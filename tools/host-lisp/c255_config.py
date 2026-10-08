#!/usr/bin/env python3
"""Single source of every 2.5.5 Seed run-name and identity constant.

Successor of c254_config.py (derived by build/card-255-seed-prep-r1/drafts/derive_c255_config.py).  The c254
tools stay byte-identical: the 2.5.4 Seed/Final receipts bind their bytes.  Nothing here runs a product command.
`check` is pure read-only validation and `selftest` exercises the validators on synthetic data only.

2.5.5 = 2.5.4 Final r1 + a Lisp-only change of the IDE editor (four levers, faster typing).  What that means:
  - baseline            the 2.5.4 Seed, which lives in TWO directories since the r1b continuation:
                          BASE       build/card-254-product-r1b   receipts, medium, ELF/PRG/LTO copies
                          BASE_LINK  build/card-254-product-r1    the halted link attempt: 75 command logs, the
                                                                  materialised native inputs, the paths every
                                                                  frozen command and native receipt names
                        and the sealed Final build/card-254-final-r1 (byte-identical artifacts).
  - native code         NO source seam.  Every compiled input is the 2.5.4 materialised input; only the
                        generated-constant seams move (CRC16 table source, static plane size, compiler-input
                        assertions, -D build id / SHELF bytes).  `.text` stays 36,899 B.  The static plane
                        SHRINKS (ide -142 B): CODE.BIN, SHELF.BIN and the static code constant go DOWN.
  - static images       CHANGED ide only; EXACT stdlib-p0 / idex / m65d / buffer / lcc (byte-exact: an
                        ENTRY-EXACT image is a halt in 2.5.5)
  - L65S packages       none re-emitted; all six envelopes rebound (the static build id changes); L65INDEX exact
  - host                Fedora 45.  The 2.5.4 baseline was linked on Fedora 44; see HOST_TOOLS below.

CHANGE CHECKLIST -- every value marked [SET-AFTER-DRY-PREFLIGHT] / [REVIEWER-DECISION] must be
reviewed by a human before the step named.  The Final pins will live in c255_final_pins.py, never here (2.5.3
lesson: the Seed receipts bind this file).
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
# The 2.5.5 source authority: the commit whose consumed roots the GREEN sealed check-source run
# build/card-255-check-source-r1 qualified (receipt exit_code 0, 3,837 s, head f6333f4a before and after,
# changed_files [], changed_protected_files 0).  It is the source candidate itself.  Never the tools commit (this
# file cannot name its own commit; HEAD = tools commit descends with no consumed-root diff, D-5).
AUTHORITY_PIN = 'f6333f4ae4193245493909e74407d95ba6df10f0'
# The 2.5.5 source candidate (HEAD when these tools were drafted).  Dry mode only: parent of the working tree.
SOURCE_CANDIDATE = 'f6333f4ae4193245493909e74407d95ba6df10f0'
AUTHORITY = os.environ.get('C255_AUTHORITY', AUTHORITY_PIN or '')
# Dry mode (C255_DRY_WORKTREE=1): selftest/preflight/e3/rehearse against the UNCOMMITTED working tree on top of
# DRY_PARENT.  Every run name gets a 'dry-' tag, the root list hashes working-tree file contents, and `seed`
# is refused.  A dry preflight can never satisfy a Seed (different names, different authority label).
DRY_PARENT = AUTHORITY_PIN or SOURCE_CANDIDATE
DRY = os.environ.get('C255_DRY_WORKTREE') == '1'
# 2.5.4 source authority (Seed r1/r1b, Final r1, published 2.5.4).  It is the host-source ERA of the baseline
# control and the OLD side of every projection: lib/ and src/ are byte-identical from 04294d56 to the journal
# commit 45c2e5d2 after the publication (measured 2026-10-06: `git diff 04294d56 45c2e5d2 -- lib src` is empty).
BASE_AUTHORITY = '04294d56dd874268d8f679ff43c3622128900e7d'
# Roots that must be IDENTICAL between BASE_AUTHORITY and the authority ("native code unchanged").  The recipe
# compiles frozen materialised copies, not src/, so this is a premise check, not an input binding.
NATIVE_UNCHANGED_ROOTS = ('src',)

# Attempt tag.  Seed/Final directories are write-once; a HALT needs a NEW tag and a reviewed successor.
ATTEMPT = 'r1'
_DRY_SUFFIX = os.environ.get('C255_DRY_SUFFIX', '')
assert re.fullmatch('[a-z0-9]{0,4}', _DRY_SUFFIX) and (DRY or not _DRY_SUFFIX)
_TAG = ('dry-' + ATTEMPT + _DRY_SUFFIX) if DRY else ATTEMPT
# C255_NAME_ROOT: preparation probes only (dry mode): put every run directory below one prep directory.
_NAME_ROOT = os.environ.get('C255_NAME_ROOT', 'build')
assert _NAME_ROOT == 'build' or (DRY and re.fullmatch(r'build/card-255-[a-z0-9-]+(/[a-z0-9-]+)*', _NAME_ROOT)), \
    'C255_NAME_ROOT is a dry-mode probe switch only'
SEED_NAME = f'card-255-product-{_TAG}'
SEED = f'{_NAME_ROOT}/{SEED_NAME}'                       # Seed output (write-once)
PREFLIGHT = f'{_NAME_ROOT}/card-255-preflight-{_TAG}'    # host-only Chunk A (write-once)
SELFTEST = f'{_NAME_ROOT}/card-255-selftest-{_TAG}'      # producer selftest (write-once)
FINAL = f'{_NAME_ROOT}/card-255-final-{_TAG}'            # Final output (write-once)
REHEARSAL = f'{_NAME_ROOT}/card-255-prelink-{_TAG}'      # pre-link/post-link rehearsal (write-once, not a product)
E3 = f'{_NAME_ROOT}/card-255-e3-{_TAG}'                  # exhaustive product-world E3 sweep (write-once; D-E3)
PREP = 'build/final-255-prep'                            # replay preparation parent
MEDIA_DIR = 'media-255'
MEDIA_NAME = 'c255.d81'
# Sealed check-source run that qualifies the Final.  NOT the source-qualifying run.
# The green sealed check-source run that qualified AUTHORITY_PIN (unit lisp65-255-sealed-r1); `check` re-reads it.
SOURCE_QUALIFIED_RUNS = ('build/card-255-check-source-r1',)
SOURCE_RUN = f'build/card-255-check-source-final-{_TAG}'
FORMAT_REPLAY = 'card255-replay-v1'
FORMAT_SEAL = 'card255-final-seal-v1'
TOOL_NAMES = ('c255_final.py', 'c255_replay.py', 'c255_seal.py')
PRODUCT_TOOL = 'c255_product.py'
PRODUCER_TOOL = 'c255_seed_producer.py'
CONFIG_TOOL = 'c255_config.py'
SITES_TOOL = 'c255_native_sites_20261006.json'         # immediate-site census of the baseline (2.5.4) ELF (bound below)
E3_TOOL = 'c255_e3_product.py'                         # product-world E3 harness (independent references; bound by tool_identity)
E3_BASE_TOOL = 'c254_e3_product.py'                    # its base (worlds, VM, cases, point sets); imported, bound as `e3_base`

# ------------------------------------------------ frozen 2.5.4 baseline
BASE = 'build/card-254-product-r1b'                # Seed RECEIPTS: seed.json, complete.json, media, ELF/PRG/LTO copies
BASE_LINK = 'build/card-254-product-r1'            # LINK attempt (halted in the inventory, completed by r1b): the 75
#                                                    command logs, native/candidate-inputs, native/derived; every
#                                                    path inside the frozen commands and native receipts names it.
#                                                    HAZARD: BASE_LINK is a string prefix of BASE; never test a
#                                                    path with startswith(BASE_LINK) without a trailing '/'.
BASE_FINAL = 'build/card-254-final-r1'             # sealed Final (byte-identical ELF, PRG, LTO object and medium)
BASE_PREFLIGHT = 'build/card-254-preflight-r1'     # its candidate plane is the delivered 2.5.4 static plane
BASE_PLANE = BASE_PREFLIGHT + '/planes/candidate'
BASE_NATIVE = BASE_LINK + '/native'                # 75-command recipe with the 2.5.4 substitutions applied
BASE_MEDIA_DIR = 'media-254'
BASE_MEDIA_NAME = 'c254.d81'
BASE_MEDIA_RECEIPT = BASE + f'/{BASE_MEDIA_DIR}/runtime-receipt.json'
BASE_OVERLAY = {fam: BASE + f'/{BASE_MEDIA_DIR}/runtime-overlays-{fam}-final.json' for fam in ('boot', 'session')}
BASE_KERNAL_WINDOW = BASE + f'/{BASE_MEDIA_DIR}/kernal-window-publish-last.json'
BASE_MEDIUM_SHA = '250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d'
BASE_ELF_SHA = '7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244'
BASE_PRG_SHA = '192138eb70b4dc46a992e95651f52180a4e1687cd138b9347f8e3b77e37d70c4'
BASE_LTO_SHA = 'e9d6dc850e01dac45efb0dc1163ac3b463a5d26e00a49c3107380073da472afc'
BASE_PRODUCT_BUILD_ID = '0x829db958'
BASE_STATIC_CODE_BYTES = 50901
BASE_SHELF_BYTES = 101155
BASE_ARTIFACTS = (('medium', f'{BASE_MEDIA_DIR}/{BASE_MEDIA_NAME}', BASE_MEDIUM_SHA),
                  ('ELF', 'wplto/resident-island-seed.prg.elf', BASE_ELF_SHA),
                  ('PRG', 'wplto/resident-island-seed.prg', BASE_PRG_SHA),
                  ('LTO', 'wplto/resident-island-seed.prg.lto.o', BASE_LTO_SHA))
# The baseline's own receipts, pinned (values = c254_final_pins.py, re-hashed 2026-10-06).
BASE_SEED_RECEIPT_SHA = '8efe0ec4631994a65d3005e1889fce5bc806635277a60f4e546f1ac2388f3c6f'   # BASE/seed.json == BASE/complete.json
BASE_RECIPE_SHA = 'b037825d4ed307f7b8182a4998caeea41ff706c4860cac07cf921bbfc752125d'         # BASE_LINK/native/command-proof.json (== the BASE copy)
BASE_SEAL_SHA = '7b70c025ef66de595e1d2c050e6d65d54ed9d34243c807c8faf4618fda8e5603'           # BASE_FINAL/seal.json
BASE_PREFLIGHT_RECEIPT_SHA = 'e2715e373bc967f1f4b3905cba2b5b289a2b1cea83090a6a2e95dbf10b8fe4e0'   # BASE_PREFLIGHT/receipt.json
# The halted link attempt keeps its four records for ever; the 2.5.4 Final pinned the same values.
BASE_LINK_RECORDS = (('attempt.json', 'a08ddbdcfd658d5581a80a6742f4a026664e09f510a41cfa5e5bb1bf7b12e657'),
                     ('product-link-claim.json', '668fd5ccc692d8cd0eaec890d2beadfa22f84c0cbc726685a06f8352e13ea816'),
                     ('linked.json', '30c3d2b1f22189201a2b00114fb24327580778b179b3e77acc7a63f9da9dee89'),
                     ('halt.json', '7b6b6b0108eb1d2c88affbe5f0f585c8ae1600b06088a6ca9d99ca69dc558dd2'))
# Native receipts that exist in BOTH baseline directories and must be byte-identical (r1b carries copies).
BASE_NATIVE_TWINS = ('command-proof.json', 'command-ready.json', 'derived-inputs.json', 'include-closure.json',
                     'plane-price.json')
# The frozen host ABI helper: the SNAPSHOT the 2.5.4 preflight took.  NOT build/c2-lite/product-shaped-v6-probe/
# c2d-v6-entry-emitter-host.so: that file is gate-rebuilt (rebuilt on the Fedora 45 host on 2026-10-06, other
# bytes) and a pin on it would halt the preflight for a host reason.  The snapshot is a frozen file; what it
# computes is checked by every preflight (baseline plane replay, byte for byte).
ENTRY_EMITTER = BASE_PREFLIGHT + '/host/c2d-v6-entry-emitter-host.so'
ENTRY_EMITTER_SHA = 'b5f8d051c48c955ec5cfd9181f8ddf5fa199f452a8ae3fd7ce1407da6b354a2f'

# ------------------------------------------------------------------- host
# The 2.5.5 Seed, Final and reproductions all run on ONE host generation: Fedora 45 (the pins of
# c2_v254_r1_toolchain.HOST_TOOLS, measured again 2026-10-06: llvm-23.1.2-2.fc45, util-linux-2.42.4-1.fc45,
# gcc-16.2.1-2.fc45.1).  The baseline ELF was linked with the Fedora 44 tools.  What the 2.5.5 native rule relies
# on: "the Fedora 45 tools give, for the 2.5.4 inputs, the 2.5.4 ELF / LTO object / PRG / D81 byte for byte" --
# so that every difference the inventory sees after the link comes from the 2.5.5 inputs and not from the host.
# Evidence, bound below and checked by `check`: the two committed public reproductions of 2.5.4, made on Fedora
# 45 with exactly these tool hashes (HOST_EQUIVALENCE).  The merged bitcode that /usr/bin/llvm-link writes
# (command 73) is a HOST-DEPENDENT intermediate: it is recorded, never compared with a 2.5.4 file.
HOST = 'Fedora 45'
HOST_TOOLS = {'/usr/bin/llvm-link': 'dc265a662955c414c16eea8b4eec8af24322608bf6b5be6ee585f72fef90d47c',
              '/usr/bin/setarch': '8a6670f4aa0a72a08715a076549efa35832c0ce3b69c5926b96c6636a2075f3e',
              '/usr/bin/cc': '66317f5338535ded9ce9e2fc7b1c20d33bf96b7d6d1c35a71aa6dc309be3a57e'}
BASE_HOST = 'Fedora 44'
BASE_HOST_TOOLS = {'/usr/bin/llvm-link': 'fbf634ce234c92624853e51226c408e2325953d7266080f2c5a9c8847f383e40',
                   '/usr/bin/setarch': '84985115f7365b9a85aba1fa0a51da1feb9a31ff1df54e36cd577ab8e93d8e28',
                   '/usr/bin/cc': '153e46b4657620f2baef1b4a70b4b4f275772faa5b0fb9e415697e87ebcb7fea'}
HOST_EQUIVALENCE = dict(
    policy=('config/c2-v254-r1-reproduction-policy.json', 'c8f05222944ea6653de25379968da6176ddae0141a526c3b92078a2a92c8709b'),
    reproductions=('config/c2-v254-r1-reproductions.json', 'e2de5d747e72e7469ef3d115b9a505223566712fb1f35e924502759496ebc904'))

# ----------------------------------------------------------- native recipe
NATIVE_COMMANDS = 75                               # 73 compiles + llvm-link + ONE product link
CRC_TABLE_COMMAND_INDEX = 29                       # c2-stream-phase-02a.c (the generated CRC16 table source)
# Native rule of 2.5.5 (= the 2.5.4 rule): no function changes except those forced by generated constants.
# The reviewed commuting-pair class of the 2.5.4 continuation is NOT carried: the 2.5.4 ELF, now the 'before'
# side, already has the order clc ; sta $a at 0xc473.  A pair that flips back is a new, unreviewed difference.
#   .text size      exactly BASE_TEXT_BYTES in the baseline AND in the new link (cap 0: any size change halts)
#   'changed'       no function may be classified changed (size change or unexplained byte)
#   'immediate'     same-size functions whose `<op> #imm` operands change by a generated-constant byte pair
#   metadata        no section may change size
# Measured on real link pairs (build/card-254-seed-prep-r1/probe/site-census.txt) and carried to the 2.5.4 ELF
# (build/card-255-seed-prep-r1/probe/make_sites_c255.py, third pair 2.5.3 r8 -> 2.5.4): constants reach the
# code through 28 immediate operands in 9 functions (c255_native_sites_20261006.json); the resident header
# COUNT macros have no consumer in the product compile (only the two ENTRY indexes are consumed, by repl.c).
NATIVE_TEXT_CAP = 0
BASE_TEXT_BYTES = 36899
NATIVE_TEXT_EXPECTED_CHANGED = ()
NATIVE_METADATA_EXPECTED = {'.lisp65_error_callsites': 0}   # exact: no new error call site
# `.text` functions that may be classified 'immediate' (every other function: exact or relocated).
NATIVE_TEXT_IMMEDIATE_ALLOWED = ('main',)
# Resident header macros that may move: NONE in 2.5.5 (the resident image stdlib-p0 is EXACT).
STDLIB_HEADER_MAY_CHANGE = ()
# [REVIEWER-DECISION] immediate-shape flags accepted before the link (normally empty).  A flag means a new
# constant byte creates or removes a coincidence (zero, equal or +-1 to a neighbouring immediate) that can
# change instruction selection and therefore a function SIZE (2.5.3: SHELF 0x0184E3 -> 0x018978 cost `main`
# +2 B because the 0x84 coincidence went away).  An accepted flag needs an owner decision on `.text`.
NATIVE_SHAPE_ACCEPTED = ()
NATIVE_SITES_SHA256 = 'e178f5d7b4ae3ba6434fddd1494e38e2327ac137a6bccb1622f7f0daca56a44d'   # sha256 of <SITES_TOOL> (next to this file)

# ------------------------------------------------------------- capacities
LIMITS = dict(code=60758, entries=2048, resolutions=4096, roots=1536, images=64)
# Minimum headroom (host model: static plane + all six packages).  Resolutions are the tightest in the 2.5.4
# record (3,784 of 4,096: 312 left).  [REVIEWER-DECISION] floors as in 2.5.4; a miss halts the preflight (free).
HEADROOM = dict(code=4096, entries=512, resolutions=256, roots=512, images=32)
SYMBOL_LIMITS = dict(symbols=1008, namepool=16351)
SYMBOL_MARGIN = dict(symbols=32, namepool=384)
C2D_DELIVERED_BYTES = 50816
# Static plane keys (order matters: same as substitution-artifacts.json).
KEYS = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
EXPECT_CHANGED = ('ide',)
EXPECT_EXACT = ('stdlib-p0', 'idex', 'm65d', 'buffer', 'lcc')
# 2.5.5: an image expected EXACT must be byte-exact (code and metadata); ENTRY-EXACT (layout moved) is a halt.
# No image may gain or lose an object (L1-L4 change bodies only: 204 IDE objects before and after).
EXACT_IS_BYTE_EXACT = True
OBJECT_POPULATION_FROZEN = True
# [SET-AFTER-DRY-PREFLIGHT confirm] symbols that may appear in the product symbol set: none.
NEW_SYMBOLS_EXPECTED = ()
# Expected candidate image blobs (sha256, code bytes).  A different blob halts the PREFLIGHT (free), in dry mode
# too.  ide: measured 2026-10-06 on the s4 product world of build/card-255-typing-r1 (world.json), whose four
# projected sources are byte-identical to what project_text gives for lib@04294d56 -> lib@f6333f4a with the two
# L2 seams below (build/card-255-seed-prep-r1/probe/projection-with-seams.json).  The other five: the 2.5.4
# candidate blobs (build/card-254-preflight-r1/candidate-blobs.json).
# [SET-AFTER-DRY-PREFLIGHT] confirm all six against <dry preflight>/candidate-blobs.json; the five EXACT images
# are pinned to the 2.5.4 blob FILES, and a blob file can differ in literal-table placeholders while the image
# is EXACT (2.5.4 note on idex) -- if the dry preflight shows that, re-pin the blob and keep the EXACT rule.
CANDIDATE_BLOBS = {
    'stdlib-p0': ('6ed68c796dcf347eaeb5c30e96829ffe364cb70888a7ea8e123ef9cb8d8b1bcb', 19860),   # = 2.5.4
    'ide': ('27bfa66240ede0654a359e13f9a10736b708ba3881b7b04196bdacd6710d4e9b', 15081),         # 2.5.4 15,223 (-142)
    'idex': ('8e3b8936694f631873346e57ad652ed182b82ed48d9b2fc93bffef474c663e39', 2940),         # = 2.5.4
    'm65d': ('80f1a7553ad8e8d46deca508487bfd15f0869fddda2fa1c5e151a4c745257d04', 4373),         # = 2.5.4
    'buffer': ('d218ff4ba23620eb02fbdb35c4b9795cf98404c0955091bcb7ded6487c24c747', 104),        # = 2.5.4
    'lcc': ('8e8c13652677e084348b41c5eb2a7299e61068fb92cd7476a66a7f645d13baca', 8401),          # = 2.5.4
}
CANDIDATE_STATIC_CODE_BYTES = 50759                # 50,901 - 142
# The product-world E3 proof (c255_e3_product.py: references independent of the swept world, the control without
# the publication must fail in BOTH shapes, named regression point) ran exhaustively on exactly this emitted ide
# image (build/card-255-typing-r1/e3-255/exhaustive-s4: PASS).  The tools refuse preflight and Seed unless (i) the
# emitted ide image is this blob AND the E3 harness world compiled from the projected sources is byte-identical
# to it, and (ii) the check holds on it: preflight runs the reduced sweep, `c255_seed_producer.py e3` the
# exhaustive one into the write-once directory E3, which rehearse and seed require.
E3_PROOF_IDE_BLOB = ('27bfa66240ede0654a359e13f9a10736b708ba3881b7b04196bdacd6710d4e9b', 15081)
# Per-image code price window (bytes) against the 2.5.4 image: (min, max).  NEGATIVE for ide: the card makes the
# image smaller (accessors written out, one store instead of one per key).  Exact, because the blob is pinned.
IMAGE_DELTA_WINDOW = {'stdlib-p0': (0, 0), 'ide': (-142, -142), 'lcc': (0, 0), 'idex': (0, 0), 'm65d': (0, 0),
                      'buffer': (0, 0)}
# idex is emitted through the closure route (mk/workbench-service-inventory.mk: V2_WORKBENCH_CODEMOD_TOOL).
CODEMOD_TOOL = 'v2_workbench_codemod_disk_r8_20261001'
CLOSURE_CONFIG = 'config/v2-workbench-artifact-closure-disk-r8-20261001.json'
M65D_SOURCE_SUITE = 'tests/bytecode/libs/p0-m65d-lib-disk-r8-20261001.json'
# ---------------------------------------------- product emission projection
# The delivered static images are NOT the Makefile route.  Since 2.5.3 each delivered image is the emission of
# a PROJECTED frozen world; the 2.5.4 worlds are the suites build/card-254-preflight-r1/emission/<key>/suite.json
# (their sources: frozen v1.5.0-era files plus the 2.5.4 projected copies under .../projection/<key>/sources).
# 2.5.5 projects the BASE_AUTHORITY -> authority change of each lib file onto the source file of that 2.5.4
# world with the same role.  Whole file when that file is exactly T(lib@BASE_AUTHORITY), otherwise diff hunks
# whose old text occurs exactly once (T = identity or codemod rewrite_tokens); a hunk that does not occur needs
# a reviewed PRODUCT_SEAM below.  Measured 2026-10-06 with the unchanged project_text of c254_product.py
# (build/card-255-seed-prep-r1/probe/projection_c255.py):
#   lib/ide-buffer.lisp            whole file, rewrite_tokens      (L3)
#   lib/ide-keymap-generated.lisp  whole file, identity            (L1, L4)
#   lib/ide-ui.lisp                15 hunks, identity: 13 project (L3), 2 need the L2 seams
# lib/ide-disk.lisp did not change and has no entry (an entry for an unchanged file is refused).
PROJECTIONS = {
    'ide': {'ide-buffer.lisp': 'lib/ide-buffer.lisp',
            'ide-keymap-generated.lisp': 'lib/ide-keymap-generated.lisp',
            'source-36ba4108c582.lisp': 'lib/ide-ui.lisp'},
}
# [REVIEWER-DECISION D-L2] lib/ide-ui.lisp hunks that do NOT occur in the shipped IDE world.  The shipped loop is
# ide-run + %ide-drain-pending with (poll-key); it has no %ide-poll / %ide-init, so lever L2 (no store per key,
# ONE store at entry) is carried by two reviewed seams (build/card-255-typing-r1/product-seams-L2.json; the
# product texts are copied from it byte for byte).  Each entry binds ONE lib hunk by the sha256 of its
# (old + NUL + new) text as project_text groups it (3 lines of context).
PRODUCT_SEAMS = {
    ('ide', 'lib/ide-ui.lisp'): (
        dict(lib_hunk='L2 no persist per key (ide-run)',
             lib_hunk_sha256='8eb0c9b43ea31b8aa8c3d00bbab44c221d14ceac2369fed81f5ef721cfd017ce', action='replace',
             product_old=('   (progn (%ide-input-open) (%ide-persist-state state))))\n'),
             product_new=('   (progn (%ide-input-open) state)))\n')),
        dict(lib_hunk='L2 one persist at entry (ide)',
             lib_hunk_sha256='a93a6f8fa027c587250947eeb6cc6d5f1352259f4d53914ca45adfc918fe1c04', action='replace',
             product_old=('     (ide-run (ide-render (ide-make-state\n'
                          '                                      (%ide-resume-buffer\n'
                          '                                       (if name (car name) nil))))))))\n'),
             product_new=('     (ide-run (%ide-persist-state\n'
                          '               (ide-render (ide-make-state\n'
                          '                            (%ide-resume-buffer\n'
                          '                             (if name (car name) nil)))))))))\n')),
    ),
}
# The two E3 seams of 2.5.4 (c254_config.PRODUCT_SEAMS, the 'replace' entries, texts copied byte for byte).  They
# are NOT projection seams any more: the 2.5.4 product file already carries their product_new text, and the
# 2.5.4 -> 2.5.5 lib diff does not touch those hunks.  The E3 harness needs them to build its control world
# "without the publication" (product_new -> product_old; each product_new must occur exactly once in the
# projected product file, or the harness refuses).
E3_PUBLICATION_SEAMS = (
    dict(lib_hunk='E3 publication in %ide-drain-pending', action='replace',
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
    dict(lib_hunk='pending C-x reset (%ide-init)', action='replace',
         product_old=('(defun ide (&rest name)\n'
                      '  (progn\n'
                      '    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))\n'),
         product_new=('(defun ide (&rest name)\n'
                      '  (progn\n'
                      '    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))\n'
                      '    (set-symbol-value (quote ide-event-command) nil)\n')),
)
# Changed lib files that reach the product through a package (L65S re-emission): none in 2.5.5.
PACKAGE_ROUTED_LIB = {}
# Changed lib files that reach NO product artifact: none in 2.5.5.
UNROUTED_LIB = {}
CLOSURE_ROUTED_LIB = ()
# Suite list edits: (key, field, old run, new run).  None in 2.5.5: the function list of the IDE world does not
# change (measured: the s4 world suite equals the 2.5.4 suite in every field but `sources`).
SUITE_EDITS = ()
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
PACKAGES_REEMIT = ()                               # 2.5.5: all six FROZEN (envelope rebound, content and index row exact)
PACKAGE_SOURCES = {}
PACKAGE_SUITE = {}
PRODUCT_RESIDENT = '@product-resident'
PACKAGE_RESIDENT = {}
PACKAGE_LIST_DOMAIN_WAIVER = ()
ERA_EXTRA_PATHS = ()
# Index row fields a re-emitted package may move; everything else (name, locator, dependencies, images,
# execution source) is exact.  Rows of FROZEN packages are exact.
PACKAGE_INDEX_FIELDS = ('artifact_bytes', 'bank2', 'combined_crc32', 'entries', 'resolutions', 'roots', 'scratch')
PACKAGE_DELTA_WINDOW = {}
PACKAGE_LIBRARY_BOUND = {}
PACKAGE_MAX_OBJECT = 255
PACKAGE_NEW_SYMBOLS = {}
PACKAGE_BLOBS = {}

# --------------------------------------------- Final identity (after Seed)
# The Final pins will live in c255_final_pins.py.  These placeholders stay None for ever (2.5.3 lesson).
SEED_RECEIPT_SHA = None
RECIPE_SHA = None
ARTIFACT_SHA = dict(ELF=None, PRG=None, LTO=None, D81=None)
ARTIFACT_PATH = dict(ELF='wplto/resident-island-seed.prg.elf',
                     PRG='wplto/resident-island-seed.prg',
                     LTO='wplto/resident-island-seed.prg.lto.o',
                     D81=f'{MEDIA_DIR}/{MEDIA_NAME}')
SEAL_SHA = None


def scratch_root():
    """Parent of every scratch directory these tools create themselves (tempfile.mkdtemp(dir=...)): below build/,
    never TMPDIR.  C255_SCRATCH_ROOT (a directory below build/) is a preparation switch."""
    path = (ROOT / os.environ.get('C255_SCRATCH_ROOT', 'build')).resolve()
    assert path == ROOT / 'build' or path.is_relative_to(ROOT / 'build'), 'scratch root must lie below build/'
    return path


def host_tools(pins=None):
    """The live host tools must be the pinned Fedora 45 binaries (resolved path, sha256).  Raises ValueError."""
    rows = []
    for path, digest in sorted((HOST_TOOLS if pins is None else pins).items()):
        real = Path(path).resolve()
        if not real.is_file():
            raise ValueError('missing host tool: ' + path)
        raw = real.read_bytes()
        got = hashlib.sha256(raw).hexdigest()
        if got != digest:
            raise ValueError('host tool drift: %s is %s, pinned %s' % (path, got, digest))
        rows.append(dict(path=path, resolved=str(real), bytes=len(raw), sha256=got))
    return rows


def host_equivalence():
    """The committed evidence that the pinned host tools reproduce the BASELINE artifacts byte for byte: the two
    public reproductions of 2.5.4 (Fedora 45).  Returns the list of problems (empty = holds)."""
    problems = []
    rows = {}
    for key, (rel, digest) in HOST_EQUIVALENCE.items():
        path = ROOT / rel
        if not path.is_file() or sha256_file(path) != digest:
            problems.append('host equivalence record is not the pinned file: ' + rel)
            return problems
        rows[key] = json.loads(path.read_text())
    policy, repro = rows['policy'], rows['reproductions']
    if policy.get('release') != '2.5.4' or {r['path']: r['sha256'] for r in policy['host_tools']} != HOST_TOOLS:
        problems.append('2.5.4 reproduction policy does not pin the 2.5.5 host tools')
    q = policy.get('host_qualification', {})
    if (q.get('final_host'), q.get('reproduction_host')) != (BASE_HOST, HOST) or \
            {r['path']: r['sha256'] for r in q.get('final_host_tools', [])} != BASE_HOST_TOOLS:
        problems.append('2.5.4 host qualification is not Fedora 44 (Final) / Fedora 45 (reproductions)')
    want = dict(ELF=BASE_ELF_SHA, PRG=BASE_PRG_SHA, LTO=BASE_LTO_SHA, D81=BASE_MEDIUM_SHA)
    if {k: v['sha256'] for k, v in policy['artifacts'].items()} != want:
        problems.append('2.5.4 reproduction policy names other artifacts than the baseline')
    if repro.get('status') != 'PASS' or len(repro.get('reproductions', [])) != 2:
        problems.append('2.5.4 reproductions record is not two PASS reproductions')
    else:
        for i, row in enumerate(repro['reproductions']):
            if {k: v['sha256'] for k, v in row['artifacts'].items()} != want or row.get('product_links') != 1:
                problems.append('2.5.4 reproduction %d is not byte-identical to the baseline' % (i + 1))
    return problems


def baseline_link_problems():
    """The two-directory 2.5.4 baseline: the halted link attempt keeps its four pinned records and never became a
    Seed; the continuation directory is the Seed and names the attempt; the native receipts are byte-identical in
    both; the Final is sealed.  Returns the list of problems (empty = holds).  Read-only."""
    problems = []
    link, seed, final = ROOT / BASE_LINK, ROOT / BASE, ROOT / BASE_FINAL
    for name, digest in BASE_LINK_RECORDS:
        if not (link / name).is_file() or sha256_file(link / name) != digest:
            problems.append('baseline link attempt record drift: ' + name)
    for name in ('complete.json', 'seed.json', 'media.json'):
        if (link / name).exists():
            problems.append('baseline link attempt carries ' + name + ' (it is not the Seed)')
    if (seed / 'halt.json').exists():
        problems.append('baseline Seed carries halt.json')
    for name in ('seed.json', 'complete.json'):
        if not (seed / name).is_file() or sha256_file(seed / name) != BASE_SEED_RECEIPT_SHA:
            problems.append('baseline Seed receipt drift: ' + name)
    for name in BASE_NATIVE_TWINS:
        a, b = link / 'native' / name, seed / 'native' / name
        if not (a.is_file() and b.is_file()) or a.read_bytes() != b.read_bytes():
            problems.append('baseline native receipt differs between the link attempt and the Seed: ' + name)
    if not (link / 'native/command-proof.json').is_file() or sha256_file(link / 'native/command-proof.json') != BASE_RECIPE_SHA:
        problems.append('baseline recipe drift')
    if not (final / 'seal.json').is_file() or sha256_file(final / 'seal.json') != BASE_SEAL_SHA:
        problems.append('baseline Final seal drift')
    if not (ROOT / BASE_PREFLIGHT / 'receipt.json').is_file() or sha256_file(ROOT / BASE_PREFLIGHT / 'receipt.json') != BASE_PREFLIGHT_RECEIPT_SHA:
        problems.append('baseline preflight receipt drift')
    if not problems:
        complete = json.loads((seed / 'complete.json').read_text())
        if complete.get('status') != 'PASS' or complete.get('product_links') != 1 or 'continues' not in complete:
            problems.append('baseline Seed is not the PASS continuation of one link')
        proof = json.loads((link / 'native/command-proof.json').read_text())['commands']
        if any((BASE + '/') in arg or arg.endswith(BASE) for command in proof for arg in command):
            problems.append('a frozen command names the continuation directory')
    emitter = ROOT / ENTRY_EMITTER
    if not emitter.is_file() or sha256_file(emitter) != ENTRY_EMITTER_SHA:
        problems.append('frozen host ABI helper snapshot drift')
    return problems


def qualified_run_problems():
    """P-AUTH / P-RUN: the authority is a commit that a GREEN sealed check-source run qualified.  Read-only."""
    problems = []
    if not AUTHORITY_PIN:
        return ['AUTHORITY_PIN not set (placeholder P-AUTH)']
    for run in SOURCE_QUALIFIED_RUNS:
        if not run:
            problems.append('SOURCE_QUALIFIED_RUNS not set (placeholder P-RUN)')
            continue
        path = ROOT / run / 'receipt.json'
        if not path.is_file():
            problems.append('qualifying sealed run has no receipt: ' + run)
            continue
        r = json.loads(path.read_text())
        if r.get('exit_code') != 0 or r.get('target') != 'make -k check-source':
            problems.append('qualifying sealed run is not a green `make -k check-source`: ' + run)
        if r.get('head_before') != AUTHORITY_PIN or r.get('head_after') != AUTHORITY_PIN:
            problems.append('qualifying sealed run did not run on the pinned authority: ' + run)
        if r.get('changed_files') or r.get('changed_sealed_artifacts') or r.get('changed_protected_files'):
            problems.append('qualifying sealed run changed files: ' + run)
    return problems


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
    assert seams is not None, ('product seam decision open (c255_config.PRODUCT_SEAMS)', key, lib)
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
    """Premise of the 2.5.5 native rule: src/ is identical at BASE_AUTHORITY and at `commit` (read-only)."""
    assert _git('diff', '--quiet', BASE_AUTHORITY, commit, '--', *NATIVE_UNCHANGED_ROOTS, check=False).returncode == 0, \
        'native source differs from 2.5.4 (BASE_AUTHORITY): the 2.5.5 native rule does not apply'
    return {root: _git('rev-parse', '--verify', f'{commit}:{root}').stdout.strip() for root in NATIVE_UNCHANGED_ROOTS}


def verify_authority():
    """Read-only git queries, run by the CLI BEFORE the write/process audit hook is installed."""
    global AUTHORITY_CHECK
    if DRY:
        return verify_dry()
    assert AUTHORITY_PIN, 'AUTHORITY_PIN not set (reviewer sets it after the green sealed run; dry mode: C255_DRY_WORKTREE=1)'
    assert re.fullmatch('[0-9a-f]{40}', AUTHORITY_PIN), 'AUTHORITY_PIN must be the full 40-digit commit hash'
    assert re.fullmatch('[0-9a-f]{8,40}', AUTHORITY), 'set C255_AUTHORITY (commit prefix, lower-case hex)'
    assert AUTHORITY_PIN.startswith(AUTHORITY), 'C255_AUTHORITY is not a prefix of the pinned authority'
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
        'authority does not descend from the 2.5.4 authority'
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
        'native source differs from 2.5.4 (BASE_AUTHORITY) in the working tree'
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
    # 1. The frozen baseline must still be exactly what the constants say, in the Seed (r1b) AND the Final r1;
    #    the link attempt r1 holds the same ELF / PRG / LTO object (r1b carries copies).
    for label, rel, want in BASE_ARTIFACTS:
        for where in (BASE, BASE_FINAL) + (() if label == 'medium' else (BASE_LINK,)):
            if not (ROOT / where / rel).is_file() or sha256_file(ROOT / where / rel) != want:
                problems.append(f'{label} drift: {where}/{rel}')
    problems += baseline_link_problems()
    # 1b. Host: the live host tools are the pinned Fedora 45 binaries, and the committed 2.5.4 reproductions show
    #     that exactly these tools give the baseline artifacts byte for byte.
    try:
        host_tools()
    except ValueError as error:
        problems.append(str(error))
    problems += host_equivalence()
    # 1c. The authority and the sealed run that qualified it (placeholders until the reviewer sets them).
    if not DRY:
        problems += qualified_run_problems()
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
        if recipe[73][0] != '/usr/bin/llvm-link' or recipe[74][:3] != ['/usr/bin/setarch', 'x86_64', '-R']:
            problems.append('baseline recipe does not use the pinned host tools at commands 73 / 74')
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
            problems.append('PRODUCT_SEAMS decision open (reviewer decision D-L2)')
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
           for b in (BASE, BASE_LINK, BASE_FINAL, BASE_PREFLIGHT)):
        problems.append('successor name inside a frozen 2.5.4 directory')
    # 5b. D-E3: the emitted ide image is pinned to the image the product-world E3 proof ran on.
    if CANDIDATE_BLOBS is not None and tuple(CANDIDATE_BLOBS['ide']) != tuple(E3_PROOF_IDE_BLOB):
        problems.append('ide image pin differs from the E3 proof image (re-run the product-world proof)')
    for tool in (E3_TOOL, E3_BASE_TOOL):
        if not (Path(__file__).resolve().parent / tool).is_file():
            problems.append('product-world E3 harness missing: ' + tool)
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
    assert DRY or AUTHORITY_PIN is None or all(SOURCE_QUALIFIED_RUNS), 'P-RUN: name the qualifying sealed run together with the authority'
    assert set(EXPECT_CHANGED) | set(EXPECT_EXACT) == set(KEYS) and not set(EXPECT_CHANGED) & set(EXPECT_EXACT)
    assert set(IMAGE_DELTA_WINDOW) == set(KEYS) and all(IMAGE_DELTA_WINDOW[k] == (0, 0) for k in EXPECT_EXACT)
    assert CANDIDATE_BLOBS is None or (set(CANDIDATE_BLOBS) == set(KEYS) and
                                       sum(v[1] for v in CANDIDATE_BLOBS.values()) == CANDIDATE_STATIC_CODE_BYTES)
    assert NATIVE_TEXT_CAP == 0 and not NATIVE_TEXT_EXPECTED_CHANGED and not any(NATIVE_METADATA_EXPECTED.values()), \
        '2.5.5 native rule: no growth, no changed function, no metadata delta'
    assert NATIVE_TEXT_IMMEDIATE_ALLOWED == ('main',) and BASE_TEXT_BYTES == 36899 and not NATIVE_SHAPE_ACCEPTED
    assert EXPECT_CHANGED == ('ide',) and IMAGE_DELTA_WINDOW['ide'][0] <= IMAGE_DELTA_WINDOW['ide'][1] < 0, \
        '2.5.5: only the ide image changes, and it gets smaller'
    assert CANDIDATE_BLOBS is None or CANDIDATE_BLOBS['ide'][1] - 15223 == IMAGE_DELTA_WINDOW['ide'][0]
    assert CANDIDATE_STATIC_CODE_BYTES is None or CANDIDATE_STATIC_CODE_BYTES - BASE_STATIC_CODE_BYTES == \
        sum(lo for lo, _hi in IMAGE_DELTA_WINDOW.values())
    assert not PACKAGES_REEMIT and not PACKAGE_BLOBS and not STDLIB_HEADER_MAY_CHANGE
    assert set(HOST_TOOLS) == set(BASE_HOST_TOOLS) and all(HOST_TOOLS[p] != BASE_HOST_TOOLS[p] for p in HOST_TOOLS)
    reject('Fedora 44 host pins on this host', lambda: host_tools(BASE_HOST_TOOLS))
    reject('host tool drift', lambda: host_tools({'/usr/bin/setarch': '0' * 64}))
    assert BASE.startswith(BASE_LINK) and BASE != BASE_LINK and BASE_NATIVE.startswith(BASE_LINK + '/'), 'two-directory baseline'
    assert not ENTRY_EMITTER.startswith('build/c2-lite/'), 'the host ABI helper must be a frozen snapshot'
    assert set(PACKAGES_REEMIT) <= set(PACKAGE_NAMES) and set(PACKAGE_SOURCES) == set(PACKAGE_SUITE) == set(PACKAGES_REEMIT)
    assert set(PACKAGE_RESIDENT) == set(PACKAGES_REEMIT) and not any('build/bytecode' in r for r in PACKAGE_RESIDENT.values())
    assert set(PACKAGE_ROUTED_LIB.values()) <= set(PACKAGES_REEMIT)
    assert all(lib in PACKAGE_SOURCES[name] for lib, name in PACKAGE_ROUTED_LIB.items()), 'package route names a foreign source'
    routed_lib()
    assert set(k for k, _ in PRODUCT_SEAMS) <= set(PROJECTIONS) and all(lib in PROJECTIONS[k].values() for k, lib in PRODUCT_SEAMS)
    assert CANDIDATE_BLOBS is None or tuple(CANDIDATE_BLOBS['ide']) == tuple(E3_PROOF_IDE_BLOB), \
        'ide image pin differs from the E3 proof image (D-E3)'
    assert all(v is not None for v in PRODUCT_SEAMS.values()), 'PRODUCT_SEAMS decision open'
    assert [s['action'] for s in PRODUCT_SEAMS[('ide', 'lib/ide-ui.lisp')]] == ['replace', 'replace'], 'D-L2 = two seams'
    assert [s['action'] for s in E3_PUBLICATION_SEAMS] == ['replace', 'replace'] and \
        not {s['product_new'] for s in E3_PUBLICATION_SEAMS} & {s['product_old'] for s in PRODUCT_SEAMS[('ide', 'lib/ide-ui.lisp')]}
    for seams in list(PRODUCT_SEAMS.values()):
        for seam in seams or ():
            assert seam['action'] in ('skip', 'replace')
            assert seam['action'] == 'skip' or (seam['product_old'] != seam['product_new'] and seam['product_old'])
    assert not any('card-254' in n or 'card-253' in n or 'o2-lite' in n for n in names), 'stale name of an earlier release'
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
        sys.exit('usage: c255_config.py selftest|check-seed|check-final')
