from app import create_app, db
from app.models import Usuario

# Cria a aplicação para ter o contexto do banco de dados
app = create_app()

# Usa o contexto da aplicação para interagir com o banco
with app.app_context():
    # --- DADOS DO PRIMEIRO USUÁRIO ADMINISTRADOR ---
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "179325"
    ADMIN_CPF = "00000000000" # CPF genérico, pode ser alterado depois

    # 1. Verifica se o usuário 'admin' já existe
    if Usuario.query.filter_by(nome=ADMIN_USERNAME).first():
        print(f"O usuário '{ADMIN_USERNAME}' já existe. Nenhuma ação foi tomada.")
    else:
        # 2. Se não existir, cria o novo usuário com o campo 'role'
        print(f"Criando o usuário administrador padrão: '{ADMIN_USERNAME}'...")
        
        admin_user = Usuario(
            nome=ADMIN_USERNAME,
            cpf=ADMIN_CPF,
            setor="TI",
            unidade="Matriz", # Unidade padrão para o primeiro admin
            role="admin"      # CORRIGIDO: Usa o campo 'role'
        )
        
        # 3. Define a senha (o hash será feito automaticamente pelo setter do modelo)
        admin_user.password = ADMIN_PASSWORD
        
        # 4. Adiciona ao banco de dados e salva
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"Usuário '{ADMIN_USERNAME}' criado com sucesso!")
        print("Você agora pode fazer login no painel administrativo com:")
        print(f"  Usuário: {ADMIN_USERNAME}")
        print(f"  Senha: {ADMIN_PASSWORD}")
