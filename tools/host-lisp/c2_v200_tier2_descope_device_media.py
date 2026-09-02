#!/usr/bin/env python3
"""Pack artifact-only media from the qualified Tier-2 descope world."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v200_tier2_delivery_device_media as BASE  # noqa: E402
import c2_v200_tier2_descope_product_card as DESC  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Independent review — tier-2 descope media — 2026-09-02"
BUILD = ROOT / "build/c2.3/v2.0-tier2-descope-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0-tier2-descope-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-tier2-descope-device-session.json"
PRODUCT_REMOTE = "V20T2DS.D81"
PRODUCT_ID = 0x702C5BD3
PLANE_BYTES = 53820
EXPECTED = {
    "PRG": (41811,
        "7e81c7ec17b0c262bae8fb238de846254fe64d9bf235785bc5cf4009acf3b8ec"),
    "ELF": (636100,
        "799a7481cc9638b0c8ffcdbfe59ee39ad95687fe0f1e77aae16016bc56e16c7c"),
}
STATUS = "PASS: V2.0 TIER2 DESCOPE DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-tier2-descope-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-tier2-descope-device-session-v1"

ORIGINAL_SESSION = BASE.session_config


class ProductCard:
    BUILD = DESC.BUILD
    WPLTO = DESC.WPLTO
    PLANE = DESC.PLANE
    PRG = DESC.PRG
    ELF = DESC.ELF
    RECEIPT = DESC.RECEIPT
    STATUS = DESC.STATUS
    LINK = DESC.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        DESC.configure()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        return DESC.CHAIN.setup_link_world()


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = BASE.PRICE.RECEIPT
    PRICE = BASE.PRICE


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.M.BASE.MediaError(message)


def load(path: Path) -> dict[str, Any]:
    return BASE.load(path)


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "descope media authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only media", "closure and generation coherence",
                  "actually packed", "545/179/110", "forced collection"):
        require(token in folded, f"descope media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(DESC.PRG), "ELF": bind(DESC.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"descope {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(DESC.RECEIPT)
    pair = accepted_pair()
    scope = DESC.BUILD / "wplto/owner-scope-result.json"
    acceptance = DESC.BUILD / "artifact-acceptance.json"
    final = receipt["final_product"]
    require(receipt["status"] == DESC.STATUS
            and receipt["media_authorized"] is False
            and receipt["media_condition"] ==
                "independent review; then both packed-byte gates"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(scope)["status"] == load(acceptance)["status"] == "PASS"
            and final["contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and all(row["passed"] for lane in (
                    final["responsiveness_lanes"]["single_keystroke"],
                    final["responsiveness_lanes"]["batch_throughput"])
                    for row in lane["walls"].values()),
            "descope card is not independently media-ready")
    return {"product_card": bind(DESC.RECEIPT), "scope": bind(scope),
        "acceptance": bind(acceptance), "review_authority": plan_section(),
        "right": "artifact-only media; zero WPLTO and product links"}


def session_config(product: Path) -> dict[str, Any]:
    value = ORIGINAL_SESSION(product)
    value["format"] = SESSION_FORMAT
    value["status"] = "ready-owner-v2.0-tier2-descope-contact"
    value["claim_scope"] = {"accepts": [
        "documented Tier-2 descope behavior and Tier-1 domain discipline",
        "resident matcher and blink on native line editor and IDE",
        "lossless delivered input across forced collection"],
        "excludes": ["Comfort", "release", "publish"]}
    value["rows"][0] = {
        "id": "T2D-1-documented-domain-behavior",
        "actions": ["submit (car 1)", "submit (length \"abc\")"],
        "expect": ["nil (documented v2.0 inconsistency)",
                   "domain error names string-length, then one live prompt"]}
    value["rows"][3]["actions"].append(
        "submit (>= nil 32) and observe recovery")
    value["rows"][3]["expect"].append(
        "A0 error recovery returns to one live prompt practically immediately")
    return value


def inherited_check(*, source_only: bool = False) -> None:
    value, session = load(RECEIPT), load(SESSION)
    readback = value["packed_readback"]
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and readback["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and readback["closure"]["object_count"] == 797
            and readback["closure"]["call_site_count"] == 2686
            and readback["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and readback["delivered_key_sources"]["armed_sink_set"] == [
                "c2_kernal_input_take"]
            and readback["delivered_host_wall"]["counters"]["taken"] == 94
            and value["composed_bank2"]["static_plane"]
                ["largest_contiguous_hole"]["bytes"] == 9846
            and session["status"] ==
                "ready-owner-v2.0-tier2-descope-contact"
            and len(session["rows"]) == 5
            and session["choreography"]["optional_library_media"] == "none",
            "Tier-2 descope media/session semantics drift")
    require(bind(SESSION) == value["session"], "descope session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"prepared artifact identity drift: {row['path']}")
        require(BASE.packed_readback(
                ROOT / value["media"]["product"]["path"])["status"] ==
                readback["status"],
                "packed readback proof no longer reproduces")
    print("v2.0 Tier2 descope packed media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def configure() -> None:
    values = {
        "CARD": ProductCard, "Adapter": Adapter,
        "BUILD": BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "PRODUCT_REMOTE": PRODUCT_REMOTE,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": EXPECTED, "STATUS": STATUS, "FORMAT": FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT,
    }
    for name, value in values.items():
        setattr(BASE, name, value)
    BASE.accepted_pair = accepted_pair
    BASE.authority = authority
    BASE.plan_section = plan_section
    BASE.session_config = session_config
    BASE.check = inherited_check
    BASE.configure_paths()


def build() -> None:
    configure()
    BASE.patch()
    if BUILD.exists():
        children = sorted(path.name for path in BUILD.iterdir())
        require(children == ["inputs"] and WPLTO.is_dir() and STATIC.is_dir()
                and not RECEIPT.exists() and not SESSION.exists(),
                "descope media retry is not the input-only stopped state")
        adapter = BASE.M.closure_adapter()
        BASE.M.BASE.write(BUILD / "closure-adapter.json", adapter)
    BASE.M.build()


def check(*, source_only: bool = False) -> None:
    configure()
    inherited_check(source_only=source_only)
    value, session = load(RECEIPT), load(SESSION)
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["packed_readback"]["closure"]["object_count"] == 797
            and value["packed_readback"]["closure"]["call_site_count"] == 2686
            and value["packed_readback"]["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and session["status"] ==
                "ready-owner-v2.0-tier2-descope-contact"
            and session["rows"][0]["expect"][0] ==
                "nil (documented v2.0 inconsistency)"
            and session["rows"][3]["actions"][-1] ==
                "submit (>= nil 32) and observe recovery",
            "descope media/session successor drift")
    require(bind(SESSION) == value["session"], "descope session identity drift")
    print("v2.0 Tier2 descope device media: CHECK PASS "
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
        raise BASE.M.BASE.MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 Tier2 descope device media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
