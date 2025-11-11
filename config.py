import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URI') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'app-dev.db')

class ProductionConfig(Config):
    # A configuração de produção agora aponta para o banco de dados SQLite principal.
    SQLALCHEMY_DATABASE_URI = os.environ.get('PROD_DATABASE_URI') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
