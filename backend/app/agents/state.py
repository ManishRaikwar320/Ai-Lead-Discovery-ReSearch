from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator


class LeadDiscoveryRequest(BaseModel):
    industry: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Target industry",
    )

    location: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Target geographic market",
    )

    ideal_customer: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Description of the ideal customer",
    )

    services: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Services being offered to leads",
    )

    company_size: str | None = Field(
        default=None,
        max_length=100,
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of leads",
    )

    @field_validator("services")
    @classmethod
    def validate_services(cls, value: list[str]) -> list[str]:
        cleaned = [
            service.strip()
            for service in value
            if service.strip()
        ]

        if not cleaned:
            raise ValueError("At least one service is required.")

        return cleaned


class Lead(BaseModel):
    """A fully enriched lead as returned by the pipeline."""

    domain: str = ""
    company_name: str
    website: str
    title: str | None = None
    description: str | None = None
    source_url: str | None = None

    # Website research
    page_title: str | None = None
    meta_description: str | None = None
    summary: str | None = None
    research_ok: bool = False

    # Company extraction
    industry: str | None = None
    location: str | None = None
    company_size: str | None = None
    technologies: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)

    # ICP qualification
    qualified: bool = True
    fit_score: int = 50
    qualification_reason: str | None = None

    # Lead scoring
    score: int = 0
    tier: str | None = None
    score_rationale: str | None = None

    # Opportunity detection
    pain_points: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    recommended_service: str | None = None
    opportunity_summary: str | None = None

    # Outreach generation
    outreach_subject: str | None = None
    outreach_body: str | None = None
    personalization_hook: str | None = None


class LeadDiscoveryResponse(BaseModel):
    status: str
    total_leads: int
    funnel: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    leads: list[Lead] = Field(default_factory=list)


class LeadDiscoveryState(TypedDict, total=False):
    # Input
    industry: str
    location: str
    ideal_customer: str
    services: list[str]
    company_size: str | None
    limit: int

    # 1. Query generation
    search_queries: list[str]

    # 2. Tavily discovery
    raw_search_results: list[dict[str, Any]]

    # 3. Deduplication
    candidates: list[dict[str, Any]]

    # 4. Website research
    research_pool: int
    researched_leads: list[dict[str, Any]]

    # 5. Company extraction
    extracted_leads: list[dict[str, Any]]

    # 6. ICP qualification
    qualified_leads: list[dict[str, Any]]

    # 7. Lead scoring
    scored_leads: list[dict[str, Any]]

    # 8. Opportunity detection
    opportunity_leads: list[dict[str, Any]]

    # 9. Outreach generation
    outreach_leads: list[dict[str, Any]]

    # 10. Validation
    validated_leads: list[dict[str, Any]]

    # 11. Final leads
    leads: list[dict[str, Any]]
    funnel: dict[str, int]

    errors: list[str]
