import time
from stacks.constants import KNOWN_MD5

def try_fast_download(d, md5):
    """Attempt fast download via membership API."""
    if not d.fast_download_enabled or not d.fast_download_key:
        return False, "Fast download not configured"
    
    if d.fast_download_info.get('downloads_left') is not None:
        if d.fast_download_info['downloads_left'] <= 0:
            return False, "No fast downloads remaining"
    
    d.logger.info("Attempting fast download...")
    
    try:
        params = {
            'md5': md5,
            'key': d.fast_download_key,
            'path_index': d.fast_download_config.get('path_index', 0),
            'domain_index': d.fast_download_config.get('domain_index', 0)
        }
        
        response = d.session.get(d.fast_download_api_url, params=params, timeout=10)
        data = response.json()
        
        if 'download_url' in data and data['download_url']:
            if 'account_fast_download_info' in data:
                info = data['account_fast_download_info']
                d.fast_download_info.update({
                    'available': True,
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day'),
                    'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                    'last_refresh': time.time()
                })
                d.logger.info(f"Fast downloads: {info.get('downloads_left')}/{info.get('downloads_per_day')} remaining")
            
            return True, data['download_url']
        
        error_message = data.get('error', 'Unknown error')
        return False, error_message
        
    except Exception as e:
        d.logger.error(f"Fast download API error: {e}")
        return False, f"API error: {e}"
    
def get_fast_download_info(d):
    """Get current fast download status."""
    return d.fast_download_info.copy()

def refresh_fast_download_info(d, force=False):
    """Refresh fast download info from API (respects 1-hour cooldown)."""
    if not d.fast_download_enabled or not d.fast_download_key:
        return False
    
    if not force:
        time_since_refresh = time.time() - d.fast_download_info.get('last_refresh', 0)
        if time_since_refresh < d.fast_download_refresh_cooldown:
            return True
    
    try:
        params = {
            'md5': KNOWN_MD5,
            'key': d.fast_download_key,
            'path_index': 0,
            'domain_index': 0
        }
        
        response = d.session.get(d.fast_download_api_url, params=params, timeout=10)
        data = response.json()
        
        if 'account_fast_download_info' in data:
            info = data['account_fast_download_info']
            d.fast_download_info.update({
                'available': True,
                'downloads_left': info.get('downloads_left'),
                'downloads_per_day': info.get('downloads_per_day'),
                'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                'last_refresh': time.time()
            })
            return True
        
        return False
        
    except Exception as e:
        d.logger.error(f"Failed to refresh fast download info: {e}")
        return False