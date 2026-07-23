from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.core.database import get_db
from app.models.models import RegionNormative, UserSession, ResponseLibrary, ClassificationLog, DevFeedback
from app.schemas.schemas import (
    BenefitOut, GenerateTemplateIn, GenerateTemplateOut,
    ClassifyIn, ClassifyOut, SessionIn, FeedbackIn, DevFeedbackIn,
)
from app.services.generator import generate_template
from app.services.classifier import classify_response, hash_text

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok, "version": "1.0", "llm_provider": "see .env"}


@router.get("/benefits", response_model=list[BenefitOut])
async def get_benefits(
    region_id: str = Query(..., min_length=1, max_length=20),
    category: str = Query(..., min_length=1, max_length=50),
    subcategory: str = Query(..., min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    regional = (await db.execute(
        select(RegionNormative).where(
            RegionNormative.region_id == region_id,
            RegionNormative.category == category,
            RegionNormative.subcategory == subcategory,
        )
    )).scalars().all()

    federal = (await db.execute(
        select(RegionNormative).where(
            RegionNormative.is_federal == True,
            RegionNormative.category == category,
            RegionNormative.subcategory == subcategory,
        )
    )).scalars().all()

    # Региональные + федеральные без дублей
    seen_ids = {r.id for r in regional}
    combined = list(regional) + [r for r in federal if r.id not in seen_ids]

    return [
        BenefitOut(
            id=r.id,
            benefit_name=r.benefit_name,
            description=r.description,
            legal_basis=r.legal_basis,
            source_url=r.source_url,
            is_federal=r.is_federal,
        )
        for r in combined
    ]


@router.post("/generate-template", response_model=GenerateTemplateOut)
async def api_generate_template(data: GenerateTemplateIn):
    try:
        return await generate_template(data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ошибка генерации шаблона: {str(e)}")


@router.post("/classify-response", response_model=ClassifyOut)
async def api_classify_response(
    data: ClassifyIn,
    db: AsyncSession = Depends(get_db),
):
    if not data.original_request.strip():
        raise HTTPException(status_code=422, detail="original_request не может быть пустым")
    if not data.official_response.strip():
        raise HTTPException(status_code=422, detail="official_response не может быть пустым")

    try:
        result = await classify_response(data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ошибка классификации: {str(e)}")

    # Сохраняем лог
    db.add(ClassificationLog(
        prompt_version="1.1",
        classification_result=result.classification,
        score=result.score,
        confidence=result.score / 3.0,
        used_llm=result.used_llm,
        markers_found=result.markers,
        created_at=datetime.utcnow(),
    ))

    # Сохраняем ответ в библиотеку (обезличенно)
    if data.region_id and data.category:
        db.add(ResponseLibrary(
            original_request_hash=hash_text(data.original_request),
            response_text=data.official_response,
            region_id=data.region_id,
            category=data.category,
            subcategory=data.subcategory or "unknown",
            classification=result.classification,
            system_label=result.classification,
            created_at=datetime.utcnow(),
        ))

    await db.commit()
    return result


@router.post("/session", status_code=204)
async def log_session(
    data: SessionIn,
    db: AsyncSession = Depends(get_db),
):
    """Логирует анонимную сессию. Никаких персональных данных."""
    db.add(UserSession(
        device_hash=data.device_hash,
        region_id=data.region_id,
        category=data.category,
        subcategory=data.subcategory,
        template_version=data.template_version,
        edit_pct=data.edit_pct,
        consent_given=data.consent_given,
        id_level=0,
        created_at=datetime.utcnow(),
    ))
    await db.commit()


@router.post("/feedback", status_code=204)
async def submit_feedback(
    data: FeedbackIn,
    db: AsyncSession = Depends(get_db),
):
    request_hash = hash_text(data.original_request)
    existing = (await db.execute(
        select(ResponseLibrary).where(
            ResponseLibrary.original_request_hash == request_hash
        )
    )).scalar_one_or_none()

    if existing:
        existing.user_label = data.user_label
    else:
        db.add(ResponseLibrary(
            original_request_hash=request_hash,
            response_text=data.response_text,
            region_id=data.region_id,
            category=data.category,
            subcategory=data.subcategory,
            organ=data.organ,
            classification=data.system_label,
            system_label=data.system_label,
            user_label=data.user_label,
            created_at=datetime.utcnow(),
        ))

    await db.commit()


# ── Обратная связь с разработчиками ─────────────────────────────────────────

@router.post("/dev-feedback", status_code=204)
async def submit_dev_feedback(
    data: DevFeedbackIn,
    db: AsyncSession = Depends(get_db),
):
    """
    Анонимное сообщение разработчикам (баг/предложение/другое).
    Никакой привязки к пользователю — ни device_hash, ни IP не сохраняются.
    """
    db.add(DevFeedback(
        category=data.category,
        message=data.message,
        page=data.page,
        created_at=datetime.utcnow(),
    ))
    await db.commit()
