#!/usr/bin/env python3
"""Close the selector-bypass domain card over its frozen final pair."""

from __future__ import annotations

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

import c2_transitive_map_nesting_gate as NEST  # noqa: E402
import c2_v160_abort_driver_relocation as ABORT  # noqa: E402
import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import c2_v160_boot_refill_dma_fix_card as DMA  # noqa: E402
import c2_v160_boot_refill_dma_fix_replacement_card as DMA_REPLACEMENT  # noqa: E402
import c2_v160_boot_refill_selector_bypass as BYPASS  # noqa: E402
import c2_v160_boot_refill_selector_bypass_adapter_replacement_card as ADAPTER  # noqa: E402
import c2_v160_boot_refill_selector_bypass_capacity_replacement_card as CAPACITY  # noqa: E402
import c2_v160_boot_refill_selector_bypass_domain_replacement_card as DOMAIN  # noqa: E402
import c2_v160_boot_refill_selector_bypass_dual_capacity_replacement_card as DUAL  # noqa: E402
import c2_v160_map_domain_alias_attribution as DOMAIN_ATTR  # noqa: E402
import c2_v160_retired_window_release_classification as RETIRED  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PARTIAL = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-domain-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-domain-card-final-red.json")
ATTRIBUTION = ARCH / "c2.3-v1.6-map-domain-alias-attribution.json"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
PRODUCER = BUILD / "producer-result.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-mutation-set-resume.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "09ca21f8"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-mutation-set-resume-v1"
STATUS = "PASS: V1.6 SELECTOR BYPASS DOMAIN CLOSED READ-ONLY"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("receipt converts to the derived named-set form",
                  "candidate-derived named registry",
                  "read-only resume over the frozen pair",
                  "single completion run", "no product change"):
        require(token in text, f"mutation-set resume authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair(partial: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {name: partial["artifacts_after"][name]
                for name in ("ELF", "PRG")}
    observed = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(observed == expected, "selector-bypass frozen pair drift")
    return observed


def domain_completion(elf: Path) -> dict[str, Any]:
    """Run the five live domain roots without replaying sealed site addresses."""
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    graph = NEST.linked_graph(elf)
    disk = truth.symbol("disk_chain_to_scratch_far")
    stub = truth.symbol("disk_chain_to_scratch")
    incoming = graph["incoming"].get(disk.name, [])
    require(incoming == [{"owner": stub.name, "owner_section": stub.section,
        "address": 0x23CD, "edge": "jsr", "target_section": disk.section,
        "target_identity": [disk.section, disk.value]}],
        "domain-aware disk caller population drift")
    nested = NEST.check(elf)
    require(nested["violations"] == [] and nested["tenant_count"] == 7,
            "domain-aware nested-MAP graph red")

    attributed = DOMAIN_ATTR.domain_graph(truth)
    target = ".text::vm_native_call"
    mapped = [f"{row.section}::{row.name}"
              for row in DOMAIN_ATTR.functions(truth)
              if row.section in DOMAIN_ATTR.MAPPED]
    mapped_paths = [path for root in mapped
                    if (path := DOMAIN_ATTR.shortest_path(
                        attributed["edges"], root, target))]
    require(mapped_paths == [], "mapped path reaches baseline vm_native_call")

    active = ACTIVE.derive_population(truth)
    require(len(active) == 1 and active[0]["call_site"] == 0xC939,
            "domain-aware active-frame population drift")
    abort_graph = ABORT.graph(truth)
    reached = ABORT.closure(abort_graph, [
        "c2_mapped_far_vm_code_load_converged",
        "c2_mapped_far_physical_read_converged"])
    forbidden = sorted(reached & {"c2_abort_driver", "c2_abort_driver_facade"})
    require(forbidden == [], "domain-aware R1 graph reaches abort path")
    retired_graph, retired_sites = RETIRED.call_graph(truth)
    require(bool(retired_graph) and bool(retired_sites),
            "domain-aware retired-window graph empty")
    selector = BYPASS.selector_semantics(truth)
    require(len(selector["actual_callers"]) == 2
            and all(row["selected_sink"] == "c2_map_cpu_read"
                    for row in selector["actual_callers"]),
            "domain-aware selector population drift")
    return {"authority": "live final-ELF section/domain graph",
        "source_gate": DOMAIN.source_gate(), "disk_body_edge": incoming[0],
        "nested_MAP": {"tenant_count": nested["tenant_count"],
                       "violations": nested["violations"]},
        "mapped_paths_to_vm_native_call": mapped_paths,
        "active_frame_population": len(active),
        "R1_forbidden_reached": forbidden,
        "retired_window_graph": {"owners": len(retired_graph),
            "site_pairs": len(retired_sites)},
        "selector_callers": selector["actual_callers"],
        "sealed_site_attribution": bind(ATTRIBUTION),
        "site_rule": (
            "sealed attribution preserves its two historical sites; live "
            "completion derives current edges by section/domain identity")}


def derive() -> dict[str, Any]:
    partial = load(PARTIAL); red = load(FINAL_RED)
    require(partial["status"] ==
                "PASS: V1.6 SELECTOR BYPASS DOMAIN FINAL WORLD GREEN"
            and red["status"] ==
                "FINAL RED: V1.6 SELECTOR BYPASS DOMAIN REPLACEMENT STOPS"
            and red["error"]["message"] ==
                "boot-refill MAP-CPU final receipt drift",
            "selector-bypass exact-list predecessor drift")
    before = frozen_pair(partial)

    old_receipt, old_status = DMA.RECEIPT, DMA.FINAL_STATUS
    replacement_receipt, replacement_status = (
        DMA_REPLACEMENT.RECEIPT, DMA_REPLACEMENT.FINAL_STATUS)
    try:
        DMA.RECEIPT = PARTIAL; DMA.FINAL_STATUS = partial["status"]
        DMA_REPLACEMENT.RECEIPT = PARTIAL
        DMA_REPLACEMENT.FINAL_STATUS = partial["status"]
        dma_adapter = DMA.check_receipt()
        DMA_REPLACEMENT.check_receipt()
    finally:
        DMA.RECEIPT, DMA.FINAL_STATUS = old_receipt, old_status
        DMA_REPLACEMENT.RECEIPT = replacement_receipt
        DMA_REPLACEMENT.FINAL_STATUS = replacement_status

    population = dma_adapter["boot_refill_DMA_mutation_population"]
    population_mutations = DMA.mutation_population_mutations(population)
    historical_gate = dict(partial["boot_refill_DMA_closure"])
    historical_gate.pop("selector_totality", None)
    historical = DMA.mutation_population(
        historical_gate, list(DMA.HISTORICAL_MUTATION_REGISTRY))
    DMA.validate_mutation_population(historical)

    bypass = BYPASS.linked_read_model(ELF); BYPASS.validate_final(bypass)
    ordinary_capacity = CAPACITY.final_capacity(ELF)
    dual_capacity = DUAL.final_capacity(ELF)
    adapter_gate = partial["nested_MAP_swap"]
    ADAPTER.validate_adapter_gate(adapter_gate)
    adapter_mutations = ADAPTER.adapter_mutations(adapter_gate)
    domain = domain_completion(ELF)

    producer, scope, acceptance = (load(PRODUCER), load(SCOPE), load(ACCEPTANCE))
    delivered = acceptance["delivered_bytes"]
    require(producer["status"] == scope["status"] == acceptance["status"] == "PASS"
            and delivered["candidate_elf"] == before["ELF"]
            and delivered["completed_resident_prg"] == before["PRG"],
            "persisted producer/Scope/Acceptance tail drift")
    after = frozen_pair(partial)
    require(before == after, "read-only completion changed frozen pair")

    execution = {"qualification_resumes": 1, "completion_runs": 1,
        "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
        "media_builds": 0, "device_contacts": 0}
    return {"format": FORMAT, "recorded_on": "2026-08-24", "status": STATUS,
        "authority": authority(), "driver": bind(DRIVER),
        "predecessor_Final_Red": bind(FINAL_RED),
        "partial_product_receipt": bind(PARTIAL),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "mutation_population": population,
        "mutation_population_mutations_rejected": population_mutations,
        "historical_four_member_world_still_valid": historical,
        "real_adapter_completion": {
            "boot_refill_DMA_fix": "PASS",
            "boot_refill_candidate_source_replacement": "PASS",
            "selector_bypass": bypass,
            "ordinary_capacity": ordinary_capacity,
            "dual_capacity": dual_capacity,
            "receipt_adapter": {"status": "PASS",
                "mutations_rejected": adapter_mutations},
            "MAP_domain": domain},
        "qualification_tail": {"producer": bind(PRODUCER),
            "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE),
            "scope_status": scope["status"],
            "acceptance_status": acceptance["status"],
            "delivered_bytes": delivered},
        "execution_accounting": execution, "product_change": False,
        "media_authorized": False, "device_contacts": 0,
        "next": "artifact-only media, then seam-confirmation contact round three",
        "claim_limit": (
            "Read-only adapter completion over the frozen final pair; no card, "
            "WPLTO, product link, media build or device action.")}


def validate(value: dict[str, Any]) -> None:
    population = value["mutation_population"]
    DMA.validate_mutation_population(population)
    partial = load(PARTIAL)
    observed_population = DMA.mutation_population(
        partial["boot_refill_DMA_closure"], partial["mutations_rejected"])
    historical_gate = dict(partial["boot_refill_DMA_closure"])
    historical_gate.pop("selector_totality", None)
    observed_historical = DMA.mutation_population(
        historical_gate, list(DMA.HISTORICAL_MUTATION_REGISTRY))
    DMA.validate_mutation_population(observed_historical)
    derived_completion = {
        "selector_bypass": BYPASS.linked_read_model(ELF),
        "ordinary_capacity": CAPACITY.final_capacity(ELF),
        "dual_capacity": DUAL.final_capacity(ELF),
        "MAP_domain": domain_completion(ELF),
    }
    BYPASS.validate_final(derived_completion["selector_bypass"])
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and bind(DRIVER) == value["driver"]
            and observed_population == population
            and observed_historical ==
                value["historical_four_member_world_still_valid"]
            and DMA.mutation_population_mutations(population) ==
                value["mutation_population_mutations_rejected"]
            and population["expected_count"] == population["observed_count"] == 7
            and population["missing"] == [] and population["unexpected"] == []
            and all(value["real_adapter_completion"][name] == result
                    for name, result in derived_completion.items())
            and value["real_adapter_completion"]["selector_bypass"]
                ["unsafe_content_DMA_count"] == 0
            and value["real_adapter_completion"]["MAP_domain"]
                ["mapped_paths_to_vm_native_call"] == []
            and value["qualification_tail"]["scope_status"] == "PASS"
            and value["qualification_tail"]["acceptance_status"] == "PASS"
            and value["execution_accounting"] == {
                "qualification_resumes": 1, "completion_runs": 1,
                "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0}
            and value["product_change"] is False,
            "selector-bypass mutation-set resume receipt drift")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in {"resume", "check"}, "usage: resume|check")
    if action == "resume":
        require(not RECEIPT.exists(), "mutation-set resume is one-shot")
        value = derive(); validate(value); RECEIPT.write_bytes(canonical(value))
    else:
        value = load(RECEIPT); validate(value)
        require(frozen_pair(load(PARTIAL)) == value["frozen_pair_after"],
                "mutation-set resume final pair drift after sealing")
    print("v1.6 selector bypass: RESUME PASS mutations=7/7 scope=PASS "
          "acceptance=PASS WPLTO=0 link=0 card=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResumeError, RuntimeError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"v1.6 selector bypass mutation-set resume: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
