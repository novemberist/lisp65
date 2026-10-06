#!/usr/bin/env python3
"""2.5.4 Seed continuation r1b: named successor of the HALTED Seed attempt build/card-254-product-r1.

What happened.  `c254_seed_producer.py seed` (attempt r1) ran all 75 frozen commands including the ONE product
link and then halted in the post-link inventory:
    c254_product.data_attribution: ('unclassified allocated-section change (needs reviewed attribution)',
                                    ['.lisp65_rt_c2d_00b'])
The section differs from the 2.5.3 Final r8 ELF in seven bytes.  Four are the build-id bytes of four
`cmp #imm` instructions (an existing class).  Three are ONE swap of two adjacent instructions in
c2_stream_phase_00b at 0xc473:   before  85 0a  sta $a (__rc8) ; 18  clc      after  18  clc ; 85 0a  sta $a (__rc8)
STA reads A and writes one zero-page cell and no flag; CLC writes the carry flag only.  The two orders leave
the same machine state; same three bytes in total; every other instruction address is unchanged; the R_MOS_ADDR8
relocation of the STA operand moves with it (0xc474 -> 0xc475).  The existing classes (constant / relocation /
immediate) cannot express a swap, and the immediate class is all-or-nothing per function, so the whole section
was reported.

Reviewer decision.  The swap is a semantically neutral code-generator scheduling difference.  It is accepted as
ONE new, narrowly pinned class, "reviewed commuting adjacent pair" (PAIR below), and the Seed is completed
WITHOUT a second link by this successor.  The release budget (one Seed link, one Final link) is unchanged.

What this tool does (and nothing else).
  check      read-only: the r1 binding and the pinned pair on the two real ELFs; writes nothing
  selftest   negative controls of the new class and of the r1 binding (write-once receipt directory named
             after this file's sha256; a changed tool needs a fresh selftest)
  dry        the whole continuation into build/card-254-product-dry-r1b<suffix>  (NOT a product)
  continue   the official continuation into build/card-254-product-r1b           (write-once, no retry)
  emit       read-only: the values the Final pins need from the finished continuation
The continuation binds r1 (attempt.json, product-link-claim.json, linked.json, halt.json, the ELF/PRG/LTO/map
and the five native receipts by sha256; the four Seed tools as recorded by r1 and still equal on disk; the
authority through the unchanged same-authority check; selftest / preflight / E3 receipts exactly as r1's seed()
required them), copies the link outputs byte for byte into the new directory, and then runs the UNCHANGED
c254_product.inventory(), media() and finish().  The only intervention is a wrapper around
c254_product.data_attribution that neutralises the pinned pair (after proving every pinned fact) and hands
everything else to the unchanged function, which still fails closed on any other unexplained byte.
No product object is compiled, nothing is linked into a product; the cold delivery stager build of media() is
allowed exactly as in r1.  The committed c254_* tools and build/card-254-product-r1 are never written.

The Final side must use the same wrapper around its own inventory():  `with reviewed_pair_class(): P.inventory()`.
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import c254_config as CFG
import c254_product as P

ROOT = CFG.ROOT
TOOL = Path(__file__).resolve()
TAG = 'r1b'
R1_NAME = 'build/card-254-product-r1'             # the halted attempt this tool continues (read-only)
OUT_NAME = 'build/card-254-product-r1b'           # the official continuation (write-once)
DRY_PREFIX = 'build/card-254-product-dry-r1b'     # + suffix: rehearsals, never a product
WORK_NAME = 'build/card-254-seed-continue-r1b'    # selftest receipts (and the author's notes)
ELF_NAME = 'wplto/resident-island-seed.prg.elf'
CLASS = 'reviewed commuting adjacent pair'

# ------------------------------------------------------------------ r1 pins
# sha256 of every r1 file this continuation consumes or cites (measured 2026-10-04 on the retained attempt).
R1_PINS = {
    'attempt.json': 'a08ddbdcfd658d5581a80a6742f4a026664e09f510a41cfa5e5bb1bf7b12e657',
    'product-link-claim.json': '668fd5ccc692d8cd0eaec890d2beadfa22f84c0cbc726685a06f8352e13ea816',
    'linked.json': '30c3d2b1f22189201a2b00114fb24327580778b179b3e77acc7a63f9da9dee89',
    'halt.json': '7b6b6b0108eb1d2c88affbe5f0f585c8ae1600b06088a6ca9d99ca69dc558dd2',
    'wplto/resident-island-seed.prg.elf': '7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244',
    'wplto/resident-island-seed.prg': '192138eb70b4dc46a992e95651f52180a4e1687cd138b9347f8e3b77e37d70c4',
    'wplto/resident-island-seed.prg.lto.o': 'e9d6dc850e01dac45efb0dc1163ac3b463a5d26e00a49c3107380073da472afc',
    'wplto/resident-island-seed.prg.map': '7d8251fc1a1ea1732eb1790ccd37be575dc719a61d232b92ff94d01fbe659f58',
    'native/command-proof.json': 'b037825d4ed307f7b8182a4998caeea41ff706c4860cac07cf921bbfc752125d',
    'native/command-ready.json': 'bad594a46ec1de6d70464c839d7892fb1bc43372ceb7f73ca01f26c0cb7fef89',
    'native/derived-inputs.json': 'f2e1b8642dd470906db495e05a6d2bb7656db7ffca1055eed8ef781e7e0c78ec',
    'native/include-closure.json': 'ab791a5432a967edf6d08ab77c4156964fde6ecaee13c61f32bd793152eb062b',
    'native/plane-price.json': '06628c20baf5c9764cfc3343ff59b9bc5fd5c0deeb0dfad5ce57c916cc3be072',
}
# Carried byte for byte into the continuation directory (same relative names).  The link outputs are r1's;
# the native receipts describe consumed immutable r1 inputs and keep their bindings in r1 coordinates.
CARRIED = tuple(n for n in R1_PINS if n.startswith(('wplto/', 'native/')))
# What a finished Seed has and the halted r1 must not have.
R1_ABSENT = ('complete.json', 'seed.json', 'media.json', 'native/inventory.json', CFG.MEDIA_DIR)
R1_HALT = dict(status='HALT', product_link_claimed=True,
               note='No in-place retry. Retain this attempt and review a named successor.',
               error="AssertionError(('unclassified allocated-section change (needs reviewed attribution)', "
                     "['.lisp65_rt_c2d_00b']))")
R1_HALT_SECTIONS = ['.lisp65_rt_c2d_00b']

# --------------------------------------------------------- the reviewed class
# ONE pair.  Every field is checked; a second pair, another offset, other bytes or another ELF is refused.
PAIR = dict(
    name=CLASS,
    base_elf=CFG.BASE_ELF_SHA,                                   # 2.5.3 Final r8 ELF (the `before` side)
    new_elf=R1_PINS['wplto/resident-island-seed.prg.elf'],       # the r1 link (and its byte-identical Final replay)
    section='.lisp65_rt_c2d_00b', section_address=0xc356, section_bytes=0x61f,
    function='c2_stream_phase_00b', function_value=0xc356, function_bytes=0x61f,
    address=0xc473, offset=0x11d,
    old='850a18', new='18850a',
    old_text=('c473: 85 0a sta $a ; 0xa <__rc8>', 'c475: 18 clc'),
    new_text=('c473: 18 clc', 'c474: 85 0a sta $a ; 0xa <__rc8>'),
    context_before='c472: 68 pla', context_after='c476: 69 10 adc #$10',
    relocation=('R_MOS_ADDR8', '__rc8', 0), old_relocation_at=0xc474, new_relocation_at=0xc475,
)
# Effects of the two opcodes of the class (65xx / 45GS02; no other opcode is admitted).
#   reads / writes: A = accumulator, C = carry flag, M = the addressed zero-page cell.  Neither instruction
#   changes the control flow, the stack, X, Y, Z, B or any flag other than the one listed.
EFFECTS = {
    0x85: dict(mnemonic='sta', length=2, reads=frozenset('A'), writes=frozenset('M')),
    0x18: dict(mnemonic='clc', length=1, reads=frozenset(), writes=frozenset('C')),
}


def commute(x, y):
    """Two adjacent straight-line instructions commute when neither writes what the other reads or writes."""
    return not (x['writes'] & (y['reads'] | y['writes'])) and not (y['writes'] & (x['reads'] | x['writes']))


def row_text(address, row):
    """One objdump row of c254_product.Listings as normalised text: 'c473: 85 0a sta $a ; 0xa <__rc8>'."""
    raw, mnemonic, operand = row
    return ' '.join(f"{address:x}: {raw.hex(' ')} {mnemonic} {operand}".split())


TARGET = re.compile(r'\$([0-9a-f]+)')


def named_addresses(rows):
    """Every `$hex` an instruction operand names (branch / jump / absolute operands; before the comment)."""
    found = {}
    for address, (_raw, _mnemonic, operand) in rows.items():
        for token in TARGET.findall(operand.split(';')[0]):
            found.setdefault(int(token, 16), []).append(address)
    return found


def pair_proof(pin, f):
    """Pure core of the class.  f = facts of ONE section pair:
         section, address, old, new            section name, VMA, bytes before / after
         function_a, function_b                (name, value, bytes) of the containing sized function
         rows_a, rows_b                        {address: (bytes, mnemonic, operand)} objdump rows of that function
         rel_a, rel_b                          {address: (kind, target, addend)} relocation operands in the section
         symbols_a, symbols_b                  [(name, value, bytes, type)] every symbol of the section
         inbound_a, inbound_b                  relocations of ANY section that resolve into the pair
       Returns (new bytes with the pair put back in the old order, relocation address map new->old, proof).
       Raises AssertionError on anything that is not exactly the pinned pair."""
    at, lo = pin['offset'], pin['address']
    old_pair, new_pair = bytes.fromhex(pin['old']), bytes.fromhex(pin['new'])
    hi = lo + len(old_pair)
    assert f['section'] == pin['section'], ('pair class: other section', f['section'])
    assert f['address'] == pin['section_address'] and len(f['old']) == len(f['new']) == pin['section_bytes'], \
        'pair class: section address or size is not the pinned one'
    assert lo == pin['section_address'] + at, 'pair class: inconsistent pin'
    want = (pin['function'], pin['function_value'], pin['function_bytes'])
    assert tuple(f['function_a']) == tuple(f['function_b']) == want, ('pair class: containing function', f['function_a'])
    # 1. the bytes: exactly the pinned old and new bytes at the pinned offset.
    assert f['old'][at:at + len(old_pair)] == old_pair, 'pair class: old bytes at the pinned offset are not the pinned bytes'
    assert f['new'][at:at + len(new_pair)] == new_pair, 'pair class: new bytes at the pinned offset are not the pinned bytes'
    # 2. the pair really is  X ; Y  ->  Y ; X  of two table instructions that commute.
    x, y = EFFECTS.get(old_pair[0]), EFFECTS.get(new_pair[0])
    assert x is not None and y is not None and x is not y, 'pair class: opcode outside the reviewed table'
    assert len(old_pair) == x['length'] + y['length'] and old_pair[x['length']] == new_pair[0], 'pair class: not two instructions'
    first, second = old_pair[:x['length']], old_pair[x['length']:]
    assert new_pair == second + first, 'pair class: new bytes are not the two instructions swapped'
    assert commute(x, y), 'pair class: the two instructions do not commute'
    # 3. the disassembly of both sides is the pinned text and agrees with the bytes.
    ra, rb = f['rows_a'], f['rows_b']
    a_first, a_second, b_first, b_second = lo, lo + x['length'], lo, lo + y['length']
    for rows, places, text, label in ((ra, (a_first, a_second), pin['old_text'], 'before'),
                                      (rb, (b_first, b_second), pin['new_text'], 'after')):
        got = tuple(row_text(p, rows[p]) if p in rows else None for p in places)
        assert got == tuple(text), ('pair class: disassembly is not the pinned text', label, got)
    assert (ra[a_first][0], ra[a_first][1]) == (first, x['mnemonic']) and (ra[a_second][0], ra[a_second][1]) == (second, y['mnemonic'])
    assert (rb[b_first][0], rb[b_first][1]) == (second, y['mnemonic']) and (rb[b_second][0], rb[b_second][1]) == (first, x['mnemonic'])
    before = max(p for p in ra if p < lo)
    assert before in rb and row_text(before, ra[before]) == row_text(before, rb[before]) == pin['context_before'], \
        'pair class: instruction before the pair'
    assert hi in ra and hi in rb and row_text(hi, ra[hi]) == row_text(hi, rb[hi]) == pin['context_after'], \
        'pair class: instruction after the pair'
    for rows, data in ((ra, f['old']), (rb, f['new'])):
        for p in (before, hi):
            raw = rows[p][0]
            assert data[p - f['address']:p - f['address'] + len(raw)] == raw, 'pair class: listing does not describe these bytes'
    # 4. the instruction stream of the whole function is otherwise the same: same addresses, lengths, mnemonics.
    assert set(ra) ^ set(rb) == {a_second, b_second}, ('pair class: instruction boundaries moved elsewhere',
                                                      sorted(set(ra) ^ set(rb))[:8])
    for p in set(ra) & set(rb):
        if p != lo:
            assert len(ra[p][0]) == len(rb[p][0]) and ra[p][1] == rb[p][1], ('pair class: other instruction changed', hex(p))
    # 5. nothing enters between the two instructions: no named branch / jump / absolute operand, no symbol,
    #    no relocation that resolves into the pair.  (Strict: the first byte of the pair is refused as well.)
    for rows, label in ((ra, 'before'), (rb, 'after')):
        named = named_addresses(rows)
        hit = sorted(hex(p) for p in range(lo, hi) if p in named)
        assert not hit, ('pair class: an operand names an address inside the pair', label, hit)
    for symbols, label in ((f['symbols_a'], 'before'), (f['symbols_b'], 'after')):
        hit = [s for s in symbols if lo <= s[1] < hi]
        assert not hit, ('pair class: symbol inside the pair', label, hit)
    assert sorted(f['symbols_a']) == sorted(f['symbols_b']), 'pair class: symbols of the section differ'
    assert not f['inbound_a'] and not f['inbound_b'], ('pair class: relocation resolves into the pair',
                                                       f['inbound_a'], f['inbound_b'])
    # 6. relocations: the STA operand relocation moves with the instruction; every other one is unchanged.
    inside_a = {p: v for p, v in f['rel_a'].items() if lo <= p < hi}
    inside_b = {p: v for p, v in f['rel_b'].items() if lo <= p < hi}
    assert inside_a == {pin['old_relocation_at']: tuple(pin['relocation'])}, ('pair class: relocation before', inside_a)
    assert inside_b == {pin['new_relocation_at']: tuple(pin['relocation'])}, ('pair class: relocation after', inside_b)
    assert pin['old_relocation_at'] == a_first + 1 and pin['new_relocation_at'] == b_second + 1, 'pair class: inconsistent pin'
    assert {p: v for p, v in f['rel_a'].items() if not lo <= p < hi} == {p: v for p, v in f['rel_b'].items() if not lo <= p < hi}, \
        'pair class: another relocation of the section changed'
    neutral = bytes(f['new'][:at]) + old_pair + bytes(f['new'][at + len(old_pair):])
    rest = [i for i in range(len(neutral)) if neutral[i] != f['old'][i]]
    assert not any(at <= i < at + len(old_pair) for i in rest)
    proof = dict(
        **{'class': pin['name']}, section=pin['section'], function=pin['function'], address=f'0x{lo:04x}',
        offset=at, before_bytes=pin['old'], after_bytes=pin['new'],
        before_text=list(pin['old_text']), after_text=list(pin['new_text']),
        context=[pin['context_before'], pin['context_after']],
        effects={e['mnemonic']: dict(reads=sorted(e['reads']), writes=sorted(e['writes'])) for e in (x, y)},
        relocation=dict(kind=pin['relocation'][0], target=pin['relocation'][1], addend=pin['relocation'][2],
                        before=f"0x{pin['old_relocation_at']:04x}", after=f"0x{pin['new_relocation_at']:04x}"),
        pair_bytes=len(old_pair), other_changed_bytes_in_section=len(rest),
        other_changed_bytes_left_to='the unchanged c254_product.data_attribution (constant / relocation / immediate)',
        decision='reviewer: semantically neutral code-generator scheduling difference; accepted as one pinned class')
    return neutral, {pin['new_relocation_at']: pin['old_relocation_at']}, proof


class NeutralTruth:
    """The `after` ElfTruth with the pinned pair put back in the old order: one section's bytes and the one
    relocation offset.  Everything else is the real object."""
    def __init__(self, truth, section, data, moved):
        self._truth, self._section, self._data = truth, section, data
        self._relocations = [dataclasses.replace(r, offset=moved[r.offset])
                             if r.source_section == section and r.offset in moved else r for r in truth.relocations]

    def __getattr__(self, name):
        return getattr(self._truth, name)

    @property
    def relocations(self):
        return self._relocations

    def section_bytes(self, name):
        return self._data if name == self._section else self._truth.section_bytes(name)


def inbound(truth, section, lo, hi):
    """Relocations of any section whose target resolves to an address of `section` inside [lo, hi)."""
    sections = {s.name: s for s in truth.sections}
    by_index = {s.index: s for s in truth.symbols}
    found = []
    for r in truth.relocations:
        target = by_index[r.target_symbol_index]
        if target.symbol_type == 'Section' and target.name == section:
            address = sections[section].address + r.addend
        elif target.symbol_type != 'Section' and target.section == section:
            address = target.value + r.addend
        else:
            continue
        if lo <= address < hi:
            found.append((r.source_section, r.offset, r.relocation_type, target.name, r.addend))
    return found


def facts(a, b, listing, paths, pin=PAIR):
    """Read the facts pair_proof needs from two ElfTruth objects and the objdump listings."""
    name = pin['section']
    lo, hi = pin['address'], pin['address'] + len(bytes.fromhex(pin['old']))
    fa, fb = a.symbol(pin['function']), b.symbol(pin['function'])
    assert fa.section == fb.section == name, 'pair class: containing function is in another section'
    return dict(
        section=name, address=a.section(name).address, old=a.section_bytes(name), new=b.section_bytes(name),
        address_b=b.section(name).address,
        function_a=(fa.name, fa.value, fa.bytes), function_b=(fb.name, fb.value, fb.bytes),
        rows_a=listing(paths[0], name, fa.value, fa.value + fa.bytes),
        rows_b=listing(paths[1], name, fb.value, fb.value + fb.bytes),
        rel_a=P.reloc_index(a, name), rel_b=P.reloc_index(b, name),
        symbols_a=[(s.name, s.value, s.bytes, s.symbol_type) for s in a.symbols if s.section == name],
        symbols_b=[(s.name, s.value, s.bytes, s.symbol_type) for s in b.symbols if s.section == name],
        inbound_a=inbound(a, name, lo, hi), inbound_b=inbound(b, name, lo, hi))


def reviewed_data_attribution(original, state, pin=PAIR):
    """c254_product.data_attribution plus the one reviewed class.  `original` stays the judge of every other byte."""
    def data_attribution(a, b, patterns, allowed=frozenset(), listing=None, paths=None, changed=frozenset()):
        assert state['applied'] == 0, 'pair class: one application per inventory'
        assert listing is not None and paths is not None and not changed, 'pair class: 2.5.4 inventory call shape only'
        assert P.sha(Path(paths[0]).read_bytes()) == pin['base_elf'], 'pair class: the before ELF is not the 2.5.3 Final r8 ELF'
        assert P.sha(Path(paths[1]).read_bytes()) == pin['new_elf'], 'pair class: the after ELF is not the pinned r1 link'
        f = facts(a, b, listing, paths, pin)
        assert f['address_b'] == f['address'], 'pair class: section moved'
        neutral, moved, proof = pair_proof(pin, f)
        rows = original(a, NeutralTruth(b, pin['section'], neutral, moved), patterns, allowed=allowed,
                        listing=listing, paths=paths, changed=changed)
        hit = [r for r in rows if r['section'] == pin['section']]
        if not hit:      # the pair was the only difference of the section
            hit = [dict(section=pin['section'], bytes=len(neutral), explained=True, by=[], unexplained=None)]
            rows.append(hit[0])
        assert len(hit) == 1 and hit[0]['explained'] and hit[0]['unexplained'] is None
        hit[0]['by'] = list(hit[0]['by']) + [pin['name']]
        hit[0]['reviewed_pair'] = proof
        state['applied'] += 1
        state['proof'] = proof
        return rows
    return data_attribution


@contextmanager
def reviewed_pair_class(pin=PAIR):
    """Install the class around c254_product.data_attribution for the duration of ONE inventory() call.
    Used by this continuation and, identically, by the Final replay.  Leaving the block without exactly one
    application is an error (the class must be needed, and only once)."""
    state = dict(applied=0, proof=None)
    with patch.object(P, 'data_attribution', reviewed_data_attribution(P.data_attribution, state, pin)):
        yield state
    assert state['applied'] == 1 and state['proof'], 'pair class: not applied exactly once'


# ------------------------------------------------------------- r1 binding
def r1_view():
    """Everything the binding check looks at, read from disk (read-only)."""
    r1 = ROOT / R1_NAME
    load = lambda name: json.loads((r1 / name).read_text()) if (r1 / name).is_file() else None
    recipe = load('native/command-proof.json')
    return dict(
        files={name: (P.sha((r1 / name).read_bytes()) if (r1 / name).is_file() else None) for name in R1_PINS},
        present=[name for name in R1_ABSENT if os.path.lexists(r1 / name)],
        logs=sorted(p.name for p in r1.glob('command-*.log')),
        attempt=load('attempt.json'), claim=load('product-link-claim.json'), linked=load('linked.json'),
        halt=load('halt.json'), link_command=recipe['commands'][74] if recipe else None,
        recipe_commands=len(recipe['commands']) if recipe else None,
        elf_bytes=(r1 / ELF_NAME).stat().st_size if (r1 / ELF_NAME).is_file() else None,
        tools_now=P.tool_identity(), authority_now=P.source_revision(),
        selftest=json.loads((P.SELFTEST / 'receipt.json').read_text()),
        preflight_bind=P.bind(P.PREFLIGHT / 'receipt.json'), predecessor_bind=P.bind(P.BASE / 'complete.json'),
        config_seed=CFG.SEED, config_gate=CFG.check(stage='seed'))


def r1_problems(v, e3_bind, preflight_revision):
    """Pure: every reason the retained r1 attempt is not exactly the reviewed one.  [] = bound."""
    found = []
    if v['config_seed'] != R1_NAME:
        found.append('c254_config.SEED is not the attempt this tool continues')
    for name, want in R1_PINS.items():
        if v['files'].get(name) != want:
            found.append('r1 file drift: ' + name)
    if v['present']:
        found.append('r1 is not a halted post-link attempt (it has ' + ', '.join(v['present']) + ')')
    if v['logs'] != [f'command-{i:03d}.log' for i in range(CFG.NATIVE_COMMANDS)]:
        found.append('r1 does not carry exactly the 75 command logs')
    attempt, claim, linked, halt = v['attempt'], v['claim'], v['linked'], v['halt']
    if not all(isinstance(x, dict) for x in (attempt, claim, linked, halt)):
        return found + ['r1 record missing']
    if attempt.get('status') != 'STARTED':
        found.append('r1 attempt.json is not a started Seed attempt')
    if attempt.get('tools') != v['tools_now']:
        found.append('Seed tool bytes differ from the four tools r1 recorded')
    if v['selftest'].get('status') != 'PASS' or v['selftest'].get('tools') != v['tools_now']:
        found.append('tool bytes changed since selftest')
    try:
        same = CFG.same_authority(attempt['authority'], v['authority_now']) and \
            CFG.same_authority(preflight_revision, v['authority_now'])
    except (KeyError, TypeError):
        same = False
    if not same:
        found.append('authority or consumed roots moved since r1 / preflight')
    if attempt.get('preflight') != v['preflight_bind']:
        found.append('r1 ran against another preflight receipt')
    if attempt.get('e3') != e3_bind:
        found.append('r1 bound another exhaustive E3 receipt')
    if attempt.get('predecessor') != v['predecessor_bind']:
        found.append('r1 bound another predecessor')
    if claim.get('product_links') != 1 or claim.get('command') != v['link_command'] or v['recipe_commands'] != CFG.NATIVE_COMMANDS:
        found.append('product-link-claim.json is not the one frozen product link of the r1 recipe')
    elif claim['command'][claim['command'].index('-o') + 1] != R1_NAME + '/wplto/resident-island-seed.prg':
        found.append('the claimed link wrote another output')
    want_linked = dict(status='LINKED', product_links=1,
                       ELF=dict(path=R1_NAME + '/' + ELF_NAME, bytes=v['elf_bytes'], sha256=R1_PINS[ELF_NAME]))
    if linked != want_linked:
        found.append('linked.json is not the LINKED record of the pinned ELF with product_links 1')
    if halt != R1_HALT:
        found.append('halt.json is not the reviewed halt')
    gate = v['config_gate']
    if gate.get('problems') != ['write-once name already claimed: ' + R1_NAME]:
        found.append('c254_config seed gate: ' + repr(gate.get('problems')))
    return found


def selftest_dir():
    return ROOT / WORK_NAME / ('selftest-' + P.sha(TOOL.read_bytes())[:12])


def entry_checks():
    """The checks r1's seed() made, plus the r1 binding.  Read-only."""
    pre = P.verify_preflight()
    tests = P.load(P.SELFTEST / 'receipt.json')
    assert tests['status'] == 'PASS' and tests['tools'] == P.tool_identity(), 'tool bytes changed since selftest'
    assert CFG.same_authority(pre['source_revision'], P.source_revision()), 'authority or consumed roots moved since preflight'
    e3_receipt = P.require_e3(pre)
    view = r1_view()
    found = r1_problems(view, e3_receipt, pre['source_revision'])
    assert not found, ('r1 binding', found)
    return pre, e3_receipt, view


def r1_binding(view):
    r1 = ROOT / R1_NAME
    logs = [P.bind(r1 / name) for name in view['logs']]
    return dict(attempt=R1_NAME, files={name: P.bind(r1 / name) for name in R1_PINS},
                command_logs=dict(count=len(logs), sha256=P.sha(json.dumps(logs, sort_keys=True).encode())),
                halt=view['halt'], halted_in='c254_product.inventory -> data_attribution',
                unclassified_sections=R1_HALT_SECTIONS, tools=view['attempt']['tools'],
                authority=view['attempt']['authority'])


# ------------------------------------------------------- process boundary
class Processes:
    """Audit hook: the continuation may start read-only ELF tools, the cold delivery stager build (four
    commands, outputs below <out>/media-254) and the host ABI contract emitter.  Nothing that names a
    product link input or output, no llvm-link, no other compiler run."""
    FORBIDDEN = ('/wplto', 'combined-c.bc', 'lto-obj-path', '.canonical-objects', 'llvm-link', '/native/',
                 'resident-island-seed')

    def __init__(self, out):
        self.out, self.rows, self.host_binary, self.active = out, [], None, True
        self.compiler = str(ROOT / 'tools/llvm-mos/bin/mos-mega65-clang')
        self.temporary = Path(tempfile.gettempdir()).resolve()

    def classify(self, command):
        command = [str(x) for x in command]
        if command[:len(P.S.PRIORITY)] == list(P.S.PRIORITY):
            command = command[len(P.S.PRIORITY):]
        assert command, 'empty command'
        tool = Path(command[0])
        if tool.parent == ROOT / 'tools/llvm-mos/bin' and tool.name in P.READ_ONLY_ELF_TOOLS:
            return 'ELF-extraction' if tool.name == 'llvm-objcopy' else 'ELF-read-only'
        text = ' '.join(command)
        if command[0] == self.compiler or (command[:1] == ['/usr/bin/setarch'] and len(command) > 3 and command[3] == self.compiler):
            assert not any(token in text for token in self.FORBIDDEN), 'continuation refuses a product compile/link'
            target = (ROOT / command[command.index('-o') + 1]).resolve()
            assert target.is_relative_to(self.out / CFG.MEDIA_DIR), 'stager output outside the media directory'
            assert sum(1 for r in self.rows if r['kind'] == 'cold-stager') < 4, 'more than the four cold stager commands'
            return 'cold-stager'
        if command[0] in ('cc', '/usr/bin/cc'):
            assert '-DLISP65_C2_LITE_MEDIA_STAGER' in command and self.host_binary is None, 'unexpected host compiler run'
            target = Path(command[command.index('-o') + 1]).resolve()
            assert target.is_relative_to(self.temporary), 'host emitter outside the temporary directory'
            self.host_binary = str(target)
            return 'host-ABI-compile'
        if self.host_binary is not None and command == [self.host_binary] and \
                not any(r['kind'] == 'host-ABI-emitter' for r in self.rows):
            return 'host-ABI-emitter'
        raise AssertionError('continuation refuses this process: ' + repr(command)[:400])

    def audit(self, event, args):
        if not self.active:
            return
        if event == 'subprocess.Popen':
            kind = self.classify(args[1])
            self.rows.append(dict(kind=kind, command=[str(x) for x in args[1]]))

    def counts(self):
        out = {}
        for row in self.rows:
            out[row['kind']] = out.get(row['kind'], 0) + 1
        return out


# ----------------------------------------------------------- continuation
STATEMENT = ('This Seed CONTINUES attempt build/card-254-product-r1 after a reviewed HALT. r1 ran all 75 frozen '
             'commands including the ONE product link and halted in the post-link inventory '
             '(unclassified allocated-section change in .lisp65_rt_c2d_00b). The reviewer accepted ONE new pinned '
             'attribution class, "reviewed commuting adjacent pair" (c2_stream_phase_00b at 0xc473: '
             'sta $a ; clc -> clc ; sta $a), and this continuation completed inventory, media and receipts. '
             'No product object was compiled and nothing was linked here: product_links counts the r1 link; '
             'ELF, PRG and LTO object are byte-identical copies of the r1 link outputs.')


def continuation(out, dry):
    """inventory + media + finish of the halted r1 attempt into `out` (write-once)."""
    pre, e3_receipt, view = entry_checks()
    selftest = selftest_dir() / 'receipt.json'
    assert selftest.is_file(), 'run `c254_seed_continue_r1b.py selftest` first (receipt of THIS tool file missing)'
    tested = P.load(selftest)
    assert tested['status'] == 'PASS' and tested['tool'] == P.bind(TOOL) and tested['seed_tools'] == P.tool_identity(), \
        'continuation selftest does not bind these tool bytes'
    assert not os.path.lexists(out), 'write-once continuation directory already claimed; no retry'
    r1 = ROOT / R1_NAME
    processes = Processes(out)
    P.guard(out, host_only=False)                 # same write boundary as the Seed: `out` and the temp directory
    sys.addaudithook(processes.audit)
    out.mkdir()
    here = out / 'native'
    try:
        binding = r1_binding(view)
        P.save(out / 'attempt.json', dict(
            status='DRY-CONTINUATION' if dry else 'CONTINUATION', continues=binding,
            tools=P.tool_identity(), continuation_tool=P.bind(TOOL), continuation_selftest=P.bind(selftest),
            authority=P.source_revision(), predecessor=P.bind(P.BASE / 'complete.json'),
            preflight=P.bind(P.PREFLIGHT / 'receipt.json'), e3=e3_receipt))
        if dry:
            P.once(out / 'NOT-A-PRODUCT.txt', 'DRY rehearsal of the 2.5.4 Seed continuation r1b. Not a Seed, not a deliverable.\n')
        carried = []
        for name in CARRIED:
            raw = (r1 / name).read_bytes()
            assert P.sha(raw) == R1_PINS[name], ('r1 file drift while carrying', name)
            P.once(out / name, raw)
            carried.append(dict(source=P.bind(r1 / name), copy=P.bind(out / name)))
            assert carried[-1]['source']['sha256'] == carried[-1]['copy']['sha256'] == R1_PINS[name]
        P.save(out / 'linked.json', dict(
            status='CARRIED', product_links=1, ELF=P.bind(out / ELF_NAME),
            linked_in=P.bind(r1 / 'linked.json'), claim=P.bind(r1 / 'product-link-claim.json'),
            note='The ONE product link ran in ' + R1_NAME + '; this ELF is its byte-identical copy. No link ran here.'))
        with patch.object(P, 'BUILD', out), patch.object(P, 'HERE', here):
            with reviewed_pair_class() as state:
                inv = P.inventory()
            assert inv['status'] == 'PASS' and inv['unclassified_bytes'] == 0 and inv['price']['text_delta'] == 0
            assert not inv['text']['changed'] and inv['price']['text_bytes'] == CFG.BASE_TEXT_BYTES
            assert [r['section'] for r in inv['protected'] if CLASS in r['by']] == [PAIR['section']]
            assert all(r['explained'] for r in inv['protected'])
            print('continuation: inventory PASS (one reviewed pair, every other byte classified)', flush=True)
            medium = P.media()
            stager = P.load(out / CFG.MEDIA_DIR / 'descriptor-stager-receipt.json')
            assert stager['status'] == 'PASS' and stager['product_links'] == 0 and stager['stager_builds'] == 1
            counts = processes.counts()
            assert counts.get('cold-stager') == 4, ('cold stager recipe', counts)
            print('continuation: media PASS', flush=True)
            P.save(out / 'continuation.json', dict(
                status='PASS', dry=dry, statement=STATEMENT, continues=binding, carried=carried,
                reviewed_class=state['proof'], class_pin={k: (list(v) if isinstance(v, tuple) else v) for k, v in PAIR.items()},
                tool=P.bind(TOOL), selftest=P.bind(selftest), seed_tools=P.tool_identity(),
                functions=['c254_product.inventory', 'c254_product.media', 'c254_product.finish'],
                wrapped=['c254_product.data_attribution'],
                product_compiles=0, product_links_here=0, product_links_of_the_attempt=1, stager_builds=1,
                processes=dict(counts=counts, rows=processes.rows),
                inventory=P.bind(here / 'inventory.json'), media=P.bind(out / 'media.json')))
            extra = dict(
                continues=dict(statement=STATEMENT, attempt=R1_NAME, halt=dict(P.bind(r1 / 'halt.json'), error=R1_HALT['error']),
                               product_link_claim=P.bind(r1 / 'product-link-claim.json'), linked=P.bind(r1 / 'linked.json'),
                               reviewed_class=dict(name=CLASS, section=PAIR['section'], function=PAIR['function'],
                                                   address=f"0x{PAIR['address']:04x}", before=list(PAIR['old_text']),
                                                   after=list(PAIR['new_text'])),
                               tool=P.bind(TOOL), record=P.bind(out / 'continuation.json'),
                               product_links_here=0, dry=dry))
            real_save = P.save

            def save(path, value):
                # finish() is unchanged; its two final receipts additionally say what this Seed is.
                if Path(path).parent == out and Path(path).name in ('seed.json', 'complete.json'):
                    assert not set(extra) & set(value)
                    value = dict(value, **extra)
                real_save(path, value)
            with patch.object(P, 'save', save):
                done = P.finish(pre, rehearsal=dry)
        complete = P.load(out / 'complete.json')
        assert (out / 'seed.json').read_bytes() == (out / 'complete.json').read_bytes()
        assert complete['continues']['attempt'] == R1_NAME and complete['ELF']['sha256'] == R1_PINS[ELF_NAME]
        assert complete['status'] == ('REHEARSAL-NOT-A-PRODUCT' if dry else 'PASS') == done['status']
        assert complete['product_links'] == (0 if dry else 1)
        assert r1_problems(r1_view(), e3_receipt, pre['source_revision']) == [], 'r1 changed during the continuation'
        return dict(status=complete['status'], out=str(out.relative_to(ROOT)), medium=complete['medium'],
                    ELF=complete['ELF'], text_bytes=inv['price']['text_bytes'],
                    build_id=f"0x{P.load(out / CFG.MEDIA_DIR / 'runtime-receipt.json')['product_build_id']:08x}",
                    changed_files=medium['changed_files'], unclassified_bytes=medium['unclassified_bytes'],
                    reviewed_class=state['proof']['class'], processes=counts)
    except BaseException as error:
        if not (out / 'halt.json').exists():
            P.save(out / 'halt.json', dict(status='HALT', error=repr(error), product_links_here=0,
                                           note='Continuation halted. No in-place retry; review a named successor.'))
        raise
    finally:
        processes.active = False


# ---------------------------------------------------------------- selftest
def selftest():
    """Negative controls: the class accepts the pinned pair only, and the r1 binding notices every drift."""
    from elf_truth import ElfTruth
    pre, e3_receipt, view = entry_checks()
    out = selftest_dir()
    assert not os.path.lexists(out), 'selftest receipt of this tool file already exists (write-once): ' + str(out.relative_to(ROOT))
    P.guard(out, host_only=False)
    out.mkdir(parents=True)
    rejected, passed = [], []

    def reject(name, fn, needle=None):
        try:
            fn()
        except AssertionError as error:
            assert needle is None or needle in repr(error), ('rejected for another reason', name, repr(error)[:300])
            rejected.append(name)
        else:
            raise AssertionError('negative survived: ' + name)
    paths = [P.BASE / ELF_NAME, ROOT / R1_NAME / ELF_NAME]
    a, b = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]
    const = P.load(P.PREFLIGHT / 'constants.json')
    header_pairs = P.header_value_pairs(P.load(ROOT / R1_NAME / 'native/derived-inputs.json'))
    patterns, allowed = P.constant_patterns(const, header_pairs), P.immediate_pairs(const, header_pairs)
    original = P.data_attribution
    name, at = PAIR['section'], PAIR['offset']
    with patch.object(P, 'HERE', out / 'native'):
        listing = P.Listings()
        run = lambda after, pin=PAIR, state=None, files=paths: reviewed_data_attribution(
            original, state if state is not None else dict(applied=0, proof=None), pin)(
                a, after, patterns, allowed=allowed, listing=listing, paths=files, changed=frozenset())
        # 0. the halt reproduces: the unchanged function refuses exactly r1's section list.
        reject('unchanged data_attribution reproduces the r1 halt',
               lambda: original(a, b, patterns, allowed=allowed, listing=listing, paths=paths, changed=frozenset()),
               repr(R1_HALT_SECTIONS))
        # 1. positive: the real pair, every other byte left to the unchanged function.
        state = dict(applied=0, proof=None)
        rows = run(b, state=state)
        row = next(r for r in rows if r['section'] == name)
        assert state['applied'] == 1 and row['explained'] and row['by'][-1] == CLASS and all(r['explained'] for r in rows)
        assert row['reviewed_pair']['other_changed_bytes_in_section'] == 4
        passed.append('real r1 pair accepted; 4 remaining bytes classified immediate by the unchanged function')
        reject('second application in one inventory', lambda: run(b, state=state), 'one application')
        # 2. end to end on mutated `after` bytes (proxy over the real ELF; listings stay the real ones).
        real = b.section_bytes(name)
        old = a.section_bytes(name)

        def mutated(edit):
            data = bytearray(real); edit(data)
            return NeutralTruth(b, name, bytes(data), {})

        def poke(offset, value):
            def edit(data):
                assert data[offset] != value
                data[offset] = value
            return edit
        base_rows = listing(paths[1], name, PAIR['function_value'], PAIR['function_value'] + PAIR['function_bytes'])
        far_opcode = next(p for p in sorted(base_rows) if p > PAIR['address'] + 0x100 and len(base_rows[p][0]) == 1) - PAIR['section_address']
        reject('third changed byte far from the pair (a one-byte opcode)',
               lambda: run(mutated(poke(far_opcode, real[far_opcode] ^ 0x01))), 'unclassified allocated-section change')
        reject('third changed byte directly after the pair (adc opcode)', lambda: run(mutated(poke(at + 3, 0x65))))
        reject('third changed byte directly before the pair (pla opcode)', lambda: run(mutated(poke(at - 1, 0x48))))
        reject('other bytes at the pinned offset (operand $a -> $b)', lambda: run(mutated(poke(at + 2, 0x0b))), 'new bytes')
        reject('pair not swapped at the pinned offset', lambda: run(NeutralTruth(b, name, bytes(old), {})), 'new bytes')
        # the same kind of swap at ANOTHER place (0xc464: 84 0c sty ; 18 clc), pinned place restored
        other = old.find(bytes.fromhex('840c18'))
        assert other >= 0 and other != at

        def swap_elsewhere(data):
            data[at:at + 3] = old[at:at + 3]
            data[other:other + 3] = bytes.fromhex('18840c')
        reject('adjacent pair swapped at another offset only', lambda: run(mutated(swap_elsewhere)), 'new bytes')

        def swap_both(data):
            data[other:other + 3] = bytes.fromhex('18840c')
        reject('pinned pair plus a second swapped pair', lambda: run(mutated(swap_both)),
               'unclassified allocated-section change')
        reject('before ELF is not the pinned 2.5.3 ELF', lambda: run(b, files=[paths[1], paths[1]]), 'before ELF')
        reject('after ELF is not the pinned r1 link', lambda: run(b, files=[paths[0], paths[0]]), 'after ELF')
        # 3. pure controls on the facts of the real pair.
        base = facts(a, b, listing, paths)
        pair_proof(PAIR, base)
        passed.append('pair_proof accepts the real facts')

        def with_facts(**change):
            return lambda: pair_proof(PAIR, dict(base, **change))

        def with_pin(**change):
            return lambda: pair_proof(dict(PAIR, **change), base)
        lo = PAIR['address']
        reject('pin at another offset', with_pin(offset=at + 1, address=lo + 1))
        reject('pin with other old bytes', with_pin(old='850b18'), 'old bytes')
        reject('pin with other new bytes', with_pin(new='18850b'), 'new bytes')
        reject('pin with other disassembly text (before)', with_pin(old_text=('c473: 85 0a sta $a', 'c475: 18 clc')), 'pinned text')
        reject('pin with other disassembly text (after)', with_pin(new_text=('c473: 18 clc', 'c474: 85 0a sta $b')), 'pinned text')
        reject('other section name', with_facts(section='.lisp65_rt_c2d_00'), 'other section')
        reject('section at another address', with_facts(address=0xc357))
        reject('section of another size', with_facts(old=old + b'\0', new=real + b'\0'))
        reject('other containing function', with_facts(function_a=('eval_init', 0xc356, 0x61f)), 'containing function')

        def synthetic(first, second):
            # a pair that is NOT the pinned one, at the pinned offset, in both sides
            o = bytearray(old); n = bytearray(real)
            o[at:at + 3] = first; n[at:at + 3] = second
            return dict(old=bytes(o), new=bytes(n))
        reject('another pair at the pinned offset (stx $a ; clc)', with_facts(**synthetic(bytes.fromhex('860a18'), bytes.fromhex('18860a'))))
        reject('another pair at the pinned offset (sta $a ; sec)', with_facts(**synthetic(bytes.fromhex('850a38'), bytes.fromhex('38850a'))))
        for label, pin_old, pin_new in (('adc #imm ; clc does not commute (opcode outside the table)', '691018', '186910'),
                                        ('lda $a ; clc (opcode outside the table)', 'a50a18', '18a50a')):
            reject(label, lambda pin_old=pin_old, pin_new=pin_new: pair_proof(
                dict(PAIR, old=pin_old, new=pin_new), dict(base, **synthetic(bytes.fromhex(pin_old), bytes.fromhex(pin_new)))),
                'opcode outside the reviewed table')
        assert commute(EFFECTS[0x85], EFFECTS[0x18]) and not commute(
            dict(reads=frozenset('AC'), writes=frozenset('AC')), EFFECTS[0x18]), 'commute() must refuse adc ; clc'
        passed.append('commute(): sta/clc commute, adc/clc do not')
        rows_b = dict(base['rows_b'])
        rows_b[lo + 1] = (rows_b[lo + 1][0], 'stx', rows_b[lo + 1][2])
        reject('listing shows another mnemonic', with_facts(rows_b=rows_b))
        rows_b = dict(base['rows_b']); rows_b[lo + 3] = (bytes.fromhex('6911'), 'adc', '#$11')
        reject('instruction after the pair differs', with_facts(rows_b=rows_b), 'after the pair')
        rows_b = dict(base['rows_b']); moved = rows_b.pop(0xc478); rows_b[0xc479 + 0x100] = moved
        reject('instruction boundary moved elsewhere', with_facts(rows_b=rows_b), 'boundaries')
        rows_b = dict(base['rows_b']); far = max(p for p in rows_b if p < lo - 0x20 and rows_b[p][1] == 'beq')
        rows_b[far] = (rows_b[far][0], 'beq', f'${lo + 1:x} <x>')
        reject('branch into the pair', with_facts(rows_b=rows_b), 'operand names an address inside the pair')
        rows_a = dict(base['rows_a']); rows_a[far] = (rows_a[far][0], 'beq', f'${lo + 2:x} <x>')
        reject('branch into the pair (before side)', with_facts(rows_a=rows_a), 'operand names an address inside the pair')
        reject('symbol inside the pair', with_facts(symbols_b=base['symbols_b'] + [('label', lo + 1, 0, 'None')]), 'symbol inside')
        reject('symbol population differs', with_facts(symbols_b=base['symbols_b'] + [('label', 0xc400, 0, 'None')]), 'symbols of the section')
        reject('relocation resolves into the pair', with_facts(inbound_b=[('.rodata', 0x1000, 'R_MOS_ADDR16', name, at + 1)]),
               'resolves into the pair')
        rel_b = dict(base['rel_b']); rel_b[PAIR['old_relocation_at']] = rel_b.pop(PAIR['new_relocation_at'])
        reject('relocation did not move with the instruction', with_facts(rel_b=rel_b), 'relocation after')
        rel_b = dict(base['rel_b']); rel_b[PAIR['new_relocation_at']] = ('R_MOS_ADDR8', '__rc9', 0)
        reject('relocation target changed', with_facts(rel_b=rel_b), 'relocation after')
        rel_b = dict(base['rel_b']); rel_b[lo] = ('R_MOS_ADDR8', '__rc8', 0)
        reject('second relocation inside the pair', with_facts(rel_b=rel_b), 'relocation after')
        rel_b = dict(base['rel_b']); rel_b.pop(next(p for p in sorted(rel_b) if p > lo + 8))
        reject('another relocation of the section changed', with_facts(rel_b=rel_b), 'another relocation')
        # 4. the context manager: needed exactly once.
        def unused():
            with reviewed_pair_class():
                pass
        reject('class installed but not applied', unused, 'not applied exactly once')
    # 5. r1 binding.
    assert r1_problems(view, e3_receipt, pre['source_revision']) == []
    passed.append('r1 binding holds on the retained attempt')
    import copy

    def drift(label, edit, needle):
        v = copy.deepcopy(view); edit(v)
        found = r1_problems(v, e3_receipt, pre['source_revision'])
        assert any(needle in x for x in found), ('binding drift not noticed', label, found)
        rejected.append('r1 binding: ' + label)
    for pinned in R1_PINS:
        drift('file drift ' + pinned, lambda v, pinned=pinned: v['files'].__setitem__(pinned, '0' * 64), 'r1 file drift: ' + pinned)
    drift('file missing', lambda v: v['files'].__setitem__('halt.json', None), 'r1 file drift: halt.json')
    drift('r1 already has complete.json', lambda v: v['present'].append('complete.json'), 'not a halted post-link attempt')
    drift('r1 has a medium', lambda v: v['present'].append(CFG.MEDIA_DIR), 'not a halted post-link attempt')
    drift('command log missing', lambda v: v['logs'].pop(), '75 command logs')
    drift('Seed tool edited (product)', lambda v: v['tools_now']['product'].__setitem__('sha256', '0' * 64), 'four tools r1 recorded')
    drift('Seed tool edited (config)', lambda v: v['tools_now']['config'].__setitem__('sha256', '0' * 64), 'four tools r1 recorded')
    drift('fifth Seed tool member', lambda v: v['tools_now'].__setitem__('extra', {}), 'four tools r1 recorded')
    drift('selftest of other tools', lambda v: v['selftest']['tools']['e3'].__setitem__('sha256', '0' * 64), 'since selftest')
    drift('authority moved', lambda v: v['authority_now'].__setitem__('authority', '0' * 40), 'authority')
    drift('consumed root moved', lambda v: v['authority_now']['root_trees'].__setitem__('lib', '0' * 40), 'authority')
    drift('other preflight', lambda v: v['preflight_bind'].__setitem__('sha256', '0' * 64), 'another preflight')
    drift('other E3 receipt', lambda v: v['attempt']['e3'].__setitem__('sha256', '0' * 64), 'another exhaustive E3')
    drift('other predecessor', lambda v: v['predecessor_bind'].__setitem__('sha256', '0' * 64), 'another predecessor')
    drift('two product links claimed', lambda v: v['claim'].__setitem__('product_links', 2), 'one frozen product link')
    drift('claimed command is not recipe command 74', lambda v: v['claim']['command'].append('-Wl,--icf=none'), 'one frozen product link')
    drift('linked.json names another ELF', lambda v: v['linked']['ELF'].__setitem__('sha256', '0' * 64), 'linked.json')
    drift('linked.json counts two links', lambda v: v['linked'].__setitem__('product_links', 2), 'linked.json')
    drift('another halt', lambda v: v['halt'].__setitem__('error', "AssertionError('other')"), 'not the reviewed halt')
    drift('halt without a claimed link', lambda v: v['halt'].__setitem__('product_link_claimed', False), 'not the reviewed halt')
    drift('config names another Seed', lambda v: v.__setitem__('config_seed', 'build/card-254-product-r2'), 'c254_config.SEED')
    drift('config gate has another problem', lambda v: v['config_gate']['problems'].append('x'), 'seed gate')
    # 6. process boundary.
    probe = Processes(ROOT / OUT_NAME)
    link = json.loads((ROOT / R1_NAME / 'product-link-claim.json').read_text())['command']
    recipe = json.loads((ROOT / R1_NAME / 'native/command-proof.json').read_text())['commands']
    reject('the product link is refused', lambda: probe.classify(link), 'refuses a product compile/link')
    reject('the product link under nice/ionice is refused', lambda: probe.classify(list(P.S.PRIORITY) + link), 'refuses a product compile/link')
    reject('a product compile is refused', lambda: probe.classify(recipe[0]))
    reject('llvm-link is refused', lambda: probe.classify(recipe[73]))
    reject('a shell is refused', lambda: probe.classify(['/bin/sh', '-c', 'true']), 'refuses this process')
    reject('a stager output outside the media directory is refused',
           lambda: probe.classify([probe.compiler, '-c', 'scripts/r3-rom-write-enable.s', '-o', 'build/x.o']), 'outside the media directory')
    assert probe.classify([str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d', 'x']) == 'ELF-read-only'
    assert not probe.rows
    result = dict(status='PASS', tool=P.bind(TOOL), seed_tools=P.tool_identity(), rejected=rejected, passed=passed,
                  negative_controls=len(rejected), class_pin={k: (list(v) if isinstance(v, tuple) else v) for k, v in PAIR.items()},
                  r1=R1_NAME, product_links=0, media_transactions=0)
    P.save(out / 'receipt.json', result)
    return dict(status='PASS', negative_controls=len(rejected), passed=passed, receipt=str((out / 'receipt.json').relative_to(ROOT)))


def check():
    """Read-only: the r1 binding and the pair facts on the real ELFs (objdump output is not logged)."""
    import subprocess
    from elf_truth import ElfTruth
    pre, e3_receipt, view = entry_checks()
    paths = [P.BASE / ELF_NAME, ROOT / R1_NAME / ELF_NAME]
    a, b = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]

    def listing(elf, section, start, stop):
        raw = subprocess.run([str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d', '--section=' + section,
                              '--start-address=' + str(start), '--stop-address=' + str(stop), str(elf)],
                             cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout.decode()
        rows = {}
        for line in raw.splitlines():
            m = P.IMMEDIATE_LINE.match(line)
            if m:
                rows[int(m[1], 16)] = (bytes.fromhex(m[2].replace(' ', '')), m[3], m[4].strip())
        return rows
    assert [P.sha(p.read_bytes()) for p in paths] == [PAIR['base_elf'], PAIR['new_elf']]
    _neutral, _moved, proof = pair_proof(PAIR, facts(a, b, listing, paths))
    return dict(status='PASS', r1=R1_NAME, r1_binding='bound', reviewed_class=proof,
                selftest_receipt=str((selftest_dir() / 'receipt.json').relative_to(ROOT)),
                selftest_present=(selftest_dir() / 'receipt.json').is_file(),
                official_output=OUT_NAME, official_output_free=not os.path.lexists(ROOT / OUT_NAME))


def emit():
    """Read-only: the Final pin values of the finished continuation (see the notes for where they go)."""
    seed = ROOT / OUT_NAME
    complete = json.loads((seed / 'complete.json').read_text())
    assert complete['status'] == 'PASS' and complete['product_links'] == 1 and not (seed / 'halt.json').exists()
    assert complete['continues']['attempt'] == R1_NAME
    attempt = json.loads((seed / 'attempt.json').read_text())
    lines = [f"SEED_NAME = '{OUT_NAME}'",
             f"SEED_LINK_NAME = '{R1_NAME}'",
             f"SEED_RECEIPT_SHA = '{CFG.sha256_file(seed / 'seed.json')}'",
             f"RECIPE_SHA = '{CFG.sha256_file(seed / 'native/command-proof.json')}'",
             'ARTIFACT_SHA = dict(' + ', '.join(f"{k}='{CFG.sha256_file(seed / CFG.ARTIFACT_PATH[k])}'"
                                                 for k in sorted(CFG.ARTIFACT_PATH)) + ')',
             'SEED_TOOL_SHA = dict(' + ', '.join(f"{k}='{attempt['tools'][k]['sha256']}'"
                                                  for k in ('config', 'producer', 'product', 'e3')) + ')',
             f"SEED_CONTINUE_TOOL_SHA = '{attempt['continuation_tool']['sha256']}'",
             f"SEED_CONTINUATION_SHA = '{CFG.sha256_file(seed / 'continuation.json')}'",
             f"E3_RECEIPT_SHA = '{attempt['e3']['sha256']}'"]
    assert CFG.sha256_file(seed / 'native/command-proof.json') == R1_PINS['native/command-proof.json']
    return dict(status='PASS', seed=OUT_NAME, link_attempt=R1_NAME, assignments=lines)


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    assert not sys.flags.optimize, 'assertions are mandatory'
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['check', 'selftest', 'dry', 'continue', 'emit'])
    parser.add_argument('--suffix', default='', help='dry only: directory suffix ([a-z0-9]{0,4})')
    args = parser.parse_args()
    assert not CFG.DRY, 'C254_DRY_WORKTREE is the pre-link dry chain; this tool continues the real r1 attempt'
    assert re.fullmatch('[a-z0-9]{0,4}', args.suffix) and (args.action == 'dry' or not args.suffix)
    assert CFG.SEED == R1_NAME and P.BUILD == ROOT / R1_NAME
    if args.action == 'emit':
        print(json.dumps(emit(), indent=2)); return
    CFG.verify_authority()   # read-only git queries BEFORE any audit hook is installed
    CFG.prime_era()
    if args.action == 'check':
        result = check()
    elif args.action == 'selftest':
        result = selftest()
    else:
        dry = args.action == 'dry'
        out = ROOT / ((DRY_PREFIX + args.suffix) if dry else OUT_NAME)
        assert out.parent == ROOT / 'build' and out != ROOT / R1_NAME
        result = continuation(out, dry)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
