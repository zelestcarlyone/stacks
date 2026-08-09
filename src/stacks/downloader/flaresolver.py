from urllib.parse import urlparse
from requests import Timeout

def solve_with_flaresolverr(d, url):
    """Use FlareSolverr to bypass DDoS-Guard/Cloudflare protection."""
    if not d.flaresolverr_url:
        return False, {}, None

    d.logger.info("Using FlareSolverr to solve protection challenge...")

    try:
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": d.flaresolverr_timeout
        }

        # Bypass the outbound proxy for this internal FlareSolverr call.
        #
        # Fixes the download-path half of #44: when a user has BOTH an outbound
        # proxy and FlareSolverr enabled, the proxy is applied to the shared
        # requests.Session (see AnnaDownloader.__init__, self.session.proxies).
        # FlareSolverr, however, is an internal service on the local/docker
        # network (e.g. http://flaresolverr:8191 or http://172.17.0.1:8191).
        # Routing that internal request through the *external* proxy creates a
        # proxy loop / unreachable-host failure, so the challenge is never
        # solved and every protected mirror fails.
        #
        # We override proxies per-request rather than mutating d.session.proxies
        # (as suggested in the issue), because the proxy is still wanted for the
        # actual outbound mirror/Anna's Archive downloads on the same session --
        # only this one hop to the local solver must skip it. A request-level
        # `proxies` dict takes precedence over the session's for this call only.
        no_proxy = {"http": None, "https": None}

        response = d.session.post(
            f"{d.flaresolverr_url}/v1",
            json=payload,
            timeout=d.flaresolverr_timeout / 1000 + 10,
            proxies=no_proxy
        )
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'ok':
            solution = data.get('solution', {})
            cookies_list = solution.get('cookies', [])
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
            html_content = solution.get('response')
            
            d.logger.info(f"FlareSolverr: Success - got {len(cookies_dict)} cookies")

            # Extract domain from URL
            actual_domain = urlparse(url).netloc.split(':')[0]

            # Apply cookies to session with proper domain
            for name, value in cookies_dict.items():
                d.session.cookies.set(name, value, domain=actual_domain)

            # Cache cookies for this domain (for reuse on retry/future downloads)
            d.save_cookies_to_cache(cookies_dict, domain=url)

            return True, cookies_dict, html_content
        else:
            error_msg = data.get('message', 'Unknown error')
            d.logger.error(f"FlareSolverr failed: {error_msg}")
            return False, {}, None
            
    except Timeout:
        d.logger.error("FlareSolverr timeout")
        return False, {}, None
    except Exception as e:
        d.logger.error(f"FlareSolverr error: {e}")
        return False, {}, None