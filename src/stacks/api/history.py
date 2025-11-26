import logging

from flask import (
    current_app,
    jsonify,
    request,
)

from . import api_bp
from stacks.security.auth import (
    require_auth,
)

logger = logging.getLogger("api")

@api_bp.route('/api/history/clear', methods=['POST'])
@require_auth
def api_history_clear():
    """Clear entire history"""
    q = current_app.stacks_queue
    count = q.clear_history()
    return jsonify({
        'success': True,
        'message': f'Cleared {count} item(s) from history'
    })


@api_bp.route('/api/history/retry', methods=['POST'])
@require_auth
def api_history_retry():
    """Retry a failed download"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400

    q = current_app.stacks_queue
    success, message = q.retry_failed(md5)
    
    return jsonify({
        'success': success,
        'message': message
    })