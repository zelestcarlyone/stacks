import time
import json
import re
from urllib.parse import urlparse
from pathlib import Path
from stacks.constants import COOKIE_CACHE_DIR

def _get_cookie_filename(domain_or_url):
    """Convert domain/URL to a safe cookie filename.

    Examples:
        annas-archive.org -> cookie-annas-archive-org.json
        https://libgen.li/some/path -> cookie-libgen-li.json
        library.lol -> cookie-library-lol.json
    """
    # Extract domain if it's a full URL
    if '://' in domain_or_url:
        domain = urlparse(domain_or_url).netloc
    else:
        domain = domain_or_url

    # Remove port if present
    domain = domain.split(':')[0]

    # Convert to safe filename: dots to dashes
    safe_name = domain.replace('.', '-')

    return f"cookie-{safe_name}.json"

def _load_cached_cookies(d, domain='annas-archive.org'):
    """Load cookies from domain-specific cache file.

    Args:
        d: Downloader instance
        domain: Domain or URL to load cookies for (default: annas-archive.org)

    Supports two formats:
    1. JSON format: {"timestamp": 123456, "cookies": {"name": "value", ...}}
    2. Simple dict format: {"name": "value", ...}

    If timestamp is present and cookies are >24h old, they're still loaded but marked as potentially stale.
    """
    cookie_filename = _get_cookie_filename(domain)
    cookie_file = COOKIE_CACHE_DIR / cookie_filename

    if cookie_file.exists():
        try:
            with open(cookie_file, 'r') as f:
                data = json.load(f)

                # Detect format
                if 'cookies' in data:
                    # Format 1: Full format with timestamp
                    cookies_dict = data.get('cookies', {})
                    cached_time = data.get('timestamp', 0)

                    if time.time() - cached_time < 86400:
                        d.logger.info(f"Loaded {len(cookies_dict)} fresh cached cookies for {domain}")
                    else:
                        d.logger.info(f"Loaded {len(cookies_dict)} cached cookies for {domain} (potentially stale)")
                else:
                    # Format 2: Simple dict of cookies (manual entry)
                    cookies_dict = data
                    d.logger.info(f"Loaded {len(cookies_dict)} manually cached cookies for {domain}")

                # Extract actual domain from URL if needed
                if '://' in domain:
                    actual_domain = urlparse(domain).netloc.split(':')[0]
                else:
                    actual_domain = domain.split(':')[0]

                # Load cookies into session for this specific domain
                for name, value in cookies_dict.items():
                    d.session.cookies.set(name, value, domain=actual_domain)

                return True
        except Exception as e:
            d.logger.debug(f"Failed to load cached cookies for {domain}: {e}")
    return False

def _save_cookies_to_cache(d, cookies_dict, domain='annas-archive.org'):
    """Save cookies to domain-specific cache file.

    Args:
        d: Downloader instance
        cookies_dict: Dictionary of cookie name-value pairs
        domain: Domain or URL these cookies are for (default: annas-archive.org)
    """
    try:
        cookie_filename = _get_cookie_filename(domain)
        cookie_file = COOKIE_CACHE_DIR / cookie_filename

        COOKIE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with open(cookie_file, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'cookies': cookies_dict
            }, f, indent=2)

        d.logger.info(f"Cached {len(cookies_dict)} cookies for {domain} -> {cookie_filename}")
    except Exception as e:
        d.logger.debug(f"Failed to cache cookies for {domain}: {e}")

def _prewarm_cookies(d):
    """Pre-warm cookies using FlareSolverr if enabled.

    Uses a slow_download URL to ensure we get all DDG cookies.
    """
    if not d.flaresolverr_url:
        return False

    d.logger.info("Pre-warming cookies with FlareSolverr...")

    # Use a slow_download URL to trigger DDG challenge and get all cookies
    # This ensures we get __ddg* cookies needed for slow_download access
    from stacks.constants import KNOWN_MD5
    test_url = f"https://annas-archive.org/slow_download/{KNOWN_MD5}/0/0"

    success, cookies, _ = d.solve_with_flaresolverr(test_url)

    if success and cookies:
        _save_cookies_to_cache(d, cookies)
        d.logger.info("Cookies pre-warmed and cached")
        return True

    d.logger.warning("Failed to pre-warm cookies")
    return False
