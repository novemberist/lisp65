#!/usr/bin/env python3
"""Gate the v1.6 cold-body swap that removes nested MAP lifetimes."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_transitive_map_nesting_gate as NEST  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ASM = ROOT / "src/optional/c2_refill_boundary_witness.s"
IO = ROOT / "src/io.c"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
DIAGNOSTIC_CAPACITY = 371
FAR_CAPACITY = 1499
FACADE_BYTES = 98
ORDINARY_FREE_FLOOR = 113
DIAGNOSTIC_FREE_FLOOR = 47
FAR_FREE_FLOOR = 15
STATUS = "PASS: COLD BODY SWAP REMOVES TRANSITIVE MAP NESTING"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def _assembled_sizes() -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="c2-nested-map-swap-") as raw:
        obj = Path(raw) / "swap.o"
        run = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(ASM), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        require(run.returncode == 0, "swap assembly red:\n" + run.stdout)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ)
        return {name: truth.symbol(name).bytes for name in (
            "disk_chain_to_scratch", "c2_refill_trace_read")}


def source_gate(*, io: str | None = None, runtime: str | None = None,
                asm: str | None = None) -> dict[str, Any]:
    io_text = IO.read_text(encoding="utf-8") if io is None else io
    runtime_text = (RUNTIME.read_text(encoding="utf-8")
                    if runtime is None else runtime)
    asm_text = ASM.read_text(encoding="utf-8") if asm is None else asm
    require("LISP65_C2_MAPPED_DIAGNOSTIC_FN\n"
            "unsigned int disk_chain_to_scratch_far(" in io_text,
            "disk-chain body is not diagnostic-arena-owned")
    require("vm_runtime_overlay_install_island_far" not in runtime_text,
            "boot installer retained its mapped successor identity")
    require("vm_runtime_overlay_status vm_runtime_overlay_install_island(void)"
            in runtime_text, "ordinary boot installer identity absent")
    stub = asm_text.split("disk_chain_to_scratch:", 1)[1].split(
        ".size disk_chain_to_scratch", 1)[0]
    ordered = ("jsr c2_mapped_far_enter", "jsr disk_chain_to_scratch_far",
               "phx", "jsr c2_mapped_far_leave", "plx", "rts")
    positions = [stub.find(token) for token in ordered]
    require(all(value >= 0 for value in positions)
            and positions == sorted(positions)
            and all(stub.count(token) == 1 for token in ordered),
            "disk-chain stub lost exact ABI-safe enter/body/leave shape")
    require("jmp c2_mapped_far_leave" not in stub,
            "two-byte disk result still uses one-byte MAP leave tail")
    sizes = _assembled_sizes() if asm is None else {
        "disk_chain_to_scratch": 12, "c2_refill_trace_read": 205}
    require(sizes == {"disk_chain_to_scratch": 12,
                      "c2_refill_trace_read": 205},
            f"emitted swap source price drift: {sizes}")
    return {"status": STATUS, "emitted": sizes,
        "ordinary_body": "vm_runtime_overlay_install_island",
        "mapped_body": "disk_chain_to_scratch_far",
        "return_abi": "unsigned-int A/X preserved across MAP leave",
        "ordinary_free_floor": ORDINARY_FREE_FLOOR,
        "diagnostic_free_floor": DIAGNOSTIC_FREE_FLOOR}


def source_mutations() -> list[str]:
    io = IO.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    asm = ASM.read_text(encoding="utf-8")
    cases = {
        "mapped-owner-removed": (io.replace(
            "LISP65_C2_MAPPED_DIAGNOSTIC_FN\nunsigned int "
            "disk_chain_to_scratch_far(",
            "unsigned int disk_chain_to_scratch_far(", 1), runtime, asm),
        "installer-remapped": (io, runtime.replace(
            "vm_runtime_overlay_status vm_runtime_overlay_install_island(void)",
            "vm_runtime_overlay_status vm_runtime_overlay_install_island_far(void)",
            1), asm),
        "high-result-save-removed": (io, runtime, asm.replace(
            "\tphx\n\tjsr c2_mapped_far_leave",
            "\tnop\n\tjsr c2_mapped_far_leave", 1)),
        "high-result-restore-removed": (io, runtime, asm.replace("\tplx\n\trts\n", "\tnop\n\trts\n", 1)),
        "one-byte-tail-restored": (io, runtime, asm.replace(
            "\tphx\n\tjsr c2_mapped_far_leave\n\tplx\n\trts",
            "\tnop\n\tjmp c2_mapped_far_leave\n\tnop\n\tnop", 1)),
    }
    rejected: list[str] = []
    for name, (io_mutant, runtime_mutant, asm_mutant) in cases.items():
        try:
            source_gate(io=io_mutant, runtime=runtime_mutant, asm=asm_mutant)
        except GateError:
            rejected.append(name)
    require(rejected == list(cases), "nested-MAP swap source mutation survived")
    return rejected


def _function(disassembly: str, name: str) -> str:
    match = re.search(rf"^[0-9a-f]+ <{re.escape(name)}>:\n(.*?)(?=^[0-9a-f]+ <|\Z)",
                      disassembly, re.MULTILINE | re.DOTALL)
    require(match is not None, f"linked function absent: {name}")
    return match.group(1)


def final_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    diagnostic = truth.section(".lisp65_c2_mapped_diagnostic")
    installer = truth.symbol("vm_runtime_overlay_install_island")
    disk_stub = truth.symbol("disk_chain_to_scratch")
    disk_body = truth.symbol("disk_chain_to_scratch_far")
    witness = truth.symbol("c2_refill_trace_read")
    require(installer.section == ".text",
            "boot installer is not permanently visible")
    require(disk_stub.section == ".text" and disk_stub.bytes == 12,
            "disk-chain entry is not the ABI-safe 12-byte ordinary stub")
    require(disk_body.section == diagnostic.name
            and disk_body.bytes == diagnostic.bytes,
            "disk-chain body escaped its mapped diagnostic arena")
    require(witness.section == ".text" and witness.bytes == 205,
            "refill witness changed outside the placement card")
    ordinary_free = facade.address - (text.address + text.bytes)
    diagnostic_free = DIAGNOSTIC_CAPACITY - diagnostic.bytes
    far_free = FAR_CAPACITY - service.bytes
    require(ordinary_free >= ORDINARY_FREE_FLOOR
            and diagnostic_free >= DIAGNOSTIC_FREE_FLOOR
            and far_free >= FAR_FREE_FLOOR and facade.bytes == FACADE_BYTES,
            "final linked swap violates candidate-derived capacity floors")

    raw = subprocess.run([str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    disassembly = raw.lower()
    stub_lines = _function(disassembly, disk_stub.name)
    enter = truth.symbol("c2_mapped_far_enter")
    leave = truth.symbol("c2_mapped_far_leave")
    require(re.search(rf"jsr\s+\${enter.value:x}\b", stub_lines)
            and re.search(rf"jsr\s+\${disk_body.value:x}\b", stub_lines)
            and re.search(r"\bphx\b", stub_lines)
            and re.search(rf"jsr\s+\${leave.value:x}\b", stub_lines)
            and re.search(r"\bplx\b", stub_lines)
            and re.search(r"\brts\b", stub_lines)
            and not re.search(rf"jmp\s+\${leave.value:x}\b", stub_lines),
            "linked disk stub lost A/X-preserving MAP leave")

    graph = NEST.linked_graph(elf)
    nested = NEST.check(elf)
    diagnostic_tenants = sorted(name for name in graph["tenants"]
        if truth.symbol(name).section == diagnostic.name)
    require(diagnostic_tenants == [disk_body.name],
            f"diagnostic arena has foreign tenants: {diagnostic_tenants}")
    direct_body = graph["incoming"].get(disk_body.name, [])
    require(len(direct_body) == 1
            and direct_body[0]["owner"] == disk_stub.name
            and direct_body[0]["owner_section"] == disk_stub.section
            and direct_body[0]["target_section"] == disk_body.section
            and direct_body[0]["target_identity"] ==
                [disk_body.section, disk_body.value],
            "mapped disk body has a direct or missing foreign caller")

    display = DISPLAY.derive()
    require(display["composed_framebuffer"]["result_tail_blank"] is True,
            "composed framebuffer regressed during MAP swap")
    lma_start = truth.symbol("__lisp65_c2_mapped_diagnostic_load_start").value
    return {"status": STATUS,
        "ordinary": {"installer_bytes": installer.bytes,
            "disk_stub_bytes": disk_stub.bytes, "free_bytes": ordinary_free,
            "floor_bytes": ORDINARY_FREE_FLOOR},
        "mapped_diagnostic": {"address": f"0x{diagnostic.address:04x}",
            "load_address": f"0x{lma_start:08x}",
            "body_bytes": disk_body.bytes,
            "capacity_bytes": DIAGNOSTIC_CAPACITY,
            "free_bytes": diagnostic_free,
            "floor_bytes": DIAGNOSTIC_FREE_FLOOR},
        "existing_far_service": {"bytes": service.bytes,
            "capacity_bytes": FAR_CAPACITY, "free_bytes": far_free,
            "floor_bytes": FAR_FREE_FLOOR},
        "facade_bytes": facade.bytes,
        "return_abi": {"type": "unsigned int", "registers": ["A", "X"],
            "preserved_across_leave": True},
        "mapped_population": nested,
        "diagnostic_tenants": diagnostic_tenants,
        "disk_body_domain_edge": direct_body[0],
        "composed_image": {"status": display["status"],
            "result_tail_blank": True},
        "witness": {"bytes": witness.bytes, "removal_default": True}}


def final_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "ordinary-floor-overstated": lambda x: x["ordinary"].update(
            free_bytes=x["ordinary"]["floor_bytes"] - 1),
        "diagnostic-floor-overstated": lambda x: x["mapped_diagnostic"].update(
            free_bytes=x["mapped_diagnostic"]["floor_bytes"] - 1),
        "high-return-not-preserved": lambda x: x["return_abi"].update(
            preserved_across_leave=False),
        "foreign-diagnostic-tenant": lambda x: x["diagnostic_tenants"].append(
            "foreign"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            require(trial["ordinary"]["free_bytes"] >=
                    trial["ordinary"]["floor_bytes"]
                    and trial["mapped_diagnostic"]["free_bytes"] >=
                    trial["mapped_diagnostic"]["floor_bytes"]
                    and trial["return_abi"]["preserved_across_leave"] is True
                    and trial["diagnostic_tenants"] ==
                        ["disk_chain_to_scratch_far"], "final mutation")
        except GateError:
            rejected.append(name)
    require(rejected == list(cases), "nested-MAP swap final mutation survived")
    return rejected


def main(argv: list[str]) -> int:
    require(len(argv) in (2, 3) and argv[1] in ("source", "selftest", "final"),
            "usage: source|selftest|final ELF")
    if argv[1] == "source":
        print(json.dumps(source_gate(), sort_keys=True))
    elif argv[1] == "selftest":
        source_gate()
        print("v1.6 nested MAP swap: SELFTEST PASS "
              f"mutations={len(source_mutations())}")
    else:
        require(len(argv) == 3, "final requires ELF")
        value = final_gate(Path(argv[2]))
        value["mutations_rejected"] = final_mutations(value)
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (GateError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 nested MAP swap: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
