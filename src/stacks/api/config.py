import logging
import time
from flask import (
    jsonify,
    request,
    current_app,
)
from stacks.constants import FAST_DOWNLOAD_API_URL, KNOWN_MD5
from . import api_bp
from stacks.utils.logutils import setup_logging
from stacks.security.auth import (
    require_auth,
)

logger = logging.getLogger("api")

@api_bp.route('/api/config/test_flaresolverr', methods=['POST'])
@require_auth
def api_config_test_flaresolverr():
    """Test FlareSolverr connection"""
    data = request.json
    test_url = data.get('url', 'http://localhost:8191')
    timeout = data.get('timeout', 10)

    if not test_url:
        return jsonify({
            'success': False,
            'error': 'No URL provided'
        }), 400

    # Normalize URL: add http:// if no scheme is present
    if not test_url.startswith(('http://', 'https://')):
        test_url = f"http://{test_url}"

    try:
        import requests

        # Try to connect to FlareSolverr's health endpoint
        response = requests.get(test_url, timeout=timeout)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'FlareSolverr is online and responding',
                'status_code': response.status_code
            })
        else:
            return jsonify({
                'success': False,
                'error': f'FlareSolverr returned status {response.status_code}'
            }), 400
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': f'Connection timeout after {timeout} seconds'
        }), 408
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Could not connect to FlareSolverr. Is it running?'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 500
    
@api_bp.route('/api/config/test_key', methods=['POST'])
@require_auth
def api_config_test_key():
    """Test fast download key and update cached info"""
    data = request.json
    test_key = data.get('key')
    
    if not test_key:
        return jsonify({
            'success': False,
            'error': 'No key provided'
        }), 400
    
    try:
        import requests
        
        # Use a known valid MD5 for testing
                
        response = requests.get(
            FAST_DOWNLOAD_API_URL,
            params={
                'md5': KNOWN_MD5,
                'key': test_key
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('download_url'):
                info = data.get('account_fast_download_info', {})
                
                # Update the worker's cached info with timestamp
                worker = current_app.stacks_worker
                if worker.downloader.fast_download_key == test_key:
                    worker.downloader.fast_download_info.update({
                        'available': True,
                        'downloads_left': info.get('downloads_left'),
                        'downloads_per_day': info.get('downloads_per_day'),
                        'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                        'last_refresh': time.time()
                    })
                
                return jsonify({
                    'success': True,
                    'message': 'Key is valid',
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day')
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No download URL in response'
                }), 400
        elif response.status_code == 401:
            return jsonify({
                'success': False,
                'error': 'Invalid secret key'
            }), 401
        elif response.status_code == 403:
            return jsonify({
                'success': False,
                'error': 'Not a member'
            }), 403
        else:
            return jsonify({
                'success': False,
                'error': f'API returned status {response.status_code}'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 500
    
@api_bp.route('/api/config', methods=['POST'])
@require_auth
def api_config_update():
    """
    Update configuration using schema validation.
    """
    data = request.json
    logger = logging.getLogger('api')
    config = current_app.stacks_config

    try:
        for section, values in data.items():
            if isinstance(values, dict):
                for key, new_value in values.items():
                    config.set(section, key, value=new_value)

        config.data = config.validate(config.data, config.schema)
        config.ensure_login_credentials()
        config.save()

        worker = current_app.stacks_worker
        worker.update_config()
        setup_logging(config)

        import copy
        cfg = copy.deepcopy(config.get_all())
        if "api" in cfg and "key" in cfg["api"]:
            cfg["api"]["key"] = "***MASKED***"
        if "login" in cfg and "password" in cfg["login"]:
            cfg["login"]["password"] = "***MASKED***"

        return jsonify({
            "success": True,
            "message": "Configuration updated",
            "config": cfg
        })

    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

    
@api_bp.route('/api/config', methods=['GET'])
@require_auth
def api_config_get():
    """Get current configuration"""
    import copy
    config = current_app.stacks_config
    config_data = copy.deepcopy(config.get_all())
    # Mask sensitive data
    if 'api' in config_data and 'key' in config_data['api']:
        config_data['api']['key'] = '***MASKED***'
    if 'login' in config_data and 'password' in config_data['login']:
        config_data['login']['password'] = '***MASKED***'
    return jsonify(config_data)