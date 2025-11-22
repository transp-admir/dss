import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Configuração base da qual as outras herdam."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = 'America/Sao_Paulo'

    # Garante que o caminho para o banco de dados seja absoluto
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')

    MAINTENANCE_WEBHOOK_URL_NOVA = None
    MAINTENANCE_WEBHOOK_URL_ATUALIZAR = None

    @staticmethod
    def init_app(app):
        """Cria a pasta de instância se ela não existir."""
        instance_path = os.path.join(basedir, 'instance')
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)


class DevelopmentConfig(Config):
    """Configuração para o ambiente de desenvolvimento."""
    DEBUG = True
    # Webhooks locais para testes
    MAINTENANCE_WEBHOOK_URL_NOVA = 'http://127.0.0.1:5000/ss/api/ss/nova'
    MAINTENANCE_WEBHOOK_URL_ATUALIZAR = 'http://127.0.0.1:5000/ss/webhook/atualizar_status'


class ProductionConfig(Config):
    """Configuração para o ambiente de produção."""
    # Em produção, as URLs devem ser configuradas via variáveis de ambiente
    MAINTENANCE_WEBHOOK_URL_NOVA = os.environ.get('MAINTENANCE_WEBHOOK_URL_NOVA')
    MAINTENANCE_WEBHOOK_URL_ATUALIZAR = os.environ.get('MAINTENANCE_WEBHOOK_URL_ATUALIZAR')


# Dicionário de configuração
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
