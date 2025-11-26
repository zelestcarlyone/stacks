import requests

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
        
        response = requests.post(
            f"{d.flaresolverr_url}/v1",
            json=payload,
            timeout=d.flaresolverr_timeout / 1000 + 10
        )
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'ok':
            solution = data.get('solution', {})
            cookies_list = solution.get('cookies', [])
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
            html_content = solution.get('response')
            
            d.logger.info(f"FlareSolverr: Success - got {len(cookies_dict)} cookies")
            
            # Apply cookies to session
            for name, value in cookies_dict.items():
                d.session.cookies.set(name, value)

            # Cache cookies for this domain (for reuse on retry/future downloads)
            d.save_cookies_to_cache(cookies_dict, domain=url)

            return True, cookies_dict, html_content
        else:
            error_msg = data.get('message', 'Unknown error')
            d.logger.error(f"FlareSolverr failed: {error_msg}")
            return False, {}, None
            
    except requests.Timeout:
        d.logger.error("FlareSolverr timeout")
        return False, {}, None
    except Exception as e:
        d.logger.error(f"FlareSolverr error: {e}")
        return False, {}, None