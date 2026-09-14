#!/usr/bin/env python3
"""Bound E000 input-member placement, derived from consumed input objects.

Only the commissioned minibuffer producer calls this transformation. Historical
producers keep their old layout. No source size is guessed from a code listing.
"""
from __future__ import annotations
import re
from pathlib import Path
from elf_truth import ElfTruth

PREFIX = '.lisp65_c2_kernal_window.'

def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'encoded input predecessor drift: {old[:100]}')
    return text.replace(old, new, 1)

def derive_sizes(objects: list[Path], readobj: Path) -> dict[str, int]:
    members = {}
    for path in objects:
        truth = ElfTruth.read(path, llvm_readobj=readobj)
        for section in truth.sections:
            if section.name.startswith(PREFIX) and section.bytes:
                if section.name in members:
                    raise ValueError(f'duplicate input owner: {section.name}')
                members[section.name] = section.bytes
    for name in ('input_capture_main', 'input_capture_helper', 'input_consumer', 'typed_queue_driver'):
        if PREFIX+name not in members:
            raise ValueError(f'missing input owner: {name}')
    return members

def transform(text: str, members: dict[str,int], baseline: ElfTruth) -> str:
    p=PREFIX
    helper=p+'input_capture_helper';main=p+'input_capture_main'
    consumer=p+'input_consumer';gap=p+'reopen_gap1'
    # Move the helper into gap0 and place the scalar reader alone in gap1.
    for section, previous, successor in ((helper,gap,main),(consumer,helper,gap)):
        old=f'''{section}
        ADDR({previous}) +
        SIZEOF({previous}) :'''
        new=f'''{section}
        ADDR({successor}) +
        SIZEOF({successor}) :'''
        text=replace_once(text,old,new)

    start=text.index(f'ASSERT(SIZEOF({helper}) == 40 &&')
    end=text.index('"Comfort input capture helper escaped its final-image-derived hole");',start)
    end+=len('"Comfort input capture helper escaped its final-image-derived hole");')
    old=text[start:end]
    new=old.replace(f'SIZEOF({helper}) == 40',f'SIZEOF({helper}) == {members[helper]}')
    new=new.replace(f'ADDR({gap})',f'ADDR({main})').replace(f'SIZEOF({gap})',f'SIZEOF({main})')
    new=new.replace(f'ADDR({p}state)',f'ADDR({p}session_emitter_state)')
    text=replace_once(text,old,new)

    start=text.index(f'ASSERT(SIZEOF({consumer}) > 0 &&')
    end=text.index('"adaptive input consumer escaped its final-image-derived hole");',start)
    end+=len('"adaptive input consumer escaped its final-image-derived hole");')
    old=text[start:end]
    new=old.replace(f'ADDR({helper})',f'ADDR({gap})').replace(f'SIZEOF({helper})',f'SIZEOF({gap})')
    text=replace_once(text,old,new)

    # Both historical assertions protect aggregate free space. Neither may
    # count the newly occupied helper bytes as a gap, or count the same gap twice.
    for message in ('adaptive input capture breached the 54-byte floor plus 3-byte watch',
                    'adaptive input consumer breached the 54-byte floor plus 3-byte watch'):
        pattern=r'ASSERT\(\(ADDR\('+re.escape(p+'profile_rodata')+r'\)[^;]+"'+re.escape(message)+r'"\);'
        matches=list(re.finditer(pattern,text));
        if len(matches)!=1:raise ValueError('capture watch population drift')
        new=f'''ASSERT((ADDR({p}profile_rodata) - (ADDR({helper}) + SIZEOF({helper}))) +
       (ADDR({p}state) - (ADDR({consumer}) + SIZEOF({consumer}))) >= 57,
       "{message}");'''
        text=text[:matches[0].start()]+new+text[matches[0].end():]

    population=[s for s in baseline.sections if s.name.startswith(p) or s.name=='.lisp65_c2_vectors']
    placed={s.name for s in population}
    allocated={s.name for s in baseline.sections if 'SHF_ALLOC' in s.flags and s.bytes and 0xe000<=s.address<0x10000}
    if not allocated <= placed:raise ValueError('unowned predecessor E000 section')
    if not set(members) <= placed:raise ValueError('unregistered new E000 input owner')
    text+='\n/* Minibuffer encoded-input owner floors; no BSS tenant. */\n'
    total=' + '.join(f'SIZEOF({s.name})' for s in population)
    text+=f'ASSERT(8192 - ({total}) >= 54, "encoded input E000 total floor 54");\n'
    for name in (main,helper,consumer,p+'typed_queue_driver'):
        text+=f'ASSERT(SIZEOF({name}) == {members[name]}, "encoded input consumed object size: {name}");\n'
        text+=f'''ASSERT(LOADADDR({name}) == ORIGIN(c2_kernal_window_load) + ADDR({name}) - 0xe000,
       "encoded input LMA projection: {name}");\n'''
    return text
