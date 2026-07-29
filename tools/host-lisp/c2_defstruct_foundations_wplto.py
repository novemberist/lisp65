#!/usr/bin/env python3
"""Measure the defstruct foundations in one product-shaped WPLTO."""

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
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_require_resolver_wplto as REQ  # noqa: E402
import c2_intern_session_service_gate as SERVICE  # noqa: E402


BASE = ROOT / "build/post-promotion/defstruct-v1/product-shaped"
STATIC = BASE / "narrow-static"
STATIC_PRODUCT = STATIC / "product"
V6 = STATIC / "v6-semantics"
FIRST_RED_BUILD = BASE / "candidate"
SHARED_C_FIRST_RED_BUILD = BASE / "candidate-shared-intern-v2"
LEAF_FIRST_RED_BUILD = BASE / "candidate-intern-leaf-v3"
SERVICE_STUB_FIRST_RED_BUILD = BASE / "candidate-session-service-v4"
SHARED_FACADE_FIRST_RED_BUILD = (
    BASE / "candidate-session-service-shared-facade-v5")
PREVALIDATED_FIRST_RED_BUILD = (
    BASE / "candidate-session-service-prevalidated-v6")
BUILD = BASE / "candidate-session-service-one-string-predicate-v17"
WPLTO = BUILD / "wplto"
RECEIPTS = BUILD / "receipts"
STATIC_RECEIPT = RECEIPTS / "defstruct-static-plane-authority.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FOUNDATIONS = EVIDENCE / "c2.2-defstruct-foundations-gate-receipt.json"
BASELINE = EVIDENCE / (
    "c2.2-product-link68-require-resolver-structural-receipt.json")
BASELINE_ELF = ROOT / (
    "build/post-promotion/link68-require-resolver/final/"
    "lisp65-c2-substitution-linked.prg.elf")
BASELINE_MAP = ROOT / (
    "build/post-promotion/link68-require-resolver/wplto/"
    "resident-island-seed.prg.map")
BASELINE_SESSION = ROOT / (
    "build/post-promotion/link68-require-resolver/wplto/"
    "runtime-overlays-session-final.json")
RECEIPT = EVIDENCE / "c2.2-defstruct-foundations-wplto-receipt.json"
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-defstruct-foundations-wplto-first-red.json")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def symbol_sizes(path: Path) -> dict[str, int]:
    nm = CAN.TOOLCHAIN / "bin/llvm-nm"
    output = run(
        [str(nm), "--print-size", "--size-sort", str(path)],
        f"inspect symbols in {path.name}")
    rows: dict[str, int] = {}
    for line in output.splitlines():
        tokens = line.split(maxsplit=3)
        if len(tokens) == 4:
            rows[tokens[3]] = int(tokens[1], 16)
    return rows


def service_manifest_gate() -> dict[str, Any]:
    current_path = WPLTO / "runtime-overlays-session-final.json"
    boot_path = WPLTO / "runtime-overlays-boot-final.json"
    current = load(current_path)
    baseline = load(BASELINE_SESSION)
    rows = current["slices"]
    old = baseline["slices"]
    require(
        len(rows) == 52 and len(old) == 51
        and [row["name"] for row in rows[:-1]]
            == [row["name"] for row in old]
        and rows[-1]["name"] == "intern-session-service"
        and rows[-1]["id"] == 51
        and rows[-1]["region_id"] == 0
        and rows[-1]["roles"] == ["runtime", "reusable"]
        and 0 < rows[-1]["memory_size"] <= 512
        and rows[-1]["source_address"] == 0x3FE00
        and current["storage"]["size"] - baseline["storage"]["size"] == 497
        and current["storage"]["size"] == 65423,
        "Session-service record/packing geometry drift")
    return {
        "status": "passed-one-Session-service-record-one-quantum",
        "record_count": len(rows),
        "baseline_record_count": len(old),
        "new_records": 1,
        "slice": rows[-1],
        "slice_delta_bytes": rows[-1]["memory_size"],
        "placement_quantum_bytes": 512,
        "alignment_before_service_bytes":
            rows[-1]["file_offset"] - baseline["storage"]["size"],
        "packed_delta_bytes":
            current["storage"]["size"] - baseline["storage"]["size"],
        "session_headroom_bytes": 65536 - current["storage"]["size"],
        "manifest": bind(current_path),
        "boot_manifest": bind(boot_path),
    }


def configure() -> None:
    REQ.BASE = BASE
    REQ.STATIC = STATIC
    REQ.STATIC_PRODUCT = STATIC_PRODUCT
    REQ.V6_OUT = V6
    REQ.BUILD = BUILD
    REQ.WPLTO = WPLTO
    REQ.RECEIPTS = RECEIPTS
    REQ.STATIC_RECEIPT = STATIC_RECEIPT
    REQ.STDLIB = STATIC / "stdlib-p0.manifest.json"
    REQ.SPECS = (
        ("stdlib-p0", "stdlib", REQ.STDLIB),
        *REQ.SPECS[1:],
    )
    REQ.configure()
    # Prim-ID 68 appends one uint16 row after the accepted Prim-ID-67 table.
    CAN.PRODUCT.configure_defstruct_foundation_profile_geometry()
    inherited_single_link = CAN.PRODUCT.single_link

    def service_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path =
            CAN.PRODUCT.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        # The historical product adapters rebuild the Session inventory at
        # the actual link boundary.  Select the new pattern class after those
        # geometry transforms and before any catalog byte is emitted.
        CAN.PRODUCT.configure_intern_session_service()
        return inherited_single_link(
            out,
            probe_definitions=probe_definitions,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "session_service=intern-on-demand-stateless-exclusive",
                "session_service_busy=ERR_BUSY-before-window-mutation",
            ),
        )

    CAN.PRODUCT.single_link = service_single_link
    os.environ.update(CAN.canonical_build_environment())


def qualify_first_red() -> int:
    builds = {
        "direct_C_case": FIRST_RED_BUILD,
        "shared_C_helper": SHARED_C_FIRST_RED_BUILD,
        "non_LTO_glue_with_C_copy": LEAF_FIRST_RED_BUILD,
    }
    baseline_map = BASELINE_MAP.read_text(encoding="utf-8")
    base_vma, _base_lma, base_text = REQ.map_item(
        baseline_map, ".text")
    base_symbols = symbol_sizes(BASELINE_ELF)
    rows: dict[str, Any] = {}
    for name, build in builds.items():
        map_path = build / "wplto/resident-island-seed.prg.map"
        lto = build / "wplto/resident-island-seed.prg.lto.o"
        stderr = build / "wplto/resident-island-seed.prg.link.stderr.txt"
        require(
            map_path.is_file() and lto.is_file() and stderr.is_file(),
            f"incomplete foundation First-Red attempt: {name}")
        text = map_path.read_text(encoding="utf-8")
        vma, _lma, size = REQ.map_item(text, ".text")
        profile = REQ.map_item(
            text, ".lisp65_c2_kernal_window.profile_rodata")
        gap1 = REQ.map_item(
            text, ".lisp65_c2_kernal_window.reopen_gap1")
        gap2 = REQ.map_item(
            text, ".lisp65_c2_kernal_window.reopen_gap2")
        symbols = symbol_sizes(lto)
        rows[name] = {
            "text_bytes": size,
            "text_delta_from_Link68": size - base_text,
            "text_end_exclusive": f"0x{vma + size:04x}",
            "handoff_overlap_bytes": vma + size - 0xB4A3,
            "vm_callprim_bytes": symbols.get("vm_callprim"),
            "vm_callprim_delta_from_Link68":
                symbols.get("vm_callprim", 0)
                - base_symbols.get("vm_callprim", 0),
            "conversion_helper_bytes":
                symbols.get("intern_string", 0)
                + symbols.get("str_copy_out", 0),
            "profile_rodata": {
                "address": f"0x{profile[0]:04x}",
                "bytes": profile[2],
            },
            "reopen_gap1_bytes": gap1[2],
            "reopen_gap2_bytes": gap2[2],
            "linked_map": bind(map_path),
            "LTO_object": bind(lto),
            "linker_diagnostic": bind(stderr),
        }
    require(
        base_vma == 0x2023 and base_text == 0x9457
        and rows["direct_C_case"]["text_delta_from_Link68"] == 389
        and rows["shared_C_helper"]["text_delta_from_Link68"] == 437
        and rows["non_LTO_glue_with_C_copy"][
            "text_delta_from_Link68"] == 446
        and rows["direct_C_case"]["profile_rodata"]["bytes"] == 348,
        "foundation First-Red attribution drift")
    value = {
        "format": "lisp65-c2-defstruct-foundations-WPLTO-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-canonical-intern-native-conversion-does-not-fit-"
            "resident-text",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "Link68_baseline": {
            "text_bytes": base_text,
            "text_headroom_bytes": 41,
            "e000_headroom_bytes": 60,
            "island_headroom_bytes": 69,
            "fixed_hot_block_headroom_bytes": 2,
            "profile_callprim_bytes": 166,
            "profile_native_call_bytes": 146,
        },
        "attempts": rows,
        "attribution": {
            "smallest_measured_form": "direct_C_case",
            "smallest_resident_delta_bytes": 389,
            "primary_symbol": "vm_callprim",
            "primary_symbol_delta_bytes":
                rows["direct_C_case"]["vm_callprim_delta_from_Link68"],
            "bank2_delta_bytes": 0,
            "session_record_delta": 0,
            "place_defstruct_media": "green and independent",
            "profile_table_growth_bytes": 4,
            "profile_window_resolution":
                "transaction_end rebalanced from named gap1 to named gap2; "
                "total E000 occupancy is unchanged apart from the four "
                "append-only profile bytes (one uint16 row on each "
                "canonical public-call surface)",
        },
        "discarded_forms": {
            "shared_C_helper":
                "one conversion truth grew text by another 48 bytes",
            "non_LTO_glue_with_C_copy":
                "48-byte leaf still required a 218-byte C copy body and "
                "grew text by another 57 bytes over the direct form",
        },
        "review_boundary": {
            "product_question": True,
            "reason":
                "The promised public Core primitive needs a runtime "
                "string-to-symbol conversion, but every resident form "
                "crosses terminal text geometry.  Places, defstruct, L65I "
                "and Bank-2 orchestration are already green.",
            "measured_directions": [
                "direct resident C case",
                "one shared resident C helper",
                "non-LTO glue around a shared resident C copy body",
            ],
            "unselected_direction":
                "cold library-service overlay with a small resident call "
                "stub and the conversion body in the Session store",
        },
        "authority": {
            "foundation_gate": bind(FOUNDATIONS),
            "Link68_receipt": bind(BASELINE),
            "Link68_ELF": bind(BASELINE_ELF),
            "Link68_map": bind(BASELINE_MAP),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit":
            "Capacity First Red only. No successful successor product link, "
            "hardware, require or defstruct runtime claim.",
    }
    FIRST_RED_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RED_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-defstruct-foundations-WPLTO: FIRST RED QUALIFIED "
        "direct=+389 shared=+437 leaf-plus-C-copy=+446 "
        "bank2=0 session-records=0")
    return 0


def main() -> int:
    try:
        if sys.argv[1:] == ["--qualify-first-red"]:
            return qualify_first_red()
        require(not sys.argv[1:], "unknown arguments")
        require(
            not BUILD.exists() and not RECEIPT.exists(),
            "defstruct-foundation WPLTO is one-shot")
        foundation = load(FOUNDATIONS)
        baseline = load(BASELINE)
        require(
            foundation["status"]
                == "passed-intern-canonical-places-and-real-defstruct-media"
            and foundation["intern"]["prim_id"] == 68
            and foundation["places"]["truth"]
                == "*setf-place-registry* in stdlib-places only"
            and foundation["places"]["failed_library"]
                == ("pending registrations invisible and discarded; "
                    "earlier committed rows unchanged")
            and baseline["status"]
                == "passed-Link68-require-resolver-product-identity-"
                   "hardware-not-run",
            "foundation or Link-68 authority drift")

        abi = run([
            sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
            "--selftest"], "ABI ledger")
        registry = run([
            sys.executable, "tools/host-lisp/v2_native_function_registry.py",
            "check"], "native registry")
        drift = run([
            sys.executable, "tools/host-lisp/bytecode_p0_drift_check.py"],
            "bytecode/native drift")
        require(
            "SELFTEST PASS" in abi
            and "registry: PASS" in registry
            and "PASS" in drift,
            "intern canonical source gates red")

        configure()
        static = REQ.build_static_plane()
        BUILD.mkdir(parents=True)
        plane = REQ.F1W.static_gate()
        wplto = CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        wall_keys = (
            "bank0_text_headroom_bytes",
            "e000_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "resident_island_headroom_bytes",
        )
        require(
            wplto["status"].startswith("passed-")
            and plane["static_code_bytes"] == REQ.EXPECTED_STATIC
            and all(walls[key] >= 0 for key in wall_keys)
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_headroom_bytes"] >= 0,
            "defstruct foundations crossed a terminal product wall")

        session = service_manifest_gate()
        candidate_elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
        service_gate = {
            "source": SERVICE.source_gate(),
            "source_mutations_rejected": SERVICE.mutation_gate(),
            "host": SERVICE.host_fixtures(
                BUILD / "session-service-host-gates"),
            "linked": SERVICE.linked_gate(
                candidate_elf,
                WPLTO / "runtime-overlays-session-final.json",
                WPLTO / "runtime-overlays-boot-final.json"),
        }
        before = symbol_sizes(BASELINE_ELF)
        after = symbol_sizes(candidate_elf)
        symbols = {}
        for name in ("vm_callprim", "eval", "intern"):
            require(name in before and name in after,
                    f"foundation ELF symbol absent: {name}")
            symbols[name] = {
                "Link68_bytes": before[name],
                "candidate_bytes": after[name],
                "delta_bytes": after[name] - before[name],
            }
        require(
            "lisp65_intern_service_entry" not in before
            and after.get("lisp65_intern_service_entry", 0) > 0,
            "cold intern service entry identity drift")
        symbols["lisp65_intern_service_entry"] = {
            "Link68_bytes": 0,
            "candidate_bytes": after["lisp65_intern_service_entry"],
            "delta_bytes": after["lisp65_intern_service_entry"],
        }
        profile = load(WPLTO / "profile-data-reference-final.json")
        require(
            profile["geometry"]["bytes"] == 348
            and profile["components"][".rodata.vm_callprim"]["bytes"]
                == 168
            and profile["components"][".rodata.vm_native_call"]["bytes"]
                == 148,
            "Prim-ID-68 canonical profile table geometry drift")

        baseline_walls = baseline["walls"]
        value = {
            "format": "lisp65-c2-defstruct-foundations-WPLTO-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-defstruct-foundations-product-shaped-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "foundations": foundation,
            "canonical_source_gates": {
                "ABI_ledger": abi.strip(),
                "native_registry": registry.strip(),
                "bytecode_native_drift": drift.strip(),
            },
            "static_build": static,
            "static_plane_gate": plane,
            "freight": {
                "bank2_bytes": REQ.EXPECTED_STATIC,
                "bank2_delta_from_Link68": 0,
                "new_session_records": session["new_records"],
                "session_slice_delta_bytes": session["slice_delta_bytes"],
                "resident_symbols": symbols,
                "profile_callprim_bytes": 168,
                "profile_callprim_delta_from_Link68": 2,
                "profile_native_call_bytes": 148,
                "profile_native_call_delta_from_Link68": 2,
            },
            "walls": walls,
            "wall_deltas_from_Link68": {
                key: walls[key] - baseline_walls[key] for key in wall_keys
            },
            "capacity": capacity,
            "session_gate": session,
            "session_service_gate": service_gate,
            "profile_data_reference_gate": profile,
            "wplto": wplto,
            "authority": {
                "foundation_gate": bind(FOUNDATIONS),
                "contract": bind(
                    ROOT / "config/c2-defstruct-v1-contract.json"),
                "session_service_contract": bind(
                    ROOT / "config/c2-session-service-contract.json"),
                "session_service_source": bind(
                    ROOT / "src/intern_service_overlay.c"),
                "session_service_gate": bind(
                    ROOT / "tools/host-lisp/"
                    "c2_intern_session_service_gate.py"),
                "native_registry": bind(
                    ROOT / "config/v2-native-function-registry.json"),
                "places": bind(ROOT / "lib/stdlib-places.lisp"),
                "defstruct": bind(ROOT / "lib/defstruct.lisp"),
                "D81": bind(
                    ROOT / "build/post-promotion/defstruct-v1/foundations/"
                    "require-defstruct.d81"),
                "profile": bind(CAN.PROFILE),
                "linked_elf": bind(candidate_elf),
                "driver": bind(Path(__file__).resolve()),
            },
            "next_gate":
                "successor product link and bundled require/defstruct "
                "hardware session",
            "claim_limit":
                "Product-shaped placement and capacity only; no successor "
                "product identity or hardware claim.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-defstruct-foundations-WPLTO: PASS "
            f"bank2={REQ.EXPECTED_STATIC} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ProbeError, CAN.CanonicalError, PLANE.GateError,
            SERVICE.GateError, SERVICE.ElfTruthError,
            subprocess.CalledProcessError) as error:
        print(f"c2-defstruct-foundations-WPLTO: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
