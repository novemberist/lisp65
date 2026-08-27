#!/usr/bin/env python3
"""Pack the accepted v1.7 Comfort Phase-1b world for one owner session."""

from __future__ import annotations

from copy import deepcopy
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

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v160_clean_product_acceptance_media as MEDIA  # noqa: E402
import c2_v17_comfort_phase1b_adapter_replacement_card as PHASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = MEDIA.BASE
LIBMEDIA = BASE.LIBMEDIA
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
CARD_BUILD = PHASE.BUILD
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.7-comfort-phase1b-acceptance-media-r1"
ADAPTER = BUILD.parent / "v1.7-comfort-phase1b-media-r1-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.7-comfort-phase1b-acceptance-media-r1-receipt.json"
SESSION = ROOT / "config/c2-v17-comfort-phase1b-device-session.json"
CLOSURE = PHASE.RECEIPT
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "a8fe76f0"
PRODUCT_REMOTE = "V17C.D81"
LIBRARY_REMOTE = "V17CLIB.D81"
EXPECTED = {
    "PRG": (41566,
            "db80cab1906fa6afb7f7a7a56e07ad138d7df23633cb5399853823967415a65c"),
    "ELF": (647524,
            "79158c0e0b0034d6843b90b4acae32ed6363cc4c835e1a68f4a37317bf00aa3e"),
}
STATUS = "PASS: V1.7 COMFORT PHASE 1B ACCEPTANCE MEDIA READY"
PRODUCT_ID = BASE.PRODUCT_ID
CURSOR_SUITE = BASE.CURSOR_SUITE
CURSOR_RESIDENT = ROOT / "config/c2-v160-comfort-repl-device-resident.json"
COMFORT_MANIFEST = PHASE.LIBRARY.with_suffix(".manifest.json")
COMFORT_BLOB = PHASE.LIBRARY.with_suffix(".blob.bin")


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
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("fresh same-world media", "facade and packed-prg proofs",
                  "comfort hardware acceptance session", "four row groups",
                  "daily-use blocker gets one repair round"):
        require(token in text,
                f"v1.7 Comfort media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    scope = load(ROOT / closure["scope"]["path"])
    acceptance = load(ROOT / closure["acceptance"]["path"])
    pair = closure["artifacts_before"]
    phase = closure["final_product"]["phase1b"]
    require(
        closure["status"] == PHASE.STATUS
        and closure["artifacts_after"] == pair
        and closure["final_product"]["diagnostic_freight_absent"] is True
        and closure["attempt_accounting"] == {
            "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0}
        and scope["status"] == acceptance["status"] == "PASS"
        and phase["status"]
            == "PASS: VARIANT B COMFORT SET PROVED ON FINAL PRODUCT WORLD"
        and phase["capacity"]["bias_adjusted_free"]
            == {"symbol_slots": 32, "namepool_bytes": 581}
        and 12 not in phase["library"]["delivered_callprims"],
        "Phase-1b closure is not media-ready")
    value = {
        "format": "lisp65-v17-comfort-phase1b-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair,
        "frozen_pair_after": closure["artifacts_after"],
        "phase1b_scope": bind(CLOSURE),
        "review_confirmation": authority(),
        "rule": "same-world adapter; no product claim is re-derived",
    }
    ADAPTER.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct the configuration consumed by the frozen Phase-1b link."""
    PHASE.configure()
    PHASE.CARD.BASE.configure_full_candidate()
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


def delivered_callprims() -> list[int]:
    phase = load(CLOSURE)["final_product"]["phase1b"]
    profile = phase["product_callprim_profile"]
    delivered = profile["delivered_ids"]
    require(profile["tombstoned_ids"] == [1, 2, 12, 26, 27, 40]
            and delivered == phase["library"]["delivered_callprims"]
            and 12 not in delivered,
            "Phase-1b product CALLPRIM profile drift")
    return delivered


def compile_cursor_library(prefix: Path) -> Path:
    suite_path = prefix.with_suffix(".suite.json")
    suite_path.write_bytes(canonical({
        "extends": str(CURSOR_SUITE.resolve()),
        # Override the declaring suite's relative spelling.  An outer adapter
        # is a new path authority and must not preserve a path while dropping
        # the base against which that path was declared.
        "resident_suite": [],
        "resident_suites": [str(CURSOR_RESIDENT.resolve())],
        "delivered_callprims": delivered_callprims(),
    }))
    suite = STD._read_suite(str(suite_path))
    STD.check_suite(str(suite_path), suite)
    STD.emit_artifacts(str(suite_path), suite, str(prefix),
                       artifact_role="disk-lib")
    return prefix.with_suffix(".manifest.json")


def library_media() -> dict[str, Any]:
    """Package the exact product-profile Comfort artifact; never recompile it."""
    generated = BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    v16_manifest = compile_cursor_library(generated / "v16core")
    closure = load(CLOSURE)["final_product"]["phase1b"]["library"]
    require(bind(COMFORT_MANIFEST) == closure["manifest"]
            and bind(COMFORT_BLOB) == closure["blob"],
            "accepted product-profile Comfort artifact drift")
    specs = (
        ("v16core", "v16core", "v16core", v16_manifest, ()),
        ("repl-comfort", "repl", "repl", COMFORT_MANIFEST, (0,)),
    )
    BASE.LIBRARY.mkdir(parents=True, exist_ok=True)
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for ordinal, spec in enumerate(specs):
        row, artifact = LIBMEDIA.measured(
            spec, (1, ordinal + 1), PRODUCT_ID)
        name = spec[0]
        placeholder.append(row)
        artifacts[name] = artifact
        path = BASE.LIBRARY / f"{name}.l65s"
        path.write_bytes(artifact)
        paths.append((path, name))
    seed_index = BASE.LIBRARY / "l65index.seed"
    seed_index.write_bytes(LIBMEDIA.L65I.encode_index(placeholder))
    seed = BASE.LIBRARY / "library.seed.d81"
    LIBMEDIA.build_library_d81(seed, seed_index, paths)
    locators = LIBMEDIA.L65I.d81_locators(seed)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        row, artifact = LIBMEDIA.measured(
            spec, locators[spec[0]], PRODUCT_ID)
        require(artifact == artifacts[spec[0]],
                f"library artifact changed with locator: {spec[0]}")
        rows.append(row)
    index = LIBMEDIA.L65I.encode_index(rows)
    index_path = BASE.LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = LIBMEDIA.L65I.decode_index(
        index, artifacts, artifact_build_id=PRODUCT_ID)
    final = BASE.LIBRARY / "lisp65-library.d81"
    LIBMEDIA.build_library_d81(final, index_path, paths)
    visible = LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index,
                        **{name.upper().encode(): raw
                           for name, raw in artifacts.items()}},
            "Phase-1b library visible-file truth drift")
    contracts = {spec[0]: LIBMEDIA.resolver_contract(decoded, spec[0])
                 for spec in specs}
    mutation_rows = deepcopy(decoded)
    mutation_rows[1]["dependencies"] = []
    mutations = LIBMEDIA.resolver_contract_mutation_gate(
        mutation_rows, "repl-comfort")
    seed.unlink()
    seed_index.unlink()
    return {
        "variant": "v1.7-comfort-phase1b-variant-B",
        "product_build_id": f"0x{PRODUCT_ID:08x}",
        "product_callprim_profile": {
            "delivered_ids": delivered_callprims(),
            "tombstoned_id_12": True,
        },
        "accepted_comfort_artifact": {
            "manifest": bind(COMFORT_MANIFEST),
            "blob": bind(COMFORT_BLOB),
        },
        "D81": bind(final), "index": bind(index_path),
        "artifacts": {name: bind(BASE.LIBRARY / f"{name}.l65s")
                      for name in artifacts},
        "index_rows": decoded,
        "resolver_contracts": contracts,
        "resolver_mutations_rejected": mutations,
        "visible_files": sorted(name.decode() for name in visible),
    }


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v17-comfort-phase1b-device-session-v1",
        "recorded_on": "2026-08-25",
        "status": "ready-owner-contact",
        "claim_scope": {
            "accepts": ["v1.7-comfort-phase1b-hardware-acceptance"],
            "green_consequence": "Phase 1b accepted on hardware",
            "excludes": ["D5-headroom", "release-acceptance",
                         "v1.7-later-blocks"],
        },
        "media": {
            "product": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "library": {**bind(library), "remote_name": LIBRARY_REMOTE},
        },
        "choreography": {
            "fresh_basic_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "product_mounted_last": True,
            "library_mounted_physically_through_freezer": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
            "observation_during_active_persistent_forms": 0,
        },
        "rows": [
            {"id": "C1-prompts", "group": "prompt rows", "actions": [
                "cold boot product; mount library physically",
                "submit (require 'v16core), then (require 'repl-comfort)",
                "submit (repl)",
                "after the other rows, submit an empty Comfort line"],
             "expect": ["native lisp65> before Comfort",
                        "t after each require", "l65> at the editor cursor",
                        "empty line returns to native lisp65>"]},
            {"id": "C2-abort", "group": "abort recovery", "actions": [
                "at l65> submit (>= nil 32)",
                "at native lisp65> submit (repl) once to continue"],
             "expect": ["*** vm: type error", "no red frame",
                        "clean recovery to native lisp65>",
                        "second Comfort entry shows l65>"]},
            {"id": "C3-input", "group": "input", "actions": [
                "type (list 1 3), move left twice, insert 2 followed by a space, submit",
                "submit (+ 10 on one line and 32) on the continuation line",
                "evaluate (list 7 8), then Up and Return",
                "with Shift-Lock off type lowercase letters and one Shift+8",
                "rapidly enter more than 192 checked printable cells before closing and submitting the form"],
             "expect": ["(1 2 3)", "42", "(7 8) repeats from history",
                        "lowercase stays lowercase and Shift+8 yields (",
                        "all characters remain present and ordered across at least one collection"]},
            {"id": "C4-display", "group": "composed display", "actions": [
                "at l65> type and submit (list 1 3)",
                "inspect the evaluated row and following prompt"],
             "expect": ["l65> and editable input share one row before Return",
                        "evaluated row is exactly (1 3) with no stale tail",
                        "next l65> and its cursor share one row"]},
        ],
        "host_half": {
            "ordered_events": "94/94", "dropped_events": 0,
            "normalization": "512/512 final-linked consumer executions",
            "fallback_frames_per_character": 0.7732179166666666,
            "fallback_margin_percent": 29.329646719903792,
            "callprim_12_tombstoned": True,
            "capacity_bias_adjusted": "32/581",
        },
        "decision_table": {
            "all-four-groups-green": "Phase 1b accepted on hardware",
            "daily-use-blocker":
                "at most one repair round; a second required round descopes Comfort",
            "rare-or-cosmetic": "Known Issue plus v1.7 register row",
        },
        "triage_limits": {"new_instruments": 0, "new_walls": 0,
                           "raised_bars": 0},
    }


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
    MEDIA.ENGINE.configure_candidate = configure_candidate
    BASE.library_media = library_media
    BASE.session_config = session_config


def finalize() -> None:
    configure_successor()
    value = load(RECEIPT)
    library = library_media_receipt()
    value.update({
        "format": "lisp65-c2-v17-comfort-phase1b-acceptance-media-v1",
        "recorded_on": "2026-08-25",
        "phase1b_library_closure": library,
        "review_authority": authority(),
    })
    RECEIPT.write_bytes(canonical(value))


def library_media_receipt() -> dict[str, Any]:
    phase = load(CLOSURE)["final_product"]["phase1b"]
    d81 = BASE.LIBRARY / "lisp65-library.d81"
    index = BASE.LIBRARY / "l65index"
    visible = LIBMEDIA.L65I.D81.visible_files(d81.read_bytes())
    require(set(visible) == {b"L65INDEX", b"V16CORE", b"REPL-COMFORT"},
            "Phase-1b library visible names drift")
    return {
        "D81": bind(d81), "index": bind(index),
        "artifacts": {name: bind(BASE.LIBRARY / f"{name}.l65s")
                      for name in ("v16core", "repl-comfort")},
        "accepted_comfort_artifact": {
            "manifest": bind(COMFORT_MANIFEST),
            "blob": bind(COMFORT_BLOB),
        },
        "product_callprim_profile": phase["product_callprim_profile"],
        "rule": "the shipped library consumes the accepted product-profile artifact",
    }


def preflight() -> None:
    configure_successor()
    MEDIA.preflight()
    print("v1.7 Comfort Phase 1b media: PREFLIGHT PASS artifact-only")


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
    session = load(SESSION)
    phase = value["phase1b_library_closure"]
    require(
        value["status"] == STATUS
        and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "replacement_media_builds": 2,
            "device_contacts": 0}
        and value["shipped_byte_facade"]["bytes"] == 98
        and value["shipped_byte_facade"]["status"]
            == "passed-packed-prg-facade-byte-equals-final-elf"
        and value["facade_mutations"] == {"cases": 2,
            "rejected": ["null-facade", "partial-facade"]}
        and value["same_world_pair"]["result"] == "same-world-pair"
        and bind(product) == value["media"]["product"]
        and bind(library) == value["media"]["library"]
        and phase == library_media_receipt()
        and phase["accepted_comfort_artifact"]["blob"]["sha256"]
            == "911653530f52979a92da462ad354d1fa9cc783e42d97ee955d870297a3c16fe5"
        and 12 not in phase["product_callprim_profile"]["delivered_ids"]
        and len(session["rows"]) == 4
        and session["claim_scope"]["accepts"]
            == ["v1.7-comfort-phase1b-hardware-acceptance"],
        "v1.7 Comfort packed-media proof drift")
    print("v1.7 Comfort Phase 1b media: CHECK PASS contact=one-owner-session")


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
