#!/usr/bin/env python3
"""Decide whether the first-event witness can avoid core synthesis."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CORE = ROOT / "build/upstream-verification/mega65-core"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-first-event-bitstream-patch-attribution.json")

AUTHORITY = "0ad6cc4e"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
FORMAT = "lisp65-c2.3-v1.6-first-event-bitstream-patch-attribution-v1"

CORE_PATHS = {
    "Makefile": "Makefile",
    "monitor_source": "src/monitor/monitor.a65",
    "monitor_bus": "src/verilog/monitor_bus.v",
    "monitor_top": "src/verilog/monitor_top.v",
    "monitor_control": "src/verilog/monitor_ctrl.v",
    "r6_implementation": "vivado/mega65r6_impl.tcl",
    "mempacker": "src/tools/mempacker/mempacker_v.c",
    "bitinfo": "src/tools/bitinfo.c",
    "bit2mcs": "src/tools/bit2mcs.c",
    "hotpatch": "src/tools/hotpatch/hotpatch.c",
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(*args: str, cwd: Path = ROOT, allow_miss: bool = False) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if not allow_miss:
        require(result.returncode == 0,
                f"command red ({' '.join(args)}): {result.stderr.decode(errors='replace')}")
    return result


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    return run("git", "show", f"{commit}:{path}", cwd=repo).stdout


def git_binding(repo: Path, commit: str, path: str) -> dict[str, Any]:
    raw = git_blob(repo, commit, path)
    return {"authority": "git-blob", "commit": commit, "path": path,
            "bytes": len(raw), "sha256": sha(raw)}


def text(path: str) -> str:
    return git_blob(CORE, CORE_COMMIT, path).decode()


def authority() -> dict[str, Any]:
    commit = run("git", "rev-parse", f"{AUTHORITY}^{{commit}}").stdout.decode().strip()
    binding = git_binding(ROOT, commit, PLAN.relative_to(ROOT).as_posix())
    raw = git_blob(ROOT, commit, binding["path"]).decode()
    compact = " ".join(raw.lower().split())
    for token in (
        "can the one-byte monitor change plus breakpoint land by bitstream patching",
        "if synthesis is unavoidable: the owner decides",
        "no core build, no flash, no device contact",
    ):
        require(token in compact, f"question authority token absent: {token}")
    return binding


def core_binding() -> dict[str, Any]:
    observed = run("git", "rev-parse", "HEAD", cwd=CORE).stdout.decode().strip()
    require(observed == CORE_COMMIT, "bound MEGA65 core checkout drift")
    return {
        "repository": "MEGA65/mega65-core",
        "commit": observed,
        "sources": {name: git_binding(CORE, CORE_COMMIT, path)
                    for name, path in CORE_PATHS.items()},
    }


def tracked_inventory() -> tuple[list[str], list[str]]:
    paths = run("git", "ls-tree", "-r", "--name-only", CORE_COMMIT,
                cwd=CORE).stdout.decode().splitlines()
    metadata = [path for path in paths
                if path.lower().endswith((".mmi", ".bmm"))]
    patch_names = [path for path in paths
                   if any(token in path.lower() for token in
                          ("updatemem", "data2mem", "bitpatch", "bitstream_patch"))]
    return metadata, patch_names


def source_facts() -> dict[str, Any]:
    make = text(CORE_PATHS["Makefile"])
    monitor = text(CORE_PATHS["monitor_source"])
    bus = text(CORE_PATHS["monitor_bus"])
    top = text(CORE_PATHS["monitor_top"])
    ctrl = text(CORE_PATHS["monitor_control"])
    impl = text(CORE_PATHS["r6_implementation"])
    mempacker = text(CORE_PATHS["mempacker"])
    bitinfo = text(CORE_PATHS["bitinfo"])
    bit2mcs = text(CORE_PATHS["bit2mcs"])
    hotpatch = text(CORE_PATHS["hotpatch"])

    for token in (
        "$(BINDIR)/monitor.m65:",
        "$(VERILOGSRCDIR)/monitor_mem.v:",
        "mempacker_v -n monitormem -w 12 -s 4096",
        "$(BINDIR)/monitor.m65@0000",
    ):
        require(token in make, f"monitor image build edge absent: {token}")
    require("launch_runs impl_1" in impl and "write_bitstream" in impl,
            "r6 implementation no longer synthesizes/writes a bitstream")
    require("cmp         #3" in monitor and "accept up to 3 hex digits" in monitor,
            "one-byte monitor aperture source absent")
    require(".org    $f000" in monitor and ".advance  $f200" in monitor,
            "monitor ROM/RAM image layout drift")
    require("$0000-$01ff - RAM" in bus and "$f000-$ffff - Monitor \"ROM\"" in bus,
            "monitor private memory decode drift")
    require("ram_write = cpu_write" in bus
            and bus.count("ram_write = cpu_write") == 1,
            "monitor ROM unexpectedly became runtime-writable")
    require("monitormem monitormem" in top and ".we(ram_write)" in top,
            "monitor memory write topology drift")
    require("monitor_break_addr == monitor_pc && monitor_break_en" in ctrl,
            "stock address-only breakpoint predicate drift")
    require("input [7:0]" in ctrl and "cpu_state" in ctrl,
            "CPU decode state no longer reaches monitor control")
    require("cpu_state !=" in ctrl and "cpu_state_write" in ctrl,
            "CPU state is not consumed by recent-state recording")

    metadata, patch_names = tracked_inventory()
    require(metadata == [] and patch_names == [],
            "core tree gained a supported memory-map/bitstream patch route")
    forbidden = run(
        "git", "grep", "-n", "-I", "-E",
        r"updatemem|data2mem|write_mem_info|\\.mmi|\\.bmm|bitstream[ _-]*patch",
        CORE_COMMIT, "--", ":!src/verilog/monitor_mem.v",
        cwd=CORE, allow_miss=True)
    require(forbidden.returncode == 1 and forbidden.stdout == b"",
            "core tree now names a bitstream-memory patch route")

    require("verilog source file" in mempacker.lower(),
            "mempacker is no longer an HDL generator")
    require("usage: bitinfo <bitstream file>" in bitinfo,
            "bitinfo role drift")
    require("xilinx bitstream files to flashable files" in bit2mcs.lower(),
            "bit2mcs role drift")
    require("oldmem" in hotpatch and "64KB memory dump" in hotpatch,
            "hotpatch stopped describing a CPU-memory context")

    # MONITOR.M65 is a separately supplied Freezer utility.  The embedded monitor
    # image has a distinct producer and name under bin/, so it is not a runtime
    # loader for monitor-private FPGA RAM.
    require("$(SDCARD_DIR)/MONITOR.M65" in make
            and "$(BINDIR)/monitor.m65:" in make,
            "Freezer utility / embedded monitor distinction drift")

    return {
        "monitor_content_pipeline": [
            "src/monitor/monitor.a65",
            "bin/monitor.m65 (Ophis)",
            "src/verilog/monitor_mem.v (mempacker_v HDL generation)",
            "Vivado synth/implementation/write_bitstream",
        ],
        "monitor_byte": {
            "change": "CMP #3 -> CMP #4",
            "shape": "one BRAM-init content byte; size-neutral",
            "standalone_supported_patch_route": False,
            "why": (
                "the bound tree emits the initial contents into generated Verilog before "
                "synthesis and ships neither .mmi/.bmm mapping metadata nor an updatemem/"
                "data2mem-class target"),
        },
        "runtime_patch_route": {
            "present": False,
            "why": (
                "monitor-private writes decode only $0000-$01ff; monitor code begins at "
                "$f200 and the $f000-$ffff decode is read-only"),
            "freezer_MONITOR_M65": (
                "separate SD-card Freezer utility, not bin/monitor.m65 and not a loader "
                "for monitor-private BRAM"),
        },
        "stock_breakpoint": {
            "predicate": "monitor_break_addr == monitor_pc && monitor_break_en",
            "cpu_state_available": True,
            "cpu_state_role": "history/recent-state recording only",
            "state_qualification_configurable": False,
            "existing_hooks": (
                "trace-control bits provide address break, flag break, watch and history; "
                "they are independent triggers, not a PC AND decode-state predicate"),
        },
        "available_core_utilities": {
            "mempacker_v": "binary-to-Verilog generator before synthesis",
            "bitinfo": "bitstream packet inspector; no writer",
            "bit2mcs": "bitstream packaging/conversion; no logic or BRAM editor",
            "hotpatch": "64-KiB target CPU memory-context translator; not FPGA configuration",
        },
        "tracked_patch_metadata": metadata,
        "tracked_patch_tools": patch_names,
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == "DECIDED: COMPLETE WITNESS REQUIRES SYNTHESIS",
            "route verdict drift")
    facts = value["facts"]
    require(facts["monitor_byte"]["standalone_supported_patch_route"] is False,
            "unsupported BRAM patch route accepted")
    require(facts["runtime_patch_route"]["present"] is False,
            "nonexistent monitor runtime loader accepted")
    bp = facts["stock_breakpoint"]
    require(bp["state_qualification_configurable"] is False
            and bp["cpu_state_available"] is True,
            "stock breakpoint capability drift")
    decision = value["decision"]
    require(decision["question_1_answer"] == "NO"
            and decision["complete_witness_by_bitstream_patching"] is False
            and decision["synthesis_unavoidable"] is True,
            "complete-witness route was not closed")
    require(decision["rom_byte_alone_sufficient"] is False,
            "content-only patch was mistaken for complete witness")
    require(value["execution_lock"] == {
        "core_sources_changed": 0, "toolchains_installed": 0,
        "core_builds": 0, "bitstreams_written": 0,
        "bitstreams_loaded": 0, "device_contacts": 0,
    }, "host-only question crossed its authority")


def derive() -> dict[str, Any]:
    facts = source_facts()
    value = {
        "format": FORMAT,
        "status": "DECIDED: COMPLETE WITNESS REQUIRES SYNTHESIS",
        "recorded_on": "2026-08-24",
        "authority": authority(),
        "inputs": {"core": core_binding()},
        "facts": facts,
        "decision": {
            "question_1_answer": "NO",
            "complete_witness_by_bitstream_patching": False,
            "synthesis_unavoidable": True,
            "rom_byte_alone_sufficient": False,
            "reason": (
                "BRAM-init patching can change contents only. The required PC=$8041 AND "
                "decode-state=$13/$14 predicate is absent from the configured monitor and "
                "requires new RTL/LUT/interconnect. The bound build also exposes no supported "
                "post-implementation monitor-BRAM patch path for the independent one-byte edit."),
            "route_1": "CLOSED",
            "next_owner_question": (
                "whether to install/use the Vivado core toolchain for one volatile diagnostic "
                "core with synthesis, implementation and timing proof"),
            "fallback": "not priced; remains weaker statistical evidence only",
        },
        "claim_boundary": (
            "This attribution answers patchability only. It authorizes no toolchain install, "
            "core edit/build, bitstream production/load, flash operation or device contact."),
        "execution_lock": {
            "core_sources_changed": 0, "toolchains_installed": 0,
            "core_builds": 0, "bitstreams_written": 0,
            "bitstreams_loaded": 0, "device_contacts": 0,
        },
    }
    validate(value)
    return value


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "invent-bram-patch-route": lambda row: row["facts"]["monitor_byte"].update(
            standalone_supported_patch_route=True),
        "invent-runtime-loader": lambda row: row["facts"]["runtime_patch_route"].update(
            present=True),
        "invent-state-hook": lambda row: row["facts"]["stock_breakpoint"].update(
            state_qualification_configurable=True),
        "claim-content-is-complete": lambda row: row["decision"].update(
            rom_byte_alone_sufficient=True),
        "claim-no-synthesis": lambda row: row["decision"].update(
            synthesis_unavoidable=False),
        "spend-core-build": lambda row: row["execution_lock"].update(core_builds=1),
        "spend-contact": lambda row: row["execution_lock"].update(device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "bitstream-route mutation survived")
    return rejected


def main(argv: list[str]) -> int:
    require(len(argv) == 2 and argv[1] in {"check", "write"},
            "usage: c2_v160_first_event_bitstream_patch_attribution.py check|write")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if argv[1] == "write":
        OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    else:
        require(OUT.is_file(), f"attribution receipt absent: {OUT}")
        require(json.loads(OUT.read_text(encoding="utf-8")) == value,
                "recorded bitstream-patch attribution drift")
    print("v1.6 first-event bitstream patch attribution: PASS "
          "route1=no synthesis=yes monitor-byte=unsupported qualifier=rtl mutations=7")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"v1.6 first-event bitstream patch attribution: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
