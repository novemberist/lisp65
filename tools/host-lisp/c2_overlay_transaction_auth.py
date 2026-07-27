#!/usr/bin/env python3
"""Bind the owner-authorized C2 overlay transaction-auth host proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-overlay-transaction-auth-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-overlay-transaction-auth-addendum.md"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
HEADER = ROOT / "src/vm_runtime_overlay.h"
PRODUCT = ROOT / "src/c2_product_runtime.c"
FIXTURE = ROOT / "scripts/runtime-overlay-transaction-main.c"
MAKEFILE = ROOT / "mk/workbench.mk"
BINARY = ROOT / "build/runtime-overlay-transaction-host"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-contract-probe-receipt.json")
EXPECTED_OUTPUT = (
    "runtime-overlay-transaction: PASS catalog=once-per-transaction "
    "record+payload=per-slice same-generation-mutation=crc-red "
    "generation-change=reauthenticated"
)


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def function(text: str, name: str) -> str:
    marker = name + "("
    start = text.index(marker)
    start = text.rfind("\n", 0, start) + 1
    brace = text.index("{", start)
    depth = 0
    for at in range(brace, len(text)):
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return text[start:at + 1]
    raise ContractError(f"unterminated function: {name}")


def source_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    product = PRODUCT.read_text(encoding="utf-8")
    fixture = FIXTURE.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")
    execute = function(runtime, "vm_runtime_overlay_exec_family")
    begin = function(runtime, "vm_runtime_overlay_transaction_begin")
    end = function(runtime, "vm_runtime_overlay_transaction_end")
    select = function(runtime, "vm_runtime_overlay_select_family")
    fail = function(runtime, "rtov_fail")
    abort = function(runtime, "vm_runtime_overlay_abort_cleanup")
    install = function(product, "c2_product_install")
    staged = function(product, "c2_product_append_staged")
    rows = {
        "api_feature_guarded": (
            "#ifdef LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH" in header
            and "vm_runtime_overlay_transaction_begin(" in header
            and "vm_runtime_overlay_transaction_end(void)" in header),
        "catalog_cache_is_transaction_scoped": all(text in runtime for text in (
            "rtov_transaction_payload_off",
            "rtov_transaction_image_limit",
            "rtov_transaction_count",
            "rtov_transaction_active",
            "rtov_transaction_trusted")),
        "first_slice_runs_both_verifiers": (
            "verifier_index = 0" in execute
            and "verifier_index == 0" in execute
            and "rtov_transaction_trusted = 1" in execute),
        "later_slices_start_at_record_verifier": (
            "rtov_transaction_active && rtov_transaction_trusted" in execute
            and "verifier_index = 1" in execute
            and "slot >= rtov_transaction_count" in execute),
        "payload_crc_remains_per_slice": (
            "rtov_read(verify.file_off" in execute
            and "verify.payload_crc" in execute
            and "rtov_wipe()" in execute),
        "begin_is_session_generation_bound": all(text in begin for text in (
            "expected_family != LISP65_RUNTIME_OVERLAY_FAMILY_SESSION",
            "expected_generation != rtov_family_generation",
            "!expected_generation")),
        "end_discards_trust": "rtov_transaction_invalidate()" in end,
        "transport_failure_discards_trust": (
            "rtov_transaction_invalidate()" in fail),
        "abort_discards_trust": "rtov_transaction_invalidate()" in abort,
        "active_family_switch_fails_closed": (
            "rtov_transaction_active" in select
            and "rtov_fail(VM_RUNTIME_OVERLAY_ERR_BUSY)" in select),
        "product_install_has_one_outer_transaction": (
            install.count("vm_runtime_overlay_transaction_begin(") == 1
            and install.count("vm_runtime_overlay_transaction_end()") == 4
            and install.index("vm_runtime_overlay_transaction_begin(")
                < install.index("c2_session_emit_reset()")),
        "standalone_append_has_bounded_transaction": (
            staged.count("vm_runtime_overlay_transaction_begin(") == 1
            and staged.count("vm_runtime_overlay_transaction_end()") == 1),
        "no_e000_facade_growth": (
            "c2_facade_overlay_transaction" not in product
            and "vector_count\": 13" in (
                ROOT / "config/c2-kernal-unmap-contract.json"
            ).read_text(encoding="utf-8")),
        "required_mutations_are_present": all(text in fixture for text in (
            "mutation_between_transactions",
            "generation_reauthenticates",
            "generation_switch_while_active",
            "catalog_once_per_transaction")),
        "permanent_make_gate": (
            "runtime-overlay-transaction-auth-smoke" in makefile
            and "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH" in makefile
            and "LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES" in makefile),
    }
    failed = sorted(name for name, passed in rows.items() if not passed)
    require(not failed, f"source gate red: {failed}")
    return {"status": "passed", "checks": rows}


def host_gate() -> dict[str, Any]:
    result = subprocess.run(
        ["make", "runtime-overlay-transaction-auth-smoke"], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=120,
    )
    require(result.returncode == 0,
            "host mutation gate red: " + (result.stderr or result.stdout).strip())
    output = "\n".join(
        line.strip() for line in (result.stdout + "\n" + result.stderr).splitlines()
        if line.strip()
    )
    require(EXPECTED_OUTPUT in output, "host proof output drift")
    require(BINARY.is_file(), "host proof binary absent")
    return {
        "status": "passed-asan-ubsan",
        "catalog_authentications_for_two_slices": 1,
        "record_authentications_for_two_slices": 2,
        "payload_executions_for_two_slices": 2,
        "same_generation_between_transactions_payload_mutation":
            "rejected-before-entry-by-payload-crc",
        "new_generation_catalog_identity_mutation":
            "rejected-before-entry-by-fresh-catalog-authentication",
        "active_generation_switch": "rejected-and-fault-latched",
        "value_string": EXPECTED_OUTPUT,
        "binary": bind(BINARY),
    }


def build() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") == "owner-authorized-host-and-capacity-probe",
            "contract status drift")
    source = source_gate()
    host = host_gate()
    return {
        "format": "lisp65-c2-overlay-transaction-auth-contract-probe-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-host-source-mutations-capacity-not-run",
        "authorization": {
            "contract": bind(CONTRACT),
            "document": bind(DOCUMENT),
            "product_links": 0,
            "hardware_runs": 0,
        },
        "implementation": {
            "runtime": bind(RUNTIME),
            "header": bind(HEADER),
            "product_integration": bind(PRODUCT),
            "fixture": bind(FIXTURE),
        },
        "source_gate": source,
        "host_mutation_gate": host,
        "security_argument": {
            "catalog": (
                "One full catalog proof per append transaction; the selected "
                "family/generation and catalog outputs cannot change while active."
            ),
            "slice": (
                "Every slice retains record validation, target payload CRC and "
                "verified wipe; manipulated fresh data never inherits catalog trust."
            ),
            "invalidation": (
                "Trust is erased on end, transport error, abort, reset and any "
                "attempted family transition."
            ),
        },
        "claim_limit": (
            "Host/source/mutation proof only. Capacity and placement are not-run. "
            "No product SHA, product link, hardware, latency, promotion or release claim."
        ),
        "next_gate": (
            "Exactly one product-shaped seed capacity/placement probe may run with "
            "Bank-0 BSS, text, Island, all runtime slices and E000 delta reported."
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
            print("c2-overlay-transaction-auth: SELFTEST PASS source")
            return 0
        value = build()
        encoded = canonical(value)
        if args.action == "write":
            if RECEIPT.exists() and RECEIPT.read_bytes() != encoded:
                raise ContractError("refusing to overwrite divergent receipt")
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(encoded)
            os.chmod(RECEIPT, 0o444)
            print("c2-overlay-transaction-auth: PASS host+source "
                  f"receipt={sha(RECEIPT)}")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded,
                "contract receipt absent or drifted")
        print("c2-overlay-transaction-auth: CHECK PASS host+source")
        return 0
    except (ContractError, json.JSONDecodeError, OSError,
            subprocess.SubprocessError) as exc:
        print(f"c2-overlay-transaction-auth: FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
