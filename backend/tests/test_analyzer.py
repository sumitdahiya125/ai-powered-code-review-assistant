"""Analyzer tests that don't require loading CodeBERT."""

from app.ml.analyzer import Analyzer, CodeBertEncoder, Finding, _merge_findings


class _OfflineEncoder(CodeBertEncoder):
    def __init__(self):
        # Skip parent init; pretend the model is unavailable.
        self.model_name = "noop"
        self.device = "cpu"
        self.max_tokens = 0
        self._available = False
        import threading

        self._lock = threading.Lock()
        self._tokenizer = None
        self._model = None


def test_analyzer_runs_without_model():
    a = Analyzer(_OfflineEncoder())
    findings = a.analyze("x = eval(input())\n", "python")
    assert any(f.rule_id.endswith("SEC-005") for f in findings)


def test_merge_prefers_higher_severity():
    a = Finding("security", "warning", "X-1", 1, "m", "s", 0.5)
    b = Finding("security", "critical", "X-1", 1, "m", "s", 0.9)
    merged = _merge_findings([a, b])
    assert len(merged) == 1
    assert merged[0].severity == "critical"
    assert merged[0].confidence == 0.9


def test_findings_sorted_by_severity_then_line():
    a = Finding("bug", "warning", "X-1", 10, "m", None, 1.0)
    b = Finding("security", "critical", "Y-1", 3, "m", None, 1.0)
    c = Finding("style", "info", "Z-1", 1, "m", None, 1.0)
    merged = _merge_findings([a, b, c])
    assert [f.severity for f in merged] == ["critical", "warning", "info"]
