#!/usr/bin/env python3
"""Configure the retirement-only continuation-liveness successor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import c2_source_owner_identity as OWNER_IDENTITY


ROOT = Path(__file__).resolve().parents[2]
FEATURE = "LISP65_C2_RTOV_CONTINUATION_LIVENESS"
SCOPE = "mapped-far-content-convergence"
OLD_SERVICE = ROOT / "src/optional/c2_mapped_far_service_abort_v3.s"
NEW_SERVICE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
OLD_PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding_abort_v2.s"
NEW_PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding_liveness_v3.s"


class ConfigurationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConfigurationError(message)


def _replace_sources(sources: tuple[Path, ...], *, successor: bool
                     ) -> tuple[Path, ...]:
    first_service, second_service = ((OLD_SERVICE, NEW_SERVICE) if successor
                                     else (NEW_SERVICE, OLD_SERVICE))
    first_padding, second_padding = ((OLD_PADDING, NEW_PADDING) if successor
                                     else (NEW_PADDING, OLD_PADDING))
    require(sources.count(first_service) == 1
            and sources.count(first_padding) == 1
            and second_service not in sources and second_padding not in sources,
            "liveness source-owner predecessor drift")
    return tuple(second_service if path == first_service else
                 second_padding if path == first_padding else path
                 for path in sources)


def _replace_linker_contract(text: str) -> str:
    old_padding = "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 10"
    require(text.count(old_padding) == 1,
            "R1 facade-padding contract absent before liveness")
    text = text.replace(old_padding,
        "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 0", 1)
    # Widen only the two service-capacity predicates that liveness owns.  The
    # physical LOADADDR relation belongs to the active placement policy and is
    # deliberately retained byte-for-byte (fixed, tight-top or page-congruent).
    old_size = "SIZEOF(.lisp65_c2_mapped_far_service) == 1382"
    new_size = ("SIZEOF(.lisp65_c2_mapped_far_service) > 0 &&\n"
                "        SIZEOF(.lisp65_c2_mapped_far_service) <= 1499")
    old_end = "__lisp65_c2_mapped_far_service_end == 0x7e18"
    new_end = "__lisp65_c2_mapped_far_service_end <= 0x7e8d"
    require(text.count(old_size) == text.count(old_end) == 1,
            "R1 mapped-far semantic capacity predicates absent")
    fixed_load = "__lisp65_c2_mapped_far_service_load_end == 0x0002be18"
    if fixed_load in text:
        require(text.count(fixed_load) == 1,
                "R1 fixed load-end predicate is not unique")
        text = text.replace(
            fixed_load,
            "__lisp65_c2_mapped_far_service_load_end <= 0x0002be8d", 1)
    else:
        relations = (
            "__lisp65_c2_mapped_far_service_load_end ==\n"
            "            LOADADDR(.lisp65_c2_mapped_product_cold)",
            "LOADADDR(.lisp65_c2_mapped_product_cold) -\n"
            "            __lisp65_c2_mapped_far_service_load_end ==\n"
            "        ADDR(.lisp65_c2_mapped_product_cold) -\n"
            "            __lisp65_c2_mapped_far_service_end",
        )
        require(sum(text.count(row) for row in relations) == 1,
                "active mapped-far LOADADDR relation is not unique")
    return text.replace(old_size, new_size, 1).replace(old_end, new_end, 1)


def configure(product: Any) -> dict[str, Any]:
    definitions = tuple(product.CONVERGENCE_DEFINES)
    sources = tuple(product.CONVERGENCE_SOURCES)
    require(FEATURE not in definitions, "continuation liveness configured twice")
    replaced = _replace_sources(sources, successor=True)
    successor_definitions = (*definitions, FEATURE)
    scoped_definitions = OWNER_IDENTITY.definitions(
        product, SCOPE, definitions, (FEATURE,))
    scopes: list[dict[str, Any]] = []
    count = 0
    for row in product.SOURCE_OWNER_SCOPES:
        if row.get("name") == SCOPE:
            scopes.append({**row, "defines": scoped_definitions,
                           "sources": replaced})
            count += 1
        else:
            scopes.append(row)
    require(count == 1, "mapped-far liveness owner scope is not unique")

    original_linker = product.linker_script
    require(not getattr(original_linker, "_v160_liveness_successor", False),
            "liveness linker successor configured twice")

    def linker_script(*args: Any, **kwargs: Any) -> str:
        return _replace_linker_contract(original_linker(*args, **kwargs))

    linker_script._v160_liveness_successor = True  # type: ignore[attr-defined]
    linker_script._v160_liveness_original = original_linker  # type: ignore[attr-defined]
    product.CONVERGENCE_DEFINES = successor_definitions
    product.CONVERGENCE_SOURCES = replaced
    product.SOURCE_OWNER_SCOPES = tuple(scopes)
    product.linker_script = linker_script

    selected = {Path(path).resolve()
                for path in product.source_list(successor_definitions)}
    require(NEW_SERVICE.resolve() in selected and NEW_PADDING.resolve() in selected
            and OLD_SERVICE.resolve() not in selected
            and OLD_PADDING.resolve() not in selected,
            "real compiler profile did not consume liveness successors")
    return {"feature": FEATURE, "scope": SCOPE,
            "sources": [path.relative_to(ROOT).as_posix() for path in replaced],
            "predecessors_absent": True,
            "facade_padding_contract_bytes": 0,
            "configured_before_core_install": True}


def restore_predecessor(product: Any) -> None:
    definitions = tuple(product.CONVERGENCE_DEFINES)
    if FEATURE not in definitions:
        return
    sources = tuple(product.CONVERGENCE_SOURCES)
    predecessor_sources = _replace_sources(sources, successor=False)
    predecessor_definitions = tuple(x for x in definitions if x != FEATURE)
    scoped_definitions = OWNER_IDENTITY.definitions(
        product, SCOPE, predecessor_definitions)
    scopes: list[dict[str, Any]] = []
    count = 0
    for row in product.SOURCE_OWNER_SCOPES:
        if row.get("name") == SCOPE:
            scopes.append({**row, "defines": scoped_definitions,
                           "sources": predecessor_sources})
            count += 1
        else:
            scopes.append(row)
    require(count == 1, "liveness predecessor owner scope restore drift")
    current_linker = product.linker_script
    require(getattr(current_linker, "_v160_liveness_successor", False),
            "liveness linker wrapper absent during restore")
    product.CONVERGENCE_DEFINES = predecessor_definitions
    product.CONVERGENCE_SOURCES = predecessor_sources
    product.SOURCE_OWNER_SCOPES = tuple(scopes)
    product.linker_script = current_linker._v160_liveness_original
