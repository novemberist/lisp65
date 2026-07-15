#!/usr/bin/env python3
"""Black-box self-test for the verified JTAG REPL input retry contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
JTAG_REPL = ROOT / "scripts" / "hw-jtag-repl.sh"
FORM = "(+ 20 22)"
CORRUPTED_FORM = "(+20 22)"
ORACLE_FORM = '(if t "expected-marker" "wrong")'
ORACLE_EXPECT = '"expected-marker"'


FAKE_M65 = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import signal
import sys
import time


def load_state(path):
    if path.exists():
        return json.loads(path.read_text())
    return {"active": "", "attempts": 0, "events": [], "executions": []}


def save_state(path, state):
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def corrupt(form):
    position = form.find(" ")
    if position < 0:
        raise SystemExit("fake m65 needs a form containing a space")
    return form[:position] + form[position + 1:]


args = sys.argv[1:]
state_path = Path(os.environ["FAKE_M65_STATE"])
expected_form = os.environ["FAKE_M65_FORM"]
mode = os.environ["FAKE_M65_MODE"]
state = load_state(state_path)

screenshot = next((arg.split("=", 1)[1] for arg in args if arg.startswith("--screenshot=")), None)
if screenshot is not None:
    Path(screenshot).write_bytes(b"fake screenshot\n")
    state["events"].append({"kind": "capture", "active": state["active"]})
    save_state(state_path, state)
    if mode == "capture_failure":
        raise SystemExit(42)
    if mode == "active_stale_basic" and state["active"]:
        rows = [
            "lisp65> " + state["active"],
            "ready.",
            state["active"],
            "?syntax error",
            "ready.",
        ]
    elif state["active"]:
        rows = ["lisp65> " + state["active"]]
    elif mode == "oracle_pass":
        rows = [
            "lisp65> " + state["executions"][-1],
            os.environ["FAKE_M65_EXPECT"],
            "lisp65>",
        ]
    elif mode == "oracle_delayed":
        result_captures = sum(
            1 for event in state["events"]
            if event["kind"] == "capture" and not event["active"]
        )
        if result_captures >= 3:
            rows = [
                "lisp65> " + state["executions"][-1],
                os.environ["FAKE_M65_EXPECT"],
                "lisp65>",
            ]
        else:
            rows = ["lisp65> " + state["executions"][-1]]
    elif mode in {"oracle_echo_only", "oracle_poll_timeout"}:
        rows = ["lisp65> " + state["executions"][-1], '"wrong-result"', "lisp65>"]
    elif mode == "oracle_basic":
        rows = ["ready.", state["executions"][-1], "", "?syntax error", "ready."]
    elif mode == "oracle_stale_basic":
        rows = [
            "lisp65> " + state["executions"][-1],
            os.environ["FAKE_M65_EXPECT"],
            "lisp65>",
            "ready.",
            state["executions"][-1],
            "?syntax error",
            "ready.",
        ]
    else:
        rows = ["lisp65>"]
    for row in rows:
        print(f" {row:<80.80} ")
    raise SystemExit(0)

if "-t" not in args:
    state["events"].append({"kind": "unexpected", "args": args})
    save_state(state_path, state)
    raise SystemExit(64)

position = args.index("-t")
if position + 1 >= len(args):
    raise SystemExit(64)
payload = args[position + 1]

if payload == "~M":
    if mode == "return_failure":
        state["events"].append({"kind": "return_failure", "active": state["active"]})
        save_state(state_path, state)
        raise SystemExit(44)
    state["events"].append({"kind": "submit", "active": state["active"]})
    state["executions"].append(state["active"])
    state["active"] = ""
elif payload and payload.replace("~T", "") == "":
    state["events"].append(
        {"kind": "clear", "before": state["active"], "key_count": len(payload) // 2}
    )
    if mode == "clear_failure":
        save_state(state_path, state)
        raise SystemExit(43)
    if mode == "partial_clear":
        state["active"] = state["active"][:-1]
    else:
        state["active"] = ""
else:
    state["attempts"] += 1
    attempt = state["attempts"]
    prior = state["active"]
    should_corrupt = mode in {"always_corrupt", "clear_failure", "partial_clear"} or (
        mode == "first_corrupt" and attempt == 1
    )
    if mode == "type_failure":
        should_corrupt = True
    typed = corrupt(payload) if should_corrupt else payload
    state["active"] += typed
    state["events"].append(
        {
            "kind": "type",
            "attempt": attempt,
            "payload": payload,
            "prior": prior,
            "active": state["active"],
        }
    )
    if payload != expected_form:
        save_state(state_path, state)
        raise SystemExit(65)
    if mode == "type_failure":
        save_state(state_path, state)
        raise SystemExit(41)
    if mode == "type_hang":
        save_state(state_path, state)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(1)

save_state(state_path, state)
raise SystemExit(0)
'''


def require(
    condition: bool,
    message: str,
    result: subprocess.CompletedProcess[str] | None = None,
) -> None:
    if condition:
        return
    detail = ""
    if result is not None:
        detail = f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    raise AssertionError(message + detail)


def events_of(state: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [event for event in state.get("events", []) if event.get("kind") == kind]


def run_case(
    tmp: Path,
    mode: str,
    *,
    timeout_sec: int = 2,
    kill_after_sec: int = 2,
    form: str = FORM,
    readback: bool = False,
    expect: str | None = None,
    expect_poll: int | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    case_dir = tmp / mode
    tools_dir = case_dir / "tools"
    out_dir = case_dir / "out"
    state_path = case_dir / "state.json"
    tools_dir.mkdir(parents=True)
    fake_m65 = tools_dir / "m65"
    fake_m65.write_text(FAKE_M65)
    fake_m65.chmod(fake_m65.stat().st_mode | stat.S_IXUSR)

    command = [
        "sh",
        str(JTAG_REPL),
        "--tools",
        str(tools_dir),
        "--device",
        "fake-jtag",
        "--out-dir",
        str(out_dir),
        "--prefix",
        "probe",
        "--timeout",
        str(timeout_sec),
        "--timeout-kill-after",
        str(kill_after_sec),
        "--form-wait",
        "0",
        "--input-retry-wait",
        "0",
        "--verified-input",
    ]
    if readback:
        if expect is None:
            raise ValueError("readback case requires expect")
        command.extend(["--wait", "0", "--expect", expect])
        if expect_poll is not None:
            command.extend(["--expect-poll", str(expect_poll)])
    else:
        command.append("--no-readback")
    command.extend(["--form", form])
    env = os.environ.copy()
    env.update(
        {
            "FAKE_M65_STATE": str(state_path),
            "FAKE_M65_FORM": form,
            "FAKE_M65_MODE": mode,
            "FAKE_M65_EXPECT": expect or "",
        }
    )
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    return result, state


def check_retry_success(tmp: Path) -> None:
    result, state = run_case(tmp, "first_corrupt")
    require(result.returncode == 0, "one corrupt input must be retried successfully", result)

    typed = events_of(state, "type")
    captures = events_of(state, "capture")
    clears = events_of(state, "clear")
    submits = events_of(state, "submit")
    require(len(typed) == 2, "retry case must type exactly twice", result)
    require(
        [event["payload"] for event in typed] == [FORM, FORM],
        "each -t must contain the complete form",
        result,
    )
    require(
        [event["prior"] for event in typed] == ["", ""],
        "INST/DEL must empty the input before retry",
        result,
    )
    require(
        [event["active"] for event in typed] == [CORRUPTED_FORM, FORM],
        "fake input corruption model drifted",
        result,
    )
    require(
        [event["active"] for event in captures] == [CORRUPTED_FORM, "", FORM],
        "each attempt and the cleared prompt need active-input evidence",
        result,
    )
    require(
        len(clears) == 1 and clears[0]["before"] == CORRUPTED_FORM,
        "corrupt input must be cleared once",
        result,
    )
    require(
        len(submits) == 1 and submits[0]["active"] == FORM,
        "only the exact retry may be submitted",
        result,
    )
    require(state.get("executions") == [FORM], "only the exact retry may execute", result)
    require("active form echo differs" in result.stdout, "the corrupt active capture must report its mismatch", result)
    require("nicht ausgefuehrte Eingabe wird verworfen" in result.stderr, "retry warning is missing", result)


def check_retry_exhaustion(tmp: Path) -> None:
    result, state = run_case(tmp, "always_corrupt")
    require(result.returncode == 5, "three corrupt inputs must retain echo-mismatch status 5", result)

    typed = events_of(state, "type")
    captures = events_of(state, "capture")
    clears = events_of(state, "clear")
    require(len(typed) == 3, "exhaustion case must type exactly three times", result)
    require(
        [event["payload"] for event in typed] == [FORM] * 3,
        "every retry must send one complete form",
        result,
    )
    require(
        [event["prior"] for event in typed] == ["", "", ""],
        "each bounded retry must start empty",
        result,
    )
    require(
        [event["active"] for event in captures] == [CORRUPTED_FORM, ""] * 3,
        "all corrupt attempts and cleared prompts need evidence",
        result,
    )
    require(
        len(clears) == 3 and state.get("active") == "",
        "every rejected input, including the final attempt, must be cleared",
        result,
    )
    require(not events_of(state, "submit"), "exhausted retries must never send ~M", result)
    require(state.get("executions") == [], "exhausted retries must execute nothing", result)


def check_first_pass(tmp: Path) -> None:
    result, state = run_case(tmp, "pass")
    require(result.returncode == 0, "exact first input must pass", result)
    require(len(events_of(state, "type")) == 1, "first pass must type once", result)
    require(len(events_of(state, "capture")) == 1, "first pass needs one capture", result)
    require(state.get("executions") == [FORM], "first pass must execute the exact form", result)


def check_failure_paths(tmp: Path) -> None:
    result, state = run_case(tmp, "type_failure")
    require(result.returncode == 41, "type failure status must propagate", result)
    require(state.get("active") == "", "type failure cleanup must prove an empty prompt", result)
    require(not events_of(state, "submit"), "type failure must not submit", result)

    result, state = run_case(tmp, "capture_failure")
    require(result.returncode == 42, "capture failure status must propagate", result)
    require(state.get("active") == "", "capture failure cleanup must clear active input", result)
    require(not events_of(state, "submit"), "capture failure must not submit", result)

    result, state = run_case(tmp, "clear_failure")
    require(result.returncode == 43, "clear failure status must propagate", result)
    require(state.get("active") == CORRUPTED_FORM, "failed clear must remain observable", result)
    require(not events_of(state, "submit"), "clear failure must not submit", result)

    result, state = run_case(tmp, "partial_clear")
    require(result.returncode == 5, "partial clear must fail its empty-prompt check", result)
    require(state.get("active"), "partial clear must remain observable", result)
    require(not events_of(state, "submit"), "partial clear must not submit", result)

    result, state = run_case(tmp, "return_failure")
    require(result.returncode == 44, "RETURN failure status must propagate", result)
    require(len(events_of(state, "return_failure")) == 1, "RETURN failure must be logged", result)
    require(state.get("executions") == [], "failed RETURN must not fake execution", result)

    result, state = run_case(tmp, "active_stale_basic")
    require(result.returncode == 6, "BASIC content after a stale active prompt must fail", result)
    require(not events_of(state, "submit"), "stale active prompt must not submit", result)


def check_hard_timeout(tmp: Path) -> None:
    result, state = run_case(tmp, "type_hang", timeout_sec=1, kill_after_sec=1)
    require(result.returncode in {124, 137}, "hard timeout status must propagate", result)
    require(state.get("active") == "", "timed-out input must be cleared when transport recovers", result)
    require(not events_of(state, "submit"), "timed-out input must not submit", result)


def check_unsafe_forms_rejected(tmp: Path) -> None:
    for mode, form in (("tilde_rejected", "(progn ~M nil)"), ("cr_rejected", "(+ 20 22)\r")):
        result, state = run_case(tmp, mode, form=form)
        require(result.returncode == 2, f"unsafe form {mode} must be rejected", result)
        require(state == {}, f"unsafe form {mode} must not invoke m65", result)


def check_result_oracle(tmp: Path) -> None:
    result, state = run_case(
        tmp,
        "oracle_pass",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
    )
    require(result.returncode == 0, "exact latest REPL result must pass", result)
    require(state.get("executions") == [ORACLE_FORM], "passing oracle must execute once", result)

    result, state = run_case(
        tmp,
        "oracle_echo_only",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
    )
    require(result.returncode == 4, "marker present only in form echo must fail", result)
    require("latest result is not exactly" in result.stdout, "echo-only mismatch must be explicit", result)
    require(state.get("executions") == [ORACLE_FORM], "echo-only oracle must execute once", result)

    result, state = run_case(
        tmp,
        "oracle_basic",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
    )
    require(result.returncode == 6, "BASIC ready/syntax-error echo must fail closed", result)
    require("REPL form/result segment is not visible" in result.stdout, "BASIC rejection must be explicit", result)
    require(state.get("executions") == [ORACLE_FORM], "BASIC oracle must record one submission", result)

    result, state = run_case(
        tmp,
        "oracle_stale_basic",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
    )
    require(result.returncode == 6, "BASIC content after a stale result must fail closed", result)
    require("follows the trailing REPL prompt" in result.stdout, "stale BASIC rejection must be explicit", result)
    require(state.get("executions") == [ORACLE_FORM], "stale BASIC oracle must record one submission", result)


def check_polled_result_oracle(tmp: Path) -> None:
    result, state = run_case(
        tmp,
        "oracle_delayed",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
        expect_poll=5,
    )
    require(result.returncode == 0, "delayed exact result must pass polling", result)
    timing = json.loads((tmp / "oracle_delayed" / "out" / "probe-timing.json").read_text())
    require(timing["status"] == "pass", "passing poll must write pass timing", result)
    require(timing["elapsed_seconds"] <= 5, "passing poll must meet its budget", result)
    require(
        len([event for event in events_of(state, "capture") if not event["active"]]) == 3,
        "delayed oracle must poll until the third result capture",
        result,
    )

    result, _ = run_case(
        tmp,
        "oracle_poll_timeout",
        form=ORACLE_FORM,
        readback=True,
        expect=ORACLE_EXPECT,
        expect_poll=2,
    )
    require(result.returncode == 4, "poll timeout must retain exact-oracle failure", result)
    timing = json.loads((tmp / "oracle_poll_timeout" / "out" / "probe-timing.json").read_text())
    require(timing["status"] == "fail", "failed poll must write fail timing", result)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lisp65-hw-jtag-repl-") as raw_tmp:
        tmp = Path(raw_tmp)
        check_first_pass(tmp)
        check_retry_success(tmp)
        check_retry_exhaustion(tmp)
        check_failure_paths(tmp)
        check_hard_timeout(tmp)
        check_unsafe_forms_rejected(tmp)
        check_result_oracle(tmp)
        check_polled_result_oracle(tmp)
    print("hw-jtag-repl harness selftest: PASS (18 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
