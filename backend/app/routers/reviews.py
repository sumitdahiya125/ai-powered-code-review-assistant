from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..cache import ReviewCache, get_cache
from ..config import get_settings
from ..database import get_db
from ..ml.analyzer import Analyzer, get_analyzer
from ..schemas import (
    FindingOut,
    ReviewListItem,
    ReviewOut,
    ReviewRequest,
    ReviewSummary,
    StatsOut,
)
from ..services.review_service import ReviewService

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _service(
    db: Session = Depends(get_db),
    cache: ReviewCache = Depends(get_cache),
    analyzer: Analyzer = Depends(get_analyzer),
) -> ReviewService:
    return ReviewService(db, cache, analyzer)


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_review(
    payload: ReviewRequest, service: ReviewService = Depends(_service)
) -> ReviewOut:
    settings = get_settings()
    if len(payload.code.encode("utf-8")) > settings.max_code_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"code exceeds limit of {settings.max_code_bytes} bytes",
        )

    review = service.create_review(payload.language, payload.code)
    return _to_review_out(review)


@router.get("/stats", response_model=StatsOut)
def stats(service: ReviewService = Depends(_service)) -> StatsOut:
    return StatsOut(**service.stats())


@router.get("", response_model=list[ReviewListItem])
def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ReviewService = Depends(_service),
) -> list[ReviewListItem]:
    reviews = service.list_reviews(limit=limit, offset=offset)
    return [
        ReviewListItem(
            id=r.id,
            language=r.language,
            summary=ReviewSummary(**(r.summary or {})),
            latency_ms=r.latency_ms,
            cached=r.cached,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: uuid.UUID, service: ReviewService = Depends(_service)) -> ReviewOut:
    review = service.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return _to_review_out(review)


def _to_review_out(review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        language=review.language,
        summary=ReviewSummary(**(review.summary or {})),
        findings=[FindingOut.model_validate(f) for f in review.findings],
        cached=review.cached,
        latency_ms=review.latency_ms,
        created_at=review.created_at,
    )
