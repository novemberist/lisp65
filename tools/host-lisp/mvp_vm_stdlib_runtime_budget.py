#!/usr/bin/env python3
"""Gate native VM rootstack pressure for the MVP bytecode stdlib."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as S  # noqa: E402
import ide_bytecode_dynamic_report as ID  # noqa: E402
import mvp_vm_stdlib_boot_budget as BB  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "tests" / "bytecode" / "stdlib" / "p0-stdlib-subset.json"


class RuntimeBudgetError(Exception):
    pass


class NativeRootTrace:
    def __init__(self, label: str):
        self.label = label
        self.max_native_frame_check = 0
        self.max_native_stack_used = 0
        self.max_native_frame_detail = "-"
        self.max_native_stack_detail = "-"

    def native_frame(self, name, code, args, native_base, frame_slots, reserve_slots, tail):
        used = native_base + frame_slots + reserve_slots
        if used > self.max_native_frame_check:
            self.max_native_frame_check = used
            self.max_native_frame_detail = (
                "%s:%s base=%d frame=%d reserve=%d tail=%s"
                % (self.label, name, native_base, frame_slots, reserve_slots, "yes" if tail else "no")
            )

    def native_stack(self, name, used):
        if used > self.max_native_stack_used:
            self.max_native_stack_used = used
            self.max_native_stack_detail = "%s:%s used=%d" % (self.label, name, used)


class BudgetSummary:
    def __init__(self):
        self.max_native_frame_check = 0
        self.max_native_stack_used = 0
        self.max_native_frame_detail = "-"
        self.max_native_stack_detail = "-"

    def observe(self, trace: NativeRootTrace | object):
        frame = int(getattr(trace, "max_native_frame_check", 0))
        stack = int(getattr(trace, "max_native_stack_used", 0))
        if frame > self.max_native_frame_check:
            self.max_native_frame_check = frame
            self.max_native_frame_detail = str(getattr(trace, "max_native_frame_detail", "-"))
        if stack > self.max_native_stack_used:
            self.max_native_stack_used = stack
            self.max_native_stack_detail = str(getattr(trace, "max_native_stack_detail", "-"))


def _code_names(heap, directory):
    return {
        id(code): heap.symbol_name(sym)
        for sym, code in directory.items()
        if heap.symbolp(sym)
    }


def _run_suite_cases(
    suite_path: Path,
    max_steps: int,
    vm_maxargs: int,
    native_initial_base: int,
    summary: BudgetSummary,
) -> int:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    (
        heap,
        _names,
        code_by_name,
        entry_flags_by_name,
        resident_entry_flags,
        _bundle,
        directory,
        cases,
        entry_names,
        _inliner,
    ) = S._compile_suite(suite)
    macro_symbols = S._macro_symbol_objs(heap, entry_flags_by_name, resident_entry_flags)
    max_call_args = S._validate_vm_limit_expectations(suite, heap, code_by_name)
    code_names = _code_names(heap, directory)
    total_steps = 0
    for case, entry in zip(cases, entry_names):
        entry_obj = heap.intern(entry)
        if entry_obj not in directory:
            raise RuntimeBudgetError("%s: missing entry %s" % (case["name"], entry))
        trace = NativeRootTrace("case:%s" % case["name"])
        vm = B.P0VM(
            heap=heap,
            directory=directory,
            macro_symbols=macro_symbols,
            max_steps=case.get("max_steps", max_steps),
            max_call_args=max_call_args,
            trace=trace,
            code_names=code_names,
            native_vm_maxargs=vm_maxargs,
            native_initial_base=native_initial_base,
        )
        result = vm.run(directory[entry_obj], [])
        total_steps += vm.steps
        got = heap.obj_to_text(result)
        if got != case["expect"]:
            raise RuntimeBudgetError(
                "%s: expected %r got %r" % (case["name"], case["expect"], got)
            )
        summary.observe(trace)
    return total_steps


def _run_ide_scenarios(
    suite_path: Path,
    max_steps: int,
    vm_maxargs: int,
    native_initial_base: int,
    summary: BudgetSummary,
) -> int:
    rt = ID.Runtime(
        suite_path,
        max_steps=max_steps,
        native_vm_maxargs=vm_maxargs,
        native_initial_base=native_initial_base,
    )
    collectors = ID._run_scenarios(rt)
    for collector in collectors:
        summary.observe(collector)
    return len(collectors)


def _status(
    gc_roots: int | None,
    summary: BudgetSummary,
    min_frame_headroom: int,
    min_stack_headroom: int,
) -> str:
    problems = []
    if gc_roots is None:
        problems.append("missing-gc-roots")
    else:
        if summary.max_native_frame_check >= gc_roots:
            problems.append("frame-check-too-deep")
        if summary.max_native_stack_used > gc_roots:
            problems.append("rootstack-too-deep")
        frame_headroom = (gc_roots - 1) - summary.max_native_frame_check
        stack_headroom = gc_roots - summary.max_native_stack_used
        if frame_headroom < min_frame_headroom:
            problems.append("frame-headroom-too-small")
        if stack_headroom < min_stack_headroom:
            problems.append("rootstack-headroom-too-small")
    return "ok" if not problems else ",".join(problems)


def _value(value: object) -> str:
    return "unknown" if value is None else str(value)


def _report_lines(info: dict) -> list[str]:
    return [
        "lisp65 mvp vm stdlib runtime budget report",
        "built_at=%s" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit=%s" % BB.git_short(),
        "status=%s" % info["status"],
        "",
        "Inputs:",
        "suite=%s" % info["suite"],
        "include_ide_scenarios=%s" % ("yes" if info["include_ide_scenarios"] else "no"),
        "",
        "Native root budget:",
        "gc_roots=%s" % _value(info["gc_roots"]),
        "vm_maxargs=%d" % info["vm_maxargs"],
        "native_initial_base=%d" % info["native_initial_base"],
        "min_native_frame_headroom=%d" % info["min_native_frame_headroom"],
        "min_native_stack_headroom=%d" % info["min_native_stack_headroom"],
        "frame_check_limit=%s" % _value(info["frame_check_limit"]),
        "max_native_frame_check=%d" % info["max_native_frame_check"],
        "native_frame_headroom=%s" % _value(info["native_frame_headroom"]),
        "max_native_frame_detail=%s" % info["max_native_frame_detail"],
        "rootstack_limit=%s" % _value(info["rootstack_limit"]),
        "max_native_stack_used=%d" % info["max_native_stack_used"],
        "native_stack_headroom=%s" % _value(info["native_stack_headroom"]),
        "max_native_stack_detail=%s" % info["max_native_stack_detail"],
        "",
        "Coverage:",
        "suite_cases=%d" % info["suite_cases"],
        "suite_steps=%d" % info["suite_steps"],
        "ide_scenarios=%d" % info["ide_scenarios"],
    ]


def write_report(path: Path, lines: list[str]) -> None:
    if str(path) == "-":
        print("\n".join(lines))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    ap.add_argument("--out", type=Path, default=Path("-"))
    ap.add_argument("--extra-cflags", default="")
    ap.add_argument("--max-steps", type=int, default=500000)
    ap.add_argument("--include-ide-scenarios", action="store_true")
    ap.add_argument("--native-initial-base", type=int, default=0)
    ap.add_argument("--min-native-frame-headroom", type=int, default=0)
    ap.add_argument("--min-native-stack-headroom", type=int, default=0)
    ap.add_argument("--fail-on-over-budget", action="store_true")
    ns = ap.parse_args(argv)

    defines = BB.d_flags(ns.extra_cflags)
    gc_roots = BB.parse_int(defines["GC_ROOTS"]) if "GC_ROOTS" in defines else None
    vm_maxargs = BB.parse_int(defines["VM_MAXARGS"]) if "VM_MAXARGS" in defines else 12

    summary = BudgetSummary()
    suite = json.loads(ns.suite.read_text(encoding="utf-8"))
    suite_steps = _run_suite_cases(
        ns.suite,
        ns.max_steps,
        vm_maxargs,
        ns.native_initial_base,
        summary,
    )
    ide_scenarios = 0
    if ns.include_ide_scenarios:
        ide_scenarios = _run_ide_scenarios(
            ns.suite,
            ns.max_steps,
            vm_maxargs,
            ns.native_initial_base,
            summary,
        )

    frame_limit = None if gc_roots is None else gc_roots - 1
    info = {
        "status": _status(
            gc_roots,
            summary,
            ns.min_native_frame_headroom,
            ns.min_native_stack_headroom,
        ),
        "suite": str(ns.suite),
        "include_ide_scenarios": ns.include_ide_scenarios,
        "gc_roots": gc_roots,
        "vm_maxargs": vm_maxargs,
        "native_initial_base": ns.native_initial_base,
        "min_native_frame_headroom": ns.min_native_frame_headroom,
        "min_native_stack_headroom": ns.min_native_stack_headroom,
        "frame_check_limit": frame_limit,
        "max_native_frame_check": summary.max_native_frame_check,
        "native_frame_headroom": None if frame_limit is None else frame_limit - summary.max_native_frame_check,
        "max_native_frame_detail": summary.max_native_frame_detail,
        "rootstack_limit": gc_roots,
        "max_native_stack_used": summary.max_native_stack_used,
        "native_stack_headroom": None if gc_roots is None else gc_roots - summary.max_native_stack_used,
        "max_native_stack_detail": summary.max_native_stack_detail,
        "suite_cases": len(suite.get("cases", [])),
        "suite_steps": suite_steps,
        "ide_scenarios": ide_scenarios,
    }
    write_report(ns.out, _report_lines(info))
    destination = "stdout" if str(ns.out) == "-" else str(ns.out)
    print(
        "mvp-vm-stdlib-runtime-budget: status=%s frame=%d/%s stack=%d/%s report=%s"
        % (
            info["status"],
            info["max_native_frame_check"],
            _value(info["frame_check_limit"]),
            info["max_native_stack_used"],
            _value(info["rootstack_limit"]),
            destination,
        )
    )
    if ns.fail_on_over_budget and info["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
