"""
Классификатор ответов чиновников.
Rule-based всегда доступен.
LLM используется только для неоднозначных случаев (score 1-2).
"""
import re
import hashlib
from typing import Optional

from app.core.config import settings
from app.schemas.schemas import ClassifyIn, ClassifyOut
from app.services.llm import llm_complete, parse_json_response

MARKER_PHRASES = [
    "не представляется возможным",
    "ранее вам уже сообщалось",
    "рекомендуем обратиться",
    "не входит в компетенцию",
    "оснований не найдено",
    "принято к сведению",
    "направлено по подведомственности",
    "вопрос находится на контроле",
    "меры будут приняты",
    "в соответствии с действующим законодательством",
]

LAW_PATTERN = re.compile(
    r"(?:ст\.|статья|фз\s*№|федеральн\w*\s+закон|нк\s+рф|жк\s+рф|тк\s+рф|кас\s+рф)\s*[\d№]",
    re.IGNORECASE,
)


def _significant_words(text: str) -> set[str]:
    """
    Значимые слова длиннее 5 символов, приведённые к псевдо-основе (первые 6 символов).
    Русский язык сильно флективный ('многодетным' vs 'многодетной', 'Москве' vs 'Москвы'),
    точное совпадение словоформ ненадёжно. Обрезка до префикса — грубая, но рабочая
    эвристика без подключения внешних NLP-библиотек (pymorphy2 и т.п. избыточны для MVP).
    """
    words = re.split(r"[\s,.;:!?()«»]+", text)
    result = set()
    for w in words:
        w_clean = w.lower().strip()
        if len(w_clean) > 5:
            result.add(w_clean[:6])
    return result


def _entity_overlap_pct(request: str, response: str) -> float:
    req_words = _significant_words(request)
    res_words = _significant_words(response)
    if not req_words:
        return 0.0
    return len(req_words & res_words) / len(req_words) * 100


def _rule_based_classify(data: ClassifyIn) -> ClassifyOut:
    text = data.official_response.lower()
    request = data.original_request.lower()

    overlap = _entity_overlap_pct(request, data.official_response)
    threshold = 50.0 if (data.escalation_count >= 2 and not data.has_new_facts) else 40.0
    marker1 = 1 if overlap >= threshold else 0

    has_law = bool(LAW_PATTERN.search(data.official_response))
    marker2 = 1 if has_law else 0

    found_markers = [m for m in MARKER_PHRASES if m in text]
    is_redirect_only = ("обратитесь" in text or "направлено" in text) and not has_law
    marker3 = 0 if (found_markers or is_redirect_only) else 1

    score = float(marker1 + marker2 + marker3)

    if score < 1:
        classification, explanation = "отписка", (
            "Ответ содержит общие фразы без конкретики. "
            "Поставленный вопрос не раскрыт, нормы к вашей ситуации не применены."
        )
    elif score < 2:
        classification, explanation = "слабый ответ", (
            "Ответ частично касается вашего вопроса, "
            "но не содержит полноценного обоснования."
        )
    elif score < 3:
        classification, explanation = "частичный ответ", (
            "Ответ затрагивает суть вопроса, но неполный — "
            "часть требований осталась без рассмотрения."
        )
    else:
        classification, explanation = "ответ по существу", (
            "Ответ содержит конкретное обоснование со ссылками на нормы, "
            "применёнными к вашей ситуации."
        )

    suggested_grounds: list[str] = []
    if score < 2:
        suggested_grounds = ["Нарушение права на ответ по существу (ст. 5 59-ФЗ)",
                             "Отсутствие нормативного обоснования"]
        if found_markers:
            suggested_grounds.append(f'Фраза-маркер отписки: «{found_markers[0]}»')

    escalation_warning = data.escalation_count >= 2 and not data.has_new_facts
    warning_text: Optional[str] = None
    if escalation_warning:
        warning_text = (
            "Повторная эскалация без новых обстоятельств может быть расценена "
            "как злоупотребление правом (ст. 10 ГК РФ, практика ВС РФ 2026). "
            "Рекомендуем добавить новые факты или документы."
        )

    return ClassifyOut(
        classification=classification,
        score=score,
        markers={"relevance": marker1, "normative": marker2, "redirect": marker3},
        explanation_user=explanation,
        suggested_grounds=suggested_grounds,
        escalation_warning=escalation_warning,
        escalation_warning_text=warning_text,
        used_llm=False,
    )


async def _llm_classify(data: ClassifyIn, rule_result: ClassifyOut) -> ClassifyOut:
    """LLM уточняет классификацию для неоднозначных случаев."""
    prompt = f"""Оцени ответ чиновника на обращение гражданина.

Запрос гражданина:
{data.original_request[:800]}

Ответ чиновника:
{data.official_response[:1500]}

Rule-based оценка: {rule_result.classification} (score: {rule_result.score})
Эскалаций ранее: {data.escalation_count}

Уточни классификацию если нужно. Объясни пользователю 2-3 предложения что не так (или почему ответ хороший).

Верни только JSON:
{{"classification": "отписка"|"слабый ответ"|"частичный ответ"|"ответ по существу", "explanation_user": "..."}}"""

    raw = await llm_complete(prompt, max_tokens=300, temperature=0.1)
    if not raw:
        return rule_result

    parsed = parse_json_response(raw)
    if not parsed:
        return rule_result

    return ClassifyOut(
        classification=parsed.get("classification", rule_result.classification),
        score=rule_result.score,
        markers=rule_result.markers,
        explanation_user=parsed.get("explanation_user", rule_result.explanation_user),
        suggested_grounds=rule_result.suggested_grounds,
        escalation_warning=rule_result.escalation_warning,
        escalation_warning_text=rule_result.escalation_warning_text,
        used_llm=True,
    )


async def classify_response(data: ClassifyIn) -> ClassifyOut:
    rule_result = _rule_based_classify(data)
    # LLM только для неоднозначных случаев
    if settings.llm_provider != "none" and rule_result.score in (1.0, 2.0):
        return await _llm_classify(data, rule_result)
    return rule_result


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]
