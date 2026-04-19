"""Thin wrapper around the `gh` CLI.

Using `gh` (vs raw HTTP) buys us: keyring auth, automatic rate-limit backoff,
consistent JSON shape across endpoints, and one less token to manage.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


class GhError(RuntimeError):
    """Non-zero exit from the gh CLI."""


def _require_gh() -> str:
    path = shutil.which("gh")
    if path is None:
        raise GhError("`gh` CLI not found on PATH. Install from https://cli.github.com/.")
    return path


def run(args: list[str], *, timeout: float = 120.0) -> str:
    """Run `gh <args>` and return stdout. Raises GhError on non-zero exit."""
    gh = _require_gh()
    result = subprocess.run(
        [gh, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise GhError(
            f"gh {' '.join(args)} exited {result.returncode}\nstderr: {result.stderr.strip()}"
        )
    return result.stdout


def run_json(args: list[str], *, timeout: float = 120.0) -> Any:
    return json.loads(run(args, timeout=timeout))


def pr_list(repo: str, *, state: str = "merged", limit: int = 1000, fields: list[str]) -> list[dict]:
    """List PRs via `gh pr list --json`. Returns list of dicts."""
    return run_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            ",".join(fields),
        ],
        timeout=300.0,
    )


def pr_view(repo: str, number: int, *, fields: list[str]) -> dict:
    """Fetch a single PR's details. Returns dict."""
    return run_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            ",".join(fields),
        ],
        timeout=60.0,
    )
