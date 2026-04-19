"""Parse pytest JUnit XML into test-id → outcome maps."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

Outcome = Literal["passed", "failed", "error", "skipped"]


def _nodeid(tc: ET.Element) -> str:
    """Reconstruct the pytest nodeid from a <testcase> element.

    Example: classname='tests.api.routes.test_items' name='test_create_item'
             → 'tests/api/routes/test_items.py::test_create_item'
    """
    classname = tc.get("classname", "")
    name = tc.get("name", "")
    if not classname:
        return name
    # pytest emits classnames like 'tests.api.routes.test_items' or
    # 'tests.api.routes.test_items.TestItems'. The last segment may be a class.
    parts = classname.split(".")
    # Heuristic: if a segment starts uppercase it's a class; everything before
    # it is the module path.
    cls_idx = next((i for i, p in enumerate(parts) if p and p[0].isupper()), None)
    if cls_idx is None:
        module_path = "/".join(parts) + ".py"
        return f"{module_path}::{name}"
    module_path = "/".join(parts[:cls_idx]) + ".py"
    class_name = parts[cls_idx]
    return f"{module_path}::{class_name}::{name}"


def parse(xml_path: Path) -> dict[str, Outcome]:
    """Return nodeid → outcome. Outcomes follow pytest semantics."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    # JUnit can be a single <testsuite> or a <testsuites> wrapper.
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    out: dict[str, Outcome] = {}
    for suite in suites:
        for tc in suite.findall("testcase"):
            nodeid = _nodeid(tc)
            if tc.find("failure") is not None:
                out[nodeid] = "failed"
            elif tc.find("error") is not None:
                out[nodeid] = "error"
            elif tc.find("skipped") is not None:
                out[nodeid] = "skipped"
            else:
                out[nodeid] = "passed"
    return out


def passing(outcomes: dict[str, Outcome]) -> set[str]:
    return {nid for nid, o in outcomes.items() if o == "passed"}


def failing(outcomes: dict[str, Outcome]) -> set[str]:
    return {nid for nid, o in outcomes.items() if o in ("failed", "error")}
