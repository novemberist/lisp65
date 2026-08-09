#!/usr/bin/env python3
"""Attribute and repair the v1.6 diagnostic ownership-guard identity.

This is desk-only work.  The released Link-82 product is the control.  The
non-promotable diagnostic window differs from that control, so its final PRG
must carry a CRC expectation computed from the bytes that it actually stages.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


OWNER_COMMIT = "9a5753e9"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"

CONTROL_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.prg"
CONTROL_ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.elf"
CONTROL_WINDOW = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/final/"
    "c2-product-kernal-window.bin")
BASE_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-preinstaller-micro-ladder/artifacts/"
    "diagnostic-preinstaller-micro-ladder.prg")
BASE_ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-preinstaller-micro-ladder/artifacts/"
    "diagnostic-preinstaller-micro-ladder.elf")
BASE_DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-preinstaller-micro-ladder/deployment.json"
LADDER_BASE_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-mem-init-before-after/artifacts/"
    "diagnostic-mem-init-before-after.prg")
DIAG_WINDOW = ROOT / (
    "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/artifacts/"
    "diagnostic-window.bin")
PHASE_C_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
LADDER_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-preinstaller-micro-ladder-preparation-receipt.json")
LADDER_RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-preinstaller-micro-ladder-device-receipt.json")

OUT = ROOT / "build/c2.3/v1.6-defstruct-ownership-crc-bound"
ART = OUT / "artifacts"
CORRECTED_PRG = ART / "diagnostic-preinstaller-micro-ladder-crc-bound.prg"
CORRECTED_ELF = ART / "diagnostic-preinstaller-micro-ladder-crc-bound.elf"
HANDOFF = ART / "section-kernal-handoff-crc-bound.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-ownership-guard-attribution-receipt.json")
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-ownership-guard-attribution-rebind-2026-08-06.json")

FORMAT = "lisp65-c2.3-v1.6-ownership-guard-attribution-v1"
PRG_LOAD = 0x2001
OWNERSHIP = 0xB4A3
OWNERSHIP_BYTES = 126
CRC_HIGH_OPERAND = 0xB4F4
CRC_LOW_OPERAND = 0xB4FA
WINDOW_CPU_START = 0xE000
WINDOW_BYTES = 8192
WINDOW_STAGE = 0x087FE000


class GuardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GuardError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], label: str) -> bytes:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"{label} failed:\n{result.stdout.decode(errors='replace')}")
    return result.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"],
               "resolve owner commission").decode().strip()
    raw = run(["git", "show", f"{full}:{path}"], "read owner commission")
    return full, raw


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xFFFF
                     if value & 0x8000 else (value << 1) & 0xFFFF)
    return value


def prg_slice(raw: bytes, address: int, count: int) -> bytes:
    require(int.from_bytes(raw[:2], "little") == PRG_LOAD, "PRG load drift")
    offset = 2 + address - PRG_LOAD
    require(offset >= 2 and offset + count <= len(raw), "PRG range absent")
    return raw[offset:offset + count]


def patch_prg(raw: bytes, address: int, before: int, after: int) -> bytes:
    result = bytearray(raw)
    offset = 2 + address - PRG_LOAD
    require(result[offset] == before, f"PRG operand drift at ${address:04X}")
    result[offset] = after
    return bytes(result)


def exact_ranges(before: bytes, after: bytes, *, base: int) -> list[dict[str, Any]]:
    require(len(before) == len(after), "identity sizes differ")
    changed = [index for index, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    if not changed:
        return []
    rows: list[dict[str, Any]] = []
    start = previous = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != previous + 1:
            width = 4 if base + start <= 0xFFFF else 8
            rows.append({"start": f"0x{base + start:0{width}x}",
                         "bytes": previous - start + 1,
                         "before": before[start:previous + 1].hex(),
                         "after": after[start:previous + 1].hex()})
            start = current
        previous = current
    return rows


def guard_table(control_prg: bytes, diagnostic_window: bytes,
                control_window: bytes) -> list[dict[str, Any]]:
    body = prg_slice(control_prg, OWNERSHIP, OWNERSHIP_BYTES)
    # These byte strings come from the resolved final PRG, not source prose.
    for expected in (
        bytes.fromhex("9ce1d6a2f08e97d69c13d7aee1d6e0409003"),
        bytes.fromhex("ad97d6290ff003"),
        bytes.fromhex("ad13d7290fd035"),
        bytes.fromhex("2021b520ffb520dda1e039d026a000c9aad022"),
    ):
        require(expected in body, f"linked ownership guard sequence absent: {expected.hex()}")
    control_crc, diagnostic_crc = crc16(control_window), crc16(diagnostic_window)
    require(prg_slice(control_prg, CRC_HIGH_OPERAND, 1)[0] == control_crc >> 8
            and prg_slice(control_prg, CRC_LOW_OPERAND, 1)[0] ==
                control_crc & 0xFF,
            "final PRG ownership CRC is not bound to the control window")
    return [
        {"id": "G1-ethernet-irq-readback", "order": 1,
         "write": {"address": "0xD6E1", "value": "0x00"},
         "pass_condition": "(read($D6E1) & $C0) == 0",
         "validated_domain": "live-MEGA65-I/O", "image_dependent": False,
         "host_image_evaluation": "NOT-APPLICABLE"},
        {"id": "G2-autoiec-irq-readback", "order": 2,
         "write": {"address": "0xD697", "value": "0xF0"},
         "pass_condition": "(read($D697) & $0F) == 0",
         "validated_domain": "live-MEGA65-I/O", "image_dependent": False,
         "host_image_evaluation": "NOT-APPLICABLE"},
        {"id": "G3-audiodma-irq-readback", "order": 3,
         "write": {"address": "0xD713", "value": "0x00"},
         "pass_condition": "(read($D713) & $0F) == 0",
         "validated_domain": "live-MEGA65-I/O", "image_dependent": False,
         "host_image_evaluation": "NOT-APPLICABLE"},
        {"id": "G4-kernal-window-crc16", "order": 4,
         "copy": {"source_physical": f"0x{WINDOW_STAGE:08X}",
                  "target_CPU": f"0x{WINDOW_CPU_START:04X}",
                  "bytes": WINDOW_BYTES},
         "pass_condition": "CRC16-CCITT-FALSE($E000..$FFFF) == linked expectation",
         "validated_domain": "staged-and-CPU-mapped-kernal-window",
         "image_dependent": True,
         "linked_final_PRG_expectation": f"0x{control_crc:04X}",
         "control": {"computed": f"0x{control_crc:04X}", "result": "PASS"},
         "diagnostic": {"computed": f"0x{diagnostic_crc:04X}",
                        "result": "FAIL"}},
    ]


def derive() -> dict[str, Any]:
    control_prg = CONTROL_PRG.read_bytes()
    base_prg = BASE_PRG.read_bytes()
    control_window = CONTROL_WINDOW.read_bytes()
    diagnostic_window = DIAG_WINDOW.read_bytes()
    require(len(control_window) == len(diagnostic_window) == WINDOW_BYTES,
            "ownership window extent drift")
    guards = guard_table(control_prg, diagnostic_window, control_window)
    control_crc, diagnostic_crc = crc16(control_window), crc16(diagnostic_window)
    require(prg_slice(base_prg, CRC_HIGH_OPERAND, 1)[0] == control_crc >> 8
            and prg_slice(base_prg, CRC_LOW_OPERAND, 1)[0] == control_crc & 0xFF,
            "base diagnostic does not retain the product CRC expectation")

    phase_c = load(PHASE_C_RECEIPT)
    window_delta = exact_ranges(control_window, diagnostic_window,
                                base=WINDOW_CPU_START)
    require(window_delta == phase_c["exact_window_byte_differences"]
            and window_delta == [{"start": "0xe08b", "bytes": 14,
                                  "before": "78a9008d1ad0a9028d20d04c96e0",
                                  "after": "4cb0b3eaeaeaeaeaeaeaeaeaeaea"}],
            "Phase-C validated-window delta drift")

    ladder = load(LADDER_PREP)
    ladder_base = LADDER_BASE_PRG.read_bytes()
    ladder_deltas = exact_ranges(ladder_base, base_prg, base=PRG_LOAD - 2)
    require(ladder["status"] == "HOST-GREEN; CONTACT READY"
            and ladder["facts"]["identity"]["actual_differing_bytes"] == 49,
            "micro-ladder identity authority drift")
    ladder_addresses: list[int] = []
    for row in ladder_deltas:
        start = int(row["start"], 16)
        ladder_addresses.extend(range(start, start + row["bytes"]))
    require(len(ladder_addresses) == 49 and
            all(not WINDOW_CPU_START <= address < WINDOW_CPU_START + WINDOW_BYTES
                for address in ladder_addresses),
            "micro-ladder byte enters an ownership-validated region")

    result = load(LADDER_RESULT)
    require(result["status"] == "OWNERSHIP-FAIL-CLOSED-EXIT"
            and result["ladder"]["raw_hex"] == "0ee1e2e300d5",
            "device result authority drift")

    corrected = patch_prg(base_prg, CRC_HIGH_OPERAND, control_crc >> 8,
                          diagnostic_crc >> 8)
    corrected = patch_prg(corrected, CRC_LOW_OPERAND, control_crc & 0xFF,
                          diagnostic_crc & 0xFF)
    ART.mkdir(parents=True, exist_ok=True)
    CORRECTED_PRG.write_bytes(corrected)

    truth = ElfTruth.read(BASE_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    section_name = ".lisp65_c2_kernal_handoff"
    handoff = bytearray(truth.section_bytes(section_name))
    handoff_base = truth.section(section_name).address
    high = CRC_HIGH_OPERAND - handoff_base
    low = CRC_LOW_OPERAND - handoff_base
    # The ELF retains the publish-last relocation sentinel A55A.  It is not
    # the executable expectation; mirror the diagnostic binding only so the
    # analysis sibling cannot misreport the corrected intent.
    require((handoff[high], handoff[low]) == (0xA5, 0x5A),
            "ELF CRC binding sentinel drift")
    handoff[high], handoff[low] = diagnostic_crc >> 8, diagnostic_crc & 0xFF
    HANDOFF.write_bytes(bytes(handoff))
    run([str(OBJCOPY), f"--update-section={section_name}={HANDOFF}",
         str(BASE_ELF), str(CORRECTED_ELF)], "derive CRC-bound diagnostic ELF")
    corrected_elf = CORRECTED_ELF.read_bytes()
    require(sum(left != right for left, right in
                zip(BASE_ELF.read_bytes(), corrected_elf, strict=True)) == 2,
            "analysis ELF correction is not exactly two bytes")

    deploy = deepcopy(load(BASE_DEPLOY))
    deploy["format"] = "lisp65-c2.3-v1.6-ownership-crc-bound-deployment-v1"
    deploy["status"] = "HOST-GREEN-NON-PROMOTABLE-OWNERSHIP-CRC-BOUND"
    deploy["promotable"] = False
    deploy["diagnostic"]["prg"] = bind(CORRECTED_PRG)
    deploy["diagnostic"]["elf"] = bind(CORRECTED_ELF)
    deploy["ownership_guard_binding"] = {
        "validated_window": bind(DIAG_WINDOW),
        "computed_crc16": f"0x{diagnostic_crc:04X}",
        "final_PRG_operand_addresses": [f"0x{CRC_HIGH_OPERAND:04X}",
                                         f"0x{CRC_LOW_OPERAND:04X}"],
        "final_PRG_operand_bytes": corrected[
            2 + CRC_HIGH_OPERAND - PRG_LOAD:3 + CRC_HIGH_OPERAND - PRG_LOAD].hex()
            + corrected[2 + CRC_LOW_OPERAND - PRG_LOAD:
                        3 + CRC_LOW_OPERAND - PRG_LOAD].hex(),
        "recontact_authorized": False,
    }
    write_json(DEPLOY, deploy)

    return {
        "guards": guards,
        "control_crc": control_crc, "diagnostic_crc": diagnostic_crc,
        "window_delta": window_delta, "ladder_delta_addresses": ladder_addresses,
        "corrected_prg_ranges": exact_ranges(base_prg, corrected, base=PRG_LOAD - 2),
        "corrected_elf_operands": [
            {"address": f"0x{CRC_HIGH_OPERAND:04x}", "before": "a5", "after": "d2"},
            {"address": f"0x{CRC_LOW_OPERAND:04x}", "before": "5a", "after": "4c"},
        ],
        "control_prg": control_prg, "base_prg": base_prg,
        "corrected_prg": corrected, "control_window": control_window,
        "diagnostic_window": diagnostic_window, "deployment": deploy,
    }


def facts(built: dict[str, Any]) -> dict[str, Any]:
    control_crc, diagnostic_crc = built["control_crc"], built["diagnostic_crc"]
    return {
        "classification": "OWNERSHIP-WINDOW-CRC-GUARD",
        "product_guard": "CORRECT-FAIL-CLOSED",
        "finding_class": "INSTRUMENT-IDENTITY",
        "boot_path_ownership_guards": built["guards"],
        "resolved_image_identity": {
            "runtime_authority": "final-PRG-plus-staged-window",
            "ELF_crc_bytes": "publish-last-relocation-sentinel-not-runtime-oracle",
            "control_window_crc16": f"0x{control_crc:04X}",
            "control_final_PRG_expected_crc16": f"0x{control_crc:04X}",
            "diagnostic_window_crc16": f"0x{diagnostic_crc:04X}",
            "base_diagnostic_final_PRG_expected_crc16": f"0x{control_crc:04X}",
            "base_diagnostic_result": "GUARANTEED-FAIL-IF-G4-REACHED",
        },
        "delta_attribution": {
            "Phase_C_validated_window_delta_bytes": 14,
            "Phase_C_validated_window_delta": built["window_delta"],
            "micro_ladder_delta_bytes": len(built["ladder_delta_addresses"]),
            "micro_ladder_bytes_inside_validated_window": 0,
            "micro_ladder_is_direct_cause": False,
            "mismatch_predates_micro_ladder": True,
        },
        "corrected_identity": {
            "promotable": False, "product_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0, "device_contacts": 0,
            "window_bytes_changed_from_base_diagnostic": 0,
            "expected_crc16": f"0x{diagnostic_crc:04X}",
            "final_PRG_operand_patches": built["corrected_prg_ranges"],
            "analysis_ELF_operand_patches": built["corrected_elf_operands"],
            "analysis_ELF_sentinel_mirrored": True,
            "guard_expectation_recomputed_from_staged_bytes": True,
            "recontact_authorized": False,
        },
        "owner_free_rule": (
            "A diagnostic witness slot is owner-free only when no active owner "
            "writes it and it lies outside every ownership-validated region. "
            "Any necessary diagnostic delta inside such a region must carry an "
            "independently recomputed, non-promotable verifier expectation."),
        "claim_limit": (
            "Desk attribution plus one repaired non-promotable diagnostic "
            "identity. The three live I/O readbacks were not observed; G4 is "
            "the deterministic image-dependent failure. No product change, "
            "device contact, mem_init answer or R/A/I/G claim."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value["classification"] == "OWNERSHIP-WINDOW-CRC-GUARD"
            and value["product_guard"] == "CORRECT-FAIL-CLOSED"
            and value["finding_class"] == "INSTRUMENT-IDENTITY",
            "ownership attribution/class drift")
    guards = value["boot_path_ownership_guards"]
    require(len(guards) == 4 and [row["order"] for row in guards] == [1, 2, 3, 4]
            and all(not row["image_dependent"] and
                    row["host_image_evaluation"] == "NOT-APPLICABLE"
                    for row in guards[:3])
            and guards[3]["image_dependent"]
            and guards[3]["control"]["result"] == "PASS"
            and guards[3]["diagnostic"]["result"] == "FAIL",
            "boot ownership guard table drift")
    identity = value["resolved_image_identity"]
    require(identity == {
        "runtime_authority": "final-PRG-plus-staged-window",
        "ELF_crc_bytes": "publish-last-relocation-sentinel-not-runtime-oracle",
        "control_window_crc16": "0x39AA",
        "control_final_PRG_expected_crc16": "0x39AA",
        "diagnostic_window_crc16": "0xD24C",
        "base_diagnostic_final_PRG_expected_crc16": "0x39AA",
        "base_diagnostic_result": "GUARANTEED-FAIL-IF-G4-REACHED",
    }, "resolved image identity drift")
    delta = value["delta_attribution"]
    require(delta["Phase_C_validated_window_delta_bytes"] == 14
            and delta["micro_ladder_delta_bytes"] == 49
            and delta["micro_ladder_bytes_inside_validated_window"] == 0
            and not delta["micro_ladder_is_direct_cause"]
            and delta["mismatch_predates_micro_ladder"],
            "validated-region delta attribution drift")
    corrected = value["corrected_identity"]
    require(not corrected["promotable"] and corrected["product_bytes_changed"] == 0
            and corrected["product_links"] == 0 and corrected["WPLTO_runs"] == 0
            and corrected["device_contacts"] == 0
            and corrected["window_bytes_changed_from_base_diagnostic"] == 0
            and corrected["expected_crc16"] == "0xD24C"
            and corrected["final_PRG_operand_patches"] == [
                {"start": "0xb4f4", "bytes": 1, "before": "39", "after": "d2"},
                {"start": "0xb4fa", "bytes": 1, "before": "aa", "after": "4c"},
            ]
            and corrected["analysis_ELF_operand_patches"] == [
                {"address": "0xb4f4", "before": "a5", "after": "d2"},
                {"address": "0xb4fa", "before": "5a", "after": "4c"},
            ]
            and corrected["analysis_ELF_sentinel_mirrored"]
            and corrected["guard_expectation_recomputed_from_staged_bytes"]
            and not corrected["recontact_authorized"],
            "corrected diagnostic identity drift")
    require("outside every ownership-validated region" in value["owner_free_rule"]
            and "three live I/O readbacks were not observed" in value["claim_limit"]
            and "No product change" in value["claim_limit"],
            "rule/claim boundary drift")


def mutations(base: dict[str, Any]) -> dict[str, str]:
    cases: list[tuple[list[Any], Any]] = [
        (["classification"], "OWNERSHIP-LIVE-IO-GUARD"),
        (["product_guard"], "PRODUCT-FAULT"),
        (["finding_class"], "PRODUCT"),
        (["boot_path_ownership_guards", 0, "image_dependent"], True),
        (["boot_path_ownership_guards", 0, "host_image_evaluation"], "PASS"),
        (["boot_path_ownership_guards", 3, "diagnostic", "result"], "PASS"),
        (["resolved_image_identity", "runtime_authority"], "ELF-sentinel"),
        (["resolved_image_identity", "control_window_crc16"], "0xA55A"),
        (["resolved_image_identity", "diagnostic_window_crc16"], "0x39AA"),
        (["delta_attribution", "Phase_C_validated_window_delta_bytes"], 0),
        (["delta_attribution", "micro_ladder_bytes_inside_validated_window"], 1),
        (["delta_attribution", "micro_ladder_is_direct_cause"], True),
        (["corrected_identity", "promotable"], True),
        (["corrected_identity", "product_bytes_changed"], 2),
        (["corrected_identity", "device_contacts"], 1),
        (["corrected_identity", "window_bytes_changed_from_base_diagnostic"], 1),
        (["corrected_identity", "expected_crc16"], "0x39AA"),
        (["corrected_identity", "analysis_ELF_operand_patches", 0, "after"], "39"),
        (["corrected_identity", "guard_expectation_recomputed_from_staged_bytes"], False),
        (["corrected_identity", "recontact_authorized"], True),
        (["owner_free_rule"], "no active owner writes it"),
        (["claim_limit"], "Product ownership fault proven."),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except GuardError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise GuardError(f"ownership attribution mutation survived: {path}")
    return rejected


def make_receipt() -> dict[str, Any]:
    built = derive(); value = facts(built); audit(value)
    rejected = mutations(value)
    owner_full, owner_raw = git_blob(OWNER_COMMIT, PLAN.relative_to(ROOT).as_posix())
    return {
        "format": FORMAT, "recorded_on": "2026-08-06",
        "status": "PRODUCT-GUARD-CORRECT-DIAGNOSTIC-IDENTITY-REPAIRED",
        "facts": value,
        "corrected_identity": {
            "prg": bind(CORRECTED_PRG), "elf": bind(CORRECTED_ELF),
            "window": bind(DIAG_WINDOW), "deployment": bind(DEPLOY)},
        "authorities": {
            "control_PRG": bind(CONTROL_PRG), "control_ELF": bind(CONTROL_ELF),
            "control_window": bind(CONTROL_WINDOW), "base_diagnostic_PRG": bind(BASE_PRG),
            "base_diagnostic_ELF": bind(BASE_ELF), "base_deployment": bind(BASE_DEPLOY),
            "ladder_base_PRG": bind(LADDER_BASE_PRG),
            "Phase_C_receipt": bind(PHASE_C_RECEIPT), "ladder_preparation": bind(LADDER_PREP),
            "ladder_device_result": bind(LADDER_RESULT),
            "owner_commission": {"commit": owner_full,
                                 "path": PLAN.relative_to(ROOT).as_posix(),
                                 "bytes": len(owner_raw), "sha256": digest(owner_raw)}},
        "bindings": {"driver": bind(DRIVER), "plan": bind(PLAN),
                     "gate_wiring": bind(GATES)},
        "verification": {"execution_witnesses": 4,
                         "mutations": len(rejected),
                         "mutations_rejected": rejected},
    }


def check() -> dict[str, Any]:
    recorded = load(RECEIPT)
    require(recorded["format"] == FORMAT
            and recorded["recorded_on"] == "2026-08-06"
            and recorded["status"] ==
                "PRODUCT-GUARD-CORRECT-DIAGNOSTIC-IDENTITY-REPAIRED",
            "receipt identity/status drift")
    expected = make_receipt()
    historical = deepcopy(expected)
    historical["bindings"] = recorded["bindings"]
    require(recorded == historical,
            "ownership guard attribution evidence drift outside loud rebind")
    require(REBIND.is_file(), "ownership guard attribution rebind absent")
    rebind = load(REBIND)
    require(rebind == {
        "format": "lisp65-c2.3-v1.6-ownership-guard-attribution-rebind-v1",
        "recorded_on": "2026-08-06",
        "status": "PASS: HISTORICAL EVIDENCE UNCHANGED; BINDINGS REBOUND",
        "reason": (
            "The consumed bundled full run was closed offline after the G4 "
            "attribution, then its Slot-39/A interpretation was loudly "
            "superseded by the rollback-provenance correction and the accepted "
            "correction commissioned the pre-rollback shadow identity. The "
            "historical receipt remains byte-for-byte unchanged; only driver, "
            "append-only plan and gate-wiring bindings are rebound for the "
            "permanent result, correction and shadow closures."),
        "historical_receipt": bind(RECEIPT),
        "from": recorded["bindings"],
        "to": expected["bindings"],
        "authorized_bindings": ["driver", "plan", "gate_wiring"],
        "historical_facts_changed": False,
    }, "ownership guard attribution loud rebind drift")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "prepare":
        receipt = make_receipt(); write_json(RECEIPT, receipt)
        output = {"status": "PREPARED", "classification":
                  receipt["facts"]["classification"],
                  "corrected_crc16": receipt["facts"]["corrected_identity"]["expected_crc16"],
                  "mutations": receipt["verification"]["mutations"]}
    else:
        receipt = check()
        output = {"status": "PASS" if args.action == "check" else "SELFTEST PASS",
                  "classification": receipt["facts"]["classification"],
                  "corrected_crc16": receipt["facts"]["corrected_identity"]["expected_crc16"],
                  "mutations": receipt["verification"]["mutations"]}
    print(json.dumps(output, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GuardError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"OWNERSHIP GUARD ATTRIBUTION FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
