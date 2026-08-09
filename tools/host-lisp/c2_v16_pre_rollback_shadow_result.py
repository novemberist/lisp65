#!/usr/bin/env python3
"""Close the shadow-armed defstruct repeat without widening R/A/I/G.

The pre-rollback shadow disproves the consumed Slot-39/A interpretation: the
v5-fail edge was never reached.  The two retained refill bytes agree with an
independent C2D/Bank-2 source oracle and the VM/GC witnesses are clean.  The
remaining terminal observer is the source-less IRQ guard, but its captured
D01A value is zero while the pre-registered pure-I row requires one.

The ordering of the contact is decisive.  Its first screenshot is a blue,
still-active form; only after that monitor/Freezer crossing does the stopped
state sit in the diagnostic fail loop with the second-source-less tag set.
This checker therefore records a harness First Red, not a post-hoc I row.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_defstruct_phase_b as PHASE_B  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-contact-device-receipt.json")
PREPARATION = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-contact-preparation-receipt.json")
PHASE_A = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json")
PHASE_B_RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
LINK72 = EVIDENCE / (
    "c2.2-link72-defstruct-active-definition-poll-harness-first-red.json")
OPTION2 = EVIDENCE / (
    "c2.2-v1.2.6-option2-fail-closed-load-attribution-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-result-first-red-receipt.json")
CONTACT_DRIVER = ROOT / "tools/host-lisp/c2_v16_pre_rollback_shadow_contact.py"
PHASE_C_DRIVER = ROOT / "tools/host-lisp/c2_v16_defstruct_phase_c.py"
IRQ_SOURCE = ROOT / "src/c2_kernal_window.s"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
GATES = ROOT / "mk/gates.mk"

FORMAT = "lisp65-c2.3-v1.6-pre-rollback-shadow-result-first-red-v1"
RECORDED_ON = "2026-08-06"
CONTACT_COMMIT = "731679dc729529abc2943c6e1d5a81d58beb4f76"
C2_PRODUCT_CODE_BANK_TAG = 1
C2_CODE_HEADER_SCALAR_BYTES = 7
C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
OWNER_ORDINAL = 0x0274
RECORD_HEX = (
    "a1a2a31000a4017402a51000a60ba7a81400a9017402aa1400ab3e5c5dcc"
    "5ecccc5fcc60cccccc61ccccb2637f01000200b6b701b800b900ba9701bbbc"
    "00bd0600"
)


class ShadowResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ShadowResultError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha_bytes(raw)}


def git_binding(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"path": path, "bytes": len(raw), "sha256": sha_bytes(raw)}


def u16(value: bytes, offset: int) -> int:
    require(0 <= offset and offset + 2 <= len(value), "u16 outside artifact")
    return int.from_bytes(value[offset:offset + 2], "little")


def c2d_entry(c2d: bytes, ordinal: int) -> dict[str, Any]:
    at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
    raw = c2d[at:at + C2D_ENTRY_BYTES]
    require(len(raw) == C2D_ENTRY_BYTES, "C2D entry outside captured plane")
    return {
        "ordinal": ordinal, "raw_hex": raw.hex(), "image_slot": raw[0],
        "literal_count": raw[1], "code_offset": u16(raw, 2),
        "code_length": u16(raw, 4), "resolution_base": u16(raw, 6),
        "generation": u16(raw, 8),
    }


def bound_capture(device: dict[str, Any], name: str) -> tuple[bytes, dict[str, Any]]:
    row = device["backing_plane_oracles"][name]
    path = ROOT / row["path"]
    binding = bind(path)
    require(binding == {key: row[key] for key in ("path", "bytes", "sha256")},
            f"{name} capture binding drift")
    return path.read_bytes(), binding


def record_field(device: dict[str, Any], name: str) -> dict[str, Any]:
    row = device["decoded_record"][name]
    require(isinstance(row, dict), f"record field absent: {name}")
    return row


def first_observation(device: dict[str, Any]) -> dict[str, Any]:
    observed = device["first_observation"]
    paths = {name: ROOT / observed[name]["path"] for name in ("png", "ansi", "text")}
    for name, path in paths.items():
        require(bind(path) == {key: observed[name][key]
                               for key in ("path", "bytes", "sha256")},
                f"first-observation {name} binding drift")
    with Image.open(paths["png"]) as image:
        rgb = image.convert("RGB")
        corners = [rgb.getpixel(point) for point in (
            (0, 0), (rgb.width - 1, 0), (0, rgb.height - 1),
            (rgb.width - 1, rgb.height - 1))]
        colors = Counter(rgb.get_flattened_data())
    require(corners == [(0, 0, 240)] * 4
            and colors[(0, 0, 240)] > 300000,
            "first observation is not the captured blue pre-fail frame")
    lines = [line.strip() for line in paths["text"].read_text(
        encoding="utf-8", errors="replace").splitlines() if line.strip()]
    require(lines[-3:] == ["lisp65> (require 'defstruct)", "t",
                           "lisp65> (defstruct point x y)"],
            "first observation no longer ends at the active defstruct form")
    return {
        "frame": "blue-workbench-not-red-fail-closed",
        "corner_RGB": list(corners[0]),
        "dominant_blue_pixels": colors[(0, 0, 240)],
        "visible_tail": lines[-3:],
        "trailing_result_or_prompt": False,
        "bindings": {name: bind(path) for name, path in paths.items()},
    }


def retained_fills(device: dict[str, Any], bank2: bytes,
                   c2d: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    owner = c2d_entry(c2d, OWNER_ORDINAL)
    require(owner == {
        "ordinal": 628, "raw_hex": "0506908d2a0006090100", "image_slot": 5,
        "literal_count": 6, "code_offset": 36240, "code_length": 42,
        "resolution_base": 2310, "generation": 1,
    }, "captured active-owner C2D row drift")
    obj = bank2[owner["code_offset"]:owner["code_offset"] + owner["code_length"]]
    header_bytes = C2_CODE_HEADER_SCALAR_BYTES + 2 * owner["literal_count"]
    require(len(obj) == 42 and header_bytes == 19 and obj.hex() == (
        "b50200021700060000000000000000000000000b3c00010c3c01020b3c0201"
        "0b3c03010b3c04013e0504"), "active-owner object drift")
    rows: list[dict[str, Any]] = []
    for prefix, cursor, expected in (
            ("previous-fill", 16, 0x0B), ("last-fill", 20, 0x3E)):
        owner_raw = bytes.fromhex(record_field(device, f"{prefix}.owner")["value_hex"])
        fetched = record_field(device, f"{prefix}.fetched-opcode")["value_le"]
        source = obj[header_bytes + cursor]
        require(record_field(device, f"{prefix}.complete")["state"] == "reached"
                and record_field(device, f"{prefix}.cursor")["value_le"] == cursor
                and record_field(device, f"{prefix}.window-base")["value_le"] == cursor
                and owner_raw[0] == C2_PRODUCT_CODE_BANK_TAG
                and int.from_bytes(owner_raw[1:3], "little") == OWNER_ORDINAL
                and source == expected and fetched == expected,
                f"{prefix} independent source-byte oracle mismatch")
        rows.append({
            "tagged": True, "identity_correct": True,
            "owner_bank_tag": owner_raw[0],
            "owner_ordinal": int.from_bytes(owner_raw[1:3], "little"),
            "cursor": cursor, "fetched": fetched, "expected": source,
            "oracle": "bound-C2D-source",
        })
    return {"row": owner, "object_sha256": sha_bytes(obj),
            "header_bytes": header_bytes}, rows


def classifier_first_red(device: dict[str, Any], fills: list[dict[str, Any]]) -> dict[str, Any]:
    state = PHASE_B.base_state()
    state["fills"] = [{key: row[key] for key in (
        "tagged", "identity_correct", "fetched", "expected", "oracle")}
        for row in fills]
    state["append"] = {"reached": True, "failure_checkpoint": None,
                       "phase_owner": 0, "c2j": "CLEAR", "non_ok": False}
    state["error"] = {"reached": False, "status": None, "edge": None}
    state["gc"] = {"reached": True, "mem_oom": 0,
                   "runs": record_field(device, "gc.runs")["value_le"]}
    state["irq"] = {
        "reached": record_field(device, "irq.source-less-entry-2")["state"]
        == "reached", "source_less_entry": 2,
        "episode_latch": record_field(device, "irq.episode-latch")["value_le"],
        "d019": record_field(device, "irq.d019")["value_le"],
        "d01a": record_field(device, "irq.d01a")["value_le"],
        "return_pc": record_field(device, "irq.interrupted-return-pc")["value_le"],
    }
    try:
        selected = PHASE_B.classify(state)
    except PHASE_B.PhaseBError as error:
        message = str(error)
    else:
        raise ShadowResultError(f"pre-registered classifier unexpectedly selected {selected}")
    require(message == "IRQ state does not name the source-less entry",
            "pre-registered classifier First Red changed")
    return {"state": state, "error": message,
            "required_I_D01A": 1, "observed_D01A": state["irq"]["d01a"]}


def derive() -> dict[str, Any]:
    device = load(DEVICE); preparation = load(PREPARATION)
    phase_a = load(PHASE_A); phase_b = load(PHASE_B_RECEIPT)
    link72 = load(LINK72); option2 = load(OPTION2)
    require(device["format"] ==
            "lisp65-c2.3-v1.6-pre-rollback-shadow-contact-device-v1"
            and device["recorded_on"] == RECORDED_ON,
            "device receipt identity drift")
    require(device["authorities"]["preparation"] == bind(PREPARATION)
            and device["authorities"]["deployment"] == bind(
                ROOT / device["authorities"]["deployment"]["path"])
            and device["authorities"]["runner"] == bind(
                ROOT / device["authorities"]["runner"]["path"])
            and device["authorities"]["driver"] == git_binding(
                CONTACT_COMMIT,
                "tools/host-lisp/c2_v16_pre_rollback_shadow_contact.py"),
            "consumed device-contact authority drift")
    require(device["quiet"]["required_seconds"] == 180.0
            and device["quiet"]["observed_seconds"] >= 180.0
            and device["quiet"]["monitor_accesses_during_window"] == 0,
            "quiet-window authority drift")
    require(device["result"]["CPU_left_stopped"]
            and device["result"]["R_A_I_G"] is None
            and device["result"]["classification_widened"] is False,
            "device claim boundary drift")
    require(len(device["stable_record_reads"]) == 3
            and all(row["hex"] == RECORD_HEX
                    for row in device["stable_record_reads"]),
            "diagnostic record is not stable 3/3")
    require(device["pre_rollback_shadow"] == {
        "address": "0xc06b", "classification": "V5-FAIL-EDGE-UNREACHED",
        "forward_slot": None, "raw": "0x7f"},
        "pre-rollback shadow no longer excludes v5_fail")
    require(device["stop"]["PC"] == "0xb431"
            and device["stop"]["code_owner"]["unique"]
            and device["stop"]["code_owner"]["selected_owner"] ==
            "pre-rollback-shadow-diagnostic-PRG",
            "terminal diagnostic hold identity drift")

    bank2, bank2_bind = bound_capture(device, "Bank-2")
    c2d, c2d_bind = bound_capture(device, "C2D")
    c2j, c2j_bind = bound_capture(device, "C2J")
    require(len(bank2) == 65536 and len(c2d) == 50816
            and len(c2j) == 64 and c2j == bytes(64) and c2d[-64:] == c2j,
            "captured backing-plane/C2J closure drift")
    counts = {"images": u16(c2d, 12), "entries": u16(c2d, 16),
              "resolutions": u16(c2d, 20), "roots": u16(c2d, 24)}
    control = phase_a["require_only_control"]["final_counts"]
    require(counts == {key: control[key] for key in counts}
            and c2d_entry(c2d, 757)["raw_hex"] == "00" * 10,
            "target no longer matches exact post-require state")
    owner, fills = retained_fills(device, bank2, c2d)
    observation = first_observation(device)
    first_red = classifier_first_red(device, fills)

    require(record_field(device, "first-error.complete")["state"] == "initial"
            and record_field(device, "gc.mem-oom")["value_le"] == 0
            and device["current"]["phase_owner"] == "0x00"
            and device["current"]["C2J_nonzero_bytes"] == 0,
            "R/A/G clean-state boundary drift")
    require(device["mem_init"]["classification"] ==
            "INIT-BUILT-NO-FAILURE-REPRODUCED", "mem_init witness drift")

    guard = phase_b["facts"]["guard"]
    require(guard["direct_ingresses"][0]["meaning"] ==
            "second consecutive source-less IRQ episode"
            and guard["direct_ingresses"][1]["kind"] == "external-reset-vector"
            and guard["reset_exclusion"]["no_software_edge_from_measured_sequence"],
            "direct fail-closed ingress closure drift")
    require(link72["status"] ==
            "resolved-harness-crossed-documented-C2.3-boundary"
            and link72["first_red"]["C2K_SOURCELESS_IRQS"] == 1
            and "JTAG screenshot per second" in
            link72["first_red"]["harness_behavior"],
            "Link-72 active-definition monitor precedent drift")
    require(option2["status"] == "attributed-known-active-definition-monitor-crossing"
            and option2["harness_and_precedent"]["known_forbidden_crossing"] ==
            "monitor/Freezer intervention while a persistent definition or append is active",
            "Option-2 monitor-crossing precedent drift")

    contact_source = CONTACT_DRIVER.read_text(encoding="utf-8")
    capture = contact_source.split("def capture(device: str)", 1)[1].split(
        "\ndef main", 1)[0]
    order = [capture.index(token) for token in (
        "time.sleep(QUIET_SECONDS)", "first_observation = screen_capture()",
        "os.open(device", "SERIAL.monitor_sync", 'VIEW.command(fd, b"t1"')]
    require(order == sorted(order), "first-observation/stop ordering drift")
    phase_c_source = PHASE_C_DRIVER.read_text(encoding="utf-8")
    irq_capture = phase_c_source.split("def irq_capture", 1)[1].split(
        "\ndef gc_capture", 1)[0]
    fail = phase_c_source.split("def fail_routine", 1)[1].split(
        "\ndef error_routine", 1)[0]
    require("code.lda_abs(0xD01A); code.sta_abs(rec + 55)" in irq_capture
            and fail.index("irq_capture(code, rec)") <
            fail.index("STZ abs"), "D01A was not captured before diagnostic clear")

    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "FIRST-RED-OBSERVATION-CROSSED-ACTIVE-DEFINITION",
        "authorities": {
            "device": bind(DEVICE), "contact_preparation": bind(PREPARATION),
            "phase_A": bind(PHASE_A), "phase_B": bind(PHASE_B_RECEIPT),
            "Link72_precedent": bind(LINK72), "Option2_precedent": bind(OPTION2),
            "contact_driver": bind(CONTACT_DRIVER),
            "phase_C_instrument": bind(PHASE_C_DRIVER),
            "IRQ_source": bind(IRQ_SOURCE), "plan": bind(PLAN),
            "gate_wiring": bind(GATES),
            "backing_planes": {"Bank-2": bank2_bind, "C2D": c2d_bind,
                               "C2J": c2j_bind},
        },
        "stopped_state": {
            "PC": "0xb431", "code_owner": "pre-rollback-shadow-diagnostic-PRG",
            "record_hex": RECORD_HEX, "stable_reads": 3,
            "CPU_left_stopped": True, "boot_witness": "0x44",
        },
        "pre_rollback_shadow": {
            "address": "0xc06b", "value": "0x7f",
            "v5_fail_edge_reached": False,
            "withdrawn_A_slot39_claim_remains_withdrawn": True,
        },
        "source_oracle": {
            **owner, "retained_fills": fills, "R_excluded": True,
            "scope": "last-two-retained-completed-refills-only",
        },
        "post_require_state": {**counts, "next_C2D_entry_757_raw_hex": "00" * 10,
                               "matches_Phase_A_require_only": True},
        "clean_witnesses": {
            "first_error": "unreached", "mem_oom": 0,
            "phase_owner_after_stop": "NONE", "C2J": "CLEAR",
            "mem_init": "INIT-BUILT-NO-FAILURE-REPRODUCED",
            "gc_runs": record_field(device, "gc.runs")["value_le"],
        },
        "first_observation": observation,
        "terminal_observer": {
            "direct_ingress": "second-consecutive-source-less-IRQ",
            "reset_excluded_by_session": True,
            "source_less_entry_tag": 2,
            "episode_latch": first_red["state"]["irq"]["episode_latch"],
            "D019": first_red["state"]["irq"]["d019"],
            "D01A": first_red["state"]["irq"]["d01a"],
            "interrupted_return_PC": "0x0197",
            "D01A_captured_before_diagnostic_clear": True,
        },
        "classification": {
            "R_A_I_G": None,
            "pre_registered_classifier": "FIRST RED",
            "classifier_error": first_red["error"],
            "I_contract": {"required_D01A": 1, "observed_D01A": 0},
            "harness_result": "FIRST-OBSERVATION-MONITOR-CROSSING",
            "reason": (
                "the blue screenshot was the first post-quiet monitor crossing; "
                "the immediately subsequent stopped state is the source-less-IRQ "
                "diagnostic fail hold, matching the bound Link-72/Option-2 precedent"),
        },
        "disposition": {
            "product_fix_authorized": False, "product_links": 0,
            "device_recontact_authorized": False,
            "defstruct_fact": (
                "no result or new prompt was visible after 180 quiet seconds; the "
                "first observation then contaminated the active form"),
            "next_question": (
                "owner review of an observation-safe terminal witness; never take a "
                "screenshot while completion of a persistent form is unproved"),
        },
        "accounting": {"product_bytes_changed": 0, "device_recontacts": 0,
                       "measured_forms_closed": 1},
        "claim_limit": (
            "This result permanently rejects the consumed Slot-39/A claim, excludes "
            "R only for the two retained completed views, and attributes the terminal "
            "hold to the first-observation monitor crossing. It does not select the "
            "pre-registered I row because D01A=0 violates that row, prove an infinite "
            "defstruct product hang, authorize a fix/link/recontact, or widen the two "
            "refill views into a claim about every historical refill."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive(), "shadow-result receipt differs from derivation")


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[list[Any], Any]] = [
        (["status"], "I"),
        (["stopped_state", "stable_reads"], 2),
        (["stopped_state", "CPU_left_stopped"], False),
        (["pre_rollback_shadow", "value"], "0xa7"),
        (["pre_rollback_shadow", "v5_fail_edge_reached"], True),
        (["source_oracle", "R_excluded"], False),
        (["source_oracle", "retained_fills", 0, "fetched"], 0x3B),
        (["source_oracle", "retained_fills", 1, "expected"], 0x0B),
        (["post_require_state", "entries"], 758),
        (["post_require_state", "next_C2D_entry_757_raw_hex"], "01" + "00" * 9),
        (["clean_witnesses", "mem_oom"], 1),
        (["clean_witnesses", "C2J"], "ACTIVE"),
        (["first_observation", "frame"], "red-fail-closed"),
        (["first_observation", "trailing_result_or_prompt"], True),
        (["terminal_observer", "direct_ingress"], "reset"),
        (["terminal_observer", "D01A"], 1),
        (["classification", "R_A_I_G"], "I"),
        (["classification", "pre_registered_classifier"], "PASS"),
        (["classification", "I_contract", "required_D01A"], 0),
        (["classification", "harness_result"], "PRODUCT-I"),
        (["disposition", "product_fix_authorized"], True),
        (["disposition", "device_recontact_authorized"], True),
        (["accounting", "product_bytes_changed"], 1),
        (["claim_limit"], "I selected; fix and Link authorized"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ShadowResultError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise ShadowResultError(f"result mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "R_A_I_G": None,
            "harness_result": base["classification"]["harness_result"],
            "rejected": rejected}


def write_result(value: dict[str, Any]) -> None:
    # Result creation is intentionally separate from the hardware driver.  It
    # serializes only the independently derived, immutable stopped-state close.
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    RESULT.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("derive", "write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "derive":
        value = derive()
    elif args.action == "write":
        value = derive(); write_result(value)
    elif args.action == "selftest":
        value = selftest()
    else:
        audit(load(RESULT))
        value = {"status": "PASS", "R_A_I_G": None,
                 "harness_result": "FIRST-OBSERVATION-MONITOR-CROSSING",
                 "mutations": 24}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ShadowResultError, PHASE_B.PhaseBError, OSError, ValueError,
            KeyError, IndexError, json.JSONDecodeError) as error:
        print(f"PRE-ROLLBACK SHADOW RESULT FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
