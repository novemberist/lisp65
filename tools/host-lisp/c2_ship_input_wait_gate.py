#!/usr/bin/env python3
"""Permanent source/artifact/allocation gate for v1.3 input and wait freight."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as P  # noqa: E402


CONTRACT = ROOT / "config/c2-ship-input-wait-contract.json"
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
WAIT = ROOT / "lib/stdlib-wait.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-time-base.json"
VM = ROOT / "src/vm.c"
SCREEN = ROOT / "src/screen.c"
SCREEN_SMOKE = ROOT / "scripts/screen-smoke-main.c"
SHELF_LEAF = ROOT / "src/screen_backspace_nonlto.s"
PRODUCT_LINK = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
SHIP_BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
BUILD = ROOT / "build/ship-builder/v13/input-wait-host-first"
BASE_PREFIX = BUILD / "base/stdlib-p0"
CANDIDATE_PREFIX = BUILD / "candidate/stdlib-p0"
OBSERVATIONS = BUILD / "candidate/observations.json"
LIMIT_SUITE = BUILD / "limit-case.json"
LIMIT_OBSERVATIONS = BUILD / "limit-observations.json"
LIMIT_PREFIX = BUILD / "limit/stdlib-p0"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.3-ship-input-wait-host-first-receipt.json"
)
NEW_NAMES = [
    "%read-line-clear-from", "%read-line-render-reverse",
    "%read-line-finish", "%read-line-loop", "read-line",
    "%wait-until", "wait",
]
CASE_NAMES = {
    "read-line-empty", "read-line-echo", "read-line-del-edit",
    "read-line-ignore-control", "read-line-run-stop", "wait-zero",
    "wait-three", "wait-counter-wrap", "wait-exact-maximum-admitted",
    "wait-overflow-rejected",
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def run_suite(suite: Path, prefix: Path, observation: Path) -> dict[str, Any]:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    bootstrap = (
        "import sys;"
        f"sys.path.insert(0,{str(HOST)!r});"
        "sys.setrecursionlimit(4096);"
        "import bytecode_p0_stdlib as m;"
        "raise SystemExit(m.main(sys.argv[1:]))"
    )
    process = subprocess.run([
        sys.executable, "-c", bootstrap, "--check",
        "--emit-artifacts", str(prefix.relative_to(ROOT)),
        "--observation-report", str(observation.relative_to(ROOT)),
        str(suite.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(process.returncode == 0, "input/wait suite red:\n" + process.stdout)
    return load(prefix.with_suffix(".manifest.json"))


def validate(contract: dict[str, Any], read_line: str, wait: str,
             suite: dict[str, Any], vm: str, screen: str,
             product_link: str, ship_builder: str, ship_io: str) -> dict[str, Any]:
    input_contract = contract["input"]
    allocation = contract["allocation"]
    wait_contract = contract["wait"]
    placement = contract["placement"]
    require(
        contract["format"] == "lisp65-c2-ship-input-wait-base-composition-v1"
        and contract["status"] == "owner-commissioned-host-first",
        "input/wait contract identity drift",
    )
    require(
        input_contract["blocking_mode"] == 1
        and input_contract["return_code"] == 13
        and input_contract["delete_codes"] == [20, 127]
        and input_contract["printable_codes"] == [32, 126]
        and input_contract["maximum_characters"] == 250
        and input_contract["screen_viewport"]["native_cursor_dependency"] is False
        and "RUN/STOP" in input_contract["run_stop"],
        "read-line public contract drift",
    )
    require(
        allocation == {
            "nursery_cells": 192,
            "maximum_cells_per_input_key": 4,
            "maximum_collections_on_one_key_for_any_incoming_phase": 1,
            "return_uses_owned_nreverse": True,
            "priced_key_classes": [
                "printable", "delete", "ignored-control", "return", "run-stop"
            ],
        },
        "read-line allocation contract drift",
    )
    for token in (
        "(event (key-event 1))", "(code (cadr event))", "(= code 13)",
        "(= code 20)", "(= code 127)", "(< length 250)",
        "(size (screen-size))", "(row (- (car (cdr size)) 1))",
        "(screen-put-char length row code 1)",
        "(screen-put-char next-length row 32 1)",
        "(%read-line-render-reverse next-codes (- columns 1) row)",
        "(%string-from-codes (nreverse codes))",
    ):
        require(token in read_line, f"Bank-2 read-line seam drift: {token}")
    require(
        "(write-char 20)" not in read_line
        and "(reverse codes)" not in read_line,
        "native DEL or copying RETURN path reintroduced",
    )
    require(
        wait_contract["low_byte"] == "$FF83"
        and wait_contract["high_byte"] == "$FF84"
        and wait_contract["maximum_frames"] == 16383
        and wait_contract["overflow_from_frames"] == 16384
        and "(%time-delta start (%time-read))" in wait
        and "(> frames 16383)" in wait
        and "(%time-error-duration-overflow)" in wait,
        "wait clock/boundary drift",
    )
    require(
        placement["admission_budget_bytes"] == 1024
        and all(placement[key] == 0 for key in (
            "resident_code_bytes", "resident_state_bytes", "new_resident_gc_roots",
            "static_plane_root_records", "runtime_overlay_records", "native_primitives",
        ))
        and placement["require_dependency"] is False,
        "input/wait placement drift",
    )
    require(
        suite["extends"] == "p0-stdlib-time-base.json"
        and suite["sources"] == ["lib/stdlib-read-line.lisp", "lib/stdlib-wait.lisp"]
        and suite["functions"] == NEW_NAMES
        and set(row["name"] for row in suite["cases"]) == CASE_NAMES,
        "input/wait suite drift",
    )
    require(
        "if (++poll_ == 0) lisp_poll();" in vm
        and "case 60: { /* key-event" in vm
        and "lisp_input_event(1u, 0u, &event)" in vm,
        "target RUN/STOP polling seam drift",
    )
    require(
        "(uint8_t)c == 20u || (uint8_t)c == 127u" not in screen
        and "LISP65_SCREEN_DEL_NONLTO" not in screen
        and screen.count("void scr_backspace(void)") == 1
        and "scr_putc((char)20);" not in SCREEN_SMOKE.read_text(encoding="utf-8")
        and "scr_putc((char)127);" not in SCREEN_SMOKE.read_text(encoding="utf-8"),
        "pre-freight C screen driver was not restored",
    )
    require(
        "screen_backspace_nonlto.s" not in product_link
        and "LISP65_SCREEN_DEL_NONLTO" not in product_link
        and "screen_backspace_nonlto.s" not in ship_builder
        and "LISP65_SCREEN_DEL_NONLTO" not in ship_builder
        and "scr_backspace();" not in ship_io,
        "abandoned native DEL path remains linked",
    )
    require(
        ".section\t.text.scr_backspace" in SHELF_LEAF.read_text(encoding="utf-8")
        and "ldz\t#0" in SHELF_LEAF.read_text(encoding="utf-8"),
        "archived non-LTO leaf shelf evidence drift",
    )
    return {
        "status": "passed-bank2-lisp-source-contract",
        "public_functions": ["read-line", "wait"],
        "existing_public_primitives": ["key-event", "screen-size", "screen-put-char"],
        "maximum_characters": 250,
        "maximum_frames": 16383,
        "resident_delta_bytes": 0,
        "native_primitive_delta": 0,
        "native_del_linked": False,
    }


def mutations(contract: dict[str, Any], read_line: str, wait: str,
              suite: dict[str, Any], vm: str, screen: str,
              product_link: str, ship_builder: str, ship_io: str) -> dict[str, str]:
    rows: list[tuple[
        str, dict[str, Any], str, str, dict[str, Any], str, str, str, str, str,
    ]] = []

    def rs(label: str, old: str, new: str) -> None:
        require(old in read_line, f"mutation anchor absent: {label}")
        rows.append((label, contract, read_line.replace(old, new, 1), wait,
                     suite, vm, screen, product_link, ship_builder, ship_io))

    def ws(label: str, old: str, new: str) -> None:
        require(old in wait, f"mutation anchor absent: {label}")
        rows.append((label, contract, read_line, wait.replace(old, new, 1),
                     suite, vm, screen, product_link, ship_builder, ship_io))

    rs("nonblocking-input", "(key-event 1)", "(key-event 0)")
    rs("wrong-return", "(= code 13)", "(= code 10)")
    rs("wrong-delete", "(= code 20)", "(= code 19)")
    rs("wrong-last-row", "(row (- (car (cdr size)) 1))",
       "(row (- (car (cdr size)) 2))")
    rs("wrong-printable-cell", "(screen-put-char length row code 1)",
       "(screen-put-char (+ length 1) row code 1)")
    rs("wrong-delete-blank", "(screen-put-char next-length row 32 1)",
       "(screen-put-char next-length row 33 1)")
    rs("length-251", "(< length 250)", "(< length 251)")
    rs("copying-return", "(%string-from-codes (nreverse codes))",
       "(%string-from-codes (reverse codes))")
    ws("wrong-wait-limit", "(> frames 16383)", "(> frames 16384)")
    ws("wrong-wait-reader", "(%time-read)", "(cons 0 0)")
    changed = copy.deepcopy(contract)
    changed["placement"]["resident_code_bytes"] = 1
    rows.append(("resident-byte", changed, read_line, wait, suite, vm, screen,
                 product_link, ship_builder, ship_io))
    changed = copy.deepcopy(contract)
    changed["allocation"]["maximum_cells_per_input_key"] = 5
    rows.append(("allocation-ceiling-drift", changed, read_line, wait, suite,
                 vm, screen, product_link, ship_builder, ship_io))
    changed_suite = copy.deepcopy(suite)
    changed_suite["cases"] = changed_suite["cases"][:-1]
    rows.append(("case-not-executed", contract, read_line, wait, changed_suite,
                 vm, screen, product_link, ship_builder, ship_io))
    changed_screen = screen.replace(
        "if (c == '\\n' || c == '\\r') { newline(); return; }",
        "if ((uint8_t)c == 20u || (uint8_t)c == 127u) { scr_backspace(); return; }\n"
        "    if (c == '\\n' || c == '\\r') { newline(); return; }",
        1,
    )
    rows.append(("native-del-reintroduced", contract, read_line, wait, suite,
                 vm, changed_screen, product_link, ship_builder, ship_io))
    require(len(rows) == 14, "DEL semantic mutation family count drift")
    rejected: dict[str, str] = {}
    for label, c, r, w, s, v, sc, product, ship, io in rows:
        try:
            validate(c, r, w, s, v, sc, product, ship, io)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"input/wait mutation survived: {label}")
    return rejected


class AllocationVM(B.P0VM):
    """Attribute heap cells between successive key-event boundaries."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.key_rows: list[dict[str, int]] = []
        self._key_start: int | None = None
        self._key_code: int | None = None

    def _close_key(self) -> None:
        if self._key_start is not None and self._key_code is not None:
            self.key_rows.append({
                "code": self._key_code,
                "cells": len(self.heap.cells) - self._key_start,
            })
        self._key_start = None
        self._key_code = None

    def _callprim(self, prim_id: int, argc: int, stack: list[int], pc: int | None = None,
                  native_base: int = 0, frame_slots: int = 0) -> int:
        if prim_id == 60:
            self._close_key()
            self._key_start = len(self.heap.cells)
            self._key_code = self.key_events[0][0] if self.key_events else -1
        if prim_id == 29:
            # The generic P0 heap represents strings as copied character
            # lists.  The admitted product profile uses LISP65_STRING_ARENA:
            # str_from_charlist consumes the bytes into the arena and allocates
            # one T_STR descriptor.  Model that target allocation shape while
            # retaining the owned list as P0's readable backing value.
            self._check_argc(argc, "CALLPRIM")
            args = self._pop_args(argc, stack)
            self._trace_call(
                "CALLPRIM", B.PRIM_IDS[prim_id], argc, pc=pc, resolved=True
            )
            if argc != 1:
                raise B.VMError("ArityError", "%string-from-codes expects one list")
            current = args[0]
            while self.heap.consp(current):
                value = self.heap.car(current)
                if not B.is_fix(value) or not 0 <= B.fixval(value) <= 255:
                    raise B.VMError(
                        "TypeError", "%string-from-codes expects byte fixnums"
                    )
                current = self.heap.cdr(current)
            if current != B.NIL:
                raise B.VMError(
                    "TypeError", "%string-from-codes expects a proper list"
                )
            return self.heap.alloc(B.T_STR, args[0], B.NIL)
        return super()._callprim(
            prim_id, argc, stack, pc=pc, native_base=native_base,
            frame_slots=frame_slots,
        )

    def finish_keys(self) -> None:
        self._close_key()


def allocation_gate(suite_path: Path) -> dict[str, Any]:
    suite = P._read_suite(str(suite_path))
    (
        heap, _names, _code_by_name, _entry_flags, resident_flags,
        _bundle, directory, cases, entry_names, _inliner,
    ) = P._compile_suite(suite)
    macro_symbols = P._macro_symbol_objs(heap, {}, resident_flags)
    abi_profile, abi_ledger = P._suite_abi(suite)
    priced_names = {
        "read-line-empty", "read-line-echo", "read-line-del-edit",
        "read-line-ignore-control", "read-line-run-stop",
        "read-line-exact-250",
    }
    rows = []
    for case, entry in zip(cases, entry_names):
        if case["name"] not in priced_names:
            continue
        case_heap = heap.clone()
        # vm_init owns these four event tags before user bytecode can run.
        for tag in ("key", "shift", "control", "meta"):
            case_heap.intern(tag)
        vm = AllocationVM(
            heap=case_heap, directory=directory, macro_symbols=macro_symbols,
            max_steps=case.get("max_steps", 300000),
            max_call_args=suite.get("max_call_args"),
            key_events=case.get("key_events"), abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        expected_error = case.get("expect_vm_error")
        try:
            vm.run(directory[case_heap.intern(entry)], [])
        except B.VMError as error:
            require(error.status == expected_error,
                    f"allocation lane {case['name']} error drift: {error.status}")
        else:
            require(not expected_error, f"allocation lane {case['name']} missed error")
        vm.finish_keys()
        rows.append({"case": case["name"], "keys": vm.key_rows})
    require({row["case"] for row in rows} == priced_names,
            "allocation key-class execution witness drift")
    all_keys = [key for row in rows for key in row["keys"]]
    ceiling = int(load(CONTRACT)["allocation"]["maximum_cells_per_input_key"])
    maximum = max(key["cells"] for key in all_keys)
    require(maximum <= ceiling, f"per-key allocation {maximum} exceeds {ceiling}")
    nursery = int(load(CONTRACT)["allocation"]["nursery_cells"])
    worst_collections = max((cells + nursery - 1) // nursery for cells in (
        key["cells"] for key in all_keys
    ))
    require(worst_collections <= 1, "one key can trigger a multi-GC burst")
    return {
        "status": "passed-per-key-cell-ceiling",
        "cases": rows,
        "keys_executed": len(all_keys),
        "maximum_cells_per_key": maximum,
        "contract_ceiling": ceiling,
        "nursery_cells": nursery,
        "maximum_collections_on_one_key_for_any_incoming_phase": 1,
    }


def artifact_gate() -> dict[str, Any]:
    base_observation = BUILD / "base/observations.json"
    old = run_suite(BASE_SUITE, BASE_PREFIX, base_observation)
    new = run_suite(SUITE, CANDIDATE_PREFIX, OBSERVATIONS)
    delta = {
        "bank2_code_bytes": int(new["code_bytes"]) - int(old["code_bytes"]),
        "directory_bytes": int(new["directory_bytes"]) - int(old["directory_bytes"]),
        "objects": int(new["objects"]) - int(old["objects"]),
        "resolution_words": (
            sum(int(row["lit_count"]) for row in new["entries"])
            - sum(int(row["lit_count"]) for row in old["entries"])
        ),
        "resident_bytes": 0,
        "native_bytes": 0,
    }
    require(
        0 < delta["bank2_code_bytes"] <= 1024
        and delta["objects"] == len(NEW_NAMES)
        and [row["name"] for row in new["entries"][-len(NEW_NAMES):]] == NEW_NAMES,
        "input/wait artifact delta or tail drift",
    )
    observations = load(OBSERVATIONS)["suites"][0]["observations"]
    observed = {row["name"]: row for row in observations if row["name"] in CASE_NAMES}
    require(set(observed) == CASE_NAMES, "input/wait cases were not all executed")
    require(
        observed["read-line-echo"]["io_witness"]["key_event"] == 4
        and observed["read-line-echo"]["io_witness"]["screen_put_char"] >= 83
        and observed["read-line-del-edit"]["io_witness"]["screen_rows"]["24"].startswith("ac")
        and observed["wait-three"]["io_witness"]["memory_read_sequence"] >= 5,
        "input/wait positive execution witness drift",
    )
    long_text = "a" * 250
    long_case = {
        "extends": str(SUITE.relative_to(ROOT)),
        "cases": [{
            "name": "read-line-exact-250",
            "expr": "(read-line)",
            "expect": json.dumps(long_text),
            "key_events": [97] * 250 + [98, 13],
            "expect_key_events_remaining": 0,
            "expect_output_codes": [10],
            "expect_screen_rows": {"24": "a" * 80},
            "expect_io_min": {"key_event": 252, "screen_put_char": 80},
            "max_steps": 400000,
        }],
    }
    write(LIMIT_SUITE, long_case)
    run_suite(LIMIT_SUITE, LIMIT_PREFIX, LIMIT_OBSERVATIONS)
    limit_rows = load(LIMIT_OBSERVATIONS)["suites"][0]["observations"]
    require(any(row["name"] == "read-line-exact-250" for row in limit_rows),
            "250-character execution witness absent")
    allocation = allocation_gate(LIMIT_SUITE)
    return {
        "baseline_manifest": bind(BASE_PREFIX.with_suffix(".manifest.json")),
        "candidate_manifest": bind(CANDIDATE_PREFIX.with_suffix(".manifest.json")),
        "delta": delta,
        "cases_per_lane": len(CASE_NAMES) + 1,
        "execution_lanes": 2,
        "observations": bind(OBSERVATIONS),
        "limit_observations": bind(LIMIT_OBSERVATIONS),
        "allocation": allocation,
    }


def main() -> int:
    try:
        contract = load(CONTRACT)
        read_line = READ_LINE.read_text(encoding="utf-8")
        wait = WAIT.read_text(encoding="utf-8")
        suite = load(SUITE)
        vm = VM.read_text(encoding="utf-8")
        screen = SCREEN.read_text(encoding="utf-8")
        product_link = PRODUCT_LINK.read_text(encoding="utf-8")
        ship_builder = SHIP_BUILDER.read_text(encoding="utf-8")
        ship_io = SHIP_IO.read_text(encoding="utf-8")
        source = validate(
            contract, read_line, wait, suite, vm, screen,
            product_link, ship_builder, ship_io,
        )
        rejected = mutations(
            contract, read_line, wait, suite, vm, screen,
            product_link, ship_builder, ship_io,
        )
        artifacts = artifact_gate()
        historical_first_red = ROOT / (
            "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
            "c2.3-v1.3-screen-nonlto-wplto-first-red.json"
        )
        historical_binding: dict[str, Any]
        if historical_first_red.is_file():
            historical_binding = bind(historical_first_red)
        else:
            historical_binding = {
                "status": "private-history-absent-not-a-build-input",
                "private_evidence_inputs": 0,
            }
        value = {
            "format": "lisp65-c2.2-v1.3-ship-input-wait-host-first-v2",
            "recorded_on": "2026-08-01",
            "status": "passed-bank2-lisp-source-artifact-allocation-and-execution",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "source_contract": source,
            "mutations_rejected": rejected,
            "artifacts": artifacts,
            "shelf_evidence": {
                "status": "retained-unlinked",
                "non_lto_leaf": bind(SHELF_LEAF),
                "historical_first_red": historical_binding,
            },
            "authority": {
                "contract": bind(CONTRACT), "read_line": bind(READ_LINE),
                "wait": bind(WAIT), "suite": bind(SUITE), "base_suite": bind(BASE_SUITE),
                "p0_vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
                "stdlib_runner": bind(ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"),
                "target_vm": bind(VM), "screen_driver": bind(SCREEN),
                "screen_smoke": bind(SCREEN_SMOKE),
                "product_link_driver": bind(PRODUCT_LINK),
                "ship_builder": bind(SHIP_BUILDER), "ship_io": bind(SHIP_IO),
                "gate": bind(Path(__file__)),
            },
            "next_gate": "one product-shaped card; no C/geometry experiment remains",
        }
        write(RECEIPT, value)
        delta = artifacts["delta"]
        print(
            "c2-ship-input-wait-gate: PASS "
            f"cases={artifacts['cases_per_lane']}x{artifacts['execution_lanes']} "
            f"mutations={len(rejected)} keys={artifacts['allocation']['keys_executed']} "
            f"max-cells/key={artifacts['allocation']['maximum_cells_per_key']} "
            f"bank2=+{delta['bank2_code_bytes']} resident=+0 native=+0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError, P.StdlibCheckError) as error:
        print(f"c2-ship-input-wait-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
