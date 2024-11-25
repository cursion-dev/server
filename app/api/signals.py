from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils.flowr import Flowr
from .models import *






@receiver(post_save, sender=FlowRun)
def flowrun_created(sender, instance, created, **kwargs):
    
    # defing instance as new flowrun
    flowrun = instance
   
    # init Flowr & execute run_next()
    Flowr(flowrun_id=str(flowrun.id)).run_next()

    # return None
    return None
        