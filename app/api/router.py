from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.core.database import get_db
from app.models.models import RegionNormative, UserSession, ResponseLibrary, ClassificationLog, Promise, PromiseVote
from app.schemas.schemas import (
    BenefitOut, GenerateTemplateIn, GenerateTemplateOut,
    ClassifyIn, ClassifyOut, SessionIn, FeedbackIn,
    PromiseCreateIn, PromiseOut, PromiseVoteIn, RegionStatsOut,
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


# ── Модуль 3: Трекер обещаний (v0.1, краудсорсинг) ──────────────────────────

@router.post("/promises", response_model=PromiseOut, status_code=201)
async def create_promise(
    data: PromiseCreateIn,
    db: AsyncSession = Depends(get_db),
):
    """Добавление обещания чиновника пользователем. Верификация — краудсорсингом."""
    promise = Promise(
        region_id=data.region_id,
        official_name=data.official_name,
        official_role=data.official_role,
        promise_text=data.promise_text,
        source_url=data.source_url,
        promise_date=data.promise_date,
        status="checking",
        votes_fulfilled=0,
        votes_broken=0,
        submitter_hash=data.device_hash,
        created_at=datetime.utcnow(),
    )
    db.add(promise)
    await db.commit()
    await db.refresh(promise)

    return PromiseOut(
        id=promise.id,
        region_id=promise.region_id,
        official_name=promise.official_name,
        official_role=promise.official_role,
        promise_text=promise.promise_text,
        source_url=promise.source_url,
        promise_date=promise.promise_date,
        status=promise.status,
        votes_fulfilled=promise.votes_fulfilled,
        votes_broken=promise.votes_broken,
        created_at=promise.created_at.isoformat(),
    )


@router.get("/promises", response_model=list[PromiseOut])
async def list_promises(
    region_id: str = Query(..., min_length=1, max_length=20),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Список обещаний по региону, новые сверху."""
    query = select(Promise).where(Promise.region_id == region_id)
    if status_filter:
        query = query.where(Promise.status == status_filter)
    query = query.order_by(Promise.created_at.desc()).limit(limit)

    rows = (await db.execute(query)).scalars().all()

    return [
        PromiseOut(
            id=p.id, region_id=p.region_id, official_name=p.official_name,
            official_role=p.official_role, promise_text=p.promise_text,
            source_url=p.source_url, promise_date=p.promise_date,
            status=p.status, votes_fulfilled=p.votes_fulfilled,
            votes_broken=p.votes_broken, created_at=p.created_at.isoformat(),
        )
        for p in rows
    ]


# Порог голосов для автоматического пересчёта статуса
VOTE_THRESHOLD = 3


@router.post("/promises/{promise_id}/vote", response_model=PromiseOut)
async def vote_promise(
    promise_id: int,
    data: PromiseVoteIn,
    db: AsyncSession = Depends(get_db),
):
    """
    Голос за статус обещания (выполнено/не выполнено).
    Один голос на устройство на обещание — защита от накрутки.

    ВАЖНО (найдено стресс-тестом с 20 параллельными голосами):
    1. Инкремент счётчиков сделан атомарным SQL UPDATE (votes_x = votes_x + 1
       на уровне БД), а не через ORM-паттерн "прочитать в Python -> +1 -> записать".
       Второй вариант теряет обновления под конкурентной нагрузкой (lost update) —
       блокировка FOR UPDATE не решает проблему полностью на SQLite (разная
       модель блокировок от Postgres), поэтому логика инкремента вынесена в SQL.
    2. Защита от дублирующего голоса полагается на UNIQUE-индекс в БД, а не
       только на предварительный SELECT — предварительная проверка сама по себе
       не атомарна (между SELECT и INSERT может проскочить конкурентный запрос).
       IntegrityError от нарушения индекса ловится и превращается в чистый 409,
       а не протекает как 500.
    """
    promise = await db.get(Promise, promise_id)
    if not promise:
        raise HTTPException(status_code=404, detail="Обещание не найдено")

    try:
        db.add(PromiseVote(
            promise_id=promise_id,
            voter_hash=data.voter_hash,
            vote=data.vote,
            created_at=datetime.utcnow(),
        ))
        await db.flush()  # форсируем проверку UNIQUE-индекса сейчас, до дальнейшей логики
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Вы уже голосовали за это обещание")

    # Атомарный инкремент на уровне SQL — единственный надёжный способ
    # избежать lost update под конкурентной нагрузкой без гарантии FOR UPDATE.
    column = Promise.votes_fulfilled if data.vote == "fulfilled" else Promise.votes_broken
    await db.execute(
        update(Promise)
        .where(Promise.id == promise_id)
        .values(**{column.key: column + 1})
    )
    await db.commit()
    await db.refresh(promise)

    # Пересчёт статуса при достижении порога голосов
    total_votes = promise.votes_fulfilled + promise.votes_broken
    if total_votes >= VOTE_THRESHOLD and promise.status == "checking":
        new_status = "fulfilled" if promise.votes_fulfilled > promise.votes_broken else "broken"
        await db.execute(
            update(Promise).where(Promise.id == promise_id).values(status=new_status)
        )
        await db.commit()
        await db.refresh(promise)

    return PromiseOut(
        id=promise.id, region_id=promise.region_id, official_name=promise.official_name,
        official_role=promise.official_role, promise_text=promise.promise_text,
        source_url=promise.source_url, promise_date=promise.promise_date,
        status=promise.status, votes_fulfilled=promise.votes_fulfilled,
        votes_broken=promise.votes_broken, created_at=promise.created_at.isoformat(),
    )


@router.get("/promises/stats", response_model=RegionStatsOut)
async def promise_stats(
    region_id: str = Query(..., min_length=1, max_length=20),
    db: AsyncSession = Depends(get_db),
):
    """Агрегированная статистика по региону — для главного экрана."""
    rows = (await db.execute(
        select(Promise).where(Promise.region_id == region_id)
    )).scalars().all()

    fulfilled = sum(1 for p in rows if p.status == "fulfilled")
    broken = sum(1 for p in rows if p.status == "broken")
    checking = sum(1 for p in rows if p.status == "checking")

    return RegionStatsOut(
        region_id=region_id,
        total_promises=len(rows),
        fulfilled_count=fulfilled,
        broken_count=broken,
        checking_count=checking,
    )
