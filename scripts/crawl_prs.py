"""Crawl merged PRs from the source repo and dump as JSONL.

Two-phase:
  1. `list_phase`: one call to `gh pr list` for bulk metadata.
  2. `enrich_phase`: per-PR `gh pr view` for files, closing issues, merge commit.

Output: raw/prs.jsonl — one JSON object per PR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from .gh import GhError, pr_list, pr_view

LIST_FIELDS = [
    "number",
    "title",
    "author",
    "body",
    "labels",
    "mergedAt",
    "createdAt",
    "url",
    "baseRefName",
    "headRefName",
    "mergeCommit",
    "additions",
    "deletions",
    "changedFiles",
    "state",
]

ENRICH_FIELDS = [
    "number",
    "files",
    "closingIssuesReferences",
    "mergeCommit",
    "mergedAt",
    "reviewDecision",
]


def _read_existing(path: Path) -> dict[int, dict]:
    """Resume support: load already-enriched PRs by number."""
    if not path.exists():
        return {}
    out: dict[int, dict] = {}
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "number" in obj:
                    out[obj["number"]] = obj
            except json.JSONDecodeError:
                continue
    return out


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def crawl(
    repo: str,
    output: Path,
    *,
    limit: int = 1000,
    resume: bool = True,
    console: Console | None = None,
) -> int:
    """Crawl merged PRs. Returns number of PRs written."""
    console = console or Console()

    console.log(f"[bold]Phase 1[/bold] — listing merged PRs for {repo} (limit={limit})")
    listing = pr_list(repo, state="merged", limit=limit, fields=LIST_FIELDS)
    console.log(f"  got {len(listing)} PRs")

    existing = _read_existing(output) if resume else {}
    if existing:
        console.log(f"  resuming — {len(existing)} already enriched, skipping")

    console.log(f"[bold]Phase 2[/bold] — enriching per-PR details")
    merged: dict[int, dict] = dict(existing)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("enrich", total=len(listing))
        for pr in listing:
            number = pr["number"]
            progress.update(task, advance=1, description=f"PR #{number}")
            if number in merged:
                continue
            try:
                detail = pr_view(repo, number, fields=ENRICH_FIELDS)
            except GhError as e:
                console.log(f"  [yellow]skip PR #{number}[/yellow]: {e}")
                continue
            # Merge list-phase metadata with enrich-phase details.
            combined = {**pr, **detail, "repo": repo}
            merged[number] = combined
            # Incremental dump — cheap insurance against crashes mid-run.
            _write_jsonl(output, sorted(merged.values(), key=lambda r: -r["number"]))

    console.log(f"[green]wrote {len(merged)} PRs → {output}[/green]")
    return len(merged)
