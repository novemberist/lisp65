#!/usr/bin/env python3
"""Bind and close the Link-92 Phase-D D1 q/time/string smoke row."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402

CONFIG = ROOT / "config/c2-v112-link92-phase-d-d1-smokes.json"
SCRIPT = ROOT / "scripts/c2-v112-link92-phase-d-d1-smokes-hw.sh"
GATES = ROOT / "mk/gates.mk"
LINK89 = ROOT / "config/c2-v14-link89-device-session.json"
TIME_CONTRACT = ROOT / "config/c2-time-contract.json"
STRINGS = ROOT / "tests/bytecode/stdlib/p0-stdlib-werkbank-subset.json"
INITIAL_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d1-smoke-preparation-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-d1-smoke-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-d1-smoke-device-receipt.json")
SPLIT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-d1-smoke-inheritance-first-red.json")
OUT = ROOT / "build/c2.3/v1.4.0-release/phase-d-split/d1-smokes"
RECORDED_ON = "2026-08-08"


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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def rows_by_id(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = value.get("rows")
    require(isinstance(rows, list), "D1 smoke rows absent")
    result = {row.get("id"): row for row in rows if isinstance(row, dict)}
    require(len(result) == len(rows), "D1 smoke row ids are not unique")
    return result


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") ==
            "lisp65-c2-v112-link92-phase-d-d1-smokes-v1",
            "D1 smoke format drift")
    require(value.get("authorization_commit") == "d528bc85",
            "D1 structural-time authorization drift")
    require(value.get("status") ==
            "owner-authorized-split-media-phase-d-restart"
            and value.get("split_restart_commit") == "a1cf5b9b",
            "D1 split-restart authorization drift")
    require(value.get("first_red_authority", {}).get("status") ==
            "first-red-d1-time-exact-zero-frame-oracle",
            "D1 time First Red authority status drift")
    require(value.get("launch_authority", {}).get("status") ==
            "passed-split-media-link92-d1-autoboot-launch-banner-and-prompt",
            "D1 launch authority status drift")
    require(value.get("candidate", {}).get("sha256") ==
            "ed4e5c7281913e351550f10533a585c2516a7a0a4214a66cf93cf35252aee306",
            "D1 candidate identity drift")
    rows = rows_by_id(value)
    require(list(rows) == ["q", "time", "strings"],
            "D1 smoke row order drift")
    require(rows["q"].get("form") == "(q->string(q*(q 1 64)(q -2 0)))"
            and rows["q"].get("expect") == '"-3.0"',
            "D1 q oracle drift")
    require(rows["strings"].get("form") ==
            '(string-trim " -" " --hi- ")'
            and rows["strings"].get("expect") == '"hi"',
            "D1 string oracle drift")
    require(rows["time"].get("form") == "(time(+ 1 2))",
            "D1 time form drift")
    require(set(rows["time"]) == {"id", "form", "oracle", "authority"},
            "D1 time row pins a measurement instead of its semantic oracle")
    require(rows["time"].get("oracle") == {
        "kind": "nonnegative-frame-count-plus-exact-result",
        "minimum_frames": 0,
        "result": "3",
    }, "D1 structural time oracle drift")
    policy = value.get("runner_policy", {})
    require(policy.get("order") == ["q", "time", "strings"],
            "D1 smoke policy order drift")
    require(policy.get("split_restart_order") == ["q", "time", "strings"]
            and policy.get("reuse_prior_q_green") is False,
            "D1 smoke split-restart order drift")
    for key in ("reuse_green_live_repl", "one_form_per_submission",
                "verified_input_before_return", "per_row_result_postcondition",
                "exact_frame_value_forbidden",
                "fail_closed_frame_check"):
        require(policy.get(key) is True, f"D1 smoke policy dimmed: {key}")
    require(policy.get("cold_reset") is False
            and policy.get("media_remount") is False,
            "D1 green live context reuse drift")
    require(policy.get("expect_poll_seconds") == 45,
            "D1 result observation budget drift")
    require(policy.get("D3_touched") is False
            and policy.get("D2_touched") is False,
            "D1 smoke scope broadened")


def smoke_order(source: str) -> str:
    begin = "# D1-SMOKE-ORDER-BEGIN"
    end = "# D1-SMOKE-ORDER-END"
    require(source.count(begin) == 1 and source.count(end) == 1,
            "D1 smoke ownership markers drift")
    return source.split(begin, 1)[1].split(end, 1)[0]


def validate_script(source: str) -> None:
    order = smoke_order(source)
    tokens = ["capture_context", "run_exact_form D1-q",
              "run_time_form D1-time-structural",
              "run_exact_form D1-strings",
              'python3 "$PY" result']
    positions = []
    for token in tokens:
        require(token in order, f"D1 smoke runner token absent: {token}")
        positions.append(order.index(token))
    require(positions == sorted(positions), "D1 smoke runner order drift")
    require(source.count("run_exact_form() (") == 1,
            "D1 exact smoke submit helper ownership drift")
    submit = source.split("run_exact_form() (", 1)[1].split("\n)\n", 1)[0]
    jtag, postcheck = submit.split("python3 tools/host-lisp/repl_screen_check.py", 1)
    for token in ("--verified-input", '--expect "$expected"',
                  "--expect-poll 45"):
        require(token in jtag, f"D1 smoke submit proof absent: {token}")
    require('--form-text "$form" --expect "$expected"' in postcheck,
            "D1 smoke independent result postcheck absent")
    require(source.count("run_time_form() (") == 1,
            "D1 structural-time submit helper ownership drift")
    time_submit = source.split("run_time_form() (", 1)[1].split("\n)\n", 1)[0]
    require("--verified-input" in time_submit
            and '--form "$form"' in time_submit
            and 'python3 "$PY" check-time' in time_submit,
            "D1 structural-time proof chain absent")
    require("--expect" not in time_submit and "0 3" not in time_submit,
            "D1 time runner pins an exact measured frame value")
    require("run_m65 -F" not in source and "mega65_ftp" not in source,
            "D1 smoke runner reboots or remounts the green identity")
    require("D3" not in order and "D2" not in order,
            "D1 smoke runner crosses into a later row")


def validate_authorities(value: dict[str, Any]) -> None:
    launch = load(ROOT / value["launch_authority"]["path"])
    require(launch.get("status") == value["launch_authority"]["status"],
            "D1 launch authority drift")
    candidate = ROOT / value["candidate"]["media"]
    require(sha(candidate) == value["candidate"]["sha256"],
            "D1 source medium drift")
    link89 = load(LINK89)["D3"]
    time_contract = load(TIME_CONTRACT).get("public_surface", {})
    rows = rows_by_id(value)
    require((rows["q"]["form"], rows["q"]["expect"]) ==
            (link89["q_form"], link89["q_expected"]),
            "D1 q hardware oracle authority drift")
    require(rows["time"]["form"] == link89["time_form"],
            "D1 time form authority drift")
    require(time_contract.get("evaluation") == "form is evaluated exactly once"
            and time_contract.get("result") ==
            "the value of form is returned unchanged"
            and time_contract.get("output") ==
            "the elapsed frame count is printed through the existing print surface",
            "D1 time semantic authority drift")
    string_cases = load(STRINGS).get("cases", [])
    case = next((item for item in string_cases
                 if item.get("name") == "string-trim"), None)
    require(case is not None
            and (rows["strings"]["form"], rows["strings"]["expect"]) ==
            (case["expr"], case["expect"]),
            "D1 string host oracle authority drift")


def rejected_mutations(value: dict[str, Any], source: str) -> list[str]:
    mutations: list[tuple[str, dict[str, Any]]] = []

    def mutate(name: str, callback: Any) -> None:
        candidate = deepcopy(value)
        callback(candidate)
        mutations.append((name, candidate))

    mutate("row-order-swapped", lambda x: x["rows"].reverse())
    mutate("q-form-drift", lambda x: x["rows"][0].update(form="(q 1 64)"))
    mutate("q-result-dimmed", lambda x: x["rows"][0].update(expect="-3"))
    mutate("time-form-drift", lambda x: x["rows"][1].update(form="(time 3)"))
    mutate("time-exact-frame-value-pinned",
           lambda x: x["rows"][1].update(expect="0 3"))
    mutate("time-result-dimmed",
           lambda x: x["rows"][1]["oracle"].update(result="0"))
    mutate("time-negative-frame-admitted",
           lambda x: x["rows"][1]["oracle"].update(minimum_frames=-1))
    mutate("string-form-drift", lambda x: x["rows"][2].update(form='"hi"'))
    mutate("string-result-dimmed", lambda x: x["rows"][2].update(expect="hi"))
    mutate("verified-input-removed",
           lambda x: x["runner_policy"].update(verified_input_before_return=False))
    mutate("multi-form-submission",
           lambda x: x["runner_policy"].update(one_form_per_submission=False))
    mutate("result-postcondition-removed",
           lambda x: x["runner_policy"].update(per_row_result_postcondition=False))
    mutate("exact-frame-pin-admitted",
           lambda x: x["runner_policy"].update(exact_frame_value_forbidden=False))
    mutate("premature-result-look",
           lambda x: x["runner_policy"].update(expect_poll_seconds=1))
    mutate("D3-crossing", lambda x: x["runner_policy"].update(D3_touched=True))
    mutate("D2-crossing", lambda x: x["runner_policy"].update(D2_touched=True))
    mutate("prior-q-session-reused",
           lambda x: x["runner_policy"].update(reuse_prior_q_green=True))
    rejected: list[str] = []
    for name, candidate in mutations:
        try:
            validate_contract(candidate)
        except GateError:
            rejected.append(name)
        else:
            raise GateError(f"contract mutation survived: {name}")

    source_mutations = {
        "source-verified-input-removed": source.replace("--verified-input", "", 1),
        "source-expect-removed": source.replace('--expect "$expected"', "", 1),
        "source-result-gate-removed": source.replace(
            '--form-text "$form" --expect "$expected"',
            '--form-text "$form"', 1),
        "source-D3-crossing": source.replace(
            'python3 "$PY" result', 'echo D3\npython3 "$PY" result', 1),
        "source-time-exact-frame-pinned": source.replace(
            '--verified-input --wait 3 --form "$form"',
            '--verified-input --wait 3 --expect "0 3" --form "$form"', 1),
        "source-time-structural-check-removed": source.replace(
            'python3 "$PY" check-time', ': # structural time check removed', 1),
    }
    before_order, owned_order = source.split("# D1-SMOKE-ORDER-BEGIN", 1)
    source_mutations["source-fresh-q-row-removed"] = (
        before_order + "# D1-SMOKE-ORDER-BEGIN" + owned_order.replace(
            'run_exact_form D1-q "$q_form" "$q_expect"',
            ': # fresh q row removed', 1))
    for name, candidate in source_mutations.items():
        try:
            validate_script(candidate)
        except GateError:
            rejected.append(name)
        else:
            raise GateError(f"source mutation survived: {name}")
    return rejected


def evaluate(*, write: bool) -> dict[str, Any]:
    value = load(CONFIG)
    validate_contract(value)
    validate_authorities(value)
    source = SCRIPT.read_text(encoding="utf-8")
    validate_script(source)
    gates = GATES.read_text(encoding="utf-8")
    require("c2-v112-phase-d-d1-smokes-selftest:" in gates
            and "c2_v112_phase_d_d1_smokes.py selftest" in gates
            and "check-source: c2-v112-phase-d-d1-smokes-selftest" in gates,
            "D1 smoke permanent gate registration drift")
    rejected = rejected_mutations(value, source)
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d1-smoke-preparation-v1",
        "recorded_on": RECORDED_ON,
        "status": "passed-split-restart-three-bound-d1-smokes-ready-on-green-live-repl",
        "rows": value["rows"],
        "bindings": {
            "config": bind(CONFIG),
            "runner": bind(SCRIPT),
            "launch_authority": bind(ROOT / value["launch_authority"]["path"]),
            "first_red_authority": bind(ROOT / value["first_red_authority"]["path"]),
            "initial_preparation": bind(INITIAL_PREP),
            "structural_time_repair": bind(ROOT / (
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-v1.12-link92-r5-phase-d-d1-smoke-structural-repair-receipt.json")),
            "split_inheritance_first_red": bind(SPLIT_FIRST_RED),
            "candidate_media": bind(ROOT / value["candidate"]["media"]),
            "q_and_time_form_authority": bind(LINK89),
            "time_semantic_authority": bind(TIME_CONTRACT),
            "string_authority": bind(STRINGS),
        },
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
        "execution_accounting": {"hardware_contacts": 0, "D1_smokes": 0,
                                 "D3_rows": 0, "D2_rows": 0},
        "claim_limit": value["claim_limit"],
    }
    if write:
        PREP.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return result


def latest_result_tokens(path: Path, form: str) -> list[str]:
    SCREEN.check_latest_result(path, form, None)
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = []
    for line in raw_lines:
        line = line.rstrip("\r")
        if len(line) == 82 and line.startswith(" ") and line.endswith(" "):
            line = line[1:-1]
        lines.append(line)
    prompts = [index for index, line in enumerate(lines)
               if line.lstrip().startswith("lisp65>")]
    require(len(prompts) >= 2, "D1 structural-time result segment absent")
    start, end = prompts[-2], prompts[-1]
    echo_rows = max(1, (len("lisp65> ") + len(form) + 79) // 80)
    visible = [line.strip() for line in lines[start + echo_rows:end]
               if line.strip()]
    require(len(visible) == 1, "D1 structural-time result is not one row")
    return visible[0].split()


def check_time_result() -> dict[str, Any]:
    value = load(CONFIG)
    validate_contract(value)
    row = rows_by_id(value)["time"]
    text = OUT / "D1-time-structural.txt"
    png = OUT / "D1-time-structural.png"
    attempt = OUT / "D1-time-structural-input-attempt-1.txt"
    SCREEN.check_active_input(attempt, row["form"])
    SCREEN.check_fail_closed_frame(png)
    tokens = latest_result_tokens(text, row["form"])
    require(len(tokens) == 2 and tokens[0].isdigit(),
            "D1 time result is not FRAME RESULT")
    frames = int(tokens[0])
    oracle = row["oracle"]
    require(frames >= oracle["minimum_frames"],
            "D1 time frame count is negative")
    require(tokens[1] == oracle["result"],
            "D1 time did not preserve the exact form result")
    return {"frames": frames, "result": tokens[1]}


def close_result() -> dict[str, Any]:
    prep = load(PREP)
    require(prep.get("status") ==
            "passed-split-restart-three-bound-d1-smokes-ready-on-green-live-repl",
            "D1 smoke preparation authority drift")
    value = load(CONFIG)
    rows = rows_by_id(value)
    bindings: dict[str, Any] = {"preparation": bind(PREP)}
    context_text = OUT / "D1-resume-context.txt"
    context_png = OUT / "D1-resume-context.png"
    context = context_text.read_text(encoding="utf-8", errors="replace")
    SCREEN.check_fail_closed_frame(context_png)
    require(value["candidate"]["banner"] in context
            and value["candidate"]["prompt"] in context,
            "D1 smoke starting context drift")
    bindings["starting_context_text"] = bind(context_text)
    bindings["starting_context_screen"] = bind(context_png)
    result_rows = []
    for name in ("q", "strings"):
        row = rows[name]
        text = OUT / f"D1-{name}.txt"
        png = OUT / f"D1-{name}.png"
        SCREEN.check_latest_result(text, row["form"], row["expect"])
        SCREEN.check_fail_closed_frame(png)
        attempt = OUT / f"D1-{name}-input-attempt-1.txt"
        SCREEN.check_active_input(attempt, row["form"])
        result_rows.append({"id": name, "form": row["form"],
                            "expect": row["expect"], "status": "passed",
                            "input_echo": bind(attempt),
                            "result_text": bind(text), "result_screen": bind(png)})
    time_row = rows["time"]
    time_result = check_time_result()
    result_rows.insert(1, {
        "id": "time", "form": time_row["form"],
        "oracle": time_row["oracle"], "observed": time_result,
        "status": "passed-structural",
        "input_echo": bind(OUT / "D1-time-structural-input-attempt-1.txt"),
        "result_text": bind(OUT / "D1-time-structural.txt"),
        "result_screen": bind(OUT / "D1-time-structural.png"),
    })
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d1-smoke-device-v1",
        "recorded_on": RECORDED_ON,
        "status": "passed-split-media-link92-d1-q-time-string-smokes",
        "rows": result_rows,
        "bindings": bindings,
        "execution_accounting": {"hardware_contacts_this_split_session": 1,
                                 "D1_smokes": 3,
                                 "D3_rows": 0, "D2_rows": 0,
                                 "product_rebuilds": 0, "media_rebuilds": 0,
                                 "additional_links": 0},
        "disposition": {"D1": "green", "next": "D3 comfort and physical editor row",
                        "D3": "not_started", "D2": "not_started"},
        "claim_limit": value["claim_limit"],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare", "selftest",
                                           "check-time", "result"))
    args = parser.parse_args()
    try:
        if args.action == "check-time":
            value = check_time_result()
            print("c2-v112-phase-d-d1-smokes: PASS structural-time "
                  f"frames={value['frames']} result={value['result']}")
        elif args.action == "result":
            value = close_result()
            print(f"c2-v112-phase-d-d1-smokes: PASS {value['status']}")
        else:
            value = evaluate(write=args.action == "prepare")
            print("c2-v112-phase-d-d1-smokes: PASS "
                  f"rows=3 mutations={value['mutation_count']}")
        return 0
    except (GateError, SCREEN.CheckError, OSError, json.JSONDecodeError) as error:
        print(f"c2-v112-phase-d-d1-smokes: FIRST RED: "
              f"{getattr(error, 'message', str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
