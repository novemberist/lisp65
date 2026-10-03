#!/usr/bin/env python3
"""Single source of every 2.5.3 Seed/Final run-name and identity constant.

Installed from the Card 2.5.3 seed-prep r1 draft, updated 2026-10-01 for the
landed D2-D5 disk state (authority 94d4e89f).  Nothing here runs a product command.  `check` is pure read-only validation and
`selftest` exercises the validators on synthetic data only.

Why one module: the 2.5.2 chain (r7 -> r7b -> r7c) burned two attempts on run
names and pins that were copied into five tools and drifted apart (preflight
hash versus self-test directory, SOURCE_RUN, plane-size copies).  Every name
below is derived from ATTEMPT exactly once; the tools import, never re-spell.

CHANGE CHECKLIST -- every value marked [SET-BEFORE-SEED] / [SET-AFTER-SEED] /
[SET-AFTER-REPLAY] must be reviewed by a human before the step named.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def _root():
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / '.git').exists():
            return p
    raise RuntimeError('repository root not found')


ROOT = _root()

# ---------------------------------------------------------------- identities
# [SET-AFTER-COMMIT] The 2.5.3 source authority is the reviewer commit that carries the LCC
# arity fix (lib/dialect-v2/lcc-profile.lisp) and its consumer successors, on top of 94d4e89f.
# Set AUTHORITY_PIN to that commit's FULL 40-hex id (git rev-parse HEAD right after the commit).
# While it is None only the dry mode below can run.  C253_AUTHORITY may be exported as a
# cross-check; it must be a prefix (>= 8 hex) of the pin.  HEAD may descend from the pin only
# with no difference in CONSUMED_ROOTS (reviewer decision D-5).
# r8 (2026-10-03): the r8 source commit ccc08061 (LCC setq nesting depth restored in lib/lcc.lisp, mem_oom
# cleared at the repl() setjmp landing in src/repl.c), qualified by the sealed check-source run
# build/card-253-check-source-r8a.  [SET-BEFORE-SEED] If that run is red and a fix commit follows, pin the
# fix commit instead (the commit whose consumed roots the GREEN sealed run qualified), never the tools commit
# (this file cannot name its own commit; HEAD = tools commit descends with no consumed-root diff, D-5).
# r7 authority (retained receipts): fe248d46d66ec06646c6f4721fe7f6c26f378ea0.
AUTHORITY_PIN = 'ccc08061b621f43ab4fde7f5a651045d4c87c247'
AUTHORITY = os.environ.get('C253_AUTHORITY', AUTHORITY_PIN or '')
# Dry mode (C253_DRY_WORKTREE=1): selftest/preflight against the UNCOMMITTED working tree on top
# of DRY_PARENT (the committed parent of the working-tree change; d1937e4b = arity fix + c253 tools).  Every run name gets
# a 'dry-' tag, the root list hashes working-tree file contents, and `seed` is refused.  A dry
# preflight can never satisfy a Seed (different names, different authority label).
DRY_PARENT = AUTHORITY_PIN or 'd1937e4bf35618303b7e316426ef13f159a19a3a'
DRY = os.environ.get('C253_DRY_WORKTREE') == '1'
# 2.5.2 published source authority and the Seed r7c parent of this cycle.
BASE_AUTHORITY = '49d128599c73a5b6eb6b8595431923cd30b84491'

# Attempt tag.  Seed/Final directories are write-once; a HALT needs a NEW tag
# (r2, r3 ...) and a reviewed successor, never an in-place retry.
# r1: selftest + preflight PASS 2026-10-01 (retained), superseded by tool fixes before any Seed
# (immediate-operand native attribution, release-tree anchoring of the v112 sources).
# r2: selftest HALT (explained() accepted a size change after the attribution refactor) and,
# chained with `;`, preflight HALT on the missing selftest receipt; both retained.
# r3: selftest + preflight PASS at 94d4e89f (retained); superseded by the LCC arity fix
# (lcc-profile.lisp joins the lcc projection) -> r4.
# r4: dry selftest + preflight PASS on 94d4e89f + lcc-profile arity fix (retained); superseded by
# the lib/lcc.lisp P5 fixpoint fix (guards moved into %lcc-unary-checked / %lcc-binary-checked) -> r5.
# r5: Seed HALT before any compile (the CRC table source was materialised twice: r7c lists it in
# `generated` and `all_generated`); retained.  r6 adds the pre-link rehearsal.
# r6: Seed ran all 75 commands and linked, then HALT in inventory(): .text +338 B over the 256 B cap
# (eval_v2_workbench_service +336, main +2); retained (halt.json product_link_claimed true).
# r7: owner decision 2026-10-01: cap 352 B, expected-changed set + main, jump-table attribution fix.
# r7 PASSED (Seed + byte-identical Final r7, retained); owner decision 2026-10-02: Final r7 does not ship
# (F2 nesting-depth regression of the r7 setq code; OOM landing hang) -> new source ccc08061.
# r8: authority ccc08061; new native seam (src/repl.c mem_oom landing hunk projected onto the frozen
# Comfort-default repl.c copy that frozen command 18 compiles); cap 368 B (owner: "raise the cap slightly");
# expected-changed set + repl (setjmp callers are never inlined: `repl` is its own .text symbol, 639 B in r7);
# candidate static images pinned (lcc = the image the nesting-ladder gate proved, the other five = r7).
ATTEMPT = 'r8'
# Dry reruns after a tool fix use C253_DRY_SUFFIX (a, b, ...) instead of burning an ATTEMPT tag.
_DRY_SUFFIX = os.environ.get('C253_DRY_SUFFIX', '')
assert re.fullmatch('[a-z0-9]{0,4}', _DRY_SUFFIX) and (DRY or not _DRY_SUFFIX)
_TAG = ('dry-' + ATTEMPT + _DRY_SUFFIX) if DRY else ATTEMPT
SEED_NAME = f'card-253-product-{_TAG}'
SEED = f'build/{SEED_NAME}'                        # Seed output (write-once)
PREFLIGHT = f'build/card-253-preflight-{_TAG}'     # host-only Chunk A (write-once)
SELFTEST = f'build/card-253-selftest-{_TAG}'       # producer selftest (write-once)
FINAL = f'build/card-253-final-{_TAG}'             # Final output (write-once)
REHEARSAL = f'build/card-253-prelink-{_TAG}'       # pre-link/post-link rehearsal (write-once, not a product)
PREP = 'build/final-253-prep'                      # replay preparation parent
MEDIA_DIR = 'media-253'                            # was media-r7
MEDIA_NAME = 'c253.d81'                            # was o2lite.d81
# Sealed check-source run that qualifies the Final.  NOT the source-qualifying
# runs build/card-253-check-source-r1 (29c2bdc4) / -r2 (94d4e89f): they do not
# qualify the Seed/Final tooling.  Set ONCE, passed as --source-run to final and seal.
SOURCE_QUALIFIED_RUNS = ('build/card-253-check-source-r1', 'build/card-253-check-source-r2',
                         'build/card-253-check-source-r8a')   # r8a: qualifies the r8 source authority
SOURCE_RUN = f'build/card-253-check-source-final-{_TAG}'
FORMAT_REPLAY = 'card253-replay-v1'
FORMAT_SEAL = 'card253-final-seal-v1'
TOOL_NAMES = ('c253_final.py', 'c253_replay.py', 'c253_seal.py')
PRODUCT_TOOL = 'c253_product.py'
PRODUCER_TOOL = 'c253_seed_producer.py'
CONFIG_TOOL = 'c253_config.py'

# ------------------------------------------------ frozen 2.5.2 (r7c) baseline
BASE = 'build/o2-lite-product-r7c'                 # predecessor Seed directory
BASE_FINAL = 'build/o2-lite-final-r7c'
BASE_PREFLIGHT = 'build/o2-lite-r7-preflight-d'    # its static planes are the baseline
BASE_PLANE = BASE_PREFLIGHT + '/planes/candidate'
BASE_NATIVE = BASE + '/native'                     # 75-command recipe with r7c substitutions
BASE_MEDIA_RECEIPT = BASE + '/media-r7/runtime-receipt.json'
# Overlay family contracts: r7c's own rebound files are the authority now.
BASE_OVERLAY = {fam: BASE + f'/media-r7/runtime-overlays-{fam}-final.json'
                for fam in ('boot', 'session')}
BASE_KERNAL_WINDOW = BASE + '/media-r7/kernal-window-publish-last.json'
BASE_MEDIUM_SHA = 'ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d'
BASE_ELF_SHA = '4edcc037a3fd729cc124ae40d8c85349889ba17941e3468f1ffe8c2de2aa4abd'
BASE_PRG_SHA = 'f74ca2df859d0f521f3926a6e9306f0cb9d53e7fe686c35899239eaca3281972'
BASE_LTO_SHA = 'af01c0a83d94429fcc747534cfcd76ad920a050a52d72cba3b07430966c1cf2a'
BASE_PRODUCT_BUILD_ID = '0x8d22c8e6'
BASE_STATIC_CODE_BYTES = 50063
BASE_SHELF_BYTES = 99555

# ----------------------------------------------------------- native recipe
# src/eval.c is consumed through a GENERATED copy (nested-error-recovery
# product r1).  Measured 2026-10-01: that copy is byte-identical to
# src/eval.c at 49d12859, and src/eval.c is byte-identical at 63b3f580 and
# 29c2bdc4.  The seam is a pure file substitution pinned by both hashes.
EVAL_BASE_SHA256 = '273456250d71dad3a307ca7e17e5a14c4df97de86fbf53a36da1a3a8e0d0b9a5'
# [SET] verified at 94d4e89f (no commit after 63b3f580 touches src/eval.c).
EVAL_AUTHORITY_SHA256 = '269ef2201f32b56902042726b35c2b4ee510d703ecb731e0a95d4b1feb6af855'
# r8: src/repl.c is NOT compiled by the product.  Frozen command 18 compiles the Comfort-default copy
# .../build/comfort-default-r2/seed/repl.c (17,640 B; it differs from src/repl.c by the Comfort state block).
# The r8 seam carries exactly the BASE -> authority change of src/repl.c (one hunk: the mem_oom landing store)
# onto that copy: the hunk's old text must occur exactly once (unique-seam rule), both ends and the result are
# pinned, and reversing the hunk on the authority src/repl.c must give src/repl.c@BASE_AUTHORITY.
# Measured 2026-10-03 (build/card-253-r8-seed-prep/repl-product-projected.c, = the price "after" source).
REPL_COMMAND_INDEX = 18
REPL_COPY_SUFFIX = 'build/comfort-default-r2/seed/repl.c'
REPL_BASE_SHA256 = '3d0c39b098bad2de6011d46ada91c045c9365e89644557f135f5fe0054083a33'       # frozen copy (r7c = r7)
REPL_BASE_SOURCE_SHA256 = '3d54f9d8b8043c966c148baea28db1f8e9ca8cfc19920b8dc40c515ae363e274'  # src/repl.c @ 49d12859
REPL_AUTHORITY_SHA256 = '2124d0d074dcc6ddda158fdb9adc4bd8fc56440bf5039b15ebebe5a295fa4b2f'  # src/repl.c @ ccc08061
REPL_PRODUCT_SHA256 = '6499b37cb5578f3175ae197eeee47de9400fbd05c834f094b664e1553b3bca28'    # projected copy, 17,883 B
REPL_LANDING_BEFORE = ('        (void)lisp65_error_render_pending();\n',
                       "        emit('\\n');\n",
                       '        lisp65_error_clear();\n')
REPL_LANDING_INSERT = ('        /* The abort crossed the mem_oom report below: left set, the first\n',
                       '         * allocating VM op of the next read-line entry reports OOM again,\n',
                       '         * forever.  Clear it at every landing (2.5.3 OOM-hang fix). */\n',
                       '        mem_oom = 0;\n')
REPL_LANDING_AFTER = ('        gc_rootsp = 0;                                    /* Roots der abgebrochenen eval verwerfen */\n',
                      '    }\n',
                      '    lisp_toplevel_active = 1;\n')


def repl_landing_hunk():
    """(old, new) text of the one src/repl.c hunk BASE -> authority, 3 lines of context each side."""
    before, after = ''.join(REPL_LANDING_BEFORE), ''.join(REPL_LANDING_AFTER)
    return before + after, before + ''.join(REPL_LANDING_INSERT) + after


NATIVE_COMMANDS = 75                               # 73 compiles + llvm-link + ONE product link
# Owner decision 2026-10-01: after the Seed r6 HALT (.text 36,559 -> 36,897 = +338 B, only
# eval_v2_workbench_service +336 and main +2 changed) the cap was raised from 256 to 352 B.
# r8: owner decision 2026-10-02 ("raise the cap slightly" for the OOM landing fix; reviewer recommendation
# +368 B): r7 measured +338 B on the real link, the mem_oom landing store is +4 B isolated
# (build/card-253-r8-source/price/native-price.json: repl.c object .text 664 -> 668 B, -fno-lto).  Last time the
# product measured more than isolated (+336 vs +215), so 368 leaves 26 B over 338 + 4.  [OWNER-DECISION]
NATIVE_TEXT_CAP = 368                              # bytes
NATIVE_TEXT_PRICE_ISOLATED = 215                   # measured isolated .text.service35 delta
NATIVE_TEXT_PRICE_ISOLATED_REPL = 4                # measured isolated repl.c object delta (r8 landing store)
# [SET] functions allowed to differ in .text (relocation masking applies to
# all others).  Measured on the real Seed r6 link (retained HALT build/card-253-product-r6):
# eval_v2_workbench_service 1769 -> 2105 B (+336) and main 620 -> 622 B (+2: LTO register
# reallocation and moved label address bytes); nothing else changed in .text.
# r8: + repl.  repl() contains the only setjmp(lisp_toplevel); LLVM never inlines a returns_twice caller, and
# the r7 ELF carries it as the local symbol `repl` (0xa970, 0x27f B), so the landing store lands in `repl`
# itself, not in main.  Sorted order (text_attribution compares sorted names).  [SET]
NATIVE_TEXT_EXPECTED_CHANGED = ('eval_v2_workbench_service', 'main', 'repl')
# Non-allocated metadata sections whose size may change, with the exact byte delta.  The F2 fix
# adds one error call site (isolated price: .lisp65_error_callsites 0 -> 1 B); measured on the
# r6 link: 50 -> 51 B.  [SET]
NATIVE_METADATA_EXPECTED = {'.lisp65_error_callsites': 1}

# ------------------------------------------------------------- capacities
LIMITS = dict(code=60758, entries=2048, resolutions=4096, roots=1536, images=64)
SYMBOL_LIMITS = dict(symbols=1008, namepool=16351)
SYMBOL_MARGIN = dict(symbols=32, namepool=384)
C2D_DELIVERED_BYTES = 50816
# Static plane keys (order matters: same as substitution-artifacts.json).
KEYS = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
# Preflight policy: which static images must change / must reproduce exactly.
# [SET] reviewer decision D-2: D2-D5 landed (lib/m65-disk.lisp), so 'm65d' is CHANGED;
# idex/buffer must be EXACT or ENTRY-EXACT (literal-table layout shift only).
EXPECT_CHANGED = ('stdlib-p0', 'ide', 'm65d', 'lcc')
EXPECT_EXACT = ('idex', 'buffer')
# r8: expected candidate image blobs (sha256, code bytes).  lcc = the image whose nesting depth the
# lcc-nesting-ladder-check gate proved (tests/bytecode/dialect-v2/evidence/capability-carrier/
# lcc-nesting-ladder-v253-20261002.json candidate_image: 109 objects, 8,349 B, largest 246 B); r7 was 59d8f1ee..., 8,348 B.
# The other five are unchanged from the r7 preflight (build/card-253-preflight-r7/emission/*/<key>.blob.bin):
# lib/lcc.lisp is the only lib file that changed after fe248d46.  A different blob halts the PREFLIGHT (free).
CANDIDATE_BLOBS = {
    'stdlib-p0': ('1bd9aab1f70228fd4d3947ec54b27ac0401e1d4a018cf736ae238d80d6478f06', 19814),
    'ide': ('a990787c906c6421c22d01536b1ea3164aa4dcb39b89f1f5249beb1b77f82f5a', 15063),
    'idex': ('7f88f49c079833e1d90d228e64e24c065694ad0ec7970b66f6b4bbf233011b24', 2940),
    'm65d': ('80f1a7553ad8e8d46deca508487bfd15f0869fddda2fa1c5e151a4c745257d04', 4373),
    'buffer': ('d218ff4ba23620eb02fbdb35c4b9795cf98404c0955091bcb7ded6487c24c747', 104),
    'lcc': ('dd0168ef519c153843f8b6233cde6577520cc17d7a3070f55cfc548d1508554d', 8349),
}
CANDIDATE_STATIC_CODE_BYTES = 50643                # r7 50,642 + 1 (lcc)
# m65d is emitted from the dated r8 suite through the Makefile's codemod route
# (mk/workbench-service-inventory.mk: V2_WORKBENCH_CODEMOD_TOOL).
CODEMOD_TOOL = 'v2_workbench_codemod_disk_r8_20261001'
CLOSURE_CONFIG = 'config/v2-workbench-artifact-closure-disk-r8-20261001.json'
M65D_SOURCE_SUITE = 'tests/bytecode/libs/p0-m65d-lib-disk-r8-20261001.json'
# ---------------------------------------------- product emission projection
# The delivered static images are NOT the Makefile route (preflight rehearsals r1-r4,
# 2026-10-01): stdlib-p0 is the O2-lite product resident (o2-lite-r4 resident.json over
# frozen v1.5.0-era sources), ide is the ide-exit-product-r2 world, lcc is the v1.5.0
# v112 compiler tier.  2.5.3 therefore PROJECTS the 2.5.2 -> 2.5.3 source change onto
# each frozen world (whole file when the frozen copy is exactly T(lib@BASE), otherwise
# diff hunks whose old text occurs exactly once; T = identity or codemod rewrite_tokens).
# idex = generated closure route, buffer = tests/bytecode/libs/p0-buffer-lib.json, m65d =
# r8 closure suite; every image is emitted against the projected product resident.
# Baseline control: each frozen world (residents normalised to the r7c product resident
# and r7c m65d suite) is re-emitted inside the BASE_AUTHORITY host-source era and must
# reproduce the delivered image byte for byte.
PROJECTIONS = {
    'stdlib-p0': {'domain-tier1-sealed.lisp': 'lib/domain-tier1.lisp'},
    'ide': {'ide-buffer.lisp': 'lib/ide-buffer.lisp', 'source-36ba4108c582.lisp': 'lib/ide-ui.lisp',
            'product-ide-disk.lisp': 'lib/ide-disk.lisp'},
    'lcc': {'lcc.lisp': 'lib/lcc.lisp', 'lcc-profile.lisp': 'lib/dialect-v2/lcc-profile.lisp'},
}
# lib/m65-disk.lisp reaches the product through the r8 closure route (m65d).
CLOSURE_ROUTED_LIB = ('lib/m65-disk.lisp',)
# Suite list edits mirroring the 2.5.3 suite commits (p0-ide-lib / werkbank / einsuite):
# (key, field, old run, new run); each old run must occur exactly once.
SUITE_EDITS = (
    ('stdlib-p0', 'functions', None, ['%nth-after-domain-check']),          # None = append (r3 precedent)
    ('stdlib-p0', 'tailcall_self', ['nth'], ['%nth-after-domain-check']),
    ('ide', 'functions', ['%ide-disk-effective-sector'], []),
    ('ide', 'functions', ['%ide-join-codes-into', '%ide-join-codes'], ['%ide-source-size', '%ide-copy-line', '%ide-copy-lines']),
    ('ide', 'functions', ['eval-buffer'], ['eval-buffer', '%ide-eval-source', '%ide-eval-open']),
    ('ide', 'tailcall_self', ['%ide-join-codes-into'], ['%ide-source-size', '%ide-copy-lines']),
    ('ide', 'tailcall_self', ['eval-buffer'], ['%ide-eval-source']),
    ('ide', 'private_inline_functions', ['%ide-join-codes'], ['%ide-copy-line']),
    ('lcc', 'functions', ['%lcc-setq'], ['%lcc-setq-one', '%lcc-setq-pairs', '%lcc-setq']),
    ('lcc', 'functions', ['%lcc-2args-p'], ['%lcc-2args-p', '%lcc-1args-p']),
    # Reviewer arity fix (lcc-profile.lisp): helpers placed before their only caller.
    # ... and the lib/lcc.lisp P5 fix helpers (defined by the projected lcc.lisp; unused in the
    # product because %lcc-expr-ops2 comes from the profile, but every defun must be owned).
    ('lcc', 'functions', ['%lcc-expr-ops2'],
     ['%lcc-unary-checked', '%lcc-binary-checked', '%lcc-v2-unary', '%lcc-v2-binary', '%lcc-expr-ops2']),
)
# ide cases / disk_files: replace exactly the entries that equal their p0-ide-lib.json@BASE
# form with their @AUTHORITY form (one case and disk_files change in 2.5.3).
IDE_CASE_SOURCE = 'tests/bytecode/libs/p0-ide-lib.json'
BUFFER_SUITE = 'tests/bytecode/libs/p0-buffer-lib.json'
# Host-source era cache (filled by prime_era() BEFORE the audit hook; no git under the hook).
ERA_PREFIXES = ('lib/', 'tests/bytecode/libs/', 'tests/bytecode/stdlib/', 'tests/bytecode/runtime/',
                'tests/bytecode/demos/', 'tests/bytecode/suites/')
ERA_CACHE = {}
CHANGED_LIB = None
# Disk library packages (L65S): re-envelope only (D-2).
PACKAGES_REEMIT = ()

# --------------------------------------------- Final identity (after Seed)
# [SET-AFTER-SEED] filled from build/card-253-product-r1 by
# `c253_seed_producer.py emit-final-constants` (prints, writes nothing).
SEED_RECEIPT_SHA = None            # sha256 of SEED/seed.json
RECIPE_SHA = None                  # sha256 of SEED/native/command-proof.json
ARTIFACT_SHA = dict(ELF=None, PRG=None, LTO=None, D81=None)
ARTIFACT_PATH = dict(ELF='wplto/resident-island-seed.prg.elf',
                     PRG='wplto/resident-island-seed.prg',
                     LTO='wplto/resident-island-seed.prg.lto.o',
                     D81=f'{MEDIA_DIR}/{MEDIA_NAME}')
# [SET-AFTER-REPLAY] pinned on the Final command line, not stored here.
# [SET-AFTER-SEAL] sha256 of FINAL/seal.json, bound by c253_gc_stress.py.
SEAL_SHA = None


def artifacts():
    missing = [k for k, v in ARTIFACT_SHA.items() if not v]
    if missing or not (SEED_RECEIPT_SHA and RECIPE_SHA):
        raise ValueError('Final constants not set after Seed: ' + ','.join(missing))
    return {k: (ARTIFACT_PATH[k], ARTIFACT_SHA[k]) for k in ARTIFACT_PATH}


def installed(names):
    return ['tools/host-lisp/' + n for n in names]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Source roots whose bytes the Seed consumes.  HEAD may be a DESCENDANT of the authority commit
# (tool installation, replay commit, journal), but none of these may differ.  [C253-CHECK]
CONSUMED_ROOTS = ('lib', 'src', 'tests/bytecode', 'config', 'scripts', 'Makefile', 'mk')
AUTHORITY_CHECK = None


def _git(*args, check=True):
    import subprocess
    return subprocess.run(['git', *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check,
                          env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def verify_authority():
    """Read-only git queries, run by the CLI BEFORE the write/process audit hook is installed.

    C253_AUTHORITY names the source commit (e.g. the last D2-D5 disk commit).  HEAD equals it or
    descends from it with no difference in any consumed source root, and the working tree has no
    uncommitted change there.  The result is stored and only read (never recomputed) by the
    producer library, which runs under the audit hook."""
    global AUTHORITY_CHECK
    if DRY:
        return verify_dry()
    assert AUTHORITY_PIN, 'AUTHORITY_PIN not set (reviewer sets it after the source commit; dry mode: C253_DRY_WORKTREE=1)'
    assert re.fullmatch('[0-9a-f]{8,40}', AUTHORITY), 'set C253_AUTHORITY (commit prefix, lower-case hex)'
    assert AUTHORITY_PIN.startswith(AUTHORITY), 'C253_AUTHORITY is not a prefix of the pinned authority'
    r = _git('rev-parse', '--verify', AUTHORITY + '^{commit}', check=False)
    assert r.returncode == 0, 'authority is not a commit in this repository'
    full = r.stdout.strip()
    head = _git('rev-parse', '--verify', 'HEAD').stdout.strip()
    relation = 'equal'
    if full != head:
        relation = 'descendant'
        assert _git('merge-base', '--is-ancestor', full, head, check=False).returncode == 0, 'HEAD does not descend from authority'
        assert _git('diff', '--quiet', full, head, '--', *CONSUMED_ROOTS, check=False).returncode == 0, \
            'consumed sources differ between authority and HEAD'
    assert _git('diff', '--quiet', 'HEAD', '--', *CONSUMED_ROOTS, check=False).returncode == 0, \
        'uncommitted change in a consumed source root'
    assert full == AUTHORITY_PIN, 'authority does not resolve to the pin'
    AUTHORITY_CHECK = dict(requested=AUTHORITY, authority=full, observed=head, relation=relation,
                           consumed_roots=list(CONSUMED_ROOTS), root_trees=consumed_root_trees(full))
    return AUTHORITY_CHECK


def authority_label():
    """The identity a projection reads as `lib@authority` (working tree, verified against it)."""
    return ('worktree@' + DRY_PARENT) if DRY else AUTHORITY_PIN


def worktree_root_digests():
    """Content digest per consumed root over tracked + untracked (non-ignored) working-tree files."""
    rows = {}
    for root in CONSUMED_ROOTS:
        names = sorted(set(_git('ls-files', '-co', '--exclude-standard', '--', root).stdout.splitlines()))
        h = hashlib.sha256()
        for name in names:
            path = ROOT / name
            if path.is_file():
                h.update(name.encode() + b'\0' + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b'\n')
        rows[root] = 'worktree:' + h.hexdigest()
    return rows


def verify_dry():
    global AUTHORITY_CHECK
    head = _git('rev-parse', '--verify', 'HEAD').stdout.strip()
    relation = 'equal'
    if head != DRY_PARENT:
        relation = 'descendant'
        assert _git('merge-base', '--is-ancestor', DRY_PARENT, head, check=False).returncode == 0, 'HEAD does not descend from DRY_PARENT'
        assert _git('diff', '--quiet', DRY_PARENT, head, '--', *CONSUMED_ROOTS, check=False).returncode == 0, \
            'committed consumed-source change after DRY_PARENT: set AUTHORITY_PIN instead of using dry mode'
    changed = sorted(set(_git('diff', '--name-only', 'HEAD', '--', *CONSUMED_ROOTS).stdout.split()) |
                     set(_git('ls-files', '-o', '--exclude-standard', '--', *CONSUMED_ROOTS).stdout.split()))
    AUTHORITY_CHECK = dict(requested='dry-worktree', authority=authority_label(), observed=head, relation=relation,
                           consumed_roots=list(CONSUMED_ROOTS), root_trees=worktree_root_digests(),
                           uncommitted=changed, dry=True)
    return AUTHORITY_CHECK


def prime_era(commit=BASE_AUTHORITY):
    """Read-only: cache every era-selectable host source at `commit` (git cat-file, before the
    audit hook) and the lib/ files changed between BASE_AUTHORITY and the authority pin."""
    global CHANGED_LIB
    import subprocess
    names = [n for n in _git('ls-tree', '-r', '--name-only', commit, '--', 'lib', 'tests/bytecode').stdout.splitlines()
             if n.startswith(ERA_PREFIXES) and (n.endswith('.lisp') if n.startswith('lib/') else n.endswith('.json'))]
    batch = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT, input=''.join(f'{commit}:{n}\n' for n in names).encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                           env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).stdout
    at = 0
    for name in names:
        end = batch.index(b'\n', at)
        header = batch[at:end].split()
        assert len(header) == 3 and header[1] == b'blob', ('era blob', name, header)
        size = int(header[2]); ERA_CACHE[(commit, name)] = batch[end + 1:end + 1 + size]; at = end + 2 + size
    assert at == len(batch) and len(ERA_CACHE) >= len(names)
    if DRY:
        CHANGED_LIB = tuple(sorted(set(_git('diff', '--name-only', commit, '--', 'lib').stdout.split()) |
                                   set(_git('ls-files', '-o', '--exclude-standard', '--', 'lib').stdout.split())))
    else:
        assert AUTHORITY_PIN, 'AUTHORITY_PIN not set'
        CHANGED_LIB = tuple(sorted(_git('diff', '--name-only', commit, AUTHORITY_PIN, '--', 'lib').stdout.split()))
    return dict(commit=commit, cached=len(names), changed_lib=list(CHANGED_LIB))


def era_blob(commit, path):
    key = (commit, Path(path).as_posix())
    assert key in ERA_CACHE, ('era blob not primed', key)
    return ERA_CACHE[key]


def consumed_root_trees(commit):
    """D-5 root list: the git object id of every consumed root at `commit` (read-only)."""
    rows = {}
    for root in CONSUMED_ROOTS:
        r = _git('rev-parse', '--verify', f'{commit}:{root}', check=False)
        assert r.returncode == 0, 'consumed root missing at authority: ' + root
        rows[root] = r.stdout.strip()
    return rows


def same_authority(a, b):
    """Seed-time comparison: same pinned authority and identical consumed-root trees.
    The observed HEAD may differ (tool/journal commits outside CONSUMED_ROOTS, D-5)."""
    return (a['authority'] == b['authority'] == authority_label() and a['root_trees'] == b['root_trees']
            and a['consumed_roots'] == b['consumed_roots'])


def authority_head(strict=True):
    assert AUTHORITY_CHECK is not None, 'verify_authority() must run first (CLI does this)'
    return AUTHORITY_CHECK


def run_names():
    return dict(SEED=SEED, PREFLIGHT=PREFLIGHT, SELFTEST=SELFTEST, FINAL=FINAL, SOURCE_RUN=SOURCE_RUN,
                PREP=PREP)


def check(*, stage):
    """Read-only constant validation.  stage in {seed, final}."""
    problems = []
    # 1. The frozen baseline must still be exactly what the constants say.
    for label, rel, want in (('base medium', BASE + '/media-r7/o2lite.d81', BASE_MEDIUM_SHA),
                             ('base ELF', BASE + '/wplto/resident-island-seed.prg.elf', BASE_ELF_SHA),
                             ('base PRG', BASE + '/wplto/resident-island-seed.prg', BASE_PRG_SHA),
                             ('base LTO', BASE + '/wplto/resident-island-seed.prg.lto.o', BASE_LTO_SHA)):
        if sha256_file(ROOT / rel) != want:
            problems.append(f'{label} drift: {rel}')
    # 2. Native eval.c pin: the working tree source must be the pinned authority.
    if sha256_file(ROOT / 'src/eval.c') != EVAL_AUTHORITY_SHA256:
        problems.append('src/eval.c != EVAL_AUTHORITY_SHA256 (re-pin after review)')
    # 3. Generated baseline eval.c must equal the pinned base.
    derived = json.loads((ROOT / BASE_NATIVE / 'derived-inputs.json').read_text())
    evals = [r for r in derived['all_generated'] if r['path'].endswith('generated-product-sources/eval.c')]
    if len(evals) != 1 or evals[0]['sha256'] != EVAL_BASE_SHA256:
        problems.append('baseline generated eval.c is not the pinned 2.5.2 source')
    # 3b. r8 repl.c seam: authority source, frozen compiled copy, frozen command 18.
    if sha256_file(ROOT / 'src/repl.c') != REPL_AUTHORITY_SHA256:
        problems.append('src/repl.c != REPL_AUTHORITY_SHA256 (re-pin after review)')
    recipe = json.loads((ROOT / BASE_NATIVE / 'command-proof.json').read_text())['commands']
    repl_c = [c[c.index('-c') + 1] for c in recipe[:73] if c[c.index('-c') + 1].endswith('/repl.c')]
    if len(repl_c) != 1 or recipe[REPL_COMMAND_INDEX][recipe[REPL_COMMAND_INDEX].index('-c') + 1] != repl_c[0] \
            or not repl_c[0].endswith(REPL_COPY_SUFFIX) or sha256_file(ROOT / repl_c[0]) != REPL_BASE_SHA256:
        problems.append('frozen compiled repl.c copy is not the pinned Comfort-default source of command 18')
    # 4. Write-once names must not exist yet (seed stage) / must exist (final).
    names = [SEED, PREFLIGHT, SELFTEST] if stage == 'seed' else [FINAL]
    for n in names:
        if stage == 'seed' and n == SEED:
            if (ROOT / n).exists():
                problems.append('write-once name already claimed: ' + n)
        elif stage == 'seed':
            pass  # PREFLIGHT/SELFTEST are created by their own actions
        elif (ROOT / n).exists():
            problems.append('Final name already claimed: ' + n)
    if stage == 'final':
        try:
            artifacts()
        except ValueError as error:
            problems.append(str(error))
        if not SOURCE_RUN.startswith('build/') or (ROOT / SOURCE_RUN).exists():
            problems.append('SOURCE_RUN must be a fresh build/ directory chosen by the reviewer')
        if not (ROOT / SEED / 'complete.json').exists():
            problems.append('Seed not complete')
    # 5. Names are all distinct and all below build/.
    values = list(run_names().values())
    if len(set(values)) != len(values) or not all(v.startswith('build/') for v in values):
        problems.append('run names collide or escape build/')
    if any(Path(v).is_relative_to(Path(b)) for v in (SEED, PREFLIGHT, SELFTEST, FINAL)
           for b in (BASE, BASE_FINAL, BASE_PREFLIGHT)):
        problems.append('successor name inside a frozen 2.5.2 directory')
    return dict(status='PASS' if not problems else 'FAIL', stage=stage, problems=problems,
                names=run_names(), authority=AUTHORITY or None)


def selftest():
    """Synthetic only: prove the validators reject what they must."""
    rejected = []

    def reject(name, fn):
        try:
            fn()
        except (AssertionError, ValueError):
            rejected.append(name)
        else:
            raise AssertionError('negative survived: ' + name)
    global AUTHORITY, AUTHORITY_CHECK
    saved, saved_check = AUTHORITY, AUTHORITY_CHECK
    try:
        AUTHORITY_CHECK = None
        reject('authority not verified', lambda: authority_head(True))
        if not DRY and AUTHORITY_PIN:
            for bad in ('xyz', '', 'DEADBEEF', 'abc'):
                AUTHORITY = bad
                reject('malformed authority ' + repr(bad), verify_authority)
            AUTHORITY = 'deadbeefdeadbeef'
            reject('foreign authority prefix', verify_authority)
        elif not DRY:
            reject('unset authority pin', verify_authority)
        AUTHORITY_CHECK = dict(authority=authority_label(), consumed_roots=list(CONSUMED_ROOTS), root_trees={'lib': 'a'})
        reject('consumed tree drift', lambda: (_ for _ in ()).throw(AssertionError()) if not same_authority(
            AUTHORITY_CHECK, dict(AUTHORITY_CHECK, root_trees={'lib': 'b'})) else None)
        assert same_authority(AUTHORITY_CHECK, dict(AUTHORITY_CHECK, observed='other-head'))
    finally:
        AUTHORITY, AUTHORITY_CHECK = saved, saved_check
    reject('unset Final constants', artifacts)
    names = [SEED, PREFLIGHT, SELFTEST, FINAL, SOURCE_RUN, PREP]
    assert len(set(names)) == len(names) and all(n.startswith('build/') for n in names), 'name collision'
    assert SOURCE_RUN not in SOURCE_QUALIFIED_RUNS, 'would reuse a source-qualifying sealed run'
    assert set(EXPECT_CHANGED) | set(EXPECT_EXACT) == set(KEYS) and 'm65d' in EXPECT_CHANGED
    assert set(CANDIDATE_BLOBS) == set(KEYS) and sum(v[1] for v in CANDIDATE_BLOBS.values()) == CANDIDATE_STATIC_CODE_BYTES
    old, new = repl_landing_hunk()
    assert new.count('mem_oom = 0;') == 1 and old.count('mem_oom') == 0 and new.startswith(old[:len(''.join(REPL_LANDING_BEFORE))])
    assert NATIVE_TEXT_CAP >= 338 + NATIVE_TEXT_PRICE_ISOLATED_REPL and 'repl' in NATIVE_TEXT_EXPECTED_CHANGED
    assert list(NATIVE_TEXT_EXPECTED_CHANGED) == sorted(NATIVE_TEXT_EXPECTED_CHANGED)
    # 2.5.2 names are build/o2-lite-*; the 2.5.3 attempt tag r7 legitimately ends in 'r7'.
    assert not any('o2-lite' in n for n in names), 'stale 2.5.2 name'
    return dict(status='PASS', negative_controls=rejected, names=run_names())


if __name__ == '__main__':
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    action = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if action == 'selftest':
        print(json.dumps(selftest(), indent=2))
    elif action == 'check-seed':
        print(json.dumps(check(stage='seed'), indent=2))
    elif action == 'check-final':
        print(json.dumps(check(stage='final'), indent=2))
    else:
        sys.exit('usage: c253_config.py selftest|check-seed|check-final')
