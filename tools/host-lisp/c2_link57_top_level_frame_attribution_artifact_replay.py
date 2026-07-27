#!/usr/bin/env python3
"""Read-only qualification of the completed frame-attribution WPLTO."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_top_level_frame_attribution_gate as ATTR  # noqa: E402


SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link57-top-level-frame-attribution-wplto3")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-wplto2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
SESSION = SOURCE / "runtime-overlays-session-final.json"
PROFILE = SOURCE / "resolved-profile.txt"
INTERNAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-top-level-frame-attribution-wplto3-internal.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-top-level-frame-attribution-wplto3-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-top-level-frame-attribution-artifact-replay-receipt.json")
REPORT = SOURCE / "frame-attribution-artifact-replay.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha(path),
            "mode": oct(path.stat().st_mode & 0o777),
        }
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def main() -> int:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "frame-attribution artifact replay is one-shot")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "diagnostic WPLTO tree is not immutable")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    source = ATTR.validate(ATTR.source_bundle())
    source["mutations_rejected"] = ATTR.mutation_tests(ATTR.source_bundle())
    linked = ATTR.linked_gate(ELF, READOBJ)
    gates = internal["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    session = json.loads(SESSION.read_text(encoding="utf-8"))
    baseline = json.loads(
        (BASELINE / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    baseline_slices = {row["name"]: row for row in baseline["slices"]}
    current_slices = {row["name"]: row for row in session["slices"]}
    deltas = {
        name: current_slices[name]["file_size"]
              - baseline_slices[name]["file_size"]
        for name in sorted(current_slices)
        if current_slices[name]["file_size"]
           != baseline_slices[name]["file_size"]
    }
    profile = PROFILE.read_text(encoding="utf-8")
    require(
        internal["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal["execution_accounting"]["product_closure_links"] == 1
        and first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and gates["status"] == "passed"
        and internal["fresh_prelink_gates"]["status"] == "passed"
        and internal["fresh_real_abi_gate"]["status"] ==
            "passed-all-assembler-leaf-abi-contracts"
        and all(
            (row.get("status") if isinstance(row, dict) else row) == "passed"
            for row in internal["fresh_generic_gates"].values()),
        "completed diagnostic WPLTO gate chain is not wholly green",
    )
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] == 33
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] == 58
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and session["storage"]["size"] == 65438
        and max(row["memory_size"] for row in session["slices"]) <= 1792,
        "frame-attribution diagnostic exceeded a bound wall or slice cap",
    )
    require(
        "LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC" in profile
        and baseline["storage"]["size"] == session["storage"]["size"]
        and len(deltas) == 14
        and sum(deltas.values()) == 87,
        "diagnostic feature or overlay attribution drift",
    )
    require(before == snapshot(SOURCE),
            "read-only frame-attribution replay modified WPLTO artifacts")
    value = {
        "format":
            "lisp65-c2-top-level-frame-attribution-artifact-replay-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-nonpromotable-frame-attribution-WPLTO-all-walls-green",
        "promotable": False,
        "authority": {
            "contract": bind(ATTR.CONTRACT),
            "source_gate": bind(Path(ATTR.__file__)),
            "internal_WPLTO": bind(INTERNAL),
            "inherited_checker_first_red": bind(FIRST_RED),
            "resolved_profile": bind(PROFILE),
        },
        "source_contract_gate": source,
        "linked_dataflow_gate": linked,
        "capacity": {
            "walls": walls,
            "session_family_bytes": capacity["session_family_bytes"],
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
            "slice_cap_bytes": capacity["slice_cap_bytes"],
            "largest_slice_bytes":
                max(row["memory_size"] for row in session["slices"]),
            "resident_text_delta_bytes":
                38 - walls["bank0_text_headroom_bytes"],
            "ordinary_bss_delta_bytes": 0,
            "fixed_hot_block_delta_bytes": 0,
            "resident_island_delta_bytes": 0,
            "e000_delta_bytes": 0,
            "session_packed_delta_bytes": 0,
            "overlay_payload_delta_bytes": deltas,
            "overlay_payload_delta_total_bytes": sum(deltas.values()),
        },
        "identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "session_family": bind(SOURCE / "runtime-overlays-session-final.bin"),
            "nonpromotable": True,
        },
        "measurement_contract": {
            "capture_address": "0x00c1e5",
            "capture_bytes": 15,
            "delta_formula": "(next-current)&0xff",
            "reject_if_complete_interval_frames_gte": 256,
            "latency_attempts_consumed": 0,
            "acceptance_claim": "none",
        },
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "compiler_or_linker_runs_in_this_replay": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "next_gate":
            "one nonpromotable hardware attribution run; do not perform "
            "latency acceptance attempt 2",
    }
    # The source tree is frozen already; the report deliberately lives beside
    # the external receipt instead of mutating that immutable artifact tree.
    report = REPORT
    write(report, value)
    value["report"] = bind(report)
    write(RECEIPT, value)
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link57-frame-attribution-artifact-replay: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} markers=15")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ReplayError,
        ATTR.GateError,
        ATTR.ELF.ElfTruthError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-frame-attribution-artifact-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
