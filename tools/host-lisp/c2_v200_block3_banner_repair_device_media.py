#!/usr/bin/env python3
"""Pack repaired Block-3 media and prove closure plus generation coherence."""

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
import c2_packed_object_generation_coherence as COHERENCE  # noqa: E402
import c2_v200_block3_banner_repair_product_card as CARD  # noqa: E402
import c2_v200_block3_return_device_media as M  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Reviewer authorization — Block-3 banner repair product card — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-block3-banner-repair-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-device-media-receipt.json")
MEDIA_RED = ARCH / (
    "c2.3-v2.0-block3-banner-repair-device-media-coherence-red.json")
SESSION = ROOT / "config/c2-v200-block3-banner-repair-device-session.json"
PRODUCT_REMOTE = "V20B3R.D81"
PRODUCT_ID = 0x7B791204
PLANE_BYTES = 52537
EXPECTED = {
    "PRG": (41811,
        "89963ac6178dd752b7aef5b852a7518d06f7eb576234e2811455999fa4b0c995"),
    "ELF": (636152,
        "75f5700343d27dc68a4e46e67c663d75ee148b3cb37a1a805cea093f49442a83"),
}
STATUS = "PASS: V2.0 BLOCK3 BANNER REPAIR DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-block3-banner-repair-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-block3-banner-repair-device-session-v1"
PRODUCT_KEYS = M.PRODUCT_KEYS


def require(value: bool, message: str) -> None:
    if not value:
        raise M.BASE.MediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    return M.load(path)


def bind(path: Path) -> dict[str, Any]:
    return M.bind(path)


def memory_binding(name: str, raw: bytes) -> dict[str, Any]:
    return {"medium_member": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "repair media authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("replacement media may be packed only",
                  "closure and coherence both run again",
                  "hardware acceptance red"):
        require(token in folded, f"repair media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    pair = M.accepted_pair()
    require(receipt["status"] == CARD.STATUS
            and receipt["media_authorized"] is True
            and receipt["media_condition"] ==
                "closure and generation coherence must both be rederived from packed D81 readback bytes"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(CARD.R1.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.R1.BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
            "repair product card is not media-ready")
    return {"product_card": bind(CARD.RECEIPT),
        "scope": bind(CARD.R1.BASE.SCOPE_RESULT),
        "acceptance": bind(CARD.R1.BASE.ACCEPTANCE_RESULT),
        "review_authority": plan_section(),
        "right": "one artifact-only replacement medium; zero WPLTO and links"}


def packed_readback_closure(product: Path) -> dict[str, Any]:
    visible = D81.visible_files(product.read_bytes())
    require({b"CODE.BIN", b"C2D.BIN", b"SHELF.BIN"} <= set(visible),
            "packed repair medium lacks a closure-bearing member")
    packed_code = visible[b"CODE.BIN"]
    source_product = STATIC / "product/substitution-artifacts.json"
    product_dir = source_product.parent
    lengths = [(product_dir / f"{key}.code.bin").stat().st_size
               for key in PRODUCT_KEYS]
    require(sum(lengths) == PLANE_BYTES and len(packed_code) == 65489,
            "packed repair code population drift")
    projection = BUILD / "packed-readback-closure/product"
    if projection.parent.exists():
        shutil.rmtree(projection.parent)
    projection.mkdir(parents=True)
    shutil.copyfile(source_product, projection / source_product.name)
    offset = 0
    slices: list[dict[str, Any]] = []
    packed_slices: list[bytes] = []
    for key, length in zip(PRODUCT_KEYS, lengths):
        actual = packed_code[offset:offset + length]
        expected = (product_dir / f"{key}.code.bin").read_bytes()
        require(actual == expected,
                f"packed repair code differs from qualified image: {key}")
        (projection / f"{key}.code.bin").write_bytes(actual)
        shutil.copyfile(product_dir / f"{key}.c2i.bin",
                        projection / f"{key}.c2i.bin")
        slices.append({"key": key, "offset": offset, "bytes": length,
            "packed": memory_binding("CODE.BIN", actual),
            "qualified": bind(product_dir / f"{key}.code.bin")})
        packed_slices.append(actual)
        offset += length
    require(packed_code[:offset] ==
            (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes(),
            "packed repair prefix differs from qualified plane")
    closure = CLOSURE.derive(projection / source_product.name)
    CLOSURE.require_closed(closure)
    require(closure["object_count"] == 792
            and closure["call_site_count"] == 2651,
            "packed repair closure population drift")
    coherence = COHERENCE.derive(
        STATIC / "stdlib-p0.manifest.json",
        product_dir / "stdlib-p0.code.bin",
        STATIC / "v2.0-block3-stdlib-suite.json",
        packed_slices[0])
    COHERENCE.require_coherent(coherence)
    sharp = COHERENCE.sharp_mutation(
        STATIC / "stdlib-p0.manifest.json",
        STATIC / "stdlib-p0.blob.bin", CARD.REPAIR.BROKEN_MANIFEST)

    def validate(raw: bytes, count: int) -> None:
        require(count == len(PRODUCT_KEYS) and raw[:PLANE_BYTES] ==
                (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes(),
                "packed readback no longer covers repair population")

    rejected = []
    for name, raw, count in (
            ("packed-code-prefix-truncated", packed_code[:PLANE_BYTES - 1], 6),
            ("packed-component-omitted", packed_code, 5)):
        try:
            validate(raw, count)
        except M.BASE.MediaError:
            rejected.append(name)
    require(len(rejected) == 2,
            "packed repair population mutation survived")
    positive = load(PRICE_RECEIPT())["closure_positive_control"]
    failure = positive["failure"]
    require(failure["caller"] == "%repl-step"
            and failure["target"] == "%ide-line-net-depth"
            and failure["classification"] == "anonymous-only",
            "packed repair closure positive control drift")
    return {"status":
                "PASS: CLOSURE AND GENERATION COHERENCE FROM PACKED D81 BYTES",
        "medium": bind(product),
        "visible_members": sorted(name.decode("ascii") for name in visible),
        "packed_code": memory_binding("CODE.BIN", packed_code),
        "packed_c2d": memory_binding("C2D.BIN", visible[b"C2D.BIN"]),
        "packed_shelf": memory_binding("SHELF.BIN", visible[b"SHELF.BIN"]),
        "code_slices": slices, "closure": closure,
        "generation_coherence": coherence,
        "generation_sharp_mutation": sharp,
        "closure_positive_control": positive,
        "mutations_rejected": [*rejected, *CLOSURE.mutation_tests(),
            *sharp["mutations_rejected"]],
        "rule": ("delivered CODE.BIN is split into the six real images; "
                 "existence and caller/implementation generation are distinct")}


def PRICE_RECEIPT() -> Path:
    return CARD.PRICE.RECEIPT


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    require(plane["status"] == "passed-v2.0-block3-return-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] == 11129
            and plane["composed_owners"][-2]["bytes"] == 324
            and plane["composed_owners"][-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "repair composed Bank-2 media drift")
    return {"manifest": bind(path), "static_plane": plane,
            "artifact": row,
            "rule": "all shipped Bank-2 intervals are composed and disjoint"}


def session_config(product: Path) -> dict[str, Any]:
    return {"format": SESSION_FORMAT, "recorded_on": "2026-09-01",
        "status": "ready-owner-v2.0-block3-banner-repair-contact",
        "claim_scope": {"accepts": [
            "Block-3 repaired display, matcher and blink on line editor and IDE"],
            "excludes": ["Comfort", "v2.1 Comfort return", "release", "publish"]},
        "media": {"product": {**bind(product), "remote_name": PRODUCT_REMOTE}},
        "choreography": {"fresh_BASIC_first": True,
            "product_uploaded_and_read_back_before_boot": True,
            "optional_library_media": "none",
            "physical_owner_keyboard_only": True,
            "post_boot_automated_device_access": 0,
            "one_form_per_submission": True},
        "rows": [
            {"id": "B3-0-display-repair",
             "actions": ["boot to banner", "wait for native prompt"],
             "expect": ("lisp65> and one active cursor visible on the same "
                        "bottom editor row; no banner-only stall")},
            {"id": "B3-1-line-editor-matcher", "actions": [
                "type and navigate across matching parentheses and quotes",
                "move away and verify old highlight disappears",
                "place delimiters inside strings/comments", "type over-close"],
             "expect": ("one current match; no stale/string/comment/over-close "
                        "false match")},
            {"id": "B3-2-IDE-matcher", "actions": [
                "repeat matcher cases in IDE", "scroll one long line"],
             "expect": "same matching semantics and no freeze"},
            {"id": "B3-3-blink", "actions": [
                "observe idle cursor on both surfaces", "type during blink-off",
                "place cursor on matched delimiter"],
             "expect": ("cursor blinks; typing restores visibility; blink does "
                        "not erase match attribute")},
            {"id": "B3-4-responsiveness-D5", "actions": [
                "type normally and rapidly on both surfaces",
                "run final loaded-configuration D5 probe"],
             "expect": ("no perceptible regression; D5 at least 32 slots and "
                        "384 name bytes")},
        ],
        "decision_table": {"all-five-groups-green":
                "Block 3 hardware-accepted",
            "daily-use-blocker": "Block 3 descoped; repair round exhausted",
            "rare-or-cosmetic": "Known Issue and v2.0 register row",
            "claim-expansion": "forbidden during the device session"}}


def check(*, source_only: bool = False) -> None:
    patch()
    M.configure_paths()
    value, session = load(RECEIPT), load(SESSION)
    packed = value["packed_transitive_closure"]
    require(value["status"] == STATUS
            and value["accepted_pair"] == M.accepted_pair()
            and packed["status"] ==
                "PASS: CLOSURE AND GENERATION COHERENCE FROM PACKED D81 BYTES"
            and packed["closure"]["object_count"] == 792
            and packed["closure"]["call_site_count"] == 2651
            and packed["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and packed["generation_sharp_mutation"]["status"] ==
                "PASS: BANNER-ONLY MIXED GENERATION REJECTED"
            and value["composed_bank2"]["static_plane"]
                ["largest_contiguous_hole"]["bytes"] == 11129
            and session["status"] ==
                "ready-owner-v2.0-block3-banner-repair-contact"
            and len(session["rows"]) == 5
            and session["decision_table"]["daily-use-blocker"].startswith(
                "Block 3 descoped"),
            "repair device media/session semantics drift")
    require(bind(SESSION) == value["session"], "repair session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"repair media identity drift: {row['path']}")
        require(packed_readback_closure(
            ROOT / value["media"]["product"]["path"])["status"] ==
                packed["status"],
            "repair packed readback no longer reproduces")
    print("v2.0 Block3 banner repair media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def patch() -> None:
    CARD.patch_r1()
    CARD.configure = CARD.patch_r1
    M.CARD = CARD; M.CARD_RECEIPT = CARD.RECEIPT
    M.SOURCE_WPLTO = CARD.WPLTO; M.SOURCE_STATIC = CARD.PLANE
    M.BUILD = BUILD; M.WPLTO = WPLTO; M.STATIC = STATIC
    M.TARGET = TARGET; M.SHARED = SHARED; M.RECEIPT = RECEIPT
    M.SESSION = SESSION; M.SCOPE = CARD.R1.BASE.SCOPE_RESULT
    M.ACCEPTANCE = CARD.R1.BASE.ACCEPTANCE_RESULT
    M.PRODUCT_REMOTE = PRODUCT_REMOTE; M.PRODUCT_ID = PRODUCT_ID
    M.PLANE_BYTES = PLANE_BYTES; M.EXPECTED = EXPECTED
    M.STATUS = STATUS; M.FORMAT = FORMAT; M.SESSION_FORMAT = SESSION_FORMAT
    M.authority = authority
    M.packed_readback_closure = packed_readback_closure
    M.static_plane_gate = static_plane_gate
    M.session_config = session_config
    M.check = check


def build() -> None:
    patch()
    require(MEDIA_RED.is_file(),
            "repair media coherence conversion is not sealed")
    M.build()


def record_media_red() -> None:
    patch()
    product = SHARED / "lisp65-product.d81"
    require(product.is_file() and not RECEIPT.exists()
            and not MEDIA_RED.exists(), "repair media-red lifecycle drift")
    visible = D81.visible_files(product.read_bytes())
    packed = visible[b"CODE.BIN"][:PLANE_BYTES]
    materialized = (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes()
    product_code = (STATIC / "product/stdlib-p0.code.bin").read_bytes()
    raw_blob = (STATIC / "stdlib-p0.blob.bin").read_bytes()
    stdlib_packed = packed[:len(product_code)]
    differences = [index for index, (left, right) in
                   enumerate(zip(raw_blob, product_code)) if left != right]
    require(packed == materialized and stdlib_packed == product_code
            and len(raw_blob) == len(product_code) == 21553
            and len(differences) == 1642,
            "repair media coherence red attribution drift")
    value = {"format": FORMAT + "-coherence-red",
        "recorded_on": "2026-09-01",
        "status": "CHECKER-WORLD RED: RAW BLOB IS NOT PACKED GENERATION",
        "product_card": bind(CARD.RECEIPT), "medium": bind(product),
        "observed_red": "packed-blob-differs-from-materialized-generation",
        "mechanism": ("the first coherence gate compared delivered CODE.BIN "
            "with the compiler blob; product materialization lawfully rewrites "
            "1,642 bytes before composing stdlib-p0.code.bin"),
        "raw_compiler_blob": bind(STATIC / "stdlib-p0.blob.bin"),
        "materialized_product_code": bind(
            STATIC / "product/stdlib-p0.code.bin"),
        "packed_stdlib_slice": memory_binding("CODE.BIN", stdlib_packed),
        "different_offsets": {"count": len(differences),
            "sha256": hashlib.sha256(canonical(differences)).hexdigest(),
            "first": differences[:32]},
        "conversion": ("source cohort remains bound by suite+manifest; packed "
            "object bytes bind to the manifest-owned materialized product code"),
        "accounting": {"WPLTO_attempts": 0, "product_link_attempts": 0,
            "product_media_attempts": 1, "material_product_D81s": 1,
            "material_work_D81s": 1, "accepted_media_receipts": 0,
            "device_contacts": 0},
        "next": "read-only finish over the existing D81"}
    MEDIA_RED.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair media: COHERENCE RED FROZEN device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "record-media-red":
        record_media_red()
    elif action == "check":
        check()
    elif action == "source-check":
        check(source_only=True)
    else:
        raise M.BASE.MediaError("usage: build|record-media-red|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 Block3 banner repair media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
