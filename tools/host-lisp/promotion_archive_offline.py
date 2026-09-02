#!/usr/bin/env python3
"""Self-contained verifier embedded in every sealed promotion archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "payload"
PRODUCT_ARTIFACT_COUNT = 14
C2_LITE_PRODUCT_ARTIFACT_COUNT = 19
FORMAT_V2 = "lisp65-promotion-archive-v2"
FORMAT_V3 = "lisp65-promotion-archive-v3"
C2_LITE_REPRO_FORMATS = {
    "lisp65-c2-lite-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.2.1-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.2.2-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.2.3-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.2.4-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.2.5-media-product-reproducibility-v1",
    "lisp65-c2-lite-v1.3.0-media-product-reproducibility-v1",
}


class VerifyError(RuntimeError):
    pass


def load(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must be an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_path(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise VerifyError(f"invalid payload path: {value!r}")
    return PAYLOAD / value


def external_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise VerifyError(f"invalid external binding path: {value!r}")
    path = PurePosixPath(value)
    if not path.is_absolute() and (path.as_posix() != value or ".." in path.parts):
        raise VerifyError(f"invalid external binding path: {value!r}")
    return value


def verify_inventory(manifest: dict) -> None:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise VerifyError("sealed archive has no file inventory")
    names: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise VerifyError(f"files[{index}] schema drift")
        path = payload_path(row["path"])
        if path.is_symlink() or not path.is_file():
            raise VerifyError(f"missing/non-regular payload file: {row['path']}")
        if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise VerifyError(f"payload drift: {row['path']}")
        names.append(row["path"])
    if names != sorted(set(names)):
        raise VerifyError("payload inventory must be sorted and unique")
    actual = sorted(
        path.relative_to(PAYLOAD).as_posix()
        for path in PAYLOAD.rglob("*") if path.is_file()
    )
    if actual != names:
        raise VerifyError("payload contains unregistered files")
    external_rows = manifest.get("external_content_bindings")
    if not isinstance(external_rows, list):
        raise VerifyError("external content binding inventory is missing")
    external: set[tuple[str, str]] = set()
    for index, row in enumerate(external_rows):
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise VerifyError(f"external_content_bindings[{index}] schema drift")
        external_path(row["path"])
        binding = (row["path"], row["sha256"])
        if binding in external or not isinstance(row["sha256"], str) or len(row["sha256"]) != 64:
            raise VerifyError("external content bindings are invalid or duplicated")
        external.add(binding)

    referenced: set[tuple[str, str]] = set()
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            value = json.loads(payload_path(name).read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            continue
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                path = item.get("path")
                digest = item.get("sha256")
                if isinstance(path, str) and isinstance(digest, str) and len(digest) == 64:
                    referenced.add((path, digest))
                for key, candidate in item.items():
                    paired_digest = item.get(f"{key}_sha256")
                    if (
                        isinstance(candidate, str)
                        and "/" in candidate
                        and isinstance(paired_digest, str)
                        and len(paired_digest) == 64
                    ):
                        referenced.add((candidate, paired_digest))
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    for path, digest in referenced:
        if PurePosixPath(path).is_absolute():
            if (path, digest) not in external:
                raise VerifyError(f"unclosed external JSON binding: {path}")
            continue
        embedded = payload_path(path)
        if embedded.is_file():
            if sha(embedded) != digest and (path, digest) not in external:
                raise VerifyError(f"embedded JSON binding drift: {path}")
        elif (path, digest) not in external:
            raise VerifyError(f"unclosed mutable JSON binding: {path}")
    if external - referenced:
        raise VerifyError("unreferenced external content binding")


def verify_assertions_source(manifest: dict) -> None:
    value = manifest.get("assertions_source")
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise VerifyError("assertions source binding is malformed")
    path = payload_path(value["path"])
    if path.is_symlink() or not path.is_file() or sha(path) != value["sha256"]:
        raise VerifyError("assertions source binding drift")
    source = load(path, "assertions source")
    if source != manifest.get("assertions"):
        raise VerifyError("manifest assertions differ from their source contract")


def product_sha(rows: list[dict]) -> str:
    by_id = {row["id"]: row for row in rows}
    identities = ("product-elf", "resident-prg", "runtime-overlays", "stdlib-preload")
    try:
        payload = "".join(
            f"{artifact_id}:{by_id[artifact_id]['sha256']}\n"
            for artifact_id in identities
        )
    except KeyError as exc:
        raise VerifyError(f"product identity artifact is missing: {exc}") from exc
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def artifact_set_sha(rows: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def r3_artifact_set_sha(rows: list[dict]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def verify_generator(receipt: dict) -> None:
    generator = receipt.get("generator")
    if not isinstance(generator, dict) or set(generator) != {"path", "bytes", "sha256"}:
        raise VerifyError("reproducibility generator binding is missing")
    generator_path = payload_path(generator["path"])
    if (
        generator_path.is_symlink()
        or not generator_path.is_file()
        or generator_path.stat().st_size != generator["bytes"]
        or sha(generator_path) != generator["sha256"]
    ):
        raise VerifyError("embedded reproducibility generator drift")


def verify_varied_builds(receipt: dict) -> None:
    builds = receipt.get("builds")
    if not isinstance(builds, list) or len(builds) != 2:
        raise VerifyError("reproducibility receipt lacks the double build")
    environments = [build.get("environment") for build in builds]
    if any(not isinstance(item, dict) for item in environments):
        raise VerifyError("reproducibility build environment is missing")
    for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date"):
        if environments[0].get(key) == environments[1].get(key):
            raise VerifyError(f"reproducibility axis did not vary: {key}")


def verify_workbench_product_materialization(manifest: dict, value: dict, receipt: dict) -> None:
    value = manifest.get("product_materialization")
    if not isinstance(value, dict) or set(value) != {
        "reproducibility_receipt", "reproducibility_receipt_sha256",
        "product_sha256", "artifact_set_sha256", "artifacts",
    }:
        raise VerifyError("sealed archive lacks product materialization")
    receipt_path = payload_path(value["reproducibility_receipt"])
    if not receipt_path.is_file() or sha(receipt_path) != value["reproducibility_receipt_sha256"]:
        raise VerifyError("embedded reproducibility receipt drift")
    receipt = load(receipt_path, "reproducibility receipt")
    if (
        receipt.get("format") != "lisp65-workbench-product-reproducibility-v1"
        or receipt.get("status") != "passed"
        or receipt.get("result") != "byte-identical-across-varied-environments"
        or receipt.get("source_commit") != manifest.get("source_commit")
        or receipt.get("product_sha256") != value["product_sha256"]
        or receipt.get("artifact_set_sha256") != value["artifact_set_sha256"]
    ):
        raise VerifyError("reproducibility receipt identity/result drift")
    verify_generator(receipt)
    verify_varied_builds(receipt)
    rows = value["artifacts"]
    if not isinstance(rows, list) or rows != receipt.get("product_artifacts"):
        raise VerifyError("materialized product inventory differs from receipt")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"id", "path", "bytes", "sha256"}:
            raise VerifyError(f"materialized product artifact {index} schema drift")
        path = payload_path(row["path"])
        if path.is_symlink() or not path.is_file():
            raise VerifyError(f"materialized product artifact is missing: {row['path']}")
        if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise VerifyError(f"materialized product artifact drift: {row['path']}")
    if product_sha(rows) != value["product_sha256"] or artifact_set_sha(rows) != value["artifact_set_sha256"]:
        raise VerifyError("materialized product aggregate drift")


def verify_r3_product_materialization(manifest: dict, value: dict, receipt: dict) -> None:
    if set(value) != {
        "reproducibility_receipt", "reproducibility_receipt_sha256",
        "reproducibility_format", "product_build_id", "artifact_set_sha256",
        "artifacts",
    }:
        raise VerifyError("sealed R3 archive lacks product materialization")
    if (
        receipt.get("format") != "lisp65-r3-product-reproducibility-v1"
        or value["reproducibility_format"] != receipt["format"]
        or receipt.get("status") != "passed"
        or receipt.get("result")
        != "byte-identical-complete-product-set-across-varied-environments"
        or receipt.get("source_commit") != manifest.get("source_commit")
        or receipt.get("artifact_set_sha256") != value["artifact_set_sha256"]
        or receipt.get("product_build_id") != value["product_build_id"]
        or receipt.get("claims")
        != {"G3": "not-run", "G6": "not-run", "release_effect": "none"}
    ):
        raise VerifyError("R3 reproducibility receipt identity/result drift")
    verify_generator(receipt)
    verify_varied_builds(receipt)
    rows = value["artifacts"]
    if (
        not isinstance(rows, list)
        or rows != receipt.get("product_artifacts")
        or len(rows) != PRODUCT_ARTIFACT_COUNT
    ):
        raise VerifyError("materialized R3 product inventory differs from receipt")
    roles: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"role", "name", "path", "bytes", "sha256"}:
            raise VerifyError(f"materialized R3 product artifact {index} schema drift")
        path = payload_path(row["path"])
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]
        ):
            raise VerifyError(f"materialized R3 product artifact drift: {row['path']}")
        roles.append(row["role"])
    if len(roles) != len(set(roles)) or r3_artifact_set_sha(rows) != value["artifact_set_sha256"]:
        raise VerifyError("materialized R3 product aggregate drift")
    for build in receipt["builds"]:
        if (
            build.get("artifact_set_sha256") != value["artifact_set_sha256"]
            or build.get("product_build_id") != value["product_build_id"]
        ):
            raise VerifyError("R3 double-build identity drift")


def verify_c2_lite_product_materialization(
        manifest: dict, value: dict, receipt: dict) -> None:
    expected_claims = {
        "Fresh-Clone": "passed",
        "R4": "not-run",
        "R5": "not-run",
        "R6": "not-run",
        "G5": "not-run",
        "G6": "not-run",
        "release_effect": "none",
    }
    if set(value) != {
        "reproducibility_receipt", "reproducibility_receipt_sha256",
        "reproducibility_format", "product_build_id", "profile_build_id",
        "artifact_set_sha256", "artifacts",
    }:
        raise VerifyError("sealed C2-lite archive lacks product materialization")
    if (
        receipt.get("format") not in C2_LITE_REPRO_FORMATS
        or value["reproducibility_format"] != receipt["format"]
        or receipt.get("status") != "passed"
        or receipt.get("result")
        != "byte-identical-complete-C2-lite-media-set-across-varied-clones"
        or receipt.get("source_commit") != manifest.get("source_commit")
        or receipt.get("artifact_set_sha256") != value["artifact_set_sha256"]
        or receipt.get("product_build_id") != value["product_build_id"]
        or receipt.get("profile_build_id") != value["profile_build_id"]
        or receipt.get("claims") != expected_claims
    ):
        raise VerifyError("C2-lite reproducibility receipt identity/result drift")
    verify_generator(receipt)
    verify_varied_builds(receipt)
    rows = value["artifacts"]
    if (
        not isinstance(rows, list)
        or rows != receipt.get("product_artifacts")
        or len(rows) != C2_LITE_PRODUCT_ARTIFACT_COUNT
    ):
        raise VerifyError(
            "materialized C2-lite product inventory differs from receipt")
    roles: list[str] = []
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"role", "name", "path", "bytes", "sha256"}
        ):
            raise VerifyError(
                f"materialized C2-lite product artifact {index} schema drift")
        path = payload_path(row["path"])
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]
        ):
            raise VerifyError(
                f"materialized C2-lite product artifact drift: {row['path']}")
        roles.append(row["role"])
    if (
        len(roles) != len(set(roles))
        or r3_artifact_set_sha(rows) != value["artifact_set_sha256"]
    ):
        raise VerifyError("materialized C2-lite product aggregate drift")
    for build in receipt["builds"]:
        if (
            build.get("artifact_set_sha256") != value["artifact_set_sha256"]
            or build.get("product_build_id") != value["product_build_id"]
            or build.get("profile_build_id") != value["profile_build_id"]
        ):
            raise VerifyError("C2-lite double-build identity drift")


def verify_product_materialization(manifest: dict) -> None:
    value = manifest.get("product_materialization")
    if not isinstance(value, dict):
        raise VerifyError("sealed archive lacks product materialization")
    receipt_path = payload_path(value.get("reproducibility_receipt"))
    if (
        not receipt_path.is_file()
        or sha(receipt_path) != value.get("reproducibility_receipt_sha256")
    ):
        raise VerifyError("embedded reproducibility receipt drift")
    receipt = load(receipt_path, "reproducibility receipt")
    if receipt.get("format") == "lisp65-workbench-product-reproducibility-v1":
        verify_workbench_product_materialization(manifest, value, receipt)
    elif receipt.get("format") == "lisp65-r3-product-reproducibility-v1":
        verify_r3_product_materialization(manifest, value, receipt)
    elif receipt.get("format") in C2_LITE_REPRO_FORMATS:
        verify_c2_lite_product_materialization(manifest, value, receipt)
    else:
        raise VerifyError("unknown reproducibility receipt format")


def verify_remote_source_binding(manifest: dict) -> None:
    """Validate a recorded online observation without consulting the network."""
    value = manifest.get("remote_source_binding")
    if value is None:
        if manifest.get("format") == FORMAT_V2:
            # Historical v2 archives predate the mandatory remote-presence gate.
            return
        raise VerifyError("promotion remote source binding is missing")
    source = manifest.get("source_commit")
    if (
        not isinstance(value, dict)
        or set(value) != {
            "branch_ref", "format", "relation", "remote", "remote_head",
            "remote_transport_head", "source_commit", "source_transport_commit", "version",
        }
        or value.get("format") != "lisp65-evidence-remote-source-binding-v1"
        or value.get("version") != 1 or value.get("remote") != "github"
        or not isinstance(value.get("branch_ref"), str)
        or not value["branch_ref"].startswith("refs/heads/")
        or value.get("source_commit") != source
        or not isinstance(source, str) or len(source) != 40
        or not isinstance(value.get("source_transport_commit"), str)
        or len(value["source_transport_commit"]) != 40
        or not isinstance(value.get("remote_head"), str)
        or len(value["remote_head"]) != 40
        or not isinstance(value.get("remote_transport_head"), str)
        or len(value["remote_transport_head"]) != 40
        or value.get("relation") != "source-commit-is-remote-ancestor"
    ):
        raise VerifyError("promotion remote source binding drift")


def run_payload(argv: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, *argv], cwd=PAYLOAD, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise VerifyError(
            f"archived verifier failed ({' '.join(argv)}):\n{result.stdout}"
        )


def verify_carrier(assertions: dict) -> None:
    verify_capacity_delta(assertions)
    contract_path = payload_path(assertions["contract"])
    contract = load(contract_path, "carrier contract")
    checkpoints = contract.get("checkpoints")
    if (
        contract.get("id") != "v2-capability-carrier"
        or contract.get("status") != "promoted"
        or not isinstance(checkpoints, list) or len(checkpoints) != 5
        or [item.get("status") for item in checkpoints] != ["passed"] * 5
    ):
        raise VerifyError("carrier promotion identity/checkpoint drift")
    run_payload([
        "tools/host-lisp/v2_capability_carrier_contract.py",
        "--contract", assertions["contract"],
        "--fixture", assertions["surface_fixture"], "check",
    ])
    run_payload(["tools/host-lisp/v2_cp5_g5_archive.py", "check"])


def verify_family(assertions: dict) -> None:
    verify_capacity_delta(assertions)
    family = assertions["family"]
    migration_path = payload_path(assertions["migration_contract"])
    migration = load(migration_path, "migration contract")
    rows = migration.get("families")
    selected = next(
        (item for item in rows if isinstance(item, dict) and item.get("id") == family),
        None,
    ) if isinstance(rows, list) else None
    source_status = assertions.get("source_family_status", "migrated")
    promotes_to = assertions.get("promotes_to", "migrated")
    if (
        not isinstance(selected, dict)
        or selected.get("status") != source_status
        or promotes_to != "migrated"
    ):
        raise VerifyError(f"family {family} source/promotion status drift")
    measurement = (
        selected.get("measurement")
        if source_status == "migrated" else assertions.get("measurement")
    )
    if not isinstance(measurement, dict):
        raise VerifyError(f"family {family} lacks measurement")
    for path_key, sha_key in (
        ("differential_receipt", "differential_receipt_sha256"),
        ("baseline_manifest", "baseline_manifest_sha256"),
        ("candidate_manifest", "candidate_manifest_sha256"),
    ):
        path = payload_path(measurement[path_key])
        if sha(path) != measurement[sha_key]:
            raise VerifyError(f"family {family} measurement binding drift")
    receipt = load(payload_path(measurement["differential_receipt"]), "family receipt")
    engines = receipt.get("engine_results")
    if (
        receipt.get("family") != family or receipt.get("result") != "passed"
        or not isinstance(engines, list) or len(engines) < 2
        or any(item.get("result") != "passed" for item in engines)
        or not isinstance(receipt.get("actual"), dict)
        or any(
            receipt["actual"].get(key) != value
            for key, value in selected.get("projection", {}).items()
        )
    ):
        raise VerifyError(f"family {family} differential receipt drift")
    decision = load(payload_path(assertions["decision_contract"]), "R2 decision contract")
    if decision.get("status") != "decided" or len(decision.get("decisions", [])) != 9:
        raise VerifyError("R2 decision prerequisite drift")
    ledger = load(payload_path(assertions["capacity_ledger"]), "capacity ledger")
    ledger_family = next(
        (
            item for item in ledger.get("family_measurements", [])
            if isinstance(item, dict) and item.get("id") == family
        ),
        None,
    )
    expected_ledger_status = (
        "migrated" if source_status == "migrated" else "promotion-ready"
    )
    if (
        not isinstance(ledger_family, dict)
        or ledger_family.get("status") != expected_ledger_status
        or ledger.get("cumulative", {}).get("capability_prerequisites_satisfied") is not True
        or ledger.get("contract_binding", {}).get("sha256") != sha(migration_path)
    ):
        raise VerifyError("family capacity/prerequisite drift")


def bound_json(item: object, label: str) -> dict:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise VerifyError(f"{label} binding is malformed")
    path = payload_path(item["path"])
    if path.is_symlink() or not path.is_file() or sha(path) != item["sha256"]:
        raise VerifyError(f"{label} binding drift")
    return load(path, label)


def verify_g3_receipt(receipt: dict, artifact_set: str, product_build_id: str) -> None:
    if (
        receipt.get("format") != "lisp65-r3-g3-emulator-receipt-v1"
        or receipt.get("status") != "passed-emulator-prefilter-only"
        or receipt.get("release_effect") != "none-r4-not-sealed"
        or receipt.get("product_artifact_set_sha256") != artifact_set
        or receipt.get("product_build_id") != product_build_id
        or receipt.get("counts") != {"pass": 9, "not_run": 6, "total": 15}
    ):
        raise VerifyError("R4 G3 receipt identity/status drift")
    cases = receipt.get("cases")
    if not isinstance(cases, list) or len(cases) != 15:
        raise VerifyError("R4 G3 case closure drift")
    emulator = [row for row in cases if row.get("fidelity") == "emulator-valid"]
    hardware = [row for row in cases if row.get("fidelity") == "hardware-only"]
    if (
        len(emulator) != 9 or {row.get("status") for row in emulator} != {"pass"}
        or len(hardware) != 6 or {row.get("status") for row in hardware} != {"not-run"}
    ):
        raise VerifyError("R4 G3 fidelity/status boundary drift")
    claims = receipt.get("claims")
    if (
        not isinstance(claims, dict)
        or claims.get("G3") != "pass" or claims.get("G6") != "not-run"
        or claims.get("hardware_started") is not False
        or claims.get("emulator_authority") != "prefilter-only"
        or claims.get("hardware_authority") != "arbiter"
        or set(claims.get("forbidden_hardware_claims", {}).values()) != {False}
    ):
        raise VerifyError("R4 G3 claim boundary drift")
    evidence: list[dict] = []
    evidence.extend(receipt.get("bindings", {}).values())
    for row in cases:
        evidence.extend(row.get("evidence", []))
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise VerifyError("R4 G3 evidence binding schema drift")
        path = payload_path(item["path"])
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]
        ):
            raise VerifyError(f"R4 G3 evidence binding drift: {item['path']}")


def verify_c2_lite_product_candidate(manifest: dict, assertions: dict) -> None:
    verify_capacity_delta(assertions)
    if (
        assertions.get("format")
        != "lisp65-c2-lite-r4-product-candidate-assertions-v1"
        or assertions.get("version") != 1
        or assertions.get("id") != "c2-lite-r4-complete-media-product"
        or assertions.get("status") != "seal-authorized"
    ):
        raise VerifyError("C2-lite R4 assertion identity drift")
    candidate = assertions.get("candidate")
    if not isinstance(candidate, dict) or set(candidate) != {
        "artifact_set_sha256", "product_build_id", "profile_build_id",
        "artifact_count",
    }:
        raise VerifyError("C2-lite R4 candidate identity is malformed")
    materialized = manifest.get("product_materialization", {})
    if (
        candidate["artifact_set_sha256"]
        != materialized.get("artifact_set_sha256")
        or candidate["product_build_id"]
        != materialized.get("product_build_id")
        or candidate["profile_build_id"]
        != materialized.get("profile_build_id")
        or candidate["artifact_count"] != C2_LITE_PRODUCT_ARTIFACT_COUNT
        or candidate["artifact_count"] != len(materialized.get("artifacts", []))
    ):
        raise VerifyError("C2-lite R4 candidate/materialized identity drift")
    if assertions.get("claims") != {
        "Fresh-Clone": "passed",
        "R4": "sealed-complete-media-product-candidate",
        "R5": "not-run",
        "R6": "not-run",
        "G5": "not-run",
        "G6": "not-run",
        "hardware_evidence_inherited": False,
        "release": "not-release-capable",
    }:
        raise VerifyError("C2-lite R4 claim boundary drift")
    bindings = assertions.get("bindings")
    old_binding_keys = {
        "media_contract",
        "matrix_terminal_disposition",
        "link66_measurement_context",
    }
    v121_binding_keys = {
        "media_contract",
        "link77_cross_invariant_delta_review",
        "link77_hardware_measurement_context",
    }
    v122_binding_keys = {
        "media_contract",
        "link78_cross_invariant_delta_review",
        "link78_feature_history_not_acceptance",
    }
    v123_binding_keys = {
        "media_contract",
        "link80_cross_invariant_delta_review",
        "link80_feature_history_not_acceptance",
    }
    v124_binding_keys = {
        "media_contract",
        "link81_cross_invariant_delta_review",
        "link81_feature_history_not_acceptance",
    }
    v125_binding_keys = {
        "media_contract",
        "link82_cross_invariant_delta_review",
        "link82_prior_append_release_terminal",
    }
    v130_binding_keys = {
        "media_contract",
        "link88_cross_invariant_delta_review",
        "link88_physical_keyboard_end_to_end",
    }
    if (
        not isinstance(bindings, dict)
        or frozenset(bindings) not in {
            frozenset(old_binding_keys), frozenset(v121_binding_keys),
            frozenset(v122_binding_keys), frozenset(v123_binding_keys),
            frozenset(v124_binding_keys), frozenset(v125_binding_keys),
            frozenset(v130_binding_keys),
        }
    ):
        raise VerifyError("C2-lite R4 binding closure drift")
    media = bound_json(bindings["media_contract"], "C2-lite media contract")
    if (
        media.get("format") != "lisp65-c2-lite-media-product-v1"
        or media.get("status")
        != "owner-authorized-for-fresh-clone-R4-R5-R6-G5-G6"
        or media.get("artifact_count") != C2_LITE_PRODUCT_ARTIFACT_COUNT
        or set(media.get("artifact_roles", []))
        != {row["role"] for row in materialized["artifacts"]}
    ):
        raise VerifyError("C2-lite R4 media-contract closure drift")
    if set(bindings) == old_binding_keys:
        matrix = bound_json(
            bindings["matrix_terminal_disposition"],
            "C2-lite matrix terminal disposition")
        if (
            matrix.get("format")
            != "lisp65-c2.2-cross-invariant-C1-terminal-disposition-v1"
            or matrix.get("status")
            != "C1-documented-C2.3-deferred-matrix-gate-may-fall"
            or matrix.get("gate_transition", {}).get("matrix_gate") != "FALLS"
            or matrix.get("gate_transition", {}).get(
                "no_inherited_green") is not True
        ):
            raise VerifyError("C2-lite R4 matrix authorization drift")
        measurement = bound_json(
            bindings["link66_measurement_context"],
            "C2-lite Link-66 measurement context")
        if (
            measurement.get("format")
            != "lisp65-c2.2-link66-bundled-hardware-measurements-v1"
            or measurement.get("status")
            != "passed-Link66-product-measurement-bundle-C1-separately-documented"
            or measurement.get("claim_limit") is None
        ):
            raise VerifyError("C2-lite R4 measurement context drift")
        expected_hardware_results = "fresh-only-no-Link66-inheritance"
    elif set(bindings) == v121_binding_keys:
        matrix = bound_json(
            bindings["link77_cross_invariant_delta_review"],
            "v1.2.1 Link-77 cross-invariant delta review")
        summary = matrix.get("summary")
        if (
            matrix.get("format")
            != "lisp65-v1.2.1-link77-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link77-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate") != "remains-fallen-for-C2.2"
        ):
            raise VerifyError("v1.2.1 R4 matrix-delta authorization drift")
        measurement = bound_json(
            bindings["link77_hardware_measurement_context"],
            "v1.2.1 Link-77 hardware measurement context")
        if (
            measurement.get("format")
            != "lisp65-c2.2-link77-gc-bundled-hardware-v1"
            or measurement.get("status")
            != "completed-GC-random-RUNSTOP-IRQ-DIRMISS-bundle"
            or measurement.get("row_local_first_reds") != []
            or measurement.get("claim_limit") is None
        ):
            raise VerifyError("v1.2.1 R4 measurement context drift")
        expected_hardware_results = "fresh-only-no-Link77-inheritance"
    elif set(bindings) == v122_binding_keys:
        matrix = bound_json(
            bindings["link78_cross_invariant_delta_review"],
            "v1.2.2 Link-78 cross-invariant delta review")
        summary = matrix.get("summary")
        if (
            matrix.get("format")
            != "lisp65-v1.2.2-link78-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link78-L65E-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate") != "remains-fallen-for-C2.2"
        ):
            raise VerifyError("v1.2.2 R4 matrix-delta authorization drift")
        history = bound_json(
            bindings["link78_feature_history_not_acceptance"],
            "v1.2.2 Link-78 feature history")
        rows = history.get("passed_rows")
        if (
            history.get("format")
            != "lisp65-c2.2-link78-d1-d2-hardware-receipt-v1"
            or history.get("status")
            != "D2-returned-to-Class-C-without-investigation"
            or not isinstance(rows, list)
            or not any(
                row.get("id") == "dirmiss-full-name"
                and row.get("outcome")
                == "*** undefined function: intern-renderer-missing"
                for row in rows if isinstance(row, dict)
            )
            or history.get("claim_limit") is None
        ):
            raise VerifyError("v1.2.2 R4 feature-history binding drift")
        expected_hardware_results = "fresh-only-no-Link78-inheritance"
    elif set(bindings) == v123_binding_keys:
        matrix = bound_json(
            bindings["link80_cross_invariant_delta_review"],
            "v1.2.3 Link-80 cross-invariant delta review")
        summary = matrix.get("summary")
        if (
            matrix.get("format")
            != "lisp65-v1.2.3-link80-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link80-v1.2.3-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate") != "remains-fallen-for-C2.2"
        ):
            raise VerifyError("v1.2.3 R4 matrix-delta authorization drift")
        history = bound_json(
            bindings["link80_feature_history_not_acceptance"],
            "v1.2.3 Link-80 feature history")
        if (
            history.get("format")
            != "lisp65-c2-v1.2.3-link80-require-device-discriminator-hw-v2"
            or history.get("status") != "anomaly-not-reproduced"
            or history.get("attempt_1", {}).get("result") != "t"
            or history.get("attempt_2", {}).get("result") != "t"
            or history.get("claim_limit") is None
        ):
            raise VerifyError("v1.2.3 R4 feature-history binding drift")
        expected_hardware_results = "fresh-only-no-Link80-inheritance"
    elif set(bindings) == v124_binding_keys:
        matrix = bound_json(
            bindings["link81_cross_invariant_delta_review"],
            "v1.2.4 Link-81 cross-invariant delta review")
        summary = matrix.get("summary")
        if (
            matrix.get("format")
            != "lisp65-v1.2.4-link81-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link81-fx-time-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate") != "remains-fallen-for-C2.2"
        ):
            raise VerifyError("v1.2.4 R4 matrix-delta authorization drift")
        history = bound_json(
            bindings["link81_feature_history_not_acceptance"],
            "v1.2.4 Link-81 feature history")
        if (
            history.get("format")
            != "lisp65-c2.2-v1.2.4-phase-m-hardware-v2"
            or history.get("status")
            != "passed-one-bundled-session-with-M1-harness-correction"
            or history.get("M3_fx", {}).get("status")
            != "passed-target-multiply-divide-rounding-smoke"
            or history.get("M4_time", {}).get("status")
            != "passed-50Hz-calibration"
            or history.get("claim_limit") is None
        ):
            raise VerifyError("v1.2.4 R4 feature-history binding drift")
        expected_hardware_results = "fresh-only-no-Link81-inheritance"
    elif set(bindings) == v125_binding_keys:
        matrix = bound_json(
            bindings["link82_cross_invariant_delta_review"],
            "v1.2.5 Link-82 cross-invariant delta review")
        summary = matrix.get("summary")
        if (
            matrix.get("format")
            != "lisp65-v1.2.5-link82-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link82-require-Option-A-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate") != "remains-fallen-for-C2.2"
            or matrix.get("method", {}).get("rederived_count") != 6
            or matrix.get("method", {}).get(
                "explicit_not_rederived_count") != 19
        ):
            raise VerifyError("v1.2.5 R4 matrix-delta authorization drift")
        hardware = bound_json(
            bindings["link82_prior_append_release_terminal"],
            "v1.2.5 Link-82 prior-append hardware acceptance")
        if (
            hardware.get("format")
            != "lisp65-c2.2-v1.2.5-require-prior-append-hardware-v1"
            or hardware.get("status")
            != "passed-require-after-two-ordinary-persistent-appends"
            or hardware.get("results", {}).get(
                "require-after-two-ordinary-appends") != "t"
            or hardware.get("results", {}).get(
                "require-after-two-ordinary-appends-repeat") != "t"
            or hardware.get("readback", {}).get("c2j") != "CLEAR"
            or hardware.get("claim_limit") is None
        ):
            raise VerifyError("v1.2.5 R4 prior-append binding drift")
        expected_hardware_results = "fresh-only-no-Link82-inheritance"
    else:
        matrix = bound_json(
            bindings["link88_cross_invariant_delta_review"],
            "v1.3.0 Link-88 cross-invariant delta review")
        summary = matrix.get("summary")
        method = matrix.get("method")
        if (
            matrix.get("format")
            != "lisp65-v1.3.0-link88-cross-invariant-delta-v1"
            or matrix.get("status")
            != "passed-Link88-v1.3.0-delta-review-no-new-open-row"
            or not isinstance(matrix.get("rows"), list)
            or len(matrix["rows"]) != 25
            or not isinstance(summary, dict)
            or summary.get("new_OPEN_rows") != 0
            or summary.get("matrix_gate")
            != "Link88-v1.3.0-delta-reviewed-no-new-open-row"
            or not isinstance(method, dict)
            or method.get("rederived_count") != 15
            or method.get("explicit_not_rederived_count") != 10
        ):
            raise VerifyError("v1.3.0 R4 matrix-delta authorization drift")
        hardware = bound_json(
            bindings["link88_physical_keyboard_end_to_end"],
            "v1.3.0 Link-88 physical-keyboard acceptance")
        observation = hardware.get("operator_observation")
        if (
            hardware.get("format")
            != "lisp65-c2.3-v1.3-link88-interactive-human-device-v1"
            or hardware.get("status")
            != "passed-Link88-physical-keyboard-end-to-end"
            or hardware.get("candidate_link") != 88
            or hardware.get("product_bytes_changed_after_link") != 0
            or not isinstance(observation, dict)
            or observation.get("expected_greeting") != "Hello, Ada!"
            or observation.get("greeting_present") is not True
            or hardware.get("claim_limit") is None
        ):
            raise VerifyError("v1.3.0 R4 physical-keyboard binding drift")
        expected_hardware_results = "fresh-only-no-Link88-inheritance"
    if assertions.get("r5_handoff") != {
        "input_authority": "sealed-c2-lite-r4-product-candidate-archive",
        "live_tree": "not-an-authority",
        "required_artifact_set_sha256": candidate["artifact_set_sha256"],
        "hardware_results": expected_hardware_results,
    }:
        raise VerifyError("C2-lite R4-to-R5 handoff drift")


def verify_product_candidate(manifest: dict, assertions: dict) -> None:
    if (
        assertions.get("format")
        == "lisp65-c2-lite-r4-product-candidate-assertions-v1"
    ):
        verify_c2_lite_product_candidate(manifest, assertions)
        return
    verify_capacity_delta(assertions)
    if (
        assertions.get("format") != "lisp65-r4-product-candidate-assertions-v1"
        or assertions.get("version") != 1
        or assertions.get("id") != "r4-final-product-candidate"
        or assertions.get("status") != "seal-authorized"
    ):
        raise VerifyError("R4 product-candidate assertion identity drift")
    candidate = assertions.get("candidate")
    if not isinstance(candidate, dict) or set(candidate) != {
        "artifact_set_sha256", "product_build_id", "artifact_count",
    }:
        raise VerifyError("R4 product-candidate identity is malformed")
    materialized = manifest.get("product_materialization", {})
    if (
        candidate["artifact_set_sha256"] != materialized.get("artifact_set_sha256")
        or candidate["product_build_id"] != materialized.get("product_build_id")
        or candidate["artifact_count"] != len(materialized.get("artifacts", []))
        or candidate["artifact_count"] != PRODUCT_ARTIFACT_COUNT
    ):
        raise VerifyError("R4 product-candidate/materialized identity drift")
    claims = assertions.get("claims")
    if claims != {
        "G3": "passed-emulator-prefilter-only",
        "emulator_valid": "9/9-pass",
        "hardware_only": "6/6-not-run",
        "G5": "not-run",
        "G6": "not-run",
        "release": "not-release-capable",
        "hardware_started": False,
        "forbidden_hardware_claims": [
            "F011-timing", "SD-buffer-address", "DMA-timing",
            "physical-reset-semantics",
        ],
    }:
        raise VerifyError("R4 product-candidate claims drift")
    bindings = assertions.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != {
        "g3_receipt", "static_preflight", "product_block_receipt",
        "r3_contract_snapshot", "boot_matrix",
    }:
        raise VerifyError("R4 product-candidate binding closure drift")
    g3 = bound_json(bindings["g3_receipt"], "R4 G3 receipt")
    verify_g3_receipt(g3, candidate["artifact_set_sha256"], candidate["product_build_id"])
    preflight = bound_json(bindings["static_preflight"], "R4 G3 static preflight")
    if (
        preflight.get("format") != "lisp65-r3-g3-static-preflight-v1"
        or preflight.get("status") != "passed-g3-not-run"
        or preflight.get("product_artifact_set_sha256") != candidate["artifact_set_sha256"]
        or preflight.get("counts")
        != {"emulator-valid": 9, "hardware-only": 6, "total": 15}
        or preflight.get("claims", {}).get("static_bindings_complete") is not True
        or preflight.get("claims", {}).get("hardware_started") is not False
    ):
        raise VerifyError("R4 static preflight boundary drift")
    product = bound_json(bindings["product_block_receipt"], "R4 product block receipt")
    if (
        product.get("format") != "lisp65-r3-product-block-receipt-v1"
        or product.get("status") != "product-implemented-g3-not-run"
        or product.get("release_effect") != "none"
        or product.get("product_identity", {}).get("artifact_set_sha256")
        != candidate["artifact_set_sha256"]
        or product.get("product_identity", {}).get("product_build_id")
        != candidate["product_build_id"]
        or product.get("null_deltas", {}).get("workbench_bank_bytes") != 0
        or product.get("null_deltas", {}).get("boot_overlay_bytes") != 0
    ):
        raise VerifyError("R4 product-block identity/null-delta drift")
    contract = bound_json(bindings["r3_contract_snapshot"], "R4 R3 contract snapshot")
    if (
        contract.get("format") != "lisp65-r3-g3-g6-contract-v1"
        or contract.get("authority", {}).get("emulator") != "prefilter-only"
        or contract.get("authority", {}).get("hardware") != "arbiter"
        or contract.get("product_block", {}).get("artifact_set_sha256")
        != candidate["artifact_set_sha256"]
    ):
        raise VerifyError("R4 R3 contract snapshot drift")
    matrix = bound_json(bindings["boot_matrix"], "R4 boot matrix")
    matrix_cases = matrix.get("cases")
    if not isinstance(matrix_cases, list) or len(matrix_cases) != 15:
        raise VerifyError("R4 boot matrix closure drift")
    if assertions.get("boot_overlay_delta_bytes") != 0:
        raise VerifyError("R4 boot-overlay delta is not zero")
    if assertions.get("r5_handoff") != {
        "input_authority": "sealed-r4-product-candidate-archive",
        "live_tree": "not-an-authority",
        "required_artifact_set_sha256": candidate["artifact_set_sha256"],
    }:
        raise VerifyError("R4-to-R5 handoff authority drift")


def verify_capacity_delta(assertions: dict) -> None:
    dimensions = ("bank", "ext", "symbols", "namepool", "directory")
    item = assertions.get("capacity_delta")
    if not isinstance(item, dict) or set(item) != {
        "baseline_identity_sha256", "candidate_identity_sha256", "dimensions",
    }:
        raise VerifyError("promotion capacity_delta is missing or malformed")
    for key in ("baseline_identity_sha256", "candidate_identity_sha256"):
        value = item[key]
        if (
            not isinstance(value, str) or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise VerifyError("promotion capacity_delta identity drift")
    values = item["dimensions"]
    if not isinstance(values, dict) or set(values) != set(dimensions):
        raise VerifyError("promotion capacity_delta dimension drift")
    policy = load(payload_path("config/block-capacity-delta-policy.json"), "capacity policy")
    if (
        policy.get("format") != "lisp65-block-capacity-delta-policy-v1"
        or policy.get("status") != "active"
        or policy.get("receipt_field") != "capacity_delta"
        or set(policy.get("dimensions", {})) != set(dimensions)
    ):
        raise VerifyError("promotion capacity policy drift")
    for name in dimensions:
        dimension = values[name]
        if not isinstance(dimension, dict) or set(dimension) != {
            "baseline", "candidate", "delta", "authorization",
        }:
            raise VerifyError(f"promotion capacity_delta {name} schema drift")
        baseline = dimension["baseline"]
        candidate = dimension["candidate"]
        delta = dimension["delta"]
        if (
            any(type(value) is not int for value in (baseline, candidate, delta))
            or candidate - baseline != delta
        ):
            raise VerifyError(f"promotion capacity_delta {name} arithmetic drift")
        authorization = dimension["authorization"]
        if delta >= 0:
            if authorization is not None:
                raise VerifyError(f"promotion capacity_delta {name} credit has authorization")
            continue
        if not isinstance(authorization, dict) or set(authorization) != {"path", "sha256"}:
            raise VerifyError(f"promotion capacity_delta {name} debit lacks authorization")
        path = payload_path(authorization["path"])
        if path.is_symlink() or not path.is_file() or sha(path) != authorization["sha256"]:
            raise VerifyError(f"promotion capacity_delta {name} authorization binding drift")
        decision = load(path, "capacity debit authorization")
        debits = decision.get("authorized_debits")
        floors = decision.get("required_floors")
        if (
            decision.get("format") != "lisp65-capacity-debit-authorization-v1"
            or decision.get("status") != "authorized"
            or decision.get("timing") != "pre-authorized"
            or not isinstance(debits, dict) or type(debits.get(name)) is not int
            or -delta > debits[name]
            or not isinstance(floors, dict) or type(floors.get(name)) is not int
            or candidate < floors[name]
        ):
            raise VerifyError(f"promotion capacity_delta {name} authorization does not cover debit")


def remote_binding_selftest() -> None:
    source = "1" * 40
    binding = {
        "format": "lisp65-evidence-remote-source-binding-v1",
        "version": 1,
        "remote": "github",
        "branch_ref": "refs/heads/test",
        "remote_head": "2" * 40,
        "remote_transport_head": "2" * 40,
        "source_commit": source,
        "source_transport_commit": source,
        "relation": "source-commit-is-remote-ancestor",
    }
    current = {"format": FORMAT_V3, "source_commit": source, "remote_source_binding": binding}
    verify_remote_source_binding(current)
    for label, mutation in (
        ("missing", {"format": FORMAT_V3, "source_commit": source}),
        ("head", {**current, "remote_source_binding": {**binding, "remote_head": "2" * 39}}),
    ):
        try:
            verify_remote_source_binding(mutation)
        except VerifyError:
            continue
        raise VerifyError(f"remote-binding selftest accepted {label} mutation")
    verify_remote_source_binding({"format": FORMAT_V2, "source_commit": source})
    print("promotion-archive-offline: REMOTE BINDING SELFTEST PASS mutations=2 historical-v2=accepted")


def main() -> int:
    try:
        if sys.argv[1:] == ["--remote-binding-selftest"]:
            remote_binding_selftest()
            return 0
        manifest = load(ROOT / "manifest.json", "promotion archive manifest")
        if (
            manifest.get("format") not in {FORMAT_V2, FORMAT_V3}
            or manifest.get("status") != "sealed"
            or manifest.get("immutability") != "append-only-never-amend"
        ):
            raise VerifyError("promotion archive identity/policy drift")
        verify_inventory(manifest)
        verify_remote_source_binding(manifest)
        verify_assertions_source(manifest)
        verify_product_materialization(manifest)
        kind = manifest.get("kind")
        assertions = manifest.get("assertions")
        if not isinstance(assertions, dict):
            raise VerifyError("promotion assertions are missing")
        if kind == "capability-carrier":
            verify_carrier(assertions)
        elif kind == "family":
            verify_family(assertions)
        elif kind == "product-candidate":
            verify_product_candidate(manifest, assertions)
        else:
            raise VerifyError(f"unknown promotion kind: {kind!r}")
        print(
            "promotion-archive-offline: PASS "
            f"id={manifest['id']} files={len(manifest['files'])}"
        )
        return 0
    except (VerifyError, KeyError, TypeError, ValueError) as exc:
        print(f"promotion-archive-offline: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
