import logging

from flask import (
    current_app,
    jsonify,
    render_template,
    request,
    session,
    redirect,
    url_for,
)

from . import api_bp
from stacks.security.auth import (
    require_login,
    check_rate_limit,
    record_failed_attempt,
    clear_attempts,
    verify_password,
)

logger = logging.getLogger("api")


@api_bp.route("/")
@require_login
def index():
    return render_template("index.html")


@api_bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in?
    if session.get("logged_in"):
        return redirect(url_for("api.index"))

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        ip = request.remote_addr or "?"

        # Rate limit
        allowed, msg = check_rate_limit(ip)
        if not allowed:
            return jsonify({"success": False, "error": msg}), 429

        # Access config at REQUEST time only
        config = current_app.stacks_config
        stored_username = config.get("login", "username")
        stored_password = config.get("login", "password")

        if username == stored_username and verify_password(password, stored_password):
            clear_attempts(ip)
            session["logged_in"] = True
            session.permanent = True
            logger.info(f"Successful login from {ip}")
            return jsonify({"success": True})

        # Wrong password
        record_failed_attempt(ip)
        logger.warning(f"Failed login attempt from {ip}")
        return jsonify({"success": False, "error": "Invalid username or password"}), 401

    # GET login page
    return render_template("login.html")


@api_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("api.login"))
