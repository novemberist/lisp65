#!/usr/bin/env python3
"""Prove the complete C2I-v2 stream decoder and its runtime-slice fit.

This is deliberately one step short of the product substitution link.  It
executes the complete six-image shelf through the same sliced C decoder that
is linked by llvm-mos, rejects contract mutations, and measures every
independently loadable phase against the current 1,792-byte runtime slot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402

BUILD = ROOT / "build/c2.1/streaming-decoder"
HOST_BIN = BUILD / "c2-stream-host"
TARGET_A = BUILD / "target-a/c2-stream-target.prg"
TARGET_B = BUILD / "target-b/c2-stream-target.prg"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-streaming-decoder-link-receipt.json"
)
FULL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-full-emission-receipt.json"
)
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
SIZE = ROOT / "tools/llvm-mos/bin/llvm-size"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
HEADER = ROOT / "scripts/c2-stream-decoder.h"
CORE = ROOT / "scripts/c2-stream-decoder.c"
INIT = ROOT / "scripts/c2-stream-init.c"
HOST_SOURCE = ROOT / "scripts/c2-stream-host-main.c"
TARGET_SOURCE = ROOT / "scripts/c2-stream-target-main.c"
DOCUMENT = ROOT / "docs/planning/c2.1-full-emission.md"
PHASES = [ROOT / f"scripts/c2-stream-phase-{index:02d}.c" for index in range(10)]
SOURCES = [INIT, *PHASES]
SLOT_BYTES = 1792


class StreamError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StreamError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def run(argv: list[str], *, env: dict[str, str] | None = None,
        expected: int = 0, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            env=env, timeout=timeout, check=False)
    if result.returncode != expected:
        raise StreamError("%s returned %d, expected %d: %s" %
                          (Path(argv[0]).name, result.returncode, expected,
                           (result.stderr or result.stdout).strip()))
    return result


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def repair_image(shelf: bytearray, c2d: bytearray, image: int) -> None:
    """Repair identities above one intentionally mutated image payload."""
    record = 32 + image * 32
    code_at, code_bytes = u24(shelf, record + 8), u16(shelf, record + 11)
    meta_at, meta_bytes = u24(shelf, record + 13), u16(shelf, record + 16)
    code = shelf[code_at:code_at + code_bytes]
    metadata = shelf[meta_at:meta_at + meta_bytes]
    struct.pack_into("<I", shelf, record + 18, zlib.crc32(code) & 0xFFFFFFFF)
    struct.pack_into("<I", shelf, record + 22, zlib.crc32(metadata) & 0xFFFFFFFF)
    struct.pack_into("<I", shelf, record + 26, zlib.crc32(code + metadata) & 0xFFFFFFFF)
    catalog = shelf[32:32 + shelf[7] * 32]
    catalog_crc = zlib.crc32(catalog) & 0xFFFFFFFF
    struct.pack_into("<I", shelf, 18, catalog_crc)
    struct.pack_into("<I", c2d, 28, catalog_crc)


def image_metadata(shelf: bytes | bytearray, image: int) -> tuple[int, int, int, int]:
    record = 32 + image * 32
    at, length = u24(shelf, record + 13), u16(shelf, record + 16)
    literal_count = u16(shelf, at + 12)
    literal_offset = u16(shelf, at + 16)
    return at, length, literal_offset, literal_count


def execute(host: Path, shelf: bytes, c2d: bytes,
            directory: Path) -> subprocess.CompletedProcess[str]:
    shelf_path, c2d_path = directory / "shelf.bin", directory / "c2d.bin"
    shelf_path.write_bytes(shelf); c2d_path.write_bytes(c2d)
    return run([str(host), str(shelf_path), str(c2d_path)])


def rejected(host: Path, shelf: bytes, c2d: bytes, directory: Path,
             label: str, phase: int, status: int) -> dict[str, Any]:
    shelf_path = directory / f"{label}.shelf.bin"
    c2d_path = directory / f"{label}.c2d.bin"
    shelf_path.write_bytes(shelf); c2d_path.write_bytes(c2d)
    result = subprocess.run([str(host), str(shelf_path), str(c2d_path)], cwd=ROOT,
                            capture_output=True, text=True, timeout=60, check=False)
    expected = f"c2-stream: FAIL phase={phase} status={status}"
    require(result.returncode == status and result.stderr.strip() == expected,
            f"{label} was not rejected at phase {phase}/status {status}: "
            f"rc={result.returncode} stderr={result.stderr.strip()!r}")
    return {"case": label, "phase": phase, "status": status}


def mutation_matrix(host: Path, shelf_raw: bytes, c2d_raw: bytes,
                    directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    c2d[0] ^= 1
    rows.append(rejected(host, shelf, c2d, directory, "c2d-magic", 0, 3))

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    shelf[0] ^= 1
    rows.append(rejected(host, shelf, c2d, directory, "shelf-magic", 1, 2))

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    shelf[32] ^= 1
    rows.append(rejected(host, shelf, c2d, directory, "catalog-crc", 1, 2))

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    meta, _length, _literal, _count = image_metadata(shelf, 0)
    shelf[meta + 4] = 1
    repair_image(shelf, c2d, 0)
    rows.append(rejected(host, shelf, c2d, directory, "c2i-v1-to-v2", 4, 4))

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    meta, _length, _literal, _count = image_metadata(shelf, 0)
    entry_offset = u16(shelf, meta + 14)
    struct.pack_into("<H", shelf, meta + entry_offset + 3, 0)
    repair_image(shelf, c2d, 0)
    rows.append(rejected(host, shelf, c2d, directory, "zero-entry-length", 5, 5))

    # Find a product image containing both a general symbol and a pair.
    chosen = None
    for image in range(shelf_raw[7]):
        meta, _length, literal_offset, count = image_metadata(shelf_raw, image)
        kinds = [shelf_raw[meta + literal_offset + i * 8] for i in range(count)]
        if 7 in kinds and 8 in kinds:
            chosen = (image, meta, literal_offset, kinds)
            break
    require(chosen is not None, "full product lacks combined kind-7/kind-8 mutation image")
    image, meta, literal_offset, kinds = chosen

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
    symbol = kinds.index(8); shelf[meta + literal_offset + symbol * 8 + 1] = 1
    repair_image(shelf, c2d, image)
    rows.append(rejected(host, shelf, c2d, directory, "kind8-flags", 7, 6))

    pair = kinds.index(7)
    for label, target in (("pair-self-reference", pair),
                          ("pair-forward-reference", pair + 1)):
        shelf, c2d = bytearray(shelf_raw), bytearray(c2d_raw)
        struct.pack_into("<H", shelf, meta + literal_offset + pair * 8 + 2, target)
        repair_image(shelf, c2d, image)
        rows.append(rejected(host, shelf, c2d, directory, label, 8, 6))

    require(len(rows) == 8, "streaming mutation matrix closure")
    return rows


def compile_host() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    result = run(["cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
                  "-I", str(ROOT / "scripts"), *map(str, SOURCES), str(HOST_SOURCE),
                  "-o", str(HOST_BIN)])
    require(not result.stdout and not result.stderr, "host compiler diagnostics")


def compile_target(output: Path, variant: str) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    map_path = output.with_suffix(".map")
    env = dict(__import__("os").environ)
    env.update({"SOURCE_DATE_EPOCH": "1784419200",
                "TMPDIR": str(output.parent), "PYTHONHASHSEED": variant})
    result = run([str(CC), "-std=c99", "-Os", "-I", str(ROOT / "scripts"),
                  *map(str, SOURCES), str(TARGET_SOURCE), "-Wl,--icf=none",
                  "-Wl,-Map," + str(map_path), "-o", str(output)], env=env)
    elf = Path(str(output) + ".elf")
    require(not result.stdout and not result.stderr and output.is_file() and elf.is_file(),
            "llvm-mos streaming link diagnostics/artifacts")
    return elf, map_path


def parse_size(text: str) -> dict[str, int]:
    rows = [line.split() for line in text.splitlines() if line.strip()]
    require(len(rows) >= 2 and rows[0][:4] == ["text", "data", "bss", "dec"],
            "llvm-size output drift")
    row = rows[-1]
    return {"text": int(row[0]), "data": int(row[1]),
            "bss": int(row[2]), "dec": int(row[3])}


def symbol_sizes(elf: Path) -> tuple[dict[str, int], dict[str, int]]:
    output = run([str(NM), "--print-size", "--size-sort", "--radix=x", str(elf)]).stdout
    phases: dict[str, int] = {}
    seams: dict[str, int] = {}
    seam_names = {"c2_stream_shelf_read", "c2_stream_c2d_read", "c2_stream_c2d_write",
                  "c2_stream_name_value", "c2_stream_pair_value"}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        name, size = fields[-1], int(fields[1], 16)
        if re.fullmatch(r"c2_stream_phase_\d\d", name):
            phases[name] = size
        elif name in seam_names:
            seams[name] = size
    require(len(phases) == 10 and set(seams) == seam_names,
            "streaming target symbol inventory drift")
    require(all(size <= SLOT_BYTES for size in phases.values()),
            "streaming phase exceeds 1,792-byte runtime slot")
    return dict(sorted(phases.items())), dict(sorted(seams.items()))


def render() -> dict[str, Any]:
    full_receipt = json.loads(FULL_RECEIPT.read_text(encoding="utf-8"))
    require(full_receipt["status"] == "host-emission-and-decode-passed-product-link-not-run",
            "complete emission receipt missing")
    images, shelf, c2d, facts = F.build_all()
    require(len(images) == 6 and len(shelf) == 69754 and len(c2d) == 10480
            and facts["c2i_v2_descriptors"] == 2249, "complete geometry drift")
    require(sha(shelf) == full_receipt["artifacts"]["shelf"]["sha256"]
            and sha(c2d) == full_receipt["artifacts"]["session_directory"]["sha256"],
            "complete emission artifacts no longer bind to receipt")

    compile_host()
    with tempfile.TemporaryDirectory(prefix="lisp65-c2-stream-") as raw:
        temporary = Path(raw)
        execution = execute(HOST_BIN, shelf, c2d, temporary)
        match = re.fullmatch(
            r"c2-stream: PASS shelf=69754 images=6 entries=583 descriptors=2249 "
            r"names=1095 strings=116 unique-symbols=344 pairs=168 context=36\n?",
            execution.stdout)
        require(match is not None and not execution.stderr, "complete streaming execution drift")
        mutations = mutation_matrix(HOST_BIN, shelf, c2d, temporary)

    for path in (TARGET_A.parent, TARGET_B.parent):
        if path.exists():
            shutil.rmtree(path)
    elf_a, map_a = compile_target(TARGET_A, "17")
    elf_b, map_b = compile_target(TARGET_B, "83")
    require(TARGET_A.read_bytes() == TARGET_B.read_bytes(),
            "varied llvm-mos target links differ")
    phases_a, seams_a = symbol_sizes(elf_a)
    phases_b, seams_b = symbol_sizes(elf_b)
    require(phases_a == phases_b and seams_a == seams_b,
            "varied target symbol sizes differ")
    sizes_a = parse_size(run([str(SIZE), str(elf_a)]).stdout)
    sizes_b = parse_size(run([str(SIZE), str(elf_b)]).stdout)
    require(sizes_a == sizes_b, "varied target aggregate sizes differ")
    sliced = sum(phases_a.values())
    require(sliced == 10388 and max(phases_a.values()) == 1682,
            "streaming phase sizing drift")

    return {
        "format": "lisp65-c2.1-streaming-decoder-link-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "full-streaming-host-passed-sliced-mos-linked-product-substitution-not-run",
        "claim_limit": (
            "This receipt executes the complete six-image, 69,754-byte L65S-v4-direct "
            "shelf and 10,480-byte C2D-v1 session directory through a bounded streaming C "
            "decoder, rejects eight full-file mutations, and proves ten independently "
            "loadable llvm-mos phases fit the existing 1,792-byte runtime slot. The target "
            "artifact is a link harness, not a product substitution link, capacity "
            "authorization, product candidate or device-execution claim."
        ),
        "bindings": {
            "full_emission": bind(FULL_RECEIPT), "contract": bind(F.CONTRACT),
            "document": bind(DOCUMENT),
            "header": bind(HEADER), "core": bind(CORE), "init": bind(INIT),
            "host_harness": bind(HOST_SOURCE), "target_harness": bind(TARGET_SOURCE),
            "phase_wrappers": [bind(path) for path in PHASES],
            "orchestrator": bind(Path(__file__)),
            "compiler": bind(ROOT / "tools/llvm-mos/bin/clang-23"),
        },
        "full_execution": {
            "shelf_bytes": len(shelf), "u16_shelf_limit_exceeded_by": len(shelf) - 65535,
            "c2d_bytes": len(c2d), "images": 6, "entries": 583,
            "descriptors": 2249, "name_or_string_values": 1095,
            "string_values": 116, "unique_interned_symbols": 344,
            "equal_symbol_spellings_share_identity": True,
            "pair_values": 168, "context_bytes": 36,
            "decoder_passes": 10, "recursive_pair_walks": 0,
        },
        "negative_matrix": {"passed": len(mutations), "cases": mutations},
        "target_link": {
            "runtime_slot_bytes": SLOT_BYTES,
            "phase_bytes": phases_a,
            "phase_total_bytes": sliced,
            "largest_phase_bytes": max(phases_a.values()),
            "smallest_phase_headroom": SLOT_BYTES - max(phases_a.values()),
            "proof_seam_bytes": seams_a,
            "aggregate": sizes_a,
            "artifact": bind(TARGET_A), "elf": bind(elf_a), "map": bind(map_a),
            "varied_second_link": {"artifact": bind(TARGET_B), "elf": bind(elf_b),
                                     "map": bind(map_b)},
            "varied_links_byteidentical": True,
            "device_execution": "not-run",
        },
        "consumer_boundary": {
            "call_graph_evidence_kind": 5,
            "general_symbol_kind": 8,
            "rule": "Tree-shaking, who-calls and ide-help cross-references consume only kind 5; kind 8 is invisible.",
        },
        "capacity_delta": {
            "scope": "standalone-sliced-proof-artifact-only", "product_bytes": 0,
            "bank0": "not-integrated-not-measured", "ext": "not-integrated-not-measured",
            "fixed_overlay": "not-integrated-not-measured",
            "runtime_overlay_bank": "not-integrated-not-measured",
            "resident_island": "not-integrated-not-measured",
            "installer_slice": "not-integrated-not-measured",
        },
        "next_action": "Real product-layout substitution link retiring all 28 L65M slices and the Bank-0 directory arrays",
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            value = render()
            require(value["negative_matrix"]["passed"] == 8
                    and value["target_link"]["varied_links_byteidentical"],
                    "streaming selftest closure")
            print("c2-stream-decoder: SELFTEST PASS full=2249 negatives=8 slices=10/10")
            return 0
        value = render(); data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data); verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "C2 streaming decoder receipt drift; regenerate with write")
            verb = "PASS"
        print(f"c2-stream-decoder: {verb} full=2249 negatives=8 "
              f"largest={value['target_link']['largest_phase_bytes']}/1792 product-link=not-run")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, StreamError, F.FullError) as error:
        print(f"c2-stream-decoder: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
