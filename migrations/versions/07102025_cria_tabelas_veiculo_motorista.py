"""Cria tabelas veiculo_indisponibilidade e motorista_isencao

Revision ID: manual_veiculo_motorista
Revises: a5e3f66e28cd
Create Date: 2025-10-07 12:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = 'manual_veiculo_motorista'
down_revision = 'a5e3f66e28cd'
branch_labels = None
depends_on = None

def upgrade():
    # Criação da tabela veiculo_indisponibilidade
    op.create_table(
        'veiculo_indisponibilidade',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('data_inicio', sa.Date, nullable=False),
        sa.Column('data_fim', sa.Date, nullable=True),
        sa.Column('motivo', sa.Text, nullable=False),
        sa.Column('veiculo_id', sa.Integer, sa.ForeignKey('veiculo.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer, sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('data_criacao', sa.DateTime, server_default=func.now()),
    )

    # Criação da tabela motorista_isencao
    op.create_table(
        'motorista_isencao',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('data', sa.Date, nullable=False),
        sa.Column('motivo', sa.String(255), nullable=False),
        sa.Column('tipo_checklist', sa.String(50), nullable=False),
        sa.Column('motorista_id', sa.Integer, sa.ForeignKey('motorista.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer, sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('data_criacao', sa.DateTime, server_default=func.now()),
        sa.UniqueConstraint('data', 'motorista_id', 'tipo_checklist', name='_data_motorista_tipo_uc')
    )

def downgrade():
    op.drop_table('motorista_isencao')
    op.drop_table('veiculo_indisponibilidade')
