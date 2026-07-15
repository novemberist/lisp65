#!/usr/bin/env python3
"""Model and gate the complete L65M phase-major commit transaction."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


SCHEMA = "lisp65-l65m-commit-ops-v1"
PHASE_NAMES = (
    "verify",
    "patch-record",
    "materialize-shape",
    "materialize-scalars",
    "materialize-strings",
    "patch-publish",
    "entries",
)
CRC_RUNS_PER_TRANSPORT = 6
NAME_MAX = 32
SOURCE_READ_BUDGET = 15_000
PREFLIGHT_SYMBOL_DMA_BUDGET = 40_000
COMMIT_NAMEPOOL_DMA_BUDGET = 250_000
COMMIT_RECURSION_DEPTH_LIMIT = 9
COMMIT_RECURSION_FRAME_BUDGET = 512
COMMIT_RECURSION_SYMBOLS = {
    "materialize-shape": "commit_shape_02",
    "materialize-scalars": "commit_scalars_03",
    "materialize-strings": "commit_strings_04",
}
ITERATIVE_HELPER_PROTOTYPE_BYTES = 1899
LIT_FIX, LIT_NIL, LIT_T, LIT_SYMBOL, LIT_CONS, LIT_LIST, LIT_STRING = range(1, 8)


class GateError(RuntimeError):
    pass


def measured_recursion_frames(disassembly: str) -> dict[str, int]:
    """Read llvm-mos' dynamic software-stack decrement from each prologue."""
    frames: dict[str, int] = {}
    for label, symbol in COMMIT_RECURSION_SYMBOLS.items():
        matches = re.findall(
            rf"^[0-9a-f]+ <{re.escape(symbol)}>:\n"
            r"\s*[0-9a-f]+:\s+pha\s*\n"
            r"\s*[0-9a-f]+:\s+clc\s*\n"
            r"\s*[0-9a-f]+:\s+lda\s+\$2(?:\s+;[^\n]*)?\n"
            r"\s*[0-9a-f]+:\s+adc\s+#\$([0-9a-f]{1,2})\s*\n"
            r"\s*[0-9a-f]+:\s+sta\s+\$2(?:\s+;[^\n]*)?\n"
            r"\s*[0-9a-f]+:\s+lda\s+\$3(?:\s+;[^\n]*)?\n"
            r"\s*[0-9a-f]+:\s+adc\s+#\$ff\s*\n"
            r"\s*[0-9a-f]+:\s+sta\s+\$3(?:\s+;[^\n]*)?\n"
            r"\s*[0-9a-f]+:\s+pla\s*$",
            disassembly, re.M,
        )
        if len(matches) != 1:
            raise GateError(f"MOS stack prologue for {symbol}: {len(matches)} expected=1")
        decrement = int(matches[0], 16)
        frame = (-decrement) & 0xff
        if not frame:
            raise GateError(f"zero MOS recursion frame: {symbol}")
        frames[label] = frame
    return frames


def read_measured_recursion_frames(
    elf: Path, objdump: Path,
) -> tuple[dict[str, int], str]:
    try:
        run = subprocess.run(
            [str(objdump), "-d", "--no-show-raw-insn", str(elf)],
            check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise GateError(f"MOS disassembly failed: {exc.stderr.strip()}") from exc
    return (measured_recursion_frames(run.stdout),
            hashlib.sha256(run.stdout.encode("utf-8")).hexdigest())


def check_recursion_frames(frames: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if set(frames) != set(COMMIT_RECURSION_SYMBOLS):
        errors.append("measured-recursion-frame-set-mismatch")
        return errors
    for name, frame_bytes in frames.items():
        projected = COMMIT_RECURSION_DEPTH_LIMIT * frame_bytes
        if projected > COMMIT_RECURSION_FRAME_BUDGET:
            errors.append(
                f"{name}-contract-worst-case-recursion-bytes={projected} "
                f"budget={COMMIT_RECURSION_FRAME_BUDGET}")
    return errors


def u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise GateError(f"u16 outside image at {offset}")
    return data[offset] | (data[offset + 1] << 8)


def c_string(pool: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(pool):
        raise GateError(f"string offset outside pool: {offset}")
    end = pool.find(b"\0", offset, min(len(pool), offset + NAME_MAX + 1))
    if end < 0:
        raise GateError(f"unterminated string at pool offset {offset}")
    try:
        return pool[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"invalid UTF-8 string at pool offset {offset}") from exc


@dataclass(frozen=True)
class Entry:
    name_off: int
    flags: int


@dataclass(frozen=True)
class Node:
    kind: int
    first: int
    count: int
    name_off: int


@dataclass(frozen=True)
class Image:
    raw: bytes
    blob_len: int
    metadata_len: int
    entries: tuple[Entry, ...]
    indices: tuple[int, ...]
    nodes: tuple[Node, ...]
    patches: tuple[tuple[int, int], ...]
    strings: bytes

    @classmethod
    def read(cls, path: Path) -> "Image":
        raw = path.read_bytes()
        if len(raw) < 42:
            raise GateError("L65M image is too short")
        blob_len, metadata_len = u16(raw, 0), u16(raw, 2)
        if 4 + blob_len + metadata_len != len(raw):
            raise GateError("L65M prefix lengths do not cover the image")
        metadata = raw[4 + blob_len :]
        if metadata[:4] != b"L65M" or metadata[4] != 1 or metadata[5] != 38:
            raise GateError("unsupported L65M header")
        entry_count = u16(metadata, 16)
        index_count = u16(metadata, 18)
        node_count = u16(metadata, 20)
        patch_count = u16(metadata, 22)
        entries_off = u16(metadata, 24)
        index_off = u16(metadata, 26)
        nodes_off = u16(metadata, 28)
        patches_off = u16(metadata, 30)
        strings_off = u16(metadata, 32)
        strings_bytes = u16(metadata, 34)
        if strings_off + strings_bytes > len(metadata):
            raise GateError("string pool exceeds metadata")
        entries = tuple(
            Entry(u16(metadata, entries_off + 8 * i), metadata[entries_off + 8 * i + 3])
            for i in range(entry_count)
        )
        indices = tuple(u16(metadata, index_off + 2 * i) for i in range(index_count))
        nodes = tuple(
            Node(
                metadata[nodes_off + 10 * i],
                u16(metadata, nodes_off + 10 * i + 4),
                u16(metadata, nodes_off + 10 * i + 6),
                u16(metadata, nodes_off + 10 * i + 8),
            )
            for i in range(node_count)
        )
        patches = tuple(
            (u16(metadata, patches_off + 4 * i), u16(metadata, patches_off + 4 * i + 2))
            for i in range(patch_count)
        )
        image = cls(
            raw,
            blob_len,
            metadata_len,
            entries,
            indices,
            nodes,
            patches,
            metadata[strings_off : strings_off + strings_bytes],
        )
        image.validate_references()
        return image

    def validate_references(self) -> None:
        for entry in self.entries:
            c_string(self.strings, entry.name_off)
        for index in self.indices:
            if index >= len(self.nodes):
                raise GateError(f"literal index outside node table: {index}")
        for _, node in self.patches:
            if node >= len(self.nodes):
                raise GateError(f"patch node outside node table: {node}")
        for node in self.nodes:
            if node.kind in (LIT_SYMBOL, LIT_STRING):
                c_string(self.strings, node.name_off)
            if node.kind in (LIT_CONS, LIT_LIST):
                if node.first + node.count > len(self.indices):
                    raise GateError("aggregate node exceeds index table")


@dataclass
class PhaseCost:
    logical_steps: int = 0
    source_reads: int = 0
    source_bytes: int = 0
    node_visits: int = 0
    index_reads: int = 0
    name_reads: int = 0

    def add_read(self, size: int, *, name: bool = False) -> None:
        self.source_reads += 1
        self.source_bytes += size
        if name:
            self.name_reads += 1


@dataclass(frozen=True)
class Trace:
    application_loads: int
    ingress_crc_runs: int
    egress_crc_runs: int
    phase_steps: tuple[int, ...]
    aborted: bool = False
    cleanup_called: bool = True
    transport_reusable: bool = True


def check_trace(trace: Trace, expected_steps: Sequence[int]) -> list[str]:
    errors: list[str] = []
    phase_count = len(expected_steps)
    if trace.application_loads != phase_count:
        errors.append(
            f"application-loads={trace.application_loads} expected={phase_count}"
        )
    if trace.ingress_crc_runs != phase_count:
        errors.append(
            f"ingress-crc-runs={trace.ingress_crc_runs} expected={phase_count}"
        )
    if trace.egress_crc_runs != phase_count:
        errors.append(
            f"egress-crc-runs={trace.egress_crc_runs} expected={phase_count}"
        )
    if tuple(trace.phase_steps) != tuple(expected_steps):
        errors.append(
            "phase-steps=" + ",".join(map(str, trace.phase_steps))
            + " expected=" + ",".join(map(str, expected_steps))
        )
    if trace.aborted and not trace.cleanup_called:
        errors.append("abort-cleanup=missing")
    if trace.aborted and not trace.transport_reusable:
        errors.append("abort-transport=latched")
    return errors


def walk(
    image: Image,
    index: int,
    cost: PhaseCost,
    visit: Callable[[Node], None] | None = None,
    depth: int = 0,
) -> None:
    if depth > 32 or index >= len(image.nodes):
        raise GateError("literal traversal exceeded its validated bound")
    node = image.nodes[index]
    cost.node_visits += 1
    cost.add_read(10)
    if visit is not None:
        visit(node)
    if node.kind in (LIT_CONS, LIT_LIST):
        for child_pos in range(node.first, node.first + node.count):
            cost.index_reads += 1
            cost.add_read(2)
            walk(image, image.indices[child_pos], cost, visit, depth + 1)


def phase_costs(image: Image) -> tuple[list[PhaseCost], list[str], list[str]]:
    costs = [PhaseCost() for _ in PHASE_NAMES]
    patch_count, entry_count = len(image.patches), len(image.entries)
    expected_steps = (1, patch_count, patch_count, patch_count, patch_count,
                      patch_count, entry_count)
    for cost, steps in zip(costs, expected_steps):
        cost.logical_steps = steps

    verify = costs[0]
    for offset in range(0, len(image.raw), 16):
        verify.add_read(min(16, len(image.raw) - offset))

    patch_record = costs[1]
    for _ in image.patches:
        patch_record.add_read(4)

    scalar_interns: list[str] = []
    publish_interns: list[str] = []
    for _, root in image.patches:
        costs[2].add_read(4)
        walk(image, root, costs[2])

        costs[3].add_read(4)
        def scalar_visit(node: Node) -> None:
            if node.kind == LIT_T:
                scalar_interns.append("t")
            elif node.kind == LIT_SYMBOL:
                name = c_string(image.strings, node.name_off)
                scalar_interns.append(name)
                costs[3].add_read(len(name.encode("utf-8")) + 1, name=True)

        walk(image, root, costs[3], scalar_visit)

        costs[4].add_read(4)
        def string_visit(node: Node) -> None:
            if node.kind == LIT_STRING:
                value = c_string(image.strings, node.name_off)
                costs[4].add_read(len(value.encode("utf-8")) + 1, name=True)

        walk(image, root, costs[4], string_visit)
        costs[5].add_read(4)
        if image.nodes[root].kind in (LIT_CONS, LIT_LIST, LIT_STRING):
            publish_interns.append("%lit-keep")

    entry_interns: list[str] = []
    for entry in image.entries:
        name = c_string(image.strings, entry.name_off)
        entry_interns.append(name)
        costs[6].add_read(8)
        costs[6].add_read(len(name.encode("utf-8")) + 1, name=True)
    return costs, scalar_interns + publish_interns + entry_interns, entry_interns


def preflight_symbol_names(image: Image) -> list[str]:
    result = [c_string(image.strings, entry.name_off) for entry in image.entries]
    seen_offsets = {entry.name_off for entry in image.entries}
    any_t = False
    any_pointer = False
    for node in image.nodes:
        any_t = any_t or node.kind == LIT_T
        if node.kind == LIT_SYMBOL and node.name_off not in seen_offsets:
            seen_offsets.add(node.name_off)
            result.append(c_string(image.strings, node.name_off))
    explicit = {c_string(image.strings, offset) for offset in seen_offsets}
    for _, root in image.patches:
        any_pointer = any_pointer or image.nodes[root].kind in (
            LIT_CONS, LIT_LIST, LIT_STRING
        )
    if any_t and "t" not in explicit:
        result.append("t")
    if any_pointer and "%lit-keep" not in explicit:
        result.append("%lit-keep")
    return result


def image_graph_depth(image: Image) -> int:
    memo: dict[int, int] = {}
    active: set[int] = set()

    def depth(index: int) -> int:
        if index in memo:
            return memo[index]
        if index in active:
            raise GateError("literal graph contains a cycle")
        active.add(index)
        node = image.nodes[index]
        result = 1
        if node.kind in (LIT_CONS, LIT_LIST) and node.count:
            result += max(depth(image.indices[pos])
                          for pos in range(node.first, node.first + node.count))
        active.remove(index)
        memo[index] = result
        return result

    return max((depth(root) for _, root in image.patches), default=0)


def manifest_symbols(path: Path | None) -> list[str]:
    if path is None:
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    names = document.get("cost", {}).get("symbol_names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise GateError("symbol manifest has no cost.symbol_names list")
    if len(names) != len(set(names)):
        raise GateError("symbol manifest contains duplicate symbol names")
    return list(names)


def symbol_dma_projection(baseline: Sequence[str], lookups: Iterable[str], mutate: bool) -> dict[str, int]:
    table = list(baseline)
    result = Counter(
        lookup_calls=0,
        nameoff_reads=0,
        namepool_reads=0,
        namepool_writes=0,
        nameoff_writes=0,
        symval_writes=0,
        symfn_writes=0,
    )
    for name in lookups:
        result["lookup_calls"] += 1
        capped = min(len(name.encode("utf-8")), 15)
        found = False
        for present in table:
            if min(len(present.encode("utf-8")), 15) != capped:
                continue
            result["nameoff_reads"] += 1
            result["namepool_reads"] += 1
            if present == name:
                found = True
                break
        if mutate and not found:
            table.append(name)
            result["namepool_writes"] += 1
            result["nameoff_writes"] += 1
            result["symval_writes"] += 1
            result["symfn_writes"] += 1
    result["dma_reads"] = result["nameoff_reads"] + result["namepool_reads"]
    result["dma_writes"] = (
        result["namepool_writes"] + result["nameoff_writes"]
        + result["symval_writes"] + result["symfn_writes"]
    )
    result["dma_total"] = result["dma_reads"] + result["dma_writes"]
    return dict(result)


def function_body(source: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", source, re.S)
    if not match:
        raise GateError(f"missing function body: {name}")
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise GateError(f"unterminated function body: {name}")


def source_audit(
    integration: str,
    commit: str,
    transport: str,
    scratch: str | None = None,
    symbol: str | None = None,
    predicate: str | None = None,
) -> list[str]:
    errors: list[str] = []
    body = function_body(integration, "vm_load_lib_ext")
    batch_calls = body.count("vm_runtime_overlay_exec_batch(")
    single_calls = body.count("vm_runtime_overlay_exec(")
    if batch_calls != 1:
        errors.append(f"integration-batch-calls={batch_calls} expected=1")
    if single_calls:
        errors.append(f"integration-single-calls={single_calls} expected=0")
    if "L65M_COMMIT_PHASE_COUNT" not in body:
        errors.append("integration-phase-count-bound=missing")
    if "VM_RUNTIME_OVERLAY_BATCH_COMMIT" not in body:
        errors.append("integration-commit-batch-policy=missing")
    if "vm_l65m_commit_batch_repeat" not in body:
        errors.append("integration-commit-repeat-predicate=missing")
    if body.count("work.context_size != L65M_COMMIT_CONTEXT_SIZE") < 2:
        errors.append("integration-context-size-boundary-check=missing")
    canonical_end = re.search(
        r"!work\.finished\s*\|\|\s*"
        r"work\.context_size\s*!=\s*L65M_COMMIT_CONTEXT_SIZE\s*\|\|\s*"
        r"work\.expected_phase\s*!=\s*L65M_COMMIT_PHASE_COUNT",
        body,
        re.S,
    )
    if not canonical_end:
        errors.append("integration-canonical-end-state=missing")

    phase_functions = (
        "l65m_commit_phase_patch_record",
        "l65m_commit_phase_materialize_shape",
        "l65m_commit_phase_materialize_scalars",
        "l65m_commit_phase_materialize_strings",
        "l65m_commit_phase_patch_publish",
    )
    for name in phase_functions:
        phase_body = function_body(commit, name)
        if "patch_count" not in phase_body or "commit_more(" not in phase_body:
            errors.append(f"{name}-repeat-progress=missing")
        if re.search(r"\b(for|while|do)\b", phase_body):
            errors.append(f"{name}-inner-loop=present")
    entries = function_body(commit, "l65m_commit_phase_entries")
    if "entry_count" not in entries or "commit_more(" not in entries:
        errors.append("l65m_commit_phase_entries-repeat-progress=missing")
    if re.search(r"\b(for|while|do)\b", entries):
        errors.append("l65m_commit_phase_entries-inner-loop=present")

    for helper in ("commit_shape_02", "commit_scalars_03", "commit_strings_04"):
        if re.search(r"\b" + re.escape(helper) + r"\s*\(", commit):
            helper_body = function_body(commit, helper)
            if re.search(r"\b" + re.escape(helper) + r"\s*\(", helper_body):
                guarded_before_descent = (
                    "depth >= L65M_MAX_GRAPH_DEPTH" in helper_body
                    or re.search(
                        r"\+\+depth\s*>\s*L65M_MAX_GRAPH_DEPTH",
                        helper_body) is not None
                )
                if not guarded_before_descent:
                    errors.append(f"{helper}-depth-guard=missing")
                if ("++depth" not in helper_body
                        and not re.search(r"depth\s*\+\s*1u", helper_body)):
                    errors.append(f"{helper}-depth-increment=missing")

    final_crc = re.search(
        r"rtov_crc_mem\s*\([^;]*RTOV_TARGET[^;]*rtov_loaded_len[^;]*\)\s*!=\s*"
        r"rtov_batch_crc",
        transport,
        re.S,
    )
    if not final_crc:
        errors.append("transport-egress-crc=missing")
    if "vm_runtime_overlay_abort_cleanup" not in transport:
        errors.append("transport-abort-cleanup=missing")
    if scratch is not None:
        adapter = function_body(scratch, "disk_lib_read")
        if adapter.count("ext_disk_read(") != 1 or "ext_disk_get(" in adapter:
            errors.append("scratch-bulk-dma-adapter=missing")
    if symbol is not None:
        lookup = function_body(symbol, "sym_lookup")
        compare = function_body(symbol, "sympool_streq")
        nameoff = function_body(integration, "nameoff_get")
        pool = function_body(integration, "sympool_read")
        if "nlen4_get(" not in lookup or "sympool_streq(" not in lookup:
            errors.append("symbol-length-filter=missing")
        if compare.count("sympool_read(") != 1:
            errors.append("symbol-name-bulk-read=missing")
        if nameoff.count("vm_dma(") != 1 or pool.count("vm_dma(") != 1:
            errors.append("symbol-ext-dma-adapter=missing")
    if predicate is not None:
        required = {
            "predicate-island-section": ".section\t.lisp65_resident_island",
            "predicate-export": ".globl\tvm_l65m_batch_repeat",
            "predicate-result-check": "cpx\t#ASM_L65M_OK",
            "predicate-null-context-high": "ora\t__rc3",
            "predicate-preflight-abi": "cmp\t#ASM_L65M_PREFLIGHT_ABI",
            "predicate-commit-abi": "cmp\t#ASM_L65M_COMMIT_ABI",
            "predicate-preflight-slot-base": "ldy\t#ASM_L65M_PREFLIGHT_SLOT_BASE",
            "predicate-commit-slot-base": "ldy\t#ASM_L65M_COMMIT_SLOT_BASE",
            "predicate-phase-offset": "ldy\t#ASM_L65M_EXPECTED_PHASE_OFFSET",
            "predicate-busy-offset": "ldy\t#ASM_L65M_BUSY_OFFSET",
            "predicate-repeat-offset": "ldy\t#ASM_L65M_REPEAT_PHASE_OFFSET",
        }
        for name, token in required.items():
            if token not in predicate:
                errors.append(f"{name}=missing")
        if not re.search(r"^\s*ldy\s+#ASM_L65M_ABI_VERSION_HIGH_OFFSET(?:\s*;.*)?$", predicate, re.M):
            errors.append("predicate-abi-high-byte=missing")
        if "sbc\t__rc6" not in predicate or "cmp\t(__rc2),y" not in predicate:
            errors.append("predicate-slot-phase-compare=missing")
        if "ora\t(__rc2),y" not in predicate:
            errors.append("predicate-transport-state-check=missing")
    return errors


def expected_steps(image: Image) -> tuple[int, ...]:
    return (1,) + (len(image.patches),) * 5 + (len(image.entries),)


def check_budgets(source_reads: int, preflight_symbol_dmas: int,
                  commit_namepool_dmas: int) -> list[str]:
    errors: list[str] = []
    for name, actual, budget in (
        ("source-reads", source_reads, SOURCE_READ_BUDGET),
        ("preflight-symbol-dmas", preflight_symbol_dmas,
         PREFLIGHT_SYMBOL_DMA_BUDGET),
        ("commit-namepool-dmas", commit_namepool_dmas,
         COMMIT_NAMEPOOL_DMA_BUDGET),
    ):
        if actual > budget:
            errors.append(f"{name}={actual} budget={budget}")
    return errors


def make_report(
    image_path: Path,
    elf_path: Path,
    image: Image,
    costs: Sequence[PhaseCost],
    baseline: Sequence[str],
    recursion_frames: dict[str, int],
    disassembly_sha256: str,
    source_errors: Sequence[str],
) -> str:
    steps = expected_steps(image)
    graph_depth = image_graph_depth(image)
    loads = len(PHASE_NAMES)
    legacy_loads = 1 + len(image.patches) * 5 + len(image.entries)
    preflight_names = preflight_symbol_names(image)
    _, commit_interns, _ = phase_costs(image)
    preflight_dma = symbol_dma_projection(baseline, preflight_names, False)
    commit_dma = symbol_dma_projection(baseline, commit_interns, True)
    lines = [
        f"schema={SCHEMA}",
        f"artifact={image_path}",
        f"artifact_sha256={hashlib.sha256(image.raw).hexdigest()}",
        f"artifact_bytes={len(image.raw)}",
        f"mos_elf={elf_path}",
        f"mos_elf_sha256={hashlib.sha256(elf_path.read_bytes()).hexdigest()}",
        f"mos_disassembly_sha256={disassembly_sha256}",
        "mos_recursion_frame_source=llvm-objdump-software-stack-prologue",
        f"entry_count={len(image.entries)}",
        f"node_count={len(image.nodes)}",
        f"patch_count={len(image.patches)}",
        f"artifact_max_graph_depth={graph_depth}",
        f"commit_recursion_depth_limit={COMMIT_RECURSION_DEPTH_LIMIT}",
        f"commit_recursion_frame_budget={COMMIT_RECURSION_FRAME_BUDGET}",
        f"iterative_helper_prototype_bytes={ITERATIVE_HELPER_PROTOTYPE_BYTES}",
        "iterative_helper_slice_limit=1792",
        "materializer_decision=bounded-recursion-iterative-prototype-too-large",
        "semantics=phase-major-commit-with-ingress-and-egress-crc",
        f"phase_major_application_slice_loads={loads}",
        f"phase_major_application_load_budget={len(PHASE_NAMES)}",
        f"legacy_per_item_application_slice_loads={legacy_loads}",
        f"eliminated_application_slice_loads={legacy_loads - loads}",
        f"phase_major_application_ingress_crc_runs={loads}",
        f"phase_major_transport_ingress_crc_runs={loads * 3}",
        f"phase_major_catalog_metadata_crc_runs={loads * 2}",
        f"phase_major_egress_crc_runs={loads}",
        f"phase_major_total_crc_runs={loads * CRC_RUNS_PER_TRANSPORT}",
        f"legacy_total_crc_runs={legacy_loads * CRC_RUNS_PER_TRANSPORT}",
    ]
    total_reads = total_bytes = total_steps = 0
    for phase, (name, cost, budget) in enumerate(zip(PHASE_NAMES, costs, steps)):
        lines.append(
            f"phase={phase:02d} name={name} logical_steps={cost.logical_steps} "
            f"step_budget={budget} source_read_calls={cost.source_reads} "
            f"source_read_bytes={cost.source_bytes} node_visits={cost.node_visits} "
            f"index_reads={cost.index_reads} name_reads={cost.name_reads} "
            "application_slice_loads=1 transport_ingress_crc_runs=3 "
            "catalog_metadata_crc_runs=2 egress_crc_runs=1"
        )
        total_reads += cost.source_reads
        total_bytes += cost.source_bytes
        total_steps += cost.logical_steps
    lines.extend(
        (
            f"total_logical_steps={total_steps}",
            f"total_source_read_calls={total_reads}",
            f"total_source_read_budget={SOURCE_READ_BUDGET}",
            f"total_source_read_bytes={total_bytes}",
            f"preflight_symbol_exists_calls={preflight_dma['lookup_calls']}",
            f"preflight_symbol_dma_reads_projected={preflight_dma['dma_reads']}",
            f"preflight_symbol_dma_budget={PREFLIGHT_SYMBOL_DMA_BUDGET}",
            f"commit_intern_calls={commit_dma['lookup_calls']}",
            f"commit_namepool_dma_reads_projected={commit_dma['dma_reads']}",
            f"commit_namepool_dma_writes_projected={commit_dma['dma_writes']}",
            f"commit_namepool_dma_total_projected={commit_dma['dma_total']}",
            f"commit_namepool_dma_budget={COMMIT_NAMEPOOL_DMA_BUDGET}",
            f"symbol_projection_baseline_names={len(baseline)}",
            "scratch_bulk_dma_adapter_audited=1",
            "symbol_namepool_dma_adapter_audited=1",
            f"source_audit_violations={len(source_errors)}",
        )
    )
    for name, frame_bytes in recursion_frames.items():
        lines.append(f"{name}_frame_bytes_per_depth={frame_bytes}")
        lines.append(
            f"{name}_projected_recursion_bytes={graph_depth * frame_bytes}")
        lines.append(
            f"{name}_contract_worst_case_recursion_bytes="
            f"{COMMIT_RECURSION_DEPTH_LIMIT * frame_bytes}")
    lines.extend(f"source_audit={error}" for error in source_errors)
    lines.append(f"gate={'PASS' if not source_errors else 'FAIL'}")
    return "\n".join(lines) + "\n"


def selftest() -> None:
    def prologue(address: int, name: str, decrement: int) -> str:
        instructions = (
            ("pha", ""), ("clc", ""), ("lda", "$2"),
            ("adc", f"#${decrement:02x}"), ("sta", "$2"),
            ("lda", "$3"), ("adc", "#$ff"), ("sta", "$3"),
            ("pla", ""),
        )
        lines = [f"{address:08x} <{name}>:"]
        lines.extend(f"    {address + i:04x}:      \t{op}\t{arg}".rstrip()
                     for i, (op, arg) in enumerate(instructions))
        return "\n".join(lines)

    disassembly = "\n".join((
        prologue(0x1000, "commit_shape_02", 0xed),
        prologue(0x1100, "commit_scalars_03", 0xca),
        prologue(0x1200, "commit_strings_04", 0xeb),
    ))
    measured = measured_recursion_frames(disassembly)
    if measured != {
        "materialize-shape": 19,
        "materialize-scalars": 54,
        "materialize-strings": 21,
    } or check_recursion_frames(measured):
        raise GateError("valid measured recursion frames were rejected")
    stack_mutations = (
        disassembly.replace("commit_strings_04", "missing_strings_04"),
        disassembly + "\n" + prologue(0x1300, "commit_scalars_03", 0xca),
        disassembly.replace("\tadc\t#$ff", "\tadc\t#$fe", 1),
    )
    for mutation in stack_mutations:
        try:
            measured_recursion_frames(mutation)
        except GateError:
            pass
        else:
            raise GateError("invalid MOS stack-size mutation survived")
    over_budget = dict(measured)
    over_budget["materialize-scalars"] = 57
    if not check_recursion_frames(over_budget):
        raise GateError("over-budget measured recursion frame survived")
    expected = (1, 3, 3, 3, 3, 3, 2)
    good = Trace(7, 7, 7, expected)
    if check_trace(good, expected):
        raise GateError("valid phase-major trace was rejected")
    mutations = {
        "legacy-per-item-reload": Trace(18, 18, 18, expected),
        "missing-egress-crc": Trace(7, 7, 6, expected),
        "step-limit": Trace(7, 7, 7, (1, 4, 3, 3, 3, 3, 2)),
        "abort-cleanup": Trace(7, 7, 7, expected, True, False, True),
        "abort-latch": Trace(7, 7, 7, expected, True, True, False),
    }
    for name, mutation in mutations.items():
        if not check_trace(mutation, expected):
            raise GateError(f"mutation survived: {name}")
    good_integration = """
        int vm_load_lib_ext(void) {
          while (phase<L65M_COMMIT_PHASE_COUNT) {
            vm_runtime_overlay_exec_batch(phase, 0, 0,
              VM_RUNTIME_OVERLAY_BATCH_COMMIT, vm_l65m_commit_batch_repeat);
            if (work.context_size != L65M_COMMIT_CONTEXT_SIZE) return 1;
          }
          if (!work.finished
              || work.context_size != L65M_COMMIT_CONTEXT_SIZE
              || work.expected_phase != L65M_COMMIT_PHASE_COUNT) return 1;
        }
    """
    good_commit = "\n".join(
        f"int {name}(void) {{ cursor++; commit_more(work, work->patch_count); }}"
        for name in (
            "l65m_commit_phase_patch_record",
            "l65m_commit_phase_materialize_shape",
            "l65m_commit_phase_materialize_scalars",
            "l65m_commit_phase_materialize_strings",
            "l65m_commit_phase_patch_publish",
        )
    ) + "\nint l65m_commit_phase_entries(void) { cursor++; commit_more(work, work->entry_count); }"
    good_transport = """
      int rtov_crc_mem(void); int vm_runtime_overlay_abort_cleanup(void);
      int f(void) { return rtov_crc_mem((void *)RTOV_TARGET, rtov_loaded_len)
                             != rtov_batch_crc; }
    """
    if source_audit(good_integration, good_commit, good_transport):
        raise GateError("valid source contract was rejected")
    if not source_audit(good_integration.replace("_batch", ""), good_commit, good_transport):
        raise GateError("legacy single-exec mutation survived")
    missing_boundary = good_integration.replace(
        "work.context_size != L65M_COMMIT_CONTEXT_SIZE", "0", 1)
    if not source_audit(missing_boundary, good_commit, good_transport):
        raise GateError("missing context-size boundary mutation survived")
    missing_end_phase = good_integration.replace(
        "|| work.expected_phase != L65M_COMMIT_PHASE_COUNT", "", 1)
    if not source_audit(missing_end_phase, good_commit, good_transport):
        raise GateError("missing canonical end-phase mutation survived")
    if not source_audit(good_integration, good_commit, "int vm_runtime_overlay_abort_cleanup(void);"):
        raise GateError("missing egress CRC mutation survived")
    if check_budgets(SOURCE_READ_BUDGET, PREFLIGHT_SYMBOL_DMA_BUDGET,
                     COMMIT_NAMEPOOL_DMA_BUDGET):
        raise GateError("valid operation budgets were rejected")
    if len(check_budgets(SOURCE_READ_BUDGET + 1,
                         PREFLIGHT_SYMBOL_DMA_BUDGET + 1,
                         COMMIT_NAMEPOOL_DMA_BUDGET + 1)) != 3:
        raise GateError("operation-budget mutations survived")
    guarded_recursive = good_commit + """
      int commit_shape_02(int depth) {
        if (depth >= L65M_MAX_GRAPH_DEPTH) return 0;
        return commit_shape_02(depth + 1u);
      }
    """
    if source_audit(good_integration, guarded_recursive, good_transport):
        raise GateError("bounded recursion contract was rejected")
    unguarded_recursive = guarded_recursive.replace(
        "if (depth >= L65M_MAX_GRAPH_DEPTH) return 0;", "")
    if not source_audit(good_integration, unguarded_recursive, good_transport):
        raise GateError("unguarded recursion mutation survived")
    good_predicate = """
\t.section\t.lisp65_resident_island
\t.globl\tvm_l65m_batch_repeat
\tcpx\t#ASM_L65M_OK
\tora\t__rc3
\tcmp\t#ASM_L65M_PREFLIGHT_ABI
\tcmp\t#ASM_L65M_COMMIT_ABI
\tldy\t#ASM_L65M_ABI_VERSION_HIGH_OFFSET
\tldy\t#ASM_L65M_PREFLIGHT_SLOT_BASE
\tldy\t#ASM_L65M_COMMIT_SLOT_BASE
\tsbc\t__rc6
\tldy\t#ASM_L65M_EXPECTED_PHASE_OFFSET
\tcmp\t(__rc2),y
\tldy\t#ASM_L65M_BUSY_OFFSET
\tora\t(__rc2),y
\tldy\t#ASM_L65M_REPEAT_PHASE_OFFSET
"""
    if source_audit(good_integration, good_commit, good_transport,
                    predicate=good_predicate):
        raise GateError("valid MOS batch predicate was rejected")
    for token in ("cpx\t#ASM_L65M_OK", "ora\t__rc3",
                  "cmp\t#ASM_L65M_COMMIT_ABI",
                  "ldy\t#ASM_L65M_ABI_VERSION_HIGH_OFFSET",
                  "ldy\t#ASM_L65M_COMMIT_SLOT_BASE",
                  "ldy\t#ASM_L65M_EXPECTED_PHASE_OFFSET",
                  "ldy\t#ASM_L65M_BUSY_OFFSET",
                  "ldy\t#ASM_L65M_REPEAT_PHASE_OFFSET",
                  "sbc\t__rc6"):
        mutation = good_predicate.replace(token, "", 1)
        if not source_audit(good_integration, good_commit, good_transport,
                            predicate=mutation):
            raise GateError(f"MOS predicate mutation survived: {token}")
    print("l65m-commit-ops selftest: PASS "
          "5 trace + 4 source + 3 op-budget + 4 MOS-frame + 9 predicate mutations")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--objdump", type=Path)
    parser.add_argument("--integration", type=Path)
    parser.add_argument("--commit-source", type=Path)
    parser.add_argument("--transport-source", type=Path)
    parser.add_argument("--scratch-source", type=Path)
    parser.add_argument("--symbol-source", type=Path)
    parser.add_argument("--predicate-source", type=Path)
    parser.add_argument("--symbol-manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    required = (
        "image", "elf", "objdump", "integration", "commit_source", "transport_source",
        "scratch_source", "symbol_source", "predicate_source",
        "symbol_manifest", "out",
    )
    missing = [name.replace("_", "-") for name in required if getattr(args, name) is None]
    if missing:
        raise GateError("missing arguments: " + ", ".join(missing))
    image = Image.read(args.image)
    recursion_frames, disassembly_sha256 = read_measured_recursion_frames(
        args.elf, args.objdump)
    costs, _, _ = phase_costs(image)
    baseline = manifest_symbols(args.symbol_manifest)
    source_errors = source_audit(
        args.integration.read_text(encoding="utf-8"),
        args.commit_source.read_text(encoding="utf-8"),
        args.transport_source.read_text(encoding="utf-8"),
        args.scratch_source.read_text(encoding="utf-8"),
        args.symbol_source.read_text(encoding="utf-8"),
        args.predicate_source.read_text(encoding="utf-8"),
    )
    _, commit_interns, _ = phase_costs(image)
    preflight_dma = symbol_dma_projection(
        baseline, preflight_symbol_names(image), False)
    commit_dma = symbol_dma_projection(baseline, commit_interns, True)
    source_errors.extend(check_budgets(
        sum(cost.source_reads for cost in costs),
        preflight_dma["dma_reads"], commit_dma["dma_total"]))
    source_errors.extend(check_recursion_frames(recursion_frames))
    graph_depth = image_graph_depth(image)
    if graph_depth > COMMIT_RECURSION_DEPTH_LIMIT:
        source_errors.append(
            f"artifact-graph-depth={graph_depth} limit={COMMIT_RECURSION_DEPTH_LIMIT}")
    report = make_report(
        args.image, args.elf, image, costs, baseline, recursion_frames,
        disassembly_sha256, source_errors
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="ascii")
    print(
        f"l65m-commit-ops: {'FAIL' if source_errors else 'PASS'} "
        f"steps={sum(expected_steps(image))} app-loads={len(PHASE_NAMES)} "
        f"report={args.out}"
    )
    return 1 if args.check and source_errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, json.JSONDecodeError) as exc:
        print(f"l65m-commit-ops: FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
