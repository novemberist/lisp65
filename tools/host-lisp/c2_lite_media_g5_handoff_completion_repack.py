#!/usr/bin/env python3
"""Build/check the G5 media identity with a completion-bound product handoff.

The v9 replay staged Bank 2, C2D and the boot stage byte-for-byte, entered the
profile-bound $2023 product entry, and later returned to the cold stager.  Its
relocated trampoline submitted the Bank-4 -> Bank-0 DMA job and immediately
jumped into the destination.  This acceptance-tool-only repack chains a
one-byte completion publication after that copy and waits for the publication
before entering the unchanged product.
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
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.2/acceptance/g5/handoff-completion-repack-v10"
RECEIPT = BUILD / "g5-handoff-completion-repack-receipt.json"
RUNBOOK = BUILD / "g5-runbook.json"
R5 = ROOT / "build/c2.2/acceptance/r5"
R5_PREFLIGHT = R5 / "r5-preflight-receipt.json"
V9 = ROOT / "build/c2.2/acceptance/g5/entry-bound-repack-v9"
V9_MANIFEST = V9 / "candidate-manifest.json"
V9_RUNBOOK = V9 / "g5-runbook.json"
V9_ELF = Path(str(V9 / "autoboot.c65") + ".elf")
V9_CAPTURE = ROOT / "build/c2.2/acceptance/g5/replay-v9-entry-bound/first-red"


class RepackError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepackError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"handoff-completion authority absent: {path}")
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


def v9_attribution() -> dict[str, Any]:
    previous = json.loads(V9_MANIFEST.read_text(encoding="utf-8"))
    truth = ElfTruth.read(
        V9_ELF, llvm_readobj=MEDIA.CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    chain = truth.section_bytes(".r3_chain_trampoline")
    immediate = bytes.fromhex("8d00d74c2320")
    pairs = (
        (V9_CAPTURE / "bank2-full.bin",
         R5 / "product/01-bank2-static-code.bin"),
        (V9_CAPTURE / "bank5-c2d.bin",
         R5 / "product/09-initial.c2d-v6.bin"),
        (V9_CAPTURE / "bank5-bootstage.bin",
         R5 / "product/08-bootstage.bin"),
    )
    require(
        previous["stager"]["product_entry"] == "0x2023"
        and chain.endswith(immediate)
        and all(left.read_bytes() == right.read_bytes()
                for left, right in pairs),
        "v9 handoff first-red attribution drift")
    return {
        "status": "hardware-first-red-entered-before-product-copy-completion",
        "staged_targets": {
            "bank2": "byte-identical",
            "bank5_c2d": "byte-identical",
            "bank5_bootstage": "byte-identical",
        },
        "old_terminal_bytes": immediate.hex(),
        "old_semantics": "submit-D700-then-immediate-JMP-$2023",
        "postmortem": (
            "product chain returned after the asynchronous copy had later "
            "completed; retained status cells were no longer authoritative"
        ),
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    r5 = json.loads(R5_PREFLIGHT.read_text(encoding="utf-8"))
    before = {
        row["role"]: row["sha256"] for row in r5["materialized_artifacts"]}
    after = {row["role"]: row["sha256"] for row in value["artifacts"]}
    changed = {role for role in before if before[role] != after[role]}
    gate = value["stager"]["gate"]["chain_handoff"]
    require(
        changed == {
            "cold-stager", "product-d81", "product-mount-descriptor"}
        and value["execution_accounting"]["product_compiler_runs"] == 0
        and value["execution_accounting"]["product_linker_runs"] == 0
        and value["execution_accounting"]["hardware_runs"] == 0
        and gate["status"].endswith("ordered-memory-completion")
        and gate["product_entry"] == "0x2023"
        and gate["completion_marker"] == "0x1858"
        and gate["completion_value"] == "0xa5"
        and gate["ordered_jobs"] == 2
        and gate["source_and_ELF_mutations_rejected"] == 8,
        "G5 handoff-completion repack qualification drift")
    return {
        "changed_roles": sorted(changed),
        "unchanged_roles": len(before) - len(changed),
        "product_compiler_runs": 0,
        "product_linker_runs": 0,
        "product_byte_changes": 0,
    }


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "G5 handoff-completion repack is one-shot")
    for authority in (
        R5_PREFLIGHT, V9_MANIFEST, V9_RUNBOOK, V9_ELF,
        *(left for left, _ in (
            (V9_CAPTURE / "bank2-full.bin", None),
            (V9_CAPTURE / "bank5-c2d.bin", None),
            (V9_CAPTURE / "bank5-bootstage.bin", None),
        )),
    ):
        require(authority.is_file(), f"required predecessor absent: {authority}")
    attribution = v9_attribution()
    value = MEDIA.build()
    MEDIA.check()
    scope = validate(value)
    previous = json.loads(V9_RUNBOOK.read_text(encoding="utf-8"))
    runbook = {
        **previous,
        "status": "ready-G5-replay-after-product-handoff-completion",
        "artifact_set_sha256": value["artifact_set_sha256"],
        "product_d81": MEDIA.PRODUCT_D81.relative_to(ROOT).as_posix(),
        "work_d81": MEDIA.WORK_D81.relative_to(ROOT).as_posix(),
        "mount_descriptor": MEDIA.MOUNT.relative_to(ROOT).as_posix(),
        "supersedes": bind(V9_RUNBOOK),
        "handoff_completion_fix": value["stager"]["gate"]["chain_handoff"],
        "tool_fix_scope": scope,
    }
    RUNBOOK.write_bytes(json_bytes(runbook))
    receipt = {
        "format": "lisp65-c2-lite-g5-handoff-completion-repack-v1",
        "recorded_on": "2026-07-26",
        "status": "passed-host-repack-hardware-not-run",
        "cause": attribution,
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
            "classification": "G5 acceptance-tool handoff ordering",
            "mechanism": (
                "normal-F018B product-copy job chains a one-byte memory "
                "publication; relocated trampoline waits for that byte"
            ),
            "gate": value["stager"]["gate"]["chain_handoff"],
            "scope": scope,
        },
        "execution_accounting": value["execution_accounting"],
        "claim_limit": (
            "G5 acceptance-tool identity only. No product compile, product "
            "link, product-byte change, G5/G6 or release claim occurred."
        ),
    }
    RECEIPT.write_bytes(json_bytes(receipt))
    return receipt


def check() -> dict[str, Any]:
    value = MEDIA.check()
    scope = validate(value)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "passed-host-repack-hardware-not-run"
        and receipt["candidate"]["manifest"] == bind(MEDIA.MANIFEST)
        and receipt["candidate"]["runbook"] == bind(RUNBOOK)
        and receipt["candidate"]["product_d81"] == bind(MEDIA.PRODUCT_D81)
        and receipt["fix"]["scope"] == scope,
        "G5 handoff-completion receipt drift")
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
            "c2-lite-media-g5-handoff-completion-repack: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
