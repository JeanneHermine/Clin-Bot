"""change default status for appointments to pending_validation

Revision ID: 0007_appt_status_default
Revises: 0006_patient_id_not_null
Create Date: 2026-06-03 09:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_appt_status_default"
down_revision = "0006_patient_id_not_null"
branch_labels = None
depends_on = None


def upgrade():
    # Change default value for status column
    op.alter_column(
        "appointments",
        "status",
        existing_type=sa.String(length=32),
        server_default="pending_validation",
        existing_server_default="confirmed",
    )


def downgrade():
    # Revert the default value
    op.alter_column(
        "appointments",
        "status",
        existing_type=sa.String(length=32),
        server_default="confirmed",
        existing_server_default="pending_validation",
    )
