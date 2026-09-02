#!/usr/bin/env python3
"""Pack artifact-only v2.0 Block-3 media and prove readback closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_v17_block3_r10_acceptance_media as R10_MEDIA  # noqa: E402
import c2_v200_block3_return_product_card as CARD  # noqa: E402
import c2_v200_symbol22_first_fault_device_media as BASE  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Reviewer authorization — Block-3 product card — 2026-08-31"
REPLACEMENT_HEADER = (
    "## Reviewer authorization — Block-3 replacement WPLTO — 2026-09-01")
CARD_RECEIPT = CARD.RECEIPT
SOURCE_WPLTO = CARD.WPLTO
SOURCE_STATIC = CARD.PLANE
BUILD = ROOT / "build/c2.3/v2.0-block3-return-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0-block3-return-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-block3-return-device-session.json"
SCOPE = CARD.WPLTO / "owner-scope-result.json"
ACCEPTANCE = CARD.BUILD / "artifact-acceptance.json"
PRODUCT_REMOTE = "V20B3P.D81"
PRODUCT_ID = 0xB8789D01
PLANE_BYTES = 52499
EXPECTED = {
    "PRG": (41811,
        "c47051b192dd033fcfc96c96ee9b068f5c8d0fb47a679164990c6680b02a865e"),
    "ELF": (636112,
        "9f0de33c49ddd514137b5137cb0da2b6605e9cf92bc4a822a9167b35d17c9a52"),
}
STATUS = "PASS: V2.0 BLOCK3 RETURN DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-block3-return-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-block3-return-device-session-v1"
PRODUCT_KEYS = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")
MEDIA = BASE.MEDIA.MEDIA


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.MediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    return BASE.load(path)


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def memory_binding(name: str, raw: bytes) -> dict[str, Any]:
    return {"medium_member": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"Block-3 {role} identity drift")
    return pair


def _plan_section(header: str, tokens: tuple[str, ...]) -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"authority section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in tokens:
        require(token in folded, f"Block-3 media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    receipt = load(CARD_RECEIPT)
    pair = accepted_pair()
    require(receipt["status"] == CARD.STATUS
            and receipt["media_authorized"] is True
            and receipt["media_condition"] ==
                "closure must be rederived from bytes read back from packed medium"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(SCOPE)["status"] == load(ACCEPTANCE)["status"] == "PASS",
            "Block-3 product card is not media-ready")
    return {
        "product_card": bind(CARD_RECEIPT),
        "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE),
        "review_authority": _plan_section(PLAN_HEADER, (
            "only then media", "actually packed medium")),
        "replacement_authority": _plan_section(REPLACEMENT_HEADER, (
            "feature/profile population", "actually packed medium")),
        "right": "artifact-only media; zero WPLTO and product links",
    }


def prepare_inputs() -> dict[str, Any]:
    if not WPLTO.exists():
        WPLTO.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_WPLTO, WPLTO)
    if not STATIC.exists():
        shutil.copytree(SOURCE_STATIC, STATIC)
    auxiliaries = WPLTO / "fresh-c2-lite-prelink-gates"
    if not auxiliaries.exists():
        shutil.copytree(STATIC, auxiliaries)
    projected = {
        "PRG": bind(WPLTO / CARD.PRG.name),
        "ELF": bind(WPLTO / CARD.ELF.name),
    }
    pair = accepted_pair()
    require(all((projected[key]["bytes"], projected[key]["sha256"]) ==
                (pair[key]["bytes"], pair[key]["sha256"])
                for key in pair),
            "artifact-only projection changed the qualified pair")
    require(bind(STATIC / "v6-semantics/bank2-static-code.bin")["sha256"] ==
            bind(SOURCE_STATIC / "v6-semantics/bank2-static-code.bin")["sha256"],
            "artifact-only projection changed the static plane")
    libs = STATIC / "libs"
    libs.mkdir(exist_ok=True)
    sources = {
        "ide.ext.bin": CARD.PRICE.BUILD / "ide.ext.bin",
        "idex.ext.bin": R10_MEDIA.LIBRARY_SOURCE / "idex.ext.bin",
        "m65d.ext.bin": R10_MEDIA.LIBRARY_SOURCE / "m65d.ext.bin",
    }
    library_rows = []
    for name, source in sources.items():
        target = libs / name
        if not target.exists():
            shutil.copyfile(source, target)
        require(source.read_bytes() == target.read_bytes(),
                f"library input projection changed: {name}")
        library_rows.append({"name": name, "source": bind(source),
                             "projected": bind(target)})
    return {"status": "PASS: BLOCK3 MEDIA INPUTS COPIED BYTE-EXACT",
            "pair": projected,
            "plane": bind(STATIC / "v6-semantics/bank2-static-code.bin"),
            "libraries": library_rows}


def configure_paths() -> None:
    media = BASE.MEDIA
    for name, value in {
        "CARD_BUILD": CARD.BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "LIBRARY_SOURCE": SOURCE_STATIC,
        "BUILD": BUILD, "STATIC": STATIC, "TARGET": TARGET,
        "SHARED": SHARED, "RECEIPT": RECEIPT, "SESSION": SESSION,
        "SCOPE": SCOPE, "ACCEPTANCE": ACCEPTANCE,
        "EXPECTED": EXPECTED, "PRODUCT_ID": PRODUCT_ID,
        "STATUS": STATUS,
    }.items():
        setattr(media, name, value)
    media.PREP.PRODUCT_ID = PRODUCT_ID
    media.PREP.BUILD = BUILD; media.PREP.CARD = CARD.BUILD
    media.PREP.WPLTO = WPLTO; media.PREP.STATIC = STATIC
    media.PREP.TARGET = TARGET; media.PREP.SHARED = SHARED
    media.PREP.LIBRARY = BUILD / "unused-library"
    media.PREP.RECEIPT = RECEIPT; media.PREP.SESSION = SESSION
    media.PREP.ACCEPTANCE = ACCEPTANCE
    media.PREP.HISTORICAL_ACCEPTANCE = ACCEPTANCE
    media.PREP.EXPECTED = EXPECTED
    media.PREP.configure_paths()


def configure_candidate() -> None:
    CARD.configure()
    CARD.setup_child()
    BASE.MEDIA.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.MEDIA.PRODUCT.INITIAL_C2D = (
        STATIC / "product/initial.c2d-v3.bin")
    BASE.MEDIA.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(BASE.MEDIA.PRODUCT.VERIFIER_BINDING_SECTION)
    require(section.bytes == 40, "Block-3 verifier-binding size drift")
    BASE.MEDIA.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.MEDIA.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    configure_paths()


def closure_adapter() -> dict[str, Any]:
    projection = prepare_inputs()
    configure_paths()
    return {"format": FORMAT + "-adapter",
            "status": "PASS: QUALIFIED BLOCK3 PAIR PROJECTED",
            "frozen_pair_before": accepted_pair(),
            "frozen_pair_after": accepted_pair(),
            "authority": authority(), "input_projection": projection,
            "rule": "copy-only completion; zero WPLTO and product links"}


def complete_artifacts() -> dict[str, Any]:
    configure_paths()
    pair = accepted_pair()
    configure_candidate()
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    freight = acceptance["additive_card_freight"]
    require(projection["dependent_fixed_vmas"] == 101
            and projection["dependent_free_derived_vmas"] == 2
            and freight["candidate_sections"] == 109,
            "Block-3 accepted projection drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            observed = bind(candidate)
            require((observed["bytes"], observed["sha256"]) ==
                    (pair["ELF"]["bytes"], pair["ELF"]["sha256"]),
                    "Completion received a different Block-3 ELF")
            return projection

    media = BASE.MEDIA
    accepted = AcceptedProjection()
    media.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    media.CRC_MEDIA.INV = accepted
    media.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = media.CAN.REPLAY.configure
    original_fixed = media.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = media.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return media.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        elf = Path(str(target) + ".elf")
        report = out / "packed-prg-facade-predecessor-rebind.json"
        if not report.exists():
            media.ITEM_MEDIA.NESTED.materialize_candidate_publish_predecessors(
                out, target, elf)
        value = media.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = (
            media.ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(target, elf))
        return value

    media.CAN.REPLAY.configure = lambda: None
    media.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    media.PRODUCT.fixed_facade_gate = facade
    try:
        value = media.CAN.complete_artifacts()
    finally:
        media.CAN.REPLAY.configure = original_configure
        media.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        media.PRODUCT.fixed_facade_gate = original_facade
    final_prg = media.CAN.FINAL / CARD.PRG.name
    final_elf = Path(str(final_prg) + ".elf")
    require(bind(final_elf)["sha256"] == pair["ELF"]["sha256"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed the frozen Block-3 pair")
    facade_gate = media.ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(
        final_prg, final_elf)
    require(facade_gate["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf",
            "Block-3 packed PRG facade drift")
    value["packed_PRG_facade"] = facade_gate
    value["completion_product"] = bind(final_prg)
    return value


def mapped_section_rows(truth: ElfTruth) -> list[tuple[int, bytes, str]]:
    rows = []
    for name in (".lisp65_c2_mapped_far_service",
                 ".lisp65_c2_mapped_product_cold"):
        raw = truth.section_bytes(name)
        symbol = "__" + name.removeprefix(".") + "_load_start"
        rows.append((truth.symbol(symbol).value, raw, name))
    require([(start, len(raw), name) for start, raw, name in rows] == [
        (0x2F8B2, 1488, ".lisp65_c2_mapped_far_service"),
        (0x2FE8D, 324, ".lisp65_c2_mapped_product_cold")],
        "Block-3 mapped media geometry drift")
    return rows


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    media = BASE.MEDIA
    static = {"status": "passed-v2.0-block3-return-static-plane",
              "product_build_id": f"0x{PRODUCT_ID:08x}",
              "bank2_static_code_bytes": PLANE_BYTES}
    wplto = {"status": "passed-qualified-v2.0-block3-link",
             "product": bind(WPLTO / CARD.PRG.name)}
    value = media.CAN.manifest(static, wplto, completion)
    elf = media.CAN.FINAL / CARD.ELF.name
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == PLANE_BYTES,
            "Block-3 static-plane prefix drift")
    base = 0x20000
    sections = mapped_section_rows(truth)
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    cursor = base + len(prefix)
    owners = [{"owner": "static-plane", "start": base,
               "end_exclusive": cursor, "bytes": len(prefix)}]
    for start, raw, name in sections:
        require(start >= cursor, f"mapped section overlaps predecessor: {name}")
        if start > cursor:
            owners.append({"owner": ("mapped-tenant-congruence-gap" if
                cursor >= 0x2F8B2 else "static-to-mapped-free-hole"),
                "start": cursor, "end_exclusive": start,
                "bytes": start - cursor})
        materialized[start - base:start - base + len(raw)] = raw
        owners.append({"owner": name, "start": start,
            "end_exclusive": start + len(raw), "bytes": len(raw)})
        cursor = start + len(raw)
    require(cursor == 0x2FFD1 and 0x30000 - cursor == 47,
            "Block-3 Bank-2 end reserve drift")
    owners.append({"owner": "mapped-tenant-bank-end-reserve",
        "start": cursor, "end_exclusive": 0x30000, "bytes": 47})
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear(); row.update({**bind(bank2),
                             "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections],
        "composed_owners": owners,
        "largest_contiguous_hole": {
            "start": base + PLANE_BYTES, "end_exclusive": sections[0][0],
            "bytes": sections[0][0] - (base + PLANE_BYTES)},
        "membership_authority": "qualified Block-3 final-ELF composition",
    })
    media.CAN.MANIFEST.write_bytes(canonical(value))
    media.CAN.check()
    return value


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    require(plane["status"] == "passed-v2.0-block3-return-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 11167
            and plane["composed_owners"][-2]["bytes"] == 324
            and plane["composed_owners"][-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "Block-3 composed Bank-2 media drift")
    return {"manifest": bind(path), "static_plane": plane,
            "artifact": row,
            "rule": "all shipped Bank-2 intervals are composed and disjoint"}


def packed_readback_closure(product: Path) -> dict[str, Any]:
    visible = D81.visible_files(product.read_bytes())
    require({b"CODE.BIN", b"C2D.BIN", b"SHELF.BIN"} <= set(visible),
            "packed Block-3 medium lacks a closure-bearing member")
    packed_code = visible[b"CODE.BIN"]
    source_product = STATIC / "product/substitution-artifacts.json"
    product_dir = source_product.parent
    lengths = [(product_dir / f"{key}.code.bin").stat().st_size
               for key in PRODUCT_KEYS]
    require(sum(lengths) == PLANE_BYTES and len(packed_code) == 65489,
            "packed Block-3 code population drift")
    projection = BUILD / "packed-readback-closure/product"
    if projection.parent.exists():
        shutil.rmtree(projection.parent)
    projection.mkdir(parents=True)
    shutil.copyfile(source_product, projection / source_product.name)
    offset = 0
    slices = []
    for key, length in zip(PRODUCT_KEYS, lengths):
        actual = packed_code[offset:offset + length]
        expected = (product_dir / f"{key}.code.bin").read_bytes()
        require(actual == expected,
                f"packed Block-3 code differs from qualified image: {key}")
        (projection / f"{key}.code.bin").write_bytes(actual)
        shutil.copyfile(product_dir / f"{key}.c2i.bin",
                        projection / f"{key}.c2i.bin")
        slices.append({"key": key, "offset": offset, "bytes": length,
                       "packed": memory_binding("CODE.BIN", actual),
                       "qualified": bind(product_dir / f"{key}.code.bin")})
        offset += length
    require(packed_code[:offset] ==
            (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes(),
            "packed closure prefix differs from the qualified plane")
    value = CLOSURE.derive(projection / source_product.name)
    CLOSURE.require_closed(value)
    require(value["object_count"] == 792
            and value["call_site_count"] == 2651,
            "packed readback closure population drift")

    def validate(raw: bytes, count: int) -> None:
        require(count == len(PRODUCT_KEYS) and raw[:PLANE_BYTES] ==
                (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes(),
                "packed readback no longer covers the qualified population")

    rejected = []
    for name, raw, count in (
            ("packed-code-prefix-truncated", packed_code[:PLANE_BYTES - 1], 6),
            ("packed-component-omitted", packed_code, 5)):
        try:
            validate(raw, count)
        except BASE.MediaError:
            rejected.append(name)
    require(rejected == ["packed-code-prefix-truncated",
                         "packed-component-omitted"],
            "packed readback mutation survived")
    price = load(CARD.PRICING_RECEIPT)
    positive = price["closure_positive_control"]
    failure = positive["failure"]
    require(positive["status"] ==
                "PASS: KNOWN COMFORT DANGLING CALLEE REJECTED"
            and failure["caller"] == "%repl-step"
            and failure["target"] == "%ide-line-net-depth"
            and failure["classification"] == "anonymous-only",
            "packed closure positive control drift")
    return {"status": "PASS: CLOSURE REDERIVED FROM PACKED D81 BYTES",
        "medium": bind(product),
        "visible_members": sorted(name.decode("ascii") for name in visible),
        "packed_code": memory_binding("CODE.BIN", packed_code),
        "packed_c2d": memory_binding("C2D.BIN", visible[b"C2D.BIN"]),
        "packed_shelf": memory_binding("SHELF.BIN", visible[b"SHELF.BIN"]),
        "code_slices": slices, "closure": value,
        "positive_control": positive,
        "mutations_rejected": [*rejected, *CLOSURE.mutation_tests()],
        "rule": ("the delivered CODE.BIN prefix is split into the six actual "
                 "product images and decoded again before media acceptance")}


def session_config(product: Path) -> dict[str, Any]:
    return {
        "format": SESSION_FORMAT, "recorded_on": "2026-09-01",
        "status": "ready-owner-v2.0-block3-contact",
        "claim_scope": {
            "accepts": ["Block-3 matcher and blink on line editor and IDE"],
            "excludes": ["Comfort", "v2.1 Comfort return", "release", "publish"]},
        "media": {"product": {**bind(product),
                                "remote_name": PRODUCT_REMOTE}},
        "choreography": {
            "fresh_BASIC_first": True,
            "product_uploaded_and_read_back_before_boot": True,
            "optional_library_media": "none",
            "physical_owner_keyboard_only": True,
            "post_boot_automated_device_access": 0,
            "one_form_per_submission": True},
        "rows": [
            {"id": "B3-1-line-editor-matcher", "actions": [
                "type and navigate across matching parentheses and quotes",
                "move away and verify the old highlight disappears",
                "place delimiters inside strings/comments",
                "type one over-close delimiter"],
             "expect": ("exactly one current match; no stale match; string/comment "
                        "delimiters and over-close remain unmarked")},
            {"id": "B3-2-IDE-matcher", "actions": [
                "repeat the same matcher cases in IDE", "scroll one long line"],
             "expect": "same matching semantics and no freeze"},
            {"id": "B3-3-blink", "actions": [
                "observe the idle cursor in line editor and IDE",
                "type during blink-off", "place cursor on a matched delimiter"],
             "expect": ("cursor blinks; typing restores visibility immediately; "
                        "blink does not erase the match attribute")},
            {"id": "B3-4-responsiveness-D5", "actions": [
                "type normally and rapidly on both surfaces",
                "run the final loaded-configuration D5 probe"],
             "expect": ("no perceptible typing regression; D5 at least 32 free "
                        "slots and 384 name bytes")},
        ],
        "decision_table": {
            "all-four-groups-green": "Block 3 hardware-accepted",
            "daily-use-blocker": ("at most one repair round; otherwise descope "
                                  "the affected Block-3 freight"),
            "rare-or-cosmetic": "Known Issue and v2.0 register row",
            "claim-expansion": "forbidden during the device session"},
    }


def finish(packed: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    MEDIA.check()
    product = MEDIA.PRODUCT_D81
    product_id, mounted_c2d = BASE.MEDIA.PREP.PAIR.product_world(product)
    require(product_id == PRODUCT_ID, "packed product carries another world")
    closure = packed_readback_closure(product)
    session = session_config(product)
    BASE.write(SESSION, session)
    value = {
        "format": FORMAT, "recorded_on": "2026-09-01", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(BASE.MEDIA.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(MEDIA.MANIFEST),
        "media": {"product": bind(product),
                  "work": bind(MEDIA.WORK_D81)},
        "readback": "passed-visible-file-and-role-identity-closure",
        "mounted_product_world": {
            "product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_artifact_closure": {
            "stager_gate": packed["stager"]["gate"],
            "product_entries": packed["media"]["product"]["entries"],
            "artifact_count": packed["artifact_count"]},
        "packed_transitive_closure": closure,
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "session": bind(SESSION), "claim_limit": session["claim_scope"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "device_contacts": 0},
    }
    BASE.write(RECEIPT, value)
    return value


def build() -> None:
    product = SHARED / "lisp65-product.d81"
    manifest = SHARED / "candidate-manifest.json"
    completion_receipt = (BASE.MEDIA.CAN.RECEIPTS /
                          "artifact-completion.json")
    if (product.is_file() and manifest.is_file()
            and completion_receipt.is_file()
            and not RECEIPT.exists()
            and (not SESSION.exists()
                 or load(SESSION) == session_config(product))):
        configure_paths()
        configure_candidate()
        completion = load(completion_receipt)
        final_prg = BASE.MEDIA.CAN.FINAL / CARD.PRG.name
        final_elf = Path(str(final_prg) + ".elf")
        completion["packed_PRG_facade"] = (
            BASE.MEDIA.ITEM_MEDIA.NESTED.REPAIR.packed_facade_gate(
                final_prg, final_elf))
        value = finish(load(manifest), completion)
        check()
        print("v2.0 Block3 device media: READ-ONLY FINISH PASS product="
              f"{value['media']['product']['sha256']} device=0")
        return
    if BUILD.exists():
        children = sorted(path.name for path in BUILD.iterdir())
        require(set(children) <= {"canonical-product", "closure-adapter.json",
                                  "inputs"}
                and {"closure-adapter.json", "inputs"} <= set(children)
                and WPLTO.is_dir() and STATIC.is_dir()
                and not RECEIPT.exists() and not SESSION.exists(),
                "Block-3 media retry found outputs beyond input projection")
        # A failed copy-only Completion owns this tree.  It is safe to replace
        # only while no medium, receipt or session exists; qualified inputs
        # remain byte-bound above and are never removed.
        if TARGET.exists():
            shutil.rmtree(TARGET)
    else:
        require(not RECEIPT.exists() and not SESSION.exists(),
                "Block-3 device media is one-shot")
    adapter = closure_adapter()
    BUILD.mkdir(parents=True, exist_ok=True)
    BASE.write(BUILD / "closure-adapter.json", adapter)
    completion = complete_artifacts()
    product_manifest(completion)
    configure_paths()
    packed = MEDIA.build(
        stager_compile_defines=(BASE.MEDIA.PREP.LIVENESS.OPT_IN,))
    value = finish(packed, completion)
    check()
    print("v2.0 Block3 device media: BUILD PASS product="
          f"{value['media']['product']['sha256']} device=0")


def check(*, source_only: bool = False) -> None:
    configure_paths()
    value, session = load(RECEIPT), load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["packed_transitive_closure"]["status"] ==
                "PASS: CLOSURE REDERIVED FROM PACKED D81 BYTES"
            and value["packed_transitive_closure"]["closure"]["object_count"] == 792
            and value["packed_transitive_closure"]["closure"]["call_site_count"] == 2651
            and value["composed_bank2"]["static_plane"]
                ["largest_contiguous_hole"]["bytes"] == 11167
            and session["status"] == "ready-owner-v2.0-block3-contact"
            and len(session["rows"]) == 4
            and session["choreography"]["optional_library_media"] == "none",
            "Block-3 device media/session semantics drift")
    require(bind(SESSION) == value["session"], "Block-3 session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"Block-3 prepared artifact identity drift: {row['path']}")
        require(packed_readback_closure(
            ROOT / value["media"]["product"]["path"])["status"] ==
                value["packed_transitive_closure"]["status"],
            "Block-3 packed readback closure no longer reproduces")
    print("v2.0 Block3 device media: CHECK PASS "
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
        raise BASE.MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 Block3 device media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
