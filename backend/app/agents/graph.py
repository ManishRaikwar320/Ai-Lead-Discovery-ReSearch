from functools import lru_cache
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .nodes import (
    deduplicate_leads,
    detect_opportunities,
    discover_leads,
    extract_companies,
    finalize_leads,
    generate_outreach,
    generate_search_queries,
    qualify_icp,
    research_websites,
    score_leads,
    validate_leads,
)
from .state import LeadDiscoveryState

# Ordered pipeline: query generation -> ... -> final leads.
PIPELINE: list[tuple[str, Callable]] = [
    ("generate_search_queries", generate_search_queries),
    ("discover_leads", discover_leads),
    ("deduplicate_leads", deduplicate_leads),
    ("research_websites", research_websites),
    ("extract_companies", extract_companies),
    ("qualify_icp", qualify_icp),
    ("score_leads", score_leads),
    ("detect_opportunities", detect_opportunities),
    ("generate_outreach", generate_outreach),
    ("validate_leads", validate_leads),
    ("finalize_leads", finalize_leads),
]

STAGE_NAMES: list[str] = [name for name, _ in PIPELINE]


@lru_cache
def get_lead_discovery_graph():
    graph = StateGraph(LeadDiscoveryState)

    for name, node in PIPELINE:
        graph.add_node(name, node)

    graph.add_edge(START, STAGE_NAMES[0])

    for current, following in zip(STAGE_NAMES, STAGE_NAMES[1:]):
        graph.add_edge(current, following)

    graph.add_edge(STAGE_NAMES[-1], END)

    return graph.compile()
