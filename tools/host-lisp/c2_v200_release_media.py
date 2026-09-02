#!/usr/bin/env python3
"""Pack artifact-only WORKBENCH 2.0.0 release media after owner Ship."""

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

import c2_v200_release_card as CARD  # noqa: E402
import c2_v200_release_strip_device_media as MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
SHIP_HEADER = "## v2.0.0 owner Ship — 2026-09-02"
BUILD = ROOT / "build/c2.3/v2.0.0-release-media-r1"
WPLTO = CARD.WPLTO
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0.0-release-media-receipt.json"
SESSION = BUILD / "unused-release-session.json"
PRODUCT_REMOTE = "LISP65.D81"
EXPECTED = {
    "PRG": (41811,
        "930da9ca24098664c4d223991b748c60d8fc10586ef0c46a115364c8e637c419"),
    "ELF": (636100,
        "96ba670981172fab72383d40cf6da24d3318749d03a916014b716d4b881ecd05"),
}
PRODUCT_ID = 0x4A1713AB
PLANE_BYTES = 47795
STATUS = "PASS: V2.0.0 RELEASE MEDIA READY"
FORMAT = "lisp65-c2-v200-release-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-release-media-no-device-session-v1"


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


class ReleaseCardAdapter:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    LINK = CARD.CHAIN.LINK
    PRODUCT_KEYS = CARD.STRIP.PRODUCT_KEYS

    @staticmethod
    def configure() -> None:
        CARD.configure()


class ProductCard:
    BUILD = ReleaseCardAdapter.BUILD
    WPLTO = ReleaseCardAdapter.WPLTO
    PLANE = ReleaseCardAdapter.PLANE
    PRG = ReleaseCardAdapter.PRG
    ELF = ReleaseCardAdapter.ELF
    RECEIPT = ReleaseCardAdapter.RECEIPT
    STATUS = ReleaseCardAdapter.STATUS
    LINK = ReleaseCardAdapter.LINK

    @staticmethod
    def patch_link_stack() -> None:
        CARD.configure()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        return CARD.CHAIN.setup_link_world()


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = MEDIA.MediaPrice.RECEIPT
    PRICE = MEDIA.MediaPrice


def ship_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(SHIP_HEADER) == 1, "v2.0 Ship section drift")
    section = SHIP_HEADER + text.split(SHIP_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("the owner said ship", "138/138/138/138",
                  "107 free symbol slots / 1,467 free name bytes",
                  "publish remains closed"):
        require(token in folded, f"v2.0 Ship authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
            "section": SHIP_HEADER, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"v2.0 release {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    card = load(CARD.RECEIPT)
    pair = accepted_pair()
    scope = ROOT / card["scope"]["path"]
    acceptance = ROOT / card["acceptance"]["path"]
    require(card["status"] == CARD.STATUS
            and card["artifacts_before"] == card["artifacts_after"]
            and {name: card["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == pair
            and card["owner_Ship"] == "DECIDABLE-NOT-INFERRED"
            and card["owner_Publish"] == "CLOSED"
            and load(scope)["status"] == load(acceptance)["status"] == "PASS",
            "v2.0 release-card authority drift")
    return {"owner_Ship": ship_authority(), "release_card": bind(CARD.RECEIPT),
            "scope": bind(scope), "acceptance": bind(acceptance),
            "rule": "Ship selects the qualified pair; media is artifact-only",
            "accounting": {"new_WPLTO_runs": 0, "new_product_links": 0,
                           "new_product_cards": 0, "device_contacts": 0}}


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    require(plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 15871
            and plane["composed_owners"][-2]["bytes"] == 324
            and plane["composed_owners"][-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "v2.0 release composed Bank-2 drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "all shipped Bank-2 intervals are composed and disjoint"}


def finish(packed: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    delivery = MEDIA.BASE.BASE
    media = delivery.M.MEDIA
    delivery.configure_paths()
    media.check()
    product, work = media.PRODUCT_D81, media.WORK_D81
    product_id, mounted_c2d = delivery.M.BASE.MEDIA.PREP.PAIR.product_world(
        product)
    require(product_id == PRODUCT_ID, "release medium carries another world")
    readback = MEDIA.packed_readback(product)
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "accepted_pair": accepted_pair(),
        "completion": bind(delivery.M.BASE.MEDIA.CAN.RECEIPTS /
                           "artifact-completion.json"),
        "media_closure": bind(media.MANIFEST),
        "media": {"product": bind(product), "work": bind(work)},
        "readback": "passed-visible-file-and-role-identity-closure",
        "mounted_product_world": {
            "product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_artifact_closure": {
            "stager_gate": packed["stager"]["gate"],
            "product_entries": packed["media"]["product"]["entries"],
            "artifact_count": packed["artifact_count"]},
        "packed_readback": readback,
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "banner": "WORKBENCH 2.0.0",
        "claim_limit": {"ships": [
                "Tier-1 domain discipline over 62 corrected cells",
                "lossless native-prompt input", "native prompt editor",
                "native INIT.L65 and A0 recovery", "resident delivery-chain gates"],
            "documents": ["(car 1) returns nil",
                          "Tier-1 type error lacks string-length hint"],
            "excludes": ["type-ahead during evaluation", "Comfort",
                         "Matcher/Blink", "Tier 2"]},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "library_media_builds": 0, "device_contacts": 0}}
    delivery.M.BASE.write(RECEIPT, value)
    return value


def inherited_check(*, source_only: bool = False) -> None:
    value = load(RECEIPT)
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["banner"] == "WORKBENCH 2.0.0"
            and value["packed_readback"]["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and value["packed_readback"]["closure"]["object_count"] == 760
            and value["packed_readback"]["closure"]["call_site_count"] == 2436
            and value["packed_readback"]["generation_coherence"]["object_count"] == 397
            and value["packed_readback"]["delivered_key_sources"]["active_sink_set"] == [
                "c2_kernal_input_take"]
            and value["packed_readback"]["delivered_host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and value["accounting"]["WPLTO_runs"] == 0
            and value["accounting"]["product_links"] == 0,
            "v2.0 release media receipt drift")
    require(value["composed_bank2"] == static_plane_gate(),
            "v2.0 release composed proof drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"v2.0 release media artifact drift: {row['path']}")
    print("v2.0.0 release media: CHECK PASS links=0 device=0 "
          f"source_only={str(source_only).lower()}")


def check() -> None:
    configure()
    inherited_check()


def configure() -> None:
    MEDIA.STRIP = ReleaseCardAdapter
    MEDIA.ProductCard = ProductCard
    MEDIA.Adapter = Adapter
    values = {"BUILD": BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "PRODUCT_REMOTE": PRODUCT_REMOTE,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": EXPECTED, "STATUS": STATUS, "FORMAT": FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT}
    for name, value in values.items():
        setattr(MEDIA, name, value)
    MEDIA.accepted_pair = accepted_pair
    MEDIA.authority = authority
    MEDIA.static_plane_gate = static_plane_gate
    MEDIA.finish = finish
    MEDIA.inherited_check = inherited_check
    MEDIA.check = inherited_check
    MEDIA.configure()


def build() -> None:
    if BUILD.exists() or RECEIPT.exists():
        require(BUILD.is_dir() and RECEIPT.is_file(),
                "v2.0 release media retry is not a complete frozen output")
        check()
        print("v2.0.0 release media: RESUME PASS artifact-only "
              f"product={load(RECEIPT)['media']['product']['sha256']} device=0")
        return
    configure()
    MEDIA.BASE.build()
    check()
    value = load(RECEIPT)
    print("v2.0.0 release media: BUILD PASS artifact-only "
          f"product={value['media']['product']['sha256']} device=0")


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
        print(f"v2.0.0 release media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
