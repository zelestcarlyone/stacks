import time
import json
from stacks.constants import COOKIE_CACHE_FILE

def _load_cached_cookies(d):
    """Load cookies from cache file."""
    if COOKIE_CACHE_FILE.exists():
        try:
            with open(COOKIE_CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Check if cookies are recent (< 24 hours old)
                cached_time = data.get('timestamp', 0)
                if time.time() - cached_time < 86400:
                    cookies_dict = data.get('cookies', {})
                    for name, value in cookies_dict.items():
                        d.session.cookies.set(name, value)
                    d.logger.info(f"Loaded {len(cookies_dict)} cached cookies")
                    return True
                else:
                    d.logger.debug("Cached cookies expired (>24h old)")
        except Exception as e:
            d.logger.debug(f"Failed to load cached cookies: {e}")
    return False

def _save_cookies_to_cache(d, cookies_dict):
    """Save cookies to cache file."""
    try:
        COOKIE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_CACHE_FILE, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'cookies': cookies_dict
            }, f, indent=2)
        d.logger.debug(f"Cached {len(cookies_dict)} cookies")
    except Exception as e:
        d.logger.debug(f"Failed to cache cookies: {e}")

def _prewarm_cookies(d):
    """Pre-warm cookies using FlareSolverr if enabled."""
    if not d.flaresolverr_url:
        return False
    
    d.logger.info("Pre-warming cookies with FlareSolverr...")
    test_url = "https://annas-archive.org"

    success, cookies, _ = d.solve_with_flaresolverr(test_url)
    
    if success and cookies:
        _save_cookies_to_cache(d, cookies)
        d.logger.info("✓ Cookies pre-warmed and cached")
        return True

    d.logger.warning("Failed to pre-warm cookies")
    return False
