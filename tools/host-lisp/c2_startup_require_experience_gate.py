#!/usr/bin/env python3
"""Price and prove cold-boot liveness plus immediate ``require`` intent.

The boot proof compiles the exact target macros into owner-shaped micro
sections.  The require proof compiles and executes the delivered definition
through the real P0 compiler/VM with instrumented callees, then rebuilds the
current Bank-2 plane to bind its artifact delta.  No product link or device is
used.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_repl_direct_expression_gate as DIRECT  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


CONTRACT = ROOT / "config/c2-startup-require-experience-contract.json"
HEADER = ROOT / "src/boot_progress.h"
STAGER = ROOT / "scripts/r3-cold-stager-main.c"
MEMORY = ROOT / "src/mem.c"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
REQUIRE_SOURCE = ROOT / "lib/stdlib-require.lisp"
BANNER = ROOT / "lib/repl-banner.lisp"
REPL = ROOT / "src/repl.c"
PLAN = ROOT / "docs/planning/startup-require-experience-work-plan.md"
BOOT_BOUND = ROOT / "docs/planning/v1.2-publication-scope.md"
RELEASE_PLAN = ROOT / "docs/planning/1.12-v1.4.0-release-work-plan.md"
REQUIRE_BASELINE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-phase-m1-require-latency-measurement-receipt.json"
)
DIRECT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-repl-direct-expression-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-startup-require-experience-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"

FORMAT = "lisp65-c2.3-startup-require-experience-v1"
RECORDED_ON = "2026-08-11"
SEAL_COMMIT = "e5d14f735a4b5bb30b88d4978202c1e48ca82ff7"

BASE_REQUIRE_DEFINITION = """(defun require (library)
  (if (symbolp library)
      (if (%require-fast-loaded-p library)
          t
          (let ((index (%l65i-parse)))
            (if index (%require-resolve library index) nil)))
      nil))"""

EXPERIENCE_REQUIRE_DEFINITION = """(defun require (library)
  (if (symbolp library)
      (progn
        ; Intent is emitted before parser, resolver or persistent loader work.
        ; The ordinary REPL result remains the sole terminal result echo.
        (write-string \"loading \")
        (write-string (symbol-name library))
        (write-string \"...\")
        (terpri)
        (if (%require-fast-loaded-p library)
            t
            (let ((index (%l65i-parse)))
              (if index (%require-resolve library index) nil))))
      nil))"""


class ExperienceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ExperienceError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def candidate_require_source(source: str) -> str:
    require(source.count(BASE_REQUIRE_DEFINITION) == 1,
            "accepted require definition is absent or ambiguous")
    require(EXPERIENCE_REQUIRE_DEFINITION not in source,
            "experience require leaked into the historical source world")
    return source.replace(
        BASE_REQUIRE_DEFINITION, EXPERIENCE_REQUIRE_DEFINITION, 1)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def run(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=ROOT, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    require(result.returncode == 0,
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stderr.strip()}")
    return result.stdout


def macro_block(source: str, name: str) -> str:
    anchor = f"#define {name}() do {{"
    start = source.find(anchor)
    require(start >= 0, f"macro absent: {name}")
    end = source.find("} while (0)", start)
    require(end >= 0, f"macro unterminated: {name}")
    return source[start:end + len("} while (0)")]


def cell_text(block: str) -> str:
    cells: dict[int, str] = {}
    pattern = re.compile(
        r"LISP65_BOOT_PROGRESS_CELL\([^,]+,\s*(\d+)u,\s*'(.)'\);"
    )
    for column, character in pattern.findall(block):
        cells[int(column)] = character
    require(cells and sorted(cells) == list(range(min(cells), max(cells) + 1)),
            "boot progress character columns are not contiguous")
    return "".join(cells[index] for index in sorted(cells))


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") ==
            "lisp65-c2-startup-require-experience-contract-v1",
            "contract identity drift")
    require(value.get("accepted_by") ==
            "236eba09f55d396e62090a379821df91b81ab8ee",
            "owner acceptance drift")
    boot = value.get("boot", {})
    require(boot.get("activation_define") ==
            "LISP65_STARTUP_REQUIRE_EXPERIENCE",
            "boot activation seam drift")
    require(boot.get("screen_base") == 0x0800
            and boot.get("screen_columns") == 80,
            "boot screen geometry drift")
    require(
        [(row["id"], row["row"], row["message"])
         for row in boot.get("progress", [])] == [
            ("stager", 8, "LISP65: STAGING MEDIA"),
            ("heap", 9, "LISP65: BUILDING HEAP"),
            ("libraries", 10, "LISP65: LOADING LIBRARIES"),
        ], "boot progress inventory drift",
    )
    require(boot.get("terminal_life_sign") == {
        "banner": "WORKBENCH 1.4.0", "prompt": "lisp65>",
        "owner": "existing Bank-2 banner and REPL",
    }, "terminal life-sign authority drift")
    require(boot.get("timing_consumers_unchanged") == {
        "cold_boot_upper_bound_seconds": 27.653,
        "release_acceptance_window_seconds": 45,
    }, "boot timing consumer drift")
    require(boot.get("target_micro_price_bytes") == {
        "separate_stager": 116,
        "disposable_boot_overlay": 116,
        "transported_decoder_slice": 133,
        "resident": 0,
    }, "boot micro-price drift")
    require_part = value.get("require", {})
    require(require_part.get("activation") ==
            "successor source substitution; historical product worlds retain "
            "the accepted definition",
            "require activation seam drift")
    require(require_part.get("intent_prefix") == "loading "
            and require_part.get("intent_suffix") == "..."
            and require_part.get("newline") is True
            and require_part.get("must_precede") == [
                "%require-fast-loaded-p", "%l65i-parse", "%require-resolve"
            ]
            and require_part.get("terminal_result_owner") ==
                "ordinary REPL result echo"
            and require_part.get("non_symbol_output") == "none",
            "require intent/result contract drift")
    require(require_part.get("accepted_target_baselines") == {
        "first_seconds": 12, "repeat_seconds": 9,
        "first_vm_instructions": 136765,
        "repeat_vm_instructions": 134788,
        "first_prim67_reads": 399, "repeat_prim67_reads": 384,
    }, "require target baseline drift")
    require(value.get("accounting") == {
        "resident_bytes": 0, "mutable_state_bytes": 0,
        "maximum_require_bank2_delta_bytes": 512,
        "product_link_authorized": False, "hardware_claim": False,
        "release_claim": False,
    }, "accounting wall drift")


def validate_sources(
    value: dict[str, Any], *, header: str, stager: str, memory: str,
    decoder: str, require_source: str, banner: str, repl: str,
) -> dict[str, Any]:
    validate_contract(value)
    require('#include "../src/boot_progress.h"' in stager
            and '#include "../src/boot_progress.h"' in decoder
            and '#include "boot_progress.h"' in memory,
            "boot progress header is not reachable from every owner")
    require("defined(__MEGA65__) && "
            "defined(LISP65_STARTUP_REQUIRE_EXPERIENCE)" in header,
            "boot progress lost its explicit successor-product opt-in")
    require("((volatile uint8_t *)0x0800u)" in header,
            "boot writes lost volatile $0800 CPU stores")
    require("static " not in header and "const char" not in header,
            "boot progress gained stored state or string data")
    require("lisp65_boot_progress_column_ < 28u" in header,
            "bounded progress-row clear drift")
    prefix = cell_text(header[header.index("#define LISP65_BOOT_PROGRESS_PREFIX"):
                              header.index("#define LISP65_BOOT_PROGRESS_STAGER")])
    require(prefix == "LISP65: ", f"boot prefix drift: {prefix!r}")
    names = {
        "stager": "LISP65_BOOT_PROGRESS_STAGER",
        "heap": "LISP65_BOOT_PROGRESS_HEAP",
        "libraries": "LISP65_BOOT_PROGRESS_LIBRARIES",
    }
    messages: dict[str, str] = {}
    for row in value["boot"]["progress"]:
        suffix = cell_text(macro_block(header, names[row["id"]]))
        require(min(
            int(column) for column in re.findall(
                r"CELL\([^,]+,\s*(\d+)u,", macro_block(header, names[row["id"]])
            )
        ) == 8, f"{row['id']} message does not begin after prefix")
        messages[row["id"]] = prefix + suffix
        require(messages[row["id"]] == row["message"],
                f"{row['id']} message drift: {messages[row['id']]!r}")

    stager_body = stager[stager.index("int main(void)"):]
    require(stager_body.index("LISP65_BOOT_PROGRESS_STAGER();") <
            stager_body.index("io_enable();"),
            "stager life sign does not precede I/O work")
    mem_body = memory[memory.index("void mem_init(void)"):]
    require(mem_body.index("LISP65_BOOT_PROGRESS_HEAP();") <
            mem_body.index("freelist = NIL;"),
            "heap life sign does not precede heap construction")
    decoder_body = decoder[decoder.index(
        "C2_SLICE(00) uint8_t c2_stream_phase_00"):
        decoder.index("C2_SLICE(00b) uint8_t c2_stream_phase_00b")]
    require(decoder_body.index("LISP65_BOOT_PROGRESS_LIBRARIES();") <
            decoder_body.index("if (!c ||"),
            "library life sign does not precede C2D validation/read")
    subtitle_start = banner.find("(defun %banner-subtitle ()")
    subtitle_end = banner.find("\n(defun ", subtitle_start + 1)
    require(subtitle_start >= 0, "Bank-2 banner owner absent")
    if subtitle_end < 0:
        subtitle_end = len(banner)
    subtitle = banner[subtitle_start:subtitle_end]
    banner_matches = re.findall(
        r'\(let \(\(text "(WORKBENCH [0-9]+\.[0-9]+\.[0-9]+)"\)\)',
        subtitle,
    )
    require(len(banner_matches) == 1
            and banner.count("(%banner-subtitle)") == 1,
            "derived Bank-2 terminal banner authority absent or ambiguous")
    require('emit_str("lisp65> ")' in repl,
            "native terminal prompt authority absent")

    require_body = require_source[require_source.index("(defun require (library)"):]
    output_tokens = (
        '(write-string "loading ")',
        "(write-string (symbol-name library))",
        '(write-string "...")', "(terpri)",
    )
    output_positions = [require_body.index(token) for token in output_tokens]
    work_positions = [require_body.index(token) for token in
                      value["require"]["must_precede"]]
    require(output_positions == sorted(output_positions)
            and max(output_positions) < min(work_positions),
            "require intent is not complete before all resolver work")
    require(require_body.count("(write-string") == 3
            and require_body.count("(terpri)") == 1,
            "require gained duplicate/terminal output")
    require("(if (symbolp library)" in require_body
            and require_body.rstrip().endswith("nil))"),
            "non-symbol require output boundary drift")
    return {
        "messages": messages,
        "orders": {
            "stager_before_io": True, "heap_before_construction": True,
            "libraries_before_c2d_read": True,
            "require_intent_before_fast_parse_resolve": True,
        },
        "terminal_life_sign_reused": True,
    }


def object_sizes(path: Path) -> dict[str, int]:
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    return {row.name: row.bytes for row in truth.sections if row.name}


def boot_target_price(value: dict[str, Any]) -> dict[str, Any]:
    candidate_source = """#include \"boot_progress.h\"
void stager(void) { LISP65_BOOT_PROGRESS_STAGER(); }
__attribute__((section(\".lisp65_boot\")))
void heap(void) { LISP65_BOOT_PROGRESS_HEAP(); }
__attribute__((section(\".lisp65_rt_c2d_00\")))
void libraries(void) { LISP65_BOOT_PROGRESS_LIBRARIES(); }
"""
    baseline_source = """void stager(void) {}
__attribute__((section(\".lisp65_boot\"))) void heap(void) {}
__attribute__((section(\".lisp65_rt_c2d_00\"))) void libraries(void) {}
"""
    with tempfile.TemporaryDirectory(prefix="lisp65-boot-progress-") as directory:
        root = Path(directory)
        sources = {"candidate": candidate_source, "baseline": baseline_source}
        sizes: dict[str, dict[str, int]] = {}
        for name, source in sources.items():
            source_path = root / f"{name}.c"
            object_path = root / f"{name}.o"
            source_path.write_text(source, encoding="utf-8")
            run([
                str(CC), "-Oz", "-Wall", "-Wextra", "-fno-lto",
                "-ffunction-sections", "-fdata-sections", "-D__MEGA65__",
                "-DLISP65_STARTUP_REQUIRE_EXPERIENCE",
                "-I", str(ROOT / "src"), "-c", str(source_path),
                "-o", str(object_path),
            ])
            sizes[name] = object_sizes(object_path)
        forbidden = (".rodata", ".data", ".bss")
        require(not any(sizes["candidate"].get(section, 0) for section in forbidden),
                "boot progress emitted stored data")
        deltas = {
            "separate_stager": sizes["candidate"][".text.stager"]
                - sizes["baseline"][".text.stager"],
            "disposable_boot_overlay": sizes["candidate"][".lisp65_boot"]
                - sizes["baseline"][".lisp65_boot"],
            "transported_decoder_slice":
                sizes["candidate"][".lisp65_rt_c2d_00"]
                - sizes["baseline"][".lisp65_rt_c2d_00"],
            "resident": 0,
        }
    require(deltas == value["boot"]["target_micro_price_bytes"],
            f"boot target micro-price drift: {deltas}")
    return {
        "compiler": bind(CC.resolve()), "elf_reader": bind(READOBJ.resolve()),
        "baseline_sections": sizes["baseline"],
        "candidate_sections": sizes["candidate"], "delta_bytes": deltas,
        "claim_limit": (
            "exact target compilation of owner-shaped macro expansions; "
            "not a product link or target wall-time measurement"
        ),
    }


def add_definition(
    form: Any, heap: B.Heap, directory: dict[int, B.CodeObject],
    names: dict[int, str], ledger: dict[str, Any],
) -> None:
    name, code, helpers = C.compile_top_form_with_helpers(
        form, heap, strict_arity=True, abi_profile="dialect-v2",
        abi_ledger=ledger,
    )
    require(name is not None and not helpers,
            f"require witness emitted unexpected helper: {name}")
    symbol = heap.intern(name)
    directory[symbol] = code
    names[id(code)] = name


class RequireVM(B.P0VM):
    WATCH = {
        "write-string", "terpri", "%require-fast-loaded-p",
        "%l65i-parse", "%require-resolve",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.events: list[dict[str, Any]] = []

    def _record(self, code: B.CodeObject, lit_idx: int, argc: int,
                stack: list[int]) -> None:
        symbol = self._callee_symbol(code, lit_idx)
        target = self.heap.symbol_name(symbol)
        if target not in self.WATCH:
            return
        args = stack[-argc:] if argc else []
        rendered = []
        for arg in args:
            if self.heap.stringp(arg):
                rendered.append(self.heap.string_to_text(arg))
            else:
                rendered.append(self.heap.obj_to_text(arg))
        self.events.append({"callee": target, "arguments": rendered})

    def _call(self, code: B.CodeObject, lit_idx: int, argc: int,
              stack: list[int], pc: int | None = None,
              native_base: int = 0, frame_slots: int = 0) -> int:
        self._record(code, lit_idx, argc, stack)
        return super()._call(
            code, lit_idx, argc, stack, pc=pc, native_base=native_base,
            frame_slots=frame_slots,
        )

    def _tailcall(self, code: B.CodeObject, lit_idx: int, argc: int,
                  stack: list[int], pc: int | None = None,
                  native_base: int = 0) -> int:
        self._record(code, lit_idx, argc, stack)
        return super()._tailcall(
            code, lit_idx, argc, stack, pc=pc, native_base=native_base,
        )


def require_form(source: str) -> Any:
    forms = [form for form in C.parse_all(source)
             if isinstance(form, list) and len(form) >= 2
             and form[0] == "defun" and form[1] == "require"]
    require(len(forms) == 1, "delivered require definition is not unique")
    return forms[0]


def run_require_case(source: str, *, fast: bool, argument: str) -> dict[str, Any]:
    heap = C.prepare_heap([])
    directory: dict[int, B.CodeObject] = {}
    names: dict[int, str] = {}
    ledger = load(ABI_LEDGER)
    fast_value = "t" if fast else "nil"
    fixtures = (
        C.parse_one("(defun write-string (value) value)"),
        C.parse_one("(defun terpri () nil)"),
        C.parse_one(
            f"(defun %require-fast-loaded-p (library) {fast_value})"
        ),
        C.parse_one("(defun %l65i-parse () 1)"),
        C.parse_one("(defun %require-resolve (library index) t)"),
        require_form(source),
    )
    for form in fixtures:
        add_definition(form, heap, directory, names, ledger)
    vm = RequireVM(
        heap=heap, directory=directory, macro_symbols=set(),
        max_steps=100_000, code_names=names,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    arg = heap.intern(argument) if argument != "#fixnum" else B.mkfix(7)
    result = vm.run(directory[heap.intern("require")], [arg])
    return {
        "argument": argument, "fast_loaded": fast,
        "result": heap.obj_to_text(result), "events": vm.events,
        "instructions": vm.steps,
    }


def require_execution(source: str) -> dict[str, Any]:
    fast = run_require_case(source, fast=True, argument="inspect")
    slow = run_require_case(source, fast=False, argument="inspect")
    nonsymbol = run_require_case(source, fast=False, argument="#fixnum")
    prefix = [
        {"callee": "write-string", "arguments": ["loading "]},
        {"callee": "write-string", "arguments": ["inspect"]},
        {"callee": "write-string", "arguments": ["..."]},
        {"callee": "terpri", "arguments": []},
    ]
    require(fast["events"] == prefix + [
        {"callee": "%require-fast-loaded-p", "arguments": ["inspect"]}
    ] and fast["result"] == "t", f"fast require witness red: {fast}")
    require(slow["events"] == prefix + [
        {"callee": "%require-fast-loaded-p", "arguments": ["inspect"]},
        {"callee": "%l65i-parse", "arguments": []},
        {"callee": "%require-resolve", "arguments": ["inspect", "1"]},
    ] and slow["result"] == "t", f"slow require witness red: {slow}")
    require(nonsymbol["events"] == [] and nonsymbol["result"] == "nil",
            f"non-symbol require emitted output: {nonsymbol}")
    return {"fast": fast, "slow": slow, "non_symbol": nonsymbol,
            "rendered_intent": "loading inspect...\n", "cases": 3}


def require_artifact_price(value: dict[str, Any]) -> dict[str, Any]:
    prior = load(DIRECT_RECEIPT)
    before = prior["accounting"]
    with tempfile.TemporaryDirectory(prefix="lisp65-require-intent-") as directory:
        root = Path(directory)
        runtime = DIRECT.candidate_runtime_source()
        runtime_path = root / "eval-runtime.lisp"
        runtime_path.write_text(runtime, encoding="utf-8")
        require_path = root / "stdlib-require.experience.lisp"
        require_path.write_text(candidate_require_source(
            REQUIRE_SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
        with DIRECT.historical_read_line_input():
            emitted = STD.emit_artifacts(
                str(DIRECT.BASE_SUITE), DIRECT.candidate_suite(
                    runtime_path, require_path=require_path),
                str(root / "stdlib-p0"), artifact_role="stdlib",
            )
        manifest = load(Path(emitted["manifest"]))
        DIRECT.validate_candidate_publication(manifest)
    after = {
        "objects": manifest["objects"], "code_bytes": manifest["code_bytes"],
        "external_bytes": manifest["external_image"]["bytes"],
        "directory_bytes": manifest["directory_bytes"],
    }
    prior_after = {
        "objects": before["objects_after"],
        "code_bytes": before["code_bytes_after"],
        "external_bytes": before["external_bytes_after"],
        "directory_bytes": before["directory_bytes_after"],
    }
    delta = {name: after[name] - prior_after[name] for name in after}
    require(delta["objects"] == 0 and delta["directory_bytes"] == 0,
            f"require intent changed object/directory cardinality: {delta}")
    require(0 < delta["external_bytes"] <=
            value["accounting"]["maximum_require_bank2_delta_bytes"],
            f"require intent Bank-2 delta outside wall: {delta}")
    return {
        "accepted_direct_plane": prior_after, "candidate_plane": after,
        "delta": {**delta, "resident_bytes": 0, "mutable_state_bytes": 0},
        "candidate_blob_sha256": manifest["blob_sha256"],
        "candidate_external_sha256": manifest["external_image"]["sha256"],
        "claim_limit": (
            "isolated full-stdlib artifact rebuild against the accepted direct-"
            "expression plane; no product link or release geometry claim"
        ),
    }


def baseline_ledger(value: dict[str, Any]) -> dict[str, Any]:
    receipt = load(REQUIRE_BASELINE)
    first = receipt["host_measurement"]["first_require"]
    repeat = receipt["host_measurement"]["idempotent_repeat"]
    expected = value["require"]["accepted_target_baselines"]
    actual = {
        "first_seconds": receipt["hardware_wall_truth"]
            ["current_valid_full_reset_product_bound_media"]
            ["first_require_seconds"],
        "repeat_seconds": receipt["hardware_wall_truth"]
            ["current_valid_full_reset_product_bound_media"]
            ["idempotent_repeat_seconds"],
        "first_vm_instructions": first["vm_instructions"],
        "repeat_vm_instructions": repeat["vm_instructions"],
        "first_prim67_reads": first["prim67_reads"],
        "repeat_prim67_reads": repeat["prim67_reads"],
    }
    require(actual == expected, f"require baseline authority drift: {actual}")
    require("27.653-second observed boot upper bound" in
            BOOT_BOUND.read_text(encoding="utf-8"),
            "27.653-second cold-boot authority absent")
    require("45-second" in RELEASE_PLAN.read_text(encoding="utf-8"),
            "45-second release acceptance authority absent")
    return {
        "require": actual,
        "first_phase_instructions": first["phase_instructions"],
        "repeat_phase_instructions": repeat["phase_instructions"],
        "boot": value["boot"]["timing_consumers_unchanged"],
        "interpretation": (
            "historical target wall and exact VM/read counts remain consumers; "
            "liveness adds no revised timing claim"
        ),
    }


def mutation_tests(value: dict[str, Any], texts: dict[str, str]) -> int:
    mutations: list[tuple[dict[str, Any], dict[str, str]]] = []
    for key, call in (
        ("stager", "    LISP65_BOOT_PROGRESS_STAGER();\n"),
        ("memory", "    LISP65_BOOT_PROGRESS_HEAP();\n"),
        ("decoder", "    LISP65_BOOT_PROGRESS_LIBRARIES();\n"),
    ):
        bad_texts = dict(texts)
        require(call in bad_texts[key], f"mutation anchor absent: {call.strip()}")
        bad_texts[key] = bad_texts[key].replace(call, "", 1)
        mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["stager"] = bad_texts["stager"].replace(
        "    LISP65_BOOT_PROGRESS_STAGER();\n    io_enable();",
        "    io_enable();\n    LISP65_BOOT_PROGRESS_STAGER();", 1,
    )
    mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["memory"] = bad_texts["memory"].replace(
        "    LISP65_BOOT_PROGRESS_HEAP();\n", "", 1
    ).replace("    freelist = NIL;",
              "    freelist = NIL;\n    LISP65_BOOT_PROGRESS_HEAP();", 1)
    mutations.append((copy.deepcopy(value), bad_texts))
    for old, new in (
        ("((volatile uint8_t *)0x0800u)", "((volatile uint8_t *)0x0801u)"),
        ("volatile uint8_t", "uint8_t"),
        ("LISP65_BOOT_PROGRESS_CELL((row), 3u, 'P');",
         "LISP65_BOOT_PROGRESS_CELL((row), 3u, 'Q');"),
    ):
        bad_texts = dict(texts)
        require(old in bad_texts["header"], f"header mutation anchor absent: {old}")
        bad_texts["header"] = bad_texts["header"].replace(old, new, 1)
        mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["stager"] = bad_texts["stager"].replace(
        '#include "../src/boot_progress.h"', '#include "boot_progress.h"', 1
    )
    mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["header"] = bad_texts["header"].replace(
        " && defined(LISP65_STARTUP_REQUIRE_EXPERIENCE)", "", 1
    )
    mutations.append((copy.deepcopy(value), bad_texts))
    for old, new in (
        ('(write-string "loading ")', '(write-string "load ")'),
        ("(write-string (symbol-name library))", '(write-string "library")'),
        ("        (terpri)\n", ""),
    ):
        bad_texts = dict(texts)
        require(old in bad_texts["require"], f"require mutation anchor absent: {old}")
        bad_texts["require"] = bad_texts["require"].replace(old, new, 1)
        mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["require"] = bad_texts["require"].replace(
        "        (if (%require-fast-loaded-p library)",
        "        (if (%require-fast-loaded-p library)\n"
        "            (write-string \"late\")", 1,
    )
    mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["banner"], replacements = re.subn(
        r'"WORKBENCH [0-9]+\.[0-9]+\.[0-9]+"', '"READY"',
        bad_texts["banner"], count=1,
    )
    require(replacements == 1, "banner mutation anchor absent or ambiguous")
    mutations.append((copy.deepcopy(value), bad_texts))
    bad_texts = dict(texts)
    bad_texts["repl"] = bad_texts["repl"].replace("lisp65> ", "ready> ", 1)
    mutations.append((copy.deepcopy(value), bad_texts))
    for path, replacement in (
        (("accounting", "resident_bytes"), 1),
        (("boot", "timing_consumers_unchanged",
          "cold_boot_upper_bound_seconds"), 27.0),
        (("boot", "target_micro_price_bytes", "resident"), 1),
        (("require", "accepted_target_baselines", "first_seconds"), 11),
        (("require", "activation"), "live historical source mutation"),
    ):
        bad = copy.deepcopy(value)
        cursor: dict[str, Any] = bad
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        mutations.append((bad, dict(texts)))
    for index, (bad_contract, bad_texts) in enumerate(mutations):
        try:
            validate_sources(
                bad_contract, header=bad_texts["header"],
                stager=bad_texts["stager"], memory=bad_texts["memory"],
                decoder=bad_texts["decoder"],
                require_source=bad_texts["require"],
                banner=bad_texts["banner"], repl=bad_texts["repl"],
            )
        except (ExperienceError, ValueError):
            continue
        raise ExperienceError(f"mutation accepted: {index}")
    return len(mutations)


def source_texts() -> dict[str, str]:
    require_base = REQUIRE_SOURCE.read_text(encoding="utf-8")
    return {
        "header": HEADER.read_text(encoding="utf-8"),
        "stager": STAGER.read_text(encoding="utf-8"),
        "memory": MEMORY.read_text(encoding="utf-8"),
        "decoder": DECODER.read_text(encoding="utf-8"),
        "require_base": require_base,
        "require": candidate_require_source(require_base),
        "banner": BANNER.read_text(encoding="utf-8"),
        "repl": REPL.read_text(encoding="utf-8"),
    }


def gate_wiring() -> list[str]:
    rows = [
        "c2-startup-require-experience-selftest:",
        "python3 tools/host-lisp/c2_startup_require_experience_gate.py selftest",
        "c2-startup-require-experience-check:",
        "python3 tools/host-lisp/c2_startup_require_experience_gate.py check",
        "check-source: c2-startup-require-experience-check",
    ]
    gates = GATES.read_text(encoding="utf-8")
    require(all(row in gates for row in rows), "permanent gate wiring absent")
    return rows


def core_receipt() -> dict[str, Any]:
    value = load(CONTRACT)
    texts = source_texts()
    source_gate = validate_sources(
        value, header=texts["header"], stager=texts["stager"],
        memory=texts["memory"], decoder=texts["decoder"],
        require_source=texts["require"], banner=texts["banner"],
        repl=texts["repl"],
    )
    candidate_require = texts["require"].encode("utf-8")
    source_gate["candidate_require"] = {
        "producer": "candidate_require_source",
        "bytes": len(candidate_require),
        "sha256": sha(candidate_require),
        "historical_source_unchanged": True,
    }
    source_gate["mutations_rejected"] = mutation_tests(value, texts)
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASSED-BOOT-LIVENESS-AND-REQUIRE-INTENT-HOST-GATES",
        "scope": {
            "product_links": 0, "device_contacts": 0,
            "resident_bytes_delta": 0, "release_claim": False,
        },
        "authorities": {
            "contract": bind(CONTRACT), "header": bind(HEADER),
            "stager": bind(STAGER), "memory": bind(MEMORY),
            "decoder": bind(DECODER), "require_source": bind(REQUIRE_SOURCE),
            "banner": bind(BANNER), "repl": bind(REPL), "plan": bind(PLAN),
            "require_baseline": bind(REQUIRE_BASELINE),
            "accepted_direct_plane": bind(DIRECT_RECEIPT),
            "driver": bind(DRIVER),
        },
        "baseline_ledger": baseline_ledger(value),
        "source_gate": source_gate,
        "boot_target_price": boot_target_price(value),
        "require_execution": require_execution(texts["require"]),
        "require_artifact_price": require_artifact_price(value),
        "effect": {
            "boot": (
                "three product-owned progress lines precede media, heap and "
                "library work; existing banner plus prompt is terminal"
            ),
            "require": (
                "intent is visible before fast-path, parser, resolver or "
                "persistent loader work; ordinary REPL result remains terminal"
            ),
            "timing": "27.653-second and 45-second consumers unchanged",
        },
        "gate_wiring": gate_wiring(),
    }


def selftest() -> dict[str, Any]:
    value = load(CONTRACT)
    texts = source_texts()
    validate_sources(
        value, header=texts["header"], stager=texts["stager"],
        memory=texts["memory"], decoder=texts["decoder"],
        require_source=texts["require"], banner=texts["banner"],
        repl=texts["repl"],
    )
    return {
        "status": "passed", "mutations": mutation_tests(value, texts),
        "require_execution_cases": require_execution(texts["require"])["cases"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.mode == "selftest":
            print(json.dumps(selftest(), indent=2, sort_keys=True))
            return 0
        value = core_receipt()
        if args.mode == "write":
            raise ExperienceError(
                "startup/require receipt is sealed evidence and cannot be regenerated"
            )
        else:
            receipt_name = RECEIPT.relative_to(ROOT).as_posix()
            require(RECEIPT.read_bytes() == ERA.era_blob(SEAL_COMMIT, receipt_name),
                    "startup/require sealed receipt bytes drift")
        print(json.dumps({
            "status": value["status"],
            "boot_delta_bytes": value["boot_target_price"]["delta_bytes"],
            "require_delta": value["require_artifact_price"]["delta"],
            "require_execution_cases": value["require_execution"]["cases"],
            "mutations": value["source_gate"]["mutations_rejected"],
        }, indent=2, sort_keys=True))
    except (
        ExperienceError, ERA.EraError, DIRECT.GateError, STD.StdlibCheckError,
        ElfTruthError,
        C.CompileError, B.BytecodeError, B.VMError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(f"c2-startup-require-experience: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
