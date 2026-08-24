#!/usr/bin/env python3
"""Permanent ordering gate for the R1 post-configuration scope projection."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tools/host-lisp/c2_v160_abort_driver_relocation_config.py"


class ProjectionRepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProjectionRepairError(message)


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (CONFIG.read_text(encoding="utf-8")
              if source_override is None else source_override)
    start = source.index("    def configure_root_source()")
    end = source.index("\n\n    configure_root_source._r1_abort_root_hook", start)
    body = source[start:end]
    ordered = ("projection = current()", "component = configure(product)",
        "live_projection = configured_scope_projection(product)",
        "validate_scope_projection(live_projection, component)",
        'projection["scopes"] = live_projection["scopes"]',
        "return projection")
    positions = [body.index(token) if token in body else -1
                 for token in ordered]
    require(all(position >= 0 for position in positions)
            and positions == sorted(positions)
            and body.count("configured_scope_projection(product)") == 1,
            "scope projection is captured before final configuration")
    return {"status": "PASS: configure precedes live projection and consumer",
        "ordered_operations": list(ordered),
        "live_projection_calls": 1,
        "returned_scope_source": "post-configuration configured state"}


def mutations() -> list[str]:
    source = CONFIG.read_text(encoding="utf-8")
    early = source.replace(
        "        component = configure(product)\n"
        "        live_projection = configured_scope_projection(product)\n",
        "        live_projection = configured_scope_projection(product)\n"
        "        component = configure(product)\n", 1)
    omitted = source.replace(
        '        projection["scopes"] = live_projection["scopes"]\n', "", 1)
    rejected = []
    for name, candidate in (("capture-before-configuration", early),
                            ("omit-live-scope-projection", omitted)):
        try:
            source_gate(candidate)
        except ProjectionRepairError:
            rejected.append(name)
    require(rejected == ["capture-before-configuration",
                         "omit-live-scope-projection"],
            "scope projection ordering mutation survived")
    return rejected


def preflight() -> dict[str, Any]:
    value = source_gate()
    value["mutations_rejected"] = mutations()
    return value


if __name__ == "__main__":
    try:
        value = preflight()
        print("R1 scope projection repair: PREFLIGHT PASS "
              f"mutations={len(value['mutations_rejected'])}")
    except ProjectionRepairError as error:
        print(f"R1 scope projection repair: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
