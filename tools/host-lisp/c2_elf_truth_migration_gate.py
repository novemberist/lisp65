#!/usr/bin/env python3
"""Keep the canonical C2 ELF gates on the shared structured truth layer."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-elf-truth-contract.json"
PRODUCT_GATE = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
BOOT_GATE = ROOT / "tools/host-lisp/c2_l65r_v2_boot_family_probe.py"
EXPECTED_CONSUMERS = {
    "boot_lifetime",
    "pre_ownership",
    "fixed_facade",
    "profile_data_reference",
    "kernal_control_flow",
    "final_section_inventory",
}


class MigrationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MigrationError(message)


def functions(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = ast.get_source_segment(source, node)
            require(segment is not None, f"cannot recover function source: {node.name}")
            result[node.name] = segment
    return result


def no_private_columns(source: str, *, label: str,
                       allow_objdump: bool = False) -> None:
    forbidden = ("llvm-nm", "llvm-size", "--sections", "--symbols",
                 "--relocations")
    for token in forbidden:
        require(token not in source, f"{label} retained private ELF view: {token}")
    if not allow_objdump:
        require("llvm-objdump" not in source,
                f"{label} retained rendered disassembly ownership")


def collect() -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    consumers = contract["migration"]["consumers"]
    require(set(consumers) == EXPECTED_CONSUMERS,
            f"consumer inventory drift: {sorted(consumers)}")
    require(set(consumers.values()) == {"migrated-shared-elf-truth"},
            f"unfinished consumers: {consumers}")
    require(contract["source"] == "tools/host-lisp/elf_truth.py",
            "shared truth source drift")
    require(contract["tool_input"] == {
        "producer": "llvm-readobj",
        "style": "JSON",
        "human_column_parsing": "forbidden",
    }, "structured tool-input contract drift")

    product = functions(PRODUCT_GATE)
    boot = functions(BOOT_GATE)
    required_product_functions = {
        "section_table",
        "defined_symbols",
        "_readobj_sections",
        "_sized_function_intervals",
        "_structured_relocation_records",
        "overlay_pack_family",
        "closure_gate",
        "fixed_facade_gate",
        "pre_ownership_gate",
        "profile_data_reference_gate",
        "_owned_control_flow_gate",
        "kernal_freedom_gate",
        "final_section_inventory_check",
    }
    missing = sorted(required_product_functions - set(product))
    require(not missing, f"canonical gate functions missing: {missing}")

    for name in ("section_table", "defined_symbols", "_readobj_sections",
                 "_sized_function_intervals",
                 "_structured_relocation_records"):
        require("ElfTruth.read" in product[name],
                f"{name} does not consume ElfTruth")
        no_private_columns(product[name], label=name)

    require("_structured_relocation_records(elf)" in
            product["profile_data_reference_gate"],
            "profile-data gate bypasses structured relocations")
    no_private_columns(product["profile_data_reference_gate"],
                       label="profile_data_reference_gate")

    for name in ("overlay_pack_family", "closure_gate"):
        require("ElfTruth.read" in product[name],
                f"{name} does not consume ElfTruth")
        # overlay_pack_family retains --nm only as a compatibility argument
        # for the legacy packer API; it no longer derives any gate truth from
        # rendered nm output.
        require("run([nm" not in product[name],
                f"{name} still executes a private nm view")
        source = product[name].replace('"--nm", nm', "").replace(
            '"llvm-nm"', '"legacy-packer-nm-api"')
        no_private_columns(source, label=name)

    for name in ("fixed_facade_gate", "pre_ownership_gate",
                 "final_section_inventory_check"):
        no_private_columns(product[name], label=name, allow_objdump=True)

    require("truth: ElfTruth" in product["_owned_control_flow_gate"],
            "control-flow ownership is not supplied by ElfTruth")
    no_private_columns(product["_owned_control_flow_gate"],
                       label="_owned_control_flow_gate", allow_objdump=True)
    require("ElfTruth.read" in product["kernal_freedom_gate"],
            "KERNAL gate does not load structured ELF truth")
    no_private_columns(product["kernal_freedom_gate"],
                       label="kernal_freedom_gate", allow_objdump=True)

    require("ELF.ElfTruth.read" in boot["boot_lifetime_gate"],
            "Boot lifetime gate left shared ELF truth")
    no_private_columns(boot["boot_lifetime_gate"], label="boot_lifetime_gate")

    return {
        "format": "lisp65-c2-elf-truth-migration-v1",
        "status": "pass",
        "consumers": dict(sorted(consumers.items())),
        "structured_helpers": 7,
        "canonical_consumers": 6,
        "instruction_decoder_boundary": (
            "llvm-objdump is permitted only for opcode bytes; structured "
            "ElfTruth owns section, symbol, size and relocation identity"
        ),
        "private_elf_views_in_named_consumers": 0,
        "ungoverned_column_parsers": ungoverned_column_parsers(contract),
        "claim_limit": (
            "Host-gate truth-source migration only; no product, linker, "
            "hardware, promotion or release claim."
        ),
    }


# One-off investigation probes are outside the migration rule -- they are not
# reachable from the build and several are named in immutable receipts, so they
# are neither rewritten nor moved.  But "private=0" reads like a statement about
# the whole tree, and it was not one.  The pinned inventory lives in the contract
# so the ungoverned population is visible and cannot grow silently: a new tool
# that parses ELF columns by hand either joins the governed consumers or moves
# the pin, deliberately.
GOVERNED_SOURCES = {
    "c2_elf_truth_migration_gate.py",
    "elf_truth.py",
}
COLUMN_TOOL_TOKENS = (
    'llvm-nm"', "llvm-nm'",
    'llvm-readelf"', "llvm-readelf'",
    'llvm-size"', "llvm-size'",
)
COLUMN_TOOL_NAMES = ("llvm-nm", "llvm-readelf", "llvm-size")
# Naming a column tool is not the same act as parsing its columns.  A source
# that hands the toolchain path to another script parses nothing; the
# accountable party is the script named in the same call.  The rule therefore
# bites on the act it claims, and stays fail-closed: a mention that is not
# handed to an accountable parser counts as hand parsing and must be pinned.


def _mentions_column_tool(value: object) -> bool:
    return isinstance(value, str) and any(
        name in value for name in COLUMN_TOOL_NAMES)


def delegated_parsers(source: str, accountable: set[str], *,
                      filename: str = "<source>") -> set[str] | None:
    """Accountable parsers every column-tool mention is handed to, else None."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return None
    mentions = {id(node) for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and _mentions_column_tool(node.value)}
    if not mentions:
        return None
    attributed: set[int] = set()
    delegates: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        named = {child.value for child in ast.walk(node)
                 if isinstance(child, ast.Constant)
                 and child.value in accountable}
        if not named:
            continue
        inside = {id(child) for child in ast.walk(node)
                  if isinstance(child, ast.Constant)
                  and _mentions_column_tool(child.value)}
        if inside:
            attributed |= inside
            delegates |= named
    if mentions - attributed:
        return None
    return delegates


def ungoverned_column_parsers(contract: dict[str, Any]) -> dict[str, Any]:
    """Probes outside the migration rule that still parse ELF columns by hand."""
    pin = contract.get("ungoverned_column_parsers_2026_07_30")
    require(isinstance(pin, dict), "ungoverned column-parser pin is missing")
    pinned = pin.get("files")
    require(
        isinstance(pinned, list) and all(isinstance(row, str) for row in pinned)
        and pin.get("count") == len(pinned),
        "ungoverned column-parser pin is malformed",
    )
    tools = Path(__file__).resolve().parent
    accountable = set(pinned) | GOVERNED_SOURCES
    found = set()
    parsers = set()
    delegating: dict[str, list[str]] = {}
    for path in sorted(tools.glob("*.py")):
        if path.name in GOVERNED_SOURCES:
            continue
        source = path.read_text(encoding="utf-8")
        if not any(token in source for token in COLUMN_TOOL_TOKENS) \
                or "ElfTruth" in source:
            continue
        found.add(path.name)
        delegates = delegated_parsers(
            source, accountable - {path.name}, filename=path.name)
        if delegates:
            delegating[path.name] = sorted(delegates)
        else:
            parsers.add(path.name)
    added = sorted(parsers - set(pinned))
    require(
        not added,
        "new tool parses ELF columns by hand instead of using shared ElfTruth: "
        f"{added}",
    )
    return {
        "scope_note": pin["scope"],
        "pinned": len(pinned),
        "present": len(found),
        "hand_parsers": len(parsers),
        "delegating": {name: delegating[name] for name in sorted(delegating)},
        "retired_since_pin": sorted(set(pinned) - found),
    }


def selftest() -> None:
    rejected = 0
    for mutation in (
        "llvm-nm --defined-only",
        "llvm-size -A",
        "llvm-readobj --relocations",
        "llvm-objdump -t",
    ):
        try:
            no_private_columns(mutation, label="mutation")
        except MigrationError:
            rejected += 1
    require(rejected == 4, f"private-view mutations accepted: {4 - rejected}")

    # A new ungoverned column parser must be rejected, not absorbed.
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    shrunk = json.loads(json.dumps(contract))
    pin = shrunk["ungoverned_column_parsers_2026_07_30"]
    pin["files"] = pin["files"][1:]
    pin["count"] = len(pin["files"])
    try:
        ungoverned_column_parsers(shrunk)
    except MigrationError:
        pass
    else:
        raise MigrationError(
            "a column parser missing from the pin was accepted silently")

    # The rule must bite on the act it claims.  Handing the toolchain path to
    # an accountable parser is delegation; every other mention counts as hand
    # parsing, including a mention that merely sits near a delegating call.
    accountable = {"resident_island.py"}
    require(
        delegated_parsers(
            'PRODUCT.tool("resident_island.py", "materialize",\n'
            '             "--nm", str(TOOLCHAIN / "llvm-nm"))',
            accountable) == accountable,
        "delegation to an accountable parser was not attributed",
    )
    for mutation in (
        'subprocess.run([str(nm), "--defined-only", str(elf)])\n'
        'check(nm, "llvm-nm", executable=True)',
        'out = run(["llvm-size", "-A", str(elf)], capture_output=True)',
        'args = ["--nm", str(TOOLCHAIN / "llvm-nm"), "--elf", str(elf)]',
        'PRODUCT.tool("resident_island.py", "materialize")\n'
        'raw = subprocess.run([str(TOOLCHAIN / "llvm-nm"), str(elf)])',
    ):
        require(
            delegated_parsers(mutation, accountable) is None,
            f"hand parsing was credited as delegation: {mutation!r}",
        )


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
        print("c2-elf-truth-migration: SELFTEST PASS mutations=10")
        return 0
    require(len(sys.argv) == 1, "usage: c2_elf_truth_migration_gate.py [--selftest]")
    result = collect()
    ungoverned = result["ungoverned_column_parsers"]
    print(
        "c2-elf-truth-migration: PASS "
        f"consumers={len(result['consumers'])} private-in-governed=0 "
        f"ungoverned-probes-pinned={ungoverned['pinned']} "
        f"mentions={ungoverned['present']} "
        f"hand-parsers={ungoverned['hand_parsers']} "
        f"delegating={len(ungoverned['delegating'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MigrationError as error:
        print(f"c2-elf-truth-migration: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
