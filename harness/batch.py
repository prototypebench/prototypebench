"""Batch-extract FAIL_TO_PASS / PASS_TO_PASS over a candidate pool.

Sequential, single-shared-checkout: clone the source repo once into
`<work_root>/_shared_repo/` and reuse it for every PR. extract.py's clean +
checkout cycle resets state between runs.

Output:
  <work_root>/<instance_id>/out/summary.json   (per-PR detail)
  <report_path>                                  (one JSON per PR, batch view)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from . import extract as ex
from . import git_ops


@dataclass
class BatchRow:
    pr: int
    instance_id: str
    title: str
    f2p: int
    p2p: int
    fallback: str | None
    status: str          # "exact" | "fallback" | "test_only" | "no_signal" | "error"
    error: str | None
    duration_s: float


def _classify(result: ex.ExtractResult) -> str:
    if result.error:
        return "error"
    if result.fallback_used:
        return "fallback"
    if result.fail_to_pass:
        return "exact"
    if result.pass_to_pass:
        return "test_only"
    return "no_signal"


def _scope_pytest(test_patch: str) -> list[str]:
    hits = re.findall(
        r"^\+\+\+ b/(backend/(?:tests|app/tests)/[^\s]+)",
        test_patch,
        re.MULTILINE,
    )
    return sorted({p.replace("backend/", "", 1) for p in hits})


def batch_extract(
    *,
    candidates_path: Path,
    work_root: Path,
    report_path: Path,
    repo_url: str,
    top_n: int | None,
    mode: str,
    console: Console | None = None,
) -> list[BatchRow]:
    console = console or Console()

    rows = []
    with candidates_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if top_n:
        rows = rows[:top_n]

    work_root.mkdir(parents=True, exist_ok=True)
    shared_repo = work_root / "_shared_repo"
    if not shared_repo.exists():
        console.log(f"first-time clone of shared repo → {shared_repo}")
        git_ops.clone(repo_url, shared_repo)

    results: list[BatchRow] = []
    quiet_console = Console(quiet=True)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("batch-extract", total=len(rows))
        for r in rows:
            pr = r["pr"]
            number = pr["number"]
            instance_id = f"fastapi__full-stack-fastapi-template-{number}"
            progress.update(task, advance=1, description=f"PR #{number}")
            t0 = time.monotonic()

            head_commit = ((pr.get("mergeCommit") or {}).get("oid")) or ""
            if not head_commit:
                results.append(BatchRow(
                    pr=number, instance_id=instance_id,
                    title=pr.get("title", ""), f2p=0, p2p=0, fallback=None,
                    status="error", error="no mergeCommit.oid",
                    duration_s=time.monotonic() - t0,
                ))
                continue

            try:
                git_ops.clean(shared_repo)
                git_ops.checkout(shared_repo, head_commit)
                base_commit = git_ops.rev_parse(shared_repo, f"{head_commit}^")
                test_patch = git_ops.diff(
                    shared_repo,
                    base_commit,
                    head_commit,
                    paths=["*test*", "*.spec.ts", "*.spec.tsx", "*.test.ts", "*.test.tsx"],
                )
            except git_ops.GitError as e:
                results.append(BatchRow(
                    pr=number, instance_id=instance_id,
                    title=pr.get("title", ""), f2p=0, p2p=0, fallback=None,
                    status="error", error=f"git: {e}",
                    duration_s=time.monotonic() - t0,
                ))
                continue

            work_dir = work_root / instance_id
            work_dir.mkdir(exist_ok=True)
            (work_dir / "test_patch.diff").write_text(test_patch)

            scoped = _scope_pytest(test_patch) if test_patch else None

            spec = ex.ExtractSpec(
                instance_id=instance_id,
                repo_url=repo_url,
                base_commit=base_commit,
                head_commit=head_commit,
                test_patch=test_patch or None,
                pytest_args=scoped or None,
            )
            try:
                result = ex.extract(
                    spec,
                    work_root=work_dir,
                    mode=mode,
                    console=quiet_console,
                    repo_dir=shared_repo,
                )
            except Exception as e:  # noqa: BLE001 — never let one PR kill the batch
                results.append(BatchRow(
                    pr=number, instance_id=instance_id,
                    title=pr.get("title", ""), f2p=0, p2p=0, fallback=None,
                    status="error", error=f"crashed: {type(e).__name__}: {e}",
                    duration_s=time.monotonic() - t0,
                ))
                continue

            results.append(BatchRow(
                pr=number,
                instance_id=instance_id,
                title=pr.get("title", ""),
                f2p=len(result.fail_to_pass),
                p2p=len(result.pass_to_pass),
                fallback=result.fallback_used,
                status=_classify(result),
                error=result.error,
                duration_s=time.monotonic() - t0,
            ))

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w") as f:
        for row in results:
            f.write(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True))
            f.write("\n")
    return results


def render_summary(results: list[BatchRow], console: Console) -> None:
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    total = len(results)
    usable = by_status.get("exact", 0) + by_status.get("fallback", 0)

    table = Table(title=f"Batch extract — {total} PRs ({usable} usable, {usable * 100 // max(total, 1)}%)")
    table.add_column("PR", justify="right")
    table.add_column("status")
    table.add_column("F2P", justify="right")
    table.add_column("P2P", justify="right")
    table.add_column("dur(s)", justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("error/note", overflow="fold")

    status_color = {
        "exact": "green", "fallback": "yellow", "test_only": "cyan",
        "no_signal": "white", "error": "red",
    }
    for r in sorted(results, key=lambda x: (x.status != "exact", x.status != "fallback", -x.f2p)):
        col = status_color.get(r.status, "white")
        table.add_row(
            str(r.pr),
            f"[{col}]{r.status}[/{col}]",
            str(r.f2p),
            str(r.p2p),
            f"{r.duration_s:.0f}",
            r.title[:60],
            (r.error or "")[:60],
        )
    console.print(table)

    summary = Table(title="Status breakdown")
    summary.add_column("status")
    summary.add_column("count", justify="right")
    summary.add_column("share", justify="right")
    for status in ("exact", "fallback", "test_only", "no_signal", "error"):
        c = by_status.get(status, 0)
        summary.add_row(status, str(c), f"{c * 100 // max(total, 1)}%")
    console.print(summary)
