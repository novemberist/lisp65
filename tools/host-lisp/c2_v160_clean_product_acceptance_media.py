#!/usr/bin/env python3
"""Pack the clean v1.6 product world for the one owner acceptance session."""

from __future__ import annotations

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

import c2_v160_boot_refill_selector_bypass_media as MEDIA  # noqa: E402
import c2_v160_clean_product_candidate as CLEAN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ENGINE = MEDIA.ENGINE
BASE = ENGINE.BASE.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = CLEAN.BUILD
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-clean-product-acceptance-media"
ADAPTER = BUILD.parent / "v1.6-clean-product-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-clean-product-acceptance-media-receipt.json"
SESSION = ROOT / "config/c2-v160-clean-product-acceptance-session.json"
CLOSURE = CLEAN.RECEIPT
ACCEPTANCE = CLEAN.ACCEPTANCE_RESULT
AUTHORIZATION = "70e55aee"
PRODUCT_REMOTE = "V16A.D81"
LIBRARY_REMOTE = "V16ALIB.D81"
EXPECTED = {
    "PRG": (41566,
            "aea2487285900be5349315e628b452d592883f629daa25cf158fe136e3b69ef4"),
    "ELF": (647524,
            "ac719d369a54e972803ac737356cef0b623353e277b6c6ed0a7541fb151ab5f8"),
}
STATUS = "PASS: V1.6 CLEAN PRODUCT ACCEPTANCE MEDIA READY"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("step 2", "fresh same-world media",
                  "facade and packed-prg proofs", "one bound acceptance session",
                  "announced with the fresh shas"):
        require(token in text, f"clean-product media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    scope = load(ROOT / closure["scope"]["path"])
    acceptance = load(ROOT / closure["acceptance"]["path"])
    pair = closure["artifacts_before"]
    require(closure["status"] == CLEAN.STATUS
            and closure["artifacts_after"] == pair
            and closure["final_product"]["diagnostic_freight_absent"] is True
            and closure["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and scope["status"] == acceptance["status"] == "PASS",
            "clean product closure is not media-ready")
    value = {
        "format": "lisp65-v160-clean-product-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair,
        "frozen_pair_after": closure["artifacts_after"],
        "clean_product_scope": bind(CLOSURE),
        "review_confirmation": authority(),
        "rule": "same-world adapter; no claim is re-derived",
    }
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct only the configuration consumed by the frozen clean link."""
    CLEAN.configure_full_candidate()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def mapped_section_rows(truth: ElfTruth) -> list[tuple[int, bytes, str]]:
    closure = load(CLOSURE)
    registered = {
        name
        for registry in closure["configuration"]["active_registries"]
        for name in registry["allocated"]
        if name.startswith(".lisp65_c2_mapped_")
    }
    names = [".lisp65_c2_mapped_far_service", *sorted(registered)]
    require(".lisp65_c2_mapped_diagnostic" not in names
            and len(names) == len(set(names)),
            "clean mapped-section authority contains diagnostic or duplicate freight")
    rows = []
    for name in names:
        raw = truth.section_bytes(name)
        symbol = "__" + name.removeprefix(".") + "_load_start"
        rows.append((truth.symbol(symbol).value, raw, name))
    return rows


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    """Materialize every active clean-product Bank-2 mapped section."""
    static = {"status": "passed-v1.6-clean-product-static-plane",
              "product_build_id": f"0x{BASE.PRODUCT_ID:08x}",
              "bank2_static_code_bytes": 46043}
    wplto = {"status": "passed-qualified-clean-product-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = BASE.CAN.manifest(static, wplto, completion)
    elf = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46043, "clean-product Bank-2 prefix drift")
    sections = mapped_section_rows(truth)
    base = 0x20000
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
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections],
        "membership_authority": "clean-product active registry union",
    })
    BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.CAN.check()
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ENGINE.BASE.RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-clean-product-acceptance-session-v1"
    value["recorded_on"] = "2026-08-24"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts": ["v1.6-item-1-cursor-navigation",
                    "v1.6-item-2-comfort-repl"],
        "green_consequence": "items 1 and 2 accepted; Halt A follows immediately",
        "excludes": ["D5-headroom", "release-acceptance", "v1.6-item-3",
                     "v1.6-item-4"],
    }
    value["rows"] = [
        {"id": "A1-prompts", "group": "prompt rows", "actions": [
            "cold boot product; mount library physically",
            "submit (require 'v16core), then (require 'repl-comfort)",
            "submit (repl)"],
         "expect": ["native lisp65> before Comfort", "t after each require",
                    "l65> on the editor row with the cursor immediately after it"]},
        {"id": "A2-abort", "group": "abort row", "actions": [
            "at l65> submit (car 1)",
            "after recovery submit (repl) once to continue the session"],
         "expect": ["no red frame", "clean recovery to native lisp65>",
                    "second Comfort entry shows l65>"]},
        {"id": "A3-input", "group": "input rows", "actions": [
            "type (list 1 3), move left twice, insert 2 followed by a space, submit",
            "submit (+ 10 on one line and 32) on the continuation line",
            "evaluate (list 7 8), then Up and Return",
            "with Shift-Lock off type lowercase letters and one Shift+8",
            "rapidly type and submit (list 1 2 3 4 5 6 7 8 9)"],
         "expect": ["(1 2 3)", "42", "(7 8) repeats from history",
                    "lowercase remains lowercase and Shift+8 yields (",
                    "no swallowed keys or progressive input backlog"]},
        {"id": "A4-display", "group": "composed display", "actions": [
            "at l65> type and submit (list 1 3)",
            "inspect the evaluated row and the following prompt"],
         "expect": ["prompt and editable input shared one row before Return",
                    "evaluated row is exactly (1 3) with no stale tail",
                    "next l65> and its cursor occupy the same row"]},
    ]
    value["decision_table"] = {
        "all-four-groups-green":
            "items 1 and 2 accepted; Halt A follows immediately",
        "clean-world-early-boot-$8040-red":
            "emulator diagnosis with xemu; never the core",
        "other-new-red": "one rescue read, then finish-plan triage",
        "daily-use-blocker":
            "at most one fix round; a second required round descopes the feature",
        "rare-or-cosmetic": "Known Issue plus v1.7 register row",
    }
    value["triage_limits"] = {"new_instruments": 0, "new_walls": 0,
                               "raised_bars": 0}
    return value


def configure_successor() -> None:
    MEDIA.CARD_BUILD = CARD_BUILD
    MEDIA.WPLTO = WPLTO
    MEDIA.STATIC = STATIC
    MEDIA.BUILD = BUILD
    MEDIA.ADAPTER = ADAPTER
    MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION
    MEDIA.CLOSURE = CLOSURE
    MEDIA.ACCEPTANCE = ACCEPTANCE
    MEDIA.AUTHORIZATION = AUTHORIZATION
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED
    MEDIA.STATUS = STATUS
    MEDIA.authority = authority
    MEDIA.closure_adapter = closure_adapter
    MEDIA.session_config = session_config
    MEDIA.configure_successor()
    ENGINE.configure_candidate = configure_candidate
    # The historical diagnostic media materialized its own second mapped
    # section.  The clean world replaces that tenant with product-cold freight.
    ENGINE.BASE.RED.product_manifest = product_manifest
    BASE.product_manifest = product_manifest


def static_plane_gate() -> dict[str, Any]:
    # A fresh read-only process has not run Completion's path projector.  Bind
    # the producer-owned output directly instead of inheriting ambient CAN
    # module state from the historical default world.
    manifest_path = BUILD / "canonical-product/canonical-product-manifest.json"
    value = load(manifest_path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    elf = BUILD / "canonical-product/final/lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    sections = mapped_section_rows(truth)
    expected_names = [name for _start, _raw, name in sections]
    expected_bytes = max(start + len(raw) for start, raw, _name in sections) - 0x20000
    require(plane["status"] == "passed-v1.6-clean-product-static-plane"
            and plane["mapped_sections"] == expected_names
            and plane["bank2_static_code_bytes"] == row["bytes"] == expected_bytes
            and ".lisp65_c2_mapped_diagnostic" not in plane["mapped_sections"]
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "clean-product mapped static-plane closure drift")
    return {"manifest": bind(manifest_path), "static_plane": plane,
            "artifact": row,
            "rule": "all active mapped product tenants reach the shipped plane"}


def finalize() -> None:
    configure_successor()
    value = load(RECEIPT)
    require(value["status"] == STATUS,
            "clean-product media receipt is not ready to finalize")
    value["clean_static_plane"] = static_plane_gate()
    RECEIPT.write_bytes(canonical(value))


def preflight() -> None:
    configure_successor()
    MEDIA.preflight()
    print("v1.6 clean product media: PREFLIGHT PASS artifact-only")


def build() -> None:
    configure_successor()
    MEDIA.build()
    finalize()


def check() -> None:
    configure_successor()
    MEDIA.check()
    value = load(RECEIPT)
    product = ROOT / value["media"]["product"]["path"]
    library = ROOT / value["media"]["library"]["path"]
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 2, "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"]["bytes"] == 98
            and value["shipped_byte_facade"]["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf"
            and value["facade_mutations"] == {"cases": 2,
                "rejected": ["null-facade", "partial-facade"]}
            and value["same_world_pair"]["result"] == "same-world-pair"
            and value["clean_static_plane"] == static_plane_gate()
            and bind(product) == value["media"]["product"]
            and bind(library) == value["media"]["library"],
            "clean-product packed-media proof drift")
    print("v1.6 clean product media: CHECK PASS contact=one-owner-session")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    elif action == "finalize":
        finalize()
    elif action == "check":
        check()
    else:
        raise RuntimeError("usage: preflight|build|finalize|check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
