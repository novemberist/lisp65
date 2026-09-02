#!/usr/bin/env python3
"""Bind the R6 Ship to the exact 15-case preflight and fail-closed G6 receipts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

import g6_two_media_oracle as TWO_MEDIA


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import history_transport_rewrite as TRANSPORT  # noqa: E402

CONTRACT = ROOT / "config/r6-g6-harness.json"
HARDWARE_PROFILE = ROOT / "config/g6-hardware-profile.json"
R7_PREREQUISITES = ROOT / "config/r7-release-prerequisites.json"
R7_PREREQUISITE_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites-receipt.json"
R7_PREREQUISITE_MANIFEST = ROOT / "tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites.json"
PACKER_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-ship-wave3-packer-receipt.json"
TRACKED_PREFLIGHT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-wave3-static-preflight-receipt.json"
PROFILE_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-wave3-profile-applicability-receipt.json"
TOOL = ROOT / "tools/host-lisp/r6_g6.py"
TWO_MEDIA_ORACLE = ROOT / "tools/host-lisp/g6_two_media_oracle.py"
FORMAT = "lisp65-r6-g6-harness-v2"
PREFLIGHT_FORMAT = "lisp65-r6-g6-static-preflight-v2"
PROFILE_RECEIPT_FORMAT = "lisp65-r6-g6-profile-applicability-receipt-v1"
SHEET_FORMAT = "lisp65-r6-g6-execution-sheet-v2"
CASE_FORMAT = "lisp65-r6-g6-case-receipt-v2"
CASE_REBIND_FORMAT = "lisp65-r6-g6-case-rebind-v1"
TOP_FORMAT = "lisp65-r6-g6-hardware-receipt-v2"
PRODUCT_SET = "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024"
ARTIFACT_COUNT = 14
R4_ID = "r4-product-candidate-726bdf8"
SEALED_STDLIB_MANIFEST = "payload/build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
OFFLINE_ARCHIVE = os.environ.get("LISP65_G6_OFFLINE_ARCHIVE") == "1"

FREEZER_PUBLIC_TRIGGER = {
    "entrypoint": "m65d-save",
    "form": '(m65d-save "g6swap" (progn (poke 208 32 2) g6src))',
    "signal": "red-border-immediately-before-public-entry",
    "operator_action": "on-red-open-freezer-and-mount-media-b",
    "acceptance": "terminal-return-12-and-persistent-status-12-plus-two-media-oracle",
    "nonacceptance": "any-other-result-or-private-helper-use-is-receiptless",
    "forbidden_symbol_prefixes": ["%m65d-"],
}


class G6Error(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise G6Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G6Error(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise G6Error(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise G6Error(f"{label} must contain an object")
    return value


def load_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise G6Error(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise G6Error(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise G6Error(f"{label} keys drift: {actual}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise G6Error(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise G6Error(f"{label} is not a canonical relative path")
    return value


def token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not TOKEN_RE.fullmatch(value):
        raise G6Error(f"{label} must use [A-Za-z0-9._-]+")
    return value


def canonical_commit(value: str, *, historical_verification: bool = False) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise G6Error("source commit must be a full lowercase Git commit")
    if OFFLINE_ARCHIVE and historical_verification:
        return value
    transport_commit = TRANSPORT.resolve_commit(value)
    completed = subprocess.run(
        ["git", "rev-parse", f"{transport_commit}^{{commit}}"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode or completed.stdout.strip() != transport_commit:
        raise G6Error("source commit is not canonical in this repository")
    for path in (TOOL, TWO_MEDIA_ORACLE, CONTRACT, HARDWARE_PROFILE, R7_PREREQUISITES):
        name = path.relative_to(ROOT).as_posix()
        materialized = subprocess.run(
            ["git", "show", f"{transport_commit}:{name}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if materialized.returncode:
            raise G6Error(f"source commit lacks G6 input: {name}")
        if historical_verification and path in {TOOL, R7_PREREQUISITES}:
            continue
        if materialized.stdout != path.read_bytes():
            raise G6Error(f"source commit does not bind current G6 input: {name}")
    return value


def canonical_commit_date(value: str) -> str:
    transport_commit = TRANSPORT.resolve_commit(value)
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cs", transport_commit], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    result = completed.stdout.strip()
    if completed.returncode or not DATE_RE.fullmatch(result):
        raise G6Error("source commit date is unavailable or non-canonical")
    return result


def hardware_profile() -> dict[str, Any]:
    value = load(HARDWARE_PROFILE, "G6 hardware profile")
    exact(
        value,
        {
            "format", "version", "id", "status", "decided_on", "transport", "G6",
            "product_code_path_audit", "receipt_policy", "upstream",
        },
        "G6 hardware profile",
    )
    g6 = exact(value["G6"], {"applicable_hardware_cases", "not_applicable", "claim"}, "G6 profile cases")
    not_applicable = exact(g6["not_applicable"], {"case_id", "reason", "prohibited_substitute"}, "G6 profile N/A")
    applicable = g6["applicable_hardware_cases"]
    audit = value["product_code_path_audit"]
    if (
        value["format"] != "lisp65-g6-hardware-profile-v1" or value["version"] != 1
        or value["id"] != "stock-core-sd-d81" or value["status"] != "owner-approved"
        or not isinstance(applicable, list) or len(applicable) != 5 or len(set(applicable)) != 5
        or not_applicable["case_id"] != "product-medium-physical-write-protect"
        or not_applicable["prohibited_substitute"] != "no-JTAG-poke-core-modification-or-synthetic-PASS"
        or audit.get("physical_write_protect_signal_branches") != []
        or "5/5 anwendbare Hardwarefälle bestanden" not in g6["claim"]
        or "n/a" not in g6["claim"]
    ):
        raise G6Error("G6 hardware profile semantic drift")
    for path in (ROOT / "src/f011_context.h", ROOT / "src/io.c", ROOT / "lib/m65-disk.lisp"):
        text = path.read_text(encoding="utf-8")
        if "D0WP" in text or "D1WP" in text:
            raise G6Error(f"dedicated write-protect signal path appeared without profile audit: {path}")
    return value


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R6/G6 harness contract")
    exact(
        value,
        {"format", "version", "id", "status", "hardware_profile", "ship", "execution", "cases", "claims_before_execution"},
        "R6/G6 harness contract",
    )
    if (
        value["format"] != FORMAT or value["version"] != 2
        or value["id"] != "r6-exact-15-case-preflight-and-g6"
        or value["status"] != "approved-for-static-preflight"
    ):
        raise G6Error("R6/G6 harness identity drift")
    profile_binding = exact(value["hardware_profile"], {"path", "sha256"}, "G6 hardware profile binding")
    if (
        profile_binding != {
            "path": HARDWARE_PROFILE.relative_to(ROOT).as_posix(), "sha256": sha(HARDWARE_PROFILE),
        }
        or hardware_profile()["id"] != "stock-core-sd-d81"
    ):
        raise G6Error("G6 hardware profile binding drift")
    ship = exact(
        value["ship"],
        {
            "path", "manifest_sha256", "package_set_sha256", "product_artifact_set_sha256",
            "product_d81_sha256", "work_d81_sha256", "r4_archive_sha256", "r5_archive_sha256",
        },
        "R6/G6 ship binding",
    )
    if (
        ship["path"] != "build/r6/ship"
        or ship["product_artifact_set_sha256"] != PRODUCT_SET
        or any(not SHA_RE.fullmatch(ship[key]) for key in ship if key.endswith("sha256"))
    ):
        raise G6Error("R6/G6 ship binding drift")
    execution = exact(
        value["execution"],
        {
            "device", "machine_serial_source", "expected_machine_serial", "m65", "mega65_ftp",
            "repl_runner", "repl_verifier", "case_verifier", "two_media_oracle",
            "core_binding", "host_free_cold_start",
        },
        "R6/G6 execution binding",
    )
    for key in ("m65", "mega65_ftp", "repl_runner", "repl_verifier", "case_verifier", "two_media_oracle"):
        relative(execution[key], f"execution {key}")
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != 15:
        raise G6Error("R6/G6 contract must contain exactly 15 cases")
    ids: set[str] = set()
    counts = {"emulator-valid": 0, "hardware-only": 0}
    for index, raw in enumerate(cases):
        raw_id = raw.get("id") if isinstance(raw, dict) else None
        keys = {"id", "fidelity", "gate", "target", "procedure", "required_roles", "required_evidence"}
        if raw_id == "mid-write-media-swap-abort":
            keys.add("manual_trigger")
        row = exact(
            raw,
            keys,
            f"R6/G6 case[{index}]",
        )
        case_id = token(row["id"], f"case[{index}].id")
        if case_id in ids or row["fidelity"] not in counts:
            raise G6Error("R6/G6 case identity/fidelity drift")
        ids.add(case_id)
        counts[row["fidelity"]] += 1
        if row["fidelity"] == "emulator-valid":
            expected = ("G3", "sealed-r4-g3", "sealed-pass")
        elif case_id == "product-medium-physical-write-protect":
            expected = ("G6", "profile-applicability-receipt", "profile-not-applicable")
        else:
            expected = ("G6", "operator-assisted-hardware", None)
        if row["gate"] != expected[0] or row["target"] != expected[1] or (expected[2] and row["procedure"] != expected[2]):
            raise G6Error(f"R6/G6 route drift: {case_id}")
        if (
            not isinstance(row["required_roles"], list) or not row["required_roles"]
            or len(row["required_roles"]) != len(set(row["required_roles"]))
            or not isinstance(row["required_evidence"], list) or not row["required_evidence"]
            or len(row["required_evidence"]) != len(set(row["required_evidence"]))
        ):
            raise G6Error(f"R6/G6 roles/evidence drift: {case_id}")
        if case_id == "mid-write-media-swap-abort":
            trigger = row["manual_trigger"]
            if trigger != FREEZER_PUBLIC_TRIGGER or "%m65d-" in trigger.get("form", ""):
                raise G6Error("R6/G6 Freezer trigger is not the exact public M65D procedure")
    if counts != {"emulator-valid": 9, "hardware-only": 6}:
        raise G6Error(f"R6/G6 fidelity counts drift: {counts}")
    expected_claims = {
        "G3": "passed-emulator-prefilter-only", "G5": "passed-for-product-artifact-set",
        "G6": "not-run(5/5-applicable); execution=single-device; product-medium-physical-write-protect=n/a-no-physical-medium-in-SD-D81-configuration",
        "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
        "hardware_boot_cases": "not-run(5/5-applicable); execution=single-device; n/a(1/1-profile-bound)",
        "release": "not-release-capable",
    }
    if value["claims_before_execution"] != expected_claims:
        raise G6Error("R6/G6 pre-execution claim drift")
    return value


def r7_prerequisites() -> dict[str, Any]:
    value = load(R7_PREREQUISITES, "R7 prerequisites")
    exact(value, {"format", "version", "status", "items", "evidence", "G6_effect", "R7_effect"}, "R7 prerequisites")
    evidence = exact(value["evidence"], {"receipt", "receipt_sha256", "manifest", "manifest_sha256"}, "R7 prerequisite evidence")
    if (
        value["format"] != "lisp65-r7-release-prerequisites-v1" or value["version"] != 1
        or value["status"] != "closed-ready-for-R7" or value["G6_effect"] != "none"
        or value["R7_effect"] != "prerequisites-satisfied-release-promotion-still-required"
        or not isinstance(value["items"], list) or len(value["items"]) != 2
        or {item.get("id") for item in value["items"]} != {"public-manifest-role-paths", "packed-on-source-commit-time"}
        or any(item.get("status") != "closed" for item in value["items"])
        or evidence != {
            "receipt": R7_PREREQUISITE_RECEIPT.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(R7_PREREQUISITE_RECEIPT),
            "manifest": R7_PREREQUISITE_MANIFEST.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(R7_PREREQUISITE_MANIFEST),
        }
    ):
        raise G6Error("R7 prerequisite contract drift")
    return value


def run_ship_verifier(ship_root: Path) -> dict[str, Any]:
    verifier = ship_root / "verify.py"
    if ship_root.is_symlink() or not ship_root.is_dir() or verifier.is_symlink() or not verifier.is_file():
        raise G6Error("R6 ship directory/verifier is missing")
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=ship_root,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise G6Error(f"R6 ship offline verifier failed: {completed.stdout.strip()}")
    return load(ship_root / "manifest.json", "R6 ship manifest")


def package_artifacts(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = manifest.get("artifacts")
    if not isinstance(rows, list) or len(rows) != ARTIFACT_COUNT:
        raise G6Error("R6 manifest artifact inventory drift")
    by_role = {row.get("role"): row for row in rows if isinstance(row, dict)}
    if len(by_role) != ARTIFACT_COUNT:
        raise G6Error("R6 manifest artifact roles drift")
    return by_role


def profile_receipt_value(ship_root: Path) -> dict[str, Any]:
    configured = contract()
    profile = hardware_profile()
    manifest = run_ship_verifier(ship_root)
    manifest_path = ship_root / "manifest.json"
    if (
        sha(manifest_path) != configured["ship"]["manifest_sha256"]
        or manifest.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
    ):
        raise G6Error("profile receipt Ship/product binding drift")
    sources = []
    for path in (ROOT / "src/f011_context.h", ROOT / "src/io.c", ROOT / "lib/m65-disk.lisp"):
        sources.append({
            "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha(path),
        })
    return {
        "format": PROFILE_RECEIPT_FORMAT,
        "version": 1,
        "status": "not-applicable-profile-bound",
        "case_id": "product-medium-physical-write-protect",
        "hardware_profile": {
            "path": HARDWARE_PROFILE.relative_to(ROOT).as_posix(),
            "sha256": sha(HARDWARE_PROFILE),
            "id": profile["id"],
        },
        "ship": {
            "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(manifest_path),
            "package_set_sha256": manifest["package_set_sha256"],
            "product_artifact_set_sha256": PRODUCT_SET,
            "product_d81_sha256": configured["ship"]["product_d81_sha256"],
        },
        "applicability": {
            "physical_floppy_present": False,
            "stock_freezer_virtual_image_write_protect_control": False,
            "result": "not-applicable-no-physical-medium-in-SD-D81-configuration",
            "synthetic_pass_attempted": False,
        },
        "product_code_path_audit": {
            "dedicated_F011_write_protect_signal_paths": [],
            "statement": "no product code path reads or branches on a dedicated F011 write-protect signal",
            "D68B_path": "opaque mounted-image transaction-token equality only; not a write-protect decision",
            "coverage": "D68B token behavior remains covered by host phase fixtures and the applicable mid-write-media-swap-abort hardware case",
            "sources": sources,
        },
        "claim": profile["G6"]["claim"],
        "result": "profile-not-applicable",
    }


def write_profile_receipt(*, ship_root: Path, output: Path, replace: bool = False) -> dict[str, Any]:
    value = profile_receipt_value(ship_root)
    data = canonical(value)
    if output.exists() or output.is_symlink():
        if not replace or output.is_symlink() or not output.is_file():
            raise G6Error(f"profile receipt output must be fresh: {output}")
        output.write_bytes(data)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    verify_profile_receipt(output, ship_root=ship_root)
    print(
        "r6-g6: PROFILE N/A PASS applicable=5/5 "
        "product-medium-physical-write-protect=n/a profile=stock-core-sd-d81"
    )
    return value


def verify_profile_receipt(path: Path, *, ship_root: Path) -> dict[str, Any]:
    value = load(path, "G6 profile applicability receipt")
    expected = profile_receipt_value(ship_root)
    if value != expected:
        raise G6Error("G6 profile applicability receipt semantic or byte binding drift")
    print(
        f"r6-g6: PROFILE CHECK PASS manifest={value['ship']['manifest_sha256'][:12]} "
        "applicable=5 n/a=1"
    )
    return value


def verify_environment(value: dict[str, Any]) -> dict[str, Any]:
    execution = value["execution"]
    rows: dict[str, Any] = {}
    for key in ("m65", "mega65_ftp", "repl_runner", "repl_verifier", "case_verifier", "two_media_oracle"):
        path = ROOT / execution[key]
        if path.is_symlink() or not path.is_file() or (key in {"m65", "mega65_ftp", "repl_runner"} and not os.access(path, os.X_OK)):
            raise G6Error(f"G6 execution tool unavailable: {key}")
        rows[key] = {"path": execution[key], "bytes": path.stat().st_size, "sha256": sha(path)}
    serial_path = Path(execution["machine_serial_source"])
    if serial_path.is_symlink() or not serial_path.is_file():
        raise G6Error("G6 machine serial source unavailable")
    serial = serial_path.read_text(encoding="ascii").strip()
    if serial != execution["expected_machine_serial"]:
        raise G6Error("G6 machine serial drift")
    if not Path(execution["device"]).exists():
        raise G6Error("G6 serial/JTAG device is absent")
    rows["machine"] = {"serial": serial, "device": execution["device"], "core": "bind-on-first-passed-case"}
    return rows


def verify_archived_environment_binding(rows: Any, value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rows, dict):
        raise G6Error("archived G6 environment binding is malformed")
    execution = value["execution"]
    expected = {"m65", "mega65_ftp", "repl_runner", "repl_verifier", "case_verifier", "two_media_oracle", "machine"}
    if set(rows) != expected:
        raise G6Error("archived G6 environment inventory drift")
    for key in expected - {"machine"}:
        row = exact(rows[key], {"path", "bytes", "sha256"}, f"archived execution {key}")
        if (
            row["path"] != execution[key]
            or not isinstance(row["bytes"], int) or row["bytes"] < 1
            or not isinstance(row["sha256"], str) or not SHA_RE.fullmatch(row["sha256"])
        ):
            raise G6Error(f"archived G6 execution binding drift: {key}")
    machine = exact(rows["machine"], {"serial", "device", "core"}, "archived G6 machine binding")
    if machine != {
        "serial": execution["expected_machine_serial"],
        "device": execution["device"],
        "core": "bind-on-first-passed-case",
    }:
        raise G6Error("archived G6 machine binding drift")
    return rows


def sealed_case_state(ship_root: Path, value: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    g3_path = ship_root / "evidence/g3-emulator-receipt.json"
    matrix_path = ship_root / "evidence/r3-boot-cases.json"
    g3 = load(g3_path, "sealed G3 receipt")
    matrix = load(matrix_path, "sealed 15-case matrix")
    matrix_rows = matrix.get("cases")
    g3_rows = g3.get("cases")
    if not isinstance(matrix_rows, list) or len(matrix_rows) != 15 or not isinstance(g3_rows, list) or len(g3_rows) != 15:
        raise G6Error("sealed G3/matrix case count drift")
    contract_ids = [row["id"] for row in value["cases"]]
    if [row.get("id") for row in matrix_rows] != contract_ids or [row.get("id") for row in g3_rows] != contract_ids:
        raise G6Error("sealed/local G6 matrix order drift")
    statuses: dict[str, str] = {}
    for matrix_row, g3_row in zip(matrix_rows, g3_rows, strict=True):
        if matrix_row["fidelity"] == "emulator-valid":
            if g3_row.get("status") != "pass":
                raise G6Error(f"sealed G3 case is not pass: {matrix_row['id']}")
            statuses[matrix_row["id"]] = "sealed-pass"
        else:
            if g3_row.get("status") != "not-run":
                raise G6Error(f"sealed hardware case is not not-run: {matrix_row['id']}")
            statuses[matrix_row["id"]] = "ready-not-run"
    return statuses, {"path": "evidence/g3-emulator-receipt.json", "sha256": sha(g3_path)}


def preflight(*, source_commit: str, ship_root: Path, output: Path, replace_not_run: bool = False) -> dict[str, Any]:
    source_commit = canonical_commit(source_commit)
    value = contract()
    r7 = r7_prerequisites()
    if r7["status"] != "closed-ready-for-R7":
        raise G6Error("R7 prerequisites are not closed for the package-only preflight")
    manifest = run_ship_verifier(ship_root)
    ship = value["ship"]
    if (
        sha(ship_root / "manifest.json") != ship["manifest_sha256"]
        or manifest.get("package_set_sha256") != ship["package_set_sha256"]
        or manifest.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        or manifest.get("gates") != value["claims_before_execution"]
    ):
        raise G6Error("R6 Ship/preflight identity or claim drift")
    packer_receipt = load(PACKER_RECEIPT, "R6 packer receipt")
    if (
        packer_receipt.get("package", {}).get("manifest_sha256") != ship["manifest_sha256"]
        or packer_receipt.get("package", {}).get("package_set_sha256") != ship["package_set_sha256"]
        or packer_receipt.get("claims") != value["claims_before_execution"]
    ):
        raise G6Error("R6 packer receipt/preflight drift")
    artifacts = package_artifacts(manifest)
    statuses, g3_binding = sealed_case_state(ship_root, value)
    profile_receipt = verify_profile_receipt(PROFILE_RECEIPT, ship_root=ship_root)
    statuses["product-medium-physical-write-protect"] = "profile-not-applicable"
    environment = verify_environment(value)
    case_rows: list[dict[str, Any]] = []
    for row in value["cases"]:
        missing = sorted(set(row["required_roles"]) - set(artifacts))
        if missing:
            raise G6Error(f"case {row['id']} refers to missing roles: {missing}")
        case_row = {
            "id": row["id"], "fidelity": row["fidelity"], "gate": row["gate"],
            "target": row["target"], "procedure": row["procedure"],
            "verifier": value["execution"]["case_verifier"],
            "required_roles": row["required_roles"], "required_evidence": row["required_evidence"],
            "artifact_bindings": [
                {"role": role, "ship_path": artifacts[role]["ship_path"], "sha256": artifacts[role]["sha256"]}
                for role in row["required_roles"]
            ],
            "status": statuses[row["id"]],
        }
        if "manual_trigger" in row:
            case_row["manual_trigger"] = row["manual_trigger"]
        case_rows.append(case_row)
    receipt = {
        "format": PREFLIGHT_FORMAT, "version": 2, "id": "r6-g6-static-preflight",
        "status": "passed-hardware-not-run", "source_commit": source_commit,
        "measured_on": canonical_commit_date(source_commit),
        "contract": {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT)},
        "ship": {
            "path": ship["path"], "manifest_sha256": ship["manifest_sha256"],
            "package_set_sha256": ship["package_set_sha256"],
            "product_artifact_set_sha256": PRODUCT_SET, "offline_verifier": "passed",
        },
        "hardware_profile": {
            "path": HARDWARE_PROFILE.relative_to(ROOT).as_posix(),
            "sha256": sha(HARDWARE_PROFILE),
            "id": hardware_profile()["id"],
            "applicability_receipt": PROFILE_RECEIPT.relative_to(ROOT).as_posix(),
            "applicability_receipt_sha256": sha(PROFILE_RECEIPT),
            "bound_manifest_sha256": profile_receipt["ship"]["manifest_sha256"],
        },
        "sealed_evidence": {
            "G3": g3_binding,
            "R4_archive_sha256": ship["r4_archive_sha256"],
            "R5_archive_sha256": ship["r5_archive_sha256"],
            "G5": "passed-14-of-14",
        },
        "environment": environment,
        "counts": {"total": 15, "sealed_G3_pass": 9, "G6_ready_not_run": 5, "G6_profile_not_applicable": 1},
        "cases": case_rows,
        "R7_prerequisites": {
            "path": R7_PREREQUISITES.relative_to(ROOT).as_posix(), "sha256": sha(R7_PREREQUISITES),
            "open": [item["id"] for item in r7["items"] if item["status"] != "closed"],
            "G6_effect": "none",
        },
        "claims": value["claims_before_execution"], "result": "passed",
    }
    data = canonical(receipt)
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file():
            raise G6Error(f"refusing to overwrite non-regular G6 preflight: {output}")
        if output.read_bytes() != data:
            old = load(output, "superseded G6 preflight")
            replaceable = (
                replace_not_run and output.resolve() == TRACKED_PREFLIGHT.resolve()
                and old.get("format") == PREFLIGHT_FORMAT and old.get("id") == "r6-g6-static-preflight"
                and old.get("status") == "passed-hardware-not-run" and old.get("result") == "passed"
                and old.get("ship", {}).get("product_artifact_set_sha256") == PRODUCT_SET
                and old.get("counts", {}).get("G6_ready_not_run") == 5
                and old.get("counts", {}).get("G6_profile_not_applicable") == 1
                and old.get("claims", {}).get("G6") == value["claims_before_execution"]["G6"]
                and old.get("claims", {}).get("hardware_boot_cases") == value["claims_before_execution"]["hardware_boot_cases"]
                and old.get("claims", {}).get("release") == "not-release-capable"
            )
            if not replaceable:
                raise G6Error(f"refusing to overwrite differing G6 preflight: {output}")
            output.write_bytes(data)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    print(
        f"r6-g6: PREFLIGHT PASS cases=15 G3=9/9-sealed G6=0/5-ready WP=n/a "
        f"product={PRODUCT_SET} release=no"
    )
    return receipt


def verify_preflight(path: Path, *, require_ship: bool) -> dict[str, Any]:
    value = load(path, "R6/G6 static preflight")
    exact(
        value,
        {
            "format", "version", "id", "status", "source_commit", "measured_on", "contract",
            "ship", "hardware_profile", "sealed_evidence", "environment", "counts", "cases", "R7_prerequisites",
            "claims", "result",
        },
        "R6/G6 static preflight",
    )
    source_commit = canonical_commit(
        value["source_commit"], historical_verification=True,
    )
    configured = contract()
    measured_on_valid = (
        isinstance(value["measured_on"], str) and DATE_RE.fullmatch(value["measured_on"])
        if OFFLINE_ARCHIVE
        else value["measured_on"] == canonical_commit_date(source_commit)
    )
    environment_valid = (
        verify_archived_environment_binding(value["environment"], configured) == value["environment"]
        if OFFLINE_ARCHIVE
        else value["environment"] == verify_environment(configured)
    )
    if (
        value["format"] != PREFLIGHT_FORMAT or value["version"] != 2
        or value["id"] != "r6-g6-static-preflight" or value["status"] != "passed-hardware-not-run"
        or not measured_on_valid or value["result"] != "passed"
        or value["contract"] != {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT)}
        or value["counts"] != {"total": 15, "sealed_G3_pass": 9, "G6_ready_not_run": 5, "G6_profile_not_applicable": 1}
        or value["claims"] != configured["claims_before_execution"]
        or len(value["cases"]) != 15
        or not environment_valid
        or sum(row.get("status") == "sealed-pass" for row in value["cases"]) != 9
        or sum(row.get("status") == "ready-not-run" for row in value["cases"]) != 5
        or sum(row.get("status") == "profile-not-applicable" for row in value["cases"]) != 1
    ):
        raise G6Error("R6/G6 static preflight semantic drift")
    configured_rows = {row["id"]: row for row in configured["cases"]}
    for row in value["cases"]:
        configured_row = configured_rows.get(row.get("id"))
        if configured_row is None:
            raise G6Error("R6/G6 preflight contains an unknown case")
        if row.get("manual_trigger") != configured_row.get("manual_trigger"):
            raise G6Error(f"R6/G6 preflight manual-procedure drift: {row.get('id')}")
    profile_row = exact(
        value["hardware_profile"],
        {"path", "sha256", "id", "applicability_receipt", "applicability_receipt_sha256", "bound_manifest_sha256"},
        "G6 preflight hardware profile",
    )
    if (
        profile_row["path"] != HARDWARE_PROFILE.relative_to(ROOT).as_posix()
        or profile_row["sha256"] != sha(HARDWARE_PROFILE)
        or profile_row["id"] != hardware_profile()["id"]
        or profile_row["applicability_receipt"] != PROFILE_RECEIPT.relative_to(ROOT).as_posix()
        or profile_row["applicability_receipt_sha256"] != sha(PROFILE_RECEIPT)
        or profile_row["bound_manifest_sha256"] != configured["ship"]["manifest_sha256"]
    ):
        raise G6Error("R6/G6 preflight profile binding drift")
    verify_profile_receipt(PROFILE_RECEIPT, ship_root=ROOT / configured["ship"]["path"])
    if require_ship:
        ship_root = ROOT / configured["ship"]["path"]
        manifest = run_ship_verifier(ship_root)
        if (
            sha(ship_root / "manifest.json") != value["ship"]["manifest_sha256"]
            or manifest.get("package_set_sha256") != value["ship"]["package_set_sha256"]
        ):
            raise G6Error("R6/G6 preflight live Ship drift")
    print(f"r6-g6: PREFLIGHT CHECK PASS source={source_commit[:12]} cases=15 G6=0/5 WP=n/a")
    return value


def find_case(case_id: str) -> dict[str, Any]:
    value = contract()
    row = next((item for item in value["cases"] if item["id"] == case_id), None)
    if (
        row is None or row["fidelity"] != "hardware-only"
        or row["target"] != "operator-assisted-hardware"
    ):
        raise G6Error(f"not a G6 hardware case: {case_id}")
    return row


def validate_bank5_post_commit(
    before: bytes, after: bytes, *, stdlib_bytes: int, slots: list[int]
) -> dict[str, int | bool]:
    if len(before) != len(after) or stdlib_bytes <= 0 or stdlib_bytes > len(before):
        raise G6Error("Bank-5 post-commit envelope drift")
    allowed: set[int] = set()
    seen: set[int] = set()
    for offset in slots:
        if offset < 0 or offset + 2 > stdlib_bytes or offset in seen:
            raise G6Error("Bank-5 literal patch range/identity drift")
        seen.add(offset)
        allowed.update((offset, offset + 1))
    differences = {index for index, (left, right) in enumerate(zip(before, after, strict=True)) if left != right}
    outside = differences - allowed
    changed_slots = sum(before[offset:offset + 2] != after[offset:offset + 2] for offset in slots)
    if outside or not changed_slots or before[stdlib_bytes:] != after[stdlib_bytes:]:
        raise G6Error(
            f"Bank-5 post-commit mutation escaped contract: outside={len(outside)} "
            f"changed_slots={changed_slots}"
        )
    return {
        "changed_patch_slots": changed_slots, "changed_bytes": len(differences),
        "changed_bytes_outside_patch_slots": 0, "overlay_tail_byte_identical": True,
    }


def validate_bufsel_context(precondition: bytes, postcondition: bytes) -> None:
    if precondition != b"\x80":
        raise G6Error("work persistence did not bind the forced D689=0x80 precondition")
    if postcondition != b"\x00":
        raise G6Error("work persistence did not prove F011 buffer ownership after the transaction")


def validate_user_media_identity(value: dict[str, Any], label: str) -> tuple[str, str]:
    exact(
        value,
        {
            "format", "version", "disk_name", "disk_id", "valid_1581",
            "product_boot_signature", "medium_sha256",
        },
        label,
    )
    if (
        value["format"] != "lisp65-g6-user-media-identity-v1"
        or value["version"] != 1
        or not isinstance(value["disk_name"], str) or not value["disk_name"]
        or not isinstance(value["disk_id"], str) or not value["disk_id"]
        or value["valid_1581"] is not True
        or value["product_boot_signature"] is not False
        or not SHA_RE.fullmatch(value["medium_sha256"])
    ):
        raise G6Error(f"{label} is not a valid non-product 1581 identity")
    return value["disk_name"], value["disk_id"]


def validate_phase_injection_report(value: dict[str, Any]) -> None:
    exact(value, {"format", "suites"}, "phase-injection report")
    suites = value["suites"]
    if value["format"] != "lisp65-bytecode-p0-observations-v1" or not isinstance(suites, list) or len(suites) != 1:
        raise G6Error("phase-injection report envelope drift")
    observations = suites[0].get("observations") if isinstance(suites[0], dict) else None
    if not isinstance(observations, list):
        raise G6Error("phase-injection observations are missing")
    by_name = {
        row.get("name"): row for row in observations
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    planning_expected = {
        "m65d-media-change-during-planning-read-terminal": (True, 12),
        "m65d-planning-read-failure-with-stable-token-stays-invalid": (False, 6),
    }
    for name, (token_changed, classified_status) in planning_expected.items():
        row = by_name.get(name)
        oracle = row.get("planning_read_guard_oracle") if isinstance(row, dict) else None
        if (
            not isinstance(oracle, dict)
            or row.get("result") != str(classified_status)
            or oracle != {
                "result": "pass",
                "read_failure_status": 6,
                "mount_token_changed": token_changed,
                "classified_status": classified_status,
                "persistent_status": classified_status,
                "status_state_synchronized": True,
                "partial_write_latched": False,
                "disk_write_count": 0,
            }
        ):
            raise G6Error(f"planning-read guard oracle drift: {name}")
    expected = {
        "m65d-media-change-before-data-write-terminal": ("before-data-write", 1, []),
        "m65d-media-change-before-bam-write-terminal": ("before-bam-write", 2, ["T1/S0"]),
        "m65d-media-change-before-directory-write-terminal": (
            "before-directory-write", 3, ["T1/S0", "T40/S1"],
        ),
    }
    for name, (phase, operation, changed) in expected.items():
        row = by_name.get(name)
        oracle = row.get("two_media_phase_oracle") if isinstance(row, dict) else None
        if (
            not isinstance(oracle, dict) or row.get("result") != "(12 t)"
            or oracle.get("result") != "pass" or oracle.get("phase") != phase
            or oracle.get("terminal_status") != 12
            or oracle.get("injected_write_operation") != operation
            or oracle.get("source_changed_sectors") != changed
            or oracle.get("source_visible_files") != 0
            or oracle.get("target_changed_sectors") != []
            or oracle.get("target_byte_identical") is not True
            or oracle.get("target_before_sha256") != oracle.get("target_after_sha256")
            or oracle.get("witnesses") != ["d81_persistence_fault", "d81_bam_sanity"]
        ):
            raise G6Error(f"phase-injection oracle drift: {name}")

    boundary_expected = {
        "m65d-residual-window-data-boundary": (
            "data", "T1/S0", "unallocated-data-sector-only",
        ),
        "m65d-residual-window-bam-boundary": (
            "bam", "T40/S1", "filesystem-metadata-may-be-invalid",
        ),
        "m65d-residual-window-directory-boundary": (
            "directory", "T40/S3", "filesystem-metadata-may-be-invalid",
        ),
    }
    for name, (phase, changed_sector, damage) in boundary_expected.items():
        row = by_name.get(name)
        oracle = row.get("residual_window_boundary_oracle") if isinstance(row, dict) else None
        if (
            not isinstance(oracle, dict) or row.get("result") != "12"
            or oracle.get("result") != "known-contract-boundary-characterized"
            or oracle.get("safety_pass") is not False
            or oracle.get("phase") != phase or oracle.get("terminal_status") != 12
            or oracle.get("source_changed_sectors") != []
            or oracle.get("source_byte_identical") is not True
            or oracle.get("foreign_changed_sectors") != [changed_sector]
            or oracle.get("foreign_changed_sector_count") != 1
            or oracle.get("writes_after_detection") != 0
            or not isinstance(oracle.get("foreign_filesystem_valid_after"), bool)
            or oracle.get("damage_class") != damage
            or oracle.get("witnesses")
            != ["full-image-sector-diff", "d81_persistence_fault", "d81_bam_sanity"]
        ):
            raise G6Error(f"residual-window boundary characterization drift: {name}")


def validate_freezer_boundary_confirmation(value: dict[str, Any]) -> None:
    exact(
        value,
        {
            "format", "version", "result", "safety_pass", "freezer_opened",
            "terminal_status", "automatic_retry", "writes_after_detection",
            "observed_foreign_changed_sector_count", "contract_limit_foreign_sector_count",
            "both_media_checked", "explicit_restart_required", "persistent_status",
            "status_state_synchronized",
        },
        "Freezer boundary confirmation",
    )
    if (
        value["format"] != "lisp65-g6-freezer-boundary-confirmation-v1"
        or value["version"] != 1
        or value["result"] != "within-owner-accepted-boundary"
        or value["safety_pass"] is not False
        or value["freezer_opened"] is not True
        or value["terminal_status"] != 12
        or value["persistent_status"] != 12
        or value["status_state_synchronized"] is not True
        or value["automatic_retry"] is not False
        or value["writes_after_detection"] != 0
        or value["observed_foreign_changed_sector_count"] not in {0, 1}
        or value["contract_limit_foreign_sector_count"] != 1
        or value["both_media_checked"] is not True
        or value["explicit_restart_required"] is not True
    ):
        raise G6Error("real-Freezer result exceeded or misstated the accepted boundary")


def validate_two_media_oracle(
    value: dict[str, Any], *, a_before: Path, a_after: Path,
    b_baseline: Path, b_before: Path, b_after: Path, expected_content: Path,
) -> None:
    exact(
        value,
        {
            "format", "version", "result", "expected_file", "expected_content_sha256",
            "safety_pass", "medium_a_before_sha256", "medium_a_after_sha256",
            "medium_a_header_unchanged", "medium_a_visibility", "medium_a_orphan_sector_count",
            "medium_b_baseline_sha256", "medium_b_before_sha256", "medium_b_after_sha256",
            "medium_b_changed_sectors", "medium_b_changed_sector_count",
            "contract_limit_foreign_sector_count", "medium_b_filesystem_valid_after",
            "damage_class", "both_media_checked", "witnesses",
        },
        "two-media oracle",
    )
    try:
        expected = TWO_MEDIA.verify(
            a_before_path=a_before, a_after_path=a_after,
            b_baseline_path=b_baseline, b_before_path=b_before, b_after_path=b_after,
            expected_name=value["expected_file"], expected_content_path=expected_content,
        )
    except (TWO_MEDIA.OracleError, AssertionError, ValueError, OSError) as exc:
        raise G6Error(f"two-media independent rerun rejected the raw images: {exc}") from exc
    if value != expected:
        raise G6Error("two-media report differs from the independent rerun")
    before_b = b_before.read_bytes()
    after_b = b_after.read_bytes()
    sector_size = 256
    sectors_per_track = 40
    if len(before_b) != len(after_b) or len(before_b) % sector_size:
        raise G6Error("two-media oracle input is not an exact sector image")
    changed_indices = [
        index for index in range(len(before_b) // sector_size)
        if before_b[index * sector_size : (index + 1) * sector_size]
        != after_b[index * sector_size : (index + 1) * sector_size]
    ]
    changed_sectors = [
        f"T{index // sectors_per_track + 1}/S{index % sectors_per_track}"
        for index in changed_indices
    ]
    if (
        value["format"] != "lisp65-g6-two-media-boundary-oracle-v1" or value["version"] != 1
        or value["result"] != "within-owner-accepted-boundary"
        or value["safety_pass"] is not False or not isinstance(value["expected_file"], str)
        or not value["expected_file"] or not SHA_RE.fullmatch(value["expected_content_sha256"])
        or value["medium_a_before_sha256"] != sha(a_before)
        or value["medium_a_after_sha256"] != sha(a_after)
        or value["medium_a_header_unchanged"] is not True
        or value["medium_a_visibility"] not in {"unchanged-precommit", "complete-committed"}
        or not isinstance(value["medium_a_orphan_sector_count"], int)
        or value["medium_a_orphan_sector_count"] < 0
        or value["medium_b_baseline_sha256"] != sha(b_baseline)
        or value["medium_b_before_sha256"] != sha(b_before)
        or value["medium_b_after_sha256"] != sha(b_after)
        or value["medium_b_changed_sectors"] != changed_sectors
        or value["medium_b_changed_sector_count"] != len(changed_indices)
        or len(changed_indices) > 1
        or value["contract_limit_foreign_sector_count"] != 1
        or not isinstance(value["medium_b_filesystem_valid_after"], bool)
        or value["damage_class"] not in {
            "none-observed", "data-sector-may-be-overwritten",
            "filesystem-BAM-sector-may-be-invalid",
            "filesystem-directory-sector-may-be-invalid",
        }
        or value["both_media_checked"] is not True
        or value["witnesses"]
        != ["full-image-sector-diff", "d81_persistence_fault", "d81_bam_sanity"]
        or b_baseline.read_bytes() != b_before.read_bytes()
    ):
        raise G6Error("two-media accepted-boundary oracle drift")


def bank5_oracle_value(readback: Path) -> dict[str, Any]:
    value = contract()
    ship_root = ROOT / value["ship"]["path"]
    ship_manifest = run_ship_verifier(ship_root)
    artifacts = package_artifacts(ship_manifest)
    archive = ship_root / f"evidence/{R4_ID}.tar.gz"
    preload = ship_root / "components/bank5.bin"
    if (
        archive.is_symlink() or not archive.is_file()
        or sha(archive) != value["ship"]["r4_archive_sha256"]
        or preload.is_symlink() or not preload.is_file()
        or artifacts["bank5-preload"].get("ship_path") != "components/bank5.bin"
        or sha(preload) != artifacts["bank5-preload"].get("sha256")
    ):
        raise G6Error("sealed R4 archive or Bank-5 preload binding drift")
    try:
        with tarfile.open(archive, "r:gz") as source:
            member = source.getmember(SEALED_STDLIB_MANIFEST)
            if not member.isfile() or member.issym() or member.islnk():
                raise G6Error("sealed Stdlib manifest is not a regular archive member")
            extracted = source.extractfile(member)
            if extracted is None:
                raise G6Error("sealed Stdlib manifest is unreadable")
            manifest_bytes = extracted.read()
    except (tarfile.TarError, KeyError, OSError) as exc:
        raise G6Error(f"cannot read sealed Stdlib manifest: {exc}") from exc
    manifest = load_bytes(manifest_bytes, "sealed Stdlib manifest")
    external = manifest.get("external_image")
    patches = manifest.get("literal_patches")
    before = preload.read_bytes()
    after = readback.read_bytes()
    if (
        not isinstance(external, dict) or not isinstance(patches, list)
        or external.get("format") != "lisp65-bytecode-p0-ext-image-v1"
        or not isinstance(external.get("bytes"), int) or external["bytes"] <= 0
        or sha_bytes(before[:external["bytes"]]) != external.get("sha256")
    ):
        raise G6Error("Bank-5 preload/manifest envelope drift")
    slots: list[int] = []
    seen: set[int] = set()
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict) or set(patch) != {"blob_offset", "node"}:
            raise G6Error(f"sealed literal patch malformed: {index}")
        offset = patch["blob_offset"]
        if (
            not isinstance(offset, int) or offset < 0 or offset + 2 > external["bytes"]
            or offset in seen or not isinstance(patch["node"], int) or patch["node"] < 0
        ):
            raise G6Error(f"sealed literal patch range/identity drift: {index}")
        slots.append(offset)
        seen.add(offset)
    measured = validate_bank5_post_commit(before, after, stdlib_bytes=external["bytes"], slots=slots)
    return {
        "format": "lisp65-r6-g6-bank5-post-commit-oracle-v1", "version": 1,
        "status": "passed", "r4_archive_sha256": sha(archive),
        "manifest_member": SEALED_STDLIB_MANIFEST,
        "manifest_sha256": sha_bytes(manifest_bytes),
        "preload_sha256": sha_bytes(before), "readback_sha256": sha_bytes(after),
        "preload_bytes": len(before), "stdlib_bytes": external["bytes"],
        "literal_patch_slots": len(slots), **measured, "result": "passed",
    }


def write_bank5_oracle(*, readback: Path, output: Path) -> dict[str, Any]:
    result = bank5_oracle_value(readback)
    data = canonical(result)
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file() or output.read_bytes() != data:
            raise G6Error(f"refusing to overwrite differing Bank-5 oracle: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    print(
        f"r6-g6: BANK5 ORACLE PASS patches={result['literal_patch_slots']} "
        f"changed={result['changed_patch_slots']} outside=0 overlay=exact"
    )
    return result


def verify_case_semantics(
    row: dict[str, Any], by_id: dict[str, Path], observations: dict[str, str], identity: dict[str, Any]
) -> None:
    core = by_id["core-registers"].read_bytes()
    expected_core_version = f"git-{int.from_bytes(core, 'little'):08x}" if len(core) == 4 else ""
    if (
        identity.get("machine_serial") != contract()["execution"]["expected_machine_serial"]
        or identity.get("core_id") != "mega65"
        or identity.get("core_version") != expected_core_version
    ):
        raise G6Error("G6 machine/core binding differs from physical core registers")

    procedure = row["procedure"]
    if procedure == "cold-power-autoboot":
        if observations.get("physical_action") != "power-cycle" or observations.get("host_actions_before_prompt") != "none":
            raise G6Error("cold boot lacks host-free physical power-cycle assertion")
        screen = by_id["screen"].read_text(errors="replace").lower()
        if "lisp65>" not in screen or "ready." in screen:
            raise G6Error("cold-boot screen is not an unambiguous Lisp65 REPL")
        value = contract()
        ship_root = ROOT / value["ship"]["path"]
        artifacts = package_artifacts(run_ship_verifier(ship_root))
        expected_oracle = bank5_oracle_value(by_id["bank5-readback"])
        if load(by_id["bank5-oracle"], "Bank-5 post-commit oracle") != expected_oracle:
            raise G6Error("Bank-5 post-commit oracle does not bind the readback")
        if sha(by_id["attic-readback"]) != artifacts["attic-catalog"]["sha256"]:
            raise G6Error("cold-boot Attic readback differs from R5 product bytes")
        if sha(by_id["shelf-readback"]) != artifacts["attic-library-shelf"]["sha256"]:
            raise G6Error("cold-boot library-shelf readback differs from R5 product bytes")
        if "hyppo status:" not in by_id["hyppo-status"].read_text(errors="replace").lower():
            raise G6Error("cold-boot HYPPO status evidence is malformed")
        if "03636093" not in by_id["device-discovery"].read_text(errors="replace").lower():
            raise G6Error("cold-boot device discovery does not bind the MEGA65 JTAG ID")
    elif procedure == "warm-reset-fastpath":
        if observations.get("physical_action") != "reset":
            raise G6Error("warm reset lacks physical reset assertion")
        artifacts = package_artifacts(
            run_ship_verifier(ROOT / contract()["ship"]["path"]),
        )
        if (
            by_id["pre-reset-bank5"].read_bytes() != by_id["post-reset-bank5"].read_bytes()
            or by_id["pre-reset-attic"].read_bytes() != by_id["post-reset-attic"].read_bytes()
            or by_id["pre-reset-shelf"].read_bytes() != by_id["post-reset-shelf"].read_bytes()
            or sha(by_id["post-reset-attic"]) != artifacts["attic-catalog"]["sha256"]
            or sha(by_id["post-reset-shelf"]) != artifacts["attic-library-shelf"]["sha256"]
            or "SHELF RESET PASS" not in by_id["shelf-load-transcript"].read_text(errors="replace")
            or "lisp65>" not in by_id["screen"].read_text(errors="replace").lower()
        ):
            raise G6Error("warm-reset region, disk-restart REPL or shelf-load oracle failed")
    elif procedure == "physical-write-protect":
        if by_id["pre-write-disk"].read_bytes() != by_id["post-write-disk"].read_bytes():
            raise G6Error("physical-write-protect full-medium bytes changed")
        if "pass" not in by_id["full-media-oracle"].read_text(errors="replace").lower():
            raise G6Error("physical-write-protect oracle is not PASS")
    elif procedure == "phase-injection-plus-freezer-boundary":
        identities = []
        for evidence_id in ("user-media-a-identity", "user-media-b-identity"):
            identities.append(
                validate_user_media_identity(load(by_id[evidence_id], evidence_id), evidence_id)
            )
        if identities[0] == identities[1]:
            raise G6Error("mid-write media swap did not change exact name-plus-ID identity")
        validate_phase_injection_report(load(by_id["phase-injection-report"], "phase-injection report"))
        freezer = load(by_id["freezer-boundary-transcript"], "Freezer boundary confirmation")
        validate_freezer_boundary_confirmation(freezer)
        two_media = load(by_id["two-media-oracle"], "two-media oracle")
        validate_two_media_oracle(
            two_media,
            a_before=by_id["manual-pre-media-a"], a_after=by_id["manual-post-media-a"],
            b_baseline=by_id["clean-media-b-baseline"], b_before=by_id["manual-pre-media-b"],
            b_after=by_id["manual-post-media-b"],
            expected_content=by_id["manual-expected-content"],
        )
        if (
            freezer["observed_foreign_changed_sector_count"]
            != two_media["medium_b_changed_sector_count"]
        ):
            raise G6Error("Freezer transcript and two-media sector delta disagree")
        identity_a = load(by_id["user-media-a-identity"], "user-media-a-identity")
        identity_b = load(by_id["user-media-b-identity"], "user-media-b-identity")
        if (
            identity_a["medium_sha256"] != sha(by_id["manual-pre-media-a"])
            or identity_b["medium_sha256"] != sha(by_id["manual-pre-media-b"])
        ):
            raise G6Error("two-media identity receipts do not bind the pre-run images")
    elif procedure == "work-persistence":
        validate_bufsel_context(
            by_id["bufsel-precondition"].read_bytes(),
            by_id["bufsel-postcondition"].read_bytes(),
        )
        if "pass" not in by_id["disk-oracle"].read_text(errors="replace").lower():
            raise G6Error("work persistence disk oracle is not PASS")
        if "COMPILE STRING COW PASS" not in by_id["compile-string-transcript"].read_text(errors="replace"):
            raise G6Error("work persistence lacks the compile-string COW acceptance marker")
    else:
        transcripts = b"\n".join(path.read_bytes() for key, path in by_id.items() if "transcript" in key)
        if b"PASS" not in transcripts and b"pass" not in transcripts:
            raise G6Error("composition transcript set contains no PASS oracle")


def open_case(*, case_id: str, cycle_id: str, core_id: str, core_version: str, output: Path) -> dict[str, Any]:
    preflight = verify_preflight(TRACKED_PREFLIGHT, require_ship=True)
    row = find_case(case_id)
    cycle_id, core_id, core_version = token(cycle_id, "cycle id"), token(core_id, "core id"), token(core_version, "core version")
    environment = verify_environment(contract())
    sheet = {
        "format": SHEET_FORMAT, "version": 2, "status": "open-not-evidence",
        "case_id": case_id, "procedure": row["procedure"], "cycle_id": cycle_id,
        "machine_serial": environment["machine"]["serial"], "core_id": core_id, "core_version": core_version,
        "product_artifact_set_sha256": PRODUCT_SET,
        "hardware_profile_sha256": sha(HARDWARE_PROFILE),
        "ship_manifest_sha256": preflight["ship"]["manifest_sha256"],
        "preflight_sha256": sha(TRACKED_PREFLIGHT),
        "required_evidence": row["required_evidence"],
        "operator_rule": "perform-exact-procedure-then-close-with-all-raw-evidence",
        "claims": {"case": "not-run", "G6": "not-run", "release": "not-release-capable"},
    }
    data = canonical(sheet)
    if output.exists() or output.is_symlink():
        raise G6Error(f"case sheet output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"r6-g6: CASE OPEN id={case_id} cycle={cycle_id} status=not-run")
    return sheet


def parse_bindings(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise G6Error(f"{label} binding needs key=value: {raw}")
        key, value = raw.split("=", 1)
        token(key, f"{label} key")
        if not value or key in result:
            raise G6Error(f"invalid/duplicate {label} binding: {key}")
        result[key] = value
    return result


def close_case(*, sheet_path: Path, evidence_args: list[str], observation_args: list[str], output: Path) -> dict[str, Any]:
    sheet = load(sheet_path, "G6 execution sheet")
    exact(
        sheet,
        {
            "format", "version", "status", "case_id", "procedure", "cycle_id", "machine_serial",
            "core_id", "core_version", "product_artifact_set_sha256", "hardware_profile_sha256", "ship_manifest_sha256",
            "preflight_sha256", "required_evidence", "operator_rule", "claims",
        },
        "G6 execution sheet",
    )
    if sheet["format"] != SHEET_FORMAT or sheet["status"] != "open-not-evidence" or sheet["claims"]["case"] != "not-run":
        raise G6Error("G6 execution sheet is not open")
    row = find_case(sheet["case_id"])
    configured = contract()
    if (
        sheet["procedure"] != row["procedure"]
        or sheet["machine_serial"] != configured["execution"]["expected_machine_serial"]
        or sheet["product_artifact_set_sha256"] != PRODUCT_SET
        or sheet["hardware_profile_sha256"] != sha(HARDWARE_PROFILE)
        or sheet["ship_manifest_sha256"] != configured["ship"]["manifest_sha256"]
        or sheet["preflight_sha256"] != sha(TRACKED_PREFLIGHT)
        or sheet["required_evidence"] != row["required_evidence"]
    ):
        raise G6Error("G6 execution sheet binding drift")
    evidence_values = parse_bindings(evidence_args, "evidence")
    observations = parse_bindings(observation_args, "observation")
    if set(evidence_values) != set(row["required_evidence"]):
        raise G6Error(f"G6 evidence set drift: expected={sorted(row['required_evidence'])} actual={sorted(evidence_values)}")
    if observations.get("result") != "pass":
        raise G6Error("G6 operator result must be explicit result=pass")
    evidence: list[dict[str, Any]] = []
    for key in row["required_evidence"]:
        path = Path(evidence_values[key])
        path = path if path.is_absolute() else ROOT / path
        if path.is_symlink() or not path.is_file():
            raise G6Error(f"G6 evidence file missing: {key}")
        evidence.append({"id": key, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    by_id = {item["id"]: ROOT / item["path"] for item in evidence}
    procedure = row["procedure"]
    verify_case_semantics(row, by_id, observations, sheet)
    raw_set = sha_bytes(canonical([{"id": item["id"], "sha256": item["sha256"]} for item in evidence]))
    receipt = {
        "format": CASE_FORMAT, "version": 2, "status": "passed",
        "case_id": sheet["case_id"], "procedure": procedure,
        "cycle_id": sheet["cycle_id"], "machine_serial": sheet["machine_serial"],
        "core_id": sheet["core_id"], "core_version": sheet["core_version"],
        "rom_sha256": "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0",
        "product_artifact_set_sha256": PRODUCT_SET,
        "hardware_profile_sha256": sheet["hardware_profile_sha256"],
        "product_d81_sha256": contract()["ship"]["product_d81_sha256"],
        "work_d81_sha256": contract()["ship"]["work_d81_sha256"],
        "ship_manifest_sha256": sheet["ship_manifest_sha256"],
        "preflight_sha256": sheet["preflight_sha256"],
        "sheet": {"path": sheet_path.relative_to(ROOT).as_posix(), "sha256": sha(sheet_path)},
        "evidence": evidence, "raw_evidence_set_sha256": raw_set,
        "observations": dict(sorted(observations.items())),
        "claims": {"case": "passed", "G6": "partial-until-5-of-5-applicable", "release": "not-release-capable"},
        "result": "passed",
    }
    data = canonical(receipt)
    if output.exists() or output.is_symlink():
        raise G6Error(f"G6 case receipt output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    verify_case_receipt(output)
    print(f"r6-g6: CASE PASS id={sheet['case_id']} cycle={sheet['cycle_id']} release=no")
    return receipt


def verify_case_receipt(path: Path, *, expected_preflight_sha256: str | None = None) -> dict[str, Any]:
    value = load(path, "G6 case receipt")
    exact(
        value,
        {
            "format", "version", "status", "case_id", "procedure", "cycle_id", "machine_serial",
            "core_id", "core_version", "rom_sha256", "product_artifact_set_sha256",
            "hardware_profile_sha256",
            "product_d81_sha256", "work_d81_sha256", "ship_manifest_sha256", "preflight_sha256",
            "sheet", "evidence", "raw_evidence_set_sha256", "observations", "claims", "result",
        },
        "G6 case receipt",
    )
    row = find_case(value["case_id"])
    configured = contract()
    expected_preflight_sha256 = expected_preflight_sha256 or sha(TRACKED_PREFLIGHT)
    if (
        value["format"] != CASE_FORMAT or value["version"] != 2 or value["status"] != "passed"
        or value["procedure"] != row["procedure"] or value["result"] != "passed"
        or value["product_artifact_set_sha256"] != PRODUCT_SET
        or value["hardware_profile_sha256"] != sha(HARDWARE_PROFILE)
        or value["product_d81_sha256"] != configured["ship"]["product_d81_sha256"]
        or value["work_d81_sha256"] != configured["ship"]["work_d81_sha256"]
        or value["ship_manifest_sha256"] != configured["ship"]["manifest_sha256"]
        or value["preflight_sha256"] != expected_preflight_sha256
        or value["rom_sha256"] != "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0"
        or value["claims"] != {"case": "passed", "G6": "partial-until-5-of-5-applicable", "release": "not-release-capable"}
        or not SHA_RE.fullmatch(value["raw_evidence_set_sha256"])
        or not isinstance(value["observations"], dict) or value["observations"].get("result") != "pass"
    ):
        raise G6Error("G6 case receipt semantic drift")
    sheet_row = exact(value["sheet"], {"path", "sha256"}, "G6 case receipt sheet binding")
    sheet_path = ROOT / relative(sheet_row["path"], "G6 execution sheet path")
    if (
        sheet_path.is_symlink() or not sheet_path.is_file() or sha(sheet_path) != sheet_row["sha256"]
    ):
        raise G6Error("G6 execution sheet byte drift")
    sheet = load(sheet_path, "G6 execution sheet")
    for key in (
        "case_id", "procedure", "cycle_id", "machine_serial", "core_id", "core_version",
        "product_artifact_set_sha256", "hardware_profile_sha256", "ship_manifest_sha256", "preflight_sha256",
    ):
        if sheet.get(key) != value[key]:
            raise G6Error(f"G6 execution sheet/receipt drift: {key}")
    evidence = value["evidence"]
    if (
        not isinstance(evidence, list) or len(evidence) != len(row["required_evidence"])
        or {item.get("id") for item in evidence if isinstance(item, dict)} != set(row["required_evidence"])
    ):
        raise G6Error("G6 case receipt evidence set drift")
    for item in evidence:
        exact(item, {"id", "path", "bytes", "sha256"}, "G6 case evidence binding")
        path_value = ROOT / relative(item.get("path"), "case evidence path")
        if (
            path_value.is_symlink() or not path_value.is_file() or path_value.stat().st_size != item.get("bytes")
            or sha(path_value) != item.get("sha256") or not SHA_RE.fullmatch(item.get("sha256", ""))
        ):
            raise G6Error(f"G6 case receipt evidence byte drift: {item.get('id')}")
    recomputed = sha_bytes(canonical([{"id": item["id"], "sha256": item["sha256"]} for item in evidence]))
    if recomputed != value["raw_evidence_set_sha256"]:
        raise G6Error("G6 raw evidence set SHA drift")
    by_id = {item["id"]: ROOT / item["path"] for item in evidence}
    verify_case_semantics(row, by_id, value["observations"], value)
    print(f"r6-g6: CASE CHECK PASS id={value['case_id']} cycle={value['cycle_id']}")
    return value


def verify_historical_preflight(path: Path, case: dict[str, Any]) -> dict[str, Any]:
    value = load(path, "historical G6 static preflight")
    if (
        value.get("format") != PREFLIGHT_FORMAT
        or value.get("id") != "r6-g6-static-preflight"
        or value.get("status") != "passed-hardware-not-run"
        or value.get("result") != "passed"
        or value.get("ship", {}).get("product_artifact_set_sha256") != PRODUCT_SET
        or value.get("ship", {}).get("manifest_sha256") != contract()["ship"]["manifest_sha256"]
        or value.get("hardware_profile", {}).get("sha256") != sha(HARDWARE_PROFILE)
    ):
        raise G6Error("historical G6 preflight is not identity-compatible")
    rows = value.get("cases")
    row = next((item for item in rows if item.get("id") == case["case_id"]), None) if isinstance(rows, list) else None
    current = find_case(case["case_id"])
    if (
        not isinstance(row, dict)
        or row.get("procedure") != current["procedure"]
        or row.get("required_roles") != current["required_roles"]
        or row.get("required_evidence") != current["required_evidence"]
        or row.get("status") != "ready-not-run"
    ):
        raise G6Error("historical G6 preflight case closure is not compatible")
    return value


def case_rebind_value(*, historical_receipt: Path, historical_preflight: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    current_preflight = verify_preflight(TRACKED_PREFLIGHT, require_ship=True)
    historical_preflight_sha = sha(historical_preflight)
    if historical_preflight_sha == sha(TRACKED_PREFLIGHT):
        raise G6Error("case rebind requires a superseded historical preflight")
    case = verify_case_receipt(
        historical_receipt, expected_preflight_sha256=historical_preflight_sha,
    )
    verify_historical_preflight(historical_preflight, case)
    value = {
        "format": CASE_REBIND_FORMAT,
        "version": 1,
        "status": "passed-offline-rebound-no-hardware-rerun",
        "case_id": case["case_id"],
        "cycle_id": case["cycle_id"],
        "product_artifact_set_sha256": PRODUCT_SET,
        "ship_manifest_sha256": current_preflight["ship"]["manifest_sha256"],
        "current_preflight_sha256": sha(TRACKED_PREFLIGHT),
        "current_contract_sha256": sha(CONTRACT),
        "historical_preflight": {
            "path": historical_preflight.relative_to(ROOT).as_posix(),
            "sha256": historical_preflight_sha,
        },
        "historical_case_receipt": {
            "path": historical_receipt.relative_to(ROOT).as_posix(),
            "sha256": sha(historical_receipt),
            "raw_evidence_set_sha256": case["raw_evidence_set_sha256"],
        },
        "reverification": {
            "product_identity": "unchanged",
            "procedure_semantics": "passed-against-current-contract",
            "raw_evidence": "byte-identical-and-offline-reverified",
            "hardware_case_reexecuted": False,
        },
        "claims": {
            "case": "passed-product-sha-bound-reused",
            "G6": "partial-until-5-of-5-applicable",
            "release": "not-release-capable",
        },
        "result": "passed",
    }
    return value, case


def write_case_rebind(*, historical_receipt: Path, historical_preflight: Path, output: Path) -> dict[str, Any]:
    value, _ = case_rebind_value(
        historical_receipt=historical_receipt, historical_preflight=historical_preflight,
    )
    if output.exists() or output.is_symlink():
        raise G6Error(f"G6 case rebind output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(value))
    verify_case_rebind(output)
    print(f"r6-g6: CASE REBIND PASS id={value['case_id']} cycle={value['cycle_id']} hardware-rerun=0")
    return value


def verify_case_rebind(path: Path) -> dict[str, Any]:
    value = load(path, "G6 case rebind receipt")
    historical_preflight = ROOT / relative(
        value.get("historical_preflight", {}).get("path"), "historical G6 preflight path",
    )
    historical_receipt = ROOT / relative(
        value.get("historical_case_receipt", {}).get("path"), "historical G6 case receipt path",
    )
    expected, case = case_rebind_value(
        historical_receipt=historical_receipt, historical_preflight=historical_preflight,
    )
    if value != expected:
        raise G6Error("G6 case rebind receipt semantic or byte-binding drift")
    print(f"r6-g6: CASE REBIND CHECK PASS id={value['case_id']} cycle={value['cycle_id']}")
    return case


def verify_case_binding(path: Path) -> dict[str, Any]:
    value = load(path, "G6 case binding")
    if value.get("format") == CASE_FORMAT:
        return verify_case_receipt(path)
    if value.get("format") == CASE_REBIND_FORMAT:
        return verify_case_rebind(path)
    raise G6Error(f"unsupported G6 case binding format: {value.get('format')}")


def aggregate_value(receipt_paths: list[Path]) -> dict[str, Any]:
    expected = {
        row["id"] for row in contract()["cases"]
        if row["fidelity"] == "hardware-only" and row["target"] == "operator-assisted-hardware"
    }
    receipts = [verify_case_binding(path) for path in receipt_paths]
    if len(receipts) != 5 or {row["case_id"] for row in receipts} != expected:
        raise G6Error("G6 aggregation requires each exact applicable hardware case once")
    profile_receipt = verify_profile_receipt(
        PROFILE_RECEIPT, ship_root=ROOT / contract()["ship"]["path"],
    )
    machine = {(row["machine_serial"], row["core_id"], row["core_version"], row["rom_sha256"]) for row in receipts}
    if len(machine) != 1:
        raise G6Error("G6 receipts do not share one machine/core/ROM binding")
    reset_cycles = [row["cycle_id"] for row in receipts if row["case_id"] in {"power-cycle-autoboot-restage-repl", "warm-reset-valid-catalog-fastpath"}]
    if len(set(reset_cycles)) != 2:
        raise G6Error("G6 power/reset cases require distinct cycle IDs")
    return {
        "format": TOP_FORMAT, "version": 2, "status": "passed-not-release-promoted",
        "product_artifact_set_sha256": PRODUCT_SET,
        "hardware_profile_sha256": sha(HARDWARE_PROFILE),
        "ship_manifest_sha256": contract()["ship"]["manifest_sha256"],
        "preflight_sha256": sha(TRACKED_PREFLIGHT),
        "machine": {"serial": receipts[0]["machine_serial"], "core_id": receipts[0]["core_id"], "core_version": receipts[0]["core_version"], "rom_sha256": receipts[0]["rom_sha256"]},
        "cases": [
            {"id": row["case_id"], "cycle_id": row["cycle_id"], "receipt": path.relative_to(ROOT).as_posix(), "receipt_sha256": sha(path)}
            for row, path in sorted(zip(receipts, receipt_paths, strict=True), key=lambda pair: pair[0]["case_id"])
        ],
        "profile_not_applicable": {
            "case_id": profile_receipt["case_id"],
            "receipt": PROFILE_RECEIPT.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(PROFILE_RECEIPT),
            "bound_manifest_sha256": profile_receipt["ship"]["manifest_sha256"],
        },
        "counts": {"G3_sealed": 9, "G6_applicable_passed": 5, "G6_profile_not_applicable": 1, "total": 15},
        "claims": {
            "G3": "passed-emulator-prefilter-only",
            "G5": "passed-for-product-artifact-set",
            "G6": hardware_profile()["G6"]["claim"],
            "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
            "release": "not-promoted-until-R7",
        },
        "result": "passed",
    }


def aggregate(receipt_paths: list[Path], output: Path) -> dict[str, Any]:
    top = aggregate_value(receipt_paths)
    if output.exists() or output.is_symlink():
        raise G6Error(f"G6 top receipt output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(top))
    print(f"r6-g6: AGGREGATE PASS G6=5/5-applicable WP=n/a product={PRODUCT_SET} release=awaits-R7")
    return top


def verify_aggregate_receipt(path: Path) -> dict[str, Any]:
    value = load(path, "G6 aggregate receipt")
    rows = value.get("cases")
    if not isinstance(rows, list) or len(rows) != 5:
        raise G6Error("G6 aggregate receipt case inventory drift")
    receipt_paths: list[Path] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"id", "cycle_id", "receipt", "receipt_sha256"}, f"G6 aggregate case[{index}]")
        receipt_path = ROOT / relative(row["receipt"], f"G6 aggregate case[{index}].receipt")
        if (
            receipt_path.is_symlink() or not receipt_path.is_file()
            or sha(receipt_path) != row["receipt_sha256"]
        ):
            raise G6Error(f"G6 aggregate case receipt byte drift: {row['id']}")
        receipt_paths.append(receipt_path)
    expected = aggregate_value(receipt_paths)
    if value != expected:
        raise G6Error("G6 aggregate receipt semantic or binding drift")
    print(
        f"r6-g6: AGGREGATE CHECK PASS G6=5/5-applicable WP=n/a "
        f"product={PRODUCT_SET} release=awaits-R7"
    )
    return value


def selftest() -> None:
    global CONTRACT
    value = contract()
    r7_prerequisites()
    original = deepcopy(value)
    mutations = [
        lambda x: x.update(status="release-capable"),
        lambda x: x["ship"].update(product_artifact_set_sha256="0" * 64),
        lambda x: x["cases"].pop(),
        lambda x: next(
            row for row in x["cases"] if row["id"] == "artifact-preflight-exact-set"
        ).update(fidelity="hardware-only"),
        lambda x: next(
            row for row in x["cases"] if row["id"] == "disk-swap-resident-composition"
        ).update(target="sealed-r4-g3"),
        lambda x: next(
            row for row in x["cases"] if row["id"] == "product-medium-physical-write-protect"
        ).update(target="operator-assisted-hardware", procedure="physical-write-protect"),
        lambda x: next(
            row for row in x["cases"] if row["id"] == "mid-write-media-swap-abort"
        )["manual_trigger"].update(
            entrypoint="%m65d-run-authorized",
            form='(%m65d-run-authorized "g6swap" g6src nil)',
        ),
        lambda x: x["claims_before_execution"].update(G6="passed"),
    ]
    with tempfile.TemporaryDirectory(prefix="r6-g6-selftest-") as raw:
        path = Path(raw) / "contract.json"
        live = CONTRACT
        try:
            for mutate in mutations:
                candidate = deepcopy(original)
                mutate(candidate)
                path.write_bytes(canonical(candidate))
                CONTRACT = path
                try:
                    contract()
                except G6Error:
                    continue
                raise G6Error("G6 contract mutation survived selftest")
        finally:
            CONTRACT = live
    before = bytes(range(8))
    after = bytearray(before)
    after[1:3] = b"\x80\x81"
    measured = validate_bank5_post_commit(before, bytes(after), stdlib_bytes=6, slots=[1, 3])
    if measured != {
        "changed_patch_slots": 1, "changed_bytes": 2,
        "changed_bytes_outside_patch_slots": 0, "overlay_tail_byte_identical": True,
    }:
        raise G6Error("Bank-5 post-commit positive selftest drift")
    bank5_mutations = []
    for index in (0, 6):
        candidate = bytearray(before)
        candidate[index] ^= 0xff
        bank5_mutations.append(bytes(candidate))
    bank5_mutations.append(before)
    for candidate in bank5_mutations:
        try:
            validate_bank5_post_commit(before, candidate, stdlib_bytes=6, slots=[1, 3])
        except G6Error:
            continue
        raise G6Error("Bank-5 forbidden mutation survived selftest")
    validate_bufsel_context(b"\x80", b"\x00")
    bufsel_mutations = ((b"\x00", b"\x00"), (b"\x80", b"\x80"), (b"\x80\x00", b"\x00"))
    for precondition, postcondition in bufsel_mutations:
        try:
            validate_bufsel_context(precondition, postcondition)
        except G6Error:
            continue
        raise G6Error("forbidden BUFSEL evidence survived selftest")
    media_identity = {
        "format": "lisp65-g6-user-media-identity-v1", "version": 1,
        "disk_name": "ALEXDATA", "disk_id": "A1", "valid_1581": True,
        "product_boot_signature": False, "medium_sha256": "1" * 64,
    }
    if validate_user_media_identity(media_identity, "user-media") != ("ALEXDATA", "A1"):
        raise G6Error("user-media identity positive selftest drift")
    media_mutations = []
    for key, value in (("disk_name", ""), ("valid_1581", False), ("product_boot_signature", True)):
        candidate = deepcopy(media_identity)
        candidate[key] = value
        media_mutations.append(candidate)
    for candidate in media_mutations:
        try:
            validate_user_media_identity(candidate, "user-media")
        except G6Error:
            continue
        raise G6Error("forbidden user-media identity survived selftest")
    phase_report = {
        "format": "lisp65-bytecode-p0-observations-v1",
        "suites": [{"observations": [
            {
                "name": name, "result": "(12 t)",
                "two_media_phase_oracle": {
                    "result": "pass", "phase": phase, "terminal_status": 12,
                    "injected_write_operation": operation,
                    "source_changed_sectors": changed, "source_visible_files": 0,
                    "target_changed_sectors": [], "target_byte_identical": True,
                    "target_before_sha256": "1" * 64, "target_after_sha256": "1" * 64,
                    "witnesses": ["d81_persistence_fault", "d81_bam_sanity"],
                },
            }
            for name, phase, operation, changed in (
                ("m65d-media-change-before-data-write-terminal", "before-data-write", 1, []),
                ("m65d-media-change-before-bam-write-terminal", "before-bam-write", 2, ["T1/S0"]),
                ("m65d-media-change-before-directory-write-terminal", "before-directory-write", 3, ["T1/S0", "T40/S1"]),
            )
        ] + [
            {
                "name": name, "result": "12",
                "residual_window_boundary_oracle": {
                    "result": "known-contract-boundary-characterized",
                    "safety_pass": False, "phase": phase, "terminal_status": 12,
                    "source_changed_sectors": [], "source_byte_identical": True,
                    "foreign_changed_sectors": [changed],
                    "foreign_changed_sector_count": 1, "writes_after_detection": 0,
                    "foreign_filesystem_valid_after": valid, "damage_class": damage,
                    "witnesses": [
                        "full-image-sector-diff", "d81_persistence_fault", "d81_bam_sanity",
                    ],
                },
            }
            for name, phase, changed, valid, damage in (
                ("m65d-residual-window-data-boundary", "data", "T1/S0", True, "unallocated-data-sector-only"),
                ("m65d-residual-window-bam-boundary", "bam", "T40/S1", False, "filesystem-metadata-may-be-invalid"),
                ("m65d-residual-window-directory-boundary", "directory", "T40/S3", False, "filesystem-metadata-may-be-invalid"),
            )
        ] + [
            {
                "name": name, "result": str(classified_status),
                "planning_read_guard_oracle": {
                    "result": "pass", "read_failure_status": 6,
                    "mount_token_changed": token_changed,
                    "classified_status": classified_status,
                    "persistent_status": classified_status,
                    "status_state_synchronized": True,
                    "partial_write_latched": False,
                    "disk_write_count": 0,
                },
            }
            for name, token_changed, classified_status in (
                ("m65d-media-change-during-planning-read-terminal", True, 12),
                ("m65d-planning-read-failure-with-stable-token-stays-invalid", False, 6),
            )
        ]}],
    }
    validate_phase_injection_report(phase_report)
    broken_phase = deepcopy(phase_report)
    broken_phase["suites"][0]["observations"][2]["two_media_phase_oracle"]["target_byte_identical"] = False
    try:
        validate_phase_injection_report(broken_phase)
    except G6Error:
        pass
    else:
        raise G6Error("mutated phase-injection report survived selftest")
    freezer_boundary = {
        "format": "lisp65-g6-freezer-boundary-confirmation-v1", "version": 1,
        "result": "within-owner-accepted-boundary", "safety_pass": False,
        "freezer_opened": True, "terminal_status": 12, "automatic_retry": False,
        "persistent_status": 12, "status_state_synchronized": True,
        "writes_after_detection": 0, "observed_foreign_changed_sector_count": 1,
        "contract_limit_foreign_sector_count": 1, "both_media_checked": True,
        "explicit_restart_required": True,
    }
    validate_freezer_boundary_confirmation(freezer_boundary)
    broken_boundary = deepcopy(freezer_boundary)
    broken_boundary["status_state_synchronized"] = False
    try:
        validate_freezer_boundary_confirmation(broken_boundary)
    except G6Error:
        pass
    else:
        raise G6Error("Freezer boundary overrun survived selftest")
    print(
        f"r6-g6: SELFTEST PASS mutations={len(mutations) + len(bank5_mutations) + len(bufsel_mutations) + len(media_mutations) + 2} "
        "cases=15 hardware-applicable=5 profile-n/a=1 bank5-oracle=deny-capable bufsel-oracle=deny-capable "
        "media-identity=deny-capable phase-injection=deny-capable freezer-boundary=deny-capable"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    profile_receipt = sub.add_parser("profile-receipt")
    profile_receipt.add_argument("--ship", type=Path, default=Path("build/r6/ship"))
    profile_receipt.add_argument("--out", type=Path, default=PROFILE_RECEIPT)
    profile_receipt.add_argument("--replace", action="store_true")
    profile_check = sub.add_parser("profile-receipt-check")
    profile_check.add_argument("--ship", type=Path, default=Path("build/r6/ship"))
    profile_check.add_argument("receipt", nargs="?", type=Path, default=PROFILE_RECEIPT)
    pre = sub.add_parser("preflight")
    pre.add_argument("--source-commit", required=True)
    pre.add_argument("--ship", type=Path, default=Path("build/r6/ship"))
    pre.add_argument("--out", type=Path, required=True)
    pre.add_argument("--replace-not-run", action="store_true")
    check = sub.add_parser("preflight-check")
    check.add_argument("receipt", nargs="?", type=Path, default=TRACKED_PREFLIGHT)
    check.add_argument("--without-ship", action="store_true")
    opened = sub.add_parser("case-open")
    opened.add_argument("--case", required=True)
    opened.add_argument("--cycle-id", required=True)
    opened.add_argument("--core-id", required=True)
    opened.add_argument("--core-version", required=True)
    opened.add_argument("--out", type=Path, required=True)
    close = sub.add_parser("case-close")
    close.add_argument("--sheet", type=Path, required=True)
    close.add_argument("--evidence", action="append", default=[])
    close.add_argument("--observation", action="append", default=[])
    close.add_argument("--out", type=Path, required=True)
    case_check = sub.add_parser("case-receipt-check")
    case_check.add_argument("receipt", type=Path)
    rebind = sub.add_parser("case-rebind")
    rebind.add_argument("--historical-receipt", type=Path, required=True)
    rebind.add_argument("--historical-preflight", type=Path, required=True)
    rebind.add_argument("--out", type=Path, required=True)
    rebind_check = sub.add_parser("case-rebind-check")
    rebind_check.add_argument("receipt", type=Path)
    oracle = sub.add_parser("bank5-oracle")
    oracle.add_argument("--readback", type=Path, required=True)
    oracle.add_argument("--out", type=Path, required=True)
    top = sub.add_parser("aggregate")
    top.add_argument("--receipt", action="append", type=Path, required=True)
    top.add_argument("--out", type=Path, required=True)
    aggregate_check = sub.add_parser("aggregate-check")
    aggregate_check.add_argument("receipt", type=Path)
    return result


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "profile-receipt":
            write_profile_receipt(
                ship_root=rooted(args.ship), output=rooted(args.out), replace=args.replace,
            )
        elif args.command == "profile-receipt-check":
            verify_profile_receipt(rooted(args.receipt), ship_root=rooted(args.ship))
        elif args.command == "preflight":
            preflight(
                source_commit=args.source_commit, ship_root=rooted(args.ship), output=rooted(args.out),
                replace_not_run=args.replace_not_run,
            )
        elif args.command == "preflight-check":
            verify_preflight(rooted(args.receipt), require_ship=not args.without_ship)
        elif args.command == "case-open":
            open_case(case_id=args.case, cycle_id=args.cycle_id, core_id=args.core_id, core_version=args.core_version, output=rooted(args.out))
        elif args.command == "case-close":
            close_case(sheet_path=rooted(args.sheet), evidence_args=args.evidence, observation_args=args.observation, output=rooted(args.out))
        elif args.command == "case-receipt-check":
            verify_case_receipt(rooted(args.receipt))
        elif args.command == "case-rebind":
            write_case_rebind(
                historical_receipt=rooted(args.historical_receipt),
                historical_preflight=rooted(args.historical_preflight),
                output=rooted(args.out),
            )
        elif args.command == "case-rebind-check":
            verify_case_rebind(rooted(args.receipt))
        elif args.command == "bank5-oracle":
            write_bank5_oracle(readback=rooted(args.readback), output=rooted(args.out))
        elif args.command == "aggregate":
            aggregate([rooted(path) for path in args.receipt], rooted(args.out))
        else:
            verify_aggregate_receipt(rooted(args.receipt))
        return 0
    except (G6Error, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"r6-g6: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
