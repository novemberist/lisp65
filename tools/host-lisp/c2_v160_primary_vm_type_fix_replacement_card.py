#!/usr/bin/env python3
"""Run the domain-correct replacement for the primary VM_TYPE fix card."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402
import c2_v160_primary_vm_type_fix as FIX  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-replacement-process"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
RECEIPT = ARCH / "c2.3-v1.6-primary-vm-type-fix-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-primary-vm-type-fix-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-primary-vm-type-fix-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "59729f6f"
FORMAT = "lisp65-c2-v160-primary-vm-type-fix-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 PRIMARY VM TYPE FIX REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 PRIMARY VM TYPE FIX REPLACEMENT FINAL WORLD GREEN"
V16_SUITE = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.CardError(message)


def authority() -> dict[str, Any]:
    path = FIX.PLAN.relative_to(ROOT).as_posix()
    value = ERA.era_bind(AUTHORIZATION, path)
    raw = ERA.era_blob(AUTHORIZATION, path)
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one replacement card", "artifact domains separated",
                  "final-elf claims", "v16core", "one wplto, one product link",
                  "holder gate remains open"):
        require(token in text, f"replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, **value}


def predecessor() -> dict[str, Any]:
    red = BASE.load(PREDECESSOR_RED)
    require(
        red["status"] == "FINAL RED: V1.6 HYBRID LIVE STACK CONVERSION STOPS"
        and red["error"]["message"] ==
            "final product static plane lacks fixed read-line loop"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and red["attempt_accounting"]["product_link_attempts"] == 1
        and red["final_world_claims"]["status"] ==
            "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
        and red["retry_authorized"] is False,
        "primary-fix Final Red drift",
    )
    fix = FIX.derive()
    require(fix["status"] == "PASS: PRIMARY VM_TYPE EMPTY-PHASE FIX",
            "primary-fix regression drift")
    return {"Final_Red": red, "primary_fix": fix}


def configure_module() -> None:
    BASE.set_paths(BUILD, PREFLIGHT, tag="primary-vm-type-fix-replacement")
    BASE.PREV.configure_module()


def install() -> None:
    BASE.BUILD = BUILD
    BASE.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PREFLIGHT = PREFLIGHT
    BASE.NORMAL_BUILD = NORMAL_BUILD
    BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD
    BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.PREDECESSOR_RED = PREDECESSOR_RED
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BASE.FINAL_STATUS = FINAL_STATUS
    BASE.authority = authority
    BASE.predecessor = predecessor
    BASE.configure_module = configure_module


def final_library_world(final_claims: dict[str, Any]) -> dict[str, Any]:
    out = BUILD / "candidate-library/v16core"
    out.parent.mkdir(parents=True, exist_ok=True)
    suite = STD._read_suite(str(V16_SUITE))
    checked = STD.check_suite(str(V16_SUITE), suite)
    STD.emit_artifacts(str(V16_SUITE), suite, str(out), base_addr=0,
                       artifact_role="disk-lib")
    manifest_path = out.with_suffix(".manifest.json")
    blob_path = out.with_suffix(".blob.bin")
    manifest = BASE.load(manifest_path)
    rows = [row for row in manifest["entries"] if row["name"] == "%read-line-loop"]
    require(len(rows) == 1, "candidate v16core lacks fixed read-line loop")
    row = rows[0]
    raw = blob_path.read_bytes()
    start = int(row["blob_offset"]); end = start + int(row["length"])
    emitted = B.decode_code_object(raw[start:end])
    compiled = checked["code_by_name"]["%read-line-loop"]
    require(
        int(row["length"]) == 248
        and (emitted.nargs, emitted.nlocals, emitted.flags, emitted.payload)
            == (compiled.nargs, compiled.nlocals, compiled.flags, compiled.payload)
        and manifest["blob_sha256"] == hashlib.sha256(raw).hexdigest(),
        "candidate v16core emitted/source loop identity drift",
    )
    require(
        final_claims["status"] == "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
        and final_claims["claim_source"] == "final linked ELF only"
        and final_claims["membership"]["section_bytes"] == 67,
        "final-ELF Hybrid authority drift",
    )

    # Domain-swap mutation: neither authority may be substituted for the
    # other.  The library manifest has no linked-native membership claim and
    # Final-ELF claims have no disk-library entry inventory.
    domain_swap_rejected = (
        "membership" not in manifest
        and "entries" not in final_claims
        and "%read-line-loop" not in
            {final_claims["membership"].get("symbol", "")}
    )
    require(domain_swap_rejected, "artifact-domain swap mutation survived")
    return {
        "status": "PASS: FIXED LOOP IN CANDIDATE V16CORE DOMAIN",
        "suite": BASE.bind(V16_SUITE), "manifest": BASE.bind(manifest_path),
        "blob": BASE.bind(blob_path), "function": "%read-line-loop",
        "encoded_bytes": int(row["length"]), "payload_bytes": len(emitted.payload),
        "source_emission_byteidentical": True,
        "domain_swap_mutation_rejected": True,
        "authority_split": {"native_walls": "final linked ELF",
                            "resident_loop": "candidate v16core artifact"},
    }


def check_receipt() -> dict[str, Any]:
    value = BASE.load(RECEIPT)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0},
            "primary-fix replacement receipt drift")
    BASE.PREV.PREV.PREV.validate_final_claims(value)
    require(value["primary_vm_type_fix"]["regression"]["unfixed_mutation"]
                ["steps"] == 4196
            and value["primary_vm_type_fix"]["regression"]["fixed_boundary"]
                ["steps"] == 5156
            and value["candidate_v16core"]["encoded_bytes"] == 248
            and value["candidate_v16core"]["domain_swap_mutation_rejected"]
                is True,
            "primary-fix replacement claims drift")
    return value


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "check":
        configure_module()
        check_receipt()
        print("v1.6 primary VM_TYPE fix replacement: CHECK PASS domains=ELF+v16core")
        return 0
    result = BASE.main()
    if action == "card" and RECEIPT.is_file():
        value = BASE.load(RECEIPT)
        value.update({"format": FORMAT, "status": FINAL_STATUS,
            "replacement_authority": authority(),
            "predecessor_Final_Red": BASE.bind(PREDECESSOR_RED),
            "primary_vm_type_fix": FIX.derive(),
            "candidate_v16core": final_library_world(value["final_world_claims"]),
            "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
                "product_links": 1, "media_builds": 0, "device_contacts": 0},
            "media_authorized": False, "device_contacts": 0,
            "holder_liveness_gate": "OPEN; Track-2 read not executed",
            "next": "Track-2 holder/liveness contract; no device acceptance"})
        RECEIPT.write_bytes(BASE.canonical(value))
        check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                BASE.record_red(error)
            except Exception as receipt_error:
                print(f"primary VM_TYPE replacement Final Red failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 primary VM_TYPE fix replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
