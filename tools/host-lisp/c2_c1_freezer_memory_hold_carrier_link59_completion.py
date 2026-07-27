#!/usr/bin/env python3
"""Normalize the already completed Link-59 C1 carrier artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_memory_hold_carrier_link59 as LINK  # noqa: E402


FIRST_RED = LINK.EVIDENCE / (
    "c2.2-link59-c1-freezer-memory-hold-carrier-packaging-first-red.json")
OLD_IMAGE = LINK.OUT / (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link58-rebound-stage-bound.bin")
OLD_MANIFEST = LINK.OUT / (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link58-rebound-stage-bound.json")
IMAGE = LINK.OUT / (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link59-rebound-stage-bound.bin")
MANIFEST = LINK.OUT / (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link59-rebound-stage-bound.json")
EXPECTED = {
    OLD_IMAGE:
        "f93dd547ae8a22b2fe55f9461d3effdaca5c8f8cf286138ae34e278329e8e61f",
    OLD_MANIFEST:
        "a25ef460ba2398834de38a0f5d9c3dadab5bbdd549389cf243aa07a919f1e4a3",
    LINK.RECEIPT:
        "f84a4c2679817e3268b5c5fd45d45543ee9b6efd854699f2d5a36d4d726bdaa4",
}


def main() -> int:
    old_names = OLD_IMAGE.exists() and OLD_MANIFEST.exists()
    new_names = IMAGE.exists() and MANIFEST.exists()
    LINK.require(
        FIRST_RED.is_file() and old_names != new_names,
        "Link-59 carrier completion is one-shot or First Red absent",
    )
    inputs = {
        (OLD_IMAGE if old_names else IMAGE):
            EXPECTED[OLD_IMAGE],
        (OLD_MANIFEST if old_names else MANIFEST):
            EXPECTED[OLD_MANIFEST],
        LINK.RECEIPT: EXPECTED[LINK.RECEIPT],
    }
    for path, digest in inputs.items():
        LINK.require(
            path.is_file() and LINK.BASE.sha(path) == digest,
            f"Link-59 carrier completion input drift: {path}",
        )
    os.chmod(LINK.OUT, 0o755)
    if old_names:
        os.replace(OLD_IMAGE, IMAGE)
        os.replace(OLD_MANIFEST, MANIFEST)
    os.chmod(MANIFEST, 0o644)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["format"] = (
        "lisp65-C1-Freezer-memory-hold-Link59-rebound-"
        "stage-bound-family-v1"
    )
    manifest["outer_link59_stage_binding"] = manifest.pop(
        "outer_link58_stage_binding"
    )
    for row in manifest["slice_provenance"]:
        row["source"] = row["source"].replace("Link58", "Link59")
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parsed = LINK.BASE.R.validate_image(
        IMAGE.read_bytes(),
        expected_build_id=int(manifest["profile_build_id"]),
        expected_vma=0xC356,
        max_slice_bytes=1792,
        format_version=3,
    )
    LINK.require(
        IMAGE.stat().st_size == 65438
        and LINK.BASE.S.crc16(IMAGE.read_bytes()) == 0x8BC9
        and len(parsed.slices) == 48,
        "Link-59 normalized carrier validation red",
    )
    os.chmod(LINK.RECEIPT, 0o644)
    receipt = json.loads(LINK.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2.2-C1-Freezer-memory-hold-Link59-carrier-receipt-v1"
    )
    receipt["authority"]["immutable_link59_product"] = receipt[
        "authority"
    ].pop("immutable_link58_product")
    receipt["authority"]["link59_elf"] = receipt["authority"].pop(
        "link58_elf"
    )
    receipt["authority"]["link59_receipt"] = receipt["authority"].pop(
        "link58_receipt"
    )
    receipt["authority"]["link58_carrier_precedent"] = receipt[
        "authority"
    ].pop("structured_rebind_precedent")
    receipt["authority"]["packaging_first_red"] = LINK.BASE.bind(FIRST_RED)
    receipt["artifacts"]["session_family"] = LINK.BASE.bind(IMAGE)
    receipt["artifacts"]["manifest"] = LINK.BASE.bind(MANIFEST)
    receipt["capacity"]["deployed_resident_authority"] = "immutable Link-59"
    receipt["construction"]["whole_family_crc16"] = "0x8bc9"
    receipt["construction"]["external_relocation_sites_rebound"] = 23
    receipt["proof"]["structured_relocation_mutation_count"] = 23
    receipt["next_gate"] = (
        "prepare the Link-59-bound nonpromotable hardware fixture for "
        "cutpoint 3 repeat and cutpoint 4"
    )
    LINK.RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for path in LINK.OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(LINK.RECEIPT, 0o444)
    os.chmod(LINK.OUT, 0o555)
    print(
        "c2-c1-freezer-memory-hold-carrier-link59-completion: PASS "
        "session=65438 crc=8bc9 rebindings=23 hardware=not-run"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LINK.Link59CarrierError,
        LINK.BASE.CarrierError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-memory-hold-carrier-link59-completion: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
