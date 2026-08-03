#!/usr/bin/env python3
"""Attribute Link-86's silent interactive Ship consumer path.

This is a host/source/ELF reading only.  It binds the two diagnostic target
receipts, the exact Link-86 runtime, and the ROM selected by the product
profile.  In particular it does not turn Runtime state 2 into a phase witness:
the GETIN-only and frame-peek-aware identities decide that boundary directly.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.3-v1.3-link86-consumer-path-host-elf-attribution-receipt.json"
)
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
RUNTIME_ELF = ROOT / (
    "build/ship-builder/v13/link86-final-5a7c0d18/interactive.runtime.elf"
)
STAGER_ELF = ROOT / (
    "build/ship-builder/v13/link86-final-5a7c0d18/interactive.stager.elf"
)
GETIN_ELF = ROOT / (
    "build/ship-builder/v13/link86-queue-cpu-witness-getin-only-first-red/"
    "interactive.runtime.elf"
)
WAIT_ELF = ROOT / (
    "build/ship-builder/v13/link86-queue-cpu-witness/interactive.runtime.elf"
)
GETIN_RECEIPT = EVIDENCE / (
    "c2.3-v1.3-link86-queue-cpu-witness-getin-only-first-red-receipt.json"
)
WAIT_PREP = EVIDENCE / (
    "c2.3-v1.3-link86-queue-cpu-witness-preparation-receipt.json"
)
WAIT_DEVICE = EVIDENCE / (
    "c2.3-v1.3-link86-queue-cpu-witness-device-receipt.json"
)
LINK85_JIFFY = EVIDENCE / (
    "c2.3-v1.3-link85-jiffy-split-readonly-capture-receipt.json"
)
BOOT_GATE_RECEIPT = EVIDENCE / (
    "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
)
BOOT_CONTRACT = ROOT / "config/c2-ship-boot-inheritance-contract.json"
BOOT_GATE = ROOT / "tools/host-lisp/c2_ship_boot_inheritance_gate.py"
ROM_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"
SAMPLE = ROOT / "examples/ship/interactive/main.l65"
WAIT = ROOT / "lib/stdlib-wait.lisp"
TIME = ROOT / "lib/stdlib-time.lisp"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
RUNTIME_MAIN = ROOT / "products/runtime-core/main.c"
RASTER = ROOT / "src/mega65_raster_timebase.h"
STAGER = ROOT / "scripts/r3-cold-stager-main.c"
CHAIN = ROOT / "scripts/c2-lite-cold-stager-chain.s"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ELF_TRUTH = ROOT / "tools/host-lisp/elf_truth.py"
DRIVER = Path(__file__).resolve()

RUNTIME_SHA = "6a256512378142ece82ca6405cbf01a60f7c01f2312a84b9eb4f37969d26a0b4"
STAGER_SHA = "4f977ff71167540e8d5041f1a23d9e5c34471ac7ce87e530a1636eb142db9acd"
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
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def source(path: Path) -> str:
    require(path.is_file(), f"authority absent: {path}")
    return path.read_text(encoding="utf-8")


def symbol_bytes(truth: ElfTruth, name: str, *, unsized: int = 0) -> tuple[int, bytes]:
    symbol = truth.symbol(name)
    size = symbol.bytes or unsized
    require(size > 0, f"sized symbol required: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset and offset + size <= len(data),
            f"symbol outside section: {name}")
    return symbol.value, data[offset:offset + size]


def pattern_sites(truth: ElfTruth, pattern: bytes) -> list[str]:
    sites: list[str] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags:
            continue
        data = truth.section_bytes(section.name)
        start = 0
        while True:
            offset = data.find(pattern, start)
            if offset < 0:
                break
            sites.append(f"0x{section.address + offset:04x}")
            start = offset + 1
    return sites


def audit(facts: dict[str, Any]) -> None:
    phase = facts["phase_split"]
    require(phase["sample_order"] == ["wait-1", "read-line"],
            "interactive sample order drift")
    require(phase["getin_only_immediate"] == [0] * 6
            and phase["getin_only_after_28_seconds"] == [0] * 6,
            "GETIN-only witness became live")
    require(phase["frame_peek_samples_before_key"] == 255,
            "frame-peek witness was not live")
    require(phase["selected_boundary"] == "wait-before-getin"
            and phase["getin_reached"] is False,
            "wait/GETIN boundary drift")

    clock = facts["ship_clock"]
    require(clock["logical_addresses"] == ["0xff83", "0xff84"]
            and clock["physical_addresses"] == ["0x00a2", "0x00a1"],
            "Ship public time source drift")
    require(clock["boot_acceptance"] == "one-change-is-success",
            "Ship boot proof shape drift")
    require(clock["recurring_progress_proved"] is False,
            "one-shot boot proof was promoted to recurring progress")

    platform = facts["platform_authority"]
    require(platform["rdtim"] == "0xffde->0xf813"
            and platform["rdtim_registers"]
            == ["0xdc0b", "0xdc0a", "0xdc09", "0xdc08"],
            "bound ROM time-source reading drift")
    require(platform["a1_role"] == "irq-scratch-for-d030"
            and platform["rdtim_uses_a1_a2"] is False,
            "bound ROM A1/A2 role drift")
    require(platform["live_vectors_equal_bound_defaults"] is False,
            "live ROM identity caveat was lost")

    false_green = facts["false_green"]
    require(false_green["pre_fix_live_a1_a2"] == [0x64, 0x00]
            and false_green["runtime_d030_immediate"] == "0x44",
            "one-shot transition anchors drift")
    require(false_green["mechanism"]
            == "wrong-A1/A2-time-contract-plus-one-shot-change-proof",
            "attributed mechanism drift")

    mapping = facts["mapping"]
    require(mapping["runtime_io_unlock_sites"] == ["0x73c8"]
            and mapping["stager_io_unlock_sites"] == ["0x20a0", "0x23c2"],
            "Ship I/O unlock inventory drift")
    require(mapping["linked_map_owner"] is False
            and mapping["live_io_seen_during_wait"] is True,
            "Ship mapping evidence drift")
    require(mapping["hypothesis"] == "refuted-as-current-cause",
            "mapping hypothesis was not refuted")

    scope = facts["scope"]
    require(scope == {
        "product_candidate_bytes_changed": 0,
        "product_fixes": 0,
        "product_links": 0,
        "new_hardware_contacts": 0,
        "v1.3_status": "closed-pending-owner-review",
    }, "attribution scope drift")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    changes: dict[str, tuple[list[str], Any]] = {
        "getin-witness-live": (["phase_split", "getin_only_after_28_seconds"],
                               [1, 0, 0, 0, 0, 0]),
        "frame-peek-not-live": (["phase_split", "frame_peek_samples_before_key"], 0),
        "select-getin": (["phase_split", "selected_boundary"], "getin"),
        "claim-getin-reached": (["phase_split", "getin_reached"], True),
        "reverse-sample-order": (["phase_split", "sample_order"],
                                 ["read-line", "wait-1"]),
        "change-clock-address": (["ship_clock", "physical_addresses"],
                                 ["0x00a0", "0x00a1"]),
        "claim-recurring-clock-proof": (["ship_clock", "recurring_progress_proved"],
                                        True),
        "claim-rdtim-a1-a2": (["platform_authority", "rdtim_registers"],
                              ["0x00a1", "0x00a2"]),
        "drop-a1-scratch": (["platform_authority", "a1_role"], "time-high"),
        "claim-live-rom-identity": (
            ["platform_authority", "live_vectors_equal_bound_defaults"], True),
        "select-mapping": (["mapping", "hypothesis"], "selected"),
        "drop-live-io-proof": (["mapping", "live_io_seen_during_wait"], False),
        "claim-product-byte": (["scope", "product_candidate_bytes_changed"], 1),
        "claim-product-fix": (["scope", "product_fixes"], 1),
        "claim-product-link": (["scope", "product_links"], 1),
        "claim-new-contact": (["scope", "new_hardware_contacts"], 1),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in changes.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(candidate)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"verification mutation survived: {name}")
    return rejected


def main() -> int:
    require(sha(RUNTIME_ELF) == RUNTIME_SHA, "Link-86 Runtime ELF drift")
    require(sha(STAGER_ELF) == STAGER_SHA, "Link-86 Stager ELF drift")
    runtime = ElfTruth.read(RUNTIME_ELF, llvm_readobj=READOBJ,
                            include_section_data=True)
    stager = ElfTruth.read(STAGER_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    getin_runtime = ElfTruth.read(GETIN_ELF, llvm_readobj=READOBJ,
                                  include_section_data=True)
    wait_runtime = ElfTruth.read(WAIT_ELF, llvm_readobj=READOBJ,
                                 include_section_data=True)

    getin = load(GETIN_RECEIPT)
    wait_prep = load(WAIT_PREP)
    wait_device = load(WAIT_DEVICE)
    link85 = load(LINK85_JIFFY)
    boot_contract = load(BOOT_CONTRACT)
    boot_gate = load(BOOT_GATE_RECEIPT)
    sample = source(SAMPLE)
    wait_source = source(WAIT)
    time_source = source(TIME)
    ship_io = source(SHIP_IO)
    runtime_main = source(RUNTIME_MAIN)
    stager_source = source(STAGER)
    chain_source = source(CHAIN)

    require(sample.index("(wait 1)") < sample.index("(read-line)"),
            "interactive sample order drift")
    require("(%time-read)" in wait_source
            and "(peek 255 132)" in time_source
            and "(peek 255 131)" in time_source,
            "public wait/time read chain drift")
    require("0x00a2" in ship_io and "0x00a1" in ship_io
            and "if (ship_jiffy_advanced(before)) return 1u;" in ship_io,
            "Ship time source/proof drift")
    require(boot_contract["target"]["progress_witness"]
            == "$A1/$A2 must change within three physical raster wraps",
            "boot contract progress claim drift")
    require(boot_gate["status"]
            == "passed-ship-boot-arms-and-verifies-inherited-io"
            and boot_gate["host_execution"]["executions"] == 1,
            "standing boot gate receipt drift")

    getin_red = getin["device_preflight_first_red"]
    require(getin["status"] == "TOOL-FIRST-RED-GETIN-ONLY-SAMPLER-NOT-LIVE"
            and getin_red["physical_keys"] == 0
            and getin_red["witness_immediate"] == [0] * 6
            and getin_red["witness_28_seconds_later"] == [0] * 6,
            "GETIN-only target witness drift")
    require(wait_prep["facts"]["sampler"]["call_sites"]
            == ["frame-peek", "getin"],
            "corrected sampler call-site inventory drift")
    require(wait_device["status"] == "DEVICE-DISCRIMINATOR-CPU-QUEUE-PRESENT"
            and wait_device["witness"]["pre"] == [255, 0, 255, 0, 0, 0]
            and wait_device["witness"]["post"]
            == [255, 128, 65, 1, 128, 65],
            "frame-peek-aware device witness drift")

    jiffy_address, jiffy_bytes = symbol_bytes(runtime, "ship_jiffy_read")
    require(jiffy_bytes == bytes.fromhex(
        "a6 a1 a5 a2 a4 a1 84 04 e4 04 d0 f4 60"),
        "linked Ship A1/A2 reader drift")
    start_address, start = symbol_bytes(runtime, "_start", unsized=64)
    require(start[9:14] == bytes.fromhex("a2 44 8e 30 d0"),
            "Runtime D030 immediate drift")
    getin_sites = pattern_sites(runtime, bytes.fromhex("20 e4 ff"))
    require(getin_sites == ["0x6512", "0x65c3", "0x6804"],
            "linked GETIN call-site inventory drift")
    runtime_unlock = pattern_sites(
        runtime, bytes.fromhex("a2 47 8e 2f d0 a2 53 8e 2f d0"))
    stager_unlock = pattern_sites(
        stager, bytes.fromhex("a2 47 8e 2f d0 a2 53 8e 2f d0"))
    require("c2_kernal_map_window" not in runtime.symbols_by_name
            and "c2_kernal_map_window" not in stager.symbols_by_name,
            "Ship unexpectedly linked Workbench MAP ownership")
    require("0xD02F = 0x47" in runtime_main
            and "0xD02F = 0x53" in runtime_main
            and "io_enable();" in stager_source
            and "\tmap" not in chain_source.lower(),
            "Ship I/O source binding drift")
    require(getin_runtime.symbol("ship_jiffy_read").value > 0
            and wait_runtime.symbol("ship_jiffy_read").value > 0,
            "diagnostic Runtime ELF identity drift")

    rom_binding = load(ROM_CONTRACT)["toolchain_bindings"]["rom"]
    rom_path = Path(rom_binding["path"])
    require(rom_binding["sha256"] == ROM_SHA and sha(rom_path) == ROM_SHA,
            "bound MEGA65 ROM drift")
    rom = rom_path.read_bytes()
    require(len(rom) == 0x20000, "bound MEGA65 ROM size drift")
    cpu = memoryview(rom)[0x10000:]
    require(bytes(cpu[0xFFDE:0xFFE1]) == bytes.fromhex("4c 13 f8"),
            "bound ROM RDTIM vector drift")
    require(bytes(cpu[0xF813:0xF82D]) == bytes.fromhex(
        "ad 0b dc 10 0a 29 1f 08 78 f8 18 69 12 d8 28 a8 "
        "ae 0a dc ad 09 dc ab 08 dc 60"),
        "bound ROM RDTIM CIA-TOD implementation drift")
    default_irq = int.from_bytes(cpu[0xFE08:0xFE0A], "little")
    default_getin_offset = 0xFE08 + (0x032A - 0x0314)
    default_getin = int.from_bytes(
        cpu[default_getin_offset:default_getin_offset + 2], "little")
    require(default_irq == 0xF9EC and default_getin == 0xF31C,
            "bound ROM default vector table drift")
    require(bytes(cpu[0xF9F9:0xFA02])
            == bytes.fromhex("ad 30 d0 85 a1 29 fe 8d 30")
            and bytes(cpu[0xFA41:0xFA48])
            == bytes.fromhex("a5 a1 89 68 8d 30 d0"),
            "bound ROM A1 scratch use drift")

    first_jiffy = link85["samples"]["first"]["jiffy_bytes"]
    second_jiffy = link85["samples"]["second"]["jiffy_bytes"]
    live_irq = link85["samples"]["first"]["irq_vector"]
    live_getin = link85["samples"]["first"]["getin_vector"]
    require(first_jiffy == [0x64, 0x00] and second_jiffy == first_jiffy,
            "Link-85 target A1/A2 baseline drift")
    require(live_irq == 0xF974 and live_getin == 0xF319,
            "Link-85 live vector witness drift")

    facts = {
        "phase_split": {
            "sample_order": ["wait-1", "read-line"],
            "getin_only_immediate": getin_red["witness_immediate"],
            "getin_only_after_28_seconds":
                getin_red["witness_28_seconds_later"],
            "frame_peek_samples_before_key": wait_device["witness"]["pre"][0],
            "selected_boundary": "wait-before-getin",
            "getin_reached": False,
        },
        "ship_clock": {
            "logical_addresses": ["0xff83", "0xff84"],
            "physical_addresses": ["0x00a2", "0x00a1"],
            "reader_symbol": f"0x{jiffy_address:04x}",
            "boot_acceptance": "one-change-is-success",
            "recurring_progress_proved": False,
        },
        "platform_authority": {
            "rom_sha256": ROM_SHA,
            "rdtim": "0xffde->0xf813",
            "rdtim_registers": ["0xdc0b", "0xdc0a", "0xdc09", "0xdc08"],
            "a1_role": "irq-scratch-for-d030",
            "rdtim_uses_a1_a2": False,
            "bound_default_vectors": {
                "irq": f"0x{default_irq:04x}",
                "getin": f"0x{default_getin:04x}",
            },
            "link85_live_vectors": {
                "irq": f"0x{live_irq:04x}",
                "getin": f"0x{live_getin:04x}",
            },
            "live_vectors_equal_bound_defaults": False,
            "claim_limit": (
                "The configured ROM proves that A1/A2 is not its RDTIM source "
                "and that A1 is scratch in its default IRQ path. The Link-85 "
                "live vectors differ, so this receipt does not claim the exact "
                "live handler instruction sequence."
            ),
        },
        "false_green": {
            "pre_fix_live_a1_a2": first_jiffy,
            "runtime_start": f"0x{start_address:04x}",
            "runtime_d030_immediate": "0x44",
            "standing_gate_status": boot_gate["status"],
            "mechanism": "wrong-A1/A2-time-contract-plus-one-shot-change-proof",
            "bounded_rom_explanation": (
                "The Runtime changes D030 from the captured inherited value "
                "0x64 to 0x44. The configured ROM's default IRQ path uses A1 "
                "as D030 scratch, so one IRQ can change A1 once and satisfy the "
                "boot test without establishing a recurring clock."
            ),
        },
        "mapping": {
            "runtime_io_unlock_sites": runtime_unlock,
            "stager_io_unlock_sites": stager_unlock,
            "linked_map_owner": False,
            "live_io_seen_during_wait": True,
            "getin_call_sites": getin_sites,
            "getin_reachable_after_wait_only": True,
            "hypothesis": "refuted-as-current-cause",
            "reason": (
                "The failed target run never reaches GETIN. The frame-peek "
                "sampler already sees live D60A/D619 under the current mapping."
            ),
        },
        "scope": {
            "product_candidate_bytes_changed": 0,
            "product_fixes": 0,
            "product_links": 0,
            "new_hardware_contacts": 0,
            "v1.3_status": "closed-pending-owner-review",
        },
    }
    audit(facts)
    rejected = mutations(facts)

    result = {
        "format": "lisp65-c2.3-v1.3-link86-consumer-path-host-elf-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED-WRONG-A1-A2-TIMEBASE-ONE-SHOT-FALSE-GREEN",
        "candidate_link": 86,
        "attribution": {
            "selected_phase": "initial-wait-before-GETIN",
            "mechanism": (
                "Ship exposes A1/A2 as its public frame counter even though the "
                "configured MEGA65 KERNAL uses CIA TOD for RDTIM and uses A1 as "
                "IRQ scratch. Boot accepts one incidental A1/A2 change as proof "
                "of a recurring clock; public wait then observes no progress."
            ),
            "mapping_hypothesis": "refuted-as-current-cause",
            "getin_and_keyboard": "not-reached-not-tested-by-failed-sample",
            "standing_gate": (
                "source-consistent but platform-semantically insufficient; it "
                "proves one mutation, not a recurring target time source"
            ),
        },
        "facts": facts,
        "verification": {
            "executions": 1,
            "mutation_count": len(rejected),
            "mutations_rejected": rejected,
            "elf_truth_consumers": 4,
        },
        "bindings": {
            "owner_review": bind(REVIEW),
            "driver": bind(DRIVER),
            "elf_truth": bind(ELF_TRUTH),
            "llvm_readobj": bind(READOBJ),
            "runtime_elf": bind(RUNTIME_ELF),
            "stager_elf": bind(STAGER_ELF),
            "getin_only_runtime_elf": bind(GETIN_ELF),
            "frame_peek_runtime_elf": bind(WAIT_ELF),
            "getin_only_device_receipt": bind(GETIN_RECEIPT),
            "frame_peek_preparation_receipt": bind(WAIT_PREP),
            "frame_peek_device_receipt": bind(WAIT_DEVICE),
            "link85_jiffy_capture": bind(LINK85_JIFFY),
            "standing_boot_gate_receipt": bind(BOOT_GATE_RECEIPT),
            "standing_boot_contract": bind(BOOT_CONTRACT),
            "standing_boot_gate": bind(BOOT_GATE),
            "sample": bind(SAMPLE),
            "wait": bind(WAIT),
            "time": bind(TIME),
            "ship_io": bind(SHIP_IO),
            "runtime_main": bind(RUNTIME_MAIN),
            "shared_raster_arm": bind(RASTER),
            "stager_source": bind(STAGER),
            "stager_chain": bind(CHAIN),
            "rom_contract": bind(ROM_CONTRACT),
            "bound_rom": bind(rom_path),
        },
        "next_owner_boundary": {
            "fix_authorized": False,
            "link_authorized": False,
            "hardware_authorized": False,
            "required_fix_class_if_commissioned": (
                "replace A1/A2 with an owned recurring Ship frame source and "
                "prove recurring progress, not one incidental change"
            ),
        },
        "claim_limit": (
            "One host/source/ELF attribution over already captured Link-85/86 "
            "target evidence. It attributes the wait boundary and the invalid "
            "time-source/proof contract. It does not claim the exact live ROM "
            "IRQ implementation, GETIN execution, a product fix, successor link, "
            "new hardware contact, acceptance, or release readiness."
        ),
    }
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RECEIPT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(RECEIPT)
    print(
        "c2-v13-link86-consumer-path-attribution: PASS "
        "phase=wait-before-getin mechanism=wrong-A1-A2-timebase "
        f"mutations={len(rejected)} product-bytes=0 links=0 hardware=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-consumer-path-attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
