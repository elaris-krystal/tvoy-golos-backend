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


class DevFeedbackIn(BaseModel):
    message: str = Field(..., min_length=5, max_length=2000)
    category: str = Field(..., pattern="^(bug|suggestion|other)$")
    page: Optional[str] = Field(None, max_length=200)
