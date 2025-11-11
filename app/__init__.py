from flask import Flask
from flask_migrate import Migrate
from flask_cors import CORS
from markupsafe import Markup
import os
import re
from .extensions import db
from config import config  # Importa o dicionário de configurações

def nl2br(value):
    """Converte quebras de linha em tags <br> para renderização em HTML."""
    return Markup(value.replace('\n', '<br>\n'))

def youtube_id(url):
    """Extrai o ID do vídeo de uma URL do YouTube."""
    regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"
    match = re.search(regex, url)
    return match.group(1) if match else url

migrate = Migrate()

def create_app(config_name=None):
    """Função que cria e configura a aplicação Flask (Application Factory)."""
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')

    app = Flask(__name__, instance_relative_config=True)
    
    # --- CONFIGURAÇÃO A PARTIR DO OBJETO ---
    app.config.from_object(config[config_name])

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- INICIALIZAÇÃO DE EXTENSÕES ---
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- REGISTRO DE FILTROS JINJA ---
    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['youtube_id'] = youtube_id

    # --- IMPORTAÇÃO E REGISTRO DE BLUEPRINTS ---
    from . import routes, models  # A importação de models é necessária para o Flask-Migrate

    with app.app_context():
        app.register_blueprint(routes.admin_bp)
        app.register_blueprint(routes.main_bp)

    return app
