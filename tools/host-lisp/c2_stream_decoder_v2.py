#!/usr/bin/env python3
"""Prove the owner-approved C2D-v2 product decoder before substitution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_bcode_contract as B  # noqa: E402
import c2_gc_root_single_source as G  # noqa: E402
import c2_stream_decoder as V1  # noqa: E402

BUILD = ROOT / "build/c2.1/streaming-decoder-v2"
HOST = BUILD / "c2-stream-v2-host"
TARGET_A = BUILD / "proof-a/c2-stream-v2.prg"
TARGET_B = BUILD / "proof-b/c2-stream-v2.prg"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-streaming-decoder-v2-link-receipt.json"
)
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
SIZE = ROOT / "tools/llvm-mos/bin/llvm-size"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
SLOT_BYTES = 1792

INIT = ROOT / "scripts/c2-stream-init.c"
OLD_PHASES = [ROOT / f"scripts/c2-stream-phase-{n:02d}.c" for n in range(1, 7)]
V2_PHASES = [ROOT / "scripts/c2-stream-v2-phase-00.c"] + [
    ROOT / f"scripts/c2-stream-v2-phase-{n:02d}.c" for n in range(7, 14)
]
SOURCES = [INIT, V2_PHASES[0], *OLD_PHASES, *V2_PHASES[1:]]
HOST_SOURCE = ROOT / "scripts/c2-stream-v2-host-main.c"
TARGET_SOURCE = ROOT / "scripts/c2-stream-v2-target-main.c"
HEADER = ROOT / "scripts/c2-stream-v2-decoder.h"
CORE = ROOT / "scripts/c2-stream-v2-decoder.c"
CONTRACT = ROOT / "config/c2-gc-root-single-source-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-gc-root-single-source-addendum.md"
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-gc-root-single-source-receipt.json"
)


class V2Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V2Error(message)


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
        raise V2Error(f"{Path(argv[0]).name} returned {result.returncode}, expected "
                      f"{expected}: {(result.stderr or result.stdout).strip()}")
    return result


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def compile_host() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    result = run(["cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
                  "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
                  *map(str, SOURCES), str(HOST_SOURCE),
                  "-o", str(HOST)])
    require(not result.stdout and not result.stderr, "host compiler diagnostics")


def execute(shelf: bytes, c2d: bytes, directory: Path,
            mode: str | None = None) -> subprocess.CompletedProcess[str]:
    shelf_path = directory / "shelf.bin"; c2d_path = directory / "c2d.bin"
    shelf_path.write_bytes(shelf); c2d_path.write_bytes(c2d)
    argv = [str(HOST), str(shelf_path), str(c2d_path)]
    if mode is not None:
        argv.append(mode)
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)


def rejected(shelf: bytes, c2d: bytes, directory: Path, label: str,
             *, phase: int, status: int, mode: str | None = None) -> dict[str, Any]:
    result = execute(shelf, c2d, directory, mode)
    prefix = f"c2-stream-v2: FAIL phase={phase} status={status} finished=0"
    require(result.returncode == status and result.stderr.startswith(prefix),
            f"{label} not rejected at phase {phase}/status {status}: "
            f"rc={result.returncode} err={result.stderr.strip()!r}")
    return {"case": label, "phase": phase, "status": status, "finished": False}


def descriptor_location(shelf: bytes, images: list[Any], wanted_kind: int) -> tuple[int, int, int]:
    global_ordinal = 0
    for image_index, image in enumerate(images):
        metadata = (shelf[32 + image_index * 32 + 13]
                    | shelf[32 + image_index * 32 + 14] << 8
                    | shelf[32 + image_index * 32 + 15] << 16)
        literal_offset = u16(shelf, metadata + 16)
        for local, descriptor in enumerate(image.descriptors):
            if descriptor.kind == wanted_kind:
                return image_index, metadata + literal_offset + local * 8, global_ordinal
            global_ordinal += 1
    raise V2Error(f"descriptor kind {wanted_kind} absent")


def negative_matrix(images: list[Any], shelf_raw: bytes, c2d1: bytes,
                    c2d2: bytes, directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.append(rejected(shelf_raw, c2d1, directory, "v1-to-v2", phase=0, status=3))
    try:
        F.decode_c2d(c2d2, images, [], struct.unpack_from("<I", shelf_raw, 18)[0])
    except (F.FullError, IndexError):
        rows.append({"case": "v2-to-v1", "phase": "legacy-decoder", "status": "rejected"})
    else:
        raise V2Error("legacy C2D-v1 decoder accepted v2")

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d2)
    struct.pack_into("<H", c2d, 26, u16(c2d, 26) - 1)
    rows.append(rejected(shelf, c2d, directory, "root-count", phase=0, status=3))
    shelf, c2d = bytearray(shelf_raw), bytearray(c2d2)
    struct.pack_into("<H", c2d, 24, u16(c2d, 24) - 2)
    rows.append(rejected(shelf, c2d, directory, "total-truncated", phase=0, status=3))
    rows.append(rejected(shelf_raw, c2d2 + b"\0\0", directory,
                         "trailing-data", phase=0, status=3))

    image, descriptor_at, root_ordinal = descriptor_location(shelf_raw, images, F.K_STRING)
    rows.append(rejected(shelf_raw, c2d2, directory, "heap-root-missing", phase=9,
                         status=7, mode=f"resolution:{root_ordinal}:65535"))
    rows.append(rejected(shelf_raw, c2d2, directory, "heap-root-reordered", phase=9,
                         status=7, mode=f"resolution:{root_ordinal}:1"))

    shelf, c2d = bytearray(shelf_raw), bytearray(c2d2)
    shelf[descriptor_at] = F.K_SYMBOL
    V1.repair_image(shelf, c2d, image)
    rows.append(rejected(shelf, c2d, directory, "direct-as-root", phase=7, status=7))

    rows.append(rejected(shelf_raw, c2d2, directory, "zero-root-value", phase=12,
                         status=7, mode="root:0:0"))
    rows.append(rejected(shelf_raw, c2d2, directory, "nonpointer-root-value", phase=12,
                         status=7, mode="root:0:3"))
    entry_image, _at, first_entry = descriptor_location(
        shelf_raw, images, F.K_ENTRY)
    entry_descriptor = next(
        descriptor for descriptor in images[entry_image].descriptors
        if descriptor.kind == F.K_ENTRY)
    directory_base = sum(
        len(image.manifest["entries"]) for image in images[:entry_image])
    wrong_fixnum = B.mk_bcode(directory_base + entry_descriptor.arg0) | 1
    rows.append(rejected(
        shelf_raw, c2d2, directory, "direct-entry-as-fixnum", phase=12,
        status=7, mode=f"post-resolution:{first_entry}:{wrong_fixnum}"))
    shelf, c2d = bytearray(shelf_raw), bytearray(c2d2); c2d[28] ^= 1
    rows.append(rejected(shelf, c2d, directory, "catalog-identity", phase=1, status=2))
    require(len(rows) == 12, "negative matrix closure")
    return rows


def rollback_matrix(shelf: bytes, c2d: bytes, directory: Path) -> list[dict[str, Any]]:
    # Phase boundaries plus interior writes. Every stop must remain unpublished.
    cuts = [1, 2, 64, 283, 284, 285, 600, 1000, 1270, 1271,
            1386, 1387, 2000, 2365, 2366, 2533]
    rows = []
    for cut in cuts:
        result = execute(shelf, c2d, directory, f"fail-write:{cut}")
        require(result.returncode != 0 and "finished=0" in result.stderr,
                f"write-fault {cut} published or passed: {result.stderr.strip()!r}")
        match = re.search(r"phase=(\d+) status=(\d+).*writes=(\d+)", result.stderr)
        require(match is not None and int(match.group(3)) == cut,
                f"write-fault {cut} diagnostics")
        rows.append({"write_call": cut, "phase": int(match.group(1)),
                     "status": int(match.group(2)), "published": False})
    return rows


def compile_target(output: Path, *, epoch: str, timezone: str) -> tuple[Path, Path]:
    if output.parent.exists():
        shutil.rmtree(output.parent)
    output.parent.mkdir(parents=True)
    map_path = output.with_suffix(".map")
    env = dict(os.environ)
    env.update({"SOURCE_DATE_EPOCH": epoch, "PYTHONHASHSEED": "0",
                "TZ": timezone, "TMPDIR": str(output.parent)})
    result = run([str(CC), "-mllvm", "-rng-seed=0", "-std=c99", "-Os",
                  "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
                  *map(str, SOURCES), str(TARGET_SOURCE), "-Wl,--icf=none",
                  "-Wl,-Map," + str(map_path), "-o", str(output)], env=env)
    elf = Path(str(output) + ".elf")
    require(not result.stdout and not result.stderr and output.is_file() and elf.is_file(),
            "target link diagnostics/artifacts")
    return elf, map_path


def target_sizes(elf: Path) -> tuple[dict[str, int], dict[str, int]]:
    output = run([str(NM), "--print-size", "--size-sort", "--radix=x", str(elf)]).stdout
    phases: dict[str, int] = {}; seams: dict[str, int] = {}
    seam_names = {"c2_stream_shelf_read", "c2_stream_c2d_read", "c2_stream_c2d_write",
                  "c2_stream_name_value", "c2_stream_pair_value",
                  "c2_stream_gc_checkpoint", "c2_stream_materialize_entry"}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        name, size = fields[-1], int(fields[1], 16)
        if re.fullmatch(r"c2_stream_phase_\d\d", name):
            phases[name] = size
        elif name in seam_names:
            seams[name] = size
    require(len(phases) == 13 and set(seams) == seam_names,
            "v2 target symbol inventory")
    packed = dict(phases); packed["c2_stream_materialize_entry"] = seams["c2_stream_materialize_entry"]
    require(all(value <= SLOT_BYTES for value in packed.values()),
            "v2 phase exceeds 1,792-byte runtime slot")
    return dict(sorted(phases.items())), dict(sorted(seams.items()))


def aggregate(elf: Path) -> dict[str, int]:
    rows = [line.split() for line in run([str(SIZE), str(elf)]).stdout.splitlines() if line.strip()]
    require(len(rows) >= 2 and rows[0][:4] == ["text", "data", "bss", "dec"], "size output")
    row = rows[-1]
    return {"text": int(row[0]), "data": int(row[1]), "bss": int(row[2]), "dec": int(row[3])}


def characterize_target_allocator() -> list[dict[str, Any]]:
    shapes: dict[str, dict[str, Any]] = {}
    for attempt in range(8):
        output = BUILD / f"allocation-attempt-{attempt}/c2-stream-v2.prg"
        elf, _map = compile_target(
            output,
            epoch=str(1784419200 + attempt * 86400),
            timezone="UTC" if attempt % 2 == 0 else "Pacific/Honolulu",
        )
        digest = sha(output.read_bytes())
        phases, seams = target_sizes(elf)
        packed = {**phases, "c2_stream_materialize_entry": seams["c2_stream_materialize_entry"]}
        row = {
            "prg_sha256": digest, "prg_bytes": output.stat().st_size,
            "phase_bytes": phases, "seam_bytes": seams, "aggregate": aggregate(elf),
            "largest_packed_function_bytes": max(packed.values()),
            "smallest_headroom_bytes": SLOT_BYTES - max(packed.values()),
        }
        if digest in shapes:
            require(shapes[digest] == row, "same PRG hash has different allocation metrics")
        else:
            shapes[digest] = row
    require(len(shapes) == 2, f"expected two characterized allocation shapes, got {len(shapes)}")
    rows = [shapes[key] for key in sorted(shapes)]
    for target, row in zip((TARGET_A, TARGET_B), rows):
        target.parent.mkdir(parents=True, exist_ok=True)
        source = next(
            BUILD / f"allocation-attempt-{attempt}/c2-stream-v2.prg"
            for attempt in range(8)
            if sha((BUILD / f"allocation-attempt-{attempt}/c2-stream-v2.prg").read_bytes())
            == row["prg_sha256"]
        )
        shutil.copyfile(source, target)
    return rows


def render() -> dict[str, Any]:
    approval = json.loads(HOST_RECEIPT.read_text(encoding="utf-8"))
    require(approval["status"] == "option-b2-owner-approved-product-work-authorized",
            "B2 owner approval absent")
    images, shelf, c2d1, facts = F.build_all(); c2d2, logical = G.build_v2(images, c2d1)
    require(len(shelf) == 69754 and len(c2d2) == 11048 and len(logical) == 2249,
            "C2D-v2 full geometry")
    compile_host()
    with tempfile.TemporaryDirectory(prefix="lisp65-c2-v2-") as raw:
        directory = Path(raw)
        result = execute(shelf, c2d2, directory)
        require(result.returncode == 0 and result.stderr == "" and re.fullmatch(
            r"c2-stream-v2: PASS shelf=69754 c2d=11048 images=6 entries=583 "
            r"descriptors=2249 roots=284 gc=284 materialized=583 max-literals=23 context=44\n?",
            result.stdout) is not None, "full C2D-v2 execution")
        negatives = negative_matrix(images, shelf, c2d1, c2d2, directory)
        rollbacks = rollback_matrix(shelf, c2d2, directory)

    shapes = characterize_target_allocator()

    return {
        "format": "lisp65-c2.1-streaming-decoder-v2-link-receipt-v1",
        "version": 1, "recorded_on": "2026-07-19",
        "status": "c2d-v2-product-decoder-proof-passed-real-substitution-link-next",
        "claim_limit": (
            "This receipt executes the complete owner-approved C2D-v2 image through the "
            "product-shaped sliced C decoder, collects after all 284 heap publications, "
            "materializes all 583 hot literal windows, rejects eleven format/identity "
            "violations, proves fail-closed behavior at sixteen write cutpoints and "
            "characterizes both allocator-equivalent llvm-mos proof-link shapes. It is "
            "not yet the real product "
            "substitution link, a capacity authorization, device run or product candidate."
        ),
        "bindings": {
            "owner_approval": bind(HOST_RECEIPT), "contract": bind(CONTRACT),
            "document": bind(DOCUMENT), "header": bind(HEADER), "core": bind(CORE),
            "init": bind(INIT), "unchanged_v1_validation_phases": [bind(p) for p in OLD_PHASES],
            "v2_phase_wrappers": [bind(p) for p in V2_PHASES],
            "host_harness": bind(HOST_SOURCE), "target_harness": bind(TARGET_SOURCE),
            "orchestrator": bind(Path(__file__)), "compiler": bind(ROOT / "tools/llvm-mos/bin/clang-23"),
        },
        "execution": {
            "shelf_bytes": len(shelf), "c2d_v2_bytes": len(c2d2),
            "c2d_v2_sha256": sha(c2d2), "images": 6, "entries": 583,
            "descriptors": 2249, "root_values": 284, "root_bytes": 568,
            "gc_checkpoints": 284, "gc_writebacks": 0,
            "materialized_entries": 583, "maximum_hot_literals": 23,
            "context_bytes": 44, "publication": "after-complete-root-recheck",
        },
        "negative_matrix": {"passed": len(negatives), "cases": negatives},
        "rollback_matrix": {"passed": len(rollbacks), "cases": rollbacks},
        "target_link": {
            "runtime_slot_bytes": SLOT_BYTES,
            "largest_packed_function_bytes": max(x["largest_packed_function_bytes"] for x in shapes),
            "smallest_headroom_bytes": min(x["smallest_headroom_bytes"] for x in shapes),
            "phase_count": 13, "hot_materializer_is_own_slice": True,
            "repeated_links": 8, "observed_allocation_shapes": shapes,
            "canonical_shape_artifacts": [bind(TARGET_A), bind(TARGET_B)],
            "varied_links_byteidentical": False,
            "determinism_axes": ["SOURCE_DATE_EPOCH", "TZ", "fresh-output-directory", "process-allocation"],
            "compiler_rng_seed": 0,
            "standalone_allocator_claim_limit": (
                "The standalone whole-program proof harness has exactly two observed, "
                "semantically equivalent allocator shapes. Both fit. Byte identity is "
                "not claimed here; the real product fresh-build gate is authoritative."
            ),
            "device_execution": "not-run",
        },
        "capacity_delta": {
            "scope": "standalone-sliced-product-decoder-proof-only", "product_bytes": 0,
            "bank0": "not-integrated-not-measured", "ext": "not-integrated-not-measured",
            "fixed_overlay": "not-integrated-not-measured",
            "runtime_overlay_bank": "not-integrated-not-measured",
            "resident_island": "not-integrated-not-measured",
            "installer_slice": "not-integrated-not-measured",
        },
        "next_action": "Real product substitution link retiring 28 legacy L65M phases and Bank-0 materializer state.",
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = render()
        if args.action == "selftest":
            print("c2-stream-decoder-v2: SELFTEST PASS roots=284 negatives=11 rollbacks=16 slices=14/14")
            return 0
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True); RECEIPT.write_bytes(data); verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "C2D-v2 decoder receipt drift; regenerate with write")
            verb = "PASS"
        print(f"c2-stream-decoder-v2: {verb} roots=284 negatives=11 rollbacks=16 "
              f"largest={value['target_link']['largest_packed_function_bytes']}/1792 "
              f"allocator-shapes=2 substitution=next")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, V2Error, F.FullError,
            G.SingleSourceError, V1.StreamError) as error:
        print(f"c2-stream-decoder-v2: FAIL: {error}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
