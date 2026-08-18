#!/usr/bin/env python3
"""Price the two owner-commissioned resident-text recovery shapes for 2.1."""

from __future__ import annotations

from copy import deepcopy
import hashlib
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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CALL_SEAM = ARCH / "c2.3-v2.1-call-seam-pricing-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-shrink-card-final-red.json"
RECEIPT = ARCH / "c2.3-v2.1-text-recovery-pricing-receipt.json"
BUILD = ROOT / "build/c2.3/v2.1-cpu-transport-shrink-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
EMITTER = ROOT / "src/c2_session_emitter.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
FACADE = ROOT / "src/c2_kernal_facade_reopen.s"
PACKED_MANIFEST = ROOT / (
    "build/c2.3/v2.0-phase02b-header-consumption-replacement-card/final/"
    "runtime-overlays-session-final.json")
PACKED_RECEIPT = ARCH / (
    "c2.3-v2.0-phase02b-header-consumption-replacement-card-receipt.json")
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
AUTHORIZATION = "992e70f6"
RECORDED_ON = "2026-08-14"

SELECTOR_SOURCE = r"""
	.section .text.c2_map_cpu_selector,"ax",@progbits
	.globl priced_selector
	.globl c2_stream_c2d_read_return
	.globl c2_stream_shelf_read_return
	.globl vm_runtime_overlay_exec
	.globl c2_map_cpu_read
priced_selector:
	pha
	phx
	tsx
	lda $0104,x
	cmp #>(c2_stream_c2d_read_return-1)
	bne .Lcheck_shelf
	lda $0103,x
	cmp #<(c2_stream_c2d_read_return-1)
	beq .Lreader
	bra .Lruntime
.Lcheck_shelf:
	cmp #>(c2_stream_shelf_read_return-1)
	bne .Lruntime
	lda $0103,x
	cmp #<(c2_stream_shelf_read_return-1)
	beq .Lreader
.Lruntime:
	plx
	pla
	jmp vm_runtime_overlay_exec
.Lreader:
	plx
	pla
	jmp c2_map_cpu_read
	.size priced_selector, .-priced_selector
"""


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(*argv: str) -> str:
    return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def git_blob(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = run("git", "rev-parse", f"{commit}^{{commit}}").strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, authority = git_blob(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "text-recovery pricing commissioned",
            "micro-recovery",
            "wholesale displacement",
            "winner by price",
            "exactly one card",
            "margins stay non-budgets"):
        require(token in text, f"text-recovery authorization token absent: {token}")
    return authority


def assemble(source: str, section: str, symbol: str) -> tuple[int, ElfTruth]:
    with tempfile.TemporaryDirectory(prefix="c2-v21-text-price-") as raw:
        directory = Path(raw)
        assembly = directory / "price.s"
        obj = directory / "price.o"
        assembly.write_text(source, encoding="utf-8")
        completed = subprocess.run([
            str(LLVM / "mos-mega65-clang"), "-c", "-mcpu=mos45gs02",
            str(assembly), "-o", str(obj),
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
           stderr=subprocess.STDOUT, check=False)
        require(completed.returncode == 0,
                f"pricing fixture did not assemble:\n{completed.stdout}")
        truth = ElfTruth.read(obj, llvm_readobj=LLVM / "llvm-readobj")
        row = truth.symbol(symbol)
        require(row.section == section and row.bytes == truth.section(section).bytes,
                f"fixture symbol/section identity drift: {symbol}")
        return row.bytes, truth


def micro_candidate() -> dict[str, Any]:
    current = READER.read_text(encoding="utf-8")
    old = "\tlda __rc15\n\tldx __rc18\n\tldy #0\n\tldz #$80\n\tmap\n\teom\n\tldz #0\n\trts"
    new = "\tlda __rc15\n\tldx __rc18\n\tmap\n\teom\n\trts"
    require(current.count(old) == 1, "map-window helper identity drift")
    candidate = current.replace(old, new, 1)
    current_bytes, _ = assemble(
        current, ".text.c2_map_cpu_read", "c2_map_cpu_read")
    candidate_bytes, _ = assemble(
        candidate, ".text.c2_map_cpu_read", "c2_map_cpu_read")
    prefix = current[:current.index("jsr .Lc2_cpu_map_window")]
    retained = prefix[prefix.rindex("\tldz #$80"):]
    copy = current[current.index(".Lc2_cpu_copy:"):
                   current.index(".Lc2_cpu_restore:")]
    restore = current[current.index(".Lc2_cpu_restore:"):
                      current.index(".Lc2_cpu_ok:")]
    require(
        current_bytes == 166 and candidate_bytes == 160
        and "\tldy #0\n\tmap\n\teom" in retained
        and not re.search(r"\t(?:ldz|inz|dez|plz|taz)\b", retained[1:])
        and not re.search(r"\t(?:ldy|iny|dey|ply|tay|ldz|inz|dez|plz|taz)\b", copy)
        and "\tldz #0\n\tplp" in restore
        and candidate.count("\tmap\n") == current.count("\tmap\n") == 5
        and candidate.count("\teom\n") == current.count("\teom\n") == 5,
        "six-byte micro candidate weakened the Y/Z/MAP invariant")
    return {
        "status": "PRICED BUT REJECTED FOR COMPLETE SEAM: exact six-byte recovery",
        "routine": "c2_map_cpu_read",
        "instruction_delta": ["remove helper LDY #0", "remove helper LDZ #$80",
                              "remove helper LDZ #0"],
        "checks_removed": 0,
        "before_bytes": current_bytes,
        "after_bytes": candidate_bytes,
        "resident_bytes_recovered": current_bytes - candidate_bytes,
        "proof": {
            "first_helper_entry": "caller already establishes Y=0,Z=$80",
            "copy_loop": "changes neither Y nor Z",
            "later_helper_entries": "therefore retain Y=0,Z=$80",
            "public_exit": "restore epilogue still establishes Z=0",
            "MAP_EOM_pairs_unchanged": 5,
        },
    }


def selector_fixture() -> dict[str, Any]:
    used, truth = assemble(
        SELECTOR_SOURCE, ".text.c2_map_cpu_selector", "priced_selector")
    targets = [(row.target, row.relocation_type)
               for row in truth.relocations
               if row.source_section == ".text.c2_map_cpu_selector"]
    names = [name for name, _ in targets]
    require(
        used == 40
        and names.count("c2_stream_c2d_read_return") == 2
        and names.count("c2_stream_shelf_read_return") == 2
        and names.count("vm_runtime_overlay_exec") == 1
        and names.count("c2_map_cpu_read") == 1,
        "complete selector fixture price/relocation identity drift")
    return {
        "status": "PASS: complete preserving selector prices at 40 ordinary bytes",
        "ordinary_bytes": used,
        "fixed_vector_bytes_delta": 0,
        "E000_callsite_bytes_delta": 0,
        "classification": (
            "inspect the JSR return identity through the existing "
            "runtime-overlay-exec vector"),
        "reader_callers": ["c2_stream_c2d_read_return",
                           "c2_stream_shelf_read_return"],
        "default": "every other caller retains vm_runtime_overlay_exec",
        "register_discipline": "PHA/PHX before classification; PLX/PLA on both tails",
        "Y_Z_discipline": "selector neither reads nor writes Y/Z",
        "identity_discipline": (
            "two symbolic post-call labels and relocations; no raw linked-PC pin"),
        "relocations": [{"target": name, "type": kind}
                        for name, kind in targets],
    }


def disassembly_calls(truth: ElfTruth) -> dict[str, Any]:
    target = truth.symbol("c2e_w32")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    text = run(str(LLVM / "llvm-objdump"), "-d", str(ELF))
    pattern = re.compile(
        rf"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{{2}}\s+)+"
        rf"jsr\s+\${target.value:x}\b", re.M)
    rows = [int(match.group(1), 16) for match in pattern.finditer(text)]
    require(rows == [0xC526, 0xC544, 0xC561, 0xC664, 0xC67B]
            and all(cold.address <= address < cold.address + cold.bytes
                    for address in rows),
            "c2e_w32 does not have exactly five cold-slice-only linked callers")
    return {
        "count": len(rows),
        "caller_section": cold.name,
        "caller_addresses": [f"0x{address:04x}" for address in rows],
        "outside_cold_slice": 0,
    }


def packed_slice() -> dict[str, Any]:
    manifest = load(PACKED_MANIFEST)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    matches = [row for row in rows
               if row["section"] == ".lisp65_rt_c2emit_final_crc"]
    require(len(matches) == 1, "packed final-CRC slice identity drift")
    row = matches[0]
    index = rows.index(row)
    require(index + 1 < len(rows), "packed final-CRC successor absent")
    next_offset = rows[index + 1]["file_offset"]
    allocation = next_offset - row["file_offset"]
    require(
        row["file_size"] == 1183 and allocation == 1280
        and manifest["policy"]["payload_alignment"] == 256
        and manifest["policy"]["max_slice_bytes"] == 1792
        and manifest["storage"]["size"] == 65423
        and manifest["storage"]["limit"] == 134283264,
        "packed cold-slice layout authority drift")
    return {
        "slice_id": row["id"],
        "section": row["section"],
        "file_offset": row["file_offset"],
        "file_bytes": row["file_size"],
        "allocated_page_span_bytes": allocation,
        "padding_bytes": allocation - row["file_size"],
        "hard_slice_cap_bytes": manifest["policy"]["max_slice_bytes"],
        "aggregate_bytes": manifest["storage"]["size"],
        "aggregate_capacity_bytes": (
            manifest["storage"]["limit"] - manifest["storage"]["address"]),
        "aggregate_headroom_bytes": (
            manifest["storage"]["limit"] - manifest["storage"]["address"]
            - manifest["storage"]["size"]),
    }


def wholesale_candidate(truth: ElfTruth) -> dict[str, Any]:
    routine = truth.symbol("c2e_w32")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    packed = packed_slice()
    projected = cold.bytes + routine.bytes
    projected_allocation = (projected + 255) & ~255
    require(
        routine.section == ".text" and routine.bytes == 63
        and cold.bytes == packed["file_bytes"] == 1183
        and projected == 1246 and projected_allocation == 1280
        and projected <= packed["hard_slice_cap_bytes"],
        "wholesale displacement price drift")
    return {
        "status": "WINNER: wholesale displacement into existing cold slice",
        "routine": "c2e_w32",
        "routine_address": f"0x{routine.value:04x}",
        "resident_bytes_recovered": routine.bytes,
        "destination": ".lisp65_rt_c2emit_final_crc",
        "placement_contract_change": (
            "c2e_w32 becomes a named member of the final-CRC cold slice"),
        "call_edges": disassembly_calls(truth),
        "packed_layout": {
            **packed,
            "projected_file_bytes": projected,
            "projected_allocated_page_span_bytes": projected_allocation,
            "projected_padding_bytes": projected_allocation - projected,
            "projected_hard_cap_headroom_bytes": (
                packed["hard_slice_cap_bytes"] - projected),
            "new_slice_required": False,
            "aggregate_growth_bytes": 0,
        },
        "risk": (
            "A placement-contract change, bounded by co-residency, slice-cap, "
            "page-span and no-new-caller gates; no nested overlay transfer is added."),
    }


def derive() -> dict[str, Any]:
    seam = load(CALL_SEAM)
    red = load(FINAL_RED)
    require(seam.get("status") == "PRICED: NONE OF THREE CALL SEAMS FITS"
            and seam.get("pricing", {}).get("decision", {}).get(
                "owner_disposition_required") is True,
            "call-seam predecessor authority drift")
    require(red.get("status") == "FINAL RED: CPU-reader shrink card returns to owner",
            "shrink-card Final Red authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM / "llvm-readobj")
    ordinary = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    available = facade.address - (ordinary.address + ordinary.bytes)
    require(available == 1, "ordinary text capacity authority drift")
    micro = micro_candidate()
    selector = selector_fixture()
    wholesale = wholesale_candidate(truth)
    micro_after = available + micro["resident_bytes_recovered"]
    wholesale_before = available + wholesale["resident_bytes_recovered"]
    require(micro_after == 7 and selector["ordinary_bytes"] == 40
            and wholesale_before == 64,
            "option comparison arithmetic drift")
    value = {
        "format": "lisp65-c2.3-v2.1-text-recovery-pricing-v1",
        "recorded_on": RECORDED_ON,
        "status": "PRICED: WHOLESALE COLD-PHASE DISPLACEMENT WINS; CARD GO REQUIRED",
        "authority": {
            "commission": authorization(),
            "call_seam_receipt": bind(CALL_SEAM),
            "shrink_card_final_red": bind(FINAL_RED),
            "linked_ELF": bind(ELF), "linked_map": bind(MAP),
            "reader": bind(READER), "emitter": bind(EMITTER),
            "runtime": bind(RUNTIME), "facade": bind(FACADE),
            "packed_slice_manifest": bind(PACKED_MANIFEST),
            "packed_slice_receipt": bind(PACKED_RECEIPT),
            "driver": bind(DRIVER),
        },
        "baseline": {
            "ordinary_text_end_exclusive": f"0x{ordinary.address + ordinary.bytes:04x}",
            "mapped_far_facade_start": f"0x{facade.address:04x}",
            "ordinary_bytes_available": available,
            "contracted_margins_used_as_freight": False,
            "contracted_margins": {"ordinary_chain": 5,
                                   "runtime_overlay": 6,
                                   "bank0_state": 7},
        },
        "complete_selector_seam": selector,
        "option_a_micro_recovery": {
            **micro,
            "ordinary_bytes_before_selector": micro_after,
            "selector_bytes": selector["ordinary_bytes"],
            "ordinary_deficit_after_complete_pricing": (
                selector["ordinary_bytes"] - micro_after),
            "ordinary_reserve_after_selector": None,
        },
        "option_b_wholesale_displacement": {
            **wholesale,
            "ordinary_bytes_before_selector": wholesale_before,
            "selector_bytes": selector["ordinary_bytes"],
            "ordinary_reserve_after_selector": (
                wholesale_before - selector["ordinary_bytes"]),
            "net_resident_delta_bytes": (
                selector["ordinary_bytes"] - wholesale["resident_bytes_recovered"]),
            "fixed_block_delta_bytes": 0,
            "E000_delta_bytes": 0,
            "aggregate_image_delta_bytes": 0,
        },
        "decision": {
            "winner": "option-b-wholesale-displacement",
            "why": (
                "Option A recovers exactly six bytes but remains 33 bytes short "
                "after complete selector pricing. Moving c2e_w32 recovers 63 bytes "
                "inside an already allocated cold-slice page and leaves 24 ordinary "
                "bytes after the 40-byte preserving selector."),
            "recommended_card_scope": [
                "place c2e_w32 in .lisp65_rt_c2emit_final_crc",
                "add symbolic zero-byte post-call labels at the two E000 reader calls",
                "retarget c2_facade_runtime_overlay_exec to the preserving selector",
                "route only the two named return identities to c2_map_cpu_read",
                "route every other identity to vm_runtime_overlay_exec",
            ],
            "required_gates": [
                "clean-path c2e_w32 semantic equivalence",
                "all c2e_w32 callsites co-resident in final-CRC slice",
                "final-CRC slice remains in its current page and below hard cap",
                "selector A/X preservation and unknown-caller legacy routing",
                "symbolic return identities, never raw linked-PC constants",
                "fixed-vector and E000 code sizes unchanged",
                "contracted margins remain non-budgets",
            ],
            "card_authorized": False,
            "cards_available_after_owner_go": 1,
            "owner_disposition_required": True,
        },
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
                               "product_links": 0, "media_builds": 0,
                               "device_contacts": 0},
        "claim_limit": (
            "Host/ELF pricing only. No product-source edit, placement change, "
            "selector, card, product link, medium or device contact occurred."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(
        value["status"].startswith("PRICED: WHOLESALE")
        and value["attempt_accounting"] == {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "desk-only pricing/accounting drift")
    selector = value["complete_selector_seam"]
    micro = value["option_a_micro_recovery"]
    wholesale = value["option_b_wholesale_displacement"]
    decision = value["decision"]
    require(
        selector["ordinary_bytes"] == 40
        and selector["fixed_vector_bytes_delta"] == 0
        and selector["E000_callsite_bytes_delta"] == 0
        and selector["default"] == "every other caller retains vm_runtime_overlay_exec"
        and "PHA/PHX" in selector["register_discipline"]
        and "no raw linked-PC pin" in selector["identity_discipline"]
        and micro["resident_bytes_recovered"] == 6
        and micro["checks_removed"] == 0
        and micro["ordinary_deficit_after_complete_pricing"] == 33
        and wholesale["resident_bytes_recovered"] == 63
        and wholesale["call_edges"]["outside_cold_slice"] == 0
        and wholesale["packed_layout"]["projected_file_bytes"] == 1246
        and wholesale["packed_layout"]["projected_allocated_page_span_bytes"] == 1280
        and wholesale["packed_layout"]["new_slice_required"] is False
        and wholesale["ordinary_reserve_after_selector"] == 24
        and wholesale["net_resident_delta_bytes"] == -23
        and wholesale["fixed_block_delta_bytes"] == 0
        and wholesale["E000_delta_bytes"] == 0
        and wholesale["aggregate_image_delta_bytes"] == 0
        and decision["winner"] == "option-b-wholesale-displacement"
        and decision["card_authorized"] is False
        and decision["cards_available_after_owner_go"] == 1
        and decision["owner_disposition_required"] is True
        and value["baseline"]["contracted_margins_used_as_freight"] is False,
        "priced winner or contract boundary weakened")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "accept-micro-despite-deficit": lambda x: x["decision"].update(
            winner="option-a-micro-recovery"),
        "erase-micro-deficit": lambda x: x["option_a_micro_recovery"].update(
            ordinary_deficit_after_complete_pricing=0),
        "remove-micro-check": lambda x: x["option_a_micro_recovery"].update(
            checks_removed=1),
        "underprice-selector": lambda x: x["complete_selector_seam"].update(
            ordinary_bytes=39),
        "clobber-selector-registers": lambda x: x["complete_selector_seam"].update(
            register_discipline="A/X clobbered"),
        "route-unknown-to-reader": lambda x: x["complete_selector_seam"].update(
            default="unknown caller reaches c2_map_cpu_read"),
        "pin-raw-return-PC": lambda x: x["complete_selector_seam"].update(
            identity_discipline="raw PC constants"),
        "add-outside-cold-caller": lambda x: x["option_b_wholesale_displacement"]
            ["call_edges"].update(outside_cold_slice=1),
        "overflow-cold-page": lambda x: x["option_b_wholesale_displacement"]
            ["packed_layout"].update(projected_allocated_page_span_bytes=1536),
        "require-new-overlay-slot": lambda x: x["option_b_wholesale_displacement"]
            ["packed_layout"].update(new_slice_required=True),
        "erase-wholesale-reserve": lambda x: x["option_b_wholesale_displacement"].update(
            ordinary_reserve_after_selector=0),
        "spend-contracted-margin": lambda x: x["baseline"].update(
            contracted_margins_used_as_freight=True),
        "authorize-card-at-desk": lambda x: x["decision"].update(
            card_authorized=True, owner_disposition_required=False),
        "invent-card-run": lambda x: x["attempt_accounting"].update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "text-recovery pricing mutation survived")
    return rejected


def main() -> int:
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("c2-v2.1-text-recovery-pricing: PASS winner=wholesale "
          "recovered=63 selector=40 reserve=24 mutations=14 cards=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
