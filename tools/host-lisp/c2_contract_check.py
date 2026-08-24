#!/usr/bin/env python3
"""Validate the approved C2.0 contract and inherited evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


HOST = Path(__file__).resolve().parent
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import evidence_era as ERA  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-address-identity-contract.json"
FREIGHT = ROOT / "config/c2-freight-triage.json"
MODEL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l65s-v4-layout-model-receipt.json"
)
AUDIT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-shelf-metadata-audit-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-address-identity-contract-receipt.json"
)
ENTRY_FIELD_WIDTHS = {
    "code_offset_u24": 3,
    "code_length_u16": 2,
    "literal_first_u16": 2,
    "literal_count_u8": 1,
    "export_name_offset_u16_or_ffff": 2,
    "arity_u8": 1,
    "flags_u8": 1,
    "diagnostic_ordinal_u16": 2,
    "reserved_u16_zero": 2,
}
SEALED_COMMIT = "6e9389408024580a375f52f223b4b6f5875f1ef6"


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


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


def validate_contract(contract: dict[str, Any], freight: dict[str, Any]) -> None:
    require(contract.get("format") == "lisp65-c2-address-identity-contract-v1",
            "contract format drift")
    require(contract.get("status") == "owner-approved-c2.1-proof-authorized",
            "contract approval status drift")
    require("All five review decisions approved" in contract.get("owner_approval", ""),
            "contract owner approval missing")
    require("approved on 2026-07-19" in contract.get("metadata_envelope", ""),
            "approved C2 metadata envelope missing")
    laws = contract.get("design_laws", {})
    require(set(laws) == {"substitution", "physical_address_domain", "immutability",
                          "attic_cache", "fail_fast"}, "design-law closure drift")
    logical = contract.get("logical_callable", {})
    require(logical.get("maximum_index") == 4095 and "12-bit" in logical.get("encoding", ""),
            "BCODE logical-handle contract drift")
    source = contract.get("source_address", {})
    require(source.get("encoding") == "region-id:u8 plus little-endian offset:u24",
            "source-address encoding drift")
    require(source.get("maximum_relative_offset") == 0x6FFFFF,
            "u24 shelf envelope drift")
    forbidden = source.get("forbidden", [])
    require(any("uintptr_t" in row for row in forbidden), "uintptr_t prohibition missing")
    shelf = contract.get("shelf_format", {})
    require(shelf.get("name") == "L65S-v4-direct" and shelf.get("record_limit") == 255,
            "shelf format drift")
    require(shelf.get("staging_limit") == 38400, "staging limit drift")
    entry = contract.get("direct_container", {}).get("entry_record", {})
    require(entry.get("bytes") == 16 and entry.get("code_length_limit") == 0xFFFF,
            "entry-record geometry drift")
    require("1..65535" in entry.get("code_length_rule", ""),
            "entry-record zero-length rejection missing")
    fields = entry.get("fields", [])
    require(fields == list(ENTRY_FIELD_WIDTHS), "entry-record field order drift")
    require(sum(ENTRY_FIELD_WIDTHS[field] for field in fields) == entry.get("bytes"),
            "entry-record field widths do not fill the declared record")
    require("0xffff" in entry.get("anonymous_sentinel", ""),
            "entry-record field/sentinel drift")
    literal = contract.get("direct_container", {}).get("literal_descriptor", {})
    require(literal.get("bytes") == 8 and len(literal.get("kinds", [])) == 7,
            "literal-descriptor closure drift")
    require("-16384..16383" in literal.get("fixnum_rule", ""),
            "literal Fixnum range is not pinned")
    mutable = contract.get("mutable_session_plane", {})
    require(len(mutable.get("publication_order", [])) == 7,
            "publication sequence drift")
    require("prior value" in mutable.get("export_rollback", "")
            and "reverse order" in mutable.get("export_rollback", ""),
            "late-bound export rollback journal missing")
    stages = contract.get("staged_swap", [])
    require([row.get("stage") for row in stages] == ["C2.0", "C2.1", "C2.2"],
            "staged-swap sequence drift")
    require("No product candidate contains a dual decoder" in contract.get("rollback_rule", ""),
            "dual-decoder prohibition missing")
    negatives = contract.get("required_negative_fixtures", [])
    require(len(negatives) == 17 and len(set(negatives)) == 17,
            "negative-fixture closure drift")
    require("zero-length entry" in negatives
            and "hot restage attempted in a live session" in negatives,
            "review-added negative fixtures missing")

    require(freight.get("format") == "lisp65-c2-freight-triage-v1"
            and freight.get("status") == "owner-approved-3-3-3",
            "freight status drift")
    require("2026-07-19" in freight.get("owner_approval", ""),
            "freight owner approval missing")
    rows = freight.get("items", [])
    require([row.get("rank") for row in rows].count("MUST") == 3,
            "MUST freight count drift")
    require([row.get("rank") for row in rows].count("SHOULD") == 3,
            "SHOULD freight count drift")
    require([row.get("rank") for row in rows].count("COULD") == 3,
            "COULD freight count drift")


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    freight = load(FREIGHT)
    validate_contract(contract, freight)
    obj = (ROOT / "src/obj.h").read_text(encoding="utf-8")
    require("#define BCODE_IMM_BASE 0x6000u" in obj, "BCODE base drift")
    require(re.search(r"#define MK_BCODE\(d\).+BCODE_IMM_BASE", obj),
            "BCODE constructor drift")
    vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    require("static uint8_t  dir_bank0" in vm and "static uint16_t dir_n" in vm,
            "current directory seam drift")

    model = load(MODEL)
    audit = load(AUDIT)
    variants = model.get("variants", {})
    require(set(variants) == {"catalog-widening-only",
                              "catalog-widening-plus-metadata-regions"},
            "inherited v4 variant set drift")
    require(all(row["artifact"]["bytes"] == 65367 for row in variants.values()),
            "inherited v4 model size drift")
    split = variants["catalog-widening-plus-metadata-regions"]
    require(split.get("selected_for_real_link") is True,
            "split v4 inheritance drift")
    require(audit.get("totals", {}).get("metadata") == 36260,
            "metadata total drift")
    require(audit.get("totals", {}).get("literal_machinery") == 27744,
            "literal machinery drift")

    return {
        "format": "lisp65-c2-address-identity-contract-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "owner-approved-c2.1-proof-authorized",
        "claim_limit": (
            "This receipt binds the owner-approved contract, its arithmetic and "
            "inherited evidence. It authorizes only the separate C2.1 internal "
            "proof target; it does not execute Attic code, change product bytes, "
            "authorize capacity or make a product claim."
        ),
        "bindings": {
            "verifier": ERA.era_bind(SEALED_COMMIT, ROOT / "tools/host-lisp/c2_contract_check.py"),
            "contract": ERA.era_bind(SEALED_COMMIT, CONTRACT),
            "freight": ERA.era_bind(SEALED_COMMIT, FREIGHT),
            "design_document": ERA.era_bind(SEALED_COMMIT, ROOT / "docs/planning/c2.0-address-identity-contract.md"),
            "design_inputs": ERA.era_bind(SEALED_COMMIT, ROOT / "docs/planning/c2.0-design-inputs.md"),
            "scope_memo": ERA.era_bind(SEALED_COMMIT, ROOT / "docs/planning/v1.2-scope-memo.md"),
            "v4_model": ERA.era_bind(SEALED_COMMIT, MODEL),
            "metadata_audit": ERA.era_bind(SEALED_COMMIT, AUDIT),
            "object_abi": ERA.era_bind(SEALED_COMMIT, ROOT / "src/obj.h"),
            "current_vm": ERA.era_bind(SEALED_COMMIT, ROOT / "src/vm.c"),
        },
        "validated": {
            "logical_callable_bits": 12,
            "logical_callable_maximum_index": 4095,
            "source_offset_bits": 24,
            "source_envelope_maximum_offset": 0x6FFFFF,
            "entry_record_bytes": 16,
            "literal_descriptor_bytes": 8,
            "negative_fixture_classes": 17,
            "dual_decoder_product_states": 0,
            "host_v4_variants_bytes_each": 65367,
            "inherited_metadata_bytes": 36260,
            "inherited_literal_machinery_bytes": 27744,
        },
        "freight": {
            "must": 3,
            "should": 3,
            "could": 3,
            "owner_confirmation": "approved 2026-07-19",
        },
        "next_authorized_action": "C2.1 separate internal proof target implementation and measurement only",
    }


def selftest() -> None:
    contract = load(CONTRACT)
    freight = load(FREIGHT)
    mutations = []
    for label, mutate in (
        ("dual-decoder", lambda c, f: c.__setitem__("rollback_rule", "mixed allowed")),
        ("address-width", lambda c, f: c["source_address"].__setitem__(
            "maximum_relative_offset", 0xFFFFFF)),
        ("freight-rank", lambda c, f: f["items"][0].__setitem__("rank", "COULD")),
        ("entry-width", lambda c, f: c["direct_container"]["entry_record"]["fields"].pop(7)),
        ("code-length", lambda c, f: c["direct_container"]["entry_record"].__setitem__(
            "code_length_limit", 255)),
        ("fixnum-range", lambda c, f: c["direct_container"]["literal_descriptor"].__setitem__(
            "fixnum_rule", "accept every i16 value")),
        ("export-journal", lambda c, f: c["mutable_session_plane"].__setitem__(
            "export_rollback", "restore watermarks only")),
    ):
        bad_c = copy.deepcopy(contract)
        bad_f = copy.deepcopy(freight)
        mutate(bad_c, bad_f)
        try:
            validate_contract(bad_c, bad_f)
        except ContractError:
            mutations.append(label)
    require(len(mutations) == 7, f"mutations not rejected: {mutations}")
    require(binding(ROOT / "src/vm.c") != ERA.era_bind(
                SEALED_COMMIT, ROOT / "src/vm.c"),
            "address-identity era binding collapsed to the living VM")


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    result = collect()
    require(RECEIPT.is_file(), "contract receipt missing")
    recorded = load(RECEIPT)
    require(recorded == result, "contract receipt drift; regenerate with --write")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("c2-contract-check: SELFTEST PASS mutations=7")
        return 0
    result = write() if args.write else check()
    print(
        "c2-contract-check: PASS status=approved c2.1-proof=authorized "
        f"negatives={result['validated']['negative_fixture_classes']} freight=3/3/3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
