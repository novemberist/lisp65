#!/usr/bin/env python3
"""Pack artifact-only media from the repaired Block-3 hot-path world."""

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

import c2_v200_block3_hot_path_repair_card as REPAIR  # noqa: E402
import c2_v200_tier2_descope_device_media as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — Block-3 hot-path replacement media — 2026-09-02")
BUILD = ROOT / "build/c2.3/v2.0-block3-hot-path-repair-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0-block3-hot-path-repair-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-block3-hot-path-repair-device-session.json"
PRODUCT_REMOTE = "V20B3R.D81"
PRODUCT_PROFILE = REPAIR.PLANE / "candidate-profile.json"
PRODUCT_ID = int(json.loads(PRODUCT_PROFILE.read_text())["product_build_id"], 0)
PLANE_BYTES = 53871
EXPECTED = {
    "PRG": (41811,
        "ffdbe24f22f0966dde2c604b6fb9e49ff4b2823aaed5b335ffad5a6f3e5382f0"),
    "ELF": (636100,
        "00a7fa2cc7f800c6b1077b2f96b16979d0201f86b9d93e373fca3a7d82b5a639"),
}
STATUS = "PASS: V2.0 BLOCK-3 HOT-PATH REPAIR DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-block3-hot-path-repair-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-block3-hot-path-repair-device-session-v1"
ORIGINAL_SESSION = BASE.ORIGINAL_SESSION
EXPECTED_CLOSURE_OBJECTS = 798
EXPECTED_CLOSURE_CALL_SITES = 2672
EXPECTED_COHERENCE_OBJECTS = 423
EXPECTED_LARGEST_HOLE = 9795


class ProductCard:
    BUILD = REPAIR.BUILD
    WPLTO = REPAIR.WPLTO
    PLANE = REPAIR.PLANE
    PRG = REPAIR.PRG
    ELF = REPAIR.ELF
    RECEIPT = REPAIR.RECEIPT
    STATUS = REPAIR.STATUS
    LINK = REPAIR.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        REPAIR.configure()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        return REPAIR.setup_link_world()


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = BASE.Adapter.PRICING_RECEIPT
    PRICE = BASE.Adapter.PRICE


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.BASE.M.BASE.MediaError(message)


def load(path: Path) -> dict[str, Any]:
    return BASE.load(path)


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "repair-media authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only replacement media",
                  "closure and generation coherence", "actually packed",
                  "physical single-key feel", "raw = seen = stored = taken"):
        require(token in folded, f"repair-media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(REPAIR.PRG), "ELF": bind(REPAIR.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"repair {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(REPAIR.RECEIPT)
    pair = accepted_pair()
    scope = REPAIR.CHAIN.LINK.BASE.SCOPE_RESULT
    acceptance = REPAIR.CHAIN.LINK.BASE.ACCEPTANCE_RESULT
    final = receipt["final_product"]
    single = final["responsiveness_lanes"]["single_keystroke"]
    batch = final["responsiveness_lanes"]["batch_throughput"]
    require(receipt["status"] == REPAIR.STATUS
            and receipt["media_authorized"] is False
            and receipt["media_condition"] ==
                "independent review, then packed-byte gates"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(scope)["status"] == load(acceptance)["status"] == "PASS"
            and final["contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and single["successor"]["vm_steps_per_character"] == 904
            and all(row["passed"] for row in single["walls"].values())
            and all(row["passed"] for row in batch["walls"].values()),
            "repair card is not independently media-ready")
    return {"product_card": bind(REPAIR.RECEIPT), "scope": bind(scope),
        "acceptance": bind(acceptance), "review_authority": plan_section(),
        "right": "artifact-only media; zero WPLTO and product links"}


def session_config(product: Path) -> dict[str, Any]:
    value = ORIGINAL_SESSION(product)
    value["format"] = SESSION_FORMAT
    value["status"] = "ready-owner-v2.0-block3-hot-path-repair-contact"
    value["claim_scope"] = {"accepts": [
        "documented Tier-2 descope behavior and Tier-1 domain discipline",
        "resident matcher and blink on native line editor and IDE",
        "lossless delivered input across forced collection",
        "physical single-key feel in the repaired delivered state"],
        "excludes": ["Comfort", "release", "publish"]}
    value["rows"][0] = {
        "id": "T2D-1-documented-domain-behavior",
        "actions": ["submit (car 1)", "submit (length \"abc\")"],
        "expect": ["nil (documented v2.0 inconsistency)",
                   "domain error names string-length, then one live prompt"]}
    collection = value["rows"][2]
    collection["actions"].insert(1,
        "during ordinary passes, judge each physical key against v1.9 feel")
    collection["expect"].insert(0,
        "single-key echo feels like v1.9; any visible latency is red")
    value["rows"][3]["actions"].append(
        "submit (>= nil 32) and observe recovery")
    value["rows"][3]["expect"].append(
        "A0 error recovery returns to one live prompt practically immediately")
    value["rows"][4]["D5"]["projection_only"] = {
        "free_symbol_slots": 71, "free_name_bytes": 1068}
    return value


def inherited_check(*, source_only: bool = False) -> None:
    value, session = load(RECEIPT), load(SESSION)
    readback = value["packed_readback"]
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and readback["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and readback["closure"]["object_count"] ==
                EXPECTED_CLOSURE_OBJECTS
            and readback["closure"]["call_site_count"] ==
                EXPECTED_CLOSURE_CALL_SITES
            and readback["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and readback["generation_coherence"]["object_count"] ==
                EXPECTED_COHERENCE_OBJECTS
            and readback["delivered_key_sources"]["armed_sink_set"] == [
                "c2_kernal_input_take"]
            and readback["delivered_host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and value["composed_bank2"]["static_plane"]
                ["largest_contiguous_hole"]["bytes"] ==
                EXPECTED_LARGEST_HOLE
            and session["status"] ==
                "ready-owner-v2.0-block3-hot-path-repair-contact"
            and len(session["rows"]) == 5
            and session["choreography"]["optional_library_media"] == "none"
            and session["rows"][2]["expect"][0] ==
                "single-key echo feels like v1.9; any visible latency is red",
            "repair media/session semantics drift")
    require(bind(SESSION) == value["session"], "repair session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"prepared artifact identity drift: {row['path']}")
        require(BASE.BASE.packed_readback(
                ROOT / value["media"]["product"]["path"])["status"] ==
                readback["status"],
                "packed readback proof no longer reproduces")
    print("v2.0 Block3 repair packed media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def configure() -> None:
    # The shared media builder materializes its closure adapter before its
    # later configure_candidate hook.  Bind the live repair population first
    # so that this early consumer cannot resolve the historical pricing root.
    REPAIR.configure()
    values = {
        "DESC": REPAIR, "ProductCard": ProductCard, "Adapter": Adapter,
        "BUILD": BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "PRODUCT_REMOTE": PRODUCT_REMOTE,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": EXPECTED, "STATUS": STATUS, "FORMAT": FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT,
        "PLAN": PLAN, "PLAN_HEADER": PLAN_HEADER,
    }
    for name, value in values.items():
        setattr(BASE, name, value)
    BASE.accepted_pair = accepted_pair
    BASE.authority = authority
    BASE.plan_section = plan_section
    BASE.session_config = session_config
    BASE.inherited_check = inherited_check
    delivery = BASE.BASE
    delivery.EXPECTED_CLOSURE_OBJECTS = EXPECTED_CLOSURE_OBJECTS
    delivery.EXPECTED_CLOSURE_CALL_SITES = EXPECTED_CLOSURE_CALL_SITES
    delivery.EXPECTED_COHERENCE_OBJECTS = EXPECTED_COHERENCE_OBJECTS
    delivery.EXPECTED_LARGEST_HOLE = EXPECTED_LARGEST_HOLE
    BASE.configure()


def build() -> None:
    configure()
    BASE.build()


def check(*, source_only: bool = False) -> None:
    configure()
    inherited_check(source_only=source_only)
    value, session = load(RECEIPT), load(SESSION)
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and session["format"] == SESSION_FORMAT
            and session["rows"][4]["D5"]["projection_only"] == {
                "free_symbol_slots": 71, "free_name_bytes": 1068},
            "repair media/session successor drift")
    print("v2.0 Block3 hot-path repair device media: CHECK PASS "
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
        raise BASE.BASE.M.BASE.MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 Block3 repair device media: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
