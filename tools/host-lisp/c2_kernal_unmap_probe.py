#!/usr/bin/env python3
"""Build and statically verify the bounded non-product KERNAL-unmap probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/c2.2/kernal-unmap"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
SIZE = ROOT / "tools/llvm-mos/bin/llvm-size"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
LFULL = ROOT / "config/c2-l-full-keymap-probe.json"
LITE = ROOT / "config/v11-l-lite-keymap.json"
SHARED_H = ROOT / "scripts/c2-kernal-unmap-proof-shared.h"
WINDOW_S = ROOT / "scripts/c2-kernal-unmap-proof-window.s"
CONTROL_S = ROOT / "scripts/c2-kernal-unmap-proof-control.s"
MAIN_C = ROOT / "scripts/c2-kernal-unmap-proof-main.c"
LINKER = ROOT / "config/c2-kernal-window-link.ld"
CONTROLLER_LINKER = ROOT / "config/c2-kernal-unmap-controller-link.ld"
SCREEN = ROOT / "src/screen.c"

WINDOW_O = BUILD / "c2-kernal-window.o"
WINDOW_ELF = BUILD / "c2-kernal-window.elf"
WINDOW_BIN = BUILD / "c2-kernal-window.bin"
WINDOW_MAP = BUILD / "c2-kernal-window.map"
WINDOW_DIS = BUILD / "c2-kernal-window.dis"
PRG = BUILD / "c2-kernal-unmap-proof.prg"
PRG_ELF = Path(str(PRG) + ".elf")
PRG_MAP = BUILD / "c2-kernal-unmap-proof.map"
PRG_DIS = BUILD / "c2-kernal-unmap-proof.dis"
GENERATED_H = BUILD / "c2-kernal-unmap-generated.h"
SHARED_INC = BUILD / "c2-kernal-unmap-proof-shared.inc"
LFULL_H = BUILD / "l-full-keymap.generated.h"
LFULL_CASES = BUILD / "l-full-keymap-cases.generated.json"
LFULL_DOC = BUILD / "l-full-keymap.generated.md"
REPORT = BUILD / "c2-kernal-unmap-static-report.json"
CORE_ROOT = ROOT / "build/upstream-verification/mega65-core"
HARDWARE_REFERENCE = ROOT / "docs/reference/mega65-chipset-reference.pdf"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
CORE_BINDINGS = {
    "src/vhdl/gs4510.vhdl": "ce8c7f120aac11e142add5e08e9a83dc9450b813b211bf310cb95553b4eae957",
    "src/hyppo/task.asm": "07497c4738023639300c7119e178c9a6233830026a017636fa840020472c9894",
    "src/hyppo/freeze.asm": "fd5f4cbd7c2c594388895293007055050e6c73a00fb6d423ff45b47bb51b58cd",
    "src/hyppo/syspart.asm": "b436f778ab9232f81ccd78b3cb45dbda3181c838b113387b1b7844946c57bf74",
    "src/vhdl/iomapper.vhdl": "942a08a4622001048c38b065bee11edf1e4926f2db29dfc03f67bb7257db4bba",
    "src/vhdl/c65uart.vhdl": "3679b4cce25823c3f813cdfa8fdc0038c9cfbbadfe86fb960e3db373670915b6",
    "src/vhdl/keyboard_complex.vhdl": "d49f8c72c92a8cffe120f95942becf64fb9a9df694c5d018de030caac9cff32a",
    "src/vhdl/viciv.vhdl": "8bc1db6e5e0e85fe1c1b777e899816362c6e0b06f9f49ee7fa8502b7b13b4ca2",
}


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def run(command: list[str], *, timeout: int = 180) -> str:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ProbeError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    require(not result.stderr, f"unexpected diagnostics: {result.stderr.strip()}")
    return result.stdout


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} root is not an object")
    return value


def shared_constants() -> dict[str, int]:
    text = SHARED_H.read_text(encoding="utf-8")
    values: dict[str, int] = {}
    for name, token in re.findall(r"^#define\s+(C2KU_[A-Z0-9_]+)\s+(0x[0-9a-fA-F]+|[0-9]+)u?\s*$",
                                  text, re.MULTILINE):
        values[name] = int(token, 0)
    required = {
        "C2KU_FRAME_LO", "C2KU_FRAME_HI", "C2KU_NMI_COUNT",
        "C2KU_EVENT_CODE", "C2KU_EVENT_MODIFIERS", "C2KU_DEQUEUE_COUNT",
        "C2KU_COMMAND", "C2KU_RESPONSE", "C2KU_UNEXPECTED_IRQ",
        "C2KU_STATE", "C2KU_MAP_GENERATION", "C2KU_ABORT_LATCHED",
        "C2KU_UNOWNED_VIC_FLAGS",
        "C2KU_OLD_IRQ_LO", "C2KU_OLD_IRQ_HI", "C2KU_CMD_VALIDATE",
        "C2KU_CMD_POLL_EVENT", "C2KU_RESPONSE_MAGIC",
    }
    require(required <= values.keys(), "shared mailbox constant set incomplete")
    return values


def generate_shared_inc(values: dict[str, int]) -> None:
    lines = ["; generated from scripts/c2-kernal-unmap-proof-shared.h"]
    for name in sorted(values):
        lines.append(f"\t.equ {name}, 0x{values[name]:x}")
    SHARED_INC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_lfull() -> dict:
    spec = load(LFULL)
    lite = load(LITE)
    require(spec.get("format") == "lisp65-c2-l-full-keymap-probe-v2",
            "L-full cross-check format drift")
    require(spec.get("base") == "config/v11-l-lite-keymap.json", "L-full base drift")
    require(spec.get("canonical_binding_source") ==
            "config/v11-l-lite-keymap.json#modifier_bindings",
            "L-full canonical binding source drift")
    command_ids = {row["id"] for row in lite["commands"]}
    rows = lite.get("modifier_bindings")
    require(isinstance(rows, list) and len(rows) == 2, "L-full physical binding count drift")
    by_id = {row["id"]: row for row in rows}
    require(set(by_id) == {"control-space", "meta-x"}, "L-full physical binding IDs drift")
    require(all(row["command"] in command_ids for row in rows), "L-full command not in base surface")
    masks = lite["event_model"]["modifier_masks"]
    require(masks == {"control": 4, "meta": 16}, "L-full modifier mask drift")
    require(by_id["control-space"]["raw_petscii"] == 255
            and by_id["control-space"]["normalized_code"] == 255,
            "C-Space raw/normalized source drift")
    require(by_id["meta-x"]["raw_petscii"] == 88
            and by_id["meta-x"]["normalized_code"] == 120,
            "M-x raw/normalized source drift")
    global_events = spec.get("global_events")
    require(isinstance(global_events, list) and len(global_events) == 1,
            "L-full global event count drift")
    require(global_events[0]["id"] == "run-stop-abort"
            and global_events[0]["petscii"] == 3, "RUN/STOP event drift")

    LFULL_H.write_text(
        "/* generated from config/c2-l-full-keymap-probe.json */\n"
        "#define LFULL_MOD_CONTROL 0x04u\n"
        "#define LFULL_MOD_META 0x10u\n"
        "#define LFULL_CONTROL_SPACE_PETSCII 0xffu\n"
        "#define LFULL_META_X_PETSCII 0x58u\n"
        "#define LFULL_RUN_STOP_PETSCII 0x03u\n",
        encoding="utf-8")
    cases = {
        "format": "lisp65-c2-l-full-keymap-cases-v1",
        "source": "config/c2-l-full-keymap-probe.json",
        "base_sha256": digest(LITE),
        "cases": [
            {"physical": row["display"],
             "raw_petscii": row["raw_petscii"],
             "normalized_code": row["normalized_code"],
             "required_modifiers": row["required_modifiers"], "command": row["command"],
             "hardware_sample": "required"}
            for row in rows
        ] + [{"physical": "RUN/STOP", "petscii": 3, "command": "abort",
              "hardware_sample": "required"}],
        "claim_limit": spec["claim_limit"],
    }
    LFULL_CASES.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    LFULL_DOC.write_text(
        "# L-full typed-event probe table\n\n"
        "> Non-product probe output. These physical bindings remain unpublished until the real-key samples pass.\n\n"
        "| Physical input | Queue tuple | Command |\n|---|---|---|\n"
        "| C-Space | `(255, control)` | `set-mark` |\n"
        "| M-x | `(88, meta)` | `execute-command` |\n"
        "| RUN/STOP | `(3, none)` | abort running evaluation |\n",
        encoding="utf-8")
    return cases


def crc16(data: bytes) -> int:
    crc = 0xffff
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def section_sizes(elf: Path) -> dict[str, int]:
    output = run([str(SIZE), "-A", str(elf)])
    sizes: dict[str, int] = {}
    for line in output.splitlines():
        match = re.match(r"^(\.[^\s]+)\s+(\d+)\s+", line.strip())
        if match:
            sizes[match.group(1)] = int(match.group(2))
    return sizes


def symbols(elf: Path) -> dict[str, int]:
    output = run([str(NM), "--defined-only", "--numeric-sort", str(elf)])
    result: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            result[parts[-1]] = int(parts[0], 16)
    return result


def build_window() -> None:
    run([str(CC), "-c", "-I", str(BUILD), "-I", str(ROOT / "scripts"),
         str(WINDOW_S), "-o", str(WINDOW_O)])
    run([str(LD), "--gc-sections", str(WINDOW_O), "-T", str(LINKER),
         "-Map=" + str(WINDOW_MAP), "-o", str(WINDOW_ELF)])
    run([str(OBJCOPY), "-O", "binary", str(WINDOW_ELF), str(WINDOW_BIN)])
    require(WINDOW_BIN.stat().st_size == 8192,
            f"window binary is {WINDOW_BIN.stat().st_size}, expected 8192")
    syms = symbols(WINDOW_ELF)
    require(syms.get("c2ku_window_dispatch") == 0xe000, "window dispatcher not at $e000")
    require(syms.get("c2ku_nmi_handler") == int.from_bytes(WINDOW_BIN.read_bytes()[-6:-4], "little"),
            "NMI vector does not name owned handler")
    require(syms.get("c2ku_fail_closed") == int.from_bytes(WINDOW_BIN.read_bytes()[-4:-2], "little"),
            "RESET vector does not name fail-closed handler")
    require(syms.get("c2ku_irq_handler") == int.from_bytes(WINDOW_BIN.read_bytes()[-2:], "little"),
            "IRQ vector does not name owned handler")
    WINDOW_DIS.write_text(run([str(OBJDUMP), "-d", str(WINDOW_ELF)]), encoding="utf-8")


def generate_window_header() -> None:
    data = WINDOW_BIN.read_bytes()
    GENERATED_H.write_text(
        "/* generated from the separately linked C2 KERNAL window */\n"
        "#define C2KU_WINDOW_BASE 0xe000ul\n"
        f"#define C2KU_WINDOW_BYTES {len(data)}u\n"
        f"#define C2KU_WINDOW_CRC16 0x{crc16(data):04x}u\n"
        f"#define C2KU_WINDOW_SHA256 \"{hashlib.sha256(data).hexdigest()}\"\n",
        encoding="utf-8")


def build_controller() -> None:
    command = [
        str(CC), "-mllvm", "-rng-seed=0", "-std=c99", "-Os", "-Wall",
        "-DLISP65_SCREEN_DRIVER", "-I", str(BUILD), "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "src"), str(MAIN_C), str(CONTROL_S), str(SCREEN),
        "-Wl,--icf=none", "-Wl,-T," + str(CONTROLLER_LINKER),
        "-Wl,-Map," + str(PRG_MAP), "-o", str(PRG),
    ]
    output = run(command)
    require(not output, "controller compiler emitted output")
    require(PRG.is_file() and PRG_ELF.is_file(), "controller artifacts absent")
    end = 0x2001 + PRG.stat().st_size - 2
    require(end < 0xc000, f"controller crosses etherload $c000 invariant: ${end:04x}")
    PRG_DIS.write_text(run([str(OBJDUMP), "-d", str(PRG_ELF)]), encoding="utf-8")


def static_report(lfull_cases: dict) -> dict:
    contract = load(CONTRACT)
    require(contract["bounded_probe"]["product_artifacts_emitted"] == 0,
            "contract product-artifact claim drift")
    require(digest(HARDWARE_REFERENCE)
            == contract["authority"]["hardware_reference"]["sha256"],
            "pinned hardware-reference PDF drift")
    require(run(["git", "-C", str(CORE_ROOT), "rev-parse", "HEAD"]).strip() == CORE_COMMIT,
            "pinned mega65-core commit drift")
    for relative, expected in CORE_BINDINGS.items():
        require(digest(CORE_ROOT / relative) == expected,
                f"pinned mega65-core source drift: {relative}")
    cpu_source = (CORE_ROOT / "src/vhdl/gs4510.vhdl").read_text(encoding="utf-8")
    task_source = (CORE_ROOT / "src/hyppo/task.asm").read_text(encoding="utf-8")
    freeze_source = (CORE_ROOT / "src/hyppo/freeze.asm").read_text(encoding="utf-8")
    unfreeze_source = (CORE_ROOT / "src/hyppo/syspart.asm").read_text(encoding="utf-8")
    iomapper_source = (CORE_ROOT / "src/vhdl/iomapper.vhdl").read_text(encoding="utf-8")
    uart_source = (CORE_ROOT / "src/vhdl/c65uart.vhdl").read_text(encoding="utf-8")
    keyboard_source = (CORE_ROOT / "src/vhdl/keyboard_complex.vhdl").read_text(encoding="utf-8")
    vic_source = (CORE_ROOT / "src/vhdl/viciv.vhdl").read_text(encoding="utf-8")
    require('Trap #66 ($42) = RESTORE key double-tap' in cpu_source,
            "Freezer hypervisor-trap source fact drift")
    require("restore_press_trap:" in task_source and "jsr freeze_to_slot" in task_source,
            "Freezer entry source fact drift")
    require("384KB RAM" in freeze_source and "!8 6" in freeze_source,
            "full guest-RAM freeze domain drift")
    require("@unfreezesyncwait:" in unfreeze_source
            and "sta hypervisor_enterexit_trigger" in unfreeze_source,
            "Freezer restore-before-resume source fact drift")
    require("irq <= cia1_irq and ethernet_irq and uart_irq and iec_irq;" in iomapper_source,
            "non-VIC IRQ aggregation source fact drift")
    require("fastio_rdata(7) <= key_presenting;" in uart_source
            and "fastio_rdata <= unsigned(porto);" in uart_source,
            "typed queue register source fact drift")
    require("matrix_to_ascii" in keyboard_source and "key_valid => key_valid" in keyboard_source,
            "autonomous keyboard event producer source fact drift")
    require("fastio_rdata(4) <= irq_rasterx;" in vic_source
            and "fastio_rdata(0) <= irq_raster;" in vic_source,
            "VIC-IV defined IRQ-flag domain source fact drift")
    window_sections = section_sizes(WINDOW_ELF)
    prg_sections = section_sizes(PRG_ELF)
    wanted_window = {
        ".lisp65_c2_kernal_window.dispatch",
        ".lisp65_c2_kernal_window.typed_queue_driver",
        ".lisp65_c2_kernal_window.frame_source",
        ".lisp65_c2_kernal_window.irq_handler",
        ".lisp65_c2_kernal_window.nmi_and_freezer_return",
        ".lisp65_c2_kernal_window.map_switch_and_guards",
        ".lisp65_c2_kernal_window.post_startup_output_seam",
        ".lisp65_c2_vectors",
    }
    require(wanted_window <= window_sections.keys(), "named window section missing")
    require(prg_sections.get(".lisp65_c2_map_switch_and_guards", 0) > 0,
            "low-resident map/guard section missing")
    require(prg_sections.get(".lisp65_c2_frame_handoff", 0) > 0,
            "pre-handoff frame section missing")
    require(prg_sections.get(".lisp65_c2_controller_mailbox") == 0x200,
            "shared controller/window mailbox is not linker-reserved")
    prg_syms = symbols(PRG_ELF)
    require(prg_syms.get("__c2ku_mailbox_start") == 0x3000
            and prg_syms.get("__c2ku_mailbox_end") == 0x3200,
            "shared mailbox linker geometry drift")

    window_text = WINDOW_S.read_text(encoding="utf-8").lower()
    dis = WINDOW_DIS.read_text(encoding="utf-8").lower()
    prg_dis = PRG_DIS.read_text(encoding="utf-8").lower()
    control_text = CONTROL_S.read_text(encoding="utf-8").lower()
    require("$ffd2" not in dis and "$ffe4" not in dis, "KERNAL service edge in owned window")
    require("$91" not in dis, "retired STKEY operand in owned window")
    require(dis.count("$d619") == 2, "typed queue must read and dequeue PETSCII exactly once")
    require("$d60a" in dis, "typed queue modifier source absent")
    require("bne .lunknown" in window_text
            and "jmp c2ku_queue_poll" in window_text
            and "beq c2ku_queue_poll" not in window_text,
            "cross-section queue dispatch must use a local branch plus absolute JMP")
    require(re.search(r"jmp\s+\$[0-9a-f]+ <c2ku_queue_poll>", dis) is not None,
            "linked queue dispatch does not target the typed consumer entry")
    require(not run([str(NM), "--undefined-only", str(WINDOW_ELF)]).strip(),
            "owned window has an unresolved edge")
    require(prg_dis.count("jsr\t$ffd2") == 1, "pre-main CRT CHROUT census drift")
    require("jsr\t$ffe4" not in prg_dis, "GETIN edge in bounded proof controller")
    require(re.search(r"\bmap\n\s+[0-9a-f]+:\s+ea\s+", prg_dis) is not None,
            "pinned MAP/EOM instruction pair absent")
    require("lda #$00\n\tldx #$00\n\tldy #$00\n\tldz #$80\n\tmap\n\teom\n"
            "\t; llvm-mos treats z as the zero index for indirect-z pointer accesses.\n"
            "\t; map consumes z as an operand but must not leak that value back into c.\n"
            "\tldz #$00\n\trts" in control_text,
            "MAP mask or llvm-mos Z-register return invariant drift")
    require("c2ku_prehandoff_irq:\n\tpha" in control_text
            and ".lpre_chain:\n\tpla\n\tjmp (c2ku_old_irq_lo)" in control_text,
            "pre-handoff IRQ shim must preserve A across the chained handler")
    require("lda $d019\n\t; vic-iv defines irq flags only in bits 4..0." in window_text
            and "and #$1f\n\tsta c2ku_unowned_vic_flags" in window_text
            and "cmp #$02" in window_text
            and ".lsource_less_storm:" in window_text,
            "Freezer source-less IRQ must be recorded once and storm-guarded")

    categories = {
        "typed_queue_driver": window_sections[".lisp65_c2_kernal_window.typed_queue_driver"],
        "irq_handler": window_sections[".lisp65_c2_kernal_window.irq_handler"],
        "nmi_and_freezer_return": window_sections[".lisp65_c2_kernal_window.nmi_and_freezer_return"],
        "frame_source": window_sections[".lisp65_c2_kernal_window.frame_source"]
                        + prg_sections[".lisp65_c2_frame_handoff"],
        "map_switch_and_guards": window_sections[".lisp65_c2_kernal_window.dispatch"]
                                 + window_sections[".lisp65_c2_kernal_window.map_switch_and_guards"]
                                 + prg_sections[".lisp65_c2_map_switch_and_guards"],
        "post_startup_output_seam": window_sections[".lisp65_c2_kernal_window.post_startup_output_seam"],
        "alignment_and_vectors": window_sections[".lisp65_c2_vectors"],
    }
    expected_categories = contract["capacity_model"]["replacement_categories"]
    require(list(categories) == expected_categories, "capacity category order/set drift")
    replacement = sum(categories.values())
    gross = contract["capacity_model"]["gross_window_bytes"]
    deficit = contract["capacity_model"]["fixed_resident_deficit_bytes"]
    future = gross - deficit - replacement
    require(future > 0, "net KERNAL-unmap capacity equation is not positive")

    negative_names = contract["required_negative_cases"]
    require(len(negative_names) == 25 and len(set(negative_names)) == 25,
            "contract negative-case inventory drift")
    main_text = MAIN_C.read_text(encoding="utf-8")
    lite = load(LITE)
    actual_lite_codes = {tuple(row["codes"]) for row in lite["bindings"]}
    owned_window_targets = {
        "c2ku_window_dispatch", "c2ku_queue_poll", "c2ku_frame_tick",
        "c2ku_irq_handler", "c2ku_nmi_handler", "c2ku_fail_closed",
        "c2ku_output_cell",
    }
    actual_window_targets = {
        name for name, address in symbols(WINDOW_ELF).items()
        if 0xe000 <= address < 0xfffa
    }
    map_at = main_text.index("c2ku_map_window();")
    closed_at = main_text.index("C2KU_STATE_CLOSED")
    stage_at = main_text.index("stage_window_for_handoff();")
    raster_rearm_at = main_text.index("VIC_D01A = 0x01u;", stage_at)
    post_map_rearm_at = main_text.index("VIC_D01A = 0x01u;", map_at)
    mapped_crc_at = main_text.index("mapped_window_matches()", map_at)
    armed_at = main_text.index("arm_prehandoff_frame_source();")
    armed_wait_at = main_text.index("wait_frames(2u, 0x21u);")
    abort_ready_at = main_text.index(
        "wait_firmware_event(LFULL_RUN_STOP_PETSCII, 0x20u)")
    firmware_dequeue_at = main_text.rindex(
        "REG8(0xd619) = code;", 0, abort_ready_at)
    latch_at = main_text.index("REG8(C2KU_ABORT_LATCHED) = 1u;")
    latch_consume_at = main_text.index("if (!REG8(C2KU_ABORT_LATCHED))", map_at)
    latch_clear_at = main_text.index("REG8(C2KU_ABORT_LATCHED) = 0;", latch_consume_at)
    validate_at = main_text.index("C2KU_CMD_VALIDATE", map_at)
    product_at = main_text.index("C2KU_STATE_PRODUCT", map_at)
    cli_at = main_text.index('__asm__ volatile("cli"', map_at)
    facts = {
        negative_names[0]: firmware_dequeue_at < abort_ready_at < map_at,
        negative_names[1]: abort_ready_at < map_at and "$91" not in window_text,
        negative_names[2]: abort_ready_at < latch_at < map_at < product_at < cli_at
                            < latch_consume_at < latch_clear_at,
        negative_names[3]: armed_at < armed_wait_at < closed_at < stage_at
                            < raster_rearm_at < map_at < post_map_rearm_at
                            < product_at < cli_at,
        negative_names[4]: closed_at < stage_at < map_at < mapped_crc_at
                            < validate_at < product_at < cli_at,
        negative_names[5]: "sta $d019" in window_text,
        negative_names[6]: not run([str(NM), "--undefined-only", str(WINDOW_ELF)]).strip(),
        negative_names[7]: "C2KU_MAP_GENERATION) != 1u" in main_text,
        negative_names[8]: "if (REG8(C2KU_RESPONSE) != C2KU_RESPONSE_MAGIC) stop_fail" in main_text,
        negative_names[9]: "$ffd2" not in dis,
        negative_names[10]: "$ffe4" not in dis,
        negative_names[11]: "$91" not in dis,
        negative_names[12]: actual_window_targets == owned_window_targets,
        negative_names[13]: WINDOW_O.is_file() and not run([str(NM), "--undefined-only", str(WINDOW_ELF)]).strip(),
        negative_names[14]: window_text.index("lda $d60a") < window_text.index("lda $d619"),
        negative_names[15]: window_text.count("sta $d619") == 1,
        negative_names[16]: "bpl .lqueue_empty" in window_text and "cmp #$00" not in window_text,
        negative_names[17]: (3,) not in actual_lite_codes and lfull_cases["cases"][-1]["command"] == "abort",
        negative_names[18]: digest(LFULL_H) == hashlib.sha256(LFULL_H.read_bytes()).hexdigest()
                            and len(lfull_cases["cases"]) == 3,
        negative_names[19]: all(row["hardware_sample"] == "required"
                                for row in lfull_cases["cases"][:2])
                            and "remain unpublished" in LFULL_DOC.read_text(encoding="utf-8"),
        negative_names[20]: list(categories) == expected_categories,
        negative_names[21]: future != gross and replacement > 0 and deficit > 0,
        negative_names[22]: future > 0,
        negative_names[23]: "DISK REBOOT REQUIRED" in main_text
                            and "c2ku_fail_closed" in window_text,
        negative_names[24]: contract["freezer_fidelity"]["classification"] == "hardware-only"
                            and "hardware-only-pending" == "hardware-only-pending",
    }

    def validate_negative_facts(candidate: dict[str, bool]) -> None:
        require(list(candidate) == negative_names, "negative matrix order drift")
        rejected = [name for name, passed in candidate.items() if not passed]
        if rejected:
            raise ProbeError("negative gate accepted forbidden case: " + rejected[0])

    validate_negative_facts(facts)
    mutations_rejected = 0
    for name in negative_names:
        mutation = deepcopy(facts)
        mutation[name] = False
        try:
            validate_negative_facts(mutation)
        except ProbeError:
            mutations_rejected += 1
        else:
            raise ProbeError(f"negative mutation was accepted: {name}")
    require(mutations_rejected == 25, "negative mutation rejection count drift")

    report = {
        "format": "lisp65-c2-kernal-unmap-static-probe-v1",
        "status": "static-green-hardware-pending",
        "claim_limit": "Bounded non-product proof only; no hardware PASS, product link, capacity repin or promotion claim.",
        "inputs": {str(path.relative_to(ROOT)): {"sha256": digest(path), "bytes": path.stat().st_size}
                   for path in (CONTRACT, LFULL, LITE, WINDOW_S, CONTROL_S, MAIN_C,
                                LINKER, CONTROLLER_LINKER)},
        "freezer_source_audit": {
            "repository": str(CORE_ROOT.relative_to(ROOT)),
            "commit": CORE_COMMIT,
            "files": CORE_BINDINGS,
            "facts": [
                "double-RESTORE enters hypervisor trap 0x42 at an instruction-fetch boundary, not the guest NMI vector",
                "HYPPO freezes the complete 384-KiB guest-RAM domain plus process state",
                "HYPPO resumes only after unfreeze restoration and raster synchronization",
                "owned NMI and real Freezer return therefore remain separate proof obligations",
                "typed events are produced by the hardware keyboard/matrix pipeline and exposed at D60A/D619",
                "the non-VIC IRQ line aggregates CIA1, Ethernet, UART and IEC sources",
                "VIC-IV D019 defines interrupt flags only in bits 4..0; reserved bits 6..5 are not source evidence",
            ],
        },
        "artifacts": {
            "window": {"path": str(WINDOW_BIN.relative_to(ROOT)), "bytes": WINDOW_BIN.stat().st_size,
                       "sha256": digest(WINDOW_BIN), "crc16": f"{crc16(WINDOW_BIN.read_bytes()):04x}"},
            "controller": {"path": str(PRG.relative_to(ROOT)), "bytes": PRG.stat().st_size,
                           "sha256": digest(PRG)},
        },
        "l_full": {"generated_cases": len(lfull_cases["cases"]), "physical_samples": "pending"},
        "negative_matrix": {"cases": negative_names, "cases_passed": 25,
                            "mutations_rejected": mutations_rejected},
        "kernal_freedom": {"owned_sections": sorted(wanted_window), "forbidden_edges": 0,
                           "post_unmap_getin": 0, "post_unmap_chrout": 0, "post_unmap_stkey": 0},
        "mailbox_guard": {"start": 0x3000, "end": 0x3200,
                          "bytes": prg_sections[".lisp65_c2_controller_mailbox"],
                          "link_overlap": "rejected"},
        "window_staging": {"host_verified_source": "0x087fe000",
                           "publication": "closed-handoff-enhanced-dma-to-bank0-e000",
                           "post_map_witness": "cpu-view-crc16-before-vector-publication"},
        "capacity": {"gross_window_bytes": gross, "fixed_resident_deficit_bytes": deficit,
                     "replacement_categories": categories,
                     "replacement_resident_bytes": replacement, "future_margin_bytes": future,
                     "equation_closes": gross - deficit - replacement == future},
        "hardware": {"state_machine": "pending", "run_stop_continuity": "pending",
                     "frame_continuity": "pending", "typed_queue": "pending",
                     "owned_irq_nmi": "pending", "freezer_return": "hardware-only-pending"},
        "product_artifacts_emitted": 0,
        "fifth_substitution_link": "locked",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def build() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    values = shared_constants()
    generate_shared_inc(values)
    lfull_cases = generate_lfull()
    build_window()
    generate_window_header()
    build_controller()
    report = static_report(lfull_cases)
    cap = report["capacity"]
    print("c2-kernal-unmap-probe: STATIC GREEN hardware=pending product_bytes=0 "
          f"window=8192 replacement={cap['replacement_resident_bytes']} "
          f"deficit={cap['fixed_resident_deficit_bytes']} margin={cap['future_margin_bytes']} "
          f"controller={PRG.stat().st_size}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "paths"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            build()
        else:
            for path in (WINDOW_BIN, PRG, REPORT):
                require(path.is_file(), "build the bounded proof first")
                print(path)
        return 0
    except (OSError, subprocess.SubprocessError, ProbeError, json.JSONDecodeError) as error:
        print(f"c2-kernal-unmap-probe: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
