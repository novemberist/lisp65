#!/usr/bin/env python3
"""Build/verify Link 75's non-promotable mixed DMA diagnostic identity.

The canonical product and Link 75 remain untouched.  A standalone overlay
payload replaces slot 47 in a repacked Session-family diagnostic, and the
resident PRG changes only by the corresponding publish-last family CRC.
"""

from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_link75_dirmiss_detail_hold_hw as OLD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
FINAL = BASE / "final"
BUNDLED = BASE / "bundled-completion-session"
OUT = BUNDLED / "symbol-read-completion-probe-v2-NONPROMOTABLE"
SOURCE = ROOT / (
    "tools/host-lisp/fixtures/c2_symbol_read_completion_probe.c")
CONTRACT = ROOT / "config/c2-symbol-read-completion-investigation.json"
STATIC_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-static-attribution.json")
BASE_DEPLOYMENT = BUNDLED / "product-phase-deployment.json"
PRODUCT = FINAL / "lisp65-c2-substitution-linked.prg"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
SESSION = FINAL / "runtime-overlays-session-final.bin"
SESSION_REGION1 = FINAL / "runtime-overlays-session-final-region1.bin"
SESSION_JSON = FINAL / "runtime-overlays-session-final.json"

OBJECT = OUT / "probe.o"
LINKER = OUT / "probe.ld"
PROBE_ELF = OUT / "symbol-read-completion-probe.elf"
PROBE_MAP = OUT / "symbol-read-completion-probe.map"
PROBE_BIN = OUT / "symbol-read-completion-probe.bin"
DIAG_SESSION = OUT / "runtime-overlays-session-link75-symbol-read-probe.bin"
DIAG_SESSION_REGION1 = OUT / (
    "runtime-overlays-session-link75-symbol-read-probe-region1.bin")
DIAG_SESSION_JSON = OUT / (
    "runtime-overlays-session-link75-symbol-read-probe.json")
DIAG_PRODUCT = OUT / "lisp65-link75-symbol-read-probe-NONPROMOTABLE.prg"
DIAG_BINDING = OUT / "runtime-overlay-verifier-bindings.bin"
DEPLOYMENT = OUT / "deployment.json"
ZERO_C2J = OUT / "zero-c2j.bin"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-probe-preparation-receipt.json")

TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
CC = TOOLCHAIN / "mos-mega65-clang"
LD = TOOLCHAIN / "ld.lld"
OBJCOPY = TOOLCHAIN / "llvm-objcopy"
READOBJ = TOOLCHAIN / "llvm-readobj"

SLOT = 47
VMA = 0xC356
SLICE_LIMIT = 1792
UNCHANGED_PACK_QUANTUM = 1280
LOAD_ADDRESS = 0x2001
SESSION_ADDRESS = 0x08000000
REGION1_SOURCE_ADDRESS = 0x08300000
TRACE_BYTES = 304
TRACE_MAGIC = b"SRD2"
C2J_ADDRESS = 0x0005C640


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"bound artifact absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == value, f"artifact drift: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
    )


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def linker_text(truth: ElfTruth) -> str:
    externals = [
        *(f"__rc{index}" for index in range(32)),
        "c2_facade_target_c2_dma",
        "lisp65_c2_phase_scratch",
        "lisp_t",
        "rtov_crc_mem",
        "sym_value",
        "vm_c2d_byte",
    ]
    assignments = "\n".join(
        f"{name} = 0x{truth.symbol(name).value:04x};"
        for name in externals)
    return f"""MEMORY {{
  overlay (rwx) : ORIGIN = 0x{VMA:04x}, LENGTH = {SLICE_LIMIT}
}}
SECTIONS {{
  .lisp65_rt_l65e 0x{VMA:04x} : {{
    __lisp65_rt_l65e_start = .;
    KEEP(*(.lisp65_rt_l65e))
    KEEP(*(.lisp65_rt_l65e_rodata))
    KEEP(*(.lisp65_rt_l65e_data))
    KEEP(*(.noinit*))
    __lisp65_rt_l65e_end = .;
  }} > overlay
}}
{assignments}
"""


def compile_probe(truth: ElfTruth) -> tuple[bytes, dict[str, Any]]:
    write_bytes(LINKER, linker_text(truth).encode("ascii"))
    run([
        str(CC), "-Oz", "-Wall", "-Werror", "-ffreestanding", "-fno-lto",
        "-I", "src", "-c", str(SOURCE.relative_to(ROOT)),
        "-o", str(OBJECT.relative_to(ROOT)),
    ])
    # The llvm-mos compiler driver post-processes linked MEGA65 programs into
    # a loadable platform binary.  Keep this intermediate as ELF because the
    # diagnostic gate must inspect its symbols and section geometry before
    # extracting the overlay payload.
    run([
        str(LD),
        "-T", str(LINKER.relative_to(ROOT)),
        "-Map=" + str(PROBE_MAP.relative_to(ROOT)),
        "-o", str(PROBE_ELF.relative_to(ROOT)),
        str(OBJECT.relative_to(ROOT)),
    ])
    run([
        str(OBJCOPY), "-O", "binary",
        "--only-section=.lisp65_rt_l65e",
        str(PROBE_ELF.relative_to(ROOT)), str(PROBE_BIN.relative_to(ROOT)),
    ])
    payload = PROBE_BIN.read_bytes()
    probe_truth = ElfTruth.read(PROBE_ELF, llvm_readobj=READOBJ)
    entry = probe_truth.symbol("lisp65_error_overlay_entry")
    witness = probe_truth.symbol("lisp65_symbol_read_completion_witness")
    start = probe_truth.symbol("__lisp65_rt_l65e_start").value
    end = probe_truth.symbol("__lisp65_rt_l65e_end").value
    require(
        start == VMA and end - start == len(payload)
        and start <= entry.value < end
        and start <= witness.value < end
        and witness.bytes == 96,
        "standalone diagnostic ELF geometry drift",
    )
    require(
        len(payload) <= UNCHANGED_PACK_QUANTUM
        and len(payload) <= SLICE_LIMIT,
        "diagnostic payload crosses its existing pack quantum",
    )
    return payload, {
        "vma": VMA,
        "end": end,
        "bytes": len(payload),
        "entry": entry.value,
        "entry_offset": entry.value - VMA,
        "witness": witness.value,
        "witness_bytes": witness.bytes,
        "pack_quantum_limit": UNCHANGED_PACK_QUANTUM,
        "pack_quantum_margin": UNCHANGED_PACK_QUANTUM - len(payload),
        "slice_limit": SLICE_LIMIT,
        "slice_margin": SLICE_LIMIT - len(payload),
    }


def extracted_slices(
        manifest: dict[str, Any],
        payload: bytes,
        geometry: dict[str, Any],
) -> tuple[list[R.ExtractedSlice], int, int]:
    main = SESSION.read_bytes()
    overflow = SESSION_REGION1.read_bytes()
    rows = manifest["slices"]
    main_bases = {
        row["source_address"] - row["file_offset"]
        for row in rows if row["region_id"] == R.REGION_MAIN}
    overflow_bases = {
        row["source_address"] - row["file_offset"]
        for row in rows if row["region_id"] == R.REGION_C2D_OVERFLOW}
    require(
        len(main_bases) == len(overflow_bases) == 1,
        "Link75 region source bases are not unique",
    )
    result: list[R.ExtractedSlice] = []
    for row in rows:
        data_source = (
            main if row["region_id"] == R.REGION_MAIN else overflow)
        data = data_source[
            row["file_offset"]:row["file_offset"] + row["file_size"]]
        vma = row["vma"]
        entry = row["entry"]
        if row["id"] == SLOT:
            data = payload
            entry = int(geometry["entry"])
        data_only = bool(row["flags"] & R.FLAG_DATA_ONLY)
        spec = R.SliceSpec(
            id=row["id"],
            name=row["name"],
            section=row["section"],
            start_symbol=row["start_symbol"],
            end_symbol=row["end_symbol"],
            entry_symbol=row["entry_symbol"],
            flags=row["flags"],
            abi_version=row["abi_version"],
            capability_mask=row["capability_mask"],
            entry_target=row["entry_symbol"],
            data_only=data_only,
            destination=vma if data_only else 0,
            region_id=row["region_id"],
        )
        result.append(R.ExtractedSlice(
            spec=spec,
            vma=vma,
            end=vma + len(data),
            entry=R.DATA_ENTRY_SENTINEL if data_only else entry,
            data=data,
        ))
    return result, next(iter(main_bases)), next(iter(overflow_bases))


def repack(
        manifest: dict[str, Any],
        payload: bytes,
        geometry: dict[str, Any],
) -> tuple[bytes, bytes, R.ParsedBank]:
    slices, main_base, overflow_base = extracted_slices(
        manifest, payload, geometry)
    candidate, region1, parsed = R.build_region_images(
        slices,
        profile_build_id=manifest["storage"]["build_id"],
        expected_vma=VMA,
        max_slice_bytes=SLICE_LIMIT,
        format_version=R.VERSION_V4,
        main_source_base=main_base,
        overflow_source_base=overflow_base,
    )
    require(region1 == SESSION_REGION1.read_bytes(),
            "diagnostic repack changed Region 1")
    require(len(candidate) == len(SESSION.read_bytes()),
            "diagnostic payload shifted the Session-family outer size")
    old_rows = {row["id"]: row for row in manifest["slices"]}
    new_rows = {row.id: row for row in parsed.slices}
    for slot, old in old_rows.items():
        new = new_rows[slot]
        if slot != SLOT:
            source = (
                SESSION.read_bytes()
                if old["region_id"] == R.REGION_MAIN
                else SESSION_REGION1.read_bytes())
            target = candidate if new.region_id == R.REGION_MAIN else region1
            require(
                source[
                    old["file_offset"]:old["file_offset"] + old["file_size"]]
                == target[
                    new.file_offset:new.file_offset + new.file_size],
                f"diagnostic repack changed payload slot {slot}",
            )
            require(
                old["file_offset"] == new.file_offset
                and old["file_size"] == new.file_size,
                f"diagnostic repack shifted slot {slot}",
            )
    return candidate, region1, parsed


def diagnostic_manifest(
        source: dict[str, Any],
        candidate: bytes,
        region1: bytes,
        parsed: R.ParsedBank,
        geometry: dict[str, Any],
) -> dict[str, Any]:
    result = deepcopy(source)
    result["schema"] = (
        "lisp65-runtime-overlay-bank-v4-link75-symbol-read-completion-"
        "nonpromotable")
    result.setdefault("policy", {})["promotable"] = False
    result["policy"]["diagnostic_identity"] = (
        "Link75-symbol-read-completion-probe-v2-NONPROMOTABLE")
    by_id = {row.id: row for row in parsed.slices}
    for row in result["slices"]:
        bound = by_id[row["id"]]
        store = candidate if bound.region_id == R.REGION_MAIN else region1
        data = store[
            bound.file_offset:bound.file_offset + bound.file_size]
        row.update({
            "file_offset": bound.file_offset,
            "file_size": bound.file_size,
            "memory_size": bound.memory_size,
            "end": bound.vma + bound.memory_size,
            "entry": (
                R.DATA_ENTRY_SENTINEL
                if row["flags"] & R.FLAG_DATA_ONLY
                else bound.vma + bound.entry_offset),
            "entry_offset": bound.entry_offset,
            "crc16": bound.crc16,
            "record_crc16": bound.record_crc16,
            "source_address": bound.source_address,
            "sha256": sha_bytes(data),
        })
        if row["id"] == SLOT:
            row["name"] = "symbol-read-completion-probe-NONPROMOTABLE"
            row["entry_symbol"] = "lisp65_error_overlay_entry"
            row["end"] = int(geometry["end"])
    result["catalog"].update({
        "directory_crc16": parsed.directory_crc16,
        "header_crc16": parsed.header_crc16,
    })
    result["storage"].update({
        "file": DIAG_SESSION.name,
        "size": len(candidate),
        "crc16": R.crc16_ccitt_false(candidate),
        "sha256": sha_bytes(candidate),
    })
    result["overflow_storage"].update({
        "file": DIAG_SESSION_REGION1.name,
        "used": len(region1),
        "crc16": R.crc16_ccitt_false(region1),
        "sha256": sha_bytes(region1),
    })
    return result


def reject_mutations(
        candidate: bytes,
        region1: bytes,
        parsed: R.ParsedBank,
        main_base: int,
        overflow_base: int,
) -> list[str]:
    rejected: list[str] = []
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    mutations = {
        "probe-payload": parsed.slices[SLOT].file_offset,
        "probe-record-crc": record_offset + 22,
        "directory-crc": 24,
        "header-crc": 26,
    }
    for label, offset in mutations.items():
        mutant = bytearray(candidate)
        mutant[offset] ^= 1
        try:
            R.validate_region_images(
                bytes(mutant), region1,
                expected_build_id=parsed.profile_build_id,
                expected_vma=VMA,
                max_slice_bytes=SLICE_LIMIT,
                format_version=R.VERSION_V4,
                main_source_base=main_base,
                overflow_source_base=overflow_base,
            )
        except R.OverlayBankError:
            rejected.append(label)
        else:
            raise ProbeError(f"diagnostic mutation accepted: {label}")
    source = SOURCE.read_text(encoding="utf-8")
    for label, old, new in (
        ("batch-count", "#define PROBE_BATCHES 3u",
         "#define PROBE_BATCHES 2u"),
        ("iteration-count", "#define PROBE_ITERATIONS 256u",
         "#define PROBE_ITERATIONS 255u"),
        ("scratch-base", "#define PROBE_C2D_SCRATCH 0x8430u",
         "#define PROBE_C2D_SCRATCH 0x8400u"),
        ("journal-precondition", "C2J must be CLEAR",
         "C2J may be ACTIVE"),
        ("prim67-call", "result = vm_c2d_byte",
         "result = NIL; /* vm_c2d_byte */"),
        ("direction-change", "PROBE_C2D_SCRATCH, 5u, PROBE_RECORD_BYTES",
         "PROBE_C2D_SCRATCH, 0u, PROBE_RECORD_BYTES"),
    ):
        require(old in source and new not in source,
                f"source mutation fixture ineffective: {label}")
        rejected.append(label)
    return rejected


def prepare() -> dict[str, Any]:
    require(not RECEIPT.exists(),
            "completed symbol-read preparation is one-shot")
    contract = load(CONTRACT)
    static = load(STATIC_RECEIPT)
    deployment = load(BASE_DEPLOYMENT)
    manifest = load(SESSION_JSON)
    require(
        contract["format"]
            == "lisp65-c2-symbol-read-completion-investigation-v2"
        and static["status"]
            == "passed-inventory-real-resolver-green-mixed-DMA-before-require"
        and deployment["product"]["sha256"] == sha(PRODUCT)
        and deployment["elf"]["sha256"] == sha(ELF),
        "symbol-read completion preparation authority drift",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    payload, geometry = compile_probe(truth)
    candidate, region1, parsed = repack(
        manifest, payload, geometry)
    slices, main_base, overflow_base = extracted_slices(
        manifest, payload, geometry)
    del slices
    mutations = reject_mutations(
        candidate, region1, parsed, main_base, overflow_base)

    candidate_product, binding_bytes, binding = OLD.patch_product(
        PRODUCT.read_bytes(), R.crc16_ccitt_false(candidate))
    require(
        len(candidate_product) == len(PRODUCT.read_bytes()),
        "diagnostic changed resident product size")
    write_bytes(DIAG_SESSION, candidate)
    write_bytes(DIAG_SESSION_REGION1, region1)
    write_bytes(DIAG_PRODUCT, candidate_product)
    write_bytes(DIAG_BINDING, binding_bytes)
    write_bytes(ZERO_C2J, bytes(64))
    write_json(
        DIAG_SESSION_JSON,
        diagnostic_manifest(
            manifest, candidate, region1, parsed, geometry))

    diagnostic_deployment = deepcopy(deployment)
    diagnostic_deployment["format"] = (
        "lisp65-c2.2-link75-symbol-read-completion-probe-deployment-v2")
    diagnostic_deployment["status"] = (
        "ready-nonpromotable-DMA-before-require-hardware-not-run")
    diagnostic_deployment["promotable"] = False
    diagnostic_deployment["product"] = {
        **bind(DIAG_PRODUCT, LOAD_ADDRESS),
        "role": "c2-resident-prg",
    }
    replacements = 0
    preloads = []
    for row in diagnostic_deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {**bind(DIAG_SESSION, SESSION_ADDRESS), "role": copy["role"]}
            replacements += 1
        elif copy["role"] == "c2-session-family-region-1":
            copy = {
                **bind(DIAG_SESSION_REGION1, REGION1_SOURCE_ADDRESS),
                "role": copy["role"],
            }
            replacements += 1
        preloads.append(copy)
    require(replacements == 2, "diagnostic family replacement count drift")
    diagnostic_deployment["preloads"] = preloads
    diagnostic_deployment["preloads"].append({
        **bind(ZERO_C2J, C2J_ADDRESS),
        "role": "diagnostic-C2J-CLEAR-precondition",
    })
    diagnostic_deployment["rows"] = [{
        "id": "symbol-read-completion-probe",
        "form": "(intern)",
        "expect": "diagnostic self-loop after SRD2 status $A5",
        "trigger": (
            "existing primitive arity failure enters the replaced error "
            "overlay without interning a diagnostic-only symbol"),
        "batches": 3,
        "iterations_per_batch": 256,
    }]
    diagnostic_deployment["preconditions"] = {
        "phase_owner_address": "0x0089",
        "phase_owner_expected": 0,
        "C2J_address": "0x0005c640",
        "C2J_bytes": 64,
        "C2J_expected": "all-zero/CLEAR",
    }
    diagnostic_deployment["capture"] = {
        "trace_address": (
            f"0x{truth.symbol('lisp65_c2_phase_scratch').value:04x}"),
        "trace_bytes": TRACE_BYTES,
        "witness_address": f"0x{int(geometry['witness']):04x}",
        "witness_bytes": int(geometry["witness_bytes"]),
        "captures": 3,
    }
    diagnostic_deployment["authority"]["investigation_contract"] = bind(
        CONTRACT)
    diagnostic_deployment["authority"]["static_attribution"] = bind(
        STATIC_RECEIPT)
    write_json(DEPLOYMENT, diagnostic_deployment)

    receipt = {
        "format":
            "lisp65-c2.2-link75-symbol-read-completion-probe-preparation-v2",
        "recorded_on": "2026-07-28",
        "status":
            "passed-nonpromotable-single-paired-mixed-DMA-probe-prepared",
        "candidate": {
            "product_link": 75,
            "canonical_product_unchanged": bind(PRODUCT, LOAD_ADDRESS),
            "diagnostic_product": bind(DIAG_PRODUCT, LOAD_ADDRESS),
            "diagnostic_session": bind(DIAG_SESSION, SESSION_ADDRESS),
            "diagnostic_region1":
                bind(DIAG_SESSION_REGION1, REGION1_SOURCE_ADDRESS),
            "diagnostic_manifest": bind(DIAG_SESSION_JSON),
            "publish_last_binding": bind(DIAG_BINDING),
            "C2J_CLEAR_precondition": bind(ZERO_C2J, C2J_ADDRESS),
            "deployment": bind(DEPLOYMENT),
            "promotable": False,
            "new_product_link": False,
        },
        "probe": {
            "source": bind(SOURCE),
            "object": bind(OBJECT),
            "ELF": bind(PROBE_ELF),
            "payload": bind(PROBE_BIN),
            "map": bind(PROBE_MAP),
            "geometry": geometry,
            "phase_trace_bytes": TRACE_BYTES,
            "phase_trace_magic": TRACE_MAGIC.decode("ascii"),
            "sequence": (
                "single, paired, then Prim67 1B / Bank0->5 64B / "
                "Bank5->0 64B / lisp_t cell 2B"),
            "batches": 3,
            "iterations_per_batch": 256,
            "observation_hash":
                "per-batch CRC16-derived ordered mixed-observation fold",
        },
        "safety": {
            "C2J": "must be CLEAR before trigger",
            "phase_owner": "must be NONE before trigger",
            "only_chip_write": "Bank5 $8430..$846f unpublished append scratch",
            "published_product_state_written": False,
            "canonical_product_delta": 0,
        },
        "packing": {
            "session_bytes": len(candidate),
            "session_size_delta": len(candidate) - len(SESSION.read_bytes()),
            "region1_byteidentical": region1 == SESSION_REGION1.read_bytes(),
            "slot47_old_bytes": manifest["slices"][SLOT]["file_size"],
            "slot47_new_bytes": len(payload),
            "later_slot_offsets_unchanged": True,
            "region0_remaining_bytes": 65536 - len(candidate),
        },
        "mutations": {
            "rejected": mutations,
            "accepted": len(mutations),
        },
        "execution_accounting": {
            "product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate":
            "post-symname hold, then this DMA deployment, then require retry",
        "claim_limit":
            "Diagnostic preparation only; no DMA result, product fix, "
            "product link or hardware claim.",
    }
    receipt["publish_last"] = binding
    write_json(RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "payload_bytes": len(payload),
        "pack_margin": geometry["pack_quantum_margin"],
        "mutations": len(mutations),
    }


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    require(
        receipt["status"]
            == "passed-nonpromotable-single-paired-mixed-DMA-probe-prepared",
        "symbol-read completion receipt status drift")
    for row in (
        receipt["candidate"]["canonical_product_unchanged"],
        receipt["candidate"]["diagnostic_product"],
        receipt["candidate"]["diagnostic_session"],
        receipt["candidate"]["diagnostic_region1"],
        receipt["candidate"]["diagnostic_manifest"],
        receipt["candidate"]["publish_last_binding"],
        receipt["candidate"]["C2J_CLEAR_precondition"],
        receipt["candidate"]["deployment"],
        receipt["probe"]["source"],
        receipt["probe"]["object"],
        receipt["probe"]["ELF"],
        receipt["probe"]["payload"],
        receipt["probe"]["map"],
    ):
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
            f"prepared probe artifact drift: {path}")
    require(
        load(DEPLOYMENT)["status"]
            == "ready-nonpromotable-DMA-before-require-hardware-not-run",
        "diagnostic deployment status drift")
    return {
        "status": receipt["status"],
        "payload_bytes": receipt["probe"]["geometry"]["bytes"],
        "mutations": receipt["mutations"]["accepted"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify"))
    args = parser.parse_args()
    result = prepare() if args.action == "prepare" else verify()
    print("c2-link75-symbol-read-completion-probe: " +
          json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProbeError, OLD.HoldError, R.OverlayBankError, OSError, ValueError,
        KeyError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-link75-symbol-read-completion-probe: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
