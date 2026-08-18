#!/usr/bin/env python3
"""Build, gate, bind, and protect the one authorized Link-33 successor."""

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
import c2_nested_append_v5_prelink as PRE  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / "build/c2.2/substitution/product-link-33-nested-append-v5"
BASELINE = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
BASELINE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link32-preinstall-island-guard-structural-receipt.json")
PRELINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-prelink-receipt.json")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-direct-entry-prerequisite-first-red-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-nested-append-v5-structural-receipt.json")
EXPECTED = {
    BASELINE_RECEIPT:
        "5843fea325faf2c63afc9c675de556cf72a8bb911555de0f375c98edf58ee2ab",
    PRELINK_RECEIPT:
        "09c3f83f9a698bf1f6ac9a0e50d4c1540238e956f8a4c1eefc65c8b1b49fb3a0",
    D.RECEIPT:
        "492fea599840dddadfe00421eb3f88fa2c72ab678e5e160344a7ea83595e0973",
    FIRST_RED_RECEIPT:
        "fe458106da07f034b835a2b787d25492bc83d2102a4439c60d3bc970b127a3af",
}
FEATURES = PRE.FEATURES
CAP = 1792


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
                f"Link-33 prerequisite drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    prelink = json.loads(PRELINK_RECEIPT.read_text(encoding="utf-8"))
    require(baseline.get("status")
            == "passed-new-product-identity-hardware-not-run",
            "Link-32 rollback line is not structurally green")
    require(prelink.get("status") == "passed-prelink-product-link-not-run",
            "nested-append v5 prelink is not green")
    require(prelink.get("b2_run_stop_fixture", {}).get("cases") == 18,
            "nested-append B2 prerequisite is incomplete")
    return {
        "link32_rollback_line": bind(BASELINE_RECEIPT),
        "nested_append_v5_prelink": bind(PRELINK_RECEIPT),
        "direct_entry_prerequisite_first_red": bind(FIRST_RED_RECEIPT),
        "direct_entry_contract": bind(D.RECEIPT),
    }


def configure_product_abi() -> None:
    P.configure_append_slices(P.C2_APPEND_V5_SLICES)
    require(len(P.C2_APPEND_SLICES) == 20
            and len(P.SESSION_SLICE_SPECS) == 45
            and P.UNIQUE_SLICE_COUNT == 52,
            "Link-33 append ABI configuration drift")


def final_overlay_closure(
        elf: Path, *, expected_sections: set[str] | frozenset[str] | None = None
        ) -> dict[str, Any]:
    graph = PRE.relocations(elf)
    overlay = {
        section: targets for section, targets in graph.items()
        if section.startswith(".lisp65_rt_c2append_")
    }
    expected = (set(expected_sections) if expected_sections is not None else {
        f".lisp65_rt_c2append_{name}" for name, _entry in P.C2_APPEND_SLICES
    })
    require(set(overlay) == expected,
            "FIRST RED: Link-33 final append relocation inventory drift: "
            f"missing={sorted(expected-set(overlay))} "
            f"extra={sorted(set(overlay)-expected)}")
    errors = PRE.closure_errors(overlay)
    require(not errors, f"FIRST RED: Link-33 overlay closure red: {errors}")
    return {
        "status": "passed-final-elf-overlay-closure",
        "phase_count": len(overlay),
        "forbidden_edges": errors,
        "mutation_matrix": PRE.closure_selftest(),
        "graph": overlay,
    }


def geometry(elf: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    current = P.section_table(elf)
    old = P.section_table(BASELINE / "lisp65-c2-substitution-linked.prg.elf")
    slices = {
        spec.split(":")[2]: current.get(spec.split(":")[2], {}).get("bytes", 0)
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    }
    over = {name: size for name, size in slices.items()
            if size <= 0 or size > CAP}
    require(not over, f"FIRST RED: Link-33 runtime slice cap: {over}")

    text = current[".text"]
    bss = current[".bss"]
    island = current[".lisp65_resident_island"]["bytes"]
    annex = current[".lisp65_resident_island_annex"]["bytes"]
    text_room = 0xB481 - text["address"] - text["bytes"]
    bss_room = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    island_room = 2048 - island - annex
    require(text_room >= 0 and bss_room >= 0 and island_room >= 0,
            "FIRST RED: Link-33 resident capacity: "
            f"text={text_room} bss={bss_room} island={island_room}")

    old_e000 = sum(old[name]["bytes"] for name in P.KERNAL_SECTIONS)
    new_e000 = sum(current[name]["bytes"] for name in P.KERNAL_SECTIONS)
    e000_room = P.KERNAL_WINDOW_BYTES - new_e000
    require(e000_room >= 0, f"FIRST RED: Link-33 E000 overrun: {e000_room}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (out / "runtime-overlays-session-final.json").read_text())
    require(session["storage"]["size"] <= 65536,
            "FIRST RED: Link-33 session runtime bank overrun")

    phase_sizes = {
        name: current[f".lisp65_rt_c2append_{name}"]["bytes"]
        for name, _entry in P.C2_APPEND_SLICES
    }
    old_text = old[".text"]
    old_bss = old[".bss"]
    old_text_room = 0xB481 - old_text["address"] - old_text["bytes"]
    old_bss_room = P.FIXED_BANK0_BASE - old_bss["address"] - old_bss["bytes"]
    old_island_room = (2048 - old[".lisp65_resident_island"]["bytes"]
                       - old[".lisp65_resident_island_annex"]["bytes"])
    return {
        "bank0_text": {
            "link32_headroom_bytes": old_text_room,
            "link33_headroom_bytes": text_room,
            "delta_headroom_bytes": text_room - old_text_room,
        },
        "bank0_ordinary_bss": {
            "link32_headroom_bytes": old_bss_room,
            "link33_headroom_bytes": bss_room,
            "delta_headroom_bytes": bss_room - old_bss_room,
            "prelink_static_stack_projection_bytes": 13,
            "prelink_projected_headroom_bytes": 6,
            "whole_program_lto_is_authoritative": True,
        },
        "bank0_fixed_block": {
            "headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
            "watch_floor_bytes": 200,
        },
        "resident_island": {
            "link32_headroom_bytes": old_island_room,
            "link33_base_bytes": island,
            "link33_annex_bytes": annex,
            "link33_headroom_bytes": island_room,
            "delta_headroom_bytes": island_room - old_island_room,
        },
        "runtime_overlay_slices": {
            "cap_bytes": CAP,
            "append_phase_count": len(phase_sizes),
            "append_phases": phase_sizes,
            "largest_section": max(slices, key=slices.get),
            "largest_bytes": max(slices.values()),
            "minimum_headroom_bytes": CAP - max(slices.values()),
            "over_cap_or_missing": over,
        },
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_slice_count": len(session["slices"]),
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"],
        },
        "e000": {
            "link32_occupied_bytes": old_e000,
            "link33_occupied_bytes": new_e000,
            "delta_bytes": new_e000 - old_e000,
            "future_margin_bytes": e000_room,
            "growth_policy": "closed-to-new-tenants",
        },
    }, current


def build(out: Path) -> dict[str, Any]:
    prereq = prerequisites()
    if out.exists():
        # The authorized retry may continue only from the exact pre-link-only
        # first-red state.  Neither linker ran in that attempt, and its two
        # protected objects remain immutable evidence beside the fresh replay.
        old = out / "fresh-v5-prelink-gates"
        expected_old = {
            old / "c2-runtime.o":
                "85eca8b353e6e09bfd1e27291a6b23f23d396ce4a4f4b32eb07794a33c3156c5",
            old / "interrupt.o":
                "8bd46d6fb56ce304c6d970407920e9d5cfacb69638d73eb9c17606417ae29755",
        }
        observed = {path for path in out.rglob("*") if path.is_file()}
        require(observed == set(expected_old),
                f"Link-33 retry output is not the exact pre-link first red: {observed}")
        for path, expected in expected_old.items():
            require(sha(path) == expected and path.stat().st_mode & 0o777 == 0o444,
                    f"Link-33 first-red evidence drift: {path}")
    configure_product_abi()

    # Fresh target-object, source, mutation, closure, and all 18 B2 cutpoint
    # gates.  These are rerun; the prelink receipt is only their authorization
    # and input binding, never inherited green.
    fresh_prelink = PRE.check(out / "fresh-v5-prelink-gates-retry")
    require(fresh_prelink["status"] == "passed-prelink-product-link-not-run"
            and fresh_prelink["b2_model"]["cases"] == 18,
            "FIRST RED: Link-33 fresh v5/B2 prelink replay red")

    extra = (
        "mode=link33-nested-append-v5-successor",
        "feature_defines=" + ",".join(FEATURES),
        "append_abi=v5-high-edge-transient-c2j",
        "append_slice_count=20",
        "session_family_slice_count=45",
        "nested_append_prelink_receipt_sha256=" + sha(PRELINK_RECEIPT),
        "link32_rollback_receipt_sha256=" + sha(BASELINE_RECEIPT),
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
            "FIRST RED: Link-33 generic product closure is not green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "FIRST RED: Link-33 34-byte publish-last binding is not green")

    capacity, sections = geometry(elf, out)
    closure = final_overlay_closure(elf)
    preinstall = ISLAND.static_elf_gate(elf)
    direct = H.direct_path_gate(elf)
    profile = (out / "resolved-profile.txt").read_text(encoding="utf-8")
    require("feature_defines=" + ",".join(FEATURES) in profile,
            "FIRST RED: Link-33 resolved feature profile drift")

    symbols = H.symbol_table(elf)
    require("c2_product_abort_cleanup" in symbols,
            "FIRST RED: Link-33 common C2J abort surface absent")
    session = json.loads(
        (out / "runtime-overlays-session-final.json").read_text())
    published = {row["id"]: row["name"] for row in session["slices"]}
    for index, (name, _entry) in enumerate(P.C2_APPEND_SLICES):
        slot = P.SESSION_APPEND_SLOT_BASE + index
        require(published.get(slot) == "c2-append-" + name.replace("_", "-"),
                f"FIRST RED: Link-33 append slot {slot} publication drift")

    reports = (
        "product-substitution-link.json", "total-publish-last-domain.json",
        "kernal-window-publish-last.json", "runtime-verifier-publish-last.json",
        "runtime-family-total-identity.json", "one-truth-closure.json",
        "kernal-freedom-link.json", "fixed-host-facade-final.json",
        "pre-ownership-closure-final.json", "handoff-z-abi-final.json",
        "profile-data-reference-final.json", "substitution-balance.json",
        "v2-product-profile-parity.json", "final-section-inventory.json",
    )
    evidence = {name: bind(out / name) for name in reports}
    fresh_gate_report = {
        "status": fresh_prelink["status"],
        "slices": fresh_prelink["slices"],
        "serial_driver": fresh_prelink["driver"],
        "overlay_closure": fresh_prelink["overlay_closure"],
        "b2_source": fresh_prelink["b2_source"],
        "b2_model": fresh_prelink["b2_model"],
    }
    fresh_path = out / "nested-append-v5-fresh-gates.json"
    fresh_path.write_text(json.dumps(fresh_gate_report, indent=2,
                                     sort_keys=True) + "\n", encoding="utf-8")
    closure_path = out / "nested-append-v5-final-overlay-closure.json"
    closure_path.write_text(json.dumps(closure, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    evidence[fresh_path.name] = bind(fresh_path)
    evidence[closure_path.name] = bind(closure_path)

    value = {
        "format": "lisp65-c2-product-link33-nested-append-v5-structural-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-new-product-identity-hardware-not-run",
        "link_number": 33,
        "inheritance": "none; every structural, mutation and capacity gate ran freshly",
        "execution_accounting": {
            "fresh_nonproduct_target_compiles": 2,
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
        "nested_append_v5": {
            "feature_defines": list(FEATURES),
            "session_slice_count": len(P.SESSION_SLICE_SPECS),
            "append_slice_count": len(P.C2_APPEND_SLICES),
            "fresh_prelink_gate": fresh_gate_report,
            "final_elf_overlay_closure": closure,
            "b2_run_stop_cases": fresh_prelink["b2_model"]["cases"],
            "serial_driver_is_only_overlay_caller": True,
        },
        "preinstallation_Island": preinstall,
        "hot_refill": {"direct_shared_materializer": direct},
        "capacity": capacity,
        "fresh_evidence_reports": evidence,
        "section_count": len(sections),
        "claim_limit": (
            "Fresh single product-closure Link 33 with a fresh v5 target/source/"
            "mutation/B2 replay, complete structural and capacity replay, and "
            "34-byte publish-last binding. Hardware execution, latency, Freezer "
            "identity, GC read cost, promotion and C2.2 acceptance are not run."),
        "next_gate": (
            "Run the owner-authorized receipt-less hardware presmoke: boot-to-"
            "REPL; nested eval; definition first call and warm second call with "
            "frame limits; GC blockread count; Freezer E000 identity."),
    }
    report_path = out / "nested-append-v5-successor-link.json"
    report_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def protect(out: Path) -> None:
    require(out == DEFAULT_OUT and out.is_dir(),
            "protection target is not the Link-33 directory")
    for path in out.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    for path in sorted((p for p in out.rglob("*") if p.is_dir()),
                       key=lambda p: len(p.parts), reverse=True):
        os.chmod(path, 0o555)
    os.chmod(out, 0o555)


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-33 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-new-product-identity-hardware-not-run"
            and value.get("link_number") == 33,
            "Link-33 receipt status drift")
    for row in value["product_identity"].values():
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"Link-33 identity drift: {path}")
    require(value["nested_append_v5"]["b2_run_stop_cases"] == 18,
            "Link-33 B2 receipt drift")
    require(value["post_link_identity"]["declared_mutable_product_bytes"] == 34,
            "Link-33 publish-last domain drift")
    root = DEFAULT_OUT
    bad_modes = [
        str(path.relative_to(root)) or "."
        for path in (root, *root.rglob("*"))
        if ((path.is_file() and path.stat().st_mode & 0o777 != 0o444)
            or (path.is_dir() and path.stat().st_mode & 0o777 != 0o555))
    ]
    require(not bad_modes, f"Link-33 protection drift: {bad_modes}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "protect", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            prerequisites()
            configure_product_abi()
            PRE.closure_selftest()
            require(PRE.b2_model_gate()["cases"] == 18,
                    "Link-33 B2 selftest drift")
            print("c2-nested-append-v5-successor: SELFTEST PASS "
                  "session=45 append=20 b2=18")
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
            require(not RECEIPT.exists(),
                    "refusing to overwrite existing Link-33 receipt")
            RECEIPT.write_bytes(canonical(value))
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        cap = value["capacity"]
        print("c2-nested-append-v5-successor: " + verb
              + f" product={value['product_identity']['product']['sha256'][:16]}"
              + f" text={cap['bank0_text']['link33_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss']['link33_headroom_bytes']}"
              + f" island={cap['resident_island']['link33_headroom_bytes']}"
              + f" slice={cap['runtime_overlay_slices']['minimum_headroom_bytes']}"
              + f" session={cap['runtime_overlay_bank']['session_headroom_bytes']}"
              + f" e000={cap['e000']['future_margin_bytes']}"
              + " hardware=not-run")
        return 0
    except (LinkError, PRE.GateError, ISLAND.GateError, OSError, ValueError,
            KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"c2-nested-append-v5-successor: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
