# Data definitions used throughout
# The Cursion platform




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
        'name': 'Avg Image Score',
        'key': 'avg_image_score',
        'value': 'obj.images_delta.get("average_score",0)'
    },
    {
        'name': 'List of Image Scores',
        'key': 'image_scores',
        'value': 'str([i["score"] for i in obj.images_delta["images"]])'
    },
    {
        'name': 'Test Status',
        'key': 'test_status',
        'value': 'obj.status'
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
        'value': 'obj.lighthouse_delta["scores"].get("seo_delta",0)'
    },
    {
        'name': 'PWA Delta',
        'key': 'pwa_delta',
        'value': 'obj.lighthouse_delta["scores"].get("pwa_delta",0)'
    },
    {
        'name': 'CRUX Delta',
        'key': 'crux_delta',
        'value': 'obj.lighthouse_delta["scores"].get("crux_delta",0)'
    },
    {
        'name': 'Best Practices Delta',
        'key': 'best_practices_delta',
        'value': 'obj.lighthouse_delta["scores"].get("best_practices_delta",0)'
    },
    {
        'name': 'Performance Delta',
        'key': 'performance_delta',
        'value': 'obj.lighthouse_delta["scores"].get("performance_delta",0)'
    },
    {
        'name': 'Accessibility Delta',
        'key': 'accessibility_delta',
        'value': 'obj.lighthouse_delta["scores"].get("accessibility_delta",0)'
    },
    {
        'name': 'Lighthouse Average',
        'key': 'current_lighthouse_average',
        'value': 'obj.lighthouse_delta["scores"].get("current_average",0)'
    },

    # LH scan data
    {
        'name': 'Lighthouse Average',
        'key': 'lighthouse_average',
        'value': 'obj.lighthouse["scores"].get("average",0)'
    },
    {
        'name': 'SEO',
        'key': 'seo',
        'value': 'obj.lighthouse["scores"].get("seo",0)'
    },
    {
        'name': 'PWA',
        'key': 'pwa',
        'value': 'obj.lighthouse["scores"].get("pwa",0)'
    },
    {
        'name': 'CRUX',
        'key': 'crux',
        'value': 'obj.lighthouse["scores"].get("crux",0)'
    },
    {
        'name': 'Best Practice',
        'key': 'best_practices',
        'value': 'obj.lighthouse["scores"].get("best_practices",0)'
    },
    {
        'name': 'Performance',
        'key': 'performance',
        'value': 'obj.lighthouse["scores"].get("performance",0)'
    },
    {
        'name': 'Accessibility',
        'key': 'accessibility',
        'value': 'obj.lighthouse["scores"].get("accessibility",0)'
    },

    # YL test data
    {
        'name': 'Yellowlab Average',
        'key': 'current_yellowlab_average',
        'value': 'obj.yellowlab_delta["scores"].get("current_average",0)'
    },
    {
        'name': 'Page Weight Delta',
        'key': 'pageWeight_delta',
        'value': 'obj.yellowlab_delta["scores"].get("pageWeight_delta",0)'
    },
    {
        'name': 'Images Delta',
        'key': 'images_delta',
        'value': 'obj.yellowlab_delta["scores"].get("images_delta",0)'
    },
    {
        'name': ' DOM Complexity Delta',
        'key': 'domComplexity_delta',
        'value': 'obj.yellowlab_delta["scores"].get("domComplexity_delta",0)'
    },
    {
        'name': 'JS Complexity Delta',
        'key': 'javascriptComplexity_delta',
        'value': 'obj.yellowlab_delta["scores"].get("javascriptComplexity_delta",0)'
    },
    {
        'name': 'Bad JS Delta',
        'key': 'badJavascript_delta',
        'value': 'obj.yellowlab_delta["scores"].get("badJavascript_delta",0)'
    },
    {
        'name': 'jQuery Delta',
        'key': 'jQuery_delta',
        'value': 'obj.yellowlab_delta["scores"].get("jQuery_delta",0)'
    },
    {
        'name': 'CSS Complexity Delta',
        'key': 'cssComplexity_delta',
        'value': 'obj.yellowlab_delta["scores"].get("cssComplexity_delta",0)'
    },
    {
        'name': 'Bad CSS Delta',
        'key': 'badCSS_delta',
        'value': 'obj.yellowlab_delta["scores"].get("badCSS_delta",0)'
    },
    {
        'name': 'Fonts Delta',
        'key': 'fonts_delta',
        'value': 'obj.yellowlab_delta["scores"].get("fonts_delta",0)'
    },
    {
        'name': 'Server Config Delta',
        'key': 'serverConfig_delta',
        'value': 'obj.yellowlab_delta["scores"].get("serverConfig_delta",0)'
    },

    # YL scan data
    {
        'name': 'Yellowlab Average',
        'key': 'yellowlab_average',
        'value': 'obj.yellowlab["scores"].get("globalScore",0)'
    },
    {
        'name': 'Page Weight',
        'key': 'pageWeight',
        'value': 'obj.yellowlab["scores"].get("pageWeight",0)'
    },
    {
        'name': 'Images',
        'key': 'images',
        'value': 'obj.yellowlab["scores"].get("images",0)'
    },
    {
        'name': 'DOM Complexity',
        'key': 'domComplexity',
        'value': 'obj.yellowlab["scores"].get("domComplexity",0)'
    },
    {
        'name': 'JS Complexity',
        'key': 'javascriptComplexity',
        'value': 'obj.yellowlab["scores"].get("javascriptComplexity",0)'
    },
    {
        'name': 'Bad JS',
        'key': 'badJavascript',
        'value': 'obj.yellowlab["scores"].get("badJavascript",0)'
    },
    {
        'name': 'jQuery',
        'key': 'jQuery',
        'value': 'obj.yellowlab["scores"].get("jQuery",0)'
    },
    {
        'name': 'CSS Complexity',
        'key': 'cssComplexity',
        'value': 'obj.yellowlab["scores"].get("cssComplexity",0)'
    },
    {
        'name': 'Bad CSS',
        'key': 'badCSS',
        'value': 'obj.yellowlab["scores"].get("badCSS",0)'
    },
    {
        'name': 'Fonts',
        'key': 'fonts',
        'value': 'obj.yellowlab["scores"].get("fonts",0)'
    },
    {
        'name': 'Server Configs',
        'key': 'serverConfig',
        'value': 'obj.yellowlab["scores"].get("serverConfig",0)'
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

    Expects: {
        "key"   : str,
        "name"  : str,
    }

    Returns -> "definition" dict, or None
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