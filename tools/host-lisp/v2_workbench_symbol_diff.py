#!/usr/bin/env python3
"""Generate and verify the CP5 Workbench MOS symbol-difference audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config/v2-workbench-symbol-diff-policy.json"
DEFAULT_REPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-symbol-diff-report.json"
)
DEFAULT_NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
NM_RE = re.compile(r"^\s*([0-9]+)\s+([0-9]+)\s+(\S)\s+(.+?)\s*$")


class AuditError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise AuditError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except AuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise AuditError(f"{label} keys drift: {actual}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _parse_hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-f]+", value):
        raise AuditError(f"{label} must be a lowercase hexadecimal string")
    return int(value, 16)


def validate_policy(policy: dict[str, Any]) -> None:
    _exact(
        policy,
        {
            "format", "version", "id", "status", "product_measurement",
            "layout_neutral_attempt", "attribution", "planning",
            "selected_strategy", "failure_menu",
        },
        "policy",
    )
    if (
        policy["format"] != "lisp65-v2-workbench-symbol-diff-policy-v1"
        or policy["version"] != 1
        or policy["id"] != "cp5-workbench-resident-growth"
        or policy["status"] != "product-link-blocked"
    ):
        raise AuditError("policy identity/status drift")
    product = _exact(
        policy["product_measurement"],
        {
            "metric", "baseline_bss_end", "baseline_runtime_overlay_vma",
            "baseline_post_boot_reserve_bytes", "candidate_bss_end",
            "candidate_runtime_overlay_vma", "candidate_post_boot_reserve_bytes",
            "resident_floor_delta_bytes", "runtime_overlay_vma_limit",
            "runtime_overlay_vma_deficit_bytes", "post_boot_reserve_min_bytes",
            "post_boot_reserve_deficit_bytes", "physical_ram_overflow_bytes",
            "boot_overlay_end_overflow_bytes", "candidate_elf_state",
        },
        "product measurement",
    )
    bss1 = _parse_hex(product["baseline_bss_end"], "baseline_bss_end")
    bss2 = _parse_hex(product["candidate_bss_end"], "candidate_bss_end")
    vma1 = _parse_hex(product["baseline_runtime_overlay_vma"], "baseline VMA")
    vma2 = _parse_hex(product["candidate_runtime_overlay_vma"], "candidate VMA")
    limit = _parse_hex(product["runtime_overlay_vma_limit"], "VMA limit")
    if product != {
        "metric": "real-lto-icf-product-link-resident-floor",
        "baseline_bss_end": "0xc34e",
        "baseline_runtime_overlay_vma": "0xc350",
        "baseline_post_boot_reserve_bytes": 1800,
        "candidate_bss_end": "0xd094",
        "candidate_runtime_overlay_vma": "0xd096",
        "candidate_post_boot_reserve_bytes": -1598,
        "resident_floor_delta_bytes": 3398,
        "runtime_overlay_vma_limit": "0xc356",
        "runtime_overlay_vma_deficit_bytes": 3392,
        "post_boot_reserve_min_bytes": 1536,
        "post_boot_reserve_deficit_bytes": 3134,
        "physical_ram_overflow_bytes": 148,
        "boot_overlay_end_overflow_bytes": 1766,
        "candidate_elf_state": "link-failed-before-product-elf",
    }:
        raise AuditError("pinned product measurement drift")
    if bss2 - bss1 != 3398 or vma2 - limit != 3392 or vma1 > limit:
        raise AuditError("product measurement arithmetic drift")

    attempt = _exact(
        policy["layout_neutral_attempt"],
        {
            "status", "scope", "accepted_changes", "rejected_changes",
            "measurement", "correctness",
        },
        "layout-neutral attempt",
    )
    if (
        attempt["status"] != "closed-insufficient-reclaim"
        or attempt["scope"] != "single-layout-neutral-attempt"
        or attempt["accepted_changes"] != [
            "shared-string-construction-transaction",
            "array-based-vm-native-call",
        ]
        or attempt["rejected_changes"] != [{
            "id": "service-dispatch-table",
            "reason": "real-mos-no-lto-net-growth",
            "delta_bytes": 61,
        }]
    ):
        raise AuditError("layout-neutral attempt identity/scope drift")
    measurement = _exact(
        attempt["measurement"],
        {
            "metric", "baseline_bss_end", "baseline_runtime_overlay_vma",
            "baseline_post_boot_reserve_bytes", "baseline_elf_sha256",
            "candidate_bss_end", "candidate_runtime_overlay_vma",
            "candidate_post_boot_reserve_bytes", "candidate_elf_sha256",
            "resident_floor_delta_bytes", "resident_delta_reclaim_bytes",
            "candidate_endpoint_reclaim_bytes", "minimum_reclaim_shortfall_bytes",
            "runtime_overlay_vma_deficit_bytes", "post_boot_reserve_deficit_bytes",
            "physical_ram_headroom_bytes", "candidate_elf_state",
        },
        "layout-neutral measurement",
    )
    expected_measurement = {
        "metric": "real-lto-icf-product-link-resident-floor",
        "baseline_bss_end": "0xc34c",
        "baseline_runtime_overlay_vma": "0xc34e",
        "baseline_post_boot_reserve_bytes": 1800,
        "baseline_elf_sha256": "0c231afb6e1fbcd193654d972b760a235c8c1a5bc3039d0625f8ae120c385f56",
        "candidate_bss_end": "0xcc77",
        "candidate_runtime_overlay_vma": "0xcc78",
        "candidate_post_boot_reserve_bytes": -546,
        "candidate_elf_sha256": "70d6585a59f6a18969a56d3d6e73a32a9822fd00128889a0b7a387b6c1f041a4",
        "resident_floor_delta_bytes": 2347,
        "resident_delta_reclaim_bytes": 1051,
        "candidate_endpoint_reclaim_bytes": 1053,
        "minimum_reclaim_shortfall_bytes": 2348,
        "runtime_overlay_vma_deficit_bytes": 2338,
        "post_boot_reserve_deficit_bytes": 2082,
        "physical_ram_headroom_bytes": 904,
        "candidate_elf_state": "relaxed-limit-diagnostic-elf",
    }
    if measurement != expected_measurement:
        raise AuditError("layout-neutral measurement drift")
    attempt_bss1 = _parse_hex(measurement["baseline_bss_end"], "attempt baseline bss")
    attempt_bss2 = _parse_hex(measurement["candidate_bss_end"], "attempt candidate bss")
    attempt_vma2 = _parse_hex(measurement["candidate_runtime_overlay_vma"], "attempt candidate VMA")
    if (
        attempt_bss2 - attempt_bss1 != measurement["resident_floor_delta_bytes"]
        or product["resident_floor_delta_bytes"] - measurement["resident_floor_delta_bytes"]
        != measurement["resident_delta_reclaim_bytes"]
        or _parse_hex(product["candidate_bss_end"], "initial candidate bss") - attempt_bss2
        != measurement["candidate_endpoint_reclaim_bytes"]
        or 3399 - measurement["resident_delta_reclaim_bytes"]
        != measurement["minimum_reclaim_shortfall_bytes"]
        or attempt_vma2 - limit != measurement["runtime_overlay_vma_deficit_bytes"]
        or 0xd000 - attempt_vma2 != measurement["physical_ram_headroom_bytes"]
        or measurement["candidate_post_boot_reserve_bytes"]
        != measurement["physical_ram_headroom_bytes"] - 1450
        or 1536 - measurement["candidate_post_boot_reserve_bytes"]
        != measurement["post_boot_reserve_deficit_bytes"]
        or not SHA_RE.fullmatch(measurement["baseline_elf_sha256"])
        or not SHA_RE.fullmatch(measurement["candidate_elf_sha256"])
    ):
        raise AuditError("layout-neutral measurement arithmetic drift")
    correctness = _exact(
        attempt["correctness"],
        {
            "strict_arity_preserved", "string_atomicity_preserved",
            "layout_changed", "resident_island_changed", "runtime_slot_changed",
        },
        "layout-neutral correctness",
    )
    if correctness != {
        "strict_arity_preserved": True,
        "string_atomicity_preserved": True,
        "layout_changed": False,
        "resident_island_changed": False,
        "runtime_slot_changed": False,
    }:
        raise AuditError("layout-neutral correctness contract drift")

    attr = _exact(
        policy["attribution"],
        {
            "metric", "optimization", "limitations", "required_positive_deltas",
            "required_negative_deltas", "groups", "rank_limit",
        },
        "attribution",
    )
    if (
        attr["metric"] != "paired-real-mos-relocatable-elf-named-symbol-delta"
        or attr["optimization"] != "-Oz-fno-lto"
        or attr["limitations"]
        != ["no-lto", "no-icf", "no-product-section-gc", "indicator-not-product-footprint"]
        or not isinstance(attr["rank_limit"], int)
        or attr["rank_limit"] < 20
    ):
        raise AuditError("attribution semantics drift")
    for key in ("required_positive_deltas", "required_negative_deltas", "groups"):
        if not isinstance(attr[key], dict) or not attr[key]:
            raise AuditError(f"attribution {key} must be a non-empty object")
    if any(type(value) is not int or value <= 0 for value in attr["required_positive_deltas"].values()):
        raise AuditError("positive attribution pins are invalid")
    if any(type(value) is not int or value >= 0 for value in attr["required_negative_deltas"].values()):
        raise AuditError("negative attribution pins are invalid")
    for pattern in attr["groups"].values():
        try:
            re.compile(pattern)
        except (TypeError, re.error) as exc:
            raise AuditError(f"invalid attribution group regex: {pattern!r}") from exc

    planning = _exact(
        policy["planning"],
        {
            "policy", "minimum_measured_reclaim_for_net_negative_bytes",
            "pinned_planning_reclaim_bytes", "estimates_may_promote",
            "promotion_metric",
        },
        "planning",
    )
    if planning != {
        "policy": "pessimistic-power-of-two-headroom",
        "minimum_measured_reclaim_for_net_negative_bytes": 3399,
        "pinned_planning_reclaim_bytes": 4096,
        "estimates_may_promote": False,
        "promotion_metric": "real-lto-icf-product-link-resident-floor",
    }:
        raise AuditError("pessimistic planning pin drift")
    strategy = _exact(
        policy["selected_strategy"],
        {
            "id", "runtime_core", "release_path", "release_product",
            "active_work_lines", "layout_option", "new_language_families",
            "new_ap8_blocks",
        },
        "selected_strategy",
    )
    layout_option = _exact(
        strategy["layout_option"],
        {"status", "available_bytes", "vma_deficit_bytes", "reserve_deficit_bytes"},
        "selected_strategy.layout_option",
    )
    if strategy != {
        "id": "runtime-proof-parallel-workbench-de-residentization",
        "runtime_core": "internal-proof-only",
        "release_path": "workbench-de-residentization",
        "release_product": "lisp65-workbench-v2",
        "active_work_lines": [
            "runtime-core-proof",
            "workbench-de-residentization",
        ],
        "layout_option": {
            "status": "rejected-insufficient",
            "available_bytes": 1302,
            "vma_deficit_bytes": 2338,
            "reserve_deficit_bytes": 2082,
        },
        "new_language_families": "forbidden",
        "new_ap8_blocks": "forbidden",
    } or not (
        layout_option["available_bytes"] < layout_option["vma_deficit_bytes"]
        and layout_option["available_bytes"] < layout_option["reserve_deficit_bytes"]
    ):
        raise AuditError("selected proof/release strategy drift")
    menu = policy["failure_menu"]
    if not isinstance(menu, list) or [item.get("id") for item in menu if isinstance(item, dict)] != [
        "a-layout-island-slice-cap", "b-de-residentization", "c-runtime-core-first",
    ]:
        raise AuditError("failure menu identity/order drift")
    for index, item in enumerate(menu):
        _exact(
            item,
            {"id", "kind", "scope", "status", "release_effect", "requires_user_approval"},
            f"failure_menu[{index}]",
        )
        if item["requires_user_approval"] is not True:
            raise AuditError("failure menu must remain architecture-gated")
    if menu != [
        {
            "id": "a-layout-island-slice-cap",
            "kind": "rejected-layout-decision",
            "scope": "resident-island-plus-runtime-slice-cap-insufficient",
            "status": "rejected-insufficient",
            "release_effect": "none",
            "requires_user_approval": True,
        },
        {
            "id": "b-de-residentization",
            "kind": "resident-code-reduction",
            "scope": "move-or-rewrite-cold-capability-and-service-code-without-layout-drift",
            "status": "selected-release-path",
            "release_effect": "none-before-workbench-g5",
            "requires_user_approval": True,
        },
        {
            "id": "c-runtime-core-first",
            "kind": "internal-proof-sequencing",
            "scope": "prove-runtime-core-while-workbench-de-residentization-remains-release-critical",
            "status": "selected-proof-line",
            "release_effect": "none",
            "requires_user_approval": True,
        },
    ]:
        raise AuditError("failure menu decision state drift")


def _mos_elf(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"{label} must be a regular non-symlink ELF: {path}")
    header = path.read_bytes()[:20]
    if len(header) < 20 or header[:4] != b"\x7fELF" or header[4:6] != b"\x01\x01":
        raise AuditError(f"{label} is not an ELF32 little-endian file")
    machine = struct.unpack_from("<H", header, 18)[0]
    if machine != 0x1966:
        raise AuditError(f"{label} is not a MOS ELF (e_machine=0x{machine:04x})")
    return {"sha256": _sha_file(path), "elf_class": 32, "endian": "little", "machine": "0x1966"}


def _symbols(nm: Path, elf: Path) -> dict[str, dict[str, Any]]:
    try:
        result = subprocess.run(
            [str(nm), "--defined-only", "--print-size", "--radix=d", str(elf)],
            check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise AuditError(f"cannot execute llvm-nm: {exc}") from exc
    if result.returncode:
        raise AuditError(f"llvm-nm failed for {elf}: {result.stderr.strip()}")
    symbols: dict[str, dict[str, Any]] = {}
    for line in result.stdout.splitlines():
        match = NM_RE.match(line)
        if not match:
            continue
        address, size, symbol_type, name = match.groups()
        record = {"address": int(address), "size": int(size), "type": symbol_type}
        prior = symbols.get(name)
        if prior is None or record["size"] > prior["size"]:
            symbols[name] = record
    if not symbols:
        raise AuditError(f"llvm-nm returned no sized definitions for {elf}")
    return symbols


def _symbol_diff(baseline: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for name in set(baseline) | set(candidate):
        before = baseline.get(name, {}).get("size", 0)
        after = candidate.get(name, {}).get("size", 0)
        delta = after - before
        if delta:
            records.append({"name": name, "baseline_bytes": before, "candidate_bytes": after, "delta_bytes": delta})
    return sorted(records, key=lambda item: (-item["delta_bytes"], item["name"]))


def generate(policy_path: Path, baseline_elf: Path, candidate_elf: Path, nm: Path) -> dict[str, Any]:
    policy = _load(policy_path, "symbol-diff policy")
    validate_policy(policy)
    inputs = {
        "baseline": _mos_elf(baseline_elf, "baseline attribution ELF"),
        "candidate": _mos_elf(candidate_elf, "candidate attribution ELF"),
    }
    records = _symbol_diff(_symbols(nm, baseline_elf), _symbols(nm, candidate_elf))
    by_name = {record["name"]: record["delta_bytes"] for record in records}
    attr = policy["attribution"]
    for direction in ("required_positive_deltas", "required_negative_deltas"):
        for name, expected in attr[direction].items():
            if by_name.get(name) != expected:
                raise AuditError(f"pinned attribution delta drift: {name} expected {expected} got {by_name.get(name)}")
    positive = [item for item in records if item["delta_bytes"] > 0]
    negative = sorted(
        (item for item in records if item["delta_bytes"] < 0),
        key=lambda item: (item["delta_bytes"], item["name"]),
    )
    group_totals = {}
    for name, pattern in attr["groups"].items():
        regex = re.compile(pattern)
        selected = [item for item in records if regex.search(item["name"])]
        group_totals[name] = {
            "named_symbols": len(selected),
            "net_delta_bytes": sum(item["delta_bytes"] for item in selected),
            "positive_delta_bytes": sum(max(0, item["delta_bytes"]) for item in selected),
        }
    limit = attr["rank_limit"]
    report = {
        "format": "lisp65-v2-workbench-symbol-diff-report-v1",
        "policy_sha256": _sha_bytes(_canonical(policy)),
        "status": "blocked",
        "product_measurement": policy["product_measurement"],
        "layout_neutral_attempt": policy["layout_neutral_attempt"],
        "attribution": {
            "metric": attr["metric"],
            "optimization": attr["optimization"],
            "limitations": attr["limitations"],
            "inputs": inputs,
            "net_named_delta_bytes": sum(item["delta_bytes"] for item in records),
            "positive_named_delta_bytes": sum(item["delta_bytes"] for item in positive),
            "negative_named_delta_bytes": sum(item["delta_bytes"] for item in negative),
            "group_totals": group_totals,
            "ranked_positive_deltas": positive[:limit],
            "ranked_negative_deltas": negative[:limit],
        },
        "planning": policy["planning"],
        "selected_strategy": policy["selected_strategy"],
        "failure_menu": policy["failure_menu"],
        "conclusion": "cp5-workbench-product-link-remains-blocked",
    }
    validate_report(policy, report)
    return report


def validate_report(policy: dict[str, Any], report: dict[str, Any]) -> None:
    validate_policy(policy)
    _exact(
        report,
        {
            "format", "policy_sha256", "status", "product_measurement",
            "layout_neutral_attempt", "attribution", "planning",
            "selected_strategy", "failure_menu",
            "conclusion",
        },
        "report",
    )
    if (
        report["format"] != "lisp65-v2-workbench-symbol-diff-report-v1"
        or report["policy_sha256"] != _sha_bytes(_canonical(policy))
        or report["status"] != "blocked"
        or report["product_measurement"] != policy["product_measurement"]
        or report["layout_neutral_attempt"] != policy["layout_neutral_attempt"]
        or report["planning"] != policy["planning"]
        or report["selected_strategy"] != policy["selected_strategy"]
        or report["failure_menu"] != policy["failure_menu"]
        or report["conclusion"] != "cp5-workbench-product-link-remains-blocked"
    ):
        raise AuditError("report policy/status binding drift")
    attr = _exact(
        report["attribution"],
        {
            "metric", "optimization", "limitations", "inputs",
            "net_named_delta_bytes", "positive_named_delta_bytes",
            "negative_named_delta_bytes", "group_totals",
            "ranked_positive_deltas", "ranked_negative_deltas",
        },
        "report attribution",
    )
    expected = policy["attribution"]
    if (attr["metric"], attr["optimization"], attr["limitations"]) != (
        expected["metric"], expected["optimization"], expected["limitations"],
    ):
        raise AuditError("report attribution semantics drift")
    _exact(attr["inputs"], {"baseline", "candidate"}, "attribution inputs")
    for label, record in attr["inputs"].items():
        _exact(record, {"sha256", "elf_class", "endian", "machine"}, f"{label} input")
        if not SHA_RE.fullmatch(record["sha256"]) or record != {
            "sha256": record["sha256"], "elf_class": 32, "endian": "little", "machine": "0x1966",
        }:
            raise AuditError(f"invalid {label} MOS ELF identity")
    positive = attr["ranked_positive_deltas"]
    negative = attr["ranked_negative_deltas"]
    if not isinstance(positive, list) or not isinstance(negative, list):
        raise AuditError("ranked symbol deltas must be arrays")
    for label, records, sign in (("positive", positive, 1), ("negative", negative, -1)):
        for index, record in enumerate(records):
            _exact(record, {"name", "baseline_bytes", "candidate_bytes", "delta_bytes"}, f"{label}[{index}]")
            if type(record["delta_bytes"]) is not int or record["delta_bytes"] * sign <= 0:
                raise AuditError(f"{label} symbol delta has wrong sign")
            if record["candidate_bytes"] - record["baseline_bytes"] != record["delta_bytes"]:
                raise AuditError(f"{label} symbol arithmetic drift")
    if positive != sorted(positive, key=lambda item: (-item["delta_bytes"], item["name"])):
        raise AuditError("positive symbol ranking drift")
    if negative != sorted(negative, key=lambda item: (item["delta_bytes"], item["name"])):
        raise AuditError("negative symbol ranking drift")
    by_name = {item["name"]: item["delta_bytes"] for item in positive + negative}
    for direction in ("required_positive_deltas", "required_negative_deltas"):
        for name, delta in expected[direction].items():
            if by_name.get(name) != delta:
                raise AuditError(f"report lacks pinned attribution delta: {name}")
    if (
        attr["positive_named_delta_bytes"] <= 0
        or attr["negative_named_delta_bytes"] >= 0
        or attr["net_named_delta_bytes"]
        != attr["positive_named_delta_bytes"] + attr["negative_named_delta_bytes"]
    ):
        raise AuditError("named attribution totals drift")
    if not isinstance(attr["group_totals"], dict) or set(attr["group_totals"]) != set(expected["groups"]):
        raise AuditError("attribution groups drift")


def selftest() -> None:
    policy = _load(DEFAULT_POLICY, "symbol-diff policy")
    validate_policy(policy)
    sample_a = {
        "keep": {"size": 7}, "grow": {"size": 3}, "removed": {"size": 9},
    }
    sample_b = {
        "keep": {"size": 7}, "grow": {"size": 8}, "added": {"size": 4},
    }
    result = _symbol_diff(sample_a, sample_b)
    if [(item["name"], item["delta_bytes"]) for item in result] != [
        ("grow", 5), ("added", 4), ("removed", -9),
    ]:
        raise AuditError("selftest symbol diff drift")
    mutations = []
    for label, mutate in (
        ("floor", lambda value: value["product_measurement"].__setitem__("resident_floor_delta_bytes", 3397)),
        ("attempt", lambda value: value["layout_neutral_attempt"]["measurement"].__setitem__("resident_delta_reclaim_bytes", 1052)),
        ("planning", lambda value: value["planning"].__setitem__("pinned_planning_reclaim_bytes", 3399)),
        ("release-strategy", lambda value: value["selected_strategy"].__setitem__("release_product", "runtime-core")),
        ("layout-rejection", lambda value: value["selected_strategy"]["layout_option"].__setitem__("available_bytes", 3000)),
        ("menu", lambda value: value["failure_menu"].pop()),
        ("lto", lambda value: value["attribution"].__setitem__("optimization", "-Oz")),
    ):
        value = json.loads(json.dumps(policy))
        mutate(value)
        try:
            validate_policy(value)
        except AuditError:
            mutations.append(label)
            continue
        raise AuditError(f"selftest accepted policy mutation: {label}")
    report = _load(DEFAULT_REPORT, "symbol-diff report")
    validate_report(policy, report)
    for label, mutate in (
        ("report-policy", lambda value: value.__setitem__("policy_sha256", "0" * 64)),
        ("report-product", lambda value: value["product_measurement"].__setitem__("resident_floor_delta_bytes", 3397)),
        ("report-symbol", lambda value: value["attribution"]["ranked_positive_deltas"][0].__setitem__("delta_bytes", 2272)),
    ):
        value = json.loads(json.dumps(report))
        mutate(value)
        try:
            validate_report(policy, value)
        except AuditError:
            mutations.append(label)
            continue
        raise AuditError(f"selftest accepted report mutation: {label}")
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-symbol-diff-") as temp:
        elf = Path(temp) / "mos.elf"
        header = bytearray(20)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<H", header, 18, 0x1966)
        elf.write_bytes(header)
        if _mos_elf(elf, "selftest")["machine"] != "0x1966":
            raise AuditError("selftest MOS ELF recognition drift")
    print(f"v2-workbench-symbol-diff: SELFTEST PASS mutations={len(mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    check = sub.add_parser("check")
    check.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    emit = sub.add_parser("generate")
    emit.add_argument("--baseline-elf", type=Path, required=True)
    emit.add_argument("--candidate-elf", type=Path, required=True)
    emit.add_argument("--nm", type=Path, default=DEFAULT_NM)
    emit.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "check":
            policy = _load(args.policy, "symbol-diff policy")
            validate_report(policy, _load(args.report, "symbol-diff report"))
            print("v2-workbench-symbol-diff: PASS report=bound status=blocked planning=4096")
        else:
            report = generate(args.policy, args.baseline_elf, args.candidate_elf, args.nm)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(_canonical(report))
            print(
                "v2-workbench-symbol-diff: WROTE "
                f"delta={report['product_measurement']['resident_floor_delta_bytes']} "
                f"indicator={report['attribution']['net_named_delta_bytes']} out={args.out}"
            )
        return 0
    except (AuditError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"v2-workbench-symbol-diff: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
