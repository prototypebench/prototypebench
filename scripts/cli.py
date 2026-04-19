"""`pbench` — PrototypeBench pipeline CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .build_instance import build_from_candidates
from .crawl_prs import crawl
from .filter_prs import filter_prs, load_jsonl
from .validate import validate_file

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


if __name__ == "__main__":
    app()
