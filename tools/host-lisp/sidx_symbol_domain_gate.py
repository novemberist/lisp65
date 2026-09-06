#!/usr/bin/env python3
"""Exercise and mutation-test the eval-facing symbol-writer domain guard."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from evidence_era import era_bind


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/eval.c"
TREE_FORMS = ROOT / "tests/equivalence/symbol-writer-domain.lisp"
VM_FORMS = ROOT / "tests/equivalence/symbol-writer-vm-regression.lisp"
HOST = ROOT / "build/equivalence/dialect-v2-equivalence-check"
BUILD = ROOT / "build/2.6/sidx-symbol-domain-gate"
MUTANT_SOURCE = BUILD / "eval-without-setq-symbol-guard.c"
MUTANT_HOST = BUILD / "dialect-v2-equivalence-check-without-setq-guard"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "block-2.6-card1-sidx-symbol-domain-gate.json"
)
FORMAT = "lisp65-block-2.6-sidx-symbol-domain-gate-v1"
EVIDENCE_ERA = "cdecb627a3acee8329b8d462492fe0f0b5c8be3e"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(command: list[str], label: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check:
        require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result


def definition(text: str, name: str) -> str:
    match = re.search(rf"(?:static\s+)?[^;\n]+\b{re.escape(name)}\s*\([^;]*?\)\s*\{{", text)
    require(match is not None, f"function absent: {name}")
    start = match.start(); brace = text.find("{", match.start())
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{": depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated function: {name}")


def source_model(text: str) -> dict[str, Any]:
    helper = definition(text, "eval_symbol_arg_p")
    require("if (is_sym(value)) return 1;" in helper
            and 'lisp_abort_static(LISP65_ERR_VM_TYPE, "vm: type error");' in helper
            and "return 0;" in helper,
            "shared eval symbol-domain predicate is not fail-closed")
    ordered = {
        "set-symbol-function": (
            "if (!eval_symbol_arg_p(symbol)) return NIL;",
            "set_sym_function(symbol, cadr(args));"),
        "%set-macro-list-ABI": (
            "if (!eval_symbol_arg_p(nm)) return NIL;", "m = alloc(T_MACRO);"),
        "%set-macro-array-ABI": (
            "if (!eval_symbol_arg_p(args[0])) {", "macro = alloc(T_MACRO);"),
        "sf_setq": (
            "if (!eval_symbol_arg_p(s)) { gc_rootsp = base; return NIL; }",
            "v = eval_env(cadr(args), env);"),
    }
    positions = {}
    for name, (guard, effect) in ordered.items():
        guard_at, effect_at = text.find(guard), text.find(effect)
        require(guard_at >= 0 and effect_at >= 0 and guard_at < effect_at,
                f"{name} guard is absent or follows its first effect")
        positions[name] = {"guard_offset": guard_at, "effect_offset": effect_at}
    require(text.count("eval_symbol_arg_p(") == 5,
            "eval symbol-domain call-site population is not helper plus four ABI sites")
    return {"status": "PASS: THREE LOGICAL EVAL WRITERS GUARDED BEFORE EFFECTS",
        "logical_edges": ["sf_setq", "set-symbol-function", "%set-macro"],
        "physical_ABI_sites": positions,
        "error": {"code": "LISP65_ERR_VM_TYPE", "text": "vm: type error"},
        "internal_symbol_writers_rechecked": False,
        "rule": "validate at the untrusted eval boundary before sidx, evaluation, allocation or write"}


def compile_mutant(text: str) -> None:
    needle = "if (!eval_symbol_arg_p(s)) { gc_rootsp = base; return NIL; }"
    require(text.count(needle) == 1, "SETQ mutation target drift")
    BUILD.mkdir(parents=True, exist_ok=True)
    MUTANT_SOURCE.write_text(text.replace(needle,
        "/* mutation: symbol-domain guard removed */", 1), encoding="utf-8")
    definitions = [
        "LISP65_COMPILE_REPL", "LISP65_VM", "LISP65_VM_GLOBAL_PRIMS",
        "LISP65_EVAL_PRIMS", "LISP65_EVAL_CONTROL_SF", "LISP65_VM_APPLY_OPFN",
        "LISP65_MACROEXPAND_PRIM", "LISP65_LCC_INSTALL", "LISP65_DIALECT_V2",
        "LISP65_STRING_ARENA", "LISP65_V2_NATIVE_CAPABILITIES",
        "LISP65_V2_NATIVE_STRING_CODECS", "LISP65_DIALECT_FAMILY_HARNESS",
        "LISP65_NUMERIC_ERRORS", "HEAP_CELLS=8192", "GC_ROOTS=1024",
        "MAX_SYM=512", "NAMEPOOL=8192", "VM_DIR_MAX=128", "IO_BUF_MAX=16",
    ]
    sources = [
        ROOT / "scripts/equivalence-main.c", MUTANT_SOURCE, ROOT / "src/compile.c",
        ROOT / "src/compile_repl.c", ROOT / "src/lcc_install_overlay.c",
        ROOT / "src/vm.c", ROOT / "src/mem.c", ROOT / "src/symbol.c",
        ROOT / "src/reader.c", ROOT / "src/printer.c", ROOT / "src/io.c",
        ROOT / "src/interrupt.c", ROOT / "src/screen.c",
    ]
    command = ["cc", "-std=c99", "-Wall", "-Wno-unused-function",
               *[f"-D{item}" for item in definitions], "-Isrc",
               *[str(path) for path in sources], "-o", str(MUTANT_HOST)]
    run(command, "SETQ guard-removal mutant compile")


def execute(binary: Path, lane: str, forms: Path, *, check: bool = True) -> dict[str, Any]:
    result = run([str(binary), lane, str(forms)], f"{lane} execution", check=check)
    return {"returncode": result.returncode, "stdout": result.stdout,
            "command": [binary.relative_to(ROOT).as_posix(), lane,
                        forms.relative_to(ROOT).as_posix()]}


def validate(value: dict[str, Any]) -> None:
    execution = value["execution"]
    require(value["format"] == FORMAT
            and value["source_model"]["logical_edges"] == [
                "sf_setq", "set-symbol-function", "%set-macro"]
            and execution["tree_guarded"]["returncode"] == 0
            and execution["tree_guarded"]["stdout"].count("!error:runtime") == 3
            and execution["tree_guarded"]["stdout"].startswith("(setq x 7) => 7\n")
            and execution["vm_guarded"]["returncode"] == 0
            and execution["vm_guarded"]["stdout"] == execution["vm_predecessor"]["stdout"]
            and execution["vm_guarded"]["stdout"].count("!error:runtime") == 2
            and execution["setq_guard_removed"]["rejected"] is True,
            "sidx symbol-domain receipt drift")


def build() -> None:
    require(not RECEIPT.exists(), "sidx domain gate is one-shot")
    text = SOURCE.read_text(encoding="utf-8")
    model = source_model(text)
    run(["make", str(HOST.relative_to(ROOT))], "guarded equivalence host build")
    guarded_tree = execute(HOST, "tree", TREE_FORMS)
    guarded_vm = execute(HOST, "vm", VM_FORMS)
    compile_mutant(text)
    mutant_tree = execute(MUTANT_HOST, "tree", TREE_FORMS, check=False)
    mutant_vm = execute(MUTANT_HOST, "vm", VM_FORMS)
    rejected = (mutant_tree["returncode"] != guarded_tree["returncode"]
                or mutant_tree["stdout"] != guarded_tree["stdout"])
    require(rejected and "(setq 5 x) => !error:runtime" not in mutant_tree["stdout"],
            "executed SETQ guard-removal mutation survived")
    value = {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": "PASS: SIDX EVAL WRITER DOMAIN CLOSED",
        "source": bind(SOURCE), "tree_fixture": bind(TREE_FORMS),
        "vm_fixture": bind(VM_FORMS), "source_model": model,
        "execution": {"tree_guarded": guarded_tree, "vm_guarded": guarded_vm,
            "vm_predecessor": mutant_vm,
            "setq_guard_removed": {**mutant_tree, "rejected": rejected,
                "mutation": "remove sf_setq eval_symbol_arg_p check"}},
        "claim": ("The exact form (setq 5 x) executes after x is bound; the "
                  "guarded tree lane raises the existing type error, while the "
                  "guard-removal mutant is rejected. VM setter behavior is byte-source-"
                  "unchanged and execution-identical across the eval-only mutation.")}
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("sidx-symbol-domain BUILD PASS logical=3 physical=4 mutations=1")


def check() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    validate(value)
    current = source_model(SOURCE.read_text(encoding="utf-8"))
    require(value["source"] == era_bind(EVIDENCE_ERA, SOURCE)
            and value["tree_fixture"] == bind(TREE_FORMS)
            and value["vm_fixture"] == bind(VM_FORMS),
            "sidx domain gate input binding drift")
    require(current["logical_edges"] == value["source_model"]["logical_edges"]
            and current["error"] == value["source_model"]["error"],
            "sidx successor lost the guarded writer semantics")
    print("sidx-symbol-domain CHECK PASS logical=3 physical=4 mutations=1")


def selftest() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    cases = {
        "lost-logical-edge": lambda row: row["source_model"]["logical_edges"].pop(),
        "guard-removal-survives": lambda row: row["execution"]["setq_guard_removed"].update(
            {"rejected": False}),
        "vm-path-drifts": lambda row: row["execution"]["vm_predecessor"].update(
            {"stdout": "different"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try: validate(trial)
        except (GateError, KeyError, ValueError): rejected.append(name)
    require(rejected == list(cases), "sidx receipt mutation survived")
    print(f"sidx-symbol-domain SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, subprocess.CalledProcessError) as error:
        print(f"sidx-symbol-domain: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
