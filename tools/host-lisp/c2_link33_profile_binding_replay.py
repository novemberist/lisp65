#!/usr/bin/env python3
"""Bind the immutable green Link-33 WPLTO profile to its canonical object."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


WPLTO_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link33-bss-triage-facade15-placement-probe")
WPLTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-facade15-placement-probe-receipt.json")
WPLTO_RECEIPT_SHA = (
    "59209a27d73a976df4f74f57683f720b9d6a1cfe6633c74f2bb291923351fa3f")
WPLTO_RESOLVED = WPLTO_OUT / "resolved-profile.txt"
WPLTO_RESOLVED_SHA = (
    "37b5fa04b53dba843a2d0ae0aeef89d201400117460d1e9eb00453805ff6da9b")
PROBE_DRIVER = ROOT / "tools/host-lisp/c2_link33_bss_triage_probe.py"
PRODUCT_DRIVER = ROOT / "tools/host-lisp/c2_link33_bss_triage_product_link.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-product-profile-binding-replay-receipt.json")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def fields(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "input_sha256":
            continue
        require(key not in rows, f"duplicate resolved-profile field: {key}")
        rows[key] = value
    return rows


def source_single_truth_gate() -> dict[str, str]:
    results: dict[str, str] = {}
    for path in (PROBE_DRIVER, PRODUCT_DRIVER):
        source = path.read_text(encoding="utf-8")
        require("import c2_link33_product_profile as PROFILE" in source,
                f"{path.name} does not import the canonical profile")
        require("FEATURES = PROFILE.feature_defines()" in source,
                f"{path.name} restates product feature defines")
        require("PROFILE.configure(P)" in source,
                f"{path.name} does not consume the canonical configuration")
        forbidden = (
            "P.configure_append_slices(",
            "P.configure_session_emitter_state(",
            "P.configure_e000_reopening()",
            "P.configure_bss_triage()",
        )
        require(not any(token in source for token in forbidden),
                f"{path.name} reconstructs a canonical profile field")
        results[path.name] = "passed-canonical-profile-only"
    return results


def check() -> dict[str, Any]:
    require(sha(WPLTO_RECEIPT) == WPLTO_RECEIPT_SHA,
            "immutable WPLTO receipt drift")
    require(sha(WPLTO_RESOLVED) == WPLTO_RESOLVED_SHA,
            "immutable WPLTO resolved-profile drift")
    old = json.loads(WPLTO_RECEIPT.read_text(encoding="utf-8"))
    require(old.get("status")
            == "FIRST RED: sole Whole-Program-LTO placement probe failed"
            and old["execution_accounting"]["successful_seed_links"] == 1,
            "historical WPLTO receipt is not the approved structural profile")
    row = fields(WPLTO_RESOLVED)
    data = PROFILE.value()
    require(row.get("feature_defines") == ",".join(data["feature_defines"]),
            "WPLTO feature set differs from canonical profile object")
    require(row.get("append_slice_count") == str(len(data["append_slices"])),
            "WPLTO append count differs from canonical profile object")
    require(row.get("session_emitter_cpu_state_bytes")
            == str(data["session_emitter_state_bytes"]),
            "WPLTO emitter state differs from canonical profile object")
    require(row.get("fixed_facade_vector_count")
            == str(data["fixed_facade"]["vector_count"])
            and int(row.get("fixed_facade_handle_normalize", "-1"), 0)
            == data["fixed_facade"]["handle_normalize_vma"],
            "WPLTO facade differs from canonical profile object")
    PROFILE.configure(P)
    source_gate = source_single_truth_gate()
    return {
        "format": "lisp65-c2-link33-profile-binding-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-profile-object-binding-pure-replay-no-link",
        "product_profile_object": PROFILE.receipt_identity(),
        "historical_green_wplto_profile": {
            "receipt": bind(WPLTO_RECEIPT),
            "resolved_profile": bind(WPLTO_RESOLVED),
            "exact_feature_defines": 9,
            "exact_append_slices": 21,
            "session_emitter_state_bytes": 10,
            "fixed_facade_vectors": 15,
            "fixed_facade_handle_normalize_vma": 0xB5EE,
            "equivalent_to_profile_object_sha256": PROFILE.sha256(),
        },
        "single_truth_source_gate": source_gate,
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "product_links": 0, "hardware_runs": 0,
        },
        "claim_limit": (
            "The immutable green WPLTO configuration is exactly represented "
            "by the canonical profile object. No capacity, product-link or "
            "hardware result is newly claimed."),
        "next_gate": (
            "fresh Link 33 must report the same profile-object SHA before "
            "any seed or product link"),
    }


def run() -> dict[str, Any]:
    require(not RECEIPT.exists(), "profile binding replay is one-shot")
    value = check()
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = check() if args.action == "check" else run()
    print("c2-link33-profile-binding-replay: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, PROFILE.ProfileError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-link33-profile-binding-replay: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
