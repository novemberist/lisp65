#!/usr/bin/env python3
"""Project the bound profile through real configurators, then finish the link.

This is the sole replacement authorized after the profile-consumption run
proved that spelling a feature on the compiler command line does not recreate
the configurator state owned by that feature.  The preflight therefore runs
the real historical/current configurator chain and semantically compiles every
translation unit before the replacement run may start.
"""

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
import c2_v20_phase02b_header_consumption_card as HEADER  # noqa: E402
import c2_v21_root_padding_profile_consumption_replacement as PREVIOUS  # noqa: E402
import c2_v21_root_padding_profile_consumption_red_attribution as RED  # noqa: E402


BASE = PREVIOUS.BASE
CANONICAL = BASE.PREVIOUS.PRODUCER.BASE.L95.CAN
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TAINTED_TARGET = PREVIOUS.TARGET
TAINTED_WPLTO = PREVIOUS.WPLTO
TAINTED_FINAL = PREVIOUS.FINAL
TAINTED_RED = ARCH / (
    "c2.3-v2.1-root-padding-configurator-projection-replacement-final-red.json")
TARGET = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation")
WPLTO = TARGET / "wplto"
FINAL = WPLTO / "lisp65-c2-substitution-linked.prg"
OBJECT_ROOT = WPLTO / (
    ".canonical-objects-" + FINAL.stem + "-configurator-parity")
FAILED_SEMANTIC_PREFLIGHT_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-closure-preflight")
PREFLIGHT_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-preflight")
PREFLIGHT_OBJECT_ROOT = PREFLIGHT_ROOT / "semantic-objects"
PREFLIGHT = PREFLIGHT_ROOT / "preflight.json"
LINK_RECEIPT = TARGET / "configurator-parity-final-link.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-replacement-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-replacement-final-red.json")
PREFLIGHT_RED = ARCH / (
    "c2.3-v2.1-root-padding-configurator-projection-preflight-red.json")
PREFLIGHT_HARNESS_RED = ARCH / (
    "c2.3-v2.1-root-padding-configurator-semantic-harness-first-red.json")
PREFLIGHT_DRIVER_COMMIT = "588f509b"
PRODUCT_CONSUMPTION_RECEIPT = ARCH / (
    "c2.3-v2.0-phase02b-header-consumption-replacement-card-receipt.json")
AUTHORIZATION = "7d49bb5d"
FORMAT = "lisp65-c2.3-v2.1-configurator-parity-replacement-v3"
STATUS = (
    "PASS: product/continuation configurators match, 46043 consumed, "
    "66/66 compiled, final linked")


class ProjectionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProjectionError(message)


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


def function_binding(function: Callable[..., Any]) -> dict[str, Any]:
    module = sys.modules[function.__module__]
    path = Path(module.__file__).resolve()
    return {"module": function.__module__, "function": function.__name__,
            "source": bind(path)}


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
    for token in ("consumption closure completed, one final link authorized",
                  "tainted finals persist", "configure_consumption()",
                  "every configurator the product build runs",
                  "46,043", "exactly one new final link"):
        require(token in text, f"configurator-parity authority absent: {token}")
    return value


def bound_features() -> tuple[tuple[str, ...], tuple[str, ...]]:
    prior = PREVIOUS.feature_projection()
    profile = tuple(prior["bound_profile_features"])
    candidate = tuple(prior["candidate_scope_features"])
    require(len(profile) == 24 and len(candidate) == 6
            and tuple(prior["combined_compiler_features"])
                == (*profile, *candidate),
            "bound feature union drift")
    return profile, candidate


def product_consumption_authority() -> dict[str, Any]:
    value = load(PRODUCT_CONSUMPTION_RECEIPT)
    rows = value["compiler_input_consumption"]
    require(value["status"].startswith("PASS")
            and set(rows) == {"seed", "final"}
            and all(row["result"]["consumed_value"] == 46043
                    and row["result"]["bound_header"] == HEADER.header_binding()
                    and row["result"]["status"]
                        == "passed-bound-candidate-header-consumed"
                    for row in rows.values()),
            "product-build static-header configurator authority drift")
    return {"receipt": bind(PRODUCT_CONSUMPTION_RECEIPT),
            "seed": rows["seed"], "final": rows["final"]}


def state(artifacts: dict[str, Any]) -> dict[str, Any]:
    definitions = PRODUCT.definitions(artifacts)
    return {
        "runtime_overlay_format": PRODUCT.RUNTIME_OVERLAY_FORMAT_VERSION,
        "append_names": [name for name, _entry in PRODUCT.C2_APPEND_SLICES],
        "append_count": len(PRODUCT.C2_APPEND_SLICES),
        "boot_slice_count": len(PRODUCT.BOOT_SLICE_SPECS),
        "boot_data_count": len(PRODUCT.BOOT_DATA_SPECS),
        "boot_family_count": (
            len(PRODUCT.BOOT_SLICE_SPECS) + len(PRODUCT.BOOT_DATA_SPECS)),
        "session_family_count": len(PRODUCT.SESSION_SLICE_SPECS),
        "unique_slice_count": PRODUCT.UNIQUE_SLICE_COUNT,
        "bank3_staging": PRODUCT.BANK3_STAGING_SLICES,
        "bank3_session_slot": PRODUCT.BOOT_BANK3_STAGE_SLOT,
        "island_install_slot": PRODUCT.BOOT_ISLAND_SLOT,
        "island_carrier_slot": PRODUCT.BOOT_ISLAND_CARRIER_SLOT,
        "intern_session_service": PRODUCT.INTERN_SESSION_SERVICE,
        "session_service_slot_base": PRODUCT.SESSION_SERVICE_SLOT_BASE,
        "session_emitter_state_bytes": PRODUCT.SESSION_EMITTER_STATE_BYTES,
        "fixed_bank0_code_bytes": PRODUCT.FIXED_BANK0_CODE_BYTES,
        "compiler_consumed_static_header": (
            bind(PRODUCT.COMPILER_CONSUMED_STATIC_HEADER)
            if PRODUCT.COMPILER_CONSUMED_STATIC_HEADER is not None else None),
        "compiler_consumed_static_code_bytes": (
            PRODUCT.COMPILER_CONSUMED_STATIC_CODE_BYTES),
        "compiler_definitions": definitions,
    }


def definition_map(values: list[str]) -> dict[str, str]:
    result = {item.split("=", 1)[0]: item for item in values}
    require(len(result) == len(values), "configured compiler definition duplicated")
    return result


PROFILE_OWNED_EXCLUSIONS = {
    "LISP65_C2_LITE_BANK2_STAGING",
    "LISP65_RUNTIME_OVERLAY_FORMAT_V4",
    "LISP65_C2_TWO_REGION_SESSION_STORE",
}


def validate_projection(value: dict[str, Any]) -> None:
    profile, previous_candidate = bound_features()
    effective = tuple(value["effective_final_link_features"])
    combined = tuple(dict.fromkeys((*profile, *effective)))
    steps = value["steps"]
    mappings = value["feature_configurators"]
    final = value["final_state"]
    derived = value["derived_compiler_bindings"]
    product_closure = value["product_build_configurators"]
    continuation_closure = value["continuation_configurators"]
    require(
        value.get("status") == "PASS: all profile features configured"
        and value["bound_profile_features"] == list(profile)
        and value["previous_candidate_scope_features"]
            == list(previous_candidate)
        and value["effective_final_link_features"] == [
            "LISP65_CODE_WINDOW_CONVERGENCE",
            "LISP65_DMA_CONTENT_CONVERGENCE",
            "LISP65_C2_ASM_CONVERGENCE",
            "LISP65_C2_FULL_SPAN_CONVERGENCE",
            "LISP65_C2_MUTABLE_CPU_READS",
            "LISP65_C2_TERMINAL_RETURN_GUARD",
            "LISP65_STARTUP_REQUIRE_EXPERIENCE",
            "LISP65_C2_MAP_CPU_TRANSPORT",
            "LISP65_C2_REQUIRE_RESOLVER",
        ]
        and value["wrapper_derived_features"] == [
            "LISP65_C2_TERMINAL_RETURN_GUARD",
            "LISP65_STARTUP_REQUIRE_EXPERIENCE",
            "LISP65_C2_REQUIRE_RESOLVER",
        ]
        and value["combined_compiler_features"] == list(combined)
        and len(combined) == 33
        and [row["name"] for row in steps] == [
            "product-candidate-chain", "complete-profile", "bank2-stage", "two-region",
            "current-pin-adapters", "intern-session-service",
            "static-header-consumption",
            "real-final-link-consumer"]
        and all(row["invoked"] is True and row["output"]
                for row in steps)
        and set(mappings) == set(combined)
        and all(mappings[name]["output"] for name in combined)
        and steps[-1]["output"]["probe_definitions"] == list(effective)
        and steps[-1]["output"]["feature_count"] == 9
        and steps[-1]["output"]["extra_arguments"] == {}
        and product_closure == continuation_closure
        and value["product_build_consumption_authority"]
            == product_consumption_authority()
        and len(product_closure) == 7
        and [row["name"] for row in product_closure] == [
            "product-candidate-chain", "complete-profile", "bank2-stage",
            "two-region", "current-pin-adapters", "intern-session-service",
            "static-header-consumption"]
        and all(row["invoked"] is True for row in continuation_closure)
        and final["runtime_overlay_format"] == 4
        and final["append_count"] == 24
        and final["boot_family_count"] == 12
        and final["session_family_count"] == 52
        and final["bank3_staging"] is True
        and final["bank3_session_slot"] == 9
        and final["island_install_slot"] == 10
        and final["island_carrier_slot"] == 11
        and final["intern_session_service"] is True
        and final["compiler_consumed_static_code_bytes"] == 46043
        and final["compiler_consumed_static_header"] == HEADER.header_binding()
        and steps[1]["output"]["bank3_session_slot"] == 8
        and steps[2]["output"]["bank3_session_slot"] == 9
        and derived == {
            "LISP65_BUFFER_OVERLAY_ALLOC_SLOT": {
                "before": "LISP65_BUFFER_OVERLAY_ALLOC_SLOT=35",
                "after": "LISP65_BUFFER_OVERLAY_ALLOC_SLOT=50"},
            "LISP65_BUFFER_OVERLAY_READ_SLOT": {
                "before": "LISP65_BUFFER_OVERLAY_READ_SLOT=33",
                "after": "LISP65_BUFFER_OVERLAY_READ_SLOT=48"},
            "LISP65_BUFFER_OVERLAY_WRITE_SLOT": {
                "before": "LISP65_BUFFER_OVERLAY_WRITE_SLOT=34",
                "after": "LISP65_BUFFER_OVERLAY_WRITE_SLOT=49"},
            "LISP65_C2_BANK3_STAGE_SESSION_SLOT": {
                "before": None,
                "after": "LISP65_C2_BANK3_STAGE_SESSION_SLOT=9"},
            "LISP65_ERROR_OVERLAY_SLOT": {
                "before": "LISP65_ERROR_OVERLAY_SLOT=32",
                "after": "LISP65_ERROR_OVERLAY_SLOT=47"},
            "LISP65_INTERN_SERVICE_SLOT": {
                "before": None, "after": "LISP65_INTERN_SERVICE_SLOT=51"},
            "LISP65_INTERN_SESSION_SERVICE": {
                "before": None, "after": "LISP65_INTERN_SESSION_SERVICE"},
            "LISP65_RUNTIME_ISLAND_CARRIER_SLOT": {
                "before": "LISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
                "after": "LISP65_RUNTIME_ISLAND_CARRIER_SLOT=11"},
            "LISP65_RUNTIME_ISLAND_INSTALL_SLOT": {
                "before": "LISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
                "after": "LISP65_RUNTIME_ISLAND_INSTALL_SLOT=10"},
        },
        "real configurator projection drift")


def projection_mutations(value: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    for feature in value["combined_compiler_features"]:
        trial = deepcopy(value)
        trial["feature_configurators"][feature]["output"] = None
        try:
            validate_projection(trial)
        except ProjectionError:
            rejected.append("missing-configurator-output:" + feature)
    require(len(rejected) == 33,
            "feature-without-configurator-output mutation survived")
    for side in ("product_build_configurators", "continuation_configurators"):
        for index, row in enumerate(value[side]):
            trial = deepcopy(value)
            trial[side].pop(index)
            try:
                validate_projection(trial)
            except ProjectionError:
                rejected.append(
                    f"one-sided-configurator:{side}:{row['name']}")
    require(len(rejected) == 47,
            "one-sided configurator mutation survived")
    return rejected


def configure_projected_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the product configurators, never synthesize their definitions."""
    captured: dict[str, Any] = {}

    def final_consumer(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path | None = None,
        direct_entry_check_tool: str = "",
        extra_contract_lines: tuple[str, ...] = (), **kwargs: Any,
    ) -> None:
        require(not captured, "real final-link consumer invoked twice")
        captured.update({
            "out": out.relative_to(ROOT).as_posix(),
            "probe_definitions": list(probe_definitions),
            "feature_count": len(probe_definitions),
            "direct_entry_receipt": (
                direct_entry_receipt.relative_to(ROOT).as_posix()
                if direct_entry_receipt is not None else None),
            "direct_entry_check_tool": direct_entry_check_tool,
            "extra_contract_lines": list(extra_contract_lines),
            "extra_arguments": kwargs,
        })

    # Install the capture at the actual base consumer before any historical
    # configurator composes its wrapper.  Invoking the resulting top-level
    # consumer below therefore exercises the complete configured chain without
    # compiling or linking anything.
    PRODUCT.single_link = final_consumer
    old, _paths = BASE.PREVIOUS.configure_candidate()
    artifacts = load(BASE.SOURCE_MANIFEST)
    initial = state(artifacts)
    chain: list[tuple[str, Callable[[], Any]]] = [
        ("complete-profile", CANONICAL.REPLAY.PROFILE.configure),
        ("bank2-stage", CANONICAL.REPLAY.BANK2.configure_bank2_stage),
        ("two-region", CANONICAL.REPLAY.TWO.configure_two_region),
        ("current-pin-adapters",
         CANONICAL.REPLAY.LINK60.configure_current_pin_adapters),
        ("intern-session-service", PRODUCT.configure_intern_session_service),
    ]
    steps: list[dict[str, Any]] = [{
        "name": "product-candidate-chain", "invoked": True,
        "configurator": function_binding(BASE.PREVIOUS.configure_candidate),
        "output": initial}]
    for name, function in chain:
        function()
        steps.append({"name": name, "invoked": True,
                      "configurator": function_binding(function),
                      "output": state(artifacts)})
    header_binding = HEADER.configure_consumption()
    steps.append({"name": "static-header-consumption", "invoked": True,
                  "configurator": function_binding(HEADER.configure_consumption),
                  "output": {"binding": header_binding,
                      "consumed_value": PRODUCT.COMPILER_CONSUMED_STATIC_CODE_BYTES,
                      "state": state(artifacts)}})
    PRODUCT.single_link(
        ROOT / "build/c2.3/configurator-projection-capture-only",
        probe_definitions=PRODUCT.CONVERGENCE_DEFINES)
    require(captured, "real final-link consumer emitted no projection")
    steps.append({"name": "real-final-link-consumer", "invoked": True,
                  "configurator": {
                      "kind": "fully-composed-real-consumer",
                      "outer_module": PRODUCT.single_link.__module__,
                      "outer_function": PRODUCT.single_link.__name__},
                  "output": captured})
    profile, previous_candidate = bound_features()
    effective = tuple(captured["probe_definitions"])
    combined = tuple(dict.fromkeys((*profile, *effective)))
    wrapper_derived = tuple(
        item for item in effective if item not in previous_candidate)
    mappings: dict[str, dict[str, Any]] = {}
    for feature in profile:
        if feature == "LISP65_C2_LITE_BANK2_STAGING":
            owner = "bank2-stage"
        elif feature in {"LISP65_RUNTIME_OVERLAY_FORMAT_V4",
                          "LISP65_C2_TWO_REGION_SESSION_STORE"}:
            owner = "two-region"
        else:
            owner = "complete-profile"
        output = next(row["output"] for row in steps if row["name"] == owner)
        mappings[feature] = {"owner": owner, "output": {
            "runtime_overlay_format": output["runtime_overlay_format"],
            "append_count": output["append_count"],
            "boot_family_count": output["boot_family_count"],
            "session_family_count": output["session_family_count"],
            "bank3_session_slot": output["bank3_session_slot"],
        }}
    for feature in effective:
        mappings[feature] = {"owner": "real-final-link-consumer", "output": {
            "feature": feature, "consumer_feature_count": len(effective),
            "contract_lines": captured["extra_contract_lines"]}}
    before = definition_map(initial["compiler_definitions"])
    final = next(row["output"]["state"] for row in steps
                 if row["name"] == "static-header-consumption")
    after = definition_map(final["compiler_definitions"])
    changed = {name: {"before": before.get(name), "after": after.get(name)}
               for name in sorted(set(before) | set(after))
               if before.get(name) != after.get(name)}
    closure = [{"name": row["name"], "invoked": row["invoked"],
                "configurator": row["configurator"]}
               for row in steps if row["name"] != "real-final-link-consumer"]
    value = {
        "status": "PASS: all profile features configured",
        "bound_profile_features": list(profile),
        "previous_candidate_scope_features": list(previous_candidate),
        "effective_final_link_features": list(effective),
        "wrapper_derived_features": list(wrapper_derived),
        "combined_compiler_features": list(combined),
        "initial_unprojected_state": initial,
        "steps": steps,
        "feature_configurators": mappings,
        "product_build_configurators": deepcopy(closure),
        "continuation_configurators": deepcopy(closure),
        "product_build_consumption_authority": product_consumption_authority(),
        "derived_compiler_bindings": changed,
        "final_state": final,
        "rule": (
            "Profile features enter their real configurators. Compiler flags "
            "are emitted only from the resulting configured product state."),
    }
    validate_projection(value)
    value["mutations_rejected"] = projection_mutations(value)
    return old, value


def configured_compile_prefix(
        projection: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    command = RED.parse_command(load(PREVIOUS.FINAL_RED))
    compile_at = command.index("-c")
    prefix = command[:compile_at]
    define_positions = [index for index, token in enumerate(prefix)
                        if token.startswith("-D")]
    require(define_positions, "failed command has no compiler definitions")
    insert_at = define_positions[0]
    stripped = [token for token in prefix if not token.startswith("-D")]
    product = projection["final_state"]["compiler_definitions"]
    scoped = list(PRODUCT.scoped_probe_definitions(
        tuple(projection["combined_compiler_features"])))
    definitions = [*product, *scoped]
    names = [item.split("=", 1)[0] for item in definitions]
    require(len(names) == len(set(names)), "configured command defines twice")
    derived = projection["derived_compiler_bindings"]
    require(all(row["after"] in definitions for row in derived.values()),
            "derived configurator binding escaped compiler command")
    result = [*stripped[:insert_at],
              *(f"-D{item}" for item in definitions),
              *stripped[insert_at:]]
    consumed_flags, report = PRODUCT.compiler_consumed_static_header_flags(
        PREFLIGHT_ROOT, PREFLIGHT_ROOT / "semantic-candidate.prg")
    require(report is not None
            and report["bound_header"] == HEADER.header_binding()
            and report["consumed_value"] == 46043,
            "semantic compiler lacks candidate static-header projection")
    report["actual_force_include_flags"] = list(consumed_flags)
    return [*result, *consumed_flags], report


def historical_objects() -> dict[str, Any]:
    tainted = load(TAINTED_RED)
    expected = tainted["historical_partial_objects"]
    current = {
        "first_red": PREVIOUS.PREVIOUS.partial_prefix(),
        "profile_consumption_red": RED.object_bindings(),
        "preserved": True, "reused": False,
    }
    require(current == expected,
            "historical partial-object evidence drift")
    return current


def tainted_finals() -> dict[str, Any]:
    value = load(TAINTED_RED)
    expected = value["final_artifacts"]
    current = {path.name: bind(path) for path in BASE.family(TAINTED_FINAL)}
    require(current == expected
            and value["candidate_input_red"]["qualification_safe"] is False
            and value["execution_accounting"]["final_product_links"] == 1,
            "tainted final evidence drift")
    return current


def historical_objects_postlink(expected: dict[str, Any]) -> dict[str, Any]:
    """Read historical objects without reasserting a pre-link boundary."""
    current = {
        "first_red": PREVIOUS.PREVIOUS.partial_prefix(),
        "profile_consumption_red": RED.object_bindings(),
        "preserved": True, "reused": False,
    }
    require(current == expected,
            "historical partial-object identity changed after final link")
    return current


def static_header_consumption_red() -> dict[str, Any]:
    candidate = ROOT / (
        "build/c2.3/v2.0-ownership-recharter-inputs/"
        "c2_lite_static_plane.h")
    live = ROOT / "src/c2_lite_static_plane.h"

    def extent(path: Path) -> int:
        rows = [line for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith(
                    "#define LISP65_C2_LITE_STATIC_CODE_BYTES ")]
        require(len(rows) == 1, f"static-plane extent absent: {path}")
        return int(rows[0].split()[-1].removesuffix("UL"), 10)

    receipt = Path(str(FINAL) + ".compiler-input-consumption.json")
    phase = BASE.SOURCE_WPLTO / "generated-product-sources/c2-stream-phase-02b.c"
    generated_header = phase.parent / "c2_lite_static_plane.h"
    require(extent(candidate) == 46043 and extent(live) == 45939
            and not receipt.exists() and not generated_header.exists()
            and '#include "c2_lite_static_plane.h"' in (
                phase.parent / "c2-stream-decoder.c").read_text(
                    encoding="utf-8"),
            "static-header consumption attribution drift")
    return {
        "class": "BOUND-CANDIDATE-STATIC-HEADER-NOT-CONSUMED",
        "candidate_header": bind(candidate),
        "candidate_extent_bytes": extent(candidate),
        "ambient_header": bind(live),
        "ambient_extent_bytes": extent(live),
        "difference_bytes": extent(candidate) - extent(live),
        "compiler_input_consumption_receipt": None,
        "generated_translation_unit": bind(phase),
        "generated_local_header_absent": True,
        "known_consequence": (
            "phase-02b contract would expect 45939 bytes while the six "
            "candidate C2D rows deliver 46043 bytes"),
        "qualification_safe": False,
    }


def semantic_compile(projection: dict[str, Any]) -> dict[str, Any]:
    require(not PREFLIGHT_OBJECT_ROOT.exists(),
            "semantic preflight object directory pre-exists")
    PREFLIGHT_OBJECT_ROOT.mkdir()
    prefix, header_report = configured_compile_prefix(projection)
    inputs = BASE.reference_inputs()["compiler_inputs"]
    require(len(inputs) == 66, "semantic compiler input closure drift")
    historical_before = historical_objects()
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(inputs):
        source = item["path"]
        path = Path(source)
        output = PREFLIGHT_OBJECT_ROOT / (
            f"{index:03d}-{path.stem}{path.suffix}.o")
        flags = ([prefix[0], "-Qunused-arguments", *prefix[1:]]
                 if path.suffix == ".s" else list(prefix))
        completed = subprocess.run(
            [*flags, "-c", source, "-o", output.relative_to(ROOT).as_posix()],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, check=False)
        require(completed.returncode == 0,
                f"configured semantic compiler red: {source}: "
                f"{completed.stderr}")
        rows.append({"ordinal": index, "source": item,
                     "language": "assembler" if path.suffix == ".s" else "c",
                     "exit_status": 0, "object": bind(output),
                     "static_header_consumed": {
                         "bound": header_report["bound_header"],
                         "value": header_report["consumed_value"],
                         "assertion": header_report[
                             "compile_time_assertion"]},
                     "stderr_sha256": hashlib.sha256(
                         completed.stderr.encode()).hexdigest()})
    require(historical_objects() == historical_before,
            "semantic preflight changed historical partial objects")
    return {"status": "PASS: configured semantic compiler 66/66",
            "translation_unit_count": len(rows),
            "translation_units": rows,
            "object_directory": PREFLIGHT_OBJECT_ROOT.relative_to(ROOT).as_posix(),
            "objects_written": len(rows), "final_links": 0,
            "compiler_input_consumption": header_report,
            "derived_binding_count": len(
                projection["derived_compiler_bindings"]),
            "profile_features_configured": 24,
            "effective_final_link_features": 9,
            "wrapper_derived_features": 3,
            "combined_compiler_features": 33}


def target_state() -> dict[str, Any]:
    require(not TARGET.exists() and not OBJECT_ROOT.exists(),
            "configurator-projected object directory pre-exists")
    require(not any(path.exists() for path in BASE.family(FINAL)),
            "final family exists before configurator replacement")
    return {"path": TARGET.relative_to(ROOT).as_posix(),
            "materialized_header": bind(TAINTED_WPLTO / "resident-island.h"),
            "tainted_finals": tainted_finals(),
            "tainted_finals_preserved": True,
            "tainted_finals_promotable": False,
            "historical_objects": historical_objects(),
            "configurator_object_directory":
                OBJECT_ROOT.relative_to(ROOT).as_posix(),
            "configurator_object_directory_absent": True,
            "final_artifacts": []}


def validate_preflight(value: dict[str, Any]) -> None:
    projection = value["configurator_projection"]
    semantic = value["semantic_compile"]
    saved_mutations = projection.pop("mutations_rejected", None)
    try:
        validate_projection(projection)
    finally:
        if saved_mutations is not None:
            projection["mutations_rejected"] = saved_mutations
    require(
        value.get("format") == FORMAT
        and value.get("status") ==
            "PASS: configurators projected and all TUs semantically compiled"
        and saved_mutations is not None and len(saved_mutations) == 47
        and semantic["translation_unit_count"] == 66
        and len(semantic["translation_units"]) == 66
        and semantic["objects_written"] == 66
        and semantic["final_links"] == 0
        and all(row["exit_status"] == 0
                for row in semantic["translation_units"])
        and all(row["static_header_consumed"]["value"] == 46043
                and row["static_header_consumed"]["bound"]
                    == HEADER.header_binding()
                for row in semantic["translation_units"])
        and semantic["compiler_input_consumption"]["consumed_value"] == 46043
        and semantic["compiler_input_consumption"]["bound_header"]
            == HEADER.header_binding()
        and semantic["compiler_input_consumption"][
            "actual_force_include_flags"] == [
                "-include", HEADER.CANDIDATE_HEADER.relative_to(ROOT).as_posix(),
                "-include", semantic["compiler_input_consumption"][
                    "compile_time_assertion"]["path"]]
        and value["target"]["historical_objects"]["preserved"] is True
        and value["target"]["historical_objects"]["reused"] is False
        and value["target"]["tainted_finals_preserved"] is True
        and value["target"]["tainted_finals_promotable"] is False
        and value["target"]["configurator_object_directory_absent"] is True
        and value["prior_semantic_preflight_red"] == bind(PREFLIGHT_RED)
        and value["semantic_harness_red"] == bind(PREFLIGHT_HARNESS_RED)
        and value["execution_lock"] == {"replacement_runs": 0,
            "new_WPLTO_card_runs": 0, "product_objects": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "configurator semantic preflight drift")


def record_preflight_harness_red() -> None:
    require(not PREFLIGHT_HARNESS_RED.exists(),
            "semantic harness Red is one-shot")
    root = FAILED_SEMANTIC_PREFLIGHT_ROOT / "semantic-objects"
    objects = [bind(path) for path in sorted(root.glob("*.o"))]
    require(len(objects) == 66
            and not (FAILED_SEMANTIC_PREFLIGHT_ROOT / "preflight.json").exists()
            and not OBJECT_ROOT.exists()
            and not any(path.exists() for path in BASE.family(FINAL)),
            "semantic harness Red boundary drift")
    source_raw, source = git_bind(
        PREFLIGHT_DRIVER_COMMIT, Path(__file__).resolve())
    text = source_raw.decode()
    require(
        '"drop-semantic-TU": lambda x: x["semantic_compile"][\n'
        '            "translation_units"].pop()' in text
        and 'len(semantic["translation_units"]) == 66' not in text,
        "failed semantic-harness source mechanism drift")
    PREFLIGHT_HARNESS_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-configurator-semantic-harness-red-v1",
        "recorded_on": "2026-08-17",
        "status": "PREFLIGHT HARNESS RED: REMOVED TU ROW SURVIVED",
        "authority": {"owner": authorization(), "failed_driver": source,
            "prior_preflight_red": bind(PREFLIGHT_RED),
            "current_driver": bind(Path(__file__))},
        "semantic_compile": {"translation_units_green": len(objects),
            "objects": objects, "persisted_pass_receipt": False},
        "mechanism": {
            "mutation": "drop-semantic-TU",
            "declared_count_after_mutation": 66,
            "actual_rows_after_mutation": 65,
            "missing_invariant": (
                "declared TU count equals concrete translation-unit rows"),
            "fix": "bind len(translation_units) == 66 in validator"},
        "execution_accounting": {"semantic_preflight_attempts": 2,
            "replacement_runs": 0, "product_objects": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "retry": {"kind": "fresh disposable semantic preflight",
            "root": PREFLIGHT_ROOT.relative_to(ROOT).as_posix(),
            "authorized_replacement_run_still_unused": True},
        "claim_limit": (
            "All 66 disposable semantic objects compiled, but no PASS receipt "
            "was persisted. No product compilation or link ran."),
    }))
    print("configurator projection: PREFLIGHT HARNESS RED BOUND "
          "semantic=66 replacement=0")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-semantic-TU": lambda x: x["semantic_compile"][
            "translation_units"].pop(),
        "claim-65-TUs": lambda x: x["semantic_compile"].update(
            translation_unit_count=65),
        "reuse-historical-object": lambda x: x["target"][
            "historical_objects"].update(reused=True),
        "skip-feature-configurator": lambda x: x[
            "configurator_projection"]["feature_configurators"][
                x["configurator_projection"]["bound_profile_features"][0]
            ].update(output=None),
        "wrong-TU-static-header": lambda x: x["semantic_compile"][
            "translation_units"][0]["static_header_consumed"].update(
                value=45939),
        "drop-final-static-consumer": lambda x: x[
            "configurator_projection"]["continuation_configurators"].pop(),
        "invent-run": lambda x: x["execution_lock"].update(
            replacement_runs=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_preflight(trial)
        except ProjectionError:
            rejected.append(name)
    require(rejected == list(cases), "semantic preflight mutation survived")
    return rejected


def record_preflight() -> None:
    require(not PREFLIGHT_ROOT.exists() and not LINK_RECEIPT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "configurator-projection replacement is one-shot")
    PREFLIGHT_ROOT.mkdir()
    old: dict[str, Any] | None = None
    try:
        old, projection = configure_projected_candidate()
        value = {
            "format": FORMAT, "recorded_on": "2026-08-17",
            "status": (
                "PASS: configurators projected and all TUs semantically compiled"),
            "authority": {"owner": authorization(),
                "tainted_final_red": bind(TAINTED_RED),
                "profile_consumption_Final_Red": bind(PREVIOUS.FINAL_RED),
                "attribution": bind(RED.RECEIPT),
                "semantic_preflight_red": bind(PREFLIGHT_RED),
                "semantic_harness_red": bind(PREFLIGHT_HARNESS_RED),
                "bound_profile": bind(BASE.PROFILE),
                "driver": bind(Path(__file__)),
                "producer": bind(ROOT /
                    "tools/host-lisp/c2_product_substitution_link.py")},
            "source_evidence": BASE.immutable_tree(),
            "inputs": BASE.reference_inputs(),
            "header_references": PREVIOUS.PREVIOUS.header_references(),
            "prior_semantic_preflight_red": bind(PREFLIGHT_RED),
            "semantic_harness_red": bind(PREFLIGHT_HARNESS_RED),
            "target": target_state(),
            "configurator_projection": projection,
            "semantic_compile": semantic_compile(projection),
            "execution_lock": {"replacement_runs": 0,
                "new_WPLTO_card_runs": 0, "product_objects": 0,
                "final_product_links": 0, "completion_runs": 0,
                "media_builds": 0, "device_contacts": 0},
            "claim_limit": (
                "Real configurator projection and disposable semantic compile "
                "only. The replacement run, final link, Completion, media and "
                "device remain untouched."),
        }
        validate_preflight(value)
        value["mutations_rejected"] = preflight_mutations(value)
        PREFLIGHT.write_bytes(canonical(value))
    finally:
        if old is not None:
            BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old)
    print("configurator parity: PREFLIGHT PASS configurators=7/7 "
          "profile=24/24 final-consumer=9 combined=33 "
          "static-header=46043 semantic=66/66 link=0")


def consume_preflight() -> dict[str, Any]:
    value = load(PREFLIGHT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value)
            and value["authority"]["driver"] == bind(Path(__file__))
            and value["authority"]["producer"] == bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py")
            and value["source_evidence"] == BASE.immutable_tree()
            and value["inputs"] == BASE.reference_inputs()
            and value["target"] == target_state(),
            "configurator preflight/authority drift")
    return value


def exact_source_list(
        rows: list[dict[str, Any]], expected: tuple[str, ...]
        ) -> Callable[..., list[str]]:
    paths = [str(ROOT / row["path"]) for row in rows]

    def selected(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        require(tuple(extra_definitions) == expected,
                "final link requested a scope other than configured union")
        return list(paths)

    return selected


def prepare_link_target() -> None:
    require(not TARGET.exists(), "configurator-parity target pre-exists")
    TARGET.mkdir()
    WPLTO.mkdir()
    references = {
        "c2-substitution.ld": BASE.SOURCE_WPLTO / "c2-substitution.ld",
        "full-map-linker": BASE.SOURCE_WPLTO / "full-map-linker",
        "error-text-table.h": BASE.SOURCE_WPLTO / "error-text-table.h",
        "c2-kernal-window.generated.h": (
            BASE.SOURCE_WPLTO / "c2-kernal-window.generated.h"),
    }
    for name, source in references.items():
        require(source.exists() and not source.is_symlink(),
                f"link reference source absent: {source}")
        target = WPLTO / name
        target.symlink_to(os.path.relpath(source, start=target.parent))
        require(target.resolve() == source.resolve(),
                f"link reference resolution drift: {name}")


def run_link() -> None:
    preflight = consume_preflight()
    projection_bound = preflight["configurator_projection"]
    features_bound = tuple(projection_bound["bound_profile_features"])
    combined = tuple(projection_bound["combined_compiler_features"])
    source_before = BASE.immutable_tree()
    inputs_before = BASE.reference_inputs()
    tainted_before = tainted_finals()
    prepare_link_target()
    old_config, projection = configure_projected_candidate()
    projection.pop("mutations_rejected", None)
    expected_projection = deepcopy(projection_bound)
    expected_projection.pop("mutations_rejected", None)
    require(projection == expected_projection,
            "run configurator projection differs from semantic preflight")
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    old_features = PRODUCT.configure_compiler_consumed_feature_profile(
        BASE.PROFILE, bind(BASE.PROFILE), features_bound)
    try:
        PRODUCT.source_list = exact_source_list(
            inputs_before["compiler_inputs"], combined)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = BASE.SOURCE_MANIFEST
        artifacts = load(BASE.SOURCE_MANIFEST)
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [BASE.SOURCE_WPLTO / "stage-config.h",
             BASE.SOURCE_WPLTO / "runtime-overlay.prepare.h",
             TAINTED_WPLTO / "resident-island.h",
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
            and tainted_finals() == tainted_before
            and historical_objects() == preflight["target"][
                "historical_objects"],
            "replacement changed frozen source or historical Red evidence")
    finals = BASE.bound_family(FINAL)
    objects = sorted(path for path in OBJECT_ROOT.glob("*.o"))
    require(len(finals) == 4 and len(objects) == 66,
            "configurator-projected final/object family incomplete")
    feature_receipt = load(
        Path(str(FINAL) + ".compiler-feature-consumption.json"))
    input_receipt_path = Path(
        str(FINAL) + ".compiler-input-consumption.json")
    input_receipt = load(input_receipt_path)
    require(feature_receipt["consumed_feature_count"] == 24
            and feature_receipt["missing_features"] == []
            and input_receipt["status"]
                == "passed-bound-candidate-header-consumed"
            and input_receipt["bound_header"] == HEADER.header_binding()
            and input_receipt["consumed_value"] == 46043
            and input_receipt["historical_same_basename_accepted"] is False
            and input_receipt["actual_force_include_flags"] == [
                "-include", HEADER.CANDIDATE_HEADER.relative_to(ROOT).as_posix(),
                "-include", input_receipt["compile_time_assertion"]["path"]],
            "persisted configured feature/header consumption drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "tainted_final_red": bind(TAINTED_RED),
            "driver": bind(Path(__file__)),
            "producer": bind(ROOT /
                "tools/host-lisp/c2_product_substitution_link.py")},
        "source_evidence_before": source_before,
        "source_evidence_after": BASE.immutable_tree(),
        "configurator_projection": projection_bound,
        "semantic_preflight": {
            "translation_units": 66,
            "receipt": bind(PREFLIGHT),
            "object_directory": preflight["semantic_compile"][
                "object_directory"]},
        "compiler_feature_consumption": bind(
            Path(str(FINAL) + ".compiler-feature-consumption.json")),
        "compiler_feature_result": feature_receipt,
        "historical_partial_objects": historical_objects(),
        "tainted_final_evidence": tainted_before,
        "tainted_final_promoted": False,
        "object_compilation": {"directory":
            OBJECT_ROOT.relative_to(ROOT).as_posix(),
            "new_count": len(objects), "historical_reused_count": 0},
        "materialization": {"new_runs": 0,
            "reused_deterministic_header": bind(
                TAINTED_WPLTO / "resident-island.h")},
        "final_artifacts": finals,
        "compiler_input_consumption": bind(input_receipt_path),
        "compiler_input_result": input_receipt,
        "candidate_derived_inventory": bind(
            WPLTO / f"final-section-inventory-{FINAL.name}.json"),
        "LTO_metadata": bind(
            WPLTO / f"lto-partition-metadata-{FINAL.name}.json"),
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0, "new_materializations": 0,
            "semantic_preflight_objects": 66,
            "new_product_objects": 66, "final_product_links": 1,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "same read-only acceptance authorities over four finals",
        "claim_limit": (
            "Configurator-projected replacement compilation and final link "
            "only. Acceptance, Completion, media and device have not run."),
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    print("configurator parity: LINK PASS configurators=7/7 "
          "static-header=46043 profile=24/24 final-consumer=9 "
          "semantic=66/66 compiled=66 final=4 WPLTO=0 link=1")


def record_final_red(error: Exception) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    finals = {path.name: bind(path) for path in BASE.family(FINAL)
              if path.is_file() and not path.is_symlink()}
    preflight = load(PREFLIGHT)
    objects = [bind(path) for path in sorted(OBJECT_ROOT.glob("*.o"))]
    input_receipt_path = Path(
        str(FINAL) + ".compiler-input-consumption.json")
    input_receipt = (load(input_receipt_path)
                     if input_receipt_path.exists() else None)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-configurator-parity-red-v1",
        "recorded_on": "2026-08-17",
        "status": "FINAL RED: CONFIGURATOR-PARITY LINK RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__))},
        "source_evidence": BASE.immutable_tree(),
        "configured_input": {"bound_header": HEADER.header_binding(),
            "bound_value": 46043,
            "compiler_receipt": (bind(input_receipt_path)
                if input_receipt_path.exists() else None),
            "compiler_result": input_receipt},
        "tainted_final_evidence": tainted_finals(),
        "tainted_final_promoted": False,
        "historical_partial_objects": historical_objects_postlink(
            preflight["target"]["historical_objects"]),
        "new_product_objects": objects,
        "compiler_feature_consumption": bind(
            Path(str(FINAL) + ".compiler-feature-consumption.json")),
        "final_artifacts": finals, "retry_authorized": False,
        "owner_disposition_required": True,
        "execution_accounting": {"replacement_runs": 1,
            "new_WPLTO_card_runs": 0,
            "new_product_objects": len(objects),
            "final_product_links": 1,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Exactly one successor final-link attempt was made. No automatic "
            "retry, Completion, media, or device action follows a Red."),
    }))


def bind_existing_final_red() -> None:
    raise ProjectionError(
        "bind-link-red is retired after the tainted-final disposition")


def check() -> None:
    value = load(RECEIPT)
    require(value.get("status") == STATUS
            and value["final_artifacts"] == BASE.bound_family(FINAL)
            and value["compiler_feature_result"][
                "consumed_feature_count"] == 24
            and value["object_compilation"]["new_count"] == 66,
            "configurator-projection replacement receipt drift")
    print("configurator projection: CHECK PASS profile=24 "
          "combined=33 semantic=66 final=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "bind-preflight-red", "bind-link-red", "preflight", "link", "check"))
    action = parser.parse_args().action
    try:
        {"bind-preflight-red": record_preflight_harness_red,
         "bind-link-red": bind_existing_final_red,
         "preflight": record_preflight, "link": run_link,
         "check": check}[action]()
    except Exception as error:
        if action == "link":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print("configurator Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProjectionError, OSError, ValueError, KeyError, SyntaxError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"configurator projection: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
