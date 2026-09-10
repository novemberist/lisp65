#!/usr/bin/env python3
"""Build and execute DWX Item-4 rows without desktop-focus input."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v200_comfort_return_final_composition as COMFORT  # noqa: E402
import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402
import evidence_era as ERA


CONTRACT_PATH = ROOT / "config/dwx-mirrored-prefilter-rows-contract.json"
ADAPTER_CONTRACT_PATH = ROOT / "config/dwx-headless-input-adapter-contract.json"
BLIND_CONTRACT_PATH = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
RECEIPT_PATH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "dwx-mirrored-prefilter-rows-receipt-20260902.json"
)
REPORT_PATH = ROOT / "docs/planning/dwx-mirrored-prefilter-rows-report.md"
WORK_PLAN_PATH = ROOT / "docs/planning/dwx-delivered-world-executor-work-plan.md"
SAFE_RUNNER = ROOT / "scripts/xmega65-safe-run.sh"
SEALED_ITEM4_DEVICE_ROWS = list(BLIND.BLIND_IDS[:4])
SEALED_ITEM4_BLIND_BINDING = {
    "path": "config/dwx-prefilter-blind-spot-contract.json",
    "bytes": 3535,
    "sha256": "01b86f775ff799c2e09d6a4918794ae5205a5efc451bea05170377552ba30fd9",
}
SEALED_ITEM4_EXECUTOR_BINDING = {
    "path": "tools/host-lisp/dwx_mirrored_prefilter_rows.py",
    "bytes": 38062,
    "sha256": "ac930170060ff7f57b17e176e2a8cbe8507ec35aa7d958b5a340a7be86239f97",
}

ACTIVE_IDS = (
    "boot-surface-without-libraries",
    "tier1-documented-domain-error",
    "library-require-over-packed-medium",
    "init-l65-absent",
    "init-l65-valid",
    "init-l65-broken",
    "composed-native-prompt-and-cursor",
    "capture-counters-at-stopped-point",
)
DEFERRED_ID = "matcher-and-blink-visibility"
ORACLE_TYPES = {"framebuffer", "stopped-memory"}


class RowError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RowError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RowError(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def decoded_framebuffer(text: str) -> str:
    return re.sub(r"\{([A-Za-z0-9])\}", r"\1", text).upper()


def framebuffer_oracle(text: str, oracle: dict[str, Any]) -> dict[str, Any]:
    decoded = decoded_framebuffer(text)
    lines = [line.strip() for line in decoded.splitlines()]
    required = [str(item).upper() for item in oracle.get("required", [])]
    forbidden = [str(item).upper() for item in oracle.get("forbidden", [])]
    exact = [str(item).upper() for item in oracle.get("required_exact_lines", [])]
    same = [str(item).upper() for item in oracle.get("required_same_line", [])]
    missing = [item for item in required if item not in decoded]
    present_forbidden = [item for item in forbidden if item in decoded]
    missing_exact = [item for item in exact if item not in lines]
    matching_lines = [line for line in lines if same and all(item in line for item in same)]
    expected_line_count = oracle.get("required_line_count")
    same_line_failed = bool(same) and (
        not matching_lines
        or (expected_line_count is not None and len(matching_lines) != expected_line_count)
    )
    return {
        "type": "framebuffer",
        "passed": not missing and not present_forbidden and not missing_exact and not same_line_failed,
        "required": required,
        "missing": missing,
        "required_exact_lines": exact,
        "missing_exact_lines": missing_exact,
        "required_same_line": same,
        "matching_lines": matching_lines,
        "forbidden": forbidden,
        "present_forbidden": present_forbidden,
    }


def resolve_device_counterpart(value: str) -> None:
    require("#" in value, f"device counterpart has no row fragment: {value}")
    relative, row_id = value.rsplit("#", 1)
    path = ROOT / relative
    data = load(path)
    rows = data.get("rows")
    require(isinstance(rows, list), f"device binding has no rows: {relative}")
    require(
        sum(1 for row in rows if row.get("id") == row_id) == 1,
        f"device counterpart is not an exact row: {value}",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-mirrored-prefilter-rows-contract-v1"
        and contract.get("status") == "ACTIVE"
        and contract.get("evidence_class") == "xemu-prefilter-green",
        "mirrored-row contract header drift",
    )
    require(
        contract.get("authority_rule")
        == "A prefilter row exists only when it names its physical-device counterpart and uses a framebuffer or stopped-memory oracle; logs are never authority.",
        "mirrored-row authority rule drift",
    )
    policy = contract.get("runtime_policy")
    require(
        policy
        == {
            "headless": True,
            "desktop_focus_input": False,
            "input_transport": "local-unix-uart-monitor-to-HWA-queue",
            "screen_queries_are_control_only": True,
            "logs_are_oracle": False,
            "fresh_process_per_runtime_row": True,
            "device_acceptance_claimed": False,
        },
        "headless runtime policy drift",
    )
    rows = contract.get("rows")
    require(isinstance(rows, list), "mirrored row population absent")
    active = tuple(row.get("id") for row in rows if row.get("state") == "ACTIVE")
    deferred = tuple(row.get("id") for row in rows if row.get("state") != "ACTIVE")
    require(active == ACTIVE_IDS and deferred == (DEFERRED_ID,), "mirrored row population drift")
    for row in rows:
        counterpart = row.get("device_counterpart")
        require(isinstance(counterpart, str) and counterpart, f"{row.get('id')} lost device counterpart")
        resolve_device_counterpart(counterpart)
        oracle = row.get("oracle")
        require(isinstance(oracle, dict), f"{row.get('id')} lost oracle")
        require(
            oracle.get("type") in ORACLE_TYPES,
            f"{row.get('id')} uses a log or unknown oracle",
        )
    matcher = next(row for row in rows if row["id"] == DEFERRED_ID)
    require(
        matcher.get("state") == "DEFERRED_UNTIL_FREIGHT_RETURNS"
        and matcher.get("execution") == "not-a-prefilter-row-yet",
        "matcher/blink was claimed before its freight returned",
    )
    require_row = next(row for row in rows if row["id"] == "library-require-over-packed-medium")
    require(
        require_row.get("medium") == "product-plus-packed-library"
        and require_row.get("input") == "(require 'repl-comfort)\n",
        "runtime require lost its packed-medium seam",
    )
    counters = next(row for row in rows if row["id"] == "capture-counters-at-stopped-point")
    oracle = counters["oracle"]
    require(
        counters.get("execution") == "headless-HWA-input-then-CPU-stop"
        and oracle.get("type") == "stopped-memory"
        and oracle.get("address") == "0xBCFC"
        and oracle.get("bytes") == 4
        and oracle.get("names") == ["raw", "seen", "stored", "taken"]
        and oracle.get("relation") == "raw == seen == stored == taken != 0",
        "capture row lost the stopped-state four-counter oracle",
    )
    stimulus = counters.get("stimulus", {})
    require(
        stimulus.get("control_marker") == "9"
        and "(print 9)" in stimulus.get("controller", "")
        and stimulus.get("expected_device_modulo_count") == 136,
        "capture row lost its product-lifecycle synchronization",
    )


def mutations(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    value = deepcopy(contract)
    value["runtime_policy"]["desktop_focus_input"] = True
    result["desktop-focus-input-reintroduced"] = value
    value = deepcopy(contract)
    value["runtime_policy"]["headless"] = False
    result["GUI-runtime-reintroduced"] = value
    value = deepcopy(contract)
    value["runtime_policy"]["logs_are_oracle"] = True
    result["log-promoted-to-oracle"] = value
    value = deepcopy(contract)
    del value["rows"][1]["device_counterpart"]
    result["device-counterpart-omitted"] = value
    value = deepcopy(contract)
    value["rows"][1]["oracle"]["type"] = "log"
    result["tier1-log-oracle"] = value
    value = deepcopy(contract)
    value["rows"][2]["medium"] = "product"
    result["require-no-longer-uses-packed-medium"] = value
    value = deepcopy(contract)
    value["rows"][7]["state"] = "ACTIVE"
    result["matcher-claimed-before-return"] = value
    value = deepcopy(contract)
    value["rows"][8]["execution"] = "headless-HWA-input"
    result["counter-read-not-at-stopped-point"] = value
    value = deepcopy(contract)
    value["rows"][8]["oracle"]["relation"] = "raw == seen == stored"
    result["taken-counter-omitted"] = value
    value = deepcopy(contract)
    value["rows"].pop(2)
    result["ported-row-omitted"] = value
    return result


def mutation_names(contract: dict[str, Any]) -> list[str]:
    names = []
    for name, value in mutations(contract).items():
        try:
            validate_contract(value)
        except RowError:
            names.append(name)
            continue
        raise RowError(f"mirrored-row mutation survived: {name}")
    return sorted(names)


def histogram_transport_selftest() -> None:
    """Execute delayed/partial replies and the former short-timeout mutation."""
    import inspect
    import tempfile
    import textwrap
    import threading

    source = textwrap.dedent(inspect.getsource(Monitor.command))
    needle = 'histogram = command == "~pcsave"'
    require(source.count(needle) == 1, "histogram mutation anchor drift")
    namespace = dict(Monitor.command.__globals__)
    exec(source.replace(needle, 'histogram = False'), namespace)
    old_timeout = namespace['command']
    for name, invoke, reply, expected in (
        ('delayed-complete', Monitor.command, b'DWX PC save: 0\n.\r\n', True),
        ('short-timeout-mutant', old_timeout, b'DWX PC save: 0\n.\r\n', False),
        ('truncated-response', Monitor.command, b'DWX PC save: 0', False),
        ('failed-save', Monitor.command, b'DWX PC save: -1\n.\r\n', False),
    ):
        with tempfile.TemporaryDirectory(prefix='dwx-histogram-') as directory:
            path = Path(directory) / 'monitor.sock'
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(path))
            server.listen(1)
            errors: list[Exception] = []

            def serve() -> None:
                try:
                    client, _ = server.accept()
                    with client:
                        require(client.recv(100) == b'~pcsave\r', 'wrong test request')
                        time.sleep(0.75)
                        try:
                            client.sendall(reply)
                        except BrokenPipeError:
                            require(name == 'short-timeout-mutant', 'unexpected broken pipe')
                except Exception as error:
                    errors.append(error)
                finally:
                    server.close()

            worker = threading.Thread(target=serve)
            worker.start()
            try:
                answer = invoke(Monitor(path), '~pcsave', timeout=0.6)
                accepted = 'DWX PC save: 0\n' in answer and '\n.\r\n' in answer
            except RowError:
                accepted = False
            finally:
                worker.join(timeout=5)
            require(not worker.is_alive() and not errors, f'transport harness failed: {errors}')
            require(accepted == expected, f'histogram transport control failed: {name}')


def breakpoint_transport_selftest() -> list[str]:
    """Real Unix-socket peer: asynchronous report after the first reply.

    Only the isolated child restores default SIGPIPE. The qualifying Xemu
    process never suppresses a signal; early client close kills this child.
    """
    import multiprocessing
    import signal
    import tempfile
    context = multiprocessing.get_context('fork')
    controls = []
    for early_close in (False, True):
        with tempfile.TemporaryDirectory(prefix='dwx-breakpoint-') as directory:
            path = Path(directory) / 'monitor.sock'
            ready, release = context.Event(), context.Event()
            def peer():
                signal.signal(signal.SIGPIPE, signal.SIG_DFL)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(path)); server.listen(1); ready.set()
                    client, _ = server.accept()
                    with client:
                        client.settimeout(3)
                        require(client.recv(100) == b'b ff09\r', 'fixture arm command')
                        client.sendall(b'b ff09\r\n.\r\n')
                        require(release.wait(3), 'fixture release timeout')
                        client.sendall(b'\r\nPC SP\r\nFF09 01CC\r\n')
                        require(client.recv(100) == b'r\r', 'fixture register command')
                        client.sendall(b'r\r\nFF0A 01CC\r\n.\r\n')
                        require(client.recv(100) == b'~pcclearbreak\r', 'fixture disarm command')
                        client.sendall(b'DWX PC breakpoint cleared\n.\r\n')
                        require(client.recv(1) == b'', 'connection not released after clear')
            process = context.Process(target=peer)
            process.start()
            try:
                require(ready.wait(3), 'fixture listener timeout')
                monitor = Monitor(path)
                if not early_close:
                    monitor.begin_breakpoint_connection()
                monitor.command('b ff09')
                release.set()
                if not early_close:
                    response = monitor.command('r')
                    require('FF09 01CC' in response and 'FF0A 01CC' in response,
                            'asynchronous report or command reply lost')
                    # Also exercises failure-cleanup's mandatory disarm.
                    monitor.end_breakpoint_connection()
                process.join(4)
                require(process.exitcode == (-signal.SIGPIPE if early_close else 0),
                        f'breakpoint lifetime control failed: {process.exitcode}')
            finally:
                if process.is_alive(): process.terminate(); process.join(2)
            controls.append('early-close-SIGPIPE' if early_close else 'held-until-disarm')
    return controls


def owned_readiness(function):
    """Hold the transport, without changing readiness or guest-cycle oracles."""
    from functools import wraps
    @wraps(function)
    def run(self, *args, **kwargs):
        self.begin_breakpoint_connection()
        try:
            return function(self, *args, **kwargs)
        finally:
            self.end_breakpoint_connection()
    return run


class Monitor:
    def __init__(self, path: Path):
        self.path = path

    def begin_breakpoint_connection(self, timeout: float = 3.0) -> None:
        """Own one socket before arming, until acknowledged breakpoint clear."""
        require(getattr(self, '_breakpoint_socket', None) is None, 'nested monitor connection')
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(timeout)
        try:
            client.connect(str(self.path))
        except BaseException:
            client.close()
            raise
        self._breakpoint_socket = client
        self._breakpoint_cleared = False
        self._breakpoint_pending = b''

    def end_breakpoint_connection(self) -> None:
        client = getattr(self, '_breakpoint_socket', None)
        require(client is not None, 'no owned monitor connection')
        # On failed readiness, disarm on the still-owned connection too.
        try:
            if not self._breakpoint_cleared:
                require('DWX PC breakpoint cleared' in self.command('~pcclearbreak'),
                        'breakpoint disarm not acknowledged')
        finally:
            self._breakpoint_socket = None
            client.close()

    def _breakpoint_command(self, command: str, timeout: float) -> str:
        client = self._breakpoint_socket
        deadline = time.monotonic() + timeout
        client.settimeout(timeout)
        client.sendall(command.encode('ascii') + b'\r')
        chunks = [self._breakpoint_pending]
        self._breakpoint_pending = b''
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'owned monitor response deadline')
            client.settimeout(remaining)
            block = client.recv(16384)
            require(bool(block), 'owned monitor response incomplete')
            chunks.append(block)
            raw = b''.join(chunks)
            if b'\n.\r\n' in raw:
                end = raw.index(b'\n.\r\n') + len(b'\n.\r\n')
                self._breakpoint_pending = raw[end:]
                response = raw[:end].decode('utf-8', errors='replace')
                if command == '~pcclearbreak':
                    require('DWX PC breakpoint cleared' in response, 'missing clear acknowledgement')
                    self._breakpoint_cleared = True
                return response

    def command(self, command: str, timeout: float = 3.0) -> str:
        # A stopped-CPU histogram dump can take longer than an ordinary UART
        # reply. Closing its socket after 0.5 s caused host SIGPIPE in Xemu.
        # This is a transport deadline, never a guest measurement exclusion.
        histogram = command == "~pcsave"
        if histogram:
            timeout = max(timeout, 30.0)
        if getattr(self, '_breakpoint_socket', None) is not None:
            return self._breakpoint_command(command, timeout)
        deadline = time.monotonic() + timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(0.5)
            try:
                client.connect(str(self.path))
                client.sendall(command.encode("ascii") + b"\r")
                chunks: list[bytes] = []
                while True:
                    if histogram:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("PC histogram response deadline")
                        client.settimeout(remaining)
                    block = client.recv(16384)
                    if not block:
                        break
                    chunks.append(block)
                    if b"\n.\r\n" in b"".join(chunks):
                        break
                response = b"".join(chunks).decode("utf-8", errors="replace")
                if histogram:
                    require("\n.\r\n" in response,
                            "PC histogram response incomplete")
                return response
            except OSError as error:
                last_error = error
                time.sleep(0.02)
            finally:
                client.close()
        raise RowError(f"UART monitor command failed: {command}: {last_error}")

    def screen(self) -> str:
        response = self.command("~screen")
        require("\n.\r\n" in response, "screen monitor response incomplete")
        body = response.split("\n", 1)[1].rsplit("\n.\r\n", 1)[0]
        return body

    def wait_screen(self, required: list[str], timeout: float = 12.0) -> str:
        deadline = time.monotonic() + timeout
        last = ""
        folded = [item.upper() for item in required]
        while time.monotonic() < deadline:
            last = self.screen()
            decoded = decoded_framebuffer(last)
            if all(item in decoded for item in folded):
                return last
            time.sleep(0.03)
        raise RowError(f"framebuffer control trigger timed out: {required}; last={last[-300:]}")

    def type_text(self, text: str) -> None:
        response = self.command("~typehex " + text.encode("ascii").hex())
        require("DWX HWA input queued" in response, "HWA input was not queued")
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            status = self.command("~typebusy")
            if "DWX HWA input busy: 0" in status:
                return
            time.sleep(0.02)
        raise RowError("HWA input did not drain")

    def memory16(self, address: int) -> bytes:
        response = self.command(f"m {address:08x}")
        match = re.search(r":[0-9A-Fa-f]{8}:([0-9A-Fa-f]{32})", response)
        require(match is not None, f"memory response malformed at {address:08x}")
        return bytes.fromhex(match.group(1))

    def wait_counter_value(self, expected: int, timeout: float = 12.0) -> bytes:
        deadline = time.monotonic() + timeout
        last = b""
        while time.monotonic() < deadline:
            last = self.memory16(0xBCFC)[:4]
            if last == bytes([expected]) * 4:
                return last
            time.sleep(0.02)
        raise RowError(
            f"capture counters did not converge to {expected:02x}: {last.hex()}"
        )

    def type_and_wait_counters(self, text: str, current: int) -> int:
        expected = (current + len(text)) & 0xFF
        self.type_text(text)
        self.wait_counter_value(expected)
        return expected


def verify_sha(path: Path, expected: str, role: str) -> None:
    require(path.is_file() and sha256(path) == expected, f"{role} SHA drift")


def create_packed_medium(contract: dict[str, Any], output: Path) -> Path:
    inputs = contract["inputs"]
    product = ROOT / inputs["require_product_d81"]["path"]
    verify_sha(product, inputs["require_product_d81"]["sha256"], "require product D81")
    medium = output / "sealed-r4-product-plus-repl-comfort.d81"
    shutil.copyfile(product, medium)
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    members = {member["disk_name"]: member for member in inputs["packed_library_members"]}
    for member in members.values():
        verify_sha(ROOT / member["path"], member["sha256"], member["disk_name"])

    spec = (
        "repl-comfort",
        "repl",
        "repl",
        COMFORT.REPAIR.COMFORT_MANIFEST,
        (),
    )
    placeholder, artifact = V17.LIBMEDIA.measured(
        spec, (1, 1), COMFORT.REPAIR.BASE.PRODUCT_ID
    )
    require(
        artifact == (ROOT / members["repl-comfort"]["path"]).read_bytes(),
        "measured Comfort artifact differs from the bound packed member",
    )
    seed_index = output / "l65index.seed"
    seed_index.write_bytes(V17.LIBMEDIA.L65I.encode_index([placeholder]))

    def c1541_write(source: Path, disk_name: str) -> None:
        completed = subprocess.run(
            [c1541, str(medium), "-write", str(source), disk_name],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        require(completed.returncode == 0, f"c1541 append failed for {disk_name}")

    c1541_write(seed_index, "l65index")
    c1541_write(ROOT / members["repl-comfort"]["path"], "repl-comfort")
    locator = V17.LIBMEDIA.L65I.d81_locators(medium)["repl-comfort"]
    row, located_artifact = V17.LIBMEDIA.measured(
        spec, locator, COMFORT.REPAIR.BASE.PRODUCT_ID
    )
    require(located_artifact == artifact, "Comfort artifact changed with packed locator")
    final_index = output / "l65index.packed"
    final_index.write_bytes(V17.LIBMEDIA.L65I.encode_index([row]))
    deleted = subprocess.run(
        [c1541, str(medium), "-delete", "l65index"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(deleted.returncode == 0, "c1541 could not replace the seed L65INDEX")
    c1541_write(final_index, "l65index")
    visible = V17.LIBMEDIA.L65I.D81.visible_files(medium.read_bytes())
    expected = {
        b"L65INDEX": final_index.read_bytes(),
        b"REPL-COMFORT": artifact,
    }
    for disk_name, raw in expected.items():
        require(
            visible.get(disk_name) == raw,
            f"packed bytes differ for {disk_name.decode()}",
        )
    decoded = V17.LIBMEDIA.L65I.decode_index(
        final_index.read_bytes(),
        {"repl-comfort": artifact},
        artifact_build_id=COMFORT.REPAIR.BASE.PRODUCT_ID,
    )
    require(
        len(decoded) == 1
        and tuple(decoded[0][key] for key in ("track", "sector")) == locator,
        "packed index does not name the actual artifact locator",
    )
    return medium


def run_headless(
    row: dict[str, Any], medium: Path, output: Path, args: argparse.Namespace
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    run_dir = output / ("run-" + row["id"])
    run_dir.mkdir()
    sd_copy = run_dir / "system-sd.img"
    subprocess.run(
        ["cp", "--reflink=auto", "--sparse=always", str(args.sd_image), str(sd_copy)],
        check=True,
    )
    d81_copy = run_dir / medium.name
    shutil.copyfile(medium, d81_copy)
    d81_copy.chmod(0o444)
    screen = run_dir / "framebuffer.txt"
    memory = run_dir / "memory.bin"
    log = run_dir / "xemu.log"
    monitor_path = Path("/tmp") / (
        f"l65-dwx-{os.getpid()}-{hashlib.sha256(row['id'].encode()).hexdigest()[:8]}.sock"
    )
    monitor_path.unlink(missing_ok=True)
    command = [
        str(SAFE_RUNNER),
        str(memory),
        str(args.timeout),
        str(args.xemu),
        "-skipconfigfile",
        "-headless",
        "-testing",
        "-sleepless",
        "-besure",
        "-fastboot",
        "-nosound",
        "-rom",
        str(args.rom),
        "-sdimg",
        str(sd_copy),
        "-8",
        str(d81_copy),
        "-autoload",
        "-uartmon",
        str(monitor_path),
        "-dumpscreen",
        str(screen),
        "-dumpmem",
        str(memory),
    ]
    stopped: dict[str, Any] | None = None
    with log.open("wb") as log_handle:
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 10.0
            while not monitor_path.exists() and time.monotonic() < deadline:
                require(process.poll() is None, f"Xemu exited early for {row['id']}")
                time.sleep(0.02)
            require(monitor_path.exists(), f"UART monitor absent for {row['id']}")
            monitor = Monitor(monitor_path)
            # The require row intentionally replays its sealed R4 device world,
            # whose banner predates the published v2.0.0 medium.  Readiness is
            # the live native prompt; each row's final framebuffer oracle binds
            # the world-specific visible result.
            monitor.wait_screen(["LISP65>"])
            if row["id"] == "capture-counters-at-stopped-point":
                stimulus = row["stimulus"]
                controller = stimulus["controller"]
                require(controller.endswith("\n"), "capture controller lost its submit event")
                monitor.type_text(controller[:-1])
                monitor.wait_screen(["WAIT 16383"])
                monitor.type_text("\n")
                # The marker is control-only instrumentation in the submitted
                # form.  It executes immediately before the nested read-line;
                # the product-owned lifecycle then arms the ring and resets all
                # four counters.  This establishes the same atomic origin as
                # the physical device row without desktop timing or focus.
                monitor.wait_screen(["\n" + stimulus["control_marker"] + "\n"])
                deadline = time.monotonic() + 12.0
                while time.monotonic() < deadline:
                    if (
                        monitor.memory16(0xFF8D)[0] != 0xFF
                        and monitor.memory16(0xBCFC)[:4] == b"\0\0\0\0"
                    ):
                        break
                    time.sleep(0.02)
                else:
                    raise RowError("capture controller never reached its fresh ring origin")

                counter = 0
                for _ in range(stimulus["passes"]):
                    counter = monitor.type_and_wait_counters(
                        stimulus["pattern"], counter
                    )
                    counter = monitor.type_and_wait_counters(
                        "\x08" * stimulus["delete_events_per_pass"], counter
                    )
                final = stimulus["final"]
                require(final.endswith("\n"), "capture final input lost its submit event")
                counter = monitor.type_and_wait_counters(final[:-1], counter)
                counter = monitor.type_and_wait_counters("\n", counter)
                require(
                    counter == stimulus["expected_device_modulo_count"],
                    "capture sequence no longer derives the device modulo count",
                )
                monitor.wait_screen(["\n7\n"])
                monitor.command("t1")
                counter_bytes = monitor.memory16(0xBCFC)[:4]
                stopped = {
                    "CPU_stopped_before_read": True,
                    "address": "0xBCFC",
                    "raw_bytes": counter_bytes.hex(),
                    "values": {
                        name: counter_bytes[index]
                        for index, name in enumerate(row["oracle"]["names"])
                    },
                    "all_equal": len(set(counter_bytes)) == 1,
                    "all_nonzero": all(counter_bytes),
                }
            else:
                monitor.type_text(row["input"])
                trigger = list(row["oracle"].get("required", []))
                trigger.extend("\n" + item + "\n" for item in row["oracle"].get("required_exact_lines", []))
                monitor.wait_screen(trigger)
                monitor.command("t1")
            monitor.command("~exit")
            status = process.wait(timeout=10)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            monitor_path.unlink(missing_ok=True)
            raise
    monitor_path.unlink(missing_ok=True)
    require(status == 0, f"headless Xemu failed for {row['id']}: {status}")
    require(screen.is_file() and memory.is_file(), f"runtime outputs absent for {row['id']}")
    text = screen.read_text(encoding="utf-8")
    oracle_result = framebuffer_oracle(text, row["oracle"])
    require(oracle_result["passed"], f"framebuffer oracle failed for {row['id']}: {oracle_result}")
    if stopped is not None:
        dump_bytes = memory.read_bytes()[0xBCFC:0xBD00]
        require(
            dump_bytes.hex() == stopped["raw_bytes"],
            "stopped monitor bytes and shutdown memory dump diverged",
        )
        require(stopped["all_equal"] and stopped["all_nonzero"], "capture counters diverged or stayed zero")
        exact = row["oracle"]["framebuffer_required_exact_lines"]
        lines = [line.strip() for line in decoded_framebuffer(text).splitlines()]
        require(all(item in lines for item in exact), "capture numeric framebuffer oracle failed")
    require(sha256(medium) == sha256(d81_copy), f"runtime medium changed for {row['id']}")
    return (
        {
            "status": "PASS",
            "transport": "headless local UART monitor to Xemu HWA queue",
            "desktop_focus_used": False,
            "GUI_used": False,
            "screen_queries_are_control_only": True,
            "oracle": oracle_result,
            "outputs": {
                "framebuffer": bind(screen),
                "memory": bind(memory),
                "log_non_authoritative": bind(log),
            },
        },
        stopped,
    )


def item3_row(contract_row: dict[str, Any], item3: dict[str, Any]) -> dict[str, Any]:
    mode = contract_row["execution"].split("bound-item3-", 1)[1].split("-cold-boot", 1)[0]
    row = next(
        value for value in item3["product_media_variants"] if value["id"] == f"product-medium-init-{mode}"
    )
    run_screen = ROOT / f"build/dwx/item3-freezer-free-variants-r2/run-{mode}/framebuffer.txt"
    require(sha256(run_screen) == row["outputs"]["framebuffer_sha256"], f"Item-3 {mode} framebuffer drift")
    result = framebuffer_oracle(run_screen.read_text(encoding="utf-8"), contract_row["oracle"])
    require(result["passed"], f"Item-3 {mode} row does not satisfy {contract_row['id']}")
    return {
        "status": "PASS",
        "source": "bound DWX Item-3 fresh cold boot",
        "item3_id": row["id"],
        "media_sha256": row["media"]["sha256"],
        "framebuffer_sha256": row["outputs"]["framebuffer_sha256"],
        "oracle": result,
    }


def build(args: argparse.Namespace) -> None:
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    adapter_contract = load(ADAPTER_CONTRACT_PATH)
    blind = load(BLIND_CONTRACT_PATH)
    BLIND.validate_contract(blind)
    inputs = contract["inputs"]
    verify_sha(ROOT / inputs["product_d81"]["path"], inputs["product_d81"]["sha256"], "product D81")
    verify_sha(
        ROOT / inputs["require_product_d81"]["path"],
        inputs["require_product_d81"]["sha256"],
        "require product D81",
    )
    verify_sha(args.rom, inputs["rom_sha256"], "ROM")
    verify_sha(args.sd_image, inputs["system_sd_sha256"], "system SD")
    manifest_path = ROOT / inputs["headless_adapter_manifest"]["path"]
    binary_path = ROOT / inputs["headless_adapter_binary"]["path"]
    verify_sha(manifest_path, inputs["headless_adapter_manifest"]["sha256"], "adapter manifest")
    verify_sha(binary_path, inputs["headless_adapter_binary"]["sha256"], "adapter binary")
    require(args.xemu.resolve() == binary_path.resolve(), "runtime Xemu is not the bound headless adapter")
    manifest = load(manifest_path)
    require(
        manifest.get("status") == "PASS"
        and manifest.get("binary", {}).get("sha256") == sha256(args.xemu)
        and manifest.get("transport") == adapter_contract["transport"]
        and manifest.get("base_qualified_tool_identity") == blind["sealed_item2_tool_identity"],
        "headless adapter manifest drift",
    )
    require(not args.out.exists(), f"output exists: {args.out}")
    args.out.mkdir(parents=True)
    packed_medium = create_packed_medium(contract, args.out)
    item3 = load(ROOT / inputs["item3_receipt"]["path"])
    results = []
    stopped = None
    product_medium = ROOT / inputs["product_d81"]["path"]
    for row in contract["rows"]:
        if row["state"] != "ACTIVE":
            continue
        if row["execution"].startswith("bound-item3-"):
            runtime = item3_row(row, item3)
        else:
            medium = packed_medium if row.get("medium") == "product-plus-packed-library" else product_medium
            runtime, stopped_row = run_headless(row, medium, args.out, args)
            if stopped_row is not None:
                stopped = stopped_row
        results.append(
            {
                "id": row["id"],
                "result": "PASS",
                "device_counterpart": row["device_counterpart"],
                "oracle_type": row["oracle"]["type"],
                "runtime": runtime,
            }
        )
    require(tuple(row["id"] for row in results) == ACTIVE_IDS, "executed row population drift")
    receipt = {
        "format": "lisp65-dwx-mirrored-prefilter-rows-receipt-v1",
        "status": "PASS",
        "recorded_on": "2026-09-02",
        "evidence_class": contract["evidence_class"],
        "authority": {
            "executor": bind(Path(__file__)),
            "contract": bind(CONTRACT_PATH),
            "adapter_contract": bind(ADAPTER_CONTRACT_PATH),
            "blind_spot_contract": bind(BLIND_CONTRACT_PATH),
            "item3_receipt": bind(ROOT / inputs["item3_receipt"]["path"]),
        },
        "tool_identity": {
            "base_qualified_fork": blind["sealed_item2_tool_identity"],
            "headless_input_extension": {
                "manifest": bind(manifest_path),
                "binary_sha256": sha256(args.xemu),
                "patches": manifest["patches"],
                "patched_source_sha256": manifest["patched_source_sha256"],
            },
        },
        "runtime_policy": contract["runtime_policy"],
        "packed_require_medium": bind(packed_medium),
        "rows": results,
        "deferred_rows": [
            {
                "id": DEFERRED_ID,
                "state": "DEFERRED_UNTIL_FREIGHT_RETURNS",
                "device_counterpart": next(
                    row for row in contract["rows"] if row["id"] == DEFERRED_ID
                )["device_counterpart"],
                "oracle_type": "framebuffer",
                "prefilter_claimed": False,
            }
        ],
        "capture_stopped_state": stopped,
        "device_mandatory_rows": list(BLIND.BLIND_IDS),
        "device_acceptance_claimed": False,
        "mutations": {"attempted": mutation_names(contract), "survived": []},
        "accounting": {
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "fresh_headless_xemu_processes": 3,
            "focus_dependent_input_events": 0,
        },
        "claim_limit": "Functional Xemu prefilter only. Every row remains device-mandatory for acceptance; Freezer, DMA timing, FPGA core identity, and physical typing feel remain blind spots.",
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "dwx mirrored rows BUILD PASS active=8 runtime=3 item3=5 "
        f"counters={stopped['raw_bytes'] if stopped else 'absent'} focus=0 GUI=0"
    )


def validate_receipt(receipt: dict[str, Any], contract: dict[str, Any]) -> None:
    validate_contract(contract)
    device_rows = receipt.get("device_mandatory_rows")
    require(
        device_rows in (SEALED_ITEM4_DEVICE_ROWS, list(BLIND.BLIND_IDS)),
        "mirrored-row receipt lost its sealed or live blind-spot population",
    )
    require(
        receipt.get("format") == "lisp65-dwx-mirrored-prefilter-rows-receipt-v1"
        and receipt.get("status") == "PASS"
        and receipt.get("evidence_class") == "xemu-prefilter-green"
        and receipt.get("runtime_policy") == contract["runtime_policy"]
        and receipt.get("device_acceptance_claimed") is False,
        "mirrored-row receipt header drift",
    )
    rows = receipt.get("rows")
    require(
        isinstance(rows, list)
        and tuple(row.get("id") for row in rows) == ACTIVE_IDS
        and all(row.get("result") == "PASS" for row in rows)
        and all(row.get("oracle_type") in ORACLE_TYPES for row in rows)
        and all(row.get("device_counterpart") for row in rows),
        "mirrored-row result population drift",
    )
    contract_rows = {row["id"]: row for row in contract["rows"]}
    for row in rows:
        resolve_device_counterpart(row["device_counterpart"])
        runtime = row["runtime"]
        require(runtime.get("status") == "PASS", f"{row['id']} is not green")
        if row["id"] in (
            "tier1-documented-domain-error",
            "library-require-over-packed-medium",
            "capture-counters-at-stopped-point",
        ):
            require(
                runtime.get("desktop_focus_used") is False
                and runtime.get("GUI_used") is False
                and runtime.get("screen_queries_are_control_only") is True
                and runtime.get("oracle", {}).get("passed") is True,
                f"{row['id']} lost focus-free execution or framebuffer authority",
            )
            outputs = runtime.get("outputs", {})
            for role in ("framebuffer", "memory", "log_non_authoritative"):
                artifact = outputs.get(role, {})
                require(
                    artifact == bind(ROOT / artifact.get("path", "")),
                    f"{row['id']} {role} binding drift",
                )
            framebuffer = ROOT / outputs["framebuffer"]["path"]
            require(
                runtime["oracle"] == framebuffer_oracle(
                    framebuffer.read_text(encoding="utf-8"),
                    contract_rows[row["id"]]["oracle"],
                ),
                f"{row['id']} framebuffer oracle was not rederived",
            )
    stopped = receipt.get("capture_stopped_state")
    require(
        isinstance(stopped, dict)
        and stopped.get("CPU_stopped_before_read") is True
        and stopped.get("address") == "0xBCFC"
        and stopped.get("all_equal") is True
        and stopped.get("all_nonzero") is True
        and list(stopped.get("values", {})) == ["raw", "seen", "stored", "taken"],
        "capture stopped-state oracle drift",
    )
    capture_runtime = next(
        row["runtime"] for row in rows
        if row["id"] == "capture-counters-at-stopped-point"
    )
    capture_memory = ROOT / capture_runtime["outputs"]["memory"]["path"]
    require(
        capture_memory.read_bytes()[0xBCFC:0xBD00].hex()
        == stopped["raw_bytes"],
        "capture stopped-state bytes do not match the bound memory dump",
    )
    deferred = receipt.get("deferred_rows")
    require(
        deferred
        == [
            {
                "id": DEFERRED_ID,
                "state": "DEFERRED_UNTIL_FREIGHT_RETURNS",
                "device_counterpart": next(
                    row for row in contract["rows"] if row["id"] == DEFERRED_ID
                )["device_counterpart"],
                "oracle_type": "framebuffer",
                "prefilter_claimed": False,
            }
        ],
        "deferred matcher/blink row was promoted or lost",
    )
    require(
        receipt.get("mutations") == {"attempted": mutation_names(contract), "survived": []}
        and receipt.get("accounting")
        == {
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "fresh_headless_xemu_processes": 3,
            "focus_dependent_input_events": 0,
        },
        "mirrored-row mutations or accounting drift",
    )
    authority = receipt.get("authority")
    blind_binding = (
        SEALED_ITEM4_BLIND_BINDING
        if device_rows == SEALED_ITEM4_DEVICE_ROWS
        else bind(BLIND_CONTRACT_PATH)
    )
    executor_binding = (
        SEALED_ITEM4_EXECUTOR_BINDING
        if device_rows == SEALED_ITEM4_DEVICE_ROWS
        else bind(Path(__file__))
    )
    require(
        authority
        == {
            "executor": executor_binding,
            "contract": bind(CONTRACT_PATH),
            "adapter_contract": (ERA.era_bind("b8c59de7", ADAPTER_CONTRACT_PATH)
                                 if device_rows == SEALED_ITEM4_DEVICE_ROWS
                                 else bind(ADAPTER_CONTRACT_PATH)),
            "blind_spot_contract": blind_binding,
            "item3_receipt": bind(ROOT / contract["inputs"]["item3_receipt"]["path"]),
        },
        "mirrored-row authority drift",
    )
    inputs = contract["inputs"]
    manifest_path = ROOT / inputs["headless_adapter_manifest"]["path"]
    manifest = load(manifest_path)
    blind = load(BLIND_CONTRACT_PATH)
    base_identity = (
        blind["sealed_item2_tool_identity"]
        if device_rows == SEALED_ITEM4_DEVICE_ROWS
        else blind["qualified_tool_identity"]
    )
    require(
        receipt.get("tool_identity") == {
            "base_qualified_fork": base_identity,
            "headless_input_extension": {
                "manifest": bind(manifest_path),
                "binary_sha256": sha256(
                    ROOT / inputs["headless_adapter_binary"]["path"]
                ),
                "patches": manifest["patches"],
                "patched_source_sha256": manifest["patched_source_sha256"],
            },
        },
        "headless adapter identity drift",
    )
    packed = receipt.get("packed_require_medium", {})
    require(
        packed == bind(ROOT / packed.get("path", "")),
        "packed require medium binding drift",
    )


def check() -> None:
    contract = load(CONTRACT_PATH)
    receipt = load(RECEIPT_PATH)
    validate_receipt(receipt, contract)
    if receipt.get("device_mandatory_rows") == SEALED_ITEM4_DEVICE_ROWS:
        mixed = deepcopy(receipt)
        mixed["authority"]["adapter_contract"] = bind(ADAPTER_CONTRACT_PATH)
        if mixed["authority"]["adapter_contract"] != receipt["authority"]["adapter_contract"]:
            try:
                validate_receipt(mixed, contract)
            except RowError:
                pass
            else:
                raise RowError("sealed Item-4 claim accepted live navigation authority")
    report = REPORT_PATH.read_text(encoding="utf-8")
    plan = WORK_PLAN_PATH.read_text(encoding="utf-8")
    require(
        "fokusfreie UART/HWA-Schnittstelle" in report
        and "Framebuffer" in report
        and "Stopped-State-Speicher" in report
        and "keine Logzeile" in report,
        "Item-4 report lost transport or oracle boundary",
    )
    item4 = plan.split("### Item 4", 1)[1].split("### Item 5", 1)[0]
    require("**Closed 2026-09-02:**" in item4, "work plan does not close Item 4")
    print(
        "dwx mirrored rows CHECK PASS active=8 deferred=1 "
        f"counters={receipt['capture_stopped_state']['raw_bytes']} focus=0 GUI=0"
    )


def selftest() -> None:
    breakpoint_transport_selftest()
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    names = mutation_names(contract)
    require(len(names) == 10, "mirrored-row mutation population drift")
    good = framebuffer_oracle(
        "WORKBENCH 2.0.0\nT\nLISP65> {$A0}\n",
        {"required": ["LISP65>"], "required_exact_lines": ["T"], "forbidden": ["ERROR"]},
    )
    require(good["passed"], "framebuffer exact-line control rejected")
    require(
        not framebuffer_oracle("T only in xemu.log", {"required": ["LISP65>"], "required_exact_lines": ["T"]})["passed"],
        "log-only oracle mutation survived",
    )
    print("dwx mirrored rows SELFTEST PASS mutations=10 oracles=framebuffer,stopped-memory")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    parser.add_argument("--xemu", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--sd-image", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv[1:])
    if args.action == "selftest":
        selftest()
    elif args.action == "check":
        check()
    else:
        require(
            args.xemu is not None and args.rom is not None and args.sd_image is not None and args.out is not None,
            "build requires --xemu, --rom, --sd-image, and --out",
        )
        args.xemu = args.xemu.resolve()
        args.rom = args.rom.resolve()
        args.sd_image = args.sd_image.resolve()
        args.out = args.out.resolve()
        build(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (RowError, OSError, subprocess.CalledProcessError) as error:
        print(f"dwx-mirrored-rows: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
