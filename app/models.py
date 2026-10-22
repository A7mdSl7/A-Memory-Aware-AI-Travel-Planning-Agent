from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

class Preferences(BaseModel):
    likes_museums: bool | None = None
    cuisine_preferences: list[str] = Field(default_factory=list)
    avoid_early_mornings: bool | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    currency: str = "EUR"
    uncertain: dict[str, str] = Field(default_factory=dict)

class PlanStep(BaseModel):
    id: str
    title: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: str | None = None
    error: str | None = None

class TravelPlan(BaseModel):
    task_id: str
    request: str
    steps: list[PlanStep]

class ToolRecord(BaseModel):
    tool_name: str
    arguments: dict
    status: Literal["running", "completed", "failed"]
    result: dict | None = None
    error: str | None = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
