#!/usr/bin/env python3
"""Validate the non-authorizing C2 metadata-envelope addendum."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "config/c2-address-identity-contract.json"
PROPOSAL = ROOT / "config/c2-metadata-envelope-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.0-metadata-envelope-addendum.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-metadata-envelope-proposal-receipt.json"
)


class EnvelopeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EnvelopeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def validate(core: dict[str, Any], proposal: dict[str, Any]) -> None:
    require(core.get("status") == "owner-approved-c2.1-proof-authorized",
            "approved C2 core contract missing")
    require(proposal.get("format") == "lisp65-c2-metadata-envelope-proposal-v1"
            and proposal.get("status") == "owner-approved-c2.1-bytes-authorized",
            "proposal status drift")
    require("Option A" in proposal.get("owner_approval", "")
            and proposal.get("owner_decision") ==
            "local-24-byte-header approved; C2.1 must emit and decode this exact envelope",
            "metadata-envelope owner approval missing")
    options = proposal.get("options", [])
    require([row.get("id") for row in options] == [
        "local-24-byte-header", "expand-l65s-record", "proof-only-compile-time-counts"
    ], "option closure drift")
    require([row.get("assessment") for row in options] == [
        "recommended", "not-recommended", "rejected"
    ], "option assessment drift")

    contract = proposal.get("recommended_contract", {})
    header = contract.get("metadata_header", {})
    fields = header.get("fields", [])
    require(header.get("magic") == "C2I\\0" and header.get("bytes") == 24,
            "metadata header identity drift")
    require(sum(row.get("bytes", -1000) for row in fields) == 24,
            "metadata header field arithmetic does not close")
    require([row.get("name") for row in fields] == [
        "magic_4", "version_u8", "header_bytes_u8", "entry_bytes_u8",
        "literal_bytes_u8", "flags_u16_zero", "entry_count_u16",
        "literal_count_u16", "entries_offset_u16", "literals_offset_u16",
        "strings_offset_u16", "strings_bytes_u16", "reserved_u16_zero"
    ], "metadata header field order drift")
    sections = contract.get("sections", {})
    require(sections.get("entries_offset") == "24"
            and "entry_count * 16" in sections.get("literals_offset", "")
            and "literal_count * 8" in sections.get("strings_offset", "")
            and sections.get("metadata_bytes") == "align2(strings_offset + strings_bytes)",
            "section closure drift")
    pool = contract.get("string_pool", {})
    require("length_u16" in pool.get("record", "")
            and "including NUL" in pool.get("binary_string_rule", "")
            and "7-bit ASCII" in pool.get("symbol_name_rule", ""),
            "binary-safe string contract drift")
    flags = contract.get("entry_flags", {})
    require(flags.get("0x01") == "macro export"
            and flags.get("0x02") == "late-bound export"
            and flags.get("allowed_mask") == 3,
            "entry flag assignment drift")
    kinds = contract.get("literal_kinds", [])
    require([row.get("id") for row in kinds] == list(range(7)),
            "literal kind IDs drift")
    require([row.get("name") for row in kinds] == core["direct_container"]["literal_descriptor"]["kinds"],
            "literal kind names differ from approved core")
    require(len(proposal.get("required_negative_fixtures", [])) == 12,
            "metadata negative closure drift")


def collect() -> dict[str, Any]:
    core = load(CORE)
    proposal = load(PROPOSAL)
    validate(core, proposal)
    return {
        "format": "lisp65-c2-metadata-envelope-proposal-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "owner-approved-c2.1-bytes-authorized",
        "claim_limit": (
            "This receipt binds the owner-approved metadata envelope and its arithmetic. "
            "It authorizes only the separate C2.1 internal proof target; it changes no "
            "product byte, authorizes no capacity and makes no execution claim."
        ),
        "bindings": {
            "core_contract": binding(CORE),
            "proposal": binding(PROPOSAL),
            "document": binding(DOCUMENT),
            "verifier": binding(ROOT / "tools/host-lisp/c2_metadata_envelope_check.py"),
        },
        "validated": {
            "header_bytes": 24,
            "header_field_bytes": 24,
            "entry_bytes": 16,
            "literal_bytes": 8,
            "literal_kinds": 7,
            "negative_fixture_classes": 12,
            "shelf_record_bytes_changed": 0,
            "product_bytes_changed": 0,
        },
        "next_authorized_action": "C2.1 exact-envelope emitter and decoder implementation only",
    }


def selftest() -> None:
    core = load(CORE)
    proposal = load(PROPOSAL)
    rejected = []
    for label, mutate in (
        ("header-width", lambda value: value["recommended_contract"]["metadata_header"]["fields"][0].__setitem__("bytes", 3)),
        ("option", lambda value: value["options"][0].__setitem__("assessment", "rejected")),
        ("string-record", lambda value: value["recommended_contract"]["string_pool"].__setitem__("record", "NUL terminated")),
    ):
        bad = copy.deepcopy(proposal)
        mutate(bad)
        try:
            validate(core, bad)
        except EnvelopeError:
            rejected.append(label)
    require(len(rejected) == 3, f"mutations not rejected: {rejected}")


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    result = collect()
    require(RECEIPT.is_file(), "proposal receipt missing")
    require(load(RECEIPT) == result, "proposal receipt drift; regenerate with --write")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("c2-metadata-envelope: SELFTEST PASS mutations=3")
        return 0
    result = write() if args.write else check()
    print("c2-metadata-envelope: PASS status=approved c2.1-bytes=authorized header=24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
