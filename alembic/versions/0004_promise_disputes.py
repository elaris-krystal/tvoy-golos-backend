"""add dispute mechanism to promises (defamation risk mitigation)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promises", sa.Column("dispute_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("promises", sa.Column("hidden", sa.Boolean, nullable=False, server_default="false"))

    op.create_table(
        "promise_disputes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("promise_id", sa.Integer, nullable=False),
        sa.Column("disputer_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_pd_promise_disputer", "promise_disputes", ["promise_id", "disputer_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_pd_promise_disputer", "promise_disputes")
    op.drop_table("promise_disputes")
    op.drop_column("promises", "hidden")
    op.drop_column("promises", "dispute_count")
