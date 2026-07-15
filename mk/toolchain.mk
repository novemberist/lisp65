# Compiler and image-tool entry points shared by all build profiles.

LLVM    := tools/llvm-mos/bin
CC_M65  := $(LLVM)/mos-mega65-clang
LEGACY_CC_C64 := $(LLVM)/mos-c64-clang
HOSTCC  ?= cc
C1541   ?= c1541
CFLAGS  := -Os -Wall
HOST_VM_CFLAGS ?= -std=c99 -Wall -DHEAP_CELLS=2048 -DGC_ROOTS=1024 -DLISP65_VM_DIAGNOSTICS -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS -DLISP65_SCREEN_WRITE_STRING -DLISP65_VM_GLOBAL_PRIMS
M65VMSTDLIB_NM ?= $(LLVM)/llvm-nm
M65VMSTDLIB_SIZE ?= $(LLVM)/llvm-size
ETHERLOAD := tools/m65tools/etherload
