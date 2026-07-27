#!/usr/bin/env python3
"""Bind the terminal-detail WPLTO's one-quantum aggregate First Red."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as PRODUCT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-inventory-replay2")
ELF = SOURCE / "lisp65-c2-substitution-linked.prg.elf"
MAP = SOURCE / "lisp65-c2-substitution-linked.prg.map"
BASE_MANIFEST = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2/"
    "runtime-overlays-session-final.json")
COMPLETION = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-artifact-completion2")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-"
    "aggregate-first-red-receipt.json")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def align(value: int) -> int:
    return math.ceil(value / 256) * 256


def main() -> int:
    require(not RECEIPT.exists(), "aggregate First Red is one-shot")
    baseline = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    sections = PRODUCT.section_table(ELF)
    slices = baseline["slices"]
    cursor = align(32 + len(slices) * 32)
    rows: list[dict[str, Any]] = []
    for row in slices:
        cursor = align(cursor)
        old = int(row["file_size"])
        new = int(sections[row["section"]]["bytes"])
        rows.append({
            "id": row["id"],
            "name": row["name"],
            "section": row["section"],
            "baseline_bytes": old,
            "current_bytes": new,
            "delta_bytes": new - old,
            "baseline_quantum_bytes": align(old),
            "current_quantum_bytes": align(new),
            "quantum_delta_bytes": align(new) - align(old),
            "current_file_offset": cursor,
        })
        cursor += new
    changed = [row for row in rows if row["delta_bytes"]]
    by_name = {row["name"]: row for row in rows}
    require(
        baseline["storage"]["size"] == 65438
        and len(rows) == 48
        and cursor == 65694
        and cursor - 65536 == 158
        and changed == [
            by_name["c2-append-reserve-transient-bounds"],
            by_name["error-text-renderer"],
        ]
        and by_name["c2-append-reserve-transient-bounds"][
            "baseline_bytes"] == 971
        and by_name["c2-append-reserve-transient-bounds"][
            "current_bytes"] == 1265
        and by_name["c2-append-reserve-transient-bounds"][
            "delta_bytes"] == 294
        and by_name["c2-append-reserve-transient-bounds"][
            "quantum_delta_bytes"] == 256
        and by_name["error-text-renderer"]["baseline_bytes"] == 1143
        and by_name["error-text-renderer"]["current_bytes"] == 1204
        and by_name["error-text-renderer"]["quantum_delta_bytes"] == 0,
        "terminal-detail aggregate attribution drift")
    value = {
        "format":
            "lisp65-c2-link58-terminal-detail-seam-aggregate-first-red-v1",
        "recorded_on": "2026-07-23",
        "status":
            "FIRST RED: terminal abort was modeled as returning and cost "
            "one session-family quantum",
        "promotable": False,
        "authority": {
            "WPLTO_elf": bind(ELF),
            "WPLTO_map": bind(MAP),
            "Link57_green_session_manifest": bind(BASE_MANIFEST),
            "attribution_driver": bind(Path(__file__)),
        },
        "session_family": {
            "baseline_bytes": baseline["storage"]["size"],
            "baseline_headroom_bytes": 65536 - baseline["storage"]["size"],
            "current_projected_bytes": cursor,
            "overflow_bytes": cursor - 65536,
            "records": len(rows),
        },
        "changed_slices": changed,
        "attribution": {
            "terminal_detail_phase_raw_growth_bytes": 294,
            "terminal_detail_phase_pack_growth_bytes": 256,
            "renderer_raw_growth_bytes": 61,
            "renderer_pack_growth_bytes": 0,
            "cause":
                "the target compiler retained a fictitious return path after "
                "lisp_abort_symbol and made the whole bounds function "
                "call-live",
            "correction":
                "the MOS callsite states its existing abort landing is "
                "non-returning; host fixture return semantics remain intact",
        },
        "failed_completion_tree": {
            "path": COMPLETION.relative_to(ROOT).as_posix(),
            "diagnostic":
                "runtime-overlay-bank rejected first-class-buffer-alloc "
                "after the projected image crossed 64 KiB",
        },
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "additional_compiler_runs": 0,
            "additional_linker_runs": 0,
            "hardware_runs": 0,
        },
        "next_gate":
            "one fresh WPLTO with the MOS terminal-control-flow truth",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-terminal-detail-aggregate-first-red: PASS "
        "session=65694 overflow=158 phase=+294/raw,+256/packed "
        "renderer=+61/raw,+0/packed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-terminal-detail-aggregate-first-red: FAIL "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
