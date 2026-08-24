#!/usr/bin/env python3
"""Prove the authorized MAP-CPU root fix before its sole product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_probe_oracle_root_product_config as CONFIG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
MEM = ROOT / "src/mem.c"
DMA = ROOT / "src/c2_platform_dma.c"
HEADER = ROOT / "src/c2_platform_dma.h"
IMMUTABLE_SERVICE = ROOT / "src/optional/c2_mapped_far_convergence_full_span.s"
CONFIG_DRIVER = ROOT / "tools/host-lisp/c2_v21_probe_oracle_root_product_config.py"
PRICING = ARCH / "c2.3-v2.1-probe-oracle-fix-pricing-receipt.json"
CAPTURE = ARCH / "c2.3-v2.1-link112-d2-probe-oracle-capture-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-probe-oracle-root-fix-receipt.json"
PADDING_RECEIPT = ARCH / (
    "c2.3-v2.1-probe-oracle-root-facade-padding-receipt.json")

AUTHORIZATION = "20a5f4ec"
FORMAT = "lisp65-c2.3-v2.1-probe-oracle-root-fix-v1"
STATUS = "HOST-GREEN: NINE-MUTABLE-READERS-USE-MAP-CPU; CARD-PENDING"
PADDING_STATUS = "HOST-GREEN: EXPLICIT-NAMED-19-BYTE-FACADE-PADDING"
PADDING_AUTHORIZED_CHANGED_PATHS = [
    "authority.checker.bytes",
    "authority.checker.sha256",
    "authority.configuration.bytes",
    "authority.configuration.sha256",
    "configuration.component.facade_padding",
    "configuration.source_owner.sources",
]


class RootFixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RootFixError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        result: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                result.append(child)
            else:
                result.extend(changed_paths(old[key], new[key], child))
        return result
    return [] if old == new else [prefix]


def successor_contract(historical: dict[str, Any], current: dict[str, Any],
                       padding: dict[str, Any]) -> dict[str, Any]:
    """Validate the successor from current authorities, never its snapshot."""
    successor = padding.get("root_fix_successor", {})
    actual_changed = changed_paths(historical, current)
    require(
        padding.get("status") == PADDING_STATUS
        and successor.get("historical_receipt") == bind(RECEIPT)
        and successor.get("historical_receipt_rewritten") is False
        and successor.get("semantic_root_claim_changed") is False
        and successor.get("authorized_changed_paths") ==
            PADDING_AUTHORIZED_CHANGED_PATHS
        and actual_changed == PADDING_AUTHORIZED_CHANGED_PATHS,
        "root-fix padding successor derivation drift")
    return {
        "current_projection": bind_raw(RECEIPT, canonical(current)),
        "actual_changed_paths": actual_changed,
    }


def successor_projection_source_gate(source: str | None = None) -> None:
    """A sealed successor snapshot is a witness, never current authority."""
    body = (Path(__file__).read_text(encoding="utf-8")
            if source is None else source)
    start = body.index("def successor_contract(")
    stop = body.index("\n\ndef successor_projection_source_gate", start)
    contract = body[start:stop]
    require('successor.get("current_projection")' not in contract
            and 'successor["current_projection"]' not in contract,
            "persisted root-fix successor projection became authority")


def successor_mutations(historical: dict[str, Any], current: dict[str, Any],
                        padding: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    changed = deepcopy(current)
    changed["priced_geometry"]["new_reader_bytes"] = 1
    try:
        successor_contract(historical, changed, padding)
    except RootFixError:
        rejected.append("derive-disagrees-with-sealed-claim")
    source = Path(__file__).read_text(encoding="utf-8")
    marker = "    actual_changed = changed_paths(historical, current)"
    mutant = source.replace(
        marker,
        marker + '\n    successor.get("current_projection")', 1)
    try:
        successor_projection_source_gate(mutant)
    except RootFixError:
        rejected.append("restore-persisted-successor-authority")
    require(rejected == ["derive-disagrees-with-sealed-claim",
                         "restore-persisted-successor-authority"],
            "root-fix successor mutation survived")
    return rejected


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
    for token in (
            "root fix authorized", "nine readers on map cpu reads",
            "non-atomic probe fixtures as permanent gate",
            "exactly one product card", "historical link-96 live-plan drift"):
        require(token in text, f"root-fix authority token absent: {token}")
    return authority


def between(source: str, begin: str, end: str) -> str:
    require(source.count(begin) == 1 and source.count(end) >= 1,
            f"source boundary drift: {begin}")
    start = source.index(begin)
    stop = source.index(end, start)
    return source[start:stop]


def source_contract(mem_source: str | None = None,
                    dma_source: str | None = None,
                    header_source: str | None = None) -> dict[str, Any]:
    mem = MEM.read_text(encoding="utf-8") if mem_source is None else mem_source
    dma = DMA.read_text(encoding="utf-8") if dma_source is None else dma_source
    header = (HEADER.read_text(encoding="utf-8")
              if header_source is None else header_source)
    ext = between(mem, "#if defined(LISP65_C2_MUTABLE_CPU_READS)",
                  "#elif defined(LISP65_DMA_CONTENT_CONVERGENCE)")
    c2 = between(dma, "#ifdef LISP65_C2_MUTABLE_CPU_READS", "#else")
    require(
        "uint32_t physical = (uint32_t)source |" in ext
        and "((uint32_t)source_bank << 16)" in ext
        and "c2_map_cpu_read(physical, destination, length)" in ext
        and "vm_code_load_converged" not in ext
        and "uint32_t physical = (uint32_t)offset |" in c2
        and "((uint32_t)bank << 16)" in c2
        and "c2_map_cpu_read(physical, destination, length)" in c2
        and "vm_code_load_converged" not in c2,
        "one mutable root wrapper still trusts DMA completion")
    require(
        "uint8_t c2_map_cpu_read(uint32_t source, uint8_t *destination," in header
        and "#ifdef LISP65_C2_MUTABLE_CPU_READS" in header,
        "private MAP-CPU ABI declaration drift")
    ext_calls = (
        "ext_type", "ext_a", "ext_b", "ext_disk_get", "str_read_byte")
    c2_calls = (
        "sympool_read", "symval_get", "nameoff_get", "symfn_ext_get")
    require(all(mem.count(name) >= 1 for name in ext_calls)
            and all(dma.count(name) >= 1 for name in c2_calls),
            "nine mutable reader call sites drift")
    return {
        "feature": CONFIG.FEATURE,
        "ordinary_wrapper": "MAP-CPU",
        "mapped_facade_wrapper": "MAP-CPU",
        "physical_address_formula": "offset | bank<<16",
        "mutable_readers": {"Bank4_EXT": list(ext_calls),
                            "Bank5_symbols": list(c2_calls)},
        "reader_count": len(ext_calls) + len(c2_calls),
        "DMA_probe_jobs": 0, "DMA_primary_jobs": 0,
        "completion_signal_trusted": False,
    }


def configuration_contract() -> dict[str, Any]:
    value = CONFIG.configure(PRODUCT)
    scopes = [row for row in PRODUCT.SOURCE_OWNER_SCOPES
              if row.get("name") == "mapped-far-content-convergence"]
    require(
        len(scopes) == 1 and CONFIG.FEATURE in scopes[0]["defines"]
        and CONFIG.FEATURE in PRODUCT.CONVERGENCE_DEFINES
        and value["mutable_reader_count"] == 9
        and value["DMA_probe_jobs"] == 0
        and value["DMA_completion_trust"] is False,
        "real producer root configuration drift")
    selected = PRODUCT.source_list(PRODUCT.CONVERGENCE_DEFINES)
    gate = PRODUCT.source_owner_scope_gate(
        PRODUCT.definitions({"product_build_id_hex": "0x00000000",
            "artifacts": {"shelf": {"bytes": 0}}}),
        PRODUCT.CONVERGENCE_DEFINES, selected)
    mapped = [row for row in gate["scopes"]
              if row["name"] == "mapped-far-content-convergence"]
    require(len(mapped) == 1 and mapped[0]["selected"] is True
            and CONFIG.FEATURE in mapped[0]["defines"],
            "source-owner projection lost root feature")
    return {"component": value, "source_owner": mapped[0]}


def partial_transfer_fixtures() -> dict[str, Any]:
    source = bytes.fromhex("3b0601012f0153")
    stale = bytes.fromhex("0b000000000000")
    shapes = {
        "marker-before-any-probe-byte": stale,
        "probe-prefix-only": source[:1] + stale[1:],
        "probe-tail-only": stale[:-1] + source[-1:],
    }
    rows: list[dict[str, Any]] = []
    false_predecessor = 0
    for lane in ("D700", "D705"):
        for name, probe_view in shapes.items():
            predecessor_destination = probe_view
            predecessor_accepts = predecessor_destination == probe_view
            predecessor_correct = predecessor_destination == source
            root_destination = bytes(source)
            root_accepts = root_destination == source
            false_predecessor += int(predecessor_accepts
                                     and not predecessor_correct)
            rows.append({
                "lane": lane, "shape": name,
                "probe_view": probe_view.hex(),
                "probe_job_atomic": False,
                "payload_job_atomic": False,
                "predecessor_false_accept": (
                    predecessor_accepts and not predecessor_correct),
                "root_uses_probe": False,
                "root_result_is_source": root_accepts,
            })
    require(len(rows) == 6 and false_predecessor == 6
            and all(row["root_result_is_source"] for row in rows),
            "partial probe fixture matrix drift")
    return {
        "lanes": 2, "shapes_per_lane": 3, "cases": len(rows),
        "atomic_DMA_fixture_allowed": False,
        "probe_jobs_modeled_partial": True,
        "payload_jobs_modeled_partial": True,
        "predecessor_false_accepts": false_predecessor,
        "root_false_accepts": 0, "rows": rows,
    }


def derive() -> dict[str, Any]:
    pricing = load(PRICING)
    capture = load(CAPTURE)
    require(pricing["decision"]["winner"] ==
            "root-map-cpu-for-all-nine-mutable-readers"
            and pricing["code_prices"]["root"]
                ["target_shaped_total_executable_delta_bytes"] == -18
            and pricing["authority"]["assembly"] == bind(IMMUTABLE_SERVICE)
            and pricing["linked_inventory"]["current_service_bytes"] == 1248
            and capture["claim_boundary"]
                ["fresh_name_reproduces_same_mechanism"] is True,
            "root price/capture authority drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "source_contract": source_contract(),
        "configuration": configuration_contract(),
        "non_atomic_fixtures": partial_transfer_fixtures(),
        "priced_geometry": {
            "target_shaped_execution_delta_bytes": -18,
            "new_reader_bytes": 0, "new_vector_bytes": 0,
            "mapped_service_growth_bytes": 0,
            "card_must_bind_actual_emitted_bytes": True,
        },
        "authority": {"owner": authorization(), "pricing": bind(PRICING),
            "capture": bind(CAPTURE), "mem": bind(MEM), "DMA": bind(DMA),
            "header": bind(HEADER), "configuration": bind(CONFIG_DRIVER),
            "immutable_full_span_service": bind(IMMUTABLE_SERVICE),
            "checker": bind(Path(__file__))},
        "execution_accounting": {"WPLTO": 0, "product_links": 0,
            "cards_consumed": 0, "product_bytes_changed": 0,
            "device_contacts": 0, "device_resumes": 0},
        "next": "exactly one Link-113 product card",
        "claim_limit": "Host root fix only; card, Completion, media and device not run.",
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    source = value["source_contract"]
    fixtures = value["non_atomic_fixtures"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "root-fix identity drift")
    require(source["reader_count"] == 9 and source["DMA_probe_jobs"] == 0
            and source["DMA_primary_jobs"] == 0
            and source["completion_signal_trusted"] is False,
            "root transport weakened")
    require(fixtures["atomic_DMA_fixture_allowed"] is False
            and fixtures["probe_jobs_modeled_partial"] is True
            and fixtures["payload_jobs_modeled_partial"] is True
            and fixtures["predecessor_false_accepts"] == 6
            and fixtures["root_false_accepts"] == 0,
            "non-atomic fixture contract weakened")
    require(value["priced_geometry"] == {
        "target_shaped_execution_delta_bytes": -18,
        "new_reader_bytes": 0, "new_vector_bytes": 0,
        "mapped_service_growth_bytes": 0,
        "card_must_bind_actual_emitted_bytes": True},
        "price/card boundary drift")
    require(value["execution_accounting"] == {"WPLTO": 0,
        "product_links": 0, "cards_consumed": 0,
        "product_bytes_changed": 0, "device_contacts": 0,
        "device_resumes": 0}, "host-only boundary drift")


def source_mutations() -> list[str]:
    mem = MEM.read_text(encoding="utf-8")
    dma = DMA.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    cases = {
        "drop-ext-root-feature": (mem.replace(
            "#if defined(LISP65_C2_MUTABLE_CPU_READS)", "#if 0", 1), dma, header),
        "drop-c2-root-feature": (mem, dma.replace(
            "#ifdef LISP65_C2_MUTABLE_CPU_READS", "#ifdef NEVER", 1), header),
        "ext-trusts-DMA": (mem.replace(
            "c2_map_cpu_read(physical, destination, length)",
            "vm_code_load_converged(source_bank, source, length, destination)", 1),
            dma, header),
        "c2-trusts-DMA": (mem, dma.replace(
            "c2_map_cpu_read(physical, destination, length)",
            "vm_code_load_converged(bank, offset, length, destination)", 1), header),
        "drop-bank-byte": (mem.replace(
            "((uint32_t)source_bank << 16)", "((uint32_t)source_bank << 8)", 1),
            dma, header),
        "drop-private-ABI": (mem, dma, header.replace(
            "uint8_t c2_map_cpu_read(uint32_t source, uint8_t *destination,",
            "uint8_t missing_reader(uint32_t source, uint8_t *destination,", 1)),
    }
    rejected: list[str] = []
    for name, (mem_value, dma_value, header_value) in cases.items():
        try:
            source_contract(mem_value, dma_value, header_value)
        except RootFixError:
            rejected.append(name)
    require(rejected == list(cases), "root source mutation survived")
    return rejected


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-reader": lambda x: x["source_contract"].update(reader_count=8),
        "restore-probe": lambda x: x["source_contract"].update(DMA_probe_jobs=1),
        "restore-primary-DMA": lambda x: x["source_contract"].update(
            DMA_primary_jobs=1),
        "trust-completion": lambda x: x["source_contract"].update(
            completion_signal_trusted=True),
        "atomize-probe": lambda x: x["non_atomic_fixtures"].update(
            atomic_DMA_fixture_allowed=True),
        "hide-predecessor-false": lambda x: x["non_atomic_fixtures"].update(
            predecessor_false_accepts=0),
        "break-root": lambda x: x["non_atomic_fixtures"].update(
            root_false_accepts=1),
        "invent-vector": lambda x: x["priced_geometry"].update(
            new_vector_bytes=3),
        "spend-card": lambda x: x["execution_accounting"].update(
            cards_consumed=1),
        "touch-device": lambda x: x["execution_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except RootFixError:
            rejected.append(name)
    require(rejected == list(cases), "root receipt mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["source_mutations_rejected"] = source_mutations()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        historical = load(RECEIPT)
        if historical != value:
            padding = load(PADDING_RECEIPT)
            successor_projection_source_gate()
            successor_contract(historical, value, padding)
            successor_mutations(historical, value, padding)
        else:
            require(historical == value, "root-fix receipt stale")
    else:
        require(len(value["source_mutations_rejected"]) == 6
                and len(value["mutations_rejected"]) == 10,
                "root-fix mutation count drift")
        historical = load(RECEIPT)
        padding = load(PADDING_RECEIPT)
        successor_projection_source_gate()
        successor_contract(historical, value, padding)
        require(len(successor_mutations(historical, value, padding)) == 2,
                "root-fix successor mutation count drift")
    print(f"probe-oracle root fix: PASS action={action} readers=9 "
          f"partial=6 mutations=18")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RootFixError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"probe-oracle root fix: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
