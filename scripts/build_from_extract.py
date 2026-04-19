"""Convert batch-extract results into schema-shaped task instances.

Input:  raw/extract_report.jsonl  (batch_extract output)
        raw/prs.jsonl              (PR metadata for problem_statement etc)
        per-PR  <work_root>/<instance_id>/out/summary.json
        per-PR  <work_root>/<instance_id>/test_patch.diff
        shared repo checkout (defaults to <work_root>/_shared_repo)

Output: tasks/instances.jsonl  (one instance per usable PR)

Only PRs with status in {exact, fallback} are converted by default — those are
the ones with a non-empty FAIL_TO_PASS signal, which is the minimum the
schema requires.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from harness import git_ops


def _sha256_of_file_at_commit(repo_dir: Path, commit: str, rel_path: str) -> str | None:
    """Return sha256 of `<commit>:<rel_path>` content; None if file absent."""
    try:
        content = git_ops.show_file(repo_dir, commit, rel_path)
    except git_ops.GitError:
        return None
    return "sha256:" + hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _derive_stack_domain(diff_text: str) -> str:
    """Backend / frontend / fullstack from the non-test patch's `+++ b/` paths."""
    paths = re.findall(r"^\+\+\+ b/(.+?)\s*$", diff_text, re.MULTILINE)
    has_be = any(p.startswith("backend/") for p in paths)
    has_fe = any(p.startswith("frontend/") for p in paths)
    if has_be and has_fe:
        return "fullstack"
    if has_be:
        return "backend_only"
    if has_fe:
        return "frontend_only"
    return "fullstack"


def _contamination_tier(created_at: str, cutoff: str = "2026-01-01") -> str:
    return "public" if (created_at[:10] < cutoff) else "held_out"


def _problem_statement(pr_meta: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (problem_statement, notes)."""
    notes: list[str] = []
    closing = pr_meta.get("closingIssuesReferences") or []
    if closing and isinstance(closing[0], dict):
        body = (closing[0].get("body") or "").strip()
        if body:
            return body, notes

    body = (pr_meta.get("body") or "").strip()
    if body:
        notes.append("problem_statement sourced from PR description (no linked issue) — review for solution leakage.")
        return body, notes

    notes.append("problem_statement is a placeholder — both PR body and closing issue were empty. Curator must rewrite.")
    return f"<<TODO:problem_statement — PR #{pr_meta.get('number')} has empty body and no closing issue>>", notes


def build_instance_from_extract(
    *,
    pr_meta: dict[str, Any],
    summary: dict[str, Any],
    test_patch: str,
    repo_dir: Path,
    repo: str,
    cutoff: str = "2026-01-01",
) -> dict[str, Any]:
    base_commit = summary["base_commit"]
    head_commit = summary["head_commit"]
    number = summary.get("instance_id", "").rsplit("-", 1)[-1]

    # Compute the non-test reference patch from base..head.
    patch = git_ops.diff(
        repo_dir, base_commit, head_commit,
        paths=["."],
        exclude=["*test*", "*.spec.ts", "*.spec.tsx", "*.test.ts", "*.test.tsx"],
    )

    test_patch_backend = git_ops.diff(
        repo_dir, base_commit, head_commit,
        paths=["backend/tests/**", "backend/app/tests/**"],
    )
    test_patch_frontend = git_ops.diff(
        repo_dir, base_commit, head_commit,
        paths=["frontend/tests/**", "frontend/**/*.spec.ts", "frontend/**/*.spec.tsx",
               "frontend/**/*.test.ts", "frontend/**/*.test.tsx"],
    )

    owner, name = repo.split("/", 1)
    instance_id = f"{owner}__{name}-{number}"

    notes: list[str] = []
    notes.extend(summary.get("notes") or [])
    if summary.get("fallback_used"):
        notes.append(f"FAIL_TO_PASS recovered via {summary['fallback_used']}")

    problem, problem_notes = _problem_statement(pr_meta)
    notes.extend(problem_notes)

    fail_to_pass_be = list(summary.get("fail_to_pass") or [])
    pass_to_pass_be = list(summary.get("pass_to_pass") or [])

    created_at = pr_meta.get("mergedAt") or pr_meta.get("createdAt") or ""

    instance: dict[str, Any] = {
        "instance_id": instance_id,
        "repo": repo,
        "pr_number": int(number),
        "pr_url": pr_meta.get("url", ""),
        "pr_title": pr_meta.get("title", ""),
        "pr_author": (pr_meta.get("author") or {}).get("login", ""),
        "pr_labels": [l.get("name") for l in (pr_meta.get("labels") or []) if isinstance(l, dict)],
        "base_commit": base_commit,
        "head_commit": head_commit,
        "problem_statement": problem,
        "patch": patch,
        "test_patch": test_patch or (test_patch_backend + test_patch_frontend),
        "test_patch_backend": test_patch_backend,
        "test_patch_frontend": test_patch_frontend,
        "fail_to_pass": {"backend": fail_to_pass_be, "frontend": []},
        "pass_to_pass": {"backend": pass_to_pass_be, "frontend": []},
        "stack_domain": _derive_stack_domain(patch),
        "environment": {
            "python_version": "3.10",
            "node_version": "20",
            "uv_lock_sha": _sha256_of_file_at_commit(repo_dir, base_commit, "uv.lock") or "",
            "bun_lock_sha": _sha256_of_file_at_commit(repo_dir, base_commit, "bun.lock") or "",
            "docker_compose_sha": _sha256_of_file_at_commit(repo_dir, base_commit, "compose.yml") or "",
        },
        "created_at": created_at,
        "contamination_tier": _contamination_tier(created_at, cutoff=cutoff) if created_at else "public",
        "notes": "\n".join(notes) if notes else None,
        "schema_version": "0.1",
    }
    # Strip None values that the schema doesn't allow.
    return {k: v for k, v in instance.items() if v is not None}


def build_from_extract(
    *,
    report_path: Path,
    prs_path: Path,
    repo_dir: Path,
    work_root: Path,
    output: Path,
    statuses: set[str],
    repo: str = "fastapi/full-stack-fastapi-template",
    cutoff: str = "2026-01-01",
) -> tuple[int, int]:
    """Returns (n_built, n_skipped)."""
    # Index PRs by number.
    prs_by_number: dict[int, dict] = {}
    with prs_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            prs_by_number[row["number"]] = row

    rows = []
    with report_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    output.parent.mkdir(parents=True, exist_ok=True)
    n_built = 0
    n_skipped = 0
    with output.open("w") as out_f:
        for r in rows:
            if r.get("status") not in statuses:
                n_skipped += 1
                continue
            pr_number = r["pr"]
            pr_meta = prs_by_number.get(pr_number)
            if pr_meta is None:
                n_skipped += 1
                continue
            instance_id = r["instance_id"]
            summary_path = work_root / instance_id / "out" / "summary.json"
            test_patch_path = work_root / instance_id / "test_patch.diff"
            if not summary_path.exists() or not test_patch_path.exists():
                n_skipped += 1
                continue
            summary = json.loads(summary_path.read_text())
            test_patch = test_patch_path.read_text()

            instance = build_instance_from_extract(
                pr_meta=pr_meta,
                summary=summary,
                test_patch=test_patch,
                repo_dir=repo_dir,
                repo=repo,
                cutoff=cutoff,
            )
            out_f.write(json.dumps(instance, ensure_ascii=False, sort_keys=True))
            out_f.write("\n")
            n_built += 1
    return n_built, n_skipped
