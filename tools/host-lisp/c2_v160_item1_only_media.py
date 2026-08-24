#!/usr/bin/env python3
"""Pack the owner-selected v1.6 item-1-only product and library world."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_clean_product_acceptance_media as MEDIA  # noqa: E402
import c2_v160_item1_only_candidate as ITEM1  # noqa: E402


PREP = MEDIA.BASE
NESTED = MEDIA.ENGINE.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-item1-only-media-r1-public2"
ADAPTER = BUILD.parent / "v1.6-item1-only-media-r1-public2-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-item1-only-media-r1-public2-receipt.json"
SESSION = ROOT / "config/c2-v160-item1-only-r1-public2-session.json"
DEVICE_RESULT = ARCH / (
    "c2.3-v1.6-item1-only-r1-public2-device-result-receipt.json")
DEPLOY_READBACK = BUILD / "deploy-readback"
AUTHORIZATION = "3c60ab50"
PRODUCT_REMOTE = "V16I1Q.D81"
LIBRARY_REMOTE = "V16I1QL.D81"
EXPECTED = {
    "PRG": (41566,
            "4d80051c80473e26f3a8b4582d8e0200ec9d15e5e6faa4e1cd7984e6a97b4f6c"),
    "ELF": (646192,
            "82bc474e61a0ba4691abe52c3f0c8fcf6e26335f533df2d59ddd3ab2f3eba489"),
}
STATUS = "PASS: V1.6 ITEM 1 ONLY R1 PUBLIC2 ACCEPTANCE MEDIA READY"
DEVICE_STATUS = "PASS: V1.6 ITEM 1 HARDWARE ACCEPTED; HALT A REACHED"
BASE_PREPARATION_STATUS = "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY"


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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("v1.6 ships item 1 alone", "fresh media",
                  "native lisp65> only", "d5 without repl-comfort"):
        require(token in text, f"item-1 media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def emitted_public_input_gate(prefix: Path) -> dict[str, Any]:
    """Prove the public-mode projection in the bytecode that ships."""
    disasm_path = Path(str(prefix) + ".disasm.txt")
    manifest_path = Path(str(prefix) + ".manifest.json")
    disasm = disasm_path.read_text(encoding="utf-8")
    blocks = {match.group(1): match.group(2) for match in re.finditer(
        r"(?ms)^\[\d+\] ([^\n]+)\n(.*?)(?=^\[\d+\] |\Z)", disasm)}
    required = {"%rl-render", "%rl-put", "%read-line-loop"}
    require(required.issubset(blocks),
            "public input functions absent from emitted v16core")
    call = "CALLPRIM prim=60:key-event argc=1"
    require(call not in blocks["%rl-render"]
            and call not in blocks["%rl-put"],
            "private key-event consumer survived in emitted public editor")
    require(disasm.count(call) == 1
            and blocks["%read-line-loop"].count(call) == 1
            and re.search(r"PUSHI8 1\n\s+[0-9a-f]+ " + re.escape(call),
                          blocks["%read-line-loop"]) is not None,
            "emitted public editor does not consume exactly key-event mode 1")
    return {
        "manifest": bind(manifest_path),
        "disassembly": bind(disasm_path),
        "private_key_event_calls": 0,
        "public_key_event_calls": 1,
        "public_key_event_modes": [1],
        "private_consumers_checked": ["%rl-render", "%rl-put"],
        "public_consumer": "%read-line-loop",
    }


def library_media() -> dict[str, Any]:
    """Build a one-row library D81; Comfort is absent from delivered bytes."""
    generated = PREP.BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    public_source = generated / "stdlib-read-line-item1.lisp"
    public_source.write_text(ITEM1.CURSOR.public_only_source(
        ITEM1.CURSOR.READ_LINE.read_text(encoding="utf-8")), encoding="utf-8")
    public_suite = generated / "v16core-item1-suite.json"
    public_suite.write_bytes(canonical({
        "extends": str(PREP.CURSOR_SUITE.resolve()),
        "sources": [public_source.relative_to(ROOT).as_posix()],
        "remove_sources": [ITEM1.CURSOR.READ_LINE.relative_to(ROOT).as_posix()],
        "resident_suite": str((ROOT /
            "config/c2-v160-comfort-repl-device-resident.json").resolve()),
        "private_key_event_modes": False,
        "description": (
            "Item-1 projection: public cursor editor with key-event modes 0/1; "
            "Comfort modes 2/3 are not emitted."),
    }))
    prefix = generated / "v16core"
    manifest = PREP.compile_library(public_suite, prefix)
    emitted = emitted_public_input_gate(prefix)
    spec = ("v16core", "v16core", "v16core", manifest, ())
    PREP.LIBRARY.mkdir(parents=True)
    row, artifact = PREP.LIBMEDIA.measured(spec, (1, 1), PREP.PRODUCT_ID)
    artifact_path = PREP.LIBRARY / "v16core.l65s"
    artifact_path.write_bytes(artifact)
    seed_index = PREP.LIBRARY / "l65index.seed"
    seed_index.write_bytes(PREP.LIBMEDIA.L65I.encode_index([row]))
    seed = PREP.LIBRARY / "library.seed.d81"
    PREP.LIBMEDIA.build_library_d81(
        seed, seed_index, [(artifact_path, "v16core")])
    locators = PREP.LIBMEDIA.L65I.d81_locators(seed)
    row, located = PREP.LIBMEDIA.measured(
        spec, locators["v16core"], PREP.PRODUCT_ID)
    require(located == artifact, "v16core changed with final locator")
    index = PREP.LIBMEDIA.L65I.encode_index([row])
    index_path = PREP.LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = PREP.LIBMEDIA.L65I.decode_index(
        index, {"v16core": artifact}, artifact_build_id=PREP.PRODUCT_ID)
    require(len(decoded) == 1 and decoded[0]["name"] == "v16core",
            "item-1 library contains a second row")
    contract = PREP.LIBMEDIA.resolver_contract(decoded, "v16core")

    rejected: dict[str, str] = {}
    for label, actual in (("omitted-only-row", []),
                          ("duplicated-only-row", [0, 0])):
        try:
            PREP.LIBMEDIA.resolver_contract(
                deepcopy(decoded), "v16core", actual_override=actual)
        except PREP.LIBMEDIA.MediaClosureError as error:
            rejected[label] = str(error)
        else:
            raise RuntimeError(f"item-1 resolver mutation survived: {label}")

    final = PREP.LIBRARY / "lisp65-library.d81"
    PREP.LIBMEDIA.build_library_d81(
        final, index_path, [(artifact_path, "v16core")])
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index, b"V16CORE": artifact}
            and b"REPL-COMFORT" not in visible,
            "item-1 library visible-file closure drift")
    seed.unlink(); seed_index.unlink()
    return {
        "variant": "item-1-only",
        "product_build_id": f"0x{PREP.PRODUCT_ID:08x}",
        "D81": bind(final), "index": bind(index_path),
        "artifacts": {"v16core": bind(artifact_path)},
        "index_rows": decoded,
        "resolver_contracts": {"v16core": contract},
        "resolver_mutations_rejected": rejected,
        "visible_files": sorted(name.decode() for name in visible),
        "Comfort_absent": True,
        "public_only_projection": {
            "source": bind(public_source), "suite": bind(public_suite),
            "key_event_modes": [0, 1], "emitted_artifact_gate": emitted},
    }


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v160-item1-only-r1-public2-device-session-v1",
        "recorded_on": "2026-08-24",
        "status": "ready-owner-contact",
        "claim_scope": {
            "accepts": ["v1.6-item-1-cursor-navigation"],
            "green_consequence": "item 1 accepted; Halt A follows",
            "excludes": ["v1.6-item-2-comfort-repl", "lossless-input",
                         "D5-headroom", "release-acceptance", "v1.6-item-3",
                         "v1.6-item-4"],
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
            {"id": "I1-boot", "actions": [
                "cold boot product", "mount library physically",
                "submit (require 'v16core)"],
             "expect": ["three boot liveness lines", "native lisp65> prompt",
                        "require returns t; repl-comfort is not delivered"]},
            {"id": "I1-left-insert", "actions": [
                "submit (read-line)", "type abde", "press Left twice",
                "insert c and press Return"],
             "expect": "returned string is abcde; insertion does not overwrite"},
            {"id": "I1-navigation", "actions": [
                "in fresh (read-line) inputs exercise Left/Right and C-b/C-f",
                "exercise C-a/C-e then insert at each endpoint",
                "exercise Delete/C-d and boundary no-ops"],
             "expect": "cursor motions and edits preserve order and boundaries"},
            {"id": "I1-abort", "action": "submit (car 1) at native prompt",
             "expect": "ordinary error returns to native lisp65>; no red frame"},
            {"id": "I1-native-echo", "action": "submit (list 1 3)",
             "expect": "native result is (1 3) with no new regression"},
        ],
        "acceptance_bar": {
            "navigation": "all cursor semantics correct",
            "regression": "no regression versus v1.5 at ordinary typing rate",
            "known_v15_fast_input_loss": "documented; not a v1.6 item-1 claim",
            "first_red_regression": (
                "public read-line must accept its first printable byte without "
                "calling private key-event modes"),
        },
        "host_half": {
            "cursor_navigation_cases": "8/8",
            "library_rows": 1,
            "Comfort_product_freight": 0,
        },
    }


def item1_completion() -> dict[str, Any]:
    """Consume the active candidate projection, never the old 107-row world."""
    NESTED.BASE.configure_paths()
    product = NESTED.WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, NESTED.BASE.sha(product)) ==
                NESTED.EXPECTED["PRG"]
            and (elf.stat().st_size, NESTED.BASE.sha(elf)) ==
                NESTED.EXPECTED["ELF"],
            "accepted item-1 pair drift at Completion")
    NESTED.configure_candidate()
    closure = load(NESTED.CLOSURE)
    acceptance = load(NESTED.ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    freight = acceptance["additive_card_freight"]
    registered = freight["registered_sections"]
    require(closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["MAP_fix_closed"] is True
            and acceptance["status"] == "PASS"
            and registered == [".lisp65_c2_mapped_product_cold"]
            and freight["candidate_sections"] ==
                freight["golden_sections"] + len(registered),
            "item-1 candidate projection is not additive and derived")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, NESTED.BASE.sha(candidate)) ==
                        NESTED.EXPECTED["ELF"],
                    "Completion received a different item-1 ELF")
            return projection

    accepted = AcceptedProjection()
    NESTED.BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    NESTED.BASE.CRC_MEDIA.INV = accepted
    NESTED.BASE.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = NESTED.BASE.CAN.REPLAY.configure
    original_fixed = NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = NESTED.BASE.PRODUCT.fixed_facade_gate
    original_kernal = NESTED.BASE.PRODUCT.kernal_freedom_gate
    original_kernal_sections = list(NESTED.BASE.PRODUCT.KERNAL_SECTIONS)

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return NESTED.BASE.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        value = NESTED.BASE.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = NESTED.REPAIR.packed_facade_gate(
            target, Path(str(target) + ".elf"))
        return value

    def item1_kernal(out: Path, target: Path) -> dict[str, object]:
        optional = {
            *map(str, NESTED.BASE.PRODUCT.INPUT_CAPTURE_BUILD_CONFIGURATION[
                "allocated"]),
            *map(str, NESTED.BASE.PRODUCT.INPUT_HYBRID_BUILD_CONFIGURATION[
                "allocated"]),
        }
        truth = NESTED.ElfTruth.read(
            Path(str(target) + ".elf"),
            llvm_readobj=NESTED.BASE.PRODUCT.TOOLCHAIN / "llvm-readobj")
        present = {row.name for row in truth.sections}
        require(not optional.intersection(present),
                "item-1 ELF unexpectedly contains Comfort KERNAL freight")
        # The Completion consumer historically inherited optional names from
        # its module registry.  Bind that consumer to the materialized final
        # profile: inactive optional owners are not missing product sections.
        NESTED.BASE.PRODUCT.KERNAL_SECTIONS[:] = [
            name for name in NESTED.BASE.PRODUCT.KERNAL_SECTIONS
            if name not in optional]
        return original_kernal(out, target)

    NESTED.BASE.CAN.REPLAY.configure = lambda: None
    NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    NESTED.BASE.PRODUCT.fixed_facade_gate = facade
    NESTED.BASE.PRODUCT.kernal_freedom_gate = item1_kernal
    try:
        value = NESTED.BASE.CAN.complete_artifacts()
    finally:
        NESTED.BASE.CAN.REPLAY.configure = original_configure
        NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        NESTED.BASE.PRODUCT.fixed_facade_gate = original_facade
        NESTED.BASE.PRODUCT.kernal_freedom_gate = original_kernal
        NESTED.BASE.PRODUCT.KERNAL_SECTIONS[:] = original_kernal_sections
    final_product = NESTED.BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_elf.stat().st_size, NESTED.BASE.sha(final_elf)) ==
                NESTED.EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "artifact-only Completion rebuilt the item-1 pair")
    NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
    return value


def finish(media: dict[str, Any]) -> dict[str, Any]:
    PREP.configure_paths()
    PREP.MEDIA.check()
    product_d81 = PREP.MEDIA.PRODUCT_D81
    library_d81 = PREP.LIBRARY / "lisp65-library.d81"
    pair = PREP.PAIR.pair_identity(product_d81, library_d81)
    require(pair["product_build_id"] == f"0x{PREP.PRODUCT_ID:08x}"
            and pair["index_rows"] == 1
            and pair["row_names"] == ["v16core"],
            "item-1 product/library pair identity drift")
    config = session_config(product_d81, library_d81)
    PREP.SESSION.write_bytes(canonical(config))
    value = {
        "format": "lisp65-c2-v160-item1-only-media-r1-public2-receipt-v1",
        "recorded_on": "2026-08-24",
        # The historical wrapping chain consumes this intermediate status and
        # then promotes the same receipt through every artifact-only layer.
        "status": BASE_PREPARATION_STATUS,
        "accepted_pair": {
            "PRG": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
        },
        "completion": bind(PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product_d81), "work": bind(PREP.MEDIA.WORK_D81),
                  "library": bind(library_d81),
                  "library_index": bind(PREP.LIBRARY / "l65index")},
        "readback": {
            "product": "passed-packed-visible-file-and-role-identity-closure",
            "library": "passed-one-row-index-and-artifact-identity-closure"},
        "same_world_pair": pair,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": {
            "D81": bind(library_d81),
            "index": bind(PREP.LIBRARY / "l65index"),
            "artifacts": {"v16core": bind(PREP.LIBRARY / "v16core.l65s")},
            "row_names": ["v16core"], "Comfort_absent": True,
            "public_only_projection": {
                "source": bind(PREP.BUILD / "library-inputs/stdlib-read-line-item1.lisp"),
                "suite": bind(PREP.BUILD / "library-inputs/v16core-item1-suite.json"),
                "key_event_modes": [0, 1],
                "emitted_artifact_gate": emitted_public_input_gate(
                    PREP.BUILD / "library-inputs/v16core")}},
        "session": bind(PREP.SESSION),
        "claim_limit": config["claim_scope"],
        "execution_accounting": {
            "successful_run": {"WPLTO_runs": 0, "product_links": 0,
                "artifact_completions": 1, "media_builds": 2,
                "device_contacts": 0}},
    }
    PREP.RECEIPT.write_bytes(canonical(value))
    print("v1.6 item-1 preparation: PASS media=2 rows=1 contact=ready")
    return value


def preparation_check() -> dict[str, Any]:
    value = load(PREP.RECEIPT)
    require(value["status"] in (BASE_PREPARATION_STATUS, STATUS)
            and value["same_world_pair"]["index_rows"] == 1
            and value["same_world_pair"]["row_names"] == ["v16core"]
            and value["library_closure"]["Comfort_absent"] is True
            and value["library_closure"]["public_only_projection"]
                ["emitted_artifact_gate"]["private_key_event_calls"] == 0
            and value["library_closure"]["public_only_projection"]
                ["emitted_artifact_gate"]["public_key_event_calls"] == 1,
            "item-1 preparation receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(), value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"item-1 prepared artifact identity drift: {row['path']}")
    pair = PREP.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "item-1 pair identity drift")
    return value


def device_result() -> dict[str, Any]:
    """Bind the owner's physical-keyboard result to the staged byte world."""
    media = load(RECEIPT)
    require(media["status"] == STATUS
            and media["same_world_pair"]["index_rows"] == 1
            and media["same_world_pair"]["row_names"] == ["v16core"]
            and media["library_closure"]["Comfort_absent"] is True
            and media["library_closure"]["public_only_projection"]
                ["emitted_artifact_gate"]["private_key_event_calls"] == 0
            and media["library_closure"]["public_only_projection"]
                ["emitted_artifact_gate"]["public_key_event_calls"] == 1,
            "item-1 final media receipt drift at device-result binding")
    for row in [*media["accepted_pair"].values(),
                *media["media"].values(), media["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"item-1 device input identity drift: {row['path']}")
    session = load(SESSION)
    product_readback = DEPLOY_READBACK / PRODUCT_REMOTE
    library_readback = DEPLOY_READBACK / LIBRARY_REMOTE
    require(product_readback.read_bytes() ==
                (ROOT / media["media"]["product"]["path"]).read_bytes(),
            "deployed item-1 product readback mismatch")
    require(library_readback.read_bytes() ==
                (ROOT / media["media"]["library"]["path"]).read_bytes(),
            "deployed item-1 library readback mismatch")
    require(session["claim_scope"] == media["claim_limit"],
            "item-1 device claim boundary drift")
    return {
        "format": "lisp65-c2-v160-item1-only-r1-public2-device-result-v1",
        "recorded_on": "2026-08-24",
        "status": DEVICE_STATUS,
        "authority": {
            "media_preparation": bind(RECEIPT),
            "session": bind(SESSION),
            "recorder": bind(Path(__file__).resolve()),
        },
        "delivered_identity": {
            "product": media["media"]["product"],
            "product_readback": bind(product_readback),
            "library": media["media"]["library"],
            "library_readback": bind(library_readback),
            "accepted_pair": media["accepted_pair"],
        },
        "choreography": {
            **session["choreography"],
            "device": "/dev/ttyUSB1",
            "owner_observed": True,
            "red_frames": 0,
            "hangs": 0,
        },
        "results": {
            "boot": {
                "native_prompt": "lisp65>",
                "library_mount_returned": True,
                "require_v16core": "t",
            },
            "first_red_retest": {
                "stimulus": "read-line; type abde; Left twice; insert c",
                "result": "abcde",
                "first_printable_byte_accepted": True,
                "insertion_overwrite": False,
            },
            "mixed_navigation": {
                "bindings": ["Left", "Right", "C-b", "C-f"],
                "result": "abcdef",
            },
            "endpoints": {
                "bindings": ["C-a", "C-e"],
                "result": "abcd",
            },
            "deletion_and_boundaries": {
                "bindings": ["Delete", "C-d"],
                "left_boundary_noop": True,
                "right_boundary_noop": True,
                "result": "abcd",
            },
            "abort_recovery": {
                "non_error_probe": {"form": "(car 1)", "result": "nil",
                    "classification": "valid dialect semantics; not an abort"},
                "error_probe": {"form": "(>= nil 32)",
                    "result": "*** vm: type error"},
                "returned_to_native_prompt": True,
            },
            "native_echo": {"form": "(list 1 3)", "result": "(1 3)"},
        },
        "acceptance": {
            "cursor_navigation": "PASS",
            "ordinary_rate_v1.5_regression": "PASS",
            "public_input_first_red": "FIXED-ON-DEVICE",
            "item_1": "ACCEPTED",
            "Halt_A": "REACHED-UNDER-OWNER-ITEM1-ONLY-DISPOSITION",
        },
        "claim_limit": session["claim_scope"],
        "next": "D5-headroom-without-repl-comfort-then-release-ladder",
    }


def validate_device_result(value: dict[str, Any], *, verify: bool) -> None:
    results = value.get("results", {})
    acceptance = value.get("acceptance", {})
    require(
        value.get("status") == DEVICE_STATUS
        and results.get("boot", {}).get("require_v16core") == "t"
        and results.get("first_red_retest", {}).get("result") == "abcde"
        and results.get("mixed_navigation", {}).get("result") == "abcdef"
        and results.get("endpoints", {}).get("result") == "abcd"
        and results.get("deletion_and_boundaries", {}).get("result") == "abcd"
        and results.get("deletion_and_boundaries", {}).get(
            "left_boundary_noop") is True
        and results.get("deletion_and_boundaries", {}).get(
            "right_boundary_noop") is True
        and results.get("abort_recovery", {}).get("non_error_probe", {}).get(
            "result") == "nil"
        and results.get("abort_recovery", {}).get("error_probe", {}).get(
            "result") == "*** vm: type error"
        and results.get("abort_recovery", {}).get(
            "returned_to_native_prompt") is True
        and results.get("native_echo", {}).get("result") == "(1 3)"
        and value.get("choreography", {}).get("red_frames") == 0
        and value.get("choreography", {}).get("hangs") == 0
        and acceptance.get("item_1") == "ACCEPTED"
        and acceptance.get("Halt_A") ==
            "REACHED-UNDER-OWNER-ITEM1-ONLY-DISPOSITION",
        "item-1 device result claim drift")
    if verify:
        require(value == device_result(), "item-1 device result receipt stale")


def device_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "change-first-red-result": lambda x: x["results"][
            "first_red_retest"].update(result="type-error"),
        "drop-mixed-binding": lambda x: x["results"][
            "mixed_navigation"]["bindings"].remove("C-f"),
        "change-mixed-result": lambda x: x["results"][
            "mixed_navigation"].update(result="abcde"),
        "lose-left-boundary": lambda x: x["results"][
            "deletion_and_boundaries"].update(left_boundary_noop=False),
        "erase-real-abort": lambda x: x["results"][
            "abort_recovery"]["error_probe"].update(result="nil"),
        "claim-red-frame": lambda x: x["choreography"].update(red_frames=1),
        "withdraw-item-1": lambda x: x["acceptance"].update(item_1="OPEN"),
        "expand-to-comfort": lambda x: x["claim_limit"]["accepts"].append(
            "v1.6-item-2-comfort-repl"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_device_result(trial, verify=False)
            require(trial == device_result(), "mutated result survived identity")
        except RuntimeError:
            rejected.append(name)
    require(rejected == list(cases), "item-1 device result mutation survived")
    return rejected


def device_write() -> None:
    require(not DEVICE_RESULT.exists(), "item-1 device result already exists")
    value = device_result()
    value["mutations_rejected"] = device_mutations(value)
    DEVICE_RESULT.write_bytes(canonical(value))
    print("v1.6 item-1 device result: PASS item=accepted halt-A=reached")


def device_check() -> None:
    value = load(DEVICE_RESULT)
    rejected = value.pop("mutations_rejected", None)
    validate_device_result(value, verify=True)
    require(rejected == device_mutations(value),
            "item-1 device result mutation set drift")
    print("v1.6 item-1 device check: PASS item=accepted halt-A=reached")


def configure() -> None:
    ITEM1.configure()
    MEDIA.CLEAN = ITEM1.BASE
    MEDIA.CARD_BUILD = ITEM1.BUILD
    MEDIA.WPLTO = ITEM1.BUILD / "wplto"
    MEDIA.STATIC = ITEM1.BUILD / "static-plane/narrow-static"
    MEDIA.BUILD = BUILD
    MEDIA.ADAPTER = ADAPTER
    MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION
    MEDIA.CLOSURE = ITEM1.RECEIPT
    MEDIA.ACCEPTANCE = ITEM1.BUILD / "artifact-acceptance.json"
    MEDIA.AUTHORIZATION = AUTHORIZATION
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED
    MEDIA.STATUS = STATUS
    MEDIA.authority = authority
    MEDIA.session_config = session_config
    MEDIA.configure_successor()
    NESTED.complete = item1_completion
    # The historical bottom producer owned two library rows.  Item 1 owns one.
    PREP.library_media = library_media
    PREP.session_config = session_config
    PREP.finish = finish
    PREP.check = preparation_check


def run(action: str) -> None:
    configure()
    if action == "preflight":
        MEDIA.preflight()
    elif action == "build":
        MEDIA.build()
    elif action == "finalize":
        MEDIA.finalize()
        value = load(RECEIPT)
        value["library_closure"]["public_only_projection"][
            "emitted_artifact_gate"] = emitted_public_input_gate(
                BUILD / "library-inputs/v16core")
        RECEIPT.write_bytes(canonical(value))
    elif action == "device-write":
        device_write()
    elif action == "device-check":
        device_check()
    else:
        MEDIA.check()
        value = load(RECEIPT)
        require(value["status"] == STATUS
                and value["same_world_pair"]["index_rows"] == 1
                and value["library_closure"]["Comfort_absent"] is True
                and value["library_closure"]["public_only_projection"]
                    ["emitted_artifact_gate"]["private_key_event_calls"] == 0
                and value["library_closure"]["public_only_projection"]
                    ["emitted_artifact_gate"]["public_key_event_calls"] == 1
                and value["packed_artifact_closure"]["artifact_count"] == 19,
                "item-1 final media gate drift")
        print("v1.6 item-1 media: CHECK PASS rows=1 comfort=absent")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in ("preflight", "build", "finalize", "check",
                      "device-write", "device-check"):
        raise RuntimeError(
            "usage: preflight|build|finalize|check|device-write|device-check")
    run(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 item-1 media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
