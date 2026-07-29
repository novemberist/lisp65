#!/usr/bin/env python3
"""Prove the complete C2-lite product/media set in varied fresh clones."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools/host-lisp/c2_lite_product_reproducibility.py"
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-media-fresh-clone-reproducibility-receipt.json")
FORMAT = "lisp65-c2-lite-media-product-reproducibility-v1"
BUILD_COMMANDS = (
    ("python3", "tools/host-lisp/c2_lite_canonical_product.py", "build"),
    ("python3", "tools/host-lisp/c2_lite_media_product.py", "build"),
)
MEDIA_MANIFEST_RELATIVE = Path(
    "build/c2.2/canonical-media/candidate-manifest.json")
MEDIA_MANIFEST_FORMAT = "lisp65-c2-lite-canonical-media-product-v1"
AXES = (
    {
        "id": "fresh-clone-seed-23-pago-pago-2002",
        "PYTHONHASHSEED": "23",
        "SOURCE_DATE_EPOCH": "1009843200",
        "TZ": "Pacific/Pago_Pago",
    },
    {
        "id": "fresh-clone-seed-987654329-kiritimati-2032",
        "PYTHONHASHSEED": "987654329",
        "SOURCE_DATE_EPOCH": "1956528000",
        "TZ": "Pacific/Kiritimati",
    },
)
ROLE_SET = {
    "linked-product-elf",
    "c2-resident-prg",
    "c2-bank2-static-code-plane",
    "c2d-v6-code-plane",
    "c2-two-record-boot-stage",
    "c2-session-family-region-0",
    "c2-product-shelf",
    "c2-boot-family",
    "c2-session-family-region-1",
    "c2-kernal-window",
    "resolved-profile",
    "library-ide",
    "library-idex",
    "library-m65d",
    "cold-stager",
    "boot-descriptor",
    "product-d81",
    "work-d81",
    "product-mount-descriptor",
}


class ReproError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def require(value: bool, message: str) -> None:
    if not value:
        raise ReproError(message)


def run(argv: list[str] | tuple[str, ...], *, cwd: Path,
        env: dict[str, str], label: str) -> str:
    result = subprocess.run(
        argv, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-120:])
        raise ReproError(
            f"{label} failed ({result.returncode}):\n{tail}")
    return result.stdout


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReproError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def full_commit(value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    commit = result.stdout.strip() if result.returncode == 0 else ""
    require(
        len(commit) == 40
        and all(character in "0123456789abcdef" for character in commit),
        f"invalid source commit: {value!r}")
    return commit


def normalized_rows(rows: Any, checkout: Path) -> list[dict[str, Any]]:
    require(isinstance(rows, list) and len(rows) == 19,
            "fresh candidate must contain exactly 19 artifacts")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and set(row) == {"role", "name", "path", "bytes", "sha256"},
            f"fresh artifact {index} schema drift")
        path = checkout / str(row["path"])
        require(
            not path.is_symlink() and path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"fresh artifact binding drift: {row['role']}")
        result.append({
            key: row[key]
            for key in ("role", "name", "path", "bytes", "sha256")
        })
    require(
        {str(row["role"]) for row in result} == ROLE_SET,
        "fresh C2-lite media role set drift")
    return sorted(result, key=lambda row: (row["role"], row["name"]))


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in rows
    ]
    return sha_bytes(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode("ascii"))


def artifact_differences(
        left: list[dict[str, Any]],
        right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a compact role-qualified diff for a failed aggregate proof."""
    left_by_role = {str(row["role"]): row for row in left}
    right_by_role = {str(row["role"]): row for row in right}
    result = []
    for role in sorted(set(left_by_role) | set(right_by_role)):
        first = left_by_role.get(role)
        second = right_by_role.get(role)
        if first == second:
            continue
        result.append({
            "role": role,
            "first": None if first is None else {
                key: first[key] for key in ("name", "bytes", "sha256")
            },
            "second": None if second is None else {
                key: second[key] for key in ("name", "bytes", "sha256")
            },
        })
    return result


def tool_bindings(checkout: Path) -> list[dict[str, Any]]:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    tools = (
        checkout / "tools/llvm-mos/bin/clang-23",
        checkout / "tools/llvm-mos/bin/lld",
        Path("/usr/bin/llvm-link"),
        Path("/usr/bin/setarch"),
        Path(c1541),
    )
    rows = []
    for path in tools:
        require(path.is_file(), f"fresh build tool absent: {path}")
        rows.append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        })
    return rows


def build_one(parent: Path, commit: str,
              axis: dict[str, str]) -> dict[str, Any]:
    checkout = parent / axis["id"]
    clone_environment = os.environ.copy()
    clone_environment["GIT_LFS_SKIP_SMUDGE"] = "1"
    run([
        "git", "clone", "--no-local", "--no-checkout", str(ROOT),
        str(checkout),
    ], cwd=parent, env=clone_environment, label=f"clone {axis['id']}")
    run([
        "git", "checkout", "--detach", commit,
    ], cwd=checkout, env=clone_environment, label=f"checkout {axis['id']}")
    toolchain = checkout / "tools/llvm-mos"
    require(
        not toolchain.exists() and not toolchain.is_symlink(),
        f"fresh clone unexpectedly contains toolchain path: {toolchain}")
    toolchain.symlink_to(ROOT / "tools/llvm-mos", target_is_directory=True)

    environment = os.environ.copy()
    environment.update({
        key: axis[key]
        for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")
    })
    outputs = [
        run(
            command, cwd=checkout, env=environment,
            label=f"{axis['id']} build step {index}")
        for index, command in enumerate(BUILD_COMMANDS, 1)
    ]
    manifest_path = checkout / MEDIA_MANIFEST_RELATIVE
    manifest = load(manifest_path, "fresh C2-lite media manifest")
    require(
        manifest.get("format") == MEDIA_MANIFEST_FORMAT
        and manifest.get("status")
            == "passed-complete-C2-lite-two-media-product"
        and manifest.get("artifact_count") == 19
        and manifest.get("execution_accounting", {}).get("hardware_runs") == 0,
        "fresh C2-lite media identity/claim drift")
    rows = normalized_rows(manifest.get("artifacts"), checkout)
    artifact_set = artifact_set_sha(rows)
    require(
        manifest.get("artifact_set_sha256") == artifact_set,
        "fresh C2-lite aggregate artifact identity drift")
    epoch = int(axis["SOURCE_DATE_EPOCH"])
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": axis["PYTHONHASHSEED"],
            "SOURCE_DATE_EPOCH": axis["SOURCE_DATE_EPOCH"],
            "TZ": axis["TZ"],
            "calendar_date": datetime.fromtimestamp(
                epoch, ZoneInfo(axis["TZ"])).date().isoformat(),
        },
        "artifact_set_sha256": artifact_set,
        "product_build_id": manifest.get("product_build_id"),
        "profile_build_id": manifest.get("profile_build_id"),
        "candidate_manifest_sha256": sha(manifest_path),
        "artifacts": rows,
        "tool_bindings": tool_bindings(checkout),
        "log_lines": sum(len(output.splitlines()) for output in outputs),
    }


def build_receipt(source_commit: str, measured_on: str) -> dict[str, Any]:
    commit = full_commit(source_commit)
    with tempfile.TemporaryDirectory(
            prefix="lisp65-c2-lite-media-repro-") as raw:
        builds = [
            build_one(Path(raw), commit, axis)
            for axis in AXES
        ]
    first, second = builds
    for key in (
        "product_build_id", "profile_build_id", "artifacts",
        "artifact_set_sha256", "tool_bindings",
    ):
        if first[key] != second[key]:
            diagnostic = {
                "field": key,
                "first": {
                    "artifact_set_sha256": first["artifact_set_sha256"],
                    "product_build_id": first["product_build_id"],
                    "profile_build_id": first["profile_build_id"],
                },
                "second": {
                    "artifact_set_sha256": second["artifact_set_sha256"],
                    "product_build_id": second["product_build_id"],
                    "profile_build_id": second["profile_build_id"],
                },
                "artifact_differences": artifact_differences(
                    first["artifacts"], second["artifacts"]),
            }
            raise ReproError(
                "varied fresh-clone C2-lite builds diverged:\n"
                + json.dumps(diagnostic, indent=2, sort_keys=True))
    return {
        "format": FORMAT,
        "version": 1,
        "id": "c2-lite-complete-media-varied-double-build",
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
        "builds": [{
            key: build[key] for key in (
                "id", "clone", "commands", "environment",
                "artifact_set_sha256", "product_build_id",
                "profile_build_id", "candidate_manifest_sha256",
            )
        } for build in builds],
        "artifact_count": 19,
        "artifact_set_sha256": first["artifact_set_sha256"],
        "product_build_id": first["product_build_id"],
        "profile_build_id": first["profile_build_id"],
        "product_artifacts": first["artifacts"],
        "tool_bindings": first["tool_bindings"],
        "result":
            "byte-identical-complete-C2-lite-media-set-across-varied-clones",
        "claims": {
            "Fresh-Clone": "passed",
            "R4": "not-run",
            "R5": "not-run",
            "R6": "not-run",
            "G5": "not-run",
            "G6": "not-run",
            "release_effect": "none",
        },
    }


def lower_sha(value: Any, label: str) -> str:
    require(
        isinstance(value, str) and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{label} is not a lowercase SHA-256")
    return value


def validate(value: dict[str, Any]) -> None:
    required = {
        "format", "version", "id", "status", "measured_on",
        "source_commit", "generator", "variation_axes", "builds",
        "artifact_count", "artifact_set_sha256", "product_build_id",
        "profile_build_id", "product_artifacts", "tool_bindings",
        "result", "claims",
    }
    require(set(value) == required, "C2-lite reproducibility schema drift")
    require(
        value["format"] == FORMAT and value["version"] == 1
        and value["id"] == "c2-lite-complete-media-varied-double-build"
        and value["status"] == "passed"
        and value["artifact_count"] == 19
        and value["result"]
            == "byte-identical-complete-C2-lite-media-set-across-varied-clones"
        and value["claims"] == {
            "Fresh-Clone": "passed", "R4": "not-run",
            "R5": "not-run", "R6": "not-run", "G5": "not-run",
            "G6": "not-run", "release_effect": "none",
        },
        "C2-lite reproducibility identity/result drift")
    require(
        isinstance(value["source_commit"], str)
        and len(value["source_commit"]) == 40,
        "C2-lite reproducibility source commit drift")
    require(value["variation_axes"] == [
        "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
        "timezone-and-calendar-date",
    ], "C2-lite reproducibility axes drift")
    generator = value["generator"]
    require(
        isinstance(generator, dict)
        and set(generator) == {"path", "bytes", "sha256"}
        and generator["path"] == GENERATOR.relative_to(ROOT).as_posix()
        and type(generator["bytes"]) is int and generator["bytes"] > 0,
        "C2-lite reproducibility generator binding drift")
    lower_sha(generator["sha256"], "generator.sha256")
    artifact_set = lower_sha(
        value["artifact_set_sha256"], "artifact_set_sha256")
    for label in ("product_build_id", "profile_build_id"):
        require(
            isinstance(value[label], str) and len(value[label]) == 8
            and all(character in "0123456789abcdef"
                    for character in value[label]),
            f"{label} drift")
    rows = value["product_artifacts"]
    require(
        isinstance(rows, list) and len(rows) == 19,
        "C2-lite reproducibility artifact inventory drift")
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and set(row) == {"role", "name", "path", "bytes", "sha256"}
            and type(row["bytes"]) is int and row["bytes"] > 0,
            f"product_artifacts[{index}] schema drift")
        lower_sha(row["sha256"], f"product_artifacts[{index}].sha256")
    require(
        {row["role"] for row in rows} == ROLE_SET
        and artifact_set_sha(rows) == artifact_set,
        "C2-lite reproducibility aggregate identity drift")
    tools = value["tool_bindings"]
    require(
        isinstance(tools, list) and len(tools) == 5,
        "C2-lite reproducibility tool binding drift")
    for index, row in enumerate(tools):
        require(
            isinstance(row, dict)
            and set(row) == {"name", "bytes", "sha256"}
            and type(row["bytes"]) is int and row["bytes"] > 0,
            f"tool_bindings[{index}] schema drift")
        lower_sha(row["sha256"], f"tool_bindings[{index}].sha256")
    builds = value["builds"]
    require(
        isinstance(builds, list) and len(builds) == 2,
        "C2-lite reproducibility requires two builds")
    expected_commands = [" ".join(command) for command in BUILD_COMMANDS]
    environments = []
    for index, build in enumerate(builds):
        require(
            isinstance(build, dict)
            and set(build) == {
                "id", "clone", "commands", "environment",
                "artifact_set_sha256", "product_build_id",
                "profile_build_id", "candidate_manifest_sha256",
            }
            and build["clone"] == "fresh-no-local-detached"
            and build["commands"] == expected_commands,
            f"builds[{index}] isolation/command drift")
        for key in (
            "artifact_set_sha256", "product_build_id",
            "profile_build_id",
        ):
            require(
                build[key] == value[key],
                f"builds[{index}] identity drift: {key}")
        lower_sha(
            build["candidate_manifest_sha256"],
            f"builds[{index}].candidate_manifest_sha256")
        environment = build["environment"]
        require(
            isinstance(environment, dict)
            and set(environment) == {
                "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
                "TZ", "calendar_date",
            },
            f"builds[{index}] environment drift")
        environments.append(environment)
    for key in (
            "PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date"):
        require(
            environments[0][key] != environments[1][key],
            f"C2-lite reproducibility axis did not vary: {key}")


def selftest() -> None:
    rows = [{
        "role": role,
        "name": f"{index:02d}.bin",
        "path": f"build/{index:02d}.bin",
        "bytes": index + 1,
        "sha256": f"{index + 1:064x}",
    } for index, role in enumerate(sorted(ROLE_SET))]
    common = {
        "artifact_set_sha256": artifact_set_sha(rows),
        "product_build_id": "12345678",
        "profile_build_id": "90abcdef",
    }
    build = {
        "id": "a",
        "clone": "fresh-no-local-detached",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1",
            "TZ": "A", "calendar_date": "2002-01-01",
        },
        "candidate_manifest_sha256": "a" * 64,
        **common,
    }
    fixture = {
        "format": FORMAT,
        "version": 1,
        "id": "c2-lite-complete-media-varied-double-build",
        "status": "passed",
        "measured_on": "2026-07-26",
        "source_commit": "0" * 40,
        "generator": {
            "path": GENERATOR.relative_to(ROOT).as_posix(),
            "bytes": 1, "sha256": "b" * 64,
        },
        "variation_axes": [
            "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
            "timezone-and-calendar-date",
        ],
        "builds": [build, deepcopy(build)],
        "artifact_count": 19,
        **common,
        "product_artifacts": rows,
        "tool_bindings": [{
            "name": name, "bytes": 1, "sha256": "c" * 64,
        } for name in ("clang-23", "lld", "llvm-link", "setarch", "c1541")],
        "result":
            "byte-identical-complete-C2-lite-media-set-across-varied-clones",
        "claims": {
            "Fresh-Clone": "passed", "R4": "not-run",
            "R5": "not-run", "R6": "not-run", "G5": "not-run",
            "G6": "not-run", "release_effect": "none",
        },
    }
    fixture["builds"][1]["id"] = "b"
    fixture["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2",
        "TZ": "B", "calendar_date": "2032-01-01",
    }
    validate(fixture)
    mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        ("status", lambda x: x.update(status="failed")),
        ("one-build", lambda x: x["builds"].pop()),
        ("same-seed", lambda x: x["builds"][1]["environment"].update(
            PYTHONHASHSEED="1")),
        ("artifact-set", lambda x: x.update(
            artifact_set_sha256="f" * 64)),
        ("claim", lambda x: x["claims"].update(R4="passed")),
        ("role", lambda x: x["product_artifacts"][0].update(
            role="unknown")),
    )
    survivors = []
    for name, mutate in mutations:
        changed = deepcopy(fixture)
        mutate(changed)
        try:
            validate(changed)
        except ReproError:
            continue
        survivors.append(name)
    require(not survivors, f"selftest accepted mutations: {survivors}")
    print(
        "c2-lite-product-reproducibility: SELFTEST PASS "
        f"mutations={len(mutations)} roles=19")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--source-commit", required=True)
    generate.add_argument("--measured-on", required=True)
    generate.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    check = sub.add_parser("check")
    check.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
            return 0
        path = args.output if args.action == "generate" else args.receipt
        if not path.is_absolute():
            path = ROOT / path
        if args.action == "generate":
            value = build_receipt(args.source_commit, args.measured_on)
            validate(value)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical(value))
            print(
                "c2-lite-product-reproducibility: WROTE "
                f"builds=2 artifacts=19 set={value['artifact_set_sha256']} "
                f"output={path.relative_to(ROOT)}")
        else:
            value = load(path, "C2-lite reproducibility receipt")
            validate(value)
            generator = value["generator"]
            require(
                GENERATOR.is_file() and not GENERATOR.is_symlink()
                and GENERATOR.stat().st_size == generator["bytes"]
                and sha(GENERATOR) == generator["sha256"],
                "live C2-lite reproducibility generator binding drift")
            print(
                "c2-lite-product-reproducibility: PASS "
                f"builds=2 artifacts=19 set={value['artifact_set_sha256']}")
        return 0
    except (
        ReproError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-lite-product-reproducibility: FIRST RED: " + str(error),
            file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
