"""Score an agent-submitted patch against a task instance.

Shares the execution core with `harness.extract`. The only difference:
  extract applies `test_patch` on base to *derive* FAIL_TO_PASS/PASS_TO_PASS.
  score  applies `test_patch` + `agent_patch` on base to *verify* them.

Scoring (v1, SWE-bench convention):
  score = 1  iff  FAIL_TO_PASS ⊆ passing(agent_run)
              AND PASS_TO_PASS ⊆ passing(agent_run)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rich.console import Console

from . import git_ops, junit, postgres, runner


@dataclass
class ScoreSpec:
    instance_id: str
    repo_url: str
    base_commit: str
    test_patch: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    agent_patch: str           # non-test diff from the agent
    pytest_args: list[str] | None = None


@dataclass
class ScoreResult:
    instance_id: str
    score: int                 # 0 or 1
    fail_to_pass_passed: list[str] = field(default_factory=list)
    fail_to_pass_missing: list[str] = field(default_factory=list)
    pass_to_pass_passed: list[str] = field(default_factory=list)
    pass_to_pass_regressed: list[str] = field(default_factory=list)
    phase_returncode: int | None = None
    phase_duration_s: float | None = None
    error: str | None = None


def score_patch(
    spec: ScoreSpec,
    *,
    work_root: Path,
    console: Console | None = None,
) -> ScoreResult:
    console = console or Console()
    work_root.mkdir(parents=True, exist_ok=True)
    repo_dir = work_root / "repo"
    out_dir = work_root / "out"
    out_dir.mkdir(exist_ok=True)

    result = ScoreResult(instance_id=spec.instance_id, score=0)

    if not repo_dir.exists():
        console.log(f"cloning {spec.repo_url} → {repo_dir}")
        git_ops.clone(spec.repo_url, repo_dir)
    else:
        console.log(f"reusing checkout: {repo_dir}")
        git_ops.clean(repo_dir)

    # 1. base checkout
    console.log(f"checkout base {spec.base_commit[:10]}")
    git_ops.checkout(repo_dir, spec.base_commit)

    # 2. test_patch (harness-injected) — must succeed
    try:
        git_ops.apply_diff(repo_dir, spec.test_patch)
    except git_ops.GitError as e:
        result.error = f"test_patch apply failed: {e}"
        return result

    # 3. agent_patch — must not touch test files (enforced by convention; we
    # still let git apply fail naturally if conflicts overlap). An empty patch
    # is treated as "agent produced nothing" (not an error) — expected to
    # score 0 since FAIL_TO_PASS tests will still fail.
    if spec.agent_patch.strip():
        try:
            git_ops.apply_diff(repo_dir, spec.agent_patch)
        except git_ops.GitError as e:
            result.error = f"agent_patch apply failed: {e}"
            return result
    else:
        console.log("agent_patch is empty — skipping apply, scoring as-is")

    # 4. postgres
    pg_name = f"pbench-score-{spec.instance_id}"[:60]
    postgres.stop(pg_name)
    try:
        pg = postgres.start(pg_name)
    except postgres.PostgresError as e:
        result.error = f"postgres start failed: {e}"
        return result

    try:
        backend_dir = repo_dir / "backend"

        # 5. prestart
        console.log("running prestart (alembic + initial data)")
        rc, so, se = runner.run_prestart(
            workspace_root=repo_dir, backend_dir=backend_dir, env_overrides=pg.env()
        )
        (out_dir / "agent.prestart.log").write_text(so + "\n---stderr---\n" + se)
        if rc != 0:
            result.error = f"prestart failed (rc={rc}). See agent.prestart.log"
            return result

        # 6. pytest
        console.log("running agent pytest")
        t0 = time.monotonic()
        run = runner.run_pytest(
            workspace_root=repo_dir,
            backend_dir=backend_dir,
            junit_path=out_dir / "agent.junit.xml",
            env_overrides=pg.env(),
            pytest_args=spec.pytest_args,
        )
        result.phase_duration_s = time.monotonic() - t0
        result.phase_returncode = run.returncode
        (out_dir / "agent.stdout.log").write_text(run.stdout)
        (out_dir / "agent.stderr.log").write_text(run.stderr)

        if not run.junit_path.exists():
            result.error = "pytest produced no JUnit xml (likely crashed during collection)"
            return result

        outcomes = junit.parse(run.junit_path)
        passing_tests = junit.passing(outcomes)

        # 7. compare against the curator's FAIL_TO_PASS / PASS_TO_PASS
        f2p_set = set(spec.fail_to_pass)
        p2p_set = set(spec.pass_to_pass)
        result.fail_to_pass_passed = sorted(f2p_set & passing_tests)
        result.fail_to_pass_missing = sorted(f2p_set - passing_tests)
        result.pass_to_pass_passed = sorted(p2p_set & passing_tests)
        result.pass_to_pass_regressed = sorted(p2p_set - passing_tests)

        result.score = int(not result.fail_to_pass_missing and not result.pass_to_pass_regressed)
    finally:
        postgres.stop(pg_name)

    # 8. write summary
    (out_dir / "score_summary.json").write_text(json.dumps(asdict(result), indent=2, sort_keys=True))
    console.log(
        f"score={result.score}  "
        f"F2P {len(result.fail_to_pass_passed)}/{len(spec.fail_to_pass)}  "
        f"P2P {len(result.pass_to_pass_passed)}/{len(spec.pass_to_pass)}"
    )
    return result
