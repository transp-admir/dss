"""botao para ativar e desativar opcao de conjuntos para o motorista

Revision ID: 280987b406a6
Revises: e6b0ca8b867b
Create Date: 2025-10-08 09:45:04.877455
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '280987b406a6'
down_revision = 'e6b0ca8b867b'
branch_labels = None
depends_on = None

def upgrade():
    # Criação da nova tabela unidade_config
    op.create_table(
        'unidade_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unidade', sa.String(length=100), nullable=False),
        sa.Column('motorista_pode_trocar_veiculo', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unidade')
    )

    # Alteração na tabela extintor_check
    with op.batch_alter_table('extintor_check', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preenchimento_id', sa.Integer(), nullable=False))
        batch_op.drop_constraint('fk_extintor_check_checklist_preenchido_id', type_='foreignkey')  # substitua pelo nome real da FK
        batch_op.create_foreign_key('fk_extintor_check_preenchimento_id', 'checklist_preenchido', ['preenchimento_id'], ['id'])
        batch_op.drop_column('checklist_preenchido_id')

def downgrade():
    # Reversão da tabela extintor_check
    with op.batch_alter_table('extintor_check', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checklist_preenchido_id', sa.INTEGER(), nullable=False))
        batch_op.drop_constraint('fk_extintor_check_preenchimento_id', type_='foreignkey')  # nome da FK criada no upgrade
        batch_op.create_foreign_key('fk_extintor_check_checklist_preenchido_id', 'checklist_preenchido', ['checklist_preenchido_id'], ['id'])
        batch_op.drop_column('preenchimento_id')

    # Remoção da tabela unidade_config
    op.drop_table('unidade_config')
