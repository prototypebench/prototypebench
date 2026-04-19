"""Skeleton builder: turn a crawled PR into a task instance draft.

Auto-fills every field we can derive from the PR alone. Leaves `<<TODO:...>>`
placeholders for fields that require running tests or human judgment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TODO_PATCH = "<<TODO:patch — compute via `git diff base..head -- . ':!*test*' ':!*spec.ts'`>>"
TODO_TEST_PATCH = "<<TODO:test_patch — compute via `git diff base..head -- '*test*' '*spec.ts'`>>"
TODO_FAIL_BE = "<<TODO:fill after running pytest base→head>>"
TODO_FAIL_FE = "<<TODO:fill after running Playwright base→head>>"


def _derive_stack_domain(file_paths: list[str]) -> str:
    """Infer stack_domain from paths of changed files (test files excluded from count)."""
    non_test = [p for p in file_paths if not _is_test_path(p)]
    has_be = any(p.startswith("backend/") for p in non_test)
    has_fe = any(p.startswith("frontend/") for p in non_test)
    if has_be and has_fe:
        return "fullstack"
    if has_be:
        return "backend_only"
    if has_fe:
        return "frontend_only"
    return "fullstack"


_TEST_PATTERNS = (
    re.compile(r"^backend/.*tests?/.*\.py$"),
    re.compile(r"^backend/.*test_.*\.py$"),
    re.compile(r"^frontend/tests/.*\.(spec|test)\.[tj]sx?$"),
    re.compile(r"^frontend/.*\.(spec|test)\.[tj]sx?$"),
)


def _is_test_path(path: str) -> bool:
    return any(p.match(path) for p in _TEST_PATTERNS)


def _contamination_tier(created_at: str, cutoff: str = "2026-01-01") -> str:
    return "public" if created_at < cutoff else "held_out"


def build_instance(pr: dict[str, Any], *, cutoff: str = "2026-01-01") -> dict[str, Any]:
    """Produce a schema-shaped dict from a single crawled PR row.

    Fields that cannot be derived without test execution are left as `<<TODO:...>>`
    strings; the curator must replace them before `pbench validate` accepts the row.
    """
    repo = pr["repo"]
    owner, name = repo.split("/", 1)
    number = pr["number"]
    merge_commit = (pr.get("mergeCommit") or {}).get("oid") or ""

    # The PR's "base" on GitHub = merge base; the branch's baseRefOid is not exposed
    # via `gh pr view`. Curator must confirm with `git merge-base`.
    base_commit_placeholder = (
        "<<TODO:base_commit — git merge-base master " + (merge_commit or "<head>") + ">>"
    )

    files = [f.get("path", "") for f in (pr.get("files") or [])]
    stack = _derive_stack_domain(files)

    closing = pr.get("closingIssuesReferences") or []
    first_issue_body = ""
    if closing and isinstance(closing[0], dict):
        first_issue_body = closing[0].get("body") or ""

    problem = first_issue_body or (pr.get("body") or "")
    problem = problem.strip() or f"<<TODO:problem_statement — PR has empty body and no closing issue>>"

    created_at = pr.get("mergedAt") or pr.get("createdAt") or ""

    instance: dict[str, Any] = {
        "instance_id": f"{owner}__{name}-{number}",
        "repo": repo,
        "pr_number": number,
        "pr_url": pr.get("url", ""),
        "pr_title": pr.get("title", ""),
        "pr_author": (pr.get("author") or {}).get("login", ""),
        "pr_labels": [l.get("name") for l in (pr.get("labels") or []) if isinstance(l, dict)],
        "base_commit": base_commit_placeholder,
        "head_commit": merge_commit or "<<TODO:head_commit>>",
        "problem_statement": problem,
        "patch": TODO_PATCH,
        "test_patch": TODO_TEST_PATCH,
        "fail_to_pass": {"backend": [TODO_FAIL_BE], "frontend": [TODO_FAIL_FE]},
        "pass_to_pass": {"backend": [], "frontend": []},
        "stack_domain": stack,
        "environment": {
            "python_version": "3.11",
            "node_version": "20",
            "uv_lock_sha": "<<TODO:shasum backend/uv.lock at base>>",
            "bun_lock_sha": "<<TODO:shasum frontend/bun.lockb at base>>",
            "docker_compose_sha": "<<TODO:shasum docker-compose.yml at base>>",
        },
        "created_at": created_at,
        "contamination_tier": _contamination_tier(created_at, cutoff=cutoff) if created_at else "public",
        "notes": "<<TODO:curator notes — why this PR, caveats>>",
        "schema_version": "0.1",
    }
    return instance


def build_from_candidates(
    candidates_path: Path, drafts_path: Path, *, top_n: int | None = None
) -> int:
    """Write a drafts JSONL from the top-N candidates."""
    rows = []
    with candidates_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if top_n:
        rows = rows[:top_n]
    drafts_path.parent.mkdir(parents=True, exist_ok=True)
    with drafts_path.open("w") as f:
        for r in rows:
            instance = build_instance(r["pr"])
            f.write(json.dumps(instance, ensure_ascii=False, sort_keys=True))
            f.write("\n")
    return len(rows)
