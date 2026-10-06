#!/usr/bin/env python3
"""Single source of every 2.5.4 Seed/Final run-name and identity constant.

Successor of c253_config.py (installed from build/card-254-seed-prep-r1/drafts, phase 2).  The c253 tools stay byte-identical:
the 2.5.3 Seed/Final receipts bind their bytes.  Nothing here runs a product command.  `check` is pure
read-only validation and `selftest` exercises the validators on synthetic data only.

2.5.4 = 2.5.3 Final r8 + Lisp-only changes.  What that means for the constants below:
  - baseline            the 2.5.3 Seed r8 directory (byte-identical to the sealed Final r8)
  - native code         NO source seam.  Every compiled input is the 2.5.3 Seed r8 materialised input; only the
                        generated-constant seams move (CRC16 table source, resident header counts, static plane
                        size, compiler-input assertions, -D build id / SHELF bytes).  `.text` stays 36,899 B.
  - static images       CHANGED stdlib-p0 / ide / lcc, EXACT idex / m65d / buffer
  - L65S packages       REPL-COMFORT and DEFSTRUCT re-emitted; all six envelopes rebound (the static build id
                        changes); L65INDEX changes in the two re-emitted rows only

CHANGE CHECKLIST -- every value marked [SET-BEFORE-SEED] / [SET-AFTER-DRY-PREFLIGHT] / [REVIEWER-DECISION]
must be reviewed by a human before the step named.  The Final pins live in c254_final_pins.py, never here
(2.5.3 lesson: the Seed receipts bind this file).
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
# The 2.5.4 source authority: the commit whose consumed roots the GREEN sealed check-source run
# build/card-254-check-source-r2 qualified (receipt exit_code 0, head 04294d56 before and after, changed_files []).
# 04294d56 differs from the source candidate 8bd8f1db in mk/gates.mk, two Card-5 receipts under config/ and one
# receipt under tests/bytecode/ only (lib, src, scripts identical).  Never the tools commit (this file cannot
# name its own commit; HEAD = tools commit descends with no consumed-root diff, D-5).
AUTHORITY_PIN = '04294d56dd874268d8f679ff43c3622128900e7d'
AUTHORITY = os.environ.get('C254_AUTHORITY', AUTHORITY_PIN or '')
# Dry mode (C254_DRY_WORKTREE=1): selftest/preflight/rehearse against the UNCOMMITTED working tree on top of
# DRY_PARENT.  Every run name gets a 'dry-' tag, the root list hashes working-tree file contents, and `seed`
# is refused.  A dry preflight can never satisfy a Seed (different names, different authority label).
DRY_PARENT = AUTHORITY_PIN
DRY = os.environ.get('C254_DRY_WORKTREE') == '1'
# 2.5.3 source authority (Seed r8 / Final r8 / published 2.5.3).  It is the host-source ERA of the baseline
# control and the OLD side of every projection: lib/ is byte-identical from ccc08061 to the published head
# 22ab180e (measured 2026-10-04: `git diff ccc08061 22ab180e -- lib src` is empty).
BASE_AUTHORITY = 'ccc08061b621f43ab4fde7f5a651045d4c87c247'
# Roots that must be IDENTICAL between BASE_AUTHORITY and the authority ("native code unchanged").  The recipe
# compiles frozen materialised copies, not src/, so this is a premise check, not an input binding.
NATIVE_UNCHANGED_ROOTS = ('src',)

# Attempt tag.  Seed/Final directories are write-once; a HALT needs a NEW tag and a reviewed successor.
ATTEMPT = 'r1'
_DRY_SUFFIX = os.environ.get('C254_DRY_SUFFIX', '')
assert re.fullmatch('[a-z0-9]{0,4}', _DRY_SUFFIX) and (DRY or not _DRY_SUFFIX)
_TAG = ('dry-' + ATTEMPT + _DRY_SUFFIX) if DRY else ATTEMPT
# C254_NAME_ROOT: phase-1 probes only (dry mode): put every run directory below one prep directory.
_NAME_ROOT = os.environ.get('C254_NAME_ROOT', 'build')
assert _NAME_ROOT == 'build' or (DRY and re.fullmatch(r'build/card-254-[a-z0-9-]+(/[a-z0-9-]+)*', _NAME_ROOT)), \
    'C254_NAME_ROOT is a dry-mode probe switch only'
SEED_NAME = f'card-254-product-{_TAG}'
SEED = f'{_NAME_ROOT}/{SEED_NAME}'                       # Seed output (write-once)
PREFLIGHT = f'{_NAME_ROOT}/card-254-preflight-{_TAG}'    # host-only Chunk A (write-once)
SELFTEST = f'{_NAME_ROOT}/card-254-selftest-{_TAG}'      # producer selftest (write-once)
FINAL = f'{_NAME_ROOT}/card-254-final-{_TAG}'            # Final output (write-once)
REHEARSAL = f'{_NAME_ROOT}/card-254-prelink-{_TAG}'      # pre-link/post-link rehearsal (write-once, not a product)
E3 = f'{_NAME_ROOT}/card-254-e3-{_TAG}'                  # exhaustive product-world E3 sweep (write-once; D-E3)
PREP = 'build/final-254-prep'                            # replay preparation parent
MEDIA_DIR = 'media-254'
MEDIA_NAME = 'c254.d81'
# Sealed check-source run that qualifies the Final.  NOT the source-qualifying run.
SOURCE_QUALIFIED_RUNS = ('build/card-254-check-source-r2',)
SOURCE_RUN = f'build/card-254-check-source-final-{_TAG}'
FORMAT_REPLAY = 'card254-replay-v1'
FORMAT_SEAL = 'card254-final-seal-v1'
TOOL_NAMES = ('c254_final.py', 'c254_replay.py', 'c254_seal.py')
PRODUCT_TOOL = 'c254_product.py'
PRODUCER_TOOL = 'c254_seed_producer.py'
CONFIG_TOOL = 'c254_config.py'
SITES_TOOL = 'c254_native_sites_20261004.json'         # immediate-site census of the baseline ELF (bound below)
E3_TOOL = 'c254_e3_product.py'                         # product-world E3 harness (D-E3; bound by tool_identity)

# ------------------------------------------------ frozen 2.5.3 (r8) baseline
BASE = 'build/card-253-product-r8'                 # predecessor Seed directory (byte-identical Final below)
BASE_FINAL = 'build/card-253-final-r8'
BASE_PREFLIGHT = 'build/card-253-preflight-r8'     # its candidate plane is the delivered 2.5.3 static plane
BASE_PLANE = BASE_PREFLIGHT + '/planes/candidate'
BASE_NATIVE = BASE + '/native'                     # 75-command recipe with the r8 substitutions applied
BASE_MEDIA_DIR = 'media-253'
BASE_MEDIA_NAME = 'c253.d81'
BASE_MEDIA_RECEIPT = BASE + f'/{BASE_MEDIA_DIR}/runtime-receipt.json'
BASE_OVERLAY = {fam: BASE + f'/{BASE_MEDIA_DIR}/runtime-overlays-{fam}-final.json' for fam in ('boot', 'session')}
BASE_KERNAL_WINDOW = BASE + f'/{BASE_MEDIA_DIR}/kernal-window-publish-last.json'
BASE_MEDIUM_SHA = '7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f'
BASE_ELF_SHA = '5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293'
BASE_PRG_SHA = '6bf9dbd59b7ef3c4ef19eaa900f57606d313fbbc106475c1ede0102d3ada63ad'
BASE_LTO_SHA = '0491996a5d530545bb663dbb72712be484190e665addf0318d5de51b86f13c6b'
BASE_PRODUCT_BUILD_ID = '0xaff6dfd2'
BASE_STATIC_CODE_BYTES = 50643
BASE_SHELF_BYTES = 100729
BASE_ARTIFACTS = (('medium', f'{BASE_MEDIA_DIR}/{BASE_MEDIA_NAME}', BASE_MEDIUM_SHA),
                  ('ELF', 'wplto/resident-island-seed.prg.elf', BASE_ELF_SHA),
                  ('PRG', 'wplto/resident-island-seed.prg', BASE_PRG_SHA),
                  ('LTO', 'wplto/resident-island-seed.prg.lto.o', BASE_LTO_SHA))

# ----------------------------------------------------------- native recipe
NATIVE_COMMANDS = 75                               # 73 compiles + llvm-link + ONE product link
CRC_TABLE_COMMAND_INDEX = 29                       # c2-stream-phase-02a.c (the generated CRC16 table source)
# Native rule of 2.5.4: no function changes except those forced by generated constants.
#   .text size      exactly BASE_TEXT_BYTES in the baseline AND in the new link (cap 0: any size change halts)
#   'changed'       no function may be classified changed (size change or unexplained byte)
#   'immediate'     same-size functions whose `<op> #imm` operands change by a generated-constant byte pair
#   metadata        no section may change size
# Measured on real link pairs (build/card-254-seed-prep-r1/probe/site-census.txt): constants reach the code
# through 27 immediate operands in 9 functions (c254_native_sites_20261004.json); the resident header COUNT
# macros have no consumer in the product compile (only the two ENTRY indexes are consumed, by repl.c).
NATIVE_TEXT_CAP = 0
BASE_TEXT_BYTES = 36899
NATIVE_TEXT_EXPECTED_CHANGED = ()
NATIVE_METADATA_EXPECTED = {'.lisp65_error_callsites': 0}   # exact: no new error call site
# `.text` functions that may be classified 'immediate' (every other function: exact or relocated).
NATIVE_TEXT_IMMEDIATE_ALLOWED = ('main',)
# Resident header macros that may move.  ENTRY indexes (REPL_BANNER_ENTRY, NATIVE_READ_LINE_ENTRY) are
# immediates of `repl`; they must NOT move in 2.5.4 (no resident function is added, removed or reordered).
STDLIB_HEADER_MAY_CHANGE = ('BLOB_BYTES', 'LITERAL_INDEX_COUNT', 'LITERAL_NODE_COUNT', 'LITERAL_PATCH_COUNT')
# [REVIEWER-DECISION] immediate-shape flags accepted before the link (normally empty).  A flag means a new
# constant byte creates or removes a coincidence (zero, equal or +-1 to a neighbouring immediate) that can
# change instruction selection and therefore a function SIZE (2.5.3: SHELF 0x0184E3 -> 0x018978 cost `main`
# +2 B because the 0x84 coincidence went away).  An accepted flag needs an owner decision on `.text`.
NATIVE_SHAPE_ACCEPTED = ()
NATIVE_SITES_SHA256 = '0fc696bf3699c7bacb6ed55150605350715f7cce13fadbc79dab497ac64cd573'   # sha256 of <SITES_TOOL> (next to this file)

# ------------------------------------------------------------- capacities
LIMITS = dict(code=60758, entries=2048, resolutions=4096, roots=1536, images=64)
# Minimum headroom after the 2.5.4 growth (host model: static plane + all six packages).  Resolutions were the
# tightest in the 2.5.3 record (3,762 of 4,096).  [REVIEWER-DECISION] floors; a miss halts the preflight (free).
HEADROOM = dict(code=4096, entries=512, resolutions=256, roots=512, images=32)
SYMBOL_LIMITS = dict(symbols=1008, namepool=16351)
SYMBOL_MARGIN = dict(symbols=32, namepool=384)
C2D_DELIVERED_BYTES = 50816
# Static plane keys (order matters: same as substitution-artifacts.json).
KEYS = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
EXPECT_CHANGED = ('stdlib-p0', 'ide', 'lcc')
EXPECT_EXACT = ('idex', 'm65d', 'buffer')
# Expected candidate image blobs (sha256, code bytes).  A different blob halts the PREFLIGHT (free), in dry mode
# too.  Measured by the phase-1 dry chain on 8bd8f1db (build/card-254-seed-prep-r1/dry, proposal A) and
# reproduced by the phase-2 dry chain on 04294d56 (build/card-254-preflight-dry-r1*); lcc must be the image the
# lcc-nesting-ladder-v254 gate proved (109 objects, 8,401 B, sha 8e8c1365...).  With another ide seam variant
# the ide blob, the static code bytes, the build id and SHELF bytes all differ.
CANDIDATE_BLOBS = {
    'stdlib-p0': ('6ed68c796dcf347eaeb5c30e96829ffe364cb70888a7ea8e123ef9cb8d8b1bcb', 19860),   # 2.5.3 19,814 (+46: mapcan)
    'ide': ('84a7d3e443d384d5bf1c72cf765188315913be02bfa2aaee9e85fa184d21a4aa', 15223),         # 2.5.3 15,063 (+160)
    'idex': ('8e3b8936694f631873346e57ad652ed182b82ed48d9b2fc93bffef474c663e39', 2940),         # image EXACT (blob placeholders differ)
    'm65d': ('80f1a7553ad8e8d46deca508487bfd15f0869fddda2fa1c5e151a4c745257d04', 4373),         # = 2.5.3
    'buffer': ('d218ff4ba23620eb02fbdb35c4b9795cf98404c0955091bcb7ded6487c24c747', 104),        # = 2.5.3
    'lcc': ('8e8c13652677e084348b41c5eb2a7299e61068fb92cd7476a66a7f645d13baca', 8401),          # = the ladder-gate image (+52)
}
CANDIDATE_STATIC_CODE_BYTES = 50901
# [REVIEWER-DECISION D-E3] The product-world E3 proof (build/card-254-e3-product-r1/notes.txt: exhaustive abort
# sweep on the projected product IDE world, 0 violations; controls no-copy and without-proposal-A fail) ran on
# exactly this emitted ide image.  The tools refuse preflight and Seed unless (i) the emitted ide image is this
# blob AND the E3 harness world compiled from the projected sources is byte-identical to it, and (ii) the
# product-world E3 check holds on it: preflight runs a reduced discriminating sweep (library point set),
# `c254_seed_producer.py e3` the exhaustive one into the write-once directory E3, which rehearse and seed require.
E3_PROOF_IDE_BLOB = ('84a7d3e443d384d5bf1c72cf765188315913be02bfa2aaee9e85fa184d21a4aa', 15223)
# Per-image code price window (bytes) against the 2.5.3 image: (min, max).  Card prices: ide +160, lcc +52,
# stdlib-p0 +46 (host lib-world figures; the product IDE world is a different composition, so ide has a window).
IMAGE_DELTA_WINDOW = {'stdlib-p0': (46, 46), 'ide': (1, 320), 'lcc': (52, 52), 'idex': (0, 0), 'm65d': (0, 0),
                      'buffer': (0, 0)}
# idex is emitted through the closure route (mk/workbench-service-inventory.mk: V2_WORKBENCH_CODEMOD_TOOL).
CODEMOD_TOOL = 'v2_workbench_codemod_disk_r8_20261001'
CLOSURE_CONFIG = 'config/v2-workbench-artifact-closure-disk-r8-20261001.json'
M65D_SOURCE_SUITE = 'tests/bytecode/libs/p0-m65d-lib-disk-r8-20261001.json'
# ---------------------------------------------- product emission projection
# The delivered static images are NOT the Makefile route.  Since 2.5.3 each delivered image is the emission of
# a PROJECTED frozen world; the 2.5.3 worlds are the suites build/card-253-preflight-r8/emission/<key>/suite.json
# (their sources: frozen v1.5.0-era files plus the 2.5.3 projected copies under .../projection/<key>/sources).
# 2.5.4 projects the BASE_AUTHORITY -> authority change of each lib file onto the source file of that 2.5.3
# world with the same role: "the old text" is the 2.5.3 world's own file (a 2.5.3 projected copy, or the
# frozen file when 2.5.3 did not touch it).  Whole file when that file is exactly T(lib@BASE_AUTHORITY),
# otherwise diff hunks whose old text occurs exactly once (T = identity or codemod rewrite_tokens); a hunk
# that does not occur needs a reviewed PRODUCT_SEAM below.  Measured 2026-10-04 on 8bd8f1db
# (build/card-254-seed-prep-r1/probe/projection_probe.txt).
PROJECTIONS = {
    'stdlib-p0': {'stdlib-lists.lisp': 'lib/stdlib-lists.lisp',                 # whole-file, identity
                  'domain-tier1-sealed.lisp': 'lib/domain-tier1.lisp'},         # 1 hunk (mapcan), identity
    'ide': {'ide-buffer.lisp': 'lib/ide-buffer.lisp',                           # whole-file, rewrite_tokens
            'ide-keymap-generated.lisp': 'lib/ide-keymap-generated.lisp',       # whole-file, identity (frozen ide-exit-r5 copy)
            'source-36ba4108c582.lisp': 'lib/ide-ui.lisp',                      # 2 hunks project, 3 need PRODUCT_SEAMS
            'product-ide-disk.lisp': 'lib/ide-disk.lisp'},                      # whole-file, rewrite_tokens
    'lcc': {'lcc.lisp': 'lib/lcc.lisp',                                         # 2 hunks, identity
            'lcc-profile.lisp': 'lib/dialect-v2/lcc-profile.lisp'},             # whole-file, identity
}
# [REVIEWER-DECISION D-E3] lib/ide-ui.lisp hunks that do NOT occur in the shipped IDE world.  The shipped world
# (130 defuns; blocking loop ide-run + %ide-drain-pending with (poll-key)) has no %ide-idle / %ide-init /
# %ide-poll, so the E3 publication (lib: before `(%ide-idle 4 ...)`) and the pending-C-x reset (lib: in
# %ide-init) cannot be carried over by the unique-seam rule.  Each entry binds ONE lib hunk by the sha256 of
# its (old, new) text and names what the product world gets instead:
#   action 'skip'     the lib hunk has no product counterpart (comment-only change of a comment that differs)
#   action 'replace'  product_old occurs exactly once in the product file and becomes product_new
# DECIDED (D-E3, reviewer): proposal A is adopted -- the same publication before the product's `(poll-key)` in
# %ide-drain-pending; reset of ide-event-command in `ide`; the E3 comment hunk is skipped with a reason.
# Host-proven on the projected product world (build/card-254-e3-product-r1/notes.txt) and re-proven by every
# preflight (reduced sweep) and by the mandatory exhaustive E3 step (see E3_PROOF_IDE_BLOB).
PRODUCT_SEAMS = {
    ('ide', 'lib/ide-ui.lisp'): (
        dict(lib_hunk='E3 comment',
             lib_hunk_sha256='d17a7860edf7e86a0de8ea2355136f38909872bb44f1778fff158c34fac30595', action='skip',
             reason='comment block; the product file carries an older comment'),
        dict(lib_hunk='E3 publication in %ide-drain-pending',
             lib_hunk_sha256='558ed0f35d5bf9be064a55264dd63c607ee5799ae984a8ef8324dd873c81479f', action='replace',
             product_old=('         (if k\n'
                          '             (%ide-drain-pending (ide-step state k))\n'
                          '             state))\n'
                          '       (poll-key))))\n'),
             product_new=('         (if k\n'
                          '             (%ide-drain-pending (ide-step state k))\n'
                          '             state))\n'
                          '       (progn\n'
                          '         ((lambda (buf alist)\n'
                          '            (if (if alist (eq (car buf) (car (car alist))) nil)\n'
                          '                (rplacd (car alist) buf)\n'
                          '                (%ide-store-buffer buf)))\n'
                          '          (ide-state-buffer state)\n'
                          '          (%ide-buffers-alist))\n'
                          '         (poll-key)))))\n')),
        dict(lib_hunk='pending C-x reset (%ide-init)',
             lib_hunk_sha256='46936475f0375f682bb8380db56c25c7d44548d19ebb32a5864188e867678adb', action='replace',
             product_old=('(defun ide (&rest name)\n'
                          '  (progn\n'
                          '    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))\n'),
             product_new=('(defun ide (&rest name)\n'
                          '  (progn\n'
                          '    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))\n'
                          '    (set-symbol-value (quote ide-event-command) nil)\n')),
    ),
}
# Changed lib files that reach the product through a package (L65S re-emission), not a static image.
PACKAGE_ROUTED_LIB = {'lib/defstruct.lisp': 'defstruct', 'lib/lite-hot.lisp': 'repl-comfort',
                      'lib/repl-comfort-v250.lisp': 'repl-comfort'}
# Changed lib files that reach NO product artifact; the preflight proves it (the file is a source of no
# emitted suite and of no package).
UNROUTED_LIB = {'lib/dialect-v2/lists-library.lisp': 'host dialect-v2 library copy of mapcan; in no product world',
                'lib/tests/ide-keymap-eval-cases.generated.json': 'generated host test cases'}
CLOSURE_ROUTED_LIB = ()
# Suite list edits: (key, field, old run, new run); each old run must occur exactly once (None = append).
# ide-bind-key takes the directory slot of the removed %ide-source-size, so no other IDE entry index moves.
SUITE_EDITS = (
    ('ide', 'functions', ['ide', '%ide-source-size', '%ide-copy-line'], ['ide', 'ide-bind-key', '%ide-copy-line']),
    ('ide', 'tailcall_self', ['%ide-source-size'], []),
)
IDE_CASE_SOURCE = 'tests/bytecode/libs/p0-ide-lib.json'
BUFFER_SUITE = 'tests/bytecode/libs/p0-buffer-lib.json'
# Host-source era cache (filled by prime_era() BEFORE the audit hook; no git under the hook).
ERA_PREFIXES = ('lib/', 'tests/bytecode/libs/', 'tests/bytecode/stdlib/', 'tests/bytecode/runtime/',
                'tests/bytecode/demos/', 'tests/bytecode/suites/')
ERA_CACHE = {}
CHANGED_LIB = None
# ------------------------------------------------- L65S package re-emission
# Six packages in directory order.  FROZEN = envelope rebound to the new static build id, content and index row
# exact (as in 2.5.3).  REEMIT = emitted from the live sources; the baseline control re-emits the SAME recipe
# inside the BASE_AUTHORITY era and must reproduce the delivered 2.5.3 payload and index row byte for byte.
PACKAGE_NAMES = ('buffer', 'place', 'string-extra', 'inspect', 'defstruct', 'repl-comfort')
PACKAGES_REEMIT = ('defstruct', 'repl-comfort')
PACKAGE_SOURCES = {
    'repl-comfort': ('lib/comfort-state-address.lisp', 'lib/lite-hot.lisp', 'lib/repl-comfort-v250.lisp', 'lib/lite.lisp'),
    'defstruct': ('lib/defstruct.lisp',),
}
PACKAGE_SUITE = {
    'repl-comfort': 'config/comfort-default-plane/libraries/repl-comfort-suite.json',
    'defstruct': 'config/c2-v240-public-plane/libraries/defstruct-suite.json',
}
# Residents are FROZEN worlds only.  REPL-COMFORT is emitted against the tracked r4-era resident (the symbol
# population its loader was emitted against since 2.5.1; same as c2_v253_r2_public_libraries.comfort_reemission)
# with the list-domain pre-check waived.  DEFSTRUCT's own suite names the live resident
# tests/bytecode/libs/p0-stdlib-require-resolver.json, whose sources are build/bytecode/dialect-v2/sources/...
# (gate-rebuilt, not bindable: 2.5.2 Final r2 lesson); it is emitted against the PRODUCT resident of the same
# side instead.  Measured 2026-10-04 (probe/defstruct_resident_probe.py): baseline era + r8 product resident
# reproduces the delivered 2.5.3 DEFSTRUCT payload and row exactly; the candidate payload is identical under
# both residents (payload f6a78d52..., 2,935 B).
PRODUCT_RESIDENT = '@product-resident'
PACKAGE_RESIDENT = {
    'repl-comfort': 'config/c2-v253-r2-public-plane/comfort-reemission/build/o2-lite-r4-slots-preflight/planes/resident.json',
    'defstruct': PRODUCT_RESIDENT,
}
PACKAGE_LIST_DOMAIN_WAIVER = ('repl-comfort',)
# Config files the BASE era must also see at BASE_AUTHORITY (the Comfort suite gains %lt-fit / %lt-write).
ERA_EXTRA_PATHS = tuple(PACKAGE_SUITE.values())
# Index row fields a re-emitted package may move; everything else (name, locator, dependencies, images,
# execution source) is exact.  Rows of FROZEN packages are exact.
PACKAGE_INDEX_FIELDS = ('artifact_bytes', 'bank2', 'combined_crc32', 'entries', 'resolutions', 'roots', 'scratch')
# Price windows: (min, max) code-byte delta, library bound, largest object.  Card prices +112 / +13.
PACKAGE_DELTA_WINDOW = {'repl-comfort': (1, 129), 'defstruct': (1, 13)}
PACKAGE_LIBRARY_BOUND = {'repl-comfort': 3000}
PACKAGE_MAX_OBJECT = 255
PACKAGE_NEW_SYMBOLS = {'repl-comfort': ('%lt-fit', '%lt-write'), 'defstruct': ()}
# Expected re-emitted package loader code blobs (sha256, bytes); a different blob halts the PREFLIGHT (free).
PACKAGE_BLOBS = {
    'defstruct': ('4e2f8e7f5d991acfd5d6c03342c176f41ab651b044e83a372417038fff2f4c4e', 1051),
    'repl-comfort': ('b5677e317b5e95c15f58edc47163346c96ccc757388de9cbe71ad395c416a7c9', 2207),
}

# --------------------------------------------- Final identity (after Seed)
# The Final pins live in c254_final_pins.py.  These placeholders stay None for ever (2.5.3 lesson).
SEED_RECEIPT_SHA = None
RECIPE_SHA = None
ARTIFACT_SHA = dict(ELF=None, PRG=None, LTO=None, D81=None)
ARTIFACT_PATH = dict(ELF='wplto/resident-island-seed.prg.elf',
                     PRG='wplto/resident-island-seed.prg',
                     LTO='wplto/resident-island-seed.prg.lto.o',
                     D81=f'{MEDIA_DIR}/{MEDIA_NAME}')
SEAL_SHA = None


assert 'C254_SEAMS' not in os.environ, 'C254_SEAMS was a phase-1 probe switch; PRODUCT_SEAMS is decided (D-E3)'


def artifacts():
    missing = [k for k, v in ARTIFACT_SHA.items() if not v]
    if missing or not (SEED_RECEIPT_SHA and RECIPE_SHA):
        raise ValueError('Final constants not set after Seed: ' + ','.join(missing))
    return {k: (ARTIFACT_PATH[k], ARTIFACT_SHA[k]) for k in ARTIFACT_PATH}


def installed(names):
    return ['tools/host-lisp/' + n for n in names]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def product_seams(key, lib):
    """The reviewed product seams of one projection, or () when the projection needs none."""
    if (key, lib) not in PRODUCT_SEAMS:
        return ()
    seams = PRODUCT_SEAMS[(key, lib)]
    assert seams is not None, ('product seam decision open (c254_config.PRODUCT_SEAMS)', key, lib)
    return tuple(seams)


# Source roots whose bytes the Seed consumes.  HEAD may be a DESCENDANT of the authority commit
# (tool installation, replay commit, journal), but none of these may differ.
CONSUMED_ROOTS = ('lib', 'src', 'tests/bytecode', 'config', 'scripts', 'Makefile', 'mk')
AUTHORITY_CHECK = None


def _git(*args, check=True):
    import subprocess
    return subprocess.run(['git', *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check,
                          env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def native_unchanged(commit):
    """Premise of the 2.5.4 native rule: src/ is identical at BASE_AUTHORITY and at `commit` (read-only)."""
    assert _git('diff', '--quiet', BASE_AUTHORITY, commit, '--', *NATIVE_UNCHANGED_ROOTS, check=False).returncode == 0, \
        'native source differs from 2.5.3 (BASE_AUTHORITY): the 2.5.4 native rule does not apply'
    return {root: _git('rev-parse', '--verify', f'{commit}:{root}').stdout.strip() for root in NATIVE_UNCHANGED_ROOTS}


def verify_authority():
    """Read-only git queries, run by the CLI BEFORE the write/process audit hook is installed."""
    global AUTHORITY_CHECK
    if DRY:
        return verify_dry()
    assert AUTHORITY_PIN, 'AUTHORITY_PIN not set (reviewer sets it after the green sealed run; dry mode: C254_DRY_WORKTREE=1)'
    assert re.fullmatch('[0-9a-f]{8,40}', AUTHORITY), 'set C254_AUTHORITY (commit prefix, lower-case hex)'
    assert AUTHORITY_PIN.startswith(AUTHORITY), 'C254_AUTHORITY is not a prefix of the pinned authority'
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
    assert _git('merge-base', '--is-ancestor', BASE_AUTHORITY, full, check=False).returncode == 0, \
        'authority does not descend from the 2.5.3 authority'
    AUTHORITY_CHECK = dict(requested=AUTHORITY, authority=full, observed=head, relation=relation,
                           consumed_roots=list(CONSUMED_ROOTS), root_trees=consumed_root_trees(full),
                           native_unchanged=native_unchanged(full))
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
    assert _git('diff', '--quiet', BASE_AUTHORITY, '--', *NATIVE_UNCHANGED_ROOTS, check=False).returncode == 0, \
        'native source differs from 2.5.3 (BASE_AUTHORITY) in the working tree'
    AUTHORITY_CHECK = dict(requested='dry-worktree', authority=authority_label(), observed=head, relation=relation,
                           consumed_roots=list(CONSUMED_ROOTS), root_trees=worktree_root_digests(),
                           uncommitted=changed, dry=True, native_unchanged='working tree == ' + BASE_AUTHORITY)
    return AUTHORITY_CHECK


def prime_era(commit=BASE_AUTHORITY):
    """Read-only: cache every era-selectable host source at `commit` (git cat-file, before the
    audit hook), the era-extra config files, and the lib/ files changed between BASE_AUTHORITY and the authority."""
    global CHANGED_LIB
    import subprocess
    names = [n for n in _git('ls-tree', '-r', '--name-only', commit, '--', 'lib', 'tests/bytecode').stdout.splitlines()
             if n.startswith(ERA_PREFIXES) and (n.endswith('.lisp') if n.startswith('lib/') else n.endswith('.json'))]
    names += [n for n in ERA_EXTRA_PATHS if n not in names]
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


def routed_lib():
    """Every changed lib file must have exactly one declared route."""
    routes = [{lib for m in PROJECTIONS.values() for lib in m.values()}, set(PACKAGE_ROUTED_LIB),
              set(UNROUTED_LIB), set(CLOSURE_ROUTED_LIB)]
    total = set().union(*routes)
    assert sum(len(r) for r in routes) == len(total), 'a lib file has two routes'
    return sorted(total)


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
                PREP=PREP, REHEARSAL=REHEARSAL, E3=E3)


def check(*, stage):
    """Read-only constant validation.  stage in {seed, final}."""
    problems = []
    # 1. The frozen baseline must still be exactly what the constants say, in the Seed r8 AND the Final r8.
    for label, rel, want in BASE_ARTIFACTS:
        for where in (BASE, BASE_FINAL):
            if sha256_file(ROOT / where / rel) != want:
                problems.append(f'{label} drift: {where}/{rel}')
    # 2. Baseline recipe shape: 75 commands, the CRC table source where the producer expects it, and no
    #    compiled source outside the baseline's own materialised inputs.
    recipe = json.loads((ROOT / BASE_NATIVE / 'command-proof.json').read_text())['commands']
    if len(recipe) != NATIVE_COMMANDS:
        problems.append('baseline recipe is not 75 commands')
    else:
        compiled = [c[c.index('-c') + 1] for c in recipe[:73]]
        if not compiled[CRC_TABLE_COMMAND_INDEX].endswith('c2-stream-phase-02a.c'):
            problems.append('CRC table source is not frozen command %d' % CRC_TABLE_COMMAND_INDEX)
        if not all(p.startswith(BASE_NATIVE + '/') for p in compiled):
            problems.append('a baseline compile reads a source outside ' + BASE_NATIVE)
    # 3. Baseline static constants.
    frozen = json.loads((ROOT / BASE_PLANE / 'product/substitution-artifacts.json').read_text())
    if frozen['product_build_id_hex'] != BASE_PRODUCT_BUILD_ID or frozen['artifacts']['shelf']['bytes'] != BASE_SHELF_BYTES:
        problems.append('baseline static plane constants drift')
    # 4. Write-once names must not exist yet (seed stage) / must exist (final).
    if stage == 'seed':
        if (ROOT / SEED).exists():
            problems.append('write-once name already claimed: ' + SEED)
        if not DRY and (CANDIDATE_BLOBS is None or PACKAGE_BLOBS is None or CANDIDATE_STATIC_CODE_BYTES is None
                        or NATIVE_SITES_SHA256 is None):
            problems.append('candidate image / package / site-table pins not set (run the dry chain first)')
        if any(v is None for v in PRODUCT_SEAMS.values()):
            problems.append('PRODUCT_SEAMS decision open (reviewer decision D-E3)')
    else:
        if (ROOT / FINAL).exists():
            problems.append('Final name already claimed: ' + FINAL)
        if not SOURCE_RUN.startswith('build/') or (ROOT / SOURCE_RUN).exists():
            problems.append('SOURCE_RUN must be a fresh build/ directory chosen by the reviewer')
        if not (ROOT / SEED / 'complete.json').exists():
            problems.append('Seed not complete')
    # 5. Names are all distinct and all below build/.
    values = list(run_names().values())
    if len(set(values)) != len(values) or not all(v.startswith('build/') for v in values):
        problems.append('run names collide or escape build/')
    if any(Path(v).is_relative_to(Path(b)) for v in (SEED, PREFLIGHT, SELFTEST, FINAL, REHEARSAL, E3)
           for b in (BASE, BASE_FINAL, BASE_PREFLIGHT)):
        problems.append('successor name inside a frozen 2.5.3 directory')
    # 5b. D-E3: the emitted ide image is pinned to the image the product-world E3 proof ran on.
    if CANDIDATE_BLOBS is not None and tuple(CANDIDATE_BLOBS['ide']) != tuple(E3_PROOF_IDE_BLOB):
        problems.append('ide image pin differs from the E3 proof image (re-run the product-world proof, D-E3)')
    if not (Path(__file__).resolve().parent / E3_TOOL).is_file():
        problems.append('product-world E3 harness missing: ' + E3_TOOL)
    # 6. Site table binding.
    sites = Path(__file__).resolve().parent / SITES_TOOL
    if NATIVE_SITES_SHA256 is not None and (not sites.is_file() or sha256_file(sites) != NATIVE_SITES_SHA256):
        problems.append('native site table is not the pinned file')
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
    names = [SEED, PREFLIGHT, SELFTEST, FINAL, SOURCE_RUN, PREP, REHEARSAL, E3]
    assert len(set(names)) == len(names) and all(n.startswith('build/') for n in names), 'name collision'
    assert SOURCE_RUN not in SOURCE_QUALIFIED_RUNS, 'would reuse a source-qualifying sealed run'
    assert set(EXPECT_CHANGED) | set(EXPECT_EXACT) == set(KEYS) and not set(EXPECT_CHANGED) & set(EXPECT_EXACT)
    assert set(IMAGE_DELTA_WINDOW) == set(KEYS) and all(IMAGE_DELTA_WINDOW[k] == (0, 0) for k in EXPECT_EXACT)
    assert CANDIDATE_BLOBS is None or (set(CANDIDATE_BLOBS) == set(KEYS) and
                                       sum(v[1] for v in CANDIDATE_BLOBS.values()) == CANDIDATE_STATIC_CODE_BYTES)
    assert NATIVE_TEXT_CAP == 0 and not NATIVE_TEXT_EXPECTED_CHANGED and not any(NATIVE_METADATA_EXPECTED.values()), \
        '2.5.4 native rule: no growth, no changed function, no metadata delta'
    assert set(PACKAGES_REEMIT) <= set(PACKAGE_NAMES) and set(PACKAGE_SOURCES) == set(PACKAGE_SUITE) == set(PACKAGES_REEMIT)
    assert set(PACKAGE_RESIDENT) == set(PACKAGES_REEMIT) and not any('build/bytecode' in r for r in PACKAGE_RESIDENT.values())
    assert set(PACKAGE_ROUTED_LIB.values()) <= set(PACKAGES_REEMIT)
    assert all(lib in PACKAGE_SOURCES[name] for lib, name in PACKAGE_ROUTED_LIB.items()), 'package route names a foreign source'
    routed_lib()
    assert set(k for k, _ in PRODUCT_SEAMS) <= set(PROJECTIONS) and all(lib in PROJECTIONS[k].values() for k, lib in PRODUCT_SEAMS)
    assert CANDIDATE_BLOBS is None or tuple(CANDIDATE_BLOBS['ide']) == tuple(E3_PROOF_IDE_BLOB), \
        'ide image pin differs from the E3 proof image (D-E3)'
    assert all(v is not None for v in PRODUCT_SEAMS.values()), 'PRODUCT_SEAMS decision open'
    assert [s['action'] for s in PRODUCT_SEAMS[('ide', 'lib/ide-ui.lisp')]] == ['skip', 'replace', 'replace'], 'D-E3 = proposal A'
    for seams in list(PRODUCT_SEAMS.values()):
        for seam in seams or ():
            assert seam['action'] in ('skip', 'replace')
            assert seam['action'] == 'skip' or (seam['product_old'] != seam['product_new'] and seam['product_old'])
    assert not any('card-253' in n or 'o2-lite' in n for n in names), 'stale 2.5.3 name'
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
        sys.exit('usage: c254_config.py selftest|check-seed|check-final')
