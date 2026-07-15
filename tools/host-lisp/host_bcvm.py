#!/usr/bin/env python3
"""Host reference bytecode compiler and stack VM for the historical dialect.

It is an executable specification for the native Phase-4 VM and continuously
compares tree-walk and bytecode evaluation. The supported core covers values,
control flow, assignment, builtins, recursive DE/EXPR calls, and shared dynamic
value cells. FEXPR, MACRO, nospread, and special builtins are excluded.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lisp64 as L
from lisp64 import Symbol, Pair, Str, NIL, T, intern, list_to_py, resolve_function, Builtin, Closure, lisp_eval, lisp_repr


class Unsupported(Exception):
    pass


def mklist(*items):
    res = NIL
    for x in reversed(items):
        res = Pair(x, res)
    return res


class Compiler:
    def __init__(self):
        self.code = []

    def emit(self, op):
        self.code.append(op); return len(self.code) - 1

    def patch(self, idx, target):
        op = self.code[idx]; self.code[idx] = (op[0], target)

    def compile(self, form):
        if isinstance(form, Symbol):
            if form is NIL or form is T or form.name.startswith(":"):
                self.emit(("CONST", form))
            else:
                self.emit(("VAR", form))
        elif isinstance(form, (int, Str)):
            self.emit(("CONST", form))
        elif isinstance(form, Pair):
            head = form.car
            args = list_to_py(form.cdr)
            if not isinstance(head, Symbol):
                raise Unsupported("Operator: " + lisp_repr(head))
            nm = head.name
            if nm == "QUOTE":
                self.emit(("CONST", args[0]))
            elif nm == "IF":
                self.c_if(args)
            elif nm == "COND":
                self.compile(self.cond_to_if(list_to_py(form.cdr)))
            elif nm == "PROGN":
                self.c_progn(args)
            elif nm == "SETQ":
                self.compile(args[1]); self.emit(("SETV", args[0]))
            elif nm == "AND":
                self.c_logic(args, jmp="JF", empty=T)
            elif nm == "OR":
                self.c_logic(args, jmp="JT", empty=NIL)
            else:
                for a in args:
                    self.compile(a)
                self.emit(("CALL", head, len(args)))
        else:
            self.emit(("CONST", form))

    def c_if(self, args):
        self.compile(args[0])
        jf = self.emit(("JF", None))
        self.compile(args[1])
        jmp = self.emit(("JMP", None))
        self.patch(jf, len(self.code))
        self.compile(args[2] if len(args) > 2 else NIL)
        self.patch(jmp, len(self.code))

    def cond_to_if(self, clauses):
        if not clauses:
            return NIL
        cl = clauses[0]
        test = cl.car
        then = Pair(intern("PROGN"), cl.cdr)
        if isinstance(test, Symbol) and test is T:
            return then
        return mklist(intern("IF"), test, then, self.cond_to_if(clauses[1:]))

    def c_progn(self, args):
        if not args:
            self.emit(("CONST", NIL)); return
        for i, a in enumerate(args):
            if i > 0:
                self.emit(("POP",))
            self.compile(a)

    def c_logic(self, args, jmp, empty):
        if not args:
            self.emit(("CONST", empty)); return
        ends = []
        for i, a in enumerate(args):
            self.compile(a)
            if i < len(args) - 1:
                self.emit(("DUP",))
                ends.append(self.emit((jmp, None)))
                self.emit(("POP",))
        for e in ends:
            self.patch(e, len(self.code))


def compile_top(form):
    c = Compiler(); c.compile(form); return c.code


def is_false(v):
    return v is NIL


def run(code):
    stack = []
    pc = 0
    n = len(code)
    while pc < n:
        op = code[pc]; pc += 1
        t = op[0]
        if t == "CONST":
            stack.append(op[1])
        elif t == "VAR":
            s = op[1]
            if not s.bound:
                raise L.LispError("unbound variable: " + s.name)
            stack.append(s.value)
        elif t == "SETV":
            v = stack.pop(); s = op[1]
            s.value = v; s.bound = True; stack.append(v)
        elif t == "POP":
            stack.pop()
        elif t == "DUP":
            stack.append(stack[-1])
        elif t == "JMP":
            pc = op[1]
        elif t == "JF":
            if is_false(stack.pop()):
                pc = op[1]
        elif t == "JT":
            if not is_false(stack.pop()):
                pc = op[1]
        elif t == "CALL":
            sym = op[1]; k = op[2]
            argv = [stack.pop() for _ in range(k)][::-1]
            stack.append(call(sym, argv))
        else:
            raise Unsupported("Opcode " + t)
    return stack[-1] if stack else NIL


def call(sym, argv):
    fn = resolve_function(sym)
    if fn is None:
        raise L.LispError("undefined function: " + sym.name)
    if isinstance(fn, Builtin):
        if fn.special:
            raise Unsupported("special builtin: " + sym.name)
        return fn.fn(argv)
    if isinstance(fn, Closure):
        if fn.kind != "EXPR":
            raise Unsupported("non-EXPR closure: " + sym.name)
        # A closure stores params as a Lisp list and body as a Python list.
        params = fn.params if isinstance(fn.params, list) else list_to_py(fn.params)
        body = fn.body if isinstance(fn.body, list) else list_to_py(fn.body)
        comp = Compiler(); comp.c_progn(body); code = comp.code
        save = []
        for p, a in zip(params, argv):
            save.append((p, p.bound, p.value)); p.value = a; p.bound = True
        try:
            return run(code)
        finally:
            for p, had, old in reversed(save):
                p.bound = had; p.value = old
    raise Unsupported("call target: " + sym.name)


def vm_eval(form):
    return run(compile_top(form))


# ---------------------------------------------------------------------------
# Differential-Test: Tree-Walker vs. Bytecode-VM
# ---------------------------------------------------------------------------
SETUP = """
(DE FACT (N) (COND ((EQ N 0) 1) (T (TIMES N (FACT (DIFFERENCE N 1))))))
(DE FIB (N) (COND ((LESSP N 2) N) (T (PLUS (FIB (DIFFERENCE N 1)) (FIB (DIFFERENCE N 2))))))
(DE SUMTO (N ACC) (COND ((EQ N 0) ACC) (T (SUMTO (DIFFERENCE N 1) (PLUS ACC N)))))
(DE MYLEN (L) (COND ((NULL L) 0) (T (ADD1 (MYLEN (CDR L))))))
"""

CASES = [
    "(PLUS (TIMES 3 4) (DIFFERENCE 10 2))",
    "(COND ((LESSP 2 3) 10) (T 20))",
    "(COND ((GREATERP 2 3) 10) (T 20))",
    "(COND ((EQ 1 2) (QUOTE A)) ((EQ 1 1) (QUOTE B)) (T (QUOTE C)))",
    "(AND 1 2 3)",
    "(AND 1 NIL 3)",
    "(OR NIL NIL 5)",
    "(OR 1 2)",
    "(PROGN (SETQ GX 7) (PLUS GX 1))",
    "(CAR (CDR (QUOTE (1 2 3))))",
    "(REVERSE (QUOTE (1 2 3 4)))",
    "(LENGTH (APPEND (QUOTE (1 2)) (QUOTE (3 4 5))))",
    "(FACT 5)",
    "(FACT 8)",
    "(FIB 10)",
    "(SUMTO 100 0)",
    "(MYLEN (QUOTE (A B C D E)))",
    "(TIMES (FACT 4) (FIB 7))",
]


def main():
    for form in L.read_all(SETUP):
        lisp_eval(form)
    ok = 0
    for src in CASES:
        f1, _ = L.Reader(src).read()
        f2, _ = L.Reader(src).read()
        a = lisp_eval(f1)
        b = vm_eval(f2)
        ra, rb = lisp_repr(a), lisp_repr(b)
        assert ra == rb, "DIFFERENTIAL: %s -> Tree %s != VM %s" % (src, ra, rb)
        ok += 1
    print("host_bcvm: ALLES OK (%d Differential-Faelle, Tree == Bytecode)" % ok)


if __name__ == "__main__":
    main()
