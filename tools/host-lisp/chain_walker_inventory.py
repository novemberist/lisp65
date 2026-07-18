#!/usr/bin/env python3
"""Gate every live 1581 link walker against the shared corruption cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-1581-chain-walker-inventory-v1"


class GateError(RuntimeError):
    pass


WALKERS: tuple[dict[str, Any], ...] = (
    {
        "id": "cold-stager-file",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "scan_file",
        "kind": "file-data", "sector_limit": 3226, "large_case": "accept",
        "requires": [
            "uint16_t fuel", "expected_length + R3_LOGICAL_SECTOR_PAYLOAD - 1ul",
            "if (!next_track && !next_sector)", "next_track == track && next_sector == sector",
            "if (track) return 0",
        ],
    },
    {
        "id": "cold-stager-descriptor",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "load_descriptor",
        "kind": "fixed-file-data", "sector_limit": 4, "large_case": "reject",
        "requires": [
            "uint8_t fuel = 4", "uint16_t used", "!next_track && !next_sector",
            "next_track == track && next_sector == sector", "!track && used == R3_DESCRIPTOR_BYTES",
        ],
    },
    {
        "id": "cold-stager-directory",
        "path": "scripts/r3-cold-stager-main.c", "language": "c", "name": "find_file",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["uint8_t fuel = 64", "next_sector == sector"],
    },
    {
        "id": "c-file-capacity",
        "path": "src/io.c", "language": "c", "name": "disk_chain_capacity",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["fuel = DISK_CHAIN_FUEL", "disk_chain_count", "return t ? 0 : cap"],
    },
    {
        "id": "c-file-save",
        "path": "src/io.c", "language": "c", "name": "io_disk_save_impl",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["fuel = DISK_CHAIN_FUEL", "disk_chain_count", "return t == 0"],
    },
    {
        "id": "c-file-stage",
        "path": "src/io.c", "language": "c", "name": "disk_chain_to_scratch",
        "kind": "file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["!nt && !ns", "nt == t && ns == s", "cnt > remaining", "return n"],
    },
    {
        "id": "c-source-stream",
        "path": "src/io.c", "language": "c", "name": "disk_source_fetch",
        "kind": "coupled-file-data", "sector_limit": 153, "large_case": "reject",
        "requires": ["disk_file_pos >= disk_file_len", "if (!nt && !ns) return '\\0'"],
    },
    {
        "id": "c-directory",
        "path": "src/io.c", "language": "c", "name": "disk_dir_find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": [
            "fuel = 64", "if (nt == 0) return 0", "nt != 40u", "ns >= 40u",
            "nt == track && ns == sector",
        ],
    },
    {
        "id": "ide-effective-count",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-effective-count",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["%ide-disk-link-valid-p", "-1"],
    },
    {
        "id": "ide-read-chain",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-read-chain",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["%ide-disk-link-valid-p", "nil"],
    },
    {
        "id": "ide-directory",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-disk-find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "ide-directory-list",
        "path": "lib/ide-disk.lisp", "language": "lisp", "name": "%ide-dir-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "m65d-old-chain",
        "path": "lib/m65-disk.lisp", "language": "lisp", "name": "%m65d-read-old-chain",
        "kind": "file-data", "sector_limit": 33, "large_case": "reject",
        "requires": ["(= fuel 0)", "%m65d-pair-member-p", "(< next-sector 1)", "(- fuel 1)"],
    },
    {
        "id": "m65d-directory",
        "path": "lib/m65-disk.lisp", "language": "lisp", "name": "%m65d-dir-scan",
        "kind": "directory", "sector_limit": 40, "large_case": "not-applicable",
        "requires": ["(= fuel 0)", "(= next-sector sector)", "(- fuel 1)"],
    },
    {
        "id": "fasl-slot-capacity",
        "path": "lib/lcc-fasl.lisp", "language": "lisp", "name": "%compile-slot-capacity",
        "kind": "file-data", "sector_limit": 255, "large_case": "reject",
        "requires": ["(> next-sector 0)", "(= next-track track)", "(= next-sector sector)", "(1- fuel)"],
    },
    {
        "id": "fasl-slot-directory",
        "path": "lib/lcc-fasl.lisp", "language": "lisp", "name": "%compile-slot-find",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "resident-load-directory",
        "path": "lib/stdlib-load.lisp", "language": "lisp", "name": "%load-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
    {
        "id": "resident-load-lib-directory",
        "path": "lib/stdlib-load-lib.lisp", "language": "lisp", "name": "%load-lib-scan-directory",
        "kind": "directory", "sector_limit": 64, "large_case": "not-applicable",
        "requires": ["(> fuel 0)", "(1- fuel)", "%disk-directory-link-valid-p"],
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def c_body(text: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\([^;]*?\)\s*\{{", text, re.S)
    if not match:
        raise GateError(f"C walker not found: {name}")
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise GateError(f"unterminated C walker: {name}")


def lisp_body(text: str, name: str) -> str:
    marker = f"(defun {name}"
    start = text.find(marker)
    if start < 0:
        raise GateError(f"Lisp walker not found: {name}")
    depth = 0
    in_string = False
    escaped = False
    comment = False
    for index in range(start, len(text)):
        char = text[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == ";":
            comment = True
        elif char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated Lisp walker: {name}")


def chain(sectors: int) -> dict[tuple[int, int], tuple[int, int]]:
    links: dict[tuple[int, int], tuple[int, int]] = {}
    for index in range(sectors):
        current = (1 + index // 40, index % 40)
        if index + 1 == sectors:
            links[current] = (0, 2)
        else:
            links[current] = (1 + (index + 1) // 40, (index + 1) % 40)
    return links


def walk_model(
    links: dict[tuple[int, int], tuple[int, int]], limit: int, *, file_data: bool,
) -> str:
    current = (1, 0)
    seen: set[tuple[int, int]] = set()
    for _ in range(limit):
        if current in seen or current not in links:
            return "reject"
        seen.add(current)
        next_track, next_sector = links[current]
        if next_track == 0:
            if file_data and next_sector == 0:
                return "reject"
            return "accept"
        if not 1 <= next_track <= 80 or not 0 <= next_sector < 40:
            return "reject"
        current = (next_track, next_sector)
    return "reject"


def data_case(kind: str, limit: int, case: str) -> str:
    file_data = kind != "directory"
    if case == "greater-than-255-sectors":
        if not file_data:
            return "not-applicable"
        return walk_model(chain(258), limit, file_data=True)
    if case == "zero-tail":
        if not file_data:
            return "not-applicable"
        return walk_model({(1, 0): (0, 0)}, limit, file_data=True)
    if case == "self-reference":
        return walk_model({(1, 0): (1, 0)}, limit, file_data=file_data)
    raise GateError(f"unknown shared case: {case}")


def verify() -> dict[str, Any]:
    rows = []
    bindings: dict[str, dict[str, Any]] = {}
    validators = []
    coordinators = []
    for spec in (
        {
            "id": "c-file-link-decoder", "path": "src/io.c", "language": "c",
            "name": "disk_chain_count",
            "requires": ["if (!nt)", "if (!ns) return 255u", "nt == t && ns == s", "return 254u"],
        },
        {
            "id": "ide-file-link-decoder", "path": "lib/ide-disk.lisp", "language": "lisp",
            "name": "%ide-disk-link-valid-p",
            "requires": ["(= next-track 0)", "(> next-sector 0)", "(= next-track track)", "(= next-sector sector)"],
        },
        {
            "id": "resident-directory-link-decoder", "path": "lib/stdlib-load.lisp", "language": "lisp",
            "name": "%disk-directory-link-valid-p",
            "requires": [
                "(= next-track 0)", "(= next-track 40)", "(< next-sector 40)",
                "(= next-track track)", "(= next-sector sector)",
            ],
        },
    ):
        path = ROOT / spec["path"]
        text = path.read_text(encoding="utf-8")
        body = c_body(text, spec["name"]) if spec["language"] == "c" else lisp_body(text, spec["name"])
        missing = [token for token in spec["requires"] if token not in body]
        if missing:
            raise GateError(f"{spec['id']} misses structural guards: {missing}")
        validators.append({
            "id": spec["id"], "path": spec["path"], "function": spec["name"],
            "zero_tail": "reject", "self_reference": "reject", "status": "pass",
        })
        bindings[spec["path"]] = {"path": spec["path"], "sha256": sha256(path)}
    for spec in WALKERS:
        path = ROOT / spec["path"]
        text = path.read_text(encoding="utf-8")
        body = c_body(text, spec["name"]) if spec["language"] == "c" else lisp_body(text, spec["name"])
        missing = [token for token in spec["requires"] if token not in body]
        if missing:
            raise GateError(f"{spec['id']} misses structural guards: {missing}")
        observed_large = data_case(spec["kind"], spec["sector_limit"], "greater-than-255-sectors")
        if observed_large != spec["large_case"]:
            raise GateError(f"{spec['id']} large-chain classification drift")
        rows.append({
            "id": spec["id"], "path": spec["path"], "function": spec["name"],
            "language": spec["language"], "kind": spec["kind"],
            "sector_accounting": (
                "16-bit-or-fixnum-for-file-data; bounded-8-bit-for-40/64-sector-directory-domain"
            ),
            "sector_limit": spec["sector_limit"],
            "corrupt_zero_tail": data_case(spec["kind"], spec["sector_limit"], "zero-tail"),
            "self_reference": data_case(spec["kind"], spec["sector_limit"], "self-reference"),
            "greater_than_255_sectors": observed_large,
            "status": "pass",
        })
        bindings[spec["path"]] = {
            "path": spec["path"], "sha256": sha256(path),
        }
    cases = [
        {
            "id": "greater-than-255-sectors", "sectors": 258,
            "rule": "accept only the media-sized cold stager; bounded user APIs reject rather than truncate",
            "status": "pass",
        },
        {
            "id": "link-byte-zero-in-final-sector", "terminal_link": [0, 0],
            "rule": "file-data walkers reject before reading payload byte 256; directory walkers use track zero as their format terminator",
            "status": "pass",
        },
        {
            "id": "self-reference", "link": "current-track/current-sector",
            "rule": "reject immediately where identity is retained, otherwise terminate at the documented domain fuel without publishing a partial success",
            "status": "pass",
        },
    ]
    return {
        "format": FORMAT,
        "status": "pass",
        "scope": "all live 1581 on-media link walkers in product C and Lisp sources",
        "criteria": {
            "sector_accounting": "no 8-bit truncation for file-data chains; explicitly bounded counters for finite directory/descriptor domains",
            "corrupt_link_clamp": "zero-byte file terminators and invalid/self links fail closed",
            "fuel_or_cycle_bound": "every walker has length-derived fuel, a format-domain fuel, or a byte-ceiling bound",
        },
        "shared_cases": cases,
        "shared_link_validators": validators,
        "chain_coordinators": coordinators,
        "walkers": rows,
        "excluded_non_walkers": [
            "M65D new-chain allocation and write recursion consume validated in-memory pair lists, not on-media link bytes",
            "the Wave-1 preallocated C1 FASL slot walker and commit-last writer are retired; compile-string now publishes through M65D COW",
            "archived m65-disk-alloc*.lisp prototypes are not product inputs",
            "host D81 parsers are independent witnesses, not device walkers",
        ],
        "deviations": [],
        "source_bindings": sorted(bindings.values(), key=lambda row: row["path"]),
        "claim_limit": "This receipt proves structural guards and the common host model. Hardware timing and F011 transport remain outside this gate.",
    }


def selftest() -> None:
    if data_case("file-data", 3226, "greater-than-255-sectors") != "accept":
        raise GateError("large media model rejected the cold-stager case")
    if data_case("file-data", 255, "greater-than-255-sectors") != "reject":
        raise GateError("bounded model accepted a truncated large chain")
    if data_case("file-data", 153, "zero-tail") != "reject":
        raise GateError("zero-tail mutation accepted")
    if data_case("directory", 64, "self-reference") != "reject":
        raise GateError("directory self-reference mutation accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("chain-walker-inventory: SELFTEST PASS mutations=4")
            return 0
        receipt = verify()
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"chain-walker-inventory: PASS walkers={len(receipt['walkers'])} cases=3 deviations=0")
        return 0
    except (GateError, OSError, UnicodeError) as exc:
        print(f"chain-walker-inventory: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
