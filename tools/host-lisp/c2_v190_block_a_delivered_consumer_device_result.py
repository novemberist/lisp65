#!/usr/bin/env python3
"""Bind the one r8 forced-collection counter read and Block-A verdict."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — Block A delivered-consumer repair — 2026-08-30")
MEDIA_RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-r8-media-receipt.json")
SESSION = ROOT / "config/c2-v190-block-a-delivered-consumer-r8-session.json"
CAPTURE = ROOT / (
    "build/c2.3/v1.9-block-a-delivered-consumer-r8-contact/counter-capture.json")
READBACK = ROOT / (
    "build/c2.3/v1.9-block-a-delivered-consumer-r8-contact/V19R8P-readback.d81")
RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-r8-device-result.json")
REPORT = ROOT / "docs/planning/v1.9.0-block-a-delivered-consumer-device-result.md"
STATUS = "PASS: V1.9 BLOCK A HARDWARE ACCEPTED"
MEDIA_SHA = "eac2ce662f5c07c5e02969515947082157ad8e30534833ca39b1e3da9f398f38"
PAIR = {
    "ELF": "1b7e85b44060b7729e22f0888f02ac6f21e97f54ade144a1a0fb34e5913f01f2",
    "PRG": "55725440e41b1dd9f1cf1fa912161846dc523ccc4b8e17ef869eba29430c717d",
}


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


def section_bind(path: Path, header: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": path.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify_capture(capture: dict[str, Any]) -> None:
    require(capture["format"] ==
                "lisp65-c2-v190-block-a-r8-counter-capture-v1"
            and capture["counters"] == {
                "raw": 136, "seen": 136, "stored": 136, "taken": 136}
            and capture["counters_hex"] == "88888888"
            and capture["read"] == {
                "address": "0xBCFC", "bytes": 4,
                "command": "m0000bcfc",
                "returned_16_hex": "88888888000000000000000000000000"}
            and capture["discipline"] == {
                "CPU_left_stopped": True, "resumes": 0, "stops": 1}
            and capture["owner_observation"] == {
                "all_six_tokens_visible_exact": True,
                "all_six_delete_passes_blank_exact": True,
                "numeric_oracle": 7},
            "r8 counter capture is not the bound green row")


def derive() -> dict[str, Any]:
    media = load(MEDIA_RECEIPT)
    session = load(SESSION)
    capture = load(CAPTURE)
    verify_capture(capture)
    require(media["status"] ==
                "PASS: V1.9 BLOCK-A R8 ARTIFACT-ONLY MEDIA READY"
            and media["media"]["product"]["sha256"] == MEDIA_SHA
            and bind(READBACK)["sha256"] == MEDIA_SHA
            and {name: row["sha256"]
                 for name, row in media["accepted_pair"].items()} == PAIR
            and session["counter_witness"]["green"] ==
                "raw=seen=stored=taken=136 and visible numeric oracle=7"
            and session["counter_witness"]["addresses"] == {
                "raw": "0xBCFC", "seen": "0xBCFD",
                "stored": "0xBCFE", "taken": "0xBCFF"},
            "r8 medium/session world differs from capture")
    return {"format": "lisp65-c2-v190-block-a-r8-device-result-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": {"review": section_bind(PLAN, PLAN_HEADER),
                      "media": bind(MEDIA_RECEIPT), "session": bind(SESSION)},
        "deployment": {"transport": "mega65_ftp-over-JTAG",
            "remote_name": "V19R8P.D81", "source_sha256": MEDIA_SHA,
            "readback": bind(READBACK), "byte_identical": True},
        "owner_observation": capture["owner_observation"],
        "stopped_state": {"capture": bind(CAPTURE),
            "tuple": capture["tuple"], "read": capture["read"],
            "counters": capture["counters"],
            "discipline": capture["discipline"]},
        "decision": {"Block_A_hardware": "PASS",
            "Block_B_hardware": "PASS-INHERITED-INDEPENDENT-REVIEW",
            "v1_5_fast_typing_Known_Issue": "PENSIONED",
            "v1_8_native_prompt_cursor_Known_Issue": "PENSIONED",
            "v1_9_release_carriers": "A+B-HARDWARE-GREEN"},
        "claim_limit": ("lossless physical input through the delivered armed "
            "read-line lifetime across a forced collection; type-ahead during "
            "evaluation, Comfort and Matcher/Blink remain excluded"),
        "next": "release card, owner Ship, D5 delta attribution, owner Publish"}


def verify(value: dict[str, Any]) -> None:
    require(value == derive(), "r8 Block-A device result drift")


def selftest() -> None:
    base = derive()
    cases = {
        "restore-device-red-taken-zero": lambda x: x["stopped_state"][
            "counters"].update(taken=0),
        "hide-counter-wrap": lambda x: x["stopped_state"]["counters"].update(
            raw=392),
        "claim-resume": lambda x: x["stopped_state"]["discipline"].update(
            resumes=1),
        "drop-readback-identity": lambda x: x["deployment"].update(
            byte_identical=False),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = copy.deepcopy(base)
        mutate(trial)
        if trial != derive():
            rejected.append(name)
    require(rejected == list(cases), "r8 result mutation survived")
    print(f"v1.9 Block-A r8 result: SELFTEST PASS mutations={len(rejected)}")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "r8 device result is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(f"""# v1.9 Block A — delivered-consumer device result

Status: **{STATUS}**

The reviewed r8 product medium was uploaded over JTAG and read back
byte-identically at SHA-256 `{MEDIA_SHA}`.  The owner completed all six
forced-collection passes with exact visible tokens and exact blank deletion
boundaries; the final numeric oracle was `7`.

The sole stopped-state read returned `88 88 88 88` at `$BCFC..$BCFF`:
`raw=seen=stored=taken=136`.  The CPU was not resumed.  This is the exact
nonzero equality bound before the contact and proves that the delivered editor
consumed every captured event across the forced collection.

Block A is hardware-accepted and the v1.5 fast-typing Known Issue is pensioned.
Together with the already accepted Block B, both v1.9 release carriers are now
hardware-green.  Comfort and Matcher/Blink remain outside the claim.
""", encoding="utf-8")
    verify(load(RECEIPT))
    print("v1.9 Block-A r8 result: WRITE PASS counters=136/136/136/136")


def source_check() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["deployment"]["source_sha256"] == MEDIA_SHA
            and value["stopped_state"]["counters"] == {
                "raw": 136, "seen": 136, "stored": 136, "taken": 136}
            and value["stopped_state"]["discipline"]["resumes"] == 0
            and value["decision"]["Block_A_hardware"] == "PASS"
            and value["decision"]["v1_5_fast_typing_Known_Issue"] == "PENSIONED"
            and REPORT.is_file() and STATUS in REPORT.read_text(encoding="utf-8"),
            "r8 tracked device result drift")
    print("v1.9 Block-A r8 result: SOURCE CHECK PASS Block-A=accepted")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "write":
        write()
    elif action == "check":
        verify(load(RECEIPT))
        print("v1.9 Block-A r8 result: CHECK PASS Block-A=accepted")
    elif action == "source-check":
        source_check()
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: write|check|source-check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 Block-A r8 result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
