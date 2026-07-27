#!/usr/bin/env python3
"""One product-shaped L65R-v2 implementation/capacity probe; no Link 33."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-product-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-product-implementation-capacity-probe-receipt.json")
CONTRACT = ROOT / "config/c2-resident-island-two-record-contract.json"
CONTRACT_PROBE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-resident-island-two-record-contract-probe-receipt.json")
CONTRACT_PROBE_SHA = (
    "5a52cb007dc85fffb68ab87cbff9f7108928571116713c6ce3ad1bd472f851a7")
LINK32 = ROOT / (
    "build/c2.2/substitution/product-link-32-preinstall-island-guard/"
    "lisp65-c2-substitution-linked.prg")
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
FEATURES = PROFILE.feature_defines()


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def protect(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_file():
            os.chmod(item, 0o444)
    for item in sorted((p for p in path.rglob("*") if p.is_dir()),
                       key=lambda p: len(p.parts), reverse=True):
        os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def configure() -> None:
    PROFILE.configure(P)
    require(FEATURES[-1] == "LISP65_RUNTIME_OVERLAY_FORMAT_V2",
            "canonical product profile does not select L65R-v2")
    require(P.BOOT_ISLAND_SLOT == 8 and P.BOOT_ISLAND_CARRIER_SLOT == 9
            and len(P.BOOT_DATA_SPECS) == 1,
            "two-record boot ABI drift")


def prerequisites() -> dict[str, Any]:
    require(CONTRACT.is_file(), "two-record contract absent")
    require(CONTRACT_PROBE.is_file() and sha(CONTRACT_PROBE) == CONTRACT_PROBE_SHA,
            "two-record contract probe receipt drift")
    require(LINK32.is_file() and sha(LINK32) == LINK32_SHA,
            "Link-32 rollback identity drift")
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    require(contract["container"]["version"] == 2
            and contract["container"]["new_product_emission"] == "version-2-only"
            and contract["island_carrier_record"]["entry_offset"] == 0xffff,
            "machine-readable L65R-v2 contract drift")
    return {
        "contract": bind(CONTRACT),
        "contract_probe": bind(CONTRACT_PROBE),
        "canonical_product_profile": PROFILE.receipt_identity(),
        "link32_rollback": {**bind(LINK32), "status": "untouched"},
    }


def host_gate(out: Path) -> dict[str, Any]:
    binary = out / "c2-l65r-v2-product-host"
    command = [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=2",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V2",
        "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE=0x08200000UL",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
        "-I" + str(ROOT / "src"),
        str(ROOT / "scripts/c2-l65r-v2-product-main.c"),
        str(ROOT / "src/vm_runtime_overlay.c"), "-o", str(binary),
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    run = subprocess.run(
        [str(binary)], check=True, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    require("PASS publish-last+12 fail-closed cases" in run.stdout,
            "target-decoder host fixture did not report its full matrix")
    write(out / "target-decoder-host.stdout.txt", run.stdout)
    return {
        "status": "passed-actual-target-source",
        "asan": "passed", "ubsan": "passed",
        "fail_closed_cases": 12,
        "binary": bind(binary),
        "stdout": bind(out / "target-decoder-host.stdout.txt"),
    }


def refresh(data: bytearray) -> None:
    count = data[7]
    directory_end = R.HEADER_SIZE + count * R.ENTRY_SIZE
    struct.pack_into("<H", data, 24,
                     R.crc16_ccitt_false(data[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", data, 26, 0)
    struct.pack_into("<H", data, 26,
                     R.crc16_ccitt_false(data[:R.HEADER_SIZE]))


def packer_mutations(image: Path, manifest: Path) -> dict[str, str]:
    baseline = image.read_bytes()
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    build_id = meta["profile_build_id"]
    carrier = meta["slices"][9]
    record = R.HEADER_SIZE + 9 * R.ENTRY_SIZE
    cases: dict[str, Callable[[bytearray], None]] = {
        "v1-header": lambda b: b.__setitem__(4, 1),
        "missing-data-flag": lambda b: struct.pack_into("<H", b, record + 2, 1),
        "unknown-data-flag": lambda b: struct.pack_into("<H", b, record + 2, 0x19),
        "callable-entry": lambda b: struct.pack_into("<H", b, record + 12, 0),
        "abi-one": lambda b: struct.pack_into("<H", b, record + 14, 1),
        "wrong-destination": lambda b: struct.pack_into("<H", b, record + 8, 0xc356),
        "capability": lambda b: struct.pack_into("<I", b, record + 24, 1),
        "zero-length": lambda b: struct.pack_into("<H", b, record + 6, 0),
        "over-cap": lambda b: struct.pack_into("<H", b, record + 6, 1793),
        "source-payload": lambda b: b.__setitem__(carrier["file_offset"],
                                                    b[carrier["file_offset"]] ^ 1),
    }
    result: dict[str, str] = {}
    for name, mutate in cases.items():
        candidate = bytearray(baseline)
        mutate(candidate)
        if name != "source-payload":
            refresh(candidate)
        try:
            R.validate_image(
                candidate, expected_build_id=build_id,
                expected_vma=int(meta["policy"]["common_vma"]),
                max_slice_bytes=1792, format_version=2)
        except R.OverlayBankError:
            result[name] = "rejected-fail-closed"
        else:
            raise ProbeError(f"v2 packer accepted mutation {name}")
    return result


def build_headers(out: Path, artifacts: dict[str, Any], contract: Path) -> list[Path]:
    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime = out / "runtime-overlay.prepare.h"
    island = out / "resident-island.prepare.h"
    stage = out / "stage-config.h"
    error = out / "error-text-table.h"
    kernal = out / "c2-kernal-window.generated.h"
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
           "--header", str(runtime_standard), "--profile", P.PROFILE,
           "--format-version", "2")
    P.render_prepared_family_header(runtime_standard, runtime)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
           "--header", str(island))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    P.tool("error_text_table.py", "prepare",
           "--spec", str(ROOT / "config/error-texts.json"),
           "--profile", "workbench", "--build-id", hex(build_id),
           "--header", str(error), "--binary", str(out / "error-text-table.bin"))
    write(stage, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    pin = P.kernal_window_identity_pin()
    write(kernal, P.kernal_header_values(
        int(str(pin["crc16"]), 16), str(pin["sha256"])))
    return [stage, runtime, island, error, kernal]


def run_probe_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "L65R-v2 product probe is one-shot and already has output")
    configure()
    prereq = prerequisites()
    OUT.mkdir(parents=True)
    host = host_gate(OUT)
    artifacts_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    P.write_v2_profile_report(OUT, artifacts)
    write(OUT / "c2-substitution.ld", P.linker_script())
    contract_lines = [
        "profile=" + P.PROFILE,
        "mode=l65r-v2-product-implementation-capacity-probe",
        "hardware_execution=prohibited",
        "product_link=not-run",
        "runtime_overlay_catalog_version=2",
        "runtime_overlay_decoder_versions=2-only",
        "boot_family_record_count=10",
        "resident_island_carrier_slot=9",
        "product_profile_object_sha256=" + PROFILE.sha256(),
        "c2_artifacts_sha256=" + sha(artifacts_path),
        "linker_sha256=" + sha(OUT / "c2-substitution.ld"),
    ]
    for source in P.source_list():
        path = Path(source)
        contract_lines.append(
            f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    resolved = OUT / "resolved-profile.txt"
    write(resolved, "\n".join(contract_lines) + "\n")
    headers = build_headers(OUT, artifacts, resolved)
    seed = P.compile_link(
        OUT, "l65r-v2-island-seed.prg", headers, artifacts,
        probe_definitions=FEATURES)
    island_header = OUT / "resident-island.h"
    P.tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
           "--nm", str(TOOLCHAIN / "llvm-nm"),
           "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
           "--abi-contract", str(resolved), "--header", str(island_header))
    final_headers = [headers[0], headers[1], island_header, headers[3], headers[4]]
    probe = P.compile_link(
        OUT, "l65r-v2-placement-probe.prg", final_headers, artifacts,
        probe_definitions=FEATURES)
    elf = Path(str(probe) + ".elf")

    provisional = P.extract_provisional_kernal_window(OUT, probe)
    handoff = P.handoff_z_abi_gate(OUT, probe, "l65r-v2-probe")
    pre = P.pre_ownership_gate(OUT, probe, "l65r-v2-probe")
    data_refs = P.profile_data_reference_gate(
        OUT, probe, "l65r-v2-probe", pre)
    facade = P.fixed_facade_gate(OUT, probe, "l65r-v2-probe")
    boot_u = P.overlay_pack_family(OUT, probe, resolved, "boot", "unbound")
    session_u = P.overlay_pack_family(OUT, probe, resolved, "session", "unbound")
    binding = P.patch_verifier_binding_table(
        OUT, probe, boot_u[1], session_u[1])
    boot = P.overlay_pack_family(OUT, probe, resolved, "boot", "final")
    session = P.overlay_pack_family(OUT, probe, resolved, "session", "final")
    identity = P.runtime_family_identity_gate(
        OUT, boot_u, session_u, boot, session)
    write(OUT / "runtime-overlays-final.bin", session[0].read_bytes())
    P.closure_gate(OUT, probe)
    kernal = P.kernal_freedom_gate(OUT, probe)
    balance = P.substitution_balance(OUT, probe, kernal)

    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes": P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes": (
            P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]),
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": (
            2048 - sections[".lisp65_resident_island"]["bytes"]
            - sections[".lisp65_resident_island_annex"]["bytes"]),
        "e000_headroom_bytes": kernal["capacity"]["actual_future_margin_bytes"],
    }
    require(all(value >= 0 for value in walls.values()),
            f"FIRST RED: resident wall {walls}")
    require(walls["e000_headroom_bytes"] == 115,
            "FIRST RED: final E000 equation did not land at 115 bytes")

    boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
    session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
    require(boot_manifest["catalog"]["version"] == 2
            and session_manifest["catalog"]["version"] == 2,
            "FIRST RED: one family is not strict L65R-v2")
    carrier = boot_manifest["slices"][9]
    installer = boot_manifest["slices"][8]
    require(carrier["name"] == "resident-island-image"
            and carrier["roles"] == ["boot", "data-only"]
            and carrier["entry"] is None
            and carrier["entry_offset"] == 0xffff
            and carrier["abi_version"] == 0
            and carrier["vma"] == 0x1800,
            "FIRST RED: emitted carrier record differs from the v2 contract")
    require(carrier["file_size"] <= 1792 and installer["file_size"] <= 1792,
            "FIRST RED: two-record slice cap")
    mutation_matrix = packer_mutations(boot[0], boot[1])
    require(len(mutation_matrix) == 10
            and set(mutation_matrix.values()) == {"rejected-fail-closed"},
            "v2 packer mutation matrix incomplete")

    result = {
        "format": "lisp65-c2-l65r-v2-product-implementation-capacity-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-product-shaped-implementation-capacity-no-link33",
        "scope": {
            "host_target_compiles": 1,
            "whole_program_lto_probe_links": 2,
            "product_closure_links": 0,
            "link33_attempts": 0,
            "hardware_runs": 0,
        },
        "prerequisites": prereq,
        "product_profile": PROFILE.receipt_identity(),
        "target_decoder": host,
        "strict_versioning": {
            "emitted": 2, "accepted_by_c2_binary": [2],
            "dual_decoder": False,
            "v1_header_mutation": mutation_matrix["v1-header"],
        },
        "records": {
            "installer": {
                "id": 8, "bytes": installer["file_size"],
                "headroom_bytes": 1792 - installer["file_size"],
                "entry_offset": installer["entry_offset"], "abi_version": 1,
            },
            "carrier": {
                "id": 9, "bytes": carrier["file_size"],
                "headroom_bytes": 1792 - carrier["file_size"],
                "entry_offset": carrier["entry_offset"], "abi_version": 0,
                "destination": carrier["vma"], "sha256": carrier["sha256"],
                "crc16": carrier["crc16"],
            },
        },
        "runtime_banks": {
            "boot": {
                "records": len(boot_manifest["slices"]),
                "bytes": boot[0].stat().st_size,
                "headroom_bytes": 65536 - boot[0].stat().st_size,
            },
            "session": {
                "records": len(session_manifest["slices"]),
                "bytes": session[0].stat().st_size,
                "headroom_bytes": 65536 - session[0].stat().st_size,
            },
        },
        "resident_walls": walls,
        "e000_equation": "531 - 416 - 6 = 115",
        "packer_mutations": mutation_matrix,
        "fresh_structural_gates": {
            "handoff": handoff["status"],
            "pre_ownership": pre["status"],
            "profile_data_references": data_refs["status"],
            "fixed_facade": facade["status"],
            "runtime_family_identity": identity["status"],
            "one_truth": "passed",
            "kernal_freedom": kernal["status"],
            "provisional_window": provisional["status"],
            "verifier_publish_last": binding["status"],
        },
        "substitution_balance_probe": balance["status"],
        "artifacts": {
            "probe_prg": bind(probe), "probe_elf": bind(elf),
            "boot_image": bind(boot[0]), "boot_manifest": bind(boot[1]),
            "session_image": bind(session[0]),
            "session_manifest": bind(session[1]),
            "resolved_profile": bind(resolved),
        },
        "claim_limit": (
            "Product-shaped L65R-v2 packer/target-decoder implementation, "
            "capacity, placement and structural probe only. This is not Link "
            "33, a hardware run, promotion or acceptance."),
        "next_gate": "separate authorization for a fresh Link 33 with no inherited green",
    }
    report = OUT / "l65r-v2-product-implementation-capacity-probe.json"
    write(report, json.dumps(result, indent=2, sort_keys=True) + "\n")
    receipt = {**result, "report": bind(report)}
    write(RECEIPT, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    os.chmod(RECEIPT, 0o444)
    protect(OUT)
    return receipt


def bind_first_red(error: BaseException) -> dict[str, Any]:
    """Conserve the sole authorized probe even when its first gate is red."""
    require(OUT.exists(), "cannot bind first red before the probe output exists")
    require(not RECEIPT.exists(), "refusing to overwrite an existing probe receipt")
    evidence: list[dict[str, Any]] = []
    for path in sorted(item for item in OUT.rglob("*") if item.is_file()):
        evidence.append(bind(path))
    result = {
        "format": "lisp65-c2-l65r-v2-product-implementation-capacity-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: sole product-shaped L65R-v2 probe stopped",
        "diagnostic": {
            "exception_type": type(error).__name__,
            "message": str(error),
        },
        "scope": {
            "product_closure_links": 0,
            "link33_attempts": 0,
            "hardware_runs": 0,
            "retry_authorized": False,
        },
        "canonical_product_profile": PROFILE.receipt_identity(),
        "link32_rollback": {**bind(LINK32), "status": "untouched"},
        "evidence": evidence,
        "claim_limit": (
            "Receipt-less diagnostic evidence from the sole authorized "
            "product-shaped probe. No Link 33, hardware execution, promotion "
            "or acceptance is claimed."),
        "next_gate": "review of this first red; no automatic retry",
    }
    report = OUT / "l65r-v2-product-implementation-capacity-first-red.json"
    write(report, json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = bind(report)
    write(RECEIPT, json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.chmod(RECEIPT, 0o444)
    protect(OUT)
    return result


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "L65R-v2 product probe is one-shot and already has output")
    try:
        return run_probe_once()
    except (ProbeError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        if OUT.exists() and not RECEIPT.exists():
            return bind_first_red(error)
        raise


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "L65R-v2 product probe receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-product-shaped-implementation-capacity-no-link33",
            "L65R-v2 product probe is not green")
    for row in value["artifacts"].values():
        path = ROOT / row["path"]
        require(path.is_file() and sha(path) == row["sha256"],
                f"probe artifact drift: {path}")
    require(sha(LINK32) == LINK32_SHA, "Link-32 rollback identity drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = run_probe() if args.action == "run" else check()
    print("c2-l65r-v2-product-probe: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-l65r-v2-product-probe: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
