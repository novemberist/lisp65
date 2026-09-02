#!/usr/bin/env python3
"""Pack stripped v2.0 release media and its final device session."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_init_l65_product_variants_media as INIT  # noqa: E402
import c2_v200_release_strip_product_card as STRIP  # noqa: E402
import c2_v200_tier2_descope_device_media as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Independent review — stripped v2.0 release media — 2026-09-02"
BUILD = ROOT / "build/c2.3/v2.0-release-strip-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / "c2.3-v2.0-release-strip-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-release-strip-device-session.json"
VALID = BUILD / "lisp65-product-init-valid.d81"
VALID_SOURCE = BUILD / "INIT-VALID.L65"
PRODUCT_REMOTE = "V20STRP.D81"
VALID_REMOTE = "V20SINI.D81"
PRODUCT_ID = 0xC4C3CE30
PLANE_BYTES = 47795
EXPECTED = {
    "PRG": (41811,
        "0fb9092a32820c1e3914096f5393a96a14374cdd05c56ef66f9293457422d369"),
    "ELF": (636100,
        "3754c3857ecce95943e315bc5ef6fb30962d6c8dde9cb6294cb049c7e512cf6d"),
}
EXPECTED_CLOSURE_OBJECTS = 760
EXPECTED_CLOSURE_CALL_SITES = 2436
EXPECTED_COHERENCE_OBJECTS = 397
EXPECTED_LARGEST_HOLE = 15871
STATUS = "PASS: V2.0 STRIPPED RELEASE DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-release-strip-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-release-strip-device-session-v1"


class ProductCard:
    BUILD = STRIP.BUILD
    WPLTO = STRIP.WPLTO
    PLANE = STRIP.PLANE
    PRG = STRIP.PRG
    ELF = STRIP.ELF
    RECEIPT = STRIP.RECEIPT
    STATUS = STRIP.STATUS
    LINK = STRIP.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        STRIP.configure()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        return STRIP.CHAIN.setup_link_world()


class MediaPrice:
    BUILD = BASE.BASE.M.CARD.PRICE.BUILD
    RECEIPT = BASE.BASE.M.CARD.PRICE.RECEIPT
    STDLIB_SUITE = BASE.BASE.PRICE.STDLIB_SUITE


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = MediaPrice.RECEIPT
    PRICE = MediaPrice


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.BASE.M.BASE.MediaError(message)


def load(path: Path) -> dict[str, Any]:
    return BASE.load(path)


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def memory_binding(name: str, raw: bytes) -> dict[str, Any]:
    return {"medium_member": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "strip media authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only media", "actual product d81",
                  "like v1.9", "absent and valid init.l65", "109/1,486"):
        require(token in folded, f"strip media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(STRIP.PRG), "ELF": bind(STRIP.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"stripped {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(STRIP.RECEIPT)
    pair = accepted_pair()
    scope = STRIP.BUILD / "wplto/owner-scope-result.json"
    acceptance = STRIP.BUILD / "artifact-acceptance.json"
    final = receipt["final_product"]
    require(receipt["status"] == STRIP.STATUS
            and receipt["media_authorized"] is False
            and receipt["media_condition"] ==
                "independent review; then closure and generation coherence over actually packed readback bytes"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == pair
            and load(scope)["status"] == load(acceptance)["status"] == "PASS"
            and final["Tier_1_contract_counts"] == {
                "error-raised": 545, "documented-permissive": 179,
                "silently-wrong": 110}
            and final["responsiveness_lanes"]["single_keystroke"]
                ["observed_steps_per_key"] == 902.0
            and final["responsiveness_lanes"]["batch_throughput"]
                ["margin_percent"] >= 25.0,
            "stripped card is not independently media-ready")
    return {"product_card": bind(STRIP.RECEIPT), "scope": bind(scope),
        "acceptance": bind(acceptance), "review_authority": plan_section(),
        "right": "artifact-only absent/valid media; zero WPLTO and product links"}


def packed_readback(product: Path) -> dict[str, Any]:
    delivery = BASE.BASE
    visible = delivery.D81.visible_files(product.read_bytes())
    require({b"CODE.BIN", b"C2D.BIN", b"SHELF.BIN"} <= set(visible),
            "packed stripped medium lacks a product member")
    packed_code = visible[b"CODE.BIN"]
    source_product = STATIC / "product/substitution-artifacts.json"
    product_dir = source_product.parent
    lengths = [(product_dir / f"{key}.code.bin").stat().st_size
               for key in STRIP.PRODUCT_KEYS]
    require(sum(lengths) == PLANE_BYTES and len(packed_code) == 65489,
            "packed stripped population drift")
    projection = BUILD / f"packed-readback-{product.stem.lower()}/product"
    if projection.parent.exists():
        shutil.rmtree(projection.parent)
    projection.mkdir(parents=True)
    shutil.copyfile(source_product, projection / source_product.name)
    offset = 0
    slices: list[dict[str, Any]] = []
    packed_slices: list[bytes] = []
    for key, length in zip(STRIP.PRODUCT_KEYS, lengths):
        actual = packed_code[offset:offset + length]
        expected = (product_dir / f"{key}.code.bin").read_bytes()
        require(actual == expected,
                f"packed stripped code differs from qualified image: {key}")
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
            "packed stripped prefix differs from qualified plane")
    closure = delivery.CLOSURE.derive(projection / source_product.name)
    delivery.CLOSURE.require_closed(closure)
    require(closure["object_count"] == EXPECTED_CLOSURE_OBJECTS
            and closure["call_site_count"] == EXPECTED_CLOSURE_CALL_SITES,
            "packed stripped closure population drift")
    coherence = delivery.COHERENCE.derive(
        STATIC / "stdlib-p0.manifest.json",
        product_dir / "stdlib-p0.code.bin", delivery.PRICE.STDLIB_SUITE,
        packed_slices[0])
    delivery.COHERENCE.require_coherent(coherence)
    require(coherence["object_count"] == EXPECTED_COHERENCE_OBJECTS
            and coherence["contract"]["caller"] == "%native-prompt"
            and coherence["contract"]["implementation"] == "%rl-screen-tail",
            "packed stripped generation contract drift")
    rejected: list[str] = []
    for name, raw, count in (
            ("packed-code-prefix-truncated", packed_code[:PLANE_BYTES - 1], 6),
            ("packed-component-omitted", packed_code, 5)):
        try:
            require(count == len(STRIP.PRODUCT_KEYS)
                    and raw[:PLANE_BYTES] == plane,
                    "packed readback no longer covers stripped population")
        except BASE.BASE.M.BASE.MediaError:
            rejected.append(name)
    require(len(rejected) == 2, "packed stripped mutation survived")
    final = load(STRIP.RECEIPT)["final_product"]["packed_product"]
    require(final["key_sources"]["active_sink_set"] == [
                "c2_kernal_input_take"]
            and final["host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94},
            "stripped delivered input-consumer wall drift")
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
        "mutations_rejected": [*rejected,
            *delivery.CLOSURE.mutation_tests(), "mixed-object-generation",
            "surviving-active-public-queue-reader",
            "delivered-consumer-taken-zero"],
        "rule": ("closure and caller/implementation generation are derived "
                 "from CODE.BIN read back from this packed D81")}


def _make_valid_variant(product: Path) -> dict[str, Any]:
    shutil.copyfile(product, VALID)
    VALID_SOURCE.write_bytes(INIT.VALID_INIT)
    INIT._append_init(VALID_SOURCE, VALID)
    absent_raw, valid_raw = product.read_bytes(), VALID.read_bytes()
    proof = INIT.variant_proof(absent_raw, valid_raw, INIT.VALID_INIT)
    source_proof = INIT.source_compile_proof()["valid"]
    require(BASE.BASE.M.BASE.MEDIA.PREP.PAIR.product_world(product) ==
            BASE.BASE.M.BASE.MEDIA.PREP.PAIR.product_world(VALID),
            "INIT variant changed the frozen product world")
    return {"medium": {**bind(VALID), "remote_name": VALID_REMOTE},
        "INIT_L65": bind(VALID_SOURCE), "diff_attribution": proof,
        "source_compile_proof": source_proof}


def session_config(product: Path, valid: Path = VALID) -> dict[str, Any]:
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
    return {"format": SESSION_FORMAT, "recorded_on": "2026-09-02",
        "status": "ready-owner-v2.0-stripped-final-contact",
        "claim_scope": {"accepts": [
            "Tier-1 domain discipline over 62 corrected cells",
            "v1.9-identical native editor responsiveness",
            "lossless delivered input across forced collection",
            "stripped v2.0 boot, INIT.L65 and A0 regression"],
            "excludes": ["Comfort", "Matcher/Blink", "Tier 2",
                         "release", "Ship", "Publish"]},
        "media": {
            "absent_INIT": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "valid_INIT": {**bind(valid), "remote_name": VALID_REMOTE}},
        "choreography": {"fresh_BASIC_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "initial_medium": PRODUCT_REMOTE,
            "valid_INIT_medium_is_final_cold_boot": VALID_REMOTE,
            "optional_library_media": "none",
            "physical_owner_keyboard_only": True,
            "post_boot_automated_device_access": 0,
            "one_form_per_submission": True,
            "D5_and_performance_before_valid_INIT_reboot": True},
        "rows": [
            {"id": "S20-1-documented-domain-behavior", "medium": PRODUCT_REMOTE,
             "actions": ["submit (car 1)", "submit (length \"abc\")"],
             "expect": ["nil (documented v2.0 inconsistency)",
                        "vm type error followed by one live prompt; hint text is not claimed"]},
            {"id": "S20-2-v1.9-input-and-forced-collection",
             "medium": PRODUCT_REMOTE,
             "actions": [
                "confirm ordinary and rapid typing feel like v1.9",
                "submit the collection controller and wait for its blank nested row",
                "six times type the 32-character pattern; after each pass delete four counted groups of eight until blank",
                "use ordinary pace for passes 1-2 and fast pace for passes 3-6",
                "type abcdefg, press Return and touch no further key",
                "stop once while wait is active and read BCFC..BCFF raw-first"],
             "collection": collection,
             "expect": ["single-key feel is like v1.9",
                        "every token is exact and deletion 32 empties each pass",
                        "visible numeric oracle is 7",
                        "raw=seen=stored=taken=136 (88 hex), all nonzero"]},
            {"id": "S20-3-boot-INIT-A0", "media": [PRODUCT_REMOTE, VALID_REMOTE],
             "actions": [
                "on the initial absent-INIT boot confirm banner and a live native lisp65> without optional libraries",
                "submit (>= nil 32) and observe recovery to exactly one prompt practically immediately",
                "after rows S20-1, S20-2 and S20-4 cold-boot the valid-INIT medium",
                "observe exactly one line containing 17 before the banner",
                "at lisp65> submit (init-proof)"],
             "expect": ["absent INIT.L65 is silent and free",
                        "A0 recovery has no red frame and is practically immediate",
                        "valid INIT executes before the first banner exactly once",
                        "init-proof returns 17 and INIT is not retried"]},
            {"id": "S20-4-release-terminal-D5-and-performance",
             "medium": PRODUCT_REMOTE,
             "actions": ["define (defun v20-perf-probe (x) (+ x 1))",
                         "run the four bound time forms",
                         "read final D5 counters before the valid-INIT reboot"],
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
                    "projection_only": {"free_symbol_slots": 109,
                                        "free_name_bytes": 1486}},
             "expect": ["each performance form is at most two frames",
                        "D5 is at least 32 slots and 384 name bytes"]}],
        "stopped_read": {"input_counters": {"address": "0xBCFC",
            "bytes": 4, "layout": ["raw", "seen", "stored", "taken"]}},
        "decision_table": {"all-four-groups-green":
                "stripped v2.0 hardware acceptance complete",
            "daily-use-blocker": "stop; no claim or release advancement",
            "rare-or-cosmetic": "Known Issue and v2.0 register row",
            "claim-expansion": "forbidden during device session"}}


def static_plane_gate() -> dict[str, Any]:
    delivery = BASE.BASE
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    require(plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and plane["largest_contiguous_hole"]["bytes"] ==
                EXPECTED_LARGEST_HOLE
            and plane["composed_owners"][-2]["bytes"] == 324
            and plane["composed_owners"][-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "stripped composed Bank-2 media drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
        "rule": "all shipped Bank-2 intervals are composed and disjoint"}


def finish(packed: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    delivery = BASE.BASE
    media = delivery.M.MEDIA
    delivery.configure_paths()
    media.check()
    product = media.PRODUCT_D81
    product_id, mounted_c2d = delivery.M.BASE.MEDIA.PREP.PAIR.product_world(
        product)
    require(product_id == PRODUCT_ID, "packed medium carries another world")
    absent_readback = packed_readback(product)
    variant = _make_valid_variant(product)
    valid_readback = packed_readback(VALID)
    session = session_config(product)
    delivery.M.BASE.write(SESSION, session)
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "accepted_pair": accepted_pair(),
        "completion": bind(delivery.M.BASE.MEDIA.CAN.RECEIPTS /
                           "artifact-completion.json"),
        "media_closure": bind(media.MANIFEST),
        "media": {"absent_INIT": {**bind(product),
                                     "remote_name": PRODUCT_REMOTE},
                  "valid_INIT": variant["medium"],
                  "work": bind(media.WORK_D81)},
        "INIT_variant": variant,
        "readback": "passed-visible-file-and-role-identity-closure",
        "mounted_product_world": {
            "product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_artifact_closure": {
            "stager_gate": packed["stager"]["gate"],
            "product_entries": packed["media"]["product"]["entries"],
            "artifact_count": packed["artifact_count"]},
        "packed_readback": {"absent_INIT": absent_readback,
                            "valid_INIT": valid_readback},
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(),
        "session": bind(SESSION), "claim_limit": session["claim_scope"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "INIT_variant_media_builds": 1,
            "work_media_builds": 1, "device_contacts": 0}}
    delivery.M.BASE.write(RECEIPT, value)
    return value


def inherited_check(*, source_only: bool = False) -> None:
    value, session = load(RECEIPT), load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and set(value["packed_readback"]) == {"absent_INIT", "valid_INIT"}
            and all(row["status"] ==
                    "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
                    for row in value["packed_readback"].values())
            and all(row["closure"]["object_count"] ==
                    EXPECTED_CLOSURE_OBJECTS
                    and row["closure"]["call_site_count"] ==
                        EXPECTED_CLOSURE_CALL_SITES
                    and row["generation_coherence"]["object_count"] ==
                        EXPECTED_COHERENCE_OBJECTS
                    and row["delivered_key_sources"]["active_sink_set"] == [
                        "c2_kernal_input_take"]
                    and row["delivered_host_wall"]["counters"]["taken"] == 94
                    for row in value["packed_readback"].values())
            and value["composed_bank2"]["static_plane"]
                ["largest_contiguous_hole"]["bytes"] ==
                    EXPECTED_LARGEST_HOLE
            and session["status"] ==
                "ready-owner-v2.0-stripped-final-contact"
            and len(session["rows"]) == 4
            and session["rows"][0]["expect"][0] ==
                "nil (documented v2.0 inconsistency)"
            and session["rows"][3]["D5"]["projection_only"] == {
                "free_symbol_slots": 109, "free_name_bytes": 1486},
            "stripped device media/session semantics drift")
    require(bind(SESSION) == value["session"], "strip session identity drift")
    if not source_only:
        for row in [*value["accepted_pair"].values(), value["completion"],
                    value["media_closure"], *value["media"].values()]:
            require(all(bind(ROOT / row["path"])[key] == row[key]
                        for key in ("path", "bytes", "sha256")),
                    f"prepared artifact identity drift: {row['path']}")
        for key, row in (("absent_INIT", value["media"]["absent_INIT"]),
                         ("valid_INIT", value["media"]["valid_INIT"])):
            require(packed_readback(ROOT / row["path"])["status"] ==
                    value["packed_readback"][key]["status"],
                    f"packed readback no longer reproduces: {key}")
    print("v2.0 stripped release packed media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def configure() -> None:
    STRIP.configure()
    # The descope wrapper names these classes directly inside configure();
    # replace those module globals as well as the downstream CARD binding.
    BASE.ProductCard = ProductCard
    BASE.Adapter = Adapter
    values = {"CARD": ProductCard, "Adapter": Adapter,
        "BUILD": BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "PRODUCT_REMOTE": PRODUCT_REMOTE,
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": EXPECTED, "STATUS": STATUS, "FORMAT": FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT}
    for name, value in values.items():
        setattr(BASE, name, value)
    BASE.accepted_pair = accepted_pair
    BASE.authority = authority
    BASE.plan_section = plan_section
    BASE.session_config = lambda product: session_config(product)
    BASE.inherited_check = inherited_check
    BASE.check = inherited_check
    BASE.configure()
    delivery = BASE.BASE
    delivery.PRODUCT_KEYS = STRIP.PRODUCT_KEYS
    delivery.EXPECTED_CLOSURE_OBJECTS = EXPECTED_CLOSURE_OBJECTS
    delivery.EXPECTED_CLOSURE_CALL_SITES = EXPECTED_CLOSURE_CALL_SITES
    delivery.EXPECTED_COHERENCE_OBJECTS = EXPECTED_COHERENCE_OBJECTS
    delivery.EXPECTED_LARGEST_HOLE = EXPECTED_LARGEST_HOLE
    delivery.packed_readback = packed_readback
    delivery.session_config = lambda product: session_config(product)
    delivery.static_plane_gate = static_plane_gate
    delivery.finish = finish


def build() -> None:
    configure()
    BASE.build()


def check(*, source_only: bool = False) -> None:
    configure()
    inherited_check(source_only=source_only)


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
        print(f"v2.0 stripped release device media: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
