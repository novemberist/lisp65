#!/usr/bin/env python3
"""Write a compact footprint report for the native MVP VM stdlib PRG."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mvp_vm_stdlib_boot_budget as BB  # noqa: E402


def parse_int(text):
    s = str(text).strip()
    if s.endswith(("u", "U")):
        s = s[:-1]
    return int(s, 0)


def header_macros(path):
    macros = {}
    pattern = re.compile(r"^\s*#define\s+([A-Z0-9_]+)\s+([0-9][0-9A-Fa-fxXuU]*)\b")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            macros[m.group(1)] = parse_int(m.group(2))
    return macros


def d_flags(cflags):
    out = {}
    for token in shlex.split(cflags):
        if not token.startswith("-D"):
            continue
        item = token[2:]
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, "1"
        out[key] = value
    return out


def git_short():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def build_timestamp():
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is None:
        return datetime.now(timezone.utc)
    try:
        epoch = int(raw, 10)
    except ValueError as exc:
        raise SystemExit("footprint: invalid SOURCE_DATE_EPOCH") from exc
    if epoch < 0:
        raise SystemExit("footprint: SOURCE_DATE_EPOCH must be nonnegative")
    return datetime.fromtimestamp(epoch, timezone.utc)


def nm_symbols(nm, elf):
    out = subprocess.check_output(
        [str(nm), "--defined-only", str(elf)],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    symbols = {}
    pattern = re.compile(r"^([0-9A-Fa-f]+)\s+\S\s+(\S+)$")
    for line in out.splitlines():
        m = pattern.match(line.strip())
        if m:
            symbols[m.group(2)] = int(m.group(1), 16)
    return symbols


def section_sizes(size_tool, elf):
    if size_tool is None or not size_tool.exists():
        return {}
    out = subprocess.check_output(
        [str(size_tool), "-A", str(elf)],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    sizes = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("."):
            try:
                sizes[parts[0]] = int(parts[1], 0)
            except ValueError:
                pass
    return sizes


def prg_load_info(path):
    data = path.read_bytes()
    if len(data) < 2:
        raise SystemExit("footprint: PRG too short to contain load address: %s" % path)
    load_addr = data[0] | (data[1] << 8)
    payload_bytes = len(data) - 2
    file_end = load_addr + payload_bytes
    return {
        "load_addr": load_addr,
        "payload_bytes": payload_bytes,
        "file_end": file_end,
    }


def emit(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prg", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--header", type=Path, required=True)
    ap.add_argument("--elf", type=Path, required=True)
    ap.add_argument("--nm", type=Path, required=True)
    ap.add_argument("--size", type=Path)
    ap.add_argument("--min-stack-gap", default="1200")
    ap.add_argument("--min-boot-stack-gap", default="512")
    ap.add_argument("--min-bank0-reserve", default="0")
    ap.add_argument("--bank0-reserve-target", default="1024")
    ap.add_argument("--max-prg-file-end", default="0xc000")
    ap.add_argument("--m65-cflags", required=True)
    ap.add_argument("--heap-cells", required=True)
    ap.add_argument("--extra-cflags", required=True)
    ap.add_argument("--eval-c", type=Path, default=Path("src/eval.c"))
    ap.add_argument("--native-c", type=Path, action="append", default=[])
    ap.add_argument("--min-symbol-headroom", type=int, default=0)
    ap.add_argument(
        "--boot-symbol-correction",
        type=int,
        default=0,
        help="measured runtime-only symbols to add to the static boot-budget estimate",
    )
    ns = ap.parse_args(argv)

    manifest = json.loads(ns.manifest.read_text(encoding="utf-8"))
    macros = header_macros(ns.header)
    defines = d_flags(ns.extra_cflags)
    boot_budget = BB.compute_budget(
        manifest_path=ns.manifest,
        eval_c=ns.eval_c,
        extra_cflags=ns.extra_cflags,
        native_sources=ns.native_c,
        min_sym_headroom=ns.min_symbol_headroom,
        symbol_correction=ns.boot_symbol_correction,
    )
    entries = manifest.get("entries", [])
    lengths = [int(entry["length"]) for entry in entries]
    largest = max(entries, key=lambda entry: int(entry["length"])) if entries else None
    prg_bytes = ns.prg.stat().st_size
    prg_info = prg_load_info(ns.prg)
    min_stack_gap = parse_int(ns.min_stack_gap)
    min_boot_stack_gap = parse_int(ns.min_boot_stack_gap)
    min_bank0_reserve = parse_int(ns.min_bank0_reserve)
    bank0_reserve_target = parse_int(ns.bank0_reserve_target)
    max_prg_file_end = parse_int(ns.max_prg_file_end)

    symbols = nm_symbols(ns.nm, ns.elf)
    sections = section_sizes(ns.size, ns.elf)
    heap_start = symbols.get("__heap_start")
    stack_addr = symbols.get("__stack")
    if heap_start is None or stack_addr is None:
        missing = ", ".join(k for k in ("__heap_start", "__stack") if k not in symbols)
        raise SystemExit("footprint: missing ELF symbols: %s" % missing)
    stack_gap = stack_addr - heap_start
    stack_gap_status = "ok" if stack_gap >= min_stack_gap else "too-small"
    bank0_usable_start = prg_info["load_addr"]
    bank0_usable_end = stack_addr
    bank0_usable_bytes = bank0_usable_end - bank0_usable_start
    bank0_resident_bytes = heap_start - bank0_usable_start
    bank0_text_data_bytes = sum(
        sections.get(name, 0) for name in (".basic_header", ".text", ".rodata", ".data")
    )
    bank0_bss_bytes = sum(sections.get(name, 0) for name in (".bss", ".noinit"))
    bank0_other_resident_bytes = (
        bank0_resident_bytes - bank0_text_data_bytes - bank0_bss_bytes
    )
    bank0_reserve_bytes = stack_gap - min_stack_gap
    bank0_reserve_status = (
        "ok" if bank0_reserve_bytes >= min_bank0_reserve else "too-small"
    )
    bank0_reserve_target_status = (
        "ok" if bank0_reserve_bytes >= bank0_reserve_target else "below-target"
    )
    overlay_start = symbols.get("__lisp65_boot_overlay_start")
    overlay_end = symbols.get("__lisp65_boot_overlay_end")
    noinit_start = symbols.get("__lisp65_noinit_start")
    noinit_end = symbols.get("__lisp65_noinit_end")
    overlay_present = overlay_start is not None and overlay_end is not None
    overlay_size = None
    boot_stack_gap = None
    boot_stack_gap_status = "missing"
    noinit_size = None
    noinit_overlay_gap = None
    noinit_overlay_status = "missing"
    if overlay_present:
        overlay_size = overlay_end - overlay_start
        boot_stack_gap = stack_addr - overlay_end
        boot_stack_gap_status = "ok" if boot_stack_gap >= min_boot_stack_gap else "too-small"
        if noinit_start is not None and noinit_end is not None:
            noinit_size = noinit_end - noinit_start
            noinit_overlay_gap = overlay_start - noinit_end
            noinit_overlay_status = "ok" if noinit_end < overlay_start else "overlap"
    base_addr = parse_int(manifest["base_addr"])
    code_bytes = int(manifest["code_bytes"])
    blob_end = base_addr + code_bytes
    external_image = manifest.get("external_image") or {}
    external_image_ext_bank = (base_addr >> 16) & 0xff
    external_image_ext_start = base_addr & 0xffff
    external_image_bytes = None
    external_image_ext_end = None
    if external_image.get("bytes") is not None:
        external_image_bytes = parse_int(external_image["bytes"])
        external_image_ext_end = external_image_ext_start + external_image_bytes
    sympool_ext_bank = None
    sympool_ext_off = None
    sympool_ext_end = None
    sympool_ext_status = "missing"
    external_image_sympool_status = "missing"
    if "LISP65_SYMPOOL_EXT" in defines:
        sympool_ext_status = "1"
        sympool_ext_bank = parse_int(defines.get("SYMPOOL_EXT_BANK", "5"))
        sympool_ext_off = parse_int(defines.get("SYMPOOL_EXT_OFF", "0x8000"))
        if defines.get("NAMEPOOL") is not None:
            sympool_ext_end = sympool_ext_off + parse_int(defines["NAMEPOOL"])
    if (
        "LISP65_STDLIB_EXTERNAL_BLOB" in defines
        and "LISP65_STDLIB_EXT_METADATA" in defines
        and "LISP65_SYMPOOL_EXT" in defines
        and external_image_bytes is not None
        and sympool_ext_bank is not None
        and sympool_ext_off is not None
        and sympool_ext_end is not None
    ):
        if external_image_ext_bank != sympool_ext_bank:
            external_image_sympool_status = "ok"
        elif (
            external_image_ext_start < sympool_ext_end
            and sympool_ext_off < external_image_ext_end
        ):
            external_image_sympool_status = "overlap"
        else:
            external_image_sympool_status = "ok"
    report_status_parts = []
    prg_file_end_status = (
        "ok" if prg_info["file_end"] < max_prg_file_end else "too-high"
    )
    if prg_file_end_status != "ok":
        report_status_parts.append("prg-file-end-too-high")
    if stack_gap_status != "ok":
        report_status_parts.append("stack-gap-too-small")
    if bank0_reserve_status != "ok":
        report_status_parts.append("bank0-reserve-too-small")
    if overlay_present and boot_stack_gap_status != "ok":
        report_status_parts.append("boot-stack-gap-too-small")
    if overlay_present and noinit_overlay_status not in ("ok", "missing"):
        report_status_parts.append("boot-overlay-noinit-overlap")
    if boot_budget["status"] != "ok":
        for part in str(boot_budget["status"]).split(","):
            report_status_parts.append("boot-budget-%s" % part)
    if external_image_sympool_status == "overlap":
        report_status_parts.append("external-image-sympool-overlap")
    report_status = "ok" if not report_status_parts else ",".join(report_status_parts)

    lines = [
        "lisp65 mvp vm stdlib footprint report",
        "built_at=%s" % build_timestamp().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit=%s" % git_short(),
        "status=%s" % report_status,
        "",
        "Native PRG:",
        "prg=%s" % ns.prg,
        "elf=%s" % ns.elf,
        "prg_bytes=%d" % prg_bytes,
        "prg_load_addr=0x%04x" % prg_info["load_addr"],
        "prg_payload_bytes=%d" % prg_info["payload_bytes"],
        "prg_file_end=0x%04x" % prg_info["file_end"],
        "max_prg_file_end=0x%04x" % max_prg_file_end,
        "prg_file_end_status=%s" % prg_file_end_status,
        "m65vmstdlib_cflags=%s" % ns.m65_cflags,
        "m65vmstdlib_heap=%s" % ns.heap_cells,
        "m65vmstdlib_extra_cflags=%s" % ns.extra_cflags,
        "heap_cells=%s" % ns.heap_cells,
        "max_sym=%s" % defines.get("MAX_SYM", "missing"),
        "namepool=%s" % defines.get("NAMEPOOL", "missing"),
        "sympool_ext=%s" % sympool_ext_status,
        "sympool_ext_bank=%s"
        % ("0x%02x" % sympool_ext_bank if sympool_ext_bank is not None else "missing"),
        "sympool_ext_off=%s"
        % ("0x%04x" % sympool_ext_off if sympool_ext_off is not None else "missing"),
        "sympool_ext_end=%s"
        % ("0x%04x" % sympool_ext_end if sympool_ext_end is not None else "missing"),
        "external_image_sympool_status=%s" % external_image_sympool_status,
        "gc_roots=%s" % defines.get("GC_ROOTS", "missing"),
        "metadata=%s" % defines.get("LISP65_BYTECODE_STDLIB_EMIT_METADATA", "missing"),
        "stdlib_boot_overlay=%s" % defines.get("LISP65_STDLIB_BOOT_OVERLAY", "missing"),
        "stdlib_external_blob=%s" % defines.get("LISP65_STDLIB_EXTERNAL_BLOB", "missing"),
        "mark_bitmap=%s" % defines.get("LISP65_MARK_BITMAP", "missing"),
        "embed_stdlib=1",
        "embed_dma=1",
        "boot_budget_status=%s" % boot_budget["status"],
        "boot_required_symbols=%d" % boot_budget["required_symbols"],
        "boot_static_required_symbols=%d" % boot_budget["static_required_symbols"],
        "boot_symbol_correction=%d" % boot_budget["symbol_correction"],
        "boot_max_sym=%s" % (boot_budget["max_sym"] if boot_budget["max_sym"] is not None else "missing"),
        "boot_min_sym_headroom=%d" % boot_budget["min_sym_headroom"],
        "boot_sym_headroom=%s"
        % (boot_budget["sym_headroom"] if boot_budget["sym_headroom"] is not None else "missing"),
        "boot_required_namepool_bytes=%d" % boot_budget["required_namepool_bytes"],
        "boot_namepool=%s" % (boot_budget["namepool"] if boot_budget["namepool"] is not None else "missing"),
        "boot_namepool_headroom=%s"
        % (
            boot_budget["namepool_headroom"]
            if boot_budget["namepool_headroom"] is not None
            else "missing"
        ),
        "boot_vm_codebuf=%s"
        % (boot_budget["vm_codebuf"] if boot_budget["vm_codebuf"] is not None else "missing"),
        "boot_vm_codebuf_required=%d" % boot_budget["vm_codebuf_required"],
        "boot_vm_codebuf_headroom=%s"
        % (
            boot_budget["vm_codebuf_headroom"]
            if boot_budget["vm_codebuf_headroom"] is not None
            else "missing"
        ),
        "boot_vm_codebuf_worst_entry=%s" % boot_budget["vm_codebuf_worst_entry"],
        "heap_start=0x%04x" % heap_start,
        "stack_addr=0x%04x" % stack_addr,
        "stack_gap_bytes=%d" % stack_gap,
        "min_stack_gap_bytes=%d" % min_stack_gap,
        "stack_gap_status=%s" % stack_gap_status,
        "bank0_usable_start=0x%04x" % bank0_usable_start,
        "bank0_usable_end=0x%04x" % bank0_usable_end,
        "bank0_usable_bytes=%d" % bank0_usable_bytes,
        "bank0_resident_bytes=%d" % bank0_resident_bytes,
        "bank0_text_data_bytes=%d" % bank0_text_data_bytes,
        "bank0_bss_bytes=%d" % bank0_bss_bytes,
        "bank0_other_resident_bytes=%d" % bank0_other_resident_bytes,
        "bank0_stack_gap_bytes=%d" % stack_gap,
        "bank0_stack_gap_required_bytes=%d" % min_stack_gap,
        "bank0_reserve_bytes=%d" % bank0_reserve_bytes,
        "min_bank0_reserve_bytes=%d" % min_bank0_reserve,
        "bank0_reserve_status=%s" % bank0_reserve_status,
        "bank0_reserve_target_bytes=%d" % bank0_reserve_target,
        "bank0_reserve_target_status=%s" % bank0_reserve_target_status,
        "bank0_dashboard=usable=%d resident=%d text_data=%d bss=%d other=%d stack_gap=%d reserve=%d target=%d target_status=%s"
        % (
            bank0_usable_bytes,
            bank0_resident_bytes,
            bank0_text_data_bytes,
            bank0_bss_bytes,
            bank0_other_resident_bytes,
            stack_gap,
            bank0_reserve_bytes,
            bank0_reserve_target,
            bank0_reserve_target_status,
        ),
        "bank0_coupling_summary=text_data_moves_heap_start;bss_moves_heap_start;MAX_SYM_NAMEPOOL_VM_DIR_MAX_GC_ROOTS_VM_CODEBUF_HEAP_CELLS_affect_bss;stack_gap=__stack-__heap_start",
        "boot_overlay_present=%s" % ("1" if overlay_present else "0"),
        "noinit_start=%s" % ("0x%04x" % noinit_start if noinit_start is not None else "missing"),
        "noinit_end=%s" % ("0x%04x" % noinit_end if noinit_end is not None else "missing"),
        "noinit_bytes=%s" % (noinit_size if noinit_size is not None else "missing"),
        "boot_overlay_start=%s" % ("0x%04x" % overlay_start if overlay_start is not None else "missing"),
        "boot_overlay_end=%s" % ("0x%04x" % overlay_end if overlay_end is not None else "missing"),
        "boot_overlay_bytes=%s" % (overlay_size if overlay_size is not None else "missing"),
        "noinit_overlay_gap_bytes=%s"
        % (noinit_overlay_gap if noinit_overlay_gap is not None else "missing"),
        "noinit_overlay_status=%s" % noinit_overlay_status,
        "boot_stack_gap_bytes=%s" % (boot_stack_gap if boot_stack_gap is not None else "missing"),
        "min_boot_stack_gap_bytes=%d" % min_boot_stack_gap,
        "boot_stack_gap_status=%s" % boot_stack_gap_status,
        "",
        "Bytecode stdlib artifact:",
        "manifest=%s" % ns.manifest,
        "header=%s" % ns.header,
        "format=%s" % manifest.get("format", "missing"),
        "suite=%s" % manifest.get("suite", "missing"),
        "base_addr=%s" % manifest.get("base_addr", "missing"),
        "blob_end_addr=0x%06x" % blob_end,
        "external_image=%s" % external_image.get("path", "missing"),
        "external_image_bytes=%s" % external_image.get("bytes", "missing"),
        "external_image_ext_bank=0x%02x" % external_image_ext_bank,
        "external_image_ext_start=0x%04x" % external_image_ext_start,
        "external_image_ext_end=%s"
        % (
            "0x%04x" % external_image_ext_end
            if external_image_ext_end is not None
            else "missing"
        ),
        "external_image_sha256=%s" % external_image.get("sha256", "missing"),
        "external_metadata_addr=%s" % external_image.get("metadata_addr", "missing"),
        "external_metadata_offset=%s" % external_image.get("metadata_offset", "missing"),
        "external_metadata_bytes=%s" % external_image.get("metadata_bytes", "missing"),
        "external_metadata_sha256=%s" % external_image.get("metadata_sha256", "missing"),
        "objects=%s" % manifest.get("objects", "missing"),
        "functions=%d" % len(manifest.get("functions", [])),
        "cases=%d" % len(manifest.get("cases", [])),
        "entries=%d" % len(entries),
        "code_bytes=%d" % code_bytes,
        "directory_bytes=%s" % manifest.get("directory_bytes", "missing"),
        "literal_nodes=%d" % len(manifest.get("literal_nodes", [])),
        "literal_index=%d" % len(manifest.get("literal_index", [])),
        "literal_patches=%d" % len(manifest.get("literal_patches", [])),
        "blob_sha256=%s" % manifest.get("blob_sha256", "missing"),
        "directory_sha256=%s" % manifest.get("directory_sha256", "missing"),
        "disasm_sha256=%s" % manifest.get("disasm_sha256", "missing"),
        "",
        "Generated header macros:",
        "object_count=%s" % macros.get("LISP65_BYTECODE_STDLIB_OBJECT_COUNT", "missing"),
        "embed_count=%s" % macros.get("LISP65_BYTECODE_STDLIB_EMBED_COUNT", "missing"),
        "blob_bytes=%s" % macros.get("LISP65_BYTECODE_STDLIB_BLOB_BYTES", "missing"),
        "directory_bytes_macro=%s" % macros.get("LISP65_BYTECODE_STDLIB_DIRECTORY_BYTES", "missing"),
        "literal_node_count=%s" % macros.get("LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT", "missing"),
        "literal_index_count=%s" % macros.get("LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT", "missing"),
        "literal_patch_count=%s" % macros.get("LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT", "missing"),
        "",
        "Code object size summary:",
        "min_object_bytes=%d" % (min(lengths) if lengths else 0),
        "max_object_bytes=%d" % (max(lengths) if lengths else 0),
        "avg_object_bytes=%.2f" % ((sum(lengths) / len(lengths)) if lengths else 0.0),
        "largest_object=%s" % (largest["name"] if largest else "missing"),
        "largest_object_bytes=%s" % (largest["length"] if largest else "missing"),
    ]
    emit(ns.out, lines)
    print("mvp-vm-stdlib-footprint-report: WROTE %s" % ns.out)
    if prg_file_end_status != "ok":
        print(
            "mvp-vm-stdlib-footprint-report: FAIL PRG file end 0x%04x >= 0x%04x"
            % (prg_info["file_end"], max_prg_file_end),
            file=sys.stderr,
        )
        return 1
    if stack_gap_status != "ok":
        print(
            "mvp-vm-stdlib-footprint-report: FAIL stack gap %d < %d"
            % (stack_gap, min_stack_gap),
            file=sys.stderr,
        )
        return 1
    if bank0_reserve_status != "ok":
        print(
            "mvp-vm-stdlib-footprint-report: FAIL Bank-0 reserve %d < %d"
            % (bank0_reserve_bytes, min_bank0_reserve),
            file=sys.stderr,
        )
        return 1
    if overlay_present and boot_stack_gap_status != "ok":
        print(
            "mvp-vm-stdlib-footprint-report: FAIL boot stack gap %d < %d"
            % (boot_stack_gap, min_boot_stack_gap),
            file=sys.stderr,
        )
        return 1
    if overlay_present and noinit_overlay_status not in ("ok", "missing"):
        print(
            "mvp-vm-stdlib-footprint-report: FAIL boot overlay overlaps .noinit "
            "(noinit_end=0x%04x overlay_start=0x%04x)"
            % (noinit_end, overlay_start),
            file=sys.stderr,
        )
        return 1
    if external_image_sympool_status == "overlap":
        print(
            "mvp-vm-stdlib-footprint-report: FAIL external image "
            "[bank=0x%02x 0x%04x..0x%04x) overlaps SYMPOOL_EXT "
            "[bank=0x%02x 0x%04x..0x%04x)"
            % (
                external_image_ext_bank,
                external_image_ext_start,
                external_image_ext_end,
                sympool_ext_bank,
                sympool_ext_off,
                sympool_ext_end,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
