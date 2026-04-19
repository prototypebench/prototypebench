"""Run pytest inside the source-repo checkout and capture a JUnit XML."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class RunnerError(RuntimeError):
    pass


def run_prestart(
    *,
    workspace_root: Path,
    backend_dir: Path,
    env_overrides: dict[str, str] | None = None,
    timeout: float = 300.0,
) -> tuple[int, str, str]:
    """Run `alembic upgrade head` + initial data setup before tests.

    Mirrors backend/scripts/prestart.sh. DB must already be reachable.
    Returns (returncode, stdout, stderr) of the combined run; bails at the first
    non-zero step.
    """
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    combined_stdout: list[str] = []
    combined_stderr: list[str] = []
    for step in (
        ["python", "app/backend_pre_start.py"],
        ["alembic", "upgrade", "head"],
        ["python", "app/initial_data.py"],
    ):
        cmd = ["uv", "run", "--project", str(workspace_root), *step]
        r = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, env=env, timeout=timeout)
        combined_stdout.append(f"$ {' '.join(step)}\n{r.stdout}")
        combined_stderr.append(f"$ {' '.join(step)}\n{r.stderr}")
        if r.returncode != 0:
            return r.returncode, "\n".join(combined_stdout), "\n".join(combined_stderr)
    return 0, "\n".join(combined_stdout), "\n".join(combined_stderr)


@dataclass
class PytestResult:
    returncode: int
    stdout: str
    stderr: str
    junit_path: Path

    @property
    def crashed(self) -> bool:
        """Exit codes ≥ 2 in pytest mean collection/internal errors (not just test failures).

        0 = all passed, 1 = some failed, 2 = interrupted, 3 = internal error,
        4 = usage error, 5 = no tests collected. We treat anything other than
        0/1/5 as a crash.
        """
        return self.returncode not in (0, 1, 5)


def run_pytest(
    *,
    workspace_root: Path,
    backend_dir: Path,
    junit_path: Path,
    env_overrides: dict[str, str] | None = None,
    pytest_args: list[str] | None = None,
    timeout: float = 900.0,
) -> PytestResult:
    """Invoke `uv run pytest` in the source-repo backend dir.

    workspace_root: repo root (contains uv.lock)
    backend_dir:    backend/ within the repo — pytest is invoked with cwd=backend_dir
    junit_path:     where to write JUnit XML
    env_overrides:  POSTGRES_* etc.
    pytest_args:    extra args (e.g. ["tests/api/"]); default = ["tests"]
    """
    junit_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # Keep the host's `uv` findable but stabilize PATH a bit.
    if env_overrides:
        env.update(env_overrides)
    # pytest will read .env via pydantic-settings (FastAPI template convention).
    # Providing PYTHONDONTWRITEBYTECODE avoids littering .pyc files in the
    # bind-mounted repo.
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    args = pytest_args or ["tests"]
    cmd = [
        "uv", "run", "--project", str(workspace_root),
        "pytest",
        f"--junitxml={junit_path}",
        "-q",
        "--tb=short",
        *args,
    ]
    result = subprocess.run(
        cmd,
        cwd=backend_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return PytestResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        junit_path=junit_path,
    )
