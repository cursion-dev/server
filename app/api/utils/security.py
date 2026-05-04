from .driver import driver_init, get_data, quit_driver
from cursion import settings
from ..models import Scan
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import boto3, json, os, uuid
import tldextract


_tld_extract = tldextract.TLDExtract(suffix_list_urls=None)





class Security():
    """
    Run a security audit for the specific `Page`
    associated with the passed `Scan`.

    Args:
        scan    : object
        driver  : object

    Returns:
        dict
    """


    def __init__(self, scan, driver=None):

        # set shared objects
        self.scan = scan
        self.site = scan.site
        self.page = scan.page

        # track if driver was passed from caller
        self._driver_provided = driver is not None

        # setup driver
        self.driver = driver_init(
            browser=self.scan.configs.get('browser', 'chrome'),
            window_size=self.scan.configs['window_size'],
            device=self.scan.configs['device']
        ) if not driver else driver

        # setup boto3 configurations
        self.s3 = boto3.client(
            's3', aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME),
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL)
        )

        # data shapes
        self.categories = ['transport', 'browser', 'scripts', 'forms', 'compliance']
        self.category_titles = {
            'transport': 'Transport Security',
            'browser': 'Browser Protections',
            'scripts': 'Script Safety',
            'forms': 'Form Security',
            'compliance': 'Compliance & Privacy',
        }
        self.category_weights = {
            'transport': 30,
            'browser': 25,
            'scripts': 20,
            'forms': 15,
            'compliance': 10,
        }

        # empty data shell for extractor
        self.data = {}

        # score mapping
        self.status_scores = {
            'pass': 1.0,
            'warning': 0.5,
            'fail': 0.0,
            'informational': None,
            'not_applicable': None,
            'error': None,
        }

        # detectors and allow lists
        self.tracker_domains = {
            'google-analytics.com', 'googletagmanager.com',
            'doubleclick.net', 'facebook.net', 'facebook.com',
            'hotjar.com', 'segment.com', 'mixpanel.com',
            'cdn.segment.com', 'clarity.ms', 'matomo',
        }
        self.cdn_domains = {
            'cdn.jsdelivr.net', 'unpkg.com', 'cdnjs.cloudflare.com',
            'ajax.googleapis.com', 'code.jquery.com',
            'stackpath.bootstrapcdn.com', 'fonts.googleapis.com',
            'fonts.gstatic.com',
        }
        self.approved_script_domains = set(getattr(settings, 'SECURITY_APPROVED_SCRIPT_DOMAINS', []))



    def extractor(self):
        """
        Using self.driver, extracts all required data
        to be used by the security auditors.

        Returns:
            self.data
        """

        # using self.driver, extract html & logs
        self.driver.get(self.page.page_url)
        data = get_data(
            driver=self.driver,
            browser=self.scan.configs.get('browser', 'chrome'),
            max_wait_time=int(self.scan.configs.get('max_wait_time', 30)),
            min_wait_time=int(self.scan.configs.get('min_wait_time', 3)),
            interval=int(self.scan.configs.get('interval', 1)),
        )
        html = data.get('html')
        logs = data.get('logs', [])

        final_url = self.driver.current_url

        # normalize all artifacts
        soup = BeautifulSoup(html or '', 'html.parser')
        scripts = self._extract_scripts(soup, final_url)
        forms = self._extract_forms(soup, final_url)
        iframes = self._extract_iframes(soup, final_url)
        links = self._extract_policy_links(soup, final_url)
        events = self._extract_console_security_events(logs)

        network_data = self._extract_network_artifacts()

        self.data = {
            'start_url': self.page.page_url,
            'final_url': final_url,
            'redirect_chain': network_data.get('redirect_chain', []),
            'headers': network_data.get('headers', {}),
            'tls': network_data.get('tls', {}),
            'resources': network_data.get('resources', []),
            'status_code': network_data.get('status_code'),
            'cookies': network_data.get('cookies', []),
            'scripts': scripts,
            'forms': forms,
            'iframes': iframes,
            'links': links,
            'console_security_events': events,
            'consent_banner_detected': self._detect_consent_banner(soup),
            'trackers_detected': self._detect_trackers(scripts, iframes),
        }

        return self.data




    def _safe_driver_url(self):
        """
        Safely read current URL from selenium driver.
        """

        try:
            if self.driver and self.driver.current_url:
                return self.driver.current_url
        except Exception:
            pass

        return None



    def _extract_scripts(self, soup, base_url):
        scripts = []
        page_host = self._host(base_url)

        for tag in soup.find_all('script'):
            src = tag.get('src')
            src_url = urljoin(base_url, src) if src else None
            domain = self._host(src_url) if src_url else page_host
            third_party = bool(domain and page_host and not self._is_same_site_domain(domain, page_host))

            scripts.append({
                'src': src_url,
                'inline': src is None,
                'integrity': tag.get('integrity'),
                'async': tag.has_attr('async'),
                'defer': tag.has_attr('defer'),
                'type': tag.get('type'),
                'domain': domain,
                'third_party': third_party,
            })

        return scripts



    def _extract_forms(self, soup, base_url):
        forms = []
        page_host = self._host(base_url)
        page_secure = self._is_https(base_url)

        sensitive_patterns = [
            'password', 'pass', 'email', 'phone', 'card', 'cc', 'cvv',
            'ssn', 'social', 'dob', 'birth', 'address', 'name',
        ]

        payment_patterns = ['card', 'credit', 'debit', 'cvv', 'expiry', 'exp', 'billing']

        for form in soup.find_all('form'):
            action = form.get('action')
            explicit_action = bool(str(action or '').strip())
            action_url = urljoin(base_url, action) if explicit_action else base_url
            method      = (form.get('method') or 'get').lower()

            fields = []
            sensitive_fields = []
            payment_fields = []

            for field in form.find_all(['input', 'textarea', 'select']):
                
                field_name  = (field.get('name') or '')
                field_id    = (field.get('id') or '')
                field_type  = (field.get('type') or 'text').lower()
                composite   = f'{field_name} {field_id} {field_type}'.lower()

                entry = {
                    'name': field_name,
                    'id': field_id,
                    'type': field_type,
                    'autocomplete': field.get('autocomplete'),
                }
                fields.append(entry)

                if field_type == 'password' or any(x in composite for x in sensitive_patterns):
                    sensitive_fields.append(entry)
                if any(x in composite for x in payment_patterns):
                    payment_fields.append(entry)

            action_host     = self._host(action_url)
            cross_origin    = bool(action_host and page_host and not self._is_same_site_domain(action_host, page_host))
            action_scheme   = self._scheme(action_url)
            is_http_target  = action_scheme in ['http', 'https']
            insecure_target = bool(action_url and is_http_target and not self._is_https(action_url))

            forms.append({
                'action': action_url,
                'explicit_action': explicit_action,
                'method': method,
                'fields': fields,
                'sensitive_fields': sensitive_fields,
                'payment_like_fields': payment_fields,
                'cross_origin': cross_origin,
                'insecure_target': insecure_target,
                'page_secure': page_secure,
            })

        return forms



    def _extract_iframes(self, soup, base_url):
        items = []
        page_host = self._host(base_url)

        for frame in soup.find_all('iframe'):
            src = frame.get('src')
            src_url = urljoin(base_url, src) if src else None
            domain = self._host(src_url) if src_url else None
            third_party = bool(domain and page_host and not self._is_same_site_domain(domain, page_host))

            items.append({
                'src': src_url,
                'domain': domain,
                'sandbox': frame.get('sandbox'),
                'allow': frame.get('allow'),
                'third_party': third_party,
            })

        return items



    def _extract_policy_links(self, soup, base_url):
        links = []

        for a in soup.find_all('a'):
            href = a.get('href')
            text = (a.get_text() or '').strip().lower()
            href_url = urljoin(base_url, href) if href else None
            if not href_url:
                continue

            links.append({
                'href': href_url,
                'text': text,
            })

        def _match(*needles):
            for l in links:
                target = (l.get('href', '') + ' ' + l.get('text', '')).lower()
                if any(n in target for n in needles):
                    return True
            return False

        return {
            'all': links,
            'privacy_policy': _match('privacy policy', '/privacy', 'privacy-policy'),
            'terms': _match('terms of service', 'terms & conditions', '/terms', '/tos'),
            'contact_or_report': _match('contact', 'report abuse', 'security', 'support'),
        }



    def _extract_console_security_events(self, logs):
        events = []

        patterns = [
            ('mixed_content', ['mixed content']),
            ('insecure_form', ['insecure form', 'password field is present']),
            ('csp_violation', ['content security policy', 'violates the following content security policy']),
            ('cookie_warning', ['cookie', 'samesite']),
            ('certificate_warning', ['certificate', 'tls', 'ssl']),
            ('blocked_resource', ['blocked', 'refused to load']),
        ]

        for entry in logs or []:
            message = str((entry or {}).get('message', ''))
            level = str((entry or {}).get('level', '')).lower() or 'info'
            source = str((entry or {}).get('source', ''))
            message_lower = message.lower()

            event_type = None
            for t, keys in patterns:
                if any(k in message_lower for k in keys):
                    event_type = t
                    break

            if not event_type:
                continue

            severity = 'warning'
            if level in ['error', 'severe']:
                severity = 'high'
            elif level in ['warning', 'warn']:
                severity = 'warning'
            else:
                severity = 'low'

            events.append({
                'type': event_type,
                'message': message,
                'source': source,
                'severity': severity,
            })

        return events



    def _extract_network_artifacts(self):
        """
        Attempt to parse response headers / status / redirects from
        Chromium performance logs. Safe no-op for unsupported browsers.
        """

        headers         = {}
        status_code     = None
        redirect_chain  = []
        resources       = []
        cookies         = []

        try:
            browser = self.scan.configs.get('browser', 'chrome')
            if browser == 'firefox':
                return {
                    'headers': {},
                    'status_code': None,
                    'redirect_chain': [],
                    'resources': [],
                    'tls': {},
                    'cookies': [],
                }

            raw_logs = self.driver.get_log('performance')
            for item in raw_logs:
                try:
                    payload = json.loads(item.get('message', '{}')).get('message', {})
                except Exception:
                    continue

                method = payload.get('method')
                params = payload.get('params', {})

                if method == 'Network.requestWillBeSent':
                    req = params.get('request', {})
                    if req.get('url'):
                        resources.append({
                            'url': req.get('url'),
                            'type': params.get('type'),
                            'secure': self._is_https(req.get('url')),
                        })
                    if params.get('redirectResponse'):
                        prev_url = params.get('redirectResponse', {}).get('url')
                        if prev_url:
                            redirect_chain.append(prev_url)

                if method == 'Network.responseReceived':
                    res = params.get('response', {})
                    url = res.get('url')
                    if url and self._urls_match_loose(url, self._safe_driver_url()):
                        headers = res.get('headers', {}) or headers
                        status_code = res.get('status')

            # parse Set-Cookie if available
            set_cookie = ''
            for h in headers:
                if str(h).lower() == 'set-cookie':
                    set_cookie = headers[h]
                    break

            if set_cookie:
                if isinstance(set_cookie, list):
                    header_values = set_cookie
                else:
                    header_values = [set_cookie]

                for item in header_values:
                    parts = [p.strip().lower() for p in str(item).split(';') if p.strip()]
                    attrs = set(parts[1:])
                    cookies.append({
                        'raw': item,
                        'secure': 'secure' in attrs,
                        'httponly': 'httponly' in attrs,
                        'samesite': any(a.startswith('samesite=') for a in attrs),
                        'third_party': False,
                    })

        except Exception as e:
            print(e)

        return {
            'headers': headers,
            'status_code': status_code,
            'redirect_chain': redirect_chain,
            'resources': resources,
            'tls': {},
            'cookies': cookies,
        }



    def run_security_audits(self, artifacts):
        """
        Execute deterministic audits against normalized artifacts.
        """

        audits = []

        start_url   = artifacts.get('start_url')
        final_url   = artifacts.get('final_url')
        headers     = {str(k).lower(): v for k, v in (artifacts.get('headers') or {}).items()}
        scripts     = artifacts.get('scripts') or []
        forms       = artifacts.get('forms') or []
        iframes     = artifacts.get('iframes') or []
        events      = artifacts.get('console_security_events') or []
        cookies     = artifacts.get('cookies') or []
        links       = artifacts.get('links') or {}
        resources   = artifacts.get('resources') or []

        has_https = self._is_https(final_url)
        started_http = str(start_url or '').lower().startswith('http://')

        mixed_events = [e for e in events if e.get('type') == 'mixed_content']

        insecure_subresources = [
            r for r in resources
            if r.get('url') and str(r.get('url')).startswith('http://')
        ]
        insecure_subresources += [
            s for s in scripts
            if s.get('src') and str(s.get('src')).startswith('http://')
        ]
        insecure_subresources += [
            f for f in iframes
            if f.get('src') and str(f.get('src')).startswith('http://')
        ]

        insecure_form_targets   = [f for f in forms if f.get('insecure_target')]
        sensitive_forms         = [f for f in forms if len(f.get('sensitive_fields') or []) > 0]
        sensitive_cross_origin  = [f for f in sensitive_forms if f.get('cross_origin')]
        sensitive_get           = [f for f in sensitive_forms if f.get('method') == 'get']
        payment_forms           = [f for f in forms if len(f.get('payment_like_fields') or []) > 0]

        # transport audits
        audits.append(self._build_audit(
            audit_id='https-used',
            title='Page uses HTTPS',
            category='transport',
            status='pass' if has_https else 'fail',
            severity='critical' if not has_https else None,
            confidence='high',
            weight=10,
            details='Final page URL uses HTTPS.' if has_https else 'Final page URL is not HTTPS.',
            evidence={'final_url': final_url},
            recommendation='Serve the page over HTTPS and redirect all HTTP requests to HTTPS.' if not has_https else None,
        ))

        redirects_https = started_http and has_https
        redirect_status = 'pass' if redirects_https else 'fail' if started_http else 'not_applicable'
        audits.append(self._build_audit(
            audit_id='http-redirects-to-https',
            title='HTTP requests redirect to HTTPS',
            category='transport',
            status=redirect_status,
            severity='high' if redirect_status == 'fail' else None,
            confidence='medium',
            weight=8,
            details='HTTP requests resolve to HTTPS final URL.' if redirect_status == 'pass' else 'HTTP requests do not reliably redirect to HTTPS.' if redirect_status == 'fail' else 'Start URL is already HTTPS; HTTP redirect behavior was not directly verified.',
            evidence={'start_url': start_url, 'final_url': final_url, 'redirect_chain': artifacts.get('redirect_chain')},
            recommendation='Add a server-side 301/308 redirect from HTTP to HTTPS.' if redirect_status == 'fail' else None,
        ))

        cert_status = 'not_applicable' if has_https else 'fail'
        audits.append(self._build_audit(
            audit_id='certificate-valid',
            title='TLS certificate appears valid',
            category='transport',
            status=cert_status,
            severity='high' if cert_status == 'fail' else None,
            confidence='low',
            weight=8,
            details='Certificate metadata not available in current collector.' if has_https else 'HTTPS is not in use, certificate cannot be validated.',
            evidence={'tls': artifacts.get('tls', {})},
            recommendation='Ensure a valid TLS certificate is configured for this host.' if cert_status == 'fail' else None,
        ))

        audits.append(self._build_audit(
            audit_id='certificate-expiring-soon',
            title='TLS certificate is not expiring soon',
            category='transport',
            status='not_applicable',
            severity=None,
            confidence='low',
            weight=4,
            details='Certificate expiration inspection is not available in MVP collector.',
            evidence={'tls': artifacts.get('tls', {})},
            recommendation=None,
        ))

        mixed_status = 'fail' if len(mixed_events) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='mixed-content',
            title='No mixed-content warnings detected',
            category='transport',
            status=mixed_status,
            severity='high' if mixed_status == 'fail' else None,
            confidence='high',
            weight=7,
            details='Mixed content events were detected in console logs.' if mixed_status == 'fail' else 'No mixed content events detected in console logs.',
            evidence={'mixed_events': mixed_events},
            recommendation='Load all page resources via HTTPS and remove HTTP references.' if mixed_status == 'fail' else None,
        ))

        subresource_status = 'fail' if len(insecure_subresources) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='insecure-subresource-request',
            title='No insecure subresource requests',
            category='transport',
            status=subresource_status,
            severity='high' if subresource_status == 'fail' else None,
            confidence='medium',
            weight=6,
            details='Found HTTP-loaded scripts/iframes/resources.' if subresource_status == 'fail' else 'No HTTP-loaded scripts/iframes/resources detected.',
            evidence={'insecure_subresources': insecure_subresources[:25]},
            recommendation='Upgrade external resource URLs to HTTPS or remove insecure dependencies.' if subresource_status == 'fail' else None,
        ))

        form_target_status = 'fail' if len(insecure_form_targets) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='insecure-form-target',
            title='Forms do not submit to insecure targets',
            category='transport',
            status=form_target_status,
            severity='critical' if form_target_status == 'fail' else None,
            confidence='high',
            weight=10,
            details='One or more forms submit to non-HTTPS endpoints.' if form_target_status == 'fail' else 'No insecure form targets detected.',
            evidence={'insecure_form_targets': insecure_form_targets[:20]},
            recommendation='Update form actions to HTTPS endpoints and enforce secure transport.' if form_target_status == 'fail' else None,
        ))

        # browser audits
        hsts_present = 'strict-transport-security' in headers
        audits.append(self._build_audit(
            audit_id='hsts-present',
            title='HSTS header is present',
            category='browser',
            status='pass' if hsts_present else 'warning',
            severity='medium' if not hsts_present else None,
            confidence='high',
            weight=6,
            details='Strict-Transport-Security header is present.' if hsts_present else 'Strict-Transport-Security header is missing.',
            evidence={'header': headers.get('strict-transport-security')},
            recommendation='Add Strict-Transport-Security with an adequate max-age and includeSubDomains.' if not hsts_present else None,
        ))

        csp_present = 'content-security-policy' in headers
        audits.append(self._build_audit(
            audit_id='csp-present',
            title='Content-Security-Policy header is present',
            category='browser',
            status='pass' if csp_present else 'warning',
            severity='high' if not csp_present else None,
            confidence='high',
            weight=8,
            details='Content-Security-Policy header is present.' if csp_present else 'Content-Security-Policy header is missing.',
            evidence={'header': headers.get('content-security-policy')},
            recommendation='Set a restrictive Content-Security-Policy tailored to your app resources.' if not csp_present else None,
        ))

        xcto_present = headers.get('x-content-type-options', '').lower() == 'nosniff'
        audits.append(self._build_audit(
            audit_id='x-content-type-options-present',
            title='X-Content-Type-Options is set to nosniff',
            category='browser',
            status='pass' if xcto_present else 'warning',
            severity='low' if not xcto_present else None,
            confidence='high',
            weight=4,
            details='X-Content-Type-Options: nosniff is present.' if xcto_present else 'X-Content-Type-Options: nosniff header is missing.',
            evidence={'header': headers.get('x-content-type-options')},
            recommendation='Set X-Content-Type-Options: nosniff to reduce MIME type confusion risks.' if not xcto_present else None,
        ))

        referrer_present = 'referrer-policy' in headers
        audits.append(self._build_audit(
            audit_id='referrer-policy-present',
            title='Referrer-Policy header is present',
            category='browser',
            status='pass' if referrer_present else 'warning',
            severity='low' if not referrer_present else None,
            confidence='high',
            weight=4,
            details='Referrer-Policy header is present.' if referrer_present else 'Referrer-Policy header is missing.',
            evidence={'header': headers.get('referrer-policy')},
            recommendation='Set a strict Referrer-Policy (for example strict-origin-when-cross-origin).' if not referrer_present else None,
        ))

        frame_protection = ('x-frame-options' in headers) or (
            'content-security-policy' in headers and 'frame-ancestors' in str(headers.get('content-security-policy', '')).lower()
        )
        audits.append(self._build_audit(
            audit_id='frame-protection-present',
            title='Frame embedding protections are present',
            category='browser',
            status='pass' if frame_protection else 'warning',
            severity='medium' if not frame_protection else None,
            confidence='high',
            weight=5,
            details='Frame protection is configured.' if frame_protection else 'No X-Frame-Options or frame-ancestors policy detected.',
            evidence={
                'x-frame-options': headers.get('x-frame-options'),
                'content-security-policy': headers.get('content-security-policy'),
            },
            recommendation='Set X-Frame-Options or CSP frame-ancestors to prevent unwanted framing.' if not frame_protection else None,
        ))

        permissions_present = 'permissions-policy' in headers
        audits.append(self._build_audit(
            audit_id='permissions-policy-present',
            title='Permissions-Policy header is present',
            category='browser',
            status='pass' if permissions_present else 'warning',
            severity='low' if not permissions_present else None,
            confidence='high',
            weight=3,
            details='Permissions-Policy header is present.' if permissions_present else 'Permissions-Policy header is missing.',
            evidence={'header': headers.get('permissions-policy')},
            recommendation='Set Permissions-Policy to limit access to powerful browser features.' if not permissions_present else None,
        ))

        if len(cookies) > 0:
            secure_cookie_ratio = len([c for c in cookies if c.get('secure')]) / len(cookies)
            cookie_status = 'pass' if secure_cookie_ratio == 1 else 'warning'
        else:
            cookie_status = 'not_applicable'

        audits.append(self._build_audit(
            audit_id='secure-cookies',
            title='Cookies are marked Secure',
            category='browser',
            status=cookie_status,
            severity='medium' if cookie_status == 'warning' else None,
            confidence='medium',
            weight=5,
            details='All observed cookies include Secure flag.' if cookie_status == 'pass' else 'Some observed cookies are missing Secure flag.' if cookie_status == 'warning' else 'No cookies were observed in available artifacts.',
            evidence={'cookies': cookies[:25]},
            recommendation='Set the Secure flag on cookies, especially session/auth cookies.' if cookie_status == 'warning' else None,
        ))

        if len(cookies) > 0:
            httponly_ratio = len([c for c in cookies if c.get('httponly')]) / len(cookies)
            httponly_status = 'pass' if httponly_ratio == 1 else 'warning'
        else:
            httponly_status = 'not_applicable'

        audits.append(self._build_audit(
            audit_id='httponly-cookies',
            title='Cookies are marked HttpOnly',
            category='browser',
            status=httponly_status,
            severity='medium' if httponly_status == 'warning' else None,
            confidence='medium',
            weight=5,
            details='All observed cookies include HttpOnly flag.' if httponly_status == 'pass' else 'Some observed cookies are missing HttpOnly flag.' if httponly_status == 'warning' else 'No cookies were observed in available artifacts.',
            evidence={'cookies': cookies[:25]},
            recommendation='Set HttpOnly on sensitive cookies to reduce script-level access risk.' if httponly_status == 'warning' else None,
        ))

        if len(cookies) > 0:
            samesite_ratio = len([c for c in cookies if c.get('samesite')]) / len(cookies)
            samesite_status = 'pass' if samesite_ratio == 1 else 'warning'
        else:
            samesite_status = 'not_applicable'

        audits.append(self._build_audit(
            audit_id='samesite-cookies',
            title='Cookies specify SameSite',
            category='browser',
            status=samesite_status,
            severity='medium' if samesite_status == 'warning' else None,
            confidence='medium',
            weight=5,
            details='All observed cookies include SameSite attribute.' if samesite_status == 'pass' else 'Some observed cookies are missing SameSite attribute.' if samesite_status == 'warning' else 'No cookies were observed in available artifacts.',
            evidence={'cookies': cookies[:25]},
            recommendation='Set SameSite=Lax or SameSite=Strict for cookies unless cross-site usage is required.' if samesite_status == 'warning' else None,
        ))

        # scripts audits
        third_party_domains = sorted(list(set([
            s.get('domain') for s in scripts if s.get('third_party') and s.get('domain')
        ])))

        audits.append(self._build_audit(
            audit_id='third-party-script-inventory',
            title='Third-party script inventory',
            category='scripts',
            status='informational',
            severity=None,
            confidence='high',
            weight=1,
            details=f'Detected {len(third_party_domains)} third-party script domains.',
            evidence={'domains': third_party_domains[:50]},
            recommendation=None,
        ))

        unapproved_domains = [
            d for d in third_party_domains
            if len(self.approved_script_domains) > 0 and d not in self.approved_script_domains
        ]

        if len(self.approved_script_domains) == 0:
            unapproved_status = 'informational'
            unapproved_details = 'No approved script domain allow list configured.'
        else:
            unapproved_status = 'fail' if len(unapproved_domains) > 0 else 'pass'
            unapproved_details = 'Found script domains outside the approved allow list.' if len(unapproved_domains) > 0 else 'All third-party script domains are approved.'

        audits.append(self._build_audit(
            audit_id='unapproved-script-domain',
            title='No unapproved script domains',
            category='scripts',
            status=unapproved_status,
            severity='high' if unapproved_status == 'fail' else None,
            confidence='high',
            weight=8,
            details=unapproved_details,
            evidence={'unapproved_domains': unapproved_domains[:50]},
            recommendation='Review and allow-list only trusted third-party script domains.' if unapproved_status == 'fail' else None,
        ))

        inline_count = len([s for s in scripts if s.get('inline')])
        inline_status = 'warning' if inline_count > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='inline-script-detected',
            title='Inline scripts are minimized',
            category='scripts',
            status=inline_status,
            severity='medium' if inline_status == 'warning' else None,
            confidence='high',
            weight=7,
            details='Inline scripts were detected.' if inline_status == 'warning' else 'No inline scripts detected.',
            evidence={'inline_script_count': inline_count},
            recommendation='Move inline scripts to external files and enforce CSP nonce/hash controls.' if inline_status == 'warning' else None,
        ))

        missing_sri = []
        for s in scripts:
            src = s.get('src')
            domain = s.get('domain')
            if not src:
                continue
            if domain in self.cdn_domains and not s.get('integrity'):
                missing_sri.append(src)

        sri_status = 'warning' if len(missing_sri) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='missing-sri-on-cdn-script',
            title='CDN scripts include integrity attribute',
            category='scripts',
            status=sri_status,
            severity='medium' if sri_status == 'warning' else None,
            confidence='high',
            weight=6,
            details='One or more CDN scripts are missing integrity attributes.' if sri_status == 'warning' else 'Observed CDN scripts include integrity attributes.',
            evidence={'scripts_missing_sri': missing_sri[:50]},
            recommendation='Add an integrity attribute to externally hosted CDN scripts where feasible.' if sri_status == 'warning' else None,
        ))

        unexpected_iframe_domains = sorted(list(set([
            i.get('domain') for i in iframes
            if i.get('third_party') and i.get('domain')
        ])))
        iframe_status = 'warning' if len(unexpected_iframe_domains) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='unexpected-iframe-domain',
            title='Iframes do not load unexpected third-party domains',
            category='scripts',
            status=iframe_status,
            severity='medium' if iframe_status == 'warning' else None,
            confidence='high',
            weight=5,
            details='Found third-party iframe domains.' if iframe_status == 'warning' else 'No third-party iframe domains detected.',
            evidence={'iframe_domains': unexpected_iframe_domains[:50]},
            recommendation='Review iframe sources and remove or sandbox untrusted third-party frames.' if iframe_status == 'warning' else None,
        ))

        # forms audits
        missing_action = [f for f in forms if not f.get('explicit_action')]
        if len(forms) == 0:
            form_action_status = 'not_applicable'
        else:
            form_action_status = 'fail' if len(missing_action) > 0 else 'pass'

        audits.append(self._build_audit(
            audit_id='form-action-present',
            title='Forms define explicit action targets',
            category='forms',
            status=form_action_status,
            severity='medium' if form_action_status == 'fail' else None,
            confidence='high',
            weight=6,
            details='Some forms are missing action attributes.' if form_action_status == 'fail' else 'All forms have explicit action attributes.' if form_action_status == 'pass' else 'No forms detected on page.',
            evidence={'missing_action_forms': missing_action[:20]},
            recommendation='Define explicit, approved form action URLs for all forms.' if form_action_status == 'fail' else None,
        ))

        if len(forms) == 0:
            submit_secure_status = 'not_applicable'
        else:
            submit_secure_status = 'fail' if len(insecure_form_targets) > 0 else 'pass'

        audits.append(self._build_audit(
            audit_id='form-submits-securely',
            title='Forms submit over secure transport',
            category='forms',
            status=submit_secure_status,
            severity='critical' if submit_secure_status == 'fail' else None,
            confidence='high',
            weight=9,
            details='One or more forms submit to HTTP.' if submit_secure_status == 'fail' else 'Detected form actions are secure.' if submit_secure_status == 'pass' else 'No forms detected on page.',
            evidence={'insecure_form_targets': insecure_form_targets[:20]},
            recommendation='Update form action URLs to HTTPS endpoints.' if submit_secure_status == 'fail' else None,
        ))

        sensitive_http_status = 'not_applicable'
        if len(sensitive_forms) > 0:
            sensitive_http_status = 'fail' if not has_https else 'pass'

        audits.append(self._build_audit(
            audit_id='sensitive-fields-on-insecure-page',
            title='Sensitive fields are not served on insecure pages',
            category='forms',
            status=sensitive_http_status,
            severity='critical' if sensitive_http_status == 'fail' else None,
            confidence='high',
            weight=10,
            details='Sensitive form fields detected on a non-HTTPS page.' if sensitive_http_status == 'fail' else 'Sensitive fields are on HTTPS page.' if sensitive_http_status == 'pass' else 'No sensitive form fields detected.',
            evidence={'sensitive_form_count': len(sensitive_forms), 'final_url': final_url},
            recommendation='Serve sensitive forms only over HTTPS and enforce secure redirects.' if sensitive_http_status == 'fail' else None,
        ))

        cross_origin_status = 'not_applicable'
        if len(sensitive_forms) > 0:
            cross_origin_status = 'fail' if len(sensitive_cross_origin) > 0 else 'pass'

        audits.append(self._build_audit(
            audit_id='sensitive-form-cross-origin',
            title='Sensitive forms avoid cross-origin submission',
            category='forms',
            status=cross_origin_status,
            severity='high' if cross_origin_status == 'fail' else None,
            confidence='high',
            weight=8,
            details='Sensitive forms submit to different origins.' if cross_origin_status == 'fail' else 'Sensitive forms submit to same origin.' if cross_origin_status == 'pass' else 'No sensitive form fields detected.',
            evidence={'sensitive_cross_origin_forms': sensitive_cross_origin[:20]},
            recommendation='Review why this form submits sensitive data to a different origin and ensure the destination is approved.' if cross_origin_status == 'fail' else None,
        ))

        sensitive_get_status = 'not_applicable'
        if len(sensitive_forms) > 0:
            sensitive_get_status = 'warning' if len(sensitive_get) > 0 else 'pass'

        audits.append(self._build_audit(
            audit_id='sensitive-form-uses-get',
            title='Sensitive forms do not use GET method',
            category='forms',
            status=sensitive_get_status,
            severity='high' if sensitive_get_status == 'warning' else None,
            confidence='high',
            weight=7,
            details='Sensitive forms using GET were detected.' if sensitive_get_status == 'warning' else 'Sensitive forms use non-GET methods.' if sensitive_get_status == 'pass' else 'No sensitive form fields detected.',
            evidence={'sensitive_get_forms': sensitive_get[:20]},
            recommendation='Use POST for forms collecting sensitive data and avoid query-string exposure.' if sensitive_get_status == 'warning' else None,
        ))

        has_password = len([
            f for f in sensitive_forms
            if len([x for x in (f.get('sensitive_fields') or []) if x.get('type') == 'password']) > 0
        ]) > 0
        audits.append(self._build_audit(
            audit_id='password-field-detected',
            title='Password fields detected',
            category='forms',
            status='informational',
            severity=None,
            confidence='high',
            weight=1,
            details='Password field(s) were detected on this page.' if has_password else 'No password fields detected on this page.',
            evidence={'has_password_field': has_password},
            recommendation=None,
        ))

        audits.append(self._build_audit(
            audit_id='payment-like-fields-detected',
            title='Payment-like fields detected',
            category='forms',
            status='informational',
            severity=None,
            confidence='high',
            weight=1,
            details='Payment-like fields were detected.' if len(payment_forms) > 0 else 'No payment-like fields detected.',
            evidence={'payment_like_form_count': len(payment_forms)},
            recommendation=None,
        ))

        # compliance audits
        trackers = artifacts.get('trackers_detected') or []
        tracker_status = 'warning' if len(trackers) > 0 else 'pass'
        audits.append(self._build_audit(
            audit_id='trackers-detected',
            title='Known tracker scripts are limited',
            category='compliance',
            status=tracker_status,
            severity='medium' if tracker_status == 'warning' else None,
            confidence='medium',
            weight=5,
            details='Known tracker domains were detected.' if tracker_status == 'warning' else 'No known tracker domains detected.',
            evidence={'trackers': trackers[:50]},
            recommendation='Review third-party trackers and ensure collection is justified and disclosed.' if tracker_status == 'warning' else None,
        ))

        if len(cookies) == 0:
            third_party_cookie_status = 'not_applicable'
            third_party_cookies = []
        else:
            third_party_cookies = [c for c in cookies if c.get('third_party')]
            third_party_cookie_status = 'warning' if len(third_party_cookies) > 0 else 'pass'

        audits.append(self._build_audit(
            audit_id='third-party-cookies-detected',
            title='Third-party cookies are minimized',
            category='compliance',
            status=third_party_cookie_status,
            severity='medium' if third_party_cookie_status == 'warning' else None,
            confidence='low' if third_party_cookie_status == 'not_applicable' else 'medium',
            weight=4,
            details='Third-party cookies were detected.' if third_party_cookie_status == 'warning' else 'No third-party cookies detected.' if third_party_cookie_status == 'pass' else 'Cookie ownership source is not available in MVP collector.',
            evidence={'third_party_cookies': third_party_cookies[:25]},
            recommendation='Reduce third-party cookie usage and gate non-essential cookies behind consent.' if third_party_cookie_status == 'warning' else None,
        ))

        consent_detected = bool(artifacts.get('consent_banner_detected'))
        if len(trackers) == 0:
            consent_status = 'informational'
        else:
            consent_status = 'pass' if consent_detected else 'warning'

        audits.append(self._build_audit(
            audit_id='consent-banner-detected',
            title='Consent banner presence',
            category='compliance',
            status=consent_status,
            severity='medium' if consent_status == 'warning' else None,
            confidence='medium',
            weight=5,
            details='Consent banner elements detected.' if consent_status == 'pass' else 'No consent banner indicators found while trackers were detected.' if consent_status == 'warning' else 'No tracker activity detected; consent banner check is informational.',
            evidence={'consent_banner_detected': consent_detected},
            recommendation='Provide a clear consent mechanism before non-essential trackers run.' if consent_status == 'warning' else None,
        ))

        privacy_present = bool(links.get('privacy_policy'))
        audits.append(self._build_audit(
            audit_id='privacy-policy-link-detected',
            title='Privacy policy link is detectable',
            category='compliance',
            status='pass' if privacy_present else 'warning',
            severity='medium' if not privacy_present else None,
            confidence='high',
            weight=8,
            details='Privacy policy link detected on page.' if privacy_present else 'No privacy policy link detected on page.',
            evidence={'privacy_policy_detected': privacy_present},
            recommendation='Add a clear privacy policy link in global navigation or footer.' if not privacy_present else None,
        ))

        terms_present = bool(links.get('terms'))
        audits.append(self._build_audit(
            audit_id='terms-link-detected',
            title='Terms link is detectable',
            category='compliance',
            status='pass' if terms_present else 'warning',
            severity='low' if not terms_present else None,
            confidence='high',
            weight=3,
            details='Terms link detected on page.' if terms_present else 'No terms link detected on page.',
            evidence={'terms_detected': terms_present},
            recommendation='Add a clear terms/conditions link for user-facing data flows.' if not terms_present else None,
        ))

        personal_data_without_notice = len(sensitive_forms) > 0 and not privacy_present
        pd_status = 'fail' if personal_data_without_notice else 'pass' if len(sensitive_forms) > 0 else 'not_applicable'
        audits.append(self._build_audit(
            audit_id='personal-data-form-without-notice',
            title='Personal-data forms include privacy notice access',
            category='compliance',
            status=pd_status,
            severity='high' if pd_status == 'fail' else None,
            confidence='high',
            weight=10,
            details='Sensitive form fields detected without a visible privacy policy link.' if pd_status == 'fail' else 'Sensitive form fields detected with privacy notice access.' if pd_status == 'pass' else 'No sensitive personal-data form detected.',
            evidence={'sensitive_forms': len(sensitive_forms), 'privacy_policy_detected': privacy_present},
            recommendation='Provide a privacy notice link near forms collecting personal data.' if pd_status == 'fail' else None,
        ))

        return audits



    def score_security_audits(self, audits):
        """
        Score by category and compute weighted overall average.
        """

        scores = {
            'transport': None,
            'browser': None,
            'scripts': None,
            'forms': None,
            'compliance': None,
            'average': None,
        }

        scorable_statuses = ['pass', 'warning', 'fail']

        for category in self.categories:
            category_audits = [
                a for a in audits
                if a.get('category') == category and a.get('status') in scorable_statuses
            ]

            if len(category_audits) == 0:
                scores[category] = None
                continue

            total_weight = sum([a.get('weight', 0) for a in category_audits])
            if total_weight == 0:
                scores[category] = None
                continue

            weighted_score = sum([
                float(a.get('score', 0)) * float(a.get('weight', 0))
                for a in category_audits
            ]) / total_weight

            scores[category] = int(round(weighted_score * 100))

        # weighted category average
        present = [c for c in self.categories if scores.get(c) is not None]
        if len(present) > 0:
            total_cat_weight = sum([self.category_weights[c] for c in present])
            weighted_avg = sum([
                scores[c] * self.category_weights[c]
                for c in present
            ]) / total_cat_weight
            scores['average'] = int(round(weighted_avg))

        return scores



    def build_summary(self, audits):
        """
        Build summary counters for payload metadata.
        """

        summary = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'passed': 0,
            'warnings': 0,
            'failed': 0,
        }

        for audit in audits:
            status = audit.get('status')
            severity = audit.get('severity')

            if status == 'pass':
                summary['passed'] += 1
            if status == 'warning':
                summary['warnings'] += 1
            if status == 'fail':
                summary['failed'] += 1

            if severity in ['critical', 'high', 'medium', 'low'] and status in ['warning', 'fail']:
                summary[severity] += 1

        return summary



    def build_audits_by_category(self, audits):
        """
        Build standarized audits artifact: {category: [audit, ...]}.
        """

        return {
            category: [a for a in audits if a.get('category') == category]
            for category in self.categories
        }



    def build_payload(self, artifacts, audits, scores, summary):
        """
        Build full security audit JSON payload for S3.
        """

        category_items = []
        for cat in self.categories:
            cat_audits = [a.get('id') for a in audits if a.get('category') == cat]
            category_items.append({
                'id': cat,
                'title': self.category_titles.get(cat, cat.title()),
                'score': scores.get(cat),
                'audit_ids': cat_audits,
            })

        payload = {
            'version': 'security-audit/1.0.0',
            'scan_id': str(self.scan.id),
            'site_id': str(self.site.id),
            'page_id': str(self.page.id),
            'url': artifacts.get('final_url') or self.page.page_url,
            'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'scores': scores,
            'categories': category_items,
            'audits': audits,
            'artifacts': {
                'final_url': artifacts.get('final_url'),
                'redirect_chain': artifacts.get('redirect_chain', []),
                'headers': artifacts.get('headers', {}),
                'tls': artifacts.get('tls', {}),
                'resources': artifacts.get('resources', []),
                'scripts': artifacts.get('scripts', []),
                'forms': artifacts.get('forms', []),
                'cookies': artifacts.get('cookies', []),
                'iframes': artifacts.get('iframes', []),
                'console_security_events': artifacts.get('console_security_events', []),
            },
            'summary': summary,
        }

        return payload



    def upload_security_audit(self, payload):
        """
        Upload full payload JSON to S3 and return public URL.
        """

        file_id = uuid.uuid4()
        local_path = os.path.join(settings.BASE_DIR, f'{file_id}.json')

        with open(local_path, 'w') as fp:
            json.dump(payload, fp)

        remote_path = f'static/sites/{self.site.id}/{self.page.id}/{self.scan.id}/{file_id}.json'
        root_path = settings.AWS_S3_URL_PATH
        audits_url = f'{root_path}/{remote_path}'

        with open(local_path, 'rb') as data:
            self.s3.upload_fileobj(
                data,
                str(settings.AWS_STORAGE_BUCKET_NAME),
                remote_path,
                ExtraArgs={'ACL': 'public-read', 'ContentType': 'application/json'}
            )

        os.remove(local_path)
        return audits_url



    def persist_scan_security(self, scores, s3_url):
        """
        Persist summary shape directly to Scan.security.
        """

        self.scan.security = {
            'scores': scores,
            'audits': s3_url,
            'failed': False,
        }
        self.scan.save(update_fields=['security'])
        return self.scan.security



    def get_data(self):
        """
        Main entrypoint to extract, evaluate, score, upload, persist.
        """

        try:
            artifacts = self.extractor()
            audits = self.run_security_audits(artifacts)
            scores = self.score_security_audits(audits)
            audits_payload = self.build_audits_by_category(audits)
            audits_url = self.upload_security_audit(audits_payload)
            data = self.persist_scan_security(scores, audits_url)
            data['failed'] = False
            return data

        except Exception as e:
            print(e)
            data = {
                'scores': {
                    'transport': None,
                    'browser': None,
                    'scripts': None,
                    'forms': None,
                    'compliance': None,
                    'average': None,
                },
                'audits': None,
                'failed': True,
            }
            self.scan.security = data
            self.scan.save(update_fields=['security'])
            return data

        finally:
            if not self._driver_provided and self.driver is not None:
                try:
                    quit_driver(self.driver)
                except Exception:
                    pass



    def _build_audit(
            self,
            audit_id,
            title,
            category,
            status,
            severity,
            confidence,
            weight,
            details,
            evidence,
            recommendation
        ):

        return {
            'id': audit_id,
            'title': title,
            'category': category,
            'status': status,
            'score': self.status_scores.get(status),
            'severity': severity,
            'confidence': confidence,
            'weight': weight,
            'details': details,
            'evidence': evidence or {},
            'recommendation': recommendation,
        }



    def _detect_consent_banner(self, soup):
        text = str(soup).lower()
        consent_markers = [
            'cookie consent', 'consent banner', 'accept cookies',
            'reject cookies', 'cookie settings', 'privacy choices',
        ]
        return any(x in text for x in consent_markers)



    def _detect_trackers(self, scripts, iframes):
        found = set()

        for item in (scripts or []) + (iframes or []):
            d = (item.get('domain') or '').lower()
            if any(d == t or d.endswith(f'.{t}') for t in self.tracker_domains):
                found.add(d)

        return sorted(list(found))



    def _host(self, url):
        if not url:
            return None
        try:
            return (urlparse(url).hostname or '').lower()
        except Exception:
            return None



    def _scheme(self, url):
        if not url:
            return None
        try:
            return str(urlparse(url).scheme).lower()
        except Exception:
            return None



    def _is_https(self, url):
        if not url:
            return False
        try:
            return str(urlparse(url).scheme).lower() == 'https'
        except Exception:
            return False



    def _registrable_domain(self, host):
        if not host:
            return None
        parsed = _tld_extract(str(host).lower())
        if not parsed.domain or not parsed.suffix:
            return None
        return f'{parsed.domain}.{parsed.suffix}'



    def _is_same_site_domain(self, left, right):
        if not left or not right:
            return False
        l_host = str(left).lower()
        r_host = str(right).lower()
        if l_host == r_host:
            return True
        return self._registrable_domain(l_host) == self._registrable_domain(r_host)



    def _urls_match_loose(self, left, right):
        if not left or not right:
            return False
        try:
            l = urlparse(left)
            r = urlparse(right)
            l_path = (l.path or '/').rstrip('/') or '/'
            r_path = (r.path or '/').rstrip('/') or '/'
            return (
                str(l.scheme).lower() == str(r.scheme).lower() and
                str(l.hostname or '').lower() == str(r.hostname or '').lower() and
                l_path == r_path
            )
        except Exception:
            return False



def generate_security_audit_for_scan(scan_id):
    """
    Idempotent helper for rerunning security generation for existing scans.
    """

    scan = Scan.objects.get(id=scan_id)
    return Security(scan=scan).get_data()
