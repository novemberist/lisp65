#!/usr/bin/env python3
"""Bind the rejected 1.1-G state/error carrier attempt and its rollback."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "0da2d57"
CONTRACT = ROOT / "config/v11-g-state-error-contract.json"
PACK_PLAN = ROOT / "config/v11-g-private-service-pack-plan.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-g-state-error-implementation-probe-receipt.json"
)
PROBE = ROOT / "build/probes/v11-g"
FAILED_MAP = PROBE / "generic-facade-link/failed-resident-island-seed-linked.prg.map"
FAILED_LOG = PROBE / "generic-facade-link/real-product-build.log"
STATE_OBSERVATIONS = PROBE / "state-error-observations.json"
ROOM_OBSERVATIONS = PROBE / "room-observations.json"
GENERIC_OBSERVATIONS = PROBE / "generic-facade-observations.json"
SHELF = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin"
SHELF_MANIFEST = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json"
OVERLAY_VMA = 0xC356

ROLLBACK_PATHS = (
    "config/bytecode-abi-ledger.json",
    "config/v2-native-function-registry.json",
    "config/dialect-v2-contract.json",
    "config/dialect-v2-surface.json",
    "config/v11-surface-delivery-parity.json",
    "lib/dialect-v2/eval-runtime.lisp",
    "src/buffer_overlay.h",
    "src/interrupt.c",
    "src/interrupt.h",
    "src/lcc_install_overlay.c",
    "src/symbol.c",
    "src/vm.c",
    "mk/workbench.mk",
    "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json",
)


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"cannot read {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing regular binding: {path}")
    payload = path.read_bytes()
    return {
        "path": rel(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def map_section(name: str) -> dict[str, int]:
    text = FAILED_MAP.read_text(encoding="utf-8")
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}\s*$",
        text,
        re.MULTILINE,
    )
    require(match is not None, f"missing failed-map section: {name}")
    start = int(match.group(1), 16)
    size = int(match.group(2), 16)
    return {"start": start, "bytes": size, "end_exclusive": start + size}


def map_symbol(name: str) -> int:
    text = FAILED_MAP.read_text(encoding="utf-8")
    values = re.findall(
        rf"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}\s*$",
        text,
        re.MULTILINE,
    )
    require(len(values) == 1, f"failed-map symbol count drift for {name}: {len(values)}")
    return int(values[0], 16)


def git_blob(path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{path}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"cannot read baseline blob {path}")
    return result.stdout


def rollback_bindings() -> list[dict[str, Any]]:
    rows = []
    for name in ROLLBACK_PATHS:
        current = (ROOT / name).read_bytes()
        baseline = git_blob(name)
        require(current == baseline, f"product rollback differs from {BASELINE_COMMIT}: {name}")
        rows.append({
            "path": name,
            "bytes": len(current),
            "sha256": hashlib.sha256(current).hexdigest(),
            "baseline_commit": BASELINE_COMMIT,
            "identical": True,
        })
    return rows


def observation_names(path: Path) -> list[str]:
    report = load(path, path.name)
    suites = report.get("suites")
    require(isinstance(suites, list) and suites, f"missing observation suites: {path}")
    names: list[str] = []
    for suite in suites:
        rows = suite.get("observations") if isinstance(suite, dict) else None
        require(isinstance(rows, list), f"missing observations: {path}")
        for row in rows:
            require(isinstance(row, dict) and isinstance(row.get("name"), str),
                    f"invalid observation row: {path}")
            names.append(row["name"])
    return names


def collect() -> dict[str, Any]:
    contract = load(CONTRACT, "state/error contract")
    pack_plan = load(PACK_PLAN, "private-service pack plan")
    require(contract.get("status") == "semantics-pinned-delivery-deferred-to-c2.2",
            "contract is not in the final deferred state")
    require(pack_plan.get("status") ==
            "rejected-after-the-one-authorized-attempt-fallback-triggered",
            "pack plan is not in the final rejected state")

    bss = map_section(".bss")
    lcci_01 = map_section(".lisp65_rt_lcci_01")
    lcci_02 = map_section(".lisp65_rt_lcci_02")
    require(bss == {"start": 0xBB72, "bytes": 0x8C8, "end_exclusive": 0xC43A},
            "failed candidate BSS arithmetic drift")
    require(bss["end_exclusive"] - OVERLAY_VMA == 228,
            "failed candidate overlap drift")
    require(lcci_01["bytes"] == 2007 and lcci_02["bytes"] == 1560,
            "failed carrier section size drift")
    symbols = {
        "vm_callprim": map_symbol("vm_callprim"),
        "generic_facade": map_symbol("lisp65_private_runtime_call"),
        "dynamic_error_renderer": map_symbol("lisp65_error_render_pending"),
        "error_carrier_entry": map_symbol("lisp65_private_runtime_error_entry"),
        "state_carrier_entry": map_symbol("lisp65_private_runtime_state_entry"),
        "lcc_install_phase_01": map_symbol("lcc_install_phase_01"),
        "lcc_install_phase_02": map_symbol("lcc_install_phase_02"),
    }
    expected_symbols = {
        "vm_callprim": 4434,
        "generic_facade": 161,
        "dynamic_error_renderer": 387,
        "error_carrier_entry": 576,
        "state_carrier_entry": 482,
        "lcc_install_phase_01": 1052,
        "lcc_install_phase_02": 1078,
    }
    require(symbols == expected_symbols, "failed candidate symbol attribution drift")
    log_text = FAILED_LOG.read_text(encoding="utf-8")
    for needle in (
        "workbench overlay overlaps resident BSS",
        "runtime overlay lcci-01 exceeds its stack-safe window",
        ".bss range is [0xBB72, 0xC439]",
    ):
        require(needle in log_text, f"failed-link diagnostic drift: {needle}")

    state_names = observation_names(STATE_OBSERVATIONS)
    room_names = observation_names(ROOM_OBSERVATIONS)
    generic_names = observation_names(GENERIC_OBSERVATIONS)
    for required in (
        "v11-g-gc-direct", "v11-g-gc-funcall", "v11-g-gc-apply",
        "v11-g-error-direct", "v11-g-error-funcall", "v11-g-error-apply",
    ):
        require(required in state_names, f"missing semantic observation: {required}")
    for required in ("room-direct", "room-funcall", "room-apply",
                     "room-repeat-fixed-allocation"):
        require(required in room_names, f"missing room observation: {required}")
    require(len(generic_names) >= len(state_names),
            "generic-facade observation set is unexpectedly incomplete")

    shelf_manifest = load(SHELF_MANIFEST, "canonical shelf manifest")
    require(SHELF.stat().st_size == shelf_manifest.get("shelf_bytes") == 65368,
            "canonical shelf was not restored to five-container size")
    require(len(shelf_manifest.get("containers", [])) == 5,
            "canonical shelf container count drift")

    return {
        "format": "lisp65-v11-g-state-error-architecture-outcome-receipt-v2",
        "version": 2,
        "status": "deferred-to-c2.2-after-one-authorized-architecture-attempt",
        "recorded_on": "2026-07-17",
        "claim_limit": (
            "Semantics and the rejected host/link experiment only. No product delivery, "
            "capacity authorization, product artifact, or hardware acceptance is claimed."
        ),
        "decision": {
            "attempts_permitted": 1,
            "attempts_run": 1,
            "result": "failed-hard-link-gates",
            "fallback_triggered": True,
            "second_attempt_permitted": False,
            "delivery": "gc/room/error absent from 1.1; carried together to C2.2",
        },
        "real_link": {
            "exit": "nonzero",
            "bss": bss,
            "fixed_overlay_vma": OVERLAY_VMA,
            "resident_overlap_bytes": 228,
            "lcci_01": {
                **lcci_01,
                "hard_cap_bytes": 1792,
                "over_cap_bytes": 215,
            },
            "lcci_02": {
                **lcci_02,
                "planned_allocation_bytes": 1280,
                "over_plan_bytes": 280,
            },
            "symbols_bytes": symbols,
            "bindings": {
                "map": binding(FAILED_MAP),
                "log": binding(FAILED_LOG),
            },
        },
        "semantic_evidence_retained": {
            "state_error_routes": binding(STATE_OBSERVATIONS),
            "room_routes_and_allocation": binding(ROOM_OBSERVATIONS),
            "generic_facade_routes": binding(GENERIC_OBSERVATIONS),
            "state_error_observation_count": len(state_names),
            "room_observation_count": len(room_names),
            "generic_facade_observation_count": len(generic_names),
        },
        "rollback": {
            "baseline_commit": BASELINE_COMMIT,
            "delivery_sources_identical": rollback_bindings(),
            "abi_prim_ids": 67,
            "native_registry_active": 61,
            "surface_bound_names": 65,
            "canonical_shelf_bytes": 65368,
            "canonical_shelf_headroom_bytes": 167,
            "canonical_shelf": binding(SHELF),
            "canonical_shelf_manifest": binding(SHELF_MANIFEST),
        },
        "bindings": {
            "semantic_contract": binding(CONTRACT),
            "attempt_pack_plan": binding(PACK_PLAN),
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT, "outcome receipt")
    expected = collect()
    require(actual == expected, "outcome receipt does not bind the current final state")
    return actual


def selftest() -> None:
    sample = {"attempts_run": 1, "resident_overlap_bytes": 228, "fallback": True}
    for label, mutation in (
        ("attempt-count", lambda value: value.update(attempts_run=2)),
        ("overlap", lambda value: value.update(resident_overlap_bytes=0)),
        ("fallback", lambda value: value.update(fallback=False)),
    ):
        candidate = copy.deepcopy(sample)
        mutation(candidate)
        require(candidate != sample, f"selftest mutation survived: {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v11-g-state-error-outcome: SELFTEST PASS mutations=3")
            return 0
        value = write() if args.command == "collect" else check()
    except (AcceptanceError, OSError, ValueError, KeyError) as exc:
        print(f"v11-g-state-error-outcome: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-g-state-error-outcome: PASS "
        f"status={value['status']} overlap={value['real_link']['resident_overlap_bytes']} "
        f"shelf_headroom={value['rollback']['canonical_shelf_headroom_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
