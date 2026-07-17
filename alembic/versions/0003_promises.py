"""add promises and promise_votes tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promises",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("region_id", sa.String(20), nullable=False),
        sa.Column("official_name", sa.String(200), nullable=False),
        sa.Column("official_role", sa.String(200), nullable=False),
        sa.Column("promise_text", sa.Text, nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("promise_date", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="checking"),
        sa.Column("votes_fulfilled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("votes_broken", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitter_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_pr_region_status", "promises", ["region_id", "status"])
    op.create_index("ix_pr_created_at", "promises", ["created_at"])

    op.create_table(
        "promise_votes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("promise_id", sa.Integer, nullable=False),
        sa.Column("voter_hash", sa.String(64), nullable=False),
        sa.Column("vote", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_pv_promise_voter", "promise_votes", ["promise_id", "voter_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_pv_promise_voter", "promise_votes")
    op.drop_table("promise_votes")
    op.drop_index("ix_pr_created_at", "promises")
    op.drop_index("ix_pr_region_status", "promises")
    op.drop_table("promises")
