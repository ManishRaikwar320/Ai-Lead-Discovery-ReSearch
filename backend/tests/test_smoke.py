import re
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents import nodes
from app.agents.graph import STAGE_NAMES, get_lead_discovery_graph
from app.agents.nodes import (
    _normalize_tier,
    clean_company_name,
    deduplicate_leads,
    domain_key,
    finalize_leads,
    is_company_domain,
    normalize_domain,
    validate_leads,
)
from app.agents.schemas import (
    CompanyExtraction,
    CompanyExtractionBatch,
    ICPVerdict,
    ICPVerdictBatch,
    LeadScore,
    LeadScoreBatch,
    OpportunityBatch,
    OpportunityFinding,
    OutreachBatch,
    OutreachMessage,
    SearchQueries,
    clamp_score,
    tier_for_score,
)
from app.agents.state import LeadDiscoveryRequest
from app.tools.fetch_page import extract_page_text

EXPECTED_STAGES = [
    "generate_search_queries",
    "discover_leads",
    "deduplicate_leads",
    "research_websites",
    "extract_companies",
    "qualify_icp",
    "score_leads",
    "detect_opportunities",
    "generate_outreach",
    "validate_leads",
    "finalize_leads",
]

SEARCH_RESULTS = [
    {
        "title": "Home | Acme Dental",
        "url": "https://www.acme-dental.com/about",
        "content": "Acme description",
    },
    {
        "title": "Acme Dental homepage",
        "url": "https://acme-dental.com",
        "content": "Acme homepage description",
    },
    {
        "title": "Bright Smile Dental",
        "url": "https://brightsmile.io",
        "content": "Bright description",
    },
    {
        "title": "Care Clinic",
        "url": "https://careclinic.co",
        "content": "Care description",
    },
    {
        "title": "No URL",
        "url": "",
        "content": "skipped",
    },
    {
        "title": "Dental automation tips - Medium",
        "url": "https://medium.com/@writer/dental-automation-tips",
        "content": "content platform, not a company",
    },
]

FAKE_SETTINGS = SimpleNamespace(
    max_search_results=5,
    research_concurrency=3,
    research_timeout=1.0,
    research_max_chars=1000,
    max_research_leads=12,
    llm_batch_size=4,
    llm_context_chars=800,
    llm_brief_chars=300,
    retry_backoff=0.0,
)


def prompt_domains(prompt: str) -> list[str]:
    return re.findall(r"^domain: (\S+)$", prompt, flags=re.MULTILINE)


def fake_invoke_structured(schema, prompt, **kwargs):
    domains = prompt_domains(prompt)

    if schema is SearchQueries:
        return SearchQueries(queries=["dental clinics Austin TX"])

    if schema is CompanyExtractionBatch:
        return CompanyExtractionBatch(
            companies=[
                CompanyExtraction(
                    domain=domain,
                    company_name=f"Company {domain}",
                    industry="dental clinic",
                    location="Austin, Texas",
                    company_size="small business",
                    summary=f"Summary for {domain}",
                    technologies=["WordPress"],
                    signals=["online booking"],
                )
                for domain in domains
            ]
        )

    if schema is ICPVerdictBatch:
        return ICPVerdictBatch(
            verdicts=[
                ICPVerdict(
                    domain=domain,
                    qualified=domain != "careclinic.co",
                    fit_score=90 if index == 0 else 65,
                    reason=f"Verdict for {domain}",
                )
                for index, domain in enumerate(domains)
            ]
        )

    if schema is LeadScoreBatch:
        return LeadScoreBatch(
            scores=[
                LeadScore(
                    domain=domain,
                    score=[92, 74, 40][index],
                    tier=["A", "B", "C"][index],
                    rationale=f"Score for {domain}",
                )
                for index, domain in enumerate(domains)
            ]
        )

    if schema is OpportunityBatch:
        return OpportunityBatch(
            opportunities=[
                OpportunityFinding(
                    domain=domain,
                    detected=True,
                    pain_points=["manual intake"],
                    buying_signals=["online booking form"],
                    recommended_service="patient intake automation",
                    summary=f"Opportunity for {domain}",
                )
                for domain in domains
            ]
        )

    if schema is OutreachBatch:
        return OutreachBatch(
            messages=[
                OutreachMessage(
                    domain=domain,
                    subject=f"Idea for {domain}",
                    body=f"Hi {domain} team,\n\nLet's talk.",
                    personalization_hook="online booking form",
                )
                for domain in domains
            ]
        )

    raise AssertionError(f"Unexpected schema: {schema}")


def fake_search_web(query: str, max_results: int = 5) -> list[dict]:
    return SEARCH_RESULTS


def fake_fetch_pages(urls, **kwargs):
    return {
        url: {
            "url": url,
            "ok": True,
            "title": "Home | Company",
            "meta_description": "Meta description",
            "text": "We provide dental care in Austin.",
            "error": None,
        }
        for url in urls
    }


@pytest.fixture
def offline_graph(monkeypatch):
    monkeypatch.setattr(nodes, "invoke_structured", fake_invoke_structured)
    monkeypatch.setattr(nodes, "search_web", fake_search_web)
    monkeypatch.setattr(nodes, "fetch_pages", fake_fetch_pages)
    monkeypatch.setattr(nodes, "get_settings", lambda: FAKE_SETTINGS)

    return get_lead_discovery_graph()


def base_state(**overrides) -> dict:
    state = {
        "industry": "dental clinics",
        "location": "Austin, Texas",
        "ideal_customer": "Independent dental practices with 2-10 dentists",
        "services": ["patient intake automation"],
        "company_size": "small business",
        "limit": 5,
        "errors": [],
    }
    state.update(overrides)
    return state


# --------------------------------------------------------------------------
# Request schema
# --------------------------------------------------------------------------


def test_request_requires_valid_services():
    with pytest.raises(ValidationError):
        LeadDiscoveryRequest(
            industry="dental clinics",
            location="Austin, TX",
            ideal_customer="Independent dental practices needing automation",
            services=["   "],
        )


def test_request_accepts_valid_payload():
    request = LeadDiscoveryRequest(
        industry="dental clinics",
        location="Austin, TX",
        ideal_customer="Independent dental practices needing automation",
        services=[" intake automation ", "booking"],
        limit=3,
    )
    assert request.services == ["intake automation", "booking"]
    assert request.limit == 3


# --------------------------------------------------------------------------
# Stage 3 helpers: normalization + deduplication
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.Example.com/path", "example.com"),
        ("https://example.com", "example.com"),
        ("https://sub.example.com/page", "sub.example.com"),
        ("not-a-url", ""),
        ("", ""),
    ],
)
def test_normalize_domain(url, expected):
    assert normalize_domain(url) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.Example.com/path", "example.com"),
        ("Example.com", "example.com"),
        ("example.com/", "example.com"),
        ("", ""),
        (None, ""),
    ],
)
def test_domain_key(value, expected):
    assert domain_key(value) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Home | Acme Corp", "Acme Corp"),
        ("Acme Corp - Official Site", "Acme Corp"),
        ("", ""),
        ("Solo", "Solo"),
    ],
)
def test_clean_company_name(title, expected):
    assert clean_company_name(title) == expected


def test_deduplicate_leads_by_domain_and_prefers_homepage():
    state = {"raw_search_results": SEARCH_RESULTS}

    result = deduplicate_leads(state)
    candidates = result["candidates"]

    assert len(candidates) == 3
    assert candidates[0]["domain"] == "acme-dental.com"
    assert candidates[0]["website"] == "https://acme-dental.com"
    assert candidates[0]["discovered_url"] == "https://www.acme-dental.com/about"
    assert candidates[0]["source_url"] == "https://www.acme-dental.com/about"
    assert candidates[0]["company_name"] == "Acme Dental"
    assert candidates[0]["description"] == "Acme description"
    assert candidates[1]["website"] == "https://brightsmile.io"
    assert "medium.com" not in {lead["domain"] for lead in candidates}


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("acme-dental.com", True),
        ("blog.acme-dental.com", True),
        ("medium.com", False),
        ("something.medium.com", False),
        ("youtube.com", False),
        ("youtu.be", True),
        ("", False),
    ],
)
def test_is_company_domain(domain, expected):
    assert is_company_domain(domain) is expected


# --------------------------------------------------------------------------
# Stage 4 helpers: page extraction
# --------------------------------------------------------------------------


def test_extract_page_text_strips_boilerplate():
    html = """
    <html>
      <head>
        <title>Acme Dental | Home</title>
        <meta name="description" content="Family dental care in Austin." />
        <script>alert(1)</script>
      </head>
      <body>
        <nav>Home Services Contact</nav>
        <h1>Welcome to Acme Dental</h1>
        <p>We offer gentle family dentistry.</p>
        <footer>Copyright</footer>
      </body>
    </html>
    """

    title, meta_description, text = extract_page_text(html)

    assert title == "Acme Dental | Home"
    assert meta_description == "Family dental care in Austin."
    assert "gentle family dentistry" in text
    assert "alert(1)" not in text
    assert "Copyright" not in text


# --------------------------------------------------------------------------
# Stage 6/7 helpers: scoring primitives
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (90, 90),
        (90.7, 90),
        ("85", 85),
        ("85/100", 85),
        (-5, 0),
        (150, 100),
        ("n/a", 0),
        (True, 0),
    ],
)
def test_clamp_score(value, expected):
    assert clamp_score(value) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "A"),
        (80, "A"),
        (79, "B"),
        (60, "B"),
        (59, "C"),
        (0, "C"),
    ],
)
def test_tier_for_score(score, expected):
    assert tier_for_score(score) == expected


@pytest.mark.parametrize(
    ("value", "score", "expected"),
    [
        (None, 85, "A"),
        (None, 74, "B"),
        (None, 40, "C"),
        ("A", 40, "A"),
        ("B+", 40, "B"),
        ("tier A", 40, "A"),
        ("unknown", 74, "B"),
    ],
)
def test_normalize_tier(value, score, expected):
    assert _normalize_tier(value, score) == expected


# --------------------------------------------------------------------------
# Stage 10: validation
# --------------------------------------------------------------------------


def test_validate_leads_drops_invalid_and_unqualified():
    state = {
        "outreach_leads": [
            {
                "domain": "keep.com",
                "company_name": "Keep Co",
                "website": "https://keep.com",
                "qualified": True,
                "score": 91,
                "fit_score": 88,
                "tier": "A",
                "outreach_subject": "Hello",
                "outreach_body": "Body",
            },
            {
                "domain": "unqualified.com",
                "company_name": "No Fit",
                "website": "https://unqualified.com",
                "qualified": False,
                "score": 10,
                "fit_score": 5,
                "tier": "C",
                "outreach_subject": "Hello",
                "outreach_body": "Body",
            },
            {
                "domain": "no-website.com",
                "company_name": "No Site",
                "website": "",
                "qualified": True,
                "score": 70,
                "fit_score": 60,
            },
            {
                "domain": "keep.com",
                "company_name": "Duplicate",
                "website": "https://keep.com",
                "qualified": True,
                "score": 50,
            },
            {
                "domain": "no-outreach.com",
                "company_name": "No Outreach",
                "website": "https://no-outreach.com",
                "qualified": True,
                "score": "85",
                "fit_score": "70",
                "tier": "Tier A",
            },
        ]
    }

    result = validate_leads(state)
    validated = result["validated_leads"]

    assert [lead["domain"] for lead in validated] == ["keep.com", "no-outreach.com"]
    assert validated[1]["score"] == 85
    assert validated[1]["tier"] == "A"
    assert validated[1]["outreach_body"]
    assert len(result["errors"]) == 1
    assert "2 invalid" in result["errors"][0]


# --------------------------------------------------------------------------
# Stage 11: finalize
# --------------------------------------------------------------------------


def test_finalize_leads_sorts_applies_limit_and_builds_funnel():
    state = {
        "limit": 2,
        "search_queries": ["q1", "q2"],
        "raw_search_results": [{"url": "https://a.com"}] * 4,
        "candidates": [{"domain": "a.com"}, {"domain": "b.com"}],
        "researched_leads": [{"domain": "a.com"}, {"domain": "b.com"}],
        "extracted_leads": [{"domain": "a.com"}, {"domain": "b.com"}],
        "qualified_leads": [
            {"domain": "a.com", "qualified": True},
            {"domain": "b.com", "qualified": False},
        ],
        "scored_leads": [{"domain": "a.com"}, {"domain": "b.com"}],
        "opportunity_leads": [
            {"domain": "a.com", "detected": True},
            {"domain": "b.com", "detected": False},
        ],
        "outreach_leads": [
            {"domain": "a.com", "outreach_body": "a"},
            {"domain": "b.com", "outreach_body": "b"},
        ],
        "validated_leads": [
            {
                "domain": "low.com",
                "company_name": "Low",
                "website": "https://low.com",
                "score": 40,
                "fit_score": 30,
            },
            {
                "domain": "high.com",
                "company_name": "High",
                "website": "https://high.com",
                "score": 95,
                "fit_score": 99,
            },
            {
                "domain": "mid.com",
                "company_name": "Mid",
                "website": "https://mid.com",
                "score": 70,
                "fit_score": 50,
            },
        ],
    }

    result = finalize_leads(state)

    assert [lead["domain"] for lead in result["leads"]] == ["high.com", "mid.com"]
    assert result["funnel"]["search_queries"] == 2
    assert result["funnel"]["deduplicated"] == 2
    assert result["funnel"]["icp_qualified"] == 1
    assert result["funnel"]["opportunities"] == 1
    assert result["funnel"]["validated"] == 3
    assert result["funnel"]["final"] == 2


# --------------------------------------------------------------------------
# Graph wiring
# --------------------------------------------------------------------------


def test_pipeline_matches_expected_stage_order():
    assert STAGE_NAMES == EXPECTED_STAGES


def test_graph_imports_and_compiles():
    graph = get_lead_discovery_graph()

    assert graph is get_lead_discovery_graph()
    assert hasattr(graph, "invoke")


def test_full_pipeline_runs_end_to_end(offline_graph):
    result = offline_graph.invoke(base_state())

    leads = result["leads"]

    assert len(leads) == 2
    assert [lead["domain"] for lead in leads] == [
        "acme-dental.com",
        "brightsmile.io",
    ]
    assert leads[0]["score"] == 92
    assert leads[0]["tier"] == "A"
    assert leads[0]["industry"] == "dental clinic"
    assert leads[0]["pain_points"] == ["manual intake"]
    assert leads[0]["outreach_body"]
    assert leads[0]["research_ok"] is True
    assert "careclinic.co" not in {lead["domain"] for lead in leads}

    funnel = result["funnel"]
    assert funnel["deduplicated"] == 3
    assert funnel["research_pool"] == 3
    assert funnel["researched"] == 3
    assert funnel["icp_qualified"] == 2
    assert funnel["validated"] == 2
    assert funnel["final"] == 2


def test_full_pipeline_respects_limit(offline_graph):
    result = offline_graph.invoke(base_state(limit=1))

    assert len(result["leads"]) == 1
    assert result["funnel"]["final"] == 1


def test_pipeline_survives_llm_failure(monkeypatch, offline_graph):
    def broken_invoke(schema, prompt, **kwargs):
        raise RuntimeError("groq down")

    monkeypatch.setattr(nodes, "invoke_structured", broken_invoke)

    result = offline_graph.invoke(base_state())

    assert result["leads"] == []
    assert result["errors"]
    assert any("failed" in error for error in result["errors"])


# --------------------------------------------------------------------------
# HTTP route
# --------------------------------------------------------------------------


def test_app_health_route():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


class FakeGraph:
    def __init__(self, result):
        self.result = result

    def invoke(self, state):
        return self.result


def test_discover_route_reports_funnel_and_status(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import routes
    from app.main import app

    monkeypatch.setattr(
        routes,
        "get_lead_discovery_graph",
        lambda: FakeGraph(
            {
                "leads": [
                    {
                        "domain": "keep.com",
                        "company_name": "Keep Co",
                        "website": "https://keep.com",
                        "score": 91,
                        "tier": "A",
                        "fit_score": 88,
                        "qualified": True,
                        "page_text": "internal only",
                    }
                ],
                "funnel": {"search_queries": 2, "final": 1},
                "errors": ["Website research failed for 1 of 4 candidates."],
            },
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/leads/discover",
        json={
            "industry": "dental clinics",
            "location": "Austin, Texas",
            "ideal_customer": "Independent dental practices with 2-10 dentists",
            "services": ["patient intake automation"],
            "limit": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed_with_errors"
    assert body["total_leads"] == 1
    assert body["funnel"]["final"] == 1
    assert body["errors"]
    assert body["leads"][0]["company_name"] == "Keep Co"
    assert "page_text" not in body["leads"][0]


def test_discover_route_reports_failed_run(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import routes
    from app.main import app

    monkeypatch.setattr(
        routes,
        "get_lead_discovery_graph",
        lambda: FakeGraph({"leads": [], "funnel": {}, "errors": ["boom"]}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/leads/discover",
        json={
            "industry": "dental clinics",
            "location": "Austin, Texas",
            "ideal_customer": "Independent dental practices with 2-10 dentists",
            "services": ["patient intake automation"],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
