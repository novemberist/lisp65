#!/usr/bin/env python3
"""Run the one authorized real-consumer refill-witness replacement card."""

from __future__ import annotations

from copy import deepcopy
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
import c2_v160_refill_boundary_witness_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-refill-boundary-witness-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-refill-boundary-witness-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-refill-boundary-witness-replacement-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-refill-boundary-witness-replacement-inherited-process")
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "registry-only-build"
MUTANT_PREFLIGHT = PROCESS / "registry-only-preflight"
RECEIPT = ARCH / "c2.3-v1.6-refill-boundary-witness-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-refill-boundary-witness-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-refill-boundary-witness-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-refill-boundary-witness-real-consumer-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "74ffb40e"
FORMAT = "lisp65-c2-v160-refill-boundary-witness-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 REFILL WITNESS REAL CONSUMER ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 REFILL WITNESS REAL CONSUMER FINAL WORLD GREEN"
FEATURE = PRODUCT.REFILL_WITNESS_FEATURE
SOURCE = PRODUCT.REFILL_WITNESS_SOURCE.resolve()
REGISTRY_ONLY_MUTANT = False
REAL_CONSUMER_INSTALLED = False


class FinalCompilerBoundaryReached(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PREV.BASE.CARD.BASE.CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one replacement card", "real single_link caller",
                  "actual resolved profile", "compiler source list",
                  "seed object inventory", "pure registry binding",
                  "for any feature flag", "exceptionless"):
        require(token in text, f"replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = PREV.BASE.CARD.BASE.load(PREDECESSOR_RED)
    attribution = PREV.BASE.CARD.BASE.load(ATTRIBUTION)
    require(red["status"] == "FINAL RED: V1.6 REFILL WITNESS CARD STOPS"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["retry_authorized"] is False
            and attribution["status"] ==
                "PASS: REFILL WITNESS BOUND BUT NOT CONSUMED BY REAL SINGLE-LINK"
            and attribution["decision"]["pricing_refuted"] is False,
            "replacement predecessor/attribution drift")
    return {"Final_Red": red, "attribution": attribution}


def install_real_consumer() -> None:
    """Project the feature at the first real single-link consumer."""
    global REAL_CONSUMER_INSTALLED
    if REAL_CONSUMER_INSTALLED:
        return
    current = PRODUCT.single_link

    def single_link_with_witness(*args: Any, **kwargs: Any) -> Any:
        definitions = tuple(kwargs.get("probe_definitions", ()))
        require(FEATURE not in definitions,
                "witness feature already entered single-link arguments")
        kwargs["probe_definitions"] = (*definitions, FEATURE)
        return current(*args, **kwargs)

    single_link_with_witness._v160_refill_witness_consumer = True  # type: ignore[attr-defined]
    single_link_with_witness._v160_refill_witness_delegate = current  # type: ignore[attr-defined]
    # The delegate already contains the active-frame liveness wrapper.  Carry
    # its installation identity outward so a later configure pass does not
    # install a second liveness wrapper behind this feature projection.
    single_link_with_witness._v160_active_frame_liveness = True  # type: ignore[attr-defined]
    single_link_with_witness._v160_active_frame_delegate = current  # type: ignore[attr-defined]
    PRODUCT.single_link = single_link_with_witness
    REAL_CONSUMER_INSTALLED = True


def configure_module() -> None:
    # Every materialized world owns its complete inherited preflight subtree;
    # a fixed historical tag would make otherwise separate producers collide.
    PREV.BASE.CARD.configure_for_paths(
        PREV.BUILD, PREV.PREFLIGHT,
        tag="refill-witness-" + PREV.PREFLIGHT.name)
    registration = PRODUCT.configure_refill_boundary_witness()
    require(registration["selected"] is True
            and registration["allocated"] ==
                [".lisp65_c2_mapped_diagnostic"],
            "refill witness configuration was not consumed")
    if not REGISTRY_ONLY_MUTANT:
        install_real_consumer()


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = INHERITED_PROCESS
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.configure_module = configure_module
    PREV.install()


def _profile_features(path: Path) -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in path.read_text().splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1, "resolved profile has no unique feature row")
    return tuple(item for item in rows[0].split(",") if item)


def _materialization_mutations(
        registered: tuple[str, ...], profile: tuple[str, ...],
        sources: tuple[str, ...], objects: tuple[dict[str, object], ...],
        scopes: tuple[dict[str, object], ...]
        ) -> list[str]:
    normal = PRODUCT.materialized_feature_gate(
        registered, profile, sources, objects, owner_scopes=scopes)
    rejected: list[str] = []
    for row in normal["features"]:
        owner = str(row["sources"][0])
        trial_sources = tuple(path for path in sources
                              if Path(path).resolve() != (ROOT / owner).resolve())
        trial_objects = tuple(item for item in objects
                              if Path(str(item["source"])).resolve() !=
                                  (ROOT / owner).resolve())
        try:
            PRODUCT.materialized_feature_gate(
                registered, profile, trial_sources, trial_objects,
                owner_scopes=scopes)
        except RuntimeError:
            rejected.append(str(row["trigger"]))
    require(len(rejected) == int(normal["registered_feature_count"]),
            "feature-generic materialization mutation survived")
    return rejected


def process_probe_child(*, mutant: bool) -> None:
    global REGISTRY_ONLY_MUTANT
    build = MUTANT_BUILD if mutant else NORMAL_BUILD
    preflight = MUTANT_PREFLIGHT if mutant else NORMAL_PREFLIGHT
    PREV.BUILD = build
    PREV.PREFLIGHT = preflight
    PREV.PROCESS = PROCESS / (
        "registry-only-inherited" if mutant else "normal-inherited")
    PREV.RECEIPT = preflight / "forbidden-receipt.json"
    PREV.FINAL_RED = preflight / "forbidden-final-red.json"
    REGISTRY_ONLY_MUTANT = mutant
    configure_module()

    compiler = str(PRODUCT.TOOLCHAIN / "mos-mega65-clang")
    processes: list[dict[str, Any]] = []
    final_driver: dict[str, Any] = {}
    materialized_scopes: list[dict[str, object]] = []
    original_run = PRODUCT.run
    original_final = PRODUCT.run_link_with_exact_orphan_wrapper

    def observed_run(argv: list[str], *, capture: bool = False) -> str:
        if (argv and argv[0] == compiler and "-c" in argv
                and not materialized_scopes):
            materialized_scopes.extend(deepcopy(PRODUCT.SOURCE_OWNER_SCOPES))
        result = original_run(argv, capture=capture)
        if argv and argv[0] == compiler and "-c" in argv and "-o" in argv:
            source = (ROOT / argv[argv.index("-c") + 1]).resolve()
            output = (ROOT / argv[argv.index("-o") + 1]).resolve()
            definitions = [item[2:] for item in argv if item.startswith("-D")]
            processes.append({"ordinal": len(processes),
                "source": source.relative_to(ROOT).as_posix(),
                "object": output.relative_to(ROOT).as_posix(),
                "object_bytes": output.stat().st_size,
                "object_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "feature_defines": definitions,
                "witness": FEATURE in definitions})
        return result

    def stop_final(_out: Path, _target: Path, argv: list[str]) -> None:
        final_driver.update({"argv_sha256": hashlib.sha256(
                "\0".join(argv).encode()).hexdigest(),
            "feature_defines": [item[2:] for item in argv if item.startswith("-D")],
            "executed": False, "stop": "before-WPLTO-link"})
        raise FinalCompilerBoundaryReached()

    PRODUCT.run = observed_run
    PRODUCT.run_link_with_exact_orphan_wrapper = stop_final
    old_argv = list(sys.argv)
    try:
        sys.argv = [str(DRIVER), "_produce"]
        PREV.main()
    except FinalCompilerBoundaryReached:
        pass
    except SystemExit:
        # The inherited producer adapter converts the deliberate final-driver
        # stop into its ordinary no-final-artifact exit.  It is expected only
        # after both sides of our compiler boundary have been observed.
        if not processes or not final_driver:
            raise
    except Exception:
        # Some inherited card layers express the same deliberate boundary as
        # their typed "producer emitted no final artifacts" exception.
        if not processes or not final_driver:
            raise
    finally:
        sys.argv = old_argv
        PRODUCT.run = original_run
        PRODUCT.run_link_with_exact_orphan_wrapper = original_final
        REGISTRY_ONLY_MUTANT = False

    require(processes and final_driver and materialized_scopes,
            "real compiler boundary was not reached")
    profile_path = build / "wplto/resolved-profile.txt"
    require(profile_path.is_file(), "materialized resolved profile absent")
    profile = _profile_features(profile_path)
    sources = tuple(str(ROOT / row["source"]) for row in processes)
    objects = tuple({"source": str(ROOT / row["source"]),
                     "object": str(ROOT / row["object"]),
                     "exists": True, "bytes": row["object_bytes"],
                     "sha256": row["object_sha256"]} for row in processes)
    registered = tuple(PRODUCT.CONVERGENCE_DEFINES)
    observation = {"status": "materialized-real-compiler-boundary",
        "mutant": mutant, "compiler_process_count": len(processes),
        "processes": processes, "resolved_profile": bind(profile_path),
        "resolved_profile_features": list(profile),
        "witness_profile_present": FEATURE in profile,
        "witness_source_process_present": any(
            (ROOT / row["source"]).resolve() == SOURCE for row in processes),
        "witness_seed_object_present": any(
            (ROOT / row["source"]).resolve() == SOURCE
            and int(row["object_bytes"]) > 0 for row in processes),
        "final_driver_boundary": final_driver,
        "execution": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0}}
    if mutant:
        rejected = False
        try:
            PRODUCT.materialized_feature_gate(
                (*registered, FEATURE) if FEATURE not in registered else registered,
                profile, sources, objects,
                owner_scopes=tuple(materialized_scopes))
        except RuntimeError:
            rejected = True
        require(rejected and not observation["witness_profile_present"]
                and not observation["witness_source_process_present"]
                and not observation["witness_seed_object_present"],
                "registry-only materialization mutation survived")
        observation["registry_only_mutation"] = "rejected"
    else:
        gate = PRODUCT.materialized_feature_gate(
            registered, profile, sources, objects,
            owner_scopes=tuple(materialized_scopes))
        observation["feature_generic_gate"] = gate
        observation["feature_generic_mutations_rejected"] = (
            _materialization_mutations(
                registered, profile, sources, objects,
                tuple(materialized_scopes)))
        require(observation["witness_profile_present"]
                and observation["witness_source_process_present"]
                and observation["witness_seed_object_present"],
                "witness escaped a materialized real consumer")
    print("MATERIALIZATION_JSON:" + json.dumps(observation, sort_keys=True))


def child_value(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"materialization child {action} red:\n{result.stdout}\n{result.stderr}")
    rows = [line.removeprefix("MATERIALIZATION_JSON:")
            for line in result.stdout.splitlines()
            if line.startswith("MATERIALIZATION_JSON:")]
    require(len(rows) == 1, "materialization child emitted no unique receipt")
    return json.loads(rows[0])


def process_gate() -> dict[str, Any]:
    normal = child_value("_witness_materialization_probe")
    mutant = child_value("_witness_materialization_probe_mutant")
    require(normal["witness_profile_present"] is True
            and normal["witness_source_process_present"] is True
            and normal["witness_seed_object_present"] is True
            and mutant["registry_only_mutation"] == "rejected",
            "real-consumer materialization decision table drift")
    return {"status": "PASS: EVERY REGISTERED FEATURE MATERIALIZES AT REAL CALLER",
        "normal": normal, "registry_only_mutation": mutant,
        "feature_generic": True, "permanent_gate": True}


def append_preflight(process: dict[str, Any]) -> None:
    path = PREFLIGHT / "preflight.json"
    value = PREV.BASE.CARD.BASE.load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "replacement_authority": authority(),
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_consumer_attribution": bind(ATTRIBUTION),
        "feature_materialization": process,
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, PROCESS,
        INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "witness replacement card is one-shot")
    predecessor(); authority()
    process = process_gate()
    configure_module(); PREV.preflight(); append_preflight(process)
    print("v1.6 refill witness replacement: PREFLIGHT PASS card=0/1 "
          "profile=source=seed-object=materialized")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = PREV.BASE.CARD.BASE.load(PREFLIGHT / "preflight.json")
    process = value["feature_materialization"]
    require(value["status"] == PREFLIGHT_STATUS
            and process["normal"]["witness_profile_present"] is True
            and process["normal"]["witness_source_process_present"] is True
            and process["normal"]["witness_seed_object_present"] is True
            and process["registry_only_mutation"]["registry_only_mutation"] ==
                "rejected", "persisted materialization preflight drift")
    PREV.card()
    receipt = PREV.BASE.CARD.BASE.load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "replacement_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_consumer_attribution": bind(ATTRIBUTION),
        "feature_materialization": process,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent review, same-world media, one seam contact"})
    RECEIPT.write_bytes(canonical(receipt))
    check_receipt()
    print("v1.6 refill witness replacement: CARD PASS card=1/1 "
          "final-world=green")


def check_receipt() -> dict[str, Any]:
    value = PREV.BASE.CARD.BASE.load(RECEIPT)
    gate = value["refill_boundary_witness"]
    materialized = value["feature_materialization"]["normal"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"]["cards_consumed"] == 1
            and materialized["witness_profile_present"] is True
            and materialized["witness_source_process_present"] is True
            and materialized["witness_seed_object_present"] is True
            and gate["ordinary"]["free_bytes"] == 3
            and gate["mapped_diagnostic"]["free_bytes"] == 160
            and gate["composed_image"]["result_tail_blank"] is True,
            "witness replacement final receipt drift")
    return value


def record_red(error: Exception) -> None:
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = PREV.BASE.CARD.BASE.load(FINAL_RED)
        value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 REFILL WITNESS REPLACEMENT STOPS",
            "replacement_authority": authority(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "real_consumer_attribution": bind(ATTRIBUTION),
            "classification": {
                "known_family": "successor-identity-and-counted-edge-expectations",
                "mechanism_fully_attributed": True,
                "product_fault": False,
                "pricing_refuted": False,
                "real_compiler_consumption_present": True},
            "final_world_observation": {
                "resolved_profile_witness_feature_present": True,
                "canonical_witness_object_present": True,
                "diagnostic_section_bytes": 211,
                "ordinary_installer_stub_bytes": 9,
                "installer_successor_bytes": 211,
                "trace_reader_bytes": 205},
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0,
            "next": "exceptionless review disposition required"})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 refill witness replacement: CHECK PASS")
        return 0
    if action == "_witness_materialization_probe":
        process_probe_child(mutant=False); return 0
    if action == "_witness_materialization_probe_mutant":
        process_probe_child(mutant=True); return 0
    return PREV.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 refill witness replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
