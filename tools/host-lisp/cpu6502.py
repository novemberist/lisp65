#!/usr/bin/env python3
"""Minimal functional 6502 core for fast host tests.

It executes assembled native routines without a VICE boot. The model is not
cycle-accurate, has only 64 KiB RAM and no I/O, rejects decimal mode rather than
emulating it incorrectly, and implements documented opcodes only. Sound, video,
and timing remain emulator or hardware concerns.
"""

# Status-Flags
N = 0x80; V = 0x40; U = 0x20; B = 0x10; D = 0x08; I = 0x04; Z = 0x02; C = 0x01


class CPU:
    def __init__(self, mem=None):
        self.mem = mem if mem is not None else bytearray(65536)
        self.A = self.X = self.Y = 0
        self.SP = 0xFD
        self.PC = 0
        self.P = U | I
        self.halted = False

    # --- Memory ---
    def rd(self, a): return self.mem[a & 0xFFFF]
    def wr(self, a, v): self.mem[a & 0xFFFF] = v & 0xFF
    def rd16(self, a): return self.rd(a) | (self.rd(a + 1) << 8)
    def rd16zp(self, z):  # high byte wraps within zero page, as on a 6502
        return self.rd(z & 0xFF) | (self.rd((z + 1) & 0xFF) << 8)

    # --- Flags ---
    def set(self, flag, on): self.P = (self.P | flag) if on else (self.P & ~flag & 0xFF)
    def get(self, flag): return 1 if (self.P & flag) else 0
    def set_zn(self, v):
        v &= 0xFF
        self.set(Z, v == 0)
        self.set(N, v & 0x80)

    # --- Stack ---
    def push(self, v):
        self.wr(0x0100 + self.SP, v); self.SP = (self.SP - 1) & 0xFF
    def pull(self):
        self.SP = (self.SP + 1) & 0xFF; return self.rd(0x0100 + self.SP)
    def push16(self, v): self.push((v >> 8) & 0xFF); self.push(v & 0xFF)
    def pull16(self): lo = self.pull(); hi = self.pull(); return lo | (hi << 8)

    # --- Operanden-Fetch ---
    def fetch(self): v = self.rd(self.PC); self.PC = (self.PC + 1) & 0xFFFF; return v
    def fetch16(self): lo = self.fetch(); hi = self.fetch(); return lo | (hi << 8)

    def addr(self, mode):
        if mode == "imm":
            a = self.PC; self.PC = (self.PC + 1) & 0xFFFF; return a
        if mode == "zp":  return self.fetch()
        if mode == "zpx": return (self.fetch() + self.X) & 0xFF
        if mode == "zpy": return (self.fetch() + self.Y) & 0xFF
        if mode == "abs": return self.fetch16()
        if mode == "abx": return (self.fetch16() + self.X) & 0xFFFF
        if mode == "aby": return (self.fetch16() + self.Y) & 0xFFFF
        if mode == "indx": return self.rd16zp((self.fetch() + self.X) & 0xFF)
        if mode == "indy": return (self.rd16zp(self.fetch()) + self.Y) & 0xFFFF
        raise ValueError("addr mode " + mode)

    # --- ALU ---
    def adc(self, val):
        if self.P & D:
            raise RuntimeError("Decimal-Mode (BCD) nicht unterstuetzt")
        a = self.A; c = self.get(C); t = a + val + c
        self.set(C, t > 0xFF)
        r = t & 0xFF
        self.set(V, (~(a ^ val) & (a ^ r) & 0x80) != 0)
        self.A = r; self.set_zn(r)
    def sbc(self, val): self.adc(val ^ 0xFF)
    def cmp_(self, reg, val):
        t = (reg - val) & 0x1FF
        self.set(C, reg >= val); self.set_zn(t & 0xFF)

    def branch(self, cond):
        off = self.fetch()
        if cond:
            if off & 0x80: off -= 0x100
            self.PC = (self.PC + off) & 0xFFFF

    # --- One step ---
    def step(self):
        if getattr(self, "trace", False):
            import sys as _s
            _s.stderr.write(self.trace_line() + "\n")
        op = self.fetch()
        h = OPS.get(op)
        if h is None:
            raise RuntimeError("Unbekannter Opcode $%02X @ $%04X" % (op, (self.PC - 1) & 0xFFFF))
        h(self)

    def trace_line(self):
        return "%04X  %-12s  A=%02X X=%02X Y=%02X SP=%02X P=%02X" % (
            self.PC, disasm(self.mem, self.PC), self.A, self.X, self.Y, self.SP, self.P)

    def run(self, max_steps=1000000):
        n = 0
        while not self.halted and n < max_steps:
            self.step(); n += 1
        if n >= max_steps:
            raise RuntimeError("max_steps reached; possible infinite loop")
        return n

    def call(self, entry, max_steps=1000000):
        """Call the subroutine at entry; RTS to a sentinel address stops execution."""
        HALT = 0xFFF0
        self.halted = False
        self.push16(HALT - 1)   # RTS adds one and reaches HALT
        self.PC = entry & 0xFFFF
        self._halt_at = HALT
        self.run(max_steps)


# ---- Opcode-Handler ----
def _ld(reg):
    def f(c, m): v = c.rd(c.addr(m)); setattr(c, reg, v); c.set_zn(v)
    return f
def _st(reg):
    def f(c, m): c.wr(c.addr(m), getattr(c, reg))
    return f

def _build():
    o = {}
    def E(code, fn): o[code] = fn
    # LDA
    for code, m in [(0xA9,"imm"),(0xA5,"zp"),(0xB5,"zpx"),(0xAD,"abs"),(0xBD,"abx"),(0xB9,"aby"),(0xA1,"indx"),(0xB1,"indy")]:
        E(code, (lambda mm: lambda c: (_set(c,"A",c.rd(c.addr(mm)))))(m))
    for code, m in [(0xA2,"imm"),(0xA6,"zp"),(0xB6,"zpy"),(0xAE,"abs"),(0xBE,"aby")]:
        E(code, (lambda mm: lambda c: _set(c,"X",c.rd(c.addr(mm))))(m))
    for code, m in [(0xA0,"imm"),(0xA4,"zp"),(0xB4,"zpx"),(0xAC,"abs"),(0xBC,"abx")]:
        E(code, (lambda mm: lambda c: _set(c,"Y",c.rd(c.addr(mm))))(m))
    for code, m in [(0x85,"zp"),(0x95,"zpx"),(0x8D,"abs"),(0x9D,"abx"),(0x99,"aby"),(0x81,"indx"),(0x91,"indy")]:
        E(code, (lambda mm: lambda c: c.wr(c.addr(mm), c.A))(m))
    for code, m in [(0x86,"zp"),(0x96,"zpy"),(0x8E,"abs")]:
        E(code, (lambda mm: lambda c: c.wr(c.addr(mm), c.X))(m))
    for code, m in [(0x84,"zp"),(0x94,"zpx"),(0x8C,"abs")]:
        E(code, (lambda mm: lambda c: c.wr(c.addr(mm), c.Y))(m))
    # ADC / SBC
    for code, m in [(0x69,"imm"),(0x65,"zp"),(0x75,"zpx"),(0x6D,"abs"),(0x7D,"abx"),(0x79,"aby"),(0x61,"indx"),(0x71,"indy")]:
        E(code, (lambda mm: lambda c: c.adc(c.rd(c.addr(mm))))(m))
    for code, m in [(0xE9,"imm"),(0xE5,"zp"),(0xF5,"zpx"),(0xED,"abs"),(0xFD,"abx"),(0xF9,"aby"),(0xE1,"indx"),(0xF1,"indy")]:
        E(code, (lambda mm: lambda c: c.sbc(c.rd(c.addr(mm))))(m))
    # AND/ORA/EOR
    def logic(opname):
        def g(c, v):
            if opname=="and": c.A &= v
            elif opname=="ora": c.A |= v
            else: c.A ^= v
            c.A &= 0xFF; c.set_zn(c.A)
        return g
    for code, m in [(0x29,"imm"),(0x25,"zp"),(0x35,"zpx"),(0x2D,"abs"),(0x3D,"abx"),(0x39,"aby"),(0x21,"indx"),(0x31,"indy")]:
        E(code, (lambda mm: lambda c: logic("and")(c, c.rd(c.addr(mm))))(m))
    for code, m in [(0x09,"imm"),(0x05,"zp"),(0x15,"zpx"),(0x0D,"abs"),(0x1D,"abx"),(0x19,"aby"),(0x01,"indx"),(0x11,"indy")]:
        E(code, (lambda mm: lambda c: logic("ora")(c, c.rd(c.addr(mm))))(m))
    for code, m in [(0x49,"imm"),(0x45,"zp"),(0x55,"zpx"),(0x4D,"abs"),(0x5D,"abx"),(0x59,"aby"),(0x41,"indx"),(0x51,"indy")]:
        E(code, (lambda mm: lambda c: logic("eor")(c, c.rd(c.addr(mm))))(m))
    # CMP/CPX/CPY
    for code, m in [(0xC9,"imm"),(0xC5,"zp"),(0xD5,"zpx"),(0xCD,"abs"),(0xDD,"abx"),(0xD9,"aby"),(0xC1,"indx"),(0xD1,"indy")]:
        E(code, (lambda mm: lambda c: c.cmp_(c.A, c.rd(c.addr(mm))))(m))
    for code, m in [(0xE0,"imm"),(0xE4,"zp"),(0xEC,"abs")]:
        E(code, (lambda mm: lambda c: c.cmp_(c.X, c.rd(c.addr(mm))))(m))
    for code, m in [(0xC0,"imm"),(0xC4,"zp"),(0xCC,"abs")]:
        E(code, (lambda mm: lambda c: c.cmp_(c.Y, c.rd(c.addr(mm))))(m))
    # INC/DEC mem
    for code, m in [(0xE6,"zp"),(0xF6,"zpx"),(0xEE,"abs"),(0xFE,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:(v+1)&0xFF))(m))
    for code, m in [(0xC6,"zp"),(0xD6,"zpx"),(0xCE,"abs"),(0xDE,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:(v-1)&0xFF))(m))
    # Shifts (accumulator and memory)
    E(0x0A, lambda c: _asl_a(c)); E(0x4A, lambda c: _lsr_a(c))
    E(0x2A, lambda c: _rol_a(c)); E(0x6A, lambda c: _ror_a(c))
    for code, m in [(0x06,"zp"),(0x16,"zpx"),(0x0E,"abs"),(0x1E,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:_asl(c,v)))(m))
    for code, m in [(0x46,"zp"),(0x56,"zpx"),(0x4E,"abs"),(0x5E,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:_lsr(c,v)))(m))
    for code, m in [(0x26,"zp"),(0x36,"zpx"),(0x2E,"abs"),(0x3E,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:_rol(c,v)))(m))
    for code, m in [(0x66,"zp"),(0x76,"zpx"),(0x6E,"abs"),(0x7E,"abx")]:
        E(code, (lambda mm: lambda c: _rmw(c, mm, lambda v:_ror(c,v)))(m))
    # Register-Inc/Dec + Transfers
    E(0xE8, lambda c: _set(c,"X",(c.X+1)&0xFF)); E(0xCA, lambda c: _set(c,"X",(c.X-1)&0xFF))
    E(0xC8, lambda c: _set(c,"Y",(c.Y+1)&0xFF)); E(0x88, lambda c: _set(c,"Y",(c.Y-1)&0xFF))
    E(0xAA, lambda c: _set(c,"X",c.A)); E(0x8A, lambda c: _set(c,"A",c.X))
    E(0xA8, lambda c: _set(c,"Y",c.A)); E(0x98, lambda c: _set(c,"A",c.Y))
    E(0xBA, lambda c: _set(c,"X",c.SP)); E(0x9A, lambda c: _txs(c))
    # Stack
    E(0x48, lambda c: c.push(c.A)); E(0x68, lambda c: _set(c,"A",c.pull()))
    E(0x08, lambda c: c.push(c.P | B | U)); E(0x28, lambda c: _plp(c))
    # Flags
    E(0x18, lambda c: c.set(C,0)); E(0x38, lambda c: c.set(C,1))
    E(0xD8, lambda c: c.set(D,0)); E(0xF8, lambda c: c.set(D,1))
    E(0x58, lambda c: c.set(I,0)); E(0x78, lambda c: c.set(I,1))
    E(0xB8, lambda c: c.set(V,0))
    # Branches
    E(0xF0, lambda c: c.branch(c.get(Z))); E(0xD0, lambda c: c.branch(not c.get(Z)))
    E(0xB0, lambda c: c.branch(c.get(C))); E(0x90, lambda c: c.branch(not c.get(C)))
    E(0x30, lambda c: c.branch(c.get(N))); E(0x10, lambda c: c.branch(not c.get(N)))
    E(0x70, lambda c: c.branch(c.get(V))); E(0x50, lambda c: c.branch(not c.get(V)))
    # Jumps
    E(0x4C, lambda c: _jmp_abs(c)); E(0x6C, lambda c: _jmp_ind(c))
    E(0x20, lambda c: _jsr(c)); E(0x60, lambda c: _rts(c)); E(0x40, lambda c: _rti(c))
    # BIT
    for code, m in [(0x24,"zp"),(0x2C,"abs")]:
        E(code, (lambda mm: lambda c: _bit(c, c.rd(c.addr(mm))))(m))
    # NOP / BRK
    E(0xEA, lambda c: None)
    E(0x00, lambda c: _brk(c))
    return o

def _set(c, reg, v): v &= 0xFF; setattr(c, reg, v); c.set_zn(v)
def _txs(c): c.SP = c.X & 0xFF   # TXS does not set flags
def _plp(c): c.P = (c.pull() & ~B & 0xFF) | U
def _rmw(c, m, fn):
    a = c.addr(m); v = fn(c.rd(a)) & 0xFF; c.wr(a, v); c.set_zn(v)
def _asl(c, v): c.set(C, v & 0x80); return (v << 1) & 0xFF
def _lsr(c, v): c.set(C, v & 0x01); return v >> 1
def _rol(c, v): nc = v & 0x80; r = ((v << 1) | c.get(C)) & 0xFF; c.set(C, nc); return r
def _ror(c, v): nc = v & 0x01; r = (v >> 1) | (c.get(C) << 7); c.set(C, nc); return r
def _asl_a(c): c.A = _asl(c, c.A); c.set_zn(c.A)
def _lsr_a(c): c.A = _lsr(c, c.A); c.set_zn(c.A)
def _rol_a(c): c.A = _rol(c, c.A); c.set_zn(c.A)
def _ror_a(c): c.A = _ror(c, c.A); c.set_zn(c.A)
def _bit(c, v):
    c.set(Z, (c.A & v) == 0); c.set(N, v & 0x80); c.set(V, v & 0x40)
def _jmp_abs(c): c.PC = c.fetch16()
def _jmp_ind(c):
    p = c.fetch16()
    lo = c.rd(p); hi = c.rd((p & 0xFF00) | ((p + 1) & 0xFF))  # Page-Bug
    c.PC = lo | (hi << 8)
def _jsr(c):
    target = c.fetch16(); c.push16((c.PC - 1) & 0xFFFF); c.PC = target
def _rts(c):
    c.PC = (c.pull16() + 1) & 0xFFFF
    if getattr(c, "_halt_at", None) is not None and c.PC == c._halt_at:
        c.halted = True
def _rti(c):
    c.P = (c.pull() & ~B & 0xFF) | U; c.PC = c.pull16()
def _brk(c): c.halted = True

OPS = _build()


# ---- Disassembler for the commonly used opcodes -------------------------
_M2 = {"imm","zp","zpx","zpy","indx","indy","rel"}   # two bytes
_M3 = {"abs","abx","aby","ind"}                       # three bytes
INFO = {
    0xA9:("LDA","imm"),0xA5:("LDA","zp"),0xB5:("LDA","zpx"),0xAD:("LDA","abs"),0xBD:("LDA","abx"),0xB9:("LDA","aby"),0xA1:("LDA","indx"),0xB1:("LDA","indy"),
    0xA2:("LDX","imm"),0xA6:("LDX","zp"),0xB6:("LDX","zpy"),0xAE:("LDX","abs"),0xBE:("LDX","aby"),
    0xA0:("LDY","imm"),0xA4:("LDY","zp"),0xB4:("LDY","zpx"),0xAC:("LDY","abs"),0xBC:("LDY","abx"),
    0x85:("STA","zp"),0x95:("STA","zpx"),0x8D:("STA","abs"),0x9D:("STA","abx"),0x99:("STA","aby"),0x81:("STA","indx"),0x91:("STA","indy"),
    0x86:("STX","zp"),0x96:("STX","zpy"),0x8E:("STX","abs"),0x84:("STY","zp"),0x94:("STY","zpx"),0x8C:("STY","abs"),
    0x69:("ADC","imm"),0x65:("ADC","zp"),0x6D:("ADC","abs"),0xE9:("SBC","imm"),0xE5:("SBC","zp"),0xED:("SBC","abs"),
    0x29:("AND","imm"),0x09:("ORA","imm"),0x49:("EOR","imm"),
    0xC9:("CMP","imm"),0xC5:("CMP","zp"),0xE0:("CPX","imm"),0xC0:("CPY","imm"),
    0xE6:("INC","zp"),0xC6:("DEC","zp"),0xEE:("INC","abs"),0xCE:("DEC","abs"),
    0x0A:("ASL","acc"),0x4A:("LSR","acc"),0x2A:("ROL","acc"),0x6A:("ROR","acc"),
    0xE8:("INX","impl"),0xCA:("DEX","impl"),0xC8:("INY","impl"),0x88:("DEY","impl"),
    0xAA:("TAX","impl"),0x8A:("TXA","impl"),0xA8:("TAY","impl"),0x98:("TYA","impl"),0xBA:("TSX","impl"),0x9A:("TXS","impl"),
    0x48:("PHA","impl"),0x68:("PLA","impl"),0x08:("PHP","impl"),0x28:("PLP","impl"),
    0x18:("CLC","impl"),0x38:("SEC","impl"),0xD8:("CLD","impl"),0xF8:("SED","impl"),0x58:("CLI","impl"),0x78:("SEI","impl"),0xB8:("CLV","impl"),
    0xF0:("BEQ","rel"),0xD0:("BNE","rel"),0xB0:("BCS","rel"),0x90:("BCC","rel"),0x30:("BMI","rel"),0x10:("BPL","rel"),0x70:("BVS","rel"),0x50:("BVC","rel"),
    0x4C:("JMP","abs"),0x6C:("JMP","ind"),0x20:("JSR","abs"),0x60:("RTS","impl"),0x40:("RTI","impl"),
    0x24:("BIT","zp"),0x2C:("BIT","abs"),0xEA:("NOP","impl"),0x00:("BRK","impl"),
}

def disasm(mem, addr):
    op = mem[addr & 0xFFFF]
    info = INFO.get(op)
    if info is None:
        return ".byte $%02X" % op
    name, mode = info
    if mode in _M3:
        v = mem[(addr + 1) & 0xFFFF] | (mem[(addr + 2) & 0xFFFF] << 8)
        suf = {"abs":"$%04X","abx":"$%04X,X","aby":"$%04X,Y","ind":"($%04X)"}[mode] % v
        return "%s %s" % (name, suf)
    if mode == "rel":
        off = mem[(addr + 1) & 0xFFFF]; off = off - 0x100 if off & 0x80 else off
        return "%s $%04X" % (name, (addr + 2 + off) & 0xFFFF)
    if mode in _M2:
        v = mem[(addr + 1) & 0xFFFF]
        suf = {"imm":"#$%02X","zp":"$%02X","zpx":"$%02X,X","zpy":"$%02X,Y","indx":"($%02X,X)","indy":"($%02X),Y"}[mode] % v
        return "%s %s" % (name, suf)
    return name if mode == "impl" else "%s A" % name


# ---------------------------------------------------------------------------
# Self-test with hand-assembled programs.
# ---------------------------------------------------------------------------
def _load(cpu, at, *bytez):
    for i, b in enumerate(bytez):
        cpu.wr(at + i, b)

def _selftest():
    ok = 0
    # 1) 42 + 7 -> $10
    cpu = CPU()
    _load(cpu, 0xC000,
          0xA9, 42,        # LDA #42
          0x18,            # CLC
          0x69, 7,         # ADC #7
          0x85, 0x10,      # STA $10
          0x60)            # RTS
    cpu.call(0xC000)
    assert cpu.rd(0x10) == 49, cpu.rd(0x10); ok += 1
    assert cpu.A == 49; ok += 1

    # 2) Sum 5+4+3+2+1 -> $12 (DEX/BNE loop)
    cpu = CPU()
    _load(cpu, 0xC000,
          0xA9, 0x00,      # LDA #0
          0xA2, 0x05,      # LDX #5
          0x86, 0x00,      # L: STX $00
          0x18,            #    CLC
          0x65, 0x00,      #    ADC $00
          0xCA,            #    DEX
          0xD0, 0xF8,      #    BNE L (back to STX)
          0x85, 0x12,      # STA $12
          0x60)            # RTS
    cpu.call(0xC000)
    assert cpu.rd(0x12) == 15, cpu.rd(0x12); ok += 1

    # 3) Subroutine: LDA #10; JSR inc; STA $13   (inc: ADC #1)
    cpu = CPU()
    _load(cpu, 0xC000,
          0xA9, 10,        # LDA #10
          0x20, 0x10, 0xC0,# JSR $C010
          0x85, 0x13,      # STA $13
          0x60)            # RTS
    _load(cpu, 0xC010,
          0x18,            # CLC
          0x69, 1,         # ADC #1
          0x60)            # RTS
    cpu.call(0xC000)
    assert cpu.rd(0x13) == 11, cpu.rd(0x13); ok += 1

    # 4) 16-bit Addition: $20/$21 (300) + $22/$23 (1000) -> $24/$25 = 1300
    cpu = CPU()
    cpu.wr(0x20, 300 & 0xFF); cpu.wr(0x21, 300 >> 8)
    cpu.wr(0x22, 1000 & 0xFF); cpu.wr(0x23, 1000 >> 8)
    _load(cpu, 0xC000,
          0x18,            # CLC
          0xA5, 0x20,      # LDA $20
          0x65, 0x22,      # ADC $22
          0x85, 0x24,      # STA $24
          0xA5, 0x21,      # LDA $21
          0x65, 0x23,      # ADC $23
          0x85, 0x25,      # STA $25
          0x60)            # RTS
    cpu.call(0xC000)
    res = cpu.rd(0x24) | (cpu.rd(0x25) << 8)
    assert res == 1300, res; ok += 1

    # 5) Flags/Carry: 200 + 100 setzt Carry
    cpu = CPU()
    _load(cpu, 0xC000, 0xA9, 200, 0x18, 0x69, 100, 0x60)
    cpu.call(0xC000)
    assert cpu.A == 44 and cpu.get(C) == 1, (cpu.A, cpu.get(C)); ok += 1

    # 6) Shifts: ASL A von $01 -> $02, Carry 0; ROL danach
    cpu = CPU()
    _load(cpu, 0xC000, 0xA9, 0x81, 0x0A, 0x60)  # LDA #$81; ASL A
    cpu.call(0xC000)
    assert cpu.A == 0x02 and cpu.get(C) == 1, (cpu.A, cpu.get(C)); ok += 1

    # 7) Disassembler
    cpu = CPU()
    _load(cpu, 0xC000, 0xA9, 0x2A, 0x18, 0x69, 0x07, 0x85, 0x10, 0x20, 0x10, 0xC0, 0x60)
    assert disasm(cpu.mem, 0xC000) == "LDA #$2A", disasm(cpu.mem, 0xC000); ok += 1
    assert disasm(cpu.mem, 0xC002) == "CLC"; ok += 1
    assert disasm(cpu.mem, 0xC005) == "STA $10"; ok += 1
    assert disasm(cpu.mem, 0xC007) == "JSR $C010"; ok += 1

    print("cpu6502: ALLES OK (%d Asserts)" % ok)

if __name__ == "__main__":
    _selftest()
