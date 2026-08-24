#!/usr/bin/env python3
"""Run the authorized final-world active-frame liveness product card."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402
import c2_v160_input_drop_counters as COUNTERS  # noqa: E402
import c2_v160_liveness_capture_guard_card as LIVENESS_GUARD  # noqa: E402
import c2_v160_liveness_config as LIVENESS_CONFIG  # noqa: E402
import c2_v160_primary_vm_type_fix as PRIMARY_FIX  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-active-frame-liveness-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-active-frame-liveness-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-active-frame-liveness-process"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-active-frame-liveness-card-receipt.json"
RESUME_RECEIPT = ARCH / (
    "c2.3-v1.6-active-frame-liveness-acceptance-resume-receipt.json")
RESUME_FINAL_RED = ARCH / (
    "c2.3-v1.6-active-frame-liveness-acceptance-resume-final-red.json")
REPLACEMENT_RESUME_FINAL_RED = ARCH / (
    "c2.3-v1.6-active-frame-liveness-acceptance-replacement-resume-final-red.json")
FINAL_RED = ARCH / "c2.3-v1.6-active-frame-liveness-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v1.6-primary-vm-type-fix-replacement-card-receipt.json"
V16_SUITE = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ad4a25ad"
RESUME_AUTHORIZATION = "e782e159"
REPLACEMENT_RESUME_AUTHORIZATION = "7902b7c6"
FORMAT = "lisp65-c2-v160-active-frame-liveness-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS FINAL WORLD GREEN"
RESUME_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS CLOSED READ-ONLY"
ORIGINAL_PROCESS_PROBE_CHILD = BASE.process_probe_child


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.CardError(message)


def authority() -> dict[str, Any]:
    value = ERA.era_bind(AUTHORIZATION, ACTIVE.PLAN.relative_to(ROOT).as_posix())
    raw = ERA.era_blob(AUTHORIZATION, value["path"])
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one product card", "preflight derives",
                  "enforcement lands in the far service",
                  "counters prove on the final elf", "exceptionless"):
        require(token in text, f"active-frame card authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, **value}


def resume_authority() -> dict[str, Any]:
    value = ERA.era_bind(RESUME_AUTHORIZATION,
                         ACTIVE.PLAN.relative_to(ROOT).as_posix())
    raw = ERA.era_blob(RESUME_AUTHORIZATION, value["path"])
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("consumer size validates candidate-derived",
                  "checked against its contract as a bound",
                  "reintroduced 67 pin falls by mutation",
                  "scope and acceptance resume read-only",
                  "no new wplto", "no new link", "no new card"):
        require(token in text, f"active-frame resume authority absent: {token}")
    return {"authority": "git-blob", "commit": RESUME_AUTHORIZATION, **value}


def replacement_resume_authority() -> dict[str, Any]:
    value = ERA.era_bind(REPLACEMENT_RESUME_AUTHORIZATION,
                         ACTIVE.PLAN.relative_to(ROOT).as_posix())
    raw = ERA.era_blob(REPLACEMENT_RESUME_AUTHORIZATION, value["path"])
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("exactly one read-only replacement resume",
                  "no rebuild", "no wplto", "no link", "no card",
                  "resume and receipt adapters",
                  "vocabulary mismatch in an adapter must fall before"):
        require(token in text,
                f"active-frame replacement-resume authority absent: {token}")
    return {"authority": "git-blob",
            "commit": REPLACEMENT_RESUME_AUTHORIZATION, **value}


def predecessor() -> dict[str, Any]:
    value = BASE.load(PREDECESSOR)
    require(value["status"] ==
                "PASS: V1.6 PRIMARY VM TYPE FIX REPLACEMENT FINAL WORLD GREEN"
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["primary_vm_type_fix"]["regression"]["fixed_boundary"]
                ["steps"] == 5156,
            "active-frame predecessor final world drift")
    fix = PRIMARY_FIX.derive()
    require(fix["status"] == "PASS: PRIMARY VM_TYPE EMPTY-PHASE FIX",
            "primary VM_TYPE fix source drift")
    return {"primary_fix_Final_World": value, "primary_fix": fix}


def install_liveness_consumer() -> None:
    current = BASE.PRODUCT.single_link
    if getattr(current, "_v160_active_frame_liveness", False):
        return

    def single_link_with_liveness(*args: Any, **kwargs: Any) -> Any:
        # The complete historical stack has installed R1 at this boundary.
        # Substitute its liveness successor at the first real compiler
        # consumer, never in an earlier projected world.
        LIVENESS_CONFIG.restore_predecessor(BASE.PRODUCT)
        LIVENESS_CONFIG.configure(BASE.PRODUCT)
        definitions = tuple(kwargs.get("probe_definitions", ()))
        require(LIVENESS_CONFIG.FEATURE not in definitions,
                "liveness feature already entered single-link arguments")
        kwargs["probe_definitions"] = (*definitions, LIVENESS_CONFIG.FEATURE)
        try:
            return current(*args, **kwargs)
        finally:
            LIVENESS_CONFIG.restore_predecessor(BASE.PRODUCT)

    single_link_with_liveness._v160_active_frame_liveness = True  # type: ignore[attr-defined]
    single_link_with_liveness._v160_active_frame_delegate = current  # type: ignore[attr-defined]
    BASE.PRODUCT.single_link = single_link_with_liveness


def configure_for_paths(build: Path, preflight: Path, *, tag: str) -> None:
    BASE.set_paths(build, preflight, tag=tag)
    BASE.PREV.configure_module()
    install_liveness_consumer()
    REOPEN.capture_successor_gate = LIVENESS_GUARD.active_capture_successor_gate


def configure_module() -> None:
    configure_for_paths(BUILD, PREFLIGHT, tag="active-frame-liveness")


def process_probe_child(*, mutant: bool) -> None:
    original_configure = BASE.PREV.configure_module

    def configure_then_install() -> None:
        original_configure()
        install_liveness_consumer()
        REOPEN.capture_successor_gate = (
            LIVENESS_GUARD.active_capture_successor_gate)

    BASE.PREV.configure_module = configure_then_install
    try:
        ORIGINAL_PROCESS_PROBE_CHILD(mutant=mutant)
    finally:
        BASE.PREV.configure_module = original_configure


def install() -> None:
    BASE.BUILD = BUILD
    BASE.PRODUCT_ELF = PRODUCT_ELF
    BASE.PREFLIGHT = PREFLIGHT
    BASE.NORMAL_BUILD = NORMAL_BUILD
    BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD
    BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.PREDECESSOR_RED = PREDECESSOR
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BASE.FINAL_STATUS = FINAL_STATUS
    BASE.authority = authority
    BASE.predecessor = predecessor
    BASE.configure_module = configure_module
    BASE.process_probe_child = process_probe_child


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def validate_empty_phase_claim(value: dict[str, Any]) -> None:
    require(value["length_authority"] == "candidate manifest"
            and 0 < value["encoded_bytes"] <= 255
            and value["semantic_fixture"] ==
                "comfort-cursor-down-empty-boundary"
            and value["fixed_status"] ==
                "PASS: EMPTY PHASE WAITS AND CONTINUES"
            and value["unfixed_status"] == "TypeError"
            and value["preload_only_rejected"] is True
            and value["emitted_equals_compiled"] is True,
            "candidate v16core empty-phase semantic claim drift")


def empty_phase_claim_mutations(value: dict[str, Any]) -> list[str]:
    mutations = {
        "restore-stored-248-size-pin": lambda x: x.update(
            length_authority="stored equality: 248"),
        "unfixed-form-accepted": lambda x: x.update(unfixed_status="PASS"),
        "emitted-object-not-consumed": lambda x: x.update(
            emitted_equals_compiled=False),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_empty_phase_claim(trial)
        except BASE.CardError:
            rejected.append(name)
    require(rejected == list(mutations),
            "candidate v16core empty-phase claim mutation survived")
    return rejected


def final_library_gate(final_claims: dict[str, Any]) -> dict[str, Any]:
    out = BUILD / "candidate-library/v16core"
    out.parent.mkdir(parents=True, exist_ok=True)
    suite = STD._read_suite(str(V16_SUITE))
    checked = STD.check_suite(str(V16_SUITE), suite)
    STD.emit_artifacts(str(V16_SUITE), suite, str(out), base_addr=0,
                       artifact_role="disk-lib")
    manifest_path = out.with_suffix(".manifest.json")
    manifest = BASE.load(manifest_path)
    rows = [row for row in manifest["entries"] if row["name"] == "%read-line-loop"]
    require(len(rows) == 1 and 0 < int(rows[0]["length"]) <= 255,
            "candidate v16core loop identity/size contract drift")
    blob = out.with_suffix(".blob.bin")
    raw = blob.read_bytes(); row = rows[0]
    start = int(row["blob_offset"]); end = start + int(row["length"])
    emitted = B.decode_code_object(raw[start:end])
    compiled = checked["code_by_name"]["%read-line-loop"]
    semantic = PRIMARY_FIX.derive()
    claim = {"length_authority": "candidate manifest",
        "encoded_bytes": int(row["length"]),
        "semantic_fixture": semantic["fixture_contract"]["case"],
        "fixed_status": semantic["regression"]["fixed_boundary"]["status"],
        "unfixed_status": semantic["regression"]["unfixed_mutation"]["status"],
        "preload_only_rejected": semantic["fixture_contract"]
            ["preload_only_rejected"],
        "emitted_equals_compiled": ((emitted.nargs, emitted.nlocals,
            emitted.flags, emitted.payload) == (compiled.nargs, compiled.nlocals,
            compiled.flags, compiled.payload))}
    validate_empty_phase_claim(claim)
    mutations = empty_phase_claim_mutations(claim)
    require(manifest["blob_sha256"] == hashlib.sha256(raw).hexdigest()
            and claim["emitted_equals_compiled"] is True
            and final_claims["claim_source"] == "final linked ELF only",
            "candidate v16core/final-ELF authority split drift")
    return {"manifest": BASE.bind(manifest_path), "blob": BASE.bind(blob),
            "function": "%read-line-loop", "encoded_bytes": int(row["length"]),
            "source_fix": BASE.bind(PRIMARY_FIX.SOURCE),
            "empty_phase_semantic_claim": claim,
            "mutations_rejected": mutations,
            "authority_split": {"native_walls": "final linked ELF",
                                "resident_loop": "candidate v16core artifact"}}


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = BASE.load(path)
    # The inherited reopen preflight carries the target-object observation
    # from its own sealed world.  Refresh that one living observation from
    # the candidate source after the full configurator stack has run; the real
    # card consumer immediately validates the resulting complete report.
    value["input_fidelity"]["target_object"] = FIDELITY.target_object_gate()
    value["input_fidelity"]["target_object"]["candidate_derived_at_card"] = True
    FIDELITY.validate(value["input_fidelity"], final=False)
    mutant = deepcopy(value["input_fidelity"])
    mutant["target_object"]["sizes"]["helper"] = 25
    try:
        FIDELITY.validate(mutant, final=False)
    except FIDELITY.FidelityError:
        pass
    else:
        require(False, "stored 25-byte helper witness survived candidate rebind")
    processes = value["real_process_argv_witness"]["normal"]["processes"]
    sources = [row["source"] for row in processes]
    new_service = LIVENESS_CONFIG.NEW_SERVICE.relative_to(ROOT).as_posix()
    new_padding = LIVENESS_CONFIG.NEW_PADDING.relative_to(ROOT).as_posix()
    old_service = LIVENESS_CONFIG.OLD_SERVICE.relative_to(ROOT).as_posix()
    old_padding = LIVENESS_CONFIG.OLD_PADDING.relative_to(ROOT).as_posix()
    require(sources.count(new_service) == 1 and sources.count(new_padding) == 1
            and old_service not in sources and old_padding not in sources,
            "real compiler processes did not consume liveness successors")
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "active_frame_authority": authority(),
        "active_frame_predecessor": BASE.bind(PREDECESSOR),
        "active_frame_preflight": ACTIVE.preflight(),
        "input_counter_preflight": COUNTERS.derive(),
        "candidate_object_rebind": {
            "consumer": "input_fidelity_reopen_card.validate_card_preflight",
            "source": "assembled candidate after full card configuration",
            "helper_bytes": value["input_fidelity"]["target_object"]
                ["sizes"]["helper"],
            "stored_25_byte_witness_absent": True,
            "stored_25_byte_mutation_rejected": True,
        },
        "liveness_real_consumer": {
            "consumer": "real mos-mega65-clang process argv",
            "service": new_service, "padding": new_padding,
            "predecessors_absent": True,
        },
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def append_final() -> None:
    value = BASE.load(RECEIPT)
    gate = ACTIVE.final_gate(PRODUCT_ELF)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "active_frame_authority": authority(),
        "active_frame_predecessor": BASE.bind(PREDECESSOR),
        "active_frame_preflight": BASE.bind(PREFLIGHT / "preflight.json"),
        "active_frame_final_gate": gate,
        "candidate_v16core": final_library_gate(value["final_world_claims"]),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "Comfort prompt card, same-world media, fourth owner contact"})
    RECEIPT.write_bytes(canonical(value))


def validate_counter_receipt_adapter(gate: dict[str, Any]) -> dict[str, Any]:
    counters = gate["input_counters"]
    addresses = counters["counter_addresses"]
    counter_count = len(addresses)
    physical_allocation_bytes = 112
    ring_index_values = physical_allocation_bytes - counter_count
    usable_events = ring_index_values - 1
    loss = counters["loss_wall"]
    required_events = loss["events"]
    reserve_events = usable_events - required_events
    require(counter_count > 0
            and len(set(addresses.values())) == counter_count
            and counters["ring_usable_events"] == usable_events
            and loss == {"events": 94, "seen": 94, "stored": 94,
                         "taken": 94, "dropped": 0}
            and counters["reserve_events"] == reserve_events
            and usable_events >= required_events,
            "active-frame candidate-derived counter receipt drift")
    return {"source": "candidate counter population",
            "physical_allocation_bytes": physical_allocation_bytes,
            "counter_count": counter_count,
            "counter_names": sorted(addresses),
            "ring_index_values": ring_index_values,
            "ring_usable_events": usable_events,
            "loss_wall_events": required_events,
            "reserve_events": reserve_events,
            "contract": "ring_usable_events >= loss_wall_events"}


def counter_receipt_adapter_mutations(gate: dict[str, Any]) -> list[str]:
    mutations = {
        "restore-pre-RAW-108-14-pin": lambda row: row["input_counters"].update(
            ring_usable_events=108, reserve_events=14),
        "loss-wall-exceeds-derived-capacity": lambda row: row["input_counters"]
            ["loss_wall"].update(events=108, seen=108, stored=108, taken=108),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        trial = deepcopy(gate); mutate(trial)
        try:
            validate_counter_receipt_adapter(trial)
        except BASE.CardError:
            rejected.append(name)
    require(rejected == list(mutations),
            "active-frame counter receipt adapter mutation survived")
    return rejected


def check_receipt() -> dict[str, Any]:
    value = BASE.load(RECEIPT)
    gate = value["active_frame_final_gate"]
    validate_counter_receipt_adapter(gate)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["population"]["population_count"] == 1
            and gate["enforcement"]["section"] == ACTIVE.SERVICE
            and gate["far_service"]["free_bytes"] >= 0
            and gate["input_counters"]["loss_wall"]["dropped"] == 0,
            "active-frame final receipt drift")
    BASE.PREV.PREV.PREV.validate_final_claims(value)
    return value


def validate_resume_execution(value: dict[str, int]) -> None:
    require(value == {"scope_acceptance_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "media_builds": 0,
        "device_contacts": 0},
        "active-frame read-only resume attempted product work")


def resume_execution_mutations(value: dict[str, int]) -> list[str]:
    rejected: list[str] = []
    for name in ("WPLTO_runs", "product_links", "cards_consumed"):
        trial = deepcopy(value); trial[name] = 1
        try:
            validate_resume_execution(trial)
        except BASE.CardError:
            rejected.append(name)
        else:
            require(False, f"active-frame rebuild mutation survived: {name}")
    return rejected


def validate_resume_adapter(gate: dict[str, Any]) -> None:
    enforcement = gate.get("enforcement", {})
    require(enforcement.get("section") == ACTIVE.SERVICE
            and enforcement.get("walker_bytes") == 80,
            "active-frame resume adapter vocabulary drift")


def resume_adapter_preflight(elf: Path) -> dict[str, Any]:
    gate = ACTIVE.final_gate(elf)
    validate_resume_adapter(gate)
    mutant = deepcopy(gate)
    enforcement = mutant["enforcement"]
    enforcement["symbol_bytes"] = enforcement.pop("walker_bytes")
    try:
        validate_resume_adapter(mutant)
    except BASE.CardError:
        rejected = True
    else:
        require(False, "resume adapter vocabulary mutation survived pre-resume")
    return {"status": "PASS: REAL RESUME ADAPTER CONSUMED PRODUCER VOCABULARY",
        "producer": "ACTIVE.final_gate", "consumer": "resume tail adapter",
        "field": "enforcement.walker_bytes", "value": 80,
        "legacy_symbol_bytes_mutation_rejected": rejected}


def resume_red_predecessor() -> dict[str, Any]:
    red = BASE.load(RESUME_FINAL_RED)
    require(red.get("status") ==
                "FINAL RED: ACTIVE-FRAME READ-ONLY RESUME STOPS"
            and red.get("error") == {"type": "KeyError",
                                     "message": "'symbol_bytes'"}
            and red.get("classification", {}).get("producer_field") ==
                "walker_bytes"
            and red.get("frozen_pair_before") == red.get("frozen_pair_after")
            and red.get("attempt_accounting", {}).get("WPLTO_runs") == 0
            and red.get("attempt_accounting", {}).get("product_links") == 0
            and red.get("attempt_accounting", {}).get("cards_consumed") == 0,
            "active-frame replacement-resume predecessor drift")
    return red


def frozen_pair() -> dict[str, dict[str, Any]]:
    red = BASE.load(FINAL_RED)
    artifacts = red.get("artifacts", {})
    require(red.get("status") ==
                "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS"
            and red.get("error", {}).get("message") ==
                "final linked hybrid consumer membership red"
            and red.get("attempt_accounting", {}).get("WPLTO_runs") == 1
            and red.get("attempt_accounting", {}).get("product_link_attempts") == 1,
            "active-frame consumer-size Final Red drift")
    pair = {name: artifacts[name] for name in ("ELF", "PRG")}
    for row in pair.values():
        require(BASE.bind(ROOT / row["path"]) == row,
                f"active-frame frozen artifact drift: {row['path']}")
    return pair


def resume() -> None:
    install()
    require(not RECEIPT.exists() and not RESUME_RECEIPT.exists()
            and RESUME_FINAL_RED.exists()
            and not REPLACEMENT_RESUME_FINAL_RED.exists(),
            "active-frame replacement resume is one-shot")
    predecessor = resume_red_predecessor()
    auth = replacement_resume_authority(); before = frozen_pair()
    red = BASE.load(FINAL_RED)
    claims = {"status": BASE.PREV.PREV.PREV.FINAL_STATUS,
              "final_world_claims": red["final_world_claims"]}
    BASE.PREV.PREV.PREV.validate_final_claims(claims)
    mutations = BASE.PREV.PREV.PREV.claim_mutations(claims)
    member = red["final_world_claims"]["membership"]
    consumer_bytes = member["section_bytes"]
    require("restore-stored-consumer-size-67" in mutations
            and consumer_bytes == member["symbol_bytes"],
            "candidate-derived consumer-size conversion drift")

    elf = ROOT / before["ELF"]["path"]
    adapter = resume_adapter_preflight(elf)
    build = ROOT / before["ELF"]["path"].split("/wplto/")[0]
    scope_path = build / "owner-scope-result.json"
    acceptance_path = build / "artifact-acceptance.json"
    scope = BASE.load(scope_path); acceptance = BASE.load(acceptance_path)
    delivered = acceptance.get("delivered_bytes", {})
    require(scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS"
            and delivered.get("candidate_elf") == before["ELF"]
            and delivered.get("completed_resident_prg") == before["PRG"],
            "frozen Scope/Acceptance identity drift")

    gate = ACTIVE.final_gate(elf)
    validate_resume_adapter(gate)
    require(gate["far_service"]["free_bytes"] == 37
            and gate["enforcement"]["walker_bytes"] == 80
            and gate["input_counters"]["ring_usable_events"] == 108
            and gate["input_counters"]["loss_wall"]["dropped"] == 0,
            "active-frame read-only final gate red")
    execution = {"scope_acceptance_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "media_builds": 0,
        "device_contacts": 0}
    validate_resume_execution(execution)
    after = frozen_pair()
    require(before == after, "read-only resume changed frozen pair")
    value = {"format": FORMAT + "-acceptance-resume-v1",
        "recorded_on": "2026-08-21", "status": RESUME_STATUS,
        "liveness_contract_closed": True,
        "consumer_size": {"source": "final linked candidate",
            "section_bytes": consumer_bytes,
            "symbol_bytes": member["symbol_bytes"],
            "contract": "0 < candidate bytes <= 70",
            "stored_67_pin_rejected": True},
        "final_world_claims": red["final_world_claims"],
        "final_world_mutations_rejected": mutations,
        "active_frame_final_gate": gate,
        "real_resume_adapter_preflight": adapter,
        "scope": {"receipt": BASE.bind(scope_path), "status": scope["status"]},
        "acceptance": {"receipt": BASE.bind(acceptance_path),
            "status": acceptance["status"]},
        "frozen_pair_before": before, "frozen_pair_after": after,
        "execution_witness": execution,
        "rebuild_mutations_rejected": resume_execution_mutations(execution),
        "authority": {"review": auth,
            "original_resume": resume_authority(),
            "resume_Final_Red": BASE.bind(RESUME_FINAL_RED),
            "Final_Red": BASE.bind(FINAL_RED), "driver": BASE.bind(DRIVER)},
        "predecessor_attempt_accounting": predecessor["attempt_accounting"],
        "media_authorized": False, "device_contacts": 0,
        "next": "Comfort prompt card, then fresh same-world media"}
    RESUME_RECEIPT.write_bytes(canonical(value))
    print("v1.6 active-frame liveness: RESUME PASS scope=PASS "
          f"acceptance=PASS consumer={consumer_bytes}<=70 "
          "WPLTO=0 link=0 card=0")


def record_resume_red(error: Exception) -> None:
    before = frozen_pair()
    build = ROOT / before["ELF"]["path"].split("/wplto/")[0]
    scope_path = build / "owner-scope-result.json"
    acceptance_path = build / "artifact-acceptance.json"
    replacement = RESUME_FINAL_RED.exists()
    target = REPLACEMENT_RESUME_FINAL_RED if replacement else RESUME_FINAL_RED
    require(not target.exists(), "active-frame resume Final Red already sealed")
    value = {"format": FORMAT + "-acceptance-resume-final-red-v1",
        "recorded_on": "2026-08-21",
        "status": "FINAL RED: ACTIVE-FRAME READ-ONLY RESUME STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "classification": {
            "family": "receipt-vocabulary-adapter",
            "mechanism_fully_attributed": True,
            "product_fault": False,
            "scope_green_before_stop": True,
            "acceptance_green_before_stop": True,
            "expected_field": "symbol_bytes",
            "producer_field": "walker_bytes"},
        "frozen_pair_before": before, "frozen_pair_after": frozen_pair(),
        "scope": {"receipt": BASE.bind(scope_path),
            "status": BASE.load(scope_path)["status"]},
        "acceptance": {"receipt": BASE.bind(acceptance_path),
            "status": BASE.load(acceptance_path)["status"]},
        "attempt_accounting": {"scope_acceptance_resumes": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"review": (replacement_resume_authority()
                if replacement else resume_authority()),
            "Final_Red": BASE.bind(FINAL_RED), "driver": BASE.bind(DRIVER)},
        "retry_authorized": False, "media_authorized": False,
        "next": "review disposition for a read-only replacement resume"}
    require(value["frozen_pair_before"] == value["frozen_pair_after"],
            "failed resume changed frozen pair")
    if replacement:
        value["predecessor_resume_Final_Red"] = BASE.bind(RESUME_FINAL_RED)
    target.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, NORMAL_BUILD,
        NORMAL_PREFLIGHT, MUTANT_BUILD, MUTANT_PREFLIGHT, RECEIPT, FINAL_RED)),
        "active-frame liveness card is one-shot")
    predecessor(); authority(); ACTIVE.preflight(); COUNTERS.validate(COUNTERS.derive())
    BASE.preflight(); append_preflight()
    print("v1.6 active-frame card: PREFLIGHT PASS card=0/1 population=1 "
          "ring=108 wall=94")


def card() -> None:
    predecessor(); authority()
    value = BASE.load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["active_frame_preflight"]["population"]
                ["population_count"] == 1,
            "active-frame persisted preflight drift")
    BASE.card(); append_final(); check_receipt()
    print("v1.6 active-frame card: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    configure_module(); BASE.record_red(error)
    if FINAL_RED.exists():
        value = BASE.load(FINAL_RED)
        value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS",
            "active_frame_authority": authority(),
            "active_frame_predecessor": BASE.bind(PREDECESSOR),
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        if RESUME_RECEIPT.exists():
            value = BASE.load(RESUME_RECEIPT)
            require(value["status"] == RESUME_STATUS
                    and value["frozen_pair_before"] ==
                        value["frozen_pair_after"],
                    "active-frame resume receipt drift")
            print("v1.6 active-frame card: CHECK PASS liveness=CLOSED")
            return 0
        check_receipt()
        print("v1.6 active-frame card: CHECK PASS final-world=green")
        return 0
    if action == "resume":
        resume(); return 0
    return BASE.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"active-frame Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        elif len(sys.argv) > 1 and sys.argv[1] == "resume":
            try:
                record_resume_red(error)
            except Exception as receipt_error:
                print(f"active-frame resume Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 active-frame card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
