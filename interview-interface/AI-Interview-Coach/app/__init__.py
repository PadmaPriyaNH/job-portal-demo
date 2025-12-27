import os
import logging
from flask import Flask


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
    )

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

    # Logging
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    from .routes import bp
    app.register_blueprint(bp)

    return app
