#!/usr/bin/env python3
"""Classify the captured v1.5 D2 ``defun`` BADOPCODE.

The device was stopped once after the bound First Red.  This checker derives
the append state and the complete staged L65S/C2I object from those physical
reads, then binds the exact target-only compiler shape to the unprotected
F018B read seams that supplied both heap cells and symbol names.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import c2_repl_pipeline_cost_attribution as PIPE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CAPTURE = ROOT / "build/c2.3/v1.5.0-name-freight-d2-badopcode-capture"
DESK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-desk-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-capture-receipt.json"
)
ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
CANONICAL = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/"
    "canonical-product-manifest.json"
)
INSPECT = ROOT / (
    "build/c2.3/v1.5.0-name-freight-libraries/inspect.manifest.json"
)
STRING_EXTRA = ROOT / (
    "build/post-promotion/v112/string-extra/string-extra.manifest.json"
)
SCREEN = ROOT / (
    "build/c2.3/v1.5.0-name-freight-d2-d5/row-d2-define-probe.txt"
)
EMITTER = ROOT / "src/c2_session_emitter.c"
DECODER = ROOT / "src/c2_product_decoder.c"
SYMBOL = ROOT / "src/symbol.c"
DMA = ROOT / "src/c2_platform_dma.c"
DMA_HEADER = ROOT / "src/c2_platform_dma.h"
MEM = ROOT / "src/mem.c"
WORKBENCH = ROOT / "config/workbench.mk"
ABI = ROOT / "config/bytecode-abi-ledger.json"

FORMAT = "lisp65-c2.3-v150-name-freight-D2-defun-BADOPCODE-capture-v1"
STATUS = "F018B-READ-CONTENT-COMPLETION-PROVEN"
FORM = "(defun trace-probe (x) (+ x 1))"
POISONED_FORM = "(defun trace-probe (x) + (+ x 1))"
STAGE_FILE_OFFSET = 0x6900 + 0x100
STAGE_BYTES = 148


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def u16(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 2], "little")


def u24(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 3], "little")


def u32(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 4], "little")


def stream(raw: bytes, at: int = 0) -> dict[str, int]:
    names = (
        "shelf_bytes", "catalog_crc32", "c2d_bytes", "generation",
        "image_count", "entry_count", "resolution_count", "images_offset",
        "entries_offset", "resolutions_offset", "roots_offset",
        "image_cursor", "entry_cursor", "resolution_cursor",
        "pair_depth_max", "image_first", "entry_first",
        "resolution_first", "root_first", "phase", "finished", "error",
        "reserved",
    )
    values = [u32(raw, at), u32(raw, at + 4)]
    values += [u16(raw, at + off) for off in range(8, 42, 2)]
    values += list(raw[at + 42:at + 46])
    require(len(names) == len(values), "stream decoder layout drift")
    return dict(zip(names, values))


def host_compile(source: str) -> dict[str, Any]:
    canonical_value, stdlib, carrier = PIPE.manifest_paths(CANONICAL)
    del canonical_value
    heap = C.prepare_heap([])
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    names: dict[int, str] = {}
    origins: dict[int, str] = {}
    for path, role in (
        (stdlib, "product-runtime"),
        (carrier, "compiler-carrier"),
        (INSPECT, "required-inspect"),
        (STRING_EXTRA, "required-string-extra"),
    ):
        PIPE.load_manifest_entries(
            heap, path, role, directory, macros, names, origins
        )
    vm = PIPE.PipelineVM(
        heap=heap,
        directory=directory,
        macro_symbols=macros,
        max_steps=10_000_000,
        code_names=names,
        abi_profile="dialect-v2",
        abi_ledger=PIPE.load(ABI),
    )
    form = vm._compiler_form_obj(C.parse_one(source))
    try:
        vm.run(directory[heap.intern("lcc-run")], [form])
    except PIPE.InstallBoundary as boundary:
        code = PIPE.decode_definition(heap, boundary.args[0], "trace-probe")
        return {
            "install_name": heap.obj_to_text(boundary.args[1]),
            "encoded_hex": code.encode().hex(),
            "payload_hex": code.payload.hex(),
            "nargs": code.nargs,
            "nlocals": code.nlocals,
            "flags": code.flags,
            "literal_count": len(code.littab),
            "literals": [heap.obj_to_text(value) for value in code.littab],
        }
    raise CaptureError("host replay did not reach install boundary")


def staged_object(bank4: bytes) -> dict[str, Any]:
    raw = bank4[STAGE_FILE_OFFSET:STAGE_FILE_OFFSET + STAGE_BYTES]
    require(len(raw) == STAGE_BYTES, "staged source outside captured Bank 4")
    require(raw[:4] == b"L65S" and raw[4:8] == bytes((4, 32, 32, 1)),
            "staged L65S header drift")
    require(u24(raw, 13) == STAGE_BYTES and raw[32:36] == b"SESS",
            "staged source length/session record drift")
    require(u24(raw, 40) == 64 and u16(raw, 43) == 20
            and u24(raw, 45) == 84 and u16(raw, 48) == 64,
            "staged code/metadata geometry drift")
    require(u32(raw, 18) == (zlib.crc32(raw[32:64]) & 0xFFFFFFFF)
            and u32(raw, 50) == (zlib.crc32(raw[64:84]) & 0xFFFFFFFF)
            and u32(raw, 54) == (zlib.crc32(raw[84:148]) & 0xFFFFFFFF)
            and u32(raw, 58) == (zlib.crc32(raw[64:148]) & 0xFFFFFFFF),
            "staged object CRC mismatch")
    code = raw[64:84]
    meta = raw[84:148]
    require(code[:7] == bytes.fromhex("b50100020b0001")
            and code[7:9] == b"\0\0"
            and code[9:] == bytes.fromhex("06003d13013b0b01010205"),
            "target code shape drift")
    require(meta[:24] == bytes.fromhex(
        "433249000218100800000100010018002800300010000000"),
        "target C2I header drift")
    entry = meta[24:40]
    descriptor = meta[40:48]
    strings = meta[48:64]
    require(descriptor == bytes.fromhex("080001000d000000"),
            "target literal descriptor drift")
    require(strings[:13] == b"\x0b\x00trace-probe"
            and strings[13:] == b"\x01\x00\xa0",
            "target string pool drift")
    return {
        "physical_address": "0x00046a00",
        "bytes": STAGE_BYTES,
        "sha256": sha(raw),
        "all_CRCs_valid": True,
        "code": {
            "bytes": len(code), "hex": code.hex(),
            "nargs": code[1], "nlocals": code[2], "flags": code[3],
            "payload_bytes": u16(code, 4), "literal_count": code[6],
            "payload_hex": code[9:].hex(),
            "decoded_prefix": [
                "PUSHLIT 0", "CALLPRIM symbol-value/1", "DROP"
            ],
            "decoded_body": ["PUSHARG0", "PUSHI8 1", "ADD", "RET"],
        },
        "metadata": {
            "bytes": len(meta), "entry_hex": entry.hex(),
            "literal_descriptor": {
                "kind": descriptor[0], "length": u16(descriptor, 2),
                "string_offset": u24(descriptor, 4),
                "hex": descriptor.hex(),
            },
            "strings": [
                {"offset": 0, "length": 11, "bytes": "trace-probe"},
                {"offset": 13, "length": 1, "hex": "a0",
                 "canonical_ASCII": False},
            ],
        },
    }


def append_state(bank0: bytes, truth: ElfTruth) -> dict[str, Any]:
    base = truth.symbol("lisp65_c2_phase_scratch").value
    raw = bank0[base:base + 304]
    require(len(raw) == 304, "phase scratch capture incomplete")
    append = stream(raw, 4)
    scalar_names = (
        "length", "code_off", "code_len", "meta_off", "meta_len",
        "entries", "literals", "roots", "old_images", "old_entries",
        "old_resolutions", "old_roots", "new_images", "new_entries",
        "new_resolutions", "new_roots",
    )
    scalars = {
        name: u16(raw, 50 + index * 2)
        for index, name in enumerate(scalar_names)
    }
    scalars["attic"] = u32(raw, 82)
    require(append["phase"] == 10 and append["finished"] == 0
            and append["error"] == 7,
            "append decoder no longer names phase-10 resolution failure")
    require(scalars == {
        "length": 148, "code_off": 64, "code_len": 20,
        "meta_off": 84, "meta_len": 64, "entries": 1,
        "literals": 1, "roots": 0, "old_images": 8,
        "old_entries": 771, "old_resolutions": 3351,
        "old_roots": 722, "new_images": 9, "new_entries": 772,
        "new_resolutions": 3352, "new_roots": 722, "attic": 0,
    }, "append scalar state drift")
    require(raw[238:241] == bytes((1, 0, 0)),
            "staged/committed/rollback flags drift")
    require(raw[302:304] == bytes((39, 128)),
            "locked cleanup trace drift")
    return {
        "decoder_context": append,
        "append_scalars": scalars,
        "staged": raw[238], "committed": raw[239],
        "rollback_rebuild_header": raw[240],
        "installer_trace": {
            "last_slot": raw[302], "flags": raw[303],
            "interpretation": (
                "locked completion/rollback provenance only; the preserved "
                "append decoder context, not slot 39, names the forward error"
            ),
        },
    }


def target_state(bank0: bytes, bank5: bytes, truth: ElfTruth) -> dict[str, Any]:
    def value(name: str, size: int | None = None) -> int:
        symbol = truth.symbol(name)
        width = size if size is not None else symbol.bytes
        return int.from_bytes(bank0[symbol.value:symbol.value + width], "little")

    runtime_at = truth.symbol("c2_runtime").value
    runtime = stream(bank0, runtime_at)
    scratch_at = truth.symbol("sym_name_scratch").value
    scratch = bank0[scratch_at:scratch_at + 34]
    require(scratch == b"\xa0" + b"\0" * 33,
            "sym_name_scratch no longer corroborates staged non-name")
    require(value("c2_journal_count") == 0 and value("vm_status", 1) == 0
            and value("mem_oom", 1) == 0 and value("gc_badobj") == 0
            and value("c2_phase_owner", 1) == 0
            and value("c2_ready", 1) == 1,
            "clean stopped-state exclusions drift")
    require(runtime["image_count"] == 8 and runtime["entry_count"] == 771
            and runtime["resolution_count"] == 3351
            and runtime["image_cursor"] == 722,
            "committed C2 runtime changed despite rollback")
    require(bank5[33840:33840 + 64] == b"\0" * 64,
            "C2J is not CLEAR")
    return {
        "committed_runtime": runtime,
        "c2_journal_count": value("c2_journal_count"),
        "C2J_CLEAR": True,
        "phase_owner": value("c2_phase_owner", 1),
        "vm_status_after_REPL_cleanup": value("vm_status", 1),
        "mem_oom": value("mem_oom", 1),
        "gc_badobj": value("gc_badobj"),
        "gc_runs": value("gc_runs"),
        "symbol_count": value("nsym"),
        "namepool_used": value("npool"),
        "sym_name_scratch_hex": scratch.hex(),
    }


def seam_facts() -> dict[str, Any]:
    emitter = EMITTER.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    symbol = SYMBOL.read_text(encoding="utf-8")
    dma = DMA.read_text(encoding="utf-8")
    mem = MEM.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")
    require("-DDISK_EXT_BASE=0x6900" in workbench,
            "actual Link-97 disk scratch base drift")
    require("ext_disk_put((uint16_t)(256u + at), value)" in emitter
            and "name = symname(value);" in emitter
            and "c2e_string_bytes(symname(value))" in emitter,
            "emitter name-consumption seam drift")
    require("sympool_read(off, sym_name_scratch" in symbol
            and "return sym_name_scratch;" in symbol,
            "symname scratch seam drift")
    require("c2_facade_c2_dma" in dma
            and "#ifdef LISP65_CODE_WINDOW_CONVERGENCE" in dma,
            "symbol-pool DMA conditional seam drift")
    require("obj     ext_a(uint16_t i)" in mem
            and "obj     ext_b(uint16_t i)" in mem
            and "#define ext_dma_read_or_abort(source, bank, destination, length)" in mem
            and "ext_dma((source), (bank), (uint16_t)(uintptr_t)(destination)" in mem,
            "EXT-heap immediate-return read seam drift")
    require("block[i] < 0x21u || block[i] > 0x7eu" in decoder,
            "canonical-name rejection seam drift")
    nm = subprocess.run(
        [str(ROOT / "tools/llvm-mos/bin/llvm-nm"), "-n", str(ELF)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(nm.returncode == 0, "cannot inspect Link-97 ELF symbols")
    names = nm.stdout.decode(errors="replace")
    require(" sympool_read" in names and " c2_facade_c2_dma" in names
            and " ext_a" in names and " ext_b" in names
            and " c2_facade_car" in names and " c2_facade_cdr" in names
            and "vm_code_load_converged" not in names
            and "c2_dma_read_or_abort" not in names,
            "Link-97 convergence/non-convergence identity drift")
    return {
        "disk_scratch_base": "0x6900",
        "emitter_stage_physical_address": "0x00046a00",
        "symname_contract": (
            "DMA Bank-5 namepool into shared Bank-0 scratch, then return scratch"
        ),
        "consumer_contract": (
            "c2e_add_name measures and copies returned scratch immediately"
        ),
        "EXT_heap_contract": (
            "compiler car/cdr reaches ext_a/ext_b, whose target read uses the "
            "same immediate-return DMA when convergence is absent"
        ),
        "target_ELF": {
            "sympool_read": True,
            "c2_facade_c2_dma": True,
            "ext_a_ext_b": True,
            "c2_facade_car_cdr": True,
            "content_convergence_owner": False,
        },
        "decoder_contract": "canonical symbol bytes must be 0x21..0x7e",
    }


def derive() -> dict[str, Any]:
    require((CAPTURE / "capture-complete").exists(), "capture completion absent")
    bank0 = (CAPTURE / "physical-bank0.bin").read_bytes()
    bank4 = (CAPTURE / "physical-bank4.bin").read_bytes()
    bank5 = (CAPTURE / "physical-bank5.bin").read_bytes()
    require((len(bank0), len(bank4), len(bank5)) == (65536, 27648, 50816),
            "capture range length drift")
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False,
    )
    registers = load(CAPTURE / "registers.json")
    expected_registers = {
        "A": "0xcf", "B": "0x00", "MAPH": "0x8000",
        "MAPL": "0x0000", "PC": "0xe004", "SP": "0x01d8",
        "X": "0xcf", "Y": "0x00", "Z": "0x00",
    }
    require({name: registers.get(name) for name in expected_registers}
            == expected_registers, "stopped register tuple drift")
    correct = host_compile(FORM)
    poisoned = host_compile(POISONED_FORM)
    require(correct == {
        "install_name": "trace-probe",
        "encoded_hex": "b50100020500000b01010205",
        "payload_hex": "0b01010205", "nargs": 1, "nlocals": 0,
        "flags": 2, "literal_count": 0, "literals": [],
    }, "correct host replay drift")
    require(poisoned == {
        "install_name": "trace-probe",
        "encoded_hex": "b50100020b00010c0006003d13013b0b01010205",
        "payload_hex": "06003d13013b0b01010205", "nargs": 1,
        "nlocals": 0, "flags": 2, "literal_count": 1,
        "literals": ["+"],
    }, "one-extra-plus host replay drift")
    staged = staged_object(bank4)
    require(staged["code"]["payload_hex"] == poisoned["payload_hex"],
            "target payload is no longer exact poisoned-form payload")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "capture": {
            "registers": registers,
            "CPU_remains_stopped": True,
            "device_stops": 1, "device_resumes": 0,
            "physical_reads": [
                bind(CAPTURE / "physical-bank0.bin"),
                bind(CAPTURE / "physical-bank4.bin"),
                bind(CAPTURE / "physical-bank5.bin"),
            ],
        },
        "append": append_state(bank0, truth),
        "staged_object": staged,
        "target_state": target_state(bank0, bank5, truth),
        "host_replay_after_both_requires": {
            "typed_form": correct,
            "one_extra_plus_form": poisoned,
            "target_payload_matches_one_extra_plus_form": True,
        },
        "read_completion_seam": seam_facts(),
        "conclusion": {
            "mechanism": (
                "content-consumed F018B reads return before their destination "
                "is independently known to contain the requested bytes"
            ),
            "observed_members": [
                (
                    "EXT-heap/compiler input: the target payload exactly matches "
                    "a body with one spurious standalone '+' expression"
                ),
                (
                    "Bank-5 symbol pool: symname returned 0xa0 for the one-byte "
                    "symbol and the emitter copied that non-name into valid-CRC C2I"
                ),
            ],
            "terminal_error": (
                "phase 10 rejects the 0xa0 symbol spelling with "
                "C2_STREAM_ERR_RESOLUTION; lcc-install surfaces VM_BADOPCODE"
            ),
            "slot39_correction": (
                "slot 39 is completion/rollback provenance in this unwind and "
                "does not name the original forward failure"
            ),
            "product_guard_behavior": "correct fail-closed rollback; no C2D commit",
            "F018B_family_membership": True,
            "fix_authorized": False,
            "next": (
                "owner disposition for the already designed content-defined "
                "completion primitive across every content-consumed F018B read"
            ),
        },
        "claim_limit": (
            "This capture proves the D2 failure mechanism and F018B family "
            "membership. It does not authorize a fix, relink, media rebuild, "
            "device resume, or continuation to D3-D5."
        ),
        "authority": {
            "desk_receipt": bind(DESK), "screen": bind(SCREEN),
            "ELF": bind(ELF), "canonical": bind(CANONICAL),
            "inspect": bind(INSPECT), "string_extra": bind(STRING_EXTRA),
            "emitter": bind(EMITTER), "decoder": bind(DECODER),
            "symbol": bind(SYMBOL), "DMA": bind(DMA),
            "DMA_header": bind(DMA_HEADER), "memory": bind(MEM),
            "workbench": bind(WORKBENCH),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "product_bytes_changed": 0, "links": 0, "WPLTO": 0,
            "device_contacts": 1, "device_stops": 1, "device_resumes": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "capture identity drift")
    append = value["append"]
    require(append["decoder_context"]["phase"] == 10
            and append["decoder_context"]["error"] == 7
            and append["staged"] == 1 and append["committed"] == 0,
            "phase-10 precommit boundary lost")
    staged = value["staged_object"]
    require(staged["all_CRCs_valid"] is True
            and staged["metadata"]["strings"][1] == {
                "offset": 13, "length": 1, "hex": "a0",
                "canonical_ASCII": False,
            }, "noncanonical staged name evidence lost")
    require(value["host_replay_after_both_requires"]
            ["target_payload_matches_one_extra_plus_form"] is True,
            "target/compiler poison identity lost")
    require(value["target_state"]["C2J_CLEAR"] is True
            and value["target_state"]["mem_oom"] == 0,
            "clean rollback/resource exclusion lost")
    require(value["read_completion_seam"]["target_ELF"]
            ["content_convergence_owner"] is False,
            "unprotected target seam lost")
    require(value["conclusion"]["F018B_family_membership"] is True
            and value["conclusion"]["fix_authorized"] is False,
            "family claim/fix boundary drift")
    require(value["capture"]["CPU_remains_stopped"] is True
            and value["execution_accounting"]["device_resumes"] == 0,
            "stopped-state discipline drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "move-decoder-phase": lambda x: x["append"]["decoder_context"].__setitem__("phase", 9),
        "erase-resolution-error": lambda x: x["append"]["decoder_context"].__setitem__("error", 0),
        "claim-commit": lambda x: x["append"].__setitem__("committed", 1),
        "normalize-symbol-byte": lambda x: x["staged_object"]["metadata"]["strings"].__setitem__(
            1, {"offset": 13, "length": 1, "hex": "2b", "canonical_ASCII": True}),
        "break-staged-CRC": lambda x: x["staged_object"].__setitem__("all_CRCs_valid", False),
        "lose-poisoned-form-match": lambda x: x["host_replay_after_both_requires"].__setitem__(
            "target_payload_matches_one_extra_plus_form", False),
        "invent-OOM": lambda x: x["target_state"].__setitem__("mem_oom", 1),
        "invent-convergence-owner": lambda x: x["read_completion_seam"]["target_ELF"].__setitem__(
            "content_convergence_owner", True),
        "withdraw-family-membership": lambda x: x["conclusion"].__setitem__(
            "F018B_family_membership", False),
        "silently-authorize-fix": lambda x: x["conclusion"].__setitem__("fix_authorized", True),
        "resume-after-capture": lambda x: x["capture"].__setitem__("CPU_remains_stopped", False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except CaptureError:
            rejected.append(name)
    require(rejected == list(cases), "capture result mutation survived")
    return rejected


def record() -> None:
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))


def check() -> None:
    observed = load(RECEIPT)
    expected = derive()
    expected["mutations_rejected"] = mutations(expected)
    require(observed == expected, "D2 BADOPCODE capture receipt stale")


def selftest() -> None:
    require(len(mutations(derive())) == 11, "capture mutation count drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    try:
        {"record": record, "check": check, "selftest": selftest}[args.action]()
    except (CaptureError, PIPE.PipelineError) as error:
        print(f"D2 BADOPCODE capture: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"D2 BADOPCODE capture: PASS action={args.action} status={STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
