#!/usr/bin/env python3
"""Prove whether the commissioned Link-92 trace fix fits library-only scope.

The owner pre-bound a descope edge: ``inspect`` may implement the fix only if
the delivered product already exposes the current function-cell *value* and a
transaction form capable of publishing the persistent wrapper together with
the cell mutation.  This gate audits the shipped Link-92 ABI and executes an
indistinguishability proof.  It changes no library, compiler, core, media, or
device state.
"""

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
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
REGISTRY = ROOT / "config/v2-native-function-registry.json"
DISPATCH = ROOT / "src/v2_native_function_dispatch.h"
EVAL = ROOT / "src/eval.c"
VM = ROOT / "src/vm.c"
PRODUCT = ROOT / "src/c2_product_runtime.c"
PROFILE = ROOT / "config/workbench.mk"
COMPILER = ROOT / (
    "build/post-promotion/v112/compiler-tier/c2-compiler-sources/lib/lcc.lisp"
)
TRACE = ROOT / "lib/comfort-trace.lisp"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d3-trace-host-attribution.json"
)
GATES = ROOT / "mk/gates.mk"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-trace-fix-library-scope.json"
)
FORMAT = "lisp65-c2.3-v1.12-link92-r5-trace-fix-library-scope-v2"
RECORDED_ON = "2026-08-09"
HISTORICAL_AUTHORITY = "f426f7c71b5e85bcbec0a181fa3d1e4838e6388f"


class ScopeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ScopeError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bytes(path: Path) -> bytes:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    result = subprocess.run(
        ["git", "show", f"{HISTORICAL_AUTHORITY}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout


def git_text(path: Path) -> str:
    return git_bytes(path).decode("utf-8")


def git_json(path: Path) -> dict[str, Any]:
    value = json.loads(git_text(path))
    require(isinstance(value, dict), f"historical JSON object required: {path}")
    return value


def bind_git(path: Path) -> dict[str, Any]:
    raw = git_bytes(path)
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "git_commit": HISTORICAL_AUTHORITY,
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def delivered_surface() -> dict[str, Any]:
    # This is a sealed Link-92 claim.  Reading the live ABI would rewrite
    # history as soon as the explicitly commissioned successor capability
    # appears.  All tracked product authorities therefore come from the
    # owner-descope commit itself.
    ledger = git_json(LEDGER)
    registry = git_json(REGISTRY)
    dispatch = git_text(DISPATCH)
    eval_source = git_text(EVAL)
    vm_source = git_text(VM)
    profile = git_text(PROFILE)
    compiler = COMPILER.read_text(encoding="utf-8")

    prims = {
        int(row["id"]): row["canonical_name"]
        for row in ledger["prim_identities"]
    }
    registry_names = {row["name"] for row in registry["entries"]}
    registry_names.update(row["name"] for row in registry["restricted_primitives"])
    getter_names = {
        "symbol-function", "%symbol-function", "function-cell", "%function-cell"
    }
    require(not getter_names.intersection(prims.values()),
            "a function-cell getter appeared in the active primitive ABI")
    require(not getter_names.intersection(registry_names),
            "a function-cell getter appeared in the delivered registry")
    require(not any(f'X("{name}"' in dispatch for name in getter_names),
            "a function-cell getter appeared in generated dispatch")
    require(prims.get(21) == "%disk-poke", "Prim 21 identity drift")
    require(prims.get(36) == "function-kind", "Prim 36 identity drift")
    require(prims.get(38) == "lcc-install", "Prim 38 identity drift")
    require(prims.get(66) == "%c2-control", "Prim 66 identity drift")

    require(
        "case P_SETFN:   set_sym_function(car(args), cadr(args)); return cadr(args);"
        in eval_source,
        "set-symbol-function return contract drift",
    )
    require(
        "if (IS_BCODE(f)) return k_bytecode;" in eval_source
        and "if (IS_BCODE(function)) { *result = k_bytecode; return 1; }"
        in eval_source,
        "function-kind no longer collapses all BCODE values to their kind",
    )
    require(
        "case 66: /* %c2-control -- the sole born-code emitter */" in vm_source
        and "return c2_session_emit_control(a[0], a[1]);" in vm_source,
        "%c2-control contract drift",
    )
    require("-DLISP65_TREEWALK_STRIP" in profile,
            "Link-92 product no longer strips treewalk")
    require(
        "obj r = is_sym(x) ? sym_function(x) : eval_env(x, env);" in eval_source,
        "treewalk function-cell contrast drift",
    )
    require(
        "((eq op 'function)" in compiler
        and "(%lcc-push-lit cs (car args))" in compiler,
        "delivered compiler function-symbol lowering drift",
    )
    return {
        "active_primitive_count": len(prims),
        "function_cell_getter_names_checked": sorted(getter_names),
        "function_cell_getter_delivered": False,
        "nearby_capabilities": {
            "21": "%disk-poke (not a getter)",
            "36": "function-kind (kind only)",
            "38": "lcc-install (install result only)",
            "66": "%c2-control (session emit control only)",
            "set-symbol-function": "writes cell; returns the supplied new value",
        },
        "treewalk_only_contrast": (
            "(function SYMBOL) reads sym_function, but Link-92 strips treewalk"
        ),
        "delivered_compiler_semantics": "(function SYMBOL) -> PUSHLIT symbol",
    }


def indistinguishability_proof() -> dict[str, Any]:
    states = [
        {"name": "A", "actual_old_cell": {"kind": "BCODE", "ordinal": 748}},
        {"name": "B", "actual_old_cell": {"kind": "BCODE", "ordinal": 749}},
    ]
    observations = []
    for state in states:
        observations.append({
            "state": state["name"],
            "compiled_function_form": {"symbol": "capitalize"},
            "function_kind": "bytecode",
            "set_symbol_function_result": {"kind": "wrapper"},
            "required_exact_capture": state["actual_old_cell"],
        })
    observable_projection = [
        {
            "compiled_function_form": row["compiled_function_form"],
            "function_kind": row["function_kind"],
            "set_symbol_function_result": row["set_symbol_function_result"],
        }
        for row in observations
    ]
    require(observable_projection[0] == observable_projection[1],
            "test states unexpectedly distinguishable through delivered Lisp")
    require(
        observations[0]["required_exact_capture"]
        != observations[1]["required_exact_capture"],
        "test states do not require different restoration values",
    )
    return {
        "states": observations,
        "delivered_observations_equal": True,
        "required_restoration_values_equal": False,
        "conclusion": (
            "no library program over the delivered observations can capture "
            "the exact prior function-cell value for both states"
        ),
    }


def transaction_boundary() -> dict[str, Any]:
    source = PRODUCT.read_text(encoding="utf-8")
    required = (
        "old = sym_function(symbol);",
        "journal[2] = (uint8_t)old;",
        "journal[3] = (uint8_t)((uint16_t)old >> 8);",
        "set_sym_function(symbol, published);",
        "c2_journal_count = 0;",
        "return definition_name != NIL ? definition_name : MK_BCODE(main);",
    )
    require(all(item in source for item in required),
            "C2 publication journal/return contract drift")
    return {
        "persistent_install": (
            "C2 publication captures the old cell internally, journals it, "
            "publishes the new export, clears the journal, and returns the "
            "definition name (or main BCODE), not the old cell"
        ),
        "library_setter": (
            "set-symbol-function is outside that publication API and returns "
            "the supplied new value"
        ),
        "old_cell_exposed_to_lisp": False,
        "atomic_library_install_and_cell_mutation_available": False,
        "conclusion": (
            "a persistent wrapper may be published, but inspect cannot both "
            "capture the exact old callable and atomically bind/restorable-state "
            "with the delivered transaction surface"
        ),
    }


def validate_result(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT, "scope receipt format drift")
    require(value.get("historical_authority_commit") == HISTORICAL_AUTHORITY,
            "sealed Link-92 authority commit drift")
    require(
        value.get("status") == "descope-required-missing-function-cell-capability",
        "library-only descope status dimmed",
    )
    require(value["delivered_surface"]["function_cell_getter_delivered"] is False,
            "missing getter conclusion dimmed")
    require(
        value["indistinguishability"]["delivered_observations_equal"] is True
        and value["indistinguishability"]["required_restoration_values_equal"]
        is False,
        "function-cell indistinguishability proof dimmed",
    )
    require(
        value["transaction_boundary"]["old_cell_exposed_to_lisp"] is False
        and value["transaction_boundary"]
        ["atomic_library_install_and_cell_mutation_available"] is False,
        "transaction capability absence dimmed",
    )
    require(value["scope_disposition"] == {
        "commissioned_library_fix": "not-representable-on-delivered-Link-92-ABI",
        "prebound_edge": "triggered",
        "inspect_source_changed": False,
        "compiler_or_core_changed": False,
        "media_rebuilt": False,
        "device_contact": False,
        "recontact_authorized": False,
        "next_authority": "owner-descope-or-explicit-core-capability-decision",
    }, "scope boundary broadened")
    require(
        value["owner_options"][0]["id"] == "descope-trace-untrace-from-v1.4"
        and value["owner_options"][0]["recommended"] is True,
        "narrow release recommendation drift",
    )


def derive() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(
        attribution.get("status") == "host-red-trace-transient-closure-escape",
        "trace host-attribution authority drift",
    )
    trace_source = TRACE.read_text(encoding="utf-8")
    require(
        "(function ,name)" in trace_source
        and "(set-symbol-function" in trace_source,
        "commissioned trace source shape drift",
    )
    gates = GATES.read_text(encoding="utf-8")
    wiring = (
        "c2-v112-trace-fix-scope-selftest:",
        "python3 tools/host-lisp/c2_v112_trace_fix_scope.py selftest",
        "c2-v112-trace-fix-scope-check:",
        "python3 tools/host-lisp/c2_v112_trace_fix_scope.py check",
        "check-source: c2-v112-trace-fix-scope-check",
    )
    require(all(item in gates for item in wiring),
            "trace library-scope permanent gate wiring absent")
    result = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "descope-required-missing-function-cell-capability",
        "historical_authority_commit": HISTORICAL_AUTHORITY,
        "bindings": {
            name: (bind(path) if name in {
                "delivered_compiler", "commissioned_trace_source"
            } else bind_git(path))
            for name, path in {
                "trace_host_attribution": ATTRIBUTION,
                "bytecode_abi_ledger": LEDGER,
                "native_function_registry": REGISTRY,
                "generated_native_dispatch": DISPATCH,
                "eval_core": EVAL,
                "vm_core": VM,
                "C2_product_runtime": PRODUCT,
                "Link_92_profile": PROFILE,
                "delivered_compiler": COMPILER,
                "commissioned_trace_source": TRACE,
            }.items()
        },
        "delivered_surface": delivered_surface(),
        "indistinguishability": indistinguishability_proof(),
        "transaction_boundary": transaction_boundary(),
        "scope_disposition": {
            "commissioned_library_fix": "not-representable-on-delivered-Link-92-ABI",
            "prebound_edge": "triggered",
            "inspect_source_changed": False,
            "compiler_or_core_changed": False,
            "media_rebuilt": False,
            "device_contact": False,
            "recontact_authorized": False,
            "next_authority": "owner-descope-or-explicit-core-capability-decision",
        },
        "owner_options": [
            {
                "id": "descope-trace-untrace-from-v1.4",
                "recommended": True,
                "effect": (
                    "ship who-calls and the two string utilities; remove the "
                    "broken trace/untrace surface from both v1.4 media variants"
                ),
                "cost_class": "release-library-and-media-closure-only",
            },
            {
                "id": "commission-atomic-trace-cell-capability",
                "recommended": False,
                "effect": (
                    "add an explicit core ABI that captures the old function "
                    "cell and atomically publishes/restores a persistent wrapper"
                ),
                "cost_class": "product-core-ABI-new-link-and-hardware-acceptance",
            },
            {
                "id": "defer-v1.4-release",
                "recommended": False,
                "effect": "hold all v1.4 freight behind the larger capability block",
                "cost_class": "release-delay",
            },
        ],
        "claim_limit": (
            "This proves only that the commissioned correctness contract cannot "
            "be represented as an inspect-only change on the delivered Link-92 "
            "ABI. It does not authorize a core/compiler change, a media rebuild, "
            "a device contact, or an unchanged-byte retry."
        ),
    }
    validate_result(result)
    return result


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "invent-function-cell-getter": lambda x: x["delivered_surface"].update(
            function_cell_getter_delivered=True
        ),
        "collapse-required-old-values": lambda x: x["indistinguishability"].update(
            required_restoration_values_equal=True
        ),
        "claim-observations-distinguish-old-bcode": lambda x: x[
            "indistinguishability"
        ].update(delivered_observations_equal=False),
        "expose-journal-old-cell": lambda x: x["transaction_boundary"].update(
            old_cell_exposed_to_lisp=True
        ),
        "invent-atomic-library-transaction": lambda x: x[
            "transaction_boundary"
        ].update(atomic_library_install_and_cell_mutation_available=True),
        "authorize-inspect-source-change": lambda x: x["scope_disposition"].update(
            inspect_source_changed=True
        ),
        "authorize-core-scope-growth": lambda x: x["scope_disposition"].update(
            compiler_or_core_changed=True
        ),
        "authorize-recontact": lambda x: x["scope_disposition"].update(
            recontact_authorized=True
        ),
        "replace-owner-decision-with-library-fix": lambda x: x[
            "scope_disposition"
        ].update(next_authority="continue-library-fix"),
        "recommend-silent-core-growth": lambda x: x["owner_options"][0].update(
            recommended=False
        ),
    }
    rejected = []
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate_result(candidate)
        except (ScopeError, KeyError):
            rejected.append(name)
        else:
            raise ScopeError(f"trace scope mutation survived: {name}")
    require(len(rejected) == len(mutations), "trace scope mutation count drift")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "check", "record"))
    args = parser.parse_args()
    try:
        value = derive()
        rejected = rejected_mutations(value)
        value["mutations_rejected"] = rejected
        value["mutation_count"] = len(rejected)
        if args.action == "selftest":
            print(f"c2-v112-trace-fix-scope: PASS mutations={len(rejected)}")
            return 0
        if args.action == "record":
            write_json(RECEIPT, value)
            print(f"c2-v112-trace-fix-scope: WROTE {RECEIPT.relative_to(ROOT)}")
            return 0
        require(load(RECEIPT) == value, "trace fix scope receipt is stale")
        print("c2-v112-trace-fix-scope: PASS descope-required")
        return 0
    except (ScopeError, KeyError, TypeError, ValueError, OSError) as error:
        print(f"c2-v112-trace-fix-scope: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
