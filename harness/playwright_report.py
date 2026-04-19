"""Parse Playwright `--reporter=json` output into stable test-id → outcome maps.

Playwright nodeid scheme we adopt (stable across PR diffs — no line/col):
    "<spec_file_path>::<title-path-joined-by-' > '>"

  Example: "tests/login.spec.ts::Inputs are visible, empty and editable"

Status mapping (Playwright → SWE-bench convention):
  expected   → passed
  unexpected → failed
  flaky      → failed     (treat flaky as failure for fairness; no retry yet)
  skipped    → skipped
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

Outcome = Literal["passed", "failed", "skipped"]


def _spec_outcome(spec: dict) -> Outcome:
    """Reduce a spec's per-project test results to one outcome (worst wins)."""
    statuses = [t.get("status", "") for t in spec.get("tests", [])]
    if not statuses:
        return "failed"  # spec with no run is suspicious — treat as failure
    if any(s == "unexpected" for s in statuses):
        return "failed"
    if any(s == "flaky" for s in statuses):
        return "failed"
    if all(s == "skipped" for s in statuses):
        return "skipped"
    if all(s == "expected" for s in statuses):
        return "passed"
    return "failed"


def _walk(suite: dict, title_path: list[str], file: str, out: dict[str, Outcome]) -> None:
    cur = title_path + ([suite["title"]] if suite.get("title") else [])
    for spec in suite.get("specs", []):
        spec_title = spec.get("title", "")
        nodeid_titles = " > ".join([*cur, spec_title]).strip(" > ")
        nodeid = f"{file}::{nodeid_titles}"
        out[nodeid] = _spec_outcome(spec)
    for sub in suite.get("suites", []):
        _walk(sub, cur, file, out)


def parse(json_path: Path) -> dict[str, Outcome]:
    """Return spec-nodeid → outcome map.

    Top-level suites in Playwright's reporter carry the file path under both
    `file` and `title`; inner suites only carry `title` (a `describe` block).
    """
    data = json.loads(json_path.read_text())
    out: dict[str, Outcome] = {}
    for suite in data.get("suites", []):
        file = suite.get("file") or suite.get("title", "")
        # Don't include the file itself as a title segment.
        for spec in suite.get("specs", []):
            spec_title = spec.get("title", "")
            out[f"{file}::{spec_title}"] = _spec_outcome(spec)
        for sub in suite.get("suites", []):
            _walk(sub, [], file, out)
    return out


def passing(outcomes: dict[str, Outcome]) -> set[str]:
    return {nid for nid, o in outcomes.items() if o == "passed"}


def failing(outcomes: dict[str, Outcome]) -> set[str]:
    return {nid for nid, o in outcomes.items() if o == "failed"}
