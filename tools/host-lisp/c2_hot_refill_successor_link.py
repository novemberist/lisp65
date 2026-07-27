#!/usr/bin/env python3
"""Build and pin the one owner-authorized hot-refill successor product link."""

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
import c2_hot_refill_direct_entry_contract as D  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
SEMANTIC = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-contract-probe-receipt.json")
REPLAY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-gate-replay-receipt.json")
BASELINE_ELF = ROOT / (
    "build/c2.2/substitution/product-link-29-direct-entry-encoding/"
    "lisp65-c2-substitution-linked.prg.elf")
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
PRODUCT_SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link30-hot-refill-structural-receipt.json")
FEATURE = "LISP65_C2_DIRECT_HOT_REFILL"
EXPECTED = {
    SEMANTIC: "3527f95aa7b418630a5d901353852eafaf1293804b0a183d4af84b580445aec0",
    REPLAY: "4d86035adee0502ece4a924b11aea08c19cdc2c712eb75fd4d4ef8a778c53d01",
    D.RECEIPT: "64e42be6679e0610e3242ff8c22c25fdf0bd2af90e753f1b81f385d47b06b5ac",
}


class SuccessorError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SuccessorError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def verify_prerequisites() -> None:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"hot-refill prerequisite drift: {path}")
    semantic = json.loads(SEMANTIC.read_text())
    replay = json.loads(REPLAY.read_text())
    direct = json.loads(D.RECEIPT.read_text())
    require(semantic["status"]
            == "passed-non-product-contract-stage-and-semantic-probe",
            "semantic prerequisite not green")
    require(replay["status"]
            == "passed-protected-seed-gate-replay-product-link-not-authorized",
            "gate replay prerequisite not green")
    require(direct["status"]
            == "passed-fresh-hot-refill-contract-and-cross-parity-probe-only",
            "fresh direct-entry prerequisite not green")


def e000_gate(elf: Path) -> dict[str, Any]:
    current = P.section_table(elf)
    baseline = P.section_table(BASELINE_ELF)
    rows = {
        name: {"link29": baseline.get(name), "link30": current.get(name)}
        for name in P.KERNAL_SECTIONS
    }
    require(all(row["link29"] == row["link30"] for row in rows.values()),
            f"FIRST RED: successor $E000 section geometry drift: {rows}")
    before = sum(baseline[name]["bytes"] for name in P.KERNAL_SECTIONS)
    after = sum(current[name]["bytes"] for name in P.KERNAL_SECTIONS)
    require(after == before, f"FIRST RED: successor $E000 delta {after-before}")
    return {"status": "passed-exact-zero-delta", "link29_bytes": before,
            "link30_bytes": after, "delta_bytes": after - before,
            "future_margin_bytes": P.KERNAL_WINDOW_BYTES - after,
            "named_sections": rows}


def capacity(out: Path, elf: Path) -> dict[str, Any]:
    sections = P.section_table(elf)
    baseline = P.section_table(BASELINE_ELF)
    slices = sorted({spec.split(":")[2]
                     for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS})
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0) for name in slices}
    over = {name: size for name, size in slice_sizes.items()
            if size <= 0 or size > 1792}
    text = sections[".text"]; bss = sections[".bss"]
    old_text = baseline[".text"]; old_bss = baseline[".bss"]
    text_room = 0xB481 - text["address"] - text["bytes"]
    old_text_room = 0xB481 - old_text["address"] - old_text["bytes"]
    bss_room = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    old_bss_room = P.FIXED_BANK0_BASE - old_bss["address"] - old_bss["bytes"]
    island = sections[".lisp65_resident_island"]["bytes"]
    annex = sections[".lisp65_resident_island_annex"]["bytes"]
    island_room = 2048 - island - annex
    require(not over and min(text_room, bss_room, island_room) >= 0,
            f"FIRST RED: successor capacity slices={over} text={text_room} "
            f"bss={bss_room} island={island_room}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads((out / "runtime-overlays-session-final.json").read_text())
    return {
        "bank0_text": {"link29_headroom_bytes": old_text_room,
                       "link30_headroom_bytes": text_room,
                       "delta_headroom_bytes": text_room - old_text_room},
        "bank0_ordinary_bss": {"link29_headroom_bytes": old_bss_room,
                               "link30_headroom_bytes": bss_room,
                               "delta_headroom_bytes": bss_room - old_bss_room},
        "bank0_fixed_block": {"headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
                              "delta_bytes": 0},
        "resident_island": {"base_bytes": island, "annex_bytes": annex,
                            "headroom_bytes": island_room},
        "runtime_overlay_slices": {
            "cap_bytes": 1792,
            "largest_section": max(slice_sizes, key=slice_sizes.get),
            "largest_bytes": max(slice_sizes.values()),
            "phase13_bytes": slice_sizes[".lisp65_rt_c2d_13"],
            "phase13_headroom_bytes": 1792
                - slice_sizes[".lisp65_rt_c2d_13"],
            "over_cap_or_missing": over},
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"]},
        "bank5_mutable_plane": {
            "bytes": INITIAL_C2D.stat().st_size,
            "headroom_bytes": 65536 - INITIAL_C2D.stat().st_size},
        "attic_immutable_shelf": {
            "bytes": PRODUCT_SHELF.stat().st_size},
        "installer_slice": {"status": "outside-C2-closure-unmodified",
                            "delta_bytes": 0},
    }


def build(out: Path) -> dict[str, Any]:
    verify_prerequisites()
    require(not out.exists(), f"successor output already exists: {out}")
    extra = (
        "mode=link30-hot-refill-successor",
        "hot_refill_feature_define=" + FEATURE,
        "hot_refill_semantic_receipt_sha256=" + sha(SEMANTIC),
        "hot_refill_gate_replay_receipt_sha256=" + sha(REPLAY),
        "hot_refill_direct_entry_receipt_sha256=" + sha(D.RECEIPT),
        "green_inheritance=none",
    )
    P.single_link(
        out, probe_definitions=(FEATURE,), direct_entry_receipt=D.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=extra)
    product = out / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads((out / "product-substitution-link.json").read_text())
    total = json.loads((out / "total-publish-last-domain.json").read_text())
    require(structure["status"] == "passed"
            and structure["product_closure_link_count"] == 1,
            "successor generic structural closure is not green")
    require(total["status"] == "passed"
            and total["declared_domain_bytes"] == 34,
            "34-byte post-link domain is not green")
    window = e000_gate(elf)
    retained = C.retained_link29_seams_gate(elf, BASELINE_ELF)
    direct = C.direct_path_gate(elf)
    cap = capacity(out, elf)
    reports = (
        "product-substitution-link.json", "total-publish-last-domain.json",
        "kernal-window-publish-last.json", "runtime-verifier-publish-last.json",
        "runtime-family-total-identity.json", "one-truth-closure.json",
        "kernal-freedom-link.json", "fixed-host-facade-final.json",
        "pre-ownership-closure-final.json", "handoff-z-abi-final.json",
        "profile-data-reference-final.json", "substitution-balance.json",
    )
    evidence = {name: bind(out / name) for name in reports}
    value = {
        "format": "lisp65-c2-product-link30-hot-refill-structural-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-new-product-identity-hardware-not-run",
        "link_number": 30,
        "inheritance": "none; every structural and capacity gate ran freshly",
        "execution_accounting": {"resident_island_seed_links": 1,
                                 "product_closure_links": 1,
                                 "hardware_runs": 0},
        "prerequisites": {"semantic": bind(SEMANTIC), "gate_replay": bind(REPLAY),
                          "fresh_direct_entry": bind(D.RECEIPT)},
        "product_identity": {"product": bind(product), "elf": bind(elf),
                             "resolved_profile": bind(out / "resolved-profile.txt")},
        "post_link_identity": {
            "declared_mutable_product_bytes": total["declared_domain_bytes"],
            "declared_domains": total["declared_domains"],
            "actual_changed_bytes": total["actual_changed_bytes"],
            "mutation_outside_domain": total["negative_matrix"][
                "mutation-outside-34-byte-domain"],
            "mutated_kernal_crc_operand": total["negative_matrix"][
                "mutated-kernal-crc-operand"],
            "status": total["status"]},
        "hot_refill": {"feature_define": FEATURE,
                       "direct_shared_materializer": direct,
                       "retained_link29_seams": retained},
        "e000": window,
        "capacity": cap,
        "fresh_evidence_reports": evidence,
        "claim_limit": (
            "Fresh single product-closure Link 30 with one prerequisite Island seed, "
            "complete structural/capacity replay and 34-byte publish-last binding. "
            "Hardware execution, latency, promotion and release remain not-run."),
        "next_gate": (
            "The owner-authorized receipt-less hardware pre-smoke must measure "
            "banner-to-REPL boot, cold definition-first-call and warm second-call "
            "separately with claim limits in its value string."),
    }
    (out / "hot-refill-successor-link.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            verify_prerequisites()
            print("c2-hot-refill-successor-link: SELFTEST PASS prerequisites=3")
            return 0
        if args.action == "check":
            require(RECEIPT.is_file(), "successor receipt absent")
            value = json.loads(RECEIPT.read_text())
            require(RECEIPT.read_bytes() == canonical(value),
                    "successor receipt is not canonical")
            for row in value["product_identity"].values():
                path = ROOT / row["path"]
                require(path.is_file() and sha(path) == row["sha256"],
                        f"successor identity drift: {path}")
            require(value["status"]
                    == "passed-new-product-identity-hardware-not-run",
                    "successor receipt is not structurally green")
            verb = "PASS"
        else:
            value = build(args.out.resolve())
            data = canonical(value)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        print("c2-hot-refill-successor-link: " + verb
              + f" product={value['product_identity']['product']['sha256'][:16]}"
              + f" e000-delta={value['e000']['delta_bytes']}"
              + f" island={value['capacity']['resident_island']['headroom_bytes']}"
              + " hardware=not-run")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError,
            SuccessorError) as error:
        print(f"c2-hot-refill-successor-link: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
