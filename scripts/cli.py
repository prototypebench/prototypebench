"""`pbench` — PrototypeBench pipeline CLI."""

from __future__ import annotations

import json
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
) -> None:
    """Quick look: print top-N candidates by score."""
    rows = load_jsonl(candidates)[:n]
    table = Table(title=f"Top {len(rows)} candidates")
    table.add_column("#", justify="right")
    table.add_column("score", justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("reasons", overflow="fold")
    for r in rows:
        pr = r["pr"]
        table.add_row(
            str(pr["number"]),
            str(r["score"]),
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
) -> None:
    """Phase 2 — extract FAIL_TO_PASS / PASS_TO_PASS for a single PR (backend, local mode)."""
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

    spec = ex.ExtractSpec(
        instance_id=instance_id,
        repo_url=repo_url,
        base_commit=base_commit,
        head_commit=head_commit,
        test_patch=test_patch or None,
        pytest_args=[a for a in pytest_args.split() if a] or None,
    )
    result = ex.extract(spec, work_root=work_dir, console=console)

    console.print("")
    console.print(f"[bold]FAIL_TO_PASS[/bold]: {len(result.fail_to_pass)}")
    for t in result.fail_to_pass[:10]:
        console.print(f"  + {t}")
    if len(result.fail_to_pass) > 10:
        console.print(f"  ... and {len(result.fail_to_pass) - 10} more")
    console.print(f"[bold]PASS_TO_PASS[/bold]: {len(result.pass_to_pass)}")
    console.print(f"summary → {work_dir / 'out' / 'summary.json'}")


if __name__ == "__main__":
    app()
