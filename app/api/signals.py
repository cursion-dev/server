from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils.flowr import Flowr
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

            # create process objw
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
        