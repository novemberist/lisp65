#!/usr/bin/env python3
"""Price whole-span verification after the Link-111 partial-transfer proof."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CAPTURE = ARCH / "c2.3-v2.1-link111-d2-partial-span-capture-receipt.json"
GRANULARITY = ARCH / "c2.3-v2.0-convergence-granularity-review-receipt.json"
ORACLE = ROOT / "config/c2-v20-source-authoritative-oracle-contract.json"
CPU_CONTRACT = ROOT / "config/c2-v21-cpu-transport-release-contract.json"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
ASM = ROOT / "src/c2_mapped_far_convergence.s"
DMA = ROOT / "src/c2_platform_dma.c"
MEM = ROOT / "src/mem.c"
ASM_GATE = ROOT / "tools/host-lisp/c2_mapped_far_asm_equivalence.py"
CLASS_GATE = ROOT / "tools/host-lisp/c2_code_window_convergence_gate.py"
ELF = ROOT / (
    "build/c2.3/v2.1-terminal-screen-lease-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
RECEIPT = ARCH / "c2.3-v2.1-span-verification-pricing-receipt.json"
SOURCE_UNBIND = ARCH / (
    "c2.3-v2.1-span-pricing-source-unbind-20260816-receipt.json")

LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

COMMISSION = "179aaf1c"
FORMAT = "lisp65-c2.3-v2.1-span-verification-pricing-v1"
STATUS = "FULL-SPAN-COMPARE-SELECTED; FIX-AND-CARD-PENDING"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return {
        "authority": "git-blob", "commit": commit, "path": relative,
        "bytes": len(raw), "sha256": sha(raw),
    }


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def partial_fixtures() -> dict[str, Any]:
    source = bytes.fromhex("3b0601012f0153")
    stale = bytes.fromhex("0b000000000000")
    all_indices = tuple(range(len(source)))
    schedules = {
        "prefix-one-then-all": ((0,), all_indices),
        "prefix-three-then-all": ((0, 1, 2), all_indices),
        "tail-first-then-all": ((6,), all_indices),
        "middle-first-then-all": ((3, 4), all_indices),
        "odd-first-then-all": ((1, 3, 5), all_indices),
        "never-complete": ((0,), (0,)),
    }

    def run(schedule: tuple[tuple[int, ...], ...], mode: str) -> dict[str, Any]:
        destination = bytearray(stale)
        first = next(index for index, pair in enumerate(zip(source, destination))
                     if pair[0] != pair[1])
        accepted_at: int | None = None
        for step, indices in enumerate(schedule, 1):
            for index in indices:
                destination[index] = source[index]
            accepted = {
                "first-byte": destination[first] == source[first],
                "tail": destination[-1] == source[-1],
                "full-compare": bytes(destination) == source,
                "span-crc16": crc16(bytes(destination)) == crc16(source),
            }[mode]
            if accepted:
                accepted_at = step
                break
        return {
            "accepted": accepted_at is not None,
            "accepted_step": accepted_at,
            "destination_at_decision": bytes(destination).hex(),
            "full_span_equal_at_decision": bytes(destination) == source,
        }

    rows: dict[str, Any] = {}
    for name, schedule in schedules.items():
        rows[name] = {
            mode: run(schedule, mode)
            for mode in ("first-byte", "tail", "full-compare", "span-crc16")
        }
    require(
        rows["prefix-one-then-all"]["first-byte"]
            ["full_span_equal_at_decision"] is False
        and rows["tail-first-then-all"]["tail"]
            ["full_span_equal_at_decision"] is False,
        "partial fixtures no longer expose discriminator/sentinel holes",
    )
    for name, row in rows.items():
        if name == "never-complete":
            require(not row["full-compare"]["accepted"]
                    and not row["span-crc16"]["accepted"],
                    "complete-span verifier accepted a torn timeout")
        else:
            require(row["full-compare"]["accepted"]
                    and row["full-compare"]["full_span_equal_at_decision"]
                    and row["span-crc16"]["accepted"]
                    and row["span-crc16"]["full_span_equal_at_decision"],
                    f"complete-span verifier rejected completed fixture: {name}")
    return {
        "source_hex": source.hex(),
        "stale_hex": stale.hex(),
        "fixture_rule": (
            "every transfer fixture exposes genuine prefix, suffix, middle, "
            "out-of-order and never-complete partial visibility; atomic-only "
            "primary copies are forbidden"
        ),
        "cases": rows,
        "current_first_byte_false_accepts": 2,
        "tail_sentinel_false_accepts": 1,
        "full_compare_false_accepts": 0,
        "span_crc16_false_accepts": 0,
    }


def full_span_variant(source: str) -> str:
    ordinary_primary = """\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d700_primary_not_yet
\tlda #1
\trts
.Lc2_d700_primary_not_yet:"""
    ordinary_redirect = """\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d700_primary_not_yet
\tlda #0
\tsta __rc15
\tsta __rc16
\tjmp .Lc2_d700_post_scan
.Lc2_d700_primary_not_yet:"""
    require(source.count(ordinary_primary) == 1,
            "ordinary first-byte edge drift")
    source = source.replace(ordinary_primary, ordinary_redirect)

    ordinary_anchor = """\tlda #0
\trts

\t.globl c2_mapped_far_vm_code_load_converged"""
    ordinary_post = """\tlda #0
\trts

.Lc2_d700_post_scan:
\tjsr .Lc2_d700_source_byte
\tbeq .Lc2_d700_failure
\tclc
\tlda __rc13
\tadc __rc15
\tsta __rc20
\tlda __rc14
\tadc __rc16
\tsta __rc21
\tldy #0
\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d700_post_not_yet
\tinc __rc15
\tbne .Lc2_d700_post_compare
\tinc __rc16
.Lc2_d700_post_compare:
\tlda __rc15
\tcmp __rc11
\tbne .Lc2_d700_post_scan
\tlda __rc16
\tcmp __rc12
\tbne .Lc2_d700_post_scan
\tlda #1
\trts
.Lc2_d700_post_not_yet:
\tjsr .Lc2_far_timed_out
\tbne .Lc2_d700_failure
\tlda #0
\tsta __rc15
\tsta __rc16
\tjmp .Lc2_d700_post_scan

\t.globl c2_mapped_far_vm_code_load_converged"""
    require(source.count(ordinary_anchor) == 1,
            "ordinary post-scan insertion seam drift")
    source = source.replace(ordinary_anchor, ordinary_post)

    physical_primary = """\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d705_primary_not_yet
\tlda #1
\trts
.Lc2_d705_primary_not_yet:"""
    physical_redirect = """\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d705_primary_not_yet
\tlda #0
\tsta __rc16
\tsta __rc17
\tjmp .Lc2_d705_post_scan
.Lc2_d705_primary_not_yet:"""
    require(source.count(physical_primary) == 1,
            "physical first-byte edge drift")
    source = source.replace(physical_primary, physical_redirect)

    physical_anchor = """\tlda #0
\trts

\t.globl c2_mapped_far_physical_read_converged"""
    physical_post = """\tlda #0
\trts

.Lc2_d705_post_scan:
\tjsr .Lc2_d705_source_byte
\tbeq .Lc2_d705_failure
\tclc
\tlda __rc12
\tadc __rc16
\tsta __rc20
\tlda __rc13
\tadc __rc17
\tsta __rc21
\tldy #0
\tlda (__rc20),y
\tcmp __rc27
\tbne .Lc2_d705_post_not_yet
\tinc __rc16
\tbne .Lc2_d705_post_compare
\tinc __rc17
.Lc2_d705_post_compare:
\tlda __rc16
\tcmp __rc14
\tbne .Lc2_d705_post_scan
\tlda __rc17
\tcmp __rc15
\tbne .Lc2_d705_post_scan
\tlda #1
\trts
.Lc2_d705_post_not_yet:
\tjsr .Lc2_far_timed_out
\tbne .Lc2_d705_failure
\tlda #0
\tsta __rc16
\tsta __rc17
\tjmp .Lc2_d705_post_scan

\t.globl c2_mapped_far_physical_read_converged"""
    require(source.count(physical_anchor) == 1,
            "physical post-scan insertion seam drift")
    return source.replace(physical_anchor, physical_post)


def section_size(path: Path) -> int:
    result = subprocess.run(
        [str(LLVM_READOBJ), "--sections", str(path)], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout
    at = result.index("Name: .lisp65_c2_mapped_far_service")
    block = result[at:result.index("  }", at)]
    for line in block.splitlines():
        if line.strip().startswith("Size:"):
            return int(line.split(":", 1)[1].strip(), 0)
    raise PricingError("mapped-far section size absent")


def target_price() -> dict[str, Any]:
    source = ASM.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="lisp65-span-price-") as name:
        directory = Path(name)
        current_s = directory / "current.s"
        variant_s = directory / "full-span.s"
        current_o = directory / "current.o"
        variant_o = directory / "full-span.o"
        current_s.write_text(source, encoding="utf-8")
        variant_s.write_text(full_span_variant(source), encoding="utf-8")
        for input_path, output_path in ((current_s, current_o),
                                        (variant_s, variant_o)):
            subprocess.run(
                [str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
                 "-filetype=obj", "-o", str(output_path), str(input_path)],
                cwd=ROOT, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        current = section_size(current_o)
        variant = section_size(variant_o)
    contract = load(ABI_CONTRACT)["artifact_successor"]
    capacity = contract["capacity_bytes"]
    require(current == contract["exact_bytes"] == 1086
            and capacity == 1499 and variant == 1224,
            "target-shaped pricing identity drift")
    return {
        "method": (
            "assemble the current service and a target-shaped two-lane "
            "post-primary full-rescan prototype with llvm-mc"
        ),
        "current_service_bytes": current,
        "full_span_prototype_bytes": variant,
        "delta_bytes": variant - current,
        "arena_capacity_bytes": capacity,
        "headroom_after_prototype_bytes": capacity - variant,
        "ordinary_lane_delta_bytes": 69,
        "physical_lane_delta_bytes": 69,
        "new_product_link": False,
    }


def linked_inventory() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=LLVM_READOBJ, include_section_data=False)
    symbols = {symbol.name for symbol in truth.symbols}
    surfaces = {
        "mutable-Bank4": {
            "functions": [
                "str_read_byte", "ext_a", "ext_b", "ext_type",
                "ext_disk_get",
            ],
            "span_bytes": [1, 2, 2, 1, 1],
            "delivery_bound_crc": False,
        },
        "mutable-Bank5": {
            "functions": [
                "nameoff_get", "sympool_read", "sym_value", "sym_function",
            ],
            "span_bytes": [2, "1..34", 2, 2],
            "delivery_bound_crc": False,
        },
    }
    require(all(name in symbols for row in surfaces.values()
                for name in row["functions"]),
            "one linked dynamic reader surface disappeared")
    disassembly = subprocess.run(
        [str(LLVM_OBJDUMP), "-d", "--symbolize-operands", str(ELF)],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True,
    ).stdout
    ext_edges = sum(
        "<ext_dma_read_or_abort>" in line
        and ("jsr" in line or "jmp" in line)
        for line in disassembly.splitlines())
    symbol_edges = sum(
        "<c2_dma_read_or_abort>" in line
        and ("jsr" in line or "jmp" in line)
        for line in disassembly.splitlines())
    physical_edges = sum(
        "<c2_physical_read_converged>" in line
        and ("jsr" in line or "jmp" in line)
        for line in disassembly.splitlines())
    require((ext_edges, symbol_edges, physical_edges) == (5, 4, 0),
            "Link-111 remaining convergence-edge inventory drift")
    cpu = load(CPU_CONTRACT)
    require("LISP65_C2_MAP_CPU_TRANSPORT" in cpu["build"]["activation_defines"],
            "Link-111 CPU transport contract drift")
    return {
        "CPU_rerouted_library_reads": 346298,
        "CPU_rerouted_reads_pay_span_verification": False,
        "remaining_active_DMA_surfaces": 9,
        "remaining_wrapper_edges": {
            "Bank4_EXT": ext_edges, "Bank5_symbol": symbol_edges,
            "physical_D705": physical_edges,
        },
        "surfaces": surfaces,
        "maximum_active_span_bytes": 34,
    }


def pricing() -> dict[str, Any]:
    oracle = load(ORACLE)
    granularity = load(GRANULARITY)
    require(
        oracle["scope"] == (
            "the three immutable phase-02a boot reads only; mutable runtime "
            "readers retain their dynamic convergence contract"),
        "delivery-oracle scope drift",
    )
    require(granularity["source_identity_domains"]["c2d"]
            ["becomes_mutable_during_decode"] is True,
            "mutable-source precedent drift")
    per_span = {
        "1": {"post_primary_source_probe_DMA_jobs": 2,
              "destination_compares": 1},
        "2": {"post_primary_source_probe_DMA_jobs": 4,
              "destination_compares": 2},
        "34": {"post_primary_source_probe_DMA_jobs": 68,
               "destination_compares": 34},
    }
    return {
        "tail_sentinel": {
            "verdict": "rejected",
            "reason": (
                "no transfer-order guarantee exists; tail-first visibility "
                "is a concrete false-success fixture"
            ),
        },
        "delivery_bound_span_crc16": {
            "existing_leaf_bytes": 74,
            "existing_oracle_rows": 12,
            "eligible_current_active_DMA_surfaces": 0,
            "verdict": "safe-but-not-applicable-to-Link-111-D2",
            "reason": (
                "the existing CRC authority covers only three immutable "
                "phase-02a record reads, all now served by CPU transport"
            ),
        },
        "live_source_span_crc16": {
            "post_primary_source_probe_DMA_jobs": "2*N",
            "CPU_passes": 2,
            "persistent_oracle_state_if_cached": (
                "new per-write epoch/CRC ownership required"
            ),
            "verdict": "dominated-for-mutable-runtime-spans",
            "reason": (
                "without delivery truth it must safely reread every source "
                "byte, then CRC both source and destination; full compare "
                "uses the same probes and fewer CPU operations"
            ),
        },
        "post_primary_full_span_compare": {
            "post_primary_source_probe_DMA_jobs": "2*N",
            "CPU_passes": 1,
            "per_span_examples": per_span,
            "already_equal_span_delta": 0,
            "verdict": "selected-for-all-remaining-mutable-DMA-spans",
        },
        "winner": "post-primary-full-span-compare",
    }


def derive() -> dict[str, Any]:
    capture = load(CAPTURE)
    require(capture.get("status") ==
            "PARTIAL-SPAN-F018B-TARGET-MEMBERSHIP-PROVEN",
            "target-membership authority drift")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": STATUS,
        "fixtures": partial_fixtures(),
        "linked_inventory": linked_inventory(),
        "pricing": pricing(),
        "target_code_price": target_price(),
        "decision": {
            "winner": "post-primary-full-span-compare",
            "why": (
                "all nine active Link-111 DMA surfaces are mutable runtime "
                "spans without delivery-bound CRC truth; a live source CRC "
                "pays the same safe source probes plus more CPU work"
            ),
            "fixture_gate_required_before_fix_card": True,
            "fix_authorized": False,
            "card_authorized": False,
            "device_contact_authorized": False,
            "D3_D5_open": False,
            "next": (
                "owner authorization for the full-span fix, genuine partial-transfer gate conversion, and one product card"
            ),
        },
        "claim_limit": (
            "Desk-only pricing. The target-shaped object is a size probe, not "
            "a product artifact. No source fix, WPLTO, link, card, media, "
            "device access, resume or D3-D5 continuation is authorized."
        ),
        "authority": {
            "commission": git_bind(COMMISSION, PLAN),
            "capture": bind(CAPTURE),
            "granularity": bind(GRANULARITY),
            "delivery_oracle": bind(ORACLE),
            "CPU_transport_contract": bind(CPU_CONTRACT),
            "ABI_capacity_contract": bind(ABI_CONTRACT),
            "assembly": bind(ASM),
            "DMA_source": bind(DMA),
            "EXT_source": bind(MEM),
            "assembly_gate": bind(ASM_GATE),
            "class_gate": bind(CLASS_GATE),
            "ELF": bind(ELF),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "micro_assemblies": 2,
            "WPLTO": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "device_contacts": 0,
            "device_resumes": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "pricing identity drift")
    fixtures = value["fixtures"]
    require(fixtures["current_first_byte_false_accepts"] == 2
            and fixtures["tail_sentinel_false_accepts"] == 1
            and fixtures["full_compare_false_accepts"] == 0
            and fixtures["span_crc16_false_accepts"] == 0,
            "partial-transfer fixture conclusion drift")
    inventory = value["linked_inventory"]
    require(inventory["CPU_rerouted_library_reads"] == 346298
            and inventory["CPU_rerouted_reads_pay_span_verification"] is False
            and inventory["remaining_active_DMA_surfaces"] == 9
            and inventory["remaining_wrapper_edges"] == {
                "Bank4_EXT": 5, "Bank5_symbol": 4, "physical_D705": 0},
            "Link-111 path inventory drift")
    prices = value["pricing"]
    require(prices["winner"] == "post-primary-full-span-compare"
            and prices["tail_sentinel"]["verdict"] == "rejected"
            and prices["delivery_bound_span_crc16"]
                ["eligible_current_active_DMA_surfaces"] == 0
            and prices["live_source_span_crc16"]["CPU_passes"] == 2
            and prices["post_primary_full_span_compare"]["CPU_passes"] == 1,
            "candidate price/selection drift")
    target = value["target_code_price"]
    require(target["current_service_bytes"] == 1086
            and target["full_span_prototype_bytes"] == 1224
            and target["delta_bytes"] == 138
            and target["arena_capacity_bytes"] == 1499
            and target["headroom_after_prototype_bytes"] == 275
            and target["new_product_link"] is False,
            "target-shaped code price drift")
    decision = value["decision"]
    require(decision["winner"] == "post-primary-full-span-compare"
            and decision["fixture_gate_required_before_fix_card"] is True
            and decision["fix_authorized"] is False
            and decision["card_authorized"] is False
            and decision["device_contact_authorized"] is False
            and decision["D3_D5_open"] is False,
            "pricing claim boundary drift")
    require(value["execution_accounting"] == {
        "micro_assemblies": 2, "WPLTO": 0, "product_links": 0,
        "product_bytes_changed": 0, "device_contacts": 0,
        "device_resumes": 0,
    }, "execution accounting drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-first-byte-hole": lambda x: x["fixtures"].__setitem__(
            "current_first_byte_false_accepts", 0),
        "admit-tail": lambda x: x["fixtures"].__setitem__(
            "tail_sentinel_false_accepts", 0),
        "break-full-compare": lambda x: x["fixtures"].__setitem__(
            "full_compare_false_accepts", 1),
        "break-span-crc": lambda x: x["fixtures"].__setitem__(
            "span_crc16_false_accepts", 1),
        "charge-CPU-boot": lambda x: x["linked_inventory"].__setitem__(
            "CPU_rerouted_reads_pay_span_verification", True),
        "lose-dynamic-surface": lambda x: x["linked_inventory"].__setitem__(
            "remaining_active_DMA_surfaces", 8),
        "invent-D705-edge": lambda x: x["linked_inventory"]
            ["remaining_wrapper_edges"].__setitem__("physical_D705", 1),
        "invent-delivery-CRC": lambda x: x["pricing"]
            ["delivery_bound_span_crc16"].__setitem__(
                "eligible_current_active_DMA_surfaces", 1),
        "make-live-CRC-cheaper": lambda x: x["pricing"]
            ["live_source_span_crc16"].__setitem__("CPU_passes", 1),
        "select-CRC": lambda x: x["pricing"].__setitem__(
            "winner", "delivery-bound-span-crc16"),
        "lose-byte-price": lambda x: x["target_code_price"].__setitem__(
            "delta_bytes", 137),
        "overflow-arena": lambda x: x["target_code_price"].__setitem__(
            "headroom_after_prototype_bytes", -1),
        "silently-authorize-fix": lambda x: x["decision"].__setitem__(
            "fix_authorized", True),
        "open-D3": lambda x: x["decision"].__setitem__("D3_D5_open", True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "pricing mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        value["mutations_rejected"] = mutations(value)
        RECEIPT.write_bytes(canonical(value))
    else:
        # This receipt priced the Link-111 world.  It remains immutable
        # historical evidence and must not be re-derived against the living
        # MAP-CPU successor sources.  The loud successor receipt proves the
        # source-world split and names the current acceptance authority.
        stored = load(RECEIPT)
        rejected = stored.pop("mutations_rejected", None)
        validate(stored)
        require(rejected == mutations(stored),
                "historical pricing mutation set drift")
        successor = load(SOURCE_UNBIND)
        require(
            successor.get("status") ==
                "PASS: HISTORICAL-SPAN-PRICING-DETACHED-FROM-LIVE-SOURCES"
            and successor.get("historical", {}).get(
                "receipt_sha256") == sha(RECEIPT.read_bytes())
            and successor.get("living", {}).get(
                "historical_sources_are_live_predicates") is False,
            "span-pricing source-unbind successor drift")
        value = stored
    print(
        "Link-111 span verification pricing: PASS "
        f"action={action} winner=full-span delta=138 headroom=275 "
        f"mutations={len(rejected if action != 'record' else value['mutations_rejected'])}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Link-111 span verification pricing: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
