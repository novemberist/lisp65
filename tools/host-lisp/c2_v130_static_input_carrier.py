#!/usr/bin/env python3
"""Verify or materialize the product-bound Link-88 static input carrier."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-v130-static-input-carrier.json"
EXPECTED = {
    "idex-blob": (2940, "293ee9ba357c4c970a8e27f3f09beafd968e317c90d0852aad41b5a3e2e93e9f"),
    "idex-image": (7380, "e7bb1a4139f9cd31696d23809bc008c3759d2bc445ea5303ad1738c7c948b392"),
    "idex-manifest": (70458, "168b17833fa832e651826fc4e3ff66e9eff363bf27aa49a3a36c2f434fba4770"),
    "m65d-blob": (4083, "3556853d71d05ea760e21f839b1e32372f7e7882552fb87e7e22a2656f4877c7"),
    "m65d-image": (6573, "4a32837cc87480375c982a3d39ee8f1759b124c2e563cf4d1aaafd439a8e720e"),
    "m65d-manifest": (64154, "f68b989f9d51e2b39ed728d64f88408ef7855751d1ddc3c3231c149b72d9dbfa"),
}


class CarrierError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CarrierError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "carrier contract must be an object")
    return value


def validate_shape(value: dict[str, Any]) -> list[dict[str, Any]]:
    require(
        value.get("format") == "lisp65-c2-v130-static-input-carrier-v1"
        and value.get("version") == 1
        and value.get("id") == "link88-static-plane-historical-IDEX-M65D"
        and value.get("status") == "product-bound-generated-inputs",
        "carrier contract identity drift")
    rows = value.get("artifacts")
    require(isinstance(rows, list) and len(rows) == len(EXPECTED),
            "carrier artifact count drift")
    require({row.get("role") for row in rows} == set(EXPECTED),
            "carrier role inventory drift")
    destinations: set[str] = set()
    sources: set[str] = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {
            "role", "source", "destination", "bytes", "sha256"},
            "carrier row schema drift")
        role = str(row["role"])
        require((row["bytes"], row["sha256"]) == EXPECTED[role],
                f"carrier identity drift: {role}")
        source = str(row["source"])
        destination = str(row["destination"])
        require(source.startswith(
            "tests/bytecode/dialect-v2/fixtures/v130-static-inputs/")
            and destination.startswith(
                "build/c2.2/substitution/"
                "published-nullary-call-bytecode-artifacts/libs/"),
            f"carrier path domain drift: {role}")
        sources.add(source)
        destinations.add(destination)
    require(len(sources) == len(EXPECTED)
            and len(destinations) == len(EXPECTED),
            "carrier paths are not one-to-one")
    return rows


def check_files(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        path = ROOT / row["source"]
        require(path.is_file() and not path.is_symlink(),
                f"carrier source absent: {row['role']}")
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                f"carrier source bytes drift: {row['role']}")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", row["source"]],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False)
        require(tracked.returncode == 0,
                f"carrier source is not tracked: {row['role']}")
    by_role = {row["role"]: row for row in rows}
    for name in ("idex", "m65d"):
        manifest = json.loads(
            (ROOT / by_role[f"{name}-manifest"]["source"]).read_text(
                encoding="utf-8"))
        blob = by_role[f"{name}-blob"]
        image = by_role[f"{name}-image"]
        require(
            manifest.get("blob") == blob["destination"]
            and manifest.get("blob_sha256") == blob["sha256"]
            and manifest.get("code_bytes") == blob["bytes"],
            f"carrier manifest/blob binding drift: {name}")
        external = manifest.get("external_image")
        require(
            isinstance(external, dict)
            and external.get("path") == image["destination"]
            and external.get("sha256") == image["sha256"]
            and external.get("bytes") == image["bytes"],
            f"carrier manifest/image binding drift: {name}")


def materialize(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        source = ROOT / row["source"]
        destination = ROOT / row["destination"]
        if destination.exists():
            require(destination.is_file() and not destination.is_symlink()
                    and destination.stat().st_size == row["bytes"]
                    and sha(destination) == row["sha256"],
                    f"existing carrier destination differs: {row['role']}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        require(destination.stat().st_size == row["bytes"]
                and sha(destination) == row["sha256"],
                f"materialized carrier drift: {row['role']}")


def selftest(value: dict[str, Any]) -> None:
    mutations = []
    for name, mutate in (
        ("drop", lambda x: x["artifacts"].pop()),
        ("role", lambda x: x["artifacts"][0].update(role="other")),
        ("hash", lambda x: x["artifacts"][0].update(sha256="0" * 64)),
        ("source", lambda x: x["artifacts"][0].update(source="/tmp/x")),
        ("destination", lambda x: x["artifacts"][0].update(destination="src/x")),
    ):
        changed = deepcopy(value)
        mutate(changed)
        try:
            validate_shape(changed)
        except CarrierError:
            mutations.append(name)
    require(len(mutations) == 5, f"carrier selftest survivors: {mutations}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "materialize", "selftest"))
    args = parser.parse_args()
    try:
        value = load_contract()
        rows = validate_shape(value)
        if args.action == "selftest":
            selftest(value)
        else:
            check_files(rows)
            if args.action == "materialize":
                materialize(rows)
        count = len(EXPECTED)
        suffix = f" materialized={count}" if args.action == "materialize" else ""
        print(
            f"c2-v130-static-input-carrier: PASS assets={count} "
            f"mutations=5{suffix}")
        return 0
    except (CarrierError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v130-static-input-carrier: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
