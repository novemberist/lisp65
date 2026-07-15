#!/usr/bin/env python3
"""Historical Phase-4 bytecode VM host prototype.

The 6502-independent model combines a small Scheme-like compiler with a stack
VM, constant pool, lexical frame slots, closures, and tail calls. It covers
quote, control forms, let bindings, lambda with &rest, mutation, calls, and
arithmetic/list primitives. Opcodes are tuples, but retain the compile-once,
tight-dispatch design.
"""

import sys

# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

class Sym:
    _tab = {}
    __slots__ = ("name",)
    def __new__(cls, name):
        s = cls._tab.get(name)
        if s is None:
            s = object.__new__(cls); s.name = name; cls._tab[name] = s
        return s
    def __repr__(self):
        return self.name

class Pair:
    __slots__ = ("car", "cdr")
    def __init__(self, a, d):
        self.car, self.cdr = a, d

class NilType:
    _i = None
    def __new__(cls):
        if cls._i is None:
            cls._i = object.__new__(cls)
        return cls._i
    def __repr__(self):
        return "()"

NIL = NilType()

class Closure:
    __slots__ = ("code", "env")
    def __init__(self, code, env):
        self.code, self.env = code, env

class Primitive:
    __slots__ = ("fn", "name")
    def __init__(self, fn, name):
        self.fn, self.name = fn, name

class Frame:
    __slots__ = ("slots", "parent")
    def __init__(self, slots, parent):
        self.slots, self.parent = slots, parent

def is_false(v):
    return v is False or v is NIL

def lisp_list(pyvals, tail=NIL):
    out = tail
    for x in reversed(pyvals):
        out = Pair(x, out)
    return out

def lisp_to_py(v):
    out = []
    while isinstance(v, Pair):
        out.append(v.car); v = v.cdr
    return out

def deep_py(v):
    if isinstance(v, list):
        return [deep_py(x) for x in v]
    if isinstance(v, Pair):
        return [deep_py(x) for x in lisp_to_py(v)]
    if isinstance(v, Sym):
        return v.name
    return v


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def tokenize(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c == ";":
            while i < n and s[i] != "\n":
                i += 1
        elif c in "()'":
            out.append(c); i += 1
        else:
            j = i
            while j < n and s[j] not in " \t\r\n()';":
                j += 1
            out.append(s[i:j]); i = j
    return out

def parse_all(s):
    toks = tokenize(s); pos = [0]
    def rd():
        t = toks[pos[0]]; pos[0] += 1
        if t == "(":
            lst = []
            while toks[pos[0]] != ")":
                lst.append(rd())
            pos[0] += 1
            return lst
        if t == "'":
            return [Sym("quote"), rd()]
        try:
            return int(t)
        except ValueError:
            return Sym(t)
    forms = []
    while pos[0] < len(toks):
        forms.append(rd())
    return forms


# ---------------------------------------------------------------------------
# Code object
# ---------------------------------------------------------------------------

class Code:
    def __init__(self):
        self.ins = []
        self.consts = []
        self.children = []
        self.nfixed = 0
        self.has_rest = False
        self.params_src = None   # lambda parameter source for decompiler metadata
    def emit(self, *ins):
        self.ins.append(list(ins)); return len(self.ins) - 1
    def addconst(self, v):
        self.consts.append(v); return len(self.consts) - 1
    def addchild(self, c):
        self.children.append(c); return len(self.children) - 1
    def here(self):
        return len(self.ins)


def parse_params(plist):
    fixed, rest, i = [], None, 0
    while i < len(plist):
        if plist[i] is Sym("&rest"):
            rest = plist[i + 1]; break
        fixed.append(plist[i]); i += 1
    return fixed, rest


def to_value(x):
    if isinstance(x, list):
        v = NIL
        for e in reversed(x):
            v = Pair(to_value(e), v)
        return v
    return x


class Compiler:
    def __init__(self, enable_tco=True):
        self.tco = enable_tco

    def compile_program(self, forms):
        top = Code()
        for k, f in enumerate(forms):
            self.expr(f, top, [], tail=False)
            if k != len(forms) - 1:
                top.emit("POP")
        top.emit("HALT")
        return top

    def resolve(self, name, scopes):
        for d, frame in enumerate(scopes):
            if name in frame:
                return d, frame.index(name)
        return None

    def body(self, forms, code, scopes, tail):
        if not forms:
            code.emit("CONST", code.addconst(NIL)); return
        for f in forms[:-1]:
            self.expr(f, code, scopes, tail=False); code.emit("POP")
        self.expr(forms[-1], code, scopes, tail=tail)

    def expr(self, form, code, scopes, tail):
        if isinstance(form, int):
            code.emit("CONST", code.addconst(form)); return
        if isinstance(form, Sym):
            r = self.resolve(form, scopes)
            code.emit("LOADL", r[0], r[1]) if r else code.emit("LOADG", form.name)
            return
        if form is NIL:
            code.emit("CONST", code.addconst(NIL)); return
        if not isinstance(form, list) or not form:
            raise SyntaxError(f"bad form: {form}")

        h = form[0]
        if h is Sym("quote"):
            code.emit("CONST", code.addconst(to_value(form[1]))); return
        if h is Sym("if"):
            self.expr(form[1], code, scopes, False)
            jf = code.emit("JFALSE", None)
            self.expr(form[2], code, scopes, tail)
            jm = code.emit("JMP", None)
            code.ins[jf][1] = code.here()
            if len(form) > 3:
                self.expr(form[3], code, scopes, tail)
            else:
                code.emit("CONST", code.addconst(NIL))
            code.ins[jm][1] = code.here(); return
        if h is Sym("cond"):
            ends = []; saw_else = False
            for clause in form[1:]:
                test, cbody = clause[0], clause[1:]
                if test is Sym("else"):
                    self.body(cbody, code, scopes, tail); saw_else = True; break
                self.expr(test, code, scopes, False)
                jf = code.emit("JFALSE", None)
                self.body(cbody if cbody else [test], code, scopes, tail)
                ends.append(code.emit("JMP", None))
                code.ins[jf][1] = code.here()
            if not saw_else:
                code.emit("CONST", code.addconst(NIL))
            for j in ends:
                code.ins[j][1] = code.here()
            return
        if h is Sym("and"):
            parts = form[1:]
            if not parts:
                code.emit("CONST", code.addconst(True)); return
            ends = []
            for e in parts[:-1]:
                self.expr(e, code, scopes, False)
                code.emit("DUP"); ends.append(code.emit("JFALSE", None)); code.emit("POP")
            self.expr(parts[-1], code, scopes, tail)
            for j in ends:
                code.ins[j][1] = code.here()
            return
        if h is Sym("or"):
            parts = form[1:]
            if not parts:
                code.emit("CONST", code.addconst(NIL)); return
            ends = []
            for e in parts[:-1]:
                self.expr(e, code, scopes, False)
                code.emit("DUP"); ends.append(code.emit("JTRUE", None)); code.emit("POP")
            self.expr(parts[-1], code, scopes, tail)
            for j in ends:
                code.ins[j][1] = code.here()
            return
        if h is Sym("when"):
            self.expr([Sym("if"), form[1], [Sym("begin")] + form[2:]], code, scopes, tail); return
        if h is Sym("unless"):
            self.expr([Sym("if"), form[1], [Sym("quote"), []], [Sym("begin")] + form[2:]],
                      code, scopes, tail); return
        if h is Sym("begin"):
            self.body(form[1:], code, scopes, tail); return
        if h is Sym("lambda"):
            fixed, rest = parse_params(form[1])
            frame = fixed + ([rest] if rest is not None else [])
            child = Code(); child.nfixed = len(fixed); child.has_rest = rest is not None
            child.params_src = form[1]
            self.body(form[2:], child, [frame] + scopes, tail=True)
            child.emit("RET")
            code.emit("CLOSURE", code.addchild(child)); return
        if h is Sym("let"):
            names = [b[0] for b in form[1]]
            inits = [b[1] for b in form[1]]
            self.expr([[Sym("lambda"), names] + form[2:]] + inits, code, scopes, tail); return
        if h is Sym("let*"):
            binds, lbody = form[1], form[2:]
            if not binds:
                self.expr([Sym("begin")] + lbody, code, scopes, tail)
            else:
                inner = [Sym("let*"), binds[1:]] + lbody
                self.expr([Sym("let"), [binds[0]], inner], code, scopes, tail)
            return
        if h is Sym("define"):
            self.expr(form[2], code, scopes, False); code.emit("STOREG", form[1].name); return
        if h is Sym("set!"):
            self.expr(form[2], code, scopes, False)
            r = self.resolve(form[1], scopes)
            code.emit("STOREL", r[0], r[1]) if r else code.emit("STOREG", form[1].name)
            return
        # Call
        self.expr(h, code, scopes, False)
        for a in form[1:]:
            self.expr(a, code, scopes, False)
        n = len(form) - 1
        code.emit("TAILCALL" if (tail and self.tco) else "CALL", n)


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

class VM:
    def __init__(self, g):
        self.g = g; self.ins_count = 0; self.max_call_depth = 0

    def run(self, main, initial_env=None):
        code, pc, env = main, 0, initial_env
        st, cs = [], []
        while True:
            ins = code.ins[pc]; pc += 1; self.ins_count += 1; op = ins[0]
            if op == "CONST":
                st.append(code.consts[ins[1]])
            elif op == "LOADL":
                f = env
                for _ in range(ins[1]):
                    f = f.parent
                st.append(f.slots[ins[2]])
            elif op == "STOREL":
                f = env
                for _ in range(ins[1]):
                    f = f.parent
                f.slots[ins[2]] = st[-1]
            elif op == "LOADG":
                st.append(self.g[ins[1]])
            elif op == "STOREG":
                self.g[ins[1]] = st[-1]
            elif op == "POP":
                st.pop()
            elif op == "DUP":
                st.append(st[-1])
            elif op == "JMP":
                pc = ins[1]
            elif op == "JFALSE":
                if is_false(st.pop()):
                    pc = ins[1]
            elif op == "JTRUE":
                if not is_false(st.pop()):
                    pc = ins[1]
            elif op == "CLOSURE":
                st.append(Closure(code.children[ins[1]], env))
            elif op in ("CALL", "TAILCALL"):
                n = ins[1]
                args = st[len(st) - n:] if n else []
                del st[len(st) - n:]
                callee = st.pop()
                if isinstance(callee, Primitive):
                    st.append(callee.fn(args))
                    if op == "TAILCALL":
                        if not cs:
                            return st[-1]
                        code, pc, env = cs.pop()
                elif isinstance(callee, Closure):
                    cc = callee.code
                    if cc.has_rest:
                        slots = list(args[:cc.nfixed]) + [lisp_list(args[cc.nfixed:])]
                    else:
                        slots = list(args)
                    nf = Frame(slots, callee.env)
                    if op == "CALL":
                        cs.append((code, pc, env))
                        if len(cs) > self.max_call_depth:
                            self.max_call_depth = len(cs)
                        code, pc, env = cc, 0, nf
                    else:
                        code, pc, env = cc, 0, nf
                else:
                    raise TypeError(f"not callable: {callee}")
            elif op == "RET":
                if not cs:
                    return st[-1]
                code, pc, env = cs.pop()
            elif op == "HALT":
                return st[-1] if st else NIL
            else:
                raise RuntimeError(f"bad op {op}")


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _len(v):
    n = 0
    while isinstance(v, Pair):
        n += 1; v = v.cdr
    return n

def _append2(lists):
    if not lists:
        return NIL
    *front, last = lists
    acc = last
    for lst in reversed(front):
        acc = lisp_list(lisp_to_py(lst), acc)
    return acc

def _rev(v):
    out = NIL
    while isinstance(v, Pair):
        out = Pair(v.car, out); v = v.cdr
    return out

def base_globals():
    import math
    def p(fn, nm): return Primitive(fn, nm)
    g = {
        "+": p(lambda a: sum(a), "+"),
        "-": p(lambda a: -a[0] if len(a) == 1 else a[0] - sum(a[1:]), "-"),
        "*": p(lambda a: math.prod(a), "*"),
        "<": p(lambda a: a[0] < a[1], "<"),
        ">": p(lambda a: a[0] > a[1], ">"),
        "<=": p(lambda a: a[0] <= a[1], "<="),
        ">=": p(lambda a: a[0] >= a[1], ">="),
        "=": p(lambda a: a[0] == a[1], "="),
        "not": p(lambda a: True if is_false(a[0]) else False, "not"),
        "eq?": p(lambda a: a[0] is a[1] or (isinstance(a[0], int) and a[0] == a[1]), "eq?"),
        "pair?": p(lambda a: isinstance(a[0], Pair), "pair?"),
        "null?": p(lambda a: a[0] is NIL, "null?"),
        "cons": p(lambda a: Pair(a[0], a[1]), "cons"),
        "car": p(lambda a: a[0].car, "car"),
        "cdr": p(lambda a: a[0].cdr, "cdr"),
        "cadr": p(lambda a: a[0].cdr.car, "cadr"),
        "list": p(lambda a: lisp_list(list(a)), "list"),
        "length": p(lambda a: _len(a[0]), "length"),
        "append": p(lambda a: _append2(list(a)), "append"),
        "reverse": p(lambda a: _rev(a[0]), "reverse"),
    }
    return g

def run_program(src, enable_tco=True):
    code = Compiler(enable_tco).compile_program(parse_all(src))
    vm = VM(base_globals())
    return vm.run(code), vm


# ---------------------------------------------------------------------------
# Disassembler and decompiler for editable function display
# ---------------------------------------------------------------------------

def disasm(code, indent=0):
    pad = "  " * indent
    out = []
    for i, ins in enumerate(code.ins):
        op = ins[0]
        if op == "CONST":
            out.append(f"{pad}{i:3} CONST   {lisp_str(code.consts[ins[1]])}")
        elif op in ("LOADL", "STOREL"):
            out.append(f"{pad}{i:3} {op:7} {ins[1]} {ins[2]}")
        elif op in ("LOADG", "STOREG"):
            out.append(f"{pad}{i:3} {op:7} {ins[1]}")
        elif op in ("CALL", "TAILCALL", "JMP", "JFALSE", "JTRUE"):
            out.append(f"{pad}{i:3} {op:7} {ins[1]}")
        elif op == "CLOSURE":
            ch = code.children[ins[1]]
            out.append(f"{pad}{i:3} CLOSURE #{ins[1]} {lisp_str(ch.params_src)}")
            out.append(disasm(ch, indent + 2))
        else:
            out.append(f"{pad}{i:3} {op}")
    return "\n".join(out)


def lisp_str(v):
    if isinstance(v, list):
        return "(" + " ".join(lisp_str(x) for x in v) + ")"
    return str(v)


class DecompileError(Exception):
    pass

def frame_names(params_src):
    out, i = [], 0
    while i < len(params_src):
        if params_src[i] is Sym("&rest"):
            out.append(params_src[i + 1]); break
        out.append(params_src[i]); i += 1
    return out

def quote_const(v):
    if isinstance(v, int) or v is True or v is NIL:
        return v
    if isinstance(v, Sym):
        return [Sym("quote"), v]
    return [Sym("quote"), v]

def decompile_body(code, scopes):
    # Reconstruct a source S-expression from straight-line bytecode. Control flow raises
    # DecompileError.
    st = []
    for ins in code.ins:
        op = ins[0]
        if op == "CONST":
            st.append(quote_const(code.consts[ins[1]]))
        elif op == "LOADL":
            st.append(scopes[ins[1]][ins[2]])
        elif op == "LOADG":
            st.append(Sym(ins[1]))
        elif op == "CLOSURE":
            ch = code.children[ins[1]]
            inner = decompile_body(ch, [frame_names(ch.params_src)] + scopes)
            st.append([Sym("lambda"), ch.params_src, inner])
        elif op in ("CALL", "TAILCALL"):
            n = ins[1]
            args = st[len(st) - n:] if n else []
            del st[len(st) - n:]
            callee = st.pop()
            st.append([callee] + args)
        elif op in ("RET", "HALT"):
            break
        else:
            raise DecompileError(op)
    if len(st) != 1:
        raise DecompileError("stack not single")
    return st[0]

def decompile(src):
    # src is one top-level lambda. Return the reconstructed form or ('disasm', listing).
    code = Compiler().compile_program(parse_all(src))
    try:
        return decompile_body(code, [])
    except DecompileError:
        return ("disasm", disasm(code))


# ---------------------------------------------------------------------------
# Heap-frame allocator and GC-root host oracle
#
# Pin executable semantics for heap-resident frames: parent handles, depth walks, closure-held GC
# roots, transitive parent reachability, and shared mutable slots that retain identity across a
# stop-the-world collection. This specifies pointer behavior without prescribing a memory layout.
# ---------------------------------------------------------------------------

NULLPTR = 0

class HeapFrame:
    __slots__ = ("addr", "slots", "parent")
    def __init__(self, addr, slots, parent):
        self.addr = addr          # heap handle (>0); 0 == NULLPTR
        self.slots = slots        # list of four-byte values
        self.parent = parent      # parent heap handle or NULLPTR

class FrameHeap:
    # Minimal allocator with explicit handles and parent links. .freed records collected handles.
    def __init__(self):
        self.cells = {}           # addr -> HeapFrame
        self.next = 1             # reserve zero as NULLPTR
        self.freed = []

    def alloc(self, slots, parent=NULLPTR):
        addr = self.next; self.next += 1
        self.cells[addr] = HeapFrame(addr, list(slots), parent)
        return addr

    def deref(self, addr):
        return self.cells[addr]

    def walk(self, addr, depth):
        # depth>0 walks parent handles, matching the native parent-pointer chain.
        f = self.deref(addr)
        for _ in range(depth):
            assert f.parent != NULLPTR, "Parent-Walk laeuft in NULLPTR"
            f = self.deref(f.parent)
        return f

    def loadl(self, addr, depth, idx):
        return self.walk(addr, depth).slots[idx]

    def storel(self, addr, depth, idx, value):
        self.walk(addr, depth).slots[idx] = value

    def collect(self, root_addrs):
        # Stop-the-world mark/sweep from frame handles retained by escaped closures. Mark parent
        # chains transitively and collect everything else.
        marked = set()
        stack = [a for a in root_addrs if a != NULLPTR]
        while stack:
            a = stack.pop()
            if a in marked:
                continue
            marked.add(a)
            p = self.deref(a).parent
            if p != NULLPTR and p not in marked:
                stack.append(p)
        dead = {a for a in self.cells if a not in marked}
        for a in dead:
            del self.cells[a]
            self.freed.append(a)
        return marked, dead

class HeapClosure:
    # Closure object = child code index + heap-frame handle serving as the GC root.
    __slots__ = ("child", "frame")
    def __init__(self, child, frame):
        self.child = child
        self.frame = frame


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def report(label, ok):
    print(f"  [{'OK ' if ok else 'XX '}] {label}"); return ok

def main():
    allok = True

    print("== 1. Kern: Arithmetik, if, Rekursion ==")
    allok &= report("(+ 1 2 3) = 6", run_program("(+ 1 2 3)")[0] == 6)
    allok &= report("(if (< 2 3) 10 20) = 10", run_program("(if (< 2 3) 10 20)")[0] == 10)
    allok &= report("(fact 5) = 120", run_program(
        "(define fact (lambda (n)(if (= n 0) 1 (* n (fact (- n 1)))))) (fact 5)")[0] == 120)

    print("\n== 2. Closures ==")
    allok &= report("Capture: ((λx.λy.x+y) 3) 4 = 7",
                    run_program("(((lambda (x)(lambda (y)(+ x y))) 3) 4)")[0] == 7)
    allok &= report("Capture kommutativ: ((λx.λy.y+x) 3) 4 = 7",
                    run_program("(((lambda (x)(lambda (y)(+ y x))) 3) 4)")[0] == 7)
    allok &= report("Capture geordnet: ((λx.λy.x-y) 7) 4 = 3",
                    run_program("(((lambda (x)(lambda (y)(- x y))) 7) 4)")[0] == 3)
    allok &= report("Capture geordnet vertauscht: ((λx.λy.y-x) 7) 4 = -3",
                    run_program("(((lambda (x)(lambda (y)(- y x))) 7) 4)")[0] == -3)
    cnt = run_program("(define mk (lambda ()(let ((n 0))(lambda ()(set! n (+ n 1)) n))))"
                      "(define c (mk))(define c2 (mk))(c)(c)(list (c)(c2)(c))")[0]
    allok &= report(f"Counter (list (c)(c2)(c)) = {lisp_to_py(cnt)}", lisp_to_py(cnt) == [3, 1, 4])
    # Shared mutable frame: two closures from one constructor share n by reference.
    sh = run_program("(define mk (lambda ()(let ((n 0))"
                     "  (cons (lambda ()(set! n (+ n 1)) n)(lambda () n)))))"
                     "(define p (mk))(define inc (car p))(define get (cdr p))"
                     "(inc)(inc)(inc)(get)")[0]
    allok &= report(f"Geteilter Frame: inc x3, dann get = {sh}", sh == 3)
    # Depth-3 capture: z frame -> y parent -> x grandparent.
    d3 = run_program("(define f (lambda (x)(lambda (y)(lambda (z)(+ x y z)))))"
                     "(((f 1) 2) 3)")[0]
    allok &= report(f"depth-3 Capture (((f 1) 2) 3) = {d3}", d3 == 6)

    print("\n== 3. cond / and / or / when / unless / let* ==")
    allok &= report("cond -> b", run_program("(cond ((< 2 1) 'a)((< 1 2) 'b)(else 'c))")[0] is Sym("b"))
    allok &= report("(and (< 1 2) 5) = 5", run_program("(and (< 1 2) 5)")[0] == 5)
    allok &= report("(and (< 2 1) 5) = falsch", is_false(run_program("(and (< 2 1) 5)")[0]))
    allok &= report("(or (< 2 1) 7) = 7", run_program("(or (< 2 1) 7)")[0] == 7)
    allok &= report("(when (< 1 2) 10) = 10", run_program("(when (< 1 2) 10)")[0] == 10)
    allok &= report("(unless (< 2 1) 11) = 11", run_program("(unless (< 2 1) 11)")[0] == 11)
    allok &= report("(let* ((a 2)(b (+ a 3)))(+ a b)) = 7",
                    run_program("(let* ((a 2)(b (+ a 3)))(+ a b))")[0] == 7)

    print("\n== 4. &rest-Parameter ==")
    fr = deep_py(run_program("(define f (lambda (a b &rest r)(list a b r)))(f 1 2 3 4)")[0])
    allok &= report(f"(f 1 2 3 4) = {fr}", fr == [1, 2, [3, 4]])
    g = run_program("(define g (lambda (&rest xs) xs))(g 1 2 3)")[0]
    allok &= report(f"(g 1 2 3) = {lisp_to_py(g)}", lisp_to_py(g) == [1, 2, 3])

    print("\n== 5. Ausdrucksstärke: map + tail-rekursives foldl ==")
    m = run_program(
        "(define map (lambda (f xs)(cond ((null? xs) '())(else (cons (f (car xs))(map f (cdr xs)))))))"
        "(define sq (lambda (x)(* x x)))(map sq (list 1 2 3 4))")[0]
    allok &= report(f"(map sq '(1 2 3 4)) = {lisp_to_py(m)}", lisp_to_py(m) == [1, 4, 9, 16])
    fo, _ = run_program(
        "(define foldl (lambda (f acc xs)(cond ((null? xs) acc)(else (foldl f (f acc (car xs))(cdr xs))))))"
        "(foldl + 0 (list 1 2 3 4 5))")
    allok &= report(f"(foldl + 0 '(1..5)) = {fo}", fo == 15)

    print("\n== 6. TCO durch cond (endrekursive Schleife) ==")
    v, vm = run_program(
        "(define sumto (lambda (n acc)(cond ((= n 0) acc)(else (sumto (- n 1)(+ acc n))))))"
        "(sumto 5000 0)", enable_tco=True)
    allok &= report(f"(sumto 5000 0) = {v}, max Aufruf-Stack = {vm.max_call_depth}",
                    v == 12502500 and vm.max_call_depth <= 2)

    print("\n== 7. Decompiler (Bytecode -> editierbare Form) ==")
    d1 = decompile("(lambda (x) (+ x 1))")
    allok &= report(f"decompile (λx.x+1) = {deep_py(d1)}",
                    deep_py(d1) == ["lambda", ["x"], ["+", "x", 1]])
    d2 = decompile("(lambda (x) (lambda (y) (+ x y)))")
    allok &= report(f"decompile geschachtelt = {deep_py(d2)}",
                    deep_py(d2) == ["lambda", ["x"], ["lambda", ["y"], ["+", "x", "y"]]])
    d3 = decompile("(lambda (n) (cons n (g n)))")
    allok &= report(f"decompile mit Aufruf = {deep_py(d3)}",
                    deep_py(d3) == ["lambda", ["n"], ["cons", "n", ["g", "n"]]])
    d4 = decompile("(lambda (n) (if (= n 0) 1 n))")
    allok &= report("Kontrollfluss -> Disassembly-Fallback (enthält JFALSE)",
                    isinstance(d4, tuple) and d4[0] == "disasm" and "JFALSE" in d4[1])

    print("\n== 8. Frame Value V0: depth-0 LOADL/STOREL ==")
    load_code = Code()
    load_code.emit("LOADL", 0, 0)
    load_code.emit("RET")
    load_env = Frame([42], None)
    allok &= report("LOADL 0 0 liest lokalen 4-Byte-Value-Slot",
                    VM({}).run(load_code, load_env) == 42)

    store_code = Code()
    store_code.emit("CONST", store_code.addconst(99))
    store_code.emit("STOREL", 0, 1)
    store_code.emit("LOADL", 0, 1)
    store_code.emit("RET")
    store_env = Frame([0, 0], None)
    store_result = VM({}).run(store_code, store_env)
    allok &= report("STOREL 0 1 schreibt und LOADL liest denselben Slot",
                    store_result == 99 and store_env.slots[1] == 99)

    print("\n== 9. Heap-Frame-Allokator + GC-Root V0 (naechster nativer Schritt) ==")
    # (a) Allocator and parent walk: grandparent x=1, parent y=2, child z=3.
    h = FrameHeap()
    gx = h.alloc([1], NULLPTR)
    py = h.alloc([2], gx)
    cz = h.alloc([3], py)
    allok &= report("Parent-Walk: LOADL depth=2 vom Child liest x=1",
                    h.loadl(cz, 2, 0) == 1)
    allok &= report("Parent-Walk: LOADL depth=1 vom Child liest y=2",
                    h.loadl(cz, 1, 0) == 2 and h.loadl(cz, 0, 0) == 3)

    # (b) A shared mutable frame keeps identity and visible write-through across collection.
    #     (let ((n 0)) (cons (lambda ()(set! n (+ n 1)) n) (lambda () n)))
    h2 = FrameHeap()
    shared = h2.alloc([0], NULLPTR)
    inc = HeapClosure(child=0, frame=shared)
    get = HeapClosure(child=1, frame=shared)
    for _ in range(3):                       # inc x3 schreibt in den GETEILTEN Slot
        h2.storel(inc.frame, 0, 0, h2.loadl(inc.frame, 0, 0) + 1)
    marked, dead = h2.collect({inc.frame, get.frame})   # Wurzeln = erreichbare Closures
    allok &= report("Geteilter Frame ueberlebt GC (in Wurzelmenge, nicht gesammelt)",
                    shared in marked and shared not in dead)
    allok &= report("get sieht nach GC denselben write-through Wert (=3), gleiche Identitaet",
                    h2.loadl(get.frame, 0, 0) == 3 and inc.frame == get.frame)

    # (c) A non-escaped frame is collected without leaking.
    h3 = FrameHeap()
    keep = h3.alloc([7], NULLPTR)
    tmp = h3.alloc([8], NULLPTR)             # niemand haelt tmp
    esc = HeapClosure(child=0, frame=keep)
    m3, d3 = h3.collect({esc.frame})
    allok &= report("Nicht-erreichbarer Frame wird gesammelt (kein Leak)",
                    tmp in d3 and keep in m3 and tmp in h3.freed)

    # (d) An escaped child transitively keeps its otherwise-unrooted parent alive.
    h4 = FrameHeap()
    par = h4.alloc([5], NULLPTR)
    chi = h4.alloc([6], par)
    other = h4.alloc([9], NULLPTR)           # unbeteiligt -> sammelbar
    escc = HeapClosure(child=0, frame=chi)
    m4, d4 = h4.collect({escc.frame})
    allok &= report("Escaped Child haelt Parent transitiv am Leben",
                    par in m4 and chi in m4 and other in d4)

    print()
    print("ERGEBNIS:", "ALLES OK" if allok else "FEHLER")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
