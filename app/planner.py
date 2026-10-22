import re, uuid
from .models import TravelPlan, PlanStep

STEP_DEFS=[("load_preferences","Load saved preferences"),("search_flights","Search flight options"),("search_hotels","Search hotel options"),("find_attractions","Find attractions"),("search_restaurants","Find restaurants"),("check_weather","Check illustrative weather"),("build_itinerary","Build personalized itinerary")]
def create_plan(request: str) -> TravelPlan:
    """Create request-specific tasks with deterministic dependency order."""
    steps=[PlanStep(id=i,title=t) for i,t in STEP_DEFS]
    if not re.search(r'\b(flight|fly|air|airport|travel from|from .+ to)\b',request,re.I): steps=[s for s in steps if s.id!='search_flights']
    return TravelPlan(task_id=str(uuid.uuid4()),request=request,steps=steps)
def update_step(plan: TravelPlan, step_id: str, status: str, result=None, error=None):
    step=next(s for s in plan.steps if s.id==step_id)
    step.status=status; step.result=result; step.error=error
    return plan
