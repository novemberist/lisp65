#!/usr/bin/env python3
"""Pack the phase-0 `$22` product/library pair and bind its short session."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v190_blocks_ab_acceptance_media as MEDIA  # noqa: E402
import c2_v17_block3_r10_acceptance_media as BLOCK3  # noqa: E402
import c2_v200_symbol22_first_fault_completion_replacement as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — phase-0 r3 closure and device-session authority — 2026-08-31")
CARD_RECEIPT = CARD.RECEIPT
CARD_BUILD = CARD.BUILD
SOURCE_WPLTO = CARD.COMPLETION
SEED_WPLTO = CARD.BUILD / "wplto"
SCOPE = CARD_BUILD / "owner-scope-result.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
SOURCE_STATIC = CARD.CARD.RELEASE_PLANE_ROOT
BUILD = ROOT / "build/c2.3/v2.0-symbol22-first-fault-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-symbol22-first-fault-device-session.json"
PRODUCT_REMOTE = "V20S22P.D81"
LIBRARY_REMOTE = "V20S22L.D81"
PRODUCT_ID = 0x8C6CC520
PLANE_BYTES = 47469
EXPECTED = {
    "PRG": (41811,
        "1b353c22ee0592dcd5547f9ea46133ed9374c3486ab535d9d32e73ea19758aa4"),
    "ELF": (636100,
        "80fae82f837ceb6e38c64f4adecb9c9f1de935b657c21ee7ab4d324392f6c3f4"),
}
STATUS = "PASS: V2.0 SYMBOL22 FIRST-FAULT DEVICE MEDIA READY"


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


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


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def section_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "device-session authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    normalized = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one short $22 device session", "external %read-line-loop",
                  "press left exactly once", "tag == 0", "before any further input"):
        require(token in normalized, f"device-session authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"r3 {role} identity drift")
    return pair


def prepare_wplto_inputs() -> dict[str, Any]:
    """Project the replacement finals over their immutable seed auxiliaries."""
    if not WPLTO.exists():
        WPLTO.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_WPLTO, WPLTO)
        shutil.copytree(SEED_WPLTO / "fresh-c2-lite-prelink-gates",
                        WPLTO / "fresh-c2-lite-prelink-gates")
    projected = {
        "PRG": bind(WPLTO / "lisp65-c2-substitution-linked.prg"),
        "ELF": bind(WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
    }
    pair = accepted_pair()
    for role in ("PRG", "ELF"):
        require((projected[role]["bytes"], projected[role]["sha256"]) ==
                    (pair[role]["bytes"], pair[role]["sha256"]),
                f"artifact-only WPLTO projection changed r3 {role}")
    require((WPLTO / "fresh-c2-lite-prelink-gates/v6-semantics/"
                     "bank2-static-code.bin").is_file(),
            "seed auxiliaries absent from artifact-only WPLTO projection")
    return {"source_finals": SOURCE_WPLTO.relative_to(ROOT).as_posix(),
            "source_auxiliaries": (SEED_WPLTO /
                "fresh-c2-lite-prelink-gates").relative_to(ROOT).as_posix(),
            "projected_pair": projected,
            "rule": "copy-only overlay; replacement finals dominate seed auxiliaries"}


def authority() -> dict[str, Any]:
    receipt, scope, acceptance = load(CARD_RECEIPT), load(SCOPE), load(ACCEPTANCE)
    pair = accepted_pair()
    require(receipt["status"] == CARD.STATUS
            and receipt["artifacts_before"] == receipt["artifacts_after"]
            and {name: receipt["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == pair
            and scope["status"] == acceptance["status"] == "PASS"
            and receipt["attempt_accounting"] == {
                "seed_WPLTOs": 1, "unqualified_product_links": 1,
                "replacement_product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "r3 closure is not device-media ready")
    return {"independent_review": section_authority(),
            "product_card": bind(CARD_RECEIPT), "scope": bind(SCOPE),
            "acceptance": bind(ACCEPTANCE),
            "right": "artifact-only product media, current-plane external library and one short contact",
            "accounting": {"WPLTO_runs": 0, "product_links": 0,
                           "product_cards": 0, "device_contacts": 0}}


def configure_paths() -> None:
    for name, value in {
        "CARD_BUILD": CARD_BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "BUILD": BUILD, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "CARD_RECEIPT": CARD_RECEIPT, "SCOPE": SCOPE,
        "ACCEPTANCE": ACCEPTANCE, "EXPECTED": EXPECTED,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "STATUS": STATUS, "SESSION": SESSION,
    }.items():
        setattr(MEDIA, name, value)
    MEDIA.PREP.PRODUCT_ID = PRODUCT_ID
    MEDIA.PREP.BUILD = BUILD
    MEDIA.PREP.CARD = CARD_BUILD
    MEDIA.PREP.WPLTO = WPLTO
    MEDIA.PREP.STATIC = STATIC
    MEDIA.PREP.TARGET = TARGET
    MEDIA.PREP.SHARED = SHARED
    MEDIA.PREP.LIBRARY = LIBRARY
    MEDIA.PREP.RECEIPT = RECEIPT
    MEDIA.PREP.SESSION = SESSION
    MEDIA.PREP.ACCEPTANCE = ACCEPTANCE
    MEDIA.PREP.HISTORICAL_ACCEPTANCE = ACCEPTANCE
    MEDIA.PREP.EXPECTED = EXPECTED
    MEDIA.PREP.configure_paths()
    BLOCK3.INPUT_ROOT = BUILD / "library-inputs"


def configure_candidate() -> None:
    """Install exactly the configuration which emitted replacement r3."""
    CARD.configure()
    CARD.configure_seed_world()
    release = CARD.CARD.RELEASE
    release.R8.R7.R6.CARD.CLIENT.INIT._configure_plane_module()
    release.R8.R7.R6.CARD.CLIENT.CURRENT_PLANE.bind_current_plane(STATIC)
    MEDIA.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    MEDIA.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    MEDIA.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(MEDIA.PRODUCT.VERIFIER_BINDING_SECTION)
    require(section.bytes == 40, "r3 verifier-binding size drift")
    MEDIA.PRODUCT.VERIFIER_BINDING_BASE = section.address
    MEDIA.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    # The historical configurator reconstructs the candidate accurately but
    # also restores its phase-owned Completion root.  Media Completion owns a
    # fresh projection of the same bytes, so rebind that consumer after the
    # reconstruction rather than letting it read the historical root.
    configure_paths()


def closure_adapter() -> dict[str, Any]:
    projection = prepare_wplto_inputs()
    configure_paths()
    return {"format": "lisp65-v200-symbol22-device-media-adapter-v1",
            "status": "PASS: REVIEW-SELECTED R3 PAIR MEDIA AUTHORIZED",
            "frozen_pair_before": accepted_pair(),
            "frozen_pair_after": accepted_pair(), "authority": authority(),
            "completion_input_projection": MEDIA.prepare_static_inputs(),
            "WPLTO_input_projection": projection,
            "rule": "artifact-only completion; zero WPLTO and product links"}


def complete_artifacts() -> dict[str, Any]:
    configure_paths()
    pair = accepted_pair()
    configure_candidate()
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    freight = acceptance["additive_card_freight"]
    require(projection["dependent_fixed_vmas"] == 101
            and projection["dependent_free_derived_vmas"] == 2
            and freight["candidate_sections"] == 109
            and [row["name"] for row in freight["freight_rows"]] == [
                ".lisp65_c2_kernal_window.input_capture_helper",
                ".lisp65_c2_kernal_window.input_capture_main",
                ".lisp65_c2_kernal_window.input_consumer",
                ".lisp65_c2_mapped_product_cold",
                ".lisp65_symbol22_first_fault_latch",
                ".lisp65_symbol22_first_fault_state"],
            "r3 accepted projection drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            observed = bind(candidate)
            require((observed["bytes"], observed["sha256"]) ==
                    (pair["ELF"]["bytes"], pair["ELF"]["sha256"]),
                    "Completion received a different r3 ELF")
            return projection

    accepted = AcceptedProjection()
    MEDIA.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    MEDIA.CRC_MEDIA.INV = accepted
    MEDIA.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = MEDIA.CAN.REPLAY.configure
    original_fixed = MEDIA.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = MEDIA.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return MEDIA.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        elf = Path(str(target) + ".elf")
        report = out / "packed-prg-facade-predecessor-rebind.json"
        if not report.exists():
            MEDIA.ITEM_MEDIA.NESTED.materialize_candidate_publish_predecessors(
                out, target, elf)
        value = MEDIA.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = (
            MEDIA.ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(target, elf))
        return value

    MEDIA.CAN.REPLAY.configure = lambda: None
    MEDIA.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    MEDIA.PRODUCT.fixed_facade_gate = facade
    try:
        value = MEDIA.CAN.complete_artifacts()
    finally:
        MEDIA.CAN.REPLAY.configure = original_configure
        MEDIA.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        MEDIA.PRODUCT.fixed_facade_gate = original_facade
    final_prg = MEDIA.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_prg) + ".elf")
    final_elf_id = bind(final_elf)
    require((final_elf_id["bytes"], final_elf_id["sha256"]) ==
                (pair["ELF"]["bytes"], pair["ELF"]["sha256"])
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed the frozen r3 pair")
    facade_gate = MEDIA.ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(
        final_prg, final_elf)
    require(facade_gate["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf",
            "r3 packed PRG facade drift")
    value["packed_PRG_facade"] = facade_gate
    value["completion_product"] = bind(final_prg)
    value["frozen_input_PRG_unchanged"] = pair["PRG"]
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    value = MEDIA.product_manifest(completion)
    value["static_plane"]["status"] = "passed-v2.0-symbol22-r3-static-plane"
    value["static_plane"]["membership_authority"] = (
        "r3 final-ELF composed ownership over the unchanged v1.9 plane")
    MEDIA.CAN.MANIFEST.write_bytes(canonical(value))
    MEDIA.CAN.check()
    return value


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v2.0-symbol22-r3-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 16197
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "r3 composed Bank-2 drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def external_library() -> dict[str, Any]:
    """Build the sealed seam class against the current final plane."""
    configure_paths()
    if LIBRARY.exists():
        shutil.rmtree(LIBRARY)
    value = BLOCK3.library_media()
    require(value["comfort_absent"] is True
            and value["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and value["visible_files"] == ["L65INDEX", "V16CORE"],
            "current-plane external v16core closure drift")
    return value


def external_seam_gate() -> dict[str, Any]:
    """Prove the historical external-caller/resident-callee seam in cargo."""
    manifest_path = BUILD / "library-inputs/v17core.manifest.json"
    manifest = load(manifest_path)
    entries = manifest.get("entries", [])
    callers = [row for row in entries if row.get("name") == "%read-line-loop"]
    require(len(callers) == 1, "external %read-line-loop population drift")
    require(not any(row.get("name") == "%rl-poll" for row in entries),
            "%rl-poll was emitted into the external library")
    literals = callers[0].get("literals", [])
    edge_count = sum(
        1 for row in literals
        if isinstance(row, dict) and row.get("symbol") == "%rl-poll")
    omitted = [
        row for row in manifest.get("omission_gate", {}).get("defuns", [])
        if row.get("name") == "%rl-poll"
    ]
    suites = [Path(row) for row in manifest.get("resident_suites", [])]
    resident = [path for path in suites
                if load(path).get("functions", []).count("%rl-poll") == 1]
    require(edge_count == 1 and len(omitted) == 1 and len(resident) == 1,
            "external %read-line-loop -> resident %rl-poll edge not materialized")
    return {
        "status": "passed-external-read-line-loop-to-resident-rl-poll",
        "manifest": bind(manifest_path),
        "external_caller": {
            "name": callers[0]["name"],
            "ext_addr": callers[0]["ext_addr"],
            "length": callers[0]["length"],
        },
        "literal_edge_count": edge_count,
        "resident_target": omitted[0],
        "resident_suite": bind(resident[0]),
        "external_target_entries": 0,
        "rule": "the shipped external caller names the resident target exactly once",
    }


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v200-symbol22-first-fault-device-session-v1",
        "recorded_on": "2026-08-31",
        "status": "ready-owner-bounded-symbol22-contact",
        "claim_scope": {
            "accepts": ["phase-0-symbol22-three-way-decision"],
            "excludes": ["Comfort-return", "Block-3-return", "repair",
                         "feature-acceptance", "release"],
        },
        "media": {
            "product": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "library": {**bind(library), "remote_name": LIBRARY_REMOTE},
        },
        "seam": {
            "static_plane_bytes": PLANE_BYTES,
            "external_library": "v16core single-row append",
            "required_edge": "external %read-line-loop -> resident %rl-poll",
            "materialized_edge": external_seam_gate(),
            "historical_authority": {
                "hardware": bind(ROOT / "docs/planning/v1.7.0-block3-left-first-red-attribution.md"),
                "host_replay": bind(ROOT / "docs/planning/v1.8.0-block1-symbol22-host-reproduction.md"),
            },
        },
        "choreography": {
            "both_media_uploaded_and_read_back_before_boot": True,
            "fresh_BASIC_first": True,
            "library_mounted_physically_through_freezer": True,
            "product_mounted_last": True,
            "physical_owner_keyboard_only": True,
            "post_boot_automated_access_before_stimulus": 0,
            "one_boot": True, "one_library_append": True,
            "retries": 0,
        },
        "bounded_stimulus": {
            "actions": [
                "wait for the native lisp65> prompt after the external library has loaded",
                "type (list 1 3) without Return",
                "press Cursor-Left exactly once",
                "if an error has already returned to lisp65>, touch no key",
                "otherwise press Return exactly once and wait for result plus lisp65>",
                "touch no further key before the stopped-state read",
            ],
            "maximum_owner_key_events_after_prompt": 12,
            "repeat_until_failure": False,
        },
        "read_cutpoint": {
            "when": "first live prompt after the bounded sequence; after longjmp/cleanup/recovery and before further input",
            "ranges": [
                {"name": "latch-state", "address": "0xC34D", "bytes": 5,
                 "layout": ["tag", "caller-lo", "caller-hi", "name-lo", "name-hi"]},
                {"name": "repl.buf-payload", "address": "0xBC89", "bytes": 34,
                 "layout": "name bytes, NUL-stopped"},
                {"name": "nsym", "address": "0x005A", "bytes": 2,
                 "encoding": "little-endian"},
                {"name": "npool", "address": "0xBE1A", "bytes": 2,
                 "encoding": "little-endian"},
            ],
            "tag_committed_value": "0xA5",
            "tag_zero_meaning": "no recurrence; final-ELF positive control proved firing",
        },
        "decision_table": {
            "tag-A5-resolvable-caller-and-NUL-name": (
                "writer named; price repair; Comfort and Block 3 may reopen"),
            "tag-zero-and-no-visible-symbol22": (
                "no recurrence; request owner residual-risk word with latch retained"),
            "visible-symbol22-without-usable-name": (
                "recurrence without name; Comfort and Block 3 leave v2.0"),
            "any-other-state": "stop for raw-first attribution; no feature claim",
        },
        "positive_control": {
            "final_ELF_executed": True,
            "state_hex": "a567450006",
            "payload_nonzero_bytes": 34,
            "meaning": "tag zero on device is discriminating, not an untested latch",
        },
    }


def finish(packed: dict[str, Any], completion: dict[str, Any],
           library: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    MEDIA.MEDIA.check()
    product = MEDIA.MEDIA.PRODUCT_D81
    library_d81 = LIBRARY / "lisp65-library.d81"
    pair = MEDIA.PREP.PAIR.pair_identity(product, library_d81)
    require(pair["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and pair["index_rows"] == 1 and pair["row_names"] == ["v16core"],
            "product/library current-world identity drift")
    session = session_config(product, library_d81)
    write(SESSION, session)
    value = {
        "format": "lisp65-c2-v200-symbol22-first-fault-device-media-v1",
        "recorded_on": "2026-08-31", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(MEDIA.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(MEDIA.MEDIA.MANIFEST),
        "media": {"product": bind(product),
                  "work": bind(MEDIA.MEDIA.WORK_D81),
                  "library": bind(library_d81),
                  "library_index": bind(LIBRARY / "l65index")},
        "readback": "passed-product-role-and-one-row-library-identity-closure",
        "same_world_pair": pair,
        "library_closure": library,
        "external_seam": external_seam_gate(),
        "packed_artifact_closure": {
            "stager_gate": packed["stager"]["gate"],
            "product_entries": packed["media"]["product"]["entries"],
            "artifact_count": packed["artifact_count"]},
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "session": bind(SESSION), "claim_limit": session["claim_scope"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "library_media_builds": 1, "device_contacts": 0},
    }
    write(RECEIPT, value)
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "phase-0 device media is one-shot")
    adapter = closure_adapter()
    BUILD.mkdir(parents=True, exist_ok=True)
    write(BUILD / "closure-adapter.json", adapter)
    completion = complete_artifacts()
    product_manifest(completion)
    configure_paths()
    packed = MEDIA.MEDIA.build(
        stager_compile_defines=(MEDIA.PREP.LIVENESS.OPT_IN,))
    library = external_library()
    value = finish(packed, completion, library)
    check()
    print("v2.0 symbol22 device media: BUILD PASS product="
          f"{value['media']['product']['sha256']} library="
          f"{value['media']['library']['sha256']} device=0")


def check(*, source_only: bool = False) -> None:
    value, session = load(RECEIPT), load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["same_world_pair"]["row_names"] == ["v16core"]
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "artifact_completions": 1,
                "product_media_builds": 1, "work_media_builds": 1,
                "library_media_builds": 1, "device_contacts": 0}
            and session["bounded_stimulus"]["maximum_owner_key_events_after_prompt"] == 12
            and session["bounded_stimulus"]["repeat_until_failure"] is False
            and value["external_seam"] == session["seam"]["materialized_edge"]
            and value["external_seam"]["status"] ==
                "passed-external-read-line-loop-to-resident-rl-poll"
            and session["read_cutpoint"]["ranges"] == [
                {"name": "latch-state", "address": "0xC34D", "bytes": 5,
                 "layout": ["tag", "caller-lo", "caller-hi", "name-lo", "name-hi"]},
                {"name": "repl.buf-payload", "address": "0xBC89", "bytes": 34,
                 "layout": "name bytes, NUL-stopped"},
                {"name": "nsym", "address": "0x005A", "bytes": 2,
                 "encoding": "little-endian"},
                {"name": "npool", "address": "0xBE1A", "bytes": 2,
                 "encoding": "little-endian"}],
            "phase-0 device receipt/session semantics drift")
    require(bind(SESSION) == value["session"], "session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"prepared artifact identity drift: {row['path']}")
        configure_paths()
        MEDIA.MEDIA.check()
        require(value["composed_bank2"] == static_plane_gate(),
                "persisted composed Bank-2 proof drift")
        require(value["external_seam"] == external_seam_gate(),
                "persisted external seam proof drift")
        require(MEDIA.PREP.PAIR.pair_identity(
            ROOT / value["media"]["product"]["path"],
            ROOT / value["media"]["library"]["path"])
                == value["same_world_pair"],
                "persisted product/library identity drift")
    print("v2.0 symbol22 device media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def refresh_seam() -> None:
    """Persist a proof-only successor without rebuilding either medium."""
    seam = external_seam_gate()
    session = load(SESSION)
    session["seam"]["materialized_edge"] = seam
    write(SESSION, session)
    value = load(RECEIPT)
    value["external_seam"] = seam
    value["session"] = bind(SESSION)
    write(RECEIPT, value)
    check()
    print("v2.0 symbol22 device media: SEAM REFRESH PASS")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "source-check":
        check(source_only=True)
    elif action == "refresh-seam":
        refresh_seam()
    else:
        raise MediaError("usage: build|check|source-check|refresh-seam")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 symbol22 device media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
