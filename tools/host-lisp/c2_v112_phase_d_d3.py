#!/usr/bin/env python3
"""Bind Link-92 Phase-D D3 split-library and quiet editor acceptance."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402

CONFIG = ROOT / "config/c2-v112-link92-phase-d-d3.json"
SCRIPT = ROOT / "scripts/c2-v112-link92-phase-d-d3-hw.sh"
GATES = ROOT / "mk/gates.mk"
STRING_SUITE = ROOT / "tests/bytecode/libs/p0-string-extra.json"
INSPECT_SUITE = ROOT / "tests/bytecode/libs/p0-inspect.json"
PHYSICAL_PRECEDENT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-closing-device-first-red-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d3-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d3-device-receipt.json")
OUT = Path(os.environ.get(
    "OUT", ROOT / "build/c2.3/v1.4.0-release/phase-d-split/d3"))
if not OUT.is_absolute():
    OUT = ROOT / OUT


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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"binding absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def rows_by_id(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = value.get("libraries", {}).get("rows", [])
    result = {row.get("id"): row for row in rows if isinstance(row, dict)}
    require(len(rows) == len(result), "D3 split-library row ids are not unique")
    return result


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") == "lisp65-c2-v112-link92-phase-d-d3-v1",
            "D3 format drift")
    require(value.get("D1_authority", {}).get("status") ==
            "passed-link92-d1-q-time-string-smokes", "D3 D1 authority drift")
    identity = value.get("identity", {})
    medium = ROOT / identity.get("library_medium", {}).get("path", "")
    require(medium.is_file()
            and identity.get("library_medium", {}).get("bytes") == medium.stat().st_size
            and identity.get("library_medium", {}).get("sha256") == sha(medium),
            "D3 base-library identity/readback drift")
    require(identity.get("product", {}).get("sha256") ==
            "fcc785365d2a6d7a3269367a4234cb372783d46b9debdee6ad37e758f6e20a52",
            "D3 Link-92 product identity drift")
    preloads = identity.get("preloads", [])
    require(len(preloads) == 7 and preloads[0].get("bytes") == 50816
            and preloads[0].get("address") == "0x00050000",
            "D3 complete reset-domain/preload closure drift")
    require(identity.get("c2j_clear") == {
        "address": "0x0005c640", "bytes": 64,
        "authority": "build/ship-builder/v13/closing-device-session/zero-c2j.bin",
        "sha256": "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b",
    }, "D3 C2J CLEAR authority drift")
    require(identity.get("boot_quiet_seconds") == 45
            and identity.get("banner") == "WORKBENCH 1.4.0"
            and identity.get("prompt") == "lisp65>",
            "D3 boot observation contract drift")
    require(value.get("libraries", {}).get("requires") == [
        {"id": "string-extra", "form": "(require(quote string-extra))",
         "expect": "t", "quiet_seconds": 120},
        {"id": "inspect", "form": "(require(quote inspect))",
         "expect": "t", "quiet_seconds": 120},
    ], "D3 quiet split-library require contract drift")
    rows = rows_by_id(value)
    expected_ids = ["capitalize", "string-split", "who-calls"]
    require(list(rows) == expected_ids, "D3 split-library row order drift")
    expected = {
        "capitalize": ('(capitalize "hello")', '"Hello"'),
        "string-split": ('(string-split "a,b,c" ",")', '("a" "b" "c")'),
        "who-calls": ("(who-calls(quote %ide-region-parts-tail))",
                      "(%ide-region-parts %ide-region-parts-tail)"),
    }
    for name, pair in expected.items():
        require((rows[name].get("form"), rows[name].get("expect")) == pair,
                f"D3 split-library oracle drift: {name}")
    require(not {"trace", "trace-call", "untrace", "post-untrace"}
            .intersection(rows), "D3 retained a descoped trace row")
    editor = value.get("editor", {})
    text = editor.get("physical_text", "")
    require(editor.get("form") == '(ide"measure3")'
            and len(text.encode("ascii")) == editor.get("physical_keys") == 64
            and editor.get("return_pressed") is False
            and editor.get("observations_during_physical_window") == 0
            and editor.get("initial_fill") == 0
            and editor.get("final_fill") == 64,
            "D3 physical editor contract drift")


def validate_authorities(value: dict[str, Any]) -> None:
    d1 = load(ROOT / value["D1_authority"]["path"])
    require(d1.get("status") == value["D1_authority"]["status"],
            "D3 D1 receipt authority drift")
    for item in [value["identity"]["library_medium"],
                 value["identity"]["product"],
                 *value["identity"]["preloads"]]:
        path = ROOT / item["path"]
        require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                f"D3 artifact binding drift: {item['path']}")
    c2j = value["identity"]["c2j_clear"]
    c2j_path = ROOT / c2j["authority"]
    require(c2j_path.stat().st_size == c2j["bytes"]
            and sha(c2j_path) == c2j["sha256"]
            and c2j_path.read_bytes() == bytes(64),
            "D3 C2J CLEAR file authority drift")
    reset = (ROOT / value["identity"]["preloads"][0]["path"]).read_bytes()
    require(reset[33840:] == bytes(16976)
            and reset[0xC640:0xC680] == bytes(64),
            "D3 reset domain does not carry a CLEAR C2J suffix")
    string_suite = load(STRING_SUITE)
    inspect_suite = load(INSPECT_SUITE)
    string_cases = {row["name"]: (row["expr"], row["expect"])
                    for row in string_suite.get("cases", [])}
    inspect_cases = {row["name"]: (row["expr"], row["expect"])
                     for row in inspect_suite.get("cases", [])}
    rows = rows_by_id(value)
    require(string_suite.get("provides") == ["string-extra"]
            and inspect_suite.get("provides") == ["inspect"]
            and string_cases.get("capitalize-mixed") ==
            ('(capitalize "hELLO")', '"Hello"')
            and string_cases.get("string-split-basic") ==
            (rows["string-split"]["form"], rows["string-split"]["expect"])
            and inspect_cases.get("who-calls-known") ==
            ("(who-calls '%ide-region-parts-tail)",
             rows["who-calls"]["expect"]),
            "D3 split-library host oracle authority drift")
    require(inspect_suite.get("sources") == [
        "lib/comfort-who-calls-generated.lisp"]
            and inspect_suite.get("functions") == [
                "%comfort-callers-index", "who-calls"],
            "D3 inspect suite retained descoped trace freight")
    precedent = load(PHYSICAL_PRECEDENT).get("rider_1_physical_editor", {})
    require(precedent.get("result") == "passed-64-physical-keys-persisted-64"
            and precedent.get("active_window", {}).get("physical_keys") == 64,
            "D3 physical editor precedent drift")


def order_window(source: str) -> str:
    begin, end = "# D3-ORDER-BEGIN", "# D3-ORDER-END"
    require(source.count(begin) == source.count(end) == 1,
            "D3 source ownership markers drift")
    return source.split(begin, 1)[1].split(end, 1)[0]


def validate_script(source: str) -> None:
    order = order_window(source)
    tokens = ["fresh_start", "ftp_library", "load_identity",
              "run_quiet_requires", "jq -c '.libraries.rows[]'",
              'python3 "$PY" check-libraries', "D3-editor-input",
              "capture_buffer d3-context", "check-d1-buffer",
              "run_m65 -r", "physical-window-active"]
    positions = []
    for token in tokens:
        require(token in order, f"D3 ordered token absent: {token}")
        positions.append(order.index(token))
    require(positions == sorted(positions), "D3 execution order drift")
    for token in ('-c "get $remote $readback_path"', 'cmp "$media" "$readback_path"',
                  'jq -c \'.identity.preloads[]\'',
                  'readback "$((address))" "$bytes"', 'cmp "$path"',
                  'readback "$c2j_address" "$c2j_bytes"',
                  'cmp "$c2j_authority" "$OUT/D3-c2j-before-run.bin"',
                  'sleep "$quiet"',
                  "--expected-fill 64"):
        require(token in source, f"D3 runner proof absent: {token}")
    require(source.count("run_quiet_requires() (") == 1,
            "D3 quiet-requires helper ownership drift")
    quiet_requires = source.split("run_quiet_requires() (", 1)[1].split("\n)\n", 1)[0]
    require("--verified-input --no-readback" in quiet_requires
            and 'sleep "$quiet"' in quiet_requires
            and 'capture_screen "D3-require-$id"' in quiet_requires,
            "D3 quiet split-library require chain drift")
    physical = source.split(': > "$OUT/physical-window-active"', 1)[1]
    require("run_m65" not in physical and "capture_screen" not in physical
            and "readback" not in physical,
            "D3 physical window contains automated observation")
    require("D2" not in order, "D3 runner crosses into D2")


def validate_driver(source: str) -> None:
    header = source.split("class GateError", 1)[0]
    require('OUT = Path(os.environ.get(' in header
            and '"OUT", ROOT / "build/c2.3/v1.4.0-release/phase-d-split/d3"' in header
            and "if not OUT.is_absolute():" in header
            and "OUT = ROOT / OUT" in header,
            "D3 Python checker ignores the runner output override")


def rejected_mutations(
    value: dict[str, Any], source: str, driver_source: str,
) -> list[str]:
    mutations: list[tuple[str, dict[str, Any]]] = []
    def mutate(name: str, callback: Any) -> None:
        candidate = deepcopy(value); callback(candidate); mutations.append((name, candidate))
    mutate("library-identity-drift", lambda x: x["identity"]["library_medium"].update(sha256="00" * 32))
    mutate("reset-domain-prefix-only", lambda x: x["identity"]["preloads"][0].update(bytes=33840))
    mutate("preload-removed", lambda x: x["identity"]["preloads"].pop())
    mutate("C2J-clear-dimmed", lambda x: x["identity"]["c2j_clear"].update(bytes=63))
    mutate("early-boot-look", lambda x: x["identity"].update(boot_quiet_seconds=20))
    mutate("early-require-look", lambda x: x["libraries"]["requires"][0].update(quiet_seconds=1))
    mutate("library-require-order-swapped", lambda x: x["libraries"]["requires"].reverse())
    mutate("legacy-comfort-require-reintroduced",
           lambda x: x["libraries"]["requires"][0].update(
               id="comfort", form="(require(quote comfort))"))
    mutate("library-row-order-swapped", lambda x: x["libraries"]["rows"].reverse())
    mutate("virtual-uppercase-fixture-reintroduced",
           lambda x: x["libraries"]["rows"][0].update(form='(capitalize "hELLO")'))
    mutate("apostrophe-fixture-reintroduced",
           lambda x: x["libraries"]["rows"][2].update(
               form="(who-calls '%ide-region-parts-tail)"))
    mutate("who-calls-dimmed", lambda x: x["libraries"]["rows"][2].update(expect="nil"))
    mutate("trace-row-reintroduced", lambda x: x["libraries"]["rows"].append(
        {"id": "trace", "form": "(trace capitalize)", "expect": "capitalize"}))
    mutate("untrace-row-reintroduced", lambda x: x["libraries"]["rows"].append(
        {"id": "untrace", "form": "(untrace capitalize)", "expect": "capitalize"}))
    mutate("physical-short", lambda x: x["editor"].update(physical_text="a" * 63))
    mutate("physical-return", lambda x: x["editor"].update(return_pressed=True))
    mutate("physical-observation", lambda x: x["editor"].update(observations_during_physical_window=1))
    mutate("final-fill-dimmed", lambda x: x["editor"].update(final_fill=63))
    rejected = []
    for name, candidate in mutations:
        try: validate_contract(candidate)
        except GateError: rejected.append(name)
        else: raise GateError(f"D3 contract mutation survived: {name}")
    source_mutations = {
        "source-preload-readback-removed": source.replace('readback "$((address))" "$bytes"', ': # readback removed', 1),
        "source-preload-compare-removed": source.replace('cmp "$path"', ': # compare removed', 1),
        "source-C2J-readback-removed": source.replace(
            'readback "$c2j_address" "$c2j_bytes"', ': # C2J readback removed', 1),
        "source-verified-require-removed": source.replace(
            "--verified-input --no-readback", "--no-readback"),
        "source-physical-observation-added": source.replace(
            ': > "$OUT/physical-window-active"',
            ': > "$OUT/physical-window-active"\nrun_m65 --screenshot=bad.png', 1),
        "source-D2-crossing": source.replace(
            'python3 "$PY" check-libraries', 'echo D2\npython3 "$PY" check-libraries', 1),
    }
    for name, candidate in source_mutations.items():
        try: validate_script(candidate)
        except GateError: rejected.append(name)
        else: raise GateError(f"D3 source mutation survived: {name}")
    candidate = driver_source.replace(
        'OUT = Path(os.environ.get(', 'OUT = Path({}.get(', 1)
    try: validate_driver(candidate)
    except GateError: rejected.append("driver-output-override-ignored")
    else: raise GateError("D3 driver output-override mutation survived")
    return rejected


def latest_segment(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    clean = [line[1:-1] if len(line) == 82 and line.startswith(" ")
             and line.endswith(" ") else line for line in lines]
    prompts = [i for i, line in enumerate(clean) if line.lstrip().startswith("lisp65>")]
    require(len(prompts) >= 2, f"D3 latest segment absent: {path}")
    return "\n".join(clean[prompts[-2]:prompts[-1]])


def check_libraries() -> dict[str, Any]:
    value = load(CONFIG); validate_contract(value); rows = rows_by_id(value)
    require_results = []
    for row in value["libraries"]["requires"]:
        text = OUT / f"D3-require-{row['id']}.txt"
        screen = OUT / f"D3-require-{row['id']}.png"
        SCREEN.check_latest_result(text, row["form"], row["expect"])
        SCREEN.check_fail_closed_frame(screen)
        require_results.append({"id": row["id"], "form": row["form"],
                                "expect": row["expect"], "text": bind(text),
                                "screen": bind(screen)})
    results = []
    for name, row in rows.items():
        text, png = OUT / f"D3-{name}.txt", OUT / f"D3-{name}.png"
        SCREEN.check_latest_result(text, row["form"], row["expect"])
        SCREEN.check_fail_closed_frame(png)
        segment = latest_segment(text)
        for marker in row.get("visible_markers", []):
            require(marker in segment, f"D3 visible trace marker absent: {marker}")
        for marker in row.get("forbid_latest_markers", []):
            require(marker not in segment, f"D3 untrace restoration failed: {marker}")
        results.append({"id": name, "form": row["form"], "expect": row["expect"],
                        "text": bind(text), "screen": bind(png)})
    return {"requires": require_results,
            "rows": results}


def evaluate(*, write: bool) -> dict[str, Any]:
    value = load(CONFIG); validate_contract(value); validate_authorities(value)
    source = SCRIPT.read_text(encoding="utf-8"); validate_script(source)
    driver_source = Path(__file__).read_text(encoding="utf-8")
    validate_driver(driver_source)
    gates = GATES.read_text(encoding="utf-8")
    require("c2-v112-phase-d-d3-selftest:" in gates
            and "c2_v112_phase_d_d3.py selftest" in gates
            and "check-source: c2-v112-phase-d-d3-selftest" in gates,
            "D3 permanent gate registration drift")
    rejected = rejected_mutations(value, source, driver_source)
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d3-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-D3-split-libraries-and-physical-editor-ready",
        "bindings": {"config": bind(CONFIG), "runner": bind(SCRIPT),
                     "D1_authority": bind(ROOT / value["D1_authority"]["path"]),
                     "string_extra_suite": bind(STRING_SUITE),
                     "inspect_suite": bind(INSPECT_SUITE),
                     "physical_precedent": bind(PHYSICAL_PRECEDENT),
                     "C2J_CLEAR_authority": bind(
                         ROOT / value["identity"]["c2j_clear"]["authority"])},
        "identity": value["identity"], "libraries": value["libraries"],
        "editor": value["editor"], "mutations_rejected": rejected,
        "mutation_count": len(rejected),
        "execution_accounting": {"hardware_contacts": 0, "D3_rows": 0, "D2_rows": 0},
        "claim_limit": value["claim_limit"],
    }
    if write: PREP.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def close_result() -> dict[str, Any]:
    prep = load(PREP)
    require(prep.get("status") == "passed-D3-split-libraries-and-physical-editor-ready",
            "D3 preparation authority drift")
    value = load(CONFIG); libraries = check_libraries()
    context = load(OUT / "d3-context-buffer-context.json")
    final = load(OUT / "d3-final-buffer-context.json")
    require(context.get("expected_fill") == 0 and final.get("expected_fill") == 64,
            "D3 physical editor buffer postcondition drift")
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d3-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-D3-three-split-library-names-and-physical-editor-64-of-64",
        "libraries": libraries,
        "editor": {"physical_text": value["editor"]["physical_text"],
                   "physical_keys": 64, "return_pressed": False,
                   "observations_during_window": 0,
                   "precondition": context, "postcondition": final,
                   "context_screen": bind(OUT / "D3-editor-context.png"),
                   "final_screen": bind(OUT / "D3-editor-final.png")},
        "bindings": {"preparation": bind(PREP),
                     "library_readback": bind(OUT / "D3-library-readback.d81"),
                     "boot_screen": bind(OUT / "D3-boot.png")},
        "execution_accounting": {"hardware_contacts": 1, "D3_rows": 1,
                                 "D2_rows": 0, "product_rebuilds": 0,
                                 "media_rebuilds": 0, "additional_links": 0},
        "disposition": {"D1": "green", "D3": "green", "next": "cold reset then D2",
                        "D2": "not_started", "selector": "unset"},
        "claim_limit": value["claim_limit"],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare", "selftest", "dry-run",
                                           "check-libraries", "result"))
    args = parser.parse_args()
    try:
        if args.action == "check-libraries":
            value = check_libraries(); print(f"c2-v112-phase-d-d3: PASS split-library rows={len(value['rows'])}")
        elif args.action == "result":
            value = close_result(); print(f"c2-v112-phase-d-d3: PASS {value['status']}")
        else:
            value = evaluate(write=args.action == "prepare")
            print("c2-v112-phase-d-d3: PASS "
                  f"mutations={value['mutation_count']} split-library=3 physical=64")
        return 0
    except (GateError, SCREEN.CheckError, OSError, json.JSONDecodeError) as error:
        print("c2-v112-phase-d-d3: FIRST RED: "
              f"{getattr(error, 'message', str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
