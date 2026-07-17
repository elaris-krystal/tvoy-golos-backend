"""remove region_name, add indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Убираем избыточный region_name из regions_normatives
    op.drop_column("regions_normatives", "region_name")

    # Составной индекс на regions_normatives
    op.create_index("ix_rn_region_category", "regions_normatives", ["region_id", "category"])

    # Индексы на responses_library
    op.create_index("ix_rl_region_category", "responses_library", ["region_id", "category"])
    op.create_index("ix_rl_created_at", "responses_library", ["created_at"])

    # Индекс на classification_logs
    op.create_index("ix_cl_created_at", "classification_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_cl_created_at", "classification_logs")
    op.drop_index("ix_rl_created_at", "responses_library")
    op.drop_index("ix_rl_region_category", "responses_library")
    op.drop_index("ix_rn_region_category", "regions_normatives")
    op.add_column("regions_normatives", sa.Column("region_name", sa.String(200), nullable=True))
