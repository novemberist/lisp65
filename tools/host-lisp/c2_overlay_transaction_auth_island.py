#!/usr/bin/env python3
"""Bind the authorized transaction-auth Island/no-inline host proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-overlay-transaction-auth-island-followup-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-overlay-transaction-auth-island-followup.md"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
HEADER = ROOT / "src/vm_runtime_overlay.h"
PRODUCT = ROOT / "src/c2_product_runtime.c"
FIXTURE = ROOT / "scripts/runtime-overlay-transaction-main.c"
MAKEFILE = ROOT / "mk/workbench.mk"
BINARY = ROOT / "build/runtime-overlay-transaction-host"
OLD_HOST = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-contract-probe-receipt.json")
OLD_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-capacity-first-red-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-overlay-transaction-auth-E5-cold-front-terminal-noreturn-"
    "rebind-receipt.json")
EXPECTED_OUTPUT = (
    "runtime-overlay-transaction: PASS catalog=once-per-transaction "
    "record+payload=per-slice same-generation-mutation=crc-red "
    "generation-change=reauthenticated batch-state=lifetime-exclusive"
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def source_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    product = PRODUCT.read_text(encoding="utf-8")
    fixture = FIXTURE.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")
    rows = {
        "island_feature_is_explicit": (
            "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND" in runtime
            and "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND" in makefile),
        "transaction_api_has_named_noinline_homes": (
            header.count("LISP65_C2_REOPEN_GAP0_FN") >= 2
            and header.count("LISP65_C2_REOPEN_GAP2_FN") >= 3
            and runtime.count("LISP65_C2_REOPEN_GAP0_FN\n"
                              "vm_runtime_overlay_status "
                              "vm_runtime_overlay_transaction_begin") == 1
            and runtime.count("LISP65_C2_REOPEN_GAP2_FN\n"
                              "vm_runtime_overlay_status "
                              "vm_runtime_overlay_transaction_end") == 1
            and "#define LISP65_C2_REOPEN_GAP0_FN "
                "LISP65_RESIDENT_ISLAND_FN" in header
            and "#define LISP65_C2_REOPEN_GAP2_FN "
                "LISP65_RESIDENT_ISLAND_FN" in header),
        "catalog_context_is_island_noinline": (
            "static LISP65_RESIDENT_ISLAND_FN uint8_t "
            "rtov_transaction_context(" in runtime),
        "state_reuses_batch_tuple": all(token in runtime for token in (
            "#define rtov_transaction_payload_off rtov_batch_entry",
            "#define rtov_transaction_image_limit rtov_batch_crc",
            "#define rtov_transaction_count rtov_batch_slot_id")),
        "invalidation_clears_discriminator": (
            "rtov_transaction_count = RTOV_TRANSACTION_INACTIVE;" in runtime),
        "batch_and_transaction_reject_overlap": (
            "if (rtov_busy || rtov_repeat || RTOV_TRANSACTION_ACTIVE())" in runtime
            and "if (RTOV_TRANSACTION_ACTIVE()) return "
                "VM_RUNTIME_OVERLAY_ERR_BUSY;" in runtime),
        "S1_batch_never_claims_shared_tuple": (
            "E000-S1 retires the Island-resident same-payload loop" in runtime
            and "status = vm_runtime_overlay_exec("
                "slot, context, entry_result);" in runtime
            and "rtov_repeat = repeat;" not in runtime),
        "product_entrypoints_are_single_copy": (
            product.count("LISP65_C2_TRANSACTION_AUTH_NOINLINE") == 2
            and product.count("__attribute__((noinline, used))") >= 2),
        "semantic_edges_remain": all(token in fixture for token in (
            "mutation_between_transactions",
            "generation_reauthenticates",
            "generation_switch_while_active",
            "batch_transaction_lifetimes_are_exclusive")),
        "host_build_uses_island_profile": (
            "-DLISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND" in makefile),
    }
    failed = sorted(name for name, passed in rows.items() if not passed)
    require(not failed, f"source gate red: {failed}")
    return {"status": "passed", "checks": rows}


def host_gate() -> dict[str, Any]:
    result = subprocess.run(
        ["make", "runtime-overlay-transaction-auth-smoke"], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=120,
    )
    detail = result.stdout + "\n" + result.stderr
    require(result.returncode == 0, "host gate red: " + detail.strip())
    require(EXPECTED_OUTPUT in detail, "host proof output drift")
    require(BINARY.is_file(), "host proof binary absent")
    symbols = subprocess.run(
        ["nm", "--defined-only", str(BINARY)], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=30,
    )
    require(symbols.returncode == 0, "host nm failed")
    forbidden = (
        "rtov_transaction_payload_off", "rtov_transaction_image_limit",
        "rtov_transaction_count", "rtov_transaction_active",
        "rtov_transaction_trusted",
    )
    require(not any(name in symbols.stdout for name in forbidden),
            "dedicated transaction BSS survived the Island profile")
    return {
        "status": "passed-asan-ubsan",
        "catalog_authentications_for_two_slices": 1,
        "record_and_payload_checks_for_two_slices": 2,
        "same_generation_between_transactions_mutation": "crc-red",
        "generation_change": "fresh-authentication-red",
        "batch_transaction_overlap": "busy-before-shared-state-change",
        "dedicated_transaction_bss_symbols": 0,
        "value_string": EXPECTED_OUTPUT,
        "binary": bind(BINARY),
    }


def build() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") == "owner-authorized-one-capacity-probe",
            "contract status drift")
    expected = contract["prerequisites"]
    require(sha(OLD_HOST) == expected["host_semantics_receipt_sha256"],
            "historical host receipt drift")
    require(sha(OLD_RED) == expected["capacity_first_red_receipt_sha256"],
            "historical first-red receipt drift")
    return {
        "format": "lisp65-c2-overlay-transaction-auth-island-contract-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-host-source-mutations-capacity-not-run",
        "authorization": {
            "contract": bind(CONTRACT),
            "document": bind(DOCUMENT),
            "historical_host_semantics": bind(OLD_HOST),
            "historical_capacity_first_red": bind(OLD_RED),
            "product_links": 0,
            "hardware_runs": 0,
        },
        "implementation": {
            "runtime": bind(RUNTIME),
            "header": bind(HEADER),
            "product_integration": bind(PRODUCT),
            "fixture": bind(FIXTURE),
            "makefile": bind(MAKEFILE),
        },
        "source_gate": source_gate(),
        "host_mutation_gate": host_gate(),
        "claim_limit": (
            "Host/source/mutation proof only. Island size, Bank-0 BSS, E000 "
            "identity and all product structure gates are not-run. No product "
            "SHA, hardware, latency, promotion or release claim."
        ),
        "next_gate": (
            "Exactly one product-shaped seed capacity/placement probe may run; "
            "any red stops before a product link."
        ),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            source_gate()
            print("c2-overlay-transaction-auth-island: SELFTEST PASS source")
            return 0
        data = canonical(build())
        if args.action == "write":
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            print("c2-overlay-transaction-auth-island: PASS host+source "
                  f"receipt={sha(RECEIPT)}")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                "contract receipt absent or drifted")
        print("c2-overlay-transaction-auth-island: CHECK PASS host+source")
        return 0
    except (GateError, OSError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        print(f"c2-overlay-transaction-auth-island: FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
