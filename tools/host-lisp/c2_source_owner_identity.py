#!/usr/bin/env python3
"""Identity-scoped projection helpers for source-owner registries."""

from __future__ import annotations

from typing import Any


class SourceOwnerIdentityError(RuntimeError):
    pass


def definitions(product: Any, owner_name: str,
                selected_definitions: tuple[str, ...],
                additions: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Project selected definitions through the named owner row."""
    rows = [row for row in product.SOURCE_OWNER_SCOPES
            if row.get("name") == owner_name]
    if len(rows) != 1:
        raise SourceOwnerIdentityError(
            f"source-owner identity is not unique: {owner_name}")
    owned = set(str(value) for value in rows[0]["defines"])
    owned.update(str(value) for value in additions)
    result = tuple(str(value) for value in (*selected_definitions, *additions)
                   if str(value) in owned)
    if len(result) != len(set(result)):
        raise SourceOwnerIdentityError(
            f"duplicate identity-scoped definition: {owner_name}")
    return result
