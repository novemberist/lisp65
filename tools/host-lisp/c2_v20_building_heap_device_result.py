#!/usr/bin/env python3
"""Close the one authorized v2.0 D1 BUILDING-HEAP stopped-state row.

The physical contact reached the first two boot-liveness lines and then the
product-owned red fail-closed frame. Exactly one stopped session captured the
register tuple, CPU-view fail-loop bytes, Page 1 and the ten pre-registered
physical Bank-0 ranges. This checker binds those raw observations to the exact
candidate ELF, mapped-far contract and audited 45GS02 stack semantics.

The result names a mapped-far return/instruction-identity contradiction. It
does not invent the live byte at the stacked BRK address, identify the earlier
corruptor, authorize a fix, reopen D2--D5 or touch a device.
"""

from __future__ import annotations

import argparse
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

from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CAPTURE_CONTRACT = ROOT / "config/c2-v20-building-heap-capture-row.json"
ATTRIBUTION = EVIDENCE / "c2.3-v2.0-building-heap-attribution-receipt.json"
MEDIA = EVIDENCE / (
    "c2.3-v2.0-crc-carveout-media-liveness-closure-receipt.json")
IRQ_DESK = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-desk-attribution-receipt.json")
MAP_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
FAR_FACADE = ROOT / "src/c2_mapped_far_service.s"
FAR_BODY = ROOT / "src/c2_mapped_far_convergence.s"
WINDOW = ROOT / "src/c2_kernal_window.s"
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = EVIDENCE / "c2.3-v2.0-building-heap-device-receipt.json"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-building-heap-device-result-v1"
STATUS = "D1-HEAP-RED; MAPPED-FAR-RETURN-INSTRUCTION-IDENTITY-CONTRADICTION"
RECORDED_ON = "2026-08-12"
AUTHORIZATION_COMMIT = "6bbf828a"
ELF_SHA256 = "34fb0a1173d66c2779ec7778ab0ab208bda7fd9a407989e2bb31660e71af4080"
PRODUCT_D81_SHA256 = (
    "704c60a3979b4a1b5b55f7ccf8de95d99b2ef9fb82c462dfe496952af3ab4dde")
LIBRARY_D81_SHA256 = (
    "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060")

TUPLE = {
    "PC": "0xE096", "SP": "0x01C9", "A": "0x02", "X": "0x00",
    "Y": "0xB4", "Z": "0x00", "B": "0x00", "MB": "0x00",
    "P": "0x24", "MAPH": "0x8000", "MAPL": "0x2480",
    "ROMC": False,
    "CPU_port": {"LORAM": True, "HIRAM": True, "CHAREN": False},
}
CPU_VIEW_PC_HEX = (
    "4c96e09d0008608508ae8ec0ac8fc0a9025aa4048406a40584077a8404a40884")
STACK_HEX = (
    "0000000000000000000000000000000000e300b3a0820083001180b100e00083"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000042e400b40000328731b803bb2e2f0060605cc5390105ddc9"
    "2240a818005ca46218004920de276420b103b300e300833dc1ea2d31ea362f20")

PHYSICAL = {
    "allocator-zp": (0x003D, 16, "00000000600000000000000000000000"),
    "vm-and-boot-zp": (
        0x005F, 21, "03000000e000000000000000000000000000000901"),
    "ownership-and-convergence-zp": (
        0x0087, 9, "020000000000000000"),
    "ordinary-dma-list": (0xB9D3, 12, "000200a3cf0022fa05000000"),
    "gc-runs": (0xB9EE, 2, "0000"),
    "pending-error-pointer": (0xBFEF, 2, "0000"),
    "runtime-overlay-state": (0xBFF7, 4, "00810000"),
    "convergence-state": (0xC000, 66, "00" * 66),
    "c2-runtime-state": (0xC080, 50, "00" * 50),
}

SCREEN = {
    "visible_lines": ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP"],
    "absent_lines": ["LISP65: LOADING LIBRARIES", "WORKBENCH 1.5.0",
                     "lisp65>"],
    "frame": "red",
    "png_sha256": (
        "71ed655d921a0ffa34ddf46d701d6811d90f0b1d5ec0ff511964b9f5b40076d2"),
    "text_sha256": (
        "ab942ccbb45823f713e4269826bdacce0bafc9ad9e6f92e81ddc0335a4ef8c3d"),
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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
    completed = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(completed.stdout), "sha256": sha(completed.stdout)}


def alloc_bytes(truth: ElfTruth, address: int, count: int,
                *, section: str | None = None) -> bytes:
    owners = [row for row in truth.sections_at_vma(address)
              if "SHF_ALLOC" in row.flags and row.section_type == "SHT_PROGBITS"
              and (section is None or row.name == section)
              and address + count <= row.address + row.bytes]
    require(len(owners) == 1,
            f"VMA 0x{address:04X} lacks one linked byte owner: {owners}")
    owner = owners[0]
    data = truth.section_bytes(owner.name)
    offset = address - owner.address
    return data[offset:offset + count]


def linked_facts() -> dict[str, Any]:
    require(bind(ELF)["sha256"] == ELF_SHA256, "candidate ELF identity drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    nameoff = truth.symbol("nameoff_get")
    wrapper = truth.symbol("c2_dma_read_or_abort")
    facade = truth.symbol("vm_code_load_converged")
    enter = truth.symbol("c2_mapped_far_enter")
    leave = truth.symbol("c2_mapped_far_leave")
    done = truth.symbol("c2_dma_verify_done")
    require((nameoff.value, nameoff.bytes, nameoff.section)
            == (0x3143, 99, ".text"), "nameoff_get identity drift")
    require((wrapper.value, wrapper.bytes) == (0xB3E4, 46)
            and (facade.value, facade.bytes) == (0xB3B0, 9),
            "mapped-far wrapper identity drift")
    require((enter.value, enter.bytes) == (0xB3C2, 19)
            and (leave.value, leave.bytes) == (0xB3D5, 15),
            "mapped-far enter/leave identity drift")
    require((done.value, done.bytes, done.section)
            == (0x87, 1, ".lisp65_c2_convergence_zp"),
            "convergence commit-slot identity drift")
    require(alloc_bytes(truth, 0x3180, 16, section=".text")
            == bytes.fromhex("20e4b3b2168504a001b116aaa5048512"),
            "nameoff_get call/return neighborhood drift")
    require(alloc_bytes(truth, 0xE096, 3) == bytes.fromhex("4c96e0")
            and bytes.fromhex(CPU_VIEW_PC_HEX)[:3] == bytes.fromhex("4c96e0"),
            "live fail-loop bytes do not bind to the candidate")
    require(alloc_bytes(truth, facade.value, facade.bytes,
                        section=facade.section)
            == bytes.fromhex("20c2b320dc794cd5b3"),
            "mapped-far facade call/leave chain drift")
    require(alloc_bytes(truth, enter.value, enter.bytes,
                        section=enter.section)
            == bytes.fromhex("48da5aa980a224a000a3805ceaa3007afa6860")
            and alloc_bytes(truth, leave.value, leave.bytes,
                            section=leave.section)
            == bytes.fromhex("48a900a200a000a3805cea68a30060"),
            "mapped-far mapping byte contract drift")
    return {
        "fail_closed_live_PC": {
            "PC": "0xE096", "owner": "c2_kernal_fail_closed",
            "CPU_view_hex": CPU_VIEW_PC_HEX,
            "candidate_prefix_hex": "4c96e0",
            "result": "exact fail-loop identity",
        },
        "stacked_continuation_owner": {
            "function": "nameoff_get", "start": "0x3143", "bytes": 99,
            "call": {"PC": "0x3180", "instruction": "JSR $B3E4",
                     "callee": "c2_dma_read_or_abort"},
            "post_call": [
                {"PC": "0x3183", "bytes": "b216", "instruction": "LDA ($16),Z"},
                {"PC": "0x3185", "bytes": "8504", "instruction": "STA $04"},
                {"PC": "0x3187", "bytes": "a001", "instruction": "LDY #$01"},
            ],
        },
        "mapped_facade": {
            "entry": "0xB3B0", "enter": "0xB3C2", "leave": "0xB3D5",
            "call_far_service": "JSR $79DC", "leave_edge": "JMP $B3D5",
            "restore_tuple": {"A": "0x00", "X": "0x00", "Y": "0x00",
                              "Z": "0x80", "resulting_MAPL": "0x0000"},
        },
        "commit_slot": {"symbol": "c2_dma_verify_done", "address": "0x0087"},
    }


def device_facts() -> dict[str, Any]:
    stack = bytes.fromhex(STACK_HEX)
    require(len(stack) == 256, "Page-1 capture length drift")
    sp = int(TUPLE["SP"], 0) & 0xFF
    frame = stack[sp + 1:sp + 8]
    require(frame == bytes.fromhex("00b40000328731"),
            "hardware/handler frame bytes drift")
    stacked_p = frame[4]
    return_pc = frame[5] | frame[6] << 8
    require(stacked_p & 0x10 and return_pc == 0x3187,
            "software-BRK frame discriminator drift")
    irq = load(IRQ_DESK)
    core = irq["authorities"]["tested_core_CPU"]
    require(core["semantic_result"] == (
        "hardware IRQ stacks B=0 and the resume PC; BRK stacks B=1 "
        "and the PC two bytes after opcode $00"),
        "tested-core BRK/IRQ authority drift")
    require(irq["stack_and_mapping"]["capture_stack_rule"].startswith(
        "after hardware frame plus PHA/PHX/PHY/PHZ"),
        "handler stack-layout authority drift")

    map_contract = load(MAP_CONTRACT)["mapped_far_service"]
    map_tuple = map_contract["map_tuple"]
    require(map_contract["cpu_window"] == {
                "start": "0x6000", "end_exclusive": "0x8000", "block": 3,
                "capacity_bytes": 8192}
            and map_tuple["maplo_a"] == "0x80"
            and map_tuple["maplo_x"] == "0x24"
            and map_tuple["restore_a"] == "0x00"
            and map_tuple["restore_x"] == "0x00",
            "mapped-far contract drift")
    require(TUPLE["MAPL"] == "0x2480" and TUPLE["MAPH"] == "0x8000",
            "captured mapping tuple drift")
    require(not (0x6000 <= 0x3185 < 0x8000),
            "stacked opcode site unexpectedly lies in mapped block 3")
    window = WINDOW.read_text(encoding="utf-8")
    handler = window.split("c2_kernal_irq_handler:", 1)[1].split(
        "c2_kernal_output_cell:", 1)[0]
    require("\tmap" not in handler and "\teom" not in handler,
            "IRQ/fail path now changes mapping")

    state = {name: {"physical_address": f"0x{address:08X}",
                    "bytes": count, "raw_hex": raw}
             for name, (address, count, raw) in PHYSICAL.items()}
    done = bytes.fromhex(PHYSICAL["ownership-and-convergence-zp"][2])[0]
    far = FAR_BODY.read_text(encoding="utf-8")
    require(".equ C2_MARKER, 0xa5" in far
            and ".equ C2_MARKER_CLEAR, 0x5a" in far,
            "convergence marker contract drift")
    require(done == 0x02 and done not in (0x5A, 0xA5),
            "captured convergence commit-slot classification drift")
    require(bytes.fromhex(PHYSICAL["gc-runs"][2]) == b"\0\0"
            and bytes.fromhex(PHYSICAL["pending-error-pointer"][2]) == b"\0\0",
            "clean GC/error exclusions drift")
    require(bytes.fromhex(PHYSICAL["convergence-state"][2]) == bytes(66)
            and bytes.fromhex(PHYSICAL["c2-runtime-state"][2]) == bytes(50),
            "captured state-plane bytes drift")
    return {
        "screen": SCREEN,
        "tuple_first": TUPLE,
        "one_stopped_session": {
            "contacts": 1, "stops": 1, "resumes": 0,
            "CPU_left_stopped": True, "D2_D5_executed": False,
            "pre_stop_external_observations_after_red": 1,
        },
        "hardware_frame": {
            "handler_SP": "0xC9",
            "saved": {"Z": "0x00", "Y": "0xB4", "X": "0x00", "A": "0x00"},
            "stacked_P": "0x32", "stacked_B": 1,
            "stacked_continuation": "0x3187",
            "candidate_BRK_opcode_address": "0x3185",
            "tested_core_semantics": core["semantic_result"],
        },
        "mapping": {
            "captured": {"MAPH": "0x8000", "MAPL": "0x2480"},
            "meaning": "mapped far-service CPU block 3 remains selected",
            "handler_or_fail_path_changes_mapping": False,
            "required_after_normal_facade_return": "MAPL=0x0000",
            "stacked_opcode_site_affected_by_block3_map": False,
        },
        "physical_state": state,
        "convergence_commit": {
            "symbol": "c2_dma_verify_done", "address": "0x0087",
            "observed": "0x02", "clear": "0x5A", "committed": "0xA5",
            "valid_state": False,
        },
        "readback_identity": {
            "product_D81_sha256": PRODUCT_D81_SHA256,
            "library_D81_sha256": LIBRARY_D81_SHA256,
        },
    }


def derive() -> dict[str, Any]:
    capture = load(CAPTURE_CONTRACT)
    attribution = load(ATTRIBUTION)
    media = load(MEDIA)
    require(capture["observation"]["stop_count"] == 1
            and capture["observation"]["resume_count"] == 0,
            "capture-row stop boundary drift")
    require(attribution["status"]
            == "HOST-GREEN-NO-MECHANISM; ONE-STOPPED-STATE-ROW-SPECIFIED",
            "host attribution authority drift")
    require(media["shared_system"]["product_D81"]["sha256"]
            == PRODUCT_D81_SHA256
            and media["library"]["D81"]["sha256"] == LIBRARY_D81_SHA256,
            "contact media identity drift")
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": STATUS,
        "authorities": {
            "owner_authorization": git_bind(AUTHORIZATION_COMMIT, PLAN),
            "capture_contract": bind(CAPTURE_CONTRACT),
            "host_attribution": bind(ATTRIBUTION),
            "media_closure": bind(MEDIA),
            "tested_core_and_stack_semantics": bind(IRQ_DESK),
            "mapped_far_contract": bind(MAP_CONTRACT),
            "mapped_far_facade_source": bind(FAR_FACADE),
            "mapped_far_body_source": bind(FAR_BODY),
            "IRQ_window_source": bind(WINDOW),
            "candidate_ELF": bind(ELF),
            "result_driver": bind(DRIVER),
        },
        "device": device_facts(),
        "linked_candidate": linked_facts(),
        "classification": {
            "capture_row_consumed": True,
            "selected_pre_registered_rows": [
                "runtime-family-or-convergence", "wild-control-flow"],
            "immediate_terminal_cause": (
                "second consecutive source-less/BRK-class entry selected the "
                "product-owned fail-closed loop"),
            "first_real_mechanism_evidence": (
                "the mapped-far content-read call returned to nameoff_get with "
                "the far-service MAP still selected, an invalid convergence "
                "commit byte, and a B=1 frame whose continuation is two bytes "
                "after the candidate's linked STA $04"),
            "proved": [
                "D1 reached STAGING MEDIA and BUILDING HEAP but not LOADING LIBRARIES",
                "the live stopped PC is the exact candidate fail-closed loop",
                "the terminal hardware frame has B=1 and continuation $3187",
                "the linked candidate has STA $04 bytes $85 $04 at $3185",
                "normal vm_code_load_converged return must execute mapped-far leave",
                "MAPL remained $2480 and c2_dma_verify_done was invalid $02",
                "GC count and pending error pointer were both zero",
            ],
            "not_proved": [
                "the post-stop live CPU-view byte at $3185",
                "whether $3185 was stale, overwritten or reached via a corrupt frame",
                "which earlier instruction or writer broke the return/instruction identity",
                "a heap, OOM, GC-loop, product fix or release result",
            ],
            "root_cause_named": False,
            "next": "owner disposition over the mapped-far return/instruction-view contradiction",
        },
        "session_disposition": {
            "D1": "red-with-complete-stopped-state-row",
            "D2_D5_open": False,
            "recontact_authorized": False,
            "fix_authorized": False,
            "additional_device_reads_authorized": False,
            "CPU_left_stopped": True,
        },
        "claim_limit": (
            "One consumed D1 stopped-state row. It proves a software-BRK-class "
            "frame and a mapped-far return/instruction-identity contradiction, "
            "not the post-stop live byte at $3185, the earlier corruptor, a "
            "specific fix, another device read/contact, D2-D5 or release readiness."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "device result identity drift")
    contact = value["device"]["one_stopped_session"]
    frame = value["device"]["hardware_frame"]
    mapping = value["device"]["mapping"]
    commit = value["device"]["convergence_commit"]
    classification = value["classification"]
    disposition = value["session_disposition"]
    require(contact == {"contacts": 1, "stops": 1, "resumes": 0,
                        "CPU_left_stopped": True, "D2_D5_executed": False,
                        "pre_stop_external_observations_after_red": 1},
            "one-session contact boundary drift")
    require(frame["stacked_P"] == "0x32" and frame["stacked_B"] == 1
            and frame["stacked_continuation"] == "0x3187"
            and frame["candidate_BRK_opcode_address"] == "0x3185",
            "software-BRK frame facts drift")
    require(mapping["captured"] == {"MAPH": "0x8000", "MAPL": "0x2480"}
            and mapping["required_after_normal_facade_return"] == "MAPL=0x0000"
            and mapping["handler_or_fail_path_changes_mapping"] is False,
            "mapped-far return contradiction drift")
    require(commit == {"symbol": "c2_dma_verify_done", "address": "0x0087",
                       "observed": "0x02", "clear": "0x5A",
                       "committed": "0xA5", "valid_state": False},
            "invalid convergence commit fact drift")
    require(classification["capture_row_consumed"] is True
            and classification["root_cause_named"] is False
            and "the post-stop live CPU-view byte at $3185"
            in classification["not_proved"],
            "device claim boundary broadened")
    require(disposition == {
                "D1": "red-with-complete-stopped-state-row",
                "D2_D5_open": False, "recontact_authorized": False,
                "fix_authorized": False,
                "additional_device_reads_authorized": False,
                "CPU_left_stopped": True},
            "session disposition drift")
    if verify:
        require(value == derive(), "device receipt differs from bound evidence")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-D1-green": lambda x: x.update(status="D1-GREEN"),
        "clear-stacked-B": lambda x:
            x["device"]["hardware_frame"].update(stacked_B=0),
        "move-return-PC": lambda x:
            x["device"]["hardware_frame"].update(stacked_continuation="0x3185"),
        "claim-restored-map": lambda x:
            x["device"]["mapping"]["captured"].update(MAPL="0x0000"),
        "accept-invalid-commit": lambda x:
            x["device"]["convergence_commit"].update(valid_state=True),
        "claim-live-3185": lambda x:
            x["classification"]["not_proved"].remove(
                "the post-stop live CPU-view byte at $3185"),
        "name-root-cause": lambda x:
            x["classification"].update(root_cause_named=True),
        "open-D2-D5": lambda x:
            x["session_disposition"].update(D2_D5_open=True),
        "authorize-read": lambda x:
            x["session_disposition"].update(additional_device_reads_authorized=True),
        "authorize-fix": lambda x:
            x["session_disposition"].update(fix_authorized=True),
        "resume": lambda x:
            x["device"]["one_stopped_session"].update(resumes=1),
        "second-stop": lambda x:
            x["device"]["one_stopped_session"].update(stops=2),
        "leave-running": lambda x:
            x["session_disposition"].update(CPU_left_stopped=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "device-result mutation survived")
    return rejected


def build() -> int:
    require(not RECEIPT.exists(), "device receipt already exists")
    value = derive()
    validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v2.0 BUILDING-HEAP device result: PASS mapped-far identity red")
    return 0


def rebind() -> int:
    require(RECEIPT.is_file(), "device receipt absent")
    value = derive()
    validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v2.0 BUILDING-HEAP device result: PASS loud-authority-rebind")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "device mutation receipt drift")
    print("v2.0 BUILDING-HEAP device result check: PASS")
    return 0


def selftest() -> int:
    value = derive()
    validate(value, verify=False)
    require(len(mutations(value)) == 13, "device mutation count drift")
    print("v2.0 BUILDING-HEAP device result selftest: PASS mutations=13")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "build", "rebind", "check", "selftest"))
    action = parser.parse_args().action
    return {"build": build, "rebind": rebind,
            "check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 BUILDING-HEAP device result: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
