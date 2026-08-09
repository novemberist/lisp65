#!/usr/bin/env python3
"""Close the v1.6 VM-progress two-sample non-interference prerequisite.

The first progress identity exposed a live counter through an 8-bit seqlock.
Reading it twice with the monitor would stop the machine between observations,
so this diagnostic-only successor moves the observations into the target's
already-owned raster IRQ.  Four commit-last slots retain consecutive samples;
the host enters the monitor only once, after the target has made the samples.
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


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-vm-progress/deployment.json"
BASE_RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-preparation-receipt.json")
COST_RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-vm-cost-closure-receipt.json"
LAUNCH_FIRST_RED = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-autonomous-launch-first-red.json")
LINE_VERIFY_FIRST_RED = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-line-verify-first-red.json")
PHYSICAL_LAUNCH_FIRST_RED = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-physical-launch-first-red.json")
FINAL_CONTACT_FIRST_RED = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-final-contact-first-red.json")
GUARD_RECEIPT = EVIDENCE / (
    "c2.2-product-link73-vm-codebuf-owner-structural-receipt.json")
KERNAL_SOURCE = ROOT / "src/c2_kernal_window.s"
RUNNER = ROOT / "scripts/c2-v16-defstruct-vm-progress-hw.sh"
PLAN_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OWNER_COMMIT = "32e9ccbee15c75f0a27c773b5bffda4fa6662939"
AUTHORIZATION_COMMIT = "c5963c68ace734e5dcdec543e4c2302eef70bd84"
DRIVER = Path(__file__).resolve()
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

OUT = ROOT / "build/c2.3/v1.6-defstruct-vm-progress-noninterference"
ART = OUT / "artifacts"
PRG = ART / "diagnostic-vm-progress-noninterference.prg"
ELF = ART / "diagnostic-vm-progress-noninterference.elf"
WINDOW = ART / "diagnostic-vm-progress-noninterference-window.bin"
HELPER_BIN = ART / "vm-progress-atomic-helper.bin"
LOW_STATE_BIN = ART / "vm-progress-atomic-state-reset.bin"
LOW_PRELOAD_BIN = ART / "vm-progress-atomic-lowram-preload.bin"
SLOT_RESET_BIN = ART / "vm-progress-slot-reset.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-vm-progress-noninterference-receipt.json")

FORMAT = "lisp65-c2.3-v1.6-vm-progress-noninterference-v1"
RECORDED_ON = "2026-08-06"
PRG_LOAD = 0x2001
WINDOW_BASE = 0xE000
WINDOW_BYTES = 8192
HOOK = 0x467D
ABORT_CALL = 0x2DDE
IRQ_SAMPLE_CALL = 0xE053
SAMPLER = 0xFEE1
SAMPLER_LIMIT = 0xFF67
SLOTS = 0xFF40
SLOT_BYTES = 8
SLOT_COUNT = 4
SLOTS_BYTES = SLOT_BYTES * SLOT_COUNT
SLOTS_PHYSICAL = 0x087FFF40
FRAME_LO = 0xFF83
FRAME_HI = 0xFF84
SOURCELESS = 0xFF86
BREAK_SAMPLE = 0xD613
HELPER = 0x1FCE
HELPER_BYTES = 42
LOW_STATE = 0x1FF8
LOW_STATE_BYTES = 8
COUNTER = LOW_STATE
OWNER = LOW_STATE + 4
ARM = LOW_STATE + 6
POLL = 0xBFEA
OWNER_OFF = 0xB9B2
CRC_HIGH = 0xB4F4
CRC_LOW = 0xB4FA
SAMPLE_HIGH_STRIDE = 8
SAMPLE_FRAMES = SAMPLE_HIGH_STRIDE * 256
FRAME_HZ_MILLI = 51966
QUIET_FLOOR_SECONDS = 120
COMMIT = 0xA5
LOW_STATE_RESET = bytes((0, 0, 0, 0, 0xD2, 0xD3, 0xA5, 0xD4))
SLOT_RESET = bytes((0xD0, 0xD1, 0xD2, 0xD3,
                    0xD4, 0xD5, 0xD6, 0x00)) * SLOT_COUNT


class ProofError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProofError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"commit": full, "path": path, "bytes": len(raw),
            "sha256": digest(raw)}


def run(argv: list[str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def replace(raw: bytearray, at: int, before: bytes, after: bytes,
            label: str) -> None:
    require(len(before) == len(after), f"fixed-size patch required: {label}")
    require(raw[at:at + len(before)] == before, f"patch authority drift: {label}")
    raw[at:at + len(after)] = after


class Asm:
    def __init__(self, origin: int):
        self.origin = origin
        self.raw = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.raw)

    def emit(self, *values: int) -> None:
        self.raw.extend(values)

    def abs(self, opcode: int, address: int) -> None:
        self.emit(opcode, address & 0xFF, address >> 8)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.pc

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.raw) - 1, label))

    def finish(self) -> bytes:
        for offset, label in self.fixups:
            require(label in self.labels, f"missing label: {label}")
            source_after = self.origin + offset + 1
            delta = self.labels[label] - source_after
            require(-128 <= delta <= 127, f"branch out of range: {label}")
            self.raw[offset] = delta & 0xFF
        return bytes(self.raw)


def helper_bytes() -> bytes:
    """Atomic producer: the raster IRQ can see only old or new state."""
    a = Asm(HELPER)
    a.emit(0x08, 0x78, 0x48)             # PHP; SEI; PHA
    a.abs(0xAD, OWNER_OFF); a.abs(0x8D, OWNER)
    a.abs(0xAD, OWNER_OFF + 1); a.abs(0x8D, OWNER + 1)
    a.abs(0xEE, COUNTER); a.branch(0xD0, "done")
    a.abs(0xEE, COUNTER + 1); a.branch(0xD0, "done")
    a.abs(0xEE, COUNTER + 2); a.branch(0xD0, "done")
    a.abs(0xEE, COUNTER + 3)
    a.label("done")
    a.emit(0x68, 0x28)                   # PLA; PLP
    a.abs(0xAE, POLL)                    # displaced LDX, owns final N/Z
    a.emit(0x60)
    code = a.finish()
    require(len(code) == 39, f"atomic helper size drift: {len(code)}")
    return code + b"\xea" * (HELPER_BYTES - len(code))


def sampler_bytes() -> bytes:
    """Self-snapshot every 2048 owned raster frames into a four-slot ring."""
    a = Asm(SAMPLER)
    a.abs(0xAD, ARM); a.emit(0xC9, COMMIT); a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_LO); a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_HI); a.emit(0x29, SAMPLE_HIGH_STRIDE - 1)
    a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_HI); a.emit(0x29, (SLOT_COUNT - 1) * SLOT_BYTES)
    a.emit(0xAA)                          # X = slot offset 0/8/16/24
    a.abs(0x9E, SLOTS + 7)                # invalidate before payload
    for index in range(4):
        a.abs(0xAD, COUNTER + index); a.abs(0x9D, SLOTS + index)
    for index in range(2):
        a.abs(0xAD, OWNER + index); a.abs(0x9D, SLOTS + 4 + index)
    a.abs(0xAD, FRAME_HI); a.abs(0x9D, SLOTS + 6)
    a.emit(0xA9, COMMIT); a.abs(0x9D, SLOTS + 7)  # commit last
    a.label("done")
    a.abs(0xAD, BREAK_SAMPLE)             # displaced IRQ load
    a.emit(0x60)
    code = a.finish()
    require(len(code) <= SLOTS - SAMPLER,
            f"sampler overlaps slots: {len(code)} bytes")
    image = code + b"\xea" * (SLOTS - SAMPLER - len(code)) + SLOT_RESET
    image += b"\xea" * (SAMPLER_LIMIT - SAMPLER - len(image))
    require(len(image) == SAMPLER_LIMIT - SAMPLER,
            "sampler image geometry drift")
    return image


def patch_elf(base: Path, updates: dict[str, bytes]) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    argv = [str(OBJCOPY)]
    for index, (section, raw) in enumerate(updates.items()):
        path = ART / f"elf-section-{index}.bin"
        path.write_bytes(raw)
        argv.append(f"--update-section={section}={path}")
    argv.extend([
        f"--add-symbol=lisp65_v16_vm_progress_sampler=0x{SAMPLER:x},global,function",
        f"--add-symbol=lisp65_v16_vm_progress_slots=0x{SLOTS:x},global,object",
        str(base), str(ELF)])
    run(argv, "derive non-interfering progress ELF")


def executable_edges(truth: ElfTruth, target: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        raw = truth.section_bytes(section.name)
        for index in range(len(raw) - 2):
            if raw[index] in (0x20, 0x4C) \
                    and int.from_bytes(raw[index + 1:index + 3], "little") == target:
                rows.append({"section": section.name,
                             "pc": f"0x{section.address + index:04x}",
                             "opcode": "JSR" if raw[index] == 0x20 else "JMP"})
    return rows


def guard_source_contract(source: str) -> dict[str, Any]:
    owned = source.split("c2_kernal_irq_handler:", 1)[1].split(
        ".Lsource_less:", 1)[0]
    sourceless = source.split(".Lsource_less:", 1)[1].split(
        ".section .lisp65_c2_kernal_window.nmi", 1)[0]
    require("lda $d019" in owned and "and #$01" in owned
            and "beq .Lsource_less" in owned and "sta $d019" in owned
            and "stz C2K_SOURCELESS_IRQS" in owned
            and "inc C2K_FRAME_LO" in owned,
            "owned raster guard entry contract drift")
    require("lda C2K_SOURCELESS_IRQS" in sourceless
            and "jmp c2_kernal_fail_closed" in sourceless
            and "inc C2K_SOURCELESS_IRQS" in sourceless,
            "source-less fail-closed contract drift")
    return {
        "owned_entry_order": ["D019&1", "ack D019", "clear source-less latch",
                              "increment FF83/FF84", "call sampler"],
        "source_less_branch_precedes_sampler": True,
        "second_source_less_target": "c2_kernal_fail_closed",
    }


def runner_contract(source: str) -> dict[str, Any]:
    require("dry-run|stage|capture" in source
            and "verify-boot|arm" not in source,
            "progress runner action surface drift")
    require("v1.6 is finally parked; hardware contact forbidden" in source
            and ".vm_progress.recontact_authorized" in source,
            "final-park execution lock drift")
    require("screen_name=$1" in source
            and "input_name=$1 input_form=$2" in source
            and 'screen "${input_name}-input"' in source
            and '"$OUT/${input_name}-input.txt"' in source,
            "line-verifier helper scope isolation drift")
    stage = source.split('if [ "$ACTION" = stage ]; then', 1)[1].split(
        'if [ "$ACTION" = capture ]; then', 1)[0]
    capture = source.split('if [ "$ACTION" = capture ]; then', 1)[1]
    require("type RUN, (require 'defstruct), and (defstruct point x y) physically" in stage
            and "type_verified" not in stage
            and "run_m65 -t" not in stage
            and "run_m65 -T" not in stage
            and stage.count("run_m65 -H -@") >= 2
            and "run_m65 -r" in stage
            and "physically" in stage,
            "physical-owner input choreography drift")
    post_resume = stage.rsplit("run_m65 -r", 1)[1]
    require(not any(token in post_resume for token in (
                "run_m65", "screen ", "readback", "monitor_sync", "stop_once")),
            "prelaunch monitor/target access after staging resume")
    before_stop = capture.split("# FIRST-AND-ONLY-POST-FORM-MONITOR-ENTRY", 1)[0]
    after_stop = capture.split("# FIRST-AND-ONLY-POST-FORM-MONITOR-ENTRY", 1)[1]
    forbidden = ("run_m65", "stop_once", "screen ", "monitor_sync", "-t1",
                 "--memsave")
    require(f"sleep {QUIET_FLOOR_SECONDS}" in before_stop
            and not any(token in before_stop for token in forbidden),
            "monitor/CPU stop leaked into active sample interval")
    require(after_stop.count("\n  stop_once\n") == 1,
            "final stop transition is not singular")
    require("run_m65 -H" not in after_stop,
            "second halt transition leaked into post-sample reads")
    stop_body = source.split("stop_once() {", 1)[1].split("ftp_medium() {", 1)[0]
    require(stop_body.count('serial.slow_write(fd, b"t1\\r")') == 1
            and 'b"t0\\r"' not in stop_body
            and "view.command(fd, b\"r\"" in stop_body
            and "os.close(fd)" in stop_body,
            "one-stop same-session read contract drift")
    return {
        "quiet_floor_seconds": QUIET_FLOOR_SECONDS,
        "external_calls_during_active_sample_interval": 0,
        "monitor_entries_during_active_sample_interval": 0,
        "CPU_stop_transitions_after_samples": 1,
        "sample_producer": "owned raster IRQ on target",
        "prelaunch_monitor_accesses_after_resume": 0,
        "intermediate_automated_device_actions": 0,
        "owner_keyboard_inputs": 3,
        "physical_inputs": [
            "RUN", "(require (quote defstruct))", "(defstruct point x y)"],
    }


def executable_mutations(window: bytes, runner: str) -> dict[str, str]:
    """Exercise the three commissioned failure classes against real inputs."""
    rejected: dict[str, str] = {}

    # A first sample implemented with t1 would manufacture the state observed
    # by the second sample.  The source-order checker must reject that runner.
    stopped = runner.replace(
        f"  sleep {QUIET_FLOOR_SECONDS}\n",
        f"  stop_once\n  sleep {QUIET_FLOOR_SECONDS}\n", 1)
    try:
        runner_contract(stopped)
    except ProofError as error:
        rejected["CPU-stop-mid-persistent-operation"] = str(error)
    else:
        raise ProofError("mid-operation CPU-stop runner mutation survived")

    # The spent contact submitted RUN and RETURN together without proving the
    # active line.  That launch shape must not satisfy the runner again.
    unverified = runner.replace(
        '  echo "VM-PROGRESS STAGE READY:',
        '  run_m65 -T RUN\n  echo "VM-PROGRESS STAGE READY:', 1)
    try:
        runner_contract(unverified)
    except ProofError as error:
        rejected["unverified-combined-launch-submit"] = str(error)
    else:
        raise ProofError("unverified autonomous launch mutation survived")

    # POSIX shell function assignments share global scope.  Reusing the
    # caller's input_name in screen() must not be allowed to redirect the
    # verifier to a capture path that was never produced.
    scope_clobber = runner.replace("screen_name=$1", "input_name=$1", 1)
    try:
        runner_contract(scope_clobber)
    except ProofError as error:
        rejected["screen-helper-clobbers-line-id"] = str(error)
    else:
        raise ProofError("line-verifier helper-scope mutation survived")

    # The successful physical-run precedent has no target access between the
    # staging resume and owner RUN.  Restore the accidental screenshot from
    # the consumed contact and require the choreography gate to reject it.
    prelaunch = runner.replace(
        "  run_m65 -r\n  echo \"VM-PROGRESS STAGE READY:",
        "  run_m65 -r\n  screen post-staging-ready\n"
        "  echo \"VM-PROGRESS STAGE READY:", 1)
    try:
        runner_contract(prelaunch)
    except ProofError as error:
        rejected["prelaunch-monitor-after-resume"] = str(error)
    else:
        raise ProofError("prelaunch-monitor runner mutation survived")

    # The retired one-byte seqlock really does ABA after 128 ordinary commits.
    # This proves why equal/even cannot remain a reader authority.  The new
    # reader has no sequence input and rejects a slot whose commit was cleared
    # before a torn payload write.
    sequence_before = 0x20
    sequence_after = (sequence_before + 2 * 128) & 0xFF
    legacy_accepts = sequence_before == sequence_after and not (sequence_after & 1)
    raw = bytearray(SLOT_RESET)
    raw[:SLOT_BYTES] = (b"\x11\x22\x33\x44\x55\x66\x00" + bytes((COMMIT,)))
    raw[SLOT_BYTES:2 * SLOT_BYTES] = (
        b"\xaa\xbb\xcc\xdd\xee\xff\x08\x00")  # torn/invalid newest
    try:
        accepted_slots(bytes(raw), 0x09)
    except ProofError as error:
        require(legacy_accepts, "legacy ABA counterexample no longer closes")
        rejected["accept-torn-or-8bit-ABA-window"] = str(error)
    else:
        raise ProofError("torn/ABA reader mutation survived")

    # Introduce a second direct sampler edge at the source-less entry.  The
    # linked-image route closure must see it in addition to the owned edge.
    mutated = bytearray(window)
    at = 0xE06D - WINDOW_BASE
    mutated[at:at + 3] = b"\x20" + u16(SAMPLER)
    edges = []
    for index in range(len(mutated) - 2):
        if mutated[index] in (0x20, 0x4C) \
                and int.from_bytes(mutated[index + 1:index + 3], "little") == SAMPLER:
            edges.append(WINDOW_BASE + index)
    if edges != [IRQ_SAMPLE_CALL]:
        rejected["sampler-reachable-from-source-less-guard"] = (
            f"sampler inbound edge set mutated to {[hex(value) for value in edges]}")
    else:
        raise ProofError("source-less sampler-edge mutation survived")

    require(set(rejected) == {
        "CPU-stop-mid-persistent-operation",
        "unverified-combined-launch-submit",
        "screen-helper-clobbers-line-id",
        "prelaunch-monitor-after-resume",
        "accept-torn-or-8bit-ABA-window",
        "sampler-reachable-from-source-less-guard",
    }, "commissioned executable mutation closure drift")
    return rejected


def helper_model(raw: bytes, before: int, owner: int) -> dict[str, Any]:
    """Independent tiny execution model, including interrupt-enable state."""
    memory = bytearray(65536)
    memory[HELPER:HELPER + len(raw)] = raw
    memory[COUNTER:COUNTER + 4] = before.to_bytes(4, "little")
    memory[OWNER:OWNER + 2] = b"\xd2\xd3"
    memory[ARM] = COMMIT
    memory[OWNER_OFF:OWNER_OFF + 2] = owner.to_bytes(2, "little")
    memory[POLL] = 0x6C
    pc = HELPER; a = 0x5A; x = 0; sp = 0xFD
    p = 0x20  # IRQ enabled, ordinary caller flags
    boundaries: list[dict[str, Any]] = []
    for _ in range(80):
        boundaries.append({"pc": pc, "I": bool(p & 0x04),
                           "counter": int.from_bytes(memory[COUNTER:COUNTER + 4], "little"),
                           "owner": int.from_bytes(memory[OWNER:OWNER + 2], "little")})
        op = memory[pc]; pc += 1
        if op in (0xAD, 0x8D, 0xAE, 0xEE):
            address = memory[pc] | memory[pc + 1] << 8; pc += 2
            if op == 0xAD:
                a = memory[address]
                p = (p | 0x02) if a == 0 else (p & ~0x02)
            elif op == 0x8D:
                memory[address] = a
            elif op == 0xAE:
                x = memory[address]
                p = (p | 0x02) if x == 0 else (p & ~0x02)
            else:
                memory[address] = (memory[address] + 1) & 0xFF
                p = (p | 0x02) if memory[address] == 0 else (p & ~0x02)
        elif op == 0xD0:
            delta = memory[pc]; pc += 1
            if not (p & 0x02):
                pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif op == 0x08:  # PHP
            memory[0x100 + sp] = p; sp = (sp - 1) & 0xFF
        elif op == 0x78:
            p |= 0x04
        elif op == 0x48:
            memory[0x100 + sp] = a; sp = (sp - 1) & 0xFF
        elif op == 0x68:
            sp = (sp + 1) & 0xFF; a = memory[0x100 + sp]
        elif op == 0x28:
            sp = (sp + 1) & 0xFF; p = memory[0x100 + sp]
        elif op == 0xEA:
            pass
        elif op == 0x60:
            break
        else:
            raise ProofError(f"unmodeled helper opcode 0x{op:02x}")
    else:
        raise ProofError("atomic helper did not return")
    new = (before + 1) & 0xFFFFFFFF
    interruptible = {(row["counter"], row["owner"])
                     for row in boundaries if not row["I"]}
    require(interruptible <= {(before, 0xD3D2), (new, owner)},
            f"IRQ can observe torn producer state: {interruptible}")
    return {"before": before, "after": new, "owner": owner,
            "A_after": a, "X_after": x, "stack_after": sp,
            "interruptible_states": [
                {"counter": counter, "owner": seen_owner}
                for counter, seen_owner in sorted(interruptible)],
            "torn_interruptible_states": 0}


def helper_vectors(raw: bytes) -> list[dict[str, Any]]:
    rows = [helper_model(raw, value, 0x02D5)
            for value in (0, 1, 0xFE, 0xFF, 0xFFFF, 0xFFFFFF, 0xFFFFFFFF)]
    require(all(row["A_after"] == 0x5A and row["X_after"] == 0x6C
                and row["stack_after"] == 0xFD
                and row["torn_interruptible_states"] == 0 for row in rows),
            "atomic helper execution contract drift")
    return rows


def accepted_slots(raw: bytes, final_frame_hi: int) -> list[dict[str, int]]:
    require(len(raw) == SLOTS_BYTES, "slot reader width drift")
    rows: list[dict[str, int]] = []
    for offset in range(0, len(raw), SLOT_BYTES):
        slot = raw[offset:offset + SLOT_BYTES]
        if slot[7] != COMMIT:
            continue
        frame = slot[6]
        require(frame & (SAMPLE_HIGH_STRIDE - 1) == 0,
                "committed slot has non-sample frame")
        rows.append({
            "offset": offset,
            "counter": int.from_bytes(slot[:4], "little"),
            "owner": int.from_bytes(slot[4:6], "little"),
            "frame_hi": frame,
            "age_high_bytes": (final_frame_hi - frame) & 0xFF,
        })
    rows.sort(key=lambda row: row["age_high_bytes"])
    require(len(rows) >= 2, "fewer than two committed self-snapshots")
    require(rows[1]["age_high_bytes"] - rows[0]["age_high_bytes"]
            == SAMPLE_HIGH_STRIDE,
            "reader accepted non-consecutive/ABA-aged slots")
    return rows[:2]


def reader_vectors() -> list[dict[str, Any]]:
    def slot(counter: int, owner: int, frame: int, valid: int = COMMIT) -> bytes:
        return (counter.to_bytes(4, "little") + owner.to_bytes(2, "little")
                + bytes((frame, valid)))
    raw = (slot(0xFFFFFFF0, 0x101, 0xF0)
           + slot(0x00000020, 0x102, 0xF8)
           + slot(0x00001020, 0x103, 0x00)
           + slot(0x00001021, 0x104, 0x08))
    newest = accepted_slots(raw, 0x0A)
    require([row["frame_hi"] for row in newest] == [0x08, 0x00]
            and ((newest[0]["counter"] - newest[1]["counter"]) & 0xFFFFFFFF) == 1,
            "frame-wrap/latest-pair reader drift")
    torn = bytearray(raw); torn[3 * SLOT_BYTES + 7] = 0
    fallback = accepted_slots(bytes(torn), 0x0A)
    require([row["frame_hi"] for row in fallback] == [0x00, 0xF8],
            "commit-last torn-write fallback drift")
    return [{"name": "frame-wrap-latest-pair", "accepted": newest},
            {"name": "torn-newest-falls-back-to-two-complete", "accepted": fallback}]


def build() -> dict[str, Any]:
    base = load(BASE_DEPLOY); prior = load(BASE_RECEIPT); cost = load(COST_RECEIPT)
    launch_first_red = load(LAUNCH_FIRST_RED)
    line_verify_first_red = load(LINE_VERIFY_FIRST_RED)
    physical_launch_first_red = load(PHYSICAL_LAUNCH_FIRST_RED)
    final_contact_first_red = load(FINAL_CONTACT_FIRST_RED)
    guard = load(GUARD_RECEIPT)
    require(base["status"] == "HOST-GREEN-NON-PROMOTABLE-VM-PROGRESS-ARMED"
            and base["promotable"] is False,
            "base progress deployment drift")
    require(prior["status"] ==
            "HOST-GREEN; PROGRESS-WITNESS-ARMED; CONTACT-NOT-AUTHORIZED"
            and prior["witness"]["sample_transport_contract"]["status"]
            == "NOT-YET-BOUND", "prior contact boundary drift")
    require(cost["decision"]["completed_price_floor_seconds"] == 788
            and cost["decision"]["observed_beyond_completed_price_floor_seconds"] == 207,
            "completed price premise drift")
    require(launch_first_red["status"].endswith("RECONTACT-NOT-AUTHORIZED")
            and launch_first_red["accounting"]["measured_forms_started"] == 0,
            "autonomous launch First Red boundary drift")
    require(line_verify_first_red["status"].endswith("RECONTACT-NOT-AUTHORIZED")
            and line_verify_first_red["accounting"]["RETURN_submitted"] is False
            and line_verify_first_red["accounting"]["measured_forms_started"] == 0,
            "line-verifier First Red boundary drift")
    require(physical_launch_first_red["status"].endswith(
                "RECONTACT-NOT-AUTHORIZED")
            and physical_launch_first_red["contact"]
                ["prelaunch_monitor_accesses_after_resume"] == 1
            and physical_launch_first_red["accounting"]
                ["measured_forms_started"] == 0,
            "physical-launch First Red boundary drift")
    require(final_contact_first_red["status"].endswith(
                "1.6-FINAL-PARK; RECONTACT-FORBIDDEN")
            and final_contact_first_red["contact"]
                ["automated_device_actions_after_final_resume"] == 0
            and final_contact_first_red["accounting"]
                ["measured_forms_started"] == 0
            and final_contact_first_red["hard_edge"]["further_contacts"] == 0,
            "final-contact hard-edge boundary drift")
    irq_guard = guard["fix_gates"]["IRQ_episode"]
    require(irq_guard["source"]["second_consecutive_source_less_fail_closed"] is True
            and irq_guard["semantics"]["double_sourceless_fixture"]["outcomes"]
            == ["continue", "fail-closed"],
            "source-less guard receipt drift")
    source_contract = guard_source_contract(KERNAL_SOURCE.read_text(encoding="utf-8"))
    choreography = runner_contract(RUNNER.read_text(encoding="utf-8"))

    base_prg_path = ROOT / base["diagnostic"]["prg"]["path"]
    base_elf_path = ROOT / base["diagnostic"]["elf"]["path"]
    base_window_path = ROOT / base["diagnostic"]["window"]["path"]
    require(bind(base_prg_path) == base["diagnostic"]["prg"]
            and bind(base_elf_path) == base["diagnostic"]["elf"]
            and bind(base_window_path) == base["diagnostic"]["window"],
            "base progress artifact binding drift")
    base_prg = base_prg_path.read_bytes(); base_window = base_window_path.read_bytes()
    require(len(base_window) == WINDOW_BYTES and crc16(base_window) == 0xD5CB,
            "base progress window/CRC drift")

    helper = helper_bytes(); sampler = sampler_bytes()
    ART.mkdir(parents=True, exist_ok=True)
    HELPER_BIN.write_bytes(helper); LOW_STATE_BIN.write_bytes(LOW_STATE_RESET)
    LOW_PRELOAD_BIN.write_bytes(helper + LOW_STATE_RESET)
    SLOT_RESET_BIN.write_bytes(SLOT_RESET)

    window = bytearray(base_window)
    replace(window, IRQ_SAMPLE_CALL - WINDOW_BASE, b"\xad\x13\xd6",
            b"\x20" + u16(SAMPLER), "owned IRQ sampler call")
    abort_start = SAMPLER - WINDOW_BASE
    replace(window, abort_start, bytes(window[abort_start:abort_start + len(sampler)]),
            sampler, "diagnostic sampler replaces abort driver")
    new_crc = crc16(bytes(window)); WINDOW.write_bytes(window)

    prg = bytearray(base_prg)
    replace(prg, prg_offset(ABORT_CALL), b"\x20\xe1\xfe", b"\xea\xea\xea",
            "retire diagnostic abort edge to sampler")
    replace(prg, prg_offset(CRC_HIGH), bytes((0xD5,)), bytes((new_crc >> 8,)),
            "sampler window CRC high")
    replace(prg, prg_offset(CRC_LOW), bytes((0xCB,)), bytes((new_crc & 0xFF,)),
            "sampler window CRC low")
    PRG.write_bytes(prg)

    truth = ElfTruth.read(base_elf_path, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = bytearray(truth.section_bytes(".text"))
    text_base = truth.section(".text").address
    replace(text, ABORT_CALL - text_base, b"\x20\xe1\xfe", b"\xea\xea\xea",
            "ELF retire abort edge")
    irq_name = ".lisp65_c2_kernal_window.irq_handler"
    irq = bytearray(truth.section_bytes(irq_name)); irq_base = truth.section(irq_name).address
    replace(irq, IRQ_SAMPLE_CALL - irq_base, b"\xad\x13\xd6",
            b"\x20" + u16(SAMPLER), "ELF owned IRQ sampler call")
    reopen_name = ".lisp65_c2_kernal_window.reopen_gap1"
    reopen = bytearray(truth.section_bytes(reopen_name))
    reopen_base = truth.section(reopen_name).address
    replace(reopen, SAMPLER - reopen_base,
            bytes(reopen[SAMPLER - reopen_base:SAMPLER - reopen_base + len(sampler)]),
            sampler, "ELF sampler image")
    handoff_name = ".lisp65_c2_kernal_handoff"
    handoff = bytearray(truth.section_bytes(handoff_name))
    handoff_base = truth.section(handoff_name).address
    replace(handoff, CRC_HIGH - handoff_base, bytes((0xD5,)),
            bytes((new_crc >> 8,)), "ELF sampler CRC high")
    replace(handoff, CRC_LOW - handoff_base, bytes((0xCB,)),
            bytes((new_crc & 0xFF,)), "ELF sampler CRC low")
    patch_elf(base_elf_path, {
        ".text": bytes(text), irq_name: bytes(irq), reopen_name: bytes(reopen),
        handoff_name: bytes(handoff),
        ".lisp65_v16_defstruct_vm_progress_helper": helper,
        ".lisp65_v16_defstruct_vm_progress_state": LOW_STATE_RESET,
    })

    derived = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    edges = executable_edges(derived, SAMPLER)
    require(edges == [{"section": irq_name, "pc": "0xe053", "opcode": "JSR"}],
            f"sampler inbound-edge closure drift: {edges}")
    require(derived.section_bytes(reopen_name)[SAMPLER - reopen_base:
            SAMPLER_LIMIT - reopen_base] == sampler,
            "ELF sampler region drift")
    require(derived.section_bytes(".text")[ABORT_CALL - text_base:
            ABORT_CALL - text_base + 3] == b"\xea\xea\xea",
            "abort/guard edge still reaches sampler")

    vectors = helper_vectors(helper)
    readers = reader_vectors()
    execution_mutations = executable_mutations(
        bytes(window), RUNNER.read_text(encoding="utf-8"))
    gap_seconds = SAMPLE_FRAMES * 1000 / FRAME_HZ_MILLI
    max_increments = int(40_000_000 * gap_seconds)
    require(gap_seconds < 60 and max_increments < 2**32,
            "u32 progress delta can ABA-wrap inside sample gap")

    deploy = deepcopy(base)
    deploy["format"] = "lisp65-c2.3-v1.6-vm-progress-noninterference-deployment-v1"
    deploy["status"] = "HOST-GREEN-NON-PROMOTABLE-SELF-SAMPLING-ARMED"
    deploy["diagnostic"]["prg"] = bind(PRG)
    deploy["diagnostic"]["elf"] = bind(ELF)
    deploy["diagnostic"]["window"] = bind(WINDOW)
    for row in deploy["diagnostic"]["preloads"]:
        if row["role"] == "c2-kernal-window":
            row.update(bind(WINDOW))
        elif row["role"] == "diagnostic-vm-progress-lowram":
            row.update(bind(LOW_PRELOAD_BIN))
    deploy["ownership_guard_binding"] = {
        "validated_window": bind(WINDOW),
        "computed_crc16": f"0x{new_crc:04X}",
        "final_PRG_operand_addresses": ["0xB4F4", "0xB4FA"],
        "final_PRG_operand_bytes": f"{new_crc:04x}",
        "recontact_authorized": False,
    }
    deploy["vm_progress"] = {
        "helper": {"start": "0x1fce", "end_exclusive": "0x1ff8",
                   "bytes": HELPER_BYTES},
        "state": {"start": "0x1ff8", "end_exclusive": "0x2000",
                  "bytes": LOW_STATE_BYTES,
                  "layout": ["counter_u32_le", "owner_ordinal_u16_le",
                             "arm", "reserved"]},
        "sampler": {"start": "0xfee1", "end_exclusive": "0xff40",
                    "slots": ["0xff40", "0xff60"],
                    "slots_physical": "0x087fff40"},
        "sample_period_frames": SAMPLE_FRAMES,
        "sample_period_seconds": f"{gap_seconds:.6f}",
        "quiet_floor_seconds": QUIET_FLOOR_SECONDS,
        "sample_transport": "target-owned-raster-self-snapshot",
        "recontact_authorized": False,
    }
    write_json(DEPLOY, deploy)

    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; FINAL-CONTACT-CONSUMED; 1.6-FINAL-PARK",
        "authorities": {
            "owner_commission": git_bind(OWNER_COMMIT, PLAN_PATH),
            "contact_authorization": git_bind(AUTHORIZATION_COMMIT, PLAN_PATH),
            "autonomous_launch_first_red": bind(LAUNCH_FIRST_RED),
            "line_verify_first_red": bind(LINE_VERIFY_FIRST_RED),
            "physical_launch_first_red": bind(PHYSICAL_LAUNCH_FIRST_RED),
            "final_contact_first_red": bind(FINAL_CONTACT_FIRST_RED),
            "base_progress_deployment": bind(BASE_DEPLOY),
            "base_progress_receipt": bind(BASE_RECEIPT),
            "cost_closure": bind(COST_RECEIPT),
            "source_less_guard_receipt": bind(GUARD_RECEIPT),
            "kernal_IRQ_source": bind(KERNAL_SOURCE),
            "runner": bind(RUNNER), "driver": bind(DRIVER),
        },
        "identity": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0, "hardware_contacts": 4,
            "base_progress_PRG": bind(base_prg_path),
            "base_progress_ELF": bind(base_elf_path),
            "base_progress_window": bind(base_window_path),
            "diagnostic_PRG": bind(PRG), "diagnostic_ELF": bind(ELF),
            "diagnostic_window": bind(WINDOW),
            "atomic_lowram_preload": bind(LOW_PRELOAD_BIN),
            "slot_reset": bind(SLOT_RESET_BIN),
            "window_crc16": f"0x{new_crc:04X}",
            "abort_driver_available_in_diagnostic": False,
            "abort_call_retired_at": "0x2dde",
        },
        "guard_binding": {
            **source_contract,
            "sampler_only_inbound_edge": edges[0],
            "sampler_edges_from_source_less_or_fail_closed": 0,
            "sampler_reads_D019": False,
            "sampler_writes_D019_or_D01A": False,
            "sampler_monitor_or_CPU_stop_operations": 0,
            "diagnostic_abort_edge_retired": True,
        },
        "producer": {
            "counter": {"address": "0x1ff8", "bits": 32,
                        "granularity": "every VM dispatch"},
            "owner": {"address": "0x1ffc", "bits": 16,
                      "source": "vm_buf_off"},
            "atomicity": "PHP; SEI; producer update; PLA; PLP",
            "IRQ_observation_states": "old-complete or new-complete only",
            "execution_vectors": vectors,
            "torn_interruptible_states": 0,
            "register_stack_contract": {
                "A_preserved": True, "stack_balanced": True,
                "I_restored": True, "final_NZ_from_displaced_LDX": True,
            },
        },
        "self_snapshot": {
            "trigger": "owned raster IRQ after D019 bit-0 proof and acknowledge",
            "period_frames": SAMPLE_FRAMES,
            "period_seconds_at_51_966Hz": f"{gap_seconds:.6f}",
            "ring": {"slots": SLOT_COUNT, "slot_bytes": SLOT_BYTES,
                     "logical_range": ["0xff40", "0xff60"],
                     "physical_range": ["0x087fff40", "0x087fff60"]},
            "slot_layout": ["counter_u32_le", "owner_u16_le", "frame_hi", "commit"],
            "writer_order": ["commit=0", "payload", "commit=0xA5"],
            "reader_rule": (
                "after the one final CPU stop, reject commit!=A5 and non-multiple-"
                "of-8 frame tags; order by modulo-256 age from FF84; accept only "
                "the two newest slots whose frame tags differ by exactly 8"),
            "reader_vectors": readers,
            "one_slot_torn_retains_complete_slots": 3,
        },
        "ABA_closure": {
            "old_8bit_seqlock_consumed_by_reader": False,
            "reason": (
                "the producer is IRQ-masked during its multi-byte update; the "
                "snapshot executes inside that IRQ; the reader runs only after "
                "the final stop and validates commit-last ring slots"),
            "counter_bits": 32,
            "maximum_sample_gap_frames": SAMPLE_FRAMES,
            "maximum_sample_gap_seconds": f"{gap_seconds:.6f}",
            "one_cycle_dispatch_upper_bound_in_gap": max_increments,
            "counter_modulus": 2**32,
            "counter_wrap_possible_in_gap": False,
            "frame_tag_stride": SAMPLE_HIGH_STRIDE,
            "frame_tag_wrap_disambiguated_by_four_slot_age_window": True,
        },
        "choreography": choreography,
        "decision_table": {
            "form_completes_before_final_stop": "PRODUCT-COMPLETES; progress samples unused",
            "modulo_u32_delta_nonzero": "LIVE-VM-DISPATCH-PROGRESS",
            "modulo_u32_delta_zero": (
                "NO-VM-DISPATCH-IN-39.410SEC; later owner plus final code-owner/PC "
                "names the VM owner or native boundary; not alone an infinite-loop claim"),
            "fewer_than_two_valid_consecutive_slots": "INSTRUMENT-FIRST-RED; NO PRODUCT CLAIM",
        },
        "mutations": {
            "required_named": ["CPU-stop-mid-persistent-operation",
                               "unverified-combined-launch-submit",
                               "screen-helper-clobbers-line-id",
                               "prelaunch-monitor-after-resume",
                               "accept-torn-or-8bit-ABA-window",
                               "sampler-reachable-from-source-less-guard"],
            "execution_rejected": execution_mutations,
            "receipt_rejected": 24,
            "rejected": 30,
        },
        "deployment": bind(DEPLOY),
        "accounting": {"product_bytes_changed": 0, "product_links": 0,
                       "hardware_runs": 4, "recontact_authorized": False,
                       "hard_edge": "executed-1.6-final-park"},
        "claim_limit": (
            "Host proof of a non-promotable autonomous two-snapshot identity. "
            "It proves that sample one cannot stop the CPU, enter the monitor or "
            "reach the source-less guard, and that the accepted pair cannot be an "
            "8-bit ABA/torn read. Neither spent autonomous launch contact reached "
            "a submitted product RUN or the measured form. It does not report target "
            "progress or name a product mechanism. The spent physical contact had a "
            "forbidden prelaunch monitor crossing and is not product evidence. The "
            "final minimal physical contact observed a diagnostic-launch First Red "
            "before require, defstruct or either progress row, despite zero automated "
            "device actions after the final staging resume. The pre-bound hard edge "
            "parks 1.6. This receipt authorizes no further contact and makes no new "
            "product-mechanism, progress, performance or R/A/I/G claim."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] ==
            "HOST-GREEN; FINAL-CONTACT-CONSUMED; 1.6-FINAL-PARK",
            "non-interference status drift")
    require(value["identity"]["promotable"] is False
            and value["identity"]["product_candidate_bytes_changed"] == 0
            and value["identity"]["product_links"] == 0
            and value["identity"]["hardware_contacts"] == 4
            and value["identity"]["abort_driver_available_in_diagnostic"] is False,
            "diagnostic identity boundary drift")
    guard = value["guard_binding"]
    require(guard["source_less_branch_precedes_sampler"] is True
            and guard["sampler_only_inbound_edge"] == {
                "section": ".lisp65_c2_kernal_window.irq_handler",
                "pc": "0xe053", "opcode": "JSR"}
            and guard["sampler_edges_from_source_less_or_fail_closed"] == 0
            and guard["sampler_reads_D019"] is False
            and guard["sampler_writes_D019_or_D01A"] is False
            and guard["sampler_monitor_or_CPU_stop_operations"] == 0
            and guard["diagnostic_abort_edge_retired"] is True,
            "sampler/guard separation drift")
    producer = value["producer"]
    require(producer["counter"]["bits"] == 32
            and producer["atomicity"] == "PHP; SEI; producer update; PLA; PLP"
            and producer["IRQ_observation_states"] == "old-complete or new-complete only"
            and producer["torn_interruptible_states"] == 0
            and len(producer["execution_vectors"]) == 7,
            "atomic producer contract drift")
    snap = value["self_snapshot"]
    require(snap["trigger"].startswith("owned raster IRQ")
            and snap["period_frames"] == SAMPLE_FRAMES
            and snap["ring"] == {"slots": 4, "slot_bytes": 8,
                                 "logical_range": ["0xff40", "0xff60"],
                                 "physical_range": ["0x087fff40", "0x087fff60"]}
            and snap["writer_order"] == ["commit=0", "payload", "commit=0xA5"]
            and snap["one_slot_torn_retains_complete_slots"] == 3
            and len(snap["reader_vectors"]) == 2,
            "self-snapshot protocol drift")
    aba = value["ABA_closure"]
    require(aba["old_8bit_seqlock_consumed_by_reader"] is False
            and aba["counter_bits"] == 32
            and aba["maximum_sample_gap_frames"] == SAMPLE_FRAMES
            and aba["one_cycle_dispatch_upper_bound_in_gap"] < aba["counter_modulus"]
            and aba["counter_wrap_possible_in_gap"] is False
            and aba["frame_tag_wrap_disambiguated_by_four_slot_age_window"] is True,
            "ABA/wrap closure drift")
    choreography = value["choreography"]
    require(choreography == {
        "quiet_floor_seconds": QUIET_FLOOR_SECONDS,
        "external_calls_during_active_sample_interval": 0,
        "monitor_entries_during_active_sample_interval": 0,
        "CPU_stop_transitions_after_samples": 1,
        "sample_producer": "owned raster IRQ on target",
        "prelaunch_monitor_accesses_after_resume": 0,
        "intermediate_automated_device_actions": 0,
        "owner_keyboard_inputs": 3,
        "physical_inputs": [
            "RUN", "(require (quote defstruct))", "(defstruct point x y)"],
    }, "non-interfering choreography drift")
    mutations = value["mutations"]
    require(mutations["required_named"] == [
        "CPU-stop-mid-persistent-operation",
        "unverified-combined-launch-submit",
        "screen-helper-clobbers-line-id",
        "prelaunch-monitor-after-resume",
        "accept-torn-or-8bit-ABA-window",
        "sampler-reachable-from-source-less-guard"]
        and set(mutations["execution_rejected"]) == set(mutations["required_named"])
        and mutations["receipt_rejected"] == 24
        and mutations["rejected"] == 30,
        "mutation closure drift")
    require(value["accounting"] == {"product_bytes_changed": 0,
                                     "product_links": 0, "hardware_runs": 4,
                                     "recontact_authorized": False,
                                     "hard_edge": "executed-1.6-final-park"},
            "contact/accounting boundary drift")


def set_path(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    cases: list[tuple[str, list[Any], Any]] = [
        ("authorize-recontact", ["accounting", "recontact_authorized"], True),
        ("promotable", ["identity", "promotable"], True),
        ("product-byte", ["identity", "product_candidate_bytes_changed"], 1),
        ("restore-abort-edge", ["guard_binding", "diagnostic_abort_edge_retired"], False),
        ("sampler-second-edge", ["guard_binding", "sampler_edges_from_source_less_or_fail_closed"], 1),
        ("sampler-guard-PC", ["guard_binding", "sampler_only_inbound_edge", "pc"], "0xe07a"),
        ("sampler-reads-D019", ["guard_binding", "sampler_reads_D019"], True),
        ("sampler-writes-D01A", ["guard_binding", "sampler_writes_D019_or_D01A"], True),
        ("sampler-monitor", ["guard_binding", "sampler_monitor_or_CPU_stop_operations"], 1),
        ("producer-16bit", ["producer", "counter", "bits"], 16),
        ("producer-no-SEI", ["producer", "atomicity"], "ordinary seqlock"),
        ("producer-torn", ["producer", "torn_interruptible_states"], 1),
        ("drop-vector", ["producer", "execution_vectors"], []),
        ("two-slots", ["self_snapshot", "ring", "slots"], 2),
        ("non-owned-trigger", ["self_snapshot", "trigger"], "freezer NMI"),
        ("write-commit-first", ["self_snapshot", "writer_order"], ["commit=A5", "payload"]),
        ("accept-torn", ["self_snapshot", "one_slot_torn_retains_complete_slots"], 0),
        ("consume-8bit-seqlock", ["ABA_closure", "old_8bit_seqlock_consumed_by_reader"], True),
        ("long-gap", ["ABA_closure", "maximum_sample_gap_frames"], 8192),
        ("accept-counter-wrap", ["ABA_closure", "counter_wrap_possible_in_gap"], True),
        ("drop-frame-age", ["ABA_closure", "frame_tag_wrap_disambiguated_by_four_slot_age_window"], False),
        ("CPU-stop-mid-persistent-operation", ["choreography", "CPU_stop_transitions_after_samples"], 2),
        ("monitor-mid-persistent-operation", ["choreography", "monitor_entries_during_active_sample_interval"], 1),
        ("external-read-mid-persistent-operation", ["choreography", "external_calls_during_active_sample_interval"], 1),
    ]
    rejected: dict[str, str] = {}
    for name, path, replacement in cases:
        trial = deepcopy(value); set_path(trial, path, replacement)
        try:
            audit(trial)
        except ProofError as error:
            rejected[name] = str(error)
        else:
            raise ProofError(f"non-interference mutation survived: {name}")
    # check-source must not depend on the ignored materialized ELF/window.
    # A minimal linked-route fixture retains the real addresses and edge bytes;
    # the explicit ``check`` below repeats the mutation on the actual window.
    route_fixture = bytearray(WINDOW_BYTES)
    route_fixture[IRQ_SAMPLE_CALL - WINDOW_BASE:
                  IRQ_SAMPLE_CALL - WINDOW_BASE + 3] = b"\x20" + u16(SAMPLER)
    executable = executable_mutations(
        bytes(route_fixture), RUNNER.read_text(encoding="utf-8"))
    require(len(rejected) == value["mutations"]["receipt_rejected"]
            and executable == value["mutations"]["execution_rejected"],
            "mutation count/execution drift")
    return {"status": "SELFTEST PASS",
            "mutations": len(rejected) + len(executable),
            "execution_mutations": sorted(executable),
            "helper_vectors": len(value["producer"]["execution_vectors"]),
            "reader_vectors": len(value["self_snapshot"]["reader_vectors"]),
            "rejected": rejected}


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    for key in ("diagnostic_PRG", "diagnostic_ELF", "diagnostic_window",
                "atomic_lowram_preload", "slot_reset"):
        require(bind(ROOT / value["identity"][key]["path"])
                == value["identity"][key], f"artifact drift: {key}")
    require(bind(DEPLOY) == value["deployment"], "deployment drift")
    require(helper_vectors(HELPER_BIN.read_bytes())
            == value["producer"]["execution_vectors"], "helper vector drift")
    require(reader_vectors() == value["self_snapshot"]["reader_vectors"],
            "reader vector drift")
    require(runner_contract(RUNNER.read_text(encoding="utf-8"))
            == value["choreography"], "runner contract drift")
    require(executable_mutations(WINDOW.read_bytes(),
            RUNNER.read_text(encoding="utf-8"))
            == value["mutations"]["execution_rejected"],
            "executable mutation receipt drift")
    return {"status": "PASS", "mutations": value["mutations"]["rejected"],
            "sample_period_frames": SAMPLE_FRAMES,
            "quiet_floor_seconds": QUIET_FLOOR_SECONDS,
            "recontact_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        if OUT.exists():
            shutil.rmtree(OUT)
        value = build(); write_json(RECEIPT, value)
        result = {"status": "WRITTEN", "crc16": value["identity"]["window_crc16"],
                  "recontact_authorized": False}
    elif args.action == "selftest":
        result = selftest()
    else:
        result = check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProofError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"VM PROGRESS NONINTERFERENCE FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
