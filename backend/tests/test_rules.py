from app.ml.rules import run_rules


def _ids(findings):
    return [f.rule_id for f in findings]


def test_sql_injection_concatenation_flagged():
    code = 'q = "SELECT * FROM u WHERE name=" + name\ndb.execute(q)'
    rule_hits = _ids(run_rules(code, "python"))
    assert any("SEC-001" in r for r in rule_hits)


def test_hardcoded_secret_flagged():
    code = 'API_KEY = "sk-abcdef1234567890"'
    assert any("SEC-002" in r for r in _ids(run_rules(code, "python")))


def test_eval_flagged():
    code = "x = eval(user_input)"
    assert any("SEC-005" in r for r in _ids(run_rules(code, "python")))


def test_bare_except_flagged():
    code = "try:\n    do()\nexcept:\n    pass\n"
    assert any("BUG-002" in r for r in _ids(run_rules(code, "python")))


def test_compare_to_none_flagged():
    code = "if x == None:\n    pass\n"
    assert any("BUG-001" in r for r in _ids(run_rules(code, "python")))


def test_mutable_default_argument_flagged():
    code = "def f(x, items=[]):\n    items.append(x)\n    return items\n"
    assert any("PY-BUG-010" in r for r in _ids(run_rules(code, "python")))


def test_wildcard_import_flagged():
    code = "from os import *\n"
    assert any("ANTI-001" in r for r in _ids(run_rules(code, "python")))


def test_clean_code_has_no_findings():
    code = (
        "def add(a: int, b: int) -> int:\n"
        '    """Add two numbers."""\n'
        "    return a + b\n"
    )
    assert run_rules(code, "python") == []


def test_python_syntax_error_surfaced():
    code = "def broken(:\n"
    hits = run_rules(code, "python")
    assert any(f.rule_id == "PY-SYNTAX" for f in hits)
