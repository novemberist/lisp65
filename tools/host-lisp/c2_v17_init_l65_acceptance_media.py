#!/usr/bin/env python3
"""Pack artifact-only native INIT.L65 acceptance media."""

from __future__ import annotations

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
import c2_v160_nested_map_swap_media as NESTED  # noqa: E402
import c2_v17_block3_r10_acceptance_media as BASE_MEDIA  # noqa: E402
import c2_v17_init_l65_card as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PREP = BASE_MEDIA.PREP
BASE = BASE_MEDIA.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-v17-init-l65-media-contract.json"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = CARD.PLANE_ROOT
LIBRARY_SOURCE = CARD.BASELINE_ROOT / "static-plane/narrow-static/libs"
INPUT_ROOT = ROOT / "build/c2.3/v1.7-init-l65-media-inputs"
STATIC = INPUT_ROOT / "static-plane"
BUILD = ROOT / "build/c2.3/v1.7-init-l65-acceptance-media"
ADAPTER = BUILD.parent / "v1.7-init-l65-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.7-init-l65-acceptance-media-receipt.json"
SESSION = ROOT / "config/c2-v17-init-l65-device-session.json"
CLOSURE = CARD.RECEIPT
RESUME = CARD.RESUME_RECEIPT
ACCEPTANCE = CARD.BUILD / "artifact-acceptance.json"
PRODUCT_REMOTE = "V17IP.D81"
MISSING_REMOTE = "V17IM.D81"
VALID_REMOTE = "V17IOK.D81"
ERROR_REMOTE = "V17IBAD.D81"
EXPECTED = {
    "PRG": (41566,
            "f2ea6e12333ff036067a21ec04c32b26cda66b004e16df2814e3b5fbaa1813b7"),
    "ELF": (647280,
            "4ae360b0ff583505d0c584c7c20a269526b8145f9406f1ef0752433099a021b9"),
}
STATUS = "PASS: V1.7 NATIVE INIT.L65 ACCEPTANCE MEDIA READY"
VALID_INIT = b"(defun init-proof () 17)\n"
ERROR_INIT = b"(car 1)\n"


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


def bind_bytes(raw: bytes) -> dict[str, Any]:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    contract = load(CONTRACT)
    closure = load(CLOSURE)
    resume = load(RESUME)
    require(contract["status"] ==
                "OPEN: REVIEW-AUTHORIZED ARTIFACT-ONLY MEDIA AND OWNER SESSION"
            and contract["scope"] == {"new_WPLTO_runs": 0,
                "new_product_links": 0, "new_product_cards": 0,
                "device_contacts_during_build": 0, "artifact_only": True}
            and closure["status"] == CARD.STATUS
            and resume["status"] ==
                "PASS: INIT.L65 R4 FINAL GATE RESUMED READ-ONLY"
            and resume["frozen_pair_before"] == resume["frozen_pair_after"],
            "native INIT media authority drift")
    return {"contract": bind(CONTRACT), "card": bind(CLOSURE),
            "read_only_resume": bind(RESUME)}


def prepare_static_inputs() -> dict[str, Any]:
    if not STATIC.exists():
        INPUT_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE_STATIC, STATIC)
    (STATIC / "libs").mkdir(exist_ok=True)
    rows = []
    for name in ("ide.ext.bin", "idex.ext.bin", "m65d.ext.bin"):
        source = LIBRARY_SOURCE / name
        projected = STATIC / "libs" / name
        if not projected.exists():
            shutil.copyfile(source, projected)
        require(bind(source)["sha256"] == bind(projected)["sha256"],
                f"INIT media library projection differs: {name}")
        rows.append({"name": name, "source": bind(source),
                     "projected": bind(projected)})
    source_code = SOURCE_STATIC / "v6-semantics/bank2-static-code.bin"
    projected_code = STATIC / "v6-semantics/bank2-static-code.bin"
    require(bind(source_code)["sha256"] == bind(projected_code)["sha256"],
            "INIT media static-plane projection differs")
    return {"status": "PASS: COMPLETION PATH PROJECTION PRESERVES BYTES",
            "source_root": SOURCE_STATIC.relative_to(ROOT).as_posix(),
            "completion_root": STATIC.relative_to(ROOT).as_posix(),
            "libraries": rows}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    resume = load(RESUME)
    scope = load(ROOT / closure["scope"]["path"])
    acceptance = load(ROOT / closure["acceptance"]["path"])
    pair = {name: closure["artifacts_after"][name] for name in ("ELF", "PRG")}
    require(closure["status"] == CARD.STATUS
            and closure["artifacts_before"] == closure["artifacts_after"]
            and resume["frozen_pair_before"] == resume["frozen_pair_after"] == pair
            and resume["execution"] == {"qualification_resumes": 1,
                "new_WPLTO_runs": 0, "new_product_links": 0,
                "new_cards_consumed": 0, "media_builds": 0,
                "device_contacts": 0}
            and scope["status"] == acceptance["status"] == "PASS",
            "native INIT closure is not media-ready")
    value = {
        "format": "lisp65-v17-init-l65-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair, "frozen_pair_after": pair,
        "card": bind(CLOSURE), "read_only_resume": bind(RESUME),
        "review_authority": authority(),
        "completion_input_projection": prepare_static_inputs(),
        "rule": "same-world adapter; no product claim is re-derived",
    }
    ADAPTER.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct configuration and paths only; never compile or link."""
    CARD.configure()
    CARD.BASE.configure_full_candidate()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "native INIT verifier-binding size drift")


def complete() -> dict[str, Any]:
    """Run Completion over the derived active-freight population."""
    NESTED.BASE.configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, NESTED.BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, NESTED.BASE.sha(elf)) == EXPECTED["ELF"],
            "accepted native INIT pair drift")
    configure_candidate()
    closure = load(ADAPTER)
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    freight = acceptance["additive_card_freight"]
    registered = freight["registered_sections"]
    require(closure["status"] ==
                "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["MAP_fix_closed"] is True
            and acceptance["status"] == "PASS"
            and freight["candidate_sections"] ==
                freight["golden_sections"] + len(registered),
            "native INIT closure or derived Acceptance freight drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, NESTED.BASE.sha(candidate)) ==
                        EXPECTED["ELF"],
                    "Completion received a different native INIT ELF")
            return projection

    accepted = AcceptedProjection()
    NESTED.BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    NESTED.BASE.CRC_MEDIA.INV = accepted
    NESTED.BASE.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = NESTED.BASE.CAN.REPLAY.configure
    original_fixed = NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = NESTED.BASE.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return NESTED.BASE.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        value = NESTED.BASE.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = NESTED.REPAIR.packed_facade_gate(
            target, Path(str(target) + ".elf"))
        return value

    NESTED.BASE.CAN.REPLAY.configure = lambda: None
    NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    NESTED.BASE.PRODUCT.fixed_facade_gate = facade
    try:
        value = NESTED.BASE.CAN.complete_artifacts()
    finally:
        NESTED.BASE.CAN.REPLAY.configure = original_configure
        NESTED.BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        NESTED.BASE.PRODUCT.fixed_facade_gate = original_facade
    final_product = NESTED.BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_elf.stat().st_size, NESTED.BASE.sha(final_elf)) ==
                EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "artifact-only Completion rebuilt the native INIT pair")
    NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
    return value


def mapped_section_rows(truth: ElfTruth) -> list[tuple[int, bytes, str]]:
    names = (".lisp65_c2_mapped_far_service",
             ".lisp65_c2_mapped_product_cold")
    rows = []
    for name in names:
        raw = truth.section_bytes(name)
        start = truth.symbol("__" + name.removeprefix(".") + "_load_start").value
        rows.append((start, raw, name))
    require([(start, len(raw), name) for start, raw, name in rows] == [
        (0x2B8B2, 1488, ".lisp65_c2_mapped_far_service"),
        (0x2BE8D, 324, ".lisp65_c2_mapped_product_cold")],
        "native INIT mapped media geometry drift")
    return rows


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    identity = load(STATIC / "product/substitution-artifacts.json")
    product_id = identity["product_build_id_hex"]
    require(product_id == "0xb0202154", "native INIT product identity drift")
    static = {"status": "passed-v1.7-native-init-static-plane",
              "product_build_id": product_id,
              "product_build_id_authority": bind(
                  STATIC / "product/substitution-artifacts.json"),
              "bank2_static_code_bytes": 46053}
    wplto = {"status": "passed-qualified-native-init-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = BASE.CAN.manifest(static, wplto, completion)
    elf = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46053, "native INIT Bank-2 prefix drift")
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
                cursor >= 0x2B8B2 else "static-to-mapped-free-hole"),
                "start": cursor, "end_exclusive": start,
                "bytes": start - cursor})
        offset = start - base
        materialized[offset:offset + len(raw)] = raw
        owners.append({"owner": name, "start": start,
                       "end_exclusive": start + len(raw), "bytes": len(raw)})
        cursor = start + len(raw)
    require(cursor == 0x2BFD1 and 0x30000 - cursor == 16431,
            "native INIT media end reserve drift")
    owners.append({"owner": "mapped-tenant-bank-end-reserve",
                   "start": cursor, "end_exclusive": 0x30000,
                   "bytes": 16431})
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
        "membership_authority": "native INIT final-ELF composed ownership",
    })
    BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.CAN.check()
    return value


def _append_init(source: Path, image: Path) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    result = subprocess.run([c1541, str(image), "-write", str(source),
                             "init.l65"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, "c1541 INIT append failed:\n" +
            result.stdout.decode("latin-1", errors="replace"))


def pair_identity(product: Path, library: Path,
                  expected_init: bytes | None) -> dict[str, Any]:
    product_id, c2d = PREP.PAIR.product_world(product)
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(library.read_bytes())
    init = visible.pop(b"INIT.L65", None)
    require(init == expected_init, "INIT.L65 visible payload drift")
    require(b"L65INDEX" in visible, "library D81 lacks L65INDEX")
    artifacts = {name.decode("ascii").lower(): raw
                 for name, raw in visible.items() if name != b"L65INDEX"}
    worlds = {name: PREP.PAIR.artifact_world(raw)
              for name, raw in artifacts.items()}
    require(all(world == product_id for world in worlds.values()),
            "library/product world mismatch")
    rows = PREP.LIBMEDIA.L65I.decode_index(
        visible[b"L65INDEX"], artifacts, artifact_build_id=product_id)
    require(sorted(row["name"] for row in rows) == sorted(artifacts),
            "library index/artifact inventory mismatch")
    return {
        "mounted_C2D_sha256": hashlib.sha256(c2d).hexdigest(),
        "product_build_id": f"0x{product_id:08x}",
        "library_build_ids": {name: f"0x{world:08x}"
                              for name, world in sorted(worlds.items())},
        "index_rows": len(rows), "row_names": [row["name"] for row in rows],
        "INIT_L65": (None if init is None else bind_bytes(init)),
        "result": "same-world-pair-with-raw-init-source",
    }


def library_media() -> dict[str, Any]:
    """Bind candidate stdlib as index anchor and derive raw INIT variants."""
    product_id, _c2d = PREP.PAIR.product_world(PREP.MEDIA.PRODUCT_D81)
    PREP.PRODUCT_ID = product_id
    PREP.LIBRARY.mkdir(parents=True)
    manifest = next(path for key, _image, path in CARD.init_specs()
                    if key == "buffer")
    spec = ("buffer", "buffer", "buffer", manifest, ())
    row, artifact = PREP.LIBMEDIA.measured(spec, (1, 1), product_id)
    artifact_path = PREP.LIBRARY / "buffer.l65s"
    artifact_path.write_bytes(artifact)
    seed_index = PREP.LIBRARY / "l65index.seed"
    seed_index.write_bytes(PREP.LIBMEDIA.L65I.encode_index([row]))
    seed = PREP.LIBRARY / "library.seed.d81"
    PREP.LIBMEDIA.build_library_d81(
        seed, seed_index, [(artifact_path, "buffer")])
    locator = PREP.LIBMEDIA.L65I.d81_locators(seed)["buffer"]
    row, located = PREP.LIBMEDIA.measured(spec, locator, product_id)
    require(located == artifact, "INIT media anchor changed with final locator")
    index = PREP.LIBMEDIA.L65I.encode_index([row])
    index_path = PREP.LIBRARY / "l65index"
    index_path.write_bytes(index)
    missing = PREP.LIBRARY / "lisp65-library.d81"
    PREP.LIBMEDIA.build_library_d81(
        missing, index_path, [(artifact_path, "buffer")])
    seed.unlink()
    seed_index.unlink()
    valid_source = PREP.LIBRARY / "INIT-VALID.L65"
    error_source = PREP.LIBRARY / "INIT-ERROR.L65"
    valid_source.write_bytes(VALID_INIT)
    error_source.write_bytes(ERROR_INIT)
    valid = PREP.LIBRARY / "lisp65-library-init-valid.d81"
    error = PREP.LIBRARY / "lisp65-library-init-error.d81"
    shutil.copyfile(missing, valid)
    shutil.copyfile(missing, error)
    _append_init(valid_source, valid)
    _append_init(error_source, error)
    variants = {
        "missing": {"D81": bind(missing),
                    "pair": pair_identity(PREP.MEDIA.PRODUCT_D81, missing, None)},
        "valid": {"D81": bind(valid), "source": bind(valid_source),
                  "pair": pair_identity(PREP.MEDIA.PRODUCT_D81, valid, VALID_INIT)},
        "error": {"D81": bind(error), "source": bind(error_source),
                  "pair": pair_identity(PREP.MEDIA.PRODUCT_D81, error, ERROR_INIT)},
    }
    require(all(row["pair"]["product_build_id"] == f"0x{product_id:08x}"
                and row["pair"]["row_names"] == ["buffer"]
                for row in variants.values()),
            "native INIT library variants do not share one product world")
    return {"variant": "v1.7-native-init", "product_build_id":
            f"0x{product_id:08x}", "D81": bind(missing),
            "index": bind(index_path), "index_rows": [row],
            "artifacts": {"buffer": bind(artifact_path)},
            "visible_files": ["BUFFER", "L65INDEX"],
            "Comfort_absent": True,
            "INIT_variants": variants}


def session_config(product: Path, library: Path) -> dict[str, Any]:
    valid = PREP.LIBRARY / "lisp65-library-init-valid.d81"
    error = PREP.LIBRARY / "lisp65-library-init-error.d81"
    return {
        "format": "lisp65-c2-v17-native-init-device-session-v1",
        "recorded_on": "2026-08-27", "status": "ready-owner-contact",
        "claim_scope": {
            "accepts": ["v1.7-native-INIT.L65"],
            "observes_only": ["A0-error-to-prompt-perception"],
            "excludes": ["Comfort", "Block-3", "canonical-prompt-swap",
                         "release-publication", "automatic-feature-reopening"],
        },
        "media": {
            "product": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "library_missing": {**bind(library), "remote_name": MISSING_REMOTE},
            "library_valid": {**bind(valid), "remote_name": VALID_REMOTE},
            "library_error": {**bind(error), "remote_name": ERROR_REMOTE},
        },
        "choreography": {
            "all_media_uploaded_and_read_back_before_boot": True,
            "fresh_cold_boot_for_each_library_variant": True,
            "product_mounted_last": True,
            "library_mounted_physically_through_freezer": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
        },
        "rows": [
            {"id": "I-absent", "library": MISSING_REMOTE,
             "actions": ["cold boot with no INIT.L65 on the library medium"],
             "expect": ["no INIT error or output", "native lisp65> is usable"]},
            {"id": "I-present", "library": VALID_REMOTE,
             "actions": ["cold boot", "at lisp65> submit (init-proof)"],
             "expect": ["INIT evaluates before the banner", "result is 17"]},
            {"id": "I-error", "library": ERROR_REMOTE,
             "actions": ["cold boot", "observe the one ordinary INIT error",
                         "at the returned lisp65> submit (list 1 3)"],
             "expect": ["exactly one normal numeric VM error", "no red frame",
                        "INIT is not retried", "result is (1 3)"]},
            {"id": "A0-perception", "library": MISSING_REMOTE,
             "actions": ["at a live native prompt submit (>= nil 32)",
                         "report approximate seconds from Return to lisp65>"],
             "expect": ["ordinary type error", "no red frame",
                        "usable native prompt"],
             "claim": "observation only; does not reopen Comfort or Block 3"},
        ],
        "decision_table": {
            "all-I-rows-green": "Block I hardware accepted",
            "A0-observation": "owner input to a later, separate reopening decision",
            "daily-use-blocker": "stop under the standing anti-rabbit-hole rule",
        },
    }


def finish_media(media: dict[str, Any]) -> dict[str, Any]:
    PREP.configure_paths()
    PREP.MEDIA.check()
    product = PREP.MEDIA.PRODUCT_D81
    missing = PREP.LIBRARY / "lisp65-library.d81"
    valid = PREP.LIBRARY / "lisp65-library-init-valid.d81"
    error = PREP.LIBRARY / "lisp65-library-init-error.d81"
    pairs = {
        "missing": pair_identity(product, missing, None),
        "valid": pair_identity(product, valid, VALID_INIT),
        "error": pair_identity(product, error, ERROR_INIT),
    }
    config = session_config(product, missing)
    PREP.SESSION.write_bytes(canonical(config))
    value = {
        "format": "lisp65-c2-v17-native-init-base-media-receipt-v1",
        "recorded_on": "2026-08-27",
        # Historical wrappers promote this in place after adding packed gates.
        "status": "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY",
        "accepted_pair": {"PRG": bind(PREP.WPLTO /
            "lisp65-c2-substitution-linked.prg"), "ELF": bind(PREP.WPLTO /
            "lisp65-c2-substitution-linked.prg.elf")},
        "completion": bind(PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(PREP.MEDIA.WORK_D81),
                  "library": bind(missing), "library_index": bind(
                      PREP.LIBRARY / "l65index"),
                  "library_valid": bind(valid), "library_error": bind(error)},
        "readback": {"product":
            "passed-packed-visible-file-and-role-identity-closure",
            "libraries": "passed-indexed-world-plus-explicit-raw-INIT-closure"},
        "same_world_pair": pairs["missing"], "same_world_pairs": pairs,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": {
            "index": bind(PREP.LIBRARY / "l65index"),
            "artifacts": {"buffer": bind(PREP.LIBRARY / "buffer.l65s")},
            "row_names": ["buffer"], "Comfort_absent": True,
            "INIT_variants": {name: {"D81": bind(path),
                "INIT_L65": pairs[name]["INIT_L65"]}
                for name, path in (("missing", missing), ("valid", valid),
                                   ("error", error))}},
        "session": bind(PREP.SESSION), "claim_limit": config["claim_scope"],
        "execution_accounting": {"successful_run": {"WPLTO_runs": 0,
            "product_links": 0, "artifact_completions": 1,
            "media_builds": 4, "device_contacts": 0}},
    }
    PREP.RECEIPT.write_bytes(canonical(value))
    print("v1.7 native INIT base media: PASS media=4 variants=3")
    return value


def check_base_media() -> dict[str, Any]:
    # A fresh read-only process has not traversed the historical path-rebind
    # stack in the same order as the one-shot producer.  Bind the consumer to
    # this successor's explicit receipt rather than ambient PREP state.
    value = load(RECEIPT)
    require(value["status"] in (
                "PASS: V1.6 ITEMS 1/2 DEVICE CONTACT READY", STATUS)
            and value["library_closure"]["Comfort_absent"] is True,
            "native INIT base media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"native INIT prepared artifact identity drift: {row['path']}")
    product = ROOT / value["media"]["product"]["path"]
    current = {
        "missing": pair_identity(product,
            ROOT / value["media"]["library"]["path"], None),
        "valid": pair_identity(product,
            ROOT / value["media"]["library_valid"]["path"], VALID_INIT),
        "error": pair_identity(product,
            ROOT / value["media"]["library_error"]["path"], ERROR_INIT),
    }
    require(current == value["same_world_pairs"],
            "native INIT persisted pair identity drift")
    return value


def static_plane_gate() -> dict[str, Any]:
    path = BUILD / "canonical-product/canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v1.7-native-init-static-plane"
            and plane["product_build_id"] == "0xb0202154"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 49105
            and plane["mapped_sections"] == [
                ".lisp65_c2_mapped_far_service",
                ".lisp65_c2_mapped_product_cold"]
            and any(item["owner"] == "static-to-mapped-free-hole"
                    and item["bytes"] == 1229 for item in owners)
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 16431
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "native INIT packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def configure_successor() -> None:
    prepare_static_inputs()
    for name, value in {
        "CARD_BUILD": CARD_BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "BUILD": BUILD, "ADAPTER": ADAPTER, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "CLOSURE": CLOSURE, "ACCEPTANCE": ACCEPTANCE,
        "PRODUCT_REMOTE": PRODUCT_REMOTE, "LIBRARY_REMOTE": MISSING_REMOTE,
        "EXPECTED": EXPECTED, "STATUS": STATUS,
    }.items():
        setattr(BASE_MEDIA, name, value)
    for name, function in {
        "authority": authority, "prepare_static_inputs": prepare_static_inputs,
        "closure_adapter": closure_adapter,
        "configure_candidate": configure_candidate,
        "product_manifest": product_manifest, "session_config": session_config,
        "library_media": library_media, "finish_media": finish_media,
        "check_base_media": check_base_media,
        "static_plane_gate": static_plane_gate,
    }.items():
        setattr(BASE_MEDIA, name, function)
    NESTED.complete = complete
    BASE_MEDIA.configure_successor()


def finalize() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == STATUS, "native INIT wrappers did not seal media")
    value.update({
        "format": "lisp65-c2-v17-native-init-acceptance-media-v1",
        "recorded_on": "2026-08-27", "media_contract": bind(CONTRACT),
        "read_only_resume": bind(RESUME),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "replacement_media_builds": 4,
            "device_contacts": 0},
        "status": STATUS,
    })
    RECEIPT.write_bytes(canonical(value))
    return value


def build() -> None:
    configure_successor()
    MEDIA.build()
    value = finalize()
    print("v1.7 native INIT media: PASS "
          f"product={value['media']['product']['sha256'][:12]} variants=3")


def check() -> None:
    configure_successor()
    PREP.configure_paths()
    PREP.MEDIA.check()
    value = check_base_media()
    product = ROOT / value["media"]["product"]["path"]
    final_product = BUILD / "canonical-product/final/lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 4, "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"]["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf"
            and value["clean_static_plane"] == static_plane_gate()
            and value["media_contract"] == bind(CONTRACT)
            and value["read_only_resume"] == bind(RESUME)
            and bind(product) == value["media"]["product"]
            and NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
                == value["shipped_byte_facade"],
            "native INIT packed-media proof drift")
    print("v1.7 native INIT media: CHECK PASS links=0 cards=0 device=0")


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
