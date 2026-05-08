# Data definitions used throughout
# the Cursion platform




definitions = [
    
    # high-level test score
    {   
        'name': 'Test Score',
        'key': 'test_score',
        'value': 'obj.score'
    },
    {
        'name': 'Health',
        'key': 'current_health',
        'value': 'obj.post_scan.score'
    },
    {
        'name': 'Test Status',
        'key': 'test_status',
        'value': 'obj.status'
    },
    {
        'name': 'Images Score',
        'key': 'images_score',
        'value': 'obj.component_scores.get("images", obj.component_scores.get("images",0))'
    },
    {
        'name': 'VRT Score',
        'key': 'vrt_score',
        'value': 'obj.component_scores.get("images", obj.component_scores.get("vrt",0))'
    },
    {
        'name': 'Logs Score',
        'key': 'logs_score',
        'value': 'obj.component_scores.get("logs",0)'
    },
    {
        'name': 'HTML Score',
        'key': 'html_score',
        'value': 'obj.component_scores.get("html",0)'
    },
    {
        'name': 'Yellowlab Score',
        'key': 'yellowlab_score',
        'value': 'obj.component_scores.get("yellowlab",0)'
    },
    {
        'name': 'Lighthouse Score',
        'key': 'lighthouse_score',
        'value': 'obj.component_scores.get("lighthouse",0)'
    },
    {
        'name': 'Security Score',
        'key': 'security_score',
        'value': 'obj.component_scores.get("security",0)'
    },

    # high-level scan score
    {
        'name': 'Health',
        'key': 'health',
        'value': 'obj.score'
    },
    {
        'name': 'Error Logs',
        'key': 'logs',
        'value': 'len(obj.logs)'
    },

    # LH test data
    {
        'name': 'SEO Delta',
        'key': 'seo_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("seo_delta",0)'
    },
    {
        'name': 'PWA Delta',
        'key': 'pwa_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("pwa_delta",0)'
    },
    {
        'name': 'CRUX Delta',
        'key': 'crux_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("crux_delta",0)'
    },
    {
        'name': 'Best Practices Delta',
        'key': 'best_practices_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("best_practices_delta",0)'
    },
    {
        'name': 'Performance Delta',
        'key': 'performance_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("performance_delta",0)'
    },
    {
        'name': 'Accessibility Delta',
        'key': 'accessibility_delta',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("accessibility_delta",0)'
    },
    {
        'name': 'Lighthouse Average',
        'key': 'current_lighthouse_average',
        'value': '((obj.lighthouse_delta or {}).get("scores") or {}).get("current_average",0)'
    },

    # LH scan data
    {
        'name': 'Lighthouse Average',
        'key': 'lighthouse_average',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("average",0)'
    },
    {
        'name': 'SEO',
        'key': 'seo',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("seo",0)'
    },
    {
        'name': 'PWA',
        'key': 'pwa',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("pwa",0)'
    },
    {
        'name': 'CRUX',
        'key': 'crux',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("crux",0)'
    },
    {
        'name': 'Best Practice',
        'key': 'best_practices',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("best_practices",0)'
    },
    {
        'name': 'Performance',
        'key': 'performance',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("performance",0)'
    },
    {
        'name': 'Accessibility',
        'key': 'accessibility',
        'value': '((obj.lighthouse or {}).get("scores") or {}).get("accessibility",0)'
    },

    # Security test data
    {
        'name': 'Security Average',
        'key': 'current_security_average',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("current_average",0)'
    },
    {
        'name': 'Transport Delta',
        'key': 'transport_delta',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("transport_delta",0)'
    },
    {
        'name': 'Browser Delta',
        'key': 'browser_delta',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("browser_delta",0)'
    },
    {
        'name': 'Scripts Delta',
        'key': 'scripts_delta',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("scripts_delta",0)'
    },
    {
        'name': 'Forms Delta',
        'key': 'forms_delta',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("forms_delta",0)'
    },
    {
        'name': 'Compliance Delta',
        'key': 'compliance_delta',
        'value': '((obj.security_delta or {}).get("scores") or {}).get("compliance_delta",0)'
    },

    # Security scan data
    {
        'name': 'Security Average',
        'key': 'security_average',
        'value': '((obj.security or {}).get("scores") or {}).get("average",0)'
    },
    {
        'name': 'Transport',
        'key': 'transport',
        'value': '((obj.security or {}).get("scores") or {}).get("transport",0)'
    },
    {
        'name': 'Browser',
        'key': 'browser',
        'value': '((obj.security or {}).get("scores") or {}).get("browser",0)'
    },
    {
        'name': 'Scripts',
        'key': 'scripts',
        'value': '((obj.security or {}).get("scores") or {}).get("scripts",0)'
    },
    {
        'name': 'Forms',
        'key': 'forms',
        'value': '((obj.security or {}).get("scores") or {}).get("forms",0)'
    },
    {
        'name': 'Compliance',
        'key': 'compliance',
        'value': '((obj.security or {}).get("scores") or {}).get("compliance",0)'
    },

    # caserun
    {
        'name': 'Case Run Status',
        'key': 'caserun_status',
        'value': 'obj.status'
    },
    {
        'name': 'Case Run ID',
        'key': 'caserun_id',
        'value': 'str(obj.id)'
    },
    {
        'name': 'Case Title',
        'key': 'case_title',
        'value': 'obj.title'
    },
    {
        'name': 'Case ID',
        'key': 'case_id',
        'value': 'str(obj.case.id)'
    },

    # flowrun
    {
        'name': 'Flow Run Status',
        'key': 'flowrun_status',
        'value': 'obj.status'
    },
    {
        'name': 'Flow Run ID',
        'key': 'flowrun_id',
        'value': 'str(obj.id)'
    },
    {
        'name': 'Flow Title',
        'key': 'flow_title',
        'value': 'obj.title'
    },
    {
        'name': 'Flow ID',
        'key': 'flow_id',
        'value': 'str(obj.flow.id)'
    },

    # report
    {
        'name': 'Report URL',
        'key': 'report_url',
        'value': 'obj.path'
    },
    {
        'name': 'Report ID',
        'key': 'report_id',
        'value': 'str(obj.id)'
    },

    # issue
    {
        'name': 'Issue Title',
        'key': 'issue_title',
        'value': 'obj.title'
    },
    {
        'name': 'Issue Details',
        'key': 'issue_details',
        'value': 'obj.details'
    },
    {
        'name': 'Issue ID',
        'key': 'issue_id',
        'value': 'str(obj.id)'
    },
    {
        'name': 'Issue Affected ID',
        'key': 'issue_affected_id',
        'value': 'str(obj.affected.get("id"))'
    },
    {
        'name': 'Issue Affected',
        'key': 'issue_affected',
        'value': 'str(obj.affected.get("str"))'
    },
    {
        'name': 'Issue Affected Type',
        'key': 'issue_affected_type',
        'value': 'str(obj.affected.get("type"))'
    },
    {
        'name': 'Issue Trigger Type',
        'key': 'issue_trigger_type',
        'value': 'str(obj.trigger.get("type"))'
    },
    {
        'name': 'Issue Trigger ID',
        'key': 'issue_trigger_id',
        'value': 'str(obj.trigger.get("id"))'
    },

    # test
    {
        'name': 'Test ID',
        'key': 'test_id',
        'value': 'str(obj.id)'
    },

    # scan
    {
        'name': 'Scan ID',
        'key': 'scan_id',
        'value': 'str(obj.id)'
    },

    # page
    {
        'name': 'Page ID',
        'key': 'page_id',
        'value': 'str(obj.page.id)'
    },
    {
        'name': 'Page URL',
        'key': 'page_url',
        'value': 'obj.page.page_url'
    },

    # site
    {
        'name': 'Site ID',
        'key': 'site_id',
        'value': 'str(obj.site.id)'
    },
    {
        'name': 'Site URL',
        'key': 'site_url',
        'value': 'obj.site.site_url'
    },
]





# get definition
def get_definition(key: str=None, name: str=None) -> str:
    """ 
    Finds the specific data definition based on the 
    key or name provided.

    Args:
        "key"   : str,
        "name"  : str,
    
    Returns: "definition" dict, or None
    """

    # setting default
    selected = None

    # iterate and search through definitions
    for obj in definitions:
        if obj['key'] == key or obj['name'] == name:
            selected = obj
            break
    
    # return definition
    return selected
