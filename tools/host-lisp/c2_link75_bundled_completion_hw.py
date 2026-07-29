#!/usr/bin/env python3
"""Record Link 75's product-first bundled completion hardware appointment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link69_hw as BASE  # noqa: E402
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


BASE_DIR = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/"
    "bundled-completion-session")
DEPLOYMENT = BASE_DIR / "product-phase-deployment.json"
DIAG_DEPLOYMENT = BASE_DIR / (
    "post-symname-hold-NONPROMOTABLE/deployment.json")
OUT = BASE_DIR / "hardware"
OBSERVATIONS = OUT / "observed-product-rows.json"
DIAG_CAPTURE = OUT / "post-symname-capture.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-completion-preparation-receipt.json")
PRODUCT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-product-hardware-receipt.json")
DIAG_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-post-symname-hardware-receipt.json")
HOLD_VMA = 0xC472
SYM_NAME_SCRATCH = 0xC1F6
SYM_NAME_SCRATCH_BYTES = 34
EXPECTED_NAME = b"intern-renderer-missing"


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def authority() -> tuple[dict[str, Any], dict[str, Any]]:
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    require(
        preparation["status"]
            == "passed-product-first-session-and-post-symname-variant-prepared"
        and deployment["status"] == "ready-product-phase-hardware-not-run"
        and deployment["product"]["sha256"]
            == preparation["product_candidate"]["product"]["sha256"]
        and len(deployment["rows"]) == 12,
        "bundled hardware authority drift")
    for row in [deployment["product"], *deployment["preloads"]]:
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"deployment artifact drift: {path}")
    return preparation, deployment


def initialize() -> dict[str, Any]:
    _, deployment = authority()
    OUT.mkdir(parents=True, exist_ok=True)
    if not OBSERVATIONS.exists():
        write(OBSERVATIONS, {
            "format":
                "lisp65-c2.2-link75-bundled-product-observations-v1",
            "status": "hardware-not-started",
            "rows": [],
        })
    value = load(OBSERVATIONS)
    require(value["rows"] == [], "fresh appointment requires zero rows")
    return {
        "status": "ready",
        "rows": len(deployment["rows"]),
        "product": deployment["product"]["sha256"],
    }


def record(row_id: str, screen: Path) -> dict[str, Any]:
    _, deployment = authority()
    if not screen.is_absolute():
        screen = ROOT / screen
    observations = load(OBSERVATIONS)
    position = len(observations["rows"])
    require(position < len(deployment["rows"]), "all rows already recorded")
    expected = deployment["rows"][position]
    require(row_id == expected["id"], "hardware row order drift")
    try:
        SCREEN.check_latest_result(
            screen, expected["form"], expected["expect"])
    except SCREEN.CheckError as error:
        raise HardwareError(
            f"row screen is not a clean expected result: "
            f"{row_id}: {error.message}") from error
    observations["rows"].append({
        **expected,
        "screen": bind(screen),
        "status": "passed-exact-screen-result",
    })
    observations["status"] = (
        "hardware-complete-pending-finalize"
        if len(observations["rows"]) == len(deployment["rows"])
        else "hardware-in-progress")
    write(OBSERVATIONS, observations)
    return {
        "status": "passed",
        "id": row_id,
        "position": position + 1,
        "total": len(deployment["rows"]),
    }


def compare_repeat(name: str) -> dict[str, Any]:
    require(name in ("first-repeat", "post-use-repeat"),
            "unknown repeat capture")
    before = OUT / f"{name}-before-bank5.bin"
    after = OUT / f"{name}-after-bank5.bin"
    require(before.is_file() and after.is_file(),
            f"repeat capture absent: {name}")
    old = before.read_bytes()
    new = after.read_bytes()
    require(len(old) == len(new) == 65536,
            f"repeat width drift: {name}")
    old_cells = BASE.require_transient_cells(old)
    new_cells = BASE.require_transient_cells(new)
    require(old_cells == new_cells,
            f"resolver cell coordinates drift: {name}")
    allowed = {
        offset + byte
        for _, offset in old_cells.values()
        for byte in range(2)
    }
    changed = [
        offset for offset, pair in enumerate(zip(old, new))
        if pair[0] != pair[1]]
    forbidden = [offset for offset in changed if offset not in allowed]
    require(not forbidden,
            f"require repeat changed contracted byte 0x{forbidden[0]:04x}")
    return {
        "id": name,
        "before": bind(before),
        "after": bind(after),
        "changed_offsets": [f"0x{x:04x}" for x in changed],
        "contracted_immutable_bytes": len(old) - len(allowed),
        "status": "passed-generation-idempotence-no-product-state-drift",
    }


def finalize_product() -> dict[str, Any]:
    preparation, deployment = authority()
    observations = load(OBSERVATIONS)
    require(
        [row["id"] for row in observations["rows"]]
            == [row["id"] for row in deployment["rows"]],
        "product row closure incomplete")
    media = ROOT / deployment["media"]["path"]
    uploaded = OUT / "uploaded-media-readback.d81"
    core = OUT / "device-core-id.bin"
    require(
        uploaded.is_file() and uploaded.read_bytes() == media.read_bytes()
        and core.is_file() and core.stat().st_size == 4,
        "media/core evidence drift")
    for item in deployment["preloads"]:
        source = ROOT / item["path"]
        readback = OUT / f"readback-{source.name}"
        require(
            readback.is_file() and readback.read_bytes() == source.read_bytes(),
            f"preload readback differs: {item['role']}")
    repeats = [
        compare_repeat("first-repeat"),
        compare_repeat("post-use-repeat"),
    ]
    receipt = {
        "format":
            "lisp65-c2.2-link75-bundled-product-hardware-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-Link75-carrier-require-defstruct-product-phase",
        "candidate": {
            "link": 75,
            "product": deployment["product"],
            "ELF": deployment["elf"],
            "media": bind(media),
        },
        "device": {
            "core_identity": {**bind(core), "hex": core.read_bytes().hex()},
            "physical_devices": 1,
        },
        "results": {
            "rows": observations["rows"],
            "require_idempotence": repeats,
            "defstruct": {
                "definition": "t",
                "constructor": "(point 3 4)",
                "accessors": [3, 4],
                "predicate": "t",
                "functional_update": "(point 3 8)",
                "canonical_place_mutation": "(point 9 4)",
            },
        },
        "evidence": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
            "uploaded_media": bind(uploaded),
        },
        "execution_accounting": {
            "hardware_sessions": 1,
            "new_product_links": 0,
            "product_byte_changes": 0,
        },
        "next_gate":
            "post-symname diagnostic variant in the same device appointment",
        "claim_limit":
            "Link75 carrier/require/defstruct product phase only; diagnostic "
            "renderer/DMA attribution remains separate.",
    }
    write(PRODUCT_RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "rows": len(observations["rows"]),
        "product": preparation["product_candidate"]["product"]["sha256"],
    }


def monitor_command(fd: int, value: bytes, wait: float = 0.02) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.3)


def read_registers(fd: int) -> dict[str, Any]:
    raw = monitor_command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw)
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == HOLD_VMA,
            f"expected post-symname hold 0x{HOLD_VMA:04x}, got 0x{pc:04x}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width)
        in enumerate(zip(names, widths), 1)
    }


def capture_diagnostic() -> dict[str, Any]:
    require(PRODUCT_RECEIPT.is_file(),
            "diagnostic may run only after green product phase")
    deployment = load(DIAG_DEPLOYMENT)
    require(
        deployment["promotable"] is False
        and deployment["status"]
            == "ready-nonpromotable-hardware-after-product-phase",
        "diagnostic deployment drift")
    require(not DIAG_CAPTURE.exists() and not DIAG_RECEIPT.exists(),
            "post-symname capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c275postsym\r")
        monitor_command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            scratch = OLD.read_block(
                fd, SYM_NAME_SCRATCH, SYM_NAME_SCRATCH_BYTES)
            live_patch = OLD.read_block(fd, HOLD_VMA, 2)
            rows.append({
                "index": index,
                "scratch_hex": scratch.hex(),
                "scratch_name":
                    scratch.split(b"\0", 1)[0].decode(
                        "ascii", errors="replace"),
                "matches_expected":
                    scratch.startswith(EXPECTED_NAME + b"\0"),
                "live_patch_hex": live_patch.hex(),
            })
    finally:
        os.close(fd)
    require(
        all(row["live_patch_hex"] == "80fe" for row in rows),
        "live post-symname hold bytes drift")
    require(all(row == {**rows[0], "index": row["index"]} for row in rows),
            "post-symname scratch changed across captures")
    correct = all(row["matches_expected"] for row in rows)
    outcome = (
        "R-renderer-consumption-symname-and-read-seam-exonerated"
        if correct else
        "S-symname-scratch-damaged-run-conditional-DMA-stage")
    capture = {
        "format":
            "lisp65-c2.2-link75-post-symname-capture-v1",
        "recorded_on": "2026-07-28",
        "status": "completed-stable-three-capture-post-symname-hold",
        "registers": registers,
        "captures": rows,
        "outcome": outcome,
        "DMA_stage_required": not correct,
        "CPU_left_stopped": True,
    }
    write(DIAG_CAPTURE, capture)
    receipt = {
        "format":
            "lisp65-c2.2-link75-post-symname-hardware-v1",
        "recorded_on": "2026-07-28",
        "status": outcome,
        "promotable": False,
        "product_phase": bind(PRODUCT_RECEIPT),
        "deployment": bind(DIAG_DEPLOYMENT),
        "capture": bind(DIAG_CAPTURE),
        "execution_accounting": {
            "device_appointments": 0,
            "additional_deployments_in_same_appointment": 1,
            "new_product_links": 0,
        },
        "next_gate": (
            "renderer fix-form review; DMA stage cancelled"
            if correct else
            "build conditional DMA stage before ending this appointment"),
        "claim_limit": (
            "Post-symname boundary only; no product fix or promotion claim."),
    }
    write(DIAG_RECEIPT, receipt)
    return {
        "status": outcome,
        "captures": len(rows),
        "DMA_stage_required": not correct,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("initialize")
    record_parser = sub.add_parser("record")
    record_parser.add_argument("--id", required=True)
    record_parser.add_argument("--screen", type=Path, required=True)
    sub.add_parser("finalize-product")
    sub.add_parser("capture-diagnostic")
    args = parser.parse_args()
    if args.action == "initialize":
        result = initialize()
    elif args.action == "record":
        result = record(args.id, args.screen)
    elif args.action == "finalize-product":
        result = finalize_product()
    else:
        result = capture_diagnostic()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        HardwareError, BASE.HardwareError, SERIAL.HoldError,
        OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link75-bundled-completion-hw: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
