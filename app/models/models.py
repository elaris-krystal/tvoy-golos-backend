from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class RegionNormative(Base):
    __tablename__ = "regions_normatives"
    __table_args__ = (
        Index("ix_rn_region_category", "region_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[str] = mapped_column(String(20), nullable=False)
    # region_name убран — избыточно, регион идентифицируется по region_id
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    benefit_name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_federal: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    edit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    id_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResponseLibrary(Base):
    """Обезличенная библиотека ответов. Нет foreign key на user_sessions."""
    __tablename__ = "responses_library"
    __table_args__ = (
        Index("ix_rl_region_category", "region_id", "category"),
        Index("ix_rl_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    region_id: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    organ: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    system_label: Mapped[str] = mapped_column(String(50), nullable=False)
    user_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClassificationLog(Base):
    __tablename__ = "classification_logs"
    __table_args__ = (
        Index("ix_cl_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    classification_result: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    edit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    used_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    markers_found: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DevFeedback(Base):
    """Анонимная обратная связь с разработчиками. Никакой привязки к пользователю."""
    __tablename__ = "dev_feedback"
    __table_args__ = (
        Index("ix_df_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # bug|suggestion|other
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[str] = mapped_column(String(200), nullable=True)  # с какого экрана отправлено
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
