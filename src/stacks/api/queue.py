import logging

from flask import (
    current_app,
    jsonify,
    request,
)

from . import api_bp
from stacks.utils.md5utils import extract_md5
from stacks.security.auth import (
    require_auth,
)

logger = logging.getLogger("api")

@api_bp.route('/api/queue/remove', methods=['POST'])
@require_auth
def api_queue_remove():
    """Remove item from queue"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400
    
    q = current_app.stacks_queue
    removed = q.remove_from_queue(md5)
    
    return jsonify({
        'success': removed,
        'message': 'Removed from queue' if removed else 'Not found in queue'
    })


@api_bp.route('/api/queue/clear', methods=['POST'])
@require_auth
def api_queue_clear():
    """Clear entire queue"""
    q = current_app.stacks_queue
    count = q.clear_queue()
    return jsonify({
        'success': True,
        'message': f'Cleared {count} item(s) from queue'
    })

@api_bp.route('/api/queue/add', methods=['POST'])
@require_auth
def api_queue_add():
    """Add item to queue"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400
    
    # Validate MD5
    extracted_md5 = extract_md5(md5)
    
    if not extracted_md5:
        return jsonify({'success': False, 'error': 'Invalid MD5 format'}), 400
    
    # Add to queue
    q = current_app.stacks_queue
    success, message = q.add(
        extracted_md5,
        source=data.get('source')
    )
    
    return jsonify({
        'success': success,
        'message': message,
        'md5': extracted_md5
    })
