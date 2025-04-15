from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils.flowr import Flowr
from .tasks import case_pre_run_bg, run_test
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
        



@receiver(post_save, sender=Scan)
def post_scan_completed(sender, instance, created, **kwargs):
    
    # defing instance as Scan
    scan = instance
    
    # check location & created
    if settings.LOCATION == 'us' and not created:

        # check scan.time_completed & Test association
        if scan.time_completed and Test.objects.filter(post_scan=scan).exists():

            # build args from scan.system data
            alert_id    = scan.system['tasks'][0]['kwargs'].get('alert_id')
            flowrun_id  = scan.system['tasks'][0]['kwargs'].get('flowrun_id')
            node_index  = scan.system['tasks'][0]['kwargs'].get('node_index')
            
            # start new Test run
            test = Test.objects.filter(post_scan=scan)[0]
            run_test.delay(
                test_id     = str(test.id),
                alert_id    = alert_id,
                flowrun_id  = flowrun_id,
                node_index  = node_index
            )
        

    # return None
    return None    
