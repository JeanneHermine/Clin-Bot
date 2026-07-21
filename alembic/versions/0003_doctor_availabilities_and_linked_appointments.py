"""doctor availabilities and linked appointments

Revision ID: 0003_doctor_appts
Revises: 0002_add_otp_challenges
Create Date: 2026-05-26 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_doctor_appts"
down_revision = "0002_add_otp_challenges"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doctor_availabilities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("doctor_name", sa.String(length=200), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=True),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("block_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_doctor_availabilities_id"), "doctor_availabilities", ["id"], unique=False)
    op.create_index(op.f("ix_doctor_availabilities_doctor_name"), "doctor_availabilities", ["doctor_name"], unique=False)
    op.create_index(op.f("ix_doctor_availabilities_specialty"), "doctor_availabilities", ["specialty"], unique=False)
    op.create_index(op.f("ix_doctor_availabilities_start_time"), "doctor_availabilities", ["start_time"], unique=False)

    op.add_column("appointments", sa.Column("availability_id", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("motif", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_appointments_availability_id", "appointments", ["availability_id"])
    op.create_foreign_key(
        "fk_appointments_availability_id",
        "appointments",
        "doctor_availabilities",
        ["availability_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_appointments_availability_id", "appointments", type_="foreignkey")
    op.drop_constraint("uq_appointments_availability_id", "appointments", type_="unique")
    op.drop_column("appointments", "motif")
    op.drop_column("appointments", "availability_id")

    op.drop_index(op.f("ix_doctor_availabilities_start_time"), table_name="doctor_availabilities")
    op.drop_index(op.f("ix_doctor_availabilities_specialty"), table_name="doctor_availabilities")
    op.drop_index(op.f("ix_doctor_availabilities_doctor_name"), table_name="doctor_availabilities")
    op.drop_index(op.f("ix_doctor_availabilities_id"), table_name="doctor_availabilities")
    op.drop_table("doctor_availabilities")
