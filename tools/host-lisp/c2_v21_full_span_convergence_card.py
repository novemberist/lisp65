#!/usr/bin/env python3
"""Run the one owner-authorized full-span convergence product card."""

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
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_FIX  # noqa: E402
import c2_v21_full_span_convergence as FIX  # noqa: E402
import c2_v21_full_span_product_config as CONFIG  # noqa: E402
import c2_v21_phase9_abi_fix_replacement_card as BASE  # noqa: E402
import c2_v21_terminal_screen_lease as LEASE  # noqa: E402
import c2_v21_terminal_screen_lease_card as LINK111  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-full-span-convergence-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-full-span-convergence-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-full-span-convergence-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-full-span-convergence-card-final-red.json"
CONTRACT = FIX.CONTRACT
CONFIG_DRIVER = ROOT / "tools/host-lisp/c2_v21_full_span_product_config.py"
PREDECESSOR = LINK111.PREDECESSOR
MEDIA = LINK111.MEDIA
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "afe63882"
RECORDED_ON = "2026-08-16"
LINK = 112
FORMAT = "lisp65-c2.3-v2.1-full-span-convergence-card-v1"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    for token in ("full-span fix on all nine readers",
                  "first-byte-success shape as its named mutation",
                  "transfer-fixture conversion", "one product card"):
        require(token in raw, f"full-span card authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    card = load(PREDECESSOR)
    media = load(MEDIA)
    require(
        card.get("status") == "PASS: frozen phase-9 Acceptance resumed and green"
        and media.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready"
        and media.get("media", {}).get("readback") == "byteidentical",
        "Link-111 completed same-world predecessor drift")
    return {"card": card, "media": media}


def artifact_contract() -> dict[str, Any]:
    value = load(CONTRACT)
    artifact = value["artifact_successor"]
    require(artifact["exact_bytes"] == 1248
            and artifact["relocation_bytes"] == 4644
            and artifact["relocation_records"] == 387
            and artifact["capacity_bytes"] == 1499
            and artifact["headroom_bytes"] == 251,
            "full-span artifact contract drift")
    return artifact


def projected_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    ownership, full = BASE.projected_contracts()
    artifact = artifact_contract()
    far = ownership["mapped_far_service"]
    far["bank2"].update({
        "service_physical_end_exclusive":
            artifact["physical_end_exclusive"],
        "service_bytes": artifact["exact_bytes"],
        "post_service_static_bytes": artifact["post_service_static_bytes"],
        "post_service_headroom_bytes":
            artifact["post_service_headroom_bytes"],
    })
    far["map_tuple"]["mapped_service_cpu_end_exclusive"] = (
        artifact["cpu_end_exclusive"])
    symbols = [row for row in far["far_symbols"]
               if row["name"] == "c2_mapped_far_convergence_assembly_body"]
    require(len(symbols) == 1, "mapped-far symbolic owner is not unique")
    symbols[0]["bytes"] = artifact["exact_bytes"]

    additions = full["generated_linker_requirements"][
        "final_section_inventory_additions"]
    service = [row for row in additions
               if row["name"] == ".lisp65_c2_mapped_far_service"]
    relocation = [row for row in additions
                  if row["name"] == ".rela.lisp65_c2_mapped_far_service"]
    require(len(service) == len(relocation) == 1,
            "full-map full-span rows are not unique")
    service[0]["bytes"] = artifact["exact_bytes"]
    relocation[0].update({
        "bytes": artifact["relocation_bytes"],
        "bytes_authority": "emitted-full-span-micro-ELF-and-candidate",
        "emitted_records": artifact["relocation_records"],
    })
    ledger = [row for row in full["fixed_simultaneous_live_ledger"]
              if row.get("owner") == "mapped-bank2-far-service"]
    require(len(ledger) == 1, "mapped-far capacity owner is not unique")
    ledger[0].update({
        "service_cpu_end_exclusive": artifact["cpu_end_exclusive"],
        "service_physical_end_exclusive": artifact[
            "physical_end_exclusive"],
        "demand_bytes": artifact["exact_bytes"],
    })
    full["authorities"]["full_span_convergence"] = {
        "contract": bind(CONTRACT), "host_gate": bind(FIX.RECEIPT),
        "configuration": bind(CONFIG_DRIVER),
    }
    return ownership, full


def write_projections() -> None:
    ownership, full = projected_contracts()
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    PROJECTED_OWNERSHIP.write_bytes(canonical(ownership))
    PROJECTED_FULL_MAP.write_bytes(canonical(full))


ORIGINAL_CONFIGURE_FIX_SOURCE = MAP_FIX.configure_fix_source


def configure_full_span_source() -> dict[str, Any]:
    """Apply after every nested real-producer configure call."""
    if CONFIG.FEATURE in PRODUCT.CONVERGENCE_DEFINES:
        PRODUCT.CONVERGENCE_DEFINES = tuple(
            item for item in PRODUCT.CONVERGENCE_DEFINES
            if item != CONFIG.FEATURE)
    ORIGINAL_CONFIGURE_FIX_SOURCE()
    component = CONFIG.configure(PRODUCT)

    # The component report is provenance about this successor.  It must not
    # replace the complete source-owner projection consumed by downstream
    # qualification.  Recompute that projection after the real producer and
    # this successor have both configured the registry, then add the component
    # report under its own key.
    selected = tuple(str(scope["trigger"])
                     for scope in PRODUCT.SOURCE_OWNER_SCOPES)
    dummy = {"product_build_id_hex": "0x00000000",
             "artifacts": {"shelf": {"bytes": 0}}}
    projection = PRODUCT.source_owner_scope_gate(
        PRODUCT.definitions(dummy), selected, PRODUCT.source_list(selected))
    projection["components"] = {"full_span_convergence": component}
    return projection


MAP_FIX.configure_fix_source = configure_full_span_source


def configure() -> dict[str, Any]:
    require(PROJECTED_OWNERSHIP.is_file() and PROJECTED_FULL_MAP.is_file(),
            "candidate contract projections absent")
    # Link 112 inherits the clean-screen byte from Link 111.  Keep the
    # inherited MAP-mask checker on that emitted identity rather than its
    # pre-screen predecessor byte.
    BASE.OLD.BASE.EXPECTED_PROGRESS = LEASE.EXPECTED_LINKED_PROGRESS
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    BASE.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-phase9-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-phase9-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE.configure()
    return configure_full_span_source()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    value = {name: bind(path) for name, path in artifact_paths().items()}
    value["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    value["real_ABI_report"] = bind(ABI_REPORT)
    return value


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0 and token in result.stdout,
            f"fresh {label} red:\n{result.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(result.stdout.split())}


def host_gates() -> dict[str, Any]:
    return {
        "full_span": run_gate(
            [sys.executable, str(FIX.DRIVER), "check"],
            "CHECK PASS cases=18/18", "full-span convergence"),
        "span_pricing": run_gate(
            [sys.executable, str(HOST / "c2_v21_span_verification_pricing.py"),
             "check"], "winner=full-span", "span pricing"),
        "historical_v20_unbind": run_gate(
            [sys.executable, str(HOST /
                "c2_v20_building_heap_source_unbind_full_span_rebind_20260816.py"),
             "check"], "mutations=6", "v2.0 authority rebind"),
        "postlink_wrapper_contract": run_gate(
            [sys.executable, str(HOST / "c2_v21_postlink_wrapper_contract.py"),
             "check"], "CHECK PASS", "post-link wrapper contract"),
        "postlink_schema_contract": run_gate(
            [sys.executable, str(HOST / "c2_v21_postlink_schema_contract.py"),
             "check"], "CHECK PASS", "post-link schema contract"),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    source = configure()
    return {
        "format": "lisp65-c2.3-v2.1-full-span-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: full-span fix and real producer scope green; card armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "service_bytes": 1248, "service_headroom_bytes": 251,
            "relocation_bytes": 4644, "relocation_records": 387,
            "source_owner": source},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "host_gates": host_gates(),
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "contract": bind(CONTRACT), "predecessor": bind(PREDECESSOR),
            "predecessor_media": bind(MEDIA),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "full-span card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-first-byte-body": lambda x: x["configuration"]
            ["source_owner"].update(
                candidate_body="src/c2_mapped_far_convergence.s"),
        "two-body-owners": lambda x: x["configuration"]["source_owner"].update(
            single_body_owner=False),
        "pin-old-relocations": lambda x: x["configuration"].update(
            relocation_records=331),
        "drop-partial-gate": lambda x: x["host_gates"].pop("full_span"),
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "spend-card": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "full-span preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not INVOCATION.exists()
            and not PREFLIGHT_RECEIPT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "full-span product card is one-shot")
    write_projections()
    value = preflight_value()
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("full-span convergence card: PREFLIGHT PASS card=0/1 bytes=1248")


def produce_child() -> int:
    configure()
    return BASE.OLD.BASE.BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.OLD.BASE.BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.OLD.BASE.BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh full-span child {action} red:\n{result.stdout}")


def linked_product() -> dict[str, Any]:
    configure()
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    artifact = artifact_contract()
    section = truth.section(artifact["section"])
    relocation = truth.section(".rela.lisp65_c2_mapped_far_service")
    report = load(ABI_REPORT)
    transitive = report["transitive_callee_saved_preservation"]
    contractual = report["contractual_mapped_far_exit_preservation"]
    map_product = BASE.OLD.BASE.linked_product()
    reader = truth.symbol("c2_map_cpu_read")
    reader_section = truth.section(reader.section)
    reader_body = truth.section_bytes(reader.section)[
        reader.value - reader_section.address:
        reader.value - reader_section.address + reader.bytes]
    progress = reader_body[12:34]
    require(
        section.address == int(artifact["cpu_vma"], 0)
        and section.bytes == artifact["exact_bytes"]
        and relocation.bytes == artifact["relocation_bytes"]
        and relocation.bytes // 12 == artifact["relocation_records"]
        and transitive["status"]
            == "passed-actual-C-reachable-transitive-preservation"
        and transitive["model"]["unpreserved_callee_saved_writers"] == []
        and contractual["status"]
            == "passed-eight-contractual-service-exits-preserved"
        and contractual["model"]["inner_exits"] == 8
        and reader.bytes == 189 and progress == LEASE.EXPECTED_LINKED_PROGRESS,
        "linked full-span/ABI/screen identity drift")
    return {
        "status": "PASS: full-span successor linked and accepted",
        "mapped_far": {"address": f"0x{section.address:04x}",
            "bytes": section.bytes,
            "end_exclusive": f"0x{section.address + section.bytes:04x}",
            "headroom_bytes": artifact["headroom_bytes"]},
        "relocation_emission": {"bytes": relocation.bytes,
            "records": relocation.bytes // 12,
            "authority": "actual-linked-candidate"},
        "C_reachable_ASM_closure": transitive["model"],
        "contractual_service_exits": contractual["model"],
        "CPU_reader": map_product["reader"],
        "MAP_tuple_gate": map_product["tuple_gate"],
        "terminal_screen_lease": {"reader_bytes": reader.bytes,
            "post_phase_screen_code": "0x20", "post_phase_visible": False},
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-old-service": lambda x: x["mapped_far"].update(bytes=1086),
        "pin-old-relocation": lambda x: x["relocation_emission"].update(
            records=331),
        "lose-callee-save": lambda x: x["C_reachable_ASM_closure"].update(
            unpreserved_callee_saved_writers=["__rc20"]),
        "lose-exit": lambda x: x["contractual_service_exits"].update(
            inner_exits=7),
        "restore-screen-zero": lambda x: x["terminal_screen_lease"].update(
            post_phase_screen_code="0x30", post_phase_visible=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "linked full-span mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "full-span preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "full-span card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "fix": bind(FIX.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "full-span acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    product = linked_product()
    source_gate = producer["post_configuration_source_owner_gate"]
    mapped = [row for row in source_gate["scopes"]
              if row["name"] == "mapped-far-content-convergence"]
    require(
        len({os.getpid(), producer["pid"], scope["pid"],
             acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"].get("dependent_fixed_vmas") == 101
        and acceptance["VMA_golden"].get("dependent_free_derived_vmas") == 2
        and len(mapped) == 1 and mapped[0]["selected"] is True
        and "src/optional/c2_mapped_far_convergence_full_span.s"
            in mapped[0]["sources"]
        and "src/c2_mapped_far_convergence.s" not in mapped[0]["sources"],
        "full-span linked acceptance/source-owner drift")
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: sole full-span convergence card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "contract": bind(CONTRACT), "predecessor": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product,
        "source_owner": mapped[0],
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "Completion, same-world media closure, then D2 resume",
        "claim_limit": "One product card; no Completion/media/device run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("full-span convergence card: PASS card=1/1 bytes=1248 reloc=387")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-full-span-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: full-span card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no Completion or media.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "full-span Final Red drift")
        print("full-span convergence card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("full-span convergence card: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") == "PASS: sole full-span convergence card green"
        and value["attempt_accounting"]["cards_consumed"] == 1
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["linked_product"] == linked_product(),
        "full-span card receipt drift")
    print("full-span convergence card: CHECK PASS card=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "card", "check", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"full-span receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"full-span convergence card: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
