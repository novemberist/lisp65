#!/usr/bin/env python3
"""Complete and qualify the sole Link-63 WPLTO artifact without relinking."""

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
import c2_completion_retry_length_elf_gate as LENGTH_ELF  # noqa: E402
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as PROFILE  # noqa: E402
import c2_lite_v6_bank2_target_stage_wplto as BANK2  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_two_region_session_store_wplto as TWO  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as LINK60  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/link63-canonical-completion-length-wplto")
SOURCE_PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
SOURCE_ELF = Path(str(SOURCE_PRODUCT) + ".elf")
SOURCE_MAP = Path(str(SOURCE_PRODUCT) + ".map")
PROFILE_PATH = SOURCE / "resolved-profile.txt"
INTERNAL = EVIDENCE / (
    "c2.2-link63-canonical-completion-length-wplto-internal.json")
RAW = EVIDENCE / (
    "c2.2-link63-canonical-completion-length-wplto-raw.json")
SOURCE_GATE = ROOT / (
    "build/c2.2/two-region-session-store/"
    "link63-canonical-completion-length-write-completion-source-gate.json")
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "product/substitution-artifacts.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link63-canonical-completion-length-artifact-replay2")
PRODUCT = OUT / SOURCE_PRODUCT.name
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
RECEIPT = EVIDENCE / (
    "c2.2-link63-canonical-completion-length-artifact-replay-receipt.json")
EXPECTED_REGION1 = {
    "c2-append-rollback-wipe-plane",
    "c2-append-rollback-wipe-chip",
    "c2-append-rollback-wipe-attic",
}


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    PROFILE.configure()
    # The immutable Link-63 ELF was built with the canonical twelve-record
    # Boot inventory.  Artifact-side packing must consume that same inventory,
    # including the linked Bank-2 staging decoder, rather than reconstructing
    # the historical eleven-record predecessor.
    BANK2.configure_bank2_stage()
    TWO.configure_two_region()
    LINK60.configure_current_pin_adapters()
    P.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
    require(
        P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
        and P.VERIFIER_BINDING_BASE == 0xB972
        and P.runtime_binding_bytes() == 40
        and P.total_publish_last_bytes() == 42
        and P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D
        and P.fixed_bank0_contract_end() == 0xC354,
        "current Link-63 profile geometry drift")
    require(
        len(P.BOOT_SLICE_SPECS) + len(P.BOOT_DATA_SPECS) == 12
        and P.BOOT_BANK3_STAGE_SLOT == 9
        and P.BOOT_ISLAND_SLOT == 10
        and P.BOOT_ISLAND_CARRIER_SLOT == 11,
        "current Link-63 Boot inventory drift")


def current_walls() -> dict[str, int]:
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
        "Link-63 artifact replay is one-shot")
    require(
        all(path.is_file() for path in (
            SOURCE_PRODUCT, SOURCE_ELF, SOURCE_MAP, PROFILE_PATH, INTERNAL,
            RAW, SOURCE_GATE, PRODUCT_IDENTITY)),
        "Link-63 WPLTO artifact set is incomplete")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    source_gate = json.loads(SOURCE_GATE.read_text(encoding="utf-8"))
    require(
        internal["diagnostic"] == {
            "type": "RuntimeError",
            "message": "verifier binding address drift 0xb972 != 0xb94e",
        }
        and internal["execution_accounting"]["product_closure_links"] == 1
        and raw["status"]
            == "FIRST RED: historical checker stopped current-product "
               "L-full keymap WPLTO"
        and source_gate["format"]
            == "lisp65-c2-cpu-chip-write-completion-probe-v4"
        and source_gate["mutation_count"] == 22,
        "Link-63 expected historical-checker boundary drift")
    before = snapshot(SOURCE)
    require(
        before and all((int(row["mode"], 8) & 0o222) == 0
                       for row in before.values()),
        "Link-63 WPLTO tree is not immutable")

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
            f"artifact replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = guarded_run
        retry_length = LENGTH_ELF.audit_elf(ELF)
        crc_codegen = P.CRC_CODEGEN.audit_elf(
            ELF, out=OUT / "c2-crc-codegen-gate.json")
        crc_leaf = P.CRC_ASM_LEAF.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-gate.json")
        leaf_abi = P.ASM_LEAF_ABI.audit_elf(
            ELF, out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
            require_bank3_chain=P.FAMILY_STAGE_BINDINGS)
        f011 = P.F011_WINDOW.audit(P.F011_WINDOW.disassemble(
            P.TOOLCHAIN / "llvm-objdump", ELF))
        P.write(
            OUT / "c2-f011-mount-window-gate.json",
            json.dumps(f011, indent=2, sort_keys=True) + "\n")
        handoff = P.handoff_z_abi_gate(OUT, PRODUCT, "link63-replay")
        pre_ownership = P.pre_ownership_gate(
            OUT, PRODUCT, "link63-replay")
        data_reference = P.profile_data_reference_gate(
            OUT, PRODUCT, "link63-replay", pre_ownership)
        facade = P.fixed_facade_gate(OUT, PRODUCT, "link63-replay")
        fixed = P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-link63.json")

        unbound_boot = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "unbound")
        unbound_session = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "unbound")
        binding = P.patch_verifier_binding_table(
            OUT, PRODUCT, unbound_boot[1], unbound_session[1],
            expected_base=0xB972)
        window_binding = json.loads(
            (OUT / "kernal-window-publish-last.json").read_text(
                encoding="utf-8"))
        total_binding = P.total_publish_last_gate(
            OUT, PRODUCT, window_binding, binding,
            expected_verifier_base=0xB972)
        final_boot = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "final")
        final_session = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "final")
        family_identity = P.runtime_family_identity_gate(
            OUT, unbound_boot, unbound_session, final_boot, final_session)
        P.write(
            OUT / "runtime-overlays-final.bin",
            final_session[0].read_bytes())
        P.write(
            OUT / "runtime-overlays-final-region1.bin",
            (OUT / "runtime-overlays-session-final-region1.bin").read_bytes())
        P.closure_gate(OUT, PRODUCT)
        kernal = P.kernal_freedom_gate(OUT, PRODUCT)
        balance = P.substitution_balance(OUT, PRODUCT, kernal)
    finally:
        subprocess.run = original_run

    walls = current_walls()
    session = json.loads(final_session[1].read_text(encoding="utf-8"))
    boot = json.loads(final_boot[1].read_text(encoding="utf-8"))
    overflow = session["overflow_storage"]
    region1 = [
        row for row in session["slices"]
        if int(row.get("region_id", 0)) == 1]
    sections = P.section_table(ELF)
    require(
        walls == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and int(session["storage"]["size"]) == 64926
        and int(overflow["used"]) == 1956
        and int(overflow["capacity"]) == 2032
        and {str(row["name"]) for row in region1} == EXPECTED_REGION1
        and all(int(row["file_size"]) <= 1792
                for row in session["slices"])
        and sections[P.VERIFIER_BINDING_SECTION]
            == {"address": 0xB972, "bytes": 40}
        and retry_length["mutation_count"] == 4
        and binding["status"] == "passed"
        and total_binding["status"] == "passed"
        and family_identity["status"] == "passed"
        and kernal["status"] == "passed"
        and balance["status"] == "passed",
        "Link-63 artifact replay has a structural or capacity red")
    require(
        before == snapshot(SOURCE),
        "artifact replay modified the immutable Link-63 WPLTO tree")

    value = {
        "format":
            "lisp65-c2-link63-canonical-completion-length-artifact-replay-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-canonical-retry-length-WPLTO-all-walls-and-gates-green",
        "promotable": False,
        "authority": {
            "sole_WPLTO_product": bind(SOURCE_PRODUCT),
            "sole_WPLTO_ELF": bind(SOURCE_ELF),
            "sole_WPLTO_map": bind(SOURCE_MAP),
            "historical_checker_First_Red": bind(INTERNAL),
            "source_and_mutation_gate": bind(SOURCE_GATE),
            "retry_length_ELF_gate": bind(Path(LENGTH_ELF.__file__)),
            "driver": bind(Path(__file__)),
        },
        "class_A_historical_pin_correction": {
            "old_checker_pin": "0xb94e",
            "current_contract_pin": "0xb972",
            "measured_section": {
                "address": "0xb972",
                "bytes": 40,
            },
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "compiler_or_linker_replay": False,
        },
        "completion_retry_length": {
            "source_gate_status": source_gate["status"],
            "source_mutations": source_gate["mutation_count"],
            "ELF_gate": retry_length,
        },
        "walls": walls,
        "wall_requirements": {
            "bank0_text_noise_headroom_bytes": 32,
            "e000_floor_bytes": 54,
        },
        "runtime_families": {
            "boot_bytes": boot["storage"]["size"],
            "session_main_bytes": session["storage"]["size"],
            "session_main_headroom_bytes":
                65536 - int(session["storage"]["size"]),
            "session_overflow_used_bytes": overflow["used"],
            "session_overflow_capacity_bytes": overflow["capacity"],
            "session_overflow_headroom_bytes":
                int(overflow["capacity"]) - int(overflow["used"]),
        },
        "publish_last": {
            "verifier_and_family_stage": binding,
            "total_domain": total_binding,
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
        "completed_nonpromotable_identity": {
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
            "replay_compiler_runs": 0,
            "replay_linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "read_only_tool_invocations": commands,
        },
        "next_gate": "one authorized Link 63 with all gates fresh",
        "claim_limit": (
            "Artifact-side WPLTO qualification only. No product Link 63, "
            "hardware, C1 closure, matrix fall or acceptance-chain claim."),
    }
    report = OUT / "artifact-replay-report.json"
    write_json(report, value)
    value["artifact_replay_report"] = bind(report)
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link63-completion-length-artifact-replay: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={session['storage']['size']} "
        f"reloads={retry_length['linked_dataflow']['reload_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link63-completion-length-artifact-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
