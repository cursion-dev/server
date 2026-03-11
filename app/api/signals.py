import threading
from django.db.models.signals import post_save
from django.db import transaction
from django.dispatch import receiver
from .utils.flowr import Flowr
from .utils.agent import Agent
from .tasks import case_pre_run_bg
from .models import *
from cursion import settings






@receiver(post_save, sender=FlowRun)
def flowrun_created(sender, instance, created, **kwargs):
    
    # defing instance as new flowrun
    flowrun = instance
    
    # check location
    if settings.LOCATION == 'us':

        # init Flowr & execute run_next()
        Flowr(flowrun_id=str(flowrun.id)).run_next()

    # return None
    return None




@receiver(post_save, sender=Case)
def case_created(sender, instance, created, **kwargs):
    
    # defing instance as new case
    case = instance
    
    # check location and created
    if settings.LOCATION == 'us' and created:

        # check if Case has processed
        if not case.processed:

            # return early if no site association
            if not case.site:
                case.processed = True
                case.save()
                return None

            # create process obj
            process = Process.objects.create(
                site=case.site,
                type='case.pre_run',
                object_id=str(case.id),
                account=case.account,
                progress=1
            )

            # start pre_run for new Case
            case_pre_run_bg.delay(
                case_id=str(case.id),
                process_id=str(process.id)
            )

    # return None
    return None




def _run_agent_response(chat_id: str) -> None:
    try:
        Agent(chat_id=chat_id).respond()
    except Exception as e:
        print(f'Error in Agent response: {e}')


@receiver(post_save, sender=Chat)
def chat_updated(sender, instance, created, **kwargs):
    
    # defing instance as new chat
    chat = instance

    # check if latest message is sent by user
    if len(chat.messages) > 0:
        if chat.messages[-1].get('author') == 'user':
            
            # trigger agent asynchronously after transaction commit
            transaction.on_commit(
                lambda: threading.Thread(
                    target=_run_agent_response,
                    args=(str(chat.id),),
                    daemon=True
                ).start()
            )
    
    # return None
    return None



