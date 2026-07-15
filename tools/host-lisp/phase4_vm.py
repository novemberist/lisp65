#!/usr/bin/env python3
"""Independent host oracle for the historical native Phase-4 bytecode VM.

The Python model executes the native opcode set without VICE and lets tests
predict VM output before emulator runs. Default mode models the normal build;
`object_values=True` adds raw object identity, NIL/T literals, and NIL-only
false semantics. Arithmetic wraps as signed 32-bit values.

The small source-result classifier models compile-time boundaries rather than a
second compiler. Call16, CallRoot operations, and nonzero-depth closure frames
require the full code-object runtime and therefore raise UnsupportedOpcode.

Usage:
  phase4_vm.py --selftest
  phase4_vm.py --acme-label Phase4VMSmokeCode
  phase4_vm.py --expr "(PLUS 2 (DIFFERENCE 50 10))"  # compile + run
  phase4_vm.py --object-values --source-kind "(NOT (QUOTE QUOTE))"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase4_disasm import (OPCODES, decode_one, DisasmError,  # noqa: E402
                           extract_acme_label, parse_hex)

MASK32 = 0xFFFFFFFF


def to_int32(v):
    v &= MASK32
    return v - 0x100000000 if v & 0x80000000 else v


class VMError(Exception):
    pass


class UnsupportedOpcode(Exception):
    pass


# Opcodes that require code-object runtime support and cannot be modeled by a pure arithmetic oracle.
_UNSUPPORTED = {4, 36, 38, 39}   # Call16, CallRoot1/2/3

# Frame-slot prototype with depth 0 and three local slots. LOADL/STOREL address VM-local slots;
# depth > 0 or index >= N is an error. Arguments seed slots 0..N-1 and the remainder starts NIL.
_FRAME_SLOTS = 3
_SLOT_NAME_TO_IDX = {"A": 0, "B": 1, "C": 2}
_SLOT_IDX_TO_NAME = {0: "A", 1: "B", 2: "C"}

_LIT_U8 = 1
_LIT_S8 = 2
_LIT_U16 = 3
_LIT_S16 = 4
_LIT_NIL = 5
_LIT_T = 6


def _typed_literal_value(entry, object_values=False):
    """Convert one host entry to the ACC32 value produced by PUSHLITTYPED."""
    if isinstance(entry, tuple):
        kind, value = entry
    else:
        kind, value = entry, None
    if isinstance(kind, str):
        kind = {
            "u8": _LIT_U8, "s8": _LIT_S8, "u16": _LIT_U16, "s16": _LIT_S16,
            "nil": _LIT_NIL, "t": _LIT_T,
        }[kind.lower()]
    if kind == _LIT_U8:
        return value & 0xFF
    if kind == _LIT_S8:
        value &= 0xFF
        return value - 0x100 if value & 0x80 else value
    if kind == _LIT_U16:
        return value & 0xFFFF
    if kind == _LIT_S16:
        value &= 0xFFFF
        return value - 0x10000 if value & 0x8000 else value
    if kind == _LIT_NIL and object_values:
        return 0
    if kind == _LIT_T and object_values:
        return 1
    raise VMError("ungueltiger typed Literal-Eintrag: %r" % (entry,))


def run(mem, args=(), literals=(), typed_literals=(), object_values=False,
        max_steps=100000):
    """Execute one bytecode sequence.

    args holds up to three values. literals backs the PushLit family;
    typed_literals contains entries such as ("s16", 0xFED4), "nil", or "t".
    Return output, stack, halted, and steps. Output strings match native VM
    PrintAcc/PrintBool lines.
    """
    stack = []
    arg = [to_int32(a) for a in args] + [0, 0, 0]
    # Local depth-0 frame slots seeded from arguments.
    frame = list(arg[:_FRAME_SLOTS])
    out = []
    pc = 0
    steps = 0

    def pop():
        if not stack:
            raise VMError("Stack-Underflow bei $%04X" % pc)
        return stack.pop()

    while pc < len(mem):
        steps += 1
        if steps > max_steps:
            raise VMError("max_steps ueberschritten (Endlosschleife?)")
        ins = decode_one(mem, pc)
        op = ins["opcode"]
        if op in _UNSUPPORTED or (op == 45 and not object_values):
            raise UnsupportedOpcode("%s bei $%04X (Codeobjekt-Laufzeit noetig)"
                                    % (ins["mnemonic"], pc))
        nxt = pc + ins["length"]

        if op == 0:                              # HALT
            return {"output": out, "stack": stack, "halted": True, "steps": steps}
        elif op == 5:                            # RET (top-level => stop)
            return {"output": out, "stack": stack, "halted": True, "steps": steps}
        elif op == 1:                            # PUSHI8 (unsigned immediate)
            stack.append(ins["operand"])
        elif op == 43:                           # PUSHNIL
            stack.append(0)
        elif op == 44:                           # PUSHT
            stack.append(1)
        elif op in (11, 12, 13):                 # PUSHARG0/1/2
            stack.append(arg[op - 11])
        elif op in (6, 7, 8, 9):                 # PUSHLIT8/S8/16/S16
            idx = ins["operand"]
            if idx >= len(literals):
                raise VMError("Literal-Index %d ausserhalb der Tabelle" % idx)
            stack.append(to_int32(literals[idx]))
        elif op == 10:                           # PUSHLITTYPED
            idx = ins["operand"]
            if idx >= len(typed_literals):
                raise VMError("Typed-Literal-Index %d ausserhalb der Tabelle" % idx)
            stack.append(to_int32(_typed_literal_value(
                typed_literals[idx], object_values=object_values)))
        elif op == 45:                           # PUSHOBJ (Object-Values-Slice)
            stack.append(ins["operand"])
        # ---- Binary arithmetic and bits ----
        elif op == 2:                            # ADD
            b = pop(); a = pop(); stack.append(to_int32(a + b))
        elif op == 14:                           # SUB
            b = pop(); a = pop(); stack.append(to_int32(a - b))
        elif op == 15:                           # MUL
            b = pop(); a = pop(); stack.append(to_int32(a * b))
        elif op == 16:                           # DIV (QUOTIENT, trunc->0)
            b = pop(); a = pop()
            if b == 0:
                raise VMError("Division durch 0 bei $%04X" % pc)
            q = int(a / b) if (a < 0) ^ (b < 0) else a // b
            stack.append(to_int32(q))
        elif op == 24:                           # REMAINDER (Vorzeichen Dividend)
            b = pop(); a = pop()
            if b == 0:
                raise VMError("Division durch 0 bei $%04X" % pc)
            r = abs(a) % abs(b)
            stack.append(to_int32(-r if a < 0 else r))
        elif op == 26:                           # LOGAND
            b = pop(); a = pop(); stack.append(to_int32((a & b) & MASK32))
        elif op == 27:                           # LOGOR
            b = pop(); a = pop(); stack.append(to_int32((a | b) & MASK32))
        elif op == 32:                           # LOGXOR
            b = pop(); a = pop(); stack.append(to_int32((a ^ b) & MASK32))
        # ---- Unary operations ----
        elif op == 22:                           # ADD1
            stack.append(to_int32(pop() + 1))
        elif op == 23:                           # SUB1
            stack.append(to_int32(pop() - 1))
        elif op == 25:                           # MINUS (-x)
            stack.append(to_int32(-pop()))
        elif op == 31:                           # ABS
            stack.append(to_int32(abs(pop())))
        elif op == 33:                           # COMPL (~x, bitweise)
            stack.append(to_int32(~pop()))
        elif op == 34:                           # LBYTE
            stack.append(pop() & 0xFF)
        elif op == 35:                           # HBYTE
            stack.append((pop() >> 8) & 0xFF)
        # ---- Comparisons and booleans, pushing 1/0 ----
        elif op == 18:                           # LESS
            b = pop(); a = pop(); stack.append(1 if a < b else 0)
        elif op == 19:                           # GREATER
            b = pop(); a = pop(); stack.append(1 if a > b else 0)
        elif op == 30:                           # EQ
            b = pop(); a = pop(); stack.append(1 if a == b else 0)
        elif op == 20:                           # ZEROP
            stack.append(1 if pop() == 0 else 0)
        elif op == 21:                           # MINUSP
            stack.append(1 if pop() < 0 else 0)
        elif op == 42:                           # NOT
            stack.append(1 if pop() == 0 else 0)
        elif op == 48:                           # DROP
            pop()
        # ---- Depth-0 frame slots ----
        elif op == 46:                           # LOADL depth,idx
            depth, idx = ins["operand"]
            if depth != 0 or idx >= _FRAME_SLOTS:
                raise VMError("BadFrameSlot LOADL %d,%d bei $%04X"
                              % (depth, idx, pc))
            stack.append(frame[idx])
        elif op == 47:                           # STOREL depth,idx (void)
            depth, idx = ins["operand"]
            if depth != 0 or idx >= _FRAME_SLOTS:
                raise VMError("BadFrameSlot STOREL %d,%d bei $%04X"
                              % (depth, idx, pc))
            frame[idx] = pop()
        # ---- Output ----
        elif op == 3:                            # PRINTACC
            out.append(str(to_int32(pop())))
        elif op == 17:                           # PRINTBOOL
            out.append("NIL" if pop() == 0 else "T")
        # ---- Branches ----
        elif op == 28:                           # JMPREL
            pc = ins["target"]; continue
        elif op == 29:                           # JFALSEREL
            v = pop()
            if v == 0:
                pc = ins["target"]; continue
        # ---- Tail self-call: replace arguments and reset PC ----
        elif op == 37:                           # TAILSELF1
            arg[0] = pop(); pc = 0; continue
        elif op == 40:                           # TAILSELF2
            arg[1] = pop(); arg[0] = pop(); pc = 0; continue
        elif op == 41:                           # TAILSELF3
            arg[2] = pop(); arg[1] = pop(); arg[0] = pop(); pc = 0; continue
        else:
            raise UnsupportedOpcode("%s bei $%04X" % (ins["mnemonic"], pc))

        pc = nxt

    return {"output": out, "stack": stack, "halted": False, "steps": steps}


# ---- Mini compiler: Lisp-like AST -> bytecode ----------------------------
#
# AST is an integer or (OPNAME, arg, ...). Constants use a literal table so arbitrary 32-bit
# values and the PushLit path are exercised.

_BINOP = {"PLUS": 2, "DIFFERENCE": 14, "TIMES": 15, "QUOTIENT": 16,
          "REMAINDER": 24, "LOGAND": 26, "LOGOR": 27, "LOGXOR": 32,
          "LESSP": 18, "GREATERP": 19, "EQ": 30}
_UNOP = {"MINUS": 25, "ABS": 31, "ADD1": 22, "SUB1": 23, "COMPL": 33,
         "LBYTE": 34, "HBYTE": 35, "ZEROP": 20, "MINUSP": 21, "NOT": 42}

RESULT_NUMERIC = "numeric"
RESULT_BOOL = "bool"
RESULT_OBJECT = "object"

_NUMERIC_BINOPS = {
    "PLUS", "DIFFERENCE", "TIMES", "QUOTIENT", "REMAINDER",
    "LOGAND", "LOGOR", "LOGXOR",
}
_NUMERIC_PREDICATES = {"LESSP", "GREATERP"}
_NUMERIC_UNOPS = {"MINUS", "ABS", "ADD1", "SUB1", "COMPL", "LBYTE", "HBYTE"}
_NUMERIC_UNARY_PREDICATES = {"ZEROP", "MINUSP"}


class SourceTypeError(ValueError):
    pass


def _require_non_object(kind, form):
    if kind == RESULT_OBJECT:
        raise SourceTypeError("object operand in numeric source form: %r" %
                              (form,))


def _quoted_result_kind(value, object_values=False):
    if not object_values:
        raise SourceTypeError("quoted object outside Object-Values source")
    if isinstance(value, str):
        return RESULT_OBJECT
    raise SourceTypeError("quoted cons object not yet source-lowerable: %r" %
                          (value,))


def infer_source_result_kind(ast, object_values=False):
    """Return numeric/bool/object for the modelled Source-Lowerer subset.

    The native compiler still owns byte emission. This helper intentionally
    tracks only the type policy needed by the Object-Values boundary tests:
    numeric operators reject object operands, EQ accepts raw identity values,
    NOT/COND conditions accept general truth values, and COND rejects mixed
    object/non-object branch result kinds until tagged values exist.
    """
    if isinstance(ast, int):
        return RESULT_NUMERIC
    if isinstance(ast, str):
        if object_values and ast in ("NIL", "T"):
            return RESULT_OBJECT
        raise SourceTypeError("unbound host source symbol: %s" % ast)
    op = ast[0]
    rands = ast[1:]
    if op == "QUOTE":
        if len(rands) != 1:
            raise SourceTypeError("QUOTE needs one operand")
        return _quoted_result_kind(rands[0], object_values=object_values)
    if op in _NUMERIC_BINOPS:
        if len(rands) < 2:
            raise SourceTypeError("%s needs >=2 operands" % op)
        for r in rands:
            _require_non_object(
                infer_source_result_kind(r, object_values=object_values), ast)
        return RESULT_NUMERIC
    if op in _NUMERIC_PREDICATES:
        if len(rands) != 2:
            raise SourceTypeError("%s needs two operands" % op)
        for r in rands:
            _require_non_object(
                infer_source_result_kind(r, object_values=object_values), ast)
        return RESULT_BOOL
    if op == "EQ":
        if len(rands) != 2:
            raise SourceTypeError("EQ needs two operands")
        infer_source_result_kind(rands[0], object_values=object_values)
        infer_source_result_kind(rands[1], object_values=object_values)
        return RESULT_BOOL
    if op in _NUMERIC_UNOPS:
        if len(rands) != 1:
            raise SourceTypeError("%s needs one operand" % op)
        _require_non_object(
            infer_source_result_kind(rands[0], object_values=object_values),
            ast)
        return RESULT_NUMERIC
    if op in _NUMERIC_UNARY_PREDICATES:
        if len(rands) != 1:
            raise SourceTypeError("%s needs one operand" % op)
        _require_non_object(
            infer_source_result_kind(rands[0], object_values=object_values),
            ast)
        return RESULT_BOOL
    if op == "NOT":
        if len(rands) != 1:
            raise SourceTypeError("NOT needs one operand")
        infer_source_result_kind(rands[0], object_values=object_values)
        return RESULT_BOOL
    if op == "COND":
        result_kind = None
        for clause in rands:
            if len(clause) != 2:
                raise SourceTypeError("COND clause needs test and value")
            infer_source_result_kind(clause[0], object_values=object_values)
            clause_result = infer_source_result_kind(
                clause[1], object_values=object_values)
            if result_kind is None:
                result_kind = clause_result
            elif result_kind != clause_result:
                if object_values and (
                    result_kind == RESULT_OBJECT or
                    clause_result == RESULT_OBJECT
                ):
                    raise SourceTypeError(
                        "mixed object/non-object COND results: %r" % (ast,))
                result_kind = RESULT_NUMERIC
        if result_kind is None:
            raise SourceTypeError("COND needs at least one clause")
        return result_kind
    raise SourceTypeError("unmodelled source operator: %s" % op)


def _is_void_form(ast):
    """Void forms SETQ and STOREL leave no value on the stack."""
    return isinstance(ast, tuple) and len(ast) >= 1 and ast[0] in ("SETQ", "STOREL")


def _progn_to_begin2(forms):
    """Lower PROGN to the exact right-nested BEGIN2 shape."""
    if not forms:
        raise ValueError("PROGN braucht mindestens eine Form")
    if len(forms) == 1:
        return forms[0]
    return ("BEGIN2", forms[0], _progn_to_begin2(forms[1:]))


class _Comp:
    def __init__(self):
        self.code = []
        self.literals = []

    def _lit(self, v):
        v = to_int32(v)
        if v in self.literals:
            return self.literals.index(v)
        self.literals.append(v)
        return len(self.literals) - 1

    def emit_expr(self, ast):
        if isinstance(ast, int):
            if 0 <= ast <= 255:
                self.code += [1, ast]            # PUSHI8
            else:
                self.code += [9, self._lit(ast)]  # PUSHLITS16
            return
        if isinstance(ast, str):                 # lokale Slot-Referenz A/B/C
            if ast in _SLOT_NAME_TO_IDX:
                self.code += [46, 0, _SLOT_NAME_TO_IDX[ast]]   # LOADL 0,idx
                return
            raise ValueError("unbekannte Slot-Referenz: %s" % ast)
        op = ast[0]
        rands = ast[1:]
        if op in _BINOP:
            if len(rands) < 2:
                raise ValueError("%s braucht >=2 Argumente" % op)
            self.emit_expr(rands[0])
            for r in rands[1:]:                  # links-assoziativ falten
                self.emit_expr(r)
                self.code.append(_BINOP[op])
            return
        if op in _UNOP:
            if len(rands) != 1:
                raise ValueError("%s braucht 1 Argument" % op)
            self.emit_expr(rands[0])
            self.code.append(_UNOP[op])
            return
        # ---- Frame-slot lowering, mirroring the source lowerer ----
        if op == "SETQ":                         # (SETQ A|B|C expr) -> STOREL (void)
            name, expr = rands
            self.emit_expr(expr)
            self.code += [47, 0, _SLOT_NAME_TO_IDX[name]]
            return
        if op == "STOREL":                       # (STOREL depth idx expr)
            depth, idx, expr = rands
            self.emit_expr(expr)
            self.code += [47, depth, idx]
            return
        if op == "LOADL":                        # (LOADL depth idx)
            depth, idx = rands
            self.code += [46, depth, idx]
            return
        if op == "BEGIN2":                       # (BEGIN2 first second)
            first, second = rands
            self.emit_expr(first)
            if not _is_void_form(first):         # Zwischenwert verwerfen
                self.code.append(48)             # DROP
            self.emit_expr(second)
            return
        if op == "PROGN":                        # -> rechts-genestete BEGIN2
            self.emit_expr(_progn_to_begin2(rands))
            return
        raise ValueError("unbekannter Operator: %s" % op)


def compile_expr(ast, print_result=True):
    """Compile an AST to (bytecode, literals).

    With print_result, emit PRINTACC for the result followed by HALT.
    """
    c = _Comp()
    c.emit_expr(ast)
    if print_result:
        c.code.append(3)       # PRINTACC
    c.code.append(0)           # HALT
    return bytes(c.code), c.literals


def eval_ast(ast, env=None):
    """Python oracle with matching dialect semantics.

    env represents local frame slots A/B/C. SETQ and STOREL mutate them,
    PROGN/BEGIN2 sequence them, and LOADL or slot references read them.
    """
    if env is None:
        env = {"A": 0, "B": 0, "C": 0}
    if isinstance(ast, int):
        return to_int32(ast)
    if isinstance(ast, str):                     # lokale Slot-Referenz
        if ast in env:
            return env[ast]
        raise ValueError("unbekannte Slot-Referenz: %s" % ast)
    op = ast[0]
    # ---- Special forms: do not evaluate eagerly ----
    if op == "SETQ":
        name, expr = ast[1], ast[2]
        env[name] = eval_ast(expr, env)
        return None
    if op == "STOREL":
        env[_SLOT_IDX_TO_NAME[ast[2]]] = eval_ast(ast[3], env)
        return None
    if op == "LOADL":
        return env[_SLOT_IDX_TO_NAME[ast[2]]]
    if op == "BEGIN2":
        eval_ast(ast[1], env)
        return eval_ast(ast[2], env)
    if op == "PROGN":
        result = None
        for f in ast[1:]:
            result = eval_ast(f, env)
        return result
    # ---- Normal operators: eager ----
    rands = [eval_ast(x, env) for x in ast[1:]]
    if op == "PLUS":
        return to_int32(sum(rands))
    if op == "DIFFERENCE":
        acc = rands[0]
        for r in rands[1:]:
            acc = to_int32(acc - r)
        return acc
    if op == "TIMES":
        acc = 1
        for r in rands:
            acc = to_int32(acc * r)
        return acc
    if op == "QUOTIENT":
        acc = rands[0]
        for d in rands[1:]:
            if d == 0:
                raise VMError("Division durch 0")
            acc = to_int32(int(acc / d) if (acc < 0) ^ (d < 0) else acc // d)
        return acc
    if op == "REMAINDER":
        n, d = rands
        r = abs(n) % abs(d)
        return to_int32(-r if n < 0 else r)
    if op == "LOGAND":
        acc = MASK32
        for r in rands:
            acc &= r & MASK32
        return to_int32(acc)
    if op == "LOGOR":
        acc = 0
        for r in rands:
            acc |= r & MASK32
        return to_int32(acc)
    if op == "LOGXOR":
        acc = 0
        for r in rands:
            acc ^= r & MASK32
        return to_int32(acc)
    if op == "LESSP":
        return 1 if rands[0] < rands[1] else 0
    if op == "GREATERP":
        return 1 if rands[0] > rands[1] else 0
    if op == "EQ":
        return 1 if rands[0] == rands[1] else 0
    if op == "MINUS":
        return to_int32(-rands[0])
    if op == "ABS":
        return to_int32(abs(rands[0]))
    if op == "ADD1":
        return to_int32(rands[0] + 1)
    if op == "SUB1":
        return to_int32(rands[0] - 1)
    if op == "COMPL":
        return to_int32(~rands[0])
    if op == "LBYTE":
        return rands[0] & 0xFF
    if op == "HBYTE":
        return (rands[0] >> 8) & 0xFF
    if op == "ZEROP":
        return 1 if rands[0] == 0 else 0
    if op == "MINUSP":
        return 1 if rands[0] < 0 else 0
    if op == "NOT":
        return 1 if rands[0] == 0 else 0
    raise ValueError("unbekannter Operator: %s" % op)


def run_expr(ast):
    code, lits = compile_expr(ast)
    res = run(code, literals=lits)
    return res["output"]


# ---- Simple S-expression parser for the CLI ------------------------------

def parse_sexpr(s):
    toks = s.replace("(", " ( ").replace(")", " ) ").split()
    pos = [0]

    def parse():
        t = toks[pos[0]]; pos[0] += 1
        if t == "(":
            lst = []
            while toks[pos[0]] != ")":
                lst.append(parse())
            pos[0] += 1
            return tuple(lst) if not isinstance(lst[0], int) else lst
        if t == ")":
            raise ValueError("unerwartetes )")
        try:
            return int(t)
        except ValueError:
            return t   # Operatorname
    return parse()


# ---- Self-test -----------------------------------------------------------

def _selftest():
    import random

    # 1) Source smoke program: PushI8 2/3, Add, Print -> 5.
    here = os.path.dirname(os.path.abspath(__file__))
    acme = os.path.join(here, "..", "..", "src", "v2", "modules",
                        "20-bytecode-vm.acme")
    if os.path.exists(acme):
        mem = extract_acme_label(acme, "Phase4VMSmokeCode")
        assert run(mem)["output"] == ["5"], run(mem)

    # 2) Handwritten mixed arithmetic -> 42.
    prog = bytes([1, 2, 1, 50, 1, 10, 14, 2, 3, 0])
    assert run(prog)["output"] == ["42"], run(prog)

    # 3) Signed 32-bit wraparound.
    assert run_expr(("TIMES", 100000, 100000)) == [str(to_int32(10000000000))]

    # 4) Booleans as 1/0 plus PRINTBOOL.
    #    PUSHI8 3 ; PUSHI8 5 ; LESS ; PRINTBOOL ; HALT  -> "T"
    assert run(bytes([1, 3, 1, 5, 18, 17, 0]))["output"] == ["T"]
    assert run(bytes([1, 5, 1, 3, 18, 17, 0]))["output"] == ["NIL"]

    # 4a) Sequencing drops the first value and prints the second.
    assert run(bytes([1, 12, 48, 1, 34, 3, 0]))["output"] == ["34"]

    # 4b) Typed-literal smoke: -300 + 500 -> 200.
    typed = [("s16", 0xFED4), ("u16", 0x01F4)]
    assert run(bytes([10, 0, 10, 1, 2, 3, 0]),
               typed_literals=typed)["output"] == ["200"]

    # 4c) Object truth: NIL/T, typed NIL/T, and PushObj identity.
    obj_prog = bytes([
        43, 17,                         # PUSHNIL PRINTBOOL -> NIL
        44, 17,                         # PUSHT PRINTBOOL -> T
        43, 42, 17,                     # (NOT NIL) -> T
        44, 29, 3, 1, 7, 3,             # T branch not taken -> 7
        43, 29, 3, 1, 99, 3,            # NIL branch skips 99
        10, 0, 17,                      # typed NIL -> NIL
        10, 1, 42, 17,                  # (NOT typed T) -> NIL
        10, 1, 44, 30, 17,              # typed T EQ PUSHT -> T
        43, 43, 30, 17,                 # NIL EQ NIL -> T
        44, 43, 30, 17,                 # T EQ NIL -> NIL
        45, 0x34, 0x12, 42, 17,         # object is true; NOT -> NIL
        45, 0x34, 0x12, 29, 3, 1, 8, 3, # object branch not taken -> 8
        45, 0x34, 0x12, 45, 0x34, 0x12, 30, 17,
        45, 0x34, 0x12, 45, 0x35, 0x12, 30, 17,
        0
    ])
    assert run(obj_prog, typed_literals=["nil", "t"], object_values=True)[
        "output"] == ["NIL", "T", "T", "7", "NIL", "NIL", "T",
                      "T", "NIL", "NIL", "8", "T", "NIL"]

    # 4d) Object-value source policy checks compile-time boundaries, not bytecode emission.
    qsym = ("QUOTE", "QUOTE")
    assert infer_source_result_kind(
        ("NOT", qsym), object_values=True) == RESULT_BOOL
    assert infer_source_result_kind(
        ("COND", (qsym, 42), ("T", 99)), object_values=True) == RESULT_NUMERIC
    assert infer_source_result_kind(
        ("COND", (qsym, qsym), ("T", ("QUOTE", "T"))),
        object_values=True) == RESULT_OBJECT
    assert infer_source_result_kind(
        ("COND", (("ZEROP", 0), 42), ("T", ("EQ", 1, 1))),
        object_values=True) == RESULT_NUMERIC
    for bad in [
        ("QUOTE", ("A", "B")),
        ("PLUS", qsym, 1),
        ("ZEROP", qsym),
        ("COND", (qsym, qsym), ("T", 99)),
    ]:
        try:
            infer_source_result_kind(bad, object_values=True)
            assert False, "erwartete SourceTypeError fuer %r" % (bad,)
        except SourceTypeError:
            pass

    # 5) Branch: JFALSEREL skips PRINTACC for NIL.
    #    PUSHNIL ; JFALSEREL +3 ; PUSHI8 99 ; PRINTACC ; PUSHI8 7 ; PRINTACC ; HALT
    #    NIL branches over PUSHI8 99 / PRINTACC, leaving only 7.
    prog5 = bytes([43, 29, 0x03, 1, 99, 3, 1, 7, 3, 0])
    assert run(prog5)["output"] == ["7"], run(prog5)

    # 6) TailSelf1 loop counts argument 0 down and prints zero.
    #    $00 PUSHARG0  $01 JFALSEREL +3 (->$06 when Arg0==NIL)
    #    $03 PUSHARG0  $04 SUB1  $05 TAILSELF1 (Arg0<-Arg0-1, PC=0)
    #    $06 PUSHARG0  $07 PRINTACC  $08 HALT
    loop = bytes([11, 29, 0x03, 11, 23, 37, 11, 3, 0])
    assert run(loop, args=(5,))["output"] == ["0"], run(loop, args=(5,))
    assert run(loop, args=(0,))["output"] == ["0"]

    # 7) Unsupported opcode reports cleanly.
    try:
        run(bytes([36, 0, 0xC0, 0]))
        assert False, "erwartete UnsupportedOpcode"
    except UnsupportedOpcode:
        pass

    # 8) Differential random arithmetic: oracle equals reference.
    rng = random.Random(20260621)
    ops_bin = ["PLUS", "DIFFERENCE", "TIMES", "QUOTIENT", "REMAINDER",
               "LOGAND", "LOGOR", "LOGXOR"]
    ops_un = ["MINUS", "ABS", "ADD1", "SUB1", "COMPL", "LBYTE", "HBYTE"]

    def gen(depth):
        if depth <= 0 or rng.random() < 0.35:
            return rng.randint(-70000, 70000)
        if rng.random() < 0.30:
            return (rng.choice(ops_un), gen(depth - 1))
        op = rng.choice(ops_bin)
        a, b = gen(depth - 1), gen(depth - 1)
        if op in ("QUOTIENT", "REMAINDER") and eval_ast(b) == 0:
            b = 1
        return (op, a, b)

    n = 0
    for _ in range(1500):
        ast = gen(4)
        try:
            expect = eval_ast(ast)
        except VMError:
            continue   # Division durch 0 verworfen
        got = run_expr(ast)
        assert got == [str(expect)], "AST=%r erwartet %s, Orakel %s" % (
            ast, expect, got)
        n += 1

    # 9) Frame slots: reproduce native smokes and byte-exact lowering.
    #    LOADL 0,0 from a seeded slot.
    assert run(bytes([46, 0, 0, 3, 0]), args=(42,))["output"] == ["42"]
    #    STOREL 0,1 followed by LOADL 0,1.
    assert run(bytes([1, 99, 47, 0, 1, 46, 0, 1, 3, 0]))["output"] == ["99"]
    #    BadFrameSlot: nonzero depth and index >= 3 are errors.
    for bad in (bytes([46, 1, 0, 0]), bytes([46, 0, 3, 0]),
                bytes([1, 5, 47, 1, 0, 0]), bytes([1, 5, 47, 0, 3, 0])):
        try:
            run(bad)
            assert False, "erwartete VMError (BadFrameSlot)"
        except VMError:
            pass

    # 9a) Byte-exact lowering snapshots without Print/HALT.
    def _lower(ast):
        c = _Comp(); c.emit_expr(ast); return bytes(c.code)
    #     (PROGN 1 2 42) -> BEGIN2 (LIT8 1) (BEGIN2 (LIT8 2) (LIT8 42))
    assert _lower(("PROGN", 1, 2, 42)) == bytes([1, 1, 48, 1, 2, 48, 1, 42])
    #     (PROGN 1 (SETQ B 99) B) -> BEGIN2 (LIT8 1)
    #         (BEGIN2 (STOREL 0,1 (LIT8 99)) (LOADL 0,1))
    assert _lower(("PROGN", 1, ("SETQ", "B", 99), "B")) == bytes(
        [1, 1, 48, 1, 99, 47, 0, 1, 46, 0, 1])
    #     End-to-end readable result.
    assert run_expr(("PROGN", 1, ("SETQ", "B", 99), "B")) == ["99"]

    # 9b) Differential PROGN/SETQ bodies over local slots; oracle equals reference.
    slots = ["A", "B", "C"]

    def gen_slot_expr(depth):
        r = rng.random()
        if depth <= 0 or r < 0.4:
            return rng.randint(0, 200)
        if r < 0.6:
            return rng.choice(slots)
        op = rng.choice(["PLUS", "DIFFERENCE", "TIMES"])
        return (op, gen_slot_expr(depth - 1), gen_slot_expr(depth - 1))

    def gen_body():
        forms = [("SETQ", rng.choice(slots), gen_slot_expr(2))
                 for _ in range(rng.randint(1, 4))]
        forms.append(rng.choice(slots))          # finaler Slot-Read (non-void)
        return ("PROGN",) + tuple(forms)

    m = 0
    for _ in range(1000):
        ast = gen_body()
        expect = eval_ast(ast)
        got = run_expr(ast)
        assert got == [str(expect)], "AST=%r erwartet %s, Orakel %s" % (
            ast, expect, got)
        m += 1

    # 9c) Cross-check against the real native payloads from source.
    if os.path.exists(acme):
        load_pl = extract_acme_label(acme, "Phase6VMLoadLSmokePayload")
        assert run(load_pl, args=(42,))["output"] == ["42"], run(load_pl)
        store_pl = extract_acme_label(acme, "Phase6VMStoreLSmokePayload")
        assert run(store_pl)["output"] == ["99"], run(store_pl)

    print("phase4_vm self-test: ALLES OK (%d Arithmetik- + %d Frame-Slot-"
          "Differential-Faelle)" % (n, m))


def main(argv):
    if not argv or "--selftest" in argv:
        _selftest()
        return 0
    object_values = False
    if "--object-values" in argv:
        object_values = True
        argv = [a for a in argv if a != "--object-values"]
    if argv[0] == "--acme-label":
        here = os.path.dirname(os.path.abspath(__file__))
        acme = os.path.join(here, "..", "..", "src", "v2", "modules",
                            "20-bytecode-vm.acme")
        mem = extract_acme_label(acme, argv[1])
        args = [int(x) for x in argv[2:]]
        res = run(mem, args=args, object_values=object_values)
        print("output:", res["output"], "stack:", res["stack"],
              "halted:", res["halted"])
        return 0
    if argv[0] == "--hex":
        res = run(parse_hex(" ".join(argv[1:])), object_values=object_values)
        print("output:", res["output"], "stack:", res["stack"])
        return 0
    if argv[0] == "--expr":
        ast = parse_sexpr(" ".join(argv[1:]))
        code, lits = compile_expr(ast)
        res = run(code, literals=lits)
        print("AST     :", ast)
        print("literals:", lits)
        print("output  :", res["output"])
        print("referenz:", [str(eval_ast(ast))])
        return 0
    if argv[0] == "--source-kind":
        ast = parse_sexpr(" ".join(argv[1:]))
        try:
            print(infer_source_result_kind(ast, object_values=object_values))
            return 0
        except SourceTypeError as exc:
            print("error:", exc)
            return 1
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
