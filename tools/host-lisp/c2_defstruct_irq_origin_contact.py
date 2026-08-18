#!/usr/bin/env python3
"""Prepare and close the one authorized defstruct IRQ-origin capture row.

The existing Link-92-r5 diagnostic medium already diverts the terminal
fail-closed edge into a 132-byte ordinary-RAM capture body.  Immediately before
the measured form this contact replaces only that non-promotable body and the
65-byte diagnostic record.  The replacement snapshots the hardware frame,
live resume bytes and the authorized interrupt-source registers with the
target CPU, commits the row last, and enters the same terminal hold.  It never
changes a product or medium byte and never resumes after read-to-clear I/O.
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
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
import c2_defstruct_irq_origin_attribution as DESK  # noqa: E402
import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
from c2_v16_defstruct_phase_c import Code, u16  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-preparation-receipt.json")
DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-device-receipt.json")
RUNNER = ROOT / "scripts/c2-defstruct-irq-origin-hw.sh"
OUT = ROOT / "build/c2.3/defstruct-irq-origin-contact"
CAPTURE_BODY = OUT / "irq-origin-fail-capture.bin"
RECORD_RESET = OUT / "irq-origin-record-reset.bin"

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-irq-origin-contact-preparation-v1"
DEVICE_FORMAT = "lisp65-c2.3-post-v1.4-defstruct-irq-origin-contact-device-v1"
RECORDED_ON = "2026-08-10"
AUTHORIZATION_COMMIT = "3bcaded3"
AUTHORIZATION_PATH = "docs/planning/post-v1.4.0-direction-plan.md"
PREPARATION_COMMIT = "6ca037e5"

CODE0 = 0xB3B0
CAPTURE_BYTES = 132
RECORD = 0xC03F
RECORD_BYTES = 65
COMPLETE_SENTINEL = 0x71
COMPLETE_TAG = 0xD0

FIELDS = {
    "complete": 0,
    "stacked_P": 1,
    "stacked_PCL": 2,
    "stacked_PCH": 3,
    "resume_PC_minus_2": 4,
    "resume_PC_minus_1": 5,
    "resume_PC": 6,
    "resume_PC_plus_1": 7,
    "CIA1_ICR": 8,
    "CIA2_ICR": 9,
    "Ethernet_IRQ": 10,
    "AutoIEC_IRQ": 11,
    "AudioDMA_IRQ": 12,
    "episode_latch": 13,
    "D019_witness": 14,
    "D01A": 15,
}

IO_SOURCES = (
    (0xDC0D, "CIA1_ICR"),
    (0xDD0D, "CIA2_ICR"),
    (0xD6E1, "Ethernet_IRQ"),
    (0xD697, "AutoIEC_IRQ"),
    (0xD713, "AudioDMA_IRQ"),
    (0xFF86, "episode_latch"),
    (0xFF89, "D019_witness"),
    (0xD01A, "D01A"),
)


class ContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContactError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def git_bind(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def historical_file_bind(commit: str, path: str) -> dict[str, Any]:
    row = git_bind(commit, path)
    return {"path": path, "bytes": row["bytes"], "sha256": row["sha256"]}


def record_reset() -> bytes:
    return bytes((COMPLETE_SENTINEL,)) + bytes((0xCC,)) * (RECORD_BYTES - 1)


def capture_body() -> bytes:
    code = Code()
    code.add(0xBA)  # TSX: X is the handler SP after Z/Y/X/A pushes.
    for stack_offset, name in ((5, "stacked_P"),
                               (6, "stacked_PCL"),
                               (7, "stacked_PCH")):
        code.lda_stack_x(stack_offset)
        code.sta_abs(RECORD + FIELDS[name])

    # Materialize return-PC-2 in $04/$05, carrying the low-byte borrow.
    code.lda_abs(RECORD + FIELDS["stacked_PCL"])
    code.add(0x38)                 # SEC
    code.add(0xE9, 2)             # SBC #2
    code.sta_zp(0x04)
    code.lda_abs(RECORD + FIELDS["stacked_PCH"])
    code.add(0xE9, 0)             # SBC #0 with propagated borrow
    code.sta_zp(0x05)
    for z_value, name in enumerate((
        "resume_PC_minus_2", "resume_PC_minus_1",
        "resume_PC", "resume_PC_plus_1",
    )):
        code.add(0xA3, z_value)    # LDZ #n
        code.lda_ind_z(0x04)
        code.sta_abs(RECORD + FIELDS[name])

    # CPU-side I/O. CIA ICR reads are intentionally once-only/read-to-clear.
    for source, name in IO_SOURCES:
        code.lda_abs(source)
        code.sta_abs(RECORD + FIELDS[name])

    code.tag(RECORD + FIELDS["complete"], COMPLETE_TAG)  # commit last
    code.add(0x78)                 # SEI (already set, explicit terminal edge)
    code.parts.append(b"\x9c" + u16(0xD01A))  # STZ $D01A
    code.lda_imm(2)
    code.sta_abs(0xD020)
    loop = CODE0 + len(code.bytes())
    code.jmp(loop)
    payload = code.bytes()
    require(len(payload) <= CAPTURE_BYTES,
            f"origin body exceeds inherited terminal arena: {len(payload)}")
    return payload + b"\xea" * (CAPTURE_BYTES - len(payload))


def emulate(body: bytes, *, sp: int, stacked_p: int, resume_pc: int,
            neighborhood: bytes, io: dict[int, int]) -> bytes:
    require(len(neighborhood) == 4, "four live resume bytes required")
    mem: dict[int, int] = {address: value for address, value in io.items()}
    reset = record_reset()
    mem.update({RECORD + index: value for index, value in enumerate(reset)})
    mem[0x0100 + ((sp + 5) & 0xFF)] = stacked_p
    mem[0x0100 + ((sp + 6) & 0xFF)] = resume_pc & 0xFF
    mem[0x0100 + ((sp + 7) & 0xFF)] = resume_pc >> 8
    for index, value in enumerate(neighborhood):
        mem[(resume_pc - 2 + index) & 0xFFFF] = value
    pc = 0
    a = x = z = 0
    carry = 0
    steps = 0
    while pc < len(body):
        steps += 1
        require(steps < 100, "capture emulator did not reach terminal jump")
        op = body[pc]
        if op == 0xBA:             # TSX
            x = sp; pc += 1
        elif op == 0xBD:           # LDA abs,X
            address = body[pc + 1] | body[pc + 2] << 8
            a = mem.get((address + x) & 0xFFFF, 0); pc += 3
        elif op == 0xAD:           # LDA abs
            address = body[pc + 1] | body[pc + 2] << 8
            a = mem.get(address, 0); pc += 3
        elif op == 0x8D:           # STA abs
            address = body[pc + 1] | body[pc + 2] << 8
            mem[address] = a; pc += 3
        elif op == 0x38:           # SEC
            carry = 1; pc += 1
        elif op == 0xE9:           # SBC #imm
            total = a - body[pc + 1] - (1 - carry)
            carry = 1 if total >= 0 else 0
            a = total & 0xFF; pc += 2
        elif op == 0x85:           # STA zp
            mem[body[pc + 1]] = a; pc += 2
        elif op == 0xA3:           # LDZ #imm
            z = body[pc + 1]; pc += 2
        elif op == 0xB2:           # LDA (zp),Z
            zp = body[pc + 1]
            address = (mem.get(zp, 0) | mem.get((zp + 1) & 0xFF, 0) << 8)
            a = mem.get((address + z) & 0xFFFF, 0); pc += 2
        elif op == 0xA9:           # LDA #imm
            a = body[pc + 1]; pc += 2
        elif op == 0x78:           # SEI
            pc += 1
        elif op == 0x9C:           # STZ abs
            address = body[pc + 1] | body[pc + 2] << 8
            mem[address] = 0; pc += 3
        elif op == 0x4C:           # terminal JMP self
            address = body[pc + 1] | body[pc + 2] << 8
            require(address == CODE0 + pc, "terminal loop target drift")
            break
        else:
            raise ContactError(f"unexpected origin-body opcode ${op:02X} at {pc}")
    return bytes(mem.get(RECORD + index, 0) for index in range(RECORD_BYTES))


def parse_record(raw: bytes) -> dict[str, Any]:
    require(len(raw) == RECORD_BYTES, "origin record length drift")
    require(raw[FIELDS["complete"]] == COMPLETE_TAG,
            "origin row did not commit")
    pc = raw[FIELDS["stacked_PCL"]] | raw[FIELDS["stacked_PCH"]] << 8
    neighborhood = raw[FIELDS["resume_PC_minus_2"]:
                       FIELDS["resume_PC_plus_1"] + 1]
    stacked_p = raw[FIELDS["stacked_P"]]
    b_set = bool(stacked_p & 0x10)
    sources = {name: raw[FIELDS[name]] for _, name in IO_SOURCES}
    if b_set and neighborhood[0] == 0x00:
        decision = "BRK-CONTROL-FLOW-ESCAPE"
    elif not b_set and sources["CIA1_ICR"] & 0x80 \
            and sources["CIA1_ICR"] & 0x1F:
        decision = "HARDWARE-IRQ-CIA1"
    elif not b_set and any((
        sources["Ethernet_IRQ"] & 0xC0,
        sources["AutoIEC_IRQ"] & 0x80,
        sources["AudioDMA_IRQ"] & 0x80,
    )):
        decision = "HARDWARE-IRQ-INTERNAL-PERIPHERAL"
    elif not b_set:
        decision = "HARDWARE-IRQ-DEFERRED-OR-EXTERNAL-REMAINDER"
    else:
        decision = "INSTRUMENT-RED-INCONSISTENT-BRK"
    return {
        "status": decision,
        "stacked_P": f"0x{stacked_p:02X}",
        "stacked_B": int(b_set),
        "stacked_return_PC": f"0x{pc:04X}",
        "resume_neighborhood_PC_minus_2_through_plus_1": neighborhood.hex(),
        "sources": {name: f"0x{value:02X}" for name, value in sources.items()},
    }


def derive() -> dict[str, Any]:
    desk = DESK.derive()
    require(desk["required_capture_row"]["authorization"]
            == "not-authorized-by-this-desk-result",
            "desk boundary drift")
    sister = load(SISTER.RECEIPT)
    original = SISTER.DIAG_PRG.read_bytes()
    at = SISTER.prg_offset(CODE0)
    require(original[at:at + CAPTURE_BYTES]
            == SISTER.record_patch(load(SISTER.PHASE_B))["code0"][:CAPTURE_BYTES],
            "inherited terminal capture body drift")
    body = capture_body()
    test_io = {address: (index * 17 + 3) & 0xFF
               for index, (address, _) in enumerate(IO_SOURCES)}
    test_io[0xDC0D] = 0
    brk = parse_record(emulate(
        body, sp=0x80, stacked_p=0x34, resume_pc=0xBF73,
        neighborhood=bytes.fromhex("00ea1122"), io=test_io))
    irq_io = dict(test_io); irq_io[0xDC0D] = 0x81
    irq = parse_record(emulate(
        body, sp=0x80, stacked_p=0x24, resume_pc=0xBF73,
        neighborhood=bytes.fromhex("3b010203"), io=irq_io))
    require(brk["status"] == "BRK-CONTROL-FLOW-ESCAPE"
            and irq["status"] == "HARDWARE-IRQ-CIA1",
            "independent capture-body execution model failed")
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; ONE TERMINAL CONTACT AUTHORIZED",
        "authorities": {
            "owner_authorization": git_bind(AUTHORIZATION_COMMIT,
                                              AUTHORIZATION_PATH),
            "desk_attribution": bind(DESK.RECEIPT),
            "diagnostic_sister": bind(SISTER.RECEIPT),
            "diagnostic_PRG": bind(SISTER.DIAG_PRG),
            "diagnostic_medium": bind(SISTER.DIAG_D81),
            "library_medium": bind(SISTER.LIBRARY_D81),
            "runner": bind(RUNNER),
        },
        "identity": {
            "promotable": False,
            "product_candidate_bytes_changed": 0,
            "medium_bytes_changed": 0,
            "product_links": 0,
            "runtime_patch_address": "0x0000B3B0",
            "runtime_patch_bytes": CAPTURE_BYTES,
            "inherited_terminal_arena_bytes": CAPTURE_BYTES,
            "record_address": "0x0000C03F",
            "record_bytes": RECORD_BYTES,
        },
        "capture": {
            "body_sha256": digest(body),
            "body_bytes": len(body),
            "record_reset_sha256": digest(record_reset()),
            "record_fields": FIELDS,
            "CPU_side_reads": [f"0x{address:04X}" for address, _ in IO_SOURCES],
            "CIA_reads_once_only": True,
            "commit_last": True,
            "resume_after_capture": False,
            "postcondition_reads": 1,
            "emulator_cases": [brk["status"], irq["status"]],
        },
        "contact": {
            "contacts": 1,
            "physical_owner_keyboard_only": True,
            "forms": ["(require (quote defstruct))", "(defstruct point x y)"],
            "quiet_seconds": 180,
            "monitor_accesses_during_active_form": 0,
            "screen_polls_during_active_form": 0,
            "stops": 1,
            "CPU_left_stopped": True,
        },
        "claim_limit": (
            "One authorized non-promotable terminal origin row. No product or "
            "medium byte changes, product link, fix, second contact or resume "
            "after the once-only source reads."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"]
            == "HOST-GREEN; ONE TERMINAL CONTACT AUTHORIZED",
            "contact preparation identity drift")
    identity = value["identity"]
    require(identity["promotable"] is False
            and identity["product_candidate_bytes_changed"] == 0
            and identity["medium_bytes_changed"] == 0
            and identity["product_links"] == 0
            and identity["runtime_patch_bytes"] == CAPTURE_BYTES,
            "diagnostic identity boundary drift")
    capture = value["capture"]
    require(capture["CPU_side_reads"]
            == [f"0x{address:04X}" for address, _ in IO_SOURCES]
            and capture["CIA_reads_once_only"] is True
            and capture["commit_last"] is True
            and capture["resume_after_capture"] is False
            and capture["postcondition_reads"] == 1,
            "authorized row semantics drift")
    contact = value["contact"]
    require(contact["contacts"] == 1 and contact["stops"] == 1
            and contact["physical_owner_keyboard_only"] is True
            and contact["monitor_accesses_during_active_form"] == 0
            and contact["screen_polls_during_active_form"] == 0
            and contact["CPU_left_stopped"] is True,
            "contact boundary drift")


def runner_contract() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    require(source.count("ftp_bundle_under_basic") == 2,
            "runner must define and invoke one preboot FTP lifetime")
    product_live = source.split("# PRODUCT-LIVE-BEGIN", 1)[1]
    require("mega65_ftp" not in product_live and '"$FTP"' not in product_live
            and "ftp_bundle_under_basic" not in product_live,
            "post-boot FTP crossing in origin runner")
    active = source.split("# ACTIVE-DEFSTRUCT-BEGIN", 1)[1].split(
        "# ACTIVE-DEFSTRUCT-END", 1)[0]
    require("sleep \"$quiet\"" in active and "run_m65" not in active
            and "screen " not in active and "readback " not in active,
            "measured form is externally observed")
    require(source.count("stop_once") == 2
            and 'readback 0x0000c03f 65 "$OUT/origin-record.bin"' in source
            and 'run_m65 -r' in source,
            "single-stop/readback choreography drift")


def materialize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CAPTURE_BODY.write_bytes(capture_body())
    RECORD_RESET.write_bytes(record_reset())


def audit() -> None:
    value = load(PREPARATION)
    validate(value)
    expected = derive()
    expected["authorities"]["runner"] = historical_file_bind(
        PREPARATION_COMMIT, RUNNER.relative_to(ROOT).as_posix())
    require(value == expected,
            "preparation receipt differs from committed contact authority")
    require(CAPTURE_BODY.read_bytes() == capture_body()
            and RECORD_RESET.read_bytes() == record_reset(),
            "runtime capture artifacts drift")
    runner_contract()


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[Any], Any]] = [
        ("promotable", ["identity", "promotable"], True),
        ("product-byte", ["identity", "product_candidate_bytes_changed"], 1),
        ("medium-byte", ["identity", "medium_bytes_changed"], 1),
        ("product-link", ["identity", "product_links"], 1),
        ("drop-CIA1", ["capture", "CPU_side_reads", 0], "0xD019"),
        ("drop-CIA2", ["capture", "CPU_side_reads", 1], "0xD019"),
        ("repeat-CIA", ["capture", "CIA_reads_once_only"], False),
        ("commit-first", ["capture", "commit_last"], False),
        ("resume-after-read", ["capture", "resume_after_capture"], True),
        ("two-readbacks", ["capture", "postcondition_reads"], 2),
        ("two-contacts", ["contact", "contacts"], 2),
        ("virtual-input", ["contact", "physical_owner_keyboard_only"], False),
        ("active-monitor", ["contact", "monitor_accesses_during_active_form"], 1),
        ("active-screen", ["contact", "screen_polls_during_active_form"], 1),
        ("two-stops", ["contact", "stops"], 2),
        ("resume-final", ["contact", "CPU_left_stopped"], False),
    ]
    rejected: list[str] = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        cursor: Any = trial
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = replacement
        try:
            validate(trial)
            require(trial == derive(), "mutated preparation accepted")
        except ContactError:
            rejected.append(name)
        else:
            raise ContactError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected, "capture_bytes": len(capture_body())}


def device_result(record_path: Path, registers_path: Path) -> dict[str, Any]:
    prep = load(PREPARATION)
    audit()
    registers = load(registers_path)
    raw_record = record_path.read_bytes()
    result = parse_record(raw_record)
    require(registers["MAPH"].lower() == "0x8000"
            and registers["MAPL"].lower() == "0x0000",
            "stopped mapping tuple drift")
    return {
        "format": DEVICE_FORMAT,
        "recorded_on": RECORDED_ON,
        "status": result["status"],
        "authorities": {
            "preparation": bind(PREPARATION),
            "record": bind(record_path),
            "registers": bind(registers_path),
        },
        "mapping": {"MAPH": registers["MAPH"], "MAPL": registers["MAPL"]},
        "register_tuple": registers,
        "raw_record_hex": raw_record.hex(),
        "terminal_row": result,
        "CPU_left_stopped": True,
        "claim_limit": (
            "One terminal origin row only. It distinguishes BRK from hardware "
            "IRQ and records readable internal sources; it does not identify the "
            "earlier control-flow corruptor, authorize a fix or authorize another "
            "contact."),
        "preparation_status": prep["status"],
    }


def validate_device(value: dict[str, Any]) -> None:
    require(value["format"] == DEVICE_FORMAT
            and value["status"] == "BRK-CONTROL-FLOW-ESCAPE",
            "device result identity/classification drift")
    require(value["CPU_left_stopped"] is True
            and value["mapping"] == {"MAPH": "0x8000", "MAPL": "0x0000"},
            "device stop/mapping boundary drift")
    raw = bytes.fromhex(value["raw_record_hex"])
    reconstructed = parse_record(raw)
    require(value["terminal_row"] == reconstructed,
            "terminal row differs from embedded raw record")
    require(reconstructed["stacked_P"] == "0x30"
            and reconstructed["stacked_B"] == 1
            and reconstructed["stacked_return_PC"] == "0xBF73"
            and reconstructed["resume_neighborhood_PC_minus_2_through_plus_1"]
            == "00000000",
            "BRK discriminator facts drift")
    require(reconstructed["sources"]["CIA1_ICR"] == "0x02"
            and int(reconstructed["sources"]["CIA1_ICR"], 16) & 0x80 == 0,
            "CIA1 context was promoted to asserted hardware IRQ")
    require("does not identify the earlier control-flow corruptor"
            in value["claim_limit"]
            and "authorize a fix" in value["claim_limit"],
            "device claim limit broadened")


def audit_device() -> None:
    value = load(DEVICE)
    validate_device(value)


def device_selftest() -> dict[str, Any]:
    base = load(DEVICE)
    validate_device(base)
    cases: list[tuple[str, list[Any], Any]] = [
        ("call-it-hardware-IRQ", ["status"], "HARDWARE-IRQ-CIA1"),
        ("clear-stacked-B", ["terminal_row", "stacked_B"], 0),
        ("rewrite-stacked-P", ["terminal_row", "stacked_P"], "0x20"),
        ("rewrite-return-PC", ["terminal_row", "stacked_return_PC"], "0xBF71"),
        ("invent-live-opcode", ["terminal_row",
                                 "resume_neighborhood_PC_minus_2_through_plus_1"],
         "ea000000"),
        ("rewrite-raw-record", ["raw_record_hex"], "00" * RECORD_BYTES),
        ("claim-CIA-asserted", ["terminal_row", "sources", "CIA1_ICR"], "0x82"),
        ("wrong-MAP", ["mapping", "MAPH"], "0x0000"),
        ("resume", ["CPU_left_stopped"], False),
        ("erase-claim-limit", ["claim_limit"], "origin and fix proven"),
    ]
    rejected: list[str] = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        cursor: Any = trial
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = replacement
        try:
            validate_device(trial)
        except ContactError:
            rejected.append(name)
        else:
            raise ContactError(f"device mutation survived: {name}")
    require(len(rejected) == len(cases), "device mutation accounting drift")
    return {"status": "DEVICE SELFTEST PASS",
            "mutations_rejected": len(rejected), "cases": rejected,
            "mechanism_class": base["status"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "derive", "record", "check", "selftest", "classify", "record-device"))
    parser.add_argument("--record-file", type=Path)
    parser.add_argument("--registers", type=Path)
    args = parser.parse_args()
    if args.action == "derive":
        value = derive()
    elif args.action == "record":
        materialize()
        value = derive()
        write(PREPARATION, value)
    elif args.action == "check":
        audit()
        if DEVICE.is_file():
            audit_device()
            result = device_selftest()
            value = {"status": "PASS", "capture_bytes": CAPTURE_BYTES,
                     "preparation_mutations": 16,
                     "device_mutations": result["mutations_rejected"],
                     "mechanism_class": result["mechanism_class"]}
        else:
            value = {"status": "PASS", "capture_bytes": CAPTURE_BYTES,
                     "mutations_rejected": 16}
    elif args.action == "selftest":
        value = selftest()
    else:
        require(args.record_file is not None and args.registers is not None,
                "device result needs --record-file and --registers")
        value = device_result(args.record_file.resolve(), args.registers.resolve())
        if args.action == "record-device":
            write(DEVICE, value)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContactError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT IRQ ORIGIN CONTACT: {error}", file=sys.stderr)
        raise SystemExit(1)
