#!/usr/bin/env python3
"""Pack artifact-only Block-3 r10 Same-World acceptance media."""

from __future__ import annotations

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

import c2_v160_clean_product_acceptance_media as MEDIA  # noqa: E402
import c2_v160_items12_device_preparation as PREP  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r10 as R10  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ENGINE = MEDIA.ENGINE
BASE = MEDIA.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
CARD_BUILD = R10.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = R10.setup_plane()
LIBRARY_SOURCE = R10.CARD.PLANE
INPUT_ROOT = ROOT / "build/c2.3/v1.7-block3-r10-media-inputs"
STATIC = INPUT_ROOT / "static-plane"
BUILD = ROOT / "build/c2.3/v1.7-block3-r10-acceptance-media"
ADAPTER = BUILD.parent / "v1.7-block3-r10-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.7-block3-r10-acceptance-media-receipt.json"
SESSION = ROOT / "config/c2-v17-block3-r10-acceptance-session.json"
CLOSURE = R10.RECEIPT
ACCEPTANCE = R10.ACCEPTANCE
AUTHORIZATION = "c9e957ca"
PRODUCT_REMOTE = "V17B3P.D81"
LIBRARY_REMOTE = "V17B3L.D81"
EXPECTED = {
    "PRG": (41566, "a7a06b5e2cdfff0078dd56d715525d698c249a101890a624ae141e275096a862"),
    "ELF": (647940, "a5c5af3784ca7202258457fbe0a843911108400374b552a92091876f422bbd60"),
}
STATUS = "PASS: V1.7 BLOCK3 R10 ACCEPTANCE MEDIA READY"


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
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("r10 page-congruent placement authority",
                  "only then run scope", "composed preflight and media build",
                  "hardware remains outside this authority"):
        require(token in text, f"r10 media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def prepare_static_inputs() -> dict[str, Any]:
    if not STATIC.exists():
        INPUT_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_STATIC, STATIC)
    (STATIC / "libs").mkdir(exist_ok=True)
    for name in ("ide.ext.bin", "idex.ext.bin", "m65d.ext.bin"):
        shutil.copyfile(LIBRARY_SOURCE / name, STATIC / "libs" / name)
    rows = []
    for name in ("ide.ext.bin", "idex.ext.bin", "m65d.ext.bin"):
        source, projected = LIBRARY_SOURCE / name, STATIC / "libs" / name
        require(bind(source)["sha256"] == bind(projected)["sha256"],
                f"media library projection differs: {name}")
        rows.append({"name": name, "source": bind(source),
                     "projected": bind(projected)})
    require(bind(SOURCE_STATIC / "v6-semantics/bank2-static-code.bin")["sha256"]
            == bind(STATIC / "v6-semantics/bank2-static-code.bin")["sha256"],
            "media static-plane projection differs")
    return {"status": "PASS: COMPLETION PATH PROJECTION PRESERVES BYTES",
            "source_root": SOURCE_STATIC.relative_to(ROOT).as_posix(),
            "library_source_root": LIBRARY_SOURCE.relative_to(ROOT).as_posix(),
            "completion_root": STATIC.relative_to(ROOT).as_posix(),
            "libraries": rows}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    projection = prepare_static_inputs()
    require(closure["status"] == R10.STATUS
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["scope_status"] == closure["acceptance_status"] == "PASS"
            and closure["composed_bank2"]["largest_contiguous_hole"]["bytes"]
                == 11436
            and closure["tuple_LOADADDR"]["shared_offset"] == 0x28000
            and closure["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1,
                "qualification_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "r10 closure is not media-ready")
    value = {"format": "lisp65-v17-block3-r10-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": closure["frozen_pair_before"],
        "frozen_pair_after": closure["frozen_pair_after"],
        "r10_closure": bind(CLOSURE), "review_authority": authority(),
        "composed_bank2": closure["composed_bank2"],
        "tuple_LOADADDR": closure["tuple_LOADADDR"],
        "completion_input_projection": projection,
        "rule": "same-world adapter; no product claim is re-derived"}
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct paths/config only; never compile or link."""
    R10.install()
    R10.CARD.BASE.configure_full_candidate()
    R10.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    R10.CARD.bind_current_plane(STATIC)
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    truth = ElfTruth.read(R10.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def mapped_section_rows(truth: ElfTruth) -> list[tuple[int, bytes, str]]:
    names = (".lisp65_c2_mapped_far_service",
             ".lisp65_c2_mapped_product_cold")
    rows = []
    for name in names:
        raw = truth.section_bytes(name)
        start = truth.symbol("__" + name.removeprefix(".") + "_load_start").value
        rows.append((start, raw, name))
    require([(start, len(raw), name) for start, raw, name in rows] == [
        (0x2F8B2, 1488, ".lisp65_c2_mapped_far_service"),
        (0x2FE8D, 324, ".lisp65_c2_mapped_product_cold")],
        "r10 mapped media geometry drift")
    return rows


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    product_identity = load(STATIC / "product/substitution-artifacts.json")
    product_build_id = product_identity["product_build_id_hex"]
    require(product_build_id == "0x248cdf49",
            "r10 candidate product identity drift")
    static = {"status": "passed-v1.7-block3-r10-static-plane",
              "product_build_id": product_build_id,
              "product_build_id_authority": bind(
                  STATIC / "product/substitution-artifacts.json"),
              "bank2_static_code_bytes": 52230}
    wplto = {"status": "passed-qualified-r10-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = BASE.CAN.manifest(static, wplto, completion)
    elf = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 52230, "r10 Bank-2 static prefix drift")
    sections = mapped_section_rows(truth)
    base = 0x20000
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    cursor = base + len(prefix)
    owners = []
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
            "r10 media end reserve drift")
    owners.append({"owner": "mapped-tenant-bank-end-reserve",
                   "start": cursor, "end_exclusive": 0x30000,
                   "bytes": 47})
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear(); row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections],
        "composed_owners": owners,
        "membership_authority": "r10 final-ELF composed ownership"})
    BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.CAN.check()
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ENGINE.BASE.RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v17-block3-r10-acceptance-session-v1"
    value["recorded_on"] = "2026-08-26"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts": ["v1.7-block3-matcher", "v1.7-block3-cursor-blink"],
        "excludes": ["release-publication", "other-v1.7-blocks"],
    }
    value["rows"] = [
        {"id": "B3-1-line-editor-matcher", "actions": [
            "type and navigate across matching parens and quotes",
            "verify old highlight disappears after cursor movement",
            "verify delimiters inside strings/comments do not match",
            "verify over-close remains unmarked"],
         "expect": "one correct current match, no stale or false match"},
        {"id": "B3-2-IDE-matcher", "actions": [
            "repeat matcher cases in IDE", "scroll a long line"],
         "expect": "same semantics and no freeze"},
        {"id": "B3-3-blink", "actions": [
            "observe idle cursor in line editor and IDE",
            "type while cursor is in blink-off phase",
            "place cursor on a matched delimiter"],
         "expect": ("cursor blinks, typing makes it immediately visible, "
                    "blink never erases match attribute")},
        {"id": "B3-4-responsiveness-D5", "actions": [
            "type normally and rapidly on both surfaces",
            "run final loaded-configuration D5 probe"],
         "expect": ("no perceptible typing regression; D5 remains at or above "
                    "32 slots and 384 name bytes")},
    ]
    value["decision_table"] = {
        "all-four-groups-green": "Block 3 hardware accepted",
        "daily-use-blocker": "at most one fix round, else feature descope",
        "rare-or-cosmetic": "Known Issue and v1.7 register row"}
    return value


def block3_cursor_suite() -> Path:
    generated = INPUT_ROOT / "library-suite"
    generated.mkdir(parents=True, exist_ok=True)
    base_suite = PREP.STD._read_suite(str(PREP.CURSOR_SUITE))
    omitted = [row["name"] for row in base_suite["allow_omitted_defuns"]]
    require("%frame-low" in omitted and "%rl-poll" in omitted
            and "%sexp-paint" in omitted,
            "Block-3 resident successor population drift")
    resident = generated / "block3-resident.json"
    resident.write_bytes(canonical({
        "extends": str((ROOT /
            "config/c2-v160-comfort-repl-device-resident.json").resolve()),
        "functions": omitted,
        "require_all_defuns": False,
        "description": ("Block-3 final static plane supplies the matcher, "
                        "idle scheduler and shared frame reader."),
    }))
    suite = generated / "v17core.json"
    suite.write_bytes(canonical({
        "extends": str(PREP.CURSOR_SUITE.resolve()),
        "resident_suite": str(resident.resolve()),
        "description": "v1.7 Block-3 hardware-acceptance line-editor delta",
    }))
    return suite


def library_media() -> dict[str, Any]:
    """Build only the native line-editor delta; Comfort remains descoped."""
    product_id, _c2d = PREP.PAIR.product_world(PREP.MEDIA.PRODUCT_D81)
    PREP.PRODUCT_ID = product_id
    generated = PREP.BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    suite = block3_cursor_suite()
    prefix = generated / "v17core"
    manifest = PREP.compile_library(suite, prefix)
    spec = ("v16core", "v16core", "v16core", manifest, ())
    PREP.LIBRARY.mkdir(parents=True)
    row, artifact = PREP.LIBMEDIA.measured(spec, (1, 1), product_id)
    artifact_path = PREP.LIBRARY / "v16core.l65s"
    artifact_path.write_bytes(artifact)
    seed_index = PREP.LIBRARY / "l65index.seed"
    seed_index.write_bytes(PREP.LIBMEDIA.L65I.encode_index([row]))
    seed = PREP.LIBRARY / "library.seed.d81"
    PREP.LIBMEDIA.build_library_d81(
        seed, seed_index, [(artifact_path, "v16core")])
    locators = PREP.LIBMEDIA.L65I.d81_locators(seed)
    row, located = PREP.LIBMEDIA.measured(
        spec, locators["v16core"], product_id)
    require(located == artifact, "Block-3 v16core changed with final locator")
    index = PREP.LIBMEDIA.L65I.encode_index([row])
    index_path = PREP.LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = PREP.LIBMEDIA.L65I.decode_index(
        index, {"v16core": artifact}, artifact_build_id=product_id)
    require(len(decoded) == 1 and decoded[0]["name"] == "v16core",
            "Block-3 library contains an undeclared second row")
    contract = PREP.LIBMEDIA.resolver_contract(decoded, "v16core")
    rejected = {}
    for label, actual in (("omitted-only-row", []),
                          ("duplicated-only-row", [0, 0])):
        try:
            PREP.LIBMEDIA.resolver_contract(
                deepcopy(decoded), "v16core", actual_override=actual)
        except PREP.LIBMEDIA.MediaClosureError as error:
            rejected[label] = str(error)
        else:
            raise RuntimeError(f"Block-3 resolver mutation survived: {label}")
    final = PREP.LIBRARY / "lisp65-library.d81"
    PREP.LIBMEDIA.build_library_d81(
        final, index_path, [(artifact_path, "v16core")])
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index, b"V16CORE": artifact},
            "Block-3 library visible-file closure drift")
    seed.unlink(); seed_index.unlink()
    return {"variant": "v1.7-block3", "comfort_absent": True,
        "product_build_id": f"0x{product_id:08x}",
        "D81": bind(final), "index": bind(index_path),
        "artifacts": {"v16core": bind(artifact_path)},
        "index_rows": decoded, "resolver_contracts": {"v16core": contract},
        "resolver_mutations_rejected": rejected,
        "visible_files": sorted(name.decode() for name in visible),
        "suite": bind(suite)}


def finish_media(media: dict[str, Any]) -> dict[str, Any]:
    """Bind the one-row Block-3 library to the derived media world."""
    PREP.configure_paths()
    PREP.MEDIA.check()
    product_d81 = PREP.MEDIA.PRODUCT_D81
    library_d81 = PREP.LIBRARY / "lisp65-library.d81"
    pair = PREP.PAIR.pair_identity(product_d81, library_d81)
    product_id = int(pair["product_build_id"], 16)
    PREP.PRODUCT_ID = product_id
    require(pair["index_rows"] == 1
            and pair["row_names"] == ["v16core"],
            "Block-3 product/library pair identity drift")
    config = session_config(product_d81, library_d81)
    PREP.SESSION.write_bytes(canonical(config))
    value = {
        "format": "lisp65-c2-v17-block3-r10-base-media-receipt-v1",
        "recorded_on": "2026-08-26",
        # The historical artifact-only wrappers promote this receipt in place.
        "status": "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY",
        "accepted_pair": {
            "PRG": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg.elf")},
        "completion": bind(PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product_d81),
            "work": bind(PREP.MEDIA.WORK_D81),
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
            "suite": bind(block3_cursor_suite())},
        "session": bind(PREP.SESSION),
        "claim_limit": config["claim_scope"],
        "execution_accounting": {"successful_run": {
            "WPLTO_runs": 0, "product_links": 0,
            "artifact_completions": 1, "media_builds": 2,
            "device_contacts": 0}}}
    PREP.RECEIPT.write_bytes(canonical(value))
    print("v1.7 Block3 base media: PASS media=2 rows=1 pair=same-world")
    return value


def check_base_media() -> dict[str, Any]:
    value = load(PREP.RECEIPT)
    require(value["status"] in (
                "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY", STATUS)
            and value["same_world_pair"]["index_rows"] == 1
            and value["same_world_pair"]["row_names"] == ["v16core"]
            and value["library_closure"]["Comfort_absent"] is True,
            "Block-3 base media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"Block-3 prepared artifact identity drift: {row['path']}")
    pair = PREP.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"],
            "Block-3 persisted pair identity drift")
    return value


def static_plane_gate() -> dict[str, Any]:
    path = BUILD / "canonical-product/canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v1.7-block3-r10-static-plane"
            and plane["product_build_id"] == "0x248cdf49"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["mapped_sections"] == [
                ".lisp65_c2_mapped_far_service",
                ".lisp65_c2_mapped_product_cold"]
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "r10 packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def configure_successor() -> None:
    prepare_static_inputs()
    MEDIA.CARD_BUILD = CARD_BUILD; MEDIA.WPLTO = WPLTO; MEDIA.STATIC = STATIC
    MEDIA.BUILD = BUILD; MEDIA.ADAPTER = ADAPTER; MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION; MEDIA.CLOSURE = CLOSURE
    MEDIA.ACCEPTANCE = ACCEPTANCE; MEDIA.AUTHORIZATION = AUTHORIZATION
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE; MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED; MEDIA.STATUS = STATUS
    MEDIA.authority = authority; MEDIA.closure_adapter = closure_adapter
    MEDIA.session_config = session_config; MEDIA.configure_candidate = configure_candidate
    MEDIA.product_manifest = product_manifest; MEDIA.static_plane_gate = static_plane_gate
    MEDIA.configure_successor()
    PREP.library_media = library_media
    PREP.finish = finish_media
    PREP.check = check_base_media


def build() -> None:
    configure_successor()
    MEDIA.build()


def check() -> None:
    configure_successor()
    MEDIA.check()
    value = load(RECEIPT)
    product = ROOT / value["media"]["product"]["path"]
    library = ROOT / value["media"]["library"]["path"]
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "replacement_media_builds": 2,
                "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"]["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf"
            and value["same_world_pair"]["result"] == "same-world-pair"
            and value["clean_static_plane"]["static_plane"]
                ["product_build_id"] == value["same_world_pair"]
                ["product_build_id"]
            and value["clean_static_plane"] == static_plane_gate()
            and bind(product) == value["media"]["product"]
            and bind(library) == value["media"]["library"],
            "r10 packed-media proof drift")
    print("v1.7 Block3 r10 media: CHECK PASS device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    else:
        raise RuntimeError("usage: build|check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
