#!/usr/bin/env python3
"""Disassemble the historical native Phase-4 bytecode VM instruction set.

The tool converts byte sequences and ACME smoke blocks into readable mnemonics
and operands without modifying source. The Phase4VMOpXxx equates are the source
of truth; `--check-acme` reports drift from the mirrored table here.

Usage:
  phase4_disasm.py --hex "01 2a 02 03 00"      # Hex-Bytes
  phase4_disasm.py --file build/.../foo.bin
  phase4_disasm.py --acme-label Phase4VMSmokeCode
  phase4_disasm.py --selftest
  phase4_disasm.py --check-acme
"""

import sys
import os

# opcode -> (mnemonic, operand_kind)
# Order and numbers mirror 20-bytecode-vm.acme (Phase4VMOpXxx = N).
OPCODES = {
    0:  ("HALT",        "none"),
    1:  ("PUSHI8",      "u8"),
    2:  ("ADD",         "none"),
    3:  ("PRINTACC",    "none"),
    4:  ("CALL16",      "u16"),
    5:  ("RET",         "none"),
    6:  ("PUSHLIT8",    "idx"),
    7:  ("PUSHLITS8",   "idx"),
    8:  ("PUSHLIT16",   "idx"),
    9:  ("PUSHLITS16",  "idx"),
    10: ("PUSHLITTYPED","idx"),
    11: ("PUSHARG0",    "none"),
    12: ("PUSHARG1",    "none"),
    13: ("PUSHARG2",    "none"),
    14: ("SUB",         "none"),
    15: ("MUL",         "none"),
    16: ("DIV",         "none"),
    17: ("PRINTBOOL",   "none"),
    18: ("LESS",        "none"),
    19: ("GREATER",     "none"),
    20: ("ZEROP",       "none"),
    21: ("MINUSP",      "none"),
    22: ("ADD1",        "none"),
    23: ("SUB1",        "none"),
    24: ("REMAINDER",   "none"),
    25: ("MINUS",       "none"),
    26: ("LOGAND",      "none"),
    27: ("LOGOR",       "none"),
    28: ("JMPREL",      "rel8"),
    29: ("JFALSEREL",   "rel8"),
    30: ("EQ",          "none"),
    31: ("ABS",         "none"),
    32: ("LOGXOR",      "none"),
    33: ("COMPL",       "none"),
    34: ("LBYTE",       "none"),
    35: ("HBYTE",       "none"),
    36: ("CALLROOT1",   "u16"),
    37: ("TAILSELF1",   "none"),
    38: ("CALLROOT2",   "u16"),
    39: ("CALLROOT3",   "u16"),
    40: ("TAILSELF2",   "none"),
    41: ("TAILSELF3",   "none"),
    42: ("NOT",         "none"),
    43: ("PUSHNIL",     "none"),
    44: ("PUSHT",       "none"),
    45: ("PUSHOBJ",     "u16"),   # valid only in the OBJECT_VALUES build
    46: ("LOADL",       "u8u8"),  # Phase-6 Frame-Slot-Prototyp
    47: ("STOREL",      "u8u8"),  # Phase-6 Frame-Slot-Prototyp
    48: ("DROP",        "none"),  # Phase-6 source sequencing
    49: ("CLOSURE",     "u16"),   # Phase-6 Closure-Opcode-Prototyp
    50: ("CALLCLOSURE1","none"),  # Phase-6 Closure-Call-Prototyp
}

OPERAND_LEN = {"none": 0, "u8": 1, "idx": 1, "rel8": 1, "u16": 2, "u8u8": 2}


class DisasmError(Exception):
    pass


def decode_one(mem, pc):
    """Decode one instruction at mem[pc].

    Return dict(addr, opcode, mnemonic, kind, operand, length, target).
    `operand` is numeric and signed for rel8; `target` is the absolute rel8
    address or None. Raise DisasmError for unknown or truncated instructions.
    """
    if pc >= len(mem):
        raise DisasmError("PC %d ausserhalb des Puffers (len=%d)" % (pc, len(mem)))
    op = mem[pc]
    if op not in OPCODES:
        raise DisasmError("Unbekannter Opcode $%02X bei $%04X" % (op, pc))
    mnem, kind = OPCODES[op]
    olen = OPERAND_LEN[kind]
    if pc + 1 + olen > len(mem):
        raise DisasmError("Operand von %s bei $%04X abgeschnitten" % (mnem, pc))
    operand = None
    target = None
    if kind == "u8" or kind == "idx":
        operand = mem[pc + 1]
    elif kind == "rel8":
        raw = mem[pc + 1]
        operand = raw - 256 if raw >= 128 else raw   # signed
        target = pc + 2 + operand                    # relativ zum naechsten Opcode
    elif kind == "u16":
        operand = mem[pc + 1] | (mem[pc + 2] << 8)
    elif kind == "u8u8":
        operand = (mem[pc + 1], mem[pc + 2])
    return {
        "addr": pc, "opcode": op, "mnemonic": mnem, "kind": kind,
        "operand": operand, "length": 1 + olen, "target": target,
    }


def _operand_text(ins):
    kind = ins["kind"]
    if kind == "none":
        return ""
    if kind == "u8":
        return "%d" % ins["operand"]
    if kind == "idx":
        return "lit[%d]" % ins["operand"]
    if kind == "rel8":
        return "%+d  -> $%04X" % (ins["operand"], ins["target"])
    if kind == "u16":
        return "$%04X" % ins["operand"]
    if kind == "u8u8":
        return "%d %d" % ins["operand"]
    return ""


def format_line(ins, mem):
    raw = " ".join("%02X" % mem[ins["addr"] + i] for i in range(ins["length"]))
    body = "%-9s %s" % (ins["mnemonic"], _operand_text(ins))
    return "$%04X  %-9s %s" % (ins["addr"], raw, body.rstrip())


def disasm(mem, start=0, end=None, stop_at_halt=False):
    """Decode from start to exclusive end, or to the end of the buffer.

    Return instruction dictionaries. With stop_at_halt, stop after the first
    HALT instruction.
    """
    if end is None:
        end = len(mem)
    out = []
    pc = start
    while pc < end:
        ins = decode_one(mem, pc)
        out.append(ins)
        pc += ins["length"]
        if stop_at_halt and ins["opcode"] == 0:
            break
    return out


def disasm_text(mem, start=0, end=None, stop_at_halt=False):
    return "\n".join(format_line(ins, mem)
                     for ins in disasm(mem, start, end, stop_at_halt))


# ---- CLI helpers --------------------------------------------------------

def parse_hex(s):
    s = s.replace(",", " ").replace("$", " ").replace("0x", " ")
    toks = s.split()
    return bytes(int(t, 16) for t in toks)


def acme_opcode_table(path):
    """Read Phase4VMOpXxx = N equates from acme source for drift checks."""
    import re
    pat = re.compile(r"^Phase4VMOp([A-Za-z0-9]+)\s*=\s*(\d+)\s*$")
    table = {}
    with open(path) as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                table[int(m.group(2))] = m.group(1)
    return table


def acme_symbol_table(path):
    """Read decimal or $hex `<Symbol> = <number>` equates."""
    import re
    pat = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\$[0-9A-Fa-f]+|\d+)\s*$")
    table = {}
    with open(path) as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                v = m.group(2)
                table[m.group(1)] = int(v[1:], 16) if v.startswith("$") else int(v)
    return table


def _resolve_byte_token(tok, syms):
    tok = tok.strip()
    if not tok:
        return None
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if tok.lstrip("-").isdigit():
        return int(tok) & 0xFF
    if tok in syms:
        return syms[tok] & 0xFF
    raise DisasmError("Unaufloesbares !byte-Token: %r" % tok)


def extract_acme_label(path, label):
    """Collect the `!byte` data for a named acme block.

    Start at `<label>:` and read `!byte` lines until the next non-empty,
    non-`!byte` line. Resolve symbolic values through the equate table and
    return bytes.
    """
    syms = acme_symbol_table(path)
    out = []
    started = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not started:
                if s == label + ":":
                    started = True
                continue
            # im Block
            if s.startswith("!byte"):
                rest = s[len("!byte"):]
                rest = rest.split(";", 1)[0]   # Kommentar ab ';' weg
                for tok in rest.split(","):
                    b = _resolve_byte_token(tok, syms)
                    if b is not None:
                        out.append(b)
            elif s == "":
                continue
            else:
                break   # naechstes Label / andere Direktive -> Blockende
    if not started:
        raise DisasmError("Label %r nicht gefunden in %s" % (label, path))
    return bytes(out)


def check_acme(path):
    """Compare OPCODES numbers with acme equates; return zero when aligned."""
    acme = acme_opcode_table(path)
    drift = 0
    for num, name in sorted(acme.items()):
        if num not in OPCODES:
            print("DRIFT: .acme hat Opcode %d (%s), Disasm-Tabelle nicht" % (num, name))
            drift += 1
    # Names use different case conventions; check numeric coverage and the final entry.
    for num in OPCODES:
        if num not in acme and num != 45:   # 45=PushObj exists only in the OBJECT build
            print("DRIFT: Disasm-Tabelle hat Opcode %d, .acme nicht" % num)
            drift += 1
    return drift


# ---- Self-test ---------------------------------------------------------

def _selftest():
    # Hand-built program: (PLUS 2 (DIFFERENCE 50 10)) -> 42, then print/halt.
    #   PUSHI8 2 ; PUSHI8 50 ; PUSHI8 10 ; SUB ; ADD ; PRINTACC ; HALT
    prog = bytes([1, 2, 1, 50, 1, 10, 14, 2, 3, 0])
    ins = disasm(prog)
    mnems = [i["mnemonic"] for i in ins]
    assert mnems == ["PUSHI8", "PUSHI8", "PUSHI8", "SUB", "ADD",
                     "PRINTACC", "HALT"], mnems
    assert ins[0]["operand"] == 2
    assert ins[1]["operand"] == 50
    lengths = [i["length"] for i in ins]
    assert lengths == [2, 2, 2, 1, 1, 1, 1], lengths

    # rel8 backward jump: JMPREL -5 at $0005 targets $0005+2-5 = $0002.
    prog2 = bytes([2, 3, 5, 28, 0xFB])   # ADD PRINTACC RET JMPREL -5
    d2 = decode_one(prog2, 3)
    assert d2["mnemonic"] == "JMPREL", d2
    assert d2["operand"] == -5, d2
    assert d2["target"] == 0, d2          # 3+2-5 = 0
    assert d2["length"] == 2

    # rel8 forward jump.
    d3 = decode_one(bytes([29, 0x04]), 0)  # JFALSEREL +4 -> 0+2+4 = 6
    assert d3["target"] == 6, d3

    # u16 little-endian: CALL16 $1234
    d4 = decode_one(bytes([4, 0x34, 0x12]), 0)
    assert d4["operand"] == 0x1234, d4
    assert d4["length"] == 3

    # CallRoot2 (u16 Symbolzeiger) + PushObj (u16)
    assert decode_one(bytes([38, 0x00, 0xC0]), 0)["operand"] == 0xC000
    assert decode_one(bytes([45, 0xEF, 0xBE]), 0)["operand"] == 0xBEEF

    # idx-Familie: alle 1 Byte
    for op in (6, 7, 8, 9, 10):
        assert decode_one(bytes([op, 7]), 0)["length"] == 2
        assert decode_one(bytes([op, 7]), 0)["kind"] == "idx"

    # TailSelf*/PushNil/PushT/Not/Drop/CallClosure1: operandenlos
    for op in (37, 40, 41, 42, 43, 44, 48, 50):
        assert decode_one(bytes([op]), 0)["length"] == 1

    # Phase-6 Closure-Call-V0-Sequenz: CLOSURE child; PUSHI8 arg; CALLCLOSURE1.
    cseq = bytes([49, 0x34, 0x12, 1, 4, 50, 0])
    cseq_m = [i["mnemonic"] for i in disasm(cseq, stop_at_halt=True)]
    assert cseq_m == ["CLOSURE", "PUSHI8", "CALLCLOSURE1", "HALT"], cseq_m
    assert decode_one(cseq, 0)["operand"] == 0x1234

    # Unbekannter Opcode wirft
    try:
        decode_one(bytes([200]), 0)
        assert False, "erwartete DisasmError"
    except DisasmError:
        pass

    # abgeschnittener Operand wirft
    try:
        decode_one(bytes([1]), 0)   # PUSHI8 without an operand
        assert False, "erwartete DisasmError"
    except DisasmError:
        pass

    # Text format contains address, hex bytes, and mnemonic.
    txt = disasm_text(prog, stop_at_halt=True)
    assert "PUSHI8" in txt and "$0000" in txt and "HALT" in txt

    # Check drift against .acme when available.
    here = os.path.dirname(os.path.abspath(__file__))
    acme = os.path.join(here, "..", "..", "src", "v2", "modules",
                        "20-bytecode-vm.acme")
    if os.path.exists(acme):
        assert check_acme(acme) == 0, "Opcode-Tabelle weicht von .acme ab"
        # Echten Smoke-Block extrahieren + dekodieren (Symbolaufloesung)
        mem = extract_acme_label(acme, "Phase4VMSmokeCode")
        m2 = [i["mnemonic"] for i in disasm(mem, stop_at_halt=True)]
        assert m2 == ["PUSHI8", "PUSHI8", "ADD", "PRINTACC", "HALT"], m2

    print("phase4_disasm self-test: ALLES OK (%d Opcodes)" % len(OPCODES))


def main(argv):
    if not argv or "--selftest" in argv:
        _selftest()
        return 0
    if "--check-acme" in argv:
        here = os.path.dirname(os.path.abspath(__file__))
        acme = os.path.join(here, "..", "..", "src", "v2", "modules",
                            "20-bytecode-vm.acme")
        drift = check_acme(acme)
        print("Drift: %d" % drift)
        return 1 if drift else 0
    if argv[0] == "--hex":
        mem = parse_hex(" ".join(argv[1:]))
    elif argv[0] == "--file":
        with open(argv[1], "rb") as f:
            mem = f.read()
    elif argv[0] == "--acme-label":
        here = os.path.dirname(os.path.abspath(__file__))
        acme = os.path.join(here, "..", "..", "src", "v2", "modules",
                            "20-bytecode-vm.acme")
        path = argv[2] if len(argv) > 2 else acme
        mem = extract_acme_label(path, argv[1])
    else:
        sys.stderr.write(__doc__)
        return 2
    print(disasm_text(mem, stop_at_halt=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
