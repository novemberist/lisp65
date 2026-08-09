#!/usr/bin/env python3
"""Build and gate the diagnostic-only v1.6 ROMC bootstrap repair."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-v16-defstruct-bootstrap-romc-repair.json"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PHASE_C_DRIVER = ROOT / "tools/host-lisp/c2_v16_defstruct_phase_c.py"
PHASE_C_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-residual-launch-boundary-attribution-receipt.json")
BASE_DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
CONTROL_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.prg"
CONTROL_ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.elf"
BASE_ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf"
BASE_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-corrected-view-quiet-appointment/diagnostic-link82-corrected-view-b5c3.prg")
WINDOW = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-window.bin"
RESET = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/record-reset.bin"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OUT = ROOT / "build/c2.3/v1.6-defstruct-bootstrap-romc-repair"
ARTIFACTS = OUT / "artifacts"
REPAIRED_PRG = ARTIFACTS / "diagnostic-link82-romc-safe.prg"
REPAIRED_ELF = ARTIFACTS / "diagnostic-link82-romc-safe.elf"
REPAIRED_WINDOW = ARTIFACTS / "diagnostic-window.bin"
REPAIRED_BOOT_RECORD = ARTIFACTS / "record-boot-romc-safe.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
DRIVER = Path(__file__).resolve()
PRG_LOAD = 0x2001


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def run(args: list[str], label: str) -> bytes:
    process = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            f"{label} failed:\n{process.stdout.decode(errors='replace')}")
    return process.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"],
               "resolve owner commit").decode().strip()
    return full, run(["git", "show", f"{full}:{path}"], "read owner commission")


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": sha_bytes(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def prg_slice(raw: bytes, address: int, count: int) -> bytes:
    require(int.from_bytes(raw[:2], "little") == PRG_LOAD, "PRG load drift")
    offset = 2 + address - PRG_LOAD
    require(offset >= 2 and offset + count <= len(raw), "PRG range absent")
    return raw[offset:offset + count]


def patch_prg(raw: bytes, address: int, before: bytes, after: bytes) -> bytes:
    require(len(before) == len(after), "fixed-size PRG patch required")
    result = bytearray(raw)
    offset = 2 + address - PRG_LOAD
    require(result[offset:offset + len(before)] == before,
            f"PRG patch authority drift at ${address:04X}")
    result[offset:offset + len(after)] = after
    return bytes(result)


def exact_ranges(before: bytes, after: bytes, *, base: int) -> list[dict[str, Any]]:
    require(len(before) == len(after), "identity range sizes differ")
    changed = [index for index, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    if not changed:
        return []
    rows: list[dict[str, Any]] = []
    start = previous = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != previous + 1:
            rows.append({"start": f"0x{base + start:04x}",
                         "bytes": previous - start + 1,
                         "before": before[start:previous + 1].hex(),
                         "after": after[start:previous + 1].hex()})
            start = current
        previous = current
    return rows


def bootstrap_visibility(code: bytes, start: int, end: int,
                         inherited_d030: int) -> list[dict[str, Any]]:
    """Decode the bootstrap prefix and reject transfers into hidden regions."""
    at = start
    x: int | None = None
    d030 = inherited_d030
    transfers: list[dict[str, Any]] = []
    while at < end:
        offset = at - start
        opcode = code[offset]
        if opcode in (0x78, 0xEA):             # SEI, NOP
            size = 1
        elif opcode == 0xA2:                   # LDX #imm
            x = code[offset + 1]; size = 2
        elif opcode in (0x86, 0x85):           # STX/STA zp
            size = 2
        elif opcode == 0xA9:                   # LDA #imm
            size = 2
        elif opcode == 0x8E:                   # STX abs
            target = int.from_bytes(code[offset + 1:offset + 3], "little")
            require(x is not None, "STX absolute with unknown X in bootstrap")
            if target == 0xD030:
                d030 = x
            size = 3
        elif opcode in (0x20, 0x4C):           # JSR/JMP abs
            target = int.from_bytes(code[offset + 1:offset + 3], "little")
            mapping_dependency = "ROMC" if 0xC000 <= target < 0xE000 else "none"
            if mapping_dependency == "ROMC":
                require((d030 & 0x20) == 0,
                        f"bootstrap transfer targets hidden C000 region at ${at:04X}")
            transfers.append({"at": f"0x{at:04x}", "target": f"0x{target:04x}",
                              "opcode": "JSR" if opcode == 0x20 else "JMP",
                              "mapping_dependency": mapping_dependency,
                              "D030_at_transfer": f"0x{d030:02x}",
                              "CPU_visible": True})
            size = 3
        else:
            raise RepairError(f"unknown bootstrap opcode ${opcode:02X} at ${at:04X}")
        at += size
    require(at == end and transfers, "bootstrap visibility extent/transfer drift")
    return transfers


def simulate_bootstrap(prg: bytes) -> dict[str, Any]:
    """Execute the tiny bootstrap slice with an independent register model."""
    pc = 0x202C
    a = x = 0
    sp = 0xFF
    z = n = False
    memory = {0xD030: 0x64, 0x0002: 0xA5, 0xB5C3: 0xD7}
    returns: list[int] = []
    steps = 0
    while pc != 0x2035:
        steps += 1
        require(steps <= 16, "bootstrap equivalence model did not terminate")
        opcode = prg_slice(prg, pc, 1)[0]
        if opcode == 0xA2:                       # LDX #imm
            x = prg_slice(prg, pc + 1, 1)[0]
            z, n = x == 0, bool(x & 0x80); pc += 2
        elif opcode == 0x8E:                     # STX abs
            target = int.from_bytes(prg_slice(prg, pc + 1, 2), "little")
            memory[target] = x; pc += 3
        elif opcode == 0xA9:                     # LDA #imm
            a = prg_slice(prg, pc + 1, 1)[0]
            z, n = a == 0, bool(a & 0x80); pc += 2
        elif opcode == 0x85:                     # STA zp
            memory[prg_slice(prg, pc + 1, 1)[0]] = a; pc += 2
        elif opcode == 0x20:                     # JSR abs
            target = int.from_bytes(prg_slice(prg, pc + 1, 2), "little")
            returns.append(pc + 3); sp = (sp - 2) & 0xFF; pc = target
        elif opcode == 0xEA:                     # NOP
            pc += 1
        elif opcode == 0x60:                     # RTS
            require(returns, "bootstrap RTS without JSR")
            pc = returns.pop(); sp = (sp + 2) & 0xFF
        else:
            raise RepairError(f"equivalence model opcode ${opcode:02X} at ${pc:04X}")
    require(not returns, "bootstrap equivalence return stack not balanced")
    return {"PC": "0x2035", "A": a, "X": x, "SP": sp,
            "Z": z, "N": n, "D030": memory[0xD030],
            "zp02": memory[0x0002], "B5C3": memory[0xB5C3], "steps": steps}


def patch_elf(text: bytes, state: bytes) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    text_file = ARTIFACTS / "section-text.bin"
    state_file = ARTIFACTS / "section-state.bin"
    text_file.write_bytes(text); state_file.write_bytes(state)
    run([str(OBJCOPY), f"--update-section=.text={text_file}",
         f"--update-section=.lisp65_v16_defstruct_diagnostic_state={state_file}",
         str(BASE_ELF), str(REPAIRED_ELF)], "patch repaired diagnostic ELF")


def build_artifacts(config: dict[str, Any]) -> dict[str, Any]:
    authority = config["authorities"]
    expected_hashes = {
        CONTROL_PRG: authority["control_prg_sha256"],
        CONTROL_ELF: authority["control_elf_sha256"],
        BASE_PRG: authority["diagnostic_prg_sha256"],
        BASE_ELF: authority["diagnostic_elf_sha256"],
        WINDOW: authority["diagnostic_window_sha256"],
        RESET: authority["record_reset_sha256"],
        PHASE_C_RECEIPT: authority["phase_c_receipt_sha256"],
        ATTRIBUTION: authority["attribution_receipt_sha256"],
    }
    require(all(sha(path) == expected for path, expected in expected_hashes.items()),
            "repair input authority drift")

    phase_c_output = run(["python3", str(PHASE_C_DRIVER), "selftest"],
                         "Phase-C witness rerun")
    phase_c_text = phase_c_output.decode()
    require("witnesses=7 mutations=26" in phase_c_text,
            "Phase-C witness rerun count drift")

    reset = RESET.read_bytes()
    require(len(reset) == 65 and reset[:9].hex() == "515253cccc54cccccc",
            "canonical record reset drift")
    repaired_routine = bytes.fromhex("a90085028ec3b560")
    repaired_boot_record = repaired_routine + reset[len(repaired_routine):]
    require(len(repaired_boot_record) == 65, "repaired boot record size drift")

    base_prg = BASE_PRG.read_bytes()
    repaired_prg = patch_prg(base_prg, 0x202C,
                             bytes.fromhex("203fc0eaea"),
                             bytes.fromhex("a2448e30d0"))
    repaired_prg = patch_prg(repaired_prg, 0x2031,
                             bytes.fromhex("a9008502"),
                             bytes.fromhex("203fc0ea"))
    repaired_prg = patch_prg(repaired_prg, 0xC03F,
                             bytes.fromhex("a2448e30d08ec3b560"),
                             repaired_boot_record[:9])

    base_truth = ElfTruth.read(BASE_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    text_section = base_truth.section(".text")
    state_section = base_truth.section(".lisp65_v16_defstruct_diagnostic_state")
    require(text_section.address == 0x2023 and state_section.address == 0xC03F
            and state_section.bytes == 65,
            "diagnostic linked-section placement drift")
    text = bytearray(base_truth.section_bytes(".text"))
    text_offset = lambda address: address - text_section.address
    require(text[text_offset(0x202C):text_offset(0x2031)] ==
            bytes.fromhex("203fc0eaea"), "linked old hook drift")
    text[text_offset(0x202C):text_offset(0x2031)] = bytes.fromhex("a2448e30d0")
    require(text[text_offset(0x2031):text_offset(0x2035)] ==
            bytes.fromhex("a9008502"), "linked repaired-hook authority drift")
    text[text_offset(0x2031):text_offset(0x2035)] = bytes.fromhex("203fc0ea")
    patch_elf(bytes(text), repaired_boot_record)

    REPAIRED_PRG.write_bytes(repaired_prg)
    REPAIRED_BOOT_RECORD.write_bytes(repaired_boot_record)
    shutil.copyfile(WINDOW, REPAIRED_WINDOW)

    repaired_truth = ElfTruth.read(REPAIRED_ELF, llvm_readobj=READOBJ,
                                   include_section_data=True)
    repaired_text = repaired_truth.section_bytes(".text")
    repaired_state = repaired_truth.section_bytes(
        ".lisp65_v16_defstruct_diagnostic_state")
    require(repaired_state == repaired_boot_record
            and repaired_truth.symbol("lisp65_v16_defstruct_entry_capture").value ==
                0xC03F,
            "repaired linked witness identity drift")
    require(repaired_text[text_offset(0x2023):text_offset(0x2035)] ==
            prg_slice(repaired_prg, 0x2023, 0x12),
            "PRG/ELF bootstrap bytes differ")
    require(prg_slice(repaired_prg, 0xC03F, 65) == repaired_state,
            "PRG/ELF state bytes differ")

    base_deploy = load(BASE_DEPLOY)
    deployment = deepcopy(base_deploy)
    deployment["format"] = "lisp65-c2.3-v1.6-defstruct-bootstrap-romc-repair-deployment-v1"
    deployment["status"] = "HOST-GREEN-NON-PROMOTABLE-ROMC-SAFE-DIAGNOSTIC"
    deployment["promotable"] = False
    deployment["diagnostic"]["prg"] = bind(REPAIRED_PRG)
    deployment["diagnostic"]["elf"] = bind(REPAIRED_ELF)
    deployment["diagnostic"]["window"] = bind(REPAIRED_WINDOW)
    for row in deployment["diagnostic"]["preloads"]:
        if row["role"] == "c2-kernal-window":
            row.update(bind(REPAIRED_WINDOW))
    deployment["entry_witness"].update({
        "hook": 0x2031, "routine": 0xC03F,
        "routine_bytes": repaired_routine.hex(),
        "displaced_bytes_replayed": "a9008502",
        "ROMC_clear_address": 0x202C,
        "ROMC_clear_bytes": "a2448e30d0",
        "ROMC_clear_precedes_entry_call": True,
        "stamp_address": 0xB5C3, "stamp_value": 0x44,
    })
    deployment["record"]["boot"] = bind(REPAIRED_BOOT_RECORD)
    write_json(DEPLOY, deployment)

    mapping = config["mapping_contract"]
    bootstrap = prg_slice(repaired_prg, mapping["bootstrap_start"],
                          mapping["bootstrap_visibility_end_exclusive"] -
                          mapping["bootstrap_start"])
    transfers = bootstrap_visibility(
        bootstrap, mapping["bootstrap_start"],
        mapping["bootstrap_visibility_end_exclusive"],
        mapping["inherited_d030"])

    # Required structural counterexample: recreate the old hidden-callee shape.
    hidden = bytearray(bootstrap)
    hidden[0x202C - mapping["bootstrap_start"]:
           0x2031 - mapping["bootstrap_start"]] = bytes.fromhex("203fc0eaea")
    hidden[0x2031 - mapping["bootstrap_start"]:
           0x2035 - mapping["bootstrap_start"]] = bytes.fromhex("a9008502")
    try:
        bootstrap_visibility(bytes(hidden), mapping["bootstrap_start"],
                             mapping["bootstrap_visibility_end_exclusive"],
                             mapping["inherited_d030"])
    except RepairError as error:
        hidden_rejected = str(error)
    else:
        raise RepairError("hidden-callee structural mutation survived")

    return {
        "phase_c_selftest_output": phase_c_text,
        "phase_c_selftest_sha256": sha_bytes(phase_c_output),
        "repaired_prg": repaired_prg,
        "repaired_routine": repaired_routine,
        "repaired_boot_record": repaired_boot_record,
        "transfers": transfers,
        "hidden_callee_rejection": hidden_rejected,
        "deployment": deployment,
    }


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    config = load(CONFIG)
    owner_commit, owner = git_blob(config["owner_commit"], PLAN)
    owner_text = owner.decode()
    require("Bootstrap repair authorized — 2026-08-05" in owner_text
            and "no bootstrap transfer" in owner_text
            and "Zero product bytes" in owner_text,
            "owner repair commission drift")
    attribution = load(ATTRIBUTION)
    require(attribution["facts"]["attribution"]["mechanism"] ==
            "bootstrap-hook-target-hidden-by-inherited-ROMC",
            "attributed mechanism drift")
    built = build_artifacts(config)
    repaired_prg = built["repaired_prg"]
    control_prg = CONTROL_PRG.read_bytes()
    base_prg = BASE_PRG.read_bytes()
    control_ranges = exact_ranges(control_prg, repaired_prg, base=PRG_LOAD - 2)
    repair_ranges = exact_ranges(base_prg, repaired_prg, base=PRG_LOAD - 2)
    require([(row["start"], row["bytes"]) for row in control_ranges] == [
        ("0x2031", 4), ("0x47c5", 10), ("0x8eb7", 5),
        ("0xb3b0", 243), ("0xbff7", 71), ("0xc03f", 1),
        ("0xc041", 63)],
        "control/repaired enumerated PRG delta drift")
    require([(row["start"], row["bytes"]) for row in repair_ranges] == [
        ("0x202c", 9), ("0xc03f", 9)],
        "old/repaired bootstrap delta drift")
    require(REPAIRED_WINDOW.read_bytes() == WINDOW.read_bytes(),
            "repair changed diagnostic window")
    control_state = simulate_bootstrap(control_prg)
    repaired_state = simulate_bootstrap(repaired_prg)
    require({key: value for key, value in control_state.items()
             if key not in ("B5C3", "steps")} ==
            {key: value for key, value in repaired_state.items()
             if key not in ("B5C3", "steps")}
            and control_state["B5C3"] == 0xD7
            and repaired_state["B5C3"] == 0x44,
            "bootstrap semantic equivalence drift")

    facts = {
        "repair": {
            "mechanism_repaired": "bootstrap-hook-target-hidden-by-inherited-ROMC",
            "mapping_clear": {"address": "0x202c", "bytes": "a2448e30d0",
                              "executes_from": "low-RAM"},
            "hook": {"address": "0x2031", "bytes": "203fc0ea",
                     "target": "0xc03f"},
            "routine": {"address": "0xc03f",
                        "bytes": built["repaired_routine"].hex(),
                        "replays": "a9008502", "witness": "STX $B5C3"},
            "mapping_clear_precedes_transfer": True,
            "target_CPU_visible_at_transfer": True,
        },
        "general_visibility_gate": {
            "source": "linked .text plus independent inherited-D030 contract",
            "rule": ("no bootstrap transfer may target a region whose CPU visibility "
                     "depends on mapping state not yet established"),
            "bootstrap_extent": ["0x2023", "0x2035"],
            "transfers": built["transfers"],
            "hidden_callee_mutation_rejected": True,
            "hidden_callee_error": built["hidden_callee_rejection"],
        },
        "identity": {
            "control_byteidentical_outside_enumerated_delta": True,
            "control_PRG_delta_ranges": control_ranges,
            "repair_only_delta_ranges": repair_ranges,
            "PRG_ELF_bootstrap_byteidentical": True,
            "PRG_ELF_record_byteidentical": True,
            "diagnostic_window_byteidentical": True,
            "phase_C_execution_witnesses_rerun": 7,
            "phase_C_mutations_rerun": 26,
            "phase_C_selftest_sha256": built["phase_c_selftest_sha256"],
            "canonical_record_reset_before_measured_form": True,
            "bootstrap_semantic_equivalence": {
                "control_end": control_state,
                "repaired_end": repaired_state,
                "only_added_side_effect": "$B5C3=$44",
                "all_other_end_state_equal": True,
            },
        },
        "scope": {
            "diagnostic_promotable": False,
            "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0,
            "hardware_contacts": 0, "measured_forms_run": 0,
            "contact_authorized": False, "CPU_remains_stopped": True,
        },
        "decision": {
            "host_green": True,
            "next_owner_question":
                "authorize physical launch proof before the D2 measured form",
        },
    }
    authorities = {
        "owner_commission": bind_blob(f"git:{owner_commit}:{PLAN}", owner),
        "configuration": bind(CONFIG), "attribution": bind(ATTRIBUTION),
        "phase_C_receipt": bind(PHASE_C_RECEIPT),
        "phase_C_driver": bind(PHASE_C_DRIVER),
        "source_control_PRG": bind(CONTROL_PRG),
        "source_control_ELF": bind(CONTROL_ELF),
        "source_diagnostic_PRG": bind(BASE_PRG),
        "source_diagnostic_ELF": bind(BASE_ELF),
        "repaired_PRG": bind(REPAIRED_PRG),
        "repaired_ELF": bind(REPAIRED_ELF),
        "repaired_window": bind(REPAIRED_WINDOW),
        "repaired_boot_record": bind(REPAIRED_BOOT_RECORD),
        "deployment": bind(DEPLOY), "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    repair = facts["repair"]
    gate = facts["general_visibility_gate"]
    identity = facts["identity"]
    scope = facts["scope"]
    require(repair["mechanism_repaired"] ==
            "bootstrap-hook-target-hidden-by-inherited-ROMC"
            and repair["mapping_clear"]["address"] == "0x202c"
            and repair["mapping_clear"]["bytes"] == "a2448e30d0"
            and repair["mapping_clear"]["executes_from"] == "low-RAM"
            and repair["hook"]["address"] == "0x2031"
            and repair["hook"]["target"] == "0xc03f"
            and repair["mapping_clear_precedes_transfer"]
            and repair["target_CPU_visible_at_transfer"],
            "ROMC repair semantics drift")
    require(gate["source"] ==
            "linked .text plus independent inherited-D030 contract"
            and gate["bootstrap_extent"] == ["0x2023", "0x2035"]
            and len(gate["transfers"]) == 1
            and gate["transfers"][0]["D030_at_transfer"] == "0x44"
            and gate["transfers"][0]["CPU_visible"]
            and gate["hidden_callee_mutation_rejected"],
            "general bootstrap visibility gate drift")
    require(identity["control_byteidentical_outside_enumerated_delta"]
            and identity["PRG_ELF_bootstrap_byteidentical"]
            and identity["PRG_ELF_record_byteidentical"]
            and identity["diagnostic_window_byteidentical"]
            and identity["phase_C_execution_witnesses_rerun"] == 7
            and identity["phase_C_mutations_rerun"] == 26
            and identity["canonical_record_reset_before_measured_form"]
            and identity["bootstrap_semantic_equivalence"][
                "only_added_side_effect"] == "$B5C3=$44"
            and identity["bootstrap_semantic_equivalence"][
                "all_other_end_state_equal"],
            "diagnostic identity/equivalence drift")
    require(scope == {
        "diagnostic_promotable": False,
        "product_candidate_bytes_changed": 0,
        "product_links": 0, "WPLTO_runs": 0,
        "hardware_contacts": 0, "measured_forms_run": 0,
        "contact_authorized": False, "CPU_remains_stopped": True,
    }, "repair scope drift")
    require(facts["decision"]["host_green"], "repair is not host-green")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "move-clear-behind-transfer":
            (["repair", "mapping_clear_precedes_transfer"], False),
        "claim-hidden-target-visible":
            (["repair", "target_CPU_visible_at_transfer"], False),
        "move-clear-to-C000": (["repair", "mapping_clear", "executes_from"], "C000"),
        "restore-old-hook": (["repair", "hook", "address"], "0x202c"),
        "change-hook-target": (["repair", "hook", "target"], "0xc13f"),
        "source-expectation-from-image":
            (["general_visibility_gate", "source"], "linked .text only"),
        "drop-hidden-callee-mutation":
            (["general_visibility_gate", "hidden_callee_mutation_rejected"], False),
        "mark-transfer-hidden":
            (["general_visibility_gate", "transfers", 0, "CPU_visible"], False),
        "wrong-D030-at-transfer":
            (["general_visibility_gate", "transfers", 0, "D030_at_transfer"], "0x64"),
        "drop-control-equivalence":
            (["identity", "control_byteidentical_outside_enumerated_delta"], False),
        "drop-PRG-ELF-bootstrap":
            (["identity", "PRG_ELF_bootstrap_byteidentical"], False),
        "drop-PRG-ELF-record":
            (["identity", "PRG_ELF_record_byteidentical"], False),
        "change-window": (["identity", "diagnostic_window_byteidentical"], False),
        "drop-witness": (["identity", "phase_C_execution_witnesses_rerun"], 6),
        "drop-mutation": (["identity", "phase_C_mutations_rerun"], 25),
        "partial-record-reset":
            (["identity", "canonical_record_reset_before_measured_form"], False),
        "break-bootstrap-equivalence":
            (["identity", "bootstrap_semantic_equivalence",
              "all_other_end_state_equal"], False),
        "make-promotable": (["scope", "diagnostic_promotable"], True),
        "claim-product-byte": (["scope", "product_candidate_bytes_changed"], 1),
        "claim-link": (["scope", "product_links"], 1),
        "claim-WPLTO": (["scope", "WPLTO_runs"], 1),
        "claim-contact": (["scope", "hardware_contacts"], 1),
        "claim-form": (["scope", "measured_forms_run"], 1),
        "authorize-contact": (["scope", "contact_authorized"], True),
        "resume-CPU": (["scope", "CPU_remains_stopped"], False),
        "red-repair": (["decision", "host_green"], False),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        target: Any = trial
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(trial)
        except RepairError as error:
            rejected[name] = str(error)
        else:
            raise RepairError(f"repair mutation survived: {name}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    rejected = rejected_mutations(facts)
    rejected["hidden-callee-linked-image"] = facts["general_visibility_gate"][
        "hidden_callee_error"]
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-bootstrap-romc-repair-result-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN DIAGNOSTIC-ONLY ROMC BOOTSTRAP REPAIR",
        "facts": facts, "authorities": authorities,
        "mutations_rejected": rejected,
        "claim_limit": (
            "Repairs only the non-promotable v1.6 diagnostic bootstrap: ROMC "
            "is cleared from low RAM before the $C03F transfer. The linked-image "
            "gate enforces the general visibility rule and rejects the historical "
            "hidden-callee shape. No product byte, Link, WPLTO, hardware contact, "
            "measured form or R/A/I/G result is claimed."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    value = expected()
    if args.action == "write":
        write_json(RECEIPT, value)
    elif args.action == "check":
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "ROMC repair receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"]),
                 "phase_C_witnesses":
                    value["facts"]["identity"]["phase_C_execution_witnesses_rerun"]}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RepairError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-v1.6-bootstrap-romc-repair: FIRST RED: " + str(error))
        raise SystemExit(2)
