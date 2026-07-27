#!/usr/bin/env python3
"""Run the one authorized product-shaped capacity probe for MK_BCODE fix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_direct_entry_contract as D  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402

DEFAULT_OUT = ROOT / "build/c2.2/substitution/direct-entry-encoding-capacity-probe"
BASELINE = ROOT / "build/c2.2/substitution/product-link-28"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-contract-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-capacity-probe-receipt.json")


class CapacityProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CapacityProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def prepare(out: Path, artifacts: dict[str, Any]) -> tuple[Path, list[Path]]:
    out.mkdir(parents=True, exist_ok=False)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    contract_lines = [
        "profile=" + P.PROFILE,
        "mode=direct-entry-encoding-capacity-placement-probe",
        "hardware_execution=prohibited-non-product-seed",
        "direct_entry_contract_sha256=" + sha(CONTRACT_RECEIPT),
        "c2_artifacts_sha256=" + sha(manifest),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "v2_profile_parity_sha256=" + sha(out / "v2-product-profile-parity.json"),
        "product_closure_link_count=0",
        "resident_island_seed_link_count=1",
    ]
    for raw in P.source_list():
        path = Path(raw)
        contract_lines.append(
            f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    contract = out / "resolved-profile.txt"
    P.write(contract, "\n".join(contract_lines) + "\n")

    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header = out / "c2-kernal-window.generated.h"
    pin = P.kernal_window_identity_pin()
    P.write(kernal_header, P.kernal_header_values(
        int(str(pin["crc16"]), 16), str(pin["sha256"])))
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
           "--header", str(runtime_standard), "--profile", P.PROFILE)
    P.render_prepared_family_header(runtime_standard, runtime_prepared)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
           "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    P.tool("error_text_table.py", "prepare",
           "--spec", str(ROOT / "config/error-texts.json"),
           "--profile", "workbench", "--build-id", hex(build_id),
           "--header", str(error_header),
           "--binary", str(out / "error-text-table.bin"))
    P.write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    return contract, [stage_header, runtime_prepared, island_prepared,
                      error_header, kernal_header]


def changed_sections(before: dict[str, dict[str, int]],
                     after: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name in sorted(set(before) | set(after)):
        old = before.get(name, {}).get("bytes", 0)
        new = after.get(name, {}).get("bytes", 0)
        if old != new:
            result[name] = {"link28_bytes": old, "probe_bytes": new,
                            "delta_bytes": new - old}
    return result


def run_probe(out: Path) -> dict[str, Any]:
    require(CONTRACT_RECEIPT.is_file(), "direct-entry contract receipt absent")
    expected_contract = D.canonical(D.collect())
    require(CONTRACT_RECEIPT.read_bytes() == expected_contract,
            "direct-entry contract receipt drift")
    artifacts_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    contract, headers = prepare(out, artifacts)
    seed = P.compile_link(out, "direct-entry-capacity-seed.prg", headers, artifacts)
    elf = Path(str(seed) + ".elf")
    baseline_elf = BASELINE / "resident-island-seed.prg.elf"
    sections = P.section_table(elf); baseline = P.section_table(baseline_elf)
    slice_names = sorted({
        spec.split(":")[2] for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    })
    slices = {name: sections.get(name, {}).get("bytes", 0)
              for name in slice_names}
    baseline_slices = {name: baseline.get(name, {}).get("bytes", 0)
                       for name in slice_names}
    red_slices = {name: value for name, value in slices.items()
                  if value <= 0 or value > 1792}
    text = sections[".text"]
    bss = sections[".bss"]
    text_headroom = 0xB481 - (text["address"] + text["bytes"])
    bss_headroom = P.FIXED_BANK0_BASE - (bss["address"] + bss["bytes"])
    e000_live = sum(sections.get(name, {}).get("bytes", 0)
                    for name in P.KERNAL_SECTIONS)
    e000_margin = P.KERNAL_WINDOW_BYTES - e000_live
    if red_slices or text_headroom < 0 or bss_headroom < 0 or e000_margin < 0:
        raise CapacityProbeError(
            f"first red before structural gates: slices={red_slices} "
            f"text={text_headroom} bss={bss_headroom} e000={e000_margin}")

    P.extract_provisional_kernal_window(out, seed)
    P.handoff_z_abi_gate(out, seed, "direct-entry-capacity-probe")
    ownership = P.pre_ownership_gate(
        out, seed, "direct-entry-capacity-probe")
    data_refs = P.profile_data_reference_gate(
        out, seed, "direct-entry-capacity-probe", ownership)
    P.fixed_facade_gate(out, seed, "direct-entry-capacity-probe")
    boot = P.overlay_pack_family(
        out, seed, contract, "boot", "direct-entry-capacity-probe")
    session = P.overlay_pack_family(
        out, seed, contract, "session", "direct-entry-capacity-probe")
    kernal = P.kernal_freedom_gate(out, seed)
    boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
    session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
    old_boot = json.loads((BASELINE / "runtime-overlays-boot-final.json").read_text())
    old_session = json.loads((BASELINE / "runtime-overlays-session-final.json").read_text())
    shelf = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
    c2d = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
    changed = changed_sections(baseline, sections)
    phase_deltas = {
        name: {"link28_bytes": baseline_slices[name], "probe_bytes": slices[name],
               "delta_bytes": slices[name] - baseline_slices[name]}
        for name in slice_names if slices[name] != baseline_slices[name]
    }
    report = {
        "format": "lisp65-c2-direct-entry-encoding-capacity-probe-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-capacity-placement-and-structural-probe-only",
        "scope": {"resident_island_seed_links": 1, "product_closure_links": 0,
                  "hardware_execution": "prohibited", "promotion": "not-authorized"},
        "identity": {
            "contract_receipt": bind(CONTRACT_RECEIPT),
            "seed_prg": bind(seed), "seed_elf": bind(elf),
            "baseline_link28_seed_elf": bind(baseline_elf),
            "resolved_profile": bind(contract),
            "product_shelf_unchanged": bind(shelf),
            "initial_c2d_unchanged": bind(c2d),
        },
        "capacity": {
            "bank0_text": {"headroom_bytes": text_headroom,
                           "link28_headroom_bytes": 0xB481 - (
                               baseline[".text"]["address"] + baseline[".text"]["bytes"])},
            "bank0_ordinary_bss": {"headroom_bytes": bss_headroom,
                                   "link28_headroom_bytes": 19,
                                   "growth_policy": "full-no-new-resident-growth-budget"},
            "bank0_fixed_block": {"headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
                                  "link28_headroom_bytes": 273},
            "cpu_e000_window": {"future_margin_bytes": e000_margin,
                                "link28_future_margin_bytes": 386,
                                "growth_policy": "closed-to-new-tenants"},
            "runtime_overlay_slices": {
                "cap_bytes": 1792, "largest_bytes": max(slices.values()),
                "largest_section": max(slices, key=slices.get),
                "over_cap_or_missing": red_slices,
                "changed_phase_sections": phase_deltas,
            },
            "runtime_overlay_bank": {
                "boot_bytes": boot_manifest["storage"]["size"],
                "boot_delta_vs_link28": boot_manifest["storage"]["size"]
                    - old_boot["storage"]["size"],
                "boot_headroom_bytes": 65536 - boot_manifest["storage"]["size"],
                "session_bytes": session_manifest["storage"]["size"],
                "session_delta_vs_link28": session_manifest["storage"]["size"]
                    - old_session["storage"]["size"],
                "session_headroom_bytes": 65536 - session_manifest["storage"]["size"],
            },
            "bank5_mutable_plane": {"bytes": c2d.stat().st_size,
                                    "headroom_bytes": 65536 - c2d.stat().st_size,
                                    "delta_bytes": 0},
            "attic_immutable_shelf": {"bytes": shelf.stat().st_size,
                                      "delta_bytes": 0},
            "resident_island": {
                "base_bytes": sections[".lisp65_resident_island"]["bytes"],
                "annex_bytes": sections[".lisp65_resident_island_annex"]["bytes"],
                "delta_vs_link28_bytes": (
                    sections[".lisp65_resident_island"]["bytes"]
                    + sections[".lisp65_resident_island_annex"]["bytes"]
                    - baseline[".lisp65_resident_island"]["bytes"]
                    - baseline[".lisp65_resident_island_annex"]["bytes"]),
            },
            "installer_slice": {
                "status": "outside-C2-product-closure-unmodified-by-this-probe",
                "delta_bytes": 0,
            },
        },
        "section_deltas_vs_link28_seed": changed,
        "fresh_structural_gates": {
            "v2_profile_parity": "passed",
            "direct_entry_contract_cross_parity_637_of_637": "passed",
            "handoff_z_and_io": "passed", "pre_ownership": "passed",
            "profile_data_references": "passed",
            "profile_data_relocation_count": data_refs["matched_relocation_count"],
            "fixed_facade": "passed", "kernal_freedom": "passed",
            "owned_control_flow_edges": kernal["control_flow_ownership"][
                "direct_window_edges"],
        },
        "claim_limit": (
            "One owner-authorized product-shaped seed capacity and placement "
            "probe for the direct-entry correction. It creates no product closure "
            "link, device claim, promotion or release claim."
        ),
        "next_gate": (
            "A green result permits at most one separately named successor product "
            "link; any unapproved negative capacity drift stops first."
        ),
    }
    P.write(out / "direct-entry-capacity-probe.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument(
        "action", choices=("write", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        report = run_probe(args.out.resolve())
        data = canonical(report)
        if args.action == "write":
            RECEIPT.write_bytes(data); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.read_bytes() == data, "capacity receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        capacity = report["capacity"]
        print("c2-direct-entry-capacity-probe: " + verb
              + f" bss={capacity['bank0_ordinary_bss']['headroom_bytes']}"
              + f" e000={capacity['cpu_e000_window']['future_margin_bytes']}"
              + f" largest-slice={capacity['runtime_overlay_slices']['largest_bytes']}/1792"
              + " product-links=0")
        return 0
    except (OSError, ValueError, RuntimeError, CapacityProbeError,
            D.DirectEntryError) as error:
        print(f"c2-direct-entry-capacity-probe: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
