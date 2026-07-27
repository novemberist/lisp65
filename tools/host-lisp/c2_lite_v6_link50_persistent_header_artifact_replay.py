#!/usr/bin/env python3
"""Pure final qualification replay for product Link 50."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link49_persistent_header_artifact_replay as REPLAY  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-50-c2-lite-v6-persistent-header")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-structural-receipt.json")
STRUCTURAL_SHA = (
    "1fe1abbed824968c26b5a19175a6bff3c8de8d84e6d13b3e9c1584b558ba567f")
WPLTO = EVIDENCE / (
    "c2.2-link49-persistent-header-artifact-replay-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/product-link-50-persistent-header-artifact-replay")
RECEIPT = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-"
    "artifact-replay-structural-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-50 replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {
                "bytes": path.stat().st_size,
                "mode": oct(path.stat().st_mode & 0o777),
                "sha256": sha(path)}
            for path in sorted(root.rglob("*")) if path.is_file()}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def configure() -> None:
    REPLAY.SOURCE = SOURCE
    REPLAY.PRODUCT = PRODUCT
    REPLAY.ELF = ELF
    REPLAY.MAP = MAP
    REPLAY.OUT = OUT
    REPLAY.RECEIPT = RECEIPT
    base = REPLAY.BASE
    base.SOURCE = SOURCE
    base.PRODUCT = PRODUCT
    base.ELF = ELF
    base.MAP = MAP
    base.OUT = OUT
    base.RECEIPT = RECEIPT
    base.VERIFIER_BASE = REPLAY.VERIFIER_BASE
    base.configure_profile()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-50 artifact replay is one-shot")
    require(STRUCTURAL.is_file() and sha(STRUCTURAL) == STRUCTURAL_SHA,
            "Link-50 structural authority drift")
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(structural["status"] ==
                "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and structural["link_number"] == 50
            and structural["product_identity"]["product"]["sha256"] ==
                "3e13c9101b53ba89b8fb33e0f11c641ca53803b3f447831c5e1243475f7bc216"
            and structural["fresh_replacement_gates"]["walls"]
                ["e000_headroom_bytes"] == 58,
            "Link-50 structural receipt is not the completed link truth")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "Link-50 product tree is not read-only")
    OUT.mkdir(parents=True)
    configure()

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"Link-50 replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    old_out = REPLAY.BASE.BASE_LINK.OUT
    try:
        REPLAY.BASE.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = REPLAY.BASE.generic_gate_evidence()
        replacement = REPLAY.replay_gates()
    finally:
        subprocess.run = original_run
        REPLAY.BASE.BASE_LINK.OUT = old_out
    after = snapshot(SOURCE)
    require(before == after, "Link-50 replay modified the product tree")
    require(replacement["walls"] ==
                structural["fresh_replacement_gates"]["walls"]
            and replacement["append_phase_plan"]["linked"]["plan_data"]
                ["lisp65_c2_append_persistent_publish_plan"]["bytes"] ==
                [38, 39, 40, 41, 0],
            "Link-50 fresh replay differs from its product receipt")

    value = {
        "format": "lisp65-c2-lite-v6-link50-persistent-header-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-new-c2-lite-persistent-header-identity-hardware-not-run",
        "promotable": False,
        "link_number": 50,
        "authority": {
            "completed_link_receipt": bind(STRUCTURAL),
            "green_WPLTO": bind(WPLTO),
            "replay_driver": bind(Path(__file__))},
        "class_a_correction": {
            "historical_postcheck": "Link-48 required E000 >= 115",
            "current_contract": "C2-lite Hybrid requires E000 >= 54",
            "measured_e000_headroom_bytes": 58,
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0},
        "fresh_generic_gates": generic,
        "fresh_replacement_gates": replacement,
        "product_identity": {"product": bind(PRODUCT), "elf": bind(ELF),
                             "map": bind(MAP)},
        "protected_planes": {
            "c2d": bind(SOURCE / (
                "fresh-c2-lite-prelink-gates/v6-semantics/"
                "initial.c2d-v6.bin")),
            "bank2_static": bind(SOURCE / (
                "fresh-c2-lite-prelink-gates/v6-semantics/"
                "bank2-static-code.bin")),
        },
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "new_product_links": 0, "hardware_runs": 0,
            "product_link_runs_in_authority": 1,
            "read_only_tool_invocations": commands},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "claim_limit": (
            "Structurally complete Link 50; hardware and latency are not run, "
            "promotion and acceptance remain blocked."),
        "next_gate": "hardware presmoke from line 1, then the defun path",
    }
    report = OUT / "artifact-replay-report.json"
    write(report, value)
    value["replay_report"] = bind(report)
    write(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-lite-v6-link50-persistent-header-replay: FIRST RED "
              + str(error), file=sys.stderr)
        return 2
    walls = value["fresh_replacement_gates"]["walls"]
    print("c2-lite-v6-link50-persistent-header-replay: PASS "
          f"product={value['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
