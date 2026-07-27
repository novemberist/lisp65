#!/usr/bin/env python3
"""Qualify the sole single-submit WPLTO artifact without compiling or linking."""

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
import c2_link64_nonlto_completion_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STEM = "link65-single-submit-completion"
SOURCE = ROOT / f"build/c2.2/substitution/{STEM}-wplto"
SOURCE_PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
SOURCE_ELF = Path(str(SOURCE_PRODUCT) + ".elf")
SOURCE_MAP = Path(str(SOURCE_PRODUCT) + ".map")
PROFILE_PATH = SOURCE / "resolved-profile.txt"
INTERNAL = EVIDENCE / f"c2.2-{STEM}-wplto-internal.json"
RAW = EVIDENCE / f"c2.2-{STEM}-wplto-raw.json"
SOURCE_GATE = ROOT / (
    "build/c2.2/two-region-session-store/"
    f"{STEM}-write-completion-source-gate.json")
OUT = ROOT / f"build/c2.2/substitution/{STEM}-artifact-replay2"
PRODUCT = OUT / SOURCE_PRODUCT.name
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
RECEIPT = EVIDENCE / f"c2.2-{STEM}-artifact-replay2-receipt.json"
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


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "single-submit artifact replay is one-shot")
    required = (
        SOURCE_PRODUCT, SOURCE_ELF, SOURCE_MAP, PROFILE_PATH, INTERNAL, RAW,
        SOURCE_GATE, BASE.PRODUCT_IDENTITY)
    require(all(path.is_file() for path in required),
            "single-submit WPLTO artifact set is incomplete")
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
            == "lisp65-c2-cpu-chip-write-completion-probe-v7"
        and source_gate["mutation_count"] == 25,
        "expected Class-A checker boundary drift")
    before = snapshot(SOURCE)
    require(
        before and all((int(row["mode"], 8) & 0o222) == 0
                       for row in before.values()),
        "WPLTO tree is not immutable")

    shutil.copytree(SOURCE, OUT)
    os.chmod(OUT, 0o755)
    for path in OUT.rglob("*"):
        os.chmod(path, 0o644 if path.is_file() else 0o755)
    BASE.ELF = ELF
    BASE.configure()

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
        retry = BASE.LENGTH.audit_elf(ELF)
        crc_codegen = BASE.P.CRC_CODEGEN.audit_elf(
            ELF, out=OUT / "c2-crc-codegen-gate.json")
        crc_leaf = BASE.P.CRC_ASM_LEAF.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-gate.json")
        leaf_abi = BASE.ABI.audit_elf(
            ELF, out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
            require_bank3_chain=BASE.P.FAMILY_STAGE_BINDINGS)
        f011 = BASE.P.F011_WINDOW.audit(BASE.P.F011_WINDOW.disassemble(
            BASE.P.TOOLCHAIN / "llvm-objdump", ELF))
        BASE.P.write(OUT / "c2-f011-mount-window-gate.json",
                     json.dumps(f011, indent=2, sort_keys=True) + "\n")
        handoff = BASE.P.handoff_z_abi_gate(
            OUT, PRODUCT, "link65-artifact-replay")
        pre_ownership = BASE.P.pre_ownership_gate(
            OUT, PRODUCT, "link65-artifact-replay")
        data_reference = BASE.P.profile_data_reference_gate(
            OUT, PRODUCT, "link65-artifact-replay", pre_ownership)
        facade = BASE.P.fixed_facade_gate(
            OUT, PRODUCT, "link65-artifact-replay")
        fixed = BASE.P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-link65.json")

        unbound_boot = BASE.P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "unbound")
        unbound_session = BASE.P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "unbound")
        binding = BASE.P.patch_verifier_binding_table(
            OUT, PRODUCT, unbound_boot[1], unbound_session[1],
            expected_base=0xB972)
        window_binding = json.loads(
            (OUT / "kernal-window-publish-last.json").read_text(
                encoding="utf-8"))
        total_binding = BASE.P.total_publish_last_gate(
            OUT, PRODUCT, window_binding, binding,
            expected_verifier_base=0xB972)
        final_boot = BASE.P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "final")
        final_session = BASE.P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "final")
        family_identity = BASE.P.runtime_family_identity_gate(
            OUT, unbound_boot, unbound_session, final_boot, final_session)
        BASE.P.write(
            OUT / "runtime-overlays-final.bin",
            final_session[0].read_bytes())
        BASE.P.write(
            OUT / "runtime-overlays-final-region1.bin",
            (OUT / "runtime-overlays-session-final-region1.bin").read_bytes())
        BASE.P.closure_gate(OUT, PRODUCT)
        kernal = BASE.P.kernal_freedom_gate(OUT, PRODUCT)
        balance = BASE.P.substitution_balance(OUT, PRODUCT, kernal)
    finally:
        subprocess.run = original_run

    walls = BASE.current_walls()
    session = json.loads(final_session[1].read_text(encoding="utf-8"))
    boot = json.loads(final_boot[1].read_text(encoding="utf-8"))
    overflow = session["overflow_storage"]
    region1 = [
        row for row in session["slices"]
        if int(row.get("region_id", 0)) == 1]
    sections = BASE.P.section_table(ELF)
    single = retry["linked_dataflow"]["poll"]["single_submit"]
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
        and sections[BASE.P.VERIFIER_BINDING_SECTION]
            == {"address": 0xB972, "bytes": 40}
        and retry["mutation_count"] == 10
        and retry["phase_mutation_count"] == 6
        and single == {
            "reader_call_count": 1,
            "retry_target_is_after_reader": True,
            "retry_target_is_after_poison": True,
        }
        and binding["status"] == "passed"
        and total_binding["status"] == "passed"
        and family_identity["status"] == "passed"
        and kernal["status"] == "passed"
        and balance["status"] == "passed",
        "single-submit artifact replay has a structural or capacity red")
    require(before == snapshot(SOURCE),
            "artifact replay modified the immutable WPLTO tree")

    value = {
        "format":
            "lisp65-c2-link65-single-submit-completion-artifact-replay-v1",
        "recorded_on": "2026-07-26",
        "status":
            "passed-single-submit-local-observation-all-walls-and-gates",
        "promotable": False,
        "authority": {
            "sole_WPLTO_product": bind(SOURCE_PRODUCT),
            "sole_WPLTO_ELF": bind(SOURCE_ELF),
            "sole_WPLTO_map": bind(SOURCE_MAP),
            "historical_checker_First_Red": bind(INTERNAL),
            "source_and_mutation_gate": bind(SOURCE_GATE),
            "retry_ELF_gate": bind(Path(BASE.LENGTH.__file__)),
            "assembler_ABI_gate": bind(Path(BASE.ABI.__file__)),
            "driver": bind(Path(__file__)),
        },
        "class_A_gate_correction": {
            "historical_pin": "0xb94e",
            "current_contract_pin": "0xb972",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "compiler_or_linker_replay": False,
        },
        "completion": {
            "source_gate_status": source_gate["status"],
            "source_mutations": source_gate["mutation_count"],
            "linked_gate": retry,
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
        "next_gate":
            "separate Class-C authorization for the successor product link",
        "claim_limit": (
            "Artifact-side WPLTO qualification only. No product link, "
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
        "c2-link65-single-submit-completion-artifact-replay: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={session['storage']['size']} "
        f"reader_submits={single['reader_call_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link65-single-submit-completion-artifact-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
