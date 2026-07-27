#!/usr/bin/env python3
"""Pure Class-A gate replay for the split-family alias harness correction."""

import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_coresident_diet_probe as PROBE  # noqa: E402
import c2_lite_v6_coresident_diet_successor_probe as SUCCESSOR  # noqa: E402


ARTIFACT_OUT = ROOT / "build/c2-lite/v6-coresident-diet-successor-wplto-probe"
OUT = ROOT / "build/c2-lite/v6-coresident-diet-successor-gate-replay"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-gate-replay-receipt.json")
PATH_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-wplto-probe-receipt.json")


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def build() -> dict:
    PROBE.require(not OUT.exists() and not RECEIPT.exists(),
                  "gate replay is one-shot and already exists")
    PROBE.require(PATH_FIRST_RED.is_file(), "path-harness First Red absent")
    full = ARTIFACT_OUT / "full-product-wplto"
    target = full / "c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    for path in (target, elf, Path(str(target) + ".map"),
                 full / "runtime-overlays-boot-c2-lite.bin",
                 full / "runtime-overlays-session-c2-lite.bin"):
        PROBE.require(path.is_file() and path.stat().st_mode & 0o222 == 0,
                      f"immutable replay input absent or writable: {path}")

    OUT.mkdir(parents=True)
    aliases = {
        "runtime-overlays-final.bin":
            full / "runtime-overlays-session-c2-lite.bin",
        "runtime-overlays-boot-final.bin":
            full / "runtime-overlays-boot-c2-lite.bin",
        "runtime-overlays-session-final.bin":
            full / "runtime-overlays-session-c2-lite.bin",
    }
    alias_report = {}
    for name, source in aliases.items():
        destination = OUT / name
        shutil.copyfile(source, destination)
        PROBE.require(PROBE.sha(source) == PROBE.sha(destination),
                      f"family replay alias differs: {name}")
        alias_report[name] = {"source": PROBE.bind(source),
                              "alias": PROBE.bind(destination)}

    # The artifact root remains the completed WPLTO.  Only gate reports and
    # canonical compatibility aliases are written under OUT.
    PROBE.OUT = ARTIFACT_OUT
    wplto, replay_target, replay_elf = SUCCESSOR.replay_existing_wplto()
    PROBE.require(replay_target == target and replay_elf == elf,
                  "pure replay selected a different product identity")
    structural = PROBE.COLD.structural_gates(target, elf, report_out=OUT)
    capacity = PROBE.capacity_gate(wplto, elf)
    semantic = PROBE.semantic_product_gate(wplto, target, elf)
    root = PROBE.ROOT_GATE.collect()
    PROBE.require(root["status"] == "pass", "root-surrogate gate replay red")

    value = {
        "format": "lisp65-c2-lite-v6-coresident-diet-gate-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-pure-gate-replay-no-compiler-no-link-no-hardware",
        "scope": {"class": "A", "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0,
                  "product_bytes_changed": 0, "capacity_effect_bytes": 0},
        "first_red": PROBE.bind(PATH_FIRST_RED),
        "harness_correction": {
            "cause": (
                "one-truth closure expected a historical combined-family "
                "filename although C2-lite emits canonical Boot and Session packs"),
            "fix": (
                "expose SHA-identical read-only compatibility aliases only in "
                "the gate-report directory; do not repack or relink"),
            "aliases": alias_report,
        },
        "immutable_inputs": {
            "measurement_prg": PROBE.bind(target),
            "measurement_elf": PROBE.bind(elf),
            "measurement_map": PROBE.bind(Path(str(target) + ".map")),
            "saved_lto_object": PROBE.bind(Path(str(target) + ".lto.o")),
        },
        "whole_program_lto_reconstruction": wplto,
        "co_resident_capacity": capacity,
        "product_semantics": semantic,
        "permanent_root_surrogate_gate": root,
        "fresh_structural_gates": structural,
        "claim_limit": (
            "Pure gates over one immutable nonpromotable WPLTO identity. No "
            "compiler, link, hardware, product, promotion or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    PROBE.write_json(OUT / "coresident-diet-gate-replay.json", value)
    value["replay_report"] = PROBE.bind(
        OUT / "coresident-diet-gate-replay.json")
    PROBE.write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        failure = {
            "format": "lisp65-c2-lite-v6-coresident-diet-gate-replay-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: pure gate replay",
            "failure": str(error),
            "scope": {"compiler_runs": 0, "linker_runs": 0,
                      "product_links": 0, "hardware_runs": 0},
            "next_gate": "Class-A correction or Class-C review if product-facing",
        }
        if not RECEIPT.exists():
            PROBE.write_json(RECEIPT, failure)
        if OUT.exists():
            protect()
        print("c2-lite-v6-coresident-diet-gate-replay: FIRST RED " + str(error))
        return 2
    capacity = value["co_resident_capacity"]
    print("c2-lite-v6-coresident-diet-gate-replay: PASS "
          f"session={capacity['session_family_bytes']} "
          f"headroom={capacity['session_family_headroom_bytes']} "
          f"crc-metadata={capacity['fused_section_bytes']['crc_metadata']} "
          f"publish-exports={capacity['fused_section_bytes']['publish_exports']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
