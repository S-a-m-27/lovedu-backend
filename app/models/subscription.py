from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class PlanType(str, Enum):
    free = "free"
    basic = "basic"
    pro = "pro"

class PlanDetails(BaseModel):
    plan: PlanType
    tokens_limit: int
    pdf_uploads_per_day: int
    images_per_day: int
    price_per_month: Optional[float] = None

class UserUsageResponse(BaseModel):
    user_id: str
    usage_date: str
    tokens_used: int
    pdf_uploads: int
    images_uploaded: int

class UpgradePlanRequest(BaseModel):
    plan: PlanType

class UserPlanResponse(BaseModel):
    plan: PlanType
    tokens_limit: int
    pdf_uploads_per_day: int
    images_per_day: int
    tokens_used_today: int
    pdf_uploads_today: int
    images_uploaded_today: int
    tokens_remaining: int
    price_per_month: Optional[float] = None

class SubscriptionResponse(BaseModel):
    plan: PlanType
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None

