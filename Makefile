# lisp65 — Build (llvm-mos)
# make        -> build/lisp65-mega65.prg  (natives MEGA65-Target)
# make prelude -> build/lisp65-mega65-prelude.prg (eingebettete M1-Prelude)
# make mvp-vm-stdlib -> build/lisp65-mega65-vm-stdlib.prg (PRG + externes Bytecode-Stdlib-Blob)
# make mvp-vm-stdlib-core -> VM-Stdlib ohne residente IDE, mit Disk-Lib-Loader
# make mvp-vm-stdlib-hw-selftest -> sichtbares MEGA65-Selftest-PRG fuer volle Stdlib
# make mvp-vm-stdlib-known-open-diagnostic -> Diagnose-PRG fuer HW-Known-Open-Faelle
# make mvp-vm-stdlib-compile-repl -> M6-Referenz: VM-Stdlib + geraeteseitiger Compiler
# make mvp-vm-stdlib-crfit -> crfit-Referenz: Blob-Stdlib + Compiler-REPL, kein Produkt-Gate
# make mvp-vm-stdlib-s5-proof -> Source-on-Disk-Proof-PRG fuer scripts/xemu-s5-verify.py
# make mvp-vm-stdlib-einsuite -> P6c-Kandidat: Werkbank + lcc-Blob + lcc-install
# make mvp-vm-stdlib-einsuite-strip -> Opt-in: Ein-Suite ohne Treewalk, eval via lcc-run
# make mvp-vm-stdlib-einsuite-full -> M4-Full: Strip + Disk-load/save + Bulk-Render
# make mvp-vm-stdlib-einsuite-fasl -> B3-Opt-in: Strip + Disk + FASL compile-file
# make mvp-vm-stdlib-einsuite-core -> historische Dev-Core-Referenz: Strip + Disk + native FASL + load-lib
# make mvp-vm-stdlib-einsuite-core-string-arena -> Dev-Core + opt-in Packed-Byte-Strings
# make mvp-vm-stdlib-einsuite-core-arena-ide -> Arena-IDE: Dev-Core ohne FASL, mit Packed-Byte-Strings
# make workbench-candidate -> aktueller Workbench-Kandidat (Arena-IDE + compile-string)
# make workbench-gate -> automatisierbarer Workbench-Produktgate-Slice
# make workbench-persistence-gate -> IDE-Persistenz/Ship/Dry-Run-Gate
# make s5-source-d81 -> QUELL-D81 fuer S5 Source-on-Disk
# make mvp-vm-stdlib-footprint-report -> build/bytecode/mvp-vm-stdlib-footprint.txt
# make mvp-vm-stdlib-compile-repl-footprint-report -> M6-Referenz-Footprint
# make mvp-vm-stdlib-crfit-footprint-report -> crfit-Referenz-Footprint
# make mvp-vm-stdlib-einsuite-footprint-report -> P6c-Ein-Suite-Footprint
# make mvp-vm-stdlib-einsuite-strip-footprint-report -> Ein-Suite-Treewalk-Strip-Footprint
# make mvp-vm-stdlib-einsuite-full-footprint-report -> M4-Full-Footprint
# make mvp-vm-stdlib-einsuite-fasl-footprint-report -> B3-FASL-Opt-in-Footprint
# make mvp-vm-stdlib-einsuite-core-footprint-report -> Dev-Core-Footprint
# make mvp-vm-stdlib-einsuite-core-string-arena-footprint-report -> Dev-Core-Arena-Footprint
# make mvp-vm-stdlib-einsuite-core-arena-ide-footprint-report -> Arena-IDE-Footprint
# make workbench-candidate-footprint-report -> aktueller Workbench-Kandidat-Footprint
# make mvp-vm-stdlib-load-footprint-report -> F011/LOAD-Profil mit Bytecode-(load)
# make mvp-vm-stdlib-disklibs -> F011/LOAD + residenter Disk-Lib-Loader
# make bytecode-p0-disklib-d81 -> standalone Bytecode-Lib-Blob als D81
# make bytecode-p0-ide-lib-d81 -> IDE-Bytecode-Lib als D81
# make demo-suite-check -> Host-P0-Guard fuer lesbare Demo-Programme
# make demo-suite-d81 -> Demo-Quellen + FASL-Slots als MEGA65-D81
# make hw-demo-suite -> Demo-Suite auf echter MEGA65-HW kompilieren/laden/pruefen
# make hw-workbench-ux-smoke -> Workbench-UX per Etherload + JTAG-REPL pruefen
# make hw-workbench-bam-read-smoke -> Workbench-D81-BAM read-only auf echter HW pruefen
# make hw-workbench-bam-alloc-smoke -> M2-Wegwerf-D81-BAM-Allokation auf echter HW pruefen
# make hw-workbench-chain-write-smoke -> M3-Wegwerf-D81-Ketten-Write auf echter HW pruefen
# make hw-workbench-dir-write-smoke -> M4-Wegwerf-D81-Directory-Write auf echter HW pruefen
# make hw-workbench-save-new-smoke -> M5-Wegwerf-D81-Lisp-save-new auf echter HW pruefen
# make hw-workbench-save-new-scan-smoke -> M6-Wegwerf-D81-Lisp-save-new mit BAM-Scan pruefen
# make string-arena-probe -> opt-in Host-Gate fuer Packed-Byte-String-Arena
# make eval-bytecode-equivalence-check -> Host-Eval und P0-Bytecode muessen gleiche Werte liefern
# make equivalence-check -> Treewalk und Geraete-Compiler muessen gleiche Werte liefern
# make stdlib-embed-whatif -> optionale Stdlib-Suites gegen Produkt-Embed kalkulieren
# make ide-bytecode-cost-report -> statischer P0-Kosten-/Render-Kontrakt-Report fuer die IDE
# make run-mvp-vm-stdlib -> per etherload auf echte MEGA65-HW
# make hw-stress-full -> Full-Profil-Stresslauf per etherload auf echte MEGA65-HW
# make hw-stress-deep -> Deep-Dive-Stresslauf mit zehn Spezialtests
# make hw-stress-redeploy -> wiederholte Etherload-Deploys ohne Hard-Reset + JTAG-Readback
# make check  -> Host-/Bytecode-Oracle + native MEGA65-MVP-Build/Dry-Run
# make mvp-ship -> aktuelles MVP-Produkt: Workbench-PRG + Blob + IDE/Compile-Slot-D81
# make legacy-c64-check -> historische C64/GO64-Smokes (kein MVP-Gate)
# make interim-ship -> historischer Prelude-only-PRG+D81-Pfad
# make run    -> per etherload auf echte MEGA65-HW (Remote-Modus noetig)
# make clean

.DEFAULT_GOAL := all

include mk/toolchain.mk

VM_SRCS := src/vm.c
COMPILE_SRCS := src/compile.c
COMPILE_REPL_SRCS := src/compile_repl.c
SRCS    := $(filter-out $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS),$(wildcard src/*.c))
RUNTIME_SRCS := $(filter-out src/main.c,$(SRCS))
M65PRG  := build/lisp65-mega65.prg
C64PRG  := build/lisp65-c64.prg
M65PRELUDEPRG := build/lisp65-mega65-prelude.prg
M65VMSTDLIBPRG := build/lisp65-mega65-vm-stdlib.prg
M65VMSTDLIBCOREPRG := build/lisp65-mega65-vm-stdlib-core.prg
M65VMSTDLIBDISKLIBSPRG := build/lisp65-mega65-vm-stdlib-disklibs.prg
M65VMSTDLIBSELFTESTPRG := build/lisp65-mega65-vm-stdlib-hw-selftest.prg
M65VMSTDLIBDIAGPRG := build/lisp65-mega65-vm-stdlib-known-open-diagnostic.prg
M65VMSTDLIBCOMPILEPRG := build/lisp65-mega65-vm-stdlib-compile-repl.prg
M65VMSTDLIBCRFITPRG := build/lisp65-crfit.prg
M65VMSTDLIBS5PRG := build/lisp65-s5-proof.prg
M65VMSTDLIBEINSUITEPRG := build/lisp65-mega65-vm-stdlib-einsuite.prg
M65VMSTDLIBEINSUITESTRIPPRG := build/lisp65-mega65-vm-stdlib-einsuite-strip.prg
M65VMSTDLIBEINSUITEFULLPRG := build/lisp65-mega65-vm-stdlib-einsuite-full.prg
M65VMSTDLIBEINSUITEFASLPRG := build/lisp65-mega65-vm-stdlib-einsuite-fasl.prg
M65VMSTDLIBEINSUITECOREPRG := build/lisp65-mega65-vm-stdlib-einsuite-core.prg
M65VMSTDLIBEINSUITECOREEDMASCROLLPRG := build/lisp65-mega65-vm-stdlib-einsuite-core-edma-scroll.prg
M65VMSTDLIBEINSUITECORESTRINGARENAPRG := build/lisp65-mega65-vm-stdlib-einsuite-core-string-arena.prg
S5_SOURCE_D81 ?= build/s5/lisp65-s5-source.d81
S5_SOURCE_SUITE ?= $(BYTECODE_STDLIB_SUITE)
S5_SOURCE_CHUNK_DIR ?= build/s5/source-chunks
S5_SOURCE_BUNDLE ?= build/s5/stdlib-source.lisp
S5_SOURCE_PACKAGE_MANIFEST ?= build/s5/source-package-manifest.txt
S5_SOURCE_MANIFEST ?= build/s5/source-d81-manifest.txt
S5_SOURCE_CHUNK_MAX ?= 30000
C64PRELUDEPRG := build/lisp65-c64-prelude.prg
C64PRELUDETESTPRG := build/lisp65-c64-prelude-test.prg
C64PRELUDEGCTESTPRG := build/lisp65-c64-prelude-gc-test.prg
M65PRELUDEGCTESTPRG := build/lisp65-mega65-prelude-gc-test.prg
C64LOADSOURCETESTPRG := build/lisp65-c64-load-source-test.prg
C64STRINGTESTPRG := build/lisp65-c64-string-test.prg
C64STDLIBTESTPRG := build/lisp65-c64-stdlib-test.prg
C64FORMATTESTPRG := build/lisp65-c64-format-test.prg
C64CONTROLTESTPRG := build/lisp65-c64-control-test.prg
M65F011LOADTESTPRG := build/lisp65-mega65-f011-load-test.prg
M65F011LOADHWPRG := build/lisp65-mega65-f011-load-hw-visible.prg
M65F011STDLIBTESTPRG := build/lisp65-mega65-f011-stdlib-test.prg
M65F011STDLIBLAYERPRG := build/lisp65-mega65-f011-stdlib-layer-probe.prg
LEGACY_INTERIM_SHIP_DIR ?= build/legacy-interim-ship
M65F011SHIPPRG := $(LEGACY_INTERIM_SHIP_DIR)/lisp65-f011-interim.prg
M65F011SHIPD81 := $(LEGACY_INTERIM_SHIP_DIR)/lisp65-f011-interim.d81
M65F011SHIPMANIFEST := $(LEGACY_INTERIM_SHIP_DIR)/f011-manifest.txt
MVP_CANDIDATE_DIR ?= build/ship-candidate
MVP_VERIFIED_DIR ?= build/ship
MVP_VM_SHIP_DIR ?= $(MVP_CANDIDATE_DIR)
MVP_VM_SHIP_PRG ?= $(MVP_VM_SHIP_DIR)/lisp65-mvp-workbench.prg
MVP_VM_SHIP_BLOB ?= $(MVP_VM_SHIP_DIR)/lisp65-mvp-workbench.blob.bin
MVP_VM_SHIP_OVERLAYS ?= $(MVP_VM_SHIP_DIR)/lisp65-mvp-workbench.overlays.bin
MVP_VM_SHIP_D81 ?= $(MVP_VM_SHIP_DIR)/lisp65-mvp-workbench.d81
MVP_VM_SHIP_MANIFEST ?= $(MVP_VM_SHIP_DIR)/manifest.json
MVP_VM_SHIP_FOOTPRINT ?= $(MVP_VM_SHIP_DIR)/mvp-vm-stdlib-footprint.txt
MVP_VM_SHIP_D81_MANIFEST ?= $(MVP_VM_SHIP_DIR)/workbench-d81-manifest.txt
WORKBENCH_SHIP_D81 ?= $(MVP_VM_SHIP_D81)
WORKBENCH_SHIP_D81_MANIFEST ?= $(MVP_VM_SHIP_D81_MANIFEST)
export MVP_VM_SHIP_DIR MVP_VM_SHIP_PRG MVP_VM_SHIP_BLOB MVP_VM_SHIP_OVERLAYS MVP_VM_SHIP_D81
export MVP_VM_SHIP_MANIFEST MVP_VM_SHIP_FOOTPRINT MVP_VM_SHIP_D81_MANIFEST
WORKBENCH_D81_EXPECT_FREE_BLOCKS ?= 2782
WORKBENCH_D81_EXPECT_FILE_BLOCKS ?= 378
WORKBENCH_M2_TRACK ?= 45
WORKBENCH_M2_SECTOR ?= 8
WORKBENCH_M3_TRACK ?= 45
WORKBENCH_M3_FIRST_SECTOR ?= 8
WORKBENCH_M3_SECOND_SECTOR ?= 9
M3_CHAIN_SOURCE := tests/disk/m3-chain-source.lisp
M3_CHAIN_GEN := build/hw/m3-chain-source.h
WORKBENCH_M4_TRACK ?= 45
WORKBENCH_M4_FIRST_SECTOR ?= 8
WORKBENCH_M4_SECOND_SECTOR ?= 9
WORKBENCH_M4_DIR_TRACK ?= 40
WORKBENCH_M4_DIR_SECTOR ?= 4
WORKBENCH_M4_DIR_ENTRY ?= 2
WORKBENCH_M4_NAME ?= m4src
M4_DIR_SOURCE := tests/disk/m4-dir-source.lisp
M4_DIR_GEN := build/hw/m4-dir-source.h
WORKBENCH_M5_TRACK ?= 45
WORKBENCH_M5_FIRST_SECTOR ?= 26
WORKBENCH_M5_SECOND_SECTOR ?= 27
WORKBENCH_M5_DIR_TRACK ?= 40
WORKBENCH_M5_DIR_SECTOR ?= 4
WORKBENCH_M5_DIR_ENTRY ?= 3
WORKBENCH_M5_NAME ?= m5src
WORKBENCH_M5_ALLOC_NAME ?= m5alloc
WORKBENCH_M5_SELFTEST_D81 ?= build/hw/workbench-m5-selftest-before.d81
WORKBENCH_M6_FIRST_SECTOR ?= 27
WORKBENCH_M6_SECOND_SECTOR ?= 28
WORKBENCH_M6_NAME ?= m6src
WORKBENCH_M6_RESERVE_SECTOR ?= 26
WORKBENCH_M6_SELFTEST_D81 ?= build/hw/workbench-m6-selftest-before.d81
WORKBENCH_M7_NAME ?= m7src
WORKBENCH_M7_ALLOC_NAME ?= m7alloc
WORKBENCH_M7_SELFTEST_D81 ?= build/hw/workbench-m7-selftest-before.d81
M5_NEW_SOURCE := tests/disk/m5-new-source.lisp
M5_ALLOC_SOURCE := lib/m65-disk-alloc.lisp
M5_PAYLOAD_FORM := tests/disk/m5-new-payload-form.lisp
M5_PAYLOAD_GEN := build/hw/m5-new-payload-form.h
M7_ALLOC_SOURCE := lib/m65-disk-alloc-var.lisp
M7_VAR_SOURCE := tests/disk/m7-var-source.lisp
M7_PAYLOAD_FORM := tests/disk/m7-var-payload-form.lisp
M7_PAYLOAD_GEN := build/hw/m7-var-payload-form.h
M5_SAVE_NEW_SRCS := src/eval.c src/interrupt.c src/io.c src/mem.c src/printer.c src/reader.c src/screen.c src/symbol.c
M65D_ALLOC_LOAD_CHECK := build/m65-disk-alloc-load-check
M65HWACCESSPRG := build/lisp65-mega65-hw-access-smoke.prg
M65HWCOLORRAMPRG := build/lisp65-mega65-hw-color-ram-smoke.prg
M65HWEDMASCREENPRG := build/lisp65-mega65-hw-edma-screen-smoke.prg
M65HWBAMALLOCPRG := build/lisp65-mega65-hw-bam-alloc-smoke.prg
M65HWCHAINWRITEPRG := build/lisp65-mega65-hw-chain-write-smoke.prg
M65HWDIRWRITEPRG := build/lisp65-mega65-hw-dir-write-smoke.prg
M65HWSAVENEWPRG := build/lisp65-mega65-hw-save-new-smoke.prg
M65HWSAVENEWSCANPRG := build/lisp65-mega65-hw-save-new-scan-smoke.prg
M65HWSAVENEWVARPRG := build/lisp65-mega65-hw-save-new-var-smoke.prg
BYTECODE_VM_M65_OBJ := build/vm-mega65.o
BYTECODE_P0_VECTOR_JSON := tests/bytecode/p0-golden-vectors.json
BYTECODE_P0_C_VECTORS := build/bytecode-p0-vectors.h
BYTECODE_P0_NATIVE_COMPILE_VECTORS := build/bytecode-p0-native-compile-vectors.h
BYTECODE_P0_NATIVE_COMPILER_HOST := build/bytecode-p0-native-compiler-host
EQUIVALENCE_HOST := build/equivalence/equivalence-check
DIALECT_V1_SOURCE_ROOT := build/equivalence/frozen-v1-f6527d25/source
DIALECT_V1_SOURCE_MANIFEST := $(DIALECT_V1_SOURCE_ROOT)/export-manifest.json
DIALECT_V1_EQUIVALENCE_HOST := build/equivalence/frozen-v1-f6527d25/equivalence-check
DIALECT_V2_EQUIVALENCE_HOST := build/equivalence/dialect-v2-equivalence-check
DIALECT_V1_EQUIVALENCE_BUILD := build/equivalence/frozen-v1-f6527d25/build-receipt.json
DIALECT_V2_EQUIVALENCE_BUILD := build/equivalence/dialect-v2-build-receipt.json
DIALECT_V2_PRELUDE_FIXTURE := tests/bytecode/dialect-v2/prelude-control/cases.json
DIALECT_V2_LISTS_FIXTURE := tests/bytecode/dialect-v2/lists/cases.json
DIALECT_V2_STRINGS_FIXTURE := tests/bytecode/dialect-v2/strings/cases.json
DIALECT_V2_EVAL_APPLY_FUNCALL_FIXTURE := tests/bytecode/dialect-v2/eval-apply-funcall/cases.json
DIALECT_V2_CAPACITY_LEDGER := config/dialect-v2-capacity-ledger.json
DIALECT_V2_CAPACITY_REPORT := build/bytecode/dialect-v2/capacity-ledger.json
V2_CAPABILITY_CARRIER_CONTRACT := config/v2-capability-carrier-block.json
V2_CAPABILITY_CARRIER_FIXTURE := tests/bytecode/dialect-v2/capability-carrier/surface.json
V2_CAPABILITY_CARRIER_G5_CONTRACT := config/v2-capability-carrier-g5-candidate.json
V2_CAPABILITY_CARRIER_G5_DIR := build/cp5-g5-v2-bound
V2_CAPABILITY_CARRIER_G5_RUNTIME := $(V2_CAPABILITY_CARRIER_G5_DIR)/runtime-package
V2_CAPABILITY_CARRIER_G5_CANDIDATE := $(V2_CAPABILITY_CARRIER_G5_DIR)/candidate.json
V2_CAPABILITY_CARRIER_G5_PLAN := $(V2_CAPABILITY_CARRIER_G5_DIR)/hardware-plan.json
V2_CAPABILITY_CARRIER_G5_HW_PACKAGE := $(V2_CAPABILITY_CARRIER_G5_DIR)/workbench-hw-package
V2_CAPABILITY_CARRIER_G5_EVIDENCE := $(V2_CAPABILITY_CARRIER_G5_DIR)/evidence
V2_CAPABILITY_CARRIER_G5_D81 := $(V2_CAPABILITY_CARRIER_G5_DIR)/lisp65-v2-workbench.d81
V2_CAPABILITY_CARRIER_G5_PREFLIGHT_KEY := $(shell sha256sum config/v2-capability-carrier-g5-candidate.json tools/host-lisp/v2_capability_carrier_g5.py tools/host-lisp/v2_g5_domain_verifiers.py Makefile | sha256sum | cut -c1-16)
V2_CAPABILITY_CARRIER_G5_PREFLIGHT := $(V2_CAPABILITY_CARRIER_G5_DIR)/preflight/preflight-$(V2_CAPABILITY_CARRIER_G5_PREFLIGHT_KEY).json
# The explicit v2 proof target and the canonical product target must resolve to
# one artifact set. A second output path changes the ABI-contract build id and
# therefore creates a different product SHA despite identical code/layout.
V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR := build/products/workbench/overlay-stack-guard
V2_CAPABILITY_CARRIER_G5_V2_DEFINES := -DLISP65_DIALECT_V2 -DLISP65_V2_CARRIER_CUT -DLISP65_VM_NATIVE_APPLY -DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS -DLISP65_V2_SERVICE_REGISTRY_CLOSED -DLISP65_V2_WORKBENCH_SERVICES -DLISP65_V2_TREE_PRIMITIVE_VIEW
V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV = \
	MVP_VM_SHIP_PRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.prg' \
	MVP_VM_SHIP_BLOB='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.blob.bin' \
	MVP_VM_SHIP_OVERLAYS='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.overlays.bin' \
	MVP_VM_SHIP_D81='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.d81'
R5_GLOBAL_G5_DIR := build/r5-global-g5
R5_GLOBAL_G5_PRODUCT := $(R5_GLOBAL_G5_DIR)/product
R5_GLOBAL_G5_MATERIALIZATION := $(R5_GLOBAL_G5_PRODUCT)/materialization.json
R5_GLOBAL_G5_RUNTIME := $(R5_GLOBAL_G5_DIR)/runtime-package
R5_GLOBAL_G5_TEST_D81 := $(R5_GLOBAL_G5_DIR)/workbench-test.d81
R5_GLOBAL_G5_TEST_D81_MANIFEST := $(R5_GLOBAL_G5_DIR)/workbench-test-d81-manifest.json
R5_GLOBAL_G5_CLOSURE := $(R5_GLOBAL_G5_DIR)/test-closure.json
R5_GLOBAL_G5_CANDIDATE := $(R5_GLOBAL_G5_DIR)/candidate.json
R5_GLOBAL_G5_HW_PACKAGE := $(R5_GLOBAL_G5_DIR)/hw-package
R5_GLOBAL_G5_NEGATIVE_PROOF := $(R5_GLOBAL_G5_DIR)/workbench-verifier-negative-proof.json
R5_GLOBAL_G5_PREFLIGHT_BUILD := $(R5_GLOBAL_G5_DIR)/static-preflight-receipt.json
R5_GLOBAL_G5_PREFLIGHT_RECEIPT := tests/bytecode/dialect-v2/evidence/r5/global-g5-static-preflight-receipt.json
R5_GLOBAL_G5_RUN_ID := r5-run-20260715-13
R5_GLOBAL_G5_EVIDENCE := $(R5_GLOBAL_G5_DIR)/evidence/$(R5_GLOBAL_G5_RUN_ID)
R5_GLOBAL_G5_BOOT_WAIT_SEC := 8
R5_GLOBAL_G5_PRODUCT_SET := c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165
R5_GLOBAL_G5_CLOSURE_SET = $(shell python3 -c 'import json; print(json.load(open("$(R5_GLOBAL_G5_CLOSURE)"))["closure_set_sha256"])' 2>/dev/null)
R5_GLOBAL_G5_PRODUCT_PREFIX := $(R5_GLOBAL_G5_PRODUCT)/build/products/workbench/overlay-stack-guard
R6_SHIP_DIR := build/r6/ship
R6_SHIP_SECOND_DIR := build/r6/ship-second
R6_SHIP_SOURCE_COMMIT ?= $(shell git rev-parse HEAD)
R6_SHIP_PACKED_ON ?= $(shell git show -s --format=%cs $(R6_SHIP_SOURCE_COMMIT) 2>/dev/null)
R6_SHIP_RECEIPT := tests/bytecode/dialect-v2/evidence/post-release/r6-ship-101-packer-receipt.json
R6_G6_SOURCE_COMMIT ?= $(shell git rev-parse HEAD)
R6_G6_PREFLIGHT_RECEIPT := tests/bytecode/dialect-v2/evidence/post-release/r6-g6-101-static-preflight-receipt.json
R6_G6_PROFILE_RECEIPT := tests/bytecode/dialect-v2/evidence/post-release/r6-g6-101-profile-applicability-receipt.json
R6_G6_RUN_DIR := build/r6/g6/run-20260715-02-preflight-212f957
R6_G6_TOP_RECEIPT := $(R6_G6_RUN_DIR)/g6-hardware-receipt.json
R6_G6_SEAL_SOURCE_COMMIT ?= $(shell git rev-parse HEAD)
R6_G6_SEALED_ON ?= $(shell git show -s --format=%cs $(R6_G6_SEAL_SOURCE_COMMIT) 2>/dev/null)
R6_G6_SEAL_ID ?= r6-g6-hardware-acceptance-$(shell git rev-parse --short=7 $(R6_G6_SEAL_SOURCE_COMMIT) 2>/dev/null)
R6_G6_SEAL_ARCHIVE ?= tests/bytecode/dialect-v2/evidence/promotions/$(R6_G6_SEAL_ID).tar.gz
R7_MANIFEST_SOURCE_COMMIT ?= $(shell git rev-parse HEAD)
R7_MANIFEST_PREVIEW ?= build/r7/public-manifest-prerequisites.json
R7_MANIFEST_RECEIPT ?= build/r7/public-manifest-prerequisites-receipt.json
R7_RELEASE_BUNDLE := releases/lisp65-1.0.1.tar.gz
R7_RELEASE_RECEIPT := releases/lisp65-1.0.1-receipt.json
R5_GLOBAL_G5_WORKBENCH_ENV = \
	BOOT_WAIT_SEC='$(R5_GLOBAL_G5_BOOT_WAIT_SEC)' \
	MVP_VM_SHIP_PRG='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.prg' \
	MVP_VM_SHIP_BLOB='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.blob.bin' \
	MVP_VM_SHIP_OVERLAYS='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.overlays.bin' \
	MVP_VM_SHIP_D81='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.d81'
V2_NATIVE_FUNCTION_REGISTRY := config/v2-native-function-registry.json
V2_NATIVE_FUNCTION_FIXTURE := tests/bytecode/dialect-v2/native-function-routes/cases.generated.json
V2_NATIVE_FUNCTION_RECEIPT := tests/bytecode/dialect-v2/evidence/capability-carrier/native-function-route-matrix.json
V2_NATIVE_FUNCTION_VIEWS := tools/host-lisp/v2_native_function_views_generated.py
V2_NATIVE_FUNCTION_PARITY := tests/bytecode/dialect-v2/evidence/capability-carrier/primitive-view-cross-parity.json
V2_NATIVE_FUNCTION_HOST := build/equivalence/dialect-v2-native-function-check
V2_LCC_COMPILE_ERROR_RECEIPT := tests/bytecode/dialect-v2/evidence/capability-carrier/invalid-parameter-list-verdict.json
V2_WORKBENCH_SYMBOL_DIFF_POLICY := config/v2-workbench-symbol-diff-policy.json
V2_WORKBENCH_SYMBOL_DIFF_REPORT := tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-symbol-diff-report.json
V2_WORKBENCH_SYMBOL_DIFF_LIVE_REPORT := build/bytecode/dialect-v2/workbench-symbol-diff-report.json
V2_WORKBENCH_DERES_AUDIT := config/v2-workbench-de-residentization-audit.json
V2_WORKBENCH_ATTR_BASELINE_ELF ?=
V2_WORKBENCH_ATTR_CANDIDATE_ELF ?=
DIALECT_EQUIVALENCE_HEADERS := $(wildcard src/*.h)
DIALECT_EQUIVALENCE_SOURCE_NAMES := eval.c compile.c compile_repl.c lcc_install_overlay.c vm.c mem.c symbol.c reader.c printer.c io.c interrupt.c screen.c
BYTECODE_STDLIB_SUITE := tests/bytecode/stdlib/p0-stdlib-subset.json
BYTECODE_STDLIB_CORE_SUITE := tests/bytecode/stdlib/p0-stdlib-core-subset.json
BYTECODE_STDLIB_LOAD_SUITE := tests/bytecode/stdlib/p0-stdlib-load-subset.json
BYTECODE_STDLIB_DISKLIBS_SUITE := tests/bytecode/stdlib/p0-stdlib-disklibs-subset.json
BYTECODE_STDLIB_EINSUITE_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-subset.json
BYTECODE_STDLIB_EINSUITE_FULL_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-full-subset.json
BYTECODE_STDLIB_EINSUITE_FASL_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-fasl-subset.json
BYTECODE_STDLIB_EINSUITE_CORE_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json
BYTECODE_DISKLIB_SUITE := tests/bytecode/libs/p0-testlib.json
BYTECODE_IDE_FULL_LIB_SUITE := tests/bytecode/libs/p0-ide-sequential-full-lib.json
BYTECODE_IDE_BASELINE_LIB_SUITE := tests/bytecode/libs/p0-ide-full-lib.json
BYTECODE_IDE_LIB_SUITE := tests/bytecode/libs/p0-ide-core-lib.json
BYTECODE_IDE_EXTRA_LIB_SUITE := tests/bytecode/libs/p0-ide-extra-lib.json
BYTECODE_M65D_LIB_SUITE := tests/bytecode/libs/p0-m65d-lib.json
BYTECODE_FIXED_SUITE := tests/bytecode/stdlib/p0-fixed-point-subset.json
BYTECODE_STRING_POLISH_SUITE := tests/bytecode/stdlib/p0-string-polish-subset.json
BYTECODE_EQUIV_SUITES := tests/bytecode/equivalence/p0-eval-bytecode.json
BYTECODE_STDLIB_PREFIX := build/bytecode/stdlib-p0
BYTECODE_STDLIB_HEADER := $(BYTECODE_STDLIB_PREFIX).h
BYTECODE_STDLIB_C := $(BYTECODE_STDLIB_PREFIX).c
BYTECODE_STDLIB_CODE_BLOB := $(BYTECODE_STDLIB_PREFIX).blob.bin
BYTECODE_STDLIB_EXT_BLOB := $(BYTECODE_STDLIB_PREFIX).ext.bin
BYTECODE_STDLIB_BLOB ?= $(BYTECODE_STDLIB_EXT_BLOB)
STRING_ARENA_STDLIB_PREFIX := build/bytecode/string-arena-stdlib-p0
STRING_ARENA_STDLIB_C := $(STRING_ARENA_STDLIB_PREFIX).c
STRING_ARENA_PROBE_BASELINE := build/string-arena-probe-baseline
STRING_ARENA_PROBE_ARENA := build/string-arena-probe-arena
BYTECODE_DISKLIB_PREFIX := build/bytecode/libs/testlib
BYTECODE_DISKLIB_EXT_BLOB := $(BYTECODE_DISKLIB_PREFIX).ext.bin
BYTECODE_DISKLIB_D81 ?= build/bytecode/libs/testlib.d81
BYTECODE_DISKLIB_D81_MANIFEST ?= build/bytecode/libs/testlib-d81-manifest.txt
L65M_CONTRACT_FIXTURE := tests/bytecode/formats/p0-disk-lib-v1.json
L65M_CONTRACT_HEADER := build/l65m-contract-cases.h
L65M_NATIVE_LOADER_HOST := build/l65m-native-loader-host
L65M_V2_PRODUCT_HEADER := build/l65m-v2-product-cases.h
L65M_V2_PRODUCT_HOST := build/l65m-v2-product-host
FASL_EMIT_CHECK_HOST := build/equivalence/fasl-emit-check
FASL_EMIT_CHECK_ARTIFACT := build/equivalence/fasl-test.bin
BYTECODE_IDE_LIB_PREFIX := build/bytecode/libs/ide
BYTECODE_IDE_FULL_LIB_PREFIX := build/bytecode/libs/ide-full
BYTECODE_IDE_EXTRA_LIB_PREFIX := build/bytecode/libs/idex
BYTECODE_M65D_LIB_PREFIX := build/bytecode/libs/m65d
BYTECODE_FORMAT_LIB_SUITE := tests/bytecode/libs/p0-format-lib.json
BYTECODE_FIXED_LIB_SUITE := tests/bytecode/libs/p0-fixed-lib.json
BYTECODE_STRINGS_EXTRA_LIB_SUITE := tests/bytecode/libs/p0-strings-extra-lib.json
BYTECODE_PLACE_LIB_SUITE := tests/bytecode/libs/p0-place-lib.json
BYTECODE_IDE_LIB_EXT_BLOB := $(BYTECODE_IDE_LIB_PREFIX).ext.bin
BYTECODE_IDE_EXTRA_LIB_EXT_BLOB := $(BYTECODE_IDE_EXTRA_LIB_PREFIX).ext.bin
BYTECODE_M65D_LIB_EXT_BLOB := $(BYTECODE_M65D_LIB_PREFIX).ext.bin
BYTECODE_IDE_LIB_D81 ?= build/bytecode/libs/ide.d81
BYTECODE_IDE_LIB_D81_MANIFEST ?= build/bytecode/libs/ide-d81-manifest.txt
BYTECODE_FORMAT_LIB_PREFIX := build/bytecode/libs/fmt
BYTECODE_FORMAT_LIB_EXT_BLOB := $(BYTECODE_FORMAT_LIB_PREFIX).ext.bin
BYTECODE_FORMAT_LIB_D81 ?= build/bytecode/libs/fmt.d81
BYTECODE_FORMAT_LIB_D81_MANIFEST ?= build/bytecode/libs/fmt-d81-manifest.txt
BYTECODE_FIXED_LIB_PREFIX := build/bytecode/libs/fixed
BYTECODE_FIXED_LIB_EXT_BLOB := $(BYTECODE_FIXED_LIB_PREFIX).ext.bin
BYTECODE_FIXED_LIB_D81 ?= build/bytecode/libs/fixed.d81
BYTECODE_FIXED_LIB_D81_MANIFEST ?= build/bytecode/libs/fixed-d81-manifest.txt
BYTECODE_STRINGS_EXTRA_LIB_PREFIX := build/bytecode/libs/strx
BYTECODE_STRINGS_EXTRA_LIB_EXT_BLOB := $(BYTECODE_STRINGS_EXTRA_LIB_PREFIX).ext.bin
BYTECODE_STRINGS_EXTRA_LIB_D81 ?= build/bytecode/libs/strx.d81
BYTECODE_STRINGS_EXTRA_LIB_D81_MANIFEST ?= build/bytecode/libs/strx-d81-manifest.txt
BYTECODE_PLACE_LIB_PREFIX := build/bytecode/libs/place
BYTECODE_PLACE_LIB_EXT_BLOB := $(BYTECODE_PLACE_LIB_PREFIX).ext.bin
BYTECODE_PLACE_LIB_D81 ?= build/bytecode/libs/place.d81
BYTECODE_PLACE_LIB_D81_MANIFEST ?= build/bytecode/libs/place-d81-manifest.txt
BYTECODE_PILOT_LIB_D81 ?= build/bytecode/libs/pilot-libs.d81
BYTECODE_PILOT_LIB_D81_MANIFEST ?= build/bytecode/libs/pilot-libs-d81-manifest.txt
DEMO_SUITE ?= tests/bytecode/demos/p0-demo-suite.json
DEMO_SUITE_D81 ?= build/demos/lisp65-demo-suite.d81
DEMO_SUITE_MANIFEST ?= build/demos/demo-suite-manifest.txt
DEMO_SUITE_FASL_SLOT_BYTES ?= 8192
IDE_BYTECODE_COST_REPORT ?= build/bytecode/ide-bytecode-costs.txt
IDE_RENDER_CALLGRAPH_REPORT ?= build/bytecode/ide-render-callgraph.txt
IDE_BYTECODE_DYNAMIC_REPORT ?= build/bytecode/ide-bytecode-dynamic.txt
WORKBENCH_SYMFN_DYNAMIC_REPORT ?= build/bytecode/workbench-symfn-dynamic.txt
# Budgets = Fusion+Fastpath-Stand (Codex-Eichung aus 2e801f5); nach dem Wiedereinlanden
# von 3e93673/521afb9 (2026-07-03) wieder scharf. Historie: Prae-Fusion lag bei 101895
# total (-62% durch Fusion) — Zwischenwerte siehe docs/collaboration.md (REVERT-Sektion).
# 2026-07-06 Delta-Render (Lane K): +12-15 Ops je Step fuer den Dirty-Hint
# (%ide-hint!-Global + cons) — bezahlt auf dem GERAET ~130->~7 gemalte Zeichen je
# Taste (der Host-Trace modelliert Bulk-Screen und sieht die Ersparnis nicht).
# Budgets (Ist nach Hint-MERGE, Koaleszenz-Artefakt-Fix): self-insert 400 (382),
# repeat-10 3400 (3204), delete-cached 280 (261), navigation-8 2200 (2110),
# delete-backward 660 (651), type-render-5 12400 (12138). 2026-07-09 nach
# direktem Buffer-Zyklus + delete-forward: navigation-8 2350,
# delete-forward 573. Statusline-Zeilennummer nach Accessor-Reclaim: type-render-5 12813.
IDE_BYTECODE_DYNAMIC_BUDGET_ARGS ?= \
	--max-total-instructions 71000 \
	--max-scenario-instructions ide-step-self-insert=420 \
	--max-scenario-instructions ide-render-cold-short=5400 \
	--max-scenario-instructions ide-render-warm-after-insert=2900 \
	--max-scenario-instructions ide-step-long-line-insert=940 \
	--max-scenario-instructions ide-repeat-self-insert-10=3400 \
	--max-scenario-instructions ide-type-render-5=13000 \
	--max-scenario-instructions ide-step-delete-backward=700 \
	--max-scenario-instructions ide-step-delete-forward=600 \
	--max-scenario-instructions ide-step-delete-cached=301 \
	--max-scenario-instructions ide-step-navigation-8=2500 \
	--max-scenario-instructions ide-render-cold-25-lines=41000 \
	--max-scenario-instructions ide-dirty-scan-25-lines=1410
# Host-Trace fuer den Workbench-Pin mit LISP65_SYMFN_EXT: jeder Bytecode CALL/TAILCALL
# liest symfn via DMA auf dem Geraet. Die Budgets modellieren nicht die Zyklen, halten aber
# die dynamische Lookup-Exposure fuer Editor- und Compiler-Hotpaths sichtbar.
WORKBENCH_SYMFN_DYNAMIC_BUDGET_ARGS ?= \
	--max-total-instructions 130000 \
	--max-total-symfn-resolutions 9000 \
	--max-scenario-instructions ide-step-self-insert=420 \
	--max-scenario-instructions ide-render-cold-short=40500 \
	--max-scenario-instructions ide-render-warm-after-insert=5500 \
	--max-scenario-instructions ide-step-long-line-insert=950 \
	--max-scenario-instructions ide-repeat-self-insert-10=3450 \
	--max-scenario-instructions ide-type-render-5=26900 \
	--max-scenario-instructions ide-step-delete-backward=720 \
	--max-scenario-instructions ide-step-delete-forward=600 \
	--max-scenario-instructions ide-step-delete-cached=301 \
	--max-scenario-instructions ide-step-navigation-8=2500 \
	--max-scenario-instructions ide-render-cold-25-lines=42000 \
	--max-scenario-instructions ide-dirty-scan-25-lines=1450 \
	--max-scenario-instructions lcc-compile-small-defun=1100 \
	--max-scenario-instructions lcc-compile-branch-defun=2850 \
	--max-scenario-instructions lcc-compile-closure-defun=2200 \
	--max-scenario-symfn-resolutions ide-step-self-insert=35 \
	--max-scenario-symfn-resolutions ide-render-cold-short=2600 \
	--max-scenario-symfn-resolutions ide-render-warm-after-insert=450 \
	--max-scenario-symfn-resolutions ide-step-long-line-insert=100 \
	--max-scenario-symfn-resolutions ide-repeat-self-insert-10=270 \
	--max-scenario-symfn-resolutions ide-type-render-5=2200 \
	--max-scenario-symfn-resolutions ide-step-delete-backward=70 \
	--max-scenario-symfn-resolutions ide-step-delete-forward=60 \
	--max-scenario-symfn-resolutions ide-step-delete-cached=20 \
	--max-scenario-symfn-resolutions ide-step-navigation-8=200 \
	--max-scenario-symfn-resolutions ide-render-cold-25-lines=2750 \
	--max-scenario-symfn-resolutions ide-dirty-scan-25-lines=60 \
	--max-scenario-symfn-resolutions lcc-compile-small-defun=110 \
	--max-scenario-symfn-resolutions lcc-compile-branch-defun=260 \
	--max-scenario-symfn-resolutions lcc-compile-closure-defun=215
BYTECODE_KNOWN_OPEN_DIAG_SUITE := tests/bytecode/runtime/p0-known-open-diagnostic-stdlib.json
BYTECODE_KNOWN_OPEN_DIAG_PREFIX := build/bytecode/known-open-diagnostic/stdlib-p0
BYTECODE_KNOWN_OPEN_DIAG_HEADER := $(BYTECODE_KNOWN_OPEN_DIAG_PREFIX).h
BYTECODE_KNOWN_OPEN_DIAG_C := $(BYTECODE_KNOWN_OPEN_DIAG_PREFIX).c
BYTECODE_KNOWN_OPEN_DIAG_BLOB := $(BYTECODE_KNOWN_OPEN_DIAG_PREFIX).blob.bin
MVP_VM_STDLIB_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-footprint.txt
MVP_VM_STDLIB_COMPILE_REPL_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-compile-repl-footprint.txt
MVP_VM_STDLIB_CRFIT_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-crfit-footprint.txt
MVP_VM_STDLIB_EINSUITE_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-footprint.txt
MVP_VM_STDLIB_EINSUITE_STRIP_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-strip-footprint.txt
MVP_VM_STDLIB_EINSUITE_FULL_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-full-footprint.txt
MVP_VM_STDLIB_EINSUITE_FASL_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-fasl-footprint.txt
MVP_VM_STDLIB_EINSUITE_CORE_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-core-footprint.txt
MVP_VM_STDLIB_EINSUITE_CORE_EDMA_SCROLL_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-core-edma-scroll-footprint.txt
MVP_VM_STDLIB_EINSUITE_CORE_STRING_ARENA_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-core-string-arena-footprint.txt
MVP_VM_STDLIB_LOAD_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-load-footprint.txt
SCREEN_EDMA_SCROLL_FOOTPRINT_DELTA_REPORT ?= build/bytecode/screen-edma-scroll-footprint-delta.txt
MVP_VM_STDLIB_BOOT_BUDGET_REPORT ?= build/bytecode/mvp-vm-stdlib-boot-budget.txt
MVP_VM_STDLIB_RUNTIME_BUDGET_REPORT ?= build/bytecode/mvp-vm-stdlib-runtime-budget.txt
BANK0_RECLAIM_REPORT ?= build/bytecode/bank0-reclaim-report.txt
VM_SMOKE_HOST := build/vm-smoke-host
VM_SMOKE_V2_HOST := build/vm-smoke-v2-host
GC_SMOKE_HOST := build/gc-smoke-host
COMPILE_SMOKE_HOST := build/compile-smoke-host
COMPILE_RUN_HOST := build/compile-run-host
REPL_SESSION_HOST := build/repl-session-host
LCC_INSTALL_DEVICE_SMOKE_HOST := build/lcc-install-device-smoke-host
LCC_INSTALL_OVERLAY_SMOKE_HOST := build/lcc-install-overlay-smoke-host
VM_BOOT_FASTPATH_SMOKE_HOST := build/vm-boot-fastpath-smoke-host
ERROR_STATE_SMOKE_HOST := build/error-state-smoke-host
ERROR_STATE_NUMERIC_SMOKE_HOST := build/error-state-numeric-smoke-host
PRELUDE_COMPILE_CHECK_HOST := build/prelude-compile-check-host
PRELUDE_LOAD_RUN_HOST := build/prelude-load-run-host
OUTPUT_SMOKE_HOST := build/output-smoke-host
EVAL_PRIMS_SMOKE_HOST := build/eval-prims-smoke-host
READER_CONFORMANCE_HOST := build/reader-conformance-host
READER_CONFORMANCE_ARENA_HOST := build/reader-conformance-arena-host
READER_ROOT_GUARD_HOST := build/reader-root-guard-host
SAVE_SEMANTICS_SLOTS ?= loadall l00 stdlib
F011_DEFD81_SDIMG ?= build/f011/lisp65-f011-defd81-sd.img
STDLIB_D81 ?= $(LEGACY_INTERIM_SHIP_DIR)/lisp65-stdlib.d81
STDLIB_CHUNK_DIR ?= $(LEGACY_INTERIM_SHIP_DIR)/stdlib-chunks
STDLIB_CHUNK_MANIFEST := $(STDLIB_CHUNK_DIR)/manifest.txt
STDLIB_MANIFEST ?= $(LEGACY_INTERIM_SHIP_DIR)/stdlib-d81-manifest.txt
STDLIB_LOAD_COMMANDS ?= $(LEGACY_INTERIM_SHIP_DIR)/load-stdlib-commands.txt
F011_STDLIB_SDIMG ?= build/f011/lisp65-stdlib-defd81-sd.img
F011_AUTOLOAD_SDIMG ?= build/f011/lisp65-f011-autoload-sd.img
F011_STDLIB_AUTOLOAD_SDIMG ?= build/f011/lisp65-stdlib-autoload-sd.img
F011_STDLIB_LAYER_PROBE_SDIMG ?= build/f011/lisp65-stdlib-layer-probe-sd.img
F011_STDLIB_LAYER_PROBE_D81 ?= build/f011/lisp65-stdlib-layer-probe.d81
F011_STDLIB_LAYER_PROBE_DUMP ?= build/f011-stdlib-layer-probe-dump.bin
PRELUDE_LISP ?= lib/prelude-m1.lisp
PRELUDE_GEN := src/prelude_gen.h
LOAD_SMOKE_LISP := scripts/load-smoke-lib.lisp
LOAD_SMOKE_GEN := src/load_smoke_gen.h
STDLIB_STRINGS_LISP := lib/stdlib-strings.lisp
STDLIB_STRINGS_GEN := src/stdlib_strings_gen.h
STDLIB_SEQUENCES_LISP := lib/stdlib-sequences.lisp
STDLIB_SEQUENCES_GEN := src/stdlib_sequences_gen.h
STDLIB_MATH_LISP := lib/stdlib-math.lisp
STDLIB_MATH_GEN := src/stdlib_math_gen.h
STDLIB_PLISTS_LISP := lib/stdlib-plists.lisp
STDLIB_PLISTS_GEN := src/stdlib_plists_gen.h
STDLIB_FORMAT_LISP := lib/stdlib-format.lisp
STDLIB_FORMAT_GEN := src/stdlib_format_gen.h
STDLIB_CONTROL_LISP := lib/stdlib-control.lisp
STDLIB_CONTROL_GEN := src/stdlib_control_gen.h
LCC_LISP := lib/lcc.lisp
LCC_GEN := build/lcc_gen.h
PRELUDE_GC_HEAP ?= 1280
PRELUDE_GC_EXTRA_CFLAGS ?=
M65PRELUDE_GC_HEAP ?= 320
M65PRELUDE_GC_EXTRA_CFLAGS ?=
C64STDLIB_HEAP ?= 1560
C64STDLIB_EXTRA_CFLAGS ?= -DMAX_SYM=180 -DNAMEPOOL=1200
C64STRING_HEAP ?= 1600
C64STRING_EXTRA_CFLAGS ?= -DMAX_SYM=180 -DNAMEPOOL=1200
C64FORMAT_HEAP ?= 1500
C64FORMAT_EXTRA_CFLAGS ?= -DMAX_SYM=180 -DNAMEPOOL=1200
C64CONTROL_HEAP ?= 1500
C64CONTROL_EXTRA_CFLAGS ?= -DMAX_SYM=180 -DNAMEPOOL=1200
M65F011_REPL_HEAP ?= 1150
M65F011_CFLAGS ?= -Oz -Wall
M65F011_SMOKE_HEAP ?= 128
M65F011_SMOKE_IO_BUF ?= 512
M65F011_STDLIB_SMOKE_HEAP ?= 128
M65F011_STDLIB_SMOKE_IO_BUF ?= 512
M65F011_STDLIB_SMOKE_EXTRA_CFLAGS ?=
M65F011_STDLIB_LAYER_PROBE_HEAP ?= 128
M65F011_STDLIB_LAYER_PROBE_EXTRA_CFLAGS ?=
M65F011_LOAD_EXTRA_CFLAGS ?= -DMAX_SYM=560 -DNAMEPOOL=8192 -DGC_ROOTS=136 -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_MARK_BITMAP
M65VMSTDLIB_CFLAGS ?= -Oz -Wall
# Kein Boot-Overlay: auch ein CODE-Overlay hinter .noinit landet als PRG-File-Inhalt
# ueber $C000 (etherload-Landmine, 2x bewiesen am 2026-07-02). Boot-Code-Auslagerung
# braeuchte einen Loader-Mechanismus jenseits des flachen PRG — notiert als T/K-Thema.
M65VMSTDLIB_LDFLAGS ?=
# HEAP 976 (Claude/Lane K, 2026-07-02): moeglich, weil die Boot-Metadaten jetzt per
# LISP65_STDLIB_EXT_METADATA aus dem L65M-Trailer im erw. RAM gelesen werden — das PRG
# traegt weder Overlay-Sektion noch Embed-/littab-Tabellen. Die $C000-Grenze (etherload-
# Load-Invariante, s. u.) gilt weiter fuers PRG-FILE und wird im Footprint-Report gegated;
# Laufzeit-NOBITS (.bss/Heap/Stack) ueber $C000 ist unproblematisch.
# 976 -> 896 -> 544 (Claude, 2026-07-02): Screen-Treiber (~550 B) und die 9 IDE-
# Primitive (~1,8 KB: screen-size/-clear/-put-char, read-key/poll-key, symbol-count/
# symbol-max/symbol-name, function-kind — apply_prim waechst um 1,3 KB, ehrlicher
# 6502-Codegen, keine LTO-Klippe) zahlen aus dem Hot-Heap. Mit EXT bleibt der
# Gesamtheap gross (544 hot + 4096 ext = 4640 Zellen); hot ist nur Geschwindigkeit.
# Groesster kuenftiger Hebel: vm_run ist 10 KB .text (Lane-T-Thema).
M65VMSTDLIB_HEAP ?= 60
# 1450 statt 1200 (2026-07-03): xemu-vermessen braucht der IDE-Tastenpfad (self-insert +
# RETURN-Split + Render) 1338 B C-Stack — NACH der vm_run-Stack-Diaet (vorher 1834 B,
# was bei Gap 1232 in heap/BSS trampelte: der "vm: stack overflow"-HW-Crash des
# Fusion-Relands). Das Gate prueft nur das ANGEBOT; den BEDARF misst bisher nur der
# manuelle xemu-Harness (G5-Kandidat fuer Lane T).
M65VMSTDLIB_MIN_STACK_GAP ?= 1450
M65VMSTDLIB_MIN_BOOT_STACK_GAP ?= 512
# LOAD reserve guard (2026-07-04): dir directory compaction lifted the current
# reserve to 658 B. Hold almost all of it for the Rule-B LOAD redesign instead
# of spending it on more tactical slots; lower this explicitly only with a
# measured LOAD product profile.
M65VMSTDLIB_MIN_BANK0_RESERVE ?= 640
M65VMSTDLIB_BANK0_RESERVE_TARGET ?= 1024
M65VMSTDLIB_EVAL_ROOT_BASELINE ?= 3
M65VMSTDLIB_MIN_SYMBOL_HEADROOM ?= 8
M65VMSTDLIB_MIN_RUNTIME_FRAME_HEADROOM ?= 6
M65VMSTDLIB_MIN_RUNTIME_STACK_HEADROOM ?= 16
M65VMSTDLIB_MAX_PRG_FILE_END ?= 0xc0c0
# MVP-VM-Profil (Lane T, 2026-07-02): der kalte Symbol-Namepool liegt mit
# LISP65_SYMPOOL_EXT im erweiterten RAM. Zusammen mit externem Blob und Boot-
# Overlay ist das volle Stdlib-Boot-Budget tragbar; bis die Boot-Metadaten ebenfalls
# im EXT-Blob liegen, deckelt die PRG-File-End-Grenze den Heap auf den HW-gruenen
# Interim-Wert oben. Der Footprint-Report gate't PRG-Ende, Stack-Luecke,
# .noinit-Abstand und Boot-Overlay-Reserve hart.
# Das externe Preload-Artefakt wird nach 0x050000 vorgeladen: vorn der Bytecode-
# Blob, dahinter ein pointerfreier Metadata-Trailer fuer den naechsten Loader-Schritt.
# Die aktuelle Runtime nutzt die Boot-Metadaten noch als Stack-Overlay im PRG.
# Overlay-Fix 2026-07-02: scripts/lisp65-mega65-boot-overlay.ld platziert die Sektion
# explizit hinter .noinit; ein ELF-/Footprint-Gate verhindert erneuten VMA-Overlap.
# GC_ROOTS 48->112 (Claude/Lane K, 2026-07-02): NICHT-Tail-Rekursion haelt ~6 Root-
# Slots je eval-Ebene; 48 trampelte ab (fact 7) hinter den Rootstack (HW-Befund).
# Dazu Rekursions-Guard in eval_env (sauberer Abort statt Korruption).
# EXT-Heap (Claude/Lane K, 2026-07-02): +4096 Ueberlauf-Zellen in Bank 4 ($40000, F018-DMA;
# Bank 5 = Blob+Namepool). Gesamt 976 hot + 4096 ext = 5072 Zellen. HW-bewiesen (gc-stress
# 300 Zyklen auf Geraet, Hot=96 erzwang EXT-Traffic); Host-Gate: gc-smoke-ext.
# Werkbank-v2a (2026-07-05): IDE + Syntax + eval-string + Treewalk-"/" resident.
# VM_DIR_MAX=272 (2026-07-08: IDE-RUN/STOP-Persistenz +2 fns -> 266 Objekte) laesst wieder etwas
# Luft fuer IDE-Fns; MAX_SYM=400 haelt nach M-x/Multi-line-Region 391 Runtime-Symbole
# plus den 8er Boot-Budget-Headroom. Das ist das alte eingebettete Check-Profil,
# nicht der aktuelle Workbench-Produktpin.
# boot headroom after the screen-bulk-p capability predicate and keeps reserve >= 640.
M65VMSTDLIB_EXTRA_CFLAGS ?= -DMAX_SYM=400 -DNAMEPOOL=8192 -DVM_DIR_MAX=272 -DVM_CODEBUF=56 -DREPL_BUF_MAX=96 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=112 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=2304 -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS -DLISP65_SCREEN_WRITE_STRING -DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_EVAL_PRIMS -DLISP65_EVAL_DIV_PRIM
# Core+Disk-Lib profile keeps VM_DIR_MAX high enough for loading the 96-object IDE
# lib after 8-slot alignment (154 -> 160 + 96 = 256). It uses the EXT symbol-table
# storage and the native screen output driver for a HW-safe REPL, but omits the VM
# screen primitives; the target is intended for load-lib and non-render IDE proof
# calls, not the interactive editor loop.
M65VMSTDLIB_CORE_EXTRA_CFLAGS ?= -DMAX_SYM=330 -DNAMEPOOL=8192 -DVM_DIR_MAX=256 -DVM_CODEBUF=48 -DREPL_BUF_MAX=80 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=136 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_SCREEN_DRIVER -DLISP65_VM_STDLIB_IO_WRAPPERS -DMEGA65_F011_LOAD -DIO_BUF_MAX=1 -DLISP65_DISK_LIBS -DLISP65_VM_GLOBAL_PRIMS
# LOAD proof profile keeps full bytecode surface but omits native bulk screen-write-string;
# it is for REPL/load smokes, not interactive IDE rendering.
M65VMSTDLIB_LOAD_EXTRA_CFLAGS ?= -DMAX_SYM=560 -DNAMEPOOL=8192 -DVM_DIR_MAX=264 -DVM_CODEBUF=48 -DREPL_BUF_MAX=112 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS -DLISP65_VM_STDLIB_IO_WRAPPERS -DMEGA65_F011_LOAD -DIO_BUF_MAX=1
M65VMSTDLIB_LOAD_MIN_BANK0_RESERVE ?= 512
M65VMSTDLIB_DISKLIBS_EXTRA_CFLAGS ?= -DMAX_SYM=128 -DNAMEPOOL=4096 -DVM_DIR_MAX=64 -DVM_CODEBUF=48 -DREPL_BUF_MAX=128 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DGC_ROOTS=136 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_SCREEN_DRIVER -DLISP65_VM_STDLIB_IO_WRAPPERS -DMEGA65_F011_LOAD -DIO_BUF_MAX=1 -DLISP65_DISK_LIBS -DLISP65_VM_GLOBAL_PRIMS
# M6 compile-REPL proof profile: deliberately leaner than the full resident IDE profile.
# It keeps the native screen driver for the REPL itself, but omits VM screen primitives and
# bulk screen-write-string; the interactive IDE remains a disk-lib/post-M6 concern.
M65VMSTDLIB_COMPILE_REPL_EXTRA_CFLAGS ?= -DMAX_SYM=224 -DNAMEPOOL=8192 -DVM_DIR_MAX=96 -DVM_CODEBUF=48 -DREPL_BUF_MAX=80 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_SCREEN_DRIVER -DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_COMPILE_REPL -DLISP65_VM_GLOBAL_PRIMS
M65VMSTDLIB_COMPILE_REPL_MIN_BANK0_RESERVE ?= $(M65VMSTDLIB_MIN_BANK0_RESERVE)
# S5 Phase-1 Proof: kein Blob und keine Blob-Metadaten; xemu-s5-verify.py stagt
# kurze Lisp-Quelle nach EXT und beweist, dass der Boot sie on-device kompiliert.
M65VMSTDLIB_S5_EXTRA_CFLAGS ?= -DMAX_SYM=224 -DNAMEPOOL=8192 -DVM_DIR_MAX=96 -DVM_CODEBUF=48 -DREPL_BUF_MAX=80 -DHIST_MAX=16 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=3072 -DLISP65_SCREEN_DRIVER -DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_COMPILE_REPL -DLISP65_VM_GLOBAL_PRIMS -DMEGA65_F011_LOAD -DIO_BUF_MAX=1 -DLISP65_STDLIB_FROM_DISK
# crfit: historisch HW-gruenes Vollprofil aus docs/vollprofil-stack-heap-collision.md.
# Bleibt als Referenz-/Equivalence-Fahrzeug baubar, ist aber seit M4/einsuite-full
# kein Geraeteprodukt-Gate mehr.
M65VMSTDLIB_CRFIT_EXTRA_CFLAGS ?= -DMAX_SYM=330 -DNAMEPOOL=8192 -DVM_DIR_MAX=242 -DVM_CODEBUF=48 -DREPL_BUF_MAX=80 -DHIST_MAX=8 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=96 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=1024 -DLISP65_SCREEN_DRIVER -DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_COMPILE_REPL -DLISP65_VM_GLOBAL_PRIMS -DLISP65_STACK_GUARD -DCREPL_NF=4 -DCREPL_CODESZ=80 -DCREPL_LITSZ=10
M65VMSTDLIB_CRFIT_MIN_STACK_GAP ?= 700
M65VMSTDLIB_CRFIT_MIN_BANK0_RESERVE ?= 0
# P6c Ein-Suite-Kandidat: Werkbank + lcc-Blob. Der C-Compiler/compile-repl bleibt draussen;
# lcc-install schreibt Code-Objekte direkt. Das Closure-Gate ist Produktpflicht; einige
# Treewalk-Stdlib-Prims liegen im Ein-Suite-Profil als Bytecode-Bridges vor.
M65VMSTDLIB_EINSUITE_HEAP ?= 48
M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS ?= -DMAX_SYM=481 -DNAMEPOOL=8192 -DVM_DIR_MAX=416 -DVM_CODEBUF=56 -DREPL_BUF_MAX=72 -DHIST_MAX=0 -DLISP65_SYMPOOL_EXT -DSYMPOOL_EXT_OFF=0xa000 -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DEXT_CELLS=384 -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS -DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL -DLISP65_LCC_INSTALL_CLOSURES -DLISP65_TREEWALK_STDLIB_BRIDGES -DLISP65_OUTPUT_WRAPPERS_IN_STDLIB -DLISP65_SCREEN_BULK_P_IN_STDLIB
M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS ?= $(M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS) -DLISP65_TREEWALK_STRIP -DLISP65_EVAL_PRIMS
M65VMSTDLIB_EINSUITE_FULL_EXTRA_CFLAGS ?= $(filter-out -DLISP65_SCREEN_BULK_P_IN_STDLIB -DMAX_SYM=481 -DVM_DIR_MAX=416 -DSYMPOOL_EXT_OFF=0xa000,$(M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS)) -DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DLISP65_SCREEN_WRITE_STRING -DMAX_SYM=544 -DVM_DIR_MAX=480 -DSYMPOOL_EXT_OFF=0xc000
M65VMSTDLIB_EINSUITE_FASL_EXTRA_CFLAGS ?= $(filter-out -DSYMPOOL_EXT_OFF=0xa000 -DMAX_SYM=481 -DVM_DIR_MAX=416 -DREPL_BUF_MAX=72,$(M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS)) -DSYMPOOL_EXT_OFF=0xb000 -DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DMAX_SYM=532 -DVM_DIR_MAX=408 -DREPL_BUF_MAX=64 -DLISP65_FASL
M65VMSTDLIB_EINSUITE_CORE_EXTRA_CFLAGS ?= $(filter-out -DSYMPOOL_EXT_OFF=0xa000 -DMAX_SYM=481 -DVM_DIR_MAX=416 -DREPL_BUF_MAX=72 -DLISP65_EVAL_PRIMS -DEXT_CELLS=384,$(M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS)) -DSYMPOOL_EXT_OFF=0xb000 -DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DMAX_SYM=576 -DVM_DIR_MAX=480 -DREPL_BUF_MAX=64 -DLISP65_FASL -DEXT_CELLS=1024 -DLISP65_REPL_IDE_TOGGLE -DLISP65_NURSERY_HYSTERESIS=192
M65VMSTDLIB_EINSUITE_CORE_EDMA_SCROLL_EXTRA_CFLAGS ?= $(M65VMSTDLIB_EINSUITE_CORE_EXTRA_CFLAGS) -DLISP65_SCREEN_EDMA_SCROLL
M65VMSTDLIB_EINSUITE_CORE_STRING_ARENA_EXTRA_CFLAGS ?= $(M65VMSTDLIB_EINSUITE_CORE_EXTRA_CFLAGS) -DLISP65_STRING_ARENA
M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION ?= 8
M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE ?= 0
M65VMSTDLIB_BSS_CAP ?= 0xcd40
M65VMSTDLIB_BSS_CAP_LD ?= scripts/lisp65-mega65-bss-cap.ld
M65VMSTDLIB_CRFIT_LDFLAGS ?= -Wl,--defsym=__lisp65_bss_cap=$(M65VMSTDLIB_BSS_CAP) -Wl,-T,$(M65VMSTDLIB_BSS_CAP_LD)
M65VMSTDLIB_DIAG_HEAP ?= $(M65VMSTDLIB_HEAP)
M65VMSTDLIB_DIAG_STEP_LIMIT ?= 20000
M65VMSTDLIB_DIAG_EXTRA_CFLAGS ?= $(M65VMSTDLIB_EXTRA_CFLAGS) -DVM_STEP_LIMIT=$(M65VMSTDLIB_DIAG_STEP_LIMIT) -DLISP65_VM_DIAGNOSTICS
STRING_ARENA_PROBE_CFLAGS ?= -std=c99 -O1 -w -DLISP65_VM -DLISP65_EMBED_STDLIB -DHEAP_CELLS=48 -DEXT_CELLS=1024 -DLISP65_EXT_HEAP -DLISP65_MARK_BITMAP -DLISP65_NURSERY_HYSTERESIS=192 -DMAX_SYM=576 -DNAMEPOOL=8192 -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DVM_DIR_MAX=480 -DVM_CODEBUF=56 -DREPL_BUF_MAX=64 -DLISP65_VM_GLOBAL_PRIMS
STRING_ARENA_PROBE_SRCS := scripts/string-arena-probe-main.c src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/interrupt.c src/screen.c src/io.c src/vm_embed.c

RUNTIME_KNOWN_OPEN := tests/bytecode/runtime/p0-runtime-known-open.json
HOST_ORACLE_FILES := salvage/lisp/prelude.lsp salvage/lisp/conformance.lsp

include config/workbench.mk
include mk/workbench.mk
include config/runtime-core.mk
include config/runtime-core-v2-proof.mk
include mk/runtime-core.mk
include mk/overlay-package.mk
include mk/v2-string-caps.mk
include mk/v2-callprim-runtime.mk
include mk/runtime-core-v2-proof.mk

.PHONY: all prelude mvp-vm-stdlib mvp-vm-stdlib-core mvp-vm-stdlib-disklibs mvp-vm-stdlib-hw-selftest mvp-vm-stdlib-known-open-diagnostic mvp-vm-stdlib-compile-repl mvp-vm-stdlib-crfit mvp-vm-stdlib-s5-proof mvp-vm-stdlib-einsuite mvp-vm-stdlib-einsuite-strip mvp-vm-stdlib-einsuite-full mvp-vm-stdlib-einsuite-fasl mvp-vm-stdlib-einsuite-core mvp-vm-stdlib-einsuite-core-edma-scroll mvp-vm-stdlib-einsuite-core-string-arena mvp-vm-stdlib-einsuite-core-arena-ide s5-source-d81 mvp-vm-stdlib-footprint-report mvp-vm-stdlib-compile-repl-footprint-report mvp-vm-stdlib-crfit-footprint-report mvp-vm-stdlib-einsuite-footprint-report mvp-vm-stdlib-einsuite-strip-footprint-report mvp-vm-stdlib-einsuite-full-footprint-report mvp-vm-stdlib-einsuite-fasl-footprint-report mvp-vm-stdlib-einsuite-core-footprint-report mvp-vm-stdlib-einsuite-core-edma-scroll-footprint-report mvp-vm-stdlib-einsuite-core-string-arena-footprint-report mvp-vm-stdlib-einsuite-core-arena-ide-footprint-report screen-edma-scroll-footprint-delta mvp-vm-stdlib-load-footprint-report mvp-vm-stdlib-boot-budget-report mvp-vm-stdlib-runtime-budget-report bank0-reclaim-report stdlib-footprint-rank workbench-ship-d81 workbench-d81-bam-sanity workbench-d81-bam-alloc-diff-selftest workbench-d81-chain-write-diff-selftest mvp-ship run run-mvp-vm-stdlib check clean FORCE
.PHONY: host-oracle legacy-lisp64-oracle xmega65-safety-check fixed-point-check closure-surface-check ide-host-slice-check ide-bytecode-cost-report ide-render-callgraph ide-bytecode-dynamic-report bytecode-p0-oracle bytecode-p0-compiler-check bytecode-p0-program-check bytecode-p0-bundle-check bytecode-p0-stdlib-check bytecode-p0-stdlib-artifacts string-arena-probe bytecode-p0-disklib-check bytecode-p0-disklib-artifacts bytecode-p0-disklib-d81 l65m-contract-check l65m-native-loader-check fasl-emit-check bytecode-p0-ide-full-lib-check bytecode-p0-ide-lib-check bytecode-p0-ide-lib-artifacts bytecode-p0-ide-extra-lib-check bytecode-p0-ide-extra-lib-artifacts bytecode-p0-ide-lib-d81 bytecode-p0-format-lib-check bytecode-p0-format-lib-artifacts bytecode-p0-format-lib-d81 bytecode-p0-fixed-lib-check bytecode-p0-fixed-lib-artifacts bytecode-p0-fixed-lib-d81 bytecode-p0-strings-extra-lib-check bytecode-p0-strings-extra-lib-artifacts bytecode-p0-strings-extra-lib-d81 bytecode-p0-place-lib-check bytecode-p0-place-lib-artifacts bytecode-p0-place-lib-d81 bytecode-p0-pilot-libs-check bytecode-p0-pilot-libs-artifacts bytecode-p0-pilot-libs-d81 demo-suite-check demo-suite-d81 bytecode-known-open-diagnostic-artifacts bytecode-p0-drift-check bytecode-vm-compile-check runtime-known-open-check vm-smoke gc-smoke native-reader-conformance compile-smoke compile-run repl-session lcc-install-device-smoke lcc-install-overlay-smoke vm-boot-fastpath-smoke error-state-smoke prelude-compile-check prelude-load-run output-smoke eval-prims-smoke save-semantics-check
.PHONY: eval-bytecode-equivalence-check eval-surface-contract-check equivalence-check dialect-v2-prelude-control-selftest dialect-v2-prelude-control-check dialect-v2-prelude-control-matrix dialect-v2-prelude-evidence-selftest dialect-v2-prelude-evidence-check dialect-v2-prelude-evidence-live-check bytecode-p0-native-compiler-check post-mvp-stdlib-polish-check stdlib-embed-whatif stdlib-embed-whatif-check mvp-vm-stdlib-boot-budget-check mvp-vm-stdlib-runtime-budget-check xemu-mega65-prelude-gc-smoke hw-smoke-vm-stdlib hw-smoke-vm-stdlib-dry-run hw-smoke-vm-stdlib-selftest hw-smoke-vm-stdlib-selftest-dry-run hw-workbench-ux-smoke hw-workbench-ux-smoke-dry-run hw-workbench-bam-read-smoke hw-workbench-bam-read-smoke-dry-run hw-workbench-bam-alloc-smoke-prg hw-workbench-bam-alloc-smoke hw-workbench-bam-alloc-smoke-dry-run hw-workbench-chain-write-smoke-prg hw-workbench-chain-write-smoke hw-workbench-chain-write-smoke-dry-run hw-smoke-compile-repl hw-smoke-compile-repl-dry-run hw-known-open-diagnostic hw-known-open-diagnostic-dry-run hw-demo-suite hw-demo-suite-dry-run hw-stress-full hw-stress-full-dry-run hw-stress-dmaprof hw-stress-dmaprof-dry-run hw-stress-deep hw-stress-deep-dry-run hw-stress-deep1 hw-stress-deep1-dry-run hw-stress-deep2 hw-stress-deep2-dry-run hw-stress-redeploy hw-stress-redeploy-dry-run hw-stress-redeploy-deep hw-stress-redeploy-deep-dry-run hw-access-smoke-prg hw-access-smoke hw-access-smoke-dry-run hw-access-smoke-readback hw-access-smoke-readback-dry-run hw-color-ram-smoke-prg hw-color-ram-smoke hw-color-ram-smoke-dry-run hw-color-ram-smoke-readback hw-color-ram-smoke-readback-dry-run hw-edma-screen-smoke-prg hw-edma-screen-smoke hw-edma-screen-smoke-dry-run hw-edma-screen-smoke-readback hw-edma-screen-smoke-readback-dry-run hyppo-probe-matrix
.PHONY: dialect-v2-eval-apply-funcall-selftest dialect-v2-eval-apply-funcall-check dialect-v2-eval-apply-funcall-matrix
.PHONY: dialect-v2-lists-selftest dialect-v2-lists-check dialect-v2-lists-native-matrix dialect-v2-lists-p0-selftest dialect-v2-lists-p0-check dialect-v2-lists-lcc-selftest dialect-v2-lists-lcc-check dialect-v2-lists-matrix dialect-v2-lists-type-errors-check
.PHONY: dialect-v2-system-runtime-check dialect-v2-system-runtime-evidence-selftest dialect-v2-system-runtime-evidence-build dialect-v2-system-runtime-evidence-check
.PHONY: dialect-v2-strings-selftest dialect-v2-strings-check dialect-v2-strings-native-stage3-matrix dialect-v2-strings-compiler-matrix dialect-v2-strings-native-matrix dialect-v2-strings-p0-selftest dialect-v2-strings-p0-check dialect-v2-strings-lcc-selftest dialect-v2-strings-lcc-stage3-check dialect-v2-strings-lcc-check dialect-v2-strings-matrix v2-string-codec-workload-selftest v2-string-codec-workload-check
.PHONY: dialect-v2-lists-evidence-selftest dialect-v2-lists-evidence-build dialect-v2-lists-evidence-check
.PHONY: dialect-v2-strings-evidence-selftest dialect-v2-strings-evidence-build dialect-v2-strings-evidence-check
.PHONY: dialect-v2-capacity-ledger-selftest dialect-v2-capacity-ledger-check
.PHONY: block-bank-delta-policy-selftest block-bank-delta-policy-check block-capacity-delta-policy-selftest block-capacity-delta-policy-check r2-known-open-selftest r2-known-open-check directory-only-l65m-v2-probe-selftest directory-only-l65m-v2-probe-check directory-only-emitter-selftest l65m-v2-product-check
.PHONY: v2-prim-lowering-check
.PHONY: dialect-v2-lcc-compile-error-selftest dialect-v2-lcc-compile-error-check
.PHONY: v2-carrier-state-selftest v2-carrier-state-active v2-carrier-cut-host-check v2-carrier-state-removed v2-native-function-registry-check v2-native-function-matrix-check v2-workbench-symbol-diff-selftest v2-workbench-symbol-diff-check v2-workbench-symbol-diff-live v2-workbench-deresidentization-audit-selftest v2-workbench-deresidentization-audit-check v2-workbench-deresidentization-prototype-selftest v2-workbench-deresidentization-prototype-check v2-fasl-save-host-selftest v2-fasl-save-host-check dialect-v2-number-to-string-check v2-capability-carrier-internal-g5-selftest v2-capability-carrier-internal-g5-check v2-capability-carrier-internal-g5-runtime-package v2-capability-carrier-internal-g5-workbench-link v2-capability-carrier-internal-g5-d81 v2-capability-carrier-internal-g5-candidate v2-capability-carrier-internal-g5-plan v2-capability-carrier-internal-g5-hw-package v2-cp5-g5-archive-check v2-capability-carrier-contract-selftest v2-capability-carrier-contract-check v2-capability-carrier-check-host-1 v2-capability-carrier-check-host-2 v2-capability-carrier-check-host-3 v2-capability-carrier-check-host-4 v2-capability-carrier-check-host-5
.PHONY: interim-ship interim-ship-matrix ship-footprint-report full-embed-fit-report ship-readiness-report ship-readiness-check ship-artifacts-check
.PHONY: legacy-interim-ship-footprint-report legacy-interim-full-embed-fit-report legacy-interim-ship-readiness-report legacy-interim-ship-readiness-check legacy-interim-ship-artifacts-check legacy-interim-ship-check legacy-interim-ship-release
.PHONY: release ship-release ship-check
.PHONY: f011-interim-ship f011-offline-image f011-defd81-image f011-load-hw-visible stdlib-d81 f011-stdlib-image f011-autoload-image f011-stdlib-layer-probe-image f011-stdlib-layer-probe-report f011-stdlib-profile-matrix f011-check hw-smoke-interim hw-smoke-interim-dry-run hw-smoke-f011-stdlib hw-smoke-f011-stdlib-dry-run xemu-f011-load-probe xemu-f011-load-smoke xemu-f011-stdlib-smoke xemu-f011-stdlib-layer-probe
.PHONY: legacy-c64 legacy-prelude-c64 legacy-run-c64 legacy-c64-check legacy-xc64-smoke legacy-xc64-prelude-smoke legacy-xc64-prelude-gc-smoke legacy-xc64-load-source-smoke legacy-xc64-string-smoke legacy-xc64-stdlib-smoke legacy-xc64-format-smoke legacy-xc64-control-smoke
.PHONY: m65-disk-alloc-load-check m65-disk-alloc-var-load-check workbench-d81-dir-write-diff-selftest workbench-d81-save-new-diff-selftest workbench-d81-save-new-scan-diff-selftest workbench-d81-save-new-var-diff-selftest hw-workbench-dir-write-smoke-prg hw-workbench-dir-write-smoke hw-workbench-dir-write-smoke-dry-run hw-workbench-save-new-smoke-prg hw-workbench-save-new-smoke hw-workbench-save-new-smoke-dry-run hw-workbench-save-new-scan-smoke-prg hw-workbench-save-new-scan-smoke hw-workbench-save-new-scan-smoke-dry-run hw-workbench-save-new-var-smoke-prg hw-workbench-save-new-var-smoke hw-workbench-save-new-var-smoke-dry-run
.PHONY: mvp-ship-artifacts mvp-ship-wip workbench-ship-artifacts-check workbench-ship-verifier-selftest workbench-reproducibility-check verify-ship print-workbench-resolved-profile bytecode-p0-workbench-stdlib-artifacts
.PHONY: bytecode-p0-private-inline-check workbench-private-inline-composition-probe gc-symbol-scan-timing-check ide-capacity-selftest ide-capacity-check m65d-blank-d81-oracle-selftest bytecode-p0-m65d-lib-check bytecode-p0-m65d-lib-artifacts
all: $(M65PRG)

$(M65PRG): $(SRCS) | build
	$(CC_M65) $(CFLAGS) $(SRCS) -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

legacy-c64: $(C64PRG)
$(C64PRG): $(SRCS) | build
	$(LEGACY_CC_C64) $(CFLAGS) $(SRCS) -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

$(PRELUDE_GEN): $(PRELUDE_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(PRELUDE_LISP) $@

$(LOAD_SMOKE_GEN): $(LOAD_SMOKE_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(LOAD_SMOKE_LISP) $@ load_smoke_src

$(STDLIB_STRINGS_GEN): $(STDLIB_STRINGS_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_STRINGS_LISP) $@ stdlib_strings_src

$(STDLIB_SEQUENCES_GEN): $(STDLIB_SEQUENCES_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_SEQUENCES_LISP) $@ stdlib_sequences_src

$(STDLIB_MATH_GEN): $(STDLIB_MATH_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_MATH_LISP) $@ stdlib_math_src

$(STDLIB_PLISTS_GEN): $(STDLIB_PLISTS_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_PLISTS_LISP) $@ stdlib_plists_src

$(STDLIB_FORMAT_GEN): $(STDLIB_FORMAT_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_FORMAT_LISP) $@ stdlib_format_src

$(STDLIB_CONTROL_GEN): $(STDLIB_CONTROL_LISP) scripts/embed-prelude.py
	python3 scripts/embed-prelude.py $(STDLIB_CONTROL_LISP) $@ stdlib_control_src

$(LCC_GEN): $(LCC_LISP) scripts/embed-prelude.py | build
	python3 scripts/embed-prelude.py $(LCC_LISP) $@ lcc_src

$(M3_CHAIN_GEN): $(M3_CHAIN_SOURCE) scripts/embed-prelude.py | build
	python3 scripts/embed-prelude.py $(M3_CHAIN_SOURCE) $@ m3_chain_src

$(M4_DIR_GEN): $(M4_DIR_SOURCE) scripts/embed-prelude.py | build
	python3 scripts/embed-prelude.py $(M4_DIR_SOURCE) $@ m4_dir_src

$(M5_PAYLOAD_GEN): $(M5_PAYLOAD_FORM) scripts/embed-prelude.py | build
	python3 scripts/embed-prelude.py $(M5_PAYLOAD_FORM) $@ m5_payload_src

$(M7_PAYLOAD_GEN): $(M7_PAYLOAD_FORM) scripts/embed-prelude.py | build
	python3 scripts/embed-prelude.py $(M7_PAYLOAD_FORM) $@ m7_payload_src

prelude: $(M65PRELUDEPRG)
$(M65PRELUDEPRG): $(SRCS) $(PRELUDE_GEN) | build
	$(CC_M65) $(CFLAGS) -DLISP65_WITH_PRELUDE $(SRCS) -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

legacy-prelude-c64: $(C64PRELUDEPRG)
$(C64PRELUDEPRG): $(SRCS) $(PRELUDE_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_WITH_PRELUDE $(SRCS) -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

mvp-vm-stdlib: $(M65VMSTDLIBPRG)
$(M65VMSTDLIBPRG): $(SRCS) $(VM_SRCS) bytecode-p0-stdlib-artifacts | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

mvp-vm-stdlib-einsuite: $(M65VMSTDLIBEINSUITEPRG)
$(M65VMSTDLIBEINSUITEPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/lcc)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-strip: $(M65VMSTDLIBEINSUITESTRIPPRG)
$(M65VMSTDLIBEINSUITESTRIPPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/strip)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-full: $(M65VMSTDLIBEINSUITEFULLPRG)
$(M65VMSTDLIBEINSUITEFULLPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_FULL_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_FULL_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/full)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-fasl: $(M65VMSTDLIBEINSUITEFASLPRG)
$(M65VMSTDLIBEINSUITEFASLPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_FASL_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_FASL_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/fasl)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-core: $(M65VMSTDLIBEINSUITECOREPRG)
$(M65VMSTDLIBEINSUITECOREPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_CORE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_CORE_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/core)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-core-edma-scroll: $(M65VMSTDLIBEINSUITECOREEDMASCROLLPRG)
$(M65VMSTDLIBEINSUITECOREEDMASCROLLPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_CORE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_CORE_EDMA_SCROLL_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/core-edma-scroll)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-core-string-arena: $(M65VMSTDLIBEINSUITECORESTRINGARENAPRG)
$(M65VMSTDLIBEINSUITECORESTRINGARENAPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_CORE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_CORE_STRING_ARENA_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/core-string-arena)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-core: $(M65VMSTDLIBCOREPRG)
$(M65VMSTDLIBCOREPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_CORE_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_CORE_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

mvp-vm-stdlib-disklibs: $(M65VMSTDLIBDISKLIBSPRG)
$(M65VMSTDLIBDISKLIBSPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_DISKLIBS_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_DISKLIBS_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

mvp-vm-stdlib-hw-selftest: $(M65VMSTDLIBSELFTESTPRG)
$(M65VMSTDLIBSELFTESTPRG): $(RUNTIME_SRCS) $(VM_SRCS) bytecode-p0-stdlib-artifacts scripts/mvp-vm-stdlib-hw-selftest-main.c | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(RUNTIME_SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) scripts/mvp-vm-stdlib-hw-selftest-main.c $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

mvp-vm-stdlib-known-open-diagnostic: $(M65VMSTDLIBDIAGPRG)
$(M65VMSTDLIBDIAGPRG): $(SRCS) $(VM_SRCS) bytecode-known-open-diagnostic-artifacts | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_DIAG_HEAP) \
		$(M65VMSTDLIB_DIAG_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode/known-open-diagnostic -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_KNOWN_OPEN_DIAG_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, VM_STEP_LIMIT=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_DIAG_HEAP)" "$(M65VMSTDLIB_DIAG_STEP_LIMIT)"

mvp-vm-stdlib-compile-repl: $(M65VMSTDLIBCOMPILEPRG)
# LEAN-Proving-Profil (Claude, 2026-07-05, HW-Fix): OHNE Blob UND ohne Prelude -- nur Compiler + VM + REPL.
# Der Nutzer definiert alles selbst; die Proving-Tests (defun/call/Closures) nutzen nur Compiler-Formen
# (+/*/let/setq). Kein LISP65_EMBED_STDLIB (Blob) -> keine Region/Blob-Kollision in Bank 5 (HW-Bug
# (sq 5)->cannot compile); kein LISP65_WITH_PRELUDE -> kein prelude_src im PRG (~7 KB .rodata gespart).
# EMBED_DMA bleibt (vm_ext_write/vm_code_load fuer die Compiled-Fn-Region + EXT-Symboltabelle). eval.c
# faellt via gc-sections ganz weg. Deploy OHNE --preload-bin; Region ab Bank 5/0 (crepl_off=0).
# TODO(Codex-Review): eigenes Target/Var; volles Prelude braucht Bank-0-Diaet (prelude_src ~7 KB .rodata).
$(M65VMSTDLIBCOMPILEPRG): $(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) bytecode-p0-stdlib-artifacts | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_COMPILE_REPL_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, LEAN/no-blob)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

mvp-vm-stdlib-crfit: $(M65VMSTDLIBCRFITPRG)
$(M65VMSTDLIBCRFITPRG): $(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) $(M65VMSTDLIB_BSS_CAP_LD) bytecode-p0-stdlib-artifacts | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_CRFIT_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) $(BYTECODE_STDLIB_C) \
		$(M65VMSTDLIB_CRFIT_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, bss_cap=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)" "$(M65VMSTDLIB_BSS_CAP)"

mvp-vm-stdlib-s5-proof: $(M65VMSTDLIBS5PRG)
$(M65VMSTDLIBS5PRG): $(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) scripts/xemu-s5-verify.py | build
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_HEAP) \
		$(M65VMSTDLIB_S5_EXTRA_CFLAGS) -Isrc \
		$(SRCS) $(VM_SRCS) $(COMPILE_SRCS) $(COMPILE_REPL_SRCS) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, source-on-disk proof)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_HEAP)"

s5-source-d81: $(S5_SOURCE_D81)
$(S5_SOURCE_D81): scripts/build-s5-source-d81.sh tools/host-lisp/s5_source_package.py scripts/split-lisp-source.py $(S5_SOURCE_SUITE) $(wildcard lib/*.lisp) | build
	S5_SOURCE_D81="$(S5_SOURCE_D81)" \
	S5_SOURCE_SUITE="$(S5_SOURCE_SUITE)" \
	S5_SOURCE_CHUNK_DIR="$(S5_SOURCE_CHUNK_DIR)" \
	S5_SOURCE_BUNDLE="$(S5_SOURCE_BUNDLE)" \
	S5_SOURCE_PACKAGE_MANIFEST="$(S5_SOURCE_PACKAGE_MANIFEST)" \
	S5_SOURCE_MANIFEST="$(S5_SOURCE_MANIFEST)" \
	S5_SOURCE_CHUNK_MAX="$(S5_SOURCE_CHUNK_MAX)" \
	sh scripts/build-s5-source-d81.sh

mvp-vm-stdlib-footprint-report:
	$(MAKE) mvp-vm-stdlib
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--extra-cflags "$(M65VMSTDLIB_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITEPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITEPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-strip-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-strip
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_STRIP_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITESTRIPPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITESTRIPPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_STRIP_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_STRIP_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-full-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-full
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_FULL_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITEFULLPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITEFULLPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_FULL_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_FULL_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-fasl-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-fasl
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_FASL_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITEFASLPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITEFASLPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_FASL_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_FASL_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-core-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-core
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_CORE_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITECOREPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITECOREPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_CORE_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_CORE_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-core-edma-scroll-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-core-edma-scroll
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_CORE_EDMA_SCROLL_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITECOREEDMASCROLLPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITECOREEDMASCROLLPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_CORE_EDMA_SCROLL_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_CORE_EDMA_SCROLL_FOOTPRINT_REPORT)"

mvp-vm-stdlib-einsuite-core-string-arena-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-core-string-arena
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_CORE_STRING_ARENA_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITECORESTRINGARENAPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITECORESTRINGARENAPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_CORE_STRING_ARENA_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_CORE_STRING_ARENA_FOOTPRINT_REPORT)"

# ---- Arena-IDE (no-FASL) Lean-Profil (Claude/K, 2026-07-08) --------------------------
# Loest den Bank-0-Blocker der Voll-Arena (bank0_reserve -620): Codex-Messung zeigte, dass
# allein das Entfernen von -DLISP65_FASL reicht (reserve -> +630). Arena + IDE + REPL/lcc +
# Disk-load/save + load-lib + (edit)-Launcher bleiben; compile-file/FASL faellt aus dem
# Produktvertrag. Suite entfernt lib/lcc-fasl.lisp KONSISTENT mit dem C-Flag (keine
# laufzeit-kaputten Registrierungen). Suite host-verifiziert (bytecode-p0-stdlib-check PASS,
# 277 Fn). Geraete-Footprint/HW-Gate: Codex verifiziert (Toolchain fehlt im Claude-Worktree).
M65VMSTDLIBEINSUITECOREARENAIDEPRG := build/lisp65-mega65-vm-stdlib-einsuite-core-arena-ide.prg
BYTECODE_STDLIB_EINSUITE_CORE_ARENA_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-core-arena-subset.json
M65VMSTDLIB_EINSUITE_CORE_ARENA_IDE_EXTRA_CFLAGS ?= $(filter-out -DLISP65_FASL,$(M65VMSTDLIB_EINSUITE_CORE_STRING_ARENA_EXTRA_CFLAGS))
MVP_VM_STDLIB_EINSUITE_CORE_ARENA_IDE_FOOTPRINT_REPORT ?= build/bytecode/mvp-vm-stdlib-einsuite-core-arena-ide-footprint.txt

# Workbench (Claude/K, 2026-07-08): Arena-IDE + compile-string-Slow-Path. Arena-IDE-CFLAGS (kein
# natives FASL) + -DLISP65_COMPILE_STRING (die kleine FASL-Byte-/String-Reader-Naht OHNE Disk-Source,
# kein disk_dir_find). Suite bringt lib/lcc-fasl.lisp zurueck, aber ohne compile-file/fasl-emit-scratch.
# Der Workbench-Kandidat zeigt jetzt hierauf (nicht mehr auf reines arena-ide ohne compile-file).
# Workbench-Caps (Codex-HW-Retest 2026-07-08, Host-Nachzug 2026-07-09): volle
# IDE-on-demand braucht nach Minibuffer/Datei-Persistenz/TAB-Auswahl und
# Symbol-Introspektions-Reclaim 211 Dir-Slots. AP8.0 fuegt zwei erstklassige
# Arithmetik-Bridges hinzu; die konservative IDE+IDEX+AP6-Projektion endet nach
# Ausrichtung bei 552 Eintraegen. Mit Pin 560 bleiben 8 Post-Align-Slots fuer
# kleine Compile-/Demo-FASLs in derselben Session. Die IDE-Lib bringt
# Smoke-erwartet `symbol-count` auf knapp unter 700;
# Pin 720 laesst danach knappen User-/Demo-Compile-Headroom. Der Namepool ist
# ebenfalls EXT-basiert; `SYMPOOL_EXT_OFF=0xc9e0`/`NAMEPOOL=9536` haelt
# kombinierten Stdlib+IDE-Load ueber der Namensgrenze und laesst zugleich
# ein sehr knappes EXT-Codefenster fuer die ladbare IDE-Lib. `SYMPOOL_EXT_OFF +
# NAMEPOOL` bleibt bei $ef20, die nachgelagerten symval/nameoff/symfn-Tabellen
# behalten also ihre Lage und das Symbol-Layout endet weiter exakt an der
# Bankgrenze. Fuer Save-New via `tmp`-Reserve-Slot ist die IDE-Lib groesser;
# Workbench verschiebt deshalb Disk-Scratch nach $6900 und reduziert die
# String-Arena leicht auf 0x2480 je Halbfenster. Das Host-Gate
# `workbench-disk-lib-budget-check` prueft diese EXT-Code-, Symbol-, Namepool-
# und Diskfenster-Grenzen explizit.
# `LISP65_SYMFN_EXT` verlagert die Funktionszellen nach EXT; dadurch
# bleiben MAX_SYM/VM_DIR_MAX trotz IDE-on-demand im Stack-Gate. Der RUN/STOP->IDE-Komforttoggle wird im Produktprofil
# herausgefiltert, damit das PRG-Ende-Gate haelt; `(edit)` bleibt der REPL-Einstieg. Die einstufige
# REPL-History nutzt im Workbench-Sparpfad den vorhandenen REPL-Buffer statt eines zweiten Puffers.
# REPL_BUF_MAX=192 ist ein reiner BSS/Stack-Gap-Tradeoff: laengere Single-Line-Forms ohne PRG-Code.
# Alias zeigt auf das Workbench-Profil (arena-ide + compile-string-Slow-Path). Umzug am
# 2026-07-08 nach gruenem Footprint (Codex-Caps MAX_SYM=472/VM_DIR_MAX=384: stack_gap=1474,
# reserve=24) UND gruenem HW-Compile-Roundtrip auf echter MEGA65: mehrformige Quelle
# (compile-string "(defun a () 40)(defun b () (+ (a) 2))" "an") in vorallozierten SEQ-Slot,
# (load-lib "an") -> t, (b) -> 42; VM-Health gc_badobj=0/mem_oom=0. Beleg: build/hw/ob-result.png.
.PHONY: mvp-vm-stdlib-einsuite-core-arena-ide mvp-vm-stdlib-einsuite-core-arena-ide-footprint-report mvp-vm-stdlib-einsuite-core-workbench mvp-vm-stdlib-einsuite-core-workbench-footprint-report workbench-candidate workbench-candidate-footprint-report workbench-gate workbench-disk-lib-budget-check workbench-symfn-dynamic-report workbench-persistence-gate

mvp-vm-stdlib-einsuite-core-arena-ide: $(M65VMSTDLIBEINSUITECOREARENAIDEPRG)
$(M65VMSTDLIBEINSUITECOREARENAIDEPRG): $(SRCS) $(VM_SRCS) FORCE | build
	$(MAKE) bytecode-p0-stdlib-artifacts BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_EINSUITE_CORE_ARENA_SUITE)"
	$(CC_M65) $(M65VMSTDLIB_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(M65VMSTDLIB_EINSUITE_HEAP) \
		$(M65VMSTDLIB_EINSUITE_CORE_ARENA_IDE_EXTRA_CFLAGS) -Isrc -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(BYTECODE_STDLIB_C) $(M65VMSTDLIB_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/core-arena-ide no-FASL)\n' "$@" "$$(stat -c%s $@)" "$(M65VMSTDLIB_EINSUITE_HEAP)"

mvp-vm-stdlib-einsuite-core-arena-ide-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-core-arena-ide
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_EINSUITE_CORE_ARENA_IDE_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBEINSUITECOREARENAIDEPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBEINSUITECOREARENAIDEPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_EINSUITE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_EINSUITE_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(M65VMSTDLIB_EINSUITE_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(M65VMSTDLIB_EINSUITE_CORE_ARENA_IDE_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_EINSUITE_CORE_ARENA_IDE_FOOTPRINT_REPORT)"

screen-edma-scroll-footprint-delta:
	$(MAKE) mvp-vm-stdlib-einsuite-core-footprint-report
	@status=0; \
		$(MAKE) mvp-vm-stdlib-einsuite-core-edma-scroll-footprint-report || status=$$?; \
		python3 scripts/footprint-delta.py \
			--baseline "$(MVP_VM_STDLIB_EINSUITE_CORE_FOOTPRINT_REPORT)" \
			--candidate "$(MVP_VM_STDLIB_EINSUITE_CORE_EDMA_SCROLL_FOOTPRINT_REPORT)" \
			--out "$(SCREEN_EDMA_SCROLL_FOOTPRINT_DELTA_REPORT)" \
			--label "screen-edma-scroll" \
			--candidate-exit "$$status"; \
		printf '==> geschrieben: %s\n' "$(SCREEN_EDMA_SCROLL_FOOTPRINT_DELTA_REPORT)"

mvp-vm-stdlib-compile-repl-footprint-report:
	$(MAKE) mvp-vm-stdlib-compile-repl
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_COMPILE_REPL_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBCOMPILEPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBCOMPILEPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_COMPILE_REPL_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--native-c src/compile.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--extra-cflags "$(M65VMSTDLIB_COMPILE_REPL_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_COMPILE_REPL_FOOTPRINT_REPORT)"

mvp-vm-stdlib-crfit-footprint-report:
	$(MAKE) mvp-vm-stdlib-crfit
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(MVP_VM_STDLIB_CRFIT_FOOTPRINT_REPORT)" \
		--prg "$(M65VMSTDLIBCRFITPRG)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--header "$(BYTECODE_STDLIB_HEADER)" \
		--elf "$(M65VMSTDLIBCRFITPRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(M65VMSTDLIB_CRFIT_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(M65VMSTDLIB_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(M65VMSTDLIB_CRFIT_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(M65VMSTDLIB_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(M65VMSTDLIB_MAX_PRG_FILE_END)" \
		--m65-cflags "$(M65VMSTDLIB_CFLAGS)" \
		--heap-cells "$(M65VMSTDLIB_HEAP)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--native-c src/compile.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--extra-cflags "$(M65VMSTDLIB_CRFIT_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_CRFIT_FOOTPRINT_REPORT)"

mvp-vm-stdlib-load-footprint-report:
	$(MAKE) mvp-vm-stdlib-footprint-report \
		BYTECODE_STDLIB_SUITE="$(BYTECODE_STDLIB_LOAD_SUITE)" \
		M65VMSTDLIB_EXTRA_CFLAGS="$(M65VMSTDLIB_LOAD_EXTRA_CFLAGS)" \
		M65VMSTDLIB_MIN_BANK0_RESERVE="$(M65VMSTDLIB_LOAD_MIN_BANK0_RESERVE)" \
		MVP_VM_STDLIB_FOOTPRINT_REPORT="$(MVP_VM_STDLIB_LOAD_FOOTPRINT_REPORT)"

mvp-vm-stdlib-boot-budget-report: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/mvp_vm_stdlib_boot_budget.py \
		--out "$(MVP_VM_STDLIB_BOOT_BUDGET_REPORT)" \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--extra-cflags "$(M65VMSTDLIB_EXTRA_CFLAGS)"
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_BOOT_BUDGET_REPORT)"

mvp-vm-stdlib-runtime-budget-report: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/mvp_vm_stdlib_runtime_budget.py \
		--out "$(MVP_VM_STDLIB_RUNTIME_BUDGET_REPORT)" \
		--suite "$(BYTECODE_STDLIB_SUITE)" \
		--extra-cflags "$(M65VMSTDLIB_EXTRA_CFLAGS)" \
		--native-initial-base "$(M65VMSTDLIB_EVAL_ROOT_BASELINE)" \
		--min-native-frame-headroom "$(M65VMSTDLIB_MIN_RUNTIME_FRAME_HEADROOM)" \
		--min-native-stack-headroom "$(M65VMSTDLIB_MIN_RUNTIME_STACK_HEADROOM)" \
		--include-ide-scenarios
	@printf '==> geschrieben: %s\n' "$(MVP_VM_STDLIB_RUNTIME_BUDGET_REPORT)"

bank0-reclaim-report: workbench-reference-footprint-report
	python3 tools/host-lisp/bank0_reclaim_report.py \
		--elf "$(WORKBENCH_REFERENCE_PRG).elf" \
		--footprint "$(WORKBENCH_REFERENCE_FOOTPRINT_REPORT)" \
		--out "$(BANK0_RECLAIM_REPORT)" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)"
	@printf '==> geschrieben: %s\n' "$(BANK0_RECLAIM_REPORT)"

stdlib-footprint-rank: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/stdlib_footprint_rank.py --focus 'string|char|trim|subseq|search|substring'

stdlib-embed-whatif:
	python3 tools/host-lisp/stdlib_embed_whatif.py $(BYTECODE_STRING_POLISH_SUITE) $(BYTECODE_FIXED_SUITE)

interim-ship:
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/build-interim-ship.sh

interim-ship-matrix:
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/build-interim-ship-matrix.sh

legacy-interim-ship-footprint-report: interim-ship interim-ship-matrix f011-interim-ship stdlib-d81
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/ship-footprint-report.sh

legacy-interim-full-embed-fit-report:
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/full-embed-fit-report.sh

legacy-interim-ship-readiness-report:
	@mkdir -p $(LEGACY_INTERIM_SHIP_DIR)
	python3 tools/host-lisp/ship_readiness.py \
		--footprint $(LEGACY_INTERIM_SHIP_DIR)/footprint-report.txt \
		--full-embed $(LEGACY_INTERIM_SHIP_DIR)/full-embed-fit-report.txt \
		--f011-matrix $(LEGACY_INTERIM_SHIP_DIR)/f011-stdlib-profile-matrix.txt \
		> $(LEGACY_INTERIM_SHIP_DIR)/ship-readiness.txt
	@printf '==> geschrieben: $(LEGACY_INTERIM_SHIP_DIR)/ship-readiness.txt\n'

legacy-interim-ship-readiness-check: legacy-interim-ship-readiness-report
	python3 tools/host-lisp/check_ship_readiness.py $(LEGACY_INTERIM_SHIP_DIR)/ship-readiness.txt

legacy-interim-ship-artifacts-check:
	python3 tools/host-lisp/check_ship_artifacts.py \
		--ship $(LEGACY_INTERIM_SHIP_DIR)/manifest.txt \
		--f011 $(LEGACY_INTERIM_SHIP_DIR)/f011-manifest.txt \
		--stdlib $(LEGACY_INTERIM_SHIP_DIR)/stdlib-d81-manifest.txt

# Compatibility names for historical reports remain explicit about what they run.
ship-footprint-report: legacy-interim-ship-footprint-report
	@printf 'Hinweis: ship-footprint-report ist historisch; verwende legacy-interim-ship-footprint-report.\n'

full-embed-fit-report: legacy-interim-full-embed-fit-report
	@printf 'Hinweis: full-embed-fit-report ist historisch; verwende legacy-interim-full-embed-fit-report.\n'

ship-readiness-report: legacy-interim-ship-readiness-report
	@printf 'Hinweis: ship-readiness-report ist historisch; verwende legacy-interim-ship-readiness-report.\n'

ship-readiness-check: legacy-interim-ship-readiness-check
	@printf 'Hinweis: ship-readiness-check ist historisch; verwende legacy-interim-ship-readiness-check.\n'

ship-artifacts-check: legacy-interim-ship-artifacts-check
	@printf 'Hinweis: ship-artifacts-check ist historisch; verwende legacy-interim-ship-artifacts-check.\n'

f011-interim-ship:
	SHIP_PRG=$(M65F011SHIPPRG) SHIP_D81=$(M65F011SHIPD81) SHIP_MANIFEST=$(M65F011SHIPMANIFEST) \
		SHIP_WITH_PRELUDE=0 \
		SHIP_HEAP_CELLS=$(M65F011_REPL_HEAP) \
		SHIP_EXTRA_CFLAGS="-DMEGA65_F011_LOAD" \
		sh scripts/build-interim-ship.sh

f011-offline-image: interim-ship
	sh scripts/build-f011-offline-image.sh

f011-defd81-image:
	F011_DEFD81_SDIMG=$(F011_DEFD81_SDIMG) sh scripts/build-f011-defd81-image.sh

f011-load-hw-visible: $(M65F011LOADHWPRG) f011-defd81-image
	@printf 'built %s and %s for manual MEGA65 F011 load testing\n' "$(M65F011LOADHWPRG)" "$(F011_DEFD81_SDIMG)"

stdlib-d81:
	STDLIB_D81=$(STDLIB_D81) STDLIB_CHUNK_DIR=$(STDLIB_CHUNK_DIR) \
		STDLIB_MANIFEST=$(STDLIB_MANIFEST) STDLIB_LOAD_COMMANDS=$(STDLIB_LOAD_COMMANDS) \
		sh scripts/build-stdlib-d81.sh

f011-stdlib-image: stdlib-d81
	F011_DEFD81_SDIMG=$(F011_STDLIB_SDIMG) \
		F011_DEFD81_D81=build/f011/lisp65-stdlib.d81 \
		F011_DEFD81_SOURCE_D81=$(STDLIB_D81) \
		sh scripts/build-f011-defd81-image.sh

f011-autoload-image: $(M65F011LOADTESTPRG)
	F011_AUTOLOAD_SDIMG=$(F011_AUTOLOAD_SDIMG) \
	F011_AUTOLOAD_PRG=$(M65F011LOADTESTPRG) \
		sh scripts/build-f011-autoload-image.sh

f011-stdlib-autoload-image: $(M65F011STDLIBTESTPRG) stdlib-d81
	F011_AUTOLOAD_SDIMG=$(F011_STDLIB_AUTOLOAD_SDIMG) \
		F011_AUTOLOAD_D81=build/f011/lisp65-stdlib-autoload.d81 \
		F011_AUTOLOAD_PRG=$(M65F011STDLIBTESTPRG) \
		F011_AUTOLOAD_EXTRA_DIR=$(STDLIB_CHUNK_DIR) \
		F011_AUTOLOAD_MANIFEST=build/f011/stdlib-autoload-manifest.txt \
		sh scripts/build-f011-autoload-image.sh

f011-stdlib-layer-probe-image: $(M65F011STDLIBLAYERPRG) stdlib-d81
	F011_AUTOLOAD_SDIMG=$(F011_STDLIB_LAYER_PROBE_SDIMG) \
		F011_AUTOLOAD_D81=$(F011_STDLIB_LAYER_PROBE_D81) \
		F011_AUTOLOAD_PRG=$(M65F011STDLIBLAYERPRG) \
		F011_AUTOLOAD_EXTRA_DIR=$(STDLIB_CHUNK_DIR) \
		F011_AUTOLOAD_MANIFEST=build/f011/stdlib-layer-probe-manifest.txt \
		sh scripts/build-f011-autoload-image.sh

f011-stdlib-layer-probe-report: xemu-f011-stdlib-layer-probe
	F011_STDLIB_DUMP=$(F011_STDLIB_LAYER_PROBE_DUMP) sh scripts/ship-footprint-report.sh

f011-stdlib-profile-matrix:
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/f011-stdlib-profile-matrix.sh

f011-check: xemu-f011-load-probe xemu-f011-load-smoke xemu-f011-stdlib-smoke

legacy-interim-ship-check: interim-ship interim-ship-matrix f011-interim-ship f011-offline-image f011-stdlib-image f011-check hw-smoke-interim-dry-run hw-smoke-f011-stdlib-dry-run legacy-interim-ship-footprint-report
	$(MAKE) legacy-interim-full-embed-fit-report
	$(MAKE) f011-stdlib-profile-matrix
	$(MAKE) legacy-interim-ship-artifacts-check
	$(MAKE) legacy-interim-ship-readiness-check

legacy-interim-ship-release: legacy-interim-ship-check
	LEGACY_INTERIM_SHIP_DIR=$(LEGACY_INTERIM_SHIP_DIR) sh scripts/build-ship-release.sh

release ship-release ship-check:
	@printf '%s\n' \
		'Fehler: Es gibt noch keinen aktuellen lisp65-Releasevertrag.' \
		'G3 ist nicht verfuegbar; G3-G5-Evidenz und ein freigegebener Releasevertrag fehlen.' \
		'Aktueller Kandidat: make mvp-ship (g2-verified-candidate, kein Release).' \
		'Historische Referenz: make legacy-interim-ship-release.' >&2
	@exit 2

hw-smoke-vm-stdlib: mvp-ship-artifacts
	sh scripts/hw-smoke-vm-stdlib.sh --no-build

hw-smoke-vm-stdlib-dry-run: mvp-ship-artifacts
	sh scripts/hw-smoke-vm-stdlib.sh --dry-run --no-build

hw-workbench-ux-smoke: mvp-ship-artifacts
	sh scripts/hw-workbench-ux-smoke.sh --no-build

hw-workbench-ux-smoke-dry-run: mvp-ship-artifacts
	sh scripts/hw-workbench-ux-smoke.sh --dry-run --no-build

hw-workbench-bam-read-smoke: mvp-ship-artifacts
	sh scripts/hw-workbench-bam-read-smoke.sh --no-build

hw-workbench-bam-read-smoke-dry-run: mvp-ship-artifacts
	sh scripts/hw-workbench-bam-read-smoke.sh --dry-run --no-build

hw-workbench-bam-alloc-smoke-prg: $(M65HWBAMALLOCPRG)
$(M65HWBAMALLOCPRG): scripts/hw-workbench-bam-alloc-main.c scripts/hw-mega65-hwops.h src/f011_context.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts \
		scripts/hw-workbench-bam-alloc-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-bam-alloc-smoke: mvp-ship-artifacts $(M65HWBAMALLOCPRG)
	sh scripts/hw-workbench-bam-alloc-smoke.sh --no-build

hw-workbench-bam-alloc-smoke-dry-run: mvp-ship-artifacts $(M65HWBAMALLOCPRG)
	sh scripts/hw-workbench-bam-alloc-smoke.sh --dry-run --no-build

hw-workbench-chain-write-smoke-prg: $(M65HWCHAINWRITEPRG)
$(M65HWCHAINWRITEPRG): scripts/hw-workbench-chain-write-main.c $(M3_CHAIN_GEN) scripts/hw-mega65-hwops.h src/f011_context.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts -Ibuild/hw \
		scripts/hw-workbench-chain-write-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-chain-write-smoke: mvp-ship-artifacts $(M65HWCHAINWRITEPRG)
	sh scripts/hw-workbench-chain-write-smoke.sh --no-build

hw-workbench-chain-write-smoke-dry-run: mvp-ship-artifacts $(M65HWCHAINWRITEPRG)
	sh scripts/hw-workbench-chain-write-smoke.sh --dry-run --no-build

hw-workbench-dir-write-smoke-prg: $(M65HWDIRWRITEPRG)
$(M65HWDIRWRITEPRG): scripts/hw-workbench-dir-write-main.c $(M4_DIR_GEN) scripts/hw-mega65-hwops.h src/f011_context.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts -Ibuild/hw \
		scripts/hw-workbench-dir-write-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-dir-write-smoke: mvp-ship-artifacts $(M65HWDIRWRITEPRG)
	sh scripts/hw-workbench-dir-write-smoke.sh --no-build

hw-workbench-dir-write-smoke-dry-run: mvp-ship-artifacts $(M65HWDIRWRITEPRG)
	sh scripts/hw-workbench-dir-write-smoke.sh --dry-run --no-build

hw-workbench-save-new-smoke-prg: $(M65HWSAVENEWPRG)
$(M65HWSAVENEWPRG): scripts/hw-workbench-save-new-main.c $(M5_PAYLOAD_GEN) $(M5_SAVE_NEW_SRCS) src/screen.h | build
	$(CC_M65) -Oz -Wall -DHEAP_CELLS=128 -DMAX_SYM=224 -DNAMEPOOL=6144 -DGC_ROOTS=96 \
		-DLISP65_EXT_HEAP -DEXT_CELLS=2048 -DLISP65_MARK_BITMAP -DLISP65_SCREEN_DRIVER \
		-DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT \
		-DLISP65_VM_STDLIB_IO_WRAPPERS \
		-DLISP65_OUTPUT_WRAPPERS_IN_STDLIB -DLISP65_SCREEN_BULK_P_IN_STDLIB \
		-DMEGA65_F011_LOAD -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DDISK_EXT_FILE_MAX=8192 \
		-Isrc -Iscripts -Ibuild/hw $(M5_SAVE_NEW_SRCS) scripts/hw-workbench-save-new-main.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-save-new-scan-smoke-prg: $(M65HWSAVENEWSCANPRG)
$(M65HWSAVENEWSCANPRG): scripts/hw-workbench-save-new-main.c $(M5_PAYLOAD_GEN) $(M5_SAVE_NEW_SRCS) src/screen.h | build
	$(CC_M65) -Oz -Wall -DHEAP_CELLS=128 -DMAX_SYM=224 -DNAMEPOOL=6144 -DGC_ROOTS=96 \
		-DLISP65_EXT_HEAP -DEXT_CELLS=2048 -DLISP65_MARK_BITMAP -DLISP65_SCREEN_DRIVER \
		-DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT \
		-DLISP65_VM_STDLIB_IO_WRAPPERS \
		-DLISP65_OUTPUT_WRAPPERS_IN_STDLIB -DLISP65_SCREEN_BULK_P_IN_STDLIB \
		-DMEGA65_F011_LOAD -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DDISK_EXT_FILE_MAX=8192 \
		'-DSAVE_NEW_TARGET_NAME="$(WORKBENCH_M6_NAME)"' \
		-Isrc -Iscripts -Ibuild/hw $(M5_SAVE_NEW_SRCS) scripts/hw-workbench-save-new-main.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-save-new-var-smoke-prg: $(M65HWSAVENEWVARPRG)
$(M65HWSAVENEWVARPRG): scripts/hw-workbench-save-new-main.c $(M7_PAYLOAD_GEN) $(M5_SAVE_NEW_SRCS) src/screen.h | build
	$(CC_M65) -Oz -Wall -DHEAP_CELLS=192 -DMAX_SYM=320 -DNAMEPOOL=8192 -DGC_ROOTS=128 \
		-DLISP65_EXT_HEAP -DEXT_CELLS=2048 -DLISP65_MARK_BITMAP -DLISP65_SCREEN_DRIVER \
		-DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT \
		-DLISP65_VM_STDLIB_IO_WRAPPERS \
		-DLISP65_OUTPUT_WRAPPERS_IN_STDLIB -DLISP65_SCREEN_BULK_P_IN_STDLIB \
		-DMEGA65_F011_LOAD -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DDISK_EXT_FILE_MAX=12288 \
		'-DSAVE_NEW_TARGET_NAME="$(WORKBENCH_M7_NAME)"' \
		'-DSAVE_NEW_ALLOC_NAME="$(WORKBENCH_M7_ALLOC_NAME)"' \
		'-DSAVE_NEW_FUNCTION="m65d-save-new"' \
		'-DSAVE_NEW_PAYLOAD_HEADER="m7-var-payload-form.h"' \
		-DSAVE_NEW_PAYLOAD_SRC=m7_payload_src \
		'-DSAVE_NEW_RUN_EXPR="(m7-var-run)"' \
		'-DSAVE_NEW_RUN_NAME="m7-var-run"' \
		-DSAVE_NEW_RUN_EXPECT=907 \
		-Isrc -Iscripts -Ibuild/hw $(M5_SAVE_NEW_SRCS) scripts/hw-workbench-save-new-main.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-workbench-save-new-smoke: mvp-ship-artifacts $(M65HWSAVENEWPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --no-build \
		--name "$(WORKBENCH_M5_NAME)" \
		--first-sector "$(WORKBENCH_M5_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M5_SECOND_SECTOR)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)"

hw-workbench-save-new-smoke-dry-run: mvp-ship-artifacts $(M65HWSAVENEWPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --dry-run --no-build \
		--name "$(WORKBENCH_M5_NAME)" \
		--first-sector "$(WORKBENCH_M5_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M5_SECOND_SECTOR)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)"

hw-workbench-save-new-scan-smoke: mvp-ship-artifacts $(M65HWSAVENEWSCANPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --no-build \
		--remote-d81 L65M6.D81 \
		--before-d81 build/hw/workbench-m6-before.d81 \
		--after-d81 build/hw/workbench-m6-after.d81 \
		--prefix hw-workbench-save-new-scan \
		--name "$(WORKBENCH_M6_NAME)" \
		--first-sector "$(WORKBENCH_M6_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M6_SECOND_SECTOR)" \
		--reserve-sector "$(WORKBENCH_M6_RESERVE_SECTOR)" \
		--prg "$(M65HWSAVENEWSCANPRG)"

hw-workbench-save-new-scan-smoke-dry-run: mvp-ship-artifacts $(M65HWSAVENEWSCANPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --dry-run --no-build \
		--remote-d81 L65M6.D81 \
		--before-d81 build/hw/workbench-m6-before.d81 \
		--after-d81 build/hw/workbench-m6-after.d81 \
		--prefix hw-workbench-save-new-scan \
		--name "$(WORKBENCH_M6_NAME)" \
		--first-sector "$(WORKBENCH_M6_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M6_SECOND_SECTOR)" \
		--reserve-sector "$(WORKBENCH_M6_RESERVE_SECTOR)" \
		--prg "$(M65HWSAVENEWSCANPRG)"

hw-workbench-save-new-var-smoke: mvp-ship-artifacts $(M65HWSAVENEWVARPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --no-build \
		--generic-diff \
		--wait 45 \
		--timeout 40 \
		--remote-d81 L65M7.D81 \
		--before-d81 build/hw/workbench-m7-before.d81 \
		--after-d81 build/hw/workbench-m7-after.d81 \
		--prefix hw-workbench-save-new-var \
		--source "$(M7_VAR_SOURCE)" \
		--alloc-source "$(M7_ALLOC_SOURCE)" \
		--alloc-name "$(WORKBENCH_M7_ALLOC_NAME)" \
		--name "$(WORKBENCH_M7_NAME)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)" \
		--load-ok m7-load-ok \
		--load-fail m7-load-fail \
		--run-form "(m7-var-run)" \
		--run-expect "907" \
		--prg "$(M65HWSAVENEWVARPRG)"

hw-workbench-save-new-var-smoke-dry-run: mvp-ship-artifacts $(M65HWSAVENEWVARPRG)
	sh scripts/hw-workbench-save-new-smoke.sh --dry-run --no-build \
		--generic-diff \
		--wait 45 \
		--timeout 40 \
		--remote-d81 L65M7.D81 \
		--before-d81 build/hw/workbench-m7-before.d81 \
		--after-d81 build/hw/workbench-m7-after.d81 \
		--prefix hw-workbench-save-new-var \
		--source "$(M7_VAR_SOURCE)" \
		--alloc-source "$(M7_ALLOC_SOURCE)" \
		--alloc-name "$(WORKBENCH_M7_ALLOC_NAME)" \
		--name "$(WORKBENCH_M7_NAME)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)" \
		--load-ok m7-load-ok \
		--load-fail m7-load-fail \
		--run-form "(m7-var-run)" \
		--run-expect "907" \
		--prg "$(M65HWSAVENEWVARPRG)"

hw-smoke-vm-stdlib-selftest: mvp-vm-stdlib-hw-selftest
	sh scripts/hw-smoke-vm-stdlib-selftest.sh --no-build

hw-smoke-vm-stdlib-selftest-dry-run: mvp-vm-stdlib-hw-selftest
	sh scripts/hw-smoke-vm-stdlib-selftest.sh --dry-run --no-build

hw-smoke-compile-repl: mvp-vm-stdlib-compile-repl
	sh scripts/hw-smoke-compile-repl.sh --no-build

hw-smoke-compile-repl-dry-run:
	sh scripts/hw-smoke-compile-repl.sh --dry-run --no-build

hw-known-open-diagnostic: mvp-vm-stdlib-known-open-diagnostic
	sh scripts/hw-known-open-diagnostic.sh --no-build

hw-known-open-diagnostic-dry-run: mvp-vm-stdlib-known-open-diagnostic
	sh scripts/hw-known-open-diagnostic.sh --dry-run --no-build

hw-demo-suite:
	sh scripts/hw-demo-suite.sh

hw-demo-suite-dry-run:
	sh scripts/hw-demo-suite.sh --dry-run

hw-access-smoke-prg: $(M65HWACCESSPRG)
$(M65HWACCESSPRG): scripts/hw-access-smoke-main.c scripts/hw-mega65-hwops.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts \
		scripts/hw-access-smoke-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-access-smoke:
	sh scripts/hw-access-smoke.sh

hw-access-smoke-dry-run: $(M65HWACCESSPRG)
	sh scripts/hw-access-smoke.sh --dry-run --no-build

hw-access-smoke-readback: $(M65HWACCESSPRG)
	python3 scripts/hw-opportunity-readback.py access --elf $(M65HWACCESSPRG).elf

hw-access-smoke-readback-dry-run: $(M65HWACCESSPRG)
	python3 scripts/hw-opportunity-readback.py access --elf $(M65HWACCESSPRG).elf --dry-run

hw-color-ram-smoke-prg: $(M65HWCOLORRAMPRG)
$(M65HWCOLORRAMPRG): scripts/hw-color-ram-smoke-main.c scripts/hw-mega65-hwops.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts \
		scripts/hw-color-ram-smoke-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-color-ram-smoke:
	sh scripts/hw-color-ram-smoke.sh

hw-color-ram-smoke-dry-run: $(M65HWCOLORRAMPRG)
	sh scripts/hw-color-ram-smoke.sh --dry-run --no-build

hw-color-ram-smoke-readback: $(M65HWCOLORRAMPRG)
	python3 scripts/hw-opportunity-readback.py color --elf $(M65HWCOLORRAMPRG).elf

hw-color-ram-smoke-readback-dry-run: $(M65HWCOLORRAMPRG)
	python3 scripts/hw-opportunity-readback.py color --elf $(M65HWCOLORRAMPRG).elf --dry-run

hw-edma-screen-smoke-prg: $(M65HWEDMASCREENPRG)
$(M65HWEDMASCREENPRG): scripts/hw-edma-screen-smoke-main.c scripts/hw-mega65-hwops.h src/screen.c src/screen.h | build
	$(CC_M65) $(CFLAGS) -DLISP65_SCREEN_DRIVER -Isrc -Iscripts \
		scripts/hw-edma-screen-smoke-main.c src/screen.c -o $@
	@sz=$$(stat -c%s "$@"); end=$$((0x2001 + $$sz - 2)); \
		printf 'built %s (%s bytes, prg_file_end $$%04x)' "$@" "$$sz" "$$end"; \
		if [ "$$end" -ge $$((0xC000)) ]; then \
			printf ' -- UEBER der etherload-Invariante $$C000, ABBRUCH\n'; exit 3; \
		fi; \
		printf ' (< $$C000 OK)\n'

hw-edma-screen-smoke:
	sh scripts/hw-edma-screen-smoke.sh

hw-edma-screen-smoke-dry-run: $(M65HWEDMASCREENPRG)
	sh scripts/hw-edma-screen-smoke.sh --dry-run --no-build

hw-edma-screen-smoke-readback: $(M65HWEDMASCREENPRG)
	python3 scripts/hw-opportunity-readback.py screen --elf $(M65HWEDMASCREENPRG).elf

hw-edma-screen-smoke-readback-dry-run: $(M65HWEDMASCREENPRG)
	python3 scripts/hw-opportunity-readback.py screen --elf $(M65HWEDMASCREENPRG).elf --dry-run

hw-stress-full:
	sh scripts/hw-stress-full.sh

hw-stress-full-dry-run:
	sh scripts/hw-stress-full.sh --dry-run --no-build

hw-stress-dmaprof:
	sh scripts/hw-stress-full.sh --dma-prof

hw-stress-dmaprof-dry-run:
	sh scripts/hw-stress-full.sh --dma-prof --dry-run --no-build

hw-stress-deep:
	sh scripts/hw-stress-full.sh --deep 1
	sh scripts/hw-stress-full.sh --deep 2

hw-stress-deep-dry-run:
	sh scripts/hw-stress-full.sh --deep 1 --dry-run --no-build
	sh scripts/hw-stress-full.sh --deep 2 --dry-run --no-build

hw-stress-deep1:
	sh scripts/hw-stress-full.sh --deep 1

hw-stress-deep1-dry-run:
	sh scripts/hw-stress-full.sh --deep 1 --dry-run --no-build

hw-stress-deep2:
	sh scripts/hw-stress-full.sh --deep 2

hw-stress-deep2-dry-run:
	sh scripts/hw-stress-full.sh --deep 2 --dry-run --no-build

hw-stress-redeploy:
	sh scripts/hw-stress-redeploy.sh

hw-stress-redeploy-dry-run:
	sh scripts/hw-stress-redeploy.sh --dry-run

hw-stress-redeploy-deep:
	sh scripts/hw-stress-redeploy.sh --deep 1
	sh scripts/hw-stress-redeploy.sh --deep 2

hw-stress-redeploy-deep-dry-run:
	sh scripts/hw-stress-redeploy.sh --deep 1 --dry-run
	sh scripts/hw-stress-redeploy.sh --deep 2 --dry-run

hw-smoke-interim:
	sh scripts/hw-smoke-interim.sh

hw-smoke-interim-dry-run:
	sh scripts/hw-smoke-interim.sh --dry-run --no-build

hw-smoke-f011-stdlib: f011-interim-ship stdlib-d81
	sh scripts/hw-smoke-interim.sh --f011-stdlib --no-build

hw-smoke-f011-stdlib-dry-run: f011-interim-ship stdlib-d81
	sh scripts/hw-smoke-interim.sh --f011-stdlib --dry-run --no-build

hyppo-probe-matrix: | build
	sh scripts/build-hyppo-probe-matrix.sh

$(C64PRELUDETESTPRG): $(RUNTIME_SRCS) scripts/prelude-smoke-main.c $(PRELUDE_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE -Isrc \
		$(RUNTIME_SRCS) scripts/prelude-smoke-main.c -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

$(C64PRELUDEGCTESTPRG): $(RUNTIME_SRCS) scripts/prelude-gc-stress-main.c $(PRELUDE_GEN) FORCE | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(PRELUDE_GC_HEAP) $(PRELUDE_GC_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/prelude-gc-stress-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(PRELUDE_GC_HEAP)"

$(M65PRELUDEGCTESTPRG): $(RUNTIME_SRCS) scripts/prelude-gc-stress-main.c $(PRELUDE_GEN) FORCE | build
	$(CC_M65) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(M65PRELUDE_GC_HEAP) $(M65PRELUDE_GC_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/prelude-gc-stress-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65PRELUDE_GC_HEAP)"

$(C64LOADSOURCETESTPRG): $(RUNTIME_SRCS) scripts/load-source-smoke-main.c $(PRELUDE_GEN) $(LOAD_SMOKE_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE -Isrc \
		$(RUNTIME_SRCS) scripts/load-source-smoke-main.c -o $@
	@printf 'built %s (%s bytes)\n' "$@" "$$(stat -c%s $@)"

$(C64STRINGTESTPRG): $(RUNTIME_SRCS) scripts/string-smoke-main.c $(PRELUDE_GEN) $(STDLIB_STRINGS_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(C64STRING_HEAP) $(C64STRING_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/string-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(C64STRING_HEAP)"

$(C64STDLIBTESTPRG): $(RUNTIME_SRCS) scripts/stdlib-smoke-main.c $(PRELUDE_GEN) $(STDLIB_SEQUENCES_GEN) $(STDLIB_MATH_GEN) $(STDLIB_PLISTS_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(C64STDLIB_HEAP) $(C64STDLIB_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/stdlib-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(C64STDLIB_HEAP)"

$(M65F011LOADTESTPRG): $(RUNTIME_SRCS) scripts/f011-load-smoke-main.c | build
	$(CC_M65) $(M65F011_CFLAGS) -DLISP65_XEMU_TEST \
		-DMEGA65_F011_LOAD -DIO_BUF_MAX=$(M65F011_SMOKE_IO_BUF) \
		-DHEAP_CELLS=$(M65F011_SMOKE_HEAP) \
		$(M65F011_LOAD_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/f011-load-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65F011_SMOKE_HEAP)"

$(M65F011LOADHWPRG): $(RUNTIME_SRCS) scripts/f011-load-smoke-main.c | build
	$(CC_M65) $(M65F011_CFLAGS) \
		-DMEGA65_F011_LOAD -DLISP65_F011_HW_HOLD -DIO_BUF_MAX=$(M65F011_SMOKE_IO_BUF) \
		-DHEAP_CELLS=$(M65F011_SMOKE_HEAP) \
		$(M65F011_LOAD_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/f011-load-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65F011_SMOKE_HEAP)"

$(M65F011STDLIBTESTPRG): $(RUNTIME_SRCS) scripts/f011-stdlib-smoke-main.c stdlib-d81 | build
	chunk_count=$$(awk '/^L[0-9][0-9] / { n++ } END { print n + 0 }' $(STDLIB_CHUNK_MANIFEST)); \
	test "$$chunk_count" -gt 0; \
	$(CC_M65) $(M65F011_CFLAGS) -DLISP65_XEMU_TEST \
		-DMEGA65_F011_LOAD -DIO_BUF_MAX=$(M65F011_STDLIB_SMOKE_IO_BUF) \
		-DHEAP_CELLS=$(M65F011_STDLIB_SMOKE_HEAP) \
		-DF011_STDLIB_CHUNKS=$$chunk_count \
		$(M65F011_LOAD_EXTRA_CFLAGS) $(M65F011_STDLIB_SMOKE_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/f011-stdlib-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65F011_STDLIB_SMOKE_HEAP)"

$(M65F011STDLIBLAYERPRG): $(RUNTIME_SRCS) scripts/f011-stdlib-smoke-main.c stdlib-d81 FORCE | build
	chunk_count=$$(awk '/^L[0-9][0-9] / { n++ } END { print n + 0 }' $(STDLIB_CHUNK_MANIFEST)); \
	test "$$chunk_count" -gt 0; \
	$(CC_M65) $(M65F011_CFLAGS) -DLISP65_XEMU_TEST \
		-DMEGA65_F011_LOAD -DIO_BUF_MAX=$(M65F011_STDLIB_SMOKE_IO_BUF) \
		-DHEAP_CELLS=$(M65F011_STDLIB_LAYER_PROBE_HEAP) \
		-DF011_STDLIB_CHUNKS=$$chunk_count \
		-DF011_STDLIB_LAYER_PROBE \
		$(M65F011_LOAD_EXTRA_CFLAGS) $(M65F011_STDLIB_LAYER_PROBE_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/f011-stdlib-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(M65F011_STDLIB_LAYER_PROBE_HEAP)"

$(C64FORMATTESTPRG): $(RUNTIME_SRCS) scripts/format-smoke-main.c $(PRELUDE_GEN) $(STDLIB_FORMAT_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(C64FORMAT_HEAP) $(C64FORMAT_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/format-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(C64FORMAT_HEAP)"

$(C64CONTROLTESTPRG): $(RUNTIME_SRCS) scripts/control-smoke-main.c $(PRELUDE_GEN) $(STDLIB_CONTROL_GEN) | build
	$(LEGACY_CC_C64) $(CFLAGS) -DLISP65_XEMU_TEST -DLISP65_WITH_PRELUDE \
		-DHEAP_CELLS=$(C64CONTROL_HEAP) $(C64CONTROL_EXTRA_CFLAGS) -Isrc \
		$(RUNTIME_SRCS) scripts/control-smoke-main.c -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s)\n' "$@" "$$(stat -c%s $@)" "$(C64CONTROL_HEAP)"

FORCE:

run: $(M65PRG)
	$(ETHERLOAD) -5 -r $(M65PRG)

legacy-run-c64: $(C64PRG)
	$(ETHERLOAD) -4 -r $(C64PRG)

run-mvp-vm-stdlib: $(M65VMSTDLIBPRG)
	$(ETHERLOAD) --halt -b 0x050000 $(BYTECODE_STDLIB_BLOB)
	$(ETHERLOAD) -5 -r $(M65VMSTDLIBPRG)

include mk/workbench-service-inventory.mk
include mk/gates.mk

.PHONY: dialect-v2-lcc-surface-selftest dialect-v2-lcc-surface-check

host-oracle:
	sh tools/host-lisp/run-mvp-tests.sh

legacy-lisp64-oracle:
	python3 tools/host-lisp/lisp64.py salvage/lisp/prelude.lsp salvage/lisp/conformance.lsp

xmega65-safety-check:
	python3 scripts/check-xmega65-safe-run.py --selftest
	python3 scripts/check-xmega65-safe-run.py

fixed-point-check:
	python3 tools/host-lisp/stdlib_fixed_eval_oracle.py
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_FIXED_SUITE)

post-mvp-stdlib-polish-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_STRING_POLISH_SUITE)

eval-bytecode-equivalence-check:
	python3 tools/host-lisp/eval_bytecode_equivalence.py $(BYTECODE_EQUIV_SUITES)

$(EQUIVALENCE_HOST): scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -Isrc \
		scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c \
		src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c \
		src/printer.c src/io.c src/interrupt.c src/screen.c -o $@

$(DIALECT_V2_EQUIVALENCE_HOST): scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c $(DIALECT_EQUIVALENCE_HEADERS) | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL -DLISP65_DIALECT_V2 \
		-DLISP65_STRING_ARENA -DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS \
		-DLISP65_DIALECT_FAMILY_HARNESS -DLISP65_NUMERIC_ERRORS \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -Isrc \
		scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c \
		src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c \
		src/printer.c src/io.c src/interrupt.c src/screen.c -o $@

$(DIALECT_V1_SOURCE_MANIFEST): config/dialect-migration-contract.json tools/host-lisp/dialect_v1_source_export.py
	python3 tools/host-lisp/dialect_v1_source_export.py --output $(DIALECT_V1_SOURCE_ROOT)

$(DIALECT_V1_EQUIVALENCE_HOST): $(DIALECT_V1_SOURCE_MANIFEST) scripts/equivalence-main.c Makefile | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
		-DLISP65_DIALECT_FAMILY_HARNESS -DLISP65_FROZEN_V1_HARNESS -DLISP65_NUMERIC_ERRORS \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -I$(DIALECT_V1_SOURCE_ROOT)/src \
		scripts/equivalence-main.c \
		$(addprefix $(DIALECT_V1_SOURCE_ROOT)/src/,$(DIALECT_EQUIVALENCE_SOURCE_NAMES)) -o $@

$(DIALECT_V1_EQUIVALENCE_BUILD): $(DIALECT_V1_EQUIVALENCE_HOST) Makefile tools/host-lisp/dialect_v2_prelude_control.py
	python3 tools/host-lisp/dialect_v2_prelude_control.py record-build \
		--profile dialect-v1 --binary $(DIALECT_V1_EQUIVALENCE_HOST) \
		--compiler "$(HOSTCC)" --source-root $(DIALECT_V1_SOURCE_ROOT) \
		--source-commit f6527d25e2035eae5a98dae7431d641515e2fd2e --output $@

$(DIALECT_V2_EQUIVALENCE_BUILD): $(DIALECT_V2_EQUIVALENCE_HOST) Makefile lib/dialect-v2/prelude-control.lisp tools/host-lisp/dialect_v2_prelude_control.py
	python3 tools/host-lisp/dialect_v2_prelude_control.py record-build \
		--profile dialect-v2 --binary $(DIALECT_V2_EQUIVALENCE_HOST) \
		--compiler "$(HOSTCC)" --source-root . --output $@

semantic-contracts-g1: $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)

dialect-v2-prelude-control-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_PRELUDE_FIXTURE) selftest

dialect-v2-prelude-control-check: dialect-v2-prelude-control-selftest
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_PRELUDE_FIXTURE) check

dialect-v2-prelude-control-matrix: dialect-v2-prelude-control-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_PRELUDE_FIXTURE) run \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/prelude-control

dialect-v2-eval-apply-funcall-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_EVAL_APPLY_FUNCALL_FIXTURE) selftest

dialect-v2-eval-apply-funcall-check: dialect-v2-eval-apply-funcall-selftest
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_EVAL_APPLY_FUNCALL_FIXTURE) check

dialect-v2-eval-apply-funcall-matrix: dialect-v2-eval-apply-funcall-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_EVAL_APPLY_FUNCALL_FIXTURE) run \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/eval-apply-funcall

dialect-v2-lists-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_LISTS_FIXTURE) selftest

dialect-v2-lists-check: dialect-v2-lists-selftest
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_LISTS_FIXTURE) check

dialect-v2-lists-native-matrix: dialect-v2-lists-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_LISTS_FIXTURE) run \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/lists

dialect-v2-lists-p0-selftest: $(DIALECT_V1_SOURCE_MANIFEST)
	python3 tools/host-lisp/dialect_v2_lists_p0.py --selftest

dialect-v2-lists-p0-check: dialect-v2-lists-p0-selftest $(DIALECT_V2_LISTS_FIXTURE) lib/dialect-v2/lists-core.lisp lib/dialect-v2/lists-library.lisp
	python3 tools/host-lisp/dialect_v2_lists_p0.py --fixture $(DIALECT_V2_LISTS_FIXTURE) \
		--output-dir build/bytecode/dialect-v2/lists

dialect-v2-lists-lcc-selftest:
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --lists --selftest

dialect-v2-lists-lcc-check: dialect-v2-lists-lcc-selftest $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --lists \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--lists-output-dir build/bytecode/dialect-v2/lists

dialect-v2-lists-matrix: dialect-v2-lists-native-matrix dialect-v2-lists-p0-check dialect-v2-lists-lcc-check

dialect-v2-lists-type-errors-check:
	python3 tools/host-lisp/dialect_v2_lists_type_errors.py check

dialect-v2-system-runtime-check: $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_system_runtime.py check

dialect-v2-strings-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) selftest

dialect-v2-strings-check: dialect-v2-strings-selftest
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) check

dialect-v2-strings-native-matrix: dialect-v2-strings-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) run \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-native-stage3-matrix: dialect-v2-strings-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) run \
		--stage3-carrier-active \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-compiler-matrix: dialect-v2-strings-check $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_prelude_control.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) run \
		--engine native-c-compiler-vm \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-p0-selftest:
	python3 tools/host-lisp/dialect_v2_strings_p0.py --selftest

dialect-v2-strings-p0-check: dialect-v2-strings-p0-selftest $(DIALECT_V2_STRINGS_FIXTURE) lib/dialect-v2/strings-core.lisp
	python3 tools/host-lisp/dialect_v2_strings_p0.py --fixture $(DIALECT_V2_STRINGS_FIXTURE) \
		--output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-lcc-selftest:
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --strings --selftest

dialect-v2-strings-lcc-check: dialect-v2-strings-lcc-selftest $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --strings \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--strings-output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-lcc-stage3-check: dialect-v2-strings-lcc-selftest $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --strings --stage3-carrier-active \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) --binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--build-receipt-v1 $(DIALECT_V1_EQUIVALENCE_BUILD) --build-receipt-v2 $(DIALECT_V2_EQUIVALENCE_BUILD) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 . \
		--strings-output-dir build/bytecode/dialect-v2/strings

dialect-v2-strings-matrix: dialect-v2-strings-native-matrix dialect-v2-strings-p0-check dialect-v2-strings-lcc-check

v2-string-codec-workload-selftest: v2-workbench-codemod
	python3 tools/host-lisp/v2_string_codec_workloads.py selftest

v2-string-codec-workload-check: v2-string-codec-workload-selftest
	python3 tools/host-lisp/v2_string_codec_workloads.py check

v2-prim-lowering-check:
	python3 tools/host-lisp/v2_prim_lowering.py

v2-native-function-registry-check: $(V2_NATIVE_FUNCTION_REGISTRY) src/v2_native_function_dispatch.h $(V2_NATIVE_FUNCTION_VIEWS) $(V2_NATIVE_FUNCTION_FIXTURE) $(V2_NATIVE_FUNCTION_PARITY)
	python3 tools/host-lisp/v2_native_function_registry.py check

$(V2_NATIVE_FUNCTION_HOST): scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c $(DIALECT_EQUIVALENCE_HEADERS) | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL -DLISP65_DIALECT_V2 \
		-DLISP65_STRING_ARENA -DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS \
		-DLISP65_V2_WORKBENCH_SERVICES -DLISP65_DIALECT_FAMILY_HARNESS -DLISP65_NUMERIC_ERRORS \
		-DLISP65_V2_TREE_PRIMITIVE_VIEW \
		-DLISP65_EVAL_SCREEN_PRIMS -DLISP65_SCREEN_WRITE_STRING -DLISP65_VM_SCREEN_PRIMS \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -Isrc \
		scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c \
		src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c \
		src/printer.c src/io.c src/interrupt.c src/screen.c -o $@

v2-native-function-matrix-check: v2-native-function-registry-check $(V2_NATIVE_FUNCTION_HOST) $(V2_NATIVE_FUNCTION_RECEIPT)
	python3 tools/host-lisp/v2_native_function_matrix.py check --binary $(V2_NATIVE_FUNCTION_HOST)

v2-carrier-state-selftest:
	python3 tools/host-lisp/v2_carrier_state.py --selftest

v2-carrier-state-active: v2-carrier-state-selftest
	python3 tools/host-lisp/v2_carrier_state.py --expect active

v2-carrier-cut-host-check: v2-carrier-state-selftest
	sh scripts/v2-carrier-cut-check.sh

v2-carrier-state-removed: v2-carrier-cut-host-check

dialect-v2-lcc-compile-error-selftest:
	python3 tools/host-lisp/dialect_v2_lcc_compile_error.py --selftest

dialect-v2-lcc-compile-error-check: dialect-v2-lcc-compile-error-selftest $(DIALECT_V2_EQUIVALENCE_BUILD) workbench-service-call-inventory-staging
	python3 tools/host-lisp/dialect_v2_lcc_compile_error.py \
		--binary $(DIALECT_V2_EQUIVALENCE_HOST) \
		--output $(V2_LCC_COMPILE_ERROR_RECEIPT)

dialect-v2-lists-evidence-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family lists selftest

dialect-v2-lists-evidence-build: dialect-v2-lists-matrix dialect-v2-lists-evidence-selftest
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family lists generate

dialect-v2-lists-evidence-check: dialect-v2-lists-evidence-build
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family lists check

dialect-v2-strings-evidence-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family strings selftest

dialect-v2-strings-evidence-build: dialect-v2-strings-matrix dialect-v2-strings-evidence-selftest
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family strings generate

dialect-v2-strings-evidence-check: dialect-v2-strings-evidence-build
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family strings check

dialect-v2-system-runtime-evidence-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family system-runtime selftest

dialect-v2-system-runtime-evidence-build: dialect-v2-system-runtime-check dialect-v2-system-runtime-evidence-selftest
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family system-runtime generate

dialect-v2-system-runtime-evidence-check: dialect-v2-system-runtime-evidence-build
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py --family system-runtime check

dialect-v2-ide-evidence-check:
	python3 tools/host-lisp/dialect_v2_ide_evidence.py check

dialect-v2-capacity-ledger-selftest:
	python3 tools/host-lisp/dialect_v2_capacity_ledger.py selftest

dialect-v2-capacity-ledger-check: dialect-v2-capacity-ledger-selftest
	python3 tools/host-lisp/dialect_v2_capacity_ledger.py check \
		--ledger $(DIALECT_V2_CAPACITY_LEDGER) \
		--json-out $(DIALECT_V2_CAPACITY_REPORT)

block-bank-delta-policy-selftest:
	python3 tools/host-lisp/block_bank_delta_policy.py selftest

block-bank-delta-policy-check: block-bank-delta-policy-selftest
	python3 tools/host-lisp/block_bank_delta_policy.py check

block-capacity-delta-policy-selftest:
	python3 tools/host-lisp/block_capacity_delta_policy.py selftest

block-capacity-delta-policy-check: block-capacity-delta-policy-selftest
	python3 tools/host-lisp/block_capacity_delta_policy.py check

r2-known-open-selftest: block-bank-delta-policy-check
	python3 tools/host-lisp/r2_known_open.py selftest

r2-known-open-check: r2-known-open-selftest
	python3 tools/host-lisp/r2_known_open.py check

directory-only-l65m-v2-probe-selftest:
	python3 tools/host-lisp/directory_only_l65m_v2_probe.py selftest

directory-only-l65m-v2-probe-check: directory-only-l65m-v2-probe-selftest
	python3 tools/host-lisp/directory_only_l65m_v2_probe.py check

v2-capability-carrier-contract-selftest:
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) \
		--fixture $(V2_CAPABILITY_CARRIER_FIXTURE) selftest

v2-capability-carrier-contract-check: v2-capability-carrier-contract-selftest
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) check

v2-capability-carrier-internal-g5-selftest:
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract $(V2_CAPABILITY_CARRIER_G5_CONTRACT) selftest

v2-capability-carrier-internal-g5-check: v2-capability-carrier-internal-g5-selftest
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract $(V2_CAPABILITY_CARRIER_G5_CONTRACT) check

v2-cp5-g5-archive-check:
	python3 tools/host-lisp/v2_cp5_g5_archive.py selftest
	python3 tools/host-lisp/v2_cp5_g5_archive.py check

v2-capability-carrier-internal-g5-runtime-package: v2-runtime-core-proof-candidate
	rm -rf '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)'
	python3 tools/host-lisp/v2_g5_domain_verifiers.py pack-runtime \
		--proof-dir '$(V2_RUNTIME_CORE_PROOF_CANDIDATE)' \
		--out '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)' \
		--nm '$(M65VMSTDLIB_NM)' --objcopy '$(WORKBENCH_OVERLAY_OBJCOPY)'
	python3 tools/host-lisp/v2_g5_domain_verifiers.py verify-runtime-package \
		--package '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)'

v2-capability-carrier-internal-g5-workbench-link: v2-workbench-artifacts
	$(MAKE) --no-print-directory \
		WORKBENCH_PROFILE_ID=dialect-v2-capability-carrier-workbench-staging \
		WORKBENCH_SUITE=build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json \
		WORKBENCH_BYTECODE_DIR=build/bytecode/dialect-v2/workbench \
		WORKBENCH_OVERLAY_GUARD_DIR='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)' \
		WORKBENCH_OVERLAY_GUARD_DEFINES='-DLISP65_STACK_GUARD $(V2_CAPABILITY_CARRIER_G5_V2_DEFINES)' \
		workbench-overlay-stack-guard

v2-capability-carrier-internal-g5-d81: v2-workbench-artifacts
	mkdir -p '$(V2_CAPABILITY_CARRIER_G5_DIR)'
	WORKBENCH_SHIP_D81='$(V2_CAPABILITY_CARRIER_G5_D81)' \
		WORKBENCH_SHIP_D81_MANIFEST='$(V2_CAPABILITY_CARRIER_G5_DIR)/workbench-d81-manifest.txt' \
		WORKBENCH_SHIP_IDE_LIB=build/bytecode/dialect-v2/libs/ide.ext.bin \
		WORKBENCH_SHIP_IDEX_LIB=build/bytecode/dialect-v2/libs/idex.ext.bin \
		WORKBENCH_SHIP_M65D_LIB=build/bytecode/dialect-v2/libs/m65d.ext.bin \
		sh scripts/build-workbench-d81.sh

v2-capability-carrier-internal-g5-candidate: \
	v2-capability-carrier-internal-g5-check \
	v2-capability-carrier-internal-g5-runtime-package \
	v2-capability-carrier-internal-g5-workbench-link \
	v2-capability-carrier-internal-g5-d81 \
	hw-workbench-bam-alloc-smoke-prg hw-workbench-chain-write-smoke-prg \
	hw-workbench-dir-write-smoke-prg hw-workbench-save-new-smoke-prg \
	hw-workbench-save-new-scan-smoke-prg hw-workbench-save-new-var-smoke-prg
	@git diff --quiet && git diff --cached --quiet || { \
		printf '%s\n' 'G5 candidate requires a committed source/verifier state' >&2; exit 2; }
	rm -f '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)'
	@set -eu; \
		build_id=$$(python3 -c 'import json; print(json.load(open("$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/runtime-overlays-manifest.json"))["profile_build_id"])'); \
		python3 tools/host-lisp/v2_capability_carrier_g5.py \
			--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' pack-candidate \
			--build-id "$$build_id" --source-commit "$$(git rev-parse HEAD)" \
			--artifact product-link-budget-report=tests/bytecode/dialect-v2/evidence/capability-carrier/string-caps-cp5-product-link-report.json \
			--artifact g5-domain-verifier=tools/host-lisp/v2_g5_domain_verifiers.py \
			--artifact runtime-hardware-verifier=tools/host-lisp/runtime_export_hw_oracle.py \
			--artifact runtime-preload-verifier=tools/host-lisp/runtime_export_preload.py \
			--artifact runtime-ship-verifier=tools/host-lisp/runtime_export_ship.py \
			--artifact runtime-core-audit='$(V2_RUNTIME_CORE_PROOF_CANDIDATE)/audit.txt' \
			--artifact runtime-core-elf='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/runtime.prg.elf' \
			--artifact runtime-core-footprint='$(V2_RUNTIME_CORE_PROOF_CANDIDATE)/footprint.txt' \
			--artifact runtime-core-preload='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/runtime-preload.bin' \
			--artifact runtime-core-prg='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/runtime.prg' \
			--artifact runtime-hw-manifest='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/manifest.json' \
			--artifact runtime-hw-oracle='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/hardware-oracle.json' \
			--artifact runtime-stage-clean='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/stage-clean.bin' \
			--artifact runtime-stage-truncated='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/stage-truncated.bin' \
			--artifact runtime-effective-truncated='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/effective-truncated.bin' \
			--artifact runtime-clear-truncated='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/clear-truncated.bin' \
			--artifact runtime-stage-bitflip='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/stage-bitflip.bin' \
			--artifact runtime-stage-build-id-mismatch='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/stage-build-id-mismatch.bin' \
			--artifact runtime-foreign-profile='$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/foreign-profile.txt' \
			--artifact workbench-attic-catalog='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/lisp65-mvp-workbench.overlays.bin' \
			--artifact workbench-d81='$(V2_CAPABILITY_CARRIER_G5_D81)' \
			--artifact workbench-elf='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/lisp65-workbench-overlay-linked.prg.elf' \
			--artifact workbench-footprint='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/footprint-audit.json' \
			--artifact workbench-preload='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/stdlib-with-overlay.ext.bin' \
			--artifact workbench-prg='$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/lisp65-workbench-resident.prg' \
			--artifact persistence-bam-alloc-prg='$(M65HWBAMALLOCPRG)' \
			--artifact persistence-chain-write-prg='$(M65HWCHAINWRITEPRG)' \
			--artifact persistence-dir-write-prg='$(M65HWDIRWRITEPRG)' \
			--artifact persistence-save-new-prg='$(M65HWSAVENEWPRG)' \
			--artifact persistence-save-new-scan-prg='$(M65HWSAVENEWSCANPRG)' \
			--artifact persistence-save-new-var-prg='$(M65HWSAVENEWVARPRG)' \
			--out '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)'
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' verify-candidate \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)'

v2-capability-carrier-internal-g5-plan: v2-capability-carrier-internal-g5-candidate
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' plan \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--out '$(V2_CAPABILITY_CARRIER_G5_PLAN)'

v2-capability-carrier-internal-g5-hw-package: v2-capability-carrier-internal-g5-plan
	rm -rf '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)'
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' pack-hw \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--runtime-overlays-manifest '$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR)/runtime-overlays-manifest.json' \
		--out '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)'
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' verify-hw \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--package '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)'

.PHONY: v2-capability-carrier-internal-g5-ready
v2-capability-carrier-internal-g5-ready:
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' verify-candidate \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)'
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' verify-hw \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--package '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)'
	python3 tools/host-lisp/v2_g5_domain_verifiers.py verify-runtime-package \
		--package '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)'

.PHONY: v2-capability-carrier-internal-g5-preflight v2-capability-carrier-internal-g5-preflight-ready
v2-capability-carrier-internal-g5-preflight: v2-capability-carrier-internal-g5-ready
	@mkdir -p '$(dir $(V2_CAPABILITY_CARRIER_G5_PREFLIGHT))'
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' preflight \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--hw-package '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)' \
		--runtime-package '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)' \
		--out '$(V2_CAPABILITY_CARRIER_G5_PREFLIGHT)'

v2-capability-carrier-internal-g5-preflight-ready: v2-capability-carrier-internal-g5-ready
	python3 tools/host-lisp/v2_capability_carrier_g5.py \
		--contract '$(V2_CAPABILITY_CARRIER_G5_CONTRACT)' verify-preflight \
		--manifest '$(V2_CAPABILITY_CARRIER_G5_CANDIDATE)' \
		--hw-package '$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)' \
		--runtime-package '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)' \
		--receipt '$(V2_CAPABILITY_CARRIER_G5_PREFLIGHT)'

.PHONY: v2-capability-carrier-g5-workbench-overlay-stack-guard \
	v2-capability-carrier-g5-workbench-stdlib-runtime \
	v2-capability-carrier-g5-workbench-ux-complete \
	v2-capability-carrier-g5-workbench-bam-read \
	v2-capability-carrier-g5-workbench-bam-alloc \
	v2-capability-carrier-g5-workbench-chain-write \
	v2-capability-carrier-g5-workbench-dir-write \
	v2-capability-carrier-g5-workbench-save-new \
	v2-capability-carrier-g5-workbench-save-new-scan \
	v2-capability-carrier-g5-workbench-save-new-var

v2-capability-carrier-g5-workbench-overlay-stack-guard: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-overlay-stack-guard' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	WORKBENCH_OVERLAY_RESIDENT_PRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.prg' \
		WORKBENCH_OVERLAY_PRELOAD='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.blob.bin' \
		WORKBENCH_RUNTIME_OVERLAY='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.overlays.bin' \
		WORKBENCH_OVERLAY_ELF='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-workbench-overlay-linked.prg.elf' \
		WORKBENCH_OVERLAY_D81='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/lisp65-mvp-workbench.d81' \
		WORKBENCH_SHIP_MANIFEST='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/manifest.json' \
		OUT_DIR='$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-overlay-stack-guard' \
		PREFIX=v2-g5-overlay-stack-guard \
		sh scripts/hw-workbench-overlay-stack-smoke.sh --no-readback

v2-capability-carrier-g5-workbench-stdlib-runtime: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-stdlib-runtime' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	mkdir -p '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-stdlib-runtime'
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		sh scripts/hw-smoke-vm-stdlib.sh --no-build --remote-d81 L65G5S.D81
	sleep 3
	scripts/hw-jtag-repl.sh --form '(+ 20 22)' --expect 42 --verified-input \
		--prefix v2-g5-stdlib-runtime --out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-stdlib-runtime'

v2-capability-carrier-g5-workbench-ux-complete: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-ux-complete' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		OUT_DIR='$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-ux-complete' PREFIX=v2-g5-ux \
		sh scripts/hw-workbench-ux-smoke.sh --no-build --remote-d81 L65G5U.D81

v2-capability-carrier-g5-workbench-bam-read: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-read' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		OUT_DIR='$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-read' PREFIX=v2-g5-bam-read \
		sh scripts/hw-workbench-bam-read-smoke.sh --no-build --remote-d81 L65G5R.D81

v2-capability-carrier-g5-workbench-bam-alloc: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-alloc' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWBAMALLOCPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-bam-alloc.prg' \
		sh scripts/hw-workbench-bam-alloc-smoke.sh --no-build --remote-d81 L65G5A.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-alloc' --prefix v2-g5-bam-alloc \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-alloc/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-bam-alloc/after.d81'

v2-capability-carrier-g5-workbench-chain-write: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-chain-write' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWCHAINWRITEPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-chain-write.prg' \
		sh scripts/hw-workbench-chain-write-smoke.sh --no-build --remote-d81 L65G5C.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-chain-write' --prefix v2-g5-chain-write \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-chain-write/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-chain-write/after.d81'

v2-capability-carrier-g5-workbench-dir-write: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-dir-write' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWDIRWRITEPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-dir-write.prg' \
		sh scripts/hw-workbench-dir-write-smoke.sh --no-build --remote-d81 L65G5D.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-dir-write' --prefix v2-g5-dir-write \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-dir-write/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-dir-write/after.d81'

v2-capability-carrier-g5-workbench-save-new: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWSAVENEWPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-save-new.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --remote-d81 L65G5N.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new' --prefix v2-g5-save-new \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new/after.d81'

v2-capability-carrier-g5-workbench-save-new-scan: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-scan' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWSAVENEWPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-save-new-scan.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --remote-d81 L65G56.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-scan' --prefix v2-g5-save-new-scan \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-scan/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-scan/after.d81' \
		--name m6src --first-sector 27 --second-sector 28 --reserve-sector 26

v2-capability-carrier-g5-workbench-save-new-var: v2-capability-carrier-internal-g5-preflight-ready
	@test ! -e '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-var' || { echo 'G5 evidence directory must be fresh' >&2; exit 2; }
	$(V2_CAPABILITY_CARRIER_G5_WORKBENCH_ENV) \
		M65HWSAVENEWPRG='$(V2_CAPABILITY_CARRIER_G5_HW_PACKAGE)/persistence-save-new-var.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --generic-diff --wait 45 --timeout 40 \
		--remote-d81 L65G57.D81 \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-var' --prefix v2-g5-save-new-var \
		--before-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-var/before.d81' \
		--after-d81 '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/workbench-save-new-var/after.d81' \
		--source tests/disk/m7-var-source.lisp --alloc-source lib/m65-disk-alloc-var.lisp \
		--alloc-name m7alloc --name m7src --load-ok m7-load-ok --load-fail m7-load-fail \
		--run-form '(m7-var-run)' --run-expect 907

V2_CAPABILITY_CARRIER_G5_POWER_CYCLE_TOKEN ?=
V2_CAPABILITY_CARRIER_G5_CYCLE_ID ?=

.PHONY: v2-capability-carrier-g5-runtime-clean \
	v2-capability-carrier-g5-runtime-truncated \
	v2-capability-carrier-g5-runtime-bitflip \
	v2-capability-carrier-g5-runtime-build-id-mismatch

define V2_CAPABILITY_CARRIER_G5_RUNTIME_PHASE_TARGET
v2-capability-carrier-g5-runtime-$(1): v2-capability-carrier-internal-g5-preflight-ready
	@test '$(V2_CAPABILITY_CARRIER_G5_POWER_CYCLE_TOKEN)' = POWER-CYCLED || \
		{ printf '%s\n' 'Set V2_CAPABILITY_CARRIER_G5_POWER_CYCLE_TOKEN=POWER-CYCLED only after a physical power-cycle.' >&2; exit 2; }
	@test -n '$(V2_CAPABILITY_CARRIER_G5_CYCLE_ID)' || \
		{ printf '%s\n' 'Set a fresh V2_CAPABILITY_CARRIER_G5_CYCLE_ID for this physical power-cycle.' >&2; exit 2; }
	python3 tools/host-lisp/runtime_export_hw_oracle.py deploy \
		--gate G5 --phase '$(1)' \
		--package '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)' \
		--oracle '$(V2_CAPABILITY_CARRIER_G5_RUNTIME)/hardware-oracle.json' \
		--out-dir '$(V2_CAPABILITY_CARRIER_G5_EVIDENCE)/runtime-$(1)' \
		--power-cycle-token '$(V2_CAPABILITY_CARRIER_G5_POWER_CYCLE_TOKEN)' \
		--cycle-id '$(V2_CAPABILITY_CARRIER_G5_CYCLE_ID)'
endef

$(eval $(call V2_CAPABILITY_CARRIER_G5_RUNTIME_PHASE_TARGET,clean))
$(eval $(call V2_CAPABILITY_CARRIER_G5_RUNTIME_PHASE_TARGET,truncated))
$(eval $(call V2_CAPABILITY_CARRIER_G5_RUNTIME_PHASE_TARGET,bitflip))
$(eval $(call V2_CAPABILITY_CARRIER_G5_RUNTIME_PHASE_TARGET,build-id-mismatch))

# R5 consumes only the registered R4 product seal.  Runtime Core and all
# helper PRGs below are test-closure members and never extend the 13-artifact
# product identity.
.PHONY: r5-global-g5-selftest r5-global-g5-materialize r5-global-g5-runtime-carrier \
	r5-global-g5-test-media r5-global-g5-test-closure r5-global-g5-candidate \
	r5-global-g5-hw-package r5-global-g5-negative-proof \
	r5-global-g5-static-preflight r5-global-g5-preflight-check \
	r5-global-g5-preflight-ready r5-global-g5-seal-selftest

r5-global-g5-selftest:
	python3 tools/host-lisp/dialect_v2_workbench_g5_verify.py selftest
	python3 tools/host-lisp/r5_g5_case_receipts.py selftest
	python3 tools/host-lisp/r5_global_g5.py selftest

r5-global-g5-seal-selftest:
	python3 tools/host-lisp/r5_g5_seal.py selftest

# R6 only materializes bytes already sealed by R4/R5.  It never invokes a
# compiler, linker, disk builder, emulator, or hardware tool.
.PHONY: r6-ship-selftest r6-ship-pack r6-ship-verify r6-ship-negative-test r6-ship-receipt-check \
	g6-two-media-oracle-selftest r6-g6-selftest r6-g6-profile-receipt \
	r6-g6-profile-receipt-check r6-g6-static-preflight r6-g6-preflight-check \
	r6-g6-aggregate-check r6-g6-seal-selftest r6-g6-seal r6-g6-seal-verify \
	r6-g6-seal-negative-test r7-manifest-prerequisites-selftest \
	r7-manifest-prerequisites r7-manifest-prerequisites-check

r6-ship-selftest:
	python3 tools/host-lisp/r6_ship.py selftest

r6-ship-pack: r6-ship-selftest
	rm -rf '$(R6_SHIP_DIR)'
	python3 tools/host-lisp/r6_ship.py pack \
		--source-commit '$(R6_SHIP_SOURCE_COMMIT)' \
		--packed-on '$(R6_SHIP_PACKED_ON)' --out '$(R6_SHIP_DIR)'

r6-ship-verify:
	python3 tools/host-lisp/r6_ship.py verify '$(R6_SHIP_DIR)'

r6-ship-negative-test:
	python3 tools/host-lisp/r6_ship.py negative-test '$(R6_SHIP_DIR)'

r6-ship-receipt-check:
	python3 tools/host-lisp/r6_ship.py receipt-check '$(R6_SHIP_RECEIPT)'

# R6/G6 consumes the already packed Ship and only binds its 15 routes.  The
# hardware cases remain explicitly not-run until their own raw-evidence
# receipts pass the same verifier.
g6-two-media-oracle-selftest:
	python3 tools/host-lisp/g6_two_media_oracle.py --selftest

r6-g6-selftest: g6-two-media-oracle-selftest
	python3 tools/host-lisp/r6_g6.py selftest

r6-g6-profile-receipt: r6-g6-selftest
	python3 tools/host-lisp/r6_g6.py profile-receipt \
		--ship '$(R6_SHIP_DIR)' --out '$(R6_G6_PROFILE_RECEIPT)' --replace

r6-g6-profile-receipt-check:
	python3 tools/host-lisp/r6_g6.py profile-receipt-check \
		--ship '$(R6_SHIP_DIR)' '$(R6_G6_PROFILE_RECEIPT)'

r6-g6-static-preflight: r6-g6-profile-receipt
	python3 tools/host-lisp/r6_g6.py preflight \
		--source-commit '$(R6_G6_SOURCE_COMMIT)' --ship '$(R6_SHIP_DIR)' \
		--out '$(R6_G6_PREFLIGHT_RECEIPT)'

r6-g6-preflight-check:
	python3 tools/host-lisp/r6_g6.py preflight-check '$(R6_G6_PREFLIGHT_RECEIPT)'

r6-g6-aggregate-check:
	python3 tools/host-lisp/r6_g6.py aggregate-check '$(R6_G6_TOP_RECEIPT)'

r6-g6-seal-selftest:
	python3 tools/host-lisp/r6_g6_seal.py selftest

r6-g6-seal: r6-g6-seal-selftest r6-g6-aggregate-check
	python3 tools/host-lisp/r6_g6_seal.py seal \
		--id '$(R6_G6_SEAL_ID)' --source-commit '$(R6_G6_SEAL_SOURCE_COMMIT)' \
		--sealed-on '$(R6_G6_SEALED_ON)' --output '$(R6_G6_SEAL_ARCHIVE)'

r6-g6-seal-verify:
	python3 tools/host-lisp/r6_g6_seal.py verify '$(R6_G6_SEAL_ARCHIVE)'

r6-g6-seal-negative-test:
	python3 tools/host-lisp/r6_g6_seal.py negative-test '$(R6_G6_SEAL_ARCHIVE)'

r7-manifest-prerequisites-selftest:
	python3 tools/host-lisp/r7_manifest_prerequisites.py selftest

r7-manifest-prerequisites: r7-manifest-prerequisites-selftest
	rm -f '$(R7_MANIFEST_PREVIEW)' '$(R7_MANIFEST_RECEIPT)'
	python3 tools/host-lisp/r7_manifest_prerequisites.py preflight \
		--source-commit '$(R7_MANIFEST_SOURCE_COMMIT)' \
		--manifest-out '$(R7_MANIFEST_PREVIEW)' --receipt-out '$(R7_MANIFEST_RECEIPT)'

r7-manifest-prerequisites-check:
	python3 tools/host-lisp/r7_manifest_prerequisites.py check \
		--manifest '$(R7_MANIFEST_PREVIEW)' --receipt '$(R7_MANIFEST_RECEIPT)'

r7-release-selftest:
	python3 tools/host-lisp/r7_release.py selftest

r7-release-verify: r7-release-selftest
	python3 tools/host-lisp/r7_release.py verify '$(R7_RELEASE_BUNDLE)'

r7-release-receipt-check: r7-release-selftest
	python3 tools/host-lisp/r7_release.py receipt-check --require-tag '$(R7_RELEASE_RECEIPT)'

r5-global-g5-materialize: r5-global-g5-selftest
	rm -rf '$(R5_GLOBAL_G5_PRODUCT)'
	python3 tools/host-lisp/r5_global_g5.py materialize --out '$(R5_GLOBAL_G5_PRODUCT)'
	python3 tools/host-lisp/r5_global_g5.py verify-materialization \
		--receipt '$(R5_GLOBAL_G5_MATERIALIZATION)'

r5-global-g5-runtime-carrier: r5-global-g5-selftest
	rm -rf '$(R5_GLOBAL_G5_RUNTIME)'
	rm -f '$(R5_GLOBAL_G5_DIR)/runtime-carrier-provenance.json' \
		'$(R5_GLOBAL_G5_DIR)/runtime-carrier-reproducibility.json'
	python3 tools/host-lisp/r5_global_g5.py build-runtime-carrier-reproducible \
		--source-commit 5e1314f746e7fe154d19f585452274ff8dfd464e \
		--out '$(R5_GLOBAL_G5_RUNTIME)'

r5-global-g5-test-media: r5-global-g5-materialize
	rm -f '$(R5_GLOBAL_G5_TEST_D81)' '$(R5_GLOBAL_G5_TEST_D81_MANIFEST)'
	python3 tools/host-lisp/r5_workbench_test_media.py \
		--work-d81 '$(R5_GLOBAL_G5_PRODUCT)/build/r3/product/lisp65-work.d81' \
		--ide '$(R5_GLOBAL_G5_PRODUCT)/build/bytecode/dialect-v2/libs/ide.ext.bin' \
		--idex '$(R5_GLOBAL_G5_PRODUCT)/build/bytecode/dialect-v2/libs/idex.ext.bin' \
		--m65d '$(R5_GLOBAL_G5_PRODUCT)/build/bytecode/dialect-v2/libs/m65d.ext.bin' \
		--demo demos/d06-numbers.lisp --out '$(R5_GLOBAL_G5_TEST_D81)' \
		--manifest '$(R5_GLOBAL_G5_TEST_D81_MANIFEST)'

r5-global-g5-test-closure: r5-global-g5-test-media r5-global-g5-runtime-carrier \
	hw-workbench-bam-alloc-smoke-prg hw-workbench-chain-write-smoke-prg \
	hw-workbench-dir-write-smoke-prg hw-workbench-save-new-smoke-prg \
	hw-workbench-save-new-scan-smoke-prg hw-workbench-save-new-var-smoke-prg
	rm -f '$(R5_GLOBAL_G5_CLOSURE)'
	python3 tools/host-lisp/r5_global_g5.py pack-closure --out '$(R5_GLOBAL_G5_CLOSURE)'
	python3 tools/host-lisp/r5_global_g5.py verify-closure --manifest '$(R5_GLOBAL_G5_CLOSURE)'

r5-global-g5-candidate: r5-global-g5-test-closure
	rm -f '$(R5_GLOBAL_G5_CANDIDATE)'
	python3 tools/host-lisp/r5_global_g5.py pack-candidate \
		--materialization '$(R5_GLOBAL_G5_MATERIALIZATION)' \
		--closure '$(R5_GLOBAL_G5_CLOSURE)' --out '$(R5_GLOBAL_G5_CANDIDATE)'
	python3 tools/host-lisp/r5_global_g5.py verify-candidate \
		--manifest '$(R5_GLOBAL_G5_CANDIDATE)' \
		--materialization '$(R5_GLOBAL_G5_MATERIALIZATION)' \
		--closure '$(R5_GLOBAL_G5_CLOSURE)'

r5-global-g5-hw-package: r5-global-g5-candidate
	rm -rf '$(R5_GLOBAL_G5_HW_PACKAGE)'
	python3 tools/host-lisp/r5_global_g5.py pack-hw \
		--candidate '$(R5_GLOBAL_G5_CANDIDATE)' \
		--materialization '$(R5_GLOBAL_G5_MATERIALIZATION)' \
		--closure '$(R5_GLOBAL_G5_CLOSURE)' --out '$(R5_GLOBAL_G5_HW_PACKAGE)'

r5-global-g5-negative-proof: r5-global-g5-candidate
	rm -f '$(R5_GLOBAL_G5_NEGATIVE_PROOF)'
	python3 tools/host-lisp/dialect_v2_workbench_g5_verify.py negative-proof \
		--product-artifact-set-sha256 '$(R5_GLOBAL_G5_PRODUCT_SET)' \
		--candidate-manifest-sha256 "$$(sha256sum '$(R5_GLOBAL_G5_CANDIDATE)' | cut -d' ' -f1)" \
		--build-id "$$(python3 -c 'import json; print(json.load(open("$(R5_GLOBAL_G5_CANDIDATE)"))["build_id"])')" \
		--out '$(R5_GLOBAL_G5_NEGATIVE_PROOF)'

r5-global-g5-static-preflight: r5-global-g5-hw-package r5-global-g5-negative-proof
	rm -f '$(R5_GLOBAL_G5_PREFLIGHT_BUILD)'
	python3 tools/host-lisp/r5_global_g5.py preflight \
		--candidate '$(R5_GLOBAL_G5_CANDIDATE)' \
		--materialization '$(R5_GLOBAL_G5_MATERIALIZATION)' \
		--closure '$(R5_GLOBAL_G5_CLOSURE)' \
		--negative-proof '$(R5_GLOBAL_G5_NEGATIVE_PROOF)' \
		--hw-package '$(R5_GLOBAL_G5_HW_PACKAGE)' \
		--out '$(R5_GLOBAL_G5_PREFLIGHT_BUILD)'

r5-global-g5-preflight-check: r5-global-g5-selftest
	python3 tools/host-lisp/r5_global_g5.py verify-preflight \
		--candidate '$(R5_GLOBAL_G5_CANDIDATE)' \
		--materialization '$(R5_GLOBAL_G5_MATERIALIZATION)' \
		--closure '$(R5_GLOBAL_G5_CLOSURE)' \
		--negative-proof '$(R5_GLOBAL_G5_NEGATIVE_PROOF)' \
		--hw-package '$(R5_GLOBAL_G5_HW_PACKAGE)' \
		--receipt '$(R5_GLOBAL_G5_PREFLIGHT_RECEIPT)'

r5-global-g5-preflight-ready: r5-global-g5-preflight-check

define R5_GLOBAL_G5_CASE_GUARD
	@test '$(R5_GLOBAL_G5_PRODUCT_SET)' = 'c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165'
	@test -n '$(R5_GLOBAL_G5_CLOSURE_SET)'
	@test -n '$(R5_GLOBAL_G5_CYCLE_ID)' || \
		{ printf '%s\n' 'Set R5_GLOBAL_G5_CYCLE_ID to the Workbench run id or fresh Runtime power-cycle id.' >&2; exit 2; }
endef

define R5_GLOBAL_G5_PRODUCT_PHASE
	@printf '%s\n' 'R5_CASE_PHASE=product-execution case=$(1)'
endef

define R5_GLOBAL_G5_PRODUCT_PASS
	@printf '%s\n' 'R5_PRODUCT_RESULT=PASS case=$(1) receipt-chain=pending'
endef

define R5_GLOBAL_G5_PACK_WORKBENCH
	python3 tools/host-lisp/r5_g5_case_receipts.py pack-workbench \
		--candidate '$(R5_GLOBAL_G5_CANDIDATE)' --domain '$(1)' --case-id '$(2)' \
		--cycle-id '$(R5_GLOBAL_G5_CYCLE_ID)' $(3) \
		--native-out '$(R5_GLOBAL_G5_EVIDENCE)/workbench-$(2)/receipt-chain/$(R5_GLOBAL_G5_CLOSURE_SET)/native-receipt.json' \
		--out '$(R5_GLOBAL_G5_EVIDENCE)/workbench-$(2)/receipt-chain/$(R5_GLOBAL_G5_CLOSURE_SET)/case-receipt.json'
endef

.PHONY: r5-global-g5-workbench-overlay-stack-guard \
	r5-global-g5-workbench-stdlib-runtime r5-global-g5-workbench-ux-complete \
	r5-global-g5-workbench-bam-read r5-global-g5-workbench-bam-alloc \
	r5-global-g5-workbench-chain-write r5-global-g5-workbench-dir-write \
	r5-global-g5-workbench-save-new r5-global-g5-workbench-save-new-scan \
	r5-global-g5-workbench-save-new-var

r5-global-g5-workbench-overlay-stack-guard: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET)'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-ux/overlay-stack-guard)
	BOOT_WAIT_SEC='$(R5_GLOBAL_G5_BOOT_WAIT_SEC)' \
		WORKBENCH_OVERLAY_RESIDENT_PRG='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.prg' \
		WORKBENCH_OVERLAY_PRELOAD='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.blob.bin' \
		WORKBENCH_RUNTIME_OVERLAY='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.overlays.bin' \
		WORKBENCH_OVERLAY_ELF='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-workbench-overlay-linked.prg.elf' \
		WORKBENCH_OVERLAY_D81='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.d81' \
		WORKBENCH_SHIP_MANIFEST='$(R5_GLOBAL_G5_HW_PACKAGE)/manifest.json' \
		OUT_DIR='$(R5_GLOBAL_G5_EVIDENCE)/workbench-overlay-stack-guard' PREFIX=r5-g5-overlay-stack \
		sh scripts/hw-workbench-overlay-stack-smoke.sh --no-readback || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-ux/overlay-stack-guard'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-ux/overlay-stack-guard)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-ux,overlay-stack-guard,\
		--evidence ship-receipt='$(R5_GLOBAL_G5_EVIDENCE)/workbench-overlay-stack-guard/r5-g5-overlay-stack-ship-manifest-receipt.json' \
		--evidence arith='$(R5_GLOBAL_G5_EVIDENCE)/workbench-overlay-stack-guard/r5-g5-overlay-stack-arith-42.txt' \
		--evidence reader-recovery='$(R5_GLOBAL_G5_EVIDENCE)/workbench-overlay-stack-guard/r5-g5-overlay-stack-reader-recovery.txt')

r5-global-g5-workbench-stdlib-runtime: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET)'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-ux/stdlib-runtime)
	mkdir -p '$(R5_GLOBAL_G5_EVIDENCE)/workbench-stdlib-runtime'
	$(R5_GLOBAL_G5_WORKBENCH_ENV) sh scripts/hw-smoke-vm-stdlib.sh --no-build --remote-d81 L65R5S.D81 || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-ux/stdlib-runtime'; exit $$status; }
	@printf '%s\n' 'R5 Workbench boot wait: $(R5_GLOBAL_G5_BOOT_WAIT_SEC)s before semantic input'
	sleep '$(R5_GLOBAL_G5_BOOT_WAIT_SEC)'
	scripts/hw-jtag-repl.sh --form '(+ 20 22)' --expect 42 --verified-input \
		--prefix r5-g5-stdlib-runtime --out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-stdlib-runtime' || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-ux/stdlib-runtime'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-ux/stdlib-runtime)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-ux,stdlib-runtime,\
		--evidence result='$(R5_GLOBAL_G5_EVIDENCE)/workbench-stdlib-runtime/r5-g5-stdlib-runtime.txt')

r5-global-g5-workbench-ux-complete: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET)'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-ux/ux-complete)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) OUT_DIR='$(R5_GLOBAL_G5_EVIDENCE)/workbench-ux-complete' \
		PREFIX=r5-g5-ux sh scripts/hw-workbench-ux-smoke.sh --no-build --remote-d81 L65R5U.D81 || \
		{ status=$$?; case $$status in \
			5|6|124) printf '%s\n' 'R5 receipt chain: FAIL kind=harness case=workbench-ux/ux-complete stage=verified-input-or-capture' ;; \
			*) printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-ux/ux-complete' ;; \
		esac; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-ux/ux-complete)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-ux,ux-complete,\
		--evidence persistence='$(R5_GLOBAL_G5_EVIDENCE)/workbench-ux-complete/r5-g5-ux-persistence-reset-read.txt' \
		--evidence some='$(R5_GLOBAL_G5_EVIDENCE)/workbench-ux-complete/r5-g5-ux-higher-order-idex-some.txt' \
		--evidence every='$(R5_GLOBAL_G5_EVIDENCE)/workbench-ux-complete/r5-g5-ux-higher-order-idex-every.txt' \
		--evidence mx-eval-buffer='$(R5_GLOBAL_G5_EVIDENCE)/workbench-ux-complete/r5-g5-ux-mx-eval-buffer.txt')

r5-global-g5-workbench-bam-read: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET)'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/bam-read)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) OUT_DIR='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-read' \
		PREFIX=r5-g5-bam-read sh scripts/hw-workbench-bam-read-smoke.sh --no-build --remote-d81 L65R5R.D81 || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/bam-read'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/bam-read)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,bam-read,\
		--evidence media-d81='$(R5_GLOBAL_G5_HW_PACKAGE)/lisp65-mvp-workbench.d81' \
		--evidence sector-1='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-read/r5-g5-bam-read-bam-sector-1.txt' \
		--evidence sector-2='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-read/r5-g5-bam-read-bam-sector-2.txt')

r5-global-g5-workbench-bam-alloc: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-bam-alloc'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/bam-alloc)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWBAMALLOCPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-bam-alloc.prg' \
		sh scripts/hw-workbench-bam-alloc-smoke.sh --no-build --remote-d81 L65R5A.D81 \
		--out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc' --prefix r5-g5-bam-alloc \
		--before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc/after.d81' || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/bam-alloc'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/bam-alloc)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,bam-alloc,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-bam-alloc/r5-g5-bam-alloc.txt')

r5-global-g5-workbench-chain-write: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-chain-write'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/chain-write)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWCHAINWRITEPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-chain-write.prg' \
		sh scripts/hw-workbench-chain-write-smoke.sh --no-build --remote-d81 L65R5C.D81 \
		--out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write' --prefix r5-g5-chain-write \
		--before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/after.d81' || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/chain-write'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/chain-write)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,chain-write,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/r5-g5-chain-write.txt' \
		--evidence run='$(R5_GLOBAL_G5_EVIDENCE)/workbench-chain-write/r5-g5-chain-write-run-chain.txt')

r5-global-g5-workbench-dir-write: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-dir-write'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/dir-write)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWDIRWRITEPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-dir-write.prg' \
		sh scripts/hw-workbench-dir-write-smoke.sh --no-build --remote-d81 L65R5D.D81 \
		--out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write' --prefix r5-g5-dir-write \
		--before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/after.d81' || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/dir-write'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/dir-write)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,dir-write,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/r5-g5-dir-write.txt' \
		--evidence run='$(R5_GLOBAL_G5_EVIDENCE)/workbench-dir-write/r5-g5-dir-write-run-dir.txt')

r5-global-g5-workbench-save-new: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-save-new'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/save-new)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWSAVENEWPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-save-new.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --remote-d81 L65R5N.D81 \
		--out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new' --prefix r5-g5-save-new \
		--before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/after.d81' \
		--first-sector 27 --second-sector 28 || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/save-new'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/save-new)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,save-new,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/r5-g5-save-new.txt' \
		--evidence run='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new/r5-g5-save-new-run-save-new.txt')

r5-global-g5-workbench-save-new-scan: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-save-new-scan'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/save-new-scan)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWSAVENEWPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-save-new-scan.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --remote-d81 L65R56.D81 \
		--out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan' --prefix r5-g5-save-new-scan \
		--before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/after.d81' \
		--name m6src --first-sector 28 --second-sector 29 --reserve-sector 27 || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/save-new-scan'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/save-new-scan)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,save-new-scan,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/r5-g5-save-new-scan.txt' \
		--evidence run='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-scan/r5-g5-save-new-scan-run-save-new.txt')

r5-global-g5-workbench-save-new-var: r5-global-g5-preflight-ready
	$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$(R5_GLOBAL_G5_PRODUCT_SET) closure=$(R5_GLOBAL_G5_CLOSURE_SET) helper-save-new-var'
	$(call R5_GLOBAL_G5_PRODUCT_PHASE,workbench-persistence/save-new-var)
	$(R5_GLOBAL_G5_WORKBENCH_ENV) M65HWSAVENEWPRG='$(R5_GLOBAL_G5_HW_PACKAGE)/persistence-save-new-var.prg' \
		sh scripts/hw-workbench-save-new-smoke.sh --no-build --generic-diff --wait 45 --timeout 40 \
		--remote-d81 L65R57.D81 --out-dir '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var' \
		--prefix r5-g5-save-new-var --before-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/before.d81' \
		--after-d81 '$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/after.d81' \
		--source tests/disk/m7-var-source.lisp --alloc-source lib/m65-disk-alloc-var.lisp \
		--alloc-name m7alloc --name m7src --load-ok m7-load-ok --load-fail m7-load-fail \
		--run-form '(m7-var-run)' --run-expect 907 || \
		{ status=$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=workbench-persistence/save-new-var'; exit $$status; }
	$(call R5_GLOBAL_G5_PRODUCT_PASS,workbench-persistence/save-new-var)
	$(call R5_GLOBAL_G5_PACK_WORKBENCH,workbench-persistence,save-new-var,\
		--evidence before-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/before.d81' \
		--evidence after-d81='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/after.d81' \
		--evidence marker='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/r5-g5-save-new-var.txt' \
		--evidence run='$(R5_GLOBAL_G5_EVIDENCE)/workbench-save-new-var/r5-g5-save-new-var-run-save-new.txt')

R5_GLOBAL_G5_POWER_CYCLE_TOKEN ?=
R5_GLOBAL_G5_CYCLE_ID ?=

.PHONY: r5-global-g5-runtime-clean r5-global-g5-runtime-truncated \
	r5-global-g5-runtime-bitflip r5-global-g5-runtime-build-id-mismatch

define R5_GLOBAL_G5_RUNTIME_PHASE_TARGET
r5-global-g5-runtime-$(1): r5-global-g5-preflight-ready
	$$(R5_GLOBAL_G5_CASE_GUARD)
	@printf '%s\n' 'R5 binding product=$$(R5_GLOBAL_G5_PRODUCT_SET) closure=$$(R5_GLOBAL_G5_CLOSURE_SET) runtime-package'
	$$(call R5_GLOBAL_G5_PRODUCT_PHASE,runtime-export/$(1))
	@test '$$(R5_GLOBAL_G5_POWER_CYCLE_TOKEN)' = POWER-CYCLED || \
		{ printf '%s\n' 'Set R5_GLOBAL_G5_POWER_CYCLE_TOKEN=POWER-CYCLED only after a physical power-cycle.' >&2; exit 2; }
	python3 tools/host-lisp/runtime_export_hw_oracle.py deploy --gate G5 --phase '$(1)' \
		--package '$$(R5_GLOBAL_G5_RUNTIME)' \
		--oracle '$$(R5_GLOBAL_G5_RUNTIME)/hardware-oracle.json' \
		--out-dir '$$(R5_GLOBAL_G5_EVIDENCE)/runtime-$(1)/native' \
		--power-cycle-token '$$(R5_GLOBAL_G5_POWER_CYCLE_TOKEN)' \
		--cycle-id '$$(R5_GLOBAL_G5_CYCLE_ID)' || \
		{ status=$$$$?; printf '%s\n' 'R5_PRODUCT_RESULT=FAIL case=runtime-export/$(1)'; exit $$$$status; }
	$$(call R5_GLOBAL_G5_PRODUCT_PASS,runtime-export/$(1))
	python3 tools/host-lisp/r5_g5_case_receipts.py pack-runtime \
		--candidate '$$(R5_GLOBAL_G5_CANDIDATE)' --phase '$(1)' \
		--cycle-id '$$(R5_GLOBAL_G5_CYCLE_ID)' \
		--package '$$(R5_GLOBAL_G5_RUNTIME)' \
		--oracle '$$(R5_GLOBAL_G5_RUNTIME)/hardware-oracle.json' \
		--native-receipt '$$(R5_GLOBAL_G5_EVIDENCE)/runtime-$(1)/native/receipt-$(1).json' \
		--out '$$(R5_GLOBAL_G5_EVIDENCE)/runtime-$(1)/receipt-chain/$$(R5_GLOBAL_G5_CLOSURE_SET)/case-receipt.json'
endef

$(eval $(call R5_GLOBAL_G5_RUNTIME_PHASE_TARGET,clean))
$(eval $(call R5_GLOBAL_G5_RUNTIME_PHASE_TARGET,truncated))
$(eval $(call R5_GLOBAL_G5_RUNTIME_PHASE_TARGET,bitflip))
$(eval $(call R5_GLOBAL_G5_RUNTIME_PHASE_TARGET,build-id-mismatch))

v2-workbench-symbol-diff-selftest:
	python3 tools/host-lisp/v2_workbench_symbol_diff.py \
		--policy $(V2_WORKBENCH_SYMBOL_DIFF_POLICY) selftest

v2-workbench-symbol-diff-check: v2-workbench-symbol-diff-selftest $(V2_WORKBENCH_SYMBOL_DIFF_POLICY) $(V2_WORKBENCH_SYMBOL_DIFF_REPORT)
	python3 tools/host-lisp/v2_workbench_symbol_diff.py \
		--policy $(V2_WORKBENCH_SYMBOL_DIFF_POLICY) check \
		--report $(V2_WORKBENCH_SYMBOL_DIFF_REPORT)

v2-workbench-deresidentization-audit-selftest:
	python3 tools/host-lisp/v2_workbench_deresidentization_audit.py \
		--contract $(V2_WORKBENCH_DERES_AUDIT) --selftest

v2-workbench-deresidentization-audit-check: v2-workbench-deresidentization-audit-selftest $(V2_WORKBENCH_DERES_AUDIT)
	python3 tools/host-lisp/v2_workbench_deresidentization_audit.py \
		--contract $(V2_WORKBENCH_DERES_AUDIT)

v2-workbench-deresidentization-prototype-selftest:
	python3 tools/host-lisp/v2_workbench_deresidentization_prototype.py selftest

v2-workbench-deresidentization-prototype-check: v2-workbench-deresidentization-prototype-selftest
	python3 tools/host-lisp/v2_workbench_deresidentization_prototype.py verify --offline \
		--report tests/bytecode/dialect-v2/evidence/capability-carrier/number-to-string-prototype/report.json

v2-fasl-save-host-selftest:
	python3 tools/host-lisp/v2_fasl_save_host_acceptance.py selftest

v2-fasl-save-host-check: v2-fasl-save-host-selftest
	python3 tools/host-lisp/v2_fasl_save_host_acceptance.py check

dialect-v2-number-to-string-check: $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_number_to_string.py check

# Live attribution consumes two caller-built, real MOS relocatable ELFs. It
# explains ownership, but never replaces the LTO/ICF product-floor metric.
v2-workbench-symbol-diff-live: v2-workbench-symbol-diff-selftest
	@test -n '$(V2_WORKBENCH_ATTR_BASELINE_ELF)' || { echo 'V2_WORKBENCH_ATTR_BASELINE_ELF is required' >&2; exit 2; }
	@test -n '$(V2_WORKBENCH_ATTR_CANDIDATE_ELF)' || { echo 'V2_WORKBENCH_ATTR_CANDIDATE_ELF is required' >&2; exit 2; }
	python3 tools/host-lisp/v2_workbench_symbol_diff.py \
		--policy $(V2_WORKBENCH_SYMBOL_DIFF_POLICY) generate \
		--baseline-elf '$(V2_WORKBENCH_ATTR_BASELINE_ELF)' \
		--candidate-elf '$(V2_WORKBENCH_ATTR_CANDIDATE_ELF)' \
		--nm $(M65VMSTDLIB_NM) --out $(V2_WORKBENCH_SYMBOL_DIFF_LIVE_REPORT)
	python3 tools/host-lisp/v2_workbench_symbol_diff.py \
		--policy $(V2_WORKBENCH_SYMBOL_DIFF_POLICY) check \
		--report $(V2_WORKBENCH_SYMBOL_DIFF_LIVE_REPORT)

v2-capability-carrier-check-host-1: v2-capability-carrier-contract-check dialect-v2-eval-apply-funcall-check
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) \
		--fixture $(V2_CAPABILITY_CARRIER_FIXTURE) surface-check
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) checkpoint --number 1

v2-capability-carrier-check-host-2: v2-capability-carrier-check-host-1 workbench-service-call-inventory-current
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) checkpoint --number 2

v2-capability-carrier-check-host-3: v2-capability-carrier-check-host-2 dialect-v2-lists-matrix dialect-v2-strings-native-stage3-matrix dialect-v2-strings-p0-check dialect-v2-strings-lcc-stage3-check v2-prim-lowering-check v2-string-caps-host-check v2-callprim-runtime-check v2-string-codec-workload-check v2-carrier-state-active
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) checkpoint --number 3

v2-capability-carrier-check-host-4: v2-capability-carrier-check-host-3 workbench-service-call-inventory-staging v2-workbench-services-check v2-workbench-library-composition-check dialect-v2-lcc-compile-error-check v2-carrier-state-removed v2-string-caps-host-check v2-callprim-runtime-check v2-native-function-matrix-check
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) checkpoint --number 4

v2-capability-carrier-check-host-5: v2-capability-carrier-check-host-4 v2-workbench-symbol-diff-check v2-capability-carrier-internal-g5-check v2-cp5-g5-archive-check
	python3 tools/host-lisp/v2_capability_carrier_contract.py \
		--contract $(V2_CAPABILITY_CARRIER_CONTRACT) checkpoint --number 5

dialect-v2-lcc-surface-selftest:
	python3 tools/host-lisp/dialect_v2_lcc_surface.py --selftest

dialect-v2-lcc-surface-check: dialect-v2-lcc-surface-selftest $(DIALECT_V1_EQUIVALENCE_BUILD) $(DIALECT_V2_EQUIVALENCE_BUILD)
	python3 tools/host-lisp/dialect_v2_lcc_surface.py \
		--binary-v1 $(DIALECT_V1_EQUIVALENCE_HOST) \
		--binary-v2 $(DIALECT_V2_EQUIVALENCE_HOST) \
		--source-root-v1 $(DIALECT_V1_SOURCE_ROOT) --source-root-v2 .

dialect-v2-prelude-evidence-selftest:
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py selftest

dialect-v2-prelude-evidence-check: dialect-v2-prelude-evidence-selftest
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py check

dialect-v2-prelude-evidence-live-check: dialect-v2-prelude-control-matrix dialect-v2-prelude-evidence-check
	python3 tools/host-lisp/dialect_v2_prelude_evidence.py check \
		--verdict-dir build/bytecode/dialect-v2/prelude-control

eval-surface-contract-check: $(EQUIVALENCE_HOST)
	python3 tools/host-lisp/eval_surface_contract.py --engine python-p0-compiler-vm tests/bytecode/runtime/p0-eval-surface.json
	python3 tools/host-lisp/eval_surface_contract.py --engine native-treewalk --binary $(EQUIVALENCE_HOST) tests/bytecode/runtime/p0-eval-surface.json
	python3 tools/host-lisp/eval_surface_contract.py --engine native-c-compiler-vm --binary $(EQUIVALENCE_HOST) tests/bytecode/runtime/p0-eval-surface.json
	python3 tools/host-lisp/eval_surface_contract.py --engine lisp-lcc --binary $(EQUIVALENCE_HOST) tests/bytecode/runtime/p0-eval-surface.json

equivalence-check:
	sh scripts/equivalence-check.sh

stdlib-embed-whatif-check:
	python3 tools/host-lisp/stdlib_embed_whatif.py $(BYTECODE_STRING_POLISH_SUITE) $(BYTECODE_FIXED_SUITE) >/dev/null

mvp-vm-stdlib-boot-budget-check: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/mvp_vm_stdlib_boot_budget.py \
		--out /dev/null \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(M65VMSTDLIB_MIN_SYMBOL_HEADROOM)" \
		--extra-cflags "$(M65VMSTDLIB_EXTRA_CFLAGS)" \
		--fail-on-over-budget >/dev/null

mvp-vm-stdlib-runtime-budget-check: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/mvp_vm_stdlib_runtime_budget.py \
		--out /dev/null \
		--suite "$(BYTECODE_STDLIB_SUITE)" \
		--extra-cflags "$(M65VMSTDLIB_EXTRA_CFLAGS)" \
		--native-initial-base "$(M65VMSTDLIB_EVAL_ROOT_BASELINE)" \
		--min-native-frame-headroom "$(M65VMSTDLIB_MIN_RUNTIME_FRAME_HEADROOM)" \
		--min-native-stack-headroom "$(M65VMSTDLIB_MIN_RUNTIME_STACK_HEADROOM)" \
		--include-ide-scenarios \
		--fail-on-over-budget >/dev/null

closure-surface-check:
	python3 tools/host-lisp/closure_surface_check.py

ide-host-slice-check:
	python3 tools/host-lisp/ide_buffer_eval_oracle.py
	python3 tools/host-lisp/ide_completion_eval_oracle.py
	python3 tools/host-lisp/ide_eval_request_eval_oracle.py
	python3 tools/host-lisp/ide_ui_eval_oracle.py

ide-bytecode-cost-report: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/ide_bytecode_cost_report.py \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--out "$(IDE_BYTECODE_COST_REPORT)" \
		--check-render-contract

ide-render-callgraph: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/ide_render_callgraph.py \
		--manifest "$(BYTECODE_STDLIB_PREFIX).manifest.json" \
		--out "$(IDE_RENDER_CALLGRAPH_REPORT)"

ide-bytecode-dynamic-report: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/ide_bytecode_dynamic_report.py \
		--suite "$(BYTECODE_STDLIB_SUITE)" \
		--out "$(IDE_BYTECODE_DYNAMIC_REPORT)" \
		$(IDE_BYTECODE_DYNAMIC_BUDGET_ARGS) \
		--check

bytecode-p0-oracle:
	python3 tools/host-lisp/bytecode_p0_oracle.py

bytecode-p0-compiler-check:
	python3 tools/host-lisp/bytecode_p0_compiler.py --check

bytecode-p0-program-check:
	python3 tools/host-lisp/bytecode_p0_compiler.py --check-programs

bytecode-p0-bundle-check:
	python3 tools/host-lisp/bytecode_p0_bundle.py --check

bytecode-p0-stdlib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check

bytecode-p0-stdlib-artifacts: | build/bytecode
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_STDLIB_PREFIX) $(BYTECODE_STDLIB_SUITE)
	$(HOSTCC) -std=c99 -Wall -I. -include $(BYTECODE_STDLIB_HEADER) -x c -c /dev/null -o build/bytecode/stdlib-p0-header-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -I. -Isrc -include $(BYTECODE_STDLIB_HEADER) -x c -c /dev/null -o build/bytecode/stdlib-p0-vm-header-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -I. -Isrc -Ibuild/bytecode -c $(BYTECODE_STDLIB_C) -o build/bytecode/stdlib-p0-c-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -DLISP65_BYTECODE_STDLIB_EMIT_METADATA -I. -Isrc -Ibuild/bytecode -c $(BYTECODE_STDLIB_C) -o build/bytecode/stdlib-p0-metadata-c-smoke.o

$(STRING_ARENA_STDLIB_C): $(BYTECODE_STDLIB_EINSUITE_CORE_SUITE) tools/host-lisp/bytecode_p0_stdlib.py | build/bytecode
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(STRING_ARENA_STDLIB_PREFIX) $(BYTECODE_STDLIB_EINSUITE_CORE_SUITE)

$(STRING_ARENA_PROBE_BASELINE): $(STRING_ARENA_PROBE_SRCS) $(STRING_ARENA_STDLIB_C) | build
	$(HOSTCC) $(STRING_ARENA_PROBE_CFLAGS) -Isrc -Ibuild/bytecode $(STRING_ARENA_PROBE_SRCS) $(STRING_ARENA_STDLIB_C) -o $@

$(STRING_ARENA_PROBE_ARENA): $(STRING_ARENA_PROBE_SRCS) $(STRING_ARENA_STDLIB_C) | build
	$(HOSTCC) $(STRING_ARENA_PROBE_CFLAGS) -DLISP65_STRING_ARENA -Isrc -Ibuild/bytecode $(STRING_ARENA_PROBE_SRCS) $(STRING_ARENA_STDLIB_C) -o $@

string-arena-probe: $(STRING_ARENA_PROBE_BASELINE) $(STRING_ARENA_PROBE_ARENA)
	$(STRING_ARENA_PROBE_BASELINE)
	$(STRING_ARENA_PROBE_ARENA)

bytecode-p0-disklib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_DISKLIB_SUITE)

bytecode-p0-disklib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_DISKLIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_DISKLIB_SUITE)

$(L65M_CONTRACT_HEADER): $(L65M_CONTRACT_FIXTURE) tools/host-lisp/l65m_contract.py | build
	python3 tools/host-lisp/l65m_contract.py check-fixture $(L65M_CONTRACT_FIXTURE) --emit-c-header $@

l65m-contract-check: $(L65M_CONTRACT_HEADER)
	python3 tools/host-lisp/l65m_contract.py check-fixture $(L65M_CONTRACT_FIXTURE) --check-c-header $(L65M_CONTRACT_HEADER)

$(L65M_NATIVE_LOADER_HOST): scripts/l65m-native-loader-main.c src/l65m_commit_overlay.c src/l65m_commit_overlay.h src/l65m_validate.c src/l65m_validate.h src/l65m_overlay_abi.h src/vm_embed.c src/vm_embed.h src/vm.c src/vm.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h $(L65M_CONTRACT_HEADER) | bytecode-p0-stdlib-artifacts build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_VM -DLISP65_RUNTIME_CORE -DLISP65_DISK_LIBS \
		-DL65M_COMMIT_OVERLAY_HOST_DIRECT \
		-DLISP65_STDLIB_EXT_METADATA -DLISP65_EXT_HEAP -DLISP65_MARK_BITMAP \
		-DLISP65_STRING_ARENA -DHEAP_CELLS=256 -DEXT_CELLS=1024 \
		-DGC_ROOTS=256 -DMAX_SYM=256 -DNAMEPOOL=4096 -DVM_DIR_MAX=128 \
		-DSTR_ARENA_SIZE=4096 -DSYMPOOL_EXT_OFF=0xf000 \
		-Isrc -Ibuild/bytecode -Ibuild scripts/l65m-native-loader-main.c \
		src/l65m_commit_overlay.c src/l65m_validate.c src/vm_embed.c src/vm.c \
		src/mem.c src/symbol.c src/interrupt.c -o $@

l65m-native-loader-check: $(L65M_NATIVE_LOADER_HOST)
	$(L65M_NATIVE_LOADER_HOST)

$(L65M_V2_PRODUCT_HEADER): v2-workbench-artifacts tools/host-lisp/l65m_v2_product_cases.py \
		config/directory-only-l65m-v2-implementation.json \
		config/directory-only-interlibrary-api.json \
		build/bytecode/dialect-v2/libs/ide.ext.bin \
		build/bytecode/dialect-v2/libs/ide.manifest.json \
		build/bytecode/dialect-v2/libs/ide.diagnostic-map.json \
		build/bytecode/dialect-v2/libs/idex.ext.bin \
		build/bytecode/dialect-v2/libs/idex.manifest.json \
		build/bytecode/dialect-v2/libs/idex.diagnostic-map.json \
		build/bytecode/dialect-v2/workbench/stdlib-p0.ext.bin \
		build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json | build
	python3 tools/host-lisp/l65m_v2_product_cases.py --emit-c-header $@

$(L65M_V2_PRODUCT_HOST): scripts/l65m-v2-product-main.c $(L65M_V2_PRODUCT_HEADER) \
		src/l65m_commit_overlay.c src/l65m_validate.c src/vm_embed.c src/vm.c \
		src/mem.c src/symbol.c src/interrupt.c \
		build/bytecode/dialect-v2/workbench/stdlib-p0.c | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_VM -DLISP65_RUNTIME_CORE -DLISP65_DISK_LIBS \
		-DLISP65_DIALECT_V2 -DLISP65_TREEWALK_STRIP -DLISP65_V2_CARRIER_CUT \
		-DLISP65_VM_NATIVE_APPLY -DLISP65_V2_NATIVE_CAPABILITIES \
		-DLISP65_V2_NATIVE_STRING_CODECS -DLISP65_V2_SERVICE_REGISTRY_CLOSED \
		-DLISP65_V2_WORKBENCH_SERVICES -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_DIRECTORY_ONLY_HARNESS -DLISP65_VM_DIAGNOSTICS \
		-DL65M_COMMIT_OVERLAY_HOST_DIRECT \
		-DLISP65_STDLIB_EXT_METADATA -DLISP65_EXT_HEAP -DLISP65_MARK_BITMAP \
		-DLISP65_SYMPOOL_EXT \
		-DLISP65_STRING_ARENA -DHEAP_CELLS=2048 -DEXT_CELLS=8192 \
		-DGC_ROOTS=1024 -DMAX_SYM=752 -DNAMEPOOL=10208 -DVM_DIR_MAX=752 \
		-DSTR_ARENA_SIZE=16384 -DSYMPOOL_EXT_OFF=0xd000 \
		-Isrc -Ibuild/bytecode -Ibuild scripts/l65m-v2-product-main.c \
		build/bytecode/dialect-v2/workbench/stdlib-p0.c \
		src/l65m_commit_overlay.c src/l65m_validate.c src/vm_embed.c src/vm.c \
		src/mem.c src/symbol.c src/interrupt.c -o $@

directory-only-emitter-selftest:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --directory-only-selftest

l65m-v2-product-check: directory-only-emitter-selftest $(L65M_V2_PRODUCT_HOST)
	$(L65M_V2_PRODUCT_HOST)
	$(L65M_V2_PRODUCT_HOST) --transaction-matrix

$(FASL_EMIT_CHECK_HOST): scripts/fasl-emit-check-main.c lib/lcc.lisp lib/lcc-fasl.lisp src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c | build
	@mkdir -p $(@D)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_VM -DLISP65_FASL -DLISP65_EVAL_CONTROL_SF -DLISP65_EVAL_PRIMS \
		-DLISP65_EVAL_DIV_PRIM -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM \
		-DLISP65_EXT_HEAP -DEXT_CELLS=4096 -DLISP65_MARK_BITMAP \
		-DHEAP_CELLS=12000 -DGC_ROOTS=2048 -DMAX_SYM=768 -DNAMEPOOL=16384 \
		-DVM_DIR_MAX=128 -Isrc scripts/fasl-emit-check-main.c src/eval.c src/vm.c \
		src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c \
		src/screen.c -o $@

$(FASL_EMIT_CHECK_ARTIFACT): $(FASL_EMIT_CHECK_HOST) lib/lcc.lisp lib/lcc-fasl.lisp
	$(FASL_EMIT_CHECK_HOST) $@

fasl-emit-check: $(FASL_EMIT_CHECK_ARTIFACT)
	python3 tools/host-lisp/l65m_contract.py validate $(FASL_EMIT_CHECK_ARTIFACT)

bytecode-p0-disklib-d81: bytecode-p0-disklib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_DISKLIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_DISKLIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_DISKLIB_EXT_BLOB):TESTLIB" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-ide-full-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_IDE_FULL_LIB_SUITE)

bytecode-p0-private-inline-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --private-inline-selftest
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check tests/bytecode/libs/p0-private-inline-test.json

workbench-private-inline-composition-probe:
	python3 tools/host-lisp/workbench_private_inline_probe.py selftest
	python3 tools/host-lisp/workbench_private_inline_probe.py check

gc-symbol-scan-timing-check:
	python3 tools/host-lisp/gc_symbol_scan_timing.py \
		--max-symbols 752 --baseline-symbols 720 --namepool 10208

bytecode-p0-omission-contract-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --omission-contract-selftest
	python3 tools/host-lisp/bytecode_p0_stdlib.py --omission-contract-audit

ide-capacity-selftest:
	python3 tools/host-lisp/ide_capacity_report.py --selftest

ide-capacity-check: bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts
	python3 tools/host-lisp/ide_capacity_report.py \
		--contract config/ide-capacity-contract.json \
		--json-out build/bytecode/ide-capacity-report.json

bytecode-p0-ide-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_IDE_LIB_SUITE)

bytecode-p0-ide-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_IDE_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_IDE_LIB_SUITE)
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_IDE_FULL_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_IDE_BASELINE_LIB_SUITE)

bytecode-p0-ide-extra-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_IDE_EXTRA_LIB_SUITE)

bytecode-p0-ide-extra-lib-artifacts: bytecode-p0-ide-lib-artifacts | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_IDE_EXTRA_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_IDE_EXTRA_LIB_SUITE)

m65d-blank-d81-oracle-selftest:
	python3 tools/host-lisp/m65d_blank_d81_oracle.py --selftest

bytecode-p0-m65d-lib-check: m65d-blank-d81-oracle-selftest
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_M65D_LIB_SUITE)

bytecode-p0-m65d-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_M65D_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_M65D_LIB_SUITE)

bytecode-p0-ide-lib-d81: bytecode-p0-ide-lib-artifacts bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_IDE_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_IDE_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_IDE_LIB_EXT_BLOB):IDE $(BYTECODE_IDE_EXTRA_LIB_EXT_BLOB):IDEX $(BYTECODE_M65D_LIB_EXT_BLOB):M65D" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-format-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_FORMAT_LIB_SUITE)

bytecode-p0-format-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_FORMAT_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_FORMAT_LIB_SUITE)

bytecode-p0-format-lib-d81: bytecode-p0-format-lib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_FORMAT_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_FORMAT_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_FORMAT_LIB_EXT_BLOB):FMT" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-fixed-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_FIXED_LIB_SUITE)

bytecode-p0-fixed-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_FIXED_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_FIXED_LIB_SUITE)

bytecode-p0-fixed-lib-d81: bytecode-p0-fixed-lib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_FIXED_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_FIXED_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_FIXED_LIB_EXT_BLOB):FIXED" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-strings-extra-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_STRINGS_EXTRA_LIB_SUITE)

bytecode-p0-strings-extra-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_STRINGS_EXTRA_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_STRINGS_EXTRA_LIB_SUITE)

bytecode-p0-strings-extra-lib-d81: bytecode-p0-strings-extra-lib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_STRINGS_EXTRA_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_STRINGS_EXTRA_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_STRINGS_EXTRA_LIB_EXT_BLOB):STRX" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-place-lib-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(BYTECODE_PLACE_LIB_SUITE)

bytecode-p0-place-lib-artifacts: | build/bytecode/libs
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_PLACE_LIB_PREFIX) --artifact-role disk-lib --base-addr 0x000000 $(BYTECODE_PLACE_LIB_SUITE)

bytecode-p0-place-lib-d81: bytecode-p0-place-lib-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_PLACE_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_PLACE_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_PLACE_LIB_EXT_BLOB):PLACE" \
		sh scripts/build-bytecode-lib-d81.sh

bytecode-p0-pilot-libs-check: bytecode-p0-ide-full-lib-check bytecode-p0-ide-lib-check bytecode-p0-ide-extra-lib-check bytecode-p0-m65d-lib-check bytecode-p0-format-lib-check bytecode-p0-fixed-lib-check bytecode-p0-strings-extra-lib-check bytecode-p0-place-lib-check

bytecode-p0-pilot-libs-artifacts: bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts bytecode-p0-format-lib-artifacts bytecode-p0-fixed-lib-artifacts bytecode-p0-strings-extra-lib-artifacts bytecode-p0-place-lib-artifacts

bytecode-p0-pilot-libs-d81: bytecode-p0-pilot-libs-artifacts
	BYTECODE_LIB_D81=$(BYTECODE_PILOT_LIB_D81) \
		BYTECODE_LIB_MANIFEST=$(BYTECODE_PILOT_LIB_D81_MANIFEST) \
		BYTECODE_LIB_FILES="$(BYTECODE_IDE_LIB_EXT_BLOB):IDE $(BYTECODE_IDE_EXTRA_LIB_EXT_BLOB):IDEX $(BYTECODE_M65D_LIB_EXT_BLOB):M65D $(BYTECODE_FORMAT_LIB_EXT_BLOB):FMT $(BYTECODE_FIXED_LIB_EXT_BLOB):FIXED $(BYTECODE_STRINGS_EXTRA_LIB_EXT_BLOB):STRX $(BYTECODE_PLACE_LIB_EXT_BLOB):PLACE" \
		sh scripts/build-bytecode-lib-d81.sh

demo-suite-check:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check $(DEMO_SUITE)

demo-suite-d81: bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts demo-suite-check scripts/build-demo-suite-d81.sh $(wildcard demos/*.lisp) | build/demos
	DEMO_SUITE_D81=$(DEMO_SUITE_D81) \
		DEMO_SUITE_MANIFEST=$(DEMO_SUITE_MANIFEST) \
		DEMO_SUITE_FASL_SLOT_BYTES=$(DEMO_SUITE_FASL_SLOT_BYTES) \
		DEMO_SUITE_IDE_LIB=$(BYTECODE_IDE_LIB_EXT_BLOB) \
		DEMO_SUITE_IDEX_LIB=$(BYTECODE_IDE_EXTRA_LIB_EXT_BLOB) \
		DEMO_SUITE_M65D_LIB=$(BYTECODE_M65D_LIB_EXT_BLOB) \
		sh scripts/build-demo-suite-d81.sh

bytecode-known-open-diagnostic-artifacts: | build/bytecode
	mkdir -p build/bytecode/known-open-diagnostic
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(BYTECODE_KNOWN_OPEN_DIAG_PREFIX) $(BYTECODE_KNOWN_OPEN_DIAG_SUITE)
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -DLISP65_BYTECODE_STDLIB_EMIT_METADATA -I. -Isrc -Ibuild/bytecode/known-open-diagnostic -c $(BYTECODE_KNOWN_OPEN_DIAG_C) -o build/bytecode/known-open-diagnostic/stdlib-p0-c-smoke.o

bytecode-p0-drift-check: bytecode-p0-stdlib-artifacts
	python3 tools/host-lisp/bytecode_p0_drift_check.py

runtime-known-open-check:
	python3 tools/host-lisp/runtime_known_open_check_test.py
	python3 tools/host-lisp/runtime_known_open_check.py $(RUNTIME_KNOWN_OPEN)

$(BYTECODE_P0_C_VECTORS): $(BYTECODE_P0_VECTOR_JSON) tools/host-lisp/bytecode_p0_c_vectors.py tools/host-lisp/bytecode_p0.py | build
	python3 tools/host-lisp/bytecode_p0_c_vectors.py $(BYTECODE_P0_VECTOR_JSON) > $@

$(BYTECODE_P0_NATIVE_COMPILE_VECTORS): $(BYTECODE_P0_VECTOR_JSON) tools/host-lisp/bytecode_p0_native_compile_vectors.py tools/host-lisp/bytecode_p0_c_vectors.py tools/host-lisp/bytecode_p0.py | build
	python3 tools/host-lisp/bytecode_p0_native_compile_vectors.py $(BYTECODE_P0_VECTOR_JSON) > $@

$(BYTECODE_P0_NATIVE_COMPILER_HOST): scripts/bytecode-p0-native-compiler-main.c $(BYTECODE_P0_NATIVE_COMPILE_VECTORS) src/compile.c src/compile.h src/mem.c src/symbol.c src/reader.c src/interrupt.c | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DHEAP_CELLS=2048 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-Isrc -Ibuild scripts/bytecode-p0-native-compiler-main.c src/compile.c \
		src/mem.c src/symbol.c src/reader.c src/interrupt.c -o $@

bytecode-p0-native-compiler-check: $(BYTECODE_P0_NATIVE_COMPILER_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(BYTECODE_P0_NATIVE_COMPILER_HOST)

$(BYTECODE_VM_M65_OBJ): $(VM_SRCS) src/vm.h src/obj.h src/mem.h src/symbol.h | build
	$(CC_M65) $(CFLAGS) -Isrc -c $(VM_SRCS) -o $@
	@printf 'compiled %s\n' "$@"

bytecode-vm-compile-check: $(BYTECODE_VM_M65_OBJ)

$(VM_SMOKE_HOST): scripts/vm-smoke-main.c $(BYTECODE_P0_C_VECTORS) src/vm.c src/vm.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h src/screen.c src/screen.h | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -Isrc -Ibuild scripts/vm-smoke-main.c src/vm.c src/mem.c src/symbol.c src/interrupt.c src/screen.c -o $@

$(VM_SMOKE_V2_HOST): scripts/vm-smoke-main.c $(BYTECODE_P0_C_VECTORS) src/vm.c src/vm.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h src/screen.c src/screen.h | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -DLISP65_DIALECT_V2 -DLISP65_STRING_ARENA \
		-DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS \
		-Isrc -Ibuild scripts/vm-smoke-main.c src/vm.c src/mem.c src/symbol.c src/interrupt.c src/screen.c -o $@

vm-smoke: $(VM_SMOKE_HOST) $(VM_SMOKE_V2_HOST)
	$(VM_SMOKE_HOST)
	$(VM_SMOKE_V2_HOST)

# GC-Smoke (Host): uebt den Fixpoint-Sweep-GC unter Druck. Schliesst die CI-Luecke, die den
# mega65-GC-Freeze versteckte (bisher nur C64-GC getestet). HW-Entsprechung:
# tools/host-lisp/gc-stress-test.c (docs/mvp-hw-findings.md).
$(GC_SMOKE_HOST): scripts/gc-smoke-main.c src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h | build
	$(HOSTCC) -std=c99 -Wall -DHEAP_CELLS=320 -DGC_ROOTS=128 -DMAX_SYM=160 -DNAMEPOOL=1280 -Isrc scripts/gc-smoke-main.c src/mem.c src/symbol.c src/interrupt.c -o $@

# EXT-Variante (Claude/Lane K, 2026-07-02): winziger Hot-Bereich zwingt die lebende Liste in
# den erweiterten Heap (Host-Simulation in mem.c) — Regressionsgate fuer den Fixpoint-
# Marking-Bugfix (EXT-Zellen muessen ihre Kinder nachmarkieren; ohne Fix FAIL @iter=0).
GC_SMOKE_EXT_HOST := build/gc-smoke-ext-host
$(GC_SMOKE_EXT_HOST): scripts/gc-smoke-main.c src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h | build
	$(HOSTCC) -std=c99 -Wall -DLISP65_EXT_HEAP -DHEAP_CELLS=48 -DEXT_CELLS=512 -DGC_ROOTS=128 -DMAX_SYM=160 -DNAMEPOOL=1280 -Isrc scripts/gc-smoke-main.c src/mem.c src/symbol.c src/interrupt.c -o $@

gc-smoke: $(GC_SMOKE_HOST) $(GC_SMOKE_EXT_HOST)
	$(GC_SMOKE_HOST)

READER_CONFORMANCE_CFLAGS := -std=c99 -Wall -Wextra -fsanitize=address,undefined -fno-omit-frame-pointer -DHEAP_CELLS=8192 -DMAX_SYM=160 -DNAMEPOOL=4096 -Isrc
READER_CONFORMANCE_SRCS := scripts/reader-conformance-main.c src/reader.c src/mem.c src/symbol.c src/interrupt.c

$(READER_CONFORMANCE_HOST): $(READER_CONFORMANCE_SRCS) src/reader.h src/mem.h src/obj.h | build
	$(HOSTCC) $(READER_CONFORMANCE_CFLAGS) -DGC_ROOTS=128 $(READER_CONFORMANCE_SRCS) -o $@

$(READER_CONFORMANCE_ARENA_HOST): $(READER_CONFORMANCE_SRCS) src/reader.h src/mem.h src/obj.h | build
	$(HOSTCC) $(READER_CONFORMANCE_CFLAGS) -DGC_ROOTS=128 -DLISP65_STRING_ARENA -DSTR_ARENA_SIZE=16384 $(READER_CONFORMANCE_SRCS) -o $@

$(READER_ROOT_GUARD_HOST): $(READER_CONFORMANCE_SRCS) src/reader.h src/mem.h src/obj.h | build
	$(HOSTCC) $(READER_CONFORMANCE_CFLAGS) -DGC_ROOTS=4 $(READER_CONFORMANCE_SRCS) -o $@

native-reader-conformance: $(READER_CONFORMANCE_HOST) $(READER_CONFORMANCE_ARENA_HOST) $(READER_ROOT_GUARD_HOST)
	python3 tools/host-lisp/native_reader_conformance.py --driver $(READER_CONFORMANCE_HOST) --root-driver $(READER_ROOT_GUARD_HOST)
	python3 tools/host-lisp/native_reader_conformance.py --driver $(READER_CONFORMANCE_ARENA_HOST)

# Compiler-Smoke (Claude/Lane K, 2026-07-05): verifiziert den geraeteseitigen Bytecode-Compiler
# (src/compile.c, Treewalk-Ersatz) BYTE-EXAKT gegen die erwartete Opcode-Folge. Meilenstein-Gate.
$(COMPILE_SMOKE_HOST): scripts/compile-smoke-main.c $(COMPILE_SRCS) src/compile.h src/mem.c src/symbol.c src/reader.c src/interrupt.c | build
	$(HOSTCC) -std=c99 -Wall -DHEAP_CELLS=320 -DGC_ROOTS=128 -DMAX_SYM=160 -DNAMEPOOL=1280 -Isrc scripts/compile-smoke-main.c $(COMPILE_SRCS) src/mem.c src/symbol.c src/reader.c src/interrupt.c -o $@

compile-smoke: $(COMPILE_SMOKE_HOST)
	$(COMPILE_SMOKE_HOST)

# Compile+Run-Smoke (Claude/Lane K, 2026-07-05): kompiliert eine Form, assembliert zum CodeObject und
# FUEHRT SIE AUF DEM HOST-vm_run AUS -- semantische Ende-zu-Ende-Verifikation (staerker als byte-exakt);
# Pivot fuer M5 Makros (Rumpf zur Compile-Zeit laufen) + M6 REPL-Integration.
$(COMPILE_RUN_HOST): scripts/compile-run-main.c $(COMPILE_SRCS) src/compile.h src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -DMAX_SYM=512 -DNAMEPOOL=4096 -Isrc scripts/compile-run-main.c $(COMPILE_SRCS) src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c -o $@

compile-run: $(COMPILE_RUN_HOST)
	$(COMPILE_RUN_HOST)
	$(GC_SMOKE_EXT_HOST)

# REPL-Session-Prototyp (Claude/Lane K, 2026-07-05, M6 Schritt 1): validiert compile_run_top_form +
# Compiled-Fn-Region + top-level defun (inkl. Rekursion/Redefinition) auf dem Host-vm_run -- die
# geteilte Operation, die REPL-Swap UND load_source teilen (Design §4a). Vor der Geraete-Verdrahtung.
$(REPL_SESSION_HOST): scripts/repl-session-main.c $(COMPILE_REPL_SRCS) src/compile_repl.h $(COMPILE_SRCS) src/compile.h src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -DLISP65_COMPILE_REPL -DMAX_SYM=512 -DNAMEPOOL=4096 -Isrc scripts/repl-session-main.c $(COMPILE_REPL_SRCS) $(COMPILE_SRCS) src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c -o $@

repl-session: $(REPL_SESSION_HOST)
	$(REPL_SESSION_HOST)

$(LCC_INSTALL_DEVICE_SMOKE_HOST): Makefile scripts/lcc-install-device-smoke-main.c $(LCC_GEN) src/eval.c src/eval.h src/lcc_install_overlay.c src/lcc_install_overlay.h src/vm.c src/vm.h src/vm_embed.c src/vm_embed.h src/vm_registry.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/reader.c src/reader.h src/printer.c src/printer.h src/io.c src/io.h src/interrupt.c src/interrupt.h src/screen.c src/screen.h | build
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function -ffunction-sections -fdata-sections -DHEAP_CELLS=8192 -DGC_ROOTS=128 -DLISP65_VM_DIAGNOSTICS -DLISP65_VM -DLISP65_EVAL_CONTROL_SF -DLISP65_EVAL_PRIMS -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL -DLISP65_LCC_INSTALL_CLOSURES -DMAX_SYM=768 -DNAMEPOOL=16384 -DVM_DIR_MAX=128 -Ibuild -Isrc \
		scripts/lcc-install-device-smoke-main.c src/eval.c src/lcc_install_overlay.c src/vm.c src/vm_embed.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c -Wl,--gc-sections -o $@

lcc-install-device-smoke: $(LCC_INSTALL_DEVICE_SMOKE_HOST)
	$(LCC_INSTALL_DEVICE_SMOKE_HOST)

$(LCC_INSTALL_OVERLAY_SMOKE_HOST): Makefile scripts/lcc-install-overlay-main.c src/lcc_install_overlay.c src/lcc_install_overlay.h src/vm.c src/vm.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/reader.c src/reader.h src/interrupt.c src/interrupt.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_VM -DLISP65_LCC_INSTALL -DHEAP_CELLS=2048 -DGC_ROOTS=4096 -DMAX_SYM=192 -DNAMEPOOL=4096 -DVM_DIR_MAX=64 -Isrc \
		scripts/lcc-install-overlay-main.c src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c -o $@

lcc-install-overlay-smoke: $(LCC_INSTALL_OVERLAY_SMOKE_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(LCC_INSTALL_OVERLAY_SMOKE_HOST)

$(VM_BOOT_FASTPATH_SMOKE_HOST): Makefile scripts/vm-boot-fastpath-main.c src/vm_boot_fastpath.c src/vm_boot_fastpath.h src/vm.c src/vm.h src/vm_embed.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/interrupt.c src/interrupt.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_VM -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_RUNTIME_OVERLAY -DLISP65_STDLIB_EXT_METADATA -DLISP65_EXT_HEAP \
		-DHEAP_CELLS=96 -DEXT_CELLS=128 -DGC_ROOTS=128 -DMAX_SYM=128 -DNAMEPOOL=2048 -DVM_DIR_MAX=32 \
		-DLISP65_BOOT_OVERLAY_PROFILE_BUILD_ID=0x12345678UL -DLISP65_BOOT_STDLIB_PROFILE_BUILD_ID=0x12345678UL \
		-DLISP65_BOOT_STDLIB_BANK=5u -DLISP65_BOOT_STDLIB_OFF=0u -DLISP65_BOOT_STDLIB_IMAGE_BYTES=116u \
		-DLISP65_BOOT_STDLIB_IMAGE_CRC16=0x388cu -DLISP65_BOOT_STDLIB_BLOB_BYTES=8u -DLISP65_BOOT_STDLIB_METADATA_BYTES=108u \
		-DLISP65_BOOT_STDLIB_ENTRY_COUNT=1u -DLISP65_BOOT_STDLIB_INDEX_COUNT=3u -DLISP65_BOOT_STDLIB_NODE_COUNT=3u -DLISP65_BOOT_STDLIB_PATCH_COUNT=3u \
		-DLISP65_BOOT_STDLIB_LIT_FIX_COUNT=1u -DLISP65_BOOT_STDLIB_LIT_NIL_COUNT=0u -DLISP65_BOOT_STDLIB_LIT_T_COUNT=0u \
		-DLISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT=1u -DLISP65_BOOT_STDLIB_LIT_CONS_COUNT=0u -DLISP65_BOOT_STDLIB_LIT_LIST_COUNT=0u -DLISP65_BOOT_STDLIB_LIT_STRING_COUNT=1u \
		-DLISP65_BOOT_STDLIB_ENTRIES_OFF=38u -DLISP65_BOOT_STDLIB_INDEX_OFF=46u -DLISP65_BOOT_STDLIB_NODES_OFF=52u \
		-DLISP65_BOOT_STDLIB_PATCHES_OFF=82u -DLISP65_BOOT_STDLIB_STRINGS_OFF=94u -DLISP65_BOOT_STDLIB_STRINGS_BYTES=14u -Isrc \
		scripts/vm-boot-fastpath-main.c src/vm_boot_fastpath.c src/vm.c src/mem.c src/symbol.c src/interrupt.c -o $@

vm-boot-fastpath-smoke: $(VM_BOOT_FASTPATH_SMOKE_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(VM_BOOT_FASTPATH_SMOKE_HOST)

$(ERROR_STATE_SMOKE_HOST): Makefile scripts/error-state-main.c src/error_codes.h src/interrupt.c src/interrupt.h src/vm_runtime_overlay.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -DLISP65_RUNTIME_OVERLAY -Isrc \
		scripts/error-state-main.c src/interrupt.c -o $@

$(ERROR_STATE_NUMERIC_SMOKE_HOST): Makefile scripts/error-state-main.c src/error_codes.h src/interrupt.c src/interrupt.h src/vm_runtime_overlay.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -DLISP65_RUNTIME_OVERLAY \
		-DLISP65_NUMERIC_ERRORS -Isrc scripts/error-state-main.c src/interrupt.c -o $@

error-state-smoke: $(ERROR_STATE_SMOKE_HOST) $(ERROR_STATE_NUMERIC_SMOKE_HOST)
	$(ERROR_STATE_SMOKE_HOST)
	$(ERROR_STATE_NUMERIC_SMOKE_HOST)

# Prelude-Compile-Gate (Claude/Lane K, 2026-07-05, M7-Vorbereitung): prueft, dass
# compile_run_top_form alle defuns des eingebetteten Prelude ohne Treewalk uebersetzen kann.
$(PRELUDE_COMPILE_CHECK_HOST): scripts/prelude-compile-check.c lib/prelude-m1.lisp $(COMPILE_REPL_SRCS) src/compile_repl.h $(COMPILE_SRCS) src/compile.h src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -DMAX_SYM=512 -DNAMEPOOL=4096 -Isrc scripts/prelude-compile-check.c $(COMPILE_REPL_SRCS) $(COMPILE_SRCS) src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c -o $@

prelude-compile-check: $(PRELUDE_COMPILE_CHECK_HOST)
	$(PRELUDE_COMPILE_CHECK_HOST)

# Prelude-Load-Run-Gate (Claude/Lane K, 2026-07-05, M7-Vorbereitung): simuliert
# load_source -> compile_run_top_form fuer alle Prelude-Top-Level-Formen und prueft
# danach Prelude-Funktionen. -DLISP65_COMPILE_REPL aktiviert vm_native_apply (Claude, K/T-Schnitt --
# Codex bitte reviewen): so testet der Harness Higher-order funcall/apply/mapcar OHNE Treewalk (M7-Pfad).
$(PRELUDE_LOAD_RUN_HOST): scripts/prelude-load-run.c lib/prelude-m1.lisp $(COMPILE_REPL_SRCS) src/compile_repl.h $(COMPILE_SRCS) src/compile.h src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c | build
	$(HOSTCC) $(HOST_VM_CFLAGS) -DLISP65_COMPILE_REPL -DMAX_SYM=512 -DNAMEPOOL=4096 -Isrc scripts/prelude-load-run.c $(COMPILE_REPL_SRCS) $(COMPILE_SRCS) src/vm.c src/mem.c src/symbol.c src/reader.c src/interrupt.c src/screen.c -o $@

prelude-load-run: $(PRELUDE_LOAD_RUN_HOST)
	$(PRELUDE_LOAD_RUN_HOST)

$(EVAL_PRIMS_SMOKE_HOST): scripts/eval-prims-smoke.c src/eval.c src/eval.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/reader.c src/reader.h src/printer.c src/printer.h src/interrupt.c src/interrupt.h src/io.c src/io.h | build
	$(HOSTCC) -std=c99 -Wall -DHEAP_CELLS=768 -DGC_ROOTS=256 -DMAX_SYM=256 -DNAMEPOOL=2048 -DLISP65_EVAL_PRIMS -Isrc \
		scripts/eval-prims-smoke.c src/eval.c src/mem.c src/symbol.c src/reader.c src/printer.c src/interrupt.c src/io.c -o $@

eval-prims-smoke: $(EVAL_PRIMS_SMOKE_HOST)
	$(EVAL_PRIMS_SMOKE_HOST)

save-semantics-check: $(S5_SOURCE_D81)
	@for name in $(SAVE_SEMANTICS_SLOTS); do \
		python3 scripts/save-semantics-check.py "$(S5_SOURCE_D81)" "$$name" || exit $$?; \
	done

# Screen-Treiber-Smoke (Claude/Lane K, 2026-07-02): src/screen.c gegen Host-Simulation.
SCREEN_SMOKE_HOST := build/screen-smoke-host
$(SCREEN_SMOKE_HOST): scripts/screen-smoke-main.c src/screen.c src/screen.h | build
	$(HOSTCC) -std=c99 -Wall -Isrc scripts/screen-smoke-main.c src/screen.c -o $@

screen-smoke: $(SCREEN_SMOKE_HOST)
	$(SCREEN_SMOKE_HOST)

$(OUTPUT_SMOKE_HOST): scripts/output-smoke-main.c src/eval.c src/eval.h src/mem.c src/mem.h src/symbol.c src/symbol.h src/reader.c src/reader.h src/printer.c src/printer.h src/interrupt.c src/interrupt.h src/io.c src/io.h | build
	$(HOSTCC) -std=c99 -Wall -DHEAP_CELLS=512 -DGC_ROOTS=128 -DMAX_SYM=128 -DNAMEPOOL=1024 -Isrc \
		scripts/output-smoke-main.c src/eval.c src/mem.c src/symbol.c src/reader.c src/printer.c src/interrupt.c src/io.c -o $@

output-smoke: $(OUTPUT_SMOKE_HOST)
	$(OUTPUT_SMOKE_HOST) > build/output-smoke.out
	python3 scripts/check-output-smoke.py build/output-smoke.out

# Historische C64/GO64-Smokes. Nicht Teil des MEGA65-MVP-Gates.
legacy-xc64-smoke:
	sh scripts/smoke-xc64-legacy.sh

legacy-xc64-prelude-smoke: $(C64PRELUDETESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 prelude: 1" $(C64PRELUDETESTPRG)

legacy-xc64-prelude-gc-smoke: $(C64PRELUDEGCTESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 gc-stress: 12" $(C64PRELUDEGCTESTPRG)

xemu-mega65-prelude-gc-smoke: $(M65PRELUDEGCTESTPRG)
	sh scripts/smoke-xmega65.sh "lisp65 gc-stress: 12" $(M65PRELUDEGCTESTPRG)

legacy-xc64-load-source-smoke: $(C64LOADSOURCETESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 load-source: 15" $(C64LOADSOURCETESTPRG)

legacy-xc64-string-smoke: $(C64STRINGTESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 string: 17" $(C64STRINGTESTPRG)

legacy-xc64-stdlib-smoke: $(C64STDLIBTESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 stdlib: 23" $(C64STDLIBTESTPRG)

legacy-xc64-format-smoke: $(C64FORMATTESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 format: 12" $(C64FORMATTESTPRG)

legacy-xc64-control-smoke: $(C64CONTROLTESTPRG)
	sh scripts/smoke-xc64-legacy.sh "lisp65 control: 7" $(C64CONTROLTESTPRG)

legacy-c64-check: legacy-xc64-smoke legacy-xc64-prelude-smoke legacy-xc64-prelude-gc-smoke legacy-xc64-load-source-smoke legacy-xc64-string-smoke legacy-xc64-stdlib-smoke legacy-xc64-format-smoke legacy-xc64-control-smoke

xemu-f011-load-probe: $(M65F011LOADTESTPRG) f011-defd81-image
	sh scripts/smoke-xmega65-f011-load.sh "lisp65 f011-base:" $(M65F011LOADTESTPRG) $(F011_DEFD81_SDIMG)

xemu-f011-load-smoke: f011-autoload-image
	sh scripts/smoke-xmega65-f011-autoload.sh "lisp65 f011-load: 25" $(F011_AUTOLOAD_SDIMG)

xemu-f011-stdlib-smoke: f011-stdlib-autoload-image
	chunk_count=$$(awk '/^L[0-9][0-9] / { n++ } END { print n + 0 }' $(STDLIB_CHUNK_MANIFEST)); \
	test "$$chunk_count" -gt 0; \
	sh scripts/smoke-xmega65-f011-autoload.sh "lisp65 f011-stdlib-loaded: $$chunk_count" "lisp65 f011-stdlib: $$chunk_count" "lisp65 f011-stdlib-sentinels:" "lisp65 f011-stdlib-bindings:" "lisp65 f011-stdlib-fns:" "lisp65 f011-stdlib-free-cell-sample:" $(F011_STDLIB_AUTOLOAD_SDIMG)

xemu-f011-stdlib-layer-probe: f011-stdlib-layer-probe-image
	chunk_count=$$(awk '/^L[0-9][0-9] / { n++ } END { print n + 0 }' $(STDLIB_CHUNK_MANIFEST)); \
	test "$$chunk_count" -gt 0; \
	DUMP=$(F011_STDLIB_LAYER_PROBE_DUMP) sh scripts/smoke-xmega65-f011-autoload.sh "lisp65 f011-stdlib-loaded: $$chunk_count" "lisp65 f011-stdlib: $$chunk_count" "lisp65 f011-stdlib-layer:" "lisp65 f011-stdlib-fns:" $(F011_STDLIB_LAYER_PROBE_SDIMG)

build:
	mkdir -p build

build/bytecode:
	mkdir -p build/bytecode

build/bytecode/libs:
	mkdir -p build/bytecode/libs

build/demos:
	mkdir -p build/demos

clean:
	rm -rf build $(PRELUDE_GEN) $(LOAD_SMOKE_GEN) $(STDLIB_STRINGS_GEN) $(STDLIB_SEQUENCES_GEN) $(STDLIB_MATH_GEN) $(STDLIB_PLISTS_GEN) $(STDLIB_FORMAT_GEN) $(STDLIB_CONTROL_GEN) $(BYTECODE_VM_M65_OBJ) $(BYTECODE_P0_C_VECTORS) $(VM_SMOKE_HOST) $(VM_SMOKE_V2_HOST) $(OUTPUT_SMOKE_HOST) $(EVAL_PRIMS_SMOKE_HOST)
