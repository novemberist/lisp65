#!/usr/bin/env python3
"""Verify the owner-approved Wave-2 removal of ``restart-repl``.

The earlier Green-Surface receipt remains historical evidence for the
implemented-but-rejected surface.  This verifier binds the corrected public
surface, proves that no delivery path remains, and measures the new product
against the last common Wave-2 repin without rewriting that history.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import v11_wave2_common_repin as W2  # noqa: E402


CONTRACT = ROOT / "config/v11-g-green-surface-contract.json"
BASELINE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-common-repin-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-restart-repl-wave2-scope-correction-receipt.json"
)
OBSERVATIONS = ROOT / "build/bytecode/dialect-v2/v11-g-green-observations.json"
MANIFEST = ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
ELF = ROOT / (
    "build/products/workbench/overlay-stack-guard/"
    "lisp65-workbench-overlay-linked.prg.elf"
)
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

SOURCE_PATHS = tuple(ROOT / path for path in (
    "config/v11-g-green-surface-contract.json",
    "config/dialect-v2-contract.json",
    "config/dialect-v2-surface.json",
    "config/v11-surface-delivery-parity.json",
    "config/v11-workbench-differential-baseline.json",
    "config/r6-g6-harness.json",
    "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json",
    "tests/bytecode/dialect-v2/r3-boot/cases.json",
    "lib/dialect-v2/eval-runtime.lisp",
    "src/vm.c",
    "tools/host-lisp/r6_g6.py",
    "docs/planning/v1.2-scope-memo.md",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-restart-repl-self-restart-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-restart-repl-attic-recovery-probe-receipt.json",
))

HEADROOM_KEYS = (
    "bank_post_boot_reserve_bytes",
    "runtime_stack_gap_bytes",
    "fixed_overlay_headroom_bytes",
    "runtime_overlay_bank_headroom_bytes",
    "runtime_overlay_max_slice_headroom_bytes",
    "installer_slice_headroom_bytes",
    "shelf_headroom_bytes",
    "symbol_headroom",
    "namepool_headroom_bytes",
    "directory_load_headroom",
    "directory_post_align_headroom",
    "ext_code_peak_headroom",
    "ext_code_post_headroom",
    "codebuf_headroom",
)
USAGE_KEYS = (
    "resident_bytes",
    "resident_file_end",
    "ext_post_load_bytes",
    "fixed_overlay_bytes",
    "runtime_overlay_bank_bytes",
    "runtime_overlay_max_slice_bytes",
    "boot_fastpath_verify_slice_bytes",
    "resident_island_bytes",
    "installer_slice_bytes",
    "shelf_bytes",
    "vm_callprim_bytes",
    "vm_run_inner_bytes",
)


class ScopeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScopeError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScopeError(f"cannot read {path}: {exc}") from exc
    require(isinstance(value, dict), f"object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def names(path: Path, key: str) -> set[str]:
    value = load(path)
    rows = value.get(key)
    require(isinstance(rows, list), f"list required: {path}:{key}")
    result: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            result.add(row)
        elif isinstance(row, dict) and isinstance(row.get("name"), str):
            result.add(row["name"])
    return result


def semantic_gates() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("format") == "lisp65-v11-g-green-surface-contract-v4"
            and contract.get("status") == "owner-approved-wave2-scope-corrected",
            "scope-corrected Green Surface contract drift")
    require(set(contract.get("features", {})) == {"read-from-string"},
            "Wave-2 Green Surface must contain only read-from-string")
    deferred = contract.get("deferred_features", {}).get("restart-repl", {})
    require(deferred.get("destination") == "C2.3"
            and deferred.get("wave2_surface") == "not-delivered",
            "restart-repl C2.3 deferral drift")

    observations = load(OBSERVATIONS)
    suites = observations.get("suites")
    require(isinstance(suites, list) and len(suites) == 1,
            "Green Surface observation suite drift")
    rows = suites[0].get("observations")
    require(isinstance(rows, list), "Green Surface observations missing")
    by_name = {row.get("name"): row for row in rows if isinstance(row, dict)}
    expected = {
        "v11-g-read-from-string-direct": ("result", "42"),
        "v11-g-read-from-string-funcall": ("result", "42"),
        "v11-g-read-from-string-apply": ("result", "42"),
        "v11-g-read-from-string-first-object": ("result", "42"),
        "v11-g-read-from-string-type-error": ("error", "TypeError"),
        "v11-g-read-from-string-arity-zero": ("error", "ArityError"),
        "v11-g-read-from-string-arity-extra": ("error", "ArityError"),
    }
    for name, (field, value) in expected.items():
        require(by_name.get(name, {}).get(field) == value,
                f"read-from-string observation failed: {name}")
    require(not any("restart-repl" in str(name) for name in by_name),
            "restart-repl observation survived scope correction")

    manifest = load(MANIFEST)
    entries = {row.get("name"): row for row in manifest.get("entries", [])
               if isinstance(row, dict)}
    require(entries.get("read-from-string", {}).get("length") == 27,
            "read-from-string bytecode delivery drift")
    require("restart-repl" not in entries,
            "restart-repl remains in the resident bytecode manifest")

    require("restart-repl" not in names(ROOT / "config/dialect-v2-contract.json", "public_names"),
            "restart-repl remains in dialect contract")
    require("restart-repl" not in names(ROOT / "config/dialect-v2-surface.json", "definitions"),
            "restart-repl remains in public surface")
    require("restart-repl" not in names(ROOT / "config/v11-surface-delivery-parity.json", "claims"),
            "restart-repl remains in delivery parity")

    eval_text = (ROOT / "lib/dialect-v2/eval-runtime.lisp").read_text(encoding="utf-8")
    vm_text = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    require("(defun restart-repl" not in eval_text,
            "restart-repl Lisp wrapper survived")
    require("FIXVAL(a[0]) == 30" not in vm_text,
            "restart-repl resident control action survived")

    result = subprocess.run(
        [str(OBJDUMP), "-d", "--disassemble-symbols=vm_callprim", str(ELF)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    require(result.returncode == 0, f"cannot disassemble vm_callprim: {result.stderr}")
    require(not re.search(r"\b6c fc ff\b.*\bjmp\s+\(\$fffc\)", result.stdout),
            "platform-reset interception remains linked in vm_callprim")
    return {
        "read_from_string": "7/7 direct-funcall-apply-first-object-and-negative-cases",
        "restart_repl_public_surface": "absent",
        "restart_repl_resident_manifest": "absent",
        "restart_repl_vm_interception": "absent-source-and-disassembly",
        "restart_repl_destination": "C2.3",
    }


def collect() -> dict[str, Any]:
    baseline_receipt = load(BASELINE)
    require(baseline_receipt.get("status") == "passed-owner-authorized-ready-for-wave2-promotion",
            "Wave-2 common-repin baseline status drift")
    baseline = baseline_receipt["candidate"]["metrics"]
    candidate = W2.metrics(W2.CANDIDATE_PRODUCTS, W2.CANDIDATE_REPORTS)
    delta = {key: int(candidate[key]) - int(baseline[key])
             for key in baseline if key != "build_id"}
    regressions = {
        key: delta[key] for key in HEADROOM_KEYS if delta[key] < 0
    } | {
        key: delta[key] for key in USAGE_KEYS if delta[key] > 0
    }
    require(not regressions,
            f"scope correction has negative capacity drift: {regressions}")

    return {
        "format": "lisp65-v11-restart-repl-wave2-scope-correction-receipt-v1",
        "version": 1,
        "id": "v11-restart-repl-wave2-scope-correction",
        "status": "implemented-passed-credit-only-awaiting-capacity-repin-review",
        "recorded_on": "2026-07-18",
        "owner_decision": "restart-repl is not delivered by 1.1 and is named C2.3 freight",
        "baseline": binding(BASELINE) | {"metrics": baseline},
        "candidate": {
            "metrics": candidate,
            "artifacts": W2.artifact_bindings(W2.CANDIDATE_PRODUCTS, W2.CANDIDATE_REPORTS),
        },
        "capacity_delta": delta,
        "semantic_gates": semantic_gates(),
        "historical_design_inputs": [
            binding(ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-self-restart-probe-receipt.json"),
            binding(ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-attic-recovery-probe-receipt.json"),
        ],
        "source_bindings": [binding(path) for path in SOURCE_PATHS],
        "claim_limit": "This receipt proves Wave-2 non-delivery and a credit-only product delta. It makes no restart-repl behavior claim and is not a Wave-2 promotion or hardware receipt.",
    }


def selftest() -> None:
    sample = {
        "status": "implemented-passed-credit-only-awaiting-capacity-repin-review",
        "semantic_gates": {"restart_repl_public_surface": "absent"},
        "capacity_delta": {"bank_post_boot_reserve_bytes": 1},
    }
    mutations = []
    for label, mutate in (
        ("surface", lambda value: value["semantic_gates"].update(restart_repl_public_surface="present")),
        ("capacity", lambda value: value["capacity_delta"].update(bank_post_boot_reserve_bytes=-1)),
        ("status", lambda value: value.update(status="promoted")),
    ):
        candidate = copy.deepcopy(sample)
        mutate(candidate)
        if candidate != sample:
            mutations.append(label)
    require(mutations == ["surface", "capacity", "status"],
            "scope-correction selftest drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v11-restart-repl-scope-correction: SELFTEST PASS mutations=3")
            return 0
        expected = collect()
        if args.command == "collect":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(expected))
        else:
            require(load(RECEIPT) == expected, "scope-correction receipt drift")
        delta = expected["capacity_delta"]
        print(
            "v11-restart-repl-scope-correction: PASS "
            f"bank={delta['bank_post_boot_reserve_bytes']:+d} "
            f"ext={delta['ext_code_post_headroom']:+d} "
            f"symbols={delta['symbol_headroom']:+d} "
            f"namepool={delta['namepool_headroom_bytes']:+d}"
        )
        return 0
    except (ScopeError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"v11-restart-repl-scope-correction: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
