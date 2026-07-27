#!/usr/bin/env python3
"""Repair Link-60's Boot catalog from its immutable final ELF.

The product link itself compiled the canonical twelve-record Boot world and
stopped later at an inherited publish-last pin.  Its first artifact completion
reconstructed the predecessor eleven-record packer inventory, silently omitted
``c2-decode-03b`` and shifted the three following records.  This completion
reruns no compiler or linker: it copies the exact First-Red Link-60 artifact,
packs both families from that ELF under the canonical inventory, republishes
the existing 42-byte domain and reruns the full structural gate program.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_two_region_e000_s1_artifact_completion as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-60-boot-inventory-artifact-repair")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
RECEIPT = EVIDENCE / (
    "c2.2-product-link60-boot-inventory-artifact-repair-receipt.json")
FAULTY = ROOT / (
    "build/c2.2/substitution/"
    "product-link-60-two-region-e000-s1-completion")
FAILED_HARDWARE = ROOT / (
    "build/c2.2/"
    "c1-freezer-hardware-link60-cutpoints3-4-NONPROMOTABLE")
EXPECTED_NAMES = [
    "catalog-verifier",
    "record-verifier",
    "c2-decode-00",
    "c2-decode-00b",
    "c2-decode-01",
    "c2-decode-02a",
    "c2-decode-02b",
    "c2-decode-03",
    "c2-decode-03b",
    "bank3-stage-session",
    "resident-island-installer",
    "resident-island-image",
]


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"repair authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    require(
        not OUT.exists() and not RECEIPT.exists(),
        "Link-60 Boot-inventory repair is one-shot",
    )
    faulty_manifest_path = FAULTY / "runtime-overlays-boot-final.json"
    faulty_product = FAULTY / "lisp65-c2-substitution-linked.prg"
    boot_screen = FAILED_HARDWARE / "boot-screen.png"
    require(
        faulty_manifest_path.is_file()
        and faulty_product.is_file()
        and boot_screen.is_file(),
        "Link-60 catalog First-Red evidence is incomplete",
    )
    faulty_manifest = json.loads(
        faulty_manifest_path.read_text(encoding="utf-8"))
    faulty_names = [str(row["name"]) for row in faulty_manifest["slices"]]
    require(
        len(faulty_names) == 11
        and "c2-decode-03b" not in faulty_names
        and faulty_names[-3:] == [
            "bank3-stage-session",
            "resident-island-installer",
            "resident-island-image",
        ],
        "diagnosed eleven-record completion is not the bound First Red",
    )

    BASE.OUT = OUT
    BASE.PRODUCT = PRODUCT
    BASE.ELF = ELF
    BASE.MAP = MAP
    BASE.RECEIPT = RECEIPT
    result = BASE.main()
    require(result == 0, "canonical Link-60 artifact completion stopped")

    boot_path = OUT / "runtime-overlays-boot-final.json"
    session_path = OUT / "runtime-overlays-session-final.json"
    gate_path = OUT / "boot-inventory-one-truth-final.json"
    report_path = OUT / "link60-artifact-completion.json"
    boot = json.loads(boot_path.read_text(encoding="utf-8"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    names = [str(row["name"]) for row in boot["slices"]]
    slots = {str(row["name"]): int(row["id"]) for row in boot["slices"]}
    require(
        names == EXPECTED_NAMES
        and slots["c2-decode-03b"] == 8
        and slots["bank3-stage-session"] == 9
        and slots["resident-island-installer"] == 10
        and slots["resident-island-image"] == 11
        and int(boot["storage"]["size"]) == 19269
        and int(session["storage"]["size"]) == 64926
        and gate["status"]
            == "passed-profile-record-and-linked-slot-one-truth"
        and gate["profile_boot_family_slice_count"] == 12
        and gate["linked_slots"] == {"installer": 10, "carrier": 11}
        and len(gate["mutations_rejected"]) == 5,
        "repaired Boot inventory or permanent one-truth gate is red",
    )

    faulty_session = FAULTY / "runtime-overlays-session-final.bin"
    repaired_session = OUT / "runtime-overlays-session-final.bin"
    faulty_region1 = FAULTY / "runtime-overlays-session-final-region1.bin"
    repaired_region1 = OUT / "runtime-overlays-session-final-region1.bin"
    require(
        faulty_session.read_bytes() == repaired_session.read_bytes()
        and faulty_region1.read_bytes() == repaired_region1.read_bytes(),
        "Boot-only repair changed either Session region",
    )

    os.chmod(report_path, 0o644)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["format"] = "lisp65-c2-link60-boot-inventory-repair-v1"
    report["status"] = (
        "passed-canonical-twelve-record-repack-and-all-gates-green")
    report["boot_inventory_repair"] = {
        "cause":
            "the artifact-completion driver reconstructed the pre-Bank2 "
            "eleven-record structural inventory although the canonical "
            "compiler profile and final ELF contained c2-decode-03b",
        "compiler_or_product_link_rerun": False,
        "source_ELF_changed": False,
        "faulty_completion": {
            "product": bind(faulty_product),
            "boot_manifest": bind(faulty_manifest_path),
            "record_count": len(faulty_names),
            "record_names": faulty_names,
        },
        "repaired_completion": {
            "record_count": len(names),
            "record_names": names,
            "slots": slots,
            "boot_bytes": int(boot["storage"]["size"]),
            "boot_crc16": f"0x{int(boot['storage']['crc16']):04x}",
        },
        "session_regions_byteidentical": True,
        "permanent_gate": bind(gate_path),
        "hardware_first_red": {
            "screen": bind(boot_screen),
            "observed": "E2f",
            "classification":
                "record verifier rejected DATA_ONLY carrier at compiled "
                "installer slot before copy or READY",
            "fail_closed": "Island wiped; READY=0; no cutpoint armed",
        },
    }
    report["gates"]["boot_inventory_one_truth"] = gate["status"]
    write_json(report_path, report)

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link60-boot-inventory-repair-v1")
    receipt["status"] = (
        "passed-link60-canonical-boot-inventory-artifact-repair-"
        "awaiting-pure-replay")
    receipt["authority"]["link60_artifact_completion"] = bind(report_path)
    receipt["authority"]["repair_driver"] = bind(Path(__file__))
    receipt["boot_inventory_repair"] = report["boot_inventory_repair"]
    receipt["product_identity"]["runtime_boot"] = bind(
        OUT / "runtime-overlays-boot-final.bin")
    receipt["product_identity"]["runtime_session"] = bind(repaired_session)
    receipt["product_identity"]["runtime_session_region1"] = bind(
        repaired_region1)
    receipt["next_gate"] = (
        "pure full replay against this SHA-bound product and families; "
        "hardware remains blocked until that replay is green")
    write_json(RECEIPT, receipt)

    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link60-boot-inventory-artifact-repair: PASS "
        f"product={sha(PRODUCT)} boot={boot['storage']['size']}/"
        f"{int(boot['storage']['crc16']):04x} "
        "records=12 slots=stage9,installer10,carrier11 "
        "session=byteidentical compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RepairError, BASE.CompletionError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link60-boot-inventory-artifact-repair: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
