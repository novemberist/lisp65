#!/usr/bin/env python3
"""Bind the Link-92 D3 trace First Red to the delivered compiler/runtime.

This is an attribution gate, not a trace implementation and not a device
runner.  It executes the delivered ``trace`` and ``untrace`` macros with the
delivered Link-92 compiler carrier, decodes the resulting CodeObjects and
replays the externally visible function-cell state across the target's
transient C2 append/rollback boundary.

Two claims deliberately remain separate:

* D3 polling was unsafe because the target carrier sends this non-direct REPL
  form through a transient C2 append/C2J transaction.
* the exact delivered expansion has an independent product defect: the
  compiler lowers ``(function SYMBOL)`` to a symbol literal, and the wrapper
  closure that escapes through ``set-symbol-function`` names a transient
  helper removed by rollback.

Therefore the observed target red is crossing-consistent but is not closed as
harness-only.  No retry on unchanged product bytes is authorized here.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_link75_require_defstruct_host_attribution as CARRIER  # noqa: E402
import c2_v111_compiler_locality as LOCALITY  # noqa: E402
import c2_v16_defstruct_phase_a as PHASE_A  # noqa: E402


COMPILER = ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"
INSPECT = ROOT / "build/post-promotion/v112/inspect/inspect.manifest.json"
STRING_EXTRA = ROOT / (
    "build/post-promotion/v112/string-extra/string-extra.manifest.json"
)
MEDIA = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5-split/base/"
    "lisp65-library.d81"
)
MEDIA_MANIFEST = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5-split/"
    "base-candidate-manifest.json"
)
STATIC_C2D = ROOT / (
    "build/c2.3/v1.4.0-candidate-product-link92-r5/static-plane/"
    "narrow-static/v6-semantics/initial.c2d-v6.bin"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-d3-trace-first-red.json"
)
POLICY = ROOT / "config/c2-repl-observation-policy.json"
PLAN = ROOT / "docs/planning/1.12-v1.4.0-release-work-plan.md"
TRACE_SOURCE = ROOT / "lib/comfort-trace.lisp"
EVAL_RUNTIME = ROOT / "lib/dialect-v2/eval-runtime.lisp"
COMPILER_SOURCE = ROOT / (
    "build/post-promotion/v112/compiler-tier/c2-compiler-sources/lib/lcc.lisp"
)
EVAL_SOURCE = ROOT / "src/eval.c"
PRODUCT_RUNTIME = ROOT / "src/c2_product_runtime.c"
VM_SOURCE = ROOT / "src/vm.c"
PROFILE = ROOT / "config/workbench.mk"
GATES = ROOT / "mk/gates.mk"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d3-trace-host-attribution.json"
)
FORMAT = "lisp65-c2.3-v1.12-link92-r5-d3-trace-host-attribution-v1"
RECORDED_ON = "2026-08-08"
C2D_ENTRY_CAP = 2048


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


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


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def static_geometry() -> dict[str, int]:
    raw = STATIC_C2D.read_bytes()
    require(
        len(raw) == 33840 and raw[:8] == b"C2D\0\x06\x30\x20\x0a",
        "Link-92 static C2D identity/geometry drift",
    )
    u16 = lambda at: struct.unpack_from("<H", raw, at)[0]
    u32 = lambda at: struct.unpack_from("<I", raw, at)[0]
    value = {
        "generation": u16(10),
        "images": u16(12),
        "entries": u16(16),
        "resolutions": u16(20),
        "roots": u16(24),
        "immutable_images": u16(38),
        "build_id": u32(44),
    }
    require(
        value == {
            "generation": 1,
            "images": 6,
            "entries": 748,
            "resolutions": 2913,
            "roots": 350,
            "immutable_images": 6,
            "build_id": 0x3B48650D,
        },
        f"Link-92 static geometry drift: {value}",
    )
    return value


def code_row(heap: B.Heap, code: B.CodeObject, ledger: dict[str, Any]) -> dict[str, Any]:
    instructions = []
    pc = 0
    while pc < len(code.payload):
        at = pc
        spec, operand, pc = B.decode_instruction(
            code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger
        )
        if isinstance(operand, tuple):
            encoded_operand: Any = list(operand)
        else:
            encoded_operand = operand
        instructions.append(
            {"pc": at, "opcode": spec.code, "mnemonic": spec.mnemonic,
             "operand": encoded_operand}
        )
    semantic = {
        "nargs": code.nargs,
        "nlocals": code.nlocals,
        "flags": code.flags,
        "literals": [STD._obj_spec(heap, item) for item in code.littab],
        "payload_hex": bytes(code.payload).hex(),
    }
    return {
        **semantic,
        "encoded_bytes": len(code.encode()),
        "encoded_sha256": sha(code.encode()),
        "semantic_sha256": sha(canonical(semantic)),
        "instructions": instructions,
    }


def subsequence(rows: list[dict[str, Any]], expected: list[tuple[str, Any]]) -> bool:
    cursor = 0
    for mnemonic, operand in expected:
        while cursor < len(rows) and not (
            rows[cursor]["mnemonic"] == mnemonic
            and rows[cursor]["operand"] == operand
        ):
            cursor += 1
        if cursor == len(rows):
            return False
        cursor += 1
    return True


def exact_compilation() -> dict[str, Any]:
    carrier = LOCALITY.carrier_class(COMPILER)()
    identities: dict[str, dict[str, Any]] = {}
    for manifest, role in ((STRING_EXTRA, "string-extra"), (INSPECT, "inspect")):
        directory, macros, names = PHASE_A.manifest_directory(
            carrier.heap, manifest, identities, role=role
        )
        carrier.directory.update(directory)
        carrier.macro_symbols.update(macros)
        carrier.code_names.update(names)

    argument = carrier.heap.intern("capitalize")
    expansions: dict[str, str] = {}
    compiled: dict[str, list[dict[str, Any]]] = {}
    compile_steps: dict[str, int] = {}
    for macro in ("trace", "untrace"):
        symbol = carrier.heap.intern(macro)
        require(symbol in carrier.macro_symbols, f"delivered {macro} is not a macro")
        macro_vm = carrier.vm()
        expansion = macro_vm.run(carrier.directory[symbol], [argument])
        expansions[macro] = carrier.heap.obj_to_text(expansion)
        compile_vm = carrier.vm()
        fnlist = compile_vm.run(
            carrier.directory[carrier.compiler_symbol], [expansion]
        )
        values = CARRIER.proper_list(carrier.heap, fnlist, macro + ".fnlist")
        compiled[macro] = [
            code_row(
                carrier.heap,
                carrier.decode_code(value, f"{macro}.object-{index}"),
                carrier.ledger,
            )
            for index, value in enumerate(values)
        ]
        compile_steps[macro] = compile_vm.steps

    require(len(compiled["trace"]) == 2, "trace no longer emits helper plus main")
    helper, main = compiled["trace"]
    require(
        (helper["nargs"], helper["nlocals"], helper["flags"],
         helper["encoded_bytes"], len(bytes.fromhex(helper["payload_hex"])))
        == (0, 2, 3, 64, 45),
        "trace helper semantic identity drift",
    )
    require(
        (main["nargs"], main["nlocals"], main["flags"],
         main["encoded_bytes"], len(bytes.fromhex(main["payload_hex"])))
        == (0, 1, 2, 85, 68),
        "trace main semantic identity drift",
    )
    require(
        subsequence(
            main["instructions"],
            [
                ("PUSHLIT", 1), ("STOREL", 0),
                ("PUSHLIT", 1), ("LOADL", 0),
                ("CLOSURE", [3, 1]), ("CALL", [4, 2]),
            ],
        ),
        "trace no longer captures symbol literal and installs helper closure",
    )
    require(
        main["literals"][1] == {"symbol": "capitalize"}
        and main["literals"][3] == [{"symbol": "%lcc-helper"}, 0]
        and main["literals"][4] == {"symbol": "set-symbol-function"},
        "trace main literal identity drift",
    )
    require(len(compiled["untrace"]) == 1, "untrace object count drift")
    untrace = compiled["untrace"][0]
    require(
        subsequence(
            untrace["instructions"],
            [("CDR", None), ("CALL", [3, 2])],
        )
        and untrace["literals"][3] == {"symbol": "set-symbol-function"},
        "untrace no longer restores the recorded cdr into the function cell",
    )
    return {
        "macro_expansions": {
            name: {"text": text, "sha256": sha(text.encode("utf-8"))}
            for name, text in expansions.items()
        },
        "compiler_steps": compile_steps,
        "trace_objects": compiled["trace"],
        "untrace_objects": compiled["untrace"],
    }


def runtime_path() -> dict[str, Any]:
    profile = PROFILE.read_text(encoding="utf-8")
    eval_runtime = EVAL_RUNTIME.read_text(encoding="utf-8")
    eval_source = EVAL_SOURCE.read_text(encoding="utf-8")
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    compiler = COMPILER_SOURCE.read_text(encoding="utf-8")
    vm = VM_SOURCE.read_text(encoding="utf-8")
    require("-DLISP65_TREEWALK_STRIP" in profile,
            "Link-92 product no longer has the treewalk-stripped profile")
    require("(t (lcc-install compiled 't))" in eval_runtime,
            "non-definition lcc-run carrier drift")
    require("result = c2_product_install(fnlist, defname);" in eval_source,
            "target lcc-install bridge drift")
    required_product = (
        "#define C2D_ENTRY_CAP 2048u",
        "uint8_t transient = (uint8_t)(definition_name == lisp_t);",
        "c2_session_emit_add(fnlist,\n            transient ? NIL : definition_name, 0u);",
        "append_ok = c2_append_begin(length, &before, &main",
        "- 1u + C2D_ENTRY_CAP);",
        "result = vm_run_dir((int)main, 0, 0);",
        "if (!c2_append_rollback(&before))",
    )
    require(all(fragment in product for fragment in required_product),
            "target transient append/run/rollback path drift")
    require(
        "((eq op 'function)" in compiler
        and "(%lcc-push-lit cs (car args))" in compiler,
        "delivered compiler no longer lowers (function SYMBOL) to PUSHLIT",
    )
    require(
        "if (op == sf_function)" in eval_source
        and "obj r = is_sym(x) ? sym_function(x) : eval_env(x, env);" in eval_source,
        "treewalk function-cell contrast drift",
    )
    require(
        "clo = alloc(T_CLOSURE)" in vm
        and "cell_set_a(clo, MK_BCODE(di));" in vm
        and "res = vm_run_dir((int)BCODE_IDX(cell_a(fn)), argv, na);" in vm,
        "target closure/directory semantics drift",
    )
    return {
        "profile": "treewalk-stripped",
        "repl_non_direct_form": "%c2-compile-form -> lcc-install compiled t",
        "target_install": "c2_product_install transient append -> vm_run_dir -> rollback",
        "journal_class": "C2D transient append/C2J transaction",
        "transient_image_export_name": "NIL",
        "rollback_scope": "C2 append/publication state; not arbitrary function-cell side effects",
        "function_symbol_lowering": "PUSHLIT symbol (not sym_function value)",
        "treewalk_contrast": "(function SYMBOL) reads sym_function",
        "closure_target": "T_CLOSURE.a = MK_BCODE(transient helper ordinal)",
    }


def poststate_replay(compilation: dict[str, Any], geometry: dict[str, int]) -> dict[str, Any]:
    string_entries = len(load(STRING_EXTRA)["entries"])
    inspect_entries = len(load(INSPECT)["entries"])
    before_entries = geometry["entries"] + string_entries + inspect_entries
    helper_physical = before_entries
    main_physical = before_entries + 1
    helper_ordinal = C2D_ENTRY_CAP + helper_physical
    main_ordinal = C2D_ENTRY_CAP + main_physical
    main = compilation["trace_objects"][1]

    # The decoded main proves that LOADL 0 receives PUSHLIT(capitalize), not
    # the existing BCODE function cell.  Replaying only state visible outside
    # the transient transaction is sufficient and avoids inventing a second
    # target VM.
    captured_original = main["literals"][1]
    installed = {
        "kind": "T_CLOSURE",
        "code": {"kind": "BCODE", "ordinal": helper_ordinal},
        "upvalues": [captured_original],
    }
    active_entries = before_entries + len(compilation["trace_objects"])
    require(main_ordinal == C2D_ENTRY_CAP + active_entries - 1,
            "trace main is not the transient append main object")

    after_rollback_entries = before_entries
    rollback_entry_first = C2D_ENTRY_CAP + before_entries
    helper_normalized = helper_ordinal - C2D_ENTRY_CAP
    helper_live_after_rollback = (
        helper_ordinal >= rollback_entry_first
        and helper_normalized < after_rollback_entries
    )
    require(not helper_live_after_rollback,
            "mutation: transient helper unexpectedly survived rollback")
    invocation = {
        "function_cell": installed,
        "directory_length_at_helper_ordinal": 0,
        "target_status": "VM_DIRMISS",
        "target_detail": f"BCODE ordinal {helper_ordinal}",
        "reason": "vm_run_dir rejects the removed transient helper ordinal",
    }
    untrace_restoration = {
        "recorded_original": captured_original,
        "restored_function_cell": captured_original,
        "restored_callable_kind": "symbol-not-BCODE",
        "matches_pre_trace_BCODE": False,
    }
    require(captured_original == {"symbol": "capitalize"},
            "mutation: replay substituted an abstract/function-cell original")
    require(not untrace_restoration["matches_pre_trace_BCODE"],
            "mutation: untrace incorrectly restored the pre-trace BCODE")
    return {
        "before": {
            "static_entries": geometry["entries"],
            "required_library_entries": string_entries + inspect_entries,
            "directory_entries": before_entries,
            "capitalize_function_cell": "published BCODE",
            "C2J": "CLEAR",
        },
        "active_transient_append": {
            "helper_ordinal": helper_ordinal,
            "helper_physical_entry": helper_physical,
            "main_ordinal": main_ordinal,
            "main_physical_entry": main_physical,
            "directory_entries": active_entries,
            "installed_function_cell": installed,
            "C2J": "guard-sensitive transient append transaction",
        },
        "after_rollback": {
            "directory_entries": after_rollback_entries,
            "transient_entry_first": rollback_entry_first,
            "helper_normalized_entry": helper_normalized,
            "helper_live": helper_live_after_rollback,
            "function_cell_side_effect_restored_by_C2_rollback": False,
            "C2J": "CLEAR",
        },
        "first_traced_call": invocation,
        "untrace": untrace_restoration,
    }


def validate_policy(value: dict[str, Any]) -> None:
    require(value.get("format") == "lisp65-repl-observation-policy-v1",
            "observation policy format drift")
    require(value.get("default") == {
        "classification": "persistent-until-proven-nonpersistent",
        "monitor_or_screenshot_polling": "forbidden",
        "observation": "one-postcondition-read-after-bound-quiet-window-or-product-completion",
        "polling_exception": "requires-bound-nonpersistent-proof",
    }, "fail-closed observation default drift")
    trace = value.get("active_trace_disposition", {})
    require(
        trace.get("candidate") == "Link-92-r5"
        and trace.get("classification") == "persistent-transient-C2D-C2J"
        and trace.get("recontact_authorized") is False
        and trace.get("unchanged_product_retry") == "forbidden-host-red",
        "trace retry was authorized or persistence classification dimmed",
    )
    repeat = trace.get("future_repeat_contract", {})
    require(
        repeat.get("observations_during_sequence") == 0
        and repeat.get("postcondition_reads") == 1
        and repeat.get("postcondition_must_cover")
        == ["trace-install", "traced-call-output", "untrace-restoration"],
        "quiet trace lifecycle repeat contract drift",
    )


def audit_policy() -> dict[str, Any]:
    value = load(POLICY)
    validate_policy(value)
    return value


def validate_result(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT, "attribution receipt format drift")
    require(value.get("status") == "host-red-trace-transient-closure-escape",
            "trace host-red status dimmed")
    claims = value["attribution"]
    require(claims == {
        "polling_policy": "proven-invalid-for-this-form",
        "observed_red_cause": "not-separated-crossing-consistent-and-product-red-capable",
        "host_replay": "red",
        "product_mechanism": "symbol-capture-plus-transient-helper-escape-across-rollback",
        "quiet_retry_on_unchanged_bytes": "forbidden",
        "next_authority": "owner-disposition-before-fix-or-recontact",
    }, "trace attribution claim broadened or dimmed")
    replay = value["exact_host_replay"]
    require(
        replay["first_traced_call"]["target_status"] == "VM_DIRMISS"
        and replay["after_rollback"]["helper_live"] is False
        and replay["untrace"]["matches_pre_trace_BCODE"] is False,
        "exact trace poststate no longer proves the two product failures",
    )
    require(value["execution_accounting"] == {
        "hardware_contacts": 0,
        "product_bytes_changed": 0,
        "media_bytes_changed": 0,
        "recontacts_authorized": 0,
    }, "host-only attribution boundary drift")


def derive() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    require(
        first_red.get("status") == "first-red-d3-trace-install-under-result-poll"
        and first_red["first_red"]["form"] == "(trace capitalize)"
        and first_red["first_red"]["runner_behavior"]
        == "the result helper took repeated screenshots while waiting for the trace result"
        and first_red["disposition"]["recontact_authorized"] is False,
        "D3 trace First Red authority drift",
    )
    media = load(MEDIA_MANIFEST)
    require(
        media["library"]["D81"]["sha256"] == sha(MEDIA.read_bytes())
        and [row["name"] for row in media["library"]["index_rows"]]
        == ["string-extra", "inspect"],
        "split media identity/order drift",
    )
    geometry = static_geometry()
    compilation = exact_compilation()
    path = runtime_path()
    replay = poststate_replay(compilation, geometry)
    policy = audit_policy()
    gates = GATES.read_text(encoding="utf-8")
    required_wiring = (
        "c2-v112-trace-red-attribution-selftest:",
        "python3 tools/host-lisp/c2_v112_trace_red_attribution.py selftest",
        "c2-v112-trace-red-attribution-check:",
        "python3 tools/host-lisp/c2_v112_trace_red_attribution.py check",
        "check-source: c2-v112-trace-red-attribution-check",
    )
    require(all(item in gates for item in required_wiring),
            "trace attribution permanent gate wiring absent")
    result = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "host-red-trace-transient-closure-escape",
        "bindings": {
            name: bind(pathname)
            for name, pathname in {
                "first_red": FIRST_RED,
                "library_medium": MEDIA,
                "media_manifest": MEDIA_MANIFEST,
                "static_C2D": STATIC_C2D,
                "compiler_manifest": COMPILER,
                "inspect_manifest": INSPECT,
                "string_extra_manifest": STRING_EXTRA,
                "trace_source": TRACE_SOURCE,
                "eval_runtime": EVAL_RUNTIME,
                "compiler_source": COMPILER_SOURCE,
                "eval_source": EVAL_SOURCE,
                "product_runtime": PRODUCT_RUNTIME,
                "vm_source": VM_SOURCE,
                "workbench_profile": PROFILE,
                "observation_policy": POLICY,
                "work_plan": PLAN,
            }.items()
        },
        "delivered_geometry": geometry,
        "runtime_path": path,
        "exact_compilation": compilation,
        "exact_host_replay": replay,
        "observation_policy": policy,
        "attribution": {
            "polling_policy": "proven-invalid-for-this-form",
            "observed_red_cause": "not-separated-crossing-consistent-and-product-red-capable",
            "host_replay": "red",
            "product_mechanism": "symbol-capture-plus-transient-helper-escape-across-rollback",
            "quiet_retry_on_unchanged_bytes": "forbidden",
            "next_authority": "owner-disposition-before-fix-or-recontact",
        },
        "execution_accounting": {
            "hardware_contacts": 0,
            "product_bytes_changed": 0,
            "media_bytes_changed": 0,
            "recontacts_authorized": 0,
        },
        "claim_limit": (
            "The delivered trace form is a transient C2D/C2J operation and the "
            "D3 poll choreography was invalid. The exact delivered compiler "
            "also installs a closure backed by rolled-back transient code and "
            "records a symbol instead of the prior function-cell BCODE. This "
            "does not prove which mechanism produced the observed red frame; "
            "it forbids a harness-only closure and any unchanged-byte retry."
        ),
    }
    validate_result(result)
    return result


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    mutations = {
        "classify-trace-nonpersistent": lambda x: x["attribution"].update(
            polling_policy="allowed"
        ),
        "close-red-as-harness-only": lambda x: x["attribution"].update(
            observed_red_cause="monitor-crossing"
        ),
        "abstract-away-symbol-capture": lambda x: x["exact_host_replay"]["untrace"].update(
            matches_pre_trace_BCODE=True
        ),
        "keep-transient-helper-after-rollback": lambda x: x["exact_host_replay"]["after_rollback"].update(
            helper_live=True
        ),
        "replace-dirmiss-with-success": lambda x: x["exact_host_replay"]["first_traced_call"].update(
            target_status="VM_OK"
        ),
        "authorize-unchanged-product-retry": lambda x: x["attribution"].update(
            quiet_retry_on_unchanged_bytes="authorized"
        ),
        "omit-post-install-callability": lambda x: x["exact_host_replay"].pop(
            "first_traced_call"
        ),
        "broaden-product-or-device-scope": lambda x: x["execution_accounting"].update(
            hardware_contacts=1
        ),
    }
    rejected = []
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate_result(candidate)
        except (AttributionError, KeyError):
            rejected.append(name)
        else:
            raise AttributionError(f"trace attribution mutation survived: {name}")
    policy = load(POLICY)
    policy_mutations = {
        "policy-default-nonpersistent": lambda x: x["default"].update(
            classification="nonpersistent"
        ),
        "policy-polling-default-allowed": lambda x: x["default"].update(
            monitor_or_screenshot_polling="allowed"
        ),
        "policy-trace-recontact-authorized": lambda x: x["active_trace_disposition"].update(
            recontact_authorized=True
        ),
        "policy-repeat-has-intermediate-read": lambda x: x["active_trace_disposition"]["future_repeat_contract"].update(
            observations_during_sequence=1
        ),
    }
    for name, mutate in policy_mutations.items():
        candidate = deepcopy(policy)
        mutate(candidate)
        try:
            validate_policy(candidate)
        except AttributionError:
            rejected.append(name)
        else:
            raise AttributionError(f"trace policy mutation survived: {name}")
    require(len(rejected) == len(mutations) + len(policy_mutations),
            "trace mutation accounting drift")
    return rejected


def archive_check() -> dict[str, Any]:
    """Validate the accepted historical receipt after trace leaves delivery.

    The old inspect/media paths are intentionally rebuilt without trace.  The
    attribution remains authority as a sealed decoded execution receipt; it
    must not start treating the new media as if they were the red candidate.
    """
    recorded = load(RECEIPT)
    validate_result(recorded)
    rejected = rejected_mutations(recorded)
    require(recorded.get("mutations_rejected") == rejected
            and recorded.get("mutation_count") == len(rejected),
            "archived trace attribution mutation closure drift")
    current_bindings = recorded.get("bindings", {})
    for key, path in {
        "trace_source": TRACE_SOURCE,
        "eval_runtime": EVAL_RUNTIME,
        "compiler_source": COMPILER_SOURCE,
        "eval_source": EVAL_SOURCE,
        "product_runtime": PRODUCT_RUNTIME,
        "vm_source": VM_SOURCE,
        "workbench_profile": PROFILE,
        "observation_policy": POLICY,
    }.items():
        require(current_bindings.get(key) == bind(path),
                f"archived trace attribution source binding drift: {key}")
    return recorded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("selftest", "check", "record", "archive-check"))
    args = parser.parse_args()
    try:
        if args.action == "archive-check":
            value = archive_check()
            print("c2-v112-trace-red-attribution: PASS archived-host-red "
                  f"mutations={value['mutation_count']}")
            return 0
        value = derive()
        rejected = rejected_mutations(value)
        if args.action == "selftest":
            print(f"c2-v112-trace-red-attribution: PASS mutations={len(rejected)}")
            return 0
        if args.action == "record":
            value["mutations_rejected"] = rejected
            value["mutation_count"] = len(rejected)
            write_json(RECEIPT, value)
            print(f"c2-v112-trace-red-attribution: WROTE {RECEIPT.relative_to(ROOT)}")
            return 0
        recorded = load(RECEIPT)
        value["mutations_rejected"] = rejected
        value["mutation_count"] = len(rejected)
        require(recorded == value, "trace attribution receipt is stale")
        print("c2-v112-trace-red-attribution: PASS host-red "
              "transient-helper-escape")
        return 0
    except (AttributionError, B.VMError, ValueError, OSError) as error:
        print(f"c2-v112-trace-red-attribution: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
