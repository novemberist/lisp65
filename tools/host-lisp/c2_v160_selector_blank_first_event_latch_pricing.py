#!/usr/bin/env python3
"""Price the pre-wrap $8040 first-event latch without building a product."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-bypass-blank-table-heads-attribution.json")
CORE = ROOT / "build/upstream-verification/mega65-core"
MONITOR = CORE / "src/monitor/monitor.a65"
MONITOR_TOP = CORE / "src/verilog/monitor_top.v"
MONITOR_CTRL = CORE / "src/verilog/monitor_ctrl.v"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_ETH = CORE / "src/vhdl/ethernet.vhdl"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-blank-first-event-latch-pricing.json")
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORITY = "2b4aa029"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
ELF_SHA = "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4"
TARGET = 0x8040
TARGET_DECODE_PC = TARGET + 1
INSTRUCTION_FETCH = 0x12
INSTRUCTION_DECODE = 0x13
INSTRUCTION_DECODE_6502 = 0x14
FORMAT = "lisp65-c2.3-v1.6-selector-blank-first-event-latch-pricing-v1"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def authority() -> dict[str, Any]:
    row = git_binding(AUTHORITY, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{row['commit']}:{row['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    compact = " ".join(raw.lower().split())
    for token in ("pre-wrap control-edge witness pricing released",
                  "first-event latch, not a ring", "instrument neutrality",
                  "ordinary text 18, far service 11, map arena 47"):
        require(token in compact, f"pricing authority token absent: {token}")
    return row


def core_binding() -> dict[str, Any]:
    observed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=CORE, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    require(observed == CORE_COMMIT, "bound MEGA65 core commit drift")
    return {"repository": "MEGA65/mega65-core", "commit": observed,
            "sources": {path.name: bind(path) for path in
                        (MONITOR, MONITOR_TOP, MONITOR_CTRL, CORE_CPU, CORE_ETH)}}


def emitted_aperture_pair() -> dict[str, Any]:
    def assemble(immediate: int) -> bytes:
        source = f"""\
            .section .text.monitor_aperture_price,"ax",@progbits
            .globl aperture_price
        aperture_price:
            cmp #{immediate}
            bcs aperture_price
        """
        with tempfile.TemporaryDirectory(prefix="c2-v160-latch-price-") as raw:
            root = Path(raw)
            asm = root / "price.s"
            obj = root / "price.o"
            asm.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [str(CLANG), "-c", "-mcpu=mos45gs02", str(asm), "-o", str(obj)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False)
            require(result.returncode == 0,
                    f"monitor aperture micro-assembly red:\n{result.stdout}")
            truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                                  include_section_data=True)
            return truth.section_bytes(".text.monitor_aperture_price")

    old = assemble(3)
    new = assemble(4)
    differing = [index for index, pair in enumerate(zip(old, new))
                 if pair[0] != pair[1]]
    require(len(old) == len(new) and len(old) > 2 and differing == [1]
            and old[0:2] == b"\xc9\x03" and new[0:2] == b"\xc9\x04",
            f"emitted monitor aperture price drift: {old.hex()} {new.hex()} {differing}")
    return {"stock_hex": old.hex(" "), "successor_hex": new.hex(" "),
            "bytes_before": len(old), "bytes_after": len(new),
            "code_size_delta_bytes": 0, "changed_byte_count": len(differing),
            "changed_offsets": differing,
            "meaning": "CMP #3 -> CMP #4; branch and instruction geometry unchanged"}


def source_facts() -> dict[str, Any]:
    mon = MONITOR.read_text(encoding="utf-8")
    top = MONITOR_TOP.read_text(encoding="utf-8")
    ctrl = MONITOR_CTRL.read_text(encoding="utf-8")
    cpu = CORE_CPU.read_text(encoding="utf-8")
    eth = CORE_ETH.read_text(encoding="utf-8")
    require(mon.count("cmp         #3\n      bcs         bad_index") == 1,
            "stock history aperture is not the single #3 bound")
    for token in ("accept up to 3 hex digits", "compare index to 1023",
                  "sta         hist_read_hi", "jsr         print_history"):
        require(token in mon, f"monitor history-reader fact absent: {token}")
    for token in ("SIZEA(1024)", "history_wdata[55:40] = monitor_pc",
                  "history_wdata[71:56] = monitor_cpu_state",
                  "history_wdata[103:88] = monitor_sp",
                  "history_wdata[151:144] = monitor_opcode",
                  "history_wdata[159:152] = monitor_arg1",
                  "history_wdata[167:160] = monitor_arg2"):
        require(token in top, f"history field absent: {token}")
    for token in ("monitor_break_addr == monitor_pc && monitor_break_en",
                  "assign history_write = mem_trace_reg[2]",
                  "history_write_index < 1022", "history_write_continuous",
                  "history_write_index <= 0"):
        require(token in ctrl, f"break/history control fact absent: {token}")
    for token in ("InstructionFetch,                   -- 0x12",
                  "InstructionDecode,  -- $16          -- 0x13",
                  "InstructionDecode6502,              -- 0x14",
                  "monitor_state <= to_unsigned(processor_state'pos(state),8)&read_data",
                  "monitor_instructionpc <= reg_pc - 1"):
        require(token in cpu, f"CPU decode/history fact absent: {token}")
    require(eth.count("elsif false and (activity_dump='1')") == 1,
            "Ethernet instruction-stream availability changed")
    require("cpu_arrest_internal <= '1'" in eth,
            "Ethernet stream no longer carries timing-arrest risk")
    return {
        "history_storage": (
            "1024 entries x 24 bytes in monitor-private dual-port BRAM: "
            "$000..$3FE circular microcycle history plus $3FF current-state slot"),
        "history_cadence": (
            "one row per target-CPU clock while history-write is armed; the writer is "
            "not gated by monitor_instruction_strobe"),
        "captured_fields": ["current PC", "CPU state plus read byte", "SP",
                            "opcode", "arg1", "arg2",
                            "P/A/X/Y/Z/B", "MAPL", "MAPH"],
        "stock_breakpoint": (
            "address-only hardware PC comparator; insufficient here because the valid "
            "BRA at $803F also reaches PC $8041 while fetching its $8040 operand"),
        "successor_breakpoint": (
            "arm $8041 and qualify the existing comparator with CPU state $13/$14; that "
            "selects opcode decode after the $8040 fetch, rejects the valid operand fetch, "
            "and also catches fast-dispatch transfers"),
        "source_decode_rule": (
            "walk backward from the unique target decode row (uS $13/$14, PC $8041) "
            "to the prior uS $13/$14 row; its current PC minus one is the source PC "
            "and its CPU-state low byte is the fetched source opcode"),
        "stock_read_aperture": {"first": 0, "last": 0x2FF,
                                "readable_entries": 768,
                                "physical_entries": 1024,
                                "coverage_percent": 75.0,
                                "cause": "CMP high-byte,#3 rejects $300..$3FF"},
        "successor_read_aperture": {"first": 0, "last": 0x3FF,
                                    "readable_entries": 1024,
                                    "physical_entries": 1024,
                                    "coverage_percent": 100.0,
                                    "change": "CMP high-byte,#4"},
        "ethernet_stream": {
            "verdict": "REJECTED",
            "why": ("the bound core compiles the packet-emission arm behind literal false; "
                    "its buffering path can also assert ethernet_cpu_arrest and therefore "
                    "cannot carry a neutrality claim")},
    }


def capacity(truth: ElfTruth) -> dict[str, Any]:
    text = truth.section(".text")
    far = truth.section(".lisp65_c2_mapped_far_service")
    diagnostic = truth.section(".lisp65_c2_mapped_diagnostic")
    ordinary = 0xB3B0 - (text.address + text.bytes)
    far_free = diagnostic.address - (far.address + far.bytes)
    diagnostic_free = 0x8000 - (diagnostic.address + diagnostic.bytes)
    require((ordinary, far_free, diagnostic_free) == (18, 11, 47),
            "candidate capacity world drift")
    return {
        "candidate_derived": True,
        "before": {"ordinary_text_free_bytes": ordinary,
                   "far_service_free_bytes": far_free,
                   "mapped_diagnostic_free_bytes": diagnostic_free},
        "winner_product_deltas": {"ordinary_text_bytes": 0,
                                  "far_service_bytes": 0,
                                  "mapped_diagnostic_bytes": 0,
                                  "resident_state_bytes": 0,
                                  "scratch_bytes": 0},
        "after": {"ordinary_text_free_bytes": ordinary,
                  "far_service_free_bytes": far_free,
                  "mapped_diagnostic_free_bytes": diagnostic_free},
        "domain": "monitor-private BRAM/ROM, outside every product mapping domain",
    }


def decode_first_event(rows: list[dict[str, int]]) -> dict[str, int | str]:
    target_rows = [index for index, row in enumerate(rows)
                   if row["state"] in (INSTRUCTION_DECODE,
                                       INSTRUCTION_DECODE_6502)
                   and row["pc"] == TARGET_DECODE_PC]
    require(len(target_rows) == 1, "first-event model lacks unique target decode")
    target_index = target_rows[0]
    source_index = next(
        (index for distance in range(1, len(rows))
         if rows[(index := (target_index - distance) % len(rows))]["state"] in
         (INSTRUCTION_DECODE, INSTRUCTION_DECODE_6502)), None)
    require(source_index is not None, "first-event model lacks source decode")
    source = rows[source_index]
    target = rows[target_index]
    opcode = source["read_byte"]
    return {
        "source_pc": (source["pc"] - 1) & 0xFFFF,
        "source_opcode": opcode,
        "transfer_kind": "RTS/RTI" if opcode in (0x40, 0x60) else "direct",
        "event_sp": target["sp"],
    }


def decode_model() -> dict[str, Any]:
    cases = [
        {"name": "RTS", "source_pc": 0x6A10, "opcode": 0x60,
         "sp": 0x01A4, "expected": "RTS/RTI", "state": INSTRUCTION_DECODE,
         "wrap": False},
        {"name": "RTI-6502", "source_pc": 0xC7E5, "opcode": 0x40,
         "sp": 0x01C0, "expected": "RTS/RTI",
         "state": INSTRUCTION_DECODE_6502, "wrap": False},
        {"name": "JMP-absolute", "source_pc": 0x742E, "opcode": 0x4C,
         "sp": 0x0198, "expected": "direct", "state": INSTRUCTION_DECODE,
         "wrap": False},
        {"name": "JSR-fast-dispatch", "source_pc": 0x9517, "opcode": 0x20,
         "sp": 0x017E, "expected": "direct", "state": INSTRUCTION_DECODE,
         "wrap": True},
    ]
    decoded: list[dict[str, Any]] = []
    for row in cases:
        chronological = [
            {"state": row["state"], "pc": row["source_pc"] + 1,
             "read_byte": row["opcode"], "sp": row["sp"]},
            {"state": 0x44, "pc": row["source_pc"] + 1,
             "read_byte": 0x00, "sp": row["sp"]},
            {"state": row["state"], "pc": TARGET_DECODE_PC,
             "read_byte": 0x22, "sp": row["sp"]},
        ]
        history = ([chronological[-1], *chronological[:-1]]
                   if row["wrap"] else chronological)
        observed = decode_first_event(history)
        decoded.append({**row, "observed": observed})
    all_classified = all(
        row["observed"] == {
            "source_pc": row["source_pc"],
            "source_opcode": row["opcode"],
            "transfer_kind": row["expected"],
            "event_sp": row["sp"],
        } for row in decoded)
    return {
        "instruction_fetch_state": INSTRUCTION_FETCH,
        "decode_states": [INSTRUCTION_DECODE, INSTRUCTION_DECODE_6502],
        "target_decode_pc": TARGET_DECODE_PC,
        "source_rule": "prior decode PC minus one; opcode from that row's read byte",
        "valid_operand_fetch_rejected": {
            "pc": TARGET_DECODE_PC,
            "state": 0x15,
            "reason": "PC alone matches, but Cycle2 is not decode state $13/$14",
        },
        "cases": decoded,
        "all_classified": all_classified,
    }


def validate(value: dict[str, Any]) -> None:
    winner = value["winner"]
    require(value["status"] == "PRICED: COMPLETE ZERO-PRODUCT-BYTE WINNER; DIAGNOSTIC CORE REQUIRED",
            "pricing status drift")
    require(winner["product_bytes"] == 0 and winner["product_state_bytes"] == 0
            and winner["scratch_bytes"] == 0
            and winner["monitor_code_size_delta_bytes"] == 0
            and winner["monitor_changed_byte_count"] == 1,
            "winner price drift")
    require(winner["diagnostic_rtl_state_bits_delta"] == 0
            and winner["diagnostic_rtl_change"] ==
            "qualify the existing PC comparator with decode state $13/$14",
            "diagnostic breakpoint price drift")
    require(winner["captures"] == ["source PC", "transfer kind", "SP",
                                    "eight preserved stack-top bytes"],
            "first-event field set drift")
    require(value["neutrality"]["pre_event_product_writes"] == 0
            and value["neutrality"]["pre_event_cycle_delta"] == 0
            and value["neutrality"]["proved"] is True,
            "neutrality was not proved")
    require(value["stock_core_verdict"].startswith("REJECTED: 75%"),
            "incomplete stock aperture accepted")
    require(value["execution_lock"] == {
        "product_sources_changed": 0, "monitor_sources_changed": 0,
        "WPLTO_runs": 0, "product_links": 0, "core_builds": 0,
        "bitstreams_loaded": 0, "media_builds": 0, "device_contacts": 0},
        "pricing crossed its authorization boundary")
    require(value["implementation_readiness"]["ready_now"] is False,
            "unavailable diagnostic core was called ready")
    require(value["decode_model"]["all_classified"] is True
            and value["decode_model"]["target_decode_pc"] == TARGET_DECODE_PC,
            "source-PC decoder did not cover both remaining classes")


def derive() -> dict[str, Any]:
    inputs = {"ELF": bind(ELF), "table_attribution": bind(ATTRIBUTION),
              "core": core_binding()}
    require(inputs["ELF"]["sha256"] == ELF_SHA, "candidate ELF drift")
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    require(attribution["decision"]["remaining_classes"] == [
        "a corrupted RTS/RTI continuation before stack overwrite",
        "a live-mutated direct transfer outside the authorized reads"],
        "remaining-class authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    facts = source_facts()
    price = emitted_aperture_pair()
    capacities = capacity(truth)
    return {
        "format": FORMAT,
        "status": "PRICED: COMPLETE ZERO-PRODUCT-BYTE WINNER; DIAGNOSTIC CORE REQUIRED",
        "recorded_on": "2026-08-24",
        "authority": authority(),
        "inputs": inputs,
        "open_classes": attribution["decision"]["remaining_classes"],
        "source_facts": facts,
        "stock_core_verdict": (
            "REJECTED: 75% read aperture and address-only breakpoint cannot prove a "
            "one-contact first-event claim"),
        "alternatives": {
            "product_target_patch": {
                "verdict": "REJECTED: DOES NOT CAPTURE SOURCE PC",
                "reason": ("a trap at the non-boundary $8040 preserves the stack but the "
                           "source of an RTS/RTI or non-linking direct JMP is not encoded there")},
            "product_transfer_instrumentation": {
                "verdict": "REJECTED: FAILS NEUTRALITY",
                "reason": ("instrumenting the not-yet-known RTS/RTI/direct-transfer population "
                           "changes timing before the event and recreates a hand-list problem")},
            "ethernet_instruction_stream": facts["ethernet_stream"],
            "stock_serial_history": {
                "verdict": "REJECTED: INCOMPLETE",
                "reason": ("the event entry can occupy any of 1024 circular slots while the "
                           "stock command exposes only 768")},
            "stock_address_only_breakpoint": {
                "verdict": "REJECTED: FALSE POSITIVE",
                "reason": ("the valid BRA at $803F advances PC through $8041 while reading "
                           "its operand at $8040; only a decode-state-qualified match denotes "
                           "execution beginning at $8040")},
        },
        "winner": {
            "name": "volatile diagnostic-core serial-history aperture repair",
            "mechanism": ("arm the hardware breakpoint at $8041, qualify it with decode "
                          "state $13/$14, and record continuous microcycle history; expose "
                          "all 1024 already-recorded slots by changing the stopped-state "
                          "reader bound from #3 to #4"),
            "product_bytes": 0,
            "product_state_bytes": 0,
            "scratch_bytes": 0,
            "monitor_code_size_delta_bytes": price["code_size_delta_bytes"],
            "monitor_changed_byte_count": price["changed_byte_count"],
            "diagnostic_rtl_state_bits_delta": 0,
            "diagnostic_rtl_change": (
                "qualify the existing PC comparator with decode state $13/$14"),
            "diagnostic_rtl_price_limit": (
                "no new register, BRAM, product cycle or product byte; final LUT/timing "
                "acceptance remains a diagnostic-core synthesis gate"),
            "emitted_aperture_proof": price,
            "captures": ["source PC", "transfer kind", "SP",
                         "eight preserved stack-top bytes"],
            "why_complete": (
                "the unique decode row at PC $8041 proves that the opcode at $8040 was "
                "fetched, including under fast dispatch. Walking backward to the prior "
                "decode row yields source PC as PC-1 and source opcode from the CPU-state "
                "read byte; that opcode distinguishes RTS/RTI from direct transfer. The "
                "target-decode row preserves first-event SP. Any later downward pushes do "
                "not overwrite the eight bytes above that recorded SP."),
            "domain": "monitor-private control/BRAM; no product VMA or mapping alias",
        },
        "capacity": capacities,
        "origin": {
            "bound_zero": ("with target CPU held before launch: clear breakpoint/history, "
                           "set b8041, then tl resets history index and publishes continuous "
                           "recording together with free-run"),
            "atomic_publication_edge": "the final tl control-register write",
            "first_event_rule": ("select the unique uS $13/$14 row at PC $8041, then walk "
                                 "backward modulo the circular history to the prior decode row"),
            "wrap": ("$000..$3FE are 1023 circular history slots; $3FF is the current-state "
                     "slot; the successor exposes the complete $000..$3FF aperture"),
        },
        "neutrality": {
            "proved": True,
            "pre_event_product_writes": 0,
            "pre_event_cycle_delta": 0,
            "proof": [
                "history writes only monitor-private dual-port BRAM",
                "continuous history leaves target CPU in free-run and IRQ policy unchanged",
                "the breakpoint comparator changes trace state only after the $8040 opcode "
                "has been fetched and decode PC has become $8041",
                "the one-byte aperture change executes only in the stopped monitor reader",
                "no Ethernet stream or cpu_arrest path participates",
            ],
        },
        "contact_choreography_after_separate_authorization": [
            "load the diagnostic bitstream volatile-only; do not flash it",
            "hold the target CPU before candidate launch; clear stale break/history state",
            "set b8041; issue tl as the atomic origin-and-resume edge",
            "reproduce once; never resume after the hardware breakpoint fires",
            "read all 1024 history rows, registers and eight bytes above recorded first-event SP",
            "decode the unique target row at uS $13/$14 and PC $8041, then bind its prior "
            "decode row plus both raw and decoded views",
            "clear breakpoint and restore the stock core after the read",
        ],
        "decode_model": decode_model(),
        "removal_default": {
            "decision": "REMOVE AFTER ATTRIBUTION",
            "product_removal_bytes": 0,
            "action": "reload the stock a915893 bitstream; no product or medium changes exist",
        },
        "implementation_readiness": {
            "ready_now": False,
            "reason": ("the winner needs both the one-byte monitor-ROM aperture repair and "
                       "the decode-state-qualified RTL comparator. The workspace has neither "
                       "Vivado/updatemem nor a complete core build toolchain, so the diagnostic "
                       "core cannot be synthesized or timing-qualified under this pricing turn"),
            "required_next_authority": (
                "authorize one host-only diagnostic-core materialization/provenance step, then "
                "separately authorize the single volatile-load reproduction contact"),
            "no_product_card_required": True,
            "vivado_present": shutil.which("vivado") is not None,
            "updatemem_present": shutil.which("updatemem") is not None,
            "core_Ophis_present": (CORE / "Ophis/bin/ophis").is_file(),
        },
        "execution_lock": {
            "product_sources_changed": 0, "monitor_sources_changed": 0,
            "WPLTO_runs": 0, "product_links": 0, "core_builds": 0,
            "bitstreams_loaded": 0, "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Pricing only. No core source, product, link, bitstream, medium or device was "
            "changed. The receipt authorizes neither diagnostic-core materialization nor contact."),
    }


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "accept-stock-75-percent": lambda row: row.update(
            stock_core_verdict="ACCEPTED"),
        "spend-product-byte": lambda row: row["winner"].update(product_bytes=1),
        "erase-stack-field": lambda row: row["winner"].update(
            captures=["source PC", "transfer kind", "SP"]),
        "assert-neutrality": lambda row: row["neutrality"].update(proved=False),
        "claim-ready": lambda row: row["implementation_readiness"].update(
            ready_now=True),
        "drop-state-qualifier": lambda row: row["winner"].update(
            diagnostic_rtl_change="address-only comparator"),
        "spend-contact": lambda row: row["execution_lock"].update(device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "pricing mutation survived")
    return rejected


def main(argv: list[str]) -> int:
    require(len(argv) == 2 and argv[1] in {"check", "write"},
            "usage: c2_v160_selector_blank_first_event_latch_pricing.py check|write")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if argv[1] == "write":
        OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    else:
        require(OUT.is_file(), f"pricing receipt absent: {OUT}")
        require(json.loads(OUT.read_text(encoding="utf-8")) == value,
                "recorded first-event pricing drift")
    print("v1.6 first-event latch pricing: PASS winner=monitor-history "
          "product=0 monitor-delta=0 changed=1 aperture=1024/1024 "
          "ready=no mutations=7")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (PricingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"v1.6 first-event latch pricing: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
