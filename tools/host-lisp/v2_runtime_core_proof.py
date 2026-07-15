#!/usr/bin/env python3
"""Build and verify the sealed, non-shippable dialect-v2 Runtime-Core proof."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import dialect_ship_guard as ShipGuard  # noqa: E402
import runtime_export_preload as Preload  # noqa: E402
import runtime_export_ship as RuntimeShip  # noqa: E402


CONTRACT_FORMAT = "lisp65-v2-runtime-core-proof-contract-v1"
CANDIDATE_FORMAT = "lisp65-v2-runtime-core-proof-candidate-v1"
ELF_AUDIT_FORMAT = "lisp65-v2-runtime-core-elf-audit-v1"
REPRO_FORMAT = "lisp65-v2-runtime-core-reproducibility-v1"
PROFILE_FORMAT = "lisp65-v2-runtime-core-resolved-profile-v1"
DEFAULT_CONTRACT = ROOT / "config/v2-runtime-core-proof.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PROFILE_KEYS = {
    "format", "profile", "abi_profile", "scope", "shippable",
    "release_authorization", "hardware_g5_claim", "artifact_emitter",
    "source_commit", "contract_sha256", "input_set_sha256",
}
TOP_KEYS = {
    "format", "version", "id", "status", "profile", "provenance",
    "inputs", "build", "budgets", "candidate",
}
PROFILE_CONTRACT = {
    "id": "dialect-v2-runtime-core-proof",
    "abi_profile": "dialect-v2",
    "scope": "internal-evidence-only",
    "shippable": False,
    "release_authorization": "none",
    "workbench_release_effect": "none",
    "cp5_completion_effect": "none",
    "hardware_g5_claim": "none",
}
PROVENANCE_CONTRACT = {
    "artifact_emitter": "python-p0-generator",
    "supporting_evidence": "cp4-workbench-artifact-differential-335-of-335",
    "workbench_emitted": False,
    "pc_free_claim": False,
    "language_family_promotion": False,
}
BUILD_CONTRACT = {
    "entry": "runtime-main",
    "suite": "tests/bytecode/runtime/p0-runtime-export-app-v2.json",
    "layout": "inline-boot-overlay",
    "carrier": "cut",
    "service_registry": "closed-product-specific",
    "treewalk": "stripped",
    "strict_arity": True,
    "reproducibility": "byte-identical-prg-and-elf",
}
ARTIFACT_NAMES = (
    "audit.txt", "elf-audit.json", "footprint.txt", "host-smoke.txt",
    "reproducibility.json", "resolved-profile.txt", "runtime-preload.bin",
    "runtime.prg", "runtime.prg.elf", "service-inventory.json",
    "stdlib-p0.ext.bin", "stdlib-p0.manifest.json", "toolchain.txt",
)
REQUIRED_ELF_SYMBOLS = (
    "lisp65_runtime_preload_detail", "lisp65_runtime_result",
    "lisp65_runtime_state", "vm_callprim", "vm_native_call", "vm_run",
    "vm_run_dir",
)
FORBIDDEN_ELF_SYMBOLS = (
    "apply", "eval", "eval_env", "eval_init", "eval_v2_workbench_service",
    "eval_vm_apply", "eval_vm_bridge", "vm_treewalk_apply",
    "vm_treewalk_call", "vm_workbench_compile_error",
)


class ProofError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProofError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ProofError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ProofError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProofError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProofError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ProofError(f"{label} keys drift: {actual}")
    return value


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _sha_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ProofError(f"{label} must be a lowercase SHA-256")
    return value


def _safe_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProofError(f"{label} must be a non-empty path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise ProofError(f"{label} must be a canonical relative path")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _input_digest(inputs: list[dict[str, str]]) -> str:
    payload = "".join(f"{item['id']}\0{item['path']}\0{item['sha256']}\n" for item in inputs)
    return _sha_bytes(payload.encode("ascii"))


def _clean_head() -> str:
    process = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if process.returncode != 0 or process.stdout:
        raise ProofError("sealed Runtime-Core proof requires a clean Git worktree")
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise ProofError("cannot resolve proof source commit")
    return source_commit


def validate_contract(value: dict[str, Any], *, root: Path = ROOT) -> None:
    _exact(value, TOP_KEYS, "proof contract")
    if (
        value["format"] != CONTRACT_FORMAT or value["version"] != 1
        or value["id"] != "dialect-v2-runtime-core-proof"
        or value["status"] != "host-proof"
    ):
        raise ProofError("proof contract identity drift")
    if value["profile"] != PROFILE_CONTRACT:
        raise ProofError("proof isolation/release policy drift")
    if value["provenance"] != PROVENANCE_CONTRACT:
        raise ProofError("proof provenance policy drift")
    if value["build"] != BUILD_CONTRACT:
        raise ProofError("proof build policy drift")

    inputs = value["inputs"]
    expected_ids = (
        "abi-ledger", "cp4-differential", "linker-script", "p0-generator",
        "runtime-suite", "service-inventory-tool", "service-registry",
    )
    if not isinstance(inputs, list) or tuple(item.get("id") for item in inputs) != expected_ids:
        raise ProofError("proof input inventory/order drift")
    for index, raw in enumerate(inputs):
        item = _exact(raw, {"id", "path", "sha256"}, f"inputs[{index}]")
        relative = _safe_relative(item["path"], f"inputs[{index}].path")
        expected = _sha_value(item["sha256"], f"inputs[{index}].sha256")
        path = root / relative
        if path.is_symlink() or not path.is_file() or _sha(path) != expected:
            raise ProofError(f"proof input binding drift: {item['id']}")

    budgets = _exact(
        value["budgets"],
        {
            "post_boot_reserve_hard_min_bytes", "post_boot_reserve_target_bytes",
            "target_policy", "expected_post_boot_reserve_bytes",
            "expected_target_shortfall_bytes", "expected_resident_bytes",
            "expected_prg_bytes", "expected_boot_overlay_bytes",
            "max_prg_file_end",
        },
        "budgets",
    )
    expected_budgets = {
        "post_boot_reserve_hard_min_bytes": 8192,
        "post_boot_reserve_target_bytes": 12288,
        "target_policy": "report-only-not-promotion",
        "expected_post_boot_reserve_bytes": 14106,
        "expected_target_shortfall_bytes": -1818,
        "expected_resident_bytes": 22757,
        "expected_prg_bytes": 26274,
        "expected_boot_overlay_bytes": 3513,
        "max_prg_file_end": "0xb000",
    }
    if budgets != expected_budgets:
        raise ProofError("proof budget pins drift")
    if budgets["expected_post_boot_reserve_bytes"] < budgets["post_boot_reserve_hard_min_bytes"]:
        raise ProofError("proof does not meet the hard Runtime-Core reserve")
    if (
        budgets["post_boot_reserve_target_bytes"] - budgets["expected_post_boot_reserve_bytes"]
        != budgets["expected_target_shortfall_bytes"]
    ):
        raise ProofError("target shortfall arithmetic drift")

    candidate = _exact(
        value["candidate"],
        {
            "format", "status", "shippable", "release_authorization",
            "hardware_g5_claim", "artifact_names",
        },
        "candidate",
    )
    if candidate != {
        "format": CANDIDATE_FORMAT,
        "status": "sealed-host-proof",
        "shippable": False,
        "release_authorization": "none",
        "hardware_g5_claim": "none",
        "artifact_names": list(ARTIFACT_NAMES),
    }:
        raise ProofError("candidate non-release policy/inventory drift")


def parse_profile(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ProofError(f"cannot read resolved profile: {exc}") from exc
    result: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if "=" not in line:
            raise ProofError(f"resolved profile line {number} is not key=value")
        key, value = line.split("=", 1)
        if not key or not value or key in result:
            raise ProofError(f"resolved profile line {number} is empty/duplicated")
        result[key] = value
    _exact(result, PROFILE_KEYS, "resolved profile")
    if (
        result["format"] != PROFILE_FORMAT
        or result["profile"] != "dialect-v2-runtime-core-proof"
        or result["abi_profile"] != "dialect-v2"
        or result["scope"] != "internal-evidence-only"
        or result["shippable"] != "false"
        or result["release_authorization"] != "none"
        or result["hardware_g5_claim"] != "none"
        or result["artifact_emitter"] != "python-p0-generator"
        or COMMIT_RE.fullmatch(result["source_commit"]) is None
    ):
        raise ProofError("resolved profile identity/non-release policy drift")
    _sha_value(result["contract_sha256"], "profile.contract_sha256")
    _sha_value(result["input_set_sha256"], "profile.input_set_sha256")
    try:
        ShipGuard.enforce(resolved_profile=path.read_bytes())
    except ShipGuard.DialectShipError as exc:
        if "abi_profile=dialect-v2" not in str(exc):
            raise ProofError(f"normal Ship guard rejected unclearly: {exc}") from exc
    else:
        raise ProofError("normal Ship guard accepted the internal dialect-v2 proof")
    return result


def write_profile(contract_path: Path, out: Path, product_source_id: str | None = None) -> None:
    contract = _load(contract_path, "proof contract")
    validate_contract(contract)
    clean_head = _clean_head()
    source_commit = clean_head if product_source_id is None else product_source_id
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise ProofError("product source identity must be 40 lowercase hexadecimal characters")
    fields = {
        "format": PROFILE_FORMAT,
        "profile": "dialect-v2-runtime-core-proof",
        "abi_profile": "dialect-v2",
        "scope": "internal-evidence-only",
        "shippable": "false",
        "release_authorization": "none",
        "hardware_g5_claim": "none",
        "artifact_emitter": "python-p0-generator",
        "source_commit": source_commit,
        "contract_sha256": _sha(contract_path),
        "input_set_sha256": _input_digest(contract["inputs"]),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{key}={fields[key]}\n" for key in fields), encoding="ascii")
    parse_profile(out)
    print(f"v2-runtime-core-proof profile: WROTE {out} source={source_commit[:8]} shippable=false")


def _nm_symbols(nm: Path, elf: Path) -> set[str]:
    process = subprocess.run(
        [str(nm), "--defined-only", str(elf)], capture_output=True, text=True, check=False,
    )
    if process.returncode != 0:
        raise ProofError(f"llvm-nm failed: {process.stderr.strip()}")
    result: set[str] = set()
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            result.add(fields[-1])
    return result


def write_elf_audit(elf: Path, nm: Path, out: Path) -> None:
    symbols = _nm_symbols(nm, elf)
    missing = sorted(set(REQUIRED_ELF_SYMBOLS) - symbols)
    forbidden = sorted(set(FORBIDDEN_ELF_SYMBOLS) & symbols)
    if missing or forbidden:
        raise ProofError(f"Runtime-Core ELF surface failed: missing={missing} forbidden={forbidden}")
    value = {
        "format": ELF_AUDIT_FORMAT,
        "status": "passed",
        "elf_sha256": _sha(elf),
        "nm_sha256": _sha(nm),
        "required_symbols": list(REQUIRED_ELF_SYMBOLS),
        "missing_symbols": [],
        "forbidden_symbols": [],
        "carrier": "cut",
        "workbench_services": "absent",
    }
    _write_json(out, value)
    print(f"v2-runtime-core-proof ELF audit: PASS required={len(REQUIRED_ELF_SYMBOLS)} forbidden=0")


def write_repro(prg_a: Path, elf_a: Path, prg_b: Path, elf_b: Path, out: Path) -> None:
    records = []
    for role, left, right in (("prg", prg_a, prg_b), ("elf", elf_a, elf_b)):
        left_sha, right_sha = _sha(left), _sha(right)
        if left_sha != right_sha or left.read_bytes() != right.read_bytes():
            raise ProofError(f"Runtime-Core {role} double build differs")
        records.append({"role": role, "sha256": left_sha, "bytes": left.stat().st_size})
    _write_json(out, {"format": REPRO_FORMAT, "status": "passed", "byte_identical": True, "artifacts": records})
    print("v2-runtime-core-proof reproducibility: PASS prg=identical elf=identical")


def _kv(path: Path, label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in result:
                raise ProofError(f"duplicate {label} key: {key}")
            result[key] = value
    return result


def _metrics(contract: dict[str, Any], build_dir: Path) -> dict[str, Any]:
    footprint = _kv(build_dir / "footprint.txt", "footprint")
    audit = _kv(build_dir / "audit.txt", "audit")
    budgets = contract["budgets"]
    actual = {
        "prg_bytes": int(footprint["prg_bytes"], 0),
        "prg_file_end": footprint["prg_file_end"],
        "resident_bytes": int(footprint["bank0_resident_bytes"], 0),
        "post_boot_reserve_bytes": int(audit["post_boot_reserve"], 0),
        "post_boot_reserve_hard_min_bytes": budgets["post_boot_reserve_hard_min_bytes"],
        "post_boot_reserve_target_bytes": budgets["post_boot_reserve_target_bytes"],
        "target_shortfall_bytes": budgets["post_boot_reserve_target_bytes"] - int(audit["post_boot_reserve"], 0),
        "boot_overlay_bytes": int(audit["overlay_bytes"], 0),
        "hard_min_status": "passed",
        "target_status": (
            "passed"
            if int(audit["post_boot_reserve"], 0) >= budgets["post_boot_reserve_target_bytes"]
            else "below-target"
        ),
    }
    expected = {
        "prg_bytes": budgets["expected_prg_bytes"],
        "resident_bytes": budgets["expected_resident_bytes"],
        "post_boot_reserve_bytes": budgets["expected_post_boot_reserve_bytes"],
        "target_shortfall_bytes": budgets["expected_target_shortfall_bytes"],
        "boot_overlay_bytes": budgets["expected_boot_overlay_bytes"],
    }
    if any(actual[key] != value for key, value in expected.items()):
        raise ProofError(f"Runtime-Core pinned measurement drift: actual={actual} expected={expected}")
    if (
        actual["post_boot_reserve_bytes"] < budgets["post_boot_reserve_hard_min_bytes"]
        or int(actual["prg_file_end"], 0) > int(budgets["max_prg_file_end"], 0)
    ):
        raise ProofError("Runtime-Core hard budget failed")
    return actual


def _validate_elf_audit(value: dict[str, Any], elf: Path, nm: Path) -> None:
    _exact(
        value,
        {
            "format", "status", "elf_sha256", "nm_sha256", "required_symbols",
            "missing_symbols", "forbidden_symbols", "carrier", "workbench_services",
        },
        "ELF audit",
    )
    if value != {
        "format": ELF_AUDIT_FORMAT,
        "status": "passed",
        "elf_sha256": _sha(elf),
        "nm_sha256": _sha(nm),
        "required_symbols": list(REQUIRED_ELF_SYMBOLS),
        "missing_symbols": [],
        "forbidden_symbols": [],
        "carrier": "cut",
        "workbench_services": "absent",
    }:
        raise ProofError("ELF audit binding drift")
    symbols = _nm_symbols(nm, elf)
    if set(REQUIRED_ELF_SYMBOLS) - symbols or set(FORBIDDEN_ELF_SYMBOLS) & symbols:
        raise ProofError("live ELF symbols differ from the sealed audit")


def validate_candidate_manifest(value: dict[str, Any], contract: dict[str, Any]) -> None:
    _exact(
        value,
        {
            "format", "version", "profile", "abi_profile", "status", "shippable",
            "release_authorization", "cp5_completion_effect", "hardware_g5_claim",
            "source_commit", "contract", "contract_sha256", "provenance",
            "metrics", "artifacts",
        },
        "candidate manifest",
    )
    if (
        value["format"] != CANDIDATE_FORMAT or value["version"] != 1
        or value["profile"] != "dialect-v2-runtime-core-proof"
        or value["abi_profile"] != "dialect-v2"
        or value["status"] != "sealed-host-proof" or value["shippable"] is not False
        or value["release_authorization"] != "none"
        or value["cp5_completion_effect"] != "none"
        or value["hardware_g5_claim"] != "none"
        or not isinstance(value["source_commit"], str)
        or COMMIT_RE.fullmatch(value["source_commit"]) is None
        or value["contract"] != "config/v2-runtime-core-proof.json"
        or not isinstance(value["contract_sha256"], str)
    ):
        raise ProofError("candidate identity/non-release policy drift")
    if value["provenance"] != PROVENANCE_CONTRACT:
        raise ProofError("candidate provenance drift")
    if not isinstance(value["metrics"], dict):
        raise ProofError("candidate metrics are missing")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or tuple(item.get("path") for item in artifacts) != ARTIFACT_NAMES:
        raise ProofError("candidate artifact inventory/order drift")
    for index, raw in enumerate(artifacts):
        item = _exact(raw, {"path", "bytes", "sha256"}, f"artifacts[{index}]")
        _safe_relative(item["path"], f"artifacts[{index}].path")
        if type(item["bytes"]) is not int or item["bytes"] <= 0:
            raise ProofError(f"artifacts[{index}].bytes is invalid")
        _sha_value(item["sha256"], f"artifacts[{index}].sha256")


def _verify_payloads(directory: Path, contract_path: Path, contract: dict[str, Any], nm: Path) -> dict[str, Any]:
    manifest = _load(directory / "manifest.json", "candidate manifest")
    validate_candidate_manifest(manifest, contract)
    if manifest["contract_sha256"] != _sha(contract_path):
        raise ProofError("candidate contract SHA binding drift")
    expected_files = {"manifest.json", *ARTIFACT_NAMES}
    actual_files = {item.name for item in directory.iterdir() if item.is_file() and not item.is_symlink()}
    if actual_files != expected_files or any(item.is_symlink() for item in directory.iterdir()):
        raise ProofError("candidate directory inventory/symlink drift")
    for record in manifest["artifacts"]:
        path = directory / record["path"]
        if path.stat().st_size != record["bytes"] or _sha(path) != record["sha256"]:
            raise ProofError(f"candidate artifact hash/size drift: {record['path']}")

    profile = parse_profile(directory / "resolved-profile.txt")
    if (
        profile["source_commit"] != manifest["source_commit"]
        or profile["contract_sha256"] != manifest["contract_sha256"]
        or profile["input_set_sha256"] != _input_digest(contract["inputs"])
    ):
        raise ProofError("candidate resolved-profile provenance drift")
    metrics = _metrics(contract, directory)
    if manifest["metrics"] != metrics:
        raise ProofError("candidate metric binding drift")

    inventory = _load(directory / "service-inventory.json", "service inventory")
    summary = inventory.get("summary")
    if (
        inventory.get("status") != "closed" or inventory.get("service_registry_closed") is not True
        or inventory.get("runtime_function_pointer_registry") is not False
        or inventory.get("artifact", {}).get("abi_profile") != "dialect-v2"
        or inventory.get("artifact", {}).get("strict_arity") is not True
        or not isinstance(summary, dict)
        or summary != {
            "callprim_calls": 0, "classified_calls": 4, "directory_calls": 4,
            "tombstone_callprim_calls": 0, "unclassified_calls": 0,
            "unresolved_calls": 0, "workbench_service_callprim_calls": 0,
        }
    ):
        raise ProofError("candidate service inventory is not the closed Runtime-Core surface")
    stdlib = _load(directory / "stdlib-p0.manifest.json", "stdlib manifest")
    external = stdlib.get("external_image")
    if (
        stdlib.get("suite") != BUILD_CONTRACT["suite"] or stdlib.get("abi_profile") != "dialect-v2"
        or stdlib.get("strict_arity") is not True or stdlib.get("functions") != ["runtime-step", "runtime-main"]
        or not isinstance(external, dict) or external.get("sha256") != _sha(directory / "stdlib-p0.ext.bin")
    ):
        raise ProofError("candidate stdlib is not the pinned v2 Runtime-Core artifact")
    if (directory / "host-smoke.txt").read_text(encoding="utf-8") != (
        "runtime-core-smoke: PASS result=42 carrier=cut errors=typeerror\n"
    ):
        raise ProofError("candidate host smoke is not the carrier-cut result-42 proof")
    repro = _load(directory / "reproducibility.json", "reproducibility report")
    if repro.get("format") != REPRO_FORMAT or repro.get("status") != "passed" or repro.get("byte_identical") is not True:
        raise ProofError("candidate reproducibility report is not passing")
    _validate_elf_audit(_load(directory / "elf-audit.json", "ELF audit"), directory / "runtime.prg.elf", nm)

    preload = (directory / "runtime-preload.bin").read_bytes()
    try:
        payload, build_id = Preload.parse(preload)
    except Preload.PreloadError as exc:
        raise ProofError(f"candidate preload is invalid: {exc}") from exc
    if payload != (directory / "stdlib-p0.ext.bin").read_bytes():
        raise ProofError("candidate preload payload differs from the v2 stdlib image")
    expected_build_id = int(_sha(directory / "resolved-profile.txt")[:8], 16)
    if build_id != expected_build_id:
        raise ProofError("candidate preload build ID differs from the resolved profile")
    RuntimeShip.verify_prg_binding(
        (directory / "runtime.prg").read_bytes(), len(payload),
        RuntimeShip.crc16_ccitt_false(preload), build_id,
    )
    return manifest


def pack(contract_path: Path, build_dir: Path, artifact_prefix: Path, inventory: Path, nm: Path, out: Path) -> None:
    contract = _load(contract_path, "proof contract")
    validate_contract(contract)
    if out.exists() or out.is_symlink():
        raise ProofError(f"refusing to overwrite candidate directory: {out}")
    mapping = {
        "audit.txt": build_dir / "audit.txt",
        "elf-audit.json": build_dir / "elf-audit.json",
        "footprint.txt": build_dir / "footprint.txt",
        "host-smoke.txt": build_dir / "host-smoke.txt",
        "reproducibility.json": build_dir / "reproducibility.json",
        "resolved-profile.txt": build_dir / "resolved-profile.txt",
        "runtime-preload.bin": build_dir / "runtime-preload.bin",
        "runtime.prg": build_dir / "link-a/runtime.prg",
        "runtime.prg.elf": build_dir / "link-a/runtime.prg.elf",
        "service-inventory.json": inventory,
        "stdlib-p0.ext.bin": Path(str(artifact_prefix) + ".ext.bin"),
        "stdlib-p0.manifest.json": Path(str(artifact_prefix) + ".manifest.json"),
        "toolchain.txt": build_dir / "toolchain.txt",
    }
    for name in ARTIFACT_NAMES:
        source = mapping[name]
        if source.is_symlink() or not source.is_file():
            raise ProofError(f"missing proof artifact: {source}")
    profile = parse_profile(mapping["resolved-profile.txt"])
    _clean_head()
    out.mkdir(parents=True)
    try:
        for name in ARTIFACT_NAMES:
            shutil.copyfile(mapping[name], out / name)
        records = [
            {"path": name, "bytes": (out / name).stat().st_size, "sha256": _sha(out / name)}
            for name in ARTIFACT_NAMES
        ]
        manifest = {
            "format": CANDIDATE_FORMAT,
            "version": 1,
            "profile": "dialect-v2-runtime-core-proof",
            "abi_profile": "dialect-v2",
            "status": "sealed-host-proof",
            "shippable": False,
            "release_authorization": "none",
            "cp5_completion_effect": "none",
            "hardware_g5_claim": "none",
            "source_commit": profile["source_commit"],
            "contract": "config/v2-runtime-core-proof.json",
            "contract_sha256": _sha(contract_path),
            "provenance": PROVENANCE_CONTRACT,
            "metrics": _metrics(contract, out),
            "artifacts": records,
        }
        _write_json(out / "manifest.json", manifest)
        _verify_payloads(out, contract_path, contract, nm)
    except Exception:
        shutil.rmtree(out, ignore_errors=True)
        raise
    print(
        "v2-runtime-core-proof pack: PASS artifacts=13 shippable=false "
        f"reserve={manifest['metrics']['post_boot_reserve_bytes']} target_headroom=1578"
    )


def verify(contract_path: Path, directory: Path, nm: Path) -> None:
    contract = _load(contract_path, "proof contract")
    validate_contract(contract)
    manifest = _verify_payloads(directory, contract_path, contract, nm)
    print(
        "v2-runtime-core-proof verify: PASS status=sealed-host-proof "
        f"source={manifest['source_commit'][:8]} shippable=false release=none g5=none"
    )


def candidate_selftest(contract_path: Path, directory: Path, nm: Path) -> None:
    contract = _load(contract_path, "proof contract")
    validate_contract(contract)
    _verify_payloads(directory, contract_path, contract, nm)

    def rewrite_manifest(base: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
        path = base / "manifest.json"
        value = _load(path, "mutation manifest")
        mutate(value)
        _write_json(path, value)

    def bitflip(base: Path, name: str) -> None:
        path = base / name
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 1
        path.write_bytes(data)

    def rewrite_profile(base: Path) -> None:
        path = base / "resolved-profile.txt"
        path.write_text(
            path.read_text(encoding="ascii").replace("release_authorization=none", "release_authorization=passed"),
            encoding="ascii",
        )

    mutations: list[tuple[str, Callable[[Path], None]]] = [
        ("manifest-shippable", lambda base: rewrite_manifest(base, lambda x: x.__setitem__("shippable", True))),
        ("metric-forgery", lambda base: rewrite_manifest(base, lambda x: x["metrics"].__setitem__("target_status", "below-target"))),
        ("runtime-bitflip", lambda base: bitflip(base, "runtime.prg")),
        ("preload-bitflip", lambda base: bitflip(base, "runtime-preload.bin")),
        ("profile-release", rewrite_profile),
        ("artifact-drop", lambda base: (base / "audit.txt").unlink()),
    ]
    accepted = []
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-runtime-candidate-") as raw:
        temp = Path(raw)
        for name, mutate in mutations:
            candidate = temp / name
            shutil.copytree(directory, candidate)
            mutate(candidate)
            try:
                _verify_payloads(candidate, contract_path, contract, nm)
            except (ProofError, RuntimeShip.ShipError, ShipGuard.DialectShipError, OSError):
                continue
            accepted.append(name)
    if accepted:
        raise ProofError(f"candidate artifact selftest accepted mutations: {accepted}")
    print(f"v2-runtime-core-proof candidate: SELFTEST PASS mutations={len(mutations)}")


def selftest(contract_path: Path) -> None:
    contract = _load(contract_path, "proof contract")
    validate_contract(contract)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("shippable", lambda x: x["profile"].__setitem__("shippable", True)),
        ("release", lambda x: x["profile"].__setitem__("release_authorization", "allowed")),
        ("cp5", lambda x: x["profile"].__setitem__("cp5_completion_effect", "complete")),
        ("g5", lambda x: x["profile"].__setitem__("hardware_g5_claim", "passed")),
        ("emitter", lambda x: x["provenance"].__setitem__("workbench_emitted", True)),
        ("pc-free", lambda x: x["provenance"].__setitem__("pc_free_claim", True)),
        ("hard-min", lambda x: x["budgets"].__setitem__("post_boot_reserve_hard_min_bytes", 4096)),
        ("target-policy", lambda x: x["budgets"].__setitem__("target_policy", "passed")),
        ("input-sha", lambda x: x["inputs"][0].__setitem__("sha256", "0" * 64)),
        ("artifact-drop", lambda x: x["candidate"]["artifact_names"].pop()),
    ]
    accepted = []
    for name, mutate in mutations:
        candidate = deepcopy(contract)
        mutate(candidate)
        try:
            validate_contract(candidate)
        except ProofError:
            continue
        accepted.append(name)
    if accepted:
        raise ProofError(f"contract selftest accepted mutations: {accepted}")

    fake_artifacts = [
        {"path": name, "bytes": 1, "sha256": "0" * 64} for name in ARTIFACT_NAMES
    ]
    manifest = {
        "format": CANDIDATE_FORMAT, "version": 1,
        "profile": "dialect-v2-runtime-core-proof", "abi_profile": "dialect-v2",
        "status": "sealed-host-proof", "shippable": False,
        "release_authorization": "none", "cp5_completion_effect": "none",
        "hardware_g5_claim": "none", "source_commit": "1" * 40,
        "contract": "config/v2-runtime-core-proof.json", "contract_sha256": "0" * 64,
        "provenance": PROVENANCE_CONTRACT, "metrics": {}, "artifacts": fake_artifacts,
    }
    validate_candidate_manifest(manifest, contract)
    candidate_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("candidate-ship", lambda x: x.__setitem__("shippable", True)),
        ("candidate-release", lambda x: x.__setitem__("release_authorization", "release")),
        ("candidate-cp5", lambda x: x.__setitem__("cp5_completion_effect", "complete")),
        ("candidate-g5", lambda x: x.__setitem__("hardware_g5_claim", "passed")),
        ("candidate-profile", lambda x: x.__setitem__("abi_profile", "dialect-v1")),
        ("candidate-artifact", lambda x: x["artifacts"].pop()),
    ]
    accepted = []
    for name, mutate in candidate_mutations:
        candidate = deepcopy(manifest)
        mutate(candidate)
        try:
            validate_candidate_manifest(candidate, contract)
        except ProofError:
            continue
        accepted.append(name)
    if accepted:
        raise ProofError(f"candidate selftest accepted mutations: {accepted}")

    with tempfile.TemporaryDirectory(prefix="lisp65-v2-runtime-proof-") as raw:
        profile = Path(raw) / "profile.txt"
        profile.write_text(
            "format=lisp65-v2-runtime-core-resolved-profile-v1\n"
            "profile=dialect-v2-runtime-core-proof\nabi_profile=dialect-v2\n"
            "scope=internal-evidence-only\nshippable=false\nrelease_authorization=none\n"
            "hardware_g5_claim=none\nartifact_emitter=python-p0-generator\n"
            f"source_commit={'1' * 40}\ncontract_sha256={'0' * 64}\ninput_set_sha256={'0' * 64}\n",
            encoding="ascii",
        )
        parse_profile(profile)
        changed = profile.read_text(encoding="ascii").replace("shippable=false", "shippable=true")
        profile.write_text(changed, encoding="ascii")
        try:
            parse_profile(profile)
        except ProofError:
            pass
        else:
            raise ProofError("profile selftest accepted shippable=true")
    print(
        "v2-runtime-core-proof: SELFTEST PASS "
        f"contract_mutations={len(mutations)} candidate_mutations={len(candidate_mutations)} profile_mutations=1"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    sub.add_parser("check")
    profile = sub.add_parser("profile")
    profile.add_argument("--out", type=Path, required=True)
    profile.add_argument("--product-source-id")
    audit = sub.add_parser("elf-audit")
    audit.add_argument("--elf", type=Path, required=True)
    audit.add_argument("--nm", type=Path, required=True)
    audit.add_argument("--out", type=Path, required=True)
    repro = sub.add_parser("repro")
    repro.add_argument("--prg-a", type=Path, required=True)
    repro.add_argument("--elf-a", type=Path, required=True)
    repro.add_argument("--prg-b", type=Path, required=True)
    repro.add_argument("--elf-b", type=Path, required=True)
    repro.add_argument("--out", type=Path, required=True)
    pack_parser = sub.add_parser("pack")
    pack_parser.add_argument("--build-dir", type=Path, required=True)
    pack_parser.add_argument("--artifact-prefix", type=Path, required=True)
    pack_parser.add_argument("--inventory", type=Path, required=True)
    pack_parser.add_argument("--nm", type=Path, required=True)
    pack_parser.add_argument("--out", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--dir", type=Path, required=True)
    verify_parser.add_argument("--nm", type=Path, required=True)
    candidate_test = sub.add_parser("candidate-selftest")
    candidate_test.add_argument("--dir", type=Path, required=True)
    candidate_test.add_argument("--nm", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        contract_path = args.contract.resolve()
        if args.command == "selftest":
            selftest(contract_path)
        elif args.command == "check":
            contract = _load(contract_path, "proof contract")
            validate_contract(contract)
            print("v2-runtime-core-proof contract: PASS scope=internal shippable=false release=none g5=none")
        elif args.command == "profile":
            write_profile(contract_path, args.out.resolve(), args.product_source_id)
        elif args.command == "elf-audit":
            write_elf_audit(args.elf.resolve(), args.nm.resolve(), args.out.resolve())
        elif args.command == "repro":
            write_repro(
                args.prg_a.resolve(), args.elf_a.resolve(),
                args.prg_b.resolve(), args.elf_b.resolve(), args.out.resolve(),
            )
        elif args.command == "pack":
            pack(
                contract_path, args.build_dir.resolve(), args.artifact_prefix.resolve(),
                args.inventory.resolve(), args.nm.resolve(), args.out.resolve(),
            )
        elif args.command == "verify":
            verify(contract_path, args.dir.resolve(), args.nm.resolve())
        else:
            candidate_selftest(contract_path, args.dir.resolve(), args.nm.resolve())
        return 0
    except (
        ProofError, ShipGuard.DialectShipError, RuntimeShip.ShipError,
        OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError,
    ) as exc:
        print(f"v2-runtime-core-proof: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
