#!/usr/bin/env python3
"""Run the authorized replacement continuation after resolving every input."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_root_padding_separate_target_continuation as BASE  # noqa: E402
import c2_v21_root_padding_separate_target_red_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TARGET = BASE.TARGET
WPLTO = BASE.WPLTO
FINAL = BASE.FINAL
PREFLIGHT_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-separate-target-replacement-preflight")
PREFLIGHT = PREFLIGHT_ROOT / "preflight.json"
LINK_RECEIPT = TARGET / "replacement-final-link.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-replacement-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-replacement-final-red.json")
AUTHORIZATION = "3c7bcc51"
FORMAT = "lisp65-c2.3-v2.1-root-padding-separate-target-replacement-v1"
MAP_CPU_FEATURE = "LISP65_C2_MAP_CPU_TRANSPORT"
RELEASE_CONTRACT = ROOT / "config/c2-v21-cpu-transport-release-contract.json"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, value = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("path repair and replacement run authorized",
                  "os.path.relpath(source", "reference-resolution smoke",
                  "a run is a producer experiment, not a path test",
                  "one replacement continuation run"):
        require(token in text, f"replacement authority absent: {token}")
    return value


def owned_target_skeleton() -> dict[str, Any]:
    require(TARGET.is_dir() and not TARGET.is_symlink(),
            "producer-owned target root absent")
    require(WPLTO.is_dir() and not WPLTO.is_symlink(),
            "producer-owned WPLTO target absent")
    entries = sorted(path.relative_to(TARGET).as_posix()
                     for path in TARGET.rglob("*") if path != WPLTO)
    require(entries == [], f"failed-run target is not an empty skeleton: {entries}")
    return {"path": TARGET.relative_to(ROOT).as_posix(),
            "owner": "same-continuation-producer",
            "predecessor_created": True, "entries_beyond_wplto": entries,
            "safe_for_replacement": True}


def input_paths(inputs: dict[str, Any]) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for name, value in sorted(inputs["seed"].items()):
        rows.append((f"seed:{name}", ROOT / value["path"]))
    rows.extend((f"compiler:{index:02d}", ROOT / value["path"])
                for index, value in enumerate(inputs["compiler_inputs"]))
    rows.extend((f"header:{index}", ROOT / value["path"])
                for index, value in enumerate(inputs["fixed_headers"]))
    rows.extend((f"full-map:{index}", ROOT / value["path"])
                for index, value in enumerate(inputs["full_map_linker"]))
    rows.extend([
        ("profile", ROOT / inputs["profile"]["path"]),
        ("linker", ROOT / inputs["linker"]["path"]),
        ("full-map-directory", BASE.SOURCE_WPLTO / "full-map-linker"),
        ("product-identity", ROOT / inputs["product_identity"]["path"]),
        ("candidate-static-header",
         ROOT / inputs["candidate_static_header"]["path"]),
        ("materialization-witness",
         BASE.PREVIOUS.STATE / "materialization-probe/resident-island-a.h"),
    ])
    labels = [label for label, _path in rows]
    require(len(labels) == len(set(labels)), "reference-smoke label collision")
    return rows


def reference_row(label: str, source: Path, *, start: Path = WPLTO) -> dict[str, Any]:
    require(source.exists(), f"referenced input absent: {label}: {source}")
    relative = os.path.relpath(source, start=start)
    resolved = (start / relative).resolve(strict=True)
    require(resolved == source.resolve(strict=True),
            f"reference does not resolve to source: {label}")
    return {"label": label, "source": source.relative_to(ROOT).as_posix(),
            "relative_reference": relative,
            "kind": "directory" if source.is_dir() else "regular-file",
            "exists": True, "resolution_exact": True}


def reference_smoke(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = [reference_row(label, source)
            for label, source in input_paths(inputs)]
    require(len(rows) == 83 and all(row["exists"] and row["resolution_exact"]
                                    for row in rows),
            "reference-resolution smoke cardinality/result drift")
    sibling = BASE.SOURCE_WPLTO / "c2-substitution.ld"
    try:
        sibling.relative_to(WPLTO)
    except ValueError:
        containment_API_rejected = True
    else:
        containment_API_rejected = False
    require(containment_API_rejected,
            "reference smoke lacks sibling-path regression witness")
    return {"status": "PASS: every input reference resolves before run",
            "algorithm": "os.path.relpath(source, start=target.parent)",
            "target_parent": WPLTO.relative_to(ROOT).as_posix(),
            "references": rows, "reference_count": len(rows),
            "sibling_containment_API_rejected": True,
            "filesystem_writes": 0}


def validate_smoke(value: dict[str, Any]) -> None:
    require(
        value.get("status") == "PASS: every input reference resolves before run"
        and value.get("algorithm") ==
            "os.path.relpath(source, start=target.parent)"
        and value.get("reference_count") == 83
        and len(value.get("references", [])) == 83
        and all(row.get("exists") is True
                and row.get("resolution_exact") is True
                for row in value["references"])
        and value.get("sibling_containment_API_rejected") is True
        and value.get("filesystem_writes") == 0,
        "reference-resolution smoke drift")


def smoke_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-containment-api": lambda x: x.update(
            algorithm="Path.relative_to(source-parent)"),
        "drop-reference": lambda x: x["references"].pop(),
        "missing-source": lambda x: x["references"][0].update(exists=False),
        "misresolve-source": lambda x: x["references"][1].update(
            resolution_exact=False),
        "hide-sibling-witness": lambda x: x.update(
            sibling_containment_API_rejected=False),
        "write-during-dry-run": lambda x: x.update(filesystem_writes=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_smoke(trial)
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "reference-smoke mutation survived")
    return rejected


def candidate_probe_definitions() -> tuple[str, ...]:
    contract = load(RELEASE_CONTRACT)
    required = contract["build"]["activation_defines"]
    require(MAP_CPU_FEATURE in required
            and "LISP65_C2_MUTABLE_CPU_READS" in PRODUCT.CONVERGENCE_DEFINES
            and MAP_CPU_FEATURE not in PRODUCT.CONVERGENCE_DEFINES,
            "candidate MAP-CPU opt-in authority drift")
    return (*PRODUCT.CONVERGENCE_DEFINES, MAP_CPU_FEATURE)


def exact_source_list(
        rows: list[dict[str, Any]],
        expected_definitions: tuple[str, ...]) -> Callable[..., list[str]]:
    paths = [str(ROOT / row["path"]) for row in rows]

    def selected(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        require(tuple(extra_definitions) == expected_definitions,
                "replacement link requested a compiler-input scope other than seed")
        return list(paths)

    return selected


def real_consumer_dry_run(inputs: dict[str, Any]) -> dict[str, Any]:
    old_config, _paths = BASE.PREVIOUS.configure_candidate()
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    try:
        probe_definitions = candidate_probe_definitions()
        PRODUCT.source_list = exact_source_list(
            inputs["compiler_inputs"], probe_definitions)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = BASE.SOURCE_MANIFEST
        artifacts = load(BASE.SOURCE_MANIFEST)
        selected = PRODUCT.source_list(probe_definitions)
        scope = PRODUCT.source_owner_scope_gate(
            PRODUCT.definitions(artifacts), probe_definitions,
            selected)
        require(len(selected) == 66
                and [(row["name"], row["selected"]) for row in scope["scopes"]]
                    == [("mapped-far-content-convergence", True),
                        ("map-cpu-library-read", True)],
                "real final-link source consumer dry-run drift")
        return {"status": "PASS: real final-link source consumer accepts closure",
                "compiler_inputs": len(selected),
                "probe_definitions": list(probe_definitions),
                "product_build_id_hex": artifacts["product_build_id_hex"],
                "source_owner_scopes": scope["scopes"]}
    finally:
        PRODUCT.source_list = old_source_list
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old_config)


def validate_preflight(value: dict[str, Any]) -> None:
    validate_smoke(value["reference_resolution_smoke"])
    require(
        value.get("format") == FORMAT
        and value.get("status") ==
            "PASS: relpath fix and all input references dry-run green"
        and value["target"]["safe_for_replacement"] is True
        and value["source_evidence"]["mode"] == "0555"
        and len(value["inputs"]["seed"]) == 4
        and len(value["inputs"]["compiler_inputs"]) == 66
        and value["real_consumer_dry_run"]["compiler_inputs"] == 66
        and value["execution_lock"] == {"replacement_runs": 0,
            "materializations": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "replacement continuation preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "foreign-target": lambda x: x["target"].update(
            safe_for_replacement=False),
        "drop-input": lambda x: x["inputs"]["compiler_inputs"].pop(),
        "invent-run": lambda x: x["execution_lock"].update(replacement_runs=1),
        "skip-real-consumer": lambda x: x["real_consumer_dry_run"].update(
            compiler_inputs=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_preflight(trial)
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    target = owned_target_skeleton()
    inputs = BASE.reference_inputs()
    smoke = reference_smoke(inputs)
    validate_smoke(smoke)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17",
        "status": "PASS: relpath fix and all input references dry-run green",
        "authority": {"owner": authorization(), "Final_Red": bind(BASE.FINAL_RED),
            "red_attribution": bind(ATTR.RECEIPT), "driver": bind(Path(__file__))},
        "target": target, "source_evidence": BASE.immutable_tree(),
        "inputs": inputs, "reference_resolution_smoke": smoke,
        "reference_smoke_mutations_rejected": smoke_mutations(smoke),
        "real_consumer_dry_run": real_consumer_dry_run(inputs),
        "execution_lock": {"replacement_runs": 0, "materializations": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Dry-run only: reference resolution and real source consumer. No "
            "target write, materialization, link, Completion, medium or device."),
    }
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    return value


def record_preflight() -> None:
    require(not PREFLIGHT_ROOT.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "replacement continuation is one-shot")
    value = preflight_value()
    PREFLIGHT_ROOT.mkdir()
    PREFLIGHT.write_bytes(canonical(value))
    print("separate-target replacement: PREFLIGHT PASS refs=83 inputs=66 writes=0")


def consume_preflight() -> dict[str, Any]:
    value = load(PREFLIGHT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value)
            and value["authority"]["driver"] == bind(Path(__file__)),
            "replacement preflight receipt/driver drift")
    return value


def link_reference(path: Path, source: Path) -> None:
    require(source.exists() and not path.exists(), f"input reference collision: {path}")
    relative = os.path.relpath(source, start=path.parent)
    require((path.parent / relative).resolve(strict=True) == source.resolve(strict=True),
            f"input reference dry-run mismatch: {path}")
    path.symlink_to(relative, target_is_directory=source.is_dir())
    require(path.resolve(strict=True) == source.resolve(strict=True),
            f"input reference misbound: {path}")


def materialize(header: Path) -> None:
    PRODUCT.tool(
        "resident_island.py", "materialize", "--elf", str(BASE.SEED) + ".elf",
        "--nm", str(PRODUCT.TOOLCHAIN / "llvm-nm"),
        "--objcopy", str(PRODUCT.TOOLCHAIN / "llvm-objcopy"),
        "--abi-contract", str(BASE.PROFILE), "--header", str(header))


def run_link() -> None:
    preflight = consume_preflight()
    owned_target_skeleton()
    smoke_now = reference_smoke(preflight["inputs"])
    require(smoke_now == preflight["reference_resolution_smoke"],
            "reference smoke changed between dry-run and real run")
    source_before = BASE.immutable_tree()
    inputs_before = BASE.reference_inputs()
    link_reference(WPLTO / "c2-substitution.ld",
                   BASE.SOURCE_WPLTO / "c2-substitution.ld")
    link_reference(WPLTO / "full-map-linker",
                   BASE.SOURCE_WPLTO / "full-map-linker")
    header = WPLTO / "resident-island.h"
    materialize(header)
    witness = bind(BASE.PREVIOUS.STATE /
                   "materialization-probe/resident-island-a.h")
    require(bind(header)["sha256"] == witness["sha256"],
            "replacement materialization differs from bound witnesses")

    old_config, _paths = BASE.PREVIOUS.configure_candidate()
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    try:
        probe_definitions = candidate_probe_definitions()
        PRODUCT.source_list = exact_source_list(
            inputs_before["compiler_inputs"], probe_definitions)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = BASE.SOURCE_MANIFEST
        artifacts = load(BASE.SOURCE_MANIFEST)
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [BASE.SOURCE_WPLTO / "stage-config.h",
             BASE.SOURCE_WPLTO / "runtime-overlay.prepare.h", header,
             BASE.SOURCE_WPLTO / "error-text-table.h",
             BASE.SOURCE_WPLTO / "c2-kernal-window.generated.h"],
            artifacts, probe_definitions=probe_definitions)
    finally:
        PRODUCT.source_list = old_source_list
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old_config)

    source_after = BASE.immutable_tree()
    inputs_after = BASE.reference_inputs()
    require(source_after == source_before and inputs_after == inputs_before,
            "replacement changed immutable referenced evidence")
    require(not any((WPLTO / path.name).exists() for path in BASE.family(BASE.SEED)),
            "immutable seed was copied into replacement target")
    finals = BASE.bound_family(FINAL)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17",
        "status": "PASS: replacement materialized and final product linked",
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__))},
        "target": preflight["target"],
        "reference_resolution_smoke": smoke_now,
        "source_evidence_before": source_before,
        "source_evidence_after": source_after,
        "inputs_before": inputs_before, "inputs_after": inputs_after,
        "seed_consumption": {"mode": "direct-read-only-reference",
            "copied_into_target": False, "family": BASE.seed_family()},
        "materialization": {"runs": 1, "header": bind(header),
            "equals_prior_determinism_witness": True, "witness": witness},
        "final_artifacts": finals,
        "compiler_input_consumption": bind(
            Path(str(FINAL) + ".compiler-input-consumption.json")),
        "candidate_derived_inventory": bind(
            WPLTO / f"final-section-inventory-{FINAL.name}.json"),
        "LTO_metadata": bind(
            WPLTO / f"lto-partition-metadata-{FINAL.name}.json"),
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0, "materializations": 1,
            "final_product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "same acceptance authorities over the four final artifacts",
        "claim_limit": (
            "Replacement materialization and final link only. Acceptance, "
            "Completion, media and device actions have not run."),
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    print("separate-target replacement: LINK PASS refs=83 final=4 WPLTO=0 link=1")


def record_final_red(error: Exception) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    finals = {path.name: bind(path) for path in BASE.family(FINAL)
              if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-separate-target-replacement-red-v1",
        "recorded_on": "2026-08-17",
        "status": "FINAL RED: SEPARATE-TARGET REPLACEMENT RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT) if PREFLIGHT.exists() else None,
            "driver": bind(Path(__file__))},
        "source_evidence": BASE.immutable_tree(), "seed": BASE.seed_family(),
        "final_artifacts": finals, "retry_authorized": False,
        "owner_disposition_required": True,
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0,
            "final_product_links": 1 if finals else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Terminal replacement Red; no automatic retry.",
    }))


def check() -> None:
    value = load(RECEIPT if RECEIPT.exists() else LINK_RECEIPT)
    require(value["final_artifacts"] == BASE.bound_family(FINAL),
            "separate-target replacement artifact drift")
    print("separate-target replacement: CHECK PASS final=4 WPLTO=0 link=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "link", "check"))
    action = parser.parse_args().action
    try:
        {"preflight": record_preflight, "link": run_link,
         "check": check}[action]()
    except Exception as error:
        if action == "link":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"separate-target replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
