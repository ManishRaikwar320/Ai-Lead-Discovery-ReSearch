"""Pipeline nodes: 11 stages from query generation to final leads."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal
from urllib.parse import urlparse

from app.config import get_settings
from app.tools.fetch_page import fetch_pages
from app.tools.tavily_search import search_web

from .llm import invoke_structured
from .schemas import (
    CompanyExtractionBatch,
    ICPVerdictBatch,
    LeadScoreBatch,
    OpportunityBatch,
    OutreachBatch,
    SearchQueries,
    clamp_score,
    tier_for_score,
)
from .state import LeadDiscoveryState

logger = logging.getLogger(__name__)

ContextMode = Literal["page", "brief"]

MAX_LIST_ITEMS = 8

# Domains that host content, social or directory pages instead of companies.
NON_COMPANY_DOMAINS = {
    "amazon.com",
    "bbb.org",
    "craigslist.org",
    "facebook.com",
    "g2.com",
    "github.com",
    "glassdoor.com",
    "indeed.com",
    "instagram.com",
    "linkedin.com",
    "medium.com",
    "pinterest.com",
    "quora.com",
    "reddit.com",
    "substack.com",
    "trustpilot.com",
    "tiktok.com",
    "twitter.com",
    "wikipedia.org",
    "x.com",
    "yelp.com",
    "youtube.com",
}


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _with_errors(
    state: LeadDiscoveryState,
    update: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    if errors:
        update["errors"] = list(state.get("errors") or []) + errors

    return update


def normalize_domain(url: str) -> str:
    try:
        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def domain_key(value: Any) -> str:
    """Normalize a domain or URL coming back from an LLM into a match key."""
    text = str(value or "").strip().lower().rstrip("/")

    if not text:
        return ""

    if "://" in text:
        return normalize_domain(text)

    if "/" in text:
        return normalize_domain(f"https://{text}")

    return text


def is_company_domain(domain: str) -> bool:
    """Reject domains that host content platforms instead of businesses."""
    if not domain:
        return False

    for blocked in NON_COMPANY_DOMAINS:
        if domain == blocked or domain.endswith(f".{blocked}"):
            return False

    return True


BOILERPLATE_TITLE_PARTS = {
    "home",
    "official",
    "official site",
    "site",
    "contact",
    "contact us",
    "about",
    "about us",
    "services",
    "blog",
    "welcome",
    "page",
}


def clean_company_name(title: str) -> str:
    if not title:
        return ""

    normalized = (
        title.replace("–", " | ")
        .replace("—", " | ")
        .replace(" - ", " | ")
    )
    parts = [
        chunk.strip()
        for chunk in normalized.split(" | ")
        if chunk.strip()
    ]

    if not parts:
        return ""

    filtered = [
        part
        for part in parts
        if part.lower() not in BOILERPLATE_TITLE_PARTS
    ]

    if filtered:
        return max(filtered, key=len)

    return parts[0]


def _target_brief(state: LeadDiscoveryState) -> str:
    return "\n".join(
        [
            f"- Industry: {state.get('industry')}",
            f"- Location: {state.get('location')}",
            f"- Ideal customer profile: {state.get('ideal_customer')}",
            f"- Services you sell: {', '.join(state.get('services') or [])}",
            f"- Preferred company size: {state.get('company_size') or 'Any'}",
        ]
    )


def _lead_blocks(
    leads: list[dict[str, Any]],
    *,
    context: ContextMode | None = None,
) -> str:
    """Render leads as numbered blocks for an LLM prompt."""
    settings = get_settings()
    blocks: list[str] = []

    for index, lead in enumerate(leads, 1):
        lines = [
            f"#{index}",
            f"domain: {lead.get('domain')}",
            f"website: {lead.get('website')}",
            f"search title: {lead.get('title') or 'n/a'}",
            f"search snippet: {lead.get('description') or 'n/a'}",
        ]

        if context == "page":
            content = (
                lead.get("page_text")
                or lead.get("meta_description")
                or lead.get("description")
                or ""
            )
            lines.append(f"page content: {content[:settings.llm_context_chars] or 'n/a'}")

        elif context == "brief":
            summary = (
                lead.get("summary")
                or lead.get("opportunity_summary")
                or lead.get("meta_description")
                or lead.get("description")
                or ""
            )
            lines.append(f"company summary: {summary[:settings.llm_brief_chars] or 'n/a'}")

            if lead.get("recommended_service"):
                lines.append(f"recommended service: {lead['recommended_service']}")

            if lead.get("pain_points"):
                lines.append(f"pain points: {', '.join(lead['pain_points'])}")

            if lead.get("buying_signals"):
                lines.append(f"buying signals: {', '.join(lead['buying_signals'])}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks) or "No leads available."


def _batch_rules(example: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Rules:",
            "- Respond with JSON only.",
            "- Return exactly one entry per domain listed above.",
            "- Reuse the domain string exactly as given; never invent domains.",
            "- Use null for facts you cannot confirm. Never guess.",
            f"Example shape:\n{json.dumps(example, indent=2)}",
        ]
    )


def _invoke_batch(
    stage_name: str,
    schema: type,
    field: str,
    prompt: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run one structured LLM call and return its entries as dicts."""
    try:
        result = invoke_structured(schema, prompt)
    except Exception as exc:
        logger.warning("%s failed: %s", stage_name, exc)
        return [], [f"{stage_name} failed: {exc}"]

    entries = getattr(result, field, None) or []

    return [entry.model_dump() for entry in entries], []


def _run_stage(
    *,
    stage_name: str,
    schema: type,
    field: str,
    leads: list[dict[str, Any]],
    header: str,
    rules: str,
    context: ContextMode = "brief",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run a batched LLM stage, splitting leads into small chunks.

    Chunks keep every request well below provider token limits.
    """
    settings = get_settings()
    size = max(1, settings.llm_batch_size)

    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    for start in range(0, len(leads), size):
        chunk = leads[start : start + size]

        prompt = (
            f"{header}\n{_lead_blocks(chunk, context=context)}\n\n{rules}"
        )

        chunk_entries, chunk_errors = _invoke_batch(
            stage_name,
            schema,
            field,
            prompt,
        )

        entries.extend(chunk_entries)
        errors.extend(chunk_errors)

        if chunk_errors:
            break

    return entries, errors


def _apply_updates(
    leads: list[dict[str, Any]],
    updates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for lead in leads:
        entry = dict(lead)
        patch = updates.get(lead.get("domain", ""))

        if patch:
            entry.update(patch)

        merged.append(entry)

    return merged


def _with_defaults(
    leads: list[dict[str, Any]],
    defaults: dict[str, Any],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for lead in leads:
        entry = dict(lead)

        for key, value in defaults.items():
            entry.setdefault(key, value)

        merged.append(entry)

    return merged


def _normalize_tier(value: Any, score: int) -> str:
    for character in str(value or "").upper():
        if character in {"A", "B", "C"}:
            return character

    return tier_for_score(score)


def _string_list(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []

    cleaned = [
        str(item).strip()
        for item in items
        if isinstance(item, str) and item.strip()
    ]

    return cleaned[:MAX_LIST_ITEMS]


def _opt_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


# --------------------------------------------------------------------------
# Stage 1 - Query generation
# --------------------------------------------------------------------------


def generate_search_queries(state: LeadDiscoveryState) -> dict:
    prompt = f"""
You are a B2B sales research assistant.

Generate web search queries that will surface the websites of the
target businesses themselves - the companies that would buy from us.

{_target_brief(state)}

Generate between 3 and 5 highly specific search queries.

Respond with JSON only, using this schema:
{{"queries": ["query 1", "query 2", "query 3"]}}

Rules:
- Put the target location in every query.
- Phrase queries the way a buyer would search for such a business,
  for example "{state.get('industry')} in {state.get('location')}".
- Prefer queries where the businesses' own websites are likely to rank.
- Do not search for individuals or private personal information.
- Never target news, blogs, press releases, directories, job boards,
  listicles, or vendors/agencies selling to this industry.
"""

    try:
        result = invoke_structured(SearchQueries, prompt)
    except Exception as exc:
        logger.warning("Query generation failed: %s", exc)

        return _with_errors(
            state,
            {"search_queries": []},
            [f"Query generation failed: {exc}"],
        )

    queries = [
        query.strip()
        for query in result.queries
        if isinstance(query, str) and query.strip()
    ]

    return {"search_queries": queries[:5]}


# --------------------------------------------------------------------------
# Stage 2 - Tavily discovery
# --------------------------------------------------------------------------


def discover_leads(state: LeadDiscoveryState) -> dict:
    settings = get_settings()

    queries = state.get("search_queries") or []

    if not queries:
        return _with_errors(
            state,
            {"raw_search_results": []},
            ["No search queries were generated."],
        )

    all_results: list[dict] = []
    errors: list[str] = []

    for query in queries:
        try:
            results = search_web(
                query=query,
                max_results=settings.max_search_results,
            )
            all_results.extend(results)
        except Exception as exc:
            errors.append(f"Search failed for '{query}': {exc}")

    return _with_errors(
        state,
        {"raw_search_results": all_results},
        errors,
    )


# --------------------------------------------------------------------------
# Stage 3 - Deduplication
# --------------------------------------------------------------------------


def deduplicate_leads(state: LeadDiscoveryState) -> dict:
    unique: dict[str, dict] = {}

    for result in state.get("raw_search_results", []):
        url = result.get("url", "")
        domain = normalize_domain(url)

        if not domain or not is_company_domain(domain):
            continue

        if domain not in unique:
            title = result.get("title", "")

            unique[domain] = {
                "domain": domain,
                "company_name": clean_company_name(title) or domain,
                "website": f"https://{domain}",
                "discovered_url": url,
                "title": title or None,
                "description": _opt_str(result.get("content")),
                "source_url": url,
            }

            continue

        lead = unique[domain]

        if not lead.get("description"):
            lead["description"] = _opt_str(result.get("content"))

    candidates = list(unique.values())
    errors: list[str] = []

    if not state.get("raw_search_results"):
        errors.append("Search returned no results.")
    elif not candidates:
        errors.append("No company websites found in search results.")

    return _with_errors(state, {"candidates": candidates}, errors)


# --------------------------------------------------------------------------
# Stage 4 - Website research
# --------------------------------------------------------------------------


def research_websites(state: LeadDiscoveryState) -> dict:
    candidates = state.get("candidates") or []

    if not candidates:
        return {"researched_leads": [], "research_pool": 0}

    settings = get_settings()

    limit = state.get("limit") or 10
    pool = candidates[: max(settings.max_research_leads, limit)]

    urls: list[str] = []

    for lead in pool:
        homepage = f"https://{lead['domain']}"
        urls.append(homepage)

        discovered = lead.get("discovered_url")

        if discovered and discovered != homepage:
            urls.append(discovered)

    pages = fetch_pages(
        urls,
        concurrency=settings.research_concurrency,
        timeout=settings.research_timeout,
        max_chars=settings.research_max_chars,
    )

    researched: list[dict[str, Any]] = []
    failed = 0

    for lead in pool:
        homepage = f"https://{lead['domain']}"
        discovered = lead.get("discovered_url") or homepage

        page = pages.get(homepage) or {}
        research_url = homepage

        if not page.get("ok"):
            fallback = pages.get(discovered) or {}

            if fallback.get("ok"):
                page = fallback
                research_url = discovered

        entry = dict(lead)
        entry["website"] = research_url
        entry["page_title"] = _opt_str(page.get("title"))
        entry["meta_description"] = _opt_str(page.get("meta_description"))
        entry["page_text"] = page.get("text") or ""
        entry["research_ok"] = bool(page.get("ok"))

        if not entry["research_ok"]:
            failed += 1

        researched.append(entry)

    errors: list[str] = []

    if failed:
        errors.append(
            f"Website research failed for {failed} of {len(pool)} candidates.",
        )

    return _with_errors(
        state,
        {"researched_leads": researched, "research_pool": len(pool)},
        errors,
    )


# --------------------------------------------------------------------------
# Stage 5 - Company extraction
# --------------------------------------------------------------------------


def extract_companies(state: LeadDiscoveryState) -> dict:
    leads = state.get("researched_leads") or []

    if not leads:
        return {"extracted_leads": []}

    header = f"""You are a B2B sales research analyst.

Extract structured company facts for every business listed below.

Target you are researching for:
{_target_brief(state)}

Businesses:
"""

    example = {
        "companies": [
            {
                "domain": "example.com",
                "company_name": "Acme Dental",
                "industry": "dental clinic",
                "location": "Austin, Texas",
                "company_size": "small business",
                "summary": "One sentence describing what the company does.",
                "technologies": ["WordPress", "Calendly"],
                "signals": ["hiring", "online booking"],
            }
        ]
    }

    entries, errors = _run_stage(
        stage_name="Company extraction",
        schema=CompanyExtractionBatch,
        field="companies",
        leads=leads,
        header=header,
        rules=_batch_rules(example),
        context="page",
    )

    updates: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = domain_key(entry.get("domain"))

        if key:
            updates[key] = {
                "company_name": _opt_str(entry.get("company_name")),
                "industry": _opt_str(entry.get("industry")),
                "location": _opt_str(entry.get("location")),
                "company_size": _opt_str(entry.get("company_size")),
                "summary": _opt_str(entry.get("summary")),
                "technologies": _string_list(entry.get("technologies")),
                "signals": _string_list(entry.get("signals")),
            }

    extracted = _apply_updates(leads, updates)

    for lead in extracted:
        if not lead.get("company_name"):
            lead["company_name"] = (
                clean_company_name(lead.get("title") or "")
                or lead.get("domain")
            )

    return _with_errors(state, {"extracted_leads": extracted}, errors)


# --------------------------------------------------------------------------
# Stage 6 - ICP qualification
# --------------------------------------------------------------------------


def qualify_icp(state: LeadDiscoveryState) -> dict:
    leads = state.get("extracted_leads") or []

    if not leads:
        return {"qualified_leads": []}

    header = f"""You are a B2B sales qualification analyst.

Decide whether each company matches the ideal customer profile below.

Ideal customer profile:
{_target_brief(state)}

For every company decide:
- qualified: true only when the company clearly fits the profile, false otherwise
- fit_score: 0 (terrible fit) to 100 (perfect fit)
- reason: one short sentence explaining the decision
- Reject news articles, blog posts, directories and job boards.

Companies:
"""

    example = {
        "verdicts": [
            {
                "domain": "example.com",
                "qualified": True,
                "fit_score": 85,
                "reason": "Matches size, industry and location exactly.",
            }
        ]
    }

    entries, errors = _run_stage(
        stage_name="ICP qualification",
        schema=ICPVerdictBatch,
        field="verdicts",
        leads=leads,
        header=header,
        rules=_batch_rules(example),
        context="brief",
    )

    updates: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = domain_key(entry.get("domain"))

        if key:
            updates[key] = {
                "qualified": bool(entry.get("qualified", True)),
                "fit_score": clamp_score(entry.get("fit_score", 50)),
                "qualification_reason": _opt_str(entry.get("reason")),
            }

    defaults = {
        "qualified": True,
        "fit_score": 50,
        "qualification_reason": None,
    }

    return _with_errors(
        state,
        {"qualified_leads": _apply_updates(_with_defaults(leads, defaults), updates)},
        errors,
    )


# --------------------------------------------------------------------------
# Stage 7 - Lead scoring
# --------------------------------------------------------------------------


def score_leads(state: LeadDiscoveryState) -> dict:
    all_leads = state.get("qualified_leads") or []

    # Only leads that passed ICP qualification are worth scoring.
    leads = [
        lead
        for lead in all_leads
        if lead.get("qualified") is not False
    ]

    if not leads:
        return {"scored_leads": []}

    header = f"""You are a B2B lead scoring analyst.

Score how likely each qualified company to buy the services offered.

Offer context:
{_target_brief(state)}

Score each company from 0 to 100 using:
- ICP fit (company size, industry, location match)
- Evidence of need for the services offered
- Quality and completeness of the website
- Growth or buying signals

Tier must be "A" (score >= 80), "B" (60-79) or "C" (< 60).

Companies:
"""

    example = {
        "scores": [
            {
                "domain": "example.com",
                "score": 82,
                "tier": "A",
                "rationale": "Perfect ICP fit with clear need for intake automation.",
            }
        ]
    }

    entries, errors = _run_stage(
        stage_name="Lead scoring",
        schema=LeadScoreBatch,
        field="scores",
        leads=leads,
        header=header,
        rules=_batch_rules(example),
        context="brief",
    )

    updates: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = domain_key(entry.get("domain"))

        if key:
            score = clamp_score(entry.get("score", 50))

            updates[key] = {
                "score": score,
                "tier": _normalize_tier(entry.get("tier"), score),
                "score_rationale": _opt_str(entry.get("rationale")),
            }

    defaults = {
        "score": 50,
        "tier": None,
        "score_rationale": None,
    }

    scored = _with_defaults(leads, defaults)

    for lead in scored:
        if not lead.get("tier"):
            lead["tier"] = tier_for_score(clamp_score(lead.get("score", 50)))

    return _with_errors(
        state,
        {"scored_leads": _apply_updates(scored, updates)},
        errors,
    )


# --------------------------------------------------------------------------
# Stage 8 - Opportunity detection
# --------------------------------------------------------------------------


def detect_opportunities(state: LeadDiscoveryState) -> dict:
    leads = state.get("scored_leads") or []

    if not leads:
        return {"opportunity_leads": []}

    services = ", ".join(state.get("services") or [])

    header = f"""You are a B2B opportunity analyst.

For each company, identify whether there is a concrete, reachable
opportunity to sell the services listed below.

Services being sold:
{services}

Offer context:
{_target_brief(state)}

For every company return:
- detected: true when a real opportunity exists, false otherwise
- pain_points: up to 3 problems the company likely has
- buying_signals: up to 3 signals observed for the company
- recommended_service: the single best matching service from the list above
- summary: one sentence describing the opportunity

Companies:
"""

    example = {
        "opportunities": [
            {
                "domain": "example.com",
                "detected": True,
                "pain_points": ["manual patient intake"],
                "buying_signals": ["online booking form"],
                "recommended_service": "patient intake automation",
                "summary": "Legacy intake process conflicts with booking volume.",
            }
        ]
    }

    entries, errors = _run_stage(
        stage_name="Opportunity detection",
        schema=OpportunityBatch,
        field="opportunities",
        leads=leads,
        header=header,
        rules=_batch_rules(example),
        context="brief",
    )

    updates: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = domain_key(entry.get("domain"))

        if key:
            updates[key] = {
                "detected": bool(entry.get("detected", False)),
                "pain_points": _string_list(entry.get("pain_points")),
                "buying_signals": _string_list(entry.get("buying_signals")),
                "recommended_service": _opt_str(entry.get("recommended_service")),
                "opportunity_summary": _opt_str(entry.get("summary")),
            }

    defaults = {
        "detected": False,
        "pain_points": [],
        "buying_signals": [],
        "recommended_service": None,
        "opportunity_summary": None,
    }

    return _with_errors(
        state,
        {
            "opportunity_leads": _apply_updates(
                _with_defaults(leads, defaults),
                updates,
            )
        },
        errors,
    )


# --------------------------------------------------------------------------
# Stage 9 - Outreach generation
# --------------------------------------------------------------------------


def _fallback_outreach(
    lead: dict[str, Any],
    state: LeadDiscoveryState,
) -> dict[str, Any]:
    company = lead.get("company_name") or lead.get("domain") or "there"
    services = state.get("services") or ["our services"]
    hook = (
        lead.get("summary")
        or lead.get("opportunity_summary")
        or lead.get("meta_description")
        or lead.get("description")
        or ""
    ).strip()

    subject = f"Idea for {company}"

    body = (
        f"Hi {company} team,\n\n"
        f"I came across {lead.get('website')} while researching "
        f"{state.get('industry')} businesses in {state.get('location')}.\n"
    )

    if hook:
        body += f"\n{hook}\n"

    body += (
        f"\nWe help companies like yours with {services[0]}.\n\n"
        "Would you be open to a 15-minute call this week to see whether "
        "it is worth exploring?\n\n"
        "Best regards"
    )

    return {
        "outreach_subject": subject,
        "outreach_body": body,
        "personalization_hook": _opt_str(hook),
    }


def generate_outreach(state: LeadDiscoveryState) -> dict:
    leads = state.get("opportunity_leads") or []

    if not leads:
        return {"outreach_leads": []}

    services = state.get("services") or []

    header = f"""You are a B2B outbound copywriter.

Write one short, personalized outreach message per company.

Sender context:
{_target_brief(state)}

Rules:
- Reference something specific from the company itself.
- Keep the body under 140 words, plain text, no markdown, no placeholders.
- Offer one concrete service from this list: {", ".join(services)}
- Do not invent facts that are not in the input.
- No fake statistics, no hype, no emojis.

Companies:
"""

    example = {
        "messages": [
            {
                "domain": "example.com",
                "subject": "Reducing manual intake at Acme Dental",
                "body": "Hi Acme Dental team,\n\n...",
                "personalization_hook": "Noticed your online booking form.",
            }
        ]
    }

    entries, errors = _run_stage(
        stage_name="Outreach generation",
        schema=OutreachBatch,
        field="messages",
        leads=leads,
        header=header,
        rules=_batch_rules(example),
        context="brief",
    )

    updates: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = domain_key(entry.get("domain"))

        if key:
            updates[key] = {
                "outreach_subject": _opt_str(entry.get("subject")),
                "outreach_body": _opt_str(entry.get("body")),
                "personalization_hook": _opt_str(entry.get("personalization_hook")),
            }

    outreach = _apply_updates(leads, updates)

    for lead in outreach:
        if not lead.get("outreach_body"):
            lead.update(_fallback_outreach(lead, state))

    return _with_errors(state, {"outreach_leads": outreach}, errors)


# --------------------------------------------------------------------------
# Stage 10 - Validation
# --------------------------------------------------------------------------


def validate_leads(state: LeadDiscoveryState) -> dict:
    leads = state.get("outreach_leads") or []

    validated: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    rejected = 0
    unqualified = 0

    for lead in leads:
        entry = dict(lead)
        domain = entry.get("domain") or domain_key(entry.get("website"))

        if not domain or domain in seen:
            rejected += 1
            continue

        seen.add(domain)

        website = str(entry.get("website") or "")

        if not website.startswith(("http://", "https://")):
            rejected += 1
            continue

        entry["domain"] = domain

        if not str(entry.get("company_name") or "").strip():
            entry["company_name"] = domain

        if entry.get("qualified") is False:
            unqualified += 1
            continue

        entry["score"] = clamp_score(entry.get("score", 50))
        entry["fit_score"] = clamp_score(entry.get("fit_score", 50))
        entry["tier"] = _normalize_tier(entry.get("tier"), entry["score"])

        if not entry.get("outreach_subject") or not entry.get("outreach_body"):
            entry.update(_fallback_outreach(entry, state))

        validated.append(entry)

    if rejected:
        errors.append(f"Dropped {rejected} invalid or duplicate leads.")

    if unqualified:
        logger.debug(
            "Dropped %s leads that failed ICP qualification.",
            unqualified,
        )

    return _with_errors(state, {"validated_leads": validated}, errors)


# --------------------------------------------------------------------------
# Stage 11 - Final leads
# --------------------------------------------------------------------------


def finalize_leads(state: LeadDiscoveryState) -> dict:
    leads = list(state.get("validated_leads") or [])

    leads.sort(
        key=lambda lead: (
            clamp_score(lead.get("score", 0)),
            clamp_score(lead.get("fit_score", 0)),
        ),
        reverse=True,
    )

    limit = state.get("limit") or 10
    final = leads[:limit]

    qualified_leads = state.get("qualified_leads") or []
    opportunity_leads = state.get("opportunity_leads") or []
    outreach_leads = state.get("outreach_leads") or []

    funnel = {
        "search_queries": len(state.get("search_queries") or []),
        "search_results": len(state.get("raw_search_results") or []),
        "deduplicated": len(state.get("candidates") or []),
        "research_pool": state.get("research_pool") or 0,
        "researched": len(state.get("researched_leads") or []),
        "extracted": len(state.get("extracted_leads") or []),
        "icp_qualified": sum(
            1 for lead in qualified_leads if lead.get("qualified") is not False
        ),
        "scored": len(state.get("scored_leads") or []),
        "opportunities": sum(
            1 for lead in opportunity_leads if lead.get("detected")
        ),
        "outreach_ready": sum(
            1 for lead in outreach_leads if lead.get("outreach_body")
        ),
        "validated": len(state.get("validated_leads") or []),
        "final": len(final),
    }

    return {
        "leads": final,
        "funnel": funnel,
    }
