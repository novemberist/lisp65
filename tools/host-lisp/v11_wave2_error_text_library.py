#!/usr/bin/env python3
"""Bind the existing L65E overlay as the Wave-2 error-text library."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-wave2-error-text-library-contract.json"
SPEC = ROOT / "config/error-texts.json"
ERROR_CODES = ROOT / "config/error-code-contract.json"
WORKBENCH_MK = ROOT / "config/workbench.mk"
OVERLAY_SOURCE = ROOT / "src/error_overlay.c"
OVERLAY_HEADER = ROOT / "src/error_overlay.h"
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
TABLE_TOOL = ROOT / "tools/host-lisp/error_text_table.py"
CODE_TOOL = ROOT / "tools/host-lisp/error_code_contract.py"
SMOKE_TOOL = ROOT / "tools/host-lisp/error_overlay_smoke.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-error-text-library-receipt.json"
)


class ErrorTextAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ErrorTextAuditError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def run(*args: str) -> str:
    result = subprocess.run(
        ["python3", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"command failed: {' '.join(args)}\n{result.stdout}")
    return result.stdout.strip()


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    spec = load(SPEC)
    require(contract["status"] == "existing-l65e-runtime-overlay-is-canonical-delivery",
            "owner delivery classification drift")
    require(spec.get("format") == "L65E" and spec.get("version") == 1,
            "L65E format drift")
    entries = spec.get("entries")
    require(isinstance(entries, list) and len(entries) == 60,
            "stable error-text inventory drift")
    codes = [row.get("code") for row in entries]
    require(codes == list(range(1, 61)), "error-text codes are not contiguous 1..60")
    workbench = [row for row in entries if "workbench" in row.get("profiles", [])]
    omitted = [row for row in entries if "workbench" not in row.get("profiles", [])]
    require(len(workbench) == 43 and len(omitted) == 17,
            "Workbench error-text profile selection drift")
    require(all(row.get("audience") != "not-built" for row in workbench),
            "not-built error text leaked into Workbench")
    require(all(row.get("audience") == "not-built" or row.get("delivery") == "resident-only"
                for row in omitted),
            "unclassified Workbench omission")

    mk = WORKBENCH_MK.read_text(encoding="utf-8")
    require("--slice '36:error-text-renderer:.lisp65_rt_l65e:" in mk,
            "L65E runtime-overlay slice binding drift")
    require("WORKBENCH_ERROR_OVERLAY_MAX_BYTES := 1320" in mk,
            "L65E slice limit drift")
    source = OVERLAY_SOURCE.read_text(encoding="utf-8")
    interrupt = INTERRUPT_SOURCE.read_text(encoding="utf-8")
    require("L65E_SLICE uint8_t lisp65_error_overlay_entry" in source,
            "L65E entry is not overlay-resident")
    require("lisp65_error_render_pending" in interrupt
            and "emit('E')" in interrupt
            and "error_hex_digit" in interrupt,
            "stable resident fallback drift")

    table_selftest = run(rel(TABLE_TOOL), "selftest")
    code_selftest = run(rel(CODE_TOOL), "selftest")
    smoke = run(rel(SMOKE_TOOL))
    require("selftest ok cases=13" in table_selftest,
            "L65E mutation selftest count drift")
    require("selftest: PASS cases=9" in code_selftest,
            "error-code contract selftest did not pass")
    summary = re.search(
        r"profile=workbench codes=(\d+) active=(\d+) omitted=(\d+) bytes=(\d+)",
        smoke,
    )
    sections = re.search(
        r"sections: code=(\d+) table=(\d+) total=(\d+) headroom=(\d+)", smoke
    )
    require(summary is not None and tuple(map(int, summary.groups())) == (60, 43, 17, 770),
            "L65E smoke profile summary drift")
    require(sections is not None and tuple(map(int, sections.groups())) == (470, 770, 1240, 80),
            "L65E linked section accounting drift")
    require("tag-first+text+symbol+textless+alloc0+busy/latch" in smoke,
            "L65E behavioral smoke coverage drift")

    return {
        "format": "lisp65-v11-wave2-error-text-library-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "passed-existing-delivery-no-product-change",
        "claim_limit": contract["claim_limit"],
        "bindings": {
            "contract": binding(CONTRACT),
            "text_spec": binding(SPEC),
            "error_code_contract": binding(ERROR_CODES),
            "workbench_profile": binding(WORKBENCH_MK),
            "overlay_source": binding(OVERLAY_SOURCE),
            "overlay_header": binding(OVERLAY_HEADER),
            "interrupt_source": binding(INTERRUPT_SOURCE),
            "table_tool": binding(TABLE_TOOL),
            "code_tool": binding(CODE_TOOL),
            "smoke_tool": binding(SMOKE_TOOL),
        },
        "delivery": {
            "format": "L65E-v1",
            "slice": 36,
            "name": "error-text-renderer",
            "roles": ["runtime", "reusable"],
            "limit_bytes": 1320,
            "code_bytes": 470,
            "table_bytes": 770,
            "total_bytes": 1240,
            "headroom_bytes": 80,
            "stable_codes": 60,
            "workbench_active": 43,
            "workbench_omitted": 17,
        },
        "evidence": {
            "table_mutation_cases": 13,
            "code_contract_selftest_cases": 9,
            "overlay_behaviors": [
                "tag-first", "text", "symbol", "textless", "allocation-free",
                "busy-latch",
            ],
            "resident_fallback": "Ehh-class output: E plus two hexadecimal code digits",
        },
        "capacity_delta": {
            "bank0_bytes": 0,
            "ext_bytes": 0,
            "fixed_overlay_bytes": 0,
            "runtime_overlay_bank_bytes": 0,
            "resident_island_bytes": 0,
            "installer_slice_bytes": 0,
            "symbols": 0,
            "namepool_bytes": 0,
            "directory_entries": 0,
            "shelf_bytes": 0,
            "reason": "The receipt accepts an already shipped bound runtime-overlay library.",
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    expected = collect()
    require(actual == expected, "Wave-2 error-text receipt drift")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args()
    value = write() if args.command == "collect" else check()
    delivery = value["delivery"]
    print("v11-wave2-error-text-library: PASS "
          f"slice={delivery['slice']} bytes={delivery['total_bytes']} "
          f"headroom={delivery['headroom_bytes']} delta=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
