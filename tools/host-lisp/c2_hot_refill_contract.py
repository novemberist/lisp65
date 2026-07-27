#!/usr/bin/env python3
"""Prove one shared, direct C2 hot-literal refill contract without a product link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/c2.2/hot-refill-contract-probe"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
C2D = ROOT / (
    "build/c2.2/hardware-presmoke-link29-direct-entry-encoding/"
    "first-red-latency/c2d-after-two-identical-forms.bin")
HOST_SOURCE = ROOT / "scripts/c2-hot-literal-host-main.c"
HELPER_SOURCE = ROOT / "src/c2_hot_literal.c"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
PHASE_SOURCE = ROOT / "scripts/c2-stream-v2-decoder.c"
HEADER = ROOT / "scripts/c2-stream-decoder.h"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-single-source-contract-probe-receipt.json")


class HotRefillError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HotRefillError(message)


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def p16(value: int) -> bytes:
    return struct.pack("<H", value)


def p32(value: int) -> bytes:
    return struct.pack("<I", value)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(argv: list[str], *, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True,
                            check=False, timeout=120)
    if result.returncode != expected:
        raise HotRefillError(
            f"{Path(argv[0]).name} returned {result.returncode}, expected "
            f"{expected}: {(result.stderr or result.stdout).strip()}")
    return result


def source_gate() -> dict[str, Any]:
    runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")
    phase = PHASE_SOURCE.read_text(encoding="utf-8")
    helper = HELPER_SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    rows = {
        "vm_refill_calls_shared_materializer": (
            runtime.count("c2_stream_product_materialize_literals(") == 1),
        "phase13_calls_shared_materializer": (
            phase.count("c2_stream_product_materialize_literals(") == 1),
        "one_descriptor_kind_switch": helper.count("switch (kind)") == 1,
        "one_child_status_definition": (
            helper.count("c2_stream_product_child_status(") == 3),
        "public_child_delegates_to_status": (
            "return c2_stream_product_child_status(" in helper),
        "span_materializer_delegates_to_status": (
            "status = c2_stream_product_child_status(" in helper),
        "contract_header_exports_one_span_seam": (
            header.count("c2_stream_product_materialize_literals(") == 1),
        "direct_refill_is_probe_gated": (
            runtime.count("LISP65_C2_DIRECT_HOT_REFILL") == 2
            and phase.count("LISP65_C2_DIRECT_HOT_REFILL") == 1),
    }
    require(all(rows.values()), f"single-source source gate red: {rows}")
    return {key: "passed" for key in rows}


def collect_cases(shelf: bytes, c2d: bytes) -> tuple[bytes, dict[str, Any]]:
    require(c2d[:5] == b"C2D\0\x03" and len(c2d) == 33840,
            "C2D-v3 input drift")
    require(shelf[:5] == b"L65S\x04", "L65S-v4 input drift")
    generation = u16(c2d, 10); images = u16(c2d, 12)
    entries = u16(c2d, 16); resolutions = u16(c2d, 20)
    roots = u16(c2d, 24); images_offset = u16(c2d, 28)
    entries_offset = u16(c2d, 30); resolutions_offset = u16(c2d, 32)
    roots_offset = u16(c2d, 34)
    require((generation, images, entries, resolutions, roots)
            == (1, 6, 588, 2264, 283), "current product census drift")
    output = bytearray(b"HREF" + p16(entries))
    literal_words = 0; nonempty = 0; maximum = 0
    descriptor_kinds = {kind: 0 for kind in range(9)}
    locations: dict[str, int] = {}
    for ordinal in range(entries):
        directory_at = entries_offset + ordinal * 10
        directory = c2d[directory_at:directory_at + 10]
        require(len(directory) == 10 and not directory[1]
                and u16(directory, 8) == generation, "directory binding drift")
        image_index = directory[0]; local = u16(directory, 2)
        require(image_index < images, "directory image outside table")
        image_at = images_offset + image_index * 32
        image = c2d[image_at:image_at + 32]
        require(len(image) == 32 and image[0] == 0 and not image[1]
                and image[2] == image_index and u16(image, 4) == generation,
                "static image binding drift")
        directory_base = u16(image, 6); image_entries = u16(image, 8)
        resolution_base = u16(image, 10); metadata = u24(image, 23)
        require(local < image_entries and metadata + 24 <= len(shelf),
                "entry metadata binding drift")
        metadata_header = shelf[metadata:metadata + 24]
        literal_count = u16(metadata_header, 12)
        entry_offset = u16(metadata_header, 14)
        literal_offset = u16(metadata_header, 16)
        entry_at = metadata + entry_offset + local * 16
        entry = shelf[entry_at:entry_at + 16]
        require(len(entry) == 16, "entry record truncated")
        first = u16(entry, 5); count = entry[7]
        require(first <= literal_count and count <= literal_count - first
                and resolution_base + first + count <= resolutions,
                "entry literal range drift")
        expected: list[int] = []
        for index in range(count):
            global_literal = first + index
            descriptor_at = metadata + literal_offset + global_literal * 8
            descriptor = shelf[descriptor_at:descriptor_at + 8]
            require(len(descriptor) == 8 and descriptor[0] <= 8
                    and not descriptor[1] and not descriptor[7],
                    "descriptor envelope drift")
            kind = descriptor[0]; descriptor_kinds[kind] += 1
            resolution_at = resolutions_offset + (
                resolution_base + global_literal) * 2
            word = u16(c2d, resolution_at)
            if kind in (3, 7):
                require(word < roots, "root ordinal outside C2D")
                root_at = roots_offset + word * 2
                word = u16(c2d, root_at)
                require(word and word < 0x8000 and not word & 1,
                        "root value is not a heap pointer")
                locations.setdefault("root_descriptor", descriptor_at)
                locations.setdefault("root_resolution", resolution_at)
                locations.setdefault("root_value", root_at)
            elif kind == 4:
                locations.setdefault("entry_descriptor", descriptor_at)
                locations.setdefault("entry_resolution", resolution_at)
            if count:
                locations.setdefault("any_descriptor", descriptor_at)
                locations.setdefault("any_resolution", resolution_at)
            expected.append(word)
        output.extend(p16(ordinal) + p32(metadata) + p16(literal_offset)
                      + p16(literal_count) + p16(resolution_base)
                      + p16(directory_base) + p16(image_entries) + p16(first)
                      + bytes([count]) + b"".join(p16(word) for word in expected))
        literal_words += count
        if count: nonempty += 1
        maximum = max(maximum, count)
    require(literal_words == 1931 and nonempty == 485 and maximum == 23,
            "literal census drift")
    require(set(locations) == {"root_descriptor", "root_resolution", "root_value",
                               "entry_descriptor", "entry_resolution",
                               "any_descriptor", "any_resolution"},
            f"mutation locations incomplete: {locations}")
    return bytes(output), {
        "generation": generation, "images": images, "entries": entries,
        "resolutions": resolutions, "roots": roots,
        "literal_words": literal_words, "entries_with_literals": nonempty,
        "maximum_literals_per_entry": maximum,
        "descriptor_kind_observations": descriptor_kinds,
        "offsets": {"images": images_offset, "entries": entries_offset,
                    "resolutions": resolutions_offset, "roots": roots_offset},
        "mutation_locations": locations,
    }


def compile_host(out: Path) -> Path:
    host = out / "c2-hot-literal-host"
    result = run([
        "cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-DC2_STREAM_PRODUCT_V3=1", "-I", str(ROOT / "src"),
        "-I", str(ROOT / "scripts"), str(HELPER_SOURCE), str(HOST_SOURCE),
        "-o", str(host),
    ])
    require(not result.stdout and not result.stderr, "host compiler diagnostics")
    return host


def execute(host: Path, shelf: Path, c2d: Path, cases: Path,
            mode: str | None = None) -> str:
    argv = [str(host), str(shelf), str(c2d), str(cases)]
    if mode: argv.append(mode)
    return run(argv).stdout.strip()


def mutation_matrix(out: Path, host: Path, cases: Path,
                    shelf_raw: bytes, c2d_raw: bytes,
                    facts: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = out / "mutations"; mutations.mkdir()
    locations = facts["mutation_locations"]
    rows: list[dict[str, Any]] = []

    def mutated(label: str, shelf: bytearray, c2d: bytearray,
                expected: int) -> None:
        shelf_path = mutations / f"{label}.shelf.bin"
        c2d_path = mutations / f"{label}.c2d.bin"
        shelf_path.write_bytes(shelf); c2d_path.write_bytes(c2d)
        output = execute(host, shelf_path, c2d_path, cases,
                         f"expect:{expected}")
        require(f"REJECT status={expected}" in output,
                f"{label} did not fail closed: {output}")
        rows.append({"case": label, "expected_status": expected,
                     "result": "rejected"})

    shelf = bytearray(shelf_raw); c2d = bytearray(c2d_raw)
    shelf[locations["any_descriptor"]] = 9
    mutated("unknown-descriptor-kind", shelf, c2d, 6)

    shelf = bytearray(shelf_raw); c2d = bytearray(c2d_raw)
    c2d[locations["entry_resolution"]:locations["entry_resolution"] + 2] = b"\0\0"
    mutated("entry-resolution-not-bcode", shelf, c2d, 7)

    shelf = bytearray(shelf_raw); c2d = bytearray(c2d_raw)
    c2d[locations["root_resolution"]:locations["root_resolution"] + 2] = p16(
        facts["roots"])
    mutated("root-ordinal-out-of-range", shelf, c2d, 7)

    shelf = bytearray(shelf_raw); c2d = bytearray(c2d_raw)
    c2d[locations["root_value"]:locations["root_value"] + 2] = p16(3)
    mutated("root-value-not-pointer", shelf, c2d, 7)

    output = execute(host, SHELF, C2D, cases,
                     f"shelf-fail:{locations['any_descriptor']}:expect:1")
    require("REJECT status=1" in output, "descriptor read fault not rejected")
    rows.append({"case": "descriptor-read-fault", "expected_status": 1,
                 "result": "rejected"})

    output = execute(host, SHELF, C2D, cases,
                     f"c2d-fail:{locations['any_resolution']}:expect:1")
    require("REJECT status=1" in output, "resolution read fault not rejected")
    rows.append({"case": "resolution-read-fault", "expected_status": 1,
                 "result": "rejected"})
    return rows


def build() -> dict[str, Any]:
    if BUILD.exists(): shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    source = source_gate()
    shelf_raw = SHELF.read_bytes(); c2d_raw = C2D.read_bytes()
    case_raw, facts = collect_cases(shelf_raw, c2d_raw)
    cases = BUILD / "hot-refill-cases.bin"; cases.write_bytes(case_raw)
    host = compile_host(BUILD)
    positive = execute(host, SHELF, C2D, cases)
    require(positive == "c2-hot-literal: PASS entries=588 negatives=3 nested=1",
            f"positive host closure drift: {positive}")
    mutations = mutation_matrix(BUILD, host, cases, shelf_raw, c2d_raw, facts)
    facts = {key: value for key, value in facts.items()
             if key != "mutation_locations"}
    return {
        "format": "lisp65-c2-hot-refill-single-source-contract-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-non-product-contract-and-semantic-probe",
        "scope": {"product_links": 0, "hardware_execution": "none",
                  "promotion": "not-authorized",
                  "product_profile_define": "not-enabled"},
        "inputs": {"shelf": bind(SHELF), "initial_c2d": bind(INITIAL_C2D),
                   "materialized_generation1_c2d_capture": bind(C2D),
                   "helper_source": bind(HELPER_SOURCE),
                   "runtime_source": bind(RUNTIME_SOURCE),
                   "phase_source": bind(PHASE_SOURCE),
                   "contract_header": bind(HEADER),
                   "host_fixture": bind(HOST_SOURCE)},
        "generated": {"host": bind(host), "cases": bind(cases)},
        "source_single_truth_gate": source,
        "semantic_closure": {
            **facts,
            "direct_refill_vs_contract": "588/588 entries exact",
            "literal_values": "1931/1931 exact",
            "nested_caller_restoration": "passed",
            "local_argument_negatives": {
                "insufficient-hot-capacity": "rejected",
                "literal-range-overrun": "rejected",
                "wrong-decoder-phase": "rejected",
            },
            "artifact_mutation_matrix": mutations,
        },
        "claim_limit": (
            "One bounded host-only proof that the proposed direct VM refill and phase 13 "
            "share one literal materializer and preserve the current 588-entry semantics. "
            "It is not a product-shaped capacity probe, product link, hardware result, "
            "promotion, latency result or acceptance claim."),
        "next_gate": (
            "A separate product-shaped seed capacity/placement probe may compile the feature "
            "define. Any negative drift stops before a product closure link."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = build(); data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.read_bytes() == data, "contract receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        print(f"c2-hot-refill-contract: {verb} entries=588 literals=1931 "
              "mutations=6 product-links=0")
        return 0
    except (OSError, ValueError, KeyError, HotRefillError) as error:
        print(f"c2-hot-refill-contract: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
