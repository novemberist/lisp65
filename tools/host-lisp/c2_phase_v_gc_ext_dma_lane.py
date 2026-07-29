#!/usr/bin/env python3
"""Product-shaped host lane for the Link-77 EXT-heap GC First Red.

The reference lane uses the historical direct host backing array.  The DMA
lane runs the same Mark/Sweep and cell accessor code while every EXT access
crosses the checked staged-copy model in mem.c.  Both lanes freeze their boot
allocation prefix before executing the exact hardware reproducer.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/post-promotion/link77-gc-ext-dma-host-lane"
FIXTURE = ROOT / "tests/equivalence/while-target-gc-transient.lisp"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-ext-dma-host-lane-receipt.json"
)
FORMAT = "lisp65-c2.2-link77-gc-ext-dma-host-lane-receipt-v1"

SOURCES = [
    ROOT / "scripts/equivalence-main.c",
    ROOT / "src/eval.c",
    ROOT / "src/compile.c",
    ROOT / "src/compile_repl.c",
    ROOT / "src/lcc_install_overlay.c",
    ROOT / "src/vm.c",
    ROOT / "src/mem.c",
    ROOT / "src/symbol.c",
    ROOT / "src/reader.c",
    ROOT / "src/printer.c",
    ROOT / "src/io.c",
    ROOT / "src/interrupt.c",
    ROOT / "src/screen.c",
]

DEFINES = [
    "LISP65_DIALECT_V2",
    "LISP65_COMPILE_REPL",
    "LISP65_VM",
    "LISP65_VM_GLOBAL_PRIMS",
    "LISP65_EVAL_PRIMS",
    "LISP65_EVAL_CONTROL_SF",
    "LISP65_VM_APPLY_OPFN",
    "LISP65_MACROEXPAND_PRIM",
    "LISP65_LCC_INSTALL",
    "HEAP_CELLS=48",
    "EXT_CELLS=1024",
    "LISP65_EXT_HEAP",
    "LISP65_MARK_BITMAP",
    "LISP65_NURSERY_HYSTERESIS=192",
    "LISP65_GC_LANE_PROBE",
    "LISP65_STRING_ARENA",
    "STR_ARENA_SIZE=0x2480",
    "GC_ROOTS=128",
    "MAX_SYM=512",
    "NAMEPOOL=8192",
    "VM_DIR_MAX=128",
    "IO_BUF_MAX=16",
]

STAT_RE = re.compile(r"^gc-lane:\s+(.*)$", re.MULTILINE)


class LaneError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LaneError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def compile_lane(name: str, extra: list[str]) -> Path:
    binary = BUILD / name
    command = [
        os.environ.get("HOSTCC", "cc"),
        "-std=c99",
        "-Wall",
        "-Wno-unused-function",
        *[f"-D{value}" for value in DEFINES + extra],
        "-Isrc",
        *[str(path.relative_to(ROOT)) for path in SOURCES],
        "-o",
        str(binary.relative_to(ROOT)),
    ]
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        f"{name} compile red:\n{result.stdout}",
    )
    return binary


def parse_stats(stderr: str) -> dict[str, int]:
    match = STAT_RE.search(stderr)
    require(match is not None, f"GC lane report absent:\n{stderr}")
    values: dict[str, int] = {}
    for field in match.group(1).split():
        key, raw = field.split("=", 1)
        values[key] = int(raw, 10)
    return values


def run_lane(binary: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env.update({
        "LISP65_EQ_FREEZE_BOOT": "1",
        "LISP65_EQ_REQUIRE_GC": "1",
        "LISP65_EQ_REQUIRE_NO_OOM": "1",
        "LISP65_EQ_GC_LANE_REPORT": "1",
    })
    result = subprocess.run(
        [str(binary), "vm", str(FIXTURE)],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=30)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stats": parse_stats(result.stderr),
    }


def accepted(name: str, run: dict[str, Any], dma_model: int) -> None:
    stats = run["stats"]
    require(
        run["returncode"] == 0
        and run["stdout"].rstrip().endswith("=> 600")
        and stats["runs"] > 0
        and stats["frozen"] > 0
        and stats["marked"] > 0
        and stats["reclaimed"] > 0
        and stats["free_after"] > 0
        and stats["final_free"] > 0
        and stats["mem_oom"] == 0
        and stats["dma_model"] == dma_model
        and stats["dma_faults"] == 0,
        f"{name} did not prove successful post-freeze collection: {run}",
    )
    if dma_model:
        require(
            stats["dma_reads"] > 0
            and stats["dma_writes"] > 0
            and stats["dma_bytes"] > 0,
            "modeled DMA lane bypassed the transport boundary",
        )


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    direct_binary = compile_lane("direct", [])
    dma_binary = compile_lane("dma", ["LISP65_EXT_HEAP_HOST_DMA_MODEL"])
    mutation_binary = compile_lane(
        "dma-verification-mutation",
        [
            "LISP65_EXT_HEAP_HOST_DMA_MODEL",
            "LISP65_EXT_HEAP_HOST_DMA_MODEL_MUTATION",
        ],
    )

    direct = run_lane(direct_binary)
    dma = run_lane(dma_binary)
    mutation = run_lane(mutation_binary)
    accepted("direct EXT reference", direct, 0)
    accepted("checked DMA model", dma, 1)

    comparable = (
        "runs", "marked", "reclaimed", "free_before", "free_after",
        "min_free_after", "alloc_high", "frozen", "final_free", "mem_oom",
    )
    require(
        {key: direct["stats"][key] for key in comparable}
        == {key: dma["stats"][key] for key in comparable},
        "direct and modeled-DMA collector accounting diverged",
    )
    require(
        mutation["returncode"] == 7
        and mutation["stats"]["dma_faults"] > 0
        and "modeled EXT DMA verification failed" in mutation["stderr"],
        "DMA verification mutation was not rejected",
    )

    receipt = {
        "format": FORMAT,
        "recorded_on": "2026-07-29",
        "status": "passed-no-host-reproduction",
        "fixture": bind(FIXTURE),
        "geometry": {
            "hot_cells": 48,
            "extended_cells": 1024,
            "boot_prefix_frozen": True,
        },
        "implementation": {
            "collector_and_cell_access": bind(ROOT / "src/mem.c"),
            "harness": bind(ROOT / "scripts/equivalence-main.c"),
            "gate": bind(Path(__file__)),
            "public_product_gate": bind(ROOT / "mk/workbench.mk"),
            "legacy_gc_smoke_gate": bind(ROOT / "Makefile"),
            "sources": [bind(path) for path in SOURCES],
        },
        "lanes": {
            "direct_ext_reference": {
                "binary": bind(direct_binary),
                "stats": direct["stats"],
                "result": "600",
            },
            "checked_dma_copy": {
                "binary": bind(dma_binary),
                "stats": dma["stats"],
                "result": "600",
            },
        },
        "mutation": {
            "id": "modeled-dma-verification-fault",
            "rejected": True,
            "returncode": mutation["returncode"],
            "faults": mutation["stats"]["dma_faults"],
        },
        "execution_witness": {
            "expected_cases": 3,
            "executed_cases": 3,
            "cases": [
                "direct-ext-reference",
                "checked-dma-copy",
                "modeled-dma-verification-fault",
            ],
            "positive": True,
        },
        "classification": {
            "algorithm": "entlastet by direct EXT reference",
            "checked_copy_transport_semantics": "entlastet by modeled DMA lane",
            "remaining_boundary": (
                "physical EXT DMA completion/read-write behavior or target-only "
                "product root state; no product fix is attributed"
            ),
            "next_discriminator": (
                "on target, count marked cells and cells returned to the "
                "freelist by the failing collection"
            ),
        },
        "claim_limit": (
            "This host lane models checked copy semantics and the boot-frozen "
            "collector state. It does not model physical DMA completion timing "
            "or reproduce the complete live C2D root plane."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(
        "c2-phase-v-gc-ext-dma-lane: PASS "
        f"runs={dma['stats']['runs']} marked={dma['stats']['marked']} "
        f"reclaimed={dma['stats']['reclaimed']} "
        f"dma_jobs={dma['stats']['dma_reads'] + dma['stats']['dma_writes']} "
        "hardware_oom=not-reproduced"
    )


if __name__ == "__main__":
    try:
        main()
    except (LaneError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"c2-phase-v-gc-ext-dma-lane: FIRST RED: {exc}")
