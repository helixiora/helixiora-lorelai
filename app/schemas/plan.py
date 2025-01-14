"""Plan schemas."""

from datetime import datetime, date
from pydantic import BaseModel


class PlanSchema(BaseModel):
    """Schema for a plan."""

    plan_id: int
    plan_name: str
    description: str | None
    message_limit_daily: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the plan schema."""

        from_attributes = True


class UserPlanSchema(BaseModel):
    """Schema for a user plan."""

    user_plan_id: int
    user_id: int
    plan_id: int
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the user plan schema."""

        from_attributes = True
