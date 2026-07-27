#!/usr/bin/env python3
"""Compare the failed G5 writer with the proven C2-lite append writer.

This gate deliberately consumes linked ELF structure and bound hardware
receipts.  It does not infer instruction ownership from rendered disassembly.
The only byte matching is inside uniquely identified, sized ELF functions.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
G5_ELF = ROOT / "build/c2.2/canonical-media/autoboot.c65.elf"
G5_STAGER = ROOT / "build/c2.2/acceptance/r5/product/10-autoboot.c65"
PROVEN_PRODUCT_ELF = (
    ROOT / "build/c2.2/substitution/"
    "product-link-57-keymap-nullary-fast-path2/"
    "lisp65-c2-substitution-linked.prg.elf"
)
R5_PRODUCT_ELF = (
    ROOT / "build/c2.2/acceptance/r5/product/"
    "14-lisp65-c2-substitution-linked.prg.elf"
)
G5_HARDWARE_RECEIPT = (
    ROOT / "build/c2.2/acceptance/g5/session-03-write-only/"
    "hardware-receipt.json"
)
G5_LIVE_JOBS = (
    ROOT / "build/c2.2/acceptance/g5/session-03-write-only/"
    "stage-jobs-live.bin"
)
PRODUCT_HARDWARE_RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-latency-attempt2-"
    "hardware-presmoke.json"
)
OUTPUT = ROOT / "build/c2.2/acceptance/g5/dma-path-diff/receipt.json"

G5_ELF_SHA256 = (
    "b8843e93108834ce84733c753823248f728d90fe6b077e389950dab9f86589dd"
)
G5_STAGER_SHA256 = (
    "b541cdd7fa64e0c5e3279487a847379b75aafbca69910e6b53a1e59f68127434"
)
PROVEN_PRODUCT_ELF_SHA256 = (
    "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950"
)
R5_PRODUCT_ELF_SHA256 = (
    "e1bfc9e3a83abdc957bc6075b1c18f54456d5c31ea6ac6ebc36b0203878724a8"
)

# The failed standalone write from hardware session 03.
COUNT = 0x00FE
SOURCE = 0x0034BC
TARGET = 0x020000
READBACK = 0x0035BA


class DiffError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiffError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"bound artifact is absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"sized ELF symbol required: {name}")
    section = truth.section(symbol.section)
    offset = symbol.value - section.address
    data = truth.section_bytes(symbol.section)
    result = data[offset:offset + symbol.bytes]
    require(len(result) == symbol.bytes,
            f"symbol bytes leave section bounds: {name}")
    return result


def unique_offset(haystack: bytes, needle: bytes, label: str) -> int:
    offsets: list[int] = []
    start = 0
    while True:
        start = haystack.find(needle, start)
        if start < 0:
            break
        offsets.append(start)
        start += 1
    require(len(offsets) == 1,
            f"{label} must occur exactly once, found {offsets}")
    return offsets[0]


def symbolic_template(truth: ElfTruth, owner_name: str,
                      target_name: str) -> tuple[bytes, list[tuple[int, str, int]]]:
    owner = truth.symbol(owner_name)
    target = truth.symbol(target_name)
    result = bytearray(symbol_bytes(truth, owner_name))
    rows = sorted((
        row for row in truth.relocations
        if row.source_section_index == owner.section_index
        and owner.value <= row.offset < owner.value + owner.bytes
        and row.target_symbol_index == target.index),
        key=lambda row: (row.offset, row.relocation_type, row.addend))
    fingerprint = []
    for row in rows:
        relative = row.offset - owner.value
        width = 2 if row.relocation_type == "R_MOS_ADDR16" else 1
        require(relative >= 0 and relative + width <= len(result),
                "relocation leaves writer symbol")
        result[relative:relative + width] = b"\x00" * width
        fingerprint.append((relative, row.relocation_type, row.addend))
    return bytes(result), fingerprint


def f018b_job(command: int, source: int, target: int,
              count: int) -> bytes:
    return bytes((
        command,
        count & 0xFF, (count >> 8) & 0xFF,
        source & 0xFF, (source >> 8) & 0xFF, (source >> 16) & 0x0F,
        target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0x0F,
        0, 0, 0,
    ))


def main() -> int:
    for path, expected in (
            (G5_ELF, G5_ELF_SHA256),
            (G5_STAGER, G5_STAGER_SHA256),
            (PROVEN_PRODUCT_ELF, PROVEN_PRODUCT_ELF_SHA256),
            (R5_PRODUCT_ELF, R5_PRODUCT_ELF_SHA256)):
        require(sha256(path) == expected,
                f"linked comparison authority drift: {path}")

    g5 = ElfTruth.read(
        G5_ELF, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    product = ElfTruth.read(
        PROVEN_PRODUCT_ELF, llvm_readobj=LLVM_READOBJ,
        include_section_data=True)
    r5_product = ElfTruth.read(
        R5_PRODUCT_ELF, llvm_readobj=LLVM_READOBJ,
        include_section_data=True)

    g5_jobs = g5.symbol("c2_stage_jobs")
    g5_owner = g5.symbol("disk_record")
    require(
        g5_jobs.bytes == 40 and g5_jobs.section == ".bss"
        and g5_owner.bytes > 0 and g5_owner.section == ".text",
        "G5 linked writer symbol geometry drift")

    enhanced_trigger = bytes.fromhex(
        "a9018d03d7"      # EN018B=1
        "a9008d02d7"      # list bank 0
        "8d04d7"          # list megabyte 0
        f"a9{(g5_jobs.value >> 8) & 0xff:02x}8d01d7"
        f"a9{g5_jobs.value & 0xff:02x}8d05d7"
    )
    g5_trigger_offset = unique_offset(
        symbol_bytes(g5, "disk_record"), enhanced_trigger,
        "G5 Enhanced-DMA trigger")

    writer = product.symbol("c2_facade_target_c2_dma")
    dma_list = product.symbol("c2_dma_list")
    require(
        writer.bytes == 68
        and writer.section == ".lisp65_c2_kernal_window.reopen_gap2"
        and dma_list.bytes == 12 and dma_list.section == ".bss",
        "proven product writer symbol geometry drift")
    normal_trigger = bytes.fromhex(
        "a9008d02d7"
        f"a9{(dma_list.value >> 8) & 0xff:02x}8d01d7"
        f"a9{dma_list.value & 0xff:02x}8d00d7"
    )
    product_trigger_offset = unique_offset(
        symbol_bytes(product, "c2_facade_target_c2_dma"),
        normal_trigger, "product normal-DMA trigger")

    list_relocations = sorted((
        row for row in product.relocations
        if row.source_section_index == writer.section_index
        and writer.value <= row.offset < writer.value + writer.bytes
        and row.target_symbol_index == dma_list.index),
        key=lambda row: (row.offset, row.relocation_type, row.addend))
    require(
        sorted(row.addend for row in list_relocations
               if row.relocation_type == "R_MOS_ADDR16")
        == list(range(12)),
        "product writer does not bind all 12 F018B fields")
    split = product.resolve_split_address_binding(
        owner="c2_facade_target_c2_dma", target="c2_dma_list")
    append_edges = [
        row for row in product.relocations
        if row.source_section == ".lisp65_rt_c2append_stage_copy"
        and row.target == "c2_facade_c2_dma"
        and row.relocation_type == "R_MOS_ADDR16"
    ]
    require(len(append_edges) == 1,
            "real append stage-copy edge to DMA facade is not unique")
    r5_template, r5_fingerprint = symbolic_template(
        r5_product, "c2_facade_target_c2_dma", "c2_dma_list")
    proven_template, proven_fingerprint = symbolic_template(
        product, "c2_facade_target_c2_dma", "c2_dma_list")
    require(
        r5_template == proven_template
        and r5_fingerprint == proven_fingerprint
        and r5_product.symbol("c2_facade_target_c2_dma").section
        == writer.section
        and r5_product.symbol("c2_facade_target_c2_dma").bytes
        == writer.bytes,
        "R5 no longer retains the hardware-proven normal-DMA writer")

    plain_write = f018b_job(0x00, SOURCE, TARGET, COUNT)
    chained_write = f018b_job(0x04, SOURCE, TARGET, COUNT)
    plain_readback = f018b_job(0x00, TARGET, READBACK, COUNT)
    enhanced_options = bytes.fromhex("0b80008100850100")
    g5_hardware = json.loads(
        G5_HARDWARE_RECEIPT.read_text(encoding="utf-8"))
    require(
        g5_hardware["status"]
        == "first-red-standalone-write-never-visible"
        and G5_LIVE_JOBS.read_bytes()
        == enhanced_options + plain_write
        + enhanced_options + plain_readback,
        "G5 hardware failure receipt no longer proves the compared job")
    product_hardware = json.loads(
        PRODUCT_HARDWARE_RECEIPT.read_text(encoding="utf-8"))
    require(
        product_hardware["status"]
        == "pass-receipt-less-hardware-presmoke-latency-healing-green"
        and product_hardware["rows"]["definition_first_call_nullary"][
            "status"] == "pass"
        and product_hardware["rows"]["freezer_identity"]["status"] == "pass",
        "product hardware receipt no longer proves append execution")

    report = {
        "format": "lisp65-c2-lite-g5-dma-path-diff-v1",
        "status": "first-red-g5-private-enhanced-dma-transport",
        "claim_limit": (
            "Acceptance-tool attribution only. This does not alter product "
            "bytes and does not claim that Enhanced DMA is generally broken. "
            "It proves that G5 used a different, hardware-failing transport "
            "interface for the Bank-0-to-Bank-2 edge already proven through "
            "the product's normal F018B/D700 writer."
        ),
        "bindings": {
            "g5_stager": bind(G5_STAGER),
            "g5_stager_elf": bind(G5_ELF),
            "g5_write_only_hardware": bind(G5_HARDWARE_RECEIPT),
            "g5_live_jobs": bind(G5_LIVE_JOBS),
            "hardware_proven_product_elf": bind(PROVEN_PRODUCT_ELF),
            "r5_product_elf": bind(R5_PRODUCT_ELF),
            "product_append_hardware": bind(PRODUCT_HARDWARE_RECEIPT),
        },
        "structured_elf": {
            "g5": {
                "jobs_symbol": asdict(g5_jobs),
                "trigger_owner": asdict(g5_owner),
                "trigger_offset_in_owner": g5_trigger_offset,
                "trigger_vma": g5_owner.value + g5_trigger_offset,
                "trigger_bytes": enhanced_trigger.hex(),
            },
            "product": {
                "list_symbol": asdict(dma_list),
                "writer_symbol": asdict(writer),
                "trigger_offset_in_owner": product_trigger_offset,
                "trigger_vma": writer.value + product_trigger_offset,
                "trigger_bytes": normal_trigger.hex(),
                "list_field_relocations": [
                    asdict(row) for row in list_relocations],
                "list_address_binding": split,
                "append_stage_copy_edge": asdict(append_edges[0]),
                "r5_writer_equivalence": {
                    "status": "same-symbolic-function-and-relocation-schema",
                    "r5_list_vma": r5_product.symbol("c2_dma_list").value,
                    "hardware_proven_list_vma": dma_list.value,
                    "symbolic_template_sha256": hashlib.sha256(
                        proven_template).hexdigest(),
                    "relocation_fingerprint": [
                        {
                            "relative_offset": offset,
                            "type": kind,
                            "addend": addend,
                        }
                        for offset, kind, addend in proven_fingerprint
                    ],
                },
            },
        },
        "field_diff": [
            {
                "field": "F018B mode",
                "g5": "$D703 := 1 immediately before trigger",
                "product": (
                    "consumes established F018B mode; normal list shape "
                    "is structurally bound"
                ),
                "classification": "same-list-format-intent",
            },
            {
                "field": "per-job representation",
                "g5": "8-byte Enhanced option prefix + 12-byte F018B job",
                "product": "12-byte F018B job",
                "classification": "material-difference",
            },
            {
                "field": "trigger",
                "g5": "$D705 Enhanced trigger",
                "product": "$D700 normal trigger",
                "classification": "material-difference",
            },
            {
                "field": "list bank/address",
                "g5": f"$00:{g5_jobs.value:04x}",
                "product": f"$00:{dma_list.value:04x}",
                "classification": "storage-only",
            },
            {
                "field": "command/count/source/target/modulo",
                "g5": plain_write.hex(),
                "product": plain_write.hex(),
                "classification": "byte-identical",
            },
            {
                "field": "ordered readback",
                "g5": (
                    f"{enhanced_options.hex()}{chained_write.hex()} + "
                    f"{enhanced_options.hex()}{plain_readback.hex()}"
                ),
                "product": "not part of the proven single-write seam",
                "classification": "acceptance-only-extension",
            },
        ],
        "conclusion": {
            "dead_job_payload_fields": "byte-identical-to-product-F018B-shape",
            "only_material_transport_difference": (
                "G5 D705 Enhanced/options interface versus product D700 "
                "normal F018B interface"
            ),
            "root_cause_class": (
                "G5 acceptance tooling reimplemented a second private DMA "
                "transport truth instead of consuming the proven product seam"
            ),
            "required_tool_fix": (
                "Represent the immutable write/readback chain as two "
                "contiguous 12-byte F018B jobs and trigger it through D700."
            ),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "receipt": OUTPUT.relative_to(ROOT).as_posix(),
        "material_difference": (
            "D705+options versus D700+12-byte-F018B"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
