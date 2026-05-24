"""Curated anti-pattern reference snippets.

Each entry is embedded once at startup; review submissions are compared against
these via cosine similarity to surface patterns the regex/AST rules miss.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Exemplar:
    rule_id: str
    category: str
    severity: str
    message: str
    suggestion: str
    code: str


EXEMPLARS: list[Exemplar] = [
    Exemplar(
        rule_id="ML-SIM-001",
        category="security",
        severity="error",
        message="Pattern resembles unsanitised user input flowing to a system call",
        suggestion="Validate, allow-list, or escape inputs before passing them to subprocess/os.system.",
        code=(
            "import os\n"
            "name = request.args.get('name')\n"
            "os.system('echo ' + name)\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-002",
        category="security",
        severity="critical",
        message="Pattern resembles a path-traversal vulnerability",
        suggestion="Resolve and validate paths with pathlib + allow-list of base dirs.",
        code=(
            "def read(path):\n"
            "    with open('/var/data/' + path) as fh:\n"
            "        return fh.read()\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-003",
        category="bug",
        severity="warning",
        message="Pattern resembles an off-by-one loop boundary",
        suggestion="Verify range endpoints and use len(seq) carefully.",
        code=(
            "for i in range(0, len(items) - 1):\n"
            "    process(items[i + 1])\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-004",
        category="anti-pattern",
        severity="warning",
        message="Pattern resembles a god function juggling unrelated concerns",
        suggestion="Decompose into smaller functions per concern.",
        code=(
            "def handle(req):\n"
            "    auth = check_auth(req)\n"
            "    log_audit(req)\n"
            "    data = parse_payload(req)\n"
            "    saved = save_to_db(data)\n"
            "    send_email(saved)\n"
            "    push_metric(saved)\n"
            "    return render_template('ok.html', s=saved)\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-005",
        category="bug",
        severity="error",
        message="Pattern resembles a race condition on shared mutable state",
        suggestion="Guard shared state with a lock or use atomic operations.",
        code=(
            "counter = 0\n"
            "def incr():\n"
            "    global counter\n"
            "    counter = counter + 1\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-006",
        category="anti-pattern",
        severity="info",
        message="Pattern resembles deeply nested conditional logic",
        suggestion="Use guard clauses or polymorphism to flatten branches.",
        code=(
            "def f(x):\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                if d:\n"
            "                    return x\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-007",
        category="security",
        severity="error",
        message="Pattern resembles deserialising untrusted data with pickle/yaml.load",
        suggestion="Use safe loaders (yaml.safe_load) or validated formats like JSON.",
        code=(
            "import pickle\n"
            "obj = pickle.loads(payload)\n"
        ),
    ),
    Exemplar(
        rule_id="ML-SIM-008",
        category="bug",
        severity="warning",
        message="Pattern resembles a resource not closed deterministically",
        suggestion="Use a context manager (`with` block) or try/finally.",
        code=(
            "fh = open(path)\n"
            "data = fh.read()\n"
            "return data\n"
        ),
    ),
]
