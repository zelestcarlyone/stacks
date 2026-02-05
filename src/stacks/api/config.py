import logging
import time
from pathlib import Path
from flask import (
    jsonify,
    request,
    current_app,
)
from stacks.constants import KNOWN_MD5, PROJECT_ROOT
from . import api_bp
from stacks.utils.logutils import setup_logging
from stacks.utils.migrationutils import migrate_incomplete_folder
from stacks.utils.domainutils import try_domains_until_success
from stacks.security.auth import (
    require_auth_with_permissions,
    hash_password,
)

logger = logging.getLogger("api")

@api_bp.route('/api/config/test_flaresolverr', methods=['POST'])
@require_auth_with_permissions(allow_downloader=False)
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
    
def _test_key_single_domain(test_key, domain):
    """Test fast download key with a specific domain."""
    import requests

    api_url = f'https://{domain}/dyn/api/fast_download.json'

    response = requests.get(
        api_url,
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
            return {
                'success': True,
                'message': 'Key is valid',
                'downloads_left': info.get('downloads_left'),
                'downloads_per_day': info.get('downloads_per_day'),
                'account_info': info
            }
        else:
            raise Exception('No download URL in response')
    elif response.status_code == 401:
        raise Exception('Invalid secret key')
    elif response.status_code == 403:
        raise Exception('Not a member')
    else:
        raise Exception(f'API returned status {response.status_code}')


@api_bp.route('/api/config/test_key', methods=['POST'])
@require_auth_with_permissions(allow_downloader=False)
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
        # Use domain rotation to test the key
        result = try_domains_until_success(_test_key_single_domain, test_key)

        # Update the worker's cached info with timestamp
        worker = current_app.stacks_worker
        if worker.downloader.fast_download_key == test_key:
            worker.downloader.fast_download_info.update({
                'available': True,
                'downloads_left': result['downloads_left'],
                'downloads_per_day': result['downloads_per_day'],
                'last_refresh': time.time()
            })

        return jsonify({
            'success': True,
            'message': result['message'],
            'downloads_left': result['downloads_left'],
            'downloads_per_day': result['downloads_per_day']
        })

    except Exception as e:
        error_msg = str(e)

        # Return appropriate status codes
        if 'Invalid secret key' in error_msg:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 401
        elif 'Not a member' in error_msg:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
        else:
            return jsonify({
                'success': False,
                'error': f'Connection failed: {error_msg}'
            }), 500
    
@api_bp.route('/api/config', methods=['POST'])
@require_auth_with_permissions(allow_downloader=False)
def api_config_update():
    """
    Update configuration using schema validation.
    """
    data = request.json
    logger = logging.getLogger('api')
    config = current_app.stacks_config
    worker = current_app.stacks_worker

    try:
        # Check if incomplete_folder_path is being changed
        old_incomplete_path = config.get('downloads', 'incomplete_folder_path', default='/download/incomplete')
        new_incomplete_path = None
        if 'downloads' in data and 'incomplete_folder_path' in data['downloads']:
            new_incomplete_path = data['downloads']['incomplete_folder_path']

        # Apply all config changes
        for section, values in data.items():
            if isinstance(values, dict):
                for key, new_value in values.items():
                    # Special handling for password updates
                    if section == 'login' and key == 'new_password':
                        if new_value:  # Only update if new password is provided
                            hashed_password = hash_password(new_value)
                            config.set(section, 'password', value=hashed_password)
                            logger.info("Password updated successfully")
                    else:
                        config.set(section, key, value=new_value)

        # Validate config (this will normalize the path)
        config.data = config.validate(config.data, config.schema)
        config.ensure_login_credentials()

        # Get the validated/normalized new path
        if new_incomplete_path is not None:
            new_incomplete_path = config.get('downloads', 'incomplete_folder_path', default='/download/incomplete')

        # Handle incomplete folder migration if path changed
        migration_occurred = False
        if new_incomplete_path and new_incomplete_path != old_incomplete_path:
            logger.info(f"Incomplete folder path changed from {old_incomplete_path} to {new_incomplete_path}")

            # Stop active downloads and wait for them to finish
            if worker.queue.current_download:
                logger.info("Cancelling active download for migration")
                worker.pause()  # Pause queue to prevent new downloads
                worker.cancel_and_requeue_current()  # Cancel current download

                # Wait for download to actually stop
                if not worker.wait_for_current_download_to_stop(timeout=10):
                    logger.warning("Current download did not stop within timeout")
                    return jsonify({
                        "success": False,
                        "error": "Could not stop current download for migration"
                    }), 500

            # Perform migration
            old_path = PROJECT_ROOT / old_incomplete_path.lstrip('/')
            new_path = PROJECT_ROOT / new_incomplete_path.lstrip('/')

            logger.info(f"Starting migration from {old_path} to {new_path}")
            success, message, stats = migrate_incomplete_folder(old_path, new_path)

            if not success:
                logger.error(f"Migration failed: {message}")
                logger.error(f"Migration stats: {stats}")
                # Don't save config if migration failed
                return jsonify({
                    "success": False,
                    "error": "Failed to change incomplete folder, see the logfile for details"
                }), 500

            logger.info(f"Migration completed: {message}")
            logger.info(f"Migration stats: {stats}")
            migration_occurred = True

        # Save config
        config.save()

        # Recreate downloader with new config (this will use the new path)
        worker.update_config()
        setup_logging(config)

        # Resume worker if we paused it
        if migration_occurred and worker.paused:
            worker.resume()

        import copy
        cfg = copy.deepcopy(config.get_all())
        if "api" in cfg and "key" in cfg["api"]:
            cfg["api"]["key"] = "***MASKED***"
        if "login" in cfg and "password" in cfg["login"]:
            cfg["login"]["password"] = "***MASKED***"

        response_message = "Configuration updated"
        if migration_occurred:
            response_message = f"Configuration updated. {message}"

        return jsonify({
            "success": True,
            "message": response_message,
            "config": cfg
        })

    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to change incomplete folder, see the logfile for details"
        }), 500

    
@api_bp.route('/api/config', methods=['GET'])
@require_auth_with_permissions(allow_downloader=False)
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

@api_bp.route('/api/subdirs', methods=['GET'])
@require_auth_with_permissions(allow_downloader=True)
def api_subdirs_get():
    """Get list of available subdirectories"""
    config = current_app.stacks_config
    subdirs = config.get('downloads', 'subdirectories', default=None)

    # Return empty list if None or not a list
    if not subdirs or not isinstance(subdirs, list):
        subdirs = []

    return jsonify({
        'success': True,
        'subdirectories': subdirs
    })