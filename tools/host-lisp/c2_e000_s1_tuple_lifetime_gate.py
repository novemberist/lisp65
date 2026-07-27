#!/usr/bin/env python3
"""Prove E000-S1's retired batch tuple exists only for live feature owners."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/vm_runtime_overlay.c"
FIXTURE = ROOT / "scripts/runtime-overlay-transaction-main.c"
STALE = ROOT / (
    "build/c2.2/preinstall-island-guard-host/link30-resident-island.bin")
BASE = ROOT / "build/runtime-overlay-smoke-host"
AUTH = ROOT / "build/runtime-overlay-transaction-host"
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-e000-s1-tuple-feature-lifetime-gate.json")
NAMES = ("rtov_batch_entry", "rtov_batch_crc", "rtov_batch_slot_id")
ENTRY_GUARD = (
    "#if defined(LISP65_RTOV_ISLAND_SPLIT_PROBE) || \\\n"
    "    defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND)")
SLOT_GUARD = (
    "#if defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND) || \\\n"
    "    defined(LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE) || \\\n"
    "    (defined(LISP65_C1_COMPILER_TIER) && \\\n"
    "     !defined(LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND))")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def source_errors(text: str) -> list[str]:
    errors: list[str] = []
    entry_guard = text.find(ENTRY_GUARD)
    entry = text.find("static uint16_t rtov_batch_entry;")
    crc = text.find("static uint16_t rtov_batch_crc;")
    slot_guard = text.find(SLOT_GUARD)
    slot = text.find("rtov_batch_slot_id;")
    state = text.find("static uint8_t rtov_island_state;")
    if min(entry_guard, entry, crc, slot_guard, slot, state) < 0:
        errors.append("tuple-feature-member-missing")
        return errors
    if not entry_guard < entry < crc < slot_guard < slot < state:
        errors.append("tuple-feature-order")
    if "#endif" not in text[crc:slot_guard]:
        errors.append("entry-crc-guard-not-closed")
    if text[slot:state].count("#endif") < 2:
        errors.append("slot-feature-guard-not-closed")
    if "rtov_run_batch" in text or "vm_runtime_overlay_exec_batch_island" in text:
        errors.append("retired-batch-executor-present")
    return errors


def source_selftest(text: str) -> dict[str, str]:
    require(not source_errors(text),
            f"tuple lifetime source red: {source_errors(text)}")
    mutations = {
        "entry-guard-removed": text.replace(ENTRY_GUARD, "#if 1", 1),
        "slot-guard-removed": text.replace(SLOT_GUARD, "#if 1", 1),
        "entry-declaration-removed":
            text.replace("static uint16_t rtov_batch_entry;", "", 1),
        "same-payload-runner-restored":
            text + "\nvoid rtov_run_batch(void);\n",
    }
    for name, mutated in mutations.items():
        require(source_errors(mutated),
                f"tuple lifetime mutation accepted: {name}")
    return {name: "rejected" for name in mutations}


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True, capture_output=True,
        check=False, timeout=180)
    require(
        result.returncode == 0,
        f"command red ({' '.join(command)}): "
        f"{(result.stdout + result.stderr).strip()}")
    return (result.stdout + result.stderr).strip()


def tuple_symbols(binary: Path) -> dict[str, int]:
    text = run(["nm", "-S", "--size-sort", str(binary)])
    found: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[-1] in NAMES:
            found[fields[-1]] = int(fields[1], 16)
    return found


def build() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    mutations = source_selftest(source)
    run(["make", "-B", "build/runtime-overlay-smoke-host",
         "build/runtime-overlay-transaction-host"])
    env = os.environ.copy()
    env["ASAN_OPTIONS"] = "detect_leaks=1"
    env["UBSAN_OPTIONS"] = "halt_on_error=1"
    transaction_output = run([str(AUTH), str(STALE)], env=env)
    base_symbols = tuple_symbols(BASE)
    auth_symbols = tuple_symbols(AUTH)
    require(not base_symbols,
            f"dormant tuple survived narrow feature profile: {base_symbols}")
    require(
        auth_symbols == {
            "rtov_batch_entry": 2,
            "rtov_batch_crc": 2,
            "rtov_batch_slot_id": 1,
        },
        f"transaction-auth tuple identity drift: {auth_symbols}")
    require(
        "batch-S1=full-single-record-repeat" in transaction_output,
        "two-record E000-S1 host proof absent")
    return {
        "format": "lisp65-c2-E000-S1-tuple-feature-lifetime-gate-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-narrow-profile-zero-tuple-and-live-profile-exact-tuple",
        "source_contract": {
            "entry_crc_owners": [
                "serial split-installer handoff",
                "transaction-auth catalog tuple",
            ],
            "slot_owners": [
                "transaction-auth catalog tuple",
                "fixed retry probe result",
                "non-transaction-auth C1 abort result",
            ],
            "mutations": mutations,
        },
        "feature_matrix": {
            "narrow_prelink_shape": {
                "compiler": "-Wall -Wextra -Werror",
                "tuple_symbols": base_symbols,
                "expected_tuple_bytes": 0,
            },
            "transaction_auth_product_shape": {
                "compiler": "-Wall -Wextra -Werror -fsanitize=address,undefined",
                "tuple_symbols": auth_symbols,
                "expected_tuple_bytes": 5,
                "host_status": transaction_output,
            },
        },
        "authority": {
            "source": bind(SOURCE),
            "fixture": bind(FIXTURE),
            "narrow_binary": bind(BASE),
            "transaction_binary": bind(AUTH),
            "gate": bind(Path(__file__)),
        },
        "capacity": {
            "expected_current_product_delta_bytes": 0,
            "narrow_prelink_dormant_BSS_removed_bytes": 5,
            "WPLTO_truth": "pending",
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    require(not args.receipt.exists(), "tuple feature receipt is one-shot")
    value = build()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(args.receipt, 0o444)
    print(
        "c2-e000-s1-tuple-lifetime: PASS narrow=0 live=5 "
        f"mutations={len(value['source_contract']['mutations'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-e000-s1-tuple-lifetime: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
