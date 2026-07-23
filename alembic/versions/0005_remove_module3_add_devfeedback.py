"""remove module 3 (promises) tables, add dev_feedback

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19

Модуль 3 (трекер обещаний) отключён по решению о минимизации рисков на
старте: краудсорсинг непроверенных утверждений о named-людях остаётся
структурным риском даже с предохранителями от клеветы (accuracy_confirmed
+ dispute mechanism из 0004). Решено вернуться к этой функции позже, вместе
с "Пульс Региона", с более продуманной архитектурой верификации.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("promise_votes")
    op.drop_table("promise_disputes")
    op.drop_table("promises")

    op.create_table(
        "dev_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("page", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_df_created_at", "dev_feedback", ["created_at"])


def downgrade() -> None:
    """
    ВАЖНО: downgrade НЕ восстанавливает данные Модуля 3 — только структуру
    таблиц. Если модуль отключался в проде, данные в promises/promise_votes/
    promise_disputes к этому моменту уже безвозвратно удалены upgrade()-ом.
    """
    op.drop_index("ix_df_created_at", "dev_feedback")
    op.drop_table("dev_feedback")

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
        sa.Column("dispute_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("hidden", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("submitter_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_pr_region_status", "promises", ["region_id", "status"])
    op.create_index("ix_pr_created_at", "promises", ["created_at"])

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
