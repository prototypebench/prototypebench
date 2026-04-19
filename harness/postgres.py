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

    def env_host(self) -> dict[str, str]:
        """Env for a host-side process (POSTGRES_SERVER=127.0.0.1:<port>)."""
        return {
            "POSTGRES_SERVER": "127.0.0.1",
            "POSTGRES_PORT": str(self.host_port),
            "POSTGRES_USER": self.user,
            "POSTGRES_PASSWORD": self.password,
            "POSTGRES_DB": self.db,
        }

    def env_container(self) -> dict[str, str]:
        """Env for another container on the same docker network.

        Uses the container name as DNS and postgres's native port 5432.
        """
        return {
            "POSTGRES_SERVER": self.container_name,
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": self.user,
            "POSTGRES_PASSWORD": self.password,
            "POSTGRES_DB": self.db,
        }


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
