#!/usr/bin/env python3
"""Build and verify the three internal dialect-v2 G5 evidence domains."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import runtime_export_hw_oracle as RUNTIME_HW  # noqa: E402
import runtime_export_preload as PRELOAD  # noqa: E402
import r5_persistence_fixtures as R5_FIXTURES  # noqa: E402


RUNTIME_PACKAGE_FORMAT = "lisp65-v2-runtime-core-g5-package-v1"
PROOF_FORMAT = "lisp65-v2-runtime-core-proof-candidate-v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DOMAIN_RECEIPT_FORMAT = "lisp65-v2-capability-carrier-g5-domain-receipt-v1"
WORKBENCH_CASE_FORMAT = "lisp65-v2-capability-carrier-g5-workbench-case-v1"
PREFLIGHT_FORMAT = "lisp65-v2-capability-carrier-g5-preflight-v1"
CANDIDATE_FORMAT = "lisp65-v2-capability-carrier-g5-candidate-v1"
VERIFIER_PATH = "tools/host-lisp/v2_g5_domain_verifiers.py"
PERSISTENCE_FIXTURES = R5_FIXTURES.load_fixtures()

EXPECTED = {
    "runtime-export": {
        "bitflip": ("v2-capability-carrier-g5-runtime-bitflip", "terminal-preload-error-detail-3"),
        "build-id-mismatch": ("v2-capability-carrier-g5-runtime-build-id-mismatch", "terminal-preload-error-detail-2"),
        "clean": ("v2-capability-carrier-g5-runtime-clean", "result-42"),
        "truncated": ("v2-capability-carrier-g5-runtime-truncated", "terminal-preload-error-detail-1"),
    },
    "workbench-persistence": {
        "bam-alloc": ("v2-capability-carrier-g5-workbench-bam-alloc", "pass"),
        "bam-read": ("v2-capability-carrier-g5-workbench-bam-read", "pass"),
        "chain-write": ("v2-capability-carrier-g5-workbench-chain-write", "pass"),
        "dir-write": ("v2-capability-carrier-g5-workbench-dir-write", "pass"),
        "save-new": ("v2-capability-carrier-g5-workbench-save-new", "pass"),
        "save-new-scan": ("v2-capability-carrier-g5-workbench-save-new-scan", "pass"),
        "save-new-var": ("v2-capability-carrier-g5-workbench-save-new-var", "pass"),
    },
    "workbench-ux": {
        "overlay-stack-guard": ("v2-capability-carrier-g5-workbench-overlay-stack-guard", "pass"),
        "stdlib-runtime": ("v2-capability-carrier-g5-workbench-stdlib-runtime", "pass"),
        "ux-complete": ("v2-capability-carrier-g5-workbench-ux-complete", "pass"),
    },
}

WORKBENCH_EVIDENCE = {
    "bam-read": {"sector-1": "(t 40 2 40 35)", "sector-2": "(t 0 255 0 39)"},
    "bam-alloc": {"before-d81": None, "after-d81": None, "marker": "bam alloc pass 4/4"},
    "chain-write": {"before-d81": None, "after-d81": None, "marker": "chain write pass 7/7", "run": "737"},
    "dir-write": {"before-d81": None, "after-d81": None, "marker": "dir write pass 11/11", "run": "767"},
    "save-new": {"before-d81": None, "after-d81": None, "marker": "save new pass 5/5", "run": "797"},
    "save-new-scan": {"before-d81": None, "after-d81": None, "marker": "save new pass 5/5", "run": "797"},
    "save-new-var": {"before-d81": None, "after-d81": None, "marker": "save new pass 5/5", "run": "907"},
    "overlay-stack-guard": {"ship-receipt": None, "arith": "42", "reader-recovery": "42"},
    "stdlib-runtime": {"result": "42"},
    "ux-complete": {
        "persistence": "((\"(defun ap6-persisted () 612)\") 612 (\"(defun ap6-b () 613)\") 613)",
        "some": "3",
        "every": "t",
        "mx-eval-buffer": "42",
    },
}


class DomainError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DomainError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise DomainError(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DomainError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DomainError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise DomainError(f"{label} keys drift: {actual}")
    return value


def _repo_file(value: Any, sha256: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DomainError(f"{label}.path must be a repository-relative path")
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise DomainError(f"{label}.path escapes the repository") from exc
    if path.is_symlink() or not path.is_file():
        raise DomainError(f"{label} is not a regular file: {path}")
    if not isinstance(sha256, str) or not SHA_RE.fullmatch(sha256) or _sha(path) != sha256:
        raise DomainError(f"{label} SHA binding drift")
    return path


def _repo_package(value: Any, sha256: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DomainError(f"{label}.path must be a repository-relative path")
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise DomainError(f"{label}.path escapes the repository") from exc
    if path.is_symlink() or not path.is_dir():
        raise DomainError(f"{label} is not a regular package directory: {path}")
    manifest = path / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise DomainError(f"{label} lacks a regular manifest.json: {path}")
    if not isinstance(sha256, str) or not SHA_RE.fullmatch(sha256) or _sha(manifest) != sha256:
        raise DomainError(f"{label} manifest SHA binding drift")
    return path


def _candidate(path: Path, expected_sha: str | None = None) -> tuple[dict[str, Any], str]:
    candidate = _load(path, "internal G5 candidate")
    candidate_sha = _sha(path)
    if expected_sha is not None and candidate_sha != expected_sha:
        raise DomainError("candidate manifest SHA binding drift")
    if candidate.get("format") != CANDIDATE_FORMAT or candidate.get("g5_claim") != "none":
        raise DomainError("candidate is not the sealed non-claiming internal G5 candidate")
    artifacts = candidate.get("artifacts")
    if not isinstance(artifacts, list):
        raise DomainError("candidate artifact inventory is invalid")
    verifier = next((item for item in artifacts if item.get("id") == "g5-domain-verifier"), None)
    if not isinstance(verifier, dict):
        raise DomainError("candidate does not bind the G5 domain verifier")
    if verifier.get("path") != VERIFIER_PATH or verifier.get("sha256") != _sha(ROOT / VERIFIER_PATH):
        raise DomainError("candidate G5 domain verifier binding drift")
    return candidate, candidate_sha


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise DomainError(f"refusing to overwrite receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _copy(source: Path, out: Path, name: str, role: str) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise DomainError(f"runtime package input is not a regular file: {source}")
    target = out / name
    shutil.copyfile(source, target)
    return {"role": role, "path": name, "size": target.stat().st_size, "sha256": _sha(target)}


def _write(path: Path, data: bytes, role: str) -> dict[str, Any]:
    path.write_bytes(data)
    return {"role": role, "path": path.name, "size": len(data), "sha256": _sha_bytes(data)}


def _binding(record: dict[str, Any]) -> dict[str, str]:
    return {"role": record["role"], "sha256": record["sha256"]}


def _profile_fields(data: bytes) -> dict[str, str]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise DomainError("resolved profile is not ASCII") from exc
    result: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in result:
            raise DomainError(f"duplicate resolved-profile key: {key}")
        result[key] = value
    required = {
        "profile": "dialect-v2-runtime-core-proof",
        "abi_profile": "dialect-v2",
        "shippable": "false",
        "hardware_g5_claim": "none",
    }
    if any(result.get(key) != value for key, value in required.items()):
        raise DomainError("resolved profile is not the sealed dialect-v2 proof profile")
    if not re.fullmatch(r"[0-9a-f]{40}", result.get("source_commit", "")):
        raise DomainError("resolved profile lacks a source commit")
    return result


def pack_runtime(proof_dir: Path, out: Path, nm: Path, objcopy: Path) -> None:
    proof_dir = proof_dir.resolve()
    out = out.resolve()
    if out.exists() or out.is_symlink():
        raise DomainError(f"runtime package output must not exist: {out}")
    proof_manifest_path = proof_dir / "manifest.json"
    proof = _load(proof_manifest_path, "v2 Runtime-Core proof manifest")
    if proof.get("format") != PROOF_FORMAT or proof.get("hardware_g5_claim") != "none":
        raise DomainError("source is not the sealed non-claiming v2 Runtime-Core proof")
    source_commit = proof.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise DomainError("proof source commit is invalid")
    out.mkdir(parents=True, exist_ok=False)
    try:
        records = [
            _copy(proof_manifest_path, out, "proof-manifest.json", "proof-manifest"),
            _copy(proof_dir / "resolved-profile.txt", out, "resolved-profile.txt", "resolved-profile"),
            _copy(proof_dir / "runtime.prg", out, "runtime.prg", "runtime-prg"),
            _copy(proof_dir / "runtime-preload.bin", out, "runtime-preload.bin", "runtime-preload"),
            _copy(proof_dir / "runtime.prg.elf", out, "runtime.prg.elf", "runtime-elf"),
        ]
        profile_data = (out / "resolved-profile.txt").read_bytes()
        profile_fields = _profile_fields(profile_data)
        profile_sha = _sha_bytes(profile_data)
        build_id = int(profile_sha[:8], 16)
        canonical = (out / "runtime-preload.bin").read_bytes()
        payload, bound_build_id = PRELOAD.parse(canonical)
        if bound_build_id != build_id:
            raise DomainError("proof preload build-id differs from the resolved profile")
        stdlib_manifest = _load(proof_dir / "stdlib-p0.manifest.json", "v2 stdlib manifest")
        code_blob_bytes = stdlib_manifest.get("code_bytes")
        if type(code_blob_bytes) is not int or not 0 <= code_blob_bytes < len(payload):
            raise DomainError("v2 stdlib code-byte boundary is invalid")

        foreign_profile_data = profile_data.replace(
            b"profile=dialect-v2-runtime-core-proof\n",
            b"profile=dialect-v2-runtime-core-proof-g5-foreign\n",
            1,
        )
        if foreign_profile_data == profile_data:
            raise DomainError("could not derive the foreign v2 profile")
        foreign_build_id = int(_sha_bytes(foreign_profile_data)[:8], 16)
        if foreign_build_id == build_id:
            raise DomainError("foreign v2 profile did not change the build-id")
        mismatch = PRELOAD.bind(payload, foreign_build_id)
        truncated = payload
        clear = bytes(len(canonical))
        effective_truncated = payload + bytes(PRELOAD.TRAILER_BYTES)
        bitflip = bytearray(canonical)
        bitflip[code_blob_bytes] ^= 1
        bitflip = bytes(bitflip)

        stage_clean = _write(out / "stage-clean.bin", canonical, "stage-clean")
        stage_truncated = _write(out / "stage-truncated.bin", truncated, "stage-truncated")
        effective_truncated_record = _write(
            out / "effective-truncated.bin", effective_truncated, "effective-truncated"
        )
        clear_record = _write(out / "clear-truncated.bin", clear, "clear-truncated")
        stage_bitflip = _write(out / "stage-bitflip.bin", bitflip, "stage-bitflip")
        stage_mismatch = _write(
            out / "stage-build-id-mismatch.bin", mismatch, "stage-build-id-mismatch"
        )
        foreign_profile = _write(
            out / "foreign-profile.txt", foreign_profile_data, "foreign-profile"
        )
        records.extend(
            (
                stage_clean, stage_truncated, effective_truncated_record, clear_record,
                stage_bitflip, stage_mismatch, foreign_profile,
            )
        )
        symbols = RUNTIME_HW._nm_symbols(nm.resolve(), (out / "runtime.prg.elf").resolve())
        hardware_oracle = {
            "format": "lisp65-runtime-export-hardware-oracle-v1",
            "symbols": symbols,
            "states": {"complete": 3, "preload_error": 0xE4},
            "results": {"success_raw": 85, "error_nil_raw": 0},
            "preload_details": {"ok": 0, "length": 1, "build_id": 2, "crc": 3},
        }
        manifest = {
            "format": RUNTIME_PACKAGE_FORMAT,
            "version": 1,
            "profile": {
                "id": "dialect-v2-runtime-core-proof",
                "abi_profile": "dialect-v2",
                "build_id": build_id,
                "sha256": profile_sha,
                "shippable": False,
            },
            "source_candidate": {
                "path": "proof-manifest.json",
                "sha256": records[0]["sha256"],
                "format": PROOF_FORMAT,
                "source_commit": source_commit,
            },
            "artifacts": records,
            "runtime": {
                "prg": {"path": "runtime.prg", "format": "mega65-prg", "load_address": 0x2001},
                "preload": {
                    "path": "runtime-preload.bin",
                    "address": 0x050000,
                    "length": len(canonical),
                    "sha256": _sha_bytes(canonical),
                    "payload_length": len(payload),
                    "code_blob_bytes": code_blob_bytes,
                    "binding": {
                        "format": "lisp65-runtime-preload-binding-v1",
                        "trailer_offset": len(payload),
                        "trailer_length": PRELOAD.TRAILER_BYTES,
                        "build_id": build_id,
                    },
                },
                "expected_result": "42",
            },
            "hardware_oracle": hardware_oracle,
            "phases": {
                "clean": {
                    "stage": _binding(stage_clean),
                    "effective": _binding(stage_clean),
                    "expected_detail": 0,
                },
                "truncated": {
                    "stage": _binding(stage_truncated),
                    "effective": _binding(effective_truncated_record),
                    "clear": _binding(clear_record),
                    "expected_detail": 1,
                },
                "bitflip": {
                    "stage": _binding(stage_bitflip),
                    "effective": _binding(stage_bitflip),
                    "offset": code_blob_bytes,
                    "expected_detail": 3,
                },
                "build-id-mismatch": {
                    "stage": _binding(stage_mismatch),
                    "effective": _binding(stage_mismatch),
                    "foreign_profile": _binding(foreign_profile),
                    "foreign_build_id": foreign_build_id,
                    "expected_detail": 2,
                },
            },
        }
        (out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        # The shared hardware verifier performs the independent strict package check.
        RUNTIME_HW._verified_package(out)
        oracle = out / "hardware-oracle.json"
        RUNTIME_HW.create_oracle(out, out / "runtime.prg.elf", nm, objcopy, oracle)
        RUNTIME_HW.verify_oracle(out, oracle)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    print(
        "v2-g5 runtime package: PASS "
        f"build_id=0x{build_id:08x} artifacts={len(records)} out={out}"
    )


def verify_runtime_package(package: Path) -> None:
    package = package.resolve()
    RUNTIME_HW.verify_oracle(package, package / "hardware-oracle.json")
    print(f"v2-g5 runtime package verify: PASS package={package}")


def _run_oracle(command: list[str], label: str) -> None:
    completed = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise DomainError(f"{label} failed: {detail}")


def _verify_attempts(value: Any, case_id: str) -> None:
    if not isinstance(value, list) or len(value) not in (1, 2):
        raise DomainError(f"workbench case {case_id} must record one or two attempts")
    for index, raw in enumerate(value, 1):
        attempt = _exact(
            raw,
            {
                "index", "outcome", "semantic_execution", "media_content_mutation",
                "evidence_directory", "throwaway_media",
            },
            f"workbench case {case_id} attempt {index}",
        )
        if attempt["index"] != index or not isinstance(attempt["evidence_directory"], str):
            raise DomainError(f"workbench case {case_id} attempt numbering/evidence drift")
    if len(value) == 1:
        if value[0]["outcome"] != "pass" or value[0]["semantic_execution"] is not True:
            raise DomainError(f"workbench case {case_id} single attempt is not a semantic pass")
        return
    first, second = value
    if first != {
        "index": 1,
        "outcome": "transport-failure-before-semantic-execution",
        "semantic_execution": False,
        "media_content_mutation": False,
        "evidence_directory": first["evidence_directory"],
        "throwaway_media": True,
    }:
        raise DomainError(f"workbench case {case_id} retry exceeds the transport-only policy")
    if (
        second["outcome"] != "pass"
        or second["semantic_execution"] is not True
        or second["evidence_directory"] == first["evidence_directory"]
        or second["throwaway_media"] is not True
    ):
        raise DomainError(f"workbench case {case_id} retry did not use fresh passing evidence/media")


def _workbench_diff(case_id: str, evidence: dict[str, Path]) -> None:
    if case_id not in {
        "bam-alloc", "chain-write", "dir-write", "save-new", "save-new-scan",
        "save-new-var",
    }:
        return
    before = str(evidence["before-d81"])
    after = str(evidence["after-d81"])
    py = sys.executable
    fixed = PERSISTENCE_FIXTURES["fixed_write"]
    save = PERSISTENCE_FIXTURES["save_new"]
    scan = PERSISTENCE_FIXTURES["save_new_scan"]
    if case_id == "bam-alloc":
        command = [
            py, "tools/host-lisp/d81_bam_alloc_diff.py", before, after,
            "--track", str(fixed["track"]), "--sector", str(fixed["first_sector"]),
        ]
    elif case_id == "chain-write":
        command = [py, "tools/host-lisp/d81_chain_write_diff.py", before, after,
                   "--source", "tests/disk/m3-chain-source.lisp", "--track", str(fixed["track"]),
                   "--first-sector", str(fixed["first_sector"]), "--second-sector", str(fixed["second_sector"])]
    elif case_id == "dir-write":
        command = [py, "tools/host-lisp/d81_dir_write_diff.py", before, after,
                   "--source", "tests/disk/m4-dir-source.lisp", "--name", "m4src",
                   "--track", str(fixed["track"]), "--first-sector", str(fixed["first_sector"]),
                   "--second-sector", str(fixed["second_sector"]),
                   "--dir-track", str(fixed["directory_track"]),
                   "--dir-sector", str(fixed["directory_sector"]),
                   "--dir-entry", str(fixed["directory_entry"])]
    elif case_id in ("save-new", "save-new-scan"):
        row, name = (save, "m5src") if case_id == "save-new" else (scan, "m6src")
        command = [py, "tools/host-lisp/d81_dir_write_diff.py", before, after,
                   "--source", "tests/disk/m5-new-source.lisp", "--name", name,
                   "--track", str(row["track"]), "--first-sector", str(row["first_sector"]),
                   "--second-sector", str(row["second_sector"]),
                   "--dir-track", str(row["directory_track"]),
                   "--dir-sector", str(row["directory_sector"]),
                   "--dir-entry", str(row["directory_entry"])]
    elif case_id == "save-new-var":
        command = [py, "tools/host-lisp/d81_save_new_diff.py", before, after,
                   "--source", "tests/disk/m7-var-source.lisp", "--name", "m7src",
                   "--dir-track", "40", "--dir-sector", "4", "--dir-entry", "3"]
    _run_oracle(command, f"workbench case {case_id} independent D81 oracle")


def _verify_workbench_case(
    path: Path, sha256: str, domain: str, case_id: str, target: str, expected: str,
    cycle_id: str, candidate: dict[str, Any], product_identity: str,
) -> None:
    receipt_path = _repo_file(path.relative_to(ROOT).as_posix(), sha256, f"workbench case {case_id} receipt")
    receipt = _load(receipt_path, f"workbench case {case_id} receipt")
    _exact(
        receipt,
        {
            "format", "product_identity_sha256", "build_id", "case_id", "target",
            "expected", "result", "cycle_id", "attempts", "evidence",
        },
        f"workbench case {case_id} receipt",
    )
    if (
        receipt["format"] != WORKBENCH_CASE_FORMAT
        or receipt["product_identity_sha256"] != product_identity
        or receipt["build_id"] != candidate.get("build_id")
        or receipt["case_id"] != f"{domain}/{case_id}"
        or receipt["target"] != target
        or receipt["expected"] != expected
        or receipt["result"] != expected
        or receipt["cycle_id"] != cycle_id
    ):
        raise DomainError(f"workbench case {case_id} receipt binding/result drift")
    _verify_attempts(receipt["attempts"], case_id)
    required = WORKBENCH_EVIDENCE[case_id]
    evidence: dict[str, Path] = {}
    if not isinstance(receipt["evidence"], list):
        raise DomainError(f"workbench case {case_id} evidence must be a list")
    for index, raw in enumerate(receipt["evidence"]):
        item = _exact(raw, {"role", "path", "sha256"}, f"workbench case {case_id} evidence[{index}]")
        role = item["role"]
        if role in evidence or role not in required:
            raise DomainError(f"workbench case {case_id} evidence role duplicate/foreign: {role}")
        evidence[role] = _repo_file(item["path"], item["sha256"], f"workbench case {case_id} evidence {role}")
    if tuple(evidence) != tuple(required):
        raise DomainError(f"workbench case {case_id} evidence coverage/order drift")
    for role, marker in required.items():
        if marker is not None:
            text = evidence[role].read_text(encoding="utf-8", errors="replace")
            if marker not in text:
                raise DomainError(f"workbench case {case_id} evidence {role} lacks oracle {marker!r}")
    if case_id == "overlay-stack-guard":
        ship = _load(evidence["ship-receipt"], "Workbench Ship readback receipt")
        if ship.get("schema") != "lisp65-hw-ship-memory-receipt-v2" or ship.get("dry_run") is not False:
            raise DomainError("overlay stack guard lacks a live Ship readback receipt")
    _workbench_diff(case_id, evidence)


def _verify_preflight(
    path: Path, sha256: str, product_identity: str, case_key: str, target: str,
) -> None:
    receipt_path = _repo_file(path.relative_to(ROOT).as_posix(), sha256, f"preflight for {case_key}")
    receipt = _load(receipt_path, f"preflight for {case_key}")
    _exact(
        receipt,
        {
            "format", "product_identity_sha256", "candidate_manifest",
            "candidate_manifest_sha256", "contract", "contract_sha256", "verifier",
            "verifier_sha256", "makefile", "makefile_sha256", "cases", "side_effects", "result",
        },
        f"preflight for {case_key}",
    )
    if (
        receipt["format"] != PREFLIGHT_FORMAT
        or receipt["product_identity_sha256"] != product_identity
        or receipt["side_effects"] != "none"
        or receipt["result"] != "passed"
        or not isinstance(receipt["cases"], list)
    ):
        raise DomainError(f"preflight identity/result drift for {case_key}")
    matches = [item for item in receipt["cases"] if isinstance(item, dict) and item.get("id") == case_key]
    if len(matches) != 1:
        raise DomainError(f"preflight case coverage drift for {case_key}")
    case = _exact(matches[0], {"id", "target", "recipe_sha256", "status"}, f"preflight case {case_key}")
    if case["target"] != target or case["status"] != "ready" or not SHA_RE.fullmatch(case["recipe_sha256"]):
        raise DomainError(f"preflight target/status drift for {case_key}")


def pack_workbench_case(
    candidate_path: Path, preflight_path: Path, domain: str, case_id: str,
    cycle_id: str, evidence_args: list[str], out: Path,
) -> None:
    if domain not in ("workbench-persistence", "workbench-ux") or case_id not in EXPECTED[domain]:
        raise DomainError("workbench case pack domain/case is invalid")
    candidate, _ = _candidate(candidate_path.resolve())
    product_identity = candidate.get("product_identity_sha256")
    if not isinstance(product_identity, str) or not SHA_RE.fullmatch(product_identity):
        raise DomainError("candidate product identity is invalid")
    target, expected = EXPECTED[domain][case_id]
    preflight = preflight_path.resolve()
    _verify_preflight(
        preflight, _sha(preflight), product_identity, f"{domain}/{case_id}", target,
    )
    required = WORKBENCH_EVIDENCE[case_id]
    evidence = []
    paths = []
    for raw in evidence_args:
        if "=" not in raw:
            raise DomainError(f"workbench evidence must be role=path: {raw}")
        role, path_text = raw.split("=", 1)
        path = Path(path_text).resolve()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise DomainError(f"workbench evidence escapes repository: {path}") from exc
        if role in {item["role"] for item in evidence} or role not in required:
            raise DomainError(f"workbench evidence role is duplicate/foreign: {role}")
        if path.is_symlink() or not path.is_file():
            raise DomainError(f"workbench evidence is not a regular file: {path}")
        evidence.append({"role": role, "path": relative, "sha256": _sha(path)})
        paths.append(path)
    if tuple(item["role"] for item in evidence) != tuple(required):
        raise DomainError("workbench evidence pack coverage/order drift")
    parents = {path.parent for path in paths}
    evidence_directory = next(iter(parents)).relative_to(ROOT).as_posix() if len(parents) == 1 else "multiple"
    mutates_media = case_id in {
        "bam-alloc", "chain-write", "dir-write", "save-new", "save-new-scan",
        "save-new-var", "ux-complete",
    }
    receipt = {
        "format": WORKBENCH_CASE_FORMAT,
        "product_identity_sha256": product_identity,
        "build_id": candidate["build_id"],
        "case_id": f"{domain}/{case_id}",
        "target": target,
        "expected": expected,
        "result": expected,
        "cycle_id": cycle_id,
        "attempts": [{
            "index": 1,
            "outcome": "pass",
            "semantic_execution": True,
            "media_content_mutation": mutates_media,
            "evidence_directory": evidence_directory,
            "throwaway_media": mutates_media,
        }],
        "evidence": evidence,
    }
    out_path = out.resolve()
    _write_json_fresh(out_path, receipt)
    try:
        _verify_workbench_case(
            out_path, _sha(out_path), domain, case_id, target, expected,
            cycle_id, candidate, product_identity,
        )
    except Exception:
        out_path.unlink(missing_ok=True)
        raise
    print(f"v2-g5 workbench case receipt: PASS case={domain}/{case_id} product={product_identity[:12]}")


def pack_domain(
    candidate_path: Path, domain: str, bindings: list[str],
    package: Path | None, oracle: Path | None, out: Path,
) -> None:
    candidate_path = candidate_path.resolve()
    candidate, candidate_sha = _candidate(candidate_path)
    expected_cases = list(EXPECTED[domain])
    parsed = []
    for raw in bindings:
        parts = raw.split(",", 3)
        if len(parts) != 4:
            raise DomainError("case binding must be case-id,cycle-id,receipt,preflight")
        case_id, cycle_id, receipt_text, preflight_text = parts
        if case_id in {item[0] for item in parsed}:
            raise DomainError(f"duplicate domain case binding: {case_id}")
        parsed.append((case_id, cycle_id, Path(receipt_text).resolve(), Path(preflight_text).resolve()))
    if [item[0] for item in parsed] != expected_cases:
        raise DomainError("domain pack case coverage/order drift")
    inputs = []
    if domain == "runtime-export":
        if package is None or oracle is None:
            raise DomainError("runtime domain pack requires package and oracle")
        package = package.resolve()
        oracle = oracle.resolve()
        inputs = [
            {"id": "package", "path": package.relative_to(ROOT).as_posix(), "sha256": _sha(package / "manifest.json")},
            {"id": "oracle", "path": oracle.relative_to(ROOT).as_posix(), "sha256": _sha(oracle)},
        ]
    elif package is not None or oracle is not None:
        raise DomainError("Workbench domain pack does not accept shared package inputs")
    cases = []
    for case_id, cycle_id, receipt, preflight in parsed:
        target, expected = EXPECTED[domain][case_id]
        cases.append({
            "id": case_id,
            "target": target,
            "expected": expected,
            "cycle_id": cycle_id,
            "receipt": receipt.relative_to(ROOT).as_posix(),
            "receipt_sha256": _sha(receipt),
            "preflight_receipt": preflight.relative_to(ROOT).as_posix(),
            "preflight_receipt_sha256": _sha(preflight),
        })
    receipt = {
        "format": DOMAIN_RECEIPT_FORMAT,
        "domain": domain,
        "candidate_manifest": candidate_path.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": candidate_sha,
        "verifier": VERIFIER_PATH,
        "verifier_sha256": _sha(ROOT / VERIFIER_PATH),
        "cycle_ids": [item[1] for item in parsed],
        "inputs": inputs,
        "cases": cases,
    }
    out_path = out.resolve()
    _write_json_fresh(out_path, receipt)
    try:
        verify_domain(candidate_path, out_path, domain)
    except Exception:
        out_path.unlink(missing_ok=True)
        raise
    print(f"v2-g5 domain receipt pack: PASS domain={domain} cases={len(cases)}")


def _verify_runtime_suite_product_resume(
    package: Path, oracle: Path, receipts: list[Path],
) -> None:
    """Revalidate historical HW observations across packaging-only changes.

    Product identity and preflight binding are checked by the domain verifier.
    The strict runtime verifier still checks every phase mutation, raw readback,
    cycle id, address, result and evidence file.  Only the historical package
    manifest and oracle digests are rebound in temporary receipt copies.
    """
    try:
        RUNTIME_HW.verify_suite(package, oracle, receipts, None)
        return
    except RUNTIME_HW.HardwareContractError:
        pass

    oracle_value = _load(oracle, "current Runtime hardware oracle")
    manifest_sha = oracle_value.get("manifest_sha256")
    oracle_sha = _sha(oracle)
    if not isinstance(manifest_sha, str) or not SHA_RE.fullmatch(manifest_sha):
        raise DomainError("current Runtime oracle lacks a manifest SHA")

    with tempfile.TemporaryDirectory(prefix="v2-g5-runtime-resume-", dir=ROOT / "build") as raw:
        root = Path(raw)
        normalized: list[Path] = []
        for receipt in receipts:
            value = _load(receipt, "historical Runtime phase receipt")
            phase = value.get("phase")
            if phase not in EXPECTED["runtime-export"]:
                raise DomainError("historical Runtime receipt has an unknown phase")
            phase_dir = root / str(phase)
            shutil.copytree(receipt.parent, phase_dir)
            target = phase_dir / receipt.name
            value["manifest_sha256"] = manifest_sha
            value["oracle_sha256"] = oracle_sha
            target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            normalized.append(target)
        RUNTIME_HW.verify_suite(package, oracle, normalized, None)
    print("v2-g5 runtime receipt resume: PASS product-identical packaging-rebound=2-fields")


def verify_domain(candidate_path: Path, receipt_path: Path, expected_domain: str | None = None) -> dict[str, Any]:
    candidate_path = candidate_path.resolve()
    receipt_path = receipt_path.resolve()
    candidate, candidate_sha = _candidate(candidate_path)
    receipt = _load(receipt_path, "internal G5 domain receipt")
    _exact(
        receipt,
        {
            "format", "domain", "candidate_manifest", "candidate_manifest_sha256",
            "verifier", "verifier_sha256", "cycle_ids", "inputs", "cases",
        },
        "internal G5 domain receipt",
    )
    domain = receipt["domain"]
    if expected_domain is not None and domain != expected_domain:
        raise DomainError("domain receipt identity drift")
    if domain not in EXPECTED:
        raise DomainError(f"unknown G5 domain: {domain}")
    if (
        receipt["format"] != DOMAIN_RECEIPT_FORMAT
        or receipt["candidate_manifest"] != candidate_path.relative_to(ROOT).as_posix()
        or receipt["candidate_manifest_sha256"] != candidate_sha
        or receipt["verifier"] != VERIFIER_PATH
        or receipt["verifier_sha256"] != _sha(ROOT / VERIFIER_PATH)
        or not isinstance(receipt["cycle_ids"], list)
        or not receipt["cycle_ids"]
        or len(receipt["cycle_ids"]) != len(set(receipt["cycle_ids"]))
    ):
        raise DomainError(f"G5 domain {domain} provenance/cycle binding drift")
    inputs = receipt["inputs"]
    if not isinstance(inputs, list):
        raise DomainError(f"G5 domain {domain} inputs must be a list")
    bound_inputs: dict[str, Path] = {}
    for index, raw in enumerate(inputs):
        item = _exact(raw, {"id", "path", "sha256"}, f"G5 domain {domain} input[{index}]")
        if item["id"] in bound_inputs:
            raise DomainError(f"G5 domain {domain} duplicates input {item['id']}")
        label = f"G5 domain {domain} input {item['id']}"
        if domain == "runtime-export" and item["id"] == "package":
            bound_inputs[item["id"]] = _repo_package(item["path"], item["sha256"], label)
        else:
            bound_inputs[item["id"]] = _repo_file(item["path"], item["sha256"], label)
    if domain == "runtime-export" and set(bound_inputs) != {"package", "oracle"}:
        raise DomainError("Runtime domain must bind exactly its package and hardware oracle")
    if domain != "runtime-export" and bound_inputs:
        raise DomainError(f"G5 domain {domain} has unexpected shared inputs")
    cases = receipt["cases"]
    if not isinstance(cases, list) or [item.get("id") for item in cases] != list(EXPECTED[domain]):
        raise DomainError(f"G5 domain {domain} case coverage/order drift")
    runtime_receipts: list[Path] = []
    runtime_cycles: list[str] = []
    for index, raw in enumerate(cases):
        case = _exact(
            raw,
            {
                "id", "target", "expected", "cycle_id", "receipt", "receipt_sha256",
                "preflight_receipt", "preflight_receipt_sha256",
            },
            f"G5 domain {domain} case[{index}]",
        )
        case_id = case["id"]
        target, expected = EXPECTED[domain][case_id]
        if (case["target"], case["expected"]) != (target, expected) or case["cycle_id"] not in receipt["cycle_ids"]:
            raise DomainError(f"G5 domain {domain} case {case_id} contract drift")
        product_identity = candidate.get("product_identity_sha256")
        if not isinstance(product_identity, str) or not SHA_RE.fullmatch(product_identity):
            raise DomainError("candidate product identity is invalid")
        preflight = _repo_file(
            case["preflight_receipt"], case["preflight_receipt_sha256"],
            f"G5 domain {domain} case {case_id} preflight",
        )
        _verify_preflight(
            preflight, case["preflight_receipt_sha256"], product_identity,
            f"{domain}/{case_id}", target,
        )
        native = _repo_file(case["receipt"], case["receipt_sha256"], f"G5 domain {domain} case {case_id} receipt")
        if domain == "runtime-export":
            native_value = _load(native, f"Runtime phase {case_id} receipt")
            operator = native_value.get("operator")
            if native_value.get("phase") != case_id or not isinstance(operator, dict) or operator.get("cycle_id") != case["cycle_id"]:
                raise DomainError(f"Runtime phase {case_id} receipt/cycle drift")
            runtime_receipts.append(native)
            runtime_cycles.append(case["cycle_id"])
        else:
            _verify_workbench_case(
                native, case["receipt_sha256"], domain, case_id, target, expected,
                case["cycle_id"], candidate, product_identity,
            )
    if set(receipt["cycle_ids"]) != {item["cycle_id"] for item in cases}:
        raise DomainError(f"G5 domain {domain} cycle inventory has unused/missing IDs")
    if domain == "runtime-export":
        if len(runtime_cycles) != 4 or len(set(runtime_cycles)) != 4:
            raise DomainError("Runtime domain requires four distinct physical power-cycle IDs")
        _verify_runtime_suite_product_resume(
            bound_inputs["package"], bound_inputs["oracle"], runtime_receipts,
        )
    print(f"v2-g5 domain receipt: PASS domain={domain} cases={len(cases)}")
    return receipt


def selftest() -> None:
    # The live proof package test is intentionally handled by the Make target.
    if RUNTIME_PACKAGE_FORMAT != RUNTIME_HW.INTERNAL_V2_PACKAGE_FORMAT:
        raise DomainError("runtime package format drift")
    data = b"profile=dialect-v2-runtime-core-proof\nabi_profile=dialect-v2\nshippable=false\nhardware_g5_claim=none\nsource_commit=" + b"1" * 40 + b"\n"
    fields = _profile_fields(data)
    if fields["source_commit"] != "1" * 40:
        raise DomainError("profile parser selftest failed")
    if set(EXPECTED) != {"runtime-export", "workbench-persistence", "workbench-ux"}:
        raise DomainError("domain inventory selftest failed")
    if set(WORKBENCH_EVIDENCE) != set(EXPECTED["workbench-persistence"]) | set(EXPECTED["workbench-ux"]):
        raise DomainError("Workbench case oracle inventory selftest failed")
    if WORKBENCH_EVIDENCE["ux-complete"]["persistence"] != (
        "((\"(defun ap6-persisted () 612)\") 612 (\"(defun ap6-b () 613)\") 613)"
    ):
        raise DomainError("Workbench UX persistence oracle selftest failed")
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v2-g5-package-binding-", dir=ROOT / "build") as raw:
        package = Path(raw) / "runtime-package"
        package.mkdir()
        manifest = package / "manifest.json"
        manifest.write_text("{}\n", encoding="ascii")
        relative = package.relative_to(ROOT).as_posix()
        if _repo_package(relative, _sha(manifest), "selftest package") != package.resolve():
            raise DomainError("runtime package directory binding selftest failed")
        try:
            _repo_package(relative, "0" * 64, "selftest package")
        except DomainError:
            pass
        else:
            raise DomainError("runtime package directory binding accepted a false manifest SHA")
    print("v2-g5 domain verifiers: SELFTEST PASS domains=3 runtime-package=bound")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    pack = sub.add_parser("pack-runtime")
    pack.add_argument("--proof-dir", type=Path, required=True)
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--nm", type=Path, required=True)
    pack.add_argument("--objcopy", type=Path, required=True)
    verify = sub.add_parser("verify-runtime-package")
    verify.add_argument("--package", type=Path, required=True)
    case_pack = sub.add_parser("pack-workbench-case")
    case_pack.add_argument("--candidate", type=Path, required=True)
    case_pack.add_argument(
        "--domain", choices=("workbench-persistence", "workbench-ux"), required=True,
    )
    case_pack.add_argument("--case-id", required=True)
    case_pack.add_argument("--cycle-id", required=True)
    case_pack.add_argument("--preflight", type=Path, required=True)
    case_pack.add_argument("--evidence", action="append", default=[], required=True)
    case_pack.add_argument("--out", type=Path, required=True)
    domain_pack = sub.add_parser("pack-domain")
    domain_pack.add_argument("--candidate", type=Path, required=True)
    domain_pack.add_argument("--domain", choices=sorted(EXPECTED), required=True)
    domain_pack.add_argument("--case-binding", action="append", default=[], required=True)
    domain_pack.add_argument("--package", type=Path)
    domain_pack.add_argument("--oracle", type=Path)
    domain_pack.add_argument("--out", type=Path, required=True)
    domain = sub.add_parser("verify-domain")
    domain.add_argument("--candidate", type=Path, required=True)
    domain.add_argument("--receipt", type=Path, required=True)
    domain.add_argument("--domain", choices=sorted(EXPECTED))
    args = parser.parse_args(argv)
    if args.command == "selftest":
        selftest()
    elif args.command == "pack-runtime":
        pack_runtime(args.proof_dir, args.out, args.nm, args.objcopy)
    elif args.command == "verify-runtime-package":
        verify_runtime_package(args.package)
    elif args.command == "pack-workbench-case":
        pack_workbench_case(
            args.candidate, args.preflight, args.domain, args.case_id,
            args.cycle_id, args.evidence, args.out,
        )
    elif args.command == "pack-domain":
        pack_domain(
            args.candidate, args.domain, args.case_binding,
            args.package, args.oracle, args.out,
        )
    else:
        verify_domain(args.candidate, args.receipt, args.domain)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DomainError, RUNTIME_HW.HardwareContractError, PRELOAD.PreloadError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"v2-g5-domain-verifiers: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
