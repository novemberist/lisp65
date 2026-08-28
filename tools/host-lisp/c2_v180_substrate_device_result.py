#!/usr/bin/env python3
"""Bind/check the owner-observed v1.8 substrate-only D-session result."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v180_substrate_media as MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v180-substrate-d-session.json"
MEDIA_RECEIPT = ARCH / "c2.3-v1.8.0-substrate-media-receipt.json"
RESULT = ARCH / "c2.3-v1.8.0-substrate-d-session-result-receipt.json"
CAPTURE = ARCH / "artifacts/c2-v180-substrate-d-session-20260828/final-physical-bank0.bin"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
KNOWN = ROOT / "docs/known-issues.md"
V160_SESSION = ROOT / "config/c2-v160-item1-only-r1-public2-session.json"
V170_SESSION = ROOT / "config/c2-v170-release-d-session.json"
BLOCK3_SESSION = ROOT / "config/c2-v17-block3-r10-acceptance-session.json"
REPAIR = ARCH / "c2.3-v1.8-capture-hybrid-responsiveness-repair-receipt.json"
REPL_SOURCE = ROOT / "src/repl.c"
ERROR_TEXTS = ROOT / "config/error-texts.json"
ELF = ROOT / "build/c2.3/v1.8-capture-hybrid-product-card-r1/wplto/lisp65-c2-substitution-linked.prg.elf"
V18_MEDIA_ELF = ROOT / "build/c2.3/v1.8.0-substrate-media/canonical-product/final/lisp65-c2-substitution-linked.prg.elf"
V17_ELF = ROOT / "build/c2.3/v1.7.0-release-media-r5/canonical-product/final/lisp65-c2-substitution-linked.prg.elf"
BLOCK3_ELF = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r10/wplto/lisp65-c2-substitution-linked.prg.elf"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: V1.8.0 SUBSTRATE D-SESSION HARDWARE GREEN; OWNER-SHIP-PENDING"


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


def era_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout


def instruction_records(elf: Path, name: str) -> list[dict[str, Any]]:
    output = subprocess.run(
        [str(OBJDUMP), "-d", f"--disassemble-symbols={name}", str(elf)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)"
            r"([a-z][a-z0-9]*)\s*(.*?)\s*$", line)
        if match is None:
            continue
        rows.append({
            "address": int(match.group(1), 16),
            "encoding": bytes.fromhex(match.group(2)),
            "mnemonic": match.group(3),
            "operand": match.group(4).split(";", 1)[0].strip(),
        })
    require(rows, f"function disassembly absent: {elf}:{name}")
    return rows


def absolute_target(row: dict[str, Any]) -> int | None:
    encoding = bytes(row["encoding"])
    if row["mnemonic"] not in ("jsr", "jmp") or len(encoding) != 3:
        return None
    return encoding[1] | (encoding[2] << 8)


def replay_cursor_left(rows: list[dict[str, Any]], *, event_index: int,
                       abort_target: int) -> dict[str, Any]:
    """Execute the exact post-event classifier from linked machine bytes."""
    require(event_index + 2 < len(rows)
            and bytes(rows[event_index + 1]["encoding"])[0] == 0xB2,
            "linked native event-code load is absent")
    memory: dict[int, int] = {}
    for index in range(event_index):
        first = bytes(rows[index]["encoding"])
        second = (bytes(rows[index + 1]["encoding"])
                  if index + 1 < event_index else b"")
        if len(first) == 2 and first[0] == 0xA2 \
                and len(second) == 2 and second[0] == 0x86:
            memory[second[1]] = first[1]
    by_address = {int(row["address"]): row for row in rows}
    pc = int(rows[event_index + 2]["address"])
    accumulator = 0x9D
    zero = False
    path: list[str] = []
    for _step in range(40):
        row = by_address.get(pc)
        require(row is not None, f"native cursor replay left repl at 0x{pc:04x}")
        encoding = bytes(row["encoding"])
        opcode = encoding[0]
        path.append(f"0x{pc:04X}:{encoding.hex()}")
        next_pc = pc + len(encoding)
        if opcode == 0xC9 and len(encoding) == 2:       # CMP #imm
            zero = accumulator == encoding[1]
        elif opcode == 0xD0 and len(encoding) == 2:     # BNE
            if not zero:
                offset = encoding[1] - (0x100 if encoding[1] & 0x80 else 0)
                next_pc += offset
        elif opcode == 0xF0 and len(encoding) == 2:     # BEQ
            if zero:
                offset = encoding[1] - (0x100 if encoding[1] & 0x80 else 0)
                next_pc += offset
        elif opcode == 0x4C and len(encoding) == 3:     # JMP abs
            next_pc = encoding[1] | (encoding[2] << 8)
        elif opcode == 0xA8:                            # TAY
            pass
        elif opcode == 0x29 and len(encoding) == 2:     # AND #imm
            accumulator &= encoding[1]
            zero = accumulator == 0
        elif opcode == 0xA5 and len(encoding) == 2:     # LDA zp
            require(encoding[1] in memory,
                    f"cursor rejection reads unknown ZP cell ${encoding[1]:02x}")
            accumulator = memory[encoding[1]]
            zero = accumulator == 0
        elif opcode == 0xA9 and len(encoding) == 2:     # LDA #imm
            accumulator = encoding[1]
            zero = accumulator == 0
        elif opcode == 0x20 and len(encoding) == 3:     # JSR abs
            target = encoding[1] | (encoding[2] << 8)
            require(target == abort_target,
                    f"cursor rejection reached unexpected call 0x{target:04x}")
            return {
                "physical_code": "0x9D",
                "result": "lisp_abort_code",
                "error_code": accumulator,
                "error_id": "LISP65_ERR_READER_INVALID_TOKEN",
                "partial_line_evaluated": False,
                "path": path,
            }
        else:
            raise ResultError(
                f"unsupported opcode on cursor rejection path: {encoding.hex()}")
        pc = next_pc
    raise ResultError("native cursor rejection path did not terminate")


def native_prompt_model(elf: Path) -> dict[str, Any]:
    truth = MEDIA.BASE.ElfTruth.read(elf, llvm_readobj=READOBJ)
    repl = truth.symbol("repl")
    targets = {name: truth.symbol(name).value for name in (
        "lisp_input_event", "vm_run_dir", "__call_indir", "lisp_abort_code",
        "lisp_abort_symbol")}
    rows = instruction_records(elf, "repl")
    calls = [(index, row, absolute_target(row))
             for index, row in enumerate(rows) if row["mnemonic"] == "jsr"]
    event = [(index, row) for index, row, target in calls
             if target == targets["lisp_input_event"]]
    banner = [(index, row) for index, row, target in calls
              if target == targets["vm_run_dir"]]
    indirect = [row for _index, row, target in calls
                if target == targets["__call_indir"]]
    require(len(event) == 1 and len(banner) == 1 and indirect == [],
            "native prompt caller topology drift")
    banner_index, banner_row = banner[0]
    reentries = [absolute_target(row) for row in rows[banner_index + 1:]
                 if row["mnemonic"] == "jmp"
                 and absolute_target(row) is not None
                 and repl.value <= int(absolute_target(row))
                 < int(event[0][1]["address"])]
    require(reentries, "startup banner has no static native-loop re-entry")
    abort_rows = instruction_records(elf, "lisp_abort_code")
    require(absolute_target(abort_rows[-1]) == targets["lisp_abort_symbol"],
            "lisp_abort_code stopped being a non-returning abort tail")
    replay = replay_cursor_left(
        rows, event_index=event[0][0], abort_target=targets["lisp_abort_code"])
    require(replay["error_code"] == 5, "Cursor Left error identity drift")
    return {
        "ELF": bind(elf),
        "repl": {"address": f"0x{repl.value:04X}", "bytes": repl.bytes,
                 "section": repl.section},
        "input_owner": "resident repl machine function with inline C collector",
        "event_call": {
            "address": f"0x{int(event[0][1]['address']):04X}",
            "encoded_target": f"0x{targets['lisp_input_event']:04X}",
            "ELF_target": "lisp_input_event",
            "count": 1,
        },
        "startup_banner_call": {
            "address": f"0x{int(banner_row['address']):04X}",
            "encoded_target": f"0x{targets['vm_run_dir']:04X}",
            "ELF_target": "vm_run_dir",
            "count": 1,
            "static_native_loop_reentry": f"0x{int(reentries[0]):04X}",
        },
        "indirect_editor_calls": len(indirect),
        "boot_or_runtime_editor_rebind": False,
        "cursor_left_replay": replay,
    }


def addresses() -> dict[str, int]:
    truth = MEDIA.BASE.ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    return {name: truth.symbol(name).value for name in ("nsym", "npool")}


def observed() -> dict[str, int]:
    raw = CAPTURE.read_bytes()
    require(len(raw) == 65536, "physical Bank-0 capture size drift")
    where = addresses()
    return {name: int.from_bytes(raw[addr:addr + 2], "little")
            for name, addr in where.items()}


def derive() -> dict[str, Any]:
    session = load(SESSION)
    media = load(MEDIA_RECEIPT)
    v160 = load(V160_SESSION)
    v170 = load(V170_SESSION)
    block3 = load(BLOCK3_SESSION)
    repair = load(REPAIR)
    error_texts = load(ERROR_TEXTS)
    v17_prompt = native_prompt_model(V17_ELF)
    v18_prompt = native_prompt_model(V18_MEDIA_ELF)
    block3_prompt = native_prompt_model(BLOCK3_ELF)
    error_row = next(row for row in error_texts["entries"]
                     if row["code"] == 5)
    obs = observed()
    free = {"symbol_slots": 752 - obs["nsym"],
            "namepool_bytes": 10208 - obs["npool"]}
    require(session["format"] == "lisp65-c2-v180-substrate-d-session-v3"
            and session["configuration"]["loaded_library_roles"] == [],
            "active substrate session world drift")
    require(media["accepted_pair"] == MEDIA.accepted_pair(),
            "substrate result pair drift")
    require(obs == {"nsym": 639, "npool": 8702}
            and free == {"symbol_slots": 113, "namepool_bytes": 1506},
            "substrate physical D5 observation drift")
    v160_left = next(row for row in v160["rows"]
                     if row["id"] == "I1-left-insert")
    v170_cursor_rows = [row for row in v170["rows"]
                        if "cursor" in row["id"].lower()
                        or "left" in json.dumps(row).lower()]
    published_repl = era_bytes("8ab12662", "src/repl.c")
    current_repl = REPL_SOURCE.read_bytes()
    require(v160_left["actions"][0] == "submit (read-line)"
            and v170_cursor_rows == []
            and "(read-line)" not in json.dumps(block3["rows"])
            and session["configuration"]["loaded_library_roles"] == []
            and published_repl == current_repl
            and v17_prompt["ELF"]["sha256"] ==
                "e8ca0734427cbe22c6d60dfbba2cc141b8c98dd031beecdab8c57aa7d499efab"
            and v18_prompt["ELF"]["sha256"] ==
                "67f89b7354d0f473c3057508ed6a47af69edad29c0807bc1d6f031442daaceab"
            and block3_prompt["ELF"]["sha256"] ==
                "a5c5af3784ca7202258457fbe0a843911108400374b552a92091876f422bbd60"
            and error_row["c_name"] == "LISP65_ERR_READER_INVALID_TOKEN"
            and error_row["text"] == "reader: invalid token"
            and repair["frozen_pair_before"] == repair["frozen_pair_after"],
            "native cursor attribution chain drift")
    return {
        "format": "lisp65-c2-v180-substrate-d-session-result-v1",
        "recorded_on": "2026-08-28",
        "status": STATUS,
        "authority": {
            "session_binding_commit": "f886932d",
            "session": bind(SESSION),
            "media": bind(MEDIA_RECEIPT),
            "result_plan_section": section_bind(
                PLAN, "## v1.8 substrate D-session result — 2026-08-28"),
            "native_cursor_attribution_section": section_bind(
                PLAN, "## Native-prompt cursor attribution — three-way question closed — 2026-08-28"),
            "known_issue_section": section_bind(
                KNOWN,
                "## Active input limitation: Cursor Left/Right at the native `lisp65>` prompt"),
        },
        "media_readback": {
            "product": {"remote_name": "V180P.D81",
                        "sha256": media["media"]["product"]["sha256"]},
            "library": {"remote_name": "V180L.D81",
                        "sha256": media["media"]["library"]["sha256"]},
            "result": "both pre-boot readbacks SHA-identical",
        },
        "choreography": {
            "complete_deploy_and_readback_cycles": 1,
            "deployment_invocations": 1,
            "owner_keyboard_only": True,
            "post_boot_automated_device_access_before_final_stop": 0,
            "protocol_false_reds": 1,
            "final_physical_bank0_captures": 1,
            "final_resume": False,
        },
        "native_cursor_attribution": {
            "status": "PASS: THREE-WAY NATIVE CURSOR ATTRIBUTION CLOSED HOST-ONLY",
            "classification": "NEVER SUPPORTED AT NATIVE PROMPT; NOT V1.8 REGRESSION",
            "observed_world": {
                "loaded_library_roles": [],
                "v16core_loaded": False,
                "input_owner": "resident repl machine function with inline C collector",
            },
            "hypotheses": {
                "boot_time_only_v16core_binding": {
                    "verdict": "REFUTED",
                    "reason": "the delivered repl machine function returns from its one startup vm_run_dir banner call to a fixed inline collector; it has one direct lisp_input_event call and zero __call_indir editor calls",
                },
                "v1_8_candidate_regression": {
                    "verdict": "REFUTED",
                    "reason": "the sealed v1.7 release ELF follows Cursor Left to the same stable error code 5 before evaluation",
                },
                "nthcdr_aliasing_on_observed_path": {
                    "verdict": "REFUTED",
                    "reason": "the observed path never enters Lisp read-line, and the route-only repair did not alter the frozen product pair",
                },
            },
            "delivered_v1_8_ELF": v18_prompt,
            "sealed_v1_7_release_replay": v17_prompt,
            "message_origin": {
                "producer": "native resident C collector inside repl",
                "stage": "key classification before Return, parsing, or evaluation",
                "stable_code": error_row["code"],
                "stable_id": error_row["c_name"],
                "catalog_text": error_row["text"],
                "shared_vocabulary_note": "the text belongs to the common error catalog; the linked call site, not the words alone, identifies the C collector as producer",
                "partial_line_evaluated": False,
            },
            "historical_rows": {
                "v1_6_cursor_first_action": v160_left["actions"][0],
                "v1_6_cursor_surface": "explicit Bank-2 Lisp read-line after require v16core",
                "v1_7_release_D_session_cursor_rows": len(v170_cursor_rows),
            },
            "block3_correction": {
                "session_explicit_read_line_entries": 0,
                "native_prompt_ELF": block3_prompt,
                "conclusion": "Block 3 never rewired native repl to %read-line-loop; its line-editor row omitted the explicit (read-line) entry and cannot support a native-prompt claim",
            },
            "source_identity": {
                "published_v1_7_source_commit": "8ab12662",
                "path": "src/repl.c",
                "byte_identical": True,
                "sha256": hashlib.sha256(current_repl).hexdigest(),
            },
            "nthcdr_repair": {
                "reachable_from_observed_surface": False,
                "reason": "v16core was not loaded and the frozen product pair stayed SHA-identical across the route-side repair",
                "frozen_pair_unchanged": True,
            },
            "execution_accounting": {
                "WPLTO_runs": 0,
                "product_links": 0,
                "media_builds": 0,
                "device_contacts": 0,
                "ELF_machine_paths_replayed": 3,
            },
            "future_session_rule": "bare boot with zero optional roles is a separate pre-library row group",
        },
        "rows": [
            {"id": "S-boot-and-init-absence", "result": "PASS",
             "observation": "WORKBENCH 1.7.0 and native lisp65>; no INIT.L65 output or error"},
            {"id": "S-withdrawn-native-cursor-row",
             "result": "PROTOCOL-FALSE-RED", "acceptance_weight": 0,
             "product_defect": False, "key": "Cursor Left / PETSCII $9D",
             "observation": "*** reader: invalid token",
             "mechanism": "$9D & $7F = $1D; native C collector visibly rejects unhandled controls",
             "correction": "cursor evidence belongs to optional v16core explicit (read-line), not lisp65>"},
            {"id": "S-native-line-input-and-delete", "result": "PASS",
             "observation": "leading Delete no-op; corrected form returns (1 3)"},
            {"id": "S-abort-recovery", "result": "PASS",
             "form": "(>= nil 32)", "observation": "*** vm: type error; prompt practically immediate",
             "follow_up": {"form": "(list 1 3)", "value": "(1 3)"}},
            {"id": "D-setup-published-call", "result": "PASS",
             "form": "(defun v18-perf-probe (x) (+ x 1))",
             "observation": "v18-perf-probe"},
            {"id": "D-list-read", "result": "PASS", "frames": 0,
             "value": "2", "observation": "0 2"},
            {"id": "D-list-write", "result": "PASS", "frames": 1,
             "value": "(9 2)", "observation": "1 (9 2)"},
            {"id": "D-string-op", "result": "PASS", "frames": 0,
             "value": "98", "observation": "0 98"},
            {"id": "D-published-call", "result": "PASS", "frames": 0,
             "value": "42", "observation": "0 42"},
        ],
        "D5": {
            "status": "PASS: RELEASE-TERMINAL D5 HEADROOM GREEN",
            "capture": bind(CAPTURE),
            "ELF_derived_addresses": {
                name: f"0x{addr:04X}" for name, addr in addresses().items()},
            "observed": obs,
            "limits": {"symbols": 752, "namepool_bytes": 10208},
            "free": free,
            "minimum_free": {"symbol_slots": 32, "namepool_bytes": 384},
        },
        "claim_limit": {
            "accepts": ["v1.8.0-substrate-neutrality",
                        "v1.8.0-release-D5", "v1.8.0-performance-smoke"],
            "excludes": ["Capture activation", "lossless user input",
                         "Comfort", "Matcher/Blink", "Block-3", "$22",
                         "native-lisp65-prompt-cursor-navigation", "publication"],
            "known_issue_stays_open": "v1.5 fast-typing input loss",
        },
        "execution_accounting": {
            "forms_submitted": 8, "unsupported_control_attempts": 1,
            "device_contacts": 1, "new_WPLTO_runs": 0,
            "new_product_links": 0, "new_product_cards": 0,
            "new_media_builds": 0,
        },
        "next": "owner Ship halt",
    }


def verify(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "v1.8 substrate device result drift")
    require(all(row.get("frames", 0) <= 2 for row in value["rows"]),
            "performance ceiling exceeded")
    false_red = value["rows"][1]
    require(false_red["acceptance_weight"] == 0
            and false_red["product_defect"] is False,
            "protocol false red gained product weight")
    attribution = value["native_cursor_attribution"]
    require(attribution["observed_world"]["v16core_loaded"] is False
            and set(row["verdict"] for row in
                    attribution["hypotheses"].values()) == {"REFUTED"}
            and attribution["delivered_v1_8_ELF"]
                ["boot_or_runtime_editor_rebind"] is False
            and attribution["delivered_v1_8_ELF"]
                ["cursor_left_replay"]["error_code"] == 5
            and attribution["sealed_v1_7_release_replay"]
                ["cursor_left_replay"]["error_code"] == 5
            and attribution["historical_rows"]["v1_7_release_D_session_cursor_rows"] == 0
            and attribution["block3_correction"]
                ["session_explicit_read_line_entries"] == 0
            and attribution["nthcdr_repair"]["reachable_from_observed_surface"] is False,
            "native cursor attribution regained a regression path")
    require(value["D5"]["free"]["symbol_slots"] >= 32
            and value["D5"]["free"]["namepool_bytes"] >= 384,
            "release-terminal D5 floor missed")


def selftest() -> None:
    base = derive()
    cases = {
        "promote-protocol-false-red": lambda x: x["rows"][1].update(
            acceptance_weight=1),
        "claim-native-prompt-cursor": lambda x: x["claim_limit"]["excludes"].remove(
            "native-lisp65-prompt-cursor-navigation"),
        "exceed-performance-ceiling": lambda x: x["rows"][6].update(frames=3),
        "lower-symbol-headroom": lambda x: x["D5"]["free"].update(symbol_slots=31),
        "resume-after-final-capture": lambda x: x["choreography"].update(final_resume=True),
        "pretend-v16core-loaded": lambda x: x["native_cursor_attribution"]["observed_world"].update(v16core_loaded=True),
        "invent-boot-editor-rebind": lambda x: x["native_cursor_attribution"]["delivered_v1_8_ELF"].update(boot_or_runtime_editor_rebind=True),
        "hide-v17-error": lambda x: x["native_cursor_attribution"]["sealed_v1_7_release_replay"]["cursor_left_replay"].update(error_code=0),
        "promote-block3-prompt-claim": lambda x: x["native_cursor_attribution"]["block3_correction"].update(session_explicit_read_line_entries=1),
    }
    rejected = []
    for name, mutate in cases.items():
        value = copy.deepcopy(base)
        mutate(value)
        try:
            verify(value)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "v1.8 substrate result mutation survived")
    print(f"v1.8 substrate device result: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "write":
        RESULT.write_bytes(canonical(derive()))
        verify(load(RESULT))
        print("v1.8 substrate device result: WRITE PASS Ship=pending")
    elif action == "check":
        verify(load(RESULT))
        print("v1.8 substrate device result: CHECK PASS Ship=pending")
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: c2_v180_substrate_device_result.py write|check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8 substrate device result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
