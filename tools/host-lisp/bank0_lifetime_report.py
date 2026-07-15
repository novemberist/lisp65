#!/usr/bin/env python3
"""Classify physical Bank-0 allocations by their Workbench lifetime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ELF = ROOT / "build" / "lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg.elf"
DEFAULT_FOOTPRINT = (
    ROOT / "build" / "bytecode" / "mvp-vm-stdlib-einsuite-core-workbench-footprint.txt"
)
DEFAULT_POLICY = ROOT / "config" / "bank0-lifetime-workbench.json"
DEFAULT_JSON = ROOT / "build" / "reports" / "workbench" / "bank0-lifetime.json"
DEFAULT_TEXT = ROOT / "build" / "reports" / "workbench" / "bank0-lifetime.txt"
DEFAULT_NM = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"
DEFAULT_SIZE = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-size"

POLICY_SCHEMA = "lisp65-bank0-lifetime-policy-v1"
REPORT_SCHEMA = "lisp65-bank0-lifetime-report-v1"
LIFETIME_CLASSES = (
    "runtime-hot",
    "runtime-cold",
    "boot-only",
    "dev-only",
    "bss-cap",
)
_NM_RE = re.compile(r"^\s*([0-9]+)\s+([0-9]+)\s+(\S)\s+(.+?)\s*$")
_LTO_SUFFIX_RE = re.compile(r"\.\d+$")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer")
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def _parse_size_output(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) < 3 or not parts[0].startswith("."):
            continue
        try:
            size = int(parts[1], 0)
            address = int(parts[2], 0)
        except ValueError:
            continue
        name = parts[0]
        if name in seen:
            raise ValueError("duplicate section in llvm-size output: %s" % name)
        seen.add(name)
        sections.append({"name": name, "address": address, "size": size})
    if not sections:
        raise ValueError("llvm-size output contains no sections")
    return sorted(sections, key=lambda item: (item["address"], item["name"]))


def _containing_section(
    sections: list[dict[str, Any]], address: int, size: int
) -> str | None:
    matches = []
    end = address + size
    for section in sections:
        section_end = section["address"] + section["size"]
        if section["size"] and section["address"] <= address and end <= section_end:
            matches.append(section["name"])
    if len(matches) > 1:
        raise ValueError(
            "symbol range 0x%x..0x%x maps to multiple sections: %s"
            % (address, end, ", ".join(matches))
        )
    return matches[0] if matches else None


def _parse_nm_output(
    text: str,
    sections: list[dict[str, Any]],
    mapped_sections: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # The key is the physical allocation. Multiple names at the same range are
    # aliases emitted by ICF/LTO and must not inflate byte totals.
    physical: dict[tuple[str, int, int], dict[str, Any]] = {}
    unmapped: list[dict[str, Any]] = []
    for raw in text.splitlines():
        match = _NM_RE.match(raw)
        if not match:
            continue
        address_text, size_text, symbol_type, name = match.groups()
        address, size = int(address_text), int(size_text)
        if size <= 0:
            continue
        eligible_sections = (
            sections
            if mapped_sections is None
            else [item for item in sections if item["name"] in mapped_sections]
        )
        section = _containing_section(eligible_sections, address, size)
        symbol = {"name": name, "type": symbol_type, "address": address, "size": size}
        if section is None:
            unmapped.append(symbol)
            continue
        key = (section, address, size)
        allocation = physical.setdefault(
            key,
            {
                "id": "%s:0x%04x:%d" % (section, address, size),
                "section": section,
                "address": address,
                "size": size,
                "aliases": [],
            },
        )
        allocation["aliases"].append({"name": name, "type": symbol_type})

    allocations = []
    for allocation in physical.values():
        allocation["aliases"].sort(key=lambda item: (item["name"], item["type"]))
        allocation["canonical_names"] = sorted(
            {_LTO_SUFFIX_RE.sub("", item["name"]) for item in allocation["aliases"]}
        )
        allocations.append(allocation)
    allocations.sort(key=lambda item: (item["section"], item["address"], item["size"]))
    unmapped.sort(key=lambda item: (item["address"], item["size"], item["name"]))
    return allocations, unmapped


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("unsupported policy schema: %r" % policy.get("schema"))
    if not isinstance(policy.get("profile"), str) or not policy["profile"]:
        raise ValueError("policy profile must be a non-empty string")
    threshold = _parse_int(policy.get("large_symbol_min_bytes"))
    if threshold <= 0:
        raise ValueError("large_symbol_min_bytes must be positive")
    sections = policy.get("sections")
    if not isinstance(sections, list) or not sections or not all(isinstance(v, str) for v in sections):
        raise ValueError("policy sections must be a non-empty string list")
    if len(set(sections)) != len(sections):
        raise ValueError("policy sections contain duplicates")
    groups = policy.get("section_groups")
    if not isinstance(groups, dict) or set(groups) != {"text_data", "bss"}:
        raise ValueError("section_groups must define exactly text_data and bss")
    grouped: list[str] = []
    for name in ("text_data", "bss"):
        members = groups[name]
        if not isinstance(members, list) or not all(isinstance(v, str) for v in members):
            raise ValueError("section group %s must be a string list" % name)
        grouped.extend(members)
    if len(set(grouped)) != len(grouped) or set(grouped) != set(sections):
        raise ValueError("section_groups must partition policy sections")

    rule_ids: set[str] = set()
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("policy rules must be a non-empty list")
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each policy rule must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in rule_ids:
            raise ValueError("policy rule id is missing or duplicated: %r" % rule_id)
        rule_ids.add(rule_id)
        if rule.get("class") not in LIFETIME_CLASSES:
            raise ValueError("rule %s has invalid class %r" % (rule_id, rule.get("class")))
        match = rule.get("match")
        if not isinstance(match, dict):
            raise ValueError("rule %s match must be an object" % rule_id)
        matcher_keys = set(match) - {"expected_allocations"}
        if len(matcher_keys) != 1 or next(iter(matcher_keys)) not in {"name", "names", "base"}:
            raise ValueError("rule %s must use exactly one name, names, or base matcher" % rule_id)
        matcher_key = next(iter(matcher_keys))
        matcher_value = match[matcher_key]
        if matcher_key == "names":
            if (
                not isinstance(matcher_value, list)
                or not matcher_value
                or not all(isinstance(v, str) and v for v in matcher_value)
                or len(set(matcher_value)) != len(matcher_value)
            ):
                raise ValueError("rule %s names matcher must be a unique non-empty string list" % rule_id)
        elif not isinstance(matcher_value, str) or not matcher_value:
            raise ValueError("rule %s matcher must be a non-empty string" % rule_id)
        expected = _parse_int(match.get("expected_allocations"))
        if expected < 0:
            raise ValueError("rule %s expected_allocations must not be negative" % rule_id)


def _rule_matches(rule: dict[str, Any], allocation: dict[str, Any]) -> bool:
    match = rule["match"]
    alias_names = {item["name"] for item in allocation["aliases"]}
    if "name" in match:
        return match["name"] in alias_names
    if "names" in match:
        return bool(alias_names.intersection(match["names"]))
    return match["base"] in allocation["canonical_names"]


def _violation(code: str, message: str, **details: Any) -> dict[str, Any]:
    out = {"code": code, "message": message}
    if details:
        out["details"] = details
    return out


def _overlap_violations(sections: list[dict[str, Any]], selected: set[str]) -> list[dict[str, Any]]:
    violations = []
    active = sorted(
        (item for item in sections if item["name"] in selected and item["size"]),
        key=lambda item: (item["address"], item["name"]),
    )
    for left, right in zip(active, active[1:]):
        if left["address"] + left["size"] > right["address"]:
            violations.append(
                _violation(
                    "section-overlap",
                    "selected sections overlap",
                    left=left["name"],
                    right=right["name"],
                )
            )
    return violations


def _build_report(
    sections: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    unmapped: list[dict[str, Any]],
    footprint: dict[str, str],
    policy: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    _validate_policy(policy)
    violations: list[dict[str, Any]] = []
    selected = set(policy["sections"])
    section_by_name = {item["name"]: item for item in sections}
    missing_sections = sorted(selected - set(section_by_name))
    for name in missing_sections:
        violations.append(_violation("missing-section", "policy section is absent", section=name))
    violations.extend(_overlap_violations(sections, selected))

    selected_sections = [section_by_name[name] for name in policy["sections"] if name in section_by_name]
    selected_allocations = [item.copy() for item in allocations if item["section"] in selected]
    threshold = _parse_int(policy["large_symbol_min_bytes"])

    matches_by_allocation: dict[str, list[dict[str, Any]]] = {
        item["id"]: [] for item in selected_allocations
    }
    for rule in policy["rules"]:
        matched = [item for item in selected_allocations if _rule_matches(rule, item)]
        expected = _parse_int(rule["match"]["expected_allocations"])
        if len(matched) != expected:
            violations.append(
                _violation(
                    "stale-rule",
                    "policy rule matched an unexpected number of physical allocations",
                    rule=rule["id"],
                    expected=expected,
                    actual=len(matched),
                )
            )
        for allocation in matched:
            matches_by_allocation[allocation["id"]].append(rule)

    for allocation in selected_allocations:
        matches = matches_by_allocation[allocation["id"]]
        if len(matches) > 1:
            violations.append(
                _violation(
                    "classification-conflict",
                    "physical allocation matches multiple policy rules",
                    allocation=allocation["id"],
                    rules=sorted(rule["id"] for rule in matches),
                )
            )
        if allocation["size"] >= threshold and not matches:
            violations.append(
                _violation(
                    "unclassified-large-allocation",
                    "large physical allocation has no lifetime classification",
                    allocation=allocation["id"],
                    aliases=[item["name"] for item in allocation["aliases"]],
                    size=allocation["size"],
                )
            )
        if len(matches) == 1:
            rule = matches[0]
            allocation["classification"] = rule["class"]
            allocation["policy_rule"] = rule["id"]
            for field in ("feature", "source", "reason"):
                if field in rule:
                    allocation[field] = rule[field]
        else:
            allocation["classification"] = None
            allocation["policy_rule"] = None

    group_sizes: dict[str, int] = {}
    for group_name, names in policy["section_groups"].items():
        group_sizes[group_name] = sum(section_by_name[name]["size"] for name in names if name in section_by_name)

    footprint_checks = {
        "text_data": "bank0_text_data_bytes",
        "bss": "bank0_bss_bytes",
    }
    for group_name, footprint_key in footprint_checks.items():
        try:
            footprint_value = _parse_int(footprint[footprint_key])
        except (KeyError, ValueError):
            violations.append(
                _violation(
                    "footprint-field-missing",
                    "required footprint field is absent or invalid",
                    field=footprint_key,
                )
            )
            continue
        if footprint_value != group_sizes[group_name]:
            violations.append(
                _violation(
                    "section-footprint-drift",
                    "ELF section sum differs from footprint report",
                    group=group_name,
                    section_bytes=group_sizes[group_name],
                    footprint_bytes=footprint_value,
                )
            )

    section_bytes = sum(item["size"] for item in selected_sections)
    symbolized_bytes = sum(item["size"] for item in selected_allocations)
    unattributed_bytes = section_bytes - symbolized_bytes
    if unattributed_bytes < 0:
        violations.append(
            _violation(
                "symbol-coverage-overflow",
                "deduplicated symbol bytes exceed selected section bytes",
                section_bytes=section_bytes,
                symbolized_bytes=symbolized_bytes,
            )
        )

    try:
        resident = _parse_int(footprint["bank0_resident_bytes"])
        other = _parse_int(footprint["bank0_other_resident_bytes"])
        if resident != group_sizes["text_data"] + group_sizes["bss"] + other:
            violations.append(
                _violation(
                    "resident-footprint-drift",
                    "footprint resident decomposition is inconsistent",
                    resident_bytes=resident,
                    decomposed_bytes=group_sizes["text_data"] + group_sizes["bss"] + other,
                )
            )
    except (KeyError, ValueError):
        violations.append(
            _violation(
                "footprint-field-missing",
                "resident footprint fields are absent or invalid",
                fields=["bank0_resident_bytes", "bank0_other_resident_bytes"],
            )
        )

    pins = policy.get("pins", {})
    pin_specs = (
        ("max_bank0_text_data_bytes", group_sizes["text_data"], "maximum", "text_data"),
        ("max_bank0_bss_bytes", group_sizes["bss"], "maximum", "bss"),
        (
            "min_bank0_reserve_bytes",
            _parse_int(footprint.get("bank0_reserve_bytes", "-1")),
            "minimum",
            "bank0_reserve",
        ),
        ("max_unattributed_section_bytes", unattributed_bytes, "maximum", "unattributed"),
    )
    for pin_name, actual, direction, metric in pin_specs:
        if pin_name not in pins:
            violations.append(_violation("pin-missing", "required policy pin is absent", pin=pin_name))
            continue
        limit = _parse_int(pins[pin_name])
        failed = actual > limit if direction == "maximum" else actual < limit
        if failed:
            violations.append(
                _violation(
                    "pin-drift",
                    "Bank-0 metric crossed its policy pin",
                    pin=pin_name,
                    metric=metric,
                    direction=direction,
                    limit=limit,
                    actual=actual,
                )
            )

    class_summaries = []
    for lifetime_class in LIFETIME_CLASSES:
        members = [item for item in selected_allocations if item["classification"] == lifetime_class]
        class_summaries.append(
            {
                "class": lifetime_class,
                "allocations": len(members),
                "bytes": sum(item["size"] for item in members),
            }
        )

    large_allocations = [item for item in selected_allocations if item["size"] >= threshold]
    unclassified_large = [item for item in large_allocations if item["classification"] is None]
    boot_only_bytes = next(
        item["bytes"] for item in class_summaries if item["class"] == "boot-only"
    )
    report = {
        "schema": REPORT_SCHEMA,
        "status": "ok" if not violations else "violations",
        "profile": policy["profile"],
        "inputs": inputs,
        "thresholds": {"large_symbol_min_bytes": threshold},
        "sections": selected_sections,
        "section_groups": group_sizes,
        "coverage": {
            "selected_section_bytes": section_bytes,
            "symbolized_physical_bytes": symbolized_bytes,
            "unattributed_section_bytes": unattributed_bytes,
            "physical_allocations": len(selected_allocations),
            "large_allocations": len(large_allocations),
            "unclassified_large_allocations": len(unclassified_large),
            "unmapped_nonzero_symbols": len(unmapped),
        },
        "classes": class_summaries,
        "boot_only_theoretical_bytes": boot_only_bytes,
        "boot_only_note": (
            "Theoretical lifetime candidate only; layout, boot-stack, emulator, and hardware "
            "gates are required before memory can be treated as reclaimed."
        ),
        "allocations": selected_allocations,
        "unmapped_symbols": unmapped,
        "violations": sorted(
            violations,
            key=lambda item: (item["code"], item["message"], json.dumps(item.get("details", {}), sort_keys=True)),
        ),
    }
    return report


def _render_text(report: dict[str, Any]) -> str:
    lines = [
        "# lisp65 Bank-0 lifetime report",
        "schema=%s" % report["schema"],
        "status=%s" % report["status"],
        "profile=%s" % report["profile"],
        "large_symbol_min_bytes=%d" % report["thresholds"]["large_symbol_min_bytes"],
        "selected_section_bytes=%d" % report["coverage"]["selected_section_bytes"],
        "symbolized_physical_bytes=%d" % report["coverage"]["symbolized_physical_bytes"],
        "unattributed_section_bytes=%d" % report["coverage"]["unattributed_section_bytes"],
        "large_allocations=%d" % report["coverage"]["large_allocations"],
        "unclassified_large_allocations=%d"
        % report["coverage"]["unclassified_large_allocations"],
        "boot_only_theoretical_bytes=%d" % report["boot_only_theoretical_bytes"],
        "boot_only_note=%s" % report["boot_only_note"],
        "",
        "Classes:",
        "class         bytes allocations",
    ]
    for item in report["classes"]:
        lines.append("%-13s %5d %11d" % (item["class"], item["bytes"], item["allocations"]))
    lines.extend(["", "Large physical allocations:", "size section        class         aliases"])
    large_min = report["thresholds"]["large_symbol_min_bytes"]
    large = [item for item in report["allocations"] if item["size"] >= large_min]
    for item in sorted(large, key=lambda value: (-value["size"], value["section"], value["address"])):
        aliases = ",".join(alias["name"] for alias in item["aliases"])
        lines.append(
            "%4d %-14s %-13s %s"
            % (item["size"], item["section"], item["classification"] or "unclassified", aliases)
        )
    lines.extend(["", "Violations:"])
    if report["violations"]:
        for item in report["violations"]:
            details = json.dumps(item.get("details", {}), sort_keys=True, separators=(",", ":"))
            lines.append("- %s: %s %s" % (item["code"], item["message"], details))
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _run_tool(path: Path, args: list[str]) -> str:
    return subprocess.check_output([str(path), *args], text=True, stderr=subprocess.STDOUT)


def _selftest_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "profile": "selftest",
        "large_symbol_min_bytes": 80,
        "sections": [".text", ".bss"],
        "section_groups": {"text_data": [".text"], "bss": [".bss"]},
        "pins": {
            "max_bank0_text_data_bytes": 300,
            "max_bank0_bss_bytes": 100,
            "min_bank0_reserve_bytes": 20,
            "max_unattributed_section_bytes": 210,
        },
        "rules": [
            {
                "id": "hot-alias",
                "match": {"base": "hot", "expected_allocations": 1},
                "class": "runtime-hot",
            },
            {
                "id": "cold",
                "match": {"name": "cold", "expected_allocations": 1},
                "class": "runtime-cold",
            },
        ],
    }


def _selftest() -> int:
    size_text = "fixture:\nsection size addr\n.text 300 8192\n.bss 100 9000\nTotal 400\n"
    nm_text = "8192 100 t hot\n8192 100 t hot.17\n8292 90 t cold\n"
    sections = _parse_size_output(size_text)
    allocations, unmapped = _parse_nm_output(nm_text, sections)
    footprint = {
        "bank0_text_data_bytes": "300",
        "bank0_bss_bytes": "100",
        "bank0_reserve_bytes": "20",
        "bank0_resident_bytes": "400",
        "bank0_other_resident_bytes": "0",
    }
    base = _build_report(sections, allocations, unmapped, footprint, _selftest_policy(), {})
    assert base["status"] == "ok"
    hot = next(item for item in base["allocations"] if item["address"] == 8192)
    assert hot["size"] == 100 and len(hot["aliases"]) == 2
    assert base["coverage"]["symbolized_physical_bytes"] == 190

    conflict_policy = json.loads(json.dumps(_selftest_policy()))
    conflict_policy["rules"].append(
        {
            "id": "hot-conflict",
            "match": {"name": "hot", "expected_allocations": 1},
            "class": "dev-only",
        }
    )
    conflict = _build_report(sections, allocations, unmapped, footprint, conflict_policy, {})
    assert "classification-conflict" in {item["code"] for item in conflict["violations"]}

    unknown_policy = json.loads(json.dumps(_selftest_policy()))
    unknown_policy["rules"] = unknown_policy["rules"][:1]
    unknown = _build_report(sections, allocations, unmapped, footprint, unknown_policy, {})
    assert "unclassified-large-allocation" in {item["code"] for item in unknown["violations"]}

    stale_policy = json.loads(json.dumps(_selftest_policy()))
    stale_policy["rules"][0]["match"]["expected_allocations"] = 2
    stale = _build_report(sections, allocations, unmapped, footprint, stale_policy, {})
    assert "stale-rule" in {item["code"] for item in stale["violations"]}

    drift_policy = json.loads(json.dumps(_selftest_policy()))
    drift_policy["pins"]["max_bank0_text_data_bytes"] = 299
    drift_footprint = dict(footprint, bank0_text_data_bytes="299")
    drift = _build_report(sections, allocations, unmapped, drift_footprint, drift_policy, {})
    drift_codes = {item["code"] for item in drift["violations"]}
    assert "section-footprint-drift" in drift_codes and "pin-drift" in drift_codes

    with tempfile.TemporaryDirectory(prefix="lisp65-bank0-lifetime-") as tmp:
        path = Path(tmp) / "report.json"
        path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))["schema"] == REPORT_SCHEMA
    print("bank0-lifetime-report selftest: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path, default=DEFAULT_ELF)
    parser.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--nm", type=Path, default=DEFAULT_NM)
    parser.add_argument("--size", type=Path, default=DEFAULT_SIZE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--text-out", type=Path, default=DEFAULT_TEXT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()

    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        _validate_policy(policy)
        footprint = _read_kv(args.footprint)
        sections = _parse_size_output(_run_tool(args.size, ["-A", str(args.elf)]))
        allocations, unmapped = _parse_nm_output(
            _run_tool(
                args.nm,
                ["--defined-only", "--print-size", "--size-sort", "--radix=d", str(args.elf)],
            ),
            sections,
            set(policy["sections"]),
        )
        inputs = {
            "elf": {"path": _display_path(args.elf), "sha256": _sha256(args.elf)},
            "footprint": {
                "path": _display_path(args.footprint),
                "sha256": _sha256(args.footprint),
            },
            "policy": {"path": _display_path(args.policy), "sha256": _sha256(args.policy)},
            "nm": {"path": _display_path(args.nm), "sha256": _sha256(args.nm)},
            "size": {"path": _display_path(args.size), "sha256": _sha256(args.size)},
        }
        report = _build_report(sections, allocations, unmapped, footprint, policy, inputs)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print("bank0-lifetime-report: ERROR: %s" % exc, file=sys.stderr)
        return 2

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.text_out.write_text(_render_text(report), encoding="utf-8")
    print(
        "bank0-lifetime-report: %s json=%s text=%s large=%d boot_only_theoretical=%d"
        % (
            report["status"].upper(),
            args.json_out,
            args.text_out,
            report["coverage"]["large_allocations"],
            report["boot_only_theoretical_bytes"],
        )
    )
    return 1 if args.check and report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
