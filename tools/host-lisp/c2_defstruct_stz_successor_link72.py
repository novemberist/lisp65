#!/usr/bin/env python3
"""Qualify and link the Link-72 45GS02 STZ-semantics correction."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_irq_episode_gate as EPISODE  # noqa: E402
import c2_defstruct_header_crc_successor as BASE  # noqa: E402
import c2_stz_z_dominance_gate as STZ  # noqa: E402


LINK = 72
ROOT_BUILD = ROOT / "build/post-promotion/link72-stz-semantics"
ROBUST_BUILD = ROOT_BUILD / "robust-product-shaped-probe"
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe"
LINK_BUILD = ROOT_BUILD
EVIDENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks")
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link72-stz-independent-zero-wplto-first-red.json")
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-link72-stz-semantics-wplto-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link72-stz-semantics-structural-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link71-defstruct-header-crc-domain-structural-receipt.json")
DIAGNOSIS = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-c2d-byte-return-hold-nonpromotable-receipt.json")
CAPTURE = ROOT / (
    "build/post-promotion/"
    "link71-defstruct-session-record-identity-hardware-replay-v3/"
    "c2d-byte-return-hold-NONPROMOTABLE/capture-summary.json")
BASELINE_MAP = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/wplto/"
    "resident-island-seed.prg.map")
ROBUST_MAP = ROBUST_BUILD / "wplto/resident-island-seed.prg.map"
DRIVER = Path(__file__).resolve()
ORIGINAL_FIX_GATES = BASE.fix_gates


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    BASE.LINK = LINK
    BASE.ROOT_BUILD = ROOT_BUILD
    BASE.PROBE_BUILD = PROBE_BUILD
    BASE.LINK_BUILD = LINK_BUILD
    BASE.WPLTO_RECEIPT = WPLTO_RECEIPT
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    BASE.fix_gates = fix_gates


def fix_gates() -> dict[str, Any]:
    resolver = ORIGINAL_FIX_GATES()
    stz = STZ.audit()
    stz_mutations = STZ.selftest()
    episode_source = Path(EPISODE.SOURCE).read_text(encoding="utf-8")
    episode = {
        "source": EPISODE.source_gate(episode_source),
        "semantics": EPISODE.semantic_gate(),
        "mutations": EPISODE.mutation_gate(episode_source),
    }
    require(
        stz["site_count"] == 25
        and stz["assembly_site_count"] == 23
        and stz["inline_assembly"]["site_count"] == 2
        and stz_mutations["baseline_sites"] == 25
        and stz_mutations["rejected"] == 50
        and episode["mutations"]["rejected"]
            == episode["mutations"]["total"] == 13
        and "leaf-length-high-Z-nonzero"
            in resolver["source_mutations_rejected"],
        "STZ semantics, IRQ episode or private-byte regression gate red")
    return {
        "resolver_and_header": resolver,
        "handwritten_STZ_Z_dominance": stz,
        "STZ_mutations": stz_mutations,
        "IRQ_episode": episode,
    }


def symbol_bytes(path: Path, symbol: str) -> int:
    pattern = re.compile(
        r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(symbol) + r"\s*$", re.MULTILINE)
    matches = pattern.findall(path.read_text(encoding="utf-8"))
    require(len(matches) == 1, f"map symbol not unique: {symbol} in {path}")
    return int(matches[0], 16)


def section_bytes(path: Path, section: str) -> int:
    pattern = re.compile(
        r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(section) + r"\s*$", re.MULTILINE)
    matches = pattern.findall(path.read_text(encoding="utf-8"))
    require(len(matches) == 1, f"map section not unique: {section} in {path}")
    return int(matches[0], 16)


def qualify_robust_first_red() -> dict[str, Any]:
    require(
        ROBUST_MAP.is_file() and BASELINE_MAP.is_file(),
        "robust-form or Link-71 map absent")
    predecessor = load(PREDECESSOR)
    diagnosis = load(DIAGNOSIS)
    capture = load(CAPTURE)
    require(
        predecessor["status"].startswith("passed-Link71-")
        and predecessor["walls"]["e000_headroom_bytes"] == 56
        and diagnosis["status"] == "completed-nonpromotable-return-edge-capture"
        and capture["summary"]["args_bytes"].startswith("433244"),
        "Link-71/capture authority drift")
    symbols = {}
    total_delta = 0
    readers = {
        "vm_c2d_byte":
            lambda path: symbol_bytes(path, "vm_c2d_byte"),
        "c2_kernal_irq_handler":
            lambda path: section_bytes(
                path, ".lisp65_c2_kernal_window.irq_handler"),
    }
    for symbol, reader in readers.items():
        before = reader(BASELINE_MAP)
        after = reader(ROBUST_MAP)
        symbols[symbol] = {
            "Link71_bytes": before,
            "independent_zero_form_bytes": after,
            "delta_bytes": after - before,
        }
        total_delta += after - before
    headroom = predecessor["walls"]["e000_headroom_bytes"] - total_delta
    require(
        symbols == {
            "vm_c2d_byte": {
                "Link71_bytes": 89,
                "independent_zero_form_bytes": 91,
                "delta_bytes": 2,
            },
            "c2_kernal_irq_handler": {
                "Link71_bytes": 72,
                "independent_zero_form_bytes": 74,
                "delta_bytes": 2,
            },
        }
        and headroom == 52 < 54,
        "robust-form capacity attribution drift")
    value = {
        "format": "lisp65-c2.2-link72-STZ-independent-zero-first-red-v1",
        "recorded_on": "2026-07-27",
        "status": "FIRST RED: independent LDA-zero/STA form crosses E000 floor",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "floor_bytes": 54,
        "projected_headroom_bytes": headroom,
        "symbol_attribution": symbols,
        "decision":
            "owner-preauthorized fallback selected: adjacent LDZ #0 / STZ "
            "__rc5; IRQ-handler LDZ #0 remains",
        "authority": {
            "Link71": BASE.bind(PREDECESSOR),
            "Link71_map": BASE.bind(BASELINE_MAP),
            "robust_form_map": BASE.bind(ROBUST_MAP),
            "Link71_capture": BASE.bind(CAPTURE),
            "diagnosis_receipt": BASE.bind(DIAGNOSIS),
            "driver": BASE.bind(DRIVER),
        },
        "claim_limit":
            "Capacity First Red only. No Link-72 product or hardware claim.",
    }
    if FIRST_RED_RECEIPT.exists():
        require(
            load(FIRST_RED_RECEIPT)["symbol_attribution"] == symbols,
            "robust-form First Red receipt drift")
    else:
        write(FIRST_RED_RECEIPT, value)
    return value


def probe_action() -> int:
    configure()
    require(
        not PROBE_BUILD.exists() and not WPLTO_RECEIPT.exists(),
        "Link-72 final WPLTO is one-shot")
    first_red = qualify_robust_first_red()
    leaf = (ROOT / "src/vm_c2d_byte.s").read_text(encoding="utf-8")
    require(
        "ldz\t#0\n\tstz\t__rc5\n\tlda\t__rc6\n\tjsr\t"
        "c2_stream_c2d_read" in leaf,
        "authorized adjacent-Z fallback absent")
    gates = fix_gates()
    paths, result = BASE.run_wplto(PROBE_BUILD)
    value = {
        "format": "lisp65-c2.2-link72-STZ-semantics-WPLTO-v1",
        "recorded_on": "2026-07-27",
        "status": "passed-Link72-STZ-semantics-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "first_red": BASE.bind(FIRST_RED_RECEIPT),
        "diagnosis": BASE.bind(DIAGNOSIS),
        "fix": {
            "vm_c2d_byte":
                "adjacent LDZ #0 / STZ __rc5 encodes length 0x0001",
            "IRQ":
                "one LDZ #0 immediately after PHZ dominates both STZ sites",
            "platform_semantics":
                "45GS02 STZ stores the live Z register",
        },
        "fix_gates": gates,
        "static_code_bytes": result["plane"]["static_code_bytes"],
        "walls": result["walls"],
        "capacity": result["capacity"],
        "session_service": result["linked_service"],
        "wplto": result["wplto"],
        "authority": {
            "resolver_contract": BASE.bind(
                ROOT / "config/c2-require-resolver-contract.json"),
            "KERNAL_contract": BASE.bind(
                ROOT / "config/c2-kernal-unmap-contract.json"),
            "vm_leaf": BASE.bind(ROOT / "src/vm_c2d_byte.s"),
            "IRQ": BASE.bind(ROOT / "src/c2_kernal_window.s"),
            "STZ_gate": BASE.bind(
                ROOT / "tools/host-lisp/c2_stz_z_dominance_gate.py"),
            "linked_ELF": BASE.bind(
                paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"),
            "driver": BASE.bind(DRIVER),
        },
        "next_gate": "authorized Link-72 successor product link",
        "claim_limit":
            "Product-shaped capacity only; no Link-72 or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-defstruct-STZ-link72: WPLTO PASS "
        f"text={value['walls']['bank0_text_headroom_bytes']} "
        f"e000={value['walls']['e000_headroom_bytes']} "
        f"session={value['capacity']['session_family_headroom_bytes']}")
    return 0


def complete_action() -> int:
    configure()
    return BASE.complete_action()


def link_action() -> int:
    configure()
    require(WPLTO_RECEIPT.is_file(), "accepted Link-72 WPLTO absent")
    result = 0
    if not LINK_RECEIPT.exists():
        result = BASE.link_action()
    receipt = load(LINK_RECEIPT)
    manifest_path = ROOT_BUILD / "canonical-product-manifest.json"
    manifest = load(manifest_path)
    manifest["static_plane"]["status"] = (
        "passed-defstruct-header-CRC-successor-single-emitter-static-plane")
    write(manifest_path, manifest)
    BASE.configure(LINK_BUILD)
    checked = BASE.CAN.check()
    require(
        checked["identity"] == manifest["identity"],
        "Link-72 manifest reclassification changed product identity")
    final_elf = (
        ROOT_BUILD / "final/lisp65-c2-substitution-linked.prg.elf")
    replay_path = ROOT_BUILD / (
        "receipts/c2-asm-leaf-ABI-and-STZ-dataflow-replay.json")
    replay = BASE.CAN.ABI.audit_elf(final_elf, out=replay_path)
    require(
        replay["handwritten_STZ_Z_dominance"]["site_count"] == 25,
        "final Link-72 STZ inventory replay drift")
    receipt.update({
        "format": "lisp65-c2.2-product-link72-STZ-semantics-successor-v1",
        "status":
            "passed-Link72-STZ-semantics-successor-hardware-not-run",
        "predecessor": BASE.bind(PREDECESSOR),
        "manifest": BASE.bind(manifest_path),
        "fix_gates": fix_gates(),
        "next_gate":
            "Bundled require/defstruct hardware session with ordinary "
            "Freezer return; no diagnostic hardware run is required.",
        "claim_limit":
            "Link 72 structural completion only; hardware unclaimed.",
    })
    receipt["authority"]["driver"] = BASE.bind(DRIVER)
    receipt["authority"]["STZ_gate"] = BASE.bind(
        ROOT / "tools/host-lisp/c2_stz_z_dominance_gate.py")
    receipt["authority"]["final_ELF_STZ_replay"] = BASE.bind(replay_path)
    receipt["authority"]["robust_form_First_Red"] = BASE.bind(
        FIRST_RED_RECEIPT)
    write(LINK_RECEIPT, receipt)
    print(
        "c2-defstruct-STZ-link72: LINK PASS "
        f"product={receipt['product']['sha256']} "
        f"text={receipt['walls']['bank0_text_headroom_bytes']} "
        f"e000={receipt['walls']['e000_headroom_bytes']}")
    return result


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["link"], ["_complete"]),
        "usage: c2_defstruct_stz_successor_link72.py [probe|link|_complete]")
    if action == ["probe"]:
        return probe_action()
    if action == ["link"]:
        return link_action()
    return complete_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        SuccessorError, BASE.SuccessorError, BASE.PROBE.ProbeError,
        BASE.CAN.CanonicalError, BASE.SERVICE.GateError,
        BASE.SERVICE.ElfTruthError, STZ.GateError, OSError, ValueError,
        KeyError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-defstruct-STZ-link72: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
