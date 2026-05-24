from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["info", "warning", "error", "critical"]
Category = Literal["security", "bug", "anti-pattern", "style", "ml-signal"]


class ReviewRequest(BaseModel):
    language: str = Field(default="python", description="Source language identifier")
    code: str = Field(min_length=1, description="Code snippet to review")


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: Category
    severity: Severity
    rule_id: str
    line: int | None = None
    message: str
    suggestion: str | None = None
    confidence: float = 1.0


class ReviewSummary(BaseModel):
    info: int = 0
    warning: int = 0
    error: int = 0
    critical: int = 0


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    language: str
    summary: ReviewSummary
    findings: list[FindingOut]
    cached: bool = False
    latency_ms: int = 0
    created_at: datetime | None = None


class ReviewListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    language: str
    summary: ReviewSummary
    latency_ms: int
    cached: bool
    created_at: datetime


class StatsOut(BaseModel):
    total_reviews: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    avg_latency_ms: float
    cache_hit_rate: float
