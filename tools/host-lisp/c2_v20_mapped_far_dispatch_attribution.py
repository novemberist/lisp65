#!/usr/bin/env python3
"""Bind the v2.0 mapped-far dispatch defect from primary MAP semantics.

The installed far payload is already proven present.  This host-only gate
decodes the delivered MAP tuple from primary MEGA65 documentation and core
RTL, binds the exact trampoline and call chain in the frozen candidate ELF,
and models the first far-service call plus the captured BRK site.  It records
an attribution only: no source fix, card, device contact, or D2-D5 is opened.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
FACADE = ROOT / "src/c2_mapped_far_service.s"
INSTALLATION = EVIDENCE / "c2.3-v2.0-far-payload-installation-receipt.json"
DEVICE = EVIDENCE / "c2.3-v2.0-far-payload-device-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CHIPSET_PDF = ROOT / "docs/reference/mega65-chipset-reference.pdf"
GUIDE_ROOT = ROOT / "build/upstream-verification/mega65-user-guide"
GUIDE = GUIDE_ROOT / "appendix-45gs02-registers.tex"
OPCODES = GUIDE_ROOT / "instruction_sets/4510.opc"
CORE_ROOT = ROOT / "build/upstream-verification/mega65-core"
CORE = CORE_ROOT / "src/vhdl/gs4510.vhdl"
DRIVER = Path(__file__).resolve()
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-mapped-far-dispatch-attribution-receipt.json")

FORMAT = "lisp65-c2.3-v20-mapped-far-dispatch-attribution-v1"
STATUS = "PASS: mapped-far dispatch mechanism named"
MECHANISM = "MAPPED-FAR-LOW-HALF-MAP-TUPLE-TRANSPOSED"
RECORDED_ON = "2026-08-13"
COMMISSION_COMMIT = "12fed5ed"
COMMISSION_SHA256 = (
    "820918d010b6e228bd9316bbaeffa12214b8f8ba19c5114f9972614a997478fa")
ELF_SHA256 = "34fb0a1173d66c2779ec7778ab0ab208bda7fd9a407989e2bb31660e71af4080"
CHIPSET_SHA256 = (
    "107610ae3ea9f7e3f1e78915dcbe2cae1a6f404ca2e538762524a7e58cced220")
GUIDE_SHA256 = "fbf997ec136de3b8d2cecb0f2f19497f2b8a26da24c68e64dd5576cf887ec121"
OPCODES_SHA256 = (
    "20ab38fd9ebbaba020d99f1a444661c310a3d621a61dab55d0122cc4335a2449")
CORE_SHA256 = "ce8c7f120aac11e142add5e08e9a83dc9450b813b211bf310cb95553b4eae957"
GUIDE_COMMIT = "2d0c444a7f086fcc6c4aed9bbaf5ccc17a19ef60"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == 42079 and sha(raw) == COMMISSION_SHA256,
            "dispatch commission identity drift")
    require(b"Dispatch attribution commissioned" in raw
            and b"host/ELF, no device" in raw,
            "dispatch commission text absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def repo_commit(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def body(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    start = symbol.value - section.address
    return raw[start:start + symbol.bytes]


def bytes_at(truth: ElfTruth, section_name: str, address: int,
             count: int) -> bytes:
    section = truth.section(section_name)
    require(section.address <= address
            and address + count <= section.address + section.bytes,
            f"range outside {section_name}: {address:#x}+{count}")
    start = address - section.address
    return truth.section_bytes(section_name)[start:start + count]


def decode_low(a: int, x: int) -> dict[str, Any]:
    offset_units = ((x & 0x0F) << 8) | a
    mask = (x >> 4) & 0x0F
    blocks = [index for index in range(4) if mask & (1 << index)]
    return {
        "A": f"0x{a:02X}", "X": f"0x{x:02X}",
        "offset_units_256": f"0x{offset_units:03X}",
        "physical_offset": f"0x{offset_units << 8:05X}",
        "block_mask": f"0x{mask:X}", "mapped_low_half_blocks": blocks,
        "mapped_CPU_ranges": [
            f"0x{index * 0x2000:04X}-0x{(index + 1) * 0x2000 - 1:04X}"
            for index in blocks],
    }


def map_low20(cpu: int, decoded: dict[str, Any]) -> int:
    block = (cpu >> 13) & 3
    if block not in decoded["mapped_low_half_blocks"]:
        return cpu
    return cpu + int(decoded["physical_offset"], 16)


def source_semantics() -> dict[str, Any]:
    guide = GUIDE.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    opcodes = OPCODES.read_text(encoding="utf-8")
    require("A register and the lower-nibble of the X register form a 12-bit value"
            in guide and "upper nibble of the X register is used as flags" in guide,
            "primary guide MAP semantics drift")
    require("reg_offset_low <= reg_x(3 downto 0) & reg_a;" in core
            and "reg_map_low <= std_logic_vector(reg_x(7 downto 4));" in core
            and "blocknum := to_integer(short_address(14 downto 13));" in core
            and "if reg_map_low(blocknum)='1' then" in core,
            "primary core MAP semantics drift")
    require("EB   ROW $nnnn" in opcodes, "45GS02 ROW opcode identity drift")
    return {
        "normative_decode": (
            "low offset = ((X & 0x0f) << 16) | (A << 8); "
            "low block mask = X >> 4; mask bit n selects CPU block n"),
        "block_index": "CPU address bits 14..13",
        "address_resolution": (
            "selected block: inherited MB-low prefix plus low-20 "
            "offset+logical address; unselected block: ordinary logical address"),
        "opcode_0xEB": "ROW $nnnn",
    }


def elf_facts(truth: ElfTruth) -> dict[str, Any]:
    names = {
        name: truth.symbol(name) for name in (
            "vm_code_load_converged", "c2_physical_read_converged",
            "c2_mapped_far_enter", "c2_mapped_far_leave",
            "c2_dma_read_or_abort", "c2_mapped_far_vm_code_load_converged",
            "c2_mapped_far_physical_read_converged", "nameoff_get",
            "vm_callprim")}
    expected = {
        "vm_code_load_converged": (0xB3B0, 9),
        "c2_physical_read_converged": (0xB3B9, 9),
        "c2_mapped_far_enter": (0xB3C2, 19),
        "c2_mapped_far_leave": (0xB3D5, 15),
        "c2_dma_read_or_abort": (0xB3E4, 46),
        "c2_mapped_far_vm_code_load_converged": (0x79DC, 93),
        "c2_mapped_far_physical_read_converged": (0x7BBA, 98),
        "nameoff_get": (0x3143, 99), "vm_callprim": (0x6A7C, 4744),
    }
    require(all((row.value, row.bytes) == expected[name]
                for name, row in names.items()), "linked symbol identity drift")
    facade = body(truth, "vm_code_load_converged")
    enter = body(truth, "c2_mapped_far_enter")
    wrapper = body(truth, "c2_dma_read_or_abort")
    nameoff = body(truth, "nameoff_get")
    require(facade == bytes.fromhex("20c2b320dc794cd5b3"),
            "far facade call sequence drift")
    require(enter == bytes.fromhex(
        "48da5aa980a224a000a3805ceaa3007afa6860"),
        "MAP trampoline bytes drift")
    require(wrapper[0x21:0x24] == bytes.fromhex("20b0b3"),
            "DMA wrapper facade call drift")
    require(nameoff[0x3D:0x40] == bytes.fromhex("20e4b3")
            and nameoff[0x42:0x46] == bytes.fromhex("8504a001"),
            "nameoff call/BRK-site identity drift")
    ordinary = bytes_at(truth, ".text", 0x79D8, 32)
    service = bytes_at(truth, ".lisp65_c2_mapped_far_service", 0x79D8, 32)
    require(ordinary[4:7] == bytes.fromhex("eb7aa6")
            and service[4:7] == bytes.fromhex("850a86")
            and ordinary != service,
            "overlapping entry streams no longer contradict")
    require(names["vm_callprim"].section == ".text"
            and names["vm_callprim"].value <= 0x79DC
            < names["vm_callprim"].value + names["vm_callprim"].bytes,
            "ordinary first-fetch owner drift")
    return {
        "facade": {
            "VMA": "0xB3B0", "bytes": facade.hex(),
            "sequence": ["JSR $B3C2", "JSR $79DC", "JMP $B3D5"],
        },
        "map_trampoline": {
            "VMA": "0xB3C2", "bytes": enter.hex(),
            "register_sequence": ["LDA #$80", "LDX #$24", "LDY #$00",
                                  "LDZ #$80", "MAP", "EOM"],
        },
        "caller_chain": [
            "nameoff_get: JSR $B3E4 at $3180",
            "c2_dma_read_or_abort: JSR $B3B0 at $B405",
            "vm_code_load_converged: JSR enter; JSR $79DC; JMP leave",
        ],
        "first_far_entry": {
            "logical_VMA": "0x79DC", "intended_physical": "0x0002B9DC",
            "service_bytes": service[4:20].hex(),
            "ordinary_text_owner": "vm_callprim",
            "ordinary_bytes": ordinary[4:20].hex(),
            "first_wrong_opcode": "0xEB (ROW $A67A)",
        },
        "BRK_site": {
            "logical_opcode_address": "0x3185",
            "stacked_continuation": "0x3187",
            "linked_nameoff_bytes": nameoff[0x42:0x46].hex(),
            "linked_opcode": "0x85 (STA zp)",
        },
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    installation = load(INSTALLATION)
    device = load(DEVICE)
    require(installation["decision"]["selected_row"] == "PRESENT"
            and installation["decision"]["service_probe_matches"] == 3,
            "installed far-service authority drift")
    require(device["decision"]["BRK"]["stacked_B"] == 1
            and device["decision"]["BRK"]["stacked_continuation"] == "0x3187"
            and device["contact"]["tuple_first"]["MAPL"] == "0x2480"
            and device["contact"]["cpu_view"]["nameoff_get"]["raw_hex"]
            == "00" * 99,
            "captured MAP/BRK authority drift")
    map_tuple = contract["mapped_far_service"]["map_tuple"]
    require((map_tuple["maplo_a"], map_tuple["maplo_x"],
             map_tuple["maphi_y"], map_tuple["maphi_z"])
            == ("0x80", "0x24", "0x00", "0x80"),
            "contracted map tuple drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    actual = decode_low(0x80, 0x24)
    intended = decode_low(0x40, 0x82)
    require(actual["physical_offset"] == "0x48000"
            and actual["mapped_low_half_blocks"] == [1],
            "actual low MAP decode drift")
    require(intended["physical_offset"] == "0x24000"
            and intended["mapped_low_half_blocks"] == [3],
            "intended low MAP decode drift")
    require(map_low20(0x79DC, actual) == 0x79DC
            and map_low20(0x3185, actual) == 0x4B185,
            "first-call mapping model drift")
    require(repo_commit(GUIDE_ROOT) == GUIDE_COMMIT,
            "MEGA65 user-guide checkout drift")
    require(repo_commit(CORE_ROOT) == CORE_COMMIT,
            "MEGA65 core checkout drift")
    facts = elf_facts(truth)
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "mechanism": MECHANISM, "root_cause_named": True,
        "primary_MAP_semantics": source_semantics(),
        "captured_and_linked_tuple": {
            "monitor_field": "MAPL=0x2480",
            "ELF_register_tuple": {"A": "0x80", "X": "0x24",
                                   "Y": "0x00", "Z": "0x80"},
            "note": (
                "the monitor field is bound as observed; normative bit meaning "
                "comes from the delivered A/X operands and primary MAP sources"),
        },
        "mapping_decode": {
            "actual": actual, "intended": intended,
            "intended_relation": "0x6000 + 0x24000 = 0x0002A000",
            "correct_low_tuple": {"A": "0x40", "X": "0x82"},
            "contract_error": (
                "the contract transposed the A/X responsibilities: it treated "
                "A's upper nibble as the mask and X as offset bits 12..19"),
            "actual_effect": (
                "only block 1 ($2000-$3FFF) is mapped by +$48000; block 3 "
                "($6000-$7FFF), containing the far-service VMA, is not mapped"),
        },
        "linked_dispatch": facts,
        "first_call_model": {
            "service_VMA": "0x79DC",
            "expected_target_low20": "0x2B9DC",
            "actual_target_low20": "0x079DC",
            "service_entry_reached": False,
            "first_fetch_contradiction": "expected service 0x85; fetched .text 0xEB",
            "caller_BRK_low20": "0x4B185",
            "caller_expected_low20": "0x03185",
            "captured_BRK_consistency": (
                "the active wrong map replaces nameoff_get's linked STA opcode "
                "at $3185; B=1 and continuation $3187 are the resulting "
                "software-BRK signature"),
            "descriptor_all_zero_consistency": (
                "the service entry was skipped, so no descriptor initializer ran"),
            "model_boundary": (
                "the first wrong fetch and both translated/untranslated targets "
                "are exact; the intervening unintended instruction trace is not "
                "claimed or needed for the mechanism"),
        },
        "supersessions": [{
            "claim": "contracted tuple maps CPU block 3 to $02A000-$02BFFF",
            "status": "false under primary MAP semantics",
        }, {
            "claim": "captured MAPL=$2480 proves a service exit left block 3 mapped",
            "status": "withdrawn; it proves the transposed entry tuple remained active",
        }],
        "claim_limit": (
            "Host/ELF attribution of the delivered tuple and captured state only. "
            "No source fix, card, device contact, D2-D5, product-wide correctness, "
            "release, or complete unintended dynamic trace claim."),
        "disposition": {"fix_authorized": False, "card_authorized": False,
                        "device_contact_authorized": False,
                        "D2_D5_open": False},
        "next": (
            "owner disposition over correction of the low-half tuple to A=$40, "
            "X=$82, with a linked-image MAP decode/pairing gate"),
        "authorities": {
            "commission": git_bind(COMMISSION_COMMIT, PLAN),
            "installation_result": bind(INSTALLATION),
            "device_result": bind(DEVICE), "candidate_ELF": bind(ELF),
            "ownership_contract": bind(CONTRACT), "facade_source": bind(FACADE),
            "chipset_reference_PDF": bind(CHIPSET_PDF),
            "MEGA65_user_guide": bind(GUIDE), "opcode_table": bind(OPCODES),
            "MEGA65_core_RTL": bind(CORE), "driver": bind(DRIVER),
            "upstream_commits": {"user_guide": GUIDE_COMMIT, "core": CORE_COMMIT},
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value.get("mechanism") == MECHANISM
            and value.get("root_cause_named") is True,
            "dispatch attribution status drift")
    authority = value["authorities"]
    require(authority["commission"]["sha256"] == COMMISSION_SHA256
            and authority["candidate_ELF"]["sha256"] == ELF_SHA256
            and authority["chipset_reference_PDF"]["sha256"] == CHIPSET_SHA256
            and authority["MEGA65_user_guide"]["sha256"] == GUIDE_SHA256
            and authority["opcode_table"]["sha256"] == OPCODES_SHA256
            and authority["MEGA65_core_RTL"]["sha256"] == CORE_SHA256
            and authority["upstream_commits"]
            == {"user_guide": GUIDE_COMMIT, "core": CORE_COMMIT},
            "primary or candidate authority drift")
    mapping = value["mapping_decode"]
    require(mapping["actual"] == decode_low(0x80, 0x24)
            and mapping["intended"] == decode_low(0x40, 0x82)
            and mapping["correct_low_tuple"] == {"A": "0x40", "X": "0x82"}
            and "transposed" in mapping["contract_error"],
            "MAP decode or tuple diagnosis drift")
    dispatch = value["linked_dispatch"]
    require(dispatch["facade"]["sequence"]
            == ["JSR $B3C2", "JSR $79DC", "JMP $B3D5"]
            and dispatch["map_trampoline"]["register_sequence"]
            == ["LDA #$80", "LDX #$24", "LDY #$00", "LDZ #$80", "MAP", "EOM"]
            and dispatch["first_far_entry"]["ordinary_text_owner"] == "vm_callprim"
            and dispatch["first_far_entry"]["first_wrong_opcode"]
            == "0xEB (ROW $A67A)"
            and dispatch["BRK_site"]["linked_opcode"] == "0x85 (STA zp)",
            "linked dispatch identity drift")
    model = value["first_call_model"]
    require(model["expected_target_low20"] == "0x2B9DC"
            and model["actual_target_low20"] == "0x079DC"
            and model["service_entry_reached"] is False
            and model["caller_BRK_low20"] == "0x4B185"
            and model["caller_expected_low20"] == "0x03185"
            and "not claimed" in model["model_boundary"],
            "first-call model or boundary drift")
    require(value["disposition"] == {
        "fix_authorized": False, "card_authorized": False,
        "device_contact_authorized": False, "D2_D5_open": False},
        "attribution widened into implementation or contact")
    require("No source fix" in value["claim_limit"]
            and len(value["supersessions"]) == 2,
            "claim limit or supersession drift")


def mutations(value: dict[str, Any]) -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "decode-block3": lambda x: x["mapping_decode"]["actual"].update(
            mapped_low_half_blocks=[3]),
        "decode-offset-24000": lambda x: x["mapping_decode"]["actual"].update(
            physical_offset="0x24000"),
        "preserve-transposed-tuple": lambda x: x["mapping_decode"].update(
            correct_low_tuple={"A": "0x80", "X": "0x24"}),
        "claim-service-entry": lambda x: x["first_call_model"].update(
            service_entry_reached=True),
        "map-first-call-to-service": lambda x: x["first_call_model"].update(
            actual_target_low20="0x2B9DC"),
        "leave-caller-unmapped": lambda x: x["first_call_model"].update(
            caller_BRK_low20="0x03185"),
        "replace-linked-trampoline": lambda x: x["linked_dispatch"][
            "map_trampoline"].update(register_sequence=["LDA #$40", "LDX #$82"]),
        "rename-wrong-owner": lambda x: x["linked_dispatch"][
            "first_far_entry"].update(ordinary_text_owner="far-service"),
        "erase-primary-RTL": lambda x: x["authorities"][
            "MEGA65_core_RTL"].update(sha256="0" * 64),
        "erase-supersession": lambda x: x.update(supersessions=[]),
        "claim-full-dynamic-trace": lambda x: x["first_call_model"].update(
            model_boundary="complete dynamic trace proven"),
        "authorize-fix": lambda x: x["disposition"].update(fix_authorized=True),
        "authorize-contact": lambda x: x["disposition"].update(
            device_contact_authorized=True),
        "open-D2-D5": lambda x: x["disposition"].update(D2_D5_open=True),
    }


def expected() -> dict[str, Any]:
    value = derive()
    rejected: dict[str, str] = {}
    for name, mutate in mutations(value).items():
        changed = deepcopy(value)
        mutate(changed)
        try:
            validate(changed)
        except (AttributionError, KeyError, TypeError) as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"dispatch mutation survived: {name}")
    value["mutations_rejected"] = rejected
    return value


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_mapped_far_dispatch_attribution.py "
            "record|check|selftest")
    value = expected()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "dispatch attribution receipt stale")
    print("v2.0 mapped-far dispatch attribution: "
          f"PASS mechanism={MECHANISM} mutations={len(mutations(value))}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as error:
        print(f"v2.0 mapped-far dispatch attribution: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
