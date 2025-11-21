from flask import Flask
from flask_cors import CORS
from stacks.config.config import Config
from stacks.constants import WWW_PATH
from stacks.server.queue import DownloadQueue
from stacks.server.worker import DownloadWorker
from stacks.utils.logutils import setup_logging
from stacks.api import register_api
import logging

def create_app(config_path: str):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=WWW_PATH,
        static_folder=WWW_PATH,
        static_url_path=""
    )
    CORS(app, supports_credentials=True)

    # ---- Load config ----
    config = Config(config_path)

    # ---- Setup logging ---
    setup_logging(config)
    logger = logging.getLogger("stacks.server")
    logger.info("Stacks server initializing...")

    # ---- Set secret key from config ----
    app.secret_key = config.get("api", "session_secret")

    # ---- Initialize queue + worker ----
    queue = DownloadQueue(config)
    worker = DownloadWorker(queue, config)
    worker.start()

    # ---- Attach backend objects to app ----
    app.stacks_config = config
    app.stacks_queue = queue
    app.stacks_worker = worker

    # ---- Register all API routes ----
    register_api(app)
    
    return app
