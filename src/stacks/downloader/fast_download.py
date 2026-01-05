import time
from stacks.constants import KNOWN_MD5
from stacks.utils.domainutils import try_domains_until_success

def _try_fast_download_single_domain(d, md5, domain):
    """Attempt fast download via membership API using a specific domain."""
    if not d.fast_download_enabled or not d.fast_download_key:
        return False, "Fast download not configured"

    if d.fast_download_info.get('downloads_left') is not None:
        if d.fast_download_info['downloads_left'] <= 0:
            return False, "No fast downloads remaining"

    d.logger.debug(f"Attempting fast download from {domain}...")

    api_url = f'https://{domain}/dyn/api/fast_download.json'

    params = {
        'md5': md5,
        'key': d.fast_download_key,
        'path_index': d.fast_download_config.get('path_index', 0),
        'domain_index': d.fast_download_config.get('domain_index', 0)
    }

    response = d.session.get(api_url, params=params, timeout=10)
    data = response.json()

    if 'download_url' in data and data['download_url']:
        if 'account_fast_download_info' in data:
            info = data['account_fast_download_info']
            d.fast_download_info.update({
                'available': True,
                'downloads_left': info.get('downloads_left'),
                'downloads_per_day': info.get('downloads_per_day'),
                'last_refresh': time.time()
            })
            d.logger.info(f"Fast downloads: {info.get('downloads_left')}/{info.get('downloads_per_day')} remaining")

        return True, data['download_url']

    error_message = data.get('error', 'Unknown error')
    raise Exception(f"Fast download error: {error_message}")


def try_fast_download(d, md5):
    """
    Attempt fast download via membership API with automatic domain rotation.
    """
    if not d.fast_download_enabled or not d.fast_download_key:
        return False, "Fast download not configured"

    if d.fast_download_info.get('downloads_left') is not None:
        if d.fast_download_info['downloads_left'] <= 0:
            return False, "No fast downloads remaining"

    d.logger.info("Attempting fast download...")

    try:
        return try_domains_until_success(_try_fast_download_single_domain, d, md5)
    except Exception as e:
        d.logger.error(f"Fast download failed on all domains: {e}")
        return False, str(e)
    
def get_fast_download_info(d):
    """Get current fast download status."""
    return d.fast_download_info.copy()

def _refresh_fast_download_info_single_domain(d, domain):
    """Refresh fast download info from API using a specific domain."""
    d.logger.debug(f"Refreshing fast download info from {domain}...")

    api_url = f'https://{domain}/dyn/api/fast_download.json'

    params = {
        'md5': KNOWN_MD5,
        'key': d.fast_download_key,
        'path_index': 0,
        'domain_index': 0
    }

    response = d.session.get(api_url, params=params, timeout=10)
    data = response.json()

    if 'account_fast_download_info' in data:
        info = data['account_fast_download_info']
        d.fast_download_info.update({
            'available': True,
            'downloads_left': info.get('downloads_left'),
            'downloads_per_day': info.get('downloads_per_day'),
            'last_refresh': time.time()
        })
        return True

    raise Exception("No account info in API response")


def refresh_fast_download_info(d, force=False):
    """
    Refresh fast download info from API with automatic domain rotation.

    Respects 1-hour cooldown unless force=True.
    """
    if not d.fast_download_enabled or not d.fast_download_key:
        return False

    if not force:
        time_since_refresh = time.time() - d.fast_download_info.get('last_refresh', 0)
        if time_since_refresh < d.fast_download_refresh_cooldown:
            return True

    try:
        return try_domains_until_success(_refresh_fast_download_info_single_domain, d)
    except Exception as e:
        d.logger.error(f"Failed to refresh fast download info from all domains: {e}")
        return False