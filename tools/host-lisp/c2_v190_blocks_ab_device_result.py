#!/usr/bin/env python3
"""Bind/check the owner-observed v1.9 Blocks-A/B r7 device result."""

from __future__ import annotations

import copy
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
from evidence_era import era_bind  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v190-blocks-ab-display-r7-acceptance-session.json"
MEDIA_RECEIPT = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-acceptance-media-receipt.json")
CARD_RECEIPT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-receipt.json")
RESULT = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-device-result-receipt.json")
REPORT = ROOT / "docs/planning/v1.9.0-blocks-ab-r7-device-result.md"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
PLAN_HEADER = "## Block A+B r7 device result — 2026-08-30"
CAPTURE_ROOT = ARCH / "artifacts/c2-v190-blocks-ab-r7-device-20260830"
NSYM_CAPTURE = CAPTURE_ROOT / "d5-nsym.bin"
NPOOL_CAPTURE = CAPTURE_ROOT / "d5-npool.bin"
ELF = MEDIA.WPLTO / "lisp65-c2-substitution-linked.prg.elf"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LISTS = ROOT / "lib/dialect-v2/lists-core.lisp"
VM = ROOT / "src/vm.c"
EVIDENCE_ERA = "d38ea2e3"
STATUS = (
    "PASS: DEVICE ROWS GREEN; FORCED-COLLECTION DEVICE SUBCLAIM REVIEW-PENDING")


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


def addresses() -> dict[str, int]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    return {name: truth.symbol(name).value for name in ("nsym", "npool")}


def observed() -> dict[str, int]:
    nsym = NSYM_CAPTURE.read_bytes()
    npool = NPOOL_CAPTURE.read_bytes()
    require(len(nsym) == len(npool) == 2, "D5 capture width drift")
    return {"nsym": int.from_bytes(nsym, "little"),
            "npool": int.from_bytes(npool, "little")}


def derive() -> dict[str, Any]:
    session = load(SESSION)
    media = load(MEDIA_RECEIPT)
    card = load(CARD_RECEIPT)
    where = addresses()
    obs = observed()
    free = {"symbol_slots": 752 - obs["nsym"],
            "namepool_bytes": 10208 - obs["npool"]}
    loss = card["final_product"]["hybrid"]["loss"]
    response = card["final_product"]["hybrid"]["responsiveness"]
    client = card["final_product"]["v1_8_native_line_editor_client"]["client"]
    row3 = next(row for row in session["rows"]
                if row["id"] == "ABR7-3-lossless-forced-collection")
    lists_source = LISTS.read_text(encoding="utf-8")
    vm_source = VM.read_text(encoding="utf-8")
    require(media["status"] == MEDIA.STATUS
            and media["session"] == bind(SESSION)
            and media["media"]["product"]["sha256"] ==
                "9bc5d45db0c0280ce8f067856dee98ed1cc14aec256398c5e93eb1b56bb06412"
            and session["configuration"]["optional_libraries_loaded"] == []
            and where == {"nsym": 0x005A, "npool": 0xBE1A}
            and obs == {"nsym": 645, "npool": 8741}
            and free == {"symbol_slots": 107, "namepool_bytes": 1467},
            "device/media/D5 authority drift")
    require(row3["actions"][0] == "start a fresh native input with (length \""
            and row3["forced_collection"] is True
            and row3["accepted_printable_insertions_minimum"] > 192
            and "(defun length (xs)" in lists_source
            and "case 3:" in vm_source
            and "/* string-length */" in vm_source,
            "session-oracle attribution drift")
    require(loss["capture_model"]["events_produced"] == 94
            and loss["capture_model"]["events_captured"] == 94
            and loss["linked_events_drained"] == 94
            and loss["capture_model"]["dropped"] == loss["linked_dropped"] == 0
            and client["entry_closed_then_zeroed_then_armed"] is True
            and response["margin_percent"] >= 25,
            "r7 host loss/armed wall drift")
    return {
        "format": "lisp65-c2-v190-blocks-ab-r7-device-result-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": {"media": bind(MEDIA_RECEIPT), "session": bind(SESSION),
            "r7_card": bind(CARD_RECEIPT), "report": bind(REPORT),
            "plan_result_section": section_bind(PLAN, PLAN_HEADER)},
        "deployment": {
            "device": "/dev/ttyUSB1", "transport": "mega65_ftp-over-JTAG",
            "remote_name": "V19R7P.D81", "bytes": 819200,
            "source_sha256": media["media"]["product"]["sha256"],
            "readback_sha256": media["media"]["product"]["sha256"],
            "readback": "byteidentical", "optional_library_mounts": 0},
        "choreography": {"fresh_BASIC_first": True,
            "owner_keyboard_only_after_boot": True,
            "post_boot_automated_access_before_final_D5": 0,
            "final_D5_logical_capture": 1,
            "final_D5_transport_reads": 2,
            "transport_note": "m65 honors only the final --memsave per invocation; nsym was read from the same unchanged stopped state",
            "final_resume": False},
        "rows": [
            {"id": "ABR7-1-composed-native-prompt-display", "result": "PASS",
             "observation": "lisp65> and active cursor share editor-owned row 24; no scattered blanks or second cursor"},
            {"id": "ABR7-2-native-prompt-editor", "result": "PASS",
             "observations": ["Left/insert produced (1 2 3)",
                "C-b/C-f C-a/C-e Backspace C-d and boundary sequence produced abc",
                "reader: invalid token absent"]},
            {"id": "ABR7-3-lossless-forced-collection",
             "result": "PASS-DEVICE-LOSSLESS; FORCED-COLLECTION-DEVICE-NOT-CLAIMED",
             "device_observation": "owner visually confirmed ordinary and fast physical typing lossless",
             "scripted_stimulus_completed": False,
             "forced_collection_witness_on_device": False,
             "reason": "owner shortened impractical scrolling-line stimulus; scripted length oracle was list-only",
             "host_final_world": {"produced": 94, "captured": 94,
                "drained": 94, "drops": 0,
                "capture_lifecycle": "delivered read-line armed"}},
            {"id": "ABR7-4-boot-surface-without-libraries", "result": "PASS",
             "observation": "product medium only; no INIT error, red frame, or library dependency"},
            {"id": "ABR7-5-explicit-read-line-break-and-A0", "result": "PASS",
             "observations": ["explicit read-line returned abcde",
                "physical RUN/STOP returned to one live prompt",
                "vm type error recovered practically immediately",
                "follow-up (list 1 3) returned (1 3)"]},
            {"id": "ABR7-6-INIT-performance-and-D5", "result": "PASS",
             "INIT_L65_absence": "silent",
             "performance": [
                {"frames": 0, "value": "2", "observation": "0 2"},
                {"frames": 0, "value": "(9 2)", "observation": "0 (9 2)"},
                {"frames": 0, "value": "98", "observation": "0 98"},
                {"frames": 0, "value": "42", "observation": "0 42"}]},
        ],
        "session_fixture_attribution": {
            "classification": "SESSION-ORACLE-DEFECT; NOT PRODUCT DEFECT",
            "incorrect_public_form": "(length string)",
            "correct_public_form": "(string-length string)",
            "list_length_authority": bind(LISTS),
            "string_length_authority": era_bind(EVIDENCE_ERA, VM),
            "correction_rule": "a withdrawn device stimulus carries no acceptance weight and no unobserved collection claim"},
        "D5": {"status": "PASS: RELEASE-TERMINAL D5 HEADROOM GREEN",
            "captures": {"nsym": bind(NSYM_CAPTURE),
                         "npool": bind(NPOOL_CAPTURE)},
            "ELF_derived_addresses": {name: f"0x{addr:04X}"
                                      for name, addr in where.items()},
            "observed": obs, "limits": {"symbols": 752,
                "namepool_bytes": 10208}, "free": free,
            "minimum_free": {"symbol_slots": 32, "namepool_bytes": 384}},
        "decision": {"Block_B_hardware": "PASS",
            "Block_A_user_visible_losslessness": "PASS",
            "Block_A_forced_collection_device_subclaim": "NOT-CLAIMED",
            "Block_A_host_forced_collection_wall": "PASS-94/94-ZERO-DROPS",
            "all_six_groups_strictly_green": False,
            "A_plus_B_hardware_acceptance": "INDEPENDENT-REVIEW-PENDING"},
        "claim_limit": {"accepts": ["r7-display-on-one-row",
                "native-prompt-editor", "user-visible-ordinary-and-fast-input",
                "boot-without-optional-libraries", "read-line/RUNSTOP/A0",
                "performance-smokes", "release-terminal-D5"],
            "excludes": ["device-observed-forced-collection", "Comfort",
                "Matcher/Blink", "Block-C", "Block-D", "$22-closure",
                "Ship", "publication"]},
        "next": "independent review decides whether device-visible losslessness plus the 94/94 armed host wall closes Block A",
    }


def verify(value: dict[str, Any]) -> None:
    require(value == derive(), "v1.9 Blocks-A/B device result drift")
    require(value["decision"]["Block_B_hardware"] == "PASS"
            and value["decision"]["all_six_groups_strictly_green"] is False
            and value["rows"][2]["forced_collection_witness_on_device"] is False
            and all(row["frames"] <= 2
                    for row in value["rows"][5]["performance"])
            and value["D5"]["free"]["symbol_slots"] >= 32
            and value["D5"]["free"]["namepool_bytes"] >= 384
            and value["choreography"]["final_resume"] is False,
            "device result overclaim or wall drift")


def selftest() -> None:
    base = derive()
    cases = {
        "invent-device-collection": lambda x: x["rows"][2].update(
            forced_collection_witness_on_device=True),
        "promote-all-six": lambda x: x["decision"].update(
            all_six_groups_strictly_green=True),
        "hide-session-oracle": lambda x: x["session_fixture_attribution"].update(
            classification="PASS"),
        "lower-symbol-headroom": lambda x: x["D5"]["free"].update(
            symbol_slots=31),
        "lower-name-headroom": lambda x: x["D5"]["free"].update(
            namepool_bytes=383),
        "exceed-frame-wall": lambda x: x["rows"][5]["performance"][0].update(
            frames=3),
        "resume-after-D5": lambda x: x["choreography"].update(
            final_resume=True),
        "load-optional-library": lambda x: x["deployment"].update(
            optional_library_mounts=1),
    }
    rejected = []
    for name, mutate in cases.items():
        value = copy.deepcopy(base)
        mutate(value)
        try:
            verify(value)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "device result mutation survived")
    print(f"v1.9 Blocks A+B device result: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "write":
        require(not RESULT.exists(), "device result already exists")
        RESULT.write_bytes(canonical(derive()))
        verify(load(RESULT))
        print("v1.9 Blocks A+B device result: WRITE PASS review=pending")
    elif action == "check":
        verify(load(RESULT))
        print("v1.9 Blocks A+B device result: CHECK PASS review=pending")
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: write|check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 Blocks A+B device result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
