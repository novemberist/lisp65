#!/usr/bin/env python3
"""Pure qualification replay of the Link-38 real-ABI WPLTO artifacts.

The sole WPLTO already completed and stopped because LTO moved 49 bytes into
the resident-island installer slice.  Class-C review accepted that measured
movement.  This program asks the protected ELF again, accepting exactly the
reviewed deltas and no others.  It cannot compile or link.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_crc_asm_leaf_gate as CRC  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_wplto as PROBE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
SOURCE = ROOT / "build/c2-lite/v6-link38-rtov-crc-real-abi-wplto"
TREE = SOURCE / "full-product-wplto"
TARGET = TREE / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
MAP = Path(str(TARGET) + ".map")
BASE = PROBE.BASE
BASE_ELF = Path(str(BASE) + ".elf")
FIRST_RED = PROBE.RECEIPT
FIRST_RED_SHA = (
    "72aeb6de4e6a565c02f332ef2f496b3aba2eec3fc87473a781e87e040d5d0102")
OUT = ROOT / "build/c2-lite/v6-link38-rtov-crc-real-abi-wplto-replay"
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-link38-rtov-crc-real-abi-wplto-"
    "pure-replay-receipt.json")
EXPECTED_DELTAS = {".text": 8, ".lisp65_rt_island_00": 49}
EXPECTED_WALLS = {
    "bank0_text_headroom_bytes": 3,
    "ordinary_bank0_bss_headroom_bytes": 86,
    "fixed_hot_block_headroom_bytes": 33,
    "resident_island_headroom_bytes": 170,
    "e000_headroom_bytes": 501,
}
SLICE_CAP = 1792
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


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def validate_authority() -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha(FIRST_RED) == FIRST_RED_SHA,
            "real-ABI WPLTO First-Red authority drift")
    value = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        value.get("status") == "FIRST RED: rtov CRC real-ABI WPLTO stopped"
        and value.get("failure") == {
            "type": "ProbeError",
            "message": (
                "real-ABI correction changed unexpected sections: "
                "{'.lisp65_rt_island_00': 49}"),
        }
        and value.get("scope") == {
            "whole_program_lto_probes": 1,
            "product_links": 0,
            "hardware_runs": 0,
            "promotable": False,
        },
        "unexpected real-ABI First-Red class")
    expected = {row["path"]: row for row in value["evidence"]}
    actual = {
        path.relative_to(ROOT).as_posix(): path
        for path in SOURCE.rglob("*") if path.is_file()
    }
    require(set(actual) == set(expected),
            "protected WPLTO tree membership drift")
    for relative, row in expected.items():
        path = actual[relative]
        require(path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"]
                and (path.stat().st_mode & 0o222) == 0,
                f"protected WPLTO evidence drift: {relative}")
    require(sha(BASE) == PROBE.BASE_SHA,
            "Link-38 rollback product drift")
    return value, {
        "first_red": bind(FIRST_RED),
        "protected_evidence_files": len(expected),
        "measurement_target": bind(TARGET),
        "measurement_elf": bind(ELF),
        "measurement_map": bind(MAP),
        "rollback_product": {**bind(BASE), "status": "untouched"},
    }


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
    old_out = PROBE.OUT
    try:
        PROBE.OUT = OUT
        abi_mutations = ABI.selftest()
        crc_mutations = CRC.selftest()
        abi = ABI.audit_elf(
            ELF, out=OUT / "c2-asm-leaf-real-abi-callers.json",
            require_bank3_chain=True)
        parity = PROBE.workbench_crc_gate(TARGET, ELF)
        before = PROBE.section_sizes(BASE_ELF)
        after = PROBE.section_sizes(ELF)
        old_truth = ElfTruth.read(
            BASE_ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
        new_truth = ElfTruth.read(
            ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    finally:
        PROBE.OUT = old_out
        subprocess.run = original_run

    require(set(before) == set(after), "WPLTO section inventory drift")
    deltas = {name: after[name] - before[name] for name in sorted(before)}
    nonzero = {name: value for name, value in deltas.items() if value}
    require(nonzero == EXPECTED_DELTAS,
            f"reviewed WPLTO delta set drift: {nonzero}")

    leaf_before = old_truth.symbol("rtov_crc_mem")
    leaf_after = new_truth.symbol("rtov_crc_mem")
    require(leaf_before.value == leaf_after.value
            and leaf_before.bytes == 66 and leaf_after.bytes == 74,
            "real-ABI Leaf identity/size drift")

    callers = abi["rtov_crc_mem_callers"]
    owners: dict[str, int] = {}
    for row in callers["callers"]:
        owners[row["owner"]] = owners.get(row["owner"], 0) + 1
    require(callers["callsite_count"] == 7
            and owners == PROBE.EXPECTED_CALLERS,
            f"complete real-ABI caller inventory drift: {owners}")

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
    require(walls == EXPECTED_WALLS, f"qualified resident wall drift: {walls}")

    slice_row = sections[".lisp65_rt_island_00"]
    base_slice = P.section_table(BASE_ELF)[".lisp65_rt_island_00"]
    require(base_slice["bytes"] == 1287 and slice_row["bytes"] == 1336
            and slice_row["address"] == base_slice["address"] == 0xC356
            and slice_row["bytes"] <= SLICE_CAP,
            f"qualified Slice-00 shape drift: {base_slice}->{slice_row}")

    base_pack = BASE.parent / "runtime-overlays-session-final.bin"
    new_pack = TREE / "runtime-overlays-session-c2-lite.bin"
    require(base_pack.stat().st_size == new_pack.stat().st_size == 65438,
            "session aggregate changed instead of remaining pack-neutral")

    return {
        "accepted_class_c_delta": {
            "exact_nonzero_section_deltas": nonzero,
            "all_other_section_deltas_bytes": 0,
            "leaf": {
                "address": f"0x{leaf_after.value:04x}",
                "before_bytes": leaf_before.bytes,
                "after_bytes": leaf_after.bytes,
                "delta_bytes": leaf_after.bytes - leaf_before.bytes,
            },
            "resident_island_slice_00": {
                "vma": f"0x{slice_row['address']:04x}",
                "before_bytes": base_slice["bytes"],
                "after_bytes": slice_row["bytes"],
                "delta_bytes": slice_row["bytes"] - base_slice["bytes"],
                "cap_bytes": SLICE_CAP,
                "headroom_bytes": SLICE_CAP - slice_row["bytes"],
            },
            "session_aggregate": {
                "before": bind(base_pack),
                "after": bind(new_pack),
                "before_bytes": base_pack.stat().st_size,
                "after_bytes": new_pack.stat().st_size,
                "delta_bytes": 0,
                "bank_headroom_bytes": BANK_BYTES - new_pack.stat().st_size,
            },
            "resident_walls": walls,
        },
        "real_abi": {
            "status": abi["status"],
            "callsite_count": callers["callsite_count"],
            "owners": owners,
            "product_assembler_callers": 0,
            "gate": abi,
        },
        "negative_mutations": {
            "assembler_abi": abi_mutations,
            "crc_oracle_and_codegen": crc_mutations,
            "total": len(abi_mutations) + len(crc_mutations),
        },
        "six_vector_crc_parity": parity,
    }, commands


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "real-ABI qualification replay is one-shot")
    STAGE.apply_profile(LINK.BASE.configure)
    first_red, authority = validate_authority()
    before = snapshot(SOURCE)
    OUT.mkdir(parents=True)
    replay, commands = guarded_replay()
    after = snapshot(SOURCE)
    require(before == after,
            "pure replay modified protected WPLTO evidence")
    require(not any("clang" in name.lower() or name.lower() in {
                        "ld", "ld.lld", "lld"} for name in commands),
            "compiler/linker appeared in replay command inventory")

    value = {
        "format": "lisp65-c2-lite-v6-rtov-crc-real-abi-qualification-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-pure-qualification-replay-real-abi",
        "authority": authority,
        "class_c_disposition": {
            "decision": "accepted-measured-wplto-truth",
            "accepted_delta": EXPECTED_DELTAS,
            "reason": (
                "The 49-byte LTO movement retains 456 bytes of Slice-00 "
                "headroom and changes the 65,438-byte packed session "
                "aggregate by zero bytes."),
            "micro_shaving": "not-authorized-and-not-required",
        },
        "replay": replay,
        "immutable_evidence": {
            "before_and_after_files": len(before),
            "byte_and_mode_identity": "unchanged",
            "all_source_files_read_only": all(
                int(row["mode"], 8) & 0o222 == 0 for row in after.values()),
        },
        "tool_invocations": {
            "compiler": 0,
            "linker": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "read_only_tools": commands,
        },
        "artifacts": {
            "caller_gate": bind(
                OUT / "c2-asm-leaf-real-abi-callers.json"),
            "crc_parity_gate": bind(
                OUT / "c2-crc-asm-leaf-real-abi-parity.json"),
        },
        "rollback_line": {**bind(BASE), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "claim_limit": (
            "Pure qualification replay of one immutable product-shaped WPLTO "
            "ELF. No compilation, link, new product identity, hardware, "
            "latency, promotion or acceptance claim."),
        "next_gate": "Separate Class-C product-link completion; hardware blocked",
        "source_first_red": {
            "status": first_red["status"],
            "accepted_failure": first_red["failure"],
        },
    }
    write_json(OUT / "qualification-replay-report.json", value)
    value["replay_report"] = bind(OUT / "qualification-replay-report.json")
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = run_once()
    except Exception as error:
        print("c2-lite-v6-rtov-crc-real-abi-replay: FIRST RED " + str(error))
        return 2
    delta = value["replay"]["accepted_class_c_delta"]
    print("c2-lite-v6-rtov-crc-real-abi-replay: PASS "
          f"callers={value['replay']['real_abi']['callsite_count']} "
          f"vectors={value['replay']['six_vector_crc_parity']['cases']} "
          f"slice00-headroom={delta['resident_island_slice_00']['headroom_bytes']}B "
          f"session-headroom={delta['session_aggregate']['bank_headroom_bytes']}B "
          f"text-headroom={delta['resident_walls']['bank0_text_headroom_bytes']}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
