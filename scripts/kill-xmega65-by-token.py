#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def is_emulator_process(pid):
    proc = Path("/proc") / str(pid)
    try:
        comm = (proc / "comm").read_text(encoding="utf-8").strip()
    except OSError:
        comm = ""
    if comm in {"xmega65", "podman"}:
        return True

    try:
        cmdline = (proc / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    if not cmdline or not cmdline[0]:
        return False
    return Path(cmdline[0].decode("utf-8", "ignore")).name in {"xmega65", "podman"}


def process_text(pid):
    try:
        raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "ignore")


def selftest():
    token = f"lisp65-cleanup-selftest-{os.getpid()}"
    control_token = f"lisp65-cleanup-control-{os.getpid()}"
    code = "import time; time.sleep(60)"
    target = subprocess.Popen(["bash", "-c", f"exec -a podman python3 -c '{code}' {token}"])
    control = subprocess.Popen(["bash", "-c", f"exec -a podman python3 -c '{code}' {control_token}"])
    try:
        for _ in range(50):
            if token in process_text(target.pid) and control_token in process_text(control.pid):
                break
            time.sleep(0.01)
        env = os.environ.copy()
        env["XMEGA65_CLEANUP_GRACE"] = "0.05"
        result = subprocess.run(
            [sys.executable, __file__, token], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode or target.poll() is None or control.poll() is not None:
            raise SystemExit("cleanup selftest failed")
    finally:
        for child in (target, control):
            if child.poll() is None:
                child.kill()
            child.wait()
    print("xmega65 token cleanup selftest: PASS wrapper-targeted control-preserved")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
        return
    if len(sys.argv) != 2:
        raise SystemExit("usage: kill-xmega65-by-token.py TOKEN")
    token = sys.argv[1]
    own_pid = os.getpid()
    matched = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == own_pid or not is_emulator_process(pid):
            continue
        if token not in process_text(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            matched.append(pid)
        except ProcessLookupError:
            pass
    if not matched:
        return

    grace = float(os.environ.get("XMEGA65_CLEANUP_GRACE", "2"))
    if grace > 0:
        time.sleep(grace)

    sigkilled = 0
    for pid in matched:
        if token not in process_text(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            sigkilled += 1
        except ProcessLookupError:
            pass
    print(
        "killed %d emulator/wrapper process(es) matching %s%s"
        % (len(matched), token, " (SIGKILL=%d)" % sigkilled if sigkilled else "")
    )


if __name__ == "__main__":
    main()
