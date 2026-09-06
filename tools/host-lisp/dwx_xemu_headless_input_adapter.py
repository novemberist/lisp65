#!/usr/bin/env python3
"""Build the DWX Xemu fork with a focus-free scripted-input transport."""

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


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/dwx-headless-input-adapter-contract.json"
LINK73_PATH = ROOT / "config/dwx-xemu-link73-contract.json"


class AdapterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AdapterError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot load {path}: {error}") from error
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


def validate_contract(contract: dict[str, Any], link73: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-headless-input-adapter-contract-v1"
        and contract.get("status") == "ACTIVE",
        "headless-input adapter contract header drift",
    )
    require(
        contract.get("base_contract") == "config/dwx-xemu-link73-contract.json"
        and contract.get("base_patch") == link73["adapter"]["patch"],
        "headless-input adapter lost the qualified F011 base",
    )
    transport = contract.get("transport")
    require(
        isinstance(transport, dict)
        and transport.get("channel") == "local-unix-uart-monitor"
        and transport.get("commands") == ["~typehex", "~keyevent", "~typebusy", "~screen"]
        and transport.get("keymap_authority") == "config/v11-l-lite-keymap.json"
        and transport.get("keyboard_path")
        == "Xemu HWA ASCII/PETSCII queue consumed through $D610/$D619"
        and transport.get("desktop_focus_required") is False
        and transport.get("gui_required") is False
        and transport.get("screen_query_is_control_only") is True
        and transport.get("logs_are_oracle") is False,
        "focus-free transport contract drift",
    )


def verify_extension_sources(root: Path) -> None:
    inject_h = (root / "targets/mega65/inject.h").read_text(encoding="utf-8")
    inject_c = (root / "targets/mega65/inject.c").read_text(encoding="utf-8")
    input_c = (root / "targets/mega65/input_devices.c").read_text(encoding="utf-8")
    uart_c = (root / "targets/mega65/uart_monitor.c").read_text(encoding="utf-8")
    required = {
        "busy declaration": "inject_hwa_pasting_busy ( void )" in inject_h,
        "busy implementation": "return kbd_hwa_pasting != NULL;" in inject_c,
        "delete mapping": "asc = 0x14;\n\t\tpet = 0x14;" in input_c,
        "type command": 'else if (!strncmp(cmd, "typehex", 7))' in uart_c,
        "busy command": 'if (!strcmp(cmd, "typebusy"))' in uart_c,
        "screen command": 'else if (!strcmp(cmd, "screen"))' in uart_c,
        "HWA injector": "inject_hwa_pasting(text, 0)" in uart_c,
    }
    missing = [name for name, present in required.items() if not present]
    require(not missing, "headless-input patch is ineffective: " + ", ".join(missing))


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


def build(source: Path, output: Path, prefix: list[str]) -> dict[str, Any]:
    contract = load(CONTRACT_PATH)
    link73 = load(LINK73_PATH)
    validate_contract(contract, link73)
    revision = run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], stdout=subprocess.PIPE
    ).stdout.decode().strip()
    require(revision == link73["xemu_source"]["commit"], "Xemu revision drift")
    for relative, key in (
        ("targets/mega65/sdcard.c", "sdcard_c_sha256"),
        ("targets/mega65/io_mapper.c", "io_mapper_c_sha256"),
    ):
        require(
            sha256(source / relative) == link73["xemu_source"][key],
            f"Xemu source drift: {relative}",
        )
    output = output.resolve()
    build_root = (ROOT / "build").resolve()
    require(output != build_root and build_root in output.parents, "output must be below build/")
    require(not output.exists(), f"output already exists: {output}")
    output.mkdir(parents=True)
    archive = run(
        ["git", "-C", str(source), "archive", revision], stdout=subprocess.PIPE
    ).stdout
    safe_extract(archive, output)
    patches = []
    for role in ("base_patch", "transport_patch"):
        patch = ROOT / contract[role]
        run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=output)
        patches.append({"role": role, "path": contract[role], "sha256": sha256(patch)})
    from dwx_xemu_f011_adapter import verify_selected_views

    verify_selected_views((output / "targets/mega65/sdcard.c").read_text(encoding="utf-8"))
    import dwx_keymap_transport as KEYMAP
    keymap_transport = KEYMAP.generate_and_check(output)
    verify_extension_sources(output)
    env = dict(os.environ)
    env.update({"TRAVIS_BRANCH": "dwx-headless-input", "TRAVIS_COMMIT": revision})
    run(prefix + ["make", "-C", str(output / "targets/mega65"), "-j2"], env=env)
    binary = output / "build/bin/xmega65.native"
    require(binary.is_file(), "headless-input Xemu binary absent")
    sources = {}
    for relative in (
        "targets/mega65/sdcard.c",
        "targets/mega65/io_mapper.c",
        "targets/mega65/inject.h",
        "targets/mega65/inject.c",
        "targets/mega65/input_devices.c",
        "targets/mega65/uart_monitor.c",
        KEYMAP.HEADER,
    ):
        sources[relative] = sha256(output / relative)
    manifest = {
        "format": "lisp65-dwx-xemu-headless-input-adapter-build-v1",
        "status": "PASS",
        "source_commit": revision,
        "base_qualified_tool_identity": load(
            ROOT / "config/dwx-prefilter-blind-spot-contract.json"
        )["qualified_tool_identity"],
        "patches": patches,
        "keymap_transport": keymap_transport,
        "patched_source_sha256": sources,
        "binary": {"path": str(binary), "sha256": sha256(binary)},
        "transport": deepcopy(contract["transport"]),
        "claim_limit": contract["claim_limit"],
    }
    (output / "dwx-xemu-headless-input-adapter.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def selftest() -> None:
    contract = load(CONTRACT_PATH)
    link73 = load(LINK73_PATH)
    validate_contract(contract, link73)
    mutations: dict[str, dict[str, Any]] = {}
    for field in ("desktop_focus_required", "gui_required", "logs_are_oracle"):
        value = deepcopy(contract)
        value["transport"][field] = True
        mutations[f"{field}-enabled"] = value
    value = deepcopy(contract)
    value["transport"]["screen_query_is_control_only"] = False
    mutations["screen-query-promoted-to-oracle"] = value
    value = deepcopy(contract)
    value["transport"]["commands"].remove("~typebusy")
    mutations["transport-completion-status-omitted"] = value
    value = deepcopy(contract)
    value["base_patch"] = value["transport_patch"]
    mutations["qualified-f011-base-replaced"] = value
    for name, mutation in mutations.items():
        try:
            validate_contract(mutation, link73)
        except AdapterError:
            continue
        raise AdapterError(f"adapter mutation survived: {name}")
    require(len(mutations) == 6, "adapter mutation population drift")
    print("dwx headless-input adapter SELFTEST PASS mutations=6 focus=0 gui=0")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--build-prefix", default=os.environ.get("DWX_XEMU_BUILD_PREFIX", "")
    )
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
    except (AdapterError, OSError, subprocess.CalledProcessError) as error:
        print(f"dwx-headless-input-adapter: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
