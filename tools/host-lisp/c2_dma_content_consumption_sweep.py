#!/usr/bin/env python3
"""One-time ELF inventory of every linked D700/D705 submission site."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CONTRACT = ROOT / "config/c2-dma-content-consumption-sweep.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-dma-content-consumption-broaden-once-sweep.json"
)


class SweepError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SweepError(message)


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def write(value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RECEIPT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(RECEIPT)


def executable_hits(path: Path, opcodes: dict[str, str]) -> list[dict[str, Any]]:
    truth = ElfTruth.read(
        path, llvm_readobj=READOBJ, include_section_data=True)
    functions = [
        symbol for symbol in truth.symbols
        if symbol.symbol_type == "Function" and symbol.bytes > 0
        and symbol.section not in ("Absolute", "Undefined")
    ]
    rows: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes == 0:
            continue
        body = truth.section_bytes(section.name)
        for register, encoded in opcodes.items():
            needle = bytes.fromhex(encoded)
            cursor = 0
            while True:
                offset = body.find(needle, cursor)
                if offset < 0:
                    break
                address = section.address + offset
                owners = [
                    symbol for symbol in functions
                    if symbol.section == section.name
                    and symbol.value <= address < symbol.value + symbol.bytes
                ]
                require(len(owners) == 1,
                        f"submission owner is not unique: {path}:{address:04x}")
                rows.append({
                    "address": address,
                    "address_hex": f"${address:04X}",
                    "owner": owners[0].name,
                    "owner_address": owners[0].value,
                    "owner_bytes": owners[0].bytes,
                    "register": register,
                    "section": section.name,
                })
                cursor = offset + 1
    rows.sort(key=lambda row: (row["address"], row["register"]))
    counters: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        key = (row["owner"], row["register"])
        row["ordinal"] = counters[key]
        counters[key] += 1
    return rows


def main() -> int:
    receipt: dict[str, Any] = {
        "format": "lisp65-c2-dma-content-consumption-sweep-receipt-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED",
    }
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        require(contract["format"]
                == "lisp65-c2-dma-content-consumption-sweep-v1"
                and contract["status"] == "owner-commissioned-broaden-once",
                "sweep contract identity drift")
        authorities: dict[str, Any] = {
            "contract": bind(CONTRACT),
            "driver": bind(Path(__file__).resolve()),
        }
        actual: dict[str, list[dict[str, Any]]] = {}
        for name, relative in contract["images"].items():
            path = ROOT / relative
            require(path.is_file(), f"linked sweep image absent: {relative}")
            authorities[f"elf:{name}"] = bind(path)
            actual[name] = executable_hits(path, contract["trigger_opcodes"])

        expected: dict[tuple[str, str, str, int], dict[str, Any]] = {}
        for row in contract["sites"]:
            key = (row["image"], row["owner"], row["register"], row["ordinal"])
            require(key not in expected, f"duplicate contracted site: {key}")
            expected[key] = row
        seen: set[tuple[str, str, str, int]] = set()
        inventory: list[dict[str, Any]] = []
        for image, rows in actual.items():
            for linked in rows:
                key = (image, linked["owner"], linked["register"],
                       linked["ordinal"])
                require(key in expected, f"unclassified linked submission: {key}")
                spec = expected[key]
                seen.add(key)
                evidence = spec.get("evidence")
                if evidence:
                    source = ROOT / evidence["path"]
                    text = source.read_text(encoding="utf-8")
                    for token in evidence["all"]:
                        require(token in text,
                                f"oracle evidence drift: {key}: {token}")
                    authorities.setdefault(f"source:{evidence['path']}", bind(source))
                inventory.append({
                    **linked,
                    "image": image,
                    "classification": spec["classification"],
                    "oracle": spec["oracle"],
                    "evidence": evidence,
                })
        require(seen == set(expected),
                f"contracted submission absent: {sorted(set(expected) - seen)}")

        permitted = {
            "content-consumed",
            "verification-transport",
            "fire-and-forget-or-deferred-content",
            "predecessor-content-consumed-source-fixed",
        }
        require(all(row["classification"] in permitted for row in inventory),
                "unrecognized DMA consumption classification")
        gaps = [
            row for row in inventory
            if row["classification"] in {
                "content-consumed",
                "predecessor-content-consumed-source-fixed",
            }
            and (row["oracle"].startswith("missing") or not row["evidence"])
        ]
        protected = [
            row for row in inventory
            if row["classification"] in (
                "content-consumed", "verification-transport",
                "predecessor-content-consumed-source-fixed")
            and row not in gaps
        ]
        require(len(inventory) == 13, "linked submission count drift")
        receipt.update({
            "authorities": authorities,
            "inventory": inventory,
            "counts": {
                "linked_submission_sites": len(inventory),
                "content_consumed_gaps": len(gaps),
                "independently_protected_or_verifier": len(protected),
                "raw_fire_and_forget_or_deferred": sum(
                    row["classification"]
                    == "fire-and-forget-or-deferred-content"
                    for row in inventory),
                "predecessor_sites_fixed_in_source": sum(
                    row["classification"]
                    == "predecessor-content-consumed-source-fixed"
                    for row in inventory),
            },
            "gaps": [
                {
                    "image": row["image"],
                    "owner": row["owner"],
                    "register": row["register"],
                    "address": row["address_hex"],
                    "oracle": row["oracle"],
                } for row in gaps
            ],
            "claim_limit": {
                "product_link_built": False,
                "hardware_contacts": 0,
                "scope": (
                    "linked Link-90 predecessor Workbench plus fixed pre-Link-91 "
                    "Ship Runtime/stager; three predecessor gaps are bound to "
                    "their source fixes and require the authorized WPLTO"),
            },
        })
        if gaps:
            receipt["status"] = "FIRST-RED-UNPROTECTED-CONTENT-CONSUMERS"
            write(receipt)
            print("c2-dma-content-consumption-sweep: FIRST RED "
                  f"sites={len(inventory)} gaps={len(gaps)}")
            for row in receipt["gaps"]:
                print("  " + json.dumps(row, sort_keys=True))
            return 1
        receipt["status"] = "PASS"
        write(receipt)
        print("c2-dma-content-consumption-sweep: PASS "
              f"sites={len(inventory)} protected={len(protected)}")
        return 0
    except (SweepError, ElfTruthError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        receipt["status"] = "FIRST-RED-TOOL-OR-CONTRACT"
        receipt["error"] = str(error)
        write(receipt)
        print(f"c2-dma-content-consumption-sweep: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
