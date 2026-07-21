"""add otp challenges

Revision ID: 0002_add_otp_challenges
Revises: 0001_initial
Create Date: 2026-05-26 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_otp_challenges"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_number", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False, server_default="result_access"),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_otp_challenges_id"), "otp_challenges", ["id"], unique=False)
    op.create_index(op.f("ix_otp_challenges_patient_id"), "otp_challenges", ["patient_id"], unique=False)
    op.create_index(op.f("ix_otp_challenges_whatsapp_number"), "otp_challenges", ["whatsapp_number"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_otp_challenges_whatsapp_number"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_patient_id"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_id"), table_name="otp_challenges")
    op.drop_table("otp_challenges")
