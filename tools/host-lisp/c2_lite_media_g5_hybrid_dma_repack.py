#!/usr/bin/env python3
"""Build/check the address-qualified hybrid G5 media identity.

The v10 cold stager used a normal 20-bit F018B list for every media role.
That path is correct for the Chip-RAM destinations of roles 1--3, but it
truncated the Attic destinations of roles 4--8.  This acceptance-tool-only
repack keeps the proven D700 path for Chip RAM and uses D705 Enhanced jobs
with content-defined target readback for Attic addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_media_product as MEDIA  # noqa: E402


BUILD = ROOT / "build/c2.2/acceptance/g5/hybrid-dma-repack-v11"
RECEIPT = BUILD / "g5-hybrid-dma-repack-receipt.json"
RUNBOOK = BUILD / "g5-runbook.json"
V10 = ROOT / "build/c2.2/acceptance/g5/handoff-completion-repack-v10"
V10_MANIFEST = V10 / "candidate-manifest.json"
V10_RUNBOOK = V10 / "g5-runbook.json"
V10_D81 = V10 / "lisp65-product.d81"
FIRST_RED = (
    ROOT
    / "build/c2.2/acceptance/g5/replay-v10-handoff-completion"
    / "clean-reset-mount/g5-normal-f018b-attic-address-first-red.json"
)
GATE_FIRST_RED = (
    ROOT
    / "build/c2.2/acceptance/g5/hybrid-dma-capability-v11-first"
    / "first-red-receipt.json"
)


class RepackError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepackError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"hybrid-DMA authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def configure() -> None:
    MEDIA.BUILD = BUILD
    MEDIA.MANIFEST = BUILD / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = BUILD / "boot.id"
    MEDIA.STAGER = BUILD / "autoboot.c65"
    MEDIA.STAGER_MAP = BUILD / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = BUILD / "lisp65-product.d81"
    MEDIA.WORK_D81 = BUILD / "lisp65-work.d81"
    MEDIA.MOUNT = BUILD / "lisp65-product.mount.json"


def first_red_attribution() -> dict[str, Any]:
    value = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        value["status"]
            == "class-c-media-model-first-red-before-product-handoff"
        and value["candidate"]["d81_sha256"] == sha256(V10_D81)
        and value["candidate"]["product_bytes_changed"] == 0
        and value["run"]["failed_role"] == 4
        and value["run"]["failed_destination"] == "0x08000000"
        and value["target_capture"]["differing_bytes"] == 64144
        and value["attribution"]["normal_f018b_address_bits"] == 20
        and value["attribution"]["destination_after_current_encoding"]
            == "0x00000000"
        and value["promotion"]["link66_untouched"] is True,
        "v10 Attic-address first-red attribution drift")
    return {
        "status": "proved-20-bit-normal-list-truncated-role-4-Attic-target",
        "failed_role": 4,
        "descriptor_target": "0x08000000",
        "encoded_target": "0x00000000",
        "differing_target_bytes": 64144,
        "product_bytes_changed": 0,
        "link66_untouched": True,
        "authority": bind(FIRST_RED),
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    previous = json.loads(V10_MANIFEST.read_text(encoding="utf-8"))
    before = {row["role"]: row["sha256"] for row in previous["artifacts"]}
    after = {row["role"]: row["sha256"] for row in value["artifacts"]}
    changed = {role for role in before if before[role] != after[role]}
    gate = value["stager"]["gate"]
    linked = gate["linked_transport"]
    domains = linked["address_domain_gate"]
    descriptor_domains = value["descriptor"]["stage_transport_domains"]
    require(
        changed == {
            "cold-stager", "product-d81", "product-mount-descriptor"}
        and len(before) == len(after) == 19
        and value["execution_accounting"]["product_compiler_runs"] == 0
        and value["execution_accounting"]["product_linker_runs"] == 0
        and value["execution_accounting"]["hardware_runs"] == 0
        and gate["status"]
            == (
                "passed-strict-build-and-address-qualified-hybrid-f018b-"
                "content-defined-target-readback")
        and linked["normal_f018b_d700_trigger_occurrences"] == 1
        and linked["enhanced_d705_trigger_occurrences"] == 2
        and linked["normal_f018b_roles"] == [1, 2, 3]
        and linked["enhanced_f018b_roles"] == [4, 5, 6, 7, 8]
        and linked["chip_jobs_symbol"]["bytes"] == 24
        and linked["attic_stage_jobs_symbol"]["bytes"] == 40
        and linked["attic_retry_job_symbol"]["bytes"] == 20
        and domains == descriptor_domains
        and domains["mutations_rejected"] == 6
        and gate["hybrid_transport_source_mutations"] == 16
        and gate["poison_writes_per_primary_media_block"] == 1
        and gate["timeout_raster_low_wraps"] == 192
        and gate["descriptor_reuse_before_completion"] is False,
        "G5 address-qualified hybrid repack qualification drift")
    return {
        "changed_roles": sorted(changed),
        "unchanged_roles": len(before) - len(changed),
        "product_compiler_runs": 0,
        "product_linker_runs": 0,
        "product_byte_changes": 0,
        "chip_roles": [1, 2, 3],
        "attic_roles": [4, 5, 6, 7, 8],
        "normal_d700_triggers": 1,
        "enhanced_d705_triggers": 2,
        "address_domain_mutations_rejected": 6,
        "source_and_ELF_mutations_rejected": 16,
    }


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "G5 hybrid-DMA repack is one-shot")
    for authority in (
        V10_MANIFEST, V10_RUNBOOK, V10_D81, FIRST_RED, GATE_FIRST_RED,
    ):
        require(authority.is_file(),
                f"required hybrid-DMA predecessor absent: {authority}")
    cause = first_red_attribution()
    value = MEDIA.build()
    MEDIA.check()
    scope = validate(value)
    previous = json.loads(V10_RUNBOOK.read_text(encoding="utf-8"))
    gate = value["stager"]["gate"]
    runbook = {
        **previous,
        "status": "ready-G5-replay-with-address-qualified-hybrid-DMA",
        "artifact_set_sha256": value["artifact_set_sha256"],
        "product_d81": MEDIA.PRODUCT_D81.relative_to(ROOT).as_posix(),
        "work_d81": MEDIA.WORK_D81.relative_to(ROOT).as_posix(),
        "mount_descriptor": MEDIA.MOUNT.relative_to(ROOT).as_posix(),
        "supersedes": bind(V10_RUNBOOK),
        "hybrid_transport": {
            "chip_roles": [1, 2, 3],
            "chip_transport": "normal-F018B-D700-20-bit",
            "attic_roles": [4, 5, 6, 7, 8],
            "attic_transport": "Enhanced-F018B-D705-28-bit",
            "completion": (
                "poison-once; ordered target readback; immutable Enhanced "
                "readback retry until content match or 192 raster wraps"),
            "gate": gate["linked_transport"],
        },
        "tool_fix_scope": scope,
    }
    RUNBOOK.write_bytes(json_bytes(runbook))
    receipt = {
        "format": "lisp65-c2-lite-g5-hybrid-dma-repack-v1",
        "recorded_on": "2026-07-26",
        "status": "passed-host-repack-hardware-not-run",
        "cause": cause,
        "gate_first_red": bind(GATE_FIRST_RED),
        "candidate": {
            "manifest": bind(MEDIA.MANIFEST),
            "runbook": bind(RUNBOOK),
            "descriptor": bind(MEDIA.DESCRIPTOR),
            "stager": bind(MEDIA.STAGER),
            "stager_elf": bind(Path(str(MEDIA.STAGER) + ".elf")),
            "stager_map": bind(MEDIA.STAGER_MAP),
            "product_d81": bind(MEDIA.PRODUCT_D81),
            "work_d81": bind(MEDIA.WORK_D81),
            "mount": bind(MEDIA.MOUNT),
        },
        "fix": {
            "classification": (
                "G5 acceptance-tool address-domain transport model"),
            "mechanism": (
                "normal D700/F018B for 20-bit Chip-RAM roles; Enhanced "
                "D705/F018B with content-defined target readback retry for "
                "28-bit Attic roles"),
            "gate": gate,
            "scope": scope,
        },
        "execution_accounting": value["execution_accounting"],
        "claim_limit": (
            "G5 acceptance-tool identity only. No product compile, product "
            "link, product-byte change, G5/G6 or release claim occurred."),
    }
    RECEIPT.write_bytes(json_bytes(receipt))
    return receipt


def check() -> dict[str, Any]:
    value = MEDIA.check()
    scope = validate(value)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "passed-host-repack-hardware-not-run"
        and receipt["gate_first_red"] == bind(GATE_FIRST_RED)
        and receipt["candidate"]["manifest"] == bind(MEDIA.MANIFEST)
        and receipt["candidate"]["runbook"] == bind(RUNBOOK)
        and receipt["candidate"]["product_d81"] == bind(MEDIA.PRODUCT_D81)
        and receipt["fix"]["scope"] == scope,
        "G5 hybrid-DMA receipt drift")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    configure()
    value = build() if args.action == "build" else check()
    if args.action == "build":
        check()
    print(json.dumps({
        "status": value["status"],
        "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        "candidate": value["candidate"]["product_d81"],
        "fix": value["fix"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RepackError, MEDIA.MediaError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-lite-media-g5-hybrid-dma-repack: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
