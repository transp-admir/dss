import os
from app import create_app

# O servidor WSGI usará a configuração de produção, a menos que outra seja especificada
config_name = os.getenv('FLASK_CONFIG', 'production')
application = create_app(config_name)
