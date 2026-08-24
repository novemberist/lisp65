#!/usr/bin/env python3
"""Run the single live-stack Hybrid conversion card."""

from __future__ import annotations

import argparse
import hashlib
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
import c2_v160_abort_driver_relocation as R1_GATE  # noqa: E402
import c2_v160_input_fidelity_graph_rebind_replacement_card as GRAPH  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL_WORLD  # noqa: E402
import c2_v160_input_service_hybrid_projection_fold_contract_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-card-r4"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-live-stack-preflight-r4"
NORMAL_BUILD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-process-normal-r5"
NORMAL_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-live-stack-process-normal-preflight-r5"
MUTANT_BUILD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-process-mutant-r5"
MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-live-stack-process-mutant-preflight-r5"
RECEIPT = ARCH / "c2.3-v1.6-hybrid-live-stack-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-hybrid-live-stack-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-contract-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-hybrid-compiler-process-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ac231159"
FORMAT = "lisp65-c2-v160-hybrid-live-stack-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID LIVE STACK ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 HYBRID LIVE STACK FINAL WORLD GREEN"
CAPTURE = "LISP65_V160_INPUT_CAPTURE"
HYBRID = "LISP65_V160_INPUT_HYBRID"
CONSUMER = "src/optional/c2_kernal_input_consumer.s"


class CardError(RuntimeError): pass
class FinalCompilerBoundaryReached(BaseException): pass


def require(value: bool, message: str) -> None:
    if not value: raise CardError(message)


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
    for token in ("exactly one conversion card", "stack is consumed, never snapshotted",
                  "at invocation time", "process-argv witness", "final-world guard"):
        require(token in text, f"live-stack authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED); attribution = load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: V1.6 HYBRID FOLD CONTRACT REPLACEMENT STOPS"
            and red["retry_authorized"] is False
            and attribution["status"] ==
                "ATTRIBUTED: GRAPH REBIND REPLACED HYBRID CONFIGURE STACK"
            and attribution["exact_projection_writer"]["function"] ==
                "c2_v160_input_fidelity_graph_rebind_replacement_card.configure_module"
            and attribution["shared_projection_question"]
                ["shared_mechanism_below_fold"] is True,
            "live-stack predecessor/attribution drift")
    return {"Final_Red": red, "attribution": attribution}


def set_paths(build: Path, preflight: Path, *, tag: str) -> None:
    PREV.BUILD = build; PREV.PREFLIGHT = preflight
    PREV.QUALIFICATION = preflight.parent / (tag + "-qualification")
    PREV.ABI_REPORT = PREV.QUALIFICATION / "c2-asm-leaf-abi.json"
    PREV.REAL_PROBE_BUILD = preflight.parent / (tag + "-real-probe")
    PREV.REAL_PROBE_PREFLIGHT = preflight.parent / (tag + "-real-preflight")
    PREV.HYBRID_PROBE_BUILD = preflight.parent / (tag + "-profile-probe")
    PREV.HYBRID_PROBE_PREFLIGHT = preflight.parent / (tag + "-profile-preflight")
    PREV.FOLD_BUILD = preflight.parent / (tag + "-fold-probe")
    PREV.FOLD_PREFLIGHT = preflight.parent / (tag + "-fold-preflight")
    PREV.FOLD_MUTANT_BUILD = preflight.parent / (tag + "-fold-mutant")
    PREV.FOLD_MUTANT_PREFLIGHT = preflight.parent / (tag + "-fold-mutant-preflight")
    PREV.CONTRACT_BUILD = preflight.parent / (tag + "-contract-probe")
    PREV.CONTRACT_PREFLIGHT = preflight.parent / (tag + "-contract-preflight")
    PREV.CONTRACT_MUTANT_BUILD = preflight.parent / (tag + "-contract-mutant")
    PREV.CONTRACT_MUTANT_PREFLIGHT = preflight.parent / (tag + "-contract-mutant-preflight")
    PREV.RECEIPT = RECEIPT if build == BUILD else preflight / "forbidden-receipt.json"
    PREV.FINAL_RED = FINAL_RED if build == BUILD else preflight / "forbidden-final-red.json"
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS


def configure_module() -> None:
    set_paths(BUILD, PREFLIGHT, tag="live-stack-card-r4")
    PREV.configure_module()


def process_probe_child(*, mutant: bool) -> None:
    build = MUTANT_BUILD if mutant else NORMAL_BUILD
    preflight = MUTANT_PREFLIGHT if mutant else NORMAL_PREFLIGHT
    set_paths(build, preflight,
              tag="live-stack-mutant-r5" if mutant else "live-stack-normal-r5")
    snapshot_mutant_delegate = GRAPH.PREV.PREV.configure_stack
    GRAPH.SNAPSHOT_STACK_MUTANT = mutant
    GRAPH.SNAPSHOT_STACK_MUTANT_DELEGATE = (
        snapshot_mutant_delegate if mutant else None)
    PREV.configure_module()
    compiler = str(PRODUCT.TOOLCHAIN / "mos-mega65-clang")
    processes: list[dict[str, Any]] = []
    final_driver: dict[str, Any] = {}
    original_run = PRODUCT.run
    original_final = PRODUCT.run_link_with_exact_orphan_wrapper

    def observed_run(argv: list[str], *, capture: bool = False) -> str:
        if argv and argv[0] == compiler and "-c" in argv:
            source = argv[argv.index("-c") + 1]
            definitions = [item[2:] for item in argv if item.startswith("-D")]
            processes.append({"ordinal": len(processes), "argv": argv,
                "argv_sha256": hashlib.sha256("\0".join(argv).encode()).hexdigest(),
                "source": source, "feature_defines": definitions,
                "capture": CAPTURE in definitions, "hybrid": HYBRID in definitions})
        return original_run(argv, capture=capture)

    def stop_final(_out: Path, _target: Path, argv: list[str]) -> None:
        final_driver.update({"argv": argv,
            "argv_sha256": hashlib.sha256("\0".join(argv).encode()).hexdigest(),
            "executed": False, "stop": "before-WPLTO-link"})
        raise FinalCompilerBoundaryReached()

    PRODUCT.run = observed_run
    PRODUCT.run_link_with_exact_orphan_wrapper = stop_final
    old_argv = list(sys.argv)
    try:
        sys.argv = [str(Path(PREV.__file__).resolve()), "_produce"]
        PREV.main()
    except FinalCompilerBoundaryReached:
        pass
    finally:
        sys.argv = old_argv
        PRODUCT.run = original_run
        PRODUCT.run_link_with_exact_orphan_wrapper = original_final
        GRAPH.SNAPSHOT_STACK_MUTANT = False
        GRAPH.SNAPSHOT_STACK_MUTANT_DELEGATE = None
    require(processes and final_driver, "process-argv witness missed compiler boundary")
    sources = [row["source"] for row in processes]
    value = {"status": "passed-real-process-argv-witness",
        "mutant": mutant, "compiler_process_count": len(processes),
        "processes": processes, "source_order": sources,
        "all_capture": all(row["capture"] for row in processes),
        "all_hybrid": all(row["hybrid"] for row in processes),
        "consumer_source_process_present": CONSUMER in sources,
        "final_driver_boundary": final_driver,
        "execution": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0}}
    if mutant:
        require(value["all_capture"] and not value["all_hybrid"]
                and not value["consumer_source_process_present"],
                "snapshot mutation did not reproduce Capture-only process world")
    else:
        require(value["all_capture"] and value["all_hybrid"]
                and value["consumer_source_process_present"],
                "live stack did not reach every real compiler process")
    print("PROCESS_ARGV_JSON:" + json.dumps(value, sort_keys=True))


def child_value(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"process-argv child {action} red:\n{result.stdout}\n{result.stderr}")
    rows = [line.removeprefix("PROCESS_ARGV_JSON:")
            for line in result.stdout.splitlines()
            if line.startswith("PROCESS_ARGV_JSON:")]
    require(len(rows) == 1, f"process-argv child {action} emitted no unique receipt")
    return json.loads(rows[0])


def process_gate() -> dict[str, Any]:
    normal = child_value("_process_probe")
    mutant = child_value("_process_probe_mutant")
    require(normal["compiler_process_count"] == 68
            and mutant["compiler_process_count"] == 67
            and normal["all_hybrid"] is True
            and mutant["all_hybrid"] is False
            and normal["consumer_source_process_present"] is True
            and mutant["consumer_source_process_present"] is False,
            "process-argv normal/mutant decision table drift")
    return {"status": "PASS: LIVE STACK REACHES REAL COMPILER PROCESSES",
        "normal": normal, "snapshot_mutation": mutant,
        "configured_feature_count_delta": 1,
        "configured_source_count_delta": 1,
        "permanent_gate": True}


def preflight() -> None:
    predecessor(); auth = authority()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, NORMAL_BUILD,
        NORMAL_PREFLIGHT, MUTANT_BUILD, MUTANT_PREFLIGHT, RECEIPT, FINAL_RED)),
        "live-stack conversion is one-shot")
    process = process_gate()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "live_stack_authority": auth, "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "compiler_process_attribution": bind(ATTRIBUTION),
        "real_process_argv_witness": process,
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid live stack: PREFLIGHT PASS card=0/1 "
          "processes=68 mutant=67")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    witness = value["real_process_argv_witness"]
    require(value["status"] == PREFLIGHT_STATUS
            and witness["normal"]["all_hybrid"] is True
            and witness["normal"]["consumer_source_process_present"] is True
            and witness["snapshot_mutation"]["all_hybrid"] is False,
            "persisted live-stack process preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "live_stack_authority": auth, "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "compiler_process_attribution": bind(ATTRIBUTION),
        "real_process_argv_witness": witness,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent final-world review before media"})
    PREV.PREV.PREV.validate_final_claims(receipt)
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid live stack: CARD PASS card=1/1 "
          "final-world=green review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        final_claims = (FINAL_WORLD.derive(PRODUCT_ELF)
                        if PRODUCT_ELF.is_file() else None)
        geometry = None
        if PRODUCT_ELF.is_file():
            truth = FINAL_WORLD.ElfTruth.read(PRODUCT_ELF,
                llvm_readobj=FINAL_WORLD.READOBJ, include_section_data=True)
            sections = {row.name: row for row in truth.sections}
            allocated_rows = sorted((max(R1_GATE.E000_START, row.address),
                min(R1_GATE.E000_END, row.address + row.bytes))
                for row in truth.sections
                if row.bytes > 0 and "SHF_ALLOC" in set(row.flags)
                and row.address < R1_GATE.E000_END
                and row.address + row.bytes > R1_GATE.E000_START)
            allocated: list[tuple[int, int]] = []
            for start, end in allocated_rows:
                if not allocated or start > allocated[-1][1]:
                    allocated.append((start, end))
                else:
                    allocated[-1] = (allocated[-1][0],
                                     max(allocated[-1][1], end))
            free = R1_GATE.E000_END - R1_GATE.E000_START - sum(
                end - start for start, end in allocated)
            geometry = {"capture_bytes": sum(sections[name].bytes for name in (
                    ".lisp65_c2_kernal_window.input_capture_main",
                    ".lisp65_c2_kernal_window.input_capture_helper")),
                "hybrid_consumer_bytes": sections[
                    ".lisp65_c2_kernal_window.input_consumer"].bytes,
                "post_hybrid_free_bytes": free, "reserve_floor_bytes": 54,
                "surplus_over_floor_bytes": free - 54,
                "rejected_stored_world": {"free_bytes": 136,
                    "surplus_over_floor_bytes": 82}}
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 HYBRID LIVE STACK CONVERSION STOPS",
            "live_stack_authority": authority(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "compiler_process_attribution": bind(ATTRIBUTION),
            "final_world_claims": final_claims,
            "final_geometry_attribution": geometry,
            "classification": {
                "mechanism_fully_attributed": True,
                "product_claims_inherited": False,
                "real_compiler_consumption_still_absent": False,
                "wrapper_order_repair_reached_preflight": True,
                "known_family": "stored capture-only reserve equality applied to Hybrid final world",
            },
            "final_world_observation": {
                "canonical_consumer_object_present": final_claims is not None,
                "capture_object_present": final_claims is not None,
                "consumer_section_present": final_claims is not None,
                "resolved_profile_hybrid_feature_present": final_claims is not None,
            },
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0,
            "next": "known-family replacement requires a fresh one-shot card"})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe",
        "_process_probe_mutant", "_contract_probe", "_contract_probe_mutant",
        "_fold_probe", "_fold_probe_mutant", "_order_probe",
        "_order_probe_mutant", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce",
        "_scope", "_accept", "_r1_arm", "_owner_graph", "_default_probe",
        "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid live stack:",
        "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists()
        else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists()
        else "CHECK LOCKED")
    elif action == "_process_probe": process_probe_child(mutant=False)
    elif action == "_process_probe_mutant": process_probe_child(mutant=True)
    elif action == "_order_probe_mutant":
        # Do not preinstall the normal outer wrapper: the inherited mutation
        # must construct the late world itself or the test would be masked by
        # configuration performed by this successor's dispatcher.
        set_paths(BUILD, PREFLIGHT, tag="live-stack-card-r4")
        PREV.main()
    else:
        configure_module(); PREV.main()
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"live-stack Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 hybrid live stack: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
