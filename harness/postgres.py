"""Disposable Postgres container for a single extraction run.

We don't rely on the source repo's docker-compose so that the harness can run
on any host with just `docker`. Network namespace is host-bound via a mapped
port — this is fine for one-at-a-time local execution; parallel runs will get
unique ports via `find_free_port`.
"""

from __future__ import annotations

import socket
import subprocess
import time
from contextlib import closing
from dataclasses import dataclass


class PostgresError(RuntimeError):
    pass


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class PostgresHandle:
    container_name: str
    host_port: int           # host-mapped port (always present)
    user: str
    password: str
    db: str
    network: str | None = None  # docker network it joined, if any

    # Default canonical env-var names. Source-specific names live in SourceConfig
    # and are applied via the `env_for(...)` builder below.
    DEFAULT_ENV_MAP = {
        "server":   "POSTGRES_SERVER",
        "port":     "POSTGRES_PORT",
        "user":     "POSTGRES_USER",
        "password": "POSTGRES_PASSWORD",
        "db":       "POSTGRES_DB",
    }

    def env_for(
        self,
        *,
        env_map: dict[str, str] | None = None,
        from_container: bool = True,
    ) -> dict[str, str]:
        """Build env-var dict using a source-specific name map.

        env_map: canonical-key → source-specific env var name (e.g. {"password":
        "POLAR_POSTGRES_PWD"}). Missing keys fall back to DEFAULT_ENV_MAP.
        from_container: True → use container DNS name + port 5432.
                       False → use 127.0.0.1 + host-mapped port.
        """
        m = {**self.DEFAULT_ENV_MAP, **(env_map or {})}
        if from_container:
            server, port = self.container_name, "5432"
        else:
            server, port = "127.0.0.1", str(self.host_port)
        return {
            m["server"]:   server,
            m["port"]:     port,
            m["user"]:     self.user,
            m["password"]: self.password,
            m["db"]:       self.db,
        }

    # Back-compat shims — older callers pre-SourceConfig refactor.
    def env_host(self) -> dict[str, str]:
        return self.env_for(env_map=None, from_container=False)

    def env_container(self) -> dict[str, str]:
        return self.env_for(env_map=None, from_container=True)


def start(
    container_name: str,
    *,
    image: str = "postgres:18-alpine",
    user: str = "postgres",
    password: str = "changethis",
    db: str = "app",
    wait_timeout: float = 30.0,
    network: str | None = None,
) -> PostgresHandle:
    """Start a disposable postgres container and wait until it accepts connections.

    If `network` is given, the container joins that docker network so that
    other containers on the same network can reach it via `container_name:5432`.
    The host-mapped port is still published for debugging / local-mode fallback.
    """
    port = _find_free_port()
    cmd = [
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "-p", f"{port}:5432",
        "-e", f"POSTGRES_USER={user}",
        "-e", f"POSTGRES_PASSWORD={password}",
        "-e", f"POSTGRES_DB={db}",
    ]
    if network:
        cmd += ["--network", network]
    cmd.append(image)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise PostgresError(f"docker run failed: {result.stderr.strip()}")

    handle = PostgresHandle(
        container_name=container_name,
        host_port=port,
        user=user,
        password=password,
        db=db,
        network=network,
    )
    _wait_ready(handle, wait_timeout)
    return handle


def _wait_ready(handle: PostgresHandle, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["docker", "exec", handle.container_name, "pg_isready", "-U", handle.user, "-d", handle.db],
            capture_output=True,
        )
        if r.returncode == 0:
            return
        time.sleep(0.5)
    raise PostgresError(f"postgres {handle.container_name} not ready within {timeout}s")


def stop(name: str) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def create_network(name: str) -> None:
    """Idempotent docker network creation."""
    # `inspect` succeeds if it exists; otherwise create.
    r = subprocess.run(["docker", "network", "inspect", name], capture_output=True)
    if r.returncode == 0:
        return
    c = subprocess.run(
        ["docker", "network", "create", name], capture_output=True, text=True
    )
    if c.returncode != 0:
        raise PostgresError(f"network create failed: {c.stderr.strip()}")


def remove_network(name: str) -> None:
    subprocess.run(["docker", "network", "rm", name], capture_output=True)
