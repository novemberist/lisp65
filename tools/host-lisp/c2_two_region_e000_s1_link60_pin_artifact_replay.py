#!/usr/bin/env python3
"""Read-only qualification of the sole Link-60 WPLTO artifact.

The closure link completed before the fixed-leaf gate encountered a historical
relocation-model assumption.  This replay consumes that immutable ELF, packs
the two runtime regions, measures every wall and reports the next contractual
pin without compiling, linking or patching product bytes.
"""

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
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_two_region_session_store_wplto as TWO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-final-wplto4")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
CONTRACT = SOURCE / "resolved-profile.txt"
FIRST_RED = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto4-internal.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-link60-pin-artifact-replay2")
RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-link60-pin-artifact-replay2-receipt.json")
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "product/substitution-artifacts.json")
EXPECTED_REGION1 = {
    "c2-append-rollback-wipe-plane",
    "c2-append-rollback-wipe-chip",
    "c2-append-rollback-wipe-attic",
}


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    PROFILE.configure()
    TWO.configure_two_region()
    P.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
    require(
        P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
        and P.SESSION_EMITTER_STATE_BYTES == 0
        and P.SESSION_EMITTER_STATE_BASE == 0xFD22
        and P.PROFILE_RODATA_BASE == 0xFD2C
        and P.FIXED_BANK0_CODE_BYTES == 69
        and P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D
        and P.fixed_bank0_contract_end() == 0xC354,
        "Link-60 replay profile geometry drift")


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-60 pin artifact replay is one-shot")
    require(all(path.is_file() for path in (
        PRODUCT, ELF, MAP, CONTRACT, FIRST_RED, PRODUCT_IDENTITY)),
        "Link-60 WPLTO artifact set is incomplete")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["diagnostic"]["type"] == "GateError"
        and first["diagnostic"]["message"].startswith(
            "fixed rtov_fail absolute data-edge drift:")
        and first["execution_accounting"]["product_closure_links"] == 1,
        "Link-60 fixed-leaf checker boundary drift")
    before = snapshot(SOURCE)
    require(
        before and all((int(row["mode"], 8) & 0o222) == 0
                       for row in before.values()),
        "Link-60 WPLTO tree is not read-only")

    OUT.mkdir(parents=True)
    configure()
    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(
            command[0] if isinstance(command, (list, tuple))
            else command)).name
        lowered = executable.lower()
        require(
            "clang" not in lowered and lowered not in {
                "cc", "gcc", "ld", "ld.lld", "lld", "mos-mega65-clang"},
            f"artifact replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = guarded_run
        fixed = P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-current.json")
        _boot_image, boot_manifest = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT, "boot", "unbound")
        _session_image, session_manifest = P.overlay_pack_family(
            OUT, PRODUCT, CONTRACT, "session", "unbound")
    finally:
        subprocess.run = original_run

    require(before == snapshot(SOURCE),
            "artifact replay modified the frozen WPLTO tree")
    sections = P.section_table(ELF)
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    region1 = [
        row for row in session["slices"] if int(row.get("region_id", 0)) == 1]
    overflow = session["overflow_storage"]
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE -
            (sections[".text"]["address"] + sections[".text"]["bytes"]),
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE -
            (sections[".bss"]["address"] + sections[".bss"]["bytes"]),
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes":
            2048 - sections[".lisp65_resident_island"]["bytes"],
        "e000_headroom_bytes":
            P.KERNAL_WINDOW_BYTES -
            sum(sections.get(name, {}).get("bytes", 0)
                for name in P.KERNAL_SECTIONS),
    }
    verifier = sections[P.VERIFIER_BINDING_SECTION]
    e000 = {
        "session_emitter_state":
            sections[".lisp65_c2_kernal_window.session_emitter_state"],
        "profile_rodata": sections[P.PROFILE_RODATA_SECTION],
    }
    capacity_green = (
        int(session["storage"]["size"]) <= 65536
        and 0 < int(overflow["used"]) <= 2032
        and {str(row["name"]) for row in region1} == EXPECTED_REGION1
        and all(int(row["file_size"]) <= 1792 for row in session["slices"]))
    walls_green = (
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54)
    geometry_green = (
        fixed["fixed_code"] == {
            "address": 0xC218, "bytes": 69, "end_exclusive": 0xC25D}
        and fixed["hot_bss"]["address"] == 0xC25D
        and fixed["hot_bss"]["contract_end_exclusive"] == 0xC354
        and [row["target"] for row in
             fixed["leaf"]["outgoing_control_edges"]] == ["rtov_wipe"]
        and [row["target"] for row in
             fixed["leaf"]["outgoing_absolute_data_edges"]]
            == ["rtov_fault", "rtov_fault", "rtov_fault"]
        and e000 == {
            "session_emitter_state": {"address": 0xFD22, "bytes": 0},
            "profile_rodata": {"address": 0xFD2C, "bytes": 342},
        })
    pin_green = verifier == {
        "address": P.VERIFIER_BINDING_BASE,
        "bytes": P.runtime_binding_bytes(),
    }
    require(walls_green and capacity_green and geometry_green,
            "Link-60 measured map has a non-pin structural red")
    require(not pin_green and verifier["address"] == 0xB972
            and P.VERIFIER_BINDING_BASE == 0xB94E,
            "expected current publish-last pin discrepancy is absent")

    value = {
        "format": "lisp65-c2-link60-pin-artifact-replay-v1",
        "recorded_on": "2026-07-24",
        "status":
            "FIRST RED: all walls and two-region geometry pass; "
            "publish-last verifier table requires owner re-pin",
        "promotable": False,
        "class_A_fixed_leaf_correction": {
            "cause":
                "the final linker expresses rtov_fault references as the "
                ".bss section symbol plus addend, not as the object name",
            "correction":
                "resolve each structured relocation through exactly one "
                "positive-sized Object interval",
            "resolved_data_targets": [
                row["target"] for row in
                fixed["leaf"]["outgoing_absolute_data_edges"]],
            "mutations_rejected": len(P.FIXED_BLOCK_LEAF.selftest()),
            "product_bytes_changed": 0,
        },
        "class_A_source_address_parser_correction": {
            "cause":
                "the v4 main/overflow source-base CLI options reused the "
                "16-bit runtime-overlay VMA parser",
            "correction":
                "source bases use an independent 28-bit DMA-domain parser; "
                "the common execution VMA remains bounded by MAX_VMA",
            "rejected_value_before": "0x08200000",
            "accepted_domain": "0x00000000..0x0fffffff",
            "product_bytes_changed": 0,
        },
        "walls": walls,
        "fixed_geometry": fixed,
        "e000_geometry": e000,
        "runtime_families": {
            "boot_bytes": boot["storage"]["size"],
            "session_main_bytes": session["storage"]["size"],
            "session_main_headroom_bytes":
                65536 - int(session["storage"]["size"]),
            "session_overflow_used_bytes": overflow["used"],
            "session_overflow_capacity_bytes": overflow["capacity"],
            "session_overflow_headroom_bytes":
                int(overflow["capacity"]) - int(overflow["used"]),
            "region1_slices": [
                {"id": row["id"], "name": row["name"],
                 "bytes": row["file_size"]}
                for row in region1
            ],
            "all_slices_under_1792": True,
        },
        "first_red": {
            "contract_surface": "runtime-overlay publish-last identity table",
            "section": P.VERIFIER_BINDING_SECTION,
            "bytes": verifier["bytes"],
            "historical_active_pin": f"0x{P.VERIFIER_BINDING_BASE:04x}",
            "measured_address": f"0x{verifier['address']:04x}",
            "delta_bytes": verifier["address"] - P.VERIFIER_BINDING_BASE,
            "classification":
                "contract/pin authority; not E000 geometry and not a "
                "Class-A checker exception",
            "required_decision":
                "owner-authorized B94E-to-B972 re-pin before artifact-side "
                "publish-last completion",
        },
        "frozen_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "source_first_red": bind(FIRST_RED),
        },
        "immutable_source_tree": {
            "files": len(before),
            "byte_and_mode_identity": "unchanged",
        },
        "execution_accounting": {
            "source_WPLTO_closure_links": 1,
            "replay_compiler_runs": 0,
            "replay_linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "read_only_tool_invocations": commands,
        },
        "claim_limit":
            "The WPLTO map and runtime-family packing are measured green. "
            "The product remains unpromotable and unpatched at the verifier "
            "table; Link 60 and hardware are blocked by First Red.",
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
    value = build()
    walls = value["walls"]
    print(
        "c2-link60-pin-artifact-replay: FIRST RED "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"island={walls['resident_island_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        "verifier=B94E->B972")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link60-pin-artifact-replay: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
