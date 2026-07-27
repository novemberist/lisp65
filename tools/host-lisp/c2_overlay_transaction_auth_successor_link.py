#!/usr/bin/env python3
"""Build and bind the authorized transaction-auth successor product link."""

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
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / "build/c2.2/substitution/product-link-31-transaction-auth"
BASELINE = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-island-contract-probe-receipt.json")
CAPACITY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-island-capacity-placement-probe-receipt.json")
LINK30_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link30-hot-refill-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link31-transaction-auth-structural-receipt.json")
EXPECTED = {
    HOST_RECEIPT: "09c75d9f0ecaf2f4b8b301d7175febb57c27d6bcadc8ee9fe46053a678eada46",
    CAPACITY_RECEIPT: "e3cabacb77a9a93c13650f2636f3f4e32a11398ea688f15de2d400365074d1b9",
    LINK30_RECEIPT: "e0211015bb33fcd795cbd76edeea73143d1db6c069c1de965a62125e8108f022",
    D.RECEIPT: "64e42be6679e0610e3242ff8c22c25fdf0bd2af90e753f1b81f385d47b06b5ac",
}
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
)


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
                f"successor prerequisite drift: {path}")
    host = json.loads(HOST_RECEIPT.read_text(encoding="utf-8"))
    capacity = json.loads(CAPACITY_RECEIPT.read_text(encoding="utf-8"))
    link30 = json.loads(LINK30_RECEIPT.read_text(encoding="utf-8"))
    require(host.get("status")
            == "passed-host-source-mutations-capacity-not-run",
            "host/source prerequisite is not green")
    require(capacity.get("status")
            == "passed-island-noinline-capacity-placement-probe-only",
            "capacity prerequisite is not green")
    require(link30.get("status")
            == "passed-new-product-identity-hardware-not-run",
            "Link-30 rollback line is not structurally green")
    return {
        "host_and_mutations": bind(HOST_RECEIPT),
        "capacity_and_placement": bind(CAPACITY_RECEIPT),
        "link30_rollback_line": bind(LINK30_RECEIPT),
        "direct_entry_contract": bind(D.RECEIPT),
    }


def geometry(elf: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    current = P.section_table(elf)
    baseline_elf = BASELINE / "lisp65-c2-substitution-linked.prg.elf"
    baseline = P.section_table(baseline_elf)
    e000_rows = {
        name: {"link30": baseline.get(name), "link31": current.get(name)}
        for name in P.KERNAL_SECTIONS
    }
    require(all(row["link30"] == row["link31"]
                for row in e000_rows.values()),
            f"FIRST RED: successor E000 section geometry drift: {e000_rows}")
    old_e000 = sum(baseline[name]["bytes"] for name in P.KERNAL_SECTIONS)
    new_e000 = sum(current[name]["bytes"] for name in P.KERNAL_SECTIONS)
    require(old_e000 == new_e000 and P.KERNAL_WINDOW_BYTES - new_e000 == 386,
            f"FIRST RED: successor E000 delta/margin: {new_e000-old_e000}/"
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
            "FIRST RED: successor resident capacity: "
            f"slices={over} text={text_room} bss={bss_room} "
            f"island={island_room}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads((out / "runtime-overlays-session-final.json").read_text())
    capacity = {
        "bank0_text_headroom_bytes": text_room,
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
            "over_cap_or_missing": over,
        },
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"],
        },
        "e000": {
            "link30_occupied_bytes": old_e000,
            "link31_occupied_bytes": new_e000,
            "delta_bytes": new_e000 - old_e000,
            "future_margin_bytes": P.KERNAL_WINDOW_BYTES - new_e000,
            "named_sections": e000_rows,
            "growth_policy": "closed-to-new-tenants",
        },
    }
    return capacity, current


def build(out: Path) -> dict[str, Any]:
    prereq = prerequisites()
    require(not out.exists(), f"successor output already exists: {out}")
    extra = (
        "mode=link31-overlay-transaction-auth-successor",
        "feature_defines=" + ",".join(FEATURES),
        "transaction_auth_host_receipt_sha256=" + sha(HOST_RECEIPT),
        "transaction_auth_capacity_receipt_sha256=" + sha(CAPACITY_RECEIPT),
        "link30_rollback_receipt_sha256=" + sha(LINK30_RECEIPT),
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
            "FIRST RED: generic product closure is not green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "FIRST RED: 34-byte publish-last binding is not green")
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
        "format": "lisp65-c2-product-link31-transaction-auth-structural-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-new-product-identity-hardware-not-run",
        "link_number": 31,
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
            "retained_link30_seams": retained,
        },
        "capacity": capacity,
        "fresh_evidence_reports": evidence,
        "section_count": len(sections),
        "claim_limit": (
            "Fresh single product-closure Link 31 with one prerequisite Island "
            "seed, complete structural/capacity replay and 34-byte publish-last "
            "binding. Hardware execution, latency, promotion and release remain "
            "not-run."
        ),
        "next_gate": (
            "Run the owner-authorized receipt-less hardware pre-smoke: boot to "
            "REPL, cold definition-first-call and warm second-call."
        ),
    }
    (out / "transaction-auth-successor-link.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "successor receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-new-product-identity-hardware-not-run"
            and value.get("link_number") == 31,
            "successor receipt status drift")
    for row in value["product_identity"].values():
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"successor identity drift: {path}")
    require(value["post_link_identity"]["declared_mutable_product_bytes"] == 34,
            "publish-last domain drift")
    root = DEFAULT_OUT
    bad_modes = [
        str(path.relative_to(root)) or "."
        for path in (root, *root.rglob("*"))
        if ((path.is_file() and path.stat().st_mode & 0o777 != 0o444)
            or (path.is_dir() and path.stat().st_mode & 0o777 != 0o555))
    ]
    require(not bad_modes, f"successor protection drift: {bad_modes}")
    return value


def protect(out: Path) -> None:
    require(out == DEFAULT_OUT and out.is_dir(),
            "protection target is not the Link-31 directory")
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
            print("c2-overlay-transaction-auth-successor: SELFTEST PASS prerequisites=4")
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
                        "refusing to overwrite divergent successor receipt")
            else:
                RECEIPT.write_bytes(canonical(value))
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        cap = value["capacity"]
        print("c2-overlay-transaction-auth-successor: " + verb
              + f" product={value['product_identity']['product']['sha256'][:16]}"
              + f" text={cap['bank0_text_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss_headroom_bytes']}"
              + f" island={cap['resident_island']['headroom_bytes']}"
              + f" e000-delta={cap['e000']['delta_bytes']}"
              + " hardware=not-run")
        return 0
    except (LinkError, OSError, ValueError, KeyError, RuntimeError,
            json.JSONDecodeError) as exc:
        print(f"c2-overlay-transaction-auth-successor: FAIL {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
