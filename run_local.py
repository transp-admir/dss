import os
from app import create_app

# Força ambiente de desenvolvimento
config_name = 'development'
app = create_app(config_name)

if __name__ == '__main__':
    # Roda com servidor interno do Flask, acessível na rede local
    app.run(host='0.0.0.0', port=5001, debug=True)
