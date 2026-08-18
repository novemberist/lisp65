#!/usr/bin/env python3
"""Price and gate the v1.5 F018B content-safe reader fix."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-f018b-content-safe-read-contract.json"
SWEEP = ROOT / "config/c2-dma-content-consumption-sweep.json"
CONVERGENCE = ROOT / "config/c2-code-window-convergence-contract.json"
OWNERSHIP = ROOT / "config/c2-stack-overlay-ownership-contract.json"
RELEASE = ROOT / "config/c2-v150-release-contract.json"
PLAN = ROOT / "docs/planning/v1.5.0-release-work-plan.md"
MEM = ROOT / "src/mem.c"
DMA = ROOT / "src/c2_platform_dma.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
LINKER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
CARD = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
FIX_CARD = ROOT / "tools/host-lisp/c2_v150_f018b_fix_card.py"
HW_SOURCE = ROOT / "scripts/hw-access-smoke-main.c"
HW_RESULTS = ROOT / "build/hw/hw-access-hw_access_results.bin"
HW_GOT = ROOT / "build/hw/hw-access-hw_access_got.bin"
HW_WANT = ROOT / "build/hw/hw-access-hw_access_want.bin"
HW_READING = ROOT / (
    "docs/archive/pre-1.0/reference/mega65-hardware-deepdive-2026-07-10.md")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-f018b-content-safe-read-pricing-receipt.json")
LINKER_REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-f018b-linker-lma-crc-rebind-receipt.json")
RUNTIME_REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-map-tuple-d1-e25-rebind-2026-08-14.json")
SWEEP_REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-f018b-sweep-breadcrumb-rebind-20260815.json")
LMA_REPAIR_AUTHORITY = "cf2b489e8041e3d8d7034dc4bfd0bfd053131b54"
CRC_REPAIR_AUTHORITY = "30a5568706f92e7a61475b1f28745cf2d52d2de5"
LINKER_REBIND_AUTHORITY = "d6141fa3bd8b1a1bd4ca8d0fa4b93efb794710c9"
LMA_REPAIR_PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
PRICING_RECORDED_ON = "2026-08-12"
LINKER_REBIND_RECORDED_ON = "2026-08-12"


class FixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FixError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "authority": "git-blob", "commit": commit, "path": relative,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def linker_output_from_source(raw: bytes) -> bytes:
    namespace: dict[str, Any] = {
        "__file__": str(LINKER), "__name__": "_lisp65_lma_rebind_probe"}
    exec(compile(raw, str(LINKER), "exec"), namespace)
    output = namespace["linker_script"]()
    require(isinstance(output, str) and output,
            "default product linker renderer did not return text")
    return output.encode()


def linker_rebind_value() -> dict[str, Any]:
    original = load(RECEIPT)
    old_source = git_bytes(LMA_REPAIR_AUTHORITY, LINKER)
    post_lma_source = git_bytes(CRC_REPAIR_AUTHORITY, LINKER)
    rebound_source = git_bytes(LINKER_REBIND_AUTHORITY, LINKER)
    require(original["authorities"]["linker"]["sha256"]
            == hashlib.sha256(old_source).hexdigest(),
            "F018B original linker authority is not the LMA parent")
    old_output = linker_output_from_source(old_source)
    post_lma_output = linker_output_from_source(post_lma_source)
    current_output = linker_output_from_source(rebound_source)
    rebound_binding = git_bind(LINKER_REBIND_AUTHORITY, LINKER)
    rebound_binding.pop("authority")
    rebound_binding.pop("commit")
    require(old_output == post_lma_output == current_output,
            "LMA/CRC repairs changed the default historical linker rendering")
    return {
        "format": "lisp65-c2.3-v150-f018b-linker-lma-crc-rebind-v2",
        "recorded_on": LINKER_REBIND_RECORDED_ON,
        "status": "PASSED-LOUD-LMA-PLUS-CLOSER-ONLY-LINKER-REBIND",
        "authority": {
            "LMA_owner_authorization": git_bind(
                LMA_REPAIR_AUTHORITY, LMA_REPAIR_PLAN),
            "closer_owner_authorization": git_bind(
                CRC_REPAIR_AUTHORITY, LMA_REPAIR_PLAN),
            "original_pricing_receipt": bind(RECEIPT),
            "historical_linker": git_bind(LMA_REPAIR_AUTHORITY, LINKER),
            "post_LMA_pre_closer_linker": git_bind(
                CRC_REPAIR_AUTHORITY, LINKER),
            "current_linker": rebound_binding,
        },
        "semantic_equivalence": {
            "historical_default_linker_sha256": hashlib.sha256(
                old_output).hexdigest(),
            "post_LMA_default_linker_sha256": hashlib.sha256(
                post_lma_output).hexdigest(),
            "current_default_linker_sha256": hashlib.sha256(
                current_output).hexdigest(),
            "default_linker_byteidentical": True,
            "new_paths": [
                "explicit opt-in low-resident LMA reset",
                "publish-last CRC call binding by encoded target and ELF symbol",
            ],
            "f018b_pricing_or_routes_changed": False,
        },
        "execution_accounting": {
            "compiles": 0, "links": 0, "wplto_runs": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Loud semantic-preserving authority rebind for the shared linker "
            "source across the separately authorized LMA-rendering and "
            "closer-locator edits only; no F018B repricing, card, completion, "
            "media or release claim."),
    }


def validate_linker_rebind(value: dict[str, Any]) -> None:
    require(value == linker_rebind_value(),
            "F018B LMA/closer linker rebind drift")


def linker_rebind_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "detach-LMA-owner": lambda x: x["authority"][
            "LMA_owner_authorization"].update(sha256="0" * 64),
        "detach-closer-owner": lambda x: x["authority"][
            "closer_owner_authorization"].update(sha256="0" * 64),
        "rewrite-post-LMA-linker": lambda x: x["authority"][
            "post_LMA_pre_closer_linker"].update(sha256="0" * 64),
        "rewrite-current-linker": lambda x: x["authority"][
            "current_linker"].update(sha256="0" * 64),
        "claim-output-drift": lambda x: x["semantic_equivalence"].update(
            default_linker_byteidentical=False),
        "claim-f018b-change": lambda x: x["semantic_equivalence"].update(
            f018b_pricing_or_routes_changed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        candidate.pop("mutations_rejected", None)
        mutate(candidate)
        try:
            validate_linker_rebind(candidate)
        except FixError:
            rejected.append(name)
    require(rejected == list(cases), "F018B linker-rebind mutation survived")
    return rejected


def write(value: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RECEIPT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(RECEIPT)


def source_facts() -> dict[str, Any]:
    contract = load(CONTRACT)
    sweep = load(SWEEP)
    convergence = load(CONVERGENCE)
    ownership = load(OWNERSHIP)
    release = load(RELEASE)
    plan = PLAN.read_text(encoding="utf-8")
    mem = MEM.read_text(encoding="utf-8")
    dma = DMA.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    linker = LINKER.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")
    fix_card = FIX_CARD.read_text(encoding="utf-8")
    hw_source = HW_SOURCE.read_text(encoding="utf-8")
    hw_reading = HW_READING.read_text(encoding="utf-8")

    require(contract.get("format")
            == "lisp65-c2-f018b-content-safe-read-contract-v1"
            and contract.get("accepted_by") == "cf26b779"
            and contract.get("status") == "owner-commissioned-fix-block",
            "F018B fix contract identity drift")
    require(contract.get("card", {}).get("replacement") == {
                "count": 1,
                "authorized_by": "da816c8b",
                "profile_authority": (
                    "SHA-bound build-local projection of the current "
                    "candidate preflight"),
                "status": (
                    "pre-WPLTO-first-red-public-authority-kind-substituted")}
            and contract.get("card", {}).get("additional_card") == {
                "count": 1,
                "authorized_by": "43ad331e",
                "profile_authority": (
                    "public authority identity preserved; candidate "
                    "projection provenance additive"),
                "precondition": (
                    "real fresh_static_plane_bundle consumer green")}
            and contract.get("card", {}).get("first_attempt", {}).get(
                "status") == "pre-WPLTO-first-red-no-product-artifact",
            "additional-card authority drift")
    require("Owner disposition — 2026-08-12: the F018B read-path fix block"
                in plan
            and "no content-consuming read may trust a completion signal"
                in plan.lower(),
            "owner commission absent from v1.5 plan")
    require(len(sweep.get("sites", [])) == 13,
            "13-site sweep cardinality drift")
    require(len(contract.get("site_decisions", [])) == 3
            and len(contract.get("already_protected", [])) == 8,
            "per-site price table no longer closes eleven consumers")

    cpu = contract["pricing"]["cpu_28bit"]
    selected = contract["pricing"]["verified_convergence"]
    require(cpu["verdict"] == "rejected-for-bank4-bank5-and-attic"
            and selected == {
                "mapped_bank2_body_bytes": 874,
                "resident_facade_bytes": 98,
                "bank0_state_bytes": 68,
                "zero_page_bytes": 2,
                "timeout_frames": 64,
                "verdict": "selected",
                "reason": selected["reason"],
            }, "pricing result drift")
    require(HW_RESULTS.read_bytes()[-1:] == b"\x00"
            and HW_GOT.read_bytes()[-2:] == b"\xff\x00"
            and HW_WANT.read_bytes()[-2:] == b"\x7b\x00"
            and "HW_ACCESS_FLAT_BANK4_OBS" in hw_source
            and "flat_bank4_obs=FAIL" in hw_reading,
            "bound Bank-4 CPU-flat rejection drift")
    require("zp-indirekt/MAP-Read/Flat scheitern" in mem
            and "F018-DMA" in mem,
            "current EXT transport contract drift")

    require(convergence.get("timeout_frames") == 64
            and convergence.get("model_cases") == 8
            and convergence.get("mutation_cases") == 15,
            "convergence oracle authority drift")
    far = ownership.get("mapped_far_service", {}).get("bank2", {})
    require(far.get("service_bytes") == 874,
            "mapped convergence body price drift")
    require(ownership.get("geometry", {}).get(
                "candidate_service_state_bytes") == 68,
            "convergence state price drift")

    feature = contract["candidate_feature"]
    require(feature in release["build"]["activation_defines"],
            "v1.5 product does not activate content-safe reads")
    require("authorized = tuple(load(CONTRACT)[\"build\"][\"activation_defines\"])"
                in card
            and "*authorized" in card,
            "product card does not consume the complete activation contract")
    require("BASE.build()" in fix_card and "SAFE.postlink" in fix_card
            and "ADDITIONAL-CARD-CONSUMED" in fix_card
            and "candidate_projection" in fix_card
            and "F1W.static_gate()" in fix_card,
            "single successor card does not bind the post-link class gate")
    require("CONVERGENCE_FEATURE = \"LISP65_CODE_WINDOW_CONVERGENCE\""
                in linker
            and "CONVERGENCE_SOURCES" in linker
            and "ownership_scope_selected(extra_definitions)" in linker,
            "convergence source-owner opt-in drift")

    source_routes = {
        "EXT": (
            "ext_dma_read_or_abort(EXT_OFF(i)+0" in mem
            and "vm_code_load_converged(source_bank, source, length, destination)"
                in mem),
        "D700": (
            "c2_dma_read_or_abort(SYMPOOL_EXT_BANK" in dma
            and "vm_code_load_converged(bank, offset, length, destination)"
                in dma),
        "D705": (
            "return c2_physical_read_converged(base + offset" in runtime
            and "c2_physical_source_byte(source + i, &expected)" in runtime),
    }
    require(all(source_routes.values()),
            "one content-consuming reader bypasses convergence")

    return {
        "sweep_sites": 13,
        "content_consumers": 11,
        "newly_selected_reader_families": 3,
        "already_protected_families": 8,
        "cpu_transport": "rejected-by-bound-target-evidence",
        "winner": "verified-convergence-per-all-three-open-reader-families",
        "prices": {
            "mapped_bank2_body_bytes": 874,
            "resident_facade_bytes": 98,
            "bank0_state_bytes": 68,
            "zero_page_bytes": 2,
            "timeout_frames": 64,
        },
        "source_routes": source_routes,
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format")
            == "lisp65-c2.3-v150-f018b-content-safe-read-pricing-v1"
            and value.get("status")
            == "PASSED-PRICED-AND-SOURCE-ROUTED; ADDITIONAL-CARD-PENDING"
            and value.get("facts", {}).get("sweep_sites") == 13
            and value.get("facts", {}).get("content_consumers") == 11
            and value.get("execution_accounting") == {
                "first_card_attempts": 1,
                "first_card_WPLTO_runs": 0,
                "replacement_cards": 0,
                "replacement_WPLTO_runs": 0,
                "additional_cards": 0,
                "additional_WPLTO_runs": 0,
                "product_links": 0,
                "hardware_contacts": 0},
            "F018B pricing receipt claim drift")
    if verify:
        require(value["facts"] == source_facts(),
                "F018B pricing/source receipt is stale")
        current = make_authorities()
        historical = value["authorities"]
        differences = [name for name in current
                       if current[name] != historical.get(name)]
        require(set(differences).issubset({"runtime", "linker", "sweep"}),
                "F018B pricing authority drift exceeds authorized source rebinds")
        if "sweep" in differences:
            sweep_rebind = load(SWEEP_REBIND)
            old_contract = load(RECEIPT)["authorities"]["sweep"]
            current_contract = current["sweep"]
            historical_json = json.loads(subprocess.run(
                ["git", "show",
                 "e90e6291:config/c2-dma-content-consumption-sweep.json"],
                cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout)
            live_json = load(SWEEP)
            replacements = 0
            for row in live_json["sites"]:
                evidence = row.get("evidence", {}).get("all", [])
                for index, token in enumerate(evidence):
                    if token == "C2_V21_TRACE_CONVERGENCE_TIMEOUT":
                        evidence[index] = "if (!match) return 0;"
                        replacements += 1
            require(
                sweep_rebind.get("status") ==
                    "PASS: LOUD BREADCRUMB-TOKEN-ONLY SWEEP REBIND"
                and sweep_rebind.get("authority") == git_bind(
                    "e90e6291b08c79d6cd84260b49e7c958dbbd099a",
                    ROOT / "docs/planning/2.1-cpu-transport-work-plan.md")
                and sweep_rebind.get("historical_sweep") == old_contract
                and sweep_rebind.get("current_sweep") == current_contract
                and sweep_rebind.get("semantic_equivalence") == {
                    "all_other_contract_content_byteidentical": True,
                    "evidence_token_replacements": 3,
                    "pricing_or_routes_changed": False,
                }
                and replacements == 3 and live_json == historical_json,
                "F018B sweep rebind is not the breadcrumb token-only change")
        if "runtime" in differences:
            runtime_rebind = load(RUNTIME_REBIND)
            require(runtime_rebind.get("status") ==
                    "PASS: loud semantic-preserving D1/E25 runtime-source rebind"
                    and runtime_rebind.get("change") == {
                        "actual_changed_paths": [
                            "authority.runtime.bytes",
                            "authority.runtime.sha256"],
                        "allowed_paths": [
                            "authority.runtime.bytes",
                            "authority.runtime.sha256"],
                        "historical_receipt_rewritten": False,
                        "semantic_claims_changed": False,
                    }
                    and runtime_rebind["authority"]["historical_runtime"]
                    == historical["runtime"]
                    and runtime_rebind["authority"]["current_runtime"]
                    == current["runtime"],
                    "F018B runtime rebind does not join both authorities")
        if "linker" in differences:
            rebind = load(LINKER_REBIND)
            rejected = rebind.pop("mutations_rejected", None)
            validate_linker_rebind(rebind)
            require(rejected == linker_rebind_mutations(rebind),
                    "F018B linker-rebind mutation receipt drift")
            require(rebind["authority"]["historical_linker"]["sha256"]
                    == historical["linker"]["sha256"]
                    and hashlib.sha256(linker_output_from_source(
                        LINKER.read_bytes())).hexdigest()
                    == rebind["semantic_equivalence"][
                        "current_default_linker_sha256"],
                    "F018B linker rebind does not preserve current rendering")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-EXT-reader": lambda x: x["facts"]["source_routes"].update(EXT=False),
        "drop-D700-reader": lambda x: x["facts"]["source_routes"].update(D700=False),
        "drop-D705-reader": lambda x: x["facts"]["source_routes"].update(D705=False),
        "trust-flat-bank4": lambda x: x["facts"].update(cpu_transport="selected"),
        "lose-consumer": lambda x: x["facts"].update(content_consumers=10),
        "claim-additional": lambda x: x["execution_accounting"].update(
            additional_cards=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
            require(all(candidate["facts"]["source_routes"].values()),
                    "naked completion accepted")
            require(candidate["facts"]["cpu_transport"]
                    == "rejected-by-bound-target-evidence",
                    "unproved CPU transport accepted")
        except FixError:
            rejected.append(name)
    require(rejected == list(cases), "F018B pricing mutation survived")
    return rejected


def make_authorities() -> dict[str, dict[str, Any]]:
    return {name: bind(path) for name, path in {
        "contract": CONTRACT, "sweep": SWEEP,
        "convergence": CONVERGENCE, "ownership": OWNERSHIP,
        "release": RELEASE, "plan": PLAN, "mem": MEM, "dma": DMA,
        "runtime": RUNTIME, "linker": LINKER, "card": CARD,
        "fix_card": FIX_CARD,
        "hardware_source": HW_SOURCE, "hardware_results": HW_RESULTS,
        "hardware_got": HW_GOT, "hardware_want": HW_WANT,
        "hardware_reading": HW_READING,
    }.items()}


def make_receipt() -> dict[str, Any]:
    value = {
        "format": "lisp65-c2.3-v150-f018b-content-safe-read-pricing-v1",
        "recorded_on": PRICING_RECORDED_ON,
        "status": (
            "PASSED-PRICED-AND-SOURCE-ROUTED; ADDITIONAL-CARD-PENDING"),
        "facts": source_facts(),
        "authorities": make_authorities(),
        "execution_accounting": {
            "first_card_attempts": 1,
            "first_card_WPLTO_runs": 0,
            "replacement_cards": 0,
            "replacement_WPLTO_runs": 0,
            "additional_cards": 0,
            "additional_WPLTO_runs": 0,
            "product_links": 0,
            "hardware_contacts": 0},
        "claim_limit": (
            "Host/source pricing and routing only. The target geometry and "
            "product identity remain subject to the single authorized card."),
    }
    value["mutations_rejected"] = mutations(value)
    return value


def postlink(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"candidate ELF absent: {path}")
    truth = ElfTruth.read(
        path, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    opcodes = {"$D700": bytes.fromhex("8d00d7"),
               "$D705": bytes.fromhex("8d05d7")}
    service_section = ".lisp65_c2_mapped_far_service"
    service_hits: list[dict[str, Any]] = []
    base_hits: list[dict[str, Any]] = []
    functions = [
        symbol for symbol in truth.symbols
        if symbol.symbol_type == "Function" and symbol.bytes > 0
        and symbol.section not in ("Absolute", "Undefined")]
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes == 0:
            continue
        body = truth.section_bytes(section.name)
        for register, needle in opcodes.items():
            cursor = 0
            while True:
                offset = body.find(needle, cursor)
                if offset < 0:
                    break
                if section.name == service_section:
                    service_hits.append({
                        "address": section.address + offset,
                        "address_hex": f"${section.address + offset:04X}",
                        "register": register,
                        "section": section.name,
                    })
                else:
                    address = section.address + offset
                    owners = [
                        symbol for symbol in functions
                        if symbol.section == section.name
                        and symbol.value <= address < symbol.value + symbol.bytes]
                    require(len(owners) == 1,
                            f"base submission owner is not unique: "
                            f"{path}:{address:04x}")
                    base_hits.append({
                        "address": address,
                        "address_hex": f"${address:04X}",
                        "owner": owners[0].name,
                        "register": register,
                        "section": section.name,
                    })
                cursor = offset + 1

    # The historical five submissions remain separately attributable.  The
    # four internal oracle submissions are deliberately local assembler
    # leaves, so ownership there is the section plus its two exported entry
    # symbols, not a fabricated function name for each store.
    expected_base = {
        ("vm_runtime_overlay_exec_family", "$D705"),
        ("ext_dma", "$D700"),
        ("c2k_copy", "$D705"),
        ("c2_product_physical_copy", "$D705"),
        ("c2_facade_target_c2_dma", "$D700"),
    }
    actual_base = {(row["owner"], row["register"]) for row in base_hits}
    require(actual_base == expected_base,
            f"linked base submit owner set drift: {actual_base}")
    service_counts = {
        register: sum(row["register"] == register for row in service_hits)
        for register in opcodes}
    require(service_counts == {"$D700": 2, "$D705": 2},
            f"linked convergence submission set drift: {service_counts}")
    symbols = {row.name: row for row in truth.symbols}
    entries = (
        "c2_mapped_far_vm_code_load_converged",
        "c2_mapped_far_physical_read_converged",
    )
    require(all(name in symbols and symbols[name].section == service_section
                and symbols[name].bytes > 0 for name in entries),
            "linked convergence entry identity drift")
    return {
        "ELF": bind(path), "base_submission_sites": base_hits,
        "convergence_submission_sites": service_hits,
        "content_consuming_raw_sites": 3,
        "all_three_route_to_linked_convergence": True,
        "linked_oracle_entries": list(entries),
        "service_submission_counts": service_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "postlink", "rebind-linker"))
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not RECEIPT.exists(), "F018B pricing receipt already exists")
        value = make_receipt(); validate(value, verify=True); write(value)
        print("F018B content-safe reads: PASS pricing=convergence sites=3/3 "
              "additional=0/1")
        return 0
    if args.action == "check":
        value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
        validate(value, verify=True)
        require(rejected == mutations(value), "F018B mutation receipt drift")
        print("F018B content-safe reads check: PASS sites=3/3")
        return 0
    if args.action == "selftest":
        value = make_receipt()
        require(len(value["mutations_rejected"]) == 6,
                "F018B selftest mutation count drift")
        print("F018B content-safe reads selftest: PASS mutations=6")
        return 0
    if args.action == "rebind-linker":
        require(not LINKER_REBIND.exists(),
                "F018B LMA-only linker rebind already exists")
        value = linker_rebind_value()
        validate_linker_rebind(value)
        value["mutations_rejected"] = linker_rebind_mutations(value)
        write_path = LINKER_REBIND
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                dir=write_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(canonical(value))
        temporary.replace(write_path)
        print("F018B content-safe reads: LOUD LINKER REBIND PASS "
              "default-output=byteidentical mutations=6")
        return 0
    require(args.elf is not None, "--elf required for postlink")
    value = postlink(args.elf)
    print("F018B content-safe reads postlink: PASS "
          f"base={len(value['base_submission_sites'])} "
          f"oracle={len(value['convergence_submission_sites'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FixError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"F018B content-safe reads: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
