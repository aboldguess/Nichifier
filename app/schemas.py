"""app.schemas
=================
Mini-README: Defines Pydantic models used for request validation and response
serialization throughout the API. Schemas mirror ORM models while constraining the
fields exposed to clients. Monetisation schemas are included so admin and billing
APIs can safely expose configuration data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .models import (
    CreatorSubscriptionStatus,
    SubscriptionStatus,
    UserRole,
)


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class UserRead(BaseModel):
    """Representation of a user returned to clients."""

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_premium: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response body."""

    access_token: str
    token_type: str = "bearer"


class NicheCreate(BaseModel):
    """Payload for creating a new niche."""

    name: str
    short_description: str
    detailed_description: Optional[str] = None
    splash_image_url: Optional[str] = None
    newsletter_price: float = 0
    report_price: float = 0
    currency_code: str = "GBP"
    newsletter_cadence: str = "monthly"
    report_cadence: str = "monthly"
    voice_instructions: Optional[str] = None
    style_guide: Optional[str] = None


class NicheRead(BaseModel):
    """Public representation of a niche."""

    id: int
    name: str
    short_description: str
    detailed_description: Optional[str]
    splash_image_url: Optional[str]
    newsletter_price: float
    report_price: float
    currency_code: str
    newsletter_cadence: str
    report_cadence: str
    voice_instructions: Optional[str]
    style_guide: Optional[str]

    class Config:
        from_attributes = True


class NicheUpdate(BaseModel):
    """Payload for updating an existing niche with optional fields."""

    name: Optional[str] = None
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    splash_image_url: Optional[str] = None
    newsletter_price: Optional[float] = None
    report_price: Optional[float] = None
    currency_code: Optional[str] = None
    newsletter_cadence: Optional[str] = None
    report_cadence: Optional[str] = None
    voice_instructions: Optional[str] = None
    style_guide: Optional[str] = None


class SubscriptionCreate(BaseModel):
    """Payload to create or update a subscription."""

    niche_id: int
    wants_newsletter: bool = True
    wants_report: bool = False


class SubscriptionRead(BaseModel):
    """Public representation of a subscription."""

    id: int
    niche_id: int
    wants_newsletter: bool
    wants_report: bool
    started_at: datetime
    expires_at: Optional[datetime]
    status: SubscriptionStatus
    billing_cadence: str
    gross_amount: Decimal
    platform_fee_amount: Decimal
    creator_payout_amount: Decimal
    currency_code: str

    class Config:
        from_attributes = True


class BillingProfileRead(BaseModel):
    """Expose billing profile identifiers for support tooling."""

    stripe_customer_id: Optional[str]
    default_payment_method: Optional[str]

    class Config:
        from_attributes = True


class CreatorPlanRead(BaseModel):
    """Describe a curator plan for dashboards and admin editors."""

    id: int
    slug: str
    display_name: str
    description: Optional[str]
    monthly_fee: Decimal
    currency_code: str
    max_niches: int
    feature_summary: str
    platform_fee_discount_percent: Decimal

    class Config:
        from_attributes = True


class CreatorSubscriptionRead(BaseModel):
    """Surface creator subscription data to the dashboard UI."""

    id: int
    plan: CreatorPlanRead
    status: CreatorSubscriptionStatus
    started_at: datetime
    current_period_end: Optional[datetime]

    class Config:
        from_attributes = True


class PlatformMonetisationSettingsUpdate(BaseModel):
    """Payload for updating the singleton platform monetisation configuration."""

    platform_fee_percent: Decimal
    minimum_platform_fee: Decimal
    currency_code: str
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
