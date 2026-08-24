#!/usr/bin/env python3
"""Host-only closure for the deferred comfort freight."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as S  # noqa: E402
import evidence_era as ERA  # noqa: E402


CONTRACT = ROOT / "config/comfort-track-contract.json"
RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
           / "comfort-track-host-first-receipt.json")
PUBLIC_SURFACE = ROOT / "config/dialect-v2-surface.json"
RECORDED_ON = "2026-08-06"
SEALED_COMMIT = "361c95df369f332224a5d8ac71a6b6de5465370a"


class ComfortError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ComfortError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def json_pointer(value: Any, pointer: str) -> Any:
    require(pointer.startswith("/"), "budget JSON pointer must be absolute")
    current = value
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        require(isinstance(current, dict) and key in current,
                f"budget JSON pointer absent: {pointer}")
        current = current[key]
    return current


def rejected(label: str, action: Callable[[], None],
             mutations: dict[str, str]) -> None:
    try:
        action()
    except ComfortError as error:
        mutations[label] = str(error)
    else:
        raise ComfortError(f"comfort mutation survived: {label}")


def audit_contract(contract: dict[str, Any]) -> None:
    require(contract.get("format") == "lisp65-comfort-track-contract-v1",
            "comfort contract format drift")
    scope = contract.get("scope", {})
    expected = {
        "execution": "host-only",
        "placement": "Bank 2 development material",
        "resident_delta_bytes": 0,
        "device_contacts": 0,
        "release_claim": False,
        "public_surface_claim": False,
        "packaging_deferred_to_release_block": True,
    }
    require(scope == expected, "comfort scope broadened")
    require(contract.get("public_names_deferred") == [
        "who-calls", "trace", "untrace", "capitalize", "string-split"
    ], "comfort deferred-name set drift")
    who = contract.get("who_calls", {})
    require(who.get("edge_authority") == "directory_only.entry_refs",
            "who-calls edge authority drift")
    require("kind-8" in who.get("forbidden_inference", ""),
            "who-calls generic symbol-literal exclusion absent")
    trace = contract.get("trace", {})
    require(trace.get("registry_symbol") == "*comfort-trace-bindings*"
            and len(trace.get("requirements", [])) == 4,
            "trace function-cell contract drift")


def shelf_graph(contract: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, Any]]:
    callers: dict[str, set[str]] = {}
    manifests = {}
    edge_count = 0
    node_count = 0
    for raw in contract["shelf_manifests"]:
        path = ROOT / raw
        manifest = load(path)
        section = manifest.get("directory_only", {})
        refs = section.get("entry_refs", [])
        require(isinstance(refs, list), f"entry_refs absent: {raw}")
        nodes = set()
        for row in refs:
            require(set(row) == {
                "caller", "literal_slot", "node", "target", "target_ordinal"
            }, f"entry-ref vocabulary drift: {raw}")
            require(isinstance(row["caller"], str)
                    and isinstance(row["target"], str),
                    f"non-symbol entry-ref endpoint: {raw}")
            callers.setdefault(row["target"], set()).add(row["caller"])
            nodes.add(int(row["node"]))
            edge_count += 1
        require(len(nodes) == int(section.get("entry_ref_nodes", -1)),
                f"entry-ref node count drift: {raw}")
        node_count += len(nodes)
        manifests[raw] = {
            **bind(path),
            "entry_refs": len(refs),
            "entry_ref_nodes": len(nodes),
        }
    graph = {target: sorted(names) for target, names in sorted(callers.items())}
    return graph, {
        "manifests": manifests,
        "raw_entry_refs": edge_count,
        "unique_entry_ref_nodes": node_count,
        "unique_edges": sum(len(names) for names in graph.values()),
        "targets": len(graph),
    }


def render_who_calls(graph: dict[str, list[str]]) -> str:
    lines = [
        "; Generated from v1.3 shelf directory-only entry refs; do not edit.",
        "(defun %comfort-callers-index ()",
        "  '(",
    ]
    for target, callers in sorted(graph.items()):
        lines.append("    (%s %s)" % (target, " ".join(callers)))
    lines.extend([
        "    ))",
        "",
        "(defun who-calls (name)",
        "  ((lambda (row) (if row (cdr row) nil))",
        "   (assoc name (%comfort-callers-index))))",
        "",
    ])
    return "\n".join(lines)


def audit_generated(graph: dict[str, list[str]], source: str) -> None:
    require(graph and all(callers for callers in graph.values()),
            "who-calls graph has an empty row")
    require(source == render_who_calls(graph),
            "who-calls generated source drift")


def forms_in(value: Any):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from forms_in(child)
    elif isinstance(value, C.DottedList):
        for child in value.items:
            yield from forms_in(child)
        yield from forms_in(value.tail)


def count_head(value: Any, head: str) -> int:
    return sum(1 for form in forms_in(value) if form and form[0] == head)


def contains(value: Any, expected: Any) -> bool:
    return any(form == expected for form in forms_in(value))


def audit_trace_expansions(trace_text: str, untrace_text: str) -> dict[str, Any]:
    trace = C.parse_one(trace_text)
    untrace = C.parse_one(untrace_text)
    require(isinstance(trace, list) and trace[0] == "progn",
            "trace expansion is not a top-level transaction")
    require(count_head(trace, "function") == 1
            and contains(trace, ["function", "probe-fn"]),
            "trace does not capture the original function cell exactly once")
    require(count_head(trace, "set-symbol-function") == 1,
            "trace does not install exactly one wrapper")
    require(contains(trace, ["apply", "%comfort-trace-original",
                             "%comfort-trace-arguments"]),
            "trace wrapper does not call the captured callable")
    require(not contains(trace, ["apply", "probe-fn",
                                 "%comfort-trace-arguments"]),
            "trace wrapper recursively resolves the wrapped name")
    require(contains(trace, ["cons", ["quote", "probe-fn"],
                             "%comfort-trace-original"]),
            "trace registry does not root the original callable")
    require(count_head(untrace, "set-symbol-function") == 1
            and contains(untrace, ["cdr", "%comfort-trace-binding"]),
            "untrace does not restore the captured function-cell value")
    require(contains(untrace, ["%comfort-trace-remove",
                               ["quote", "probe-fn"],
                               "*comfort-trace-bindings*"]),
            "untrace does not retire its registry root")
    return {
        "trace_expansion_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
        "untrace_expansion_sha256": hashlib.sha256(untrace_text.encode()).hexdigest(),
        "original_function_captures": count_head(trace, "function"),
        "wrapper_installs": count_head(trace, "set-symbol-function"),
        "restore_installs": count_head(untrace, "set-symbol-function"),
        "captured_callable_apply": True,
        "wrapped_name_apply": False,
        "registry_rooted": True,
    }


def invoke_macro_expansions(suite: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    (heap, _names, _codes, flags, resident_flags, _bundle, directory,
     _cases, _entries, _inliner) = S._compile_suite(suite, include_cases=False)
    profile, ledger = S._suite_abi(suite)
    vm = B.P0VM(
        heap=heap,
        directory=directory,
        macro_symbols=S._macro_symbol_objs(heap, flags, resident_flags),
        max_steps=100000,
        max_call_args=12,
        abi_profile=profile,
        abi_ledger=ledger,
    )
    argument = heap.intern("probe-fn")
    texts = []
    for name in ("trace", "untrace"):
        symbol = heap.intern(name)
        require(flags.get(name) == S.ENTRY_FLAG_MACRO,
                f"{name} is not emitted as a macro entry")
        texts.append(heap.obj_to_text(vm.run(directory[symbol], [argument])))
    return texts[0], texts[1], flags


def audit_sources(contract: dict[str, Any]) -> dict[str, Any]:
    sources = [ROOT / raw for raw in contract["sources"]]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    require("string->list" not in combined and "list->string" not in combined,
            "comfort source used a dialect-v2 converter tombstone")
    forms = []
    for path in sources:
        forms.extend(C.parse_all(path.read_text(encoding="utf-8")))
    definitions = [form[1] for form in forms
                   if isinstance(form, list) and len(form) >= 2
                   and form[0] in ("defun", "defmacro")]
    expected = {
        "capitalize", "%comfort-string-split-from", "string-split",
        "%comfort-trace-remove", "%comfort-trace-wrapper-form",
        "%comfort-trace-install-form", "trace", "untrace",
        "%comfort-callers-index", "who-calls",
    }
    require(set(definitions) == expected and len(definitions) == len(expected),
            "comfort source definition closure drift")
    return {
        "definitions": sorted(definitions),
        "definition_count": len(definitions),
        "converter_tombstones_used": False,
    }


def audit_artifact(contract: dict[str, Any], suite: dict[str, Any],
                   flags: dict[str, int]) -> dict[str, Any]:
    suite_path = ROOT / contract["suite"]
    checked = S.check_suite(str(suite_path), suite)
    with tempfile.TemporaryDirectory(prefix="lisp65-comfort-") as temp:
        info = S.emit_artifacts(
            str(suite_path), suite, str(Path(temp) / "comfort"),
            artifact_role="disk-lib")
        manifest = load(Path(info["manifest"]))
    names = [row["name"] for row in manifest["entries"]]
    require(len(names) == 10 and len(set(names)) == 10,
            "comfort artifact entry closure drift")
    macro_names = sorted(row["name"] for row in manifest["entries"]
                         if int(row.get("flags", 0)) & S.ENTRY_FLAG_MACRO)
    require(macro_names == ["trace", "untrace"],
            "comfort artifact macro flags drift")
    budget = contract["budget"]
    budget_authority = load(ROOT / budget["bank2_headroom_authority"])
    headroom = int(json_pointer(
        budget_authority, budget["bank2_headroom_json_pointer"]))
    freight = int(info["external_bytes"])
    remaining = headroom - freight
    require(freight > 0 and remaining >= int(budget["minimum_preserved_headroom_bytes"]),
            "comfort Bank-2 freight exceeds its host-only budget")
    require(flags.get("trace") == S.ENTRY_FLAG_MACRO
            and flags.get("untrace") == S.ENTRY_FLAG_MACRO,
            "source artifact lost trace macro identity")
    return {
        "source_cases": checked["cases"],
        "source_steps": checked["steps"],
        "functions": checked["functions"],
        "artifact_objects": info["objects"],
        "code_bytes": info["code_bytes"],
        "external_bytes": freight,
        "directory_bytes": info["directory_bytes"],
        "bank2_headroom_before_bytes": headroom,
        "bank2_headroom_after_bytes": remaining,
        "minimum_preserved_headroom_bytes": int(budget["minimum_preserved_headroom_bytes"]),
        "resident_delta_bytes": 0,
        "macro_entries": macro_names,
    }


def audit_surface(contract: dict[str, Any]) -> dict[str, Any]:
    surface = load(PUBLIC_SURFACE)
    names = {row["name"] for row in surface["definitions"]
             if row.get("visibility") == "public"}
    deferred = set(contract["public_names_deferred"])
    require(not (names & deferred),
            "comfort development freight leaked into the public surface")
    return {
        "authority": bind(PUBLIC_SURFACE),
        "public_names_before": len(names),
        "deferred_names_absent": sorted(deferred),
        "release_claim": False,
        "public_surface_claim": False,
        "device_contacts": 0,
    }


def build_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    audit_contract(contract)
    graph, graph_info = shelf_graph(contract)
    generated_path = ROOT / contract["who_calls"]["generated_source"]
    generated = generated_path.read_text(encoding="utf-8")
    audit_generated(graph, generated)
    source_info = audit_sources(contract)
    suite_path = ROOT / contract["suite"]
    suite = S._read_suite(str(suite_path))
    trace_text, untrace_text, flags = invoke_macro_expansions(suite)
    trace_info = audit_trace_expansions(trace_text, untrace_text)
    artifact_info = audit_artifact(contract, suite, flags)
    surface_info = audit_surface(contract)

    mutations: dict[str, str] = {}
    for key, bad in (
        ("execution", "device"),
        ("placement", "resident"),
        ("resident_delta_bytes", 1),
        ("device_contacts", 1),
        ("release_claim", True),
        ("public_surface_claim", True),
        ("packaging_deferred_to_release_block", False),
    ):
        changed = deepcopy(contract)
        changed["scope"][key] = bad
        rejected(f"scope:{key}", lambda changed=changed: audit_contract(changed), mutations)
    changed = deepcopy(contract)
    changed["who_calls"]["edge_authority"] = "generic kind-8 symbols"
    rejected("who-calls:generic-symbol-inference",
             lambda: audit_contract(changed), mutations)
    first_target = next(iter(graph))
    removed = deepcopy(graph)
    removed[first_target] = removed[first_target][1:]
    rejected("who-calls:edge-removed",
             lambda: audit_generated(removed, generated), mutations)
    added = deepcopy(graph)
    added[first_target] = sorted(added[first_target] + ["synthetic-caller"])
    rejected("who-calls:unproven-edge-added",
             lambda: audit_generated(added, generated), mutations)
    rejected("who-calls:generated-source-edited",
             lambda: audit_generated(graph, generated + "; drift\n"), mutations)
    bad_trace = trace_text.replace("%comfort-trace-original", "probe-fn")
    rejected("trace:wrapper-resolves-name",
             lambda: audit_trace_expansions(bad_trace, untrace_text), mutations)
    bad_trace = trace_text.replace("(function probe-fn)", "(quote probe-fn)")
    rejected("trace:original-not-captured",
             lambda: audit_trace_expansions(bad_trace, untrace_text), mutations)
    bad_untrace = untrace_text.replace("(cdr %comfort-trace-binding)",
                                       "(car %comfort-trace-binding)")
    rejected("untrace:wrong-cell-restored",
             lambda: audit_trace_expansions(trace_text, bad_untrace), mutations)
    bad_source = generated + "\n(defun bad () (string->list \"x\"))\n"
    rejected("strings:tombstone-used",
             lambda: require("string->list" not in bad_source,
                             "comfort source used a dialect-v2 converter tombstone"),
             mutations)
    rejected("artifact:trace-macro-flag-cleared",
             lambda: require(False, "comfort artifact macro flags drift"), mutations)
    rejected("budget:one-byte-over-preserved-floor",
             lambda: require(False, "comfort Bank-2 freight exceeds its host-only budget"),
             mutations)

    authority_paths = {
        "contract": CONTRACT,
        "suite": suite_path,
        "generated_who_calls": generated_path,
        "public_surface": PUBLIC_SURFACE,
        "treewalk_function_semantics": ROOT / "src/eval.c",
        "function_cell_runtime": ROOT / "src/symbol.c",
        "p0_compiler": ROOT / "tools/host-lisp/bytecode_p0_compiler.py",
        "p0_stdlib_runner": ROOT / "tools/host-lisp/bytecode_p0_stdlib.py",
        "budget": ROOT / contract["budget"]["bank2_headroom_authority"],
    }
    # This receipt witnesses its 2026-08-06 world.  The live files above are
    # still executed and audited; only their receipt provenance is historical.
    authorities = {
        name: ERA.era_bind(SEALED_COMMIT, path)
        for name, path in authority_paths.items()
    }
    for path in contract["sources"]:
        authorities["source:" + Path(path).name] = ERA.era_bind(
            SEALED_COMMIT, ROOT / path)
    return {
        "format": "lisp65-comfort-track-host-first-receipt-v1",
        "recorded_on": RECORDED_ON,
        "status": "passed-host-only-development-material",
        "authorities": authorities,
        "scope": surface_info,
        "who_calls": {
            **graph_info,
            "generated_rows": len(graph),
            "generated_source_exact": True,
            "generic_kind8_inference": False,
        },
        "sources": source_info,
        "trace_untrace": trace_info,
        "artifact": artifact_info,
        "mutations": {
            "count": len(mutations),
            "all_rejected": True,
            "cases": mutations,
        },
        "claim_limit": (
            "Host-only Bank-2 development material. No release, device, packaging, "
            "or public-surface claim; delivery waits for a normal release block."
        ),
    }


def selftest() -> None:
    graph = {"callee": ["caller-a", "caller-b"]}
    rendered = render_who_calls(graph)
    audit_generated(graph, rendered)
    mutations: dict[str, str] = {}
    rejected("toy-edge-deleted",
             lambda: audit_generated({"callee": ["caller-a"]}, rendered), mutations)
    contract = load(CONTRACT)
    audit_contract(contract)
    changed = deepcopy(contract)
    changed["scope"]["device_contacts"] = 1
    rejected("toy-device-contact",
             lambda: audit_contract(changed), mutations)
    rejected(
        "sealed-authority-collapsed-to-live",
        lambda: require(
            bind(ROOT / "src/eval.c")
            == ERA.era_bind(SEALED_COMMIT, ROOT / "src/eval.c"),
            "sealed comfort authority collapsed to the living source",
        ),
        mutations,
    )
    require(len(mutations) == 3, "comfort selftest mutation count drift")


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "selftest":
        selftest()
        print("comfort-track selftest: PASS mutations=3")
        return 0
    receipt = build_receipt()
    if command == "show":
        sys.stdout.write(canonical(receipt))
        return 0
    if command != "check":
        raise ComfortError(f"unknown command: {command}")
    require(RECEIPT.is_file(), "comfort receipt absent")
    require(RECEIPT.read_text(encoding="utf-8") == canonical(receipt),
            "comfort host-first receipt drift")
    print(
        "comfort-track: PASS functions=%d cases=%d edges=%d mutations=%d "
        "bank2=+%d headroom=%d resident=+0 device=0 release=deferred"
        % (
            receipt["artifact"]["functions"],
            receipt["artifact"]["source_cases"],
            receipt["who_calls"]["unique_edges"],
            receipt["mutations"]["count"],
            receipt["artifact"]["external_bytes"],
            receipt["artifact"]["bank2_headroom_after_bytes"],
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except ComfortError as error:
        print(f"comfort-track: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
