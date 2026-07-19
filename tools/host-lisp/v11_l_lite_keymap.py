#!/usr/bin/env python3
"""Generate and verify the Wave-3 L-lite keymap implementation and claims."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-l-lite-keymap.json"
LISP_OUT = ROOT / "lib/ide-keymap-generated.lisp"
HOST_CASES_OUT = ROOT / "lib/tests/ide-keymap-eval-cases.generated.json"
P0_CORE_CASES_OUT = ROOT / "tests/bytecode/libs/p0-ide-keymap-cases.generated.json"
P0_EXTRA_CASES_OUT = ROOT / "tests/bytecode/libs/p0-ide-keymap-extra-cases.generated.json"
HW_CASES_OUT = ROOT / "tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json"
DOC_OUT = ROOT / "docs/generated/ide-keymap.md"

ROUTE_IDS = {
    "direct": 1,
    "line-start": 2,
    "line-end": 3,
    "save": 4,
    "find": 5,
    "write": 6,
    "switch": 7,
    "directory": 8,
    "compile": 9,
    "next-buffer": 10,
    "previous-buffer": 11,
    "motion": 12,
    "exit": 13,
}


class KeymapError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise KeymapError(message)


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise KeymapError(f"cannot read keymap contract: {exc}") from exc
    require(isinstance(value, dict), "keymap contract must be an object")
    require(value.get("format") == "lisp65-v11-l-lite-keymap-v1", "keymap format drift")
    return value


def validate(value: dict[str, Any]) -> None:
    model = value.get("event_model")
    commands = value.get("commands")
    bindings = value.get("bindings")
    mx = value.get("m_x_commands")
    global_bindings = value.get("global_hardware_bindings")
    behavior_cases = value.get("behavior_hardware_cases")
    require(isinstance(model, dict), "event_model missing")
    require(isinstance(commands, list) and commands, "commands missing")
    require(isinstance(bindings, list) and bindings, "bindings missing")
    require(isinstance(mx, list) and mx, "m_x_commands missing")
    require(isinstance(global_bindings, list) and global_bindings,
            "global hardware bindings missing")
    require(isinstance(behavior_cases, list) and behavior_cases,
            "behavior hardware cases missing")

    command_ids: set[int] = set()
    command_names: set[str] = set()
    descriptions: dict[int, str] = {}
    for row in commands:
        require(isinstance(row, dict), "command row must be an object")
        command = row.get("id")
        name = row.get("name")
        route = row.get("route")
        description = row.get("description")
        require(isinstance(command, int) and 0 < command < 32768,
                "command id must be a positive fixnum")
        require(command not in command_ids, f"duplicate command id: {command}")
        require(isinstance(name, str) and name and name not in command_names,
                f"duplicate/invalid command name: {name!r}")
        require(isinstance(description, str) and description,
                f"missing command description: {name}")
        require(route in ROUTE_IDS, f"missing/invalid command route: {name}")
        command_ids.add(command)
        command_names.add(name)
        descriptions[command] = description

    prefix = model.get("prefix_code")
    require(isinstance(prefix, int) and 1 <= prefix <= 255, "prefix code invalid")
    sequence_ids: set[str] = set()
    sequences: set[tuple[int, ...]] = set()
    for row in bindings:
        require(isinstance(row, dict), "binding row must be an object")
        binding_id = row.get("id")
        display = row.get("display")
        codes = row.get("codes")
        command = row.get("command")
        require(isinstance(binding_id, str) and binding_id and binding_id not in sequence_ids,
                f"duplicate/invalid binding id: {binding_id!r}")
        require(isinstance(display, str) and display, f"binding display missing: {binding_id}")
        require(isinstance(codes, list) and len(codes) in (1, 2)
                and all(isinstance(code, int) and 0 <= code <= 255 for code in codes),
                f"binding codes invalid: {binding_id}")
        seq = tuple(codes)
        require(seq not in sequences, f"duplicate key sequence: {seq}")
        require(command in command_ids, f"unknown command {command}: {binding_id}")
        if len(codes) == 2:
            require(codes[0] == prefix, f"two-key binding lacks C-x prefix: {binding_id}")
        sequence_ids.add(binding_id)
        sequences.add(seq)

    required = {
        (prefix, 3): 1015,
        (prefix, 32): 1115,
        (prefix, 120): 1013,
        (prefix, 13): 1013,
    }
    actual = {tuple(row["codes"]): row["command"] for row in bindings}
    for sequence, command in required.items():
        require(actual.get(sequence) == command,
                f"required binding drift: {sequence} -> {command}")
    require((0,) not in actual, "unreachable C-Space binding returned")
    require((3,) not in actual, "RUN/STOP must not be an editor binding")

    mx_names: set[str] = set()
    for row in mx:
        require(isinstance(row, dict), "M-x row must be an object")
        name = row.get("name")
        command = row.get("command")
        require(isinstance(name, str) and len(name) > 2 and name not in mx_names,
                f"duplicate/invalid M-x name: {name!r}")
        require(command in command_ids, f"unknown M-x command: {name}")
        mx_names.add(name)
    require({row["name"] for row in mx} == {
        "find-file", "save-buffer", "compile-load", "goto-line", "eval-buffer"
    }, "public M-x surface drift")

    run_stop = [row for row in global_bindings if row.get("id") == "run-stop-abort"]
    require(len(run_stop) == 1 and run_stop[0].get("safety_critical") is True,
            "RUN/STOP safety-critical hardware case missing")
    behavior_ids: set[str] = set()
    for row in behavior_cases:
        require(isinstance(row, dict), "behavior hardware row must be an object")
        case_id = row.get("id")
        require(isinstance(case_id, str) and case_id and case_id not in behavior_ids,
                f"duplicate/invalid behavior hardware case: {case_id!r}")
        require(row.get("new_surface") is True,
                f"behavior hardware case must be new-surface-first: {case_id}")
        require(isinstance(row.get("display"), str) and isinstance(row.get("result"), str),
                f"behavior hardware case missing description/result: {case_id}")
        behavior_ids.add(case_id)


def lisp_atom(value: int) -> str:
    return str(value)


def flat_table(rows: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for row in rows:
        values.extend((str(row["codes"][-1]), lisp_atom(row["command"])))
    return "(" + " ".join(values) + ")"


def render_lisp(value: dict[str, Any]) -> str:
    model = value["event_model"]
    bindings = value["bindings"]
    base = [row for row in bindings if len(row["codes"]) == 1]
    prefix = [row for row in bindings if len(row["codes"]) == 2]
    mx = value["m_x_commands"]
    command_routes = [
        {"codes": [row["id"]], "command": ROUTE_IDS[row["route"]]}
        for row in value["commands"]
    ]
    mx_names = " ".join(json.dumps(row["name"]) for row in mx)
    lines = [
        ";; Generated by tools/host-lisp/v11_l_lite_keymap.py from",
        ";; config/v11-l-lite-keymap.json. Do not edit this file directly.",
        "",
        "(defun ide-printable-code-p (code)",
        f"  (and (>= code {model['printable_min']}) (<= code {model['printable_max']})))",
        "",
        "(defun %ide-keymap-lookup (code table)",
        "  (if table",
        "      (if (= code (car table))",
        "          (car (cdr table))",
        "          (%ide-keymap-lookup code (cdr (cdr table))))",
        "      nil))",
        "",
        "(defun %ide-prefix-command (code)",
        "  (progn",
        "    (set-symbol-value (quote ide-event-command) nil)",
        f"    (%ide-keymap-lookup code (quote {flat_table(prefix)}))))",
        "",
        "(defun %ide-base-command (code)",
        f"  (%ide-keymap-lookup code (quote {flat_table(base)})))",
        "",
        "(defun %ide-command-route (command)",
        f"  (%ide-keymap-lookup command (quote {flat_table(command_routes)})))",
        "",
        "(defun %ide-direct-p (command)",
        "  (eq (%ide-command-route command) 1))",
        "",
        "(defun ide-event-command (event)",
        "  ((lambda (code)",
        f"     (if (eq (symbol-value (quote ide-event-command)) {model['prefix_code']})",
        "         (%ide-prefix-command code)",
        f"         (if (= code {model['prefix_code']})",
        f"             (progn (set-symbol-value (quote ide-event-command) {model['prefix_code']}) nil)",
        "             ((lambda (command)",
        "                (if command",
        "                    command",
        f"                    (if (and (>= code {model['printable_min']})",
        f"                             (<= code {model['printable_max']}))",
        f"                        {model['printable_command']}",
        "                        nil)))",
        "              (%ide-base-command code)))))",
        "   (ide-event-code event)))",
        "",
        "(defun ide-command-names ()",
        f"  (list {mx_names}))",
        "",
        "(defun %ide-command-named (name)",
        "  (cond",
    ]
    for row in mx:
        lines.append(f"        ((string= name {json.dumps(row['name'])}) {row['command']})")
    lines.extend(("        (t nil)))", ""))
    return "\n".join(lines)


def sequence_expr(codes: list[int]) -> str:
    prefix_reset = "(set-symbol-value (quote ide-event-command) nil)"
    if len(codes) == 1:
        return f"(progn {prefix_reset} (ide-event-command (list (quote key) {codes[0]} nil)))"
    return (
        f"(progn {prefix_reset} "
        f"(ide-event-command (list (quote key) {codes[0]} nil)) "
        f"(ide-event-command (list (quote key) {codes[1]} nil)))"
    )


def binding_cases(value: dict[str, Any], *, p0: bool) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    input_key = "expr" if p0 else "input"
    for row in value["bindings"]:
        cases.append({
            "name": f"l-lite-binding-{row['id']}",
            input_key: sequence_expr(row["codes"]),
            "expect": str(row["command"]),
        })
    cases.extend((
        {
            "name": "l-lite-prefix-unknown-clears-carrier",
            input_key: "(progn (set-symbol-value (quote ide-event-command) 24) (ide-event-command (list (quote key) 8 nil)) (symbol-value (quote ide-event-command)))",
            "expect": "nil" if p0 else "NIL",
        },
        {
            "name": "l-lite-run-stop-not-editor-command",
            input_key: "(progn (set-symbol-value (quote ide-event-command) nil) (ide-event-command (list (quote key) 3 nil)))",
            "expect": "nil" if p0 else "NIL",
        },
        {
            "name": "l-lite-control-space-unreachable",
            input_key: "(progn (set-symbol-value (quote ide-event-command) nil) (ide-event-command (list (quote key) 0 nil)))",
            "expect": "nil" if p0 else "NIL",
        },
    ))
    return cases


def render_host_cases(value: dict[str, Any]) -> str:
    document = {
        "format": "lisp65-host-eval-cases-v1",
        "generated_from": "config/v11-l-lite-keymap.json",
        "cases": binding_cases(value, p0=False),
    }
    return json.dumps(document, indent=2, ensure_ascii=True) + "\n"


def render_p0_cases(value: dict[str, Any], extra: bool) -> str:
    cases = [] if extra else binding_cases(value, p0=True)
    if extra:
        for row in value["m_x_commands"]:
            cases.append({
                "name": f"l-lite-mx-exact-{row['name']}",
                "expr": f"(%ide-command-named {json.dumps(row['name'])})",
                "expect": str(row["command"]),
            })
        cases.extend((
            {"name": "l-lite-mx-rejects-two-character-prefix",
             "expr": "(%ide-command-named \"fi\")", "expect": "nil"},
            {"name": "l-lite-mx-rejects-trailing-junk",
             "expr": "(%ide-command-named \"save-buffer-junk\")", "expect": "nil"},
        ))
    document = {
        "generated_from": "config/v11-l-lite-keymap.json",
        "cases": cases,
    }
    return json.dumps(document, indent=2, ensure_ascii=True) + "\n"


def render_hardware_cases(value: dict[str, Any]) -> str:
    cases: list[dict[str, Any]] = []
    for row in value["bindings"]:
        cases.append({
            "id": f"binding-{row['id']}",
            "surface": "ide-keymap",
            "display": row["display"],
            "codes": row["codes"],
            "command": row["command"],
            "fidelity": "emulator-dry-plus-hardware",
            "new_surface": bool(row.get("new_surface", False)),
            "receipt_policy": "dry-variant-non-authoritative; hardware-exactly-once",
        })
    for row in value["global_hardware_bindings"]:
        cases.insert(0, {
            **row,
            "surface": "global-control",
            "fidelity": "emulator-dry-plus-hardware",
            "receipt_policy": "dry-variant-non-authoritative; hardware-exactly-once",
        })
    for row in value["behavior_hardware_cases"]:
        cases.insert(0, {
            **row,
            "surface": "ide-behavior",
            "fidelity": "emulator-dry-plus-hardware",
            "receipt_policy": "dry-variant-non-authoritative; hardware-exactly-once",
        })
    cases.sort(key=lambda row: (not row.get("new_surface", False), row["id"]))
    document = {
        "format": "lisp65-v11-l-lite-hardware-cases-v1",
        "generated_from": "config/v11-l-lite-keymap.json",
        "execution_order": "new-surfaces-first",
        "claims_before_hardware": "none",
        "cases": cases,
    }
    return json.dumps(document, indent=2, ensure_ascii=True) + "\n"


def render_docs(value: dict[str, Any]) -> str:
    descriptions = {row["id"]: row["description"] for row in value["commands"]}
    lines = [
        "<!-- Generated by tools/host-lisp/v11_l_lite_keymap.py. Do not edit. -->",
        "# Workbench key bindings",
        "",
        "The 1.1 L-lite profile uses the MEGA65 GETIN-compatible key codes. It does not",
        "claim physical Meta/Alt modifier identity; the command launcher is `C-x x` or",
        "`C-x Return`. `C-x Space` sets the mark because code zero means an empty queue",
        "and therefore cannot represent C-Space on this input path.",
        "",
        "| Key | Action |",
        "| --- | --- |",
    ]
    for row in value["bindings"]:
        lines.append(f"| `{row['display']}` | {descriptions[row['command']]} |")
    lines.extend((
        "",
        "RUN/STOP is not an editor key. During evaluation it aborts to a usable REPL",
        "with `stopped (run/stop)`; while idle it has no product action. Exit the editor",
        "with `C-x C-c`; the active buffer is preserved.",
        "",
        "## Command launcher",
        "",
        "Command names are matched exactly; two-character prefixes are not accepted.",
        "",
        "| Command | Action |",
        "| --- | --- |",
    ))
    for row in value["m_x_commands"]:
        lines.append(f"| `{row['name']}` | {descriptions[row['command']]} |")
    lines.append("")
    return "\n".join(lines)


def outputs(value: dict[str, Any]) -> dict[Path, str]:
    validate(value)
    return {
        LISP_OUT: render_lisp(value),
        HOST_CASES_OUT: render_host_cases(value),
        P0_CORE_CASES_OUT: render_p0_cases(value, extra=False),
        P0_EXTRA_CASES_OUT: render_p0_cases(value, extra=True),
        HW_CASES_OUT: render_hardware_cases(value),
        DOC_OUT: render_docs(value),
    }


def write_outputs(value: dict[str, Any]) -> None:
    for path, content in outputs(value).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"generated {path.relative_to(ROOT)}")


def check_outputs(value: dict[str, Any]) -> None:
    for path, expected in outputs(value).items():
        require(path.is_file(), f"generated output missing: {path.relative_to(ROOT)}")
        require(path.read_text(encoding="utf-8") == expected,
                f"generated output drift: {path.relative_to(ROOT)}")
    print(f"v11-l-lite-keymap: PASS bindings={len(value['bindings'])} "
          f"mx={len(value['m_x_commands'])} outputs=6")


def selftest(value: dict[str, Any]) -> None:
    validate(value)
    duplicate = copy.deepcopy(value)
    duplicate["bindings"][1]["codes"] = list(duplicate["bindings"][0]["codes"])
    try:
        validate(duplicate)
    except KeymapError:
        pass
    else:
        raise KeymapError("duplicate binding mutation was accepted")
    unsafe = copy.deepcopy(value)
    unsafe["bindings"].append({
        "id": "bad-run-stop", "display": "RUN/STOP", "codes": [3], "command": 1015,
    })
    try:
        validate(unsafe)
    except KeymapError:
        pass
    else:
        raise KeymapError("RUN/STOP editor mutation was accepted")
    partial = render_lisp(value)
    require('(string= name "find-file")' in partial and 'string-ref name' not in partial,
            "exact M-x matcher was not generated")
    with tempfile.TemporaryDirectory(prefix="v11-l-lite-keymap-") as raw:
        tmp = Path(raw) / "contract.json"
        tmp.write_text(json.dumps(value), encoding="utf-8")
        validate(load_contract(tmp))
    print("v11-l-lite-keymap: SELFTEST PASS mutations=2 exact-mx=true")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check", "selftest"))
    args = parser.parse_args(argv)
    try:
        value = load_contract()
        if args.command == "generate":
            write_outputs(value)
        elif args.command == "check":
            check_outputs(value)
        else:
            selftest(value)
    except KeymapError as exc:
        print(f"v11-l-lite-keymap: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
