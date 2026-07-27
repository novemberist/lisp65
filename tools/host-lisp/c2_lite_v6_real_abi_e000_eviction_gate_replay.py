#!/usr/bin/env python3
"""Pure artifact replay for the Link-39 E000 evacuation WPLTO.

The WPLTO run completed and every gate preceding KERNAL freedom passed.  The
probe then omitted the provisional-window extraction which that gate consumes.
This replay creates the disposable extraction in a new directory and completes
the remaining gates against the exact already-linked ELF.  It cannot invoke a
compiler or linker and it never modifies the measurement artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_real_abi_e000_eviction_wplto as PROBE  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_wplto as ABI_PROBE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = PROBE.P
SOURCE = ROOT / (
    "build/c2-lite/v6-link39-real-abi-e000-evacuation-wplto-replay")
FULL = SOURCE / "full-product-wplto"
TARGET = FULL / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
MAP = Path(str(TARGET) + ".map")
OUT = ROOT / (
    "build/c2-lite/v6-link39-real-abi-e000-evacuation-gate-replay")
EVIDENCE = PROBE.EVIDENCE
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "gate-replay-receipt.json")
DIAGNOSIS = EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "provisional-window-harness-diagnosis.json")

EXPECTED = {
    TARGET: "772510e6a992f2e31a16fffa2e4fb99f4687fc9eb905b4228b59dbda32fe1c67",
    ELF: "bb3964d13ada064ef976f235c1406174d43ecc1c571a23165639dafa95640ac7",
    MAP: "59cacdad19f3692d0231ba5166f7eea4aefc84bb9c5b36612dcae1a65048f4ea",
}
SUFFIX = "link39-e000-evacuation-wplto"
CAP = 1792
BANK_BYTES = 65536


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def snapshot(tree: Path) -> dict[str, str]:
    return {path.relative_to(tree).as_posix(): sha(path)
            for path in sorted(tree.rglob("*")) if path.is_file()}


def stage_gate() -> dict[str, Any]:
    """Read-only structural equivalent of the already-passed stage gate."""
    truth = ElfTruth.read(ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    expected = {
        "c2_lite_stage_boot_family_impl": ".lisp65_boot_bank3_stage",
        "c2_lite_stage_boot_family": ".lisp65_boot_bank3_stage",
        "vm_bank3_boot_stage_entry": ".lisp65_boot_bank3_stage",
        "vm_boot_overlay_chain_prepare": ".lisp65_boot_bank3_stage",
        "ov_bank_crc16": ".lisp65_boot_bank3_stage",
        "vm_bank3_boot_stage_fail": ".lisp65_boot_bank3_stage",
        "vm_boot_overlay_chain_commit": ".text",
        "c2_lite_stage_session_family_impl":
            ".lisp65_rt_bank3_stage_session",
        "c2_lite_stage_session_family":
            ".lisp65_rt_bank3_stage_session",
    }
    rows: dict[str, Any] = {}
    for name, section in expected.items():
        symbol = truth.symbol(name)
        require(symbol.section == section and symbol.bytes > 0,
                f"Bank-3 stage citizen drift: {name}")
        rows[name] = {"section": symbol.section, "address": symbol.value,
                      "bytes": symbol.bytes}
    bindings = truth.section(P.VERIFIER_BINDING_SECTION)
    require(bindings.address == STAGE.VERIFIER_BASE and bindings.bytes == 40,
            "Bank-3 publish-last section geometry drift")
    boot = json.loads(
        (FULL / "runtime-overlays-boot-c2-lite.json").read_text())
    session = json.loads(
        (FULL / "runtime-overlays-session-c2-lite.json").read_text())
    require(boot["storage"]["size"] <= BANK_BYTES
            and session["storage"]["size"] == 65438,
            "Bank-3 family pack drift")
    return {"status": "passed-read-only-stage-before-publish-structure",
            "citizens": rows,
            "publish_last": {"address": bindings.address,
                             "bytes": bindings.bytes},
            "bank3": {"boot_bytes": boot["storage"]["size"],
                      "session_bytes": session["storage"]["size"],
                      "session_headroom_bytes":
                          BANK_BYTES - session["storage"]["size"]}}


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists()
            and not DIAGNOSIS.exists(), "gate replay is one-shot")
    for path, digest in EXPECTED.items():
        require(path.is_file() and sha(path) == digest,
                f"completed WPLTO truth drift: {path}")
    before = snapshot(SOURCE)
    required_prior = {
        "fixed_facade": SOURCE / f"fixed-host-facade-{SUFFIX}.json",
        "handoff": SOURCE / f"handoff-z-abi-{SUFFIX}.json",
        "pre_ownership": SOURCE / f"pre-ownership-closure-{SUFFIX}.json",
        "profile_data": SOURCE / f"profile-data-reference-{SUFFIX}.json",
        "section_inventory": SOURCE /
            "final-section-inventory-c2-lite-v6-full-seed.prg.json",
        "real_abi": SOURCE / "c2-asm-leaf-real-abi-callers.json",
        "crc_parity": SOURCE / "c2-crc-asm-leaf-real-abi-parity.json",
    }
    for name, path in required_prior.items():
        value = json.loads(path.read_text(encoding="utf-8"))
        require(value.get("status", "passed").startswith("pass"),
                f"prior fresh gate is not green: {name}")

    diagnosis = {
        "format": "lisp65-c2-lite-v6-e000-provisional-window-harness-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-class-a-artifact-replay-required",
        "cause": (
            "The single WPLTO completed and the gates through final section "
            "inventory passed. The probe called KERNAL freedom before making "
            "its disposable provisional 8192-byte window extraction."),
        "correction": (
            "Extract the provisional window into a separate replay tree, then "
            "finish KERNAL freedom and the remaining gates against the exact "
            "already-linked SHA-bound ELF."),
        "measurement_truth": {path.name: bind(path)
                              for path in EXPECTED},
        "prior_harness_attempt": ({
            "diagnosis": bind(EVIDENCE / (
                "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
                "provisional-window-harness-diagnosis.json")),
            "provisional_window": bind(ROOT / (
                "build/c2-lite/v6-link39-real-abi-e000-evacuation-"
                "gate-replay/c2-product-kernal-window.bin")),
            "disposition": (
                "Stopped because llvm-size was omitted from the read-only "
                "tool allowlist; product measurement truth stayed unchanged."),
        } if "gate-replay2" in OUT.name else None),
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0},
    }
    write_json(DIAGNOSIS, diagnosis)
    OUT.mkdir(parents=True)

    # Configure only the gate model.  No source or product artifact is built.
    STAGE.apply_profile(LINK.BASE.configure)
    allowed = {"llvm-readobj", "llvm-objdump", "llvm-nm", "llvm-objcopy",
               "llvm-size"}
    original_run = P.run
    invocations: list[list[str]] = []

    def read_only_run(command: list[str], *args: Any, **kwargs: Any) -> Any:
        tool = Path(str(command[0])).name
        require(tool in allowed, f"compiler/linker path entered replay: {tool}")
        invocations.append([str(item) for item in command])
        return original_run(command, *args, **kwargs)

    P.run = read_only_run
    try:
        extraction = P.extract_provisional_kernal_window(OUT, TARGET)
        kernal = P.kernal_freedom_gate(OUT, TARGET)
        no_attic = LINK.no_runtime_attic_gate(
            ELF, FULL / "generated-product-sources")
        overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(ELF)
        preinstall = LINK.BASE.ISLAND.static_elf_gate(ELF)
        relocation = PROBE.relocation_gate(TARGET, ELF)
        abi = ABI.audit_elf(
            ELF, out=OUT / "c2-asm-leaf-real-abi-callers.json",
            require_bank3_chain=True)
    finally:
        P.run = original_run

    sections = P.section_table(ELF)
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - sections[".text"]["address"]
            - sections[".text"]["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - sections[".bss"]["address"]
            - sections[".bss"]["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(walls == {
        "bank0_text_headroom_bytes": 59,
        "ordinary_bank0_bss_headroom_bytes": 86,
        "fixed_hot_block_headroom_bytes": 33,
        "resident_island_headroom_bytes": 170,
        "e000_headroom_bytes": 445,
    }, f"completed WPLTO wall drift: {walls}")
    require(kernal["status"] == "passed"
            and no_attic["status"].startswith("passed")
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate"
            and abi["status"].startswith("passed")
            and relocation["bytes"] == 56,
            "one or more remaining evacuation gates are red")
    require(snapshot(SOURCE) == before,
            "artifact replay modified the WPLTO measurement truth")

    report = {
        "format": "lisp65-c2-lite-v6-real-abi-e000-gate-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-purpose-bound-e000-evacuation-gate-replay",
        "authority": {"diagnosis": bind(DIAGNOSIS),
                      "measurement_product": bind(TARGET),
                      "measurement_elf": bind(ELF),
                      "measurement_map": bind(MAP),
                      "driver": bind(Path(__file__))},
        "capacity": {"walls": walls, "text_margin_target_bytes": 32,
                     "e000_floor_bytes": 115,
                     "session_aggregate_bytes": 65438,
                     "session_aggregate_headroom_bytes": 98},
        "relocation": relocation,
        "fresh_gates_completed_here": {
            "provisional_window": extraction,
            "kernal_freedom": kernal,
            "no_runtime_attic": no_attic,
            "overlay_closure": overlay,
            "preinstallation_island": preinstall,
            "real_abi": abi,
            "bank3_stage": stage_gate(),
        },
        "fresh_gates_completed_before_harness_stop": {
            name: bind(path) for name, path in required_prior.items()},
        "execution_accounting": {
            "whole_program_lto_measurements": 1,
            "artifact_only_gate_replays": 1,
            "compiler_runs_in_replay": 0,
            "linker_runs_in_replay": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "read_only_tool_invocations": len(invocations),
        },
        "rollback_line": {**bind(ABI_PROBE.BASE), "status": "untouched"},
        "claim_limit": (
            "One completed WPLTO measurement plus a pure gate replay. No "
            "product link, hardware, latency, promotion or acceptance claim."),
        "next_gate": "Owner-preauthorized successor product link",
    }
    write_json(OUT / "e000-evacuation-gate-replay-report.json", report)
    report["replay_report"] = bind(
        OUT / "e000-evacuation-gate-replay-report.json")
    write_json(RECEIPT, report)
    for tree in (SOURCE, OUT):
        for path in tree.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
    os.chmod(DIAGNOSIS, 0o444)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-real-abi-e000-evacuation-gate-replay: PASS "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
