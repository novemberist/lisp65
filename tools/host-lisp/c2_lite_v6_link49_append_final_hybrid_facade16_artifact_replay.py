#!/usr/bin/env python3
"""Complete product Link 49 from its immutable post-link artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_final_island_identity_successor_link as FINAL  # noqa: E402
import c2_lite_v6_link48_append_final_hybrid_facade16_artifact_replay as GATES  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as LINK49  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-49-c2-lite-v6-append-final-hybrid-facade16-"
    "artifact-replay")
SOURCE = LINK49.OUT
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
EVIDENCE = LINK49.EVIDENCE
FIRST_RED = LINK49.RECEIPT
RECEIPT = EVIDENCE / (
    "c2.2-product-link49-c2-lite-v6-append-final-hybrid-facade16-"
    "artifact-replay-structural-receipt.json")
AUTHORITY_SOURCE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link49-facade16-artifact-replay-"
    "authority-source-first-red.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def configure() -> None:
    GATES.BASE_LINK.configure_profile()
    GATES.CONS.RF.configure_roots_fronts()
    GATES.CONS.CONS.configure_publish_clear()
    GATES.P.configure_c2_lite_hybrid_e000_geometry()
    GATES.P.configure_append_plan_facade()
    for module in (GATES.BASE_LINK, GATES.STAGE, GATES.ART):
        module.VERIFIER_BASE = GATES.VERIFIER_BASE


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-49 artifact replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(AUTHORITY_SOURCE_FIRST_RED.is_file(),
            "artifact-replay authority-source First Red absent")
    require(first["status"] == "FIRST RED: C2-lite real-ABI Link 49 stopped"
            and first["diagnostic"] == {
                "type": "LinkError",
                "message": "Link-41 roots/fronts aggregate accounting red"}
            and first["execution_accounting"]["product_closure_links"] == 1
            and first["execution_accounting"]["hardware_runs"] == 0,
            "Link-49 checker-model First Red authority drift")
    require(all(path.is_file() for path in (PRODUCT, ELF, MAP)),
            "Link-49 frozen product artifacts absent")
    before = GATES.snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "Link-49 frozen product tree is not read-only")
    OUT.mkdir(parents=True)
    configure()
    original = {
        "source": GATES.SOURCE, "product": GATES.PRODUCT,
        "elf": GATES.ELF, "map": GATES.MAP, "out": GATES.OUT,
        "base_out": GATES.BASE_LINK.OUT,
        "run": subprocess.run,
    }
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"Link-49 pure replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original["run"](command, *args, **kwargs)

    try:
        GATES.SOURCE = SOURCE
        GATES.PRODUCT = PRODUCT
        GATES.ELF = ELF
        GATES.MAP = MAP
        GATES.OUT = OUT
        GATES.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = GATES.generic_gate_evidence()
        replay = GATES.read_only_replay()
        walls, family = GATES.BASE_LINK.walls_and_family(ELF)
        shape = {"walls": walls,
                 "runtime_slices": family["runtime_slices"],
                 "successor_bank3_pack": family["successor_bank3_pack"]}
        inherited = FINAL.capacity_gate(shape, ELF)
    finally:
        subprocess.run = original["run"]
        GATES.SOURCE = original["source"]
        GATES.PRODUCT = original["product"]
        GATES.ELF = original["elf"]
        GATES.MAP = original["map"]
        GATES.OUT = original["out"]
        GATES.BASE_LINK.OUT = original["base_out"]
    after = GATES.snapshot(SOURCE)
    require(before == after, "Link-49 replay modified its frozen artifacts")
    require(inherited["status"] == "passed"
            and inherited["current_append_geometry"]
            and inherited["session_catalog_records_after"] == 49
            and inherited["session_family_bytes"] == 65438
            and inherited["publication_section"] ==
                ".lisp65_rt_c2append_publish_clear",
            "corrected inherited aggregate gate is red")
    value = {
        "format": "lisp65-c2-lite-v6-link49-facade16-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-new-c2-lite-facade16-identity-hardware-not-run",
        "link_number": 49,
        "promotable": False,
        "authority": {
            "checker_model_first_red": GATES.bind(FIRST_RED),
            "authority_source_first_red": GATES.bind(
                AUTHORITY_SOURCE_FIRST_RED),
            "qualified_wplto": GATES.bind(LINK49.WPLTO),
            "driver": GATES.bind(Path(__file__))},
        "class_a_correction": {
            "historical_session_records": 50,
            "current_session_records": 49,
            "historical_append_records": 23,
            "current_append_records": 22,
            "historical_publication":
                ".lisp65_rt_c2append_publish_exports",
            "current_publication": ".lisp65_rt_c2append_publish_clear",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0},
        "fresh_corrected_inherited_gate": inherited,
        "fresh_generic_gates": generic,
        "fresh_replacement_gates": replay,
        "product_identity": {
            "product": GATES.bind(PRODUCT), "elf": GATES.bind(ELF),
            "map": GATES.bind(MAP)},
        "rollback_line": {
            **GATES.bind(LINK49.BASELINE), "status": "untouched"},
        "execution_accounting": {
            "product_closure_links": 1,
            "additional_compiler_runs": 0,
            "additional_linker_runs": 0,
            "hardware_runs": 0,
            "read_only_tool_invocations": commands},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "claim_limit": (
            "Structurally complete Link 49; no hardware, latency, promotion "
            "or acceptance claim."),
        "next_gate": "owner-authorized hardware presmoke from line 1",
    }
    report = OUT / "link49-facade16-artifact-replay.json"
    write(report, value)
    value["replay_report"] = GATES.bind(report)
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
        print("c2-lite-v6-link49-facade16-artifact-replay: FIRST RED "
              + str(error), file=sys.stderr)
        return 2
    walls = value["fresh_replacement_gates"]["walls"]
    print("c2-lite-v6-link49-facade16-artifact-replay: PASS "
          f"product={value['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
