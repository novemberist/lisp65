#!/usr/bin/env python3
"""Run the unused replacement with profile-derived compiler features."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_root_padding_compiler_consumption_replacement as PREVIOUS  # noqa: E402
import c2_v21_root_padding_compiler_consumption_preflight_red as RED  # noqa: E402


BASE = PREVIOUS.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TARGET = PREVIOUS.TARGET
WPLTO = PREVIOUS.WPLTO
FINAL = PREVIOUS.FINAL
OBJECT_ROOT = WPLTO / (
    ".canonical-objects-" + FINAL.stem + "-profile-consumed")
PREFLIGHT_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-profile-consumption-preflight")
PREFLIGHT = PREFLIGHT_ROOT / "preflight.json"
LINK_RECEIPT = TARGET / "profile-consumption-final-link.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-profile-consumption-replacement-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-profile-consumption-replacement-final-red.json")
AUTHORIZATION = "51900c92"
FORMAT = "lisp65-c2.3-v2.1-profile-consumption-replacement-v1"
STATUS = "PASS: 24/24 profile features consumed and final product linked"


class ProfileConsumptionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProfileConsumptionError(message)


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
    for token in ("profile-feature derivation authorized",
                  "resolved-profile.txt", "additive", "24/24 feature",
                  "still-unspent replacement run"):
        require(token in text, f"profile-consumption authority absent: {token}")
    return value


def feature_projection() -> dict[str, Any]:
    profile = tuple(RED.profile_features())
    prior = load(PREVIOUS.PREVIOUS.PREFLIGHT)
    candidate = tuple(prior["real_consumer_dry_run"]["probe_definitions"])
    combined = tuple(dict.fromkeys((*profile, *candidate)))
    require(len(profile) == 24 and len(candidate) == 6
            and len(combined) == 30
            and combined[:24] == profile and combined[24:] == candidate
            and not set(profile).intersection(candidate)
            and PRODUCT.scoped_probe_definitions(combined) == combined,
            "profile/candidate additive feature projection drift")
    return {"bound_profile_features": list(profile),
            "bound_profile_feature_count": len(profile),
            "candidate_scope_features": list(candidate),
            "candidate_scope_feature_count": len(candidate),
            "combined_compiler_features": list(combined),
            "combined_compiler_feature_count": len(combined),
            "operation": "ordered-additive-union",
            "profile_replaced_by_candidate": False}


def validate_projection(value: dict[str, Any]) -> None:
    require(value["bound_profile_feature_count"] == 24
            and len(value["bound_profile_features"]) == 24
            and value["candidate_scope_feature_count"] == 6
            and len(value["candidate_scope_features"]) == 6
            and value["combined_compiler_feature_count"] == 30
            and value["combined_compiler_features"] == [
                *value["bound_profile_features"],
                *value["candidate_scope_features"]]
            and value["operation"] == "ordered-additive-union"
            and value["profile_replaced_by_candidate"] is False,
            "additive feature projection invalid")


def projection_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "replace-profile": lambda x: x.update(
            combined_compiler_features=list(x["candidate_scope_features"]),
            combined_compiler_feature_count=6,
            profile_replaced_by_candidate=True),
        "drop-profile-feature": lambda x: x[
            "combined_compiler_features"].pop(0),
        "drop-candidate-feature": lambda x: x[
            "combined_compiler_features"].pop(),
        "wrong-operation": lambda x: x.update(operation="replacement"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_projection(trial)
        except ProfileConsumptionError:
            rejected.append(name)
    require(rejected == list(cases), "feature projection mutation survived")
    return rejected


def exact_preprocessor_prefix(combined: tuple[str, ...]) -> list[str]:
    prefix = PREVIOUS.preprocessor_command_prefix()
    prior = load(PREVIOUS.PREVIOUS.PREFLIGHT)
    candidate = tuple(prior["real_consumer_dry_run"]["probe_definitions"])
    tokens = [f"-D{name}" for name in candidate]
    positions = [index for index, item in enumerate(prefix) if item in tokens]
    require(len(positions) == len(tokens)
            and [prefix[index] for index in positions] == tokens,
            "prior candidate feature command boundary drift")
    insert_at = positions[0]
    stripped = [item for item in prefix if item not in tokens]
    return [*stripped[:insert_at], *(f"-D{name}" for name in combined),
            *stripped[insert_at:]]


def real_preprocessor_smoke(projection: dict[str, Any]) -> dict[str, Any]:
    combined = tuple(projection["combined_compiler_features"])
    prefix = exact_preprocessor_prefix(combined)
    inputs = BASE.reference_inputs()["compiler_inputs"]
    require(len(inputs) == 66, "real-preprocessor input closure drift")
    rows: list[dict[str, Any]] = []
    before = PREVIOUS.partial_prefix()
    for index, item in enumerate(inputs):
        source = item["path"]
        flags = ([prefix[0], "-Qunused-arguments", *prefix[1:]]
                 if Path(source).suffix == ".s" else list(prefix))
        completed = subprocess.run(
            [*flags, "-E", source, "-o", "/dev/null"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, check=False)
        require(completed.returncode == 0,
                f"profile-derived preprocessor red: {source}: {completed.stderr}")
        rows.append({"ordinal": index, "source": bind(ROOT / source),
            "language": "assembler" if source.endswith(".s") else "c",
            "exit_status": 0,
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode()).hexdigest()})
    require(PREVIOUS.partial_prefix() == before,
            "real preprocessor changed historical partial objects")
    return {"status": "PASS: profile-derived real consumers 66/66",
            "translation_units": rows, "translation_unit_count": len(rows),
            "profile_features_consumed": 24,
            "candidate_features_consumed": 6,
            "combined_features_consumed": 30,
            "output": "/dev/null", "filesystem_writes": 0}


def compiler_feature_gate_selftest(
        projection: dict[str, Any]) -> dict[str, Any]:
    features = tuple(projection["bound_profile_features"])
    combined = tuple(projection["combined_compiler_features"])
    old = PRODUCT.configure_compiler_consumed_feature_profile(
        BASE.PROFILE, bind(BASE.PROFILE), features)
    try:
        target = WPLTO / "feature-consumption-dry-run.prg"
        flags = [f"-D{name}" for name in combined]
        report = PRODUCT.compiler_consumed_feature_profile_gate(flags, target)
        require(report is not None
                and report["consumed_feature_count"] == 24,
                "24/24 compiler feature gate did not pass")
        rejected: list[str] = []
        mutations = {
            "drop-bound-feature": flags[1:],
            "candidate-replaces-profile": [
                f"-D{name}" for name in
                projection["candidate_scope_features"]],
            "duplicate-bound-feature": [*flags, flags[0]],
        }
        for name, mutant in mutations.items():
            try:
                PRODUCT.compiler_consumed_feature_profile_gate(mutant, target)
            except RuntimeError:
                rejected.append(name)
        require(rejected == list(mutations),
                "compiler feature-consumption mutation survived")
        return {"report": report, "mutations_rejected": rejected}
    finally:
        PRODUCT.restore_compiler_consumed_feature_profile(old)


def target_state() -> dict[str, Any]:
    prior = PREVIOUS.target_state()
    require(not OBJECT_ROOT.exists(),
            "profile-consumed object directory pre-exists")
    return {**prior,
            "historical_partial_objects_reused": False,
            "historical_partial_objects_preserved": True,
            "profile_consumed_object_directory":
                OBJECT_ROOT.relative_to(ROOT).as_posix(),
            "profile_consumed_object_directory_absent": True}


def validate_preflight(value: dict[str, Any]) -> None:
    projection = value["feature_projection"]
    smoke = value["real_preprocessor_smoke"]
    validate_projection(projection)
    require(value.get("format") == FORMAT
            and value.get("status") ==
                "PASS: profile-derived 24/24 real-consumer preflight"
            and value["target"]["historical_partial_objects_reused"] is False
            and value["target"]["historical_partial_objects_preserved"] is True
            and value["target"][
                "profile_consumed_object_directory_absent"] is True
            and len(value["header_references"]) == 2
            and smoke["translation_unit_count"] == 66
            and smoke["profile_features_consumed"] == 24
            and smoke["candidate_features_consumed"] == 6
            and smoke["combined_features_consumed"] == 30
            and len(smoke["translation_units"]) == 66
            and all(row["exit_status"] == 0
                    for row in smoke["translation_units"])
            and smoke["filesystem_writes"] == 0
            and value["compiler_feature_gate"]["report"][
                "consumed_feature_count"] == 24
            and len(value["compiler_feature_gate"][
                "mutations_rejected"]) == 3
            and value["execution_lock"] == {"replacement_runs": 0,
                "new_WPLTO_card_runs": 0, "compiled_objects": 0,
                "final_product_links": 0, "completion_runs": 0,
                "media_builds": 0, "device_contacts": 0},
            "profile-consumption preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "reuse-old-object": lambda x: x["target"].update(
            historical_partial_objects_reused=True),
        "drop-TU": lambda x: x["real_preprocessor_smoke"][
            "translation_units"].pop(),
        "miss-profile-feature": lambda x: x["real_preprocessor_smoke"].update(
            profile_features_consumed=23),
        "skip-feature-gate": lambda x: x["compiler_feature_gate"][
            "report"].update(consumed_feature_count=0),
        "invent-run": lambda x: x["execution_lock"].update(replacement_runs=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_preflight(trial)
        except ProfileConsumptionError:
            rejected.append(name)
    require(rejected == list(cases), "profile preflight mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    projection = feature_projection()
    validate_projection(projection)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17",
        "status": "PASS: profile-derived 24/24 real-consumer preflight",
        "authority": {"owner": authorization(),
            "preflight_Final_Red": bind(RED.RECEIPT),
            "prior_driver": bind(ROOT /
                "tools/host-lisp/c2_v21_root_padding_compiler_consumption_replacement.py"),
            "driver": bind(Path(__file__)),
            "producer": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py")},
        "source_evidence": BASE.immutable_tree(),
        "bound_profile": bind(BASE.PROFILE),
        "inputs": BASE.reference_inputs(),
        "target": target_state(),
        "header_references": PREVIOUS.header_references(),
        "feature_projection": projection,
        "feature_projection_mutations_rejected": projection_mutations(projection),
        "real_preprocessor_smoke": real_preprocessor_smoke(projection),
        "compiler_feature_gate": compiler_feature_gate_selftest(projection),
        "execution_lock": {"replacement_runs": 0,
            "new_WPLTO_card_runs": 0, "compiled_objects": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Profile projection and real-consumer preflight only. No compile, "
            "final link, Completion, medium or device action.")}
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    return value


def record_preflight() -> None:
    require(not PREFLIGHT_ROOT.exists() and not LINK_RECEIPT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "profile-consumption replacement is one-shot")
    value = preflight_value()
    PREFLIGHT_ROOT.mkdir()
    PREFLIGHT.write_bytes(canonical(value))
    print("profile-consumption replacement: PREFLIGHT PASS profile=24/24 "
          "candidate=6 preprocess=66 objects=0 run=0")


def consume_preflight() -> dict[str, Any]:
    value = load(PREFLIGHT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value)
            and value["authority"]["driver"] == bind(Path(__file__))
            and value["authority"]["producer"] == bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py")
            and value["source_evidence"] == BASE.immutable_tree()
            and value["header_references"] == PREVIOUS.header_references()
            and value["target"] == target_state(),
            "profile-consumption preflight/authority drift")
    return value


def exact_source_list(
        rows: list[dict[str, Any]], expected: tuple[str, ...]
        ) -> Callable[..., list[str]]:
    paths = [str(ROOT / row["path"]) for row in rows]

    def selected(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        require(tuple(extra_definitions) == expected,
                "final link requested a feature scope other than the bound union")
        return list(paths)

    return selected


def run_link() -> None:
    preflight = consume_preflight()
    projection = preflight["feature_projection"]
    features = tuple(projection["bound_profile_features"])
    combined = tuple(projection["combined_compiler_features"])
    source_before = BASE.immutable_tree()
    inputs_before = BASE.reference_inputs()
    old_config, _paths = BASE.PREVIOUS.configure_candidate()
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    old_features = PRODUCT.configure_compiler_consumed_feature_profile(
        BASE.PROFILE, bind(BASE.PROFILE), features)
    try:
        PRODUCT.source_list = exact_source_list(
            inputs_before["compiler_inputs"], combined)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = BASE.SOURCE_MANIFEST
        artifacts = load(BASE.SOURCE_MANIFEST)
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [BASE.SOURCE_WPLTO / "stage-config.h",
             BASE.SOURCE_WPLTO / "runtime-overlay.prepare.h",
             WPLTO / "resident-island.h",
             WPLTO / "error-text-table.h",
             WPLTO / "c2-kernal-window.generated.h"],
            artifacts, probe_definitions=combined,
            deterministic_object_directory=OBJECT_ROOT)
    finally:
        PRODUCT.restore_compiler_consumed_feature_profile(old_features)
        PRODUCT.source_list = old_source_list
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old_config)
    require(BASE.immutable_tree() == source_before
            and BASE.reference_inputs() == inputs_before
            and PREVIOUS.partial_prefix() == preflight["target"][
                "partial_object_prefix"],
            "replacement changed immutable or historical Red evidence")
    finals = BASE.bound_family(FINAL)
    objects = sorted(path for path in OBJECT_ROOT.glob("*.o"))
    require(len(finals) == 4 and len(objects) == 66,
            "profile-consumed final/object family incomplete")
    feature_receipt = load(
        Path(str(FINAL) + ".compiler-feature-consumption.json"))
    require(feature_receipt["consumed_feature_count"] == 24
            and feature_receipt["missing_features"] == [],
            "persisted 24/24 feature consumption drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__)),
            "producer": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py")},
        "source_evidence_before": source_before,
        "source_evidence_after": BASE.immutable_tree(),
        "header_references": PREVIOUS.header_references(),
        "feature_projection": projection,
        "compiler_feature_consumption": bind(
            Path(str(FINAL) + ".compiler-feature-consumption.json")),
        "compiler_feature_result": feature_receipt,
        "historical_partial_objects": {
            "preserved": True, "reused": False,
            "objects": PREVIOUS.partial_prefix()},
        "object_compilation": {"directory":
            OBJECT_ROOT.relative_to(ROOT).as_posix(),
            "new_count": len(objects), "historical_reused_count": 0},
        "materialization": {"new_runs": 0,
            "reused_deterministic_header": bind(WPLTO / "resident-island.h")},
        "final_artifacts": finals,
        "compiler_input_consumption": bind(
            Path(str(FINAL) + ".compiler-input-consumption.json")),
        "candidate_derived_inventory": bind(
            WPLTO / f"final-section-inventory-{FINAL.name}.json"),
        "LTO_metadata": bind(
            WPLTO / f"lto-partition-metadata-{FINAL.name}.json"),
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0, "new_materializations": 0,
            "new_compiled_objects": 66, "final_product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "next": "same acceptance authorities over the four final artifacts",
        "claim_limit": (
            "Profile-derived replacement compilation and final link only. "
            "Acceptance, Completion, media and device actions have not run.")}
    LINK_RECEIPT.write_bytes(canonical(value))
    print("profile-consumption replacement: LINK PASS profile=24/24 "
          "compiled=66 final=4 WPLTO=0 link=1")


def record_final_red(error: Exception) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    finals = {path.name: bind(path) for path in BASE.family(FINAL)
              if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-profile-consumption-replacement-red-v1",
        "recorded_on": "2026-08-17",
        "status": "FINAL RED: PROFILE-CONSUMPTION REPLACEMENT RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT) if PREFLIGHT.exists() else None,
            "driver": bind(Path(__file__))},
        "source_evidence": BASE.immutable_tree(), "seed": BASE.seed_family(),
        "header_references": PREVIOUS.header_references(),
        "historical_partial_objects": PREVIOUS.partial_prefix(),
        "final_artifacts": finals, "retry_authorized": False,
        "owner_disposition_required": True,
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0,
            "final_product_links": 1 if len(finals) == 4 else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Terminal replacement Red; no automatic retry."}))


def check() -> None:
    value = load(LINK_RECEIPT)
    require(value.get("status") == STATUS
            and value["final_artifacts"] == BASE.bound_family(FINAL)
            and value["compiler_feature_result"]["consumed_feature_count"] == 24
            and value["object_compilation"]["new_count"] == 66,
            "profile-consumption replacement receipt drift")
    print("profile-consumption replacement: CHECK PASS profile=24/24 final=4")


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
                print(f"profile-consumption Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProfileConsumptionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"profile-consumption replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
