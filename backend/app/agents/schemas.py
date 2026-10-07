"""Structured-output schemas used by the LLM stages of the pipeline."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, model_validator

TIER_A_MIN = 80
TIER_B_MIN = 60

LIST_KEYS = frozenset(
    {
        "technologies",
        "signals",
        "pain_points",
        "buying_signals",
        "queries",
    }
)

TEXT_KEYS = frozenset({"domain", "subject", "body", "tier"})

BOOL_KEYS = frozenset({"detected", "qualified"})

SCORE_KEYS = ("score", "fit_score")


def clamp_score(value: object) -> int:
    """Coerce an LLM produced score into an int between 0 and 100."""
    if isinstance(value, bool):
        return 0

    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))

    digits = re.findall(r"\d+", str(value or ""))

    if not digits:
        return 0

    return max(0, min(100, int(digits[0])))


def tier_for_score(score: int) -> str:
    if score >= TIER_A_MIN:
        return "A"

    if score >= TIER_B_MIN:
        return "B"

    return "C"


def coerce_list(value: object) -> list:
    """LLMs frequently answer `null` instead of `[]`; normalise that."""
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]

    return []


def sanitize_payload(data: object) -> object:
    """Repair the shape of an LLM JSON payload before field validation."""
    if not isinstance(data, dict):
        return data

    for key in LIST_KEYS:
        if key in data:
            data[key] = coerce_list(data[key])

    for key in TEXT_KEYS:
        if key in data and data[key] is not None:
            data[key] = str(data[key])

    for key in BOOL_KEYS:
        if data.get(key) is None:
            data.pop(key, None)

    for key in SCORE_KEYS:
        if key in data:
            data[key] = clamp_score(data[key])

    return data


class LLMEntry(BaseModel):
    """Base model that repairs LLM output before field validation."""

    domain: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sanitize(cls, data: object) -> object:
        return sanitize_payload(data)


class LLMBatch(BaseModel):
    """Base model for batch payloads; a `null` batch becomes an empty batch."""

    @model_validator(mode="before")
    @classmethod
    def _sanitize(cls, data: object) -> object:
        if isinstance(data, dict):
            for name in cls.model_fields:
                if data.get(name) is None:
                    data.pop(name, None)

        return data


class SearchQueries(LLMBatch):
    queries: list[str] = Field(
        min_length=1,
        max_length=5,
    )

    @model_validator(mode="before")
    @classmethod
    def _sanitize_queries(cls, data: object) -> object:
        return sanitize_payload(data)


class CompanyExtraction(LLMEntry):
    company_name: str | None = None
    industry: str | None = None
    location: str | None = None
    company_size: str | None = None
    summary: str | None = None
    technologies: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class CompanyExtractionBatch(LLMBatch):
    companies: list[CompanyExtraction] = Field(default_factory=list)


class ICPVerdict(LLMEntry):
    qualified: bool = True
    fit_score: int = Field(default=50, ge=0, le=100)
    reason: str | None = None


class ICPVerdictBatch(LLMBatch):
    verdicts: list[ICPVerdict] = Field(default_factory=list)


class LeadScore(LLMEntry):
    score: int = Field(default=50, ge=0, le=100)
    tier: str | None = None
    rationale: str | None = None


class LeadScoreBatch(LLMBatch):
    scores: list[LeadScore] = Field(default_factory=list)


class OpportunityFinding(LLMEntry):
    detected: bool = True
    pain_points: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    recommended_service: str | None = None
    summary: str | None = None


class OpportunityBatch(LLMBatch):
    opportunities: list[OpportunityFinding] = Field(default_factory=list)


class OutreachMessage(LLMEntry):
    subject: str = ""
    body: str = ""
    personalization_hook: str | None = None


class OutreachBatch(LLMBatch):
    messages: list[OutreachMessage] = Field(default_factory=list)
