#!/usr/bin/env python3
"""Tiny source-to-P0 compiler for the first lisp65 bytecode golden vectors.

This is deliberately a narrow T1 starting slice, not the full stdlib compiler.
It accepts only the forms represented in tests/bytecode/ and emits the pinned
P0 code-object format from bytecode_p0.py.
"""

import argparse
from dataclasses import dataclass
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402
from v2_native_function_views_generated import ACTIVE_CALLPRIMS  # noqa: E402


class CompileError(Exception):
    pass


PRIVATE_INLINE_OP = object()


PRIM_CALLS = {
    "stringp": 0,
    "string->list": 1,
    "list->string": 2,
    "string-length": 3,
    "string-ref": 4,
    "symbolp": 5,
    "numberp": 6,
    "apply": 7,
    "funcall": 8,
    "screen-size": 9,
    "screen-clear": 10,
    "screen-put-char": 11,
    "screen-write-string": 12,
    "read-key": 13,
    "poll-key": 14,
    "%disk-read-sector": 15,
    "%disk-byte": 16,
    "%disk-load-file": 17,
    "%disk-load-lib": 18,
    "symbol-value": 19,
    "set-symbol-value": 20,
    "%disk-poke": 21,
    "%disk-write-sector": 22,
}

PRIM_CALLS_V2 = dict(ACTIVE_CALLPRIMS)


def _abi_profile(strict_arity, abi_profile):
    if abi_profile is None:
        return "dialect-v2" if strict_arity else "dialect-v1"
    if abi_profile not in ("dialect-v1", "dialect-v2"):
        raise CompileError("unknown ABI profile: %s" % abi_profile)
    if (abi_profile == "dialect-v2") != bool(strict_arity):
        raise CompileError("ABI profile and strict-arity mode disagree")
    return abi_profile


def _abi_ledger(abi_profile, abi_ledger):
    if abi_ledger is not None or abi_profile == "dialect-v1":
        return abi_ledger
    path = os.path.join(_repo_root(), "config", "bytecode-abi-ledger.json")
    with open(path, "r", encoding="utf-8") as source:
        return json.load(source)


@dataclass(frozen=True)
class StringLit:
    value: str


@dataclass(frozen=True)
class DottedList:
    items: tuple
    tail: object


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _default_paths():
    return sorted(glob.glob(os.path.join(_repo_root(), "tests", "bytecode", "*.json")))


def _default_program_paths():
    return sorted(glob.glob(os.path.join(_repo_root(), "tests", "bytecode", "programs", "*.json")))


def tokenize(src):
    out = []
    i = 0
    while i < len(src):
        c = src[i]
        if c.isspace():
            i += 1
        elif c == ";":
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c in "()`":
            out.append(c)
            i += 1
        elif c == "'":
            out.append(c)
            i += 1
        elif c == ",":
            if i + 1 < len(src) and src[i + 1] == "@":
                out.append(",@")
                i += 2
            else:
                out.append(c)
                i += 1
        elif c == '"':
            j = i + 1
            chars = []
            while j < len(src) and src[j] != '"':
                chars.append(src[j])
                j += 1
            if j >= len(src):
                raise CompileError("unterminated string literal")
            out.append(StringLit("".join(chars)))
            i = j + 1
        else:
            j = i
            while j < len(src) and not src[j].isspace() and src[j] not in "();":
                j += 1
            out.append(src[i:j])
            i = j
    return out


def parse_one(src):
    toks = tokenize(src)
    form, pos = read_form(toks, 0)
    if pos != len(toks):
        raise CompileError("trailing tokens: %r" % toks[pos:])
    return form


def parse_all(src):
    toks = tokenize(src)
    forms = []
    pos = 0
    while pos < len(toks):
        form, pos = read_form(toks, pos)
        forms.append(form)
    return forms


def read_form(toks, pos):
    if pos >= len(toks):
        raise CompileError("unexpected EOF")
    tok = toks[pos]
    pos += 1
    if isinstance(tok, StringLit):
        return tok, pos
    if tok == "'":
        form, pos = read_form(toks, pos)
        return ["quote", form], pos
    if tok == "`":
        form, pos = read_form(toks, pos)
        return ["quasiquote", form], pos
    if tok == ",":
        form, pos = read_form(toks, pos)
        return ["unquote", form], pos
    if tok == ",@":
        form, pos = read_form(toks, pos)
        return ["unquote-splicing", form], pos
    if tok == "(":
        items = []
        while pos < len(toks) and toks[pos] != ")":
            if toks[pos] == ".":
                if not items:
                    raise CompileError("dot needs a preceding list item")
                pos += 1
                tail, pos = read_form(toks, pos)
                if pos >= len(toks) or toks[pos] != ")":
                    raise CompileError("dotted list tail must be the final item")
                pos += 1
                return DottedList(tuple(items), tail), pos
            item, pos = read_form(toks, pos)
            items.append(item)
        if pos >= len(toks):
            raise CompileError("missing ')'")
        pos += 1
        return items, pos
    if tok == ")":
        raise CompileError("unexpected ')'")
    try:
        return int(tok, 10), pos
    except ValueError:
        return tok.lower(), pos


def load_vector_files(paths):
    loaded = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        loaded.append((path, data))
    return loaded


class FunctionCompiler:
    def __init__(
        self,
        heap,
        params,
        optional_count=0,
        optional_marker=False,
        rest_param=None,
        entry=None,
        defun_tail=False,
        helper_prefix=None,
        helper_counter=None,
        helpers=None,
        capture_candidates=None,
        strict_arity=False,
        abi_profile=None,
        abi_ledger=None,
    ):
        if len(params) > 255:
            raise CompileError("too many params")
        if optional_count < 0 or optional_count > 63:
            raise CompileError("too many &optional params")
        if optional_count > len(params):
            raise CompileError("&optional parameter count exceeds nargs")
        if (optional_marker or optional_count) and not strict_arity:
            raise CompileError("&optional requires dialect-v2 strict arity")
        self.heap = heap
        self.params = list(params)
        self.optional_count = optional_count
        self.rest_param = rest_param
        self.entry = entry
        self.defun_tail = defun_tail
        self.helper_prefix = helper_prefix or _helper_prefix(entry)
        self.helper_counter = helper_counter if helper_counter is not None else [0]
        self.helpers = helpers if helpers is not None else []
        self.capture_candidates = set(capture_candidates or [])
        self.strict_arity = strict_arity
        self.abi_profile = _abi_profile(strict_arity, abi_profile)
        self.abi_ledger = _abi_ledger(self.abi_profile, abi_ledger)
        self.prim_calls = PRIM_CALLS_V2 if self.abi_profile == "dialect-v2" else PRIM_CALLS
        self.payload = bytearray()
        self.last_mnemonic = None
        self.literals = []
        self.literal_keys = {}
        self.scopes = [{name: idx for idx, name in enumerate(self.params)}]
        self.next_slot = len(self.params)
        self.nlocals = 0
        if self.rest_param is not None:
            if self.rest_param in self.scopes[0]:
                raise CompileError("duplicate parameter: %s" % self.rest_param)
            self.scopes[0][self.rest_param] = self.next_slot
            self.next_slot += 1
            self.nlocals = 1
        self.gensym_counter = 0

    def code_object(self):
        return B.CodeObject(
            nargs=len(self.params),
            nlocals=self.nlocals,
            flags=(B.CO_FLAG_REST if self.rest_param is not None else 0)
            | (B.CO_FLAG_STRICT_ARITY if self.strict_arity else 0)
            | (self.optional_count << B.CO_FLAG_OPTIONAL_SHIFT),
            littab=tuple(self.literals),
            payload=bytes(self.payload),
        )

    def compile_body(self, body):
        self.compile_sequence(body, tail=self.defun_tail)
        self.emit_ret_unless_tailcall()
        return self.code_object()

    def emit(self, mnemonic, *operands):
        start = len(self.payload)
        self.payload += B.encode_instruction(
            mnemonic, *operands,
            profile_id=self.abi_profile, abi_ledger=self.abi_ledger,
        )
        self.last_mnemonic = mnemonic
        return start

    def emit_ret_unless_tailcall(self):
        if self.last_mnemonic != "TAILCALL":
            self.emit("RET")

    def patch_rel8(self, operand_index, target, context=None):
        rel = target - (operand_index + 1)
        if not -128 <= rel <= 127:
            detail = " in %s" % context if context else ""
            raise CompileError("branch offset out of rel8 range%s: %d" % (detail, rel))
        self.payload[operand_index] = rel & 0xFF

    def literal_symbol(self, name):
        key = ("symbol", name)
        if key in self.literal_keys:
            return self.literal_keys[key]
        idx = len(self.literals)
        self.literals.append(self.heap.intern(name))
        self.literal_keys[key] = idx
        return idx

    def literal_obj(self, key, obj):
        if key in self.literal_keys:
            return self.literal_keys[key]
        idx = len(self.literals)
        self.literals.append(obj)
        self.literal_keys[key] = idx
        return idx

    def make_string_obj(self, value):
        return self.heap.alloc(B.T_STR, self.heap.list_from_py([ord(ch) for ch in value]), B.NIL)

    def compile_expr(self, form, tail=False):
        if isinstance(form, int):
            if -128 <= form <= 127:
                self.emit("PUSHI8", form)
            else:
                self.emit("PUSHLIT", self.literal_obj(("int", form), B.mkfix(form)))
            return
        if isinstance(form, StringLit):
            self.compile_quote([form])
            return
        if isinstance(form, str):
            if form == "nil":
                self.emit("PUSHNIL")
            elif form == "t":
                self.emit("PUSHT")
            else:
                self.emit_arg(form)
            return
        if not isinstance(form, list) or not form:
            raise CompileError("bad form: %r" % (form,))

        op = form[0]
        args = form[1:]
        if isinstance(op, list) and op and op[0] == "lambda":
            self.compile_immediate_lambda(op, args, tail=tail)
        elif op == "if":
            self.compile_if(args, tail=tail)
        elif op == "progn":
            self.compile_sequence(args, tail=tail)
        elif op == "and":
            self.compile_expr(self.lower_and(args), tail=tail)
        elif op == "or":
            self.compile_expr(self.lower_or(args), tail=tail)
        elif op == "cond":
            self.compile_expr(self.lower_cond(args), tail=tail)
        elif op == "when":
            self.compile_expr(self.lower_when(args), tail=tail)
        elif op == "unless":
            self.compile_expr(self.lower_unless(args), tail=tail)
        elif op == "case":
            self.compile_expr(self.lower_case(args), tail=tail)
        elif op == "quote":
            self.compile_quote(args)
        elif op == "quasiquote":
            self.compile_expr(self.lower_quasiquote(args), tail=tail)
        elif op == "lambda":
            if len(form) < 3:
                raise CompileError("lambda needs params and body")
            name = self.compile_lambda_helper(form)
            self.emit("PUSHLIT", self.literal_symbol(name))
        elif op == "function":
            self.compile_function(args)
        elif op == "setq":
            self.compile_setq(args)
        elif op == "let":
            self.compile_let(args, tail=tail)
        elif op == "let*":
            self.compile_expr(self.lower_let_star(args), tail=tail)
        elif op is PRIVATE_INLINE_OP:
            self.compile_private_inline(args, tail=tail)
        elif op == "dotimes":
            self.compile_dotimes(args, tail=tail)
        elif op == "dolist":
            self.compile_dolist(args, tail=tail)
        elif op == "+":
            self.compile_binary(args, "ADD")
        elif op == "-":
            self.compile_binary(args, "SUB")
        elif op == "*":
            self.compile_binary(args, "MUL")
        elif op == "/":
            self.compile_binary(args, "DIV")
        elif op == "<":
            self.compile_binary(args, "LESS")
        elif op == ">":
            self.compile_binary(args, "GREATER")
        elif op == "<=":
            self.compile_compare_chain(args, ">")
        elif op == ">=":
            self.compile_compare_chain(args, "<")
        elif op == "remainder":
            self.compile_binary(args, "REMAINDER")
        elif op == "mod":
            self.compile_binary(args, "MOD")
        elif op in ("eq", "="):
            self.compile_binary(args, "EQ")
        elif op == "eql":
            self.compile_binary(args, "EQL")
        elif op in ("not", "null"):
            self.compile_unary(args, "NOT")
        elif op == "cons":
            self.compile_binary(args, "CONS")
        elif op == "car":
            self.compile_unary(args, "CAR")
        elif op == "cdr":
            self.compile_unary(args, "CDR")
        elif op == "consp":
            self.compile_unary(args, "CONSP")
        elif op in self.prim_calls:
            self.compile_callprim(args, self.prim_calls[op])
        else:
            self.compile_call(op, args, tail=tail)

    def emit_arg(self, name):
        idx = self.resolve_slot(name)
        if idx >= len(self.params):
            self.emit("LOADL", idx)
        elif idx == 0:
            self.emit("PUSHARG0")
        elif idx == 1:
            self.emit("PUSHARG1")
        elif idx == 2:
            self.emit("PUSHARG2")
        else:
            self.emit("PUSHARGN", idx)

    def resolve_slot(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if name in self.capture_candidates:
            raise CompileError("capturing closure is not supported in P0: %s" % name)
        raise CompileError("unbound variable: %s" % name)

    def alloc_local(self):
        slot = self.next_slot
        self.next_slot += 1
        self.nlocals = max(self.nlocals, self.next_slot - len(self.params))
        if self.next_slot > 256:
            raise CompileError("too many frame slots")
        return slot

    def compile_sequence(self, body, tail=False):
        if not body:
            self.emit("PUSHNIL")
            return
        for form in body[:-1]:
            self.compile_expr(form)
            self.emit("DROP")
        self.compile_expr(body[-1], tail=tail)

    def gensym(self, prefix):
        self.gensym_counter += 1
        return "__p0_%s_%d" % (prefix, self.gensym_counter)

    def helper_name(self):
        self.helper_counter[0] += 1
        return "__p0_lambda_%s_%d" % (self.helper_prefix, self.helper_counter[0])

    def lower_and(self, forms):
        if not forms:
            return "t"
        if len(forms) == 1:
            return forms[0]
        return ["if", forms[0], self.lower_and(forms[1:]), "nil"]

    def lower_or(self, forms):
        if not forms:
            return "nil"
        if len(forms) == 1:
            return forms[0]
        tmp = self.gensym("or")
        return ["let", [[tmp, forms[0]]], ["if", tmp, tmp, self.lower_or(forms[1:])]]

    def lower_compare_chain(self, args, negated_binary_op):
        tests = []
        for left, right in zip(args, args[1:]):
            tests.append(["not", [negated_binary_op, left, right]])
        return self.lower_and(tests)

    def lower_cond(self, clauses):
        if not clauses:
            return "nil"
        clause = clauses[0]
        if not isinstance(clause, list) or not clause:
            raise CompileError("bad cond clause: %r" % (clause,))
        test = clause[0]
        if test in ("t", "otherwise"):
            return ["progn"] + clause[1:] if len(clause) > 1 else test
        if len(clause) == 1:
            return ["or", test, self.lower_cond(clauses[1:])]
        return ["if", test, ["progn"] + clause[1:], self.lower_cond(clauses[1:])]

    def lower_when(self, args):
        if not args:
            raise CompileError("when needs a test")
        return ["if", args[0], ["progn"] + args[1:], "nil"]

    def lower_unless(self, args):
        if not args:
            raise CompileError("unless needs a test")
        return ["if", args[0], "nil", ["progn"] + args[1:]]

    def lower_let_star(self, args):
        if len(args) < 2:
            raise CompileError("let* needs bindings and body")
        bindings = args[0]
        if not isinstance(bindings, list):
            raise CompileError("let* bindings must be a list")
        if not bindings:
            return ["let", []] + args[1:]
        return ["let", [bindings[0]], self.lower_let_star([bindings[1:]] + args[1:])]

    def lower_case(self, args):
        if not args:
            raise CompileError("case needs keyform")
        key_tmp = self.gensym("case")
        return ["let", [[key_tmp, args[0]]], self.lower_case_clauses(key_tmp, args[1:])]

    def lower_case_clauses(self, key_tmp, clauses):
        if not clauses:
            return "nil"
        clause = clauses[0]
        if not isinstance(clause, list) or not clause:
            raise CompileError("bad case clause: %r" % (clause,))
        key_spec = clause[0]
        body = clause[1:] if len(clause) > 1 else ["nil"]
        if key_spec in ("t", "otherwise"):
            test = "t"
        else:
            test = self.lower_case_key_test(key_tmp, key_spec)
        return ["if", test, ["progn"] + body, self.lower_case_clauses(key_tmp, clauses[1:])]

    def lower_case_key_test(self, key_tmp, key_spec):
        if isinstance(key_spec, list):
            if not key_spec:
                return "nil"
            tests = [["eql", key_tmp, ["quote", key]] for key in key_spec]
            return self.lower_or(tests)
        return ["eql", key_tmp, ["quote", key_spec]]

    def compile_if(self, args, tail=False):
        if len(args) == 2:
            test, then_form = args
            else_form = "nil"
        elif len(args) == 3:
            test, then_form, else_form = args
        else:
            raise CompileError("if needs test, then, optional else")
        self.compile_expr(test)
        jf_op = self.emit("JFALSEREL", 0)
        jf_operand = jf_op + 1

        if tail:
            self.compile_expr(then_form, tail=True)
            self.emit_ret_unless_tailcall()
            self.patch_rel8(jf_operand, len(self.payload), context="if")
            self.compile_expr(else_form, tail=True)
        else:
            self.compile_expr(then_form)
            jmp_op = self.emit("JMPREL", 0)
            jmp_operand = jmp_op + 1
            self.patch_rel8(jf_operand, len(self.payload), context="if")
            self.compile_expr(else_form)
            self.patch_rel8(jmp_operand, len(self.payload), context="if")

    def compile_setq(self, args):
        if not args:
            self.emit("PUSHNIL")
            return
        if len(args) % 2 != 0:
            raise CompileError("setq needs variable/value pairs")
        pairs = list(zip(args[0::2], args[1::2]))
        for name, value in pairs:
            if not isinstance(name, str):
                raise CompileError("setq target must be a symbol: %r" % (name,))
            slot = self.resolve_slot(name)
            self.compile_expr(value)
            self.emit("STOREL", slot)
        self.emit("LOADL", self.resolve_slot(pairs[-1][0]))

    def compile_let(self, args, tail=False):
        if len(args) < 2:
            raise CompileError("let needs bindings and body")
        bindings = args[0]
        if not isinstance(bindings, list):
            raise CompileError("let bindings must be a list")
        local_scope = {}
        compiled_bindings = []
        for binding in bindings:
            if isinstance(binding, str):
                name = binding
                init = "nil"
            elif (
                isinstance(binding, list)
                and len(binding) == 2
                and isinstance(binding[0], str)
            ):
                name, init = binding
            else:
                raise CompileError("bad let binding: %r" % (binding,))
            if name in local_scope:
                raise CompileError("duplicate let binding: %s" % name)
            slot = self.alloc_local()
            local_scope[name] = slot
            compiled_bindings.append((slot, init))

        for slot, init in compiled_bindings:
            self.compile_expr(init)
            self.emit("STOREL", slot)

        self.scopes.append(local_scope)
        try:
            self.compile_sequence(args[1:], tail=tail)
        finally:
            self.scopes.pop()

    def parse_loop_spec(self, args, name):
        if not args:
            raise CompileError("%s needs a binding spec" % name)
        spec = args[0]
        if not isinstance(spec, list) or not (2 <= len(spec) <= 3):
            raise CompileError("bad %s binding spec: %r" % (name, spec))
        var = spec[0]
        if not isinstance(var, str):
            raise CompileError("%s variable must be a symbol: %r" % (name, var))
        return var, spec[1], spec[2] if len(spec) == 3 else "nil", args[1:]

    def compile_loop_body(self, body):
        for form in body:
            self.compile_expr(form)
            self.emit("DROP")

    def compile_dotimes(self, args, tail=False):
        var, count_form, result_form, body = self.parse_loop_spec(args, "dotimes")
        limit_slot = self.alloc_local()
        var_slot = self.alloc_local()

        self.compile_expr(count_form)
        self.emit("STOREL", limit_slot)
        self.emit("PUSHI8", 0)
        self.emit("STOREL", var_slot)

        loop_scope = {var: var_slot}
        self.scopes.append(loop_scope)
        try:
            loop_start = len(self.payload)
            self.emit("LOADL", var_slot)
            self.emit("LOADL", limit_slot)
            self.emit("LESS")
            exit_op = self.emit("JFALSEREL", 0)
            exit_operand = exit_op + 1

            self.compile_loop_body(body)
            self.emit("LOADL", var_slot)
            self.emit("PUSHI8", 1)
            self.emit("ADD")
            self.emit("STOREL", var_slot)
            back_op = self.emit("JMPREL", 0)
            self.patch_rel8(back_op + 1, loop_start, context="dotimes")

            self.patch_rel8(exit_operand, len(self.payload), context="dotimes")
            self.emit("LOADL", limit_slot)
            self.emit("STOREL", var_slot)
            self.compile_expr(result_form, tail=tail)
        finally:
            self.scopes.pop()

    def compile_dolist(self, args, tail=False):
        var, list_form, result_form, body = self.parse_loop_spec(args, "dolist")
        list_slot = self.alloc_local()
        var_slot = self.alloc_local()

        self.compile_expr(list_form)
        self.emit("STOREL", list_slot)

        loop_scope = {var: var_slot}
        self.scopes.append(loop_scope)
        try:
            loop_start = len(self.payload)
            self.emit("LOADL", list_slot)
            self.emit("CONSP")
            exit_op = self.emit("JFALSEREL", 0)
            exit_operand = exit_op + 1

            self.emit("LOADL", list_slot)
            self.emit("CAR")
            self.emit("STOREL", var_slot)
            self.compile_loop_body(body)
            self.emit("LOADL", list_slot)
            self.emit("CDR")
            self.emit("STOREL", list_slot)
            back_op = self.emit("JMPREL", 0)
            self.patch_rel8(back_op + 1, loop_start, context="dolist")

            self.patch_rel8(exit_operand, len(self.payload), context="dolist")
            self.emit("PUSHNIL")
            self.emit("STOREL", var_slot)
            self.compile_expr(result_form, tail=tail)
        finally:
            self.scopes.pop()

    def compile_immediate_lambda(self, lambda_form, args, tail=False):
        if len(lambda_form) < 3:
            raise CompileError("lambda needs params and body")
        params, optional_count, rest_param, optional_marker = _params(
            lambda_form[1], optional_syntax=self.strict_arity
        )
        if optional_marker and not self.strict_arity:
            raise CompileError("&optional requires dialect-v2 strict arity")
        if rest_param is not None:
            raise CompileError("immediate lambda &rest is not supported")
        required_count = len(params) - optional_count
        if len(args) < required_count or len(args) > len(params):
            raise CompileError("immediate lambda arity mismatch")
        padded_args = list(args) + ["nil"] * (len(params) - len(args))
        bindings = [[name, arg] for name, arg in zip(params, padded_args)]
        self.compile_let([bindings] + lambda_form[2:], tail=tail)

    def compile_private_inline(self, args, tail=False):
        if len(args) != 3:
            raise CompileError("private inline form needs params, body and args")
        params, body, call_args = args
        parsed_params, optional_count, rest_param, optional_marker = _params(
            params, optional_syntax=self.strict_arity
        )
        if rest_param is not None or optional_marker or optional_count:
            raise CompileError("private inline optional/rest parameters are not supported")
        if not isinstance(body, list) or not body:
            raise CompileError("private inline body must be non-empty")
        if not isinstance(call_args, list) or len(parsed_params) != len(call_args):
            raise CompileError("private inline arity mismatch")

        param_scope = {}
        slots = []
        for name in parsed_params:
            if name in param_scope:
                raise CompileError("duplicate private inline parameter: %s" % name)
            slot = self.alloc_local()
            param_scope[name] = slot
            slots.append(slot)

        # Arguments use the caller's lexical environment.  The body then sees
        # only the former top-level function parameters, so its global names
        # cannot accidentally capture caller locals.
        for slot, value in zip(slots, call_args):
            self.compile_expr(value)
            self.emit("STOREL", slot)

        caller_scopes = self.scopes
        self.scopes = [param_scope]
        try:
            self.compile_sequence(body, tail=tail)
        finally:
            self.scopes = caller_scopes

    def lower_quasiquote(self, args):
        if len(args) != 1:
            raise CompileError("quasiquote needs exactly 1 arg")
        return self.lower_quasiquote_form(args[0])

    def lower_quasiquote_form(self, form):
        if (
            isinstance(form, list)
            and len(form) == 2
            and form[0] == "unquote"
        ):
            return form[1]
        if (
            isinstance(form, list)
            and len(form) == 2
            and form[0] == "unquote-splicing"
        ):
            raise CompileError("unquote-splicing is only valid inside quasiquote lists")
        if isinstance(form, DottedList):
            return self.lower_quasiquote_dotted_list(form)
        if isinstance(form, list):
            return self.lower_quasiquote_list(form)
        return ["quote", form]

    def lower_quasiquote_list(self, items):
        out = ["quote", []]
        for item in reversed(items):
            if (
                isinstance(item, list)
                and len(item) == 2
                and item[0] == "unquote-splicing"
            ):
                out = ["append", item[1], out]
            else:
                out = ["cons", self.lower_quasiquote_form(item), out]
        return out

    def lower_quasiquote_dotted_list(self, form):
        out = self.lower_quasiquote_form(form.tail)
        for item in reversed(form.items):
            if (
                isinstance(item, list)
                and len(item) == 2
                and item[0] == "unquote-splicing"
            ):
                out = ["append", item[1], out]
            else:
                out = ["cons", self.lower_quasiquote_form(item), out]
        return out

    def compile_quote(self, args):
        if len(args) != 1:
            raise CompileError("quote needs exactly 1 arg")
        key, obj = self.quoted_obj(args[0])
        if obj == B.NIL:
            self.emit("PUSHNIL")
        elif obj == self.heap.t_obj:
            self.emit("PUSHT")
        elif B.is_fix(obj) and -128 <= B.fixval(obj) <= 127:
            self.emit("PUSHI8", B.fixval(obj))
        else:
            self.emit("PUSHLIT", self.literal_obj(key, obj))

    def quoted_obj(self, form):
        if form == []:
            return ("nil",), B.NIL
        if isinstance(form, int):
            return ("int", form), B.mkfix(form)
        if isinstance(form, StringLit):
            return ("string", form.value), self.make_string_obj(form.value)
        if isinstance(form, str):
            if form == "nil":
                return ("nil",), B.NIL
            if form == "t":
                return ("t",), self.heap.t_obj
            return ("symbol", form), self.heap.intern(form)
        if isinstance(form, list):
            items = [self.quoted_obj(item) for item in form]
            key = ("list", tuple(item_key for item_key, _ in items))
            if key in self.literal_keys:
                return key, self.literals[self.literal_keys[key]]
            obj = B.NIL
            for _, item_obj in reversed(items):
                obj = self.heap.cons(item_obj, obj)
            return key, obj
        if isinstance(form, DottedList):
            items = [self.quoted_obj(item) for item in form.items]
            tail_key, obj = self.quoted_obj(form.tail)
            key = ("dotted", tuple(item_key for item_key, _ in items), tail_key)
            if key in self.literal_keys:
                return key, self.literals[self.literal_keys[key]]
            for _, item_obj in reversed(items):
                obj = self.heap.cons(item_obj, obj)
            return key, obj
        raise CompileError("bad quoted form: %r" % (form,))

    def compile_function(self, args):
        if len(args) != 1:
            raise CompileError("function needs exactly 1 arg")
        target = args[0]
        if isinstance(target, str):
            self.emit("PUSHLIT", self.literal_symbol(target))
            return
        if (
            isinstance(target, list)
            and len(target) >= 3
            and target[0] == "lambda"
        ):
            name = self.compile_lambda_helper(target)
            self.emit("PUSHLIT", self.literal_symbol(name))
            return
        raise CompileError("function only supports named or noncapturing lambda functions in P0")

    def compile_lambda_helper(self, lambda_form):
        name = self.helper_name()
        params, optional_count, rest_param, optional_marker = _params(
            lambda_form[1], optional_syntax=self.strict_arity
        )
        capture_candidates = set(self.capture_candidates)
        for scope in self.scopes:
            capture_candidates.update(scope)
        fc = FunctionCompiler(
            self.heap,
            params,
            optional_count=optional_count,
            optional_marker=optional_marker,
            rest_param=rest_param,
            entry=name,
            defun_tail=True,
            helper_prefix=self.helper_prefix,
            helper_counter=self.helper_counter,
            helpers=self.helpers,
            capture_candidates=capture_candidates,
            strict_arity=self.strict_arity,
            abi_profile=self.abi_profile,
            abi_ledger=self.abi_ledger,
        )
        code = fc.compile_body(lambda_form[2:])
        self.helpers.append((name, code))
        return name

    def compile_compare_chain(self, args, negated_binary_op):
        if len(args) <= 1:
            self.emit("PUSHT")
            return
        if len(args) == 2:
            self.compile_expr(["not", [negated_binary_op, args[0], args[1]]])
            return
        self.compile_expr(self.lower_compare_chain(args, negated_binary_op))

    def compile_binary(self, args, mnemonic):
        if len(args) != 2:
            raise CompileError("%s needs exactly 2 args" % mnemonic)
        self.compile_expr(args[0])
        self.compile_expr(args[1])
        self.emit(mnemonic)

    def compile_unary(self, args, mnemonic):
        if len(args) != 1:
            raise CompileError("%s needs exactly 1 arg" % mnemonic)
        self.compile_expr(args[0])
        self.emit(mnemonic)

    def compile_callprim(self, args, prim_id):
        if len(args) > 255:
            raise CompileError("too many CALLPRIM args")
        for arg in args:
            self.compile_expr(arg)
        self.emit("CALLPRIM", prim_id, len(args))

    def compile_call(self, name, args, tail=False):
        if not isinstance(name, str):
            raise CompileError("bad callee: %r" % (name,))
        if len(args) > 255:
            raise CompileError("too many call args")
        for arg in args:
            self.compile_expr(arg)
        self.emit("TAILCALL" if tail else "CALL", self.literal_symbol(name), len(args))


def compile_source(
    src, heap, strict_arity=False, abi_profile=None, abi_ledger=None
):
    form = parse_one(src)
    return compile_top_form(
        form, heap, strict_arity=strict_arity, abi_profile=abi_profile,
        abi_ledger=abi_ledger,
    )


def compile_top_form_with_helpers(
    form, heap, strict_arity=False, abi_profile=None, abi_ledger=None
):
    abi_profile = _abi_profile(strict_arity, abi_profile)
    abi_ledger = _abi_ledger(abi_profile, abi_ledger)
    helpers = []
    helper_counter = [0]
    if not isinstance(form, list) or not form:
        raise CompileError("top-level form must be lambda or defun")
    head = form[0]
    if head == "lambda":
        if len(form) < 3:
            raise CompileError("lambda needs params and body")
        params, optional_count, rest_param, optional_marker = _params(
            form[1], optional_syntax=strict_arity
        )
        fc = FunctionCompiler(
            heap,
            params,
            optional_count=optional_count,
            optional_marker=optional_marker,
            rest_param=rest_param,
            helper_prefix=_helper_prefix(None),
            helper_counter=helper_counter,
            helpers=helpers,
            strict_arity=strict_arity,
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        return None, fc.compile_body(form[2:]), helpers
    if head == "defun":
        if len(form) < 4 or not isinstance(form[1], str):
            raise CompileError("defun needs name, params, body")
        name = form[1]
        params, optional_count, rest_param, optional_marker = _params(
            form[2], optional_syntax=strict_arity
        )
        fc = FunctionCompiler(
            heap,
            params,
            optional_count=optional_count,
            optional_marker=optional_marker,
            rest_param=rest_param,
            entry=name,
            defun_tail=True,
            helper_prefix=_helper_prefix(name),
            helper_counter=helper_counter,
            helpers=helpers,
            strict_arity=strict_arity,
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        return name, fc.compile_body(form[3:]), helpers
    raise CompileError("unsupported top-level form: %r" % head)


def compile_top_form(
    form, heap, strict_arity=False, abi_profile=None, abi_ledger=None
):
    name, code, helpers = compile_top_form_with_helpers(
        form, heap, strict_arity=strict_arity, abi_profile=abi_profile,
        abi_ledger=abi_ledger,
    )
    if helpers:
        raise CompileError("top-level form needs helper code objects")
    return name, code


def compile_program(
    src, heap, strict_arity=False, abi_profile=None, abi_ledger=None
):
    abi_profile = _abi_profile(strict_arity, abi_profile)
    abi_ledger = _abi_ledger(abi_profile, abi_ledger)
    forms = parse_all(src)
    if not forms:
        raise CompileError("program source must contain at least one defun")
    names = []
    seen = set()
    for form in forms:
        if not isinstance(form, list) or len(form) < 4 or form[0] != "defun":
            raise CompileError("program top-level forms must be defun: %r" % (form,))
        name = form[1]
        if not isinstance(name, str):
            raise CompileError("defun needs symbol name: %r" % (form,))
        if name in seen:
            raise CompileError("duplicate defun: %s" % name)
        seen.add(name)
        names.append(name)
    for name in names:
        heap.intern(name)

    code_by_name = {}
    for form in forms:
        name, code, helpers = compile_top_form_with_helpers(
            form, heap, strict_arity=strict_arity, abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        if name in code_by_name:
            raise CompileError("duplicate code object: %s" % name)
        code_by_name[name] = code
        for helper_name, helper_code in helpers:
            if helper_name in code_by_name:
                raise CompileError("duplicate helper code object: %s" % helper_name)
            names.append(helper_name)
            code_by_name[helper_name] = helper_code
    return names, code_by_name


def _helper_prefix(name):
    text = "anon" if name is None else str(name)
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_").lower()
    return safe or "anon"


def _params(form, optional_syntax=False):
    if not isinstance(form, list):
        raise CompileError("parameter list must be a list")
    params = []
    optional_count = 0
    optional_marker = False
    rest_param = None
    optional_mode = False
    idx = 0
    while idx < len(form):
        item = form[idx]
        if optional_syntax and item == "&optional":
            if optional_marker:
                raise CompileError("duplicate &optional in parameter list")
            optional_marker = True
            optional_mode = True
            idx += 1
            continue
        if item == "&rest":
            if rest_param is not None:
                raise CompileError("duplicate &rest in parameter list")
            if idx + 2 != len(form):
                raise CompileError("&rest must be followed by exactly one parameter")
            rest = form[idx + 1]
            if not isinstance(rest, str) or (optional_syntax and rest.startswith("&")):
                raise CompileError("bad &rest parameter: %r" % (rest,))
            rest_param = rest
            idx += 2
            continue
        if not isinstance(item, str) or (optional_syntax and item.startswith("&")):
            raise CompileError("bad parameter: %r" % (item,))
        if item in params:
            raise CompileError("duplicate parameter: %s" % item)
        params.append(item)
        if optional_mode:
            optional_count += 1
            if optional_count > 63:
                raise CompileError("too many &optional params")
        idx += 1
    if rest_param is not None and rest_param in params:
        raise CompileError("duplicate parameter: %s" % rest_param)
    return params, optional_count, rest_param, optional_marker


def prepare_heap(global_symbols):
    heap = B.Heap()
    for name in global_symbols:
        heap.intern(name)
    return heap


def check_vectors(paths, verbose=False):
    ok = 0
    for path, data in load_vector_files(paths):
        root_symbols = data.get("symbols", [])
        for vector in data.get("vectors", []):
            heap = prepare_heap(root_symbols + vector.get("symbols", []))
            expected_error = vector.get("expect_compile_error")
            try:
                entry, code = compile_source(vector["source"], heap)
            except Exception as exc:
                if expected_error and expected_error in str(exc):
                    ok += 1
                    if verbose:
                        print("PASS %-28s error=%s" % (vector["name"], exc))
                    continue
                raise
            if expected_error:
                raise AssertionError(
                    "%s (%s): expected compile error containing %r"
                    % (vector["name"], path, expected_error)
                )
            got = B.hex_bytes(code.encode())
            expected = B.hex_bytes(B.parse_hex(vector["code_object_hex"]))
            if got != expected:
                raise AssertionError(
                    "%s (%s): compiler hex mismatch\nexpected: %s\nactual:   %s"
                    % (vector["name"], path, expected, got)
                )
            if vector.get("entry") != entry:
                raise AssertionError(
                    "%s (%s): entry mismatch expected %r got %r"
                    % (vector["name"], path, vector.get("entry"), entry)
                )
            ok += 1
            if verbose:
                print("PASS %-28s %s" % (vector["name"], got))
    return ok


def check_programs(paths, verbose=False):
    ok = 0
    for path, data in load_vector_files(paths):
        root_symbols = data.get("symbols", [])
        for program in data.get("programs", []):
            heap = prepare_heap(root_symbols + program.get("symbols", []))
            expected_compile_error = program.get("expect_compile_error")
            try:
                names, code_by_name = compile_program(
                    program["source"],
                    heap,
                    strict_arity=bool(program.get("strict_arity", False)),
                )
            except Exception as exc:
                if expected_compile_error and expected_compile_error in str(exc):
                    ok += 1
                    if verbose:
                        print("PASS %-28s compile-error=%s" % (program["name"], exc))
                    continue
                raise
            if expected_compile_error:
                raise AssertionError(
                    "%s (%s): expected compile error containing %r"
                    % (program["name"], path, expected_compile_error)
                )
            expected_objects = program.get("code_objects")
            if expected_objects is not None:
                if set(expected_objects) != set(code_by_name):
                    raise AssertionError(
                        "%s (%s): code object names mismatch expected %r got %r"
                        % (program["name"], path, sorted(expected_objects), sorted(code_by_name))
                    )
                for name in names:
                    got = B.hex_bytes(code_by_name[name].encode())
                    expected = B.hex_bytes(B.parse_hex(expected_objects[name]))
                    if got != expected:
                        raise AssertionError(
                            "%s/%s (%s): compiler hex mismatch\nexpected: %s\nactual:   %s"
                            % (program["name"], name, path, expected, got)
                        )

            entry = program.get("entry")
            if entry not in code_by_name:
                raise AssertionError("%s (%s): missing entry %r" % (program["name"], path, entry))
            directory = {heap.intern(name): code for name, code in code_by_name.items()}
            args = [B.obj_from_json(heap, arg) for arg in program.get("args", [])]
            vm = B.P0VM(heap=heap, directory=directory)
            expected_vm_error = program.get("expect_vm_error")
            try:
                result = vm.run(code_by_name[entry], args)
            except B.VMError as exc:
                if expected_vm_error == exc.status:
                    ok += 1
                    if verbose:
                        print("PASS %-28s vm-error=%s" % (program["name"], exc.status))
                    continue
                raise
            if expected_vm_error:
                raise AssertionError(
                    "%s (%s): expected VM error %r"
                    % (program["name"], path, expected_vm_error)
                )
            got_text = heap.obj_to_text(result)
            if got_text != program["expect"]:
                raise AssertionError(
                    "%s (%s): result mismatch expected %r got %r"
                    % (program["name"], path, program["expect"], got_text)
                )
            if "expect_obj" in program:
                got_obj = B.obj_hex(result)
                if got_obj.lower() != program["expect_obj"].lower():
                    raise AssertionError(
                        "%s (%s): result obj mismatch expected %s got %s"
                        % (program["name"], path, program["expect_obj"], got_obj)
                    )
            ok += 1
            if verbose:
                print("PASS %-28s entry=%s steps=%d" % (program["name"], entry, vm.steps))
    if ok == 0:
        raise AssertionError("no program vectors found")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="vector JSON files")
    ap.add_argument("--check", action="store_true", help="compile sources and compare golden hex")
    ap.add_argument(
        "--check-programs",
        action="store_true",
        help="compile multi-defun programs, compare golden hex, and run via directory",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args(argv)

    paths = ns.paths or (_default_program_paths() if ns.check_programs else _default_paths())
    if not paths:
        print("bytecode-p0-compiler-check: no vectors found", file=sys.stderr)
        return 1
    if ns.check and ns.check_programs:
        print("choose only one check mode", file=sys.stderr)
        return 2
    if not ns.check and not ns.check_programs:
        print("bytecode_p0_compiler.py requires --check or --check-programs", file=sys.stderr)
        return 2
    try:
        ok = (
            check_programs(paths, verbose=ns.verbose)
            if ns.check_programs
            else check_vectors(paths, verbose=ns.verbose)
        )
    except Exception as e:
        label = "bytecode-p0-program-check" if ns.check_programs else "bytecode-p0-compiler-check"
        print("%s: FAIL: %s" % (label, e), file=sys.stderr)
        return 1
    label = "bytecode-p0-program-check" if ns.check_programs else "bytecode-p0-compiler-check"
    print("%s: PASS=%d FAIL=0" % (label, ok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
