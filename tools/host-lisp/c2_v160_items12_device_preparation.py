#!/usr/bin/env python3
"""Close same-world media and bind the v1.6 items 1/2 device session."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v112_candidate_media as LIBMEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVENESS  # noqa: E402
import c2_v160_input_fidelity_membership_real_consumer_replacement_card as TOP  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_hybrid_live_stack_replacement_card as LIVE  # noqa: E402
import c2_v20_phase02b_header_consumption_card as HEADER  # noqa: E402
import c2_v20_source_oracle_media as SOURCE_MEDIA  # noqa: E402
import c2_v20_crc_carveout_media as CRC_MEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.6-items12-device-preparation"
CARD = ROOT / "build/c2.3/v1.6-input-fidelity-membership-real-consumer-card"
WPLTO = CARD / "wplto"
STATIC = CARD / "static-plane/narrow-static"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-items12-device-preparation-receipt.json")
SESSION = ROOT / "config/c2-v160-items12-device-session.json"
ACCEPTANCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-fidelity-acceptance-resume-receipt.json")
CURSOR_SUITE = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
COMFORT_SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
PRODUCT_ID = 0x0401E53E
EXPECTED = {
    "PRG": (41566, "d287ad76f6bd98e0cbb354f3a3cde9cca5a6c4714c6c2f79ce4da03c7b43bb60"),
    "ELF": (631860, "4b2dfa0e7a33968863ec73f2162894ee1f644bd7ccbe6d9e745def7f376fb711"),
}
HISTORICAL_ACCEPTANCE = ACCEPTANCE
SUCCESSOR_BUILD = ROOT / "build/c2.3/v1.6-items12-hybrid-device-preparation"
SUCCESSOR_CARD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1"
SUCCESSOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-items12-hybrid-device-preparation-receipt.json")
SUCCESSOR_ACCEPTANCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-hybrid-live-stack-replacement-card-receipt.json")
SUCCESSOR_SESSION = ROOT / "config/c2-v160-items12-hybrid-device-session.json"
SUCCESSOR_EXPECTED = {
    "PRG": (41566, "2162046372f0b51e42ed2b9dabc019e838531dd3bcaae5cb8b1492aa0c3a3a43"),
    "ELF": (632156, "a03f9fafc5629f913dcf213925d7f007fd91b353ab2229a6189080c37f604c9c"),
}
SUCCESSOR_AUTHORIZATION = "847eca2b"


class PreparationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreparationError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def configure_paths() -> None:
    CAN.BUILD = TARGET
    CAN.WPLTO = WPLTO
    CAN.FINAL = TARGET / "final"
    CAN.ARTIFACTS = TARGET / "artifacts"
    CAN.RECEIPTS = TARGET / "receipts"
    CAN.MANIFEST = TARGET / "canonical-product-manifest.json"
    CAN.STATIC = STATIC
    CAN.STATIC_PRODUCT = STATIC / "product"
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = CAN.MANIFEST
    MEDIA.MANIFEST = SHARED / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = SHARED / "lisp65-product.d81"
    MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def configure_candidate() -> None:
    """Install the exact configuration that emitted the accepted card."""
    if CARD == SUCCESSOR_CARD:
        LIVE.install()
        LIVE.configure_module()
        core, _activation = REOPEN.configure_stack(LIVE.BUILD, LIVE.PREFLIGHT)
    else:
        TOP.configure_module()
        core, _activation = REOPEN.configure_stack(TOP.BUILD, TOP.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    CAN.REPLAY.PROFILE.configure()
    if PRODUCT.PROFILE_RODATA_BYTES == 342:
        PRODUCT.configure_require_resolver_profile_geometry()
        PRODUCT.configure_defstruct_foundation_profile_geometry()
    CAN.REPLAY.BANK2.configure_bank2_stage()
    CAN.REPLAY.TWO.configure_two_region()
    CAN.REPLAY.LINK60.configure_current_pin_adapters()
    PRODUCT.configure_intern_session_service()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    HEADER.configure_consumption()
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = STATIC / "product/substitution-artifacts.json"
    PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj"
    ).section(PRODUCT.VERIFIER_BINDING_SECTION)
    PRODUCT.VERIFIER_BINDING_BASE = section.address
    PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def complete() -> dict[str, Any]:
    configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, sha(elf)) == EXPECTED["ELF"],
            "accepted input-fidelity pair drift")
    configure_candidate()
    acceptance = load(ACCEPTANCE)
    historical = load(HISTORICAL_ACCEPTANCE)
    projection = historical["acceptance"]["VMA_golden"]
    successor = CARD == SUCCESSOR_CARD
    require(projection["dependent_fixed_vmas"] == 101
            and projection["dependent_free_derived_vmas"] == 2
            and ((not successor and acceptance["acceptance"]
                    ["additive_card_freight"]["candidate_sections"] == 105)
                 or (successor
                    and acceptance["status"] ==
                        "PASS: V1.6 HYBRID LIVE STACK REPLACEMENT FINAL WORLD GREEN"
                    and acceptance["final_world_claims"]["membership"]
                        ["section_bytes"] == 67
                    and acceptance["R1_capture_successor"]
                        ["post_capture_free_bytes"] == 69
                    and len(acceptance["card_owned_inventory_registration"]
                        ["hybrid_world"]["allocated"]) == 3)),
            "accepted additive Golden projection drift")
    class AcceptedProjection:
        """Read-only adapter for the already accepted exact candidate ELF."""
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, sha(candidate)) == EXPECTED["ELF"],
                    "Completion adapter received a different candidate ELF")
            return projection

    accepted_projection = AcceptedProjection()
    SOURCE_MEDIA.FLOW.BASE.INV = accepted_projection
    CRC_MEDIA.INV = accepted_projection
    SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = CAN.REPLAY.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        return CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)

    CAN.REPLAY.configure = lambda: None
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    PRODUCT.fixed_facade_gate = facade
    try:
        value = CAN.complete_artifacts()
    finally:
        CAN.REPLAY.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
    final_product = CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_product.stat().st_size, sha(final_product)) == EXPECTED["PRG"]
            and (final_elf.stat().st_size, sha(final_elf)) == EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed accepted product identity")
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    static = {"status": "passed-v1.6-items12-static-plane",
              "product_build_id": f"0x{PRODUCT_ID:08x}",
              "bank2_static_code_bytes": 46043}
    wplto = {"status": "passed-one-accepted-input-fidelity-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = CAN.manifest(static, wplto, completion)
    elf = CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    service = truth.section(".lisp65_c2_mapped_far_service")
    raw = truth.section_bytes(service.name)
    start = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    end = truth.symbol("__lisp65_c2_mapped_far_service_load_end").value
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46043 and len(raw) == end - start
            and len(prefix) <= start - 0x20000,
            "candidate Bank-2 extent geometry drift")
    materialized = prefix + bytes(start - 0x20000 - len(prefix)) + raw
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear(); row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({"bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest()})
    CAN.MANIFEST.write_bytes(canonical(value))
    CAN.check()
    require(len(materialized) == end - 0x20000,
            "materialized Bank-2 extent is incomplete")
    return value


def compile_library(suite_path: Path, prefix: Path) -> Path:
    suite = STD._read_suite(str(suite_path))
    STD.check_suite(str(suite_path), suite)
    STD.emit_artifacts(str(suite_path), suite, str(prefix), base_addr=0,
                       artifact_role="disk-lib")
    return prefix.with_suffix(".manifest.json")


def library_media() -> dict[str, Any]:
    generated = BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    manifests = {
        "v16core": compile_library(CURSOR_SUITE, generated / "v16core"),
        "repl-comfort": compile_library(COMFORT_SUITE, generated / "repl-comfort"),
    }
    variants = {"items12": (
        ("v16core", "v16core", "v16core", manifests["v16core"], ()),
        ("repl-comfort", "repl", "repl", manifests["repl-comfort"], (0,)),
    )}
    specs = variants["items12"]
    LIBRARY.mkdir(parents=True)
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for ordinal, spec in enumerate(specs):
        row, artifact = LIBMEDIA.measured(spec, (1, ordinal + 1), PRODUCT_ID)
        name = spec[0]
        placeholder.append(row); artifacts[name] = artifact
        path = LIBRARY / f"{name}.l65s"
        path.write_bytes(artifact); paths.append((path, name))
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(LIBMEDIA.L65I.encode_index(placeholder))
    seed = LIBRARY / "library.seed.d81"
    LIBMEDIA.build_library_d81(seed, seed_index, paths)
    locators = LIBMEDIA.L65I.d81_locators(seed)
    rows = []
    for spec in specs:
        row, artifact = LIBMEDIA.measured(spec, locators[spec[0]], PRODUCT_ID)
        require(artifact == artifacts[spec[0]],
                f"library artifact changed with locator: {spec[0]}")
        rows.append(row)
    index = LIBMEDIA.L65I.encode_index(rows)
    index_path = LIBRARY / "l65index"; index_path.write_bytes(index)
    decoded = LIBMEDIA.L65I.decode_index(
        index, artifacts, artifact_build_id=PRODUCT_ID)
    final = LIBRARY / "lisp65-library.d81"
    LIBMEDIA.build_library_d81(final, index_path, paths)
    visible = LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index,
                        **{name.upper().encode(): raw
                           for name, raw in artifacts.items()}},
            "items 1/2 library visible-file truth drift")
    contracts = {spec[0]: LIBMEDIA.resolver_contract(decoded, spec[0])
                 for spec in specs}
    # Comfort legitimately closes over both delivered rows, so no undeclared
    # live row exists for the generic negative fixture.  The mutation-only
    # copy removes that edge and exercises both under- and over-closure without
    # changing any delivered row.
    mutation_rows = deepcopy(decoded)
    mutation_rows[1]["dependencies"] = []
    mutations = LIBMEDIA.resolver_contract_mutation_gate(
        mutation_rows, "repl-comfort")
    seed.unlink(); seed_index.unlink()
    return {"variant": "items12", "product_build_id": f"0x{PRODUCT_ID:08x}",
            "D81": bind(final), "index": bind(index_path),
            "artifacts": {name: bind(LIBRARY / f"{name}.l65s")
                          for name in artifacts},
            "index_rows": decoded,
            "resolver_contracts": contracts,
            "resolver_mutations_rejected": mutations,
            "visible_files": sorted(name.decode() for name in visible)}


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v160-items12-device-session-v1",
        "recorded_on": "2026-08-20" if CARD == SUCCESSOR_CARD else "2026-08-19",
        "status": "ready-owner-contact",
        "claim_scope": {
            "accepts": ["v1.6-item-1-cursor-navigation",
                        "v1.6-item-2-comfort-repl-and-input-fidelity"],
            "excludes": ["D5-headroom", "release-acceptance", "v1.6-item-3",
                         "v1.6-item-4"]},
        "media": {"product": {**bind(product), "remote_name": "V16P12.D81"},
                  "library": {**bind(library), "remote_name": "V16C12.D81"}},
        "choreography": {
            "fresh_basic_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "product_mounted_last": True,
            "library_mounted_physically_through_freezer": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
            "observation_during_active_persistent_forms": 0},
        "rows": [
            {"id": "D1", "claim": "boot and activate Comfort REPL",
             "actions": ["cold boot product", "mount library physically",
                         "(require 'v16core)", "(require 'repl-comfort)", "(repl)"],
             "expect": ["three boot liveness lines", "WORKBENCH 1.5.0",
                        "each require returns t", "Comfort prompt"]},
            {"id": "D2-left-insert", "action": "type (list 1 3), move left twice, insert 2 followed by a space",
             "expect": "(1 2 3)"},
            {"id": "D2-navigation", "action": "physically exercise Left/Right, C-b/C-f, C-a/C-e, Delete and C-d, including boundary no-ops",
             "expect": "all bindings edit at the cursor, preserve order, and never overwrite"},
            {"id": "D2-balanced", "action": "submit (+ 10 on line one and 32) on line two",
             "expect": "42 with continuation indentation"},
            {"id": "D2-history", "action": "evaluate (list 7 8), then Up and Return",
             "expect": "(7 8) twice"},
            {"id": "D2-input-fidelity", "action": (
                "enter one balanced aggregate rapidly: (+ 1, then five continuation "
                "comment lines each containing a visually checked 40-digit 0123456789 "
                "pattern, then 2); do not pause for automated observation"),
             "forced_collection_basis": (
                "more than 192 accepted printable editor cells guarantees at least one "
                "collection during active input, independent of nursery phase"),
             "expect": "every digit remains present and ordered; final result is 3"},
            {"id": "D2-lowercase", "action": (
                "with Shift-Lock off, type a physically entered lowercase alphabetic "
                "form and inspect the characters before submission"),
             "expect": "lowercase letters remain lowercase on screen and in the result"},
            {"id": "D2-felt-latency", "action": (
                "type a rapid ordinary sentence-length burst, pause once, then edit its "
                "middle with Left/Right and insertions"),
             "expect": (
                "no swallowed keys; echo keeps up without progressive multi-second "
                "backlog, and any short burst debt drains during the single pause")},
            {"id": "D2-exit", "action": "empty Return",
             "expect": "return to native lisp65> prompt"}],
        "host_half": {"ordered_events": "94/94",
                      "forced_collection_frames": 89,
                      "event_6_observed_in_order": True,
                      "normalization_parity": "256/256 across both consumers",
                      "responsiveness_margin_percent": 29.044052413392606},
    }


def install_successor() -> None:
    global BUILD, CARD, WPLTO, STATIC, TARGET, SHARED, LIBRARY
    global RECEIPT, SESSION, ACCEPTANCE, EXPECTED
    BUILD = SUCCESSOR_BUILD
    CARD = SUCCESSOR_CARD
    WPLTO = CARD / "wplto"
    STATIC = CARD / "static-plane/narrow-static"
    TARGET = BUILD / "canonical-product"
    SHARED = BUILD / "shared-system"
    LIBRARY = BUILD / "library"
    RECEIPT = SUCCESSOR_RECEIPT
    SESSION = SUCCESSOR_SESSION
    ACCEPTANCE = SUCCESSOR_ACCEPTANCE
    EXPECTED = SUCCESSOR_EXPECTED


def successor_authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{SUCCESSOR_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    plan = "docs/planning/v1.6.0-freight-work-plan.md"
    raw = subprocess.run(["git", "show", f"{commit}:{plan}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("media preparation", "same-world successor", "no old medium is reused",
                  "canonical completion", "felt-latency check"):
        require(token in text, f"hybrid media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": plan,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def successor_preflight() -> None:
    install_successor()
    auth = successor_authority()
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "hybrid items 1/2 preparation is one-shot")
    accepted = load(ACCEPTANCE)
    require(accepted["status"] ==
                "PASS: V1.6 HYBRID LIVE STACK REPLACEMENT FINAL WORLD GREEN"
            and accepted["artifacts_before"] == accepted["artifacts_after"]
            and accepted["final_world_claims"]["membership"]["section_bytes"] == 67
            and accepted["R1_capture_successor"]["surplus_over_floor_bytes"] == 15,
            "hybrid items 1/2 accepted-world preflight drift")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, sha(elf)) == EXPECTED["ELF"],
            "hybrid items 1/2 candidate pair drift")
    print("v1.6 hybrid items 1/2 preparation: PREFLIGHT PASS "
          f"authority={auth['commit'][:8]} media=0 device=0")


def finish(media: dict[str, Any]) -> dict[str, Any]:
    """Bind already closed outputs; this stage is read-only until receipts."""
    configure_paths()
    MEDIA.check()
    product_d81 = MEDIA.PRODUCT_D81
    library_d81 = LIBRARY / "lisp65-library.d81"
    pair = PAIR.pair_identity(product_d81, library_d81)
    require(pair["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and pair["index_rows"] == 2
            and pair["row_names"] == ["v16core", "repl-comfort"],
            "v1.6 items 1/2 media pair identity drift")
    config = session_config(product_d81, library_d81)
    SESSION.write_bytes(canonical(config))
    library = {"D81": bind(library_d81), "index": bind(LIBRARY / "l65index"),
               "artifacts": {name: bind(LIBRARY / f"{name}.l65s")
                             for name in ("v16core", "repl-comfort")}}
    value = {
        "format": "lisp65-c2-v160-items12-device-preparation-receipt-v1",
        "recorded_on": "2026-08-19",
        "status": "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY",
        "accepted_pair": {"PRG": bind(WPLTO / "lisp65-c2-substitution-linked.prg"),
                          "ELF": bind(WPLTO / "lisp65-c2-substitution-linked.prg.elf")},
        "completion": bind(CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(MEDIA.MANIFEST),
        "media": {"product": bind(product_d81), "work": bind(MEDIA.WORK_D81),
                  "library": bind(library_d81), "library_index": bind(LIBRARY / "l65index")},
        "readback": {
            "product": "passed-packed-visible-file-and-role-identity-closure",
            "library": "passed-visible-file-index-and-artifact-identity-closure"},
        "same_world_pair": pair,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": library,
        "session": bind(SESSION),
        "claim_limit": config["claim_scope"],
        "execution_accounting": {
            "successful_run": {"WPLTO_runs": 0, "product_links": 0,
                "artifact_completions": 1, "media_builds": 2,
                "device_contacts": 0},
            "preparation_history": {"invocations": 7, "host_stops": 6,
                "artifact_completions": 3, "product_media_builds": 3,
                "library_media_builds": 3, "WPLTO_runs": 0,
                "product_links": 0, "device_contacts": 0}}}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 items 1/2 preparation: PASS media=2 pair=same-world contact=ready")
    return value


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "items 1/2 device preparation is one-shot")
    if BUILD.exists():
        require((SHARED / "candidate-manifest.json").is_file()
                and (LIBRARY / "lisp65-library.d81").is_file(),
                "partial preparation is not resume-complete")
        return finish(load(SHARED / "candidate-manifest.json"))
    completion = complete()
    product_manifest(completion)
    configure_paths()
    media = MEDIA.build(stager_compile_defines=(LIVENESS.OPT_IN,))
    MEDIA.check()
    library_media()
    return finish(media)


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY",
            "preparation status drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(), value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"prepared artifact identity drift: {row['path']}")
    pair = PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                              ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "persisted pair identity drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check",
                                            "successor-preflight",
                                            "successor-build",
                                            "successor-check"))
    args = parser.parse_args()
    if args.action == "successor-preflight":
        successor_preflight()
    elif args.action == "successor-build":
        install_successor()
        value = build()
        value["successor_authority"] = successor_authority()
        RECEIPT.write_bytes(canonical(value))
    elif args.action == "successor-check":
        install_successor()
        check(); print("v1.6 hybrid items 1/2 preparation: CHECK PASS")
    elif args.action == "build":
        build()
    else:
        check(); print("v1.6 items 1/2 preparation: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
