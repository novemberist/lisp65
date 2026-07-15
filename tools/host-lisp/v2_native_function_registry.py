#!/usr/bin/env python3
"""Generate and cross-check every dialect-v2 primitive view from one registry."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "v2-native-function-registry.json"
LEDGER = ROOT / "config" / "bytecode-abi-ledger.json"
SURFACE = ROOT / "config" / "dialect-v2-surface.json"
HEADER = ROOT / "src" / "v2_native_function_dispatch.h"
PY_VIEWS = ROOT / "tools" / "host-lisp" / "v2_native_function_views_generated.py"
FIXTURE = ROOT / "tests" / "bytecode" / "dialect-v2" / "native-function-routes" / "cases.generated.json"
REPORT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "capability-carrier" / "primitive-view-cross-parity.json"
FORMAT = "lisp65-v2-native-function-registry-v2"
KINDS = {"fold-identity": 1, "fold-required": 2, "callprim": 3, "opfn": 4, "boundp": 5}
VIEWS = ["callprim", "apply", "function-kind", "compile-repl"]
NAME_RE = re.compile(r"^[^\s()\"]+$")


class RegistryError(RuntimeError):
    pass


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise RegistryError(f"{path}: root is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _literal_dict(path: Path, variable: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == variable for target in targets):
                try:
                    return ast.literal_eval(node.value)
                except (TypeError, ValueError) as exc:
                    raise RegistryError(f"{path.name}:{variable} is not literal") from exc
    raise RegistryError(f"{path.name}:{variable} missing")


def _c_prim_rows(text: str) -> dict[str, int]:
    match = re.search(r"\bPRIMS\s*\[\s*\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not match:
        raise RegistryError("src/compile.c PRIMS table missing")
    return {
        name: int(ident)
        for name, ident in re.findall(r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*\}', match.group(1))
    }


def _lcc_rows(text: str) -> dict[str, int]:
    return {
        name: int(ident)
        for name, ident in re.findall(r"\(\(eq name '([^()\s]+)\)\s+(\d+)\)", text)
    }


def _eval_primitive_rows(text: str) -> dict[str, str]:
    boot_names = {
        token: name
        for token, name in re.findall(
            r'WORKBENCH_BOOTNAME\(\s*([A-Za-z0-9_]+)\s*,\s*"([^"]+)"\s*\)',
            text,
            re.S,
        )
    }
    rows: dict[str, str] = {}
    for token, tree_id in re.findall(
        r'defprim\(\s*BOOTNAME\(([A-Za-z0-9_]+)\)\s*,\s*(P_[A-Z0-9_]+)\s*\)',
        text,
    ):
        name = boot_names.get(token)
        if name is None:
            raise RegistryError(f"eval bootstrap name missing for {token}")
        if name in rows and rows[name] != tree_id:
            raise RegistryError(f"eval bootstrap primitive duplicated: {name}")
        rows[name] = tree_id
    return rows


def validate(registry: dict, ledger: dict) -> dict:
    required = {
        "format", "version", "profile", "truth_source", "parity_gate",
        "excluded_designator_error", "engines", "routes", "views", "entries",
        "intrinsic_aliases", "restricted_primitives", "safety_cases",
    }
    if set(registry) != required or registry["format"] != FORMAT or registry["version"] != 2:
        raise RegistryError("registry envelope drift")
    if registry["routes"] != ["direct", "funcall", "apply"] or registry["views"] != VIEWS:
        raise RegistryError("route/view contract drift")
    if registry["engines"] != [
        "native-c-treewalk", "native-c-compiler-vm",
        "python-p0-compiler-vm", "lisp-lcc",
    ]:
        raise RegistryError("four-engine contract drift")
    diagnostic = registry["excluded_designator_error"]
    if diagnostic != {
        "vm_status": "VM_NOTDESIGNATOR",
        "error_code": "LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR",
        "text": "vm: primitive is not a function designator",
    }:
        raise RegistryError("excluded-designator diagnostic drift")

    identities = {row["id"]: row["canonical_name"] for row in ledger["prim_identities"]}
    v1 = next(row for row in ledger["profiles"] if row["id"] == "dialect-v1")
    v2 = next(row for row in ledger["profiles"] if row["id"] == "dialect-v2")
    active = set(v2["prim_ids"]["active"])
    entries = registry["entries"]
    if not isinstance(entries, list) or not entries:
        raise RegistryError("empty public dispatch registry")
    names: set[str] = set()
    callprim: dict[str, int] = {}
    for index, row in enumerate(entries):
        mandatory = {"name", "kind", "value", "tree_id", "args", "expect"}
        if not mandatory <= set(row) or not set(row) <= mandatory | {"wrap", "setup"}:
            raise RegistryError(f"entries[{index}] shape drift")
        name, kind = row["name"], row["kind"]
        if not isinstance(name, str) or not NAME_RE.fullmatch(name) or name in names:
            raise RegistryError(f"entries[{index}] invalid or duplicate name")
        names.add(name)
        if kind not in KINDS:
            raise RegistryError(f"entries[{index}] unknown dispatch kind")
        if not isinstance(row["tree_id"], str) or not re.fullmatch(r"P_[A-Z0-9_]+", row["tree_id"]):
            raise RegistryError(f"entries[{index}] invalid tree primitive identity")
        if not isinstance(row["args"], list) or not all(isinstance(x, str) and x for x in row["args"]):
            raise RegistryError(f"entries[{index}] invalid probe args")
        if not isinstance(row["expect"], str) or not row["expect"]:
            raise RegistryError(f"entries[{index}] invalid expected value")
        if "wrap" in row and row["wrap"] not in {"symbolp", "numberp"}:
            raise RegistryError(f"entries[{index}] invalid result wrapper")
        if "setup" in row and (
            not isinstance(row["setup"], list)
            or not all(isinstance(form, str) and form for form in row["setup"])
        ):
            raise RegistryError(f"entries[{index}] invalid setup forms")
        if kind == "callprim":
            if type(row["value"]) is not int or row["value"] not in active:
                raise RegistryError(f"entries[{index}] inactive Prim-ID")
            if identities.get(row["value"]) != name:
                raise RegistryError(f"entries[{index}] Prim-ID/name drift")
            callprim[name] = row["value"]
        elif kind in {"fold-identity", "fold-required"}:
            if row["value"] not in {"OP_ADD", "OP_MUL", "OP_SUB", "OP_DIV"}:
                raise RegistryError(f"entries[{index}] invalid fold opcode")
        elif type(row["value"]) is not int:
            raise RegistryError(f"entries[{index}] invalid dispatch value")

    restricted: dict[str, dict] = {}
    for index, row in enumerate(registry["restricted_primitives"]):
        if set(row) != {"name", "value", "restricted_views", "reason"}:
            raise RegistryError(f"restricted_primitives[{index}] shape drift")
        name, ident = row["name"], row["value"]
        if name in names or name in restricted or identities.get(ident) != name or ident not in active:
            raise RegistryError(f"restricted_primitives[{index}] invalid classification")
        views = row["restricted_views"]
        if not isinstance(views, list) or not views or not set(views) <= {"apply", "function-kind"}:
            raise RegistryError(f"restricted_primitives[{index}] invalid view restriction")
        if not isinstance(row["reason"], str) or not row["reason"]:
            raise RegistryError(f"restricted_primitives[{index}] missing reason")
        restricted[name] = row

    aliases: dict[str, dict] = {}
    for index, row in enumerate(registry["intrinsic_aliases"]):
        if set(row) != {"name", "kind", "value", "restricted_views", "reason"}:
            raise RegistryError(f"intrinsic_aliases[{index}] shape drift")
        name = row["name"]
        if (
            name in names or name in restricted or name in aliases
            or row["kind"] != "opfn" or type(row["value"]) is not int
            or row["restricted_views"] != ["callprim", "function-kind"]
            or not isinstance(row["reason"], str) or not row["reason"]
        ):
            raise RegistryError(f"intrinsic_aliases[{index}] invalid classification")
        aliases[name] = row
    if set(aliases) != {"not", "null"}:
        raise RegistryError("compiler intrinsic alias inventory drift")

    classified_ids = set(callprim.values()) | {row["value"] for row in restricted.values()}
    if classified_ids != active:
        missing = sorted(active - classified_ids)
        extra = sorted(classified_ids - active)
        raise RegistryError(f"active CALLPRIM partition drift missing={missing} extra={extra}")

    surface = load(SURFACE)
    public_names = {row["name"] for row in surface["definitions"]}
    expected_public = {identities[ident]: ident for ident in active if identities[ident] in public_names}
    if callprim != expected_public:
        raise RegistryError(
            "public CALLPRIM closure drift missing=%s extra=%s" %
            (sorted(set(expected_public) - set(callprim)), sorted(set(callprim) - set(expected_public)))
        )

    safety_names: set[str] = set()
    for index, row in enumerate(registry["safety_cases"]):
        if set(row) != {"name", "target", "args", "expect_error"}:
            raise RegistryError(f"safety_cases[{index}] shape drift")
        if row["name"] in safety_names or row["target"] not in {"peek", "poke"}:
            raise RegistryError(f"safety_cases[{index}] invalid name/target")
        if row["expect_error"] != "!error" or not isinstance(row["args"], list):
            raise RegistryError(f"safety_cases[{index}] diagnostic drift")
        safety_names.add(row["name"])

    all_active = {identities[ident]: ident for ident in active}
    compile_text = (ROOT / "src" / "compile.c").read_text(encoding="utf-8")
    if "LISP65_V2_CALLPRIM_ACTIVE_ROWS" not in compile_text:
        raise RegistryError("compile-repl dispatch is not generated from the registry")
    opcode_names = {row["name"] for row in entries if row["kind"] != "callprim"}
    direct_start = compile_text.index('if      (op_is(op, "+"))')
    direct_end = compile_text.index('else if (op_is(op, "quote"))', direct_start)
    compiled_opcode_names = set(re.findall(r'op_is\(op, "([^"]+)"\)', compile_text[direct_start:direct_end]))
    compiled_opcode_names.update(re.findall(
        r'op_is\(op, "([^"]+)"\)\)\s+compile_cmpchain', compile_text
    ))
    compiled_opcode_names.discard("remainder")  # v1-only guarded branch in the shared source
    if opcode_names | set(aliases) != compiled_opcode_names:
        raise RegistryError("compile-repl opcode/intrinsic inventory drift")
    py_ids = _literal_dict(ROOT / "tools" / "host-lisp" / "bytecode_p0.py", "PRIM_IDS")
    if {py_ids[ident]: ident for ident in active} != all_active:
        raise RegistryError("Python CALLPRIM identity mirror drift")
    lcc_rows = _lcc_rows((ROOT / "lib" / "dialect-v2" / "lcc-profile.lisp").read_text(encoding="utf-8"))
    if {name: ident for name, ident in lcc_rows.items() if ident in active} != all_active:
        raise RegistryError("LCC CALLPRIM view drift")
    eval_rows = _eval_primitive_rows((ROOT / "src" / "eval.c").read_text(encoding="utf-8"))
    expected_eval_rows = {row["name"]: row["tree_id"] for row in entries}
    missing_eval = {
        name: tree_id
        for name, tree_id in expected_eval_rows.items()
        if eval_rows.get(name) != tree_id
    }
    if missing_eval:
        raise RegistryError(f"function-kind/bootstrap primitive view drift: {missing_eval}")
    vm_text = (ROOT / "src" / "vm.c").read_text(encoding="utf-8")
    vm_body = vm_text[vm_text.index("static __attribute__((noinline)) obj vm_callprim"):]
    vm_cases = {int(value) for value in re.findall(r"\bcase\s+(\d+)\s*:", vm_body)}
    if not active <= vm_cases:
        raise RegistryError(f"C CALLPRIM implementation missing IDs {sorted(active - vm_cases)}")
    return {
        "entries": entries,
        "callprim": callprim,
        "restricted": restricted,
        "aliases": aliases,
        "active": all_active,
        "v1_active": {identities[ident]: ident for ident in v1["prim_ids"]["active"]},
    }


def _rows_macro(lines: list[str], name: str, rows: list[tuple[str, object]]) -> None:
    lines.append(f"#define {name}_COUNT {len(rows)}")
    if not rows:
        lines.append(f"#define {name}_ROWS(X)")
        return
    lines.append(f"#define {name}_ROWS(X) \\")
    for index, (row_name, value) in enumerate(rows):
        suffix = " \\" if index + 1 < len(rows) else ""
        lines.append(f'    X("{row_name}", {value}){suffix}')


def header_text(registry: dict, state: dict) -> str:
    entries = state["entries"]
    groups = {kind: [row for row in entries if row["kind"] == kind] for kind in KINDS}
    lines = [
        "/* Generated by tools/host-lisp/v2_native_function_registry.py. */",
        "#ifndef LISP65_V2_NATIVE_FUNCTION_DISPATCH_H",
        "#define LISP65_V2_NATIVE_FUNCTION_DISPATCH_H",
        "",
        f"#define LISP65_V2_NATIVE_FUNCTION_COUNT {len(entries)}",
        f"#define LISP65_V2_NATIVE_FUNCTION_EXCLUSION_COUNT {len(state['restricted'])}",
        "#define LISP65_V2_NATIVE_KIND_FOLD_IDENTITY 1",
        "#define LISP65_V2_NATIVE_KIND_FOLD_REQUIRED 2",
        "#define LISP65_V2_NATIVE_KIND_CALLPRIM 3",
        "#define LISP65_V2_NATIVE_KIND_OPFN 4",
        "",
    ]
    _rows_macro(lines, "LISP65_V2_CALLPRIM_ACTIVE", sorted(state["active"].items(), key=lambda item: item[1]))
    lines.append("")
    lines.append("#define LISP65_V2_NATIVE_FUNCTION_TREE_ROWS(X) \\")
    for index, row in enumerate(entries):
        suffix = " \\" if index + 1 < len(entries) else ""
        lines.append(
            f"    X({row['tree_id']}, {KINDS[row['kind']]}, {row['value']}){suffix}"
        )
    lines.append("")
    _rows_macro(
        lines, "LISP65_V2_NATIVE_FUNCTION_INTRINSIC_ALIAS",
        [(row["name"], row["value"]) for row in state["aliases"].values()],
    )
    for kind, macro in (
        ("fold-identity", "FOLD_IDENTITY"), ("fold-required", "FOLD_REQUIRED"),
        ("callprim", "CALLPRIM"), ("opfn", "OPFN"), ("boundp", "BOUNDP"),
    ):
        rows = groups[kind]
        lines.append("")
        _rows_macro(lines, f"LISP65_V2_NATIVE_FUNCTION_{macro}", [(row["name"], row["value"]) for row in rows])
        if kind in {"fold-identity", "fold-required"}:
            match = " || ".join(f'((sym) == intern("{row["name"]}"))' for row in rows) or "0"
            value = str(rows[-1]["value"]) if rows else "0"
            for row in reversed(rows[:-1]):
                value = f'((sym) == intern("{row["name"]}") ? {row["value"]} : {value})'
            lines.append(f"#define LISP65_V2_NATIVE_FUNCTION_{macro}_MATCH(sym) ({match})")
            lines.append(f"#define LISP65_V2_NATIVE_FUNCTION_{macro}_VALUE(sym) ({value})")
    lines.append("")
    _rows_macro(
        lines, "LISP65_V2_NATIVE_FUNCTION_EXCLUSION",
        [(row["name"], row["value"]) for row in sorted(state["restricted"].values(), key=lambda item: item["value"])],
    )
    lines.extend(["", "#endif", ""])
    return "\n".join(lines)


def python_views_text(state: dict) -> str:
    active = sorted(state["active"].items(), key=lambda item: item[1])
    designators = sorted(state["callprim"].values())
    restrictions = {name: row["reason"] for name, row in sorted(state["restricted"].items())}
    return (
        '"""Generated primitive-view inventory; do not edit."""\n\n'
        f"ACTIVE_CALLPRIMS = {dict(active)!r}\n"
        f"FUNCTION_DESIGNATOR_IDS = frozenset({designators!r})\n"
        f"RESTRICTION_REASONS = {restrictions!r}\n"
    )


def route_form(name: str, args: list[str], route: str) -> str:
    joined = (" " + " ".join(args)) if args else ""
    if route == "direct":
        return f"({name}{joined})"
    if route == "funcall":
        return f"(funcall (function {name}){joined})"
    arglist = "nil"
    for arg in reversed(args):
        arglist = f"(cons {arg} {arglist})"
    return f"(apply (function {name}) {arglist})"


def fixture_value(registry: dict, state: dict) -> dict:
    cases = []
    for index, row in enumerate(state["entries"]):
        slug = re.sub(r"[^a-z0-9]+", "-", row["name"].lower()).strip("-") or f"prim-{index}"
        for route in registry["routes"]:
            form = route_form(row["name"], row["args"], route)
            if row.get("wrap"):
                form = f"({row['wrap']} {form})"
            cases.append({
                "name": f"native-{index:02d}-{slug}-{route}",
                "forms": list(row.get("setup", [])) + [form],
                "expect": row["expect"],
            })
    for row in registry["safety_cases"]:
        for route in registry["routes"]:
            cases.append({
                "name": f"safety-{row['name']}-{route}",
                "forms": [route_form(row["target"], row["args"], route)],
                "expect_error": row["expect_error"],
            })
    for index, row in enumerate(state["entries"]):
        slug = re.sub(r"[^a-z0-9]+", "-", row["name"].lower()).strip("-") or f"prim-{index}"
        cases.append({
            "name": f"view-{index:02d}-{slug}-function-kind",
            "forms": [f"(eq (function-kind (quote {row['name']})) (quote primitive))"],
            "expect": "t",
        })
    return {
        "format": "lisp65-eval-surface-v1",
        "description": "Generated primitive x route matrix plus peek/poke safety negatives.",
        "cases": cases,
    }


def report_value(registry: dict, state: dict) -> dict:
    rows = []
    for name, ident in sorted(state["active"].items(), key=lambda item: item[1]):
        restriction = state["restricted"].get(name)
        restricted_views = set() if restriction is None else set(restriction["restricted_views"])
        rows.append({
            "name": name,
            "prim_id": ident,
            "views": {view: (view not in restricted_views) for view in VIEWS},
            "classification": "public-all-views" if restriction is None else "explicitly-view-restricted",
            "reason": None if restriction is None else restriction["reason"],
        })
    return {
        "format": "lisp65-v2-primitive-view-cross-parity-v1",
        "status": "passed",
        "registry": "config/v2-native-function-registry.json",
        "registry_sha256": sha(REGISTRY),
        "active_callprims": len(rows),
        "public_designators": len(state["entries"]),
        "public_active_callprims": len(state["callprim"]),
        "opcode_designators": [
            {
                "name": row["name"],
                "route_kind": row["kind"],
                "tree_id": row["tree_id"],
                "apply": True,
                "function_kind": True,
                "compile_repl": True,
            }
            for row in state["entries"] if row["kind"] != "callprim"
        ],
        "intrinsic_aliases": list(state["aliases"].values()),
        "explicit_restrictions": len(state["restricted"]),
        "unclassified": [],
        "missing_from_callprim": [],
        "missing_from_compile_repl": [],
        "missing_public_apply": [],
        "missing_public_function_kind": [],
        "rows": rows,
        "gate_sources": {
            "callprim": "config/bytecode-abi-ledger.json + src/vm.c",
            "apply": "src/v2_native_function_dispatch.h + generated T_PRIM classification in src/eval.c",
            "function-kind": "registry-gated src/eval.c defprim table + generated T_PRIM classification",
            "compile-repl": "src/v2_native_function_dispatch.h consumed by src/compile.c",
            "python-p0": "tools/host-lisp/v2_native_function_views_generated.py",
            "lisp-lcc": "lib/dialect-v2/lcc-profile.lisp",
        },
    }


def render_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


def check_exact(path: Path, expected: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != expected:
        raise RegistryError(f"generated artifact drift: {path.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "check"))
    args = parser.parse_args(argv)
    registry, ledger = load(REGISTRY), load(LEDGER)
    state = validate(registry, ledger)
    artifacts = {
        HEADER: header_text(registry, state),
        PY_VIEWS: python_views_text(state),
        FIXTURE: render_json(fixture_value(registry, state)),
        REPORT: render_json(report_value(registry, state)),
    }
    if args.action == "generate":
        for path, content in artifacts.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        action = "GENERATED"
    else:
        for path, content in artifacts.items():
            check_exact(path, content)
        action = "PASS"
    cases = len(state["entries"]) * 4 + len(registry["safety_cases"]) * 3
    evaluations = cases * len(registry["engines"])
    print(
        f"v2-native-function-registry: {action} active={len(state['active'])} "
        f"public={len(state['entries'])} restricted={len(state['restricted'])} "
        f"cases={cases} engines=4 evaluations={evaluations} registry_sha256={sha(REGISTRY)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, SyntaxError, ValueError, RegistryError) as exc:
        print(f"v2-native-function-registry: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
