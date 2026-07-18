#!/usr/bin/env python3
"""Build and verify the Wave-1 C1 first-form correction probe receipt."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave1-c1-first-form-correction-probe.json"
)
BASELINE_ARCHIVE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/promotions/"
    "r4-product-candidate-a870bd0.tar.gz"
)
COMPOSITION = ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
PLAN = ROOT / "build/hw/wave1-c1-plan-after-first.bin"
FIRST_COUNT = ROOT / "build/hw/wave1-c1-symbol-count-after-first.bin"
FIRST_NAMEPOOL = ROOT / "build/hw/wave1-c1-namepool-after-first.bin"
SECOND_COUNT = ROOT / "build/hw/wave1-c1-symbol-count-after-second.bin"
SECOND_NAMEPOOL = ROOT / "build/hw/wave1-c1-namepool-after-second.bin"
FINAL_COUNT = ROOT / "build/hw/wave1-c1-symbol-count-after-composition.bin"
FINAL_NAMEPOOL = ROOT / "build/hw/wave1-c1-namepool-after-composition.bin"
FIRST_SCREEN = ROOT / "build/hw/wave1-c1-accounted-first-form.txt"
RESIDENT = ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg"
OVERLAY = ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay.bin"
LAYOUT = ROOT / "build/products/workbench/overlay-stack-guard/layout.json"
FOOTPRINT = ROOT / "build/products/workbench/overlay-stack-guard/footprint-audit.json"


class ProbeError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeError(f"object expected: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def u16(path: Path) -> int:
    data = path.read_bytes()
    require(len(data) == 2, f"u16 hardware scalar has wrong size: {path}")
    return struct.unpack("<H", data)[0]


def plan_values(path: Path) -> dict[str, int]:
    data = path.read_bytes()
    require(len(data) >= 59, "C1 hardware plan is truncated")
    names = [
        "source_length", "source_crc16", "source_blob_off",
        "source_metadata_off", "code_base", "blob_len", "metadata_len",
        "entry_count", "index_count", "node_count", "patch_count",
        "entries_off", "index_off", "nodes_off", "patches_off",
        "strings_off", "strings_bytes", "dir_before", "dir_after",
        "symbols_before", "namepool_before", "heap_free_before",
        "arena_used_before", "roots_before", "new_symbols",
        "new_name_bytes", "heap_cells", "arena_bytes",
    ]
    values = dict(zip(names, struct.unpack_from("<28H", data)))
    values.update(
        root_slots=data[56], max_graph_depth=data[57], format_version=data[58]
    )
    return values


def baseline_manifest() -> dict[str, Any]:
    with tarfile.open(BASELINE_ARCHIVE, "r:gz") as archive:
        member = archive.extractfile("manifest.json")
        require(member is not None, "R4 baseline archive lacks manifest.json")
        value = json.loads(member.read())
    require(isinstance(value, dict), "R4 baseline manifest is not an object")
    return value


def baseline_file(manifest: dict[str, Any], path: str) -> dict[str, Any]:
    rows = [row for row in manifest.get("files", []) if row.get("path") == path]
    require(len(rows) == 1, f"R4 baseline file binding is not unique: {path}")
    return rows[0]


def source_contracts() -> dict[str, Any]:
    c1 = (ROOT / "src/c1_compiler_overlay.c").read_text(encoding="utf-8")
    mem = (ROOT / "src/mem.h").read_text(encoding="utf-8")
    attic = (ROOT / "src/attic_library_shelf.c").read_text(encoding="utf-8")
    symbol = (ROOT / "src/symbol.h").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts/hw-workbench-overlay-stack-smoke.sh").read_text(
        encoding="utf-8"
    )
    require("plan->new_symbols == 0u" not in c1, "C1 still requires zero symbols")
    require(
        "plan->symbols_before + plan->new_symbols" in c1
        and "plan->namepool_before + plan->new_name_bytes" in c1,
        "C1 validation does not account for committed internings",
    )
    require(
        "#define LISP65_SYMBOL_NAME_MAX 33u" in symbol,
        "canonical symbol-name limit is not 33 bytes",
    )
    require(
        "LISP65_EXT_DISK_FILE_PHYSICAL" in mem
        and "LISP65_EXT_DISK_FILE_PHYSICAL" in attic
        and "0x00046d00" not in attic.lower(),
        "Attic shelf does not share the canonical disk scratch binding",
    )
    require(
        "run_phase c1-first-form" in smoke,
        "hardware smoke does not assert the first C1-backed form",
    )
    return {
        path: sha(ROOT / path)
        for path in (
            "config/workbench.mk", "mk/workbench-service-inventory.mk",
            "mk/workbench.mk",
            "src/c1_compiler_overlay.c", "src/l65m_validate.c", "src/mem.h",
            "src/attic_library_shelf.c", "src/symbol.h",
            "scripts/hw-workbench-overlay-stack-smoke.sh",
            "scripts/v11-c1-compiler-lifetime-main.c",
            "tools/host-lisp/mvp_vm_stdlib_boot_budget.py",
            "tools/host-lisp/workbench_disklib_budget.py",
            "tools/host-lisp/v11_wave1_c1_first_form.py",
        )
    }


def run_gate(*argv: str) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"gate failed: {' '.join(argv)}\n{result.stdout}")
    return result.stdout.strip()


def build_report() -> dict[str, Any]:
    run_gate("make", "--no-print-directory", "v11-c1-compiler-lifetime-check")
    run_gate("python3", "tools/host-lisp/workbench_disklib_budget.py", "--selftest")
    parity = run_gate("python3", "tools/host-lisp/v11_surface_delivery_parity.py")
    run_gate("sh", "-n", "scripts/hw-workbench-overlay-stack-smoke.sh")

    composition = load(COMPOSITION)
    symbols = composition["symbols"]
    namepool = composition["namepool"]
    require(
        symbols == {
            "boot_namepool_calibration": 303,
            "boot_symbol_calibration": 9,
            "disk_new_symbols": 128,
            "disk_symbols": 158,
            "headroom": 297,
            "namepool_bytes": 5614,
            "native_symbols": 44,
            "resident_symbols": 223,
            "retained_namepool_bytes": 432,
            "retained_symbols": 54,
            "static_namepool_bytes": 4879,
            "static_symbols": 392,
            "symbols": 455,
        },
        "composition symbol accounting drift",
    )
    require(
        namepool["used"] == 5614 and namepool["headroom"] == 4594,
        "composition namepool accounting drift",
    )

    plan = plan_values(PLAN)
    require(
        plan["symbols_before"] == 273
        and plan["namepool_before"] == 3103
        and plan["new_symbols"] == 53
        and plan["new_name_bytes"] == 418,
        "hardware C1 plan accounting drift",
    )
    first = {"symbols": u16(FIRST_COUNT), "namepool_bytes": u16(FIRST_NAMEPOOL)}
    second = {"symbols": u16(SECOND_COUNT), "namepool_bytes": u16(SECOND_NAMEPOOL)}
    final = {"symbols": u16(FINAL_COUNT), "namepool_bytes": u16(FINAL_NAMEPOOL)}
    require(first == {"symbols": 327, "namepool_bytes": 3535}, "first-form census drift")
    require(second == first, "C1 repeat leaks symbols or namepool bytes")
    require(final == {"symbols": 455, "namepool_bytes": 5614}, "composition census drift")
    require(
        re.search(r"^\s*42\s*$", FIRST_SCREEN.read_text(encoding="utf-8"), re.M)
        is not None,
        "first cold C1 form did not return 42",
    )

    base = baseline_manifest()
    base_comp = baseline_file(
        base, "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
    )
    base_prg = baseline_file(
        base, "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg"
    )
    base_overlay = baseline_file(
        base, "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay.bin"
    )
    require(base_comp["sha256"] == "2a0e12104b40eba62751c668e7987caa8d91b3675ed14d4db63183d62ba35333",
            "R4 composition baseline drift")
    require(base_prg["bytes"] == RESIDENT.stat().st_size == 39490,
            "resident PRG size delta is not zero")
    require(base_prg["sha256"] != sha(RESIDENT), "C1 correction did not change product SHA")
    require(base_overlay["sha256"] == sha(OVERLAY), "boot overlay changed")

    layout = load(LAYOUT)
    footprint = load(FOOTPRINT)
    require(
        int(layout["overlay"]["base"]) == 0xC306
        and int(layout["overlay"]["size"]) == 1669,
        "overlay capacity drift",
    )
    require(int(footprint["post_boot_reserve"]) == 1873, "Bank reserve drift")

    return {
        "format": "lisp65-v11-wave1-c1-first-form-correction-probe-v1",
        "version": 1,
        "status": "passed-not-promoted-owner-capacity-review-required",
        "baseline": {
            "r4_archive": BASELINE_ARCHIVE.relative_to(ROOT).as_posix(),
            "r4_archive_sha256": sha(BASELINE_ARCHIVE),
            "product_artifact_set_sha256": "91fcad2d6c42abc30a27f4bc2a9cfa65a8bbd85ec74d4a57bd1898ace1314c67",
            "composition_report_sha256": base_comp["sha256"],
            "resident_prg_sha256": base_prg["sha256"],
            "overlay_sha256": base_overlay["sha256"],
        },
        "findings": [
            {
                "id": "attic-shelf-disk-scratch-binding",
                "cause": "a stale private physical address bypassed the profile DISK_EXT_BASE",
                "closure": "all disk-file consumers use LISP65_EXT_DISK_FILE_PHYSICAL",
            },
            {
                "id": "l65m-symbol-name-boundary",
                "cause": "the L65M validator rejected the legal 33-byte native service name %lcc-error-invalid-parameter-list",
                "closure": "one 33-byte symbol contract plus generator 33/34 boundary cases",
            },
            {
                "id": "c1-first-form-warmup-mask",
                "cause": "C1 validation required zero new symbols/name bytes although the exact preflight planned 53/418; rollback retained internings, so only the retry passed",
                "closure": "validate the preflight deltas and assert the first hardware form as a separate phase",
            },
        ],
        "hardware": {
            "plan": {
                "path": PLAN.relative_to(ROOT).as_posix(), "sha256": sha(PLAN),
                "symbols_before": 273, "namepool_before": 3103,
                "new_symbols": 53, "new_name_bytes": 418,
            },
            "after_first_form": {
                **first, "screen": FIRST_SCREEN.relative_to(ROOT).as_posix(),
                "screen_sha256": sha(FIRST_SCREEN), "result": 42,
                "symbol_count_path": FIRST_COUNT.relative_to(ROOT).as_posix(),
                "symbol_count_sha256": sha(FIRST_COUNT),
                "namepool_path": FIRST_NAMEPOOL.relative_to(ROOT).as_posix(),
                "namepool_sha256": sha(FIRST_NAMEPOOL),
            },
            "after_identical_second_form": {
                **second,
                "symbol_count_path": SECOND_COUNT.relative_to(ROOT).as_posix(),
                "symbol_count_sha256": sha(SECOND_COUNT),
                "namepool_path": SECOND_NAMEPOOL.relative_to(ROOT).as_posix(),
                "namepool_sha256": sha(SECOND_NAMEPOOL),
            },
            "after_ide_idex_m65d": {
                **final,
                "symbol_count_path": FINAL_COUNT.relative_to(ROOT).as_posix(),
                "symbol_count_sha256": sha(FINAL_COUNT),
                "namepool_path": FINAL_NAMEPOOL.relative_to(ROOT).as_posix(),
                "namepool_sha256": sha(FINAL_NAMEPOOL),
            },
            "repeat_leak": {"symbols": 0, "namepool_bytes": 0},
        },
        "composition_accounting": {
            "static_manifest_and_native_source": {"symbols": 392, "namepool_bytes": 4879},
            "boot_only_hardware_calibration": {"symbols": 9, "namepool_bytes": 303},
            "c1_retained_after_retirement": {"symbols": 54, "namepool_bytes": 432},
            "total_used": {"symbols": 455, "namepool_bytes": 5614},
            "limits": {"symbols": 752, "namepool_bytes": 10208},
            "headroom": {"symbols": 297, "namepool_bytes": 4594},
            "report": COMPOSITION.relative_to(ROOT).as_posix(),
            "report_sha256": sha(COMPOSITION),
        },
        "capacity_delta_against_r4_claim": {
            "bank_headroom_over_1536": {"before": 337, "after": 337, "delta": 0},
            "ext_headroom_bytes": {"before": 25161, "after": 25161, "delta": 0},
            "overlay_headroom_bytes": {"before": 80, "after": 80, "delta": 0},
            "directory_headroom": {"before": 168, "after": 168, "delta": 0},
            "symbol_headroom": {"before": 388, "after": 297, "delta": -91},
            "namepool_headroom_bytes": {"before": 5625, "after": 4594, "delta": -1031},
            "classification": "runtime-capacity-accounting-correction; product binary sizes remain unchanged",
        },
        "real_link": {
            "resident_prg": {
                "bytes": RESIDENT.stat().st_size, "sha256": sha(RESIDENT),
                "baseline_bytes": base_prg["bytes"], "byte_delta": 0,
            },
            "boot_overlay": {
                "bytes": OVERLAY.stat().st_size, "sha256": sha(OVERLAY),
                "byte_identical_to_r4": True,
            },
            "post_boot_reserve": 1873,
            "overlay_base": "0xc306",
        },
        "screen_write_string_followup": {
            "status": "closed-profile-exclusion-gated",
            "dialect_surface": "public optional m65-screen capability",
            "workbench_profile": "excluded unless LISP65_SCREEN_WRITE_STRING is defined",
            "fallback": "screen-bulk-p",
            "documentation_claim": "not promised by the canonical Workbench released-surface list",
            "contract": "config/v11-surface-delivery-parity.json",
            "contract_sha256": sha(ROOT / "config/v11-surface-delivery-parity.json"),
            "gate": parity,
        },
        "evidence_policy": {
            "sealed_r4": "left immutable as historical stopped-candidate evidence",
            "old_live_c1_claim": (
                "the archived zero-new-symbol/name assertion is disproved by the "
                "bound hardware plan; this addendum supersedes it for every future candidate"
            ),
            "amendment": "new correction receipt; no sealed archive is edited",
        },
        "source_bindings": source_contracts(),
        "promotion_gate": {
            "owner_authorization_required_for": [
                "symbol-headroom-repin-388-to-297",
                "namepool-headroom-repin-5625-to-4594",
            ],
            "after_authorization": "commit correction, rebuild product set, restart R4/R5/R6 chain",
        },
        "claim_limit": (
            "This probe proves the three C1 first-form root causes, the corrected "
            "first cold hardware result, and the exact runtime-capacity repin. It "
            "does not promote a product set, preserve the stopped R5 receipts, or "
            "authorize the symbol/namepool claim correction."
        ),
    }


def validate(report: dict[str, Any]) -> None:
    require(report.get("format") == "lisp65-v11-wave1-c1-first-form-correction-probe-v1",
            "receipt format drift")
    require(report.get("status") == "passed-not-promoted-owner-capacity-review-required",
            "receipt status drift")
    hardware = report.get("hardware", {})
    require(hardware.get("after_first_form", {}).get("result") == 42,
            "receipt does not bind the first form result")
    require(hardware.get("repeat_leak") == {"symbols": 0, "namepool_bytes": 0},
            "receipt does not bind repeat stability")
    accounting = report.get("composition_accounting", {})
    require(accounting.get("total_used") == {"symbols": 455, "namepool_bytes": 5614},
            "receipt total accounting drift")
    require(accounting.get("headroom") == {"symbols": 297, "namepool_bytes": 4594},
            "receipt headroom drift")
    delta = report.get("capacity_delta_against_r4_claim", {})
    require(delta.get("symbol_headroom", {}).get("delta") == -91,
            "receipt symbol delta drift")
    require(delta.get("namepool_headroom_bytes", {}).get("delta") == -1031,
            "receipt namepool delta drift")
    require(report.get("screen_write_string_followup", {}).get("status") ==
            "closed-profile-exclusion-gated", "profile exclusion claim drift")


def verify_live(report: dict[str, Any]) -> None:
    validate(report)
    bindings = report.get("source_bindings")
    require(isinstance(bindings, dict) and bindings, "receipt lacks source bindings")
    for raw, expected in bindings.items():
        path = ROOT / raw
        require(path.is_file() and sha(path) == expected, f"source binding drift: {raw}")
    baseline = report.get("baseline", {})
    archive = ROOT / str(baseline.get("r4_archive", ""))
    require(
        archive.is_file() and sha(archive) == baseline.get("r4_archive_sha256"),
        "R4 baseline archive binding drift",
    )


def selftest() -> None:
    seed = {
        "format": "lisp65-v11-wave1-c1-first-form-correction-probe-v1",
        "status": "passed-not-promoted-owner-capacity-review-required",
        "hardware": {"after_first_form": {"result": 42},
                     "repeat_leak": {"symbols": 0, "namepool_bytes": 0}},
        "composition_accounting": {
            "total_used": {"symbols": 455, "namepool_bytes": 5614},
            "headroom": {"symbols": 297, "namepool_bytes": 4594},
        },
        "capacity_delta_against_r4_claim": {
            "symbol_headroom": {"delta": -91},
            "namepool_headroom_bytes": {"delta": -1031},
        },
        "screen_write_string_followup": {"status": "closed-profile-exclusion-gated"},
    }
    validate(seed)
    mutations = [
        ("first", lambda x: x["hardware"]["after_first_form"].update(result=0)),
        ("leak", lambda x: x["hardware"].update(repeat_leak={"symbols": 1, "namepool_bytes": 0})),
        ("symbol", lambda x: x["capacity_delta_against_r4_claim"]["symbol_headroom"].update(delta=-90)),
        ("profile", lambda x: x["screen_write_string_followup"].update(status="passed")),
    ]
    for label, mutate in mutations:
        value = deepcopy(seed)
        mutate(value)
        try:
            validate(value)
        except ProbeError:
            continue
        raise ProbeError(f"selftest mutation accepted: {label}")
    print(f"v11-wave1-c1-first-form: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            return 0
        if args.verify:
            verify_live(load(args.out))
            print("v11-wave1-c1-first-form: VERIFY PASS source-bindings=closed")
            return 0
        report = build_report()
        validate(report)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "v11-wave1-c1-first-form: PASS first=42 symbols=455/752 "
            "namepool=5614/10208 status=passed-not-promoted"
        )
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ProbeError) as exc:
        print(f"v11-wave1-c1-first-form: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
