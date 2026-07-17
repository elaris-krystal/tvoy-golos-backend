"""
Стресс-тест «Твой Голос» backend.
Проверяет поведение под конкурентной нагрузкой — то, что обычные тесты не ловят.
"""
import asyncio
import time
import httpx

BASE = "http://127.0.0.1:8000/api"


async def test_concurrent_votes_race_condition():
    """
    Критический тест: если 20 разных пользователей одновременно голосуют
    за одно и то же обещание, votes_fulfilled/votes_broken не должны
    потеряться из-за гонки (race condition) при инкременте в БД.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE}/promises", json={
            "region_id": "stress-region", "official_name": "Стресс Тест",
            "official_role": "Депутат",
            "promise_text": "Обещание для проверки конкурентного голосования race condition",
            "source_url": "https://example.com/stress1",
            "device_hash": "stress-creator",
        })
        promise_id = r.json()["id"]

        # 20 параллельных голосов от разных voter_hash
        async def vote(i):
            return await client.post(f"{BASE}/promises/{promise_id}/vote", json={
                "vote": "broken", "voter_hash": f"stress-voter-{i}",
            })

        results = await asyncio.gather(*[vote(i) for i in range(20)], return_exceptions=True)

        success_count = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
        error_count = len(results) - success_count

        print(f"  Успешных голосов: {success_count}/20")
        print(f"  Ошибок: {error_count}")

        # Проверяем финальное состояние
        final = await client.get(f"{BASE}/promises?region_id=stress-region")
        promise = next(p for p in final.json() if p["id"] == promise_id)
        print(f"  votes_broken в БД: {promise['votes_broken']}")
        print(f"  Статус: {promise['status']}")

        if promise["votes_broken"] != success_count:
            print(f"  ⚠ РАСХОЖДЕНИЕ: успешных голосов {success_count}, но votes_broken={promise['votes_broken']}")
            return False
        else:
            print(f"  ✓ Все успешные голоса учтены корректно, race condition не обнаружена")
            return True


async def test_concurrent_duplicate_vote_same_voter():
    """
    20 параллельных попыток голосования ОДНИМ И ТЕМ ЖЕ voter_hash.
    Должен пройти РОВНО один запрос, остальные 19 — получить 409.
    Это самый опасный тест на race condition: если уникальный индекс
    не защищает атомарно, может пройти больше одного голоса.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE}/promises", json={
            "region_id": "stress-region-2", "official_name": "Тест Дубликатов",
            "official_role": "Мэр",
            "promise_text": "Обещание для проверки конкурентных дублирующихся голосов",
            "source_url": "https://example.com/stress2",
            "device_hash": "stress-creator-2",
        })
        promise_id = r.json()["id"]

        async def vote_same():
            return await client.post(f"{BASE}/promises/{promise_id}/vote", json={
                "vote": "fulfilled", "voter_hash": "same-voter-stress-test",
            })

        results = await asyncio.gather(*[vote_same() for _ in range(20)], return_exceptions=True)

        status_codes = [r.status_code if not isinstance(r, Exception) else "EXC" for r in results]
        success_200 = status_codes.count(200)
        conflict_409 = status_codes.count(409)

        print(f"  200 (успех): {success_200}")
        print(f"  409 (конфликт): {conflict_409}")
        print(f"  Другое: {len(results) - success_200 - conflict_409}")

        final = await client.get(f"{BASE}/promises?region_id=stress-region-2")
        promise = next(p for p in final.json() if p["id"] == promise_id)
        print(f"  votes_fulfilled в БД: {promise['votes_fulfilled']}")

        if success_200 != 1:
            print(f"  ⚠ КРИТИЧНО: прошло {success_200} голосов вместо ровно 1! Защита от дублей не атомарна.")
            return False
        if promise["votes_fulfilled"] != 1:
            print(f"  ⚠ КРИТИЧНО: votes_fulfilled={promise['votes_fulfilled']}, ожидали 1")
            return False

        print(f"  ✓ Ровно 1 голос прошёл, защита от дублей атомарна под конкурентной нагрузкой")
        return True


async def test_generator_load():
    """50 параллельных запросов на генерацию шаблона — проверка что sync-код (SequenceMatcher) не блокирует event loop надолго."""
    async with httpx.AsyncClient(timeout=30) as client:
        start = time.time()

        async def gen(i):
            cat = ["family", "labor", "pension", "health"][i % 4]
            sub = {"family": "large_family", "labor": "salary_issues",
                   "pension": "pensioner", "health": "disability"}[cat]
            return await client.post(f"{BASE}/generate-template", json={
                "region_id": "msk", "region_name": "Москва",
                "category": cat, "subcategory": sub,
            })

        results = await asyncio.gather(*[gen(i) for i in range(50)], return_exceptions=True)
        elapsed = time.time() - start

        success = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
        print(f"  50 запросов за {elapsed:.2f} сек")
        print(f"  Успешных: {success}/50")
        print(f"  Среднее время на запрос: {elapsed/50*1000:.1f} мс")

        if success != 50:
            print(f"  ⚠ Не все запросы успешны")
            return False
        return True


async def test_benefits_read_load():
    """100 параллельных GET-запросов на чтение льгот — проверка производительности при чтении."""
    async with httpx.AsyncClient(timeout=30) as client:
        start = time.time()

        async def get_benefits():
            return await client.get(f"{BASE}/benefits?region_id=msk&category=family&subcategory=large_family")

        results = await asyncio.gather(*[get_benefits() for _ in range(100)], return_exceptions=True)
        elapsed = time.time() - start

        success = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
        print(f"  100 запросов на чтение за {elapsed:.2f} сек")
        print(f"  Успешных: {success}/100")

        return success == 100


async def main():
    print("=== Стресс-тест 1: конкурентное голосование (20 разных voters) ===")
    r1 = await test_concurrent_votes_race_condition()
    print()

    print("=== Стресс-тест 2: конкурентные дубли (один voter, 20 попыток) ===")
    r2 = await test_concurrent_duplicate_vote_same_voter()
    print()

    print("=== Стресс-тест 3: нагрузка на генератор (50 параллельных) ===")
    r3 = await test_generator_load()
    print()

    print("=== Стресс-тест 4: нагрузка на чтение (100 параллельных) ===")
    r4 = await test_benefits_read_load()
    print()

    print("=" * 50)
    all_passed = all([r1, r2, r3, r4])
    print(f"ИТОГ: {'ВСЕ ПРОШЛИ' if all_passed else 'ЕСТЬ ПРОБЛЕМЫ'}")
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
