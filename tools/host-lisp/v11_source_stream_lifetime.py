#!/usr/bin/env python3
"""Prove that disk-source reading survives C1 reuse of the file scratch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
LLVM_MOS_ROOT = Path(os.environ.get("LLVM_MOS_ROOT", ROOT / "tools/llvm-mos")).resolve()
FORMAT = "lisp65-v11-source-stream-lifetime-gate-v1"
SECTOR_PAYLOAD = 254
ISLAND_START = 0x1800
ISLAND_LIMIT = 0x2000
INSTALLER_LIMIT = 1792


class GateError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _function_body(source: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;{]*\)\s*\{", source)
    if not match:
        raise GateError(f"missing C function {name}")
    brace = source.find("{", match.start())
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise GateError(f"unterminated C function {name}")


def _chain(data: bytes) -> list[bytes]:
    chunks = [data[i:i + SECTOR_PAYLOAD] for i in range(0, len(data), SECTOR_PAYLOAD)]
    sectors: list[bytes] = []
    for index, chunk in enumerate(chunks):
        link = bytes((45, 33 + index)) if index + 1 < len(chunks) else bytes((0, len(chunk) + 1))
        sectors.append(link + chunk + bytes(SECTOR_PAYLOAD - len(chunk)))
    return sectors


def _model(source: bytes) -> dict:
    sectors = _chain(source)
    file_scratch = bytearray(source)
    directory_scratch = bytearray(sectors[0])
    old_out = bytearray(file_scratch[:209])
    new_out = bytearray(directory_scratch[2:2 + 209])
    replacement = (b"L65M-C1-COMPILER-CONTAINER" * 16)[:len(file_scratch)]
    file_scratch[:len(replacement)] = replacement
    old_out.extend(file_scratch[209:])
    position = sector_position = 209
    sector_index = 0
    while position < len(source):
        if sector_position >= SECTOR_PAYLOAD:
            sector_index += 1
            directory_scratch[:] = sectors[sector_index]
            sector_position = 0
        new_out.append(directory_scratch[2 + sector_position])
        sector_position += 1
        position += 1
    _require(bytes(old_out) != source, "old shared-scratch model unexpectedly survived C1")
    _require(bytes(new_out) == source, "sector-stream model did not preserve the exact source")
    return {
        "source_bytes": len(source),
        "sectors": len(sectors),
        "c1_replacement_after_reader_bytes": 209,
        "shared_file_scratch": "corrupted-as-expected",
        "disjoint_directory_scratch": "byte-identical",
    }


def _symbols(nm: Path, elf: Path) -> dict[str, tuple[int, int]]:
    output = subprocess.check_output([str(nm), "-S", "--size-sort", str(elf)], cwd=ROOT, text=True)
    found: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            try:
                found[fields[-1]] = (int(fields[0], 16), int(fields[1], 16))
            except ValueError:
                pass
    return found


def build_report(args: argparse.Namespace) -> dict:
    model = _model(args.fixture.read_bytes())
    io_source = args.io_source.read_text(encoding="utf-8")
    runtime_source = args.runtime_source.read_text(encoding="utf-8")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    overlays = json.loads(args.overlays.read_text(encoding="utf-8"))
    fetch = _function_body(io_source, "disk_source_fetch")
    load = _function_body(io_source, "io_disk_load_chain")
    installer = _function_body(runtime_source, "vm_resident_island_install")
    transport = _function_body(runtime_source, "vm_runtime_overlay_exec")
    _require("LISP65_RESIDENT_ISLAND_FN char disk_source_fetch" in io_source,
             "source fetch is not resident across runtime-overlay swaps")
    for token in ("io_disk_byte(0)", "io_disk_byte(1)", "io_disk_read_sector(nt, ns)"):
        _require(token in fetch, f"source fetch omits {token}")
    _require("ext_disk_get" not in fetch and "DISK_EXT_FILE" not in fetch,
             "source fetch still reads the C1-owned file scratch")
    _require("io_disk_read_sector(track, sector)" in load and
             "load_source_stream(disk_source_fetch)" in load,
             "disk load does not preload and bind the disjoint source stream")
    _require("rtov_crc_mem" in installer, "installer omits destination CRC")
    for token in ("rtov_run_verifier", "verify.file_len", "verify.payload_crc", "rtov_crc_mem"):
        _require(token in transport, f"resident transport omits {token}")
    _require(not any(token in installer for token in ("abi_version", "cookie", "capacity")),
             "installer reintroduced redundant context identity fields")
    allowed = {row.get("name"): row for row in policy.get("allowed_symbols", [])}
    _require(allowed.get("disk_source_fetch", {}).get("coordinator_class") == "source-stream",
             "resident-island policy omits the source-stream allocation")
    slices = {int(row["id"]): row for row in overlays.get("slices", [])}
    installer_slice = slices.get(37)
    _require(installer_slice is not None, "runtime manifest omits installer slice 37")
    installer_bytes = int(installer_slice["memory_size"])
    _require(installer_bytes <= INSTALLER_LIMIT, "installer exceeds its product pin")
    symbols = _symbols(args.nm, args.elf)
    _require("disk_source_fetch" in symbols, "ELF omits disk_source_fetch")
    address, size = symbols["disk_source_fetch"]
    _require(ISLAND_START <= address < ISLAND_LIMIT and address + size <= ISLAND_LIMIT,
             "disk_source_fetch is outside the resident island")
    return {
        "format": FORMAT,
        "status": "pass",
        "model": model,
        "bindings": {
            "fixture": {"path": _relative(args.fixture), "sha256": _sha(args.fixture)},
            "io_source": {"path": _relative(args.io_source), "sha256": _sha(args.io_source)},
            "runtime_source": {"path": _relative(args.runtime_source), "sha256": _sha(args.runtime_source)},
            "policy": {"path": _relative(args.policy), "sha256": _sha(args.policy)},
            "elf": {"path": _relative(args.elf), "sha256": _sha(args.elf)},
            "overlays": {"path": _relative(args.overlays), "sha256": _sha(args.overlays)},
        },
        "resident_source_fetch": {"address": address, "bytes": size, "window": [ISLAND_START, ISLAND_LIMIT]},
        "installer_slice": {
            "bytes": installer_bytes,
            "limit_bytes": INSTALLER_LIMIT,
            "headroom_bytes": INSTALLER_LIMIT - installer_bytes,
        },
        "claim_limit": (
            "This gate proves the scratch-lifetime model and exact source/link bindings. "
            "Final hardware acceptance remains the SHA-bound multi-sector chain-write case."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/disk/m3-chain-source.lisp")
    parser.add_argument("--io-source", type=Path, default=ROOT / "src/io.c")
    parser.add_argument("--runtime-source", type=Path, default=ROOT / "src/vm_runtime_overlay.c")
    parser.add_argument("--policy", type=Path, default=ROOT / "config/bank0-island-workbench.json")
    parser.add_argument("--elf", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay-linked.prg.elf")
    parser.add_argument("--overlays", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/runtime-overlays-manifest.json")
    parser.add_argument("--nm", type=Path, default=LLVM_MOS_ROOT / "bin/llvm-nm")
    parser.add_argument("--out", type=Path, default=ROOT / "build/reports/workbench/v11-source-stream-lifetime.json")
    args = parser.parse_args()
    try:
        if args.selftest:
            result = _model(args.fixture.read_bytes())
            print(f"v11-source-stream-lifetime: SELFTEST PASS source={result['source_bytes']} sectors={result['sectors']}")
            return 0
        report = build_report(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (GateError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"v11-source-stream-lifetime: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-source-stream-lifetime: PASS source=%d sectors=%d fetch=%dB installer=%dB headroom=%dB report=%s"
        % (report["model"]["source_bytes"], report["model"]["sectors"],
           report["resident_source_fetch"]["bytes"], report["installer_slice"]["bytes"],
           report["installer_slice"]["headroom_bytes"], _relative(args.out))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
