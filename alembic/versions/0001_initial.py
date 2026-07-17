"""create initial tables

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regions_normatives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("region_id", sa.String(20), nullable=False, index=True),
        sa.Column("region_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("subcategory", sa.String(50), nullable=False, index=True),
        sa.Column("benefit_name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("legal_basis", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("is_federal", sa.Boolean, default=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, default=True),
        sa.Column("success_rate", sa.Float, default=0.0),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_hash", sa.String(64), nullable=False, index=True),
        sa.Column("region_id", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subcategory", sa.String(50), nullable=False),
        sa.Column("template_version", sa.String(20), nullable=True),
        sa.Column("edit_pct", sa.Float, default=0.0),
        sa.Column("consent_given", sa.Boolean, default=False),
        sa.Column("id_level", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "responses_library",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("original_request_hash", sa.String(64), nullable=False),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("region_id", sa.String(20), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("subcategory", sa.String(50), nullable=False),
        sa.Column("organ", sa.String(200), nullable=True),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("system_label", sa.String(50), nullable=False),
        sa.Column("user_label", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "classification_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("classification_result", sa.String(50), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, default=0.0),
        sa.Column("edit_pct", sa.Float, default=0.0),
        sa.Column("used_llm", sa.Boolean, default=False),
        sa.Column("markers_found", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # Seed: федеральные льготы (стартовый набор)
    now = "2026-04-28 00:00:00"
    op.execute(f"""
    INSERT INTO regions_normatives
      (region_id, region_name, category, subcategory, benefit_name, description, legal_basis, is_federal, updated_at)
    VALUES
      ('federal','Федеральный','family','large_family','Материнский капитал','При рождении первого ребёнка — 630 400 ₽, второго — дополнительно 202 600 ₽','ФЗ № 256-ФЗ от 29.12.2006',true,'{now}'),
      ('federal','Федеральный','family','large_family','Ежемесячное пособие на детей','Пособие через СФР при доходе ниже прожиточного минимума','ФЗ № 81-ФЗ от 19.05.1995',true,'{now}'),
      ('federal','Федеральный','family','single_parent','Повышенное пособие одинокому родителю','Увеличенный размер ежемесячного пособия','ФЗ № 81-ФЗ от 19.05.1995, ст. 17',true,'{now}'),
      ('federal','Федеральный','family','disabled_child','ЕДВ на ребёнка-инвалида','Ежемесячная денежная выплата через СФР','ФЗ № 178-ФЗ от 17.07.1999, ст. 6.1',true,'{now}'),
      ('federal','Федеральный','employment','unemployed','Пособие по безработице','Мин. 1 500 ₽, макс. 12 792 ₽/мес при регистрации в ЦЗН','Закон РФ № 1032-1 от 19.04.1991, ст. 30-34',true,'{now}'),
      ('federal','Федеральный','employment','unemployed','Бесплатное переобучение','Профессиональная переподготовка по направлению ЦЗН','Закон РФ № 1032-1, ст. 23',true,'{now}'),
      ('federal','Федеральный','health','disability','ЕДВ (ежемесячная денежная выплата)','Размер зависит от группы инвалидности, выплачивается СФР','ФЗ № 178-ФЗ от 17.07.1999, ст. 6.1',true,'{now}'),
      ('federal','Федеральный','health','disability','Набор социальных услуг (НСУ)','Лекарства, санаторно-курортное лечение, проезд','ФЗ № 178-ФЗ, ст. 6.2',true,'{now}'),
      ('federal','Федеральный','housing','mortgage','Имущественный вычет при покупке жилья','Возврат НДФЛ до 260 000 ₽','НК РФ, ст. 220, п. 3',true,'{now}'),
      ('federal','Федеральный','housing','mortgage','Вычет по ипотечным процентам','Возврат НДФЛ до 390 000 ₽','НК РФ, ст. 220, п. 4',true,'{now}'),
      ('federal','Федеральный','housing','purchased','Имущественный вычет','Возврат НДФЛ при покупке жилья до 260 000 ₽. Подайте 3-НДФЛ.','НК РФ, ст. 220',true,'{now}'),
      ('federal','Федеральный','pension','pensioner','Льгота по налогу на имущество','Пенсионеры освобождены от налога на один объект каждого вида','НК РФ, ст. 407',true,'{now}'),
      ('federal','Федеральный','pension','pensioner','Социальная доплата к пенсии','Если пенсия ниже прожиточного минимума пенсионера в регионе','ФЗ № 178-ФЗ, ст. 12.1',true,'{now}'),
      ('msk','Москва','family','large_family','Региональный маткапитал (Москва)','Единовременная выплата при рождении 3-го и последующих детей','Закон г. Москвы № 60 от 23.11.2005',false,'{now}'),
      ('msk','Москва','family','large_family','Компенсация ЖКУ многодетным (Москва)','Компенсация расходов на коммунальные услуги','Постановление Правительства Москвы № 199-ПП',false,'{now}'),
      ('msk','Москва','employment','unemployed','Доплата к пособию по безработице (Москва)','Дополнительная региональная выплата сверх федерального','Закон г. Москвы № 90 от 22.12.2004',false,'{now}'),
      ('spb','Санкт-Петербург','family','large_family','Ежемесячная выплата многодетным (СПб)','Ежемесячная денежная выплата семьям с 3 и более детьми','Закон СПб № 431-85 от 22.11.2011',false,'{now}'),
      ('krd','Краснодарский край','family','large_family','Региональное пособие многодетным (Краснодар)','Ежемесячная выплата на третьего и последующих детей','Закон Краснодарского края № 2740-КЗ',false,'{now}')
    """)


def downgrade() -> None:
    op.drop_table("classification_logs")
    op.drop_table("responses_library")
    op.drop_table("user_sessions")
    op.drop_table("templates")
    op.drop_table("regions_normatives")
