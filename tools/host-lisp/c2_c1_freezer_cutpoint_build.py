#!/usr/bin/env python3
"""Build the one non-promotable C1 Freezer cutpoint carrier."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_cutpoint_gate as C1  # noqa: E402
import c2_link58_matrix_addenda_successor_link as LINK58  # noqa: E402


BASE = LINK58.BASE
L = LINK58.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-memory-holds-NONPROMOTABLE")
RECEIPT = EVIDENCE / (
    "c2.2-link58-c1-freezer-memory-holds-"
    "nonpromotable-structural-receipt.json")
FEATURE = "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE"
LINK58_PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")


class BuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BuildError(message)


def authority() -> dict[str, Any]:
    qualified = LINK58.validate_authority()
    product = LINK58.OUT / "lisp65-c2-substitution-linked.prg"
    structural = json.loads(LINK58.RECEIPT.read_text(encoding="utf-8"))
    source = C1.gate()
    require(
        L.sha(product) == LINK58_PRODUCT_SHA
        and structural["status"] ==
            "passed-link58-matrix-addenda-product-identity-hardware-not-run"
        and source["source"]["product_bytes"] == 0
        and len(source["mutations_rejected"]) == 10,
        "C1 diagnostic authority incomplete")
    return qualified


def finalize_existing() -> int:
    require(OUT.is_dir() and RECEIPT.is_file(),
            "C1 diagnostic WPLTO donor is incomplete")
    os.chmod(OUT, 0o755)
    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    session = OUT / "runtime-overlays-session-final.bin"
    session_manifest = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    slices = {row["section"]: row for row in session_manifest["slices"]}
    wanted = {
        ".lisp65_rt_c2append_journal_prepare": 1792,
        ".lisp65_rt_c2append_header": 768,
        ".lisp65_rt_c2append_publish_clear": 1280,
        ".lisp65_rt_c2append_rollback_unpublish": 768,
    }
    observed: dict[str, dict[str, int]] = {}
    for section, packed_ceiling in wanted.items():
        row = slices[section]
        observed[section] = {
            "payload_bytes": row["file_size"],
            "pack_ceiling_bytes": packed_ceiling,
            "headroom_bytes": packed_ceiling - row["file_size"],
        }
        require(0 < row["file_size"] <= packed_ceiling,
                f"C1 diagnostic slice overflow: {section}")
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    require(
        receipt["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and L.sha(product) != LINK58_PRODUCT_SHA
        and "nonpromotable_diagnostic=C1-Freezer-open-transaction"
            in (OUT / "resolved-profile.txt").read_text(encoding="utf-8")
        and walls["bank0_text_headroom_bytes"] > 0
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] == 4
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and session.stat().st_size == 65438,
        "C1 diagnostic WPLTO donor changed a bound slice/aggregate currency")

    source_gate_path = OUT / "c1-freezer-cutpoint-source-gate.json"
    if source_gate_path.exists():
        os.chmod(source_gate_path, 0o644)
    source_gate_path.write_text(
        json.dumps(C1.gate(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt["format"] = (
        "lisp65-c2.2-link58-c1-freezer-memory-hold-nonpromotable-v1")
    receipt["status"] = (
        "passed-nonpromotable-C1-memory-hold-WPLTO-donor-"
        "hardware-not-run")
    receipt["promotable"] = False
    receipt["authority"]["link58_product"] = {
        **L.bind(LINK58.OUT / "lisp65-c2-substitution-linked.prg"),
        "status": "immutable-acceptance-product"}
    receipt["authority"]["C1_contract"] = L.bind(C1.CONTRACT)
    receipt["authority"]["C1_source_gate"] = L.bind(source_gate_path)
    receipt["diagnostic_identity"] = {
        "product": L.bind(product),
        "elf": L.bind(elf),
        "map": L.bind(Path(str(product) + ".map")),
        "session_family": L.bind(session),
        "feature": FEATURE,
        "promotable": False,
        "deployment_role": "WPLTO-overlay-donor-only",
        "product_bytes_changed": 0,
        "resident_cells_added": 0,
        "gc_roots_added": 0,
        "freezer_register_assumptions": 0,
    }
    receipt["C1_cutpoints"] = {
        "addresses": {"command": "0x17e0", "reached": "0x17e1"},
        "hold_rule": (
            "reload command memory on every loop iteration; "
            "never carry the cutpoint id in a CPU register across thaw"),
        "cold_slice_capacity": observed,
        "packed_session_bytes": session.stat().st_size,
        "packed_session_headroom_bytes": 65536 - session.stat().st_size,
        "hardware": "not-run",
    }
    receipt["diagnostic_donor_qualification"] = {
        "status": "passed-for-overlay-donor-only",
        "inherited_product_qualifier": (
            "not-applicable: the diagnostic resident image is not deployed"),
        "observed_non_deployed_bank0_text_headroom_bytes":
            walls["bank0_text_headroom_bytes"],
        "deployed_resident_authority": "immutable Link-58 product",
        "deployed_resident_delta_bytes": 0,
    }
    receipt["execution_accounting"]["hardware_runs"] = 0
    receipt["execution_accounting"]["latency_attempts_consumed"] = 0
    receipt["next_gate"] = (
        "artifact-only Link-58 relocation rebind and carrier capacity gate; "
        "then separate authorization for cutpoints 2 through 4")
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(source_gate_path, 0o444)
    os.chmod(RECEIPT, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-cutpoint-build: PASS donor-only "
        f"sha={L.sha(product)} session={session.stat().st_size} "
        f"donor-text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} hardware=not-run")
    return 0


def main() -> int:
    if OUT.exists() or RECEIPT.exists():
        return finalize_existing()
    authority()
    base_names = (
        "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
        "WPLTO_SOURCE", "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA",
        "BASELINE_RECEIPT", "BASELINE_RECEIPT_SHA", "validate_authority",
    )
    old_base = {name: getattr(BASE, name) for name in base_names}
    original_single_link = L.P.single_link

    def diagnostic_single_link(
            out: Path, *, probe_definitions: tuple[str, ...] = (),
            direct_entry_receipt: Path = L.P.DIRECT_ENTRY_CONTRACT_RECEIPT,
            direct_entry_check_tool: str = "c2_direct_entry_contract.py",
            extra_contract_lines: tuple[str, ...] = ()) -> None:
        require(FEATURE not in probe_definitions,
                "C1 diagnostic feature duplicated")
        original_single_link(
            out,
            probe_definitions=(*probe_definitions, FEATURE),
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "nonpromotable_diagnostic=C1-Freezer-open-transaction",
                "diagnostic_command_address=0x17e0",
                "diagnostic_reached_address=0x17e1",
                "product_authority_sha256="
                + LINK58_PRODUCT_SHA,
            ))

    try:
        BASE.LINK_NUMBER = 58
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = LINK58.WPLTO
        BASE.WPLTO_SHA = LINK58.WPLTO_SHA
        BASE.WPLTO_SOURCE = LINK58.WPLTO_SOURCE
        BASE.WPLTO_PROFILE = LINK58.WPLTO_PROFILE
        BASE.BASELINE = LINK58.OUT / "lisp65-c2-substitution-linked.prg"
        BASE.BASELINE_SHA = LINK58_PRODUCT_SHA
        BASE.BASELINE_RECEIPT = LINK58.RECEIPT
        BASE.BASELINE_RECEIPT_SHA = L.sha(LINK58.RECEIPT)
        BASE.validate_authority = authority
        L.P.single_link = diagnostic_single_link
        result = BASE.main()
    finally:
        L.P.single_link = original_single_link
        for name, value in old_base.items():
            setattr(BASE, name, value)
    if result != 0:
        return result
    return finalize_existing()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BuildError, C1.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-cutpoint-build: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
