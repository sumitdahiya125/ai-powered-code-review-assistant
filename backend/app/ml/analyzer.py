"""CodeBERT-backed analyzer.

Composes three signals:

1. **Rules** — regex + AST hits from ``rules.py``.
2. **Embeddings** — ``microsoft/codebert-base`` encodes the submission; cosine
   similarity against the exemplar set produces "looks-like-X" findings.
3. **Composite scoring** — duplicate rule_ids get de-duplicated, severities are
   merged, confidences are folded together.

The CodeBERT model is loaded lazily on first use so the API stays responsive
during boot. Failures to load fall back to rules-only — the service keeps
working, the ML signals just go away.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np

from .exemplars import EXEMPLARS, Exemplar
from .rules import RuleFinding, run_rules

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Finding:
    category: str
    severity: str
    rule_id: str
    line: int | None
    message: str
    suggestion: str | None
    confidence: float


_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}
_RANK_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


class CodeBertEncoder:
    """Lazy-loaded CodeBERT encoder. Thread-safe init."""

    def __init__(self, model_name: str, device: str, max_tokens: int) -> None:
        self.model_name = model_name
        self.device = device
        self.max_tokens = max_tokens
        self._lock = threading.Lock()
        self._tokenizer = None
        self._model = None
        self._available: bool | None = None  # None == not yet attempted

    @property
    def available(self) -> bool:
        if self._available is None:
            self._try_load()
        return bool(self._available)

    def _try_load(self) -> None:
        with self._lock:
            if self._available is not None:
                return
            try:
                import torch  # noqa: F401  — early import to surface failures here
                from transformers import AutoModel, AutoTokenizer

                log.info("loading CodeBERT model %s on %s", self.model_name, self.device)
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModel.from_pretrained(self.model_name)
                self._model.eval()
                self._model.to(self.device)
                self._available = True
                log.info("CodeBERT ready")
            except Exception as exc:
                log.warning("CodeBERT unavailable, falling back to rules-only: %s", exc)
                self._available = False

    def encode(self, text: str) -> np.ndarray | None:
        if not self.available:
            return None
        try:
            import torch

            tokens = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_tokens,
                padding=False,
            ).to(self.device)
            with torch.no_grad():
                outputs = self._model(**tokens)
            # Mean-pool the last hidden state across tokens.
            hidden = outputs.last_hidden_state  # [1, seq, hidden]
            mask = tokens["attention_mask"].unsqueeze(-1).float()
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1)
            pooled = (summed / counts).squeeze(0).cpu().numpy()
            return pooled.astype(np.float32)
        except Exception as exc:
            log.warning("encode failed: %s", exc)
            return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class Analyzer:
    """Composite analyzer (rules + CodeBERT embeddings)."""

    SIMILARITY_THRESHOLD = 0.78

    def __init__(self, encoder: CodeBertEncoder) -> None:
        self.encoder = encoder
        self._exemplar_vecs: list[tuple[Exemplar, np.ndarray]] = []
        self._exemplars_built = False
        self._build_lock = threading.Lock()

    def _ensure_exemplars(self) -> None:
        if self._exemplars_built or not self.encoder.available:
            return
        with self._build_lock:
            if self._exemplars_built:
                return
            built: list[tuple[Exemplar, np.ndarray]] = []
            for ex in EXEMPLARS:
                vec = self.encoder.encode(ex.code)
                if vec is not None:
                    built.append((ex, vec))
            self._exemplar_vecs = built
            self._exemplars_built = True
            log.info("embedded %d exemplars", len(built))

    def analyze(self, code: str, language: str) -> list[Finding]:
        rule_findings = [
            Finding(
                category=f.category,
                severity=f.severity,
                rule_id=f.rule_id,
                line=f.line,
                message=f.message,
                suggestion=f.suggestion,
                confidence=f.confidence,
            )
            for f in run_rules(code, language)
        ]

        ml_findings = self._ml_findings(code)
        return _merge_findings(rule_findings + ml_findings)

    def _ml_findings(self, code: str) -> list[Finding]:
        if not self.encoder.available:
            return []
        self._ensure_exemplars()
        vec = self.encoder.encode(code)
        if vec is None:
            return []
        findings: list[Finding] = []
        for exemplar, ev in self._exemplar_vecs:
            sim = _cosine(vec, ev)
            if sim >= self.SIMILARITY_THRESHOLD:
                findings.append(
                    Finding(
                        category=exemplar.category,
                        severity=exemplar.severity,
                        rule_id=exemplar.rule_id,
                        line=None,
                        message=f"{exemplar.message} (similarity {sim:.2f})",
                        suggestion=exemplar.suggestion,
                        confidence=round(sim, 3),
                    )
                )
        return findings


def _merge_findings(findings: list[Finding]) -> list[Finding]:
    """De-duplicate by (rule_id, line), keep the highest severity / confidence."""
    bucket: dict[tuple[str, int | None], Finding] = {}
    for f in findings:
        key = (f.rule_id, f.line)
        existing = bucket.get(key)
        if existing is None:
            bucket[key] = f
            continue
        higher_sev = max(_SEVERITY_RANK[existing.severity], _SEVERITY_RANK[f.severity])
        higher_conf = max(existing.confidence, f.confidence)
        bucket[key] = Finding(
            category=existing.category,
            severity=_RANK_SEVERITY[higher_sev],
            rule_id=existing.rule_id,
            line=existing.line,
            message=existing.message,
            suggestion=existing.suggestion or f.suggestion,
            confidence=higher_conf,
        )
    # Stable order: severity desc, then line asc.
    return sorted(
        bucket.values(),
        key=lambda x: (-_SEVERITY_RANK[x.severity], x.line if x.line is not None else 10**9),
    )


_analyzer: Analyzer | None = None


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is None:
        from ..config import get_settings

        s = get_settings()
        encoder = CodeBertEncoder(s.model_name, s.model_device, s.model_max_tokens)
        _analyzer = Analyzer(encoder)
    return _analyzer
