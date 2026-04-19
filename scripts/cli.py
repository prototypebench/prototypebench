"""`pbench` — PrototypeBench pipeline CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .build_instance import build_from_candidates
from .crawl_prs import crawl
from .filter_prs import filter_prs, load_jsonl
from .validate import validate_file

# Harness (Phase 2) — imported lazily inside commands to keep `pbench --help`
# fast even when docker-dependent paths aren't ready.

app = typer.Typer(
    name="pbench",
    help="PrototypeBench task curation pipeline.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

DEFAULT_REPO = "fastapi/full-stack-fastapi-template"
DEFAULT_RAW_DIR = Path("raw")


@app.command(name="crawl")
def crawl_cmd(
    repo: str = typer.Option(DEFAULT_REPO, "--repo", help="Source repo in owner/name form."),
    output: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--output", "-o", help="Output JSONL path."
    ),
    limit: int = typer.Option(1000, "--limit", help="Max merged PRs to pull."),
    no_resume: bool = typer.Option(False, "--no-resume", help="Re-enrich from scratch."),
) -> None:
    """Phase 1 step 1 — crawl merged PRs from the source repo into raw/prs.jsonl."""
    count = crawl(repo, output, limit=limit, resume=not no_resume, console=console)
    console.print(f"[bold green]done[/bold green]: {count} PRs in {output}")


@app.command(name="filter")
def filter_cmd(
    input: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--input", "-i", help="Crawled PRs JSONL."
    ),
    candidates: Path = typer.Option(
        DEFAULT_RAW_DIR / "candidates.jsonl", "--candidates", help="Accepted + scored output."
    ),
    rejected: Path = typer.Option(
        DEFAULT_RAW_DIR / "rejected.jsonl", "--rejected", help="Dropped PRs with reasons."
    ),
) -> None:
    """Phase 1 step 2 — score and filter crawled PRs into a candidate pool."""
    n_ok, n_drop = filter_prs(input, candidates, rejected)
    console.print(f"[green]accepted[/green] {n_ok} → {candidates}")
    console.print(f"[yellow]rejected[/yellow] {n_drop} → {rejected}")


@app.command(name="top")
def top_cmd(
    candidates: Path = typer.Option(
        DEFAULT_RAW_DIR / "candidates.jsonl", "--candidates", help="Candidate pool JSONL."
    ),
    n: int = typer.Option(20, "--n", help="Number of candidates to show."),
    kind: str = typer.Option(
        "any", "--kind",
        help="Filter by test signal: 'backend' | 'frontend' | 'fullstack' | 'any'.",
    ),
) -> None:
    """Quick look: print top-N candidates by score, optionally filtered by kind."""
    rows = load_jsonl(candidates)

    def _matches(r: dict) -> bool:
        s = r.get("signals") or {}
        be, fe = s.get("backend_tests", 0), s.get("frontend_tests", 0)
        if kind == "backend":
            return be > 0
        if kind == "frontend":
            return fe > 0
        if kind == "fullstack":
            return be > 0 and fe > 0
        return True

    rows = [r for r in rows if _matches(r)][:n]
    table = Table(title=f"Top {len(rows)} candidates (kind={kind})")
    table.add_column("#", justify="right")
    table.add_column("score", justify="right")
    table.add_column("BE", justify="right")
    table.add_column("FE", justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("reasons", overflow="fold")
    for r in rows:
        pr = r["pr"]
        s = r.get("signals") or {}
        table.add_row(
            str(pr["number"]),
            str(r["score"]),
            str(s.get("backend_tests", 0)),
            str(s.get("frontend_tests", 0)),
            (pr.get("title") or "")[:80],
            ", ".join(r["reasons"]),
        )
    console.print(table)


@app.command(name="stats")
def stats_cmd(
    input: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--input", "-i", help="Crawled PRs JSONL."
    ),
) -> None:
    """Quick summary over crawled PRs — label distribution, size histogram."""
    prs = load_jsonl(input)
    if not prs:
        console.print("[yellow]no PRs loaded[/yellow]")
        return
    label_counts: dict[str, int] = {}
    for pr in prs:
        for l in pr.get("labels") or []:
            if isinstance(l, dict):
                name = l.get("name", "")
                label_counts[name] = label_counts.get(name, 0) + 1
    by_label = sorted(label_counts.items(), key=lambda kv: -kv[1])
    table = Table(title=f"Labels across {len(prs)} PRs")
    table.add_column("label")
    table.add_column("count", justify="right")
    for name, c in by_label[:25]:
        table.add_row(name, str(c))
    console.print(table)


@app.command(name="draft")
def draft_cmd(
    candidates: Path = typer.Option(
        DEFAULT_RAW_DIR / "candidates.jsonl", "--candidates", help="Candidate pool JSONL."
    ),
    output: Path = typer.Option(
        Path("tasks/drafts.jsonl"), "--output", "-o", help="Draft instances JSONL."
    ),
    top: int = typer.Option(10, "--top", help="How many top candidates to draft."),
) -> None:
    """Phase 1 step 3 — generate schema-shaped drafts from top-N candidates.

    Drafts contain <<TODO:...>> placeholders for fields that need test execution
    or curator judgment. Fill them in, then run `pbench validate`.
    """
    n = build_from_candidates(candidates, output, top_n=top)
    console.print(f"[green]wrote {n} draft(s)[/green] → {output}")
    console.print("Fill in <<TODO:...>> markers, then run `pbench validate`.")


@app.command(name="build-from-extract")
def build_from_extract_cmd(
    report: Path = typer.Option(
        DEFAULT_RAW_DIR / "extract_report.jsonl", "--report", help="Batch-extract JSONL."
    ),
    prs: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--prs", help="Crawled PRs JSONL."
    ),
    work_root: Path = typer.Option(
        Path("/tmp/pbench"), "--work-root", help="Same scratch dir used by batch-extract."
    ),
    output: Path = typer.Option(
        Path("tasks/instances.jsonl"), "--output", "-o", help="Output instances JSONL."
    ),
    statuses: str = typer.Option(
        "exact,fallback", "--statuses",
        help="Comma-separated extract statuses to convert.",
    ),
    cutoff: str = typer.Option(
        "2026-01-01", "--cutoff", help="ISO date for contamination_tier split."
    ),
) -> None:
    """Phase 1 step 4 — convert usable batch-extract results into tasks/instances.jsonl.

    Per-PR build pulls fields from three sources:
      - PR metadata    (raw/prs.jsonl)            → title, author, labels, body
      - Extract summary (work_root/.../summary.json) → F2P, P2P, base/head commits
      - Shared repo    (work_root/_shared_repo)    → patch, test_patch_*, lock SHAs
    """
    from scripts.build_from_extract import build_from_extract as bfe

    repo_dir = work_root / "_shared_repo"
    if not repo_dir.exists():
        raise typer.BadParameter(
            f"shared repo not found at {repo_dir} — run `pbench batch-extract` first."
        )
    status_set = {s.strip() for s in statuses.split(",") if s.strip()}
    n_built, n_skipped = bfe(
        report_path=report, prs_path=prs, repo_dir=repo_dir,
        work_root=work_root, output=output,
        statuses=status_set, cutoff=cutoff,
    )
    console.print(f"[green]built[/green] {n_built} instance(s) → {output}")
    console.print(f"[yellow]skipped[/yellow] {n_skipped} (status not in {sorted(status_set)} or missing artifacts)")
    console.print(f"\nNext: [bold]pbench validate -p {output}[/bold]")


@app.command(name="validate")
def validate_cmd(
    path: Path = typer.Option(
        Path("tasks/instances.jsonl"), "--path", "-p", help="Instances JSONL to validate."
    ),
) -> None:
    """Phase 1 step 5 — validate instances.jsonl against the task schema."""
    if not path.exists():
        console.print(f"[red]not found:[/red] {path}")
        raise typer.Exit(code=2)
    n, errors = validate_file(path)
    if not errors:
        console.print(f"[green]OK[/green] — {n} instance(s) valid")
        return
    for line_no, iid, msg in errors[:50]:
        console.print(f"[red]L{line_no}[/red] {iid}: {msg}")
    if len(errors) > 50:
        console.print(f"... and {len(errors) - 50} more")
    console.print(f"[red]{len(errors)} error(s) across {n} instance(s)[/red]")
    raise typer.Exit(code=1)


def _find_pr(prs_path: Path, pr_number: int) -> dict:
    for line in prs_path.open():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("number") == pr_number:
            return row
    raise typer.BadParameter(f"PR #{pr_number} not found in {prs_path}")


@app.command(name="extract")
def extract_cmd(
    pr: int = typer.Option(..., "--pr", help="Merged PR number from the source repo."),
    repo_url: str = typer.Option(
        "https://github.com/fastapi/full-stack-fastapi-template.git",
        "--repo-url",
    ),
    prs: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--prs", help="Crawled PRs JSONL."
    ),
    work_root: Path = typer.Option(
        Path("/tmp/pbench"), "--work-root", help="Scratch dir for checkouts/outputs."
    ),
    pytest_args: str = typer.Option(
        "", "--pytest-args", help="Extra pytest args, space-separated (e.g. 'tests/api/routes')."
    ),
    mode: str = typer.Option(
        "docker", "--mode", help="Execution mode: 'docker' (reproducible) or 'local' (host uv)."
    ),
) -> None:
    """Phase 2 — extract FAIL_TO_PASS / PASS_TO_PASS for a single PR (backend)."""
    import json as _json

    from harness import extract as ex
    from harness import git_ops

    row = _find_pr(prs, pr)
    head_commit = ((row.get("mergeCommit") or {}).get("oid")) or ""
    if not head_commit:
        raise typer.BadParameter(f"PR #{pr} has no mergeCommit.oid")

    instance_id = f"fastapi__full-stack-fastapi-template-{pr}"
    work_dir = work_root / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = work_dir / "repo"

    if not repo_dir.exists():
        console.log(f"cloning {repo_url} → {repo_dir}")
        git_ops.clone(repo_url, repo_dir)
    else:
        console.log(f"reusing checkout: {repo_dir}")

    # base = first parent of the merge commit. For squash merges (this repo's
    # default) the merge commit has exactly one parent on master — `<head>^`
    # gives the pre-PR state. For true merge commits, ^ still yields the main-
    # line parent.
    base_commit = git_ops.rev_parse(repo_dir, f"{head_commit}^")
    console.log(f"base={base_commit[:10]} head={head_commit[:10]}")

    # Derive the test-only patch from the PR range.
    test_patch = git_ops.diff(
        repo_dir,
        base_commit,
        head_commit,
        paths=["*test*", "*.spec.ts", "*.spec.tsx", "*.test.ts", "*.test.tsx"],
    )
    (work_dir / "test_patch.diff").write_text(test_patch)
    console.log(f"test_patch: {len(test_patch)} bytes")

    # Auto-scope pytest to the PR's changed backend test files when the user
    # hasn't pinned a scope explicitly. Speeds up extraction substantially and
    # matches what the curator cares about: the tests the PR actually targets.
    scoped = [a for a in pytest_args.split() if a]
    if not scoped and test_patch:
        hits = re.findall(
            r"^\+\+\+ b/(backend/(?:tests|app/tests)/[^\s]+)",
            test_patch,
            re.MULTILINE,
        )
        rel = sorted({p.replace("backend/", "", 1) for p in hits})
        if rel:
            scoped = rel
            console.log(f"auto-scoped pytest: {' '.join(rel)}")

    spec = ex.ExtractSpec(
        instance_id=instance_id,
        repo_url=repo_url,
        base_commit=base_commit,
        head_commit=head_commit,
        test_patch=test_patch or None,
        pytest_args=scoped or None,
    )
    result = ex.extract(spec, work_root=work_dir, mode=mode, console=console)

    console.print("")
    console.print(f"[bold]FAIL_TO_PASS[/bold]: {len(result.fail_to_pass)}")
    for t in result.fail_to_pass[:10]:
        console.print(f"  + {t}")
    if len(result.fail_to_pass) > 10:
        console.print(f"  ... and {len(result.fail_to_pass) - 10} more")
    console.print(f"[bold]PASS_TO_PASS[/bold]: {len(result.pass_to_pass)}")
    console.print(f"summary → {work_dir / 'out' / 'summary.json'}")


@app.command(name="extract-frontend")
def extract_frontend_cmd(
    pr: int = typer.Option(..., "--pr", help="Merged PR number from the source repo."),
    repo_url: str = typer.Option(
        "https://github.com/fastapi/full-stack-fastapi-template.git",
        "--repo-url",
    ),
    prs: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--prs", help="Crawled PRs JSONL."
    ),
    work_root: Path = typer.Option(
        Path("/tmp/pbench"), "--work-root", help="Scratch dir; reuses _shared_repo if present."
    ),
    playwright_args: str = typer.Option(
        "", "--playwright-args",
        help="Extra args, e.g. 'tests/sign-up.spec.ts' to scope to one file.",
    ),
) -> None:
    """Phase 2 — extract FAIL_TO_PASS / PASS_TO_PASS for a PR via Playwright.

    Uses the source repo's compose stack (db + backend + prestart + mailcatcher
    + frontend + playwright). First run will build the playwright image
    (5-15 min); subsequent runs reuse the cached image.
    """
    from harness import frontend_extract as fe
    from harness import git_ops as g

    row = _find_pr(prs, pr)
    head_commit = ((row.get("mergeCommit") or {}).get("oid")) or ""
    if not head_commit:
        raise typer.BadParameter(f"PR #{pr} has no mergeCommit.oid")

    instance_id = f"fastapi__full-stack-fastapi-template-{pr}"
    work_dir = work_root / instance_id
    work_dir.mkdir(parents=True, exist_ok=True)

    shared = work_root / "_shared_repo"
    if shared.exists():
        repo_dir = shared
    else:
        repo_dir = work_dir / "repo"
        if not repo_dir.exists():
            console.log(f"cloning {repo_url} → {repo_dir}")
            g.clone(repo_url, repo_dir)

    base_commit = g.rev_parse(repo_dir, f"{head_commit}^")
    console.log(f"base={base_commit[:10]} head={head_commit[:10]}")

    # Auto-scope test_patch to frontend test files only.
    test_patch = g.diff(
        repo_dir, base_commit, head_commit,
        paths=["frontend/tests/**", "frontend/**/*.spec.ts", "frontend/**/*.spec.tsx",
               "frontend/**/*.test.ts", "frontend/**/*.test.tsx"],
    )
    (work_dir / "frontend_test_patch.diff").write_text(test_patch)
    console.log(f"frontend test_patch: {len(test_patch)} bytes")

    spec = fe.FrontendExtractSpec(
        instance_id=instance_id,
        repo_url=repo_url,
        base_commit=base_commit,
        head_commit=head_commit,
        test_patch=test_patch or None,
        playwright_args=[a for a in playwright_args.split() if a] or None,
    )
    result = fe.extract_frontend(spec, work_root=work_dir, console=console, repo_dir=repo_dir)

    console.print("")
    if result.error:
        console.print(f"[red]error:[/red] {result.error}")
    console.print(f"[bold]FAIL_TO_PASS[/bold]: {len(result.fail_to_pass)}")
    for t in result.fail_to_pass[:10]:
        console.print(f"  + {t}")
    if len(result.fail_to_pass) > 10:
        console.print(f"  ... and {len(result.fail_to_pass) - 10} more")
    console.print(f"[bold]PASS_TO_PASS[/bold]: {len(result.pass_to_pass)}")
    for n in result.notes:
        console.print(f"[yellow]note:[/yellow] {n}")


@app.command(name="batch-extract")
def batch_extract_cmd(
    candidates: Path = typer.Option(
        DEFAULT_RAW_DIR / "candidates.jsonl", "--candidates", help="Filtered candidate pool."
    ),
    top: int = typer.Option(0, "--top", help="Process only the top-N candidates (0 = all)."),
    report: Path = typer.Option(
        DEFAULT_RAW_DIR / "extract_report.jsonl", "--report", help="Per-PR JSONL report."
    ),
    work_root: Path = typer.Option(
        Path("/tmp/pbench"), "--work-root", help="Scratch dir; shares one repo checkout."
    ),
    repo_url: str = typer.Option(
        "https://github.com/fastapi/full-stack-fastapi-template.git",
        "--repo-url",
    ),
    mode: str = typer.Option(
        "docker", "--mode", help="Execution mode: 'docker' or 'local' (backend kind only)."
    ),
    kind: str = typer.Option(
        "backend", "--kind",
        help="'backend' (pytest) or 'frontend' (Playwright). Default: backend.",
    ),
) -> None:
    """Phase 2 — batch-run the extractor over the candidate pool.

    Produces a per-PR JSONL report and prints a status-breakdown table:
      exact     — F2P derived from base/head test diff
      fallback  — F2P recovered from test_patch parse (base collection-error)
      test_only — no F2P signal but P2P present (test-refactor PR)
      no_signal — no F2P, no P2P (likely needs manual triage)
      error     — pipeline failed; see `error` field in the report
    """
    from harness import batch

    results = batch.batch_extract(
        candidates_path=candidates,
        work_root=work_root,
        report_path=report,
        repo_url=repo_url,
        top_n=top or None,
        mode=mode,
        kind=kind,
        console=console,
    )
    console.print("")
    batch.render_summary(results, console)
    console.print(f"\nreport → {report}")


@app.command(name="score")
def score_cmd(
    pr: int = typer.Option(..., "--pr", help="Merged PR number (must have been extracted first)."),
    patch_file: Path = typer.Option(..., "--patch-file", help="Path to the agent's unified-diff patch."),
    prs: Path = typer.Option(
        DEFAULT_RAW_DIR / "prs.jsonl", "--prs", help="Crawled PRs JSONL."
    ),
    work_root: Path = typer.Option(
        Path("/tmp/pbench"), "--work-root", help="Must match the extract run's --work-root."
    ),
    pytest_args: str = typer.Option(
        "", "--pytest-args", help="Extra pytest args (same scope used during extract)."
    ),
    mode: str = typer.Option(
        "docker", "--mode", help="Execution mode: 'docker' or 'local'."
    ),
) -> None:
    """Phase 2 — score an agent patch against a PR's FAIL_TO_PASS/PASS_TO_PASS.

    Prereq: `pbench extract --pr <N>` has already run for this PR so that
    work_root/<instance_id>/out/summary.json and test_patch.diff exist.
    """
    from harness import score as sc

    _find_pr(prs, pr)  # just validates the PR exists in the crawl
    instance_id = f"fastapi__full-stack-fastapi-template-{pr}"
    work_dir = work_root / instance_id

    summary_path = work_dir / "out" / "summary.json"
    if not summary_path.exists():
        raise typer.BadParameter(
            f"No extract summary at {summary_path}. Run `pbench extract --pr {pr}` first."
        )
    summary = json.loads(summary_path.read_text())

    test_patch_path = work_dir / "test_patch.diff"
    test_patch = test_patch_path.read_text() if test_patch_path.exists() else ""

    if not patch_file.exists():
        raise typer.BadParameter(f"patch file not found: {patch_file}")
    agent_patch = patch_file.read_text()

    spec = sc.ScoreSpec(
        instance_id=instance_id,
        repo_url="https://github.com/fastapi/full-stack-fastapi-template.git",
        base_commit=summary["base_commit"],
        test_patch=test_patch,
        fail_to_pass=list(summary.get("fail_to_pass") or []),
        pass_to_pass=list(summary.get("pass_to_pass") or []),
        agent_patch=agent_patch,
        pytest_args=[a for a in pytest_args.split() if a] or None,
    )
    result = sc.score_patch(spec, work_root=work_dir, mode=mode, console=console)

    console.print("")
    color = "green" if result.score == 1 else "red"
    console.print(f"[bold {color}]score = {result.score}[/bold {color}]")
    console.print(
        f"FAIL_TO_PASS: {len(result.fail_to_pass_passed)}/{len(spec.fail_to_pass)} passing"
    )
    if result.fail_to_pass_missing:
        console.print(f"  [red]missing[/red]:")
        for t in result.fail_to_pass_missing[:8]:
            console.print(f"    - {t}")
    console.print(
        f"PASS_TO_PASS: {len(result.pass_to_pass_passed)}/{len(spec.pass_to_pass)} passing"
    )
    if result.pass_to_pass_regressed:
        console.print(f"  [red]regressed[/red]:")
        for t in result.pass_to_pass_regressed[:8]:
            console.print(f"    - {t}")
    if result.error:
        console.print(f"[red]error:[/red] {result.error}")
    raise typer.Exit(code=0 if result.score == 1 else 1)


if __name__ == "__main__":
    app()
