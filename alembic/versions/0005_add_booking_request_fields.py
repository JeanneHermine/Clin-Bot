"""add booking request fields to appointments

Revision ID: 0005_add_booking_request_fields
Revises: 0004_add_message_logs
Create Date: 2026-06-02 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_booking_request_fields"
down_revision = "0004_add_message_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("appointments", sa.Column("requester_first_name", sa.String(length=100), nullable=True))
    op.add_column("appointments", sa.Column("requester_last_name", sa.String(length=100), nullable=True))
    op.add_column("appointments", sa.Column("requester_age", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("contact_phone_number", sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column("appointments", "contact_phone_number")
    op.drop_column("appointments", "requester_age")
    op.drop_column("appointments", "requester_last_name")
    op.drop_column("appointments", "requester_first_name")