#!/usr/bin/env python3
"""Finish the Link-61 C1 carrier identity without rebuilding any bytes.

The reusable constructor intentionally retains Link-60 labels.  This
artifact-only step gives the already verified Link-61 carrier unambiguous
names and updates its receipt.  It runs no compiler, linker, or hardware.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link60 as BASE  # noqa: E402
import c2_c1_freezer_carrier_link61 as LINK61  # noqa: E402


OUT = LINK61.OUT
RECEIPT = LINK61.RECEIPT
OLD_MAIN = OUT / (
    "runtime-overlays-session-c1-freezer-link60-stage-bound.bin")
OLD_REGION1 = OUT / (
    "runtime-overlays-session-c1-freezer-link60-region1.bin")
OLD_MANIFEST = OUT / (
    "runtime-overlays-session-c1-freezer-link60-stage-bound.json")
MAIN = OUT / "runtime-overlays-session-c1-freezer-link61-stage-bound.bin"
REGION1 = OUT / "runtime-overlays-session-c1-freezer-link61-region1.bin"
MANIFEST = OUT / (
    "runtime-overlays-session-c1-freezer-link61-stage-bound.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def rename_once(old: Path, new: Path) -> None:
    if new.is_file() and not old.exists():
        return
    require(old.is_file() and not new.exists(),
            f"carrier identity rename is ambiguous: {old} -> {new}")
    old.rename(new)


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest_source = (
        OLD_MANIFEST if OLD_MANIFEST.is_file() else MANIFEST)
    manifest = json.loads(manifest_source.read_text(encoding="utf-8"))
    require(
        receipt["status"]
        == "passed-Link61-capacity-and-gates-awaiting-hardware"
        and receipt["construction"]["compiler_runs"] == 0
        and receipt["construction"]["linker_runs"] == 0
        and receipt["construction"]["hardware_runs"] == 0
        and manifest["outer_link60_stage_binding"]["match"]
        and manifest["outer_link60_stage_binding"]["session_crc16"]
            == "0x4e98"
        and manifest["outer_link60_stage_binding"]["tail_width_bytes"] == 6,
        "unfinished Link-61 carrier authority drift")

    os.chmod(OUT, 0o755)
    rename_once(OLD_MAIN, MAIN)
    rename_once(OLD_REGION1, REGION1)
    rename_once(OLD_MANIFEST, MANIFEST)

    manifest["format"] = (
        "lisp65-C1-Freezer-Link61-v4-rebound-stage-bound-family-v1")
    manifest["status"] = (
        "passed-nonpromotable-Link61-carrier-awaiting-hardware")
    manifest["outer_link61_stage_binding"] = manifest.pop(
        "outer_link60_stage_binding")
    relocation = manifest["relocation_rebind"]
    relocation["external_sites_already_link61_exact"] = relocation.pop(
        "external_sites_already_link60_exact")
    for row in relocation["sites"]:
        row["link61_encoded"] = row.pop("link60_encoded")
        row["link61_value"] = row.pop("link60_value")
    for row in manifest["slice_provenance"]:
        row["source"] = row["source"].replace("Link60", "Link61")
    os.chmod(MANIFEST, 0o644)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    os.chmod(RECEIPT, 0o644)
    receipt["artifacts"]["session_main"] = BASE.bind(MAIN)
    receipt["artifacts"]["session_region1"] = BASE.bind(REGION1)
    receipt["artifacts"]["manifest"] = BASE.bind(MANIFEST)
    authority = receipt["authority"]
    authority["immutable_link61_product"] = authority.pop(
        "immutable_link60_product")
    authority["link61_elf"] = authority.pop("link60_elf")
    authority["link61_receipt"] = authority.pop("link60_receipt")
    authority["link61_rebind_driver"] = BASE.bind(
        ROOT / "tools/host-lisp/c2_c1_freezer_carrier_link61.py")
    authority["artifact_identity_completion"] = BASE.bind(Path(__file__))
    receipt["capacity"]["deployed_resident_authority"] = "immutable Link 61"
    construction = receipt["construction"]
    construction["region1_byteidentical_Link61"] = construction.pop(
        "region1_byteidentical_Link60")
    tail = manifest["outer_link61_stage_binding"]
    receipt["proof"]["post_RTS_tail"] = {
        "bytes": tail["tail_width_bytes"],
        "slot": tail["tail_slot"],
        "bytes_little_endian": tail["tail_bytes_little_endian"],
        "value": tail["tail_word"],
        "unreachable_after_RTS": True,
    }
    receipt["proof"]["verifier_header"] = "byteidentical-Link61"
    receipt["execution_accounting"]["artifact_identity_completions"] = 1
    receipt["execution_accounting"]["additional_compiler_runs"] = 0
    receipt["execution_accounting"]["additional_linker_runs"] = 0
    receipt["execution_accounting"]["additional_hardware_runs"] = 0
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-carrier-link61-artifact-completion: PASS "
        "tail=6 product-delta=0 compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-c1-freezer-carrier-link61-artifact-completion: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
