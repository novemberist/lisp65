#!/usr/bin/env python3
"""Permanent C2D-v6 canonical-root surrogate collision gate.

The direct-object domain is emitted by a tiny host helper compiled against the
product's ``src/obj.h``.  The gate therefore consumes the same MKFIX,
MK_BCODE, and MK_SYMI definitions as the product instead of restating their
bit arithmetic in Python.  Native descriptors use the product contract's
current direct primitive representation (MKFIX of the 14-bit primitive id).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OBJ_H = ROOT / "src/obj.h"
ROOT_CAPACITY = 1536


class SurrogateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SurrogateError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_ref(ordinal: int) -> int:
    require(0 <= ordinal < ROOT_CAPACITY, "root ordinal outside 0..1535")
    return (ordinal + 1) << 1


def root_ordinal(word: int) -> int:
    require(0 < word < 0x8000 and not word & 1,
            "resolution is not a positive-even root surrogate")
    ordinal = (word >> 1) - 1
    require(ordinal < ROOT_CAPACITY, "root surrogate exceeds the 1536-root plane")
    return ordinal


def helper_source() -> str:
    return r'''#include <stdint.h>
#include <stdio.h>
#include "obj.h"

static void emit(uint8_t domain, uint16_t value) {
    uint8_t row[3] = { domain, (uint8_t)value, (uint8_t)(value >> 8) };
    if (fwrite(row, 1, sizeof row, stdout) != sizeof row) _Exit(2);
}

int main(void) {
    int32_t n;
    uint16_t i;
    for (n = -16384; n <= 16383; ++n) emit(1, (uint16_t)MKFIX(n));
    for (i = 0; i < 4096; ++i) emit(2, (uint16_t)MK_BCODE(i));
    for (i = 0; i < 4096; ++i) emit(3, (uint16_t)MK_SYMI(i));
    for (i = 0; i < 16384; ++i) emit(4, (uint16_t)MKFIX(i));
    return 0;
}
'''


def product_domains() -> tuple[dict[str, set[int]], dict[str, Any]]:
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    require(compiler is not None, "host C compiler is required for obj.h collision gate")
    with tempfile.TemporaryDirectory(prefix="c2-root-domain-") as td:
        work = Path(td)
        source = work / "domains.c"
        binary = work / "domains"
        source.write_text(helper_source(), encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", str(ROOT / "src"), str(source), "-o", str(binary)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        raw = subprocess.run([str(binary)], check=True, stdout=subprocess.PIPE).stdout
    require(len(raw) % 3 == 0, "obj.h domain helper emitted a truncated row")
    names = {1: "fixnum", 2: "bcode", 3: "symi", 4: "native_direct"}
    domains = {name: set() for name in names.values()}
    counts = {name: 0 for name in names.values()}
    for at in range(0, len(raw), 3):
        tag = raw[at]
        require(tag in names, "obj.h domain helper emitted an unknown domain")
        name = names[tag]
        domains[name].add(raw[at + 1] | raw[at + 2] << 8)
        counts[name] += 1
    require(counts == {"fixnum": 32768, "bcode": 4096,
                       "symi": 4096, "native_direct": 16384},
            "obj.h direct-domain cardinality drift")
    return domains, {
        "compiler": Path(compiler).name,
        "helper_source_sha256": sha(helper_source().encode()),
        "obj_h_sha256": sha(OBJ_H.read_bytes()),
        "emitted_rows": sum(counts.values()),
        "domain_rows": counts,
        "domain_unique_values": {key: len(value) for key, value in domains.items()},
    }


def classify_resolution(word: int, direct_legal: set[int]) -> tuple[str, int]:
    require(0 <= word <= 0xFFFF, "resolution word is not u16")
    if word and word < 0x8000 and not word & 1:
        return "root", root_ordinal(word)
    require(word in direct_legal,
            "resolution is neither a legal root surrogate nor a legal direct obj")
    return "direct", word


def reject(label: str, operation: Any) -> str:
    try:
        operation()
    except SurrogateError:
        return label
    raise SurrogateError(f"negative fixture accepted: {label}")


def collect() -> dict[str, Any]:
    domains, source = product_domains()
    direct = set().union(*domains.values())
    surrogates = {root_ref(ordinal) for ordinal in range(ROOT_CAPACITY)}
    require(len(surrogates) == ROOT_CAPACITY, "root surrogate collision within root plane")
    intersections = {name: sorted(surrogates & values)
                     for name, values in domains.items()}
    require(all(not values for values in intersections.values()),
            "root surrogate collides with a legal direct-object domain")
    require(root_ref(0) == 0x0002 and root_ref(1535) == 0x0C00,
            "root surrogate boundary drift")
    for ordinal in range(ROOT_CAPACITY):
        require(root_ordinal(root_ref(ordinal)) == ordinal,
                "root surrogate round-trip drift")
    for word in direct:
        kind, value = classify_resolution(word, direct)
        require(kind == "direct" and value == word, "direct resolution reclassified")

    high_bit_false_roots = {
        "bcode": sum(bool(value & 0x8000) for value in domains["bcode"]),
        "symi": sum(bool(value & 0x8000) for value in domains["symi"]),
        "negative_fixnum": sum(bool(value & 0x8000)
                               for value in domains["fixnum"]),
    }
    require(all(value for value in high_bit_false_roots.values()),
            "high-bit collision witness disappeared")

    negatives = [
        reject("ordinal-1536", lambda: root_ref(1536)),
        reject("zero-surrogate", lambda: root_ordinal(0)),
        reject("odd-surrogate", lambda: root_ordinal(3)),
        reject("surrogate-above-root-plane", lambda: root_ordinal(0x0C02)),
        reject("surrogate-high-bit", lambda: root_ordinal(0x8000)),
        reject("direct-as-root", lambda: root_ordinal(next(iter(domains["bcode"])))),
        reject("root-as-direct", lambda: require(root_ref(0) in direct,
                                                  "root surrogate is not direct")),
        reject("positive-even-direct-pointer-shape",
               lambda: classify_resolution(0x1000, direct)),
    ]
    return {
        "format": "lisp65-c2d-v6-root-surrogate-gate-v1",
        "status": "pass",
        "source_truth": source,
        "root_capacity": ROOT_CAPACITY,
        "root_surrogates": {
            "count": len(surrogates), "minimum_hex": "0x0002",
            "maximum_hex": "0x0c00", "ordinal_0_hex": "0x0002",
            "ordinal_1535_hex": "0x0c00", "ordinal_1536": "rejected",
        },
        "collision_intersections": {key: len(value)
                                    for key, value in intersections.items()},
        "high_bit_tag_rejection_witnesses": high_bit_false_roots,
        "negative_fixtures": negatives,
        "permanent_rule": (
            "Every C2 probe imports and executes this complete-domain gate; "
            "new direct obj domains must be added to the obj.h-backed emitter."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "json"), nargs="?", default="check")
    args = parser.parse_args()
    try:
        report = collect()
        if args.action == "json":
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("c2-lite-root-surrogate: PASS roots=1536 direct-rows=%d negatives=%d" % (
                report["source_truth"]["emitted_rows"],
                len(report["negative_fixtures"])))
        return 0
    except (OSError, subprocess.CalledProcessError, SurrogateError) as exc:
        print(f"c2-lite-root-surrogate: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
