#!/usr/bin/env python3
"""Run the one authorized pre-install Island capacity/static seed."""

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
import c2_overlay_transaction_auth_island_capacity as BASE  # noqa: E402
import c2_preinstall_island_guard as GUARD  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/preinstall-island-capacity-probe")
LINK31 = ROOT / "build/c2.2/substitution/product-link-31-transaction-auth"
LINK31_ELF = LINK31 / "resident-island-seed.prg.elf"
CONTRACT = ROOT / "config/c2-preinstall-island-guard-contract.json"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-capacity-placement-probe-receipt.json")


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


def _headrooms(elf: Path) -> dict[str, Any]:
    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    island = sections[".lisp65_resident_island"]
    annex = sections[".lisp65_resident_island_annex"]
    slice_names = sorted({
        spec.split(":")[2]
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    })
    slices = {name: sections.get(name, {}).get("bytes", 0)
              for name in slice_names}
    e000 = {name: sections.get(name) for name in P.KERNAL_SECTIONS}
    return {
        "bank0_text": 0xB481 - text["address"] - text["bytes"],
        "bank0_bss": P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "resident_island": 2048 - island["bytes"] - annex["bytes"],
        "runtime_slices": slices,
        "largest_runtime_slice": max(slices, key=slices.get),
        "largest_runtime_slice_bytes": max(slices.values()),
        "e000": e000,
    }


def run_probe(out: Path) -> dict[str, Any]:
    require(CONTRACT_RECEIPT.is_file(), "host/lifecycle receipt absent")
    host = json.loads(CONTRACT_RECEIPT.read_text(encoding="utf-8"))
    require(host.get("status")
            == "passed-host-source-mutations-capacity-not-run",
            "host/lifecycle receipt is not green")
    require(LINK31_ELF.is_file(), "protected Link-31 seed baseline absent")
    authorization = json.loads(CONTRACT.read_text(encoding="utf-8"))
    limits = authorization["capacity_limits"]

    BASE.CONTRACT_RECEIPT = CONTRACT_RECEIPT
    report = BASE.run_probe(out)
    seed_elf = Path(report["identity"]["seed_elf"]["path"])
    if not seed_elf.is_absolute():
        seed_elf = ROOT / seed_elf
    before = _headrooms(LINK31_ELF)
    after = _headrooms(seed_elf)

    require(after["bank0_text"] >= limits["bank0_text_headroom_min_bytes"],
            f"FIRST RED: Bank-0 text headroom {after['bank0_text']}")
    require(after["bank0_bss"] == limits["bank0_bss_headroom_bytes"],
            f"FIRST RED: Bank-0 BSS headroom {after['bank0_bss']}")
    require(after["resident_island"] >= 0,
            f"FIRST RED: resident Island headroom {after['resident_island']}")
    require(after["largest_runtime_slice_bytes"] <= 1792,
            "FIRST RED: runtime slice exceeds 1792 bytes")
    require(all(after["e000"].get(name) == before["e000"].get(name)
                for name in P.KERNAL_SECTIONS),
            "FIRST RED: closed E000 section identity or placement drift")

    static_gate = GUARD.static_elf_gate(seed_elf)
    slice_deltas = {
        name: {
            "link31_bytes": before["runtime_slices"][name],
            "probe_bytes": after["runtime_slices"][name],
            "delta_bytes": (after["runtime_slices"][name]
                            - before["runtime_slices"][name]),
            "probe_headroom_bytes": 1792 - after["runtime_slices"][name],
        }
        for name in sorted(after["runtime_slices"])
        if after["runtime_slices"][name] != before["runtime_slices"][name]
    }
    report["format"] = (
        "lisp65-c2-preinstall-island-guard-capacity-placement-probe-v1")
    report["status"] = (
        "passed-preinstall-Island-capacity-placement-static-probe-only")
    report["identity"]["preinstall_guard_contract"] = bind(CONTRACT)
    report["identity"]["preinstall_guard_host_receipt"] = bind(
        CONTRACT_RECEIPT)
    report["identity"]["link31_seed_baseline"] = bind(LINK31_ELF)
    report["capacity"]["against_link31"] = {
        "bank0_text": {
            "link31_headroom_bytes": before["bank0_text"],
            "probe_headroom_bytes": after["bank0_text"],
            "delta_headroom_bytes": after["bank0_text"] - before["bank0_text"],
        },
        "bank0_ordinary_bss": {
            "link31_headroom_bytes": before["bank0_bss"],
            "probe_headroom_bytes": after["bank0_bss"],
            "delta_headroom_bytes": after["bank0_bss"] - before["bank0_bss"],
        },
        "resident_island": {
            "link31_headroom_bytes": before["resident_island"],
            "probe_headroom_bytes": after["resident_island"],
            "delta_headroom_bytes": (
                after["resident_island"] - before["resident_island"]),
        },
        "runtime_overlay_slices": {
            "cap_bytes": 1792,
            "link31_largest_section": before["largest_runtime_slice"],
            "link31_largest_bytes": before["largest_runtime_slice_bytes"],
            "probe_largest_section": after["largest_runtime_slice"],
            "probe_largest_bytes": after["largest_runtime_slice_bytes"],
            "probe_minimum_headroom_bytes": (
                1792 - after["largest_runtime_slice_bytes"]),
            "changed_sections": slice_deltas,
        },
        "cpu_e000_window": {
            "required_delta_bytes": 0,
            "actual_delta_bytes": 0,
            "all_named_sections_identical": True,
            "future_margin_bytes": 386,
            "growth_policy": "closed-to-new-tenants",
        },
    }
    report["fresh_structural_gates"]["preinstallation_Island"] = static_gate
    report["scope"]["product_closure_links"] = 0
    report["scope"]["hardware_execution"] = "prohibited"
    report["claim_limit"] = (
        "One owner-authorized product-shaped seed for capacity, placement and "
        "static pre-installation Island structure only. No product closure link, "
        "product SHA, hardware, latency, promotion or release claim.")
    report["next_gate"] = (
        "Stop for review of exact deltas. A successor product link and hardware "
        "presmoke remain separately blocked.")
    path = out / "preinstall-island-capacity-probe.json"
    P.write(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def check_receipt() -> dict[str, Any]:
    require(RECEIPT.is_file(), "capacity/static receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status")
            == "passed-preinstall-Island-capacity-placement-static-probe-only",
            "capacity/static receipt status drift")
    require(value["scope"]["resident_island_seed_links"] == 1
            and value["scope"]["product_closure_links"] == 0
            and value["scope"]["hardware_execution"] == "prohibited",
            "capacity/static receipt scope drift")
    static = value["fresh_structural_gates"]["preinstallation_Island"]
    require(static["status"]
            == "passed-static-preinstallation-Island-gate"
            and not static["unguarded_or_data_references"],
            "static pre-installation gate drift")
    for item in value["identity"].values():
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = ROOT / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and sha(path) == item["sha256"],
                f"bound artifact drift: {item['path']}")
    return value


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
            data = canonical(value)
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent capacity receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        cap = value["capacity"]["against_link31"]
        print("c2-preinstall-island-capacity: " + verb
              + f" text={cap['bank0_text']['probe_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss']['probe_headroom_bytes']}"
              + f" island={cap['resident_island']['probe_headroom_bytes']}"
              + f" slice={cap['runtime_overlay_slices']['probe_minimum_headroom_bytes']}"
              + " e000-delta=0 product-links=0")
        return 0
    except (CapacityError, GUARD.GateError, OSError, KeyError, ValueError,
            RuntimeError, json.JSONDecodeError) as exc:
        print(f"c2-preinstall-island-capacity: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
