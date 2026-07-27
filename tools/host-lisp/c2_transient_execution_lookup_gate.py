#!/usr/bin/env python3
"""Prove the callable C2D-v6 transient high-edge, not only allocation.

The original 19-case contract proved allocation, publication, rollback and
collision.  This gate covers the missing consumer path exercised by hardware:
OP_CLOSURE/direct BCODE -> logical handle 4095 -> physical entry 2047 -> high
resolution/root planes -> common execution record.  It deliberately rejects
the former bug in which the high record was checked against persistent low
counts after normalization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
VM_SOURCE = ROOT / "src/vm.c"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
PERSISTENT_CAP = 2048
RESOLUTION_CAP = 4096
ROOT_CAP = 1536
INVALID = 0xffff


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def normalize(handle: int, persistent_count: int, watermark: int) -> int:
    if not 0 <= handle < 4096:
        return INVALID
    if handle < PERSISTENT_CAP:
        return handle if handle < persistent_count else INVALID
    if handle < watermark:
        return INVALID
    return handle - PERSISTENT_CAP


def execution_record(handle: int, *, persistent_count: int = 588,
                     watermark: int = 4095,
                     persistent_resolutions: int = 1931,
                     resolution_base: int = 4095,
                     literal_count: int = 1,
                     use_high_resolution_domain: bool = True) -> int:
    physical = normalize(handle, persistent_count, watermark)
    if physical == INVALID:
        return INVALID
    limit = (RESOLUTION_CAP if handle >= PERSISTENT_CAP
             and use_high_resolution_domain else persistent_resolutions)
    if resolution_base > limit or literal_count > limit - resolution_base:
        return INVALID
    return physical


def materialize_root(handle: int, root: int, *, persistent_roots: int = 421,
                     use_high_root_domain: bool = True) -> bool:
    limit = (ROOT_CAP if handle >= PERSISTENT_CAP and use_high_root_domain
             else persistent_roots)
    return 0 <= root < limit


def model_gate() -> dict[str, Any]:
    require(execution_record(4095) == 2047,
            "first transient handle is not callable as physical entry 2047")
    require(execution_record(4094) == INVALID,
            "stale handle immediately below the watermark remained callable")
    require(execution_record(
        4095, use_high_resolution_domain=False) == INVALID,
        "persistent resolution-count regression fixture is ineffective")
    require(materialize_root(4095, 1535),
            "last transient root surrogate is not materializable")
    require(not materialize_root(
        4095, 1535, use_high_root_domain=False),
        "persistent root-count regression fixture is ineffective")
    require(execution_record(
        587, persistent_count=588, watermark=4096,
        persistent_resolutions=1931, resolution_base=1930) == 587,
        "persistent execution path changed under the high-edge fix")
    return {
        "status": "passed-callable-transient-high-edge-model",
        "positive": {
            "logical_handle": 4095, "physical_entry": 2047,
            "resolution_interval": [4095, 4096],
            "maximum_root_ordinal": 1535,
        },
        "negative_mutations": {
            "stale-handle-below-watermark": "rejected",
            "transient-resolution-checked-against-persistent-count": "rejected",
            "transient-root-checked-against-persistent-count": "rejected",
        },
        "persistent_regression": "handle 587 remains physical entry 587",
    }


def source_gate(*, generated_runtime: Path | None = None,
                generated_hot: Path | None = None) -> dict[str, Any]:
    vm = VM_SOURCE.read_text(encoding="utf-8")
    generator = GENERATOR.read_text(encoding="utf-8")
    require("int di = IS_BCODE(sym) ? (int)BCODE_IDX(sym) : dir_find(sym);"
            in vm, "OP_CLOSURE no longer keeps BCODE off the symbol lookup")
    for token in (
            "uint8_t transient = (uint8_t)(ordinal >= 2048u);",
            "uint16_t resolution_limit = transient ? 4096u : c2_runtime.resolution_count;",
            "(uint32_t)c2_u16(directory + 6) + directory[1]",
            "resolution_limit = transient ? 4096u : c->resolution_count;",
            "root_limit = transient ? 1536u : c->c2_root_count;"):
        require(token in generator,
                f"transient execution source contract drift: {token}")
    generated: dict[str, Any] = {"status": "not-yet-generated"}
    if generated_runtime is not None or generated_hot is not None:
        require(generated_runtime is not None and generated_hot is not None
                and generated_runtime.is_file() and generated_hot.is_file(),
                "generated v6 execution sources are incomplete")
        runtime = generated_runtime.read_text(encoding="utf-8")
        hot = generated_hot.read_text(encoding="utf-8")
        for token in (
                "uint8_t transient = (uint8_t)(ordinal >= 2048u);",
                "uint16_t resolution_limit = transient ? 4096u : c2_runtime.resolution_count;",
                "(uint32_t)c2_u16(directory + 6) + directory[1]"):
            require(token in runtime,
                    f"generated runtime lost transient domain split: {token}")
        for token in (
                "resolution_limit = transient ? 4096u : c->resolution_count;",
                "root_limit = transient ? 1536u : c->c2_root_count;"):
            require(token in hot,
                    f"generated materializer lost transient domain split: {token}")
        generated = {
            "status": "passed-generated-source-domain-split",
            "runtime": generated_runtime.relative_to(ROOT).as_posix(),
            "hot": generated_hot.relative_to(ROOT).as_posix(),
        }
    return {
        "status": "passed-OP_CLOSURE-direct-BCODE-and-v6-high-domain-source",
        "op_closure": "BCODE_IDX direct; dir_find is symbol-only",
        "model": model_gate(),
        "generated_sources": generated,
    }


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    normalizer = truth.symbol("c2_product_handle_normalize")
    record = truth.symbol("c2_product_entry_record")
    materializer = truth.symbol("c2_stream_product_materialize_entry")
    require(normalizer.symbol_type == record.symbol_type ==
            materializer.symbol_type == "Function"
            and min(normalizer.bytes, record.bytes, materializer.bytes) > 0,
            "transient execution functions lost sized ELF citizenship")
    targets = [row.target for row in truth.relocations
               if row.source_section_index == record.section_index
               and record.value <= row.offset < record.value + record.bytes]
    require(targets.count("c2_facade_handle_normalize") == 1,
            "v6 record path does not use the one high-edge normalizer")
    return {
        "status": "passed-linked-one-normalizer-common-record-path",
        "normalizer": {"section": normalizer.section,
                       "address": normalizer.value, "bytes": normalizer.bytes},
        "record": {"section": record.section,
                   "address": record.value, "bytes": record.bytes,
                   "normalizer_edges": 1},
        "materializer": {"section": materializer.section,
                         "address": materializer.value,
                         "bytes": materializer.bytes},
        "fixture": model_gate(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--generated-runtime", type=Path)
    parser.add_argument("--generated-hot", type=Path)
    args = parser.parse_args(argv)
    try:
        value = {"source": source_gate(
            generated_runtime=args.generated_runtime,
            generated_hot=args.generated_hot)}
        if args.elf is not None:
            value["linked"] = linked_gate(args.elf)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (GateError, ElfTruthError, OSError, ValueError) as error:
        print("c2-transient-execution-lookup-gate: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
