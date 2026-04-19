"""Single-PR FAIL_TO_PASS / PASS_TO_PASS extraction.

Backend-only. Supports two execution modes:

- `mode='local'` — runs on the host via `uv run`. Fast for iteration; depends
  on host python/uv.
- `mode='docker'` — runs in `prototypebench/backend:<tag>` with repo bind-
  mounted. Reproducible across hosts. Postgres joins a task-scoped docker
  network; the backend container reaches it by container name.

Flow:
  1. clone/reuse repo checkout
  2. git checkout <base_commit> + git apply <test_patch>
  3. start postgres (attached to network in docker mode)
  4. prestart (backend_pre_start + alembic upgrade + initial_data)
  5. pytest --junitxml → base
  6. reset/checkout <head_commit>
  7. prestart + pytest → head
  8. diff outcomes → FAIL_TO_PASS / PASS_TO_PASS
  9. write summary.json, tear down
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rich.console import Console

from . import backend_runner, git_ops, junit, postgres


@dataclass
class ExtractSpec:
    instance_id: str
    repo_url: str
    base_commit: str
    head_commit: str
    test_patch: str | None = None
    pytest_args: list[str] | None = None


@dataclass
class PhaseResult:
    returncode: int
    crashed: bool
    n_passed: int
    n_failed: int
    n_error: int
    n_skipped: int
    duration_s: float


@dataclass
class ExtractResult:
    instance_id: str
    base_commit: str
    head_commit: str
    mode: str
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    base: PhaseResult | None = None
    head: PhaseResult | None = None
    error: str | None = None


def _phase_summary(
    outcomes: dict[str, junit.Outcome], rc: int, crashed: bool, dur: float
) -> PhaseResult:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for o in outcomes.values():
        counts[o] = counts.get(o, 0) + 1
    return PhaseResult(
        returncode=rc,
        crashed=crashed,
        n_passed=counts["passed"],
        n_failed=counts["failed"],
        n_error=counts["error"],
        n_skipped=counts["skipped"],
        duration_s=dur,
    )


def extract(
    spec: ExtractSpec,
    *,
    work_root: Path,
    mode: str = "docker",
    console: Console | None = None,
    backend_image: str = "prototypebench/backend:latest",
) -> ExtractResult:
    console = console or Console()
    work_root.mkdir(parents=True, exist_ok=True)
    repo_dir = work_root / "repo"
    out_dir = work_root / "out"
    out_dir.mkdir(exist_ok=True)

    result = ExtractResult(
        instance_id=spec.instance_id,
        base_commit=spec.base_commit,
        head_commit=spec.head_commit,
        mode=mode,
    )

    def _write_summary() -> None:
        (out_dir / "summary.json").write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True)
        )

    # 1. clone (or reuse)
    if not repo_dir.exists():
        console.log(f"cloning {spec.repo_url} → {repo_dir}")
        git_ops.clone(spec.repo_url, repo_dir)
    else:
        console.log(f"reusing checkout: {repo_dir}")
        git_ops.clean(repo_dir)

    # 2-3. base + test_patch
    console.log(f"checkout base {spec.base_commit[:10]}")
    git_ops.checkout(repo_dir, spec.base_commit)

    # Sanity: our harness assumes uv-workspace layout (introduced in PR #2090,
    # merged 2026-01-20). Earlier commits were poetry-based and need a
    # different runner — bail early with an actionable message instead of
    # letting `uv sync` fail deep inside the container.
    if not (repo_dir / "uv.lock").exists():
        result.error = (
            "base_commit predates the uv-workspace migration (need merge of "
            "fastapi/full-stack-fastapi-template#2090 or later, 2026-01-20). "
            "This PR is not supported by the current harness."
        )
        _write_summary()
        return result

    if spec.test_patch:
        try:
            git_ops.apply_diff(repo_dir, spec.test_patch)
        except git_ops.GitError as e:
            result.error = f"test_patch apply failed on base: {e}"
            _write_summary()
            return result

    # 4. postgres + runner
    pg_name = f"pbench-db-{spec.instance_id}"[:60]
    network_name: str | None = None
    postgres.stop(pg_name)
    if mode == "docker":
        network_name = f"pbench-net-{spec.instance_id}"[:60]
        postgres.create_network(network_name)
    console.log(f"start postgres {pg_name} (mode={mode})")
    try:
        pg = postgres.start(pg_name, network=network_name)
    except postgres.PostgresError as e:
        result.error = f"postgres start failed: {e}"
        _write_summary()
        return result

    runner = backend_runner.make(
        mode,
        image=backend_image,
        network=network_name or "",
        out_mount=out_dir,
        container_prefix=f"pbench-b-{spec.instance_id}"[:50],
    )
    pg_env = pg.env_container() if mode == "docker" else pg.env_host()

    try:
        backend_dir = repo_dir / "backend"

        # 4a. prestart (base)
        console.log("running prestart on base")
        rc, so, se = runner.run_prestart(
            workspace_root=repo_dir, backend_dir=backend_dir, env_overrides=pg_env
        )
        (out_dir / "base.prestart.log").write_text(so + "\n---stderr---\n" + se)
        if rc != 0:
            result.error = f"prestart failed on base (rc={rc}). See base.prestart.log"
            return result

        # 5. base pytest
        console.log("running base pytest")
        t0 = time.monotonic()
        base_run = runner.run_pytest(
            workspace_root=repo_dir,
            backend_dir=backend_dir,
            junit_path=out_dir / "base.junit.xml",
            env_overrides=pg_env,
            pytest_args=spec.pytest_args,
        )
        base_outcomes = (
            junit.parse(base_run.junit_path) if base_run.junit_path.exists() else {}
        )
        result.base = _phase_summary(
            base_outcomes, base_run.returncode, base_run.crashed, time.monotonic() - t0
        )
        (out_dir / "base.stdout.log").write_text(base_run.stdout)
        (out_dir / "base.stderr.log").write_text(base_run.stderr)

        # 6-7. head
        console.log(f"checkout head {spec.head_commit[:10]}")
        git_ops.reset_hard(repo_dir, spec.base_commit)
        git_ops.checkout(repo_dir, spec.head_commit)
        console.log("running prestart on head")
        rc, so, se = runner.run_prestart(
            workspace_root=repo_dir, backend_dir=backend_dir, env_overrides=pg_env
        )
        (out_dir / "head.prestart.log").write_text(so + "\n---stderr---\n" + se)
        if rc != 0:
            result.error = f"prestart failed on head (rc={rc}). See head.prestart.log"
            return result
        console.log("running head pytest")
        t0 = time.monotonic()
        head_run = runner.run_pytest(
            workspace_root=repo_dir,
            backend_dir=backend_dir,
            junit_path=out_dir / "head.junit.xml",
            env_overrides=pg_env,
            pytest_args=spec.pytest_args,
        )
        head_outcomes = (
            junit.parse(head_run.junit_path) if head_run.junit_path.exists() else {}
        )
        result.head = _phase_summary(
            head_outcomes, head_run.returncode, head_run.crashed, time.monotonic() - t0
        )
        (out_dir / "head.stdout.log").write_text(head_run.stdout)
        (out_dir / "head.stderr.log").write_text(head_run.stderr)

        # 8. diff
        base_pass = junit.passing(base_outcomes)
        base_fail = junit.failing(base_outcomes)
        head_pass = junit.passing(head_outcomes)

        result.fail_to_pass = sorted(base_fail & head_pass)
        result.pass_to_pass = sorted((base_pass & head_pass) - set(result.fail_to_pass))
    finally:
        console.log(f"stop postgres {pg_name}")
        postgres.stop(pg_name)
        if network_name:
            postgres.remove_network(network_name)

    # 9. write summary
    _write_summary()
    console.log(
        f"FAIL_TO_PASS={len(result.fail_to_pass)} PASS_TO_PASS={len(result.pass_to_pass)}"
    )
    return result
