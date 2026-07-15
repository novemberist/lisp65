# Focused Stage-3 host gate. Invoke without changing the main Makefile:
#   make -f Makefile -f mk/v2-string-caps.mk v2-string-caps-host-check

V2_STRING_CAPS_HOST := build/v2-string-caps-host
V2_STRING_CAPS_CFLAGS := -std=c99 -Wall -Wextra -Werror \
	-fsanitize=address,undefined -fno-omit-frame-pointer \
	-DLISP65_STRING_ARENA -DLISP65_DIALECT_V2 -DLISP65_V2_NATIVE_STRING_CODECS \
	-DSTR_ARENA_SIZE=64 \
	-DHEAP_CELLS=96 -DGC_ROOTS=8

.PHONY: v2-string-caps-host-check

$(V2_STRING_CAPS_HOST): scripts/v2-string-caps-main.c src/mem.c src/mem.h src/obj.h src/symbol.h | build
	$(HOSTCC) $(V2_STRING_CAPS_CFLAGS) -Isrc scripts/v2-string-caps-main.c src/mem.c -o $@

v2-string-caps-host-check: $(V2_STRING_CAPS_HOST)
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 $(V2_STRING_CAPS_HOST)
