#!/usr/bin/env python3
"""Attribute the residual v1.6 physical-launch boundary without hardware."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
COMMISSION_COMMIT = "9532b6a6"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PREPARATION = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-preparation-receipt.json"
DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-device-receipt.json"
RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-result-receipt.json"
PHYSICAL = EVIDENCE / "c2.3-v1.6-defstruct-d2-physical-fallback-preparation-receipt.json"
LINK86 = EVIDENCE / "c2.3-v1.3-link86-consumer-path-host-elf-attribution-receipt.json"
DEPLOYMENT = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
PRELAUNCH = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                    "d2-corrected-view-quiet-appointment/prelaunch-cpu-view.json")
STAGED = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                 "d2-control-shaped-discriminator/diagnostic-prg-payload.bin")
OLD_MONITOR = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                      "d2-ram-entry-witness-complete-map/launch-before-return.txt")
VICIV = ROOT / "build/upstream-verification/mega65-core/src/vhdl/viciv.vhdl"
CPU = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
MACHINE = ROOT / ("build/upstream-verification/mega65-core/src/vhdl/"
                  "machine_container.vhdl")
MONITOR = ROOT / "build/upstream-verification/mega65-core/src/monitor/monitor.a65"
ANNOTATIONS = ROOT / ("build/upstream-verification/mega65-core/src/_unused/"
                      "c65-rom-annotations.txt")
RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-d2-residual-launch-boundary-attribution-receipt.json"
DRIVER = Path(__file__).resolve()


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": digest(raw),
    }


def run(args: list[str]) -> bytes:
    process = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"]).decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def prg_bytes(raw: bytes, address: int, count: int) -> bytes:
    require(len(raw) >= 2, "truncated PRG")
    load_address = int.from_bytes(raw[:2], "little")
    offset = 2 + address - load_address
    require(offset >= 2 and offset + count <= len(raw),
            f"PRG range outside delivery: {address:#x}+{count}")
    return raw[offset:offset + count]


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    commit, commission = git_blob(COMMISSION_COMMIT, PLAN)
    commission_text = commission.decode("utf-8")
    require("Residual launch boundary — desk commission 2026-08-05" in commission_text
            and "Read the monitor's own testimony" in commission_text
            and "Delivery-extent audit of the hook path" in commission_text,
            "desk commission drift")

    prep = load(PREPARATION)
    device = load(DEVICE)
    prior = load(RESULT)
    physical = load(PHYSICAL)
    link86 = load(LINK86)
    deployment = load(DEPLOYMENT)
    prelaunch = load(PRELAUNCH)

    require(prep["status"] == "HOST-GREEN; ONE CONTROL-SHAPED CONTACT AUTHORIZED"
            and device["result"]["CPU_left_stopped"]
            and prior["facts"]["launch"]["first_executable_diagnostic_delta"] ==
                "0x202c",
            "consumed-contact authority drift")

    # Rung 1: neither of the two load-bearing contacts captured the screen after
    # physical RETURN. The only readable $C802 row belongs to an older,
    # explicitly unhealthy pre-RETURN setup and cannot be promoted.
    device_dir = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                         "d2-control-shaped-discriminator")
    current_screens = sorted(
        path.name for path in device_dir.iterdir()
        if path.suffix in (".txt", ".png")
        and ("after" in path.name.lower() or "post" in path.name.lower()))
    require(current_screens == [], "unexpected post-RUN capture appeared")
    require("screen" not in json.dumps(device.get("authorities", {})).lower()
            and "screen" not in json.dumps(prior.get("authorities", {})).lower(),
            "load-bearing receipt unexpectedly gained screen authority")
    old_screen = OLD_MONITOR.read_text(encoding="utf-8")
    require("BREAK" in old_screen and "; 00C802 " in old_screen,
            "historical pre-RETURN monitor row drift")

    # Rung 2a: physical delivery really is complete. The exact staged payload
    # includes both the call and its body, and BASIC's installed-program end
    # pointer encloses both.
    prg_path = ROOT / prep["facts"]["identity"]["diagnostic_PRG"]["path"]
    prg = prg_path.read_bytes()
    staged = STAGED.read_bytes()
    load_address = int.from_bytes(prg[:2], "little")
    end_exclusive = load_address + len(prg) - 2
    require(load_address == 0x2001 and end_exclusive == 0xC25D,
            "diagnostic PRG extent drift")
    require(staged == prg[2:], "physical staged payload differs from PRG")
    require(physical["facts"]["BASIC_staging"]["program_end_pointer"] ==
            end_exclusive,
            "BASIC program-end pointer drift")
    hook = prg_bytes(prg, 0x202C, 5)
    routine = prg_bytes(prg, 0xC03F, 9)
    require(hook == bytes.fromhex("203fc0eaea")
            and routine == bytes.fromhex("a2448e30d08ec3b560"),
            "entry hook/body bytes drift")
    require(all(not (int(row["address"], 16) < end_exclusive
                         and int(row["address"], 16) + row["bytes"] > load_address)
                for row in deployment["diagnostic"]["preloads"]),
            "extended preload overlaps BASIC PRG")

    # Rung 2b: delivered-to-RAM is not delivered-to-the-CPU. The prior exact
    # staged prelaunch row has ROMC set. Core truth maps C000 reads to ROM while
    # that bit is set. The control clears it at $202C; the diagnostic instead
    # calls into $C03F before replaying that very clear operation.
    tail = prelaunch["registers"]["tail"].split()[-1]
    require(tail == "..c..l.c", "prelaunch ROM flag row drift")
    monitor_text = MONITOR.read_text(encoding="utf-8")
    machine_text = MACHINE.read_text(encoding="utf-8")
    viciv_text = VICIV.read_text(encoding="utf-8")
    cpu_text = CPU.read_text(encoding="utf-8")
    require('.byte       "reca8lhc"' in monitor_text
            and "monitor_roms(5) <= rom_at_c000;" in machine_text,
            "monitor ROM-flag decoder drift")
    require("$D030.5 VIC-III:ROMC Map C65 ROM @ $C000" in viciv_text
            and "rom_at_c000 <= fastio_wdata(5);" in viciv_text,
            "D030 ROMC contract drift")
    require("if (blocknum=12) and (rom_at_c000='1') then" in cpu_text
            and 'temp_address(27 downto 12) := x"002C";' in cpu_text,
            "CPU C000 ROM mapping drift")
    inherited = link86["facts"]["false_green"]["pre_fix_live_a1_a2"][0]
    runtime_d030 = int(link86["facts"]["false_green"]["runtime_d030_immediate"], 16)
    require(inherited == 0x64 and runtime_d030 == 0x44
            and inherited & 0x20 and not runtime_d030 & 0x20,
            "captured inherited/runtime D030 relationship drift")
    control_prg = (ROOT / deployment["control"]["prg"]["path"]).read_bytes()
    require(prg_bytes(control_prg, 0x202C, 5) == bytes.fromhex("a2448e30d0"),
            "control bootstrap no longer clears ROMC in low RAM")

    annotations = ANNOTATIONS.read_text(encoding="utf-8")
    require("0314   iirq             ;IRQ" in annotations
            and "0316   ibrk             ;BRK" in annotations
            and "0318   inmi             ;NMI" in annotations
            and "FF0B   monitor_brk      ;BRK handler (Monitor)" in annotations,
            "BRK/IRQ/NMI vector inventory drift")

    facts = {
        "monitor_testimony": {
            "owner_observed_spontaneous_monitor": True,
            "both_load_bearing_contacts_lack_post_RUN_screen_authority": True,
            "current_post_RUN_screen_capture_bound": False,
            "entry_PC_recoverable_from_bound_current_captures": False,
            "historical_PC_0xC802_rejected": True,
            "historical_rejection_reason":
                "older unhealthy pre-RETURN setup, not either load-bearing sighting",
            "BRK_class_consistent": True,
            "exact_live_vector_or_entry_PC_claimed": False,
        },
        "physical_delivery": {
            "load_address": "0x2001",
            "end_exclusive": "0xc25d",
            "payload_bytes": len(staged),
            "staged_payload_byteidentical": True,
            "BASIC_program_end_pointer": "0xc25d",
            "hook": {"address": "0x202c", "bytes": hook.hex()},
            "routine": {"address": "0xc03f", "bytes": routine.hex()},
            "all_hook_bytes_physically_delivered": True,
            "extended_preloads_overlap_PRG": False,
            "literal_missing_extent_hypothesis": False,
        },
        "CPU_view_delivery": {
            "prelaunch_ROM_flags": tail,
            "ROMC_enabled_before_runtime": True,
            "captured_inherited_D030": "0x64",
            "runtime_D030": "0x44",
            "ROMC_bit": 5,
            "control_order": ["LDX #$44", "STX $D030", "continue in low RAM"],
            "diagnostic_order": ["JSR $C03F", "replay LDX #$44/STX $D030 in target"],
            "C03F_CPU_view_at_call": "C65 ROM while ROMC remains set",
            "C03F_physical_underlay": "delivered diagnostic routine",
            "witness_store_reachable_in_CPU_view": False,
        },
        "attribution": {
            "mechanism": "bootstrap-hook-target-hidden-by-inherited-ROMC",
            "mechanism_attributed": True,
            "first_divergence":
                "$202C JSR fetches its $C03F target through the still-mapped C000 ROM",
            "why_control_boots":
                "control clears ROMC from low RAM before any C000 bootstrap target",
            "why_witness_stays_reset":
                "the CPU never sees the physically delivered $C03F witness routine",
            "scope": "non-promotable diagnostic identity only",
            "product_loader_exonerated": True,
            "F018B_membership_claim": False,
            "R_A_I_G_claim": False,
        },
        "decision": {
            "new_device_contact_authorized": False,
            "measured_forms_run": 0,
            "product_bytes_changed": 0,
            "fix_implemented": False,
            "CPU_remains_stopped": True,
            "next_owner_question":
                "authorize a diagnostic-only bootstrap repair before D2 resumes",
        },
    }
    authorities = {
        "commission": bind_blob(f"git:{commit}:{PLAN}", commission),
        "preparation": bind(PREPARATION), "device": bind(DEVICE),
        "prior_result": bind(RESULT), "physical_staging": bind(PHYSICAL),
        "link86_live_D030": bind(LINK86), "deployment": bind(DEPLOYMENT),
        "diagnostic_PRG": bind(prg_path), "physical_payload": bind(STAGED),
        "prelaunch_CPU_view": bind(PRELAUNCH),
        "excluded_old_monitor_screen": bind(OLD_MONITOR),
        "core_D030": bind(VICIV), "core_CPU_mapping": bind(CPU),
        "core_monitor_wiring": bind(MACHINE), "monitor_format": bind(MONITOR),
        "vector_inventory": bind(ANNOTATIONS), "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    monitor = facts["monitor_testimony"]
    physical = facts["physical_delivery"]
    view = facts["CPU_view_delivery"]
    attribution = facts["attribution"]
    decision = facts["decision"]
    require(monitor["owner_observed_spontaneous_monitor"]
            and monitor["both_load_bearing_contacts_lack_post_RUN_screen_authority"]
            and not monitor["current_post_RUN_screen_capture_bound"]
            and not monitor["entry_PC_recoverable_from_bound_current_captures"]
            and monitor["historical_PC_0xC802_rejected"]
            and monitor["BRK_class_consistent"]
            and not monitor["exact_live_vector_or_entry_PC_claimed"],
            "monitor testimony claim drift")
    require(physical["load_address"] == "0x2001"
            and physical["end_exclusive"] == "0xc25d"
            and physical["staged_payload_byteidentical"]
            and physical["BASIC_program_end_pointer"] == "0xc25d"
            and physical["all_hook_bytes_physically_delivered"]
            and not physical["extended_preloads_overlap_PRG"]
            and not physical["literal_missing_extent_hypothesis"],
            "physical delivery conclusion drift")
    require(view["prelaunch_ROM_flags"] == "..c..l.c"
            and view["ROMC_enabled_before_runtime"]
            and view["captured_inherited_D030"] == "0x64"
            and view["runtime_D030"] == "0x44" and view["ROMC_bit"] == 5
            and view["diagnostic_order"][0] == "JSR $C03F"
            and view["C03F_CPU_view_at_call"] ==
                "C65 ROM while ROMC remains set"
            and not view["witness_store_reachable_in_CPU_view"],
            "CPU-view delivery conclusion drift")
    require(attribution["mechanism"] ==
                "bootstrap-hook-target-hidden-by-inherited-ROMC"
            and attribution["mechanism_attributed"]
            and attribution["scope"] == "non-promotable diagnostic identity only"
            and attribution["product_loader_exonerated"]
            and not attribution["F018B_membership_claim"]
            and not attribution["R_A_I_G_claim"],
            "attribution boundary drift")
    require(not decision["new_device_contact_authorized"]
            and decision["measured_forms_run"] == 0
            and decision["product_bytes_changed"] == 0
            and not decision["fix_implemented"]
            and decision["CPU_remains_stopped"],
            "decision boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "invent-current-screen":
            (["monitor_testimony", "current_post_RUN_screen_capture_bound"], True),
        "invent-prior-screen":
            (["monitor_testimony", "both_load_bearing_contacts_lack_post_RUN_screen_authority"], False),
        "invent-entry-PC":
            (["monitor_testimony", "entry_PC_recoverable_from_bound_current_captures"], True),
        "promote-old-C802":
            (["monitor_testimony", "historical_PC_0xC802_rejected"], False),
        "claim-exact-vector":
            (["monitor_testimony", "exact_live_vector_or_entry_PC_claimed"], True),
        "truncate-PRG": (["physical_delivery", "end_exclusive"], "0xc03f"),
        "deny-stage-equality":
            (["physical_delivery", "staged_payload_byteidentical"], False),
        "invent-missing-body":
            (["physical_delivery", "all_hook_bytes_physically_delivered"], False),
        "restore-literal-extent-hypothesis":
            (["physical_delivery", "literal_missing_extent_hypothesis"], True),
        "clear-ROMC-before-runtime":
            (["CPU_view_delivery", "ROMC_enabled_before_runtime"], False),
        "change-ROMC-bit": (["CPU_view_delivery", "ROMC_bit"], 4),
        "claim-RAM-visible-C03F":
            (["CPU_view_delivery", "C03F_CPU_view_at_call"], "diagnostic RAM"),
        "claim-witness-reachable":
            (["CPU_view_delivery", "witness_store_reachable_in_CPU_view"], True),
        "erase-mechanism": (["attribution", "mechanism_attributed"], False),
        "rename-mechanism": (["attribution", "mechanism"], "physical extent hole"),
        "blame-product": (["attribution", "product_loader_exonerated"], False),
        "claim-F018B": (["attribution", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (["attribution", "R_A_I_G_claim"], True),
        "authorize-contact": (["decision", "new_device_contact_authorized"], True),
        "invent-form": (["decision", "measured_forms_run"], 1),
        "invent-product-byte": (["decision", "product_bytes_changed"], 1),
        "claim-fix": (["decision", "fix_implemented"], True),
        "resume-CPU": (["decision", "CPU_remains_stopped"], False),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"verification mutation survived: {name}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-residual-launch-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED: DIAGNOSTIC $C03F TARGET HIDDEN BY ROMC",
        "authorities": authorities,
        "facts": facts,
        "mutations_rejected": rejected_mutations(facts),
        "claim_limit": (
            "Desk-only attribution of the non-promotable diagnostic launch. "
            "The hook body was physically staged, but the CPU fetched C65 ROM "
            "at $C03F because the hook moved the ROMC-clearing store behind its "
            "own C000 call. No exact monitor entry PC, product defect, F018B or "
            "R/A/I/G result, measured form, fix or new contact is claimed."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    value = expected()
    if args.action == "write":
        write_json(RECEIPT, value)
    elif args.action == "check":
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "residual launch attribution receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-residual-launch-boundary: FIRST RED: " + str(error))
        raise SystemExit(2)
