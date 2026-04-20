"""Unified backend pytest runner — local (host `uv`) or docker container.

Both runners take SourceConfig-derived arguments:
  - prestart_steps: list of argv lists, each invoked via `uv run [--extra X]…`
  - pytest_extra_args: extra args passed to pytest (e.g. `-n auto`, `--no-cov`)
  - uv_extras: extras to enable for both `uv sync` and `uv run`
This lets one runner drive any source repo in the registry without each runner
hard-coding `app/backend_pre_start.py`-style invocations.
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
        """0=all passed, 1=some failed, 2=interrupted, 3=internal, 4=usage,
        5=no tests collected. Anything outside {0,1,5} is a crash."""
        return self.returncode not in (0, 1, 5)


class BackendRunner(Protocol):
    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        prestart_steps: list[list[str]],
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str, str]: ...

    def run_pytest(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        junit_path: Path,
        pytest_args: list[str] | None = None,
        pytest_extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult: ...


def _extras_flags(uv_extras: list[str] | None) -> list[str]:
    out: list[str] = []
    for e in uv_extras or []:
        out += ["--extra", e]
    return out


# --- local implementation (host uv) -----------------------------------------


class LocalRunner:
    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        prestart_steps: list[list[str]],
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str, str]:
        if not prestart_steps:
            return 0, "(no prestart steps)", ""
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        stdout: list[str] = []
        stderr: list[str] = []
        for step in prestart_steps:
            cmd = ["uv", "run", "--project", str(workspace_root), *_extras_flags(uv_extras), *step]
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
        pytest_args: list[str] | None = None,
        pytest_extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        scope = pytest_args or ["tests"]
        cmd = [
            "uv", "run", "--project", str(workspace_root), *_extras_flags(uv_extras),
            "pytest",
            f"--junitxml={junit_path}",
            "-q", "--tb=short",
            *(pytest_extra_args or []),
            *scope,
        ]
        r = subprocess.run(
            cmd, cwd=backend_dir, capture_output=True, text=True, env=env, timeout=timeout
        )
        return PytestResult(r.returncode, r.stdout, r.stderr, junit_path)


# --- docker implementation --------------------------------------------------


class DockerRunner:
    """Runs inside the source-config's backend image with repo bind-mounted at /work.

    The postgres container (if any) must be on `network` so that env-var
    container DNS works.
    """

    def __init__(
        self,
        *,
        image: str,
        network: str | None,
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
        rel_backend = backend_dir.relative_to(workspace_root) if backend_dir != workspace_root else Path(".")
        container_name = f"{self.container_prefix}-{name_suffix}"[:60]
        workdir = "/work" if str(rel_backend) in (".", "") else f"/work/{rel_backend}"
        cmd: list[str] = [
            "docker", "run", "--rm",
            "--name", container_name,
        ]
        if self.network:
            cmd += ["--network", self.network]
        cmd += [
            "-v", f"{workspace_root}:/work",
            "-v", f"{self.uv_cache_volume}:/root/.cache/uv",
            "-v", f"{self.out_mount}:/out",
            "-w", workdir,
            "-e", "PYTHONDONTWRITEBYTECODE=1",
        ]
        for k, v in (env_overrides or {}).items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [self.image, "bash", "-c", shell_cmd]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _uv_sync_cmd(self, uv_extras: list[str] | None) -> str:
        extras = " ".join(f"--extra {e}" for e in (uv_extras or []))
        return f"uv sync --frozen --project /work {extras}".strip()

    def _uv_run_prefix(self, uv_extras: list[str] | None) -> str:
        extras = " ".join(f"--extra {e}" for e in (uv_extras or []))
        return f"uv run --project /work {extras}".strip()

    def run_prestart(
        self,
        *,
        workspace_root: Path,
        backend_dir: Path,
        prestart_steps: list[list[str]],
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 600.0,
    ) -> tuple[int, str, str]:
        sync_cmd = self._uv_sync_cmd(uv_extras)
        run_prefix = self._uv_run_prefix(uv_extras)
        steps_shell = "; ".join(f"{run_prefix} {' '.join(step)}" for step in prestart_steps)
        if not prestart_steps:
            shell_cmd = f"set -e; {sync_cmd}"  # still need to install deps
        else:
            shell_cmd = f"set -e; {sync_cmd}; {steps_shell}"
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
        pytest_args: list[str] | None = None,
        pytest_extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
        uv_extras: list[str] | None = None,
        timeout: float = 900.0,
    ) -> PytestResult:
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rel_junit = junit_path.relative_to(self.out_mount)
        except ValueError as e:
            raise RunnerError(
                f"junit_path {junit_path} is not under out_mount {self.out_mount}"
            ) from e
        container_junit = f"/out/{rel_junit}"
        sync_cmd = self._uv_sync_cmd(uv_extras)
        run_prefix = self._uv_run_prefix(uv_extras)
        scope = " ".join(pytest_args or ["tests"])
        extras_args = " ".join(pytest_extra_args or [])
        shell_cmd = (
            f"set -e; {sync_cmd}; "
            f"{run_prefix} pytest --junitxml={container_junit} -q --tb=short {extras_args} {scope}"
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
    if not out_mount:
        raise RunnerError("docker mode requires `out_mount`")
    return DockerRunner(
        image=image,
        network=network,
        uv_cache_volume=uv_cache_volume,
        out_mount=out_mount,
        container_prefix=container_prefix,
    )
