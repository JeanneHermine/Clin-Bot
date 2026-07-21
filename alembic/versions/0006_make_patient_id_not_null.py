"""make patient_id not null for appointments

Revision ID: 0006_patient_id_not_null
Revises: 0005_add_booking_request_fields
Create Date: 2026-06-03 09:16:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_patient_id_not_null"
down_revision = "0005_add_booking_request_fields"
branch_labels = None
depends_on = None


def upgrade():
    # Delete appointments with NULL patient_id to avoid constraint violation
    op.execute("DELETE FROM appointments WHERE patient_id IS NULL")
    
    # Change the foreign key constraint
    op.drop_constraint("appointments_patient_id_fkey", "appointments", type_="foreignkey")
    
    # Make patient_id NOT NULL
    op.alter_column(
        "appointments",
        "patient_id",
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True,
    )
    
    # Recreate the foreign key with ondelete='CASCADE'
    op.create_foreign_key(
        "appointments_patient_id_fkey",
        "appointments",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # Revert the changes
    op.drop_constraint("appointments_patient_id_fkey", "appointments", type_="foreignkey")
    
    op.alter_column(
        "appointments",
        "patient_id",
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=False,
    )
    
    op.create_foreign_key(
        "appointments_patient_id_fkey",
        "appointments",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="SET NULL",
    )
