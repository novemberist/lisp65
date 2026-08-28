#!/usr/bin/env python3
"""Pack artifact-only v1.8.0 release media from the banner successor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v180_release_card as CARD  # noqa: E402
import c2_v180_substrate_media as SUB  # noqa: E402


BASE = SUB.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.8.0-release-media"
INPUT_ROOT = ROOT / "build/c2.3/v1.8.0-release-media-inputs"
STATIC = INPUT_ROOT / "static-plane"
WPLTO = CARD.BUILD / "wplto"
SOURCE_STATIC = CARD.PLANE_ROOT
LIBRARY_SOURCE = BASE.INIT.BASELINE_ROOT / "static-plane/narrow-static/libs"
ADAPTER = BUILD.parent / "v1.8.0-release-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.8.0-release-media-receipt.json"
DEVICE = ARCH / "c2.3-v1.8.0-substrate-d-session-result-receipt.json"
CLOSURE = CARD.RECEIPT
SCOPE = CARD.BUILD / "owner-scope-result.json"
ACCEPTANCE = CARD.BUILD / "artifact-acceptance.json"
STATUS = "PASS: V1.8.0 RELEASE MEDIA READY"


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


def accepted_pair() -> dict[str, Any]:
    closure = load(CLOSURE)
    pair = {name: bind(WPLTO / f"lisp65-c2-substitution-linked.prg{suffix}")
            for name, suffix in (("PRG", ""), ("ELF", ".elf"))}
    require(pair == {name: closure["artifacts_after"][name]
                     for name in ("PRG", "ELF")},
            "release media pair differs from qualified card")
    return pair


def product_id() -> str:
    value = load(CARD.PLANE_RECEIPT)
    result = value["geometry"]["product_build_id"]
    require(isinstance(result, str) and result.startswith("0x"),
            "release product ID absent")
    return result


def authority() -> dict[str, Any]:
    closure, device = load(CLOSURE), load(DEVICE)
    require(closure["status"] == CARD.STATUS
            and closure["media_authorized"] is True
            and closure["artifacts_before"] == closure["artifacts_after"]
            and device["status"] ==
                "PASS: V1.8.0 SUBSTRATE D-SESSION HARDWARE GREEN; OWNER-SHIP-PENDING",
            "release media authority drift")
    return {"owner_Ship": CARD.owner_section(),
            "release_card": bind(CLOSURE),
            "substrate_device_result": bind(DEVICE),
            "rule": ("hardware selects the predecessor world; the packed "
                     "successor changes only the qualified banner closure"),
            "scope": {"new_WPLTO_runs": 0, "new_product_links": 0,
                      "new_product_cards": 0, "device_contacts": 0}}


def closure_adapter() -> dict[str, Any]:
    closure, scope, acceptance = load(CLOSURE), load(SCOPE), load(ACCEPTANCE)
    pair = accepted_pair()
    require(scope["status"] == acceptance["status"] == "PASS"
            and closure["artifacts_before"] == closure["artifacts_after"],
            "release card is not media-ready")
    value = {"format": "lisp65-v180-release-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair, "frozen_pair_after": pair,
        "release_card": bind(CLOSURE), "scope": bind(SCOPE),
        "acceptance": bind(ACCEPTANCE), "review_authority": authority(),
        "completion_input_projection": BASE.MEDIA.prepare_static_inputs(),
        "rule": "artifact-only media consumes the qualified release pair"}
    ADAPTER.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER.write_bytes(canonical(value))
    return value


def library_media() -> dict[str, Any]:
    value = SUB._base_library_media()
    value["variant"] = "v1.8.0-release-v16core"
    value["claim"] = ("same-world optional native library; Capture remains "
                      "closed and Comfort remains absent")
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = SUB._base_product_manifest(completion)
    value["static_plane"]["status"] = "passed-v1.8.0-release-static-plane"
    value["static_plane"]["membership_authority"] = (
        "v1.8.0 release final-ELF composed ownership")
    BASE.MEDIA.BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.MEDIA.BASE.CAN.check()
    return value


def lifecycle_gate() -> dict[str, Any]:
    return CARD.lifecycle_gate()


def finish_media(media: dict[str, Any]) -> dict[str, Any]:
    BASE.PREP.configure_paths()
    BASE.PREP.MEDIA.check()
    product = BASE.PREP.MEDIA.PRODUCT_D81
    library = BASE.PREP.LIBRARY / "lisp65-library.d81"
    pair = BASE.PREP.PAIR.pair_identity(product, library)
    require(pair["product_build_id"] == product_id()
            and pair["row_names"] == ["v16core"],
            "release product/library pair identity drift")
    visible_product = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        product.read_bytes())
    visible_library = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        library.read_bytes())
    require(b"INIT.L65" not in visible_product
            and b"INIT.L65" not in visible_library
            and b"REPL-COMFORT" not in visible_library,
            "release media freight drift")
    value = {"format": "lisp65-c2-v180-release-media-v1",
        "recorded_on": "2026-08-28", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(BASE.PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(BASE.PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product),
                  "work": bind(BASE.PREP.MEDIA.WORK_D81),
                  "library": bind(library),
                  "library_index": bind(BASE.PREP.LIBRARY / "l65index")},
        "readback": {"product":
            "passed-packed-visible-file-and-role-identity-closure",
            "library": "passed-v16core-index-and-artifact-identity-closure"},
        "same_world_pair": pair,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": {"D81": bind(library),
            "index": bind(BASE.PREP.LIBRARY / "l65index"),
            "artifacts": {"v16core": bind(
                BASE.PREP.LIBRARY / "v16core.l65s")},
            "row_names": ["v16core"], "Comfort_absent": True,
            "INIT_L65_absent": True},
        "release_lifecycle": {"Capture_present": True,
            "Hybrid_present": True, "initial_tail": 255,
            "activation_owner_present": False,
            "losslessness_claim": False, "final_ELF": lifecycle_gate()},
        "banner": "WORKBENCH 1.8.0",
        "claim_limit": {"ships": ["closed Capture/Hybrid substrate"],
            "excludes": ["Capture activation", "lossless user input",
                         "Comfort", "Matcher/Blink", "Block-3"]},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "media_builds": 2, "device_contacts": 0}}
    RECEIPT.write_bytes(canonical(value))
    print("v1.8.0 release media: PASS product/library same-world")
    return value


def check_base_media() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["banner"] == "WORKBENCH 1.8.0"
            and value["release_lifecycle"]["initial_tail"] == 255
            and value["release_lifecycle"]["losslessness_claim"] is False
            and value["library_closure"]["Comfort_absent"] is True,
            "release media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values()]:
        require(bind(ROOT / row["path"]) == row,
                f"release media artifact drift: {row['path']}")
    pair = BASE.PREP.PAIR.pair_identity(
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
    require(plane["status"] == "passed-v1.8.0-release-static-plane"
            and plane["product_build_id"] == product_id()
            and plane["bank2_static_code_bytes"] == row["bytes"] == 49105
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 16431
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "release packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def configure() -> None:
    expected = {name: (row["bytes"], row["sha256"])
                for name, row in accepted_pair().items()}
    for name, value in {
        "CARD": CARD, "CARD_BUILD": CARD.BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "LIBRARY_SOURCE": LIBRARY_SOURCE,
        "INPUT_ROOT": INPUT_ROOT, "STATIC": STATIC, "BUILD": BUILD,
        "ADAPTER": ADAPTER, "RECEIPT": RECEIPT,
        "SESSION": ROOT / "build/c2.3/v1.8.0-release-media/no-session.json",
        "CLOSURE": CLOSURE, "REPAIR": CLOSURE, "ACCEPTANCE": ACCEPTANCE,
        "SCOPE": SCOPE, "PRODUCT_REMOTE": "V180P.D81",
        "LIBRARY_REMOTE": "V180L.D81", "EXPECTED": expected,
        "PRODUCT_ID": product_id(), "STATUS": STATUS,
    }.items():
        setattr(SUB, name, value)
    for name, function in {
        "authority": authority, "accepted_pair": accepted_pair,
        "closure_adapter": closure_adapter, "library_media": library_media,
        "product_manifest": product_manifest, "finish_media": finish_media,
        "check_base_media": check_base_media,
        "static_plane_gate": static_plane_gate,
        "lifecycle_gate": lifecycle_gate,
    }.items():
        setattr(SUB, name, function)
    SUB.configure()


def seal() -> dict[str, Any]:
    value = load(RECEIPT)
    final_product = BUILD / "canonical-product/final/" \
        "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    value.update({"authority": authority(),
        "shipped_byte_facade": BASE.NESTED.REPAIR.packed_facade_gate(
            final_product, final_elf),
        "facade_mutations": BASE.NESTED.REPAIR.mutation_selftest(
            final_product, final_elf),
        "clean_static_plane": static_plane_gate()})
    value["release_lifecycle"]["final_ELF"] = lifecycle_gate()
    RECEIPT.write_bytes(canonical(value))
    return value


def build() -> None:
    configure()
    if not RECEIPT.exists():
        try:
            BASE.MEDIA.MEDIA.build()
        except RuntimeError as error:
            require(str(error) == "artifact-only base media receipt is not sealable"
                    and RECEIPT.is_file(),
                    f"artifact-only release producer failed: {error}")
    seal()
    check()
    value = load(RECEIPT)
    print("v1.8.0 release media: BUILD PASS "
          f"product={value['media']['product']['sha256'][:12]} device=0")


def check() -> None:
    configure()
    BASE.PREP.configure_paths()
    BASE.PREP.MEDIA.check()
    value = check_base_media()
    final_product = BUILD / "canonical-product/final/" \
        "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    require(value["authority"] == authority()
            and value["execution_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "artifact_completions": 1, "media_builds": 2,
                "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"] ==
                BASE.NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
            and value["facade_mutations"] ==
                BASE.NESTED.REPAIR.mutation_selftest(final_product, final_elf)
            and value["clean_static_plane"] == static_plane_gate(),
            "release packed-media proof drift")
    print("v1.8.0 release media: CHECK PASS links=0 cards=0 device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8.0 release media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
