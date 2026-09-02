#!/usr/bin/env python3
"""Create deterministic, self-contained promotion archives and verify the live register."""

from __future__ import annotations

import argparse
import functools
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

import block_capacity_delta_policy as CAPACITY_DELTA
import c2_lite_product_reproducibility as C2_LITE_REPRO
import evidence_archive_assets as ARCHIVE_ASSETS
import promotion_archive_offline as OFFLINE_VERIFY
import remote_source_binding as REMOTE_BINDING
import r3_product_reproducibility as R3_REPRO
import workbench_product_reproducibility as WORKBENCH_REPRO


ROOT = Path(__file__).resolve().parents[2]
OFFLINE = ROOT / "tools" / "host-lisp" / "promotion_archive_offline.py"
REGISTER = ROOT / "config" / "promotion-register.json"
R4_ASSERTIONS = ROOT / "config" / "r4-product-candidate-contract.json"
R5_CONTRACT = ROOT / "config" / "r5-global-g5-contract.json"
POLICY_FORMAT = "lisp65-promotion-archive-policy-v4"
REGISTER_FORMAT = "lisp65-promotion-register-v1"
SHA_KEYS = {"sha256", "receipt_sha256", "contract_sha256"}
PRODUCT_ARTIFACT_COUNT = 14


class ArchiveError(RuntimeError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise ArchiveError(f"invalid repository path: {value!r}")
    return value


def git_bytes(commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return result.stdout if result.returncode == 0 else None


@functools.lru_cache(maxsize=None)
def nested_archive_payloads(archive_path: Path) -> dict[str, bytes]:
    """Read an immutable nested evidence archive once per seal process."""
    result: dict[str, bytes] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            if stream is not None:
                result[member.name] = stream.read()
    return result


def source_bytes(commit: str, path: str, expected: str | None = None) -> bytes:
    path = repo_path(path)
    candidates: list[bytes] = []
    committed = git_bytes(commit, path)
    if committed is not None:
        candidates.append(committed)
    live = ROOT / path
    if live.is_file() and not live.is_symlink():
        candidates.append(live.read_bytes())
    nested_archives = [
        ROOT / "tests/bytecode/dialect-v2/evidence/capability-carrier/"
        "cp5-g5-67400c05/evidence.tar.gz",
    ]
    for archive_path in nested_archives:
        if not archive_path.is_file():
            continue
        archived = nested_archive_payloads(archive_path).get(path)
        if archived is not None:
            candidates.append(archived)
    for data in candidates:
        if expected is None or sha_bytes(data) == expected:
            return data
    observed = [sha_bytes(data) for data in candidates]
    raise ArchiveError(
        f"cannot materialize bound file {path} at {commit}: "
        f"expected={expected} observed={observed}"
    )


def reproducibility_bytes(commit: str, path: str) -> tuple[bytes, dict[str, Any]]:
    """Select the committed/live receipt that actually binds the promotion cut."""
    candidates: list[bytes] = []
    committed = git_bytes(commit, path)
    if committed is not None:
        candidates.append(committed)
    live = ROOT / path
    if live.is_file() and not live.is_symlink():
        candidates.append(live.read_bytes())
    matches: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for data in candidates:
        try:
            value = json.loads(data)
            receipt_format = value.get("format") if isinstance(value, dict) else None
            if receipt_format == WORKBENCH_REPRO.FORMAT:
                WORKBENCH_REPRO.validate(value)
            elif receipt_format == R3_REPRO.FORMAT:
                R3_REPRO.validate(value)
            elif receipt_format == C2_LITE_REPRO.FORMAT:
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.2.1-media-product-"
                "reproducibility-v1"
            ):
                # The release-candidate wrapper configures the shared
                # validator with its isolated build commands, generator and
                # media path.  Import it only for this receipt format so the
                # historical canonical-product validator remains unchanged.
                import c2_v121_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.2.2-media-product-"
                "reproducibility-v1"
            ):
                # v1.2.2 uses the same complete 19-role schema with its own
                # isolated source builder and media path.  Select the wrapper
                # by the receipt's declared format; do not reinterpret it as
                # a historical v1.2.1 candidate.
                import c2_v122_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.2.3-media-product-"
                "reproducibility-v1"
            ):
                # v1.2.3 keeps the complete 19-role schema and selects the
                # Link-80 single-emitter/media wrapper.
                import c2_v123_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.2.4-media-product-"
                "reproducibility-v1"
            ):
                # v1.2.4 binds the Link-81 fx/time product and retains the
                # complete 19-role media schema.
                import c2_v124_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.2.5-media-product-"
                "reproducibility-v1"
            ):
                # v1.2.5 binds the Link-82 require Option-A correction while
                # retaining the complete 19-role media schema.
                import c2_v125_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            elif receipt_format == (
                "lisp65-c2-lite-v1.3.0-media-product-"
                "reproducibility-v1"
            ):
                # v1.3.0 binds the Link-88 Ship/input/q/editor product and
                # retains the complete 19-role C2-lite media schema.
                import c2_v130_product_reproducibility  # noqa: F401
                C2_LITE_REPRO.validate(value)
            else:
                continue
        except (
            UnicodeError, json.JSONDecodeError,
            WORKBENCH_REPRO.ReproError, R3_REPRO.ReproError,
            C2_LITE_REPRO.ReproError,
        ):
            continue
        if value.get("source_commit") == commit:
            matches[sha_bytes(data)] = (data, value)
    if len(matches) != 1:
        raise ArchiveError(
            "cannot select exactly one reproducibility receipt bound to "
            f"promotion source commit {commit}: matches={sorted(matches)}"
        )
    return next(iter(matches.values()))


def bindings(value: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        path = value.get("path")
        digest = value.get("sha256")
        if isinstance(path, str) and isinstance(digest, str) and len(digest) == 64:
            found.append((path, digest))
        for key, candidate in value.items():
            paired_digest = value.get(f"{key}_sha256")
            if (
                isinstance(candidate, str)
                and "/" in candidate
                and isinstance(paired_digest, str)
                and len(paired_digest) == 64
            ):
                found.append((candidate, paired_digest))
        for child in value.values():
            found.extend(bindings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(bindings(child))
    return found


def collect(
    commit: str, roots: list[str], follow_roots: list[str],
) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    files = {path: source_bytes(commit, path) for path in roots}
    external: set[tuple[str, str]] = set()
    queue = list(follow_roots)
    seen: set[str] = set()
    while queue:
        path = repo_path(queue.pop(0))
        if path in seen:
            continue
        seen.add(path)
        data = files.get(path)
        if data is None:
            data = source_bytes(commit, path)
            files[path] = data
        if not path.endswith(".json"):
            continue
        try:
            value = json.loads(data)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ArchiveError(f"invalid JSON in closure: {path}: {exc}") from exc
        for child, digest in bindings(value):
            if PurePosixPath(child).is_absolute():
                external.add((child, digest))
                continue
            child = repo_path(child)
            if child in files and sha_bytes(files[child]) != digest:
                external.add((child, digest))
                continue
            if child not in files:
                try:
                    files[child] = source_bytes(commit, child, digest)
                except ArchiveError:
                    external.add((child, digest))
                    continue
            if child.endswith(".json") and child not in seen:
                queue.append(child)
    return files, [
        {"path": path, "sha256": digest}
        for path, digest in sorted(external)
    ]


def tar_member(name: str, data: bytes) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info, io.BytesIO(data)


def create(args: argparse.Namespace) -> None:
    assertions_path: str | None = None
    assertions_data: bytes | None = None
    if args.assertions_file is not None:
        assertions_path = repo_path(args.assertions_file)
        assertions_data = source_bytes(args.source_commit, assertions_path)
        assertions = json.loads(assertions_data)
    else:
        assertions = json.loads(args.assertions)
    if not isinstance(assertions, dict) or "capacity_delta" not in assertions:
        raise ArchiveError("future promotion assertions require capacity_delta")
    try:
        CAPACITY_DELTA.validate_policy()
        CAPACITY_DELTA.validate_capacity_delta(assertions["capacity_delta"])
    except CAPACITY_DELTA.CapacityDeltaError as exc:
        raise ArchiveError(f"promotion capacity delta is invalid: {exc}") from exc
    commit = subprocess.run(
        ["git", "rev-parse", f"{args.source_commit}^{{commit}}"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    source_commit = commit.stdout.strip() if commit.returncode == 0 else ""
    if source_commit != args.source_commit:
        raise ArchiveError("promotion source commit must be a full canonical commit")
    try:
        remote_binding = REMOTE_BINDING.capture(source_commit)
    except REMOTE_BINDING.RemoteBindingError as exc:
        raise ArchiveError(f"promotion source is not remotely bound: {exc}") from exc
    repro_path = repo_path(args.reproducibility_receipt)
    repro_data, repro = reproducibility_bytes(source_commit, repro_path)
    repro_format = repro["format"]
    product_paths = [repo_path(path) for path in args.product_artifact]
    expected_paths = [row["path"] for row in repro["product_artifacts"]]
    if product_paths != expected_paths:
        raise ArchiveError("product artifact arguments must exactly match the reproducibility receipt")

    capacity_policy = CAPACITY_DELTA.DEFAULT_POLICY.relative_to(ROOT).as_posix()
    capacity_roots = [capacity_policy]
    for dimension in assertions["capacity_delta"]["dimensions"].values():
        authorization = dimension["authorization"]
        if authorization is None:
            continue
        path = repo_path(authorization["path"])
        source_bytes(source_commit, path, authorization["sha256"])
        capacity_roots.append(path)
    files, external = collect(
        source_commit, [*args.root, *capacity_roots],
        [*args.follow, *capacity_roots],
    )
    if assertions_path is not None and assertions_data is not None:
        if assertions_path in files and files[assertions_path] != assertions_data:
            raise ArchiveError("assertions contract materialization drift")
        files[assertions_path] = assertions_data
    if repro_path in files and files[repro_path] != repro_data:
        # A sealed predecessor may bind an older receipt at the same live path.
        # R4 materializes the receipt for this cut and retains the predecessor
        # byte stream as an explicit immutable content binding.
        external.append({"path": repro_path, "sha256": sha_bytes(files[repro_path])})
    files[repro_path] = repro_data
    product_rows: list[dict[str, Any]] = []
    for row in repro["product_artifacts"]:
        data = source_bytes(source_commit, row["path"], row["sha256"])
        if len(data) != row["bytes"]:
            raise ArchiveError(f"product artifact size drift: {row['path']}")
        files[row["path"]] = data
        product_rows.append(dict(row))
    generator = repro["generator"]
    generator_data = source_bytes(source_commit, generator["path"], generator["sha256"])
    if len(generator_data) != generator["bytes"]:
        raise ArchiveError("reproducibility generator size drift")
    files[generator["path"]] = generator_data
    if repro_format == WORKBENCH_REPRO.FORMAT:
        toolchain = repro["toolchain"]
        toolchain_binding = (repo_path(toolchain["path"]), toolchain["sha256"])
        if toolchain_binding[0] not in files:
            external.append({"path": toolchain_binding[0], "sha256": toolchain_binding[1]})
    external = sorted(
        {row["path"] + "\0" + row["sha256"]: row for row in external}.values(),
        key=lambda row: (row["path"], row["sha256"]),
    )
    product_bindings = {(row["path"], row["sha256"]) for row in product_rows}
    if any((row["path"], row["sha256"]) in product_bindings for row in external):
        raise ArchiveError("promoted product bytes may not remain external bindings")
    rows = [
        {"path": path, "sha256": sha_bytes(data), "bytes": len(data)}
        for path, data in sorted(files.items())
    ]
    if repro_format == WORKBENCH_REPRO.FORMAT:
        product_materialization = {
            "reproducibility_receipt": repro_path,
            "reproducibility_receipt_sha256": sha_bytes(repro_data),
            "product_sha256": repro["product_sha256"],
            "artifact_set_sha256": repro["artifact_set_sha256"],
            "artifacts": product_rows,
        }
    elif repro_format == R3_REPRO.FORMAT:
        product_materialization = {
            "reproducibility_receipt": repro_path,
            "reproducibility_receipt_sha256": sha_bytes(repro_data),
            "reproducibility_format": R3_REPRO.FORMAT,
            "product_build_id": repro["product_build_id"],
            "artifact_set_sha256": repro["artifact_set_sha256"],
            "artifacts": product_rows,
        }
    else:
        product_materialization = {
            "reproducibility_receipt": repro_path,
            "reproducibility_receipt_sha256": sha_bytes(repro_data),
            "reproducibility_format": C2_LITE_REPRO.FORMAT,
            "product_build_id": repro["product_build_id"],
            "profile_build_id": repro["profile_build_id"],
            "artifact_set_sha256": repro["artifact_set_sha256"],
            "artifacts": product_rows,
        }
    manifest = {
        "format": "lisp65-promotion-archive-v3",
        "id": args.id,
        "kind": args.kind,
        "status": "sealed",
        "source_commit": args.source_commit,
        "remote_source_binding": remote_binding,
        "sealed_on": args.sealed_on,
        "immutability": "append-only-never-amend",
        "assertions": assertions,
        "assertions_source": (
            None if assertions_path is None or assertions_data is None else {
                "path": assertions_path,
                "sha256": sha_bytes(assertions_data),
            }
        ),
        "product_materialization": product_materialization,
        "files": rows,
        "external_content_bindings": external,
    }
    manifest_data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    offline_data = OFFLINE.read_bytes()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for name, data in (("manifest.json", manifest_data), ("verify.py", offline_data)):
                    info, stream = tar_member(name, data)
                    archive.addfile(info, stream)
                for path, data in sorted(files.items()):
                    info, stream = tar_member(f"payload/{path}", data)
                    archive.addfile(info, stream)
    print(
        f"promotion-archive: WROTE id={args.id} files={len(files)} "
        f"bytes={args.output.stat().st_size} sha256={sha_bytes(args.output.read_bytes())}"
    )


def isolated_verify(archive_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="promotion-archive-isolated-") as raw:
        directory = Path(raw)
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not member.isfile():
                    raise ArchiveError("unsafe/non-file archive member")
            archive.extractall(directory)
        result = subprocess.run(
            [sys.executable, "verify.py"], cwd=directory, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode:
            raise ArchiveError(f"isolated verification failed:\n{result.stdout}")
        print(result.stdout.strip())


def product_candidate_check() -> None:
    assertions = json.loads(R4_ASSERTIONS.read_text(encoding="utf-8"))
    repro = json.loads(R3_REPRO.DEFAULT_RECEIPT.read_text(encoding="utf-8"))
    try:
        R3_REPRO.validate(repro)
    except R3_REPRO.ReproError as exc:
        raise ArchiveError(f"invalid R3 reproducibility receipt: {exc}") from exc
    generator = repro["generator"]
    generator_path = ROOT / repo_path(generator["path"])
    if (
        generator_path.is_symlink() or not generator_path.is_file()
        or generator_path.stat().st_size != generator["bytes"]
        or sha_bytes(generator_path.read_bytes()) != generator["sha256"]
    ):
        raise ArchiveError("live R3 reproducibility generator binding drift")
    for row in repro["product_artifacts"]:
        path = ROOT / repo_path(row["path"])
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]
            or sha_bytes(path.read_bytes()) != row["sha256"]
        ):
            raise ArchiveError(f"live R4 product artifact drift: {row['path']}")
    manifest = {
        "product_materialization": {
            "artifact_set_sha256": repro["artifact_set_sha256"],
            "product_build_id": repro["product_build_id"],
            "artifacts": repro["product_artifacts"],
        },
    }
    saved_payload = OFFLINE_VERIFY.PAYLOAD
    try:
        OFFLINE_VERIFY.PAYLOAD = ROOT
        OFFLINE_VERIFY.verify_product_candidate(manifest, assertions)
    except OFFLINE_VERIFY.VerifyError as exc:
        raise ArchiveError(f"R4 product-candidate contract drift: {exc}") from exc
    finally:
        OFFLINE_VERIFY.PAYLOAD = saved_payload
    print(
        "r4-product-candidate: PASS seal-authorized "
        f"artifacts={len(repro['product_artifacts'])} "
        f"set={repro['artifact_set_sha256']} G3=9/9 hardware-only=not-run(6/6)"
    )


def r5_input_check() -> None:
    register_check(announce=False)
    contract = json.loads(R5_CONTRACT.read_text(encoding="utf-8"))
    if isinstance(contract, dict) and contract.get("format") == "lisp65-r5-global-g5-contract-v2":
        if contract.get("status") == "sealed-hardware-passed":
            r5_sealed_input_check(contract)
        else:
            r5_static_input_check(contract)
        return
    if (
        not isinstance(contract, dict)
        or set(contract) != {
            "format", "version", "id", "status", "product_candidate",
            "preflight", "dialect_contract", "execution_layer",
            "test_closure", "matrix", "claims",
        }
        or contract["format"] != "lisp65-r5-global-g5-contract-v1"
        or contract["version"] != 1
        or contract["id"] != "workbench-r5-global-g5"
        or contract["status"] != "static-preflight-passed-hardware-not-run"
    ):
        raise ArchiveError("R5 global G5 contract identity/status drift")
    candidate = contract["product_candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {
        "input_authority", "live_tree_product_authority", "promotion_id",
        "source_commit", "archive", "archive_sha256", "artifact_set_sha256",
        "product_build_id", "artifact_count",
    }:
        raise ArchiveError("R5 product-candidate input schema drift")
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    registered = next(
        (item for item in register["promotions"] if item["id"] == candidate["promotion_id"]),
        None,
    )
    expected_register = {
        "id": candidate["promotion_id"],
        "subject": "r4-product-candidate-late-bound",
        "kind": "product-candidate",
        "source_commit": candidate["source_commit"],
        "archive": candidate["archive"],
        "archive_sha256": candidate["archive_sha256"],
    }
    if registered != expected_register:
        raise ArchiveError("R5 input is not the registered R4 product-candidate")
    archive_path = ROOT / repo_path(candidate["archive"])
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember("manifest.json")
        stream = archive.extractfile(member)
        if stream is None:
            raise ArchiveError("R5 input archive lacks manifest")
        manifest = json.loads(stream.read())
    materialized = manifest.get("product_materialization", {})
    if (
        candidate["input_authority"] != "sealed-r4-product-candidate-archive"
        or candidate["live_tree_product_authority"] is not False
        or manifest.get("id") != candidate["promotion_id"]
        or manifest.get("kind") != "product-candidate"
        or manifest.get("status") != "sealed"
        or manifest.get("source_commit") != candidate["source_commit"]
        or materialized.get("artifact_set_sha256") != candidate["artifact_set_sha256"]
        or materialized.get("product_build_id") != candidate["product_build_id"]
        or len(materialized.get("artifacts", [])) != candidate["artifact_count"]
        or candidate["artifact_count"] != PRODUCT_ARTIFACT_COUNT
    ):
        raise ArchiveError("R5/R4 sealed product identity drift")
    expected_change_policy = {
        "product_artifact_sha_change": "invalidate-all-cases-and-require-new-r4-seal",
        "test_closure_change": "repack-closure-and-offline-reverify-passed-case-receipts",
        "hardware_rerun": "only-missing-or-offline-unverifiable-cases",
    }
    expected_receipt = "tests/bytecode/dialect-v2/evidence/r5/global-g5-static-preflight-receipt.json"
    if contract["preflight"] != {
        "status": "passed", "required_before_hardware": True,
        "binding_authority": "registered-R4-archive-manifest",
        "receipt": expected_receipt,
        "product_artifacts_verified_before_cases": PRODUCT_ARTIFACT_COUNT,
        "runtime_carrier_double_builds": 2,
        "workbench_verifier_negative_mutations_rejected": 6,
        "case_receipt_chains_static_verified": 14,
        "hardware_side_effects": "none",
    } or contract["test_closure"] != {
        "policy": "config/r5-global-g5-test-closure.json",
        "product_membership": "forbidden",
        "runtime_core_role": "internal-proof-only-test-carrier",
        "change_policy": expected_change_policy,
    } or contract["matrix"] != {
        "status": "ready-not-run", "cases": 14, "physical_power_cycles": 4,
        "receipt_resume_policy": "preserve-SHA-bound-cases-for-harness-only-fixes",
    } or contract["claims"] != {
        "G3": "passed-emulator-prefilter-only", "G5": "not-run",
        "G6": "not-run", "release": "not-release-capable",
    } or contract["dialect_contract"] != {
        "path": "config/dialect-v2-contract.json",
        "sha256": "d59af38bf10d28da990d45b2ef92c7e6fecd9f97aafdc958ce7da3de65c7ac8b",
        "source_commit": "312d5abfc9208512b6ca6bdb7a55c017b5b41d3a",
        "public_names": 127,
    } or contract["execution_layer"] != {
        "status": "complete-static-verified-hardware-not-run",
        "policy": "raw-evidence-to-defined-native-receipt-to-defined-case-receipt-to-immediate-offline-verification",
        "format_invention": "forbidden",
        "product_failure_marker": "R5_PRODUCT_RESULT=FAIL",
        "harness_failure_marker": "R5 receipt chain: FAIL kind=harness",
        "resume": "passed-receipts-are-offline-reverifiable-after-test-closure-fixes-unreceipted-raw-evidence-is-never-promotable",
        "evidence_run_id": "r5-run-20260713-06",
        "workbench_boot_wait_seconds": 8,
        "case_count": 14,
    }:
        raise ArchiveError("R5 preflight/matrix claim boundary drift")
    receipt_path = ROOT / repo_path(expected_receipt)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ArchiveError("R5 static preflight receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    product = receipt.get("product_materialization", {})
    closure = receipt.get("test_closure", {})
    negative = receipt.get("workbench_verifier_negative_proof", {})
    chain = receipt.get("case_receipt_chain", {})
    cases = receipt.get("cases", [])
    if (
        receipt.get("format") != "lisp65-r5-global-g5-static-preflight-v1"
        or receipt.get("r5_contract_sha256") != sha_bytes(R5_CONTRACT.read_bytes())
        or receipt.get("matrix_contract_sha256")
        != sha_bytes((ROOT / "config/dialect-v2-g5-matrix.json").read_bytes())
        or product.get("artifact_count") != PRODUCT_ARTIFACT_COUNT
        or product.get("artifact_set_sha256") != candidate["artifact_set_sha256"]
        or product.get("verified_before_cases") is not True
        or closure.get("product_membership") != "forbidden"
        or closure.get("product_artifact_overlap") != 0
        or closure.get("runtime_carrier_double_build") is not True
        or closure.get("drift_gate") != expected_change_policy
        or negative.get("domains") != 2
        or negative.get("mutations_rejected") != 6
        or chain.get("cases") != 14
        or chain.get("coverage")
        != "target-to-raw-to-native-receipt-to-case-receipt-to-verifier"
        or chain.get("failure_classes") != ["product-execution", "receipt-chain-harness"]
        or chain.get("evidence_run_id") != "r5-run-20260713-06"
        or chain.get("workbench_boot_wait_seconds") != 8
        or chain.get("offline_verification") != "immediate-and-repeatable"
        or chain.get("result") != "passed-static-no-hardware"
        or not isinstance(cases, list)
        or len(cases) != 14
        or any(not isinstance(case, dict) or case.get("status") != "ready" for case in cases)
        or len({case.get("id") for case in cases}) != 14
        or receipt.get("case_count") != 14
        or receipt.get("physical_power_cycles_required") != 4
        or receipt.get("hardware_side_effects") != "none"
        or receipt.get("target_file_bindings", {}).get("unbound") != 0
        or receipt.get("claims") != {
            "G5": "not-run", "G6": "not-run", "release": "not-release-capable",
        }
        or receipt.get("result") != "passed"
    ):
        raise ArchiveError("R5 static preflight receipt binding/claim drift")
    print(
        "r5-global-g5-input: PASS authority=sealed-R4-archive live-tree=false "
        f"set={candidate['artifact_set_sha256']} preflight=14/14-static G5=not-run"
    )


def r5_static_input_check(contract: dict[str, Any]) -> None:
    required_keys = {
        "format", "version", "id", "status", "product_candidate",
        "preflight", "dialect_contract", "execution_layer", "test_closure",
        "matrix", "promotion", "claims",
    }
    if (
        set(contract) != required_keys
        or contract.get("version") != 2
        or contract.get("id") != "workbench-r5-global-g5"
        or contract.get("status") != "static-preflight-passed-hardware-not-run"
        or contract.get("promotion") is not None
    ):
        raise ArchiveError("static R5 global G5 contract identity/status drift")

    candidate = contract.get("product_candidate")
    candidate_keys = {
        "input_authority", "live_tree_product_authority", "promotion_id",
        "source_commit", "archive", "archive_sha256", "artifact_set_sha256",
        "product_build_id", "artifact_count",
    }
    if (
        not isinstance(candidate, dict)
        or set(candidate) != candidate_keys
        or candidate["input_authority"] != "sealed-r4-product-candidate-archive"
        or candidate["live_tree_product_authority"] is not False
        or candidate["artifact_count"] != PRODUCT_ARTIFACT_COUNT
    ):
        raise ArchiveError("static R5 product identity drift")
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    registered = next(
        (item for item in register["promotions"] if item["id"] == candidate["promotion_id"]),
        None,
    )
    if (
        not isinstance(registered, dict)
        or registered.get("kind") != "product-candidate"
        or registered.get("source_commit") != candidate["source_commit"]
        or registered.get("archive") != candidate["archive"]
        or registered.get("archive_sha256") != candidate["archive_sha256"]
    ):
        raise ArchiveError("static R5 input is not the registered R4 candidate")
    archive_path = ROOT / repo_path(candidate["archive"])
    if (
        archive_path.is_symlink() or not archive_path.is_file()
        or sha_bytes(archive_path.read_bytes()) != candidate["archive_sha256"]
    ):
        raise ArchiveError("static R5 R4 archive binding drift")
    with tarfile.open(archive_path, "r:gz") as archive:
        stream = archive.extractfile("manifest.json")
        if stream is None:
            raise ArchiveError("static R5 R4 archive lacks manifest")
        manifest = json.loads(stream.read())
    materialized = manifest.get("product_materialization", {})
    if (
        manifest.get("id") != candidate["promotion_id"]
        or manifest.get("kind") != "product-candidate"
        or manifest.get("status") != "sealed"
        or manifest.get("source_commit") != candidate["source_commit"]
        or materialized.get("artifact_set_sha256") != candidate["artifact_set_sha256"]
        or materialized.get("product_build_id") != candidate["product_build_id"]
        or len(materialized.get("artifacts", [])) != PRODUCT_ARTIFACT_COUNT
    ):
        raise ArchiveError("static R5/R4 sealed product identity drift")

    expected_change_policy = {
        "product_artifact_sha_change": "invalidate-all-cases-and-require-new-r4-seal",
        "test_closure_change": "repack-closure-and-offline-reverify-passed-case-receipts",
        "hardware_rerun": "only-missing-or-offline-unverifiable-cases",
    }
    expected_receipt = (
        "tests/bytecode/dialect-v2/evidence/r5/"
        "global-g5-static-preflight-receipt.json"
    )
    if contract["preflight"] != {
        "status": "passed", "required_before_hardware": True,
        "binding_authority": "registered-R4-archive-manifest",
        "receipt": expected_receipt,
        "product_artifacts_verified_before_cases": PRODUCT_ARTIFACT_COUNT,
        "runtime_carrier_double_builds": 2,
        "workbench_verifier_negative_mutations_rejected": 6,
        "case_receipt_chains_static_verified": 14,
        "hardware_side_effects": "none",
    } or contract["test_closure"] != {
        "policy": "config/r5-global-g5-test-closure.json",
        "product_membership": "forbidden",
        "runtime_core_role": "internal-proof-only-test-carrier",
        "change_policy": expected_change_policy,
    } or contract["matrix"] != {
        "status": "ready-not-run", "cases": 14, "physical_power_cycles": 4,
        "receipt_resume_policy": "preserve-SHA-bound-cases-for-harness-only-fixes",
    } or contract["claims"] != {
        "G3": "passed-emulator-prefilter-only", "G5": "not-run",
        "G6": "not-run", "hardware_boot_cases": "not-run(6/6)",
        "release": "not-release-capable",
    }:
        raise ArchiveError("static R5 preflight/matrix claim boundary drift")

    dialect = contract.get("dialect_contract")
    if not isinstance(dialect, dict) or set(dialect) != {
        "path", "sha256", "source_commit", "public_names",
    } or dialect["public_names"] != 128:
        raise ArchiveError("static R5 dialect binding schema drift")
    dialect_path = ROOT / repo_path(dialect["path"])
    if (
        dialect_path.is_symlink() or not dialect_path.is_file()
        or sha_bytes(dialect_path.read_bytes()) != dialect["sha256"]
    ):
        raise ArchiveError("static R5 dialect binding drift")
    execution = contract.get("execution_layer")
    if (
        not isinstance(execution, dict)
        or execution.get("status") != "complete-static-verified-hardware-not-run"
        or execution.get("case_count") != 14
        or execution.get("workbench_boot_wait_seconds") != 8
        or not isinstance(execution.get("evidence_run_id"), str)
        or not execution["evidence_run_id"]
    ):
        raise ArchiveError("static R5 execution-layer drift")

    receipt_path = ROOT / repo_path(expected_receipt)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ArchiveError("R5 static preflight receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    product = receipt.get("product_materialization", {})
    closure = receipt.get("test_closure", {})
    negative = receipt.get("workbench_verifier_negative_proof", {})
    chain = receipt.get("case_receipt_chain", {})
    cases = receipt.get("cases", [])
    if (
        receipt.get("format") != "lisp65-r5-global-g5-static-preflight-v1"
        or receipt.get("r5_contract_sha256") != sha_bytes(R5_CONTRACT.read_bytes())
        or product.get("artifact_count") != PRODUCT_ARTIFACT_COUNT
        or product.get("artifact_set_sha256") != candidate["artifact_set_sha256"]
        or product.get("verified_before_cases") is not True
        or closure.get("product_membership") != "forbidden"
        or closure.get("product_artifact_overlap") != 0
        or closure.get("runtime_carrier_double_build") is not True
        or closure.get("drift_gate") != expected_change_policy
        or negative.get("domains") != 2
        or negative.get("mutations_rejected") != 6
        or chain.get("cases") != 14
        or chain.get("evidence_run_id") != execution["evidence_run_id"]
        or chain.get("workbench_boot_wait_seconds") != 8
        or chain.get("result") != "passed-static-no-hardware"
        or not isinstance(cases, list) or len(cases) != 14
        or any(not isinstance(case, dict) or case.get("status") != "ready" for case in cases)
        or receipt.get("hardware_side_effects") != "none"
        or receipt.get("claims") != {
            "G5": "not-run",
            "G6": "not-run",
            "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
            "release": "not-release-capable",
        }
        or receipt.get("result") != "passed"
    ):
        raise ArchiveError("R5 static preflight receipt binding/claim drift")
    print(
        "r5-global-g5-input: PASS authority=sealed-R4-archive live-tree=false "
        f"set={candidate['artifact_set_sha256']} preflight=14/14-static G5=not-run"
    )


def r5_sealed_input_check(contract: dict[str, Any]) -> None:
    if (
        set(contract) != {
            "format", "version", "id", "status", "product_candidate",
            "preflight", "dialect_contract", "execution_layer",
            "test_closure", "matrix", "promotion", "claims",
        }
        or contract["version"] != 2
        or contract["id"] != "workbench-r5-global-g5"
        or contract["status"] != "sealed-hardware-passed"
    ):
        raise ArchiveError("sealed R5 global G5 contract identity/status drift")
    candidate = contract["product_candidate"]
    product_set = candidate.get("artifact_set_sha256") if isinstance(candidate, dict) else None
    if (
        not isinstance(candidate, dict)
        or candidate.get("input_authority") != "sealed-r4-product-candidate-archive"
        or candidate.get("live_tree_product_authority") is not False
        or not isinstance(product_set, str)
        or len(product_set) != 64
        or any(char not in "0123456789abcdef" for char in product_set)
        or candidate.get("artifact_count") != PRODUCT_ARTIFACT_COUNT
    ):
        raise ArchiveError("sealed R5 product identity drift")
    run_id = contract.get("execution_layer", {}).get("evidence_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ArchiveError("sealed R5 evidence run identity drift")
    expected_cycles = [
        f"{run_id}-runtime-bitflip-03",
        f"{run_id}-runtime-build-id-mismatch-04",
        f"{run_id}-runtime-clean-01",
        f"{run_id}-runtime-truncated-02",
    ]
    if contract["matrix"] != {
        "status": "passed-sealed",
        "cases": 14,
        "physical_power_cycles": 4,
        "case_coverage": "exactly-once",
        "receipt_resume_policy": "preserve-SHA-bound-cases-for-harness-only-fixes",
        "runtime_cycle_ids": expected_cycles,
    }:
        raise ArchiveError("sealed R5 matrix result drift")
    expected_claims = {
        "G3": "passed-emulator-prefilter-only",
        "G5": "passed-for-product-artifact-set",
        "product_artifact_set_sha256": product_set,
        "G6": "not-run",
        "hardware_boot_cases": "not-run(6/6)",
        "release": "not-release-capable",
    }
    if contract["claims"] != expected_claims:
        raise ArchiveError("sealed R5 claim boundary drift")
    promotion = contract["promotion"]
    required_promotion = {
        "id", "kind", "source_commit", "archive", "archive_sha256",
        "top_receipt", "top_receipt_sha256", "isolated_offline_verification",
        "archive_reproducibility", "product_sha_changes",
        "final_one_ceremony_rerun",
    }
    if (
        not isinstance(promotion, dict)
        or set(promotion) != required_promotion
        or promotion["kind"] != "hardware-acceptance"
        or promotion["isolated_offline_verification"] != "passed"
        or promotion["archive_reproducibility"] != "byte-identical-two-builds"
        or promotion["product_sha_changes"] != 0
        or promotion["final_one_ceremony_rerun"] != "permanently-unnecessary"
    ):
        raise ArchiveError("sealed R5 promotion metadata drift")
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    registered = next(
        (item for item in register["promotions"] if item["id"] == promotion["id"]),
        None,
    )
    if registered != {
        "id": promotion["id"],
        "subject": f"r5-global-g5-{product_set[:8]}",
        "kind": "hardware-acceptance",
        "source_commit": promotion["source_commit"],
        "archive": promotion["archive"],
        "archive_sha256": promotion["archive_sha256"],
    }:
        raise ArchiveError("sealed R5 acceptance is not the registered archive")
    receipt_path = ROOT / repo_path(promotion["top_receipt"])
    if (
        receipt_path.is_symlink() or not receipt_path.is_file()
        or sha_bytes(receipt_path.read_bytes()) != promotion["top_receipt_sha256"]
    ):
        raise ArchiveError("sealed R5 top receipt binding drift")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("format") != "lisp65-r5-global-g5-hardware-receipt-v1"
        or receipt.get("status") != "passed"
        or receipt.get("source_commit") != promotion["source_commit"]
        or receipt.get("run_id") != run_id
        or receipt.get("product", {}).get("artifact_set_sha256") != product_set
        or receipt.get("product", {}).get("product_sha_changes") != 0
        or receipt.get("case_coverage") != "exactly-once"
        or len(receipt.get("cases", [])) != 14
        or receipt.get("physical_power_cycles") != 4
        or receipt.get("runtime_cycle_ids") != expected_cycles
        or receipt.get("ceremony", {}).get("final_one_ceremony_rerun")
        != "permanently-unnecessary"
        or receipt.get("claims") != {
            key: value for key, value in expected_claims.items() if key != "G3"
        }
        or receipt.get("result") != "passed"
    ):
        raise ArchiveError("sealed R5 top receipt result/claim drift")
    print(
        "r5-global-g5-input: PASS authority=sealed-hardware-acceptance "
        f"set={product_set} cases=14/14 cycles=4 G5=passed G6=not-run"
    )


def register_check(*, announce: bool = True) -> None:
    value = json.loads(REGISTER.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or set(value) != {"format", "version", "policy", "promotions"}
        or value["format"] != REGISTER_FORMAT
        or value["version"] != 1
        or not isinstance(value["promotions"], list)
    ):
        raise ArchiveError("promotion register schema drift")
    policy_binding = value["policy"]
    if not isinstance(policy_binding, dict) or set(policy_binding) != {"path", "sha256"}:
        raise ArchiveError("promotion register policy binding drift")
    policy_path = ROOT / repo_path(policy_binding["path"])
    if (
        policy_path.is_symlink()
        or not policy_path.is_file()
        or sha_bytes(policy_path.read_bytes()) != policy_binding["sha256"]
    ):
        raise ArchiveError("promotion archive policy SHA drift")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if (
        not isinstance(policy, dict)
        or policy.get("format") != POLICY_FORMAT
        or policy.get("version") != 4
        or policy.get("status") != "active"
        or policy.get("rule") != "promotion-equals-sealing"
        or policy.get("scope")
        != "all-future-block-family-product-candidate-and-hardware-acceptance-promotions"
        or policy.get("archive_requirements") != [
            "varied-environment-fresh-clone-double-build-receipt-embedded",
            "promoted-product-bytes-embedded-no-external-binding",
            "all-mutable-promotion-evidence-embedded-or-content-bound",
            "stdlib-only-offline-verifier-embedded",
            "isolated-verification-without-repository-or-network",
            "source-commit-and-archive-sha-registered",
            "source-commit-already-reachable-from-recorded-private-remote-head",
            "archive-published-as-sha-bound-private-release-asset-not-git-or-lfs",
        ]
        or policy.get("product_materialization") != {
            "pre_seal_gate": "varied-environment-fresh-clone-double-build-required",
            "receipt": "embedded-and-source-commit-bound",
            "artifact_bytes": "every-receipt-product-artifact-embedded",
            "external_product_bindings": "forbidden",
        }
        or policy.get("hardware_acceptance") != {
            "kind": "hardware-acceptance",
            "input": "registered-sealed-product-candidate",
            "product_sha_changes": 0,
            "evidence": "sha-bound-case-receipts-with-cycle-ids",
            "coverage": "exactly-once-per-required-case",
            "final_one_ceremony_rerun": "permanently-unnecessary",
            "claim_boundary": "hardware-gates-not-in-archive-remain-not-run",
        }
        or policy.get("immutability", {}).get("sealed_archive")
        != "append-only-never-amend"
        or policy.get("live_tree_policy", {}).get("register_gate")
        != "validate-entry-against-sha-bound-release-asset-inventory"
        or policy.get("live_tree_policy", {}).get("historical_archive_content")
        != "not-revalidated-by-live-gates"
        or policy.get("remote_source_binding") != {
            "required_for_new_promotions": True,
            "field": "remote_source_binding.remote_head",
            "gate": "source-commit-is-remote-ancestor",
            "historical_archives_without_field": "accepted-as-pre-policy",
            "mandatory_manifest_versions": {
                "hardware_acceptance": 2,
                "promotion": "lisp65-promotion-archive-v3",
            },
            "offline_negative_gate": "missing-or-malformed-binding-rejected",
        }
        or policy.get("archive_transport") != {
            "authority": "config/evidence-archive-assets.json",
            "git": "forbidden",
            "git_lfs": "forbidden",
            "local_materialization": "ignored-cache-verified-before-use",
            "remote_mutation": "new-asset-name-and-new-promotion-id-never-clobber-sealed-bytes",
        }
    ):
        raise ArchiveError("promotion archive policy semantic drift")
    ids: list[str] = []
    subjects: list[str] = []
    for index, item in enumerate(value["promotions"]):
        if not isinstance(item, dict) or set(item) != {
            "id", "subject", "kind", "source_commit", "archive", "archive_sha256",
        }:
            raise ArchiveError(f"promotion register item {index} schema drift")
        if (
            item["kind"] not in {
                "capability-carrier", "family", "product-candidate",
                "hardware-acceptance",
            }
            or not isinstance(item["subject"], str)
            or not item["subject"]
            or not isinstance(item["source_commit"], str)
            or len(item["source_commit"]) != 40
            or any(character not in "0123456789abcdef" for character in item["source_commit"])
            or not isinstance(item["archive_sha256"], str)
            or len(item["archive_sha256"]) != 64
        ):
            raise ArchiveError(f"promotion register item {index} identity drift")
        asset = ARCHIVE_ASSETS.asset_record(item["archive"])
        if asset["sha256"] != item["archive_sha256"]:
            raise ArchiveError(f"promotion register asset drift: {item['id']}")
        path = ROOT / repo_path(item["archive"])
        if path.exists():
            try:
                ARCHIVE_ASSETS.verify_file(path, asset)
            except ARCHIVE_ASSETS.AssetError as exc:
                raise ArchiveError(f"promotion register local-cache drift: {item['id']}: {exc}") from exc
        history = subprocess.run(
            ["git", "log", "--format=%H", "--", item["archive"]], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if history.returncode:
            raise ArchiveError(f"cannot inspect archive history: {item['id']}")
        commits = [line for line in history.stdout.splitlines() if line]
        if commits:
            raise ArchiveError(
                f"sealed archive transport regressed into Git history: {item['id']}"
            )
        ids.append(item["id"])
        subjects.append(item["subject"])
    if ids != sorted(set(ids)):
        raise ArchiveError("promotion register ids must be sorted and unique")
    if len(subjects) != len(set(subjects)):
        raise ArchiveError("promotion register subjects must be unique")
    if announce:
        print(
            f"promotion-register: PASS promotions={len(ids)} "
            "asset-inventory=pass archive-content=not-revalidated immutable-history=pass"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seal = sub.add_parser("create")
    seal.add_argument("--id", required=True)
    seal.add_argument(
        "--kind", choices=("capability-carrier", "family", "product-candidate"),
        required=True,
    )
    seal.add_argument("--source-commit", required=True)
    seal.add_argument("--sealed-on", required=True)
    seal.add_argument("--root", action="append", default=[], required=True)
    seal.add_argument("--follow", action="append", default=[], required=True)
    assertion_source = seal.add_mutually_exclusive_group(required=True)
    assertion_source.add_argument("--assertions")
    assertion_source.add_argument("--assertions-file")
    seal.add_argument("--reproducibility-receipt", required=True)
    seal.add_argument("--product-artifact", action="append", default=[], required=True)
    seal.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("isolated-verify")
    verify.add_argument("archive", type=Path)
    sub.add_parser("register-check")
    sub.add_parser("product-candidate-check")
    sub.add_parser("r5-input-check")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            if not args.output.is_absolute():
                args.output = ROOT / args.output
            create(args)
        elif args.command == "isolated-verify":
            path = args.archive if args.archive.is_absolute() else ROOT / args.archive
            isolated_verify(path)
        elif args.command == "register-check":
            register_check()
        elif args.command == "product-candidate-check":
            product_candidate_check()
        else:
            r5_input_check()
        return 0
    except (ArchiveError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"promotion-archive: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
