#!/usr/bin/env python3
"""Class-B cycle 1: hold Link 50 before BADOPCODE cleanup and capture it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK50 = ROOT / (
    "build/c2.2/substitution/"
    "product-link-50-c2-lite-v6-persistent-header")
BASE_PRODUCT = LINK50 / "lisp65-c2-substitution-linked.prg"
BASE_ELF = Path(str(BASE_PRODUCT) + ".elf")
BASE_MAP = Path(str(BASE_PRODUCT) + ".map")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-"
    "artifact-replay-structural-receipt.json")
BASE_DEPLOYMENT = ROOT / (
    "build/c2.2/hardware-presmoke-link50-persistent-header/deployment.json")
BASE_CAPTURE = ROOT / "build/c2.2/hardware-diagnosis-link50-call-badopcode"
BASE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link50-first-call-badopcode-hardware-first-red.json")

BASE_PRODUCT_SHA = (
    "3e13c9101b53ba89b8fb33e0f11c641ca53803b3f447831c5e1243475f7bc216")
BASE_ELF_SHA = (
    "0ac6121a0e1b484efafd81334fbe5c14909b8b741e20ee1f41caa615524f7f47")
BASE_MAP_SHA = (
    "d7a8ada85ffab8f88c79224297528c2d7da2c19c62dac7bbe9e7ecfd47d2447c")
BASE_RECEIPT_SHA = (
    "e7f47adebda448583efa6e28d86ff28bb335adf3178853b5177e736cccd36170")
BASE_DEPLOYMENT_SHA = (
    "9a2d61d22f0c47a050d4e35b06d489a2bcaa9881abb3611234d7a09b91270628")

OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-first-call-badopcode-hold-cycle1-NONPROMOTABLE")
PRODUCT = OUT / "lisp65-link50-badopcode-hold-cycle1-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-patch-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-hold-cycle1-patch-receipt.json")
HW_OUT = ROOT / "build/c2.2/hardware-link50-badopcode-hold-cycle1"
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-hold-cycle1-hardware-receipt.json")
HARDWARE_INTERPRETATION_CORRECTION = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-hold-cycle1-"
    "interpretation-correction.json")
HARDWARE_RECEIPT_SHA = (
    "24f13b1a8b03336c48606e5e37cd57be174b2a6aebfb4d2fc44c5f5cde88ab8a")
OWNER_NAME_AUTHORITY = EVIDENCE / (
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")

LOAD_ADDRESS = 0x2001
INSTRUCTION_ADDRESS = 0x3774
INSTRUCTION_FILE_OFFSET = 2 + INSTRUCTION_ADDRESS - LOAD_ADDRESS
BEFORE = bytes.fromhex("8617")       # STX __rc21: first status >= 2 edge
AFTER = bytes.fromhex("80fe")        # BRA $3774: hold before cleanup/render
CHANGED_FILE_OFFSETS = (INSTRUCTION_FILE_OFFSET,
                        INSTRUCTION_FILE_OFFSET + 1)

VM_STATUS = 0x005B
C2_JOURNAL_COUNT = 0x002E
C2_READY = 0x008C
VM_BUF_OFF = 0xB976
VM_CODEBUF = 0xBF5A
VM_CODEBUF_BYTES = 56
VM_BUF_BANK = 0xBF92
VMR_HDRLEN = 0xBF93
VMR_LITTAB = 0xBF95
VMR_CODE = 0xBF97
VMR_PAYLOAD_OFF = 0xBF99
VMR_PAYLOAD_LEN = 0xBF9B
VMR_PAYLOAD_WINDOW_MAX = 0xBF9D
VMR_WIN = 0xBF9F
VMR_WINLEN = 0xBFA1
VMR_STREAMING = 0xBFA3
VM_STATE_START = VM_BUF_BANK
VM_STATE_END = VMR_STREAMING + 1
C2_PRODUCT_CODE_BANK_TAG = 1
C2_CODE_HEADER_SCALAR_BYTES = 7
C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
DYNAMIC_ORDINAL = 588
EXPECTED_CODE = bytes.fromhex("b50000020200002c05")
STATIC_BANK2_BYTES = 34403

TOOLS = ROOT / "tools/m65tools"
DEVICE = Path("/dev/ttyUSB1")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise GateError(f"missing {label}: {path}: {exc}") from exc
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"{label} is not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid {label}: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root is not an object")
    return value


def u16(data: bytes, offset: int = 0) -> int:
    require(offset >= 0 and offset + 2 <= len(data), "u16 outside artifact")
    return int.from_bytes(data[offset:offset + 2], "little")


def entry(data: bytes, ordinal: int) -> dict[str, Any]:
    at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
    row = data[at:at + C2D_ENTRY_BYTES]
    require(len(row) == C2D_ENTRY_BYTES, "C2D entry outside Bank 5")
    return {
        "ordinal": ordinal,
        "raw_hex": row.hex(),
        "image_slot": row[0],
        "literal_count": row[1],
        "code_offset": u16(row, 2),
        "code_length": u16(row, 4),
        "resolution_base": u16(row, 6),
        "generation": u16(row, 8),
    }


def verify_authority() -> dict[str, Any]:
    expected = {
        BASE_PRODUCT: BASE_PRODUCT_SHA,
        BASE_ELF: BASE_ELF_SHA,
        BASE_MAP: BASE_MAP_SHA,
        BASE_RECEIPT: BASE_RECEIPT_SHA,
        BASE_DEPLOYMENT: BASE_DEPLOYMENT_SHA,
    }
    for path, digest in expected.items():
        require(sha(path) == digest, f"Link-50 authority drift: {path}")
    receipt = load_json(BASE_RECEIPT, "Link-50 structural receipt")
    require(receipt.get("status") ==
            "passed-new-c2-lite-persistent-header-identity-hardware-not-run",
            "Link-50 structural authority is not green")
    require(receipt.get("product_identity", {}).get("product", {}).get(
        "sha256") == BASE_PRODUCT_SHA,
        "Link-50 structural product binding drift")
    deployment = load_json(BASE_DEPLOYMENT, "Link-50 deployment")
    require(deployment.get("status") == "ready-receipt-less"
            and deployment.get("new_product_links") == 0
            and deployment.get("product", {}).get("sha256") == BASE_PRODUCT_SHA,
            "Link-50 deployment is not authoritative")
    for row in deployment.get("preloads", []):
        path = ROOT / row["path"]
        require(bind(path)["bytes"] == row["bytes"]
                and sha(path) == row["sha256"],
                f"Link-50 preload drift: {path}")
    nm = subprocess.check_output([
        str(ROOT / "tools/llvm-mos/bin/llvm-nm"), "-S", "--size-sort",
        str(BASE_ELF)], text=True)
    require("00003766 0000004c t vm_check_status" in nm,
            "vm_check_status ELF interval drift")
    return {
        "product": bind(BASE_PRODUCT),
        "elf": bind(BASE_ELF),
        "map": bind(BASE_MAP),
        "structural_receipt": bind(BASE_RECEIPT),
        "source_deployment": bind(BASE_DEPLOYMENT),
    }


def bind_first_red() -> dict[str, Any]:
    if BASE_FIRST_RED.exists():
        value = load_json(BASE_FIRST_RED, "Link-50 first-red receipt")
        require(value.get("status") ==
                "first-red-valid-dynamic-object-fails-at-first-execution",
                "Link-50 first-red status drift")
        return value
    paths = {name: BASE_CAPTURE / f"{name}.bin"
             for name in ("bank0", "bank2", "bank3", "bank5")}
    images = {name: regular(path, f"Link-50 {name} capture")
              for name, path in paths.items()}
    require(all(len(data) == 65536 for data in images.values()),
            "Link-50 first-red capture geometry drift")
    bank0, bank2, bank5 = images["bank0"], images["bank2"], images["bank5"]
    initial_bank2 = regular(
        LINK50 / "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
    require(len(initial_bank2) == STATIC_BANK2_BYTES
            and bank2[:STATIC_BANK2_BYTES] == initial_bank2,
            "Link-50 static Bank-2 plane drift")
    require(bank5[:5] == b"C2D\0\x06", "live C2D-v6 magic drift")
    header = {
        "transient_watermark": u16(bank5, 8),
        "generation": u16(bank5, 10),
        "image_count": u16(bank5, 12),
        "entry_count": u16(bank5, 16),
        "resolution_count": u16(bank5, 20),
        "root_count": u16(bank5, 24),
    }
    require(header == {
        "transient_watermark": 4096,
        "generation": 1,
        "image_count": 7,
        "entry_count": 589,
        "resolution_count": 2264,
        "root_count": 283,
    }, f"Link-50 post-definition C2D header drift: {header}")
    row = entry(bank5, DYNAMIC_ORDINAL)
    require(row == {
        "ordinal": 588,
        "raw_hex": "060063860900d8080100",
        "image_slot": 6,
        "literal_count": 0,
        "code_offset": 0x8663,
        "code_length": 9,
        "resolution_base": 0x08d8,
        "generation": 1,
    }, f"Link-50 dynamic entry drift: {row}")
    code = bank2[row["code_offset"]:
                 row["code_offset"] + row["code_length"]]
    require(code == EXPECTED_CODE, "Link-50 dynamic code object drift")
    state = {
        "c2_ready": bank0[C2_READY],
        "c2_journal_count": u16(bank0, C2_JOURNAL_COUNT),
        "vm_status_after_repl_renderer": bank0[VM_STATUS],
    }
    require(state == {"c2_ready": 1, "c2_journal_count": 0,
                      "vm_status_after_repl_renderer": 0},
            f"Link-50 post-error state drift: {state}")
    value = {
        "format": "lisp65-c2-link50-first-call-badopcode-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-valid-dynamic-object-fails-at-first-execution",
        "candidate": verify_authority(),
        "operator_observation": "*** vm: bad bytecode",
        "definition": {
            "form": "(defun %c2h () 't)",
            "repl_result": "%c2h",
            "entry": row,
            "code_hex": code.hex(),
            "decoded_payload": ["OP_PUSHT", "OP_RET"],
        },
        "hardware_state": state,
        "captures": {name: bind(path) for name, path in paths.items()},
        "finding": (
            "Definition, append, persistent header publication and Bank-2 "
            "code bytes are coherent. The first invocation alone returns "
            "VM_BADOPCODE; the later REPL renderer overwrote vm_codebuf, so "
            "the runtime refill versus VM-dispatch split remains unproved."),
        "accounting": {
            "line1": "green", "line1_first_red_budget": "2/3",
            "completed_latency_attempts": "0/2",
        },
        "claim_limit": (
            "Read-only Link-50 hardware First-Red binding. It proves the "
            "published dynamic object and post-error state, but not the exact "
            "runtime execution cutpoint, product acceptance or latency."),
    }
    write_json(BASE_FIRST_RED, value)
    for path in [*paths.values(), BASE_FIRST_RED]:
        os.chmod(path, 0o444)
    os.chmod(BASE_CAPTURE, 0o555)
    return value


def patched(source: bytes) -> bytes:
    require(len(source) > INSTRUCTION_FILE_OFFSET + 2,
            "Link-50 PRG does not contain patch span")
    require(u16(source, 0) == LOAD_ADDRESS, "Link-50 PRG load address drift")
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == BEFORE,
            "Link-50 vm_check_status failure edge drift")
    result = bytearray(source)
    result[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] = AFTER
    return bytes(result)


def exact_patch_gate_shallow(source: bytes, candidate: bytes) -> None:
    require(len(candidate) == len(source), "post-link patch changed file size")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == list(CHANGED_FILE_OFFSETS), "patch diff-domain mutation")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == AFTER,
            "patch self-loop mutation")


def exact_patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    exact_patch_gate_shallow(source, candidate)
    mutations: dict[str, bytearray] = {}
    mutations["wrong-opcode"] = bytearray(candidate)
    mutations["wrong-opcode"][INSTRUCTION_FILE_OFFSET] = 0xea
    mutations["wrong-relative-target"] = bytearray(candidate)
    mutations["wrong-relative-target"][INSTRUCTION_FILE_OFFSET + 1] = 0xfc
    mutations["only-opcode-changed"] = bytearray(candidate)
    mutations["only-opcode-changed"][INSTRUCTION_FILE_OFFSET + 1] = BEFORE[1]
    mutations["only-operand-changed"] = bytearray(candidate)
    mutations["only-operand-changed"][INSTRUCTION_FILE_OFFSET] = BEFORE[0]
    mutations["extra-neighbour-byte"] = bytearray(candidate)
    mutations["extra-neighbour-byte"][INSTRUCTION_FILE_OFFSET + 2] ^= 1
    rejected: dict[str, str] = {}
    for name, mutated in mutations.items():
        try:
            exact_patch_gate_shallow(source, bytes(mutated))
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"post-link mutation accepted: {name}")
    return {
        "status": "passed-exact-two-byte-badopcode-self-loop-patch",
        "function": "vm_check_status",
        "function_interval": "0x3766..0x37b1",
        "instruction_address": "0x3774",
        "instruction_file_offset": f"0x{INSTRUCTION_FILE_OFFSET:04x}",
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "before_semantics": "STX __rc21, continue to status mapping and abort",
        "after_semantics": "BRA $3774, hold before status clear and renderer",
        "changed_file_offsets": [f"0x{value:04x}"
                                 for value in CHANGED_FILE_OFFSETS],
        "changed_cpu_addresses": ["0x3774", "0x3775"],
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not PATCH_RECEIPT.exists(),
            "Link-50 BADOPCODE hold cycle 1 already exists")
    authority = verify_authority()
    first_red = bind_first_red()
    source = regular(BASE_PRODUCT)
    candidate = patched(source)
    gate = exact_patch_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    require(regular(PRODUCT) == candidate, "diagnostic product writeback drift")
    manifest = {
        "format": "lisp65-c2-link50-badopcode-hold-cycle1-patch-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-nonpromotable-fixed-length-badopcode-hold",
        "promotable": False,
        "delegation": {
            "class": "B", "cycle": 1, "cycle_cap": 3,
            "question": "first execution of a proven-valid dynamic object",
        },
        "authority": authority,
        "first_red": bind(BASE_FIRST_RED),
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": gate,
        "capture_contract": {
            "three_time_separated_bank0_captures": True,
            "vm_status": "0x005b",
            "vm_codebuf": "0xbf5a..0xbf91",
            "vm_window_state": "0xbf92..0xbfa3",
            "vm_buf_off": "0xb976..0xb977",
            "live_bank2": "0x00020000..0x0002ffff",
            "live_c2d_bank5": "0x00050000..0x0005ffff",
            "classification": {
                "byteidentical_buffer": "runtime refill exonerated; VM cursor/dispatch",
                "different_buffer": "Bank-2-to-vm_codebuf refill edge",
            },
        },
        "capacity_effect": {
            "bank0_text_bytes": 0,
            "ordinary_bank0_bss_bytes": 0,
            "fixed_hot_block_bytes": 0,
            "resident_island_bytes": 0,
            "e000_bytes": 0,
            "session_family_bytes": 0,
            "runtime_slice_bytes": 0,
            "file_bytes": 0,
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "changed_bytes": 2, "hardware_runs": 0,
            "promotable_candidates": 0,
        },
        "claim_limit": (
            "Permanently non-promotable two-byte derivative of the SHA-bound "
            "Link-50 product. It carries no product, capacity, latency, "
            "promotion or acceptance claim."),
        "rollback_line": {**bind(BASE_PRODUCT), "status": "untouched"},
        "next_gate": "one announced Class-B cycle-1 hardware run",
    }
    write_json(MANIFEST, manifest)
    value = {**manifest, "manifest": bind(MANIFEST)}
    write_json(PATCH_RECEIPT, value)
    for path in (PRODUCT, MANIFEST, PATCH_RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return value


def check() -> dict[str, Any]:
    verify_authority()
    bind_first_red()
    value = load_json(PATCH_RECEIPT, "BADOPCODE hold patch receipt")
    require(value.get("status") ==
            "passed-nonpromotable-fixed-length-badopcode-hold"
            and value.get("promotable") is False,
            "BADOPCODE hold receipt is not green/nonpromotable")
    source, candidate = regular(BASE_PRODUCT), regular(PRODUCT)
    require(bind(PRODUCT) == value["diagnostic_identity"],
            "BADOPCODE hold diagnostic identity drift")
    exact_patch_gate(source, candidate)
    require(all(delta == 0 for delta in value["capacity_effect"].values()),
            "BADOPCODE hold changed a bound capacity")
    return value


def prepare_hardware() -> dict[str, Any]:
    receipt = check()
    require(not DEPLOYMENT.exists(), "BADOPCODE hold deployment already exists")
    source = load_json(BASE_DEPLOYMENT, "Link-50 deployment")
    deployment = {
        **source,
        "format": "lisp65-c2-link50-badopcode-hold-deployment-v1",
        "status": "ready-nonpromotable-class-b-cycle1",
        "product": {**bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "base_link50_product": bind(BASE_PRODUCT),
            "authorization_receipt": bind(PATCH_RECEIPT),
            "patch_manifest": bind(MANIFEST),
        },
        "new_product_links": 0,
        "promotable": False,
        "manual_sequence": [
            "wait for banner and REPL",
            "evaluate (defun %c2h () 't); expect %c2h",
            "evaluate (%c2h) exactly once; expect the machine to hold without rendering an error",
            "enter nothing further; take the read-only JTAG captures",
        ],
        "claim_limit": (
            "One non-promotable Class-B diagnostic deployment; never a "
            "product presmoke, latency attempt, promotion or acceptance run."),
    }
    HW_OUT.mkdir(parents=True)
    write_json(DEPLOYMENT, deployment)
    return deployment


def verify_hardware() -> dict[str, Any]:
    check()
    value = load_json(DEPLOYMENT, "BADOPCODE hold deployment")
    require(value.get("status") == "ready-nonpromotable-class-b-cycle1"
            and value.get("promotable") is False
            and value.get("new_product_links") == 0,
            "BADOPCODE hold deployment status drift")
    require(bind(PRODUCT) == {key: value["product"][key]
                              for key in ("path", "bytes", "sha256")},
            "BADOPCODE hold deployment product drift")
    for row in value["preloads"]:
        path = ROOT / row["path"]
        require(bind(path)["bytes"] == row["bytes"]
                and sha(path) == row["sha256"],
                f"BADOPCODE hold preload drift: {path}")
    return value


def run_command(arguments: list[str], timeout_seconds: int = 90) -> None:
    try:
        subprocess.run(arguments, cwd=ROOT, check=True,
                       timeout=timeout_seconds)
    except (OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise GateError(f"hardware command failed: {arguments}: {exc}") from exc


def m65(*arguments: str) -> list[str]:
    return [str(TOOLS / "m65"), "-l", str(DEVICE), *arguments]


def require_hardware_tools() -> None:
    require((TOOLS / "m65").is_file() and os.access(TOOLS / "m65", os.X_OK),
            "m65 JTAG tool absent")
    try:
        mode = DEVICE.stat().st_mode
    except OSError as exc:
        raise GateError(f"JTAG device absent: {DEVICE}: {exc}") from exc
    require(stat.S_ISCHR(mode), f"JTAG device is not a character device: {DEVICE}")


def deploy_hardware() -> dict[str, Any]:
    value = verify_hardware()
    require_hardware_tools()
    require(not (HW_OUT / "launch.json").exists(),
            "BADOPCODE hold hardware cycle already launched")
    run_command(m65("-F", "-H", "-1", str(PRODUCT)))
    readbacks: list[dict[str, Any]] = []
    for row in value["preloads"]:
        path = ROOT / row["path"]
        address = int(row["address"], 16)
        end = address + row["bytes"]
        readback = HW_OUT / ("readback-" + path.name)
        run_command(m65("-H", "-@", f"{path}@0x{address:08x}"))
        run_command(m65("--memsave",
                        f"0x{address:08x}:0x{end:08x}={readback}"))
        require(regular(readback) == regular(path),
                f"JTAG preload readback mismatch: {path}")
        readbacks.append(bind(readback, address))
    run_command(m65("-r", "-1", str(PRODUCT)))
    launch = {
        "format": "lisp65-c2-link50-badopcode-hold-launch-v1",
        "status": "launched-nonpromotable-class-b-cycle1",
        "monotonic_ns": time.monotonic_ns(),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT, LOAD_ADDRESS),
        "preload_readbacks": readbacks,
        "operator_next": value["manual_sequence"],
    }
    write_json(HW_OUT / "launch.json", launch)
    return launch


def capture_hardware() -> dict[str, Any]:
    verify_hardware()
    require_hardware_tools()
    launch = load_json(HW_OUT / "launch.json", "BADOPCODE hold launch")
    require(launch.get("status") == "launched-nonpromotable-class-b-cycle1",
            "BADOPCODE hold was not launched")
    require(not (HW_OUT / "capture-timing.json").exists(),
            "BADOPCODE hold captures already exist")
    start = time.monotonic_ns()
    observations: list[dict[str, Any]] = []
    for index in range(1, 4):
        path = HW_OUT / f"held-bank0-{index}.bin"
        run_command(m65("--memsave", f"0x00000000:0x00010000={path}"))
        observations.append({
            "capture": index,
            "elapsed_ms": (time.monotonic_ns() - start) // 1_000_000,
            **bind(path, 0),
        })
        if index != 3:
            time.sleep(0.5)
    bank2 = HW_OUT / "held-bank2.bin"
    bank5 = HW_OUT / "held-bank5.bin"
    run_command(m65("--memsave", f"0x00020000:0x00030000={bank2}"))
    run_command(m65("--memsave", f"0x00050000:0x00060000={bank5}"))
    timing = {
        "format": "lisp65-c2-link50-badopcode-hold-captures-v1",
        "status": "captured-read-only-while-held",
        "reference": "first-JTAG-read-command-start",
        "bank0_captures": observations,
        "bank2": bind(bank2, 0x00020000),
        "bank5": bind(bank5, 0x00050000),
    }
    write_json(HW_OUT / "capture-timing.json", timing)
    return timing


def active_owner_analysis(bank0: bytes, bank2: bytes,
                          bank5: bytes) -> dict[str, Any]:
    """Resolve vm_codebuf through its actual (bank, ordinal) owner tuple.

    vm_codebuf is a shared cache.  A nested call may replace the dynamic
    callee with its caller before the caller subsequently fails, so comparing
    the held cache to an assumed callee is not a valid refill test.
    """
    bank_tag = bank0[VM_BUF_BANK]
    ordinal = u16(bank0, VM_BUF_OFF)
    require(bank_tag == C2_PRODUCT_CODE_BANK_TAG,
            f"held vm_codebuf owner bank tag is not C2 product: {bank_tag}")
    require(ordinal < u16(bank5, 16),
            f"held vm_codebuf owner ordinal outside C2D: {ordinal}")
    row = entry(bank5, ordinal)
    object_end = row["code_offset"] + row["code_length"]
    require(object_end <= len(bank2), "active owner outside held Bank 2")
    owner = bank2[row["code_offset"]:object_end]
    require(len(owner) >= C2_CODE_HEADER_SCALAR_BYTES,
            "active owner is shorter than the code-object scalar header")

    hdrlen = u16(bank0, VMR_HDRLEN)
    littab = u16(bank0, VMR_LITTAB)
    code = u16(bank0, VMR_CODE)
    payload_off = u16(bank0, VMR_PAYLOAD_OFF)
    payload_len = u16(bank0, VMR_PAYLOAD_LEN)
    payload_window_max = u16(bank0, VMR_PAYLOAD_WINDOW_MAX)
    win = u16(bank0, VMR_WIN)
    winlen = u16(bank0, VMR_WINLEN)
    streaming = bank0[VMR_STREAMING]
    expected_hdrlen = C2_CODE_HEADER_SCALAR_BYTES + 2 * row["literal_count"]
    require(hdrlen == expected_hdrlen and payload_off == expected_hdrlen,
            "held active-owner header geometry drift")
    require(payload_len == row["code_length"] - hdrlen,
            "held active-owner payload length drift")
    require(win <= payload_len and winlen <= payload_len - win,
            "held active-owner window outside payload")
    require(hdrlen + winlen <= VM_CODEBUF_BYTES,
            "held active-owner cache window outside vm_codebuf")

    codebuf = bank0[VM_CODEBUF:VM_CODEBUF + VM_CODEBUF_BYTES]
    scalar_header = codebuf[:C2_CODE_HEADER_SCALAR_BYTES]
    expected_scalar_header = owner[:C2_CODE_HEADER_SCALAR_BYTES]
    held_window = codebuf[hdrlen:hdrlen + winlen]
    expected_window = owner[hdrlen + win:hdrlen + win + winlen]
    scalar_header_exact = scalar_header == expected_scalar_header
    payload_window_exact = held_window == expected_window
    return {
        "bank_tag": bank_tag,
        "ordinal": ordinal,
        "c2d_entry": row,
        "object_sha256": sha_bytes(owner),
        "object_hex": owner.hex(),
        "object_name": "lcc-run" if ordinal == 171 else None,
        "header": {
            "bytes": hdrlen,
            "scalar_bytes": C2_CODE_HEADER_SCALAR_BYTES,
            "scalar_hex": scalar_header.hex(),
            "expected_scalar_hex": expected_scalar_header.hex(),
            "scalar_exact": scalar_header_exact,
            "materialized_literal_table_hex": codebuf[
                C2_CODE_HEADER_SCALAR_BYTES:hdrlen].hex(),
            "littab_pointer": f"0x{littab:04x}",
            "code_pointer": f"0x{code:04x}",
        },
        "payload": {
            "offset": payload_off,
            "length": payload_len,
            "window_max": payload_window_max,
            "window_start": win,
            "window_length": winlen,
            "streaming": streaming,
            "held_window_hex": held_window.hex(),
            "expected_window_hex": expected_window.hex(),
            "window_exact": payload_window_exact,
        },
        "active_owner_cache_exact": scalar_header_exact and payload_window_exact,
    }


def classify_owner(analysis: dict[str, Any]) -> str:
    return ("active-owner-window-byteidentical-vm-execution-state"
            if analysis["active_owner_cache_exact"]
            else "active-owner-window-differs-bank2-refill")


def classifier_selftest() -> dict[str, str]:
    require(classify_owner({"active_owner_cache_exact": True}) ==
            "active-owner-window-byteidentical-vm-execution-state",
            "exact active-owner classifier drift")
    require(classify_owner({"active_owner_cache_exact": False}) ==
            "active-owner-window-differs-bank2-refill",
            "different active-owner classifier drift")
    return {"exact-active-owner": "passed",
            "different-active-owner": "passed"}


def evaluate_hardware() -> dict[str, Any]:
    deployment = verify_hardware()
    require(not HARDWARE_RECEIPT.exists(),
            "BADOPCODE hold hardware receipt already exists")
    timing = load_json(HW_OUT / "capture-timing.json", "capture timing")
    require(timing.get("status") == "captured-read-only-while-held"
            and len(timing.get("bank0_captures", [])) == 3,
            "BADOPCODE hold capture timing drift")
    bank0_paths = [HW_OUT / f"held-bank0-{index}.bin"
                   for index in range(1, 4)]
    banks0 = [regular(path) for path in bank0_paths]
    bank2 = regular(HW_OUT / "held-bank2.bin")
    bank5 = regular(HW_OUT / "held-bank5.bin")
    require(all(len(data) == 65536 for data in [*banks0, bank2, bank5]),
            "BADOPCODE hold capture geometry drift")
    require(bank5[:5] == b"C2D\0\x06", "held C2D-v6 magic drift")
    row = entry(bank5, DYNAMIC_ORDINAL)
    require(row["image_slot"] == 6 and row["literal_count"] == 0
            and row["code_length"] == len(EXPECTED_CODE)
            and row["generation"] == 1,
            f"held dynamic entry drift: {row}")
    expected = bank2[row["code_offset"]:
                     row["code_offset"] + row["code_length"]]
    require(expected == EXPECTED_CODE,
            "held Bank-2 dynamic object differs from published truth")
    require(all(bank0[VM_STATUS] == 2 for bank0 in banks0),
            "machine is not held on VM_BADOPCODE before status clear")
    require(all(bank0[C2_READY] == 1 for bank0 in banks0),
            "C2 READY changed during first-call hold")
    require(all(u16(bank0, C2_JOURNAL_COUNT) == 0 for bank0 in banks0),
            "C2 journal became active during first-call hold")
    buffers = [bank0[VM_CODEBUF:VM_CODEBUF + VM_CODEBUF_BYTES]
               for bank0 in banks0]
    windows = [bank0[VM_STATE_START:VM_STATE_END] for bank0 in banks0]
    offsets = [bank0[VM_BUF_OFF:VM_BUF_OFF + 2] for bank0 in banks0]
    require(buffers[0] == buffers[1] == buffers[2],
            "vm_codebuf changed across held captures")
    require(windows[0] == windows[1] == windows[2],
            "VM window globals changed across held captures")
    require(offsets[0] == offsets[1] == offsets[2],
            "VM buffer owner offset changed across held captures")
    owner_analyses = [active_owner_analysis(bank0, bank2, bank5)
                      for bank0 in banks0]
    require(owner_analyses[0] == owner_analyses[1] == owner_analyses[2],
            "active vm_codebuf owner analysis changed across held captures")
    outcome = classify_owner(owner_analyses[0])
    if outcome == "active-owner-window-byteidentical-vm-execution-state":
        answer = (
            "The dynamic callee is byteidentical in Bank 2. At the held "
            "failure edge vm_codebuf is owned by ordinal 171/lcc-run, not by "
            "the callee; its scalar header and final streamed payload window "
            "are also byteidentical. The first-call VM_BADOPCODE is downstream "
            "of refill in logical cursor, dispatch or operand-stack state.")
        next_gate = (
            "Class-B cycle 2 requires a proved inner BADOPCODE cutpoint that "
            "preserves the live vm_run_inner frame/PC; a generic outer hold "
            "cannot identify the failing opcode.")
    else:
        answer = (
            "The dynamic callee is exact in Bank 2, but the cache window of "
            "its actual held owner differs from that owner's Bank-2 bytes. "
            "The active Bank-2-to-window refill is the direct failure.")
        next_gate = (
            "Class C: repair and gate the runtime Bank-2 refill dataflow; no "
            "second diagnostic cycle is needed.")
    observations = []
    for index, (path, bank0, timing_row) in enumerate(
            zip(bank0_paths, banks0, timing["bank0_captures"]), start=1):
        observations.append({
            "capture": index,
            "elapsed_ms": timing_row["elapsed_ms"],
            **bind(path, 0),
            "vm_status": bank0[VM_STATUS],
            "c2_ready": bank0[C2_READY],
            "c2_journal_count": u16(bank0, C2_JOURNAL_COUNT),
            "vm_buf_bank": bank0[VM_STATE_START],
            "vm_buf_off": f"0x{u16(bank0, VM_BUF_OFF):04x}",
            "vm_codebuf_prefix_hex": buffers[index - 1].hex(),
            "active_owner": owner_analyses[index - 1],
            "vm_window_state_hex": windows[index - 1].hex(),
        })
    value = {
        "format": "lisp65-c2-link50-badopcode-hold-cycle1-hardware-v1",
        "recorded_on": "2026-07-22",
        "status": "answered-first-call-refill-versus-dispatch",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 1, "cycle_cap": 3},
        "authorization": bind(PATCH_RECEIPT),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": load_json(MANIFEST, "patch manifest")["patch_gate"],
        "published_object": {
            "c2d_entry": row,
            "bank2_code_hex": expected.hex(),
            "bank2_capture": bind(HW_OUT / "held-bank2.bin", 0x00020000),
            "c2d_capture": bind(HW_OUT / "held-bank5.bin", 0x00050000),
        },
        "held_active_owner": owner_analyses[0],
        "observations": observations,
        "classification": outcome,
        "answer": answer,
        "next_gate": next_gate,
        "classifier_mutations": classifier_selftest(),
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "changed_bytes": 2, "hardware_runs": 1,
            "read_only_post_stop_captures": 5,
            "remaining_autonomous_cycles": 2,
            "completed_latency_attempts": 0,
        },
        "claim_limit": (
            "One non-promotable Class-B diagnostic hardware run. It is not "
            "a product link, presmoke, latency result, promotion or acceptance."),
        "rollback_line": {**bind(BASE_PRODUCT), "status": "untouched"},
        "disposition": (
            "The diagnostic identity remains isolated, read-only and "
            "permanently excluded from product and receipt-archive mixing."),
    }
    write_json(HARDWARE_RECEIPT, value)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return value


def correct_hardware_interpretation() -> dict[str, Any]:
    """Correct the owner assumption without rewriting historical evidence."""
    verify_hardware()
    require(not HARDWARE_INTERPRETATION_CORRECTION.exists(),
            "BADOPCODE hold interpretation correction already exists")
    require(sha(HARDWARE_RECEIPT) == HARDWARE_RECEIPT_SHA,
            "historical BADOPCODE hardware receipt identity drift")
    require(HARDWARE_RECEIPT.stat().st_mode & 0o222 == 0,
            "historical BADOPCODE hardware receipt is not read-only")
    historical = load_json(HARDWARE_RECEIPT, "historical hardware receipt")
    require(historical.get("classification") ==
            "different-buffer-bank2-to-vm-codebuf-refill",
            "historical mistaken classification drift")
    require(all(row.get("matches_published_object") is False
                for row in historical.get("observations", [])),
            "historical assumed-callee comparisons drift")

    timing = load_json(HW_OUT / "capture-timing.json", "capture timing")
    bank0_paths = [HW_OUT / f"held-bank0-{index}.bin"
                   for index in range(1, 4)]
    banks0 = [regular(path) for path in bank0_paths]
    bank2 = regular(HW_OUT / "held-bank2.bin")
    bank5 = regular(HW_OUT / "held-bank5.bin")
    require(all(len(data) == 65536 for data in [*banks0, bank2, bank5]),
            "BADOPCODE correction capture geometry drift")
    require(all(bank0[VM_STATUS] == 2 and bank0[C2_READY] == 1
                and u16(bank0, C2_JOURNAL_COUNT) == 0
                for bank0 in banks0),
            "BADOPCODE correction held-state drift")

    dynamic = entry(bank5, DYNAMIC_ORDINAL)
    dynamic_code = bank2[dynamic["code_offset"]:
                         dynamic["code_offset"] + dynamic["code_length"]]
    require(dynamic_code == EXPECTED_CODE,
            "published dynamic callee changed in correction replay")
    analyses = [active_owner_analysis(bank0, bank2, bank5)
                for bank0 in banks0]
    require(analyses[0] == analyses[1] == analyses[2],
            "active owner changed across correction replay captures")
    analysis = analyses[0]
    require(analysis["ordinal"] == 171,
            f"unexpected held active-owner ordinal: {analysis['ordinal']}")
    require(analysis["c2d_entry"] == {
        "ordinal": 171,
        "raw_hex": "00033b0f4c00ad000100",
        "image_slot": 0,
        "literal_count": 3,
        "code_offset": 0x0f3b,
        "code_length": 76,
        "resolution_base": 0x00ad,
        "generation": 1,
    }, f"held lcc-run entry drift: {analysis['c2d_entry']}")
    require(classify_owner(analysis) ==
            "active-owner-window-byteidentical-vm-execution-state",
            "active owner did not exonerate refill")
    owner_authority = regular(OWNER_NAME_AUTHORITY,
                              "ordinal-171 name authority")
    require(b"static ordinal 171, stdlib lcc-run" in owner_authority,
            "ordinal-171 lcc-run authority drift")

    captures = []
    for index, (path, bank0, timing_row) in enumerate(
            zip(bank0_paths, banks0, timing["bank0_captures"]), start=1):
        captures.append({
            "capture": index,
            "elapsed_ms": timing_row["elapsed_ms"],
            **bind(path, 0),
            "vm_status": bank0[VM_STATUS],
            "c2_ready": bank0[C2_READY],
            "c2_journal_count": u16(bank0, C2_JOURNAL_COUNT),
            "active_owner_ordinal": u16(bank0, VM_BUF_OFF),
            "active_owner_bank_tag": bank0[VM_BUF_BANK],
            "owner_cache_exact": analyses[index - 1][
                "active_owner_cache_exact"],
        })
    value = {
        "format": (
            "lisp65-c2-link50-badopcode-hold-cycle1-"
            "interpretation-correction-v1"),
        "recorded_on": "2026-07-22",
        "status": "corrected-active-owner-refill-exonerated",
        "promotable": False,
        "delegation": {
            "class": "A evidence-interpretation correction",
            "reason": (
                "The correction changes no product byte, diagnostic byte, "
                "capacity, compiler output, link output or hardware state."),
        },
        "preserved_historical_receipt": {
            **bind(HARDWARE_RECEIPT),
            "status": "immutable-mistaken-interpretation-preserved",
        },
        "superseded_claims": [
            {
                "field": "observations[].matches_published_object",
                "old_model": (
                    "Compare vm_codebuf to dynamic ordinal 588 regardless of "
                    "the held cache-owner tuple."),
                "replacement": (
                    "Resolve vm_codebuf through (vm_buf_bank, vm_buf_off), "
                    "then compare its scalar header and current payload window "
                    "to that owner's Bank-2 object."),
            },
            {
                "field": "classification",
                "old": "different-buffer-bank2-to-vm-codebuf-refill",
                "replacement": (
                    "active-owner-window-byteidentical-vm-execution-state"),
            },
        ],
        "capture_truth": {
            "published_dynamic_callee": {
                "ordinal": DYNAMIC_ORDINAL,
                "c2d_entry": dynamic,
                "bank2_code_hex": dynamic_code.hex(),
                "status": "byteidentical-and-separate-from-held-cache-owner",
            },
            "held_active_owner": analysis,
            "owner_name_authority": bind(OWNER_NAME_AUTHORITY),
            "captures": captures,
            "bank2": bind(HW_OUT / "held-bank2.bin", 0x00020000),
            "bank5": bind(HW_OUT / "held-bank5.bin", 0x00050000),
            "timing": bind(HW_OUT / "capture-timing.json"),
        },
        "answer": (
            "The shared vm_codebuf no longer belongs to dynamic ordinal 588 "
            "at the held edge. Its actual owner tuple is Bank tag 1, ordinal "
            "171 (lcc-run). That owner's scalar header and final streamed "
            "payload window are byteidentical to Bank 2 in all three captures. "
            "Both the callee object and the restored caller window are exact; "
            "the first-call VM_BADOPCODE is downstream in VM logical cursor, "
            "dispatch or operand-stack state."),
        "next_gate": (
            "Read-only ELF/dataflow feasibility for Class-B cycle 2: identify "
            "an inner VM_BADOPCODE cutpoint whose live frame gives a stable "
            "logical PC/opcode witness before unwind. No product change."),
        "classifier_mutations": classifier_selftest(),
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "diagnostic_bytes_changed": 0,
            "pure_read_only_evidence_replay": True,
            "remaining_class_b_cycles": 2,
            "completed_latency_attempts": 0,
        },
        "budgets": {
            "class_b_first-execution-diagnostic": "1/3 consumed",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "This correction exonerates the active Bank-2 refill and narrows "
            "the fault domain. It does not identify the exact BADOPCODE site, "
            "change a product byte, authorize a product fix, or claim latency."),
        "rollback_line": {**bind(BASE_PRODUCT), "status": "untouched"},
    }
    write_json(HARDWARE_INTERPRETATION_CORRECTION, value)
    os.chmod(HARDWARE_INTERPRETATION_CORRECTION, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "bind-first-red", "build", "check",
        "prepare-hardware", "verify-hardware", "deploy-hardware",
        "capture-hardware", "evaluate-hardware", "correct-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            verify_authority()
            classifier_selftest()
            source = regular(BASE_PRODUCT)
            exact_patch_gate(source, patched(source))
            print("c2-link50-badopcode-hold: SELFTEST PASS mutations=7")
            return 0
        if args.action == "bind-first-red":
            value = bind_first_red()
        elif args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        elif args.action == "prepare-hardware":
            value = prepare_hardware()
        elif args.action == "verify-hardware":
            value = verify_hardware()
        elif args.action == "deploy-hardware":
            value = deploy_hardware()
        elif args.action == "capture-hardware":
            value = capture_hardware()
        elif args.action == "correct-hardware":
            value = correct_hardware_interpretation()
        else:
            value = evaluate_hardware()
        print("c2-link50-badopcode-hold: " + str(value["status"]))
        return 0
    except Exception as error:
        print("c2-link50-badopcode-hold: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
