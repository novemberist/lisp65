#!/usr/bin/env python3
"""Prepare same-world media and the one refill-trace reading contact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_queue_owner_device_preparation as PREV  # noqa: E402
import c2_v160_refill_boundary_witness_replacement_card as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = PREV.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-refill-boundary-witness-device-preparation"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
RECEIPT = ARCH / "c2.3-v1.6-refill-boundary-witness-device-preparation-receipt.json"
SESSION = ROOT / "config/c2-v160-refill-boundary-witness-device-session.json"
CLOSURE = ARCH / "c2.3-v1.6-refill-boundary-witness-qualification-resume-receipt.json"
PREDECESSOR_ACCEPTANCE = PREV.ACCEPTANCE
EXPECTED = {
    "PRG": (41566, "d878b418ff33f944e4a9272c601d55d7847d05706c840c350badb23c4a2022d9"),
    "ELF": (647116, "fa686ea4c9c667f681a7e78e7fe508fc964495e933b26004156a816d45312f4d"),
}
AUTHORIZATION = "11defe27"
PRODUCT_REMOTE = "V16WT.D81"
LIBRARY_REMOTE = "V16WL.D81"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("media and the trace-reading contact released",
                  "missing or failed request", "differing from the same-world medium",
                  "correct bytes with the red still standing", "diagnosis only"):
        require(token in text, f"trace-contact authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_candidate() -> None:
    CARD.install()
    CARD.configure_module()
    core, _activation = BASE.REOPEN.configure_stack(CARD.BUILD, CARD.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    BASE.CAN.REPLAY.PROFILE.configure()
    if BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        BASE.PRODUCT.configure_require_resolver_profile_geometry()
        BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    BASE.CAN.REPLAY.TWO.configure_two_region()
    BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    BASE.PRODUCT.configure_intern_session_service()
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.HEADER.configure_consumption()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = STATIC / "product/substitution-artifacts.json"
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def complete() -> dict[str, Any]:
    BASE.configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "qualified witness pair drift")
    configure_candidate()
    closure = load(CLOSURE)
    acceptance = load(PREDECESSOR_ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    witness = closure["refill_boundary_witness"]
    require(closure["status"] ==
                "PASS: V1.6 REFILL WITNESS FINAL WORLD CLOSED READ-ONLY"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and witness["ordinary"]["free_bytes"] == 3
            and witness["mapped_diagnostic"]["free_bytes"] == 160,
            "qualified witness closure drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, BASE.sha(candidate)) == EXPECTED["ELF"],
                    "Completion received a different witness ELF")
            return projection

    accepted = AcceptedProjection()
    BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    BASE.CRC_MEDIA.INV = accepted
    BASE.SOURCE_MEDIA.card_projection = lambda: {"acceptance": {"VMA_golden": projection}}
    original_configure = BASE.CAN.REPLAY.configure
    original_fixed = BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = BASE.PRODUCT.fixed_facade_gate
    original_verify = BASE.CAN.verify_published_verifier_binding

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return BASE.SOURCE_MEDIA._link105_fixed_audit(original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        return BASE.CRC_MEDIA._current_facade_gate(original_facade, out, target, suffix)

    def verify(product_path: Path, boot: Path, session: Path) -> dict[str, Any]:
        """Materialize the candidate's omitted publish-last predecessor.

        The frozen WPLTO receipt carries both the unbound SHA and the exact
        two-byte KERNAL publication.  Completion owns its target copy and may
        reconstruct this intermediate there; the frozen evidence stays 0444.
        """
        final = BASE.CAN.FINAL
        target = final / "lisp65-c2-substitution-window-bound.prg"
        if not target.exists():
            report = BASE.PRODUCT.patch_verifier_binding_table(
                final, product_path, boot, session,
                expected_base=BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE)
            require(report["bytes"] == 40
                    and report["pre_overlay_binding_sha256"]
                        == load(final / "kernal-window-publish-last.json")
                            ["window_bound_product_sha256"],
                    "Completion verifier publication predecessor drift")
        return original_verify(product_path, boot, session)

    BASE.CAN.REPLAY.configure = lambda: None
    BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    BASE.PRODUCT.fixed_facade_gate = facade
    BASE.CAN.verify_published_verifier_binding = verify
    try:
        value = BASE.CAN.complete_artifacts()
    finally:
        BASE.CAN.REPLAY.configure = original_configure
        BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        BASE.PRODUCT.fixed_facade_gate = original_facade
        BASE.CAN.verify_published_verifier_binding = original_verify
    final_product = BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require(final_product.stat().st_size == EXPECTED["PRG"][0]
            and BASE.sha(final_product) != EXPECTED["PRG"][1]
            and (final_elf.stat().st_size, BASE.sha(final_elf)) == EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed the witness final pair")
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    """Materialize both candidate-owned mapped Bank-2 sections."""
    static = {"status": "passed-v1.6-refill-witness-static-plane",
              "product_build_id": f"0x{BASE.PRODUCT_ID:08x}",
              "bank2_static_code_bytes": 46043}
    wplto = {"status": "passed-qualified-refill-witness-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = BASE.CAN.manifest(static, wplto, completion)
    elf = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46043, "candidate Bank-2 prefix drift")
    base = 0x20000
    sections = []
    for name, symbol in (
            (".lisp65_c2_mapped_far_service", "__lisp65_c2_mapped_far_service_load_start"),
            (".lisp65_c2_mapped_diagnostic", "__lisp65_c2_mapped_diagnostic_load_start")):
        section = truth.section(name)
        sections.append((truth.symbol(symbol).value, truth.section_bytes(name), name))
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    for start, raw, name in sections:
        offset = start - base
        require(offset >= len(prefix), f"mapped section overlaps prefix: {name}")
        materialized[offset:offset + len(raw)] = raw
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear(); row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({"bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections]})
    BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.CAN.check()
    return value


def expected_payload() -> dict[str, Any]:
    manifest_path = BUILD / "library-inputs/repl-comfort.manifest.json"
    manifest = load(manifest_path)
    entry = next(row for row in manifest["entries"] if row["name"] == "%repl-step")
    blob = (ROOT / manifest["blob"]).read_bytes()
    start = int(entry["blob_offset"]) + 0x45
    payload = blob[start:start + 21]
    require(len(payload) == 21 and not any(
        start <= int(row["blob_offset"]) < start + 21
        for row in manifest["literal_patches"]),
        "target payload is not a source-authoritative unpatched span")
    return {"object": "%repl-step", "object_id": "0x02fd", "offset": "0x0045",
            "length": 21, "hex": payload.hex(" "),
            "source": bind(manifest_path)}


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-refill-boundary-witness-device-session-v1"
    value["recorded_on"] = "2026-08-22"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {"accepts": ["refill-boundary-diagnosis"],
        "excludes": ["v1.6-items-1-2", "release-acceptance"]}
    value["rows"] = [
        {"id": "T1-boot", "action": "cold boot product and physically mount library",
         "expect": "native lisp65> prompt"},
        {"id": "T2-load", "action": "submit (require 'v16core), then (require 'repl-comfort)",
         "expect": "t after each form"},
        {"id": "T3-reproduce", "action": "submit (repl) and make no further input",
         "expect": "the deterministic VM_BAD_BYTECODE red stop"},
        {"id": "T4-read", "action": "one stopped read-only trace read; never resume",
         "expect": "read $BC87..$BC8B and both 34-byte slots at $BD00/$BD22"},
    ]
    value["trace_witness"] = {
        "origin": {"next": "0xBC87", "sequence": "0xBC88", "wrap": "0xBC89",
                   "active": "0xBC8A", "commit": "0xBC8B", "commit_value": "0xA5"},
        "slots": [{"address": "0xBD00", "bytes": 34},
                  {"address": "0xBD22", "bytes": 34}],
        "slot_schema": ["commit:u8", "sequence:u8", "window_id:u16",
            "offset:u16", "length:u16", "result:u8", "start_frame:u16",
            "end_frame:u16", "payload:21"],
        "expected": expected_payload(),
        "decision": {"missing-or-failed-request": "window/refill machinery",
            "payload-differs": "content path; report first differing byte",
            "payload-equal-and-red": "time-shaped failure"},
        "read_only": True, "resume": False, "removal_default": True}
    return value


def configure() -> None:
    BASE.BUILD = BUILD; BASE.CARD = CARD_BUILD; BASE.WPLTO = WPLTO; BASE.STATIC = STATIC
    BASE.TARGET = BUILD / "canonical-product"
    BASE.SHARED = BUILD / "shared-system"; BASE.LIBRARY = BUILD / "library"
    BASE.RECEIPT = RECEIPT; BASE.SESSION = SESSION; BASE.EXPECTED = EXPECTED
    BASE.configure_candidate = configure_candidate
    BASE.complete = complete
    BASE.product_manifest = product_manifest
    BASE.session_config = session_config


def preflight() -> None:
    configure(); closure = load(CLOSURE)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "refill-witness device preparation is one-shot")
    require(closure["status"] == "PASS: V1.6 REFILL WITNESS FINAL WORLD CLOSED READ-ONLY",
            "refill-witness final-world predecessor drift")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "refill-witness candidate pair drift")
    print(f"v1.6 refill witness media: PREFLIGHT PASS authority={authority()['commit'][:8]}")


def build() -> None:
    configure(); value = BASE.build()
    value.update({"format": "lisp65-c2-v160-refill-witness-device-preparation-v1",
        "recorded_on": "2026-08-22", "successor_authority": authority(),
        "witness_closure": bind(CLOSURE),
        "status": "PASS: V1.6 REFILL TRACE CONTACT READY"})
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 refill witness media: PASS media=2 contact=trace-read-ready")


def check() -> dict[str, Any]:
    configure(); value = load(RECEIPT)
    require(value["status"] == "PASS: V1.6 REFILL TRACE CONTACT READY",
            "refill witness preparation status drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"], value["witness_closure"]]:
        require(bind(ROOT / row["path"]) == row,
                f"refill witness prepared artifact drift: {row['path']}")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "refill witness pair identity drift")
    session = load(SESSION)
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and [row["id"] for row in session["rows"]] ==
                ["T1-boot", "T2-load", "T3-reproduce", "T4-read"],
            "refill witness session drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "build": build()
    else: check(); print("v1.6 refill witness media: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
