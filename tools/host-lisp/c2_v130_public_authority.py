#!/usr/bin/env python3
"""Bind/check the public clean-build authority against accepted Link 88."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "config/c2-lite-public-build-authority.json"
MEDIA = ROOT / (
    "build/c2.3/v1.3.0-candidate-media-link88-r1/candidate-manifest.json"
)
R6 = ROOT / "build/c2.3/v1.3.0-acceptance/r6/ship/manifest.json"
PRODUCT_SET = (
    "072ca89affc35bdf0e20cab382e8bd4a9df64babf535e23f6b2e268962daed1f"
)
PACKAGE_SET = (
    "3e0db21adb825cfa44c60bd005f2644a3717f4fcc5b02ae87e1139d3188a3397"
)
MANIFEST_REL = (
    "build/c2.3/v1.3.0-candidate-media-link88-r1/candidate-manifest.json"
)


class AuthorityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuthorityError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def projection(media: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = media.get("artifacts")
    require(
        media.get("status") == "passed-complete-C2-lite-two-media-product"
        and media.get("artifact_count") == 19
        and media.get("artifact_set_sha256") == PRODUCT_SET
        and isinstance(rows, list) and len(rows) == 19,
        "Link-88 media authority drift",
    )
    return {
        str(row["role"]): {
            "bytes": int(row["bytes"]), "sha256": str(row["sha256"])
        }
        for row in rows
    }


def validate(value: dict[str, Any], roles: dict[str, dict[str, Any]]) -> None:
    require(
        value.get("format") == "lisp65-c2-lite-public-build-authority-v1"
        and value.get("version") == 1
        and value.get("entry_point") == "make workbench-product"
        and value.get("candidate_manifest_path") == MANIFEST_REL
        and value.get("artifact_count") == 19
        and value.get("sealed_product_artifact_set_sha256") == PRODUCT_SET
        and value.get("sealed_package_set_sha256") == PACKAGE_SET
        and value.get("sealed_roles") == roles
        and value.get("private_evidence_is_build_input") is False
        and value.get("sealed_profile_identity", {}).get("sha256")
            == "d2c186c4e8919cf4d3b50c4d3190bb35c70bad39add483b2d8f9106114dcdf65",
        "public Link-88 authority drift",
    )


def bind() -> dict[str, Any]:
    media = load(MEDIA)
    r6 = load(R6)
    require(
        r6.get("package_set_sha256") == PACKAGE_SET,
        "R6 package set drift",
    )
    roles = projection(media)
    value = load(AUTHORITY)
    value.update({
        "candidate_manifest_path": MANIFEST_REL,
        "artifact_count": 19,
        "sealed_product_artifact_set_sha256": PRODUCT_SET,
        "sealed_package_set_sha256": PACKAGE_SET,
        "sealed_roles": roles,
    })
    validate(value, roles)
    with tempfile.NamedTemporaryFile(
        dir=AUTHORITY.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(AUTHORITY)
    return value


def selftest(value: dict[str, Any], roles: dict[str, dict[str, Any]]) -> int:
    mutations = (
        lambda item: item.update(candidate_manifest_path="build/x.json"),
        lambda item: item.update(sealed_product_artifact_set_sha256="0" * 64),
        lambda item: item.update(sealed_package_set_sha256="0" * 64),
        lambda item: item.update(private_evidence_is_build_input=True),
        lambda item: item["sealed_roles"].pop(next(iter(item["sealed_roles"]))),
    )
    rejected = 0
    for mutate in mutations:
        changed = deepcopy(value)
        mutate(changed)
        try:
            validate(changed, roles)
        except AuthorityError:
            rejected += 1
    require(rejected == len(mutations), "public authority mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("rebind", "check"))
    args = parser.parse_args()
    try:
        if args.action == "rebind":
            value = bind()
        else:
            media = load(MEDIA)
            roles = projection(media)
            value = load(AUTHORITY)
            validate(value, roles)
        rejected = selftest(value, projection(load(MEDIA)))
        print(
            "c2-v130-public-authority: PASS "
            f"roles=19 mutations={rejected} set={PRODUCT_SET}"
        )
        return 0
    except (AuthorityError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v130-public-authority: FIRST RED: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
