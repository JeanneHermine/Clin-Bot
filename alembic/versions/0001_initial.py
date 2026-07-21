"""initial migration

Revision ID: 0001_initial
Revises: 
Create Date: 2026-05-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('whatsapp_number', sa.String(length=32), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_patients_whatsapp_number'), 'patients', ['whatsapp_number'], unique=False)
    op.create_index(op.f('ix_patients_id'), 'patients', ['id'], unique=False)

    op.create_table(
        'results',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analysis_date', sa.Date(), nullable=True),
        sa.Column('analysis_type', sa.String(length=100), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='en_attente'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_results_id'), 'results', ['id'], unique=False)

    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('doctor_name', sa.String(length=200), nullable=False),
        sa.Column('specialty', sa.String(length=100), nullable=True),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='confirmed'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('whatsapp_number', sa.String(length=32), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False, server_default='menu'),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_chat_sessions_whatsapp_number'), 'chat_sessions', ['whatsapp_number'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_chat_sessions_whatsapp_number'), table_name='chat_sessions')
    op.drop_table('chat_sessions')

    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_table('appointments')

    op.drop_index(op.f('ix_results_id'), table_name='results')
    op.drop_table('results')

    op.drop_index(op.f('ix_patients_whatsapp_number'), table_name='patients')
    op.drop_index(op.f('ix_patients_id'), table_name='patients')
    op.drop_table('patients')
