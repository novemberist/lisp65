#!/usr/bin/env python3
"""Price the two v1.9 native-prompt editor compositions, host-only.

The price is deliberately taken against the accepted Block-A pair.  B-light
has two owners to compose: the resident C prompt loop and the Bank-2 line
editor.  The winning form gives the complete prompt row to the editor while
it is active.  B-full is priced as the current Comfort payload, but remains
unselectable until the separately owner-gated Block C closes.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as COMPILER  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
import c2_v180_substrate_device_result as DEVICE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.9.0-native-prompt-editor-pricing-report.md"
RECEIPT = ARCH / "c2.3-v1.9-native-prompt-editor-pricing-receipt.json"
BLOCK_A = ARCH / "c2.3-v1.9-native-capture-client-card-r1-receipt.json"
BLOCK_A_BUILD = ROOT / "build/c2.3/v1.9-native-capture-client-card-r1"
BLOCK_A_PREFLIGHT = ROOT / "build/c2.3/v1.9-native-capture-client-card-r1-preflight"
ELF = BLOCK_A_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BLOCK_A_BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BLOCK_A_BUILD / "wplto/resolved-profile.txt"
PLANE = BLOCK_A_PREFLIGHT / "setup-owned/static-plane/narrow-static"
MANIFEST = PLANE / "stdlib-p0.manifest.json"
HEADER = PLANE / "stdlib-p0.h"
ARTIFACTS = PLANE / "product/substitution-artifacts.json"
EDITOR = BLOCK_A_PREFLIGHT / "sources/stdlib-read-line.lisp"
COMFORT = ROOT / "lib/repl-comfort.lisp"
SEXP = ROOT / "lib/sexp-depth.lisp"
REPL = ROOT / "src/repl.c"
CAPACITY = ARCH / "c2.3-v1.8.0-substrate-d-session-result-receipt.json"
BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-pricing"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMPILER_BIN = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
FORMAT = "lisp65-c2-v190-native-prompt-editor-pricing-v1"
STATUS = "PASS: BLOCK-B VARIANTS PRICED; OWNER CHOICE REQUIRED"
EVIDENCE_COMMIT = "b9e5b8c6"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def evidence_bytes(path: Path) -> bytes:
    """Read a pricing-era input without rebinding sealed evidence to HEAD."""
    return subprocess.run(
        ["git", "show", f"{EVIDENCE_COMMIT}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def evidence_bind(path: Path) -> dict[str, Any]:
    raw = evidence_bytes(path)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


TAIL_SOURCE = r'''(defun %rl-screen-tail (codes index column stop cursor row)
  (if (= row -2)
      (progn
        (write-char 19)
        (dotimes (line stop nil) (write-char 17)))
      (let* ((native (< row -34))
             (prompted (< row -2))
             (actual-row (if native (- 0 (+ row 34)) (- 0 (+ row 2)))))
        (if (and prompted (= cursor -1))
            (%rl-render nil 0 0 (car (screen-size)) -2 actual-row)
            (if (and prompted (< column 0))
                (%rl-screen-tail (if codes (cdr codes) nil)
                                 (+ index 1) (+ column 1) stop cursor row)
                (let* ((origin (if native 8 (if prompted 5 0))))
                  (%rl-render codes index (+ column origin) (+ stop origin)
                              cursor (if prompted actual-row row))))))))
'''

READ_SOURCE = r'''(defun read-line (&rest prompt)
  (progn
    (poke 255 141 255)
    (poke 255 140 0)
    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))
    (poke 255 141 0)
    (let* ((size (screen-size))
           (full-columns (car size))
           (screen-row (- (car (cdr size)) 1))
           (native (if prompt 't nil))
           (columns (if native (- full-columns 8) full-columns))
           (row (if native (- 0 (+ screen-row 34)) screen-row))
           (head (cons 0 nil))
           (state (list head head head 0 0 0 columns row))
           (answer
            (progn
              (if native (%native-prompt screen-row) nil)
              (%rl-screen-tail nil 0 0 columns 0 row)
              (%read-line-loop state))))
      (progn
        (poke 255 141 255)
        answer))))
'''

HELPERS = r'''(defun %native-prompt (row)
  (progn
    (%rl-screen-tail nil 0 0 row 0 -2)
    (write-string "lisp65> ")))

(defun %native-read-line () (read-line (quote native)))

'''


def editor_candidate() -> str:
    base = EDITOR.read_text(encoding="utf-8")
    value = PRICE.replace_defun(base, "%rl-screen-tail", TAIL_SOURCE)
    value = PRICE.replace_defun(value, "read-line", READ_SOURCE)
    marker = "(defun read-line "
    require(value.count(marker) == 1, "read-line insertion seam drift")
    return value.replace(marker, HELPERS + marker, 1)


def direct_bridge_block(macro: str) -> str:
    return rf'''#ifdef {macro}
static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {{
    obj line;
    uint16_t length;
    lisp65_error_code code;
    vm_status = VM_OK;
    line = vm_run_dir({macro}, NULL, 0);
    if (vm_status != VM_OK && vm_status != VM_HALT) {{
        code = vm_status_error_code(vm_status);
        vm_status = VM_OK;
        lisp_abort_code(code);
        return 0;
    }}
    vm_status = VM_OK;
    if (!IS_PTR(line) || cell_type(line) != T_STR) {{
        lisp_abort_code(LISP65_ERR_VM_TYPE);
        return 0;
    }}
    length = str_len(line);
    if (length >= (uint16_t)(max - *np)) {{
        lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);
        return 0;
    }}
    *np = (uint8_t)(*np + str_copy_out(line, buf + *np, length));
    return 1;
}}
#else
'''


def dynamic_bridge_block(macro: str) -> str:
    return rf'''#ifdef {macro}
static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {{
    obj name, line;
    uint16_t length;
    lisp65_error_code code;
    if (!sym_lookup("read-line", &name)) {{
        lisp_abort_code(LISP65_ERR_UNDEFINED_FUNCTION);
        return 0;
    }}
    vm_status = VM_OK;
    line = vm_native_apply(name, NIL);
    if (vm_status != VM_OK && vm_status != VM_HALT) {{
        code = vm_status_error_code(vm_status);
        vm_status = VM_OK;
        lisp_abort_code(code);
        return 0;
    }}
    vm_status = VM_OK;
    if (!IS_PTR(line) || cell_type(line) != T_STR) {{
        lisp_abort_code(LISP65_ERR_VM_TYPE);
        return 0;
    }}
    length = str_len(line);
    if (length >= (uint16_t)(max - *np)) {{
        lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);
        return 0;
    }}
    *np = (uint8_t)(*np + str_copy_out(line, buf + *np, length));
    return 1;
}}
#else
'''


def bridge_source(*, dynamic: bool, composed: bool) -> str:
    source = evidence_bytes(REPL).decode()
    macro = "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY"
    include = ("#if defined(LISP65_COMPILE_REPL) || "
               "defined(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY)")
    replacement = (include + " \\" + "\n    || defined(" + macro + ")")
    require(source.count(include) == 1, "VM include feature seam drift")
    source = source.replace(include, replacement, 1)
    start = source.index(
        "static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {")
    end = source.index("\nvoid repl(void)", start)
    old = source[start:end]
    block = (dynamic_bridge_block(macro) if dynamic
             else direct_bridge_block(macro))
    source = source[:start] + block + old + "\n#endif\n" + source[end:]
    if composed:
        seam = ('        emit_str("lisp65> ");\n'
                '        st = read_line(buf, &n, BUF_MAX);\n'
                "        if (st == 1) emit('\\n');")
        changed = ('#ifndef ' + macro + '\n'
                   '        emit_str("lisp65> ");\n'
                   '#endif\n'
                   '        st = read_line(buf, &n, BUF_MAX);\n'
                   '#ifndef ' + macro + '\n'
                   "        if (st == 1) emit('\\n');\n"
                   '#endif')
        require(source.count(seam) == 1, "native prompt ownership seam drift")
        source = source.replace(seam, changed, 1)
    return source


def manifest_projection() -> dict[str, Any]:
    manifest = load(MANIFEST)
    names = [row["name"] for row in manifest["entries"]]
    require(len(names) == len(set(names)) == 396
            and names.count("read-line") == 1
            and "%native-read-line" not in names,
            "Block-A directory population drift")
    at = names.index("read-line")
    names[at:at] = ["%native-prompt", "%native-read-line"]
    ordinal = names.index("%native-read-line")
    require(ordinal == at + 1, "private native entry is not derived at seam")
    return {"predecessor_objects": len(manifest["entries"]),
            "successor_objects": len(names), "read_line_predecessor_ordinal": at,
            "native_entry_successor_ordinal": ordinal,
            "authority": "candidate directory names.index, never a literal"}


def profile_definitions() -> tuple[list[str], list[str]]:
    artifacts = load(ARTIFACTS)
    features: list[str] = []
    for line in PROFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("feature_defines="):
            features = [row for row in line.split("=", 1)[1].split(",") if row]
    require(features and len(features) == len(set(features)),
            "materialized feature profile absent/duplicated")
    definitions = PRODUCT.definitions(artifacts) + features
    require(len(definitions) == len(set(definitions))
            and "LISP65_V160_INPUT_CAPTURE" in definitions
            and "LISP65_V160_INPUT_HYBRID" in definitions,
            "Block-A target definition world drift")
    return definitions, features


def header_projection(ordinal: int) -> str:
    source = HEADER.read_text(encoding="utf-8")
    marker = "#define LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY "
    line = next(row for row in source.splitlines() if row.startswith(marker))
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{ordinal}u")
    require(define not in source, "pricing macro leaked into product header")
    return source.replace(line, line + "\n" + define, 1)


def section_sizes(path: Path) -> dict[str, int]:
    output = run([str(READOBJ), "--sections", str(path.relative_to(ROOT))],
                 f"section read {path.name}")
    rows: dict[str, int] = {}
    for name in (".text.repl", ".rodata.str1.1", ".bss.repl.buf"):
        match = re.search(r"Name: " + re.escape(name)
                          + r" .*?\n(?:.*\n)*?\s+Size: (\d+)", output)
        require(match is not None, f"target section absent: {name}")
        rows[name] = int(match.group(1))
    return rows


def target_codegen(projection: dict[str, Any]) -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    sources = {
        "baseline": evidence_bytes(REPL).decode(),
        "dynamic-uncomposed": bridge_source(dynamic=True, composed=False),
        "composed-private-entry": bridge_source(dynamic=False, composed=True),
    }
    (BUILD / "stdlib-p0.h").write_text(
        header_projection(projection["native_entry_successor_ordinal"]),
        encoding="utf-8")
    definitions, features = profile_definitions()
    results: dict[str, Any] = {}
    for name, source in sources.items():
        c_path = BUILD / f"repl-{name}.c"
        obj = BUILD / f"repl-{name}.native.o"
        c_path.write_text(source, encoding="utf-8")
        argv = [str(COMPILER_BIN), "-Oz", "-Wall", "-fno-lto",
                "-ffile-compilation-dir=.", "-fdebug-compilation-dir=.",
                "-fcoverage-compilation-dir=.", "-I", "src", "-I",
                str(BUILD.relative_to(ROOT)),
                *[f"-D{row}" for row in definitions], "-c",
                str(c_path.relative_to(ROOT)), "-o", str(obj.relative_to(ROOT))]
        output = run(argv, f"target price compile {name}")
        results[name] = {"source": bind(c_path), "object": bind(obj),
                         "sections": section_sizes(obj),
                         "warnings": [row for row in output.splitlines()
                                      if "warning:" in row]}
    expected = {
        "baseline": {".text.repl": 616, ".rodata.str1.1": 14,
                     ".bss.repl.buf": 192},
        "dynamic-uncomposed": {".text.repl": 690,
                               ".rodata.str1.1": 24,
                               ".bss.repl.buf": 192},
        "composed-private-entry": {".text.repl": 626,
                                   ".rodata.str1.1": 5,
                                   ".bss.repl.buf": 192},
    }
    require({key: row["sections"] for key, row in results.items()} == expected,
            "full materialized-profile target price drift")
    base = expected["baseline"]
    for key in ("dynamic-uncomposed", "composed-private-entry"):
        row = expected[key]
        results[key]["delta"] = {
            "text_bytes": row[".text.repl"] - base[".text.repl"],
            "rodata_bytes": row[".rodata.str1.1"] - base[".rodata.str1.1"],
            "bss_bytes": row[".bss.repl.buf"] - base[".bss.repl.buf"],
            "aggregate_alloc_bytes":
                row[".text.repl"] + row[".rodata.str1.1"]
                - base[".text.repl"] - base[".rodata.str1.1"],
        }
    return {"compiler_driver": {
                "path": COMPILER_BIN.relative_to(ROOT).as_posix(),
                "resolved_executable": bind(COMPILER_BIN.resolve())},
            "definitions": len(definitions),
            "materialized_features": features, "feature_count": len(features),
            "results": results,
            "discarded_partial_profile_probe": {
                "reason": "only immediate feature subset, not process truth",
                "direct_text_delta_bytes": 30,
                "dynamic_aggregate_delta_bytes": 86,
                "accepted_as_price": False}}


def compile_objects(source: str, functions: list[str]) -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD / ("objects-" + hashlib.sha256(source.encode()).hexdigest()[:12]
                    + ".lisp")
    path.write_text(source, encoding="utf-8")
    suite = {"format": "lisp65-bytecode-p0-stdlib-subset-v1",
             "name": "v19-prompt-price", "sources": [str(path)],
             "functions": functions, "require_all_defuns": False,
             "strict_arity": True, "abi_profile": "dialect-v2",
             "max_call_args": 12,
             "cases": [{"name": "compile-only", "expr": "nil",
                        "expect": "nil"}]}
    result = P0._compile_suite(suite, include_cases=False)
    bundle = result[5]
    return {"source": bind(path),
            "objects": {row.name: row.obj_len for row in bundle.entries},
            "code_bytes": len(bundle.blob),
            "directory_bytes": len(bundle.directory_bytes())}


def editor_price() -> dict[str, Any]:
    base = EDITOR.read_text(encoding="utf-8")
    candidate = editor_candidate()
    before = compile_objects(base, ["%rl-screen-tail", "read-line"])
    after = compile_objects(candidate, ["%rl-screen-tail", "read-line",
                                        "%native-prompt", "%native-read-line"])
    require(before["objects"] == {"%rl-screen-tail": 185, "read-line": 177}
            and after["objects"] == {"%rl-screen-tail": 212,
                                      "read-line": 235,
                                      "%native-prompt": 32,
                                      "%native-read-line": 16},
            "B-light editor object price drift")
    delta = ((after["code_bytes"] + after["directory_bytes"])
             - (before["code_bytes"] + before["directory_bytes"]))
    require(delta == 147 and max(after["objects"].values()) < 255,
            "B-light Bank-2 price/ceiling drift")
    return {"before": before, "after": after,
            "code_delta_bytes": after["code_bytes"] - before["code_bytes"],
            "directory_delta_bytes": (after["directory_bytes"]
                                      - before["directory_bytes"]),
            "static_plane_delta_bytes": delta,
            "new_private_names": ["%native-prompt", "%native-read-line"],
            "symbol_slots_delta": 2, "namepool_bytes_delta": 33,
            "all_objects_below_255": True}


def live_suite(source_path: Path, expr: str, expected: str,
               events: list[int]) -> dict[str, Any]:
    base = EDITOR.resolve()
    suite = PRICE.combined_suite(base, expr, expected, events)
    PRICE.live_function_directory(suite, base)
    suite["sources"] = [str(source_path.resolve())
                        if Path(row).resolve() == base else row
                        for row in suite["sources"]]
    source_text = source_path.read_text(encoding="utf-8")
    for name in ("%native-prompt", "%native-read-line"):
        if f"(defun {name} " in source_text and name not in suite["functions"]:
            suite["functions"].append(name)
    suite["cases"] = [{"name": "native-prompt-composed", "expr": expr,
                       "expect": json.dumps(expected), "key_events": events,
                       "max_steps": 1_000_000}]
    return suite


def frame_row(source_path: Path, expr: str, expected: str,
              events: list[int]) -> str:
    suite = live_suite(source_path, expr, expected, events)
    (heap, _names, _code, flags, resident, _bundle, directory,
     _cases, entries, _inliner) = P0._compile_suite(suite)
    macros = P0._macro_symbol_objs(heap, flags, resident)
    abi_profile, abi_ledger = P0._suite_abi(suite)
    vm = DISPLAY.FrameVM(
        heap=heap.clone(), directory=directory, macro_symbols=macros,
        max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
        key_events=events, private_key_event_modes=True,
        abi_profile=abi_profile, abi_ledger=abi_ledger, stop_at_return=True)
    try:
        vm.run(directory[heap.intern(entries[0])], [])
    except DISPLAY.AtReturn:
        pass
    else:
        raise PricingError("framebuffer witness missed editor handoff")
    require(vm.active_row is not None, "framebuffer row absent")
    return vm.active_row


def framebuffer_gate(candidate: str) -> dict[str, Any]:
    candidate_path = BUILD / "stdlib-read-line-b-light.lisp"
    candidate_path.write_text(candidate, encoding="utf-8")
    edited = frame_row(candidate_path, "(%native-read-line)", "abc",
                       [ord("a"), ord("c"), 157, ord("b"), 13])
    ordinary_candidate = frame_row(candidate_path, "(read-line)", "abc",
                                   [ord("a"), ord("b"), ord("c"), 13])
    ordinary_base = frame_row(EDITOR, "(read-line)", "abc",
                              [ord("a"), ord("b"), ord("c"), 13])
    require(edited == "lisp65> abc".ljust(80)
            and ordinary_candidate == ordinary_base,
            "composed/native or ordinary framebuffer price gate red")
    return {"native_prompt_and_edited_line": edited.rstrip(),
            "cursor_left_insert_result": "abc",
            "ordinary_read_line_before": ordinary_base.rstrip(),
            "ordinary_read_line_after": ordinary_candidate.rstrip(),
            "ordinary_read_line_framebuffer_identical": True,
            "owner": "Bank-2 editor owns prompt, input, and handoff while active"}


def block_a_capacity() -> dict[str, int]:
    value = load(CAPACITY)["D5"]["free"]
    require(value == {"symbol_slots": 113, "namepool_bytes": 1506},
            "released D5 capacity authority drift")
    return value


def b_light(codegen: dict[str, Any], editor: dict[str, Any],
            framebuffer: dict[str, Any]) -> dict[str, Any]:
    delta = codegen["results"]["composed-private-entry"]["delta"]
    before = block_a_capacity()
    after = {"symbol_slots": before["symbol_slots"] - 2,
             "namepool_bytes": before["namepool_bytes"] - 33}
    require(delta == {"text_bytes": 10, "rodata_bytes": -9,
                      "bss_bytes": 0, "aggregate_alloc_bytes": 1}
            and after == {"symbol_slots": 111, "namepool_bytes": 1473},
            "B-light aggregate/capacity price drift")
    plane_before = 47335
    plane_after = plane_before + editor["static_plane_delta_bytes"]
    return {
        "form": ("private artifact-derived zero-argument entry calls the public "
                 "read-line in native-prompt mode; other profiles retain the "
                 "C collector byte-for-byte"),
        "resident_target_projection": {
            "ordinary_text_before_free_bytes": 60,
            "permanent_text_floor_bytes": 32,
            "text_delta_bytes": delta["text_bytes"],
            "rodata_delta_bytes": delta["rodata_bytes"],
            "aggregate_alloc_delta_bytes": delta["aggregate_alloc_bytes"],
            "projected_free_bytes": 50,
            "projected_margin_over_floor_bytes": 18,
            "bss_delta_bytes": 0,
            "final_LTO_requirement": ("exact linked delta and >=32 free bytes; "
                                      "target-object projection is not a link claim")},
        "bank2": {"plane_before_bytes": plane_before,
                  "plane_after_bytes": plane_after,
                  "largest_hole_before_bytes": 16331,
                  "largest_hole_after_bytes": 16331
                    - editor["static_plane_delta_bytes"],
                  **editor},
        "capacity": {"before": before, "after": after,
                     "release_floor": {"symbol_slots": 32,
                                       "namepool_bytes": 384},
                     "margin_over_floor": {"symbol_slots": 79,
                                           "namepool_bytes": 1089}},
        "semantics": {
            "public_read_line_runtime_call": True,
            "prompt": "lisp65> ", "prompt_columns": 8,
            "native_buffer_limit": 191,
            "overlong_line": "visible reader-invalid-token; never truncate/evaluate",
            "no_editor_profile": "old C collector byte-identical by preprocessor",
            "framebuffer": framebuffer},
        "direct_fit": True,
        "implementation_budget_needed": "one owner-authorized WPLTO and product link",
    }


def b_full(block_a: dict[str, Any]) -> dict[str, Any]:
    source = COMFORT.read_text(encoding="utf-8") + "\n" + SEXP.read_text(
        encoding="utf-8")
    functions = ["%repl-read", "%repl-prompt", "%repl-step", "repl",
                 "%ide-line-net-depth"]
    objects = compile_objects(source, functions)
    require(objects["objects"] == {"%repl-read": 234, "%repl-prompt": 80,
                                    "%repl-step": 251, "repl": 250,
                                    "%ide-line-net-depth": 142}
            and objects["code_bytes"] == 957
            and objects["directory_bytes"] == 35,
            "current B-full object price drift")
    before = block_a_capacity()
    names = ["%ide-line-net-depth", "%repl-prompt", "%repl-read",
             "%repl-step", "repl", "repl-comfort"]
    name_bytes = sum(len(row.encode("ascii")) + 1 for row in names)
    after = {"symbol_slots": before["symbol_slots"] - len(names),
             "namepool_bytes": before["namepool_bytes"] - name_bytes}
    response = block_a["final_product"]["v1_9_block_A"]["client_walls"][
        "hybrid"]["responsiveness"]
    contract = load(ROOT / "config/c2-v160-input-service-hybrid-contract.json")[
        "responsiveness"]
    prompt_delta = (32 * contract["calibration_cycles_per_vm_step"]
                    / contract["cycles_per_frame"] / 40)
    frames = response["frames_per_character"] + prompt_delta
    rate = 1.0 / frames
    require(name_bytes == 73 and after == {"symbol_slots": 107,
                                           "namepool_bytes": 1433}
            and frames < 0.8 and (rate - 1.0) * 100 >= 25,
            "B-full capacity/responsiveness price drift")
    return {
        "form": ("canonical Comfort composition over the Block-A editor; the "
                 "single missing indentation helper rides the same library so "
                 "historical v16core cannot overwrite the armed read-line"),
        "product_resident_delta_bytes": 0,
        "disk_library": {**objects, "payload_bytes": 992,
                         "new_names": names, "symbol_slots_delta": len(names),
                         "namepool_bytes_delta": name_bytes},
        "capacity": {"before": before, "after": after,
                     "margin_over_floor": {"symbol_slots": 75,
                                           "namepool_bytes": 1049}},
        "responsiveness": {
            "stationary_frames_per_character": response["frames_per_character"],
            "forty_character_prompt_amortized_frames_per_character": frames,
            "service_events_per_frame": rate,
            "margin_percent": (rate - 1.0) * 100,
            "wall": {"maximum_frames_per_character": 0.8,
                     "minimum_margin_percent": 25.0}},
        "direct_fit": True,
        "selectable_now": False,
        "gate": ("Block C owner acceptance, first-fault latch price, and current "
                 "hardware acceptance are not included in this core price"),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["comparison"]["recommendation"] == "B-light"
            and value["variants"]["B_light"]["direct_fit"] is True
            and value["variants"]["B_light"]["semantics"][
                "framebuffer"]["native_prompt_and_edited_line"] == "lisp65> abc"
            and value["variants"]["B_light"]["semantics"][
                "overlong_line"].startswith("visible")
            and value["variants"]["B_full"]["selectable_now"] is False
            and value["variants"]["B_light"]["resident_target_projection"][
                "projected_free_bytes"] >= 32,
            "pricing claim validation red")


def mutation_selftest(value: dict[str, Any]) -> dict[str, str]:
    cases = {
        "registry-only-no-native-route": lambda x: x["variants"]["B_light"].update(
            direct_fit=False),
        "prompt-outside-editor-owner": lambda x: x["variants"]["B_light"][
            "semantics"]["framebuffer"].update(
                native_prompt_and_edited_line="abc"),
        "silent-192-byte-truncation": lambda x: x["variants"]["B_light"][
            "semantics"].update(overlong_line="truncate then evaluate"),
        "spend-below-text-floor": lambda x: x["variants"]["B_light"][
            "resident_target_projection"].update(projected_free_bytes=31),
        "select-Comfort-before-Block-C": lambda x: x["variants"]["B_full"].update(
            selectable_now=True),
    }
    rejected: dict[str, str] = {}
    for name, mutate in cases.items():
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PricingError as error:
            rejected[name] = str(error)
        else:
            raise PricingError(f"Block-B pricing mutation survived: {name}")
    return rejected


def derive() -> dict[str, Any]:
    block_a = load(BLOCK_A)
    require(block_a["status"] ==
            "PASS: V1.9 PAGE-CONGRUENT NATIVE CAPTURE CLIENT GREEN"
            and bind(ELF)["sha256"] ==
                "0c3282c9625e47f9549833c9f0382a2ba26fc967f8dafc473d382c47c80fee82"
            and bind(PRG)["sha256"] ==
                "13eb21566cc89e954bc50d5bb62b56aa8879c728cbcf845a221514192da177f0",
            "accepted Block-A pricing world drift")
    topology = DEVICE.native_prompt_model(ELF.resolve())
    require(topology["input_owner"].endswith("inline C collector")
            and topology["indirect_editor_calls"] == 0
            and topology["boot_or_runtime_editor_rebind"] is False,
            "native prompt already has an editor seam")
    projection = manifest_projection()
    codegen = target_codegen(projection)
    editor = editor_price()
    framebuffer = framebuffer_gate(editor_candidate())
    light = b_light(codegen, editor, framebuffer)
    full = b_full(block_a)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-28", "status": STATUS,
        "authority": {"pre_plan": evidence_bind(PLAN),
                      "Block_A_receipt": bind(BLOCK_A),
                      "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
                      "D5_capacity": bind(CAPACITY)},
        "inputs": {"native_repl": evidence_bind(REPL),
                   "candidate_editor": bind(EDITOR),
                   "candidate_manifest": bind(MANIFEST),
                   "candidate_header": bind(HEADER), "Comfort": bind(COMFORT),
                   "sexp_helper": bind(SEXP), "resolved_profile": bind(PROFILE),
                   "substitution_artifacts": bind(ARTIFACTS),
                   "pricing_driver": evidence_bind(Path(__file__).resolve())},
        "current_topology": topology,
        "directory_projection": projection,
        "target_codegen": codegen,
        "variants": {"B_light": light, "B_full": full},
        "comparison": {
            "B_light": ("+1 target-object resident projection, +147 static "
                        "Bank-2 bytes, 2 slots/33 name bytes; selectable now"),
            "B_full": ("0 product-resident bytes, 992-byte conditional disk "
                       "payload, 6 slots/73 name bytes; Block C closed"),
            "recommendation": "B-light",
            "reason": ("it closes the release-carrying native-prompt Known Issue "
                       "without Comfort risk and preserves a composed framebuffer"),
            "decision_authority": "owner Block-B touchpoint"},
        "verification": {"WPLTO_runs": 0, "product_links": 0,
                         "product_sources_changed": 0, "media_builds": 0,
                         "device_contacts": 0},
        "claim_limit": ("Host target-codegen, Bank-2 object, framebuffer, capacity "
                        "and scheduling price. No variant is selected; exact final-LTO "
                        "bytes and hardware behavior remain implementation/acceptance claims."),
    }
    validate(value)
    value["verification"]["mutations_rejected"] = mutation_selftest(value)
    return value


def report(value: dict[str, Any]) -> str:
    light = value["variants"]["B_light"]
    full = value["variants"]["B_full"]
    code = value["target_codegen"]["results"]
    return f'''# v1.9 Block B — native prompt editor pricing

Recorded: 2026-08-28  
Receipt: `c2.3-v1.9-native-prompt-editor-pricing-receipt.json`

## Outcome

Both prompt compositions are priced against the accepted Block-A pair.  The
recommendation is **B-light**, in the composed private-entry form.  It closes
the native-prompt cursor Known Issue without opening Comfort's separately
owner-gated `$22` risk.

| | B-light | B-full |
|---|---:|---:|
| Product-resident target projection | **+1 B** | 0 B |
| Static Bank-2 delta | +{light['bank2']['static_plane_delta_bytes']} B | 0 B |
| Conditional disk payload | 0 B | {full['disk_library']['payload_bytes']} B |
| New symbol/name cost | 2 / 33 B | 6 / 73 B |
| Free capacity after load | 111 / 1,473 B | 107 / 1,433 B |
| Stationary frames/character | Block-A path | {full['responsiveness']['stationary_frames_per_character']:.6f} |
| Selectable now | **yes** | **no — Block C** |

This is a decision card, not an implementation.  B-light needs one authorized
WPLTO/product link; B-full remains gated behind the separate Block-C owner
decision.

## Why the B-light winner is not a raw C call

The final Block-A ELF still has one inline C collector in `repl`: one direct
`lisp_input_event` edge, no indirect editor call, and no boot/runtime editor
rebind.  A C-side `sym_lookup("read-line")` bridge measures {code['dynamic-uncomposed']['delta']['text_bytes']}
text plus {code['dynamic-uncomposed']['delta']['rodata_bytes']} string bytes and still leaves prompt and cursor under
different framebuffer owners.

The winning form puts a private, directory-derived zero-argument entry in
Bank 2.  That entry calls the **public** `read-line` in native-prompt mode.
While active, the editor owns `lisp65> `, the editable cells and the handoff;
profiles without that entry retain the old C collector behind the preprocessor
branch.  The composed host framebuffer is exactly `lisp65> abc` after a
Cursor-Left insertion, while ordinary `(read-line)` remains framebuffer-
identical to Block A.

On the complete materialized target profile ({value['target_codegen']['definitions']} definitions, {value['target_codegen']['feature_count']} feature
defines), `repl` moves from {code['baseline']['sections']['.text.repl']}+{code['baseline']['sections']['.rodata.str1.1']} to
{code['composed-private-entry']['sections']['.text.repl']}+{code['composed-private-entry']['sections']['.rodata.str1.1']} bytes: +10 text, −9 string, zero BSS, **+1 aggregate byte**.
The aggregate resident allocation grows by one byte, but placement is not
priced from a sum: the text fragment alone grows by 10 bytes.  Against its
60-byte hole that projects 50 bytes free, 18 above the permanent 32-byte floor.
The exact final-LTO delta remains an implementation preflight; a forecast is
not a linked-byte claim.

## Bank-2 and capacity price

Two existing objects change and two private objects appear:

- `%rl-screen-tail`: 185 → 212 bytes;
- `read-line`: 177 → 235 bytes;
- `%native-prompt`: 32 bytes;
- `%native-read-line`: 16 bytes.

Code grows by 133 bytes and the two directory entries by 14, for an exact
147-byte plane projection: 47,335 → 47,482.  The largest composed Bank-2 hole
therefore projects from 16,331 to 16,184 bytes.  Both new names cost 2 slots
and 33 NUL-inclusive bytes, leaving 111/1,473 against the 32/384 floor.
Every object remains below 255 bytes.

The native C buffer remains 192 bytes.  A longer editor result is rejected
visibly as `reader: invalid token`; it is never truncated and evaluated.  This
preserves the old native line limit rather than turning the wider editor into
a WYSIWYG violation.

## B-full conditional price

The current Comfort core has four objects (815 code bytes).  To consume the
Block-A editor without reloading the historical `v16core` and overwriting its
armed `read-line`, `%ide-line-net-depth` rides the same library as a fifth
142-byte object.  The exact core is 957 code + 35 directory = **992 bytes**,
with six new names / 73 name bytes and 107/1,433 free capacity.

The real Block-A service path remains {full['responsiveness']['stationary_frames_per_character']:.6f} frames/character.
Amortizing the prompt fallback over only 40 characters gives
{full['responsiveness']['forty_character_prompt_amortized_frames_per_character']:.6f} frames/character and
{full['responsiveness']['margin_percent']:.3f}% margin.  But this excludes the
Block-C first-fault latch, residual `$22` owner word and device acceptance;
therefore B-full is priced but not selectable.

## Self-review and claim boundary

The report arithmetic is reproduced from the receipt.  Five sharp mutations
fall: registry-only/no route, split prompt ownership, silent truncation,
spending below the text floor, and selecting Comfort before Block C.  The
earlier partial-profile probe (30/86 bytes) is recorded as rejected; only the
materialized compiler process carries the price.

No product source, WPLTO, link, medium or device state changed.  Hardware
timing and exact linked size remain claims for the selected implementation
card.
'''


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("record", "check", "selftest"),
            "usage: record|check|selftest")
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
        REPORT.write_text(report(value), encoding="utf-8")
    elif action == "check":
        require(load(RECEIPT) == value, "Block-B pricing receipt stale")
        require(REPORT.read_text(encoding="utf-8") == report(value),
                "Block-B pricing report stale")
    else:
        require(len(value["verification"]["mutations_rejected"]) == 5,
                "Block-B mutation count drift")
    print("v1.9 Block-B pricing: PASS recommendation=B-light "
          "resident=+1 bank2=+147 B-full=conditional")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v1.9 Block-B pricing: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
