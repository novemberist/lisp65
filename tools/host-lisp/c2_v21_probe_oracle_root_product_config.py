#!/usr/bin/env python3
"""Opt the full-span candidate into synchronous reads for mutable content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import c2_v21_full_span_product_config as FULL
import c2_source_owner_identity as OWNER_IDENTITY


ROOT = Path(__file__).resolve().parents[2]
FEATURE = "LISP65_C2_MUTABLE_CPU_READS"
PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding.s"


class ConfigurationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConfigurationError(message)


def configure(product: Any) -> dict[str, Any]:
    """Add the root transport feature to the real full-span owner scope."""
    component = FULL.configure(product)
    require(FEATURE not in product.CONVERGENCE_DEFINES,
            "mutable CPU-read product feature configured twice")
    defines = (*product.CONVERGENCE_DEFINES, FEATURE)
    scoped_defines = OWNER_IDENTITY.definitions(
        product, "mapped-far-content-convergence", product.CONVERGENCE_DEFINES,
        (FEATURE,))
    sources = (*product.CONVERGENCE_SOURCES, PADDING)
    scopes: list[dict[str, Any]] = []
    replaced = 0
    for scope in product.SOURCE_OWNER_SCOPES:
        if scope.get("name") == "mapped-far-content-convergence":
            row = dict(scope)
            row["defines"] = scoped_defines
            row["sources"] = sources
            scopes.append(row)
            replaced += 1
        else:
            scopes.append(scope)
    require(replaced == 1, "mutable CPU-read owner scope is not unique")
    product.CONVERGENCE_DEFINES = defines
    product.CONVERGENCE_SOURCES = sources
    product.SOURCE_OWNER_SCOPES = tuple(scopes)
    selected = product.source_list(defines)
    require(str(FULL.SOURCE) in selected
            and str(FULL.PREDECESSOR) not in selected
            and str(PADDING) in selected,
            "root candidate lost the full-span service or explicit pad owner")
    return {
        **component,
        "feature": FEATURE,
        "defines": list(defines),
        "mutable_read_transport": "MAP-CPU",
        "mutable_reader_count": 9,
        "facade_padding": {
            "source": PADDING.relative_to(ROOT).as_posix(), "bytes": 19,
            "kind": "named-explicit-contract-filler"},
        "DMA_probe_jobs": 0,
        "DMA_completion_trust": False,
    }
