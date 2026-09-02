#!/usr/bin/env python3
"""Keep candidate input consumption and prelink pins under one authority.

This is deliberately a read-only post-release gate.  Historical receipts stay
sealed in their own eras; the reusable validators below are the live API for
future cards.  They validate relationships (path plus value, or LOADADDR plus
tuple), never a spelling or a stored address.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/consolidated-consumption-authority.json"
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
EXTENT = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r10-receipt.json"
ENTRY = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-receipt.json"
PINS = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-era-conversion.json")
TUPLE_PREFLIGHT = ARCH / "c2.3-v1.7-block3-r10-map-geometry-preflight-red.json"

# Cards bind every non-build resolver in their active phase graph here before
# invoking the producer.  Compiler, linker and producer are derived from the
# real target automatically; qualifiers and media builders are card-owned
# graph nodes.  Replacement, rather than accumulation, prevents an imported
# predecessor card from donating stale consumers to its successor.
_OUTPUT_ROOT_RESOLVERS: dict[str, Path] = {}


class AuthorityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuthorityError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def _scalar_leaves(value: Any, path: tuple[str, ...] = ()) -> list[
        tuple[tuple[str, ...], Any]]:
    """Enumerate every scalar authority candidate without a hand list."""
    if isinstance(value, dict):
        rows: list[tuple[tuple[str, ...], Any]] = []
        for key, child in sorted(value.items()):
            rows.extend(_scalar_leaves(child, (*path, str(key))))
        return rows
    if isinstance(value, list):
        rows = []
        for index, child in enumerate(value):
            rows.extend(_scalar_leaves(child, (*path, str(index))))
        return rows
    return [(path, value)]


def _replace_path(value: Any, path: tuple[str, ...], replacement: Any) -> None:
    cursor = value
    for key in path[:-1]:
        cursor = cursor[int(key)] if isinstance(cursor, list) else cursor[key]
    leaf = path[-1]
    if isinstance(cursor, list):
        cursor[int(leaf)] = replacement
    else:
        cursor[leaf] = replacement


def _different_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if value is None:
        return "authority-probe"
    text = str(value)
    if re.fullmatch(r"0x[0-9a-fA-F]+", text):
        width = len(text) - 2
        return "0x" + f"{int(text, 16) ^ 1:0{width}x}"
    return text + ".authority-probe"


def _definition_map(rows: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        name, separator, value = row.partition("=")
        require(bool(name) and name not in result,
                f"compiler definition is duplicate or empty: {row}")
        result[name] = value if separator else "<defined>"
    return result


def configure_output_root_resolvers(resolvers: dict[str, Path]) -> None:
    """Bind the active non-build output-root consumer graph.

    Values are the actual artifact paths each stage resolves.  The inventory
    owns semantic stage roles, never one expected directory spelling.
    """
    global _OUTPUT_ROOT_RESOLVERS
    require(bool(resolvers), "active output-root resolver graph is empty")
    normalized = {str(role): Path(path) for role, path in resolvers.items()}
    require(all(role and not path.is_dir() for role, path in normalized.items()),
            "output-root resolver role/path is malformed")
    _OUTPUT_ROOT_RESOLVERS = normalized


def build_output_root_resolver_population(*, target: Path,
        extra_resolvers: dict[str, Path] | None = None) -> dict[str, Any]:
    """Derive every active stage resolving the phase-owned output root."""
    authority_root = target.parent
    resolvers = {
        "compiler": target,
        "linker": target,
        "producer": target,
        **_OUTPUT_ROOT_RESOLVERS,
        **({} if extra_resolvers is None else {
            str(role): Path(path) for role, path in extra_resolvers.items()}),
    }
    require(len(resolvers) >= 4,
            "output-root population omits all non-build consumers")
    entries = []
    for role, path in sorted(resolvers.items()):
        entries.append({"role": role,
            "resolved_path": path.relative_to(ROOT).as_posix(),
            "resolved_root": path.parent.relative_to(ROOT).as_posix()})
    digest = hashlib.sha256((json.dumps(
        entries, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    value = {"authority_root": authority_root.relative_to(ROOT).as_posix(),
        "active_graph_roles": sorted(resolvers), "entries": entries,
        "population": {"count": len(entries), "sha256": digest}}
    validate_output_root_resolver_population(value)
    return value


def validate_output_root_resolver_population(value: dict[str, Any]) -> None:
    entries = value["entries"]
    roles = [row["role"] for row in entries]
    require(roles == sorted(roles) and len(roles) == len(set(roles))
            and roles == value["active_graph_roles"],
            "output-root resolver population differs from active graph")
    require({"compiler", "linker", "producer"} <= set(roles)
            and any(role not in {"compiler", "linker", "producer"}
                    for role in roles),
            "output-root resolver population omits a build or checking stage")
    require(all(row["resolved_root"] == value["authority_root"]
                for row in entries),
            "an active output-root resolver escaped the producer authority")
    digest = hashlib.sha256((json.dumps(
        entries, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    require(value["population"] == {"count": len(entries), "sha256": digest},
            "output-root resolver population receipt drift")


def output_root_resolver_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "qualifier-root-diverges": lambda x: x["entries"][-1].update(
            resolved_root="historical/qualifier-root"),
        "resolver-entry-omitted": lambda x: x["entries"].pop(),
        "active-graph-role-omitted": lambda x: x["active_graph_roles"].pop(),
    }
    rejected = []
    for name, mutation in cases.items():
        trial = copy.deepcopy(value)
        mutation(trial)
        try:
            validate_output_root_resolver_population(trial)
        except (AuthorityError, KeyError, TypeError, ValueError, IndexError):
            rejected.append(name)
    require(rejected == list(cases),
            "output-root resolver population mutation survived")
    return rejected


def derive_manifest_definition_authorities(
        manifest: dict[str, Any],
        renderer: Callable[[dict[str, Any]], list[str]]) -> list[dict[str, Any]]:
    """Discover every manifest scalar consumed as a compiler definition.

    Each scalar leaf is perturbed independently and the actual definition
    renderer is replayed.  The resulting population is therefore a property
    of the living producer, not an enumerated list of known constants.
    """
    baseline = _definition_map(renderer(copy.deepcopy(manifest)))
    authorities: list[dict[str, Any]] = []
    for path, old_value in _scalar_leaves(manifest):
        trial = copy.deepcopy(manifest)
        _replace_path(trial, path, _different_scalar(old_value))
        changed = _definition_map(renderer(trial))
        names = sorted(name for name in set(baseline) | set(changed)
                       if baseline.get(name) != changed.get(name))
        for name in names:
            authorities.append({
                "authority_path": "/".join(path),
                "compiler_definition": name,
                "consumed_value": baseline.get(name),
                "perturbed_value": changed.get(name),
            })
    keys = [(row["authority_path"], row["compiler_definition"])
            for row in authorities]
    require(len(keys) == len(set(keys)),
            "manifest authority discovery produced duplicate relationships")
    return authorities


def validate_authority_input_inventory(value: dict[str, Any]) -> dict[str, Any]:
    """Validate both axes of one real prelink consumption inventory."""
    manifest = value["manifest"]
    require(manifest["binding"]["sha256"] == manifest["consumed_sha256"],
            "bound and consumed manifest identities diverge")
    require(manifest["binding"]["path"] == manifest["consumed_path"],
            "bound and consumed manifest paths diverge")
    constants = manifest["derived_constants"]
    require(bool(constants), "manifest produced no authority-derived constants")
    population = manifest["derived_constant_population"]
    digest = hashlib.sha256((json.dumps(
        constants, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest()
    require(population == {"count": len(constants), "sha256": digest},
            "manifest-derived constant population drifted after discovery")
    pairs = [(row["authority_path"], row["compiler_definition"])
             for row in constants]
    require(len(pairs) == len(set(pairs)),
            "authority-derived constant population is not unique")
    require(all(bool(row.get("seed_source_consumers")) for row in constants),
            "authority-derived constant has no transported/generated source consumer")
    force_includes = value["force_include_authorities"]
    require(all(row["bound_path"] == row["consumed_path"]
                and row["bound_value"] == row["consumed_value"]
                and row["force_include_order"][0] == row["bound_path"]
                and row["proof_stage"] in {
                    "prelink-flags-armed", "postcompile-materialized"}
                for row in force_includes),
            "force-include authority path/value was not consumed")
    output = value["phase_owned_output_root"]
    require(output["target_parent"] == output["consumed_root"],
            "post-link output consumer escaped its phase-owned root")
    resolver_population = output.get("resolver_population")
    if resolver_population is not None:
        validate_output_root_resolver_population(resolver_population)
    geometry = value["linker_geometry"]
    require(geometry["loadaddr_symbolic"] is True
            and geometry["tuple_from_shared_offset"] is True,
            "MAP geometry is not derived from linker LOADADDR authority")
    feature_profile = value.get("feature_profile_population")
    if feature_profile is not None:
        bound = feature_profile["bound_features"]
        consumed = feature_profile["consumed_features"]
        require(feature_profile["status"] ==
                    "passed-bound-feature-profile-consumed"
                and bool(bound) and len(bound) == len(set(bound))
                and consumed == bound
                and feature_profile["bound_feature_count"] == len(bound)
                and feature_profile["consumed_feature_count"] == len(consumed)
                and feature_profile["missing_features"] == []
                and feature_profile["non_unique_features"] == [],
                "feature/profile population was empty, shortened or divergent")
    categories = sorted({"manifest-definition", "phase-owned-output-root",
                         "linker-LOADADDR-geometry",
                         *("force-include-header" for _ in force_includes),
                         *("feature-profile-population"
                           for _ in (() if feature_profile is None else (0,)))})
    require(categories == sorted(value["derived_authority_categories"]),
            "authority-category population was enumerated or omitted")
    return {"constants": len(constants), "force_includes": len(force_includes),
            "features": (0 if feature_profile is None
                         else len(feature_profile["bound_features"])),
            "categories": categories}


def authority_input_mutations(value: dict[str, Any]) -> list[str]:
    """Keep missing/default/stale authority directions permanently red."""
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "bound-manifest-content-diverges": lambda x: x["manifest"].update(
            consumed_sha256="0" * 64),
        "bound-manifest-path-diverges": lambda x: x["manifest"].update(
            consumed_path="historical/substitution-artifacts.json"),
        "derived-constant-omitted": lambda x: x["manifest"]
            ["derived_constants"].pop(),
        "derived-constant-consumer-omitted": lambda x: x["manifest"]
            ["derived_constants"][0].update(seed_source_consumers=[]),
        "force-include-value-diverges": lambda x: x
            ["force_include_authorities"][0].update(consumed_value=-1),
        "output-root-diverges": lambda x: x["phase_owned_output_root"].update(
            consumed_root="historical/output-root"),
        "LOADADDR-authority-lost": lambda x: x["linker_geometry"].update(
            loadaddr_symbolic=False),
        "authority-category-omitted": lambda x: x
            ["derived_authority_categories"].pop(),
    }
    if value.get("feature_profile_population") is not None:
        cases.update({
            "feature-profile-empty": lambda x: x
                ["feature_profile_population"].update(
                    consumed_features=[], consumed_feature_count=0),
            "feature-profile-shortened": lambda x: x
                ["feature_profile_population"]["consumed_features"].pop(),
            "feature-profile-category-omitted": lambda x: x
                ["derived_authority_categories"].remove(
                    "feature-profile-population"),
        })
    if value["phase_owned_output_root"].get("resolver_population") is not None:
        cases.update({
            "qualifier-output-root-diverges": lambda x: x
                ["phase_owned_output_root"]["resolver_population"]["entries"]
                [-1].update(resolved_root="historical/qualifier-root"),
            "output-root-resolver-omitted": lambda x: x
                ["phase_owned_output_root"]["resolver_population"]["entries"]
                .pop(),
        })
    rejected: list[str] = []
    for name, mutation in cases.items():
        trial = copy.deepcopy(value)
        mutation(trial)
        try:
            validate_authority_input_inventory(trial)
        except (AuthorityError, KeyError, TypeError, ValueError, IndexError):
            rejected.append(name)
    require(rejected == list(cases),
            "authority-input inventory mutation survived")
    return rejected


def build_authority_input_inventory(*, target: Path, manifest_path: Path,
        artifacts: dict[str, Any], renderer: Callable[[dict[str, Any]], list[str]],
        static_report: dict[str, Any] | None,
        stdlib_report: dict[str, Any] | None,
        linker_script: Path, compiler_sources: list[str] | None = None,
        feature_report: dict[str, Any] | None = None
        ) -> dict[str, Any]:
    """Materialize the two-axis inventory consumed by one real link."""
    require(manifest_path.is_file() and not manifest_path.is_symlink(),
            "candidate manifest authority is absent")
    raw = manifest_path.read_bytes()
    require(json.loads(raw) == artifacts,
            "caller artifacts differ from the explicitly bound authority")
    constants = derive_manifest_definition_authorities(artifacts, renderer)
    require(compiler_sources is not None and bool(compiler_sources),
            "seed compiler-source population was not materialized")
    source_paths = [Path(path) for path in compiler_sources]
    for path in source_paths:
        require(path.is_file() and not path.is_symlink(),
                f"seed compiler source absent: {path}")
    def source_closure(path: Path, visited: set[Path]) -> list[Path]:
        resolved = path.resolve()
        if resolved in visited:
            return []
        visited.add(resolved)
        text = path.read_text(encoding="utf-8")
        result = [path]
        for include in re.findall(r'^\s*#\s*include\s+"([^"]+)"',
                                  text, re.MULTILINE):
            candidates = (path.parent / include, ROOT / "src" / include,
                          ROOT / "scripts" / include)
            child = next((item for item in candidates if item.is_file()), None)
            if child is not None:
                result.extend(source_closure(child, visited))
        return result

    closures = {path: source_closure(path, set()) for path in source_paths}
    for row in constants:
        macro = str(row["compiler_definition"])
        consumers: list[dict[str, str]] = []
        for translation_unit, closure in closures.items():
            for path in closure:
                if macro in path.read_text(encoding="utf-8"):
                    consumers.append({
                        "translation_unit": translation_unit.relative_to(
                            ROOT).as_posix(),
                        "source": path.relative_to(ROOT).as_posix(),
                    })
        row["seed_source_consumers"] = sorted(
            consumers, key=lambda item: (item["translation_unit"], item["source"]))
    force_includes: list[dict[str, Any]] = []
    for report in (static_report, stdlib_report):
        if report is None:
            continue
        bound = report["bound_header"]
        materialized = report.get("materialized_header", bound)
        materialized_value = report.get(
            "materialized_value", report["consumed_value"])
        force_includes.append({
            "bound_path": bound["path"],
            "consumed_path": materialized["path"],
            "bound_value": report["consumed_value"],
            "consumed_value": materialized_value,
            "force_include_order": list(report["force_include_order"]),
            "proof_stage": ("postcompile-materialized"
                            if "materialized_header" in report
                            else "prelink-flags-armed"),
        })
    require(force_includes,
            "real link has no materialized force-include authorities")
    text = linker_script.read_text(encoding="utf-8")
    geometry = {
        "linker_script": linker_script.relative_to(ROOT).as_posix(),
        "loadaddr_symbolic": (
            "LOADADDR(.lisp65_c2_mapped_far_service)" in text),
        "tuple_from_shared_offset": (
            "__lisp65_c2_mapped_far_maplo_a" in text
            and "__lisp65_c2_mapped_shared_offset" in text),
    }
    categories = {"manifest-definition", "phase-owned-output-root",
                  "linker-LOADADDR-geometry"}
    if force_includes:
        categories.add("force-include-header")
    if feature_report is not None:
        categories.add("feature-profile-population")
    value = {
        "format": "lisp65-prelink-authority-input-inventory-v1",
        "status": "PASS: BOTH CONSUMER AND AUTHORITY POPULATIONS DERIVED",
        "target": target.relative_to(ROOT).as_posix(),
        "manifest": {
            "binding": {"path": manifest_path.relative_to(ROOT).as_posix(),
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()},
            "consumed_path": manifest_path.relative_to(ROOT).as_posix(),
            "consumed_sha256": hashlib.sha256(raw).hexdigest(),
            "derived_constants": constants,
            "derived_constant_population": {
                "count": len(constants),
                "sha256": hashlib.sha256((json.dumps(
                    constants, sort_keys=True, separators=(",", ":")) + "\n"
                    ).encode()).hexdigest()},
        },
        "force_include_authorities": force_includes,
        "phase_owned_output_root": {
            "target_parent": target.parent.relative_to(ROOT).as_posix(),
            "consumed_root": target.parent.relative_to(ROOT).as_posix(),
            "resolver_population": build_output_root_resolver_population(
                target=target)},
        "linker_geometry": geometry,
        **({"feature_profile_population": copy.deepcopy(feature_report)}
           if feature_report is not None else {}),
        "derived_authority_categories": sorted(categories),
    }
    validate_authority_input_inventory(value)
    value["mutations_rejected"] = authority_input_mutations(value)
    return value


def header_population(rows: dict[str, Any]) -> dict[str, int]:
    """Prove every real compiler consumes the bound path *and* its value."""
    require(bool(rows), "compiler population is empty")
    observed: dict[str, int] = {}
    for consumer, wrapper in sorted(rows.items()):
        row = wrapper["result"]
        bound = row["bound_header"]
        materialized = row["materialized_header"]
        flags = row["actual_force_include_flags"]
        require(bound == materialized, f"bound/materialized path drift: {consumer}")
        require(row["consumed_value"] == row["materialized_value"],
                f"bound/materialized value drift: {consumer}")
        require(len(flags) >= 2 and flags[:2] == ["-include", bound["path"]],
                f"real force-include flags omit bound path: {consumer}")
        require(row.get("historical_same_basename_accepted") is False,
                f"historical same-basename input accepted: {consumer}")
        pair = (bound["path"], int(row["consumed_value"]))
        if observed:
            require(pair in {(path, value) for path, value in observed.items()},
                    "seed/final header worlds diverge")
        observed[pair[0]] = pair[1]
    require(len(observed) == 1, "one header case produced multiple authorities")
    return observed


def validate_derived_header_consumers(
        outputs: set[str], receipts: dict[str, dict[str, Any]],
        expected_path: str, expected_value: int) -> dict[str, Any]:
    """Validate the consumer population derived from linked graph outputs.

    Callers supply product nodes discovered from the build graph, never a
    hand-maintained consumer list.  Every linked ``*.prg.elf`` node therefore
    owes exactly one adjacent consumption receipt.  Adding a new product node
    without a receipt, or with a stale path/value pair, is immediately red.
    """
    require(bool(outputs), "build graph has no linked product consumers")
    require(set(receipts) == outputs,
            "build-graph product/consumption population diverged")
    wrapped = {target: {"result": receipts[target]}
               for target in sorted(outputs)}
    observed = header_population(wrapped)
    require(observed == {expected_path: expected_value},
            "build-graph consumer escaped candidate path/value authority")
    return {
        "derivation": "every *.prg.elf product node under the active graph roots",
        "consumers": sorted(outputs),
        "candidate_header": expected_path,
        "candidate_value": expected_value,
    }


def derive_header_consumers(
        roots: list[Path], expected_path: str, expected_value: int,
        *, receipt_suffix: str = ".compiler-input-consumption.json") -> dict[str, Any]:
    """Discover real compiler consumers from materialized build-graph roots."""
    outputs: set[str] = set()
    receipts: dict[str, dict[str, Any]] = {}
    for root in roots:
        require(root.is_dir() and not root.is_symlink(),
                f"build-graph root absent: {root}")
        for elf in sorted(root.rglob("*.prg.elf")):
            target = Path(str(elf)[:-4])
            key = target.relative_to(ROOT).as_posix()
            require(key not in outputs, f"duplicate build-graph product: {key}")
            outputs.add(key)
            receipt = Path(str(target) + receipt_suffix)
            require(receipt.is_file() and not receipt.is_symlink(),
                    f"linked product lacks consumption receipt: {key}")
            row = load(receipt)
            require(row.get("target") == key,
                    f"consumption receipt target drift: {key}")
            receipts[key] = row
    return validate_derived_header_consumers(
        outputs, receipts, expected_path, expected_value)


def derived_population_mutations() -> list[str]:
    path = "candidate/c2_lite_static_plane.h"
    target = "build/card/resident-island-seed.prg"
    base = {
        "actual_force_include_flags": ["-include", path],
        "bound_header": {"path": path},
        "materialized_header": {"path": path},
        "consumed_value": 47469,
        "materialized_value": 47469,
        "historical_same_basename_accepted": False,
    }
    cases: dict[str, tuple[set[str], dict[str, dict[str, Any]]]] = {
        "new-product-without-consumption-receipt": (
            {target, "build/card/new-consumer.prg"}, {target: copy.deepcopy(base)}),
        "new-product-with-stale-header": (
            {target, "build/card/new-consumer.prg"}, {
                target: copy.deepcopy(base),
                "build/card/new-consumer.prg": {
                    **copy.deepcopy(base), "consumed_value": 46043,
                    "materialized_value": 46043,
                },
            }),
        "candidate-path-with-stale-value": (
            {target}, {target: {
                **copy.deepcopy(base), "consumed_value": 46043,
                "materialized_value": 46043,
            }}),
    }
    rejected: list[str] = []
    for name, (outputs, receipts) in cases.items():
        try:
            validate_derived_header_consumers(outputs, receipts, path, 47469)
        except (AuthorityError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases),
            "build-graph consumer-population mutation survived")
    return rejected


def tuple_population(row: dict[str, Any]) -> dict[str, Any]:
    """Prove the emitted MAP tuple consumes the final LOADADDR relation."""
    tenants = row["tenants"]
    require(len(tenants) >= 1, "MAP tenant population is empty")
    offsets = {int(item["LMA"]) - int(item["VMA"]) for item in tenants}
    require(offsets == {int(row["shared_offset"])},
            "MAP tenant LOADADDR relation diverges")
    decoded = int(str(row["decode"]["physical_offset"]), 16)
    require(decoded == int(row["shared_offset"]),
            "emitted tuple does not decode to LOADADDR offset")
    require(decoded % 0x100 == 0, "MAP offset is not page-congruent")
    require(row.get("old_fixed_tuple_authority_active") is False,
            "fixed predecessor tuple authority returned")
    return {"shared_offset": decoded,
            "tenants": [item["section"] for item in tenants]}


def validate_prelink_authority(value: dict[str, Any]) -> dict[str, Any]:
    pins = value["literal_pin_entries"]
    closures = value["inherited_candidate_dependent_closures"]
    pin_names = [item["name"] for item in pins]
    closure_names = [item["name"] for item in closures]
    require(len(pin_names) == len(set(pin_names)) == 7,
            "literal-pin authority must contain seven unique names")
    require(len(closure_names) == len(set(closure_names)) == 6,
            "closure authority must contain six unique names")
    require(all(item.get("proof") not in (False, None, "") for item in pins),
            "literal pin lacks its proof")
    require(all(item.get("world_policy") in {
        "live-successor comparison",
        "sealed-anchor to live-successor comparison",
        "era-separated sealed and live proofs",
    } for item in closures), "closure lacks an explicit era policy")
    require(sum(item["world_policy"] ==
                "era-separated sealed and live proofs" for item in closures) == 1,
            "header closure must be the single era-separated member")
    return {"literal_pins": sorted(pin_names),
            "inherited_closures": sorted(closure_names), "total": 13}


def rejected_mutations(extent: dict[str, Any], entry: dict[str, Any],
                       tuple_row: dict[str, Any], pins: dict[str, Any]) -> list[str]:
    cases: list[tuple[str, str, Any]] = []
    for label, rows in (("extent", extent), ("entry", entry)):
        trial = copy.deepcopy(rows)
        trial["seed"]["result"]["actual_force_include_flags"][1] = "wrong.h"
        cases.append((f"{label}-bound-path-not-consumed", "header", trial))
        trial = copy.deepcopy(rows)
        trial["final"]["result"]["materialized_value"] += 1
        cases.append((f"{label}-path-value-divergence", "header", trial))
    trial_tuple = copy.deepcopy(tuple_row)
    trial_tuple["tenants"][0]["LMA"] += 0x100
    cases.append(("move-LMA-without-tuple-follow", "tuple", trial_tuple))
    trial_tuple = copy.deepcopy(tuple_row)
    trial_tuple["decode"]["physical_offset"] = "0x28100"
    cases.append(("mutate-tuple-without-LMA-reason", "tuple", trial_tuple))
    trial_pins = copy.deepcopy(pins)
    trial_pins["literal_pin_entries"].pop()
    cases.append(("literal-pin-omitted", "pins", trial_pins))
    trial_pins = copy.deepcopy(pins)
    trial_pins["inherited_candidate_dependent_closures"][0]["world_policy"] = (
        "unclassified")
    cases.append(("closure-era-policy-lost", "pins", trial_pins))

    rejected: list[str] = []
    for name, kind, value in cases:
        try:
            if kind == "header":
                header_population(value)
            elif kind == "tuple":
                tuple_population(value)
            else:
                validate_prelink_authority(value)
        except (AuthorityError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == [name for name, _kind, _value in cases],
            "consolidated authority mutation survived")
    return rejected


def evaluate(root: Path = ROOT) -> dict[str, Any]:
    config = load(root / CONFIG.relative_to(ROOT))
    extent_receipt = load(root / EXTENT.relative_to(ROOT))
    entry_receipt = load(root / ENTRY.relative_to(ROOT))
    pin_receipt = load(root / PINS.relative_to(ROOT))
    tuple_preflight = load(root / TUPLE_PREFLIGHT.relative_to(ROOT))
    extent = extent_receipt["compiler_consumption"]
    entry = (entry_receipt["final_product"]["v1_9_Block_B_light"]
             ["native_prompt_final_ELF"]["stdlib_header_consumers"])
    tuple_row = extent_receipt["tuple_LOADADDR"]
    pin_world = pin_receipt["prelink_inventory"]

    cases = {
        "static-plane-extent": header_population(extent),
        "output-root-MAP-tuple": tuple_population(tuple_row),
        "bytecode-entry": header_population(entry),
    }
    require(config["format"] == "lisp65-consolidated-consumption-authority-v5"
            and "perturb every scalar leaf" in
                config["authority_population_derivation"]
            and "feature/profile population" in
                config["authority_population_derivation"]
            and "absence of an explicit authority fails closed" in
                config["rule"]
            and "qualifier" in config["output_root_population_derivation"]
            and "media-builder" in
                config["output_root_population_derivation"],
            "derived authority-population policy drift")
    authority = validate_prelink_authority(pin_world)
    mutations = rejected_mutations(extent, entry, tuple_row, pin_world)
    population_mutations = derived_population_mutations()
    configure_output_root_resolvers({
        "scope-qualifier": ROOT / "build/card/product.prg.elf",
        "media-builder": ROOT / "build/card/product.prg",
    })
    output_population = build_output_root_resolver_population(
        target=ROOT / "build/card/product.prg")
    output_mutations = output_root_resolver_mutations(output_population)
    predecessor = {
        "phase02b": sorted(extent_receipt.get("adapter_mutations", [])),
        "MAP_tuple": sorted(tuple_preflight["tuple_LOADADDR_gate_prototype"]
                            ["mutations"]),
        "bytecode_entry": sorted(entry_receipt["final_product"]
            ["v1_9_Block_B_light"]["native_prompt_final_ELF"]
            ["force_include_bound_equals_consumed"]["mutations_rejected"]),
        "prelink": sorted(pin_receipt["prelink_inventory"]
                          ["mutations_rejected"]),
    }
    require(predecessor["phase02b"] == [
        "path-value-diverge", "reintroduce-stored-46043"]
            and len(predecessor["MAP_tuple"]) == 3
            and len(predecessor["bytecode_entry"]) == 3
            and len(predecessor["prelink"]) == 2,
            "predecessor mutation population drift")
    return {
        "status": "PASS: CONSOLIDATED CONSUMPTION AND PRELINK AUTHORITIES",
        "consumption_cases": cases,
        "prelink_authority": authority,
        "predecessor_mutation_sets": predecessor,
        "consolidated_mutations_rejected": mutations,
        "consumer_population": {
            "derivation": config["consumer_population_derivation"],
            "mutations_rejected": population_mutations,
        },
        "authority_population": {
            "derivation": config["authority_population_derivation"],
            "silent_defaults": "forbidden-fail-closed",
        },
        "output_root_population": {
            "derivation": config["output_root_population_derivation"],
            "population": output_population,
            "mutations_rejected": output_mutations,
        },
        "product_bytes_changed": 0,
    }


def selftest() -> None:
    value = evaluate()
    require(value["prelink_authority"]["total"] == 13
            and len(value["consolidated_mutations_rejected"]) == 8
            and len(value["consumer_population"]["mutations_rejected"]) == 3
            and len(value["output_root_population"]["mutations_rejected"]) == 3,
            "consolidated authority selftest drift")
    print("consolidated authority selftest: PASS cases=3 pins=13 "
          "mutations=14 population=derived build-and-checking")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
    else:
        value = evaluate()
        print("consolidated authority: PASS "
              f"cases={len(value['consumption_cases'])} "
              f"pins={value['prelink_authority']['total']} product-bytes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
