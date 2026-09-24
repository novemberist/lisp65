"""Budget-free link pre-probe for the "undefined symbol at product link" class.

Seed 2 of the boot-time-name-index card failed at product link with
`ld.lld: error: undefined symbol: c2_dma_read_or_abort`, referenced from
`c2_boot_name_index_head_get`, `c2_stream_phase_10b` and `v2_bnx_find` -
because `c2_dma_read_or_abort` (src/c2_platform_dma.c) is `static`: it has
internal linkage and is invisible to translation units compiled elsewhere,
even though its name resolves at source level.

This probe catches that whole error class - not just this one symbol -
before a Seed is spent. It replays every compiler command from a Seed's
`command-proof.json` transcript verbatim (only forcing `-fno-lto -c`, the
same non-LTO object projection the other native-diet probes use), so each
translation unit is compiled exactly as the real Seed would compile it.
It then unions the defined/undefined symbol tables (structured ElfTruth,
c2_elf_truth_migration_gate.py's shared llvm-readobj JSON reader) across
every resulting object and asks, for each undefined reference: is there a global
(external-linkage) definition anywhere in this object set, or a symbol the
project's own linker scripts define/PROVIDE? If neither, and a definition
exists but only with internal (local, lowercase-letter) linkage in some
other translation unit, that is reported as the Seed-2 error class by name:
"internal linkage; unreachable across translation units". Anything else
undefined and undefined everywhere is reported as a plain missing symbol.

Two further admission sources keep the report from drowning in symbols the
real linker resolves for free: (1) the pinned compiler's own platform
archives (`tools/llvm-mos/mos-platform/{mega65,commodore,common}/lib/*.a`,
or whatever `-l`/`-L` the transcript's own link command names) are searched
via ElfTruth (each archive member is extracted with `llvm-ar` and read
individually) for global definitions - crt0/libc/libcrt helpers such as
`memcpy`, `longjmp` or the `__rc*` zero-page registers live there, not in
the transcript's own objects. (2) an optional `--baseline` transcript (the
accepted, actually-linked predecessor world) is run through the identical
pipeline; any finding that also occurs against the baseline is real, but is
*not new* - it is almost always an LTO-only dead-code reference (a symbol
non-LTO sees as undefined because whole-program LTO would have deleted the
unreachable caller before link) - and is reported as "baseline-noise", not
as a FAIL. Only a finding that is undefined against the probed transcript
but was NOT undefined against the baseline fails the gate.

This is strictly a link *pre*-probe: it never runs the linker, never
produces a `.prg`/ELF, and spends no Seed/finale/link budget. LTO-specific
resolution differences (LTO can inline across units and change what ends up
undefined at the IR level), section sizes and overlay placement are not
checked here - see the other native-diet probes and the real link for those.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'tools/host-lisp'
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

COMPILER = ROOT / 'tools/llvm-mos/bin/mos-mega65-clang'
# c2-elf-truth-migration: symbol/section identity for both plain objects and
# archive members is read exclusively through ElfTruth (llvm-readobj JSON) -
# see nm_symbols/archive_global_symbols/diet_reference_symbols/
# _e000_function_symbols below. llvm-ar is still used, but only to list and
# extract archive members (`t`/`p`), never to parse a symbol table by hand;
# each extracted member is then handed to ElfTruth like any other object.
# llvm-objdump remains for opcode-level disassembly in the E000 low-edge
# probe (_e000_kernal_call_edges) and its section-header labels
# (_e000_section_names) - the migration gate (c2_elf_truth_migration_gate.py)
# permits llvm-objdump for instruction bytes; it only forbids llvm-nm/
# llvm-readelf/llvm-size column parsing, and relocations (needed for the
# E000 jsr/jmp edge rule) are not exposed by ElfTruth, so `llvm-objdump -dr`
# stays the source of truth for that one rule.
LLVM_READOBJ = ROOT / 'tools/llvm-mos/bin/llvm-readobj'
LLVM_AR = ROOT / 'tools/llvm-mos/bin/llvm-ar'
# Narrow, documented exception discovered while migrating this probe to
# ElfTruth: several of the pinned compiler's own platform archives
# (tools/llvm-mos/mos-platform/{mega65,commodore,common}/lib/*.a - e.g.
# libcrt0.a's exit.c.obj/exit-loop.c.obj) ship members that are LLVM IR
# bitcode, not ELF, because the platform ships them ready for LTO. bitcode
# is not an object file at all (no ELF header, no llvm-readobj JSON, no
# ELF section/symbol/relocation tables to be truthful about), so ElfTruth
# structurally cannot read it - `llvm-readobj --elf-output-style=JSON` on a
# bitcode input returns an empty document with a
# "bitcode files are not supported" warning, and `llvm-objdump` refuses it
# outright, so there is no ElfTruth-compatible or objdump path here either.
# llvm-nm is the one LLVM tool that still resolves a bitcode module's own
# embedded symbol table. See _is_llvm_bitcode/_bitcode_defined_global_symbols
# below: it is used only after a member is proven (by its bitcode magic
# bytes, not by a failed parse) to be un-ELF-able. `--format=just-symbols`
# was tried first and rejected: it lists every *defined* name (verified
# against libprintf_flt.a's printf.cc.obj, whose C++ anonymous-namespace
# helpers such as `_ZN12_GLOBAL__N_1...` are internal-linkage but still
# "defined"), so it cannot tell local from external linkage and would
# over-admit local names as if the real linker could see them from any
# object. The default columnar `llvm-nm` output is kept instead, purely to
# read that single local/global type-letter distinction back out -
# identical to the tri-state this migration replaced everywhere else, but
# confined here to inputs ElfTruth cannot open at all.
LLVM_NM = ROOT / 'tools/llvm-mos/bin/llvm-nm'
DIET_REFERENCE_ELF = ROOT / 'build/native-diet-product-r4/wplto/resident-island-seed.prg.elf'

_BITCODE_MAGIC = b'BC\xc0\xde'
_BITCODE_WRAPPER_MAGIC = b'\xde\xc0\x17\x0b'
# nm type letters that mean "external-linkage definition" - the same set
# _classify_symbols distinguishes via ElfTruth's Binding field, kept here
# only for the bitcode fallback below.
_BITCODE_GLOBAL_TYPES = frozenset('TDBRAWCNiu')


def _is_llvm_bitcode(path):
    """True if `path` is an LLVM bitcode module (plain or wrapped), which
    ElfTruth (llvm-readobj) cannot read because it is not an ELF object."""
    with open(path, 'rb') as handle:
        head = handle.read(4)
    return head in (_BITCODE_MAGIC, _BITCODE_WRAPPER_MAGIC)


def _bitcode_defined_global_symbols(obj_path):
    """The one llvm-nm call left in this file, bounded to LLVM-bitcode
    archive members that ElfTruth cannot parse at all (see LLVM_NM comment
    above)."""
    rc, output = run([str(LLVM_NM), str(obj_path)])
    if rc != 0:
        raise ProbeError('llvm-nm failed on bitcode member ' + str(obj_path) + ':\n' + output)
    defined_global = set()
    for line in output.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 2:
            type_letter, name = parts
        elif len(parts) >= 3:
            type_letter, name = parts[1], parts[-1]
        else:
            continue
        if type_letter in _BITCODE_GLOBAL_TYPES:
            defined_global.add(name)
    return defined_global

# The literal path named in the task does not exist in this working tree;
# these are the actual command-proof.json transcripts of the failed Seed 2
# ("boot-time name index"), in preference order. command-world-xs13nrf3 is
# the one whose driver sha256 matches build/boot-name-index-product-r2/
# seed-invocation.json's driver binding, i.e. it is the exact transcript the
# failed Seed ran.
SEED2_PROOF_CANDIDATES = [
    ROOT / 'build/boot-name-index-product-r2/wplto/command-proof.json',
    ROOT / 'build/boot-name-index-product-r2-preflight/command-world-xs13nrf3/command-proof.json',
    ROOT / 'build/boot-name-index-product-r2-preflight/command-world-onemfols/command-proof.json',
]
SEED2_EXPECTED_FINDING = 'c2_dma_read_or_abort'

# Accepted, actually-linked predecessor world ("SEED EMITTED" native-diet
# r4) - the default --baseline transcript for the r2 gate-sharpening pass.
BASELINE_PROOF = ROOT / 'build/native-diet-product-r4/wplto/command-proof.json'

PLATFORM_LIB_DIRS = [
    ROOT / 'tools/llvm-mos/mos-platform/mega65/lib',
    ROOT / 'tools/llvm-mos/mos-platform/commodore/lib',
    ROOT / 'tools/llvm-mos/mos-platform/common/lib',
]

LLVM_OBJDUMP = ROOT / 'tools/llvm-mos/bin/llvm-objdump'

# ---------------------------------------------------------------------------
# E000 low-edge probe: a second, object-based check alongside the undefined-
# symbol analysis above. The undefined-symbol pass catches "this call can
# never resolve"; this one catches "this call resolves, but to the wrong
# side of the fixed E000 host facade" - the class that sank Seed 3
# (`c2_boot_name_index_head_get`, .lisp65_c2_kernal_window.c2_resident in
# 005-c2_product_runtime.c.o, jumps straight to `c2_boot_name_index_read`,
# an ordinary .text.c2_boot_name_index_read function in
# 004-c2_platform_dma.c.o, instead of through a facade vector).
#
# The real gate (tools/host-lisp/c2_product_substitution_link.py,
# fixed_facade_gate/_classify_fixed_facade_low_edges) only runs after a real
# link, on the final ELF, scanning KERNAL_SECTIONS by disassembling the
# *linked* addresses. This probe runs the same rule earlier and per-object,
# before any link is attempted: for every function whose section is part of
# the KERNAL window family, every jsr/jmp naming a global code address must
# land on (a) a symbol itself defined in a KERNAL-window section somewhere
# in this transcript's object set, (b) one of the fixed host-facade
# vectors, or (c) the one owned IRQ-tail continuation. Anything else is a
# low edge.
#
# KERNAL_SECTIONS provenance: every literal entry in the link tool's own
# KERNAL_SECTIONS list either equals ".lisp65_c2_vectors" or starts with
# ".lisp65_c2_kernal_window." (verified below, fail-closed, against the
# link tool's own source). This probe therefore recognizes the whole
# ".lisp65_c2_kernal_window." section family by prefix - not just the
# literal names present in a plain import of the link tool - because the
# link tool itself grows that family at run time for feature builds
# (configure_e000_reopening/_bss_triage/_append_plan_facade add
# reopen_gap0/1/2; configure_input_capture adds input_capture_main/helper
# and input_consumer) via KERNAL_SECTIONS.append(), and a static import
# without reproducing every feature toggle a given transcript happened to
# select would silently miss those sections. The prefix rule is exactly
# equivalent to the link tool's own list for every combination actually
# observed (see verify_e000_low_edge_rule_bindings).
E000_KERNAL_SECTION_PREFIX = '.lisp65_c2_kernal_window.'
E000_KERNAL_VECTORS_SECTION = '.lisp65_c2_vectors'

SUBSTITUTION_LINK_TOOL = ROOT / 'tools/host-lisp/c2_product_substitution_link.py'

# The fixed host-facade vectors (13 original + 3 formal-reopening/BSS-triage/
# append-plan extensions), and the one owned IRQ-tail exception - literal
# names pinned by the owner-authorized product contract, cross-checked
# below against both the link tool's source and a generated linker script's
# own ASSERT block (build/boot-name-index-product-r3/wplto/c2-substitution.ld
# around line 676) rather than trusted blind.
FIXED_FACADE_VECTOR_SYMBOLS = (
    'c2_facade_vm_code_load',
    'c2_facade_c2_dma',
    'c2_facade_overlay_call_family',
    'c2_facade_c2e_cons',
    'c2_facade_c2e_overlay',
    'c2_facade_car',
    'c2_facade_cdr',
    'c2_facade_gc_collect',
    'c2_facade_str_open',
    'c2_facade_str_putc',
    'c2_facade_intern',
    'c2_facade_select_family',
    'c2_facade_gc_mark',
    'c2_facade_runtime_overlay_exec',
    'c2_facade_handle_normalize',
    'c2_facade_append_plan_walk',
)
IRQ_TAIL_TARGET_SYMBOL = 'retired_window_brk_classifier'
IRQ_TAIL_OWNER_SECTION = '.lisp65_c2_kernal_window.irq_handler'

FACADE_LD_REFERENCE = ROOT / 'build/boot-name-index-product-r3/wplto/c2-substitution.ld'

# Already-compiled r3 object sets (non-LTO objects of the failed Seed-3
# transcript and of its accepted predecessor), reused by the E000 low-edge
# selftests below without recompiling anything.
E000_R3_MAIN_OBJECTS = ROOT / 'build/boot-name-index-link-preprobe-r3/main/objects'
E000_R3_BASELINE_OBJECTS = ROOT / 'build/boot-name-index-link-preprobe-r3/baseline/objects'
E000_EXPECTED_LOW_EDGE = ('c2_boot_name_index_head_get', 'c2_boot_name_index_read')

# Symbol types ElfTruth reports for a file-scoped/section-scoped ELF symbol
# table entry rather than a linkable name; excluded the same way plain
# `llvm-nm` output excludes them from a name/linkage listing.
_NON_LINKAGE_SYMBOL_TYPES = frozenset(['File', 'Section'])


class ProbeError(RuntimeError):
    """Fail-closed: a translation-unit compile failed, or an input was missing."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, cwd=ROOT):
    proc = subprocess.run(command, cwd=str(cwd), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def compile_command_of(command):
    """Split one transcript compiler-invocation into (flags, source, orig_out)."""
    c_idx = command.index('-c')
    o_idx = command.index('-o')
    return command[1:c_idx], command[c_idx + 1], command[o_idx + 1]


def compile_transcript(proof, out_dir):
    """Non-LTO-compile every `-c ... -o ...` command in the transcript.

    Returns the list of compiled objects (as repo-relative path strings).
    Fails closed (raises ProbeError) on the first compiler error, leaving
    whatever was already compiled on disk for inspection.
    """
    objects_dir = out_dir / 'objects'
    objects_dir.mkdir(parents=True, exist_ok=True)
    compile_commands = [c for c in proof['commands'] if '-c' in c and '-o' in c]
    objects = []
    for i, command in enumerate(compile_commands):
        pinned = Path(command[0])
        if pinned.resolve() != COMPILER.resolve():
            raise ProbeError('transcript compiler is not the pinned compiler: '
                             + str(pinned) + ' != ' + str(COMPILER))
        flags, source, _orig_out = compile_command_of(command)
        source_path = (ROOT / source)
        if not source_path.is_file():
            raise ProbeError('transcript source missing from working tree: ' + source)
        stem = Path(source).name
        obj_path = objects_dir / ('%03d-%s.o' % (i, stem))
        log_path = objects_dir / ('%03d-%s.log' % (i, stem))
        if obj_path.exists():
            raise ProbeError('experiment artifact already exists: ' + str(obj_path))
        cc = [str(COMPILER), *flags, '-fno-lto', '-c', source, '-o',
              str(obj_path.relative_to(ROOT))]
        rc, output = run(cc)
        log_path.write_text(output)
        if rc != 0:
            raise ProbeError('compile failed (non-LTO replay) for %s:\n%s' % (source, output))
        objects.append(dict(index=i, source=source,
                            object=str(obj_path.relative_to(ROOT))))
    return objects


def _classify_symbols(symbols):
    """Shared ElfTruth symbol classifier: works for a single object's symbol
    table and (called once per extracted member) for an archive.

    Mirrors the old llvm-nm-column tri-state exactly at the level this probe
    cares about: an ELF section index of SHN_UNDEF is an undefined
    reference (nm type 'U'/'u'/'v'/'w'); STB_LOCAL binding is internal
    linkage (nm's lowercase types); anything else defined (STB_GLOBAL or
    STB_WEAK) is external linkage (nm's uppercase types). File/Section-typed
    entries are dropped the same way a plain `nm` name/linkage listing drops
    STT_FILE/STT_SECTION table entries.
    """
    defined_global, defined_local, undefined = set(), set(), set()
    for symbol in symbols:
        if not symbol.name or symbol.symbol_type in _NON_LINKAGE_SYMBOL_TYPES:
            continue
        if symbol.section == 'Undefined':
            undefined.add(symbol.name)
        elif symbol.binding == 'Local':
            defined_local.add(symbol.name)
        else:
            defined_global.add(symbol.name)
    return defined_global, defined_local, undefined


def nm_symbols(object_path):
    """Return (defined_global, defined_local, undefined) name sets for one object."""
    truth = ElfTruth.read(ROOT / object_path, llvm_readobj=LLVM_READOBJ)
    return _classify_symbols(truth.symbols)


def _run_binary(command):
    proc = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout, proc.stderr


def archive_global_symbols(archive_path):
    """Global (external-linkage) definitions across every member of one .a.

    ElfTruth reads one ELF object at a time (llvm-readobj's JSON is per-file
    and does not understand the archive container), so each member is
    extracted with `llvm-ar p` into a temporary object file and read through
    ElfTruth individually; the per-member global-defined sets are unioned.
    llvm-ar is used only to list (`t`) and extract (`p`) members - it never
    parses a symbol/section table.
    """
    rc, listing = run([str(LLVM_AR), 't', str(archive_path)])
    if rc != 0:
        raise ProbeError('llvm-ar t failed on ' + str(archive_path) + ':\n' + listing)
    members = [line.strip() for line in listing.splitlines() if line.strip()]
    defined_global = set()
    with tempfile.TemporaryDirectory(prefix='elf-truth-archive-member-') as temp:
        for index, member in enumerate(members):
            rc, raw, err = _run_binary([str(LLVM_AR), 'p', str(archive_path), member])
            if rc != 0:
                raise ProbeError('llvm-ar p failed on ' + str(archive_path) + '(' + member + '):\n'
                                 + err.decode('utf-8', 'replace'))
            obj_path = Path(temp) / ('%04d-%s' % (index, Path(member).name))
            obj_path.write_bytes(raw)
            if _is_llvm_bitcode(obj_path):
                # See the LLVM_NM comment above: this member is LTO-ready
                # bitcode, not an ELF object, so ElfTruth cannot read it.
                defined_global |= _bitcode_defined_global_symbols(obj_path)
            else:
                truth = ElfTruth.read(obj_path, llvm_readobj=LLVM_READOBJ)
                g, _local, _undef = _classify_symbols(truth.symbols)
                defined_global |= g
    return defined_global


def platform_archives_for(proof):
    """Archives the pinned compiler would link against for this transcript.

    Prefers explicit `-l`/`-L` tokens from the transcript's own (non-compile)
    commands; falls back to every `.a` under the compiler's default mega65/
    commodore/common sysroot lib directories, which is what actually happens
    here since the driver-level command captured in these transcripts never
    spells out `-lc` etc. explicitly (that only appears inside clang's own
    internal `ld.lld` invocation, which the transcript does not record).
    """
    archives = []
    libdirs = list(PLATFORM_LIB_DIRS)
    explicit = False
    for command in proof['commands']:
        if '-c' in command:
            continue
        i = 0
        while i < len(command):
            token = command[i]
            if token.startswith('-L') and token != '-L':
                libdirs.append((ROOT / token[2:]).resolve())
            elif token == '-L' and i + 1 < len(command):
                libdirs.append((ROOT / command[i + 1]).resolve())
                i += 1
            elif token.startswith('-l:'):
                explicit = True
                for d in libdirs:
                    candidate = Path(d) / token[3:]
                    if candidate.is_file():
                        archives.append(candidate)
                        break
            elif token.startswith('-l') and token != '-l':
                explicit = True
                name = 'lib' + token[2:] + '.a'
                for d in libdirs:
                    candidate = Path(d) / name
                    if candidate.is_file():
                        archives.append(candidate)
                        break
            i += 1
    if not explicit:
        archives = []
        for d in PLATFORM_LIB_DIRS:
            archives.extend(sorted(d.glob('*.a')))
    seen, ordered = set(), []
    for a in archives:
        a = a.resolve()
        if a not in seen:
            seen.add(a)
            ordered.append(a)
    return ordered


def platform_archive_symbols(archives):
    """Union of global definitions across `archives`, plus path/sha256 bindings."""
    symbols = set()
    bindings = []
    for archive in archives:
        symbols |= archive_global_symbols(archive)
        bindings.append(dict(path=str(archive.relative_to(ROOT)), sha256=sha256(archive)))
    return symbols, bindings


LD_ASSIGN_RE = re.compile(r'(?:^|[;{])\s*([A-Za-z_.$][A-Za-z0-9_.$]*)\s*=[^=]', re.MULTILINE)
LD_PROVIDE_RE = re.compile(r'PROVIDE(?:_HIDDEN)?\s*\(\s*([A-Za-z_.$][A-Za-z0-9_.$]*)')


def linker_script_symbols(ld_paths):
    names = set()
    for ld_path in ld_paths:
        if not ld_path.is_file():
            continue
        text = ld_path.read_text()
        names.update(LD_ASSIGN_RE.findall(text))
        names.update(LD_PROVIDE_RE.findall(text))
    return names


def diet_reference_symbols(elf_path):
    """Diagnostic-only: global symbols in the accepted diet world's linked ELF."""
    if not elf_path.is_file():
        return set()
    try:
        truth = ElfTruth.read(elf_path, llvm_readobj=LLVM_READOBJ)
    except Exception:
        return set()
    defined_global, _local, _undef = _classify_symbols(truth.symbols)
    return defined_global


def linker_scripts_for(proof_dir):
    scripts = []
    substitution = proof_dir / 'c2-substitution.ld'
    if substitution.is_file():
        scripts.append(substitution)
    full_map = proof_dir / 'full-map-linker'
    if full_map.is_dir():
        scripts.extend(sorted(full_map.glob('*.ld')))
    return scripts


def analyze(objects, ld_scripts, diet_reference_elf, platform_symbols=frozenset()):
    """Core analysis: union symbol tables across objects, classify each U."""
    defined_global, defined_local = set(), set()
    local_owner = {}  # name -> list of objects defining it only locally
    undefined_refs = {}  # name -> list of referencing objects
    per_object = {}
    for row in objects:
        g, l, u = nm_symbols(row['object'])
        per_object[row['object']] = dict(defined_global=sorted(g), defined_local=sorted(l),
                                         undefined=sorted(u))
        defined_global |= g
        defined_local |= l
        for name in l:
            local_owner.setdefault(name, []).append(row['object'])
        for name in u:
            undefined_refs.setdefault(name, []).append(row['object'])
    ld_symbols = linker_script_symbols(ld_scripts)
    diet_symbols = diet_reference_symbols(diet_reference_elf)

    findings = []
    for name in sorted(undefined_refs):
        if name in defined_global:
            continue
        if name in ld_symbols:
            continue
        if name in platform_symbols:
            continue
        referenced_by = sorted(undefined_refs[name])
        if name in local_owner:
            findings.append(dict(
                symbol=name,
                classification='internal linkage; unreachable across translation units',
                defined_locally_in=sorted(local_owner[name]),
                referenced_by=referenced_by,
                also_in_diet_reference_elf=name in diet_symbols,
            ))
        else:
            findings.append(dict(
                symbol=name,
                classification='undefined; no definition found in this object set, '
                               'linker scripts or platform archives',
                referenced_by=referenced_by,
                also_in_diet_reference_elf=name in diet_symbols,
            ))
    return findings, per_object, sorted(ld_symbols)


def compile_and_analyze(proof_path, out_dir):
    """One full pass: compile a transcript, then analyze its symbol tables.

    Returns a dict with everything build_receipt/baseline-diffing need.
    """
    proof_path = Path(proof_path).resolve()
    proof = json.loads(proof_path.read_text())
    objects = compile_transcript(proof, out_dir)
    ld_scripts = linker_scripts_for(proof_path.parent)
    archives = platform_archives_for(proof)
    platform_symbols, platform_bindings = platform_archive_symbols(archives)
    findings, per_object, ld_symbols = analyze(objects, ld_scripts, DIET_REFERENCE_ELF,
                                               platform_symbols)
    return dict(proof_path=proof_path, objects=objects, ld_scripts=ld_scripts,
               ld_symbols=ld_symbols, platform_archives=archives,
               platform_bindings=platform_bindings,
               platform_symbol_count=len(platform_symbols),
               findings=findings, per_object=per_object)


def build_receipt(out_dir, pass_, baseline_pass=None):
    findings = pass_['findings']
    baseline_symbols = ({f['symbol'] for f in baseline_pass['findings']}
                        if baseline_pass is not None else None)
    annotated = []
    for finding in findings:
        finding = dict(finding)
        finding['baseline_noise'] = (baseline_symbols is not None
                                     and finding['symbol'] in baseline_symbols)
        annotated.append(finding)
    new_findings = [f for f in annotated if not f['baseline_noise']]
    baseline_noise_findings = [f for f in annotated if f['baseline_noise']]
    status = 'FAIL' if new_findings else 'PASS'
    receipt = dict(
        claim='LINK PRE-PROBE ONLY; NO LINKER RUN; NO SEED/FINALE/LINK BUDGET SPENT',
        status=status,
        findings=annotated,
        new_findings=[f['symbol'] for f in new_findings],
        new_findings_count=len(new_findings),
        baseline_noise_symbols=sorted(f['symbol'] for f in baseline_noise_findings),
        baseline_noise_count=len(baseline_noise_findings),
        object_count=len(pass_['objects']),
        objects=[o['object'] for o in pass_['objects']],
        linker_script_symbol_count=len(pass_['ld_symbols']),
        linker_scripts=[str(p.relative_to(ROOT)) for p in pass_['ld_scripts']],
        platform_archive_symbol_count=pass_['platform_symbol_count'],
        bindings=dict(
            command_proof=dict(path=str(pass_['proof_path'].relative_to(ROOT)),
                               sha256=sha256(pass_['proof_path'])),
            compiler=dict(path=str(COMPILER.relative_to(ROOT)), sha256=sha256(COMPILER)),
            # Renamed from the pre-migration `llvm_nm` binding: symbol truth
            # now comes from llvm-readobj (via ElfTruth), not llvm-nm.
            llvm_readobj=dict(path=str(LLVM_READOBJ.relative_to(ROOT)),
                              sha256=sha256(LLVM_READOBJ)),
            platform_archives=pass_['platform_bindings'],
        ),
        per_object_symbols=pass_['per_object'],
    )
    if baseline_pass is not None:
        receipt['baseline'] = dict(
            command_proof=dict(path=str(baseline_pass['proof_path'].relative_to(ROOT)),
                               sha256=sha256(baseline_pass['proof_path'])),
            object_count=len(baseline_pass['objects']),
            finding_symbols=sorted(baseline_symbols),
            finding_count=len(baseline_symbols),
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


# ---------------------------------------------------------------------------
# E000 low-edge probe implementation.

def _is_kernal_window_section(name):
    return name == E000_KERNAL_VECTORS_SECTION or name.startswith(E000_KERNAL_SECTION_PREFIX)


def verify_e000_low_edge_rule_bindings():
    """Fail-closed cross-check: the hardcoded KERNAL-prefix rule and the
    hardcoded facade/IRQ-tail names must still match the link tool's own
    source and a generated linker script, not just this file's comments."""
    if not SUBSTITUTION_LINK_TOOL.is_file():
        raise ProbeError('link tool missing: ' + str(SUBSTITUTION_LINK_TOOL))
    link_tool_src = SUBSTITUTION_LINK_TOOL.read_text()

    block = re.search(r'KERNAL_SECTIONS\s*=\s*\[(.*?)\n\]', link_tool_src, re.DOTALL)
    if not block:
        raise ProbeError('could not locate KERNAL_SECTIONS literal in ' + str(SUBSTITUTION_LINK_TOOL))
    profile_rodata_m = re.search(r'PROFILE_RODATA_SECTION\s*=\s*"([^"]+)"', link_tool_src)
    if not profile_rodata_m:
        raise ProbeError('could not locate PROFILE_RODATA_SECTION in ' + str(SUBSTITUTION_LINK_TOOL))
    profile_rodata = profile_rodata_m.group(1)

    literal_sections = []
    for raw_line in block.group(1).splitlines():
        entry = raw_line.strip().rstrip(',')
        if not entry or entry.startswith('#'):
            continue
        if entry[0] in '"\'':
            literal_sections.append(entry.strip('"\''))
        elif entry == 'PROFILE_RODATA_SECTION':
            literal_sections.append(profile_rodata)
        else:
            raise ProbeError('unrecognized KERNAL_SECTIONS literal entry: ' + entry)
    if not literal_sections:
        raise ProbeError('KERNAL_SECTIONS parsed empty from ' + str(SUBSTITUTION_LINK_TOOL))
    prefix_drift = [name for name in literal_sections if not _is_kernal_window_section(name)]
    if prefix_drift:
        raise ProbeError('E000 low-edge probe red: KERNAL_SECTIONS prefix rule drift, '
                         'literal entries not covered by the prefix rule: ' + repr(prefix_drift))

    if not IRQ_TAIL_OWNER_SECTION in literal_sections:
        raise ProbeError('E000 low-edge probe red: IRQ tail owner section '
                         + IRQ_TAIL_OWNER_SECTION + ' missing from link tool KERNAL_SECTIONS')
    if ('irq_tail_section = "%s"' % IRQ_TAIL_OWNER_SECTION) not in link_tool_src:
        raise ProbeError('E000 low-edge probe red: irq_tail_section literal drift in link tool')
    if ('"retired_window_brk_classifier"' not in link_tool_src
            or IRQ_TAIL_TARGET_SYMBOL != 'retired_window_brk_classifier'):
        raise ProbeError('E000 low-edge probe red: IRQ tail target symbol literal drift')

    if not FACADE_LD_REFERENCE.is_file():
        raise ProbeError('facade linker-script reference missing: ' + str(FACADE_LD_REFERENCE))
    ld_text = FACADE_LD_REFERENCE.read_text()
    assertion = re.search(
        r'C2 fixed host-facade vector address drift', ld_text)
    if not assertion:
        raise ProbeError('could not locate the fixed host-facade vector ASSERT in '
                         + str(FACADE_LD_REFERENCE))
    assertion_block = ld_text[max(0, assertion.start() - 1500):assertion.start()]
    ld_facade_names = re.findall(r'\b(c2_facade_[a-z0-9_]+)\s*==', assertion_block)
    if list(ld_facade_names) != list(FIXED_FACADE_VECTOR_SYMBOLS):
        raise ProbeError('E000 low-edge probe red: fixed facade vector list drift; '
                         'linker script ASSERT names %r, hardcoded list has %r'
                         % (ld_facade_names, list(FIXED_FACADE_VECTOR_SYMBOLS)))

    return dict(
        link_tool=dict(path=str(SUBSTITUTION_LINK_TOOL.relative_to(ROOT)),
                       sha256=sha256(SUBSTITUTION_LINK_TOOL)),
        facade_ld_reference=dict(path=str(FACADE_LD_REFERENCE.relative_to(ROOT)),
                                 sha256=sha256(FACADE_LD_REFERENCE)),
        kernal_sections_literal=literal_sections,
        kernal_section_prefix=E000_KERNAL_SECTION_PREFIX,
        kernal_vectors_section=E000_KERNAL_VECTORS_SECTION,
        facade_vector_symbols=list(FIXED_FACADE_VECTOR_SYMBOLS),
        irq_tail_target_symbol=IRQ_TAIL_TARGET_SYMBOL,
        irq_tail_owner_section=IRQ_TAIL_OWNER_SECTION,
    )


def _e000_function_symbols(object_path):
    """(local FUNC name -> defining section, global/weak FUNC name -> defining
    section) for one object, via ElfTruth. Local symbols are only ever
    referenced by relocations within the same object; global/weak ones may
    be referenced from any object in the transcript.

    ElfTruth's Symbol.section already carries the resolved section *name*
    (not a raw section-table index), so the separate index->name lookup the
    hand-parsed `llvm-readelf -s`/`llvm-objdump -h` pairing needed is gone;
    Undefined/Absolute/Common are not real defining sections and are
    excluded the same way the old UND/ABS/COM index tokens were.
    """
    truth = ElfTruth.read(ROOT / object_path, llvm_readobj=LLVM_READOBJ)
    local_funcs, global_funcs = {}, {}
    for symbol in truth.symbols:
        if symbol.symbol_type != 'Function' or not symbol.name:
            continue
        if symbol.section in ('Undefined', 'Absolute', 'Common'):
            continue
        if symbol.binding == 'Local':
            local_funcs[symbol.name] = symbol.section
        elif symbol.binding in ('Global', 'Weak'):
            global_funcs[symbol.name] = symbol.section
    return local_funcs, global_funcs


_E000_SECTION_HEADER_RE = re.compile(r'^Disassembly of section (\S+):$', re.IGNORECASE)
_E000_FUNC_LABEL_RE = re.compile(r'^([0-9a-fA-F]+)\s+<([^>]+)>:$')
_E000_INSN_RE = re.compile(r'^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+)+(\S+)')
_E000_RELOC_RE = re.compile(r'^\s+([0-9a-fA-F]+):\s+(R_MOS_\S+)\s+(\S+)')
_E000_CALL_MNEMONICS = frozenset(['jsr', 'jmp'])
# Only a plain absolute-address relocation is a jsr/jmp operand. ADDR16_HI/LO
# split an address across two immediate-load bytes (`lda #<sym`/`lda #>sym`)
# for a computed/indirect call or a stored function pointer - a data use of
# the address, out of scope per rule (d). ADDR8 is zero-page data.
_E000_CODE_RELOC_TYPES = frozenset(['R_MOS_ADDR16'])


def _e000_kernal_call_edges(disassembly):
    """Yield {section, function, target, instruction} for every jsr/jmp whose
    operand is a direct-address relocation, restricted to KERNAL-window
    sections. `target` is either a function-symbol name, or (for a jump to
    an unnamed intra-object offset, e.g. a local control-flow target that
    is not itself a function entry) the literal name of the section that
    offset lives in - llvm-mos emits those as `SECTION_SYMBOL+addend`
    relocations, and `_e000_classify_target` below recognizes the leading
    "." and treats the section name itself as the definition site."""
    section = None
    func = None
    pending_mnemonic = None
    for raw_line in disassembly.splitlines():
        stripped = raw_line.strip()
        section_m = _E000_SECTION_HEADER_RE.match(stripped)
        if section_m:
            section = section_m.group(1)
            func = None
            pending_mnemonic = None
            continue
        if section is None or not _is_kernal_window_section(section):
            continue
        label_m = _E000_FUNC_LABEL_RE.match(stripped)
        if label_m:
            func = label_m.group(2)
            pending_mnemonic = None
            continue
        insn_m = _E000_INSN_RE.match(raw_line)
        if insn_m:
            pending_mnemonic = insn_m.group(2).lower()
            continue
        reloc_m = _E000_RELOC_RE.match(raw_line)
        if reloc_m and pending_mnemonic in _E000_CALL_MNEMONICS:
            reloc_type = reloc_m.group(2)
            target = reloc_m.group(3).split('+')[0]
            if reloc_type in _E000_CODE_RELOC_TYPES:
                yield dict(section=section, function=func or '(section start)',
                          target=target, instruction=pending_mnemonic)
            pending_mnemonic = None


def _e000_classify_target(local_funcs, global_index, this_object, target):
    """Classify one call target per rules (a)/(b): return a dict with
    kind in {'facade', 'kernal', 'ordinary', 'undefined'} and, where known,
    the object/section the target is actually defined in."""
    if target in FIXED_FACADE_VECTOR_SYMBOLS:
        return dict(kind='facade')
    if target.startswith('.'):
        # A relocation against a bare section symbol (no distinguishing
        # function-symbol name at that offset) is always local to this
        # object's own section table.
        kind = 'kernal' if _is_kernal_window_section(target) else 'ordinary'
        return dict(kind=kind, defined_in_object=this_object, defined_in_section=target)
    local_section = local_funcs.get(target)
    if local_section is not None:
        kind = 'kernal' if _is_kernal_window_section(local_section) else 'ordinary'
        return dict(kind=kind, defined_in_object=this_object, defined_in_section=local_section)
    hits = global_index.get(target)
    if hits:
        kernal_hit = next((h for h in hits if _is_kernal_window_section(h[1])), None)
        if kernal_hit is not None:
            return dict(kind='kernal', defined_in_object=kernal_hit[0],
                       defined_in_section=kernal_hit[1])
        obj0, sec0 = hits[0]
        return dict(kind='ordinary', defined_in_object=obj0, defined_in_section=sec0)
    return dict(kind='undefined')


def _e000_finding_key(finding):
    """Baseline-comparison key. Object filenames carry a `NNN-` compile-order
    prefix that shifts between two transcripts with a different source list
    (e.g. Seed 3 adds new stream-phase translation units before some
    alphabetically-later ones), so the prefix is stripped; the remaining
    basename, function, section and target symbol are stable identity."""
    basename = re.sub(r'^\d+-', '', Path(finding['source']['object']).name)
    return (basename, finding['source']['function'], finding['source']['section'],
           finding['target']['symbol'])


def e000_low_edges_for_objects(object_paths):
    """Core E000 low-edge analysis over an already-compiled object set.
    Returns (findings, irq_tail_owned_edges). Raises ProbeError (fail-closed)
    on an IRQ-tail ownership count other than exactly one, when the IRQ-tail
    target symbol is defined anywhere in the object set at all."""
    object_paths = [str(Path(p)) for p in object_paths]
    local_funcs_by_object = {}
    global_index = {}
    irq_tail_defined = False
    for obj in object_paths:
        local_funcs, global_funcs = _e000_function_symbols(obj)
        local_funcs_by_object[obj] = local_funcs
        if IRQ_TAIL_TARGET_SYMBOL in local_funcs:
            irq_tail_defined = True
        for name, section in global_funcs.items():
            global_index.setdefault(name, []).append((obj, section))
            if name == IRQ_TAIL_TARGET_SYMBOL:
                irq_tail_defined = True

    findings = []
    irq_tail_owned = []
    for obj in object_paths:
        rc, disassembly = run([str(LLVM_OBJDUMP), '-dr', str(ROOT / obj)])
        if rc != 0:
            raise ProbeError('llvm-objdump -dr failed on ' + obj + ':\n' + disassembly)
        for edge in _e000_kernal_call_edges(disassembly):
            if (edge['section'] == IRQ_TAIL_OWNER_SECTION
                    and edge['target'] == IRQ_TAIL_TARGET_SYMBOL):
                irq_tail_owned.append(dict(object=obj, function=edge['function'],
                                          section=edge['section']))
                continue
            classification = _e000_classify_target(
                local_funcs_by_object[obj], global_index, obj, edge['target'])
            if classification['kind'] in ('facade', 'kernal'):
                continue
            findings.append(dict(
                source=dict(object=obj, function=edge['function'], section=edge['section']),
                target=dict(symbol=edge['target'],
                           defined_in_object=classification.get('defined_in_object'),
                           defined_in_section=classification.get('defined_in_section'),
                           resolution=('undefined-in-object-set'
                                      if classification['kind'] == 'undefined'
                                      else 'ordinary-section')),
                instruction=edge['instruction'],
            ))
    if irq_tail_defined and len(irq_tail_owned) != 1:
        raise ProbeError('E000 low-edge probe red: retired-window IRQ tail ownership drift: '
                         + json.dumps(irq_tail_owned))
    return findings, irq_tail_owned


def e000_low_edges_receipt(object_paths, baseline_object_paths=None):
    """Full E000 low-edge pass with optional baseline-noise classification,
    mirroring the existing undefined-symbol receipt's shape and claims."""
    bindings = verify_e000_low_edge_rule_bindings()
    findings, irq_tail_owned = e000_low_edges_for_objects(object_paths)
    baseline_keys = None
    baseline_findings = None
    baseline_irq_tail_owned = None
    if baseline_object_paths is not None:
        baseline_findings, baseline_irq_tail_owned = e000_low_edges_for_objects(
            baseline_object_paths)
        baseline_keys = {_e000_finding_key(f) for f in baseline_findings}

    annotated = []
    for finding in findings:
        finding = dict(finding)
        finding['baseline_noise'] = (baseline_keys is not None
                                     and _e000_finding_key(finding) in baseline_keys)
        annotated.append(finding)
    new_findings = [f for f in annotated if not f['baseline_noise']]
    baseline_noise_findings = [f for f in annotated if f['baseline_noise']]
    status = 'FAIL' if new_findings else 'PASS'
    receipt = dict(
        claim='E000 LOW-EDGE PRE-LINK PROBE; OBJECT-LEVEL; NO LINKER RUN',
        status=status,
        rule_bindings=bindings,
        object_count=len(object_paths),
        objects=[str(p) for p in object_paths],
        findings=annotated,
        new_findings_count=len(new_findings),
        new_findings_keys=[list(_e000_finding_key(f)) for f in new_findings],
        baseline_noise_count=len(baseline_noise_findings),
        irq_tail_owned_edges=irq_tail_owned,
    )
    if baseline_object_paths is not None:
        receipt['baseline'] = dict(
            object_count=len(baseline_object_paths),
            objects=[str(p) for p in baseline_object_paths],
            finding_count=len(baseline_findings),
            finding_keys=[list(k) for k in sorted(baseline_keys)],
            irq_tail_owned_edges=baseline_irq_tail_owned,
        )
    return receipt


def run_preprobe(proof_path, out_dir, baseline_proof_path=None):
    out_dir = Path(out_dir).resolve()
    if not out_dir.is_relative_to(ROOT / 'build'):
        raise ProbeError('outputs must stay under build/')
    main_pass = compile_and_analyze(proof_path, out_dir / 'main')
    baseline_pass = None
    if baseline_proof_path is not None:
        baseline_proof_path = Path(baseline_proof_path).resolve()
        if baseline_proof_path == main_pass['proof_path']:
            baseline_pass = main_pass  # identical transcript: reuse, do not recompile
        else:
            baseline_pass = compile_and_analyze(baseline_proof_path, out_dir / 'baseline')
    return build_receipt(out_dir, main_pass, baseline_pass)


def selftest_fabricated_undefined():
    """A hand-written object with a made-up U symbol must FAIL the probe."""
    out_dir = ROOT / 'build/boot-name-index-link-preprobe-selftest/fabricated'
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    objects_dir = out_dir / 'objects'
    objects_dir.mkdir(parents=True)
    source = out_dir / 'fabricated.c'
    source.write_text(
        'extern void c2_link_preprobe_selftest_bogus_symbol_never_defined(void);\n'
        'void fabricated_entry(void) {\n'
        '    c2_link_preprobe_selftest_bogus_symbol_never_defined();\n'
        '}\n')
    obj_path = objects_dir / '000-fabricated.c.o'
    cc = [str(COMPILER), '-Oz', '-fno-lto', '-c', str(source.relative_to(ROOT)),
         '-o', str(obj_path.relative_to(ROOT))]
    rc, output = run(cc)
    if rc != 0:
        raise ProbeError('selftest fixture failed to compile:\n' + output)
    objects = [dict(index=0, source=str(source.relative_to(ROOT)),
                    object=str(obj_path.relative_to(ROOT)))]
    findings, per_object, ld_symbols = analyze(objects, [], DIET_REFERENCE_ELF)
    names = {f['symbol'] for f in findings}
    ok = 'c2_link_preprobe_selftest_bogus_symbol_never_defined' in names
    return ok, findings


def _fresh(out_dir):
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    return out_dir


def _seed2_proof_path():
    return next((p for p in SEED2_PROOF_CANDIDATES if p.is_file()), None)


def selftest_seed2_reproduction():
    """The probe run on Seed 2's own transcript must name c2_dma_read_or_abort."""
    proof_path = _seed2_proof_path()
    if proof_path is None:
        return None, 'no Seed-2 command-proof.json transcript found among: ' + \
            ', '.join(str(p) for p in SEED2_PROOF_CANDIDATES)
    out_dir = _fresh(ROOT / 'build/boot-name-index-link-preprobe-selftest/seed2-reproduction')
    receipt = run_preprobe(proof_path, out_dir)
    names = {f['symbol'] for f in receipt['findings']}
    classifications = {f['symbol']: f['classification'] for f in receipt['findings']}
    ok = (SEED2_EXPECTED_FINDING in names and
          classifications.get(SEED2_EXPECTED_FINDING) ==
          'internal linkage; unreachable across translation units')
    detail = dict(proof_path=str(proof_path.relative_to(ROOT)),
                 findings=sorted(names), status=receipt['status'])
    return ok, detail


def selftest_baseline_against_itself():
    """The baseline transcript diffed against itself must be PASS, 0 new findings."""
    if not BASELINE_PROOF.is_file():
        return None, 'no baseline command-proof.json at ' + str(BASELINE_PROOF)
    out_dir = _fresh(ROOT / 'build/boot-name-index-link-preprobe-selftest/baseline-self')
    receipt = run_preprobe(BASELINE_PROOF, out_dir, baseline_proof_path=BASELINE_PROOF)
    ok = receipt['status'] == 'PASS' and receipt['new_findings_count'] == 0
    detail = dict(status=receipt['status'], new_findings_count=receipt['new_findings_count'],
                 baseline_noise_count=receipt['baseline_noise_count'])
    return ok, detail


def selftest_seed2_against_baseline():
    """Seed-2's transcript diffed against the diet baseline: exactly one NEW
    finding, c2_dma_read_or_abort, classified as internal linkage."""
    proof_path = _seed2_proof_path()
    if proof_path is None:
        return None, 'no Seed-2 command-proof.json transcript found among: ' + \
            ', '.join(str(p) for p in SEED2_PROOF_CANDIDATES)
    if not BASELINE_PROOF.is_file():
        return None, 'no baseline command-proof.json at ' + str(BASELINE_PROOF)
    out_dir = _fresh(ROOT / 'build/boot-name-index-link-preprobe-selftest/seed2-vs-baseline')
    receipt = run_preprobe(proof_path, out_dir, baseline_proof_path=BASELINE_PROOF)
    new_findings = {f['symbol']: f for f in receipt['findings'] if not f['baseline_noise']}
    ok = (receipt['status'] == 'FAIL' and receipt['new_findings_count'] == 1 and
          SEED2_EXPECTED_FINDING in new_findings and
          new_findings[SEED2_EXPECTED_FINDING]['classification'] ==
          'internal linkage; unreachable across translation units')
    detail = dict(status=receipt['status'], new_findings=receipt['new_findings'],
                 baseline_noise_count=receipt['baseline_noise_count'])
    return ok, detail


def _e000_r3_objects_available():
    return (E000_R3_MAIN_OBJECTS.is_dir() and E000_R3_BASELINE_OBJECTS.is_dir()
           and any(E000_R3_MAIN_OBJECTS.glob('*.o'))
           and any(E000_R3_BASELINE_OBJECTS.glob('*.o')))


def selftest_e000_seed3_against_baseline():
    """The r3 (Seed 3) object set diffed against its accepted r4-diet
    baseline object set must show exactly one NEW E000 low edge:
    c2_boot_name_index_head_get -> c2_boot_name_index_read (the same class
    that sank Seed 3 at fixed_facade_gate, caught here before any link)."""
    if not _e000_r3_objects_available():
        return None, ('no pre-compiled r3 objects at %s / %s'
                      % (E000_R3_MAIN_OBJECTS, E000_R3_BASELINE_OBJECTS))
    main_objects = sorted(E000_R3_MAIN_OBJECTS.glob('*.o'))
    baseline_objects = sorted(E000_R3_BASELINE_OBJECTS.glob('*.o'))
    receipt = e000_low_edges_receipt(main_objects, baseline_objects)
    new_keys = {tuple(k) for k in receipt['new_findings_keys']}
    expected_key = None
    for finding in receipt['findings']:
        if (not finding['baseline_noise']
                and finding['source']['function'] == E000_EXPECTED_LOW_EDGE[0]
                and finding['target']['symbol'] == E000_EXPECTED_LOW_EDGE[1]):
            expected_key = tuple(_e000_finding_key(finding))
    ok = (receipt['status'] == 'FAIL' and receipt['new_findings_count'] == 1
          and expected_key is not None and new_keys == {expected_key})
    detail = dict(status=receipt['status'], new_findings_count=receipt['new_findings_count'],
                 new_findings_keys=receipt['new_findings_keys'],
                 baseline_noise_count=receipt['baseline_noise_count'],
                 baseline_noise_keys=sorted(
                     _e000_finding_key(f) for f in receipt['findings'] if f['baseline_noise']))
    return ok, detail


def selftest_e000_baseline_against_itself():
    """The r4-diet baseline object set diffed against itself must show 0
    new E000 low edges (any low edge it does have is then all baseline
    noise, by construction)."""
    if not _e000_r3_objects_available():
        return None, ('no pre-compiled r3 objects at %s / %s'
                      % (E000_R3_MAIN_OBJECTS, E000_R3_BASELINE_OBJECTS))
    baseline_objects = sorted(E000_R3_BASELINE_OBJECTS.glob('*.o'))
    receipt = e000_low_edges_receipt(baseline_objects, baseline_objects)
    ok = receipt['status'] == 'PASS' and receipt['new_findings_count'] == 0
    detail = dict(status=receipt['status'], new_findings_count=receipt['new_findings_count'],
                 baseline_finding_count=receipt['baseline']['finding_count'],
                 baseline_finding_keys=receipt['baseline']['finding_keys'])
    return ok, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--proof', type=Path,
                        help='command-proof.json transcript of a preflight/Seed compile run')
    parser.add_argument('--out', type=Path,
                        help='fresh build/ directory for objects and receipt.json')
    parser.add_argument('--baseline', type=Path,
                        help='command-proof.json of an accepted, actually-linked '
                             'predecessor world; findings shared with it are reported '
                             'as baseline-noise instead of failing the gate')
    parser.add_argument('--selftest', action='store_true',
                        help='run the fabricated-symbol, Seed-2-reproduction, baseline-diff '
                             'and E000-low-edge selftests')
    parser.add_argument('--e000-objects', type=Path,
                        help='directory of already-compiled objects (e.g. <out>/main/objects) '
                             'to run the E000 low-edge probe on, without recompiling anything')
    parser.add_argument('--e000-baseline-objects', type=Path,
                        help='directory of already-compiled baseline objects; findings shared '
                             'with it are reported as baseline-noise instead of failing the gate')
    args = parser.parse_args()

    if args.selftest:
        selftests = [
            ('A (fabricated undefined symbol)', selftest_fabricated_undefined),
            ('B (Seed-2 reproduction, no baseline)', selftest_seed2_reproduction),
            ('C (baseline against itself)', selftest_baseline_against_itself),
            ('D (Seed-2 against baseline)', selftest_seed2_against_baseline),
            ('E (E000 low edges: Seed-3 objects against baseline objects)',
             selftest_e000_seed3_against_baseline),
            ('F (E000 low edges: baseline objects against themselves)',
             selftest_e000_baseline_against_itself),
        ]
        passed = True
        for label, fn in selftests:
            ok, detail = fn()
            if ok is None:
                print('selftest %s: SKIPPED - %s' % (label, detail))
                continue
            print('selftest %s: %s' % (label, 'PASS' if ok else 'FAIL'))
            print(json.dumps(detail, indent=2))
            passed = passed and ok
        sys.exit(0 if passed else 1)

    if args.e000_objects:
        objects = sorted(Path(args.e000_objects).glob('*.o'))
        if not objects:
            parser.error('no .o files found under ' + str(args.e000_objects))
        baseline_objects = None
        if args.e000_baseline_objects:
            baseline_objects = sorted(Path(args.e000_baseline_objects).glob('*.o'))
            if not baseline_objects:
                parser.error('no .o files found under ' + str(args.e000_baseline_objects))
        try:
            receipt = e000_low_edges_receipt(objects, baseline_objects)
        except ProbeError as exc:
            print('FAIL (fail-closed): ' + str(exc), file=sys.stderr)
            sys.exit(1)
        out_dir = Path(args.out).resolve() if args.out else None
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / 'e000-low-edges-receipt.json').write_text(
                json.dumps(receipt, indent=2) + '\n')
        print('E000 low-edge status: ' + receipt['status'])
        print('objects: %d' % receipt['object_count'])
        if baseline_objects is not None:
            print('baseline findings (noise): %d' % receipt['baseline_noise_count'])
        print('new findings: %d' % receipt['new_findings_count'])
        for finding in receipt['findings']:
            tag = ' [baseline-noise]' if finding['baseline_noise'] else ''
            print('  %s :: %s -> %s%s' % (finding['source']['function'],
                                         finding['source']['section'],
                                         finding['target']['symbol'], tag))
        sys.exit(0 if receipt['status'] == 'PASS' else 1)

    if not args.proof or not args.out:
        parser.error('--proof and --out are required unless --selftest '
                     'or --e000-objects is given')
    try:
        receipt = run_preprobe(args.proof, args.out, baseline_proof_path=args.baseline)
    except ProbeError as exc:
        out_dir = Path(args.out).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'receipt.json').write_text(json.dumps(
            dict(claim='LINK PRE-PROBE ONLY; NO LINKER RUN; NO SEED/FINALE/LINK BUDGET SPENT',
                status='FAIL', error=str(exc)), indent=2) + '\n')
        print('FAIL (fail-closed): ' + str(exc), file=sys.stderr)
        sys.exit(1)

    print('status: ' + receipt['status'])
    print('objects: %d' % receipt['object_count'])
    if args.baseline:
        print('baseline findings (noise): %d' % receipt['baseline_noise_count'])
    print('new findings: %d' % receipt['new_findings_count'])
    for finding in receipt['findings']:
        tag = ' [baseline-noise]' if finding['baseline_noise'] else ''
        print('  %s: %s%s' % (finding['symbol'], finding['classification'], tag))
        print('    referenced by: %s' % ', '.join(finding['referenced_by']))
        if 'defined_locally_in' in finding:
            print('    defined locally in: %s' % ', '.join(finding['defined_locally_in']))
    sys.exit(0 if receipt['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
