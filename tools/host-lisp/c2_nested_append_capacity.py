#!/usr/bin/env python3
"""Price the authorized C2D-v4 nested-append seams without a product link."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
SOURCE = ROOT / "scripts/c2-nested-append-capacity-main.c"
CONTRACT = ROOT / "config/c2-nested-append-unwind-contract.json"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-unwind-contract-probe-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK32_PRODUCT = LINK32 / "lisp65-c2-substitution-linked.prg"
LINK32_ELF = LINK32 / "lisp65-c2-substitution-linked.prg.elf"
LINK32_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link32-preinstall-island-guard-structural-receipt.json")
SESSION_MANIFEST = LINK32 / "runtime-overlays-session-final.json"
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
DEFAULT_OUT = ROOT / "build/c2.2/nested-append-capacity-placement-probe-locator"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-capacity-placement-first-red-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str]) -> str:
    proc = subprocess.run(command, cwd=ROOT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise ProbeError("command failed: " + " ".join(command)
                         + "\n" + proc.stdout + proc.stderr)
    return proc.stdout


def write(path: Path, data: str) -> None:
    encoded = data.encode("utf-8")
    if path.exists():
        require(path.read_bytes() == encoded, f"generated artifact drift: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)


def section_sizes(obj: Path) -> dict[str, int]:
    text = run([str(TOOLCHAIN / "llvm-size"), "-A", str(obj)])
    result: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^(\.\S+)\s+(\d+)\s+\d+\s*$", line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def symbol_sizes(elf: Path) -> dict[str, int]:
    text = run([str(TOOLCHAIN / "llvm-nm"), "--defined-only",
                "--print-size", "--numeric-sort", str(elf)])
    result: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if (len(fields) >= 4 and re.fullmatch(r"[0-9a-fA-F]+", fields[1])):
            result[fields[-1]] = int(fields[1], 16)
    return result


def align(value: int, quantum: int = 256) -> int:
    return (value + quantum - 1) & ~(quantum - 1)


def run_probe(out: Path) -> dict[str, Any]:
    require(not out.exists(), f"output already exists: {out}")
    for path in (SOURCE, CONTRACT, CONTRACT_RECEIPT, LINK32_PRODUCT, LINK32_ELF,
                 LINK32_RECEIPT, SESSION_MANIFEST, INITIAL_C2D):
        require(path.is_file(), f"required input absent: {path}")
    require(sha(LINK32_PRODUCT) == EXPECTED_PRODUCT_SHA,
            "Link-32 product identity drift")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["capacity_gate_before_product_work"]["e000_growth_policy"]
            == "closed-to-new-tenants", "E000 closure policy drift")
    host = json.loads(CONTRACT_RECEIPT.read_text(encoding="utf-8"))
    require(host["status"] == "passed-host-contract-probe-product-work-not-authorized",
            "contract probe is not green")

    out.mkdir(parents=True)
    obj = out / "c2-nested-append-capacity-main.o"
    command = [
        str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall", "-Wextra",
        "-fno-lto", "-ffunction-sections", "-fdata-sections", "-c",
        str(SOURCE), "-o", str(obj),
    ]
    run(command)
    sections = section_sizes(obj)
    required = {
        ".probe.lookup.base", ".probe.lookup.v4",
        ".probe.lookup.split-resident", ".probe.lookup.tail-slice",
        ".probe.lookup.locator-resident", ".probe.lookup.tail-locator-slice",
        ".probe.gc.exact-tail", ".probe.gc.high-water-control",
        ".probe.transaction.serial", ".probe.install.base",
        ".probe.install.v4", ".probe.abort.cleanup", ".probe.abort.facade",
    }
    require(required <= sections.keys(), "target object seam inventory incomplete")

    real_symbols = symbol_sizes(LINK32_ELF)
    real_lookup = real_symbols["c2_entry_records"]
    object_lookup = sections[".probe.lookup.base"]
    calibration_error = real_lookup - object_lookup
    require(abs(calibration_error) <= 16,
            f"target-object lookup calibration exceeds 16 bytes: {calibration_error}")

    inline_delta = sections[".probe.lookup.v4"] - object_lookup
    split_delta = sections[".probe.lookup.locator-resident"] - object_lookup
    install_delta = sections[".probe.install.v4"] - sections[".probe.install.base"]
    require(inline_delta > 0 and split_delta > 0,
            "lookup candidate unexpectedly has no resident growth")

    manifest = json.loads(SESSION_MANIFEST.read_text(encoding="utf-8"))
    slices = manifest["slices"]
    old_storage = manifest["storage"]["size"]
    tail_bytes = sections[".probe.lookup.tail-locator-slice"]
    abort_bytes = sections[".probe.abort.cleanup"]
    next_offset = align(old_storage)
    tail_offset = next_offset
    abort_offset = align(tail_offset + tail_bytes)
    projected_storage = abort_offset + abort_bytes
    projected_storage_delta = projected_storage - old_storage
    require(len(slices) + 2 <= 40,
            "two additional slice records exceed the existing 1,280-byte catalog plane")

    c2d = INITIAL_C2D.read_bytes()
    require(len(c2d) == 33840 and c2d[:5] == b"C2D\0\x03",
            "initial C2D-v3 input drift")
    persistent_roots = struct.unpack_from("<H", c2d, 24)[0]
    baseline_root_blocks = math.ceil(persistent_roots / 16)
    high_water_root_blocks = 1536 // 16

    walls = contract["capacity_gate_before_product_work"]
    resident_call_bytes = 3
    projection = {
        "bank0_text": {
            "link32_headroom_bytes": walls["bank0_text_headroom_bytes"],
            "install_rewrite_delta_bytes": install_delta,
            "central_abort_call_delta_bytes": resident_call_bytes,
            "projected_headroom_bytes": (
                walls["bank0_text_headroom_bytes"] - install_delta
                - resident_call_bytes),
            "status": "fits-target-object-projection",
        },
        "ordinary_bank0_bss": {
            "link32_headroom_bytes": walls["ordinary_bank0_bss_headroom_bytes"],
            "projected_delta_bytes": 0,
            "projected_headroom_bytes": walls["ordinary_bank0_bss_headroom_bytes"],
            "status": "unchanged",
        },
        "resident_island": {
            "link32_headroom_bytes": walls["resident_island_headroom_bytes"],
            "abort_facade_bytes": sections[".probe.abort.facade"],
            "projected_headroom_bytes": (
                walls["resident_island_headroom_bytes"]
                - sections[".probe.abort.facade"]),
            "status": "fits-target-object-projection",
        },
        "runtime_overlay_session_bank": {
            "link32_bytes": old_storage,
            "link32_headroom_bytes": 65536 - old_storage,
            "added_slices": [
                {"name": "c2-transient-tail-lookup", "bytes": tail_bytes,
                 "headroom_under_1792": 1792 - tail_bytes,
                 "projected_file_offset": tail_offset},
                {"name": "c2-longjmp-abort-cleanup", "bytes": abort_bytes,
                 "headroom_under_1792": 1792 - abort_bytes,
                 "projected_file_offset": abort_offset},
            ],
            "projected_storage_bytes": projected_storage,
            "projected_storage_delta_bytes": projected_storage_delta,
            "projected_headroom_bytes": 65536 - projected_storage,
            "slice_count_before": len(slices),
            "slice_count_after": len(slices) + 2,
            "existing_publish_remove_control": {
                "target_object_bytes_per_copy": sections[
                    ".probe.gc.high-water-control"],
                "placement": "fold one copy into append-header and one into rollback",
                "append_header_headroom_before_bytes": 1792 - next(
                    item["file_size"] for item in slices
                    if item["section"] == ".lisp65_rt_c2append_header"),
                "append_rollback_headroom_before_bytes": 1792 - next(
                    item["file_size"] for item in slices
                    if item["section"] == ".lisp65_rt_c2append_rollback"),
                "projected_new_storage_bytes": 0,
                "reason": "both additions remain inside their current 256-byte quanta",
            },
            "status": "fits-target-object-projection",
        },
        "bank5_session_plane": {
            "region_bytes": 50816,
            "c2d_bytes": 33840,
            "unwind_journal_bytes": 64,
            "journal_offset": 50752,
            "raw_headroom_after_fixed_journal_bytes": 50816 - 33840 - 64,
            "ordinary_c_bss_delta_bytes": 0,
            "status": "fits-fixed-contract-location",
        },
        "cpu_e000_window": {
            "link32_future_margin_bytes": walls["e000_headroom_bytes"],
            "required_delta_bytes": 0,
            "direct_inline_lookup_delta_bytes": inline_delta,
            "split_resident_lookup_delta_bytes": split_delta,
            "tail_slice_bytes": tail_bytes,
            "raw_margin_after_split_bytes": walls["e000_headroom_bytes"] - split_delta,
            "policy": walls["e000_growth_policy"],
            "status": "FIRST RED: split resident lookup still changes closed E000",
        },
    }

    report = {
        "format": "lisp65-c2-nested-append-capacity-placement-first-red-v2",
        "recorded_on": "2026-07-20",
        "status": "first-red-e000-product-unchanged",
        "scope": {
            "target_objects_compiled": 1,
            "product_closure_links": 0,
            "resident_island_seed_links": 0,
            "product_source_files_changed_by_probe": 0,
            "hardware_execution": "prohibited",
            "performance_claim": "none",
        },
        "bindings": {
            "contract": bind(CONTRACT),
            "contract_probe_receipt": bind(CONTRACT_RECEIPT),
            "link32_product": bind(LINK32_PRODUCT),
            "link32_structural_receipt": bind(LINK32_RECEIPT),
            "link32_session_manifest": bind(SESSION_MANIFEST),
            "initial_c2d_v3": bind(INITIAL_C2D),
            "sizing_source": bind(SOURCE),
            "target_object": bind(obj),
            "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
        },
        "compiler": {
            "command": command,
            "mode": "llvm-mos target relocatable, -Oz, no LTO",
            "reason": (
                "Separate named sections preserve each seam for measurement; the Link-32 "
                "entry-record baseline calibrates the target-object result to the real LTO link."),
            "lookup_calibration": {
                "link32_lto_symbol_bytes": real_lookup,
                "target_object_baseline_bytes": object_lookup,
                "difference_bytes": calibration_error,
            },
        },
        "costs": {
            "transient_directory_lookup": {
                "persistent_path_dma_reads_added": 0,
                "persistent_path_change": "one range branch; original two reads unchanged",
                "direct_inline": {
                    "candidate_bytes": sections[".probe.lookup.v4"],
                    "baseline_bytes": object_lookup,
                    "delta_bytes": inline_delta,
                },
                "split": {
                    "resident_candidate_bytes": sections[
                        ".probe.lookup.locator-resident"],
                    "resident_delta_bytes": split_delta,
                    "tail_slice_bytes": tail_bytes,
                    "tail_validation": (
                        "active image interval locates the slot; the resident directory-to-slot "
                        "reverse edge must match; at most four 32-byte image records"),
                    "wider_four_pointer_split_rejected": {
                        "resident_delta_bytes": sections[
                            ".probe.lookup.split-resident"] - object_lookup,
                        "tail_slice_bytes": sections[".probe.lookup.tail-slice"],
                        "reason": "the locator context is both smaller and equally bidirectional",
                    },
                },
            },
            "gc_high_tail": {
                "selected_capacity_variant": "reuse-current-B2-span-walker",
                "new_walker_bytes": 0,
                "control_bytes_per_publish_or_remove_copy": sections[
                    ".probe.gc.high-water-control"],
                "root_value_read_width_bytes": 32,
                "link32_persistent_root_count": persistent_roots,
                "link32_blocks_per_collection": baseline_root_blocks,
                "active_transient_blocks_per_collection": high_water_root_blocks,
                "additional_blocks_per_collection": (
                    high_water_root_blocks - baseline_root_blocks),
                "additional_mark_inputs_per_collection": 1536 - persistent_roots,
                "holes_rule": "inactive high plane is zero by publish/remove invariant",
                "exact_interval_alternative": {
                    "target_object_bytes": sections[".probe.gc.exact-tail"],
                    "placement": "does not fit Island and cannot be transported while an overlay is busy",
                },
                "claim": "transport count only; no latency acceptance",
            },
            "serial_transaction_boundaries": {
                "decomposed_control_bytes": sections[".probe.transaction.serial"],
                "full_install_baseline_bytes": sections[".probe.install.base"],
                "full_install_v4_bytes": sections[".probe.install.v4"],
                "full_install_delta_bytes": install_delta,
                "transaction_active_during_execute": False,
                "placement": "rewrite existing Bank-0 install function; no new resident function",
            },
            "longjmp_abort_cleanup": {
                "transported_cleanup_slice_bytes": abort_bytes,
                "resident_island_facade_bytes": sections[".probe.abort.facade"],
                "bank0_callsite_projection_bytes": resident_call_bytes,
                "journal_reads": 2,
                "journal_read_width_bytes": 32,
                "journal_bytes": 64,
                "dead_c_stack_pointers": 0,
            },
        },
        "capacity_and_placement": projection,
        "first_red": {
            "gate": "cpu-e000-delta-exactly-zero",
            "observed_smallest_measured_split_delta_bytes": split_delta,
            "why_it_stops": (
                "The smallest measured transported-tail design still grows the resident "
                "entry-record branch. Raw contingency remains, but the owner-authorized "
                "window policy is exact zero and closed to new tenants."),
            "not_attempted": [
                "product source implementation", "resident seed link",
                "product closure link", "hardware", "latency acceptance",
            ],
        },
        "triage_inputs_not_authorization": [
            {
                "id": "e000-in-place-reclaim",
                "requirement": f"recover at least {split_delta} bytes inside the existing entry-record closure",
                "cost_preserved": "Tail locator remains a 480-byte Session slice",
            },
            {
                "id": "directory-handle-contract-change",
                "requirement": "remove the resident low/high branch by changing transient handle translation",
                "warning": "format/VM ABI question; not a capacity tweak",
            },
            {
                "id": "authorize-contingency-use",
                "raw_result": f"{walls['e000_headroom_bytes'] - split_delta} bytes would remain",
                "warning": "currently forbidden by the explicit zero-delta/closed-window contract",
            },
        ],
        "claim_limit": (
            "One product-shaped target-object sizing probe. It proves the first placement "
            "red and prices the four named seams; it is not a product implementation, LTO "
            "capacity authorization, product link, hardware result, latency claim or promotion."),
        "next_gate": (
            "Stop for review. No implementation or product link is authorized; the E000 "
            "resident branch needs an explicit triage decision first."),
    }
    write(out / "capacity-placement-report.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    write(out / "compile-command.txt", " ".join(command) + "\n")
    write(out / "section-sizes.json",
          json.dumps(sections, indent=2, sort_keys=True) + "\n")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def check_receipt() -> dict[str, Any]:
    require(RECEIPT.is_file(), "capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value["status"] == "first-red-e000-product-unchanged",
            "receipt status drift")
    require(value["scope"]["product_closure_links"] == 0
            and value["scope"]["product_source_files_changed_by_probe"] == 0,
            "receipt scope drift")
    require(value["capacity_and_placement"]["cpu_e000_window"]["status"]
            .startswith("FIRST RED"), "E000 first red absent")
    for item in value["bindings"].values():
        path = ROOT / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and sha(path) == item["sha256"],
                f"bound artifact drift: {item['path']}")
    return value


def protect_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "check":
            value = check_receipt()
            verb = "CHECK PASS"
        else:
            value = run_probe(args.out.resolve())
            encoded = canonical(value)
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == encoded,
                        "refusing to overwrite divergent capacity receipt")
            else:
                RECEIPT.write_bytes(encoded)
            os.chmod(RECEIPT, 0o444)
            protect_tree(args.out.resolve())
            verb = "WROTE FIRST RED"
        e000 = value["capacity_and_placement"]["cpu_e000_window"]
        print("c2-nested-append-capacity: " + verb
              + f" e000-delta={e000['split_resident_lookup_delta_bytes']}"
              + " required=0 product-links=0")
        return 0
    except (ProbeError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as exc:
        print(f"c2-nested-append-capacity: FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
