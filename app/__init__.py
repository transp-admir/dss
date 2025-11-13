from flask import Flask, current_app, g
from flask_migrate import Migrate
from flask_cors import CORS
from markupsafe import Markup
import os
import re
from .extensions import db
from config import config

def nl2br(value):
    return Markup(value.replace('\n', '<br>\n'))

def youtube_id(url):
    regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"
    match = re.search(regex, url)
    return match.group(1) if match else url

migrate = Migrate()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])
    
    # Inicializa as configurações específicas do app (como a criação da pasta instance)
    config[config_name].init_app(app)

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['youtube_id'] = youtube_id

    with app.app_context():
        from . import routes, models
        app.register_blueprint(routes.admin_bp)
        app.register_blueprint(routes.main_bp)

        @app.before_request
        def load_webhook_urls():
            g.webhook_nova = current_app.config.get('MAINTENANCE_WEBHOOK_URL_NOVA')
            g.webhook_atualizar = current_app.config.get('MAINTENANCE_WEBHOOK_URL_ATUALIZAR')

    return app
