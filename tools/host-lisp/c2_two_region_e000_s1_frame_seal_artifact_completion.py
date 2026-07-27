#!/usr/bin/env python3
"""Complete the frame-seal WPLTO artifact through the current B972 gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_wplto as BANK2  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as LINK60  # noqa: E402
import c2_two_region_e000_s1_link60_pin_artifact_completion as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-frame-seal-wplto2")
FIRST_RED = EVIDENCE / (
    "c2.2-two-region-e000-s1-frame-seal-wplto2-internal.json")
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-frame-seal-wplto2-receipt.json")
FORMAT_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-frame-seal-format-and-stage-gate2.json")
RAW_COMPLETION_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-frame-seal-artifact-completion-raw.json")
RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-frame-seal-wplto-green-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-frame-seal-artifact-completion")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"frame-seal completion artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def configure_current_geometry() -> None:
    BASE.PROFILE.configure()
    BANK2.configure_bank2_stage()
    BASE.TWO.configure_two_region()
    LINK60.configure_current_pin_adapters()
    BASE.P.PRODUCT_ARTIFACTS_MANIFEST = BASE.PRODUCT_IDENTITY
    require(
        BASE.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
        and BASE.P.VERIFIER_BINDING_BASE == 0xB972
        and BASE.P.runtime_binding_bytes() == 40
        and BASE.P.total_publish_last_bytes() == 42
        and len(BASE.P.BOOT_SLICE_SPECS) + len(BASE.P.BOOT_DATA_SPECS) == 12
        and BASE.P.BOOT_BANK3_STAGE_SLOT == 9
        and BASE.P.BOOT_ISLAND_SLOT == 10
        and BASE.P.BOOT_ISLAND_CARRIER_SLOT == 11,
        "current frame-seal completion geometry drift",
    )


def main() -> int:
    require(
        not OUT.exists()
        and not RAW_COMPLETION_RECEIPT.exists()
        and not RECEIPT.exists(),
        "frame-seal artifact completion is one-shot",
    )
    require(
        all(path.is_file() for path in (
            SOURCE / "lisp65-c2-substitution-linked.prg",
            Path(str(SOURCE / "lisp65-c2-substitution-linked.prg") + ".elf"),
            Path(str(SOURCE / "lisp65-c2-substitution-linked.prg") + ".map"),
            SOURCE / "resolved-profile.txt",
            FIRST_RED,
            WPLTO_RECEIPT,
            FORMAT_RECEIPT,
        )),
        "frame-seal WPLTO authority is incomplete",
    )
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    format_gate = json.loads(FORMAT_RECEIPT.read_text(encoding="utf-8"))
    require(
        first["status"] == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and first["diagnostic"] == {
            "message": "verifier binding address drift 0xb972 != 0xb94e",
            "type": "RuntimeError",
        }
        and first["execution_accounting"]["product_closure_links"] == 1,
        "frame-seal WPLTO did not stop solely at the historical pin",
    )
    require(
        format_gate["status"]
            == "passed-strict-v4-two-region-format-and-mutations"
        and format_gate["v4_installer_frame_seal"]["status"]
            == "passed-verifier-transform-seal-installer-through-path"
        and format_gate["v4_installer_frame_seal"]["old_order_mutation"]
            == "reproduced-binding-red-before-READY",
        "frame-seal end-to-end authority is not green",
    )

    BASE.SOURCE = SOURCE
    BASE.SOURCE_PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.SOURCE_ELF = Path(str(BASE.SOURCE_PRODUCT) + ".elf")
    BASE.SOURCE_MAP = Path(str(BASE.SOURCE_PRODUCT) + ".map")
    BASE.CONTRACT_PROFILE = SOURCE / "resolved-profile.txt"
    BASE.OUT = OUT
    BASE.PRODUCT = OUT / BASE.SOURCE_PRODUCT.name
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.RECEIPT = RAW_COMPLETION_RECEIPT
    BASE.configure = configure_current_geometry

    result = BASE.main()
    require(result == 0, "current-pin artifact completion stopped")
    completed = json.loads(
        RAW_COMPLETION_RECEIPT.read_text(encoding="utf-8"))
    require(
        completed["status"]
            == "passed-owner-repinned-artifact-completion-all-gates-green"
        and completed["walls"] == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and completed["runtime_families"][
            "session_main_headroom_bytes"] == 610
        and completed["execution_accounting"][
            "completion_compiler_runs"] == 0
        and completed["execution_accounting"][
            "completion_linker_runs"] == 0,
        "completed frame-seal WPLTO did not close every wall and gate",
    )
    value = {
        "format": "lisp65-c2-l65r-v4-final-frame-seal-WPLTO-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-final-frame-seal-WPLTO-all-walls-and-gates-green",
        "promotable": False,
        "authority": {
            "single_WPLTO_first_red": bind(FIRST_RED),
            "single_WPLTO_receipt": bind(WPLTO_RECEIPT),
            "strict_v4_and_end_to_end_gate": bind(FORMAT_RECEIPT),
            "artifact_completion": bind(RAW_COMPLETION_RECEIPT),
            "driver": bind(Path(__file__)),
        },
        "frame_seal": format_gate["v4_installer_frame_seal"],
        "walls": completed["walls"],
        "runtime_families": completed["runtime_families"],
        "publish_last": completed["publish_last"],
        "fresh_gates": completed["fresh_gates"],
        "completed_identity": completed["completed_identity"],
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "automatic_retries": 0,
        },
        "next_gate":
            "one separate successor product link with a fresh identity and "
            "no inherited green",
        "claim_limit":
            "WPLTO capacity, placement and structural gates only; no "
            "successor product identity, C1 result, matrix closure or "
            "acceptance-chain claim.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "c2-frame-seal-WPLTO: PASS "
        "text=134 bss=161 fixed=2 island=443 e000=151 "
        "session=64926+1956 verifier=B972 compiler=1 linker=1 "
        "artifact-replay-compiler=0 artifact-replay-linker=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CompletionError, BASE.CompletionError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-frame-seal-WPLTO: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
