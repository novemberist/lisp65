#!/usr/bin/env python3
"""Qualify the parser-free require idempotence path.

The fast path is a one-entry resolution cache, never a loaded-library
authority.  It may answer ``t`` only while the generation/count state, index
lock and complete persistent identity sequence still match the post-publish
state that the slow resolver proved.  Every mismatch must fall back through
the real L65I parser and resolver.

This is a host-only product-shaped probe.  It compiles the Bank-2 Lisp
candidate, executes the real bytecode against the Link-75 C2D/D81 model, and
compares the repeat workload with the accepted Phase-M1 baseline.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402
import c2_phase_m_require_latency as M  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_require_prior_append_option_a_gate as OPTION_A  # noqa: E402


SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
LISP = ROOT / "lib/stdlib-require.lisp"
BUILD = ROOT / "build/post-promotion/phase-m/require-fastpath"
PREFIX = BUILD / "stdlib-p0"
MANIFEST = BUILD / "stdlib-p0.manifest.json"
BASE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-phase-m1-require-latency-measurement-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-idempotence-fastpath-receipt.json"
)
FORMAT = "lisp65-c2.2-require-idempotence-fastpath-v1"
BASELINE_CODE_BYTES = 13835
CURRENT_MEDIA: Path | None = None
CURRENT_MEDIA_BINDING: dict[str, Any] | None = None


class FastpathError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FastpathError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def compile_candidate() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            str(PREFIX.relative_to(ROOT)),
            str(SUITE.relative_to(ROOT)),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(run.returncode == 0, "candidate compile red:\n" + run.stdout)
    new = load(MANIFEST)
    delta = int(new["code_bytes"]) - BASELINE_CODE_BYTES
    require(0 <= delta <= 512, f"Bank-2 delta outside 0..512: {delta}")
    return {
        "baseline_code_bytes": BASELINE_CODE_BYTES,
        "candidate_code_bytes": int(new["code_bytes"]),
        "bank2_delta_bytes": delta,
        "bank2_ceiling_bytes": 512,
        "resident_delta_bytes": 0,
        "compile_stdout": run.stdout.strip().splitlines(),
    }


def prepare_environment() -> dict[str, Any]:
    global CURRENT_MEDIA, CURRENT_MEDIA_BINDING
    source = OPTION_A.run_source_gate()
    fixtures = OPTION_A.prepare_source_fixtures()
    geometry = OPTION_A.current_geometry()
    medium, binding = OPTION_A.build_library_media(geometry["build_id"])
    CURRENT_MEDIA = medium
    CURRENT_MEDIA_BINDING = binding
    return {
        "resolver": source,
        "fixtures": fixtures,
        "media": binding,
        "geometry": geometry,
    }


def environment() -> tuple[
    R.BoundStdlib, R.LivePlane, M.MeasuredResolverVM
]:
    require(CURRENT_MEDIA is not None, "source-built media not prepared")
    R.STDLIB = MANIFEST
    bound = R.BoundStdlib()
    media = CURRENT_MEDIA.read_bytes()
    locators, payloads = R.media_locators(media)
    require(payloads["l65index"][:4] == b"L65I",
            "successor media index identity drift")
    plane = OPTION_A.CurrentLivePlane()
    vm = M.MeasuredResolverVM(bound, plane, media, locators)
    return bound, plane, vm


def run_pair() -> dict[str, Any]:
    bound, plane, vm = environment()
    first = M.execute_lane(vm, bound, plane)
    repeat = M.execute_lane(
        vm, bound, plane, required_phases=("control",)
    )
    require(
        first["result"] == repeat["result"] == "t"
        and first["loader_attempts"] == 2
        and repeat["loader_attempts"] == 0
        and repeat["disk_sector_reads"] == 0
        and not repeat["c2d_and_code_changed"],
        "fast repeat semantic contract drift",
    )
    return {"first": first, "idempotent_repeat": repeat}


def median_exact(samples: list[dict[str, Any]], lane: str) -> dict[str, Any]:
    rows = [sample[lane] for sample in samples]
    for key in (
        "result", "vm_instructions", "prim67_reads", "loader_attempts",
        "disk_sector_reads", "c2d_and_code_changed", "phase_instructions",
    ):
        require(all(row[key] == rows[0][key] for row in rows[1:]),
                f"{lane} semantic sample drift: {key}")
    return {
        "result": rows[0]["result"],
        "vm_instructions": rows[0]["vm_instructions"],
        "prim67_reads": rows[0]["prim67_reads"],
        "loader_attempts": rows[0]["loader_attempts"],
        "disk_sector_reads": rows[0]["disk_sector_reads"],
        "c2d_and_code_changed": rows[0]["c2d_and_code_changed"],
        "phase_instructions": rows[0]["phase_instructions"],
    }


def fallback_case(
    label: str,
    mutate: Callable[[R.BoundStdlib, R.LivePlane], str],
) -> dict[str, Any]:
    bound, plane, vm = environment()
    first = M.execute_lane(vm, bound, plane)
    require(first["result"] == "t", f"{label}: setup require failed")
    expected = mutate(bound, plane)
    lane = M.execute_lane(
        vm,
        bound,
        plane,
        required_phases=("parse", "resolve", "control"),
        library="place" if label == "different-library" else "defstruct",
        expected_result=expected,
    )
    require(
        lane["result"] == expected
        and lane["phase_instructions"]["parse"] > 1000,
        f"{label}: mismatch did not fall back through parser/resolver",
    )
    return {
        "result": lane["result"],
        "vm_instructions": lane["vm_instructions"],
        "prim67_reads": lane["prim67_reads"],
        "parser_instructions": lane["phase_instructions"]["parse"],
        "loader_attempts": lane["loader_attempts"],
    }


def mutation_gate() -> dict[str, Any]:
    def foreign_identity(
        _bound: R.BoundStdlib, plane: R.LivePlane
    ) -> str:
        at = V6.C2D_IMAGES_OFFSET + 6 * V6.C2D_IMAGE_BYTES + 28
        plane.data[at] ^= 1
        # Option A deliberately narrows the old "foreign identity always
        # fails" rule.  Once an identity no longer occurs in L65I, the slow
        # world proof treats that geometrically valid row as an ordinary
        # Session definition.  The cache must still miss and run the full
        # parser/resolver; the already loaded requested package remains true.
        return "t"

    def wrong_generation(
        _bound: R.BoundStdlib, plane: R.LivePlane
    ) -> str:
        plane.data[10] = 2
        return "nil"

    def wrong_lock(bound: R.BoundStdlib, _plane: R.LivePlane) -> str:
        symbol = bound.heap.intern("*require-index-lock*")
        bound.heap.set_symbol_value(
            symbol, bound.heap.list_from_py([B.mkfix(0)])
        )
        return "nil"

    def stale_cache(bound: R.BoundStdlib, _plane: R.LivePlane) -> str:
        symbol = bound.heap.intern("*require-fast*")
        bound.heap.set_symbol_value(symbol, B.NIL)
        return "t"

    def different_library(
        _bound: R.BoundStdlib, _plane: R.LivePlane
    ) -> str:
        return "t"

    cases = {
        "foreign-identity": foreign_identity,
        "wrong-generation": wrong_generation,
        "wrong-index-lock": wrong_lock,
        "stale-cache": stale_cache,
        "different-library": different_library,
    }
    return {
        label: fallback_case(label, mutation)
        for label, mutation in cases.items()
    }


def source_gate() -> dict[str, Any]:
    source = LISP.read_text(encoding="utf-8")
    tokens = (
        "(defun %require-fast-loaded-p (library)",
        "(let ((state (%require-c2d-state-values)))",
        "(defun %require-active-identities-at",
        "(symbol-value '*require-index-lock*)",
        "(set-symbol-value\n                    '*require-fast*",
        "(if (%require-fast-loaded-p library)",
        "(let ((index (%l65i-parse)))",
    )
    guards = (
        "(if (equal state (nth 3 cache))",
        "(%require-active-identities-at\n"
        "                          6 (nth 1 state) (nth 0 state) nil)",
        "(symbol-value '*require-index-lock*)\n"
        "                      (nth 1 cache)",
        "(if (%require-fast-loaded-p library)\n"
        "          t\n"
        "          (let ((index (%l65i-parse)))",
    )

    def validate(candidate: str) -> None:
        require(all(token in candidate for token in tokens),
                "fastpath-source-seam")
        require(all(token in candidate for token in guards),
                "fastpath-proof-guard")
        require("(set-symbol-value '*loaded-libs*" not in candidate,
                "loaded-registry")

    validate(source)
    mutants = {
        "state-check": source.replace(
            "(if (equal state (nth 3 cache))",
            "(if t",
            1,
        ),
        "identity-sequence-check": source.replace(
            "(%require-active-identities-at\n"
            "                          6 (nth 1 state) (nth 0 state) nil)",
            "(nth 4 cache)",
            1,
        ),
        "index-lock-check": source.replace(
            "(symbol-value '*require-index-lock*)\n"
            "                      (nth 1 cache)",
            "(nth 1 cache)\n                      (nth 1 cache)",
            1,
        ),
        "parser-before-fastpath": source.replace(
            "(if (%require-fast-loaded-p library)",
            "(if nil",
            1,
        ),
        "loaded-registry": source + (
            "\n(set-symbol-value '*loaded-libs* "
            "(cons library (symbol-value '*loaded-libs*)))\n"
        ),
    }
    rejected: dict[str, str] = {}
    for label, mutant in mutants.items():
        try:
            validate(mutant)
        except FastpathError as error:
            rejected[label] = str(error)
    require(len(rejected) == len(mutants), "source mutation survived")
    return {
        "tokens": len(tokens),
        "mutations_rejected": rejected,
        "loaded_registry": False,
        "cache_authority": False,
    }


def main() -> int:
    try:
        public_build = (
            os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
        )
        geometry = compile_candidate()
        source_fixture = prepare_environment()
        samples = [run_pair() for _ in range(5)]
        first = median_exact(samples, "first")
        repeat = median_exact(samples, "idempotent_repeat")
        if public_build:
            baseline = None
            step_reduction = None
            read_reduction = None
        else:
            baseline = load(BASE_RECEIPT)["host_measurement"][
                "idempotent_repeat"
            ]
            step_reduction = 1.0 - (
                repeat["vm_instructions"] / baseline["vm_instructions"]
            )
            read_reduction = 1.0 - (
                repeat["prim67_reads"] / baseline["prim67_reads"]
            )
            require(step_reduction >= 0.90,
                    f"VM-step reduction below 90%: {step_reduction:.6f}")
            require(read_reduction >= 0.90,
                    f"Prim-67 reduction below 90%: {read_reduction:.6f}")
        fallbacks = mutation_gate()
        source = source_gate()
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-28",
            "status": (
                "passed-public-current-source-fastpath-semantics"
                if public_build
                else "passed-parser-free-idempotence-fastpath"
            ),
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "sample_count": len(samples),
            "geometry": geometry,
            "baseline_repeat": (
                {
                    "mode":
                        "not-a-public-current-source-build-input",
                    "private_evidence_inputs": 0,
                }
                if baseline is None
                else {
                    "vm_instructions": baseline["vm_instructions"],
                    "prim67_reads": baseline["prim67_reads"],
                }
            ),
            "candidate": {
                "first_require": first,
                "idempotent_repeat": repeat,
                "repeat_reduction": (
                    {
                        "mode": "not-claimed-by-public-build",
                        "private_evidence_inputs": 0,
                    }
                    if step_reduction is None or read_reduction is None
                    else {
                        "vm_steps_percent": round(
                            100 * step_reduction, 4
                        ),
                        "prim67_reads_percent": round(
                            100 * read_reduction, 4
                        ),
                        "required_minimum_percent": 90,
                    }
                ),
            },
            "fallback_mutations": fallbacks,
            "option_A_mutation_narrowing": {
                "foreign-identity": (
                    "still invalidates the cache and executes the full "
                    "parser/resolver, but a geometrically valid non-index row "
                    "is now an ordinary Session definition and the requested "
                    "loaded package returns t"
                )
            },
            "source_gate": source,
            "source_reproducible_fixture": source_fixture,
            "proof_boundary": {
                "fast_checks": [
                    "same library symbol as one-entry resolution cache",
                    "same non-NIL canonical L65I index lock",
                    "same generation and all five published count/front values",
                    "same complete ordered persistent C2D identity sequence",
                ],
                "cache_is_not_authority": (
                    "The cache never marks a library loaded. A hit is accepted "
                    "only after current C2D truth independently matches every "
                    "cached discriminator."
                ),
                "immutable_header_not_reread": (
                    "The slow path proves header shape, caps, layout, static "
                    "prefix, active layout and transient fronts before caching. "
                    "Between serialized top-level operations no legal product "
                    "writer can mutate those immutable fields without changing "
                    "the checked generation/count/front state. The permanent "
                    "source/ELF no-writer proof is required before promotion."
                ),
            },
            "authority": {
                "candidate_manifest": bind(MANIFEST),
                "baseline_code_calibration": (
                    {
                        "bytes": BASELINE_CODE_BYTES,
                        "scope":
                            "stable source-layout calibration; no private "
                            "historical receipt is a public build input",
                        "private_evidence_inputs": 0,
                    }
                    if public_build
                    else {
                        "bytes": BASELINE_CODE_BYTES,
                        "authority": bind(BASE_RECEIPT),
                        "scope":
                            "accepted pre-fastpath Bank-2 resolver "
                            "measurement",
                    }
                ),
                "lisp": bind(LISP),
                "suite": bind(SUITE),
                "driver": bind(Path(__file__).resolve()),
            },
            "claim_limit": (
                "Host VM steps and Prim-67 reads are exact for the compiled "
                "candidate against the source-built current profile/D81 "
                "model. No target timing, "
                "DMA, IRQ, physical GC, product link or hardware claim is made."
            ),
        }
        if not public_build:
            value["authority"]["baseline_measurement"] = bind(BASE_RECEIPT)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        reduction_text = (
            "public-current-source"
            if step_reduction is None or read_reduction is None
            else f"{100*step_reduction:.2f}%/{100*read_reduction:.2f}%"
        )
        print(
            "c2-require-idempotence-fastpath: PASS "
            f"bank2=+{geometry['bank2_delta_bytes']} resident=+0 "
            f"repeat={repeat['vm_instructions']}/{repeat['prim67_reads']} "
            f"reduction={reduction_text} fallbacks={len(fallbacks)}"
        )
        return 0
    except (
        FastpathError, M.MeasurementError, R.ResolverError, B.VMError,
        ValueError,
    ) as error:
        print(
            "c2-require-idempotence-fastpath: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
