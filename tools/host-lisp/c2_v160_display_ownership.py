#!/usr/bin/env python3
"""Composed-framebuffer and pricing gate for the v1.6 Comfort display owner."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

sys.setrecursionlimit(max(sys.getrecursionlimit(), 4096))

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as P  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-display-ownership-contract.json"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
COMFORT = ROOT / "lib/repl-comfort.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
RESIDENT = ROOT / "tests/bytecode/libs/p0-repl-comfort-resident.json"
BUILD = ROOT / "build/c2.3/v1.6-display-ownership"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-display-ownership-receipt.json"
)

EDITOR_FUNCTIONS = (
    "%rl-render", "%rl-cut", "%rl-move", "%rl-put", "%rl-dispatch",
    "%read-line-loop", "read-line", "%rl-screen-tail",
)
COMFORT_FUNCTIONS = ("%repl-read", "%repl-step", "repl")


class GateError(RuntimeError):
    pass


class AtReturn(Exception):
    pass


class AfterResult(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def source_gate(contract: dict[str, Any], editor: str, comfort: str) -> dict[str, Any]:
    require(
        contract == {
            "format": "lisp65-c2-v160-display-ownership-v1",
            "recorded_on": "2026-08-21",
            "authorization_commit": "e5a3b8a7",
            "status": "owner-authorized-one-card",
            "prompt": "l65> ",
            "prompt_columns": 5,
            "line_limit": 250,
            "ownership": {
                "active": "editor owns the complete final row including prompt cells",
                "handoff": "editor clears its complete row before sequential result output",
                "prompt_is_input": False,
                "composed_surface_is_claim": True,
            },
            "placement": {
                "arena": "Bank-2 disk libraries", "new_names": 1,
                "reclaimed_private_entries": ["%fasl-fs"],
                "bias_adjusted_free": {
                    "symbol_slots": 33, "namepool_bytes": 594,
                },
                "resident_bytes": 0, "far_service_bytes": 0,
                "maximum_code_object_bytes": 255,
            },
            "walls": {
                "history_lines": 10, "indent_spaces_per_depth": 2,
                "ordinary_read_line_unchanged": True,
                "maximum_cells_per_key": 4,
                "responsiveness_path": "line-boundary-only",
                "device_contacts": 0,
            },
        },
        "display-ownership contract drift",
    )
    for token in (
        "(if (= row -1)", "(defun %rl-screen-tail (codes index column stop cursor row)",
        "(prompted (< row -2))",
        "(and prompted (= cursor -1))",
        "(%rl-render nil 0 0 (car (screen-size)) -2",
        "(origin (if prompted 5 0))",
        "(write-char 19)",
        "(dotimes (line stop nil) (write-char 17))",
    ):
        require(token in editor, f"editor ownership token absent: {token}")
    for token in (
        '(screen-write-string 0 row "l65> ")',
        '(%rl-screen-tail nil 0 0 (- row 1) 0 -2)',
        "(if top (- columns 5) columns)",
        "(if top (- 0 (+ row 2)) row)",
        "(%repl-read indent history 0", "(%repl-read -1 history nil 0 0)",
    ):
        require(token in comfort, f"Comfort ownership token absent: {token}")
    require(
        '(write-line "l65>")' not in comfort
        and '(string-append "l65> " indent)' not in comfort,
        "prompt escaped the editor-owned rendering surface",
    )
    return {
        "prompt": contract["prompt"], "prompt_columns": 5,
        "new_names": 1, "reclaimed_names": 1,
        "bias_adjusted_free": {"symbol_slots": 33, "namepool_bytes": 594},
        "resident_bytes": 0, "far_service_bytes": 0,
    }


def mutated_suite(label: str, *, editor: str | None = None,
                  comfort: str | None = None) -> dict[str, Any]:
    root = BUILD / "mutations" / label
    root.mkdir(parents=True, exist_ok=True)
    resident_ref: str = str(RESIDENT)
    if editor is not None:
        editor_path = root / "stdlib-read-line.lisp"
        editor_path.write_text(editor, encoding="utf-8")
        resident_path = root / "resident.json"
        write_json(resident_path, {
            "extends": str(RESIDENT),
            "remove_sources": ["lib/stdlib-read-line.lisp"],
            "sources": [str(editor_path)],
            "require_all_defuns": False,
        })
        resident_ref = str(resident_path)
    suite_path = root / "suite.json"
    value: dict[str, Any] = {
        "extends": str(SUITE), "resident_suites": [resident_ref]
    }
    if comfort is not None:
        comfort_path = root / "repl-comfort.lisp"
        comfort_path.write_text(comfort, encoding="utf-8")
        value["remove_sources"] = ["lib/repl-comfort.lisp"]
        value["sources"] = [str(comfort_path)]
    write_json(suite_path, value)
    return P._read_suite(str(suite_path))


class FrameVM(B.P0VM):
    """Put direct-cell and sequential writes on one 80x25 surface."""

    def __init__(self, *args: Any, stop_at_return: bool = False, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.cursor_row = self.screen_rows - 1
        self.cursor_column = 0
        self.newlines = 0
        self.stop_at_return = stop_at_return
        self.active_row: str | None = None
        self.after_result: list[str] | None = None
        self.result_started = False

    def row(self, index: int) -> str:
        start = index * self.screen_columns
        return bytes(self.screen_cells[start:start + self.screen_columns]).decode("latin-1")

    def sequential(self, code: int) -> None:
        if code == 19:  # PETSCII HOME
            self.cursor_row = 0
            self.cursor_column = 0
            return
        if code == 17:  # PETSCII cursor down
            if self.cursor_row + 1 < self.screen_rows:
                self.cursor_row += 1
            return
        if code in (10, 13):
            self.cursor_column = 0
            if self.cursor_row + 1 >= self.screen_rows:
                width = self.screen_columns
                self.screen_cells[:-width] = self.screen_cells[width:]
                self.screen_cells[-width:] = [32] * width
            else:
                self.cursor_row += 1
            self.newlines += 1
            return
        self.screen_cells[
            self.cursor_row * self.screen_columns + self.cursor_column
        ] = code & 0xFF
        self.cursor_column += 1
        if self.cursor_column >= self.screen_columns:
            self.sequential(10)

    def _callprim(self, prim_id: int, argc: int, stack: list[int],
                  pc: int | None = None, native_base: int = 0,
                  frame_slots: int = 0) -> int:
        args = stack[-argc:] if argc else []
        if (prim_id == 11 and len(args) >= 3 and self.active_row is None
                and B.fixval(args[0]) == 0
                and B.fixval(args[1]) == self.screen_rows - 1
                and B.fixval(args[2]) == 32):
            # The first cell of the editor's full-row clear is the exact
            # ownership handoff.  Observe the composed row before mutating it.
            self.active_row = self.row(self.screen_rows - 1)
            if self.stop_at_return:
                raise AtReturn
        if prim_id == 41 and self.active_row is None:
            # A no-handoff mutant reaches result output without the clear.
            self.active_row = self.row(self.screen_rows - 1)
        if prim_id == 41 and args:  # prin1: host P0 otherwise records no pixels
            self.result_started = True
            for code in self.heap.obj_to_text(args[0]).encode("latin-1"):
                self.sequential(code)
        if prim_id == 45 and args:  # write-char
            self.sequential(B.fixval(args[0]))
        result = super()._callprim(
            prim_id, argc, stack, pc=pc, native_base=native_base,
            frame_slots=frame_slots,
        )
        if (prim_id == 45 and args and B.fixval(args[0]) in (10, 13)
                and self.result_started):
            self.after_result = [
                self.row(self.screen_rows - 2),
                self.row(self.screen_rows - 1),
            ]
            raise AfterResult
        return result


EDIT_EVENTS = [*b"(list 1 3)", 13]


def run_world(suite: dict[str, Any], events: list[int], *, at_return: bool) -> FrameVM:
    suite = dict(suite)
    suite["cases"] = [{
        "name": "display-owner-composed-surface", "expr": "(repl)",
        "expect": "nil", "key_events": events, "max_steps": 4000000,
    }]
    (heap, _names, _code, entry_flags, resident_flags, _bundle, directory,
     _cases, entries, _inliner) = P._compile_suite(suite)
    macros = P._macro_symbol_objs(heap, entry_flags, resident_flags)
    abi_profile, abi_ledger = P._suite_abi(suite)
    vm = FrameVM(
        heap=heap.clone(), directory=directory, macro_symbols=macros,
        max_steps=4000000, max_call_args=suite.get("max_call_args"),
        key_events=events, private_key_event_modes=True,
        abi_profile=abi_profile, abi_ledger=abi_ledger,
        stop_at_return=at_return,
    )
    try:
        vm.run(directory[heap.intern(entries[0])], [])
    except (AtReturn if at_return else AfterResult):
        pass
    else:
        raise GateError("composed framebuffer witness did not reach bound stop")
    return vm


def composed_gate() -> dict[str, Any]:
    candidate = mutated_suite("candidate")
    vm = run_world(candidate, EDIT_EVENTS, at_return=False)
    require(vm.active_row == "l65> (list 1 3)".ljust(80),
            f"prompt/editor composed row drift: {vm.active_row!r}")
    require(vm.after_result == ["(1 3)".ljust(80), " ".ljust(80)],
            f"result handoff retained residue: {vm.after_result!r}")

    boundary = run_world(candidate, [ord("a"), 1, 157, 20, 13], at_return=True)
    require(boundary.active_row == "l65> a".ljust(80),
            "prompt cells became editable at the left boundary")

    maximum = run_world(candidate, [ord("a")] * 250 + [13], at_return=True)
    require(maximum.active_row == ("l65> " + "a" * 74 + " "),
            "250-character prompted viewport/cursor drift")

    left_text = "abcde" + "a" * 72
    left = run_world(candidate, list(left_text.encode()) + [157] * 75 + [13],
                     at_return=True)
    require(left.active_row.startswith("l65> cde"),
            "prompted one-column left-scroll edge drift")
    return {
        "active_row": vm.active_row.rstrip(),
        "result_row": vm.after_result[0].rstrip(),
        "result_tail_blank": vm.after_result[0][5:] == " " * 75,
        "prompt_boundary": boundary.active_row.rstrip(),
        "maximum_characters": 250,
        "visible_text_columns": 74,
        "left_scroll_prefix": left.active_row[:9],
    }


def executable_mutations() -> dict[str, str]:
    editor = EDITOR.read_text(encoding="utf-8")
    comfort = COMFORT.read_text(encoding="utf-8")
    rejected: dict[str, str] = {}

    no_handoff = editor.replace(
        "(and prompted (= cursor -1))", "(and prompted (= cursor -3))", 1)
    vm = run_world(mutated_suite("no-handoff", editor=no_handoff), EDIT_EVENTS,
                   at_return=False)
    require(vm.after_result is not None
            and vm.after_result[0].startswith("(1 3)(list 1 3)"),
            "historical residue mutation did not recreate the device first red")
    rejected["handoff-does-not-clear"] = vm.after_result[0].rstrip()

    separate = comfort.replace(
        '(screen-write-string 0 row "l65> ")', '(write-line "l65>")', 1)
    vm = run_world(mutated_suite("separate-prompt", comfort=separate),
                   EDIT_EVENTS, at_return=True)
    require(vm.active_row is not None and not vm.active_row.startswith("l65> "),
            "separate-prompt mutation did not separate prompt and cursor")
    rejected["prompt-uses-sequential-owner"] = vm.active_row.rstrip()

    wide = comfort.replace("(if top (- columns 5) columns)", "columns", 1)
    vm = run_world(mutated_suite("viewport-ignores-prompt", comfort=wide),
                   [ord("a")] * 250 + [13], at_return=True)
    require(vm.active_row != ("l65> " + "a" * 74 + " "),
            "unsubtracted prompt-width mutation survived")
    rejected["viewport-does-not-subtract-prompt"] = vm.active_row[-8:]

    logical = P._read_suite(str(SUITE))
    require(logical.get("ignored_output_codes") == [17, 19],
            "display control-code exclusion is not explicit and exact")
    logical["ignored_output_codes"] = []
    try:
        P.check_suite("v1.6-display-owner-controls-not-excluded", logical)
    except (P.StdlibCheckError, B.VMError, AssertionError) as error:
        rejected["screen-controls-not-declared"] = str(error)
    else:
        raise GateError(
            "undeclared screen controls survived the logical-output oracle")

    require(len(rejected) == 4, "display mutation family count drift")
    return rejected


def artifact_gate(contract: dict[str, Any]) -> dict[str, Any]:
    suite = P._read_suite(str(SUITE))
    result = P.check_suite("v1.6-display-owner-comfort", suite)
    sizes = {name: len(result["code_by_name"][name].encode())
             for name in COMFORT_FUNCTIONS}
    resident = P._read_suite(str(RESIDENT))
    (_heap, _names, code, *_rest) = P._compile_suite(resident)
    for name in ("%rl-render", "%rl-screen-tail", "%read-line-loop",
                 "%rl-cut", "%rl-put"):
        sizes[name] = len(code[name].encode())
    require(max(sizes.values()) <= contract["placement"]["maximum_code_object_bytes"],
            f"display owner exceeds object ceiling: {sizes}")
    require("%fasl-fs" not in code and "%c1-compile-source" in code,
            "authorized one-for-one private reclaim did not reach emitted resident world")
    require(result["cases"] == 9 and result["functions"] == 3,
            "Comfort artifact execution coverage drift")
    return {
        "code_object_bytes": sizes,
        "largest_bytes": max(sizes.values()),
        "comfort_cases": result["cases"],
        "new_names": 1,
        "reclaimed_names": 1,
        "resident_bytes": 0,
        "far_service_bytes": 0,
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    source = source_gate(
        contract, EDITOR.read_text(encoding="utf-8"),
        COMFORT.read_text(encoding="utf-8"),
    )
    composed = composed_gate()
    mutations = executable_mutations()
    artifacts = artifact_gate(contract)
    return {
        "format": "lisp65-c2-v160-display-ownership-receipt-v1",
        "recorded_on": "2026-08-21",
        "status": "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF",
        "source": source, "composed_framebuffer": composed,
        "mutations_rejected": mutations, "artifacts": artifacts,
        "authority": {
            "contract": bind(CONTRACT), "editor": bind(EDITOR),
            "comfort": bind(COMFORT), "suite": bind(SUITE),
            "resident": bind(RESIDENT), "gate": bind(Path(__file__)),
        },
        "claim_limit": "host composed-framebuffer and emitted bytecode; no product link or device claim",
    }


def selftest() -> None:
    before = bind(RECEIPT)
    value = check()
    require(len(value["mutations_rejected"]) == 4,
            "display ownership selftest mutation count drift")
    require(bind(RECEIPT) == before,
            "display ownership check mutated its sealed receipt")


def check() -> dict[str, Any]:
    # This is a living semantic gate over the current sources.  The tracked
    # receipt witnesses the completed display card's world and is consumed by
    # later media evidence; a check is therefore a reader, never its writer.
    return derive()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
            print("v1.6 display ownership: SELFTEST PASS mutations=4")
        else:
            value = check()
            art = value["artifacts"]
            print("v1.6 display ownership: CHECK PASS "
                  f"largest={art['largest_bytes']} names=+1/-1 "
                  "headroom=33/594 framebuffer=composed")
        return 0
    except (GateError, P.StdlibCheckError, B.VMError, AssertionError) as error:
        print(f"v1.6 display ownership: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
