"""add message_logs table

Revision ID: 0004_add_message_logs
Revises: 0003_doctor_appts
Create Date: 2026-05-26 02:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_message_logs"
down_revision = "0003_doctor_appts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("to_number", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_urls", sa.Text(), nullable=True),
        sa.Column("via", sa.String(length=32), nullable=True),
        sa.Column("external_sid", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_message_logs_id"), "message_logs", ["id"], unique=False)
    op.create_index(op.f("ix_message_logs_to_number"), "message_logs", ["to_number"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_message_logs_to_number"), table_name="message_logs")
    op.drop_index(op.f("ix_message_logs_id"), table_name="message_logs")
    op.drop_table("message_logs")
