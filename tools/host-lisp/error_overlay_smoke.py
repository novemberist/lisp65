#!/usr/bin/env python3
"""Compile and run the allocation-free dedicated L65E renderer contract."""

from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile
import textwrap


ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDERER_SOURCE = ROOT / "src" / "l65e_bcode_ordinal.s"
FULL_SYMBOL = "intern-renderer-missing"


HARNESS = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "error-text-table.h"
#include "error_overlay.h"
#include "printer.h"
#include "symbol.h"
#include "vm_runtime_overlay.h"

#define L65E_SMOKE_CODE(name, code) code,
static const uint8_t omitted_codes[] = {
    LISP65_ERROR_TEXT_OMITTED_BINDINGS(L65E_SMOKE_CODE)
};
#undef L65E_SMOKE_CODE

Cell heap[HEAP_CELLS];
static char output[128];
static uint16_t output_length;
static uint8_t exec_calls;
static uint8_t exec_depth;
static uint8_t transport_mode;
static uint8_t fault_latch;
static uint8_t symname_calls;
static uint8_t allocation_calls;

void emit(char c) { output[output_length++] = c; output[output_length] = 0; }
const char *symname(obj symbol) {
    symname_calls++;
    return IS_SYMI(symbol) ? "intern-renderer-missing" : "gensym";
}

obj alloc(uint8_t type) {
    (void)type;
    allocation_calls++;
    return NIL;
}

vm_runtime_overlay_status vm_runtime_overlay_exec(
    uint8_t slot, void *context, uint8_t *entry_result) {
    exec_calls++;
    if (slot != LISP65_ERROR_OVERLAY_SLOT || !entry_result)
        return VM_RUNTIME_OVERLAY_ERR_ARGUMENT;
    if (exec_depth || transport_mode == 1) return VM_RUNTIME_OVERLAY_ERR_BUSY;
    if (fault_latch || transport_mode == 2) return VM_RUNTIME_OVERLAY_ERR_LATCHED;
    exec_depth++;
    *entry_result = lisp65_error_overlay_entry(context);
    exec_depth--;
    return VM_RUNTIME_OVERLAY_OK;
}

static void clear_observations(void) {
    memset(output, 0, sizeof output);
    output_length = exec_calls = symname_calls = allocation_calls = 0;
}

static int require(int condition, const char *message) {
    if (condition) return 1;
    fprintf(stderr, "error-overlay smoke: %s\n", message);
    return 0;
}

int main(void) {
    lisp65_error_overlay_context context;
    uint8_t before;

    memset(&context, 0xff, sizeof context);
    context.context_tag = 0xdeadbeefUL;
    clear_observations();
    if (!require(lisp65_error_overlay_entry(&context) ==
                     LISP65_ERROR_OVERLAY_ERR_CONTEXT,
                 "wrong context tag was not rejected first") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "wrong context tag caused a side effect")) return 1;

    memset(&context, 0, sizeof context);
    context.context_tag = LISP65_ERROR_OVERLAY_CONTEXT_TAG;
    context.code = 1;
    clear_observations();
    if (!require(lisp65_error_overlay_entry(&context) ==
                     LISP65_ERROR_OVERLAY_ERR_ABI,
                 "wrong context contract was not rejected") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "wrong context contract caused a side effect")) return 1;

    transport_mode = fault_latch = 0;
    clear_observations();
    if (!require(lisp65_error_render_code(1, NIL),
                 "complete-text render failed") ||
        !require(!strcmp(output, "stopped (run/stop)"), "complete text differs") ||
        !require(exec_calls == 1 && !allocation_calls,
                 "complete-text render allocated or re-entered")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_UNDEFINED_FUNCTION,
                                          MK_SYMI(7)),
                 "symbol render failed") ||
        !require(!strcmp(output,
                         "undefined function: intern-renderer-missing"),
                 "complete symbol name differs") ||
        !require(symname_calls == 1 && !allocation_calls,
                 "symbol render did not use the allocation-free accessor")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_VM_UNDEFINED_FUNCTION,
                                          MK_BCODE(0x2a5)),
                 "BCODE ordinal render failed") ||
        !require(!strcmp(output, "vm: undefined function #2a5"),
                 "BCODE ordinal suffix differs") ||
        !require(!symname_calls && !allocation_calls,
                 "BCODE ordinal was treated as a symbol or allocated")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_VM_UNDEFINED_FUNCTION,
                                          MK_BCODE(0)),
                 "zero BCODE ordinal render failed") ||
        !require(!strcmp(output, "vm: undefined function #000"),
                 "zero BCODE ordinal lost fixed width")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_VM_UNDEFINED_FUNCTION,
                                          MK_BCODE(0xfff)),
                 "maximum BCODE ordinal render failed") ||
        !require(!strcmp(output, "vm: undefined function #fff"),
                 "maximum BCODE ordinal differs")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_UNDEFINED_FUNCTION,
                                           MK_BCODE(0x2a5)),
                 "BCODE under a symbol-only code was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "rejected BCODE caused a side effect")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_VM_UNDEFINED_FUNCTION,
                                           (obj)0x0002u),
                 "foreign even detail was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "foreign detail caused a side effect")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_C2_NESTING_DEPTH,
                                          MKFIX(5)),
                 "nesting-depth Fixnum render failed") ||
        !require(!strcmp(output, "eval: nesting depth exceeded 5"),
                 "nesting-depth suffix differs") ||
        !require(!symname_calls && !allocation_calls,
                 "nesting-depth detail resolved a symbol or allocated")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_C2_NESTING_DEPTH,
                                           MKFIX(4)),
                 "nesting-depth Fixnum 4 was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "rejected nesting-depth Fixnum 4 caused a side effect")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_C2_NESTING_DEPTH,
                                           MKFIX(6)),
                 "nesting-depth Fixnum 6 was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "rejected nesting-depth Fixnum 6 caused a side effect")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_C2_NESTING_DEPTH,
                                           MK_SYMI(5)),
                 "nesting-depth symbol detail was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "rejected nesting-depth symbol caused a side effect")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(LISP65_ERR_C2_NESTING_DEPTH,
                                           NIL),
                 "nesting-depth NIL detail was accepted") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "rejected nesting-depth NIL caused a side effect")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(LISP65_ERR_FASL_ENTRIES_OVERFLOW,
                                          MK_SYMI(7)),
                 "compile-sentinel symbol render failed") ||
        !require(!strcmp(output, "compile failedintern-renderer-missing"),
                 "compile-sentinel symbol suffix differs") ||
        !require(symname_calls == 1 && !allocation_calls,
                 "compile-sentinel symbol suffix allocated")) return 1;

    clear_observations();
    if (!require(lisp65_error_render_code(
                     LISP65_ERR_LCC_INVALID_PARAMETER_LIST, MK_SYMI(7)),
                 "invalid-parameter-list symbol render failed") ||
        !require(!strcmp(output, "compile failedintern-renderer-missing"),
                 "invalid-parameter-list symbol suffix differs") ||
        !require(symname_calls == 1 && !allocation_calls,
                 "invalid-parameter-list symbol suffix allocated")) return 1;

    clear_observations();
    context.context_tag = LISP65_ERROR_OVERLAY_CONTEXT_TAG;
    context.context_contract = LISP65_ERROR_OVERLAY_CONTEXT_CONTRACT;
    context.code = omitted_codes[0];
    context.detail = NIL;
    if (!require(lisp65_error_overlay_entry(&context) ==
                     LISP65_ERROR_OVERLAY_ERR_CODE,
                 "textless entry did not return the sparse-code status") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "textless entry caused a side effect")) return 1;

    clear_observations();
    if (!require(!lisp65_error_render_code(
                     omitted_codes[0], NIL),
                 "textless code did not request Ehh fallback") ||
        !require(!output_length && !symname_calls && !allocation_calls,
                 "textless fallback emitted, resolved a symbol, or allocated")) return 1;

    clear_observations();
    exec_depth = 1;
    before = fault_latch;
    if (!require(!lisp65_error_render_code(1, NIL),
                 "active transport did not request Ehh fallback") ||
        !require(exec_calls == 1 && exec_depth == 1 && fault_latch == before,
                 "active fallback recursed or changed the latch") ||
        !require(!output_length && !allocation_calls,
                 "active fallback emitted or allocated")) return 1;
    exec_depth = 0;

    clear_observations();
    fault_latch = 1;
    before = fault_latch;
    if (!require(!lisp65_error_render_code(1, NIL),
                 "latched transport did not request Ehh fallback") ||
        !require(exec_calls == 1 && fault_latch == before,
                 "latched fallback changed latch state") ||
        !require(!output_length && !allocation_calls,
                 "latched fallback emitted or allocated")) return 1;

    puts("error-overlay smoke: ok (cases=20 full-symbol=intern-renderer-missing target-mutations=5 tag-first+text+bcode12-boundaries+depth5-fixnum+textless+alloc0+busy/latch)");
    return 0;
}
"""


def renderer_source_contract(source: str) -> None:
    """Require the linked ABI result to remain the renderer's name pointer."""
    instructions: list[str] = []
    found = False
    for raw_line in source.splitlines():
        code = raw_line.split(";", 1)[0].strip()
        if not found:
            if re.fullmatch(r"jsr\s+symname", code):
                found = True
            continue
        if not code or code.endswith(":"):
            continue
        instructions.append(" ".join(code.split()))
        if len(instructions) == 2:
            break
    if not found:
        raise RuntimeError("L65E renderer no longer calls symname")
    if instructions != ["ldz #0", "lda (__rc2),z"]:
        raise RuntimeError(
            "L65E renderer must consume symname's __rc2/__rc3 result "
            f"directly, observed {instructions!r}"
        )


def renderer_source_mutations(source: str) -> list[str]:
    """Prove the source contract rejects the known pointer-loss class."""
    anchor = "\tjsr\tsymname"
    anchor_at = source.index(anchor)
    prefix = source[:anchor_at]
    renderer_tail = source[anchor_at:]

    def mutate_tail(old: str, new: str) -> str:
        return prefix + renderer_tail.replace(old, new, 1)

    mutations = {
        "restore-incidental-A-store": mutate_tail(
            "\tjsr\tsymname\n",
            "\tjsr\tsymname\n\tsta\t__rc2\n",
        ),
        "restore-incidental-X-store": mutate_tail(
            "\tjsr\tsymname\n",
            "\tjsr\tsymname\n\tstx\t__rc3\n",
        ),
        "nonzero-Z-before-name-read": mutate_tail(
            "\tldz\t#0\n\tlda\t(__rc2),z",
            "\tldz\t#1\n\tlda\t(__rc2),z",
        ),
        "wrong-name-pointer-byte": mutate_tail(
            "\tlda\t(__rc2),z",
            "\tlda\t(__rc3),z",
        ),
        "symname-call-removed": mutate_tail(
            "\tjsr\tsymname",
            "\tjsr\temit",
        ),
    }
    rejected: list[str] = []
    for name, mutation in mutations.items():
        if mutation == source:
            raise RuntimeError(f"renderer mutation did not change source: {name}")
        try:
            renderer_source_contract(mutation)
        except RuntimeError:
            rejected.append(name)
    if len(rejected) != len(mutations):
        missing = sorted(set(mutations) - set(rejected))
        raise RuntimeError(f"renderer source mutations survived: {missing}")
    return rejected


def renderer_object_contract(disassembly: str) -> None:
    """Bind the source rule to the emitted MOS instruction stream."""
    lines = disassembly.splitlines()
    try:
        relocation = next(
            index for index, line in enumerate(lines)
            if re.search(r"R_MOS_ADDR16\s+symname\b", line)
        )
    except StopIteration as exc:
        raise RuntimeError("emitted L65E object has no symname relocation") from exc
    instructions: list[str] = []
    first_read_uses_rc2 = False
    for line in lines[relocation + 1:]:
        instruction = re.match(
            r"^\s*[0-9a-f]+:\s+([a-z]+)\s*(.*?)\s*(?:;.*)?$",
            line,
        )
        if instruction:
            instructions.append(
                " ".join(
                    f"{instruction.group(1)} {instruction.group(2)}".split()
                )
            )
            if len(instructions) > 2:
                break
            continue
        if (
            len(instructions) == 2
            and re.search(r"R_MOS_ADDR8\s+__rc2\b", line)
        ):
            first_read_uses_rc2 = True
    if (
        instructions[:2] != ["ldz #$0", "lda ($0),z"]
        or not first_read_uses_rc2
    ):
        raise RuntimeError(
            "emitted L65E object does not consume symname's __rc2/__rc3 "
            f"pointer directly: {instructions[:2]!r}, rc2={first_read_uses_rc2}"
        )


def main() -> int:
    renderer_source = RENDERER_SOURCE.read_text(encoding="ascii")
    renderer_source_contract(renderer_source)
    rejected = renderer_source_mutations(renderer_source)
    with tempfile.TemporaryDirectory(prefix="l65e-smoke-") as tmp_name:
        tmp = pathlib.Path(tmp_name)
        subprocess.run(
            [
                "python3",
                str(ROOT / "tools" / "host-lisp" / "error_text_table.py"),
                "prepare",
                "--spec",
                str(ROOT / "config" / "error-texts.json"),
                "--profile",
                "workbench",
                "--build-id",
                "0x12345678",
                "--header",
                str(tmp / "error-text-table.h"),
                "--binary",
                str(tmp / "error-text-table.bin"),
            ],
            cwd=ROOT,
            check=True,
        )
        (tmp / "main.c").write_text(
            textwrap.dedent(HARNESS).lstrip(), encoding="ascii"
        )
        exe = tmp / "error-overlay-smoke"
        subprocess.run(
            [
                "cc",
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DLISP65_ERROR_OVERLAY",
                "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
                "-DLISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID=0x12345678UL",
                "-I",
                str(tmp),
                "-I",
                str(ROOT / "src"),
                str(ROOT / "src" / "error_overlay.c"),
                str(tmp / "main.c"),
                "-o",
                str(exe),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(exe)], cwd=ROOT, check=True)

        mos_cc = ROOT / "tools" / "llvm-mos" / "bin" / "mos-mega65-clang"
        if mos_cc.exists():
            mos_object = tmp / "error-overlay.o"
            mos_ordinal_object = tmp / "l65e-bcode-ordinal.o"
            subprocess.run(
                [
                    str(mos_cc),
                    "-std=c11",
                    "-Oz",
                    "-fno-lto",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-DLISP65_ERROR_OVERLAY",
                    "-DLISP65_RUNTIME_OVERLAY",
                    "-DLISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID=0x12345678UL",
                    "-I",
                    str(tmp),
                    "-I",
                    str(ROOT / "src"),
                    "-c",
                    str(ROOT / "src" / "error_overlay.c"),
                    "-o",
                    str(mos_object),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(
                [
                    str(mos_cc),
                    "-c",
                    str(ROOT / "src" / "l65e_bcode_ordinal.s"),
                    "-o",
                    str(mos_ordinal_object),
                ],
                cwd=ROOT,
                check=True,
            )
            section_output = subprocess.run(
                [str(ROOT / "tools" / "llvm-mos" / "bin" / "llvm-objdump"),
                 "-h", str(mos_object), str(mos_ordinal_object)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            sections = {}
            for line in section_output.splitlines():
                fields = line.split()
                if len(fields) >= 3 and fields[1].startswith(".lisp65_rt_l65e"):
                    sections[fields[1]] = (
                        sections.get(fields[1], 0) + int(fields[2], 16)
                    )
            code_bytes = sections.get(".lisp65_rt_l65e", 0)
            table_bytes = sections.get(".lisp65_rt_l65e_data", 0)
            total_bytes = code_bytes + table_bytes
            hard_limit = 1320
            symbol_output = subprocess.run(
                [str(ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"),
                 "-S", "--size-sort", str(mos_object),
                 str(mos_ordinal_object)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            disassembly = subprocess.run(
                [
                    str(
                        ROOT / "tools" / "llvm-mos" / "bin" / "llvm-objdump"
                    ),
                    "-dr",
                    "--no-show-raw-insn",
                    str(mos_ordinal_object),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            renderer_object_contract(disassembly)
            sizes = [line for line in symbol_output.splitlines()
                     if "l65e_" in line or "lisp65_error_overlay_entry" in line]
            if total_bytes > hard_limit:
                raise RuntimeError(
                    f"WorkBench L65E slice is {total_bytes} bytes, limit {hard_limit}; "
                    + "; ".join(sizes)
                )
            print(
                "error-overlay MOS workbench sections: "
                f"code={code_bytes} table={table_bytes} total={total_bytes} "
                f"headroom={hard_limit - total_bytes}"
            )
            print("error-overlay MOS symbols: " + "; ".join(sizes))
            print(
                "error-overlay target pointer contract: "
                f"ok (mutations={len(rejected)} full-symbol={FULL_SYMBOL})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
