#!/usr/bin/env python3
"""Seal/check the owner-observed stripped v2.0 final device result."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Stripped v2.0 final device result — 2026-09-02"
MEDIA = ARCH / "c2.3-v2.0-release-strip-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-release-strip-device-session.json"
RECEIPT = ARCH / "c2.3-v2.0-release-strip-device-result-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-release-strip-device-result.md"
CAPTURE_ROOT = ARCH / "artifacts/c2-v200-release-strip-device-20260902"
COUNTERS = CAPTURE_ROOT / "input-counters.bin"
NSYM = CAPTURE_ROOT / "d5-nsym.bin"
NPOOL = CAPTURE_ROOT / "d5-npool.bin"
STATUS = (
    "PASS: STRIPPED V2.0 DEVICE GROUPS GREEN; INDEPENDENT REVIEW PENDING")
ABSENT_SHA = "7b043c689bcd2a862f1117c1bcb8e957c8b193ec6b25530cc5b28f31d1df620c"
VALID_SHA = "619f4bfc258d74037fb6f74c74bc3ef14ce91b1efa80bb446943b1eacfa7758c"
ELF_SHA = "3754c3857ecce95943e315bc5ef6fb30962d6c8dde9cb6294cb049c7e512cf6d"
PRG_SHA = "0fb9092a32820c1e3914096f5393a96a14374cdd05c56ef66f9293457422d369"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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


def write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "device-result plan section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("8a 8a 8a 8a", "107 free symbol slots",
                  "-2 slots / -19 bytes", "l65sys disk error",
                  "independent review is pending"):
        require(token in folded, f"device-result authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
            "section": PLAN_HEADER, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def raw_observations() -> dict[str, Any]:
    counters, nsym, npool = (COUNTERS.read_bytes(), NSYM.read_bytes(),
                              NPOOL.read_bytes())
    require(len(counters) == 4 and len(nsym) == len(npool) == 2,
            "stopped-state capture width drift")
    counter_values = list(counters)
    observed = {"nsym": int.from_bytes(nsym, "little"),
                "npool": int.from_bytes(npool, "little")}
    return {"counter_bytes_hex": counters.hex(" ").upper(),
            "counter_values": dict(zip(
                ("raw", "seen", "stored", "taken"), counter_values)),
            "D5_observed": observed,
            "D5_free": {"symbol_slots": 752 - observed["nsym"],
                        "namepool_bytes": 10208 - observed["npool"]}}


def derive() -> dict[str, Any]:
    media, session = load(MEDIA), load(SESSION)
    raw = raw_observations()
    absent = media["media"]["absent_INIT"]
    valid = media["media"]["valid_INIT"]
    packed = media["packed_readback"]
    require(media["status"] ==
                "PASS: V2.0 STRIPPED RELEASE DEVICE MEDIA READY"
            and media["accepted_pair"]["ELF"]["sha256"] == ELF_SHA
            and media["accepted_pair"]["PRG"]["sha256"] == PRG_SHA
            and absent["sha256"] == ABSENT_SHA
            and valid["sha256"] == VALID_SHA
            and media["session"] == bind(SESSION)
            and session["status"] ==
                "ready-owner-v2.0-stripped-final-contact",
            "device media/session authority drift")
    for name in ("absent_INIT", "valid_INIT"):
        row = packed[name]
        require(row["status"] ==
                    "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
                and row["closure"]["object_count"] == 760
                and row["closure"]["call_site_count"] == 2436
                and row["generation_coherence"]["object_count"] == 397
                and row["delivered_key_sources"]["active_sink_set"] == [
                    "c2_kernal_input_take"]
                and row["delivered_host_wall"]["counters"] == {
                    "raw": 94, "seen": 94, "stored": 94, "taken": 94},
                f"packed {name} gate drift")
    require(raw == {"counter_bytes_hex": "8A 8A 8A 8A",
                    "counter_values": {"raw": 138, "seen": 138,
                                       "stored": 138, "taken": 138},
                    "D5_observed": {"nsym": 645, "npool": 8741},
                    "D5_free": {"symbol_slots": 107,
                                "namepool_bytes": 1467}},
            "raw device observation drift")
    return {
        "format": "lisp65-c2-v200-release-strip-device-result-v1",
        "recorded_on": "2026-09-02", "status": STATUS,
        "authority": {"media": bind(MEDIA), "session": bind(SESSION),
                      "plan_result": plan_section(),
                      "accepted_pair": media["accepted_pair"]},
        "deployment": {
            "device": "/dev/ttyUSB1", "transport": "mega65_ftp-over-JTAG",
            "qualifying_readbacks": [
                {"medium": "V20STRP.D81", "boot": "initial-absent-INIT",
                 "sha256": ABSENT_SHA, "result": "boot-green"},
                {"medium": "V20STRP.D81", "boot": "fresh-after-power-cycle",
                 "sha256": ABSENT_SHA, "result": "boot-green"},
                {"medium": "V20SINI.D81", "boot": "fresh-valid-INIT",
                 "sha256": VALID_SHA, "result": "boot-green"}],
            "packed_gates": {"closure_objects": 760,
                "closure_calls": 2436, "generation_objects": 397,
                "active_key_sink": ["c2_kernal_input_take"]},
            "optional_library_media": "none"},
        "nonqualifying_staging_incidents": {
            "classification": (
                "SESSION/STAGING-LIFECYCLE EVIDENCE; NO PRODUCT DEFECT INFERRED"),
            "observations": [
                "post-stop reuse/remount produced a red frame and character garbage",
                "a staging attempt produced red L65SYS DISK ERROR - CHECK MEDIA",
                "a further reuse/restage attempt produced a red frame and garbage"],
            "discriminator": (
                "fresh power-cycle plus fresh upload and SHA-identical readback "
                "of the same bound absent medium booted green"),
            "permanent_choreography": (
                "every qualifying cold boot restores and rereads the bound D81; "
                "a prior staged copy is not reused")},
        "choreography": {"fresh_BASIC_first": True,
            "owner_keyboard_only_while_running": True,
            "automated_access_while_CPU_running": 0,
            "stopped_state_captures": ["BCFC..BCFF", "nsym", "npool"],
            "final_observation": "valid INIT result 17 and live prompt",
            "final_CPU_stop_claim": False},
        "rows": [
            {"id": "S20-1-documented-domain-behavior", "result": "PASS",
             "observations": ["(car 1) returned nil",
                "(length \"abc\") raised *** vm: type error and returned to one live prompt"]},
            {"id": "S20-2-v1.9-input-and-forced-collection",
             "result": "PASS: LOSSLESS ACROSS FORCED COLLECTION",
             "observations": ["ordinary and rapid typing felt like v1.9",
                "six exact 32-character passes; each 32-delete pass ended empty",
                "final abcdefg oracle returned 7"],
             "captures": {"input_counters": bind(COUNTERS),
                          **{key: raw[key] for key in (
                              "counter_bytes_hex", "counter_values")}},
             "acceptance_predicate": "raw=seen=stored=taken and nonzero",
             "fixture_projection": {"expected": 136, "observed": 138,
                "delta": 2, "status": "OPEN FIXTURE-ARITHMETIC ATTRIBUTION",
                "exact_136_claim": False}},
            {"id": "S20-3-boot-INIT-A0", "result": "PASS",
             "observations": ["absent INIT was silent and booted to one prompt",
                "(>= nil 32) recovered practically immediately",
                "valid INIT printed exactly one 17 before banner and prompt",
                "(init-proof) returned 17"]},
            {"id": "S20-4-release-terminal-D5-and-performance",
             "result": "PASS",
             "performance": ["0 2", "0 (9 2)", "0 98", "0 42"],
             "D5": {"captures": {"nsym": bind(NSYM), "npool": bind(NPOOL)},
                    "ELF_truth": {"ELF_sha256": ELF_SHA,
                        "nsym_address": "0x005C", "npool_address": "0xBE18"},
                    "observed": raw["D5_observed"],
                    "free": raw["D5_free"],
                    "minimum_free": {"symbol_slots": 32,
                                     "namepool_bytes": 384},
                    "projection": {"symbol_slots": 109,
                                   "namepool_bytes": 1486},
                    "projection_delta": {"symbol_slots": -2,
                                         "namepool_bytes": -19,
                                         "status": "ATTRIBUTION-PENDING-BEFORE-PUBLISH"}}},
        ],
        "decision": {"all_four_claim_groups_hardware_green": True,
            "losslessness_across_forced_collection": "PASS-138/138/138/138",
            "D5_floor": "PASS-107/1467",
            "hardware_acceptance": "INDEPENDENT-REVIEW-PENDING",
            "release_card": "CLOSED", "Ship": "CLOSED", "Publish": "CLOSED"},
        "claim_limit": {"accepts": ["Tier-1 device semantics sample",
                "v1.9-like native editor feel", "forced-collection losslessness",
                "absent/valid INIT and A0", "four performance smokes",
                "release-terminal D5 floor"],
            "excludes": ["exact 136-event projection", "D5 delta attribution",
                "Comfort", "Matcher/Blink", "Tier 2", "release", "Ship",
                "Publish"]},
        "next": ("independent device-result review; attribute D5 -2/-19 before "
                 "Publish and classify the +2 event projection delta")}


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "stripped v2.0 device result drift")
    counters = value["rows"][1]["captures"]["counter_values"]
    d5 = value["rows"][3]["D5"]
    require(len(set(counters.values())) == 1
            and next(iter(counters.values())) > 0
            and value["rows"][1]["fixture_projection"]["exact_136_claim"] is False
            and d5["free"]["symbol_slots"] >= d5["minimum_free"]["symbol_slots"]
            and d5["free"]["namepool_bytes"] >= d5["minimum_free"]["namepool_bytes"]
            and all(int(row.split()[0]) <= 2
                    for row in value["rows"][3]["performance"])
            and value["decision"]["release_card"] == "CLOSED"
            and value["decision"]["Ship"] == value["decision"]["Publish"] == "CLOSED",
            "device result wall or claim-boundary drift")


REPORT_TEXT = """# v2.0 stripped release-world device result

Status: **DEVICE GROUPS GREEN — independent review pending**

The absent-INIT and valid-INIT D81s were each freshly uploaded and read back
at their bound SHA-256 before their qualifying boots.  The stripped product
passed all four hardware groups: documented Tier-1 behavior, input across a
forced collection, absent/valid INIT plus A0 recovery, and release-terminal
D5 plus four performance smokes.

The forced-collection raw capture is `8A 8A 8A 8A`, so raw, seen, stored and
taken are all 138.  All six exact 32-character passes deleted back to an empty
line; the final seven-character oracle printed 7.  Equality and nonzero are
the device losslessness proof.  The bound fixture projected 136, not 138; its
+2 arithmetic delta is retained as open fixture attribution and no exact-136
claim is made.

D5 observed `nsym=645` and `npool=8741`: 107 symbol slots and 1,467 name bytes
free, safely above 32/384.  The -2-slot/-19-byte delta from projection remains
a named pre-Publish attribution obligation.  Performance returned `0 2`,
`0 (9 2)`, `0 98`, and `0 42`.

Three non-qualifying reuse/restaging attempts after the first stopped-state
read produced character garbage, a red `L65SYS DISK ERROR - CHECK MEDIA`, or
a red frame with garbage.  They are preserved as staging/choreography
evidence.  A power-cycle followed by fresh upload and SHA-identical readback
of the same bound medium booted green; future qualifying cold boots therefore
restore and reread their D81 instead of reusing a prior staged copy.

On the valid-INIT boot, exactly one `17` appeared before banner and prompt;
`(init-proof)` then returned 17.  Hardware acceptance awaits independent
review.  Release-card, Ship and Publish remain closed.
"""


def build() -> None:
    require(not RECEIPT.exists(), "device result is one-shot")
    write(REPORT, REPORT_TEXT.encode())
    value = derive()
    validate(value)
    write(RECEIPT, canonical(value))
    print("v2.0 stripped device result: BUILD PASS review=pending")


def check() -> None:
    require(REPORT.read_text(encoding="utf-8") == REPORT_TEXT,
            "device-result report drift")
    validate(load(RECEIPT))
    print("v2.0 stripped device result: CHECK PASS groups=4 review=pending")


def selftest() -> None:
    base = load(RECEIPT)
    cases = {
        "unequal-taken": lambda x: x["rows"][1]["captures"][
            "counter_values"].update(taken=137),
        "invent-exact-136": lambda x: x["rows"][1]["fixture_projection"].update(
            exact_136_claim=True),
        "hide-D5-delta": lambda x: x["rows"][3]["D5"]["projection_delta"].update(
            status="ATTRIBUTED"),
        "lower-symbol-floor": lambda x: x["rows"][3]["D5"]["free"].update(
            symbol_slots=31),
        "erase-staging": lambda x: x.update(nonqualifying_staging_incidents={}),
        "open-Ship": lambda x: x["decision"].update(Ship="OPEN"),
    }
    rejected = 0
    for name, mutate in cases.items():
        candidate = copy.deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate)
        except ResultError:
            rejected += 1
        else:
            raise ResultError(f"mutation survived: {name}")
    require(rejected == len(cases), "device-result mutation count drift")
    print(f"v2.0 stripped device result: SELFTEST PASS mutations={rejected}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build(); check()
    elif action in ("check", "source-check"):
        check()
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: build|check|source-check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 stripped device result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
