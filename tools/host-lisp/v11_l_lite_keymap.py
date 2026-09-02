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
READ_LINE_OUT = ROOT / "lib/stdlib-read-line.lisp"
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

REPL_BLOCK_BEGIN = ";; BEGIN GENERATED REPL LINE KEYMAP"
REPL_BLOCK_END = ";; END GENERATED REPL LINE KEYMAP"


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
    require(value.get("format") == "lisp65-v11-keymap-v2", "keymap format drift")
    return value


def validate(value: dict[str, Any]) -> None:
    model = value.get("event_model")
    commands = value.get("commands")
    bindings = value.get("bindings")
    modifier_bindings = value.get("modifier_bindings")
    mx = value.get("m_x_commands")
    global_bindings = value.get("global_hardware_bindings")
    behavior_cases = value.get("behavior_hardware_cases")
    repl = value.get("repl_line_projection")
    require(isinstance(model, dict), "event_model missing")
    require(isinstance(commands, list) and commands, "commands missing")
    require(isinstance(bindings, list) and bindings, "bindings missing")
    require(isinstance(modifier_bindings, list) and modifier_bindings,
            "modifier bindings missing")
    require(isinstance(mx, list) and mx, "m_x_commands missing")
    require(isinstance(global_bindings, list) and global_bindings,
            "global hardware bindings missing")
    require(isinstance(behavior_cases, list) and behavior_cases,
            "behavior hardware cases missing")
    require(isinstance(repl, dict), "REPL line projection missing")

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

    repl_ids = repl.get("binding_ids")
    repl_aliases = repl.get("legacy_aliases")
    require(isinstance(repl_ids, list) and repl_ids == [
        "return", "delete-backward", "cursor-left", "cursor-right",
        "cursor-up", "cursor-down", "control-d", "control-f", "control-b",
        "control-a", "control-e",
    ], "REPL line binding projection drift")
    binding_by_id = {row["id"]: row for row in bindings}
    require(all(binding_id in binding_by_id for binding_id in repl_ids),
            "REPL line projection names an absent IDE binding")
    require(all(len(binding_by_id[binding_id]["codes"]) == 1
                for binding_id in repl_ids),
            "REPL line projection contains a prefix binding")
    require(repl_aliases == [{"code": 127, "command": 1101}],
            "REPL legacy DEL alias drift")
    repl_codes = [binding_by_id[binding_id]["codes"][0]
                  for binding_id in repl_ids]
    require(len(repl_codes) == len(set(repl_codes))
            and 127 not in repl_codes,
            "REPL line projection has duplicate codes")

    masks = model.get("modifier_masks")
    require(masks == {"control": 4, "meta": 16}, "modifier mask drift")
    modifier_ids: set[str] = set()
    modifier_keys: set[tuple[int, tuple[str, ...]]] = set()
    for row in modifier_bindings:
        require(isinstance(row, dict), "modifier binding row must be an object")
        binding_id = row.get("id")
        display = row.get("display")
        raw = row.get("raw_petscii")
        normalized = row.get("normalized_code")
        required_modifiers = row.get("required_modifiers")
        command = row.get("command")
        require(isinstance(binding_id, str) and binding_id
                and binding_id not in modifier_ids,
                f"duplicate/invalid modifier binding id: {binding_id!r}")
        require(isinstance(display, str) and display,
                f"modifier binding display missing: {binding_id}")
        require(isinstance(raw, int) and 0 <= raw <= 255,
                f"raw PETSCII invalid: {binding_id}")
        require(isinstance(normalized, int) and 0 <= normalized <= 255,
                f"normalized code invalid: {binding_id}")
        require(isinstance(required_modifiers, list)
                and len(required_modifiers) == 1
                and required_modifiers[0] in masks,
                f"required modifier invalid: {binding_id}")
        key = (normalized, tuple(required_modifiers))
        require(key not in modifier_keys,
                f"duplicate modifier binding: {binding_id}")
        require(command in command_ids,
                f"unknown modifier command {command}: {binding_id}")
        require(row.get("new_surface") is True,
                f"modifier binding must be a new surface: {binding_id}")
        modifier_ids.add(binding_id)
        modifier_keys.add(key)
    require(modifier_ids == {"control-space", "meta-x"},
            "L-full modifier binding set drift")
    by_modifier_id = {row["id"]: row for row in modifier_bindings}
    require(by_modifier_id["control-space"]["raw_petscii"] == 255
            and by_modifier_id["control-space"]["normalized_code"] == 255
            and by_modifier_id["control-space"]["required_modifiers"] == ["control"]
            and by_modifier_id["control-space"]["command"] == 1115,
            "C-Space product binding drift")
    require(by_modifier_id["meta-x"]["raw_petscii"] == 88
            and by_modifier_id["meta-x"]["normalized_code"] == 120
            and by_modifier_id["meta-x"]["required_modifiers"] == ["meta"]
            and by_modifier_id["meta-x"]["command"] == 1013,
            "M-x raw-to-normalized product binding drift")

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
    modifier_bindings = value["modifier_bindings"]
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
        "(defun ide-event-modifiers (event)",
        "  (car (cdr (cdr event))))",
        "",
        "(defun %ide-modifier-command (code modifiers)",
        "  (cond",
    ]
    for row in modifier_bindings:
        modifier = row["required_modifiers"][0]
        lines.append(
            f"        ((and (= code {row['normalized_code']}) "
            f"(member (quote {modifier}) modifiers)) {row['command']})")
    lines.extend([
        "        (t nil)))",
        "",
        "(defun ide-event-command (event)",
        "  ((lambda (code modifiers)",
        "     ((lambda (modified)",
        "        (if modified",
        "            (progn",
        "              (set-symbol-value (quote ide-event-command) nil)",
        "              modified)",
        f"            (if (eq (symbol-value (quote ide-event-command)) {model['prefix_code']})",
        "                (%ide-prefix-command code)",
        f"                (if (= code {model['prefix_code']})",
        f"                    (progn (set-symbol-value (quote ide-event-command) {model['prefix_code']}) nil)",
        "                    ((lambda (command)",
        "                       (if command",
        "                           command",
        f"                           (if (and (>= code {model['printable_min']})",
        f"                                    (<= code {model['printable_max']}))",
        f"                               {model['printable_command']}",
        "                               nil)))",
        "                     (%ide-base-command code))))))",
        "      (%ide-modifier-command code modifiers)))",
        "   (ide-event-code event)",
        "   (ide-event-modifiers event)))",
        "",
        "(defun ide-command-names ()",
        f"  (list {mx_names}))",
        "",
        "(defun %ide-command-named (name)",
        "  (cond",
    ])
    for row in mx:
        lines.append(f"        ((string= name {json.dumps(row['name'])}) {row['command']})")
    lines.extend(("        (t nil)))", ""))
    return "\n".join(lines)


def repl_projection(value: dict[str, Any]) -> list[dict[str, int]]:
    by_id = {row["id"]: row for row in value["bindings"]}
    rows = [
        {"code": by_id[binding_id]["codes"][0],
         "command": by_id[binding_id]["command"]}
        for binding_id in value["repl_line_projection"]["binding_ids"]
    ]
    rows.extend(value["repl_line_projection"]["legacy_aliases"])
    return rows


def render_repl_expression(value: dict[str, Any]) -> str:
    rows = repl_projection(value)
    pairs = " ".join(
        f"({row['code']} . {row['command']})" for row in rows)
    lines = [
        "          ((lambda (binding) (if binding (cdr binding) 0))",
        "           (assoc code",
        f"                  (quote ({pairs}))))",
    ]
    return "\n".join(lines)


def render_read_line(value: dict[str, Any]) -> str:
    try:
        source = READ_LINE_OUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise KeymapError(f"cannot read REPL line editor: {exc}") from exc
    require(source.count(REPL_BLOCK_BEGIN) == 1
            and source.count(REPL_BLOCK_END) == 1,
            "REPL generated keymap block boundary drift")
    before, tail = source.split(REPL_BLOCK_BEGIN, 1)
    _old, after = tail.split(REPL_BLOCK_END, 1)
    return (before + REPL_BLOCK_BEGIN + "\n"
            + render_repl_expression(value) + "\n"
            + REPL_BLOCK_END + after)


def sequence_expr(codes: list[int]) -> str:
    prefix_reset = "(set-symbol-value (quote ide-event-command) nil)"
    if len(codes) == 1:
        return f"(progn {prefix_reset} (ide-event-command (list (quote key) {codes[0]} nil)))"
    return (
        f"(progn {prefix_reset} "
        f"(ide-event-command (list (quote key) {codes[0]} nil)) "
        f"(ide-event-command (list (quote key) {codes[1]} nil)))"
    )


def modifier_event_expr(code: int, modifiers: list[str]) -> str:
    rendered = " ".join(f"(quote {modifier})" for modifier in modifiers)
    modifier_list = f"(list {rendered})" if rendered else "nil"
    return (
        "(progn (set-symbol-value (quote ide-event-command) nil) "
        f"(ide-event-command (list (quote key) {code} {modifier_list})))"
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
    for row in value["modifier_bindings"]:
        modifier = row["required_modifiers"][0]
        cases.extend((
            {
                "name": f"l-full-binding-{row['id']}",
                input_key: modifier_event_expr(
                    row["normalized_code"], [modifier]),
                "expect": str(row["command"]),
            },
            {
                "name": f"l-full-binding-{row['id']}-missing-modifier",
                input_key: modifier_event_expr(row["normalized_code"], []),
                "expect": ("1110" if row["normalized_code"] == 120
                           else ("nil" if p0 else "NIL")),
            },
            {
                "name": f"l-full-binding-{row['id']}-wrong-modifier",
                input_key: modifier_event_expr(
                    row["normalized_code"],
                    ["meta" if modifier == "control" else "control"]),
                "expect": ("1110" if row["normalized_code"] == 120
                           else ("nil" if p0 else "NIL")),
            },
        ))
    cases.extend((
        {
            "name": "l-full-meta-x-raw-petscii-is-not-product-domain",
            input_key: modifier_event_expr(88, ["meta"]),
            "expect": "1110",
        },
        {
            "name": "l-full-foreign-meta-code-falls-back",
            input_key: modifier_event_expr(121, ["meta"]),
            "expect": "1110",
        },
    ))
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
    for row in value["modifier_bindings"]:
        cases.append({
            "id": f"binding-{row['id']}",
            "surface": "ide-keymap",
            "display": row["display"],
            "raw_petscii": row["raw_petscii"],
            "normalized_code": row["normalized_code"],
            "required_modifiers": row["required_modifiers"],
            "command": row["command"],
            "fidelity": "hardware-exact",
            "new_surface": True,
            "receipt_policy": "hardware-exactly-once",
        })
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
        "This generated table is bundled with lisp65 2.0.1.",
        "",
        "The Workbench editor consumes one generated 41-binding table using MEGA65",
        "typed-event key codes.",
        "Its command launcher is `C-x x` or `C-x Return`; `C-x Space` sets the mark.",
        "The same authority generates the IDE and REPL-line projections; release claims",
        "remain limited to the surfaces named by that release's hardware acceptance.",
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
        READ_LINE_OUT: render_read_line(value),
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
          f"repl={len(repl_projection(value))} "
          f"mx={len(value['m_x_commands'])} outputs=7")


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
    duplicate_modifier = copy.deepcopy(value)
    duplicate_modifier["modifier_bindings"][1]["normalized_code"] = 255
    duplicate_modifier["modifier_bindings"][1]["required_modifiers"] = ["control"]
    try:
        validate(duplicate_modifier)
    except KeymapError:
        pass
    else:
        raise KeymapError("duplicate modifier binding mutation was accepted")
    raw_domain = copy.deepcopy(value)
    raw_domain["modifier_bindings"][1]["normalized_code"] = 88
    try:
        validate(raw_domain)
    except KeymapError:
        pass
    else:
        raise KeymapError("raw M-x PETSCII product-domain mutation was accepted")
    partial = render_lisp(value)
    require('(string= name "find-file")' in partial and 'string-ref name' not in partial,
            "exact M-x matcher was not generated")
    require("(defun %ide-modifier-command" in partial
            and "(member (quote control) modifiers)" in partial
            and "(member (quote meta) modifiers)" in partial,
            "modifier-aware product consumer was not generated")
    repl = render_repl_expression(value)
    require("(157 . 1106)" in repl
            and "(29 . 1107)" in repl
            and "(145 . 1108)" in repl
            and "(17 . 1003)" in repl
            and "(127 . 1101)" in repl,
            "REPL line projection was not generated from the IDE bindings")
    with tempfile.TemporaryDirectory(prefix="v11-l-lite-keymap-") as raw:
        tmp = Path(raw) / "contract.json"
        tmp.write_text(json.dumps(value), encoding="utf-8")
        validate(load_contract(tmp))
    print("v11-l-lite-keymap: SELFTEST PASS mutations=4 exact-mx=true "
          "typed-modifiers=true repl-projection=true")


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
