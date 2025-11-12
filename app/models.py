"""app.models
=================
Mini-README: Contains SQLAlchemy ORM model definitions for the Nichifier platform,
including users, niches, subscriptions, newsletters, and AI configuration metadata.
Relationships and helper enumerations define the domain model used throughout the app.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserRole(str, enum.Enum):
    """Enumerated user roles within the platform."""

    ADMIN = "admin"
    NICHE_ADMIN = "niche_admin"
    SUBSCRIBER = "subscriber"


class User(Base):
    """Represents an authenticated user with role-based access."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.SUBSCRIBER)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    niches: Mapped[List["Niche"]] = relationship(back_populates="owner")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user")


class Niche(Base):
    """Represents an industry niche curated by a niche admin."""

    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    short_description: Mapped[str] = mapped_column(String(512), nullable=False)
    detailed_description: Mapped[str] = mapped_column(Text, nullable=True)
    splash_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    newsletter_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    report_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    voice_instructions: Mapped[str] = mapped_column(Text, default="")
    style_guide: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    owner: Mapped[Optional[User]] = relationship(back_populates="niches")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="niche")
    newsletter_issues: Mapped[List["NewsletterIssue"]] = relationship(back_populates="niche")
    report_issues: Mapped[List["ReportIssue"]] = relationship(back_populates="niche")


class Subscription(Base):
    """Stores relationships between users and niches with subscription metadata."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"))
    wants_newsletter: Mapped[bool] = mapped_column(Boolean, default=True)
    wants_report: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="subscriptions")
    niche: Mapped[Niche] = relationship(back_populates="subscriptions")


class NewsletterIssue(Base):
    """Represents an AI-assisted newsletter issue for a niche."""

    __tablename__ = "newsletter_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    niche: Mapped[Niche] = relationship(back_populates="newsletter_issues")
    articles: Mapped[List["NewsArticle"]] = relationship(back_populates="newsletter_issue")


class ReportIssue(Base):
    """Represents a deeper longform report for a niche."""

    __tablename__ = "report_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    cadence: Mapped[str] = mapped_column(String(50))
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    niche: Mapped[Niche] = relationship(back_populates="report_issues")


class NewsArticle(Base):
    """Stores raw news article metadata aggregated overnight for newsletters."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    newsletter_issue_id: Mapped[int] = mapped_column(ForeignKey("newsletter_issues.id"))
    source: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    summary: Mapped[str] = mapped_column(Text)

    newsletter_issue: Mapped[NewsletterIssue] = relationship(back_populates="articles")
