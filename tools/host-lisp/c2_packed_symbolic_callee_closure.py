#!/usr/bin/env python3
"""Prove that every packed symbolic callee is published or native."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
from v2_native_function_views_generated import ACTIVE_CALLPRIMS  # noqa: E402


FORMAT = "lisp65-c2-packed-symbolic-callee-closure-v1"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-packed-symbolic-callee-closure-first-red.json"
)
LINK94_PRODUCT = ROOT / (
    "build/c2.3/top-level-macro-redispatch-link94-preflight/"
    "static-plane/narrow-static/product/substitution-artifacts.json"
)
LINK95_PROBE = ROOT / (
    "build/c2.3/top-level-macro-publication-link95-preflight/"
    "static-plane/narrow-static/product/substitution-artifacts.json"
)
ANONYMOUS_AUTHORITY = ROOT / (
    "tests/bytecode/dialect-v2/v111-locality-replay-inputs/"
    "accepted-candidate/manifest.json"
)


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": sha(raw),
    }


def _u16(raw: bytes, at: int) -> int:
    require(at + 2 <= len(raw), "truncated u16")
    return struct.unpack_from("<H", raw, at)[0]


def _u24(raw: bytes, at: int) -> int:
    require(at + 3 <= len(raw), "truncated u24")
    return raw[at] | raw[at + 1] << 8 | raw[at + 2] << 16


def _strings(raw: bytes) -> dict[int, str]:
    rows: dict[int, str] = {}
    cursor = 0
    while cursor < len(raw):
        length = _u16(raw, cursor)
        end = cursor + 2 + length
        require(end <= len(raw), "packed C2I string pool is truncated")
        rows[cursor] = raw[cursor + 2:end].decode("ascii")
        cursor = end
    return rows


def _packed_image(product_dir: Path, key: str) -> dict[str, Any]:
    code_path = product_dir / f"{key}.code.bin"
    c2i_path = product_dir / f"{key}.c2i.bin"
    code, c2i = code_path.read_bytes(), c2i_path.read_bytes()
    require(c2i[:8] == b"C2I\0\x02\x18\x10\x08", f"C2I identity drift: {key}")
    entries, literals = _u16(c2i, 10), _u16(c2i, 12)
    entry_at, literal_at, string_at = (
        _u16(c2i, 14), _u16(c2i, 16), _u16(c2i, 18)
    )
    string_bytes = _u16(c2i, 20)
    require(entry_at == 24 and literal_at == entry_at + entries * 16
            and string_at == literal_at + literals * 8,
            f"C2I section arithmetic drift: {key}")
    strings = _strings(c2i[string_at:string_at + string_bytes])
    entry_rows: list[dict[str, Any]] = []
    published: set[str] = set()
    anonymous: set[str] = set()
    for ordinal in range(entries):
        at = entry_at + ordinal * 16
        offset, length = _u24(c2i, at), _u16(c2i, at + 3)
        first, count = _u16(c2i, at + 5), c2i[at + 7]
        name_at = _u16(c2i, at + 8)
        require(offset + length <= len(code) and first + count <= literals,
                f"packed entry bounds drift: {key}/{ordinal}")
        name = f"anonymous:{key}:{ordinal}"
        if name_at == 0xffff:
            anonymous.add(name)
        else:
            require(name_at in strings, f"packed entry name missing: {key}/{ordinal}")
            name = strings[name_at]
            published.add(name)
        entry_rows.append({
            "name": name, "offset": offset, "length": length,
            "first": first, "count": count,
        })
    descriptors: list[dict[str, Any]] = []
    for ordinal in range(literals):
        at = literal_at + ordinal * 8
        kind, arg0, arg1 = c2i[at], _u16(c2i, at + 2), _u24(c2i, at + 4)
        target = None
        if kind in {5, 8}:
            require(arg1 in strings, f"packed symbol string missing: {key}/{ordinal}")
            target = strings[arg1]
        descriptors.append({"kind": kind, "arg0": arg0, "target": target})
    return {
        "key": key, "code": code, "entries": entry_rows,
        "descriptors": descriptors, "published": published,
        "anonymous": anonymous,
        "authorities": {"code": bind(code_path), "metadata": bind(c2i_path)},
    }


def inventory(product_path: Path, *, include_rows: bool = False) -> dict[str, Any]:
    product = load(product_path)
    require(product.get("format") == "lisp65-c2-product-substitution-artifacts-v1"
            and product.get("images") == 6,
            "packed product identity drift")
    product_dir = product_path.parent
    images = [
        _packed_image(product_dir, key)
        for key in ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")
    ]
    published: set[str] = set()
    for image in images:
        published.update(image["published"])
    anonymous_manifest = load(ANONYMOUS_AUTHORITY)
    anonymous = {
        row["name"] for row in anonymous_manifest["entries"]
        if row.get("anonymous", False)
    }
    require(sum(len(image["entries"]) for image in images) == product["entries"],
            "packed entry census differs from product identity")

    ledger = C._abi_ledger("dialect-v2", None)
    rows: list[dict[str, Any]] = []
    for image in images:
        for entry in image["entries"]:
            start, length = entry["offset"], entry["length"]
            code = B.decode_code_object(image["code"][start:start + length])
            pc = 0
            while pc < len(code.payload):
                here = pc
                op, operand, pc = B.decode_instruction(
                    code.payload, pc, profile_id="dialect-v2",
                    abi_ledger=ledger,
                )
                if op.mnemonic not in {"CALL", "TAILCALL"}:
                    continue
                literal, argc = operand
                require(literal < entry["count"],
                        f"packed call literal outside table: {entry['name']}")
                descriptor = image["descriptors"][entry["first"] + literal]
                kind = descriptor["kind"]
                target = descriptor["target"]
                if kind == 4:
                    classification = "packed-direct-entry"
                    target = f"entry:{image['key']}:{descriptor['arg0']}"
                elif kind == 6:
                    classification = "native"
                    target = f"native:{descriptor['arg0']}"
                elif kind in {5, 8} and target in published:
                    classification = "published-cell"
                elif kind in {5, 8} and target in ACTIVE_CALLPRIMS:
                    classification = "native"
                elif kind in {5, 8} and target in anonymous:
                    classification = "anonymous-only"
                else:
                    classification = "absent"
                rows.append({
                    "image": image["key"],
                    "caller": entry["name"], "pc": here,
                    "opcode": op.mnemonic, "argc": argc,
                    "literal": literal, "packed_literal_kind": kind,
                    "target": target, "classification": classification,
                })
    failures = [row for row in rows if row["classification"] in {
        "anonymous-only", "absent",
    }]
    result = {
        "product": bind(product_path),
        "authorities": {
            "packed_images": [image["authorities"] for image in images],
            "anonymous_name_authority": bind(ANONYMOUS_AUTHORITY),
        },
        "published_names": len(published), "anonymous_names": len(anonymous),
        "symbolic_call_sites": len(rows),
        "direct_entry_sites": sum(
            row["classification"] == "packed-direct-entry" for row in rows),
        "published_cell_sites": sum(
            row["classification"] == "published-cell" for row in rows),
        "native_sites": sum(row["classification"] == "native" for row in rows),
        "failures": failures,
    }
    if include_rows:
        result["call_sites"] = rows
    return result


def require_closed(value: dict[str, Any]) -> None:
    require(not value["failures"],
            "packed symbolic callees lack a published/native target: "
            + repr(value["failures"]))


def mutation_tests() -> list[str]:
    base = {
        "failures": [],
        "rows": [
            {"target": "published", "classification": "published-cell"},
            {"target": "native", "classification": "native"},
            {"target": "direct", "classification": "packed-direct-entry"},
        ],
    }
    require_closed(base)
    mutations = {
        "anonymous-presence-is-not-publication": "anonymous-only",
        "absent-callee-is-not-publication": "absent",
        "fixture-publication-cannot-change-packed-product": "anonymous-only",
    }
    rejected: list[str] = []
    for name, classification in mutations.items():
        candidate = deepcopy(base)
        candidate["failures"] = [{
            "target": "%fixture-only", "classification": classification,
        }]
        try:
            require_closed(candidate)
        except ClosureError:
            rejected.append(name)
    require(len(rejected) == len(mutations), "packed closure mutation survived")
    return rejected


def first_red_receipt() -> dict[str, Any]:
    before = inventory(LINK94_PRODUCT)
    after = inventory(LINK95_PROBE)
    old = [row for row in before["failures"] if row["target"] == "%lcc-macro-p"]
    require(len(old) == 1 and old[0]["classification"] == "anonymous-only",
            "Link 94 product finding not reproduced")
    require(not [row for row in after["failures"]
                 if row["target"] in {"%lcc-macro-p", "%c2-top-level-macro-p"}],
            "Link 95 product-owned helper did not close its call edge")
    require(len(before["failures"]) == 9 and len(after["failures"]) == 8,
            "packed closure First Red census drift")
    return {
        "format": "lisp65-c2.3-link95-packed-callee-closure-first-red-v1",
        "recorded_on": "2026-08-09",
        "status": "FIRST-RED; LINK95-CARD-BLOCKED-BEFORE-WPLTO",
        "commission": "eb732707880271b642f3f009299b4216f8700d15",
        "rule": "every packed symbolic callee is published, native, or a packed direct entry",
        "authorities": {
            "contract": bind(ROOT / "config/c2-top-level-macro-publication.json"),
            "product_runtime": bind(ROOT / "lib/dialect-v2/eval-runtime.lisp"),
            "redispatch_receipt": bind(ROOT / (
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-link95-top-level-macro-publication-receipt.json"
            )),
            "published_value_replay": bind(ROOT / (
                "tools/host-lisp/c2_top_level_published_value_call_gate.py"
            )),
            "packed_closure_driver": bind(Path(__file__)),
        },
        "fixed_edge": old[0],
        "link94": before,
        "link95_preflight": after,
        "remaining_failure_count": len(after["failures"]),
        "mutations_rejected": mutation_tests(),
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "claim_limit": (
            "The commissioned helper closes the observed Link-94 DirMiss edge. "
            "The new class gate exposes eight older packed symbolic call edges "
            "without a published/native target, so Link 95 is stopped before its card."
        ),
    }


def check_sealed_first_red() -> dict[str, Any]:
    """Replay the packed artifacts without rebinding historical authorities."""
    value = load(FIRST_RED)
    before = inventory(LINK94_PRODUCT)
    after = inventory(LINK95_PROBE)
    old = [row for row in before["failures"] if row["target"] == "%lcc-macro-p"]
    authorities = value.get("authorities")
    require(
        value.get("format")
            == "lisp65-c2.3-link95-packed-callee-closure-first-red-v1"
        and value.get("status") == "FIRST-RED; LINK95-CARD-BLOCKED-BEFORE-WPLTO"
        and value.get("commission") == "eb732707880271b642f3f009299b4216f8700d15"
        and isinstance(authorities, dict)
        and set(authorities) == {
            "contract", "product_runtime", "redispatch_receipt",
            "published_value_replay", "packed_closure_driver",
        }
        and all(
            isinstance(row, dict)
            and isinstance(row.get("path"), str)
            and isinstance(row.get("bytes"), int)
            and isinstance(row.get("sha256"), str)
            and len(row["sha256"]) == 64
            for row in authorities.values()
        )
        and len(old) == 1
        and value.get("fixed_edge") == old[0]
        and value.get("link94") == before
        and value.get("link95_preflight") == after
        and value.get("remaining_failure_count") == len(after["failures"]) == 8
        and value.get("mutations_rejected") == mutation_tests()
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "sealed packed-callee First Red semantic replay drift",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("audit", "first-red", "first-red-check", "selftest")
    )
    parser.add_argument("--product", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            result: Any = {"mutations_rejected": mutation_tests()}
        elif args.action == "audit":
            require(args.product is not None, "--product is required for audit")
            result = inventory(args.product.resolve())
            require_closed(result)
        elif args.action == "first-red":
            result = first_red_receipt()
            FIRST_RED.parent.mkdir(parents=True, exist_ok=True)
            FIRST_RED.write_bytes(canonical(result))
        else:
            require(FIRST_RED.is_file(), f"First Red receipt absent: {FIRST_RED}")
            result = check_sealed_first_red()
    except (ClosureError, OSError, ValueError, KeyError, json.JSONDecodeError,
            B.DecodeError) as error:
        print(f"c2-packed-symbolic-callee-closure: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
