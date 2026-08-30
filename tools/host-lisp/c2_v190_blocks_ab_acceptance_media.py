#!/usr/bin/env python3
"""Pack artifact-only v1.9 Block-A/B media and bind the owner session."""

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

import c2_v160_item1_only_media as ITEM_MEDIA  # noqa: E402
import c2_v160_items12_device_preparation as PREP  # noqa: E402
import c2_v17_block3_r10_acceptance_media as R10_MEDIA  # noqa: E402
import c2_v190_native_prompt_editor_display_repair_r7 as R7  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CAN = PREP.CAN
MEDIA = PREP.MEDIA
PRODUCT = PREP.PRODUCT
SOURCE_MEDIA = PREP.SOURCE_MEDIA
CRC_MEDIA = PREP.CRC_MEDIA
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
CARD_BUILD = R7.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = R7.PLANE_ROOT
LIBRARY_SOURCE = R10_MEDIA.LIBRARY_SOURCE
BUILD = ROOT / "build/c2.3/v1.9-blocks-ab-display-r7-acceptance-media"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-acceptance-media-receipt.json")
SESSION = ROOT / "config/c2-v190-blocks-ab-display-r7-acceptance-session.json"
CARD_RECEIPT = R7.RECEIPT
SCOPE = CARD_BUILD / "owner-scope-result.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
PRODUCT_REMOTE = "V19R7P.D81"
EXPECTED = {
    "PRG": (41564,
        "82f4edfdfb1da15b56792b0d8a70cb6095f1d8e3348d30f486cb0cea1e15f7c1"),
    "ELF": (635524,
        "ddba7b5eeb62356ed92d9e9f933d394ceefee7d7e2f1f349496355cfc31ec04a"),
}
PRODUCT_ID = 0x0D247392
PLANE_BYTES = 47468
STATUS = "PASS: V1.9 BLOCKS A+B ACCEPTANCE MEDIA READY"
AUTHORITY_HEADER = (
    "## Block A+B r7 independent review and device-media authority — 2026-08-30")


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    raw = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(AUTHORITY_HEADER) == 1,
            "Block-A/B media authority section drift")
    section = AUTHORITY_HEADER + text.split(AUTHORITY_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    normalized = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only", "forced collection", "one row",
                  "reader: invalid token", "comfort", "all six groups"):
        require(token in normalized, f"Block-A/B media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
            "section": AUTHORITY_HEADER, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {
        "PRG": bind(WPLTO / "lisp65-c2-substitution-linked.prg"),
        "ELF": bind(WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
    }
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"r7 {role} identity drift")
    return pair


def prepare_static_inputs() -> dict[str, Any]:
    if not STATIC.exists():
        STATIC.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_STATIC, STATIC)
    require(bind(SOURCE_STATIC / "v6-semantics/bank2-static-code.bin")["sha256"]
            == bind(STATIC / "v6-semantics/bank2-static-code.bin")["sha256"],
            "r7 static-plane projection differs")
    (STATIC / "libs").mkdir(exist_ok=True)
    rows = []
    for name in ("ide.ext.bin", "idex.ext.bin", "m65d.ext.bin"):
        source = LIBRARY_SOURCE / name
        projected = STATIC / "libs" / name
        if not projected.exists():
            shutil.copyfile(source, projected)
        require(bind(source)["sha256"] == bind(projected)["sha256"],
                f"media library projection differs: {name}")
        rows.append({"name": name, "source": bind(source),
                     "projected": bind(projected)})
    identity = load(STATIC / "product/substitution-artifacts.json")
    require(identity["product_build_id_u32"] == PRODUCT_ID
            and identity["product_build_id_hex"] == f"0x{PRODUCT_ID:08x}",
            "r7 static-plane product identity drift")
    return {"status": "PASS: R7 STATIC INPUTS PROJECTED BYTE-EXACT",
            "source_root": SOURCE_STATIC.relative_to(ROOT).as_posix(),
            "completion_root": STATIC.relative_to(ROOT).as_posix(),
            "libraries": rows,
            "bank2_prefix": bind(STATIC / "v6-semantics/bank2-static-code.bin"),
            "product_identity": bind(STATIC / "product/substitution-artifacts.json")}


def configure_paths() -> None:
    PREP.BUILD = BUILD
    PREP.CARD = CARD_BUILD
    PREP.WPLTO = WPLTO
    PREP.STATIC = STATIC
    PREP.TARGET = TARGET
    PREP.SHARED = SHARED
    PREP.LIBRARY = BUILD / "unused-library"
    PREP.RECEIPT = RECEIPT
    PREP.SESSION = SESSION
    PREP.ACCEPTANCE = ACCEPTANCE
    PREP.HISTORICAL_ACCEPTANCE = ACCEPTANCE
    PREP.PRODUCT_ID = PRODUCT_ID
    PREP.EXPECTED = EXPECTED
    PREP.configure_paths()


def configure_candidate() -> None:
    """Install only the configuration that emitted the frozen r7 pair."""
    R7.configure()
    R7.CARD.BASE.configure_full_candidate()
    R7.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    R7.PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    R7.CARD.CLIENT.INIT._configure_plane_module()
    R7.CARD.CLIENT.CURRENT_PLANE.bind_current_plane(STATIC)
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    truth = ElfTruth.read(WPLTO / "lisp65-c2-substitution-linked.prg.elf",
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(PRODUCT.VERIFIER_BINDING_SECTION)
    PRODUCT.VERIFIER_BINDING_BASE = section.address
    PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "r7 verifier-binding size drift")


def closure_adapter() -> dict[str, Any]:
    receipt = load(CARD_RECEIPT)
    scope = load(SCOPE)
    acceptance = load(ACCEPTANCE)
    pair = accepted_pair()
    require(receipt["status"] == R7.STATUS
            and receipt["artifacts_before"] == receipt["artifacts_after"]
            and {name: receipt["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == pair
            and scope["status"] == acceptance["status"] == "PASS"
            and receipt["attempt_accounting"] == {
                "WPLTO_runs_total": 1, "product_links_total": 1,
                "resume_WPLTO_runs": 0, "resume_product_links": 0,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0},
            "r7 closure is not media-ready")
    return {"format": "lisp65-v190-blocks-ab-r7-media-adapter-v1",
            "status": "PASS: R7 FROZEN PAIR MEDIA AUTHORIZED",
            "frozen_pair_before": pair, "frozen_pair_after": pair,
            "card": bind(CARD_RECEIPT), "scope": bind(SCOPE),
            "acceptance": bind(ACCEPTANCE), "review_authority": authority(),
            "completion_input_projection": prepare_static_inputs(),
            "rule": "artifact-only completion; zero WPLTO and zero product links"}


def complete_artifacts() -> dict[str, Any]:
    """Run canonical Completion read-only over the already qualified r7 pair."""
    configure_paths()
    pair = accepted_pair()
    configure_candidate()
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    freight = acceptance["additive_card_freight"]
    require(projection["dependent_fixed_vmas"] == 101
            and projection["dependent_free_derived_vmas"] == 2
            and freight["candidate_sections"] == 107
            and [row["name"] for row in freight["freight_rows"]] == [
                ".lisp65_c2_kernal_window.input_capture_helper",
                ".lisp65_c2_kernal_window.input_capture_main",
                ".lisp65_c2_kernal_window.input_consumer",
                ".lisp65_c2_mapped_product_cold"],
            "r7 accepted projection drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            observed = bind(candidate)
            require((observed["bytes"], observed["sha256"]) ==
                    (pair["ELF"]["bytes"], pair["ELF"]["sha256"]),
                    "Completion received a different r7 ELF")
            return projection

    accepted = AcceptedProjection()
    SOURCE_MEDIA.FLOW.BASE.INV = accepted
    CRC_MEDIA.INV = accepted
    SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = CAN.REPLAY.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        elf = Path(str(target) + ".elf")
        report = out / "packed-prg-facade-predecessor-rebind.json"
        if not report.exists():
            ITEM_MEDIA.NESTED.materialize_candidate_publish_predecessors(
                out, target, elf)
        value = CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = (
            ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(target, elf))
        return value

    CAN.REPLAY.configure = lambda: None
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    PRODUCT.fixed_facade_gate = facade
    try:
        value = CAN.complete_artifacts()
    finally:
        CAN.REPLAY.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
    final_prg = CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_prg) + ".elf")
    final_elf_id = bind(final_elf)
    require((final_elf_id["bytes"], final_elf_id["sha256"]) ==
                (pair["ELF"]["bytes"], pair["ELF"]["sha256"])
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed the frozen r7 pair")
    facade = ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(final_prg, final_elf)
    require(facade["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf",
            "r7 packed PRG facade drift")
    value["packed_PRG_facade"] = facade
    value["completion_product"] = bind(final_prg)
    value["frozen_input_PRG_unchanged"] = accepted_pair()["PRG"]
    return value


def mapped_section_rows(truth: ElfTruth) -> list[tuple[int, bytes, str]]:
    rows = []
    for name in (".lisp65_c2_mapped_far_service",
                 ".lisp65_c2_mapped_product_cold"):
        raw = truth.section_bytes(name)
        start = truth.symbol("__" + name.removeprefix(".") + "_load_start").value
        rows.append((start, raw, name))
    require([(start, len(raw), name) for start, raw, name in rows] == [
        (0x2F8B2, 1488, ".lisp65_c2_mapped_far_service"),
        (0x2FE8D, 324, ".lisp65_c2_mapped_product_cold")],
        "r7 mapped media geometry drift")
    return rows


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    static = {"status": "passed-v1.9-blocks-ab-static-plane",
              "product_build_id": f"0x{PRODUCT_ID:08x}",
              "product_build_id_authority": bind(
                  STATIC / "product/substitution-artifacts.json"),
              "bank2_static_code_bytes": PLANE_BYTES}
    wplto = {"status": "passed-qualified-v1.9-r7-link",
             "product": accepted_pair()["PRG"]}
    value = CAN.manifest(static, wplto, completion)
    elf = CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == PLANE_BYTES, "r7 Bank-2 static prefix drift")
    sections = mapped_section_rows(truth)
    base = 0x20000
    cursor = base + len(prefix)
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    owners = [{"owner": "static-code-plane", "start": base,
               "end_exclusive": cursor, "bytes": len(prefix)}]
    for start, raw, name in sections:
        require(start >= cursor, f"mapped section overlaps predecessor: {name}")
        if start > cursor:
            owners.append({"owner": ("mapped-tenant-congruence-gap" if
                          cursor >= 0x2F8B2 else "static-to-mapped-free-hole"),
                          "start": cursor, "end_exclusive": start,
                          "bytes": start - cursor})
        offset = start - base
        materialized[offset:offset + len(raw)] = raw
        owners.append({"owner": name, "start": start,
                       "end_exclusive": start + len(raw), "bytes": len(raw)})
        cursor = start + len(raw)
    require(cursor == 0x2FFD1 and 0x30000 - cursor == 47,
            "r7 Bank-2 end reserve drift")
    owners.append({"owner": "mapped-tenant-bank-end-reserve",
                   "start": cursor, "end_exclusive": 0x30000, "bytes": 47})
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear()
    row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections],
        "composed_owners": owners,
        "largest_contiguous_hole": {"start": base + PLANE_BYTES,
            "end_exclusive": sections[0][0],
            "bytes": sections[0][0] - (base + PLANE_BYTES)},
        "membership_authority": "r7 final-ELF composed ownership"})
    CAN.MANIFEST.write_bytes(canonical(value))
    CAN.check()
    return value


def session_config(product: Path) -> dict[str, Any]:
    pattern = "0123456789"
    return {
        "format": "lisp65-c2-v190-blocks-ab-display-r7-acceptance-session-v1",
        "recorded_on": "2026-08-30",
        "status": "ready-owner-A+B-r7-contact",
        "claim_scope": {
            "accepts": ["v1.9-Block-A-lossless-capture-client",
                        "v1.9-Block-B-native-prompt-editor",
                        "v1.9-A+B-regression-freedom", "release-terminal-D5"],
            "excludes": ["Comfort", "Matcher/Blink", "Block-C", "Block-D",
                         "$22-closure", "release-publication"],
            "green_consequence": "Blocks A and B hardware-accepted",
        },
        "media": {"product": {**bind(product), "remote_name": PRODUCT_REMOTE}},
        "configuration": {
            "optional_libraries_loaded": [],
            "Comfort_present": False, "Matcher_Blink_present": False,
            "native_prompt_collector": "public read-line editor",
            "capture_lifecycle": "armed at read-line entry; disarmed at return",
            "forced_collection_basis": (
                "more than 192 accepted printable insertions while line length "
                "stays below 192 forces at least one collection independent of "
                "nursery phase"),
        },
        "choreography": {
            "fresh_BASIC_first": True,
            "all_media_uploaded_and_read_back_before_boot": True,
            "product_mounted_last": True,
            "optional_library_mounts": 0,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
            "final_stopped_state_captures": 1,
        },
        "rows": [
            {"id": "ABR7-1-composed-native-prompt-display",
             "group": "prompt and editable cursor share one owned row",
             "actions": ["cold boot the product medium",
                         "observe lisp65> and the active cursor before typing"],
             "expect": ["WORKBENCH banner and one live native lisp65> prompt",
                        "prompt and active cursor occupy the same row",
                        "no scattered positioning spaces and no second cursor"]},
            {"id": "ABR7-2-native-prompt-editor",
             "group": "native prompt editor and v1.8 issue pension",
             "actions": [
                 "at lisp65> type (list 1 3) without Return",
                 "move Left twice, insert 2 followed by a space, then Return",
                 "exercise Left/Right, C-b/C-f, C-a/C-e, Delete/C-d and boundary no-ops"],
             "expect": ["first result is (1 2 3)",
                        "all edits occur at the cursor and preserve order",
                        "*** reader: invalid token does not appear"]},
            {"id": "ABR7-3-lossless-forced-collection",
             "group": "normal and fast physical typing over forced collection",
             "actions": [
                 "start a fresh native input with (length \"",
                 f"type {pattern} twelve times (120 printable insertions)",
                 "press Delete/Backspace eighty times so forty digits remain",
                 f"rapidly type {pattern} twelve more times, then close with \" ) and Return",
                 "visually keep the ten-digit grouping ordered while typing"],
             "expect": ["result is exactly 160", "no character is swallowed",
                        "no reordering or progressive backlog",
                        "at least one collection occurred while Capture was armed"],
             "accepted_printable_insertions_minimum": 250,
             "maximum_simultaneous_line_bytes": 172,
             "forced_collection": True},
            {"id": "ABR7-4-boot-surface-without-libraries",
             "group": "boot surface without optional libraries",
             "actions": ["confirm this boot used only the product medium",
                         "do not mount or require any optional library"],
             "expect": ["native prompt remains live without library freight",
                        "no INIT.L65 error, red frame or library dependency"]},
            {"id": "ABR7-5-explicit-read-line-break-and-A0",
             "group": "explicit editor, ownership and recovery",
             "actions": [
                 "submit (read-line), type abde, move Left twice, insert c, Return",
                 "start another input and press physical RUN/STOP",
                 "submit (>= nil 32), then submit (list 1 3)"],
             "expect": ["explicit read-line returns abcde with the same framebuffer semantics",
                        "RUN/STOP returns to one live lisp65> without red frame",
                        "type error recovers practically immediately",
                        "follow-up result is (1 3)"]},
            {"id": "ABR7-6-INIT-performance-and-D5",
             "group": "INIT.L65 regression, performance smokes and D5",
             "actions": [
                 "confirm the absent INIT.L65 path was silent at this boot",
                 "define (defun v19-perf-probe (x) (+ x 1))",
                 "run the four bound time forms", "capture final D5 counters"],
             "performance_forms": [
                 {"form": "(time (car (cdr (list 1 2))))",
                  "max_frames": 2, "value": "2"},
                 {"form": "(time ((lambda (x) (progn (rplaca x 9) x)) (list 1 2)))",
                  "max_frames": 2, "value": "(9 2)"},
                 {"form": "(time (string-ref \"abc\" 1))",
                  "max_frames": 2, "value": "98"},
                 {"form": "(time (v19-perf-probe 41))",
                  "max_frames": 2, "value": "42"}],
             "expect": ["each time form stays at or below two frames",
                        "D5 free symbol slots >= 32",
                        "D5 free name bytes >= 384"]},
        ],
        "headroom_postcondition": {
            "minimum": {"free_symbol_slots": 32, "free_name_bytes": 384},
            "counter_addresses": "derive nsym and npool from the r7 ELF",
            "observation_point": "after all rows in this same fresh session"},
        "decision_table": {
            "all-six-groups-green": "Blocks A and B hardware-accepted",
            "daily-use-blocker": (
                "at most one repair round; otherwise descope the affected block"),
            "rare-or-cosmetic": "Known Issue and v1.9 register row",
            "claim-expansion": "forbidden during the device session"},
    }


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v1.9-blocks-ab-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 16198
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "r7 packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def finish(media: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    MEDIA.check()
    product = MEDIA.PRODUCT_D81
    product_id, mounted_c2d = PREP.PAIR.product_world(product)
    require(product_id == PRODUCT_ID, "product D81 carries the wrong world")
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(product.read_bytes())
    require(b"INIT.L65" not in visible and b"REPL-COMFORT" not in visible,
            "Block-A/B product medium contains excluded optional freight")
    session = session_config(product)
    write(SESSION, session)
    value = {
        "format": "lisp65-c2-v190-blocks-ab-acceptance-media-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(MEDIA.WORK_D81)},
        "readback": "passed-packed-visible-file-and-role-identity-closure",
        "mounted_product_world": {
            "product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "session": bind(SESSION), "claim_limit": session["claim_scope"],
        "optional_library_media": "not built; boot-surface group requires none",
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "device_contacts": 0},
    }
    write(RECEIPT, value)
    return value


def build() -> None:
    require(not BUILD.exists(), "Block-A/B media build is one-shot")
    require(not RECEIPT.exists() and not SESSION.exists(),
            "Block-A/B tracked outputs already exist")
    adapter = closure_adapter()
    configure_paths()
    (BUILD / "closure-adapter.json").parent.mkdir(parents=True, exist_ok=True)
    write(BUILD / "closure-adapter.json", adapter)
    completion = complete_artifacts()
    product_manifest(completion)
    configure_paths()
    media = MEDIA.build(stager_compile_defines=(PREP.LIVENESS.OPT_IN,))
    value = finish(media, completion)
    print("v1.9 Blocks A+B media: PASS artifact-only "
          f"product={value['media']['product']['sha256']} device=0")


def check(*, source_only: bool = False) -> None:
    value = load(RECEIPT)
    session = load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "artifact_completions": 1,
                "product_media_builds": 1, "work_media_builds": 1,
                "device_contacts": 0}
            and session["claim_scope"]["excludes"] == [
                "Comfort", "Matcher/Blink", "Block-C", "Block-D",
                "$22-closure", "release-publication"]
            and session["status"] == "ready-owner-A+B-r7-contact"
            and len(session["rows"]) == 6
            and session["rows"][2]["forced_collection"] is True
            and session["rows"][2]["accepted_printable_insertions_minimum"] > 192
            and "prompt and active cursor occupy the same row" in
                session["rows"][0]["expect"]
            and "*** reader: invalid token does not appear" in
                session["rows"][1]["expect"],
            "Block-A/B receipt/session semantics drift")
    require(bind(SESSION) == value["session"], "session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(),
                    value["completion"], value["media_closure"],
                    *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"prepared artifact identity drift: {row['path']}")
        configure_paths()
        MEDIA.check()
        require(value["composed_bank2"] == static_plane_gate(),
                "persisted composed Bank-2 proof drift")
    print("v1.9 Blocks A+B media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "source-check":
        check(source_only=True)
    else:
        raise MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
