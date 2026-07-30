#!/usr/bin/env python3
"""Prove the one-decoder rule from the final C2-lite ELF and artifacts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-linked-format-decoder-closure.json"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DEFAULT_RECEIPT = ROOT / (
    "build/c2.2/v1.2.4-candidate-product-link81/receipts/"
    "linked-format-decoder-closure.json")
CURRENT_CANDIDATE_ROOT = "build/c2.2/v1.2.4-candidate-product-link81"


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ClosureError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def artifact_roles(manifest: dict[str, Any]) -> dict[str, Path]:
    rows = manifest.get("artifacts")
    require(isinstance(rows, list), "candidate artifact inventory missing")
    result: dict[str, Path] = {}
    for row in rows:
        require(isinstance(row, dict), "candidate artifact row malformed")
        role = str(row.get("role", ""))
        path = ROOT / str(row.get("path", ""))
        require(role and role not in result, f"duplicate artifact role: {role}")
        require(
            path.is_file() and path.stat().st_size == row.get("bytes")
            and sha(path) == row.get("sha256"),
            f"candidate artifact binding drift: {role}")
        result[role] = path
    return result


def header_version(path: Path, magic: bytes) -> int:
    data = path.read_bytes()
    require(
        len(data) >= 5 and data[:4] == magic,
        f"{path.relative_to(ROOT)} does not begin with {magic!r}")
    return data[4]


def feature_defines(path: Path) -> set[str]:
    rows = [
        line.split("=", 1)[1]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("feature_defines=")
    ]
    require(len(rows) == 1, "resolved profile has no unique feature_defines")
    return {item for item in rows[0].split(",") if item}


def validate_model(model: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_versions = contract["current_versions"]
    require(
        model["versions"] == expected_versions,
        f"linked format version set drift: {model['versions']}")
    require(
        model["c2i_count"] == contract["c2i_count"],
        f"C2I image count drift: {model['c2i_count']}")
    require(
        model["selected_runtime_formats"]
        == [contract["runtime_overlay_profile_define"]],
        "runtime-overlay profile selects zero or multiple decoders")
    require(
        not model["missing_required_profile_defines"],
        "required product profile define absent: "
        + ",".join(model["missing_required_profile_defines"]))
    require(
        all(count == 1 for count in model["phase_symbol_counts"].values()),
        "linked C2 phase symbol is missing or duplicated")
    require(
        all(count == 1 for count in model["phase_section_counts"].values()),
        "linked C2 phase section is missing or duplicated")
    require(
        all(count == 1 for count in model["runtime_verifier_counts"].values()),
        "linked L65R verifier is missing or duplicated")
    require(
        not model["runtime_verifier_section_mismatches"],
        "linked L65R verifier section drift")
    require(
        not model["forbidden_linked_identities"],
        "retired decoder identity entered final ELF: "
        + ",".join(model["forbidden_linked_identities"]))
    require(
        not model["missing_strict_source_markers"],
        "strict decoder source guard absent: "
        + ",".join(model["missing_strict_source_markers"]))


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("format")
            == "lisp65-c2-linked-format-decoder-closure-v1"
        and contract.get("version") == 1,
        "linked format decoder contract envelope drift")
    require(
        contract.get("candidate_manifest")
            == f"{CURRENT_CANDIDATE_ROOT}/canonical-product-manifest.json"
        and contract.get("c2i_glob")
            == (
                f"{CURRENT_CANDIDATE_ROOT}/static-plane/"
                "narrow-static/product/*.c2i.bin"
            ),
        "linked format decoder candidate authority is not Link 81")


def synthetic_model(contract: dict[str, Any]) -> dict[str, Any]:
    suffixes = contract["phase_suffixes"]
    verifiers = contract["runtime_verifiers"]
    return {
        "versions": deepcopy(contract["current_versions"]),
        "c2i_count": contract["c2i_count"],
        "selected_runtime_formats": [
            contract["runtime_overlay_profile_define"]],
        "missing_required_profile_defines": [],
        "phase_symbol_counts": {suffix: 1 for suffix in suffixes},
        "phase_section_counts": {suffix: 1 for suffix in suffixes},
        "runtime_verifier_counts": {name: 1 for name in verifiers},
        "runtime_verifier_section_mismatches": [],
        "forbidden_linked_identities": [],
        "missing_strict_source_markers": [],
    }


def selftest(contract: dict[str, Any]) -> None:
    validate_contract(contract)
    baseline = synthetic_model(contract)
    validate_model(baseline, contract)
    mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        ("L65S-v3", lambda item: item["versions"].update(L65S=3)),
        ("C2I-v1", lambda item: item["versions"].update(C2I=1)),
        ("C2D-v5", lambda item: item["versions"].update(C2D=5)),
        ("L65R-v3", lambda item: item["versions"].update(L65R=3)),
        ("phase-missing", lambda item:
            item["phase_symbol_counts"].update({"06a": 0})),
        ("phase-duplicated", lambda item:
            item["phase_section_counts"].update({"04": 2})),
        ("retired-section-linked", lambda item:
            item["forbidden_linked_identities"].append(
                ".lisp65_rt_l65s_decode")),
        ("dual-runtime-decoder", lambda item:
            item["selected_runtime_formats"].append(
                "LISP65_RUNTIME_OVERLAY_FORMAT_V3")),
    )
    for label, mutate in mutations:
        candidate = deepcopy(baseline)
        mutate(candidate)
        try:
            validate_model(candidate, contract)
        except ClosureError:
            continue
        raise ClosureError(f"selftest mutation survived: {label}")
    contract_mutations = (
        ("stale-manifest-link", "candidate_manifest",
         "build/c2.2/v1.2.3-candidate-product-link80/"
         "canonical-product-manifest.json"),
        ("stale-c2i-link", "c2i_glob",
         "build/c2.2/v1.2.3-candidate-product-link80/"
         "static-plane/narrow-static/product/*.c2i.bin"),
    )
    for label, field, value in contract_mutations:
        candidate = deepcopy(contract)
        candidate[field] = value
        try:
            validate_contract(candidate)
        except ClosureError:
            continue
        raise ClosureError(f"selftest mutation survived: {label}")
    require(
        len(mutations) + len(contract_mutations) == contract["mutation_count"],
        "contract mutation count drift")
    print(
        "c2-linked-format-decoder-closure: SELFTEST PASS "
        f"mutations={len(mutations) + len(contract_mutations)}")


def collect(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = ROOT / contract["candidate_manifest"]
    manifest = load(manifest_path, "candidate product manifest")
    roles = artifact_roles(manifest)
    required_roles = {
        "linked-product-elf", "resolved-profile", "c2-product-shelf",
        "c2d-v6-code-plane", "c2-session-family-region-0",
        "c2-boot-family",
    }
    require(
        required_roles <= roles.keys(),
        "candidate product lacks a format-bearing role")

    c2i_paths = sorted(ROOT.glob(contract["c2i_glob"]))
    versions = {
        "L65S": header_version(roles["c2-product-shelf"], b"L65S"),
        "C2I": -1,
        "C2D": header_version(roles["c2d-v6-code-plane"], b"C2D\x00"),
        "L65R": header_version(
            roles["c2-session-family-region-0"], b"L65R"),
    }
    c2i_versions = {
        header_version(path, b"C2I\x00")
        for path in c2i_paths
    }
    if len(c2i_versions) == 1:
        versions["C2I"] = next(iter(c2i_versions))
    boot_l65r = header_version(roles["c2-boot-family"], b"L65R")
    require(
        boot_l65r == versions["L65R"],
        "boot and session L65R versions diverge")

    profile_path = roles["resolved-profile"]
    defines = feature_defines(profile_path)
    runtime_defines = {
        contract["runtime_overlay_profile_define"],
        *contract["forbidden_runtime_overlay_profile_defines"],
    }
    selected_runtime = sorted(defines & runtime_defines)
    missing_profile = sorted(
        set(contract["required_product_profile_defines"]) - defines)

    elf_path = roles["linked-product-elf"]
    truth = ElfTruth.read(elf_path, llvm_readobj=LLVM_READOBJ)
    suffixes = contract["phase_suffixes"]
    phase_symbols = {
        suffix: len(truth.symbols_by_name.get(
            f"c2_stream_phase_{suffix}", []))
        for suffix in suffixes
    }
    phase_sections = {
        suffix: len(truth.sections_by_name.get(
            f".lisp65_rt_c2d_{suffix}", []))
        for suffix in suffixes
    }
    verifier_counts: dict[str, int] = {}
    verifier_mismatches: list[str] = []
    for name, section in contract["runtime_verifiers"].items():
        matches = truth.symbols_by_name.get(name, [])
        verifier_counts[name] = len(matches)
        if len(matches) == 1 and matches[0].section != section:
            verifier_mismatches.append(name)

    forbidden: list[str] = []
    for section in truth.sections:
        if any(section.name.startswith(prefix) for prefix in
               contract["forbidden_linked_section_prefixes"]):
            forbidden.append(section.name)
    for symbol in truth.symbols:
        if symbol.name in contract["forbidden_linked_symbols"] or any(
                symbol.name.startswith(prefix) for prefix in
                contract["forbidden_linked_symbol_prefixes"]):
            forbidden.append(symbol.name)

    decoder_source = (
        elf_path.parent / "generated-product-sources/c2-stream-decoder.c")
    runtime_source = ROOT / "src/vm_runtime_overlay.c"
    source_text = {
        "generated_decoder": decoder_source.read_text(encoding="utf-8"),
        "runtime_overlay_decoder": runtime_source.read_text(encoding="utf-8"),
    }
    missing_markers = [
        f"{owner}:{marker}"
        for owner, markers in contract["strict_source_markers"].items()
        for marker in markers if marker not in source_text[owner]
    ]

    model = {
        "versions": versions,
        "c2i_count": len(c2i_paths),
        "selected_runtime_formats": selected_runtime,
        "missing_required_profile_defines": missing_profile,
        "phase_symbol_counts": phase_symbols,
        "phase_section_counts": phase_sections,
        "runtime_verifier_counts": verifier_counts,
        "runtime_verifier_section_mismatches": verifier_mismatches,
        "forbidden_linked_identities": sorted(set(forbidden)),
        "missing_strict_source_markers": missing_markers,
    }
    evidence = {
        "candidate_manifest": binding(manifest_path),
        "linked_elf": binding(elf_path),
        "resolved_profile": binding(profile_path),
        "format_artifacts": {
            "L65S": binding(roles["c2-product-shelf"]),
            "C2D": binding(roles["c2d-v6-code-plane"]),
            "L65R_session": binding(
                roles["c2-session-family-region-0"]),
            "L65R_boot": binding(roles["c2-boot-family"]),
            "C2I": [binding(path) for path in c2i_paths],
        },
        "decoder_sources": {
            "generated": binding(decoder_source),
            "runtime_overlay": binding(runtime_source),
        },
    }
    return model, evidence


def check(contract: dict[str, Any], output: Path) -> dict[str, Any]:
    model, evidence = collect(contract)
    validate_model(model, contract)
    value = {
        "format": "lisp65-c2-linked-format-decoder-closure-receipt-v1",
        "version": 1,
        "status": "passed",
        "claim": contract["claim"],
        "current_versions": model["versions"],
        "linked_decoder_inventory": {
            "phase_symbols": model["phase_symbol_counts"],
            "phase_sections": model["phase_section_counts"],
            "runtime_verifiers": model["runtime_verifier_counts"],
            "retired_linked_identities": model[
                "forbidden_linked_identities"],
        },
        "structurally_excluded": contract[
            "retired_formats_structurally_excluded"],
        "profile_selection": {
            "runtime_overlay": model["selected_runtime_formats"],
            "missing_required": model["missing_required_profile_defines"],
        },
        "mutation_count": contract["mutation_count"],
        "evidence": evidence,
        "claim_limit": contract["claim_limit"],
        "result":
            "one-strict-decoder-per-format-in-final-linked-product",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        contract = load(CONTRACT, "linked format decoder contract")
        validate_contract(contract)
        if args.selftest:
            selftest(contract)
        else:
            output = args.output
            if not output.is_absolute():
                output = ROOT / output
            value = check(contract, output)
            print(
                "c2-linked-format-decoder-closure: PASS "
                f"formats={value['current_versions']} "
                f"phases={len(value['linked_decoder_inventory']['phase_symbols'])} "
                f"retired={len(value['structurally_excluded'])} "
                f"receipt={output.relative_to(ROOT)}")
        return 0
    except (
        ClosureError, OSError, KeyError, ValueError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-linked-format-decoder-closure: FIRST RED: " + str(error),
            file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
