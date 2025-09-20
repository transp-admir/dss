# Importa a função 'create_app' do nosso pacote 'app'
from app import create_app

# Cria a instância da aplicação Flask
app = create_app()

# Bloco de execução principal
if __name__ == '__main__':
    # Inicia o servidor de desenvolvimento do Flask
    # host='0.0.0.0' torna o servidor visível na sua rede local
    # port=8080 define a porta
    # debug=True ativa o modo de depuração (auto-reload e mensagens de erro detalhadas)
    app.run(host='0.0.0.0', port=8080, debug=True)
