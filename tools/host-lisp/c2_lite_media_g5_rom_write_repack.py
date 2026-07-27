#!/usr/bin/env python3
"""Build/check the G5 media identity with ROM backing-bank writes enabled.

The normal-F018B/D700 replay and its I/O-personality A/B both reached live
DMA registers while Bank 2 remained byte-for-byte old.  The hardware-proven
Chip-RAM prefilter differs at one ownership boundary: it invokes the
idempotent HYPPO $D641/A=$02 service before writing ROM backing banks 2/3.
This tool gives that acceptance-stager-only correction a fresh media identity.
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


BUILD = ROOT / "build/c2.2/acceptance/g5/rom-write-enable-repack-v8"
RECEIPT = BUILD / "g5-rom-write-enable-repack-receipt.json"
RUNBOOK = BUILD / "g5-runbook.json"
R5_PREFLIGHT = ROOT / "build/c2.2/acceptance/r5/r5-preflight-receipt.json"
V7_REPACK = (
    ROOT / "build/c2.2/acceptance/g5/normal-dma-repack-v7/"
    "g5-repack-receipt.json"
)
V7_HARDWARE = (
    ROOT / "build/c2.2/acceptance/g5/replay-v7/"
    "hardware-first-red-receipt.json"
)
IO_HARDWARE = (
    ROOT / "build/c2.2/acceptance/g5/io-trigger-attribution-v1/"
    "hardware-run-01/hardware-receipt.json"
)
IO_HOST = (
    ROOT / "build/c2.2/acceptance/g5/io-trigger-attribution-v1/"
    "host-attribution.json"
)
CHIPRAM_MAIN = ROOT / "scripts/c2-lite-chipram-proof-main.c"
CHIPRAM_CONTROL = ROOT / "scripts/c2-lite-chipram-proof-control.s"
STAGER_CONTROL = ROOT / "scripts/r3-rom-write-enable.s"
PREVIOUS_RUNBOOK = (
    ROOT / "build/c2.2/acceptance/g5/normal-dma-repack-v7/"
    "g5-runbook.json"
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
            f"ROM-write repack binding absent: {path}")
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


def source_attribution() -> dict[str, Any]:
    proof_main = CHIPRAM_MAIN.read_text(encoding="utf-8")
    proof_control = CHIPRAM_CONTROL.read_text(encoding="utf-8")
    stager = MEDIA.STAGER_C.read_text(encoding="utf-8")
    control = STAGER_CONTROL.read_text(encoding="utf-8")
    proof_order = (
        proof_main.index("REG8(0xd02f) = 0x47u;")
        < proof_main.index("c2lt_rom_write_enable();")
        < proof_main.index("crc = stage_full_bank(2u,")
    )
    stager_start = stager.index(
        "profile_build_id = rd32(descriptor + 12);")
    stager_io = stager.index("    io_enable();", stager_start)
    stager_enable = stager.index(
        "    r3_rom_write_enable();", stager_io)
    stager_stage = stager.index(
        "    if (!restage_and_reverify(profile_build_id))", stager_enable)
    exact = "\tlda #$02\n\tsta $d641\n\tnop\n\tldz #$00\n\trts\n"
    require(
        proof_order
        and "c2lt_rom_write_enable:" in proof_control
        and exact in proof_control
        and stager_start < stager_io < stager_enable < stager_stage
        and "r3_rom_write_enable:" in control and exact in control,
        "ROM backing-bank source attribution drift")
    return {
        "status": "passed-proven-service-at-cold-stage-ownership-boundary",
        "hardware_proof_order": [
            "MEGA65-I/O-personality",
            "idempotent-$D641-A=$02-service",
            "Bank-2-stage",
            "Bank-3-stage",
        ],
        "acceptance_stager_order": [
            "validated-media-descriptor",
            "MEGA65-I/O-personality",
            "idempotent-$D641-A=$02-service",
            "first-stage-role",
        ],
        "service_opcode_source_identical": True,
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    r5 = json.loads(R5_PREFLIGHT.read_text(encoding="utf-8"))
    v7 = json.loads(V7_HARDWARE.read_text(encoding="utf-8"))
    io = json.loads(IO_HARDWARE.read_text(encoding="utf-8"))
    before = {
        row["role"]: row["sha256"] for row in r5["materialized_artifacts"]}
    after = {
        row["role"]: row["sha256"] for row in value["artifacts"]}
    changed = {role for role in before if before[role] != after[role]}
    gate = value["stager"]["gate"]
    require(
        v7["status"] == "first-red-normal-dma-write-not-visible"
        and io["status"]
        == "hardware-rejected-io-visibility-and-personality-hypothesis"
        and changed == {
            "cold-stager", "product-d81", "product-mount-descriptor"}
        and value["status"] == "passed-complete-C2-lite-two-media-product"
        and value["execution_accounting"]["product_compiler_runs"] == 0
        and value["execution_accounting"]["product_linker_runs"] == 0
        and value["execution_accounting"]["hardware_runs"] == 0
        and gate["ordered_chain_descriptor_bytes"] == 24
        and gate["linked_transport"][
            "normal_f018b_d700_trigger_occurrences"] == 1
        and gate["linked_transport"][
            "enhanced_d705_trigger_occurrences"] == 0
        and gate["rom_backing_write_enable"]["status"]
        == "passed-before-first-stage-role"
        and gate["rom_backing_write_enable"]["symbol"]["bytes"] == 9
        and gate["rom_backing_write_enable"][
            "source_and_opcode_mutations"] == 6,
        "ROM backing-bank G5 repack qualification drift")
    return {
        "changed_roles": sorted(changed),
        "unchanged_roles": len(before) - len(changed),
    }


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "G5 ROM-write-enable repack is one-shot")
    for authority in (
        R5_PREFLIGHT, V7_REPACK, V7_HARDWARE, IO_HOST, IO_HARDWARE,
        PREVIOUS_RUNBOOK,
    ):
        require(authority.is_file(), f"required predecessor absent: {authority}")
    source = source_attribution()
    value = MEDIA.build()
    MEDIA.check()
    scope = validate(value)
    previous = json.loads(PREVIOUS_RUNBOOK.read_text(encoding="utf-8"))
    runbook = {
        **previous,
        "format": "lisp65-c2-lite-G5-runbook-v3",
        "version": 3,
        "status": "ready-replay-after-ROM-backing-write-enable",
        "artifact_set_sha256": value["artifact_set_sha256"],
        "product_d81": MEDIA.PRODUCT_D81.relative_to(ROOT).as_posix(),
        "work_d81": MEDIA.WORK_D81.relative_to(ROOT).as_posix(),
        "mount_descriptor": MEDIA.MOUNT.relative_to(ROOT).as_posix(),
        "supersedes": bind(PREVIOUS_RUNBOOK),
        "root_cause_authority": {
            "normal_D700_first_red": bind(V7_HARDWARE),
            "io_MAP_hypothesis_rejected": bind(IO_HARDWARE),
            "hardware_proven_chipram_service": [
                bind(CHIPRAM_MAIN), bind(CHIPRAM_CONTROL),
            ],
        },
        "tool_fix_scope": {
            **scope,
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_byte_changes": 0,
        },
    }
    RUNBOOK.write_text(
        json.dumps(runbook, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": "lisp65-c2-lite-g5-rom-backing-write-repack-v1",
        "recorded_on": "2026-07-26",
        "status": "passed-host-repack-hardware-not-run",
        "cause": {
            "classification": (
                "acceptance stager omitted ROM backing-bank write enable"
            ),
            "normal_D700_first_red": bind(V7_HARDWARE),
            "io_MAP_hypothesis_rejected": bind(IO_HARDWARE),
            "source_attribution": source,
        },
        "authority": {
            "R5_preflight": bind(R5_PREFLIGHT),
            "v7_repack": bind(V7_REPACK),
            "io_host_attribution": bind(IO_HOST),
            "hardware_proven_chipram_main": bind(CHIPRAM_MAIN),
            "hardware_proven_chipram_control": bind(CHIPRAM_CONTROL),
        },
        "candidate": {
            "manifest": bind(MEDIA.MANIFEST),
            "runbook": bind(RUNBOOK),
            "stager": bind(MEDIA.STAGER),
            "stager_elf": bind(Path(str(MEDIA.STAGER) + ".elf")),
            "stager_map": bind(MEDIA.STAGER_MAP),
            "product_d81": bind(MEDIA.PRODUCT_D81),
            "work_d81": bind(MEDIA.WORK_D81),
            "mount": bind(MEDIA.MOUNT),
        },
        "fix": {
            "symbol": value["stager"]["gate"][
                "rom_backing_write_enable"]["symbol"],
            "trap": "$D641 A=$02 plus mandatory following NOP",
            "placement": "after descriptor validation, before first stage role",
            "normal_DMA_path_unchanged": True,
            "product_bytes_changed": 0,
            "scope": scope,
        },
        "gates": {
            "ROM_write_boundary": value["stager"]["gate"][
                "rom_backing_write_enable"],
            "transport": value["stager"]["gate"]["linked_transport"],
            "complete_media": value["status"],
        },
        "execution_accounting": value["execution_accounting"],
        "claim_limit": (
            "G5 acceptance-tool identity only. No product compile, product "
            "link, product-byte change, G5/G6 or release claim occurred."
        ),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def check() -> dict[str, Any]:
    value = MEDIA.check()
    scope = validate(value)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "passed-host-repack-hardware-not-run"
        and receipt["candidate"]["manifest"] == bind(MEDIA.MANIFEST)
        and receipt["candidate"]["runbook"] == bind(RUNBOOK)
        and receipt["candidate"]["stager"] == bind(MEDIA.STAGER)
        and receipt["candidate"]["product_d81"] == bind(MEDIA.PRODUCT_D81)
        and receipt["fix"]["scope"] == scope,
        "G5 ROM-write-enable repack receipt drift")
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
            "c2-lite-media-g5-rom-write-repack: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
