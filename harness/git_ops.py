"""Thin git subprocess wrappers for harness operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path, *, input_text: str | None = None, timeout: float = 120.0) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} (cwd={cwd}) exited {result.returncode}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout


def clone(url: str, dst: Path, *, depth: int | None = None) -> None:
    if dst.exists():
        raise GitError(f"clone target already exists: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["git", "clone"]
    if depth:
        args += ["--depth", str(depth)]
    args += [url, str(dst)]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(f"git clone failed: {result.stderr.strip()}")


def fetch_commit(repo: Path, commit: str) -> None:
    """Fetch a specific commit into the repo (for shallow clones)."""
    _run(["fetch", "origin", commit], cwd=repo, timeout=600)


def checkout(repo: Path, commit: str) -> None:
    _run(["checkout", "--force", commit], cwd=repo)


def reset_hard(repo: Path, commit: str) -> None:
    _run(["reset", "--hard", commit], cwd=repo)


def clean(repo: Path) -> None:
    _run(["clean", "-fdx"], cwd=repo)


def merge_base(repo: Path, a: str, b: str) -> str:
    return _run(["merge-base", a, b], cwd=repo).strip()


def rev_parse(repo: Path, rev: str) -> str:
    return _run(["rev-parse", rev], cwd=repo).strip()


def apply_diff(repo: Path, diff_text: str) -> None:
    """Apply a unified diff via stdin."""
    _run(["apply", "--whitespace=nowarn", "-"], cwd=repo, input_text=diff_text)


def show_file(repo: Path, commit: str, path: str) -> str:
    return _run(["show", f"{commit}:{path}"], cwd=repo)


def diff(repo: Path, a: str, b: str, *, paths: list[str] | None = None, exclude: list[str] | None = None) -> str:
    args = ["diff", a, b]
    if paths or exclude:
        args.append("--")
        if paths:
            args.extend(paths)
        if exclude:
            args.extend([f":!{p}" for p in exclude])
    return _run(args, cwd=repo, timeout=180)


def ensure_clean_tmp(path: Path) -> None:
    """Delete path if it exists — used for reproducible per-task tmp dirs."""
    if path.exists():
        shutil.rmtree(path)
