#!/usr/bin/env python3
"""Prove the full-span successor against genuine partial target transfers."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from cpu6502 import CPU  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import c2_mapped_far_asm_equivalence as EQ  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_full_span_product_config as CONFIG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CONTRACT = ROOT / "config/c2-mapped-far-full-span-contract-v3.json"
PREDECESSOR = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
PRICING = ARCH / "c2.3-v2.1-span-verification-pricing-receipt.json"
CAPTURE = ARCH / "c2.3-v2.1-link111-d2-partial-span-capture-receipt.json"
ASM = ROOT / "src/optional/c2_mapped_far_convergence_full_span.s"
DMA = ROOT / "src/c2_platform_dma.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RECEIPT = ARCH / "c2.3-v2.1-full-span-convergence-receipt.json"
SOURCE_UNBIND = ARCH / (
    "c2.3-v2.1-span-pricing-source-unbind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
CONFIG_DRIVER = ROOT / "tools/host-lisp/c2_v21_full_span_product_config.py"
AUTHORIZATION = "afe63882"
FORMAT = "lisp65-c2.3-v2.1-full-span-convergence-v1"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


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
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    for token in ("full-span fix on all nine readers",
                  "first-byte-success shape as its named mutation",
                  "transfer-fixture conversion", "one product card"):
        require(token in raw, f"full-span authorization absent: {token}")
    return value


def contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    predecessor = load(PREDECESSOR)
    successor = load(CONTRACT)
    pricing = load(PRICING)
    row = successor["predecessors"]["ABI_preservation_contract"]
    price_row = successor["predecessors"]["pricing_receipt"]
    require(
        successor.get("status") == "owner-authorized-afe63882"
        and row == {"path": PREDECESSOR.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(
                        PREDECESSOR.read_bytes()).hexdigest()}
        and price_row == {"path": PRICING.relative_to(ROOT).as_posix(),
                          "sha256": hashlib.sha256(
                              PRICING.read_bytes()).hexdigest()}
        and pricing.get("status")
            == "FULL-SPAN-COMPARE-SELECTED; FIX-AND-CARD-PENDING",
        "full-span contract ancestry drift")
    artifact = successor["artifact_successor"]
    require(
        artifact == {
            "source": "src/optional/c2_mapped_far_convergence_full_span.s",
            "section": ".lisp65_c2_mapped_far_service",
            "cpu_vma": "0x78b2", "physical_lma": "0x0002b8b2",
            "exact_bytes": 1248, "prototype_bytes": 1224,
            "relocation_bytes": 4644, "relocation_records": 387,
            "deadline_and_branch_safety_bytes": 24,
            "predecessor_bytes": 1086, "delta_bytes": 162,
            "capacity_bytes": 1499, "headroom_bytes": 251,
            "cpu_end_exclusive": "0x7d92",
            "physical_end_exclusive": "0x0002bd92",
            "post_service_static_bytes": 48530,
            "post_service_headroom_bytes": 17006,
            "entries": ["c2_mapped_far_vm_code_load_converged",
                        "c2_mapped_far_physical_read_converged"]},
        "full-span artifact identity drift")
    projected, _ = EQ.effective_contract()
    projected["artifact"].update({
        key: artifact[key] for key in (
            "source", "section", "cpu_vma", "physical_lma",
            "exact_bytes", "capacity_bytes", "entries")})
    return projected, predecessor, successor


CASES: tuple[dict[str, Any], ...] = (
    {"name": "clean-equal", "equal": True, "thresholds": (),
     "accepted": True},
    {"name": "prefix-one-then-all", "thresholds": (1, 3, 3, 3, 3, 3, 3),
     "accepted": True},
    {"name": "prefix-three-then-all", "thresholds": (1, 1, 1, 3, 3, 3, 3),
     "accepted": True},
    {"name": "tail-first-then-all", "thresholds": (3, 3, 3, 3, 3, 3, 1),
     "accepted": True},
    {"name": "middle-first-then-all", "thresholds": (3, 3, 1, 1, 3, 3, 3),
     "accepted": True},
    {"name": "odd-first-then-all", "thresholds": (3, 1, 3, 1, 3, 1, 3),
     "accepted": True},
    {"name": "first-only-never", "thresholds": (1, None, None, None,
                                                    None, None, None),
     "accepted": False},
    {"name": "first-tail-never", "thresholds": (1, None, None, None,
                                                   None, None, 2),
     "accepted": False},
    {"name": "one-byte", "thresholds": (2,), "accepted": True},
)


def full_span_reference(function: str, *, physical: bool) -> str:
    """Derive the opt-in C oracle without moving historical product sources."""
    suffix = "    return 1u;\n}"
    require(function.endswith(suffix), "predecessor convergence tail drift")
    probe = (
        "c2_physical_source_byte(source + i, &expected)"
        if physical else
        "c2_dma_source_byte(bank, (uint16_t)(offset + i), &expected)")
    replacement = f"""    for (;;) {{
        for (i = 0u; i < length; ++i) {{
            if (!{probe}) return 0u;
            if (observed[i] != expected) break;
        }}
        if (i == length) return 1u;
        if ((uint16_t)(c2_kernal_frame_count_inline() - start)
            >= C2_DMA_CONTENT_TIMEOUT_FRAMES)
            return 0u;
    }}
}}"""
    return function[:-len(suffix)] + replacement


def reference_harness() -> str:
    ordinary = full_span_reference(EQ.extract_function(
        DMA.read_text(encoding="utf-8"),
        "uint8_t C2_VM_CODE_LOAD_CONVERGED_IMPL("), physical=False)
    physical = full_span_reference(EQ.extract_function(
        RUNTIME.read_text(encoding="utf-8"),
        "uint8_t C2_PHYSICAL_READ_CONVERGED_IMPL("), physical=True)
    rows = []
    for case in CASES:
        thresholds = list(case["thresholds"])
        thresholds += [-1] * (7 - len(thresholds))
        rows.append(
            '  {"%s", {%s}, %d, %d},' % (
                case["name"], ",".join(
                    str(-1 if value is None else value)
                    for value in thresholds),
                len(case["thresholds"]), 1 if case.get("equal") else 0))
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LISP65_C2_MAPPED_FAR_FN
#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u
#define C2_VM_CODE_LOAD_CONVERGED_IMPL ref_ordinary
#define C2_PHYSICAL_READ_CONVERGED_IMPL ref_physical

static uint8_t reference_source[8];
static uint8_t *active_destination;
static uint16_t active_length;
static uint16_t ordinary_base;
static uint32_t physical_base;
static int thresholds[8];
static unsigned elapsed;
static int primary_submissions;

static void apply_partial(void) {
  unsigned i;
  for (i = 0; i < active_length; ++i)
    if (thresholds[i] >= 0 && elapsed >= (unsigned)thresholds[i])
      active_destination[i] = reference_source[i];
}
static uint16_t c2_kernal_frame_count_inline(void) {
  if (primary_submissions) { ++elapsed; apply_partial(); }
  return (uint16_t)elapsed;
}
static uint8_t c2_dma_source_byte(
    uint8_t bank, uint16_t offset, uint8_t *value) {
  (void)bank; (void)c2_kernal_frame_count_inline();
  if (offset < ordinary_base
      || (uint16_t)(offset - ordinary_base) >= active_length) return 0;
  *value = reference_source[(uint16_t)(offset - ordinary_base)];
  return 1;
}
static void vm_code_load(uint8_t bank, uint16_t offset, uint16_t length,
                         uint8_t *destination) {
  (void)bank; (void)offset; (void)length; (void)destination;
  ++primary_submissions; apply_partial();
}
static uint8_t c2_physical_source_byte(uint32_t source, uint8_t *value) {
  (void)c2_kernal_frame_count_inline();
  if (source < physical_base || source - physical_base >= active_length)
    return 0;
  *value = reference_source[source - physical_base];
  return 1;
}
static void c2_product_physical_copy(
    uint32_t source, uint32_t target, uint16_t length) {
  (void)source; (void)target; (void)length;
  ++primary_submissions; apply_partial();
}
''' + ordinary + "\n\n" + physical + r'''

struct row { const char *name; int threshold[7]; unsigned length; int equal; };
static const struct row rows[] = {
''' + "\n".join(rows) + r'''
};

int main(void) {
  static const uint8_t source[7] = {0x3b,0x06,0x01,0x01,0x2f,0x01,0x53};
  static const uint8_t stale[7] = {0x0b,0x00,0x00,0x00,0x00,0x00,0x00};
  unsigned lane, c, i;
  for (lane = 0; lane < 2; ++lane) for (c = 0; c < sizeof(rows)/sizeof(rows[0]); ++c) {
    uint8_t destination[7];
    const struct row *row = &rows[c];
    active_length = row->length ? row->length : 7;
    memcpy(reference_source, source, active_length);
    memcpy(destination, row->equal ? source : stale, active_length);
    active_destination = destination; ordinary_base = 0x1200;
    physical_base = 0x234560; elapsed = 0; primary_submissions = 0;
    for (i = 0; i < active_length; ++i) thresholds[i] = row->threshold[i];
    if (!lane) {
      uint8_t result = ref_ordinary(5, ordinary_base, active_length, destination);
      printf("ordinary|%s|%u|%d|", row->name, result, primary_submissions);
    } else {
      uint8_t result = ref_physical(physical_base, destination, active_length);
      printf("physical|%s|%u|%d|", row->name, result, primary_submissions);
    }
    for (i = 0; i < active_length; ++i) printf("%02x", destination[i]);
    putchar('\n');
  }
  return 0;
}
'''


def parse_reference(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for line in text.splitlines():
        lane, name, accepted, primary, destination = line.split("|")
        result[(lane, name)] = {"result": int(accepted),
                                "primary": int(primary),
                                "destination": destination}
    require(len(result) == 2 * len(CASES), "C partial fixture row loss")
    return result


class PartialCPU(EQ.DmaCPU):
    def __init__(self, *, thresholds: tuple[int | None, ...], **kwargs: Any):
        super().__init__(after=-1, **kwargs)
        self.thresholds = thresholds
        self.applied: set[int] = set()

    def _apply_pending(self) -> None:
        if self.pending is None:
            return
        for index, threshold in enumerate(self.thresholds):
            if threshold is not None and self.elapsed >= threshold:
                CPU.wr(self, self.pending["destination"] + index,
                       self.pending["data"][index])
                self.applied.add(index)
        if len(self.applied) == len(self.pending["data"]):
            self.pending = None


def run_target(truth: ElfTruth) -> dict[tuple[str, str], dict[str, Any]]:
    service = truth.section(".lisp65_c2_mapped_far_service")
    markers = truth.section(".lisp65_fixture_markers")
    symbols = {name: truth.symbol(name).value for name in (
        "c2_dma_list", "c2_dma_verify_list", "c2_dma_verify",
        "c2_dma_verify_marker", "c2_dma_verify_done", "c2_edma_job",
        "c2_edma_probe_jobs", "c2_edma_probe_value",
        "c2_edma_probe_marker", "c2_edma_probe_done")}
    rc = {index: truth.symbol(f"__rc{index}").value
          for index in range(2, 32)}
    entries = {
        "ordinary": truth.symbol(
            "c2_mapped_far_vm_code_load_converged").value,
        "physical": truth.symbol(
            "c2_mapped_far_physical_read_converged").value}
    source_full = bytes.fromhex("3b0601012f0153")
    stale_full = bytes.fromhex("0b000000000000")
    code = truth.section_bytes(service.name)
    marker_bytes = truth.section_bytes(markers.name)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for lane in ("ordinary", "physical"):
        for case_index, case in enumerate(CASES):
            length = len(case["thresholds"]) or 7
            source = source_full[:length]
            destination = source if case.get("equal") else stale_full[:length]
            source_base = 0x1200 if lane == "ordinary" else 0x234560
            thresholds = tuple(case["thresholds"])
            cpu = PartialCPU(symbols=symbols, source=source, lane=lane,
                             thresholds=thresholds, start=0,
                             source_base=source_base)
            saved = {index: (0x31 + case_index * 7
                              + (0x40 if lane == "physical" else 0)
                              + index * 11) & 0xff
                     for index in range(16, 32)}
            for index, value in saved.items():
                CPU.wr(cpu, rc[index], value)
            initial_sp = cpu.SP
            for offset, value in enumerate(code):
                CPU.wr(cpu, service.address + offset, value)
            for offset, value in enumerate(marker_bytes):
                CPU.wr(cpu, markers.address + offset, value)
            destination_address = 0x4000
            for offset, value in enumerate(destination):
                CPU.wr(cpu, destination_address + offset, value)
            if lane == "ordinary":
                cpu.A = 5; cpu.X = source_base & 0xff
                CPU.wr(cpu, rc[2], source_base >> 8)
                CPU.wr(cpu, rc[3], length); CPU.wr(cpu, rc[4], 0)
                CPU.wr(cpu, rc[6], destination_address & 0xff)
                CPU.wr(cpu, rc[7], destination_address >> 8)
            else:
                cpu.A = source_base & 0xff; cpu.X = (source_base >> 8) & 0xff
                CPU.wr(cpu, rc[2], (source_base >> 16) & 0xff)
                CPU.wr(cpu, rc[3], (source_base >> 24) & 0xff)
                CPU.wr(cpu, rc[4], destination_address & 0xff)
                CPU.wr(cpu, rc[5], destination_address >> 8)
                CPU.wr(cpu, rc[6], length); CPU.wr(cpu, rc[7], 0)
            try:
                cpu.call(entries[lane], max_steps=1_500_000)
            except RuntimeError as error:
                raise GateError(
                    f"target fixture {lane}/{case['name']}: {error}; "
                    f"pc=0x{cpu.PC:04x} elapsed={cpu.elapsed} "
                    f"primary={cpu.primary_submissions} "
                    f"probes={cpu.probe_submissions} "
                    f"start={CPU.rd(cpu, rc[5]):02x}"
                    f"{CPU.rd(cpu, rc[4]):02x} "
                    f"active-start={CPU.rd(cpu, rc[29]):02x}"
                    f"{CPU.rd(cpu, rc[28]):02x} "
                    f"frame={cpu.elapsed & 0xffff:04x}") from error
            final = bytes(CPU.rd(cpu, destination_address + offset)
                          for offset in range(length))
            preserved = sum(CPU.rd(cpu, rc[index]) == value
                            for index, value in saved.items())
            require(preserved == 16 and cpu.SP == initial_sp,
                    f"full-span ABI/stack drift: {lane}/{case['name']}")
            result[(lane, case["name"])] = {
                "result": cpu.A, "primary": cpu.primary_submissions,
                "destination": final.hex(),
                "source_probes": cpu.probe_submissions,
                "elapsed_frames": cpu.elapsed,
                "callee_saved_preserved": preserved,
                "hardware_stack_balanced": True}
    return result


def build_execution() -> dict[str, Any]:
    projected, _predecessor, successor = contract()
    old_asm = EQ.ASM
    try:
        EQ.ASM = ASM
        with tempfile.TemporaryDirectory(prefix="lisp65-full-span-") as name:
            temp = Path(name)
            harness = temp / "reference.c"
            executable = temp / "reference"
            harness.write_text(reference_harness(), encoding="utf-8")
            EQ.run(["cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
                    str(harness), "-o", str(executable)],
                   "compile full-span C reference")
            reference = parse_reference(EQ.run(
                [str(executable)], "execute full-span C reference").stdout)
            _elf, truth = EQ.build_artifact(projected, temp)
            target = run_target(truth)
            section = truth.section(".lisp65_c2_mapped_far_service")
            relocation = truth.section(
                ".rela.lisp65_c2_mapped_far_service")
    finally:
        EQ.ASM = old_asm
    rows: dict[str, Any] = {}
    equivalent = 0
    false_accepts = 0
    for key, expected in reference.items():
        observed = target[key]
        comparable = {field: observed[field]
                      for field in ("result", "primary", "destination")}
        require(comparable == expected,
                f"C/target partial divergence {key}: {comparable} != {expected}")
        case = next(row for row in CASES if row["name"] == key[1])
        require(observed["result"] == (1 if case["accepted"] else 0),
                f"partial-transfer result drift: {key}")
        if observed["result"] and observed["destination"] \
                != bytes.fromhex("3b0601012f0153")[:
                    len(bytes.fromhex(observed["destination"]))].hex():
            false_accepts += 1
        equivalent += 1
        rows["/".join(key)] = observed
    artifact = successor["artifact_successor"]
    require(section.bytes == artifact["exact_bytes"] == 1248,
            "linked full-span size drift")
    return {"cases_per_lane": len(CASES), "lanes": 2,
            "target_cases": len(target), "C_reference_cases": len(reference),
            "equivalent_cases": equivalent, "false_accepts": false_accepts,
            "callee_saved_checks": sum(
                row["callee_saved_preserved"] for row in target.values()),
            "hardware_stack_balanced_cases": sum(
                row["hardware_stack_balanced"] for row in target.values()),
            "primary_submissions_max": max(
                row["primary"] for row in target.values()),
            "linked_service_bytes": section.bytes,
            "linked_relocation_bytes": relocation.bytes,
            "linked_relocation_records": relocation.bytes // 12,
            "headroom_bytes": artifact["capacity_bytes"] - section.bytes,
            "rows": rows}


def source_scope() -> dict[str, Any]:
    old_defines = PRODUCT.CONVERGENCE_DEFINES
    old_sources = PRODUCT.CONVERGENCE_SOURCES
    configured = CONFIG.configure(PRODUCT)
    require(
        old_defines == ("LISP65_CODE_WINDOW_CONVERGENCE",
                        "LISP65_DMA_CONTENT_CONVERGENCE",
                        "LISP65_C2_ASM_CONVERGENCE")
        and old_sources[-1].name == "c2_mapped_far_convergence.s"
        and PRODUCT.CONVERGENCE_DEFINES[-1]
            == "LISP65_C2_FULL_SPAN_CONVERGENCE"
        and PRODUCT.CONVERGENCE_SOURCES[-1] == ASM,
        "full-span source-owner selection drift")
    selected = PRODUCT.source_list(PRODUCT.CONVERGENCE_DEFINES)
    require(str(ASM) in selected
            and str(ROOT / "src/c2_mapped_far_convergence.s") not in selected,
            "candidate did not consume exactly the successor assembly owner")
    require(configured["single_body_owner"] is True,
            "full-span product configuration lost its owner")
    return {"feature": "LISP65_C2_FULL_SPAN_CONVERGENCE",
            "predecessor_source": old_sources[-1].relative_to(ROOT).as_posix(),
            "candidate_source": ASM.relative_to(ROOT).as_posix(),
            "candidate_defines": list(PRODUCT.CONVERGENCE_DEFINES),
            "candidate_sources": [path.relative_to(ROOT).as_posix()
                                  for path in PRODUCT.CONVERGENCE_SOURCES],
            "single_assembly_owner": True}


def validate(value: dict[str, Any]) -> None:
    execution = value["linked_execution"]
    require(
        value.get("format") == FORMAT
        and value.get("status") == "HOST-GREEN: FULL-SPAN SUCCESSOR ARMED"
        and execution["cases_per_lane"] == 9
        and execution["target_cases"] == execution["C_reference_cases"]
            == execution["equivalent_cases"] == 18
        and execution["false_accepts"] == 0
        and execution["callee_saved_checks"] == 288
        and execution["hardware_stack_balanced_cases"] == 18
        and execution["primary_submissions_max"] == 1
        and execution["linked_service_bytes"] == 1248
        and execution["linked_relocation_bytes"] == 4644
        and execution["linked_relocation_records"] == 387
        and execution["headroom_bytes"] == 251,
        "full-span linked execution drift")
    rows = execution["rows"]
    for lane in ("ordinary", "physical"):
        require(rows[f"{lane}/first-only-never"]["result"] == 0
                and rows[f"{lane}/first-tail-never"]["result"] == 0
                and rows[f"{lane}/prefix-one-then-all"]["result"] == 1
                and rows[f"{lane}/tail-first-then-all"]["result"] == 1,
                f"genuine partial fixtures weakened: {lane}")
    require(value["source_scope"] == {
                "feature": "LISP65_C2_FULL_SPAN_CONVERGENCE",
                "predecessor_source": "src/c2_mapped_far_convergence.s",
                "candidate_source":
                    "src/optional/c2_mapped_far_convergence_full_span.s",
                "candidate_defines": [
                    "LISP65_CODE_WINDOW_CONVERGENCE",
                    "LISP65_DMA_CONTENT_CONVERGENCE",
                    "LISP65_C2_ASM_CONVERGENCE",
                    "LISP65_C2_FULL_SPAN_CONVERGENCE"],
                "candidate_sources": [
                    "src/c2_mapped_far_service.s",
                    "src/optional/c2_mapped_far_convergence_full_span.s"],
                "single_assembly_owner": True}
            and value["decision"] == {
                "fix_host_green": True, "card_authorized": True,
                "card_consumed": False, "device_contact": False,
                "D2_D5_open": False},
            "full-span scope/claim drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-first-byte-success": lambda x: x["linked_execution"]
            ["rows"]["ordinary/first-only-never"].update(result=1),
        "restore-first-tail-success": lambda x: x["linked_execution"]
            ["rows"]["physical/first-tail-never"].update(result=1),
        "atomic-only-fixtures": lambda x: x["linked_execution"].update(
            cases_per_lane=2),
        "lose-tail-first": lambda x: x["linked_execution"]["rows"].pop(
            "ordinary/tail-first-then-all"),
        "admit-false-success": lambda x: x["linked_execution"].update(
            false_accepts=1),
        "diverge-C-target": lambda x: x["linked_execution"].update(
            equivalent_cases=17),
        "resubmit-primary": lambda x: x["linked_execution"].update(
            primary_submissions_max=2),
        "clobber-callee-saved": lambda x: x["linked_execution"].update(
            callee_saved_checks=287),
        "unbalance-stack": lambda x: x["linked_execution"].update(
            hardware_stack_balanced_cases=17),
        "pin-prototype-size": lambda x: x["linked_execution"].update(
            linked_service_bytes=1224),
        "spend-arena": lambda x: x["linked_execution"].update(
            headroom_bytes=250),
        "pin-old-relocations": lambda x: x["linked_execution"].update(
            linked_relocation_records=331),
        "link-predecessor-owner": lambda x: x["source_scope"].update(
            candidate_source="src/c2_mapped_far_convergence.s"),
        "two-assembly-owners": lambda x: x["source_scope"].update(
            single_assembly_owner=False),
        "spend-card": lambda x: x["decision"].update(card_consumed=True),
        "open-D2": lambda x: x["decision"].update(D2_D5_open=True),
        "authorize-device": lambda x: x["decision"].update(
            device_contact=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except (GateError, KeyError):
            rejected.append(name)
    require(rejected == list(cases),
            f"full-span mutation survived: rejected={rejected} "
            f"expected={list(cases)}")
    return rejected


def derive() -> dict[str, Any]:
    capture = load(CAPTURE)
    require(capture.get("status")
            == "PARTIAL-SPAN-F018B-TARGET-MEMBERSHIP-PROVEN",
            "Link-111 capture authority drift")
    value = {"format": FORMAT, "recorded_on": "2026-08-16",
        "status": "HOST-GREEN: FULL-SPAN SUCCESSOR ARMED",
        "linked_execution": build_execution(), "source_scope": source_scope(),
        "decision": {"fix_host_green": True, "card_authorized": True,
            "card_consumed": False, "device_contact": False,
            "D2_D5_open": False},
        "authority": {"owner": authorization(), "contract": bind(CONTRACT),
            "predecessor_contract": bind(PREDECESSOR),
            "pricing": bind(PRICING), "capture": bind(CAPTURE),
            "assembly": bind(ASM), "DMA_source": bind(DMA),
            "runtime_source": bind(RUNTIME), "linker": bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
            "product_config": bind(CONFIG_DRIVER),
            "driver": bind(DRIVER)},
        "execution_accounting": {"micro_links": 1, "target_cases": 18,
            "C_reference_cases": 18, "WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0},
        "claim_limit": "Host/micro-ELF fix only; the one product card is not yet consumed and D2-D5 remain closed."}
    validate(value); value["mutations_rejected"] = mutations(value)
    return value


def record() -> None:
    value = derive(); RECEIPT.write_bytes(canonical(value))
    print("full-span convergence: PASS cases=18/18 false=0 bytes=1248 headroom=251 mutations=17")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    unbind = load(SOURCE_UNBIND)
    require(
        rejected == mutations(value)
        and unbind.get("status") ==
            "PASS: HISTORICAL-SPAN-PRICING-DETACHED-FROM-LIVE-SOURCES"
        and unbind.get("historical_full_span", {}).get(
            "receipt_sha256") == hashlib.sha256(
                RECEIPT.read_bytes()).hexdigest()
        and unbind.get("living", {}).get(
            "historical_sources_are_live_predicates") is False,
        "full-span historical source-unbind drift")
    print("full-span convergence: CHECK PASS cases=18/18 false=0 bytes=1248 headroom=251")


def selftest() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value) and len(rejected) == 17,
            "full-span mutation count drift")
    print("full-span convergence: SELFTEST PASS partial=9x2 mutations=17")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check,
     "selftest": selftest}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"full-span convergence: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
