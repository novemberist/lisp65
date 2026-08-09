#!/usr/bin/env python3
"""Prove that a valid zero-literal C2D-v6 entry reaches vm_run_dir.

The C2D-v6 byte at entry offset 1 is a literal count, not a validity flag.
This gate binds the real %lcc-consp row from the canonical current six-image
profile, the canonical emitter rule, the generated target reader and the final
linked call chain.  Product-dependent ordinals and row offsets are derived,
never pinned privately by this gate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Sequence

import c2_full_emission as F
import c2_l_full_static_plane_gate as PLANE
from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
VM_SOURCE = ROOT / "src/vm.c"
ENTRY_HEADER = ROOT / "src/c2d_v6_entry.h"
SPEC_ROLES = (
    ("stdlib-p0", "stdlib"),
    ("ide", "ide"),
    ("idex", "idex"),
    ("m65d", "m65d"),
    ("buffer", "buffer"),
    ("lcc", "lcc"),
)
ENTRY_OFFSET = 2096
ENTRY_BYTES = 10
INVALID = 0
CANONICAL_SPECS: tuple[tuple[str, str, Path], ...] | None = None
WITNESS_IMAGE = "lcc"
WITNESS_NAME = "%lcc-consp"
WITNESS_KIND = "function"
WITNESS_LITERAL_COUNT = 0
WITNESS_CODE_BYTES = bytes.fromhex(
    "b50100021f00000b1d1a0b3d06011d022b050b3d05011d022b050b3d00011d022b052c052b05"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def u16(data: bytes, at: int) -> int:
    require(0 <= at <= len(data) - 2, "truncated u16")
    return struct.unpack_from("<H", data, at)[0]


def function_body(source: str, name: str, *, definition: str | None = None) -> str:
    marker = definition or (name + "(")
    begin = source.find(marker)
    require(begin >= 0, f"function absent: {name}")
    brace = source.find("{", begin)
    require(brace >= 0, f"function body absent: {name}")
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise GateError(f"unterminated function: {name}")


def execution_length(handle: int, row: bytes, *, generation: int = 1,
                     entry_count: int = 2048,
                     resolution_limit: int = 4096,
                     mutant_requires_literal: bool = False) -> int:
    if len(row) != ENTRY_BYTES or not 0 <= handle < entry_count:
        return INVALID
    image = row[0]
    literals = row[1]
    code_offset = u16(row, 2)
    code_length = u16(row, 4)
    resolution_base = u16(row, 6)
    row_generation = u16(row, 8)
    if (image >= 64 or row_generation != generation or not code_length
            or code_offset + code_length > 65536
            or resolution_base + literals > resolution_limit
            or (mutant_requires_literal and not literals)):
        return INVALID
    return code_length


def mutated(row: bytes, at: int, value: int) -> bytes:
    result = bytearray(row)
    result[at] = value
    return bytes(result)


def canonical_specs() -> tuple[tuple[str, str, Path], ...]:
    """Consume the manifest set bound by the canonical L-full profile."""
    if CANONICAL_SPECS is not None:
        require(
            tuple((key, role) for key, role, _path in CANONICAL_SPECS)
                == SPEC_ROLES
            and all(path.is_file() for _key, _role, path
                    in CANONICAL_SPECS),
            "configured canonical zero-literal manifest inventory drift")
        return CANONICAL_SPECS
    bundle = PLANE.source_bundle()
    PLANE.validate(bundle)
    rows = bundle["receipt"]["authority"]["current_manifests"]
    require(len(rows) == len(SPEC_ROLES),
            "canonical six-image manifest inventory drift")
    result: list[tuple[str, str, Path]] = []
    for (key, role), row in zip(SPEC_ROLES, rows):
        path = ROOT / str(row["path"])
        require(
            path.is_file() and PLANE.sha(path) == row["sha256"],
            f"canonical zero-literal manifest binding drift: {key}",
        )
        result.append((key, role, path))
    return tuple(result)


def canonical_witness() -> dict[str, Any]:
    """Derive the witness from the same six manifests as product emission."""
    F.contract_check()
    images = [F.emit_image(*spec) for spec in canonical_specs()]
    entry_base = code_base = resolution_base = 0
    target: dict[str, Any] | None = None
    counts: list[int] = []
    for slot, image in enumerate(images):
        entries = image.manifest["entries"]
        counts.append(len(entries))
        for local, entry in enumerate(entries):
            if entry.get("name") != "%lcc-consp":
                continue
            require(target is None, "zero-literal witness is not unique")
            row = bytes((slot, int(entry["lit_count"]))) + struct.pack(
                "<HHHH",
                code_base + int(entry["blob_offset"]),
                int(entry["length"]),
                resolution_base + int(image.entry_first[local]),
                1,
            )
            code_start = int(entry["blob_offset"])
            code_length = int(entry["length"])
            code_bytes = image.code[code_start:code_start + code_length]
            require(len(code_bytes) == code_length,
                    "zero-literal witness code range drift")
            target = {
                "ordinal": entry_base + local,
                "row": row,
                "image": image.key,
                "local_ordinal": local,
                "name": entry["name"],
                "kind": entry["kind"],
                "literal_count": int(entry["lit_count"]),
                "code_length": code_length,
                "code_bytes": code_bytes,
            }
        entry_base += len(entries)
        code_base += len(image.code)
        resolution_base += len(image.descriptors)
    require(target is not None, "canonical zero-literal witness absent")
    target["entry_count"] = entry_base
    target["resolution_limit"] = resolution_base
    target["image_entry_counts"] = counts
    return target


def semantic_witness_gate(target: dict[str, Any]) -> dict[str, Any]:
    """Bind witness identity while treating every position as derived."""
    require(
        target["image"] == WITNESS_IMAGE
        and target["name"] == WITNESS_NAME
        and target["kind"] == WITNESS_KIND
        and target["literal_count"] == WITNESS_LITERAL_COUNT
        and target["code_length"] == len(WITNESS_CODE_BYTES)
        and target["code_bytes"] == WITNESS_CODE_BYTES,
        f"canonical zero-literal semantic witness drift: {target}",
    )
    return {
        "image": target["image"],
        "name": target["name"],
        "kind": target["kind"],
        "literal_count": target["literal_count"],
        "code_length": target["code_length"],
        "code_sha256": hashlib.sha256(target["code_bytes"]).hexdigest(),
    }


def semantic_contract_source_gate(source_override: str | None = None) -> dict[str, Any]:
    """Forbid position pins and require every semantic identity field."""
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        (node for node in tree.body
         if isinstance(node, ast.FunctionDef)
         and node.name == "semantic_witness_gate"),
        None,
    )
    require(function is not None, "semantic zero-literal witness gate absent")
    compared: set[str] = set()
    for comparison in (
            node for node in ast.walk(function) if isinstance(node, ast.Compare)):
        for child in ast.walk(comparison):
            if (isinstance(child, ast.Subscript)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "target"
                    and isinstance(child.slice, ast.Constant)
                    and isinstance(child.slice.value, str)):
                compared.add(child.slice.value)
    semantic = {
        "image", "name", "kind", "literal_count", "code_length", "code_bytes"
    }
    positional = {"ordinal", "local_ordinal"}
    require(semantic <= compared,
            f"semantic zero-literal identity field dimmed: {semantic - compared}")
    require(not positional & compared,
            f"positional zero-literal witness pin restored: {positional & compared}")
    return {
        "status": "passed-semantic-identity-not-position-contract",
        "semantic_fields": sorted(semantic),
        "positional_fields": "derived-only",
    }


def semantic_witness_selftest() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    contract = semantic_contract_source_gate(source)
    target: dict[str, Any] = {
        "image": WITNESS_IMAGE,
        "name": WITNESS_NAME,
        "kind": WITNESS_KIND,
        "literal_count": WITNESS_LITERAL_COUNT,
        "code_length": len(WITNESS_CODE_BYTES),
        "code_bytes": WITNESS_CODE_BYTES,
        "ordinal": 651,
        "local_ordinal": 5,
    }
    semantic_witness_gate(target)
    mutations: dict[str, str] = {}
    replacements: dict[str, Any] = {
        "image": "stdlib-p0",
        "name": "%lcc-consp-dimmed",
        "kind": "macro",
        "literal_count": 1,
        "code_length": len(WITNESS_CODE_BYTES) - 1,
        "code_bytes": WITNESS_CODE_BYTES[:-1] + b"\x00",
    }
    for field, replacement in replacements.items():
        mutant = dict(target)
        mutant[field] = replacement
        try:
            semantic_witness_gate(mutant)
        except GateError:
            mutations[f"semantic-{field}-dimmed"] = "rejected"
        else:
            raise GateError(f"dimmed semantic witness field survived: {field}")

    anchor = "        target[\"image\"] == WITNESS_IMAGE\n"
    require(anchor in source, "historical ordinal mutation anchor absent")
    positional_source = source.replace(
        anchor,
        "        target[\"local_ordinal\"] == 6\n        and "
        "target[\"image\"] == WITNESS_IMAGE\n",
        1,
    )
    try:
        semantic_contract_source_gate(positional_source)
    except GateError:
        mutations["historical-local-ordinal-6-restored"] = "rejected"
    else:
        raise GateError("historical local ordinal pin survived")
    require(len(mutations) == 7, "semantic witness mutation accounting drift")
    return {
        "status": "passed-semantic-zero-literal-witness-mutations",
        "contract": contract,
        "code_sha256": hashlib.sha256(WITNESS_CODE_BYTES).hexdigest(),
        "mutations": mutations,
        "mutations_rejected": len(mutations),
    }


def model_gate() -> dict[str, Any]:
    witness = canonical_witness()
    target_ordinal = int(witness["ordinal"])
    target_row = bytes(witness["row"])
    entry_count = int(witness["entry_count"])
    resolution_limit = int(witness["resolution_limit"])
    require(execution_length(
        target_ordinal, target_row, entry_count=entry_count,
        resolution_limit=resolution_limit) == 38,
            "valid zero-literal entry did not reach execution length")
    require(execution_length(
        target_ordinal, target_row, entry_count=entry_count,
        resolution_limit=resolution_limit,
        mutant_requires_literal=True) == INVALID,
        "nonzero-literal regression mutation was not observable")

    zero_length = bytearray(target_row)
    zero_length[4:6] = b"\0\0"
    code_wrap = bytearray(target_row)
    code_wrap[2:6] = b"\xff\xff\x02\x00"
    resolution_wrap = bytearray(target_row)
    resolution_wrap[1] = 1
    struct.pack_into("<H", resolution_wrap, 6, resolution_limit)
    wrong_generation = bytearray(target_row)
    wrong_generation[8:10] = b"\x02\x00"
    negatives = {
        "literal-count-treated-as-validity-marker": execution_length(
            target_ordinal, target_row, entry_count=entry_count,
            resolution_limit=resolution_limit,
            mutant_requires_literal=True),
        "zero-code-length": execution_length(
            target_ordinal, bytes(zero_length), entry_count=entry_count,
            resolution_limit=resolution_limit),
        "image-slot-64": execution_length(
            target_ordinal, mutated(target_row, 0, 64),
            entry_count=entry_count, resolution_limit=resolution_limit),
        "bank2-code-range-wrap": execution_length(
            target_ordinal, bytes(code_wrap), entry_count=entry_count,
            resolution_limit=resolution_limit),
        "resolution-range-wrap": execution_length(
            target_ordinal, bytes(resolution_wrap), entry_count=entry_count,
            resolution_limit=resolution_limit),
        "generation-mismatch": execution_length(
            target_ordinal, bytes(wrong_generation), entry_count=entry_count,
            resolution_limit=resolution_limit),
        "persistent-count-upper-edge": execution_length(
            entry_count, target_row, entry_count=entry_count,
            resolution_limit=resolution_limit),
    }
    require(all(value == INVALID for value in negatives.values()),
            f"zero-literal negative matrix incomplete: {negatives}")
    return {
        "status": "passed-static-zero-literal-vm-run-dir-model",
        "positive": {
            "ordinal": target_ordinal,
            "name": "%lcc-consp",
            "literal_count": 0,
            "code_length": 38,
        },
        "negative_mutations": {name: "rejected" for name in negatives},
    }


def manifest_gate() -> dict[str, Any]:
    target = canonical_witness()
    identity = semantic_witness_gate(target)
    return {
        "status": "passed-real-static-entry-witness",
        "identity": identity,
        "image_entry_counts": target["image_entry_counts"],
        "global_ordinal": target["ordinal"],
        "image": target["image"],
        "local_ordinal": target["local_ordinal"],
        "name": target["name"],
        "literal_count": target["literal_count"],
        "code_length": target["code_length"],
        "code_sha256": identity["code_sha256"],
        "derived_row_hex": bytes(target["row"]).hex(),
    }


def source_gate(*, generated_runtime: Path | None = None) -> dict[str, Any]:
    generator = GENERATOR.read_text(encoding="utf-8")
    reader = function_body(
        generator, "c2_product_entry_record",
        definition="C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(")
    length = function_body(
        generator, "c2_product_entry_length",
        definition="C2_KERNAL_RESIDENT uint16_t c2_product_entry_length(")
    emitter = ENTRY_HEADER.read_text(encoding="utf-8")
    vm = VM_SOURCE.read_text(encoding="utf-8")
    require("!directory[1]" not in reader,
            "v6 reader still treats literal_count as a validity bit")
    for token in (
            "directory[0] >= 64u",
            "c2_u16(directory + 2) + c2_u16(directory + 4)",
            "c2_u16(directory + 6) + directory[1]",
            "c2_u16(directory + 8) != c2_runtime.generation"):
        require(token in reader, f"v6 entry boundary lost: {token}")
    require("? c2_u16(row + 4) : 0u" in length,
            "entry-length consumer no longer rejects zero code length")
    require("!code_length" in emitter and "!literal_count" not in emitter,
            "canonical entry emitter changed zero-literal semantics")
    require("return c2_product_entry_length(ordinal);" in vm
            and "!(length = vm_directory_length((uint16_t)di))" in vm,
            "vm_run_dir no longer consumes the canonical v6 length seam")

    generated: dict[str, Any] = {"status": "not-yet-generated"}
    if generated_runtime is not None:
        require(generated_runtime.is_file(), "generated runtime absent")
        materialized = generated_runtime.read_text(encoding="utf-8")
        materialized_reader = function_body(
            materialized, "c2_product_entry_record",
            definition="C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(")
        require("!directory[1]" not in materialized_reader,
                "generated runtime restored the nonzero-literal bug")
        generated = {
            "status": "passed-generated-zero-literal-reader",
            "runtime": generated_runtime.relative_to(ROOT).as_posix(),
        }
    return {
        "status": "passed-zero-literal-source-contract",
        "canonical_emitter": "code_length nonzero; literal_count may be zero",
        "semantic_witness_contract": semantic_witness_selftest(),
        "manifest": manifest_gate(),
        "fixture": model_gate(),
        "generated_sources": generated,
    }


def relocation_targets(truth: ElfTruth, owner_name: str) -> list[str]:
    owner = truth.symbol(owner_name)
    require(owner.bytes > 0 and owner.symbol_type == "Function",
            f"linked owner is not a sized function: {owner_name}")
    result: list[str] = []
    for row in truth.relocations:
        if (row.source_section_index != owner.section_index
                or not owner.value <= row.offset < owner.value + owner.bytes):
            continue
        identity = truth.relocation_target_identity(row)
        if identity["symbol_type"] == "Function" \
                and identity["symbol_size"] > 0:
            result.append(identity["symbol"])
            continue
        section = identity["section"]
        if section in ("Absolute", "Undefined"):
            continue
        try:
            interval = truth.resolve_interval(
                section=section, address=identity["resolved_value"])
        except ElfTruthError:
            continue
        result.append(str(interval["name"]))
    return result


def linked_gate(elf: Path, c2d: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    record = truth.symbol("c2_product_entry_record")
    length = truth.symbol("c2_product_entry_length")
    run_dir = truth.symbol("vm_run_dir")
    require(all(row.symbol_type == "Function" and row.bytes > 0
                for row in (record, length, run_dir)),
            "zero-literal execution chain lost ELF citizenship")
    run_targets = relocation_targets(truth, "vm_run_dir")
    length_targets = relocation_targets(truth, "c2_product_entry_length")
    require(run_targets.count("c2_product_entry_length") == 1,
            f"vm_run_dir length edge drift: {run_targets}")
    require(length_targets.count("c2_product_entry_record") == 1,
            f"entry-length record edge drift: {length_targets}")

    witness = canonical_witness()
    target_ordinal = int(witness["ordinal"])
    target_row = bytes(witness["row"])
    data = c2d.read_bytes()
    at = ENTRY_OFFSET + target_ordinal * ENTRY_BYTES
    row = data[at:at + ENTRY_BYTES]
    require(
        row == target_row
        and execution_length(
            target_ordinal, row,
            entry_count=int(witness["entry_count"]),
            resolution_limit=int(witness["resolution_limit"])) == 38,
            f"linked C2D zero-literal witness drift: {row.hex()}")
    return {
        "status": "passed-linked-vm-run-dir-zero-literal-chain",
        "functions": {
            "vm_run_dir": {"address": run_dir.value,
                           "bytes": run_dir.bytes,
                           "entry_length_edges": 1},
            "c2_product_entry_length": {"address": length.value,
                                        "bytes": length.bytes,
                                        "record_edges": 1},
            "c2_product_entry_record": {"address": record.value,
                                        "bytes": record.bytes},
        },
        "c2d_witness": {
            "ordinal": target_ordinal,
            "row_hex": row.hex(),
            "literal_count": row[1],
            "code_length": u16(row, 4),
        },
        "fixture": model_gate(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--c2d", type=Path)
    parser.add_argument("--generated-runtime", type=Path)
    args = parser.parse_args(argv)
    try:
        value: dict[str, Any] = {
            "source": source_gate(generated_runtime=args.generated_runtime)}
        if args.elf is not None or args.c2d is not None:
            require(args.elf is not None and args.c2d is not None,
                    "linked gate requires both --elf and --c2d")
            value["linked"] = linked_gate(args.elf, args.c2d)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (GateError, ElfTruthError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print("c2-zero-literal-execution-gate: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
