"""add reviewed flag to dev_feedback (for feedback triage automation)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-03

Добавлено для регулярной сверки обратной связи с проектным "кредо":
без этого поля каждый цикл разбора приходилось бы просматривать весь
накопленный фидбэк заново, включая уже обработанные сообщения.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dev_feedback",
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("dev_feedback", "reviewed")
