#!/usr/bin/env python3
"""Pack artifact-only v1.9.0 release media from the Ship-selected pair."""

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

import c2_v190_blocks_ab_acceptance_media as MEDIA  # noqa: E402
import c2_v190_release_card as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.9.0-release-media-r3"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v1.9.0-release-media-receipt.json"
CARD_RECEIPT = CARD.RECEIPT
SCOPE = CARD.BUILD / "owner-scope-result.json"
ACCEPTANCE = CARD.BUILD / "artifact-acceptance.json"
WPLTO = CARD.BUILD / "wplto"
SOURCE_STATIC = CARD.PLANE_ROOT
EXPECTED = {
    "PRG": (41564,
        "fad7578736349f485fed2a49c9192e37e50bcfbd8b288c102cf8a799c4781347"),
    "ELF": (635508,
        "37cb8eff54b5394aff3130c279979ad22441c2d929c75dafc48679e3ad4b190e"),
}
PRODUCT_ID = 0x8C6CC520
PLANE_BYTES = 47469
STATUS = "PASS: V1.9.0 RELEASE MEDIA READY"
SHIP_HEADER = "## v1.9.0 owner Ship — 2026-08-30"


class ReleaseMediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReleaseMediaError(message)


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


def ship_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(SHIP_HEADER) == 1, "v1.9 Ship section drift")
    section = SHIP_HEADER + text.split(SHIP_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    normalized = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("the owner said ship", "136/136/136/136",
                  "109 slots / 1,486 name bytes", "publish remains closed"):
        require(token in normalized, f"v1.9 Ship authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
            "section": SHIP_HEADER, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(WPLTO / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(WPLTO / "lisp65-c2-substitution-linked.prg.elf")}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"v1.9 release {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    card = load(CARD_RECEIPT)
    require(card["status"] == CARD.STATUS
            and card["artifacts_before"] == card["artifacts_after"]
            and {name: card["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == accepted_pair()
            and card["owner_Ship"] == "DECIDABLE-NOT-INFERRED"
            and card["owner_Publish"] == "CLOSED",
            "v1.9 release-card authority drift")
    return {"owner_Ship": ship_authority(), "release_card": bind(CARD_RECEIPT),
            "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE),
            "rule": "Ship selects the qualified pair; media is artifact-only",
            "accounting": {"new_WPLTO_runs": 0, "new_product_links": 0,
                           "new_product_cards": 0, "device_contacts": 0}}


def configure_globals() -> None:
    for name, value in {
        "CARD_BUILD": CARD.BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "BUILD": BUILD, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "CARD_RECEIPT": CARD_RECEIPT, "SCOPE": SCOPE,
        "ACCEPTANCE": ACCEPTANCE, "EXPECTED": EXPECTED,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "STATUS": STATUS,
    }.items():
        setattr(MEDIA, name, value)
    MEDIA.PREP.PRODUCT_ID = PRODUCT_ID
    MEDIA.authority = authority
    MEDIA.accepted_pair = accepted_pair
    MEDIA.configure_candidate = configure_candidate


def configure_candidate() -> None:
    """Install exactly the configuration which emitted the release pair."""
    CARD.configure()
    r8 = CARD.R8
    r8.configure()
    r8.CARD.BASE.configure_full_candidate()
    r8.R7.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    r8.R7.PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    r8.CARD.CLIENT.INIT._configure_plane_module()
    r8.CARD.CLIENT.CURRENT_PLANE.bind_current_plane(STATIC)
    MEDIA.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    MEDIA.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    MEDIA.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(accepted_pair_path("ELF"),
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(MEDIA.PRODUCT.VERIFIER_BINDING_SECTION)
    require(section.bytes == 40, "v1.9 verifier-binding size drift")
    MEDIA.PRODUCT.VERIFIER_BINDING_BASE = section.address
    MEDIA.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address


def accepted_pair_path(role: str) -> Path:
    suffix = ".elf" if role == "ELF" else ""
    return WPLTO / f"lisp65-c2-substitution-linked.prg{suffix}"


def closure_adapter() -> dict[str, Any]:
    card, scope, acceptance = load(CARD_RECEIPT), load(SCOPE), load(ACCEPTANCE)
    pair = accepted_pair()
    require(card["status"] == CARD.STATUS
            and card["artifacts_before"] == card["artifacts_after"]
            and scope["status"] == acceptance["status"] == "PASS"
            and card["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "v1.9 release closure is not media-ready")
    return {"format": "lisp65-v190-release-media-adapter-v1",
            "status": "PASS: SHIP-SELECTED FROZEN PAIR MEDIA AUTHORIZED",
            "frozen_pair_before": pair, "frozen_pair_after": pair,
            "card": bind(CARD_RECEIPT), "scope": bind(SCOPE),
            "acceptance": bind(ACCEPTANCE), "authority": authority(),
            "completion_input_projection": MEDIA.prepare_static_inputs(),
            "rule": "artifact-only completion; zero WPLTO and product links"}


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = MEDIA.product_manifest(completion)
    value["static_plane"]["status"] = "passed-v1.9.0-release-static-plane"
    value["static_plane"]["membership_authority"] = (
        "v1.9.0 release final-ELF composed ownership")
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
    require(plane["status"] == "passed-v1.9.0-release-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 16197
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "v1.9 release composed Bank-2 drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def finish(media: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    MEDIA.configure_paths()
    MEDIA.MEDIA.check()
    product, work = MEDIA.MEDIA.PRODUCT_D81, MEDIA.MEDIA.WORK_D81
    product_id, mounted_c2d = MEDIA.PREP.PAIR.product_world(product)
    require(product_id == PRODUCT_ID, "v1.9 release D81 carries wrong world")
    visible = MEDIA.PREP.LIBMEDIA.L65I.D81.visible_files(product.read_bytes())
    require(b"INIT.L65" not in visible and b"REPL-COMFORT" not in visible,
            "v1.9 release product medium contains excluded freight")
    value = {
        "format": "lisp65-c2-v190-release-media-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(MEDIA.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(MEDIA.MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(work),
                  },
        "readback": "passed-packed-visible-file-and-role-identity-closure",
        "mounted_product_world": {"product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "library_closure": {"delivered_rows": [], "Comfort_absent": True,
            "v16core_status": "resident-product-freight-not-duplicated"},
        "packed_artifact_closure": {"stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "banner": "WORKBENCH 1.9.0",
        "claim_limit": {"ships": ["lossless native-prompt input",
            "native prompt editor", "native INIT.L65", "A0 recovery"],
            "excludes": ["type-ahead during evaluation", "Comfort",
                "Matcher/Blink", "$22", "domain findings"]},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "library_media_builds": 0, "device_contacts": 0},
    }
    RECEIPT.write_bytes(canonical(value))
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "v1.9 release media is one-shot")
    configure_globals()
    adapter = closure_adapter()
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "closure-adapter.json").write_bytes(canonical(adapter))
    completion = MEDIA.complete_artifacts()
    product_manifest(completion)
    MEDIA.configure_paths()
    packed = MEDIA.MEDIA.build(
        stager_compile_defines=(MEDIA.PREP.LIVENESS.OPT_IN,))
    value = finish(packed, completion)
    check()
    print("v1.9.0 release media: BUILD PASS artifact-only "
          f"product={value['media']['product']['sha256']} device=0")


def check() -> None:
    configure_globals()
    value = load(RECEIPT)
    require(value["status"] == STATUS and value["banner"] == "WORKBENCH 1.9.0"
            and value["accepted_pair"] == accepted_pair()
            and value["library_closure"]["Comfort_absent"] is True
            and value["library_closure"]["v16core_status"] ==
                "resident-product-freight-not-duplicated"
            and value["accounting"]["WPLTO_runs"] == 0
            and value["accounting"]["product_links"] == 0,
            "v1.9 release media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values()]:
        require(bind(ROOT / row["path"]) == row,
                f"v1.9 release media artifact drift: {row['path']}")
    MEDIA.configure_paths()
    MEDIA.MEDIA.check()
    require(value["composed_bank2"] == static_plane_gate(),
            "v1.9 release composed proof drift")
    print("v1.9.0 release media: CHECK PASS links=0 device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    else:
        raise ReleaseMediaError("usage: build|check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9.0 release media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
