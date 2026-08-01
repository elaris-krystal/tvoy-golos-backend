"""
Общий rate limiter (slowapi) для main.py и router.py — вынесен отдельно,
чтобы избежать циклического импорта между ними.

Добавлен по итогам аудита безопасности: без лимитов API можно было
скриптом дёргать без ограничений — риск как нагрузки/расходов, так и
злоупотребления (массовая автогенерация однотипных обращений на одну цель).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
