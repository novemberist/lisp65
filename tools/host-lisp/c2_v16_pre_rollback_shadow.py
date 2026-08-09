#!/usr/bin/env python3
"""Build and gate the non-promotable v1.6 pre-rollback shadow witness.

The consumed full-run diagnostic read the install trace after rollback had
already overwritten it.  This sibling redirects the one Link-82 v5_fail edge
through an eleven-byte tail helper.  The helper commits the current forward
slot to diagnostic RAM and only then enters the original rollback routine.
The released product and every product artifact remain untouched.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_v16_defstruct_phase_c as PHASE_C  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DEPLOY = ROOT / (
    "build/c2.3/v1.6-defstruct-ownership-crc-bound/deployment.json")
BASE_GUARD = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-guard-attribution-receipt.json")
CORRECTION = EVIDENCE / (
    "c2.3-v1.6-defstruct-slot39-provenance-correction-receipt.json")
FULL_RESULT = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-crc-full-run-result-receipt.json")
PHASE_B = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
MEM_PREP = EVIDENCE / (
    "c2.3-v1.6-defstruct-mem-init-before-after-preparation-receipt.json")
LADDER_PREP = EVIDENCE / (
    "c2.3-v1.6-defstruct-preinstaller-micro-ladder-preparation-receipt.json")
V17 = EVIDENCE / (
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")
V18 = EVIDENCE / "c2.3-v1.8-full-map-phase-a-closure-receipt.json"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OUT = ROOT / "build/c2.3/v1.6-defstruct-pre-rollback-shadow"
ART = OUT / "artifacts"
SHADOW_PRG = ART / "diagnostic-pre-rollback-shadow.prg"
SHADOW_ELF = ART / "diagnostic-pre-rollback-shadow.elf"
SHADOW_WINDOW = ART / "diagnostic-pre-rollback-shadow-window.bin"
SHADOW_RESET = ART / "record-reset-pre-rollback-shadow.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-preparation-receipt.json")
REBIND = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-rebind-2026-08-06.json")
OWNER_COMMIT = "4eaa72b2fcb7aa98f1e1ebddaf3c8a4e7a56c69c"
FORMAT = "lisp65-c2.3-v1.6-defstruct-pre-rollback-shadow-v1"
RECORDED_ON = "2026-08-06"

PRG_LOAD = 0x2001
FAIL_CAPTURE = 0xB3B0
FAIL_OLD_CAPTURE_BYTES = bytes.fromhex("adf4c18d6bc0a2b38e6ac0")
FAIL_RETIRED_BYTES = b"\xea" * len(FAIL_OLD_CAPTURE_BYTES)
CRC_HIGH = 0xB4F4
CRC_LOW = 0xB4FA
HELPER = 0xB5B7
HELPER_LIMIT = 0xB5C3
BOOT_WITNESS = 0xB5C3
RECORD = 0xC03F
SHADOW_LEGACY_TAG = RECORD + 43
SHADOW_VALUE = RECORD + 44
SHADOW_RESET_SENTINEL = 0x7F
SHADOW_COMMIT_MASK = 0x80
LAST_SLOT = 0xC1F4
V5_FAIL = 0xE9BE
ROLLBACK = 0xE9E5
ROLLBACK_END = 0xEA02
WINDOW_BASE = 0xE000
WINDOW_BYTES = 8192
SECTION_SHADOW = ".lisp65_v16_defstruct_pre_rollback_shadow"


class ShadowError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ShadowError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name); handle.write(payload)
    temporary.replace(path)


def run(args: list[str], label: str) -> None:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")


def git_blob(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
                          check=True, stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(["git", "show", f"{full}:{path}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def replace(raw: bytearray, at: int, before: bytes, after: bytes,
            label: str) -> None:
    require(len(before) == len(after), f"fixed-size patch required: {label}")
    require(raw[at:at + len(before)] == before, f"patch authority drift: {label}")
    raw[at:at + len(after)] = after


def helper_bytes() -> bytes:
    # Inline tagged value: reset 0x7F; committed values are 0x80|slot.  This
    # fits the complete eleven-byte owner-free tail and needs no second store.
    value = (b"\xad\xf4\xc1"      # LDA $C1F4 -- still forward provenance
             b"\x09\x80"          # ORA #$80 -- commit bit
             b"\x8d\x6b\xc0"      # STA $C06B -- shadow value
             b"\x4c\xe5\xe9")    # JMP $E9E5 -- original rollback
    require(len(value) == 11 and HELPER + len(value) < HELPER_LIMIT,
            "shadow helper does not fit owner-free tail")
    return value


def exact_ranges(before: bytes, after: bytes, *, base: int) -> list[dict[str, Any]]:
    require(len(before) == len(after), "identity comparison requires equal sizes")
    changed = [i for i, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    rows: list[dict[str, Any]] = []
    if not changed:
        return rows
    start = prior = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != prior + 1:
            rows.append({"start": f"0x{base + start:04x}",
                         "bytes": prior - start + 1,
                         "before": before[start:prior + 1].hex(),
                         "after": after[start:prior + 1].hex()})
            start = current
        prior = current
    return rows


def executable_edges(truth: ElfTruth, target: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        data = truth.section_bytes(section.name)
        for index in range(len(data) - 2):
            if data[index] in (0x20, 0x4C) \
                    and int.from_bytes(data[index + 1:index + 3], "little") == target:
                result.append({"section": section.name,
                               "pc": f"0x{section.address + index:04x}",
                               "opcode": "JSR" if data[index] == 0x20 else "JMP"})
    return result


def route_proof(window: bytes, truth: ElfTruth) -> dict[str, Any]:
    require(len(window) == WINDOW_BYTES, "diagnostic window extent drift")
    require(window[V5_FAIL - WINDOW_BASE:V5_FAIL - WINDOW_BASE + 3]
            == b"\x20" + HELPER.to_bytes(2, "little"),
            "v5_fail does not enter shadow helper")
    rollback = window[ROLLBACK - WINDOW_BASE:ROLLBACK_END - WINDOW_BASE]
    target = HELPER.to_bytes(2, "little")
    require(not any(rollback[i] in (0x20, 0x4C)
                    and rollback[i + 1:i + 3] == target
                    for i in range(len(rollback) - 2)),
            "rollback path reaches shadow helper")
    edges = executable_edges(truth, HELPER)
    require(edges == [{
        "section": ".lisp65_c2_kernal_window.c2_resident",
        "pc": "0xe9be", "opcode": "JSR"}],
        f"shadow helper inbound-edge closure drift: {edges}")
    return {
        "only_inbound_edge": edges[0],
        "rollback_range": ["0xe9e5", "0xea02"],
        "rollback_edges_to_shadow": 0,
        "helper_tail_target": "0xe9e5",
        "shadow_committed_before_rollback": True,
    }


def patch_elf(base: Path, code0: bytes, window_section: bytes,
              handoff: bytes, helper: bytes) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for index, (name, raw) in enumerate((
        ("code0", code0), ("window", window_section),
        ("handoff", handoff), ("shadow", helper))):
        path = ART / f"section-{index}-{name}.bin"; path.write_bytes(raw)
        files[name] = path
    args = [str(OBJCOPY),
            f"--update-section=.lisp65_v16_defstruct_diagnostic_code0={files['code0']}",
            f"--update-section=.lisp65_c2_kernal_window.c2_resident={files['window']}",
            f"--update-section=.lisp65_c2_kernal_handoff={files['handoff']}",
            f"--add-section={SECTION_SHADOW}={files['shadow']}",
            f"--set-section-flags={SECTION_SHADOW}=alloc,load,readonly,code",
            f"--add-symbol=lisp65_v16_pre_rollback_shadow=0x{HELPER:x},global,function",
            str(base), str(SHADOW_ELF)]
    run(args, "derive pre-rollback shadow ELF")
    PHASE_C.patch_elf_section_addresses(SHADOW_ELF, {SECTION_SHADOW: HELPER})


def build() -> dict[str, Any]:
    base_deploy = load(BASE_DEPLOY)
    guard = load(BASE_GUARD)
    correction = load(CORRECTION)
    phase_b = load(PHASE_B)
    mem = load(MEM_PREP)
    ladder = load(LADDER_PREP)
    v17 = load(V17); v18 = load(V18)
    require(base_deploy["status"] == "HOST-GREEN-NON-PROMOTABLE-OWNERSHIP-CRC-BOUND"
            and base_deploy["promotable"] is False,
            "base diagnostic identity drift")
    require(correction["supersession"]["classification"]
            == "UNRESOLVED-PRE-ROLLBACK-PROVENANCE",
            "provenance correction prerequisite drift")
    require(guard["facts"]["owner_free_rule"].startswith(
        "A diagnostic witness slot is owner-free"),
        "owner-free/validated-region rule drift")
    require(mem["facts"]["placement"]["owner_free_interval"]
            == ["0xb582", "0xb5c4"]
            and ladder["facts"]["placement"]["owner_free_bytes_left"] == 12,
            "owner-free interval authority drift")
    require(v17["execution_witness"]["input_sections_enumerated"] == 72
            and v18["execution_witness"]["lto_allocatable_chain_inputs_enumerated"] == 80,
            "state/full-map inventory authority drift")

    base_prg_path = ROOT / base_deploy["diagnostic"]["prg"]["path"]
    base_elf_path = ROOT / base_deploy["diagnostic"]["elf"]["path"]
    base_window_path = ROOT / base_deploy["diagnostic"]["window"]["path"]
    base_reset_path = ROOT / base_deploy["record"]["reset"]["path"]
    base_prg = base_prg_path.read_bytes(); base_window = base_window_path.read_bytes()
    base_reset = base_reset_path.read_bytes()
    require(len(base_prg) == 41566 and int.from_bytes(base_prg[:2], "little") == PRG_LOAD,
            "base PRG geometry drift")
    require(len(base_window) == WINDOW_BYTES and crc16(base_window) == 0xD24C,
            "base diagnostic window/CRC drift")
    require(len(base_reset) == 65 and base_reset[43] == 0x63
            and base_reset[44] == 0xCC,
            "base append-record reset drift")
    require(base_prg[offset(HELPER):offset(HELPER_LIMIT)] == bytes(12)
            and BOOT_WITNESS == HELPER_LIMIT,
            "owner-free helper tail is not zero/disjoint")

    helper = helper_bytes()
    prg = bytearray(base_prg)
    replace(prg, offset(FAIL_CAPTURE), FAIL_OLD_CAPTURE_BYTES,
            FAIL_RETIRED_BYTES, "retire terminal last-slot overwrite")
    replace(prg, offset(HELPER), bytes(len(helper)), helper,
            "install pre-rollback shadow helper")
    window = bytearray(base_window)
    replace(window, V5_FAIL - WINDOW_BASE, b"\x20\xe5\xe9",
            b"\x20" + HELPER.to_bytes(2, "little"), "redirect v5_fail")
    new_crc = crc16(bytes(window))
    replace(prg, offset(CRC_HIGH), bytes((0xD2,)), bytes((new_crc >> 8,)),
            "bind shadow window CRC high")
    replace(prg, offset(CRC_LOW), bytes((0x4C,)), bytes((new_crc & 0xFF,)),
            "bind shadow window CRC low")
    reset = bytearray(base_reset); reset[44] = SHADOW_RESET_SENTINEL

    ART.mkdir(parents=True, exist_ok=True)
    SHADOW_PRG.write_bytes(prg); SHADOW_WINDOW.write_bytes(window)
    SHADOW_RESET.write_bytes(reset)

    base_truth = ElfTruth.read(base_elf_path, llvm_readobj=READOBJ,
                               include_section_data=True)
    code0 = bytearray(base_truth.section_bytes(
        ".lisp65_v16_defstruct_diagnostic_code0"))
    replace(code0, 0, FAIL_OLD_CAPTURE_BYTES, FAIL_RETIRED_BYTES,
            "ELF terminal capture retirement")
    resident_name = ".lisp65_c2_kernal_window.c2_resident"
    resident = bytearray(base_truth.section_bytes(resident_name))
    resident_base = base_truth.section(resident_name).address
    replace(resident, V5_FAIL - resident_base, b"\x20\xe5\xe9",
            b"\x20" + HELPER.to_bytes(2, "little"), "ELF v5_fail redirect")
    handoff_name = ".lisp65_c2_kernal_handoff"
    handoff = bytearray(base_truth.section_bytes(handoff_name))
    handoff_base = base_truth.section(handoff_name).address
    replace(handoff, CRC_HIGH - handoff_base, bytes((0xD2,)),
            bytes((new_crc >> 8,)), "ELF shadow CRC high")
    replace(handoff, CRC_LOW - handoff_base, bytes((0x4C,)),
            bytes((new_crc & 0xFF,)), "ELF shadow CRC low")
    patch_elf(base_elf_path, bytes(code0), bytes(resident), bytes(handoff), helper)

    truth = ElfTruth.read(SHADOW_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    require(truth.section_bytes(SECTION_SHADOW) == helper
            and truth.section(SECTION_SHADOW).address == HELPER,
            "shadow ELF helper placement drift")
    require(truth.symbol("lisp65_v16_pre_rollback_shadow").value == HELPER,
            "shadow ELF symbol drift")
    require(truth.section_bytes(".lisp65_v16_defstruct_diagnostic_code0")[:11]
            == FAIL_RETIRED_BYTES,
            "shadow ELF terminal overwrite still live")
    route = route_proof(bytes(window), truth)

    # The only executable write to the shadow byte is the helper itself.
    stores: list[dict[str, Any]] = []
    target = SHADOW_VALUE.to_bytes(2, "little")
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        raw = truth.section_bytes(section.name)
        for index in range(len(raw) - 2):
            if raw[index] in (0x8D, 0x8E, 0x8C, 0x9C) \
                    and raw[index + 1:index + 3] == target:
                stores.append({"section": section.name,
                               "pc": f"0x{section.address + index:04x}",
                               "opcode": f"0x{raw[index]:02x}"})
    require(stores == [{"section": SECTION_SHADOW, "pc": "0xb5bc",
                        "opcode": "0x8d"}],
            f"shadow store ownership drift: {stores}")
    for section in truth.sections:
        if "c2append_rollback" not in section.name \
                or "SHF_EXECINSTR" not in section.flags:
            continue
        raw = truth.section_bytes(section.name)
        require(target not in raw, f"rollback section mentions shadow address: {section.name}")

    deploy = deepcopy(base_deploy)
    deploy["format"] = "lisp65-c2.3-v1.6-pre-rollback-shadow-deployment-v1"
    deploy["status"] = "HOST-GREEN-NON-PROMOTABLE-SHADOW-ARMED"
    deploy["diagnostic"]["prg"] = bind(SHADOW_PRG)
    deploy["diagnostic"]["elf"] = bind(SHADOW_ELF)
    deploy["diagnostic"]["window"] = bind(SHADOW_WINDOW)
    for row in deploy["diagnostic"]["preloads"]:
        if row["role"] == "c2-kernal-window": row.update(bind(SHADOW_WINDOW))
    deploy["record"]["reset"] = bind(SHADOW_RESET)
    deploy["ownership_guard_binding"] = {
        "validated_window": bind(SHADOW_WINDOW),
        "computed_crc16": f"0x{new_crc:04X}",
        "final_PRG_operand_addresses": ["0xB4F4", "0xB4FA"],
        "final_PRG_operand_bytes": f"{new_crc:04x}",
        "recontact_authorized": False,
    }
    deploy["pre_rollback_shadow"] = {
        "helper": {"start": "0xb5b7", "end_exclusive": "0xb5c2",
                   "bytes": len(helper), "code_hex": helper.hex()},
        "v5_fail_hook": "0xe9be", "rollback_target": "0xe9e5",
        "record_offset": 44, "record_address": "0xc06b",
        "reset_sentinel": "0x7f", "commit_mask": "0x80",
        "decode": "committed byte & 0x7f; 0x7f means unreached",
        "legacy_terminal_tag_offset": 43,
        "legacy_terminal_tag_must_remain": "0x63",
        "recontact_authorized": False,
    }
    write_json(DEPLOY, deploy)

    return {
        "base": {"deployment": base_deploy, "prg": base_prg,
                 "elf": base_elf_path, "window": base_window,
                 "reset": base_reset},
        "shadow": {"deployment": deploy, "prg": bytes(prg),
                   "window": bytes(window), "reset": bytes(reset),
                   "elf_truth": truth},
        "facts": {
            "identity": {
                "promotable": False, "product_bytes_changed": 0,
                "product_links": 0, "WPLTO_runs": 0, "device_contacts": 0,
                "base_identity": "G4-corrected consumed diagnostic",
                "recontact_authorized": False,
            },
            "placement": {
                "owner_free_authority_interval": ["0xb582", "0xb5c4"],
                "helper": ["0xb5b7", "0xb5c2"],
                "helper_bytes": 11, "owner_free_bytes_after_helper": 1,
                "adjacent_boot_witness": "0xb5c3",
                "all_disjoint": True,
                "outside_ownership_validated_window": True,
            },
            "shadow_semantics": {
                "edge": "c2_append_begin.v5_fail-before-rollback",
                "source": "last forward overlay slot at $C1F4",
                "destination": "record byte 44 / $C06B",
                "reset_sentinel": "0x7F",
                "commit_encoding": "0x80 | forward_slot",
                "legal_committed_range": [0x80 | 22, 0x80 | 45],
                "legacy_terminal_tag_remains_sentinel": "0x63",
                "terminal_last-slot_overwrite_retired": True,
                "transport_nonentry_limit": (
                    "the committed low seven bits name the last entered forward "
                    "slot; if transport fails before phase entry it does not invent "
                    "a later slot"),
            },
            "route_closure": route,
            "write_ownership": {"executable_stores": stores,
                                "rollback_sections_with_shadow_address": 0},
            "guard": {
                "validated_window": ["0xe000", "0x10000"],
                "old_crc16": "0xD24C", "new_crc16": f"0x{new_crc:04X}",
                "expectation_recomputed_independently": True,
            },
            "deltas": {
                "PRG": exact_ranges(base_prg, bytes(prg), base=PRG_LOAD - 2),
                "window": exact_ranges(base_window, bytes(window), base=WINDOW_BASE),
                "record_reset": exact_ranges(base_reset, bytes(reset), base=RECORD),
            },
            "contact": {"question_returned_to_owner": True,
                        "authorized": False, "measured_forms": 0},
            "claim_limit": (
                "Host-green non-promotable witness only. A future committed byte "
                "binds the last entered forward slot before rollback; an unreached "
                "sentinel proves no c2_append_begin v5_fail edge. It does not yet "
                "select R/A/I/G, prove make-point was attempted, name an internal "
                "predicate, authorize hardware, or change product bytes."),
        },
    }


def audit(facts: dict[str, Any]) -> None:
    identity = facts["identity"]
    require(identity == {
        "promotable": False, "product_bytes_changed": 0, "product_links": 0,
        "WPLTO_runs": 0, "device_contacts": 0,
        "base_identity": "G4-corrected consumed diagnostic",
        "recontact_authorized": False,
    }, "shadow identity boundary drift")
    placement = facts["placement"]
    require(placement["owner_free_authority_interval"] == ["0xb582", "0xb5c4"]
            and placement["helper"] == ["0xb5b7", "0xb5c2"]
            and placement["helper_bytes"] == 11
            and placement["owner_free_bytes_after_helper"] == 1
            and placement["adjacent_boot_witness"] == "0xb5c3"
            and placement["all_disjoint"]
            and placement["outside_ownership_validated_window"],
            "shadow placement/ownership drift")
    semantics = facts["shadow_semantics"]
    require(semantics["edge"] == "c2_append_begin.v5_fail-before-rollback"
            and semantics["source"] == "last forward overlay slot at $C1F4"
            and semantics["destination"] == "record byte 44 / $C06B"
            and semantics["reset_sentinel"] == "0x7F"
            and semantics["commit_encoding"] == "0x80 | forward_slot"
            and semantics["legal_committed_range"] == [150, 173]
            and semantics["legacy_terminal_tag_remains_sentinel"] == "0x63"
            and semantics["terminal_last-slot_overwrite_retired"],
            "shadow sentinel/tag semantics drift")
    route = facts["route_closure"]
    require(route["only_inbound_edge"] == {
        "section": ".lisp65_c2_kernal_window.c2_resident",
        "pc": "0xe9be", "opcode": "JSR"}
            and route["rollback_range"] == ["0xe9e5", "0xea02"]
            and route["rollback_edges_to_shadow"] == 0
            and route["helper_tail_target"] == "0xe9e5"
            and route["shadow_committed_before_rollback"],
            "shadow/rollback route closure drift")
    require(facts["write_ownership"] == {
        "executable_stores": [{"section": SECTION_SHADOW,
                               "pc": "0xb5bc", "opcode": "0x8d"}],
        "rollback_sections_with_shadow_address": 0,
    }, "shadow store ownership drift")
    guard = facts["guard"]
    require(guard["validated_window"] == ["0xe000", "0x10000"]
            and guard["old_crc16"] == "0xD24C"
            and guard["new_crc16"].startswith("0x")
            and guard["expectation_recomputed_independently"],
            "shadow ownership-guard binding drift")
    require(facts["contact"] == {
        "question_returned_to_owner": True, "authorized": False,
        "measured_forms": 0}, "shadow contact boundary drift")
    require("does not yet select R/A/I/G" in facts["claim_limit"]
            and "authorize hardware" in facts["claim_limit"],
            "shadow claim limit drift")


def mutations(base: dict[str, Any], built: dict[str, Any]) -> dict[str, str]:
    cases: list[tuple[list[Any], Any]] = [
        (["identity", "promotable"], True),
        (["identity", "product_bytes_changed"], 1),
        (["identity", "device_contacts"], 1),
        (["identity", "recontact_authorized"], True),
        (["placement", "helper"], ["0xb5b8", "0xb5c3"]),
        (["placement", "owner_free_bytes_after_helper"], 0),
        (["placement", "outside_ownership_validated_window"], False),
        (["shadow_semantics", "reset_sentinel"], "0xCC"),
        (["shadow_semantics", "commit_encoding"], "raw slot"),
        (["shadow_semantics", "terminal_last-slot_overwrite_retired"], False),
        (["route_closure", "rollback_edges_to_shadow"], 1),
        (["route_closure", "shadow_committed_before_rollback"], False),
        (["write_ownership", "rollback_sections_with_shadow_address"], 1),
        (["guard", "expectation_recomputed_independently"], False),
        (["contact", "authorized"], True),
        (["claim_limit"], "A proven; hardware authorized"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except ShadowError as error: rejected[f"mutation-{index:02d}"] = str(error)
        else: raise ShadowError(f"shadow mutation survived: {path}")

    # Required structural mutation: add a rollback-to-shadow edge.  It must be
    # rejected by route analysis, not merely by changing a prose boolean.
    window = bytearray(built["shadow"]["window"])
    rollback = window[ROLLBACK - WINDOW_BASE:ROLLBACK_END - WINDOW_BASE]
    at = rollback.find(b"\x4c\xf1\xb5")
    require(at >= 0, "rollback tail-JMP mutation site absent")
    window[ROLLBACK - WINDOW_BASE + at + 1:
           ROLLBACK - WINDOW_BASE + at + 3] = HELPER.to_bytes(2, "little")
    try:
        route_proof(bytes(window), built["shadow"]["elf_truth"])
    except ShadowError as error:
        rejected["mutation-17-rollback-reaches-shadow"] = str(error)
    else:
        raise ShadowError("rollback-reaches-shadow mutation survived")
    return rejected


def make_receipt() -> dict[str, Any]:
    built = build(); facts = built["facts"]; audit(facts)
    rejected = mutations(facts, built)
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; RECONTACT QUESTION RETURNED TO OWNER",
        "facts": facts,
        "identity": {"prg": bind(SHADOW_PRG), "elf": bind(SHADOW_ELF),
                     "window": bind(SHADOW_WINDOW), "record_reset": bind(SHADOW_RESET),
                     "deployment": bind(DEPLOY)},
        "authorities": {
            "base_deployment": bind(BASE_DEPLOY), "base_guard": bind(BASE_GUARD),
            "provenance_correction": bind(CORRECTION),
            "historical_full_result": bind(FULL_RESULT), "phase_B": bind(PHASE_B),
            "mem_init_owner_free_interval": bind(MEM_PREP),
            "micro_ladder_remaining_space": bind(LADDER_PREP),
            "v17_state_inventory": bind(V17), "v18_full_map_inventory": bind(V18),
            "owner_commission": git_blob(
                OWNER_COMMIT, PLAN.relative_to(ROOT).as_posix()),
        },
        "bindings": {"driver": bind(DRIVER), "plan": bind(PLAN),
                     "gate_wiring": bind(GATES)},
        "verification": {"execution_witnesses": 7,
                         "mutations": len(rejected),
                         "mutations_rejected": rejected},
    }


def check() -> dict[str, Any]:
    recorded = load(RECEIPT); expected = make_receipt()
    historical = deepcopy(expected)
    for name in ("driver", "plan", "gate_wiring"):
        historical["bindings"][name] = recorded["bindings"][name]
    require(recorded == historical,
            "pre-rollback shadow evidence drift outside loud rebind")
    rebind = load(REBIND)
    require(rebind == {
        "format": "lisp65-c2.3-v1.6-pre-rollback-shadow-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: HISTORICAL SHADOW PREPARATION UNCHANGED; CONTACT REBOUND",
        "reason": (
            "The owner authorized the shadow-armed repeat and its one-shot "
            "contact closure was added. The historical preparation remains "
            "byte-for-byte unchanged; only checker, append-only plan and "
            "gate-wiring bindings are rebound for the authorized contact."),
        "historical_receipt": bind(RECEIPT),
        "from": {name: recorded["bindings"][name]
                 for name in ("driver", "plan", "gate_wiring")},
        "to": {name: expected["bindings"][name]
               for name in ("driver", "plan", "gate_wiring")},
        "authorized_bindings": ["driver", "plan", "gate_wiring"],
        "historical_facts_changed": False,
        "diagnostic_bytes_changed": False,
    }, "pre-rollback shadow loud rebind drift")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "prepare":
        require(not REBIND.exists(),
                "historical shadow preparation is loudly rebound; prepare disabled")
        value = make_receipt(); write_json(RECEIPT, value)
        output = {"status": "PREPARED", "crc16": value["facts"]["guard"]["new_crc16"],
                  "mutations": value["verification"]["mutations"]}
    elif args.action == "selftest":
        value = make_receipt()
        output = {"status": "SELFTEST PASS",
                  "crc16": value["facts"]["guard"]["new_crc16"],
                  "mutations": value["verification"]["mutations"]}
    else:
        value = check()
        output = {"status": "PASS", "recontact_authorized":
                  value["facts"]["contact"]["authorized"],
                  "mutations": value["verification"]["mutations"]}
    print(json.dumps(output, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ShadowError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"PRE-ROLLBACK SHADOW FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
