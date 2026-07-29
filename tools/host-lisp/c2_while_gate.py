#!/usr/bin/env python3
"""Permanent four-view proof gate for the accepted C2.2 `while` form."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402


CONTRACT = ROOT / "config/c2-while-contract.json"
COMPILER_C = ROOT / "src/compile.c"
EVAL_C = ROOT / "src/eval.c"
PY_COMPILER = ROOT / "tools/host-lisp/bytecode_p0_compiler.py"
LCC = ROOT / "lib/lcc.lisp"
LCC_PROFILE = ROOT / "lib/dialect-v2/lcc-profile.lisp"
SURFACE = ROOT / "config/dialect-v2-surface.json"
MIGRATION = ROOT / "config/dialect-migration-contract.json"
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
TIER_TOOL = ROOT / "tools/host-lisp/c2_product_compiler_tier.py"
GC_FIXTURE = ROOT / "tests/equivalence/while-gc-forms.lisp"
EQUIVALENCE = ROOT / "build/equivalence/equivalence-check"
BUILD = ROOT / "build/post-promotion/phase-v/while/gate"
TIER_SUITE = BUILD / "compiler-tier/suite.json"
TIER_RECEIPT = BUILD / "compiler-tier/tier-generation.json"
CARRIER_PREFIX = BUILD / "carrier/lcc"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v2-while-four-view-receipt.json"
)
FORMAT = "lisp65-c2.2-v2-while-four-view-receipt-v1"
PROFILE = "dialect-v2"
VM_CODEBUF = 128


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def source_bundle() -> dict[str, Any]:
    return {
        "contract": load(CONTRACT),
        "compiler_c": COMPILER_C.read_text(encoding="utf-8"),
        "eval_c": EVAL_C.read_text(encoding="utf-8"),
        "python": PY_COMPILER.read_text(encoding="utf-8"),
        "lcc": LCC.read_text(encoding="utf-8"),
        "profile": LCC_PROFILE.read_text(encoding="utf-8"),
        "surface": load(SURFACE),
        "migration": load(MIGRATION),
        "tier": TIER_TOOL.read_text(encoding="utf-8"),
    }


def validate_sources(bundle: dict[str, Any]) -> dict[str, Any]:
    contract = bundle["contract"]
    require(
        contract.get("format") == "lisp65-c2-while-product-contract-v1"
        and contract.get("status")
        == "owner-authorized-successor-product-link"
        and contract["scope"]["wplto_probes_authorized"] == 1
        and contract["scope"]["wplto_probes_consumed"] == 1
        and contract["scope"]["product_links_authorized"] == 1,
        "while owner envelope drift",
    )
    lowering = contract["lowering"]
    require(
        lowering["new_vm_opcodes"] == 0
        and lowering["new_runtime_state"] == 0
        and lowering["new_resident_gc_roots"] == 0
        and lowering["new_c2j_fields"] == 0
        and lowering["new_runtime_overlay_records"] == 0
        and lowering["relative_branch_domain"]["minimum"] == -128
        and lowering["relative_branch_domain"]["maximum"] == 127,
        "while lowering/capability contract drift",
    )

    compiler = bundle["compiler_c"]
    require(
        "static uint8_t is_proper_list(obj l)" in compiler
        and "static void compile_while(obj args)" in compiler
        and "if (!is_cons(args) || !is_proper_list(args))" in compiler
        and "compile_loop_body(body);" in compiler
        and "back_op = emit_branch(OP_JMPREL); patch_to(back_op, loop_start);"
        in compiler
        and '"dolist","while"' in compiler
        and 'else if (op_is(op, "while"))    compile_while(args);' in compiler,
        "native C compiler while seam drift",
    )
    evaluator = bundle["eval_c"]
    require(
        "sf_dotimes, sf_dolist, sf_while;" in evaluator
        and "if (op == sf_while)" in evaluator
        and (
            "loop_body(body, env);\n"
            "                        if (((uint8_t)++pollc & 0x3F) == 0) "
            "lisp_poll();"
        ) in evaluator
        and "sf_while = intern(BOOTNAME(while));" in evaluator,
        "native evaluator while seam drift",
    )
    python = bundle["python"]
    require(
        'elif op == "while":' in python
        and "self.compile_while(args, tail=tail)" in python
        and 'raise CompileError("while needs a test")' in python
        and 'context="while"' in python
        and (
            "def compile_loop_body(self, body):\n"
            "        for form in body:\n"
            "            self.compile_expr(form)\n"
            '            self.emit("DROP")'
        ) in python,
        "host compiler while seam drift",
    )
    lcc = bundle["lcc"]
    require(
        "(defun %lcc-rel8 (d)" in lcc
        and "(if (< d -128)" in lcc
        and "(if (> d 127)" in lcc
        and "(defun %lcc-while (cs lvls args)" in lcc
        and "((eq op 'while) t)" in lcc
        and "(%lcc-proper-list-p args)" in lcc
        and "(%lcc-emit-op cs3 'jmprel)" in lcc
        and "(%lcc-error-invalid-parameter-list)" in lcc,
        "device LCC while/rel8 seam drift",
    )
    require(
        "((eq op 'while) t)" in bundle["profile"],
        "dialect-v2 LCC profile does not classify while",
    )
    surface_rows = {
        (row.get("name"), row.get("kind"), row.get("visibility"))
        for row in bundle["surface"].get("definitions", [])
        if isinstance(row, dict)
    }
    require(
        ("while", "macro", "public") in surface_rows,
        "public while surface row absent",
    )
    syntax = bundle["migration"]["syntax"]
    require(
        "while" in syntax["special_forms_current"]
        and "while" in syntax["special_forms_target"]
        and "while" in syntax["retained_macros"],
        "migration inventory lacks while",
    )
    require(
        "BOUND_CARRIER_WHILE_FORM" in bundle["tier"]
        and "bound-carrier-while-lowering-executes" in bundle["tier"]
        and "_bound_carrier_while_probe()" in bundle["tier"],
        "generated compiler-tier has no executable while case",
    )
    return {
        "status": "passed-one-surface-five-implementation-views",
        "new_opcodes": 0,
        "new_runtime_state_bytes": 0,
        "new_roots": 0,
        "new_C2J_fields": 0,
        "new_overlay_records": 0,
        "treewalk_poll_cadence_admitted_iterations": 64,
    }


def source_mutations(bundle: dict[str, Any]) -> dict[str, str]:
    mutants: list[tuple[str, str, str, str]] = [
        ("c-compiler-dispatch", "compiler_c",
         'else if (op_is(op, "while"))    compile_while(args);',
         'else if (op_is(op, "while-x"))  compile_while(args);'),
        ("c-compiler-proper-list", "compiler_c",
         "if (!is_cons(args) || !is_proper_list(args))",
         "if (!is_cons(args))"),
        ("treewalk-dispatch", "eval_c", "if (op == sf_while)",
         "if (op == NIL)"),
        ("treewalk-poll", "eval_c",
         "loop_body(body, env);\n"
         "                        if (((uint8_t)++pollc & 0x3F) == 0) lisp_poll();",
         "loop_body(body, env);\n"
         "                        if (((uint8_t)++pollc & 0x3F) == 0) (void)0;"),
        ("host-compiler-dispatch", "python", 'elif op == "while":',
         'elif op == "while-x":'),
        ("host-body-drop", "python",
         "def compile_loop_body(self, body):\n"
         "        for form in body:\n"
         "            self.compile_expr(form)\n"
         '            self.emit("DROP")',
         "def compile_loop_body(self, body):\n"
         "        for form in body:\n"
         "            self.compile_expr(form)\n"
         '            self.emit("PUSHNIL")'),
        ("lcc-dispatch", "lcc", "((eq op 'while) t)",
         "((eq op 'while-x) t)"),
        ("lcc-negative-bound", "lcc", "(if (< d -128)",
         "(if (< d -127)"),
        ("lcc-positive-bound", "lcc", "(if (> d 127)",
         "(if (> d 126)"),
        ("lcc-profile", "profile", "((eq op 'while) t)",
         "((eq op 'while-x) t)"),
        ("carrier-execution-case", "tier",
         "bound-carrier-while-lowering-executes",
         "bound-carrier-while-name-only"),
    ]
    rejected: dict[str, str] = {}
    for label, key, old, new in mutants:
        require(old in bundle[key], f"mutation anchor absent: {label}")
        candidate = copy.deepcopy(bundle)
        candidate[key] = candidate[key].replace(old, new, 1)
        try:
            validate_sources(candidate)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"while source mutation survived: {label}")

    for label, field in (
        ("surface-row", "surface"),
        ("migration-current", "migration"),
        ("migration-target", "migration"),
    ):
        candidate = copy.deepcopy(bundle)
        if field == "surface":
            candidate[field]["definitions"] = [
                row for row in candidate[field]["definitions"]
                if row.get("name") != "while"
            ]
        elif label.endswith("current"):
            candidate[field]["syntax"]["special_forms_current"].remove("while")
        else:
            candidate[field]["syntax"]["special_forms_target"].remove("while")
        try:
            validate_sources(candidate)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"while inventory mutation survived: {label}")
    return rejected


def compile_one(source: str, *, trace: Any = None) -> tuple[B.Heap, B.CodeObject, B.P0VM, int]:
    ledger = load(LEDGER)
    heap = C.prepare_heap([])
    names, codes = C.compile_program(
        source, heap, strict_arity=True, abi_profile=PROFILE,
        abi_ledger=ledger,
    )
    require(len(names) == 1, "while host probe must emit one function")
    code = codes[names[0]]
    vm = B.P0VM(
        heap=heap, trace=trace, max_steps=200000,
        abi_profile=PROFILE, abi_ledger=ledger,
    )
    result = vm.run(code, ())
    return heap, code, vm, result


def payload_branches(code: B.CodeObject) -> list[dict[str, int | str]]:
    ledger = load(LEDGER)
    rows = []
    pc = 0
    while pc < len(code.payload):
        op_pc = pc
        spec, operand, pc = B.decode_instruction(
            code.payload, pc, profile_id=PROFILE, abi_ledger=ledger)
        if spec.mnemonic in {"JMPREL", "JFALSEREL"}:
            delta = B.s8(operand)
            rows.append({
                "pc": op_pc,
                "mnemonic": spec.mnemonic,
                "delta": delta,
                "target": pc + delta,
            })
    return rows


def integer_forms(count: int) -> list[str]:
    return ["1"] * count


def negative_boundary_source(cons_forms: int) -> str:
    body = integer_forms(36)
    for index in range(cons_forms):
        body[index] = "(cons nil nil)"
    body.append("(setq i (+ i 1))")
    return (
        "(defun while-neg-boundary () "
        "(let ((i 0)) (progn "
        f"(while (< i 1) {' '.join(body)}) i)))"
    )


def positive_boundary_source(overflow: bool) -> str:
    # Defun-tail IF emits two terminal arms without an intervening JMP.  With
    # 43 three-byte statements, replacing two by two-byte NIL statements gives
    # +127; replacing only one gives the exact one-byte overflow +128.
    body = integer_forms(43)
    body[0] = "nil"
    if not overflow:
        body[1] = "nil"
    return (
        "(defun while-pos-boundary () "
        f"(if t (progn {' '.join(body)}) 2))"
    )


class Trace:
    def __init__(self) -> None:
        self.events: list[tuple[int, str, Any]] = []
        self.max_native_stack = 0

    def instruction(
        self, _name: str, _code: B.CodeObject, pc: int,
        spec: B.OpSpec, operand: Any,
    ) -> None:
        self.events.append((pc, spec.mnemonic, operand))

    def native_stack(self, _name: str, *, used: int) -> None:
        self.max_native_stack = max(self.max_native_stack, used)


def streamed_window_cost(code: B.CodeObject, events: list[tuple[int, str, Any]]) -> dict[str, Any]:
    header = 7 + 2 * len(code.littab)
    pwin_max = VM_CODEBUF - header
    require(len(code.payload) > pwin_max, "stream probe unexpectedly fits one window")
    win = 0
    winlen = min(len(code.payload), pwin_max)
    streaming = winlen < len(code.payload)
    refills = {"sequential": 0, "backedge": 0, "forward_branch": 0}
    backedge_crossings = 0
    pending = "sequential"
    ledger = load(LEDGER)
    for index, (pc, mnemonic, operand) in enumerate(events):
        need = min(len(code.payload), pc + 3)
        if streaming and (pc < win or win + winlen < need):
            refills[pending] += 1
            win = pc
            winlen = min(len(code.payload) - pc, pwin_max)
        pending = "sequential"
        if index + 1 >= len(events) or mnemonic not in {"JMPREL", "JFALSEREL"}:
            continue
        _spec, _operand, next_pc = B.decode_instruction(
            code.payload, pc, profile_id=PROFILE, abi_ledger=ledger)
        actual_next = events[index + 1][0]
        taken = mnemonic == "JMPREL" or actual_next != next_pc
        if not taken:
            continue
        target = actual_next
        if not (target >= win and target - win < winlen):
            is_back = target < pc
            pending = "backedge" if is_back else "forward_branch"
            if is_back:
                backedge_crossings += 1
            win = target
            winlen = 0
            streaming = True
    return {
        "VM_CODEBUF_bytes": VM_CODEBUF,
        "header_bytes": header,
        "payload_window_bytes": pwin_max,
        "payload_bytes": len(code.payload),
        "logical_VM_steps": len(events),
        "payload_refills_total": sum(refills.values()),
        "refills": refills,
        "cross_window_backedges": backedge_crossings,
        "admitted_iterations": backedge_crossings,
        "backedge_target_refills_per_admitted_iteration": (
            refills["backedge"] / backedge_crossings
            if backedge_crossings else None
        ),
    }


def host_compiler_vm_proof() -> dict[str, Any]:
    # Exact negative meet belongs to an actual while.  Replacing one 3-byte
    # statement by a 4-byte CONS statement makes the backward delta -128.
    heap, exact_negative, vm, result = compile_one(
        negative_boundary_source(cons_forms=1))
    branches = payload_branches(exact_negative)
    require(
        any(row["mnemonic"] == "JMPREL" and row["delta"] == -128
            for row in branches)
        and heap.obj_to_text(result) == "1",
        "actual while did not accept/execute the -128 exact meet",
    )
    try:
        compile_one(negative_boundary_source(cons_forms=2))
    except C.CompileError as error:
        require("-129" in str(error), "negative overflow did not report -129")
        negative_overflow = str(error)
    else:
        raise GateError("actual while accepted the -129 rel8 overflow")

    # A legal while cannot simultaneously have +127 forward and a legal
    # backward edge: |back| = forward + test + branch width.  The shared rel8
    # patcher therefore proves its positive exact meet through IF.
    heap, exact_positive, _vm, result = compile_one(
        positive_boundary_source(False))
    branches = payload_branches(exact_positive)
    require(
        any(row["mnemonic"] == "JFALSEREL" and row["delta"] == 127
            for row in branches)
        and heap.obj_to_text(result) == "1",
        "shared rel8 patcher did not accept/execute the +127 exact meet",
    )
    try:
        compile_one(positive_boundary_source(True))
    except C.CompileError as error:
        require("128" in str(error), "positive overflow did not report +128")
        positive_overflow = str(error)
    else:
        raise GateError("shared rel8 patcher accepted the +128 overflow")

    stack_source = (
        "(defun while-stack (n) "
        "(let ((i 0)) (progn "
        "(while (< i n) (setq i (+ i 1))) i)))"
    )
    ledger = load(LEDGER)
    heap = C.prepare_heap([])
    names, codes = C.compile_program(
        stack_source, heap, strict_arity=True, abi_profile=PROFILE,
        abi_ledger=ledger)
    code = codes[names[0]]
    stack_rows = []
    for iterations in (2, 200):
        trace = Trace()
        vm = B.P0VM(
            heap=heap, trace=trace, max_steps=10000,
            abi_profile=PROFILE, abi_ledger=ledger)
        got = vm.run(code, (B.mkfix(iterations),))
        require(B.fixval(got) == iterations, "constant-stack loop result drift")
        stack_rows.append({
            "iterations": iterations,
            "logical_VM_steps": vm.steps,
            "max_native_stack_slots": trace.max_native_stack,
        })
    require(
        stack_rows[0]["max_native_stack_slots"]
        == stack_rows[1]["max_native_stack_slots"],
        "while native VM stack grows with iteration count",
    )

    stream_body = " ".join(
        [*integer_forms(36), "(setq i (+ i 1))"])
    stream_source = (
        "(defun while-stream () "
        "(let ((i 0)) (progn "
        f"(while (< i 2) {stream_body}) i)))"
    )
    trace = Trace()
    heap, stream_code, stream_vm, result = compile_one(
        stream_source, trace=trace)
    require(heap.obj_to_text(result) == "2", "streamed while result drift")
    stream = streamed_window_cost(stream_code, trace.events)
    require(
        stream["cross_window_backedges"] == 2
        and stream["refills"]["backedge"] == 2
        and stream["backedge_target_refills_per_admitted_iteration"] == 1.0,
        "streamed while backedge did not reload exactly once per iteration",
    )

    for malformed in (
        "(defun malformed () (while))",
        "(defun malformed () (while nil . 1))",
    ):
        try:
            compile_one(malformed)
        except C.CompileError:
            pass
        else:
            raise GateError(f"host compiler accepted malformed while: {malformed}")

    return {
        "status": "passed-host-compiler-VM-rel8-stack-and-streaming",
        "rel8": {
            "negative_exact_while": -128,
            "negative_overflow_rejected": negative_overflow,
            "positive_exact_shared_patcher": 127,
            "positive_overflow_rejected": positive_overflow,
            "positive_exact_note": (
                "A valid while cannot reach forward +127 while retaining a "
                "legal backward edge; the same patcher is exercised by IF."
            ),
        },
        "constant_stack": stack_rows,
        "streamed_backedge": stream,
    }


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        "command red: " + " ".join(command) + "\n" + result.stdout,
    )
    return result.stdout


def native_equivalence_proof() -> dict[str, Any]:
    require(EQUIVALENCE.is_file(), "equivalence binary absent; run equivalence-check")
    env = dict(os.environ)
    env["LISP65_EQ_REQUIRE_GC"] = "1"
    outputs = {}
    for mode in ("tree", "vm"):
        outputs[mode] = run_command(
            [str(EQUIVALENCE), mode, str(GC_FIXTURE)], env=env)
    require(
        outputs["tree"] == outputs["vm"]
        and outputs["tree"].strip().endswith("=> 9999"),
        "allocation/GC while parity drift",
    )

    boundary_file = BUILD / "rel8-boundaries.lisp"
    boundary_file.parent.mkdir(parents=True, exist_ok=True)
    sources = [
        negative_boundary_source(1).replace(
            "while-neg-boundary", "while-neg-exact", 1),
        "(while-neg-exact)",
        negative_boundary_source(2).replace(
            "while-neg-boundary", "while-neg-overflow", 1),
        positive_boundary_source(False).replace(
            "while-pos-boundary", "while-pos-exact", 1),
        "(while-pos-exact)",
        positive_boundary_source(True).replace(
            "while-pos-boundary", "while-pos-overflow", 1),
    ]
    boundary_file.write_text("\n".join(sources) + "\n", encoding="utf-8")
    native = run_command([str(EQUIVALENCE), "vm", str(boundary_file)])
    results = [
        line.split("=>", 1)[1].strip()
        for line in native.splitlines() if "=>" in line
    ]
    require(
        results == [
            "while-neg-exact", "1", "!error",
            "while-pos-exact", "1", "!error",
        ],
        f"rel8 boundary outcome drift: {results}",
    )

    # The device LCC has a deliberately different tail-IF layout, so the same
    # large IF source does not produce the same positive displacement.  Bind
    # the actual WHILE negative edge through both compilers, then exercise the
    # LCC's shared signed patcher directly at all four positive/negative limits.
    lcc_while_file = BUILD / "lcc-while-rel8-boundaries.lisp"
    lcc_while_file.write_text("\n".join(sources[:3]) + "\n", encoding="utf-8")
    native_while = run_command(
        [str(EQUIVALENCE), "vm", str(lcc_while_file)])
    lcc_while = run_command([
        str(EQUIVALENCE), "lcc", str(lcc_while_file),
        "--preload", str(LCC),
    ])
    require(
        native_while == lcc_while,
        "native C compiler and device LCC actual-while rel8 drift",
    )
    lcc_rel8_file = BUILD / "lcc-rel8-function-boundaries.lisp"
    lcc_rel8_file.write_text(
        "(%lcc-rel8 127)\n"
        "(%lcc-rel8 128)\n"
        "(%lcc-rel8 -128)\n"
        "(%lcc-rel8 -129)\n",
        encoding="utf-8",
    )
    lcc_rel8 = run_command([
        str(EQUIVALENCE), "tree", str(lcc_rel8_file),
        "--preload", str(LCC),
    ])
    lcc_rel8_results = [
        line.split("=>", 1)[1].strip()
        for line in lcc_rel8.splitlines() if "=>" in line
    ]
    require(
        lcc_rel8_results == ["127", "!error", "128", "!error"],
        f"device LCC signed rel8 outcome drift: {lcc_rel8_results}",
    )
    completion = ROOT / "build/equivalence/equivalence-completion.json"
    require(completion.is_file(), "equivalence completion canary absent")
    return {
        "status": "passed-treewalk-native-compiler-device-LCC-parity",
        "allocation_GC": {
            "fixture": bind(GC_FIXTURE),
            "treewalk_and_VM_result": "9999",
            "both_engines_collected": True,
        },
        "rel8_native_LCC_outcomes": results,
        "device_LCC_rel8_function_outcomes": lcc_rel8_results,
        "completion_canary": bind(completion),
    }


def generate_carrier() -> tuple[dict[str, Any], dict[str, Any], bytes]:
    run_command([
        sys.executable, str(TIER_TOOL),
        "--out", str(TIER_SUITE.relative_to(ROOT)),
        "--receipt", str(TIER_RECEIPT.relative_to(ROOT)),
    ])
    run_command([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check", "--emit-artifacts",
        str(CARRIER_PREFIX.relative_to(ROOT)),
        "--artifact-role", "disk-lib", "--base-addr", "0x000000",
        str(TIER_SUITE.relative_to(ROOT)),
    ])
    manifest_path = CARRIER_PREFIX.with_suffix(".manifest.json")
    blob_path = CARRIER_PREFIX.with_suffix(".blob.bin")
    return load(TIER_SUITE), load(manifest_path), blob_path.read_bytes()


def bound_environment(
    suite: dict[str, Any], manifest: dict[str, Any], blob: bytes,
) -> tuple[B.Heap, dict[int, B.CodeObject], set[int], Any]:
    patch = {
        int(row["blob_offset"]): int(row["node"])
        for row in manifest["literal_patches"]
    }
    heap = C.prepare_heap([])
    directory: dict[int, B.CodeObject] = {}
    macro_symbols: set[int] = set()
    for entry in manifest["entries"]:
        symbol = heap.intern(entry["name"])
        directory[symbol] = STD._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patch)
        if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
            macro_symbols.add(symbol)
    resident_names, resident_codes, resident_flags = (
        STD._compile_resident_code(suite, heap))
    _functions, _forms, _macros, inliner = (
        STD._suite_functions_and_forms(suite))
    macro_symbols.update(STD._macro_symbol_objs(heap, resident_flags))
    STD._add_code_to_directory(
        heap, directory,
        [
            name for name in resident_names
            if name not in set(STD._as_list(suite.get("resident_overrides")))
        ],
        resident_codes, "resident suite",
    )
    return heap, directory, macro_symbols, inliner


def obj_list(heap: B.Heap, value: int) -> list[int]:
    out = []
    while heap.consp(value):
        out.append(heap.car(value))
        value = heap.cdr(value)
    require(value == B.NIL, "carrier returned an improper code-object list")
    return out


def carrier_proof() -> dict[str, Any]:
    suite, manifest, blob = generate_carrier()
    named = {
        row.get("name"): row for row in suite.get("cases", [])
        if isinstance(row, dict)
    }
    case = named.get("bound-carrier-while-lowering-executes")
    require(
        case is not None and case.get("expect") == "28",
        "executable bound-carrier while case absent",
    )
    STD._check_embed_manifest(
        CARRIER_PREFIX.with_suffix(".manifest.json"),
        suite, manifest, blob)

    heap, directory, macros, inliner = bound_environment(
        suite, manifest, blob)
    source = (
        "(defun %while-bound-probe () "
        "(let ((i 0)) "
        "(progn (while (< i 3) (setq i (+ i 1))) i)))"
    )
    expression = f"(%c2-compile-form (quote {source}))"
    expanded = STD._expand_case_expr(
        suite, inliner, C.parse_one(expression))
    name, caller, helpers = C.compile_top_form_with_helpers(
        ["defun", "__while_bound_exec", [], expanded],
        heap, strict_arity=True, abi_profile=PROFILE,
        prebuilt_primitives=True,
    )
    for helper_name, helper in helpers:
        directory[heap.intern(helper_name)] = helper
    directory[heap.intern(name)] = caller
    ledger = load(LEDGER)
    compiler_vm = B.P0VM(
        heap=heap, directory=directory, macro_symbols=macros,
        max_steps=100000, max_call_args=suite["max_call_args"],
        abi_profile=PROFILE, abi_ledger=ledger)
    generated = compiler_vm.run(caller, ())
    outer = obj_list(heap, generated)
    require(len(outer) == 1, "bound carrier emitted helper/object drift")
    fields = obj_list(heap, outer[0])
    require(len(fields) == 5, "bound carrier CodeObject shape drift")
    literal_values = obj_list(heap, fields[3]) if fields[3] != B.NIL else []
    payload_values = obj_list(heap, fields[4])
    require(all(B.is_fix(value) for value in payload_values),
            "bound carrier emitted non-byte payload")
    code = B.CodeObject(
        nargs=B.fixval(fields[0]),
        nlocals=B.fixval(fields[1]),
        flags=B.fixval(fields[2]),
        littab=tuple(literal_values),
        payload=bytes(B.fixval(value) for value in payload_values),
    )

    reference_heap = C.prepare_heap([])
    names, references = C.compile_program(
        source, reference_heap, strict_arity=True, abi_profile=PROFILE,
        abi_ledger=ledger)
    reference = references[names[0]]
    require(
        (code.nargs, code.nlocals, code.flags, code.payload)
        == (reference.nargs, reference.nlocals,
            reference.flags, reference.payload)
        and not code.littab and not reference.littab,
        "bound device carrier and host compiler emitted different while code",
    )
    target_vm = B.P0VM(
        heap=heap, max_steps=1000,
        abi_profile=PROFILE, abi_ledger=ledger)
    result = target_vm.run(code, ())
    require(
        B.is_fix(result) and B.fixval(result) == 3,
        "bound-carrier-generated while did not execute to 3 in target VM",
    )

    tier_receipt = load(TIER_RECEIPT)
    for row in tier_receipt["inputs"]:
        path = ROOT / row["path"]
        require(row["sha256"] == sha(path),
                f"stale generated carrier source: {row['path']}")
    return {
        "status":
            "passed-generated-and-packed-device-carrier-plus-target-VM",
        "carrier_compile_steps": compiler_vm.steps,
        "target_VM_steps": target_vm.steps,
        "result": 3,
        "payload_bytes": len(code.payload),
        "payload_sha256": hashlib.sha256(code.payload).hexdigest(),
        "byteidentical_to_host_compiler": True,
        "manifest": bind(CARRIER_PREFIX.with_suffix(".manifest.json")),
        "blob": bind(CARRIER_PREFIX.with_suffix(".blob.bin")),
        "tier_suite": bind(TIER_SUITE),
        "tier_generation": bind(TIER_RECEIPT),
    }


def authority() -> dict[str, Any]:
    return {
        "contract": bind(CONTRACT),
        "native_compiler": bind(COMPILER_C),
        "native_evaluator": bind(EVAL_C),
        "host_compiler": bind(PY_COMPILER),
        "device_LCC": bind(LCC),
        "device_LCC_profile": bind(LCC_PROFILE),
        "surface": bind(SURFACE),
        "migration": bind(MIGRATION),
        "ABI_ledger": bind(LEDGER),
        "carrier_generator": bind(TIER_TOOL),
        "gate": bind(Path(__file__)),
    }


def main() -> int:
    source_only = "--source-only" in sys.argv[1:]
    try:
        bundle = source_bundle()
        source = validate_sources(bundle)
        mutations = source_mutations(bundle)
        if source_only:
            print(
                "c2-while-gate: SOURCE PASS "
                f"mutations={len(mutations)} new-opcodes=0 resident-state=0"
            )
            return 0
        host = host_compiler_vm_proof()
        equivalence = native_equivalence_proof()
        carrier = carrier_proof()
        receipt = {
            "format": FORMAT,
            "recorded_on": "2026-07-29",
            "status":
                "passed-four-view-while-successor-link-authorized-not-run",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "source_contract": source,
            "mutations_rejected": mutations,
            "host_compiler_VM": host,
            "native_and_device_equivalence": equivalence,
            "bound_device_carrier": carrier,
            "authority": authority(),
            "next_gate": (
                "Exactly one owner-authorized successor product link carrying "
                "the accepted random/while WPLTO identity."
            ),
            "claim_limit": (
                "Host, native-host and packed-carrier execution plus a target "
                "window-refill model bound to src/vm.c. The authorized product "
                "link and all hardware timing/on-metal while claims remain "
                "unconsumed."
            ),
        }
        atomic_json(RECEIPT, receipt)
        stream = host["streamed_backedge"]
        print(
            "c2-while-gate: PASS "
            f"mutations={len(mutations)} carrier-result=3 "
            f"stream-steps={stream['logical_VM_steps']} "
            f"stream-refills={stream['payload_refills_total']} "
            f"backedge-refills={stream['refills']['backedge']} "
            "product-links=0 hardware=0"
        )
        return 0
    except (
        GateError, KeyError, OSError, ValueError, C.CompileError,
        B.VMError, STD.StdlibCheckError,
    ) as error:
        print(f"c2-while-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
