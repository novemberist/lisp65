#!/usr/bin/env python3
"""Validate and size the non-authorizing C2 mutable-directory proposal."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "config/c2-session-directory-proposal.json"
CORE = ROOT / "config/c2-address-identity-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.1-session-directory-addendum.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-session-directory-proposal-receipt.json"
)
MANIFESTS = (
    ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/idex.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json",
)
RUNTIME = ROOT / "build/products/workbench/overlay-stack-guard/runtime-overlays-manifest.json"
FOOTPRINT = ROOT / "build/products/workbench/overlay-stack-guard/footprint-audit.json"
COMPOSITION = ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
IMAGE_FIELDS = {
    "shelf_record_index_u8": 1,
    "flags_u8_zero": 1,
    "directory_base_u16": 2,
    "entry_count_u16": 2,
    "resolution_base_u16": 2,
    "resolution_count_u16": 2,
    "code_offset_u24": 3,
    "metadata_offset_u24": 3,
    "code_length_u16": 2,
    "metadata_length_u16": 2,
}
ENTRY_FIELDS = {
    "image_slot_u8": 1,
    "flags_u8_zero": 1,
    "entry_ordinal_u16": 2,
    "code_length_u16": 2,
    "literal_resolution_base_u16": 2,
    "session_generation_u16": 2,
}


class DirectoryError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DirectoryError(message)


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


def measured() -> dict[str, int]:
    manifests = [load(path) for path in MANIFESTS]
    runtime = load(RUNTIME)
    footprint = load(FOOTPRINT)
    composition = load(COMPOSITION)
    entries = sum(len(value.get("entries", [])) for value in manifests)
    literals = sum(len(value.get("literal_nodes", [])) for value in manifests)
    materializer = [
        row for row in runtime.get("slices", [])
        if str(row.get("name", "")).startswith("l65m-")
    ]
    return {
        "product_images": len(manifests),
        "directory_entries": entries,
        "literal_resolutions": literals,
        "directory_capacity": int(composition["limits"]["vm_dir_max"]),
        "current_post_boot_reserve_bytes": int(footprint["post_boot_reserve"]),
        "current_ext_code_post_used_bytes": int(composition["ext_code"]["post_used"]),
        "current_ext_code_limit_bytes": int(composition["limits"]["ext_code_limit"]),
        "current_runtime_materializer_slices": len(materializer),
        "current_runtime_materializer_code_bytes": sum(int(row["memory_size"]) for row in materializer),
        "current_runtime_overlay_bank_headroom_bytes": 65536 - int(runtime["storage"]["size"]),
    }


def validate(proposal: dict[str, Any], facts: dict[str, int]) -> None:
    require(proposal.get("format") == "lisp65-c2-session-directory-proposal-v1"
            and proposal.get("status") == "owner-approved-option-a-product-layout-authorized",
            "proposal status drift")
    require("approved without amendment on 2026-07-19" in proposal.get("owner_decision", ""),
            "owner approval missing")
    core = load(CORE)
    require(core.get("status") == "owner-approved-c2.1-proof-authorized",
            "approved C2 core contract missing")
    pinned = proposal.get("measured_inputs", {})
    for key, value in facts.items():
        require(pinned.get(key) == value, f"measured input drift: {key}")
    require(pinned.get("current_bank0_directory_bytes_retired_by_c2") == 761,
            "v1.1 directory retirement arithmetic drift")
    require(pinned.get("bank0_reserve_target_bytes") == 1536,
            "Bank-0 target drift")

    options = proposal.get("options", [])
    require([row.get("id") for row in options] == [
        "external-self-describing-session-directory",
        "descriptor-on-call", "fixed-bank0-entry-arrays"
    ], "option closure drift")
    require([row.get("assessment") for row in options] == [
        "recommended", "fallback-needs-contract-amendment-and-hardware-latency-proof",
        "rejected"
    ], "option assessment drift")

    contract = proposal.get("recommended_contract", {})
    header = contract.get("header", {})
    require(header.get("magic") == "C2D\\0" and header.get("bytes") == 32,
            "session header identity drift")
    require(sum(row.get("bytes", -1000) for row in header.get("fields", [])) == 32,
            "session header field arithmetic does not close")
    image = contract.get("image_record", {})
    entry = contract.get("entry_record", {})
    require(image.get("bytes") == 20 and image.get("fields") == list(IMAGE_FIELDS)
            and sum(IMAGE_FIELDS.values()) == 20,
            "session image-record geometry drift")
    require(entry.get("bytes") == 10 and entry.get("fields") == list(ENTRY_FIELDS)
            and sum(ENTRY_FIELDS.values()) == 10,
            "session entry-record geometry drift")
    require(contract.get("resolution_record") == "obj_u16",
            "session record widths drift")

    image_count = facts["product_images"]
    entry_count = facts["directory_entries"]
    literal_count = facts["literal_resolutions"]
    total = 32 + image_count * 20 + entry_count * 10 + literal_count * 2
    recommended = options[0]["exact_current_bytes"]
    require(total == 10150 and recommended.get("total") == total,
            "recommended current arithmetic drift")
    require(recommended.get("ext_headroom_if_it_replaces_current_post_code") ==
            facts["current_ext_code_limit_bytes"] - total,
            "recommended EXT projection drift")
    require(recommended.get("bank0_data_delta_after_retiring_v11_directory") ==
            64 - pinned["current_bank0_directory_bytes_retired_by_c2"],
            "recommended Bank-0 data projection drift")

    fallback = options[1]["exact_current_bytes"]
    fallback_total = 32 + image_count * 20 + literal_count * 2
    require(fallback_total == 4320 and fallback.get("total") == fallback_total
            and fallback.get("saved_against_recommended") == entry_count * 10,
            "descriptor-on-call arithmetic drift")
    rejected = options[2]["exact_current_bytes"]
    net = total - pinned["current_bank0_directory_bytes_retired_by_c2"]
    remaining = facts["current_post_boot_reserve_bytes"] - net
    require(rejected.get("net_bank0_debit") == net
            and rejected.get("resulting_post_boot_reserve") == remaining
            and rejected.get("target_deficit_before_code") ==
            pinned["bank0_reserve_target_bytes"] - remaining,
            "Bank-0 rejection arithmetic drift")
    require(len(proposal.get("required_negative_fixtures", [])) == 12,
            "session-directory negative closure drift")


def collect() -> dict[str, Any]:
    proposal = load(PROPOSAL)
    facts = measured()
    validate(proposal, facts)
    return {
        "format": "lisp65-c2-session-directory-proposal-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "option-a-owner-approved-product-layout-authorized",
        "claim_limit": (
            "This receipt binds the current six-image arithmetic and the proposed mutable "
            "directory envelope. It changes no product byte, authorizes no capacity and "
            "does not claim a C2 product link or hardware execution."
        ),
        "bindings": {
            "core_contract": binding(CORE),
            "proposal": binding(PROPOSAL),
            "document": binding(DOCUMENT),
            "verifier": binding(ROOT / "tools/host-lisp/c2_session_directory_check.py"),
            "manifests": [binding(path) for path in MANIFESTS],
            "runtime_overlay_manifest": binding(RUNTIME),
            "footprint": binding(FOOTPRINT),
            "composition": binding(COMPOSITION),
        },
        "measured": facts,
        "validated": {
            "recommended_session_bytes": 10150,
            "recommended_bank0_hot_bytes": 64,
            "recommended_bank0_data_credit": 697,
            "recommended_projected_ext_headroom_bytes": 40666,
            "fallback_session_bytes": 4320,
            "rejected_bank0_target_deficit_before_code": 9018,
            "required_negative_fixture_classes": 12,
            "product_bytes_changed": 0,
        },
        "next_action": "C2.1 product-layout substitution probe using C2D-v1; stop at every new format or capacity gate"
    }


def selftest() -> None:
    proposal = load(PROPOSAL)
    facts = measured()
    rejected = []
    for label, mutate in (
        ("header-width", lambda value: value["recommended_contract"]["header"]["fields"][0].__setitem__("bytes", 3)),
        ("entry-width", lambda value: value["recommended_contract"]["entry_record"].__setitem__("bytes", 8)),
        ("entry-field", lambda value: value["recommended_contract"]["entry_record"]["fields"].pop()),
        ("image-field", lambda value: value["recommended_contract"]["image_record"]["fields"].reverse()),
        ("image-count", lambda value: value["measured_inputs"].__setitem__("product_images", 5)),
        ("ext-arithmetic", lambda value: value["options"][0]["exact_current_bytes"].__setitem__("total", 10149)),
        ("bank-arithmetic", lambda value: value["options"][2]["exact_current_bytes"].__setitem__("target_deficit_before_code", 9017)),
    ):
        bad = copy.deepcopy(proposal)
        mutate(bad)
        try:
            validate(bad, facts)
        except DirectoryError:
            rejected.append(label)
    require(len(rejected) == 7, f"mutations not rejected: {rejected}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("c2-session-directory: SELFTEST PASS mutations=7")
        return 0
    value = collect()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(encoded, encoding="utf-8")
        action = "WROTE"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_text(encoding="utf-8") == encoded,
                "proposal receipt drift; regenerate with --write")
        action = "PASS"
    print(f"c2-session-directory: {action} images=6 entries=583 literals=2084 option=A-approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
