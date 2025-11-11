import os
from app import create_app

# Carrega a configuração de desenvolvimento por padrão para a execução local
config_name = 'development'
app = create_app(config_name)

# Bloco de execução principal
if __name__ == '__main__':
    # Inicia o servidor de desenvolvimento do Flask
    app.run(host='0.0.0.0', port=8080)
