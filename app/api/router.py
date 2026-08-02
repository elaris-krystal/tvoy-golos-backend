from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.config import settings
from app.models.models import RegionNormative, ResponseLibrary, ClassificationLog, DevFeedback
from app.schemas.schemas import (
    BenefitOut, GenerateTemplateIn, GenerateTemplateOut,
    ClassifyIn, ClassifyOut, FeedbackIn, DevFeedbackIn,
    GenerateDocumentIn,
)
from app.services.generator import generate_template
from app.services.classifier import classify_response, hash_text
from app.services.document_filler import generate_document, is_document_supported
from fastapi.responses import Response

router = APIRouter()


def _rate_limit_exempt() -> bool:
    """
    Rate limiting активен только в проде. В dev/CI (в т.ч. stress_test.py,
    который намеренно шлёт 50 параллельных запросов с одного IP) лимиты
    отключены, чтобы не мешать разработке и нагрузочному тестированию.
    """
    return settings.env != "production"


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
@limiter.limit("20/minute", exempt_when=_rate_limit_exempt)
async def api_generate_template(request: Request, data: GenerateTemplateIn):
    try:
        return await generate_template(data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ошибка генерации шаблона: {str(e)}")


@router.get("/document-available")
async def api_document_available(category: str, subcategory: str):
    return {"available": is_document_supported(category, subcategory)}


@router.post("/generate-document")
@limiter.limit("10/minute", exempt_when=_rate_limit_exempt)
async def api_generate_document(request: Request, data: GenerateDocumentIn):
    if not is_document_supported(data.category, data.subcategory):
        raise HTTPException(
            status_code=404,
            detail="Официальный бланк для этой категории пока не реализован",
        )
    try:
        content = generate_document(data.category, data.subcategory, data.region_name, data.reason_text)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ошибка генерации документа: {str(e)}")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=zayavlenie_pension_pereraschet.docx"},
    )


@router.post("/classify-response", response_model=ClassifyOut)
@limiter.limit("20/minute", exempt_when=_rate_limit_exempt)
async def api_classify_response(
    request: Request,
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

    # Сохраняем классификацию (без сырого текста ответа — см. ResponseLibrary docstring)
    if data.region_id and data.category:
        db.add(ResponseLibrary(
            original_request_hash=hash_text(data.original_request),
            region_id=data.region_id,
            category=data.category,
            subcategory=data.subcategory or "unknown",
            classification=result.classification,
            system_label=result.classification,
            created_at=datetime.utcnow(),
        ))

    await db.commit()
    return result


@router.post("/feedback", status_code=204)
@limiter.limit("15/minute", exempt_when=_rate_limit_exempt)
async def submit_feedback(
    request: Request,
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
@limiter.limit("10/minute", exempt_when=_rate_limit_exempt)
async def submit_dev_feedback(
    request: Request,
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
