"""
Генератор текстов обращений.
Проход 1: генерация через LLM.
Проход 2: уникализация (_uniqualize_text).
Fallback: статический шаблон если LLM недоступна.
"""
from difflib import SequenceMatcher
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.schemas import GenerateTemplateIn, GenerateTemplateOut
from app.services.llm import llm_complete

TEMPLATE_VERSION = "1.1"

STATIC_TEMPLATES: dict[str, str] = {
    "family": (
        "Прошу предоставить актуальный перечень мер социальной поддержки "
        "для семей с детьми в {region_name}. "
        "В соответствии со ст. 5 Федерального закона № 59-ФЗ от 02.05.2006 "
        "прошу ответить по существу в течение 30 дней. "
        "Укажите конкретные выплаты, льготы и порядок их получения."
    ),
    "employment": (
        "Прошу предоставить информацию о мерах поддержки граждан "
        "в сфере занятости в {region_name}. "
        "Основание: ст. 5 ФЗ № 59-ФЗ от 02.05.2006. "
        "Срок ответа — 30 дней. "
        "Перечислите доступные программы и документы для их получения."
    ),
    "health": (
        "Прошу предоставить перечень льгот и выплат "
        "для граждан с ограничениями по здоровью в {region_name}. "
        "Основание: ФЗ № 181-ФЗ от 24.11.1995, ст. 5 ФЗ № 59-ФЗ. "
        "Срок ответа — 30 дней."
    ),
    "housing": (
        "Прошу предоставить информацию о мерах жилищной поддержки "
        "для граждан в {region_name}. "
        "Основание: ЖК РФ, ст. 5 ФЗ № 59-ФЗ. "
        "Срок ответа — 30 дней."
    ),
    "pension": (
        "Прошу предоставить перечень льгот и надбавок "
        "для пенсионеров в {region_name}. "
        "Основание: ФЗ № 400-ФЗ от 28.12.2013, ст. 5 ФЗ № 59-ФЗ. "
        "Срок ответа — 30 дней."
    ),
    "education": (
        "Прошу предоставить информацию о мерах поддержки "
        "в сфере образования в {region_name}. "
        "Основание: ФЗ № 273-ФЗ от 29.12.2012, ст. 5 ФЗ № 59-ФЗ. "
        "Срок ответа — 30 дней."
    ),
    "labor_salary_issues": (
        "Прошу провести проверку по факту задержки (невыплаты) заработной платы "
        "в {region_name}. "
        "В соответствии со ст. 136, 142 Трудового кодекса РФ работодатель обязан "
        "выплачивать заработную плату в установленные сроки, а в случае задержки — "
        "компенсацию по ст. 236 ТК РФ. "
        "Прошу провести проверку, применить меры реагирования и разъяснить порядок "
        "взыскания задолженности и компенсации. "
        "Срок ответа — 30 дней в соответствии со ст. 5 ФЗ № 59-ФЗ."
    ),
    "labor_unfair_dismissal": (
        "Прошу провести проверку законности моего увольнения. "
        "В соответствии со ст. 391, 392 Трудового кодекса РФ прошу разъяснить порядок "
        "восстановления нарушенных трудовых прав, а также провести проверку соблюдения "
        "работодателем процедуры увольнения. "
        "Срок ответа — 30 дней в соответствии со ст. 5 ФЗ № 59-ФЗ."
    ),
    "labor_working_conditions": (
        "Прошу провести проверку условий труда на предмет соответствия требованиям "
        "безопасности. "
        "В соответствии со ст. 212, 219 Трудового кодекса РФ работодатель обязан "
        "обеспечить безопасные условия труда. Прошу провести проверку и понудить "
        "работодателя к устранению выявленных нарушений. "
        "Срок ответа — 30 дней в соответствии со ст. 5 ФЗ № 59-ФЗ."
    ),
    "labor_other_labor": (
        "Прошу провести проверку по факту нарушения моих трудовых прав "
        "в {region_name}. "
        "Основание: ст. 353-356 Трудового кодекса РФ (государственный надзор "
        "за соблюдением трудового законодательства). "
        "Срок ответа — 30 дней в соответствии со ст. 5 ФЗ № 59-ФЗ."
    ),
    "default": (
        "Прошу предоставить актуальный перечень мер социальной поддержки, "
        "положенных гражданину в {region_name}. "
        "В соответствии со ст. 5 Федерального закона № 59-ФЗ от 02.05.2006 "
        "прошу предоставить исчерпывающий ответ по существу в течение 30 дней."
    ),
}


def _static_template(data: GenerateTemplateIn) -> str:
    # Для категории 'labor' шаблоны различаются по подкатегории (нет общего для всей категории)
    combined_key = f"{data.category}_{data.subcategory}"
    tpl = STATIC_TEMPLATES.get(combined_key) or STATIC_TEMPLATES.get(data.category) or STATIC_TEMPLATES["default"]
    return tpl.format(region_name=data.region_name)


def _calc_diff_pct(original: str, modified: str) -> float:
    orig_words = original.split()
    mod_words = modified.split()
    if not orig_words:
        return 0.0
    matcher = SequenceMatcher(None, orig_words, mod_words)
    matching = sum(b.size for b in matcher.get_matching_blocks())
    changed = len(orig_words) - matching
    return round(changed / len(orig_words) * 100, 1)


async def _uniqualize_text(text: str) -> tuple[str, bool]:
    """
    Второй проход: структурная и лексическая уникализация.
    Возвращает (uniqualized_text, is_uniqualized).
    При неудаче возвращает исходный текст с is_uniqualized=False.
    """
    prompt = f"""Перепиши текст официального обращения. Сохрани смысл и юридическую силу, но измени структуру и лексику.

Исходный текст:
{text}

Требования:
1. Измени порядок блоков (факт/норма/требование).
2. Замени не менее 40% значимых слов синонимами.
3. Сохрани без изменений: все цифры, даты, статьи законов, наименования органов.
4. Если уникализация невозможна без потери смысла — верни текст с меткой [БАЗОВЫЙ ШАБЛОН] в начале.

Верни только текст."""

    result = await llm_complete(prompt, max_tokens=600, temperature=0.8)
    if not result:
        return text, False

    if result.startswith("[БАЗОВЫЙ ШАБЛОН]"):
        result = result.replace("[БАЗОВЫЙ ШАБЛОН]", "").strip()

    diff_pct = _calc_diff_pct(text, result)
    if diff_pct >= settings.uniqualize_min_pct:
        return result, True

    # Порог не достигнут — возвращаем исходный
    return text, False


async def _generate_base(data: GenerateTemplateIn) -> str | None:
    """Первый проход: генерация по промпту."""
    prompt = f"""Составь обращение по 59-ФЗ:

Регион: {data.region_name}
Категория: {data.category} / {data.subcategory}
Тема: {data.topic or "предоставление информации о мерах социальной поддержки"}

Требования:
1. Предпочтительно начинать с факта или конкретного вопроса. Избегай стандартных вводных «В соответствии с...».
2. Укажи конкретную норму, применимую к категории.
3. Сформулируй конкретный запрос.
4. Укажи срок 30 дней по 59-ФЗ.
5. 150–250 слов.

Верни только текст обращения."""

    return await llm_complete(prompt, max_tokens=600, temperature=0.7)


async def generate_template(data: GenerateTemplateIn) -> GenerateTemplateOut:
    """Основная точка входа: генерация → уникализация → fallback."""
    text = ""
    is_uniqualized = False

    # Проход 1: генерация
    generated = await _generate_base(data)

    if generated:
        # Проход 2: уникализация
        text, is_uniqualized = await _uniqualize_text(generated)
    else:
        # Fallback на статический шаблон
        text = _static_template(data)

    static_baseline = _static_template(data)
    edit_pct_baseline = _calc_diff_pct(static_baseline, text)

    return GenerateTemplateOut(
        text=text,
        is_uniqualized=is_uniqualized,
        template_version=TEMPLATE_VERSION,
        edit_pct_baseline=edit_pct_baseline,
    )
