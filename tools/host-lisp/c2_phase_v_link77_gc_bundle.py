#!/usr/bin/env python3
"""Prepare and adjudicate Link 77's bounded GC/feature hardware bundle."""

from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_link75_dirmiss_detail_hold_hw as DIRMISS_IO  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = ROOT / "build/post-promotion/link77-random-while"
FINAL = BASE / "final"
PRODUCT = FINAL / "lisp65-c2-substitution-linked.prg"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
SESSION = FINAL / "runtime-overlays-session-final.bin"
SESSION_JSON = FINAL / "runtime-overlays-session-final.json"
SESSION_REGION1 = FINAL / "runtime-overlays-session-final-region1.bin"
PUBLISH_LAST = FINAL / "runtime-verifier-publish-last.json"
BOUND_TABLE = FINAL / "runtime-overlay-verifier-bindings.bin"
BASE_DEPLOYMENT = BASE / "phase-v-bundled-hardware/deployment.json"
BASE_CONFIG = ROOT / "config/c2.2-link77-phase-v-bundled-hardware-session.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-phase-v-bundled-hardware-receipt.json")
HOST_LANE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-ext-dma-host-lane-receipt.json")

OUT = BASE / "gc-discriminator-bundled-session"
GC_PRODUCT = OUT / "gc-oom-entry-hold-NONPROMOTABLE.prg"
DIRMISS_PRODUCT = OUT / "post-symname-hold-NONPROMOTABLE.prg"
DIRMISS_SESSION = OUT / "post-symname-hold-NONPROMOTABLE.session.bin"
DIRMISS_BINDING = OUT / "post-symname-hold-verifier-bindings.bin"
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observations.json"
GC_PC = OUT / "gc-pc.json"
GC_RECEIPT = OUT / "gc-two-number-receipt.json"
DIRMISS_RECEIPT = OUT / "dirmiss-post-symname-receipt.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-discriminator-bundled-preparation-receipt.json")
HARDWARE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-discriminator-bundled-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-phase-v-link77-gc-bundle-hw.sh"

PRODUCT_SHA = "9e8999c0de31e306ee957f4912b7fa0baa52c55d58dfe8a933b1c02462e1faa3"
ELF_SHA = "ede88619d0e9711b8d5144495ca84f0414ee38352f882df8aadf5372504e9889"
LOAD_ADDRESS = 0x2001
SESSION_ADDRESS = 0x08000000

GC_HOLD_VMA = 0x3EC2
GC_PATCH_BEFORE = bytes.fromhex("a2 01")
GC_PATCH_AFTER = bytes.fromhex("80 fe")
GC_PRG_OFFSET = 2 + GC_HOLD_VMA - LOAD_ADDRESS
ZP_START = 0x003B
ZP_BYTES = 0x90 - ZP_START
MARKS_ADDRESS = 0xBBF0
MARKS_BYTES = 134
HOT_HEAP_ADDRESS = 0xC25D
HOT_CELLS = 48
HOT_CELL_BYTES = 5
EXT_ADDRESS = 0x00040000
EXT_CELLS = 1024
EXT_CELL_BYTES = 8
MAX_CELLS = HOT_CELLS + EXT_CELLS
GC_RUNS_ADDRESS = 0xB9EE

DIRMISS_SLOT = 47
DIRMISS_VMA = 0xC356
DIRMISS_FILE_OFFSET = 0xEA00
DIRMISS_HOLD_VMA = 0xC472
DIRMISS_PATCH_OFFSET = (
    DIRMISS_FILE_OFFSET + DIRMISS_HOLD_VMA - DIRMISS_VMA)
DIRMISS_BEFORE = bytes.fromhex("85 04")
DIRMISS_AFTER = bytes.fromhex("80 fe")
SYM_NAME_SCRATCH = 0xC1F6
SYM_NAME_BYTES = 34
EXPECTED_NAME = b"intern-renderer-missing"

PRODUCT_ROWS = (
    "random-state-width",
    "random-rejection-path",
    "random-seed-reproducible",
    "random-range",
    "irq-mask-readback",
    "while-run-stop",
    "post-run-stop-repl",
)


class BundleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BundleError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    path = path.resolve()
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == value, f"generated artifact drift: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
    )


def replace_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def u16(value: bytes | bytearray, offset: int = 0) -> int:
    return int.from_bytes(value[offset:offset + 2], "little")


def base_authority() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deployment = load(BASE_DEPLOYMENT)
    config = load(BASE_CONFIG)
    first_red = load(FIRST_RED)
    host = load(HOST_LANE)
    require(
        sha(PRODUCT) == PRODUCT_SHA
        and sha(ELF) == ELF_SHA
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and deployment["elf"]["sha256"] == ELF_SHA
        and first_red["status"] == "first-red-while-allocation-gc-oom"
        and first_red["first_red"]["id"] == "while-allocation-gc"
        and host["status"] == "passed-no-host-reproduction"
        and host["execution_witness"]["executed_cases"]
            == host["execution_witness"]["expected_cases"] == 3,
        "Link-77 GC bundle authority drift",
    )
    rows = config["rows"]
    return deployment, rows


def elf_feasibility() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True,
    )
    expected = {
        "alloc_oom": (GC_HOLD_VMA, 5),
        "marks": (MARKS_ADDRESS, MARKS_BYTES),
        "heap": (HOT_HEAP_ADDRESS, HOT_CELLS * HOT_CELL_BYTES),
        "alloc_high": (0x003B, 2),
        "gc_frozen": (0x003D, 2),
        "freelist": (0x003F, 2),
        "gc_rootsp": (0x005E, 2),
        "mem_oom": (0x008F, 1),
        "gc_runs": (GC_RUNS_ADDRESS, 2),
    }
    symbols = {}
    for name, (address, size) in expected.items():
        symbol = truth.symbol(name)
        require(
            symbol.value == address and symbol.bytes == size,
            f"Link-77 GC witness symbol drift: {name}",
        )
        symbols[name] = {
            "address": f"0x{address:04x}",
            "bytes": size,
            "section": symbol.section,
        }
    alloc = truth.symbol("alloc_oom")
    section = truth.section_bytes(alloc.section)
    section_address = truth.section(alloc.section).address
    offset = alloc.value - section_address
    require(
        section[offset:offset + 5] == bytes.fromhex("a2 01 86 8f 60"),
        "alloc_oom linked bytes drift",
    )
    return {
        "symbols": symbols,
        "alloc_oom_bytes": "a2 01 86 8f 60",
        "hold_ordering":
            "entry before mem_oom store; marks and freelist are the just-failed collection",
    }


def patch_gc_product(source: bytes) -> bytes:
    result = bytearray(source)
    require(
        result[GC_PRG_OFFSET:GC_PRG_OFFSET + 2] == GC_PATCH_BEFORE,
        "alloc_oom PRG patch bytes drift",
    )
    result[GC_PRG_OFFSET:GC_PRG_OFFSET + 2] = GC_PATCH_AFTER
    candidate = bytes(result)
    require(
        len(candidate) == len(source)
        and candidate[GC_PRG_OFFSET:GC_PRG_OFFSET + 2] == GC_PATCH_AFTER,
        "GC hold changed product geometry",
    )
    return candidate


def parsed_session(value: bytes) -> R.ParsedBank:
    build_id = R.HEADER.unpack_from(value)[8]
    return R.validate_region_images(
        value,
        SESSION_REGION1.read_bytes(),
        expected_build_id=build_id,
        expected_vma=DIRMISS_VMA,
        max_slice_bytes=1792,
        format_version=R.VERSION_V4,
        main_source_base=0x00030000,
        overflow_source_base=0x0005BD00,
    )


def patch_dirmiss_session(source: bytes) -> tuple[bytes, dict[str, Any]]:
    base = parsed_session(source)
    row = base.slices[DIRMISS_SLOT]
    require(
        row.id == DIRMISS_SLOT
        and row.vma == DIRMISS_VMA
        and row.file_offset == DIRMISS_FILE_OFFSET
        and source[
            DIRMISS_PATCH_OFFSET:DIRMISS_PATCH_OFFSET + 2
        ] == DIRMISS_BEFORE,
        "Link-77 post-symname geometry drift",
    )
    result = bytearray(source)
    result[
        DIRMISS_PATCH_OFFSET:DIRMISS_PATCH_OFFSET + 2
    ] = DIRMISS_AFTER
    record_offset = R.HEADER_SIZE + DIRMISS_SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    old = {
        "payload": fields[9],
        "record": fields[10],
        "directory": u16(result, 24),
        "header": u16(result, 26),
    }
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    fields[10] = R.crc16_ccitt_false(bytearray(R.ENTRY.pack(*fields)))
    require(fields[10] != 0, "derived DIRMISS record CRC is zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)
    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26, R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    candidate = bytes(result)
    verified = parsed_session(candidate)
    return candidate, {
        "record_offset": record_offset,
        "old": old,
        "new": {
            "payload": verified.slices[DIRMISS_SLOT].crc16,
            "record": verified.slices[DIRMISS_SLOT].record_crc16,
            "directory": verified.directory_crc16,
            "header": verified.header_crc16,
            "family": R.crc16_ccitt_false(candidate),
        },
    }


def patch_dirmiss_product(
        source: bytes, family_crc: int
) -> tuple[bytes, bytes, dict[str, Any]]:
    publish = load(PUBLISH_LAST)
    binding = BOUND_TABLE.read_bytes()
    start = int(publish["file_offset"])
    require(
        publish["bytes"] == len(binding) == 40
        and source[start:start + len(binding)] == binding
        and u16(binding, 38) == R.crc16_ccitt_false(SESSION.read_bytes()),
        "Link-77 verifier binding geometry drift",
    )
    candidate_binding = bytearray(binding)
    struct.pack_into("<H", candidate_binding, 38, family_crc)
    result = bytearray(source)
    result[start:start + len(binding)] = candidate_binding
    return bytes(result), bytes(candidate_binding), {
        "file_offset": start,
        "session_crc_file_offset": start + 38,
        "old_session_crc16": u16(binding, 38),
        "new_session_crc16": family_crc,
    }


def dirmiss_mutations(
        session: bytes, product: bytes, identity: dict[str, Any],
        binding: dict[str, Any],
) -> list[str]:
    rejected = []
    record = int(identity["record_offset"])
    for label, offset, old in (
        ("stale-payload-crc", record + 20, identity["old"]["payload"]),
        ("stale-record-crc", record + 22, identity["old"]["record"]),
        ("stale-directory-crc", 24, identity["old"]["directory"]),
        ("stale-header-crc", 26, identity["old"]["header"]),
    ):
        mutant = bytearray(session)
        struct.pack_into("<H", mutant, offset, old)
        try:
            parsed_session(bytes(mutant))
        except R.OverlayBankError:
            rejected.append(label)
        else:
            raise BundleError(f"DIRMISS identity mutation survived: {label}")
    opcode = bytearray(session)
    opcode[DIRMISS_PATCH_OFFSET:DIRMISS_PATCH_OFFSET + 2] = DIRMISS_BEFORE
    try:
        parsed_session(bytes(opcode))
    except R.OverlayBankError:
        rejected.append("restored-opcode-with-stale-derived-identity")
    else:
        raise BundleError("DIRMISS opcode mutation survived")
    stale = bytearray(product)
    struct.pack_into(
        "<H", stale, int(binding["session_crc_file_offset"]),
        int(binding["old_session_crc16"]))
    require(stale != product, "stale product binding mutation ineffective")
    rejected.append("stale-product-session-binding")
    return rejected


def replace_product(
        deployment: dict[str, Any], path: Path, promotable: bool
) -> dict[str, Any]:
    value = deepcopy(deployment)
    value["product"] = {
        **bind(path, LOAD_ADDRESS),
        "role": "c2-resident-prg",
    }
    value["promotable"] = promotable
    return value


def replace_session(deployment: dict[str, Any], path: Path) -> dict[str, Any]:
    replaced = 0
    rows = []
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {**bind(path, SESSION_ADDRESS), "role": copy["role"]}
            replaced += 1
        rows.append(copy)
    require(replaced == 1, "session-family replacement is not unique")
    deployment["preloads"] = rows
    return deployment


def prepare() -> None:
    require(
        not PREPARATION.exists() and not HARDWARE_RECEIPT.exists(),
        "Link-77 GC bundle preparation is one-shot",
    )
    base, rows = base_authority()
    feasibility = elf_feasibility()
    source_product = PRODUCT.read_bytes()
    gc_product = patch_gc_product(source_product)
    dirmiss_session, session_identity = patch_dirmiss_session(
        SESSION.read_bytes())
    dirmiss_product, binding_bytes, binding = patch_dirmiss_product(
        source_product, session_identity["new"]["family"])
    mutations = dirmiss_mutations(
        dirmiss_session, dirmiss_product, session_identity, binding)

    write_bytes(GC_PRODUCT, gc_product)
    write_bytes(DIRMISS_SESSION, dirmiss_session)
    write_bytes(DIRMISS_PRODUCT, dirmiss_product)
    write_bytes(DIRMISS_BINDING, binding_bytes)

    by_id = {row["id"]: row for row in rows}
    gc = replace_product(base, GC_PRODUCT, False)
    gc["status"] = "ready-nonpromotable-gc-oom-entry-hold"
    gc["test"] = {
        **by_id["while-allocation-gc"],
        "expected": "self-loop at alloc_oom entry",
        "captures": 3,
    }
    product = deepcopy(base)
    product["status"] = "ready-original-Link77-independent-rows"
    product["promotable"] = True
    product["rows"] = [by_id[name] for name in PRODUCT_ROWS]
    dirmiss = replace_session(
        replace_product(base, DIRMISS_PRODUCT, False),
        DIRMISS_SESSION,
    )
    dirmiss["status"] = "ready-nonpromotable-post-symname-hold"
    dirmiss["test"] = {
        "form": by_id["dirmiss-full-name"]["form"],
        "expected": "self-loop at post-symname return before renderer",
        "captures": 3,
    }
    value = {
        "format": "lisp65-c2.2-link77-gc-bundled-deployment-v1",
        "status": "ready-one-physical-session-three-controlled-deployments",
        "phases": {
            "gc_discriminator": gc,
            "independent_product_rows": product,
            "dirmiss_post_symname": dirmiss,
        },
        "policy": {
            "physical_device_sessions": 1,
            "dependency_scoped_first_red": True,
            "terminal": ["crash", "red-frame", "undefined-machine-state"],
            "row_local": [
                "GC discriminator classification",
                "random result",
                "IRQ readback result",
                "RUN/STOP result",
                "DIRMISS post-symname classification",
            ],
            "no_per_row_approval": True,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(DEPLOYMENT, value)
    write_json(OBSERVATIONS, {
        "format": "lisp65-c2.2-link77-gc-bundle-observations-v1",
        "status": "hardware-not-started",
        "product_rows": [],
    })
    write_json(PREPARATION, {
        "format": "lisp65-c2.2-link77-gc-bundle-preparation-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-ready-one-bundled-session-hardware-not-run",
        "promotable": False,
        "product_identity": {
            "product": bind(PRODUCT, LOAD_ADDRESS),
            "ELF": bind(ELF),
        },
        "gc_discriminator": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "patch": {
                "symbol": "alloc_oom",
                "runtime_address": f"0x{GC_HOLD_VMA:04x}",
                "PRG_file_offset": GC_PRG_OFFSET,
                "before": GC_PATCH_BEFORE.hex(),
                "after": GC_PATCH_AFTER.hex(),
                "size_delta": 0,
                "ordering": "before mem_oom=1; after failing GC",
            },
            "capture": {
                "marks": [MARKS_ADDRESS, MARKS_BYTES],
                "freelist": [0x003F, 2],
                "watermarks": [0x003B, 4],
                "hot_heap": [HOT_HEAP_ADDRESS, HOT_CELLS * HOT_CELL_BYTES],
                "extended_heap": [EXT_ADDRESS, EXT_CELLS * EXT_CELL_BYTES],
                "time_separated": [0, 1, 5],
            },
            "ELF_feasibility": feasibility,
        },
        "dirmiss": {
            "product": bind(DIRMISS_PRODUCT, LOAD_ADDRESS),
            "session": bind(DIRMISS_SESSION, SESSION_ADDRESS),
            "binding": bind(DIRMISS_BINDING),
            "patch": {
                "slot": DIRMISS_SLOT,
                "runtime_address": f"0x{DIRMISS_HOLD_VMA:04x}",
                "session_file_offset": DIRMISS_PATCH_OFFSET,
                "before": DIRMISS_BEFORE.hex(),
                "after": DIRMISS_AFTER.hex(),
                "size_delta": 0,
            },
            "mutations_rejected": mutations,
        },
        "deployment": bind(DEPLOYMENT),
        "authority": {
            "prior_hardware_First_Red": bind(FIRST_RED),
            "host_EXT_DMA_lane": bind(HOST_LANE),
            "base_deployment": bind(BASE_DEPLOYMENT),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(HARDWARE_SCRIPT),
        },
        "execution_witness": {
            "expected_cases": 8,
            "executed_cases": 8,
            "cases": [
                "gc-linked-hold-edge",
                "dirmiss-derived-session-identity",
                *[f"dirmiss-mutation-{name}" for name in mutations],
            ],
            "positive": True,
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "diagnostic_product_size_delta": 0,
        },
        "claim_limit": (
            "Preparation only. Both diagnostic identities are nonpromotable; "
            "no target GC, random, RUN/STOP, IRQ or DIRMISS claim exists yet."
        ),
    })
    verify()
    print(
        "c2-phase-v-link77-gc-bundle: PREPARE PASS "
        f"gc={sha_bytes(gc_product)} dirmiss={sha_bytes(dirmiss_product)} "
        f"mutations={len(mutations)} hardware=not-run")


def verify() -> None:
    base_authority()
    feasibility = elf_feasibility()
    deployment = load(DEPLOYMENT)
    receipt = load(PREPARATION)
    require(
        deployment["status"]
            == "ready-one-physical-session-three-controlled-deployments"
        and receipt["status"]
            == "passed-ready-one-bundled-session-hardware-not-run"
        and feasibility == receipt["gc_discriminator"]["ELF_feasibility"]
        and receipt["authority"]["driver"] == bind(Path(__file__))
        and receipt["authority"]["hardware_script"] == bind(HARDWARE_SCRIPT)
        and receipt["execution_witness"]["executed_cases"]
            == receipt["execution_witness"]["expected_cases"] == 8
        and GC_PRODUCT.read_bytes() == patch_gc_product(PRODUCT.read_bytes()),
        "Link-77 GC bundle preparation drift",
    )
    session, identity = patch_dirmiss_session(SESSION.read_bytes())
    product, binding_bytes, binding = patch_dirmiss_product(
        PRODUCT.read_bytes(), identity["new"]["family"])
    require(
        DIRMISS_SESSION.read_bytes() == session
        and DIRMISS_PRODUCT.read_bytes() == product
        and DIRMISS_BINDING.read_bytes() == binding_bytes
        and len(dirmiss_mutations(session, product, identity, binding)) == 6,
        "Link-77 DIRMISS diagnostic drift",
    )
    for phase in deployment["phases"].values():
        for row in [phase["product"], *phase["preloads"]]:
            path = ROOT / row["path"]
            require(
                path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"deployment artifact drift: {path}",
            )
    print("c2-phase-v-link77-gc-bundle: VERIFY PASS")


def refresh_authority() -> None:
    """Rebind preparation tooling only; diagnostic/product bytes stay fixed."""
    receipt = load(PREPARATION)
    require(
        receipt["status"]
            == "passed-ready-one-bundled-session-hardware-not-run"
        and receipt["product_identity"]["product"] == bind(PRODUCT, LOAD_ADDRESS)
        and receipt["gc_discriminator"]["identity"] == bind(
            GC_PRODUCT, LOAD_ADDRESS)
        and receipt["dirmiss"]["product"] == bind(
            DIRMISS_PRODUCT, LOAD_ADDRESS)
        and receipt["dirmiss"]["session"] == bind(
            DIRMISS_SESSION, SESSION_ADDRESS),
        "preparation authority refresh would cross an artifact boundary",
    )
    mutations = receipt["dirmiss"]["mutations_rejected"]
    require(len(mutations) == 6, "DIRMISS mutation inventory drift")
    receipt["authority"]["driver"] = bind(Path(__file__))
    receipt["authority"]["hardware_script"] = bind(HARDWARE_SCRIPT)
    receipt["execution_witness"] = {
        "expected_cases": 8,
        "executed_cases": 8,
        "cases": [
            "gc-linked-hold-edge",
            "dirmiss-derived-session-identity",
            *[f"dirmiss-mutation-{name}" for name in mutations],
        ],
        "positive": True,
    }
    receipt["tool_authority_rebind"] = {
        "reason":
            "dependency-scoped row recording and positive witness were added "
            "after the byteidentical diagnostic artifacts were prepared",
        "product_or_diagnostic_byte_delta": 0,
    }
    replace_json(PREPARATION, receipt)
    verify()
    print("c2-phase-v-link77-gc-bundle: AUTHORITY REFRESH PASS delta=0")


def monitor_command(fd: int, value: bytes, wait: float = 0.03) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def read_registers(fd: int, expected_pc: int) -> dict[str, str]:
    raw = monitor_command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw,
    )
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == expected_pc, f"expected PC 0x{expected_pc:04x}, got 0x{pc:04x}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width) in enumerate(zip(names, widths), 1)
    }


def capture_gc_pc() -> None:
    verify()
    require(not GC_PC.exists(), "GC PC capture is one-shot")
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c277gc\r")
        monitor_command(fd, b"t1", 0.05)
        registers = read_registers(fd, GC_HOLD_VMA)
        patch = DIRMISS_IO.read_block(fd, GC_HOLD_VMA, 2)
    finally:
        os.close(fd)
    require(patch == GC_PATCH_AFTER, "live alloc_oom hold bytes drift")
    write_json(GC_PC, {
        "format": "lisp65-c2.2-link77-gc-hold-pc-v1",
        "status": "stopped-at-alloc-oom-entry",
        "registers": registers,
        "live_patch": patch.hex(),
        "CPU_left_stopped": True,
    })
    print("c2-phase-v-link77-gc-bundle: GC PC PASS 0x3ec2")


def capture_values(index: int) -> dict[str, bytes]:
    directory = OUT / f"gc-capture-{index}"
    names = {
        "zp": ZP_BYTES,
        "marks": MARKS_BYTES,
        "hot-heap": HOT_CELLS * HOT_CELL_BYTES,
        "ext-heap": EXT_CELLS * EXT_CELL_BYTES,
        "gc-runs": 2,
        "live-patch": 2,
    }
    values = {}
    for name, size in names.items():
        path = directory / f"{name}.bin"
        require(path.is_file() and path.stat().st_size == size,
                f"GC capture geometry drift: {path}")
        values[name] = path.read_bytes()
    return values


def follow_freelist(
        head: int, hot: bytes, ext: bytes
) -> tuple[list[int], str | None]:
    chain = []
    seen = set()
    current = head
    error = None
    while current != 0:
        if current & 1:
            error = f"tagged/immediate freelist word 0x{current:04x}"
            break
        index = current >> 1
        if not 0 < index < MAX_CELLS:
            error = f"out-of-range freelist cell {index}"
            break
        if index in seen:
            error = f"freelist cycle at cell {index}"
            break
        seen.add(index)
        chain.append(index)
        if index < HOT_CELLS:
            at = index * HOT_CELL_BYTES + 1
            current = u16(hot, at)
        else:
            at = (index - HOT_CELLS) * EXT_CELL_BYTES + 2
            current = u16(ext, at)
    return chain, error


def evaluate_gc() -> None:
    require(GC_PC.is_file() and not GC_RECEIPT.exists(),
            "GC evaluation requires one fresh PC capture")
    captures = [capture_values(index) for index in range(1, 4)]
    require(
        all(
            captures[0][name] == captures[1][name] == captures[2][name]
            for name in captures[0]
        ),
        "GC witnesses changed across time-separated captures",
    )
    value = captures[0]
    zp = value["zp"]
    alloc_high = u16(zp, 0x003B - ZP_START)
    frozen = u16(zp, 0x003D - ZP_START)
    freelist = u16(zp, 0x003F - ZP_START)
    rootsp = u16(zp, 0x005E - ZP_START)
    mem_oom = zp[0x008F - ZP_START]
    marked_indices = [
        index for index in range(1, MAX_CELLS)
        if value["marks"][index >> 3] & (1 << (index & 7))
    ]
    chain, chain_error = follow_freelist(
        freelist, value["hot-heap"], value["ext-heap"])
    runtime_ext_floor = max(frozen, HOT_CELLS - 1)
    eligible = set(range(1, HOT_CELLS))
    eligible.update(range(runtime_ext_floor + 1, alloc_high + 1))
    eligible_unmarked = sorted(eligible.difference(marked_indices))
    if len(chain) == 0 and eligible_unmarked:
        classification = "sweep-or-freelist-return-failure"
    elif len(chain) == 0:
        classification = "mark-root-retention-or-true-live-set-exhaustion"
    else:
        classification = "unexpected-alloc-oom-with-nonempty-freelist"
    receipt = {
        "format": "lisp65-c2.2-link77-gc-two-number-hardware-v1",
        "recorded_on": "2026-07-29",
        "status": f"completed-{classification}",
        "promotable": False,
        "answer": {
            "marked_cells": len(marked_indices),
            "cells_actually_returned_to_freelist": len(chain),
            "classification": classification,
        },
        "supporting_geometry": {
            "alloc_high": alloc_high,
            "gc_frozen": frozen,
            "gc_rootsp": rootsp,
            "mem_oom_at_hold": mem_oom,
            "gc_runs": u16(value["gc-runs"]),
            "freelist_head": f"0x{freelist:04x}",
            "freelist_error": chain_error,
            "eligible_sweep_cells": len(eligible),
            "eligible_unmarked_cells": len(eligible_unmarked),
            "first_eligible_unmarked": eligible_unmarked[:16],
        },
        "capture": {
            "PC": load(GC_PC),
            "time_separated_captures": [
                dict(
                    {"index": index},
                    **{
                        name: bind(
                            OUT / f"gc-capture-{index}/{name}.bin")
                        for name in captures[0]
                    },
                )
                for index in range(1, 4)
            ],
            "stable_across_three": True,
        },
        "authority": {
            "preparation": bind(PREPARATION),
            "host_lane": bind(HOST_LANE),
        },
        "diagnostic_lifecycle": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discard-after-bundled-session",
        },
        "claim_limit": (
            "The two counts describe the collection frozen at alloc_oom entry. "
            "They do not alter or promote Link 77."
        ),
    }
    write_json(GC_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["status"] = "gc-complete-awaiting-independent-product-rows"
    observations["gc"] = {
        "marked": len(marked_indices),
        "returned": len(chain),
        "classification": classification,
        "receipt": bind(GC_RECEIPT),
    }
    replace_json(OBSERVATIONS, observations)
    print(
        "c2-phase-v-link77-gc-bundle: GC COMPLETE "
        f"marked={len(marked_indices)} returned={len(chain)} "
        f"class={classification}")


def record_gc_nonreproduction(screen: Path, image: Path) -> None:
    """Bind the clean success outcome when the alloc_oom hold is not reached."""
    require(
        not GC_PC.exists() and not GC_RECEIPT.exists(),
        "GC non-reproduction requires no hold capture or prior receipt",
    )
    SCREEN.check_fail_closed_frame(image)
    expected = load(DEPLOYMENT)["phases"]["gc_discriminator"]["test"]
    SCREEN.check_latest_result(
        screen, expected["form"], expected["expected_result"])
    receipt = {
        "format": "lisp65-c2.2-link77-gc-two-number-hardware-v1",
        "recorded_on": "2026-07-29",
        "status": "completed-oom-not-reproduced",
        "promotable": False,
        "answer": {
            "marked_cells": None,
            "cells_actually_returned_to_freelist": None,
            "classification": "oom-not-reproduced",
        },
        "observation": {
            "result": expected["expected_result"],
            "screen": bind(screen),
            "image": bind(image),
            "alloc_oom_hold_reached": False,
        },
        "authority": {
            "preparation": bind(PREPARATION),
            "host_lane": bind(HOST_LANE),
        },
        "diagnostic_lifecycle": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discard-after-bundled-session",
        },
        "claim_limit": (
            "The fresh diagnostic boot completed the 1200-allocation workload "
            "with result 600 and never reached alloc_oom. Therefore this run "
            "does not distinguish marked from returned cells and authorizes "
            "no GC product change."
        ),
    }
    write_json(GC_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["status"] = "gc-nonreproduction-awaiting-independent-product-rows"
    observations["gc"] = {
        "marked": None,
        "returned": None,
        "classification": "oom-not-reproduced",
        "receipt": bind(GC_RECEIPT),
    }
    replace_json(OBSERVATIONS, observations)
    print("c2-phase-v-link77-gc-bundle: GC COMPLETE oom-not-reproduced")


def row(row_id: str) -> dict[str, Any]:
    _, rows = base_authority()
    return next(value for value in rows if value["id"] == row_id)


def record_product(row_id: str, screen: Path, image: Path) -> None:
    require(row_id in PRODUCT_ROWS and row_id != "while-run-stop",
            "record-product row is not a normal bundled row")
    expected = row(row_id)
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(screen, expected["form"], expected["expected_result"])
    observations = load(OBSERVATIONS)
    require(
        row_id not in [value["id"] for value in observations["product_rows"]],
        f"product row already recorded: {row_id}",
    )
    observations["product_rows"].append({
        "id": row_id,
        "result": expected["expected_result"],
        "screen": bind(screen),
        "image": bind(image),
        "status": "passed",
    })
    replace_json(OBSERVATIONS, observations)
    print(f"c2-phase-v-link77-gc-bundle: ROW PASS {row_id}")


def record_product_red(
        row_id: str, screen: Path, image: Path, detail: str) -> None:
    require(row_id in PRODUCT_ROWS, "unknown row-local First Red")
    SCREEN.check_fail_closed_frame(image)
    observations = load(OBSERVATIONS)
    require(
        row_id not in [value["id"] for value in observations["product_rows"]],
        f"product row already recorded: {row_id}",
    )
    observations["product_rows"].append({
        "id": row_id,
        "status": "row-local-first-red",
        "detail": detail,
        "screen": bind(screen),
        "image": bind(image),
    })
    replace_json(OBSERVATIONS, observations)
    print(
        f"c2-phase-v-link77-gc-bundle: ROW-LOCAL RED {row_id}: {detail}")


def record_run_stop(screen: Path, image: Path) -> None:
    SCREEN.check_fail_closed_frame(image)
    raw = screen.read_text(errors="replace").lower()
    require(
        "*** stopped (run/stop)" in raw
        and re.search(r"(?m)^\s*lisp65>\s*$", raw),
        "RUN/STOP did not return to a live prompt",
    )
    observations = load(OBSERVATIONS)
    observations["product_rows"].append({
        "id": "while-run-stop",
        "result": "*** stopped (run/stop)",
        "screen": bind(screen),
        "image": bind(image),
        "status": "passed",
    })
    replace_json(OBSERVATIONS, observations)
    print("c2-phase-v-link77-gc-bundle: ROW PASS while-run-stop")


def capture_dirmiss() -> None:
    require(not DIRMISS_RECEIPT.exists(), "DIRMISS capture is one-shot")
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c277post\r")
        monitor_command(fd, b"t1", 0.05)
        registers = read_registers(fd, DIRMISS_HOLD_VMA)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            scratch = DIRMISS_IO.read_block(fd, SYM_NAME_SCRATCH, SYM_NAME_BYTES)
            patch = DIRMISS_IO.read_block(fd, DIRMISS_HOLD_VMA, 2)
            rows.append({
                "index": index,
                "scratch_hex": scratch.hex(),
                "scratch_name": scratch.split(b"\0", 1)[0].decode(
                    "ascii", errors="replace"),
                "matches_expected": scratch.startswith(EXPECTED_NAME + b"\0"),
                "live_patch": patch.hex(),
            })
    finally:
        os.close(fd)
    require(
        all(value["live_patch"] == DIRMISS_AFTER.hex() for value in rows)
        and all(
            {key: value for key, value in row.items() if key != "index"}
            == {key: value for key, value in rows[0].items() if key != "index"}
            for row in rows
        ),
        "DIRMISS post-symname witness drift",
    )
    correct = all(value["matches_expected"] for value in rows)
    outcome = (
        "renderer-consumption-attributed-symname-and-read-seam-exonerated"
        if correct else
        "post-symname-scratch-damaged-symbol-read-seam-remains"
    )
    write_json(DIRMISS_RECEIPT, {
        "format": "lisp65-c2.2-link77-post-symname-hardware-v1",
        "recorded_on": "2026-07-29",
        "status": outcome,
        "promotable": False,
        "registers": registers,
        "captures": rows,
        "answer": {
            "scratch_correct_after_symname": correct,
            "outcome": outcome,
        },
        "identity": {
            "product": bind(DIRMISS_PRODUCT, LOAD_ADDRESS),
            "session": bind(DIRMISS_SESSION, SESSION_ADDRESS),
        },
        "diagnostic_lifecycle": {
            "eligible_for_promotion": False,
            "state": "discarded-after-capture",
        },
    })
    observations = load(OBSERVATIONS)
    observations["dirmiss"] = {
        "outcome": outcome,
        "receipt": bind(DIRMISS_RECEIPT),
    }
    observations["status"] = "all-bundled-rows-captured-awaiting-finalize"
    replace_json(OBSERVATIONS, observations)
    print(
        "c2-phase-v-link77-gc-bundle: DIRMISS COMPLETE "
        f"scratch_correct={str(correct).lower()}")


def finalize() -> None:
    verify()
    observations = load(OBSERVATIONS)
    ids = [value["id"] for value in observations["product_rows"]]
    require(
        GC_RECEIPT.is_file() and DIRMISS_RECEIPT.is_file()
        and set(ids).issubset(set(PRODUCT_ROWS))
        and set(PRODUCT_ROWS).difference(ids).issubset({"post-run-stop-repl"}),
        "bundled hardware evidence incomplete",
    )
    row_reds = [
        value for value in observations["product_rows"]
        if value["status"] != "passed"]
    receipt = {
        "format": "lisp65-c2.2-link77-gc-bundled-hardware-v1",
        "recorded_on": "2026-07-29",
        "status": (
            "completed-GC-random-RUNSTOP-IRQ-DIRMISS-bundle"
            if not row_reds else
            "completed-bundle-with-row-local-First-Red"
        ),
        "product": bind(PRODUCT, LOAD_ADDRESS),
        "GC": load(GC_RECEIPT),
        "product_rows": observations["product_rows"],
        "row_local_first_reds": row_reds,
        "DIRMISS": load(DIRMISS_RECEIPT),
        "authority": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "controlled_deployments": 3,
            "product_links": 0,
            "promotable_diagnostic_identities": 0,
        },
        "claim_limit": (
            "Claims only the listed GC discriminator, independent product "
            "rows, and post-symname diagnostic result."
        ),
    }
    write_json(HARDWARE_RECEIPT, receipt)
    observations["status"] = "completed-and-receipted"
    observations["receipt"] = bind(HARDWARE_RECEIPT)
    replace_json(OBSERVATIONS, observations)
    print("c2-phase-v-link77-gc-bundle: FINAL PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare", "refresh-authority", "verify",
            "capture-gc-pc", "evaluate-gc", "record-gc-nonreproduction",
            "record-product", "record-product-red", "record-run-stop",
            "capture-dirmiss", "finalize",
        ),
    )
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--detail")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "refresh-authority":
        refresh_authority()
    elif args.action == "verify":
        verify()
    elif args.action == "capture-gc-pc":
        capture_gc_pc()
    elif args.action == "evaluate-gc":
        evaluate_gc()
    elif args.action == "record-gc-nonreproduction":
        require(args.screen and args.image,
                "record-gc-nonreproduction requires --screen and --image")
        record_gc_nonreproduction(args.screen, args.image)
    elif args.action == "record-product":
        require(args.id is not None and args.screen and args.image,
                "record-product requires --id, --screen and --image")
        record_product(args.id, args.screen, args.image)
    elif args.action == "record-product-red":
        require(
            args.id is not None and args.screen and args.image and args.detail,
            "record-product-red requires --id, --screen, --image and --detail")
        record_product_red(
            args.id, args.screen, args.image, str(args.detail))
    elif args.action == "record-run-stop":
        require(args.screen and args.image,
                "record-run-stop requires --screen and --image")
        record_run_stop(args.screen, args.image)
    elif args.action == "capture-dirmiss":
        capture_dirmiss()
    else:
        finalize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BundleError, R.OverlayBankError, SCREEN.CheckError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-phase-v-link77-gc-bundle: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
