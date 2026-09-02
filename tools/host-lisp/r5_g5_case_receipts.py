#!/usr/bin/env python3
"""Thin R5 case-receipt transformer and verifier.

This tool does not define an evidence format.  It binds the native Workbench
or Runtime receipt to the existing dialect-v2 case-evidence envelope and
immediately verifies both layers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import dialect_v2_workbench_g5_verify as WORKBENCH  # noqa: E402
import runtime_export_hw_oracle as RUNTIME  # noqa: E402


MATRIX = ROOT / "config/dialect-v2-g5-matrix.json"
WORKBENCH_FORMAT = "lisp65-dialect-v2-workbench-g5-case-evidence-v1"
RUNTIME_FORMAT = "lisp65-dialect-v2-runtime-g5-case-evidence-v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ReceiptError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReceiptError(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptError(f"{label} must be an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ReceiptError(f"{label} keys drift: {actual}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ReceiptError(f"{label} must be a lowercase SHA-256")
    return value


def repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"{label} must be a repository path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ReceiptError(f"{label} escapes the repository")
    path = (ROOT / Path(*pure.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise ReceiptError(f"{label} escapes the repository") from exc
    return path


def relative(path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ReceiptError(f"{label} must be inside the repository") from exc


def bound_file(path_value: Any, digest: Any, label: str) -> Path:
    path = repo_path(path_value, label)
    if path.is_symlink() or not path.is_file() or sha(path) != lower_sha(digest, f"{label} SHA"):
        raise ReceiptError(f"{label} SHA binding drift")
    return path


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_text(encoding="ascii") != data:
            raise ReceiptError(f"existing receipt is immutable and differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="ascii")


def candidate_context(path: Path) -> tuple[dict[str, Any], str]:
    value = load(path, "R5 candidate")
    if (
        value.get("format") != "lisp65-r5-global-g5-candidate-v1"
        or value.get("profile") != "dialect-v2"
        or value.get("status") != "preflight-candidate-g5-none"
        or not isinstance(value.get("build_id"), int)
    ):
        raise ReceiptError("R5 candidate identity/status drift")
    bindings = value.get("bindings")
    if not isinstance(bindings, dict):
        raise ReceiptError("R5 candidate lacks bindings")
    for prefix in ("matrix_contract", "migration_contract", "dialect_contract"):
        bound_file(bindings.get(prefix), bindings.get(f"{prefix}_sha256"), f"candidate {prefix}")
    if bindings["matrix_contract"] != MATRIX.relative_to(ROOT).as_posix():
        raise ReceiptError("candidate matrix path drift")
    product = value.get("product")
    if not isinstance(product, dict):
        raise ReceiptError("R5 candidate lacks product identity")
    lower_sha(product.get("artifact_set_sha256"), "candidate product artifact set")
    return value, sha(path)


def test_closure_artifact_sha(candidate: dict[str, Any], artifact_id: str) -> str:
    binding = candidate.get("test_closure")
    if not isinstance(binding, dict):
        raise ReceiptError("R5 candidate lacks test-closure identity")
    manifest_path = bound_file(
        binding.get("manifest"), binding.get("manifest_sha256"), "candidate test closure"
    )
    manifest = load(manifest_path, "candidate test closure")
    if manifest.get("closure_set_sha256") != binding.get("closure_set_sha256"):
        raise ReceiptError("candidate test-closure set drift")
    matches = [row for row in manifest.get("artifacts", []) if row.get("id") == artifact_id]
    if len(matches) != 1:
        raise ReceiptError(f"candidate test closure lacks unique artifact: {artifact_id}")
    return lower_sha(matches[0].get("sha256"), f"test-closure artifact {artifact_id}")


def case_spec(domain_id: str, case_id: str) -> dict[str, Any]:
    matrix = load(MATRIX, "global G5 matrix")
    for domain in matrix.get("domains", []):
        if domain.get("id") != domain_id:
            continue
        for case in domain.get("cases", []):
            if case.get("id") == case_id:
                return {
                    "domain": domain_id,
                    "verifier": domain["verifier"],
                    "verifier_sha256": domain["verifier_sha256"],
                    **case,
                }
    raise ReceiptError(f"case is outside the R5 matrix: {domain_id}/{case_id}")


def raw_rows(paths: list[Path]) -> list[dict[str, str]]:
    resolved = sorted({path.resolve() for path in paths}, key=lambda path: relative(path, "raw artifact"))
    if not resolved:
        raise ReceiptError("case receipt requires raw artifacts")
    rows = []
    for path in resolved:
        if path.is_symlink() or not path.is_file():
            raise ReceiptError(f"raw artifact is not a regular file: {path}")
        rows.append({"path": relative(path, "raw artifact"), "sha256": sha(path)})
    return rows


def common_case(
    candidate_path: Path,
    candidate: dict[str, Any],
    candidate_sha: str,
    spec: dict[str, Any],
    cycle_id: str,
    native_receipt: Path,
    raw: list[Path],
    verifier_inputs: list[dict[str, str]],
) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(cycle_id):
        raise ReceiptError("cycle id must be a nonempty safe identifier")
    bindings = candidate["bindings"]
    return {
        "format": spec["evidence_format"],
        "profile": "dialect-v2",
        "migration_contract_sha256": bindings["migration_contract_sha256"],
        "dialect_contract_sha256": bindings["dialect_contract_sha256"],
        "candidate_manifest_sha256": candidate_sha,
        "build_id": candidate["build_id"],
        "case_id": f"{spec['domain']}/{spec['id']}",
        "target": spec["target"],
        "result": spec["expected"],
        "cycle_id": cycle_id,
        "native_receipt": relative(native_receipt, "native receipt"),
        "native_receipt_sha256": sha(native_receipt),
        "verifier_inputs": verifier_inputs,
        "raw_artifacts": raw_rows(raw),
    }


def parse_evidence(values: list[str], native_out: Path, case_id: str) -> tuple[list[dict[str, str]], list[Path]]:
    expected_roles = list(WORKBENCH.EVIDENCE[case_id])
    by_role: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ReceiptError("--evidence must use role=path")
        role, raw_path = value.split("=", 1)
        path = Path(raw_path).resolve()
        if role in by_role or role not in expected_roles:
            raise ReceiptError(f"duplicate/foreign Workbench evidence role: {role}")
        if path.is_symlink() or not path.is_file():
            raise ReceiptError(f"Workbench raw evidence is missing: {path}")
        try:
            path.relative_to(native_out.parent.resolve())
        except ValueError:
            suffix = path.suffix if path.suffix else ".bin"
            target = native_out.parent.resolve() / "raw" / f"{role}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file() or target.read_bytes() != path.read_bytes():
                    raise ReceiptError(f"existing transformed raw evidence drift: {target}")
            else:
                shutil.copyfile(path, target)
            path = target
        by_role[role] = path
    if list(by_role) != expected_roles:
        raise ReceiptError(f"Workbench evidence role/order drift: expected={expected_roles} actual={list(by_role)}")
    rows = [
        {"role": role, "path": by_role[role].relative_to(native_out.parent.resolve()).as_posix(), "sha256": sha(by_role[role])}
        for role in expected_roles
    ]
    return rows, [by_role[role] for role in expected_roles]


def pack_workbench(args: argparse.Namespace) -> None:
    candidate, candidate_sha = candidate_context(args.candidate.resolve())
    spec = case_spec(args.domain, args.case_id)
    if spec["evidence_format"] != WORKBENCH_FORMAT:
        raise ReceiptError("Workbench packer received a non-Workbench case")
    native_out = args.native_out.resolve()
    evidence, paths = parse_evidence(args.evidence, native_out, args.case_id)
    attempts = []
    if args.transport_retry_evidence_dir:
        retry_dir = args.transport_retry_evidence_dir
        attempts.append({
            "index": 1,
            "outcome": "transport-failure-before-semantic-execution",
            "semantic_execution": False,
            "media_content_mutation": False,
            "evidence_directory": retry_dir,
            "throwaway_media": True,
        })
    attempts.append({
        "index": len(attempts) + 1,
        "outcome": "pass",
        "semantic_execution": True,
        "media_content_mutation": args.domain == "workbench-persistence",
        "evidence_directory": ".",
        "throwaway_media": args.domain == "workbench-persistence" or bool(attempts),
    })
    native = {
        "format": WORKBENCH.RECEIPT_FORMAT,
        "profile": "dialect-v2",
        "product_artifact_set_sha256": candidate["product"]["artifact_set_sha256"],
        "candidate_manifest_sha256": candidate_sha,
        "build_id": candidate["build_id"],
        "case_id": f"{args.domain}/{args.case_id}",
        "target": spec["target"],
        "expected": spec["expected"],
        "result": spec["expected"],
        "cycle_id": args.cycle_id,
        "attempts": attempts,
        "evidence": evidence,
    }
    write_exclusive(native_out, native)
    WORKBENCH.verify_receipt(
        native_out,
        target=spec["target"], result=spec["expected"], cycle_id=args.cycle_id,
        candidate_manifest_sha256=candidate_sha,
        product_artifact_set_sha256=candidate["product"]["artifact_set_sha256"],
        build_id=candidate["build_id"],
        workbench_test_media_sha256=(
            test_closure_artifact_sha(candidate, "workbench-test-d81")
            if args.case_id == "bam-read" else None
        ),
    )
    case = common_case(
        args.candidate.resolve(), candidate, candidate_sha, spec, args.cycle_id,
        native_out, paths, [],
    )
    write_exclusive(args.out.resolve(), case)
    verify_case(args.out.resolve(), args.candidate.resolve())
    print(f"R5 receipt chain: PASS kind=harness case={case['case_id']} native=verified outer=verified")


def runtime_paths(native: dict[str, Any], native_path: Path) -> list[Path]:
    paths = []
    for row in native.get("evidence", []):
        if not isinstance(row, dict) or not isinstance(row.get("file"), str):
            raise ReceiptError("Runtime native receipt evidence drift")
        pure = PurePosixPath(row["file"])
        if pure.is_absolute() or ".." in pure.parts:
            raise ReceiptError("Runtime native evidence escapes its directory")
        paths.append(native_path.parent / Path(*pure.parts))
    return paths


def package_input(package: Path) -> dict[str, str]:
    manifest = package.resolve() / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ReceiptError("Runtime package lacks manifest.json")
    return {"id": "package", "path": relative(manifest, "Runtime package manifest"), "sha256": sha(manifest)}


def file_input(input_id: str, path: Path) -> dict[str, str]:
    path = path.resolve()
    if path.is_symlink() or not path.is_file():
        raise ReceiptError(f"Runtime verifier input is missing: {input_id}")
    return {"id": input_id, "path": relative(path, f"Runtime {input_id}"), "sha256": sha(path)}


def pack_runtime(args: argparse.Namespace) -> None:
    candidate, candidate_sha = candidate_context(args.candidate.resolve())
    spec = case_spec("runtime-export", args.phase)
    if spec["evidence_format"] != RUNTIME_FORMAT:
        raise ReceiptError("Runtime packer received a non-Runtime case")
    native_path = args.native_receipt.resolve()
    package = args.package.resolve()
    oracle = args.oracle.resolve()
    RUNTIME.verify_receipt(package, oracle, native_path, None)
    native = load(native_path, "Runtime native receipt")
    operator = native.get("operator")
    if (
        native.get("phase") != args.phase
        or native.get("status") != "PASS"
        or not isinstance(operator, dict)
        or operator.get("cycle_id") != args.cycle_id
    ):
        raise ReceiptError("Runtime native phase/result/cycle drift")
    inputs = [package_input(package), file_input("oracle", oracle)]
    case = common_case(
        args.candidate.resolve(), candidate, candidate_sha, spec, args.cycle_id,
        native_path, runtime_paths(native, native_path), inputs,
    )
    write_exclusive(args.out.resolve(), case)
    verify_case(args.out.resolve(), args.candidate.resolve())
    print(f"R5 receipt chain: PASS kind=harness case={case['case_id']} native=verified outer=verified")


def verify_case(path: Path, candidate_path: Path) -> dict[str, Any]:
    candidate, candidate_sha = candidate_context(candidate_path)
    value = load(path, "R5 case receipt")
    exact(
        value,
        {
            "format", "profile", "migration_contract_sha256", "dialect_contract_sha256",
            "candidate_manifest_sha256", "build_id", "case_id", "target", "result",
            "cycle_id", "native_receipt", "native_receipt_sha256", "verifier_inputs",
            "raw_artifacts",
        },
        "R5 case receipt",
    )
    if not isinstance(value.get("case_id"), str) or "/" not in value["case_id"]:
        raise ReceiptError("R5 case id drift")
    domain, case_id = value["case_id"].split("/", 1)
    spec = case_spec(domain, case_id)
    bindings = candidate["bindings"]
    if (
        value["format"] != spec["evidence_format"]
        or value["profile"] != "dialect-v2"
        or value["migration_contract_sha256"] != bindings["migration_contract_sha256"]
        or value["dialect_contract_sha256"] != bindings["dialect_contract_sha256"]
        or value["candidate_manifest_sha256"] != candidate_sha
        or value["build_id"] != candidate["build_id"]
        or value["target"] != spec["target"]
        or value["result"] != spec["expected"]
        or not isinstance(value["cycle_id"], str)
        or not SAFE_ID.fullmatch(value["cycle_id"])
    ):
        raise ReceiptError("R5 case identity/result binding drift")
    native = bound_file(value["native_receipt"], value["native_receipt_sha256"], "native receipt")
    raw = []
    raw_names = []
    for index, row in enumerate(value["raw_artifacts"]):
        item = exact(row, {"path", "sha256"}, f"raw artifact[{index}]")
        raw_names.append(item["path"])
        raw.append(bound_file(item["path"], item["sha256"], f"raw artifact[{index}]"))
    if not raw or raw_names != sorted(set(raw_names)):
        raise ReceiptError("R5 raw artifact coverage/order drift")
    inputs: dict[str, Path] = {}
    input_rows = value["verifier_inputs"]
    if not isinstance(input_rows, list):
        raise ReceiptError("R5 verifier inputs must be a list")
    for index, row in enumerate(input_rows):
        item = exact(row, {"id", "path", "sha256"}, f"verifier input[{index}]")
        if item["id"] in inputs:
            raise ReceiptError("R5 verifier input duplicate")
        inputs[item["id"]] = bound_file(item["path"], item["sha256"], f"verifier input {item['id']}")
    if domain.startswith("workbench-"):
        if inputs:
            raise ReceiptError("Workbench case has unexpected verifier inputs")
        verified = WORKBENCH.verify_receipt(
            native,
            target=spec["target"], result=spec["expected"], cycle_id=value["cycle_id"],
            candidate_manifest_sha256=candidate_sha,
            product_artifact_set_sha256=candidate["product"]["artifact_set_sha256"],
            build_id=candidate["build_id"],
            workbench_test_media_sha256=(
                test_closure_artifact_sha(candidate, "workbench-test-d81")
                if case_id == "bam-read" else None
            ),
        )
        expected_raw = {
            (native.parent / row["path"]).resolve() for row in verified["evidence"]
        }
    elif domain == "runtime-export":
        if set(inputs) != {"package", "oracle"} or inputs["package"].name != "manifest.json":
            raise ReceiptError("Runtime case verifier-input coverage drift")
        package = inputs["package"].parent
        RUNTIME.verify_receipt(package, inputs["oracle"], native, None)
        native_value = load(native, "Runtime native receipt")
        operator = native_value.get("operator")
        if native_value.get("phase") != case_id or not isinstance(operator, dict) or operator.get("cycle_id") != value["cycle_id"]:
            raise ReceiptError("Runtime native phase/cycle drift")
        expected_raw = {path.resolve() for path in runtime_paths(native_value, native)}
    else:
        raise ReceiptError("unknown R5 case domain")
    if {path.resolve() for path in raw} != expected_raw:
        raise ReceiptError("outer/native raw-artifact inventory mismatch")
    return value


def selftest() -> None:
    matrix = load(MATRIX, "global G5 matrix")
    flattened = [f"{domain['id']}/{case['id']}" for domain in matrix["domains"] for case in domain["cases"]]
    if len(flattened) != 14 or len(set(flattened)) != 14:
        raise ReceiptError("R5 case packer matrix coverage drift")
    if sum(name.startswith("runtime-export/") for name in flattened) != 4:
        raise ReceiptError("R5 Runtime packer coverage drift")
    if set(WORKBENCH.EXPECTED) != {"workbench-persistence", "workbench-ux"}:
        raise ReceiptError("R5 Workbench packer domain drift")
    # Exercise the native Workbench verifier on one cheap case per domain.
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-case-packer-") as raw:
        root = Path(raw)
        for domain, case_id in (("workbench-persistence", "bam-read"), ("workbench-ux", "stdlib-runtime")):
            case_root = root / domain
            case_root.mkdir()
            receipt, _value = WORKBENCH.fixture_receipt(
                case_root, domain, case_id, "1" * 64, "2" * 64, 0xFA377C50,
            )
            target, result = WORKBENCH.EXPECTED[domain][case_id]
            WORKBENCH.verify_receipt(
                receipt, target=target, result=result,
                cycle_id=f"negative-proof-{domain}", candidate_manifest_sha256="2" * 64,
                product_artifact_set_sha256="1" * 64, build_id=0xFA377C50,
                workbench_test_media_sha256=(
                    sha(case_root / "media-d81.d81") if case_id == "bam-read" else None
                ),
            )
    print("R5 case receipt packer: SELFTEST PASS cases=14 transforms=2 verifier-domains=3")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    workbench = sub.add_parser("pack-workbench")
    workbench.add_argument("--candidate", type=Path, required=True)
    workbench.add_argument("--domain", choices=("workbench-persistence", "workbench-ux"), required=True)
    workbench.add_argument("--case-id", required=True)
    workbench.add_argument("--cycle-id", required=True)
    workbench.add_argument("--evidence", action="append", required=True)
    workbench.add_argument("--transport-retry-evidence-dir")
    workbench.add_argument("--native-out", type=Path, required=True)
    workbench.add_argument("--out", type=Path, required=True)
    runtime = sub.add_parser("pack-runtime")
    runtime.add_argument("--candidate", type=Path, required=True)
    runtime.add_argument("--phase", choices=tuple(RUNTIME.PHASES), required=True)
    runtime.add_argument("--cycle-id", required=True)
    runtime.add_argument("--package", type=Path, required=True)
    runtime.add_argument("--oracle", type=Path, required=True)
    runtime.add_argument("--native-receipt", type=Path, required=True)
    runtime.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify-case")
    verify.add_argument("--candidate", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    sub.add_parser("selftest")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "pack-workbench":
            pack_workbench(args)
        elif args.command == "pack-runtime":
            pack_runtime(args)
        elif args.command == "verify-case":
            value = verify_case(args.receipt.resolve(), args.candidate.resolve())
            print(f"R5 receipt chain: PASS kind=harness case={value['case_id']} offline=true")
        else:
            selftest()
    except (ReceiptError, WORKBENCH.VerifyError, RUNTIME.HardwareContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"R5 receipt chain: FAIL kind=harness diagnostic={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
