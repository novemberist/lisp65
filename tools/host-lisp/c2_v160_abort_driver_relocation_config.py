#!/usr/bin/env python3
"""Configure the R1 abort-driver far-service successor additively."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import c2_source_owner_identity as OWNER_IDENTITY


ROOT = Path(__file__).resolve().parents[2]
FEATURE = "LISP65_C2_ABORT_DRIVER_FAR"
OLD_FACADE = ROOT / "src/optional/c2_mapped_far_service_v2.s"
NEW_FACADE = ROOT / "src/optional/c2_mapped_far_service_abort_v3.s"
OLD_PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding.s"
NEW_PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding_abort_v2.s"
SCOPE = "mapped-far-content-convergence"
RESERVE_PIN = (
    'SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) == 2,\n'
    '       "Comfort input capture final C2 reserve is not two bytes");')
RESERVE_DERIVATION = (
    'SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) >= 54,\n'
    '       "Derived post-capture C2 reserve is below the 54-byte floor");')


class ConfigurationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConfigurationError(message)


def configure(product: Any) -> dict[str, Any]:
    definitions = tuple(product.CONVERGENCE_DEFINES)
    sources = tuple(product.CONVERGENCE_SOURCES)
    require(FEATURE not in definitions, "abort relocation configured twice")
    require(sources.count(OLD_FACADE) == 1
            and sources.count(OLD_PADDING) == 1
            and NEW_FACADE not in sources and NEW_PADDING not in sources,
            "abort relocation predecessor owners drift")
    replaced = tuple(
        NEW_FACADE if path == OLD_FACADE else
        NEW_PADDING if path == OLD_PADDING else path
        for path in sources)
    successor_definitions = (*definitions, FEATURE)
    scoped_successor_definitions = OWNER_IDENTITY.definitions(
        product, SCOPE, definitions, (FEATURE,))
    scopes: list[dict[str, Any]] = []
    count = 0
    for row in product.SOURCE_OWNER_SCOPES:
        if row.get("name") == SCOPE:
            scopes.append({**row, "defines": scoped_successor_definitions,
                           "sources": replaced})
            count += 1
        else:
            scopes.append(row)
    require(count == 1, "mapped-far source-owner scope is not unique")
    product.CONVERGENCE_DEFINES = successor_definitions
    product.CONVERGENCE_SOURCES = replaced
    product.SOURCE_OWNER_SCOPES = tuple(scopes)

    original_linker = product.linker_script
    require(not getattr(original_linker, "_r1_abort_successor", False),
            "abort linker successor configured twice")

    def linker_script(*args: Any, **kwargs: Any) -> str:
        text = original_linker(*args, **kwargs)
        old = "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 19"
        require(text.count(old) == 1,
                "predecessor facade-padding linker assertion drift")
        require(RESERVE_DERIVATION not in text,
                "capture-reserve derivation configured before R1")
        if text.count(RESERVE_PIN) == 1:
            text = text.replace(RESERVE_PIN, RESERVE_DERIVATION, 1)
        else:
            require(RESERVE_PIN not in text,
                    "predecessor capture-reserve pin multiplicity drift")
        return text.replace(old,
            "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 10",
            1)

    linker_script._r1_abort_successor = True  # type: ignore[attr-defined]
    linker_script._r1_abort_original = original_linker  # type: ignore[attr-defined]
    product.linker_script = linker_script
    selected = product.source_list(successor_definitions)
    require(str(NEW_FACADE) in selected and str(NEW_PADDING) in selected
            and str(OLD_FACADE) not in selected
            and str(OLD_PADDING) not in selected,
            "real producer did not consume the R1 source successors")
    return {
        "feature": FEATURE,
        "scope": SCOPE,
        "definitions": list(successor_definitions),
        "scoped_definitions": list(scoped_successor_definitions),
        "sources": [path.relative_to(ROOT).as_posix() for path in replaced],
        "predecessors_absent": True,
        "linker_padding_contract_bytes": 10,
        "live_reserve_checker": "derived-post-capture-free>=54",
        "historical_two_byte_pin_consumed": False,
    }


def restore_predecessor(product: Any) -> None:
    """Restore the exact predecessor before its historical configurator reruns.

    The inherited producer deliberately rebuilds its projection more than once
    in a fresh process.  R1 is the final additive layer each time; it must not
    leave a half-successor (new feature with old sources) for that producer.
    """
    definitions = tuple(product.CONVERGENCE_DEFINES)
    sources = tuple(product.CONVERGENCE_SOURCES)
    if FEATURE not in definitions:
        require(NEW_FACADE not in sources and NEW_PADDING not in sources,
                "R1 successor sources exist without their feature")
        return
    require(sources.count(NEW_FACADE) == 1
            and sources.count(NEW_PADDING) == 1
            and OLD_FACADE not in sources and OLD_PADDING not in sources,
            "R1 successor identity is incomplete before restore")
    predecessor_definitions = tuple(x for x in definitions if x != FEATURE)
    scoped_predecessor_definitions = OWNER_IDENTITY.definitions(
        product, SCOPE, predecessor_definitions)
    predecessor_sources = tuple(
        OLD_FACADE if path == NEW_FACADE else
        OLD_PADDING if path == NEW_PADDING else path for path in sources)
    scopes: list[dict[str, Any]] = []
    count = 0
    for row in product.SOURCE_OWNER_SCOPES:
        if row.get("name") == SCOPE:
            scopes.append({**row, "defines": scoped_predecessor_definitions,
                           "sources": predecessor_sources})
            count += 1
        else:
            scopes.append(row)
    require(count == 1, "mapped-far predecessor scope restore drift")
    current_linker = product.linker_script
    require(getattr(current_linker, "_r1_abort_successor", False),
            "R1 linker successor absent during predecessor restore")
    product.CONVERGENCE_DEFINES = predecessor_definitions
    product.CONVERGENCE_SOURCES = predecessor_sources
    product.SOURCE_OWNER_SCOPES = tuple(scopes)
    product.linker_script = current_linker._r1_abort_original


def configured_scope_projection(product: Any) -> dict[str, Any]:
    """Read the source-owner projection from the fully configured product."""
    selected = tuple(str(row["trigger"])
                     for row in product.SOURCE_OWNER_SCOPES)
    dummy = {"product_build_id_hex": "0x00000000",
             "artifacts": {"shelf": {"bytes": 0}}}
    return product.source_owner_scope_gate(
        product.definitions(dummy), selected, product.source_list(selected))


def validate_scope_projection(projection: dict[str, Any],
                              component: dict[str, Any]) -> None:
    rows = [row for row in projection.get("scopes", [])
            if row.get("name") == SCOPE]
    require(len(rows) == 1 and rows[0]["selected"] is True
            and rows[0]["defines"] == sorted(component["scoped_definitions"])
            and rows[0]["sources"] == sorted(component["sources"]),
            "post-configuration scope projection is incomplete")


def install_root_hook(root_module: Any, product: Any) -> None:
    """Make R1 the final layer of every real root-source projection."""
    current = root_module.configure_root_source
    if getattr(current, "_r1_abort_root_hook", False):
        raise ConfigurationError("R1 root hook configured twice")

    def configure_root_source() -> dict[str, Any]:
        restore_predecessor(product)
        projection = current()
        component = configure(product)
        live_projection = configured_scope_projection(product)
        validate_scope_projection(live_projection, component)
        components = dict(projection.get("components", {}))
        components["abort_driver_relocation"] = component
        projection["status"] = live_projection["status"]
        projection["scopes"] = live_projection["scopes"]
        projection["components"] = components
        return projection

    configure_root_source._r1_abort_root_hook = True  # type: ignore[attr-defined]
    root_module.configure_root_source = configure_root_source


def project_contracts(ownership: dict[str, Any],
                      full_map: dict[str, Any]) -> tuple[dict[str, Any],
                                                        dict[str, Any]]:
    """Project the emitted R1 price into the two real linker authorities."""
    service = ownership["mapped_far_service"]
    bank = service["bank2"]
    mapping = service["map_tuple"]
    resident = service["resident"]
    require(bank["service_bytes"] == 1248
            and mapping["mapped_service_cpu_end_exclusive"] == "0x7d92"
            and resident["total_bytes"] == 98,
            "R1 ownership predecessor geometry drift")
    bank.update({
        "service_bytes": 1382,
        "service_physical_end_exclusive": "0x0002be18",
        "post_service_static_bytes": 48664,
        "post_service_headroom_bytes": 16872,
    })
    mapping["mapped_service_cpu_end_exclusive"] = "0x7e18"
    service["far_symbols"] = [
        {"name": "c2_mapped_far_convergence_assembly_body", "bytes": 1248},
        {"name": "c2_abort_driver", "bytes": 134},
    ]
    resident.update({"entry_wrappers": 3, "map_trampoline_bytes": 61,
                     "headroom_after_bytes": 145})
    service["external_code_dependencies"] = [
        "c2_overlay_call", "c2_overlay_call_range"]

    rows = full_map["fixed_simultaneous_live_ledger"]
    matches = [row for row in rows
               if row.get("owner") == "mapped-bank2-far-service"]
    require(len(matches) == 1 and matches[0]["capacity_bytes"] == 1499,
            "R1 full-map far-service ledger drift")
    matches[0].update({
        "demand_bytes": 1382,
        "service_cpu_end_exclusive": "0x7e18",
        "service_physical_end_exclusive": "0x0002be18",
    })
    inventory = full_map["generated_linker_requirements"][
        "final_section_inventory_additions"]
    service_rows = [row for row in inventory
                    if row.get("name") == ".lisp65_c2_mapped_far_service"]
    require(len(service_rows) == 1 and service_rows[0]["bytes"] == 1248,
            "R1 predecessor final-inventory service row drift")
    service_rows[0].update({
        "bytes": 1382,
        "size_policy": "candidate-derived-section-bytes",
        "capacity_bytes": 1499,
    })
    return ownership, full_map
