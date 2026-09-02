#!/usr/bin/env python3
"""Prove the complete R3 two-media product set in varied fresh clones."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools" / "host-lisp" / "r3_product_reproducibility.py"
DEFAULT_RECEIPT = (
    ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3"
    / "product-block-reproducibility-receipt.json"
)
FORMAT = "lisp65-r3-product-reproducibility-v1"
BUILD_COMMANDS = (
    ("make", "-s", "workbench-overlay-stack-guard", "v2-workbench-library-composition-check"),
    (
        "python3", "tools/host-lisp/chain_walker_inventory.py", "--out",
        "build/bytecode/dialect-v2/wave1-chain-walker-inventory-receipt.json",
    ),
    (
        "python3", "tools/host-lisp/r3_product_block.py", "generate",
        "--receipt", "build/r3/product/product-block-receipt.json",
    ),
)
AXES = (
    {
        "id": "fresh-clone-seed-17-pago-pago-2001",
        "PYTHONHASHSEED": "17",
        "SOURCE_DATE_EPOCH": "978307200",
        "TZ": "Pacific/Pago_Pago",
    },
    {
        "id": "fresh-clone-seed-987654323-kiritimati-2031",
        "PYTHONHASHSEED": "987654323",
        "SOURCE_DATE_EPOCH": "1924992000",
        "TZ": "Pacific/Kiritimati",
    },
)


class ReproError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(argv: tuple[str, ...] | list[str], *, cwd: Path, env: dict[str, str] | None, label: str) -> str:
    result = subprocess.run(
        argv, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-100:])
        raise ReproError(f"{label} failed ({result.returncode}):\n{tail}")
    return result.stdout


def full_commit(value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    commit = result.stdout.strip() if result.returncode == 0 else ""
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ReproError(f"invalid source commit: {value!r}")
    return commit


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReproError(f"{label} must be an object")
    return value


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def build_one(parent: Path, commit: str, axis: dict[str, str]) -> dict[str, Any]:
    checkout = parent / axis["id"]
    clone_env = os.environ.copy()
    clone_env["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(
        ["git", "clone", "--no-local", "--no-checkout", str(ROOT), str(checkout)],
        cwd=parent, env=clone_env, label=f"clone {axis['id']}",
    )
    run(
        ["git", "checkout", "--detach", commit], cwd=checkout, env=clone_env,
        label=f"checkout {axis['id']}",
    )
    toolchain = checkout / "tools" / "llvm-mos"
    if toolchain.exists() or toolchain.is_symlink():
        raise ReproError(f"fresh clone unexpectedly contains toolchain path: {toolchain}")
    toolchain.symlink_to(ROOT / "tools" / "llvm-mos", target_is_directory=True)
    environment = os.environ.copy()
    environment.update({key: axis[key] for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")})
    outputs = []
    for index, command in enumerate(BUILD_COMMANDS):
        outputs.append(run(command, cwd=checkout, env=environment, label=f"build {axis['id']} step {index + 1}"))
    manifest_path = checkout / "build" / "r3" / "product" / "candidate-manifest.json"
    receipt_path = checkout / "build" / "r3" / "product" / "product-block-receipt.json"
    composition_path = checkout / "build" / "bytecode" / "dialect-v2" / "workbench-library-composition-budget.json"
    manifest = load(manifest_path, "fresh candidate manifest")
    receipt = load(receipt_path, "fresh product receipt")
    composition = load(composition_path, "fresh composition report")
    rows = manifest.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise ReproError("fresh candidate manifest lacks artifacts")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"role", "name", "path", "bytes", "sha256"}:
            raise ReproError(f"fresh artifact {index} schema drift")
        path = checkout / row["path"]
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]
            or sha(path) != row["sha256"]
        ):
            raise ReproError(f"fresh artifact binding drift: {row['role']}")
        normalized.append(dict(row))
    observed_set = artifact_set_sha(normalized)
    if (
        manifest.get("format") != "lisp65-r3-candidate-manifest-v1"
        or manifest.get("status") != "product-built-g3-not-run"
        or manifest.get("artifact_set_sha256") != observed_set
        or receipt.get("product_identity", {}).get("artifact_set_sha256") != observed_set
        or receipt.get("status") != "product-implemented-g3-not-run"
        or receipt.get("verification", {}).get("emulator_started") is not False
    ):
        raise ReproError("fresh product identity/claim drift")
    epoch = int(axis["SOURCE_DATE_EPOCH"])
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": axis["PYTHONHASHSEED"],
            "SOURCE_DATE_EPOCH": axis["SOURCE_DATE_EPOCH"],
            "TZ": axis["TZ"],
            "calendar_date": datetime.fromtimestamp(epoch, ZoneInfo(axis["TZ"])).date().isoformat(),
        },
        "artifact_set_sha256": observed_set,
        "product_build_id": manifest.get("product_build_id"),
        "candidate_manifest_sha256": sha(manifest_path),
        "product_receipt_sha256": sha(receipt_path),
        "composition": {
            "ext_headroom_bytes": composition.get("ext_code", {}).get("post_headroom"),
            "symbols_free": composition.get("symbols", {}).get("headroom"),
            "namepool_free_bytes": composition.get("namepool", {}).get("headroom"),
            "directory_free_entries": composition.get("directory", {}).get("post_align_headroom"),
        },
        "artifacts": normalized,
        "log_lines": sum(len(output.splitlines()) for output in outputs),
    }


def build_receipt(source_commit: str, measured_on: str) -> dict[str, Any]:
    commit = full_commit(source_commit)
    with tempfile.TemporaryDirectory(prefix="lisp65-r3-product-repro-") as raw:
        builds = [build_one(Path(raw), commit, axis) for axis in AXES]
    first, second = builds
    for key in (
        "artifact_set_sha256", "product_build_id", "candidate_manifest_sha256",
        "product_receipt_sha256", "composition", "artifacts",
    ):
        if first[key] != second[key]:
            raise ReproError(f"varied fresh-clone product builds diverged: {key}")
    return {
        "format": FORMAT,
        "version": 1,
        "id": "r3-two-media-product-varied-double-build",
        "status": "passed",
        "measured_on": measured_on,
        "source_commit": commit,
        "generator": {
            "path": GENERATOR.relative_to(ROOT).as_posix(),
            "bytes": GENERATOR.stat().st_size,
            "sha256": sha(GENERATOR),
        },
        "variation_axes": [
            "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
            "timezone-and-calendar-date",
        ],
        "builds": [
            {key: build[key] for key in (
                "id", "clone", "commands", "environment", "artifact_set_sha256",
                "product_build_id", "candidate_manifest_sha256",
                "product_receipt_sha256", "composition",
            )}
            for build in builds
        ],
        "artifact_set_sha256": first["artifact_set_sha256"],
        "product_build_id": first["product_build_id"],
        "candidate_manifest_sha256": first["candidate_manifest_sha256"],
        "product_receipt_sha256": first["product_receipt_sha256"],
        "composition": first["composition"],
        "product_artifacts": first["artifacts"],
        "result": "byte-identical-complete-product-set-across-varied-environments",
        "claims": {"G3": "not-run", "G6": "not-run", "release_effect": "none"},
    }


def lower_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReproError(f"{label} is not a lowercase SHA-256")
    return value


def validate(receipt: dict[str, Any]) -> None:
    keys = {
        "format", "version", "id", "status", "measured_on", "source_commit",
        "generator", "variation_axes", "builds", "artifact_set_sha256",
        "product_build_id", "candidate_manifest_sha256", "product_receipt_sha256",
        "composition", "product_artifacts", "result", "claims",
    }
    if not isinstance(receipt, dict) or set(receipt) != keys:
        raise ReproError("R3 reproducibility receipt schema drift")
    if (
        receipt["format"] != FORMAT or receipt["version"] != 1
        or receipt["id"] != "r3-two-media-product-varied-double-build"
        or receipt["status"] != "passed"
        or receipt["result"] != "byte-identical-complete-product-set-across-varied-environments"
        or receipt["claims"] != {"G3": "not-run", "G6": "not-run", "release_effect": "none"}
    ):
        raise ReproError("R3 reproducibility identity/result drift")
    if not isinstance(receipt["source_commit"], str) or len(receipt["source_commit"]) != 40:
        raise ReproError("R3 reproducibility source commit drift")
    if receipt["variation_axes"] != [
        "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "timezone-and-calendar-date",
    ]:
        raise ReproError("R3 reproducibility variation axes drift")
    generator = receipt["generator"]
    if (
        not isinstance(generator, dict) or set(generator) != {"path", "bytes", "sha256"}
        or generator["path"] != "tools/host-lisp/r3_product_reproducibility.py"
        or type(generator["bytes"]) is not int or generator["bytes"] <= 0
    ):
        raise ReproError("R3 reproducibility generator binding drift")
    lower_sha(generator["sha256"], "generator.sha256")
    artifact_set = lower_sha(receipt["artifact_set_sha256"], "artifact_set_sha256")
    lower_sha(receipt["candidate_manifest_sha256"], "candidate_manifest_sha256")
    lower_sha(receipt["product_receipt_sha256"], "product_receipt_sha256")
    if (
        not isinstance(receipt["product_build_id"], str) or len(receipt["product_build_id"]) != 8
        or any(character not in "0123456789abcdef" for character in receipt["product_build_id"])
    ):
        raise ReproError("R3 product build ID drift")
    composition = receipt["composition"]
    if (
        not isinstance(composition, dict) or set(composition) != {
            "ext_headroom_bytes", "symbols_free", "namepool_free_bytes",
            "directory_free_entries",
        }
        or any(type(value) is not int for value in composition.values())
        or composition["ext_headroom_bytes"] < 16384
        or composition["symbols_free"] < 120
        or composition["namepool_free_bytes"] < 2145
        or composition["directory_free_entries"] < 32
    ):
        raise ReproError("R3 reproducibility composition-floor drift")
    rows = receipt["product_artifacts"]
    if not isinstance(rows, list) or not rows:
        raise ReproError("R3 reproducibility artifact inventory missing")
    roles: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"role", "name", "path", "bytes", "sha256"}:
            raise ReproError(f"product_artifacts[{index}] schema drift")
        if type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ReproError(f"product_artifacts[{index}] size drift")
        lower_sha(row["sha256"], f"product_artifacts[{index}].sha256")
        roles.append(row["role"])
    if len(roles) != len(set(roles)) or artifact_set_sha(rows) != artifact_set:
        raise ReproError("R3 reproducibility aggregate identity drift")
    builds = receipt["builds"]
    if not isinstance(builds, list) or len(builds) != 2:
        raise ReproError("R3 reproducibility requires exactly two builds")
    environments = []
    expected_commands = [" ".join(command) for command in BUILD_COMMANDS]
    required_chain_command = (
        "python3 tools/host-lisp/chain_walker_inventory.py --out "
        "build/bytecode/dialect-v2/wave1-chain-walker-inventory-receipt.json"
    )
    if (
        len(expected_commands) != 3
        or expected_commands[1] != required_chain_command
        or not expected_commands[2].startswith("python3 tools/host-lisp/r3_product_block.py generate ")
    ):
        raise ReproError("R3 fresh-clone chain-inventory closure drift")
    for index, build in enumerate(builds):
        if not isinstance(build, dict) or set(build) != {
            "id", "clone", "commands", "environment", "artifact_set_sha256",
            "product_build_id", "candidate_manifest_sha256", "product_receipt_sha256",
            "composition",
        }:
            raise ReproError(f"builds[{index}] schema drift")
        if build["clone"] != "fresh-no-local-detached" or build["commands"] != expected_commands:
            raise ReproError(f"builds[{index}] isolation/command drift")
        for key in (
            "artifact_set_sha256", "product_build_id", "candidate_manifest_sha256",
            "product_receipt_sha256", "composition",
        ):
            if build[key] != receipt[key]:
                raise ReproError(f"builds[{index}] result drift: {key}")
        environment = build["environment"]
        if not isinstance(environment, dict) or set(environment) != {
            "PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date",
        }:
            raise ReproError(f"builds[{index}] environment drift")
        environments.append(environment)
    for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date"):
        if environments[0][key] == environments[1][key]:
            raise ReproError(f"R3 reproducibility axis did not vary: {key}")


def selftest() -> None:
    rows = [{
        "role": "workbench-prg", "name": "lisp65.prg", "path": "build/lisp65.prg",
        "bytes": 1, "sha256": "1" * 64,
    }]
    build = {
        "id": "a", "clone": "fresh-no-local-detached",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1", "TZ": "A",
            "calendar_date": "2001-01-01",
        },
        "artifact_set_sha256": artifact_set_sha(rows), "product_build_id": "12345678",
        "candidate_manifest_sha256": "2" * 64, "product_receipt_sha256": "3" * 64,
        "composition": {
            "ext_headroom_bytes": 16384, "symbols_free": 120,
            "namepool_free_bytes": 2145, "directory_free_entries": 32,
        },
    }
    fixture = {
        "format": FORMAT, "version": 1, "id": "r3-two-media-product-varied-double-build",
        "status": "passed", "measured_on": "2001-01-01", "source_commit": "0" * 40,
        "generator": {"path": "tools/host-lisp/r3_product_reproducibility.py", "bytes": 1, "sha256": "4" * 64},
        "variation_axes": ["fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "timezone-and-calendar-date"],
        "builds": [build, deepcopy(build)], "artifact_set_sha256": artifact_set_sha(rows),
        "product_build_id": "12345678", "candidate_manifest_sha256": "2" * 64,
        "product_receipt_sha256": "3" * 64, "composition": build["composition"],
        "product_artifacts": rows,
        "result": "byte-identical-complete-product-set-across-varied-environments",
        "claims": {"G3": "not-run", "G6": "not-run", "release_effect": "none"},
    }
    fixture["builds"][1]["id"] = "b"
    fixture["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2", "TZ": "B",
        "calendar_date": "2031-01-01",
    }
    validate(fixture)
    survivors = []
    mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        ("status", lambda x: x.update(status="failed")),
        ("same-seed", lambda x: x["builds"][1]["environment"].update(PYTHONHASHSEED="1")),
        ("artifact-set", lambda x: x.update(artifact_set_sha256="f" * 64)),
        ("one-build", lambda x: x["builds"].pop()),
        ("claim", lambda x: x["claims"].update(G3="passed")),
    )
    for name, mutate in mutations:
        changed = deepcopy(fixture)
        mutate(changed)
        try:
            validate(changed)
        except ReproError:
            continue
        survivors.append(name)
    if survivors:
        raise ReproError(f"selftest accepted mutations: {survivors}")
    print(f"r3-product-reproducibility: SELFTEST PASS mutations={len(mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--source-commit", required=True)
    generate.add_argument("--measured-on", required=True)
    generate.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    check = sub.add_parser("check")
    check.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
            return 0
        receipt_path = args.output if args.command == "generate" else args.receipt
        if not receipt_path.is_absolute():
            receipt_path = ROOT / receipt_path
        if args.command == "generate":
            receipt = build_receipt(args.source_commit, args.measured_on)
            validate(receipt)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(canonical(receipt))
            print(
                "r3-product-reproducibility: WROTE builds=2 "
                f"set={receipt['artifact_set_sha256']} output={receipt_path.relative_to(ROOT)}"
            )
        else:
            receipt = load(receipt_path, "R3 product reproducibility receipt")
            validate(receipt)
            generator = receipt["generator"]
            if (
                GENERATOR.is_symlink() or not GENERATOR.is_file()
                or GENERATOR.stat().st_size != generator["bytes"] or sha(GENERATOR) != generator["sha256"]
            ):
                raise ReproError("live R3 reproducibility generator binding drift")
            print(
                "r3-product-reproducibility: PASS builds=2 varied=yes "
                f"set={receipt['artifact_set_sha256']} G3=not-run"
            )
        return 0
    except (ReproError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"r3-product-reproducibility: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
