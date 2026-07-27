#!/usr/bin/env python3
"""Build the non-promotable G5 Enhanced-DMA write-only discriminator.

The linked cold stager normally passes DMA_COPY|CHAIN to the first of two
immutable jobs (media-buffer -> target, target -> local readback).  Hardware
G5 session 02 proved that the second job executed but observed the old target,
while the target itself stayed old after the stager timed out.

This diagnostic changes only the immediate operand that supplies CHAIN:

    $2e18: ldx #$04  ->  ldx #$00

The first write therefore runs as a standalone job.  The unchanged readback
poll times out and reaches the normal disk-error hold, where JTAG can capture
the target without any second DMA job having touched the observation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
R5 = ROOT / "build/c2.2/acceptance/r5/product"
SOURCE_STAGER = R5 / "10-autoboot.c65"
SOURCE_D81 = R5 / "15-lisp65-product.d81"
OUTPUT = ROOT / "build/c2.2/acceptance/g5/write-only-diagnostic"
PATCHED_STAGER = OUTPUT / "autoboot-write-only.c65"
DIAGNOSTIC_D81 = OUTPUT / "lisp65-product-write-only-diagnostic.d81"
EXTRACTED_STAGER = OUTPUT / "autoboot-readback.c65"
RECEIPT = OUTPUT / "build-receipt.json"
MEMBER_READBACK = OUTPUT / "member-readback"
HARDWARE_OUTPUT = ROOT / "build/c2.2/acceptance/g5/session-03-write-only"
HARDWARE_RECEIPT = HARDWARE_OUTPUT / "hardware-receipt.json"
EXPECTED_BANK2 = R5 / "01-bank2-static-code.bin"
OLD_BANK2 = (
    ROOT / "build/c2.2/acceptance/g5/session-02/first-red-readback/bank2.bin"
)
CAPTURES = tuple(
    HARDWARE_OUTPUT / f"capture-{index}.bin" for index in range(1, 4)
)
LIVE_JOBS = HARDWARE_OUTPUT / "stage-jobs-live.bin"
LIVE_PAYLOAD = HARDWARE_OUTPUT / "sector-payload-live.bin"
CHIPRAM = HARDWARE_OUTPUT / "chipram-0-6.bin"
SESSION_RESET_UTC = datetime(
    2026, 7, 26, 19, 49, 45, 676000, tzinfo=timezone.utc)

SOURCE_STAGER_SHA256 = (
    "b541cdd7fa64e0c5e3279487a847379b75aafbca69910e6b53a1e59f68127434"
)
SOURCE_D81_SHA256 = (
    "e9bc8dab15e2c988675cee49307f5f5ad0af825f333d58fd904a1a2a7595d635"
)
PATCH_FILE_OFFSET = 0x0E1A
PATCH_VMA = 0x2E19
PATCH_BEFORE = 0x04
PATCH_AFTER = 0x00

MEDIA_MEMBERS = {
    "boot.id": "00-boot.id",
    "code.bin": "01-bank2-static-code.bin",
    "c2d.bin": "09-initial.c2d-v6.bin",
    "bootstage.bin": "08-bootstage.bin",
    "session.bin": "06-runtime-overlays-session-final.bin",
    "shelf.bin": "04-product-shelf-v4-direct.bin",
    "boot.bin": "02-runtime-overlays-boot-final.bin",
    "region1.bin": "07-runtime-overlays-session-final-region1.bin",
    "window.bin": "03-c2-product-kernal-window.bin",
    "lisp65.prg": "05-lisp65-c2-substitution-linked.prg",
    "profile": "17-resolved-profile.txt",
    "ide": "11-ide.ext.bin",
    "idex": "12-idex.ext.bin",
    "m65d": "13-m65d.ext.bin",
}


class DiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv: list[str]) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise DiagnosticError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"{result.stdout}")
    return result.stdout


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"hardware evidence is missing: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def analyze_hardware() -> int:
    require(RECEIPT.is_file(), "write-only build receipt is missing")
    build = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(build["status"] == "built-not-run-non-promotable",
            "write-only build receipt status drift")
    require(EXPECTED_BANK2.is_file() and OLD_BANK2.is_file(),
            "Bank-2 comparison authority is missing")
    expected = EXPECTED_BANK2.read_bytes()[:254]
    old = OLD_BANK2.read_bytes()[:254]
    require(len(expected) == len(old) == 254,
            "Bank-2 comparison prefix length drift")
    captured = []
    for path in CAPTURES:
        data = path.read_bytes()
        require(len(data) == 254, f"capture length drift: {path}")
        captured.append(data)
    require(len(set(captured)) == 1,
            "write-only target captures are not byte-identical")
    result = captured[0]
    if result == expected:
        outcome = "standalone-write-visible"
        status = "green-standalone-write-visible"
    elif result == old:
        outcome = "standalone-write-never-visible"
        status = "first-red-standalone-write-never-visible"
    else:
        outcome = "standalone-write-produced-third-content"
        status = "first-red-standalone-write-third-content"

    expected_jobs = bytes.fromhex(
        "0b80008100850100"  # Enhanced F018B options and terminator
        "00fe00bc3400000002000000"  # standalone Bank 0 -> Bank 2 COPY
        "0b80008100850100"
        "00fe00000002ba3500000000"  # prepared, unreachable readback COPY
    )
    jobs = LIVE_JOBS.read_bytes()
    payload = LIVE_PAYLOAD.read_bytes()
    chipram = CHIPRAM.read_bytes()
    require(jobs == expected_jobs,
            "live write-only Enhanced-DMA descriptors drift")
    require(payload == expected,
            "live media payload differs from expected Bank-2 prefix")
    require(len(chipram) == 0x70000,
            "Bank 0..6 readback length drift")
    payload_hits = []
    start = 0
    while True:
        start = chipram.find(expected, start)
        if start < 0:
            break
        payload_hits.append(start)
        start += 1
    require(payload_hits == [0x34BC],
            "expected payload has an unexplained Chip-RAM copy")

    capture_rows = []
    for path in CAPTURES:
        captured_at = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc)
        capture_rows.append({
            **bind(path),
            "captured_at_utc": captured_at.isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "elapsed_after_reset_ms": int(
                (captured_at - SESSION_RESET_UTC).total_seconds() * 1000),
            "equals_expected_payload": path.read_bytes() == expected,
            "equals_preexisting_bank2": path.read_bytes() == old,
        })

    differing = sum(before != after
                    for before, after in zip(result, expected))
    receipt = {
        "format": "lisp65-c2-lite-g5-write-only-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": status,
        "diagnostic_identity": {
            "build_receipt": bind(RECEIPT),
            "stager": build["candidate"]["stager"],
            "product_d81": {
                key: build["candidate"]["product_d81"][key]
                for key in ("path", "bytes", "sha256")
            },
            "promotable": False,
        },
        "hardware_run": {
            "reset_at_utc": SESSION_RESET_UTC.isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "visible_terminal_state": (
                "expected fail-closed L65SYS DISK ERROR - CHECK MEDIA"),
            "serial_ownership_note": (
                "vf011 held the serial port through the fail-closed stop; "
                "the first JTAG capture therefore completed 45 seconds after "
                "reset, far beyond the 192-raster-wrap product deadline"
            ),
            "captures": capture_rows,
        },
        "live_inputs": {
            "stage_jobs": {
                **bind(LIVE_JOBS),
                "first_job": {
                    "command": "COPY-without-CHAIN",
                    "source": "0x000034bc",
                    "destination": "0x00020000",
                    "bytes": 254,
                },
                "second_job": "prepared-but-unreachable",
            },
            "sector_payload": {
                **bind(LIVE_PAYLOAD),
                "equals_expected_payload": payload == expected,
            },
            "chipram_bank_0_through_6": {
                **bind(CHIPRAM),
                "address": "0x00000000",
                "payload_occurrences": [
                    f"0x{address:08x}" for address in payload_hits
                ],
                "interpretation": (
                    "the exact 254-byte payload exists only at its source "
                    "0x000034bc; no second exact copy exists in Chip RAM "
                    "Bank 0 through Bank 6"
                ),
            },
        },
        "comparison": {
            "expected_payload_prefix": {
                "path": str(EXPECTED_BANK2.relative_to(ROOT)),
                "bytes": 254,
                "sha256": hashlib.sha256(expected).hexdigest(),
            },
            "preexisting_bank2_prefix": {
                "path": str(OLD_BANK2.relative_to(ROOT)),
                "bytes": 254,
                "sha256": hashlib.sha256(old).hexdigest(),
            },
            "observed_sha256": hashlib.sha256(result).hexdigest(),
            "bytes_different_from_expected": differing,
            "outcome": outcome,
        },
        "disposition": {
            "ordered-readback-prematurity_hypothesis": "rejected",
            "wrong-chipram-destination_hypothesis": (
                "no exact payload copy in Bank 0 through Bank 6"),
            "completion_contract_rewrite_authorized": False,
            "first_job": (
                "The exact standalone Bank-0-to-Bank-2 Enhanced-DMA COPY "
                "did not alter any target byte before or long after timeout."
            ),
            "next_question": (
                "Attribute trigger acceptance and the cold-state "
                "Bank-0-to-Bank-2 DMA write path before changing product or "
                "media-completion semantics."
            ),
        },
        "claim_limit": (
            "This is a non-promotable first-red diagnostic. It rejects the "
            "in-chain-readback-only explanation but proves no G5, promotion "
            "or release claim."
        ),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-lite-media-g5-write-only-diagnostic: "
        f"{status} observed={receipt['comparison']['observed_sha256']} "
        f"diff={differing}")
    return 0


def build_diagnostic() -> int:
    require(SOURCE_STAGER.is_file(), "R5 cold stager is missing")
    require(SOURCE_D81.is_file(), "R5 product D81 is missing")
    require(sha256(SOURCE_STAGER) == SOURCE_STAGER_SHA256,
            "R5 cold-stager identity drift")
    require(sha256(SOURCE_D81) == SOURCE_D81_SHA256,
            "R5 product-D81 identity drift")
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")

    source = SOURCE_STAGER.read_bytes()
    require(source[:2] == b"\x01\x20", "cold-stager load address drift")
    require(PATCH_FILE_OFFSET < len(source), "patch offset is outside stager")
    require(source[PATCH_FILE_OFFSET] == PATCH_BEFORE,
            "write-only patch preimage drift")
    require(source[PATCH_FILE_OFFSET - 1:PATCH_FILE_OFFSET + 2]
            == b"\xa2\x04\x86",
            "write-only patch instruction context drift")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidate = bytearray(source)
    candidate[PATCH_FILE_OFFSET] = PATCH_AFTER
    PATCHED_STAGER.write_bytes(candidate)

    shutil.copyfile(SOURCE_D81, DIAGNOSTIC_D81)
    run([c1541, str(DIAGNOSTIC_D81),
         "-delete", "autoboot.c65",
         "-write", str(PATCHED_STAGER), "autoboot.c65"])
    run([c1541, str(DIAGNOSTIC_D81),
         "-read", "autoboot.c65", str(EXTRACTED_STAGER)])
    require(EXTRACTED_STAGER.read_bytes() == bytes(candidate),
            "diagnostic D81 stager readback drift")
    MEMBER_READBACK.mkdir(parents=True, exist_ok=True)
    member_receipts = []
    for media_name, source_name in MEDIA_MEMBERS.items():
        source_path = R5 / source_name
        target_path = MEMBER_READBACK / source_name
        require(source_path.is_file(), f"R5 member is missing: {source_name}")
        run([c1541, str(DIAGNOSTIC_D81),
             "-read", media_name, str(target_path)])
        require(target_path.read_bytes() == source_path.read_bytes(),
                f"diagnostic D81 member drift: {media_name}")
        member_receipts.append({
            "media_name": media_name,
            "source_path": str(source_path.relative_to(ROOT)),
            "sha256": sha256(source_path),
            "bytes": source_path.stat().st_size,
        })

    changed = [
        index for index, (before, after) in enumerate(zip(source, candidate))
        if before != after
    ]
    require(changed == [PATCH_FILE_OFFSET],
            "diagnostic stager has changes outside the one-byte patch")

    receipt = {
        "format": "lisp65-c2-lite-g5-write-only-diagnostic-v1",
        "recorded_on": "2026-07-26",
        "status": "built-not-run-non-promotable",
        "source": {
            "r5_stager": {
                "path": str(SOURCE_STAGER.relative_to(ROOT)),
                "sha256": SOURCE_STAGER_SHA256,
                "bytes": len(source),
            },
            "r5_product_d81": {
                "path": str(SOURCE_D81.relative_to(ROOT)),
                "sha256": SOURCE_D81_SHA256,
                "bytes": SOURCE_D81.stat().st_size,
            },
        },
        "patch": {
            "file_offset": PATCH_FILE_OFFSET,
            "vma_operand": f"0x{PATCH_VMA:04x}",
            "instruction_vma": "0x2e18",
            "instruction": "ldx #$04 -> ldx #$00",
            "before": f"0x{PATCH_BEFORE:02x}",
            "after": f"0x{PATCH_AFTER:02x}",
            "changed_bytes": 1,
            "effect": (
                "clear CHAIN on the first immutable Enhanced-DMA copy; "
                "the prepared readback job is unreachable"
            ),
        },
        "candidate": {
            "stager": {
                "path": str(PATCHED_STAGER.relative_to(ROOT)),
                "sha256": sha256(PATCHED_STAGER),
                "bytes": PATCHED_STAGER.stat().st_size,
                "d81_readback_sha256": sha256(EXTRACTED_STAGER),
            },
            "product_d81": {
                "path": str(DIAGNOSTIC_D81.relative_to(ROOT)),
                "sha256": sha256(DIAGNOSTIC_D81),
                "bytes": DIAGNOSTIC_D81.stat().st_size,
                "unchanged_member_readbacks": member_receipts,
            },
        },
        "hardware_protocol": {
            "expected_screen": "L65SYS DISK ERROR - CHECK MEDIA",
            "reason": (
                "the unchanged readback buffer remains poisoned and the "
                "existing 192-raster-wrap fail-closed timeout must fire"
            ),
            "captures": [
                {"elapsed_after_launch_ms": 1, "address": "0x00020000",
                 "bytes": 254},
                {"elapsed_after_launch_ms": 700, "address": "0x00020000",
                 "bytes": 254},
                {"elapsed_after_launch_ms": 2400, "address": "0x00020000",
                 "bytes": 254},
            ],
            "expected_payload": {
                "path": (
                    "build/c2.2/acceptance/r5/product/"
                    "01-bank2-static-code.bin"
                ),
                "offset": 0,
                "bytes": 254,
            },
            "outcomes": {
                "converges": (
                    "the standalone write is valid; the ordered in-chain "
                    "readback was issued before target visibility"
                ),
                "stays_old": (
                    "the first Enhanced-DMA write itself is invalid or not "
                    "accepted; no readback/completion rewrite is authorized"
                ),
            },
        },
        "immutability": {
            "compiler_or_linker_run": False,
            "linked_product_bytes_changed": False,
            "source_product_d81_changed": False,
            "diagnostic_identity_promotable": False,
            "r4_r5_r6_g5_g6_claim": "none",
        },
        "claim_limit": (
            "One hardware discriminator for the first 254-byte Bank-2 stage. "
            "It cannot prove media completion, G5, promotion or release."
        ),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-lite-media-g5-write-only-diagnostic: PASS "
        f"stager={receipt['candidate']['stager']['sha256']} "
        f"d81={receipt['candidate']['product_d81']['sha256']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--analyze-hardware", action="store_true",
        help="bind and classify the completed write-only hardware capture")
    args = parser.parse_args()
    if args.analyze_hardware:
        return analyze_hardware()
    return build_diagnostic()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiagnosticError, OSError, ValueError) as exc:
        print(f"c2-lite-media-g5-write-only-diagnostic: FAIL: {exc}")
        raise SystemExit(1)
