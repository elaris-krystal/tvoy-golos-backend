"""drop unused user_sessions table (dead code cleanup)

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-02

При структурном аудите обнаружено: эндпоинт POST /session и таблица
user_sessions существовали в бэкенде и были покрыты тестом, но фронтенд
НИКОГДА их не вызывал — функция logSession() в src/lib/api.ts была
экспортирована, но нигде не импортировалась. Таблица в проде всегда пустая.

Дополнительная причина удалить, а не просто оставить: эндпоинт был
единственным из всех POST-эндпоинтов без rate limiting (пропущен при
добавлении лимитов в миграции безопасности) — неограниченная,
неаутентифицированная точка роста базы данных без всякой пользы для
продукта. Проще и честнее убрать, чем держать мёртвую, потенциально
уязвимую поверхность «на всякий случай».
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_sessions")


def downgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_hash", sa.String(64), nullable=False, index=True),
        sa.Column("region_id", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subcategory", sa.String(50), nullable=False),
        sa.Column("template_version", sa.String(20), nullable=True),
        sa.Column("edit_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
