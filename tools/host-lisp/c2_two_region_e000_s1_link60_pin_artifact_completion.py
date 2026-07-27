#!/usr/bin/env python3
"""Complete the owner-repinned Link-60 WPLTO artifact without relinking.

The sole WPLTO closure already published the two KERNAL-window CRC operands
and then stopped at a historical fixed-leaf checker.  The read-only replay
proved every wall and measured the 40-byte verifier/family-stage table at
$B972.  This class-A completion copies the immutable artifact, publishes that
table, runs the remaining gates and never invokes a compiler or linker.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_two_region_session_store_wplto as TWO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-final-wplto4")
SOURCE_PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
SOURCE_ELF = Path(str(SOURCE_PRODUCT) + ".elf")
SOURCE_MAP = Path(str(SOURCE_PRODUCT) + ".map")
CONTRACT_PROFILE = SOURCE / "resolved-profile.txt"
PIN_FIRST_RED = EVIDENCE / (
    "c2.2-two-region-e000-s1-link60-pin-artifact-replay2-receipt.json")
PIN_FIRST_RED_SHA = (
    "3d558b61150db0ba96581ba3d1e3b47c10104a2c3a6d64e067e847e60b3bbfce")
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
REGION_CONTRACT = ROOT / "config/c2-two-region-session-store-contract.json"
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "product/substitution-artifacts.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-link60-artifact-completion2")
PRODUCT = OUT / SOURCE_PRODUCT.name
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-link60-artifact-completion2-receipt.json")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def configure() -> None:
    PROFILE.configure()
    TWO.configure_two_region()
    P.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
    require(
        P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
        and P.VERIFIER_BINDING_BASE == 0xB972
        and P.runtime_binding_bytes() == 40
        and P.total_publish_last_bytes() == 42
        and P.SESSION_EMITTER_STATE_BYTES == 0
        and P.SESSION_EMITTER_STATE_BASE == 0xFD22
        and P.PROFILE_RODATA_BASE == 0xFD2C
        and P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D,
        "Link-60 completion profile drift",
    )


def walls() -> dict[str, int]:
    sections = P.section_table(ELF)
    return {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE
            - (sections[".text"]["address"] + sections[".text"]["bytes"]),
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE
            - (sections[".bss"]["address"] + sections[".bss"]["bytes"]),
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes":
            2048 - sections[".lisp65_resident_island"]["bytes"],
        "e000_headroom_bytes":
            P.KERNAL_WINDOW_BYTES
            - sum(sections.get(name, {}).get("bytes", 0)
                  for name in P.KERNAL_SECTIONS),
    }


def main() -> int:
    require(
        not OUT.exists() and not RECEIPT.exists(),
        "Link-60 artifact completion is one-shot",
    )
    require(
        all(path.is_file() for path in (
            SOURCE_PRODUCT, SOURCE_ELF, SOURCE_MAP, CONTRACT_PROFILE,
            PIN_FIRST_RED, KERNAL_CONTRACT, REGION_CONTRACT,
            PRODUCT_IDENTITY,
        ))
        and sha(PIN_FIRST_RED) == PIN_FIRST_RED_SHA,
        "Link-60 completion authority absent or drifted",
    )
    pin_red = json.loads(PIN_FIRST_RED.read_text(encoding="utf-8"))
    require(
        pin_red["first_red"]["historical_active_pin"] == "0xb94e"
        and pin_red["first_red"]["measured_address"] == "0xb972"
        and pin_red["first_red"]["delta_bytes"] == 36
        and pin_red["execution_accounting"]["source_WPLTO_closure_links"] == 1,
        "Link-60 pin First Red does not name the authorized transition",
    )
    before = snapshot(SOURCE)
    require(
        before
        and all((int(row["mode"], 8) & 0o222) == 0
                for row in before.values()),
        "sole WPLTO source tree is not immutable",
    )

    shutil.copytree(SOURCE, OUT)
    os.chmod(OUT, 0o755)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o644)
        elif path.is_dir():
            os.chmod(path, 0o755)
    configure()

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(
            command[0] if isinstance(command, (list, tuple))
            else command)).name
        lowered = executable.lower()
        require(
            "clang" not in lowered
            and lowered not in {
                "cc", "gcc", "ld", "ld.lld", "lld", "mos-mega65-clang"},
            f"artifact completion attempted compiler/linker: {executable}",
        )
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = guarded_run
        crc_codegen = P.CRC_CODEGEN.audit_elf(
            ELF, out=OUT / "c2-crc-codegen-gate.json")
        crc_leaf = P.CRC_ASM_LEAF.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-gate.json")
        leaf_abi = P.ASM_LEAF_ABI.audit_elf(
            ELF,
            out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
            require_bank3_chain=P.FAMILY_STAGE_BINDINGS,
        )
        f011 = P.F011_WINDOW.audit(P.F011_WINDOW.disassemble(
            P.TOOLCHAIN / "llvm-objdump", ELF))
        P.write(
            OUT / "c2-f011-mount-window-gate.json",
            json.dumps(f011, indent=2, sort_keys=True) + "\n",
        )
        handoff = P.handoff_z_abi_gate(OUT, PRODUCT, "completion")
        pre_ownership = P.pre_ownership_gate(
            OUT, PRODUCT, "completion")
        data_reference = P.profile_data_reference_gate(
            OUT, PRODUCT, "completion", pre_ownership)
        facade = P.fixed_facade_gate(OUT, PRODUCT, "completion")
        fixed = P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-completion.json")

        unbound_boot = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT_PROFILE, "boot", "unbound")
        unbound_session = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT_PROFILE, "session", "unbound")
        binding = P.patch_verifier_binding_table(
            OUT, PRODUCT, unbound_boot[1], unbound_session[1],
            expected_base=0xB972,
        )
        window_binding = json.loads(
            (OUT / "kernal-window-publish-last.json").read_text(
                encoding="utf-8"))
        total_binding = P.total_publish_last_gate(
            OUT, PRODUCT, window_binding, binding,
            expected_verifier_base=0xB972,
        )
        final_boot = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT_PROFILE, "boot", "final")
        final_session = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT_PROFILE, "session", "final")
        family_identity = P.runtime_family_identity_gate(
            OUT, unbound_boot, unbound_session, final_boot, final_session)
        P.write(
            OUT / "runtime-overlays-final.bin",
            final_session[0].read_bytes(),
        )
        P.write(
            OUT / "runtime-overlays-final-region1.bin",
            (OUT / "runtime-overlays-session-final-region1.bin").read_bytes(),
        )
        P.closure_gate(OUT, PRODUCT)
        kernal = P.kernal_freedom_gate(OUT, PRODUCT)
        balance = P.substitution_balance(OUT, PRODUCT, kernal)
    finally:
        subprocess.run = original_run

    current_walls = walls()
    session = json.loads(final_session[1].read_text(encoding="utf-8"))
    overflow = session["overflow_storage"]
    sections = P.section_table(ELF)
    require(
        current_walls == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and int(session["storage"]["size"]) == 64926
        and 65536 - int(session["storage"]["size"]) == 610
        and int(overflow["used"]) == 1956
        and int(overflow["capacity"]) == 2032
        and sections[P.VERIFIER_BINDING_SECTION] == {
            "address": 0xB972, "bytes": 40}
        and binding["status"] == "passed"
        and binding["address"] == 0xB972
        and binding["bytes"] == 40
        and total_binding["status"] == "passed"
        and total_binding["declared_domain_bytes"] == 42
        and family_identity["status"] == "passed"
        and kernal["status"] == "passed"
        and balance["status"] == "passed"
        and fixed["fixed_code"]["end_exclusive"] == 0xC25D,
        "Link-60 artifact completion final qualification red",
    )
    require(
        before == snapshot(SOURCE),
        "artifact completion modified the immutable WPLTO source tree",
    )

    receipt = {
        "format": "lisp65-c2-link60-artifact-completion-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-owner-repinned-artifact-completion-all-gates-green",
        "promotable": False,
        "authority": {
            "sole_WPLTO_product": bind(SOURCE_PRODUCT),
            "sole_WPLTO_ELF": bind(SOURCE_ELF),
            "sole_WPLTO_map": bind(SOURCE_MAP),
            "pin_first_red": bind(PIN_FIRST_RED),
            "kernal_contract": bind(KERNAL_CONTRACT),
            "two_region_contract": bind(REGION_CONTRACT),
            "canonical_product_artifacts": bind(PRODUCT_IDENTITY),
            "driver": bind(Path(__file__)),
        },
        "owner_repin": {
            "historical_address": "0xb94e",
            "current_address": "0xb972",
            "bytes": 40,
            "delta_bytes": 36,
            "historical_receipts_modified": 0,
        },
        "publish_last": {
            "verifier_and_family_stage": binding,
            "total_domain": total_binding,
            "product_sha256_before_verifier_publish": sha(
                OUT / "lisp65-c2-substitution-window-bound.prg"),
            "product_sha256_after_all_publish": sha(PRODUCT),
        },
        "walls": current_walls,
        "runtime_families": {
            "boot_bytes": json.loads(
                final_boot[1].read_text(encoding="utf-8"))["storage"]["size"],
            "session_main_bytes": session["storage"]["size"],
            "session_main_headroom_bytes": 610,
            "session_overflow_used_bytes": overflow["used"],
            "session_overflow_capacity_bytes": overflow["capacity"],
            "session_overflow_headroom_bytes":
                int(overflow["capacity"]) - int(overflow["used"]),
        },
        "fresh_gates": {
            "crc_codegen": crc_codegen["status"],
            "crc_leaf": crc_leaf["status"],
            "assembler_leaf_ABI": leaf_abi["status"],
            "F011_window": f011["status"],
            "handoff_Z": handoff["status"],
            "pre_ownership": pre_ownership["status"],
            "profile_data_reference": data_reference["status"],
            "fixed_facade": facade["status"],
            "fixed_block": fixed["status"],
            "runtime_family_identity": family_identity["status"],
            "one_truth_closure": "passed",
            "KERNAL_freedom": kernal["status"],
            "substitution_balance": balance["status"],
        },
        "completed_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "runtime_boot": bind(final_boot[0]),
            "runtime_session": bind(final_session[0]),
            "runtime_session_region1": bind(
                OUT / "runtime-overlays-session-final-region1.bin"),
        },
        "immutable_source_tree": {
            "files": len(before),
            "byte_and_mode_identity": "unchanged",
        },
        "execution_accounting": {
            "source_WPLTO_closure_links": 1,
            "completion_compiler_runs": 0,
            "completion_linker_runs": 0,
            "completion_product_links": 0,
            "completion_hardware_runs": 0,
            "read_only_tool_invocations": commands,
        },
        "next_gate":
            "exactly one owner-authorized Link 60 with a new product "
            "identity and no inherited green",
        "claim_limit":
            "Artifact-side completion and structural qualification only. "
            "No product Link 60, hardware, matrix closure, promotion or "
            "acceptance-chain claim.",
    }
    report = OUT / "artifact-completion-report.json"
    write_json(report, receipt)
    receipt["artifact_completion_report"] = bind(report)
    write_json(RECEIPT, receipt)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link60-artifact-completion: PASS "
        f"product={sha(PRODUCT)} "
        f"text={current_walls['bank0_text_headroom_bytes']} "
        f"bss={current_walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={current_walls['fixed_hot_block_headroom_bytes']} "
        f"island={current_walls['resident_island_headroom_bytes']} "
        f"e000={current_walls['e000_headroom_bytes']} "
        "session=64926+1956 verifier=B972 compiler=0 linker=0 hardware=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CompletionError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link60-artifact-completion: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
