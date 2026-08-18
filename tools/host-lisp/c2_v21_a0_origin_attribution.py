#!/usr/bin/env python3
"""Attribute the repeated Link-112/113 PETSCII $A0 input byte.

This is a desk-only attribution.  It binds the two captured REPL buffers,
the emitted Link-113 editor/queue path, and the pinned MEGA65 keyboard queue
producer.  It also runs a faithful small model of read_line's type/DEL/retype
behaviour.  It does not change product bytes or authorize the held WYSIWYG
card or a device contact.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ELF112 = ROOT / (
    "build/c2.3/v2.1-full-span-convergence-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
ELF113 = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CAP112 = ROOT / "build/c2.3/v2.1-link112-d2-full-span-oracle-capture"
CAP113 = ROOT / "build/c2.3/v2.1-link113-d2-root-reader-rescue"
R112 = ARCH / "c2.3-v2.1-link112-d2-probe-oracle-capture-receipt.json"
R113 = ARCH / "c2.3-v2.1-link113-d2-bank4-root-reader-rescue-receipt.json"
PRIOR = ARCH / "c2.3-v2.1-reader-caller-path-attribution-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-a0-origin-attribution-receipt.json"
REPL = ROOT / "src/repl.c"
SCREEN = ROOT / "src/screen.c"
INTERRUPT = ROOT / "src/interrupt.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
CORE = ROOT / "build/upstream-verification/mega65-core"
MATRIX = CORE / "src/vhdl/matrix_to_ascii.vhdl"
IOMAPPER = CORE / "src/vhdl/iomapper.vhdl"
UART = CORE / "src/vhdl/c65uart.vhdl"
CORE_SNAPSHOT = ROOT / (
    "tests/bytecode/dialect-v2/fixtures/"
    "c2-l-full-keymap-core-source-snapshot.json")

AUTHORIZATION = "85f70027"
SUCCESSOR_AUTHORIZATION = "01914313"
FORMAT = "lisp65-c2.3-v2.1-a0-origin-attribution-v1"
STATUS = "ATTRIBUTED: SHIFTED-TABLE-SPACE-EVENT; EDITOR-INJECTION-REFUTED"
RECORDED_ON = "2026-08-17"
EXPECTED_LINES = {
    "Link112": b"(defun test-probe (x)\xa0(+ x 1))",
    "Link113": b"(defun trace-probe (x)\xa0(+ x 1))",
}
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
MATRIX_SHA = "068dab4dfea391e8c6ac06ac31108be2e29d9d4510becbcbc1b2125bcb535536"
IOMAPPER_SHA = "942a08a4622001048c38b065bee11edf1e4926f2db29dfc03f67bb7257db4bba"
UART_SHA = "3679b4cce25823c3f813cdfa8fdc0038c9cfbbadfe86fb960e3db373670915b6"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in (
        "$a0 origin attribution commissioned",
        "bind the `$a0` position",
        "audit the injection candidates",
        "host-model an edit sequence",
        "the wysiwyg card is held meanwhile",
    ):
        require(token in text, f"authorization token absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def table_body(text: str, name: str) -> str:
    match = re.search(
        rf"\bsignal\s+{re.escape(name)}\s*:\s*key_matrix_t\s*:=\s*\("
        rf"(.*?)\n\s*\);", text, re.DOTALL | re.IGNORECASE)
    require(match is not None, f"core key table absent: {name}")
    return match.group(1)


def table_value(text: str, name: str, index: int) -> int:
    match = re.search(
        rf"^\s*{index}\s*=>\s*x\"([0-9a-f]{{2}})\"",
        table_body(text, name), re.MULTILINE | re.IGNORECASE)
    require(match is not None, f"core key table index absent: {name}[{index}]")
    return int(match.group(1), 16)


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    at = symbol.value - section.address
    require(0 <= at <= len(raw) and at + symbol.bytes <= len(raw),
            f"symbol outside section: {name}")
    return raw[at:at + symbol.bytes]


def disassemble(name: str) -> str:
    result = subprocess.run(
        [str(ROOT / "tools/llvm-mos/bin/llvm-objdump"), "-d",
         f"--disassemble-symbols={name}", str(ELF113)], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def captured_lines(truths: dict[str, ElfTruth]) -> dict[str, Any]:
    captures = {"Link112": CAP112, "Link113": CAP113}
    rows: dict[str, Any] = {}
    for name, directory in captures.items():
        symbol = truths[name].symbol("repl.buf")
        require(symbol.value == 0xBC89 and symbol.bytes == 192,
                f"{name} captured REPL-buffer identity drift")
        raw = (directory / "physical-bank0.bin").read_bytes()
        require(len(raw) == 0x10000, f"{name} Bank-0 extent drift")
        window = raw[symbol.value:symbol.value + symbol.bytes]
        end = window.find(b"\0")
        require(end >= 0, f"{name} REPL buffer is not terminated")
        line = window[:end]
        expected = EXPECTED_LINES[name]
        require(line == expected, f"{name} captured line drift")
        require(line.count(b"\xA0") == 1, f"{name} $A0 cardinality drift")
        at = line.index(0xA0)
        require(line[at - 3:at + 2] == b"(x)\xA0(",
                f"{name} $A0 grammatical position drift")
        require(at + 1 < len(line) and at not in (0, len(line) - 1),
                f"{name} $A0 moved to a boundary")
        require(len(line) + 8 <= 40,
                f"{name} line now reaches the conservative wrap boundary")
        rows[name] = {
            "buffer_symbol": "repl.buf", "address": f"0x{symbol.value:04x}",
            "buffer_capacity": symbol.bytes, "line_bytes": len(line),
            "line_hex": line.hex(),
            "visible_ascii": line.replace(b"\xA0", b" ").decode("ascii"),
            "a0_offset_zero_based": at,
            "a0_context_hex": line[at - 3:at + 2].hex(),
            "a0_context": "(x)<A0>(",
            "classification": "semantic separator between parameter list and body",
            "inside_function_name": False, "at_line_end": False,
            "at_wrap_boundary": False,
            "normal_space_offsets": [i for i, value in enumerate(line)
                                     if value == 0x20],
            "sha256": digest(line),
        }
    require(rows["Link112"]["a0_context"] == rows["Link113"]["a0_context"],
            "captures no longer share one grammatical transition")
    return rows


def core_queue_path() -> dict[str, Any]:
    snapshot = load(CORE_SNAPSHOT)
    require(snapshot.get("core_commit") == CORE_COMMIT,
            "pinned core commit drift")
    expected = snapshot.get("source_sha256", {})
    require(expected.get("src/vhdl/matrix_to_ascii.vhdl") == MATRIX_SHA
            and expected.get("src/vhdl/iomapper.vhdl") == IOMAPPER_SHA
            and expected.get("src/vhdl/c65uart.vhdl") == UART_SHA,
            "pinned core source authority drift")
    require(digest(MATRIX.read_bytes()) == MATRIX_SHA
            and digest(IOMAPPER.read_bytes()) == IOMAPPER_SHA
            and digest(UART.read_bytes()) == UART_SHA,
            "local pinned core source drift")
    matrix = MATRIX.read_text(encoding="utf-8")
    iomapper = IOMAPPER.read_text(encoding="utf-8")
    uart = UART.read_text(encoding="utf-8")
    normal_space = table_value(matrix, "matrix_petscii_normal", 60)
    shifted_space = table_value(matrix, "matrix_petscii_shifted", 60)
    shifted_close = table_value(matrix, "matrix_petscii_shifted", 32)
    require((normal_space, shifted_space, shifted_close) == (0x20, 0xA0, 0x29),
            "pinned PETSCII transition drift")
    require(
        "bucky_key_internal(0)='1' or bucky_key_internal(1)='1'"
        in matrix and "petscii_matrix := matrix_petscii_shifted;" in matrix
        and "petscii_key <= petscii_matrix(key_num);" in matrix,
        "shifted PETSCII producer selection drift")
    for token in (
        "petscii_key_buffer(key_buffer_count) <= petscii_key;",
        "bucky_key_buffer(key_buffer_count) <= bucky_key;",
        "petscii_key_buffered <= petscii_key_buffer(0);",
        "bucky_key_buffered <= bucky_key_buffer(0);",
    ):
        require(token in iomapper, f"core queue pairing drift: {token}")
    require("$D60A.0 UARTMISC:MODKEYLSHFT" in uart
            and "$D60A.1 UARTMISC:MODKEYRSHFT" in uart
            and "fastio_rdata(6 downto 0) <= unsigned(bucky_key_buffered"
            in uart and "$D619 UARTMISC:PETSCIIKEY" in uart
            and "fastio_rdata <= unsigned(porto);" in uart,
            "core queue register contract drift")
    return {
        "pinned_core_commit": CORE_COMMIT,
        "normal_space": f"0x{normal_space:02x}",
        "shifted_space": f"0x{shifted_space:02x}",
        "shifted_close_parenthesis": f"0x{shifted_close:02x}",
        "key_indices": {"close_parenthesis_9": 32, "space": 60},
        "producer_rule": (
            "the shifted PETSCII table emits $29 for key 9 and $A0 for Space; "
            "the normal table emits $20 for Space"),
        "queue_pairing": (
            "PETSCII code and modifier bits are enqueued in the same slot and "
            "dequeued together"),
        "capture_limit": (
            "read_line retained event.code but not event.modifiers, so the "
            "capture cannot distinguish physical key overlap from scan/debounce "
            "timing or another shifted-table selector"),
    }


def delivered_editor_path(truth: ElfTruth) -> dict[str, Any]:
    repl = REPL.read_text(encoding="utf-8")
    screen = SCREEN.read_text(encoding="utf-8")
    interrupt = INTERRUPT.read_text(encoding="utf-8")
    window = WINDOW.read_text(encoding="utf-8")
    for token in (
        "c = event.code;",
        "if (c == 0x14)",
        "if (n > floor) { n--; kb_del(); }",
        "if (c < 0x20 || (c >= 0x80 && c < 0xA0)) continue;",
        "buf[n++] = (char)c;",
    ):
        require(token in repl, f"read_line source path drift: {token}")
    require("event.modifiers" not in repl,
            "read_line now consumes modifier evidence")
    require("scr_host_buf" not in repl and "scr_base" not in repl,
            "REPL gained a screen-readback path")
    require("void scr_backspace(void)" in screen
            and "*cell(crow, ccol) = 0x20;" in screen,
            "screen DEL/erase behaviour drift")
    require("scr_host_buf" in screen and "#ifndef __mos__" in screen,
            "host-only screen readback boundary drift")
    require("if (event->code != LISP65_KEY_RUN_STOP) return 1u;" in interrupt,
            "lisp_input_event raw-code return drift")
    require("lda $d619" in window and "sta $d619" in window
            and "sta (__rc2),z" in window,
            "product queue raw-code handoff drift")

    repl_dis = disassemble("repl")
    queue_dis = disassemble("c2_kernal_event_poll")
    repl_symbol = truth.symbol("repl")
    queue_symbol = truth.symbol("c2_kernal_event_poll")
    stores = re.findall(r"^\s*([0-9a-f]+):.*\bsta\s+\$bc89,x\b",
                        repl_dis, re.MULTILINE)
    terminators = re.findall(r"^\s*([0-9a-f]+):.*\bstz\s+\$bc89,x\b",
                             repl_dis, re.MULTILINE)
    history_loads = re.findall(r"^\s*([0-9a-f]+):.*\blda\s+\$bc89,y\b",
                               repl_dis, re.MULTILINE)
    require(stores == ["ac79"] and terminators == ["ab9d"]
            and history_loads == ["ab5b"],
            "emitted REPL buffer access set drift")
    require("cmp\t#$14" in repl_dis and "cmp\t#$a0" in repl_dis
            and "a9 20" in repl_dis and "sta\t($4),y" in repl_dis,
            "emitted DEL/filter/store path drift")
    for token in ("lda\t$d619", "sta\t$d619", "sta\t($4),z"):
        require(token in queue_dis, f"emitted queue handoff drift: {token}")
    return {
        "source": {
            "queue": "$D619 copied unchanged to event.code",
            "input_event": "ordinary event.code returned unchanged",
            "DEL": "decrement n; screen backspace writes $20 only",
            "insert": "no insert operation exists",
            "screen_readback": "none in target REPL; host simulation only",
            "history": "reads/copies the existing REPL buffer; synthesizes no byte",
            "append": "the sole new input byte is event.code after letter-case mapping",
        },
        "emitted": {
            "repl": {"address": f"0x{repl_symbol.value:04x}",
                     "bytes": repl_symbol.bytes,
                     "sha256": digest(symbol_bytes(truth, "repl"))},
            "queue": {"address": f"0x{queue_symbol.value:04x}",
                      "bytes": queue_symbol.bytes,
                      "sha256": digest(symbol_bytes(truth, "c2_kernal_event_poll"))},
            "buffer_append_stores": [f"0x{int(x, 16):04x}" for x in stores],
            "buffer_terminators": [f"0x{int(x, 16):04x}" for x in terminators],
            "history_loads": [f"0x{int(x, 16):04x}" for x in history_loads],
            "screen_erase_store": "0xaca5: LDA #$20; $aca9: STA (screen),Y",
        },
        "editor_can_synthesize_a0_without_a0_event": False,
        "DEL_can_inject_a0": False,
        "screen_readback_can_inject_a0": False,
    }


def model_read_line(events: bytes) -> bytes:
    """Faithful model of the delivered DEVICE_KB edit subset at floor zero."""
    out = bytearray()
    for raw in events:
        value = raw
        if value in (0x0A, 0x0D):
            break
        if value in (0x93, 0x13):
            continue
        if value == 0x14:
            if out:
                out.pop()
            continue
        if value == 0x91:
            # Recall only echoes the buffer already present; it cannot create
            # a new byte.  Model an empty historical row for this attribution.
            continue
        if value < 0x20 or 0x80 <= value < 0xA0:
            continue
        if ord("A") <= value <= ord("Z"):
            value += 0x20
        elif 0xC1 <= value <= 0xDA:
            value -= 0x80
        if len(out) < 191:
            out.append(value)
    return bytes(out)


def edit_model(core: dict[str, Any]) -> dict[str, Any]:
    normal_space = int(core["normal_space"], 16)
    shifted_space = int(core["shifted_space"], 16)
    shifted_close = int(core["shifted_close_parenthesis"], 16)
    cases: dict[str, tuple[bytes, bytes]] = {}
    for name, captured in EXPECTED_LINES.items():
        canonical_line = captured.replace(b"\xA0", b" ")
        boundary = captured.index(0xA0)
        prefix = canonical_line[:boundary - 1]
        suffix = canonical_line[boundary + 1:]
        direct = canonical_line + b"\r"
        correct_after_del = (canonical_line[:boundary] + b"z\x14"
                             + bytes((normal_space,))
                             + canonical_line[boundary + 1:] + b"\r")
        delete_and_retype_separator = (
            canonical_line[:boundary + 1] + b"\x14"
            + bytes((normal_space,)) + canonical_line[boundary + 1:] + b"\r")
        shifted_transition = (prefix + bytes((shifted_close, shifted_space))
                              + suffix + b"\r")
        cases[f"{name}-direct"] = (direct, canonical_line)
        cases[f"{name}-DEL-retype"] = (correct_after_del, canonical_line)
        cases[f"{name}-separator-DEL-retype"] = (
            delete_and_retype_separator, canonical_line)
        cases[f"{name}-shifted-transition"] = (shifted_transition, captured)
    outcomes = {name: model_read_line(events) for name, (events, _) in cases.items()}
    require(all(outcomes[name] == expected
                for name, (_, expected) in cases.items()),
            "read_line edit model no longer matches expected outcomes")

    alphabet = b"x() z" + bytes((0x14,))
    probes = [b"", *[bytes((x,)) for x in alphabet]]
    probes += [bytes((a, b, c)) for a in alphabet for b in alphabet
               for c in alphabet]
    require(all(0xA0 not in model_read_line(events) for events in probes),
            "editor model synthesized $A0 without an $A0 event")
    return {
        "natural_sequences": {
            name: {"event_hex": cases[name][0].hex(),
                   "result_hex": outcomes[name].hex(),
                   "contains_a0": 0xA0 in outcomes[name]}
            for name in cases
        },
        "exhaustive_small_model": {
            "event_sequences_checked": len(probes),
            "alphabet_hex": alphabet.hex(),
            "a0_events_present": 0,
            "outputs_containing_a0": 0,
        },
        "a0_without_a0_input_event": False,
        "shifted_transition_reproduces_Link112": (
            outcomes["Link112-shifted-transition"] == EXPECTED_LINES["Link112"]),
        "shifted_transition_reproduces_Link113": (
            outcomes["Link113-shifted-transition"] == EXPECTED_LINES["Link113"]),
        "interpretation": (
            "type/DEL/retype never creates $A0 from canonical events; the exact "
            "Shift+) then shifted-table Space transition reproduces both captures"),
    }


def derive() -> dict[str, Any]:
    truths = {
        "Link112": ElfTruth.read(
            ELF112, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
            include_section_data=True),
        "Link113": ElfTruth.read(
            ELF113, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
            include_section_data=True),
    }
    r112, r113, prior = load(R112), load(R113), load(PRIOR)
    require(r112["staged_object"]["fresh_name"] is True
            and r113["three_way_comparison"]["staged_object"]["metadata"]
                ["noncanonical_literal_byte"] == "0xa0"
            and prior["status"] == "ATTRIBUTED: INVISIBLE-PETSCII-A0-INGRESS",
            "upstream capture/attribution authority drift")
    captures = captured_lines(truths)
    core = core_queue_path()
    editor = delivered_editor_path(truths["Link113"])
    model = edit_model(core)
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "captured_buffers": captures,
        "pinned_core_queue": core,
        "delivered_editor": editor,
        "edit_model": model,
        "attribution": {
            "immediate_origin": (
                "a queued raw PETSCII $A0 Space event selected from the shifted "
                "PETSCII table before read_line"),
            "repetition_signature": (
                "both independent lines contain the same (x)$A0( grammatical "
                "separator immediately after the shifted ')' keystroke; this is "
                "one repeated key transition, not two corruptions inside two names"),
            "editor_injection_hypothesis": "REFUTED",
            "DEL_insert_erase_hypothesis": "REFUTED",
            "screen_readback_hypothesis": "REFUTED",
            "queue_producer_shifted_table_hypothesis": "SUPPORTED-AND-REPRODUCED",
            "observed_a0_is_semantic_whitespace": True,
            "wysiwyg_a0_to_space_preserves_observed_intent": True,
            "physical_finger_intent": "UNRESOLVED",
            "modifier_origin": (
                "UNRESOLVED: physical Shift overlap, matrix scan/debounce timing, "
                "or another shifted-table selector cannot be separated because "
                "read_line discarded the queued modifier byte"),
            "owner_testimony_respected": True,
            "fix_authorized": False,
            "wysiwyg_card_held": True,
            "device_contact_authorized": False,
        },
        "recommendation": (
            "The delivered editor is not an injector. For both observed forms, "
            "$A0 occupies intended whitespace, so boundary normalization to $20 "
            "is sufficient and intent-preserving; resuming that held card still "
            "requires owner/reviewer disposition. Do not characterize the event "
            "as a user typo: the capture cannot resolve physical intent from "
            "modifier/scan timing."),
        "claim_limit": (
            "This desk result names the immediate queue event and refutes the "
            "delivered editor, DEL/erase, and screen-readback paths as injectors. "
            "It cannot distinguish conscious Shift-Space from physical overlap "
            "or keyboard scan/debounce timing. It authorizes no source change, "
            "product card, medium, device contact, resume, or D3-D5."),
        "authority": {
            "owner": git_authority(), "Link112_ELF": bind(ELF112),
            "Link113_ELF": bind(ELF113),
            "Link112_bank0": bind(CAP112 / "physical-bank0.bin"),
            "Link113_bank0": bind(CAP113 / "physical-bank0.bin"),
            "Link112_receipt": bind(R112), "Link113_receipt": bind(R113),
            "prior_attribution": bind(PRIOR), "repl": bind(REPL),
            "screen": bind(SCREEN), "interrupt": bind(INTERRUPT),
            "window": bind(WINDOW), "core_snapshot": bind(CORE_SNAPSHOT),
            "matrix": bind(MATRIX), "iomapper": bind(IOMAPPER),
            "uart": bind(UART), "checker": bind(Path(__file__)),
        },
        "execution_accounting": {"WPLTO": 0, "links": 0,
                                 "product_bytes_changed": 0,
                                 "device_contacts": 0, "device_resumes": 0},
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "attribution identity drift")
    captures = value["captured_buffers"]
    require(set(captures) == {"Link112", "Link113"}
            and all(row["a0_context"] == "(x)<A0>("
                    and row["classification"]
                    == "semantic separator between parameter list and body"
                    and row["inside_function_name"] is False
                    and row["at_line_end"] is False
                    and row["at_wrap_boundary"] is False
                    for row in captures.values()),
            "captured $A0 position claim drift")
    core = value["pinned_core_queue"]
    require(core["normal_space"] == "0x20"
            and core["shifted_space"] == "0xa0"
            and core["shifted_close_parenthesis"] == "0x29",
            "core PETSCII mapping claim drift")
    editor = value["delivered_editor"]
    require(editor["editor_can_synthesize_a0_without_a0_event"] is False
            and editor["DEL_can_inject_a0"] is False
            and editor["screen_readback_can_inject_a0"] is False,
            "editor exoneration drift")
    model = value["edit_model"]
    require(model["a0_without_a0_input_event"] is False
            and model["shifted_transition_reproduces_Link112"] is True
            and model["shifted_transition_reproduces_Link113"] is True
            and model["exhaustive_small_model"]["outputs_containing_a0"] == 0,
            "edit model conclusion drift")
    attr = value["attribution"]
    require(attr["editor_injection_hypothesis"] == "REFUTED"
            and attr["DEL_insert_erase_hypothesis"] == "REFUTED"
            and attr["screen_readback_hypothesis"] == "REFUTED"
            and attr["queue_producer_shifted_table_hypothesis"]
                == "SUPPORTED-AND-REPRODUCED"
            and attr["observed_a0_is_semantic_whitespace"] is True
            and attr["wysiwyg_a0_to_space_preserves_observed_intent"] is True
            and attr["physical_finger_intent"] == "UNRESOLVED"
            and attr["owner_testimony_respected"] is True
            and attr["fix_authorized"] is False
            and attr["wysiwyg_card_held"] is True
            and attr["device_contact_authorized"] is False,
            "attribution/claim boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "move-A0-into-name": lambda x: x["captured_buffers"]["Link112"].update(
            {"inside_function_name": True}),
        "move-A0-to-line-end": lambda x: x["captured_buffers"]["Link113"].update(
            {"at_line_end": True}),
        "move-A0-to-wrap": lambda x: x["captured_buffers"]["Link113"].update(
            {"at_wrap_boundary": True}),
        "change-grammatical-context": lambda x: x["captured_buffers"]["Link112"].update(
            {"a0_context": "name<A0>name"}),
        "normal-space-is-not-20": lambda x: x["pinned_core_queue"].update(
            {"normal_space": "0xa0"}),
        "shifted-space-is-not-A0": lambda x: x["pinned_core_queue"].update(
            {"shifted_space": "0x20"}),
        "shifted-close-is-not-paren": lambda x: x["pinned_core_queue"].update(
            {"shifted_close_parenthesis": "0x28"}),
        "editor-injects-A0": lambda x: x["delivered_editor"].update(
            {"editor_can_synthesize_a0_without_a0_event": True}),
        "DEL-injects-A0": lambda x: x["delivered_editor"].update(
            {"DEL_can_inject_a0": True}),
        "screen-readback-injects-A0": lambda x: x["delivered_editor"].update(
            {"screen_readback_can_inject_a0": True}),
        "model-synthesizes-A0": lambda x: x["edit_model"].update(
            {"a0_without_a0_input_event": True}),
        "model-misses-link112": lambda x: x["edit_model"].update(
            {"shifted_transition_reproduces_Link112": False}),
        "model-misses-link113": lambda x: x["edit_model"].update(
            {"shifted_transition_reproduces_Link113": False}),
        "blame-physical-intent": lambda x: x["attribution"].update(
            {"physical_finger_intent": "SHIFT-SPACE-TYPED"}),
        "silently-authorize-fix": lambda x: x["attribution"].update(
            {"fix_authorized": True}),
        "silently-unhold-card": lambda x: x["attribution"].update(
            {"wysiwyg_card_held": False}),
        "silently-authorize-device": lambda x: x["attribution"].update(
            {"device_contact_authorized": True}),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "A0-origin mutation survived")
    return rejected


def authorized_live_successor(persisted: dict[str, Any]) -> bool:
    """Keep the historical receipt about its own world after the ordered fix.

    Historical evidence must not retain a live-source predicate forever.  The
    successor is nevertheless accepted only when the later owner authority and
    the exact boundary-normalization seam are both present.
    """
    if bind(REPL)["sha256"] == persisted["authority"]["repl"]["sha256"]:
        return False
    commit = subprocess.run(
        ["git", "rev-parse", f"{SUCCESSOR_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    source = REPL.read_text(encoding="utf-8")
    return (
        "the wysiwyg card is released" in raw
        and "$a0 → $20" in raw
        and "if (c == 0xA0) c = ' ';" in source
        and "lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);" in source
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    persisted = load(RECEIPT)
    if authorized_live_successor(persisted):
        # The receipt remains byte-for-byte evidence about Link 112/113.  Its
        # 17 conclusions are revalidated without pretending the repaired live
        # source is still the historical source it described.
        value = deepcopy(persisted)
        validate(value)
        value["mutations_rejected"] = mutations(value)
    else:
        value = derive()
        value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(persisted == value, "$A0-origin attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 17,
                "mutation count drift")
    print("A0 origin attribution: PASS "
          f"action={action} origin=SHIFTED-TABLE-SPACE mutations=17")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"A0 origin attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
