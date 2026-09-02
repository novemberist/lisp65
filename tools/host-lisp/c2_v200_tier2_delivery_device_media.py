#!/usr/bin/env python3
"""Pack artifact-only Tier-2 + resident-delivery media and bind its session."""

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
import c2_v200_block3_return_device_media as M  # noqa: E402
import c2_v200_interactive_delivery_chain_pricing as PRICE  # noqa: E402
import c2_v200_interactive_delivery_chain_product_card as CARD  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — Tier 2 plus delivery-chain media — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-tier2-delivery-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0-tier2-delivery-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-tier2-delivery-device-session.json"
PRODUCT_REMOTE = "V20T2D.D81"
PRODUCT_ID = 0x702C5BD3
PLANE_BYTES = 53820
EXPECTED = {
    "PRG": (41811,
        "a5f39b5d71977c6fd59a438a0618ea69003e34f88c1515ae291944f342fd4a90"),
    "ELF": (635172,
        "f9654bdddf2e717805651d7194f5e4a1e32d471399b26362fbc4fdae95cb4f55"),
}
STATUS = "PASS: V2.0 TIER2 DELIVERY DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-tier2-delivery-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-tier2-delivery-device-session-v1"
PRODUCT_KEYS = PRICE.PRODUCT_KEYS
EXPECTED_CLOSURE_OBJECTS = 797
EXPECTED_CLOSURE_CALL_SITES = 2686
EXPECTED_COHERENCE_OBJECTS = 422
EXPECTED_LARGEST_HOLE = 9846


class Adapter:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    PRICING_RECEIPT = PRICE.RECEIPT
    PRICE = PRICE


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
    require(text.count(PLAN_HEADER) == 1, "device-media review authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("artifact-only media", "actually packed medium",
                  "boot surface without optional libraries", "553/179/102"):
        require(token in folded, f"device-media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"delivery {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    pair = accepted_pair()
    require(receipt["status"] == CARD.STATUS
            and receipt["media_authorized"] is False
            and receipt["media_condition"] ==
                "independent review first; any medium must rerun closure and generation coherence over packed readback bytes"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(CARD.LINK.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.LINK.BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
            "delivery product card is not independently media-ready")
    final = receipt["final_product"]
    require(final["Tier_2_contract_counts"] == {
                "error-raised": 553, "documented-permissive": 179,
                "silently-wrong": 102}
            and final["combined_responsiveness"]["margin_percent"] >= 25.0,
            "reviewed combined-world facts drift")
    return {"product_card": bind(CARD.RECEIPT),
        "scope": bind(CARD.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(CARD.LINK.BASE.ACCEPTANCE_RESULT),
        "review_authority": plan_section(),
        "right": "artifact-only media; zero WPLTO and product links"}


def configure_paths() -> None:
    M.CARD = Adapter
    M.CARD_RECEIPT = CARD.RECEIPT
    M.SOURCE_WPLTO = CARD.WPLTO
    M.SOURCE_STATIC = CARD.PLANE
    M.BUILD = BUILD; M.WPLTO = WPLTO; M.STATIC = STATIC
    M.TARGET = TARGET; M.SHARED = SHARED; M.RECEIPT = RECEIPT
    M.SESSION = SESSION
    M.SCOPE = CARD.LINK.BASE.SCOPE_RESULT
    M.ACCEPTANCE = CARD.LINK.BASE.ACCEPTANCE_RESULT
    M.PRODUCT_REMOTE = PRODUCT_REMOTE; M.PRODUCT_ID = PRODUCT_ID
    M.PLANE_BYTES = PLANE_BYTES; M.EXPECTED = EXPECTED
    M.STATUS = STATUS; M.FORMAT = FORMAT; M.SESSION_FORMAT = SESSION_FORMAT
    M.PRODUCT_KEYS = PRODUCT_KEYS
    M.authority = authority
    M.accepted_pair = accepted_pair
    M.configure_paths()


def configure_candidate() -> None:
    CARD.patch_link_stack()
    # Reconstruct the same feature-owned native world that produced the
    # frozen pair.  Path rebinding alone leaves the historical Completion
    # stack in its capture-disabled import state and would materialize a
    # zero-byte E000 geometry.
    CARD.setup_link_world()
    M.BASE.MEDIA.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    M.BASE.MEDIA.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    M.BASE.MEDIA.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(M.BASE.MEDIA.PRODUCT.VERIFIER_BINDING_SECTION)
    require(section.bytes == 40, "delivery verifier-binding size drift")
    M.BASE.MEDIA.PRODUCT.VERIFIER_BINDING_BASE = section.address
    M.BASE.MEDIA.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    configure_paths()


def packed_readback(product: Path) -> dict[str, Any]:
    visible = D81.visible_files(product.read_bytes())
    require({b"CODE.BIN", b"C2D.BIN", b"SHELF.BIN"} <= set(visible),
            "packed delivery medium lacks a product member")
    packed_code = visible[b"CODE.BIN"]
    source_product = STATIC / "product/substitution-artifacts.json"
    product_dir = source_product.parent
    lengths = [(product_dir / f"{key}.code.bin").stat().st_size
               for key in PRODUCT_KEYS]
    require(sum(lengths) == PLANE_BYTES and len(packed_code) == 65489,
            "packed delivery population drift")
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
                f"packed delivery code differs from qualified image: {key}")
        (projection / f"{key}.code.bin").write_bytes(actual)
        shutil.copyfile(product_dir / f"{key}.c2i.bin",
                        projection / f"{key}.c2i.bin")
        slices.append({"key": key, "offset": offset, "bytes": length,
            "packed": memory_binding("CODE.BIN", actual),
            "qualified": bind(product_dir / f"{key}.code.bin")})
        packed_slices.append(actual)
        offset += length
    plane = (STATIC / "v6-semantics/bank2-static-code.bin").read_bytes()
    require(packed_code[:offset] == plane,
            "packed delivery prefix differs from qualified plane")
    closure = CLOSURE.derive(projection / source_product.name)
    CLOSURE.require_closed(closure)
    require(closure["object_count"] == EXPECTED_CLOSURE_OBJECTS
            and closure["call_site_count"] == EXPECTED_CLOSURE_CALL_SITES,
            "packed delivery closure population drift")
    coherence = COHERENCE.derive(
        STATIC / "stdlib-p0.manifest.json",
        product_dir / "stdlib-p0.code.bin", PRICE.STDLIB_SUITE,
        packed_slices[0])
    COHERENCE.require_coherent(coherence)
    require(coherence["object_count"] == EXPECTED_COHERENCE_OBJECTS
            and coherence["contract"]["caller"] == "%native-prompt"
            and coherence["contract"]["implementation"] == "%rl-screen-tail",
            "packed delivery generation contract drift")

    rejected: list[str] = []
    for name, raw, count in (
            ("packed-code-prefix-truncated", packed_code[:PLANE_BYTES - 1], 6),
            ("packed-component-omitted", packed_code, 5)):
        try:
            require(count == len(PRODUCT_KEYS) and raw[:PLANE_BYTES] == plane,
                    "packed readback no longer covers delivery population")
        except M.BASE.MediaError:
            rejected.append(name)
    require(len(rejected) == 2, "packed delivery mutation survived")
    final = load(CARD.RECEIPT)["final_product"]["packed_product"]
    require(final["key_sources"]["armed_sink_set"] == [
                "c2_kernal_input_take"]
            and final["host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94},
            "delivered input-consumer wall drift")
    return {"status":
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE",
        "medium": bind(product),
        "visible_members": sorted(name.decode("ascii") for name in visible),
        "packed_code": memory_binding("CODE.BIN", packed_code),
        "packed_c2d": memory_binding("C2D.BIN", visible[b"C2D.BIN"]),
        "packed_shelf": memory_binding("SHELF.BIN", visible[b"SHELF.BIN"]),
        "code_slices": slices, "closure": closure,
        "generation_coherence": coherence,
        "delivered_key_sources": final["key_sources"],
        "delivered_host_wall": final["host_wall"],
        "mutations_rejected": [*rejected, *CLOSURE.mutation_tests(),
            "mixed-object-generation", "surviving-public-queue-reader",
            "delivered-consumer-taken-zero"],
        "rule": ("closure and caller/implementation generation are derived "
                 "from CODE.BIN read back from the packed D81")}


def session_config(product: Path) -> dict[str, Any]:
    collection = {
        "controller":
            "(progn (setq s (read-line)) (print (string-length s)) (wait 16383))",
        "pattern": "01234567012345670123456701234567", "passes": 6,
        "pace": {"passes_1_to_2": "ordinary", "passes_3_to_6": "fast"},
        "delete_events_per_pass": 32, "final_text": "abcdefg",
        "numeric_oracle": 7, "nursery_cells": 192,
        "heap_cells_per_printable": 1, "printable_insertions": 199,
        "proof": "199 * 1 > 192; at least one collection while Capture is armed",
        "event_arithmetic": {"physical": 392, "printable": 199,
            "delete": 192, "return": 1, "counter_width_bits": 8,
            "wraps": 1, "expected_each_modulo_256": 136}}
    return {"format": SESSION_FORMAT, "recorded_on": "2026-09-01",
        "status": "ready-owner-v2.0-tier2-delivery-contact",
        "claim_scope": {"accepts": [
            "Tier-2 car/cdr domain semantics",
            "resident matcher and blink on native line editor and IDE",
            "lossless delivered input across forced collection"],
            "excludes": ["Comfort", "release", "publish"]},
        "media": {"product": {**bind(product), "remote_name": PRODUCT_REMOTE}},
        "choreography": {"fresh_BASIC_first": True,
            "product_uploaded_and_read_back_before_boot": True,
            "optional_library_media": "none",
            "physical_owner_keyboard_only": True,
            "post_boot_automated_device_access": 0,
            "one_form_per_submission": True},
        "rows": [
            {"id": "T2-1-domain-semantics", "actions": [
                "submit (car 1)", "submit (car nil)",
                "submit (length \"abc\")"],
             "expect": ["type error then one prompt practically immediately",
                "nil", "domain error names string-length"]},
            {"id": "B3-2-matcher-and-blink", "actions": [
                "in the native line editor match parentheses and quotes; move the cursor away; test string/comment delimiters and over-close",
                "repeat matcher cases in IDE and scroll one long line",
                "observe idle blink on both surfaces; type during blink-off; place cursor on a matched delimiter"],
             "expect": ["one current match and no stale or false match",
                "IDE semantics match and never freeze",
                "typing restores cursor immediately and blink preserves the match attribute"]},
            {"id": "A-3-forced-collection", "actions": [
                "submit the collection controller and wait for its blank nested row",
                "six times type the 32-character pattern; after each pass delete four counted groups of eight until blank",
                "use ordinary pace for passes 1-2 and fast pace for passes 3-6",
                "type abcdefg, press Return and touch no further key",
                "stop once while wait is active and read BCFC..BCFF raw-first"],
             "collection": collection,
             "expect": ["every token is exact and deletion 32 empties each pass",
                "visible numeric oracle is 7",
                "raw=seen=stored=taken=136 (88 hex), all nonzero"]},
            {"id": "BOOT-4-no-optional-libraries", "actions": [
                "boot only the product medium", "confirm INIT.L65 absence path"],
             "expect": ["banner and live native lisp65> with matcher/blink",
                "no optional-library dependency and absent INIT.L65 is silent"]},
            {"id": "D5-5-performance", "actions": [
                "define (defun v20-perf-probe (x) (+ x 1))",
                "run the four bound time forms", "read final D5 counters"],
             "performance_forms": [
                {"form": "(time (car (cdr (list 1 2))))",
                 "max_frames": 2, "value": "2"},
                {"form": "(time ((lambda (x) (progn (rplaca x 9) x)) (list 1 2)))",
                 "max_frames": 2, "value": "(9 2)"},
                {"form": "(time (string-ref \"abc\" 1))",
                 "max_frames": 2, "value": "98"},
                {"form": "(time (v20-perf-probe 41))",
                 "max_frames": 2, "value": "42"}],
             "D5": {"minimum_free_symbol_slots": 32,
                "minimum_free_name_bytes": 384,
                "projection_only": {"free_symbol_slots": 72,
                    "free_name_bytes": 1077}},
             "expect": ["each performance form is at most two frames",
                "D5 is at least 32 slots and 384 name bytes"]}],
        "stopped_read": {"input_counters": {"address": "0xBCFC",
            "bytes": 4, "layout": ["raw", "seen", "stored", "taken"]}},
        "decision_table": {"all-five-groups-green":
                "Tier 2 and resident interactive delivery hardware-accepted",
            "daily-use-blocker":
                "at most one repair round for the affected block, otherwise descope",
            "rare-or-cosmetic": "Known Issue and v2.0 register row",
            "claim-expansion": "forbidden during device session"}}


_original_product_manifest = M.product_manifest


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = _original_product_manifest(completion)
    value["static_plane"]["status"] = "passed-v2.0-tier2-delivery-static-plane"
    M.BASE.MEDIA.CAN.MANIFEST.write_bytes(canonical(value))
    M.BASE.MEDIA.CAN.check()
    return value


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    require(plane["status"] == "passed-v2.0-tier2-delivery-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] ==
                EXPECTED_LARGEST_HOLE
            and plane["composed_owners"][-2]["bytes"] == 324
            and plane["composed_owners"][-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "delivery composed Bank-2 media drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
        "rule": "all shipped Bank-2 intervals are composed and disjoint"}


def finish(packed: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    M.MEDIA.check()
    product = M.MEDIA.PRODUCT_D81
    product_id, mounted_c2d = M.BASE.MEDIA.PREP.PAIR.product_world(product)
    require(product_id == PRODUCT_ID, "packed medium carries another world")
    readback = packed_readback(product)
    session = session_config(product)
    M.BASE.write(SESSION, session)
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "accepted_pair": accepted_pair(),
        "completion": bind(M.BASE.MEDIA.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(M.MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(M.MEDIA.WORK_D81)},
        "readback": "passed-visible-file-and-role-identity-closure",
        "mounted_product_world": {"product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_artifact_closure": {
            "stager_gate": packed["stager"]["gate"],
            "product_entries": packed["media"]["product"]["entries"],
            "artifact_count": packed["artifact_count"]},
        "packed_readback": readback,
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "session": bind(SESSION), "claim_limit": session["claim_scope"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "device_contacts": 0}}
    M.BASE.write(RECEIPT, value)
    return value


def patch() -> None:
    configure_paths()
    M.configure_candidate = configure_candidate
    M.packed_readback_closure = packed_readback
    M.session_config = session_config
    M.product_manifest = product_manifest
    M.static_plane_gate = static_plane_gate
    M.finish = finish
    M.check = check


def check(*, source_only: bool = False) -> None:
    patch()
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
                "ready-owner-v2.0-tier2-delivery-contact"
            and len(session["rows"]) == 5
            and session["choreography"]["optional_library_media"] == "none",
            "Tier-2 delivery media/session semantics drift")
    require(bind(SESSION) == value["session"], "session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(bind(ROOT / row["path"]) == row,
                    f"prepared artifact identity drift: {row['path']}")
        require(packed_readback(ROOT / value["media"]["product"]["path"])
                ["status"] == readback["status"],
                "packed readback proof no longer reproduces")
    print("v2.0 Tier2 delivery device media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def build() -> None:
    patch()
    M.build()


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "source-check":
        check(source_only=True)
    else:
        raise M.BASE.MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 Tier2 delivery device media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
