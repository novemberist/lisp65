#!/usr/bin/env python3
"""Run the one owner-authorized v1.2.2 DIRMISS renderer WPLTO.

This driver is deliberately probe-only.  It applies the already attributed
L65E pointer-consumption correction to the released v1.2.1 composition,
executes the exact full-name fixture, performs one current target WPLTO, and
writes a non-promotable Halt-D capacity receipt.  It cannot create a product
link or request hardware.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_phase_v_random_while_wplto as V  # noqa: E402
import error_overlay_smoke as L65E  # noqa: E402


BASE = V.BASE
BUILD = (
    ROOT /
    "build/post-release/v1.2.2/dirmiss-renderer/product-shaped-wplto-v2")
PRELINK_BUILD = (
    ROOT /
    "build/post-release/v1.2.2/dirmiss-renderer/product-shaped-wplto")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.2-dirmiss-renderer-wplto-receipt.json"
FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-dirmiss-renderer-wplto-first-red.json")
ATTRIBUTION = EVIDENCE / (
    "c2.2-v1.2.1-dirmiss-renderer-attribution-receipt.json")
LINK77 = EVIDENCE / (
    "c2.2-product-link77-random-while-structural-receipt.json")
PUBLICATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "v121-public-publication-receipt-20260729.json")
PLAN = ROOT / "docs/planning/1.2.2-worklist.md"
SMOKE = ROOT / "tools/host-lisp/error_overlay_smoke.py"
SOURCE = ROOT / "src/l65e_bcode_ordinal.s"
DRIVER = Path(__file__).resolve()

OLD_L65E_BYTES = 1210
EXPECTED_L65E_BYTES = 1206
OLD_ENTRY_BYTES = 339
EXPECTED_ENTRY_BYTES = 335


class DirmissProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DirmissProbeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0,
        f"{label} red ({result.returncode}):\n{result.stdout[-6000:]}",
    )
    return result.stdout


def configure() -> dict[str, Path]:
    """Bind the released v1.2.1 freight to an isolated D1 build."""
    V.configure_candidate()
    BASE.LINK = 78
    BASE.EXPECTED_STATIC = V.EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = V.EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = LINK77
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    # BASE.configure selects its historical default manifests.  The released
    # random/while artifacts remain the final producer selection.
    V.bind_candidate_specs()
    os.environ.update(BASE.CAN.canonical_build_environment())
    return paths


def dirmiss_host_gate() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(
        attribution.get("status")
            == "passed-renderer-pointer-abi-overwrite-attributed"
        and attribution.get("disposition", {}).get("convicted_fix")
            == "delete sta __rc2 / stx __rc3 after jsr symname"
        and attribution.get("evidence", {}).get("symname_return_abi")
            == "__rc2/__rc3",
        "DIRMISS attribution authority drift",
    )
    source = SOURCE.read_text(encoding="ascii")
    L65E.renderer_source_contract(source)
    mutations = L65E.renderer_source_mutations(source)
    output = run([sys.executable, str(SMOKE)], "DIRMISS full-name fixture")
    marker = (
        "error-overlay smoke: ok "
        "(cases=20 full-symbol=intern-renderer-missing "
        "target-mutations=5 "
    )
    require(
        marker in output
        and "error-overlay target pointer contract: "
            "ok (mutations=5 full-symbol=intern-renderer-missing)" in output
        and len(mutations) == 5,
        "DIRMISS fixture lacks its exact full-name execution witness",
    )
    return {
        "status": "passed-full-name-and-target-pointer-consumption",
        "rendered_exactly":
            "undefined function: intern-renderer-missing",
        "host_cases_executed": 20,
        "target_mutations_rejected": mutations,
        "output": output.strip().splitlines(),
        "attribution": bind(ATTRIBUTION),
    }


def linked_renderer_gate(elf: Path) -> dict[str, Any]:
    tool_root = ROOT / "tools/llvm-mos/bin"
    symbols = run(
        [str(tool_root / "llvm-nm"), "-S", str(elf)],
        "linked DIRMISS symbols",
    )
    match = re.search(
        r"^([0-9a-f]+)\s+([0-9a-f]+)\s+[Tt]\s+"
        r"lisp65_error_overlay_entry$",
        symbols,
        re.MULTILINE,
    )
    require(match is not None, "linked L65E entry symbol absent")
    entry_address = int(match.group(1), 16)
    entry_bytes = int(match.group(2), 16)
    disassembly = run(
        [
            str(tool_root / "llvm-objdump"),
            "-d",
            "--no-show-raw-insn",
            "--section=.lisp65_rt_l65e",
            str(elf),
        ],
        "linked DIRMISS disassembly",
    )
    lines = disassembly.splitlines()
    try:
        call_at = next(
            index for index, line in enumerate(lines)
            if re.search(r"\bjsr\s+\$[0-9a-f]+\s+<symname>", line)
        )
    except StopIteration as exc:
        raise DirmissProbeError(
            "linked L65E entry has no symname call"
        ) from exc
    following: list[str] = []
    for line in lines[call_at + 1:]:
        instruction = re.match(
            r"^\s*[0-9a-f]+:\s+([a-z]+)\s*(.*?)\s*(?:;.*)?$",
            line,
        )
        if not instruction:
            continue
        following.append(
            " ".join(
                f"{instruction.group(1)} {instruction.group(2)}".split()
            )
        )
        if len(following) == 2:
            break
    require(
        entry_bytes == EXPECTED_ENTRY_BYTES
        and following == ["ldz #$0", "lda ($4),z"],
        "linked L65E consumer reintroduced incidental A/X stores: "
        f"entry={entry_bytes}, following={following!r}",
    )
    return {
        "status": "passed-linked-symname-result-consumed-directly",
        "entry_address": f"0x{entry_address:04x}",
        "entry_bytes": entry_bytes,
        "old_entry_bytes": OLD_ENTRY_BYTES,
        "delta_bytes": entry_bytes - OLD_ENTRY_BYTES,
        "instructions_after_symname": following,
    }


def session_renderer_gate(manifest: Path) -> dict[str, Any]:
    value = load(manifest)
    slices = value.get("slices")
    require(isinstance(slices, list), "session manifest has no slices")
    matches = [
        row for row in slices
        if isinstance(row, dict) and row.get("name") == "error-text-renderer"
    ]
    require(len(matches) == 1, "session manifest does not own one L65E slice")
    row = matches[0]
    require(
        row.get("file_size") == EXPECTED_L65E_BYTES
        and row.get("memory_size") == EXPECTED_L65E_BYTES
        and row.get("region_id") == 0,
        "L65E cold slice size or region drift",
    )
    return {
        "status": "passed-cold-session-L65E-delta",
        "name": row["name"],
        "slot": row["id"],
        "region_id": row["region_id"],
        "bytes": row["file_size"],
        "old_bytes": OLD_L65E_BYTES,
        "delta_bytes": row["file_size"] - OLD_L65E_BYTES,
        "session_manifest": bind(manifest),
    }


def probe() -> int:
    fresh = not BUILD.exists()
    typed_prelink = FIRST_RED.is_file()
    require(
        not RECEIPT.exists() and fresh,
        "v1.2.2 DIRMISS WPLTO requires a fresh product-shaped build",
    )
    first_red: dict[str, Any] | None = None
    if typed_prelink:
        first_red = load(FIRST_RED)
        base_result = load(PRELINK_BUILD / "receipts/wplto-base-result.json")
        elf = (
            PRELINK_BUILD /
            "wplto/lisp65-c2-substitution-linked.prg.elf")
        require(
            first_red.get("status") == "FIRST RED: D1 WPLTO stopped"
            and base_result.get("WPLTO", {}).get("product_completed") is False
            and base_result.get("WPLTO", {}).get("return_code") == 2
            and not elf.exists(),
            "D1 typed prelink stop cannot be replayed",
        )
    publication = load(PUBLICATION)
    require(
        publication.get("status") == "passed"
        and publication.get("product_authority", {}).get(
            "artifact_set_sha256")
            == (
                "2115b955512a3b794f68d5f2a1d160708cb89184735b7a098"
                "4a7cfc61c38f63f"
            ),
        "released v1.2.1 authority drift",
    )
    dirmiss = dirmiss_host_gate()
    equivalence = run(
        ["make", "equivalence-check"],
        "v1.2.2 D1 equivalence and execution canary",
    )
    require(
        "equivalence-completion-canary: COMPLETE lanes=11 executed=447"
            in equivalence,
        "equivalence chain lacks its positive execution witness",
    )

    paths = configure()
    V.bind_candidate_specs()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    require(
        static["semantics"]["code_bytes"] == V.EXPECTED_STATIC
        and plane["static_code_bytes"] == V.EXPECTED_STATIC,
        "D1 fresh static plane drift",
    )
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    profile = load(ROOT / "config/c2-l-full-product-profile.json")
    require(
        product["product_build_id_hex"] == V.EXPECTED_PRODUCT_ID
        and product["entries"] == V.EXPECTED_ENTRIES
        and product["resolutions"] == V.EXPECTED_RESOLUTIONS
        and product["roots"] == V.EXPECTED_ROOTS
        and profile["direct_entry_refs"] == V.EXPECTED_DIRECT_REFS
        and profile["bank2_static_code"]["sha256"] == V.EXPECTED_BANK2_SHA,
        "v1.2.1 static plane changed during the DIRMISS-only probe",
    )
    inherited = V.inherited_gates()

    # This is the sole target linker invocation authorized for D1.
    wplto = BASE.CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    resident_keys = (
        "bank0_text_headroom_bytes",
        "e000_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "ordinary_bank0_bss_headroom_bytes",
        "resident_island_headroom_bytes",
    )
    require(
        wplto["status"].startswith("passed-one-current-WPLTO")
        and all(walls[key] >= 0 for key in resident_keys)
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0,
        "D1 crossed a product wall",
    )
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    session_manifest = (
        paths["wplto"] / "runtime-overlays-session-final.json")
    linked_renderer = linked_renderer_gate(elf)
    session_renderer = session_renderer_gate(session_manifest)

    value = {
        "format": "lisp65-c2.2-v1.2.2-dirmiss-renderer-WPLTO-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-D1-full-name-renderer-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "typed_prelink_replay": None if first_red is None else {
            "receipt": bind(FIRST_RED),
            "classification":
                "stale inherited L65E shape authority before target link",
            "old_slice_bytes": OLD_L65E_BYTES,
            "current_slice_bytes": EXPECTED_L65E_BYTES,
            "product_completed_before_replay": False,
            "linked_ELF_before_replay": False,
            "product_bytes_changed_by_checker_update": 0,
        },
        "released_baseline": {
            "release": "v1.2.1",
            "artifact_set_sha256":
                publication["product_authority"]["artifact_set_sha256"],
            "publication": bind(PUBLICATION),
            "link77": bind(LINK77),
        },
        "fix": {
            "mechanism": (
                "consume symname's __rc2/__rc3 pointer directly; do not "
                "overwrite it with incidental A/X"
            ),
            "source_delta_bytes": -4,
            "resident_delta_bytes": 0,
            "bank2_delta_bytes": 0,
            "cold_session_slice_delta_bytes": -4,
            "host_and_object_gate": dirmiss,
            "linked_gate": linked_renderer,
            "session_slice": session_renderer,
        },
        "static_geometry": {
            "bank2_static_code_bytes": V.EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - V.EXPECTED_STATIC,
            "entries": V.EXPECTED_ENTRIES,
            "resolutions": V.EXPECTED_RESOLUTIONS,
            "roots": V.EXPECTED_ROOTS,
            "direct_entry_refs": V.EXPECTED_DIRECT_REFS,
            "product_build_id": V.EXPECTED_PRODUCT_ID,
            "bank2_sha256": V.EXPECTED_BANK2_SHA,
        },
        "inherited_gates": {
            "count": len(inherited),
            "names": sorted(inherited),
            "equivalence_lanes": 11,
            "equivalence_cases_executed": 447,
        },
        "walls": walls,
        "capacity": capacity,
        "wplto": wplto,
        "authority": {
            "worklist": bind(PLAN),
            "renderer_source": bind(SOURCE),
            "full_name_fixture": bind(SMOKE),
            "attribution": bind(ATTRIBUTION),
            "profile": bind(ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract":
                bind(ROOT / "config/c2-lite-execution-contract.json"),
            "static_product": bind(product_path),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Class-C Halt D: owner reviews this capacity card. Only then "
            "may one successor product link and the bundled D1/D2 hardware "
            "session be authorized."
        ),
        "claim_limit": (
            "One product-shaped target WPLTO plus host/ELF fixtures. No "
            "successor product link, hardware DIRMISS rendering, require, "
            "defstruct or library-era claim."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-v1.2.2-dirmiss-renderer: WPLTO PASS "
        f"l65e={session_renderer['bytes']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "links=0 hardware=0"
    )
    return 0


def main() -> int:
    try:
        return probe()
    except (
        DirmissProbeError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        if not RECEIPT.exists() and not FIRST_RED.exists():
            write(FIRST_RED, {
                "format": "lisp65-c2.2-v1.2.2-dirmiss-renderer-first-red-v1",
                "recorded_on": "2026-07-29",
                "status": "FIRST RED: D1 WPLTO stopped",
                "error": str(error),
                "product_links": 0,
                "hardware_runs": 0,
                "build_exists": BUILD.exists(),
                "claim_limit": (
                    "Typed D1 probe stop only; no product or hardware claim."
                ),
            })
        print(
            "c2-v1.2.2-dirmiss-renderer: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
