#!/usr/bin/env python3
"""Build the DWX headless Xemu fork with a monotonic emulated-cycle probe."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
from typing import Any
import dwx_keymap_transport as KEYMAP


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/dwx-cycle-probe-adapter-contract.json"
HEADLESS_PATH = ROOT / "config/dwx-headless-input-adapter-contract.json"
LINK73_PATH = ROOT / "config/dwx-xemu-link73-contract.json"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, check=True, **kwargs)


def validate_contract(contract: dict[str, Any], headless: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-cycle-probe-adapter-contract-v1"
        and contract.get("status") == "ACTIVE"
        and contract.get("base_contract") == "config/dwx-headless-input-adapter-contract.json",
        "cycle-probe contract header drift",
    )
    transport = contract.get("transport")
    require(
        isinstance(transport, dict)
        and transport.get("base_commands") == headless["transport"]["commands"]
        and transport.get("added_commands") == ["~cyclecount", "~typeone"]
        and transport.get("counter") == "monotonic-emulated-CPU-and-DMA-cycles"
        and transport.get("desktop_focus_required") is False
        and transport.get("gui_required") is False
        and transport.get("logs_are_oracle") is False,
        "cycle-probe transport drift",
    )
    completion = contract.get("completion_semantics")
    reference = completion.get("hardware_reference") if isinstance(completion, dict) else None
    require(
        "completion_patch" not in contract
        and isinstance(completion, dict)
        and completion.get("status_register") == "$D082"
        and completion.get("successful_buffered_read_status_mask") == "$40"
        and completion.get("predicate_mask") == "$D8"
        and completion.get("device_core_commit") == "03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6"
        and isinstance(reference, dict)
        and reference.get("path") == "docs/reference/mega65-chipset-reference.pdf"
        and reference.get("sha256") == sha256(ROOT / reference["path"])
        and reference.get("pdf_page") == 135
        and reference.get("printed_page") == 121
        and reference.get("section") == "Buffered Sector Operations",
        "F011 buffered-read completion contract drift",
    )


def safe_extract(archive: bytes, destination: Path) -> None:
    destination_abs = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as handle:
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            require(
                target == destination_abs or destination_abs in target.parents,
                f"unsafe archive member: {member.name}",
            )
        handle.extractall(destination)


def verify_sources(root: Path) -> None:
    mega_h = (root / "targets/mega65/mega65.h").read_text(encoding="utf-8")
    mega_c = (root / "targets/mega65/mega65.c").read_text(encoding="utf-8")
    uart_c = (root / "targets/mega65/uart_monitor.c").read_text(encoding="utf-8")
    f011_c = (root / "xemu/f011_core.c").read_text(encoding="utf-8")
    require("extern Uint64 dwx_cpu_cycles_total;" in mega_h, "cycle declaration absent")
    require("dwx_cpu_cycles_total += (Uint64)dwx_step_cycles;" in mega_c, "cycle accumulation absent")
    require('if (!strcmp(cmd, "cyclecount"))' in uart_c, "cycle command absent")
    require('else if (!strncmp(cmd, "typeone", 7))' in uart_c, "single-byte command absent")
    require("hwa_kbd_set_fake_key((high << 4) | low);" in uart_c, "single-byte HWA injection absent")
    require(
        sha256(root / "xemu/f011_core.c") == "d8b5b3fc6d1ba202b7e4b4d79a17b3c78b0702030a09a39786f50cfd81b29611",
        "upstream F011 body changed; withdrawn EQ patch or another change present",
    )
    require(
        f011_c.count("DRV_STATUS_A(drive) |= 32;   // full buffered read: disk and CPU pointers are equal") == 0
        and f011_c.count("DRV_STATUS_A(drive) &= ~32;  // clear EQ, missing this in general freezes DOS") == 2,
        "F011 EQ-clear read/write population changed",
    )


def build(source: Path, output: Path, prefix: list[str]) -> dict[str, Any]:
    contract = load(CONTRACT_PATH)
    headless = load(HEADLESS_PATH)
    link73 = load(LINK73_PATH)
    validate_contract(contract, headless)
    revision = run(["git", "-C", str(source), "rev-parse", "HEAD"], stdout=subprocess.PIPE).stdout.decode().strip()
    require(revision == link73["xemu_source"]["commit"], "Xemu revision drift")
    output = output.resolve()
    build_root = (ROOT / "build").resolve()
    require(output != build_root and build_root in output.parents, "output must be below build/")
    require(not output.exists(), f"output already exists: {output}")
    output.mkdir(parents=True)
    archive = run(["git", "-C", str(source), "archive", revision], stdout=subprocess.PIPE).stdout
    safe_extract(archive, output)
    patches = []
    for role, relative in (
        ("base_patch", headless["base_patch"]),
        ("transport_patch", headless["transport_patch"]),
        ("cycle_patch", contract["cycle_patch"]),
    ):
        patch = ROOT / relative
        run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=output)
        patches.append({"role": role, "path": relative, "sha256": sha256(patch)})
    keymap_transport = KEYMAP.generate_and_check(output)
    verify_sources(output)
    env = dict(os.environ)
    env.update({"TRAVIS_BRANCH": "dwx-cycle-probe", "TRAVIS_COMMIT": revision})
    run(prefix + ["make", "-C", str(output / "targets/mega65"), "-j2"], env=env)
    binary = output / "build/bin/xmega65.native"
    require(binary.is_file(), "cycle-probe Xemu binary absent")
    source_paths = (
        "targets/mega65/sdcard.c",
        "targets/mega65/io_mapper.c",
        "targets/mega65/inject.h",
        "targets/mega65/inject.c",
        "targets/mega65/input_devices.c",
        "targets/mega65/mega65.h",
        "targets/mega65/mega65.c",
        "targets/mega65/uart_monitor.c",
        "xemu/f011_core.c",
        KEYMAP.HEADER,
    )
    manifest = {
        "format": "lisp65-dwx-xemu-cycle-probe-build-v1",
        "status": "PASS",
        "source_commit": revision,
        "base_qualified_tool_identity": load(ROOT / "config/dwx-prefilter-blind-spot-contract.json")["qualified_tool_identity"],
        "patches": patches,
        "keymap_transport": keymap_transport,
        "patched_source_sha256": {relative: sha256(output / relative) for relative in source_paths},
        "binary": {"path": str(binary), "sha256": sha256(binary)},
        "transport": deepcopy(contract["transport"]),
        "claim_limit": contract["claim_limit"],
    }
    (output / "dwx-xemu-cycle-probe-adapter.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def selftest() -> None:
    contract = load(CONTRACT_PATH)
    headless = load(HEADLESS_PATH)
    validate_contract(contract, headless)
    mutations: dict[str, dict[str, Any]] = {}
    for field in ("desktop_focus_required", "gui_required", "logs_are_oracle"):
        value = deepcopy(contract)
        value["transport"][field] = True
        mutations[f"{field}-enabled"] = value
    value = deepcopy(contract)
    value["transport"]["base_commands"].remove("~screen")
    mutations["base-command-population-shortened"] = value
    value = deepcopy(contract)
    value["transport"]["added_commands"] = ["~wallclock", "~typeone"]
    mutations["cycle-command-replaced"] = value
    value = deepcopy(contract)
    value["completion_patch"] = "tools/xemu-patches/mega65-f011-buffered-read-eq.patch"
    mutations["withdrawn-completion-patch-reintroduced"] = value
    value = deepcopy(contract)
    value["completion_semantics"]["successful_buffered_read_status_mask"] = "$60"
    mutations["completion-status-eq-reintroduced"] = value
    for name, mutation in mutations.items():
        try:
            validate_contract(mutation, headless)
        except ProbeError:
            continue
        raise ProbeError(f"cycle-probe mutation survived: {name}")
    print("dwx cycle-probe adapter SELFTEST PASS mutations=7 focus=0 GUI=0 fork-patches=3")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--build-prefix", default=os.environ.get("DWX_XEMU_BUILD_PREFIX", ""))
    args = parser.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
    require(args.source is not None and args.output is not None, "--source and --output required")
    result = build(args.source.resolve(), args.output, shlex.split(args.build_prefix))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ProbeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"dwx-cycle-probe-adapter: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
