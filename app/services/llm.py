"""
Универсальный LLM-клиент.
Провайдер выбирается через LLM_PROVIDER в .env: anthropic | openai | none
При ошибке или none — возвращает None, вызывающий код использует fallback.
"""
import asyncio
import json
import re
from typing import Optional
from app.core.config import settings


async def llm_complete(prompt: str, max_tokens: int = 600, temperature: float = 0.7) -> Optional[str]:
    """
    Отправляет промпт в LLM и возвращает текстовый ответ.
    Возвращает None если провайдер не настроен или запрос упал.
    """
    provider = getattr(settings, "llm_provider", "none").lower()

    if provider == "anthropic" and settings.anthropic_api_key:
        return await _anthropic_complete(prompt, max_tokens, temperature)
    elif provider == "openai":
        openai_key = getattr(settings, "openai_api_key", "")
        if openai_key:
            return await _openai_complete(prompt, max_tokens, temperature, openai_key)
    return None


async def _anthropic_complete(prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=settings.llm_timeout_sec,
        )
        return response.content[0].text.strip()
    except Exception:
        return None


async def _openai_complete(prompt: str, max_tokens: int, temperature: float, api_key: str) -> Optional[str]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def parse_json_response(text: str) -> Optional[dict]:
    """Парсит JSON из LLM-ответа, убирая markdown-обёртки."""
    try:
        cleaned = re.sub(r"```json|```", "", text).strip()
        return json.loads(cleaned)
    except Exception:
        return None
