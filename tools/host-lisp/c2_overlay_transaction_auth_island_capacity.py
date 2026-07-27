#!/usr/bin/env python3
"""Run the one authorized Island/no-inline transaction-auth capacity seed."""

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
import c2_overlay_transaction_auth_capacity as BASE  # noqa: E402


DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/overlay-transaction-auth-island-capacity-probe")
BASELINE = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-island-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-island-capacity-placement-probe-receipt.json")
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
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


def run_probe(out: Path) -> dict[str, Any]:
    require(CONTRACT_RECEIPT.is_file(), "Island host/source receipt absent")
    contract = json.loads(CONTRACT_RECEIPT.read_text(encoding="utf-8"))
    require(contract.get("status")
            == "passed-host-source-mutations-capacity-not-run",
            "Island host/source receipt is not green")
    BASE.CONTRACT_RECEIPT = CONTRACT_RECEIPT
    BASE.FEATURES = FEATURES
    report = BASE.run_probe(out)

    cap = report["capacity"]
    bss = cap["bank0_ordinary_bss"]
    island = cap["resident_island"]
    e000 = cap["cpu_e000_window"]
    island_growth = (
        island["probe_base_bytes"] - island["link30_base_bytes"])
    require(bss["delta_headroom_bytes"] == 0
            and bss["probe_headroom_bytes"] == 19,
            f"FIRST RED: ordinary Bank-0 BSS/headroom drift: {bss}")
    require(0 <= island_growth <= 497
            and island["probe_headroom_bytes"] >= 0,
            "FIRST RED: Island control exceeds the 497-byte authorization: "
            f"growth={island_growth} headroom={island['probe_headroom_bytes']}")
    require(e000["hard_delta_bytes"] == 0,
            f"FIRST RED: closed E000 delta is not zero: {e000}")

    elf = Path(report["identity"]["seed_elf"]["path"])
    if not elf.is_absolute():
        elf = ROOT / elf
    symbols = H.symbol_table(elf)
    sections = H.symbol_sections(elf)
    island_functions = (
        "rtov_transaction_context",
        "vm_runtime_overlay_transaction_begin",
        "vm_runtime_overlay_transaction_end",
    )
    require(all(name in symbols for name in island_functions),
            "FIRST RED: Island transaction symbol missing")
    require(all(sections.get(name) == ".lisp65_resident_island"
                and 0x1800 <= symbols[name]["address"] < 0x2000
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
            "FIRST RED: dedicated transaction state survived into Bank-0 BSS")

    report["format"] = (
        "lisp65-c2-overlay-transaction-auth-island-capacity-placement-probe-v1")
    report["status"] = (
        "passed-island-noinline-capacity-placement-probe-only")
    report["scope"]["feature_defines"] = list(FEATURES)
    report["identity"]["island_followup_contract_receipt"] = (
        bind(CONTRACT_RECEIPT))
    report["capacity"]["resident_island"]["growth_bytes"] = island_growth
    report["capacity"]["resident_island"]["authorized_growth_bytes"] = 497
    report["capacity"]["bank0_ordinary_bss"]["required_headroom_bytes"] = 19
    report["fresh_structural_gates"]["transaction_control_residence"] = {
        name: {**symbols[name], "section": sections.get(name)}
        for name in island_functions
    }
    report["fresh_structural_gates"]["product_entrypoint_single_copy"] = {
        name: {**symbols[name], "section": sections.get(name)}
        for name in product_functions
    }
    report["fresh_structural_gates"]["dedicated_transaction_bss_symbols"] = 0
    report["claim_limit"] = (
        "One owner-authorized product-shaped seed for Island/BSS/E000/slice "
        "capacity, placement and structure only. No product closure link, "
        "product SHA, hardware, latency, promotion or release claim."
    )
    report["next_gate"] = (
        "Report exact deltas for review. A successor product link remains "
        "blocked pending separate authorization."
    )
    path = out / "overlay-transaction-auth-island-capacity-probe.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def check_receipt() -> dict[str, Any]:
    require(RECEIPT.is_file(), "capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status")
            == "passed-island-noinline-capacity-placement-probe-only",
            "capacity receipt status drift")
    scope = value["scope"]
    require(scope.get("resident_island_seed_links") == 1
            and scope.get("product_closure_links") == 0
            and scope.get("hardware_execution") == "prohibited",
            "capacity receipt scope drift")
    cap = value["capacity"]
    require(cap["bank0_ordinary_bss"]["probe_headroom_bytes"] == 19
            and cap["bank0_ordinary_bss"]["delta_headroom_bytes"] == 0,
            "capacity receipt BSS gate drift")
    require(cap["resident_island"]["growth_bytes"] <= 497
            and cap["resident_island"]["probe_headroom_bytes"] >= 0,
            "capacity receipt Island gate drift")
    require(cap["cpu_e000_window"]["hard_delta_bytes"] == 0,
            "capacity receipt E000 gate drift")
    for item in value["identity"].values():
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = ROOT / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and sha(path) == item["sha256"],
                f"bound capacity artifact drift: {item['path']}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "check":
            value = check_receipt()
            cap = value["capacity"]
            print("c2-overlay-transaction-auth-island-capacity: PASS"
                  + f" text={cap['bank0_text']['probe_headroom_bytes']}"
                  + f" bss={cap['bank0_ordinary_bss']['probe_headroom_bytes']}"
                  + f" e000-delta={cap['cpu_e000_window']['hard_delta_bytes']}"
                  + f" island={cap['resident_island']['probe_headroom_bytes']}"
                  + " product-links=0")
            return 0
        value = run_probe(args.out.resolve())
        data = canonical(value)
        if RECEIPT.exists():
            require(RECEIPT.read_bytes() == data,
                    "refusing to overwrite divergent capacity receipt")
        else:
            RECEIPT.write_bytes(data)
        os.chmod(RECEIPT, 0o444)
        verb = "WROTE"
        cap = value["capacity"]
        print("c2-overlay-transaction-auth-island-capacity: " + verb
              + f" text={cap['bank0_text']['probe_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss']['probe_headroom_bytes']}"
              + f" e000-delta={cap['cpu_e000_window']['hard_delta_bytes']}"
              + f" island={cap['resident_island']['probe_headroom_bytes']}"
              + " product-links=0")
        return 0
    except (CapacityError, OSError, ValueError, KeyError,
            RuntimeError, json.JSONDecodeError) as exc:
        print(f"c2-overlay-transaction-auth-island-capacity: FAIL {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
