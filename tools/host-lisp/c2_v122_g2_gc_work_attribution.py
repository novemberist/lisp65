#!/usr/bin/env python3
"""Host-only G2 work attribution for one real Mark/Sweep collection.

This lane deliberately counts work, not host time.  The checked-copy EXT
model exercises the real collector and cell accessors; phase counters exclude
the observer's own freelist walks.  Target frame observations remain external
authorities and are never divided into invented milliseconds.
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
BUILD = ROOT / "build/post-promotion/v1.2.2-g2-gc-work-attribution"
FIXTURE = ROOT / "tests/equivalence/while-target-gc-transient.lisp"
LINK66 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link66-bundled-hardware-measurements-receipt.json"
)
FINAL_G5 = ROOT / (
    "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/"
    "g5-hardware-receipt.json"
)
FINAL_G5_COUNTERS = ROOT / (
    "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/"
    "g5/counters/after_gc_envelope.txt"
)
PRIOR_LEDGER = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-phase-m2-gc-envelope-attribution-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-gc-work-attribution-receipt.json"
)
FORMAT = "lisp65-c2.2-v1.2.2-g2-gc-work-attribution-v1"

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
    "LISP65_GC_WORK_ATTRIBUTION_PROBE",
    "LISP65_STRING_ARENA",
    "STR_ARENA_SIZE=0x2480",
    "GC_ROOTS=128",
    "MAX_SYM=512",
    "NAMEPOOL=8192",
    "VM_DIR_MAX=128",
    "IO_BUF_MAX=16",
]

LANE_RE = re.compile(r"^gc-lane:\s+(.*)$", re.MULTILINE)
WORK_RE = re.compile(r"^gc-work:\s+(.*)$", re.MULTILINE)
PHASES = ("roots", "symbols", "trace", "arena", "sweep")


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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
    require(result.returncode == 0, f"{name} compile red:\n{result.stdout}")
    return binary


def parse_fields(pattern: re.Pattern[str], text: str, label: str) -> dict[str, int]:
    match = pattern.search(text)
    require(match is not None, f"{label} report absent:\n{text}")
    fields: dict[str, int] = {}
    for field in match.group(1).split():
        key, raw = field.split("=", 1)
        fields[key] = int(raw, 10)
    return fields


def run_lane(binary: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env.update({
        "LISP65_EQ_FREEZE_BOOT": "1",
        "LISP65_EQ_REQUIRE_GC": "1",
        "LISP65_EQ_REQUIRE_NO_OOM": "1",
        "LISP65_EQ_GC_LANE_REPORT": "1",
        "LISP65_EQ_GC_WORK_REPORT": "1",
    })
    result = subprocess.run(
        [str(binary), "vm", str(FIXTURE)],
        cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=30)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "lane": parse_fields(LANE_RE, result.stderr, "GC lane"),
        "work": parse_fields(WORK_RE, result.stderr, "GC work"),
    }


def validate_semantics(run: dict[str, Any], dma_model: int) -> None:
    lane = run["lane"]
    require(
        run["returncode"] == 0
        and run["stdout"].rstrip().endswith("=> 600")
        and lane["runs"] == 6
        and lane["marked"] == 32
        and lane["reclaimed"] == 192
        and lane["mem_oom"] == 0
        and lane["dma_model"] == dma_model
        and lane["dma_faults"] == 0,
        f"collector semantics diverged: {run}",
    )


def phase_jobs(work: dict[str, int], phase: str) -> int:
    return work[f"{phase}_dma_reads"] + work[f"{phase}_dma_writes"]


def total_phase_jobs(work: dict[str, int], phase: str) -> int:
    return (
        work[f"{phase}_total_dma_reads"]
        + work[f"{phase}_total_dma_writes"]
    )


def validate_attribution(work: dict[str, int]) -> None:
    require(
        work["shadow_roots"] > 0
        and work["symbol_rows"] > 0
        and work["trace_passes"] > 0
        and work["trace_hot_visits"] > 0
        and work["arena_slots"] == 1071
        and work["sweep_hot_visits"] == 47
        and work["sweep_ext_visits"] > 0,
        f"phase execution witness incomplete: {work}",
    )
    require(
        phase_jobs(work, "sweep") > 0,
        f"modeled EXT sweep work was not attributed: {work}",
    )


def extract_target_authority() -> dict[str, Any]:
    link66 = json.loads(LINK66.read_text())
    link66_gc = link66["measurements"]["gc_envelope_informative"]
    require(
        link66_gc["frames"] == 88
        and link66_gc["collections"] == 1
        and link66_gc["blockreads_per_collection"] == 96,
        "Link 66 GC authority drifted",
    )
    g5 = json.loads(FINAL_G5.read_text())
    g5_rows = {
        row["id"]: row for row in g5["cases"]
        if row.get("id") == "runtime/gc-envelope-informative"
    }
    require(len(g5_rows) == 1, "final G5 GC row absent")
    value = g5_rows["runtime/gc-envelope-informative"]["value_string"]
    require(
        "frames=89" in value and "collections=1" in value
        and "blockreads=96" in value,
        "final G5 GC authority drifted",
    )
    counters = FINAL_G5_COUNTERS.read_text()
    require("nsym=480" in counters, "final G5 symbol-count authority drifted")
    return {
        "Link66": {
            "frames": 88,
            "collections": 1,
            "root_block_reads": 96,
        },
        "final_G5": {
            "frames": 89,
            "collections": 1,
            "root_block_reads": 96,
            "symbols": 480,
        },
    }


def main() -> None:
    product_define_authorities = [
        ROOT / "config/workbench.mk",
        ROOT / "mk/workbench.mk",
    ]
    for authority in product_define_authorities:
        require(
            "LISP65_GC_WORK_ATTRIBUTION_PROBE" not in authority.read_text(),
            f"host-only attribution probe leaked into product flags: {authority}",
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    direct_binary = compile_lane("direct", [])
    dma_binary = compile_lane("checked-dma", ["LISP65_EXT_HEAP_HOST_DMA_MODEL"])
    phase_mutation_binary = compile_lane(
        "phase-collapse-mutation",
        [
            "LISP65_EXT_HEAP_HOST_DMA_MODEL",
            "LISP65_GC_WORK_ATTRIBUTION_PHASE_MUTATION",
        ],
    )

    direct = run_lane(direct_binary)
    dma = run_lane(dma_binary)
    mutation = run_lane(phase_mutation_binary)
    validate_semantics(direct, 0)
    validate_semantics(dma, 1)
    validate_semantics(mutation, 1)
    validate_attribution(dma["work"])

    semantic_fields = (
        "runs", "marked", "reclaimed", "free_before", "free_after",
        "min_free_after", "alloc_high", "frozen", "final_free", "mem_oom",
    )
    require(
        {field: direct["lane"][field] for field in semantic_fields}
        == {field: dma["lane"][field] for field in semantic_fields},
        "direct and checked-DMA lanes disagree",
    )

    mutation_rejected = False
    try:
        validate_attribution(mutation["work"])
    except AttributionError:
        mutation_rejected = True
    require(mutation_rejected, "phase-collapse mutation escaped the work gate")

    target = extract_target_authority()
    work = dma["work"]
    modeled_jobs = {phase: phase_jobs(work, phase) for phase in PHASES}
    modeled_jobs_total = sum(modeled_jobs.values())
    total_modeled_jobs = {
        phase: total_phase_jobs(work, phase) for phase in PHASES
    }
    all_collection_jobs = sum(total_modeled_jobs.values())
    outside_jobs = total_phase_jobs(work, "outside")
    require(
        all_collection_jobs + outside_jobs
        == dma["lane"]["dma_reads"] + dma["lane"]["dma_writes"],
        "cumulative phase buckets do not close against lane DMA total",
    )
    require(outside_jobs > 0, "outside/observer-work separation was not exercised")

    # These are the only target job counts justified by accepted evidence.
    # The host phase shape is reported separately and is not projected into
    # target frames.
    target_lower_bound = {
        "roots": target["final_G5"]["root_block_reads"],
        "symbols": target["final_G5"]["symbols"],
        "trace": None,
        "arena": None,
        "sweep": None,
    }
    proven_lower_bound = (
        target_lower_bound["roots"] + target_lower_bound["symbols"]
    )
    require(proven_lower_bound == 576, "accepted target lower bound drifted")

    dominant_modeled_phase = max(modeled_jobs, key=modeled_jobs.get)
    dominant_share = modeled_jobs[dominant_modeled_phase] / modeled_jobs_total
    proven_dominant_phase = "symbols"
    proven_dominant_share = (
        target_lower_bound[proven_dominant_phase] / proven_lower_bound
    )
    target_dominance = (
        "not-attributable-from-current-authorities"
        if any(target_lower_bound[phase] is None for phase in ("trace", "arena", "sweep"))
        else "attributable"
    )

    receipt = {
        "format": FORMAT,
        "recorded_on": "2026-07-29",
        "status": "passed-host-work-attribution-no-cut-authorized",
        "product_delta_bytes": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "authority": {
            "fixture": bind(FIXTURE),
            "collector": bind(ROOT / "src/mem.c"),
            "collector_header": bind(ROOT / "src/mem.h"),
            "harness": bind(ROOT / "scripts/equivalence-main.c"),
            "driver": bind(Path(__file__)),
            "Link66": bind(LINK66),
            "final_G5": bind(FINAL_G5),
            "final_G5_counters": bind(FINAL_G5_COUNTERS),
            "prior_operation_ledger": bind(PRIOR_LEDGER),
            "product_define_authorities": [
                bind(path) for path in product_define_authorities
            ],
        },
        "execution_witness": {
            "expected_lanes": 3,
            "executed_lanes": 3,
            "lanes": [
                "direct-EXT-reference",
                "checked-copy-EXT-model",
                "phase-collapse-mutation",
            ],
            "collections_per_lane": dma["lane"]["runs"],
            "phase_counters_nonzero": True,
            "phase_collapse_mutation_rejected": mutation_rejected,
            "host_only_define_absent_from_product_build": True,
        },
        "host_lane_last_collection": {
            "semantics": {
                key: dma["lane"][key] for key in semantic_fields
            },
            "work": work,
            "modeled_EXT_jobs_by_phase": modeled_jobs,
            "modeled_EXT_jobs_in_collection": modeled_jobs_total,
            "modeled_EXT_jobs_all_six_collections_by_phase": total_modeled_jobs,
            "modeled_EXT_jobs_all_six_collections": all_collection_jobs,
            "modeled_EXT_jobs_outside_gc_collect": outside_jobs,
            "observer_correction": (
                "The historical aggregate includes six collections plus "
                "free-before/free-after/final freelist walks and ordinary "
                "workload access. Cumulative buckets now close that aggregate; "
                "last-collection buckets reset after its first observer and "
                "close before its later observers."
            ),
            "modeled_job_count_dominant_phase": dominant_modeled_phase,
            "modeled_job_count_dominant_share": dominant_share,
            "shape_note": (
                "This fixture's final collection has no live runtime EXT "
                "trace interval and no arena bytes to copy; its 177 modeled "
                "cell-heap jobs are therefore all dead-EXT sweep writes. "
                "Symbol tables and C2D roots are not resident in the host "
                "lane's modeled EXT array and are bound separately below."
            ),
        },
        "target_binding": {
            "observations": target,
            "proven_DMA_job_lower_bound": {
                "jobs": proven_lower_bound,
                "composition": {
                    "C2D_root_32_byte_reads": 96,
                    "Bank5_symval_2_byte_reads": 480,
                },
                "not_included": [
                    "pointer-valued symfn reads",
                    "C2D-root graph traversal",
                    "EXT fixed-point traversal",
                    "string-arena transfers",
                    "EXT sweep writes",
                    "observer or evaluator work outside gc_collect",
                ],
                "dominant_known_term": {
                    "phase": proven_dominant_phase,
                    "jobs": target_lower_bound[proven_dominant_phase],
                    "share_of_proven_lower_bound": proven_dominant_share,
                    "claim_limit": (
                        "dominant only inside the 576-job proven lower bound, "
                        "not inside the 89-frame envelope"
                    ),
                },
            },
            "target_phase_jobs": target_lower_bound,
            "target_phase_frames": {
                "roots": None,
                "symbols": None,
                "trace": None,
                "arena": None,
                "sweep": None,
                "whole_collection_authority": 89,
            },
        },
        "answer": {
            "host_lane_by_modeled_EXT_job_count": {
                "phase": dominant_modeled_phase,
                "share": dominant_share,
            },
            "target_proven_lower_bound_by_job_count": {
                "phase": proven_dominant_phase,
                "share": proven_dominant_share,
            },
            "89_frame_target_envelope": target_dominance,
            "reason": (
                "The host lane now separates and counts the real collector's "
                "work terms, but it does not reproduce the live target C2D "
                "root graph, symbol EXT tables, or target arena contents. "
                "Accepted hardware evidence provides only the whole 89-frame "
                "endpoint and two phase lower bounds. Assigning frames to a "
                "host-shaped phase would be an invented timing model."
            ),
            "cut_recommendation": (
                "none: no target phase dominates by accepted evidence; retain "
                "the counters as the precondition for any future phase-timed "
                "or product-shaped replay"
            ),
        },
        "claim_limit": (
            "Counts are exact for the final collection of the host fixture and "
            "the checked-copy EXT model. They are not target cycle timings. "
            "Only 88/89 whole-collection frames, 96 C2D root block reads, 480 "
            "symbol-value reads and the resulting >=576-job lower bound are "
            "bound to hardware. Unknown target phase work remains unknown."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(
        "c2-v1.2.2-g2-gc-work-attribution: PASS "
        f"collection_jobs={modeled_jobs_total} "
        f"all_collection_jobs={all_collection_jobs} "
        f"outside_jobs={outside_jobs} "
        f"host_dominant={dominant_modeled_phase}:{dominant_share:.3f} "
        "target_dominant=UNKNOWN cut=none"
    )


if __name__ == "__main__":
    try:
        main()
    except (AttributionError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"c2-v1.2.2-g2-gc-work-attribution: FIRST RED: {exc}")
