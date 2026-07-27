#!/usr/bin/env python3
"""Replay the corrected Link-29-seam gate over the protected amended seed."""

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
import c2_hot_refill_capacity_probe as C  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


SOURCE = ROOT / (
    "build/c2.2/substitution/hot-refill-link29-seams-capacity-probe")
TARGET = SOURCE / "hot-refill-capacity-seed.prg"
ELF = Path(str(TARGET) + ".elf")
LTO = Path(str(TARGET) + ".lto.o")
CONTRACT = SOURCE / "resolved-profile.txt"
BASELINE_ELF = ROOT / (
    "build/c2.2/substitution/product-link-29-direct-entry-encoding/"
    "resident-island-seed.prg.elf")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-vma-first-red-receipt.json")
SEMANTIC = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-contract-probe-receipt.json")
DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/hot-refill-link29-seams-gate-replay")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-gate-replay-receipt.json")

PINNED = {
    TARGET: "8fc25ae0ebc672140aa3db4cdaf1ef02ab6b5c033850fa5301fa722ade3fcdb1",
    ELF: "6ba5d9bed4d33915fe50d0f918db06f8cac143f1681135eb965f364b44b5526d",
    LTO: "c44ecc673f2a320eed9607387a375b6a83f00496acb389351c0685226705fc71",
    CONTRACT: "307020a7841b87f57bd8f7b092e6234694ee3d7b85aee32242572dbc947d6bfd",
    BASELINE_ELF: "dc27a8a47f3274cc08fba71d5907c58b527a0b783ca3ea04bfca8f202f89c18e",
    FIRST_RED: "08d2339497562043cc22078b40b830a0b8579534dbc6e8181c2a5579fa766549",
    SEMANTIC: "3527f95aa7b418630a5d901353852eafaf1293804b0a183d4af84b580445aec0",
}


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path),
            "mode": f"0{path.stat().st_mode & 0o777:o}"}


def verify_inputs() -> dict[str, Any]:
    for path, expected in PINNED.items():
        require(path.is_file(), f"pinned replay input absent: {path}")
        require(sha(path) == expected,
                f"pinned replay input drift: {path}: {sha(path)}")
    require(TARGET.stat().st_mode & 0o222 == 0, "seed PRG is writable")
    require(ELF.stat().st_mode & 0o222 == 0, "seed ELF is writable")
    require(LTO.stat().st_mode & 0o222 == 0, "seed LTO object is writable")
    semantic = json.loads(SEMANTIC.read_text(encoding="utf-8"))
    for key, path in {
        "helper_source": C.H.HELPER,
        "runtime_source": C.H.RUNTIME,
        "phase_source": C.H.PHASE,
        "contract_header": C.H.HEADER,
    }.items():
        expected = semantic["inputs"][key]["sha256"]
        require(sha(path) == expected,
                f"source drift after semantic proof: {key}")
    return {path.relative_to(ROOT).as_posix(): bind(path)
            for path in PINNED}


def changed_sections(before: dict[str, dict[str, int]],
                     after: dict[str, dict[str, int]]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name in sorted(set(before) | set(after)):
        old = before.get(name, {}).get("bytes", 0)
        new = after.get(name, {}).get("bytes", 0)
        if old != new:
            rows[name] = {"link29_bytes": old, "replay_bytes": new,
                          "delta_bytes": new - old}
    return rows


def replay(out: Path) -> dict[str, Any]:
    require(not out.exists(), f"replay output already exists: {out}")
    inputs = verify_inputs()
    out.mkdir(parents=True)

    sections = P.section_table(ELF)
    baseline = P.section_table(BASELINE_ELF)
    e000_rows = {
        name: {"link29": baseline.get(name), "replay": sections.get(name)}
        for name in P.KERNAL_SECTIONS
    }
    require(all(row["link29"] == row["replay"]
                for row in e000_rows.values()),
            f"exact $E000 section geometry drift: {e000_rows}")
    e000_live = sum(sections[name]["bytes"] for name in P.KERNAL_SECTIONS)
    baseline_e000_live = sum(
        baseline[name]["bytes"] for name in P.KERNAL_SECTIONS)
    require(e000_live == baseline_e000_live,
            f"exact $E000 byte delta red: {e000_live - baseline_e000_live}")
    retained = C.retained_link29_seams_gate(ELF, BASELINE_ELF)

    slice_names = sorted({
        spec.split(":")[2]
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    })
    slices = {name: sections.get(name, {}).get("bytes", 0)
              for name in slice_names}
    baseline_slices = {name: baseline.get(name, {}).get("bytes", 0)
                       for name in slice_names}
    red_slices = {name: size for name, size in slices.items()
                  if size <= 0 or size > 1792}
    text = sections[".text"]
    baseline_text = baseline[".text"]
    bss = sections[".bss"]
    baseline_bss = baseline[".bss"]
    text_headroom = 0xB481 - text["address"] - text["bytes"]
    baseline_text_headroom = (
        0xB481 - baseline_text["address"] - baseline_text["bytes"])
    bss_headroom = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    baseline_bss_headroom = (
        P.FIXED_BANK0_BASE - baseline_bss["address"] - baseline_bss["bytes"])
    island = sections[".lisp65_resident_island"]["bytes"]
    baseline_island = baseline[".lisp65_resident_island"]["bytes"]
    annex = sections[".lisp65_resident_island_annex"]["bytes"]
    island_headroom = 2048 - island - annex
    e000_margin = P.KERNAL_WINDOW_BYTES - e000_live
    require(not red_slices and min(text_headroom, bss_headroom,
                                   island_headroom, e000_margin) >= 0,
            "capacity red before structural replay: "
            f"slices={red_slices} text={text_headroom} bss={bss_headroom} "
            f"island={island_headroom} e000={e000_margin}")

    inventory = P.final_section_inventory_gate(out, TARGET)
    lto = P.lto_partition_metadata_gate(out, TARGET)
    window = P.extract_provisional_kernal_window(out, TARGET)
    P.handoff_z_abi_gate(out, TARGET, "hot-refill-link29-seams-replay")
    ownership = P.pre_ownership_gate(
        out, TARGET, "hot-refill-link29-seams-replay")
    data_refs = P.profile_data_reference_gate(
        out, TARGET, "hot-refill-link29-seams-replay", ownership)
    P.fixed_facade_gate(out, TARGET, "hot-refill-link29-seams-replay")
    boot = P.overlay_pack_family(
        out, TARGET, CONTRACT, "boot", "hot-refill-link29-seams-replay")
    session = P.overlay_pack_family(
        out, TARGET, CONTRACT, "session", "hot-refill-link29-seams-replay")
    kernal = P.kernal_freedom_gate(out, TARGET)
    direct = C.direct_path_gate(ELF)

    boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
    session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
    old_boot = json.loads((C.BASELINE / "runtime-overlays-boot-final.json").read_text())
    old_session = json.loads(
        (C.BASELINE / "runtime-overlays-session-final.json").read_text())
    old_boot_slices = {row["id"]: row for row in old_boot["slices"]}
    new_boot_slices = {row["id"]: row for row in boot_manifest["slices"]}
    old_session_slices = {row["id"]: row for row in old_session["slices"]}
    new_session_slices = {row["id"]: row for row in session_manifest["slices"]}
    phase_deltas = {
        name: {"link29_bytes": baseline_slices[name],
               "replay_bytes": slices[name],
               "delta_bytes": slices[name] - baseline_slices[name]}
        for name in slice_names if slices[name] != baseline_slices[name]
    }
    for path in out.iterdir():
        if path.is_file(): path.chmod(0o444)
    report = {
        "format": "lisp65-c2-hot-refill-link29-seams-gate-replay-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-protected-seed-gate-replay-product-link-not-authorized",
        "execution_accounting": {
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "new_seed_links": 0,
            "new_product_links": 0,
            "gate_replays": 1
        },
        "pinned_inputs": inputs,
        "corrected_gate_definition": {
            "internal_window_symbols": (
                "same source algorithm, byte size and owned section; VMA is provenance"),
            "external_absolute_seams": (
                "facade vectors, handoff and any future absolute cross-domain seam "
                "remain address-pinned"),
            "retained_link29_seams": retained,
        },
        "capacity": {
            "bank0_text": {"link29_headroom_bytes": baseline_text_headroom,
                           "replay_headroom_bytes": text_headroom,
                           "delta_headroom_bytes": text_headroom
                               - baseline_text_headroom},
            "bank0_ordinary_bss": {
                "link29_headroom_bytes": baseline_bss_headroom,
                "replay_headroom_bytes": bss_headroom,
                "delta_headroom_bytes": bss_headroom - baseline_bss_headroom},
            "bank0_fixed_block": {"headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
                                  "delta_bytes": 0},
            "cpu_e000_window": {
                "link29_occupied_bytes": baseline_e000_live,
                "replay_occupied_bytes": e000_live,
                "hard_delta_bytes": e000_live - baseline_e000_live,
                "future_margin_bytes": e000_margin,
                "named_sections": e000_rows,
                "growth_policy": "closed-to-new-tenants"},
            "resident_island": {"link29_base_bytes": baseline_island,
                                "replay_base_bytes": island,
                                "annex_bytes": annex,
                                "headroom_bytes": island_headroom,
                                "delta_base_bytes": island - baseline_island},
            "runtime_overlay_slices": {
                "cap_bytes": 1792,
                "largest_section": max(slices, key=slices.get),
                "largest_bytes": max(slices.values()),
                "phase13": {"link29_bytes": baseline_slices[
                                  ".lisp65_rt_c2d_13"],
                            "replay_bytes": slices[".lisp65_rt_c2d_13"],
                            "headroom_bytes": 1792
                                - slices[".lisp65_rt_c2d_13"]},
                "changed_sections": phase_deltas,
                "over_cap_or_missing": red_slices},
            "runtime_overlay_bank": {
                "boot_bytes": boot_manifest["storage"]["size"],
                "boot_delta_vs_link29": boot_manifest["storage"]["size"]
                    - old_boot["storage"]["size"],
                "boot_headroom_bytes": 65536
                    - boot_manifest["storage"]["size"],
                "session_bytes": session_manifest["storage"]["size"],
                "session_delta_vs_link29": session_manifest["storage"]["size"]
                    - old_session["storage"]["size"],
                "session_headroom_bytes": 65536
                    - session_manifest["storage"]["size"],
                "packing_attribution": {
                    "boot_resident_island_installer": {
                        "slot": 8,
                        "link29_file_size": old_boot_slices[8]["file_size"],
                        "replay_file_size": new_boot_slices[8]["file_size"],
                        "delta_bytes": new_boot_slices[8]["file_size"]
                            - old_boot_slices[8]["file_size"],
                        "explanation": (
                            "The boot installer carries the enlarged Resident-Island "
                            "payload; its exact +1136 bytes explain the boot-image delta."),
                    },
                    "session_phase13": {
                        "slot": 12,
                        "link29_file_size": old_session_slices[12]["file_size"],
                        "replay_file_size": new_session_slices[12]["file_size"],
                        "raw_delta_bytes": new_session_slices[12]["file_size"]
                            - old_session_slices[12]["file_size"],
                        "packed_image_delta_bytes": session_manifest["storage"]["size"]
                            - old_session["storage"]["size"],
                        "explanation": (
                            "The -1655-byte phase-13 payload crosses pack alignment "
                            "boundaries and yields -1536 bytes in the packed session image."),
                    },
                    "catalog_and_record": {
                        "slot0_delta_bytes": new_session_slices[0]["file_size"]
                            - old_session_slices[0]["file_size"],
                        "slot1_delta_bytes": new_session_slices[1]["file_size"]
                            - old_session_slices[1]["file_size"],
                    },
                }},
            "bank5_mutable_plane": {"bytes": C.ROOT.joinpath(
                "build/c2.2/substitution/initial.c2d-v3.bin").stat().st_size,
                "delta_bytes": 0},
            "attic_immutable_shelf": {"bytes": C.ROOT.joinpath(
                "build/c2.2/substitution/product-shelf-v4-direct.bin").stat().st_size,
                "delta_bytes": 0},
            "installer_slice": {"status": "outside-C2-closure-unmodified",
                                "delta_bytes": 0}
        },
        "section_deltas_vs_link29_seed": changed_sections(baseline, sections),
        "fresh_replayed_gates": {
            "section_inventory": inventory["status"],
            "lto_partition_and_relocations": lto["status"],
            "e000_exact_zero_delta": "passed",
            "retained_link29_seams": retained["status"],
            "handoff_z_and_io": "passed",
            "pre_ownership": "passed",
            "profile_data_references": "passed",
            "profile_data_relocation_count": data_refs[
                "matched_relocation_count"],
            "fixed_facade_and_external_vector_vmas": "passed",
            "runtime_family_pack": "passed",
            "kernal_freedom": "passed",
            "owned_control_flow_edges": kernal[
                "control_flow_ownership"]["direct_window_edges"],
            "one_materializer_linked_path": direct
        },
        "provisional_window": window,
        "evidence_artifacts": {
            path.name: bind(path)
            for path in sorted(out.iterdir()) if path.is_file()
        },
        "claim_limit": (
            "Pure gate replay over one protected product-shaped seed. No compiler, "
            "linker or product-closure link ran. Hardware, latency, promotion and "
            "performance remain not-run."),
        "next_gate": (
            "Report the complete replay and capacity deltas for review. A successor "
            "product link remains separately blocked."),
    }
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def augment_recorded(value: dict[str, Any], out: Path) -> dict[str, Any]:
    """Bind already-produced replay evidence without executing a gate again."""
    old_boot = json.loads((C.BASELINE / "runtime-overlays-boot-final.json").read_text())
    old_session = json.loads(
        (C.BASELINE / "runtime-overlays-session-final.json").read_text())
    boot_path = out / "runtime-overlays-boot-hot-refill-link29-seams-replay.json"
    session_path = out / "runtime-overlays-session-hot-refill-link29-seams-replay.json"
    boot = json.loads(boot_path.read_text())
    session = json.loads(session_path.read_text())
    old_boot_slices = {row["id"]: row for row in old_boot["slices"]}
    new_boot_slices = {row["id"]: row for row in boot["slices"]}
    old_session_slices = {row["id"]: row for row in old_session["slices"]}
    new_session_slices = {row["id"]: row for row in session["slices"]}
    value["capacity"]["runtime_overlay_bank"]["packing_attribution"] = {
        "boot_resident_island_installer": {
            "slot": 8,
            "link29_file_size": old_boot_slices[8]["file_size"],
            "replay_file_size": new_boot_slices[8]["file_size"],
            "delta_bytes": new_boot_slices[8]["file_size"]
                - old_boot_slices[8]["file_size"],
            "explanation": (
                "The boot installer carries the enlarged Resident-Island payload; "
                "its exact +1136 bytes explain the boot-image delta."),
        },
        "session_phase13": {
            "slot": 12,
            "link29_file_size": old_session_slices[12]["file_size"],
            "replay_file_size": new_session_slices[12]["file_size"],
            "raw_delta_bytes": new_session_slices[12]["file_size"]
                - old_session_slices[12]["file_size"],
            "packed_image_delta_bytes": session["storage"]["size"]
                - old_session["storage"]["size"],
            "explanation": (
                "The -1655-byte phase-13 payload crosses pack alignment boundaries "
                "and yields -1536 bytes in the packed session image."),
        },
        "catalog_and_record": {
            "slot0_delta_bytes": new_session_slices[0]["file_size"]
                - old_session_slices[0]["file_size"],
            "slot1_delta_bytes": new_session_slices[1]["file_size"]
                - old_session_slices[1]["file_size"],
        },
    }
    value["evidence_artifacts"] = {
        path.name: bind(path) for path in sorted(out.iterdir()) if path.is_file()
    }
    return value


def verify_recorded(out: Path) -> dict[str, Any]:
    verify_inputs()
    require(RECEIPT.is_file(), "replay receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(RECEIPT.read_bytes() == canonical(value),
            "replay receipt is not canonical")
    require(value.get("status")
            == "passed-protected-seed-gate-replay-product-link-not-authorized",
            "replay receipt is not green")
    for row in value.get("evidence_artifacts", {}).values():
        path = ROOT / row["path"]
        require(path.is_file() and sha(path) == row["sha256"]
                and path.stat().st_size == row["bytes"],
                f"replay evidence drift: {path}")
    require(value["execution_accounting"] == {
        "compiler_invocations": 0, "gate_replays": 1,
        "linker_invocations": 0, "new_product_links": 0,
        "new_seed_links": 0}, "replay execution accounting drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest",
                                            "finalize"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            verify_inputs()
            print("c2-hot-refill-link29-seams-replay: SELFTEST PASS inputs=7")
            return 0
        if args.action == "finalize":
            require(RECEIPT.is_file(), "unfinalized replay receipt absent")
            value = json.loads(RECEIPT.read_text(encoding="utf-8"))
            value = augment_recorded(value, args.out.resolve())
            os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(canonical(value))
            os.chmod(RECEIPT, 0o444)
            print("c2-hot-refill-link29-seams-replay: FINALIZED existing-gates=1 "
                  "compiler=0 linker=0 product-links=0")
            return 0
        if args.action == "check":
            value = verify_recorded(args.out.resolve())
        else:
            value = replay(args.out.resolve())
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            verb = "PASS"
        cap = value["capacity"]
        print("c2-hot-refill-link29-seams-replay: " + verb
              + f" e000-delta={cap['cpu_e000_window']['hard_delta_bytes']}"
              + f" island-headroom={cap['resident_island']['headroom_bytes']}"
              + f" phase13={cap['runtime_overlay_slices']['phase13']['replay_bytes']}"
              + " compiler=0 linker=0 product-links=0")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, ReplayError) as error:
        print(f"c2-hot-refill-link29-seams-replay: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
