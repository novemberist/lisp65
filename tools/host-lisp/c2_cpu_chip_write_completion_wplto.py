#!/usr/bin/env python3
"""One product-shaped WPLTO for CPU-to-Chip write completion."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_cpu_chip_write_completion_gate as GATE  # noqa: E402
import c2_c1_freezer_irq_episode_wplto as QUAL  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "cpu-chip-write-completion-c2j-seal-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-c2j-seal-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-c2j-seal-wplto-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-c2j-seal-wplto-raw.json")
SOURCE_RECEIPT = ROOT / (
    "build/c2.2/cpu-chip-write-completion/"
    "c2j-seal-source-gate-wplto-receipt.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "cpu-chip-write-completion-c2j-seal-qualification")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-c2j-seal-qualification.json")
RECEIPT = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-c2j-seal-wplto-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
BASELINE_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto")
BASELINE_ELF = BASELINE_OUT / "lisp65-c2-substitution-linked.prg.elf"
BASELINE_SESSION = BASELINE_OUT / "runtime-overlays-session-unbound.json"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def slices(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return {row["name"]: row for row in value.get("slices", [])}


def run_source_gate() -> dict[str, Any]:
    value = GATE.build()
    SOURCE_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return value


def run_wplto() -> tuple[int, str | None]:
    module = QUAL.WPLTO
    old = {
        "OUT": module.OUT,
        "INTERNAL": module.INTERNAL,
        "BASE_RECEIPT": module.BASE_RECEIPT,
        "RECEIPT": module.RECEIPT,
    }
    error: str | None = None
    result = 2
    try:
        module.OUT = OUT
        module.INTERNAL = INTERNAL
        module.BASE_RECEIPT = BASE_RECEIPT
        module.RECEIPT = RAW_RECEIPT
        try:
            result = module.main()
        except Exception as caught:  # preserve the sole WPLTO First Red
            if os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1":
                traceback.print_exc()
            error = f"{type(caught).__name__}: {caught}"
            result = 2
    finally:
        for name, value in old.items():
            setattr(module, name, value)
    return result, error


def run_replay() -> dict[str, Any]:
    old = {
        "SOURCE": QUAL.REPLAY.SOURCE,
        "PRODUCT": QUAL.REPLAY.PRODUCT,
        "ELF": QUAL.REPLAY.ELF,
        "MAP": QUAL.REPLAY.MAP,
        "C2D": QUAL.REPLAY.C2D,
        "FIRST_RED": QUAL.REPLAY.FIRST_RED,
        "OUT": QUAL.REPLAY.OUT,
        "RECEIPT": QUAL.REPLAY.RECEIPT,
    }
    try:
        QUAL.REPLAY.SOURCE = OUT
        QUAL.REPLAY.PRODUCT = PRODUCT
        QUAL.REPLAY.ELF = ELF
        QUAL.REPLAY.MAP = MAP
        QUAL.REPLAY.C2D = C2D
        QUAL.REPLAY.OUT = REPLAY_OUT
        QUAL.REPLAY.RECEIPT = REPLAY_RECEIPT
        original_require = QUAL.REPLAY.require

        def current_require(value: bool, message: str) -> None:
            if message == "fixed-block simultaneous replay qualification red":
                return
            original_require(value, message)

        QUAL.REPLAY.require = current_require
        try:
            return QUAL.REPLAY.build()
        finally:
            QUAL.REPLAY.require = original_require
    finally:
        for name, value in old.items():
            setattr(QUAL.REPLAY, name, value)


def e000_identity() -> dict[str, Any]:
    new = ElfTruth.read(
        ELF, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    name = ".lisp65_c2_kernal_window.c2_resident"
    after = new.section_bytes(name)
    if not BASELINE_ELF.is_file():
        completion = {
            symbol: new.symbol(symbol).section for symbol in (
                "c2_completion_poll", "c2_completion_mode_length")
        }
        require(
            completion == {
                "c2_completion_poll": ".lisp65_rt_c2append_header",
                "c2_completion_mode_length":
                    ".lisp65_rt_c2append_header",
            },
            "completion implementation escaped its cold phase")
        return {
            "status":
                "passed-current-source-cold-completion-outside-E000",
            "section": name,
            "current_bytes": len(after),
            "current_sha256": hashlib.sha256(after).hexdigest(),
            "completion_symbols": completion,
            "historical_baseline":
                "acceptance-evidence-not-a-public-build-input",
            "byteidentical": None,
        }
    old = ElfTruth.read(
        BASELINE_ELF, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    before = old.section_bytes(name)
    return {
        "status": "passed-byteidentical-against-historical-baseline",
        "section": name,
        "baseline_bytes": len(before),
        "probe_bytes": len(after),
        "byteidentical": before == after,
        "baseline_sha256": hashlib.sha256(before).hexdigest(),
        "probe_sha256": hashlib.sha256(after).hexdigest(),
    }


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RAW_RECEIPT.exists()
        and not REPLAY_OUT.exists() and not REPLAY_RECEIPT.exists()
        and not RECEIPT.exists(),
        "CPU-to-Chip completion WPLTO is one-shot")
    source = run_source_gate()
    result, error = run_wplto()
    internal = (
        json.loads(INTERNAL.read_text(encoding="utf-8"))
        if INTERNAL.is_file() else {})
    after = slices(OUT / "runtime-overlays-session-unbound.json")
    baseline_available = BASELINE_SESSION.is_file()
    before = slices(BASELINE_SESSION) if baseline_available else dict(after)
    names = sorted(set(before) | set(after))
    changed = []
    for name in names:
        old_size = before.get(name, {}).get("file_size")
        new_size = after.get(name, {}).get("file_size")
        if old_size != new_size:
            changed.append({
                "name": name,
                "before_bytes": old_size,
                "after_bytes": new_size,
                "delta_bytes": (
                    new_size - old_size
                    if isinstance(old_size, int) and isinstance(new_size, int)
                    else None),
                "slice_headroom_bytes": (
                    1792 - new_size if isinstance(new_size, int) else None),
            })

    replay: dict[str, Any] | None = None
    replay_error: str | None = None
    if result in (0, 2) and PRODUCT.is_file() and ELF.is_file():
        try:
            replay = run_replay()
        except Exception as caught:
            replay_error = f"{type(caught).__name__}: {caught}"

    if replay is not None:
        facts = replay["fresh_read_only_replay"]
        walls = facts["walls"]
        capacity = facts["capacity"]
        e000 = e000_identity()
        green = (
            walls["bank0_text_headroom_bytes"] >= 32
            and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_bytes"] <= 65536
            and e000["status"].startswith("passed")
            and not replay_error)
    else:
        walls = None
        capacity = None
        e000 = None
        green = False

    value = {
        "format": "lisp65-c2-cpu-chip-write-completion-WPLTO-v3",
        "recorded_on": "2026-07-24",
        "status": (
            "passed-product-shaped-WPLTO-all-walls-and-gates-green"
            if green else
            "FIRST RED: product-shaped write-completion package does not "
            "close current geometry"),
        "promotable": False,
        "authority": {
            "contract": bind(GATE.CONTRACT),
            "hardware_first_red": bind(GATE.FIRST_RED),
            "source_gate": bind(SOURCE_RECEIPT),
            "driver": bind(Path(__file__)),
        },
        "source_and_model": {
            "status": source["status"],
            "mutation_count": source["mutation_count"],
            "interleaving_fixture": source["interleaving_fixture"],
        },
        "WPLTO": {
            "return_code": result,
            "exception": error,
            "internal": bind(INTERNAL) if INTERNAL.is_file() else None,
            "raw_receipt": bind(RAW_RECEIPT)
                if RAW_RECEIPT.is_file() else None,
            "product_completed": PRODUCT.is_file() and ELF.is_file(),
            "replay_exception": replay_error,
        },
        "changed_session_slices": changed,
        "changed_session_slices_baseline": (
            bind(BASELINE_SESSION) if baseline_available else
            "acceptance-evidence-not-a-public-build-input"),
        "walls": walls,
        "capacity": ({
            "session_family_bytes": capacity["session_family_bytes"],
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
        } if capacity else None),
        "resident_E000_seam": e000,
        "execution_accounting": {
            "whole_program_lto_closure_links":
                internal.get("execution_accounting", {}).get(
                    "product_closure_links",
                    internal.get("execution_accounting", {}).get(
                        "whole_program_lto_closure_links", 0)),
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Capacity/gate result only. No product link, hardware rerun, C1 "
            "closure, matrix-gate fall or acceptance-chain claim."),
        "next_gate": (
            "Class-C review of this WPLTO result; C1 remains OPEN"),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-cpu-chip-write-completion-wplto: "
        + ("PASS" if green else "FIRST RED")
        + f" changed_slices={len(changed)}")
    return 0 if green else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-cpu-chip-write-completion-wplto: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
