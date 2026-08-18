#!/usr/bin/env python3
"""Isolated, content-bound replay of the accepted 1.11 locality result."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v111_compiler_locality as V111  # noqa: E402


CONTRACT = ROOT / "config/c2-v111-locality-replay-closure.json"
DRIVER = Path(__file__).resolve()
FIXTURE = ROOT / "tests/bytecode/dialect-v2/v111-locality-replay-inputs"
OUT = ROOT / "build/c2.3/v111-locality-replay-closure"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-v111-locality-replay-closure-receipt.json"
)
LIVE_SUITE = ROOT / (
    "build/bytecode/dialect-v2/suites/"
    "p0-stdlib-einsuite-core-workbench-subset.json"
)
FORMAT = "lisp65-c2.3-link94-v111-locality-replay-closure-v1"
PATH_FIELDS = (
    "blob", "c_source", "directory", "disasm", "disasm_sha256", "header", "suite",
    "sources", "resident_suites",
)


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ClosureError(f"path escaped repository: {path}") from error


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": relative(path), "bytes": len(raw), "sha256": sha(raw)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty(value))


def fixture_paths() -> list[Path]:
    resident = load(FIXTURE / "resident/suite.json")
    sources = resident.get("sources")
    require(isinstance(sources, list) and all(isinstance(x, str) for x in sources),
            "resident fixture source inventory absent")
    resident_prefix = "build/bytecode/dialect-v2/sources/"
    expected = {
        FIXTURE / "resident/suite.json",
        FIXTURE / "baseline-carrier/manifest.json",
        FIXTURE / "baseline-carrier/blob.bin",
        FIXTURE / "baseline-carrier/suite.json",
        FIXTURE / "accepted-candidate/manifest.json",
        FIXTURE / "accepted-candidate/blob.bin",
        FIXTURE / "accepted-candidate/suite.json",
    }
    for source in sources:
        require(source.startswith(resident_prefix),
                "resident fixture source escaped its historical root")
        expected.add(
            FIXTURE / "resident/sources" / source[len(resident_prefix):]
        )
    candidate = load(FIXTURE / "accepted-candidate/suite.json")
    candidate_sources = candidate.get("sources")
    candidate_prefix = (
        "build/post-promotion/v111/candidate/compiler-tier/"
        "c2-compiler-sources/"
    )
    require(isinstance(candidate_sources, list)
            and all(isinstance(x, str) for x in candidate_sources),
            "accepted candidate source inventory absent")
    for source in candidate_sources:
        require(source.startswith(candidate_prefix),
                "candidate fixture source escaped its historical root")
        expected.add(
            FIXTURE / "accepted-candidate/sources" /
            source[len(candidate_prefix):]
        )
    actual = {path for path in FIXTURE.rglob("*") if path.is_file()}
    require(actual == expected,
            "fixture contains a missing, extra, or unenumerated replay input")
    return sorted(expected, key=lambda path: relative(path))


def fixture_rows() -> list[dict[str, Any]]:
    rows = []
    for path in fixture_paths():
        raw = path.read_bytes()
        rows.append({
            "path": path.relative_to(FIXTURE).as_posix(),
            "bytes": len(raw),
            "sha256": sha(raw),
        })
    return rows


def audit_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    require(
        contract.get("format")
            == "lisp65-c2-v111-locality-replay-input-closure-v1"
        and contract.get("scope") == {
            "device_contacts": 0,
            "product_links": 0,
            "purpose": (
                "isolated historical 1.11 locality replay before the "
                "Link-94 replacement card"
            ),
            "resident_delta_bytes": 0,
        }
        and contract.get("live_shared_symbol_space", {}).get(
            "forbidden_as_input") is True,
        "replay closure contract broadened",
    )
    rows = fixture_rows()
    fixture = contract.get("fixture", {})
    require(
        fixture.get("root") == relative(FIXTURE)
        and fixture.get("files") == len(rows) == 28
        and fixture.get("bytes") == sum(row["bytes"] for row in rows)
        and fixture.get("tree_sha256") == sha(canonical(rows)),
        "replay fixture tree drift",
    )
    live_inputs = contract.get("immutable_live_inputs")
    require(isinstance(live_inputs, list) and len(live_inputs) == 11,
            "immutable live input inventory drift")
    for row in live_inputs:
        require(set(row) == {"path", "sha256"},
                "immutable input row schema drift")
        path = ROOT / row["path"]
        require(path.is_file() and sha(path.read_bytes()) == row["sha256"],
                f"immutable replay input drift: {row['path']}")
    accepted = contract["accepted_replay"]
    accepted_path = ROOT / accepted["receipt"]
    require(
        sha(accepted_path.read_bytes()) == accepted["receipt_sha256"]
        and stable_projection_sha(load(accepted_path))
            == accepted["stable_projection_sha256"],
        "accepted 1.11 replay authority drift",
    )
    return rows


def stable_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value[key])
        for key in sorted(value)
        if key not in {"authorities", "mutations_rejected"}
    }


def stable_projection_sha(value: dict[str, Any]) -> str:
    return sha(canonical(stable_projection(value)))


def normalized_manifest(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    for key in PATH_FIELDS:
        result.pop(key, None)
    directory = result.get("directory_only")
    require(isinstance(directory, dict), "candidate directory-only record absent")
    directory.pop("diagnostic_map", None)
    directory.pop("diagnostic_map_sha256", None)
    external = result.get("external_image")
    require(isinstance(external, dict), "candidate external-image record absent")
    external.pop("path", None)
    return result


def patch_resident_suite(out: Path) -> Path:
    value = load(FIXTURE / "resident/suite.json")
    prefix = "build/bytecode/dialect-v2/sources/"
    value["sources"] = [
        relative(FIXTURE / "resident/sources" / source[len(prefix):])
        for source in value["sources"]
    ]
    path = out / "resident/suite.json"
    write_json(path, value)
    return path


def patch_baseline(out: Path, resident_suite: Path) -> Path:
    suite = load(FIXTURE / "baseline-carrier/suite.json")
    suite["resident_suite"] = relative(resident_suite)
    suite.pop("resident_suites", None)
    suite_path = out / "baseline/suite.json"
    write_json(suite_path, suite)
    manifest = load(FIXTURE / "baseline-carrier/manifest.json")
    manifest["suite"] = relative(suite_path)
    manifest["blob"] = relative(FIXTURE / "baseline-carrier/blob.bin")
    manifest_path = out / "baseline/manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def isolated_build_carrier(
    contract: dict[str, Any], resident_suite: Path,
) -> dict[str, Any]:
    candidate = contract["candidate"]
    suite_path = ROOT / candidate["suite"]
    generation = V111.TIER.generate(suite_path)
    V111.write_json(ROOT / candidate["generation_receipt"], generation)
    suite_value = load(suite_path)
    suite_value["resident_suite"] = relative(resident_suite)
    suite_value.pop("resident_suites", None)
    write_json(suite_path, suite_value)

    accepted_suite = load(FIXTURE / "accepted-candidate/suite.json")
    historical_prefix = (
        "build/post-promotion/v111/candidate/compiler-tier/"
        "c2-compiler-sources/"
    )
    current_prefix = suite_path.parent / "c2-compiler-sources"
    for source in accepted_suite["sources"]:
        suffix = source[len(historical_prefix):]
        require(source.startswith(historical_prefix),
                "accepted candidate source escaped its root")
        expected = FIXTURE / "accepted-candidate/sources" / suffix
        observed = current_prefix / suffix
        require(bind(expected)["sha256"] == bind(observed)["sha256"],
                f"candidate generated source drift: {suffix}")

    suite = V111.STD._read_suite(str(suite_path))
    checked = V111.STD.check_suite(str(suite_path), suite)
    prefix = ROOT / candidate["artifact_prefix"]
    emitted = V111.STD.emit_artifacts(
        str(suite_path), suite, str(prefix), base_addr=0,
        artifact_role="disk-lib",
    )
    manifest_path = prefix.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    require(
        manifest["private_inline_functions"] == list(V111.TIER.PRIVATE_INLINE)
        and manifest["cost"]["private_inline_gate"] == {
            "expansions": 73,
            "functions": 10,
            "names": list(V111.TIER.PRIVATE_INLINE),
            "resident_functions": 0,
        },
        "isolated private-inline execution closure drift",
    )
    return {
        "suite_path": suite_path,
        "generation": generation,
        "checked": checked,
        "emit": emitted,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def isolated_build_defstruct(
    out: Path, resident_suite: Path,
) -> dict[str, Any]:
    candidate = load(V111.V110.CONTRACT)["candidate"]

    def patched(source: str, name: str) -> Path:
        value = load(ROOT / source)
        value["resident_suite"] = relative(resident_suite)
        value.pop("resident_suites", None)
        target = out / "defstruct" / name
        write_json(target, value)
        return target

    suite_path = patched(candidate["suite"], "suite.json")
    integration_path = patched(
        candidate["integration_suite"], "integration-suite.json")
    suite = V111.STD._read_suite(str(suite_path))
    integration = V111.STD._read_suite(str(integration_path))
    standalone = V111.STD.check_suite(str(suite_path), suite)
    integrated = V111.STD.check_suite(str(integration_path), integration)
    prefix = out / "defstruct/candidate"
    emitted = V111.STD.emit_artifacts(
        str(suite_path), suite, str(prefix), base_addr=0,
        artifact_role="disk-lib",
    )
    manifest_path = prefix.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    manifest_suite = Path(manifest["suite"])
    if not manifest_suite.is_absolute():
        manifest_suite = ROOT / manifest_suite
    require(
        manifest["artifact_role"] == "disk-lib"
        and manifest_suite.resolve() == suite_path.resolve(),
        "isolated defstruct candidate identity drift",
    )
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "standalone": standalone,
        "integration": integrated,
        "emit": emitted,
    }


def execute(out: Path) -> dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    resident_suite = patch_resident_suite(out)
    baseline_manifest = patch_baseline(out, resident_suite)
    contract = load(V111.CONTRACT)
    contract["baseline"]["carrier_manifest"] = relative(baseline_manifest)
    contract["candidate"].update({
        "suite": relative(out / "candidate/compiler-tier/suite.json"),
        "generation_receipt": relative(
            out / "candidate/compiler-tier/generation.json"),
        "artifact_prefix": relative(out / "candidate/carrier/lcc"),
    })
    contract_path = out / "contract.json"
    write_json(contract_path, contract)

    original_contract = V111.CONTRACT
    original_builder = V111.build_carrier
    original_carrier = V111.PHASE_A.HistoricalCarrier
    original_defstruct_builder = V111.V110.build_candidate
    try:
        V111.CONTRACT = contract_path
        V111.build_carrier = lambda value: isolated_build_carrier(
            value, resident_suite)
        V111.PHASE_A.HistoricalCarrier = V111.carrier_class(baseline_manifest)
        V111.V110.build_candidate = lambda _value: isolated_build_defstruct(
            out, resident_suite)
        result = V111.core_receipt()
    finally:
        V111.CONTRACT = original_contract
        V111.build_carrier = original_builder
        V111.PHASE_A.HistoricalCarrier = original_carrier
        V111.V110.build_candidate = original_defstruct_builder

    accepted = load(ROOT / load(CONTRACT)["accepted_replay"]["receipt"])
    stable = stable_projection_sha(result)
    require(stable == stable_projection_sha(accepted),
            "isolated replay changed the accepted 1.11 semantic projection")
    manifest_path = out / "candidate/carrier/lcc.manifest.json"
    manifest = load(manifest_path)
    normalized = sha(canonical(normalized_manifest(manifest)))
    expected = load(CONTRACT)["accepted_candidate"]
    require(
        normalized == expected["manifest_normalized_sha256"]
        and manifest["blob_sha256"] == expected["blob_sha256"]
        and manifest["cost"]["dependency_gate"]["known_targets"] == 388
        and len(manifest["entries"]) == 102
        and manifest["code_bytes"] == 8134,
        "isolated candidate content differs from accepted 1.11 carrier",
    )
    return {
        "stable_projection_sha256": stable,
        "candidate_manifest_normalized_sha256": normalized,
        "candidate_blob_sha256": manifest["blob_sha256"],
        "candidate_entries": len(manifest["entries"]),
        "candidate_code_bytes": manifest["code_bytes"],
        "candidate_known_targets": manifest["cost"]["dependency_gate"]
            ["known_targets"],
        "full_sequence_seconds": result["pricing"]["full_sequence"]
            ["candidate"]["operational_floor_seconds"],
        "post_require_seconds": result["pricing"]["post_require_definition"]
            ["candidate"]["operational_floor_seconds"],
        "product_links": 0,
        "device_contacts": 0,
        "resident_delta_bytes": 0,
        "artifacts": {
            "derived_resident_suite": bind(resident_suite),
            "derived_baseline_manifest": bind(baseline_manifest),
            "derived_candidate_suite": bind(
                out / "candidate/compiler-tier/suite.json"),
            "derived_candidate_manifest": bind(manifest_path),
        },
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    rows = audit_contract(contract)
    execution = execute(OUT)
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "passed-isolated-SHA-bound-v111-locality-replay-input-closure",
        "source": {
            "contract": bind(CONTRACT),
            "driver": bind(DRIVER),
            "accepted_replay": bind(
                ROOT / contract["accepted_replay"]["receipt"]),
        },
        "input_closure": {
            "fixture_root": relative(FIXTURE),
            "files": rows,
            "file_count": len(rows),
            "bytes": sum(row["bytes"] for row in rows),
            "tree_sha256": sha(canonical(rows)),
            "live_shared_symbol_space_is_an_input": False,
        },
        "execution": execution,
        "mutation_claim": {
            "live_symbol_space_noise_without_closure_content_change":
                "must-not-move-stable-projection-or-candidate-content",
            "proved_by_selftest": True,
        },
        "attempt_accounting": {
            "product_cards": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "claim_limit": (
            "Host-only producer input closure for the historical 1.11 replay. "
            "No Link-94 card, product, media, hardware, surface, trace, "
            "defstruct or release claim."
        ),
    }
    value["mutations_rejected"] = mutation_proof(value)
    validate(value, verify_inputs=True)
    return value


def validate(value: dict[str, Any], *, verify_inputs: bool) -> None:
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "passed-isolated-SHA-bound-v111-locality-replay-input-closure"
        and value.get("attempt_accounting") == {
            "product_cards": 0, "product_links": 0, "device_contacts": 0,
        }
        and value.get("input_closure", {}).get(
            "live_shared_symbol_space_is_an_input") is False
        and value.get("execution", {}).get("product_links") == 0
        and value.get("execution", {}).get("candidate_known_targets") == 388
        and value.get("execution", {}).get("candidate_entries") == 102
        and value.get("execution", {}).get("candidate_code_bytes") == 8134
        and value.get("execution", {}).get("full_sequence_seconds") == 677
        and value.get("execution", {}).get("post_require_seconds") == 179
        and value.get("mutation_claim", {}).get("proved_by_selftest") is True,
        "replay closure claim drift",
    )
    if verify_inputs:
        rows = audit_contract(load(CONTRACT))
        closure = value["input_closure"]
        require(
            closure["files"] == rows
            and closure["file_count"] == len(rows)
            and closure["bytes"] == sum(row["bytes"] for row in rows)
            and closure["tree_sha256"] == sha(canonical(rows)),
            "replay input closure receipt drift",
        )


def rejected(
    label: str, value: dict[str, Any], mutate: Callable[[dict[str, Any]], None],
    output: list[str],
) -> None:
    candidate = deepcopy(value)
    mutate(candidate)
    try:
        validate(candidate, verify_inputs=True)
    except ClosureError:
        output.append(label)
    else:
        raise ClosureError(f"replay closure mutation survived: {label}")


def mutation_proof(value: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for index, row in enumerate(value["input_closure"]["files"]):
        rejected(
            "input-content:" + row["path"], value,
            lambda x, at=index: x["input_closure"]["files"][at].update(
                sha256="0" * 64), output,
        )
    cases: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("missing-input", lambda x: x["input_closure"]["files"].pop()),
        ("live-symbol-input", lambda x: x["input_closure"].update(
            live_shared_symbol_space_is_an_input=True)),
        ("semantic-projection", lambda x: x["execution"].update(
            full_sequence_seconds=676)),
        ("candidate-content", lambda x: x["execution"].update(
            candidate_known_targets=391)),
        ("hide-product-link", lambda x: x["attempt_accounting"].update(
            product_links=1)),
    ]
    for label, mutate in cases:
        rejected(label, value, mutate, output)
    require(len(output) == 33, "replay closure mutation count drift")
    return output


def symbol_noise_selftest() -> None:
    require(LIVE_SUITE.is_file(), "live shared suite absent for noise mutation")
    before = LIVE_SUITE.read_bytes()
    first = execute(OUT.parent / "v111-locality-replay-selftest-a")
    try:
        noisy = json.loads(before.decode("utf-8"))
        functions = noisy.get("functions")
        require(isinstance(functions, list), "live suite function list absent")
        functions.append("%link94-live-symbol-space-noise")
        LIVE_SUITE.write_bytes(pretty(noisy))
        second = execute(OUT.parent / "v111-locality-replay-selftest-b")
    finally:
        LIVE_SUITE.write_bytes(before)
    stable_keys = {
        "stable_projection_sha256", "candidate_manifest_normalized_sha256",
        "candidate_blob_sha256", "candidate_entries", "candidate_code_bytes",
        "candidate_known_targets", "full_sequence_seconds",
        "post_require_seconds", "product_links", "device_contacts",
        "resident_delta_bytes",
    }
    require(
        {key: first[key] for key in stable_keys}
            == {key: second[key] for key in stable_keys},
        "live symbol-space noise moved the isolated replay closure",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            audit_contract(load(CONTRACT))
            symbol_noise_selftest()
            probe = derive()
            require(len(probe["mutations_rejected"]) == 33,
                    "replay closure selftest mutation drift")
            print(
                "v111 locality replay closure: SELFTEST PASS "
                "inputs=28 mutations=33 live-symbol-noise=immaterial"
            )
            return 0
        if args.action == "run":
            value = derive()
            RECEIPT.write_bytes(pretty(value))
        else:
            value = load(RECEIPT)
            validate(value, verify_inputs=True)
            current = derive()
            require(value == current, "replay closure receipt differs from execution")
        print(
            "v111 locality replay closure: PASS inputs=28 targets=388 "
            "objects=102 code=8134 full=677s post-require=179s"
        )
        return 0
    except (
        ClosureError, V111.LocalityError, V111.V110.PerformanceError,
        V111.PHASE_A.PhaseAError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"v111 locality replay closure: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
