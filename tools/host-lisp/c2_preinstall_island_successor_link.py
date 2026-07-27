#!/usr/bin/env python3
"""Build and bind the authorized pre-install-Island successor product link."""

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
import c2_hot_refill_direct_entry_contract as D  # noqa: E402
import c2_overlay_transaction_auth_successor_link as L31  # noqa: E402
import c2_preinstall_island_guard as GUARD  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/product-link-32-preinstall-island-guard")
BASELINE = ROOT / "build/c2.2/substitution/product-link-31-transaction-auth"
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-contract-probe-receipt.json")
CAPACITY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-capacity-placement-probe-receipt.json")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-capacity-first-red-receipt.json")
LINK31_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link31-transaction-auth-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link32-preinstall-island-guard-structural-receipt.json")
EXPECTED = {
    HOST_RECEIPT: "c97210eb09387bdd0fc7d22bab3e7d1c32b7c0a30e48e5d1e300bbe36b9831f1",
    CAPACITY_RECEIPT: "9a11d9e5ee2661999da08c4e0877c9b5dcd2f2053b2b8604e26bf5add31e3f93",
    FIRST_RED_RECEIPT: "b1d2d8f1591b834f5ddd77f922e2062c277c5014351253f66331cf1e2ee54e98",
    LINK31_RECEIPT: "e87310d2edc321f788a63a92c977fd50d9703590078cdc01f18658f60892d339",
    D.RECEIPT: "64e42be6679e0610e3242ff8c22c25fdf0bd2af90e753f1b81f385d47b06b5ac",
}
FEATURES = L31.FEATURES


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def prerequisites() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"Link-32 prerequisite drift: {path}")
    host = json.loads(HOST_RECEIPT.read_text(encoding="utf-8"))
    capacity = json.loads(CAPACITY_RECEIPT.read_text(encoding="utf-8"))
    link31 = json.loads(LINK31_RECEIPT.read_text(encoding="utf-8"))
    require(host.get("status")
            == "passed-host-source-mutations-capacity-not-run",
            "pre-install host/lifecycle prerequisite is not green")
    require(capacity.get("status")
            == "passed-preinstall-Island-capacity-placement-static-probe-only",
            "pre-install capacity/static prerequisite is not green")
    require(link31.get("status")
            == "passed-new-product-identity-hardware-not-run",
            "Link-31 rollback line is not structurally green")
    return {
        "host_lifecycle_and_mutations": bind(HOST_RECEIPT),
        "capacity_placement_and_static_seed": bind(CAPACITY_RECEIPT),
        "capacity_first_red_history": bind(FIRST_RED_RECEIPT),
        "link31_rollback_line": bind(LINK31_RECEIPT),
        "direct_entry_contract": bind(D.RECEIPT),
    }


def geometry(elf: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    current = P.section_table(elf)
    baseline_elf = BASELINE / "lisp65-c2-substitution-linked.prg.elf"
    baseline = P.section_table(baseline_elf)
    e000_rows = {
        name: {"link31": baseline.get(name), "link32": current.get(name)}
        for name in P.KERNAL_SECTIONS
    }
    require(all(row["link31"] == row["link32"]
                for row in e000_rows.values()),
            f"FIRST RED: Link-32 E000 section geometry drift: {e000_rows}")
    old_e000 = sum(baseline[name]["bytes"] for name in P.KERNAL_SECTIONS)
    new_e000 = sum(current[name]["bytes"] for name in P.KERNAL_SECTIONS)
    require(old_e000 == new_e000 and P.KERNAL_WINDOW_BYTES - new_e000 == 386,
            f"FIRST RED: Link-32 E000 delta/margin: {new_e000-old_e000}/"
            f"{P.KERNAL_WINDOW_BYTES-new_e000}")

    slice_names = sorted({spec.split(":")[2]
                          for spec in P.BOOT_SLICE_SPECS
                          + P.SESSION_SLICE_SPECS})
    slices = {name: current.get(name, {}).get("bytes", 0)
              for name in slice_names}
    over = {name: value for name, value in slices.items()
            if value <= 0 or value > 1792}
    text = current[".text"]
    bss = current[".bss"]
    island = current[".lisp65_resident_island"]["bytes"]
    annex = current[".lisp65_resident_island_annex"]["bytes"]
    text_room = 0xB481 - text["address"] - text["bytes"]
    bss_room = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    island_room = 2048 - island - annex
    require(not over and text_room >= 0 and bss_room == 19
            and island_room >= 0,
            "FIRST RED: Link-32 resident capacity: "
            f"slices={over} text={text_room} bss={bss_room} "
            f"island={island_room}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (out / "runtime-overlays-session-final.json").read_text())
    capacity = {
        "bank0_text_headroom_bytes": text_room,
        "bank0_text_growth_policy": (
            "closed-to-resident-growth; every future resident debit, including "
            "one byte, is a triage event; Boot-family lifetime substitution is "
            "the pre-named first candidate"),
        "bank0_ordinary_bss_headroom_bytes": bss_room,
        "bank0_fixed_block_headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
        "resident_island": {
            "base_bytes": island,
            "annex_bytes": annex,
            "headroom_bytes": island_room,
        },
        "runtime_overlay_slices": {
            "cap_bytes": 1792,
            "largest_section": max(slices, key=slices.get),
            "largest_bytes": max(slices.values()),
            "minimum_headroom_bytes": 1792 - max(slices.values()),
            "over_cap_or_missing": over,
        },
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"],
        },
        "e000": {
            "link31_occupied_bytes": old_e000,
            "link32_occupied_bytes": new_e000,
            "delta_bytes": new_e000 - old_e000,
            "future_margin_bytes": P.KERNAL_WINDOW_BYTES - new_e000,
            "named_sections": e000_rows,
            "growth_policy": "closed-to-new-tenants",
        },
    }
    return capacity, current


def build(out: Path) -> dict[str, Any]:
    prereq = prerequisites()
    require(not out.exists(), f"Link-32 output already exists: {out}")
    extra = (
        "mode=link32-preinstall-island-guard-successor",
        "feature_defines=" + ",".join(FEATURES),
        "preinstall_guard_host_receipt_sha256=" + sha(HOST_RECEIPT),
        "preinstall_guard_capacity_receipt_sha256=" + sha(CAPACITY_RECEIPT),
        "link31_rollback_receipt_sha256=" + sha(LINK31_RECEIPT),
        "green_inheritance=none",
    )
    P.single_link(
        out, probe_definitions=FEATURES,
        direct_entry_receipt=D.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=extra)
    product = out / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads((out / "product-substitution-link.json").read_text())
    total = json.loads((out / "total-publish-last-domain.json").read_text())
    require(structure.get("status") == "passed"
            and structure.get("product_closure_link_count") == 1,
            "FIRST RED: generic Link-32 product closure is not green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "FIRST RED: Link-32 34-byte publish-last binding is not green")
    capacity, sections = geometry(elf, out)

    symbols = H.symbol_table(elf)
    symbol_sections = H.symbol_sections(elf)
    island_functions = (
        "rtov_transaction_context",
        "vm_runtime_overlay_transaction_begin",
        "vm_runtime_overlay_transaction_end",
    )
    require(all(symbol_sections.get(name) == ".lisp65_resident_island"
                and 0x1800 <= symbols.get(name, {}).get("address", 0) < 0x2000
                for name in island_functions),
            "FIRST RED: transaction control escaped the resident Island")
    product_functions = ("c2_product_install", "c2_product_append_staged")
    require(all(name in symbols for name in product_functions),
            "FIRST RED: noinline product transaction entrypoint absent")
    forbidden_state = (
        "rtov_transaction_payload_off", "rtov_transaction_image_limit",
        "rtov_transaction_count", "rtov_transaction_active",
        "rtov_transaction_trusted",
    )
    require(not any(name in symbols for name in forbidden_state),
            "FIRST RED: dedicated transaction BSS survived")
    preinstall_gate = GUARD.static_elf_gate(elf)
    direct = H.direct_path_gate(elf)
    retained = H.retained_link29_seams_gate(
        elf, BASELINE / "lisp65-c2-substitution-linked.prg.elf")
    profile = (out / "resolved-profile.txt").read_text(encoding="utf-8")
    require("feature_defines=" + ",".join(FEATURES) in profile,
            "FIRST RED: resolved feature profile drift")

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
        "format": (
            "lisp65-c2-product-link32-preinstall-island-guard-"
            "structural-receipt-v1"),
        "recorded_on": "2026-07-20",
        "status": "passed-new-product-identity-hardware-not-run",
        "link_number": 32,
        "inheritance": "none; every structural and capacity gate ran freshly",
        "execution_accounting": {
            "resident_island_seed_links": 1,
            "product_closure_links": 1,
            "hardware_runs": 0,
        },
        "prerequisites": prereq,
        "product_identity": {
            "product": bind(product),
            "elf": bind(elf),
            "resolved_profile": bind(out / "resolved-profile.txt"),
        },
        "post_link_identity": {
            "declared_mutable_product_bytes": total["declared_domain_bytes"],
            "declared_domains": total["declared_domains"],
            "actual_changed_bytes": total["actual_changed_bytes"],
            "status": total["status"],
        },
        "preinstallation_Island": preinstall_gate,
        "transaction_auth": {
            "feature_defines": list(FEATURES),
            "island_functions": {
                name: {**symbols[name], "section": symbol_sections.get(name)}
                for name in island_functions
            },
            "single_copy_product_entrypoints": {
                name: {**symbols[name], "section": symbol_sections.get(name)}
                for name in product_functions
            },
            "dedicated_transaction_bss_symbols": 0,
        },
        "hot_refill": {
            "direct_shared_materializer": direct,
            "retained_link31_seams": retained,
        },
        "capacity": capacity,
        "fresh_evidence_reports": evidence,
        "section_count": len(sections),
        "claim_limit": (
            "Fresh single product-closure Link 32 with one prerequisite Island "
            "seed, complete structural/capacity replay, final-ELF pre-install "
            "Island closure proof and 34-byte publish-last binding. Hardware "
            "execution, latency, promotion and release remain not-run."),
        "next_gate": (
            "Run the owner-authorized receipt-less hardware pre-smoke: boot to "
            "REPL, cold definition-first-call and warm second-call."),
    }
    (out / "preinstall-island-successor-link.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-32 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-new-product-identity-hardware-not-run"
            and value.get("link_number") == 32,
            "Link-32 receipt status drift")
    require(value.get("preinstallation_Island", {}).get("status")
            == "passed-static-preinstallation-Island-gate",
            "Link-32 final-ELF Island gate drift")
    for row in value["product_identity"].values():
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"Link-32 identity drift: {path}")
    require(value["post_link_identity"]["declared_mutable_product_bytes"] == 34,
            "Link-32 publish-last domain drift")
    root = DEFAULT_OUT
    bad_modes = [
        str(path.relative_to(root)) or "."
        for path in (root, *root.rglob("*"))
        if ((path.is_file() and path.stat().st_mode & 0o777 != 0o444)
            or (path.is_dir() and path.stat().st_mode & 0o777 != 0o555))
    ]
    require(not bad_modes, f"Link-32 protection drift: {bad_modes}")
    return value


def protect(out: Path) -> None:
    require(out == DEFAULT_OUT and out.is_dir(),
            "protection target is not the Link-32 directory")
    for path in out.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    for path in sorted(
            (item for item in out.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555)
    os.chmod(out, 0o555)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "protect", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            prerequisites()
            GUARD.closure_model_selftest()
            print("c2-preinstall-island-successor: SELFTEST PASS prerequisites=5 mutations=4")
            return 0
        if args.action == "protect":
            protect(args.out.resolve())
            value = check()
            verb = "PROTECTED"
        elif args.action == "check":
            value = check()
            verb = "PASS"
        else:
            value = build(args.out.resolve())
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == canonical(value),
                        "refusing to overwrite divergent Link-32 receipt")
            else:
                RECEIPT.write_bytes(canonical(value))
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        cap = value["capacity"]
        print("c2-preinstall-island-successor: " + verb
              + f" product={value['product_identity']['product']['sha256'][:16]}"
              + f" text={cap['bank0_text_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss_headroom_bytes']}"
              + f" island={cap['resident_island']['headroom_bytes']}"
              + f" slice={cap['runtime_overlay_slices']['minimum_headroom_bytes']}"
              + f" e000-delta={cap['e000']['delta_bytes']}"
              + " hardware=not-run")
        return 0
    except (LinkError, GUARD.GateError, OSError, ValueError, KeyError,
            RuntimeError, json.JSONDecodeError) as exc:
        print(f"c2-preinstall-island-successor: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
