#!/usr/bin/env python3
"""Bind the Link-109 phase-9 stop to the mapped-far ABI clobber."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CAPTURE = ROOT / "build/c2.3/v2.1-map-mask-phase9-rescue/capture.json"
CAPTURE_DRIVER = ROOT / "tools/host-lisp/c2_v21_phase9_rescue_capture.py"
ELF = ROOT / (
    "build/c2.3/v2.1-map-mask-fix-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
MEM = ROOT / "src/mem.c"
FAR = ROOT / "src/c2_mapped_far_convergence.s"
FACADE = ROOT / "src/optional/c2_mapped_far_service_v2.s"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
ABI_GATE = ROOT / (
    "build/c2.3/v2.1-map-mask-fix-card/final/"
    "c2-asm-leaf-abi-dataflow-gate.json")
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DEVICE_RECEIPT = ARCH / "c2.3-v2.1-phase9-gc-fixpoint-device-receipt.json"
RESULT_RECEIPT = ARCH / "c2.3-v2.1-phase9-gc-fixpoint-attribution-receipt.json"
FORMAT = "lisp65-c2.3-v2.1-phase9-gc-fixpoint-attribution-v1"
HISTORICAL_AUTHORITY = "78ae9255"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def historical_bind(path: Path) -> dict[str, Any]:
    """Bind the immutable pre-fix source world named by the owner decision."""
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{HISTORICAL_AUTHORITY}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def u16(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 2], "little")


def u32(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 4], "little")


def ranges(capture: dict[str, Any]) -> dict[str, bytes]:
    result = {row["name"]: bytes.fromhex(row["observed_hex"])
              for row in capture["reads"]}
    require(set(result) == {"bank0-zp-stack", "c2-runtime"},
            "authorized phase-9 range set drift")
    require(len(result["bank0-zp-stack"]) == 512
            and len(result["c2-runtime"]) == 50,
            "authorized phase-9 range length drift")
    return result


def disassembly(symbols: str) -> str:
    completed = subprocess.run(
        [str(OBJDUMP), "-d", f"--disassemble-symbols={symbols}", str(ELF)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return completed.stdout.lower()


def runtime(raw: bytes) -> dict[str, int]:
    require(len(raw) == 50 and u16(raw, 2) == 0xc084,
            "phase-9 runtime pointer drift")
    c = raw[4:]
    return {
        "committed_roots": u16(raw, 0),
        "shelf_bytes": u32(c, 0),
        "catalog_crc32": u32(c, 4),
        "c2d_bytes": u16(c, 8),
        "generation": u16(c, 10),
        "image_count": u16(c, 12),
        "entry_count": u16(c, 14),
        "resolution_count": u16(c, 16),
        "images_offset": u16(c, 18),
        "entries_offset": u16(c, 20),
        "resolutions_offset": u16(c, 22),
        "roots_offset": u16(c, 24),
        "root_count": u16(c, 26),
        "entry_cursor": u16(c, 28),
        "resolution_cursor": u16(c, 30),
        "root_cursor": u16(c, 32),
        "image_first": u16(c, 34),
        "entry_first": u16(c, 36),
        "resolution_first": u16(c, 38),
        "root_first": u16(c, 40),
        "phase": c[42], "finished": c[43], "error": c[44],
        "reserved": c[45],
    }


def audit(value: dict[str, Any]) -> None:
    heap = value["heap_state"]
    mechanism = value["mechanism"]
    require(
        value.get("status") == "PRODUCT-FIRST-RED: GC-FIXPOINT-ABI-CLOBBER"
        and value["runtime"]["phase"] == 9
        and value["runtime"]["finished"] == 0
        and value["runtime"]["error"] == 0
        and value["tuple"]["PC"] == "0x3be3"
        and value["tuple"]["MAPL"] == "0x0000"
        and value["tuple"]["A"] == "0xed"
        and heap["str_top"] == 0x2480
        and heap["str_arena_capacity"] == 0x2480
        and heap["str_building"] == 0x00ee
        and heap["str_building_cell"] == 119
        and heap["alloc_high"] == 119
        and heap["ext_mark_window"] == [119, 119]
        and heap["freelist"] != 0
        and heap["mem_oom"] == 0
        and mechanism["boolean_changed_expected"] == [0, 1]
        and mechanism["captured_rc20_rc21"] == [0xed, 0xb9]
        and mechanism["captured_rc20_word"] == "0xb9ed"
        and mechanism["ext_type_destination"] == "0xb9ed"
        and mechanism["sampled_store"] == "0x3be3: sta $16"
        and mechanism["mapped_far_body_preserves_rc20_rc21"] is False
        and mechanism["loop_is_structurally_closed"] is True
        and value["classification"]["CPU_reader_exonerated"] is True
        and value["classification"]["OOM_exonerated"] is True
        and value["classification"]["loop_mechanism_named"] is True
        and value["discipline"] == {"stops": 1, "resumes": 0,
            "runs": 0, "CPU_left_stopped": True, "D2_D5_open": False},
        "phase-9 attribution claim drift")


def mutations(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "move-outside-gc": ("tuple", "PC", "0x2277"),
        "claim-reader-map-active": ("tuple", "MAPL", "0x4fc0"),
        "advance-decoder": ("runtime", "phase", 10),
        "invent-decoder-error": ("runtime", "error", 1),
        "hide-arena-boundary": ("heap_state", "str_top", 0x247f),
        "invent-OOM": ("heap_state", "mem_oom", 1),
        "erase-builder": ("heap_state", "str_building", 0),
        "move-mark-window": ("heap_state", "ext_mark_window", [118, 119]),
        "normalize-captured-A": ("tuple", "A", "0x01"),
        "normalize-captured-rc20": ("mechanism", "captured_rc20_rc21", [1, 0xb9]),
        "move-ext-type-destination": ("mechanism", "ext_type_destination", "0xb9ee"),
        "claim-far-preservation": ("mechanism", "mapped_far_body_preserves_rc20_rc21", True),
        "weaken-loop-closure": ("mechanism", "loop_is_structurally_closed", False),
        "reblame-reader": ("classification", "CPU_reader_exonerated", False),
        "open-D2-D5": ("discipline", "D2_D5_open", True),
    }
    rejected: list[str] = []
    for name, (section, field, replacement) in cases.items():
        trial = deepcopy(base)
        trial[section][field] = replacement
        try:
            audit(trial)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "phase-9 attribution mutation survived")
    return {"count": len(rejected), "rejected": rejected}


def derive() -> tuple[dict[str, Any], dict[str, Any]]:
    capture = load(CAPTURE)
    raw = ranges(capture)
    bank0 = raw["bank0-zp-stack"]
    run = runtime(raw["c2-runtime"])
    tuple_row = capture["tuple"]
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    symbols = {name: truth.symbol(name).value for name in (
        "gc_collect", "ext_type", "ext_stg1", "vm_code_load_converged",
        "c2_mapped_far_vm_code_load_converged", "c2_map_cpu_read")}
    require(symbols == {"gc_collect": 0x39c3, "ext_type": 0x3470,
            "ext_stg1": 0xb9ed, "vm_code_load_converged": 0xb3b0,
            "c2_mapped_far_vm_code_load_converged": 0x79dc,
            "c2_map_cpu_read": 0x2277},
            f"phase-9 symbol identity drift: {symbols!r}")
    gc = disassembly("gc_collect")
    ext = disassembly("ext_type")
    far_text = FAR.read_text(encoding="utf-8")
    facade_text = FACADE.read_text(encoding="utf-8")
    reader_text = READER.read_text(encoding="utf-8")
    mem_text = MEM.read_text(encoding="utf-8")
    require(
        "3bce: 05 16" in gc and "ora\t$16" in gc
        and "3be3: 85 16" in gc and "sta\t$16" in gc
        and "3bf5: a6 16" in gc and "ldx\t$16" in gc
        and "3bf7: 64 16" in gc and "stz\t$16" in gc,
        "linked GC changed-loop identity drift")
    require(
        "a2 ed" in ext and "a2 b9" in ext
        and "jsr\t$3350" in ext,
        "linked ext_type destination identity drift")
    vm_body = far_text.split(
        "c2_mapped_far_vm_code_load_converged:", 1)[1].split(
        ".Lc2_mapped_far_vm_code_load_converged_end:", 1)[0]
    require(
        "sta __rc20" in vm_body and "sta __rc21" in vm_body
        and "lda (__rc20),y" in vm_body
        and not any(token in vm_body for token in
                    ("pha __rc20", "push __rc20", "restore __rc20")),
        "mapped-far rc20/rc21 clobber identity drift")
    require(
        "jsr c2_mapped_far_vm_code_load_converged" in facade_text
        and "deliberately uses only caller-clobbered" in far_text
        and ".zeropage __rc20" in far_text
        and ".zeropage __rc31" in far_text,
        "mapped-far facade/source provenance drift")
    require(
        "do {" in mem_text and "changed = 0;" in mem_text
        and "changed |= gc_mark_children_ext(i);" in mem_text
        and "} while (changed);" in mem_text
        and "if (str_top >= STR_ARENA_SIZE)" in mem_text
        and "GC_PUSH(s); gc_collect(); GC_POPN(1);" in mem_text,
        "source-level GC/arena edge drift")
    # Register-preservation is not an inferred ABI opinion: LLVM-MOS emitted
    # the save/restore protocol for the same registers in ordinary C bodies.
    require(
        "39d0: a6 16" in gc and "39d2: da" in gc
        and "deliberately uses only caller-clobbered" in far_text,
        "compiler-emitted callee-save/control mismatch drift")
    require("sta __rc16" in reader_text and "sta __rc18" in reader_text,
            "pre-registered assembly-closure sibling drift")

    heap = {
        "alloc_high": u16(bank0, 0x3b),
        "gc_frozen": u16(bank0, 0x3d),
        "freelist": u16(bank0, 0x3f),
        "gc_badobj_cumulative": u16(bank0, 0x41),
        "allocs_since_gc": u16(bank0, 0x43),
        "ext_mark_window": [u16(bank0, 0x45), u16(bank0, 0x47)],
        "str_top": u16(bank0, 0x49),
        "str_arena_capacity": 0x2480,
        "str_frozen": u16(bank0, 0x4b),
        "gc_rootsp": u16(bank0, 0x5e),
        "c2_pending_roots": u16(bank0, 0x8a),
        "c2_ready": bank0[0x8c],
        "str_building": u16(bank0, 0x8d),
        "str_building_cell": u16(bank0, 0x8d) >> 1,
        "mem_oom": bank0[0x8f],
    }
    value: dict[str, Any] = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PRODUCT-FIRST-RED: GC-FIXPOINT-ABI-CLOBBER",
        "authority": {"capture": bind(CAPTURE),
            "capture_driver": bind(CAPTURE_DRIVER), "candidate_ELF": bind(ELF),
            "mem_source": bind(MEM), "mapped_far_source": bind(FAR),
            "mapped_far_facade": bind(FACADE), "CPU_reader_source": bind(READER),
            "assembler_ABI_gate": bind(ABI_GATE)},
        "tuple": tuple_row,
        "runtime": run,
        "heap_state": heap,
        "mechanism": {
            "sampled_function": "gc_collect+0x220",
            "sampled_store": "0x3be3: sta $16",
            "sampled_last_instruction": "0x3be1: ldy $06",
            "boolean_changed_expected": [0, 1],
            "captured_A_before_store": 0xed,
            "captured_rc20_rc21": [bank0[0x16], bank0[0x17]],
            "captured_rc20_word": f"0x{u16(bank0, 0x16):04x}",
            "ext_type_destination": f"0x{symbols['ext_stg1']:04x}",
            "clobber_chain": [
                "gc_collect retains uint8_t changed in __rc20/$16",
                "gc_mark_children_ext calls ext_type while changed is live",
                "ext_type calls vm_code_load_converged for destination $B9ED",
                "mapped-far body writes destination+index to __rc20/__rc21",
                "mapped-far body returns without restoring callee-saved pseudo-registers",
                "gc_collect ORs $ED into changed and stores $ED at $3BE3",
                "the marked EXT window remains nonempty, so every pass repeats the clobber"],
            "mapped_far_body_preserves_rc20_rc21": False,
            "compiler_emitted_preservation_evidence": (
                "gc_collect and gc_mark_spine save __rc20+ on entry; the handwritten "
                "far body instead calls __rc20..__rc31 caller-clobbered and saves none"),
            "loop_is_structurally_closed": True,
        },
        "classification": {
            "CPU_reader_exonerated": True,
            "CPU_reader_reason": "MAPL=$0000 and phases 1..8 completed",
            "decoder_exonerated": True,
            "decoder_reason": "phase=9, error=0; sampled PC is GC, not decoder/reader",
            "OOM_exonerated": True,
            "OOM_reason": "mem_oom=0 and freelist=$00A8",
            "loop_mechanism_named": True,
            "mechanism": "mapped-far service violates LLVM-MOS callee-save ABI",
            "gc_badobj_boundary": (
                "gc_badobj=4 is cumulative and has no before-sample; it is retained "
                "as an anomaly but is neither used nor erased by the loop claim"),
        },
        "fix_boundary": {
            "product": (
                "Every return from the mapped-far call closure must restore every "
                "callee-saved pseudo-register it touches; preserve the full touched set "
                "or rewrite it into caller-clobbered/owned state, then prove all exits."),
            "gate": (
                "The assembler ABI gate must close transitively over ASM-to-ASM callees "
                "reachable from a C-called leaf, not stop at the direct facade. A missed "
                "callee-saved register or exit must fail. c2_map_cpu_read is the named "
                "direct-C sibling for the same one-time audit."),
            "authorization": "not granted by this read-only attribution",
        },
        "discipline": {"stops": 1, "resumes": 0, "runs": 0,
            "CPU_left_stopped": True, "D2_D5_open": False},
        "claim_limit": (
            "The exact captured A/rc20 value, linked store and source/ELF call closure "
            "name a deterministic phase-9 GC fixpoint loop. gc_badobj=4 is cumulative "
            "without a before-sample and receives no causal or delta claim. No fix, "
            "card, resume or new device contact is authorized."),
    }
    audit(value)
    value["mutations"] = mutations(value)
    audit(value)
    device = {
        "format": "lisp65-c2.3-v2.1-phase9-gc-fixpoint-device-v1",
        "captured_on": capture["captured_on"], "authority": capture["authority"],
        "device": capture["device"], "discipline": capture["discipline"],
        "stop_raw_hex": capture["stop_raw_hex"],
        "register_raw_hex": capture["register_raw_hex"],
        "tuple": tuple_row, "reads": capture["reads"],
        "CPU_left_stopped": True,
    }
    return device, value


def check() -> None:
    device = load(DEVICE_RECEIPT)
    result = load(RESULT_RECEIPT)
    audit(result)
    require(result.get("mutations") == mutations(result),
            "persisted phase-9 mutations drift")
    require(result["authority"]["device_receipt"] == bind(DEVICE_RECEIPT)
            and result["authority"]["capture_driver"] == bind(CAPTURE_DRIVER)
            and result["authority"]["candidate_ELF"] == bind(ELF)
            and result["authority"]["mapped_far_source"]
                == historical_bind(FAR)
            and result["authority"]["CPU_reader_source"]
                == historical_bind(READER)
            and result["authority"]["assembler_ABI_gate"] == bind(ABI_GATE),
            "persisted phase-9 authority drift")
    require(device["tuple"] == result["tuple"]
            and device["discipline"]["stops"] == 1
            and device["discipline"]["resumes"] == 0
            and device["CPU_left_stopped"] is True,
            "persisted phase-9 device discipline drift")
    raw = ranges(device)
    require(runtime(raw["c2-runtime"]) == result["runtime"],
            "persisted phase-9 runtime/raw mismatch")


def main() -> int:
    try:
        require(len(sys.argv) <= 2 and (len(sys.argv) == 1
                or sys.argv[1] in {"bind", "check"}),
                "usage: c2_v21_phase9_gc_fixpoint_attribution.py [bind|check]")
        if len(sys.argv) == 2 and sys.argv[1] == "check":
            check()
            print("c2-v21-phase9-gc-fixpoint: PASS: persisted mechanism bound")
            return 0
        device, result = derive()
        DEVICE_RECEIPT.write_bytes(canonical(device))
        result["authority"]["device_receipt"] = bind(DEVICE_RECEIPT)
        RESULT_RECEIPT.write_bytes(canonical(result))
        print("c2-v21-phase9-gc-fixpoint: PASS: $B9ED clobbers changed in __rc20")
        print(json.dumps({"device_receipt": bind(DEVICE_RECEIPT),
            "result_receipt": bind(RESULT_RECEIPT),
            "mutations": result["mutations"]}, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError,
            ResultError) as error:
        print(f"c2-v21-phase9-gc-fixpoint: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
