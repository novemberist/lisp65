#!/usr/bin/env python3
"""Give the bundled Link-66 C1 carrier its final artifact identity."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_bundled_session_carrier_link66 as LINK66  # noqa: E402
import c2_c1_freezer_carrier_link60 as BASE  # noqa: E402


OUT = LINK66.OUT
RECEIPT = LINK66.RECEIPT
OLD_MAIN = OUT / (
    "runtime-overlays-session-c1-freezer-link60-stage-bound.bin")
OLD_REGION1 = OUT / (
    "runtime-overlays-session-c1-freezer-link60-region1.bin")
OLD_MANIFEST = OUT / (
    "runtime-overlays-session-c1-freezer-link60-stage-bound.json")
MAIN = OUT / (
    "runtime-overlays-session-c1-bundled-link66-stage-bound.bin")
REGION1 = OUT / (
    "runtime-overlays-session-c1-bundled-link66-region1.bin")
MANIFEST = OUT / (
    "runtime-overlays-session-c1-bundled-link66-stage-bound.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def rename_once(old: Path, new: Path) -> None:
    require(old.is_file() and not new.exists(),
            f"carrier identity rename is ambiguous: {old} -> {new}")
    old.rename(new)


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest = json.loads(OLD_MANIFEST.read_text(encoding="utf-8"))
    binding = manifest["outer_link60_stage_binding"]
    session = json.loads(
        (LINK66.LINK / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    expected_crc = f"0x{int(session['storage']['crc16']):04x}"
    require(
        receipt["status"]
        == "passed-Link66-bundled-session-capacity-and-gates-"
           "awaiting-hardware"
        and receipt["construction"]["compiler_runs"] == 0
        and receipt["construction"]["linker_runs"] == 0
        and receipt["construction"]["hardware_runs"] == 0
        and receipt["construction"]["region1_byteidentical_Link66"]
        and binding["match"]
        and binding["session_crc16"] == expected_crc
        and binding["tail_width_bytes"] >= 2,
        "unfinished bundled Link-66 carrier authority drift")

    os.chmod(OUT, 0o755)
    rename_once(OLD_MAIN, MAIN)
    rename_once(OLD_REGION1, REGION1)
    rename_once(OLD_MANIFEST, MANIFEST)

    manifest["format"] = (
        "lisp65-C1-bundled-Link66-v4-rebound-stage-bound-family-v1")
    manifest["status"] = (
        "passed-nonpromotable-Link66-bundled-carrier-awaiting-hardware")
    manifest["outer_link66_stage_binding"] = manifest.pop(
        "outer_link60_stage_binding")
    relocation = manifest["relocation_rebind"]
    relocation["external_sites_already_link66_exact"] = relocation.pop(
        "external_sites_already_link60_exact")
    for row in relocation["sites"]:
        row["link66_encoded"] = row.pop("link60_encoded")
        row["link66_value"] = row.pop("link60_value")
    for row in manifest["slice_provenance"]:
        row["source"] = row["source"].replace("Link60", "Link66")
    os.chmod(MANIFEST, 0o644)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    os.chmod(RECEIPT, 0o644)
    receipt["artifacts"]["session_main"] = BASE.bind(MAIN)
    receipt["artifacts"]["session_region1"] = BASE.bind(REGION1)
    receipt["artifacts"]["manifest"] = BASE.bind(MANIFEST)
    authority = receipt["authority"]
    authority["immutable_link66_product"] = authority.pop(
        "immutable_link60_product")
    authority["link66_elf"] = authority.pop("link60_elf")
    authority["link66_receipt"] = authority.pop("link60_receipt")
    authority["artifact_identity_completion"] = BASE.bind(Path(__file__))
    receipt["capacity"]["deployed_resident_authority"] = "immutable Link 66"
    tail = manifest["outer_link66_stage_binding"]
    receipt["proof"]["post_RTS_tail"] = {
        "bytes": tail["tail_width_bytes"],
        "slot": tail["tail_slot"],
        "bytes_little_endian": tail["tail_bytes_little_endian"],
        "value": tail["tail_word"],
        "unreachable_after_RTS": True,
    }
    receipt["proof"]["verifier_header"] = "byteidentical-Link66"
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
        "c2-c1-bundled-session-carrier-link66-artifact-completion: PASS "
        f"tail={tail['tail_width_bytes']} product-delta=0 "
        "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-c1-bundled-session-carrier-link66-artifact-completion: "
            "FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
