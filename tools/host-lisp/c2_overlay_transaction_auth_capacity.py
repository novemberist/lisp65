#!/usr/bin/env python3
"""Run the one authorized product-shaped transaction-auth capacity seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_capacity_probe as H  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/overlay-transaction-auth-capacity-probe")
BASELINE = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-capacity-placement-probe-receipt.json")
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH",
)


class CapacityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CapacityError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def prepare(out: Path, artifacts: dict[str, Any]) -> tuple[Path, list[Path]]:
    out.mkdir(parents=True, exist_ok=False)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    artifact_manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    lines = [
        "profile=" + P.PROFILE,
        "mode=overlay-transaction-auth-capacity-placement-probe",
        "hardware_execution=prohibited-non-product-seed",
        "feature_defines=" + ",".join(FEATURES),
        "transaction_auth_contract_receipt_sha256=" + sha(CONTRACT_RECEIPT),
        "c2_artifacts_sha256=" + sha(artifact_manifest),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "v2_profile_parity_sha256=" + sha(out / "v2-product-profile-parity.json"),
        "product_closure_link_count=0",
        "resident_island_seed_link_count=1",
    ]
    for raw in P.source_list():
        path = Path(raw)
        lines.append(f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    contract = out / "resolved-profile.txt"
    P.write(contract, "\n".join(lines) + "\n")

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


def run_probe(out: Path) -> dict[str, Any]:
    require(CONTRACT_RECEIPT.is_file(), "host/source contract receipt absent")
    host = json.loads(CONTRACT_RECEIPT.read_text(encoding="utf-8"))
    require(host.get("status") == "passed-host-source-mutations-capacity-not-run",
            "host/source contract receipt is not green")
    baseline_elf = BASELINE / "resident-island-seed.prg.elf"
    require(baseline_elf.is_file(), "Link-30 seed baseline absent")
    artifacts_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    contract, headers = prepare(out, artifacts)
    seed = P.compile_link(
        out, "overlay-transaction-auth-capacity-seed.prg", headers, artifacts,
        probe_definitions=FEATURES)
    elf = Path(str(seed) + ".elf")
    sections = P.section_table(elf)
    baseline = P.section_table(baseline_elf)
    slice_names = sorted({
        spec.split(":")[2]
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    })
    slices = {name: sections.get(name, {}).get("bytes", 0)
              for name in slice_names}
    old_slices = {name: baseline.get(name, {}).get("bytes", 0)
                  for name in slice_names}
    over = {name: value for name, value in slices.items()
            if value <= 0 or value > 1792}
    text = sections[".text"]
    old_text = baseline[".text"]
    bss = sections[".bss"]
    old_bss = baseline[".bss"]
    text_headroom = 0xB481 - text["address"] - text["bytes"]
    old_text_headroom = 0xB481 - old_text["address"] - old_text["bytes"]
    bss_headroom = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    old_bss_headroom = (
        P.FIXED_BANK0_BASE - old_bss["address"] - old_bss["bytes"])
    island = sections[".lisp65_resident_island"]["bytes"]
    annex = sections[".lisp65_resident_island_annex"]["bytes"]
    old_island = baseline[".lisp65_resident_island"]["bytes"]
    old_annex = baseline[".lisp65_resident_island_annex"]["bytes"]
    island_headroom = 2048 - island - annex
    e000_rows = {
        name: {
            "link30_address": baseline.get(name, {}).get("address"),
            "probe_address": sections.get(name, {}).get("address"),
            "link30_bytes": baseline.get(name, {}).get("bytes", 0),
            "probe_bytes": sections.get(name, {}).get("bytes", 0),
            "delta_bytes": sections.get(name, {}).get("bytes", 0)
                - baseline.get(name, {}).get("bytes", 0),
        }
        for name in P.KERNAL_SECTIONS
    }
    e000_live = sum(row["probe_bytes"] for row in e000_rows.values())
    old_e000_live = sum(row["link30_bytes"] for row in e000_rows.values())
    e000_margin = P.KERNAL_WINDOW_BYTES - e000_live
    require(all(row["delta_bytes"] == 0
                and row["probe_address"] == row["link30_address"]
                for row in e000_rows.values()),
            f"FIRST RED: closed E000 identity/size drift: {e000_rows}")
    require(not over and min(text_headroom, bss_headroom,
                             island_headroom, e000_margin) >= 0,
            "FIRST RED: capacity: "
            f"slices={over} text={text_headroom} bss={bss_headroom} "
            f"island={island_headroom} e000={e000_margin}")

    P.extract_provisional_kernal_window(out, seed)
    P.handoff_z_abi_gate(out, seed, "transaction-auth-capacity-probe")
    ownership = P.pre_ownership_gate(
        out, seed, "transaction-auth-capacity-probe")
    data_refs = P.profile_data_reference_gate(
        out, seed, "transaction-auth-capacity-probe", ownership)
    P.fixed_facade_gate(out, seed, "transaction-auth-capacity-probe")
    boot = P.overlay_pack_family(
        out, seed, contract, "boot", "transaction-auth-capacity-probe")
    session = P.overlay_pack_family(
        out, seed, contract, "session", "transaction-auth-capacity-probe")
    kernal = P.kernal_freedom_gate(out, seed)
    direct = H.direct_path_gate(elf)
    retained = H.retained_link29_seams_gate(
        elf, BASELINE / "lisp65-c2-substitution-linked.prg.elf")
    boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
    session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
    old_boot = json.loads((BASELINE / "runtime-overlays-boot-final.json").read_text())
    old_session = json.loads((BASELINE / "runtime-overlays-session-final.json").read_text())
    phase_deltas = {
        name: {"link30_bytes": old_slices[name], "probe_bytes": slices[name],
               "delta_bytes": slices[name] - old_slices[name]}
        for name in slice_names if slices[name] != old_slices[name]
    }
    report = {
        "format": "lisp65-c2-overlay-transaction-auth-capacity-placement-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-product-shaped-capacity-placement-probe-only",
        "scope": {
            "resident_island_seed_links": 1,
            "product_closure_links": 0,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
            "feature_defines": list(FEATURES),
        },
        "identity": {
            "contract_receipt": bind(CONTRACT_RECEIPT),
            "seed_prg": bind(seed),
            "seed_elf": bind(elf),
            "baseline_link30_seed_elf": bind(baseline_elf),
            "resolved_profile": bind(contract),
        },
        "capacity": {
            "bank0_text": {
                "link30_headroom_bytes": old_text_headroom,
                "probe_headroom_bytes": text_headroom,
                "delta_headroom_bytes": text_headroom - old_text_headroom,
            },
            "bank0_ordinary_bss": {
                "link30_headroom_bytes": old_bss_headroom,
                "probe_headroom_bytes": bss_headroom,
                "delta_headroom_bytes": bss_headroom - old_bss_headroom,
            },
            "bank0_fixed_block": {
                "headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
                "delta_bytes": 0,
            },
            "cpu_e000_window": {
                "link30_occupied_bytes": old_e000_live,
                "probe_occupied_bytes": e000_live,
                "hard_delta_bytes": e000_live - old_e000_live,
                "named_section_identity": e000_rows,
                "future_margin_bytes": e000_margin,
                "growth_policy": "closed-to-new-tenants",
            },
            "resident_island": {
                "link30_base_bytes": old_island,
                "link30_annex_bytes": old_annex,
                "probe_base_bytes": island,
                "probe_annex_bytes": annex,
                "probe_headroom_bytes": island_headroom,
            },
            "runtime_overlay_slices": {
                "cap_bytes": 1792,
                "largest_section": max(slices, key=slices.get),
                "largest_bytes": max(slices.values()),
                "changed_sections": phase_deltas,
                "over_cap_or_missing": over,
            },
            "runtime_overlay_bank": {
                "boot_bytes": boot_manifest["storage"]["size"],
                "boot_delta_vs_link30": boot_manifest["storage"]["size"]
                    - old_boot["storage"]["size"],
                "boot_headroom_bytes": 65536 - boot_manifest["storage"]["size"],
                "session_bytes": session_manifest["storage"]["size"],
                "session_delta_vs_link30": session_manifest["storage"]["size"]
                    - old_session["storage"]["size"],
                "session_headroom_bytes":
                    65536 - session_manifest["storage"]["size"],
            },
        },
        "fresh_structural_gates": {
            "v2_profile_parity": "passed-base-profile-plus-explicit-probe-defines",
            "direct_hot_materializer": direct,
            "retained_link29_seams": retained,
            "handoff_z_and_io": "passed",
            "pre_ownership": "passed",
            "profile_data_references": "passed",
            "profile_data_relocation_count": data_refs["matched_relocation_count"],
            "fixed_facade": "passed-unchanged-thirteen-vectors",
            "kernal_freedom": "passed",
            "owned_control_flow_edges": kernal["control_flow_ownership"][
                "direct_window_edges"],
        },
        "claim_limit": (
            "One owner-authorized product-shaped seed for source, capacity, "
            "placement and structure only. No product closure link, product SHA, "
            "hardware, latency, promotion or release claim."
        ),
        "next_gate": (
            "Report exact deltas for review. A successor product link remains "
            "blocked pending separate authorization."
        ),
    }
    P.write(out / "overlay-transaction-auth-capacity-probe.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        value = run_probe(args.out.resolve())
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists() and RECEIPT.read_bytes() != data:
                raise CapacityError("refusing to overwrite divergent receipt")
            RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "capacity receipt absent or drifted")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        cap = value["capacity"]
        print("c2-overlay-transaction-auth-capacity: " + verb
              + f" text={cap['bank0_text']['probe_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss']['probe_headroom_bytes']}"
              + f" e000={cap['cpu_e000_window']['future_margin_bytes']}"
              + f" island={cap['resident_island']['probe_headroom_bytes']}"
              + " product-links=0")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, CapacityError) as exc:
        print(f"c2-overlay-transaction-auth-capacity: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
