#!/usr/bin/env python3
"""Attribute Link-85 Ship's silent interactive sample at the host/ELF boundary.

This is deliberately not a target runner.  It binds the exact Ship and
Workbench ELFs, the exact ROM used by the hardware profile, and the sample's
first two effects.  The resulting receipt distinguishes what static evidence
proves from the inherited target state that only a later owner-authorized
read-only discriminator can decide.
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
    "c2.3-v1.3-link85-ship-input-boot-host-elf-attribution-receipt.json"
)
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
HUMAN_FIRST_RED = EVIDENCE / (
    "c2.3-v1.3-link85-interactive-human-device-first-red-receipt.json"
)
METHOD_READING = EVIDENCE / (
    "c2.3-v1.3-link85-interactive-method-host-reading-receipt.json"
)
SHIP_ELF = ROOT / "build/ship-builder/v13/final-fleet-bank2/interactive.runtime.elf"
STAGER_ELF = ROOT / "build/ship-builder/v13/final-fleet-bank2/interactive.stager.elf"
WORKBENCH_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link85-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
FLEET = ROOT / "build/ship-builder/v13/final-fleet-bank2/fleet-receipt.json"
CLOSURE = ROOT / "build/ship-builder/v13/final-fleet-bank2/interactive.closure.json"
SAMPLE = ROOT / "examples/ship/interactive/main.l65"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SHIP_MAIN = ROOT / "products/runtime-core/main.c"
VM = ROOT / "src/vm.c"
EVAL = ROOT / "src/eval.c"
INTERRUPT = ROOT / "src/interrupt.c"
WORKBENCH_MAIN = ROOT / "src/main.c"
OWNERSHIP = ROOT / "src/c2_kernal_runtime.c"
QUEUE = ROOT / "src/c2_kernal_window.s"
STAGER = ROOT / "scripts/r3-cold-stager-main.c"
CHAIN = ROOT / "scripts/c2-lite-cold-stager-chain.s"
TIME = ROOT / "lib/stdlib-time.lisp"
WAIT = ROOT / "lib/stdlib-wait.lisp"
ROM_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

SHIP_ELF_SHA = "0463d62418fb469817cc30dbb7e63e146866f7314e71ec86b3f5e4914054b3c2"
WORKBENCH_ELF_SHA = "569187ae75b14f4ecf072580eea34fe217ebab14d2b6466e177f60c10e9da0f9"
ROM_SHA = "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0"


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
    return {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


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


def executable_store_hits(truth: ElfTruth, addresses: set[int]) -> list[dict[str, Any]]:
    """Inventory direct absolute stores to input/IRQ contract registers.

    This is intentionally a narrow statement.  Source binding separately
    excludes an indirect initialization helper; this inventory proves that no
    ordinary compiler/direct-store encoding was hidden by LTO.
    """
    opcodes = {0x8D: "sta", 0x8E: "stx", 0x8C: "sty", 0x9C: "stz"}
    result: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        data = truth.section_bytes(section.name)
        for offset in range(len(data) - 2):
            opcode = data[offset]
            address = data[offset + 1] | (data[offset + 2] << 8)
            if opcode in opcodes and address in addresses:
                result.append({
                    "section": section.name,
                    "pc": f"0x{section.address + offset:04x}",
                    "instruction": opcodes[opcode],
                    "address": f"0x{address:04x}",
                })
    return result


def model(*, jiffy_ticks: int, keys: bytes) -> dict[str, Any]:
    """Small service-order model for the exact interactive sample."""
    if jiffy_ticks < 1:
        return {
            "runtime_state": 2,
            "stage": "wait-before-read-line",
            "input_consumed": 0,
            "output": "",
        }
    if b"\r" not in keys:
        return {
            "runtime_state": 2,
            "stage": "read-line",
            "input_consumed": len(keys),
            "output": keys.decode("ascii", errors="replace"),
        }
    line = keys.split(b"\r", 1)[0].decode("ascii", errors="replace")
    return {
        "runtime_state": 3,
        "stage": "complete",
        "input_consumed": len(line) + 1,
        "output": f"{line}\nHello, {line}!\n",
    }


def audit(document: dict[str, Any]) -> None:
    require(document["sample_order"] == ["wait-1", "read-line"],
            "sample no longer waits before input")
    require(document["runtime_loaded_state_precedes_entry"] is True,
            "runtime state 2 became a phase witness")
    require(document["ship"]["entry_sei"] is True
            and document["ship"]["runtime_cli"] is True,
            "Ship interrupt inheritance edge drift")
    require(document["ship"]["direct_irq_initialization_writes"] == [],
            "Ship unexpectedly owns an IRQ initialization register")
    require(document["ship"]["callprim60"] == ["lisp_poll", "0xffe4"],
            "Ship key-event call edge drift")
    require(document["ship"]["stkey_read"] == "0x0091",
            "Ship RUN/STOP STKEY seam drift")
    require(document["workbench"]["owns_irq"] is True
            and document["workbench"]["queue"] == ["0xd60a", "0xd619"],
            "Workbench owned input composition drift")
    require(document["rom"]["getin_vector"] == "0xffe4->($032a)->0xf31c"
            and document["rom"]["getin_worker"] == "0xe158",
            "bound ROM GETIN vector drift")
    require(document["rom"]["queue"] == ["0xd610", "0xd619", "0xd60a"],
            "bound ROM GETIN is no longer a direct queue reader")
    require(document["host_clock_is_fixture"] is True,
            "host clock fixture was mistaken for target proof")
    require(document["hardware_observation"] == {
        "runtime_state": 2, "result": 0, "screen_nonblank_lines": 0,
    }, "physical First Red drift")


def mutations(document: dict[str, Any]) -> dict[str, str]:
    changes: dict[str, tuple[list[str], Any]] = {
        "read-line-before-wait": (["sample_order"], ["read-line", "wait-1"]),
        "state-two-is-phase-witness": (["runtime_loaded_state_precedes_entry"], False),
        "ship-entry-not-sei": (["ship", "entry_sei"], False),
        "ship-missing-cli": (["ship", "runtime_cli"], False),
        "ship-private-irq-write": (["ship", "direct_irq_initialization_writes"], ["0xd01a"]),
        "ship-scnkey-call": (["ship", "callprim60"], ["0xff9f", "0xffe4"]),
        "ship-stkey-address": (["ship", "stkey_read"], "0x00c5"),
        "workbench-no-ownership": (["workbench", "owns_irq"], False),
        "workbench-wrong-queue": (["workbench", "queue"], ["0xd610", "0xd619"]),
        "rom-getin-vector": (["rom", "getin_vector"], "0xffe4->0xf000"),
        "rom-getin-worker": (["rom", "getin_worker"], "0xe000"),
        "rom-queue-register": (["rom", "queue"], ["0xd611", "0xd619", "0xd60a"]),
        "host-clock-target-claim": (["host_clock_is_fixture"], False),
        "hardware-state-complete": (["hardware_observation", "runtime_state"], 3),
    }
    result: dict[str, str] = {}
    for name, (path, replacement) in changes.items():
        candidate = deepcopy(document)
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
    require(sha(SHIP_ELF) == SHIP_ELF_SHA, "Link-85 Ship ELF drift")
    require(sha(WORKBENCH_ELF) == WORKBENCH_ELF_SHA, "Link-85 Workbench ELF drift")
    ship = ElfTruth.read(SHIP_ELF, llvm_readobj=READOBJ, include_section_data=True)
    stager = ElfTruth.read(STAGER_ELF, llvm_readobj=READOBJ, include_section_data=True)
    workbench = ElfTruth.read(WORKBENCH_ELF, llvm_readobj=READOBJ,
                              include_section_data=True)

    sample = text(SAMPLE)
    ship_io = text(SHIP_IO)
    ship_main = text(SHIP_MAIN)
    vm = text(VM)
    eval_source = text(EVAL)
    interrupt = text(INTERRUPT)
    ownership = text(OWNERSHIP)
    queue = text(QUEUE)
    chain = text(CHAIN)
    wait = text(WAIT)
    human = load(HUMAN_FIRST_RED)
    fleet = load(FLEET)
    closure = load(CLOSURE)

    wait_at = sample.index("(wait 1)")
    read_at = sample.index("(read-line)")
    require(wait_at < read_at, "interactive sample no longer waits before read-line")
    require("host_frames++;" in ship_io and "host_clock_phase" in ship_io,
            "Ship host clock fixture drift")
    require("RUNTIME_LOADED = 2" in ship_main
            and ship_main.index("lisp65_runtime_state = RUNTIME_LOADED")
            < ship_main.index("vm_run_dir"),
            "Runtime state-2 placement drift")
    require("%wait-until" in wait and "(%time-read)" in wait,
            "wait implementation drift")
    require(closure["edges"][2]["caller"] == "main"
            and set(closure["edges"][2]["callees"])
            == {"%say", "read-line", "wait"},
            "interactive closure drift")
    wait_samples = []
    for row in fleet["samples"]:
        path = FLEET.parent / f"{row['name']}.closure.json"
        if path.is_file() and "wait" in load(path).get("functions", []):
            wait_samples.append(row["name"])
    require(wait_samples == ["interactive"],
            f"standalone wait coverage inventory drift: {wait_samples}")

    ship_start_address, ship_start = symbol_bytes(ship, "_start", unsized=96)
    ship_main_address, ship_main_bytes = symbol_bytes(ship, "main")
    poll_address, poll = symbol_bytes(ship, "lisp_poll")
    vm_address, callprim = symbol_bytes(ship, "vm_callprim")
    stager_address, stager_chain = symbol_bytes(stager, "r3_chain_begin")
    wb_main_address, wb_main = symbol_bytes(workbench, "main")
    own_address, own = symbol_bytes(workbench, "c2_kernal_take_ownership")
    queue_address, queue_bytes = symbol_bytes(workbench, "c2_kernal_event_poll")

    require(ship_start[0] == 0x78 and stager_chain[0] == 0x78,
            "Ship no longer enters Runtime under SEI")
    cli_state = bytes.fromhex("58 a0 02 a2 02 86 16 84 85")
    require(ship_main_bytes.count(cli_state) == 1,
            "Ship one-CLI then state-2 edge drift")
    key_edge = bytes.fromhex("20 88 21 20 e4 ff aa f0 f7")
    require(callprim.count(key_edge) == 1,
            "Ship CALLPRIM-60 lisp_poll/GETIN edge drift")
    require(poll == bytes.fromhex(
        "a6 91 e0 7f d0 0b a2 8f 86 04 a2 7f 86 05 20 6a 21 60"),
        "Ship lisp_poll STKEY bytes drift")
    require(ship.symbol("__GETIN").value == 0xFFE4
            and ship.symbol("__SCNKEY").value == 0xFF9F,
            "Ship KERNAL vector symbols drift")
    require("c2_kernal_event_poll" not in ship.symbols_by_name,
            "Ship unexpectedly linked the Workbench queue owner")

    require(wb_main.count(bytes.fromhex("20 a3 b4")) == 1,
            "Workbench ownership call edge drift")
    require(bytes.fromhex("9c 1a d0") in own
            and bytes.fromhex("8c 1a d0 58") in own,
            "Workbench raster ownership sequence drift")
    require(bytes.fromhex("ad 0a d6 10") in queue_bytes
            and bytes.fromhex("ad 19 d6 8d 19 d6") in queue_bytes,
            "Workbench D60A/D619 queue edge drift")
    require("VIC_D01A = 0u" in ownership and "VIC_D01A = 0x01u" in ownership
            and "$d60a" in queue.lower() and "$d619" in queue.lower(),
            "Workbench source ownership drift")

    irq_registers = {0xD019, 0xD01A, 0xDC0D, 0xDD0D, 0x0314, 0x0315}
    ship_writes = executable_store_hits(ship, irq_registers)
    stager_writes = executable_store_hits(stager, irq_registers)
    require(ship_writes == [] and stager_writes == [],
            "Ship unexpectedly initializes an input/IRQ contract register")
    require("VIC_D01A" not in ship_io and "$d01a" not in ship_io.lower()
            and "$d01a" not in chain.lower(),
            "Ship source gained direct IRQ ownership")

    rom_contract = load(ROM_CONTRACT)["toolchain_bindings"]["rom"]
    rom_path = Path(rom_contract["path"])
    require(rom_contract["sha256"] == ROM_SHA and sha(rom_path) == ROM_SHA,
            "bound MEGA65 ROM drift")
    rom = rom_path.read_bytes()
    require(len(rom) == 0x20000, "bound MEGA65 ROM size drift")
    cpu = memoryview(rom)[0x10000:]
    require(bytes(cpu[0xFFE4:0xFFE7]) == bytes.fromhex("6c 2a 03"),
            "bound ROM GETIN vector is not JMP ($032a)")
    vector_offset = 0xFE08 + (0x032A - 0x0314)
    getin = int.from_bytes(cpu[vector_offset:vector_offset + 2], "little")
    require(getin == 0xF31C
            and bytes(cpu[getin:getin + 16])
            == bytes.fromhex("a5 99 d0 1b 78 20 58 e1 c9 ff d0 02 a9 00 18 60"),
            "bound ROM GETIN implementation drift")
    require(bytes(cpu[0xE158 + 0x2B:0xE158 + 0x33])
            == bytes.fromhex("ad 10 d6 d0 04 a9 ff 80")
            and bytes(cpu[0xE158 + 0x34:0xE158 + 0x40])
            == bytes.fromhex("ad 19 d6 ac 0a d6 8d 19 d6 c9 ff f0"),
            "bound ROM GETIN queue worker drift")

    raw = human["post_input_readback"]
    require(human["status"] == "PRODUCT-FIRST-RED-physical-keyboard-input-not-observed"
            and raw["runtime_state"] == 2 and raw["runtime_result"] == "0x0000"
            and raw["nonblank_lines"] == 0,
            "physical-keyboard First Red drift")
    require("NOT yet correct for the MEGA65 KERNAL" in eval_source
            and "STKEY $91 == $7F" in interrupt,
            "known STKEY caveat drift")

    facts = {
        "sample_order": ["wait-1", "read-line"],
        "runtime_loaded_state_precedes_entry": True,
        "host_clock_is_fixture": True,
        "ship": {
            "entry_sei": True,
            "runtime_cli": True,
            "direct_irq_initialization_writes": ship_writes + stager_writes,
            "callprim60": ["lisp_poll", "0xffe4"],
            "stkey_read": "0x0091",
        },
        "workbench": {
            "owns_irq": True,
            "queue": ["0xd60a", "0xd619"],
        },
        "rom": {
            "getin_vector": "0xffe4->($032a)->0xf31c",
            "getin_worker": "0xe158",
            "queue": ["0xd610", "0xd619", "0xd60a"],
        },
        "hardware_observation": {
            "runtime_state": 2,
            "result": 0,
            "screen_nonblank_lines": 0,
        },
    }
    audit(facts)
    mutation_results = mutations(facts)
    models = {
        "dead_jiffy_with_Ada": model(jiffy_ticks=0, keys=b"Ada\r"),
        "live_jiffy_no_key": model(jiffy_ticks=1, keys=b""),
        "live_jiffy_with_Ada": model(jiffy_ticks=1, keys=b"Ada\r"),
    }
    require(models["dead_jiffy_with_Ada"]["stage"] == "wait-before-read-line"
            and models["dead_jiffy_with_Ada"]["input_consumed"] == 0
            and models["live_jiffy_no_key"]["stage"] == "read-line"
            and models["live_jiffy_with_Ada"]["stage"] == "complete",
            "service-order host model drift")

    result = {
        "format": "lisp65-c2.3-v1.3-link85-ship-input-boot-host-elf-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED-SHIP-INHERITED-KERNAL-SERVICE-CONTRACT-UNPROVED",
        "candidate_link": 85,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "correction_to_prior_boundary": {
            "prior_claim": "runtime-state-2-means-waiting-for-key-event",
            "result": "refuted",
            "reason": (
                "State 2 is stored before vm_run_dir. The exact sample executes "
                "(wait 1) before (read-line), so the physical observation does "
                "not prove that CALLPRIM 60 or GETIN was reached."
            ),
        },
        "attribution": {
            "workbench": {
                "boot_contract": (
                    "masks inherited sources, installs the product E000 window, "
                    "owns VIC raster IRQ, then enables IRQs"
                ),
                "input": "CALLPRIM 60 -> lisp_input_event -> E000 D60A/D619 queue",
                "frame_clock": "product-owned FF83/FF84 raster counter",
                "elf": {
                    "main": f"0x{wb_main_address:04x}",
                    "ownership": f"0x{own_address:04x}",
                    "queue_driver": f"0x{queue_address:04x}",
                },
            },
            "ship": {
                "boot_contract": (
                    "stager enters under SEI; Runtime performs one CLI but neither "
                    "establishes nor verifies KERNAL IRQ/vector/jiffy/input state"
                ),
                "first_target_service": "wait -> logical FF84/FF83 -> KERNAL A1/A2 jiffy",
                "later_input": "CALLPRIM 60 -> lisp_poll($91) -> GETIN($FFE4)",
                "elf": {
                    "start": f"0x{ship_start_address:04x}",
                    "main": f"0x{ship_main_address:04x}",
                    "lisp_poll": f"0x{poll_address:04x}",
                    "callprim60_edge": f"0x{vm_address + callprim.index(key_edge):04x}",
                    "stager_chain": f"0x{stager_address:04x}",
                },
            },
            "bound_rom": {
                "getin": "FFE4 -> RAM vector 032A -> F31C -> E158",
                "queue": ["D610 ASCII/top event", "D619 PETSCII/dequeue", "D60A metadata"],
                "scnkey_required_for_getin_call": False,
            },
            "mechanism": (
                "Ship delegates its first timing service and its later input service "
                "to inherited KERNAL state after a media stager entered under SEI; "
                "unlike Workbench it has no owned initialization or readback contract. "
                "The host hides this gap with a synthetic advancing clock and synthetic input."
            ),
        },
        "stkey_disposition": {
            "status": "real-latent-defect-not-primary-attribution",
            "reason": (
                "$91 is explicitly documented as the wrong MEGA65 STKEY assumption, "
                "but seeing $7f would longjmp to boot-error state rather than leave "
                "the observed state 2. It must be fixed or replaced before Ship RUN/STOP "
                "can be claimed, but it does not explain this exact stable observation."
            ),
        },
        "service_order_model": models,
        "target_boundary": {
            "static_result": (
                "The missing ownership/verification contract is attributed; the "
                "physical First Red cannot distinguish a frozen inherited jiffy from "
                "a later GETIN/input failure because it never witnessed read-line entry."
            ),
            "smallest_discriminator": (
                "On the unchanged failed image, read A1/A2 twice across at least one "
                "raster interval. Unchanged => wait/jiffy boundary; advancing => wait "
                "is exonerated and GETIN/key-event becomes the live boundary. Also bind "
                "D01A and RAM vectors 0314/032A in the same read-only capture."
            ),
            "hardware_authorized": False,
            "product_fix_authorized": False,
        },
        "coverage": {
            "standalone_samples": fleet["sample_count"],
            "samples_using_wait": wait_samples,
            "standalone_target_wait_proof_before_this_attribution": 0,
            "mutations": len(mutation_results),
            "mutation_results": mutation_results,
            "executions": 3,
        },
        "bindings": {
            "owner_review": bind(REVIEW),
            "human_first_red": bind(HUMAN_FIRST_RED),
            "prior_method_reading": bind(METHOD_READING),
            "ship_elf": bind(SHIP_ELF),
            "stager_elf": bind(STAGER_ELF),
            "workbench_elf": bind(WORKBENCH_ELF),
            "bound_rom": bind(rom_path),
            "rom_contract": bind(ROM_CONTRACT),
            "fleet": bind(FLEET),
            "interactive_closure": bind(CLOSURE),
            "interactive_source": bind(SAMPLE),
            "ship_io": bind(SHIP_IO),
            "ship_main": bind(SHIP_MAIN),
            "vm": bind(VM),
            "eval": bind(EVAL),
            "interrupt": bind(INTERRUPT),
            "workbench_main": bind(WORKBENCH_MAIN),
            "workbench_ownership": bind(OWNERSHIP),
            "workbench_queue": bind(QUEUE),
            "ship_stager": bind(STAGER),
            "ship_chain": bind(CHAIN),
            "time_library": bind(TIME),
            "wait_library": bind(WAIT),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "This host/ELF attribution proves the composition and its missing "
            "boot-service ownership contract. It does not claim whether the observed "
            "target was stopped in wait or later in GETIN, and it changes no product."
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link85-ship-input-boot-attribution: PASS "
        f"mutations={len(mutation_results)} models=3 "
        "mechanism=inherited-KERNAL-service-contract first-service=wait/jiffy"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link85-ship-input-boot-attribution: FIRST RED: {error}")
        raise SystemExit(2)
