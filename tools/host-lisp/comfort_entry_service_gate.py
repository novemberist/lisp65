#!/usr/bin/env python3
"""Closed private service registration and actual prebuilt CALLPRIM inventory.

This source/prebuilt gate is not the native admission proof or the packed-world
gate. The product card must run those independently on its executable world.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import bytecode_p0 as B
import bytecode_p0_compiler as C
import v2_native_function_registry as R
from bytecode_abi_ledger import COMFORT_MODES

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "config/comfort-entry-service.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def calls(node, name):
    if not isinstance(node, list) or not node:
        return 0
    if node[0] == "quote":
        return 0
    return int(node[0] == name) + sum(calls(child, name) for child in node)


def mode_calls(node):
    if not isinstance(node, list) or not node or node[0] == "quote":
        return []
    own = []
    if node[0] == "set-symbol-value":
        args = node[1:]
        if not args:
            own = [0]
        elif len(args) == 3 and args[2] != 69:
            require(args[1:] == [["set-symbol-value", ["quote", "repl"]], 70],
                    "unresolved or invalid Prim20 mode selector/entry identity")
            own = [3]
    return own + [item for child in node for item in mode_calls(child)]


def validate(authority, ledger, registry, sources):
    name, ident = authority["name"], authority["prim_id"]
    require((name, ident) == ("set-symbol-value", 20), "living primitive identity changed")
    require(authority["arities"] == [0, 3] and authority["request_selector"] == 70
            and authority["query_consumes"] is False, "Prim20 mode contract changed")
    require(ledger["prim_mode_extensions"] == COMFORT_MODES, "mode registration omitted/changed")
    require(authority["visibility"] == "private"
            and authority["public_surface_change"] is False
            and authority["ordinary_result_is_control"] is False,
            "private/control claim changed")
    require(authority["caller"] == {"source": "lib/repl-comfort.lisp", "function": "repl"},
            "caller allowlist changed or wildcard inserted")
    identities = [r for r in ledger["prim_identities"] if r["id"] == ident or r["canonical_name"] == name]
    require(identities == [{"id": ident, "canonical_name": name}], "registration omitted/duplicated")
    active = next(p for p in ledger["profiles"] if p["id"] == "dialect-v2")["prim_ids"]["active"]
    require(ident in active, "private service inactive")
    rows = [r for r in registry["restricted_primitives"] if r["name"] == name or r["value"] == ident]
    require(len(rows) == 1 and rows[0]["restricted_views"] == authority["omitted_views"]
            == ["apply", "function-kind"], "private omission row missing or weakened")
    require(not any(r["name"] == name for r in registry["entries"]), "private service exported")

    inventory = []
    entry = None
    for path, text in sources.items():
        # Files without the token cannot contain a source call of this name;
        # the compiled packed inventory remains an independent final gate.
        if name not in text:
            continue
        for form in C.parse_all(text):
            modes = mode_calls(form)
            if modes:
                require(isinstance(form, list) and form[0] == "defun", "service outside a function")
                inventory.append({"source": path, "function": form[1], "modes": modes})
                entry = form
    require(inventory == [{**authority["caller"], "modes": [0, 3]}], "private consumer population drift")
    _, code = C.compile_top_form(entry, B.Heap(), strict_arity=True,
                                abi_profile="dialect-v2", abi_ledger=ledger,
                                prebuilt_primitives=True)
    pc, emitted = 0, []
    while pc < len(code.payload):
        start = pc
        spec, operand, pc = B.decode_instruction(code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger)
        if spec.mnemonic == "CALLPRIM" and operand[0] == ident:
            emitted.append({"offset": start, "prim_id": ident, "argc": operand[1]})
    require([e["argc"] for e in emitted if e["argc"] != 1] == [0, 3],
            "emitted query/request omitted or wrong arity")
    return {"source_inventory": inventory, "emitted_inventory": emitted,
            "entry_bytes": len(code.encode()), "entry_sha256": hashlib.sha256(code.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    authority, ledger, registry = (json.loads(p.read_text()) for p in (AUTHORITY, R.LEDGER, R.REGISTRY))
    sources = {str(p.relative_to(ROOT)): p.read_text() for p in sorted((ROOT / "lib").rglob("*.lisp"))}
    result = validate(authority, ledger, registry, sources)
    mutations = []
    for kind in ("registration-omitted", "service-inactive", "omission-weakened",
                 "private-exported", "caller-wildcard", "caller-omitted", "extra-caller", "ordinary-result-control"):
        a, l, r, s = deepcopy((authority, ledger, registry, sources))
        if kind == "registration-omitted": l["prim_mode_extensions"].pop(0)
        elif kind == "service-inactive": next(p for p in l["profiles"] if p["id"] == "dialect-v2")["prim_ids"]["active"].remove(20)
        elif kind == "omission-weakened": next(x for x in r["restricted_primitives"] if x["value"] == 20)["restricted_views"].remove("apply")
        elif kind == "private-exported": r["entries"].append({"name": "set-symbol-value"})
        elif kind == "caller-wildcard": a["caller"]["function"] = "*"
        elif kind == "caller-omitted": s["lib/repl-comfort.lisp"] = s["lib/repl-comfort.lisp"].replace("(set-symbol-value)", "nil")
        elif kind == "extra-caller": s["lib/extra-caller.lisp"] = "(defun extra () (set-symbol-value))"
        else: a["ordinary_result_is_control"] = True
        try:
            validate(a, l, r, s)
        except ValueError as error:
            mutations.append({"name": kind, "rejected": str(error)})
        else:
            raise ValueError("mutation survived: " + kind)
    result.update({"status": "source-and-prebuilt-registration-pass", "mutations": mutations,
                   "native_admission_proven": False, "packed_population_proven": False,
                   "authority_sha256": hashlib.sha256(AUTHORITY.read_bytes()).hexdigest(),
                   "public_entry_count": len(registry["entries"])})
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
