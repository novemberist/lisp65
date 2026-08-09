#!/usr/bin/env python3
"""Bind the pre-installer diversion span and price its minimal ladder."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v16_mem_init_before_after as BUILD  # noqa: E402
import c2_v16_mem_init_before_after_contact as CONTACT  # noqa: E402

OWNER_COMMIT = "e1edb6c3"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SALVAGE = EVIDENCE / (
    "c2.3-v1.6-defstruct-mem-init-preoverlay-status-salvage-device-receipt.json")
DEVICE = EVIDENCE / (
    "c2.3-v1.6-defstruct-mem-init-before-after-repeat-device-receipt.json")
WRITE_VIEW = EVIDENCE / (
    "c2.3-v1.6-defstruct-mem-init-witness-write-view-desk-attribution-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-preinstaller-stretch-desk-attribution-receipt.json")
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-mem-init-before-after/deployment.json"
ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-mem-init-before-after/artifacts/"
    "diagnostic-mem-init-before-after.elf")
PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-mem-init-before-after/artifacts/"
    "diagnostic-mem-init-before-after.prg")
CORE = ROOT / "build/upstream-verification/mega65-core"
CPU = CORE / "src/vhdl/gs4510.vhdl"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
DRIVER = Path(__file__).resolve()


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        label = path.relative_to(ROOT).as_posix()
    except ValueError:
        label = path.resolve().as_posix()
    return {"path": label, "bytes": len(raw),
            "sha256": digest(raw)}


def bind_blob(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "bytes": len(raw), "sha256": digest(raw)}


def run(args: list[str], cwd: Path = ROOT) -> bytes:
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{result.stderr.decode(errors='replace')}")
    return result.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"]).decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def prg_slice(raw: bytes, address: int, size: int) -> bytes:
    load_address = int.from_bytes(raw[:2], "little")
    offset = 2 + address - load_address
    require(offset >= 2 and offset + size <= len(raw),
            f"PRG slice outside image: 0x{address:04x}")
    return raw[offset:offset + size]


def selected(logical: int, register: int) -> bool:
    return bool(((register >> 12) & 0xF) &
                (1 << ((logical >> 13) & 0x3)))


def mapped_low20(logical: int, register: int) -> int:
    require(selected(logical, register), "address not selected by MAP register")
    return (((register & 0xFFF) + (logical >> 8)) << 8) | (logical & 0xFF)


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    owner, plan = git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("PRE-INSTALLER-BOUNDARY — desk commission" in text
            and "Bind the stopped tuple's world" in text
            and "Name the diversion candidates" in text,
            "owner desk commission drift")
    salvage, device, write_view, deployment = (
        load(path) for path in (SALVAGE, DEVICE, WRITE_VIEW, DEPLOY))
    require(salvage["classification"]["outcome"] == "PRE-INSTALLER-BOUNDARY"
            and salvage["decoded"]["ov_started"] == 0
            and salvage["contact"]["CPU_left_stopped"],
            "salvage boundary drift")
    stop = device["stop"]
    registers = stop["registers"]
    require({key: registers[key] for key in ("PC", "B", "SP", "MAPH", "MAPL")} == {
        "PC": "0xe160", "B": "0x00", "SP": "0x01ee",
        "MAPH": "0xb300", "MAPL": "0xe300"},
        "retained tuple drift")
    observed = bytes.fromhex(stop["code_owner"]["observed"])
    require(observed == bytes.fromhex(
        "a6d1f00ba4d2b91010c6d1e6d2806fa5")
        and "2060E1" in registers["tail"], "stopped code stream drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    symbols = {name: truth.symbol(name).value for name in (
        "_start", "__zero_bss", "__zero_zp_bss", "__copy_zp_data", "main",
        "c2_kernal_take_ownership", "c2_kernal_map_window",
        "vm_install_staged_boot_overlay", "vm_workbench_boot_overlay_entry",
        "ov_started", "vm_boot_overlay_status")}
    require(symbols == {
        "_start": 0x2023, "__zero_bss": 0x2301,
        "__zero_zp_bss": 0x23E9, "__copy_zp_data": 0x23FC,
        "main": 0xA4AF, "c2_kernal_take_ownership": 0xB4A3,
        "c2_kernal_map_window": 0xB5FF,
        "vm_install_staged_boot_overlay": 0xA714,
        "vm_workbench_boot_overlay_entry": 0xC85A,
        "ov_started": 0x75, "vm_boot_overlay_status": 0x74},
        "pre-installer symbol geometry drift")
    prg = PRG.read_bytes()
    require(prg_slice(prg, 0x2035, 0x15) == bytes.fromhex(
        "a9d0850320012320e92320fc23a90e20d2ff20afa4"),
        "CRT-to-main route drift")
    require(prg_slice(prg, 0xA4E0, 9) == bytes.fromhex(
        "20a3b4aaf0272014a7"), "main ownership/install route drift")
    require(prg_slice(prg, 0xB4EA, 9) == bytes.fromhex(
        "2021b520ffb520dda1"), "ownership copy/MAP/CRC route drift")
    require(prg_slice(prg, 0xB5FF, 10) == bytes.fromhex(
        "6baaa8a3805ceaa30060"), "owned MAP leaf drift")
    require(prg_slice(prg, 0xA714, 0x38)[0x34:0x38] ==
            bytes.fromhex("a2018675"), "installer arming store drift")
    require(prg_slice(prg, 0xB582, 66)[:10] ==
            bytes.fromhex("d1ccccccccd2cccccccc")
            and prg_slice(prg, 0xB582, 66)[10:] == bytes(56),
            "owner-free ladder interval drift")

    listing = run([str(OBJDUMP), "-d", str(ELF)]).decode()
    map_sites = [int(match.group(1), 16) for match in re.finditer(
        r"^\s*([0-9a-f]+):.*\bmap\s*$", listing, re.MULTILINE)]
    require(map_sites == [0xB604], f"executable MAP inventory drift: {map_sites}")
    require(write_view["facts"]["linked_route"] == {
        "ownership_call": "0xa4e0", "overlay_install_call": "0xa4e6",
        "sole_executable_MAP": "0xb604", "overlay_entry": "0xc85a",
        "before_capture": "0xc048", "after_capture": "0xc04e",
        "ownership_precedes_overlay": True}, "prior linked-route authority drift")

    core = CPU.read_text(encoding="utf-8")
    for token in ("if reg_map_high(blocknum)='1'",
                  "if reg_map_low(blocknum)='1'",
                  "temp_address(27 downto 20) := reg_mb_high",
                  "temp_address(27 downto 20) := reg_mb_low"):
        require(token in core, f"primary MAP semantic absent: {token}")
    require((selected(0xE160, 0xB300), selected(0xFFD2, 0xB300),
             selected(0x2035, 0xE300)) == (True, True, True),
            "captured MAP selection drift")
    require((mapped_low20(0xE160, 0xB300),
             mapped_low20(0xFFD2, 0xB300)) == (0x3E160, 0x3FFD2),
            "captured high-MAP offset drift")

    rom = VIEW.rom_path().read_bytes()[0x10000:]
    configured = rom[0xE158:0xE165]
    require(configured[:3] == observed[:3]
            and configured[4:] == observed[4:13]
            and configured[3] != observed[3],
            "firmware instruction-signature relation drift")

    route = [
        {"stage": "entry-tail", "range": "0x2035..0x2038",
         "transfer": None, "requires": "linked low block 1", "establishes": "none"},
        {"stage": "zero-bss", "range": "0x2039 -> 0x2301 -> 0xb34d",
         "transfer": "product-local JSR/tail-JMP", "requires": "linked low/high block 1",
         "establishes": "none"},
        {"stage": "zero-zp-bss", "range": "0x203c -> 0x23e9 -> 0xb34d",
         "transfer": "product-local JSR/tail-JMP", "requires": "linked low/high block 1",
         "establishes": "none"},
        {"stage": "copy-zp-data", "range": "0x203f -> 0x23fc -> 0xb2f7",
         "transfer": "product-local JSR/tail-JMP", "requires": "linked low/high block 1",
         "establishes": "none"},
        {"stage": "crt-shift", "range": "0x2042..0x2046",
         "transfer": "JSR 0xffd2 (KERNAL CHROUT)",
         "requires": "firmware-visible high block 3; not established by product",
         "establishes": "callee-private/unknown"},
        {"stage": "main-prefix", "range": "0x2047 -> 0xa4af..0xa4df",
         "transfer": "product-local JSR", "requires": "linked high block 1 and I/O",
         "establishes": "I/O unlocked; no MAP"},
        {"stage": "ownership-pre-map", "range": "0xa4e0 -> 0xb4a3..0xb4ec",
         "transfer": "product-local JSR plus three fail-closed guards",
         "requires": "linked high block 1 and I/O", "establishes": "none before 0xb604"},
        {"stage": "ownership-map", "range": "0xb4ed -> 0xb5ff..0xb608",
         "transfer": "product-local JSR", "requires": "linked high block 1",
         "establishes": "MAPH=0x8000, MAPL=0x0000"},
        {"stage": "ownership-return", "range": "0xb4f0..0xb520 -> 0xa4e3",
         "transfer": "CRC/guard return", "requires": "owned E000 window",
         "establishes": "success=1 or fail-closed=0"},
        {"stage": "installer-entry", "range": "0xa4e6 -> 0xa714..0xa74b",
         "transfer": "product-local JSR", "requires": "owned map",
         "establishes": "ov_started=1 at 0xa74a"},
        {"stage": "overlay-entry", "range": "installer -> 0xc85a",
         "transfer": "authenticated overlay call", "requires": "owned map and staged identity",
         "establishes": "pre-mem_init capture at 0xc048"},
    ]

    facts = {
        "stopped_world": {
            "tuple": {"PC": "0xe160", "B": "0x00", "SP": "0x01ee",
                      "MAPH": "0xb300", "MAPL": "0xe300"},
            "E160_selected": True, "E160_mapped_low20": "0x3e160",
            "FFD2_selected": True, "FFD2_mapped_low20": "0x3ffd2",
            "mapped_megabyte_registers_captured": False,
            "observed_bytes": observed.hex(),
            "configured_ROM_signature": configured.hex(),
            "signature_relation": (
                "same 13-byte instruction skeleton with only branch displacement changed; "
                "exact device ROM image and mapped megabyte remain unbound"),
            "owner_class": "firmware-shaped selected high-MAP; exact owner unresolved",
            "last_op": "JSR $E160",
        },
        "mapping_legality": {
            "linked_executable_MAP_sites": ["0xb604"],
            "linked_MAP_result": {"MAPH": "0x8000", "MAPL": "0x0000"},
            "IRQ_or_NMI_MAP_sites": 0,
            "captured_map_established_by_linked_preinstaller_step": False,
            "captured_map_compatible_with_external_firmware_private_view": True,
            "illegal_product_state_claim": False,
        },
        "route": route,
        "hidden_callee_audit": {
            "repaired_hook": "0x2031 -> 0xc03f behind the 0x202c ROMC clear: PASS",
            "local_boot_helpers": "all targets delivered in the linked PRG",
            "first_external_target": "0x2044 -> 0xffd2",
            "finding": "firmware target is consumed before c2_kernal_take_ownership establishes MAP",
            "named_boundary": "PRE-OWNERSHIP-CHROUT-OR-OWNERSHIP-FAIL-EXIT",
            "single_mechanism_claimed": False,
        },
        "diversion_candidates": [
            {"id": "U1", "span": "0x2044 JSR $FFD2 / return mapping",
             "witness": "pre/post CHROUT stamps; absent post stamp convicts this boundary"},
            {"id": "U2", "span": "0xa4e0 ownership call before/at MAP",
             "witness": "ownership-entry plus tagged raw return status"},
            {"id": "U3", "span": "ownership success to installer arming",
             "witness": "installer-entry stamp plus existing ov_started/status pair"},
            {"id": "U4", "span": "asynchronous firmware diversion",
             "witness": "ladder stage plus stopped code-owner/stack capture; no inherited claim"},
        ],
        "micro_ladder": {
            "authorization": "OWNER DECISION REQUIRED; NO CONTACT AUTHORIZED",
            "base_identity": "mem-init-before-after non-promotable diagnostic",
            "owner_free_interval": "0xb58c..0xb5c2",
            "interval_bytes": 55, "existing_witness_before": "0xb582..0xb58b",
            "durable_witness_after": "0xb5c3",
            "state": {"range": "0xb58c..0xb591", "bytes": 6,
                      "sentinels": "d0 d1 d2 d3 d4 d5",
                      "fields": ["CHROUT-enter", "CHROUT-return", "ownership-enter",
                                 "ownership-return-tag", "ownership-return-raw",
                                 "installer-enter"]},
            "wrappers": [
                {"range": "0xb592..0xb59d", "bytes": 12,
                 "callsite": "0x2044", "purpose": "stamp around JSR $FFD2"},
                {"range": "0xb59e..0xb5ae", "bytes": 17,
                 "callsite": "0xa4e0", "purpose": "stamp and retain ownership return A"},
                {"range": "0xb5af..0xb5b6", "bytes": 8,
                 "callsite": "0xa4e6", "purpose": "stamp then tail-JMP installer"},
            ],
            "gap_bytes_changed": 43, "callsite_instruction_bytes_patched": 9,
            "callsite_bytes_actually_different": 6, "total_bytes_actually_different": 49,
            "owner_free_bytes_left": 12, "layout_shift": 0, "product_bytes": 0,
            "hidden_callee_rule": (
                "each wrapper shares a visibility proof with its caller; CHROUT non-restore "
                "leaves the physical pre-call stamp as the classification"),
            "decision_table": {
                "enter-absent": "LOCAL-CRT-INIT-BOUNDARY",
                "enter-set,return-absent": "CHROUT-NONRETURN-OR-MAP-NOT-RESTORED",
                "return-set,ownership-enter-absent": "MAIN-PREFIX-BOUNDARY",
                "ownership-enter-set,return-tag-absent": "OWNERSHIP-IN-FLIGHT-BOUNDARY",
                "ownership-return-raw=0": "OWNERSHIP-FAIL-CLOSED-EXIT",
                "ownership-return-raw!=0,installer-enter-absent": "POST-OWNERSHIP-PRE-INSTALLER",
                "installer-enter-set,ov_started=0": "INSTALLER-PROLOGUE-BEFORE-ARM",
                "ov_started=1": "HAND-OFF-TO-EXISTING-STATUS-TABLE",
            },
            "contacts_priced": 1,
        },
        "disposition": {
            "classification": "MICRO-LADDER-REQUIRED; TWO LIVE DIVERSION ROUTES",
            "mem_init_answer": None, "R_A_I_G": None, "product_fault": None,
            "new_contact_authorized": False, "CPU_device_action": 0,
        },
    }
    authorities = {
        "owner_commission": bind_blob(f"git:{owner}:{PLAN}", plan),
        "salvage": bind(SALVAGE), "retained_device": bind(DEVICE),
        "write_view": bind(WRITE_VIEW), "deployment": bind(DEPLOY),
        "diagnostic_ELF": bind(ELF), "diagnostic_PRG": bind(PRG),
        "configured_ROM": bind(VIEW.rom_path()), "primary_CPU": bind(CPU),
        "primary_core_commit": run(["git", "rev-parse", "HEAD"], CORE).decode().strip(),
        "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    world, legality = facts["stopped_world"], facts["mapping_legality"]
    require(world["tuple"] == {"PC": "0xe160", "B": "0x00", "SP": "0x01ee",
                                "MAPH": "0xb300", "MAPL": "0xe300"}
            and world["E160_selected"] and world["FFD2_selected"]
            and not world["mapped_megabyte_registers_captured"]
            and world["owner_class"] ==
                "firmware-shaped selected high-MAP; exact owner unresolved",
            "stopped-world claim drift")
    require(legality == {
        "linked_executable_MAP_sites": ["0xb604"],
        "linked_MAP_result": {"MAPH": "0x8000", "MAPL": "0x0000"},
        "IRQ_or_NMI_MAP_sites": 0,
        "captured_map_established_by_linked_preinstaller_step": False,
        "captured_map_compatible_with_external_firmware_private_view": True,
        "illegal_product_state_claim": False}, "mapping-legality overclaim")
    require(len(facts["route"]) == 11
            and facts["route"][4]["transfer"] == "JSR 0xffd2 (KERNAL CHROUT)"
            and facts["route"][7]["establishes"] ==
                "MAPH=0x8000, MAPL=0x0000", "route enumeration drift")
    hidden = facts["hidden_callee_audit"]
    require(hidden["first_external_target"] == "0x2044 -> 0xffd2"
            and hidden["named_boundary"] ==
                "PRE-OWNERSHIP-CHROUT-OR-OWNERSHIP-FAIL-EXIT"
            and not hidden["single_mechanism_claimed"],
            "hidden-callee claim drift")
    require([row["id"] for row in facts["diversion_candidates"]] ==
            ["U1", "U2", "U3", "U4"], "diversion partition drift")
    ladder = facts["micro_ladder"]
    require(ladder["authorization"] ==
            "OWNER DECISION REQUIRED; NO CONTACT AUTHORIZED"
            and ladder["interval_bytes"] == 55 and ladder["state"]["bytes"] == 6
            and [row["bytes"] for row in ladder["wrappers"]] == [12, 17, 8]
            and ladder["gap_bytes_changed"] == 43
            and ladder["callsite_bytes_actually_different"] == 6
            and ladder["total_bytes_actually_different"] == 49
            and ladder["owner_free_bytes_left"] == 12
            and ladder["layout_shift"] == 0 and ladder["product_bytes"] == 0
            and ladder["contacts_priced"] == 1
            and len(ladder["decision_table"]) == 8,
            "micro-ladder price/closure drift")
    require(facts["disposition"] == {
        "classification": "MICRO-LADDER-REQUIRED; TWO LIVE DIVERSION ROUTES",
        "mem_init_answer": None, "R_A_I_G": None, "product_fault": None,
        "new_contact_authorized": False, "CPU_device_action": 0},
        "desk disposition drift")


def selftest() -> dict[str, Any]:
    base, _authorities = exact_facts()
    audit(base)
    mutations = [
        (["stopped_world", "tuple", "MAPH"], "0x8000"),
        (["stopped_world", "mapped_megabyte_registers_captured"], True),
        (["stopped_world", "owner_class"], "exact MEGA65-ROM"),
        (["mapping_legality", "linked_executable_MAP_sites"], ["0xb604", "0xe160"]),
        (["mapping_legality", "illegal_product_state_claim"], True),
        (["hidden_callee_audit", "first_external_target"], "0x2039 -> 0x2301"),
        (["hidden_callee_audit", "single_mechanism_claimed"], True),
        (["diversion_candidates", 0, "id"], "R"),
        (["micro_ladder", "authorization"], "CONTACT AUTHORIZED"),
        (["micro_ladder", "interval_bytes"], 54),
        (["micro_ladder", "wrappers", 1, "bytes"], 18),
        (["micro_ladder", "total_bytes_actually_different"], 48),
        (["micro_ladder", "layout_shift"], 1),
        (["micro_ladder", "product_bytes"], 49),
        (["disposition", "new_contact_authorized"], True),
        (["disposition", "R_A_I_G"], "R"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except AttributionError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise AttributionError(f"preinstaller mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-preinstaller-stretch-desk-attribution-v1",
        "recorded_on": "2026-08-06",
        "status": "HOST-GREEN; MICRO-LADDER PRICED; OWNER DECISION REQUIRED",
        "authorities": authorities, "facts": facts,
        "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "Desk-only route and mapping attribution. Exact mapped megabyte and "
            "device ROM identity remain unbound. No contact, product bytes, mem_init "
            "answer, R/A/I/G row or product fault is authorized or claimed."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("dump", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        value = selftest()
    elif args.action == "dump":
        sys.stdout.buffer.write(canonical(expected()))
        return 0
    else:
        value = expected()
        require(RECEIPT.read_bytes() == canonical(value),
                "preinstaller stretch receipt drift")
        value = {"status": "PASS", "mutations": len(selftest()["rejected"]),
                 "classification": value["facts"]["disposition"]["classification"]}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"PREINSTALLER STRETCH ATTRIBUTION FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
