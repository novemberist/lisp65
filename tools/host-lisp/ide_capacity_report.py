#!/usr/bin/env python3
"""Model an IDE core/extra split and the capacity reserved for AP6.

The names partition mode measures slices of the current monolithic L65M
manifest.  The manifests mode accepts already-built core and extra artifacts.
Both modes reject an incomplete/overlapping partition and Core -> Extra calls.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "ide-capacity-contract.json"
CONTRACT_FORMAT = "lisp65-ide-capacity-contract-v1"
L65M_HEADER_BYTES = 38
L65M_ENTRY_BYTES = 8
L65M_LITERAL_INDEX_BYTES = 2
L65M_LITERAL_NODE_BYTES = 10
L65M_LITERAL_PATCH_BYTES = 4


class CapacityError(Exception):
    pass


@dataclass(frozen=True)
class Metrics:
    entries: int
    code_bytes: int
    metadata_bytes: int
    image_bytes: int
    symbols: frozenset[str]
    namepool_bytes: int


def align8(value: int) -> int:
    return (value + 7) & ~7


def align2(value: int) -> int:
    return (value + 1) & ~1


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapacityError("cannot read %s: %s" % (path, exc)) from exc
    if not isinstance(value, dict):
        raise CapacityError("%s: top level must be an object" % path)
    return value


def _root_path(value: str, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CapacityError("%s must be a non-empty path" % field)
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _int_field(obj: dict, name: str, *, minimum: int = 0) -> int:
    value = obj.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CapacityError("%s must be an integer >= %d" % (name, minimum))
    return value


def _entries(manifest: dict, label: str) -> list[dict]:
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise CapacityError("%s: missing entries list" % label)
    names = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise CapacityError("%s: malformed entry %d" % (label, index))
        names.append(entry["name"])
    duplicate = sorted(name for name in set(names) if names.count(name) != 1)
    if duplicate:
        raise CapacityError("%s: duplicate entries: %s" % (label, ", ".join(duplicate)))
    return entries


def _manifest_image(manifest: dict, label: str) -> dict:
    image = manifest.get("external_image")
    if not isinstance(image, dict):
        raise CapacityError("%s: missing external_image" % label)
    for field in ("code_bytes", "metadata_bytes", "bytes", "file_header_bytes"):
        _int_field(image, field)
    return image


def _symbols_from_value(value, result: set[str]) -> None:
    if isinstance(value, dict):
        symbol = value.get("symbol")
        if isinstance(symbol, str):
            result.add(symbol)
        for child in value.values():
            _symbols_from_value(child, result)
    elif isinstance(value, list):
        for child in value:
            _symbols_from_value(child, result)


def _entry_symbols(entries: list[dict]) -> frozenset[str]:
    result = {entry["name"] for entry in entries}
    for entry in entries:
        _symbols_from_value(entry.get("literals", []), result)
    return frozenset(result)


def _name_bytes(names: set[str] | frozenset[str]) -> int:
    return sum(len(name.encode("utf-8")) + 1 for name in names)


def _reachable_literal_nodes(manifest: dict, entries: list[dict]) -> tuple[set[int], int]:
    nodes = manifest.get("literal_nodes")
    index = manifest.get("literal_index")
    if not isinstance(nodes, list) or not isinstance(index, list):
        raise CapacityError("manifest needs literal_nodes and literal_index")
    reachable = set()
    index_records = 0

    def visit(node_index: int) -> None:
        nonlocal index_records
        if node_index in reachable:
            return
        if node_index < 0 or node_index >= len(nodes):
            raise CapacityError("literal node index outside manifest: %d" % node_index)
        node = nodes[node_index]
        reachable.add(node_index)
        first = int(node.get("first", 0))
        count = int(node.get("count", 0))
        if first < 0 or count < 0 or first + count > len(index):
            raise CapacityError("literal child index range outside manifest")
        index_records += count
        for child in index[first : first + count]:
            visit(int(child))

    for entry in entries:
        first = int(entry.get("lit_first", 0))
        count = int(entry.get("lit_count", 0))
        if first < 0 or count < 0 or first + count > len(index):
            raise CapacityError("%s: literal root range outside manifest" % entry["name"])
        index_records += count
        for root in index[first : first + count]:
            visit(int(root))
    return reachable, index_records


def _subset_metrics(manifest: dict, selected: set[str], label: str) -> Metrics:
    all_entries = _entries(manifest, label)
    selected_entries = [entry for entry in all_entries if entry["name"] in selected]
    if len(selected_entries) != len(selected):
        missing = sorted(selected - {entry["name"] for entry in selected_entries})
        raise CapacityError("%s: selected names missing: %s" % (label, ", ".join(missing)))
    if not selected_entries:
        return Metrics(0, 0, 0, 0, frozenset(), 0)
    image = _manifest_image(manifest, label)
    nodes = manifest["literal_nodes"]
    reachable, index_records = _reachable_literal_nodes(manifest, selected_entries)
    pooled_names = {entry["name"] for entry in selected_entries}
    for node_index in reachable:
        name = nodes[node_index].get("name")
        if isinstance(name, str):
            pooled_names.add(name)
    metadata_bytes = align2(
        L65M_HEADER_BYTES
        + L65M_ENTRY_BYTES * len(selected_entries)
        + L65M_LITERAL_INDEX_BYTES * index_records
        + L65M_LITERAL_NODE_BYTES * len(reachable)
        + L65M_LITERAL_PATCH_BYTES * sum(int(entry.get("lit_count", 0)) for entry in selected_entries)
        + _name_bytes(pooled_names)
    )
    code_bytes = sum(int(entry.get("length", 0)) for entry in selected_entries)
    file_header_bytes = int(image["file_header_bytes"])
    symbols = _entry_symbols(selected_entries)
    return Metrics(
        entries=len(selected_entries),
        code_bytes=code_bytes,
        metadata_bytes=metadata_bytes,
        image_bytes=file_header_bytes + code_bytes + metadata_bytes,
        symbols=symbols,
        namepool_bytes=_name_bytes(symbols),
    )


def _whole_metrics(manifest: dict, label: str) -> Metrics:
    entries = _entries(manifest, label)
    image = _manifest_image(manifest, label)
    symbols = _entry_symbols(entries)
    return Metrics(
        entries=len(entries),
        code_bytes=int(image["code_bytes"]),
        metadata_bytes=int(image["metadata_bytes"]),
        image_bytes=int(image["bytes"]),
        symbols=symbols,
        namepool_bytes=_name_bytes(symbols),
    )


def _validate_metadata_model(manifest: dict, label: str) -> None:
    names = {entry["name"] for entry in _entries(manifest, label)}
    measured = _subset_metrics(manifest, names, label)
    exact = _whole_metrics(manifest, label)
    if (
        measured.code_bytes != exact.code_bytes
        or measured.metadata_bytes != exact.metadata_bytes
        or measured.image_bytes != exact.image_bytes
    ):
        raise CapacityError(
            "%s: L65M size model drift: measured code/meta/image=%d/%d/%d "
            "manifest=%d/%d/%d"
            % (
                label,
                measured.code_bytes,
                measured.metadata_bytes,
                measured.image_bytes,
                exact.code_bytes,
                exact.metadata_bytes,
                exact.image_bytes,
            )
        )


def validate_partition(
    monolith_names: set[str], core_names: set[str], extra_names: set[str]
) -> list[str]:
    failures = []
    overlap = sorted(core_names & extra_names)
    missing = sorted(monolith_names - core_names - extra_names)
    unknown = sorted((core_names | extra_names) - monolith_names)
    if overlap:
        failures.append("partition overlap: %s" % ", ".join(overlap))
    if missing:
        failures.append("partition missing: %s" % ", ".join(missing))
    if unknown:
        failures.append("partition unknown: %s" % ", ".join(unknown))
    return failures


def _names_partition(partition: dict, monolith_names: set[str]) -> tuple[set[str], set[str]]:
    core_value = partition.get("core")
    extra_value = partition.get("extra")
    if not isinstance(core_value, list) or not isinstance(extra_value, list):
        raise CapacityError("names partition needs core and extra arrays")
    if core_value == ["*"]:
        extra_names = set(extra_value)
        core_names = monolith_names - extra_names
    else:
        if "*" in core_value or "*" in extra_value:
            raise CapacityError("wildcard is only valid as the complete core array")
        core_names = set(core_value)
        extra_names = set(extra_value)
    if len(core_names) != len(core_value) and core_value != ["*"]:
        raise CapacityError("core partition contains duplicate names")
    if len(extra_names) != len(extra_value):
        raise CapacityError("extra partition contains duplicate names")
    return core_names, extra_names


def _blob_path(manifest: dict, label: str) -> Path:
    value = manifest.get("blob")
    if not isinstance(value, str) or not value:
        raise CapacityError("%s: missing blob path" % label)
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _dependency_graph(manifest: dict, label: str) -> dict[str, set[str]]:
    entries = _entries(manifest, label)
    blob_path = _blob_path(manifest, label)
    try:
        blob = blob_path.read_bytes()
    except OSError as exc:
        raise CapacityError("cannot read %s blob %s: %s" % (label, blob_path, exc)) from exc
    graph = {entry["name"]: set() for entry in entries}
    for entry in entries:
        _symbols_from_value(entry.get("literals", []), graph[entry["name"]])
        start = int(entry.get("blob_offset", -1))
        length = int(entry.get("length", -1))
        if start < 0 or length < 0 or start + length > len(blob):
            raise CapacityError("%s: %s blob range is invalid" % (label, entry["name"]))
        code = B.decode_code_object(blob[start : start + length])
        literals = entry.get("literals", [])
        pc = 0
        while pc < len(code.payload):
            spec, operand, pc = B.decode_instruction(code.payload, pc)
            if spec.mnemonic not in ("CALL", "TAILCALL"):
                continue
            literal_index, _argc = operand
            if literal_index >= len(literals):
                raise CapacityError("%s: %s call literal is outside entry" % (label, entry["name"]))
            literal = literals[literal_index]
            if isinstance(literal, dict) and isinstance(literal.get("symbol"), str):
                graph[entry["name"]].add(literal["symbol"])
    return graph


def core_to_extra_refs(
    graph: dict[str, set[str]], core_names: set[str], extra_names: set[str]
) -> list[tuple[str, str]]:
    return sorted(
        (caller, target)
        for caller in core_names
        for target in graph.get(caller, set())
        if target in extra_names
    )


def logical_manifest_partition(
    monolith_names: set[str],
    core_names: set[str],
    physical_extra_names: set[str],
    overrides: set[str],
    omitted_private: set[str] | None = None,
) -> tuple[set[str], list[str]]:
    omitted_private = set(omitted_private or ())
    physical_overlap = core_names & physical_extra_names
    if physical_overlap != overrides:
        return set(), [
            "manifest overlap must equal declared overrides: overlap=%s overrides=%s"
            % (", ".join(sorted(physical_overlap)), ", ".join(sorted(overrides)))
        ]
    unknown_omitted = sorted(omitted_private - monolith_names)
    if unknown_omitted:
        return set(), ["omitted private names are not in baseline: %s" % ", ".join(unknown_omitted)]
    extra_names = physical_extra_names - overrides
    return extra_names, validate_partition(
        monolith_names - omitted_private, core_names, extra_names
    )


def _manifest_partition(
    partition: dict, monolith: dict, monolith_names: set[str]
) -> tuple[dict, dict, Metrics, Metrics, set[str], set[str], dict[str, set[str]]]:
    core_path = _root_path(partition.get("core_manifest"), "partition.core_manifest")
    extra_path = _root_path(partition.get("extra_manifest"), "partition.extra_manifest")
    core_manifest = _load_json(core_path)
    extra_manifest = _load_json(extra_path)
    core_names = {entry["name"] for entry in _entries(core_manifest, str(core_path))}
    physical_extra_names = {
        entry["name"] for entry in _entries(extra_manifest, str(extra_path))
    }
    override_value = partition.get("overrides", [])
    if not isinstance(override_value, list) or not all(
        isinstance(name, str) for name in override_value
    ):
        raise CapacityError("partition.overrides must be an array of names")
    overrides = set(override_value)
    if len(overrides) != len(override_value):
        raise CapacityError("partition.overrides contains duplicate names")
    manifest_override_value = extra_manifest.get("resident_overrides", [])
    if not isinstance(manifest_override_value, list) or not all(
        isinstance(name, str) for name in manifest_override_value
    ):
        raise CapacityError("extra manifest resident_overrides must be an array of names")
    manifest_overrides = set(manifest_override_value)
    if len(manifest_overrides) != len(manifest_override_value):
        raise CapacityError("extra manifest resident_overrides contains duplicate names")
    if manifest_overrides != overrides:
        raise CapacityError(
            "extra manifest resident_overrides differ from contract: manifest=%s contract=%s"
            % (", ".join(sorted(manifest_overrides)), ", ".join(sorted(overrides)))
        )
    omitted_value = partition.get("omitted_private", [])
    if not isinstance(omitted_value, list) or not all(
        isinstance(name, str) for name in omitted_value
    ):
        raise CapacityError("partition.omitted_private must be an array of names")
    omitted_private = set(omitted_value)
    if len(omitted_private) != len(omitted_value):
        raise CapacityError("partition.omitted_private contains duplicate names")
    extra_names, failures = logical_manifest_partition(
        monolith_names,
        core_names,
        physical_extra_names,
        overrides,
        omitted_private,
    )
    if failures:
        raise CapacityError("; ".join(failures))
    manifest_private = set(core_manifest.get("private_inline_functions", [])) | set(
        extra_manifest.get("private_inline_functions", [])
    )
    if manifest_private != omitted_private:
        raise CapacityError(
            "private inline manifest union differs from contract: manifest=%s contract=%s"
            % (
                ", ".join(sorted(manifest_private)),
                ", ".join(sorted(omitted_private)),
            )
        )
    graph = _dependency_graph(core_manifest, "core")
    return (
        core_manifest,
        extra_manifest,
        _whole_metrics(core_manifest, "core"),
        _whole_metrics(extra_manifest, "extra"),
        core_names,
        extra_names,
        graph,
    )


def project_capacity(
    resident: Metrics,
    core: Metrics,
    extra: Metrics,
    runtime_model: dict,
    limits: dict,
    reserve: dict,
) -> dict:
    symbol_correction = _int_field(runtime_model, "symbol_correction")
    name_correction = _int_field(runtime_model, "namepool_correction_bytes")
    reserve_entries = _int_field(reserve, "entries")
    reserve_symbols = _int_field(reserve, "symbols")
    reserve_names = _int_field(reserve, "namepool_bytes")
    reserve_code = _int_field(reserve, "code_bytes")
    reserve_image = _int_field(reserve, "image_bytes")
    if reserve_image < reserve_code:
        raise CapacityError("ap6_reserve.image_bytes must be >= code_bytes")

    start = align8(resident.entries)
    core_load = start + core.entries
    core_post_align = align8(core_load)
    all_load = align8(core_load) + extra.entries if extra.entries else core_load
    all_post_align = align8(all_load)
    # AP6 is a separate on-demand M65D artifact loaded after the IDE tier.
    ap6_load = core_post_align + reserve_entries
    ap6_post_align = align8(ap6_load)
    ap6_all_load = all_post_align + reserve_entries
    ap6_all_post_align = align8(ap6_all_load)

    current_symbols = resident.symbols | core.symbols
    all_symbols = current_symbols | extra.symbols
    current_namepool = _name_bytes(current_symbols) + name_correction
    all_namepool = _name_bytes(all_symbols) + name_correction
    current_symbol_count = len(current_symbols) + symbol_correction
    all_symbol_count = len(all_symbols) + symbol_correction
    ap6_symbol_count = current_symbol_count + reserve_symbols
    ap6_namepool = current_namepool + reserve_names
    ap6_all_symbol_count = all_symbol_count + reserve_symbols
    ap6_all_namepool = all_namepool + reserve_names
    reserve_metadata = reserve_image - reserve_code
    core_post = resident.code_bytes + core.code_bytes
    core_peak = core_post + core.metadata_bytes
    ext_post = core_post + reserve_code
    ext_peak = max(core_peak, ext_post + reserve_metadata)
    extra_post = core_post + extra.code_bytes
    extra_peak = extra_post + extra.metadata_bytes
    ext_all_post = extra_post + reserve_code
    ext_all_peak = max(core_peak, extra_peak, ext_all_post + reserve_metadata)
    projected_image = reserve_image

    return {
        "directory": {
            "resident_entries": resident.entries,
            "start_after_align8": start,
            "core_load_used": core_load,
            "core_post_align_used": core_post_align,
            "all_load_used": all_load,
            "all_post_align_used": all_post_align,
            "ap6_core_load_used": ap6_load,
            "ap6_core_post_align_used": ap6_post_align,
            "ap6_all_load_used": ap6_all_load,
            "ap6_all_post_align_used": ap6_all_post_align,
            "ap6_core_headroom": _int_field(limits, "vm_dir_max") - ap6_post_align,
            "ap6_all_headroom": _int_field(limits, "vm_dir_max") - ap6_all_post_align,
        },
        "symbols": {
            "core_runtime_symbols": current_symbol_count,
            "core_runtime_namepool_bytes": current_namepool,
            "ap6_runtime_symbols": ap6_symbol_count,
            "ap6_runtime_namepool_bytes": ap6_namepool,
            "ap6_symbol_headroom": _int_field(limits, "max_symbols") - ap6_symbol_count,
            "ap6_namepool_headroom": _int_field(limits, "namepool_bytes") - ap6_namepool,
            "ap6_all_runtime_symbols": ap6_all_symbol_count,
            "ap6_all_runtime_namepool_bytes": ap6_all_namepool,
            "ap6_all_symbol_headroom": _int_field(limits, "max_symbols")
            - ap6_all_symbol_count,
            "ap6_all_namepool_headroom": _int_field(limits, "namepool_bytes")
            - ap6_all_namepool,
        },
        "ext_code": {
            "ap6_peak_used": ext_peak,
            "ap6_post_used": ext_post,
            "ap6_peak_headroom": _int_field(limits, "ext_code_bytes") - ext_peak,
            "ap6_post_headroom": _int_field(limits, "ext_code_bytes") - ext_post,
            "ap6_all_peak_used": ext_all_peak,
            "ap6_all_post_used": ext_all_post,
            "ap6_all_peak_headroom": _int_field(limits, "ext_code_bytes") - ext_all_peak,
            "ap6_all_post_headroom": _int_field(limits, "ext_code_bytes") - ext_all_post,
        },
        "disk_image": {
            "ap6_core_image_bytes": projected_image,
            "ap6_core_image_headroom": _int_field(limits, "disk_lib_image_bytes") - projected_image,
        },
    }


def _validate_reserve_measurement(
    reserve: dict, monolith_manifest: dict, monolith: Metrics
) -> list[str]:
    basis = reserve.get("basis")
    measurement_value = reserve.get("measurement_manifest")
    if basis == "planning-envelope-v1":
        if measurement_value is not None:
            return ["AP6 planning envelope must not claim a measurement manifest"]
        return []
    if basis != "measured-manifest-v1":
        return ["AP6 reserve basis must be planning-envelope-v1 or measured-manifest-v1"]
    if measurement_value is None:
        return ["AP6 measured reserve needs measurement_manifest"]
    measurement_path = _root_path(measurement_value, "ap6_reserve.measurement_manifest")
    measurement_manifest = _load_json(measurement_path)
    measured = _whole_metrics(measurement_manifest, "AP6 measurement")
    measurement_scope = reserve.get("measurement_scope", "combined")
    if measurement_scope not in ("combined", "component"):
        return ["AP6 measurement_scope must be combined or component"]
    monolith_manifest_value = reserve.get("measurement_base_manifest")
    if monolith_manifest_value is None:
        base_manifest = monolith_manifest
        base = monolith
    else:
        base_path = _root_path(
            monolith_manifest_value, "ap6_reserve.measurement_base_manifest"
        )
        base_manifest = _load_json(base_path)
        base = _whole_metrics(base_manifest, "AP6 measurement base")
    base_entry_names = {
        entry["name"] for entry in _entries(base_manifest, "AP6 measurement base")
    }
    measured_entry_names = {
        entry["name"] for entry in _entries(measurement_manifest, "AP6 measurement")
    }
    if measurement_scope == "component":
        observed = {
            "added_entries": measured.entries,
            "added_symbols": len(measured.symbols - base.symbols),
            "added_namepool_bytes": _name_bytes(measured.symbols - base.symbols),
            "net_code_bytes": measured.code_bytes,
            "net_image_bytes": measured.image_bytes,
        }
    else:
        observed = {
            "added_entries": len(measured_entry_names - base_entry_names),
            "added_symbols": len(measured.symbols - base.symbols),
            "added_namepool_bytes": _name_bytes(measured.symbols - base.symbols),
            "net_code_bytes": measured.code_bytes - base.code_bytes,
            "net_image_bytes": measured.image_bytes - base.image_bytes,
        }
    failures = []
    for name, value in observed.items():
        expected = _int_field(reserve, "measured_%s" % name)
        if value != expected:
            failures.append(
                "AP6 measurement %s drift: %d != %d" % (name, value, expected)
            )
    for budget_name, observed_name in (
        ("entries", "added_entries"),
        ("symbols", "added_symbols"),
        ("namepool_bytes", "added_namepool_bytes"),
        ("code_bytes", "net_code_bytes"),
        ("image_bytes", "net_image_bytes"),
    ):
        budget = _int_field(reserve, budget_name)
        value = observed[observed_name]
        if budget < value:
            failures.append("AP6 reserve %s %d < measured %d" % (budget_name, budget, value))
    return failures


def _metric_dict(metrics: Metrics) -> dict:
    return {
        "entries": metrics.entries,
        "code_bytes": metrics.code_bytes,
        "metadata_bytes": metrics.metadata_bytes,
        "image_bytes": metrics.image_bytes,
        "symbols": len(metrics.symbols),
        "namepool_bytes": metrics.namepool_bytes,
    }


def _gate_failures(result: dict, gates: dict) -> list[str]:
    core = result["metrics"]["core"]
    projection = result["projection"]
    checks = (
        (
            core["entries"] <= _int_field(gates, "core_max_entries_before_ap6"),
            "core entries %d exceed %d"
            % (core["entries"], gates["core_max_entries_before_ap6"]),
        ),
        (
            projection["directory"]["ap6_core_headroom"]
            >= _int_field(gates, "min_directory_headroom_after_ap6"),
            "AP6 directory headroom %d < %d"
            % (
                projection["directory"]["ap6_core_headroom"],
                gates["min_directory_headroom_after_ap6"],
            ),
        ),
        (
            projection["directory"]["ap6_all_headroom"]
            >= _int_field(gates, "min_all_directory_headroom_after_ap6"),
            "AP6 all-tier directory headroom %d < %d"
            % (
                projection["directory"]["ap6_all_headroom"],
                gates["min_all_directory_headroom_after_ap6"],
            ),
        ),
        (
            projection["symbols"]["ap6_symbol_headroom"]
            >= _int_field(gates, "min_symbol_headroom_after_ap6"),
            "AP6 symbol headroom %d < %d"
            % (
                projection["symbols"]["ap6_symbol_headroom"],
                gates["min_symbol_headroom_after_ap6"],
            ),
        ),
        (
            projection["symbols"]["ap6_all_symbol_headroom"]
            >= _int_field(gates, "min_all_symbol_headroom_after_ap6"),
            "AP6 all-tier symbol headroom %d < %d"
            % (
                projection["symbols"]["ap6_all_symbol_headroom"],
                gates["min_all_symbol_headroom_after_ap6"],
            ),
        ),
        (
            projection["symbols"]["ap6_namepool_headroom"]
            >= _int_field(gates, "min_namepool_headroom_after_ap6"),
            "AP6 namepool headroom %d < %d"
            % (
                projection["symbols"]["ap6_namepool_headroom"],
                gates["min_namepool_headroom_after_ap6"],
            ),
        ),
        (
            projection["symbols"]["ap6_all_namepool_headroom"]
            >= _int_field(gates, "min_all_namepool_headroom_after_ap6"),
            "AP6 all-tier namepool headroom %d < %d"
            % (
                projection["symbols"]["ap6_all_namepool_headroom"],
                gates["min_all_namepool_headroom_after_ap6"],
            ),
        ),
        (
            projection["ext_code"]["ap6_peak_headroom"]
            >= _int_field(gates, "min_ext_code_peak_headroom_after_ap6"),
            "AP6 EXT-code peak headroom %d < %d"
            % (
                projection["ext_code"]["ap6_peak_headroom"],
                gates["min_ext_code_peak_headroom_after_ap6"],
            ),
        ),
        (
            projection["ext_code"]["ap6_all_peak_headroom"]
            >= _int_field(gates, "min_all_ext_code_peak_headroom_after_ap6"),
            "AP6 all-tier EXT-code peak headroom %d < %d"
            % (
                projection["ext_code"]["ap6_all_peak_headroom"],
                gates["min_all_ext_code_peak_headroom_after_ap6"],
            ),
        ),
        (
            projection["ext_code"]["ap6_post_headroom"]
            >= _int_field(gates, "min_ext_code_post_headroom_after_ap6"),
            "AP6 EXT-code post headroom %d < %d"
            % (
                projection["ext_code"]["ap6_post_headroom"],
                gates["min_ext_code_post_headroom_after_ap6"],
            ),
        ),
        (
            projection["ext_code"]["ap6_all_post_headroom"]
            >= _int_field(gates, "min_all_ext_code_post_headroom_after_ap6"),
            "AP6 all-tier EXT-code post headroom %d < %d"
            % (
                projection["ext_code"]["ap6_all_post_headroom"],
                gates["min_all_ext_code_post_headroom_after_ap6"],
            ),
        ),
        (
            projection["disk_image"]["ap6_core_image_headroom"]
            >= _int_field(gates, "min_disk_image_headroom_after_ap6"),
            "AP6 disk-image headroom %d < %d"
            % (
                projection["disk_image"]["ap6_core_image_headroom"],
                gates["min_disk_image_headroom_after_ap6"],
            ),
        ),
    )
    return [message for passed, message in checks if not passed]


def evaluate(contract: dict) -> dict:
    if contract.get("format") != CONTRACT_FORMAT:
        raise CapacityError("unsupported contract format: %r" % contract.get("format"))
    inputs = contract.get("inputs")
    partition = contract.get("partition")
    runtime_model = contract.get("runtime_model")
    limits = contract.get("limits")
    reserve = contract.get("ap6_reserve")
    gates = contract.get("gates")
    if not all(isinstance(item, dict) for item in (inputs, partition, runtime_model, limits, reserve, gates)):
        raise CapacityError("contract sections must be objects")

    resident_path = _root_path(inputs.get("resident_manifest"), "inputs.resident_manifest")
    monolith_path = _root_path(inputs.get("monolith_manifest"), "inputs.monolith_manifest")
    resident_manifest = _load_json(resident_path)
    monolith = _load_json(monolith_path)
    _validate_metadata_model(resident_manifest, "resident")
    _validate_metadata_model(monolith, "monolith")
    resident_metrics = _whole_metrics(resident_manifest, "resident")
    monolith_metrics = _whole_metrics(monolith, "monolith")
    monolith_names = {entry["name"] for entry in _entries(monolith, "monolith")}

    failures = []
    failures.extend(
        _validate_reserve_measurement(reserve, monolith, monolith_metrics)
    )
    mode = partition.get("mode")
    if mode == "names":
        core_names, extra_names = _names_partition(partition, monolith_names)
        failures.extend(validate_partition(monolith_names, core_names, extra_names))
        core_metrics = _subset_metrics(monolith, core_names, "monolith")
        extra_metrics = _subset_metrics(monolith, extra_names, "monolith")
        graph = _dependency_graph(monolith, "monolith")
    elif mode == "manifests":
        (
            _core_manifest,
            _extra_manifest,
            core_metrics,
            extra_metrics,
            core_names,
            extra_names,
            graph,
        ) = _manifest_partition(partition, monolith, monolith_names)
    else:
        raise CapacityError("partition.mode must be names or manifests")

    violations = core_to_extra_refs(graph, core_names, extra_names)
    failures.extend("core references extra: %s -> %s" % item for item in violations)

    monolith_symbols = resident_metrics.symbols | monolith_metrics.symbols
    modeled_symbols = len(monolith_symbols) + _int_field(runtime_model, "symbol_correction")
    modeled_names = _name_bytes(monolith_symbols) + _int_field(
        runtime_model, "namepool_correction_bytes"
    )
    expected_symbols = _int_field(runtime_model, "expected_monolith_runtime_symbols")
    expected_names = _int_field(runtime_model, "expected_monolith_runtime_namepool_bytes")
    if modeled_symbols != expected_symbols:
        failures.append(
            "monolith runtime symbol model drift: %d != %d" % (modeled_symbols, expected_symbols)
        )
    if modeled_names != expected_names:
        failures.append(
            "monolith runtime namepool model drift: %d != %d" % (modeled_names, expected_names)
        )

    projection = project_capacity(
        resident_metrics,
        core_metrics,
        extra_metrics,
        runtime_model,
        limits,
        reserve,
    )
    result = {
        "format": "lisp65-ide-capacity-report-v1",
        "ap6_reserve_basis": reserve.get("basis"),
        "partition_mode": mode,
        "metrics": {
            "resident": _metric_dict(resident_metrics),
            "monolith": _metric_dict(monolith_metrics),
            "core": _metric_dict(core_metrics),
            "extra": _metric_dict(extra_metrics),
        },
        "projection": projection,
        "core_to_extra_refs": [
            {"caller": caller, "target": target} for caller, target in violations
        ],
        "overrides": list(partition.get("overrides", [])),
        "failures": failures,
    }
    failures.extend(_gate_failures(result, gates))
    result["status"] = "pass" if not failures else "fail"
    return result


def _print_report(result: dict) -> None:
    print("ide-capacity-report: %s" % result["status"].upper())
    print("ap6_reserve_basis=%s" % result["ap6_reserve_basis"])
    print(
        "partition mode=%s overrides=%d core_to_extra_refs=%d"
        % (
            result["partition_mode"],
            len(result["overrides"]),
            len(result["core_to_extra_refs"]),
        )
    )
    for name in ("resident", "monolith", "core", "extra"):
        metric = result["metrics"][name]
        print(
            "%s entries=%d code=%d metadata=%d image=%d symbols=%d namepool=%d"
            % (
                name,
                metric["entries"],
                metric["code_bytes"],
                metric["metadata_bytes"],
                metric["image_bytes"],
                metric["symbols"],
                metric["namepool_bytes"],
            )
        )
    directory = result["projection"]["directory"]
    symbols = result["projection"]["symbols"]
    ext_code = result["projection"]["ext_code"]
    disk = result["projection"]["disk_image"]
    print(
        "directory core=%d post_align=%d all=%d all_post_align=%d "
        "ap6_core=%d ap6_post_align=%d ap6_headroom=%d "
        "ap6_all=%d ap6_all_post_align=%d ap6_all_headroom=%d"
        % (
            directory["core_load_used"],
            directory["core_post_align_used"],
            directory["all_load_used"],
            directory["all_post_align_used"],
            directory["ap6_core_load_used"],
            directory["ap6_core_post_align_used"],
            directory["ap6_core_headroom"],
            directory["ap6_all_load_used"],
            directory["ap6_all_post_align_used"],
            directory["ap6_all_headroom"],
        )
    )
    print(
        "ap6 symbols=%d headroom=%d namepool=%d headroom=%d"
        % (
            symbols["ap6_runtime_symbols"],
            symbols["ap6_symbol_headroom"],
            symbols["ap6_runtime_namepool_bytes"],
            symbols["ap6_namepool_headroom"],
        )
    )
    print(
        "ap6_all symbols=%d headroom=%d namepool=%d headroom=%d"
        % (
            symbols["ap6_all_runtime_symbols"],
            symbols["ap6_all_symbol_headroom"],
            symbols["ap6_all_runtime_namepool_bytes"],
            symbols["ap6_all_namepool_headroom"],
        )
    )
    print(
        "ap6 ext_peak=%d headroom=%d ext_post=%d headroom=%d image=%d headroom=%d"
        % (
            ext_code["ap6_peak_used"],
            ext_code["ap6_peak_headroom"],
            ext_code["ap6_post_used"],
            ext_code["ap6_post_headroom"],
            disk["ap6_core_image_bytes"],
            disk["ap6_core_image_headroom"],
        )
    )
    for failure in result["failures"]:
        print("FAIL: %s" % failure)


def selftest() -> int:
    cases = 0
    assert [align8(value) for value in (0, 1, 7, 8, 9, 319, 539)] == [
        0,
        8,
        8,
        8,
        16,
        320,
        544,
    ]
    assert [align2(value) for value in (0, 1, 2, 3, 38)] == [0, 2, 2, 4, 38]
    cases += 1

    assert validate_partition({"a", "b"}, {"a"}, {"b"}) == []
    cases += 1
    assert validate_partition({"a", "b"}, {"a"}, {"a", "b"}) == [
        "partition overlap: a"
    ]
    cases += 1
    assert validate_partition({"a", "b"}, {"a"}, set()) == ["partition missing: b"]
    cases += 1
    assert validate_partition({"a"}, {"a", "x"}, set()) == ["partition unknown: x"]
    cases += 1

    graph = {"a": {"b", "native"}, "b": set(), "c": {"a"}}
    assert core_to_extra_refs(graph, {"a", "c"}, {"b"}) == [("a", "b")]
    assert core_to_extra_refs(graph, {"a", "b", "c"}, set()) == []
    cases += 1

    logical_extra, failures = logical_manifest_partition(
        {"a", "b", "hook"}, {"a", "hook"}, {"b", "hook"}, {"hook"}
    )
    assert logical_extra == {"b"}
    assert failures == []
    _, failures = logical_manifest_partition(
        {"a", "b", "hook"}, {"a", "hook"}, {"b", "hook"}, set()
    )
    assert failures == [
        "manifest overlap must equal declared overrides: overlap=hook overrides="
    ]
    cases += 1

    logical_extra, failures = logical_manifest_partition(
        {"a", "b", "private"}, {"a"}, {"b"}, set(), {"private"}
    )
    assert logical_extra == {"b"}
    assert failures == []
    cases += 1

    assert _validate_reserve_measurement(
        {"basis": "planning-envelope-v1"}, {}, Metrics(0, 0, 0, 0, frozenset(), 0)
    ) == []
    assert _validate_reserve_measurement(
        {"basis": "measured-manifest-v1"}, {}, Metrics(0, 0, 0, 0, frozenset(), 0)
    ) == ["AP6 measured reserve needs measurement_manifest"]
    cases += 1

    resident = Metrics(319, 1000, 200, 1200, frozenset({"r"}), 2)
    core = Metrics(120, 2000, 500, 2504, frozenset({"r", "c"}), 4)
    extra = Metrics(50, 1000, 300, 1304, frozenset({"e"}), 2)
    projection = project_capacity(
        resident,
        core,
        extra,
        {"symbol_correction": 2, "namepool_correction_bytes": 3},
        {
            "vm_dir_max": 552,
            "max_symbols": 20,
            "namepool_bytes": 100,
            "ext_code_bytes": 10000,
            "disk_lib_image_bytes": 10000,
        },
        {"entries": 40, "symbols": 4, "namepool_bytes": 20, "code_bytes": 500, "image_bytes": 900},
    )
    assert projection["directory"] == {
        "resident_entries": 319,
        "start_after_align8": 320,
        "core_load_used": 440,
        "core_post_align_used": 440,
        "all_load_used": 490,
        "all_post_align_used": 496,
        "ap6_core_load_used": 480,
        "ap6_core_post_align_used": 480,
        "ap6_all_load_used": 536,
        "ap6_all_post_align_used": 536,
        "ap6_core_headroom": 72,
        "ap6_all_headroom": 16,
    }
    assert projection["symbols"]["ap6_runtime_symbols"] == 8
    assert projection["symbols"]["ap6_runtime_namepool_bytes"] == 27
    assert projection["ext_code"]["ap6_peak_used"] == 3900
    assert projection["ext_code"]["ap6_all_peak_used"] == 4900
    assert projection["disk_image"]["ap6_core_image_bytes"] == 900
    cases += 1

    print("ide-capacity-report selftest: PASS cases=%d" % cases)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--report-only", action="store_true", help="return success even when gates fail")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        result = evaluate(_load_json(args.contract))
    except (CapacityError, B.DecodeError) as exc:
        print("ide-capacity-report: ERROR %s" % exc, file=sys.stderr)
        return 2
    _print_report(result)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["status"] == "pass" or args.report_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
