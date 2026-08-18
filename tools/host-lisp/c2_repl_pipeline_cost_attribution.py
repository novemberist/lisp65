#!/usr/bin/env python3
"""Price the per-form REPL pipeline in the v1.4.0 and Link-96 worlds.

Owner hardware rows exonerate execution inside ``(time ...)``: calls, reads,
writes and five allocations all complete in zero or one frame.  The visible
delay is therefore outside the timed body.  This gate binds that boundary to
the delivered REPL, executes the exact product ``lcc-run`` and compiler
carriers from both canonical manifests, and carries forward the existing
target-side station trace for the transient install/execute/rollback suffix.

The output is an attribution and a pricing input.  It changes no product
bytes, runs no linker and makes no new target measurement.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence"
ARCH = EVIDENCE / "architecture-blocks"
RECEIPT = ARCH / "c2.3-link96-repl-pipeline-cost-attribution-receipt.json"
V140_CANONICAL = ROOT / (
    "build/c2.3/v1.4.0-candidate-product-link92-r5/"
    "canonical-product-manifest.json"
)
LINK96_CANONICAL = ROOT / (
    "build/c2.3/terminal-return-guard-link96/canonical-product-manifest.json"
)
LINK57_TARGET = ARCH / "c2.2-link57-top-level-frame-attribution-hardware-receipt.json"
TIME_CAL = ARCH / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
VM_PROJECTION = EVIDENCE / (
    "post-release/v125-editor-input-latency-host-accounting-receipt.json"
)
REPL_SOURCE = ROOT / "src/repl.c"
READER_SOURCE = ROOT / "src/reader.c"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"
PLAN = ROOT / "docs/planning/post-v1.4.0-direction-plan.md"
EXPERIENCE_PLAN = ROOT / "docs/planning/startup-require-experience-work-plan.md"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-link96-repl-pipeline-cost-attribution-v1"
RECORDED_ON = "2026-08-11"
OWNER_CORRECTION = "665fb1ce1dd3c4d6f51ca0baa3e845e72eafd34d"
VM_CODEBUF = 56


class PipelineError(RuntimeError):
    pass


class InstallBoundary(RuntimeError):
    def __init__(self, args: list[int]) -> None:
        super().__init__("lcc-install boundary")
        self.args = list(args)


def require(value: bool, message: str) -> None:
    if not value:
        raise PipelineError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def resolve_artifact(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = path.resolve().as_posix()
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def bind_git(commit: str, relative: str) -> dict[str, Any]:
    process = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(
        process.returncode == 0,
        process.stderr.decode(errors="replace").strip()
        or f"git authority absent: {commit}:{relative}",
    )
    raw = process.stdout
    return {
        "authority": "git-blob", "commit": OWNER_CORRECTION,
        "path": relative, "bytes": len(raw), "sha256": sha(raw),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def proper_list(heap: B.Heap, value: int, label: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    while value != B.NIL:
        require(B.is_ptr(value) and heap.consp(value), f"{label} is not proper")
        key = B.to_u16(value)
        require(key not in seen, f"{label} is cyclic")
        seen.add(key)
        cell = heap.cell(value)
        out.append(cell.a)
        value = cell.b
    return out


def fixnum(value: int, label: str) -> int:
    require(B.is_fix(value), f"{label} is not a fixnum")
    return B.fixval(value)


def decode_compiled(heap: B.Heap, value: int) -> dict[str, Any]:
    objects = proper_list(heap, value, "compiled object list")
    rows: list[dict[str, Any]] = []
    for index, encoded in enumerate(objects):
        fields = proper_list(heap, encoded, f"compiled[{index}]")
        require(len(fields) == 5, "compiled CodeObject shape drift")
        literals = proper_list(heap, fields[3], f"compiled[{index}].literals")
        payload_values = proper_list(
            heap, fields[4], f"compiled[{index}].payload"
        )
        payload = bytes(
            fixnum(item, f"compiled[{index}].payload-byte")
            for item in payload_values
        )
        code = B.CodeObject(
            fixnum(fields[0], f"compiled[{index}].nargs"),
            fixnum(fields[1], f"compiled[{index}].nlocals"),
            fixnum(fields[2], f"compiled[{index}].flags"),
            tuple(literals), payload,
        )
        rows.append({
            "encoded_bytes": len(code.encode()),
            "payload_bytes": len(payload),
            "literal_count": len(literals),
            "encoded_sha256": sha(code.encode()),
            "payload_sha256": sha(payload),
        })
    return {
        "objects": len(rows),
        "encoded_bytes": sum(row["encoded_bytes"] for row in rows),
        "payload_bytes": sum(row["payload_bytes"] for row in rows),
        "literal_count": sum(row["literal_count"] for row in rows),
        "entries": rows,
    }


class PipelineTrace:
    """Instruction accounting plus the target's 56-byte window algorithm."""

    def __init__(self, origins: dict[int, str]) -> None:
        self.origins = origins
        self.function_instructions: dict[str, int] = {}
        self.role_instructions: dict[str, int] = {}
        self.initial_windows: dict[str, int] = {}
        self.refills: dict[str, int] = {}
        self.owner: int | None = None
        self.win = 0
        self.winlen = 0
        self.streaming = False
        self.install_calls = 0

    def role(self, code: B.CodeObject) -> str:
        return self.origins.get(id(code), "native-or-owner-definition")

    def enter(self, name: str, code: B.CodeObject, _args: list[int]) -> None:
        role = self.role(code)
        header = 7 + 2 * len(code.littab)
        require(header + 3 <= VM_CODEBUF, f"{name} header exceeds code window")
        capacity = VM_CODEBUF - header
        self.owner = id(code)
        self.win = 0
        self.winlen = min(len(code.payload), capacity)
        self.streaming = self.winlen < len(code.payload)
        self.initial_windows[role] = self.initial_windows.get(role, 0) + 1

    def exit(self, _name: str, _code: B.CodeObject) -> None:
        pass

    def instruction(
        self, name: str, code: B.CodeObject, pc: int, _spec: Any, _operand: Any
    ) -> None:
        role = self.role(code)
        self.function_instructions[name] = (
            self.function_instructions.get(name, 0) + 1
        )
        self.role_instructions[role] = self.role_instructions.get(role, 0) + 1
        header = 7 + 2 * len(code.littab)
        capacity = VM_CODEBUF - header
        if self.owner != id(code):
            self.owner = id(code)
            self.win = pc
            self.winlen = 0
            self.streaming = True
        need = min(len(code.payload), pc + 3)
        if self.streaming and (pc < self.win or self.win + self.winlen < need):
            self.win = pc
            self.winlen = min(len(code.payload) - pc, capacity)
            self.refills[role] = self.refills.get(role, 0) + 1

    def call(
        self, _caller: str, _kind: str, target: str, _argc: int,
        pc: int | None = None, resolved: bool = False,
    ) -> None:
        del pc, resolved
        if target == "lcc-install":
            self.install_calls += 1

    def summary(self) -> dict[str, Any]:
        functions = dict(sorted(
            self.function_instructions.items(), key=lambda row: (-row[1], row[0])
        ))
        return {
            "instructions": sum(self.function_instructions.values()),
            "instructions_by_role": dict(sorted(self.role_instructions.items())),
            "instructions_by_function": functions,
            "initial_windows_by_role": dict(sorted(self.initial_windows.items())),
            "refills_by_role": dict(sorted(self.refills.items())),
            "initial_window_count": sum(self.initial_windows.values()),
            "refill_count": sum(self.refills.values()),
            "install_calls": self.install_calls,
        }


class PipelineVM(B.P0VM):
    def _callprim(
        self, prim_id: int, argc: int, stack: list[int], pc: int | None = None,
        native_base: int = 0, frame_slots: int = 0,
    ) -> int:
        if prim_id == 38:
            self._check_argc(argc, "CALLPRIM")
            require(argc == 2 and len(stack) >= 2, "lcc-install ABI drift")
            self._trace_call(
                "CALLPRIM", "lcc-install", argc, pc=pc, resolved=True
            )
            raise InstallBoundary(stack[-argc:])
        return super()._callprim(
            prim_id, argc, stack, pc=pc,
            native_base=native_base, frame_slots=frame_slots,
        )


def load_manifest_entries(
    heap: B.Heap, path: Path, role: str,
    directory: dict[int, B.CodeObject], macros: set[int],
    names: dict[int, str], origins: dict[int, str],
) -> dict[str, Any]:
    manifest = load(path)
    blob_path = resolve_artifact(str(manifest["blob"]))
    blob = blob_path.read_bytes()
    require(
        len(blob) == int(manifest["code_bytes"])
        and sha(blob) == manifest["blob_sha256"],
        f"{role} manifest/blob drift",
    )
    patches = {
        int(row["blob_offset"]): int(row["node"])
        for row in manifest["literal_patches"]
    }
    for entry in manifest["entries"]:
        symbol = heap.intern(entry["name"])
        require(symbol not in directory, f"duplicate packed callee: {entry['name']}")
        code = STD._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patches
        )
        directory[symbol] = code
        names[id(code)] = entry["name"]
        origins[id(code)] = role
        if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
            macros.add(symbol)
    return {
        "manifest": bind(path), "blob": bind(blob_path),
        "entries": len(manifest["entries"]),
        "code_bytes": int(manifest["code_bytes"]),
    }


def manifest_paths(canonical_manifest: Path) -> tuple[dict[str, Any], Path, Path]:
    canonical_value = load(canonical_manifest)
    static = canonical_value["static_plane"]
    stdlib = ROOT / static["stdlib_manifest"]["path"]
    carrier = ROOT / static["compiler_carrier"]["path"]
    require(bind(stdlib)["sha256"] == static["stdlib_manifest"]["sha256"],
            "canonical stdlib binding drift")
    require(bind(carrier)["sha256"] == static["compiler_carrier"]["sha256"],
            "canonical carrier binding drift")
    return canonical_value, stdlib, carrier


def decode_definition(
    heap: B.Heap, value: int, name: str
) -> B.CodeObject:
    compiled = proper_list(heap, value, name + ".compiled")
    require(len(compiled) == 1, name + " helper count drift")
    fields = proper_list(heap, compiled[0], name)
    require(len(fields) == 5, name + " CodeObject shape drift")
    literals = proper_list(heap, fields[3], name + ".literals")
    payload = bytes(
        fixnum(item, name + ".payload")
        for item in proper_list(heap, fields[4], name + ".payload-list")
    )
    return B.CodeObject(
        fixnum(fields[0], name + ".nargs"),
        fixnum(fields[1], name + ".nlocals"),
        fixnum(fields[2], name + ".flags"), tuple(literals), payload,
    )


def ast_cons_cells(form: Any) -> int:
    if not isinstance(form, list):
        return 0
    return len(form) + sum(ast_cons_cells(item) for item in form)


def run_form(
    label: str, source: str, canonical_manifest: Path,
    *, publish_probe: bool = False,
) -> dict[str, Any]:
    canonical_value, stdlib_path, carrier_path = manifest_paths(canonical_manifest)
    heap = C.prepare_heap([])
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    names: dict[int, str] = {}
    origins: dict[int, str] = {}
    stdlib = load_manifest_entries(
        heap, stdlib_path, "product-runtime", directory, macros, names, origins
    )
    carrier = load_manifest_entries(
        heap, carrier_path, "compiler-carrier", directory, macros, names, origins
    )
    ledger = load(ABI_LEDGER)
    if publish_probe:
        setup_vm = B.P0VM(
            heap=heap, directory=directory, macro_symbols=macros,
            max_steps=10_000_000, code_names=names,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
        probe_form = setup_vm._compiler_form_obj(
            C.parse_one("(defun probe (x) x)")
        )
        probe_compiled = setup_vm.run(
            directory[heap.intern("%c2-compile-form")], [probe_form]
        )
        probe_code = decode_definition(heap, probe_compiled, "probe")
        directory[heap.intern("probe")] = probe_code
        names[id(probe_code)] = "probe"
        origins[id(probe_code)] = "owner-published-definition"
        require(probe_code.encode().hex() == "b50100020200000b05",
                "probe identity drift")

    parsed = C.parse_one(source)
    trace = PipelineTrace(origins)
    vm = PipelineVM(
        heap=heap, directory=directory, macro_symbols=macros,
        max_steps=10_000_000, trace=trace, code_names=names,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    form = vm._compiler_form_obj(parsed)
    heap_after_read = len(heap.cells)
    outcome: dict[str, Any]
    try:
        result = vm.run(directory[heap.intern("lcc-run")], [form])
    except InstallBoundary as boundary:
        outcome = {
            "route": "compile-then-transient-install",
            "install_name": heap.obj_to_text(boundary.args[1]),
            "compiled": decode_compiled(heap, boundary.args[0]),
        }
    else:
        outcome = {
            "route": "published-direct-call",
            "result": heap.obj_to_text(result),
            "compiled": None,
        }
    summary = trace.summary()
    require(summary["instructions"] == vm.steps, "trace/VM step drift")
    form_cells = ast_cons_cells(parsed)
    return {
        "id": label,
        "source": source,
        "reader_structure": {
            "source_bytes_ascii": len(source.encode("ascii")),
            "form_cons_cells": form_cells,
            "lcc_first_wrapper_cons_cells": 4,
            "pre_lcc_cons_cells": form_cells + 4,
            "time_authority": "structural count only; no reader wall-time claimed",
        },
        "pipeline": summary,
        "outcome": outcome,
        "host_heap_cells_allocated_after_read": len(heap.cells) - heap_after_read,
        "world": {
            "canonical_manifest": bind(canonical_manifest),
            "product_build_id": canonical_value["static_plane"]["product_build_id"],
            "stdlib": stdlib,
            "compiler_carrier": carrier,
        },
    }


FORM_CASES = (
    ("primitive-direct", "(+ 1 2)", False),
    ("owner-published-direct", "(probe 41)", True),
    ("nested-fixnum-arithmetic", "(+ 1 2 (+ 3 4 (- 3 1)))", False),
    ("nested-list-read", "(car (cdr lst))", False),
    ("setq-special-form", "(setq x 1)", False),
    ("five-cell-list-direct", "(list 1 2 3 4 5)", False),
)


def world_rows(canonical_manifest: Path) -> dict[str, Any]:
    rows = {
        label: run_form(
            label, source, canonical_manifest, publish_probe=publish_probe
        )
        for label, source, publish_probe in FORM_CASES
    }
    common = next(iter(rows.values()))["world"]
    for row in rows.values():
        require(row.pop("world") == common, "per-form world binding drift")
    return {"authority": common, "forms": rows}


def projection(value: dict[str, Any], instructions: int) -> dict[str, Any]:
    constants = value["pricing_authorities"]["historical_vm_projection"]["constants"]
    micros = instructions * constants["microseconds_per_vm_instruction"]
    return {
        "instructions": instructions,
        "microseconds": micros,
        "milliseconds": micros / 1000.0,
        "frames": micros / value["pricing_authorities"]["frame_microseconds"],
        "claim_limit": "historical projection, not a Link-96 target measurement",
    }


def source_and_docs() -> dict[str, Any]:
    repl = REPL_SOURCE.read_text(encoding="utf-8")
    reader = READER_SOURCE.read_text(encoding="utf-8")
    runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    experience = EXPERIENCE_PLAN.read_text(encoding="utf-8")
    repl_rows = [
        "obj form = read_expr(&p);",
        "q = cons(form, NIL);",
        "q = cons(intern(\"quote\"), q);",
        "q = cons(q, NIL);",
        "q = cons(lccrun, q);",
        "print_obj(eval(q));",
    ]
    reader_rows = [
        "cell = cons(value, NIL);",
        "cell_set_b(tail, cell);",
        "obj read_expr(const char **p)",
    ]
    runtime_rows = [
        "obj c2_product_install(obj fnlist, obj definition_name)",
        "emit = c2_session_emit_reset();",
        "append_ok = c2_append_begin(length, &before, &main",
        "result = vm_run_dir((int)main, 0, 0);",
        "if (!c2_append_rollback(&before))",
    ]
    plan_rows = [
        "`(time (point-y test))` → 0",
        "`(time (list 1 2 3 4 5))` → **0 frames for five allocations**",
        "between RETURN and body execution",
        "Reader, outer expansion and\nclassification, LCC compile",
        "frames-per-form, not seconds-per-form",
    ]
    experience_rows = [
        "REPL per-form reactivity",
        "third experience pillar",
        "no seconds-per-form interaction",
    ]
    require(all(row in repl for row in repl_rows), "REPL route drift")
    require(all(row in reader for row in reader_rows), "reader route drift")
    require(all(row in runtime for row in runtime_rows), "transient suffix drift")
    require(all(row in plan for row in plan_rows), "owner correction drift")
    require(all(row in experience for row in experience_rows),
            "experience-plan third pillar absent")
    return {
        "owner_correction": bind_git(
            OWNER_CORRECTION, "docs/planning/post-v1.4.0-direction-plan.md"
        ),
        "repl": {"authority": bind(REPL_SOURCE), "projection": repl_rows},
        "reader": {"authority": bind(READER_SOURCE), "projection": reader_rows},
        "transient_install": {
            "authority": bind(RUNTIME_SOURCE), "projection": runtime_rows,
        },
        "current_direction_plan": bind(PLAN),
        "experience_plan": bind(EXPERIENCE_PLAN),
    }


def gate_wiring() -> dict[str, Any]:
    text = GATES.read_text(encoding="utf-8")
    rows = [
        "c2-repl-pipeline-cost-attribution-selftest:",
        "python3 tools/host-lisp/c2_repl_pipeline_cost_attribution.py selftest",
        "c2-repl-pipeline-cost-attribution-check: c2-repl-pipeline-cost-attribution-selftest",
        "python3 tools/host-lisp/c2_repl_pipeline_cost_attribution.py check",
        "check-source: c2-repl-pipeline-cost-attribution-check",
    ]
    require(all(row in text for row in rows), "pipeline gate wiring absent")
    return {"path": "mk/gates.mk", "semantic_projection": rows}


def core_receipt() -> dict[str, Any]:
    v140 = world_rows(V140_CANONICAL)
    link96 = world_rows(LINK96_CANONICAL)
    target = load(LINK57_TARGET)
    time_cal = load(TIME_CAL)
    vm_projection = load(VM_PROJECTION)
    require(
        target["captures"]["cold"]["first_to_last_frames"] == 43
        and target["captures"]["warm"]["first_to_last_frames"] == 44
        and target["conclusions"]["remaining_unstamped_frames"]
        == "17/18 frames occur before final emitter CRC or after journal clear in the compiler/REPL envelope",
        "historical target station authority drift",
    )
    hz = time_cal["M4_time"]["frames_per_second"]
    constants = vm_projection["bound_constants"]
    require(
        constants["historical_cycles_per_vm_instruction"] == 1100
        and constants["target_cpu_hz"] == 40_000_000
        and abs(hz - 51.96615805290813) < 1e-12,
        "historical projection constants drift",
    )
    frame_us = 1_000_000.0 / hz

    diffs: dict[str, Any] = {}
    for label, _source, _probe in FORM_CASES:
        old = v140["forms"][label]
        new = link96["forms"][label]
        require(old["outcome"]["route"] == new["outcome"]["route"],
                f"route diverged: {label}")
        diffs[label] = {
            "route": old["outcome"]["route"],
            "v1_4_instructions": old["pipeline"]["instructions"],
            "Link96_instructions": new["pipeline"]["instructions"],
            "delta_instructions": (
                new["pipeline"]["instructions"] - old["pipeline"]["instructions"]
            ),
            "v1_4_compiler_instructions": old["pipeline"]
                ["instructions_by_role"].get("compiler-carrier", 0),
            "Link96_compiler_instructions": new["pipeline"]
                ["instructions_by_role"].get("compiler-carrier", 0),
            "v1_4_install_calls": old["pipeline"]["install_calls"],
            "Link96_install_calls": new["pipeline"]["install_calls"],
        }

    expansion_functions = link96["forms"]["primitive-direct"]["pipeline"]
    functions = expansion_functions["instructions_by_function"]
    expansion_instructions = (
        functions.get("%c2-top-level-expand", 0)
        + functions.get("%c2-top-level-macro-p", 0)
        + functions.get("%lcc-macro-p", 0)
    )
    require(expansion_instructions == 18, "Link-94 expansion-stage price drift")
    require(
        diffs["primitive-direct"]["delta_instructions"] == 30
        and diffs["owner-published-direct"]["delta_instructions"] == 30
        and diffs["five-cell-list-direct"]["delta_instructions"] == 30,
        "direct-route world delta drift",
    )
    require(
        diffs["nested-list-read"]["delta_instructions"] == -103
        and diffs["setq-special-form"]["delta_instructions"] == -103,
        "compiler-route world delta drift",
    )
    require(
        all(diffs[name]["Link96_install_calls"] == 0 for name in (
            "primitive-direct", "owner-published-direct", "five-cell-list-direct"
        ))
        and all(diffs[name]["Link96_install_calls"] == 1 for name in (
            "nested-fixnum-arithmetic", "nested-list-read", "setq-special-form"
        )),
        "direct/transient route cardinality drift",
    )

    value: dict[str, Any] = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": (
            "ATTRIBUTED-PER-FORM-TRANSIENT-CEREMONY; "
            "LINK94-EXPANSION-NOT-DOMINANT; RUNTIME-BODY-EXONERATED"
        ),
        "scope": {
            "execution": "host exact-artifact replay plus historical target receipt",
            "product_bytes_changed": 0,
            "product_links": 0,
            "device_contacts": 0,
            "new_target_timing_measurements": 0,
            "fix_implemented": False,
            "release_claim": False,
        },
        "authorities": {
            "source_and_docs": source_and_docs(),
            "v1_4_canonical": bind(V140_CANONICAL),
            "Link96_canonical": bind(LINK96_CANONICAL),
            "historical_target_stations": bind(LINK57_TARGET),
            "frame_calibration": bind(TIME_CAL),
            "historical_vm_projection": bind(VM_PROJECTION),
            "abi_ledger": bind(ABI_LEDGER),
            "driver": bind(DRIVER),
            "gate_wiring": gate_wiring(),
        },
        "owner_hardware_rows": {
            "runtime_body": [
                {"form": "(+ 1 2)", "frames": 0},
                {"form": "(cdr lst)", "frames": 0},
                {"form": "(length l10)", "frames": 1},
                {"form": "(cdr qlst)", "frames": 0},
                {"form": "(time (point-y test))", "frames": 0},
                {"form": "(time (list 1 2 3 4 5))", "frames": 0},
            ],
            "amortized_outlier": {
                "form": "(cons 1 2)", "frames": 5,
                "disposition": (
                    "not a per-cell price: five allocations subsequently completed "
                    "inside one timed body in zero frames"
                ),
            },
            "claim": (
                "calls, reads, writes and allocation inside the timed body are "
                "healthy; the perceived delay is outside that body"
            ),
            "authority": "owner physical observations bound by 665fb1ce",
            "remeasured_here": False,
        },
        "worlds": {"released_v1_4_0": v140, "accepted_Link96": link96},
        "world_diff": diffs,
        "pricing_authorities": {
            "frame_hz": hz,
            "frame_microseconds": frame_us,
            "historical_vm_projection": {
                "authority": bind(VM_PROJECTION),
                "constants": {
                    "cycles_per_vm_instruction": 1100,
                    "target_cpu_hz": 40_000_000,
                    "microseconds_per_vm_instruction": 27.5,
                },
                "claim_limit": vm_projection["claim_limit"],
            },
            "transient_suffix_target_station_trace": {
                "cold_first_to_last_frames": 43,
                "warm_first_to_last_frames": 44,
                "cold_station_deltas": target["captures"]["cold"]
                    ["consecutive_frame_deltas"],
                "warm_station_deltas": target["captures"]["warm"]
                    ["consecutive_frame_deltas"],
                "station_order": target["stations"],
                "unobserved_envelope_frames_cold_warm": [17, 18],
                "derived_whole_envelope_frames_cold_warm": [60, 62],
                "claim_limit": (
                    "physical C2 Link-57 attribution for the same named serial "
                    "ceremony; structural price authority, not a Link-96 remeasurement"
                ),
            },
        },
        "stage_prices": {
            "reader": {
                "unit": "exact cons-cell structure plus four-cell lcc-first wrapper",
                "range_pre_lcc_cells": [
                    min(row["reader_structure"]["pre_lcc_cons_cells"]
                        for row in link96["forms"].values()),
                    max(row["reader_structure"]["pre_lcc_cons_cells"]
                        for row in link96["forms"].values()),
                ],
                "target_time": "unmeasured; no seconds claim",
            },
            "Link94_outer_expansion": {
                "exact_vm_instructions_nonmacro_form": expansion_instructions,
                "nested_form_instructions": sum(
                    link96["forms"]["nested-fixnum-arithmetic"]["pipeline"]
                    ["instructions_by_function"].get(name, 0)
                    for name in (
                        "%c2-top-level-expand", "%c2-top-level-macro-p",
                        "%lcc-macro-p",
                    )
                ),
                "historical_projection": None,
                "classification": (
                    "outer-only constant probe; present but not seconds-dominant"
                ),
            },
            "world_delta_direct_route": {
                "exact_vm_instructions": 30,
                "historical_projection": None,
                "classification": "sub-frame by two orders of magnitude",
            },
            "compiler_carrier": {
                "nested_list_read": {
                    "v1_4": diffs["nested-list-read"]["v1_4_compiler_instructions"],
                    "Link96": diffs["nested-list-read"]["Link96_compiler_instructions"],
                },
                "setq": {
                    "v1_4": diffs["setq-special-form"]["v1_4_compiler_instructions"],
                    "Link96": diffs["setq-special-form"]["Link96_compiler_instructions"],
                },
                "classification": (
                    "Link96 carrier work is lower in both compiled counterprobes; "
                    "the Link94 change is not a seconds-class compiler regression"
                ),
            },
            "compiler_window_pressure": {
                "nested_list_read_events": {
                    "v1_4": (
                        v140["forms"]["nested-list-read"]["pipeline"]
                        ["initial_window_count"]
                        + v140["forms"]["nested-list-read"]["pipeline"]
                        ["refill_count"]
                    ),
                    "Link96": (
                        link96["forms"]["nested-list-read"]["pipeline"]
                        ["initial_window_count"]
                        + link96["forms"]["nested-list-read"]["pipeline"]
                        ["refill_count"]
                    ),
                },
                "nested_fixnum_events": {
                    "v1_4": (
                        v140["forms"]["nested-fixnum-arithmetic"]["pipeline"]
                        ["initial_window_count"]
                        + v140["forms"]["nested-fixnum-arithmetic"]["pipeline"]
                        ["refill_count"]
                    ),
                    "Link96": (
                        link96["forms"]["nested-fixnum-arithmetic"]["pipeline"]
                        ["initial_window_count"]
                        + link96["forms"]["nested-fixnum-arithmetic"]["pipeline"]
                        ["refill_count"]
                    ),
                },
                "nested_fixnum_compiled_identity_equal": (
                    v140["forms"]["nested-fixnum-arithmetic"]["outcome"]
                    ["compiled"] == link96["forms"]["nested-fixnum-arithmetic"]
                    ["outcome"]["compiled"]
                ),
                "target_time": (
                    "not projected: no current per-window target cost authority"
                ),
                "classification": (
                    "form-shape scaling is in compiler work/window traffic, not "
                    "recursive Link94 outer expansion"
                ),
            },
            "transient_install_execute_rollback": {
                "target_first_to_last_frames_cold_warm": [43, 44],
                "derived_whole_envelope_frames_cold_warm": [60, 62],
                "repeated_for_every_non_direct_form": True,
                "classification": "dominant measured per-form cost class",
            },
        },
        "attribution": {
            "boundary": "after RETURN and before the user body starts",
            "mechanism": (
                "every non-direct top-level form repeats the serial compile, "
                "emit, transient append/install, execute and rollback ceremony"
            ),
            "new_vs_always_present": (
                "the seconds-class ceremony predates v1.4.0; Link94 adds an "
                "18-instruction outer expansion stage, while the accepted Link96 "
                "carrier is cheaper on both compiled counterprobes"
            ),
            "direct_fastpath_explanation": (
                "published calls and primitive bytecode calls with already-direct "
                "arguments bypass compile/install; this explains probe(41) and "
                "flat literal forms without invoking a runtime-path defect"
            ),
            "runtime_body": "exonerated by the owner frame rows",
            "reader": "structurally bounded here but not target-timed",
            "Link94_expansion": "priced and exonerated as the dominant term",
            "optimization_target": (
                "remove or amortize the per-form transient ceremony; do not "
                "optimize healthy CAR/CDR, allocation, accessor or game-loop paths"
            ),
        },
        "experience_block_disposition": {
            "track": "startup & require experience",
            "third_pillar": "REPL per-form reactivity",
            "phase_A": (
                "use this ledger as the baseline and price reader, routing/carrier "
                "and transient suffix separately"
            ),
            "phase_C_candidate_order": [
                "direct-path coverage for semantically complete forms",
                "reuse/amortize transient installation without weakening rollback",
                "reader/compiler work only if the residual price justifies it",
            ],
            "v1_5_gate": "no seconds-per-form interaction",
            "permanent_release_smokes": [
                "published direct call", "nested compiled form", "setq",
                "list allocation inside time", "string operation",
            ],
            "game_loop_claim": (
                "compiled runtime execution is currently exonerated; this receipt "
                "does not yet constitute a game-frame hardware acceptance"
            ),
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "device_contacts": 0,
        },
        "withdrawn_receipt": {
            "path": (
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-link96-cons-access-cost-world-diff-receipt.json"
            ),
            "reason": (
                "superseded: it promoted an isolated five-frame event to a "
                "per-access cost despite the later zero-frame five-allocation row"
            ),
            "retained_as_authority": False,
        },
        "claim_limit": (
            "This receipt exactly replays the canonical v1.4.0 and Link96 "
            "runtime/compiler artifacts through the install boundary, binds the "
            "historical target station trace, and attributes the seconds-class "
            "interaction to the repeated transient ceremony. VM time conversions "
            "are historical projections, reader time is unmeasured, and no fix, "
            "Link96 target timing, v1.5 release, or game-frame acceptance is claimed."
        ),
    }
    value["stage_prices"]["Link94_outer_expansion"]["historical_projection"] = (
        projection(value, expansion_instructions)
    )
    value["stage_prices"]["world_delta_direct_route"]["historical_projection"] = (
        projection(value, 30)
    )
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT
        and value.get("status") == (
            "ATTRIBUTED-PER-FORM-TRANSIENT-CEREMONY; "
            "LINK94-EXPANSION-NOT-DOMINANT; RUNTIME-BODY-EXONERATED"
        ),
        "receipt identity drift",
    )
    require(value.get("scope") == {
        "execution": "host exact-artifact replay plus historical target receipt",
        "product_bytes_changed": 0,
        "product_links": 0,
        "device_contacts": 0,
        "new_target_timing_measurements": 0,
        "fix_implemented": False,
        "release_claim": False,
    }, "scope broadened")
    rows = value["world_diff"]
    require(
        rows["primitive-direct"]["delta_instructions"] == 30
        and rows["owner-published-direct"]["delta_instructions"] == 30
        and rows["five-cell-list-direct"]["delta_instructions"] == 30,
        "direct world delta drift",
    )
    require(
        rows["nested-list-read"]["delta_instructions"] == -103
        and rows["setq-special-form"]["delta_instructions"] == -103,
        "compiled world delta drift",
    )
    require(
        all(rows[name]["Link96_install_calls"] == 0 for name in (
            "primitive-direct", "owner-published-direct", "five-cell-list-direct"
        ))
        and all(rows[name]["Link96_install_calls"] == 1 for name in (
            "nested-fixnum-arithmetic", "nested-list-read", "setq-special-form"
        )),
        "route/install cardinality drift",
    )
    stages = value["stage_prices"]
    require(
        stages["Link94_outer_expansion"]["exact_vm_instructions_nonmacro_form"] == 18
        and stages["Link94_outer_expansion"]["nested_form_instructions"] == 18
        and stages["Link94_outer_expansion"]["classification"]
        == "outer-only constant probe; present but not seconds-dominant"
        and stages["transient_install_execute_rollback"]
        ["target_first_to_last_frames_cold_warm"] == [43, 44]
        and stages["transient_install_execute_rollback"]
        ["derived_whole_envelope_frames_cold_warm"] == [60, 62]
        and stages["transient_install_execute_rollback"]
        ["repeated_for_every_non_direct_form"] is True,
        "stage-price attribution drift",
    )
    require(
        stages["compiler_window_pressure"]["nested_list_read_events"]
        == {"v1_4": 368, "Link96": 258}
        and stages["compiler_window_pressure"]["nested_fixnum_events"]
        == {"v1_4": 701, "Link96": 443}
        and stages["compiler_window_pressure"]
        ["nested_fixnum_compiled_identity_equal"] is True,
        "compiler window/shape attribution drift",
    )
    owner = value["owner_hardware_rows"]
    require(
        owner["runtime_body"][-1] == {
            "form": "(time (list 1 2 3 4 5))", "frames": 0
        }
        and owner["amortized_outlier"]["frames"] == 5
        and owner["remeasured_here"] is False,
        "owner evidence overclaim/drift",
    )
    attribution = value["attribution"]
    require(
        attribution["boundary"] == "after RETURN and before the user body starts"
        and attribution["runtime_body"] == "exonerated by the owner frame rows"
        and attribution["reader"] == "structurally bounded here but not target-timed"
        and attribution["Link94_expansion"]
        == "priced and exonerated as the dominant term",
        "attribution claim drift",
    )
    disposition = value["experience_block_disposition"]
    require(
        disposition["third_pillar"] == "REPL per-form reactivity"
        and disposition["v1_5_gate"] == "no seconds-per-form interaction"
        and disposition["permanent_release_smokes"] == [
            "published direct call", "nested compiled form", "setq",
            "list allocation inside time", "string operation",
        ],
        "experience/release disposition drift",
    )
    require(
        value["withdrawn_receipt"]["retained_as_authority"] is False
        and value["accounting"] == {
            "product_bytes_changed": 0, "product_links": 0,
            "hardware_runs": 0, "device_contacts": 0,
        },
        "withdrawal/accounting drift",
    )


def mutation_proof(value: dict[str, Any]) -> dict[str, str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-runtime-slow": lambda x: x["attribution"].__setitem__(
            "runtime_body", "slow"
        ),
        "turn-five-allocations-slow": lambda x: x["owner_hardware_rows"]
            ["runtime_body"][-1].__setitem__("frames", 25),
        "hide-cons-outlier": lambda x: x["owner_hardware_rows"]
            ["amortized_outlier"].__setitem__("frames", 0),
        "claim-reader-timed": lambda x: x["attribution"].__setitem__(
            "reader", "target timed"
        ),
        "inflate-expansion": lambda x: x["stage_prices"]
            ["Link94_outer_expansion"].__setitem__(
                "exact_vm_instructions_nonmacro_form", 18000
            ),
        "blame-expansion": lambda x: x["stage_prices"]
            ["Link94_outer_expansion"].__setitem__(
                "classification", "seconds dominant"
            ),
        "make-expansion-per-node": lambda x: x["stage_prices"]
            ["Link94_outer_expansion"].__setitem__(
                "nested_form_instructions", 90
            ),
        "hide-window-scaling": lambda x: x["stage_prices"]
            ["compiler_window_pressure"]["nested_fixnum_events"]
            .__setitem__("Link96", 258),
        "remove-direct-delta": lambda x: x["world_diff"]
            ["primitive-direct"].__setitem__("delta_instructions", 0),
        "invent-compiler-regression": lambda x: x["world_diff"]
            ["nested-list-read"].__setitem__("delta_instructions", 103),
        "compile-primitive-direct": lambda x: x["world_diff"]
            ["primitive-direct"].__setitem__("Link96_install_calls", 1),
        "skip-nested-install": lambda x: x["world_diff"]
            ["nested-list-read"].__setitem__("Link96_install_calls", 0),
        "erase-target-suffix": lambda x: x["stage_prices"]
            ["transient_install_execute_rollback"].__setitem__(
                "target_first_to_last_frames_cold_warm", [0, 0]
            ),
        "erase-whole-envelope": lambda x: x["stage_prices"]
            ["transient_install_execute_rollback"].__setitem__(
                "derived_whole_envelope_frames_cold_warm", [0, 0]
            ),
        "deny-per-form-repeat": lambda x: x["stage_prices"]
            ["transient_install_execute_rollback"].__setitem__(
                "repeated_for_every_non_direct_form", False
            ),
        "drop-repl-pillar": lambda x: x["experience_block_disposition"]
            .__setitem__("third_pillar", "require only"),
        "ship-seconds": lambda x: x["experience_block_disposition"]
            .__setitem__("v1_5_gate", "seconds accepted"),
        "drop-compiled-smoke": lambda x: x["experience_block_disposition"]
            ["permanent_release_smokes"].pop(1),
        "retain-stale-receipt": lambda x: x["withdrawn_receipt"]
            .__setitem__("retained_as_authority", True),
        "claim-device-contact": lambda x: x["accounting"]
            .__setitem__("device_contacts", 1),
        "claim-fix": lambda x: x["scope"].__setitem__("fix_implemented", True),
        "claim-release": lambda x: x["scope"].__setitem__("release_claim", True),
    }
    rejected: dict[str, str] = {}
    for name, mutate in mutations.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            audit(candidate)
        except PipelineError as error:
            rejected[name] = str(error)
        else:
            raise PipelineError(f"mutation survived: {name}")
    require(len(rejected) == 22, "mutation count drift")
    return rejected


def derive() -> dict[str, Any]:
    value = core_receipt()
    audit(value)
    value["mutation_proof"] = {
        "expected": 22,
        "rejected": mutation_proof(value),
    }
    return value


def check_sealed_receipt() -> dict[str, Any]:
    """Validate the accepted pricing baseline without rebinding its live world."""
    value = load(RECEIPT)
    audit(value)
    proof = value.get("mutation_proof")
    require(
        value.get("format") == FORMAT
        and value.get("recorded_on") == RECORDED_ON
        and isinstance(proof, dict)
        and proof.get("expected") == 22
        and proof.get("rejected") == mutation_proof(value),
        "sealed REPL-pipeline attribution semantic replay drift",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.command == "run":
        value = derive()
        write_json(RECEIPT, value)
        print(f"wrote {RECEIPT.relative_to(ROOT)}")
        return 0
    if args.command == "check":
        check_sealed_receipt()
        print("REPL pipeline cost attribution: PASS")
        return 0
    value = core_receipt()
    audit(value)
    require(len(mutation_proof(value)) == 22, "mutation selftest drift")
    print("REPL pipeline cost attribution selftest: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        PipelineError, B.VMError, C.CompileError, KeyError, IndexError,
        TypeError, ValueError,
    ) as error:
        print(f"REPL pipeline cost attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
