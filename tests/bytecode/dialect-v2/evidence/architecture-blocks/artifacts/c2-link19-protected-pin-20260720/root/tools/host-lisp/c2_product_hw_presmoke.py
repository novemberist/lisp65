#!/usr/bin/env python3
"""Prepare and verify the receipt-less Link-19 product hardware pre-smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/product-link-19"
SUBSTITUTION = ROOT / "build/c2.2/substitution"
DEFAULT_OUT = ROOT / "build/c2.2/hardware-presmoke-link19"
PIN_RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-product-substitution-link-19-pin-receipt.json")
REPLAY_RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.2-product-substitution-link-19-replay-receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"

DESCRIPTOR_MAGIC = b"L65O"
DESCRIPTOR_VERSION = 1
DESCRIPTOR_BYTES = 18
BOOT_OVERLAY_STAGE = 0x00058500
BOOT_FAMILY_STAGE = 0x08200000
SESSION_FAMILY_STAGE = 0x08000000
SHELF_STAGE = 0x08100000
C2D_STAGE = 0x00050000
KERNAL_WINDOW_STAGE = 0x087FE000
PHYSICAL_LIMIT = 0x10000000


class PreSmokeError(RuntimeError):
    pass


def regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PreSmokeError(f"missing {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PreSmokeError(f"{label} must be a regular, symlink-free file: {path}")
    return path.read_bytes()


def sha(path: Path) -> str:
    return hashlib.sha256(regular(path, "hash input")).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreSmokeError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreSmokeError(f"{label} root must be an object")
    return value


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        raise PreSmokeError(f"command failed: {' '.join(args)}: {detail.strip()}") from exc
    if result.stderr:
        raise PreSmokeError(f"unexpected command diagnostic: {result.stderr.strip()}")
    return result.stdout


def symbols(elf: Path) -> dict[str, int]:
    wanted = {
        "__lisp65_workbench_overlay_start",
        "__lisp65_workbench_overlay_end",
        "vm_workbench_boot_overlay_entry",
    }
    result: dict[str, int] = {}
    for line in run([str(NM), "--defined-only", str(elf)]).splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[-1] in wanted:
            if fields[-1] in result:
                raise PreSmokeError(f"duplicate ELF symbol: {fields[-1]}")
            result[fields[-1]] = int(fields[0], 16)
    if set(result) != wanted:
        raise PreSmokeError(f"missing ELF symbols: {sorted(wanted - set(result))}")
    return result


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xFFFF
                     if value & 0x8000 else (value << 1) & 0xFFFF)
    return value


def binding(path: Path, address: int) -> dict[str, Any]:
    data = regular(path, "deployment artifact")
    if not 0 <= address < PHYSICAL_LIMIT or address + len(data) > PHYSICAL_LIMIT:
        raise PreSmokeError(f"deployment span outside physical address space: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "address": f"0x{address:08x}",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def assert_binding(path: Path, expected: dict[str, Any], label: str) -> None:
    data = regular(path, label)
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise PreSmokeError(f"{label} differs from its pinned binding: {path}")


def verify_source_bindings() -> dict[str, Path]:
    pin = load_json(PIN_RECEIPT, "Link-19 pin receipt")
    replay = load_json(REPLAY_RECEIPT, "Link-19 replay receipt")
    if pin.get("status") != "pinned-structural-hardware-not-run":
        raise PreSmokeError("Link-19 pin is not structurally passed and hardware-not-run")
    if replay.get("status") != "passed-structural-hardware-not-run":
        raise PreSmokeError("Link-19 replay is not structurally passed and hardware-not-run")
    if pin.get("link_number") != 19 or replay.get("link_number") != 19:
        raise PreSmokeError("Link-19 receipt number drift")
    if not str(pin.get("inheritance", "")).startswith("none;"):
        raise PreSmokeError("Link-19 pin unexpectedly inherits an earlier green claim")
    if replay.get("new_product_links") != 0:
        raise PreSmokeError("Link-19 replay unexpectedly performed a product link")
    if replay.get("remaining_claims", {}).get("hardware") != "not-run":
        raise PreSmokeError("Link-19 hardware claim is no longer the expected not-run state")
    if sha(PIN_RECEIPT) != replay.get("pin_receipt", {}).get("sha256"):
        raise PreSmokeError("Link-19 pin-receipt binding drift")
    evidence = pin.get("evidence_objects", [])
    if pin.get("evidence_object_count") != 43 or len(evidence) != 43:
        raise PreSmokeError("Link-19 evidence-object count drift")
    pinned: dict[str, dict[str, Any]] = {}
    for item in evidence:
        relative = item.get("path")
        if not isinstance(relative, str) or relative in pinned:
            raise PreSmokeError("invalid or duplicate Link-19 evidence path")
        pinned[relative] = item
        assert_binding(ROOT / relative, item, f"Link-19 pinned object {relative}")
    if replay.get("pinned_evidence_objects_verified") != 43:
        raise PreSmokeError("Link-19 replay did not verify all pinned objects")
    if replay.get("pinned_evidence_drift") != 0:
        raise PreSmokeError("Link-19 replay recorded pinned evidence drift")

    paths = {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family": LINK / "runtime-overlays-session-final.bin",
        "shelf": SUBSTITUTION / "product-shelf-v4-direct.bin",
        "c2d": SUBSTITUTION / "initial.c2d-v3.bin",
        "contract": LINK / "resolved-profile.txt",
        "stage_header": LINK / "stage-config.h",
    }
    product = replay.get("product_identity", {})
    if sha(paths["product"]) != product.get("sha256"):
        raise PreSmokeError("Link-19 product SHA drift")
    for name, path in paths.items():
        relative = str(path.relative_to(ROOT))
        if relative not in pinned:
            raise PreSmokeError(f"deployment source is absent from Link-19 pin: {name}")
        assert_binding(path, pinned[relative], name)
    regular(paths["contract"], "resolved profile")
    regular(paths["stage_header"], "stage header")
    return paths


def prepare(out: Path) -> None:
    if out.exists():
        raise PreSmokeError(f"pre-smoke output must be fresh: {out}")
    paths = verify_source_bindings()
    out.mkdir(parents=True)
    elf_symbols = symbols(paths["elf"])
    start = elf_symbols["__lisp65_workbench_overlay_start"]
    end = elf_symbols["__lisp65_workbench_overlay_end"]
    entry = elf_symbols["vm_workbench_boot_overlay_entry"]
    if not 0 < start <= entry < end <= 0x10000:
        raise PreSmokeError("boot-overlay ELF geometry is invalid")

    overlay = out / "boot-overlay.raw.bin"
    # llvm-objcopy rewrites its input in place when no explicit output object
    # is given, even for --dump-section.  Work only on a disposable copy and
    # name an explicit normalized output so the SHA-bound evidence ELF is
    # never an objcopy destination.
    scratch_input = out / "elf-section-source.copy"
    scratch_output = out / "elf-section-normalized.discard"
    shutil.copyfile(paths["elf"], scratch_input)
    run([str(OBJCOPY), "--dump-section",
         f".lisp65_workbench_overlay={overlay}",
         str(scratch_input), str(scratch_output)])
    scratch_input.unlink()
    scratch_output.unlink()
    overlay_data = regular(overlay, "boot-overlay payload")
    if len(overlay_data) != end - start:
        raise PreSmokeError("boot-overlay extraction length differs from ELF geometry")

    contract_sha = sha(paths["contract"])
    build_id = int(contract_sha[:8], 16)
    header_text = regular(paths["stage_header"], "stage header").decode("ascii")
    expected_build = re.search(r"LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x([0-9a-fA-F]+)UL", header_text)
    expected_bank = re.search(r"LISP65_BOOT_OVERLAY_STAGE_BANK 0x([0-9a-fA-F]+)u", header_text)
    expected_off = re.search(r"LISP65_BOOT_OVERLAY_STAGE_OFF 0x([0-9a-fA-F]+)u", header_text)
    if not expected_build or not expected_bank or not expected_off:
        raise PreSmokeError("stage header is missing a pinned overlay binding")
    if int(expected_build.group(1), 16) != build_id:
        raise PreSmokeError("boot-overlay build ID differs from resolved-profile SHA")
    header_address = (int(expected_bank.group(1), 16) << 16) | int(expected_off.group(1), 16)
    if header_address != BOOT_OVERLAY_STAGE:
        raise PreSmokeError("boot-overlay stage address drift")

    descriptor = struct.pack(
        "<4sBBIHHHH", DESCRIPTOR_MAGIC, DESCRIPTOR_VERSION, DESCRIPTOR_BYTES,
        build_id, start, entry, len(overlay_data), crc16(overlay_data))
    stage = out / "boot-overlay.stage.bin"
    write_atomic(stage, descriptor + overlay_data)

    deployment = {
        "format": "lisp65-c2-link19-hardware-presmoke-deployment-v1",
        "status": "ready-receipt-less",
        "claim_limit": (
            "Host-verified deployment plan for a receipt-less fail-fast hardware "
            "pre-smoke. It is not hardware evidence, promotion, acceptance or release."),
        "source_pin_receipt": {
            "path": str(PIN_RECEIPT.relative_to(ROOT)),
            "sha256": sha(PIN_RECEIPT),
        },
        "source_replay_receipt": {
            "path": str(REPLAY_RECEIPT.relative_to(ROOT)),
            "sha256": sha(REPLAY_RECEIPT),
        },
        "product": binding(paths["product"], 0x00002001),
        "preloads": [
            binding(paths["c2d"], C2D_STAGE),
            binding(stage, BOOT_OVERLAY_STAGE),
            binding(paths["session_family"], SESSION_FAMILY_STAGE),
            binding(paths["shelf"], SHELF_STAGE),
            binding(paths["boot_family"], BOOT_FAMILY_STAGE),
            binding(paths["window"], KERNAL_WINDOW_STAGE),
        ],
        "boot_overlay": {
            "build_id": f"0x{build_id:08x}",
            "vma": f"0x{start:04x}",
            "entry": f"0x{entry:04x}",
            "payload_bytes": len(overlay_data),
            "payload_crc16": f"0x{crc16(overlay_data):04x}",
            "descriptor_bytes": DESCRIPTOR_BYTES,
        },
        "span_checks": {
            "c2d_ends_before_boot_overlay": C2D_STAGE + paths["c2d"].stat().st_size <= BOOT_OVERLAY_STAGE,
            "session_ends_before_shelf": SESSION_FAMILY_STAGE + paths["session_family"].stat().st_size <= SHELF_STAGE,
            "shelf_ends_before_boot_family": SHELF_STAGE + paths["shelf"].stat().st_size <= BOOT_FAMILY_STAGE,
            "window_ends_at_attic_limit": KERNAL_WINDOW_STAGE + paths["window"].stat().st_size == 0x08800000,
        },
        "new_product_links": 0,
    }
    if not all(deployment["span_checks"].values()):
        raise PreSmokeError("deployment spans overlap or drift")
    write_atomic(out / "deployment.json",
                 (json.dumps(deployment, indent=2, sort_keys=True) + "\n").encode("ascii"))
    verify(out)
    print(f"c2-product-hw-presmoke: PREPARE PASS out={out} new-links=0")


def verify(out: Path) -> None:
    verify_source_bindings()
    deployment = load_json(out / "deployment.json", "pre-smoke deployment")
    if deployment.get("status") != "ready-receipt-less" or deployment.get("new_product_links") != 0:
        raise PreSmokeError("pre-smoke deployment status drift")
    if sha(PIN_RECEIPT) != deployment["source_pin_receipt"]["sha256"]:
        raise PreSmokeError("pre-smoke pin-receipt binding drift")
    if sha(REPLAY_RECEIPT) != deployment["source_replay_receipt"]["sha256"]:
        raise PreSmokeError("pre-smoke replay-receipt binding drift")
    for item in [deployment["product"], *deployment["preloads"]]:
        path = ROOT / item["path"]
        assert_binding(path, item, "pre-smoke deployment artifact")
    if not all(deployment["span_checks"].values()):
        raise PreSmokeError("pre-smoke span check drift")
    print(f"c2-product-hw-presmoke: VERIFY PASS out={out} new-links=0")


def selftest() -> None:
    if crc16(b"123456789") != 0x29B1:
        raise PreSmokeError("CRC-16/CCITT-FALSE selftest failed")
    sample = struct.pack("<4sBBIHHHH", DESCRIPTOR_MAGIC, 1, 18,
                         0x12345678, 0xC000, 0xC123, 0x234, 0xABCD)
    if len(sample) != DESCRIPTOR_BYTES or sample[:4] != DESCRIPTOR_MAGIC:
        raise PreSmokeError("boot-overlay descriptor selftest failed")
    print("c2-product-hw-presmoke: SELFTEST PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            prepare(args.out.resolve())
        elif args.mode == "verify":
            verify(args.out.resolve())
        else:
            selftest()
    except PreSmokeError as exc:
        print(f"c2-product-hw-presmoke: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
