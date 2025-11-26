import logging

from flask import (
    current_app,
    jsonify,
)

from . import api_bp
from stacks.security.auth import (
    require_session_only,
    generate_api_key,
)

logger = logging.getLogger("api")

@api_bp.route('/api/key/regenerate', methods=['POST'])
@require_session_only
def api_key_regenerate():
    """Regenerate API key"""
    try:
        new_key = generate_api_key()
        config = current_app.stacks_config
        config.set('api', 'key', value=new_key)
        config.save()
        
        logger.info("API key regenerated")
        
        return jsonify({
            'success': True,
            'message': 'New API key generated',
            'api_key': new_key
        })
    except Exception as e:
        logger.error(f"Failed to regenerate API key: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    

@api_bp.route('/api/key')
@require_session_only
def api_key_info():
    """Get API key (session auth only - for web UI)"""
    config = current_app.stacks_config
    return jsonify({'api_key': config.get('api', 'key')})




