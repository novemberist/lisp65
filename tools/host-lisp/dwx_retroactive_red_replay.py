#!/usr/bin/env python3
"""Replay the three sealed v2.0 session reds in headless Xemu."""

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

import dwx_mirrored_prefilter_rows as ROWS  # noqa: E402


CONTRACT_PATH = ROOT / "config/dwx-retroactive-red-replay-contract.json"
RECEIPT_PATH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "dwx-buffered-repair-three-patch-red-replay-receipt-20260905.json"
)
REPORT_PATH = ROOT / "docs/planning/dwx-three-patch-restoration-report.md"
WORK_PLAN_PATH = ROOT / "docs/planning/dwx-delivered-world-executor-work-plan.md"
SAFE_RUNNER = ROOT / "scripts/xmega65-safe-run.sh"
ROW_IDS = ("stale-v16core-freight", "b3-1-no-keystroke", "block3-hot-path")
PATCH_ROLES = ("base_patch", "transport_patch", "cycle_patch")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReplayError(f"cannot load {path}: {error}") from error
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


def sealed_bytes(commit: str, path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(completed.returncode == 0,
            f"sealed input absent at {commit}: {relative}")
    return completed.stdout


def sealed_bind(commit: str, path: Path) -> dict[str, Any]:
    raw = sealed_bytes(commit, path)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def verify_binding(value: dict[str, Any], role: str) -> Path:
    path = ROOT / value.get("path", "")
    require(path.is_file() and sha256(path) == value.get("sha256"), f"{role} binding drift")
    return path


def cycle_manifest_view(value: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Bind the live three-patch executor and every member of its patch set."""
    path = ROOT / value.get("path", "")
    require(path.is_file() and not path.is_symlink(), "cycle-probe manifest absent")
    current = load(path)
    current_binding = bind(path)
    require({"path": current_binding["path"],
             "sha256": current_binding["sha256"]} == value,
            "cycle-probe manifest binding drift")
    patches = current.get("patches")
    require(isinstance(patches, list)
            and tuple(row.get("role") for row in patches) == PATCH_ROLES,
            "live cycle-probe is not the complete ordered three-patch fork")
    for patch in current["patches"]:
        require(bind(ROOT / patch["path"])["sha256"] == patch["sha256"],
                f"live cycle-probe patch binding drift: {patch['role']}")
    require(len(current.get("patched_source_sha256", {})) == 10
            and "targets/mega65/dwx_keymap_generated.h" in current["patched_source_sha256"]
            and "xemu/f011_core.c" in current["patched_source_sha256"],
            "four-patch source population drift")
    return path, current, current_binding


def resolve_device_counterpart(value: str) -> None:
    require("#" in value, f"device counterpart has no row fragment: {value}")
    relative, row_id = value.rsplit("#", 1)
    rows = load(ROOT / relative).get("rows")
    require(
        isinstance(rows, list) and sum(row.get("id") == row_id for row in rows) == 1,
        f"device counterpart is not an exact row: {value}",
    )


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-retroactive-red-replay-contract-v2"
        and contract.get("status") == "ACTIVE"
        and contract.get("evidence_class") == "xemu-prefilter-red-reproduced",
        "retroactive contract header drift",
    )
    require(
        contract.get("authority_rule")
        == "Every sealed v2.0 device-session red is replayed over its byte-exact sealed medium by a fresh headless process and must reproduce through a framebuffer, stopped-memory, or emulated-cycle oracle; a log line is never the oracle.",
        "retroactive authority rule drift",
    )
    require(
        contract.get("runtime_policy")
        == {
            "headless": True,
            "desktop_focus_input": False,
            "input_transport": "local-unix-uart-monitor-to-HWA-queue",
            "logs_are_oracle": False,
            "fresh_process_per_world": True,
            "device_acceptance_claimed": False,
        },
        "retroactive runtime policy drift",
    )
    rows = contract.get("rows")
    require(isinstance(rows, list) and tuple(row.get("id") for row in rows) == ROW_IDS, "red row population drift")
    expected_types = ("framebuffer", "stopped-memory-plus-framebuffer", "emulated-cycle-trace")
    for row, oracle_type in zip(rows, expected_types):
        resolve_device_counterpart(row.get("device_counterpart", ""))
        verify_binding(row["sealed_red_receipt"], f"{row['id']} red receipt")
        verify_binding(row["product_medium"], f"{row['id']} product medium")
        require(row.get("oracle", {}).get("type") == oracle_type, f"{row['id']} oracle drift")
    stale, b31, hot = rows
    require(
        verify_binding(stale["library_medium"], "stale v16core library").stat().st_size == 819200
        and stale["stimulus"] == "(require 'v16core)\n"
        and stale["oracle"]["minimum_visible_instances"] >= 2,
        "stale-v16core replay was weakened",
    )
    require(
        b31["stimulus"] == "a"
        and b31["oracle"]["names"] == ["raw", "seen", "stored", "taken"]
        and b31["oracle"]["relation"] == "raw == seen == stored >= 1 and taken == 0",
        "B3-1 stopped-memory discriminator drift",
    )
    require(
        verify_binding(hot["reference_medium"], "hot-path reference medium").stat().st_size == 819200
        and hot["stimulus"] == {
            "byte": "a",
            "characters": 40,
            "screen_base": "0x0800",
            "device_reference_vm_steps_per_key": 902,
        }
        and hot["oracle"]["minimum_red_to_reference_cycle_ratio"] >= 1.5,
        "hot-path measurement was weakened",
    )
    inputs = contract["inputs"]
    verify_binding(inputs["item5_receipt"], "Item-5 receipt")
    requalification = load(verify_binding(
        inputs["fork_requalification_receipt"], "four-patch requalification receipt"
    ))
    require(
        requalification.get("status") == "PASS"
        and tuple(p.get("role") for p in requalification.get("prefilter_tool_identity", {}).get("patches", [])) == PATCH_ROLES,
        "four-patch runtime requalification is not green",
    )
    cycle_manifest_view(inputs["cycle_probe_manifest"])
    verify_binding(inputs["cycle_probe_binary"], "cycle-probe binary")


def mutations(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    value = deepcopy(contract)
    value["runtime_policy"]["desktop_focus_input"] = True
    result["desktop-focus-input-reintroduced"] = value
    value = deepcopy(contract)
    value["runtime_policy"]["logs_are_oracle"] = True
    result["log-promoted-to-oracle"] = value
    value = deepcopy(contract)
    value["rows"].pop(1)
    result["sealed-red-omitted"] = value
    value = deepcopy(contract)
    value["rows"][0]["oracle"]["minimum_visible_instances"] = 1
    result["v16core-loop-reduced-to-one-message"] = value
    value = deepcopy(contract)
    value["rows"][1]["oracle"]["names"].pop()
    result["b31-taken-counter-omitted"] = value
    value = deepcopy(contract)
    value["rows"][1]["oracle"]["relation"] = "raw == seen == stored"
    result["b31-zero-taken-not-required"] = value
    value = deepcopy(contract)
    value["rows"][2].pop("reference_medium")
    result["hot-path-reference-omitted"] = value
    value = deepcopy(contract)
    value["rows"][2]["stimulus"]["characters"] = 8
    result["hot-path-trace-shortened"] = value
    value = deepcopy(contract)
    value["rows"][2]["oracle"]["minimum_red_to_reference_cycle_ratio"] = 1.0
    result["hot-path-red-threshold-weakened"] = value
    value = deepcopy(contract)
    value["rows"][0].pop("device_counterpart")
    result["device-counterpart-omitted"] = value
    return result


def mutation_names(contract: dict[str, Any]) -> list[str]:
    names = []
    for name, value in mutations(contract).items():
        try:
            validate_contract(value)
        except (ReplayError, KeyError):
            names.append(name)
            continue
        raise ReplayError(f"retroactive replay mutation survived: {name}")
    return sorted(names)


class ProbeMonitor(ROWS.Monitor):
    def cycle_count(self) -> int:
        response = self.command("~cyclecount")
        match = re.search(r"DWX CPU cycles: ([0-9]+)", response)
        require(match is not None, "cycle counter response malformed")
        return int(match.group(1))

    def memory_range(self, address: int, count: int) -> bytes:
        return b"".join(self.memory16(at) for at in range(address, address + count, 16))[:count]

    def queue_one(self, value: int) -> None:
        response = self.command(f"~typeone {value:02x}")
        require("DWX HWA single byte queued" in response, "single-byte HWA injection failed")


def start_run(run_id: str, medium: Path, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    run_dir = output / ("run-" + run_id)
    run_dir.mkdir()
    sd_copy = run_dir / "system-sd.img"
    subprocess.run(["cp", "--reflink=auto", "--sparse=always", str(args.sd_image), str(sd_copy)], check=True)
    medium_copy = run_dir / medium.name
    shutil.copyfile(medium, medium_copy)
    medium_copy.chmod(0o444)
    memory = run_dir / "memory.bin"
    screen = run_dir / "framebuffer.txt"
    log = run_dir / "xemu.log"
    monitor_path = Path("/tmp") / f"l65-dwx-item6-{os.getpid()}-{run_id}.sock"
    monitor_path.unlink(missing_ok=True)
    command = [
        str(SAFE_RUNNER), str(memory), str(args.timeout), str(args.xemu),
        "-skipconfigfile", "-headless", "-testing", "-sleepless", "-besure",
        "-fastboot", "-nosound", "-rom", str(args.rom), "-sdimg", str(sd_copy),
        "-8", str(medium_copy), "-autoload", "-uartmon", str(monitor_path),
        "-dumpscreen", str(screen), "-dumpmem", str(memory),
    ]
    log_handle = log.open("wb")
    process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 12
    while not monitor_path.exists() and time.monotonic() < deadline:
        require(process.poll() is None, f"Xemu exited before monitor for {run_id}")
        time.sleep(0.02)
    require(monitor_path.exists(), f"UART monitor absent for {run_id}")
    monitor = ProbeMonitor(monitor_path)
    monitor.wait_screen(["LISP65>"], timeout=20)
    return {
        "id": run_id,
        "dir": run_dir,
        "medium_copy": medium_copy,
        "memory": memory,
        "screen": screen,
        "log": log,
        "monitor_path": monitor_path,
        "log_handle": log_handle,
        "process": process,
        "monitor": monitor,
        "source_medium_sha256": sha256(medium),
    }


def finish_run(run: dict[str, Any], framebuffer: str | None = None) -> dict[str, Any]:
    monitor: ProbeMonitor = run["monitor"]
    process: subprocess.Popen[bytes] = run["process"]
    if framebuffer is None:
        framebuffer = monitor.screen()
    (run["dir"] / "oracle-framebuffer.txt").write_text(framebuffer, encoding="utf-8")
    monitor.command("~exit")
    status = process.wait(timeout=12)
    run["log_handle"].close()
    run["monitor_path"].unlink(missing_ok=True)
    require(status == 0, f"headless Xemu failed for {run['id']}: {status}")
    require(run["memory"].is_file() and run["screen"].is_file(), f"shutdown outputs absent for {run['id']}")
    require(sha256(run["medium_copy"]) == run["source_medium_sha256"], f"runtime medium changed for {run['id']}")
    return {
        "framebuffer": bind(run["dir"] / "oracle-framebuffer.txt"),
        "shutdown_framebuffer": bind(run["screen"]),
        "memory": bind(run["memory"]),
        "log_non_authoritative": bind(run["log"]),
    }


def abort_run(run: dict[str, Any]) -> None:
    process: subprocess.Popen[bytes] = run["process"]
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    run["log_handle"].close()
    run["monitor_path"].unlink(missing_ok=True)


def replay_stale(row: dict[str, Any], output: Path, args: argparse.Namespace) -> dict[str, Any]:
    product = verify_binding(row["product_medium"], "stale product medium")
    library = verify_binding(row["library_medium"], "stale library medium")
    run = start_run(row["id"], product, output, args)
    try:
        library_copy = run["dir"] / library.name
        shutil.copyfile(library, library_copy)
        library_copy.chmod(0o444)
        response = run["monitor"].command("~mount0" + str(library_copy.resolve()))
        require("?SYNTAX ERROR" not in response, "headless sealed-library mount failed")
        run["monitor"].type_text(row["stimulus"])
        screen = run["monitor"].wait_screen([row["oracle"]["required_text"]], timeout=20)
        deadline = time.monotonic() + 5
        while ROWS.decoded_framebuffer(screen).count(row["oracle"]["required_text"]) < row["oracle"]["minimum_visible_instances"] and time.monotonic() < deadline:
            time.sleep(0.03)
            screen = run["monitor"].screen()
        run["monitor"].command("t1")
        screen = run["monitor"].screen()
        count = ROWS.decoded_framebuffer(screen).count(row["oracle"]["required_text"])
        require(count >= row["oracle"]["minimum_visible_instances"], "stale-v16core red did not repeat")
        outputs = finish_run(run, screen)
        require(sha256(library_copy) == row["library_medium"]["sha256"], "mounted stale library changed")
        return {
            "id": row["id"], "result": "EMULATOR RED REPRODUCED", "oracle_type": "framebuffer",
            "device_counterpart": row["device_counterpart"], "visible_instances": count,
            "mounted_library": bind(library_copy), "outputs": outputs,
        }
    except BaseException:
        abort_run(run)
        raise


def replay_b31(row: dict[str, Any], output: Path, args: argparse.Namespace) -> dict[str, Any]:
    product = verify_binding(row["product_medium"], "B3-1 product medium")
    run = start_run(row["id"], product, output, args)
    try:
        before = run["monitor"].screen()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if run["monitor"].memory16(0xFF8D)[0] != 0xFF:
                break
            time.sleep(0.02)
        else:
            raise ReplayError("B3-1 product never armed its input ring")
        run["monitor"].type_text(row["stimulus"])
        deadline = time.monotonic() + 12
        counters = b""
        while time.monotonic() < deadline:
            counters = run["monitor"].memory16(0xBCFC)[:4]
            if counters[0] == counters[1] == counters[2] and counters[0] >= 1 and counters[3] == 0:
                break
            time.sleep(0.02)
        require(counters and counters[0] == counters[1] == counters[2] and counters[0] >= 1 and counters[3] == 0, f"B3-1 discriminator did not appear: {counters.hex()}")
        run["monitor"].command("t1")
        screen = run["monitor"].screen()
        require("LISP65>" in ROWS.decoded_framebuffer(screen), "B3-1 framebuffer lost visible prompt")
        outputs = finish_run(run, screen)
        dumped = (ROOT / outputs["memory"]["path"]).read_bytes()[0xBCFC:0xBD00]
        require(dumped == counters, "B3-1 stopped bytes differ from shutdown dump")
        return {
            "id": row["id"], "result": "EMULATOR RED REPRODUCED", "oracle_type": "stopped-memory-plus-framebuffer",
            "device_counterpart": row["device_counterpart"], "stimulus_visible": ROWS.decoded_framebuffer(screen) != ROWS.decoded_framebuffer(before),
            "stopped_state": {"address": "0xBCFC", "raw_bytes": counters.hex(), "values": dict(zip(row["oracle"]["names"], counters))},
            "outputs": outputs,
        }
    except BaseException:
        abort_run(run)
        raise


def find_input_start(monitor: ProbeMonitor, screen_base: int) -> int:
    screen = monitor.memory_range(screen_base, 80 * 25)
    needles = (
        bytes((0x0C, 0x09, 0x13, 0x10, 0x36, 0x35, 0x3E)),
        b"LISP65>",
        b"lisp65>",
    )
    positions = [screen.rfind(needle) for needle in needles]
    position = max(positions)
    require(position >= 0, "native prompt not found in screen RAM")
    target = screen_base + position + 8
    require(monitor.memory16(target)[0] in (0, 0x20, 0xA0), f"native input cell is not blank: {target:04x}")
    return target


def cycle_trace(run_id: str, medium: Path, characters: int, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    run = start_run(run_id, medium, output, args)
    try:
        monitor: ProbeMonitor = run["monitor"]
        monitor.command("t1")
        start = find_input_start(monitor, 0x0800)
        deltas = []
        targets = []
        for index in range(characters):
            target = start + index
            before_byte = monitor.memory16(target)[0]
            require(before_byte in (0, 0x20, 0xA0), f"trace target already occupied at {target:04x}")
            monitor.command(f"w {target:08x}")
            before_cycles = monitor.cycle_count()
            monitor.queue_one(ord("a"))
            monitor.command("t0")
            deadline = time.monotonic() + 12
            after_cycles = before_cycles
            after_byte = before_byte
            while time.monotonic() < deadline:
                after_byte = monitor.memory16(target)[0]
                first = monitor.cycle_count()
                time.sleep(0.002)
                second = monitor.cycle_count()
                after_cycles = second
                if after_byte != before_byte and first == second:
                    break
            require(after_byte != before_byte and after_cycles > before_cycles, f"screen-write watchpoint did not fire at {target:04x}")
            deltas.append(after_cycles - before_cycles)
            targets.append(f"0x{target:04X}")
        screen = monitor.screen()
        trace = {
            "characters": characters,
            "input_byte": "0x61",
            "screen_start": f"0x{start:04X}",
            "screen_write_targets": targets,
            "cycle_deltas": deltas,
            "total_cycles": sum(deltas),
            "mean_cycles_per_key": sum(deltas) / len(deltas),
            "minimum_cycles": min(deltas),
            "maximum_cycles": max(deltas),
        }
        trace_path = run["dir"] / "cycle-trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs = finish_run(run, screen)
        trace["artifact"] = bind(trace_path)
        trace["outputs"] = outputs
        return trace
    except BaseException:
        abort_run(run)
        raise


def replay_hot(row: dict[str, Any], output: Path, args: argparse.Namespace) -> dict[str, Any]:
    hot = verify_binding(row["product_medium"], "hot-path red medium")
    reference = verify_binding(row["reference_medium"], "902-step reference medium")
    characters = row["stimulus"]["characters"]
    reference_trace = cycle_trace("block3-hot-path-reference", reference, characters, output, args)
    red_trace = cycle_trace(row["id"], hot, characters, output, args)
    ratio = red_trace["total_cycles"] / reference_trace["total_cycles"]
    require(ratio >= row["oracle"]["minimum_red_to_reference_cycle_ratio"], f"hot-path cycle red not reproduced: ratio={ratio:.6f}")
    return {
        "id": row["id"], "result": "EMULATOR RED REPRODUCED", "oracle_type": "emulated-cycle-trace",
        "device_counterpart": row["device_counterpart"],
        "device_reference_vm_steps_per_key": row["stimulus"]["device_reference_vm_steps_per_key"],
        "reference_trace": reference_trace, "red_trace": red_trace,
        "red_to_reference_cycle_ratio": ratio,
        "required_minimum_ratio": row["oracle"]["minimum_red_to_reference_cycle_ratio"],
    }


def build(args: argparse.Namespace) -> None:
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    inputs = contract["inputs"]
    require(sha256(args.rom) == inputs["rom_sha256"], "ROM SHA drift")
    require(sha256(args.sd_image) == inputs["system_sd_sha256"], "system SD SHA drift")
    binary = verify_binding(inputs["cycle_probe_binary"], "cycle-probe binary")
    require(args.xemu.resolve() == binary.resolve(), "runtime Xemu is not the bound cycle-probe fork")
    _, manifest, _ = cycle_manifest_view(inputs["cycle_probe_manifest"])
    require(manifest.get("binary", {}).get("sha256") == sha256(binary), "cycle-probe manifest/binary divergence")
    require(not args.out.exists(), f"output exists: {args.out}")
    args.out.mkdir(parents=True)
    rows = {row["id"]: row for row in contract["rows"]}
    results = [
        replay_stale(rows["stale-v16core-freight"], args.out, args),
        replay_b31(rows["b3-1-no-keystroke"], args.out, args),
        replay_hot(rows["block3-hot-path"], args.out, args),
    ]
    require(tuple(row["id"] for row in results) == ROW_IDS, "executed red population drift")
    receipt = {
        "format": "lisp65-dwx-retroactive-red-replay-receipt-v2",
        "status": "PASS: THREE OF THREE SEALED DEVICE REDS REPRODUCED",
        "recorded_on": "2026-09-05",
        "evidence_class": contract["evidence_class"],
        "authority": {
            "executor": bind(Path(__file__)), "contract": bind(CONTRACT_PATH),
            "item5_receipt": bind(verify_binding(inputs["item5_receipt"], "Item-5 receipt")),
            "fork_requalification_receipt": bind(verify_binding(
                inputs["fork_requalification_receipt"], "four-patch requalification receipt"
            )),
            "cycle_probe_manifest": bind(verify_binding(inputs["cycle_probe_manifest"], "cycle-probe manifest")),
        },
        "tool_identity": {
            "binary": bind(binary), "source_commit": manifest["source_commit"],
            "patches": manifest["patches"], "patched_source_sha256": manifest["patched_source_sha256"],
        },
        "runtime_policy": contract["runtime_policy"],
        "rows": results,
        "bar": {"required_reds": 3, "reproduced_reds": 3, "all_reproduced": True},
        "mutations": {"attempted": mutation_names(contract), "survived": []},
        "accounting": {
            "product_bytes_changed": 0, "WPLTO_runs": 0, "product_links": 0,
            "device_contacts": 0, "fresh_headless_xemu_processes": 4,
            "focus_dependent_input_events": 0,
        },
        "device_acceptance_claimed": False,
        "claim_limit": "Retroactive Xemu-prefilter coverage only. UART/HWA and emulated cycles do not claim physical keyboard timing, typing feel, FPGA timing, Freezer behavior, or device acceptance.",
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"dwx retroactive replay BUILD PASS reds=3/3 b31={results[1]['stopped_state']['raw_bytes']} hot-ratio={results[2]['red_to_reference_cycle_ratio']:.6f} focus=0 GUI=0")


def validate_receipt(receipt: dict[str, Any], contract: dict[str, Any]) -> None:
    validate_contract(contract)
    require(
        receipt.get("format") == "lisp65-dwx-retroactive-red-replay-receipt-v2"
        and receipt.get("status") == "PASS: THREE OF THREE SEALED DEVICE REDS REPRODUCED"
        and receipt.get("evidence_class") == contract["evidence_class"]
        and receipt.get("runtime_policy") == contract["runtime_policy"]
        and receipt.get("device_acceptance_claimed") is False,
        "retroactive receipt header drift",
    )
    rows = receipt.get("rows")
    require(isinstance(rows, list) and tuple(row.get("id") for row in rows) == ROW_IDS, "retroactive result population drift")
    require(all(row.get("result") == "EMULATOR RED REPRODUCED" for row in rows), "a sealed red is not reproduced")
    stale, b31, hot = rows
    stale_screen = (ROOT / stale["outputs"]["framebuffer"]["path"]).read_text(encoding="utf-8")
    required = contract["rows"][0]["oracle"]["required_text"]
    require(ROWS.decoded_framebuffer(stale_screen).count(required) == stale["visible_instances"] >= 2, "stale-v16core framebuffer red drift")
    b31_memory = (ROOT / b31["outputs"]["memory"]["path"]).read_bytes()[0xBCFC:0xBD00]
    require(
        b31_memory.hex() == b31["stopped_state"]["raw_bytes"]
        and b31_memory[0] == b31_memory[1] == b31_memory[2]
        and b31_memory[0] >= 1 and b31_memory[3] == 0,
        "B3-1 stopped-memory red drift",
    )
    for role in ("reference_trace", "red_trace"):
        trace = hot[role]
        artifact = ROOT / trace["artifact"]["path"]
        require(bind(artifact) == trace["artifact"], f"hot-path {role} binding drift")
        derived = load(artifact)
        require(
            derived["total_cycles"] == trace["total_cycles"]
            and derived["cycle_deltas"] == trace["cycle_deltas"]
            and len(derived["cycle_deltas"]) == 40,
            f"hot-path {role} was not rederived",
        )
    ratio = hot["red_trace"]["total_cycles"] / hot["reference_trace"]["total_cycles"]
    require(ratio == hot["red_to_reference_cycle_ratio"] and ratio >= 1.5, "hot-path cycle red drift")
    for row in rows:
        resolve_device_counterpart(row["device_counterpart"])
        outputs = []
        if "outputs" in row:
            outputs.append(row["outputs"])
        if row["id"] == "block3-hot-path":
            outputs.extend([row["reference_trace"]["outputs"], row["red_trace"]["outputs"]])
        for output in outputs:
            for artifact in output.values():
                require(bind(ROOT / artifact["path"]) == artifact, "runtime output binding drift")
    inputs = contract["inputs"]
    _, manifest, current_manifest = cycle_manifest_view(inputs["cycle_probe_manifest"])
    executed_contract = receipt.get("authority", {}).get("contract", {})
    contract_path = verify_binding(
        {k: executed_contract.get(k) for k in ("path", "sha256")}, "executed contract")
    require(load(contract_path) == contract, "promoted contract differs from executed contract")
    require(
        receipt.get("authority") == {
            "executor": bind(Path(__file__)),
            "contract": bind(contract_path),
            "item5_receipt": bind(verify_binding(inputs["item5_receipt"], "Item-5 receipt")),
            "fork_requalification_receipt": bind(verify_binding(
                inputs["fork_requalification_receipt"], "four-patch requalification receipt"
            )),
            "cycle_probe_manifest": current_manifest,
        }
        and receipt.get("tool_identity") == {
            "binary": bind(verify_binding(inputs["cycle_probe_binary"], "cycle-probe binary")),
            "source_commit": manifest["source_commit"], "patches": manifest["patches"],
            "patched_source_sha256": manifest["patched_source_sha256"],
        },
        "retroactive authority or tool identity drift",
    )
    require(
        receipt.get("bar") == {"required_reds": 3, "reproduced_reds": 3, "all_reproduced": True}
        and receipt.get("mutations") == {"attempted": mutation_names(contract), "survived": []}
        and receipt.get("accounting") == {
            "product_bytes_changed": 0, "WPLTO_runs": 0, "product_links": 0,
            "device_contacts": 0, "fresh_headless_xemu_processes": 4,
            "focus_dependent_input_events": 0,
        },
        "retroactive bar, mutations, or accounting drift",
    )


def check() -> None:
    contract = load(CONTRACT_PATH)
    receipt = load(RECEIPT_PATH)
    validate_receipt(receipt, contract)
    report = REPORT_PATH.read_text(encoding="utf-8")
    plan = WORK_PLAN_PATH.read_text(encoding="utf-8")
    require("3/3" in report and "Drei-Patch-Fork" in report, "three-patch requalification report lost its result")
    item6 = plan.split("### Item 6", 1)[1].split("## Out of scope", 1)[0]
    require("**Closed 2026-09-03:**" in item6, "work plan does not close Item 6")
    print(f"dwx retroactive replay CHECK PASS reds=3/3 b31={receipt['rows'][1]['stopped_state']['raw_bytes']} hot-ratio={receipt['rows'][2]['red_to_reference_cycle_ratio']:.6f}")


def selftest() -> None:
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    names = mutation_names(contract)
    require(len(names) == 10, "retroactive mutation population drift")
    print(f"dwx retroactive replay SELFTEST PASS mutations=10 required-reds=3 fork-patches={len(PATCH_ROLES)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    parser.add_argument("--xemu", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--sd-image", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv[1:])
    if args.action == "selftest":
        selftest()
    elif args.action == "check":
        check()
    else:
        require(all(value is not None for value in (args.xemu, args.rom, args.sd_image, args.out)), "build requires --xemu, --rom, --sd-image, and --out")
        args.xemu = args.xemu.resolve()
        args.rom = args.rom.resolve()
        args.sd_image = args.sd_image.resolve()
        args.out = args.out.resolve()
        build(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ReplayError, ROWS.RowError, OSError, subprocess.CalledProcessError, socket.error, json.JSONDecodeError) as error:
        print(f"dwx-retroactive-red-replay: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
