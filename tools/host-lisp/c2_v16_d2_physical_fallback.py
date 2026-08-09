#!/usr/bin/env python3
"""Prepare the hook-free physical-owner D2 fallback identity."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PHASE_C = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
SIXTH_RED = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.3-v1.6-defstruct-closing-d2-complete-pair-entry-device-first-red-receipt.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-closing-d2-physical.sh"
OUT = ROOT / "build/c2.3/v1.6-defstruct-d2-physical-fallback"
PHYSICAL_PRG = OUT / "diagnostic-link82-physical.prg"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.6-defstruct-d2-physical-fallback-preparation-receipt.json")
FORMAT = "lisp65-c2.3-v1.6-defstruct-D2-physical-fallback-v1"


class PhysicalFallbackError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhysicalFallbackError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prg_offset(payload: bytes, address: int) -> int:
    require(len(payload) >= 2, "PRG truncated")
    load_address = int.from_bytes(payload[:2], "little")
    require(load_address == 0x2001, "PRG load address drift")
    return 2 + address - load_address


def ranges(before: bytes, after: bytes) -> list[dict[str, Any]]:
    require(len(before) == len(after), "fixed-size physical identity required")
    changed = [i for i, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    result = []
    if not changed:
        return result
    start = prior = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != prior + 1:
            result.append({"address": f"0x{0x2001 + start - 2:04x}",
                           "bytes": prior - start + 1,
                           "before": before[start:prior + 1].hex(),
                           "after": after[start:prior + 1].hex()})
            start = current
        prior = current
    return result


def runner_audit() -> dict[str, Any]:
    source = RUNNER.read_text(encoding="utf-8")
    require("dry-run|stage|continue" in source,
            "physical stage/continue action set absent")
    stage = source.index('if [ "$ACTION" = continue ]')
    owner = source.index("The owner has now typed RUN and RETURN", stage)
    prompt = source.index("screen physical-after-launch", owner)
    context = source.index("# Immediate context asserts", prompt)
    require_form = source.index('quiet_input require "$require_form"', context)
    reset = source.index('run_m65 -H -@ "$reset@$record_hex"', require_form)
    arm = source.index('run_m65 -H -@ "$arm@$record_hex"', reset)
    defstruct = source.index('quiet_input defstruct "$defstruct_form"', arm)
    stable = source.index('readback "$record" 65 "$OUT/record-1.bin"', defstruct)
    require(stage < owner < prompt < context < require_form < reset < arm <
            defstruct < stable,
            "physical launch/measurement ordering drift")
    stage_path = source.index("run_m65 -F; sleep 5; screen fresh-basic")
    ready = source.index('screen physical-launch-ready', stage_path)
    marker = source.index(': > "$OUT/stage.ready"', ready)
    require(stage_path < ready < marker,
            "physical stage readiness ordering drift")
    require('grep -q \'lisp65>\' "$OUT/physical-after-launch.txt"' in source
            and 'grep -Eqi \'BREAK|MONITOR COMMANDS\'' in source,
            "physical launch prompt/fail-closed classification absent")
    require("sleep 120" in source and "sleep 180" in source
            and "record-2.bin" in source and "record-3.bin" in source,
            "quiet/stable-read measurement contract absent")
    require("c2_v16_d2_ram_entry_witness" not in source
            and "virtual_matrix" not in source
            and '"$ENTRY" submit' not in source,
            "virtual or boot-hook launch dependency survived")
    require('run_m65 -H "$product"' in source
            and 'run_m65 -H -1 "$product"' not in source,
            "physical stage does not install the PRG as a BASIC program")
    return {
        "actions": ["dry-run", "stage", "continue"],
        "physical_launch_prompt_required": True,
        "virtual_launch_transport_present": False,
        "boot_entry_hook_helper_present": False,
        "context_asserts_before_forms": True,
        "full_record_reset_between_forms": True,
        "quiet_windows_seconds": [120, 180],
        "stable_record_reads": 3,
        "BASIC_program_loader": "m65 -H without binary -1 mode",
    }


def build_bytes() -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    deployment = load(DEPLOY)
    phase_c = load(PHASE_C)
    sixth = load(SIXTH_RED)
    require(deployment["promotable"] is False
            and phase_c["status"] == "PREPARED-NON-PROMOTABLE-LINK82-DIAGNOSTIC"
            and sixth["status"].endswith("physical-owner fallback active"),
            "physical fallback authority drift")
    diagnostic_path = ROOT / deployment["diagnostic"]["prg"]["path"]
    control_path = ROOT / deployment["control"]["prg"]["path"]
    reset_path = ROOT / deployment["record"]["reset"]["path"]
    require(bind(diagnostic_path) == deployment["diagnostic"]["prg"]
            and bind(control_path) == deployment["control"]["prg"]
            and bind(reset_path) == deployment["record"]["reset"],
            "Phase-C deployment binding drift")
    diagnostic = diagnostic_path.read_bytes()
    control = control_path.read_bytes()
    reset = reset_path.read_bytes()
    witness = deployment["entry_witness"]
    hook = witness["hook"]
    hook_bytes = bytes.fromhex(witness["displaced_bytes_replayed"])
    hook_offset = prg_offset(diagnostic, hook)
    record = int(deployment["record"]["address"], 0)
    record_offset = prg_offset(diagnostic, record)
    require(diagnostic[hook_offset:hook_offset + len(hook_bytes)] ==
            bytes.fromhex("203fc0eaea"), "entry hook authority drift")
    require(control[hook_offset:hook_offset + len(hook_bytes)] == hook_bytes,
            "control startup bytes drift")
    require(len(reset) == deployment["record"]["bytes"] == 65,
            "canonical record geometry drift")
    physical = bytearray(diagnostic)
    physical[hook_offset:hook_offset + len(hook_bytes)] = hook_bytes
    physical[record_offset:record_offset + len(reset)] = reset
    physical = bytes(physical)
    require(physical[hook_offset:hook_offset + len(hook_bytes)] == hook_bytes
            and physical[record_offset:record_offset + len(reset)] == reset,
            "hook-free physical identity construction failed")
    differences = ranges(diagnostic, physical)
    require(len(differences) == 2
            and [row["address"] for row in differences] == ["0x202c", "0xc03f"],
            f"physical fallback difference set drift: {differences}")
    runner = runner_audit()
    load_address = int.from_bytes(physical[:2], "little")
    program_end_exclusive = load_address + len(physical) - 2
    return physical, deployment, {
        "source_diagnostic_to_physical_differences": differences,
        "entry_hook_present": False,
        "boot_record_is_canonical_reset": True,
        "measurement_hooks_changed": 0,
        "product_bytes_changed": 0,
        "promotable": False,
        "virtual_launch_contacts_remaining": 0,
        "launch_method": "physical owner types RUN and RETURN",
        "entry_authority": "physical launch plus visible Workbench prompt",
        "R_A_I_G_record_bytes": 65,
        "R_A_I_G_fields": phase_c["facts"]["instrument"]["record_fields"],
        "runner": runner,
        "BASIC_staging": {
            "load_address": load_address,
            "loaded_payload_bytes": len(physical) - 2,
            "loaded_end_exclusive": program_end_exclusive,
            "program_end_pointer": program_end_exclusive,
            "program_end_pointer_encloses_loaded_program": True,
        },
    }


def audit(value: dict[str, Any]) -> None:
    require(not value["entry_hook_present"]
            and value["boot_record_is_canonical_reset"]
            and value["measurement_hooks_changed"] == 0
            and value["product_bytes_changed"] == 0
            and not value["promotable"]
            and value["virtual_launch_contacts_remaining"] == 0
            and value["launch_method"] == "physical owner types RUN and RETURN"
            and value["entry_authority"] ==
            "physical launch plus visible Workbench prompt"
            and value["R_A_I_G_record_bytes"] == 65
            and value["R_A_I_G_fields"] == 29
            and value["runner"] == {
                "actions": ["dry-run", "stage", "continue"],
                "physical_launch_prompt_required": True,
                "virtual_launch_transport_present": False,
                "boot_entry_hook_helper_present": False,
                "context_asserts_before_forms": True,
                "full_record_reset_between_forms": True,
                "quiet_windows_seconds": [120, 180],
                "stable_record_reads": 3,
                "BASIC_program_loader": "m65 -H without binary -1 mode",
            }
            and value["BASIC_staging"] == {
                "load_address": 0x2001,
                "loaded_payload_bytes": 41564,
                "loaded_end_exclusive": 0xC25D,
                "program_end_pointer": 0xC25D,
                "program_end_pointer_encloses_loaded_program": True,
            }
            and [row["address"] for row in
                 value["source_diagnostic_to_physical_differences"]] ==
            ["0x202c", "0xc03f"],
            "physical fallback contract drift")


def mutations(base: dict[str, Any]) -> dict[str, str]:
    cases = {
        "retain-entry-hook": (["entry_hook_present"], True),
        "retain-boot-routine": (["boot_record_is_canonical_reset"], False),
        "change-measurement-hook": (["measurement_hooks_changed"], 1),
        "claim-product-delta": (["product_bytes_changed"], 1),
        "make-promotable": (["promotable"], True),
        "reopen-virtual-loop": (["virtual_launch_contacts_remaining"], 1),
        "virtual-entry-authority": (["entry_authority"], "virtual transport"),
        "shrink-record": (["R_A_I_G_record_bytes"], 64),
        "binary-stage-empty-BASIC-pointer":
        (["BASIC_staging", "program_end_pointer"], 0x2001),
    }
    rejected = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base); trial[path[0]] = replacement
        try:
            audit(trial)
        except PhysicalFallbackError as error:
            rejected[name] = str(error)
        else:
            raise PhysicalFallbackError(f"physical fallback mutation survived: {name}")
    require(len(rejected) == 9, "physical fallback mutation count drift")
    return rejected


def expected() -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    physical, deployment, value = build_bytes()
    audit(value); rejected = mutations(value)
    deployment_out = {
        "format": FORMAT + "-deployment",
        "status": "prepared-physical-owner-fallback",
        "physical_prg": {"path": PHYSICAL_PRG.relative_to(ROOT).as_posix(),
                         "bytes": len(physical),
                         "sha256": hashlib.sha256(physical).hexdigest()},
        "phase_c_deployment": bind(DEPLOY),
        "library_medium": deployment["library_medium"],
        "diagnostic_preloads": deployment["diagnostic"]["preloads"],
        "library_remote": deployment["library_remote"],
        "record": deployment["record"],
        "forms": deployment["forms"],
    }
    receipt = {
        "format": FORMAT,
        "recorded_on": date.today().isoformat(),
        "status": "prepared-hook-free-physical-owner-fallback",
        "facts": value,
        "mutations_rejected": rejected,
        "execution_witnesses": 2 + len(rejected),
        "authorities": {"plan": bind(PLAN), "phase_C": bind(PHASE_C),
                        "phase_C_deployment": bind(DEPLOY),
                        "sixth_setup_First_Red": bind(SIXTH_RED),
                        "runner": bind(RUNNER), "driver": bind(Path(__file__))},
        "claim_limit": "One hook-free non-promotable physical-launch identity; no product byte, device result, measured form or R/A/I/G row.",
    }
    return physical, deployment_out, receipt


def prepare() -> int:
    physical, deployment, receipt = expected()
    OUT.mkdir(parents=True, exist_ok=True)
    PHYSICAL_PRG.write_bytes(physical)
    write_json(DEPLOYMENT, deployment)
    write_json(RECEIPT, receipt)
    print("D2 PHYSICAL FALLBACK PREPARED hook=absent record=canonical "
          "BASIC-end=$C25D mutations=9 hardware=0")
    return 0


def check() -> int:
    physical, deployment, receipt = expected()
    require(PHYSICAL_PRG.is_file() and PHYSICAL_PRG.read_bytes() == physical,
            "physical fallback PRG drift")
    require(load(DEPLOYMENT) == deployment and load(RECEIPT) == receipt,
            "physical fallback receipt/deployment drift")
    print("D2 PHYSICAL FALLBACK PASS hook=absent record=canonical "
          "BASIC-end=$C25D mutations=9 hardware=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "prepare", "check"))
    args = parser.parse_args()
    if args.action == "selftest":
        _physical, _deployment, value = build_bytes()
        audit(value); rejected = mutations(value)
        print(f"D2 PHYSICAL FALLBACK SELFTEST PASS mutations={len(rejected)} "
              "BASIC-pointer=encloses-payload")
        return 0
    return prepare() if args.action == "prepare" else check()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PhysicalFallbackError as error:
        print(f"D2 PHYSICAL FALLBACK FIRST RED: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)
