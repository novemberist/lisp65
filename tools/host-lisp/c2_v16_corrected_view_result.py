#!/usr/bin/env python3
"""Close the v1.6 corrected-view launch contact from stopped-state data."""

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
OWNER_COMMIT = "9b80f78a"
AUTHORIZATION_COMMIT = "1adb9153"
CONTACT_DRIVER_COMMIT = "a1d73327"
PLAN_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
CONTACT_DRIVER_PATH = "tools/host-lisp/c2_v16_corrected_view_contact.py"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-device-receipt.json"
PREPARATION = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-preparation-receipt.json"
CHOREOGRAPHY = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-preparation-receipt.json")
PRIOR = EVIDENCE / "c2.3-v1.6-defstruct-d2-identity-view-desk-attribution-receipt.json"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
WINDOW = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-window.bin"
CORE = ROOT / "build/upstream-verification/mega65-core"
CPU = CORE / "src/vhdl/gs4510.vhdl"
MONITOR = CORE / "src/monitor/monitor.a65"
MACHINE = CORE / "src/vhdl/machine_container.vhdl"
BOOT_MAP = ROOT / "docs/archive/pre-1.0/reference/mega65-lisp-start-path.md"
RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-result-receipt.json"
DRIVER = Path(__file__).resolve()

CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
LIVE_E000 = bytes.fromhex("f724a20fdd54eef005ca10f88018a5d1")
MAPH = 0x8300
MAPL = 0x82A0
PRODUCT_WINDOW_PHYSICAL = 0x087FE000
E000_PROBE = 0xE1B8


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def run(args: list[str], *, cwd: Path = ROOT) -> bytes:
    process = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"] ).decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def decode_rom_flags(tail: str) -> dict[str, bool]:
    token = tail.split()[-1]
    require(len(token) == 8, f"ROM-enable field width drift: {token!r}")
    return {f"{index}:{label}": token[index] != "."
            for index, label in enumerate("reca8lhc")}


def high_map_low20(logical: int, maph: int) -> int:
    enables = (maph >> 12) & 0xF
    offset = maph & 0xFFF
    block = (logical >> 13) & 0x3
    require(logical & 0x8000 and enables & (1 << block),
            "logical address is not selected by MAPH")
    return ((offset + (logical >> 8)) << 8) | (logical & 0xFF)


def required_maph(logical_base: int, target_low20: int) -> int:
    require(logical_base % 0x2000 == target_low20 % 0x2000 == 0,
            "MAP bases must be 8KB aligned")
    block = (logical_base >> 13) & 0x3
    offset = ((target_low20 - logical_base) >> 8) & 0xFFF
    return (1 << (12 + block)) | offset


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    owner_commit, plan = git_blob(OWNER_COMMIT, PLAN_PATH)
    authorization_commit, authorization = git_blob(
        AUTHORIZATION_COMMIT, PLAN_PATH)
    contact_commit, contact_driver = git_blob(
        CONTACT_DRIVER_COMMIT, CONTACT_DRIVER_PATH)
    plan_text = plan.decode("utf-8")
    require("Claim correction and choreography rule — 2026-08-05" in plan_text
            and "The launch outcome is undecidable from this contact" in plan_text
            and "first stop precedes the bound" in plan_text,
            "corrected-view claim-correction authority drift")
    authorization_text = authorization.decode("utf-8")
    require("Recontact authorized — 2026-08-05" in authorization_text
            and "The owner\nauthorizes the repeat contact"
            in authorization_text
            and "recontact_authorized` flips by this decision"
            in authorization_text,
            "corrected-view recontact authorization drift")
    contact_text = contact_driver.decode("utf-8")
    immediate_stop = (
        'SERIAL.monitor_sync(fd, f"#c2v16corrected{index}\\r".encode())\n'
        '            command(fd, b"t1", 0.05)')
    require(immediate_stop in contact_text
            and "FIRST_OBSERVATION_QUIET_SECONDS" not in contact_text,
            "historical immediate-t1 schedule drift")
    device, prep, prior, deployment = (load(path) for path in
                                        (DEVICE, PREPARATION, PRIOR, DEPLOY))
    require(device["status"] == "VIEW-OR-OWNER-FIRST-RED"
            and device["result"]["CPU_left_stopped"]
            and device["result"]["all_state_reads_CPU_view"]
            and device["result"]["MAPH_MAPL_bound_per_sample"]
            and not device["result"]["R_A_I_G_claimed"]
            and device["result"]["measured_forms_run"] == 0,
            "corrected-view device boundary drift")
    require(prep["status"] ==
            "HOST-GREEN; ONE CORRECTED-VIEW CONTACT AUTHORIZED"
            and len(prep["mutations_rejected"]) == 17,
            "historical corrected-view preparation drift")
    choreography = load(CHOREOGRAPHY)
    require(choreography["status"] ==
            "HOST-GREEN; ONE QUIET RECONTACT AUTHORIZED"
            and len(choreography["mutations_rejected"]) == 20
            and choreography["facts"]["appointment"][
                "first_observation_quiet_seconds"] == 27.653
            and choreography["facts"]["appointment"][
                "recontact_authorized"],
            "corrected-view quiet choreography drift")
    require(prior["status"] ==
            "ATTRIBUTED WRONG E000 OWNER PLUS PHYSICAL-RAM VIEW",
            "prior attribution authority drift")
    require(run(["git", "rev-parse", "HEAD"], cwd=CORE).decode().strip() ==
            CORE_COMMIT, "mega65-core authority drift")
    cpu_text, monitor_text, machine_text, boot_text = (
        path.read_text(encoding="utf-8")
        for path in (CPU, MONITOR, MACHINE, BOOT_MAP))
    require('monitor_mem_address_drive(27 downto 16) = x"777"' in cpu_text
            and "reg_offset_high+to_integer(short_address(15 downto 8))"
            in cpu_text and "if reg_map_high(blocknum)='1'" in cpu_text,
            "CPU-view/MAP resolution authority drift")
    require('.byte       "reca8lhc"' in monitor_text
            and "; $26 - ROM enables" in monitor_text,
            "monitor ROM-enable authority drift")
    require("monitor_roms(6) <= rom_at_e000" in machine_text,
            "E000 ROM flag authority drift")
    require("MAPHI=$8300" in boot_text and "ROM-/KERNAL" in boot_text,
            "historical C65/BOOT map authority drift")

    samples = device["samples"]
    require(len(samples) == 3
            and [row["PC"] for row in samples] ==
            ["0xe1c1", "0xe1bc", "0xe1c1"]
            and [row["registers"]["X"] for row in samples] ==
            ["0x0b", "0x06", "0x05"], "live PC/X signature drift")
    require(all(row["mapping"]["MAPH"] == "0x8300"
                and row["mapping"]["MAPL"] == "0x82a0"
                for row in samples), "MAPH/MAPL sample drift")
    flags = [decode_rom_flags(row["mapping"]["raw_tail"])
             for row in samples]
    require(all(not value["1:e"] for value in flags),
            "E000 hardware-ROM flag unexpectedly set")
    require(all(bytes.fromhex(row["E000_owner"]["observed"]) == LIVE_E000
                and row["durable_witness"] == "0xd7"
                and row["freelist_head"] == "0x0000"
                and row["gc_runs"] == 0 for row in samples),
            "live E000/entry/freelist/gc tuple drift")
    require(all(all(raw["command"].startswith("m0777")
                        and raw["view"] == "CPU-resolved-0x0777xxxx"
                        for raw in row["raw"].values()) for row in samples),
            "a stopped-state read escaped CPU view")
    require(b"CMP   $EE54,X" in bytes.fromhex(samples[1]["registers"]["raw_hex"])
            and b"DEX" in bytes.fromhex(samples[0]["registers"]["raw_hex"]),
            "live C65/KERNAL loop disassembly drift")

    observed_low20 = high_map_low20(E000_PROBE, MAPH)
    product_low20 = (PRODUCT_WINDOW_PHYSICAL + E000_PROBE - 0xE000) & 0xFFFFF
    product_maph = required_maph(0xE000, PRODUCT_WINDOW_PHYSICAL & 0xFFFFF)
    require((observed_low20, product_low20, product_maph) ==
            (0x3E1B8, 0xFE1B8, 0x8F00), "MAP/product separation drift")
    window = WINDOW.read_bytes()
    product_bytes = window[E000_PROBE - 0xE000:
                           E000_PROBE - 0xE000 + len(LIVE_E000)]
    require(product_bytes != LIVE_E000
            and deployment["diagnostic"]["preloads"][-1]["address"] ==
            "0x087fe000", "product E000 owner separation drift")

    facts = {
        "view_proof": {
            "samples": 3, "all_memory_commands": "m0777xxxx",
            "MAPH": "0x8300", "MAPL": "0x82a0",
            "ROM_enable_fields": [row["mapping"]["raw_tail"].split()[-1]
                                  for row in samples],
            "E000_hardware_ROM_enabled": False, "CPU_left_stopped": True,
        },
        "code_owner": {
            "live_E000_bytes": LIVE_E000.hex(),
            "product_E000_bytes": product_bytes.hex(),
            "configured_ROM_exact_match": False,
            "observed_MAPHI": "0x8300",
            "observed_low20_at_E1B8": "0x3e1b8",
            "product_required_MAPHI": "0x8f00",
            "product_low20_at_E1B8": "0xfe1b8",
            "selected_owner": "C65/BOOT high-MAP KERNAL/BASIC image; non-product",
            "exact_backing_megabyte_captured": False,
            "symbol_interpretation": "none; ownership precedes symbols",
        },
        "launch": {
            "PCs": [row["PC"] for row in samples],
            "X": [row["registers"]["X"] for row in samples],
            "live_loop": "LDX #$0f; CMP $ee54,X; BEQ; DEX; BPL",
            "entry_witness": [row["durable_witness"] for row in samples],
            "entry_observed_during_samples": False,
            "first_observation_quiet_interval_bound": False,
            "first_observation_action": "monitor-sync then immediate t1",
            "classification": "LAUNCH-OUTCOME-UNDECIDABLE-EARLY-T1",
            "control_launch_divergence_explained": False,
        },
        "correction": {
            "prior_non_product_core_holds": True,
            "prior_exact_MEGA65_ROM_owner_superseded": True,
            "prior_no_handover_claim_withdrawn": True,
            "reason": ("live E000 differs from configured ROM, the E000 ROM "
                       "enable is clear, and MAPH selects a non-product image; "
                       "the immediate t1 leaves launch outcome undecidable"),
        },
        "decision": {
            "launch_boundary_named": "unresolved due to unbounded pre-t1 runtime",
            "product_code_observed_in_samples": False,
            "product_hang_claim": False,
            "F018B_membership_claim": False, "R_A_I_G_claim": False,
            "measured_forms_run": 0, "new_contact_authorized": True,
            "next_step": ("one owner-authorized repeat with the first monitor "
                          "entry at least 27.653 seconds after capture invocation"),
        },
    }
    authorities = {
        "claim_correction": bind_blob(f"git:{owner_commit}:{PLAN_PATH}", plan),
        "recontact_authorization": bind_blob(
            f"git:{authorization_commit}:{PLAN_PATH}", authorization),
        "historical_contact_driver": bind_blob(
            f"git:{contact_commit}:{CONTACT_DRIVER_PATH}", contact_driver),
        "device": bind(DEVICE), "preparation": bind(PREPARATION),
        "quiet_choreography": bind(CHOREOGRAPHY),
        "prior_attribution": bind(PRIOR), "deployment": bind(DEPLOY),
        "diagnostic_window": bind(WINDOW), "core_CPU_MAP": bind(CPU),
        "core_monitor_format": bind(MONITOR), "core_ROM_flags": bind(MACHINE),
        "C65_BOOT_map_history": bind(BOOT_MAP), "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    view, owner = facts["view_proof"], facts["code_owner"]
    launch, correction, decision = (facts[name] for name in
                                     ("launch", "correction", "decision"))
    require(view["all_memory_commands"] == "m0777xxxx"
            and view["MAPH"] == "0x8300" and view["MAPL"] == "0x82a0"
            and not view["E000_hardware_ROM_enabled"]
            and view["CPU_left_stopped"], "view proof drift")
    require(owner["selected_owner"] ==
            "C65/BOOT high-MAP KERNAL/BASIC image; non-product"
            and not owner["configured_ROM_exact_match"]
            and owner["observed_MAPHI"] != owner["product_required_MAPHI"]
            and owner["symbol_interpretation"] ==
            "none; ownership precedes symbols", "code-owner conclusion drift")
    require(not launch["entry_observed_during_samples"]
            and not launch["first_observation_quiet_interval_bound"]
            and launch["first_observation_action"] ==
                "monitor-sync then immediate t1"
            and launch["classification"] ==
                "LAUNCH-OUTCOME-UNDECIDABLE-EARLY-T1"
            and not launch["control_launch_divergence_explained"],
            "launch boundary drift")
    require(correction["prior_non_product_core_holds"]
            and correction["prior_exact_MEGA65_ROM_owner_superseded"]
            and correction["prior_no_handover_claim_withdrawn"],
            "prior-claim correction drift")
    require(not decision["product_code_observed_in_samples"]
            and not decision["product_hang_claim"]
            and not decision["F018B_membership_claim"]
            and not decision["R_A_I_G_claim"]
            and decision["measured_forms_run"] == 0
            and decision["new_contact_authorized"],
            "claim/contact boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "physical-view": (["view_proof", "all_memory_commands"], "m0000xxxx"),
        "discard-MAPH": (["view_proof", "MAPH"], "unknown"),
        "discard-MAPL": (["view_proof", "MAPL"], "unknown"),
        "claim-E000-ROM": (["view_proof", "E000_hardware_ROM_enabled"], True),
        "resume-CPU": (["view_proof", "CPU_left_stopped"], False),
        "select-product-owner":
            (["code_owner", "selected_owner"], "diagnostic-E000-window"),
        "claim-configured-ROM-match":
            (["code_owner", "configured_ROM_exact_match"], True),
        "erase-MAP-separation":
            (["code_owner", "product_required_MAPHI"], "0x8300"),
        "symbolize-before-owner":
            (["code_owner", "symbol_interpretation"], "product ELF"),
        "claim-entry": (["launch", "entry_observed_during_samples"], True),
        "invent-quiet-interval":
            (["launch", "first_observation_quiet_interval_bound"], True),
        "erase-immediate-t1":
            (["launch", "first_observation_action"], "delayed t1"),
        "claim-launch-explained":
            (["launch", "control_launch_divergence_explained"], True),
        "retain-exact-ROM-prior":
            (["correction", "prior_exact_MEGA65_ROM_owner_superseded"], False),
        "retain-no-handover-claim":
            (["correction", "prior_no_handover_claim_withdrawn"], False),
        "claim-product-code":
            (["decision", "product_code_observed_in_samples"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "invent-form": (["decision", "measured_forms_run"], 1),
        "revoke-contact": (["decision", "new_contact_authorized"], False),
    }
    rejected: dict[str, str] = {}
    for label, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ResultError as error:
            rejected[label] = str(error)
        else:
            raise ResultError(f"verification mutation survived: {label}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    rejected = rejected_mutations(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-corrected-view-result-v2",
        "recorded_on": date.today().isoformat(),
        "status": "CORRECTED: NON-PRODUCT SAMPLES; LAUNCH OUTCOME UNDECIDABLE",
        "authorities": authorities, "facts": facts,
        "execution_witnesses": [
            "all stopped-state reads use the CPU-resolved 0x0777 monitor view",
            "MAPH=0x8300 and MAPL=0x82a0 are retained in all three samples",
            "the ROM-enable field proves E000 hardware ROM is not selected",
            "MAP arithmetic places E1B8 at low20 0x3e1b8, not product 0xfe1b8",
            "the live E000 stream is stable and differs from the product window",
            "the live loop and PC/X samples identify the C65/KERNAL context",
            "the durable entry witness remains reset in all three samples",
            "the configured ROM mismatch prevents an exact ROM-image overclaim",
            "the historical runner proves monitor-sync then immediate t1",
            "the absent pre-t1 quiet bound withdraws the no-handover claim",
        ],
        "mutations_rejected": rejected,
        "claim_limit": ("Loud correction of the corrected-view physical RUN. "
                        "It proves a non-product C65/BOOT high-MAP context only "
                        "at the three stopped samples; the launch outcome is "
                        "undecidable because the first t1 had no bound quiet "
                        "interval. No product hang, F018B membership, R/A/I/G "
                        "row, form or fix is claimed. A separate owner decision "
                        "authorizes exactly one quiet-window repeat."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    value = expected()
    if args.action == "write":
        write_json(RESULT, value)
    elif args.action == "check":
        require(RESULT.is_file() and RESULT.read_bytes() == canonical(value),
                "corrected-view result receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-corrected-view-result: FIRST RED: " + str(error))
        raise SystemExit(2)
