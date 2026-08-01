"""remove response_text column from responses_library (PII risk fix)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-01

Аудит безопасности выявил: каждый вызов /classify-response и /feedback
сохранял ПОЛНЫЙ сырой текст ответа госоргана в базу навсегда — включая
ФИО и должность подписавшего чиновника и, потенциально, данные самого
пользователя, если письмо адресное. Это обработка персональных данных
третьих лиц по 152-ФЗ без явного правового основания и уведомления.

Для аналитики (паттерны классификации по регионам/категориям) сырой текст
не нужен — достаточно classification/system_label/user_label и хэша
исходного запроса, которые остаются. Колонка удаляется вместе со всеми
уже накопленными данными в проде (см. downgrade — данные не восстанавливаются).
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("responses_library", "response_text")


def downgrade() -> None:
    """
    ВАЖНО: downgrade восстанавливает только колонку, не данные — исходный
    текст ответов был безвозвратно удалён upgrade()-ом по соображениям
    защиты персональных данных.
    """
    op.add_column(
        "responses_library",
        sa.Column("response_text", sa.Text(), nullable=False, server_default=""),
    )
