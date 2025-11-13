import os
from app import create_app

# Força ambiente de desenvolvimento
config_name = 'development'
app = create_app(config_name)

if __name__ == '__main__':
    # Roda com servidor interno do Flask
    app.run(host='127.0.0.1', port=5001, debug=True)
