#!/usr/bin/env python3
"""Resume the owned target after proving every real compiler consumer."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_root_padding_separate_target_replacement as PREVIOUS  # noqa: E402
import c2_v21_root_padding_separate_target_replacement_red_attribution as ATTR  # noqa: E402


BASE = PREVIOUS.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TARGET = PREVIOUS.TARGET
WPLTO = PREVIOUS.WPLTO
FINAL = PREVIOUS.FINAL
OBJECT_ROOT = WPLTO / (".canonical-objects-" + FINAL.stem)
PREFLIGHT_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-compiler-consumption-preflight")
PREFLIGHT = PREFLIGHT_ROOT / "preflight.json"
LINK_RECEIPT = TARGET / "compiler-consumption-final-link.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-compiler-consumption-replacement-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-compiler-consumption-replacement-final-red.json")
AUTHORIZATION = "00b99d71"
FORMAT = "lisp65-c2.3-v2.1-compiler-consumption-replacement-v1"
STATUS = "PASS: real consumers green and partial object prefix resumed"
HEADER_NAMES = (
    "c2-kernal-window.generated.h",
    "error-text-table.h",
)


class ConsumptionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConsumptionError(message)


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
    for token in ("header visibility and preprocessor smoke authorized",
                  "read-only sibling symlinks", "genuine preprocessor pass",
                  "of every translation unit", "one replacement run"):
        require(token in text, f"compiler-consumption authority absent: {token}")
    return value


def final_paths() -> list[str]:
    return [path.relative_to(ROOT).as_posix()
            for path in BASE.family(FINAL) if path.exists()]


def partial_prefix() -> list[dict[str, Any]]:
    attribution = load(ATTR.RECEIPT)
    expected = attribution["mechanism"]["partial_objects"]
    rows: list[dict[str, Any]] = []
    for item in expected:
        path = ROOT / item["path"]
        current = bind(path)
        require(current == item, f"partial object identity drift: {path}")
        rows.append({"name": path.name, "bytes": current["bytes"],
                     "sha256": current["sha256"]})
    require([row["name"] for row in rows] == [
        "000-buffer_overlay.c.o", "001-c2_hot_literal.c.o"],
        "partial object prefix is not exact")
    return rows


def link_reference(path: Path, source: Path) -> None:
    require(source.is_file() and not source.is_symlink(),
            f"immutable header source absent: {source}")
    relative = os.path.relpath(source, start=path.parent)
    if not path.exists() and not path.is_symlink():
        path.symlink_to(relative)
    require(path.is_symlink() and os.readlink(path) == relative
            and path.resolve(strict=True) == source.resolve(strict=True),
            f"read-only header reference misbound: {path}")


def header_references() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in HEADER_NAMES:
        source = BASE.SOURCE_WPLTO / name
        target = WPLTO / name
        relative = os.path.relpath(source, start=target.parent)
        require(target.is_symlink() and os.readlink(target) == relative
                and target.resolve(strict=True) == source.resolve(strict=True),
                f"header sibling reference absent: {name}")
        mode = stat.S_IMODE(source.stat().st_mode)
        require(mode & 0o222 == 0, f"header source is writable: {source}")
        rows.append({
            "name": name,
            "target": target.relative_to(ROOT).as_posix(),
            "relative_reference": relative,
            "source": bind(source),
            "source_mode": format(mode, "04o"),
            "target_is_symlink": True,
            "target_is_copy": False,
            "resolution_exact": True,
        })
    return rows


def target_state() -> dict[str, Any]:
    require(TARGET.is_dir() and WPLTO.is_dir() and not WPLTO.is_symlink(),
            "owned continuation target absent")
    require((WPLTO / "c2-substitution.ld").is_symlink()
            and (WPLTO / "full-map-linker").is_symlink(),
            "prior immutable linker references absent")
    materialized = bind(WPLTO / "resident-island.h")
    witness = bind(BASE.PREVIOUS.STATE /
                   "materialization-probe/resident-island-a.h")
    require(materialized["sha256"] == witness["sha256"],
            "deterministic materialization drift")
    prefix = partial_prefix()
    existing = sorted(path.name for path in OBJECT_ROOT.iterdir())
    require(existing == [row["name"] for row in prefix],
            "partial object directory gained an unbound member")
    require(final_paths() == [], "final family exists before replacement")
    return {
        "path": TARGET.relative_to(ROOT).as_posix(),
        "materialized_header": materialized,
        "equals_prior_witness": True,
        "partial_object_prefix": prefix,
        "partial_object_count": len(prefix),
        "final_artifacts": [],
    }


def failed_compile_command() -> list[str]:
    red = load(PREVIOUS.FINAL_RED)
    message = red["error"]["message"]
    prefix = "Command '"
    suffix = "' returned non-zero exit status 1."
    require(message.startswith(prefix) and message.endswith(suffix),
            "prior real compiler command absent")
    value = ast.literal_eval(message[len(prefix):-len(suffix)])
    require(isinstance(value, list) and all(isinstance(item, str) for item in value),
            "prior compiler command is not a string list")
    return value


def preprocessor_command_prefix() -> list[str]:
    command = failed_compile_command()
    compile_index = command.index("-c")
    require(command[compile_index + 1] == "src/c2_kernal_runtime.c"
            and command.count("-c") == 1
            and command[0] == str(PRODUCT.TOOLCHAIN / "mos-mega65-clang"),
            "prior compiler command boundary drift")
    # The target occurs as the argument following -I, not as a standalone
    # source.  Bind that exact search-domain membership separately.
    target_arg = WPLTO.relative_to(ROOT).as_posix()
    pairs = list(zip(command, command[1:]))
    require(pairs.count(("-I", target_arg)) == 1
            and all(value != BASE.SOURCE_WPLTO.relative_to(ROOT).as_posix()
                    for flag, value in pairs if flag == "-I"),
            "prior compiler include-search domain drift")
    return command[:compile_index]


def preprocess_smoke(inputs: dict[str, Any]) -> dict[str, Any]:
    prefix = preprocessor_command_prefix()
    sources = [row["path"] for row in inputs["compiler_inputs"]]
    require(len(sources) == 66 and len(set(sources)) == 66,
            "preprocessor input closure drift")
    before = partial_prefix()
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        flags = ([prefix[0], "-Qunused-arguments", *prefix[1:]]
                 if Path(source).suffix == ".s" else list(prefix))
        command = [*flags, "-E", source, "-o", "/dev/null"]
        completed = subprocess.run(
            command, cwd=ROOT, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, check=False)
        require(completed.returncode == 0,
                f"real preprocessor consumer red: {source}: {completed.stderr}")
        rows.append({
            "ordinal": index,
            "source": bind(ROOT / source),
            "language": "assembler" if Path(source).suffix == ".s" else "c",
            "exit_status": completed.returncode,
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode()).hexdigest(),
        })
    require(partial_prefix() == before,
            "preprocessor smoke changed the partial object prefix")
    return {
        "status": "PASS: real preprocessor consumed every translation unit",
        "translation_units": rows,
        "translation_unit_count": len(rows),
        "c_count": sum(row["language"] == "c" for row in rows),
        "assembler_count": sum(
            row["language"] == "assembler" for row in rows),
        "exact_target_include_domain": WPLTO.relative_to(ROOT).as_posix(),
        "immutable_source_include_domain_added": False,
        "output": "/dev/null",
        "filesystem_writes": 0,
    }


def validate_preflight(value: dict[str, Any]) -> None:
    smoke = value["real_preprocessor_smoke"]
    require(
        value.get("format") == FORMAT
        and value.get("status") ==
            "PASS: sibling headers and real consumers dry-run green"
        and len(value["header_references"]) == 2
        and all(row["target_is_symlink"] is True
                and row["target_is_copy"] is False
                and row["source_mode"] == "0444"
                and row["resolution_exact"] is True
                for row in value["header_references"])
        and value["target"]["partial_object_count"] == 2
        and smoke["translation_unit_count"] == 66
        and smoke["c_count"] == 46
        and smoke["assembler_count"] == 20
        and len(smoke["translation_units"]) == 66
        and all(row["exit_status"] == 0
                for row in smoke["translation_units"])
        and smoke["immutable_source_include_domain_added"] is False
        and smoke["filesystem_writes"] == 0
        and value["execution_lock"] == {
            "replacement_runs": 0, "new_materializations": 0,
            "new_compiled_objects": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "compiler-consumption preflight drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "copy-header": lambda x: x["header_references"][0].update(
            target_is_symlink=False, target_is_copy=True),
        "writable-source": lambda x: x["header_references"][1].update(
            source_mode="0644"),
        "drop-translation-unit": lambda x: x["real_preprocessor_smoke"][
            "translation_units"].pop(),
        "failed-consumer": lambda x: x["real_preprocessor_smoke"][
            "translation_units"][2].update(exit_status=1),
        "ambient-source-search": lambda x: x["real_preprocessor_smoke"].update(
            immutable_source_include_domain_added=True),
        "preprocessor-write": lambda x: x["real_preprocessor_smoke"].update(
            filesystem_writes=1),
        "drop-prefix-object": lambda x: x["target"].update(
            partial_object_count=1),
        "invent-link": lambda x: x["execution_lock"].update(
            final_product_links=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_preflight(trial)
        except ConsumptionError:
            rejected.append(name)
    require(rejected == list(cases),
            "compiler-consumption preflight mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    inputs = BASE.reference_inputs()
    target = target_state()
    refs = header_references()
    resolution = PREVIOUS.reference_smoke(inputs)
    source_owner = PREVIOUS.real_consumer_dry_run(inputs)
    preprocessor = preprocess_smoke(inputs)
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": "PASS: sibling headers and real consumers dry-run green",
        "authority": {
            "owner": authorization(),
            "prior_Final_Red": bind(PREVIOUS.FINAL_RED),
            "red_attribution": bind(ATTR.RECEIPT),
            "driver": bind(Path(__file__)),
            "producer": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
        },
        "source_evidence": BASE.immutable_tree(),
        "inputs": inputs,
        "target": target,
        "header_references": refs,
        "reference_resolution_smoke": resolution,
        "real_source_owner_consumer": source_owner,
        "real_preprocessor_smoke": preprocessor,
        "execution_lock": {
            "replacement_runs": 0, "new_materializations": 0,
            "new_compiled_objects": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Authorized reference setup and dry-run only. No new object, final "
            "link, Completion, medium or device action."),
    }
    validate_preflight(value)
    value["mutations_rejected"] = mutations(value)
    return value


def record_preflight() -> None:
    require(not PREFLIGHT_ROOT.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "compiler-consumption replacement is one-shot")
    for name in HEADER_NAMES:
        link_reference(WPLTO / name, BASE.SOURCE_WPLTO / name)
    value = preflight_value()
    PREFLIGHT_ROOT.mkdir()
    PREFLIGHT.write_bytes(canonical(value))
    print("compiler-consumption replacement: PREFLIGHT PASS refs=83 "
          "preprocess=66 c=46 asm=20 writes=0")


def consume_preflight() -> dict[str, Any]:
    value = load(PREFLIGHT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == mutations(value)
            and value["authority"]["driver"] == bind(Path(__file__))
            and value["authority"]["producer"] == bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py")
            and value["source_evidence"] == BASE.immutable_tree()
            and value["header_references"] == header_references()
            and value["target"] == target_state(),
            "compiler-consumption preflight/inputs drift")
    return value


def run_link() -> None:
    preflight = consume_preflight()
    source_before = BASE.immutable_tree()
    inputs_before = BASE.reference_inputs()
    prefix = partial_prefix()
    old_config, _paths = BASE.PREVIOUS.configure_candidate()
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    try:
        probe_definitions = PREVIOUS.candidate_probe_definitions()
        PRODUCT.source_list = PREVIOUS.exact_source_list(
            inputs_before["compiler_inputs"], probe_definitions)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = BASE.SOURCE_MANIFEST
        artifacts = load(BASE.SOURCE_MANIFEST)
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [BASE.SOURCE_WPLTO / "stage-config.h",
             BASE.SOURCE_WPLTO / "runtime-overlay.prepare.h",
             WPLTO / "resident-island.h",
             WPLTO / "error-text-table.h",
             WPLTO / "c2-kernal-window.generated.h"],
            artifacts, probe_definitions=probe_definitions,
            deterministic_object_prefix=prefix)
    finally:
        PRODUCT.source_list = old_source_list
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old_config)
    require(BASE.immutable_tree() == source_before
            and BASE.reference_inputs() == inputs_before,
            "replacement changed immutable referenced evidence")
    finals = BASE.bound_family(FINAL)
    require(len(finals) == 4, "replacement final family incomplete")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__)),
            "producer": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py")},
        "source_evidence_before": source_before,
        "source_evidence_after": BASE.immutable_tree(),
        "header_references": header_references(),
        "materialization": {"new_runs": 0,
            "reused_deterministic_header": bind(WPLTO / "resident-island.h")},
        "object_compilation": {"reused_prefix": prefix,
            "reused_count": len(prefix), "new_count": 64,
            "total_count": 66},
        "final_artifacts": finals,
        "compiler_input_consumption": bind(
            Path(str(FINAL) + ".compiler-input-consumption.json")),
        "candidate_derived_inventory": bind(
            WPLTO / f"final-section-inventory-{FINAL.name}.json"),
        "LTO_metadata": bind(
            WPLTO / f"lto-partition-metadata-{FINAL.name}.json"),
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0, "new_materializations": 0,
            "reused_objects": 2, "new_compiled_objects": 64,
            "final_product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "same acceptance authorities over the four final artifacts",
        "claim_limit": (
            "Replacement compilation and final link only. Acceptance, "
            "Completion, media and device actions have not run."),
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    print("compiler-consumption replacement: LINK PASS reused=2 compiled=64 "
          "final=4 WPLTO=0 link=1")


def record_final_red(error: Exception) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    finals = {path.name: bind(path) for path in BASE.family(FINAL)
              if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-compiler-consumption-replacement-red-v1",
        "recorded_on": "2026-08-17",
        "status": "FINAL RED: COMPILER-CONSUMPTION REPLACEMENT RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT) if PREFLIGHT.exists() else None,
            "driver": bind(Path(__file__))},
        "source_evidence": BASE.immutable_tree(), "seed": BASE.seed_family(),
        "header_references": header_references(),
        "final_artifacts": finals, "retry_authorized": False,
        "owner_disposition_required": True,
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0,
            "final_product_links": 1 if len(finals) == 4 else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Terminal replacement Red; no automatic retry.",
    }))


def check() -> None:
    value = load(LINK_RECEIPT)
    require(value.get("status") == STATUS
            and value["final_artifacts"] == BASE.bound_family(FINAL)
            and value["object_compilation"]["reused_count"] == 2
            and value["object_compilation"]["new_count"] == 64,
            "compiler-consumption replacement receipt drift")
    print("compiler-consumption replacement: CHECK PASS final=4 link=1")


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
                print(f"compiler-consumption Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConsumptionError, OSError, ValueError, KeyError, SyntaxError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"compiler-consumption replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
