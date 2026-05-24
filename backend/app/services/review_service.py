from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..cache import ReviewCache
from ..ml.analyzer import Analyzer, Finding
from ..models import Finding as FindingModel
from ..models import Review

log = logging.getLogger(__name__)


class ReviewService:
    def __init__(self, db: Session, cache: ReviewCache, analyzer: Analyzer) -> None:
        self.db = db
        self.cache = cache
        self.analyzer = analyzer

    # ---------- public API ----------

    def create_review(self, language: str, code: str) -> Review:
        code_hash = _hash(language, code)
        cache_key = f"review:{code_hash}"

        cached = self.cache.get(cache_key)
        start = time.perf_counter()

        if cached:
            findings = [Finding(**f) for f in cached["findings"]]
            review = self._persist(language, code, code_hash, findings, cached=True, latency_ms=int(cached.get("latency_ms", 0)))
            return review

        findings = self.analyzer.analyze(code, language)
        latency_ms = int((time.perf_counter() - start) * 1000)

        review = self._persist(language, code, code_hash, findings, cached=False, latency_ms=latency_ms)

        self.cache.set(
            cache_key,
            {
                "findings": [_finding_dict(f) for f in findings],
                "latency_ms": latency_ms,
            },
        )
        return review

    def get_review(self, review_id: uuid.UUID) -> Review | None:
        stmt = (
            select(Review)
            .options(selectinload(Review.findings))
            .where(Review.id == review_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_reviews(self, limit: int = 50, offset: int = 0) -> list[Review]:
        stmt = (
            select(Review)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def stats(self) -> dict:
        total = self.db.execute(select(func.count(Review.id))).scalar_one()
        cached_count = self.db.execute(
            select(func.count(Review.id)).where(Review.cached.is_(True))
        ).scalar_one()
        avg_latency = (
            self.db.execute(select(func.coalesce(func.avg(Review.latency_ms), 0))).scalar_one()
            or 0
        )

        by_sev = dict(
            self.db.execute(
                select(FindingModel.severity, func.count(FindingModel.id))
                .group_by(FindingModel.severity)
            ).all()
        )
        by_cat = dict(
            self.db.execute(
                select(FindingModel.category, func.count(FindingModel.id))
                .group_by(FindingModel.category)
            ).all()
        )

        return {
            "total_reviews": int(total or 0),
            "by_severity": {k: int(v) for k, v in by_sev.items()},
            "by_category": {k: int(v) for k, v in by_cat.items()},
            "avg_latency_ms": float(avg_latency or 0.0),
            "cache_hit_rate": (float(cached_count) / float(total)) if total else 0.0,
        }

    # ---------- helpers ----------

    def _persist(
        self,
        language: str,
        code: str,
        code_hash: str,
        findings: list[Finding],
        cached: bool,
        latency_ms: int,
    ) -> Review:
        summary = _summarise(findings)
        review = Review(
            language=language,
            code=code,
            code_hash=code_hash,
            summary=summary,
            cached=cached,
            latency_ms=latency_ms,
            findings=[
                FindingModel(
                    category=f.category,
                    severity=f.severity,
                    rule_id=f.rule_id,
                    line=f.line,
                    message=f.message,
                    suggestion=f.suggestion,
                    confidence=f.confidence,
                )
                for f in findings
            ],
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review


def _hash(language: str, code: str) -> str:
    h = hashlib.sha256()
    h.update(language.encode("utf-8"))
    h.update(b"\0")
    h.update(code.encode("utf-8"))
    return h.hexdigest()


def _summarise(findings: list[Finding]) -> dict[str, int]:
    counts = Counter(f.severity for f in findings)
    return {sev: int(counts.get(sev, 0)) for sev in ("info", "warning", "error", "critical")}


def _finding_dict(f: Finding) -> dict:
    return {
        "category": f.category,
        "severity": f.severity,
        "rule_id": f.rule_id,
        "line": f.line,
        "message": f.message,
        "suggestion": f.suggestion,
        "confidence": f.confidence,
    }
