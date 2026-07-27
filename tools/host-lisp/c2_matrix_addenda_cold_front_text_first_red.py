#!/usr/bin/env python3
"""Bind the real Bank-0 text First Red from E5's cold-front WPLTO."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASELINE = ROOT / (
    "build/c2.2/substitution/link58-matrix-addenda-cold-placement-wplto")
CURRENT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-wplto-replay2")
BASELINE_MAP = BASELINE / "resident-island-seed.prg.map"
CURRENT_MAP = CURRENT / "resident-island-seed.prg.map"
BASELINE_LTO = BASELINE / "resident-island-seed.prg.lto.o"
CURRENT_LTO = CURRENT / "resident-island-seed.prg.lto.o"
PRODUCT = CURRENT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
STRUCTURE = CURRENT / "product-substitution-link.json"
BALANCE = CURRENT / "substitution-balance.json"
SESSION = CURRENT / "runtime-overlays-session-final.json"
WPLTO_FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-receipt.json")
WPLTO_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-internal.json")
REPLAY_PARTIAL = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-artifact-replay/"
    "final-island-single-runtime-identity.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-text-capacity-first-red-"
    "receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"


class DiagnosisError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"diagnosis input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def map_rows(path: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        r"(\.[A-Za-z0-9_.$-]+)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(4) not in rows:
            rows[match.group(4)] = {
                "address": int(match.group(1), 16),
                "load_address": int(match.group(2), 16),
                "bytes": int(match.group(3), 16),
            }
    return rows


def symbols(path: Path) -> dict[str, int]:
    output = subprocess.run(
        [str(NM), "-S", "--size-sort", str(path)],
        cwd=ROOT, text=True, capture_output=True, check=True).stdout
    result: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            try:
                result[fields[3]] = int(fields[1], 16)
            except ValueError:
                pass
    return result


def main() -> int:
    require(not RECEIPT.exists(), "cold-front capacity receipt is one-shot")
    first = json.loads(WPLTO_FIRST_RED.read_text(encoding="utf-8"))
    internal = json.loads(WPLTO_INTERNAL.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"] ==
            "retired L65E shape/capacity drift"
        and internal["execution_accounting"]["product_closure_links"] == 1,
        "completed WPLTO/checker First Red drift")
    before = map_rows(BASELINE_MAP)
    after = map_rows(CURRENT_MAP)
    before_symbols = symbols(BASELINE_LTO)
    after_symbols = symbols(CURRENT_LTO)
    structure = json.loads(STRUCTURE.read_text(encoding="utf-8"))
    balance = json.loads(BALANCE.read_text(encoding="utf-8"))
    session = json.loads(SESSION.read_text(encoding="utf-8"))

    text_end = after[".text"]["address"] + after[".text"]["bytes"]
    text_headroom = 0xB4A3 - text_end
    baseline_text_end = (
        before[".text"]["address"] + before[".text"]["bytes"])
    baseline_text_headroom = 0xB4A3 - baseline_text_end
    deltas = {
        name: after_symbols.get(name, 0) - before_symbols.get(name, 0)
        for name in (
            "lisp_abort_symbol", "lisp65_error_raise_pending",
            "c2_product_install")
    }
    slices = {row["name"]: row for row in session["slices"]}
    require(
        baseline_text_headroom == 33
        and text_headroom == 12
        and deltas == {
            "lisp_abort_symbol": 22,
            "lisp65_error_raise_pending": -29,
            "c2_product_install": 28}
        and sum(deltas.values()) == 21
        and after[".lisp65_rt_c2append_roots_fronts"]["bytes"] == 1510
        and after[".lisp65_rt_c2append_reserve_transient_bounds"]["bytes"]
            == 986
        and after[".lisp65_rt_l65e"]["bytes"] == 1204
        and slices["c2-append-roots-fronts"]["memory_size"] == 1510
        and slices["c2-append-reserve-transient-bounds"]["memory_size"] == 986
        and structure["actual_e000_future_margin_bytes"] == 56
        and structure["ordinary_bank0_bss_headroom_bytes"] == 213
        and structure["fixed_bank0_headroom_bytes"] == 33
        and balance["currencies"]["runtime_overlay_bank"][
            "session_image_bytes"] == 65438,
        "cold-front WPLTO attribution drift")

    value = {
        "format":
            "lisp65-c2.2-matrix-addenda-cold-front-text-first-red-v1",
        "recorded_on": "2026-07-23",
        "status":
            "FIRST RED: E5 cold-front placement closes Session and E000 "
            "but leaves Bank-0 text below its noise reserve",
        "promotable": False,
        "authority": {
            "WPLTO_attempt": bind(WPLTO_FIRST_RED),
            "WPLTO_internal_diagnosis": bind(WPLTO_INTERNAL),
            "baseline_map": bind(BASELINE_MAP),
            "current_map": bind(CURRENT_MAP),
            "baseline_LTO_object": bind(BASELINE_LTO),
            "current_LTO_object": bind(CURRENT_LTO),
            "frozen_product": bind(PRODUCT),
            "frozen_ELF": bind(ELF),
            "generic_structure": bind(STRUCTURE),
            "substitution_balance": bind(BALANCE),
            "session_package": bind(SESSION),
            "class_A_replay_partial": bind(REPLAY_PARTIAL),
            "driver": bind(Path(__file__)),
        },
        "walls": {
            "bank0_text": {
                "baseline_headroom_bytes": baseline_text_headroom,
                "measured_headroom_bytes": text_headroom,
                "required_noise_headroom_bytes": 32,
                "deficit_bytes": 32 - text_headroom,
                "verdict": "red",
            },
            "E000": {
                "measured_headroom_bytes":
                    structure["actual_e000_future_margin_bytes"],
                "required_floor_bytes": 54,
                "headroom_above_floor_bytes":
                    structure["actual_e000_future_margin_bytes"] - 54,
                "reopen_gap0_overlap_bytes": 0,
                "verdict": "green",
            },
            "ordinary_BSS": {"headroom_bytes": 213, "verdict": "green"},
            "fixed_hot_block": {"headroom_bytes": 33, "verdict": "green"},
            "resident_island": {"headroom_bytes": 5, "verdict": "green"},
            "session_family": {
                "bytes": 65438,
                "headroom_bytes": 98,
                "limit_bytes": 65536,
                "verdict": "green",
            },
        },
        "cold_escape_result": {
            "reserve_transient_bounds": {
                "before_bytes":
                    before[
                        ".lisp65_rt_c2append_reserve_transient_bounds"
                    ]["bytes"],
                "after_bytes": 986,
                "delta_bytes": 986 - before[
                    ".lisp65_rt_c2append_reserve_transient_bounds"]["bytes"],
            },
            "roots_fronts": {
                "before_bytes":
                    before[".lisp65_rt_c2append_roots_fronts"]["bytes"],
                "after_bytes": 1510,
                "delta_bytes": 1510 - before[
                    ".lisp65_rt_c2append_roots_fronts"]["bytes"],
                "slice_cap_bytes": 1792,
                "headroom_bytes": 282,
            },
            "L65E": {
                "bytes": 1204,
                "slice_cap_bytes": 1320,
                "headroom_bytes": 116,
            },
            "result":
                "the authorized cold-phase escape removed the Session "
                "quantum and the E000 overlap exactly as intended",
        },
        "bank0_text_attribution": {
            "net_delta_bytes": 21,
            "objects": {
                "lisp_abort_symbol": {
                    "delta_bytes": deltas["lisp_abort_symbol"],
                    "reason":
                        "the new overlay caller forces the existing terminal "
                        "status-plus-detail seam to retain its full ABI form",
                },
                "retired_lisp65_error_raise_pending": {
                    "delta_bytes": deltas["lisp65_error_raise_pending"],
                    "reason":
                        "the superseded deferred seam disappeared",
                },
                "c2_product_install": {
                    "delta_bytes": deltas["c2_product_install"],
                    "reason":
                        "Whole-Program LTO control/liveness response to the "
                        "terminal-seam form; measured, not projected",
                },
            },
        },
        "gates": {
            "generic_product_structure": structure["status"],
            "session_pack": "passed-48-slices",
            "E5_host_and_renderer": "green-14-mutations",
            "BADOPCODE_and_BCODE_shape_replays":
                "green-current-333/68/803/1204",
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "stop_rule":
            "real product-capacity question; stop before successor link and "
            "all C1/B3/C3/D3/E5 hardware cutpoints",
        "rollback_line": "Link 57 remains untouched",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-cold-front-first-red: "
        "TEXT=12/32 (-20) E000=56/54 BSS=213 FIXED=33 "
        "ISLAND=5 SESSION=65438/65536")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiagnosisError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(
            "c2-matrix-addenda-cold-front-first-red: FAIL: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
