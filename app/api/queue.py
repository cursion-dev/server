from __future__ import annotations

from celery import Task
from celery.utils.log import get_task_logger
from contextlib import contextmanager
from django.apps import apps
from redis import Redis
from cursion import settings
import time, random, secrets




# setting logger 
logger = get_task_logger(__name__)


class BaseTaskWithRetry(Task):
    autoretry_for = (Exception, KeyError)
    retry_kwargs = {'max_retries': int(settings.MAX_ATTEMPTS - 1)}
    retry_backoff = True


# setting redis client
redis_client = Redis.from_url(settings.CELERY_BROKER_URL)

CELERY_QUEUE_SCHEDULED = getattr(settings, 'CELERY_QUEUE_SCHEDULED', 'scheduled')
CELERY_QUEUE_ON_DEMAND = getattr(settings, 'CELERY_QUEUE_ON_DEMAND', 'on_demand')


def get_task_queue(task_request=None, kwargs: dict | None = None) -> str:
    if kwargs and kwargs.get('_queue'):
        return str(kwargs['_queue'])
    if task_request is not None:
        try:
            delivery_info = getattr(task_request, 'delivery_info', {}) or {}
            routing_key = delivery_info.get('routing_key')
            if routing_key:
                return str(routing_key)
        except Exception:
            pass
    return str(getattr(settings, 'CELERY_TASK_DEFAULT_QUEUE', CELERY_QUEUE_SCHEDULED))


def apply_async_in_queue(task, *, kwargs: dict, queue: str, task_id: str | None = None):
    return task.apply_async(
        kwargs=kwargs,
        queue=queue,
        routing_key=queue,
        task_id=task_id,
    )


_ACCT_SEMAPHORE_SCRIPT = redis_client.register_script(
    """
    local held_key = KEYS[1]
    local pending_key = KEYS[2]
    local token = ARGV[1]
    local now_ms = tonumber(ARGV[2])
    local ttl_ms = tonumber(ARGV[3])
    local limit = tonumber(ARGV[4])
    local pending_max_age_ms = tonumber(ARGV[5])

    redis.call('ZREMRANGEBYSCORE', held_key, '-inf', now_ms)
    redis.call('ZREMRANGEBYSCORE', pending_key, '-inf', now_ms - pending_max_age_ms)

    -- ensure token is in pending with enqueue time; don't overwrite if exists
    if redis.call('ZSCORE', pending_key, token) == false then
      redis.call('ZADD', pending_key, now_ms, token)
    end

    local rank = redis.call('ZRANK', pending_key, token)
    if rank == false then
      rank = 0
    end

    -- FIFO gating: only the first `limit` pending tokens are eligible to run
    if rank >= limit then
      return {0, rank}
    end

    local count = tonumber(redis.call('ZCARD', held_key))
    if count >= limit then
      return {0, rank}
    end

    redis.call('ZREM', pending_key, token)
    redis.call('ZADD', held_key, now_ms + ttl_ms, token)
    redis.call('PEXPIRE', held_key, ttl_ms + 60000)
    redis.call('PEXPIRE', pending_key, pending_max_age_ms + 60000)
    return {1, rank}
    """
)


def _account_semaphore_key(account_id: str) -> str:
    return f"semaphore:account:{account_id}:held"


def _account_pending_key(account_id: str) -> str:
    return f"semaphore:account:{account_id}:pending"


def _get_account_concurrency_limit(account_id: str) -> int:
    try:
        Account = apps.get_model('api', 'Account')
        account = Account.objects.get(id=account_id)
        return int((account.usage or {}).get('concurrency', 2))
    except Exception:
        return 2


@contextmanager
def account_concurrency_slot(self_task, *, account_id: str, ttl_seconds: int = 21600):
    limit = _get_account_concurrency_limit(account_id)
    if limit <= 0:
        yield False, 0
        return

    token = str(getattr(self_task.request, 'id', None) or secrets.token_hex(16))
    now_ms      = int(time.time() * 1000)
    ttl_ms      = int(ttl_seconds * 1000)
    pending_max_age_ms = int(6 * 60 * 60 * 1000)
    held_key = _account_semaphore_key(account_id)
    pending_key = _account_pending_key(account_id)
    result = _ACCT_SEMAPHORE_SCRIPT(
        keys=[held_key, pending_key],
        args=[token, now_ms, ttl_ms, limit, pending_max_age_ms],
    )
    acquired = bool(result and int(result[0]) == 1)
    rank = int(result[1]) if result and len(result) > 1 else 0
    try:
        yield acquired, rank
    finally:
        if acquired:
            try:
                redis_client.zrem(held_key, token)
            except Exception:
                pass


def _reschedule_due_to_concurrency(self_task, *, rank: int) -> None:
    base            = 2.0
    per_position    = 4.0
    max_wait        = 240.0
    jitter          = random.uniform(0.5, 2.5)
    countdown       = min(max_wait, base + (max(0, int(rank)) * per_position) + jitter)

    delivery_info   = getattr(self_task.request, 'delivery_info', {}) or {}
    queue           = delivery_info.get('routing_key') or getattr(settings, 'CELERY_TASK_DEFAULT_QUEUE', CELERY_QUEUE_SCHEDULED)
    kwargs          = getattr(self_task.request, 'kwargs', {}) or {}

    self_task.apply_async(
        kwargs=kwargs,
        countdown=countdown,
        queue=queue,
        routing_key=queue,
        task_id=str(getattr(self_task.request, 'id', '') or secrets.token_hex(16)),
    )


def _get_account_id_from_scan_id(scan_id: str) -> str | None:
    try:
        Scan = apps.get_model('api', 'Scan')
        scan = Scan.objects.select_related('page', 'page__account').get(id=scan_id)
        return str(scan.page.account.id) if scan.page and scan.page.account else None
    except Exception:
        return None


def _get_account_id_from_test_id(test_id: str) -> str | None:
    try:
        Test = apps.get_model('api', 'Test')
        test = Test.objects.select_related('page', 'page__account').get(id=test_id)
        return str(test.page.account.id) if test.page and test.page.account else None
    except Exception:
        return None


def _get_account_id_from_caserun_id(caserun_id: str) -> str | None:
    try:
        CaseRun = apps.get_model('api', 'CaseRun')
        caserun = CaseRun.objects.select_related('account').get(id=caserun_id)
        return str(caserun.account.id) if caserun.account else None
    except Exception:
        return None


def _get_account_id_from_page_id(page_id: str) -> str | None:
    try:
        Page = apps.get_model('api', 'Page')
        page = Page.objects.select_related('account').get(id=page_id)
        return str(page.account.id) if page.account else None
    except Exception:
        return None




# setting locking manager to prevent duplicate tasks
@contextmanager
def task_lock(lock_name, timeout=300):
    lock = redis_client.lock(lock_name, timeout=timeout)
    acquired = lock.acquire(blocking=False)
    logger.info(f"Lock {'acquired' if acquired else 'not acquired'} for {lock_name}")
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
            logger.info(f"Lock released for {lock_name}")

@contextmanager
def _always_acquired():
    yield True, 0

