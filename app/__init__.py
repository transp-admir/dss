from flask import Flask
from dotenv import load_dotenv
import os
import re # Importa o módulo de expressões regulares
from markupsafe import Markup

from .extensions import db

def nl2br(value):
    """Converte quebras de linha em tags <br> para renderização em HTML."""
    return Markup(value.replace('\n', '<br>\n'))

def youtube_id(url):
    """Extrai o ID do vídeo de uma URL do YouTube."""
    regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)"
    match = re.search(regex, url)
    return match.group(1) if match else url

def create_app():
    """Função que cria e configura a aplicação Flask (Application Factory)."""
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)

    # --- CONFIGURAÇÃO ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-padrao-fraca')
    default_db_uri = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', default_db_uri)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- INICIALIZAÇÃO DE EXTENSÕES ---
    db.init_app(app)

    # --- REGISTRO DE FILTROS JINJA ---
    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['youtube_id'] = youtube_id # Novo filtro

    # --- REGISTRO DE BLUEPRINTS E CRIAÇÃO DO BANCO ---
    with app.app_context():
        from . import models
        
        # Importa e registra os blueprints
        from . import routes
        app.register_blueprint(routes.admin_bp) # Blueprint da área administrativa
        app.register_blueprint(routes.main_bp)   # Novo blueprint da área pública

        db.create_all()

    return app
