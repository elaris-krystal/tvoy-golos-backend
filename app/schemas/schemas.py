from pydantic import BaseModel, Field
from typing import Optional


class BenefitOut(BaseModel):
    id: int
    benefit_name: str
    description: str
    legal_basis: str
    source_url: Optional[str] = None
    is_federal: bool


class GenerateTemplateIn(BaseModel):
    region_id: str
    region_name: str
    category: str
    subcategory: str
    topic: Optional[str] = None


class GenerateTemplateOut(BaseModel):
    text: str
    is_uniqualized: bool
    template_version: str
    edit_pct_baseline: float = 0.0


class ClassifyIn(BaseModel):
    original_request: str
    official_response: str
    escalation_count: int = 0
    has_new_facts: bool = False
    region_id: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None


class ClassifyOut(BaseModel):
    classification: str
    score: float
    markers: dict
    explanation_user: str
    suggested_grounds: list[str]
    escalation_warning: bool
    escalation_warning_text: Optional[str] = None
    used_llm: bool = False


class SessionIn(BaseModel):
    device_hash: str = Field(..., max_length=64)
    region_id: str
    category: str
    subcategory: str
    template_version: Optional[str] = None
    edit_pct: float = 0.0
    consent_given: bool = False


class FeedbackIn(BaseModel):
    response_text: str
    original_request: str
    region_id: str
    category: str
    subcategory: str
    organ: Optional[str] = None
    system_label: str
    user_label: str
    edit_pct: float = 0.0


class PromiseCreateIn(BaseModel):
    region_id: str
    official_name: str = Field(..., max_length=200)
    official_role: str = Field(..., max_length=200)
    promise_text: str = Field(..., min_length=10, max_length=2000)
    source_url: str = Field(..., max_length=500)
    promise_date: Optional[str] = None
    device_hash: str = Field(..., max_length=64)
    # Обязательное явное подтверждение — аналог consent-экранов в Модулях 1/2.
    # Без него запись не создаётся. Это не формальность: платформа публично
    # приписывает слова конкретному названному человеку, и должна иметь
    # зафиксированное подтверждение того, что добавивший ознакомлен с
    # ответственностью за недостоверные сведения (ст. 152 ГК РФ).
    accuracy_confirmed: bool = Field(...)


class PromiseOut(BaseModel):
    id: int
    region_id: str
    official_name: str
    official_role: str
    promise_text: str
    source_url: str
    promise_date: Optional[str] = None
    status: str
    votes_fulfilled: int
    votes_broken: int
    dispute_count: int = 0
    created_at: str


class PromiseVoteIn(BaseModel):
    vote: str = Field(..., pattern="^(fulfilled|broken)$")
    voter_hash: str = Field(..., max_length=64)


class PromiseDisputeIn(BaseModel):
    reason: str = Field(..., pattern="^(not_in_source|fabricated|other)$")
    disputer_hash: str = Field(..., max_length=64)


class RegionStatsOut(BaseModel):
    region_id: str
    total_promises: int
    fulfilled_count: int
    broken_count: int
    checking_count: int
