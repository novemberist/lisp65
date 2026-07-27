#!/usr/bin/env python3
"""Static authority gate for the owner-approved append-final Hybrid.

This gate performs no compile or link.  It binds the explicit 54-byte E000
geometry and prices the three scope-cut choices from the one SHA-bound failed
WPLTO map/LTO object.  A product cut remains forbidden while selection is
null.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as P  # noqa: E402


CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
ACTIVE = ROOT / "config/c2-lite-execution-contract.json"
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link48-append-final-consolidation-wplto-first-red-diagnosis.json")
FAILED_MAP = ROOT / (
    "build/c2.2/substitution/"
    "link48-append-final-consolidation-wplto-gate-replay/"
    "resident-island-seed.prg.map")
FAILED_LTO = FAILED_MAP.with_suffix(".lto.o")
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"


class GateError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def symbol_bytes(text: str, name: str) -> int:
    pattern = re.compile(
        rf"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}\s*$",
        re.MULTILINE)
    matches = [int(value, 16) for value in pattern.findall(text)]
    require(len(matches) == 1, f"map symbol census drift: {name}={matches}")
    return matches[0]


def validate(value: dict[str, Any]) -> None:
    geo = value["e000_geometry"]
    gap = geo["reopen_gap0"]
    state = geo["session_emitter_state"]
    profile = geo["profile_rodata"]
    require(geo["active_floor_bytes"] == 54
            and int(gap["address"], 16) == 0xFCA2
            and gap["bytes"] == 128
            and int(gap["end_exclusive"], 16) == 0xFD22
            and int(state["address"], 16) == 0xFD22
            and state["bytes"] == 10
            and int(state["end_exclusive"], 16) == 0xFD2C
            and int(profile["address"], 16) == 0xFD2C
            and profile["bytes"] == 342
            and int(profile["end_exclusive"], 16) == 0xFE82
            and gap["bytes"] + int(gap["address"], 16)
                == int(state["address"], 16)
            and state["bytes"] + int(state["address"], 16)
                == int(profile["address"], 16),
            "Hybrid E000 predecessor geometry drift")
    require("automatically triggers scope triage" in geo["self_defense"]
            and "no negotiation" in geo["self_defense"].lower()
            and value["bank0_text"]["required_noise_headroom_bytes"] == 32
            and value["bank0_text"]["scope_cut_required_bytes"] == 24,
            "Hybrid self-defense or text-noise policy drift")
    candidates = value["scope_cut_candidates"]
    require([(row["id"], row["current_attributed_text_bytes"])
             for row in candidates] == [
                 ("numeric-early-errors", 81),
                 ("visible-block-cursor", 65),
                 ("mid-transaction-media-change-classification", 27)],
            "scope-cut candidate set or price drift")
    selected = value["selection"]["selected_candidate"]
    authorized = value["selection"]["product_source_changes_authorized"]
    require((selected is None and authorized == 0)
            or (selected == "numeric-early-errors" and authorized == 1
                and value["selection"]["selected_attributed_text_bytes"] == 81),
            "scope-cut selection/authorization is not an allowed state")


def main() -> int:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    validate(value)
    require(active["decision"]["e000_active_floor_bytes"] == 54
            and active["decision"]["bank0_text_noise_floor_bytes"] == 32,
            "active C2-lite authority differs from Hybrid contract")
    require(sha(FAILED_MAP) == diagnosis["evidence"]["failed_map"]["sha256"]
            and sha(FAILED_LTO)
                == diagnosis["evidence"]["failed_lto_object"]["sha256"],
            "failed WPLTO pricing evidence identity drift")

    map_text = FAILED_MAP.read_text(encoding="utf-8")
    measured = {
        "scr_cursor": symbol_bytes(map_text, "scr_cursor"),
        "io_disk_transaction_classify_status": symbol_bytes(
            map_text, "io_disk_transaction_classify_status"),
        "lisp65_error_render_pending": symbol_bytes(
            map_text, "lisp65_error_render_pending"),
    }
    require(measured == {
        "scr_cursor": 65,
        "io_disk_transaction_classify_status": 27,
        "lisp65_error_render_pending": 159,
    }, "failed-map candidate symbol size drift")
    disassembly = subprocess.run(
        [str(OBJDUMP), "-dr", "--no-show-raw-insn",
         "--disassemble-symbols=lisp65_error_render_pending", str(FAILED_LTO)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.lower()
    require("       7:" in disassembly
            and "      57:" in disassembly
            and "      58:" in disassembly
            and "r_mos_addr16\t.text.lisp65_error_render_code" in disassembly,
            "resident-error branch boundary disassembly drift")
    resident_branch_bytes = 0x58 - 0x07
    require(resident_branch_bytes == 81,
            "resident-error branch price is not 81 bytes")

    saved = (P.E000_REOPENING, P.BSS_TRIAGE, P.SESSION_EMITTER_STATE_BYTES,
             P.E000_FINAL_FLOOR_BYTES, P.PROFILE_RODATA_BASE)
    try:
        P.E000_REOPENING = True
        P.BSS_TRIAGE = True
        P.configure_session_emitter_state(10)
        P.configure_c2_lite_hybrid_e000_geometry()
        linker = P.linker_script()
    finally:
        (P.E000_REOPENING, P.BSS_TRIAGE, P.SESSION_EMITTER_STATE_BYTES,
         P.E000_FINAL_FLOOR_BYTES, P.PROFILE_RODATA_BASE) = saved
    for token in (
            "profile_rodata 0xfd2c", "+ 0x1d2c)",
            "session_emitter_state 0xfd22 (NOLOAD)",
            "C2 final E000 floor below 54 bytes"):
        require(token in linker, f"generated Hybrid linker truth missing: {token}")

    mutations = []
    for name, mutate in (
        ("floor-53", lambda row: row["e000_geometry"].update(
            active_floor_bytes=53)),
        ("state-old-address", lambda row: row["e000_geometry"][
            "session_emitter_state"].update(address="0xfd08")),
        ("profile-old-address", lambda row: row["e000_geometry"][
            "profile_rodata"].update(address="0xfd12")),
        ("noise-floor-8", lambda row: row["bank0_text"].update(
            required_noise_headroom_bytes=8)),
        ("unselected-candidate", lambda row: row["selection"].update(
            selected_candidate="visible-block-cursor")),
        ("selection-without-authorization", lambda row: row["selection"].update(
            product_source_changes_authorized=0)),
    ):
        changed = copy.deepcopy(value)
        mutate(changed)
        try:
            validate(changed)
        except (GateError, KeyError, TypeError, ValueError):
            mutations.append(name)
        else:
            raise GateError(f"Hybrid mutation was accepted: {name}")

    print(json.dumps({
        "status": "passed-static-hybrid-authority-and-pricing-gate",
        "geometry": {
            "floor_bytes": 54,
            "reopen_gap0": "0xfca2..0xfd21",
            "session_emitter_state": "0xfd22..0xfd2b",
            "profile_rodata_start": "0xfd2c",
            "resolved_overlap_bytes": 26,
        },
        "candidate_attribution_bytes": [81, 65, 27],
        "mutations_rejected": mutations,
        "compiler_runs": 0,
        "linker_runs": 0,
        "product_bytes_changed": 0,
        "wplto_runs": 0,
        "hardware_runs": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, subprocess.CalledProcessError) as error:
        print(f"c2-append-final-hybrid-gate: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
