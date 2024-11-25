from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils.flowr import Flowr
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
        