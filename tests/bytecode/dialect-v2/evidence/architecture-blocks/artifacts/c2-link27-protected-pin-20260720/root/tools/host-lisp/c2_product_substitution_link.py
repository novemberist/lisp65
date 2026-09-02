#!/usr/bin/env python3
"""Build the first real C2 product-substitution link, stopping on first red."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "build/c2.2/substitution/product-link"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
PROFILE = "c2-product-substitution-v1"
RUNTIME_VMA = "0xc356"
KERNAL_WINDOW_STAGE = 0x087FE000
KERNAL_WINDOW_BASE = 0xE000
KERNAL_WINDOW_BYTES = 0x2000
RUNTIME_LOAD_BASE = 0x010000
RUNTIME_LOAD_BYTES = 0x020000
KERNAL_WINDOW_LOAD_BASE = 0x040000
HOST_FACADE_BASE = 0xB5A2
HOST_FACADE_STRIDE = 3
FIXED_ZP_BASE = 0x89
FIXED_ZP_BYTES = 7
FIXED_BANK0_BASE = 0xC080
FIXED_BANK0_BYTES = 408
FIXED_BANK0_CODE_BASE = 0xC218
FIXED_BANK0_CODE_BYTES = 45
FIXED_BANK0_HEADROOM_BYTES = 273
SESSION_EMITTER_STATE_BYTES = 346
VERIFIER_BINDING_SECTION = ".lisp65_runtime_overlay_verifier_bindings"
VERIFIER_BINDING_BYTES = 32
VERIFIER_BINDING_SENTINELS = (
    0xA100, 0xA101, 0xA102, 0xA103,
    0xA110, 0xA111, 0xA112, 0xA113,
    0xB100, 0xB101, 0xB102, 0xB103,
    0xB110, 0xB111, 0xB112, 0xB113,
)
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
HOST_FACADE_SYMBOLS = (
    "c2_facade_vm_code_load",
    "c2_facade_c2_dma",
    "c2_facade_overlay_call_family",
    "c2_facade_c2e_cons",
    "c2_facade_c2e_overlay",
    "c2_facade_car",
    "c2_facade_cdr",
    "c2_facade_gc_collect",
    "c2_facade_str_open",
    "c2_facade_str_putc",
    "c2_facade_intern",
    "c2_facade_select_family",
    "c2_facade_gc_mark",
)
ORPHAN_ALLOWLIST = (
    ".comment",
    ".symtab",
    ".strtab",
    ".shstrtab",
    ".lisp65_error_callsites",
)

LEGACY_C = {
    "attic_library_shelf.c",
    "c1_compiler_overlay.c",
    "c1_phase_probe.c",
    "l65m_commit_overlay.c",
    "l65m_validate.c",
    "lcc_install_overlay.c",
    "vm_boot_fastpath.c",
    "vm_embed.c",
    "c2_product_decoder.c",
}

C2_PHASE_SOURCES = [
    ROOT / "scripts/c2-stream-init.c",
    ROOT / "scripts/c2-stream-phase-00.c",
    ROOT / "scripts/c2-stream-phase-00b.c",
    ROOT / "scripts/c2-stream-phase-01.c",
    ROOT / "scripts/c2-stream-phase-02a.c",
    ROOT / "scripts/c2-stream-phase-02b.c",
    ROOT / "scripts/c2-stream-phase-03.c",
    ROOT / "scripts/c2-stream-phase-04.c",
    ROOT / "scripts/c2-stream-phase-05.c",
    ROOT / "scripts/c2-stream-phase-06a.c",
    ROOT / "scripts/c2-stream-phase-06b.c",
    ROOT / "scripts/c2-stream-v2-phase-07.c",
    ROOT / "scripts/c2-stream-v2-phase-08.c",
    ROOT / "scripts/c2-stream-v2-phase-09.c",
    ROOT / "scripts/c2-stream-v2-phase-10.c",
    ROOT / "scripts/c2-stream-v2-phase-11.c",
    ROOT / "scripts/c2-stream-v2-phase-12.c",
    ROOT / "scripts/c2-stream-v2-phase-13.c",
]

C2_DECODER_SLICES = [
    ("00", "c2_stream_phase_00"),
    ("00b", "c2_stream_phase_00b"),
    ("01", "c2_stream_phase_01"),
    ("02a", "c2_stream_phase_02a"),
    ("02b", "c2_stream_phase_02b"),
    ("03", "c2_stream_phase_03"),
    ("04", "c2_stream_phase_04"),
    ("05", "c2_stream_phase_05"),
    ("06a", "c2_stream_phase_06a"),
    ("06b", "c2_stream_phase_06b"),
    ("07", "c2_stream_phase_07"),
    ("08", "c2_stream_phase_08"),
    ("09", "c2_stream_phase_09"),
    ("10", "c2_stream_phase_10"),
    ("11", "c2_stream_phase_11"),
    ("12", "c2_stream_phase_12"),
    ("13", "c2_stream_phase_13"),
]

C2_EMITTER_SLICES = [
    ("prepare", "c2_session_emit_prepare_phase"),
    ("name", "c2_session_emit_name_phase"),
    ("literal_prep", "c2_session_emit_literal_prep_phase"),
    ("literal_atom", "c2_session_emit_literal_atom_phase"),
    ("literal_append", "c2_session_emit_literal_append_phase"),
    ("code", "c2_session_emit_code_phase"),
    ("final_meta", "c2_session_emit_final_meta_phase"),
    ("final_crc", "c2_session_emit_final_crc_phase"),
]

C2_APPEND_SLICES = [
    ("envelope", "c2_append_envelope_phase"),
    ("crc", "c2_append_crc_phase"),
    ("metadata", "c2_append_metadata_phase"),
    ("capacity", "c2_append_capacity_phase"),
    ("stage", "c2_append_stage_phase"),
    ("image", "c2_append_image_phase"),
    ("entries", "c2_append_entries_phase"),
    ("header", "c2_append_header_phase"),
    ("publish_names", "c2_append_publish_names_phase"),
    ("publish_cells", "c2_append_publish_cells_phase"),
    ("rollback", "c2_append_rollback_phase"),
]

BOOT_DECODER_SLICES = C2_DECODER_SLICES[:6]
SESSION_DECODER_SLICES = C2_DECODER_SLICES[6:]
BOOT_ISLAND_SLOT = 2 + len(BOOT_DECODER_SLICES)
SESSION_EMITTER_SLOT_BASE = 2 + len(SESSION_DECODER_SLICES)
SESSION_APPEND_SLOT_BASE = SESSION_EMITTER_SLOT_BASE + len(C2_EMITTER_SLICES)
SESSION_SERVICE_SLOT_BASE = SESSION_APPEND_SLOT_BASE + len(C2_APPEND_SLICES)

VERIFIER_SPECS = [
    "0:catalog-verifier:.lisp65_rt_rtov_catalog:__lisp65_rt_rtov_catalog_start:__lisp65_rt_rtov_catalog_end:__lisp65_rt_rtov_catalog_entry:runtime+reusable:1:0:vm_runtime_overlay_catalog_verifier",
    "1:record-verifier:.lisp65_rt_rtov_record:__lisp65_rt_rtov_record_start:__lisp65_rt_rtov_record_end:__lisp65_rt_rtov_record_entry:runtime+reusable:1:0:vm_runtime_overlay_record_verifier",
] 


def checked_public_projection(names: list[str]) -> dict[str, str]:
    """Project internal C identifiers once at the public L65R boundary."""
    projected: dict[str, str] = {}
    owners: dict[str, str] = {}
    for internal in names:
        public = internal.replace("_", "-")
        previous = owners.get(public)
        if previous is not None and previous != internal:
            raise RuntimeError(
                f"public slice-name projection collision: {previous!r} and "
                f"{internal!r} both map to {public!r}")
        owners[public] = internal
        projected[internal] = public
    return projected


EMITTER_PUBLIC_NAMES = checked_public_projection(
    [name for name, _entry in C2_EMITTER_SLICES])
APPEND_PUBLIC_NAMES = checked_public_projection(
    [name for name, _entry in C2_APPEND_SLICES])

BOOT_SLICE_SPECS = VERIFIER_SPECS + [
    f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(BOOT_DECODER_SLICES)
] + [
    f"{BOOT_ISLAND_SLOT}:resident-island-installer:.lisp65_rt_island_00:__lisp65_rt_island_00_start:__lisp65_rt_island_00_end:__lisp65_rt_island_00_entry:boot:1:0:vm_resident_island_install"
]

SESSION_SLICE_SPECS = VERIFIER_SPECS + [
    f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(SESSION_DECODER_SLICES)
] + [
    f"{SESSION_EMITTER_SLOT_BASE + index}:c2-emit-{EMITTER_PUBLIC_NAMES[name]}:.lisp65_rt_c2emit_{name}:__lisp65_rt_c2emit_{name}_start:__lisp65_rt_c2emit_{name}_end:__lisp65_rt_c2emit_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(C2_EMITTER_SLICES)
] + [
    f"{SESSION_APPEND_SLOT_BASE + index}:c2-append-{APPEND_PUBLIC_NAMES[name]}:.lisp65_rt_c2append_{name}:__lisp65_rt_c2append_{name}_start:__lisp65_rt_c2append_{name}_end:__lisp65_rt_c2append_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(C2_APPEND_SLICES)
] + [
    f"{SESSION_SERVICE_SLOT_BASE}:error-text-renderer:.lisp65_rt_l65e:__lisp65_rt_l65e_start:__lisp65_rt_l65e_end:__lisp65_rt_l65e_entry:runtime+reusable:1:0:lisp65_error_overlay_entry",
    f"{SESSION_SERVICE_SLOT_BASE + 1}:first-class-buffer-read:.lisp65_rt_buffer_read:__lisp65_rt_buffer_read_start:__lisp65_rt_buffer_read_end:__lisp65_rt_buffer_read_entry:runtime+reusable:1:0:lisp65_buffer_overlay_read_entry",
    f"{SESSION_SERVICE_SLOT_BASE + 2}:first-class-buffer-write:.lisp65_rt_buffer_write:__lisp65_rt_buffer_write_start:__lisp65_rt_buffer_write_end:__lisp65_rt_buffer_write_entry:runtime+reusable:1:0:lisp65_buffer_overlay_write_entry",
    f"{SESSION_SERVICE_SLOT_BASE + 3}:first-class-buffer-alloc:.lisp65_rt_buffer_alloc:__lisp65_rt_buffer_alloc_start:__lisp65_rt_buffer_alloc_end:__lisp65_rt_buffer_alloc_entry:runtime+reusable:1:0:lisp65_buffer_overlay_alloc_entry",
]

UNIQUE_SLICE_COUNT = (2 + len(C2_DECODER_SLICES) + len(C2_EMITTER_SLICES)
                      + len(C2_APPEND_SLICES) + 5)


def assert_unique_public_specs() -> None:
    names = [spec.split(":", 2)[1]
             for spec in BOOT_SLICE_SPECS + SESSION_SLICE_SPECS]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    # The two family-local verifier names intentionally repeat across distinct
    # lifetime catalogs.  Every other published name is globally unique.
    expected = {"catalog-verifier", "record-verifier"}
    if set(duplicates) != expected:
        raise RuntimeError(
            f"unexpected public slice-name collision set: {duplicates}")


assert_unique_public_specs()


def run(argv: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        argv, cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else ""


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="ascii")
    else:
        path.write_bytes(data)


def crc16(data: bytes) -> int:
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xffff
                     if value & 0x8000 else (value << 1) & 0xffff)
    return value


KERNAL_SECTIONS = [
    ".lisp65_c2_kernal_window.typed_queue_driver",
    ".lisp65_c2_kernal_window.frame_source",
    ".lisp65_c2_kernal_window.irq_handler",
    ".lisp65_c2_kernal_window.nmi_and_freezer_return",
    ".lisp65_c2_kernal_window.map_switch_and_guards",
    ".lisp65_c2_kernal_window.post_startup_output_seam",
    ".lisp65_c2_kernal_window.event_poll",
    ".lisp65_c2_kernal_window.c2_resident",
    ".lisp65_c2_kernal_window.session_emitter_state",
    ".lisp65_c2_kernal_window.state",
    ".lisp65_c2_vectors",
]


def kernal_header_values(crc: int, sha256: str) -> bytes:
    return (
        "/* generated from the integrated C2 product window */\n"
        "#ifndef LISP65_C2_KERNAL_WINDOW_GENERATED_H\n"
        "#define LISP65_C2_KERNAL_WINDOW_GENERATED_H\n"
        f"#define C2_KERNAL_WINDOW_STAGE_PHYSICAL 0x{KERNAL_WINDOW_STAGE:08x}UL\n"
        f"#define C2_KERNAL_WINDOW_CPU_BASE 0x{KERNAL_WINDOW_BASE:04x}UL\n"
        f"#define C2_KERNAL_WINDOW_BYTES {KERNAL_WINDOW_BYTES}u\n"
        f"#define C2_KERNAL_WINDOW_CRC16 0x{crc:04x}u\n"
        f"#define C2_KERNAL_WINDOW_SHA256 \"{sha256}\"\n"
        "#endif\n"
    ).encode("ascii")


def kernal_header(data: bytes) -> bytes:
    return kernal_header_values(crc16(data), hashlib.sha256(data).hexdigest())


def kernal_window_identity_pin() -> dict[str, object]:
    contract = json.loads(KERNAL_CONTRACT.read_text(encoding="utf-8"))
    pin = contract.get("product_window_identity")
    if not isinstance(pin, dict) or pin.get("bytes") != KERNAL_WINDOW_BYTES:
        raise RuntimeError("C2 KERNAL window identity pin is absent or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", str(pin.get("sha256", ""))):
        raise RuntimeError("C2 KERNAL window identity SHA-256 is malformed")
    crc = pin.get("crc16")
    if not isinstance(crc, str) or not re.fullmatch(r"0x[0-9a-f]{4}", crc):
        raise RuntimeError("C2 KERNAL window identity CRC-16 is malformed")
    return pin


def verify_kernal_window_pin_source(out: Path,
                                    pin: dict[str, object]) -> dict[str, object]:
    source = ROOT / str(pin["source_elf"])
    if (not source.exists() or
            hashlib.sha256(source.read_bytes()).hexdigest()
            != pin["source_elf_sha256"]):
        raise RuntimeError("C2 KERNAL window identity source ELF is unavailable or changed")
    temporary = out / "c2-kernal-window-pin-source.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(source), str(temporary)])
    run(command)
    data = temporary.read_bytes()
    temporary.unlink()
    actual_sha = hashlib.sha256(data).hexdigest()
    actual_crc = crc16(data)
    if (len(data) != pin["bytes"] or actual_sha != pin["sha256"] or
            actual_crc != int(str(pin["crc16"]), 16)):
        raise RuntimeError("C2 KERNAL window identity pin does not match its source ELF")
    return {
        "source_elf": str(source.relative_to(ROOT)),
        "source_elf_sha256": pin["source_elf_sha256"],
        "bytes": len(data),
        "crc16": f"0x{actual_crc:04x}",
        "sha256": actual_sha,
        "status": "verified",
    }


def extract_pinned_kernal_window(out: Path, target: Path,
                                 pin: dict[str, object]) -> Path:
    image = out / "c2-product-kernal-window.bin"
    temporary = out / "c2-product-kernal-window.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(target) + ".elf", str(temporary)])
    run(command)
    data = temporary.read_bytes()
    if len(data) != KERNAL_WINDOW_BYTES:
        raise RuntimeError(
            f"C2 KERNAL window is {len(data)} bytes, expected {KERNAL_WINDOW_BYTES}")
    expected_sha = str(pin["sha256"])
    expected_crc = int(str(pin["crc16"]), 16)
    actual_sha = hashlib.sha256(data).hexdigest()
    actual_crc = crc16(data)
    if actual_sha != expected_sha or actual_crc != expected_crc:
        raise RuntimeError(
            "C2 KERNAL window drift against the pre-link identity pin: "
            f"sha={actual_sha} crc=0x{actual_crc:04x}")
    expected_header = kernal_header_values(expected_crc, expected_sha)
    header = out / "c2-kernal-window.generated.h"
    if not header.exists() or header.read_bytes() != expected_header:
        raise RuntimeError("C2 KERNAL window pre-link identity-header drift")
    write(image, data)
    temporary.unlink()
    return image


def extract_provisional_kernal_window(out: Path, target: Path) -> dict[str, object]:
    """Extract one probe window without pretending it matches the old pin."""
    image = out / "c2-product-kernal-window.bin"
    temporary = out / "c2-product-kernal-window.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(target) + ".elf", str(temporary)])
    run(command)
    data = temporary.read_bytes()
    temporary.unlink()
    if len(data) != KERNAL_WINDOW_BYTES:
        raise RuntimeError(
            f"provisional C2 KERNAL window is {len(data)} bytes, "
            f"expected {KERNAL_WINDOW_BYTES}")
    write(image, data)
    return {
        "path": str(image.relative_to(ROOT)),
        "bytes": len(data),
        "crc16": f"0x{crc16(data):04x}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "identity_status": "provisional-unpinned-hardware-prohibited",
    }


def replace_region(text: str, start: str, end: str, replacement: str) -> str:
    first = text.index(start)
    last = text.index(end, first)
    return text[:first] + replacement + text[last:]


def linker_script() -> str:
    text = (ROOT / "scripts/lisp65-mega65-workbench-overlay.ld").read_text(
        encoding="utf-8"
    )
    overlay_start = "    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS {"
    overlay_end = "    } >ram\n} INSERT AFTER .noinit;"
    sections = [
        "        .lisp65_workbench_overlay { KEEP(*(.lisp65_boot .lisp65_boot.*)) }",
        "        .lisp65_rt_rtov_catalog { KEEP(*(.lisp65_rt_rtov_catalog)) }",
        "        .lisp65_rt_rtov_record { KEEP(*(.lisp65_rt_rtov_record)) }",
    ]
    sections.extend(
        f"        .lisp65_rt_c2d_{name} {{ KEEP(*(.lisp65_rt_c2d_{name})) }}"
        for name, _entry in C2_DECODER_SLICES
    )
    sections.extend(
        f"        .lisp65_rt_c2emit_{name} {{ KEEP(*(.lisp65_rt_c2emit_{name})) }}"
        for name, _entry in C2_EMITTER_SLICES
    )
    sections.extend(
        f"        .lisp65_rt_c2append_{name} {{ KEEP(*(.lisp65_rt_c2append_{name})) }}"
        for name, _entry in C2_APPEND_SLICES
    )
    sections.extend([
        "        .lisp65_rt_l65e { KEEP(*(.lisp65_rt_l65e)) KEEP(*(.lisp65_rt_l65e_data)) }",
        "        .lisp65_rt_island_00 { KEEP(*(.lisp65_rt_island_00)) KEEP(*(.lisp65_rt_island_00_data)) }",
        "        .lisp65_rt_buffer_read { KEEP(*(.lisp65_rt_buffer_read)) }",
        "        .lisp65_rt_buffer_write { KEEP(*(.lisp65_rt_buffer_write)) }",
        "        .lisp65_rt_buffer_alloc { KEEP(*(.lisp65_rt_buffer_alloc)) }",
    ])
    new_overlay = (
        "    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS "
        "AT(ORIGIN(c2_runtime_load)) {\n"
        + "\n".join(sections) + "\n"
    )
    text = replace_region(text, overlay_start, overlay_end, new_overlay)
    text = re.sub(
        r"__lisp65_resident_island_seed_lma =\n\s+ALIGN\(LOADADDR\(\.lisp65_rt_c1_compiler\) \+ SIZEOF\(\.lisp65_rt_c1_compiler\), 0x100\);",
        "__lisp65_resident_island_seed_lma =\n"
        "    ALIGN(LOADADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc), 0x100);",
        text,
    )
    symbol_start = "__lisp65_rt_rtov_catalog_start ="
    symbol_end = "__lisp65_resident_island_start ="
    symbols = [
        "__lisp65_rt_rtov_catalog_start = ADDR(.lisp65_rt_rtov_catalog); __lisp65_rt_rtov_catalog_end = ADDR(.lisp65_rt_rtov_catalog) + SIZEOF(.lisp65_rt_rtov_catalog);",
        "__lisp65_rt_rtov_record_start = ADDR(.lisp65_rt_rtov_record); __lisp65_rt_rtov_record_end = ADDR(.lisp65_rt_rtov_record) + SIZEOF(.lisp65_rt_rtov_record);",
    ]
    symbols.extend(
        f"__lisp65_rt_c2d_{name}_start = ADDR(.lisp65_rt_c2d_{name}); __lisp65_rt_c2d_{name}_end = ADDR(.lisp65_rt_c2d_{name}) + SIZEOF(.lisp65_rt_c2d_{name});"
        for name, _entry in C2_DECODER_SLICES
    )
    symbols.extend(
        f"__lisp65_rt_c2emit_{name}_start = ADDR(.lisp65_rt_c2emit_{name}); __lisp65_rt_c2emit_{name}_end = ADDR(.lisp65_rt_c2emit_{name}) + SIZEOF(.lisp65_rt_c2emit_{name});"
        for name, _entry in C2_EMITTER_SLICES
    )
    symbols.extend(
        f"__lisp65_rt_c2append_{name}_start = ADDR(.lisp65_rt_c2append_{name}); __lisp65_rt_c2append_{name}_end = ADDR(.lisp65_rt_c2append_{name}) + SIZEOF(.lisp65_rt_c2append_{name});"
        for name, _entry in C2_APPEND_SLICES
    )
    symbols.extend([
        "__lisp65_rt_l65e_start = ADDR(.lisp65_rt_l65e); __lisp65_rt_l65e_end = ADDR(.lisp65_rt_l65e) + SIZEOF(.lisp65_rt_l65e);",
        "__lisp65_rt_buffer_read_start = ADDR(.lisp65_rt_buffer_read); __lisp65_rt_buffer_read_end = ADDR(.lisp65_rt_buffer_read) + SIZEOF(.lisp65_rt_buffer_read);",
        "__lisp65_rt_buffer_write_start = ADDR(.lisp65_rt_buffer_write); __lisp65_rt_buffer_write_end = ADDR(.lisp65_rt_buffer_write) + SIZEOF(.lisp65_rt_buffer_write);",
        "__lisp65_rt_buffer_alloc_start = ADDR(.lisp65_rt_buffer_alloc); __lisp65_rt_buffer_alloc_end = ADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc);",
    ])
    text = replace_region(text, symbol_start, symbol_end, "\n".join(symbols) + "\n")
    entry_start = "__lisp65_rt_rtov_catalog_entry ="
    entry_end = "__lisp65_rt_island_00_entry ="
    entries = [
        "__lisp65_rt_rtov_catalog_entry = vm_runtime_overlay_catalog_verifier;",
        "__lisp65_rt_rtov_record_entry = vm_runtime_overlay_record_verifier;",
    ]
    entries.extend(
        f"__lisp65_rt_c2d_{name}_entry = {entry};"
        for name, entry in C2_DECODER_SLICES
    )
    entries.extend(
        f"__lisp65_rt_c2emit_{name}_entry = {entry};"
        for name, entry in C2_EMITTER_SLICES
    )
    entries.extend(
        f"__lisp65_rt_c2append_{name}_entry = {entry};"
        for name, entry in C2_APPEND_SLICES
    )
    entries.extend([
        "__lisp65_rt_l65e_entry = lisp65_error_overlay_entry;",
        "__lisp65_rt_buffer_read_entry = lisp65_buffer_overlay_read_entry;",
        "__lisp65_rt_buffer_write_entry = lisp65_buffer_overlay_write_entry;",
        "__lisp65_rt_buffer_alloc_entry = lisp65_buffer_overlay_alloc_entry;",
    ])
    text = replace_region(text, entry_start, entry_end, "\n".join(entries) + "\n")
    assert_start = "ASSERT(SIZEOF(.lisp65_rt_rtov_catalog)"
    assert_end = "ASSERT(SIZEOF(.lisp65_rt_island_00)"
    assertions = [
        "ASSERT(SIZEOF(.lisp65_rt_rtov_catalog) > 0 && SIZEOF(.lisp65_rt_rtov_catalog) <= 1792 && __lisp65_rt_rtov_catalog_end <= __lisp65_workbench_runtime_overlay_limit, \"runtime overlay catalog verifier exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_rtov_record) > 0 && SIZEOF(.lisp65_rt_rtov_record) <= 1792 && __lisp65_rt_rtov_record_end <= __lisp65_workbench_runtime_overlay_limit, \"runtime overlay record verifier exceeds its stack-safe window\");",
    ]
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2d_{name}) > 0 && SIZEOF(.lisp65_rt_c2d_{name}) <= 1792 && __lisp65_rt_c2d_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 decoder phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_DECODER_SLICES
    )
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2emit_{name}) > 0 && SIZEOF(.lisp65_rt_c2emit_{name}) <= 1792 && __lisp65_rt_c2emit_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 emitter phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_EMITTER_SLICES
    )
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2append_{name}) > 0 && SIZEOF(.lisp65_rt_c2append_{name}) <= 1792 && __lisp65_rt_c2append_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 append phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_APPEND_SLICES
    )
    assertions.extend([
        "ASSERT(SIZEOF(.lisp65_rt_l65e) > 0 && SIZEOF(.lisp65_rt_l65e) <= 1792 && __lisp65_rt_l65e_end <= __lisp65_workbench_runtime_overlay_limit, \"L65E renderer exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_l65e) <= __lisp65_error_overlay_max_bytes, \"L65E renderer exceeds its product budget\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_read) > 0 && SIZEOF(.lisp65_rt_buffer_read) <= 1792 && __lisp65_rt_buffer_read_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer reader exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_write) > 0 && SIZEOF(.lisp65_rt_buffer_write) <= 1792 && __lisp65_rt_buffer_write_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer writer exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_alloc) > 0 && SIZEOF(.lisp65_rt_buffer_alloc) <= 1792 && __lisp65_rt_buffer_alloc_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer allocator exceeds its stack-safe window\");",
    ])
    text = replace_region(text, assert_start, assert_end, "\n".join(assertions) + "\n")
    memory_layout = (
        "MEMORY {\n"
        f"    c2_runtime_load (!rwx) : ORIGIN = 0x{RUNTIME_LOAD_BASE:06x}, "
        f"LENGTH = 0x{RUNTIME_LOAD_BYTES:06x}\n"
        "    c2_kernal_window (!rwx) : ORIGIN = 0xe000, LENGTH = 0x2000\n"
        f"    c2_kernal_window_load (!rwx) : ORIGIN = 0x{KERNAL_WINDOW_LOAD_BASE:06x}, "
        "LENGTH = 0x002000\n"
        "}\n\n"
    )
    binding_layout = r"""/* Four verifier tuples are the sole publish-last
 * mutation domain.  The input comes from a non-LTO assembler object, and the
 * public labels pin order as boot catalog/record then session catalog/record. */
SECTIONS {
    .lisp65_runtime_overlay_verifier_bindings : {
        __lisp65_rtov_binding_section_start = .;
        KEEP(*(.lisp65_runtime_overlay_verifier_bindings))
        __lisp65_rtov_binding_section_end = .;
    } >ram
} INSERT AFTER .rodata;

ASSERT(SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 32 &&
       __lisp65_rtov_binding_section_end -
       __lisp65_rtov_binding_section_start == 32,
       "runtime-overlay verifier binding table is not exactly 32 bytes");
ASSERT(__lisp65_rtov_verifier_bindings_start ==
           __lisp65_rtov_binding_section_start &&
       rtov_boot_verifiers == __lisp65_rtov_binding_section_start &&
       rtov_verifiers == __lisp65_rtov_binding_section_start + 16 &&
       __lisp65_rtov_verifier_bindings_end ==
           __lisp65_rtov_binding_section_end,
       "runtime-overlay verifier tuple order or labels drifted");
"""
    kernal_layout = r"""/* Product-resident handoff code is ordinary PRG material.  Name it here so
 * neither fixed-VMA artifact can capture an orphan section. */
SECTIONS {
    .lisp65_c2_kernal_handoff 0xb481 : {
        KEEP(*(.lisp65_c2_kernal_handoff))
    } >ram
    .lisp65_c2_host_facade 0xb5a2 : {
        KEEP(*(.lisp65_c2_host_facade))
    } >ram
    .lisp65_c2_kernal_io_reveal 0xb5c9 : {
        KEEP(*(.lisp65_c2_kernal_io_reveal))
    } >ram
    .lisp65_c2_kernal_map_switch 0xb5d4 : {
        KEEP(*(.lisp65_c2_kernal_map_switch))
    } >ram
    .lisp65_c2_kernal_state 0xb5e0 (NOLOAD) : {
        KEEP(*(.lisp65_c2_kernal_state))
    } >ram
} INSERT AFTER .text;

/* Every state cell referenced by the owned window has a declared address.
 * These are storage contracts, not ordinary whole-program allocation. */
SECTIONS {
    .lisp65_c2_fixed_zp 0x89 (NOLOAD) : {
        __lisp65_c2_fixed_zp_phase_owner = .;
        KEEP(*(.lisp65_c2_fixed_zp.phase_owner))
        __lisp65_c2_fixed_zp_pending_roots = .;
        KEEP(*(.lisp65_c2_fixed_zp.pending_roots))
        __lisp65_c2_fixed_zp_ready = .;
        KEEP(*(.lisp65_c2_fixed_zp.ready))
        __lisp65_c2_fixed_zp_str_building = .;
        KEEP(*(.lisp65_c2_fixed_zp.str_building))
        __lisp65_c2_fixed_zp_mem_oom = .;
        KEEP(*(.lisp65_c2_fixed_zp.mem_oom))
    } >zp
} INSERT AFTER .zp;

SECTIONS {
    .lisp65_c2_fixed_bank0 0xc080 (NOLOAD) : {
        __lisp65_c2_fixed_bank0_committed_roots = .;
        KEEP(*(.lisp65_c2_fixed_bank0.committed_roots))
        __lisp65_c2_fixed_bank0_decode_active = .;
        KEEP(*(.lisp65_c2_fixed_bank0.decode_active))
        __lisp65_c2_fixed_bank0_runtime = .;
        KEEP(*(.lisp65_c2_fixed_bank0.runtime))
        __lisp65_c2_fixed_bank0_edma_job = .;
        KEEP(*(.lisp65_c2_fixed_bank0.edma_job))
        __lisp65_c2_fixed_bank0_phase_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.phase_scratch))
        __lisp65_c2_fixed_bank0_sym_name_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.sym_name_scratch))
    } >ram
    .lisp65_c2_fixed_bank0_code 0xc218 : {
        __lisp65_c2_fixed_bank0_code_start = .;
        __lisp65_c2_fixed_bank0_code_kb_cursor_off = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.kb_cursor_off))
        __lisp65_c2_fixed_bank0_code_c2e_cons = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.c2e_cons))
        __lisp65_c2_fixed_bank0_code_end = .;
    } >ram
} INSERT AFTER .bss;

/* The owned CPU window has its own load-image counter.  Preserve VMA-relative
 * holes in the LMA so objcopy emits one exact 8-KiB window image. */
SECTIONS {
    .lisp65_c2_kernal_window.typed_queue_driver 0xe000 :
        AT(ORIGIN(c2_kernal_window_load) + 0x0000) {
        KEEP(*(.lisp65_c2_kernal_window.typed_queue_driver))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.frame_source :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.frame_source) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.frame_source))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.irq_handler :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.irq_handler) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.irq_handler))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.nmi_and_freezer_return :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.nmi_and_freezer_return))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.map_switch_and_guards :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.map_switch_and_guards))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.post_startup_output_seam :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.post_startup_output_seam))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.event_poll :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.event_poll) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.event_poll))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_code :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_code) - 0xe000) {
        __lisp65_c2_session_emitter_code_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_code))
        __lisp65_c2_session_emitter_code_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.c2_resident :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.c2_resident) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.c2_resident))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_state (NOLOAD) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_state) - 0xe000) {
        __lisp65_c2_session_emitter_state_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_state))
        __lisp65_c2_session_emitter_state_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.state 0xff80 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f80) {
        KEEP(*(.lisp65_c2_kernal_window.state))
    } >c2_kernal_window
    .lisp65_c2_vectors 0xfffa :
        AT(ORIGIN(c2_kernal_window_load) + 0x1ffa) {
        KEEP(*(.lisp65_c2_vectors))
    } >c2_kernal_window
} INSERT AFTER .lisp65_resident_island_annex;

ASSERT(ADDR(.basic_header) == 0x2001,
       "C2 load domains moved the product PRG header");
ASSERT(LOADADDR(.lisp65_workbench_overlay) == ORIGIN(c2_runtime_load),
       "C2 runtime-slice load domain did not start at its own origin");
ASSERT(__lisp65_resident_island_seed_lma + SIZEOF(.lisp65_resident_island) <=
       ORIGIN(c2_runtime_load) + LENGTH(c2_runtime_load),
       "C2 runtime-slice load domain exhausted");
ASSERT(LOADADDR(.lisp65_c2_kernal_window.typed_queue_driver) ==
       ORIGIN(c2_kernal_window_load),
       "C2 KERNAL-window load domain did not start at its own origin");
ASSERT(LOADADDR(.lisp65_c2_vectors) + SIZEOF(.lisp65_c2_vectors) ==
       ORIGIN(c2_kernal_window_load) + LENGTH(c2_kernal_window_load),
       "C2 KERNAL-window load image is not exactly 8 KiB");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) < 0xe000 &&
       ADDR(.lisp65_c2_host_facade) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_io_reveal) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_map_switch) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_state) < 0xe000,
       "C2 low-resident handoff escaped the PRG domain");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) == 0xb481 &&
       ADDR(.lisp65_c2_kernal_handoff) + SIZEOF(.lisp65_c2_kernal_handoff) <= 0xb5a2,
       "C2 handoff overlaps the fixed host facade");
ASSERT(ADDR(.lisp65_c2_host_facade) == 0xb5a2 &&
       SIZEOF(.lisp65_c2_host_facade) == 39,
       "C2 fixed host-facade geometry drift");
ASSERT(c2_facade_vm_code_load == 0xb5a2 && c2_facade_c2_dma == 0xb5a5 &&
       c2_facade_overlay_call_family == 0xb5a8 && c2_facade_c2e_cons == 0xb5ab &&
       c2_facade_c2e_overlay == 0xb5ae && c2_facade_car == 0xb5b1 &&
       c2_facade_cdr == 0xb5b4 && c2_facade_gc_collect == 0xb5b7 &&
       c2_facade_str_open == 0xb5ba && c2_facade_str_putc == 0xb5bd &&
       c2_facade_intern == 0xb5c0 && c2_facade_select_family == 0xb5c3 &&
       c2_facade_gc_mark == 0xb5c6,
       "C2 fixed host-facade vector address drift");
ASSERT(ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5c9 &&
       SIZEOF(.lisp65_c2_kernal_io_reveal) == 11 &&
       c2_kernal_reveal_io == 0xb5c9 &&
       ADDR(.lisp65_c2_kernal_map_switch) == 0xb5d4 &&
       SIZEOF(.lisp65_c2_kernal_map_switch) == 10 &&
       ADDR(.lisp65_c2_kernal_map_switch) +
           SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb5e0 &&
       ADDR(.lisp65_c2_kernal_state) == 0xb5e0,
       "C2 fixed low-resident handoff geometry drift");

ASSERT(ADDR(.zp) + SIZEOF(.zp) <= 0x89,
       "ordinary zero-page storage overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_zp) == 0x89 &&
       SIZEOF(.lisp65_c2_fixed_zp) == 7 &&
       __lisp65_c2_fixed_zp_phase_owner == 0x89 &&
       __lisp65_c2_fixed_zp_pending_roots == 0x8a &&
       __lisp65_c2_fixed_zp_ready == 0x8c &&
       __lisp65_c2_fixed_zp_str_building == 0x8d &&
       __lisp65_c2_fixed_zp_mem_oom == 0x8f,
       "C2 fixed zero-page state geometry drift");
ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0xc080,
       "ordinary Bank-0 state overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) == 0xc080 &&
       SIZEOF(.lisp65_c2_fixed_bank0) == 408 &&
       __lisp65_c2_fixed_bank0_committed_roots == 0xc080 &&
       __lisp65_c2_fixed_bank0_decode_active == 0xc082 &&
       __lisp65_c2_fixed_bank0_runtime == 0xc084 &&
       __lisp65_c2_fixed_bank0_edma_job == 0xc0b2 &&
       __lisp65_c2_fixed_bank0_phase_scratch == 0xc0c6 &&
       __lisp65_c2_fixed_bank0_sym_name_scratch == 0xc1f6,
       "C2 fixed Bank-0 state geometry drift");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) + SIZEOF(.lisp65_c2_fixed_bank0) <=
       ADDR(.lisp65_c2_fixed_bank0_code) &&
       ADDR(.lisp65_c2_fixed_bank0_code) == 0xc218 &&
       SIZEOF(.lisp65_c2_fixed_bank0_code) == 45 &&
       __lisp65_c2_fixed_bank0_code_start == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_kb_cursor_off == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_c2e_cons == 0xc21d &&
       __lisp65_c2_fixed_bank0_code_end == 0xc245 &&
       ADDR(.lisp65_c2_fixed_bank0_code) +
       SIZEOF(.lisp65_c2_fixed_bank0_code) <=
       __lisp65_workbench_runtime_overlay_vma,
       "C2 fixed Bank-0 state overlaps the runtime overlay");

ASSERT(ADDR(.lisp65_c2_kernal_window.c2_resident) +
       SIZEOF(.lisp65_c2_kernal_window.c2_resident) <= 0xff80,
       "C2-owned KERNAL-window residents overlap state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0 &&
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 346,
       "C2 session-only E000 residency geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.state) == 0xff80 &&
       SIZEOF(.lisp65_c2_kernal_window.state) == 16,
       "C2 KERNAL-window state geometry drift");
ASSERT(ADDR(.lisp65_c2_vectors) == 0xfffa && SIZEOF(.lisp65_c2_vectors) == 6,
       "C2 owned vector geometry drift");
"""
    metadata_sections = []
    for name in ORPHAN_ALLOWLIST:
        keep = f"KEEP(*({name}))" if name == ".lisp65_error_callsites" else f"*({name})"
        metadata_sections.append(f"    {name} 0 (INFO) : {{ {keep} }}")
    metadata_layout = (
        "\n/* Exact non-ALLOC orphan allowlist.  Unknown section names remain fatal. */\n"
        "SECTIONS {\n" + "\n".join(metadata_sections) + "\n}\n"
        "ASSERT(SIZEOF(.lisp65_error_callsites) > 0,\n"
        "       \"required error-callsite evidence section is absent\");\n"
        "ASSERT(ADDR(.lisp65_error_callsites) == 0,\n"
        "       \"error-callsite evidence section moved from address zero\");\n"
    )
    return (memory_layout + text + "\n" + binding_layout + kernal_layout
            + metadata_layout).replace(
        "directly after Slot 37", "directly after the final C2 runtime slice")


def source_list() -> list[str]:
    sources = [
        str(path) for path in sorted((ROOT / "src").glob("*.c"))
        if path.name not in LEGACY_C
    ]
    sources.extend(str(path) for path in C2_PHASE_SOURCES)
    sources.extend([
        str(ROOT / "src/mega65_math.s"),
        str(ROOT / "src/f011_guarded_write.s"),
        str(ROOT / "src/runtime_overlay_verifier_bindings.s"),
        str(ROOT / "src/c2_kernal_facade.s"),
        str(ROOT / "src/c2_kernal_map.s"),
        str(ROOT / "src/c2_kernal_window.s"),
    ])
    return sources


def definitions(artifacts: dict[str, object]) -> list[str]:
    return [
        "LISP65_VM", "LISP65_EMBED_STDLIB", "LISP65_EMBED_DMA", "LISP65_REPL",
        "HEAP_CELLS=48", "LISP65_MEGA65_MATH_OVERRIDE", "LISP65_F011_GUARD_ASM",
        "VM_CODEBUF=56", "LISP65_SYMPOOL_EXT", "LISP65_SYMVAL_EXT",
        "LISP65_NAMEOFF_EXT", "GC_ROOTS=128", "LISP65_MARK_BITMAP", "LISP65_EXT_HEAP",
        "LISP65_SCREEN_DRIVER", "LISP65_VM_SCREEN_PRIMS", "LISP65_VM_STDLIB_IO_WRAPPERS",
        "LISP65_VM_GLOBAL_PRIMS", "LISP65_MACROEXPAND_PRIM", "LISP65_TREEWALK_STDLIB_BRIDGES",
        "LISP65_OUTPUT_WRAPPERS_IN_STDLIB", "LISP65_SCREEN_BULK_P_IN_STDLIB",
        "LISP65_TREEWALK_STRIP", "MEGA65_F011_LOAD", "MEGA65_F011_WRITE", "IO_BUF_MAX=1",
        "EXT_CELLS=1024", "LISP65_NURSERY_HYSTERESIS=192", "LISP65_STRING_ARENA",
        "LISP65_FIRST_CLASS_BUFFER", "STR_ARENA_SIZE=0x2480", "DISK_EXT_BASE=0x6900",
        "DISK_EXT_FILE_MAX=0x9600", "LISP65_COMPILE_STRING", "LISP65_SYMFN_EXT",
        "SYMPOOL_EXT_OFF=0xc680", "NAMEPOOL=10208", "MAX_SYM=752", "VM_DIR_MAX=608",
        "REPL_BUF_MAX=192", "HIST_MAX=64", "LISP65_REPL_HISTORY_IN_BUF",
        "LISP65_REPL_BANNER_REQUIRED", "LISP65_STDLIB_BOOT_OVERLAY_CODE",
        "LISP65_STAGED_BOOT_OVERLAY", "LISP65_RUNTIME_OVERLAY",
        "LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "LISP65_C2_RUNTIME_LIFETIME_FAMILIES", "LISP65_STACK_GUARD",
        "LISP65_C2_PRODUCT_CUT", "LISP65_C2_SLICED_APPEND", "C2_STREAM_PRODUCT_V3=1",
        "LISP65_C2_KERNAL_UNMAP",
        f"LISP65_C2_PRODUCT_BUILD_ID={artifacts['product_build_id_hex']}UL",
        f"LISP65_C2_PRODUCT_SHELF_BYTES={artifacts['artifacts']['shelf']['bytes']}UL",
        "LISP65_ERROR_OVERLAY",
        f"LISP65_ERROR_OVERLAY_SLOT={SESSION_SERVICE_SLOT_BASE}",
        f"LISP65_RUNTIME_ISLAND_INSTALL_SLOT={BOOT_ISLAND_SLOT}",
        f"LISP65_BUFFER_OVERLAY_READ_SLOT={SESSION_SERVICE_SLOT_BASE + 1}",
        f"LISP65_BUFFER_OVERLAY_WRITE_SLOT={SESSION_SERVICE_SLOT_BASE + 2}",
        f"LISP65_BUFFER_OVERLAY_ALLOC_SLOT={SESSION_SERVICE_SLOT_BASE + 3}",
    ]


def compile_link(out: Path, name: str, headers: list[Path], artifacts: dict[str, object]) -> Path:
    target = out / name
    command = [str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall"]
    command.extend(f"-D{item}" for item in definitions(artifacts))
    for header in headers:
        command.extend(["-include", str(header)])
    command.extend([
        "-I", str(ROOT / "src"),
        "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "build/c2.2/substitution"),
        "-I", str(out),
        "-I", str(ROOT / "build/bytecode"),
    ])
    command.extend(source_list())
    command.extend([
        "-Wl,--icf=all",
        "-Wl,--orphan-handling=error",
        "-Wl,--defsym=__udivhi3=lisp65_hw_udivhi3",
        "-Wl,--defsym=__umodhi3=lisp65_hw_umodhi3",
        "-Wl,--defsym=__udivmodhi4=lisp65_hw_udivmodhi4",
        "-Wl,--defsym=__mulhi3=lisp65_hw_mulhi3",
        "-Wl,--defsym=__divhi3=lisp65_hw_divhi3",
        "-Wl,--defsym=__modhi3=lisp65_hw_modhi3",
        "-Wl,-T," + str(out / "c2-substitution.ld"),
        "-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=512",
        "-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=1450",
        "-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=1024",
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=" + RUNTIME_VMA,
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=" + RUNTIME_VMA,
        "-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=1320",
        "-Wl,--defsym=__lisp65_workbench_screen_base_param=0x0800",
        "-Wl,--defsym=__lisp65_workbench_screen_columns_param=80",
        "-Wl,--defsym=__lisp65_workbench_screen_rows_param=50",
        "-Wl,--defsym=__lisp65_workbench_screen_cell_bytes_param=1",
        "-Wl,--defsym=__lisp65_resident_island_base_param=0x1800",
        "-Wl,--defsym=__lisp65_resident_island_limit_param=0x2000",
        "-Wl,--defsym=__lisp65_resident_island_payload_capacity_param=2048",
        "-Wl,-Map=" + str(target) + ".map",
        "-o", str(target),
    ])
    run(command)
    return target


def tool(name: str, *args: str) -> None:
    run([sys.executable, str(ROOT / "tools/host-lisp" / name), *args])


def overlay_pack_family(out: Path, target: Path, contract: Path,
                        family: str, suffix: str) -> tuple[Path, Path]:
    nm = str(TOOLCHAIN / "llvm-nm")
    symbols = run([nm, "--defined-only", str(target) + ".elf"], capture=True)
    match = re.search(r"^([0-9a-fA-F]+)\s+\S\s+__lisp65_workbench_runtime_overlay_vma$", symbols, re.M)
    if not match:
        raise RuntimeError("missing runtime-overlay VMA")
    args = [
        "pack", "--elf", str(target) + ".elf", "--nm", nm,
        "--objcopy", str(TOOLCHAIN / "llvm-objcopy"), "--profile", PROFILE,
        "--abi-contract", str(contract), "--vma", "0x" + match.group(1),
        "--max-slice-bytes", "1792",
    ]
    specs = BOOT_SLICE_SPECS if family == "boot" else SESSION_SLICE_SPECS
    for spec in specs:
        args.extend(["--slice", spec])
    image = out / f"runtime-overlays-{family}-{suffix}.bin"
    manifest = out / f"runtime-overlays-{family}-{suffix}.json"
    temporary_header = out / f"runtime-overlay-{family}-{suffix}.h"
    args.extend([
        "--image", str(image), "--manifest", str(manifest),
        "--header", str(temporary_header), "--header-mode", "write",
    ])
    tool("runtime_overlay_bank.py", *args)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["lifetime_family"] = family
    value["storage"]["address"] = 0x08200000 if family == "boot" else 0x08000000
    value["storage"]["lifetime"] = (
        "generation-invalid-through-phase-3" if family == "boot"
        else "post-phase-3-session"
    )
    write(manifest, json.dumps(value, indent=2, sort_keys=True) + "\n")
    return image, manifest


def _verifier_tuple(manifest: dict[str, object], slot: int) -> tuple[int, int, int, int]:
    records = manifest["slices"]
    record = next(item for item in records if item["id"] == slot)
    return (record["file_offset"], record["file_size"],
            record["entry_offset"], record["crc16"])


def verifier_binding_bytes(boot_manifest: Path,
                           session_manifest: Path) -> bytes:
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    values: list[int] = []
    for manifest in (boot, session):
        for slot in (0, 1):
            values.extend(_verifier_tuple(manifest, slot))
    if len(values) != 16 or any(not 0 <= value <= 0xffff for value in values):
        raise RuntimeError("runtime verifier tuple lies outside its 32-byte table")
    return struct.pack("<16H", *values)


def _validate_family_artifact(data: bytes, manifest: dict[str, object],
                              label: str) -> None:
    storage = manifest["storage"]
    if storage["size"] != len(data):
        raise RuntimeError(f"{label}: storage size does not match image")
    if storage["sha256"] != hashlib.sha256(data).hexdigest():
        raise RuntimeError(f"{label}: storage SHA-256 does not match image")
    if storage["crc16"] != crc16(data):
        raise RuntimeError(f"{label}: storage CRC-16 does not match image")
    for record in manifest["slices"]:
        start = record["file_offset"]
        end = start + record["file_size"]
        if start < 0 or end > len(data) or end <= start:
            raise RuntimeError(f"{label}: slice {record['id']} range is invalid")
        payload = data[start:end]
        if record["sha256"] != hashlib.sha256(payload).hexdigest():
            raise RuntimeError(f"{label}: slice {record['id']} SHA-256 mismatch")
        if record["crc16"] != crc16(payload):
            raise RuntimeError(f"{label}: slice {record['id']} CRC-16 mismatch")


def _family_identity_equal(reference_image: Path, reference_manifest: Path,
                           candidate_image: Path, candidate_manifest: Path,
                           label: str) -> int:
    reference_data = reference_image.read_bytes()
    candidate_data = candidate_image.read_bytes()
    reference = json.loads(reference_manifest.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest.read_text(encoding="utf-8"))
    _validate_family_artifact(reference_data, reference, label + ":reference")
    _validate_family_artifact(candidate_data, candidate, label + ":candidate")
    if reference["slices"] != candidate["slices"]:
        raise RuntimeError(f"{label}: runtime-family record field drift")
    if reference_data != candidate_data:
        raise RuntimeError(f"{label}: runtime-family payload drift")
    return len(reference["slices"])


def _family_identity_negative_selftest(image: Path, manifest: Path) -> str:
    data = bytearray(image.read_bytes())
    value = json.loads(manifest.read_text(encoding="utf-8"))
    record = value["slices"][-1]
    offset = record["file_offset"] + record["file_size"] // 2
    data[offset] ^= 0x01
    try:
        _validate_family_artifact(bytes(data), value,
                                  "mutated-payload-negative")
    except RuntimeError:
        return "rejected"
    raise AssertionError("mutated runtime-family payload was accepted")


def runtime_family_identity_gate(
        out: Path,
        unbound_boot: tuple[Path, Path], unbound_session: tuple[Path, Path],
        final_boot: tuple[Path, Path], final_session: tuple[Path, Path]
) -> dict[str, object]:
    boot_records = _family_identity_equal(
        unbound_boot[0], unbound_boot[1], final_boot[0], final_boot[1], "boot")
    session_records = _family_identity_equal(
        unbound_session[0], unbound_session[1],
        final_session[0], final_session[1], "session")
    negative = _family_identity_negative_selftest(final_session[0], final_session[1])
    report = {
        "format": "lisp65-runtime-family-total-identity-v1",
        "status": "passed",
        "comparison": "all-record-fields-and-all-payload-bytes",
        "boot_records": boot_records,
        "session_records": session_records,
        "record_occurrences": boot_records + session_records,
        "mutated_payload_negative": negative,
        "claim_limit": (
            "Pack/repack identity from one ELF and a pinned negative mutation; "
            "hardware execution is not claimed."
        ),
    }
    write(out / "runtime-family-total-identity.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def patch_verifier_binding_table(out: Path, target: Path,
                                 boot_manifest: Path,
                                 session_manifest: Path) -> dict[str, object]:
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    section = sections.get(VERIFIER_BINDING_SECTION)
    if not section or section["bytes"] != VERIFIER_BINDING_BYTES:
        raise RuntimeError(f"verifier binding section geometry red: {section}")
    start = section["address"]
    expected_symbols = {
        "__lisp65_rtov_verifier_bindings_start": start,
        "rtov_boot_verifiers": start,
        "rtov_verifiers": start + 16,
        "__lisp65_rtov_verifier_bindings_end": start + VERIFIER_BINDING_BYTES,
    }
    for name, expected in expected_symbols.items():
        if symbols.get(name) != expected:
            raise RuntimeError(
                f"verifier binding symbol drift {name}: "
                f"{symbols.get(name)} != {expected}")

    original = target.read_bytes()
    if len(original) < 2:
        raise RuntimeError("product PRG lacks its load address")
    load_address = original[0] | (original[1] << 8)
    file_offset = 2 + start - load_address
    if file_offset < 2 or file_offset + VERIFIER_BINDING_BYTES > len(original):
        raise RuntimeError("verifier binding section lies outside the product PRG")
    placeholder = struct.pack("<16H", *VERIFIER_BINDING_SENTINELS)
    if original[file_offset:file_offset + VERIFIER_BINDING_BYTES] != placeholder:
        raise RuntimeError("verifier binding placeholder bytes drifted")

    unbound = out / "lisp65-c2-substitution-unbound.prg"
    write(unbound, original)
    binding = verifier_binding_bytes(boot_manifest, session_manifest)
    write(out / "runtime-overlay-verifier-bindings.bin", binding)
    patched = bytearray(original)
    patched[file_offset:file_offset + VERIFIER_BINDING_BYTES] = binding
    write(target, bytes(patched))
    changed = [index for index, (before, after) in
               enumerate(zip(original, patched)) if before != after]
    allowed = set(range(file_offset, file_offset + VERIFIER_BINDING_BYTES))
    if not changed or not set(changed) <= allowed:
        raise RuntimeError("publish-last patch escaped its 32-byte section")
    if target.read_bytes()[file_offset:file_offset + VERIFIER_BINDING_BYTES] != binding:
        raise RuntimeError("published verifier binding does not match manifests")

    report = {
        "format": "lisp65-runtime-verifier-publish-last-v1",
        "status": "passed",
        "section": VERIFIER_BINDING_SECTION,
        "address": start,
        "file_offset": file_offset,
        "bytes": VERIFIER_BINDING_BYTES,
        "changed_bytes": len(changed),
        "changed_range_confined": True,
        "tuple_order": [
            "boot-catalog", "boot-record", "session-catalog", "session-record"
        ],
        "unbound_sha256": hashlib.sha256(original).hexdigest(),
        "bound_sha256": hashlib.sha256(bytes(patched)).hexdigest(),
        "binding_sha256": hashlib.sha256(binding).hexdigest(),
    }
    write(out / "runtime-verifier-publish-last.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def render_prepared_family_header(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="ascii")
    marker = "#endif /* LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H */"
    insertion = "\n".join([
        "#define LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES 1",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE 0x08200000UL",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16 LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16 LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16",
        "",
    ])
    write(destination, text.replace(marker, insertion + marker))


def section_table(elf: Path) -> dict[str, dict[str, int]]:
    output = run([str(TOOLCHAIN / "llvm-size"), "-A", str(elf)], capture=True)
    result: dict[str, dict[str, int]] = {}
    for line in output.splitlines():
        match = re.match(r"^(\.[^\s]+)\s+(\d+)\s+(\d+)$", line.strip())
        if match:
            result[match.group(1)] = {
                "bytes": int(match.group(2)), "address": int(match.group(3))}
    return result


def defined_symbols(elf: Path) -> dict[str, int]:
    output = run([
        str(TOOLCHAIN / "llvm-nm"), "--defined-only", "--numeric-sort", str(elf)
    ], capture=True)
    result: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            result[fields[-1]] = int(fields[0], 16)
    return result


def fixed_facade_gate(out: Path, target: Path, suffix: str) -> dict[str, object]:
    """Pin every cross-domain call and state operand used by the E000 slab."""
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    required_sections = {
        ".lisp65_c2_host_facade": (HOST_FACADE_BASE,
                                    len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE),
        ".lisp65_c2_fixed_zp": (FIXED_ZP_BASE, FIXED_ZP_BYTES),
        ".lisp65_c2_fixed_bank0": (FIXED_BANK0_BASE, FIXED_BANK0_BYTES),
        ".lisp65_c2_fixed_bank0_code": (FIXED_BANK0_CODE_BASE,
                                          FIXED_BANK0_CODE_BYTES),
        ".lisp65_c2_kernal_window.session_emitter_state": (
            sections.get(".lisp65_c2_kernal_window.session_emitter_state", {}).get(
                "address", -1), SESSION_EMITTER_STATE_BYTES),
    }
    for name, (address, size) in required_sections.items():
        row = sections.get(name)
        if row != {"address": address, "bytes": size}:
            raise RuntimeError(
                f"fixed facade red: {name} is {row}, expected "
                f"address=0x{address:04x} bytes={size}")

    vector_addresses = {
        name: HOST_FACADE_BASE + index * HOST_FACADE_STRIDE
        for index, name in enumerate(HOST_FACADE_SYMBOLS)
    }
    drift = {
        name: {"actual": symbols.get(name), "expected": address}
        for name, address in vector_addresses.items()
        if symbols.get(name) != address
    }
    if drift:
        raise RuntimeError(f"fixed facade red: vector address drift {drift}")

    fixed_state = {
        "__lisp65_c2_fixed_zp_phase_owner": 0x89,
        "__lisp65_c2_fixed_zp_pending_roots": 0x8A,
        "__lisp65_c2_fixed_zp_ready": 0x8C,
        "__lisp65_c2_fixed_zp_str_building": 0x8D,
        "__lisp65_c2_fixed_zp_mem_oom": 0x8F,
        "__lisp65_c2_fixed_bank0_committed_roots": 0xC080,
        "__lisp65_c2_fixed_bank0_decode_active": 0xC082,
        "__lisp65_c2_fixed_bank0_runtime": 0xC084,
        "__lisp65_c2_fixed_bank0_edma_job": 0xC0B2,
        "__lisp65_c2_fixed_bank0_phase_scratch": 0xC0C6,
        "__lisp65_c2_fixed_bank0_sym_name_scratch": 0xC1F6,
        "__lisp65_c2_fixed_bank0_code_start": FIXED_BANK0_CODE_BASE,
        "__lisp65_c2_fixed_bank0_code_kb_cursor_off": FIXED_BANK0_CODE_BASE,
        "__lisp65_c2_fixed_bank0_code_c2e_cons": FIXED_BANK0_CODE_BASE + 5,
        "__lisp65_c2_fixed_bank0_code_end": (
            FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES),
    }
    state_drift = {
        name: {"actual": symbols.get(name), "expected": address}
        for name, address in fixed_state.items()
        if symbols.get(name) != address
    }
    if state_drift:
        raise RuntimeError(f"fixed facade red: state address drift {state_drift}")

    facade_targets = set(vector_addresses.values())
    bad_window_edges: list[dict[str, object]] = []
    for section in KERNAL_SECTIONS:
        if section in {".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors"}:
            continue
        disassembly = run([
            str(TOOLCHAIN / "llvm-objdump"), "-d", f"--section={section}", str(elf)
        ], capture=True).lower()
        for match in re.finditer(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", disassembly):
            destination = int(match.group(1), 16)
            if destination < KERNAL_WINDOW_BASE and destination not in facade_targets:
                bad_window_edges.append({
                    "section": section,
                    "target": f"0x{destination:04x}",
                    "instruction": match.group(0),
                })
    if bad_window_edges:
        raise RuntimeError(
            f"fixed facade red: E000 code bypasses the fixed vectors "
            f"{bad_window_edges}")

    report = {
        "format": "lisp65-c2-fixed-host-facade-link-v1",
        "status": "passed",
        "link_stage": suffix,
        "vector_contract": {
            "base": HOST_FACADE_BASE,
            "stride_bytes": HOST_FACADE_STRIDE,
            "bytes": len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE,
            "symbols": vector_addresses,
        },
        "fixed_state_contract": {
            "zero_page": {"base": FIXED_ZP_BASE, "bytes": FIXED_ZP_BYTES},
            "bank0": {"base": FIXED_BANK0_BASE, "bytes": FIXED_BANK0_BYTES},
            "bank0_code": {
                "base": FIXED_BANK0_CODE_BASE,
                "bytes": FIXED_BANK0_CODE_BYTES,
                "headroom_to_runtime_overlay_bytes": FIXED_BANK0_HEADROOM_BYTES,
            },
            "symbols": fixed_state,
        },
        "window_direct_low_edges_outside_facade": [],
        "claim_limit": (
            "Structural fixed-address and edge gate; hardware behavior is not claimed."
        ),
    }
    write(out / f"fixed-host-facade-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _sectioned_disassembly(text: str) -> tuple[
        dict[tuple[str, int], dict[str, object]], dict[str, list[str]]]:
    """Parse functions without pretending a VMA identifies an overlay node."""
    nodes: dict[tuple[str, int], dict[str, object]] = {}
    section_lines: dict[str, list[str]] = {}
    section: str | None = None
    current: dict[str, object] | None = None
    for raw_line in text.lower().splitlines():
        section_header = re.match(r"^disassembly of section ([^:]+):$",
                                  raw_line.strip())
        if section_header:
            section = section_header.group(1)
            section_lines.setdefault(section, [])
            current = None
            continue
        if section is None:
            continue
        section_lines[section].append(raw_line)
        function_header = re.match(r"^([0-9a-f]+) <([^>]+)>:$",
                                   raw_line.strip())
        if function_header:
            address = int(function_header.group(1), 16)
            key = (section, address)
            current = nodes.setdefault(key, {
                "section": section,
                "address": address,
                "names": [],
                "lines": [],
            })
            name = function_header.group(2)
            if name not in current["names"]:
                current["names"].append(name)
            continue
        if current is not None:
            current["lines"].append(raw_line)
    return nodes, section_lines


def _direct_call_targets(lines: list[str]) -> list[int]:
    return [int(match.group(1), 16) for line in lines
            if (match := re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b",
                                   line))]


def _machine_instructions(lines: list[str]) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    for line in lines:
        match = re.match(
            r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2}\s+)+([a-z][a-z0-9]*)\s*(.*?)\s*$",
            line)
        if match:
            operand = match.group(2).split(";", 1)[0].strip()
            instructions.append((match.group(1), operand))
    return instructions


def _handoff_z_abi_errors(ownership_lines: list[str], copy_lines: list[str],
                          reveal_lines: list[str],
                          map_lines: list[str]) -> list[str]:
    """Bind both firmware-to-product ABI invariants before any I/O store."""
    ownership = _machine_instructions(ownership_lines)
    errors: list[str] = []
    if len(ownership) < 2 or ownership[0][0] != "sei":
        errors.append("ownership-first-instruction-is-not-sei")
    if (len(ownership) < 2 or ownership[1][0] != "ldz"
            or not re.fullmatch(r"#\$(?:0+)", ownership[1][1])):
        errors.append("ownership-does-not-normalize-z-immediately-after-sei")
    if (len(ownership) < 3 or ownership[2][0] != "jsr"
            or not re.fullmatch(r"\$b5c9(?:\s+<[^>]+>)?", ownership[2][1])):
        errors.append("ownership-does-not-reveal-mega65-io-before-register-access")

    reveal = _machine_instructions(reveal_lines)
    expected_reveal = [
        ("lda", "#$47"), ("sta", "$d02f"),
        ("lda", "#$53"), ("sta", "$d02f"), ("rts", ""),
    ]
    if reveal != expected_reveal:
        errors.append("mega65-io-knock-sequence-drift")

    # EOM is encoded as $ea and llvm-objdump renders it as NOP.  The sequence
    # deliberately derives A/X/Y=0 from the boundary-owned Z=0 invariant.
    map_switch = _machine_instructions(map_lines)
    expected_map_switch = [
        ("tza", ""), ("tax", ""), ("tay", ""), ("ldz", "#$80"),
        ("map", ""), ("nop", ""), ("ldz", "#$0"), ("rts", ""),
    ]
    if map_switch != expected_map_switch:
        errors.append("kernal-map-operand-sequence-drift")

    copy = _machine_instructions(copy_lines)
    stores = {(mnemonic, operand) for mnemonic, operand in copy}
    if ("stz", "$d702") not in stores:
        errors.append("fixed-handoff-size-payment-missing:$d702")
    if any(operand == "$d704" for _mnemonic, operand in copy):
        errors.append("redundant-d704-write-returned")
    return errors


def _handoff_z_abi_model_selftest() -> dict[str, str]:
    good = [
        "    b481: 78            sei",
        "    b482: a3 00         ldz #$0",
        "    b484: 20 c9 b5      jsr $b5c9",
        "    b487: 9c 0e dd      stz $dd0e",
    ]
    copy = [
        "    b520: 9c 02 d7      stz $d702",
    ]
    reveal = [
        "    b5c9: a9 47         lda #$47",
        "    b5cb: 8d 2f d0      sta $d02f",
        "    b5ce: a9 53         lda #$53",
        "    b5d0: 8d 2f d0      sta $d02f",
        "    b5d3: 60            rts",
    ]
    map_switch = [
        "    b5d4: 6b            tza",
        "    b5d5: aa            tax",
        "    b5d6: a8            tay",
        "    b5d7: a3 80         ldz #$80",
        "    b5d9: 5c            map",
        "    b5da: ea            nop",
        "    b5db: a3 00         ldz #$0",
        "    b5dd: 60            rts",
    ]
    if _handoff_z_abi_errors(good, copy, reveal, map_switch):
        raise AssertionError("valid handoff boundary was rejected")
    mutations = {
        "missing-z-normalization": [good[0], good[2], good[3]],
        "late-z-normalization": [good[0], good[2], good[1], good[3]],
        "nonzero-z-normalization": [good[0],
                                    "    b482: a3 06         ldz #$6",
                                    good[2], good[3]],
        "missing-io-reveal-call": [good[0], good[1], good[3]],
        "late-io-reveal-call": [good[0], good[1], good[3], good[2]],
        "missing-size-payment": good,
        "redundant-d704-write": good,
    }
    for name, ownership in mutations.items():
        candidate_copy = [] if name == "missing-size-payment" else copy
        if name == "redundant-d704-write":
            candidate_copy = copy + [
                "    b523: 9c 04 d7      stz $d704",
            ]
        if not _handoff_z_abi_errors(
                ownership, candidate_copy, reveal, map_switch):
            raise AssertionError(f"handoff mutation accepted: {name}")
    reveal_mutations = {
        "missing-first-knock": reveal[1:],
        "wrong-second-knock": reveal[:2] + [
            "    b5cb: a9 52         lda #$52", *reveal[3:]],
    }
    for name, candidate_reveal in reveal_mutations.items():
        if not _handoff_z_abi_errors(
                good, copy, candidate_reveal, map_switch):
            raise AssertionError(f"handoff I/O mutation accepted: {name}")
    map_mutations = {
        "wrong-map-register-source": [
            "    b5d4: a9 01         lda #$1", *map_switch[1:]],
        "c000-plus-e000-map-mask": [
            *map_switch[:3], "    b5d4: a3 c0         ldz #$c0",
            *map_switch[4:]],
    }
    for name, bad_map_switch in map_mutations.items():
        if not _handoff_z_abi_errors(good, copy, reveal, bad_map_switch):
            raise AssertionError(f"handoff MAP-operand mutation accepted: {name}")
    return {
        "valid-sei-ldz-zero-prefix": "passed",
        "valid-mega65-io-knock": "passed",
        "missing-z-normalization": "rejected",
        "late-z-normalization": "rejected",
        "nonzero-z-normalization": "rejected",
        "missing-io-reveal-call": "rejected",
        "late-io-reveal-call": "rejected",
        "missing-first-knock": "rejected",
        "wrong-second-knock": "rejected",
        "missing-fixed-size-payment": "rejected",
        "redundant-d704-write": "rejected",
        "wrong-map-register-source": "rejected",
        "c000-plus-e000-map-mask": "rejected",
    }


def handoff_z_abi_gate(out: Path, target: Path,
                       suffix: str) -> dict[str, object]:
    elf = Path(str(target) + ".elf")
    disassembly = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)
    ], capture=True)
    nodes, _section_lines = _sectioned_disassembly(disassembly)
    ownership = [row for row in nodes.values()
                 if "c2_kernal_take_ownership" in row["names"]]
    copy = [row for row in nodes.values() if "c2k_copy" in row["names"]]
    reveal = [row for row in nodes.values()
              if "c2_kernal_reveal_io" in row["names"]]
    map_switch = [row for row in nodes.values()
                  if "c2_kernal_map_window" in row["names"]]
    if (len(ownership) != 1 or len(copy) != 1 or len(reveal) != 1
            or len(map_switch) != 1):
        raise RuntimeError(
            "handoff ABI red: ownership/copy/reveal/map function is not unique")
    errors = _handoff_z_abi_errors(
        ownership[0]["lines"], copy[0]["lines"], reveal[0]["lines"],
        map_switch[0]["lines"])
    if errors:
        raise RuntimeError(f"handoff ABI red: {errors}")
    sections = section_table(elf)
    handoff = sections.get(".lisp65_c2_kernal_handoff")
    if not handoff:
        raise RuntimeError("handoff ABI red: handoff section absent")
    report = {
        "format": "lisp65-c2-handoff-boundary-abi-v3",
        "status": "passed",
        "link_stage": suffix,
        "boundary": (
            "firmware-owned-state-to-llvm-mos-mega65-io-and-c2-ownership-order"
        ),
        "required_prefix": ["sei", "ldz #$00", "jsr $b5c9"],
        "observed_prefix": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(
                ownership[0]["lines"])[:3]
        ],
        "io_reveal_sequence": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(reveal[0]["lines"])
        ],
        "map_operand_sequence": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(
                map_switch[0]["lines"])
        ],
        "mapped_cpu_domain": (
            "0xe000-0xffff to physical bank-0; block-6 remains un-MAP so "
            "0xd000 I/O stays visible"
        ),
        "fixed_handoff_section": handoff,
        "size_payment": {
            "kept": "stz $d702",
            "omitted_as_controller-defined_side_effect": "write $d702 clears $d704",
        },
        "negative_matrix": _handoff_z_abi_model_selftest(),
        "hardware_origin": {
            "link_19": {
                "observed_z": "0x06",
                "effect": "C zero stores wrote 0x06 into IRQ controls and the DMA descriptor",
            },
            "link_20": {
                "observed_d700_cpu_view": "all zero / not MEGA65 I/O",
                "effect": "the correct descriptor was never triggered until the $47/$53 knock was repeated",
            },
            "link_23": {
                "observed_map_high": "0xc000",
                "effect": (
                    "mapping block 6 hid $d000 I/O behind Bank-0 RAM; the real "
                    "VIC raster IRQ could not be acknowledged and stormed"
                ),
            },
        },
        "claim_limit": (
            "Disassembly and mutation proof of the firmware-to-product Z and "
            "I/O-personality normalization boundary. Hardware execution is a separate gate."
        ),
    }
    write(out / f"handoff-z-abi-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _pre_ownership_violations(
        records: list[tuple[str, int, list[str]]], *,
        code_start: int, code_end: int, state_start: int, state_end: int,
        c2e_vector: int) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for label, address, lines in records:
        if code_start <= address < code_end:
            violations.append({"node": label,
                               "reason": "session-code-in-boot-closure"})
        for line in lines:
            call = re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", line)
            if call and code_start <= int(call.group(1), 16) < code_end:
                violations.append({"node": label,
                                   "reason": "session-code-edge-from-boot-closure",
                                   "instruction": line.strip()})
            operands = [int(item, 16)
                        for item in re.findall(r"\$([0-9a-f]{2,4})\b", line)]
            if any(state_start <= operand < state_end for operand in operands):
                violations.append({"node": label,
                                   "reason": "session-state-in-boot-closure",
                                   "instruction": line.strip()})
            if c2e_vector in operands:
                violations.append({"node": label,
                                   "reason": "session-cons-vector-in-boot-closure",
                                   "instruction": line.strip()})
    return violations


def _pre_handoff_fixed_domain_violations(
        records: list[tuple[str, int, list[str]]], *,
        fixed_start: int, fixed_end: int,
        window_start: int, window_end: int) -> list[dict[str, object]]:
    """Reject every C2 fixed-domain consumer before the ownership call."""
    violations: list[dict[str, object]] = []
    domains = (
        ("fixed-bank0", fixed_start, fixed_end),
        ("kernal-window", window_start, window_end),
    )
    for label, address, lines in records:
        for domain, start, end in domains:
            if start <= address < end:
                violations.append({
                    "node": label,
                    "reason": f"pre-handoff-node-in-{domain}",
                    "address": f"0x{address:04x}",
                })
        for line in lines:
            instructions = _machine_instructions([line])
            if not instructions:
                continue
            _mnemonic, operand = instructions[0]
            if operand.startswith("#"):
                continue
            addresses = [int(item, 16)
                         for item in re.findall(r"\$([0-9a-f]{4})\b", operand)]
            for domain, start, end in domains:
                if any(start <= value < end for value in addresses):
                    violations.append({
                        "node": label,
                        "reason": f"pre-handoff-operand-in-{domain}",
                        "instruction": line.strip(),
                    })
    return violations


def _source_ownership_order_errors(source: str) -> list[str]:
    # Gate executable source, not explanatory prose that may name the same
    # call.  String literals in this narrow main.c region do not contain any
    # of the bound call tokens.
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source,
                    flags=re.DOTALL)
    calls = {
        "ownership": "c2_kernal_take_ownership()",
        "overlay-install": "vm_install_staged_boot_overlay()",
        "prepare": "c2_product_prepare_boot()",
        "boot": "c2_product_boot()",
        "repl": "repl()",
    }
    positions: dict[str, int] = {}
    errors: list[str] = []
    for name, token in calls.items():
        if source.count(token) != 1:
            errors.append(f"source-call-not-unique:{name}")
        else:
            positions[name] = source.index(token)
    if len(positions) == len(calls):
        if positions["ownership"] > positions["overlay-install"]:
            errors.append("overlay-install-precedes-ownership")
        if positions["ownership"] > positions["prepare"]:
            errors.append("prepare-precedes-ownership")
        if positions["ownership"] > positions["boot"]:
            errors.append("boot-precedes-ownership")
        if positions["ownership"] > positions["repl"]:
            errors.append("repl-precedes-ownership")
    return errors


def _pre_ownership_model_selftest() -> dict[str, str]:
    synthetic = """\
Disassembly of section .boot-a:
0000c356 <root_a>:
    c356: 60            rts
Disassembly of section .boot-b:
0000c356 <root_b>:
    c356: 60            rts
"""
    nodes, _lines = _sectioned_disassembly(synthetic)
    if set(nodes) != {(".boot-a", 0xC356), (".boot-b", 0xC356)}:
        raise AssertionError("section-qualified same-VMA roots collapsed")

    mutations = {
        "boot-edge-to-session-code": "    c356: 20 9e e0      jsr $e09e",
        "boot-operand-to-session-state": "    c356: ad 5f f1      lda $f15f",
        "boot-edge-to-c2e-cons-vector": "    c356: 20 ab b5      jsr $b5ab",
    }
    expected = {
        "boot-edge-to-session-code": "session-code-edge-from-boot-closure",
        "boot-operand-to-session-state": "session-state-in-boot-closure",
        "boot-edge-to-c2e-cons-vector": "session-cons-vector-in-boot-closure",
    }
    for name, instruction in mutations.items():
        reasons = {row["reason"] for row in _pre_ownership_violations(
            [(name, 0xC356, [instruction])], code_start=0xE09E,
            code_end=0xE0C6, state_start=0xF15F, state_end=0xF2B9,
            c2e_vector=0xB5AB)}
        if expected[name] not in reasons:
            raise AssertionError(f"pre-ownership mutation accepted: {name}")
    boundary_mutations = {
        "pre-handoff-edge-to-kernal-window": (
            "    4600: 20 6f e1      jsr $e16f",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-edge-to-vm-logical-pc-helper": (
            "    4600: 20 20 e8      jsr $e820",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-edge-to-c2-root-walker": (
            "    4600: 20 80 e9      jsr $e980",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-operand-to-fixed-state": (
            "    4600: 9c b2 c0      stz $c0b2",
            "pre-handoff-operand-in-fixed-bank0"),
    }
    for name, (instruction, expected_reason) in boundary_mutations.items():
        reasons = {row["reason"] for row in
                   _pre_handoff_fixed_domain_violations(
                       [(name, 0x4600, [instruction])],
                       fixed_start=FIXED_BANK0_BASE,
                       fixed_end=FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES,
                       window_start=KERNAL_WINDOW_BASE,
                       window_end=KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES)}
        if expected_reason not in reasons:
            raise AssertionError(f"pre-handoff mutation accepted: {name}")
    source_good = """
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
repl();
"""
    if _source_ownership_order_errors(source_good):
        raise AssertionError("valid ownership source order was rejected")
    source_mutations = {
        "overlay-install-before-ownership": """
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
repl();
""",
        "prepare-before-ownership": """
if (!c2_product_prepare_boot()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_boot()) return 1;
repl();
""",
        "boot-before-ownership": """
if (!c2_product_boot()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
repl();
""",
        "repl-before-ownership": """
repl();
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
""",
    }
    for name, candidate in source_mutations.items():
        if not _source_ownership_order_errors(candidate):
            raise AssertionError(f"ownership-order mutation accepted: {name}")
    return {
        "same-vma-section-identity": "passed",
        "boot-edge-to-session-code": "rejected",
        "boot-operand-to-session-state": "rejected",
        "boot-edge-to-c2e-cons-vector": "rejected",
        "pre-handoff-edge-to-kernal-window": "rejected",
        "pre-handoff-edge-to-vm-logical-pc-helper": "rejected",
        "pre-handoff-edge-to-c2-root-walker": "rejected",
        "pre-handoff-operand-to-fixed-state": "rejected",
        "overlay-install-before-ownership": "rejected",
        "prepare-before-ownership": "rejected",
        "boot-before-ownership": "rejected",
        "repl-before-ownership": "rejected",
    }


def pre_ownership_gate(out: Path, target: Path, suffix: str) -> dict[str, object]:
    """Prove ownership precedes fixed-domain use and isolates session state."""
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    code = sections.get(".lisp65_c2_kernal_window.session_emitter_code")
    state = sections.get(".lisp65_c2_kernal_window.session_emitter_state")
    resident = sections.get(".lisp65_c2_kernal_window.c2_resident")
    if ((code is not None and code["bytes"] != 0) or not state or
            state["bytes"] != SESSION_EMITTER_STATE_BYTES):
        raise RuntimeError(
            f"pre-ownership red: session E000 geometry code={code} state={state}")
    code = code or {"address": 0, "bytes": 0}
    if not resident or not resident["bytes"]:
        raise RuntimeError("pre-ownership red: C2 resident window absent")
    post_handoff_helpers = {
        name: symbols.get(name) for name in (
            "vm_logical_relative_target", "c2_product_gc_mark_roots")
    }
    helper_drift = {
        name: address for name, address in post_handoff_helpers.items()
        if address is None or not (
            resident["address"] <= address
            < resident["address"] + resident["bytes"])
    }
    if helper_drift:
        raise RuntimeError(
            f"pre-ownership red: post-handoff helper placement {helper_drift}")

    disassembly = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)
    ], capture=True)
    nodes, section_lines = _sectioned_disassembly(disassembly)
    boot_contract = [(fields[2].lower(), fields[-1].lower())
                     for spec in BOOT_SLICE_SPECS
                     if len(fields := spec.split(":")) == 10]
    if len(boot_contract) != len(BOOT_SLICE_SPECS):
        raise RuntimeError("pre-ownership red: malformed generated boot slice spec")
    root_nodes: list[tuple[str, int]] = []
    missing_roots: list[dict[str, str]] = []
    for section, entry in boot_contract:
        matches = [key for key, row in nodes.items()
                   if key[0] == section and entry in row["names"]]
        if len(matches) != 1:
            missing_roots.append({"section": section, "entry": entry,
                                  "matches": str(len(matches))})
        else:
            root_nodes.append(matches[0])
    if missing_roots:
        raise RuntimeError(f"pre-ownership red: boot roots unresolved {missing_roots}")

    runtime_sections = {spec.split(":")[2].lower()
                        for spec in BOOT_SLICE_SPECS + SESSION_SLICE_SPECS}
    runtime_sections.add(".lisp65_workbench_overlay")
    ordinary_nodes = {
        key: row for key, row in nodes.items()
        if key[0] not in runtime_sections and not key[0].startswith(".lisp65_rt_")
    }
    address_to_ordinary: dict[int, list[tuple[str, int]]] = {}
    for key in ordinary_nodes:
        address_to_ordinary.setdefault(key[1], []).append(key)

    main_nodes = [key for key, row in ordinary_nodes.items()
                  if "main" in row["names"]]
    ownership_address = symbols.get("c2_kernal_take_ownership")
    if len(main_nodes) != 1 or ownership_address is None:
        raise RuntimeError("pre-ownership red: main or ownership symbol absent")
    main_node = main_nodes[0]
    main_lines: list[str] = ordinary_nodes[main_node]["lines"]
    main_prefix: list[str] = []
    handoff_seen = False
    for line in main_lines:
        call = re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", line)
        if call and int(call.group(1), 16) == ownership_address:
            handoff_seen = True
            break
        main_prefix.append(line)
    if not handoff_seen:
        raise RuntimeError("pre-ownership red: main has no explicit ownership cutpoint")

    boot_records: list[tuple[str, int, list[str]]] = []
    boot_pending: list[tuple[str, int]] = []
    for section, _entry in boot_contract:
        geometry = sections.get(section)
        lines = section_lines.get(section)
        if geometry is None or lines is None:
            raise RuntimeError(f"pre-ownership red: boot section absent {section}")
        boot_records.append((f"boot-section:{section}", geometry["address"], lines))
        section_end = geometry["address"] + geometry["bytes"]
        for target_address in _direct_call_targets(lines):
            if geometry["address"] <= target_address < section_end:
                continue
            boot_pending.extend(address_to_ordinary.get(target_address, []))
    pre_handoff_pending: list[tuple[str, int]] = []
    for target_address in _direct_call_targets(main_prefix):
        pre_handoff_pending.extend(address_to_ordinary.get(target_address, []))

    def collect_closure(pending: list[tuple[str, int]]) -> set[tuple[str, int]]:
        closure: set[tuple[str, int]] = set()
        pending = pending.copy()
        while pending:
            key = pending.pop()
            if key in closure:
                continue
            closure.add(key)
            for target_address in _direct_call_targets(
                    ordinary_nodes[key]["lines"]):
                pending.extend(candidate for candidate in
                               address_to_ordinary.get(target_address, [])
                               if candidate not in closure)
        return closure

    pre_handoff_closure = collect_closure(pre_handoff_pending)
    closure = collect_closure(boot_pending + pre_handoff_pending)

    records = boot_records + [
        (f"{key[0]}:{'/'.join(ordinary_nodes[key]['names'])}", key[1],
         ordinary_nodes[key]["lines"])
        for key in sorted(closure)
    ]
    records.append(("main-before-c2-kernal-take-ownership",
                    main_node[1], main_prefix))
    pre_handoff_records = [
        (f"{key[0]}:{'/'.join(ordinary_nodes[key]['names'])}", key[1],
         ordinary_nodes[key]["lines"])
        for key in sorted(pre_handoff_closure)
    ]
    pre_handoff_records.append(("main-before-c2-kernal-take-ownership",
                                main_node[1], main_prefix))
    boundary_violations = _pre_handoff_fixed_domain_violations(
        pre_handoff_records,
        fixed_start=FIXED_BANK0_BASE,
        fixed_end=FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES,
        window_start=KERNAL_WINDOW_BASE,
        window_end=KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES)
    if boundary_violations:
        raise RuntimeError(
            f"pre-ownership red: fixed-domain use before handoff "
            f"{boundary_violations}")
    violations = _pre_ownership_violations(
        records, code_start=code["address"],
        code_end=code["address"] + code["bytes"],
        state_start=state["address"],
        state_end=state["address"] + state["bytes"],
        c2e_vector=symbols.get("c2_facade_c2e_cons", -1))
    if violations:
        raise RuntimeError(f"pre-ownership red: {violations}")

    main_source = (ROOT / "src/main.c").read_text(encoding="utf-8")
    source_order_errors = _source_ownership_order_errors(main_source)
    if source_order_errors:
        raise RuntimeError(
            f"pre-ownership red: source handoff order drift {source_order_errors}")

    negative_matrix = _pre_ownership_model_selftest()
    report = {
        "format": "lisp65-c2-pre-ownership-closure-v3",
        "status": "passed",
        "link_stage": suffix,
        "node_identity": "section-and-vma",
        "boot_roots": [
            {"section": section, "entry": entry,
             "vma": next(key[1] for key in root_nodes if key[0] == section)}
            for section, entry in boot_contract
        ],
        "boot_section_count": len(boot_records),
        "ordinary_closure_function_count": len(closure),
        "pre_handoff_closure_function_count": len(pre_handoff_closure),
        "pre_handoff_fixed_domain": {
            "fixed_bank0": (
                f"0x{FIXED_BANK0_BASE:04x}-"
                f"0x{FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES - 1:04x}"
            ),
            "kernal_window": "0xe000-0xffff",
            "consumer_count": 0,
        },
        "post_handoff_only_helpers": {
            name: f"0x{address:04x}"
            for name, address in post_handoff_helpers.items()
        },
        "session_emitter_code": code,
        "session_emitter_state": state,
        "session_code_edges_from_boot_closure": 0,
        "session_state_operands_from_boot_closure": 0,
        "session_cons_vector_edges_from_boot_closure": 0,
        "negative_matrix": negative_matrix,
        "source_order": (
            "c2_kernal_take_ownership-before-overlay-install-"
            "c2_product_prepare_boot-c2_product_boot-and-repl"
        ),
        "claim_limit": (
            "Section-qualified direct pre-handoff and boot-phase closures plus "
            "source-order gate; hardware behavior and unresolved indirect call "
            "targets are not claimed."
        ),
    }
    write(out / f"pre-ownership-closure-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _owned_edge_violation(
        opcode: str, source_node: tuple[str, int], target: int,
        instruction_owners: dict[int, tuple[str, int]],
        function_entries: set[int]) -> str | None:
    """Classify one direct edge into the owned CPU window.

    Function entries are deliberately T/t-only.  Absolute and weak aliases are
    not passed to this function and can therefore never manufacture ownership.
    """
    target_node = instruction_owners.get(target)
    if target_node is None:
        return "target-not-owned-executable-instruction"
    if opcode == "jsr":
        return None if target in function_entries else "jsr-not-function-entry"
    if opcode != "jmp":
        return "unsupported-direct-edge-opcode"
    if target_node == source_node:
        return None
    return None if target in function_entries else "inter-function-jmp-not-entry"


def _owned_control_flow_model_selftest() -> dict[str, str]:
    first = (".owned.code", 0xE000)
    second = (".owned.code", 0xE010)
    instruction_owners = {
        0xE000: first,
        0xE003: first,
        0xE010: second,
        0xE011: second,
    }
    function_entries = {0xE000, 0xE010}
    cases = {
        "same-function-symbol-less-basic-block": (
            "jmp", first, 0xE003, None),
        "same-function-mid-instruction": (
            "jmp", first, 0xE002,
            "target-not-owned-executable-instruction"),
        "owned-state-or-data-target": (
            "jmp", first, 0xFF80,
            "target-not-owned-executable-instruction"),
        "inter-function-non-entry-offset": (
            "jmp", first, 0xE011,
            "inter-function-jmp-not-entry"),
        "jsr-to-internal-basic-block": (
            "jsr", first, 0xE003, "jsr-not-function-entry"),
        # $ffd2 is deliberately imagined to exist in an unfiltered nm alias
        # set.  It is absent from T/t executable entries and must stay red.
        "absolute-weak-alias-disguised-exit": (
            "jmp", first, 0xFFD2,
            "target-not-owned-executable-instruction"),
    }
    result: dict[str, str] = {}
    for name, (opcode, source, target, expected) in cases.items():
        actual = _owned_edge_violation(
            opcode, source, target, instruction_owners, function_entries)
        if actual != expected:
            raise AssertionError(
                f"owned-control-flow selftest {name}: {actual} != {expected}")
        result[name] = "passed" if expected is None else "rejected"
    return result


def _owned_control_flow_gate(elf: Path, sections: dict[str, dict[str, int]],
                             objdump: str,
                             symbols_text: str) -> dict[str, object]:
    non_executable = {
        ".lisp65_c2_kernal_window.session_emitter_state",
        ".lisp65_c2_kernal_window.state",
        ".lisp65_c2_vectors",
    }
    executable_sections = {
        name for name in KERNAL_SECTIONS
        if name not in non_executable and sections.get(name, {}).get("bytes", 0)
    }
    nodes, _section_lines = _sectioned_disassembly(objdump)
    owned_nodes = {
        key: row for key, row in nodes.items() if key[0] in executable_sections
    }
    instruction_owners: dict[int, tuple[str, int]] = {}
    for key, row in owned_nodes.items():
        for line in row["lines"]:
            match = re.match(r"^\s*([0-9a-f]+):\s", line)
            if not match:
                continue
            address = int(match.group(1), 16)
            previous = instruction_owners.get(address)
            if previous is not None and previous != key:
                raise RuntimeError(
                    f"KERNAL freedom red: ambiguous instruction owner at 0x{address:04x}")
            instruction_owners[address] = key

    function_entries: dict[int, str] = {}
    ignored_aliases: list[str] = []
    for line in symbols_text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        address = int(fields[0], 16)
        symbol_type = fields[1]
        name = fields[-1]
        if not KERNAL_WINDOW_BASE <= address < KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES:
            continue
        if symbol_type in {"t", "T"} and address in instruction_owners:
            function_entries[address] = name
        elif symbol_type in {"a", "A", "w", "W"}:
            ignored_aliases.append(name)

    violations: list[dict[str, object]] = []
    internal_basic_block_jumps = 0
    entry_edges = 0
    direct_window_edges = 0
    audited_pre_main_chrout = 0
    for source_node, row in nodes.items():
        for line in row["lines"]:
            edge = re.search(
                r"\b(jsr|jmp)\s+\$([ef][0-9a-f]{3})\b", line)
            if not edge:
                continue
            opcode = edge.group(1)
            target = int(edge.group(2), 16)
            direct_window_edges += 1
            if (opcode == "jsr" and target == 0xFFD2 and
                    "shift" in row["names"]):
                audited_pre_main_chrout += 1
                continue
            reason = _owned_edge_violation(
                opcode, source_node, target, instruction_owners,
                set(function_entries))
            if reason is not None:
                violations.append({
                    "source_section": source_node[0],
                    "source_function_address": f"0x{source_node[1]:04x}",
                    "opcode": opcode,
                    "target": f"0x{target:04x}",
                    "reason": reason,
                    "instruction": line.strip(),
                })
            elif (opcode == "jmp" and
                  instruction_owners.get(target) == source_node and
                  target not in function_entries):
                internal_basic_block_jumps += 1
            else:
                entry_edges += 1
    if audited_pre_main_chrout != 1:
        violations.append({
            "reason": "audited-pre-main-chrout-count",
            "actual": audited_pre_main_chrout,
            "expected": 1,
        })
    if violations:
        raise RuntimeError(f"KERNAL freedom red: qualified edge violations {violations}")

    return {
        "model": "section-qualified-function-and-instruction-boundary-v1",
        "executable_sections": sorted(executable_sections),
        "owned_function_entries": dict(sorted(function_entries.items())),
        "ignored_absolute_or_weak_alias_count": len(set(ignored_aliases)),
        "direct_window_edges": direct_window_edges,
        "entry_edges": entry_edges,
        "same_function_basic_block_jumps": internal_basic_block_jumps,
        "audited_pre_main_chrout_edges": audited_pre_main_chrout,
        "violations": [],
        "matrix": _owned_control_flow_model_selftest(),
    }


def kernal_freedom_gate(out: Path, final: Path) -> dict[str, object]:
    elf = Path(str(final) + ".elf")
    sections = section_table(elf)
    missing = [name for name in KERNAL_SECTIONS if name not in sections]
    if missing:
        raise RuntimeError(f"KERNAL freedom red: missing owned sections {missing}")
    live_window = {
        name: row for name, row in sections.items()
        if KERNAL_WINDOW_BASE <= row["address"] < KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES
        and row["bytes"]
    }
    unknown = sorted(set(live_window) - set(KERNAL_SECTIONS))
    if unknown:
        raise RuntimeError(f"KERNAL freedom red: unnamed window occupants {unknown}")

    objdump = run([str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)], capture=True).lower()
    undefined = run([str(TOOLCHAIN / "llvm-nm"), "--undefined-only", str(elf)], capture=True)
    if re.search(r"\b(?:cbm_k_getin|cbm_k_chrout|cbm_k_open|cbm_k_load)\b", undefined):
        raise RuntimeError("KERNAL freedom red: CBM-I/O member remains unresolved")
    if re.search(r"\b(?:jsr|jmp)\s+\$ffe4\b", objdump):
        raise RuntimeError("KERNAL freedom red: post-startup GETIN edge")
    if re.search(r"\b(?:lda|ldx|ldy|sta|stx|sty|inc|dec|bit)\s+\$91\b", objdump):
        raise RuntimeError("KERNAL freedom red: retired STKEY operand")
    chrout_edges = len(re.findall(r"\bjsr\s+\$ffd2\b", objdump))
    if chrout_edges != 1:
        raise RuntimeError(
            f"KERNAL freedom red: expected one audited pre-main CHROUT, found {chrout_edges}")

    window_dis = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d",
        "--section=.lisp65_c2_kernal_window.typed_queue_driver", str(elf)
    ], capture=True).lower()
    if window_dis.count("$d60a") != 1 or window_dis.count("$d619") != 2:
        raise RuntimeError("KERNAL freedom red: typed queue is not one-head/one-dequeue")

    symbols_text = run([
        str(TOOLCHAIN / "llvm-nm"), "--defined-only", "--numeric-sort", str(elf)
    ], capture=True)
    control_flow = _owned_control_flow_gate(
        elf, sections, objdump, symbols_text)

    category_sections = {
        "typed_queue_driver": [
            ".lisp65_c2_kernal_window.typed_queue_driver",
            ".lisp65_c2_kernal_window.event_poll",
        ],
        "irq_handler": [".lisp65_c2_kernal_window.irq_handler"],
        "nmi_and_freezer_return": [".lisp65_c2_kernal_window.nmi_and_freezer_return"],
        "frame_source": [".lisp65_c2_kernal_window.frame_source"],
        "map_switch_and_guards": [
            ".lisp65_c2_kernal_window.map_switch_and_guards",
            ".lisp65_c2_kernal_handoff", ".lisp65_c2_kernal_io_reveal",
            ".lisp65_c2_kernal_map_switch"],
        "post_startup_output_seam": [
            ".lisp65_c2_kernal_window.post_startup_output_seam"],
        "alignment_and_vectors": [
            ".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors"],
    }
    categories = {
        name: sum(sections.get(section, {}).get("bytes", 0) for section in names)
        for name, names in category_sections.items()
    }
    replacement = sum(categories.values())
    relocated = sum(
        sections[name]["bytes"] for name in (
            ".lisp65_c2_kernal_window.c2_resident",
            ".lisp65_c2_kernal_window.session_emitter_state",
        ))
    if relocated < 3639:
        raise RuntimeError(
            f"KERNAL freedom red: relocated C2 residents {relocated} < deficit 3639")
    contract_future = KERNAL_WINDOW_BYTES - 3639 - replacement
    actual_live = sum(row["bytes"] for row in live_window.values())
    actual_future = KERNAL_WINDOW_BYTES - actual_live
    if contract_future <= 0 or actual_future <= 0:
        raise RuntimeError(
            f"KERNAL freedom red: future margins contract={contract_future} actual={actual_future}")

    report = {
        "format": "lisp65-c2-kernal-freedom-link-v2",
        "status": "passed",
        "orphan_policy": {
            "mode": "error",
            "exact_non_alloc_allowlist": list(ORPHAN_ALLOWLIST),
            "error_callsites_required": True,
        },
        "owned_sections": live_window,
        "control_flow_ownership": control_flow,
        "forbidden_edges": {"getin": 0, "stkey": 0,
                            "unowned_window_targets": 0,
                            "audited_pre_main_chrout": chrout_edges},
        "source_census": {"typed_input_paths": 1, "abort_sources": 1,
                          "frame_owners": 1},
        "capacity": {
            "gross_window_bytes": KERNAL_WINDOW_BYTES,
            "fixed_resident_deficit_bytes": 3639,
            "replacement_categories": categories,
            "replacement_resident_bytes": replacement,
            "contract_future_margin_bytes": contract_future,
            "relocated_c2_resident_bytes": relocated,
            "actual_live_window_bytes": actual_live,
            "actual_future_margin_bytes": actual_future,
        },
        "window_artifact": {
            "path": str((out / "c2-product-kernal-window.bin").relative_to(ROOT)),
            "bytes": KERNAL_WINDOW_BYTES,
            "sha256": hashlib.sha256(
                (out / "c2-product-kernal-window.bin").read_bytes()).hexdigest(),
        },
    }
    write(out / "kernal-freedom-link.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def substitution_balance(out: Path, final: Path,
                         kernal: dict[str, object]) -> dict[str, object]:
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads((out / "runtime-overlays-session-final.json").read_text())
    c2d = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
    shelf = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
    sections = section_table(Path(str(final) + ".elf"))
    bank0 = sum(
        row["bytes"] for name, row in sections.items()
        if name in {".lisp65_c2_kernal_handoff", ".lisp65_c2_host_facade",
                    ".lisp65_c2_kernal_io_reveal",
                    ".lisp65_c2_kernal_map_switch", ".lisp65_c2_kernal_state",
                    ".lisp65_c2_fixed_bank0", ".lisp65_c2_fixed_bank0_code",
                    ".lisp65_c2_fixed_zp"})
    report = {
        "format": "lisp65-c2-product-substitution-balance-v1",
        "status": "passed",
        "projection_vs_actual": {
            "retirements": {
                "l65m_materializer": {"projected_runtime_bank_bytes": 36744,
                                      "actual_legacy_closure_edges": 0},
                "l65m_runtime_slices": {"projected_count": 28,
                                        "actual_remaining_count": 0},
                "old_directory_arrays": {"projected_bank0_credit_bytes": 697,
                                         "actual_remaining_legacy_arrays": 0},
                "kernal_window": {"projected_cpu_window_bytes": 8192,
                                  "actual_owned_cpu_window_bytes": 8192},
            },
            "arrivals": {
                "c2_decoder_emitter_append_and_services": {
                    "boot_family_image_bytes": boot["storage"]["size"],
                    "session_family_image_bytes": session["storage"]["size"],
                    "boot_slices": len(boot["slices"]),
                    "session_slices": len(session["slices"]),
                },
                "c2d_mutable_plane": {"bytes": c2d.stat().st_size},
                "immutable_shelf": {"bytes": shelf.stat().st_size},
                "resident_facades_and_state": {
                    "bank0_and_fixed_zp_bytes": bank0,
                    "fixed_host_vector_bytes": len(HOST_FACADE_SYMBOLS)
                    * HOST_FACADE_STRIDE,
                    "fixed_bank0_state_bytes": FIXED_BANK0_BYTES,
                    "fixed_bank0_code_bytes": FIXED_BANK0_CODE_BYTES,
                    "fixed_bank0_headroom_bytes": FIXED_BANK0_HEADROOM_BYTES,
                    "fixed_zero_page_state_bytes": FIXED_ZP_BYTES,
                    "non_lto_verifier_binding_bytes": VERIFIER_BINDING_BYTES,
                },
                "typed_queue_irq_nmi_and_window": kernal["capacity"],
            },
        },
        "currencies": {
            "runtime_overlay_bank": {
                "retired_l65m_bytes": 36744,
                "boot_image_bytes": boot["storage"]["size"],
                "session_image_bytes": session["storage"]["size"],
                "families_are_lifetime_exclusive": True,
            },
            "bank5_mutable_plane": {"c2d_bytes": c2d.stat().st_size,
                                    "capacity_bytes": 65536,
                                    "headroom_bytes": 65536 - c2d.stat().st_size},
            "attic_immutable": {"shelf_bytes": shelf.stat().st_size},
            "bank0": {"retired_directory_projection_bytes": 697,
                      "new_kernal_facade_and_state_bytes": bank0,
                      "fixed_host_vector_bytes": len(HOST_FACADE_SYMBOLS)
                      * HOST_FACADE_STRIDE,
                      "fixed_bank0_state_bytes": FIXED_BANK0_BYTES,
                      "fixed_bank0_code_bytes": FIXED_BANK0_CODE_BYTES,
                      "fixed_bank0_headroom_bytes": FIXED_BANK0_HEADROOM_BYTES,
                      "fixed_zero_page_state_bytes": FIXED_ZP_BYTES},
            "publish_last_binding": {
                "retired_embedded_tuple_bytes": VERIFIER_BINDING_BYTES,
                "non_lto_table_bytes": VERIFIER_BINDING_BYTES,
                "net_resident_bytes": 0,
            },
            "cpu_e000_window": kernal["capacity"],
        },
    }
    write(out / "substitution-balance.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def closure_gate(out: Path, final: Path) -> None:
    forbidden_sources = sorted(LEGACY_C | {"l65m_batch_repeat.s"})
    maps = (Path(str(final) + ".map").read_text(encoding="utf-8", errors="replace"))
    bad_sources = [name for name in forbidden_sources if name in maps]
    symbols = run([str(TOOLCHAIN / "llvm-nm"), "--defined-only", str(final) + ".elf"], capture=True)
    forbidden_symbols = re.findall(
        r"\b(?:l65m_|lcc_install_|vm_boot_fastpath_|l65s_|lisp65_c1_)\w+", symbols
    )
    payloads = [
        final, out / "runtime-overlays-final.bin",
        out / "runtime-overlays-boot-final.bin",
        out / "runtime-overlays-session-final.bin",
        ROOT / "build/c2.2/substitution/initial.c2d-v3.bin",
        ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin",
    ]
    magic_hits = [str(path) for path in payloads if b"L65M" in path.read_bytes()]
    if bad_sources or forbidden_symbols or magic_hits:
        raise RuntimeError(
            f"one-truth closure red: sources={bad_sources} "
            f"symbols={sorted(set(forbidden_symbols))} magic={magic_hits}"
        )
    report = {
        "format": "lisp65-c2-one-truth-closure-v1",
        "legacy_sources_in_map": [],
        "legacy_symbols": [],
        "l65m_magic_payloads": [],
        "runtime_slice_count_unique": UNIQUE_SLICE_COUNT,
        "runtime_families": {
            "boot": len(BOOT_SLICE_SPECS),
            "session": len(SESSION_SLICE_SPECS),
        },
        "status": "passed",
    }
    write(out / "one-truth-closure.json", json.dumps(report, indent=2, sort_keys=True) + "\n")


def finish_single_link(out: Path, final: Path, contract: Path,
                       window_pin: dict[str, object],
                       window_pin_source: str) -> None:
    """Finish an already emitted sole product link without relinking it."""
    extract_pinned_kernal_window(out, final, window_pin)
    handoff_z_abi_gate(out, final, "final")
    pre_ownership_gate(out, final, "final")
    fixed_facade_gate(out, final, "final")
    unbound_boot = overlay_pack_family(
        out, final, contract, "boot", "unbound")
    unbound_session = overlay_pack_family(
        out, final, contract, "session", "unbound")
    binding = patch_verifier_binding_table(
        out, final, unbound_boot[1], unbound_session[1])
    final_boot = overlay_pack_family(out, final, contract, "boot", "final")
    final_session = overlay_pack_family(
        out, final, contract, "session", "final")
    family_identity = runtime_family_identity_gate(
        out, unbound_boot, unbound_session, final_boot, final_session)
    _boot_image, _boot_manifest = final_boot
    session_image, _session_manifest = final_session
    write(out / "runtime-overlays-final.bin", session_image.read_bytes())
    closure_gate(out, final)
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)
    write(out / "eighteenth-substitution-link.json", json.dumps({
        "format": "lisp65-c2-eighteenth-substitution-link-v1",
        "status": "passed",
        "product": str(final.relative_to(ROOT)),
        "product_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "identity_gate": "passed",
        "identity_components": {
            "kernal_window_sha_crc_pin": "passed",
            "verifier_publish_last_32_bytes": binding["status"],
            "all_runtime_family_records_and_payloads": family_identity["status"],
            "mutated_payload_negative": family_identity["mutated_payload_negative"],
        },
        "kernal_window_identity_source": window_pin_source,
        "product_closure_link_count": 1,
        "resident_island_seed_link_count": 1,
        "capacity_gate": "passed",
        "one_truth_gate": "passed",
        "kernal_freedom_gate": "passed",
        "fixed_host_facade_gate": "passed",
        "pre_ownership_gate": "passed",
        "handoff_z_abi_gate": "passed",
        "fixed_bank0_headroom_bytes": FIXED_BANK0_HEADROOM_BYTES,
        "substitution_balance": "passed",
        "actual_e000_future_margin_bytes": kernal["capacity"]["actual_future_margin_bytes"],
        "runtime_family_headroom_bytes": {
            "boot": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "claim_limit": (
            "Real single-product-closure C2 substitution link and structural "
            "closure only; the prerequisite resident-island seed materializer "
            "is separately counted. No hardware acceptance or promotion claim."
        ),
    }, indent=2, sort_keys=True) + "\n")
    print("c2-product-substitution-link: PASS "
          f"prg={final} families=boot:{len(BOOT_SLICE_SPECS)},"
          f"session:{len(SESSION_SLICE_SPECS)} "
          f"e000-margin={kernal['capacity']['actual_future_margin_bytes']}")


def whole_phase_facade_probe(out: Path) -> None:
    """One bounded capacity/control-flow probe; never a product candidate."""
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_window_pin = kernal_window_identity_pin()
    out.mkdir(parents=True, exist_ok=True)
    old_window_source = verify_kernal_window_pin_source(out, old_window_pin)
    write(out / "c2-substitution.ld", linker_script())
    contract_lines = [
        "profile=" + PROFILE,
        "mode=link24-latency-whole-phase-facade-capacity-probe",
        "hardware_execution=prohibited-unpinned-window",
        "c2_artifacts_sha256="
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256="
        + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "baseline_kernal_window_identity_sha256=" + str(old_window_pin["sha256"]),
        "baseline_kernal_window_identity_crc16=" + str(old_window_pin["crc16"]),
        "product_closure_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:"
            f"{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    island_header = out / "resident-island.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"

    # The probe intentionally compiles against the last accepted header while
    # measuring a new provisional window.  It can prove capacity and control
    # flow, but it cannot run on hardware or claim identity until a separately
    # authorized pin/link cycle publishes that new window.
    write(kernal_header_path, kernal_header_values(
        int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE)
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare",
         "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header),
         "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    common = [stage_header, runtime_prepared, island_prepared, error_header]
    seed = compile_link(out, "resident-island-seed.prg", common, artifacts)
    tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
         "--nm", str(TOOLCHAIN / "llvm-nm"),
         "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
         "--abi-contract", str(contract), "--header", str(island_header))
    final = compile_link(
        out, "whole-phase-facade-probe.prg",
        [stage_header, runtime_prepared, island_header,
         error_header, kernal_header_path], artifacts)

    provisional_window = extract_provisional_kernal_window(out, final)
    handoff_z_abi_gate(out, final, "probe")
    pre_ownership_gate(out, final, "probe")
    fixed_facade_gate(out, final, "probe")
    unbound_boot = overlay_pack_family(
        out, final, contract, "boot", "unbound")
    unbound_session = overlay_pack_family(
        out, final, contract, "session", "unbound")
    binding = patch_verifier_binding_table(
        out, final, unbound_boot[1], unbound_session[1])
    final_boot = overlay_pack_family(out, final, contract, "boot", "final")
    final_session = overlay_pack_family(
        out, final, contract, "session", "final")
    family_identity = runtime_family_identity_gate(
        out, unbound_boot, unbound_session, final_boot, final_session)
    write(out / "runtime-overlays-final.bin", final_session[0].read_bytes())
    closure_gate(out, final)
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)

    sections = section_table(Path(str(final) + ".elf"))
    phases = {
        name: sections[f".lisp65_rt_c2d_{name}"]["bytes"]
        for name, _entry in C2_DECODER_SLICES
    }
    largest_name = max(phases, key=phases.get)
    smallest_headroom = 1792 - phases[largest_name]
    baseline_path = (ROOT / "build/c2.2/substitution/"
                     "product-link-24-ownership-io-safe-map/"
                     "kernal-freedom-link.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_window = baseline["capacity"]
    new_window = kernal["capacity"]
    baseline_transports = 21068
    whole_phase_boot_transports = 14
    baseline_seconds = 12 * 60
    projected_transport_seconds = (
        baseline_seconds * whole_phase_boot_transports / baseline_transports)

    report = {
        "format": "lisp65-c2-link24-whole-phase-facade-capacity-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-capacity-and-structural-probe-only",
        "scope": {
            "trigger": "Link 24 eventually reached phase 13 and the REPL but cold boot took about twelve minutes",
            "product_links": 1,
            "resident_island_seed_links": 1,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
            "link25": "not-created",
        },
        "identities": {
            "probe_prg": str(final.relative_to(ROOT)),
            "probe_prg_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "probe_elf_sha256": hashlib.sha256(
                Path(str(final) + ".elf").read_bytes()).hexdigest(),
            "baseline_window_pin": old_window_pin,
            "baseline_window_pin_source": old_window_source,
            "provisional_window": provisional_window,
            "identity_claim": "none; a fresh pin/link authorization is required",
        },
        "decoder_transport": {
            "before": {
                "slices": 25,
                "minimum_boot_transports": baseline_transports,
                "cursor_work_state": "resident ordinary Bank-0 BSS",
            },
            "after": {
                "slices": len(C2_DECODER_SLICES),
                "boot_transports": whole_phase_boot_transports,
                "cursor_work_state": "retired",
                "logical_phases": [name for name, _entry in C2_DECODER_SLICES],
            },
            "validation_semantics": "unchanged catalog, record and payload verification once per transported logical phase",
        },
        "slice_capacity": {
            "cap_bytes": 1792,
            "phase_bytes": phases,
            "largest_phase": largest_name,
            "largest_phase_bytes": phases[largest_name],
            "smallest_headroom_bytes": smallest_headroom,
            "all_phases_fit": all(value <= 1792 for value in phases.values()),
        },
        "kernal_window_capacity": {
            "baseline_live_bytes": baseline_window["actual_live_window_bytes"],
            "baseline_future_margin_bytes": baseline_window["actual_future_margin_bytes"],
            "probe_live_bytes": new_window["actual_live_window_bytes"],
            "probe_future_margin_bytes": new_window["actual_future_margin_bytes"],
            "helper_facade_delta_bytes": (
                new_window["actual_live_window_bytes"]
                - baseline_window["actual_live_window_bytes"]),
            "control_flow_gate": "passed",
        },
        "runtime_overlay_bank": {
            "boot_image_bytes": balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "boot_headroom_bytes": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session_image_bytes": balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
            "session_headroom_bytes": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "fresh_gates": {
            "slice_caps": "passed",
            "fixed_facade": "passed",
            "pre_ownership": "passed",
            "handoff_z_and_io": "passed",
            "owned_window_control_flow": "passed",
            "one_truth_closure": "passed",
            "kernal_freedom": "passed",
            "runtime_family_total_identity": family_identity["status"],
            "mutated_payload_negative": family_identity["mutated_payload_negative"],
            "publish_last_verifier_binding": binding["status"],
        },
        "boot_time_projection": {
            "model": "linear redundant-transport component only",
            "link24_observed_seconds_approx": baseline_seconds,
            "link24_minimum_transport_count": baseline_transports,
            "probe_transport_count": whole_phase_boot_transports,
            "projected_redundant_transport_component_seconds": round(
                projected_transport_seconds, 3),
            "falsifiable_expectation": "cold C2 decode should move from minutes to the seconds class; the next receipt-less hardware pre-smoke measures the real total",
            "performance_claim": "not-run-not-passed",
        },
        "claim_limit": "One owner-authorized non-product capacity and structural probe. The provisional window is deliberately unpinned and must not be deployed. No Link 25, hardware acceptance, promotion or release claim.",
    }
    receipt = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-link24-whole-phase-facade-capacity-probe-receipt.json")
    write(receipt, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-whole-phase-facade-probe: PASS "
          f"largest={largest_name}:{phases[largest_name]}/1792 "
          f"e000-margin={new_window['actual_future_margin_bytes']} "
          f"transports={baseline_transports}->{whole_phase_boot_transports}")


def coarse_split_capacity_probe(out: Path) -> None:
    """Measure 02a/02b/06a/06b in the product-shaped seed link only."""
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    write(out / "c2-substitution.ld", linker_script())
    contract_lines = [
        "profile=" + PROFILE,
        "mode=link24-phase-02-06-coarse-split-capacity-probe",
        "hardware_execution=prohibited-non-product-seed",
        "c2_artifacts_sha256="
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256="
        + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "product_closure_link_count=0",
        "resident_island_seed_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:"
            f"{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"
    old_window_pin = kernal_window_identity_pin()
    write(kernal_header_path, kernal_header_values(
        int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE)
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare",
         "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header),
         "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    seed = compile_link(
        out, "coarse-split-capacity-seed.prg",
        [stage_header, runtime_prepared, island_prepared, error_header], artifacts)
    sections = section_table(Path(str(seed) + ".elf"))
    phases = {
        name: sections[f".lisp65_rt_c2d_{name}"]["bytes"]
        for name, _entry in C2_DECODER_SLICES
    }
    split_names = ("02a", "02b", "06a", "06b")
    split_bytes = {name: phases[name] for name in split_names}
    all_fit = all(value <= 1792 for value in split_bytes.values())
    if not all_fit:
        raise RuntimeError(
            "coarse split capacity first-red: "
            + ", ".join(f"{name}={split_bytes[name]}" for name in split_names))
    phase13 = phases["13"]
    if phase13 > 1792:
        raise RuntimeError(f"phase 13 watch first-red: {phase13}/1792")

    report = {
        "format": "lisp65-c2-link24-phase-02-06-coarse-split-capacity-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-non-product-capacity-probe-only",
        "scope": {
            "resident_island_seed_links": 1,
            "product_closure_links": 0,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
        },
        "identity": {
            "seed_prg": str(seed.relative_to(ROOT)),
            "seed_prg_sha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            "seed_elf_sha256": hashlib.sha256(
                Path(str(seed) + ".elf").read_bytes()).hexdigest(),
            "resolved_profile_sha256": hashlib.sha256(
                contract.read_bytes()).hexdigest(),
        },
        "semantic_cuts": {
            "02a": "all shelf-to-C2D image-record cross-bindings",
            "02b": "entry/resolution totals close, cursor reset, phase-3 publication",
            "06a": "normalized code structure and zero literal slots",
            "06b": "canonical export-name validation and phase-7 publication",
            "fail_closed_cutpoint_markers": {
                "02": "reserved 0x00 -> 0x2a -> 0x00",
                "06": "reserved 0x00 -> 0x6a -> 0x00",
                "skip_reorder_or_replay": "rejected",
            },
        },
        "slice_capacity": {
            "cap_bytes": 1792,
            "split_phase_bytes": split_bytes,
            "split_phase_headroom_bytes": {
                name: 1792 - value for name, value in split_bytes.items()
            },
            "all_four_split_phases_fit": True,
            "all_decoder_phase_bytes": phases,
            "phase_13_watch": {
                "bytes": phase13,
                "headroom_bytes": 1792 - phase13,
                "status": "narrowest-known-phase-watch",
            },
        },
        "transport_projection": {
            "link24_minimum_cursor_transports": 21068,
            "coarse_boot_decode_transports_excluding_phase13_materialization": 16,
            "performance_claim": "projected-only-not-run-not-passed",
        },
        "next_gate": (
            "A separately named regular product link with the complete identity, "
            "capacity, one-truth, KERNAL-freedom and structural gate set."
        ),
        "claim_limit": (
            "Owner-authorized product-shaped seed capacity probe only. It proves "
            "that the four new transported halves fit the unchanged 1792-byte "
            "cap; it is not a product link, identity pin, hardware acceptance, "
            "promotion or release claim."
        ),
    }
    receipt = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-link24-phase-02-06-coarse-split-capacity-probe-receipt.json")
    write(receipt, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-coarse-split-capacity-probe: PASS "
          + " ".join(f"{name}={split_bytes[name]}/1792" for name in split_names)
          + f" phase13={phase13}/1792 product-links=0")


def single_link(out: Path) -> None:
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    window_pin = kernal_window_identity_pin()
    out.mkdir(parents=True, exist_ok=True)
    window_pin_source = verify_kernal_window_pin_source(out, window_pin)
    write(out / "c2-substitution.ld", linker_script())
    contract_lines = [
        "profile=" + PROFILE,
        "c2_artifacts_sha256=" + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256=" + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "kernal_window_identity_sha256=" + str(window_pin["sha256"]),
        "kernal_window_identity_crc16=" + str(window_pin["crc16"]),
        "product_closure_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(f"input_sha256={item.relative_to(ROOT)}:{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")
    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    island_header = out / "resident-island.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"
    # The owned window is already protected by its fixed facade.  Bind its
    # Link-17 SHA/CRC identity before the sole product-closure link; the link
    # must reproduce all 8 KiB exactly.  Runtime-family tuples remain assembler
    # sentinels until their publish-last patch below.
    write(kernal_header_path, kernal_header_values(
        int(str(window_pin["crc16"]), 16), str(window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE)
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare", "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header), "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    common = [stage_header, runtime_prepared, island_prepared, error_header]
    seed = compile_link(out, "resident-island-seed.prg", common, artifacts)
    tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
         "--nm", str(TOOLCHAIN / "llvm-nm"), "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
         "--abi-contract", str(contract), "--header", str(island_header))
    final = compile_link(out, "lisp65-c2-substitution-linked.prg",
                         [stage_header, runtime_prepared, island_header,
                          error_header, kernal_header_path], artifacts)
    finish_single_link(out, final, contract, window_pin, window_pin_source)


def resume_single_link(out: Path) -> None:
    """Resume only gates/packing after a tool-only first red; never relink."""
    final = out / "lisp65-c2-substitution-linked.prg"
    contract = out / "resolved-profile.txt"
    required = [final, Path(str(final) + ".elf"), Path(str(final) + ".map"),
                contract]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"existing-link resume inputs absent: {missing}")
    if (out / "lisp65-c2-substitution-unbound.prg").exists():
        raise RuntimeError(
            "existing-link resume refuses an already publish-last-patched product")
    window_pin = kernal_window_identity_pin()
    window_pin_source = verify_kernal_window_pin_source(out, window_pin)
    finish_single_link(out, final, contract, window_pin, window_pin_source)


def verify_link18_replay_inputs(out: Path) -> dict[str, object]:
    receipt_path = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.2-product-substitution-link-18-first-red-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "first-red":
        raise RuntimeError("Link-18 replay source receipt is not first-red")
    for name, item in receipt["evidence"].items():
        for path_key, sha_key in (
                ("path", "sha256"),
                ("image_path", "image_sha256"),
                ("manifest_path", "manifest_sha256")):
            if path_key not in item:
                continue
            path = ROOT / item[path_key]
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            if actual != item[sha_key]:
                raise RuntimeError(
                    f"Link-18 replay input drift {name}:{path_key}: {actual}")
    expected_out = ROOT / "build/c2.2/substitution/product-link-18"
    if out != expected_out:
        raise RuntimeError(f"Link-18 replay must use {expected_out}")
    for forbidden in (
            "kernal-freedom-link.json", "substitution-balance.json",
            "eighteenth-substitution-link.json", "link-18-gate-replay.json"):
        if (out / forbidden).exists():
            raise RuntimeError(f"Link-18 replay output already exists: {forbidden}")
    return {
        "receipt": str(receipt_path.relative_to(ROOT)),
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "verified_evidence_entries": len(receipt["evidence"]),
        "status": "passed",
    }


def replay_link18(out: Path) -> None:
    replay_inputs = verify_link18_replay_inputs(out)
    final = out / "lisp65-c2-substitution-linked.prg"
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)
    report = {
        "format": "lisp65-c2-eighteenth-substitution-link-v1",
        "status": "passed",
        "product": str(final.relative_to(ROOT)),
        "product_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "replay": {
            "mode": "artifact-only-gate-replay",
            "new_product_links": 0,
            "inputs": replay_inputs,
        },
        "identity_gate": "passed",
        "capacity_gate": "passed",
        "one_truth_gate": "passed",
        "kernal_freedom_gate": "passed",
        "fixed_host_facade_gate": "passed",
        "pre_ownership_gate": "passed",
        "runtime_family_total_identity_gate": "passed",
        "mutated_payload_negative": "rejected",
        "control_flow_ownership": kernal["control_flow_ownership"],
        "fixed_bank0_headroom_bytes": FIXED_BANK0_HEADROOM_BYTES,
        "substitution_balance": "passed",
        "actual_e000_future_margin_bytes": kernal["capacity"]["actual_future_margin_bytes"],
        "runtime_family_headroom_bytes": {
            "boot": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "claim_limit": (
            "SHA-bound artifact-only structural closure of Link 18. No new "
            "product link, hardware acceptance or promotion claim."
        ),
    }
    write(out / "eighteenth-substitution-link.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    write(out / "link-18-gate-replay.json", json.dumps({
        "format": "lisp65-c2-link-18-gate-replay-v1",
        "status": "passed",
        "new_product_links": 0,
        "source_receipt": replay_inputs,
        "kernal_freedom_report_sha256": hashlib.sha256(
            (out / "kernal-freedom-link.json").read_bytes()).hexdigest(),
        "substitution_balance_sha256": hashlib.sha256(
            (out / "substitution-balance.json").read_bytes()).hexdigest(),
        "final_structural_report_sha256": hashlib.sha256(
            (out / "eighteenth-substitution-link.json").read_bytes()).hexdigest(),
    }, indent=2, sort_keys=True) + "\n")
    print("c2-product-substitution-link: REPLAY PASS "
          f"prg={final} new-links=0 "
          f"e000-margin={kernal['capacity']['actual_future_margin_bytes']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--single-link", action="store_true")
    parser.add_argument("--whole-phase-facade-probe", action="store_true")
    parser.add_argument("--coarse-split-capacity-probe", action="store_true")
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--replay-link-18", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        z_matrix = _handoff_z_abi_model_selftest()
        assert len(z_matrix) == 13
        assert z_matrix["valid-sei-ldz-zero-prefix"] == "passed"
        assert z_matrix["valid-mega65-io-knock"] == "passed"
        assert z_matrix["nonzero-z-normalization"] == "rejected"
        assert z_matrix["wrong-map-register-source"] == "rejected"
        assert z_matrix["c000-plus-e000-map-mask"] == "rejected"
        matrix = _pre_ownership_model_selftest()
        assert len(matrix) == 12
        assert matrix["same-vma-section-identity"] == "passed"
        assert matrix["prepare-before-ownership"] == "rejected"
        assert matrix["pre-handoff-edge-to-vm-logical-pc-helper"] == "rejected"
        assert matrix["pre-handoff-edge-to-c2-root-walker"] == "rejected"
        assert matrix["repl-before-ownership"] == "rejected"
        assert matrix["pre-handoff-operand-to-fixed-state"] == "rejected"
        control_matrix = _owned_control_flow_model_selftest()
        assert control_matrix["same-function-symbol-less-basic-block"] == "passed"
        assert control_matrix["absolute-weak-alias-disguised-exit"] == "rejected"
        assert len(control_matrix) == 6
        try:
            checked_public_projection(["literal_prep", "literal-prep"])
        except RuntimeError:
            pass
        else:
            raise AssertionError("slice-name projection collision was accepted")
        generated = linker_script()
        assert ".lisp65_rt_c2d_13" in generated
        assert ".lisp65_rt_c2d_13b" not in generated
        assert ".lisp65_rt_l65m_00" not in generated
        assert ".lisp65_c2_kernal_window.c2_resident" in generated
        assert ".lisp65_c2_kernal_window.event_poll" in generated
        assert ".lisp65_c2_host_facade 0xb5a2" in generated
        assert ".lisp65_c2_fixed_zp 0x89" in generated
        assert ".lisp65_c2_fixed_bank0 0xc080" in generated
        assert ".lisp65_c2_fixed_bank0_code 0xc218" in generated
        assert ".lisp65_runtime_overlay_verifier_bindings" in generated
        assert "SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 32" in generated
        assert ".lisp65_c2_kernal_handoff 0xb481" in generated
        assert ".lisp65_c2_kernal_io_reveal 0xb5c9" in generated
        assert ".lisp65_c2_kernal_map_switch 0xb5d4" in generated
        assert "SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0" in generated
        assert ".lisp65_c2_kernal_window.session_emitter_state" in generated
        assert len(HOST_FACADE_SYMBOLS) == 13
        assert len(set(HOST_FACADE_SYMBOLS)) == 13
        assert HOST_FACADE_BASE + len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE == 0xb5c9
        layout_header = (ROOT / "src/c2_kernal_layout.h").read_text(encoding="utf-8")
        mem_header = (ROOT / "src/mem.h").read_text(encoding="utf-8")
        mem_source = (ROOT / "src/mem.c").read_text(encoding="utf-8")
        assert "#define LISP65_C2_ZP __zp" in layout_header
        assert "extern uint8_t LISP65_C2_ZP mem_oom" in mem_header
        assert 'LISP65_C2_FIXED_ZP("mem_oom") mem_oom' in mem_source
        repl_source = (ROOT / "src/repl.c").read_text(encoding="utf-8")
        assert 'LISP65_C2_FIXED_BANK0_CODE("kb_cursor_off")' in repl_source
        emitter_source = (ROOT / "src/c2_session_emitter.c").read_text(
            encoding="utf-8")
        assert 'LISP65_C2_FIXED_BANK0_CODE("c2e_cons")' in emitter_source
        binding_source = (ROOT / "src/runtime_overlay_verifier_bindings.s").read_text(
            encoding="utf-8")
        assert "rtov_boot_verifiers:" in binding_source
        assert "rtov_verifiers:" in binding_source
        assert "0xff80" in generated
        assert "AT(ORIGIN(c2_runtime_load))" in generated
        assert generated.count("(!rwx)") == 3
        assert generated.count("(INFO)") == len(ORPHAN_ALLOWLIST)
        assert "KEEP(*(.lisp65_error_callsites))" in generated
        assert "SIZEOF(.lisp65_error_callsites) > 0" in generated
        assert generated.index("MEMORY {") < generated.index(
            "AT(ORIGIN(c2_runtime_load))")
        assert "INSERT AFTER .lisp65_resident_island_annex" in generated
        assert UNIQUE_SLICE_COUNT == 43
        assert len(BOOT_SLICE_SPECS) == 9
        assert len(SESSION_SLICE_SPECS) == 36
        decoder_source = (ROOT / "scripts/c2-stream-decoder.c").read_text(
            encoding="utf-8")
        assert "c->reserved = 0x2au" in decoder_source
        assert "c->reserved != 0x2au" in decoder_source
        assert "c->reserved = 0x6au" in decoder_source
        assert "c->reserved != 0x6au" in decoder_source
        print("c2-product-substitution-link: SELFTEST PASS "
              "unique-slices=43 boot=9 session=36")
        return 0
    if sum((args.single_link, args.whole_phase_facade_probe,
            args.coarse_split_capacity_probe,
            args.resume_existing,
            args.replay_link_18)) != 1:
        parser.error("choose exactly one link, whole-phase facade probe, "
                     "existing-link resume or Link-18 replay mode")
    if args.single_link:
        single_link(args.out.resolve())
    elif args.whole_phase_facade_probe:
        whole_phase_facade_probe(args.out.resolve())
    elif args.coarse_split_capacity_probe:
        coarse_split_capacity_probe(args.out.resolve())
    elif args.resume_existing:
        resume_single_link(args.out.resolve())
    else:
        replay_link18(args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
