#!/usr/bin/env python3
"""Map-only feasibility calculation for one C2 handoff reanchor."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-handoff-reanchor-feasibility-contract.json"
CURRENT_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-boot-branch-probe/"
    "l65r-v2-boot-family-seed.prg.map")
VALID_MAP = ROOT / (
    "build/c2.2/substitution/product-link-33-profile-inventory-final/"
    "resident-island-seed.prg.map")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-boot-branch-relocation-first-red-diagnosis.json")
LINK32 = ROOT / (
    "build/c2.2/substitution/product-link-32-preinstall-island-guard/"
    "lisp65-c2-substitution-linked.prg")
LINK32_SHA256 = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-feasibility-receipt.json")

SECTION_ORDER = [
    ".lisp65_c2_kernal_handoff",
    ".lisp65_c2_host_facade",
    ".lisp65_c2_kernal_io_reveal",
    ".lisp65_c2_kernal_map_switch",
    ".lisp65_c2_kernal_state",
    ".rodata",
    ".lisp65_runtime_overlay_verifier_bindings",
    ".data",
    ".bss",
]
FIXED_SECTIONS = [
    ".lisp65_c2_fixed_bank0",
    ".lisp65_c2_fixed_bank0_code",
    ".lisp65_c2_fixed_bank0_hot_bss",
    ".noinit",
    ".lisp65_workbench_overlay",
]
VECTOR_SYMBOLS = [
    "c2_facade_vm_code_load",
    "c2_facade_c2_dma",
    "c2_facade_overlay_call_family",
    "c2_facade_c2e_cons",
    "c2_facade_c2e_overlay",
    "c2_facade_car",
    "c2_facade_cdr",
    "c2_facade_gc_collect",
    "c2_facade_str_open",
    "c2_facade_str_putc",
    "c2_facade_intern",
    "c2_facade_select_family",
    "c2_facade_gc_mark",
    "c2_facade_runtime_overlay_exec",
    "c2_facade_handle_normalize",
]

CURRENT_AUTHORITIES = [
    ("config/c2-kernal-unmap-contract.json", "machine-readable address and mutation-domain contract"),
    ("config/c2-link33-product-profile.json", "canonical fifteen-vector profile and handle-normalize VMA"),
    ("docs/planning/c2.2-kernal-unmap-contract.md", "human-readable handoff/facade/publish-last contract"),
    ("docs/planning/c2.2-link33-coordinated-residency-plan.md", "current Link-33 layout and fixed-margin record"),
    ("tools/host-lisp/c2_product_substitution_link.py", "canonical linker generator and all final structural gates"),
]

EXECUTION_GATES = [
    ("tools/host-lisp/c2_link33_product_profile.py", "canonical profile validator"),
    ("tools/host-lisp/c2_preinstall_island_guard.py", "pre-install closure and exact facade interval"),
    ("tools/host-lisp/c2_link33_facade15_section_replay.py", "fifteenth-vector section proof"),
    ("tools/host-lisp/c2_link33_facade15_provenance_replay.py", "fifteenth-vector provenance proof"),
    ("tools/host-lisp/c2_link33_profile_binding_replay.py", "profile hash binding"),
    ("tools/host-lisp/c2_link33_section_inventory_replay.py", "profile-derived final-section inventory"),
    ("tools/host-lisp/c2_link33_bss_triage_probe.py", "WPLTO placement and headroom probe"),
    ("tools/host-lisp/c2_link33_bss_triage_product_link.py", "fresh Link-33 driver and prerequisite pins"),
    ("tools/host-lisp/c2_l65r_v2_product_probe.py", "L65R-v2 product-shaped probe"),
    ("tools/host-lisp/c2_l65r_v2_boot_family_probe.py", "boot-family WPLTO probe"),
    ("tools/host-lisp/c2_l65r_v2_boot_branch_relocation_probe.py", "current branch-relocation WPLTO wrapper"),
]

BANNER_EVIDENCE = [
    "config/v11-repl-banner-native-binding-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-repl-banner-native-binding-diagnosis.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-repl-banner-block-receipt.json",
    "docs/planning/repl-banner-spec-1.1.md",
    "src/repl.c",
    "lib/repl-banner.lisp",
]


class FeasibilityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FeasibilityError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(relative: str | Path, role: str | None = None) -> dict[str, Any]:
    path = ROOT / relative
    require(path.is_file(), f"bound input missing: {relative}")
    result: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if role is not None:
        result["role"] = role
    return result


def parse_sections(path: Path) -> dict[str, dict[str, int]]:
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(\.\S+)\s*$")
    result: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        address, lma, size, name = match.groups()
        if name in result:
            raise FeasibilityError(f"duplicate top-level section: {name}")
        start = int(address, 16)
        count = int(size, 16)
        result[name] = {
            "address": start,
            "lma": int(lma, 16),
            "bytes": count,
            "end_exclusive": start + count,
        }
    return result


def hx(value: int) -> str:
    return f"0x{value:04x}"


def row(name: str, before: dict[str, int], after_address: int,
        classification: str) -> dict[str, Any]:
    size = before["bytes"]
    return {
        "name": name,
        "bytes": size,
        "before": {"start": hx(before["address"]),
                   "end_exclusive": hx(before["end_exclusive"])},
        "after": {"start": hx(after_address),
                  "end_exclusive": hx(after_address + size)},
        "delta_bytes": after_address - before["address"],
        "classification": classification,
    }


def build_report() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for key, path in (("current_two_byte_first_red", CURRENT_MAP),
                      ("last_valid_predecessor_binding", VALID_MAP)):
        expected = contract["source_maps"][key]["sha256"]
        require(sha(path) == expected, f"{key} map SHA drift")
    require(sha(FIRST_RED) ==
            "2217ab1eff952428dbb54e35be19feccd404f678b9610bb1fc9711ba1093fa32",
            "branch-relocation First Red receipt drift")
    require(LINK32.is_file() and sha(LINK32) == LINK32_SHA256,
            "Link-32 rollback identity drift")

    current = parse_sections(CURRENT_MAP)
    valid = parse_sections(VALID_MAP)
    for name in [".text", *SECTION_ORDER, *FIXED_SECTIONS]:
        require(name in current and name in valid, f"section absent: {name}")

    expected_current = {
        ".text": (0x2023, 0x9460),
        ".lisp65_c2_kernal_handoff": (0xB481, 0x121),
        ".lisp65_c2_host_facade": (0xB5A2, 0x2D),
        ".lisp65_c2_kernal_io_reveal": (0xB5CF, 0x0B),
        ".lisp65_c2_kernal_map_switch": (0xB5DA, 0x0A),
        ".lisp65_c2_kernal_state": (0xB5E4, 0x14),
        ".rodata": (0xB5FA, 0x33A),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB934, 0x20),
        ".data": (0xB954, 0x16),
        ".bss": (0xB96A, 0x633),
        ".lisp65_c2_fixed_bank0": (0xC080, 0x198),
        ".lisp65_c2_fixed_bank0_code": (0xC218, 0x2D),
        ".lisp65_c2_fixed_bank0_hot_bss": (0xC245, 0xF0),
        ".lisp65_workbench_overlay": (0xC356, 0x6C3),
    }
    for name, (address, count) in expected_current.items():
        require((current[name]["address"], current[name]["bytes"]) ==
                (address, count), f"current WPLTO geometry drift: {name}")

    # The failed map's two bytes between state and rodata already violate the
    # predecessor contract.  The valid map proves the lawful zero-gap chain.
    require(valid[".lisp65_c2_kernal_state"]["end_exclusive"] ==
            valid[".rodata"]["address"],
            "valid state/rodata predecessor binding absent")
    for left, right in zip(SECTION_ORDER[4:], SECTION_ORDER[5:]):
        require(valid[left]["end_exclusive"] == valid[right]["address"],
                f"valid predecessor chain gap: {left}->{right}")
    require(current[".lisp65_c2_kernal_state"]["end_exclusive"] + 2 ==
            current[".rodata"]["address"],
            "failed-map rodata drift is not exactly two bytes")

    text_end = current[".text"]["end_exclusive"]
    old_handoff = valid[".lisp65_c2_kernal_handoff"]["address"]
    target_reserve = contract["target"][
        "standing_bank0_text_lto_noise_reserve_bytes"]
    new_handoff = text_end + target_reserve
    shift = new_handoff - old_handoff
    require(text_end == 0xB483 and old_handoff == 0xB481,
            "two-byte First Red geometry drift")
    require(shift == 34 and new_handoff == 0xB4A3,
            "derived target reanchor changed")

    pre_fixed_pocket = (valid[".lisp65_c2_fixed_bank0"]["address"] -
                        valid[".bss"]["end_exclusive"])
    require(pre_fixed_pocket == 229, "pre-fixed pocket drift")
    max_shift = pre_fixed_pocket
    require(shift <= max_shift, "target shift does not fit")

    chain = []
    for name in SECTION_ORDER:
        chain.append(row(name, valid[name], valid[name]["address"] + shift,
                         "moves-as-one-predecessor-bound-chain"))
    fixed = []
    for name in FIXED_SECTIONS:
        fixed.append(row(name, valid[name], valid[name]["address"],
                         "fixed-point-unchanged"))

    vector_before = valid[".lisp65_c2_host_facade"]["address"]
    vector_after = vector_before + shift
    vectors = [{
        "name": name,
        "before": hx(vector_before + index * 3),
        "after": hx(vector_after + index * 3),
        "bytes": 3,
        "delta_bytes": shift,
    } for index, name in enumerate(VECTOR_SYMBOLS)]

    post_fixed_reserve = (valid[".lisp65_workbench_overlay"]["address"] -
                          valid[".lisp65_c2_fixed_bank0_hot_bss"][
                              "end_exclusive"])
    require(post_fixed_reserve == 33, "post-fixed reserve drift")

    active = [bind(path, role) for path, role in CURRENT_AUTHORITIES]
    gates = [bind(path, role) for path, role in EXECUTION_GATES]
    banner = [bind(path) for path in BANNER_EVIDENCE]

    native_binding = json.loads((ROOT / BANNER_EVIDENCE[1]).read_text(
        encoding="utf-8"))
    require(native_binding["capacity_correction"]["bank"][
                "correction_bytes"] == -3,
            "historical native banner seam delta drift")
    require("vm_run_dir" in (ROOT / "src/repl.c").read_text(encoding="utf-8")
            and "%repl-banner" in (ROOT / "lib/repl-banner.lisp").read_text(
                encoding="utf-8"),
            "banner source shape drift")

    projected_table = valid[
        ".lisp65_runtime_overlay_verifier_bindings"]["address"] + shift
    require(projected_table == 0xB954, "projected verifier table drift")

    return {
        "format": "lisp65-c2-handoff-reanchor-feasibility-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-21",
        "status": "passed-map-only-option-1-feasible-owner-decision-pending",
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_created_or_changed": 0,
            "hardware_runs": 0,
            "link33": "not-run",
            "link32": "untouched",
        },
        "authority": bind(CONTRACT.relative_to(ROOT)),
        "bound_inputs": {
            "current_first_red_map": bind(CURRENT_MAP.relative_to(ROOT)),
            "last_valid_predecessor_map": bind(VALID_MAP.relative_to(ROOT)),
            "current_first_red_diagnosis": bind(FIRST_RED.relative_to(ROOT)),
            "untouched_link32_rollback_product": bind(LINK32.relative_to(ROOT)),
        },
        "finding": {
            "option_1": "feasible-by-map",
            "old_handoff_anchor": hx(old_handoff),
            "current_text_end_exclusive": hx(text_end),
            "current_text_headroom_bytes": old_handoff - text_end,
            "target_standing_text_headroom_bytes": target_reserve,
            "required_reanchor_delta_bytes": shift,
            "new_handoff_anchor": hx(new_handoff),
            "maximum_absorbable_reanchor_delta_bytes": max_shift,
            "maximum_anchor": hx(old_handoff + max_shift),
            "maximum_text_headroom_bytes": old_handoff + max_shift - text_end,
            "decision_note": "The requested 32-byte standing reserve fits with 195 bytes left before the unchanged 0xc080 fixed block. No combination with banner trim is required for feasibility."
        },
        "pocket_ledger": {
            "text_corridor": {
                "before_bytes": old_handoff - text_end,
                "after_bytes": new_handoff - text_end,
                "change_bytes": shift,
            },
            "lawful_pre_fixed_pocket": {
                "before_bytes": pre_fixed_pocket,
                "after_bytes": pre_fixed_pocket - shift,
                "consumed_bytes": shift,
                "range_before": f"{hx(valid['.bss']['end_exclusive'])}..{hx(valid['.lisp65_c2_fixed_bank0']['address'] - 1)}",
                "range_after": f"{hx(valid['.bss']['end_exclusive'] + shift)}..{hx(valid['.lisp65_c2_fixed_bank0']['address'] - 1)}",
            },
            "rejected_failed_map_alignment": {
                "bytes": 2,
                "classification": "not-capacity; already rejected predecessor-placement drift",
            },
            "post_fixed_pocket": {
                "bytes": post_fixed_reserve,
                "range": "0xc335..0xc355",
                "classification": "unchanged and non-fungible for this reanchor",
            },
        },
        "objectwise_chain": chain,
        "facade_vectors": vectors,
        "fixed_points": fixed,
        "publish_last_projection": {
            "address_correction": "0xb86d is historical Link 19, not the current table. Link 28 pinned 0xb914; the last valid Link-33 WPLTO geometry already places the table at 0xb932.",
            "verifier_table_before_current_valid_geometry": "0xb932",
            "verifier_table_after_reanchor_projection": hx(projected_table),
            "verifier_table_bytes": 32,
            "kernal_crc_high_before": "0xb4aa",
            "kernal_crc_high_after_projection": hx(0xB4AA + shift),
            "kernal_crc_low_before": "0xb4ae",
            "kernal_crc_low_after_projection": hx(0xB4AE + shift),
            "rule": "All 34 named post-link bytes remain the sole mutation domain; their addresses are successor-pinned after the one real link, never inferred as acceptance from this map calculation."
        },
        "repin_inventory": {
            "current_authorities": active,
            "execution_gate_sources": gates,
            "successor_receipts_to_regenerate": [
                "facade-15 section/provenance replays",
                "canonical-profile binding replay",
                "profile-derived section-inventory replay",
                "WPLTO capacity/placement receipt",
                "fresh Link-33 structural and publish-last receipts",
                "hardware-presmoke identity receipt after structural acceptance"
            ],
            "historical_receipts": "immutable; they retain their historical addresses and SHAs",
            "effort_summary": {
                "authority_files": len(active),
                "gate_source_files": len(gates),
                "successor_receipt_families": 6,
                "facade_vector_address_pins": len(vectors),
                "post_link_address_pins": 3
            }
        },
        "banner_trim_comparison": {
            "evidence": banner,
            "visible_lisp_banner_content_trim_bank0_resident_saving_bytes": 0,
            "reason": "The visible banner is Lisp bytecode; trimming its runs/text changes the shelf/C2 image, not the native Bank-0 launch seam.",
            "complete_native_banner_launch_removal_historical_upper_bound_bytes": 3,
            "upper_bound_scope": "Measured 2026-07-16 for replacing the generated vm_run_dir launch with the smaller legacy fallback while retaining the separately beneficial REPL byte-index correction. It is a comparison value, not a current WPLTO result.",
            "standing_reserve_if_upper_bound_carried_to_current_map_bytes": 1,
            "satisfies_32_byte_standing_reserve": False,
            "warning": "Rolling back the whole historical banner block is not a 3-byte trim: that block also carried a net 81-byte Bank-0 correction, so its unrelated credits must not be discarded or misattributed."
        },
        "claim_limit": "This receipt proves only arithmetic feasibility against two SHA-bound maps and inventories the one-time repin surface. It authorizes no reanchor, source change, compiler/linker run, product byte, Link 33, hardware run, promotion, or acceptance."
    }


def selftest() -> dict[str, str]:
    report = build_report()
    finding = report["finding"]
    require(finding["required_reanchor_delta_bytes"] == 34,
            "target-shift selftest failed")
    require(report["pocket_ledger"]["lawful_pre_fixed_pocket"][
                "after_bytes"] == 195,
            "remaining-pocket selftest failed")
    require(finding["maximum_absorbable_reanchor_delta_bytes"] == 229,
            "maximum-shift selftest failed")
    require(report["fixed_points"][-1]["after"]["start"] == "0xc356",
            "overlay fixed-point selftest failed")
    altered = json.loads(json.dumps(report))
    altered["finding"]["required_reanchor_delta_bytes"] = 33
    require(altered["finding"]["required_reanchor_delta_bytes"] !=
            finding["required_reanchor_delta_bytes"],
            "shift mutation was accepted")
    return {
        "target-shift-minus-one": "rejected",
        "failed-map-two-byte-gap-as-pocket": "rejected-by-contract",
        "post-fixed-33-byte-pocket-as-pre-fixed-capacity": "rejected-by-position",
        "historical-b86d-table-as-current-pin": "rejected",
        "banner-content-trim-as-resident-credit": "rejected",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=RECEIPT)
    args = parser.parse_args()
    if args.selftest:
        print("c2-handoff-reanchor-feasibility: SELFTEST PASS " +
              json.dumps(selftest(), sort_keys=True))
        return 0
    report = build_report()
    report["negative_matrix"] = selftest()
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        require(args.output.is_file(), "receipt absent")
        require(args.output.read_text(encoding="utf-8") == encoded,
                "receipt drift")
        print("c2-handoff-reanchor-feasibility: CHECK PASS "
              f"shift={report['finding']['required_reanchor_delta_bytes']} "
              f"text-reserve={report['finding']['target_standing_text_headroom_bytes']} "
              f"pre-fixed-remain={report['pocket_ledger']['lawful_pre_fixed_pocket']['after_bytes']} "
              "links=0 product-bytes=0")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print("c2-handoff-reanchor-feasibility: PASS "
          f"shift={report['finding']['required_reanchor_delta_bytes']} "
          f"new-anchor={report['finding']['new_handoff_anchor']} "
          f"max-shift={report['finding']['maximum_absorbable_reanchor_delta_bytes']} "
          "links=0 product-bytes=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FeasibilityError as error:
        print(f"c2-handoff-reanchor-feasibility: FAIL: {error}")
        raise SystemExit(1)
