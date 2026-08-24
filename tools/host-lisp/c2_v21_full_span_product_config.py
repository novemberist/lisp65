#!/usr/bin/env python3
"""Opt the current product producer into the full-span assembly successor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import c2_source_owner_identity as OWNER_IDENTITY


ROOT = Path(__file__).resolve().parents[2]
FEATURE = "LISP65_C2_FULL_SPAN_CONVERGENCE"
SOURCE = ROOT / "src/optional/c2_mapped_far_convergence_full_span.s"
PREDECESSOR = ROOT / "src/c2_mapped_far_convergence.s"


class ConfigurationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConfigurationError(message)


def configure(product: Any) -> dict[str, Any]:
    """Replace only the convergence-body owner after real producer setup."""
    defines = tuple(product.CONVERGENCE_DEFINES)
    sources = tuple(product.CONVERGENCE_SOURCES)
    require(FEATURE not in defines, "full-span product feature configured twice")
    require(len(sources) == 2 and sources[1].resolve() == PREDECESSOR.resolve(),
            "full-span predecessor body is not the configured real owner")
    candidate_defines = (*defines, FEATURE)
    scoped_defines = OWNER_IDENTITY.definitions(
        product, "mapped-far-content-convergence", defines, (FEATURE,))
    candidate_sources = (sources[0], SOURCE)
    replacement = {
        "name": "mapped-far-content-convergence",
        "trigger": product.CONVERGENCE_FEATURE,
        "defines": scoped_defines,
        "sources": candidate_sources,
    }
    scopes: list[dict[str, Any]] = []
    replaced = 0
    for scope in product.SOURCE_OWNER_SCOPES:
        if scope.get("name") == replacement["name"]:
            scopes.append(replacement); replaced += 1
        else:
            scopes.append(scope)
    require(replaced == 1, "mapped-far source-owner identity is not unique")
    product.CONVERGENCE_DEFINES = candidate_defines
    product.CONVERGENCE_SOURCES = candidate_sources
    product.SOURCE_OWNER_SCOPES = tuple(scopes)
    selected = product.source_list(candidate_defines)
    require(str(SOURCE) in selected and str(PREDECESSOR) not in selected,
            "real producer did not consume exactly the full-span body")
    return {
        "feature": FEATURE,
        "service_owner": sources[0].relative_to(ROOT).as_posix(),
        "predecessor_body": PREDECESSOR.relative_to(ROOT).as_posix(),
        "candidate_body": SOURCE.relative_to(ROOT).as_posix(),
        "defines": list(candidate_defines),
        "sources": [path.relative_to(ROOT).as_posix()
                    for path in candidate_sources],
        "single_body_owner": True,
    }
