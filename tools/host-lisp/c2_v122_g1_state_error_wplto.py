#!/usr/bin/env python3
"""Run the Phase-G1 state/error instrument product-shaped WPLTO.

The resident Link-78 geometry is terminal.  This probe may add Bank-2 code
and cold Session-overlay freight only; every resident wall is an equality,
not merely a non-negative budget.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_phase_v_random_while_wplto as V  # noqa: E402
import c2_state_error_carrier_gate as G1  # noqa: E402
import error_overlay_smoke as L65E  # noqa: E402


BASE = V.BASE
BUILD = ROOT / "build/post-release/v1.2.2/g1-state-error/product-shaped-wplto-v6"
PRELINK_BUILD = (
    ROOT / "build/post-release/v1.2.2/g1-state-error/product-shaped-wplto")
INVENTORY_PRELINK_BUILD = (
    ROOT / "build/post-release/v1.2.2/g1-state-error/"
    "product-shaped-wplto-v2")
CANDIDATE = ROOT / "build/post-release/v1.2.2/g1-state-error/static/buffer"
BUFFER_MANIFEST = CANDIDATE.with_suffix(".manifest.json")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.2-g1-state-error-carrier-receipt.json"
FIRST_RED = EVIDENCE / "c2.2-v1.2.2-g1-state-error-carrier-first-red.json"
INVENTORY_FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-g1-state-error-renderer-inventory-first-red.json")
CAPACITY_FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-g1-session-aggregate-first-red.json")
POLICY_CAPACITY_FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-g1-session-aggregate-after-policy-first-red.json")
NOINLINE_FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-g1-noinline-semantic-split-first-red.json")
LINK78 = EVIDENCE / (
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
DRIVER = Path(__file__).resolve()

EXPECTED_STATIC = 41597
EXPECTED_ENTRIES = 699
EXPECTED_RESOLUTIONS = 2763
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 656
EXPECTED_PRODUCT_ID = "0x5e40e50d"
EXPECTED_BANK2_SHA = (
    "f1ca07a84537568878236117dde2a4e57a0b70b11615e10863b119eb406a5149")
EXPECTED_RESIDENT = {
    "bank0_text_headroom_bytes": 243,
    "e000_headroom_bytes": 54,
    "fixed_hot_block_headroom_bytes": 2,
    "ordinary_bank0_bss_headroom_bytes": 137,
    "resident_island_headroom_bytes": 50,
}


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


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
        f"{label} red ({result.returncode}):\n{result.stdout[-8000:]}",
    )
    return result.stdout


def build_buffer_artifact() -> dict[str, Any]:
    CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
    output = run(
        [
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            str(CANDIDATE),
            "--artifact-role",
            "disk-lib",
            "--base-addr",
            "0x000000",
            str(G1.BUFFER_SUITE),
        ],
        "G1 bound Buffer image",
    )
    manifest = load(BUFFER_MANIFEST)
    require(
        manifest["code_bytes"] == 216
        and manifest["directory_bytes"] == 70
        and manifest["objects"] == 10
        and "bytecode-p0-stdlib-check: PASS "
            "suites=1 functions=10 cases=10" in output
        and "bytecode-p0-stdlib-embed-check: PASS cases=10" in output,
        "G1 bound Buffer image geometry or execution witness drift",
    )
    return {
        "manifest": bind(BUFFER_MANIFEST),
        "code_bytes": manifest["code_bytes"],
        "directory_bytes": manifest["directory_bytes"],
        "objects": manifest["objects"],
        "output": output.strip().splitlines()[-2:],
    }


def source_gates() -> dict[str, Any]:
    value = G1.bundle()
    source = G1.validate(value)
    mutations = G1.mutation_tests(value)
    execution = G1.executable_fixtures()
    packed = G1.bound_artifact_fixtures()
    l65e = run(
        [sys.executable, str(ROOT / "tools/host-lisp/error_overlay_smoke.py")],
        "G1 append-only user String renderer",
    )
    require(
        mutations == 21
        and execution["positive_count"] == 9
        and execution["negative_count"] == 9
        and packed["mutations_rejected"] == 6
        and packed["execution_witness"] == {
            "source_cases": 10,
            "embedded_cases": 10,
        }
        and "dynamic-string=exact" in l65e
        and "total=1239 headroom=81" in l65e,
        "G1 source, execution, packed-artifact or renderer gate red",
    )
    return {
        "source": source,
        "source_mutations_rejected": mutations,
        "execution": execution,
        "packed_artifact": packed,
        "renderer_output": l65e.strip().splitlines(),
    }


def bind_g1_specs() -> None:
    """Select the new Buffer image at every active producer boundary."""
    req = BASE.PROBE.REQ
    req.SPECS = tuple(
        (
            key,
            name,
            BUFFER_MANIFEST if key == "buffer" else path,
        )
        for key, name, path in req.SPECS
    )
    req.EXPECTED_STATIC = EXPECTED_STATIC
    req.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    req.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    req.F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.F1W.SPECS = req.SPECS
    BASE.CAN.SPECS = req.SPECS
    BASE.CAN.PREFIXES = tuple(
        (
            path.with_suffix(""),
            "stdlib" if index == 0 else "disk-lib",
            None if index == 0 else "0x000000",
        )
        for index, (_key, _name, path) in enumerate(req.SPECS)
    )


def configure() -> dict[str, Path]:
    for name, value in (
        ("EXPECTED_STATIC", EXPECTED_STATIC),
        ("EXPECTED_ENTRIES", EXPECTED_ENTRIES),
        ("EXPECTED_RESOLUTIONS", EXPECTED_RESOLUTIONS),
        ("EXPECTED_ROOTS", EXPECTED_ROOTS),
        ("EXPECTED_DIRECT_REFS", EXPECTED_DIRECT_REFS),
        ("EXPECTED_PRODUCT_ID", EXPECTED_PRODUCT_ID),
        ("EXPECTED_BANK2_SHA", EXPECTED_BANK2_SHA),
    ):
        setattr(V, name, value)
    V.configure_candidate()
    BASE.LINK = 79
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = LINK78
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    V.bind_candidate_specs()
    bind_g1_specs()
    os.environ.update(BASE.CAN.canonical_build_environment())
    return paths


def session_slices(path: Path) -> dict[str, Any]:
    manifest = load(path)
    rows = {
        row["name"]: row
        for row in manifest["slices"]
        if isinstance(row, dict) and "name" in row
    }
    buffer_read = rows["first-class-buffer-read"]
    error = rows["error-text-renderer"]
    require(
        buffer_read["file_size"] <= 1792
        and error["file_size"] <= 1320,
        "G1 semantic split still crosses a cold-slice cap: "
        f"buffer={buffer_read['file_size']} error={error['file_size']}",
    )
    return {
        "buffer_read": buffer_read,
        "error_text_renderer": error,
    }


def probe() -> int:
    typed_prelink = FIRST_RED.is_file()
    require(
        not BUILD.exists() and not RECEIPT.exists(),
        "G1 WPLTO requires a fresh one-shot build",
    )
    prelink: dict[str, Any] | None = None
    if typed_prelink:
        prelink = load(FIRST_RED)
        base_result = load(
            PRELINK_BUILD / "receipts/wplto-base-result.json")
        inventory = load(INVENTORY_FIRST_RED)
        inventory_result = load(
            INVENTORY_PRELINK_BUILD / "receipts/wplto-base-result.json")
        capacity_red = load(CAPACITY_FIRST_RED)
        capacity_result = load(
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v3/receipts/wplto-base-result.json")
        capacity_elf = (
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v3/wplto/"
            "lisp65-c2-substitution-linked.prg.elf")
        policy_capacity_red = load(POLICY_CAPACITY_FIRST_RED)
        policy_capacity_result = load(
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v4/receipts/wplto-base-result.json")
        policy_capacity_elf = (
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v4/wplto/"
            "lisp65-c2-substitution-linked.prg.elf")
        noinline_red = load(NOINLINE_FIRST_RED)
        noinline_result = load(
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v5/receipts/wplto-base-result.json")
        noinline_lto = (
            ROOT / "build/post-release/v1.2.2/g1-state-error/"
            "product-shaped-wplto-v5/wplto/"
            "resident-island-seed.prg.lto.o")
        require(
            prelink["status"]
                == "FIRST RED: G1 product-shaped WPLTO stopped"
            and base_result["WPLTO"]["product_completed"] is False
            and base_result["WPLTO"]["return_code"] == 2
            and not (
                PRELINK_BUILD / "wplto/"
                "lisp65-c2-substitution-linked.prg.elf").exists(),
            "G1 typed prelink Z-boundary stop cannot be replayed",
        )
        require(
            inventory["status"]
                == "FIRST RED: G1 inherited L65E emit inventory stopped"
            and inventory_result["WPLTO"]["product_completed"] is False
            and inventory_result["WPLTO"]["return_code"] == 2
            and not (
                INVENTORY_PRELINK_BUILD / "wplto/"
                "lisp65-c2-substitution-linked.prg.elf").exists(),
            "G1 typed inherited-renderer stop cannot be replayed",
        )
        require(
            capacity_red["status"]
                == "FIRST RED: G1 cold freight exceeded the Session aggregate"
            and capacity_result["WPLTO"]["return_code"] == 2
            and capacity_elf.is_file()
            and not (
                capacity_elf.parent /
                "runtime-overlays-session-unbound.json").exists(),
            "G1 typed Session-aggregate stop cannot be replayed",
        )
        require(
            policy_capacity_red["status"]
                == "FIRST RED: G1 cold carrier still consumed two Session quanta"
            and policy_capacity_result["WPLTO"]["return_code"] == 2
            and policy_capacity_elf.is_file()
            and not (
                policy_capacity_elf.parent /
                "runtime-overlays-session-unbound.json").exists(),
            "G1 post-policy Session-aggregate stop cannot be replayed",
        )
        require(
            noinline_red["status"]
                == "FIRST RED: G1 noinline semantic split exceeded its cold slice"
            and noinline_result["WPLTO"]["product_completed"] is False
            and noinline_result["WPLTO"]["return_code"] == 2
            and noinline_lto.is_file()
            and not (
                noinline_lto.parent /
                "lisp65-c2-substitution-linked.prg.elf").exists(),
            "G1 rejected noinline semantic split cannot be replayed",
        )
    predecessor = load(LINK78)
    require(
        predecessor["link_number"] == 78
        and predecessor["walls"] == {
            **EXPECTED_RESIDENT,
            "session_family_headroom_bytes": 113,
        },
        "Link-78 terminal geometry authority drift",
    )
    artifact = build_buffer_artifact()
    gates = source_gates()
    equivalence = run(
        ["make", "equivalence-check"],
        "G1 equivalence chain and positive execution canary",
    )
    require(
        "equivalence-completion-canary: COMPLETE lanes=11 executed=447"
            in equivalence,
        "G1 equivalence chain lacks its positive execution witness",
    )

    paths = configure()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and product["product_build_id_hex"] == EXPECTED_PRODUCT_ID
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS,
        "G1 single-emitter product identity drift",
    )

    # The only target linker invocation authorized for this G1 card.
    wplto = BASE.CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    slices = session_slices(
        paths["wplto"] / "runtime-overlays-session-final.json")
    require(
        wplto["status"].startswith("passed-one-current-WPLTO")
        and walls == EXPECTED_RESIDENT,
        "G1 debited closed resident geometry: "
        f"expected={EXPECTED_RESIDENT} actual={walls}",
    )
    require(
        capacity["session_family_headroom_bytes"] >= 0,
        "G1 cold freight crossed the Session aggregate: "
        f"{capacity['session_family_headroom_bytes']} bytes",
    )

    value = {
        "format": "lisp65-c2.2-v1.2.2-g1-state-error-WPLTO-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-G1-state-error-instrument-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "predecessor": bind(LINK78),
        "typed_prelink_replay": None if prelink is None else {
            "stops": [
                {
                    "receipt": bind(FIRST_RED),
                    "classification":
                        "ASM-to-C Z-boundary source gate before product link",
                    "mechanism":
                        "l65e_emit_user_string called str_len with unknown Z",
                    "correction": "ldz #0 immediately before jsr str_len"
                },
                {
                    "receipt": bind(INVENTORY_FIRST_RED),
                    "classification":
                        "inherited L65E instruction-inventory checker",
                    "mechanism":
                        "append-only user String output owns the eighth emit",
                    "correction":
                        "derive the current seven-jsr/two-tail-jmp plus "
                        "print_string_raw inventory"
                },
                {
                    "receipt": bind(CAPACITY_FIRST_RED),
                    "classification":
                        "cold L65R aggregate after one linked ELF",
                    "mechanism":
                        "L65E and Buffer-read crossed three 256-byte quanta "
                        "against 113 bytes of inherited Session headroom",
                    "correction":
                        "move room policy to Bank 2 and reuse the canonical "
                        "cold String printer before repacking"
                },
                {
                    "receipt": bind(POLICY_CAPACITY_FIRST_RED),
                    "classification":
                        "cold read-carrier packing after policy extraction",
                    "mechanism":
                        "the read carrier still occupied 1724 bytes and two "
                        "quanta beyond its Link-78 predecessor",
                    "correction":
                        "three noinline same-section semantic helpers retain "
                        "one record and one callable carrier entry"
                },
                {
                    "receipt": bind(NOINLINE_FIRST_RED),
                    "classification":
                        "rejected same-section noinline helper form",
                    "mechanism":
                        "call-state preservation expanded the read slice to "
                        "1915 bytes against its 1792-byte cap",
                    "correction":
                        "discard the helper form and restore the smaller "
                        "1724-byte inlined carrier"
                }
            ],
            "old_renderer_bytes": 1311,
            "current_renderer_bytes": 1239,
            "product_completed_before_replay": False,
            "linked_ELF_before_replay": False,
            "product_bytes_changed_by_checker_update": 0,
        },
        "geometry_policy": {
            "resident": "closed; every Link-78 wall is byte-identical",
            "allowed_freight": ["Bank 2", "cold Session overlays"],
            "forbidden_freight": ["resident text", "E000", "fixed block",
                                  "ordinary BSS", "resident island"],
        },
        "gates": gates,
        "bound_buffer_image": artifact,
        "static_geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_from_Link78_bytes": 112,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "entries_delta": 3,
            "resolutions": EXPECTED_RESOLUTIONS,
            "resolutions_delta": 3,
            "roots": EXPECTED_ROOTS,
            "roots_delta": 0,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": EXPECTED_PRODUCT_ID,
            "bank2_sha256": EXPECTED_BANK2_SHA,
        },
        "cold_slices": slices,
        "walls": walls,
        "capacity": capacity,
        "equivalence": {"lanes": 11, "executed": 447},
        "wplto": wplto,
        "authority": {
            "contract": bind(G1.CONTRACT),
            "contract_note": bind(
                ROOT / "docs/planning/c2.2-f3-state-error-carrier-contract.md"),
            "worklist": bind(ROOT / "docs/planning/1.2.2-worklist.md"),
            "profile": bind(ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract": bind(
                ROOT / "config/c2-lite-execution-contract.json"),
            "static_header": bind(ROOT / "src/c2_lite_static_plane.h"),
            "static_product": bind(product_path),
            "linked_ELF": bind(
                paths["wplto"] /
                "lisp65-c2-substitution-linked.prg.elf"),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Use room as the Phase-G attribution instrument. A successor "
            "product link or hardware run still requires separate authority."
        ),
        "claim_limit": (
            "One product-shaped WPLTO and host/ELF evidence only; no product "
            "link, hardware gc/room/error claim, or GC performance claim."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-v1.2.2-g1-state-error: WPLTO PASS "
        f"bank2={EXPECTED_STATIC} "
        f"buffer={slices['buffer_read']['file_size']} "
        f"error={slices['error_text_renderer']['file_size']} "
        f"session={capacity['session_family_headroom_bytes']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} links=0 hardware=0"
    )
    return 0


def main() -> int:
    try:
        return probe()
    except (
        ProbeError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        if not RECEIPT.exists() and not FIRST_RED.exists():
            write(FIRST_RED, {
                "format":
                    "lisp65-c2.2-v1.2.2-g1-state-error-first-red-v1",
                "recorded_on": "2026-07-29",
                "status": "FIRST RED: G1 product-shaped WPLTO stopped",
                "error": str(error),
                "product_links": 0,
                "hardware_runs": 0,
                "wplto_probes_consumed": 1 if BUILD.exists() else 0,
                "build_exists": BUILD.exists(),
                "claim_limit":
                    "Typed G1 probe stop only; no product or hardware claim.",
            })
        print(
            "c2-v1.2.2-g1-state-error: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
