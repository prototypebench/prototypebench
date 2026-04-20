"""Source config for IBM/mcp-context-forge.

The repo is a single-package layout (no workspace): pyproject.toml, uv.lock,
mcpgateway/, tests/ all live at the root. Tests default to in-memory SQLite
(see top-level conftest.py), so no Postgres is required for the harness.

CI command (from .github/workflows/pytest.yml):
  uv run --extra plugins pytest -n auto --ignore=tests/fuzz --cov=mcpgateway ...

We drop --cov flags (we only care about pass/fail).
"""

from __future__ import annotations

from . import SourceConfig, register

CONFIG = register(SourceConfig(
    name="IBM/mcp-context-forge",
    short_name="mcp-context-forge",
    repo_url="https://github.com/IBM/mcp-context-forge.git",
    backend_dir="",                          # backend is the repo root
    uv_lock_path="uv.lock",
    backend_test_path_re=r"^tests/[^\s]+\.py$",
    backend_test_path_strip_prefix="",       # already cwd-relative
    backend_image="prototypebench/backend-py312:latest",
    python_version="3.12",
    uv_extras=["plugins"],
    uv_dev=True,
    prestart_steps=[],                       # SQLite create_all auto via conftest
    pytest_extra_args=["-n", "auto", "--ignore=tests/fuzz", "--no-cov"],
    pg_required=False,
    pg_env_map={},
    pg_defaults={},
    extra_services=[],
    uv_era_min_merged_at="2024-01-01",       # well-formed since uv adoption
))
