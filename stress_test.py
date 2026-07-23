"""
Стресс-тест «Твой Голос» backend.
Проверяет поведение под конкурентной нагрузкой — то, что обычные тесты не ловят.

Тесты на конкурентное голосование за обещания убраны вместе с Модулем 3
(отключён по решению о минимизации рисков на старте — см. миграцию 0005).
"""
import asyncio
import time
import httpx

BASE = "http://127.0.0.1:8000/api"


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
    print("=== Стресс-тест 1: нагрузка на генератор (50 параллельных) ===")
    r1 = await test_generator_load()
    print()

    print("=== Стресс-тест 2: нагрузка на чтение (100 параллельных) ===")
    r2 = await test_benefits_read_load()
    print()

    print("=" * 50)
    all_passed = all([r1, r2])
    print(f"ИТОГ: {'ВСЕ ПРОШЛИ' if all_passed else 'ЕСТЬ ПРОБЛЕМЫ'}")
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
