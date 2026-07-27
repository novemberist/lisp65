#!/usr/bin/env python3
"""Build and bind the one owner-authorized terminal-floor Link 36."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_crc_convergence_terminal_floor_wplto as FLOOR  # noqa: E402
import c2_dma_completion_first_status_successor_link as LINK35  # noqa: E402
import c2_l65r_v3_crc_convergence_wplto as V3  # noqa: E402


P = FLOOR.P
BASE = LINK35.BASE
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/product-link-36-crc-convergence"
RECEIPT = EVIDENCE / (
    "c2.2-product-link36-crc-convergence-structural-receipt.json")
TERMINAL_RECEIPT = FLOOR.RECEIPT
TERMINAL_RECEIPT_SHA = (
    "115cf83ccee353163b952e90a9b7c794f677777dc0a3e2ced04447ad24e8b3c9")
LINK35_REPLAY = LINK35.REPLAY_RECEIPT
LINK35_REPLAY_SHA = (
    "10bc82583a9b6f80c805a6770769792047e838e93e07d92a4735b673bd2fd13d")
LINK35_PRODUCT = LINK35.OUT / "lisp65-c2-substitution-linked.prg"
LINK35_PRODUCT_SHA = (
    "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65")
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"
SCOPE_MEMO = ROOT / "docs/planning/v1.2-scope-memo.md"
DRIVER = FLOOR.DRIVER
FEATURES = FLOOR.FEATURES
CAP = 1792


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-36 artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def tree(out: Path) -> dict[str, dict[str, Any]]:
    if not out.exists():
        return {}
    return {path.relative_to(out).as_posix(): {
                "bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path) -> None:
    if out.exists():
        BASE.protect(out)
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o444)


def configure() -> str:
    """Install exactly the terminal-floor WPLTO configuration in P."""
    FLOOR.configure()
    linker = FLOOR.floor_linker_script()
    require(P.E000_FINAL_FLOOR_BYTES == 63
            and P.host_facade_bytes() == 48
            and P.host_facade_vector_addresses().get(
                "c2_facade_rtov_crc_mem") == 0xB5F1
            and FLOOR.CRC_WINDOW_SECTION in P.KERNAL_SECTIONS,
            "Link-36 terminal-floor configuration drift")
    return linker


def prerequisites() -> dict[str, Any]:
    expected = {
        TERMINAL_RECEIPT: TERMINAL_RECEIPT_SHA,
        LINK35_REPLAY: LINK35_REPLAY_SHA,
        LINK35_PRODUCT: LINK35_PRODUCT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-36 prerequisite drift: {path}")
    terminal = json.loads(TERMINAL_RECEIPT.read_text(encoding="utf-8"))
    require(terminal.get("status") == "passed-terminal-floor-package-wplto"
            and terminal["measurement"]["walls"]["e000_headroom_bytes"] == 63
            and terminal["execution_accounting"]["promotable_product_links"] == 0
            and terminal["execution_accounting"]["hardware_runs"] == 0,
            "terminal-floor WPLTO authority is not green and non-promotable")
    predecessor = json.loads(LINK35_REPLAY.read_text(encoding="utf-8"))
    require(predecessor.get("status") ==
            "passed-artifact-only-link35-preinstall-dataflow-replay"
            and predecessor["product_identity"]["product"]["sha256"] ==
            LINK35_PRODUCT_SHA,
            "Link-35 rollback authority drift")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    floor = contract["formal_reopening_2026_07_21"]["final_floor_rule"]
    require(contract.get("status") ==
            "terminal-63-byte-floor-wplto-pass-link36-pending"
            and floor["bytes"] == 63 and floor["previous_bytes"] == 115
            and floor["authorized_debit_bytes"] == 52
            and floor["facade_vector_count"] == 16
            and "automatically selects C2-lite" in
            floor["future_resident_growth"],
            "terminal-floor contract is not Link-36-ready")
    gate = subprocess.run(
        [sys.executable, str(ROOT / "tools/host-lisp/"
                             "c2_kernal_unmap_contract_gate.py")],
        cwd=ROOT, check=False, capture_output=True, text=True)
    require(gate.returncode == 0 and "PASS" in gate.stdout,
            "terminal KERNAL-unmap contract gate is red: " + gate.stderr)
    return {
        "terminal_floor_wplto": bind(TERMINAL_RECEIPT),
        "link35_structural_rollback": bind(LINK35_REPLAY),
        "link35_product_rollback": bind(LINK35_PRODUCT),
        "kernal_unmap_contract": bind(CONTRACT),
        "kernal_unmap_contract_document": bind(CONTRACT_DOC),
        "scope_memo": bind(SCOPE_MEMO),
        "terminal_driver": bind(DRIVER),
        "contract_gate": gate.stdout.strip(),
    }


def host_command(source: Path, binary: Path) -> list[str]:
    return [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=3",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V3",
        "-DLISP65_RTOV_CRC_CONVERGENCE",
        "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE=0x08200000UL",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
        "-I" + str(ROOT / "src"),
        str(ROOT / "scripts/c2-l65r-v2-product-main.c"), str(source),
        "-o", str(binary),
    ]


def current_host_gate(out: Path) -> dict[str, Any]:
    """Fresh v3 matrix plus the first-innermost-status negative."""
    gate = out / "current-host-semantics"
    gate.mkdir(parents=True, exist_ok=False)
    positive = gate / "v3-positive"
    subprocess.run(host_command(ROOT / "src/vm_runtime_overlay.c", positive),
                   cwd=ROOT, check=True)
    env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
           "UBSAN_OPTIONS": "halt_on_error=1"}
    run = subprocess.run([str(positive)], cwd=ROOT, env=env, check=False,
                         capture_output=True, text=True)
    require(run.returncode == 0
            and "PASS publish-last+14 fail-closed cases" in run.stdout,
            "fresh v3 host matrix failed: " + run.stderr)
    (gate / "positive.stdout.txt").write_text(run.stdout, encoding="utf-8")

    source = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    source_gate = LINK35.first_status_source_gate(source)
    old = "rtov_busy = 0;\n        return transport;"
    replacement = (
        "rtov_fault = VM_RUNTIME_OVERLAY_ERR_ISLAND;\n"
        "        rtov_busy = 0;\n"
        "        return VM_RUNTIME_OVERLAY_ERR_ISLAND;")
    require(source.count(old) == 1,
            "Link-36 first-status negative source anchor drift")
    mutated = gate / "vm_runtime_overlay.generic-outer-negative.c"
    mutated.write_text(source.replace(old, replacement, 1), encoding="utf-8")
    negative = gate / "v3-generic-outer-negative"
    subprocess.run(host_command(mutated, negative), cwd=ROOT, check=True)
    neg = subprocess.run([str(negative)], cwd=ROOT, env=env, check=False,
                         capture_output=True, text=True)
    require(neg.returncode != 0
            and "FAIL v1 rejected with inner VERSION status" in neg.stderr,
            "generic outer-status mutation did not reproduce the red")
    (gate / "negative.stderr.txt").write_text(neg.stderr, encoding="utf-8")
    return {
        "status": "passed-v3-14-cases-and-first-status-negative",
        "asan": "passed", "ubsan": "passed", "positive_cases": 14,
        "first_status_source": source_gate,
        "generic_outer_overwrite_mutation": "reproduced-red",
        "positive": bind(positive), "negative": bind(negative),
        "positive_stdout": bind(gate / "positive.stdout.txt"),
        "negative_stderr": bind(gate / "negative.stderr.txt"),
        "mutated_source": bind(mutated),
    }


def capacity(elf: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    text_room = P.HANDOFF_BASE - text["address"] - text["bytes"]
    bss_room = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    fixed = sections[FLOOR.FIXED_SECTION]
    fixed_room = 0xC356 - fixed["address"] - fixed["bytes"]
    island_room = 2048 - sum(
        sections.get(name, {}).get("bytes", 0) for name in
        (".lisp65_resident_island", ".lisp65_resident_island_annex"))
    window_used = sum(sections[name]["bytes"] for name in P.KERNAL_SECTIONS)
    e000_room = P.KERNAL_WINDOW_BYTES - window_used
    retry = sections[FLOOR.CRC_WINDOW_SECTION]
    facade = sections[".lisp65_c2_host_facade"]
    reopen_window = sum(sections[name]["bytes"]
                        for name in P.e000_reopening_section_names())
    old_reopening_debit = P.e000_reopening_debit(sections)
    pre_terminal_room = e000_room + retry["bytes"]
    pre_package_room = pre_terminal_room + reopen_window
    require(retry == {"address": 0xFF44, "bytes": 52},
            f"Link-36 terminal retry tenant drift: {retry}")
    require(fixed == {"address": 0xC335, "bytes": 31},
            f"Link-36 fixed retry scaffold drift: {fixed}")
    require(facade == {"address": 0xB5C4, "bytes": 48},
            f"Link-36 sixteen-vector facade drift: {facade}")
    require((pre_package_room, reopen_window, retry["bytes"], e000_room) ==
            (531, 416, 52, 63),
            "Link-36 terminal floor equation drift: "
            f"{pre_package_room}-{reopen_window}-{retry['bytes']}={e000_room}")
    require(old_reopening_debit == 425 <= P.E000_REOPEN_DEBIT_CAP,
            "Link-36 historical reopening debit/cap drift")
    require(all(value >= 0 for value in
                (text_room, bss_room, fixed_room, island_room))
            and e000_room == 63,
            "Link-36 resident wall red: "
            f"text={text_room} bss={bss_room} fixed={fixed_room} "
            f"island={island_room} e000={e000_room}")
    symbols = P.defined_symbols(elf)
    expected_symbols = {
        "rtov_crc_converge_retry_window": 0xFF44,
        "c2_facade_rtov_crc_mem": 0xB5F1,
        "rtov_install_island_finalize": 0xC343,
    }
    drift = {name: {"actual": symbols.get(name), "expected": address}
             for name, address in expected_symbols.items()
             if symbols.get(name) != address}
    require(not drift, f"Link-36 purpose-bound symbol drift: {drift}")
    slice_names = {spec.split(":")[2] for spec in
                   P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0)
                   for name in slice_names}
    bad_slices = {name: size for name, size in slice_sizes.items()
                  if size <= 0 or size > CAP}
    require(not bad_slices, f"Link-36 runtime slice cap red: {bad_slices}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (out / "runtime-overlays-session-final.json").read_text())
    require(boot["storage"]["size"] <= 65536
            and session["storage"]["size"] <= 65536,
            "Link-36 overlay-bank capacity red")
    return {
        "bank0_text_headroom_bytes": text_room,
        "ordinary_bank0_bss_headroom_bytes": bss_room,
        "fixed_retry_pocket_headroom_bytes": fixed_room,
        "resident_island_headroom_bytes": island_room,
        "e000": {
            "actual_headroom_bytes": e000_room,
            "terminal_floor_bytes": 63,
            "headroom_above_floor_bytes": 0,
            "pre_terminal_headroom_bytes": pre_terminal_room,
            "terminal_retry_debit_bytes": retry["bytes"],
            "pre_package_headroom_bytes": pre_package_room,
            "historical_in_window_debit_bytes": reopen_window,
            "historical_facade_debit_bytes": 9,
            "historical_reopening_debit_bytes": old_reopening_debit,
            "historical_reopening_cap_bytes": P.E000_REOPEN_DEBIT_CAP,
            "equations": ["531 - 416 - 52 = 63", "416 + 9 = 425 <= 450"],
            "successor_policy": "automatic-C2-lite",
        },
        "purpose_bound_driver": {
            "window_bytes": retry["bytes"],
            "fixed_scaffold_bytes": fixed["bytes"],
            "facade_vectors": 16,
            "symbols": expected_symbols,
        },
        "runtime_slices": {
            "count": len(slice_sizes), "cap_bytes": CAP,
            "largest_bytes": max(slice_sizes.values()),
            "minimum_headroom_bytes": CAP - max(slice_sizes.values()),
        },
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"],
        },
    }, sections


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 36 is one-shot and already has output")
    linker = configure()
    authority = prerequisites()
    original_sources = P.source_list
    original_linker = P.linker_script
    original_fixed_end = P.fixed_bank0_contract_end

    def sources(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        result = original_sources(extra_definitions)
        if FLOOR.FLOOR_DEFINE in extra_definitions:
            result.append(str(DRIVER))
        return result

    try:
        OUT.mkdir(parents=True)
        host = current_host_gate(OUT)
        fresh = BASE.PRE.check(OUT / "fresh-v5-prelink-gates")
        require(fresh["status"] == "passed-prelink-product-link-not-run"
                and fresh["b2_model"]["cases"] == 18,
                "Link-36 fresh nested-append/B2 prelink gates failed")
        P.source_list = sources
        P.linker_script = lambda: linker
        # The purpose-bound scaffold owns the complete C335..C355 pocket.
        # Pre-ownership must therefore classify that declared construction
        # range as fixed infrastructure rather than as unowned Island space.
        P.fixed_bank0_contract_end = lambda: 0xC356
        P.single_link(
            OUT, probe_definitions=FEATURES,
            direct_entry_receipt=BASE.DIRECT.RECEIPT,
            direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link36-crc-convergence-terminal-floor",
                "feature_defines=" + ",".join(FEATURES),
                "runtime_overlay_catalog_version=3",
                "runtime_overlay_decoder_versions=3-only",
                "record_crc_emitter_sites=1",
                "completion_timeout_frames=64",
                "shared_crc_retry_driver=one",
                "fixed_facade_vector_count=16",
                "final_e000_floor_bytes=63",
                "terminal_successor_policy=automatic-c2-lite",
                "green_inheritance=none",
            ))
    except Exception as error:
        value = {
            "format": "lisp65-c2-product-link36-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: terminal-floor Link 36 stopped",
            "promotable": False,
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "execution_accounting": {
                "product_closure_links": int(
                    (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
                "hardware_runs": 0,
            },
            "authority": authority,
            "evidence": tree(OUT),
            "rollback_line": {**bind(LINK35_PRODUCT), "status": "untouched"},
            "next_gate": "return to Class-C review; no retry or hardware",
        }
        write_json(RECEIPT, value)
        protect(OUT)
        return value
    finally:
        P.source_list = original_sources
        P.linker_script = original_linker
        P.fixed_bank0_contract_end = original_fixed_end

    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    try:
        structure = json.loads(
            (OUT / "product-substitution-link.json").read_text())
        total = json.loads((OUT / "total-publish-last-domain.json").read_text())
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate",
        )
        require(structure.get("status") == "passed"
                and structure.get("product_closure_link_count") == 1
                and all(structure.get(name) == "passed" for name in required),
                "Link-36 product closure is not fully green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 34,
                "Link-36 publish-last domain drift")
        measured, sections = capacity(elf, OUT)
        completion = LINK35.LEAF.elf_gate(elf)
        closure = BASE.LINK33_BASE.final_overlay_closure(elf)
        preinstall = BASE.ISLAND.static_elf_gate(elf)
        hot = BASE.HOT.direct_path_gate(elf)
        v3_source = V3.source_gate()
        manifests = V3.manifest_gate(OUT)
        source = FLOOR.source_gate()
        require(sha(product) != LINK35_PRODUCT_SHA,
                "Link 36 did not create a new product identity")
        crc_codegen = json.loads(
            (OUT / "c2-crc-codegen-gate.json").read_text())
        crc_leaf = json.loads((OUT / "c2-crc-asm-leaf-gate.json").read_text())
        f011 = json.loads((OUT / "c2-f011-mount-window-gate.json").read_text())
        fresh_gates = {
            **{name: structure[name] for name in required},
            "direct_entry_encoding": structure["direct_entry_encoding_gate"],
            "runtime_family_identity": structure["identity_components"]
                ["all_runtime_family_records_and_payloads"],
            "total_publish_last": total["status"],
            "crc_codegen": crc_codegen["status"],
            "crc_assembler_leaf": crc_leaf["status"],
            "f011_mount_window": f011["status"],
            "overlay_closure": closure["status"],
            "preinstallation_island": preinstall["status"],
            "hot_refill": hot["status"],
            "dma_completion_leaf": completion["status"],
            "v3_source": v3_source["status"],
            "v3_emission": manifests["status"],
            "terminal_source": source["status"],
            "current_host_semantics": host["status"],
        }
        require(all("pass" in status for status in fresh_gates.values()),
                f"Link-36 fresh gate set red: {fresh_gates}")
        value = {
            "format": "lisp65-c2-product-link36-crc-convergence-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-product-identity-hardware-not-run",
            "promotable": False,
            "link_number": 36,
            "inheritance": "none; every structural and capacity gate ran freshly",
            "execution_accounting": {
                "host_semantic_compiles": 2,
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
            },
            "authority": authority,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_link35_sha256": LINK35_PRODUCT_SHA,
                "new_identity": True,
            },
            "fresh_gates": fresh_gates,
            "current_host_semantics": host,
            "terminal_source": source,
            "v3_source": v3_source,
            "v3_manifests": manifests,
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "nested_append_v5": {
                "b2_run_stop_cases": fresh["b2_model"]["cases"],
                "final_overlay_closure": closure,
            },
            "preinstallation_Island": preinstall,
            "hot_refill": hot,
            "dma_completion_leaf": completion,
            "capacity": measured,
            "section_count": len(sections),
            "rollback_line": {
                **bind(LINK35_PRODUCT), "status": "untouched-and-readable"},
            "claim_limit": (
                "Fresh Link-36 product identity and structural/capacity closure "
                "only. Hardware, latency, nested eval, GC read cost, Freezer "
                "identity, promotion and acceptance remain not-run."),
            "next_gate": "authorized six-line hardware presmoke from line 1",
        }
        report = OUT / "link36-crc-convergence-structural.json"
        write_json(report, value)
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect(OUT)
        return receipt
    except Exception as error:
        value = {
            "format": "lisp65-c2-product-link36-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: terminal-floor Link 36 stopped",
            "promotable": False,
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "execution_accounting": {"product_closure_links": 1,
                                     "hardware_runs": 0},
            "authority": authority, "evidence": tree(OUT),
            "rollback_line": {**bind(LINK35_PRODUCT), "status": "untouched"},
            "next_gate": "return to Class-C review; no retry or hardware",
        }
        write_json(RECEIPT, value)
        protect(OUT)
        return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-36 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") in {
        "passed-new-product-identity-hardware-not-run",
        "FIRST RED: terminal-floor Link 36 stopped"},
        "Link-36 receipt status unknown")
    require(sha(LINK35_PRODUCT) == LINK35_PRODUCT_SHA,
            "Link-35 rollback identity drift")
    if value["status"].startswith("passed"):
        for name in ("product", "elf", "resolved_profile"):
            row = value["product_identity"][name]
            require(bind(ROOT / row["path"]) == row,
                    f"Link-36 identity drift: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = build() if args.action == "run" else check()
    print("c2-crc-convergence-successor-link: " + value["status"])
    return 3 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("c2-crc-convergence-successor-link: FAIL " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
