"""Unified backend pytest runner — local (host `uv`) or docker container.

Same interface both modes. extract/score call `runner = make(mode, ...)` and
then `runner.run_prestart(...)` / `runner.run_pytest(...)` without caring which
implementation is underneath.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RunnerError(RuntimeError):
    pass


@dataclass
class PytestResult:
    returncode: int
    stdout: str
    stderr: str
    junit_path: Path

    @property
    def crashed(self) -> bool:
        """pytest exit codes ≥ 2 mean collection/internal errors.
        0=all passed, 1=some failed, 2=interrupted, 3=internal, 4=usage,
        5=no tests collected. Treat anything outside {0,1,5} as a crash.
        """
        return self.returncode not in (0, 1, 5)


class BackendRunner(Protocol):
    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        env_overrides: dict[str, str] | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str, str]: ...

    def run_pytest(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        junit_path: Path,
        env_overrides: dict[str, str] | None = None,
        pytest_args: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult: ...


# --- local implementation (host uv) -----------------------------------------


class LocalRunner:
    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        env_overrides: dict[str, str] | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str, str]:
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        stdout: list[str] = []
        stderr: list[str] = []
        for step in (
            ["python", "app/backend_pre_start.py"],
            ["alembic", "upgrade", "head"],
            ["python", "app/initial_data.py"],
        ):
            cmd = ["uv", "run", "--project", str(workspace_root), *step]
            r = subprocess.run(
                cmd, cwd=backend_dir, capture_output=True, text=True, env=env, timeout=timeout
            )
            stdout.append(f"$ {' '.join(step)}\n{r.stdout}")
            stderr.append(f"$ {' '.join(step)}\n{r.stderr}")
            if r.returncode != 0:
                return r.returncode, "\n".join(stdout), "\n".join(stderr)
        return 0, "\n".join(stdout), "\n".join(stderr)

    def run_pytest(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        junit_path: Path,
        env_overrides: dict[str, str] | None = None,
        pytest_args: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        args = pytest_args or ["tests"]
        cmd = [
            "uv", "run", "--project", str(workspace_root),
            "pytest",
            f"--junitxml={junit_path}",
            "-q", "--tb=short",
            *args,
        ]
        r = subprocess.run(
            cmd, cwd=backend_dir, capture_output=True, text=True, env=env, timeout=timeout
        )
        return PytestResult(r.returncode, r.stdout, r.stderr, junit_path)


# --- docker implementation --------------------------------------------------


class DockerRunner:
    """Runs inside `prototypebench/backend:<tag>` with repo bind-mounted at /work.

    Mapping:
      workspace_root  →  mounted at /work  (cwd is set to /work/<rel backend_dir>)
      out_dir         →  mounted at /out   (junit_path must live inside out_dir)
      uv cache        →  named docker volume mounted at /root/.cache/uv

    The postgres container must be on `network` so env POSTGRES_SERVER can be
    the DB's container name.
    """

    def __init__(
        self,
        *,
        image: str,
        network: str,
        uv_cache_volume: str,
        out_mount: Path,
        container_prefix: str,
    ):
        self.image = image
        self.network = network
        self.uv_cache_volume = uv_cache_volume
        self.out_mount = out_mount
        self.container_prefix = container_prefix

    def _docker_run(
        self,
        *,
        name_suffix: str,
        workspace_root: Path,
        backend_dir: Path,
        shell_cmd: str,
        env_overrides: dict[str, str] | None,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        rel_backend = backend_dir.relative_to(workspace_root)
        container_name = f"{self.container_prefix}-{name_suffix}"[:60]
        cmd: list[str] = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", self.network,
            "-v", f"{workspace_root}:/work",
            "-v", f"{self.uv_cache_volume}:/root/.cache/uv",
            "-v", f"{self.out_mount}:/out",
            "-w", f"/work/{rel_backend}",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
        ]
        for k, v in (env_overrides or {}).items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [self.image, "bash", "-c", shell_cmd]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        env_overrides: dict[str, str] | None = None,
        timeout: float = 600.0,
    ) -> tuple[int, str, str]:
        # One-shot container: `uv sync` → backend_pre_start → alembic → initial_data.
        shell_cmd = (
            "set -e; "
            "uv sync --frozen --project /work; "
            "uv run --project /work python app/backend_pre_start.py; "
            "uv run --project /work alembic upgrade head; "
            "uv run --project /work python app/initial_data.py"
        )
        r = self._docker_run(
            name_suffix="prestart",
            workspace_root=workspace_root,
            backend_dir=backend_dir,
            shell_cmd=shell_cmd,
            env_overrides=env_overrides,
            timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr

    def run_pytest(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        junit_path: Path,
        env_overrides: dict[str, str] | None = None,
        pytest_args: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        # junit_path must live under out_mount so /out/<name> writes back to host.
        try:
            rel_junit = junit_path.relative_to(self.out_mount)
        except ValueError as e:
            raise RunnerError(
                f"junit_path {junit_path} is not under out_mount {self.out_mount}"
            ) from e
        container_junit = f"/out/{rel_junit}"
        args = " ".join(pytest_args or ["tests"])
        shell_cmd = (
            "set -e; "
            "uv sync --frozen --project /work; "
            f"uv run --project /work pytest --junitxml={container_junit} -q --tb=short {args}"
        )
        r = self._docker_run(
            name_suffix="pytest",
            workspace_root=workspace_root,
            backend_dir=backend_dir,
            shell_cmd=shell_cmd,
            env_overrides=env_overrides,
            timeout=timeout,
        )
        return PytestResult(r.returncode, r.stdout, r.stderr, junit_path)


# --- factory ---------------------------------------------------------------


def make(
    mode: str,
    *,
    # docker-only:
    image: str = "prototypebench/backend:latest",
    network: str | None = None,
    uv_cache_volume: str = "pbench-uv-cache",
    out_mount: Path | None = None,
    container_prefix: str = "pbench-backend",
) -> BackendRunner:
    """Build a runner for the requested mode.

    `mode='local'` returns a LocalRunner and ignores docker-specific args.
    `mode='docker'` requires `network` and `out_mount`.
    """
    if mode == "local":
        return LocalRunner()
    if mode != "docker":
        raise RunnerError(f"unknown mode: {mode}")
    if not network or not out_mount:
        raise RunnerError("docker mode requires `network` and `out_mount`")
    return DockerRunner(
        image=image,
        network=network,
        uv_cache_volume=uv_cache_volume,
        out_mount=out_mount,
        container_prefix=container_prefix,
    )
