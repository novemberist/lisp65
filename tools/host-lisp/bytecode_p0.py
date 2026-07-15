#!/usr/bin/env python3
"""Host reference pieces for the pinned lisp65 P0 bytecode ABI.

This module is intentionally small and literal: it mirrors docs/archive/pre-1.0/contracts/bytecode-abi.md
for code-object encoding, disassembly, and an executable reference VM over the
lisp65 16-bit `obj` value model. It does not depend on the tree-walker.
"""

from dataclasses import dataclass


CO_MAGIC = 0xB5
CO_FLAG_REST = 0x01
CO_FLAG_STRICT_ARITY = 0x02
CO_FLAG_OPTIONAL_SHIFT = 2
CO_FLAG_OPTIONAL_MASK = 0xFC
NIL = 0

T_CONS = "cons"
T_SYM = "sym"
T_STR = "str"


class BytecodeError(Exception):
    pass


class DecodeError(BytecodeError):
    pass


class VMError(BytecodeError):
    def __init__(self, status, message, *, error_code=None, error_symbol=None):
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.error_symbol = error_symbol


def to_i16(n):
    n &= 0xFFFF
    return n - 0x10000 if n & 0x8000 else n


def to_u16(n):
    return n & 0xFFFF


def s8(n):
    n &= 0xFF
    return n - 0x100 if n & 0x80 else n


def mkfix(n):
    return to_i16((int(n) << 1) | 1)


def is_fix(o):
    return (to_i16(o) & 1) != 0


def fixval(o):
    return to_i16(o) >> 1


def is_ptr(o):
    return to_i16(o) != NIL and (to_i16(o) & 1) == 0


def obj_hex(o):
    return "0x%04x" % to_u16(o)


def _u16le(n):
    return bytes((n & 0xFF, (n >> 8) & 0xFF))


def _read_u16le(data, off):
    return data[off] | (data[off + 1] << 8)


def _check_u8(n, name):
    if not 0 <= int(n) <= 0xFF:
        raise ValueError("%s out of u8 range: %r" % (name, n))
    return int(n)


def _check_s8(n, name):
    if not -128 <= int(n) <= 127:
        raise ValueError("%s out of s8 range: %r" % (name, n))
    return int(n) & 0xFF


@dataclass(frozen=True)
class OpSpec:
    code: int
    mnemonic: str
    operand: str = "none"


OP_SPECS = [
    OpSpec(0, "HALT"),
    OpSpec(1, "PUSHI8", "s8"),
    OpSpec(2, "ADD"),
    OpSpec(5, "RET"),
    OpSpec(6, "PUSHLIT", "idx"),
    OpSpec(11, "PUSHARG0"),
    OpSpec(12, "PUSHARG1"),
    OpSpec(13, "PUSHARG2"),
    OpSpec(14, "SUB"),
    OpSpec(15, "MUL"),
    OpSpec(16, "DIV"),
    OpSpec(17, "MOD"),
    OpSpec(18, "LESS"),
    OpSpec(19, "GREATER"),
    OpSpec(24, "REMAINDER"),
    OpSpec(28, "JMPREL", "rel8"),
    OpSpec(29, "JFALSEREL", "rel8"),
    OpSpec(30, "EQ"),
    OpSpec(42, "NOT"),
    OpSpec(43, "PUSHNIL"),
    OpSpec(44, "PUSHT"),
    OpSpec(51, "CONS"),
    OpSpec(52, "CAR"),
    OpSpec(53, "CDR"),
    OpSpec(54, "CONSP"),
    OpSpec(55, "EQL"),
    OpSpec(56, "PUSHARGN", "u8"),
    OpSpec(57, "LOADL", "u8"),
    OpSpec(58, "STOREL", "u8"),
    OpSpec(59, "DROP"),
    OpSpec(60, "CALL", "idx+u8"),
    OpSpec(61, "CALLPRIM", "pid+u8"),
    OpSpec(62, "TAILCALL", "idx+u8"),
    OpSpec(63, "CLOSURE", "idx+u8"),
    OpSpec(64, "UPVAL", "u8"),
    OpSpec(65, "SETUPVAL", "u8"),
]

OPCODES = {spec.code: spec for spec in OP_SPECS}
MNEMONICS = {spec.mnemonic: spec for spec in OP_SPECS}

PRIM_IDS = {
    0: "stringp",
    1: "string->list",
    2: "list->string",
    3: "string-length",
    4: "string-ref",
    5: "symbolp",
    6: "numberp",
    7: "apply",
    8: "funcall",
    9: "screen-size",
    10: "screen-clear",
    11: "screen-put-char",
    12: "screen-write-string",
    13: "read-key",
    14: "poll-key",
    15: "%disk-read-sector",
    16: "%disk-byte",
    17: "%disk-load-file",
    18: "%disk-load-lib",
    19: "symbol-value",
    20: "set-symbol-value",
    21: "%disk-poke",
    22: "%disk-write-sector",
    23: "nreverse",
    24: "rplaca",
    25: "rplacd",
    26: "%string-slice",
    27: "%string-concat-list",
    28: "%string-codes",
    29: "%string-from-codes",
    30: "%cs-read-open", 31: "%fasl-read-form", 32: "%fasl-stage",
    33: "%fasl-stage-get", 34: "%save-staged", 35: "%set-macro",
    36: "function-kind", 37: "gensym", 38: "lcc-install",
    39: "macroexpand-1", 40: "number->string", 41: "prin1",
    42: "symbol-count", 43: "symbol-max", 44: "symbol-name", 45: "write-char",
    46: "%fasl-error-entries-overflow", 47: "%fasl-error-nodes-overflow",
    48: "%fasl-error-not-a-defun", 49: "%fasl-error-output-overflow",
    50: "%fasl-error-patches-overflow", 51: "%fasl-error-strings-overflow",
    52: "%fasl-error-too-many-helpers", 53: "%fasl-error-unsupported-literal",
    54: "%fasl-error-window-overflow", 55: "%lcc-error-do-body-too-big",
    56: "%lcc-error-invalid-parameter-list",
    57: "boundp",
    58: "%list-malformed-error",
    59: "set",
    60: "key-event",
    61: "peek",
    62: "poke",
}

PRIM_NAME_IDS = {name: prim_id for prim_id, name in PRIM_IDS.items()}
V1_ACTIVE_PRIM_IDS = frozenset(range(23))
INTERNAL_ONLY_PRIM_IDS = frozenset(
    prim_id for prim_id, name in PRIM_IDS.items() if name.startswith("%")
)

ABI_DIAGNOSTICS = {
    "opcode_active": "abi-opcode-active",
    "opcode_tombstone": "abi-opcode-tombstone",
    "opcode_reserved": "abi-opcode-reserved",
    "prim_active": "abi-prim-active",
    "prim_tombstone": "abi-prim-tombstone",
    "prim_reserved": "abi-prim-reserved",
}


def classify_abi_id(kind, ident, profile_id="dialect-v1", abi_ledger=None):
    """Classify an 8-bit opcode or Prim-ID for offline encode/decode tooling."""
    if kind not in ("opcode", "prim") or type(ident) is not int or not 0 <= ident <= 255:
        raise ValueError("ABI classification requires opcode|prim and an 8-bit id")
    if abi_ledger is None:
        if profile_id != "dialect-v1":
            raise ValueError("non-default ABI profile requires an explicit ledger")
        identities = OPCODES if kind == "opcode" else PRIM_IDS
        identity = identities.get(ident)
        active = set(OPCODES) if kind == "opcode" else V1_ACTIVE_PRIM_IDS
        status = "active" if ident in active else "reserved"
        name = None if identity is None else (
            identity.mnemonic if kind == "opcode" else identity
        )
        operand = None if kind == "prim" or identity is None else identity.operand
        return {
            "id": ident,
            "status": status,
            "canonical_name": name,
            "operand": operand,
            "diagnostic": ABI_DIAGNOSTICS["%s_%s" % (kind, status)],
        }

    profiles = abi_ledger.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("ABI ledger has no profiles list")
    profile = next(
        (item for item in profiles if isinstance(item, dict) and item.get("id") == profile_id),
        None,
    )
    if profile is None:
        raise ValueError("unknown ABI profile: %s" % profile_id)
    space = profile.get("opcodes" if kind == "opcode" else "prim_ids")
    if not isinstance(space, dict):
        raise ValueError("ABI profile %s has no %s space" % (profile_id, kind))
    active = space.get("active", ())
    tombstone = space.get("tombstone", ())
    status = "active" if ident in active else "tombstone" if ident in tombstone else "reserved"
    identity_key = "opcode_identities" if kind == "opcode" else "prim_identities"
    identities = abi_ledger.get(identity_key, ())
    identity = next(
        (item for item in identities if isinstance(item, dict) and item.get("id") == ident),
        None,
    )
    if status != "reserved" and identity is None:
        raise ValueError("%s %s %d lacks an ABI identity" % (profile_id, kind, ident))
    diagnostics = abi_ledger.get("diagnostics", ABI_DIAGNOSTICS)
    diagnostic = diagnostics.get("%s_%s" % (kind, status))
    if not isinstance(diagnostic, str) or not diagnostic:
        raise ValueError("ABI ledger lacks the %s %s diagnostic" % (kind, status))
    return {
        "id": ident,
        "status": status,
        "canonical_name": None if identity is None else identity.get("canonical_name"),
        "operand": None if kind == "prim" or identity is None else identity.get("operand"),
        "diagnostic": diagnostic,
    }


def prim_is_function_designator(prim_id, profile_id="dialect-v1", abi_ledger=None):
    """Return whether a Prim-ID is public through symbol/funcall/apply lookup."""
    if profile_id == "dialect-v2":
        from v2_native_function_views_generated import FUNCTION_DESIGNATOR_IDS
        return prim_id in FUNCTION_DESIGNATOR_IDS
    if prim_id in INTERNAL_ONLY_PRIM_IDS:
        return False
    return classify_abi_id(
        "prim", prim_id, profile_id=profile_id, abi_ledger=abi_ledger
    )["status"] == "active"


# Unconditional eval_init defprim names. Conditional screen/keyboard prims are omitted here:
# stdlib VM builds expose them as bytecode wrappers, which the directory check below sees first.
EVAL_PRIMITIVE_NAMES = frozenset(
    (
        "+",
        "-",
        "*",
        "/",
        "mod",
        "remainder",
        "<",
        ">",
        "=",
        "<=",
        ">=",
        "eq",
        "eql",
        "cons",
        "car",
        "cdr",
        "consp",
        "list",
        "funcall",
        "apply",
        "set-symbol-function",
        "gensym",
        "boundp",
        "set",
        "key-event",
        "screen-size",
        "screen-clear",
        "screen-put-char",
        "screen-write-string",
        "peek",
        "poke",
        "load",
        "stringp",
        "numberp",
        "symbolp",
        "string->list",
        "list->string",
        "string-length",
        "string-ref",
        "write-char",
        "terpri",
        "write-string",
        "prin1",
        "screen-bulk-p",
        "princ",
        "print",
        "write",
        "write-line",
        "save",
        "nreverse",
        "rplaca",
        "rplacd",
        "symbol-count",
        "symbol-max",
        "nth-symbol",
        "symbol-name",
        "function-kind",
        "number->string",
        "set-symbol-value",
        "symbol-value",
        "boundp",
    )
)


@dataclass
class Cell:
    type: str
    a: int = NIL
    b: int = NIL
    name: str = ""


class Heap:
    """Minimal hot-heap model for objects used by P0 vectors."""

    def __init__(self):
        self.cells = [None]
        self.symbols = {}
        self.sym_values = {}
        self.t_obj = self.intern("t")

    def clone(self):
        other = Heap.__new__(Heap)
        other.cells = [
            None if cell is None else Cell(cell.type, cell.a, cell.b, cell.name)
            for cell in self.cells
        ]
        other.symbols = dict(self.symbols)
        other.sym_values = dict(self.sym_values)
        other.t_obj = self.t_obj
        return other

    def alloc(self, typ, a=NIL, b=NIL, name=""):
        idx = len(self.cells)
        if idx > 0x7FFF:
            raise VMError("HeapOOM", "host heap object index overflow")
        self.cells.append(Cell(typ, to_i16(a), to_i16(b), name))
        return to_i16(idx << 1)

    def cell(self, o):
        if not is_ptr(o):
            raise VMError("TypeError", "not a pointer: %s" % obj_hex(o))
        idx = to_u16(o) >> 1
        if idx <= 0 or idx >= len(self.cells):
            raise VMError("TypeError", "bad pointer: %s" % obj_hex(o))
        return self.cells[idx]

    def intern(self, name):
        if name in self.symbols:
            return self.symbols[name]
        obj = self.alloc(T_SYM, name=name)
        self.symbols[name] = obj
        return obj

    def symbol_name(self, o):
        c = self.cell(o)
        if c.type != T_SYM:
            raise VMError("TypeError", "not a symbol: %s" % obj_hex(o))
        return c.name

    def symbol_value(self, o):
        if not self.symbolp(o):
            raise VMError("TypeError", "not a symbol: %s" % obj_hex(o))
        return self.sym_values.get(to_i16(o), NIL)

    def set_symbol_value(self, o, value):
        if not self.symbolp(o):
            raise VMError("TypeError", "not a symbol: %s" % obj_hex(o))
        self.sym_values[to_i16(o)] = to_i16(value)
        return to_i16(value)

    def cons(self, a, b):
        return self.alloc(T_CONS, a, b)

    def car(self, o):
        return self.cell(o).a if is_ptr(o) else NIL

    def cdr(self, o):
        return self.cell(o).b if is_ptr(o) else NIL

    def consp(self, o):
        return is_ptr(o) and self.cell(o).type == T_CONS

    def symbolp(self, o):
        return is_ptr(o) and self.cell(o).type == T_SYM

    def stringp(self, o):
        return is_ptr(o) and self.cell(o).type == T_STR

    def list_from_py(self, values):
        out = NIL
        for item in reversed(values):
            out = self.cons(obj_from_json(self, item), out)
        return out

    def string_from_text(self, text):
        chars = NIL
        for ch in reversed(text):
            chars = self.cons(mkfix(ord(ch)), chars)
        return self.alloc(T_STR, chars, NIL)

    def string_to_text(self, o):
        if not self.stringp(o):
            raise VMError("TypeError", "not a string: %s" % obj_hex(o))
        return self._string_text(self.cell(o).a)

    def obj_to_text(self, o):
        o = to_i16(o)
        if o == NIL:
            return "nil"
        if is_fix(o):
            return str(fixval(o))
        c = self.cell(o)
        if c.type == T_SYM:
            return c.name
        if c.type == T_CONS:
            return self._list_text(o)
        if c.type == T_STR:
            return '"%s"' % self._string_text(c.a)
        return "#<%s>" % c.type

    def _list_text(self, o):
        parts = []
        seen = set()
        while is_ptr(o) and self.cell(o).type == T_CONS:
            if to_u16(o) in seen:
                parts.append("...")
                return "(" + " ".join(parts) + ")"
            seen.add(to_u16(o))
            c = self.cell(o)
            parts.append(self.obj_to_text(c.a))
            o = c.b
        if o != NIL:
            parts.append(".")
            parts.append(self.obj_to_text(o))
        return "(" + " ".join(parts) + ")"

    def _string_text(self, chars):
        out = []
        while is_ptr(chars) and self.cell(chars).type == T_CONS:
            c = self.cell(chars)
            if not is_fix(c.a):
                break
            out.append(chr(fixval(c.a) & 0xFF))
            chars = c.b
        return "".join(out)


def obj_from_json(heap, spec):
    """Materialize a JSON literal spec as a host obj.

    Supported compact forms:
      42                  -> Fixnum
      null or "nil"       -> NIL
      [1, 2, 3]           -> proper list
      {"symbol": "foo"}   -> interned symbol
      {"cons": [a, b]}    -> dotted pair
    """
    if spec is None:
        return NIL
    if isinstance(spec, bool):
        return heap.t_obj if spec else NIL
    if isinstance(spec, int):
        return mkfix(spec)
    if isinstance(spec, str):
        if spec.lower() == "nil":
            return NIL
        if spec.lower() == "t":
            return heap.t_obj
        raise ValueError("string literals must use {'symbol': name}: %r" % spec)
    if isinstance(spec, list):
        return heap.list_from_py(spec)
    if isinstance(spec, dict):
        if "symbol" in spec:
            return heap.intern(spec["symbol"])
        if "cons" in spec:
            a, b = spec["cons"]
            return heap.cons(obj_from_json(heap, a), obj_from_json(heap, b))
        if "string" in spec:
            chars = [ord(ch) for ch in spec["string"]]
            return heap.alloc(T_STR, heap.list_from_py(chars), NIL)
    raise ValueError("unsupported literal spec: %r" % (spec,))


@dataclass(frozen=True)
class CodeObject:
    nargs: int
    nlocals: int
    flags: int
    littab: tuple
    payload: bytes

    def encode(self):
        return encode_code_object(
            self.nargs, self.nlocals, self.flags, self.littab, self.payload
        )


def encode_code_object(nargs, nlocals, flags, littab, payload):
    nargs = _check_u8(nargs, "nargs")
    nlocals = _check_u8(nlocals, "nlocals")
    flags = _check_u8(flags, "flags")
    if len(littab) > 255:
        raise ValueError("too many literals: %d" % len(littab))
    if len(payload) > 0xFFFF:
        raise ValueError("payload too long: %d" % len(payload))
    out = bytearray((CO_MAGIC, nargs, nlocals, flags))
    out += _u16le(len(payload))
    out.append(len(littab))
    for lit in littab:
        out += _u16le(to_u16(lit))
    out += bytes(payload)
    return bytes(out)


def decode_code_object(data):
    data = bytes(data)
    if len(data) < 7:
        raise DecodeError("code object too short: %d bytes" % len(data))
    if data[0] != CO_MAGIC:
        raise DecodeError("bad magic: 0x%02x" % data[0])
    nargs, nlocals, flags = data[1], data[2], data[3]
    code_len = _read_u16le(data, 4)
    nlits = data[6]
    payload_off = 7 + 2 * nlits
    total = payload_off + code_len
    if len(data) != total:
        raise DecodeError(
            "length mismatch: header says %d bytes, got %d" % (total, len(data))
        )
    littab = []
    for i in range(nlits):
        littab.append(to_i16(_read_u16le(data, 7 + 2 * i)))
    return CodeObject(nargs, nlocals, flags, tuple(littab), data[payload_off:total])


def parse_hex(s):
    return bytes(int(tok, 16) for tok in s.replace(",", " ").split())


def hex_bytes(data):
    return " ".join("%02x" % b for b in data)


def encode_instruction(
    mnemonic, *operands, profile_id="dialect-v1", abi_ledger=None
):
    spec = MNEMONICS[mnemonic]
    classification = classify_abi_id(
        "opcode", spec.code, profile_id=profile_id, abi_ledger=abi_ledger
    )
    if classification["status"] != "active":
        raise ValueError(
            "emitter rejected %s opcode %d:%s"
            % (profile_id, spec.code, classification["diagnostic"])
        )
    out = bytearray((spec.code,))
    if spec.operand == "none":
        if operands:
            raise ValueError("%s takes no operand" % mnemonic)
    elif spec.operand == "s8":
        out.append(_check_s8(operands[0], mnemonic))
    elif spec.operand in ("u8", "idx"):
        out.append(_check_u8(operands[0], mnemonic))
    elif spec.operand == "rel8":
        out.append(_check_s8(operands[0], mnemonic))
    elif spec.operand in ("idx+u8", "pid+u8"):
        if spec.operand == "pid+u8":
            prim_id = _check_u8(operands[0], mnemonic)
            prim = classify_abi_id(
                "prim", prim_id, profile_id=profile_id, abi_ledger=abi_ledger
            )
            if prim["status"] != "active":
                raise ValueError(
                    "emitter rejected %s Prim-ID %d:%s"
                    % (profile_id, prim_id, prim["diagnostic"])
                )
        out.append(_check_u8(operands[0], mnemonic))
        out.append(_check_u8(operands[1], mnemonic))
    else:
        raise ValueError("unsupported operand form: %s" % spec.operand)
    return bytes(out)


def decode_instruction(payload, pc, *, profile_id="dialect-v1", abi_ledger=None):
    if pc >= len(payload):
        raise DecodeError("pc outside payload: %d" % pc)
    start = pc
    op = payload[pc]
    pc += 1
    classification = classify_abi_id(
        "opcode", op, profile_id=profile_id, abi_ledger=abi_ledger
    )
    if classification["status"] == "reserved":
        raise DecodeError(
            "%s opcode=0x%02x at %04x"
            % (classification["diagnostic"], op, start)
        )
    spec = OPCODES.get(op)
    if spec is None:
        raise DecodeError("ABI opcode 0x%02x lacks a decoder spec at %04x" % (op, start))
    operand = None
    if spec.operand == "none":
        pass
    elif spec.operand in ("s8", "rel8"):
        if pc >= len(payload):
            raise DecodeError("truncated operand for %s" % spec.mnemonic)
        operand = s8(payload[pc])
        pc += 1
    elif spec.operand in ("u8", "idx"):
        if pc >= len(payload):
            raise DecodeError("truncated operand for %s" % spec.mnemonic)
        operand = payload[pc]
        pc += 1
    elif spec.operand in ("idx+u8", "pid+u8"):
        if pc + 1 >= len(payload):
            raise DecodeError("truncated operand for %s" % spec.mnemonic)
        operand = (payload[pc], payload[pc + 1])
        pc += 2
    else:
        raise DecodeError("unsupported operand form: %s" % spec.operand)
    if spec.operand == "pid+u8":
        prim = classify_abi_id(
            "prim", operand[0], profile_id=profile_id, abi_ledger=abi_ledger
        )
        if prim["status"] == "reserved":
            raise DecodeError(
                "%s Prim-ID=%d at %04x"
                % (prim["diagnostic"], operand[0], start)
            )
    return spec, operand, pc


def disassemble_payload(payload, *, profile_id="dialect-v1", abi_ledger=None):
    lines = []
    pc = 0
    while pc < len(payload):
        start = pc
        spec, operand, pc = decode_instruction(
            payload, pc, profile_id=profile_id, abi_ledger=abi_ledger
        )
        opcode = classify_abi_id(
            "opcode", spec.code, profile_id=profile_id, abi_ledger=abi_ledger
        )
        display_name = spec.mnemonic
        if opcode["status"] == "tombstone":
            display_name += "[%s]" % opcode["diagnostic"]
        text = "%04x %s" % (start, display_name)
        if spec.operand == "s8":
            text += " %d" % operand
        elif spec.operand in ("u8", "idx"):
            text += " %d" % operand
        elif spec.operand == "rel8":
            text += " %+d -> %04x" % (operand, pc + operand)
        elif spec.operand == "idx+u8":
            text += " lit=%d argc=%d" % operand
        elif spec.operand == "pid+u8":
            prim = classify_abi_id(
                "prim", operand[0], profile_id=profile_id, abi_ledger=abi_ledger
            )
            prim_name = prim["canonical_name"] or "?"
            if prim["status"] == "tombstone":
                prim_name += "[%s]" % prim["diagnostic"]
            text += " prim=%d:%s argc=%d" % (operand[0], prim_name, operand[1])
        lines.append(text)
    return lines


def disassemble_code_object(code, *, profile_id="dialect-v1", abi_ledger=None):
    lines = [
        "code nargs=%d nlocals=%d flags=%d nlits=%d payload=%d"
        % (code.nargs, code.nlocals, code.flags, len(code.littab), len(code.payload))
    ]
    for idx, lit in enumerate(code.littab):
        lines.append("lit[%d] = %s" % (idx, obj_hex(lit)))
    lines.extend(
        disassemble_payload(code.payload, profile_id=profile_id, abi_ledger=abi_ledger)
    )
    return lines


class P0VM:
    def __init__(
        self,
        heap=None,
        directory=None,
        macro_symbols=None,
        max_steps=100000,
        max_call_args=None,
        trace=None,
        code_names=None,
        native_vm_maxargs=12,
        native_initial_base=0,
        disk_files=None,
        d81_bam_model=False,
        disk_read_fail_ops=None,
        disk_write_fail_ops=None,
        disk_mount_token=None,
        disk_mount_token_change_before_read_ops=None,
        disk_mount_token_change_before_write_ops=None,
        disk_mount_token_change_after_guard_before_write_ops=None,
        abi_profile="dialect-v1",
        abi_ledger=None,
    ):
        if abi_profile not in ("dialect-v1", "dialect-v2"):
            raise ValueError("unknown ABI profile: %s" % abi_profile)
        if abi_profile != "dialect-v1" and abi_ledger is None:
            raise ValueError("non-default ABI profile requires an explicit ledger")
        self.heap = heap if heap is not None else Heap()
        self.directory = dict(directory or {})
        self.macro_symbols = set(macro_symbols or [])
        self.max_steps = max_steps
        self.max_call_args = max_call_args
        self.native_vm_maxargs = int(native_vm_maxargs)
        self.native_initial_base = int(native_initial_base)
        self.trace = trace
        self.code_names = {}
        for key, value in dict(code_names or {}).items():
            self.code_names[id(key) if isinstance(key, CodeObject) else key] = value
        self._trace_stack = []
        self.disk_buf = [0] * 256
        self.disk_loaded = []
        self.disk_loaded_libs = []
        self.disk_written = {}
        self.disk_foreign_written = {}
        token = tuple(disk_mount_token or (3, 0, 0, 0, 0))
        if len(token) != 5 or any(type(value) is not int or not 0 <= value <= 255 for value in token):
            raise ValueError("disk_mount_token must contain five bytes")
        self.memory = {
            0xD68B + offset: value for offset, value in enumerate(token)
        }
        self.disk_mount_token_change_before_write_ops = {}
        self.disk_mount_token_change_after_guard_before_write_ops = {}
        self.disk_mount_token_change_before_read_ops = {}
        self.disk_transaction_mount_token = None
        for target, source in (
            (
                self.disk_mount_token_change_before_read_ops,
                disk_mount_token_change_before_read_ops,
            ),
            (self.disk_mount_token_change_before_write_ops, disk_mount_token_change_before_write_ops),
            (
                self.disk_mount_token_change_after_guard_before_write_ops,
                disk_mount_token_change_after_guard_before_write_ops,
            ),
        ):
            for operation, changed in dict(source or {}).items():
                if isinstance(operation, str) and operation.isdigit():
                    operation = int(operation)
                changed = tuple(changed)
                if type(operation) is not int or operation < 1 or len(changed) != 5 or any(
                    type(value) is not int or not 0 <= value <= 255 for value in changed
                ):
                    raise ValueError("mount-token injections must map positive operations to five bytes")
                target[operation] = changed
        self.disk_files = self._init_disk_files(disk_files)
        self.d81_bam_model = bool(d81_bam_model)
        self.fasl_stage = [0] * 16384
        self.io_counters = {}
        self.disk_read_trace = []
        self.disk_write_trace = []
        self.configure_disk_faults(disk_read_fail_ops, disk_write_fail_ops)
        self.reset_io_observation()
        self.abi_profile = abi_profile
        self.abi_ledger = abi_ledger
        self.steps = 0

    @staticmethod
    def _fault_ops(values, label):
        result = set()
        for value in values or ():
            if type(value) is not int or value < 1:
                raise ValueError("%s fault operations must be positive integers" % label)
            result.add(value)
        return result

    def configure_disk_faults(self, read_ops=None, write_ops=None):
        self.disk_read_fail_ops = self._fault_ops(read_ops, "read")
        self.disk_write_fail_ops = self._fault_ops(write_ops, "write")

    def reset_io_observation(self):
        self.io_counters = {
            "disk_read": 0,
            "disk_write": 0,
            "disk_poke": 0,
            "fasl_stage_put": 0,
            "fasl_stage_get": 0,
        }
        self.disk_read_trace = []
        self.disk_write_trace = []

    def fasl_stage_put(self, index, value):
        if index < 0 or index >= len(self.fasl_stage):
            return False
        self.io_counters["fasl_stage_put"] += 1
        self.fasl_stage[index] = value & 0xFF
        return True

    def fasl_stage_get(self, index):
        if index < 0 or index >= len(self.fasl_stage):
            raise IndexError("FASL stage index out of range: %d" % index)
        self.io_counters["fasl_stage_get"] += 1
        return self.fasl_stage[index]

    def _init_disk_files(self, disk_files):
        if disk_files is None:
            disk_files = {
                "TESTLIB": "alpha\nbeta",
                "WORK": {"content": "", "capacity": 254},
                "DEMO": "(defun demo-numbers-run () 42)\n",
            }
        out = {}
        track = 1
        sector = 2
        for name, spec in disk_files.items():
            key = self._disk_key(name)
            if isinstance(spec, dict):
                content = spec.get("content", "")
                capacity = int(spec.get("capacity", max(254, len(content))))
            else:
                content = str(spec)
                capacity = max(254, len(content))
            sectors = []
            for _ in range(max(1, (capacity + 253) // 254)):
                if track == 40:
                    track = 41
                if track > 80:
                    raise VMError("DiskFull", "disk fixture exceeds D81 data tracks")
                sectors.append((track, sector))
                sector += 1
                if sector == 40:
                    track += 1
                    sector = 0
            out[key] = {
                "content": content,
                "capacity": capacity,
                "track": sectors[0][0],
                "sector": sectors[0][1],
                "sectors": sectors,
            }
        return out

    def _disk_key(self, name):
        return str(name).upper()[:16]

    def _disk_find_by_sector(self, track, sector):
        for name, meta in self.disk_files.items():
            if meta["track"] == track and meta["sector"] == sector:
                return name, meta
        return None, None

    def _disk_find_sector_chunk(self, track, sector):
        for name, meta in self.disk_files.items():
            for index, address in enumerate(meta["sectors"]):
                if address == (track, sector):
                    return name, meta, index
        return None, None, None

    def _disk_decode_dir_name(self, base):
        chars = []
        for i in range(16):
            c = self.disk_buf[base + 5 + i]
            if c > 127:
                c -= 128
            if c in (0, 32):
                break
            chars.append(chr(c))
        return "".join(chars).upper()

    def _disk_sync_directory_sector(self):
        renames = []
        for entry in range(8):
            base = entry * 32
            if self.disk_buf[base + 2] == 0:
                continue
            track = self.disk_buf[base + 3]
            sector = self.disk_buf[base + 4]
            old, meta = self._disk_find_by_sector(track, sector)
            if old is None:
                continue
            new = self._disk_decode_dir_name(base)
            if new and new != old:
                renames.append((old, new, meta))
        for old, new, meta in renames:
            del self.disk_files[old]
            self.disk_files[new] = meta

    def _disk_bam_sector(self, bam_sector):
        data = [0] * 256
        if bam_sector == 1:
            data[0], data[1] = 40, 2
            first_track, last_track = 1, 40
        else:
            data[0], data[1] = 0, 255
            first_track, last_track = 41, 80
        used = {
            address
            for meta in self.disk_files.values()
            for address in meta["sectors"]
        }
        for track in range(first_track, last_track + 1):
            base = 16 + 6 * (track - first_track)
            bitmap = [0xFF] * 5
            if track == 40:
                bitmap = [0] * 5
            else:
                for used_track, used_sector in used:
                    if used_track == track:
                        bitmap[used_sector // 8] &= ~(1 << (used_sector % 8))
            data[base] = sum(byte.bit_count() for byte in bitmap)
            data[base + 1 : base + 6] = bitmap
        return data

    def run(self, code, args=()):
        self.steps = 0
        return self._run(
            code,
            list(args),
            self._code_name(code),
            native_base=self.native_initial_base,
        )

    def _code_name(self, code):
        return self.code_names.get(id(code), "<code@%x>" % id(code))

    def _trace_enter(self, name, code, args):
        self._trace_stack.append(name)
        if self.trace is not None and hasattr(self.trace, "enter"):
            self.trace.enter(name, code, args)

    def _trace_exit(self, name, code):
        if self.trace is not None and hasattr(self.trace, "exit"):
            self.trace.exit(name, code)
        if self._trace_stack:
            self._trace_stack.pop()

    def _trace_instruction(self, name, code, pc, spec, operand):
        if self.trace is not None and hasattr(self.trace, "instruction"):
            self.trace.instruction(name, code, pc, spec, operand)

    def _trace_call(self, kind, target, argc, pc=None, resolved=False):
        if self.trace is not None and hasattr(self.trace, "call"):
            caller = self._trace_stack[-1] if self._trace_stack else "<top>"
            self.trace.call(caller, kind, target, argc, pc=pc, resolved=resolved)

    def _trace_native_frame(self, name, code, args, native_base, frame_slots, tail):
        if self.trace is not None and hasattr(self.trace, "native_frame"):
            self.trace.native_frame(
                name,
                code,
                args,
                native_base=native_base,
                frame_slots=frame_slots,
                reserve_slots=self.native_vm_maxargs + 1,
                tail=tail,
            )

    def _trace_native_stack(self, name, used):
        if self.trace is not None and hasattr(self.trace, "native_stack"):
            self.trace.native_stack(name, used=used)

    def _run(self, code, args, name=None, native_base=0, native_tail=False):
        name = name or self._code_name(code)
        self._trace_enter(name, code, args)
        optional_count = code.flags >> CO_FLAG_OPTIONAL_SHIFT
        if optional_count and not (code.flags & CO_FLAG_STRICT_ARITY):
            raise VMError("BadOpcode", "optional arity requires STRICT_ARITY")
        if optional_count > code.nargs:
            raise VMError("BadOpcode", "optional arity exceeds nargs")
        if code.flags & CO_FLAG_REST and code.nlocals == 0:
            raise VMError("BadOpcode", "rest arity lacks a local slot")
        if code.flags & CO_FLAG_STRICT_ARITY:
            minimum = code.nargs - optional_count
            if len(args) < minimum or (
                not (code.flags & CO_FLAG_REST) and len(args) > code.nargs
            ):
                raise VMError(
                    "ArityError",
                    "wrong argument count for %s: expected %d%s%d, got %d"
                    % (
                        name,
                        minimum,
                        "+" if code.flags & CO_FLAG_REST else "..",
                        code.nargs,
                        len(args),
                    ),
                )
        frame_slots = code.nargs + code.nlocals
        self._trace_native_frame(name, code, args, native_base, frame_slots, native_tail)
        frame = []
        try:
            for i in range(code.nargs):
                frame.append(to_i16(args[i]) if i < len(args) else NIL)
            if code.flags & CO_FLAG_REST:
                if code.nlocals < 1:
                    raise VMError("BadOpcode", "variadic code object needs rest slot")
                frame.append(self._list_from_objs(args[code.nargs :]))
                frame.extend([NIL] * (code.nlocals - 1))
            else:
                frame.extend([NIL] * code.nlocals)
            stack = []
            pc = 0

            def note_native_stack():
                self._trace_native_stack(name, native_base + len(frame) + len(stack))

            note_native_stack()

            def pop():
                if not stack:
                    raise VMError("BadOpcode", "stack underflow at %04x" % pc)
                return stack.pop()

            def slot(n):
                if n >= len(frame):
                    raise VMError("BadOpcode", "frame slot out of range: %d" % n)
                return frame[n]

            def set_slot(n, value):
                if n >= len(frame):
                    raise VMError("BadOpcode", "frame slot out of range: %d" % n)
                frame[n] = to_i16(value)

            def fix2():
                b = pop()
                a = pop()
                if not is_fix(a) or not is_fix(b):
                    raise VMError("TypeError", "expected two fixnums")
                return fixval(a), fixval(b)

            while pc < len(code.payload):
                note_native_stack()
                self.steps += 1
                if self.steps > self.max_steps:
                    raise VMError("BadOpcode", "max_steps exceeded")
                op_pc = pc
                spec, operand, pc = decode_instruction(
                    code.payload, pc,
                    profile_id=self.abi_profile, abi_ledger=self.abi_ledger,
                )
                self._trace_instruction(name, code, op_pc, spec, operand)
                op = spec.code

                if op in (0, 5):  # HALT, RET
                    note_native_stack()
                    return stack[-1] if stack else NIL
                if op == 1:
                    stack.append(mkfix(operand))
                elif op == 6:
                    if operand >= len(code.littab):
                        raise VMError("BadOpcode", "literal index out of range")
                    stack.append(code.littab[operand])
                elif op == 11:
                    stack.append(slot(0))
                elif op == 12:
                    stack.append(slot(1))
                elif op == 13:
                    stack.append(slot(2))
                elif op == 2:
                    a, b = fix2()
                    stack.append(mkfix(a + b))
                elif op == 14:
                    a, b = fix2()
                    stack.append(mkfix(a - b))
                elif op == 15:
                    a, b = fix2()
                    stack.append(mkfix(a * b))
                elif op == 16:
                    a, b = fix2()
                    if b == 0:
                        raise VMError("TypeError", "division by zero")
                    stack.append(mkfix(_trunc_div(a, b)))
                elif op == 18:
                    a, b = fix2()
                    stack.append(self.heap.t_obj if a < b else NIL)
                elif op == 19:
                    a, b = fix2()
                    stack.append(self.heap.t_obj if a > b else NIL)
                elif op == 24:
                    a, b = fix2()
                    if b == 0:
                        raise VMError("TypeError", "remainder by zero")
                    stack.append(mkfix(a - _trunc_div(a, b) * b))
                elif op == 17:
                    a, b = fix2()
                    if b == 0:
                        raise VMError("TypeError", "mod by zero")
                    remainder = a - _trunc_div(a, b) * b
                    if remainder != 0 and ((remainder < 0) != (b < 0)):
                        remainder += b
                    stack.append(mkfix(remainder))
                elif op == 28:
                    pc += operand
                    _check_pc(pc, code.payload, op_pc)
                elif op == 29:
                    test = pop()
                    if test == NIL:
                        pc += operand
                        _check_pc(pc, code.payload, op_pc)
                elif op == 30:
                    b = pop()
                    a = pop()
                    stack.append(self.heap.t_obj if a == b else NIL)
                elif op == 42:
                    stack.append(self.heap.t_obj if pop() == NIL else NIL)
                elif op == 43:
                    stack.append(NIL)
                elif op == 44:
                    stack.append(self.heap.t_obj)
                elif op == 51:
                    b = pop()
                    a = pop()
                    stack.append(self.heap.cons(a, b))
                elif op == 52:
                    stack.append(self.heap.car(pop()))
                elif op == 53:
                    stack.append(self.heap.cdr(pop()))
                elif op == 54:
                    stack.append(self.heap.t_obj if self.heap.consp(pop()) else NIL)
                elif op == 55:
                    b = pop()
                    a = pop()
                    stack.append(self.heap.t_obj if a == b else NIL)
                elif op == 56:
                    stack.append(slot(operand))
                elif op == 57:
                    stack.append(slot(operand))
                elif op == 58:
                    set_slot(operand, pop())
                elif op == 59:
                    pop()
                elif op == 60:
                    lit_idx, argc = operand
                    stack.append(
                        self._call(
                            code,
                            lit_idx,
                            argc,
                            stack,
                            pc=op_pc,
                            native_base=native_base,
                            frame_slots=len(frame),
                        )
                    )
                elif op == 61:
                    prim_id, argc = operand
                    stack.append(
                        self._callprim(
                            prim_id,
                            argc,
                            stack,
                            pc=op_pc,
                            native_base=native_base,
                            frame_slots=len(frame),
                        )
                    )
                elif op == 62:
                    lit_idx, argc = operand
                    note_native_stack()
                    return self._tailcall(
                        code,
                        lit_idx,
                        argc,
                        stack,
                        pc=op_pc,
                        native_base=native_base,
                    )
                else:
                    raise VMError("BadOpcode", "unsupported opcode %d" % op)
                note_native_stack()
            return stack[-1] if stack else NIL
        finally:
            self._trace_exit(name, code)

    def _pop_args(self, argc, stack):
        if argc > len(stack):
            raise VMError("BadOpcode", "stack underflow in call")
        args = stack[-argc:] if argc else []
        del stack[len(stack) - argc:]
        return args

    def _check_argc(self, argc, context):
        if self.max_call_args is not None and argc > self.max_call_args:
            raise VMError(
                "BadOpcode",
                "%s argc %d exceeds max_call_args %d"
                % (context, argc, self.max_call_args),
            )

    def _list_from_objs(self, objs):
        out = NIL
        for obj in reversed(objs):
            out = self.heap.cons(obj, out)
        return out

    def _list_to_objs(self, obj, context):
        out = []
        while obj != NIL:
            if not self.heap.consp(obj):
                raise VMError("TypeError", "%s expects a proper list" % context)
            c = self.heap.cell(obj)
            out.append(c.a)
            obj = c.b
        return out

    def _call(self, code, lit_idx, argc, stack, pc=None, native_base=0, frame_slots=0):
        self._check_argc(argc, "CALL")
        args = self._pop_args(argc, stack)
        callee_base = native_base + frame_slots + len(stack)
        sym = self._callee_symbol(code, lit_idx)
        callee = self.directory.get(sym)
        target = self.heap.symbol_name(sym) if self.heap.symbolp(sym) else self.heap.obj_to_text(sym)
        self._trace_call("CALL", target, argc, pc=pc, resolved=callee is not None)
        if callee is None:
            return self._invoke_function(sym, args, native_base=callee_base)
        return self._run(callee, args, target, native_base=callee_base)

    def _tailcall(self, code, lit_idx, argc, stack, pc=None, native_base=0):
        self._check_argc(argc, "TAILCALL")
        args = self._pop_args(argc, stack)
        sym = self._callee_symbol(code, lit_idx)
        callee = self.directory.get(sym)
        target = self.heap.symbol_name(sym) if self.heap.symbolp(sym) else self.heap.obj_to_text(sym)
        self._trace_call("TAILCALL", target, argc, pc=pc, resolved=callee is not None)
        if callee is None:
            return self._invoke_function(sym, args, native_base=native_base, native_tail=True)
        return self._run(callee, args, target, native_base=native_base, native_tail=True)

    def _callee_symbol(self, code, lit_idx):
        if lit_idx >= len(code.littab):
            raise VMError("BadOpcode", "callee literal index out of range")
        return code.littab[lit_idx]

    def _invoke_function(self, fn, args, native_base=0, native_tail=False):
        self._check_argc(len(args), "function")
        callee = self.directory.get(fn)
        if self.heap.symbolp(fn):
            target = self.heap.symbol_name(fn)
        else:
            target = self.heap.obj_to_text(fn)
        self._trace_call("INVOKE", target, len(args), resolved=callee is not None)
        if callee is not None:
            return self._run(callee, args, target, native_base=native_base, native_tail=native_tail)
        if not self.heap.symbolp(fn):
            raise VMError("TypeError", "expected function symbol")
        name = target
        return self._invoke_primitive_name(name, args, native_base=native_base)

    def _invoke_primitive_name(
        self, name, args, native_base=0, allow_callprim=True
    ):
        if (
            allow_callprim
            and
            name in PRIM_NAME_IDS
            and prim_is_function_designator(
                PRIM_NAME_IDS[name], self.abi_profile, self.abi_ledger
            )
        ):
            stack = list(args)
            return self._callprim(PRIM_NAME_IDS[name], len(args), stack, native_base=native_base)
        if name == "+":
            total = 0
            for arg in args:
                if not is_fix(arg):
                    raise VMError("TypeError", "+ expects fixnums")
                total += fixval(arg)
            return mkfix(total)
        if name == "*":
            total = 1
            for arg in args:
                if not is_fix(arg):
                    raise VMError("TypeError", "* expects fixnums")
                total *= fixval(arg)
            return mkfix(total)
        if name == "-":
            if not args:
                raise VMError("TypeError", "- expects at least one argument")
            if not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "- expects fixnums")
            total = fixval(args[0])
            if len(args) == 1:
                return mkfix(-total)
            for arg in args[1:]:
                total -= fixval(arg)
            return mkfix(total)
        if name == "/":
            if len(args) < 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "/ expects at least two fixnums")
            total = fixval(args[0])
            for arg in args[1:]:
                divisor = fixval(arg)
                if divisor == 0:
                    raise VMError("TypeError", "division by zero")
                total = _trunc_div(total, divisor)
            return mkfix(total)
        if name in ("mod", "remainder"):
            if len(args) != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%s expects two fixnums" % name)
            divisor = fixval(args[1])
            if divisor == 0:
                raise VMError("TypeError", "%s by zero" % name)
            remainder = fixval(args[0]) - _trunc_div(fixval(args[0]), divisor) * divisor
            if name == "mod" and remainder != 0 and ((remainder < 0) != (divisor < 0)):
                remainder += divisor
            return mkfix(remainder)
        if name in ("<", "<=", ">", ">=", "="):
            if len(args) < 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%s expects at least two fixnums" % name)
            vals = [fixval(arg) for arg in args]
            if name == "<":
                ok = all(a < b for a, b in zip(vals, vals[1:]))
            elif name == "<=":
                ok = all(a <= b for a, b in zip(vals, vals[1:]))
            elif name == ">":
                ok = all(a > b for a, b in zip(vals, vals[1:]))
            elif name == ">=":
                ok = all(a >= b for a, b in zip(vals, vals[1:]))
            else:
                ok = all(val == vals[0] for val in vals[1:])
            return self.heap.t_obj if ok else NIL
        if name in ("eq", "eql"):
            if len(args) != 2:
                raise VMError("TypeError", "%s expects two arguments" % name)
            return self.heap.t_obj if args[0] == args[1] else NIL
        if name in ("not", "null"):
            if len(args) != 1:
                raise VMError("TypeError", "%s expects one argument" % name)
            return self.heap.t_obj if args[0] == NIL else NIL
        if name == "cons":
            if len(args) != 2:
                raise VMError("TypeError", "cons expects two arguments")
            return self.heap.cons(args[0], args[1])
        if name == "car":
            if len(args) != 1:
                raise VMError("TypeError", "car expects one argument")
            return self.heap.car(args[0])
        if name == "cdr":
            if len(args) != 1:
                raise VMError("TypeError", "cdr expects one argument")
            return self.heap.cdr(args[0])
        if name == "consp":
            if len(args) != 1:
                raise VMError("TypeError", "consp expects one argument")
            return self.heap.t_obj if self.heap.consp(args[0]) else NIL
        if name == "nreverse":
            if len(args) != 1:
                raise VMError("TypeError", "nreverse expects one argument")
            cur = args[0]
            prev = NIL
            while self.heap.consp(cur):
                cell = self.heap.cell(cur)
                nxt = cell.b
                cell.b = prev
                prev = cur
                cur = nxt
            return prev
        if name == "gensym":
            if len(args) != 0:
                raise VMError("ArityError", "gensym expects no arguments")
            return self.heap.intern("#:G%d" % len(self.heap.symbols))
        if name == "rplaca":
            if len(args) != 2 or not self.heap.consp(args[0]):
                raise VMError("TypeError", "rplaca expects cons and value")
            self.heap.cell(args[0]).a = to_i16(args[1])
            return args[0]
        if name == "rplacd":
            if len(args) != 2 or not self.heap.consp(args[0]):
                raise VMError("TypeError", "rplacd expects cons and value")
            self.heap.cell(args[0]).b = to_i16(args[1])
            return args[0]
        if name == "write-char":
            if len(args) != 1 or not is_fix(args[0]):
                raise VMError("TypeError", "write-char expects one fixnum")
            return args[0]
        if name == "screen-bulk-p":
            if len(args) != 0:
                raise VMError("TypeError", "screen-bulk-p expects no arguments")
            return self.heap.t_obj
        if name == "terpri":
            return NIL
        if name in ("write-string", "prin1", "princ", "print", "write", "write-line"):
            if len(args) != 1:
                raise VMError("TypeError", "%s expects one argument" % name)
            return args[0]
        if name == "save":
            if len(args) != 2 or not self.heap.stringp(args[0]) or not self.heap.stringp(args[1]):
                raise VMError("TypeError", "save expects name and content strings")
            key = self._disk_key(self.heap.string_to_text(args[0]))
            if key not in self.disk_files:
                return NIL
            content = self.heap.string_to_text(args[1])
            if len(content) > self.disk_files[key]["capacity"]:
                return NIL
            self.disk_files[key]["content"] = content
            return self.heap.t_obj
        if name == "symbol-count":
            if len(args) != 0:
                raise VMError("TypeError", "symbol-count expects no arguments")
            return mkfix(len(self.heap.symbols))
        if name == "symbol-max":
            if len(args) != 0:
                raise VMError("TypeError", "symbol-max expects no arguments")
            return mkfix(330)
        if name == "nth-symbol":
            if len(args) != 1 or not is_fix(args[0]):
                raise VMError("TypeError", "nth-symbol expects one fixnum")
            idx = fixval(args[0])
            if idx < 0 or idx >= len(self.heap.symbols):
                return NIL
            return list(self.heap.symbols.values())[idx]
        if name == "symbol-name":
            if len(args) != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "symbol-name expects one symbol")
            return self.heap.string_from_text(self.heap.symbol_name(args[0]))
        if name == "number->string":
            if len(args) != 1 or not is_fix(args[0]):
                raise VMError("TypeError", "number->string expects one fixnum")
            return self.heap.string_from_text(str(fixval(args[0])))
        if name == "set-symbol-value":
            if len(args) != 2 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "set-symbol-value expects symbol and value")
            return self.heap.set_symbol_value(args[0], args[1])
        if name == "set":
            if len(args) != 2:
                raise VMError("ArityError", "set expects two arguments")
            if not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "set expects a symbol")
            return self.heap.set_symbol_value(args[0], args[1])
        if name == "key-event":
            if len(args) > 1:
                raise VMError("ArityError", "key-event expects zero or one argument")
            mode = 0 if not args else fixval(args[0]) if is_fix(args[0]) else -1
            if mode not in (0, 1):
                raise VMError("TypeError", "key-event mode must be 0 or 1")
            return NIL
        if name == "symbol-value":
            if len(args) != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "symbol-value expects one symbol")
            if to_i16(args[0]) not in self.heap.sym_values:
                raise VMError("UnboundVariable", "symbol-value: unbound")
            return self.heap.symbol_value(args[0])
        if name == "boundp":
            if len(args) != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "boundp expects one symbol")
            return (
                self.heap.t_obj
                if to_i16(args[0]) in self.heap.sym_values
                else NIL
            )
        if name == "function-kind":
            if len(args) != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "function-kind expects one symbol")
            target_name = self.heap.symbol_name(args[0])
            if args[0] in self.macro_symbols:
                return self.heap.intern("macro")
            if args[0] in self.directory:
                return self.heap.intern("bytecode")
            if target_name in EVAL_PRIMITIVE_NAMES:
                return self.heap.intern("primitive")
            return NIL
        raise VMError("DirMiss", "function not in directory: %s" % name)

    def _callprim(self, prim_id, argc, stack, pc=None, native_base=0, frame_slots=0):
        self._check_argc(argc, "CALLPRIM")
        classification = classify_abi_id(
            "prim", prim_id,
            profile_id=self.abi_profile, abi_ledger=self.abi_ledger,
        )
        if classification["status"] != "active":
            raise VMError(
                "BadOpcode",
                "CALLPRIM rejected %s Prim-ID %d: %s"
                % (self.abi_profile, prim_id, classification["diagnostic"]),
            )
        args = self._pop_args(argc, stack)
        callee_base = native_base + frame_slots + len(stack)
        self._trace_call(
            "CALLPRIM",
            PRIM_IDS.get(prim_id, "#%d" % prim_id),
            argc,
            pc=pc,
            resolved=True,
        )
        if prim_id == 0:
            return self.heap.t_obj if argc >= 1 and self.heap.stringp(args[0]) else NIL
        if prim_id == 1:
            if argc < 1 or not self.heap.stringp(args[0]):
                raise VMError("TypeError", "string->list expects a string")
            return self.heap.cell(args[0]).a
        if prim_id == 2:
            if argc < 1:
                raise VMError("TypeError", "list->string expects an argument")
            return self.heap.alloc(T_STR, args[0], NIL)
        if prim_id == 3:
            if argc < 1 or not self.heap.stringp(args[0]):
                raise VMError("TypeError", "string-length expects a string")
            count = 0
            chars = self.heap.cell(args[0]).a
            while is_ptr(chars) and self.heap.cell(chars).type == T_CONS:
                count += 1
                chars = self.heap.cell(chars).b
            return mkfix(count)
        if prim_id == 4:
            if argc < 2 or not self.heap.stringp(args[0]) or not is_fix(args[1]):
                raise VMError("TypeError", "string-ref expects string and index")
            k = fixval(args[1])
            chars = self.heap.cell(args[0]).a
            while is_ptr(chars) and self.heap.cell(chars).type == T_CONS and k > 0:
                k -= 1
                chars = self.heap.cell(chars).b
            if not is_ptr(chars) or self.heap.cell(chars).type != T_CONS:
                raise VMError("TypeError", "string-ref index out of range")
            return self.heap.cell(chars).a
        if prim_id == 5:
            return self.heap.t_obj if argc >= 1 and self.heap.symbolp(args[0]) else NIL
        if prim_id == 6:
            return self.heap.t_obj if argc >= 1 and is_fix(args[0]) else NIL
        if prim_id == 7:
            if argc < 2:
                raise VMError("TypeError", "apply expects function and argument list")
            call_args = list(args[1:-1])
            call_args.extend(self._list_to_objs(args[-1], "apply"))
            return self._invoke_function(args[0], call_args, native_base=callee_base)
        if prim_id == 8:
            if argc < 1:
                raise VMError("TypeError", "funcall expects a function")
            return self._invoke_function(args[0], list(args[1:]), native_base=callee_base)
        if prim_id == 9:
            if argc != 0:
                raise VMError("TypeError", "screen-size expects no arguments")
            return self._list_from_objs([mkfix(80), mkfix(25)])
        if prim_id == 10:
            if argc != 0:
                raise VMError("TypeError", "screen-clear expects no arguments")
            return NIL
        if prim_id == 11:
            if argc not in (3, 4) or not all(is_fix(arg) for arg in args[:3]):
                raise VMError("TypeError", "screen-put-char expects x y code [attr]")
            if argc == 4 and not is_fix(args[3]):
                raise VMError("TypeError", "screen-put-char attr must be a fixnum")
            return NIL
        if prim_id == 12:
            if (
                argc not in (3, 4)
                or not all(is_fix(arg) for arg in args[:2])
                or not self.heap.stringp(args[2])
            ):
                raise VMError("TypeError", "screen-write-string expects x y string [attr]")
            if argc == 4 and not is_fix(args[3]):
                raise VMError("TypeError", "screen-write-string attr must be a fixnum")
            return NIL
        if prim_id == 13:
            if argc != 0:
                raise VMError("TypeError", "read-key expects no arguments")
            return self._list_from_objs([self.heap.intern("key"), mkfix(0), NIL])
        if prim_id == 14:
            if argc != 0:
                raise VMError("TypeError", "poll-key expects no arguments")
            return NIL
        if prim_id == 15:
            if argc != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%disk-read-sector expects track and sector")
            return self.heap.t_obj if self._disk_read_sector(fixval(args[0]), fixval(args[1])) else NIL
        if prim_id == 16:
            if argc != 1 or not is_fix(args[0]):
                raise VMError("TypeError", "%disk-byte expects an index")
            index = fixval(args[0])
            if 0 <= index <= 255:
                return mkfix(self.disk_buf[index])
            if 256 <= index <= 260:
                return mkfix(self.memory[0xD68B + index - 256])
            raise VMError("TypeError", "%disk-byte index must be 0..260")
        if prim_id == 17:
            if argc != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%disk-load-file expects track and sector")
            track, sector = fixval(args[0]), fixval(args[1])
            if (track, sector) != (1, 2):
                return NIL
            self.disk_loaded.append((track, sector))
            return self.heap.t_obj
        if prim_id == 18:
            if argc != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%disk-load-lib expects track and sector")
            track, sector = fixval(args[0]), fixval(args[1])
            if (track, sector) != (1, 2):
                return NIL
            self.disk_loaded_libs.append((track, sector))
            return self.heap.t_obj
        if prim_id == 19:
            if argc != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "symbol-value expects one symbol")
            return self.heap.symbol_value(args[0])
        if prim_id == 20:
            if argc != 2 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "set-symbol-value expects symbol and value")
            return self.heap.set_symbol_value(args[0], args[1])
        if prim_id == 21:
            if argc != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%disk-poke expects index and byte")
            self.io_counters["disk_poke"] += 1
            self.disk_buf[fixval(args[0]) & 0xFF] = fixval(args[1]) & 0xFF
            return args[1]
        if prim_id == 22:
            if argc == 0:
                self.disk_transaction_mount_token = tuple(
                    self.memory[0xD68B + offset] for offset in range(5)
                )
                return mkfix(0)
            if argc == 1 and is_fix(args[0]):
                actual = tuple(self.memory[0xD68B + offset] for offset in range(5))
                status = fixval(args[0])
                if status == 6 and actual != self.disk_transaction_mount_token:
                    status = 12
                return mkfix(status)
            if argc == 2 and all(is_fix(arg) for arg in args):
                self.disk_transaction_mount_token = tuple(
                    self.memory[0xD68B + offset] for offset in range(5)
                )
                return self.heap.t_obj if self._disk_write_sector(fixval(args[0]), fixval(args[1])) else NIL
            if argc == 3 and all(is_fix(arg) for arg in args):
                status = self._disk_write_sector_guarded(
                    fixval(args[0]), fixval(args[1]),
                    self.disk_transaction_mount_token,
                )
                return mkfix(status)
            raise VMError(
                "TypeError",
                "%disk-write-sector expects (), (status), (track sector), or (track sector guarded)",
            )
        if prim_id == 23:
            if argc != 1:
                raise VMError("ArityError", "nreverse expects one argument")
            cur = args[0]
            prev = NIL
            while self.heap.consp(cur):
                cell = self.heap.cell(cur)
                nxt = cell.b
                cell.b = prev
                prev = cur
                cur = nxt
            return prev
        if prim_id == 24:
            if argc != 2:
                raise VMError("ArityError", "rplaca expects two arguments")
            if not self.heap.consp(args[0]):
                raise VMError("TypeError", "rplaca expects cons and value")
            self.heap.cell(args[0]).a = to_i16(args[1])
            return args[0]
        if prim_id == 25:
            if argc != 2:
                raise VMError("ArityError", "rplacd expects two arguments")
            if not self.heap.consp(args[0]):
                raise VMError("TypeError", "rplacd expects cons and value")
            self.heap.cell(args[0]).b = to_i16(args[1])
            return args[0]
        if prim_id == 26:
            if argc != 3:
                raise VMError("ArityError", "%string-slice expects three arguments")
            if (
                not self.heap.stringp(args[0])
                or not is_fix(args[1])
                or not is_fix(args[2])
            ):
                raise VMError("TypeError", "%string-slice expects string start end")
            text = self.heap.string_to_text(args[0])
            start, end = fixval(args[1]), fixval(args[2])
            if start < 0 or start > end or end > len(text):
                raise VMError("TypeError", "%string-slice bounds out of range")
            return self.heap.string_from_text(text[start:end])
        if prim_id == 27:
            if argc != 1:
                raise VMError("ArityError", "%string-concat-list expects one list")
            parts = []
            cur = args[0]
            seen = set()
            while cur != NIL:
                if not self.heap.consp(cur) or to_u16(cur) in seen:
                    raise VMError("TypeError", "%string-concat-list expects a proper list")
                if len(parts) >= 12:
                    raise VMError("TypeError", "%string-concat-list exceeds 12 strings")
                seen.add(to_u16(cur))
                cell = self.heap.cell(cur)
                if not self.heap.stringp(cell.a):
                    raise VMError("TypeError", "%string-concat-list expects strings")
                parts.append(self.heap.string_to_text(cell.a))
                cur = cell.b
            return self.heap.string_from_text("".join(parts))
        if prim_id == 28:
            if argc != 1 or not self.heap.stringp(args[0]):
                raise VMError("TypeError", "%string-codes expects one string")
            return self._list_from_objs(
                [mkfix(ord(ch)) for ch in self.heap.string_to_text(args[0])]
            )
        if prim_id == 29:
            if argc != 1:
                raise VMError("ArityError", "%string-from-codes expects one list")
            chars = self._list_to_objs(args[0], "%string-from-codes")
            if any(not is_fix(ch) or not 0 <= fixval(ch) <= 255 for ch in chars):
                raise VMError("TypeError", "%string-from-codes expects byte fixnums")
            return self.heap.string_from_text("".join(chr(fixval(ch)) for ch in chars))
        if prim_id == 32:
            if argc != 2 or not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "%fasl-stage expects index and byte")
            index = fixval(args[0])
            return self.heap.t_obj if self.fasl_stage_put(index, fixval(args[1])) else NIL
        if prim_id == 33:
            if argc != 1 or not is_fix(args[0]):
                raise VMError("TypeError", "%fasl-stage-get expects an index")
            index = fixval(args[0])
            try:
                value = self.fasl_stage_get(index)
            except IndexError:
                raise VMError("TypeError", "%fasl-stage-get index out of range")
            return mkfix(value)
        if 30 <= prim_id <= 45:
            return self._invoke_primitive_name(
                PRIM_IDS[prim_id], args, native_base=native_base,
                allow_callprim=False,
            )
        if 46 <= prim_id <= 56:
            raise VMError(
                "CompileError", PRIM_IDS[prim_id],
                error_code=prim_id + 3, error_symbol=PRIM_IDS[prim_id],
            )
        if prim_id == 57:
            if argc != 1 or not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "boundp expects one symbol")
            return self.heap.t_obj if to_i16(args[0]) in self.heap.sym_values else NIL
        if prim_id == 58:
            if argc != 0:
                raise VMError("ArityError", "%list-malformed-error expects no arguments")
            raise VMError(
                "TypeError", "vm: type error", error_code=38,
                error_symbol="%list-malformed-error",
            )
        if prim_id == 59:
            if argc != 2:
                raise VMError("ArityError", "set expects two arguments")
            if not self.heap.symbolp(args[0]):
                raise VMError("TypeError", "set expects a symbol")
            return self.heap.set_symbol_value(args[0], args[1])
        if prim_id == 60:
            if argc > 1:
                raise VMError("ArityError", "key-event expects zero or one argument")
            mode = 0 if argc == 0 else fixval(args[0]) if is_fix(args[0]) else -1
            if mode not in (0, 1):
                raise VMError("TypeError", "key-event mode must be 0 or 1")
            return NIL
        if prim_id == 61:
            if argc != 2:
                raise VMError("ArityError", "peek expects exactly 2 arguments")
            if not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "peek expects byte fixnums")
            values = [fixval(arg) for arg in args]
            if any(value < 0 or value > 255 for value in values):
                raise VMError("TypeError", "peek arguments must be in 0..255")
            return mkfix(self.memory.get((values[0] << 8) | values[1], 0))
        if prim_id == 62:
            if argc != 3:
                raise VMError("ArityError", "poke expects exactly 3 arguments")
            if not all(is_fix(arg) for arg in args):
                raise VMError("TypeError", "poke expects byte fixnums")
            values = [fixval(arg) for arg in args]
            if any(value < 0 or value > 255 for value in values):
                raise VMError("TypeError", "poke arguments must be in 0..255")
            self.memory[(values[0] << 8) | values[1]] = values[2]
            return args[2]
        raise VMError("DirMiss", "unsupported CALLPRIM id=%d argc=%d" % (prim_id, argc))

    def _disk_read_sector(self, track, sector):
        self.io_counters["disk_read"] += 1
        operation = self.io_counters["disk_read"]
        changed = self.disk_mount_token_change_before_read_ops.get(operation)
        if changed is not None:
            for offset, value in enumerate(changed):
                self.memory[0xD68B + offset] = value
        if operation in self.disk_read_fail_ops:
            self.disk_buf = [0] * 256
            self.disk_read_trace.append(
                {"operation": operation, "track": track, "sector": sector, "success": False}
            )
            return False
        success = self._disk_read_sector_impl(track, sector)
        self.disk_read_trace.append(
            {"operation": operation, "track": track, "sector": sector, "success": success}
        )
        return success

    def _disk_read_sector_impl(self, track, sector):
        self.disk_buf = [0] * 256
        key = (track, sector)
        if key in self.disk_written:
            self.disk_buf = list(self.disk_written[key])
            return True
        if self.d81_bam_model and track == 40 and sector in (1, 2):
            self.disk_buf = self._disk_bam_sector(sector)
            return True
        # HW-style end-of-chain read: F011 can still return a readable zeroed sector
        # for track 0. This keeps host tests sensitive to `(if next-track ...)`
        # truthiness bugs, because fixnum 0 is not NIL in lisp65.
        if (track, sector) == (0, 0):
            return True
        if (track, sector) == (40, 0):
            # A real 1581 header is a link root, never a directory sector.
            # Its T40/S3 link must be followed before any 32-byte entry is
            # inspected.  Keeping files in the header made the host model
            # agree with the exact corruption that the G6 disk oracle found.
            self.disk_buf[0] = 40
            self.disk_buf[1] = 3
            header = "L65WORK"
            self.disk_buf[2] = 0x44
            self.disk_buf[3] = 0
            for i in range(16):
                self.disk_buf[4 + i] = (ord(header[i]) | 0x80) if i < len(header) else 0xA0
            self.disk_buf[22] = ord("6")
            self.disk_buf[23] = ord("5")
            self.disk_buf[24] = 0xA0
            self.disk_buf[25] = ord("3")
            self.disk_buf[26] = ord("D")
            self.disk_buf[27] = 0xA0
            return True
        if (track, sector) == (40, 3):
            self.disk_buf[0] = 0
            self.disk_buf[1] = 0xFF
            for entry, (name, meta) in enumerate(list(self.disk_files.items())[:8]):
                base = entry * 32
                self.disk_buf[base + 2] = 0x82
                self.disk_buf[base + 3] = meta["track"]
                self.disk_buf[base + 4] = meta["sector"]
                blocks = len(meta["sectors"])
                self.disk_buf[base + 30] = blocks & 0xFF
                self.disk_buf[base + 31] = (blocks >> 8) & 0xFF
                for i in range(16):
                    self.disk_buf[base + 5 + i] = (ord(name[i]) | 0x80) if i < len(name) else 0xA0
            return True
        _name, meta, chunk = self._disk_find_sector_chunk(track, sector)
        if meta is None:
            return False
        payload_len = min(max(0, int(meta["capacity"]) - chunk * 254), 254)
        content = meta["content"][chunk * 254 : chunk * 254 + payload_len]
        data = [ord(ch) & 0xFF for ch in content]
        data.extend([32] * (payload_len - len(data)))
        if chunk + 1 < len(meta["sectors"]):
            self.disk_buf[0], self.disk_buf[1] = meta["sectors"][chunk + 1]
        else:
            self.disk_buf[0] = 0
            self.disk_buf[1] = len(data) + 1
        for i, byte in enumerate(data):
            self.disk_buf[2 + i] = byte
        return True

    def _disk_write_sector(self, track, sector):
        self.io_counters["disk_write"] += 1
        operation = self.io_counters["disk_write"]
        success = (
            operation not in self.disk_write_fail_ops
            and 1 <= track <= 80
            and 0 <= sector <= 39
        )
        self.disk_write_trace.append(
            {
                "operation": operation,
                "track": track,
                "sector": sector,
                "success": success,
                "bytes": tuple(self.disk_buf),
            }
        )
        if not success:
            return False
        self.disk_written[(track, sector)] = list(self.disk_buf)
        if track == 40 and sector >= 3:
            self._disk_sync_directory_sector()
        return True

    def _disk_write_sector_guarded(self, track, sector, expected_token):
        operation = self.io_counters["disk_write"] + 1
        changed = self.disk_mount_token_change_before_write_ops.get(operation)
        if changed is not None:
            for offset, value in enumerate(changed):
                self.memory[0xD68B + offset] = value
        actual = tuple(self.memory[0xD68B + offset] for offset in range(5))
        if expected_token is None or actual != tuple(expected_token):
            self.io_counters["disk_write"] += 1
            self.disk_write_trace.append(
                {
                    "operation": operation,
                    "track": track,
                    "sector": sector,
                    "success": False,
                    "reason": "media-changed-during-transaction",
                    "expected_mount_token": tuple(expected_token),
                    "actual_mount_token": actual,
                    "bytes": tuple(self.disk_buf),
                }
            )
            return 12
        changed_after_guard = self.disk_mount_token_change_after_guard_before_write_ops.get(operation)
        if changed_after_guard is not None:
            for offset, value in enumerate(changed_after_guard):
                self.memory[0xD68B + offset] = value
            self.io_counters["disk_write"] += 1
            command_success = (
                operation not in self.disk_write_fail_ops
                and 1 <= track <= 80 and 0 <= sector <= 39
            )
            if command_success:
                self.disk_foreign_written[(track, sector)] = list(self.disk_buf)
            self.disk_write_trace.append(
                {
                    "operation": operation,
                    "track": track,
                    "sector": sector,
                    "success": False,
                    "command_success": command_success,
                    "foreign_write": command_success,
                    "reason": "media-changed-in-residual-window",
                    "expected_mount_token": tuple(expected_token),
                    "actual_mount_token": tuple(changed_after_guard),
                    "bytes": tuple(self.disk_buf),
                }
            )
            return 12 if command_success else 7
        return 0 if self._disk_write_sector(track, sector) else 7


def _trunc_div(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) ^ (b < 0) else q


def _check_pc(pc, payload, origin):
    if not 0 <= pc <= len(payload):
        raise VMError("BadOpcode", "branch from %04x to %04x out of range" % (origin, pc))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Disassemble a lisp65 P0 code object")
    ap.add_argument("hex", nargs="?", help="code-object hex bytes")
    ns = ap.parse_args()
    if not ns.hex:
        ap.print_help()
        raise SystemExit(2)
    for line in disassemble_code_object(decode_code_object(parse_hex(ns.hex))):
        print(line)
