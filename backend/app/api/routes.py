import logging

from fastapi import APIRouter, HTTPException

from app.agents.graph import get_lead_discovery_graph

from .schemas import (
    LeadDiscoveryRequest,
    LeadDiscoveryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/leads",
    tags=["Lead Discovery"],
)


@router.post(
    "/discover",
    response_model=LeadDiscoveryResponse,
)
def discover_leads(
    request: LeadDiscoveryRequest,
):
    try:
        graph = get_lead_discovery_graph()

        initial_state = {
            "industry": request.industry,
            "location": request.location,
            "ideal_customer": request.ideal_customer,
            "services": request.services,
            "company_size": request.company_size,
            "limit": request.limit,
            "errors": [],
        }

        result = graph.invoke(initial_state)

        errors = result.get("errors") or []
        leads = result.get("leads") or []
        funnel = result.get("funnel") or {}

        if errors:
            logger.warning(
                "Lead discovery completed with errors: %s",
                errors,
            )

        if errors and not leads:
            status = "failed"
        elif errors:
            status = "completed_with_errors"
        else:
            status = "completed"

        return LeadDiscoveryResponse(
            status=status,
            total_leads=len(leads),
            funnel=funnel,
            errors=errors,
            leads=leads,
        )

    except Exception:
        logger.exception("Lead discovery failed")

        raise HTTPException(
            status_code=500,
            detail="Lead discovery failed. Check server logs for details.",
        ) from None
