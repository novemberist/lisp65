#!/usr/bin/env python3
"""Attribute the consumed v1.6 durable-progress identity/view contradiction."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PLAN_COMMIT = "3df953a5"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-device-receipt.json")
PRIOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-first-red-receipt.json")
CONTROL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
RUNNER = ROOT / "tools/host-lisp/c2_v16_boot_durable_progress.py"
WINDOW = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-window.bin")
ROM_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_MONITOR = CORE / "src/monitor/monitor.a65"
M65_REPO = Path(os.environ.get(
    "LISP65_MEGA65_TOOLS_REPOSITORY",
    str(ROOT / "tools/m65tools")))
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-identity-view-desk-attribution-receipt.json")
DRIVER = Path(__file__).resolve()

CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
M65_COMMIT = "c5bf0ccd7ec6398290176f8af928d0780482577f"
ROM_SHA = "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0"
PRODUCT_SLICE_START = 0xE1B8
PRODUCT_SLICE_END = 0xE1D0
ROM_SLICE_START = 0xE1B8
ROM_SLICE_END = 0xE1D0


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def run(args: list[str], *, cwd: Path) -> bytes:
    process = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    return run(["git", "show", f"{commit}:{path}"], cwd=repo)


def rom_path() -> Path:
    contract = load(ROM_CONTRACT)
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.endswith("MEGA65.ROM"):
            candidates.append(value)

    walk(contract)
    require(len(set(candidates)) == 1, "exactly one configured MEGA65.ROM required")
    return Path(candidates[0]).expanduser()


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    plan_raw = git_blob(ROOT, PLAN_COMMIT, PLAN.relative_to(ROOT).as_posix())
    plan = plan_raw.decode("utf-8")
    require("BOOT-ENTRY-IDENTITY first red — desk commission 2026-08-05"
            in plan, "owner commission absent from plan")
    deployment = load(DEPLOY)
    device = load(DEVICE)
    prior = load(PRIOR)
    control = load(CONTROL)
    require(device["status"] == "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
            "consumed contact status drift")
    require(prior["facts"]["contradiction"]["classification"] ==
            "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
            "prior contradiction boundary drift")
    require(control["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control["control_identity"]["physical_RUN"] is True
            and control["control_identity"]["screen_result"]["visible_REPL"]
            is True, "control physical-launch authority drift")

    product = WINDOW.read_bytes()
    require(len(product) == 0x2000, "diagnostic E000 window size drift")
    require(deployment["diagnostic"]["window"] == bind(WINDOW),
            "deployment/window binding drift")
    rom = rom_path()
    rom_bytes = rom.read_bytes()
    require(digest(rom_bytes) == ROM_SHA and len(rom_bytes) == 0x20000,
            "configured MEGA65 ROM drift")
    cpu_rom = rom_bytes[0x10000:]
    product_slice = product[
        PRODUCT_SLICE_START - 0xE000:PRODUCT_SLICE_END - 0xE000]
    rom_slice = cpu_rom[ROM_SLICE_START:ROM_SLICE_END]
    require(product_slice.hex() ==
            "068a69008507a41fb1048504a001b106aa"
            "a50420e8b518a5",
            "product E1B8..E1CF instruction slice drift")
    require(rom_slice.hex() ==
            "80288adff724a20fdd6deef005ca10f8"
            "8018a5d1d012bd00",
            "KERNAL E1B8..E1CF instruction slice drift")

    samples = device["samples"]
    pcs = [row["PC"] for row in samples]
    x_values = [row["registers"]["X"] for row in samples]
    require(pcs == ["0xe1bc", "0xe1c2", "0xe1c2"]
            and x_values == ["0x08", "0x07", "0x06"],
            "sampled PC/X signature drift")
    require([row["durable_witness"] for row in samples] == ["0xd7"] * 3
            and [row["gc_runs"] for row in samples] == [0, 0, 0],
            "physical RAM witness tuple drift")

    core_head = run(["git", "rev-parse", "HEAD"], cwd=CORE).decode().strip()
    require(core_head == CORE_COMMIT, "mega65-core authority drift")
    cpu_source = CORE_CPU.read_text(encoding="utf-8")
    monitor_source = CORE_MONITOR.read_text(encoding="utf-8")
    runner_source = RUNNER.read_text(encoding="utf-8")
    require('monitor_mem_address_drive(27 downto 16) = x"777"'
            in cpu_source
            and "M777xxxx in serial monitor reads memory from CPU's perspective"
            in cpu_source
            and "memory_access_resolve_address := '0';" in cpu_source,
            "core monitor-view contract drift")
    require("MAPH MAPL" in monitor_source and "RECA8LHC" in monitor_source
            and ".byte       $06,$05,$81,$82,$83,$84,$8a,$8c,$0b,$90,$11,$8d,$0e"
            in monitor_source, "monitor register-row mapping fields drift")
    require('f"m{address:08x}"' in runner_source
            and 'names = ("PC", "A", "X", "Y", "Z", "B", "SP")'
            in runner_source, "durable runner read path drift")
    for address in (0xB5C3, 0x003D, 0xB9F0, 0x0016):
        require((address >> 16) != 0x777,
                "historical read unexpectedly used CPU-view magic")

    tools_common = git_blob(M65_REPO, M65_COMMIT, "src/tools/m65common.c")
    common_text = tools_common.decode("utf-8")
    require('snprintf(cmd, 79, "m%X\\r", (unsigned int)addr);'
            in common_text and "Fetch a block of RAM" in common_text,
            "m65 monitor-read source authority drift")

    facts = {
        "sample_signature": {
            "PCs": pcs,
            "X_values": x_values,
            "durable_witness": ["0xd7", "0xd7", "0xd7"],
            "gc_runs": [0, 0, 0],
            "stable_BASIC_echo": "owner-bound hint; not promoted alone",
        },
        "code_owner_binding": {
            "product_E000": {
                "slice": "0xe1b8..0xe1cf",
                "bytes": product_slice.hex(),
                "at_E1BC": "STA $07",
                "at_E1C2": "STA $04",
                "contains_descending_X_search_loop": False,
            },
            "kernal_ROM": {
                "slice": "0xe1b8..0xe1cf",
                "bytes": rom_slice.hex(),
                "loop": "LDX #$0f; CMP $ee6d,X; BEQ exit; DEX; BPL loop",
                "loop_PC_fetch_span": "0xe1be..0xe1c7",
                "contains_descending_X_search_loop": True,
            },
            "selected_owner": "MEGA65-KERNAL-ROM",
            "why": (
                "the sampled E1xx PC/X signature matches the KERNAL's descending "
                "table search, while the physical entry sentinel proves the "
                "diagnostic $202C path never ran"),
        },
        "monitor_view": {
            "register_PC_source": "CPU history/register state",
            "register_row_exposes": ["MAPH", "MAPL", "ROM-enable-flags"],
            "register_fields_retained_by_runner":
                ["PC", "A", "X", "Y", "Z", "B", "SP"],
            "mapping_fields_retained_by_runner": False,
            "memory_commands": [
                "m0000b5c3", "m0000003d", "m0000b9f0", "m00000016"],
            "memory_view": "28-bit-physical-bank0-unresolved",
            "CPU_view_magic_used": False,
            "CPU_view_magic": "0x0777xxxx",
            "memory_values_valid_as_physical_RAM": True,
            "memory_values_prove_executing_CPU_view": False,
        },
        "control_reconciliation": {
            "control_physical_RUN_reached_visible_REPL": True,
            "control_proves_environment_can_launch": True,
            "control_proves_diagnostic_contact_entered": False,
            "diagnostic_entry_stamp_observed": False,
            "diagnostic_post_RUN_screen_or_mapping_proof_retained": False,
            "explanation": (
                "the control row has its own post-RUN prompt postcondition; the "
                "diagnostic row has only pre-RUN staging identity plus later "
                "samples. Byteidentical staging capability is not execution "
                "identity for a separate physical launch"),
        },
        "decision": {
            "named_mechanism": (
                "address-only product-ELF symbolization was applied to KERNAL-owned "
                "E000 PCs, then combined with unresolved physical bank-0 monitor "
                "reads after the diagnostic entry witness had not fired"),
            "wrong_code_owner": True,
            "wrong_read_view_for_CPU_identity_claim": True,
            "diagnostic_launch_entry_proved": False,
            "prior_root_scan_claim_valid": False,
            "product_hang_claim": False,
            "F018B_membership_claim": False,
            "R_A_I_G_claim": False,
            "new_device_contact_authorized": False,
            "required_shape_before_owner_contact_question": (
                "retain raw r-row MAPH/MAPL/ROM flags or otherwise prove the E000 "
                "owner, and use 0x0777xxxx CPU-view reads (or a CPU-side RAM copy) "
                "for every state value compared with executing code"),
        },
    }
    authorities = {
        "plan": bind_blob(PLAN.relative_to(ROOT).as_posix(), plan_raw),
        "deployment": bind(DEPLOY), "device": bind(DEVICE),
        "prior_first_red": bind(PRIOR), "control": bind(CONTROL),
        "durable_runner": bind(RUNNER), "diagnostic_window": bind(WINDOW),
        "ROM_contract": bind(ROM_CONTRACT), "MEGA65_ROM": bind(rom),
        "core_CPU_view": bind(CORE_CPU), "core_monitor_format": bind(CORE_MONITOR),
        "m65_fetch_ram_source": bind_blob(
            f"mega65-tools@{M65_COMMIT}:src/tools/m65common.c", tools_common),
        "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    owner = facts["code_owner_binding"]
    view = facts["monitor_view"]
    control = facts["control_reconciliation"]
    decision = facts["decision"]
    require(owner["selected_owner"] == "MEGA65-KERNAL-ROM"
            and owner["kernal_ROM"]["contains_descending_X_search_loop"]
            and not owner["product_E000"]["contains_descending_X_search_loop"],
            "E000 owner attribution drift")
    require(view["memory_view"] == "28-bit-physical-bank0-unresolved"
            and not view["CPU_view_magic_used"]
            and not view["mapping_fields_retained_by_runner"]
            and view["memory_values_valid_as_physical_RAM"]
            and not view["memory_values_prove_executing_CPU_view"],
            "monitor-view attribution drift")
    require(control["control_physical_RUN_reached_visible_REPL"]
            and control["control_proves_environment_can_launch"]
            and not control["control_proves_diagnostic_contact_entered"]
            and not control["diagnostic_entry_stamp_observed"],
            "control reconciliation drift")
    require(decision["wrong_code_owner"]
            and decision["wrong_read_view_for_CPU_identity_claim"]
            and not decision["diagnostic_launch_entry_proved"]
            and not decision["prior_root_scan_claim_valid"]
            and not decision["product_hang_claim"]
            and not decision["F018B_membership_claim"]
            and not decision["R_A_I_G_claim"]
            and not decision["new_device_contact_authorized"],
            "claim/contact boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "select-product-E000-owner":
            (["code_owner_binding", "selected_owner"], "diagnostic-product-window"),
        "invent-product-X-loop":
            (["code_owner_binding", "product_E000",
              "contains_descending_X_search_loop"], True),
        "erase-kernal-X-loop":
            (["code_owner_binding", "kernal_ROM",
              "contains_descending_X_search_loop"], False),
        "reinterpret-m-as-CPU-view":
            (["monitor_view", "memory_view"], "CPU-mapped-logical"),
        "claim-777-magic-used":
            (["monitor_view", "CPU_view_magic_used"], True),
        "claim-mapping-fields-retained":
            (["monitor_view", "mapping_fields_retained_by_runner"], True),
        "claim-physical-values-prove-CPU-view":
            (["monitor_view", "memory_values_prove_executing_CPU_view"], True),
        "promote-control-to-diagnostic-entry-proof":
            (["control_reconciliation", "control_proves_diagnostic_contact_entered"],
             True),
        "claim-diagnostic-entry":
            (["decision", "diagnostic_launch_entry_proved"], True),
        "retain-root-scan-claim":
            (["decision", "prior_root_scan_claim_valid"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "authorize-contact": (["decision", "new_device_contact_authorized"], True),
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
        except AttributionError as error:
            rejected[label] = str(error)
        else:
            raise AttributionError(f"verification mutation survived: {label}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    rejected = rejected_mutations(facts)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-identity-view-desk-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED WRONG E000 OWNER PLUS PHYSICAL-RAM VIEW",
        "authorities": authorities,
        "facts": facts,
        "execution_witnesses": [
            "both E000 candidate byte streams are bound independently",
            "the KERNAL stream contains the observed descending-X search loop",
            "the product stream at both sampled addresses contains ordinary stores",
            "the diagnostic entry sentinel remains reset in all three samples",
            "the core reserves 0x0777xxxx, not 0x0000xxxx, for CPU-view monitor reads",
            "the runner used only unresolved 0x0000xxxx memory commands",
            "the monitor register row exposed mapping/ROM fields that the runner discarded",
            "the separate control row owns an explicit post-RUN prompt postcondition",
        ],
        "mutations_rejected": rejected,
        "claim_limit": (
            "Desk attribution of the consumed identity/view contradiction only. "
            "It names KERNAL E000 ownership plus unresolved physical-RAM reads, "
            "withdraws every root-scan interpretation, and authorizes no hardware, "
            "product/diagnostic fix, measured form, F018B membership or R/A/I/G row."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_receipt(value: dict[str, Any]) -> None:
    payload = canonical(value)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RESULT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(RESULT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        facts, _ = exact_facts()
        audit(facts)
        rejected = rejected_mutations(facts)
        value: dict[str, Any] = {
            "status": "SELFTEST PASS", "mutations": len(rejected)}
    else:
        value = expected()
        if args.action == "write":
            write_receipt(value)
        else:
            require(RESULT.is_file() and RESULT.read_bytes() == canonical(value),
                    "identity/view attribution receipt drift")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-identity-view-attribution: FIRST RED: " + str(error))
        raise SystemExit(2)
