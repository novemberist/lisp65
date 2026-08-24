#!/usr/bin/env python3
"""Run the selector-bypass replacement with domain-aware linked identities."""

from __future__ import annotations

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

import c2_transitive_map_nesting_gate as NEST  # noqa: E402
import c2_v160_abort_driver_relocation as ABORT  # noqa: E402
import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import c2_v160_boot_refill_selector_bypass as BYPASS  # noqa: E402
import c2_v160_boot_refill_selector_bypass_adapter_replacement_card as ADAPTER  # noqa: E402
import c2_v160_map_domain_alias_attribution as ATTR  # noqa: E402
import c2_v160_nested_map_swap as SWAP  # noqa: E402
import c2_v160_retired_window_release_classification as RETIRED  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-inherited-process")
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-domain-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-domain-card-final-red.json")
PREVIOUS_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-final-red.json")
PREVIOUS_PARTIAL = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-receipt.json")
PREVIOUS_ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-adapter-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
ATTRIBUTION = ARCH / "c2.3-v1.6-map-domain-alias-attribution.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "07877cb1"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-domain-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 SELECTOR BYPASS DOMAIN REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 SELECTOR BYPASS DOMAIN FINAL WORLD GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("one self-dispositional successor card",
                  "five roots convert together", "section/mapping-domain",
                  "one wplto, one product link"):
        require(token in text, f"domain-card authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_gate() -> dict[str, Any]:
    specs = {
        "shared_MAP_graph": (ROOT / "tools/host-lisp/c2_transitive_map_nesting_gate.py",
            ("by_identity", "target_section", '"target_identity"'), ("by_value",)),
        "R1_graph": (ROOT / "tools/host-lisp/c2_v160_abort_driver_relocation.py",
            ("row.section == section", "identity.get(\"section\")"),
            ("row.value == address]",)),
        "active_frame": (ROOT / "tools/host-lisp/c2_v160_active_frame_liveness.py",
            ("target.section, target.value", "row.section == identity.get"), ()),
        "retired_window": (ROOT /
            "tools/host-lisp/c2_v160_retired_window_release_classification.py",
            ("by_identity", "key = (section, value)"), ("by_value",)),
        "selector_scanner": (ROOT /
            "tools/host-lisp/c2_v160_boot_refill_selector_bypass.py",
            ("for relocation in truth.relocations", '"target_identity"'),
            ("raw.find(needle",)),
    }
    result = {}
    for name, (path, required, forbidden) in specs.items():
        text = path.read_text(encoding="utf-8")
        require(all(token in text for token in required)
                and not any(token in text for token in forbidden),
                f"domain-aware source conversion drift: {name}")
        result[name] = {"path": path.relative_to(ROOT).as_posix(),
                        "required": list(required), "forbidden": list(forbidden)}
    return result


def final_conversion(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    graph = NEST.linked_graph(elf)
    disk = truth.symbol("disk_chain_to_scratch_far")
    stub = truth.symbol("disk_chain_to_scratch")
    incoming = graph["incoming"].get(disk.name, [])
    require(incoming == [{"owner": stub.name, "owner_section": stub.section,
        "address": 0x23CD, "edge": "jsr", "target_section": disk.section,
        "target_identity": [disk.section, disk.value]}],
        "domain-aware disk caller set drift")
    nested = NEST.check(elf)
    require(nested["violations"] == [] and nested["tenant_count"] == 7,
            "domain-aware nested-MAP graph red")

    attributed_graph = ATTR.domain_graph(truth)
    node = ".text::vm_native_call"
    mapped = [f"{row.section}::{row.name}" for row in ATTR.functions(truth)
              if row.section in ATTR.MAPPED]
    mapped_paths = [path for root in mapped
                    if (path := ATTR.shortest_path(
                        attributed_graph["edges"], root, node))]
    require(mapped_paths == [], "mapped path reaches baseline vm_native_call")
    sites = ATTR.site_rows(truth)

    active = ACTIVE.derive_population(truth)
    require(len(active) == 1 and active[0]["call_site"] == 0xC939,
            "domain-aware active-frame population drift")
    abort_graph = ABORT.graph(truth)
    reached = ABORT.closure(abort_graph, [
        "c2_mapped_far_vm_code_load_converged",
        "c2_mapped_far_physical_read_converged"])
    require(not (reached & {"c2_abort_driver", "c2_abort_driver_facade"}),
            "domain-aware R1 graph reaches abort path")
    retired_graph, retired_sites = RETIRED.call_graph(truth)
    require(bool(retired_graph) and bool(retired_sites),
            "domain-aware retired-window graph empty")
    selector = BYPASS.selector_semantics(truth)
    require(len(selector["actual_callers"]) == 2
            and all(row["selected_sink"] == "c2_map_cpu_read"
                    and row["target_identity"] == [
                        ".lisp65_c2_host_facade",
                        truth.symbol("c2_facade_runtime_overlay_exec").value]
                    for row in selector["actual_callers"]),
            "domain-aware selector population drift")
    return {"source_gate": source_gate(), "disk_body_edge": incoming[0],
        "nested_MAP": {"tenant_count": nested["tenant_count"],
                       "violations": nested["violations"]},
        "vm_native_sites": sites, "mapped_paths_to_vm_native_call": mapped_paths,
        "active_frame_population": len(active),
        "R1_forbidden_reached": sorted(
            reached & {"c2_abort_driver", "c2_abort_driver_facade"}),
        "retired_window_graph": {"owners": len(retired_graph),
            "site_pairs": len(retired_sites)},
        "selector_callers": selector["actual_callers"]}


def validate_conversion(value: dict[str, Any]) -> None:
    edge = value["disk_body_edge"]
    require(edge["owner_section"] == ".text"
            and edge["target_section"] ==
                ".lisp65_c2_mapped_diagnostic"
            and edge["target_identity"] ==
                [".lisp65_c2_mapped_diagnostic", 0x7E8D]
            and value["nested_MAP"] == {"tenant_count": 7, "violations": []}
            and value["mapped_paths_to_vm_native_call"] == []
            and value["active_frame_population"] == 1
            and value["R1_forbidden_reached"] == []
            and len(value["selector_callers"]) == 2
            and len(value["source_gate"]) == 5,
            "domain-identity conversion drift")


def conversion_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "erase-disk-target-domain": lambda x: x["disk_body_edge"].update(
            target_section=".text", target_identity=[".text", 0x7E8D]),
        "erase-disk-source-domain": lambda x: x["disk_body_edge"].update(
            owner_section="unknown"),
        "admit-baseline-jump-as-mapped": lambda x: x[
            "mapped_paths_to_vm_native_call"].append(
                ["mapped::tenant", ".text::vm_native_call"]),
        "drop-active-frame-domain-member": lambda x: x.update(
            active_frame_population=0),
        "drop-selector-domain-caller": lambda x: x[
            "selector_callers"].pop(),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try: validate_conversion(trial)
        except RuntimeError: rejected.append(name)
    require(rejected == list(cases), "domain-identity mutation survived")
    return rejected


def predecessor() -> dict[str, Any]:
    red = load(PREVIOUS_RED); partial = load(PREVIOUS_PARTIAL)
    attribution = load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: V1.6 SELECTOR BYPASS ADAPTER REPLACEMENT STOPS"
            and red["error"]["message"] ==
                "mapped disk body has a direct or missing foreign caller"
            and partial["status"] ==
                "PASS: V1.6 SELECTOR BYPASS ADAPTER FINAL WORLD GREEN"
            and attribution["status"] == ATTR.STATUS
            and attribution["decision"]["branch"] == "gate-misclassification"
            and attribution["decision"]["product_finding"] is False,
            "domain replacement predecessor drift")
    return {"adapter_replacement_Final_Red": bind(PREVIOUS_RED),
            "linked_partial_receipt": bind(PREVIOUS_PARTIAL),
            "linked_candidate_ELF": bind(PREVIOUS_ELF),
            "domain_attribution": bind(ATTRIBUTION)}


def install() -> None:
    ADAPTER.BUILD = BUILD
    ADAPTER.PREFLIGHT = PREFLIGHT
    ADAPTER.PROCESS = PROCESS
    ADAPTER.INHERITED_PROCESS = INHERITED_PROCESS
    ADAPTER.RECEIPT = RECEIPT
    ADAPTER.FINAL_RED = FINAL_RED
    ADAPTER.PREVIOUS_RED = PREVIOUS_RED
    ADAPTER.PREVIOUS_PARTIAL = PREVIOUS_PARTIAL
    ADAPTER.PREVIOUS_ELF = PREVIOUS_ELF
    ADAPTER.DRIVER = DRIVER
    ADAPTER.AUTHORIZATION = AUTHORIZATION
    ADAPTER.FORMAT = FORMAT
    ADAPTER.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    ADAPTER.FINAL_STATUS = FINAL_STATUS
    ADAPTER.authority = authority
    ADAPTER.predecessor = predecessor
    ADAPTER.install()


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"; value = load(path)
    conversion = final_conversion(PREVIOUS_ELF)
    validate_conversion(conversion)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "domain_replacement_authority": authority(),
        "domain_predecessor": predecessor(),
        "domain_conversion": conversion,
        "domain_mutations_rejected": conversion_mutations(conversion),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "selector-bypass domain replacement is one-shot")
    predecessor(); authority(); conversion_mutations(final_conversion(PREVIOUS_ELF))
    ADAPTER.preflight(); append_preflight()
    print("v1.6 selector bypass domain: PREFLIGHT PASS card=0/1 roots=5 mutations=5")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT); conversion = value["MAP_domain_conversion"]
    validate_conversion(conversion)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["MAP_domain_mutations_rejected"] == [
                "erase-disk-target-domain", "erase-disk-source-domain",
                "admit-baseline-jump-as-mapped",
                "drop-active-frame-domain-member",
                "drop-selector-domain-caller"],
            "selector-bypass domain receipt drift")
    return value


def card() -> None:
    predecessor(); authority()
    require(load(PREFLIGHT / "preflight.json")["status"] == PREFLIGHT_STATUS,
            "persisted domain preflight drift")
    ADAPTER.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    conversion = final_conversion(elf); validate_conversion(conversion)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "domain_replacement_authority": authority(),
        "domain_predecessor": predecessor(), "MAP_domain_conversion": conversion,
        "MAP_domain_mutations_rejected": conversion_mutations(conversion),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, seam confirmation"})
    RECEIPT.write_bytes(canonical(value)); check_receipt()
    print("v1.6 selector bypass domain: CARD PASS final-world=green")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 SELECTOR BYPASS DOMAIN REPLACEMENT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "domain_replacement_authority": authority(),
        "domain_predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False, "media_authorized": False,
        "next": "reviewer disposition; no further self-disposition"}))


def main() -> int:
    install(); action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 selector bypass domain: CHECK PASS"); return 0
    return ADAPTER.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"domain replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 selector bypass domain: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
