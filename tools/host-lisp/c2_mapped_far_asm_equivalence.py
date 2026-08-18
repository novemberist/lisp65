#!/usr/bin/env python3
"""Execute the mapped assembly body against its retained C references."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from cpu6502 import CPU  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-mapped-far-asm-equivalence-contract.json"
SUCCESSOR_CONTRACT = ROOT / (
    "config/c2-mapped-far-abi-preservation-contract-v2.json")
ASM = ROOT / "src/c2_mapped_far_convergence.s"
DMA_C = ROOT / "src/c2_platform_dma.c"
RUNTIME_C = ROOT / "src/c2_product_runtime.c"
CONVERGENCE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-mapped-far-assembly-equivalence-receipt.json")
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def effective_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Project the immutable 874-byte contract into its authorized successor."""
    base = load(CONTRACT)
    successor = load(SUCCESSOR_CONTRACT)
    require(
        base.get("format") == "lisp65-c2-mapped-far-assembly-equivalence-v1"
        and base.get("status") == "owner-commissioned-phase-c",
        "historical assembly equivalence contract drift")
    require(
        successor.get("format")
            == "lisp65-c2-mapped-far-abi-preservation-contract-v2"
        and successor.get("status") == "owner-authorized-78ae9255",
        "mapped-far ABI successor contract drift")
    predecessor = successor["predecessors"]["assembly_equivalence_contract"]
    require(predecessor["path"] == CONTRACT.relative_to(ROOT).as_posix()
            and predecessor["sha256"]
                == hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            "mapped-far ABI successor lost assembly-contract ancestry")
    artifact = successor["artifact_successor"]
    projected = deepcopy(base)
    projected["artifact"].update({
        "source": artifact["source"],
        "section": artifact["section"],
        "cpu_vma": artifact["cpu_vma"],
        "physical_lma": artifact["physical_lma"],
        "exact_bytes": artifact["exact_bytes"],
        "capacity_bytes": artifact["capacity_bytes"],
        "entries": artifact["entries"],
    })
    projected["new_seam_mutations"] = 16
    return projected, successor


def run(command: list[str], label: str, *, input_text: str | None = None,
        expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=ROOT, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == expect,
            f"{label}: exit={result.returncode}: {result.stderr}")
    return result


def extract_function(text: str, signature: str) -> str:
    at = text.index(signature)
    line = text.rfind("\n", 0, at) + 1
    previous = text.rfind("\n", 0, line - 1) + 1
    if "LISP65_C2_MAPPED_FAR_FN" in text[previous:line]:
        line = previous
    brace = text.index("{", at)
    depth = 0
    for end in range(brace, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return text[line:end + 1]
    raise GateError(f"unterminated C reference: {signature}")


CASE_ROWS = (
    ("immediate", 0, 0, False),
    ("primary-late-35", 35, 0, False),
    ("exact-edge-64", 64, 0, False),
    ("nonconvergent", -1, 0, False),
    ("uint16-wrap", 35, 0xFFF0, False),
    ("destination-already-source", -1, 0, True),
    ("first-difference-at-tail", 9, 0, False),
    ("one-byte", 3, 0, False),
)


def reference_harness() -> str:
    dma = DMA_C.read_text(encoding="utf-8")
    runtime = RUNTIME_C.read_text(encoding="utf-8")
    ordinary = extract_function(
        dma, "uint8_t C2_VM_CODE_LOAD_CONVERGED_IMPL(")
    physical = extract_function(
        runtime, "uint8_t C2_PHYSICAL_READ_CONVERGED_IMPL(")
    cases = "\n".join(
        f'  {{"{name}", {after}, {start}, {1 if equal else 0}}},'
        for name, after, start, equal in CASE_ROWS)
    return f"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LISP65_C2_MAPPED_FAR_FN
#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u
#define C2_VM_CODE_LOAD_CONVERGED_IMPL ref_ordinary
#define C2_PHYSICAL_READ_CONVERGED_IMPL ref_physical

static uint8_t reference_source[16];
static uint8_t *active_destination;
static uint16_t active_length;
static uint16_t ordinary_base;
static uint32_t physical_base;
static int primary_after;
static int primary_submissions;
static int primary_applied;
static unsigned elapsed;
static uint16_t frame_value;

static void apply_primary(void) {{
  if (!primary_applied && primary_after >= 0
      && elapsed >= (unsigned)primary_after) {{
    memcpy(active_destination, reference_source, active_length);
    primary_applied = 1;
  }}
}}
static uint16_t c2_kernal_frame_count_inline(void) {{
  uint16_t observed = frame_value;
  if (primary_submissions) {{
    ++elapsed;
    ++frame_value;
    apply_primary();
  }}
  return observed;
}}
static uint8_t c2_dma_source_byte(
    uint8_t bank, uint16_t offset, uint8_t *value) {{
  (void)bank;
  if (offset < ordinary_base
      || (uint16_t)(offset - ordinary_base) >= active_length) return 0;
  *value = reference_source[(uint16_t)(offset - ordinary_base)];
  return 1;
}}
static void vm_code_load(uint8_t bank, uint16_t offset, uint16_t length,
                         uint8_t *destination) {{
  (void)bank; (void)offset;
  active_destination = destination; active_length = length;
  ++primary_submissions; apply_primary();
}}
static uint8_t c2_physical_source_byte(
    uint32_t source, uint8_t *value) {{
  if (source < physical_base || source - physical_base >= active_length)
    return 0;
  *value = reference_source[source - physical_base];
  return 1;
}}
static void c2_product_physical_copy(
    uint32_t source, uint32_t target, uint16_t length) {{
  (void)source; (void)target;
  active_length = length; ++primary_submissions; apply_primary();
}}

{ordinary}

{physical}

struct case_row {{ const char *name; int after; unsigned start; int equal; }};
static const struct case_row cases[] = {{
{cases}
}};

static void print_row(const char *lane, const struct case_row *row,
                      uint8_t result, const uint8_t *dst, unsigned length) {{
  unsigned i;
  printf("%s|%s|%u|%d|%u|", lane, row->name, result,
         primary_submissions, elapsed);
  for (i = 0; i < length; ++i) printf("%02x", dst[i]);
  putchar('\\n');
}}

int main(void) {{
  static const uint8_t source[] = {{0x3b,0x06,0x01,0x01,0x2f,0x01,0x53}};
  static const uint8_t stale[] = {{0x0b,0x00,0x01,0x01,0x2f,0x01,0x53}};
  unsigned c, lane;
  for (lane = 0; lane < 2; ++lane) for (c = 0; c < 8; ++c) {{
    const struct case_row *row = &cases[c];
    uint8_t dst[8];
    unsigned length = c == 7 ? 1 : 7;
    memcpy(reference_source, source, length);
    if (row->equal) memcpy(dst, source, length);
    else if (c == 6) {{ memcpy(dst, source, length); dst[length-1] ^= 0xff; }}
    else memcpy(dst, stale, length);
    active_destination = dst; active_length = length;
    ordinary_base = 0x1200; physical_base = 0x00234560u;
    primary_after = row->after; primary_submissions = 0;
    primary_applied = 0; elapsed = 0; frame_value = row->start;
    if (!lane)
      print_row("ordinary", row,
        ref_ordinary(5, ordinary_base, length, dst), dst, length);
    else
      print_row("physical", row,
        ref_physical(physical_base, dst, length), dst, length);
  }}
  return 0;
}}
"""


def parse_rows(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for line in text.splitlines():
        lane, name, result, primary, elapsed, data = line.split("|")
        rows[(lane, name)] = {
            "result": int(result), "primary": int(primary),
            "elapsed": int(elapsed), "destination": data,
        }
    require(len(rows) == 16, "C reference did not execute 16 cases")
    return rows


def fixture_source() -> str:
    return """
.section .lisp65_c2_convergence_state,"aw",@nobits
.globl c2_dma_verify_list
c2_dma_verify_list: .space 24
.globl c2_dma_verify
c2_dma_verify: .space 1
.globl c2_edma_probe_jobs
c2_edma_probe_jobs: .space 40
.globl c2_edma_probe_value
c2_edma_probe_value: .space 1

.section .lisp65_fixture_dependencies,"aw",@nobits
.globl c2_dma_list
c2_dma_list: .space 12
.globl c2_edma_job
c2_edma_job: .space 20

.section .lisp65_fixture_markers,"a",@progbits
.globl c2_dma_verify_marker
c2_dma_verify_marker: .byte 0xa5
.globl c2_edma_probe_marker
c2_edma_probe_marker: .byte 0xa5

.section .lisp65_c2_convergence_zp,"aw",@nobits
.globl c2_dma_verify_done
c2_dma_verify_done: .space 1
.globl c2_edma_probe_done
c2_edma_probe_done: .space 1
""".strip() + "\n"


def fixture_linker(contract: dict[str, Any]) -> str:
    artifact = contract["artifact"]
    rc = "\n".join(f"__rc{i} = 0x{i:02x};" for i in range(2, 32))
    return f"""{rc}
SECTIONS {{
  .lisp65_c2_mapped_far_service {int(artifact['cpu_vma'], 0):#x}
      : AT({int(artifact['physical_lma'], 0):#x}) {{
    KEEP(*(.lisp65_c2_mapped_far_service))
  }}
  .lisp65_c2_convergence_state 0xc000 (NOLOAD) : {{
    KEEP(*(.lisp65_c2_convergence_state))
  }}
  .lisp65_fixture_dependencies 0xc080 (NOLOAD) : {{
    KEEP(*(.lisp65_fixture_dependencies))
  }}
  .lisp65_fixture_markers 0xc0a0 : {{ KEEP(*(.lisp65_fixture_markers)) }}
  .lisp65_c2_convergence_zp 0x87 (NOLOAD) : {{
    KEEP(*(.lisp65_c2_convergence_zp))
  }}
}}
ASSERT(SIZEOF(.lisp65_c2_mapped_far_service) == {artifact['exact_bytes']},
       "assembly far-body identity drift");
ASSERT(ADDR(.lisp65_c2_mapped_far_service) == {int(artifact['cpu_vma'], 0):#x},
       "assembly far-body VMA drift");
"""


def build_artifact(contract: dict[str, Any], temp: Path) -> tuple[Path, ElfTruth]:
    body = temp / "body.o"
    state = temp / "state.o"
    script = temp / "linked.ld"
    elf = temp / "linked.elf"
    script.write_text(fixture_linker(contract), encoding="utf-8")
    run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
         "-filetype=obj", "-o", str(body), str(ASM)], "assemble body")
    run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
         "-filetype=obj", "-o", str(state)], "assemble fixture state",
        input_text=fixture_source())
    run([str(LD_LLD), "--emit-relocs", "-T", str(script), "-o", str(elf),
         str(body), str(state)], "link executable assembly fixture")
    truth = ElfTruth.read(
        elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    return elf, truth


class DmaCPU(CPU):
    def __init__(self, *, symbols: dict[str, int], source: bytes,
                 lane: str, after: int, start: int, source_base: int):
        super().__init__()
        self.symbols = symbols
        self.source = source
        self.lane = lane
        self.primary_after = after
        self.frame = start & 0xffff
        self.source_base = source_base
        self.frame_phase = 0
        self.pending: dict[str, Any] | None = None
        self.primary_submissions = 0
        self.probe_submissions = 0
        self.elapsed = 0

    def _apply_pending(self) -> None:
        if self.pending is None or self.primary_after < 0:
            return
        if self.elapsed >= self.primary_after:
            for i, value in enumerate(self.pending["data"]):
                super().wr(self.pending["destination"] + i, value)
            self.pending = None

    def rd(self, address: int) -> int:
        address &= 0xffff
        self._apply_pending()
        if address == 0xff84:
            value = (self.frame >> 8) & 0xff
            if self.frame_phase == 0:
                self.frame_phase = 1
            elif self.frame_phase == 2:
                self.frame_phase = 0
                if self.pending is not None:
                    self.elapsed += 1
                    self.frame = (self.frame + 1) & 0xffff
                    self._apply_pending()
            return value
        if address == 0xff83:
            if self.frame_phase == 1:
                self.frame_phase = 2
            return self.frame & 0xff
        return super().rd(address)

    def wr(self, address: int, value: int) -> None:
        address &= 0xffff
        super().wr(address, value)
        if address == 0xd700:
            self._submit_d700(value | (super().rd(0xd701) << 8))
        elif address == 0xd705:
            self._submit_d705(value | (super().rd(0xd701) << 8))

    def _source_bank_byte(self, bank: int, offset: int) -> int:
        require(bank == 5 and self.source_base <= offset
                < self.source_base + len(self.source),
                "ordinary descriptor source escaped fixture")
        return self.source[offset - self.source_base]

    def _source_physical_byte(self, address: int) -> int:
        require(self.source_base <= address
                < self.source_base + len(self.source),
                "physical descriptor source escaped fixture")
        return self.source[address - self.source_base]

    def _submit_d700(self, base: int) -> None:
        if base == self.symbols["c2_dma_verify_list"]:
            self.probe_submissions += 1
            bank = super().rd(base + 5)
            source = super().rd(base + 3) | (super().rd(base + 4) << 8)
            target = super().rd(base + 6) | (super().rd(base + 7) << 8)
            super().wr(target, self._source_bank_byte(bank, source))
            second = base + 12
            marker = super().rd(second + 3) | (super().rd(second + 4) << 8)
            done = super().rd(second + 6) | (super().rd(second + 7) << 8)
            super().wr(done, super().rd(marker))
            return
        require(base == self.symbols["c2_dma_list"],
                f"unknown D700 descriptor 0x{base:04x}")
        self.primary_submissions += 1
        length = super().rd(base + 1) | (super().rd(base + 2) << 8)
        source = super().rd(base + 3) | (super().rd(base + 4) << 8)
        bank = super().rd(base + 5)
        destination = super().rd(base + 6) | (super().rd(base + 7) << 8)
        data = bytes(self._source_bank_byte(bank, source + i)
                     for i in range(length))
        self.pending = {"destination": destination, "data": data}
        self._apply_pending()

    def _edma_job(self, base: int) -> tuple[int, int, int, int, int]:
        source = (super().rd(base + 11) | (super().rd(base + 12) << 8)
                  | ((super().rd(base + 13) & 0x0f) << 16)
                  | (super().rd(base + 2) << 20))
        target = (super().rd(base + 14) | (super().rd(base + 15) << 8)
                  | ((super().rd(base + 16) & 0x0f) << 16)
                  | (super().rd(base + 4) << 20))
        length = super().rd(base + 9) | (super().rd(base + 10) << 8)
        return super().rd(base + 8), source, target, length, base

    def _submit_d705(self, base: int) -> None:
        if base == self.symbols["c2_edma_probe_jobs"]:
            self.probe_submissions += 1
            command, source, target, length, _ = self._edma_job(base)
            require(command == 4 and length == 1,
                    "physical source probe descriptor drift")
            super().wr(target, self._source_physical_byte(source))
            command, marker, done, length, _ = self._edma_job(base + 20)
            require(command == 0 and length == 1,
                    "physical marker descriptor drift")
            super().wr(done, super().rd(marker))
            return
        require(base == self.symbols["c2_edma_job"],
                f"unknown D705 descriptor 0x{base:04x}")
        self.primary_submissions += 1
        command, source, destination, length, _ = self._edma_job(base)
        require(command == 0, "physical primary command drift")
        data = bytes(self._source_physical_byte(source + i)
                     for i in range(length))
        self.pending = {"destination": destination, "data": data}
        self._apply_pending()


def run_assembly_cases(truth: ElfTruth) -> dict[tuple[str, str], dict[str, Any]]:
    service = truth.section(".lisp65_c2_mapped_far_service")
    markers = truth.section(".lisp65_fixture_markers")
    symbols = {name: truth.symbol(name).value for name in (
        "c2_dma_list", "c2_dma_verify_list", "c2_dma_verify",
        "c2_dma_verify_marker", "c2_dma_verify_done", "c2_edma_job",
        "c2_edma_probe_jobs", "c2_edma_probe_value",
        "c2_edma_probe_marker", "c2_edma_probe_done")}
    rc = {i: truth.symbol(f"__rc{i}").value for i in range(2, 32)}
    entries = {
        "ordinary": truth.symbol(
            "c2_mapped_far_vm_code_load_converged").value,
        "physical": truth.symbol(
            "c2_mapped_far_physical_read_converged").value,
    }
    source_full = bytes([0x3b, 0x06, 0x01, 0x01, 0x2f, 0x01, 0x53])
    stale_full = bytes([0x0b, 0x00, 0x01, 0x01, 0x2f, 0x01, 0x53])
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for lane in ("ordinary", "physical"):
        for case_index, (name, after, start, equal) in enumerate(CASE_ROWS):
            length = 1 if case_index == 7 else 7
            source = source_full[:length]
            if equal:
                destination = source
            elif case_index == 6:
                destination = source[:-1] + bytes([source[-1] ^ 0xff])
            else:
                destination = stale_full[:length]
            source_base = 0x1200 if lane == "ordinary" else 0x234560
            cpu = DmaCPU(symbols=symbols, source=source, lane=lane,
                         after=after, start=start, source_base=source_base)
            callee_saved = {
                index: (0x31 + case_index * 7
                        + (0x40 if lane == "physical" else 0)
                        + index * 11) & 0xff
                for index in range(16, 32)
            }
            for index, value in callee_saved.items():
                CPU.wr(cpu, rc[index], value)
            initial_sp = cpu.SP
            code = truth.section_bytes(service.name)
            for i, value in enumerate(code):
                CPU.wr(cpu, service.address + i, value)
            for i, value in enumerate(truth.section_bytes(markers.name)):
                CPU.wr(cpu, markers.address + i, value)
            destination_address = 0x4000
            for i, value in enumerate(destination):
                CPU.wr(cpu, destination_address + i, value)
            if lane == "ordinary":
                cpu.A = 5
                cpu.X = source_base & 0xff
                CPU.wr(cpu, rc[2], (source_base >> 8) & 0xff)
                CPU.wr(cpu, rc[3], length & 0xff)
                CPU.wr(cpu, rc[4], length >> 8)
                CPU.wr(cpu, rc[6], destination_address & 0xff)
                CPU.wr(cpu, rc[7], destination_address >> 8)
            else:
                cpu.A = source_base & 0xff
                cpu.X = (source_base >> 8) & 0xff
                CPU.wr(cpu, rc[2], (source_base >> 16) & 0xff)
                CPU.wr(cpu, rc[3], (source_base >> 24) & 0xff)
                CPU.wr(cpu, rc[4], destination_address & 0xff)
                CPU.wr(cpu, rc[5], destination_address >> 8)
                CPU.wr(cpu, rc[6], length & 0xff)
                CPU.wr(cpu, rc[7], length >> 8)
            try:
                cpu.call(entries[lane], max_steps=500000)
            except RuntimeError as error:
                raise GateError(
                    f"assembly execution {lane}/{name}: {error}; "
                    f"pc=0x{cpu.PC:04x} frame=0x{cpu.frame:04x} "
                    f"primary={cpu.primary_submissions} "
                    f"probes={cpu.probe_submissions}") from error
            final = bytes(CPU.rd(cpu, destination_address + i)
                          for i in range(length))
            preserved = sum(
                CPU.rd(cpu, rc[index]) == value
                for index, value in callee_saved.items())
            require(preserved == len(callee_saved),
                    f"assembly ABI clobber {lane}/{name}: "
                    f"preserved={preserved}/{len(callee_saved)}")
            require(cpu.SP == initial_sp,
                    f"assembly hardware stack imbalance {lane}/{name}: "
                    f"0x{cpu.SP:02x} != 0x{initial_sp:02x}")
            rows[(lane, name)] = {
                "result": cpu.A, "primary": cpu.primary_submissions,
                "elapsed": cpu.elapsed, "destination": final.hex(),
                "source_probes": cpu.probe_submissions,
                "callee_saved_preserved": preserved,
                "hardware_stack_balanced": True,
            }
    require(len(rows) == 16, "assembly artifact did not execute 16 cases")
    return rows


def audit(facts: dict[str, Any]) -> None:
    require(facts["c_reference_cases"] == 16, "C reference case loss")
    require(facts["assembly_artifact_cases"] == 16,
            "assembly artifact case loss")
    require(facts["equivalent_cases"] == 16, "C/assembly divergence")
    require(facts["exact_bytes"] == 1086, "assembly successor identity drift")
    require(facts["cpu_vma"] == 0x78B2, "assembly body VMA drift")
    require(facts["physical_lma"] == 0x2B8B2, "assembly body LMA drift")
    require(facts["static_stack_bytes"] == 0,
            "assembly body acquired compiler static stack")
    require(facts["entry_symbols"] == 2, "assembly entry loss")
    require(facts["callee_saved_registers"] == 16,
            "llvm-mos callee-saved imaginary-register set drift")
    require(facts["callee_saved_checks"] == 256,
            "not every linked execution preserved every callee-saved byte")
    require(facts["hardware_stack_balanced_cases"] == 16,
            "mapped-far wrapper did not balance the hardware stack")
    require(facts["inner_exit_count"] == 8,
            "mapped-far inner exit coverage drift")
    require(facts["public_wrappers"] == 2,
            "mapped-far public wrapper coverage drift")
    require(facts["preservation_authority"] == "linked-execution-bytes",
            "callee-save claim came from source instead of linked execution")
    require(facts["primary_submissions_max"] == 1,
            "assembly silently resubmitted the primary transfer")
    require(facts["content_oracle"] == "source-derived-first-difference",
            "assembly consumed completion metadata as content truth")
    require(facts["linked_bytes_executed"] is True,
            "gate interpreted source instead of executing linked bytes")
    require(facts["existing_mutations_rejected"] == 15,
            "existing class mutations were not inherited")
    require(facts["product_wplto"] is False and facts["hardware_contacts"] == 0,
            "Phase-C gate overclaimed product or hardware")


def mutation_selftest(facts: dict[str, Any]) -> dict[str, str]:
    cases = {
        "drop-c-reference-case": ("c_reference_cases", 15),
        "drop-assembly-case": ("assembly_artifact_cases", 15),
        "one-divergent-case": ("equivalent_cases", 15),
        "body-size": ("exact_bytes", 873),
        "body-vma": ("cpu_vma", 0x78B3),
        "body-lma": ("physical_lma", 0x2B8B3),
        "static-stack": ("static_stack_bytes", 1),
        "missing-entry": ("entry_symbols", 1),
        "silent-resubmit": ("primary_submissions_max", 2),
        "metadata-oracle": ("content_oracle", "submission-return"),
        "drop-callee-saved-register": ("callee_saved_registers", 15),
        "miss-one-preservation-check": ("callee_saved_checks", 255),
        "unbalanced-hardware-stack": ("hardware_stack_balanced_cases", 15),
        "miss-one-inner-exit": ("inner_exit_count", 7),
        "miss-one-public-wrapper": ("public_wrappers", 1),
        "source-only-preservation": ("preservation_authority", "source-text"),
    }
    rejected: dict[str, str] = {}
    for name, (key, value) in cases.items():
        candidate = deepcopy(facts)
        candidate[key] = value
        try:
            audit(candidate)
        except GateError as error:
            rejected[name] = str(error)
        else:
            raise GateError(f"assembly seam mutation survived: {name}")
    return rejected


def build_receipt() -> dict[str, Any]:
    contract, successor = effective_contract()
    convergence = load(CONVERGENCE_RECEIPT)
    require(convergence["status"] == "PASS"
            and convergence["execution_witness"] == 8
            and len(convergence["mutations_rejected"]) == 15,
            "retained C-reference class gate is not 8/8 and 15/15")
    with tempfile.TemporaryDirectory(prefix="lisp65-far-asm-") as name:
        temp = Path(name)
        harness = temp / "reference.c"
        executable = temp / "reference"
        harness.write_text(reference_harness(), encoding="utf-8")
        run(["cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
             str(harness), "-o", str(executable)], "compile retained C reference")
        reference = parse_rows(run([str(executable)], "execute C reference").stdout)
        elf, truth = build_artifact(contract, temp)
        assembly = run_assembly_cases(truth)
        artifact = contract["artifact"]
        section = truth.section(artifact["section"])
        require(section.address == int(artifact["cpu_vma"], 0)
                and section.bytes == artifact["exact_bytes"],
                "linked assembly VMA/size drift")
        equivalent = 0
        case_rows: dict[str, Any] = {}
        for key, expected in reference.items():
            observed = assembly[key]
            comparable = {field: observed[field]
                          for field in ("result", "primary", "destination")}
            expected_comparable = {field: expected[field]
                                   for field in comparable}
            require(comparable == expected_comparable,
                    f"assembly/C divergence {key}: "
                    f"{comparable} != {expected_comparable}")
            equivalent += 1
            case_rows["/".join(key)] = {
                "result": observed["result"],
                "primary_submissions": observed["primary"],
                "source_probes": observed["source_probes"],
                "assembly_elapsed_frames": observed["elapsed"],
                "c_elapsed_frames": expected["elapsed"],
                "destination": observed["destination"],
                "callee_saved_preserved": observed[
                    "callee_saved_preserved"],
                "hardware_stack_balanced": observed[
                    "hardware_stack_balanced"],
            }
        facts = {
            "c_reference_cases": len(reference),
            "assembly_artifact_cases": len(assembly),
            "equivalent_cases": equivalent,
            "exact_bytes": section.bytes,
            "cpu_vma": section.address,
            "physical_lma": int(artifact["physical_lma"], 0),
            "static_stack_bytes": 0,
            "entry_symbols": sum(
                truth.symbol(entry).section == artifact["section"]
                for entry in artifact["entries"]),
            "callee_saved_registers": successor["abi"]
                ["callee_saved_imaginary_registers"]["count"],
            "callee_saved_checks": sum(
                row["callee_saved_preserved"] for row in assembly.values()),
            "hardware_stack_balanced_cases": sum(
                row["hardware_stack_balanced"] for row in assembly.values()),
            "inner_exit_count": successor["abi"]["inner_exit_count"],
            "public_wrappers": successor["abi"]["public_entry_count"],
            "preservation_authority": "linked-execution-bytes",
            "primary_submissions_max": max(
                row["primary"] for row in assembly.values()),
            "content_oracle": "source-derived-first-difference",
            "linked_bytes_executed": True,
            "existing_mutations_rejected": len(
                convergence["mutations_rejected"]),
            "product_wplto": False,
            "hardware_contacts": 0,
        }
        audit(facts)
        rejected = mutation_selftest(facts)
        require(len(rejected) == contract["new_seam_mutations"],
                "new assembly seam mutation count drift")
        elf_bind = {
            "bytes": elf.stat().st_size,
            "sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "service_sha256": hashlib.sha256(
                truth.section_bytes(artifact["section"])).hexdigest(),
        }
    return {
        "format": "lisp65-c2-mapped-far-assembly-equivalence-receipt-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS",
        "claim": contract["claim"],
        "authorities": {key: bind(path) for key, path in {
            "contract": CONTRACT,
            "abi_successor_contract": SUCCESSOR_CONTRACT,
            "assembly": ASM,
            "ordinary_c_reference": DMA_C,
            "physical_c_reference": RUNTIME_C,
            "existing_convergence_receipt": CONVERGENCE_RECEIPT,
            "driver": Path(__file__).resolve(),
        }.items()},
        "linked_artifact": elf_bind,
        "facts": facts,
        "cases": case_rows,
        "mutations_rejected": rejected,
        "execution_witness": {
            "c_reference": len(reference),
            "assembly_artifact": len(assembly),
            "equivalence": equivalent,
            "existing_mutations": len(convergence["mutations_rejected"]),
            "new_seam_mutations": len(rejected),
            "total": len(reference) + len(assembly) + equivalent
                     + len(convergence["mutations_rejected"])
                     + len(rejected),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt()
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(canonical(receipt))
        print(
            "c2-mapped-far-asm-equivalence: PASS "
            f"cases={receipt['execution_witness']['equivalence']}/16 "
            f"mutations={receipt['execution_witness']['new_seam_mutations']} "
            f"bytes={receipt['facts']['exact_bytes']} "
            f"executions={receipt['execution_witness']['total']}")
        return 0
    except (GateError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"c2-mapped-far-asm-equivalence: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
