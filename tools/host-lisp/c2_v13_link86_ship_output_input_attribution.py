#!/usr/bin/env python3
"""Bind the Link-86 blank-screen observation to its output/input seams.

The physical row reached the standalone Runtime and then remained on a blank
screen after human input.  This host/ELF-only attribution answers the owner's
two static questions without changing the product: whether the exact sample
owes any visible output before read-line, and whether Ship omitted a screen
initialisation that Workbench performs.  It also records the first remaining
composition difference rather than promoting it to a target mechanism without
the queue readback that would be needed for that claim.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.3-v1.3-link86-ship-output-input-host-elf-attribution-receipt.json"
)
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
HUMAN_FIRST_RED = EVIDENCE / (
    "c2.3-v1.3-link86-interactive-human-device-first-red-receipt.json"
)
BOOT_GATE = EVIDENCE / (
    "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
)
SHIP_ELF = ROOT / (
    "build/ship-builder/v13/link86-final-5a7c0d18/interactive.runtime.elf"
)
WORKBENCH_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link86-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
SAMPLE = ROOT / "examples/ship/interactive/main.l65"
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SHIP_MAIN = ROOT / "products/runtime-core/main.c"
SCREEN = ROOT / "src/screen.c"
VM = ROOT / "src/vm.c"
WORKBENCH_MAIN = ROOT / "src/main.c"
WORKBENCH_REPL = ROOT / "src/repl.c"
WORKBENCH_INPUT = ROOT / "src/interrupt.c"
WORKBENCH_QUEUE = ROOT / "src/c2_kernal_window.s"
SHIP_CONTRACT = ROOT / "docs/contracts/ship-builder-v1.md"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

SHIP_ELF_SHA = "6a256512378142ece82ca6405cbf01a60f7c01f2312a84b9eb4f37969d26a0b4"
WORKBENCH_ELF_SHA = "cf8d4c9bb6404f9df3a47241628793206a90a60946202647e9a631d2ef6e5245"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def text(path: Path) -> str:
    require(path.is_file(), f"authority absent: {path}")
    return path.read_text(encoding="utf-8")


def symbol_bytes(truth: ElfTruth, name: str, *, unsized: int = 0) -> tuple[int, bytes]:
    symbol = truth.symbol(name)
    size = symbol.bytes or unsized
    require(size > 0, f"sized symbol required: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset and offset + size <= len(data), f"symbol outside section: {name}")
    return symbol.value, data[offset:offset + size]


def jsr(address: int) -> bytes:
    return bytes((0x20, address & 0xFF, address >> 8))


def audit(facts: dict[str, Any]) -> None:
    require(facts["sample_before_read_line"] == {
        "prompt": False, "character_output": False, "visible_output": False,
    }, "sample gained visible output before read-line")
    require(facts["read_line_visibility"] == {
        "entry": "spaces-only-last-row",
        "first-visible-write": "after-printable-key-event",
        "greeting": "after-return",
    }, "read-line visibility ordering drift")
    require(facts["screen"] == {
        "shared-driver-source": True,
        "ship-init-before-runtime-state-2": True,
        "ship-clear-before-runtime-state-2": True,
        "workbench-init-before-repl": True,
        "physical-screen-transition": "BASIC-text-to-blank-blue",
    }, "screen attribution drift")
    require(facts["input_composition"] == {
        "ship": "CALLPRIM-60->KERNAL-GETIN-FFE4",
        "workbench": "CALLPRIM-60->owned-D60A-D619-queue",
    }, "input composition boundary drift")
    require(facts["broadening_rule_activated"] is False,
            "broaden-once was activated without a second inheritance member")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "invent-pre-input-prompt": (
            ["sample_before_read_line", "prompt"], True),
        "invent-pre-input-character": (
            ["sample_before_read_line", "character_output"], True),
        "make-entry-visible": (
            ["read_line_visibility", "entry"], "visible-prompt"),
        "move-echo-before-key": (
            ["read_line_visibility", "first-visible-write"], "before-key-event"),
        "deny-shared-screen-source": (
            ["screen", "shared-driver-source"], False),
        "move-ship-init-after-state2": (
            ["screen", "ship-init-before-runtime-state-2"], False),
        "remove-ship-clear": (
            ["screen", "ship-clear-before-runtime-state-2"], False),
        "deny-physical-clear": (
            ["screen", "physical-screen-transition"], "unchanged"),
        "pretend-ship-owned-queue": (
            ["input_composition", "ship"], "CALLPRIM-60->owned-D60A-D619-queue"),
        "pretend-workbench-getin": (
            ["input_composition", "workbench"], "CALLPRIM-60->KERNAL-GETIN-FFE4"),
        "premature-broadening": (["broadening_rule_activated"], True),
    }
    result: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(candidate)
        except AttributionError:
            result[name] = "rejected"
        else:
            raise AttributionError(f"verification mutation survived: {name}")
    return result


def main() -> int:
    require(sha(SHIP_ELF) == SHIP_ELF_SHA, "Link-86 Ship ELF drift")
    require(sha(WORKBENCH_ELF) == WORKBENCH_ELF_SHA, "Link-86 Workbench ELF drift")
    ship = ElfTruth.read(SHIP_ELF, llvm_readobj=READOBJ, include_section_data=True)
    workbench = ElfTruth.read(
        WORKBENCH_ELF, llvm_readobj=READOBJ, include_section_data=True)

    sample = text(SAMPLE)
    read_line = text(READ_LINE)
    ship_io = text(SHIP_IO)
    ship_main = text(SHIP_MAIN)
    screen = text(SCREEN)
    vm = text(VM)
    wb_main = text(WORKBENCH_MAIN)
    wb_repl = text(WORKBENCH_REPL)
    wb_input = text(WORKBENCH_INPUT)
    wb_queue = text(WORKBENCH_QUEUE)
    contract = text(SHIP_CONTRACT)
    physical = load(HUMAN_FIRST_RED)
    boot_gate = load(BOOT_GATE)

    main_form = sample[sample.index("(defun main") :]
    read_at = main_form.index("(read-line)")
    before_read = main_form[:read_at]
    after_read = main_form[read_at:]
    require("(wait 1)" in before_read, "sample wait/read-line order drift")
    require("%say" not in before_read and "write-char" not in before_read
            and "screen-put-char" not in before_read,
            "sample now writes before read-line")
    require(after_read.index("(%say \"Hello, \")") > 0,
            "sample greeting no longer follows read-line")

    key_at = read_line.index("(key-event 1)")
    printable_at = read_line.index("(screen-put-char length row code 1)")
    finish_at = read_line.index("(%read-line-finish codes)")
    clear_body = read_line[
        read_line.index("(defun %read-line-clear-from"):
        read_line.index("(defun %read-line-render-reverse")
    ]
    require("screen-put-char column row 32 1" in clear_body,
            "read-line entry clear no longer writes spaces")
    require(key_at < printable_at and key_at < finish_at,
            "read-line gained visible output before input")

    ship_main_address, ship_main_bytes = symbol_bytes(ship, "main")
    ship_vm_address, ship_callprim = symbol_bytes(ship, "vm_callprim")
    ship_clear_address, _ = symbol_bytes(ship, "scr_clear")
    wb_main_address, _ = symbol_bytes(workbench, "main")
    wb_input_address, wb_input_bytes = symbol_bytes(workbench, "lisp_input_event")
    wb_queue_address, wb_queue_bytes = symbol_bytes(workbench, "c2_kernal_event_poll")
    wb_scr_init_address, _ = symbol_bytes(workbench, "scr_init")
    wb_scr_putc_address, _ = symbol_bytes(workbench, "scr_putc")

    screen_init = bytes.fromhex("ae 60 d0 ac 61 d0")
    geometry = bytes.fromhex("ac 31 d0")
    state_two = bytes.fromhex("a0 02 a2 02 86 16 84 85")
    init_at = ship_main_bytes.index(screen_init)
    geometry_at = ship_main_bytes.index(geometry)
    clear_at = ship_main_bytes.index(jsr(ship_clear_address))
    state_at = ship_main_bytes.index(state_two)
    require(init_at < geometry_at < clear_at < state_at,
            "Ship screen init/clear no longer precedes runtime state 2")
    require("scr_init();" in ship_io
            and "lisp65_ship_io_init()" in ship_main,
            "Ship source screen initialization drift")
    require("scr_init();" in wb_repl and "repl();" in wb_main,
            "Workbench screen initialization drift")
    require("void scr_init(void)" in screen and "void scr_putc(char c)" in screen,
            "shared screen driver source drift")

    getin = bytes.fromhex("20 e4 ff")
    require(ship.symbol("__GETIN").value == 0xFFE4,
            "Ship GETIN absolute symbol drift")
    getin_calls = ship_callprim.count(getin)
    require(getin_calls >= 2 and "cbm_k_getin()" in ship_io,
            "Ship CALLPRIM-60 GETIN binding drift")
    require("c2_kernal_event_poll" not in ship.symbols_by_name,
            "Ship unexpectedly linked Workbench queue owner")
    require(bytes.fromhex("ad 0a d6 10") in wb_queue_bytes
            and bytes.fromhex("ad 19 d6 8d 19 d6") in wb_queue_bytes,
            "Workbench D60A/D619 queue binding drift")
    require("c2_kernal_event_poll(event)" in wb_input
            and "$d60a" in wb_queue.lower() and "$d619" in wb_queue.lower(),
            "Workbench queue source drift")
    require("case 60" in vm and "lisp65_ship_io_getin" in vm
            and "lisp_input_event" in vm,
            "primitive-60 profile split drift")

    require(physical["preconditions"]["runtime_state_before_input"] == 2
            and physical["post_input_readback"]["nonblank_lines"] == 0
            and physical["operator_observation"]["screen_before_input"]
            == "completely blue, no prompt",
            "Link-86 physical blank-screen evidence drift")
    require(physical["bindings"]["fresh_BASIC_screen"]["sha256"]
            != physical["post_input_readback"]["screen"]["sha256"],
            "fresh BASIC and blank Runtime screen unexpectedly identical")
    require(boot_gate["status"]
            == "passed-ship-boot-arms-and-verifies-inherited-io"
            and boot_gate["host_execution"]["status"] == "passed"
            and boot_gate["mutation_count"] == 10,
            "Link-86 timebase gate drift")
    require("directly to its physical keyboard, screen" in contract,
            "Ship public input/output contract wording drift")

    facts = {
        "sample_before_read_line": {
            "prompt": False,
            "character_output": False,
            "visible_output": False,
        },
        "read_line_visibility": {
            "entry": "spaces-only-last-row",
            "first-visible-write": "after-printable-key-event",
            "greeting": "after-return",
        },
        "screen": {
            "shared-driver-source": True,
            "ship-init-before-runtime-state-2": True,
            "ship-clear-before-runtime-state-2": True,
            "workbench-init-before-repl": True,
            "physical-screen-transition": "BASIC-text-to-blank-blue",
        },
        "input_composition": {
            "ship": "CALLPRIM-60->KERNAL-GETIN-FFE4",
            "workbench": "CALLPRIM-60->owned-D60A-D619-queue",
        },
        "broadening_rule_activated": False,
    }
    audit(facts)
    mutation_results = mutations(facts)

    result = {
        "format": "lisp65-c2.3-v1.3-link86-ship-output-input-host-elf-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED-NO-PREINPUT-OUTPUT-NO-SECOND-INHERITANCE-MEMBER",
        "candidate_link": 86,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "sample_visibility": {
            "before_read_line": "none; the only preceding form is (wait 1)",
            "on_read_line_entry": "last row is cleared with spaces",
            "first_visible_echo": "only after key-event returns a printable code",
            "greeting": "only after RETURN completes read-line",
            "blank_screen_interpretation": (
                "expected before the first accepted printable event; it neither "
                "convicts nor exonerates character output"
            ),
        },
        "screen_attribution": {
            "result": "exonerated-as-missing-initialization-layer",
            "source": "Ship and Workbench call the same src/screen.c driver",
            "ship_elf": {
                "main": f"0x{ship_main_address:04x}",
                "screen_base_read_offset": f"0x{ship_main_address + init_at:04x}",
                "geometry_read_offset": f"0x{ship_main_address + geometry_at:04x}",
                "clear_call_offset": f"0x{ship_main_address + clear_at:04x}",
                "runtime_state_2_offset": f"0x{ship_main_address + state_at:04x}",
            },
            "workbench_elf": {
                "main": f"0x{wb_main_address:04x}",
                "scr_init": f"0x{wb_scr_init_address:04x}",
                "scr_putc": f"0x{wb_scr_putc_address:04x}",
            },
            "target_observation": (
                "the exact Ship run replaced the visible BASIC screen with the "
                "blank blue screen produced by its initialization/clear path"
            ),
        },
        "remaining_composition_boundary": {
            "ship": {
                "path": "CALLPRIM 60 -> lisp_poll -> KERNAL GETIN $FFE4",
                "vm_callprim": f"0x{ship_vm_address:04x}",
                "direct_getin_calls_in_vm_callprim": getin_calls,
                "owned_queue_driver_linked": False,
            },
            "workbench": {
                "path": "CALLPRIM 60 -> lisp_input_event -> c2_kernal_event_poll",
                "lisp_input_event": f"0x{wb_input_address:04x}",
                "queue_driver": f"0x{wb_queue_address:04x}",
                "queue_registers": ["0xD60A", "0xD619"],
            },
            "attribution": (
                "The blank-screen theory does not expose a second missing "
                "Workbench initialization member. The first remaining profile "
                "difference is the input source itself: Ship relies on inherited "
                "KERNAL GETIN state, while Workbench consumes the product-owned "
                "MEGA65 typed queue directly. The physical First Red falsifies the "
                "Ship key-event end-to-end claim, but static evidence alone cannot "
                "separate absent queue production from failed GETIN consumption."
            ),
        },
        "broaden_once_disposition": {
            "activated": False,
            "reason": (
                "Screen initialization is present, linked before state 2 and "
                "physically visible as a clear. Broadening timebase+screen+input "
                "would therefore mix a disproved screen premise with an input "
                "boundary that still has two target-side outcomes."
            ),
        },
        "owner_decision_boundary": {
            "smallest_discriminator": (
                "On unchanged Link 86, type one physical printable key and read "
                "$D60A and $D619 without consuming them. Queue present separates "
                "KERNAL GETIN consumption; queue absent separates keyboard scan/"
                "queue production. No new link or product byte is needed."
            ),
            "alternative_fix_forward": (
                "Bind Ship key-event to the same D60A/D619 queue contract as "
                "Workbench, with its own arm/readback gate. This removes the "
                "unproven GETIN inheritance but is a product decision, not "
                "authorized by this attribution."
            ),
            "hardware_authorized": False,
            "product_fix_authorized": False,
        },
        "coverage": {
            "executions": 1,
            "mutations": len(mutation_results),
            "mutation_results": mutation_results,
        },
        "bindings": {
            "owner_review": bind(REVIEW),
            "physical_first_red": bind(HUMAN_FIRST_RED),
            "boot_gate": bind(BOOT_GATE),
            "ship_elf": bind(SHIP_ELF),
            "workbench_elf": bind(WORKBENCH_ELF),
            "interactive_source": bind(SAMPLE),
            "read_line": bind(READ_LINE),
            "ship_io": bind(SHIP_IO),
            "ship_main": bind(SHIP_MAIN),
            "screen": bind(SCREEN),
            "vm": bind(VM),
            "workbench_main": bind(WORKBENCH_MAIN),
            "workbench_repl": bind(WORKBENCH_REPL),
            "workbench_input": bind(WORKBENCH_INPUT),
            "workbench_queue": bind(WORKBENCH_QUEUE),
            "ship_contract": bind(SHIP_CONTRACT),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "This host/ELF attribution answers the commissioned output question "
            "and binds the remaining composition boundary. It does not claim a "
            "target queue state, change product bytes, authorize a fix, create a "
            "link or consume a hardware contact."
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link86-ship-output-input-attribution: PASS "
        f"mutations={len(mutation_results)} prompt=none screen=initialized "
        f"ship-getin-calls={getin_calls} boundary=input-source"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-ship-output-input-attribution: FIRST RED: {error}")
        raise SystemExit(2)
