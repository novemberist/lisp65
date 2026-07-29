#!/usr/bin/env python3
"""Run the F1 published-value call through one current product WPLTO."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_top_level_published_value_call_gate as F1  # noqa: E402


BASE = ROOT / "build/post-promotion/f1"
STATIC_PRODUCT = BASE / "product"
V6 = BASE / "v6-semantics"
BUILD = BASE / "product-shaped"
WPLTO = BUILD / "wplto"
RECEIPTS = BUILD / "receipts"
STATIC_RECEIPT = RECEIPTS / "f1-static-plane-authority.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-f1-published-value-call-wplto-receipt.json"
EXPECTED_STATIC = 34748
EXPECTED_ENTRIES = 596
EXPECTED_RESOLUTIONS = 2283
EXPECTED_ROOTS = 283

SPECS = (
    ("stdlib-p0", "stdlib", BASE / "stdlib-p0.manifest.json"),
    ("ide", "ide", CAN.STATIC / "libs/ide.manifest.json"),
    ("idex", "idex", CAN.STATIC / "libs/idex.manifest.json"),
    ("m65d", "m65d", CAN.STATIC / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/c2.2/substitution/lcc.manifest.json"),
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"F1 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bank2_fixture_product() -> dict[str, Any]:
    artifacts = {
        "c2d": bind(V6 / "initial.c2d-v6.bin"),
        "code": bind(V6 / "bank2-static-code.bin"),
        "shelf": bind(STATIC_PRODUCT / "product-shelf-v4-direct.bin"),
    }
    require(
        artifacts["c2d"]["bytes"] == 33840
        and artifacts["code"]["bytes"] == EXPECTED_STATIC
        and artifacts["shelf"]["bytes"] == 71710,
        "F1 Bank-2 fixture geometry drift",
    )
    return {"host_c2d_v6": {"artifacts": artifacts}}


def bank2_target_fixture(product: dict[str, Any]) -> dict[str, Any]:
    artifacts = product["host_c2d_v6"]["artifacts"]
    shelf_path = ROOT / artifacts["shelf"]["path"]
    c2d_path = ROOT / artifacts["c2d"]["path"]
    expected_path = ROOT / artifacts["code"]["path"]
    elf = CAN.LINK_GATE.BASE.ELF
    fixture_dir = WPLTO / "fresh-c2-lite-prelink-gates/bank2-target-stage"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    workbench_path = fixture_dir / "current-workbench-overlay.bin"
    scratch_in = fixture_dir / "workbench-extract-input.elf"
    scratch_out = fixture_dir / "workbench-extract-output.elf"
    shutil.copyfile(elf, scratch_in)
    CAN.run([
        str(CAN.OBJCOPY), "--dump-section",
        f".lisp65_workbench_overlay={workbench_path}",
        str(scratch_in), str(scratch_out),
    ], "extract F1 Workbench negative fixture")
    scratch_in.unlink()
    scratch_out.unlink()

    shelf = shelf_path.read_bytes()
    c2d = c2d_path.read_bytes()
    expected_plane = expected_path.read_bytes()
    scratch = workbench_path.read_bytes()
    require(
        len(expected_plane) == EXPECTED_STATIC
        and 0 < len(scratch) <= 1792,
        "F1 Bank-2 target fixture artifact geometry drift",
    )
    rows: list[dict[str, Any]] = []
    cursor = 0
    for image in range(6):
        shelf_record = shelf[32 + image * 32:64 + image * 32]
        c2d_record = c2d[48 + image * 32:80 + image * 32]
        source = int.from_bytes(shelf_record[8:11], "little")
        length = int.from_bytes(shelf_record[11:13], "little")
        crc = int.from_bytes(shelf_record[18:22], "little")
        target = int.from_bytes(c2d_record[18:21], "little")
        require(
            target == cursor
            and int.from_bytes(c2d_record[21:23], "little") == length
            and zlib.crc32(shelf[source:source + length]) & 0xffffffff == crc
            and zlib.crc32(expected_plane[target:target + length])
                & 0xffffffff == crc,
            f"F1 Bank-2 record {image} source/target binding red",
        )
        rows.append({
            "image": image, "source": source, "target": target,
            "bytes": length, "crc32": f"0x{crc:08x}",
        })
        cursor += length
    require(cursor == EXPECTED_STATIC,
            "F1 Bank-2 records do not close the exact plane")
    scratch_plane = scratch + bytes(EXPECTED_STATIC - len(scratch))
    scratch_matches = sum(
        (zlib.crc32(scratch_plane[row["target"]:
                                  row["target"] + row["bytes"]])
         & 0xffffffff) == int(row["crc32"], 16)
        for row in rows
    )
    require(scratch_matches == 0,
            "F1 Workbench scratch unexpectedly passes a code record")
    return {
        "status": "passed-six-F1-record-target-and-workbench-negative",
        "records": rows,
        "record_count": len(rows),
        "static_plane_bytes": cursor,
        "expected_plane_all_target_crcs": "passed",
        "workbench_scratch_bytes": len(scratch),
        "workbench_scratch_passing_records": scratch_matches,
        "ready_if_workbench_scratch_remains": False,
        "shelf": bind(shelf_path),
        "c2d": bind(c2d_path),
        "expected_bank2": bind(expected_path),
        "workbench": bind(workbench_path),
        "linked_elf": bind(elf),
    }


def configure() -> None:
    old_static = CAN.STATIC
    os.environ.update(CAN.canonical_build_environment())
    CAN.BUILD = BUILD
    CAN.WPLTO = WPLTO
    CAN.FINAL = BUILD / "final"
    CAN.ARTIFACTS = BUILD / "artifacts"
    CAN.RECEIPTS = RECEIPTS
    CAN.MANIFEST = BUILD / "canonical-product-manifest.json"
    CAN.STATIC = BASE
    CAN.STATIC_PRODUCT = STATIC_PRODUCT
    CAN.STATIC_RECEIPT = STATIC_RECEIPT
    CAN.SPECS = SPECS
    CAN.PREFIXES = tuple(
        (path.with_suffix(""), "stdlib" if index == 0 else "disk-lib",
         None if index == 0 else "0x000000")
        for index, (_key, _name, path) in enumerate(SPECS)
    )

    PLANE.FRESH_ROOT = BASE
    PLANE.FRESH_PRODUCT = STATIC_PRODUCT / "substitution-artifacts.json"
    PLANE.FRESH_IDE = old_static / "libs/ide.manifest.json"
    PLANE.FRESH_BANK2 = V6 / "bank2-static-code.bin"
    PLANE.FRESH_MANIFESTS = tuple(path for _key, _name, path in SPECS)
    CAN.fresh_bank2_fixture_product = bank2_fixture_product
    CAN.fresh_bank2_target_fixture = bank2_target_fixture

    # Several historical successor adapters replay the semantic model from a
    # copied predecessor tree.  Their module-level cleanup restores the old
    # A.SPECS tuple before a later adapter asks the model again.  F1's driver
    # binds every such replay to the current six manifests at the actual call
    # boundary; otherwise the model would compare the new 34,748-byte profile
    # against the promoted 34,542-byte plane.
    original_host_semantics = CAN.V6.host_semantics

    def f1_host_semantics() -> dict[str, Any]:
        CAN.V6.PRODUCT_IDENTITY = (
            STATIC_PRODUCT / "substitution-artifacts.json")
        CAN.V6.STATIC_CODE_BYTES = EXPECTED_STATIC
        CAN.V6.A.SPECS = SPECS
        return original_host_semantics()

    CAN.V6.host_semantics = f1_host_semantics

    original_single_link = CAN.PRODUCT.single_link

    def f1_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path = CAN.PRODUCT.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        # Historical successor adapters restore PRODUCT globals while
        # unwinding their own predecessor scopes.  Bind the one actual link
        # at its call boundary so C2D, shelf and the compiled profile cannot
        # come from different product identities.
        CAN.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
            STATIC_PRODUCT / "substitution-artifacts.json")
        CAN.PRODUCT.INITIAL_C2D = (
            STATIC_PRODUCT / "initial.c2d-v3.bin")
        CAN.PRODUCT.PRODUCT_SHELF = (
            STATIC_PRODUCT / "product-shelf-v4-direct.bin")
        return original_single_link(
            out,
            probe_definitions=probe_definitions,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=extra_contract_lines,
        )

    CAN.PRODUCT.single_link = f1_single_link

    original_artifact_profile_gate = (
        CAN.LINK57.canonical_artifact_profile_gate)

    def f1_artifact_profile_gate(out: Path) -> dict[str, Any]:
        # The same historical stack also restores LINK57.PRODUCT_IDENTITY
        # before its post-link gate.  Rebind the reader as well as the writer;
        # this is a read-only check over the just-linked F1 artifacts.
        old_identity = CAN.LINK57.PRODUCT_IDENTITY
        try:
            CAN.LINK57.PRODUCT_IDENTITY = (
                STATIC_PRODUCT / "substitution-artifacts.json")
            return original_artifact_profile_gate(out)
        finally:
            CAN.LINK57.PRODUCT_IDENTITY = old_identity

    CAN.LINK57.canonical_artifact_profile_gate = f1_artifact_profile_gate


def static_gate() -> dict[str, Any]:
    product = load(STATIC_PRODUCT / "substitution-artifacts.json")
    profile = load(CAN.PROFILE)
    require(
        product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and profile["product_build_id"] == product["product_build_id_hex"],
        "F1 substitution/profile identity drift",
    )
    bundle = CAN.fresh_static_plane_bundle()
    report = PLANE.validate(bundle)
    mutations = PLANE.mutations(bundle)
    require(
        report["static_code_bytes"] == EXPECTED_STATIC
        and report["entries"] == EXPECTED_ENTRIES
        and len(mutations) == 6,
        "F1 static-plane gate red",
    )
    STATIC_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    STATIC_RECEIPT.write_text(
        json.dumps(bundle["receipt"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**report, "mutations_rejected": mutations}


def main() -> int:
    try:
        resume = (
            BUILD.exists()
            and (RECEIPTS / "wplto-internal.json").is_file()
            and not RECEIPT.exists()
        )
        require((not BUILD.exists() or resume) and not RECEIPT.exists(),
                "F1 WPLTO probe is one-shot or read-only qualification resume")
        source = F1.validate_source(F1.bundle())
        source["mutations_rejected"] = F1.mutation_tests(F1.bundle())
        execution = F1.executable_fixtures()
        configure()
        BUILD.mkdir(parents=True, exist_ok=resume)
        plane = static_gate()
        if resume:
            internal = load(RECEIPTS / "wplto-internal.json")
            require(
                internal["status"]
                    == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
                and (WPLTO / "lisp65-c2-substitution-linked.prg.elf").is_file()
                and (WPLTO / "lisp65-c2-substitution-linked.prg.map").is_file(),
                "F1 read-only WPLTO resume lacks a green linked closure",
            )
            replacement = internal["fresh_replacement_gates"]
            wplto = {
                "status":
                    "passed-read-only-qualification-of-existing-F1-WPLTO",
                "new_compiler_runs": 0,
                "new_linker_runs": 0,
                "internal": bind(RECEIPTS / "wplto-internal.json"),
                "qualification": bind(
                    RECEIPTS / "wplto-qualification.json"),
            }
        else:
            wplto = CAN.run_wplto()
            replacement = wplto["historical_checker_boundary"][
                "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        require(
            wplto["status"].startswith("passed-")
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_headroom_bytes"] == 610,
            "F1 WPLTO crossed a bound wall",
        )
        value = {
            "format": "lisp65-c2-f1-published-value-call-WPLTO-v1",
            "recorded_on": "2026-07-27",
            "status": "passed-F1-product-shaped-WPLTO-all-walls-green",
            "promotable": False,
            "hardware_runs": 0,
            "source_gate": source,
            "execution_gate": execution,
            "static_plane_gate": plane,
            "freight": {
                "bank2_static_code_baseline_bytes": 34542,
                "bank2_static_code_candidate_bytes": EXPECTED_STATIC,
                "bank2_delta_bytes": EXPECTED_STATIC - 34542,
                "native_source_delta_bytes": 0,
                "linked_bank0_text_delta_bytes": 3,
                "linked_bank0_text_attribution":
                    "identity-driven Whole-Program-LTO movement; no native "
                    "source or feature define changed",
                "entries_baseline": 590,
                "entries_candidate": EXPECTED_ENTRIES,
                "resolutions_baseline": 2273,
                "resolutions_candidate": EXPECTED_RESOLUTIONS,
                "roots_baseline": EXPECTED_ROOTS,
                "roots_candidate": EXPECTED_ROOTS,
            },
            "walls": walls,
            "capacity": capacity,
            "wplto": wplto,
            "qualification_history": {
                "prelink_wrapper_first_red": (
                    "historical semantic replay restored the v1.2.0 static "
                    "manifest tuple; no product link ran"),
                "postlink_writer_first_red": (
                    "historical successor restored the v1.2.0 product "
                    "identity before single_link"),
                "postlink_reader_first_red": (
                    "the link consumed F1 identity but the historical "
                    "postlink reader restored v1.2.0 before comparison"),
                "final_qualification":
                    "read-only over the existing third WPLTO ELF/map; no "
                    "additional compiler or linker run",
            },
            "authority": {
                "contract": bind(F1.CONTRACT),
                "contract_note": bind(
                    ROOT / "docs/planning/"
                    "c2.2-f1-published-value-direct-call-contract.md"),
                "source": bind(F1.SOURCE),
                "source_gate": bind(Path(F1.__file__)),
                "profile": bind(CAN.PROFILE),
                "static_header": bind(PLANE.HEADER),
                "substitution": bind(
                    STATIC_PRODUCT / "substitution-artifacts.json"),
                "bank2": bind(V6 / "bank2-static-code.bin"),
                "linked_elf": bind(
                    WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
                "driver": bind(Path(__file__)),
            },
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (ProbeError, CAN.CanonicalError, PLANE.GateError, F1.GateError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-f1-published-value-call-WPLTO: FIRST RED: {error}",
              file=sys.stderr)
        return 2
    print(
        "c2-f1-published-value-call-WPLTO: PASS "
        f"bank2={EXPECTED_STATIC} delta=+{EXPECTED_STATIC - 34542} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
