#!/usr/bin/env python3
"""Pack artifact-only v1.7.0 release/D-session media from the release card."""

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

import c2_v160_item1_only_media as ITEM_MEDIA  # noqa: E402
import c2_v17_init_l65_acceptance_media as MEDIA  # noqa: E402
import c2_v17_init_l65_card as INIT  # noqa: E402
import c2_v170_release_card as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PREP = MEDIA.PREP
NESTED = MEDIA.NESTED
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = CARD.PLANE_ROOT
LIBRARY_SOURCE = INIT.BASELINE_ROOT / "static-plane/narrow-static/libs"
INPUT_ROOT = ROOT / "build/c2.3/v1.7.0-release-media-r5-inputs"
STATIC = INPUT_ROOT / "static-plane"
BUILD = ROOT / "build/c2.3/v1.7.0-release-media-r5"
ADAPTER = BUILD.parent / "v1.7.0-release-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.7.0-release-media-receipt.json"
SESSION = ROOT / "config/c2-v170-release-d-session.json"
CLOSURE = CARD.RECEIPT
RESUME = CARD.RESUME_RECEIPT
ACCEPTANCE = CARD.BUILD / "artifact-acceptance.json"
PRODUCT_REMOTE = "V170P.D81"
LIBRARY_REMOTE = "V170L.D81"
EXPECTED = {
    "PRG": (41566,
        "b6ea4519cd2ec29eec028e65fa0102b9eac89f7d0b1a85458415595f5db0342c"),
    "ELF": (647268,
        "e8ca0734427cbe22c6d60dfbba2cc141b8c98dd031beecdab8c57aa7d499efab"),
}
PRODUCT_ID = "0x2f688387"
STATUS = "PASS: V1.7.0 RELEASE MEDIA AND D-SESSION READY"
V16CORE_SOURCE_ERA = "e900ebe7bedffd97a3fdf480c03e3ea0d2e2e3ef"


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


def authority() -> dict[str, Any]:
    plan = CARD.authority()["owner_plan"]
    closure = load(CLOSURE)
    resume = load(RESUME)
    require(plan["commit"] == CARD.AUTHORIZATION
            and closure["status"] == CARD.STATUS
            and closure["media_authorized"] is True
            and resume["status"] ==
                "PASS: RELEASE FINAL GATE RESUMED READ-ONLY"
            and resume["artifacts_before"] == resume["artifacts_after"],
            "release media authority drift")
    return {"owner_plan": plan, "release_card": bind(CLOSURE),
            "read_only_resume": bind(RESUME)}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    scope = load(CARD.BUILD / "owner-scope-result.json")
    acceptance = load(ACCEPTANCE)
    pair = {name: closure["artifacts_after"][name]
            for name in ("ELF", "PRG")}
    require(closure["artifacts_before"] == closure["artifacts_after"]
            and scope["status"] == acceptance["status"] == "PASS",
            "release closure is not media-ready")
    value = {
        "format": "lisp65-v170-release-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair, "frozen_pair_after": pair,
        "card": bind(CLOSURE), "read_only_resume": bind(RESUME),
        "review_authority": authority(),
        "completion_input_projection": MEDIA.prepare_static_inputs(),
        "rule": "release media consumes the qualified pair; it never rebuilds it",
    }
    ADAPTER.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    CARD.configure()
    CARD.BASE.configure_full_candidate()
    MEDIA.BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    MEDIA.BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    MEDIA.BASE.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(MEDIA.BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    MEDIA.BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    MEDIA.BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "release verifier-binding size drift")


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    identity = load(STATIC / "product/substitution-artifacts.json")
    require(identity["product_build_id_hex"] == PRODUCT_ID,
            "release product identity drift")
    static = {"status": "passed-v1.7.0-release-static-plane",
              "product_build_id": PRODUCT_ID,
              "product_build_id_authority": bind(
                  STATIC / "product/substitution-artifacts.json"),
              "bank2_static_code_bytes": 46053}
    wplto = {"status": "passed-qualified-v1.7.0-release-link",
             "product": bind(WPLTO / "lisp65-c2-substitution-linked.prg")}
    value = MEDIA.BASE.CAN.manifest(static, wplto, completion)
    elf = MEDIA.BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46053, "release Bank-2 prefix drift")
    sections = MEDIA.mapped_section_rows(truth)
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
            "release media composed geometry drift")
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
        "membership_authority": "v1.7.0 release final-ELF composed ownership",
    })
    MEDIA.BASE.CAN.MANIFEST.write_bytes(canonical(value))
    MEDIA.BASE.CAN.check()
    return value


def library_media() -> dict[str, Any]:
    """Build v16core from its sealed v1.6 source against the v1.7 world."""
    product_id, _c2d = PREP.PAIR.product_world(PREP.MEDIA.PRODUCT_D81)
    PREP.PRODUCT_ID = product_id
    require(f"0x{product_id:08x}" == PRODUCT_ID,
            "release library derived the wrong product world")
    generated = PREP.BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    historical = subprocess.run(
        ["git", "show", f"{V16CORE_SOURCE_ERA}:lib/stdlib-read-line.lisp"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    public_source = generated / "stdlib-read-line-v160-sealed.lisp"
    public_source.write_text(
        ITEM_MEDIA.ITEM1.CURSOR.public_only_source(historical),
        encoding="utf-8")
    historical_sexp = subprocess.run(
        ["git", "show", f"{V16CORE_SOURCE_ERA}:lib/sexp-depth.lisp"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    sexp_source = generated / "sexp-depth-v160-sealed.lisp"
    sexp_source.write_bytes(historical_sexp)
    public_suite = generated / "v16core-v170-suite.json"
    public_suite.write_bytes(canonical({
        "extends": str(PREP.CURSOR_SUITE.resolve()),
        "sources": [public_source.relative_to(ROOT).as_posix(),
                    sexp_source.relative_to(ROOT).as_posix()],
        "remove_sources": [
            ITEM_MEDIA.ITEM1.CURSOR.READ_LINE.relative_to(ROOT).as_posix(),
            "lib/sexp-depth.lisp"],
        "resident_suite": str((ROOT /
            "config/c2-v160-comfort-repl-device-resident.json").resolve()),
        "private_key_event_modes": False,
        "allow_omitted_defuns": [],
        "evidence_era": {"commit": V16CORE_SOURCE_ERA,
            "path": "lib/stdlib-read-line.lisp"},
        "description": (
            "Shipped v1.6 cursor editor re-emitted for the v1.7 product ID; "
            "post-v1.6 Block-3 source is parked and not library freight."),
    }))
    prefix = generated / "v16core"
    manifest = PREP.compile_library(public_suite, prefix)
    emitted = ITEM_MEDIA.emitted_public_input_gate(prefix)
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
    locator = PREP.LIBMEDIA.L65I.d81_locators(seed)["v16core"]
    row, located = PREP.LIBMEDIA.measured(
        spec, locator, PREP.PRODUCT_ID)
    require(located == artifact, "v17 v16core changed with final locator")
    index = PREP.LIBMEDIA.L65I.encode_index([row])
    index_path = PREP.LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = PREP.LIBMEDIA.L65I.decode_index(
        index, {"v16core": artifact}, artifact_build_id=PREP.PRODUCT_ID)
    require(len(decoded) == 1 and decoded[0]["name"] == "v16core",
            "release library contains a second row")
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
            raise MediaError(f"release resolver mutation survived: {label}")
    final = PREP.LIBRARY / "lisp65-library.d81"
    PREP.LIBMEDIA.build_library_d81(
        final, index_path, [(artifact_path, "v16core")])
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index, b"V16CORE": artifact}
            and b"REPL-COMFORT" not in visible,
            "release library visible-file closure drift")
    seed.unlink(); seed_index.unlink()
    return {
        "variant": "v1.7.0-release-v16core",
        "product_build_id": f"0x{PREP.PRODUCT_ID:08x}",
        "D81": bind(final), "index": bind(index_path),
        "artifacts": {"v16core": bind(artifact_path)},
        "index_rows": decoded, "resolver_contracts": {"v16core": contract},
        "resolver_mutations_rejected": rejected,
        "visible_files": sorted(name.decode() for name in visible),
        "Comfort_absent": True,
        "source_authority": {"commit": V16CORE_SOURCE_ERA,
            "paths": ["lib/stdlib-read-line.lisp", "lib/sexp-depth.lisp"],
            "projected": [bind(public_source), bind(sexp_source)],
            "suite": bind(public_suite)},
        "public_only_projection": {"key_event_modes": [0, 1],
                                    "emitted_artifact_gate": emitted},
    }


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v170-release-d-session-v1",
        "recorded_on": "2026-08-27", "status": "ready-owner-Ship-contact",
        "claim_scope": {
            "accepts": ["v1.7.0-release-D5", "v1.7.0-performance-smoke",
                        "v1.7.0-INIT.L65-absence"],
            "excludes": ["Comfort", "Block-3", "v1.8-candidates",
                         "publication"],
            "green_consequence": "owner Ship halt becomes decidable",
        },
        "media": {
            "product": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "library": {**bind(library), "remote_name": LIBRARY_REMOTE},
        },
        "configuration": {
            "loaded_library_roles": [],
            "available_optional_roles": ["v16core"],
            "INIT_L65_on_release_product": False,
            "measurement_world": "shipped v1.7.0 product configuration",
        },
        "choreography": {
            "fresh_BASIC_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "product_mounted_last": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
            "final_stops": 1,
            "physical_bank0_captures": 1,
        },
        "rows": [
            {"id": "D-boot-and-init-absence",
             "actions": ["cold boot the release product medium"],
             "expect": ["WORKBENCH 1.7.0", "native lisp65>",
                        "no INIT.L65 output or error before the banner"]},
            {"id": "D-setup-published-call",
             "form": "(defun v17-perf-probe (x) (+ x 1))",
             "oracle": {"kind": "exact", "value": "v17-perf-probe"}},
            {"id": "D-list-read", "form": "(time (car (cdr (list 1 2))))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "2"}},
            {"id": "D-list-write",
             "form": "(time ((lambda (x) (progn (rplaca x 9) x)) (list 1 2)))",
             "oracle": {"kind": "time", "max_frames": 2,
                        "value": "(9 2)"}},
            {"id": "D-string-op", "form": "(time (string-ref \"abc\" 1))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "98"}},
            {"id": "D-published-call", "form": "(time (v17-perf-probe 41))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "42"}},
        ],
        "headroom_postcondition": {
            "minimum": {"free_symbol_slots": 32, "free_name_bytes": 384},
            "counter_addresses": "derive nsym and npool from the release ELF",
            "counter_view": "one final physical Bank-0 stopped-state capture",
            "observation_point": "after all D rows in the same fresh session",
        },
        "decision_table": {
            "all-rows-and-D5-green": "owner may say Ship",
            "daily-use-blocker": "stop; no Ship",
            "publication": "remains closed until later owner Publish",
        },
    }


def finish_media(media: dict[str, Any]) -> dict[str, Any]:
    PREP.configure_paths()
    PREP.MEDIA.check()
    product = PREP.MEDIA.PRODUCT_D81
    library = PREP.LIBRARY / "lisp65-library.d81"
    pair = PREP.PAIR.pair_identity(product, library)
    require(pair["product_build_id"] == PRODUCT_ID
            and pair["row_names"] == ["v16core"],
            "release product/library pair identity drift")
    visible = PREP.LIBMEDIA.L65I.D81.visible_files(product.read_bytes())
    require(b"INIT.L65" not in visible,
            "release product medium unexpectedly contains INIT.L65")
    config = session_config(product, library)
    SESSION.write_bytes(canonical(config))
    value = {
        "format": "lisp65-c2-v170-release-media-v1",
        "recorded_on": "2026-08-27", "status": STATUS,
        "authority": authority(),
        "accepted_pair": {"PRG": bind(WPLTO /
            "lisp65-c2-substitution-linked.prg"), "ELF": bind(WPLTO /
            "lisp65-c2-substitution-linked.prg.elf")},
        "completion": bind(PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(PREP.MEDIA.WORK_D81),
                  "library": bind(library),
                  "library_index": bind(PREP.LIBRARY / "l65index")},
        "readback": {"product":
            "passed-packed-visible-file-and-role-identity-closure",
            "library": "passed-v16core-index-and-artifact-identity-closure"},
        "same_world_pair": pair,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": {
            "D81": bind(library), "index": bind(PREP.LIBRARY / "l65index"),
            "artifacts": {"v16core": bind(PREP.LIBRARY / "v16core.l65s")},
            "row_names": ["v16core"], "Comfort_absent": True},
        "INIT_L65_absence": {"medium": "product", "visible_member": False,
            "gate": "visible D81 membership checked before owner contact"},
        "session": bind(SESSION), "claim_limit": config["claim_scope"],
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "media_builds": 2, "device_contacts": 0},
    }
    RECEIPT.write_bytes(canonical(value))
    print("v1.7.0 release media: PASS product/library same-world INIT=absent")
    return value


def check_base_media() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["INIT_L65_absence"]["visible_member"] is False
            and value["same_world_pair"]["row_names"] == ["v16core"],
            "release media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"release media artifact drift: {row['path']}")
    pair = PREP.PAIR.pair_identity(
        ROOT / value["media"]["product"]["path"],
        ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "release pair identity drift")
    return value


def static_plane_gate() -> dict[str, Any]:
    path = BUILD / "canonical-product/canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v1.7.0-release-static-plane"
            and plane["product_build_id"] == PRODUCT_ID
            and plane["bank2_static_code_bytes"] == row["bytes"] == 49105
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 16431
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "release packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def configure_successor() -> None:
    MEDIA.CARD = CARD
    CARD.init_specs = INIT.init_specs
    for name, value in {
        "CARD_BUILD": CARD_BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "LIBRARY_SOURCE": LIBRARY_SOURCE,
        "INPUT_ROOT": INPUT_ROOT, "STATIC": STATIC, "BUILD": BUILD,
        "ADAPTER": ADAPTER, "RECEIPT": RECEIPT, "SESSION": SESSION,
        "CLOSURE": CLOSURE, "RESUME": RESUME, "ACCEPTANCE": ACCEPTANCE,
        "PRODUCT_REMOTE": PRODUCT_REMOTE, "MISSING_REMOTE": LIBRARY_REMOTE,
        "EXPECTED": EXPECTED, "STATUS": STATUS,
    }.items():
        setattr(MEDIA, name, value)
    for name, function in {
        "authority": authority, "closure_adapter": closure_adapter,
        "configure_candidate": configure_candidate,
        "product_manifest": product_manifest,
        "library_media": library_media,
        "session_config": session_config, "finish_media": finish_media,
        "check_base_media": check_base_media,
        "static_plane_gate": static_plane_gate,
    }.items():
        setattr(MEDIA, name, function)
    MEDIA.configure_successor()


def build() -> None:
    configure_successor()
    if RECEIPT.exists() and BUILD.exists():
        # r5 reached and sealed all release-owned outputs before a historical
        # successor finalizer rejected the already-promoted status.  Resume the
        # release owner read-only over those exact outputs; do not rebuild D81s.
        check()
        value = load(RECEIPT)
        print("v1.7.0 release media: READ-ONLY RESUME PASS "
              f"product={value['media']['product']['sha256'][:12]} device=0")
        return
    MEDIA.MEDIA.build()
    check()
    value = load(RECEIPT)
    print("v1.7.0 release media: BUILD PASS "
          f"product={value['media']['product']['sha256'][:12]} device=0")


def check() -> None:
    configure_successor()
    PREP.configure_paths()
    PREP.MEDIA.check()
    value = check_base_media()
    product = ROOT / value["media"]["product"]["path"]
    final_product = BUILD / "canonical-product/final/" \
        "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    require(value["authority"] == authority()
            and value["execution_accounting"] == {
                "WPLTO_runs": 0, "product_links": 0, "product_cards": 0,
                "artifact_completions": 1, "media_builds": 2,
                "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["INIT_L65_absence"]["visible_member"] is False
            and NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
                ["status"] == "passed-packed-prg-facade-byte-equals-final-elf"
            and bind(product) == value["media"]["product"],
            "release packed-media proof drift")
    static_plane_gate()
    print("v1.7.0 release media: CHECK PASS links=0 cards=0 device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7.0 release media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
