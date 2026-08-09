#!/usr/bin/env python3
"""Build the selected v1.4 product and Base library from public source only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v112_candidate_media as MEDIA  # noqa: E402
import c2_v112_candidate_product as PRODUCT  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.4.0-public-selected"
MANIFEST = BUILD / "candidate-manifest.json"
FREIGHT = BUILD / "public-source-freight.json"
BASE = ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5-split/base"
STRING_PREFIX = ROOT / "build/post-promotion/v112/string-extra/string-extra"
INSPECT_PREFIX = ROOT / "build/post-promotion/v112/inspect/inspect"
EXPECTED_BASE_D81 = (
    819200,
    "1a77a2f5d71c58ef8e9650316d7d0103675fd419b5aa96d37e8f44e7b24186b7",
)


class PublicBuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PublicBuildError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def emit_library(suite: str, prefix: Path) -> dict[str, Any]:
    suite_path = ROOT / suite
    value = STD._read_suite(str(suite_path))
    STD.check_suite(str(suite_path), value)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    STD.emit_artifacts(
        str(suite_path), value, str(prefix), base_addr=0,
        artifact_role="disk-lib",
    )
    return load(prefix.with_suffix(".manifest.json"))


def prepare_source_freight() -> dict[str, Any]:
    string = emit_library("tests/bytecode/libs/p0-string-extra.json", STRING_PREFIX)
    inspect = emit_library("tests/bytecode/libs/p0-inspect.json", INSPECT_PREFIX)
    string_names = {row["name"] for row in string["entries"]}
    inspect_names = {row["name"] for row in inspect["entries"]}
    require(
        {"capitalize", "string-split"}.issubset(string_names)
        and "who-calls" in inspect_names
        and not {"trace", "untrace"}.intersection(inspect_names),
        "selected public library surface drift",
    )
    value = {
        "format": "lisp65-v1.4-public-source-freight-v1",
        "status": "passed-host-integrated-release-freight",
        "public_source_projection": "selected-base-no-private-evidence",
        "private_evidence_inputs": 0,
        "selector": "base",
        "public_names": ["capitalize", "string-split", "who-calls"],
        "resident_delta_bytes": 0,
        "bank2": {"resident_delta_bytes": 0},
        "string_extra": bind(STRING_PREFIX.with_suffix(".manifest.json")),
        "inspect": bind(INSPECT_PREFIX.with_suffix(".manifest.json")),
    }
    FREIGHT.parent.mkdir(parents=True, exist_ok=True)
    FREIGHT.write_bytes(canonical(value))
    return value


def source_freight_gates() -> dict[str, Any]:
    # The inherited v1.3 public gate validates the *current* tracked profile
    # against its caller-bound identity.  The normal v1.4 configure path
    # performs this rebinding later, after freight gates.  Bind only those
    # two expected identities here so the predecessor checks the accepted
    # Link-92 profile rather than its historical Link-88 constants.
    PRODUCT.P.EXPECTED_PRODUCT_ID = PRODUCT.EXPECTED_PRODUCT_ID
    PRODUCT.P.EXPECTED_BANK2_SHA = PRODUCT.EXPECTED_BANK2_SHA
    inherited = PRODUCT.LINK88.freight_gates()
    value = load(FREIGHT)
    require(
        value.get("status") == "passed-host-integrated-release-freight"
        and value.get("public_source_projection")
            == "selected-base-no-private-evidence"
        and value.get("private_evidence_inputs") == 0
        and value.get("selector") == "base"
        and value.get("resident_delta_bytes") == 0,
        "public-source freight projection drift",
    )
    return {
        "mode": "v1.4-public-source-selected-base",
        "private_evidence_inputs": 0,
        "inherited_public_current_source": inherited,
        "summaries": {
            **inherited["summaries"],
            "source_freight": "passed",
        },
        "release_freight": bind(FREIGHT),
    }


def emit_inherited_manifests() -> dict[str, Any]:
    # This callback runs before the inherited product configurator rebinds
    # the two promoted roles.  Project those two current v1.4 carriers by
    # identity; the other four roles already name their canonical sources.
    specs = tuple(
        (
            key,
            name,
            PRODUCT.RELEASE_STDLIB
            if key == "stdlib-p0"
            else PRODUCT.P.IDE
            if key == "ide"
            else PRODUCT.PROMOTED_PREFIX.with_suffix(".manifest.json")
            if key == "lcc"
            else path,
        )
        for key, name, path in PRODUCT.CAN.SPECS
    )
    require(
        len(specs) == 6
        and {key for key, _name, _path in specs}
            == {"stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc"}
        and all(path.is_file() for _key, _name, path in specs),
        "v1.4 current-source manifest inventory incomplete",
    )
    return {
        "status": "passed-six-source-emitted-predecessor-manifests",
        "selection": "v1.4-selected-base-current-source",
        "manifests": [bind(path) for _key, _name, path in specs],
    }


def configure_product() -> None:
    # Every inherited freight gate must rebuild its authority from public
    # current sources.  Set this at the outermost v1.4 entrypoint so deep
    # predecessor gates cannot fall back to proof-worktree receipts merely
    # because their immediate caller did not need to inspect the mode.
    os.environ["LISP65_PUBLIC_CURRENT_SOURCE_BUILD"] = "1"
    PRODUCT.FREIGHT = FREIGHT
    PRODUCT.complete_in_fresh_process = complete_in_fresh_process
    PRODUCT.freight_gates = source_freight_gates
    PRODUCT.P.emit_inherited_manifests = emit_inherited_manifests
    PRODUCT.P.PRODUCT.emit_inherited_manifests = emit_inherited_manifests


def complete_in_fresh_process() -> None:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "complete"],
        cwd=ROOT, env={**os.environ, **PRODUCT.CAN.canonical_build_environment()},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, "public completion failed:\n" + result.stdout)


def complete() -> None:
    configure_product()
    PRODUCT.bind_inherited_entrypoint()
    result = PRODUCT.P.PRODUCT.complete_action()
    require(result == 0, "public-source product completion failed")


def profile() -> None:
    configure_product()
    PRODUCT.profile()


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def build_media() -> dict[str, Any]:
    require(PRODUCT.BUILD.is_dir() and not MANIFEST.exists(),
            "v1.4 public media build is one-shot after product completion")
    MEDIA.VARIANTS = {
        "base": (
            ("string-extra", "strx", "strextr",
             STRING_PREFIX.with_suffix(".manifest.json"), ()),
            ("inspect", "inspect", "inspect",
             INSPECT_PREFIX.with_suffix(".manifest.json"), ()),
        ),
    }
    MEDIA.configure_shared()
    shared = MEDIA.MEDIA.build()
    MEDIA.MEDIA.check()
    base = MEDIA.build_library_variant(
        "base", BASE, MEDIA.product_build_id())
    require(
        (base["D81"]["bytes"], base["D81"]["sha256"])
        == EXPECTED_BASE_D81,
        "fresh public Base library differs from Halt-1 selection",
    )

    rows = [dict(row) for row in shared["artifacts"]]
    additions = (
        ("optional-library-d81", BASE / "lisp65-library.d81"),
        ("optional-library-index", BASE / "l65index"),
        ("library-string-extra", BASE / "string-extra.l65s"),
        ("library-inspect", BASE / "inspect.l65s"),
    )
    for role, path in additions:
        row = bind(path)
        rows.append({"role": role, "name": path.name, **row})
    require(len(rows) == 23 and len({row["role"] for row in rows}) == 23,
            "selected public artifact inventory drift")
    value = {
        "format": "lisp65-v1.4-public-selected-product-v1",
        "status": "passed-public-source-selected-base-product",
        "artifact_count": len(rows),
        "artifact_set_sha256": artifact_set(rows),
        "product_build_id": shared["product_build_id"],
        "profile_build_id": shared["profile_build_id"],
        "private_evidence_inputs": 0,
        "selector": "base",
        "artifacts": rows,
    }
    BUILD.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_bytes(canonical(value))
    check()
    return value


def build() -> dict[str, Any]:
    require(not PRODUCT.BUILD.exists() and not BUILD.exists(),
            "v1.4 public build is one-shot")
    generated = subprocess.run(
        ["make", "--no-print-directory", "v2-workbench-artifacts",
         "bytecode-p0-buffer-lib-artifacts", "fasl-emit-check",
         "equivalence-check"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(generated.returncode == 0,
            "public workbench source generation failed:\n" + generated.stdout)
    require(
        (ROOT / "build/equivalence/equivalence-check").is_file(),
        "public equivalence binary generation did not materialize its output",
    )
    carrier = subprocess.run(
        [sys.executable,
         str(ROOT / "tools/host-lisp/c2_v130_static_input_carrier.py"),
         "materialize"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(carrier.returncode == 0,
            "public static input carrier failed:\n" + carrier.stdout)
    prepare_source_freight()
    configure_product()
    profile_run = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "profile"],
        cwd=ROOT, env=os.environ.copy(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(profile_run.returncode == 0,
            "public linker-free profile failed:\n" + profile_run.stdout)
    require(PRODUCT.product("build") == 0, "v1.4 public product build failed")
    media_run = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "media"],
        cwd=ROOT, env=os.environ.copy(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(media_run.returncode == 0,
            "public selected media build failed:\n" + media_run.stdout)
    return check()


def check() -> dict[str, Any]:
    value = load(MANIFEST)
    rows = value.get("artifacts", [])
    require(
        value.get("format") == "lisp65-v1.4-public-selected-product-v1"
        and value.get("status") == "passed-public-source-selected-base-product"
        and value.get("private_evidence_inputs") == 0
        and value.get("selector") == "base"
        and value.get("artifact_count") == len(rows) == 23
        and artifact_set(rows) == value.get("artifact_set_sha256"),
        "selected public manifest drift",
    )
    for row in rows:
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink()
                and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"selected public artifact drift: {row.get('role')}")
    return value


def clean() -> None:
    for path in (
        PRODUCT.BUILD, PRODUCT.PREFLIGHT,
        ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5",
        ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5-split",
        BUILD,
    ):
        if path.exists():
            require(path.is_dir() and path.resolve().is_relative_to(
                (ROOT / "build").resolve()), "clean path escaped build")
            shutil.rmtree(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("build", "check", "complete", "profile", "media", "clean"),
    )
    action = parser.parse_args().action
    try:
        if action == "build":
            value = build()
        elif action == "check":
            value = check()
        elif action == "complete":
            complete()
            return 0
        elif action == "profile":
            profile()
            return 0
        elif action == "media":
            value = build_media()
        else:
            clean()
            print("c2-v140-public-product: CLEAN")
            return 0
        print(
            "c2-v140-public-product: PASS "
            f"roles={value['artifact_count']} set={value['artifact_set_sha256']}"
        )
        return 0
    except (PublicBuildError, PRODUCT.CandidateError, MEDIA.MediaClosureError,
            RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v140-public-product: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
