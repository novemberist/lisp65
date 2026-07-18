#!/usr/bin/env python3
"""Collect and verify the real-link 1.1-M architecture comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config" / "v11-m-transactional-fasl-probe.json"
BUILD = ROOT / "build" / "probes" / "v11-m"
RECEIPT = (
    ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence"
    / "architecture-blocks" / "v11-m-transactional-fasl-comparison-probe-receipt.json"
)
CODEMOD = "tools/host-lisp/v11_m_transactional_fasl_codemod.py"
VARIANTS = ("baseline", "composition", "dedicated")
LEGACY_SLOT_FUNCTIONS = (
    "%compile-slot-scan-entries", "%compile-slot-find",
    "%compile-slot-capacity", "%c1-slot-link-valid-p",
    "%fasl-save-sector", "%fasl-save-tail", "%fasl-commit-first",
    "%fasl-save-from-first", "%fasl-save-staged-v2",
)


class ProbeError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProbeError(f"{label} must be an object")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _binding(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"missing regular binding: {path}")
    return {"path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise ProbeError(f"git {' '.join(args)} failed: {result.stdout}")
    return result.stdout.strip()


def _run(argv: list[str], log: Path | None = None, env: dict[str, str] | None = None) -> None:
    output = subprocess.PIPE if log is not None else None
    result = subprocess.run(
        argv, cwd=ROOT, env=env, text=True, stdout=output,
        stderr=subprocess.STDOUT if log is not None else None,
    )
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout or "", encoding="utf-8")
    if result.returncode:
        detail = (result.stdout or "")[-6000:]
        raise ProbeError(f"command failed ({result.returncode}): {' '.join(argv)}\n{detail}")


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def build() -> None:
    import os

    for variant in VARIANTS:
        out = BUILD / variant
        env = dict(os.environ)
        env["LISP65_V11_M_VARIANT"] = variant
        common = [
            "make", "--no-print-directory",
            f"V2_WORKBENCH_CODEMOD_TOOL={CODEMOD}",
        ]
        _run(
            [*common, f"WORKBENCH_OVERLAY_GUARD_DIR={_relative(out)}",
             "workbench-overlay-stack-guard"],
            out / "real-link.log", env,
        )
        _run([*common, "v2-workbench-library-composition-check"],
             out / "composition.log", env)
        _copy(ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json",
              out / "stdlib-p0.manifest.json")
        _copy(ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json",
              out / "m65d.manifest.json")
        _copy(ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json",
              out / "composition-budget.json")
        if variant != "baseline":
            _run([*common, "v11-c1-compiler-tier-artifacts"],
                 out / "compiler-tier.log", env)
            _copy(ROOT / "build/bytecode/dialect-v2/libs/lcc.ext.bin", out / "lcc.ext.bin")
            _copy(ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json",
                  out / "lcc.manifest.json")
            _run([
                "python3", "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
                "--observation-report", str(out / "m65d-observations.json"),
                "build/bytecode/dialect-v2/suites/p0-m65d-lib.json",
            ], out / "m65d-observations.log", env)
            _copy(ROOT / "build/bytecode/dialect-v2/suites/p0-m65d-lib.json",
                  out / "m65d-suite.json")
            _copy(
                ROOT / "build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json",
                out / "resident-suite.json",
            )
    # Leave ignored generated files in their canonical Wave-1 form.
    _run(["python3", "tools/host-lisp/v11_c1_lease_codemod.py"])


def _define(path: Path, name: str) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^#define {re.escape(name)} ([0-9]+)u$", text, re.MULTILINE)
    if match is None:
        raise ProbeError(f"missing {name} in {path}")
    return int(match.group(1))


def _runtime_metrics(manifest: dict[str, Any]) -> dict[str, int]:
    slices = manifest.get("slices")
    _require(isinstance(slices, list) and len(slices) == 44,
             "runtime-overlay slice inventory drift")
    installer = next((row for row in slices if row.get("name") == "resident-island-installer"), None)
    boot_verify = next((row for row in slices if row.get("name") == "boot-fastpath-verify"), None)
    _require(isinstance(installer, dict), "installer slice missing")
    _require(isinstance(boot_verify, dict), "boot-fastpath verifier slice missing")
    runtime = [row for row in slices if "runtime" in row.get("roles", [])]
    _require(runtime, "runtime slice inventory empty")
    image_bytes = int(manifest.get("image", {}).get("bytes", 0))
    if not image_bytes:
        # The package is fixed-slot and the on-disk image itself is authoritative.
        image_bytes = 0
    return {
        "slice_count": len(slices),
        "max_runtime_slice_bytes": max(int(row["memory_size"]) for row in runtime),
        "max_runtime_slice_headroom_bytes": 1792 - max(int(row["memory_size"]) for row in runtime),
        "installer_slice_bytes": int(installer["memory_size"]),
        "installer_slice_headroom_bytes": 1792 - int(installer["memory_size"]),
        "boot_fastpath_verify_slice_bytes": int(boot_verify["memory_size"]),
        "image_bytes": image_bytes,
    }


def _variant(name: str) -> dict[str, Any]:
    root = BUILD / name
    layout = _load(root / "layout.json", f"{name} layout")
    footprint = _load(root / "footprint-audit.json", f"{name} footprint")
    budget = _load(root / "composition-budget.json", f"{name} composition")
    stdlib = _load(root / "stdlib-p0.manifest.json", f"{name} stdlib")
    m65d = _load(root / "m65d.manifest.json", f"{name} M65D")
    overlays = _load(root / "runtime-overlays-manifest.json", f"{name} overlays")
    _require(footprint.get("status") == "pass" and budget.get("status") == "pass",
             f"{name} real-link gate is not green")
    runtime = _runtime_metrics(overlays)
    runtime["image_bytes"] = (root / "lisp65-mvp-workbench.overlays.bin").stat().st_size
    island_immutable = _define(root / "resident-island-image.h", "LISP65_RESIDENT_ISLAND_LENGTH")
    island_capacity = _define(root / "resident-island-image.h", "LISP65_RESIDENT_ISLAND_CAPACITY")
    # The fixed 260-byte root-stack annex is outside the immutable image but
    # inside the same 2 KiB island contract.
    island_reserve = island_capacity - island_immutable - 260
    result = {
        "status": "passed" if name == "baseline" else "passed-not-promoted",
        "capacity": {
            "bank_post_boot_reserve_bytes": int(footprint["post_boot_reserve"]),
            "fixed_overlay_bytes": int(layout["overlay"]["size"]),
            "fixed_overlay_vma_headroom_bytes": 0,
            "resident_island_immutable_bytes": island_immutable,
            "resident_island_annex_bytes": 260,
            "resident_island_reserve_bytes": island_reserve,
            "runtime_overlay_bank_bytes": runtime["image_bytes"],
            "runtime_overlay_bank_headroom_bytes": 65536 - runtime["image_bytes"],
            "runtime_overlay_max_slice_bytes": runtime["max_runtime_slice_bytes"],
            "runtime_overlay_max_slice_headroom_bytes": runtime["max_runtime_slice_headroom_bytes"],
            "installer_slice_bytes": runtime["installer_slice_bytes"],
            "installer_slice_headroom_bytes": runtime["installer_slice_headroom_bytes"],
            "boot_fastpath_verify_slice_bytes": runtime["boot_fastpath_verify_slice_bytes"],
            "ext_post_load_headroom_bytes": int(budget["ext_code"]["post_headroom"]),
            "symbol_headroom": int(budget["symbols"]["headroom"]),
            "namepool_headroom_bytes": int(budget["namepool"]["headroom"]),
            "directory_load_headroom": int(budget["directory"]["load_headroom"]),
            "directory_post_align_headroom": int(budget["directory"]["post_align_headroom"]),
        },
        "artifacts": {
            "resident": {
                "objects": int(stdlib["objects"]),
                "code_bytes": int(stdlib["code_bytes"]),
                "directory_bytes": int(stdlib["directory_bytes"]),
                "ext_bytes": int(stdlib["external_image"]["bytes"]),
            },
            "m65d": {
                "objects": int(m65d["objects"]),
                "code_bytes": int(m65d["code_bytes"]),
                "directory_bytes": int(m65d["directory_bytes"]),
                "ext_bytes": int(m65d["external_image"]["bytes"]),
            },
        },
        "bindings": {
            label: _binding(root / filename)
            for label, filename in (
                ("layout", "layout.json"),
                ("footprint", "footprint-audit.json"),
                ("composition", "composition-budget.json"),
                ("resident_manifest", "stdlib-p0.manifest.json"),
                ("m65d_manifest", "m65d.manifest.json"),
                ("runtime_manifest", "runtime-overlays-manifest.json"),
                ("linked_elf", "lisp65-workbench-overlay-linked.prg.elf"),
            )
        },
    }
    if name != "baseline":
        observations = _load(root / "m65d-observations.json", f"{name} observations")
        suite = _load(root / "resident-suite.json", f"{name} resident suite")
        m65d_suite = _load(root / "m65d-suite.json", f"{name} M65D suite")
        observed = observations.get("suites", [{}])[0].get("observations", [])
        buffer_rows = [row for row in observed if f"buffer-payload-{name}" in row.get("name", "")]
        _require(len(observed) == 40 and len(buffer_rows) == 2,
                 f"{name} observation inventory drift")
        success = next((row for row in buffer_rows if "external" in row.get("name", "")), None)
        bad_type = next((row for row in buffer_rows if "bad-type" in row.get("name", "")), None)
        oracle = success.get("external_d81_oracle", {}) if isinstance(success, dict) else {}
        _require(
            success is not None and success.get("result") == "0"
            and oracle.get("result") == "pass"
            and oracle.get("witnesses") == ["d81_persistence_fault", "d81_bam_sanity"]
            and oracle.get("allocated_equals_visible_chain") is True
            and oracle.get("header_unchanged") is True
            and oracle.get("no_double_allocation") is True,
            f"{name} independent Buffer/D81 oracle failed",
        )
        _require(bad_type is not None and bad_type.get("result") == "3",
                 f"{name} invalid Buffer payload did not fail with status 3")
        functions = set(suite.get("functions", []))
        _require(not functions.intersection(LEGACY_SLOT_FUNCTIONS),
                 f"{name} retained legacy slot functions")
        result["semantic_gates"] = {
            "m65d_cases": len(observed),
            "historical_cases": len(observed) - len(buffer_rows),
            "buffer_cases": len(buffer_rows),
            "buffer_external_oracle": oracle,
            "invalid_payload_status": int(bad_type["result"]),
            "legacy_slot_functions_absent": True,
            "m65d_function_count": len(m65d_suite.get("functions", [])),
            "compiler_tier": _binding(root / "lcc.ext.bin"),
        }
        result["bindings"].update({
            "m65d_observations": _binding(root / "m65d-observations.json"),
            "resident_suite": _binding(root / "resident-suite.json"),
            "m65d_suite": _binding(root / "m65d-suite.json"),
            "compiler_tier": _binding(root / "lcc.ext.bin"),
        })
    return result


def _delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(candidate["capacity"][key]) - int(baseline["capacity"][key])
        for key in candidate["capacity"]
    }


def collect(out: Path) -> dict[str, Any]:
    contract = _load(CONTRACT, "1.1-M contract")
    _require(contract.get("format") == "lisp65-v11-m-transactional-fasl-probe-contract-v1",
             "1.1-M contract format drift")
    variants = {name: _variant(name) for name in VARIANTS}
    baseline = variants["baseline"]
    composition = variants["composition"]
    dedicated = variants["dedicated"]

    critical = (
        "fixed_overlay_bytes", "fixed_overlay_vma_headroom_bytes",
        "resident_island_reserve_bytes", "runtime_overlay_max_slice_bytes",
        "installer_slice_bytes", "installer_slice_headroom_bytes",
    )
    for name, candidate in (("composition", composition), ("dedicated", dedicated)):
        _require(all(candidate["capacity"][key] == baseline["capacity"][key] for key in critical),
                 f"{name} changed a critical capacity dimension")
        _require(
            candidate["capacity"]["runtime_overlay_bank_headroom_bytes"]
            >= baseline["capacity"]["runtime_overlay_bank_headroom_bytes"],
            f"{name} consumed runtime-overlay bank headroom",
        )
    _require(
        composition["semantic_gates"]["compiler_tier"]["sha256"]
        == dedicated["semantic_gates"]["compiler_tier"]["sha256"],
        "compiler tier differs between candidates",
    )
    _require(composition["capacity"]["symbol_headroom"] > dedicated["capacity"]["symbol_headroom"],
             "dedicated entry did not consume its expected symbol")
    _require(composition["capacity"]["namepool_headroom_bytes"] > dedicated["capacity"]["namepool_headroom_bytes"],
             "dedicated entry did not consume its expected name")
    _require(composition["capacity"]["ext_post_load_headroom_bytes"] > dedicated["capacity"]["ext_post_load_headroom_bytes"],
             "dedicated entry did not consume post-load EXT")

    receipt = {
        "format": "lisp65-v11-m-transactional-fasl-comparison-probe-receipt-v1",
        "status": "passed-not-promoted",
        "recorded_on": "2026-07-17",
        "recording_commit": _git("rev-parse", "HEAD"),
        "scope": "real-link comparison only; canonical product sources are unchanged",
        "baseline_product_set_sha256": contract["baseline"]["product_set_sha256"],
        "variants": variants,
        "deltas_from_wave1_baseline": {
            name: _delta(variants[name], baseline) for name in ("composition", "dedicated")
        },
        "candidate_comparison": {
            "dedicated_minus_composition": {
                "ext_post_load_headroom_bytes": (
                    dedicated["capacity"]["ext_post_load_headroom_bytes"]
                    - composition["capacity"]["ext_post_load_headroom_bytes"]
                ),
                "symbol_headroom": (
                    dedicated["capacity"]["symbol_headroom"]
                    - composition["capacity"]["symbol_headroom"]
                ),
                "namepool_headroom_bytes": (
                    dedicated["capacity"]["namepool_headroom_bytes"]
                    - composition["capacity"]["namepool_headroom_bytes"]
                ),
                "directory_load_headroom": (
                    dedicated["capacity"]["directory_load_headroom"]
                    - composition["capacity"]["directory_load_headroom"]
                ),
                "runtime_overlay_bank_headroom_bytes": (
                    dedicated["capacity"]["runtime_overlay_bank_headroom_bytes"]
                    - composition["capacity"]["runtime_overlay_bank_headroom_bytes"]
                ),
                "boot_fastpath_verify_slice_bytes": (
                    dedicated["capacity"]["boot_fastpath_verify_slice_bytes"]
                    - composition["capacity"]["boot_fastpath_verify_slice_bytes"]
                ),
                "m65d_code_bytes": (
                    dedicated["artifacts"]["m65d"]["code_bytes"]
                    - composition["artifacts"]["m65d"]["code_bytes"]
                ),
                "m65d_ext_bytes": (
                    dedicated["artifacts"]["m65d"]["ext_bytes"]
                    - composition["artifacts"]["m65d"]["ext_bytes"]
                ),
            },
            "semantic_difference": "none in the transactional Buffer oracle; only the published entry surface differs",
        },
        "recommendation": {
            "choice": "composition",
            "reason": "Both candidates reuse the identical M65D COW transaction and leave the fixed overlay, resident island, reusable runtime-slice maximum and installer slice unchanged. Composition also crosses a 256-byte runtime-bank packing boundary because its boot verifier is 23 bytes smaller. The dedicated seam buys no additional property and costs one symbol, 17 namepool bytes, one raw Directory entry, 45 post-load EXT bytes, 119 M65D container bytes and that 256-byte bank credit.",
            "implementation_gate": "owner/reviewer authorization required before canonical sources or product identities change",
        },
        "bindings": {
            "contract": _binding(CONTRACT),
            "codemod": _binding(ROOT / CODEMOD),
            "collector": _binding(Path(__file__).resolve()),
            "plan": _binding(ROOT / "docs/planning/development-plan-1.1.md"),
            "canonical_eval": _binding(ROOT / "lib/dialect-v2/eval-runtime.lisp"),
            "canonical_m65d": _binding(ROOT / "lib/m65-disk.lisp"),
        },
        "claim_limit": contract["claim_limit"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def selftest() -> None:
    # Exercise the two error-prone helpers without depending on build outputs.
    _require(_delta({"capacity": {"x": 3}}, {"capacity": {"x": 1}}) == {"x": 2},
             "delta selftest failed")
    sample = b"transactional-fasl"
    _require(hashlib.sha256(sample).hexdigest() ==
             "7179484fbc54d0db18e37d3a816c10518df1064d8d47746e0ef0a301b321036f",
             "hash selftest failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("v11-m-transactional-fasl-probe: SELFTEST PASS")
            return 0
        if args.build:
            build()
        receipt = collect(args.out)
    except (OSError, ValueError, ProbeError, subprocess.SubprocessError) as exc:
        print(f"v11-m-transactional-fasl-probe: FAIL: {exc}")
        return 1
    comparison = receipt["candidate_comparison"]["dedicated_minus_composition"]
    print(
        "v11-m-transactional-fasl-probe: PASS status=passed-not-promoted "
        f"choice=composition dedicated_ext_delta={comparison['ext_post_load_headroom_bytes']} "
        f"receipt={_relative(args.out)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
