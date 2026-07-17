"""
Автономный тест-сьют «Твой Голос» backend.
Запуск: venv/bin/pytest test_autonomous.py -v
"""
import os
import sys
import asyncio
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(__file__))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_autonomous.db"
os.environ["LLM_PROVIDER"] = "none"

from httpx import AsyncClient, ASGITransport
from app.core.database import Base, engine
from app.models import models
from app.main import app


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    if os.path.exists("./test_autonomous.db"):
        os.remove("./test_autonomous.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        s.add(models.RegionNormative(
            region_id="msk", category="family", subcategory="large_family",
            benefit_name="Тест", description="Тест", legal_basis="ФЗ",
            is_federal=False,
        ))
        await s.commit()
    yield
    if os.path.exists("./test_autonomous.db"):
        os.remove("./test_autonomous.db")


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Benefits — базовые случаи ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_benefits_found(client):
    r = await client.get("/api/benefits?region_id=msk&category=family&subcategory=large_family")
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_benefits_not_found_empty_list(client):
    """Несуществующая комбинация должна вернуть пустой список, не ошибку."""
    r = await client.get("/api/benefits?region_id=xyz&category=xyz&subcategory=xyz")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_benefits_missing_required_param(client):
    """Без обязательного параметра — 422, не 500."""
    r = await client.get("/api/benefits?region_id=msk&category=family")
    assert r.status_code == 422


# ── Benefits — edge cases (новое, не проверялось раньше) ───────────────────

@pytest.mark.asyncio
async def test_benefits_sql_injection_attempt(client):
    """Попытка SQL-инъекции в параметрах — не должна вызвать ошибку сервера."""
    r = await client.get("/api/benefits?region_id=msk';DROP TABLE regions_normatives;--&category=family&subcategory=large_family")
    assert r.status_code in (200, 422)  # либо обработано корректно, либо отклонено валидацией
    assert r.status_code != 500


@pytest.mark.asyncio
async def test_benefits_very_long_param(client):
    """Параметр длиннее max_length — должен быть отклонён валидацией, не упасть с 500."""
    long_str = "a" * 1000
    r = await client.get(f"/api/benefits?region_id={long_str}&category=family&subcategory=large_family")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_benefits_unicode_emoji(client):
    """Эмодзи и юникод в параметрах не должны ронять сервер."""
    r = await client.get("/api/benefits?region_id=msk😀&category=family&subcategory=large_family")
    assert r.status_code in (200, 422)
    assert r.status_code != 500


# ── Generate template ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_template_basic(client):
    r = await client.post("/api/generate-template", json={
        "region_id": "msk", "region_name": "Москва",
        "category": "family", "subcategory": "large_family",
    })
    assert r.status_code == 200
    assert len(r.json()["text"]) > 20


@pytest.mark.asyncio
async def test_generate_template_labor_all_subcategories(client):
    """Все 4 трудовые подкатегории должны давать разный текст (не default-фоллбэк)."""
    subs = ["salary_issues", "unfair_dismissal", "working_conditions", "other_labor"]
    texts = []
    for sub in subs:
        r = await client.post("/api/generate-template", json={
            "region_id": "msk", "region_name": "Москва",
            "category": "labor", "subcategory": sub,
        })
        assert r.status_code == 200
        texts.append(r.json()["text"])
    # Все 4 текста должны отличаться друг от друга
    assert len(set(texts)) == 4


@pytest.mark.asyncio
async def test_generate_template_unknown_category_fallback(client):
    """Неизвестная категория не должна ронять сервер — должен сработать default."""
    r = await client.post("/api/generate-template", json={
        "region_id": "msk", "region_name": "Москва",
        "category": "totally_unknown_category", "subcategory": "whatever",
    })
    assert r.status_code == 200
    assert len(r.json()["text"]) > 0


@pytest.mark.asyncio
async def test_generate_template_empty_region_name(client):
    """Пустое имя региона — не должно падать, просто странный текст."""
    r = await client.post("/api/generate-template", json={
        "region_id": "msk", "region_name": "",
        "category": "family", "subcategory": "large_family",
    })
    assert r.status_code == 200


# ── Classify response ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classify_otpiska(client):
    r = await client.post("/api/classify-response", json={
        "original_request": "Прошу предоставить перечень льгот",
        "official_response": "Оснований не найдено. Рекомендуем обратиться в другой орган.",
        "escalation_count": 0, "has_new_facts": False,
    })
    assert r.status_code == 200
    assert r.json()["classification"] == "отписка"


@pytest.mark.asyncio
async def test_classify_empty_request_422(client):
    r = await client.post("/api/classify-response", json={
        "original_request": "", "official_response": "текст",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_classify_empty_response_422(client):
    r = await client.post("/api/classify-response", json={
        "original_request": "текст", "official_response": "",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_classify_escalation_warning_triggers(client):
    """При escalation_count >= 2 и без новых фактов — предупреждение обязано появиться."""
    r = await client.post("/api/classify-response", json={
        "original_request": "текст запроса",
        "official_response": "Оснований не найдено.",
        "escalation_count": 2, "has_new_facts": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["escalation_warning"] is True
    assert data["escalation_warning_text"] is not None


@pytest.mark.asyncio
async def test_classify_no_warning_with_new_facts(client):
    """При наличии новых фактов предупреждение не должно появляться даже при escalation_count >= 2."""
    r = await client.post("/api/classify-response", json={
        "original_request": "текст запроса",
        "official_response": "Оснований не найдено.",
        "escalation_count": 3, "has_new_facts": True,
    })
    assert r.status_code == 200
    assert r.json()["escalation_warning"] is False


@pytest.mark.asyncio
async def test_classify_very_long_response(client):
    """Очень длинный текст ответа (10000 символов) не должен ронять сервер."""
    long_response = "Оснований не найдено. " * 500
    r = await client.post("/api/classify-response", json={
        "original_request": "запрос",
        "official_response": long_response,
    })
    assert r.status_code == 200


# ── Promises (Модуль 3) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_promise_full_lifecycle(client):
    """Создание → голосование до порога → автопересчёт статуса."""
    r = await client.post("/api/promises", json={
        "region_id": "spb", "official_name": "Тест Т.", "official_role": "Мэр",
        "promise_text": "Тестовое обещание для автономного теста номер один",
        "source_url": "https://example.com/1", "device_hash": "auto-test-1",
    })
    assert r.status_code == 201
    promise_id = r.json()["id"]
    assert r.json()["status"] == "checking"

    for i, voter in enumerate(["v1", "v2", "v3"]):
        r = await client.post(f"/api/promises/{promise_id}/vote", json={
            "vote": "broken", "voter_hash": voter,
        })
        assert r.status_code == 200

    final = await client.get(f"/api/promises?region_id=spb")
    promise = next(p for p in final.json() if p["id"] == promise_id)
    assert promise["status"] == "broken"
    assert promise["votes_broken"] == 3


@pytest.mark.asyncio
async def test_promise_duplicate_vote_409(client):
    r = await client.post("/api/promises", json={
        "region_id": "spb", "official_name": "Тест", "official_role": "Глава",
        "promise_text": "Второе тестовое обещание для проверки повторного голоса",
        "source_url": "https://example.com/2", "device_hash": "auto-test-2",
    })
    promise_id = r.json()["id"]

    r1 = await client.post(f"/api/promises/{promise_id}/vote", json={
        "vote": "fulfilled", "voter_hash": "same-voter",
    })
    assert r1.status_code == 200

    r2 = await client.post(f"/api/promises/{promise_id}/vote", json={
        "vote": "broken", "voter_hash": "same-voter",
    })
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_promise_vote_nonexistent_404(client):
    r = await client.post("/api/promises/999999/vote", json={
        "vote": "fulfilled", "voter_hash": "someone",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_promise_invalid_vote_value_422(client):
    r = await client.post("/api/promises", json={
        "region_id": "spb", "official_name": "Тест", "official_role": "Депутат",
        "promise_text": "Третье обещание для проверки невалидного значения голоса",
        "source_url": "https://example.com/3", "device_hash": "auto-test-3",
    })
    promise_id = r.json()["id"]
    r2 = await client.post(f"/api/promises/{promise_id}/vote", json={
        "vote": "maybe_yes_maybe_no", "voter_hash": "voter-x",
    })
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_promise_short_text_rejected(client):
    """promise_text короче 10 символов должен быть отклонён валидацией."""
    r = await client.post("/api/promises", json={
        "region_id": "spb", "official_name": "Тест", "official_role": "Мэр",
        "promise_text": "коротко",
        "source_url": "https://example.com/4", "device_hash": "auto-test-4",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_promise_stats(client):
    r = await client.get("/api/promises/stats?region_id=spb")
    assert r.status_code == 200
    data = r.json()
    assert data["total_promises"] >= 2  # минимум из предыдущих тестов


@pytest.mark.asyncio
async def test_promise_limit_param(client):
    """Создаём 5 обещаний, проверяем что limit реально ограничивает выдачу."""
    for i in range(5):
        r = await client.post("/api/promises", json={
            "region_id": "limit-test-region", "official_name": f"Тест {i}",
            "official_role": "Депутат",
            "promise_text": f"Обещание номер {i} для проверки лимита выдачи данных",
            "source_url": f"https://example.com/limit{i}",
            "device_hash": f"limit-fixture-{i}",
        })
        assert r.status_code == 201

    r_limited = await client.get("/api/promises?region_id=limit-test-region&limit=2")
    assert len(r_limited.json()) == 2

    r_all = await client.get("/api/promises?region_id=limit-test-region")
    assert len(r_all.json()) == 5


@pytest.mark.asyncio
async def test_promise_status_filter(client):
    """Фильтр по статусу должен корректно разделять checking/fulfilled/broken."""
    r = await client.get("/api/promises?region_id=limit-test-region&status=checking")
    assert len(r.json()) == 5

    r_fulfilled = await client.get("/api/promises?region_id=limit-test-region&status=fulfilled")
    assert len(r_fulfilled.json()) == 0


# ── Session logging ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_log(client):
    r = await client.post("/api/session", json={
        "device_hash": "session-test", "region_id": "msk",
        "category": "family", "subcategory": "large_family",
        "edit_pct": 25.5, "consent_given": True,
    })
    assert r.status_code == 204


# ── Feedback ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feedback(client):
    r = await client.post("/api/feedback", json={
        "response_text": "текст ответа для фидбэка",
        "original_request": "текст запроса для фидбэка",
        "region_id": "msk", "category": "family", "subcategory": "large_family",
        "system_label": "отписка", "user_label": "отписка",
    })
    assert r.status_code == 204


# ── CORS ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cors_header_present(client):
    r = await client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_promise_concurrent_votes_no_lost_updates(client):
    """
    Регрессионный тест на найденный стресс-тестом race condition:
    10 конкурентных голосов от разных voters не должны терять инкременты.
    """
    r = await client.post("/api/promises", json={
        "region_id": "concurrency-test", "official_name": "Конкурентный тест",
        "official_role": "Мэр",
        "promise_text": "Обещание для regression-теста на потерю обновлений",
        "source_url": "https://example.com/concurrency",
        "device_hash": "concurrency-creator",
    })
    promise_id = r.json()["id"]

    async def vote(i):
        return await client.post(f"/api/promises/{promise_id}/vote", json={
            "vote": "broken", "voter_hash": f"concurrent-voter-{i}",
        })

    results = await asyncio.gather(*[vote(i) for i in range(10)])
    assert all(r.status_code == 200 for r in results)

    final = await client.get("/api/promises?region_id=concurrency-test")
    promise = next(p for p in final.json() if p["id"] == promise_id)
    assert promise["votes_broken"] == 10, (
        f"Race condition regression: ожидали 10 голосов, получили {promise['votes_broken']}"
    )


@pytest.mark.asyncio
async def test_promise_concurrent_duplicate_returns_clean_409(client):
    """
    Регрессионный тест: конкурентные дубли от одного voter_hash не должны
    протекать как 500 (IntegrityError) — только 200 (один раз) и 409 (остальные).
    """
    r = await client.post("/api/promises", json={
        "region_id": "concurrency-test-2", "official_name": "Тест дублей",
        "official_role": "Депутат",
        "promise_text": "Обещание для проверки конкурентных дублирующих голосов",
        "source_url": "https://example.com/dup",
        "device_hash": "dup-creator",
    })
    promise_id = r.json()["id"]

    async def vote_same():
        return await client.post(f"/api/promises/{promise_id}/vote", json={
            "vote": "fulfilled", "voter_hash": "same-voter-regression",
        })

    results = await asyncio.gather(*[vote_same() for _ in range(10)])
    statuses = [r.status_code for r in results]
    assert statuses.count(200) == 1, f"Ожидали ровно 1 успех, получили {statuses.count(200)}"
    assert statuses.count(409) == 9, f"Ожидали 9 конфликтов, получили {statuses.count(409)}"
    assert 500 not in statuses, "IntegrityError протёк как 500 вместо чистого 409"


@pytest.mark.asyncio
async def test_cors_unknown_origin_not_reflected(client):
    """Неизвестный Origin не должен получить allow-origin в ответе — проверка что CORS реально ограничивает."""
    r = await client.get("/api/health", headers={"Origin": "https://evil-site.example"})
    cors_header = r.headers.get("access-control-allow-origin")
    assert cors_header != "https://evil-site.example"
