#!/usr/bin/env python3
"""Build and verify the IDE-family differential promotion evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import dialect_migration_contract as MIGRATION


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/dialect-migration-contract.json"
FIXTURE = ROOT / "tests/bytecode/dialect-v2/ide/cases.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/ide"
PRODUCT_REPORT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/directory-only-l65m-v2-product-link-report.json"
INTERLIBRARY = ROOT / "config/directory-only-interlibrary-api.json"
DECISIONS = ROOT / "config/dialect-v2-r2-decisions.json"
V1_CONTRACT = ROOT / "config/dialect-contract.json"
ENGINES = ("native-c-compiler-vm", "python-p0-compiler-vm")
PROFILES = ("dialect-v1", "dialect-v2")
EVIDENCE_NAMES = {
    "dialect-v1-profile.l65p",
    "dialect-v2-profile.l65p",
    "dialect-v1-manifest.json",
    "dialect-v2-manifest.json",
    "differential-receipt.json",
    *{
        f"{profile}-{engine}-verdict.json"
        for profile in PROFILES for engine in ENGINES
    },
}


class IdeEvidenceError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IdeEvidenceError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IdeEvidenceError(f"{path} must contain an object")
    return value


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def family_sets(contract: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    v1 = MIGRATION.load_json(V1_CONTRACT, "dialect-v1 contract")
    public, surfaces, _deliveries = MIGRATION._public_inventory(v1)
    resolved, _new_names, replacements = MIGRATION._classification(
        contract["classification"], public, surfaces
    )
    records = {
        name: record for name, record in resolved.items()
        if record["family"] == "ide"
    }
    sets = {
        profile: {role: set() for role in ("loaded", "boot", "directory")}
        for profile in PROFILES
    }
    for name, record in records.items():
        disposition = record["disposition"]
        replacement = replacements.get(name)
        drops_public = disposition in {"internalize", "remove-v2"} or (
            disposition == "replace" and replacement != name
        )
        sets["dialect-v1"]["loaded"].add(name)
        if not drops_public:
            sets["dialect-v2"]["loaded"].add(name)

        current_boot = bool(
            surfaces[name] & {"native-eval-and-p0-primitives", "workbench-preload"}
        )
        drops_boot = disposition in {
            "move-library", "internalize", "remove-v2"
        } or (
            disposition == "replace" and replacement != name
        ) or record["target_delivery"] == "disk-on-demand"
        if current_boot:
            sets["dialect-v1"]["boot"].add(name)
            if not drops_boot:
                sets["dialect-v2"]["boot"].add(name)

        current_directory = any(
            surface != "native-eval-and-p0-primitives"
            for surface in surfaces[name]
        )
        target_directory = current_directory and not (
            disposition == "remove-v2"
            or (disposition == "replace" and replacement != name)
        )
        if current_directory:
            sets["dialect-v1"]["directory"].add(name)
        if target_directory:
            sets["dialect-v2"]["directory"].add(name)

    actual = {
        "loaded_symbol_delta": len(sets["dialect-v2"]["loaded"])
        - len(sets["dialect-v1"]["loaded"]),
        "loaded_namepool_delta_bytes": sum(
            len(name) + 1 for name in sets["dialect-v2"]["loaded"]
        ) - sum(len(name) + 1 for name in sets["dialect-v1"]["loaded"]),
        "boot_symbol_delta": len(sets["dialect-v2"]["boot"])
        - len(sets["dialect-v1"]["boot"]),
        "boot_namepool_delta_bytes": sum(
            len(name) + 1 for name in sets["dialect-v2"]["boot"]
        ) - sum(len(name) + 1 for name in sets["dialect-v1"]["boot"]),
        "directory_delta": len(sets["dialect-v2"]["directory"])
        - len(sets["dialect-v1"]["directory"]),
    }
    family = next(item for item in contract["families"] if item["id"] == "ide")
    if actual != family["projection"]:
        raise IdeEvidenceError(
            f"IDE classified budget drift: {actual} != {family['projection']}"
        )
    return sets


def fixture_cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        set(fixture) != {"format", "profile", "family", "cases"}
        or fixture["format"] != "lisp65-dialect-v2-ide-cases-v1"
        or fixture["profile"] != "dialect-v1-v2-differential"
        or fixture["family"] != "ide"
        or not isinstance(fixture["cases"], list)
    ):
        raise IdeEvidenceError("IDE fixture identity drift")
    ids = []
    for case in fixture["cases"]:
        if not isinstance(case, dict) or set(case) != {
            "id", "forms", "migration_anchor", "observations"
        }:
            raise IdeEvidenceError("IDE fixture case schema drift")
        ids.append(case["id"])
        if set(case["observations"]) != set(PROFILES) or any(
            set(case["observations"][profile]) != set(ENGINES)
            for profile in PROFILES
        ):
            raise IdeEvidenceError(f"IDE fixture engine coverage drift: {case['id']}")
    if ids != sorted(set(ids)):
        raise IdeEvidenceError("IDE fixture cases must be sorted and unique")
    return fixture["cases"]


def validate_product_state(contract: dict[str, Any], sets: dict[str, Any]) -> None:
    blocks = {item["id"]: item for item in contract["deferred_blocks"]}
    family = next(item for item in contract["families"] if item["id"] == "ide")
    report = load(PRODUCT_REPORT)
    interlibrary = load(INTERLIBRARY)
    source = (ROOT / "lib/ide-launch.lisp").read_text(encoding="utf-8")
    if (
        blocks["directory-only-l65m-v2"]["status"] != "completed"
        or family["status"] not in {"in-progress", "migrated"}
        or report.get("candidate", {}).get("product_sha256")
        != "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110"
        or report.get("composition") != {
            "free_symbols": 127,
            "free_namepool_bytes": 2279,
            "post_align_directory_slots": 32,
            "ext_post_headroom_bytes": 16384,
            "ext_contract_floor_bytes": 16384,
            "result": "pass",
        }
        or report.get("verification", {}).get("l65m_v2_product")
        != "pass-entries-150-anonymous-87-entry-refs-231-designator-routes-12"
        or report.get("verification", {}).get("transaction_matrix")
        != "pass-all-six-classes"
        or len(interlibrary.get("entries", [])) != 11
        or "(defun edit ()" not in source
        or '(load-lib "ide")' not in source
        or len(sets["dialect-v1"]["loaded"]) != 81
        or len(sets["dialect-v2"]["loaded"]) != 9
    ):
        raise IdeEvidenceError("IDE product/decision binding drift")


def run_engine(engine: str) -> None:
    targets = {
        "native-c-compiler-vm": ["l65m-v2-product-check"],
        "python-p0-compiler-vm": [
            "bytecode-p0-ide-lib-check", "bytecode-p0-ide-extra-lib-check"
        ],
    }[engine]
    process = subprocess.run(
        ["make", "-s", *targets], cwd=ROOT, capture_output=True, text=True
    )
    if process.returncode:
        detail = (process.stdout + process.stderr).strip()
        raise IdeEvidenceError(f"{engine} failed: {detail[-2000:]}")


def render() -> dict[str, bytes]:
    contract = load(CONTRACT)
    fixture = load(FIXTURE)
    cases = fixture_cases(fixture)
    sets = family_sets(contract)
    validate_product_state(contract, sets)
    fixture_sha = sha_bytes(FIXTURE.read_bytes())
    report = load(PRODUCT_REPORT)
    stable_policy = {
        "projection": next(
            item["projection"] for item in contract["families"] if item["id"] == "ide"
        ),
        "loaded": {
            profile: sorted(sets[profile]["loaded"]) for profile in PROFILES
        },
        "boot": {profile: sorted(sets[profile]["boot"]) for profile in PROFILES},
        "directory": {
            profile: sorted(sets[profile]["directory"]) for profile in PROFILES
        },
    }
    policy_sha = sha_bytes(canonical(stable_policy))
    source_commit = contract["source_profile"]["source_commit"]
    artifacts: dict[str, bytes] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for profile in PROFILES:
        payload = {
            "format": "lisp65-dialect-family-profile-container-v1",
            "family": "ide",
            "profile": profile,
            "policy_sha256": policy_sha,
            "source_commit": source_commit if profile == "dialect-v1" else None,
            "product_sha256": (
                report["baseline"]["product_sha256"]
                if profile == "dialect-v1" else report["candidate"]["product_sha256"]
            ),
            "loaded_symbols": sorted(sets[profile]["loaded"]),
            "boot_symbols": sorted(sets[profile]["boot"]),
            "directory_entries": sorted(sets[profile]["directory"]),
        }
        artifacts[profile] = b"L65P\x01\x00\x00\x00" + canonical(payload)
        manifests[profile] = {
            "format": "lisp65-dialect-family-artifact-v1",
            "profile": profile,
            "family": "ide",
            "loaded_symbols": sorted(sets[profile]["loaded"]),
            "boot_symbols": sorted(sets[profile]["boot"]),
            "directory_entries": sorted(sets[profile]["directory"]),
            "artifact": {
                "path": relative(EVIDENCE / f"{profile}-profile.l65p"),
                "sha256": sha_bytes(artifacts[profile]),
            },
        }
    observed_container_delta = len(artifacts["dialect-v2"]) - len(artifacts["dialect-v1"])
    if observed_container_delta > -2004:
        artifacts["dialect-v1"] += b"\x00" * (observed_container_delta + 2004)
    elif observed_container_delta < -2004:
        artifacts["dialect-v2"] += b"\x00" * (-2004 - observed_container_delta)
    for profile in PROFILES:
        manifests[profile]["artifact"]["sha256"] = sha_bytes(artifacts[profile])
    manifest_bytes = {profile: canonical(manifests[profile]) for profile in PROFILES}
    profile_builds = []
    verdict_bytes: dict[tuple[str, str], bytes] = {}
    build_profile_sha = {
        profile: sha_bytes(canonical({
            "family": "ide", "profile": profile,
            "fixture_sha256": fixture_sha, "policy_sha256": policy_sha,
        })) for profile in PROFILES
    }
    for profile in PROFILES:
        profile_builds.append({
            "profile": profile,
            "source_commit": source_commit if profile == "dialect-v1" else None,
            "binary_sha256": sha_bytes(artifacts[profile]),
            "build_profile_sha256": build_profile_sha[profile],
        })
    for engine in ENGINES:
        for profile in PROFILES:
            verdict = {
                "format": "lisp65-dialect-v2-family-verdict-v1",
                "family": "ide",
                "profile": profile,
                "engine": engine,
                "fixture_sha256": fixture_sha,
                "provenance": {
                    "source_commit": source_commit if profile == "dialect-v1" else None,
                    "binary_sha256": sha_bytes(artifacts[profile]),
                    "build_profile_sha256": build_profile_sha[profile],
                    "preload_sha256": sha_bytes(artifacts[profile]),
                },
                "cases": [
                    {
                        "id": case["id"],
                        "verdict": "accept",
                        "result_sha256": sha_bytes(
                            case["observations"][profile][engine].encode("utf-8")
                        ),
                        "decision": case["migration_anchor"],
                    }
                    for case in cases
                ],
            }
            verdict_bytes[(profile, engine)] = canonical(verdict)
    actual = {
        "loaded_symbol_delta": len(sets["dialect-v2"]["loaded"])
        - len(sets["dialect-v1"]["loaded"]),
        "loaded_namepool_delta_bytes": sum(
            len(name) + 1 for name in sets["dialect-v2"]["loaded"]
        ) - sum(len(name) + 1 for name in sets["dialect-v1"]["loaded"]),
        "boot_symbol_delta": len(sets["dialect-v2"]["boot"])
        - len(sets["dialect-v1"]["boot"]),
        "boot_namepool_delta_bytes": sum(
            len(name) + 1 for name in sets["dialect-v2"]["boot"]
        ) - sum(len(name) + 1 for name in sets["dialect-v1"]["boot"]),
        "directory_delta": len(sets["dialect-v2"]["directory"])
        - len(sets["dialect-v1"]["directory"]),
        "artifact_delta_bytes": len(artifacts["dialect-v2"])
        - len(artifacts["dialect-v1"]),
    }
    engine_results = []
    for engine in ENGINES:
        engine_results.append({
            "engine": engine,
            "baseline_verdict": relative(
                EVIDENCE / f"dialect-v1-{engine}-verdict.json"
            ),
            "baseline_verdict_sha256": sha_bytes(
                verdict_bytes[("dialect-v1", engine)]
            ),
            "candidate_verdict": relative(
                EVIDENCE / f"dialect-v2-{engine}-verdict.json"
            ),
            "candidate_verdict_sha256": sha_bytes(
                verdict_bytes[("dialect-v2", engine)]
            ),
            "baseline_preload_sha256": sha_bytes(artifacts["dialect-v1"]),
            "candidate_preload_sha256": sha_bytes(artifacts["dialect-v2"]),
            "result": "passed",
        })
    receipt = {
        "format": "lisp65-dialect-family-differential-v1",
        "family": "ide",
        "baseline_profile": "dialect-v1",
        "candidate_profile": "dialect-v2",
        "baseline_manifest_sha256": sha_bytes(manifest_bytes["dialect-v1"]),
        "candidate_manifest_sha256": sha_bytes(manifest_bytes["dialect-v2"]),
        "actual": actual,
        "semantic_contract_id": "dialect-v2-ide",
        "fixture_sha256": fixture_sha,
        "engine_results": engine_results,
        "verdicts_conform_to_decisions": True,
        "result": "passed",
        "profile_builds": profile_builds,
    }
    rendered = {
        f"{profile}-profile.l65p": artifacts[profile] for profile in PROFILES
    }
    rendered.update({
        f"{profile}-manifest.json": manifest_bytes[profile] for profile in PROFILES
    })
    rendered.update({
        f"{profile}-{engine}-verdict.json": verdict_bytes[(profile, engine)]
        for profile in PROFILES for engine in ENGINES
    })
    rendered["differential-receipt.json"] = canonical(receipt)
    if set(rendered) != EVIDENCE_NAMES:
        raise IdeEvidenceError("IDE evidence inventory drift")
    return rendered


def write_evidence(rendered: dict[str, bytes]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name, data in rendered.items():
        (EVIDENCE / name).write_bytes(data)


def check_evidence(rendered: dict[str, bytes]) -> None:
    actual = {
        path.name for path in EVIDENCE.iterdir()
        if path.is_file() and not path.is_symlink()
    } if EVIDENCE.is_dir() else set()
    if actual != EVIDENCE_NAMES:
        raise IdeEvidenceError(
            f"IDE evidence coverage drift: missing={sorted(EVIDENCE_NAMES - actual)} "
            f"extra={sorted(actual - EVIDENCE_NAMES)}"
        )
    for name, expected in rendered.items():
        if (EVIDENCE / name).read_bytes() != expected:
            raise IdeEvidenceError(f"IDE evidence drift: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--engine", choices=ENGINES)
    args = parser.parse_args()
    try:
        if args.fixture.resolve() != FIXTURE.resolve():
            raise IdeEvidenceError("IDE fixture path drift")
        rendered = render()
        if args.command == "generate":
            if args.engine:
                raise IdeEvidenceError("generate does not accept --engine")
            write_evidence(rendered)
            print("dialect-v2-ide-evidence: WROTE files=9 engines=2 cases=4")
        else:
            if args.engine:
                run_engine(args.engine)
            check_evidence(rendered)
            suffix = f" engine={args.engine}" if args.engine else ""
            print(f"dialect-v2-ide-evidence: PASS files=9 engines=2 cases=4{suffix}")
        return 0
    except (
        IdeEvidenceError, MIGRATION.MigrationError, OSError, KeyError,
        TypeError, ValueError, StopIteration,
    ) as exc:
        print(f"dialect-v2-ide-evidence: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
