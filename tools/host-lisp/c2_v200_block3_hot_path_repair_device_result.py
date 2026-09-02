#!/usr/bin/env python3
"""Seal the stopped Block-3 hot-path repair hardware result."""

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
PLAN_HEADER = (
    "## Block-3 hot-path repair device result and final descope — 2026-09-02")
MEDIA = ARCH / "c2.3-v2.0-block3-hot-path-repair-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-block3-hot-path-repair-device-session.json"
READBACK = ROOT / (
    "build/c2.3/v2.0-block3-hot-path-repair-device-media/device-stage/"
    "product-readback.d81")
RECEIPT = ARCH / (
    "c2.3-v2.0-block3-hot-path-repair-device-result-receipt.json")
REPORT = ROOT / (
    "docs/planning/v2.0.0-block3-hot-path-repair-device-result.md")
STATUS = "FINAL RED: BLOCK 3 DESCOPED AFTER HOT-PATH REPAIR"
MEDIA_SHA = "5cd1c79d4348bbae099aeffb16b6fbb7347e945e0899981a8866f8efc3ab0320"


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


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "device-result plan section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("no delimiter acquired a match mark",
                  "noticeably laggier than v1.9", "finally descoped",
                  "string-length diagnostic hint was absent"):
        require(token in folded, f"device-result authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
        "section": PLAN_HEADER, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def result_value() -> dict[str, Any]:
    media, session = load(MEDIA), load(SESSION)
    source = media["media"]["product"]
    readback = bind(READBACK)
    require(media["status"] ==
                "PASS: V2.0 BLOCK-3 HOT-PATH REPAIR DEVICE MEDIA READY"
            and source["sha256"] == readback["sha256"] == MEDIA_SHA
            and source["bytes"] == readback["bytes"] == 819200
            and session["status"] ==
                "ready-owner-v2.0-block3-hot-path-repair-contact"
            and session["rows"][2]["expect"][0] ==
                "single-key echo feels like v1.9; any visible latency is red",
            "device-result media/session authority drift")
    return {
        "format": "lisp65-c2-v200-block3-hot-path-repair-device-result-v1",
        "recorded_on": "2026-09-02", "status": STATUS,
        "authority": {"media": bind(MEDIA), "session": bind(SESSION),
                      "plan_result": plan_section(),
                      "decision_table": session["decision_table"]},
        "deployment": {"fresh_BASIC_first": True,
            "transport": "mega65_ftp-over-JTAG", "remote_name": "V20B3R.D81",
            "source": source, "readback": readback, "byteidentical": True,
            "optional_library_media": "none",
            "automated_device_access_after_boot": 0},
        "owner_observations": [
            {"id": "BOOT-0", "result": "PASS",
             "evidence": "banner, native lisp65> and cursor visible"},
            {"id": "T2D-1-car", "result": "PASS",
             "stimulus": "(car 1)", "observed": "nil"},
            {"id": "T2D-1-length", "result": "PARTIAL RED: HINT ABSENT",
             "stimulus": "(length \"abc\")",
             "observed": "*** vm: type error; exactly one live prompt",
             "missing": "string-length diagnostic hint"},
            {"id": "B3-2-line-editor-matcher",
             "result": "FIRST DAILY-USE RED: NO MATCH MARK",
             "stimulus": "(list 1 3), cursor on closing delimiter",
             "observed": "no mark immediately or after many idle seconds"},
            {"id": "B3-physical-key-feel",
             "result": "RED: WORSE THAN V1.9",
             "observed": ("much better than the prior roughly-one-second "
                          "runs, but definitely laggy and noticeably worse "
                          "than v1.9, especially while typing fast")},
        ],
        "session_progress": {
            "completed": ["BOOT-0", "T2D-1-car"],
            "partial": ["T2D-1-length", "B3-2-line-editor-matcher",
                        "B3-physical-key-feel"],
            "not_run": ["IDE matcher", "line-editor blink", "IDE blink",
                "forced-collection input and counters", "explicit INIT.L65",
                "A0", "D5", "performance smokes"]},
        "decision": {"classification": "daily-use product red",
            "block3_v2_0": "DESCOPED",
            "remaining_block3_feature_repair_rounds": 0,
            "tier1": "independent and retained",
            "latency_device_claim": "not accepted",
            "matcher_device_claim": "not accepted",
            "diagnostic_hint": "recorded discrepancy; not accepted",
            "further_device_rows": "stopped at first daily-use red"},
        "claim_limit": {"accepts": [
                "byte-identical medium deployment",
                "boot to native prompt", "documented (car 1) result",
                "type-error and prompt recovery for (length \"abc\")",
                "absence of a visible line-editor match mark",
                "owner latency comparison against v1.9",
                "pre-bound Block-3 descope branch"],
            "excludes": ["string-length hint", "Block-3 acceptance",
                "IDE matcher", "either blink surface", "lossless collection",
                "INIT/A0", "D5", "performance smokes", "release"]},
        "next": "retain Tier 1; remove Block 3 from the v2.0 release world",
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["authority"]["media"] == bind(MEDIA)
            and value["authority"]["session"] == bind(SESSION)
            and value["deployment"]["source"]["sha256"] ==
                value["deployment"]["readback"]["sha256"] == MEDIA_SHA
            and value["deployment"]["byteidentical"] is True
            and value["deployment"]["automated_device_access_after_boot"] == 0,
            "device-result authority/deployment drift")
    observations = {row["id"]: row for row in value["owner_observations"]}
    require(observations["T2D-1-car"]["observed"] == "nil"
            and observations["T2D-1-length"]["result"] ==
                "PARTIAL RED: HINT ABSENT"
            and observations["B3-2-line-editor-matcher"]["result"] ==
                "FIRST DAILY-USE RED: NO MATCH MARK"
            and observations["B3-physical-key-feel"]["result"] ==
                "RED: WORSE THAN V1.9",
            "raw owner observation drift")
    require(value["decision"] == {
            "classification": "daily-use product red",
            "block3_v2_0": "DESCOPED",
            "remaining_block3_feature_repair_rounds": 0,
            "tier1": "independent and retained",
            "latency_device_claim": "not accepted",
            "matcher_device_claim": "not accepted",
            "diagnostic_hint": "recorded discrepancy; not accepted",
            "further_device_rows": "stopped at first daily-use red"},
            "pre-bound descope decision drift")
    require(value["session_progress"]["not_run"] == [
            "IDE matcher", "line-editor blink", "IDE blink",
            "forced-collection input and counters", "explicit INIT.L65",
            "A0", "D5", "performance smokes"],
            "unrun session claim drift")


REPORT_TEXT = """# v2.0 Block-3 hot-path repair device result

Status: **FINAL RED — Block 3 descoped after its hot-path repair**

The artifact-only `V20B3R.D81` was uploaded from fresh BASIC and read back
byte-identically at SHA-256 `5cd1c79d…`.  With no optional library mounted it
booted to the banner, native `lisp65>` and one cursor.

The documented Tier-2 fallback `(car 1)` returned `nil`.  The Tier-1 sample
`(length "abc")` raised `*** vm: type error` and recovered to one live prompt,
but did not display the bound `string-length` diagnostic hint.  Error semantics
are therefore observed; the promised diagnostic wording is not accepted.

Block 3 itself is hardware-red.  With `(list 1 3)` in the native editor and
the cursor on the closing delimiter, no match mark appeared immediately or
after many idle seconds.  Physical echo was much better than the preceding
roughly-one-second runs, but the owner still judged it definitely laggy and
noticeably worse than v1.9, especially during fast typing.  The host result of
904 versus 902 steps does not override either device observation.

The session stopped at these daily-use reds.  IDE Matcher, both Blink surfaces,
the forced-collection/counter row, explicit INIT/A0, D5 and performance smokes
did not run and carry no claim.  This was Block 3's already repaired feature
world, so its pre-bound fallback fires with zero further repair rounds.  Tier 1
remains independent; Block 3 leaves the v2.0 release world.
"""


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "device result is one-shot")
    value = result_value()
    validate(value)
    write(RECEIPT, value)
    REPORT.write_text(REPORT_TEXT, encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.read_text(encoding="utf-8") == REPORT_TEXT,
            "device-result report drift")
    print("v2.0 Block3 hot-path device result: CHECK PASS "
          "Block3=descoped Tier1=retained")
    return value


def selftest() -> None:
    value = load(RECEIPT)
    cases = {
        "accept-block3": lambda row: row["decision"].update(
            {"block3_v2_0": "ACCEPTED"}),
        "reopen-round": lambda row: row["decision"].update(
            {"remaining_block3_feature_repair_rounds": 1}),
        "erase-matcher-red": lambda row: row["owner_observations"][3].update(
            {"result": "PASS"}),
        "accept-latency": lambda row: row["owner_observations"][4].update(
            {"result": "PASS"}),
        "claim-D5": lambda row: row["session_progress"]["not_run"].remove(
            "D5"),
        "alter-readback": lambda row: row["deployment"]["readback"].update(
            {"sha256": "0" * 64}),
    }
    rejected = 0
    for name, mutate in cases.items():
        candidate = copy.deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except ResultError:
            rejected += 1
        else:
            raise ResultError(f"mutation survived: {name}")
    require(rejected == len(cases), "device-result mutation count drift")
    print(f"v2.0 Block3 hot-path device result: SELFTEST PASS "
          f"mutations={rejected}")


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
        print(f"v2.0 Block3 hot-path device result: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
