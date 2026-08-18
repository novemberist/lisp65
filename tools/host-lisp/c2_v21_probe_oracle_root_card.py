#!/usr/bin/env python3
"""Run the sole authorized product card for the mutable-read MAP-CPU root."""

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
import c2_v21_full_span_convergence_card as BASE  # noqa: E402
import c2_v21_probe_oracle_root_fix as FIX  # noqa: E402
import c2_v21_probe_oracle_root_product_config as CONFIG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-probe-oracle-root-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-probe-oracle-root-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-probe-oracle-root-card-final-red.json"
PREDECESSOR = ARCH / (
    "c2.3-v2.1-full-span-projection-artifact-replay-receipt.json")
MEDIA = BASE.LINK111.MEDIA
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
LINK96 = ROOT / "tools/host-lisp/c2_terminal_return_guard_media.py"

AUTHORIZATION = "20a5f4ec"
RECORDED_ON = "2026-08-16"
LINK = 113
FORMAT = "lisp65-c2.3-v2.1-probe-oracle-root-card-v1"


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
    raw, authority = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().split())
    for token in ("root fix authorized", "nine readers on map cpu reads",
                  "non-atomic probe fixtures as permanent gate",
                  "exactly one product card", "owner veto open"):
        require(token in text, f"root card authority token absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    card = load(PREDECESSOR)
    media = load(MEDIA)
    require(
        card.get("status") ==
            "PASS: Link-112 candidate-derived freight tail qualified"
        and card.get("execution_accounting", {}).get(
            "artifact_replays_run") == 1
        and media.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready"
        and media.get("media", {}).get("readback") == "byteidentical",
        "Link-112 green predecessor drift")
    return {"card": card, "media": media}


ORIGINAL_CONFIGURE_FIX_SOURCE = BASE.ORIGINAL_CONFIGURE_FIX_SOURCE


def configure_root_source() -> dict[str, Any]:
    """Reapply the real producer, full-span owner and root feature additively."""
    drop = {CONFIG.FEATURE, CONFIG.FULL.FEATURE}
    PRODUCT.CONVERGENCE_DEFINES = tuple(
        value for value in PRODUCT.CONVERGENCE_DEFINES if value not in drop)
    ORIGINAL_CONFIGURE_FIX_SOURCE()
    component = CONFIG.configure(PRODUCT)
    selected = tuple(str(scope["trigger"])
                     for scope in PRODUCT.SOURCE_OWNER_SCOPES)
    dummy = {"product_build_id_hex": "0x00000000",
             "artifacts": {"shelf": {"bytes": 0}}}
    projection = PRODUCT.source_owner_scope_gate(
        PRODUCT.definitions(dummy), selected, PRODUCT.source_list(selected))
    projection["components"] = {"probe_oracle_root": component}
    return projection


def configure() -> dict[str, Any]:
    require(PROJECTED_OWNERSHIP.is_file() and PROJECTED_FULL_MAP.is_file(),
            "root candidate projections absent")
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
    BASE.RECEIPT = BUILD / "unused-full-span-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-full-span-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE.configure_full_span_source = configure_root_source
    BASE.MAP_FIX.configure_fix_source = configure_root_source
    BASE.configure()
    return configure_root_source()


def write_projections() -> None:
    ownership, full = BASE.projected_contracts()
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    PROJECTED_OWNERSHIP.write_bytes(canonical(ownership))
    PROJECTED_FULL_MAP.write_bytes(canonical(full))


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
    pricing = load(FIX.PRICING)
    immutable = bind(FIX.IMMUTABLE_SERVICE)
    require(pricing["authority"]["assembly"] == immutable
            and pricing["linked_inventory"]["current_service_bytes"] == 1248,
            "immutable full-span service identity drift")
    return {
        "root_fix": run_gate(
            [sys.executable, str(HOST /
                "c2_v21_probe_oracle_root_fix.py"), "check"],
            "readers=9 partial=6", "probe-oracle root fix"),
        "full_span_immutable_service": {
            "status": "PASS", "bytes": 1248, "source": immutable,
            "semantic_boundary": "unchanged immutable boot spans only"},
        "Link96_loud_rebind": run_gate(
            [sys.executable, str(LINK96), "check"],
            "check: PASS mutations=16", "Link-96 loud r3 rebind"),
        "postlink_wrapper_contract": run_gate(
            [sys.executable, str(HOST / "c2_v21_postlink_wrapper_contract.py"),
             "check"], "CHECK PASS", "post-link wrapper contract"),
        "postlink_schema_contract": run_gate(
            [sys.executable, str(HOST / "c2_v21_postlink_schema_contract.py"),
             "check"], "CHECK PASS", "post-link schema contract"),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    root = load(FIX.RECEIPT)
    require(root.get("status") == FIX.STATUS
            and root["source_contract"]["reader_count"] == 9
            and root["non_atomic_fixtures"]["predecessor_false_accepts"] == 6,
            "root-fix host authority drift")
    source = configure()
    component = source["components"]["probe_oracle_root"]
    return {
        "format": "lisp65-c2.3-v2.1-probe-oracle-root-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: nine-reader MAP-CPU root green; card armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "mutable_readers": 9, "DMA_probe_jobs": 0,
            "DMA_primary_jobs": 0, "completion_signal_trusted": False,
            "source_owner": source, "component": component},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "host_gates": host_gates(),
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "predecessor": bind(PREDECESSOR), "predecessor_media": bind(MEDIA),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "probe-oracle root preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-reader": lambda x: x["configuration"].update(mutable_readers=8),
        "restore-probe": lambda x: x["configuration"].update(DMA_probe_jobs=1),
        "trust-completion": lambda x: x["configuration"].update(
            completion_signal_trusted=True),
        "drop-fixtures": lambda x: x["host_gates"].pop("root_fix"),
        "drop-Link96-rebind": lambda x: x["host_gates"].pop(
            "Link96_loud_rebind"),
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "spend-card": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "root preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "probe-oracle root card is one-shot")
    write_projections()
    value = preflight_value()
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("probe-oracle root card: PREFLIGHT PASS readers=9 card=0/1")


def produce_child() -> int:
    configure()
    return BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh probe-oracle root child {action} red:\n{result.stdout}")


def function_body(disassembly: str, name: str) -> str:
    marker = f"<{name}>:"
    require(disassembly.count(marker) == 1, f"linked function drift: {name}")
    tail = disassembly.split(marker, 1)[1]
    next_symbol = tail.find("\n\n")
    return tail if next_symbol < 0 else tail[:next_symbol]


def linked_product() -> dict[str, Any]:
    configure()
    inherited = BASE.linked_product()
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    ext = truth.symbol("ext_dma_read_or_abort")
    c2 = truth.symbol("c2_dma_read_or_abort")
    reader = truth.symbol("c2_map_cpu_read")
    service = truth.section(".lisp65_c2_mapped_far_service")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    disassembly = subprocess.run(
        [str(OBJDUMP), "-d", "--symbolize-operands", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    ext_body = function_body(disassembly, "ext_dma_read_or_abort")
    c2_body = function_body(disassembly, "c2_dma_read_or_abort")
    require(
        ext.bytes == 35 and c2.bytes == 27 and reader.bytes == 189
        and service.bytes == 1248
        and facade.bytes == 98 and padding.bytes == 19
        and padding.value == facade.address + 79
        and ext_body.count("<c2_map_cpu_read>") == 1
        and c2_body.count("<c2_map_cpu_read>") == 1
        and "vm_code_load_converged" not in ext_body
        and "vm_code_load_converged" not in c2_body,
        "linked candidate did not emit the priced MAP-CPU wrappers")
    functions = {
        "Bank4_EXT": ("ext_type", "ext_a", "ext_b", "ext_disk_get",
                       "str_read_byte"),
        "Bank5_symbols": ("sympool_read", "symval_get", "nameoff_get",
                           "symfn_ext_get"),
    }
    edges: dict[str, list[str]] = {}
    for lane, names in functions.items():
        target = "ext_dma_read_or_abort" if lane == "Bank4_EXT" \
            else "c2_dma_read_or_abort"
        rows = []
        for name in names:
            body = function_body(disassembly, name)
            require(f"<{target}>" in body,
                    f"mutable reader escaped root wrapper: {name}")
            rows.append(name)
        edges[lane] = rows
    return {
        "status": "PASS: nine mutable readers use synchronous MAP-CPU",
        "wrappers": {"ordinary": {"symbol": ext.name, "bytes": ext.bytes},
            "mapped_facade": {"symbol": c2.name, "bytes": c2.bytes},
            "execution_delta_from_Link112_bytes": (ext.bytes - 38) +
                (c2.bytes - 46)},
        "reader": {"address": f"0x{reader.value:04x}", "bytes": reader.bytes},
        "facade_padding": {"symbol": padding.name,
            "address": f"0x{padding.value:04x}", "bytes": padding.bytes,
            "facade_bytes": facade.bytes, "executed": False},
        "mutable_edges": edges, "mutable_reader_count": 9,
        "DMA_probe_jobs": 0, "DMA_primary_jobs": 0,
        "completion_signal_trusted": False,
        "immutable_service": {"bytes": service.bytes,
            "unchanged_from_Link112": service.bytes == 1248},
        "inherited": inherited,
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-reader": lambda x: x.update(mutable_reader_count=8),
        "restore-probe": lambda x: x.update(DMA_probe_jobs=1),
        "restore-primary-DMA": lambda x: x.update(DMA_primary_jobs=1),
        "trust-completion": lambda x: x.update(completion_signal_trusted=True),
        "grow-code": lambda x: x["wrappers"].update(
            execution_delta_from_Link112_bytes=0),
        "change-service": lambda x: x["immutable_service"].update(bytes=1086),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        if candidate != value:
            rejected.append(name)
    require(rejected == list(cases), "linked root mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "root preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "probe-oracle root card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "fix": bind(FIX.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "root acceptance changed frozen artifacts")
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
        and acceptance["VMA_golden"].get(
            "dependent_free_derived_vmas") == 2
        and len(mapped) == 1 and mapped[0]["selected"] is True
        and CONFIG.FEATURE in mapped[0]["defines"]
        and product["wrappers"]["execution_delta_from_Link112_bytes"] == -22,
        "root linked acceptance drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: sole probe-oracle root product card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "predecessor": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product,
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "source_owner": mapped[0],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "linked-image DMA content-reader structural-absence gate",
        "claim_limit": "One product card; Completion, media and device not run.",
    }
    RECEIPT.write_bytes(canonical(value))
    print("probe-oracle root card: PASS card=1/1 readers=9 delta=-22")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-probe-oracle-root-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: probe-oracle root card returns to owner",
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
                "probe-oracle root Final Red drift")
        print("probe-oracle root card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("probe-oracle root card: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") ==
            "PASS: sole probe-oracle root product card green"
        and value["attempt_accounting"]["cards_consumed"] == 1
        and value["linked_product"] == linked_product()
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"],
        "probe-oracle root green receipt drift")
    print("probe-oracle root card: CHECK PASS card=1/1 readers=9 delta=-22")


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
                print(f"probe-oracle root Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"probe-oracle root card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
