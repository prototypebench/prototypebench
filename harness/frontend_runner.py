"""Frontend Playwright runner — orchestrates the source repo's compose stack.

We deliberately reuse the base repo's compose definition (compose.yml +
compose.override.yml + frontend/Dockerfile.playwright) rather than replicate
it. The repo already wires backend, db, prestart (alembic + initial_data),
mailcatcher, frontend, and playwright services together — bypassing it
would mean re-implementing all those dependencies.

Per-PR isolation: docker-compose project name = `pbench-fe-<instance_id>`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import playwright_report


class FrontendRunnerError(RuntimeError):
    pass


@dataclass
class PlaywrightRun:
    returncode: int
    stdout: str
    stderr: str
    json_path: Path
    json_present: bool


_NO_PORTS_OVERLAY = (
    Path(__file__).resolve().parent / "docker" / "compose.no-host-ports.yml"
)


def _compose(repo_dir: Path, project: str, args: list[str], *, timeout: float, capture: bool = True) -> subprocess.CompletedProcess[str]:
    # Explicitly pass the source repo's compose files plus our overlay so we
    # know exactly which configuration is in effect — implicit auto-discovery
    # would skip the overlay since it lives outside the repo.
    cmd = [
        "docker", "compose",
        "-f", "compose.yml",
        "-f", "compose.override.yml",
        "-f", str(_NO_PORTS_OVERLAY),
        "-p", project,
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=repo_dir,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def teardown(repo_dir: Path, project: str) -> None:
    _compose(repo_dir, project, ["down", "-v", "--remove-orphans"], timeout=180)


def build(repo_dir: Path, project: str, *, timeout: float = 1800.0) -> subprocess.CompletedProcess[str]:
    """Build the playwright service image. Frontend Dockerfile.playwright also
    copies frontend/ source — so this needs to be re-run when source changes
    between base/head commits.
    """
    return _compose(repo_dir, project, ["build", "playwright"], timeout=timeout)


def run_playwright(
    *,
    repo_dir: Path,
    project: str,
    out_dir: Path,
    extra_args: list[str] | None = None,
    timeout: float = 1800.0,
) -> PlaywrightRun:
    """Run `bunx playwright test --reporter=json` inside the playwright service.

    Output is bind-mounted to `out_dir` (host) → `/output` (container). We use
    a shell wrapper so we can capture playwright's exit code separately from
    docker compose's.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    pa = " ".join(extra_args or [])
    # PLAYWRIGHT_JSON_OUTPUT_NAME tells the json reporter to write to a file
    # instead of stdout — needed because frontend's playwright.config imports
    # `dotenv/config`, which prints a banner to stdout that would corrupt JSON
    # parsing if we relied on > redirection.
    container_cmd = (
        f"bunx playwright test --reporter=json {pa} "
        f"> /output/playwright.stdout 2> /output/playwright.stderr; "
        "echo $? > /output/playwright.exitcode"
    )
    # Use the path as-is (no resolve()) so Docker Desktop's file-sharing
    # policy treats it consistently with how /tmp is registered. resolve()
    # turns /tmp into /private/tmp on macOS, which can fail to mount.
    out_abs = out_dir if out_dir.is_absolute() else out_dir.resolve()
    cmd = [
        "docker", "compose",
        "-f", "compose.yml",
        "-f", "compose.override.yml",
        "-f", str(_NO_PORTS_OVERLAY),
        "-p", project, "run", "--rm",
        "-v", f"{out_abs}:/output",
        "-e", "PLAYWRIGHT_JSON_OUTPUT_NAME=/output/playwright.json",
        "-T",
        "playwright",
        "bash", "-c", container_cmd,
    ]
    r = subprocess.run(
        cmd, cwd=repo_dir, capture_output=True, text=True, timeout=timeout
    )
    json_path = out_dir / "playwright.json"
    return PlaywrightRun(
        returncode=r.returncode,
        stdout=r.stdout,
        stderr=r.stderr,
        json_path=json_path,
        json_present=json_path.exists() and json_path.stat().st_size > 0,
    )


def run_phase(
    *,
    repo_dir: Path,
    project: str,
    out_dir: Path,
    extra_args: list[str] | None = None,
    build_timeout: float = 1800.0,
    test_timeout: float = 1800.0,
) -> tuple[PlaywrightRun, dict[str, playwright_report.Outcome]]:
    """End-to-end one phase: teardown previous → build → run → parse → teardown."""
    teardown(repo_dir, project)
    b = build(repo_dir, project, timeout=build_timeout)
    if b.returncode != 0:
        raise FrontendRunnerError(f"playwright image build failed:\n{b.stderr[-2000:]}")
    run = run_playwright(
        repo_dir=repo_dir, project=project, out_dir=out_dir,
        extra_args=extra_args, timeout=test_timeout,
    )
    teardown(repo_dir, project)
    if not run.json_present:
        return run, {}
    outcomes = playwright_report.parse(run.json_path)
    return run, outcomes
