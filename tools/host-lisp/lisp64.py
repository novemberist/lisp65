#!/usr/bin/env python3
"""Host reference interpreter for the historical LISP 64 dialect.

It models language semantics so preludes, libraries, conformance tests, and
benchmarks can iterate without VICE. It is not an emulator substitute: ROM,
memory, GC, timing, five-byte cells, banking, and machine I/O are outside the
model, and physical C64 behavior remains authoritative.

Symbols are uppercased, NIL is the only false value, integers wrap as signed
32-bit values, and scope is dynamically shallow-bound. Lambda supports spread
and nospread conventions; missing parameters bind to NIL. DE is EXPR, DF is
FEXPR, and DM is MACRO.
"""

import sys
import random

MASK32 = 0xFFFFFFFF


def to_int32(n):
    n &= MASK32
    if n >= 0x80000000:
        n -= 0x100000000
    return n


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Symbol:
    __slots__ = ("name", "value", "func", "plist", "bound")

    def __init__(self, name):
        self.name = name
        self.value = None
        self.bound = False        # is the value cell bound?
        self.func = None          # Funktionsdefinition (EXPR/FEXPR/MACRO/builtin)
        self.plist = {}           # property list

    def __repr__(self):
        return self.name


class Pair:
    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr


class Str:
    __slots__ = ("s",)

    def __init__(self, s):
        self.s = s

    def __eq__(self, other):
        return isinstance(other, Str) and other.s == self.s

    def __hash__(self):
        return hash(self.s)


class Closure:
    """Benutzerfunktion: kind in {EXPR, FEXPR, MACRO}."""
    __slots__ = ("kind", "params", "body", "name")

    def __init__(self, kind, params, body, name="LAMBDA"):
        self.kind = kind
        self.params = params
        self.body = body
        self.name = name


class Builtin:
    __slots__ = ("fn", "special", "name")

    def __init__(self, fn, special, name):
        self.fn = fn
        self.special = special   # special means arguments are not evaluated first
        self.name = name


class LispError(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class GoSignal(Exception):
    def __init__(self, tag):
        self.tag = tag


class Condition:
    """Typisierte Condition: ctype (Symbol) + message (str) + data (Lisp-Wert)."""
    __slots__ = ("ctype", "message", "data")

    def __init__(self, ctype, message, data):
        self.ctype = ctype
        self.message = message
        self.data = data


class ConditionSignal(Exception):
    """Signal a condition from ERROR, SIGNAL, or an internal error."""
    def __init__(self, cond):
        self.cond = cond


class ThrowSignal(Exception):
    """Non-local CATCH/THROW transfer with an EQ-comparable tag."""
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value


# ---------------------------------------------------------------------------
# Symbol table
# ---------------------------------------------------------------------------

SYMTAB = {}


def intern(name):
    s = SYMTAB.get(name)
    if s is None:
        s = Symbol(name)
        SYMTAB[name] = s
    return s


NIL = intern("NIL")
T = intern("T")
# F is the dialect's predefined false atom, equivalent to NIL.
_F = intern("F")
_F.value = NIL
_F.bound = True


def is_nil(x):
    return x is NIL


def truthy(x):
    return x is not NIL


def from_bool(b):
    return T if b else NIL


# List helpers
def cons(a, d):
    return Pair(a, d)


def py_to_list(seq, tail=NIL):
    out = tail
    for x in reversed(seq):
        out = Pair(x, out)
    return out


def list_to_py(x):
    out = []
    while isinstance(x, Pair):
        out.append(x.car)
        x = x.cdr
    return out


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class Reader:
    def __init__(self, text):
        self.text = text
        self.i = 0
        self.n = len(text)

    def peek(self):
        return self.text[self.i] if self.i < self.n else ""

    def next(self):
        c = self.text[self.i]
        self.i += 1
        return c

    def skip_ws(self):
        while self.i < self.n:
            c = self.text[self.i]
            if c == ";":
                while self.i < self.n and self.text[self.i] != "\n":
                    self.i += 1
            elif c in " \t\r\n":
                self.i += 1
            else:
                break

    def read(self):
        self.skip_ws()
        if self.i >= self.n:
            return None, False
        c = self.peek()
        if c == "(":
            self.next()
            return self.read_list(), True
        if c == ")":
            raise LispError("unerwartete )")
        if c == "'":
            self.next()
            form, ok = self.read()
            if not ok:
                raise LispError("' ohne Form")
            return py_to_list([intern("QUOTE"), form]), True
        if c == "`":
            # Quasiquote needs a replacement character on a real C64 because PETSCII has no backtick.
            self.next()
            form, ok = self.read()
            if not ok:
                raise LispError("` ohne Form")
            return py_to_list([intern("QUASIQUOTE"), form]), True
        if c == ",":
            self.next()
            if self.peek() == "@":
                self.next()
                form, ok = self.read()
                return py_to_list([intern("UNQUOTE-SPLICING"), form]), True
            form, ok = self.read()
            return py_to_list([intern("UNQUOTE"), form]), True
        if c == '"':
            return self.read_string(), True
        return self.read_atom(), True

    def read_list(self):
        items = []
        tail = NIL
        while True:
            self.skip_ws()
            if self.i >= self.n:
                raise LispError("unvollstaendige Liste")
            c = self.peek()
            if c == ")":
                self.next()
                break
            if c == "." and self.i + 1 < self.n and self.text[self.i + 1] in " \t\r\n":
                self.next()
                tail, _ = self.read()
                self.skip_ws()
                if self.peek() != ")":
                    raise LispError("schlecht geformtes Punkt-Paar")
                self.next()
                break
            form, _ = self.read()
            items.append(form)
        return py_to_list(items, tail)

    def read_string(self):
        self.next()  # opening quote
        buf = []
        while self.i < self.n:
            c = self.next()
            if c == '"':
                return Str("".join(buf))
            buf.append(c)
        raise LispError("unvollstaendiger String")

    def read_atom(self):
        buf = []
        while self.i < self.n:
            c = self.text[self.i]
            if c in " \t\r\n()'\";`,":
                break
            buf.append(c)
            self.i += 1
        token = "".join(buf)
        # Integer?
        if self._is_int(token):
            return to_int32(int(token))
        return intern(token.upper())

    @staticmethod
    def _is_int(tok):
        if not tok:
            return False
        body = tok[1:] if tok[0] in "+-" else tok
        return body.isdigit() and body != ""


def read_all(text):
    r = Reader(text)
    forms = []
    while True:
        form, ok = r.read()
        if not ok:
            break
        forms.append(form)
    return forms


# ---------------------------------------------------------------------------
# Printer
# ---------------------------------------------------------------------------

def lisp_repr(x, readable=True):
    if x is NIL:
        return "NIL"
    if isinstance(x, Symbol):
        return x.name
    if isinstance(x, int):
        return str(x)
    if isinstance(x, Str):
        return '"' + x.s + '"' if readable else x.s
    if isinstance(x, Pair):
        if (isinstance(x.car, Symbol) and x.car.name == "QUOTE"
                and isinstance(x.cdr, Pair) and x.cdr.cdr is NIL):
            return "'" + lisp_repr(x.cdr.car, readable)
        parts = []
        cur = x
        while isinstance(cur, Pair):
            parts.append(lisp_repr(cur.car, readable))
            cur = cur.cdr
        if cur is NIL:
            return "(" + " ".join(parts) + ")"
        return "(" + " ".join(parts) + " . " + lisp_repr(cur, readable) + ")"
    if isinstance(x, (Closure, Builtin)):
        return "#<" + getattr(x, "name", "FN") + ">"
    if isinstance(x, Condition):
        return "#<CONDITION " + x.ctype.name + ": " + x.message + ">"
    return str(x)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def lisp_eval(form):
    if isinstance(form, Symbol):
        if form is NIL or form is T:
            return form
        if form.name.startswith(":"):     # Keyword-Literal -> selbstauswertend
            return form
        if not form.bound:
            raise LispError("unbound variable: " + form.name)
        return form.value
    if isinstance(form, (int, Str)):
        return form
    if not isinstance(form, Pair):
        return form

    head = form.car
    args = form.cdr

    # Resolve operator.
    fn = resolve_function(head)
    if fn is None:
        raise LispError("undefined function: " + lisp_repr(head))

    if isinstance(fn, Builtin):
        if fn.special:
            return fn.fn(args)
        argv = [lisp_eval(a) for a in list_to_py(args)]
        return fn.fn(argv)

    if isinstance(fn, Closure):
        if fn.kind == "CLMACRO":
            # CL-style DEFMACRO: spread parameters bind unevaluated operand forms; the body returns
            # the expansion that is evaluated afterward.
            expansion = run_bindings(fn, list_to_py(args))
            return lisp_eval(expansion)
        return apply_closure(fn, args, eval_args=(fn.kind == "EXPR"), whole_form=form)

    raise LispError("nicht aufrufbar: " + lisp_repr(head))


DEF_KEYS = (("EXPR", "EXPR"), ("FEXPR", "FEXPR"), ("MACRO", "MACRO"),
            ("CLMACRO", "CLMACRO"))


def build_def_closure(x, kind):
    # x is the stored definition list (NAME params . body). Rebuild it on each call so TRACE
    # mutations remain visible.
    params = x.cdr.car
    body = list_to_py(x.cdr.cdr)
    name = x.car.name if isinstance(x.car, Symbol) else "FN"
    return Closure(kind, params, body, name)


def resolve_function(head):
    if isinstance(head, Symbol):
        if isinstance(head.func, (Builtin, Closure)):
            return head.func
        # User definitions remain introspectable on the plist under EXPR/FEXPR/MACRO.
        for key, kind in DEF_KEYS:
            x = head.plist.get(key)
            if isinstance(x, Pair):
                return build_def_closure(x, kind)
        return None
    if isinstance(head, Pair):
        # (LAMBDA ...), (NLAMBDA ...), or (LABEL ...) as operator.
        op = head.car
        if isinstance(op, Symbol):
            if op.name in ("LAMBDA",):
                return make_closure("EXPR", head.cdr)
            if op.name in ("NLAMBDA", "FLAMBDA"):
                return make_closure("FEXPR", head.cdr)
            if op.name == "LABEL":
                # (LABEL NAME (LAMBDA ...))
                items = list_to_py(head.cdr)
                name, lam = items[0], items[1]
                clo = resolve_function(lam)
                if isinstance(name, Symbol):
                    name.func = clo
                    clo.name = name.name
                return clo
        # Evaluate the operator form.
        val = lisp_eval(head)
        return val if isinstance(val, (Closure, Builtin)) else None
    return None


def make_closure(kind, rest):
    items = list_to_py(rest)
    params = items[0] if items else NIL
    body = items[1:]
    return Closure(kind, params, body)


def apply_closure(clo, args, eval_args, whole_form=None):
    if clo.kind == "MACRO":
        # Bind the formal to the complete call form, then evaluate the expansion.
        expansion = run_bindings(clo, [whole_form], single_whole=True)
        return lisp_eval(expansion)

    raw = list_to_py(args)
    if eval_args:
        actuals = [lisp_eval(a) for a in raw]
    else:
        actuals = raw
    return run_bindings(clo, actuals)


def run_bindings(clo, actuals, single_whole=False):
    saved = []
    params = clo.params
    try:
        if single_whole:
            # MACRO binds its single formal, either a nospread symbol or one-element formal list,
            # to the complete call form.
            whole = actuals[0]
            if isinstance(params, Symbol) and params is not NIL:
                _bind(params, whole, saved)
            else:
                formals = list_to_py(params)
                if formals and isinstance(formals[0], Symbol):
                    _bind(formals[0], whole, saved)
        elif isinstance(params, Symbol) and params is not NIL:
            # Nospread binds the complete argument list to one symbol.
            _bind(params, py_to_list(actuals), saved)
        else:
            formals = list_to_py(params)
            for idx, p in enumerate(formals):
                if not isinstance(p, Symbol):
                    continue
                val = actuals[idx] if idx < len(actuals) else NIL
                _bind(p, val, saved)
        result = NIL
        for b in clo.body:
            result = lisp_eval(b)
        return result
    finally:
        for sym, had, old in reversed(saved):
            sym.bound = had
            sym.value = old


def _bind(sym, value, saved):
    saved.append((sym, sym.bound, sym.value))
    sym.bound = True
    sym.value = value


def apply_fn(fn, actuals):
    """Apply fn to arguments that have already been evaluated."""
    if isinstance(fn, Symbol):
        resolved = resolve_function(fn)
        if resolved is not None:
            fn = resolved
    elif isinstance(fn, Pair):
        # (LAMBDA ...), (NLAMBDA ...), or (LABEL ...) as a function value.
        resolved = resolve_function(fn)
        if resolved is not None:
            fn = resolved
    if isinstance(fn, Builtin):
        if fn.special:
            return fn.fn(py_to_list(actuals))
        return fn.fn(list(actuals))
    if isinstance(fn, Closure):
        return run_bindings(fn, list(actuals))
    raise LispError("APPLY: nicht aufrufbar: " + lisp_repr(fn))


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def reg(name, special=False):
    def deco(f):
        sym = intern(name)
        sym.func = Builtin(f, special, name)
        return f
    return deco


def need_int(x):
    if not isinstance(x, int):
        raise LispError("Zahl erwartet: " + lisp_repr(x))
    return x


def need_str(x):
    if not isinstance(x, Str):
        raise LispError("String erwartet: " + lisp_repr(x))
    return x


# --- Lists and pairs ---
@reg("CAR")
def _car(a):
    x = a[0]
    return x.car if isinstance(x, Pair) else NIL

@reg("CDR")
def _cdr(a):
    x = a[0]
    return x.cdr if isinstance(x, Pair) else NIL

@reg("CONS")
def _cons(a):
    return cons(a[0], a[1])

@reg("CADR")
def _cadr(a):
    return _car([_cdr([a[0]])])

@reg("CDDR")
def _cddr(a):
    return _cdr([_cdr([a[0]])])

@reg("CAAR")
def _caar(a):
    return _car([_car([a[0]])])

@reg("CDAR")
def _cdar(a):
    return _cdr([_car([a[0]])])

@reg("LIST")
def _list(a):
    return py_to_list(a)

@reg("LENGTH")
def _length(a):
    return to_int32(len(list_to_py(a[0])))

@reg("REVERSE")
def _reverse(a):
    return py_to_list(list(reversed(list_to_py(a[0]))))

@reg("APPEND")
def _append(a):
    if not a:
        return NIL
    *front, last = a
    items = []
    for lst in front:
        items.extend(list_to_py(lst))
    return py_to_list(items, last)

@reg("COPY")
def _copy(a):
    def deep(x):
        return cons(deep(x.car), deep(x.cdr)) if isinstance(x, Pair) else x
    return deep(a[0])

@reg("NTH")
def _nth(a):
    # Dialect NTH is one-based nthcdr: (NTH '(A B C D) 3) = (C D).
    lst, n = a[0], need_int(a[1])
    for _ in range(max(0, n - 1)):
        lst = lst.cdr if isinstance(lst, Pair) else NIL
    return lst

@reg("LAST")
def _last(a):
    # Dialect semantics return the final element, not CL's final cons cell.
    x = a[0]
    if not isinstance(x, Pair):
        return NIL
    while isinstance(x.cdr, Pair):
        x = x.cdr
    return x.car

@reg("MEMBER")
def _member(a):
    item, lst = a[0], a[1]
    while isinstance(lst, Pair):
        if lisp_equal(item, lst.car):
            return lst
        lst = lst.cdr
    return NIL

@reg("ASSOC")
def _assoc(a):
    # ASSOC compares with EQ; SASSOC uses EQUAL.
    key, alist = a[0], a[1]
    while isinstance(alist, Pair):
        pair = alist.car
        if isinstance(pair, Pair) and lisp_eq(pair.car, key):
            return pair
        alist = alist.cdr
    return NIL

@reg("SASSOC")
def _sassoc(a):
    # SASSOC compares with EQUAL.
    key, alist = a[0], a[1]
    while isinstance(alist, Pair):
        pair = alist.car
        if isinstance(pair, Pair) and lisp_equal(pair.car, key):
            return pair
        alist = alist.cdr
    return NIL

@reg("RPLACA")
def _rplaca(a):
    p = a[0]
    if not isinstance(p, Pair):
        raise LispError("RPLACA: kein Paar")
    p.car = a[1]
    return p

@reg("RPLACD")
def _rplacd(a):
    p = a[0]
    if not isinstance(p, Pair):
        raise LispError("RPLACD: kein Paar")
    p.cdr = a[1]
    return p

@reg("NCONC")
def _nconc(a):
    result = NIL
    last_pair = None
    for lst in a:
        if lst is NIL:
            continue
        if result is NIL:
            result = lst
        elif last_pair is not None:
            last_pair.cdr = lst
        if isinstance(lst, Pair):
            p = lst
            while isinstance(p.cdr, Pair):
                p = p.cdr
            last_pair = p
    return result

@reg("NCONC1")
def _nconc1(a):
    return _nconc([a[0], cons(a[1], NIL)])

@reg("REMOVE")
def _remove(a):
    # Non-destructively remove every EQUAL occurrence.
    x, lst = a[0], a[1]
    out = [e for e in list_to_py(lst) if not lisp_equal(x, e)]
    return py_to_list(out)


# --- Predicates ---
@reg("ATOM")
def _atom(a):
    return from_bool(not isinstance(a[0], Pair))

@reg("CONSP")
def _consp(a):
    return from_bool(isinstance(a[0], Pair))

@reg("NULL")
def _null(a):
    return from_bool(a[0] is NIL)

@reg("NOT")
def _not(a):
    return from_bool(a[0] is NIL)

@reg("NUMBERP")
def _numberp(a):
    return from_bool(isinstance(a[0], int))

@reg("STRINGP")
def _stringp(a):
    return from_bool(isinstance(a[0], Str))

@reg("STRING->LIST")
def _string_to_list(a):
    s = need_str(a[0]).s
    return py_to_list([ord(ch) for ch in s])

@reg("LIST->STRING")
def _list_to_string(a):
    chars = []
    lst = a[0]
    while isinstance(lst, Pair):
        code = need_int(lst.car)
        if code < 0 or code > 255:
            raise LispError("Zeichencode ausserhalb 0..255: " + str(code))
        chars.append(chr(code))
        lst = lst.cdr
    if lst is not NIL:
        raise LispError("LIST->STRING: proper list erwartet")
    return Str("".join(chars))

@reg("STRING-LENGTH")
def _string_length(a):
    return to_int32(len(need_str(a[0]).s))

@reg("STRING-REF")
def _string_ref(a):
    s = need_str(a[0]).s
    i = need_int(a[1])
    if i < 0 or i >= len(s):
        raise LispError("STRING-REF: Index ausserhalb")
    return ord(s[i])

@reg("ZEROP")
def _zerop(a):
    return from_bool(isinstance(a[0], int) and a[0] == 0)

@reg("MINUSP")
def _minusp(a):
    return from_bool(isinstance(a[0], int) and a[0] < 0)

@reg("EQ")
def _eq(a):
    return from_bool(lisp_eq(a[0], a[1]))

@reg("EQL")
def _eql(a):
    return from_bool(lisp_eq(a[0], a[1]))

@reg("EQUAL")
def _equal(a):
    return from_bool(lisp_equal(a[0], a[1]))


def lisp_eq(x, y):
    if x is y:
        return True
    if isinstance(x, int) and isinstance(y, int):
        return x == y
    return False


def lisp_equal(x, y):
    if lisp_eq(x, y):
        return True
    if isinstance(x, Str) and isinstance(y, Str):
        return x.s == y.s
    if isinstance(x, Pair) and isinstance(y, Pair):
        return lisp_equal(x.car, y.car) and lisp_equal(x.cdr, y.cdr)
    return False


# --- Signed 32-bit arithmetic ---
@reg("PLUS")
def _plus(a):
    return to_int32(sum(need_int(x) for x in a))

@reg("DIFFERENCE")
def _difference(a):
    if not a:
        return 0
    acc = need_int(a[0])
    for x in a[1:]:
        acc -= need_int(x)
    return to_int32(acc)

@reg("TIMES")
def _times(a):
    acc = 1
    for x in a:
        acc *= need_int(x)
    return to_int32(acc)

@reg("QUOTIENT")
def _quotient(a):
    acc = need_int(a[0])
    for x in a[1:]:
        d = need_int(x)
        if d == 0:
            raise LispError("Division durch 0")
        acc = int(acc / d) if (acc < 0) ^ (d < 0) else acc // d
    return to_int32(acc)

@reg("REMAINDER")
def _remainder(a):
    n, d = need_int(a[0]), need_int(a[1])
    if d == 0:
        raise LispError("Division durch 0")
    r = abs(n) % abs(d)
    return to_int32(-r if n < 0 else r)

@reg("MINUS")
def _minus(a):
    return to_int32(-need_int(a[0]))

@reg("ABS")
def _abs(a):
    return to_int32(abs(need_int(a[0])))

@reg("ADD1")
def _add1(a):
    return to_int32(need_int(a[0]) + 1)

@reg("SUB1")
def _sub1(a):
    return to_int32(need_int(a[0]) - 1)

@reg("LESSP")
def _lessp(a):
    return from_bool(need_int(a[0]) < need_int(a[1]))

@reg("GREATERP")
def _greaterp(a):
    return from_bool(need_int(a[0]) > need_int(a[1]))

@reg("LOGAND")
def _logand(a):
    acc = MASK32
    for x in a:
        acc &= need_int(x) & MASK32
    return to_int32(acc)

@reg("LOGOR")
def _logor(a):
    acc = 0
    for x in a:
        acc |= need_int(x) & MASK32
    return to_int32(acc)

@reg("LOGXOR")
def _logxor(a):
    acc = 0
    for x in a:
        acc ^= need_int(x) & MASK32
    return to_int32(acc)

@reg("LBYTE")
def _lbyte(a):
    return need_int(a[0]) & 0xFF

@reg("HBYTE")
def _hbyte(a):
    return (need_int(a[0]) >> 8) & 0xFF

@reg("COMPL")
def _compl(a):
    return to_int32(~need_int(a[0]))


# --- Symbols, values, and properties ---
@reg("SET")
def _set(a):
    sym = a[0]
    if not isinstance(sym, Symbol):
        raise LispError("SET: kein Symbol")
    sym.value = a[1]
    sym.bound = True
    return a[1]

@reg("VALUE")
def _value(a):
    sym = a[0]
    if isinstance(sym, Symbol) and sym.bound:
        return sym.value
    return NIL

@reg("PUTPROP")
def _putprop(a):
    # Dialect convention: (PUTPROP symbol indicator value)
    sym, key, val = a[0], a[1], a[2]
    sym.plist[key.name if isinstance(key, Symbol) else key] = val
    return val

@reg("DEFPROP", special=True)
def _defprop(args):
    # (DEFPROP symbol indicator value), with unevaluated FEXPR-like arguments.
    items = list_to_py(args)
    sym, key, val = items[0], items[1], items[2]
    sym.plist[key.name if isinstance(key, Symbol) else key] = val
    return sym

@reg("GETPROP")
def _getprop(a):
    sym, key = a[0], a[1]
    if isinstance(sym, Symbol):
        return sym.plist.get(key.name if isinstance(key, Symbol) else key, NIL)
    return NIL

@reg("REMPROP")
def _remprop(a):
    sym, key = a[0], a[1]
    k = key.name if isinstance(key, Symbol) else key
    if isinstance(sym, Symbol) and k in sym.plist:
        del sym.plist[k]
        return T
    return NIL


# --- Higher-order functions ---
@reg("MAPCAR")
def _mapcar(a):
    fn, lst = a[0], a[1]
    return py_to_list([apply_fn(fn, [x]) for x in list_to_py(lst)])

@reg("MAPC")
def _mapc(a):
    # Apply fn to elements for side effects and return NIL.
    fn, lst = a[0], a[1]
    for x in list_to_py(lst):
        apply_fn(fn, [x])
    return NIL

@reg("MAP")
def _map(a):
    # Apply fn to the list and each successive cdr for side effects; return NIL.
    fn, lst = a[0], a[1]
    while isinstance(lst, Pair):
        apply_fn(fn, [lst])
        lst = lst.cdr
    return NIL

@reg("MAPLIST")
def _maplist(a):
    # Like MAP, but collect results, approximately CL maplist.
    fn, lst = a[0], a[1]
    out = []
    while isinstance(lst, Pair):
        out.append(apply_fn(fn, [lst]))
        lst = lst.cdr
    return py_to_list(out)

@reg("MAPCAN")
def _mapcan(a):
    # (APPLY 'NCONC (MAPCAR fn list))
    fn, lst = a[0], a[1]
    results = [apply_fn(fn, [x]) for x in list_to_py(lst)]
    return _nconc(results)

@reg("MAP2CAR")
def _map2car(a):
    fn, l1, l2 = a[0], a[1], a[2]
    out = []
    p1, p2 = l1, l2
    while isinstance(p1, Pair) and isinstance(p2, Pair):
        out.append(apply_fn(fn, [p1.car, p2.car]))
        p1, p2 = p1.cdr, p2.cdr
    return py_to_list(out)

@reg("APPLY")
def _apply(a):
    return apply_fn(a[0], list_to_py(a[1]))

@reg("APPLY*")
def _applystar(a):
    return apply_fn(a[0], a[1:])

@reg("EVAL")
def _eval(a):
    return lisp_eval(a[0])


# --- I/O ---
@reg("PRINT")
def _print(a):
    sys.stdout.write(lisp_repr(a[0], readable=True) + "\n")
    return a[0]

@reg("PRIN1")
def _prin1(a):
    sys.stdout.write(lisp_repr(a[0], readable=True))
    return a[0]

@reg("PRINC")
def _princ(a):
    sys.stdout.write(lisp_repr(a[0], readable=False))
    return a[0]

@reg("TERPRI")
def _terpri(a):
    sys.stdout.write("\n")
    return NIL

@reg("ERROR")
def _error(a):
    # Signal a USER-ERROR condition, catchable by handler-case. A leading symbol selects a
    # condition type; otherwise the type remains USER-ERROR.
    if a and isinstance(a[0], Symbol) and a[0].name.endswith("-ERROR"):
        ctype = a[0]
        rest = a[1:]
    else:
        ctype = intern("USER-ERROR")
        rest = a
    msg = " ".join(lisp_repr(x, readable=False) for x in rest)
    raise ConditionSignal(Condition(ctype, msg, py_to_list(list(rest))))

@reg("MSG")
def _msg(a):
    # Print each argument: T means newline, strings are raw, other values are readable.
    for x in a:
        if x is T:
            sys.stdout.write("\n")
        elif isinstance(x, Str):
            sys.stdout.write(x.s)
        else:
            sys.stdout.write(lisp_repr(x, readable=True))
    return NIL

@reg("SPACES")
def _spaces(a):
    n = need_int(a[0]) if a and isinstance(a[0], int) else 0
    sys.stdout.write(" " * max(0, n))
    return NIL

@reg("WAITCHAR")
def _waitchar(a):
    # No interactive waiting on the host.
    return NIL


# --- String, symbol, and character semantics ---
def _name_of(x):
    if isinstance(x, Symbol):
        return x.name
    if isinstance(x, Str):
        return x.s
    if isinstance(x, int):
        return str(x)
    return lisp_repr(x, readable=False)

@reg("ASC")
def _asc(a):
    # (ASC "A") = 65 -- Code des ersten Zeichens.
    s = _name_of(a[0])
    return ord(s[0]) if s else 0

@reg("CHAR")
def _char(a):
    # (CHAR 65) = "A"
    return Str(chr(need_int(a[0]) & 0xFF))

@reg("PACK")
def _pack(a):
    # (PACK '(A B C D)) = ABCD; any string component makes the result a string.
    items = list_to_py(a[0])
    text = "".join(_name_of(x) for x in items)
    if any(isinstance(x, Str) for x in items):
        return Str(text)
    return intern(text)

@reg("UNPACK")
def _unpack(a):
    # Symbol -> list of one-character symbols; string -> list of one-character strings.
    x = a[0]
    if isinstance(x, Str):
        return py_to_list([Str(c) for c in x.s])
    if isinstance(x, Symbol):
        return py_to_list([intern(c) for c in x.name])
    return NIL

@reg("GETPROPLIST")
def _getproplist(a):
    sym = a[0]
    out = []
    if isinstance(sym, Symbol):
        for k, v in sym.plist.items():
            out.append(intern(k))
            out.append(v)
    return py_to_list(out)

@reg("PRINL")
def _prinl(a):
    # Output without syntax: flat atoms separated by spaces, followed by CR.
    parts = []
    def walk(x):
        if isinstance(x, Pair):
            walk(x.car)
            walk(x.cdr)
        elif x is NIL:
            pass
        else:
            parts.append(lisp_repr(x, readable=False))
    walk(a[0])
    sys.stdout.write(" ".join(parts) + "\n")
    return NIL

@reg("FORMAT")
def _format(a):
    # Core FORMAT subset: (FORMAT control arg...) returns a string like CL (format nil ...).
    # Supports ~A ~S ~D ~X ~C ~% ~~ and minimum widths; iteration directives are intentionally out.
    if not a or not isinstance(a[0], Str):
        raise LispError("FORMAT: Kontrollstring erwartet")
    ctrl = a[0].s
    args = a[1:]
    state = {"ai": 0}

    def next_arg():
        if state["ai"] >= len(args):
            raise LispError("FORMAT: zu wenige Argumente")
        v = args[state["ai"]]
        state["ai"] += 1
        return v

    out = []
    i, n = 0, len(ctrl)
    while i < n:
        c = ctrl[i]
        if c != "~":
            out.append(c)
            i += 1
            continue
        i += 1
        num = ""
        while i < n and ctrl[i].isdigit():
            num += ctrl[i]
            i += 1
        width = int(num) if num else None
        if i >= n:
            raise LispError("FORMAT: Direktive abgeschnitten")
        d = ctrl[i].upper()
        i += 1
        if d == "A":
            s = lisp_repr(next_arg(), readable=False)
            out.append(s.ljust(width) if width else s)
        elif d == "S":
            s = lisp_repr(next_arg(), readable=True)
            out.append(s.ljust(width) if width else s)
        elif d == "D":
            v = next_arg()
            s = str(v) if isinstance(v, int) else lisp_repr(v, False)
            out.append(s.rjust(width) if width else s)
        elif d == "X":
            v = next_arg()
            if isinstance(v, int):
                s = ("-" + format(-v, "X")) if v < 0 else format(v, "X")
            else:
                s = lisp_repr(v, False)
            out.append(s.rjust(width) if width else s)
        elif d == "C":
            v = next_arg()
            if isinstance(v, Str):
                out.append(v.s)
            elif isinstance(v, int):
                out.append(chr(v & 0xFF))
            else:
                out.append(lisp_repr(v, False))
        elif d == "%":
            out.append("\n" * (width or 1))
        elif d == "~":
            out.append("~" * (width or 1))
        else:
            raise LispError("FORMAT: unbekannte Direktive ~" + d)
    return Str("".join(out))

@reg("LINE")
def _line(a):
    return a[0] if a else NIL

@reg("RANDOM")
def _random(a):
    lo, hi = need_int(a[0]), need_int(a[1])
    if hi < lo:
        lo, hi = hi, lo
    return to_int32(random.randint(lo, hi))

@reg("OBLIST")
def _oblist(a):
    return py_to_list([s for s in SYMTAB.values()])

@reg("REMOB")
def _remob(a):
    sym = a[0]
    if isinstance(sym, Symbol) and sym.name in SYMTAB and sym not in (NIL, T):
        del SYMTAB[sym.name]
    return NIL

# Host stubs for I/O, disk, and machine primitives deliberately return NIL so larger samples can
# run without undefined functions. Only VICE can exercise their real behavior.
for _stub in ("READL", "READCH", "GETCHAR", "READ", "OPEN", "CLOSE", "INPUT",
              "OUTPUT", "NORMAL", "LOAD", "SAVE", "DIR", "DISK", "ST", "PEEK",
              "POKE", "CALL", "SYS", "EXIT", "RESET", "TAB", "UNBIND"):
    intern(_stub).func = Builtin(lambda a: NIL, False, _stub)

@reg("GC")
def _gc(a):
    # Real LISP 64 collects and returns the free-node count. The host has no node manager, so 0.
    return 0


# --- Special forms ---
@reg("*", special=True)
def _comment(args):
    # '*' marks comments in this dialect; multiplication is TIMES. Arguments are not evaluated.
    return NIL

@reg("QUOTE", special=True)
def _quote(args):
    return args.car

# Quasiquote builds the runtime structure with UNQUOTE and UNQUOTE-SPLICING. Deep nested
# backquotes are not fully supported by this prototype.
_UNQUOTE = intern("UNQUOTE")
_UNQUOTE_SPLICING = intern("UNQUOTE-SPLICING")

def _qq(x):
    if not isinstance(x, Pair):
        return x
    if x.car is _UNQUOTE:
        return lisp_eval(x.cdr.car)
    return _qq_list(x)

def _qq_list(lst):
    if not isinstance(lst, Pair):
        return lst
    if lst.car is _UNQUOTE:            # (... . ,x) -- gepunktetes Unquote
        return lisp_eval(lst.cdr.car)
    head = lst.car
    if isinstance(head, Pair) and head.car is _UNQUOTE_SPLICING:
        spliced = lisp_eval(head.cdr.car)
        return _append([spliced, _qq_list(lst.cdr)])
    return cons(_qq(head), _qq_list(lst.cdr))

@reg("QUASIQUOTE", special=True)
def _quasiquote(args):
    return _qq(args.car)

@reg("DEFMACRO", special=True)
def _defmacro(args):
    # CL-style DEFMACRO binds spread parameters to unevaluated operand forms and returns expansion.
    return _define(args, "CLMACRO")

def _build_getdef(name):
    # Reconstruct the definition form: (DE|DF|DM NAME params . body).
    if isinstance(name, Symbol):
        for key, deform in (("EXPR", "DE"), ("FEXPR", "DF"), ("MACRO", "DM")):
            x = name.plist.get(key)
            if isinstance(x, Pair):
                return cons(intern(deform), x)
    return NIL

@reg("GETDEF", special=True)
def _getdef(args):
    # (GETDEF NAME): NAME is unevaluated; returns (DF NAME (..) ..).
    return _build_getdef(args.car)

@reg("PDEF", special=True)
def _pdef(args):
    d = _build_getdef(args.car)
    sys.stdout.write(lisp_repr(d, readable=True) + "\n")
    return args.car

@reg("PP", special=True)
def _pp(args):
    return _pdef(args)

@reg("COND", special=True)
def _cond(args):
    clause = args
    while isinstance(clause, Pair):
        cl = clause.car
        test = lisp_eval(cl.car)
        if truthy(test):
            body = cl.cdr
            if body is NIL:
                return test
            result = NIL
            while isinstance(body, Pair):
                result = lisp_eval(body.car)
                body = body.cdr
            return result
        clause = clause.cdr
    return NIL

@reg("AND", special=True)
def _and(args):
    result = T
    while isinstance(args, Pair):
        result = lisp_eval(args.car)
        if result is NIL:
            return NIL
        args = args.cdr
    return result

@reg("OR", special=True)
def _or(args):
    while isinstance(args, Pair):
        result = lisp_eval(args.car)
        if truthy(result):
            return result
        args = args.cdr
    return NIL

@reg("SETQ", special=True)
def _setq(args):
    sym = args.car
    val = lisp_eval(args.cdr.car)
    if not isinstance(sym, Symbol):
        raise LispError("SETQ: kein Symbol")
    sym.value = val
    sym.bound = True
    return val

@reg("PROGN", special=True)
def _progn(args):
    result = NIL
    while isinstance(args, Pair):
        result = lisp_eval(args.car)
        args = args.cdr
    return result

@reg("PROG1", special=True)
def _prog1(args):
    first = lisp_eval(args.car) if isinstance(args, Pair) else NIL
    rest = args.cdr if isinstance(args, Pair) else NIL
    while isinstance(rest, Pair):
        lisp_eval(rest.car)
        rest = rest.cdr
    return first

def _define(args, key):
    # Store the definition as an introspectable (NAME params . body) list under
    # EXPR/FEXPR/MACRO so GETPROP/TRACE can read and mutate it.
    name = args.car
    name.func = None
    name.plist[key] = cons(name, args.cdr)  # (NAME params . body)
    return name

@reg("DE", special=True)
def _de(args):
    return _define(args, "EXPR")

@reg("DF", special=True)
def _df(args):
    return _define(args, "FEXPR")

@reg("DM", special=True)
def _dm(args):
    return _define(args, "MACRO")

@reg("PROG", special=True)
def _prog(args):
    locals_list = list_to_py(args.car)
    body = list_to_py(args.cdr)
    saved = []
    try:
        for v in locals_list:
            if isinstance(v, Symbol):
                _bind(v, NIL, saved)
        # Collect jump labels.
        i = 0
        while i < len(body):
            stmt = body[i]
            if isinstance(stmt, Symbol):
                i += 1
                continue
            try:
                lisp_eval(stmt)
            except GoSignal as g:
                target = None
                for j, s in enumerate(body):
                    if isinstance(s, Symbol) and s is g.tag:
                        target = j
                        break
                if target is None:
                    raise LispError("GO: unbekannte Marke " + g.tag.name)
                i = target
                continue
            i += 1
        return NIL
    except ReturnSignal as r:
        return r.value
    finally:
        for sym, had, old in reversed(saved):
            sym.bound = had
            sym.value = old

@reg("RETURN", special=True)
def _return(args):
    val = lisp_eval(args.car) if isinstance(args, Pair) else NIL
    raise ReturnSignal(val)

@reg("GO", special=True)
def _go(args):
    tag = args.car
    raise GoSignal(tag)


GENSYM_COUNTER = [0]

@reg("GENSYM")
def _gensym(args):
    # GENSYM returns a fresh, uninterned symbol with a unique name for macro hygiene.
    GENSYM_COUNTER[0] += 1
    prefix = "G"
    if args:
        a = args[0]
        if isinstance(a, Str):
            prefix = a.s
        elif isinstance(a, Symbol):
            prefix = a.name
    return Symbol(prefix + str(GENSYM_COUNTER[0]))


# --- Error and condition model ---

@reg("MAKE-CONDITION")
def _make_condition(a):
    ctype = a[0] if a else intern("ERROR")
    if len(a) > 1:
        msg = a[1].s if isinstance(a[1], Str) else lisp_repr(a[1], False)
    else:
        msg = ""
    data = a[2] if len(a) > 2 else NIL
    return Condition(ctype, msg, data)

@reg("CONDITIONP")
def _conditionp(a):
    return T if a and isinstance(a[0], Condition) else NIL

@reg("CONDITION-TYPE")
def _condition_type(a):
    return a[0].ctype if isinstance(a[0], Condition) else NIL

@reg("CONDITION-MESSAGE")
def _condition_message(a):
    return Str(a[0].message) if isinstance(a[0], Condition) else NIL

@reg("CONDITION-DATA")
def _condition_data(a):
    return a[0].data if isinstance(a[0], Condition) else NIL

@reg("SIGNAL", special=True)
def _signal(args):
    cond = lisp_eval(args.car)
    if not isinstance(cond, Condition):
        cond = Condition(intern("ERROR"), lisp_repr(cond, False), NIL)
    raise ConditionSignal(cond)

@reg("CATCH", special=True)
def _catch(args):
    tag = lisp_eval(args.car)
    body = list_to_py(args.cdr)
    try:
        result = NIL
        for f in body:
            result = lisp_eval(f)
        return result
    except ThrowSignal as ts:
        if ts.tag is tag:
            return ts.value
        raise

@reg("THROW", special=True)
def _throw(args):
    tag = lisp_eval(args.car)
    value = lisp_eval(args.cdr.car) if isinstance(args.cdr, Pair) else NIL
    raise ThrowSignal(tag, value)

@reg("UNWIND-PROTECT", special=True)
def _unwind_protect(args):
    protected = args.car
    cleanup = list_to_py(args.cdr)
    try:
        return lisp_eval(protected)
    finally:
        for f in cleanup:
            lisp_eval(f)

def _condition_matches(cond, ctype):
    if ctype is T:
        return True
    if isinstance(ctype, Symbol) and ctype.name == "ERROR":
        return True   # flat hierarchy: every condition is an ERROR
    return isinstance(ctype, Symbol) and ctype is cond.ctype

@reg("HANDLER-CASE", special=True)
def _handler_case(args):
    form = args.car
    clauses = list_to_py(args.cdr)
    try:
        return lisp_eval(form)
    except ConditionSignal as cs:
        cond = cs.cond
    except LispError as e:
        cond = Condition(intern("ERROR"), str(e), NIL)
    for cl in clauses:
        ctype = cl.car                      # Typ-Symbol (unausgewertet)
        varspec = cl.cdr.car                # (var) or NIL
        body = list_to_py(cl.cdr.cdr)
        if _condition_matches(cond, ctype):
            saved = []
            try:
                if isinstance(varspec, Pair) and isinstance(varspec.car, Symbol):
                    _bind(varspec.car, cond, saved)
                result = NIL
                for f in body:
                    result = lisp_eval(f)
                return result
            finally:
                for sym, had, old in reversed(saved):
                    sym.bound = had
                    sym.value = old
    raise ConditionSignal(cond)             # no handler; propagate

@reg("IGNORE-ERRORS", special=True)
def _ignore_errors(args):
    try:
        result = NIL
        for f in list_to_py(args):
            result = lisp_eval(f)
        return result
    except (ConditionSignal, LispError):
        return NIL

@reg("LOAD")
def _load(a):
    # LOAD reads and evaluates a file; this is the basis for REQUIRE.
    if not a or not isinstance(a[0], Str):
        raise LispError("LOAD: Dateipfad (String) erwartet")
    load_file(a[0].s)
    return T

@reg("READ-FROM-STRING")
def _read_from_string(a):
    # READ-FROM-STRING returns the first form read.
    if not a or not isinstance(a[0], Str):
        raise LispError("READ-FROM-STRING: String erwartet")
    form, ok = Reader(a[0].s).read()
    return form if ok else NIL


# --- Simulated RAM for PEEK/POKE tests without an emulator ---
# C64 addresses stay within 64 KiB. MEGA65 platform tests additionally model the 384 KiB fast-RAM
# dump range so linear Bank-4 addresses from $40000 can be checked. Effects, banking, timing, and
# native 6502 execution are not modeled.
MEMORY_SIZE = 393216
MEMORY = bytearray(MEMORY_SIZE)
POKE_LOG = []

def memory_addr(addr):
    addr = need_int(addr)
    if 0 <= addr < MEMORY_SIZE:
        return addr
    return addr & 0xFFFF

@reg("POKE")
def _poke(a):
    addr = memory_addr(a[0])
    val = need_int(a[1]) & 0xFF
    MEMORY[addr] = val
    POKE_LOG.append((addr, val))
    return NIL

@reg("PEEK")
def _peek(a):
    return to_int32(MEMORY[memory_addr(a[0])])

@reg("MEM-RESET")
def _mem_reset(a):
    for i in range(MEMORY_SIZE):
        MEMORY[i] = 0
    del POKE_LOG[:]
    return NIL

@reg("POKE-LOG")
def _poke_log(a):
    # Record pokes as (addr . value) pairs for sequence assertions.
    return py_to_list([Pair(to_int32(ad), to_int32(v)) for ad, v in POKE_LOG])

@reg("POKE-LOG-CLEAR")
def _poke_log_clear(a):
    del POKE_LOG[:]
    return NIL


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

def load_text(text, echo=False):
    for form in read_all(text):
        val = lisp_eval(form)
        if echo:
            sys.stdout.write(lisp_repr(val) + "\n")


def load_file(path, echo=False):
    with open(path, "r") as fh:
        load_text(fh.read(), echo=echo)


def break_loop(cond):
    # Nested error-context REPL. Empty line, Ctrl-D, or :a aborts to top level.
    sys.stdout.write("** Break: " + lisp_repr(cond) + "\n")
    sys.stdout.write("   (Ausdruck auswerten; Leerzeile oder :A = abbrechen)\n")
    while True:
        sys.stdout.write("debug> ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line or not line.strip() or line.strip().upper() == ":A":
            sys.stdout.write("** zurueck zum Top-Level\n")
            return
        try:
            for form in read_all(line):
                sys.stdout.write(lisp_repr(lisp_eval(form)) + "\n")
        except ConditionSignal as cs:
            sys.stdout.write("** Fehler im Break-Loop: " + lisp_repr(cs.cond) + "\n")
        except LispError as e:
            sys.stdout.write("** Fehler im Break-Loop: " + str(e) + "\n")
        except (ReturnSignal, GoSignal, ThrowSignal):
            sys.stdout.write("** Steuerfluss ausserhalb seines Kontexts\n")


def repl():
    sys.stdout.write("LISP 64 Host-Interpreter (Referenzmodell). Strg-D zum Beenden.\n")
    while True:
        try:
            sys.stdout.write("> ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:
                break
            for form in read_all(line):
                sys.stdout.write(lisp_repr(lisp_eval(form)) + "\n")
        except ConditionSignal as cs:
            break_loop(cs.cond)
        except LispError as e:
            break_loop(Condition(intern("ERROR"), str(e), NIL))
        except (ReturnSignal, GoSignal, ThrowSignal):
            sys.stdout.write("Fehler: Steuerfluss (RETURN/GO/THROW) ausserhalb Kontext\n")


def main(argv):
    files = []
    do_repl = False
    echo = False
    for arg in argv[1:]:
        if arg in ("-r", "--repl"):
            do_repl = True
        elif arg in ("-e", "--echo"):
            echo = True
        elif arg in ("-h", "--help"):
            sys.stdout.write("usage: lisp64.py [--echo] [--repl] file.lsp ...\n")
            return 0
        else:
            files.append(arg)
    try:
        for f in files:
            load_file(f, echo=echo)
    except LispError as e:
        sys.stderr.write("Fehler: " + str(e) + "\n")
        return 1
    except ConditionSignal as cs:
        sys.stderr.write("Fehler: " + lisp_repr(cs.cond) + "\n")
        return 1
    if do_repl or not files:
        repl()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
