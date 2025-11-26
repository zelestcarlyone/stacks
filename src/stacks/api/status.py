import logging
from flask import jsonify, current_app
from stacks.utils.logutils import LOG_BUFFER

from . import api_bp
from stacks.security.auth import require_auth

logger = logging.getLogger("api")


@api_bp.get("/api/health")
def health():
    logger.debug("Health endpoint checked")
    return {"status": "ok"}


@api_bp.get("/api/version")
def api_version():
    """Get current version and tampermonkey script version"""
    from stacks.constants import VERSION, TAMPER_VERSION

    return jsonify({
        "version": VERSION,
        "tamper_version": TAMPER_VERSION
    })


@api_bp.get("/api/logs")
@require_auth
def get_logfile():
    """Return recent console logs"""
    return jsonify({"lines": list(LOG_BUFFER)})

@api_bp.get("/api/status")
@require_auth
def api_status():
    """Get current status"""

    q = current_app.stacks_queue
    w = current_app.stacks_worker

    status = q.get_status()

    w.refresh_fast_download_info_if_stale()
    status["fast_download"] = w.get_fast_download_info()

    return jsonify(status)
