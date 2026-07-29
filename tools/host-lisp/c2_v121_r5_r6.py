#!/usr/bin/env python3
"""Bind the fresh-G5-tested v1.2.1 R5 set and package exact R6 bytes."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_r5_r6 as R6  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.1-acceptance"
R5_PREFLIGHT = BASE / "r5/r5-preflight-receipt.json"
G5 = BASE / "r5/hardware-session-01/g5-hardware-receipt.json"
R5_BIND_ROOT = BASE / "r5-tested"
R5_BIND = R5_BIND_ROOT / "r5-tested-set-receipt.json"
R6_ROOT = BASE / "r6"
R6_SHIP = R6_ROOT / "ship"
R6_RECEIPT = R6_ROOT / "r6-packaging-receipt.json"
CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
ROLE_COUNT = 19


class V121R6Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise V121R6Error(message)


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V121R6Error(f"cannot load {label}: {error}") from error
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"binding missing: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def write_exact(path: Path, value: dict[str, Any]) -> None:
    data = canonical(value)
    if path.exists() or path.is_symlink():
        require(
            path.is_file() and not path.is_symlink() and path.read_bytes() == data,
            f"existing receipt differs: {path}",
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def configure() -> None:
    R6.TOOL = ROOT / "tools/host-lisp/c2_v121_r5_r6.py"
    R6.OLD_R5 = R5_PREFLIGHT
    R6.G5 = G5
    R6.R5_OUT = R5_BIND_ROOT
    R6.R5_PRODUCT = R5_BIND_ROOT / "product"
    R6.R5_RECEIPT = R5_BIND
    R6.R6_OUT = R6_ROOT
    R6.R6_SHIP = R6_SHIP
    R6.R6_RECEIPT = R6_RECEIPT
    R6.CHAIN = ()
    R6.R5_ACCEPTED_STATUSES = {"passed-tested-R5-bind"}
    R6.R5_PROOF_NAME = "r5-preflight-receipt.json"
    R6.R5_PACKAGE_CLAIM = "passed-tested-R5-bind"
    R6.R5_DESCRIPTION = "fresh-G5-tested v1.2.1 R5 set"
    R6.R5_MAPPING = "all-19-tested-R5-roles-exactly-once"
    R6.R6_ID = "R6-from-v1.2.1-tested-R5"
    R6.R6_RECEIPT_ID = "R6-v1.2.1-tested-set"
    R6.RECORDED_ON = date.today().isoformat()


def bind_tested_r5() -> dict[str, Any]:
    preflight = load(R5_PREFLIGHT, "R5 preflight")
    g5 = load(G5, "G5 hardware receipt")
    contract = load(CONTRACT, "acceptance contract")
    rows = preflight.get("materialized_artifacts")
    roles = contract.get("artifact_roles")
    require(
        preflight.get("status") == "passed-ready-for-fresh-G5-hardware"
        and isinstance(rows, list)
        and len(rows) == ROLE_COUNT
        and isinstance(roles, list)
        and len(roles) == ROLE_COUNT
        and {row.get("role") for row in rows} == set(roles),
        "R5 preflight role closure drift",
    )
    for row in rows:
        path = ROOT / row["materialized_path"]
        require(
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"R5 materialized role drift: {row['role']}",
        )
    require(
        g5.get("status") == "passed-fresh-nine-case-G5"
        and g5.get("result") == "passed"
        and len(g5.get("cases", [])) == 9
        and g5.get("product", {}).get("artifact_set_sha256")
        == preflight.get("artifact_set_sha256")
        and g5.get("product", {}).get("product_d81", {}).get("sha256")
        == next(row["sha256"] for row in rows if row["role"] == "product-d81"),
        "G5 does not bind the exact materialized R5 set",
    )
    materialized = [
        {
            "role": row["role"],
            "name": row["name"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
            "source_path": row["materialized_path"],
            "materialized_path": row["materialized_path"],
        }
        for row in rows
    ]
    receipt = {
        "format": "lisp65-c2-lite-v1.2.1-tested-R5-receipt-v1",
        "version": 1,
        "id": "v1.2.1-R5-tested-set",
        "status": "passed-tested-R5-bind",
        "recorded_on": date.today().isoformat(),
        "authority": {
            "acceptance_contract": bind(CONTRACT),
            "R5_preflight": bind(R5_PREFLIGHT),
            "fresh_G5": bind(G5),
        },
        "successor_identity": {
            "artifact_count": ROLE_COUNT,
            "artifact_set_sha256": preflight["artifact_set_sha256"],
            "product_build_id": preflight["product_build_id"],
            "profile_build_id": preflight["profile_build_id"],
            "materialized_artifacts": materialized,
        },
        "mapping": "all-19-tested-R5-roles-byteidentical",
        "claims": {
            "R5": "passed-tested-set-bind",
            "G5": "passed-fresh-nine-case-G5",
            "R6": "not-run",
            "G6": "not-run",
            "release": "not-release-capable",
        },
        "execution_accounting": {
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
            "hardware_runs": 0,
        },
        "result": "passed",
    }
    write_exact(R5_BIND, receipt)
    return receipt


def verify() -> None:
    configure()
    tested = bind_tested_r5()
    packaged = R6.package()
    require(
        packaged["product_artifact_set_sha256"]
        == tested["successor_identity"]["artifact_set_sha256"],
        "tested R5/R6 identity drift",
    )
    print(
        "c2-v121 R5/R6 PASS "
        f"roles=19 set={packaged['product_artifact_set_sha256']} "
        f"package={packaged['package_set_sha256']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bind-r5", "package", "verify"))
    args = parser.parse_args()
    try:
        configure()
        if args.action == "bind-r5":
            value = bind_tested_r5()
            print(
                "c2-v121 R5 BIND PASS "
                f"set={value['successor_identity']['artifact_set_sha256']}"
            )
        elif args.action == "package":
            R6.package()
        else:
            verify()
        return 0
    except (V121R6Error, R6.RebindError, KeyError, OSError, TypeError) as error:
        print(f"c2-v121 R5/R6: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
