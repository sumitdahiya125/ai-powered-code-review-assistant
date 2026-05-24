from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..cache import ReviewCache, get_cache
from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(
    response: Response,
    db: Session = Depends(get_db),
    cache: ReviewCache = Depends(get_cache),
) -> dict[str, object]:
    checks: dict[str, object] = {}
    healthy = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    checks["cache"] = "ok" if cache.ping() else "disabled"

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    checks["status"] = "ok" if healthy else "degraded"
    return checks
