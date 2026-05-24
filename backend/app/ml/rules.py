"""Static rule engine.

Each rule is a callable that returns a list of Findings for a piece of source
code. The engine intentionally stays simple: regex for cross-language patterns,
optional AST inspection for Python. ML signals are layered on top in
``analyzer.py``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RuleFinding:
    category: str
    severity: str
    rule_id: str
    line: int | None
    message: str
    suggestion: str | None
    confidence: float = 1.0


RuleFn = Callable[[str, str], list[RuleFinding]]


# ---------- regex-based rules (language-agnostic-ish) ----------

_REGEX_RULES: list[tuple[str, str, str, str, re.Pattern[str], str]] = [
    (
        "SEC-001",
        "security",
        "critical",
        "Possible SQL injection via string concatenation/formatting",
        re.compile(
            r"""(?ix)
            (execute|exec|query)\s*\(\s*
            (
                (f|rf|fr)?["'].*?\{.*?\}.*?["']      # f-string interpolation
              | ["'].*?["']\s*\+                     # "..." + var
              | ["'].*?%s.*?["']\s*%                 # "...%s..." % var
            )
            """
        ),
        "Use parameterised queries (placeholders + bound params) instead of string formatting.",
    ),
    (
        "SEC-001B",
        "security",
        "critical",
        "SQL-shaped string built via concatenation or f-string interpolation",
        re.compile(
            r"""(?ix)
            (
              ["'](SELECT|INSERT|UPDATE|DELETE|MERGE)\b[^"']*["']\s*\+
            | (f|rf|fr)["'](SELECT|INSERT|UPDATE|DELETE|MERGE)\b[^"']*\{.*?\}
            | ["'](SELECT|INSERT|UPDATE|DELETE|MERGE)\b[^"']*%s[^"']*["']\s*%
            )
            """
        ),
        "Construct SQL with placeholders and pass parameters separately to the driver.",
    ),
    (
        "SEC-002",
        "security",
        "critical",
        "Hardcoded credential or API key",
        re.compile(
            r"""(?i)(api[_-]?key|secret|password|passwd|token|access[_-]?key)\s*=\s*['"][A-Za-z0-9_\-]{12,}['"]"""
        ),
        "Load secrets from environment variables or a secrets manager.",
    ),
    (
        "SEC-003",
        "security",
        "error",
        "Weak hash algorithm (MD5/SHA1) used",
        re.compile(r"""(?i)hashlib\.(md5|sha1)\b"""),
        "Use SHA-256 or stronger; for passwords use bcrypt/argon2/scrypt.",
    ),
    (
        "SEC-004",
        "security",
        "error",
        "subprocess called with shell=True",
        re.compile(r"""shell\s*=\s*True"""),
        "Pass argument list and avoid shell=True to prevent command injection.",
    ),
    (
        "SEC-005",
        "security",
        "critical",
        "Dynamic code execution via eval/exec",
        re.compile(r"""\b(eval|exec)\s*\("""),
        "Avoid eval/exec on untrusted input; use ast.literal_eval or explicit dispatch.",
    ),
    (
        "SEC-006",
        "security",
        "warning",
        "Disabled TLS verification",
        re.compile(r"""verify\s*=\s*False"""),
        "Leaving TLS verification off in production exposes traffic to MITM attacks.",
    ),
    (
        "SEC-007",
        "security",
        "error",
        "Deserialising untrusted data with pickle/yaml.load",
        re.compile(r"""(?ix)
            (pickle\.loads?|cPickle\.loads?|yaml\.load\s*\((?!.*Loader\s*=\s*(?:Safe|safe_)))
        """),
        "Use safe loaders (yaml.safe_load, json.loads) or signed payloads.",
    ),
    (
        "BUG-001",
        "bug",
        "warning",
        "Comparison to None with == / !=",
        re.compile(r"""[^=!]==\s*None\b|!=\s*None\b"""),
        "Use `is None` / `is not None` for identity comparison.",
    ),
    (
        "BUG-002",
        "bug",
        "warning",
        "Bare except clause swallows all exceptions",
        re.compile(r"""^\s*except\s*:\s*$""", re.MULTILINE),
        "Catch a specific exception type, or at minimum `except Exception:`.",
    ),
    (
        "ANTI-001",
        "anti-pattern",
        "warning",
        "Wildcard import",
        re.compile(r"""^\s*from\s+[\w.]+\s+import\s+\*""", re.MULTILINE),
        "Import explicit names to keep the namespace predictable.",
    ),
    (
        "ANTI-002",
        "anti-pattern",
        "info",
        "TODO/FIXME marker",
        re.compile(r"""\b(TODO|FIXME|XXX)\b"""),
        "Track follow-up work in your issue tracker, not in a code comment.",
    ),
]


def _regex_rules(code: str, language: str) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for rule_id, category, severity, message, pattern, suggestion in _REGEX_RULES:
        for match in pattern.finditer(code):
            line = code.count("\n", 0, match.start()) + 1
            findings.append(
                RuleFinding(
                    category=category,
                    severity=severity,
                    rule_id=f"GEN-{rule_id}",
                    line=line,
                    message=message,
                    suggestion=suggestion,
                )
            )
    return findings


# ---------- Python AST rules ----------


class _PyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings: list[RuleFinding] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_default(node)
        self._check_function_size(node)
        self._check_nesting(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_default(node)
        self._check_function_size(node)
        self._check_nesting(node)
        self.generic_visit(node)

    def _check_mutable_default(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.findings.append(
                    RuleFinding(
                        category="bug",
                        severity="error",
                        rule_id="PY-BUG-010",
                        line=getattr(default, "lineno", node.lineno),
                        message=f"Mutable default argument in function `{node.name}`",
                        suggestion="Use None as the default and create the container inside the body.",
                    )
                )

    def _check_function_size(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not node.body:
            return
        start = node.lineno
        end = getattr(node.body[-1], "end_lineno", start) or start
        length = end - start + 1
        if length > 60:
            self.findings.append(
                RuleFinding(
                    category="anti-pattern",
                    severity="warning",
                    rule_id="PY-ANTI-020",
                    line=node.lineno,
                    message=f"Function `{node.name}` is {length} lines long (god function)",
                    suggestion="Split into smaller, single-responsibility helpers.",
                )
            )

    def _check_nesting(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        depth = _max_depth(node)
        if depth >= 5:
            self.findings.append(
                RuleFinding(
                    category="anti-pattern",
                    severity="warning",
                    rule_id="PY-ANTI-021",
                    line=node.lineno,
                    message=f"Deep nesting (depth {depth}) in `{node.name}`",
                    suggestion="Flatten with early returns or extracted helpers.",
                )
            )


_NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)


def _max_depth(node: ast.AST, current: int = 0) -> int:
    deepest = current
    for child in ast.iter_child_nodes(node):
        next_depth = current + 1 if isinstance(child, _NESTING_NODES) else current
        deepest = max(deepest, _max_depth(child, next_depth))
    return deepest


def _python_ast_rules(code: str, language: str) -> list[RuleFinding]:
    if language.lower() != "python":
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [
            RuleFinding(
                category="bug",
                severity="error",
                rule_id="PY-SYNTAX",
                line=exc.lineno,
                message=f"Python syntax error: {exc.msg}",
                suggestion=None,
            )
        ]
    visitor = _PyVisitor()
    visitor.visit(tree)
    return visitor.findings


RULE_FUNCTIONS: list[RuleFn] = [_regex_rules, _python_ast_rules]


def run_rules(code: str, language: str) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for fn in RULE_FUNCTIONS:
        findings.extend(fn(code, language))
    return findings
