from fastapi import APIRouter, Depends

from services.analytics_aggregation import common_dietary_constraints, most_recommended_items
from services.auth import require_kitchen_role
from services.firestore_client import get_firestore_client

router = APIRouter()


@router.get("/admin/analytics")
async def get_admin_analytics(uid: str = Depends(require_kitchen_role)):
    """README §9.5 / design-spec.md §4.4, tasks.md 4.4. Anonymized
    aggregate stats only — no student identifiers anywhere in the
    response. Kitchen-role gated, same as every other /admin/* route."""
    db = get_firestore_client()
    return {
        "most_recommended_items": most_recommended_items(db),
        "dietary_constraints": common_dietary_constraints(db),
    }
