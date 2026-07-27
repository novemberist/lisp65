#!/usr/bin/env python3
"""Build/check the G5 media identity using the proven normal DMA seam.

The historical canonical-media directory is intentionally one-shot.  This
wrapper gives the corrected acceptance-tool stager a fresh identity without
rewriting either that history or any product artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_media_product as MEDIA  # noqa: E402


BUILD = ROOT / "build/c2.2/acceptance/g5/normal-dma-repack-v7"
DIFF_RECEIPT = (
    ROOT / "build/c2.2/acceptance/g5/dma-path-diff/receipt.json"
)
RECEIPT = BUILD / "g5-repack-receipt.json"
RUNBOOK = BUILD / "g5-runbook.json"
R5_PREFLIGHT = ROOT / "build/c2.2/acceptance/r5/r5-preflight-receipt.json"
R5_RUNBOOK = ROOT / "build/c2.2/acceptance/r5/g5-runbook.json"
R5_BANK2 = ROOT / "build/c2.2/acceptance/r5/product/01-bank2-static-code.bin"
OLD_BANK2 = (
    ROOT / "build/c2.2/acceptance/g5/session-02/"
    "first-red-readback/bank2.bin"
)
REPLAY = ROOT / "build/c2.2/acceptance/g5/replay-v7"
HARDWARE_RECEIPT = REPLAY / "hardware-first-red-receipt.json"
DEPLOY_LOG = REPLAY / "deploy-serial.log"
SCREENS = (
    REPLAY / "screen-05.png",
    REPLAY / "screen-first-red-confirm.png",
)
READBACK = REPLAY / "first-red-readback"


class RepackError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepackError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"repack binding absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def configure() -> None:
    MEDIA.BUILD = BUILD
    MEDIA.MANIFEST = BUILD / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = BUILD / "boot.id"
    MEDIA.STAGER = BUILD / "autoboot.c65"
    MEDIA.STAGER_MAP = BUILD / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = BUILD / "lisp65-product.d81"
    MEDIA.WORK_D81 = BUILD / "lisp65-work.d81"
    MEDIA.MOUNT = BUILD / "lisp65-product.mount.json"


def validate(value: dict[str, Any]) -> None:
    diff = json.loads(DIFF_RECEIPT.read_text(encoding="utf-8"))
    r5 = json.loads(R5_PREFLIGHT.read_text(encoding="utf-8"))
    before = {
        row["role"]: row["sha256"] for row in r5["materialized_artifacts"]}
    after = {
        row["role"]: row["sha256"] for row in value["artifacts"]}
    changed = {role for role in before if before[role] != after[role]}
    require(
        diff["status"] == "first-red-g5-private-enhanced-dma-transport"
        and changed == {
            "cold-stager", "product-d81", "product-mount-descriptor"}
        and value["status"] == "passed-complete-C2-lite-two-media-product"
        and value["execution_accounting"]["product_compiler_runs"] == 0
        and value["execution_accounting"]["product_linker_runs"] == 0
        and value["execution_accounting"]["hardware_runs"] == 0
        and value["stager"]["gate"]["ordered_chain_descriptor_bytes"] == 24
        and value["stager"]["gate"]["status"].startswith(
            "passed-strict-build-and-product-equivalent-normal-f018b")
        and value["stager"]["gate"]["linked_transport"][
            "normal_f018b_d700_trigger_occurrences"] == 1
        and value["stager"]["gate"]["linked_transport"][
            "enhanced_d705_trigger_occurrences"] == 0,
        "normal-DMA G5 repack qualification drift")


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "G5 normal-DMA repack is one-shot")
    require(DIFF_RECEIPT.is_file(), "DMA-path diff must precede repack")
    value = MEDIA.build()
    MEDIA.check()
    validate(value)
    old_runbook = json.loads(R5_RUNBOOK.read_text(encoding="utf-8"))
    runbook = {
        **old_runbook,
        "format": "lisp65-c2-lite-G5-runbook-v2",
        "version": 2,
        "status": "ready-replay-after-G5-tool-transport-fix",
        "input_authority": (
            "accepted-R5-product-plus-bound-G5-tool-only-repack"),
        "artifact_set_sha256": value["artifact_set_sha256"],
        "product_d81": MEDIA.PRODUCT_D81.relative_to(ROOT).as_posix(),
        "work_d81": MEDIA.WORK_D81.relative_to(ROOT).as_posix(),
        "mount_descriptor": MEDIA.MOUNT.relative_to(ROOT).as_posix(),
        "supersedes": bind(R5_RUNBOOK),
        "r5_preflight": bind(R5_PREFLIGHT),
        "tool_fix": bind(DIFF_RECEIPT),
        "tool_fix_scope": {
            "changed_roles": [
                "cold-stager", "product-d81",
                "product-mount-descriptor",
            ],
            "unchanged_roles": 16,
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_byte_changes": 0,
        },
    }
    RUNBOOK.write_text(
        json.dumps(runbook, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": "lisp65-c2-lite-g5-normal-dma-repack-v1",
        "status": "passed-host-repack-hardware-not-run",
        "claim_limit": (
            "G5 acceptance-tool identity only. Product artifacts are copied "
            "byte-for-byte from the accepted R5 set; no product compile, "
            "product link, hardware run, G5 claim or promotion occurred."
        ),
        "cause": bind(DIFF_RECEIPT),
        "media_manifest": bind(MEDIA.MANIFEST),
        "runbook": bind(RUNBOOK),
        "stager": bind(MEDIA.STAGER),
        "product_d81": bind(MEDIA.PRODUCT_D81),
        "work_d81": bind(MEDIA.WORK_D81),
        "mount": bind(MEDIA.MOUNT),
        "transport": {
            "list_format": "F018B",
            "jobs": 2,
            "job_bytes": 12,
            "total_descriptor_bytes": 24,
            "first_command": "COPY|CHAIN",
            "second_command": "COPY",
            "trigger": "$D700",
            "mode": "$D703=1",
            "list_bank": "$D702=0",
        },
        "execution_accounting": value["execution_accounting"],
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def check() -> dict[str, Any]:
    value = MEDIA.check()
    validate(value)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "passed-host-repack-hardware-not-run"
        and receipt["cause"] == bind(DIFF_RECEIPT)
        and receipt["media_manifest"] == bind(MEDIA.MANIFEST)
        and receipt["runbook"] == bind(RUNBOOK)
        and receipt["stager"] == bind(MEDIA.STAGER)
        and receipt["product_d81"] == bind(MEDIA.PRODUCT_D81),
        "G5 normal-DMA repack receipt drift")
    return receipt


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def analyze_hardware_first_red() -> dict[str, Any]:
    host = check()
    require(host["status"] == "passed-host-repack-hardware-not-run",
            "host repack no longer precedes the hardware replay")
    deploy = DEPLOY_LOG.read_text(encoding="utf-8")
    require("Uploaded 819200 bytes in " in deploy,
            "serial deployment did not report the complete D81")
    reset = re.search(
        r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\dZ) NOTE reseting "
        r"MEGA65 and exiting",
        deploy,
    )
    require(reset is not None, "serial mount/reset timestamp is absent")
    require(len({sha256(path) for path in SCREENS}) == 1,
            "first-red screen was not stable across both captures")

    jobs_path = READBACK / "stage-jobs-live.bin"
    payload_path = READBACK / "sector-payload-live.bin"
    bank2_path = READBACK / "bank2-prefix-live.bin"
    target_path = READBACK / "target-readback-live.bin"
    verify_path = READBACK / "verify-buffer-live.bin"
    jobs = jobs_path.read_bytes()
    payload = payload_path.read_bytes()
    bank2 = bank2_path.read_bytes()
    target = target_path.read_bytes()
    expected = R5_BANK2.read_bytes()[:254]
    old = OLD_BANK2.read_bytes()[:254]
    expected_jobs = bytes.fromhex(
        "04fe006c3400000002000000"
        "00fe000000026a3500000000"
    )
    require(jobs == expected_jobs,
            "live normal-F018B job pair differs from the linked v7 geometry")
    require(payload == expected and len(payload) == 254,
            "live sector payload differs from the accepted R5 Bank-2 prefix")
    require(bank2 == target == old and len(bank2) == 254,
            "normal-DMA first-red target/readback classification drift")
    differing = sum(before != after
                    for before, after in zip(payload, bank2))
    require(differing == 251, "normal-DMA first-red diff count drift")

    receipt = {
        "format": "lisp65-c2-lite-g5-normal-dma-hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status": "first-red-normal-dma-write-not-visible",
        "authority": {
            "host_repack": bind(RECEIPT),
            "runbook": bind(RUNBOOK),
            "product_d81": bind(MEDIA.PRODUCT_D81),
            "stager": bind(MEDIA.STAGER),
            "stager_elf": bind(BUILD / "autoboot.c65.elf"),
            "dma_path_diff": bind(DIFF_RECEIPT),
        },
        "deployment": {
            **bind(DEPLOY_LOG),
            "transport": "serial-SD-upload-and-mount",
            "device": "/dev/ttyUSB1",
            "remote_name": "L65G5V7.D81",
            "uploaded_bytes_reported": 819200,
            "mount_reset_at_utc": reset.group(1),
        },
        "first_red": {
            "runbook_case": "media/cold-boot-stage-banner",
            "expected": "banner-and-usable-REPL",
            "observed": "L65SYS DISK ERROR - CHECK MEDIA",
            "border": "red",
            "later_cases_executed": 0,
            "screens": [
                {**bind(path), "captured_at_utc": utc_mtime(path)}
                for path in SCREENS
            ],
            "stable_screen_sha256": sha256(SCREENS[0]),
        },
        "live_readback": {
            "stage_jobs": {
                **bind(jobs_path),
                "bytes_hex": jobs.hex(),
                "first": {
                    "command": "COPY|CHAIN",
                    "source": "0x0000346c",
                    "destination": "0x00020000",
                    "bytes": 254,
                },
                "second": {
                    "command": "COPY",
                    "source": "0x00020000",
                    "destination": "0x0000356a",
                    "bytes": 254,
                },
                "list_format": "F018B",
                "trigger_bound_by_host_gate": "$D700",
            },
            "sector_payload": {
                **bind(payload_path),
                "equals_expected_bank2_prefix": True,
            },
            "bank2_prefix": {
                **bind(bank2_path),
                "equals_sector_payload": False,
                "equals_preexisting_bank2": True,
            },
            "target_readback": {
                **bind(target_path),
                "equals_sector_payload": False,
                "equals_bank2_prefix": True,
            },
            "verify_buffer": bind(verify_path),
            "bytes_different_target_vs_payload": differing,
        },
        "classification": {
            "normal_f018b_job_materialized": True,
            "sector_payload_correct": True,
            "bank0_to_bank2_write_visible": False,
            "readback_observed_old_target": True,
            "previous_private_enhanced_path_explanation": (
                "insufficient: replacing the private D705 path with the "
                "product-style D700/F018B path did not make the write "
                "visible in this cold-stager context"
            ),
            "internal_failure_stage_beyond_this_evidence": "not claimed",
            "next_question": (
                "Attribute the live D700 trigger acceptance and controller "
                "state in the cold stager before proposing another tool fix."
            ),
        },
        "claims": {
            "G5": "first-red",
            "G6": "not-run",
            "promotion": "not-claimed",
            "product_open_findings": 0,
            "acceptance_tool_open_findings": 1,
        },
        "immutability": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 1,
        },
        "claim_limit": (
            "This receipt proves only the first G5 runbook case failed on "
            "the v7 acceptance-media identity and that the linked normal "
            "F018B job did not produce a visible Bank-2 write. It does not "
            "localize controller non-acceptance, prove a product defect, "
            "or support G5, G6, promotion, or release."
        ),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def check_hardware_first_red() -> dict[str, Any]:
    require(HARDWARE_RECEIPT.is_file(),
            "normal-DMA hardware first-red receipt is absent")
    expected = analyze_hardware_first_red()
    actual = json.loads(HARDWARE_RECEIPT.read_text(encoding="utf-8"))
    require(actual == expected, "normal-DMA hardware receipt drift")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "build", "check", "record-hardware-first-red",
            "check-hardware-first-red",
        ),
    )
    args = parser.parse_args()
    configure()
    if args.action == "build":
        value = build()
    elif args.action == "check":
        value = check()
    elif args.action == "record-hardware-first-red":
        value = analyze_hardware_first_red()
    else:
        value = check_hardware_first_red()
    print(json.dumps({
        "status": value["status"],
        "receipt": (
            HARDWARE_RECEIPT if "hardware" in args.action else RECEIPT
        ).relative_to(ROOT).as_posix(),
        "product_d81": (
            value["authority"]["product_d81"]
            if "hardware" in args.action else value["product_d81"]
        ),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RepackError, MEDIA.MediaError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(f"c2-lite-media-g5-normal-dma-repack: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
