#!/usr/bin/env python3
"""Pure replay of the CRC assembler-leaf WPLTO artifacts; never relink."""

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
import c2_crc_asm_leaf_gate as ASM  # noqa: E402
import c2_crc_codegen_gate as CRC  # noqa: E402
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import f011_mount_window as F011  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-crc-asm-leaf-wplto"
ELF = OUT / "l65r-v2-boot-family-placement.prg.elf"
MAP = OUT / "l65r-v2-boot-family-placement.prg.map"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-asm-leaf-wplto-probe-receipt.json")
FIRST_RED_SHA = (
    "832639c8bf1d9694d5670802091582f4c1e00883ec5ab9331544ed5dd96dd57f")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-asm-leaf-wplto-harness-first-red-diagnosis.json")
DIAGNOSIS_SHA = (
    "9f5f0c51b042cc6b05d801f1f7509000578e753fda514584e75912e8d71cc5b7")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-asm-leaf-wplto-pure-replay-receipt.json")
ELF_SHA = "5d80c52c39cff7844f4206209416aa3a9a4d01bad1472f9e292472df44a117b0"
MAP_SHA = "4cabcf761abf800cb08523ce65e17786a57a9d3264af83f5248fb6a417a46561"
LINK33 = ROOT / (
    "build/c2.2/substitution/product-link-33-handoff-reanchor-final/"
    "lisp65-c2-substitution-linked.prg")
LINK33_SHA = "5f44b65a1a67530a9c3c8b687d7be597422978ae749f56101f42bdcebaf50044"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {
                "bytes": path.stat().st_size,
                "mode": oct(path.stat().st_mode & 0o777),
                "sha256": sha(path),
            }
            for path in sorted(root.rglob("*")) if path.is_file()}


def load_report(name: str, expected: str) -> dict[str, Any]:
    value = json.loads((OUT / name).read_text(encoding="utf-8"))
    require(value.get("status") == expected,
            f"replayed report red: {name}: {value.get('status')}")
    return value


def guarded_replay() -> tuple[dict[str, Any], list[str]]:
    commands: list[str] = []
    original_run = subprocess.run

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
            "ld", "ld.lld", "lld", "mos-mega65-clang"},
            f"pure replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    subprocess.run = guarded_run
    try:
        crc = CRC.audit_elf(ELF)
        asm = ASM.audit_elf(ELF)
        f011 = F011.audit(F011.disassemble(TOOLCHAIN / "llvm-objdump", ELF))
        boot_manifest = json.loads(
            (OUT / "runtime-overlays-boot-final.json").read_text(
                encoding="utf-8"))
        session_manifest = json.loads(
            (OUT / "runtime-overlays-session-final.json").read_text(
                encoding="utf-8"))
        lifetime = BOOT.boot_lifetime_gate(ELF, boot_manifest, session_manifest)
        preinstall = BOOT.ISLAND.static_elf_gate(ELF)
        sections = P.section_table(ELF)
    finally:
        subprocess.run = original_run

    kernal = load_report("kernal-freedom-link.json", "passed")
    walls = {
        "bank0_text_headroom_bytes": (
            P.HANDOFF_BASE - sections[".text"]["address"]
            - sections[".text"]["bytes"]),
        "ordinary_bank0_bss_headroom_bytes": (
            P.FIXED_BANK0_BASE - sections[".bss"]["address"]
            - sections[".bss"]["bytes"]),
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": (
            2048 - sections[".lisp65_resident_island"]["bytes"]
            - sections[".lisp65_resident_island_annex"]["bytes"]),
        "e000_headroom_bytes": kernal["capacity"][
            "actual_future_margin_bytes"],
    }
    require(all(value >= 0 for value in walls.values()),
            f"replayed resident wall red: {walls}")
    require(walls["e000_headroom_bytes"] == 115,
            "replay changed final E000 floor")
    require((OUT / "c2-product-kernal-window.bin").stat().st_size == 8192,
            "provisional KERNAL-window extraction is not exactly 8 KiB")

    reports = {
        "handoff": load_report(
            "handoff-z-abi-l65r-v2-boot-family.json", "passed")["status"],
        "pre_ownership": load_report(
            "pre-ownership-closure-l65r-v2-boot-family.json", "passed")["status"],
        "profile_data_references": load_report(
            "profile-data-reference-l65r-v2-boot-family.json", "passed")["status"],
        "fixed_facade": load_report(
            "fixed-host-facade-l65r-v2-boot-family.json", "passed")["status"],
        "runtime_family_identity": load_report(
            "runtime-family-total-identity.json", "passed")["status"],
        "one_truth": load_report("one-truth-closure.json", "passed")["status"],
        "kernal_freedom": kernal["status"],
        "provisional_window_shape": "passed",
        "verifier_publish_last": load_report(
            "runtime-verifier-publish-last.json", "passed")["status"],
        "substitution_balance": load_report(
            "substitution-balance.json", "passed")["status"],
        "boot_lifetime": lifetime["status"],
        "preinstallation_island": preinstall["status"],
        "crc_codegen": crc["status"],
        "crc_assembler_leaf": asm["status"],
        "f011_mount_window": f011["status"],
    }
    require(all("pass" in value for value in reports.values()),
            f"one replayed gate is not green: {reports}")
    mutations = BOOT.BASE.packer_mutations(
        OUT / "runtime-overlays-boot-final.bin",
        OUT / "runtime-overlays-boot-final.json")
    require(len(mutations) == 10
            and set(mutations.values()) == {"rejected-fail-closed"},
            "replayed L65R-v2 packer matrix is incomplete")
    return {
        "resident_walls": walls,
        "fresh_structural_gates": reports,
        "target_stable_crc": crc,
        "linked_leaf_equivalence": asm,
        "f011_mount_window": f011,
        "packer_mutations": mutations,
        "boot_lifetime_negative_matrix": lifetime["negative_matrix"],
        "preinstallation_negative_matrix": preinstall["negative_matrix"],
    }, commands


def run_once() -> dict[str, Any]:
    require(not RECEIPT.exists(), "pure replay receipt already exists")
    require(sha(FIRST_RED) == FIRST_RED_SHA, "First-Red receipt drift")
    require(sha(DIAGNOSIS) == DIAGNOSIS_SHA, "First-Red diagnosis drift")
    require(sha(ELF) == ELF_SHA and sha(MAP) == MAP_SHA,
            "SHA-bound WPLTO replay artifacts drift")
    require(sha(LINK33) == LINK33_SHA, "Link-33 rollback identity drift")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first_red.get("status") ==
            "FIRST RED: CRC assembler-leaf WPLTO probe stopped"
            and first_red.get("diagnostic", {}).get("message") == "'status'",
            "unexpected First-Red class")
    for row in first_red["evidence"]:
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"First-Red evidence drift: {path}")

    BOOT.BASE.configure()
    require(P.HANDOFF_BASE == 0xB4A3 and P.E000_FINAL_FLOOR_BYTES == 115
            and P.fixed_bank0_headroom_bytes() == 33,
            "canonical Link-33 geometry drift")
    before = snapshot(OUT)
    result, commands = guarded_replay()
    after = snapshot(OUT)
    require(before == after, "pure replay changed a WPLTO evidence artifact")
    require(not any("clang" in name.lower() or name.lower() in {
                        "ld", "ld.lld", "lld"} for name in commands),
            "compiler/linker appeared in replay command inventory")

    value = {
        "format": "lisp65-c2-crc-asm-leaf-wplto-pure-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-crc-asm-leaf-wplto-pure-replay-no-product-link",
        "authority": {
            "first_red_receipt": bind(FIRST_RED),
            "first_red_diagnosis": bind(DIAGNOSIS),
            "placement_elf": bind(ELF),
            "placement_map": bind(MAP),
            "rollback_product": {**bind(LINK33), "status": "untouched"},
        },
        "replay": result,
        "tool_invocations": {
            "compiler": 0,
            "linker": 0,
            "read_only_tools": commands,
            "wplto_tree_files_before_and_after": len(before),
            "wplto_tree_byte_identity": "unchanged",
            "wplto_tree_mode_identity": "unchanged",
        },
        "scope": {
            "pure_replays": 1,
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "product_closure_links": 0,
            "product_candidates": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Pure replay of one SHA-bound product-shaped WPLTO ELF and its "
            "immutable evidence. This is not a product link, new product "
            "identity, hardware result, promotion or acceptance."),
        "next_gate": (
            "Return for separate authorization of one successor product link; "
            "hardware remains blocked."),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "pure replay receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-crc-asm-leaf-wplto-pure-replay-no-product-link",
            "pure replay receipt is not green")
    require(sha(ELF) == ELF_SHA and sha(LINK33) == LINK33_SHA,
            "replay authority drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = run_once() if args.action == "run" else check()
    print("c2-crc-asm-leaf-wplto-replay: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, ASM.GateError, CRC.GateError, F011.AuditError,
            BOOT.GateError, BOOT.ISLAND.GateError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-crc-asm-leaf-wplto-replay: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(1)
