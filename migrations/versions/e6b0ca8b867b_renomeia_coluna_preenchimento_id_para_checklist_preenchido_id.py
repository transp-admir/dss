"""Renomeia coluna preenchimento_id para checklist_preenchido_id

Revision ID: e6b0ca8b867b
Revises: manual_veiculo_motorista
Create Date: 2025-10-07 13:30:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e6b0ca8b867b'
down_revision = 'manual_veiculo_motorista'
branch_labels = None
depends_on = None

def upgrade():
    # SQLite não suporta ALTER COLUMN diretamente, usamos batch_op
    with op.batch_alter_table('checklist_resposta', schema=None) as batch_op:
        batch_op.alter_column('preenchimento_id', new_column_name='checklist_preenchido_id')

def downgrade():
    with op.batch_alter_table('checklist_resposta', schema=None) as batch_op:
        batch_op.alter_column('checklist_preenchido_id', new_column_name='preenchimento_id')
