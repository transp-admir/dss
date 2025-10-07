import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# este é o objeto de configuração do Alembic, que fornece
# acesso aos valores dentro do arquivo .ini em uso.
config = context.config

# Interpreta o arquivo de configuração para o logging do Python.
# Esta linha basicamente configura os loggers.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# --- Configuração para o Alembic "enxergar" a aplicação Flask ---
# A URL do banco de dados é lida diretamente da configuração da aplicação Flask.
config.set_main_option('sqlalchemy.url', current_app.config.get('SQLALCHEMY_DATABASE_URI'))

# Aponta para os metadados dos seus modelos.
# A correção no app/__init__.py garante que os modelos estão disponíveis aqui.
target_metadata = current_app.extensions['migrate'].db.metadata

def run_migrations_offline() -> None:
    """Executa migrações em modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Essencial para que migrações no SQLite funcionem corretamente
        # com alterações de tabela (constraints, etc).
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações em modo 'online'."""
    # Conecta-se ao banco de dados usando o engine do Flask-SQLAlchemy
    connectable = current_app.extensions['migrate'].db.get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # Essencial para que migrações no SQLite funcionem corretamente.
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
