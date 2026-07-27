#!/usr/bin/env python3
"""Preflight the product-shaped CRC-convergence WPLTO probe."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/vm_runtime_overlay.c"
CONTRACT = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-runtime-overlay-crc-convergence-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-runtime-overlay-crc-convergence-wplto-preflight-first-red.json")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"required artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "CRC-convergence WPLTO preflight already consumed")
    source = SOURCE.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    receipt = json.loads(CONTRACT_RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("status") ==
            "passed-crc-convergence-contract-product-not-implemented",
            "CRC-convergence contract receipt is not green")

    anchors = {
        "transaction_cache_dispatch":
            "verifier_index = rtov_transaction_context_if_ready(&verify, 0u);",
        "trusted_path_starts_at_record_verifier":
            "if (!RTOV_TRANSACTION_TRUSTED()) return 0;",
        "record_verifier_standalone_read":
            "context->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +",
        "only_cached_catalog_scalars":
            "rtov_transaction_payload_off = verify->payload_off;",
    }
    for label, token in anchors.items():
        require(token in source, f"source anchor absent: {label}")

    seams = contract.get("covered_seams", [])
    selected = [row for row in seams
                if row.get("id") == "requested-record-entry"]
    require(len(selected) == 1, "contract seam 3 absent or duplicated")
    require(selected[0].get("disposition") ==
            "capture-requested-record-during-successful-pass-and-remove-standalone-read",
            "contract no longer eliminates the selected-record read")
    require(contract.get("record_read_rule", {}).get("second_record_buffer") ==
            "forbidden",
            "contract no longer pins zero extra record-buffer bytes")

    # Model the exact two-call edge.  The first call starts at verifier zero
    # and may capture its selected record during the directory pass.  Once the
    # transaction cache is trusted, the second call starts at verifier one;
    # no directory bytes are visited from which its different record can be
    # captured.  The cache contains only payload_off/image_limit/count.
    model = {
        "first_slot": {
            "transaction_trusted_on_entry": False,
            "first_verifier_index": 0,
            "directory_pass_visits_selected_record": True,
        },
        "second_distinct_slot": {
            "transaction_trusted_on_entry": True,
            "first_verifier_index": 1,
            "directory_pass_visits_selected_record": False,
            "authenticated_expected_record_bytes_available": False,
        },
        "cached_fields": ["payload_off_u16", "image_limit_u16", "count_u8"],
        "record_bytes_required": 32,
        "record_digest_in_l65r_entry": False,
    }
    require(model["second_distinct_slot"]["first_verifier_index"] == 1,
            "transaction model did not reach the conflicting edge")

    value = {
        "format": "lisp65-c2-crc-convergence-wplto-preflight-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": (
            "FIRST RED: selected-record capture conflicts with the trusted "
            "transaction fast path before WPLTO"),
        "claim_limit": (
            "Source/contract preflight only. No compiler, product link, "
            "capacity claim, product identity, or hardware execution."),
        "authority": {
            "contract": bind(CONTRACT),
            "contract_receipt": bind(CONTRACT_RECEIPT),
            "implementation_source": bind(SOURCE),
        },
        "conflict": {
            "contract_claim": (
                "Seam 3 removes the standalone selected-record read and "
                "uses no second record buffer."),
            "product_invariant": (
                "After the first append member authenticates the family, "
                "later members start at verifier index 1 and deliberately "
                "skip the directory pass."),
            "missing_proof_material": (
                "The transaction cache retains three catalog scalars, not "
                "the 32-byte record or a per-record content digest."),
            "consequence": (
                "Only the first selected record can be captured during the "
                "successful aggregate pass. A later distinct slot would "
                "either retain an unproved read or re-run the directory, "
                "silently undoing transaction amortization."),
            "two_call_model": model,
        },
        "rejected_silent_workarounds": [
            {
                "option": "re-run-full-directory-for-every-record",
                "reason": (
                    "Restores a proof but removes the approved once-per-"
                    "transaction authentication and reintroduces hot-path "
                    "DMA/CRC work."),
            },
            {
                "option": "cache-all-records-or-add-second-buffer",
                "reason": (
                    "Violates the zero-extra-buffer contract and requires a "
                    "new placement/capacity decision."),
            },
            {
                "option": "compile-generated-record-copy",
                "reason": (
                    "Creates a second metadata truth unless the format gains "
                    "an explicitly bound per-record digest/index."),
            },
        ],
        "review_options": [
            "add an emissions-derived per-record digest/index to the trusted transaction metadata",
            "retain the standalone read and define a different content-bound completion proof",
            "amend the transaction-amortization contract and accept a measured directory reproof cost",
        ],
        "capacity": {
            "status": "not-reached",
            "e000_delta_bytes": "n/a",
            "all_bound_walls": "n/a",
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "whole_program_lto_runs": 0,
            "product_closure_links": 0,
            "hardware_runs": 0,
            "product_bytes_emitted": 0,
        },
        "rollback": {
            "status": "complete-before-receipt",
            "probe_define_present": "LISP65_RTOV_CRC_CONVERGENCE" in source,
            "timeout_status_present": "VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT" in source,
        },
        "next_gate": "Class-C contract decision; product link and hardware remain blocked",
    }
    require(value["rollback"]["probe_define_present"] is False,
            "aborted convergence source branch still present")
    require(value["rollback"]["timeout_status_present"] is False,
            "aborted timeout product status still present")
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    RECEIPT.chmod(0o444)
    print(value["status"])
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
