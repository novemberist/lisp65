#!/usr/bin/env python3
"""Dynamic P0 bytecode histogram for IDE hot-path tuning.

This is a host-VM trace, not a cycle-accurate MEGA65 measurement. Its job is to
rank dynamic opcode pairs and call targets before we spend ABI budget on
superinstructions or IDE helper fusion.
"""

from __future__ import annotations

import argparse
from collections import Counter
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as S  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "tests" / "bytecode" / "stdlib" / "p0-stdlib-subset.json"
DEFAULT_OUT = ROOT / "build" / "bytecode" / "ide-bytecode-dynamic.txt"
SYMFN_EXT_CALL_KINDS = frozenset(("CALL", "TAILCALL"))


class DynamicReportError(Exception):
    pass


class TraceCollector:
    def __init__(self, name: str, heap: B.Heap):
        self.name = name
        self.heap = heap
        self.stack = []
        self.steps = 0
        self.max_depth = 0
        self.op_counts = Counter()
        self.op_detail_counts = Counter()
        self.pair_counts = Counter()
        self.pair_detail_counts = Counter()
        self.function_entries = Counter()
        self.function_steps = Counter()
        self.function_op_counts = Counter()
        self.call_counts = Counter()
        self.call_site_counts = Counter()
        self.results = []
        self.max_native_frame_check = 0
        self.max_native_stack_used = 0
        self.max_native_frame_detail = "-"
        self.max_native_stack_detail = "-"

    def enter(self, name, code, args):
        self.function_entries[name] += 1
        self.stack.append({"name": name, "last": None, "last_detail": None})
        self.max_depth = max(self.max_depth, len(self.stack))

    def exit(self, name, code):
        if self.stack:
            self.stack.pop()

    def instruction(self, name, code, pc, spec, operand):
        detail = self._detail(code, spec, operand)
        self.steps += 1
        self.op_counts[spec.mnemonic] += 1
        self.op_detail_counts[detail] += 1
        self.function_steps[name] += 1
        self.function_op_counts[(name, spec.mnemonic)] += 1
        if self.stack:
            frame = self.stack[-1]
            if frame["last"] is not None:
                self.pair_counts[(frame["last"], spec.mnemonic)] += 1
                self.pair_detail_counts[(frame["last_detail"], detail)] += 1
            frame["last"] = spec.mnemonic
            frame["last_detail"] = detail

    def call(self, caller, kind, target, argc, pc=None, resolved=False):
        key = (kind, target, argc)
        self.call_counts[key] += 1
        self.call_site_counts[(caller, kind, target, argc)] += 1

    def native_frame(self, name, code, args, native_base, frame_slots, reserve_slots, tail):
        used = native_base + frame_slots + reserve_slots
        if used > self.max_native_frame_check:
            self.max_native_frame_check = used
            self.max_native_frame_detail = (
                "%s:%s base=%d frame=%d reserve=%d tail=%s"
                % (self.name, name, native_base, frame_slots, reserve_slots, "yes" if tail else "no")
            )

    def native_stack(self, name, used):
        if used > self.max_native_stack_used:
            self.max_native_stack_used = used
            self.max_native_stack_detail = "%s:%s used=%d" % (self.name, name, used)

    def _literal_name(self, code, idx):
        if idx >= len(code.littab):
            return "<bad-lit-%d>" % idx
        lit = code.littab[idx]
        if self.heap.symbolp(lit):
            return self.heap.symbol_name(lit)
        return self.heap.obj_to_text(lit)

    def _detail(self, code, spec, operand):
        m = spec.mnemonic
        if m in ("CALL", "TAILCALL"):
            lit_idx, argc = operand
            return "%s:%s/%d" % (m, self._literal_name(code, lit_idx), argc)
        if m == "CALLPRIM":
            prim_id, argc = operand
            return "%s:%s/%d" % (m, B.PRIM_IDS.get(prim_id, "#%d" % prim_id), argc)
        if m in ("PUSHI8", "PUSHARGN", "LOADL", "STOREL"):
            return "%s:%s" % (m, operand)
        if m == "PUSHLIT":
            return "PUSHLIT:%s" % self._literal_name(code, operand)
        if m in ("JMPREL", "JFALSEREL"):
            return "%s:%+d" % (m, operand)
        return m


class Runtime:
    def __init__(
        self,
        suite_path: Path,
        max_steps: int,
        native_vm_maxargs: int = 12,
        native_initial_base: int = 0,
    ):
        self.suite_path = suite_path
        self.max_steps = max_steps
        self.native_vm_maxargs = native_vm_maxargs
        self.native_initial_base = native_initial_base
        self.suite = S._read_suite(str(suite_path))
        self.suite_path = Path(self.suite.get("_suite_path", suite_path))
        (
            self.heap,
            self.names,
            self.code_by_name,
            self.entry_flags_by_name,
            self.resident_entry_flags,
            self.bundle,
            self.directory,
            self.cases,
            self.entry_names,
            self.inliner,
        ) = S._compile_suite(self.suite)
        self.macro_symbols = S._macro_symbol_objs(
            self.heap, self.entry_flags_by_name, self.resident_entry_flags
        )
        self.max_call_args = S._validate_vm_limit_expectations(
            self.suite, self.heap, self.code_by_name
        )
        self.abi_profile, self.abi_ledger = S._suite_abi(self.suite)
        self.code_names = {
            id(code): self.heap.symbol_name(sym)
            for sym, code in self.directory.items()
            if self.heap.symbolp(sym)
        }

    def run_named(self, name, args=(), trace=None):
        sym = self.heap.intern(name)
        if sym not in self.directory:
            raise DynamicReportError("missing bytecode function: %s" % name)
        vm = B.P0VM(
            heap=self.heap,
            directory=self.directory,
            macro_symbols=self.macro_symbols,
            max_steps=self.max_steps,
            max_call_args=self.max_call_args,
            trace=trace,
            code_names=self.code_names,
            native_vm_maxargs=self.native_vm_maxargs,
            native_initial_base=self.native_initial_base,
            abi_profile=self.abi_profile,
            abi_ledger=self.abi_ledger,
        )
        return vm.run(self.directory[sym], list(args))

    def has_function(self, name):
        return self.heap.intern(name) in self.directory

    def obj(self, spec):
        return B.obj_from_json(self.heap, spec)

    def make_state(self, lines, line=0, column=0, rendered=False):
        buffer_obj = self.run_named(
            "ide-make-buffer",
            [self.obj({"string": "scratch"}), self.obj([{"string": s} for s in lines])],
        )
        buffer_obj = self.run_named(
            "ide-set-point", [buffer_obj, B.mkfix(line), B.mkfix(column)]
        )
        state = self.run_named("ide-make-state", [buffer_obj])
        if rendered:
            state = self.run_named("ide-render", [state])
        return state

    def key_event(self, code):
        return self.obj([{"symbol": "key"}, int(code), None])


def _run_scenarios(rt: Runtime):
    collectors = []

    def scenario(name, fn):
        collector = TraceCollector(name, rt.heap)
        result = fn(collector)
        if result is not None:
            collector.results.append(rt.heap.obj_to_text(result)[:160])
        collectors.append(collector)

    scenario(
        "ide-step-self-insert",
        lambda tr: rt.run_named(
            "ide-step",
            [rt.make_state(["hello"], line=0, column=5), rt.key_event(33)],
            trace=tr,
        ),
    )
    scenario(
        "ide-render-cold-short",
        lambda tr: rt.run_named(
            "ide-render", [rt.make_state(["hello"], line=0, column=5)], trace=tr
        ),
    )
    def warm_insert_render(tr):
        state = rt.make_state(["hello"], line=0, column=5, rendered=True)
        state = rt.run_named("ide-step", [state, rt.key_event(33)], trace=tr)
        return rt.run_named("ide-render", [state], trace=tr)

    scenario("ide-render-warm-after-insert", warm_insert_render)
    scenario(
        "ide-step-long-line-insert",
        lambda tr: rt.run_named(
            "ide-step",
            [
                rt.make_state(
                    ["abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"],
                    line=0,
                    column=62,
                ),
                rt.key_event(33),
            ],
            trace=tr,
        ),
    )
    def repeat_self_insert_10(tr):
        state = rt.make_state([""], line=0, column=0)
        for _ in range(10):
            state = rt.run_named("ide-step", [state, rt.key_event(120)], trace=tr)
        return state

    scenario("ide-repeat-self-insert-10", repeat_self_insert_10)

    def type_render_5(tr):
        state = rt.make_state([""], line=0, column=0, rendered=True)
        for code in (104, 101, 108, 108, 111):
            state = rt.run_named("ide-step", [state, rt.key_event(code)], trace=tr)
            state = rt.run_named("ide-render", [state], trace=tr)
        return state

    scenario("ide-type-render-5", type_render_5)
    scenario(
        "ide-step-delete-backward",
        lambda tr: rt.run_named(
            "ide-step",
            [rt.make_state(["hello"], line=0, column=5), rt.key_event(20)],
            trace=tr,
        ),
    )
    scenario(
        "ide-step-delete-forward",
        lambda tr: rt.run_named(
            "ide-step",
            [rt.make_state(["hello"], line=0, column=1), rt.key_event(4)],
            trace=tr,
        ),
    )

    def cached_delete(tr):
        state = rt.run_named(
            "ide-step",
            [rt.make_state(["hello"], line=0, column=5), rt.key_event(33)],
        )
        return rt.run_named("ide-step", [state, rt.key_event(20)], trace=tr)

    scenario("ide-step-delete-cached", cached_delete)

    def navigation_8(tr):
        state = rt.make_state(["alpha", "be", "gamma", "delta"], line=1, column=1)
        for code in (157, 29, 29, 145, 17, 17, 157, 145):
            state = rt.run_named("ide-step", [state, rt.key_event(code)], trace=tr)
        return state

    scenario("ide-step-navigation-8", navigation_8)
    scenario(
        "ide-render-cold-25-lines",
        lambda tr: rt.run_named(
            "ide-render",
            [
                rt.make_state(
                    ["line-%02d abcdefghijklmnopqrstuvwxyz" % i for i in range(25)],
                    line=12,
                    column=8,
                )
            ],
            trace=tr,
        ),
    )

    def dirty_scan_25(tr):
        old_lines = ["line-%02d" % i for i in range(25)]
        new_lines = list(old_lines)
        new_lines[7] = "line-07!"
        return rt.run_named(
            "ide-dirty-line-indices",
            [
                rt.obj([{"string": s} for s in old_lines]),
                rt.obj([{"string": s} for s in new_lines]),
                B.mkfix(7),
                B.mkfix(6),
            ],
            trace=tr,
        )

    scenario("ide-dirty-scan-25-lines", dirty_scan_25)
    return collectors


def _defun_form(name, params, body):
    return [{"symbol": "defun"}, {"symbol": name}, [{"symbol": p} for p in params], body]


def _compiler_forms():
    return [
        (
            "lcc-compile-small-defun",
            _defun_form(
                "dyn-small",
                ["x"],
                [{"symbol": "+"}, {"symbol": "x"}, 1],
            ),
        ),
        (
            "lcc-compile-branch-defun",
            _defun_form(
                "dyn-branch",
                ["x", "y"],
                [
                    {"symbol": "if"},
                    [{"symbol": "<"}, {"symbol": "x"}, {"symbol": "y"}],
                    [{"symbol": "+"}, {"symbol": "x"}, {"symbol": "y"}],
                    [{"symbol": "-"}, {"symbol": "x"}, {"symbol": "y"}],
                ],
            ),
        ),
        (
            "lcc-compile-closure-defun",
            _defun_form(
                "dyn-closure",
                ["n"],
                [
                    {"symbol": "lambda"},
                    [{"symbol": "x"}],
                    [{"symbol": "+"}, {"symbol": "x"}, {"symbol": "n"}],
                ],
            ),
        ),
    ]


def _run_compiler_scenarios(rt: Runtime):
    if not rt.has_function("lcc-compile-obj"):
        raise DynamicReportError("compiler scenarios require lcc-compile-obj in the suite")

    collectors = []
    for name, form in _compiler_forms():
        collector = TraceCollector(name, rt.heap)
        result = rt.run_named("lcc-compile-obj", [rt.obj(form)], trace=collector)
        collector.results.append(rt.heap.obj_to_text(result)[:160])
        collectors.append(collector)
    return collectors


def _merge(collectors, attr):
    out = Counter()
    for collector in collectors:
        out.update(getattr(collector, attr))
    return out


def _fmt_key(key):
    if isinstance(key, tuple):
        return " -> ".join(str(part) for part in key)
    return str(key)


def _counter_lines(counter, limit=20, width=48):
    if not counter:
        return ["  -"]
    lines = []
    for key, count in counter.most_common(limit):
        lines.append("  %-*s %6d" % (width, _fmt_key(key), count))
    return lines


def _parse_scenario_budget(spec: str):
    if "=" not in spec:
        raise argparse.ArgumentTypeError("scenario budget must be NAME=MAX")
    name, value = spec.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError("scenario budget name must not be empty")
    try:
        limit = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("scenario budget must use an integer MAX") from exc
    if limit < 0:
        raise argparse.ArgumentTypeError("scenario budget MAX must be >= 0")
    return name, limit


def _symfn_resolution_count(call_counts):
    return sum(
        count for (kind, _target, _argc), count in call_counts.items() if kind in SYMFN_EXT_CALL_KINDS
    )


def _symfn_target_counts(call_counts):
    counts = Counter()
    for (kind, target, argc), count in call_counts.items():
        if kind in SYMFN_EXT_CALL_KINDS:
            counts[(target, argc)] += count
    return counts


def _symfn_site_counts(call_site_counts):
    counts = Counter()
    for (caller, kind, target, argc), count in call_site_counts.items():
        if kind in SYMFN_EXT_CALL_KINDS:
            counts[(caller, target, argc)] += count
    return counts


def _candidate_lines(pair_counts):
    interesting = Counter()
    for (left, right), count in pair_counts.items():
        if count < 5:
            continue
        if right in ("CALL", "TAILCALL", "CALLPRIM"):
            interesting[(left, right)] += count
        elif left in ("PUSHI8", "LOADL", "PUSHARG0", "PUSHARG1", "PUSHARG2") and right in (
            "ADD",
            "SUB",
            "LESS",
            "GREATER",
            "EQ",
            "EQL",
            "JFALSEREL",
        ):
            interesting[(left, right)] += count
    return _counter_lines(interesting, limit=20, width=32)


def _write_report(path: Path, suite_path: Path, rt: Runtime, collectors):
    op_counts = _merge(collectors, "op_counts")
    op_detail_counts = _merge(collectors, "op_detail_counts")
    pair_counts = _merge(collectors, "pair_counts")
    pair_detail_counts = _merge(collectors, "pair_detail_counts")
    function_entries = _merge(collectors, "function_entries")
    function_steps = _merge(collectors, "function_steps")
    call_counts = _merge(collectors, "call_counts")
    call_site_counts = _merge(collectors, "call_site_counts")
    total_steps = sum(c.steps for c in collectors)
    symfn_resolutions = _symfn_resolution_count(call_counts)
    symfn_targets = _symfn_target_counts(call_counts)
    symfn_sites = _symfn_site_counts(call_site_counts)

    lines = [
        "# lisp65 IDE P0 dynamic bytecode histogram",
        "suite: %s" % suite_path,
        "scope: HOST P0 VM dynamic instruction trace",
        "cycle_accuracy: no",
        "dma_reload_accuracy: no",
        "purpose: rank opcode-pair/superinstruction candidates before MEGA65 timing work",
        "objects: %d" % len(rt.names),
        "code_bytes: %d" % len(rt.bundle.blob),
        "scenarios: %d" % len(collectors),
        "total_dynamic_instructions: %d" % total_steps,
        "symfn_ext_model: dynamic CALL/TAILCALL count; each resolves sym_function(target)",
        "symfn_ext_dynamic_resolutions: %d" % symfn_resolutions,
        "symfn_ext_unique_targets: %d" % len(symfn_targets),
        "symfn_ext_unique_call_sites: %d" % len(symfn_sites),
        "max_call_depth_observed: %d" % max(c.max_depth for c in collectors),
        "max_native_frame_check_observed: %d"
        % max(c.max_native_frame_check for c in collectors),
        "max_native_stack_used_observed: %d"
        % max(c.max_native_stack_used for c in collectors),
        "",
        "Scenario summary:",
        "name                                instr  symfn depth nframe nstack entries result",
    ]
    for c in collectors:
        result = c.results[0] if c.results else "-"
        lines.append(
            "%-34s %6d %6d %5d %6d %6d %7d %s"
            % (
                c.name,
                c.steps,
                _symfn_resolution_count(c.call_counts),
                c.max_depth,
                c.max_native_frame_check,
                c.max_native_stack_used,
                sum(c.function_entries.values()),
                result,
            )
        )

    lines.extend(["", "Top dynamic opcodes:"])
    lines.extend(_counter_lines(op_counts, limit=24, width=24))
    lines.extend(["", "Top dynamic opcode details:"])
    lines.extend(_counter_lines(op_detail_counts, limit=30, width=48))
    lines.extend(["", "Top dynamic opcode pairs (mnemonic):"])
    lines.extend(_counter_lines(pair_counts, limit=30, width=32))
    lines.extend(["", "Top dynamic opcode pairs (detailed):"])
    lines.extend(_counter_lines(pair_detail_counts, limit=35, width=76))
    lines.extend(["", "Superinstruction candidate families (dynamic pair counts):"])
    lines.extend(_candidate_lines(pair_counts))
    lines.extend(["", "Top functions by dynamic instructions:"])
    lines.extend(_counter_lines(function_steps, limit=35, width=40))
    lines.extend(["", "Top function entries:"])
    lines.extend(_counter_lines(function_entries, limit=35, width=40))
    lines.extend(["", "Top SYMFN_EXT dynamic call targets:"])
    lines.extend(_counter_lines(symfn_targets, limit=35, width=56))
    lines.extend(["", "Top SYMFN_EXT dynamic call sites:"])
    lines.extend(_counter_lines(symfn_sites, limit=45, width=76))
    lines.extend(["", "Top dynamic calls by target:"])
    lines.extend(_counter_lines(call_counts, limit=35, width=56))
    lines.extend(["", "Top dynamic call sites:"])
    lines.extend(_counter_lines(call_site_counts, limit=45, width=76))

    lines.extend(["", "Per-scenario hot pairs:"])
    for c in collectors:
        lines.append("")
        lines.append("[%s]" % c.name)
        lines.append("instructions: %d" % c.steps)
        lines.append("symfn_ext_resolutions: %d" % _symfn_resolution_count(c.call_counts))
        lines.append("top_pairs:")
        lines.extend(_counter_lines(c.pair_counts, limit=12, width=32))
        lines.append("top_functions:")
        lines.extend(_counter_lines(c.function_steps, limit=12, width=40))
        lines.append("top_symfn_targets:")
        lines.extend(_counter_lines(_symfn_target_counts(c.call_counts), limit=12, width=56))
        lines.append("top_calls:")
        lines.extend(_counter_lines(c.call_counts, limit=12, width=56))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(DEFAULT_SUITE), help="P0 stdlib suite JSON")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="report output path")
    ap.add_argument("--max-steps", type=int, default=500000)
    ap.add_argument("--check", action="store_true", help="fail if the trace is empty or misses render I/O")
    ap.add_argument(
        "--max-total-instructions",
        type=int,
        default=None,
        help="fail under --check if total dynamic instructions exceed this budget",
    )
    ap.add_argument(
        "--max-scenario-instructions",
        action="append",
        type=_parse_scenario_budget,
        default=[],
        metavar="NAME=MAX",
        help="fail under --check if a scenario exceeds its dynamic instruction budget",
    )
    ap.add_argument(
        "--include-compiler-scenarios",
        action="store_true",
        help="also trace lcc-compile-obj scenarios when the suite contains the compiler",
    )
    ap.add_argument(
        "--max-total-symfn-resolutions",
        type=int,
        default=None,
        help="fail under --check if dynamic CALL/TAILCALL lookups exceed this budget",
    )
    ap.add_argument(
        "--max-scenario-symfn-resolutions",
        action="append",
        type=_parse_scenario_budget,
        default=[],
        metavar="NAME=MAX",
        help="fail under --check if a scenario exceeds its CALL/TAILCALL lookup budget",
    )
    ns = ap.parse_args(argv)

    suite_path = Path(ns.suite)
    out = Path(ns.out)
    rt = Runtime(suite_path, max_steps=ns.max_steps)
    collectors = _run_scenarios(rt)
    if ns.include_compiler_scenarios:
        collectors.extend(_run_compiler_scenarios(rt))
    _write_report(out, rt.suite_path, rt, collectors)

    op_counts = _merge(collectors, "op_counts")
    pair_counts = _merge(collectors, "pair_counts")
    call_counts = _merge(collectors, "call_counts")
    total_steps = sum(c.steps for c in collectors)
    total_symfn_resolutions = _symfn_resolution_count(call_counts)
    if ns.check:
        errors = []
        if total_steps <= 0:
            errors.append("no dynamic instructions traced")
        if not pair_counts:
            errors.append("no dynamic opcode pairs traced")
        if not any(
            key[0] == "CALLPRIM" and key[1] in ("screen-write-string", "screen-put-char")
            for key in call_counts
        ):
            errors.append("render scenarios did not reach screen I/O")
        if ns.max_total_instructions is not None and total_steps > ns.max_total_instructions:
            errors.append(
                "total dynamic instructions %d exceed budget %d"
                % (total_steps, ns.max_total_instructions)
            )
        if (
            ns.max_total_symfn_resolutions is not None
            and total_symfn_resolutions > ns.max_total_symfn_resolutions
        ):
            errors.append(
                "total SYMFN_EXT dynamic resolutions %d exceed budget %d"
                % (total_symfn_resolutions, ns.max_total_symfn_resolutions)
            )
        scenario_steps = {c.name: c.steps for c in collectors}
        for name, limit in ns.max_scenario_instructions:
            if name not in scenario_steps:
                errors.append("scenario budget references unknown scenario: %s" % name)
            elif scenario_steps[name] > limit:
                errors.append(
                    "scenario %s dynamic instructions %d exceed budget %d"
                    % (name, scenario_steps[name], limit)
                )
        scenario_symfn = {c.name: _symfn_resolution_count(c.call_counts) for c in collectors}
        for name, limit in ns.max_scenario_symfn_resolutions:
            if name not in scenario_symfn:
                errors.append("SYMFN_EXT scenario budget references unknown scenario: %s" % name)
            elif scenario_symfn[name] > limit:
                errors.append(
                    "scenario %s SYMFN_EXT dynamic resolutions %d exceed budget %d"
                    % (name, scenario_symfn[name], limit)
                )
        if errors:
            for err in errors:
                print("ide-bytecode-dynamic-report: FAIL: %s" % err, file=sys.stderr)
            return 1

    top_pair = pair_counts.most_common(1)[0][0] if pair_counts else ("-", "-")
    print(
        "ide-bytecode-dynamic-report: WROTE %s scenarios=%d instructions=%d symfn=%d top_opcode=%s top_pair=%s"
        % (
            out,
            len(collectors),
            total_steps,
            total_symfn_resolutions,
            op_counts.most_common(1)[0][0] if op_counts else "-",
            "%s->%s" % top_pair,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
