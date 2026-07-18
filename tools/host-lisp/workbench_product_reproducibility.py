#!/usr/bin/env python3
"""Prove the canonical Workbench product across varied fresh-clone builds."""

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
GENERATOR = ROOT / "tools/host-lisp/workbench_product_reproducibility.py"
DEFAULT_RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/r3/"
    "canonical-product-reproducibility-receipt.json"
)
FORMAT = "lisp65-workbench-product-reproducibility-v1"
BUILD_COMMAND = ["make", "-s", "workbench-overlay-stack-guard"]
AXES = (
    {
        "id": "fresh-clone-seed-1-pago-pago-2000",
        "PYTHONHASHSEED": "1",
        "SOURCE_DATE_EPOCH": "946684800",
        "TZ": "Pacific/Pago_Pago",
    },
    {
        "id": "fresh-clone-seed-987654321-kiritimati-2030",
        "PYTHONHASHSEED": "987654321",
        "SOURCE_DATE_EPOCH": "1893456000",
        "TZ": "Pacific/Kiritimati",
    },
)
ARTIFACTS = (
    (
        "product-elf",
        "build/products/workbench/overlay-stack-guard/"
        "lisp65-workbench-overlay-linked.prg.elf",
    ),
    (
        "resident-prg",
        "build/products/workbench/overlay-stack-guard/"
        "lisp65-workbench-resident.prg",
    ),
    (
        "runtime-overlays",
        "build/products/workbench/overlay-stack-guard/"
        "lisp65-mvp-workbench.overlays.bin",
    ),
    (
        "stdlib-preload",
        "build/products/workbench/overlay-stack-guard/"
        "stdlib-with-overlay.ext.bin",
    ),
    (
        "resolved-profile",
        "build/products/workbench/overlay-stack-guard/resolved-profile.txt",
    ),
    ("library-ide", "build/bytecode/dialect-v2/libs/ide.ext.bin"),
    ("library-idex", "build/bytecode/dialect-v2/libs/idex.ext.bin"),
    ("library-m65d", "build/bytecode/dialect-v2/libs/m65d.ext.bin"),
)
IDENTITY_IDS = ("product-elf", "resident-prg", "runtime-overlays", "stdlib-preload")


class ReproError(RuntimeError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None, label: str) -> str:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-80:])
        raise ReproError(f"{label} failed ({result.returncode}):\n{tail}")
    return result.stdout


def full_commit(value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    commit = result.stdout.strip() if result.returncode == 0 else ""
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ReproError(f"invalid source commit: {value!r}")
    return commit


def artifact_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact_id, relative in ARTIFACTS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ReproError(f"missing product artifact {artifact_id}: {path}")
        rows.append(
            {
                "id": artifact_id,
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha_file(path),
            }
        )
    return rows


def product_sha(rows: list[dict[str, Any]]) -> str:
    by_id = {row["id"]: row for row in rows}
    payload = "".join(
        f"{artifact_id}:{by_id[artifact_id]['sha256']}\n"
        for artifact_id in IDENTITY_IDS
    )
    return sha_bytes(payload.encode("ascii"))


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "id": row["id"],
            "path": row["path"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }
        for row in rows
    ]
    return sha_bytes(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode())


def metrics(root: Path) -> dict[str, Any]:
    path = root / "build/products/workbench/overlay-stack-guard/footprint-audit.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproError(f"cannot read footprint audit: {exc}") from exc
    expected = {
        "overlay_vma": f"0x{value['overlay_base']:04x}",
        "post_boot_reserve_bytes": value["post_boot_reserve"],
        "banked_headroom_bytes": value["post_boot_reserve"] - 1536,
        "boot_stack_gap_bytes": value["boot_stack_gap"],
        "runtime_stack_gap_bytes": value["runtime_stack_gap"],
        "resident_file_end": value["resident_file_end"],
    }
    if value.get("status") != "pass" or expected["banked_headroom_bytes"] < 0:
        raise ReproError("fresh product footprint is not release-budget clean")
    return expected


def toolchain_binding() -> dict[str, Any]:
    path = ROOT / "tools/llvm-mos/bin/clang-23"
    if path.is_symlink() or not path.is_file():
        raise ReproError(f"missing bound compiler: {path}")
    return {
        "path": "tools/llvm-mos/bin/clang-23",
        "bytes": path.stat().st_size,
        "sha256": sha_file(path),
    }


def build_one(parent: Path, commit: str, axis: dict[str, str]) -> dict[str, Any]:
    checkout = parent / axis["id"]
    clone_env = os.environ.copy()
    clone_env["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(
        ["git", "clone", "--no-local", "--no-checkout", str(ROOT), str(checkout)],
        cwd=parent,
        env=clone_env,
        label=f"clone {axis['id']}",
    )
    run(
        ["git", "checkout", "--detach", commit],
        cwd=checkout,
        env=clone_env,
        label=f"checkout {axis['id']}",
    )
    toolchain = checkout / "tools/llvm-mos"
    toolchain.symlink_to(ROOT / "tools/llvm-mos", target_is_directory=True)
    environment = os.environ.copy()
    environment.update({key: axis[key] for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")})
    run(BUILD_COMMAND, cwd=checkout, env=environment, label=f"build {axis['id']}")
    rows = artifact_rows(checkout)
    epoch = int(axis["SOURCE_DATE_EPOCH"])
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached",
        "command": " ".join(BUILD_COMMAND),
        "environment": {
            "PYTHONHASHSEED": axis["PYTHONHASHSEED"],
            "SOURCE_DATE_EPOCH": axis["SOURCE_DATE_EPOCH"],
            "TZ": axis["TZ"],
            "calendar_date": datetime.fromtimestamp(epoch, ZoneInfo(axis["TZ"])).date().isoformat(),
        },
        "product_sha256": product_sha(rows),
        "artifact_set_sha256": artifact_set_sha(rows),
        "metrics": metrics(checkout),
        "artifacts": rows,
    }


def build_receipt(source_commit: str, measured_on: str) -> dict[str, Any]:
    commit = full_commit(source_commit)
    with tempfile.TemporaryDirectory(prefix="lisp65-product-repro-") as raw:
        parent = Path(raw)
        builds = [build_one(parent, commit, axis) for axis in AXES]
    first, second = builds
    if (
        first["artifacts"] != second["artifacts"]
        or first["product_sha256"] != second["product_sha256"]
        or first["artifact_set_sha256"] != second["artifact_set_sha256"]
        or first["metrics"] != second["metrics"]
    ):
        raise ReproError("varied fresh-clone product builds diverged")
    return {
        "format": FORMAT,
        "version": 1,
        "id": "canonical-workbench-varied-double-build",
        "status": "passed",
        "measured_on": measured_on,
        "source_commit": commit,
        "generator": {
            "path": GENERATOR.relative_to(ROOT).as_posix(),
            "bytes": GENERATOR.stat().st_size,
            "sha256": sha_file(GENERATOR),
        },
        "toolchain": toolchain_binding(),
        "variation_axes": [
            "fresh-clone",
            "PYTHONHASHSEED",
            "SOURCE_DATE_EPOCH",
            "timezone-and-calendar-date",
        ],
        "builds": [
            {key: build[key] for key in (
                "id", "clone", "command", "environment", "product_sha256",
                "artifact_set_sha256", "metrics",
            )}
            for build in builds
        ],
        "product_sha256": first["product_sha256"],
        "artifact_set_sha256": first["artifact_set_sha256"],
        "metrics": first["metrics"],
        "product_artifacts": first["artifacts"],
        "result": "byte-identical-across-varied-environments",
    }


def _sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReproError(f"{label} is not a lowercase SHA-256")
    return value


def validate(receipt: dict[str, Any]) -> None:
    keys = {
        "format", "version", "id", "status", "measured_on", "source_commit",
        "generator", "toolchain", "variation_axes", "builds", "product_sha256",
        "artifact_set_sha256", "metrics", "product_artifacts", "result",
    }
    if not isinstance(receipt, dict) or set(receipt) != keys:
        raise ReproError("reproducibility receipt schema drift")
    if (
        receipt["format"] != FORMAT
        or receipt["version"] != 1
        or receipt["id"] != "canonical-workbench-varied-double-build"
        or receipt["status"] != "passed"
        or receipt["result"] != "byte-identical-across-varied-environments"
    ):
        raise ReproError("reproducibility receipt identity/result drift")
    if not isinstance(receipt["source_commit"], str) or len(receipt["source_commit"]) != 40:
        raise ReproError("reproducibility source commit drift")
    if receipt["variation_axes"] != [
        "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
        "timezone-and-calendar-date",
    ]:
        raise ReproError("reproducibility variation axes drift")
    generator = receipt["generator"]
    if (
        not isinstance(generator, dict)
        or set(generator) != {"path", "bytes", "sha256"}
        or generator["path"] != "tools/host-lisp/workbench_product_reproducibility.py"
        or type(generator["bytes"]) is not int
        or generator["bytes"] <= 0
    ):
        raise ReproError("reproducibility generator binding drift")
    _sha(generator["sha256"], "generator.sha256")
    rows = receipt["product_artifacts"]
    if (
        not isinstance(rows, list)
        or [row.get("id") for row in rows] != [item[0] for item in ARTIFACTS]
        or [row.get("path") for row in rows] != [item[1] for item in ARTIFACTS]
    ):
        raise ReproError("reproducibility artifact inventory drift")
    for index, row in enumerate(rows):
        if set(row) != {"id", "path", "bytes", "sha256"}:
            raise ReproError(f"product_artifacts[{index}] schema drift")
        if type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ReproError(f"product_artifacts[{index}] size drift")
        _sha(row["sha256"], f"product_artifacts[{index}].sha256")
    product = _sha(receipt["product_sha256"], "product_sha256")
    artifact_set = _sha(receipt["artifact_set_sha256"], "artifact_set_sha256")
    if product != product_sha(rows) or artifact_set != artifact_set_sha(rows):
        raise ReproError("reproducibility aggregate identity drift")
    builds = receipt["builds"]
    if not isinstance(builds, list) or len(builds) != 2:
        raise ReproError("reproducibility requires exactly two builds")
    environments: list[dict[str, str]] = []
    for index, build in enumerate(builds):
        if set(build) != {
            "id", "clone", "command", "environment", "product_sha256",
            "artifact_set_sha256", "metrics",
        }:
            raise ReproError(f"builds[{index}] schema drift")
        if build["clone"] != "fresh-no-local-detached" or build["command"] != " ".join(BUILD_COMMAND):
            raise ReproError(f"builds[{index}] isolation/command drift")
        if (
            build["product_sha256"] != product
            or build["artifact_set_sha256"] != artifact_set
            or build["metrics"] != receipt["metrics"]
        ):
            raise ReproError(f"builds[{index}] result drift")
        environment = build["environment"]
        if not isinstance(environment, dict) or set(environment) != {
            "PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date",
        }:
            raise ReproError(f"builds[{index}] environment drift")
        environments.append(environment)
    for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date"):
        if environments[0][key] == environments[1][key]:
            raise ReproError(f"reproducibility axis did not vary: {key}")
    toolchain = receipt["toolchain"]
    if not isinstance(toolchain, dict) or set(toolchain) != {"path", "bytes", "sha256"}:
        raise ReproError("reproducibility toolchain binding drift")
    _sha(toolchain["sha256"], "toolchain.sha256")


def load_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproError(f"cannot read reproducibility receipt: {exc}") from exc
    if not isinstance(value, dict):
        raise ReproError("reproducibility receipt must be an object")
    return value


def selftest() -> None:
    rows = [
        {"id": artifact_id, "path": path, "bytes": index + 1, "sha256": sha_bytes(path.encode())}
        for index, (artifact_id, path) in enumerate(ARTIFACTS)
    ]
    product = product_sha(rows)
    artifact_set = artifact_set_sha(rows)
    build = {
        "id": "a",
        "clone": "fresh-no-local-detached",
        "command": " ".join(BUILD_COMMAND),
        "environment": {
            "PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1",
            "TZ": "A", "calendar_date": "2000-01-01",
        },
        "product_sha256": product,
        "artifact_set_sha256": artifact_set,
        "metrics": {"banked_headroom_bytes": 1},
    }
    fixture = {
        "format": FORMAT, "version": 1,
        "id": "canonical-workbench-varied-double-build", "status": "passed",
        "measured_on": "2000-01-01", "source_commit": "0" * 40,
        "generator": {
            "path": "tools/host-lisp/workbench_product_reproducibility.py",
            "bytes": 1, "sha256": "2" * 64,
        },
        "toolchain": {"path": "tools/llvm-mos/bin/clang-23", "bytes": 1, "sha256": "1" * 64},
        "variation_axes": [
            "fresh-clone", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH",
            "timezone-and-calendar-date",
        ],
        "builds": [build, deepcopy(build)],
        "product_sha256": product, "artifact_set_sha256": artifact_set,
        "metrics": build["metrics"], "product_artifacts": rows,
        "result": "byte-identical-across-varied-environments",
    }
    fixture["builds"][1]["id"] = "b"
    fixture["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2",
        "TZ": "B", "calendar_date": "2030-01-01",
    }
    validate(fixture)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("status", lambda x: x.update(status="failed")),
        ("same seed", lambda x: x["builds"][1]["environment"].update(PYTHONHASHSEED="1")),
        ("product", lambda x: x.update(product_sha256="f" * 64)),
        ("artifact", lambda x: x["product_artifacts"][0].update(bytes=0)),
        ("clone", lambda x: x["builds"][0].update(clone="live-tree")),
        ("one build", lambda x: x["builds"].pop()),
    ]
    failures = 0
    for label, mutate in mutations:
        candidate = deepcopy(fixture)
        mutate(candidate)
        try:
            validate(candidate)
        except ReproError:
            continue
        print(f"workbench-product-repro selftest mutation survived: {label}", file=sys.stderr)
        failures += 1
    if failures:
        raise ReproError(f"selftest failures={failures}")
    print(f"workbench-product-repro: SELFTEST PASS mutations={len(mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--source-commit", required=True)
    generate.add_argument("--measured-on", required=True)
    generate.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    check = sub.add_parser("check")
    check.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
            return 0
        receipt_path = args.receipt if hasattr(args, "receipt") else args.output
        if not receipt_path.is_absolute():
            receipt_path = ROOT / receipt_path
        if args.command == "generate":
            receipt = build_receipt(args.source_commit, args.measured_on)
            validate(receipt)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(canonical(receipt))
            print(
                "workbench-product-repro: WROTE "
                f"product={receipt['product_sha256']} set={receipt['artifact_set_sha256']}"
            )
            return 0
        expected = load_receipt(receipt_path)
        validate(expected)
        generator = expected["generator"]
        generator_path = ROOT / generator["path"]
        if (
            generator_path.is_symlink()
            or not generator_path.is_file()
            or generator_path.stat().st_size != generator["bytes"]
            or sha_file(generator_path) != generator["sha256"]
        ):
            raise ReproError("live reproducibility generator binding drift")
        if args.command == "preflight":
            observed = build_receipt(expected["source_commit"], expected["measured_on"])
            if canonical(observed) != canonical(expected):
                raise ReproError("varied double-build receipt drift")
        print(
            f"workbench-product-repro: PASS mode={args.command} "
            f"product={expected['product_sha256']} builds=2"
        )
        return 0
    except (ReproError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"workbench-product-repro: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
