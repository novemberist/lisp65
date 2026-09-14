#!/usr/bin/env python3
"""Gate v2 string-codec latency and monotone P0 heap pressure."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import sys
import tempfile
import types
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_stdlib as S  # noqa: E402
import bytecode_p0 as B  # noqa: E402
import evidence_era as ERA  # noqa: E402
import v2_workbench_codemod as C  # noqa: E402
from ide_bytecode_dynamic_report import Runtime, TraceCollector  # noqa: E402


HISTORICAL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "string-codec-workload-receipt.json"
)
DEFAULT_OUTPUT = HISTORICAL_RECEIPT.with_name('string-codec-workload-v230-receipt.json')
V2_IDE_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
FORMAT_SUITE = ROOT / "tests/bytecode/libs/p0-format-lib.json"
FORMAT = "lisp65-v2-string-codec-workload-receipt-v1"
STATUS_BASELINE = "ded9afd19ba0c5ca31445cdb9556e0a68f3a7a1a"
SHIPPED_DOMAIN = "config/c2-v220-public-plane/sources/024-domain-tier1-sealed.lisp"
SHIPPED_DOMAIN_SHA = "f60046dd70282e640e6ff3db4c79e80f2ef84575d17279752e87c9d8a90f2b35"

MINI8 = """(progn
 (set-symbol-value (quote %ide-prefix) nil)
 (let* ((s0 (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))
        (s1 (ide-step s0 (list (quote key) 24 nil)))
        (s2 (ide-step s1 (list (quote key) 6 nil)))
        (s3 (ide-render (ide-step s2 (list (quote key) 100 nil))))
        (s4 (ide-render (ide-step s3 (list (quote key) 101 nil))))
        (s5 (ide-render (ide-step s4 (list (quote key) 109 nil))))
        (s6 (ide-render (ide-step s5 (list (quote key) 111 nil))))
        (s7 (ide-render (ide-step s6 (list (quote key) 49 nil))))
        (s8 (ide-render (ide-step s7 (list (quote key) 50 nil))))
        (s9 (ide-render (ide-step s8 (list (quote key) 51 nil))))
        (s10 (ide-render (ide-step s9 (list (quote key) 52 nil)))))
   (list (ide-state-message s10)
         (%ide-mini-status-line))))"""

CLIP160 = """(car (ide-state-render-lines
 (ide-render
  (ide-make-state
   (ide-set-point
    (ide-make-buffer \"scratch\" (list \"%s\"))
    0 120)))))""" % ("x" * 160)

STATUS = """(let ((state (ide-make-state (ide-make-buffer \"scratch\" (list \"a\")))))
 (progn
  (rplaca (nthcdr 7 state) \"B\")
  (ide-status-line (%ide-state-with-message state \"compiled ok\") 80)))"""

WORKLOADS = (
    {
        "id": "mini8", "suite": V2_IDE_SUITE, "profile_role": "v2-candidate",
        "expr": MINI8, "expect": '(1005 "Find file: demo1234")',
        "max_ops": 95000, "max_heap_churn": 3200,
    },
    {
        "id": "clip160", "suite": V2_IDE_SUITE, "profile_role": "v2-candidate",
        "expr": CLIP160, "expect": '"%s"' % ("x" * 80),
        "max_ops": 50000, "max_heap_churn": 1100,
    },
    {
        "id": "status", "suite": V2_IDE_SUITE, "profile_role": "v2-candidate",
        "expr": STATUS, "expect": '"-- scratch compiled ok L1 -- B"',
        # 06e577b9: executed v2.2.0 product-domain baseline, no margin.
        # Historical permissive Host wall: 3000 ops / 384 cells (2574 / 272).
        "max_ops": 3114, "max_heap_churn": 272,
    },
    {
        "id": "format", "suite": FORMAT_SUITE,
        "profile_role": "dialect-v1-format-baseline-only",
        "expr": '(format nil "name=~A n=~D" "bob" 42)',
        "expect": '"name=bob n=42"', "max_ops": 700, "max_heap_churn": 72,
    },
)


class WorkloadError(RuntimeError):
    pass


def status_budget(ops, cells, reference):
    if ops > reference['ops'] or cells > reference['heap_churn']:
        raise WorkloadError('status exceeds executed product-domain v2.2.0 baseline')


def product_domain(runtime):
    """Execute the formerly permissive nthcdr boundary in the consumed VM."""
    pair = runtime.heap.cons(runtime.obj(1), runtime.heap.intern('t'))
    try:
        runtime.run_named('nthcdr', [runtime.obj(1), pair])
    except B.VMError as error:
        if error.status == 'TypeError':
            return
        raise WorkloadError('unexpected product-domain error: '+str(error)) from error
    raise WorkloadError('permissive list domain is not the shipped product domain')


def status_reference(temp):
    """Replay 2.2.0 sources, selecting its shipped, not old Host, domain."""
    if _sha(ROOT / SHIPPED_DOMAIN) != SHIPPED_DOMAIN_SHA:
        raise WorkloadError('shipped v2.2.0 domain provenance drift')
    original = C.generate
    namespace = dict(original.__globals__)
    namespace['ERA'] = types.SimpleNamespace(host_source_commit=lambda: None,
                                             era_blob=ERA.era_blob)
    C.generate = types.FunctionType(original.__code__, namespace, original.__name__,
                                    original.__defaults__, original.__closure__)
    try:
        with ERA.generated_workbench_world(STATUS_BASELINE) as reads:
            C.generate = original
            resolved = S._read_suite(str(V2_IDE_SUITE))
            spec = dict(next(s for s in WORKLOADS if s['id'] == 'status'))
            spec['suite'] = Path(resolved['_suite_path'])
            result = _measure(spec, temp)
            result['source_reads'] = reads.copy()
    finally:
        C.generate = original
    if (result['ops'], result['heap_churn']) != (3114, 272):
        raise WorkloadError('sealed v2.2.0 status baseline drift')
    return dict(commit=STATUS_BASELINE, domain=SHIPPED_DOMAIN,
                domain_sha256=SHIPPED_DOMAIN_SHA, measurement=result,
                historical_host_wall=dict(ops=3000, heap_churn=384,
                                          domain='permissive; not a live limit'))


def mini_screen(columns, cells):
    from ide_minibuffer_screen_check import PREFIX, row_failures, row_selftest
    row_selftest()
    row=cells[-columns:]
    text=PREFIX+'demo1234'
    low7=''.join(chr(c & 127) for c in row)
    cursor=len(text)
    if row_failures(row,text,columns):
        raise WorkloadError(f'mini8 screen drift: observed={low7!r}; expected={text!r} then inverse cursor and cleared tail')
    return dict(cells=row,cursor_column=cursor)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _resolve(path: str, base: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    local = base / candidate
    return local if local.exists() else ROOT / candidate


def _suite_bindings(path: Path, seen: set[Path] | None = None) -> list[dict[str, str]]:
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    if not path.is_file() or not path.is_relative_to(ROOT):
        raise WorkloadError(f"suite/input is missing or outside the repository: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    result = [{"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)}]
    for source in raw.get("sources", []):
        source_path = _resolve(source, path.parent).resolve()
        if not source_path.is_file() or not source_path.is_relative_to(ROOT):
            raise WorkloadError(f"suite source is missing or unsafe: {source_path}")
        if source_path not in seen:
            seen.add(source_path)
            result.append({
                "path": source_path.relative_to(ROOT).as_posix(),
                "sha256": _sha(source_path),
            })
    residents = list(raw.get("resident_suites", []))
    if raw.get("resident_suite"):
        residents.append(raw["resident_suite"])
    for resident in residents:
        result.extend(_suite_bindings(_resolve(resident, path.parent), seen))
    return result


def _absolute_suite(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    value = deepcopy(raw)
    value["sources"] = [str(_resolve(item, path.parent).resolve()) for item in value["sources"]]
    if "resident_suite" in value:
        value["resident_suite"] = str(
            _resolve(value["resident_suite"], path.parent).resolve()
        )
    if "resident_suites" in value:
        value["resident_suites"] = [
            str(_resolve(item, path.parent).resolve())
            for item in value["resident_suites"]
        ]
    return value


def _measure(spec: dict[str, Any], temp: Path) -> dict[str, Any]:
    suite_path = spec["suite"]
    if not suite_path.is_file():
        raise WorkloadError(f"required generated suite is missing: {suite_path}")
    raw = json.loads(suite_path.read_text(encoding="utf-8"))
    suite = _absolute_suite(raw, suite_path)
    suite["cases"] = [{
        "name": spec["id"], "expr": spec["expr"], "expect": spec["expect"],
        "max_steps": 2_000_000,
    }]
    temporary_suite = temp / f"{spec['id']}.json"
    temporary_suite.write_text(json.dumps(suite), encoding="utf-8")
    runtime = Runtime(temporary_suite, 2_000_000)
    entry = S._entry_name(spec["id"])
    trace = TraceCollector(spec["id"], runtime.heap)
    cells_before = len(runtime.heap.cells) - 1
    result = runtime.run_named(entry, trace=trace)
    observed = runtime.heap.obj_to_text(result)
    churn = (len(runtime.heap.cells) - 1) - cells_before
    if observed != spec["expect"]:
        raise WorkloadError(
            f"{spec['id']} result drift: observed={observed!r} expected={spec['expect']!r}"
        )
    if trace.steps > spec["max_ops"] or churn > spec["max_heap_churn"]:
        raise WorkloadError(
            f"{spec['id']} budget exceeded: ops={trace.steps}/{spec['max_ops']} "
            f"heap_churn={churn}/{spec['max_heap_churn']}"
        )
    screen={}
    if spec['id']=='mini8':
        screen['screen']=mini_screen(runtime.last_vm.screen_columns,runtime.last_vm.screen_cells)
    if spec.get('capture_screen'):
        screen['screen_columns']=runtime.last_vm.screen_columns
        screen['screen_cells']=list(runtime.last_vm.screen_cells)
    if spec['id'] == 'status':
        product_domain(runtime)
    return {
        "id": spec["id"], "profile_role": spec["profile_role"],
        "form_sha256": hashlib.sha256(spec["expr"].encode("utf-8")).hexdigest(),
        "result": observed, "ops": trace.steps, "max_ops": spec["max_ops"],
        "heap_churn": churn, "max_heap_churn": spec["max_heap_churn"], **screen,
    }


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="v2-string-codec-workloads-") as raw:
        temp = Path(raw)
        workloads = [_measure(spec, temp) for spec in WORKLOADS]
        reference = status_reference(temp)
        current = next(w for w in workloads if w['id'] == 'status')
        status_budget(current['ops'], current['heap_churn'], reference['measurement'])
    bindings: list[dict[str, str]] = []
    seen: set[Path] = set()
    for spec in WORKLOADS:
        bindings.extend(_suite_bindings(spec["suite"], seen))
    bindings.sort(key=lambda item: item["path"])
    return {
        "format": FORMAT,
        "status": "passed",
        "scope": {
            "v2_candidate": ["mini8", "clip160", "status"],
            "format": "dialect-v1-baseline-only-until-format-migration",
            "hardware_latency_claim": "none",
            "allocation_metric": "monotone-p0-runtime-cell-churn",
        },
        "inputs": bindings,
        "workloads": workloads,
        "status_reference": reference,
    }


def check_receipt(receipt: dict[str, Any]) -> None:
    fresh = measure()
    compare_receipt(receipt, fresh)


def compare_receipt(receipt: dict[str, Any], fresh: dict[str, Any]) -> None:
    if receipt != fresh:
        raise WorkloadError("string codec workload receipt is stale or has drifted")


def selftest() -> None:
    receipt = measure()
    try:
        compare_receipt(json.loads(HISTORICAL_RECEIPT.read_bytes()), receipt)
    except WorkloadError:
        pass
    else:
        raise WorkloadError('historical-receipt substitution mutation survived')
    reference = receipt['status_reference']['measurement']
    for ops, cells in ((reference['ops'] + 1, reference['heap_churn']),
                       (reference['ops'], reference['heap_churn'] + 1)):
        try:
            status_budget(ops, cells, reference)
        except WorkloadError:
            pass
        else:
            raise WorkloadError('status +1 regression mutation survived')
    # Execute the actual historical permissive model: the domain guard, not
    # a provenance label or the cheaper operation count, must reject it.
    with ERA.generated_workbench_world(STATUS_BASELINE):
        runtime = Runtime(V2_IDE_SUITE, 2_000_000)
        try:
            product_domain(runtime)
        except WorkloadError as error:
            if 'permissive list domain' not in str(error):
                raise
        else:
            raise WorkloadError('permissive-model mutation survived')
    mutated = deepcopy(receipt)
    mutated["workloads"][0]["ops"] += 1
    if mutated == receipt:
        raise WorkloadError("receipt mutation was not observable")
    if [item["id"] for item in receipt["workloads"]] != [
        "mini8", "clip160", "status", "format"
    ]:
        raise WorkloadError("workload coverage drift")
    row=receipt['workloads'][0]['screen']['cells']
    cursor=receipt['workloads'][0]['screen']['cursor_column']
    for name,index,value in [('missing-input',cursor-1,32),('missing-inverse',cursor,95),
                             ('stray-inverse',0,row[0]|128)]:
        wrong=list(row);wrong[index]=value
        try:mini_screen(len(wrong),wrong)
        except WorkloadError:pass
        else:raise WorkloadError('screen mutation survived: '+name)
    old=dict(WORKLOADS[0]);old['expr']=MINI8.replace('(%ide-mini-status-line)',
        '(car (last (ide-state-render-lines s10)))')
    with tempfile.TemporaryDirectory() as tmp:
        try:_measure(old,Path(tmp))
        except WorkloadError:pass
        else:raise WorkloadError('empty-placeholder mutation survived')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    record = sub.add_parser("record")
    record.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check = sub.add_parser("check")
    check.add_argument("--receipt", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v2-string-codec-workloads: SELFTEST PASS cases=4")
        elif args.command == "record":
            receipt = measure()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(_canonical(receipt))
            print(f"v2-string-codec-workloads: WROTE {args.output}")
        else:
            check_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
            print("v2-string-codec-workloads: PASS cases=4")
        return 0
    except (WorkloadError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"v2-string-codec-workloads: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
