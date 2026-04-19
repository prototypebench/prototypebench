"""Parse a test-only diff to recover the set of added/modified test functions.

Used as a fallback when the base commit cannot collect the patched tests
(e.g. PR #2104: test_patch imports a symbol the base implementation lacks,
so pytest emits a file-level collection error and no per-test nodeids).

We're deliberately permissive — any `+def test_*` inside a `+++ b/...` block
counts. The result is intersected with the head run's *passing* nodeids
upstream, so noise (lines that happen to look like test defs in comments)
is filtered there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `+def test_foo(` — single `+` (not `++`/`+++`), optional indent for class
# methods, then a test function.
_ADDED_TEST_RE = re.compile(r"^\+(?!\+)\s*def (test_\w+)\s*\(")
# `+    def test_foo(` inside a class body still matches the same regex (the
# leading `+` precedes whitespace, then `def`).

_FILE_HEADER_RE = re.compile(r"^\+\+\+ b/(.+?)\s*$")
_CLASS_HEADER_RE = re.compile(r"^\+\s*class (Test\w+)\s*[\(:]")


@dataclass(frozen=True)
class AddedTest:
    file_path: str        # post-image path (e.g. "backend/tests/api/routes/test_x.py")
    test_name: str        # e.g. "test_create_item"
    class_name: str | None = None  # e.g. "TestItems" if inside a +class block


def parse_added_tests(test_patch: str) -> list[AddedTest]:
    """Return the (file, [class], test) tuples added by the diff.

    Only inspects `+` lines (additions). Doesn't try to detect *removals* —
    a removed test is no longer relevant to FAIL_TO_PASS regardless.
    """
    out: list[AddedTest] = []
    current_file: str | None = None
    current_class: str | None = None
    for line in test_patch.splitlines():
        fh = _FILE_HEADER_RE.match(line)
        if fh:
            current_file = fh.group(1)
            current_class = None
            continue
        if line.startswith("@@"):
            # New hunk — class context resets to "unknown" since the +class
            # marker only appears in the hunk that defines it. We won't try
            # to track class context across hunks; it's noisy and we'd rather
            # over-include than miss tests.
            current_class = None
            continue
        if current_file is None:
            continue
        ch = _CLASS_HEADER_RE.match(line)
        if ch:
            current_class = ch.group(1)
            continue
        m = _ADDED_TEST_RE.match(line)
        if m:
            out.append(
                AddedTest(file_path=current_file, test_name=m.group(1), class_name=current_class)
            )
    return out


def candidate_nodeids(added: AddedTest, *, backend_root: str = "backend/") -> list[str]:
    """Generate plausible pytest nodeid strings for a parsed test.

    pytest nodeids inside the backend run are relative to backend/ (we cd into
    backend/ before invoking pytest). So strip the leading `backend/` from
    file_path when present.

    Multiple candidates are returned because the same test can appear under
    `<file>::<test>` or `<file>::<class>::<test>` and we don't always know
    the class context with certainty.
    """
    rel = added.file_path
    if rel.startswith(backend_root):
        rel = rel[len(backend_root):]
    out: list[str] = [f"{rel}::{added.test_name}"]
    if added.class_name:
        out.append(f"{rel}::{added.class_name}::{added.test_name}")
    return out
