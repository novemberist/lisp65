#!/usr/bin/env python3
"""Attribute v1.6 Hybrid projection down to real compiler processes."""

from __future__ import annotations

import argparse
import functools
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_input_service_hybrid_projection_fold_contract_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-contract-card-final-red.json"
REPORT = ARCH / "c2.3-v1.6-hybrid-compiler-process-attribution.json"
BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-r4"
PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-preflight-r4"
QUALIFICATION = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-qualification-r4"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-real-probe-r4"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-real-preflight-r4"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-profile-probe-r4"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-profile-preflight-r4"
FOLD_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-fold-probe-r4"
FOLD_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-fold-preflight-r4"
FOLD_MUTANT_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-fold-mutant-r4"
FOLD_MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-fold-mutant-preflight-r4"
CONTRACT_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-contract-r4"
CONTRACT_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-contract-preflight-r4"
CONTRACT_MUTANT_BUILD = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-contract-mutant-r4"
CONTRACT_MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-compiler-process-attribution-driver-contract-mutant-preflight-r4"
FOLD_PREFLIGHT_EVIDENCE = ROOT / (
    "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-"
    "preflight-r3/preflight.json")
AUTHORIZATION = "da2e34a2"
FORMAT = "lisp65-c2-v160-hybrid-compiler-process-attribution-v1"
CAPTURE = "LISP65_V160_INPUT_CAPTURE"
HYBRID = "LISP65_V160_INPUT_HYBRID"
CONSUMER = "src/optional/c2_kernal_input_consumer.s"


class AttributionError(RuntimeError): pass
class FinalCompilerBoundaryReached(BaseException): pass


def require(value: bool, message: str) -> None:
    if not value: raise AttributionError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("real compiler process invocation itself", "argv",
                  "feature defines", "concrete source list",
                  "share one projection mechanism", "no retry", "no successor"):
        require(token in text, f"compiler-process attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_red() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red["status"] ==
                "FINAL RED: V1.6 HYBRID FOLD CONTRACT REPLACEMENT STOPS"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and red["final_world_observation"] == {
                "canonical_consumer_object_present": False,
                "capture_object_present": True,
                "consumer_section_present": False,
                "resolved_profile_hybrid_feature_present": False},
            "frozen fold-contract Red drift")
    profile = ROOT / red["artifacts"]["resolved_profile"]["path"]
    feature_row = next(line for line in profile.read_text(encoding="utf-8").splitlines()
                       if line.startswith("feature_defines="))
    features = feature_row.removeprefix("feature_defines=").split(",")
    require(CAPTURE in features and HYBRID not in features,
            "frozen final compiler profile is not Capture-only")
    return {"Final_Red": bind(FINAL_RED), "resolved_profile": bind(profile),
            "features": features, "capture": True, "hybrid": False}


def accepted_fold_world() -> dict[str, Any]:
    value = load(FOLD_PREFLIGHT_EVIDENCE)
    fold = value["real_single_link_feature_fold"]
    require(fold["status"] == "passed-real-single-link-feature-fold"
            and fold["capture_consumed"] is True
            and fold["hybrid_consumed"] is True
            and fold["consumer_source_consumed"] is True
            and fold["early_return_mutation_rejected"] is True,
            "accepted fold preflight evidence drift")
    return {"receipt": bind(FOLD_PREFLIGHT_EVIDENCE),
            "projected_definitions": fold["projected_definitions"],
            "capture": True, "hybrid": True,
            "consumer_source_selected": True}


def caller_name() -> str:
    ignored = {"wrapped_project", "wrapped_sources", "wrapped_compile"}
    for frame in inspect.stack()[2:]:
        if frame.function not in ignored:
            return f"{Path(frame.filename).name}:{frame.function}"
    return "unknown"


def process_probe() -> dict[str, Any]:
    require(not BUILD.exists() and not PREFLIGHT.exists(),
            "compiler-process attribution is one-shot")
    CARD.BUILD = BUILD; CARD.PREFLIGHT = PREFLIGHT
    CARD.QUALIFICATION = QUALIFICATION
    CARD.ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
    CARD.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    CARD.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    CARD.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    CARD.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    CARD.FOLD_BUILD = FOLD_BUILD; CARD.FOLD_PREFLIGHT = FOLD_PREFLIGHT
    CARD.FOLD_MUTANT_BUILD = FOLD_MUTANT_BUILD
    CARD.FOLD_MUTANT_PREFLIGHT = FOLD_MUTANT_PREFLIGHT
    CARD.CONTRACT_BUILD = CONTRACT_BUILD
    CARD.CONTRACT_PREFLIGHT = CONTRACT_PREFLIGHT
    CARD.CONTRACT_MUTANT_BUILD = CONTRACT_MUTANT_BUILD
    CARD.CONTRACT_MUTANT_PREFLIGHT = CONTRACT_MUTANT_PREFLIGHT
    CARD.RECEIPT = BUILD / "forbidden-green-receipt.json"
    CARD.FINAL_RED = BUILD / "forbidden-final-red.json"
    CARD.configure_module()

    projector_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    compile_rows: list[dict[str, Any]] = []
    process_rows: list[dict[str, Any]] = []
    stack_assignments: list[dict[str, Any]] = []
    stack_invocations: list[dict[str, Any]] = []
    hybrid_configurations: list[dict[str, Any]] = []
    final_invocation: dict[str, Any] = {}
    original_project = PRODUCT.input_capture_compile_profile
    original_sources = PRODUCT.source_list
    original_compile = PRODUCT.compile_link
    original_run = PRODUCT.run
    original_final = PRODUCT.run_link_with_exact_orphan_wrapper
    original_hybrid_configure = PRODUCT.configure_input_hybrid
    original_reopen_class = REOPEN.__class__
    compiler = str(PRODUCT.TOOLCHAIN / "mos-mega65-clang")

    class TracedReopenModule(original_reopen_class):  # type: ignore[misc]
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "configure_stack" and callable(value):
                assigned = value
                row = {"ordinal": len(stack_assignments),
                    "writer": caller_name(),
                    "assigned_qualname": getattr(assigned, "__qualname__", repr(assigned)),
                    "hybrid_marker": bool(getattr(assigned, "_v160_input_hybrid", False)),
                    "before_install_marker": bool(getattr(
                        assigned, "_v160_hybrid_before_install", False))}
                stack_assignments.append(row)

                @functools.wraps(assigned)
                def observed(*args: Any, **kwargs: Any) -> Any:
                    before = {"capture": PRODUCT.INPUT_CAPTURE_ENABLED,
                              "hybrid": PRODUCT.INPUT_HYBRID_ENABLED}
                    result = assigned(*args, **kwargs)
                    stack_invocations.append({"ordinal": len(stack_invocations),
                        "assignment_ordinal": row["ordinal"],
                        "assigned_qualname": row["assigned_qualname"],
                        "before": before,
                        "after": {"capture": PRODUCT.INPUT_CAPTURE_ENABLED,
                                  "hybrid": PRODUCT.INPUT_HYBRID_ENABLED}})
                    return result
                value = observed
            super().__setattr__(name, value)

    def wrapped_hybrid_configure() -> dict[str, object]:
        before = {"enabled": PRODUCT.INPUT_HYBRID_ENABLED,
                  "in_global_definitions": HYBRID in PRODUCT.CONVERGENCE_DEFINES}
        result = original_hybrid_configure()
        hybrid_configurations.append({"ordinal": len(hybrid_configurations),
            "caller": caller_name(), "before": before,
            "after": {"enabled": PRODUCT.INPUT_HYBRID_ENABLED,
                      "in_global_definitions": HYBRID in PRODUCT.CONVERGENCE_DEFINES},
            "result": result})
        return result

    def wrapped_project(definitions: tuple[str, ...]) -> tuple[str, ...]:
        result = original_project(definitions)
        projector_rows.append({"ordinal": len(projector_rows),
            "caller": caller_name(), "input": list(definitions),
            "output": list(result), "capture_enabled": PRODUCT.INPUT_CAPTURE_ENABLED,
            "hybrid_enabled": PRODUCT.INPUT_HYBRID_ENABLED,
            "capture_output": CAPTURE in result, "hybrid_output": HYBRID in result})
        return result

    def wrapped_sources(definitions: tuple[str, ...] = ()) -> list[str]:
        result = original_sources(definitions)
        source_rows.append({"ordinal": len(source_rows), "caller": caller_name(),
            "definitions": list(definitions),
            "sources": [Path(item).relative_to(ROOT).as_posix() for item in result],
            "consumer_present": CONSUMER in {
                Path(item).relative_to(ROOT).as_posix() for item in result}})
        return result

    def wrapped_compile(out: Path, name: str, headers: list[Path],
                        artifacts: dict[str, object], **kwargs: Any) -> Path:
        definitions = tuple(kwargs.get("probe_definitions", ()))
        compile_rows.append({"ordinal": len(compile_rows), "name": name,
            "probe_definitions": list(definitions),
            "capture": CAPTURE in definitions, "hybrid": HYBRID in definitions})
        return original_compile(out, name, headers, artifacts, **kwargs)

    def wrapped_run(argv: list[str], *, capture: bool = False) -> str:
        if argv and argv[0] == compiler and "-c" in argv:
            source = argv[argv.index("-c") + 1]
            definitions = [item[2:] for item in argv if item.startswith("-D")]
            process_rows.append({"ordinal": len(process_rows),
                "kind": "translation-unit-compiler-process",
                "argv": argv, "argv_sha256": hashlib.sha256(
                    "\0".join(argv).encode()).hexdigest(),
                "source": source, "feature_defines": definitions,
                "capture": CAPTURE in definitions, "hybrid": HYBRID in definitions})
        return original_run(argv, capture=capture)

    def stop_final(_out: Path, _target: Path, argv: list[str]) -> None:
        definitions = [item[2:] for item in argv if item.startswith("-D")]
        final_invocation.update({"kind": "whole-program-compiler-driver-boundary",
            "argv": argv, "argv_sha256": hashlib.sha256(
                "\0".join(argv).encode()).hexdigest(),
            "feature_defines": definitions,
            "capture": CAPTURE in definitions, "hybrid": HYBRID in definitions,
            "executed": False,
            "stop_reason": "attribution stops before WPLTO/product link"})
        raise FinalCompilerBoundaryReached()

    PRODUCT.input_capture_compile_profile = wrapped_project
    PRODUCT.source_list = wrapped_sources
    PRODUCT.compile_link = wrapped_compile
    PRODUCT.run = wrapped_run
    PRODUCT.run_link_with_exact_orphan_wrapper = stop_final
    PRODUCT.configure_input_hybrid = wrapped_hybrid_configure
    REOPEN.__class__ = TracedReopenModule
    old_argv = list(sys.argv)
    try:
        # Follow the exact nested driver dispatch used by the card's child
        # process.  The direct producer call is deliberately not equivalent:
        # each wrapper's ``main`` re-applies its own configuration before the
        # deepest ``_produce`` consumer is reached.
        sys.argv = [str(Path(CARD.__file__).resolve()), "_produce"]
        CARD.main()
    except FinalCompilerBoundaryReached:
        pass
    finally:
        sys.argv = old_argv
        PRODUCT.input_capture_compile_profile = original_project
        PRODUCT.source_list = original_sources
        PRODUCT.compile_link = original_compile
        PRODUCT.run = original_run
        PRODUCT.run_link_with_exact_orphan_wrapper = original_final
        PRODUCT.configure_input_hybrid = original_hybrid_configure
        REOPEN.__class__ = original_reopen_class

    require(final_invocation, "producer did not reach final compiler boundary")
    require(process_rows, "producer launched no real translation-unit compiler process")
    require(not (BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf").exists(),
            "attribution unexpectedly linked a final ELF")
    source_order = [row["source"] for row in process_rows]
    require(len(source_order) == len(set(source_order)),
            "compiler process source order is not unique")
    return {"driver_choreography":
            "projection-fold-contract-card.main -> inherited mains -> _produce",
        "projector_calls": projector_rows, "source_list_calls": source_rows,
        "compile_link_calls": compile_rows,
        "configure_stack_assignments": stack_assignments,
        "configure_stack_invocations": stack_invocations,
        "hybrid_configurations": hybrid_configurations,
        "translation_unit_processes": process_rows,
        "process_source_order": source_order,
        "process_source_count": len(source_order),
        "final_driver_boundary": final_invocation,
        "execution": {"translation_unit_compiler_processes": len(process_rows),
            "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0}}


def first_loss(probe: dict[str, Any]) -> dict[str, Any]:
    projector = probe["projector_calls"][-1]
    compiles = probe["compile_link_calls"]
    processes = probe["translation_unit_processes"]
    require(projector["capture_output"], "actual projector omitted Capture")
    require(compiles, "compile_link boundary absent")
    first_compile = compiles[0]
    first_process = processes[0]
    if not projector["hybrid_output"]:
        boundary = "configured fold world -> actual driver projector"
        writer = "nested configure_stack replacement/activation order"
    elif not first_compile["hybrid"]:
        boundary = "projector-output -> compile_link(probe_definitions)"
        writer = "single_link caller/compile_link argument projection"
    elif not first_process["hybrid"]:
        boundary = "compile_link(probe_definitions) -> compiler argv"
        writer = "compile_link scoped-definition/flag projection"
    else:
        boundary = "no loss in probed compiler process"
        writer = "frozen-card process configuration differs from attribution process"
    last_assignment = probe["configure_stack_assignments"][-1]
    last_invocation = probe["configure_stack_invocations"][-1]
    exact_graph_replacement = (
        boundary == "configured fold world -> actual driver projector"
        and last_assignment["writer"] ==
            "c2_v160_input_fidelity_graph_rebind_replacement_card.py:configure_module"
        and last_assignment["assigned_qualname"] == "graph_configure_stack"
        and last_assignment["hybrid_marker"] is False
        and last_invocation["after"] == {"capture": True, "hybrid": False}
        and probe["hybrid_configurations"] == [])
    require(exact_graph_replacement,
            "exact graph-rebind projection writer was not uniquely reproduced")
    return {"boundary": boundary, "writer_space": writer,
        "projector_output": projector,
        "compile_link_input": first_compile,
        "first_real_compiler_process": first_process,
        "consumer_source_process_present": CONSUMER in probe["process_source_order"],
        "last_configure_stack_assignment": last_assignment,
        "last_configure_stack_invocation": last_invocation,
        "hybrid_configuration_calls": probe["hybrid_configurations"],
        "exact_writer_reproduced": True}


def derive() -> dict[str, Any]:
    auth = authority(); red = frozen_red(); fold = accepted_fold_world()
    probe = process_probe()
    loss = first_loss(probe)
    common = loss["boundary"] in {
        "configured fold world -> actual driver projector",
        "projector-output -> compile_link(probe_definitions)"}
    process_features = probe["translation_unit_processes"][0]["feature_defines"]
    return {"format": FORMAT, "recorded_on": "2026-08-20",
        "status": "ATTRIBUTED: GRAPH REBIND REPLACED HYBRID CONFIGURE STACK",
        "authority": auth, "frozen_red_world": red,
        "accepted_fold_world": fold,
        "actual_process_probe": probe, "first_loss": loss,
        "fold_to_process_diff": {
            "fold_only": sorted(set(fold["projected_definitions"])
                                - set(process_features)),
            "process_only": sorted(set(process_features)
                                   - set(fold["projected_definitions"])),
            "decisive_missing_feature": HYBRID,
            "compiler_process_count": probe["process_source_count"],
            "consumer_source_process_present":
                loss["consumer_source_process_present"]},
        "exact_projection_writer": {
            "function":
                "c2_v160_input_fidelity_graph_rebind_replacement_card.configure_module",
            "written_value": "REOPEN.configure_stack = graph_configure_stack",
            "replaced_value": "hybrid-marked configure_stack decorator",
            "stored_base": "ORIGINAL_STACK captured before Hybrid existed",
            "process_effect": ("graph_configure_stack activates Capture but never "
                               "calls configure_input_hybrid"),
            "downstream_effect": ("input_capture_compile_profile correctly folds "
                                  "the active set, which is Capture-only; every real "
                                  "TU compiler argv therefore omits Hybrid")},
        "shared_projection_question": {
            "shared_mechanism_below_fold": common,
            "answer": ("yes: graph_configure_stack is the single shared lower "
                       "projection boundary; convert its replacement into an "
                       "additive decorator once, then all lower consumers inherit "
                       "the complete feature world" if common else
                       "the probed process retains Hybrid; compare process setup worlds")},
        "decision": {"successor_authorized": False,
            "media_authorized": False, "device_contacts": 0},
        "claim_limit": ("Host-only process attribution. Real per-TU compiler "
            "processes ran; the final driver was captured and stopped before "
            "WPLTO/link. No successor, media, or device contact is authorized.")}


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT
            and value.get("status") ==
                "ATTRIBUTED: GRAPH REBIND REPLACED HYBRID CONFIGURE STACK",
            "compiler-process attribution status drift")
    probe = value["actual_process_probe"]
    require(probe["execution"]["WPLTO_runs"] == 0
            and probe["execution"]["product_links"] == 0
            and probe["translation_unit_processes"]
            and probe["final_driver_boundary"]["executed"] is False
            and value["first_loss"]["exact_writer_reproduced"] is True
            and value["fold_to_process_diff"]["decisive_missing_feature"] == HYBRID
            and value["exact_projection_writer"]["function"] ==
                "c2_v160_input_fidelity_graph_rebind_replacement_card.configure_module"
            and value["shared_projection_question"]
                ["shared_mechanism_below_fold"] is True
            and value["decision"] == {"successor_authorized": False,
                "media_authorized": False, "device_contacts": 0},
            "compiler-process execution/decision drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("report", "check", "selftest"))
    action = parser.parse_args().action
    if action == "report":
        value = derive(); validate(value); REPORT.write_bytes(canonical(value))
        print("v1.6 hybrid compiler process: REPORT WRITTEN "
              f"boundary={value['first_loss']['boundary']}")
    else:
        value = load(REPORT); validate(value)
        print("v1.6 hybrid compiler process: " + action.upper() + " PASS")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 hybrid compiler process: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
