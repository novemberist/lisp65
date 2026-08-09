#!/usr/bin/env python3
"""Build the canonical C2-lite product tree from a clean checkout.

The historical C2.2 drivers are deliberately one-shot evidence generators.
This wrapper gives Fresh-Clone/R4 a repeatable entry point without weakening
their gates: it regenerates the six-image Lisp plane, runs one current WPLTO
closure, performs the established post-link publish-last completion without a
second link, and emits one manifest for the media packer.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_stdlib as BYTECODE  # noqa: E402
import c2_append_phase_plan_gate as APPEND_PLAN  # noqa: E402
import c2_badopcode_hold_shelf_gate as HOLD_SHELF  # noqa: E402
import c2_direct_entry_contract as DIRECT_ENTRY  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_hot_refill_successor_link as HOT_REFILL  # noqa: E402
import c2_journal_prepare_coresident_gate as JOURNAL_PREPARE  # noqa: E402
import c2_lite_v6_export_symbol_domain_successor_link as EXPORT_DOMAIN  # noqa: E402
import c2_lite_v6_bank2_target_stage_phase02b_artifact_replay as BANK2_REPLAY  # noqa: E402
import c2_lite_v6_final_island_identity_successor_link as FINAL_ISLAND  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_lite_v6_real_abi_direct_entry_contract as REAL_DIRECT  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_successor_link as REAL_ABI_LINK  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as LINK49  # noqa: E402
import c2_lite_v6_link50_persistent_header_successor_link as LINK50  # noqa: E402
import c2_lite_v6_link45_bcode_ordinal_wplto as ORDINAL  # noqa: E402
import c2_lite_v6_link50_badopcode_retirement_wplto as RETIRE_WPLTO  # noqa: E402
import c2_lite_v6_link52_install_phase_wplto as LEGACY_WPLTO  # noqa: E402
import c2_link57_l_full_keymap_current_product_wplto as LINK57  # noqa: E402
import c2_matrix_addenda_fixed_block_wplto_final2 as MATRIX_FINAL  # noqa: E402
import c2_matrix_addenda_wplto as MATRIX_WPLTO  # noqa: E402
import c2_nested_append_unwind_probe as NESTED_MODEL  # noqa: E402
import c2_nested_append_v5_prelink as NESTED_PRELINK  # noqa: E402
import c2_product_compiler_tier as COMPILER_TIER  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_substitution_artifacts as SUBSTITUTION  # noqa: E402
import c2_link65_single_submit_completion_wplto as LINK_GATE  # noqa: E402
import c2_link64_nonlto_completion_artifact_replay as REPLAY  # noqa: E402
import c2_zero_literal_execution_gate as ZERO_LITERAL  # noqa: E402


_ORIGINAL_PLANE_SOURCE_BUNDLE = PLANE.source_bundle
BUILD = ROOT / "build/c2.2/canonical-product"
STATIC = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts")
STATIC_PRODUCT = STATIC / "product"
WPLTO = BUILD / "wplto"
FINAL = BUILD / "final"
ARTIFACTS = BUILD / "artifacts"
RECEIPTS = BUILD / "receipts"
MANIFEST = BUILD / "canonical-product-manifest.json"
CONTRACT = ROOT / "config/c2-lite-media-product.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
WPLTO_FEATURE_PROFILE = (
    ROOT / "config/c2-lite-v6-roots-fronts-product-profile.json")
CANONICAL_BUILD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "LISP65_LTO_RNG_SEED": "0",
    "LISP65_LTO_THREADS": "1",
    "LISP65_DETERMINISTIC_OBJECTS": "1",
    "LISP65_LLVM_LINK": "/usr/bin/llvm-link",
    "LISP65_DISABLE_LINK_ASLR": "1",
    "SOURCE_DATE_EPOCH": "1785024000",
    "TZ": "UTC",
    "LC_ALL": "C",
    "LANG": "C",
    "LISP65_PUBLIC_CLEAN_BUILD": "1",
}
PUBLIC_BUILD_AUTHORITY = ROOT / "config/c2-lite-public-build-authority.json"
DIRECT_ENTRY_ENV_KEYS = (
    "LISP65_DIRECT_ENTRY_PROFILE",
    "LISP65_DIRECT_ENTRY_SHELF",
    "LISP65_DIRECT_ENTRY_C2D",
    "LISP65_DIRECT_ENTRY_ARTIFACTS",
    "LISP65_DIRECT_ENTRY_BUILD",
    "LISP65_DIRECT_ENTRY_RECEIPT",
    "LISP65_DIRECT_ENTRY_EXPECTED_REFS",
    "LISP65_DIRECT_ENTRY_EXPECTED_CHANGED_BINDINGS",
    "LISP65_DIRECT_ENTRY_PUBLIC_CLEAN_BUILD",
)
STATIC_RECEIPT = RECEIPTS / "fresh-static-plane-authority.json"
TOOLCHAIN = Path(os.environ.get(
    "LLVM_MOS_ROOT", str(ROOT / "tools/llvm-mos")))
COMPILER = TOOLCHAIN / "bin/mos-mega65-clang"
OBJCOPY = TOOLCHAIN / "bin/llvm-objcopy"

SUITES = (
    ROOT / "build/bytecode/dialect-v2/suites/"
        "p0-stdlib-einsuite-core-workbench-subset.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-extra-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-m65d-lib.json",
    ROOT / "tests/bytecode/libs/p0-buffer-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-c2-compiler-tier.json",
)
PREFIXES = (
    (STATIC / "workbench/stdlib-p0", "stdlib", None),
    (STATIC / "libs/ide", "disk-lib", "0x000000"),
    (STATIC / "libs/idex", "disk-lib", "0x000000"),
    (STATIC / "libs/m65d", "disk-lib", "0x000000"),
    (ROOT / "build/bytecode/dialect-v2/libs/buffer",
     "disk-lib", "0x000000"),
    (ROOT / "build/c2.2/substitution/lcc", "disk-lib", "0x000000"),
)
SPECS = tuple(
    (key, name, prefix.with_suffix(".manifest.json"))
    for (key, name), (prefix, _role, _base) in zip(
        (
            ("stdlib-p0", "stdlib"), ("ide", "ide"), ("idex", "idex"),
            ("m65d", "m65d"), ("buffer", "buffer"), ("lcc", "lcc"),
        ),
        PREFIXES,
    )
)


class CanonicalError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CanonicalError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, role: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"canonical artifact absent: {path}")
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if role is not None:
        row["role"] = role
    return row


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise CanonicalError(
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def make_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)


def protect(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)


def static_plane_valid() -> bool:
    try:
        result = PLANE.validate(fresh_static_plane_bundle())
    except Exception:
        return False
    return (
        result.get("status")
        == "passed-canonical-L-full-static-plane-to-target-dataflow"
        and all(path.is_file() for _key, _name, path in SPECS)
        and (STATIC_PRODUCT / "product-shelf-v4-direct.bin").is_file()
        and (STATIC / "v6-semantics/bank2-static-code.bin").is_file()
    )


def public_build_authority() -> dict[str, Any]:
    value = load(PUBLIC_BUILD_AUTHORITY)
    identity = value.get("sealed_profile_identity")
    legacy = value.get("sealed_legacy_profile_fields")
    require(
        value["format"] in {
            "lisp65-c2-lite-public-build-authority-v1",
            "lisp65-c2-lite-public-build-authority-v2",
        }
        and value["build_model"] ==
            "fresh-source-single-emitter-plus-one-WPLTO"
        and value["private_evidence_is_build_input"] is False
        and isinstance(identity, dict)
        and set(identity) == {"field", "sha256", "meaning"}
        and identity["field"] == "direct_entry_contract_sha256"
        and isinstance(identity["sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", identity["sha256"]) is not None
        and isinstance(identity["meaning"], str)
        and "private historical receipt bytes are not build inputs"
            in identity["meaning"]
        and isinstance(legacy, dict)
        and re.fullmatch(
            r"[0-9a-f]{64}", str(legacy.get("c2_artifacts_sha256", "")))
            is not None
        and "checkout-absolute diagnostic paths"
            in str(legacy.get("meaning", "")),
        "public C2-lite build authority drift")
    return value


def canonical_build_environment() -> dict[str, str]:
    """Return the deterministic environment plus the sealed profile token.

    The direct-entry gate still runs against freshly emitted current sources.
    Only the legacy identity field embedded in the accepted product profile is
    stable: hashing the newly written diagnostic receipt would make private
    historical prose and path bindings part of the product identity.
    """
    authority = public_build_authority()
    return {
        **CANONICAL_BUILD_ENVIRONMENT,
        "LISP65_DIRECT_ENTRY_IDENTITY_SHA256":
            authority["sealed_profile_identity"]["sha256"],
    }


def fresh_static_plane_bundle() -> dict[str, Any]:
    """Apply the semantic profile to this checkout's freshly emitted files.

    The historical source gate also pins diagnostic manifest byte streams.
    Those manifests contain checkout-absolute paths and are deliberately not
    product artifacts.  Fresh Clone instead binds the emitted code/container
    identities through the profile while allowing those private paths to
    differ.
    """
    return _ORIGINAL_PLANE_SOURCE_BUNDLE()


def write_static_plane_authority() -> dict[str, Any]:
    bundle = fresh_static_plane_bundle()
    value = bundle["receipt"]
    STATIC_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    STATIC_RECEIPT.write_bytes(json_bytes(value))
    return value


def build_static_plane() -> dict[str, Any]:
    if static_plane_valid():
        write_static_plane_authority()
        return {
            "status": "passed-existing-byteidentical-static-plane",
            "gate": PLANE.validate(fresh_static_plane_bundle()),
        }
    require(not STATIC.exists(),
            "partial canonical static plane exists but fails its authority")
    run(["make", "fasl-emit-check"],
        "canonical real-compiler L65M oracle")
    run([sys.executable, "tools/host-lisp/v2_workbench_codemod.py"],
        "canonical Workbench codemod")
    COMPILER_TIER.generate(SUITES[-1])
    for suite, (prefix, role, base) in zip(SUITES, PREFIXES):
        prefix.parent.mkdir(parents=True, exist_ok=True)
        # The emitter records its command-line paths in private diagnostics.
        # Feed it checkout-relative paths so those diagnostics cannot leak the
        # fresh-clone directory name into the resolved product profile.
        relative_prefix = prefix.relative_to(ROOT).as_posix()
        relative_suite = suite.relative_to(ROOT).as_posix()
        command = [
            sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check", "--emit-artifacts", relative_prefix,
        ]
        if role == "disk-lib":
            command += ["--artifact-role", role, "--base-addr", str(base)]
        command.append(relative_suite)
        run(command, f"emit {prefix.name}")

    old_sub = (SUBSTITUTION.BUILD, SUBSTITUTION.SPECS)
    old_v6 = (
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUBSTITUTION.BUILD = STATIC_PRODUCT
        SUBSTITUTION.SPECS = SPECS
        product = SUBSTITUTION.build()
        static_bytes = sum(
            int(load(path)["code_bytes"]) for _key, _name, path in SPECS)
        V6.OUT = STATIC / "v6-semantics"
        V6.PRODUCT_IDENTITY = STATIC_PRODUCT / "substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = static_bytes
        V6.A.SPECS = SPECS
        V6.OUT.mkdir(parents=True, exist_ok=True)
        semantics = V6.host_semantics()
    finally:
        SUBSTITUTION.BUILD, SUBSTITUTION.SPECS = old_sub
        (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES,
         V6.A.SPECS) = old_v6

    write_static_plane_authority()
    gate = PLANE.validate(fresh_static_plane_bundle())
    require(
        product["images"] == 6 and product["entries"] == 590
        and static_bytes == 34542
        and semantics["static_bank2"]["code_bytes"] == 34542
        and gate["status"]
            == "passed-canonical-L-full-static-plane-to-target-dataflow",
        "fresh static-plane emission differs from its canonical profile")
    protect(STATIC)
    return {
        "status": "passed-fresh-byteidentical-static-plane",
        "product": product,
        "semantics": semantics,
        "gate": gate,
    }


def fresh_link57_authority() -> dict[str, Any]:
    """Bind the inherited Link-57 WPLTO to fresh current-plane artifacts.

    Link 57's hardware latency history is acceptance evidence, not an input to
    a source build.  Fresh Clone therefore proves the current static plane and
    keymap from source and records the public build-model authority explicitly.
    """
    plane_bundle = fresh_static_plane_bundle()
    plane = PLANE.validate(plane_bundle)
    plane["mutations_rejected"] = len(PLANE.mutations(plane_bundle))
    key_bundle = LINK57.KEYGATE.source_bundle()
    keymap = LINK57.KEYGATE.validate(key_bundle, run_oracle=True)
    keymap["mutations_rejected"] = LINK57.KEYGATE.mutation_tests(key_bundle)
    require(
        plane["mutations_rejected"] == 7
        and keymap["mutations_rejected"] == 10,
        "fresh Link-57 static/keymap authority is incomplete")
    return {
        "fresh_clone_static_product_receipt": bind(STATIC_RECEIPT),
        "fresh_clone_substitution_artifacts": bind(
            STATIC_PRODUCT / "substitution-artifacts.json"),
        "fresh_clone_IDE_manifest": bind(
            PREFIXES[1][0].with_suffix(".manifest.json")),
        "public_build_authority": bind(PUBLIC_BUILD_AUTHORITY),
        "acceptance_history": {
            "classification": "not-a-build-input",
            "rule": public_build_authority()["acceptance_evidence_rule"],
        },
        "L_full_product_profile": bind(PLANE.PROFILE),
        "static_plane_header": bind(PLANE.HEADER),
        "static_plane_gate": {
            **bind(Path(PLANE.__file__)), "result": plane},
        "keymap_end_to_end_gate": {
            **bind(Path(LINK57.KEYGATE.__file__)), "result": keymap},
        "driver": bind(Path(LINK57.__file__)),
    }


def fresh_link49_features() -> tuple[str, ...]:
    """Resolve the Link-49 layer from structured, tracked authorities.

    The historical successor drivers parsed a private ``resolved-profile``
    file from an earlier local WPLTO.  Fresh Clone instead consumes the
    tracked base profile and the three approved Link-49 contract features.
    The historical tuple remains a cross-check, never the source.
    """
    profile = load(WPLTO_FEATURE_PROFILE)
    base = tuple(profile["feature_defines"])
    hybrid = load(LINK49.CONTRACT)
    additions = (
        hybrid["append_plan_facade16"]["feature"],
        LINK49.NUMERIC.FEATURE,
        "LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT",
    )
    features = (*base, *additions)
    require(
        profile["format"]
            == "lisp65-c2-lite-v6-roots-fronts-product-profile-v1"
        and len(base) == 19
        and len(set(features)) == len(features)
        and features == LINK49.EXPECTED_FEATURES,
        "structured Link-49 feature profile differs from its approved "
        "contract layer")
    # Both historical failure directions are explicit: omitting a layer or
    # leaking the later journal layer into this predecessor must fail.
    mutations = (
        features[:-1],
        (*features, "LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT"),
        (*features[:19], features[20], features[19], *features[21:]),
    )
    require(
        all(tuple(row) != LINK49.EXPECTED_FEATURES for row in mutations),
        "structured Link-49 profile mutations are ineffective")
    return features


def fresh_bank3_lifetime() -> dict[str, Any]:
    """Exercise lifetime exclusivity on fresh, bound source-plane bytes.

    Exact final Boot/Session family identities are checked after linking.
    This prelink model proves only the Bank-3 lifetime transition, so it must
    not reopen Link-35 product binaries merely to obtain payload bytes.
    """
    boot_source = STATIC / "v6-semantics/bank2-static-code.bin"
    session_source = STATIC_PRODUCT / "product-shelf-v4-direct.bin"
    boot = boot_source.read_bytes()[:15605]
    session = session_source.read_bytes()[:60062]
    require(
        len(boot) == 15605 and len(session) == 60062,
        "fresh source-plane lifetime fixtures are truncated")
    bank_bytes = V6.BANK_BYTES
    bank1 = bytes([0xA1]) * bank_bytes
    bank3 = bytearray(bank_bytes)
    generation = 1
    bank3[:len(boot)] = boot
    boot_binding = ("boot", generation, hashlib.sha256(
        bytes(bank3[:len(boot)])).hexdigest())
    generation += 1
    bank3[:] = b"\0" * bank_bytes
    bank3[:len(session)] = session
    session_binding = ("session", generation, hashlib.sha256(
        bytes(bank3[:len(session)])).hexdigest())
    require(
        boot_binding[1] != session_binding[1]
        and bank1 == bytes([0xA1]) * bank_bytes,
        "fresh Bank-3 lifetime transition or Bank-1 exclusion failed")
    return {
        "status": "passed-lifetime-exclusive",
        "fixture_policy":
            "fresh-bound-source-slices; final-family identity is postlink",
        "boot": {
            "bytes": len(boot), "sha256": boot_binding[2],
            "bank": 3, "headroom_bytes": bank_bytes - len(boot),
            "generation": 1, "source_artifact": bind(boot_source),
        },
        "session": {
            "bytes": len(session), "sha256": session_binding[2],
            "bank": 3, "headroom_bytes": bank_bytes - len(session),
            "generation": 2, "source_artifact": bind(session_source),
        },
        "simultaneously_callable": False,
        "invalidation_before_overwrite": True,
        "stale_boot_binding_rejected": True,
        "bank1_untouched": True,
    }


def fresh_bank2_fixture_product() -> dict[str, Any]:
    """Bind the Bank-2 target fixture to this build's emitted artifacts.

    The inherited phase-02b replay used private predecessor receipts merely
    to recover these three paths.  Their target-dataflow and negative-scratch
    semantics are independent of that history, so Fresh Clone feeds the gate
    the current single-emitter artifacts directly.
    """
    artifacts = {
        "c2d": bind(STATIC / "v6-semantics/initial.c2d-v6.bin"),
        "code": bind(STATIC / "v6-semantics/bank2-static-code.bin"),
        "shelf": bind(STATIC_PRODUCT / "product-shelf-v4-direct.bin"),
    }
    require(
        artifacts["c2d"]["bytes"] == 33840
        and artifacts["code"]["bytes"] == 34542
        and artifacts["shelf"]["bytes"] == 71194,
        "fresh Bank-2 target fixture geometry drift")
    return {"host_c2d_v6": {"artifacts": artifacts}}


def fresh_bank2_target_fixture(product: dict[str, Any]) -> dict[str, Any]:
    """Run the target-CRC negative against this link's Workbench overlay."""
    artifacts = product["host_c2d_v6"]["artifacts"]
    shelf_path = ROOT / artifacts["shelf"]["path"]
    c2d_path = ROOT / artifacts["c2d"]["path"]
    expected_path = ROOT / artifacts["code"]["path"]
    elf = LINK_GATE.BASE.ELF
    fixture_dir = WPLTO / "fresh-c2-lite-prelink-gates/bank2-target-stage"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    workbench_path = fixture_dir / "current-workbench-overlay.bin"
    scratch_in = fixture_dir / "workbench-extract-input.elf"
    scratch_out = fixture_dir / "workbench-extract-output.elf"
    shutil.copyfile(elf, scratch_in)
    run([
        str(OBJCOPY), "--dump-section",
        f".lisp65_workbench_overlay={workbench_path}",
        str(scratch_in), str(scratch_out),
    ], "extract current Workbench negative fixture")
    scratch_in.unlink()
    scratch_out.unlink()

    shelf = shelf_path.read_bytes()
    c2d = c2d_path.read_bytes()
    expected_plane = expected_path.read_bytes()
    scratch = workbench_path.read_bytes()
    require(
        len(expected_plane) == 34542 and len(scratch) == 1710,
        "fresh Bank-2 target fixture artifact geometry drift")
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
            f"fresh Bank-2 record {image} source/target binding red")
        rows.append({
            "image": image, "source": source, "target": target,
            "bytes": length, "crc32": f"0x{crc:08x}",
        })
        cursor += length
    require(cursor == 34542, "fresh six Bank-2 records do not close plane")
    scratch_plane = scratch + bytes(34542 - len(scratch))
    scratch_matches = sum(
        (zlib.crc32(scratch_plane[row["target"]:
                                  row["target"] + row["bytes"]])
         & 0xffffffff) == int(row["crc32"], 16)
        for row in rows)
    require(
        scratch_matches == 0,
        "current Workbench scratch unexpectedly passes a code record")
    return {
        "status": "passed-six-current-record-target-and-workbench-negative",
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


def fresh_roots_fronts_product_gate(elf: Path) -> dict[str, Any]:
    """Check the fused entries against the current two-region v4 package."""
    gate = LINK50.BASE.CONS
    truth = gate.ElfTruth.read(
        elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_rt_c2append_roots_fronts")
    symbols = {name: truth.symbol(name) for name in (
        "c2_append_roots_phase",
        "c2_append_fronts_phase",
        "c2_append_roots_fronts_phase",
    )}
    session = elf.parent / "runtime-overlays-session-final.bin"
    overflow = elf.parent / "runtime-overlays-session-final-region1.bin"
    manifest = load(elf.parent / "runtime-overlays-session-final.json")
    service_enabled = PRODUCT.INTERN_SESSION_SERVICE
    expected_records = 52 if service_enabled else 51
    expected_session_bytes = (
        int(manifest["storage"]["size"])
        if service_enabled else 64926)
    service_rows = [
        row for row in manifest["slices"]
        if row["name"] == "intern-session-service"]
    require(
        0 < section.bytes <= 1792
        and all(symbol.section == section.name and symbol.bytes > 0
                for symbol in symbols.values())
        and ".lisp65_rt_c2append_roots" not in truth.sections_by_name
        and ".lisp65_rt_c2append_fronts" not in truth.sections_by_name
        and session.stat().st_size == expected_session_bytes
        and expected_session_bytes <= 65536
        and overflow.stat().st_size == 1956
        and manifest["catalog"]["version"] == 4
        and manifest["catalog"]["slice_count"] == expected_records
        and manifest["storage"]["size"] == expected_session_bytes
        and manifest["overflow_storage"]["used"] == 1956
        and manifest["overflow_storage"]["capacity"] == 2032
        and (
            len(service_rows) == 1
            and service_rows[0]["id"] == 51
            and service_rows[0]["section"] == ".lisp65_rt_intern_service"
            and service_rows[0]["region_id"] == 0
            if service_enabled else not service_rows),
        "current roots/fronts two-region product gate red")
    return {
        "status": "passed-one-slice-two-entry-current-v4-product",
        "section": {
            "name": section.name,
            "address": section.address,
            "bytes": section.bytes,
            "headroom_bytes": 1792 - section.bytes,
        },
        "entries": {
            name: {
                "address": symbol.value,
                "bytes": symbol.bytes,
                "section": symbol.section,
            }
            for name, symbol in symbols.items()
        },
        "session_region0_bytes": session.stat().st_size,
        "session_region0_headroom_bytes": 65536 - session.stat().st_size,
        "session_region1_bytes": overflow.stat().st_size,
        "session_region1_headroom_bytes": 2032 - overflow.stat().st_size,
        "session_catalog_records": manifest["catalog"]["slice_count"],
    }


def fresh_final_island_validate_identity(
        image: bytes | bytearray, row: dict[str, Any],
        section: bytes) -> dict[str, Any]:
    """Validate the final carrier under strict L65R-v4 record semantics."""
    gate = FINAL_ISLAND.IDENTITY
    slot = int(row["id"])
    record = gate.raw_record(image, slot)
    values = gate.record_values(record)
    start = int(row["file_offset"])
    end = start + values["file_length"]
    region_id = record[24]
    source_address = (
        values["file_offset"]
        | ((record[25] & 0x0f) << 16)
        | (record[26] << 20))
    gate.require(
        values["slot"] == slot and values["flags"] == 9,
        "carrier record identity/flags drift")
    gate.require(
        values["vma"] == 0x1800
        and values["memory_length"] == values["file_length"]
        and values["entry_offset"] == 0xffff and values["abi"] == 0,
        "carrier DATA_ONLY geometry drift")
    gate.require(
        region_id in (0, 1)
        and region_id == int(row["region_id"])
        and record[25] & 0xf0 == 0
        and record[27:] == bytes(5)
        and source_address == int(row["source_address"])
        and values["file_offset"] == (source_address & 0xffff),
        "carrier L65R-v4 region/source identity drift")
    gate.require(
        values["record_crc16"] != 0
        and values["record_crc16"] == gate.record_crc(record),
        "carrier record self-CRC drift")
    gate.require(
        0 < values["file_length"] <= gate.HARD_MAX
        and end <= len(image),
        "carrier payload bounds drift")
    payload = bytes(image[start:end])
    gate.require(
        values["file_length"] == len(section),
        "carrier record length differs from final Island section")
    gate.require(
        values["payload_crc16"] == gate.crc16(payload)
        == gate.crc16(section),
        "carrier record CRC differs from final Island section")
    gate.require(
        payload == section,
        "carrier payload differs from final section")
    digest = gate.sha_bytes(section)
    gate.require(
        int(row["file_size"]) == len(section)
        and int(row["memory_size"]) == len(section)
        and int(row["crc16"]) == values["payload_crc16"]
        and row["sha256"] == digest,
        "carrier manifest differs from record/final section")
    return {
        "slot": slot,
        **values,
        "region_id": region_id,
        "source_address": source_address,
        "section_bytes": len(section),
        "section_crc16": values["payload_crc16"],
        "section_sha256": digest,
    }


def fresh_real_abi_gate(elf: Path) -> dict[str, Any]:
    """Bind the legacy Link-39 adapter to the complete current ELF surface."""
    report = ABI.audit_elf(
        elf,
        out=REAL_ABI_LINK.OUT / "c2-asm-leaf-real-abi-callers.json",
        require_bank3_chain=True)
    callers = report["rtov_crc_mem_callers"]
    owners: dict[str, int] = {}
    for row in callers["callers"]:
        owners[row["owner"]] = owners.get(row["owner"], 0) + 1
    expected = {
        "vm_runtime_overlay_exec_family": 2,
        "vm_runtime_overlay_catalog_verifier": 1,
        "vm_runtime_overlay_record_verifier": 1,
        "c2_append_journal_write_phase": 1,
        "c2_append_journal_validate_phase": 1,
        "c2_completion_poll": 1,
        "vm_resident_island_install": 2,
    }
    derived = report["ELF_derived_C_called_inventory"]
    require(
        report["status"] == "passed-all-assembler-leaf-abi-contracts"
        and derived["status"]
            == "passed-ELF-derived-C-called-assembler-universe"
        and derived["unclassified_C_called_functions"] == []
        and callers["callsite_count"] == 9
        and owners == expected,
        f"current ELF-derived CRC caller inventory drift: {owners}")
    return {
        "status": report["status"],
        "callsite_count": callers["callsite_count"],
        "owners": owners,
        "product_assembler_callers": 0,
        "ELF_derived_C_called_functions":
            derived["C_called_function_count"],
        "unclassified_C_called_functions":
            derived["unclassified_C_called_functions"],
        "report": report,
    }


_HISTORICAL_WPLTO_QUALIFICATION_MESSAGES = {
    "BADOPCODE retirement WPLTO crossed a bound wall or gate",
    "install-phase WPLTO crossed a bound wall or linked gate",
    "Link-53 first-fault WPLTO qualification red",
    "Link-54 phase-06a cutpoint WPLTO qualification red",
    "Link-55 cold append source-domain WPLTO qualification red",
    "Link-55 append suffix/read-domain WPLTO qualification red",
    "Link-55 append geometry WPLTO qualification red",
    "Link-55 one-quantum fusion qualification red",
    "selector tail-Z WPLTO qualification red",
}


def fresh_current_product_postlink_gate() -> dict[str, Any]:
    """Replace frozen Link-55/56 maps with the live pre-publish closure.

    The historical WPLTO stack runs before artifact-side publish-last
    completion.  Its PRG, ELF and region-0 image therefore deliberately differ
    from the sealed roles after verifier-table binding.  Bind this gate to the
    fresh Link-50 identity and family manifest; the public clean-build gate
    separately requires the completed nineteen-role set byte-for-byte.
    """
    internal = load(LINK_GATE.BASE.INTERNAL)
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    abi = internal["fresh_real_abi_gate"]
    artifacts = {
        "product":
            WPLTO / "lisp65-c2-substitution-linked.prg",
        "elf":
            WPLTO / "lisp65-c2-substitution-linked.prg.elf",
        "map":
            WPLTO / "lisp65-c2-substitution-linked.prg.map",
    }
    for role, path in artifacts.items():
        require(
            path.is_file()
            and bind(path) == internal["product_identity"][role],
            f"current WPLTO identity drift: {role}")
    session_path = WPLTO / "runtime-overlays-session-final.bin"
    region1_path = WPLTO / "runtime-overlays-session-final-region1.bin"
    session_manifest = load(
        WPLTO / "runtime-overlays-session-final.json")
    runtime_family = replacement["runtime_family"][
        "successor_bank3_pack"]["session"]
    overflow = session_manifest["overflow_storage"]
    session_binding = bind(session_path)
    service_enabled = PRODUCT.INTERN_SESSION_SERVICE
    expected_records = 52 if service_enabled else 51
    expected_session_bytes = int(session_manifest["storage"]["size"])
    require(
        internal["status"]
            in {
                "passed-new-c2-lite-real-abi-identity-hardware-not-run",
                "passed-new-c2-lite-persistent-header-identity-hardware-not-run",
            }
        and all(session_binding[key] == runtime_family[key]
                for key in ("path", "bytes", "sha256"))
        and expected_session_bytes <= 65536
        and (service_enabled or expected_session_bytes == 64926)
        and session_manifest["storage"]["sha256"] == sha(session_path)
        and overflow["used"] == 1956
        and overflow["capacity"] == 2032
        and overflow["sha256"] == sha(region1_path)
        and replacement["status"] == "passed"
        and capacity["status"]
            == "passed-current-v4-two-region-session-aggregate"
        and capacity["session_catalog_records"] == expected_records
        and capacity["session_service_records"]
            == (1 if service_enabled else 0)
        and capacity["session_family_bytes"] == expected_session_bytes
        and capacity["session_family_headroom_bytes"]
            == 65536 - expected_session_bytes
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and replacement["bank2_workbench_scratch_negative"]
            ["workbench_scratch_passing_records"] == 0
        and replacement["roots_fronts_one_slice_two_entry"]["status"]
            == "passed-one-slice-two-entry-current-v4-product"
        and replacement["final_island_single_runtime_identity"]
            ["status"]
            == "passed-final-record-equals-final-island-single-truth"
        and replacement["final_island_single_runtime_identity"]
            ["mutation_cases"] == 11
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and abi["callsite_count"] == 9
        and abi["unclassified_C_called_functions"] == [],
        "current sealed postlink closure is not fully green")
    return {
        "status": "passed-current-v4-pre-publish-WPLTO-closure",
        "historical_maps_replaced": sorted(
            _HISTORICAL_WPLTO_QUALIFICATION_MESSAGES),
        "walls": walls,
        "capacity": capacity,
        "assembler_leaf_ABI": {
            "callsite_count": abi["callsite_count"],
            "unclassified_C_called_functions":
                abi["unclassified_C_called_functions"],
        },
        "pre_publish_identity": {
            role: bind(path, role) for role, path in artifacts.items()},
        "pre_publish_session_regions": {
            "region_0": session_binding,
            "region_1": bind(region1_path),
        },
        "sealed_role_check":
            "deferred-to-post-publish-public-clean-build-gate",
    }


def fresh_link49_profile_authority() -> dict[str, Any]:
    features = fresh_link49_features()
    return {
        "status": "passed-bound-structured-Link49-profile-layer",
        "base_profile_object": bind(WPLTO_FEATURE_PROFILE),
        "append_hybrid_contract": bind(LINK49.CONTRACT),
        "feature_defines": list(features),
        "base_feature_count": 19,
        "wrapper_features": list(features[19:]),
        "mutations_rejected": 3,
        "private_resolved_profile_parsing": "forbidden",
    }


def fresh_link49_prerequisites() -> dict[str, Any]:
    """Bind a fresh source closure without reopening rollback products."""
    return {
        "status": "passed-fresh-source-Link49-prerequisites",
        "fresh_clone_static_product_receipt": bind(STATIC_RECEIPT),
        "fresh_clone_substitution_artifacts": bind(
            STATIC_PRODUCT / "substitution-artifacts.json"),
        "complete_product_profile": fresh_link49_profile_authority(),
        "append_final_hybrid_contract": bind(LINK49.CONTRACT),
        "public_build_authority": bind(PUBLIC_BUILD_AUTHORITY),
        "historical_acceptance_evidence":
            "excluded-from-the-clean-build-input-closure",
        "rollback_product_dependency": "forbidden-in-fresh-source-closure",
        "driver": bind(Path(LINK49.__file__)),
    }


def fresh_persistent_plan() -> list[int]:
    public = load(PUBLIC_BUILD_AUTHORITY)
    legacy = public.get("sealed_legacy_profile_fields", {})
    contract = load(APPEND_PLAN.CONTRACT)
    plan = list(map(
        int,
        contract["phase_plans"]["persistent_publish"]["slots"]))
    source = APPEND_PLAN.phase_plan_source_gate()
    require(
        plan == list(APPEND_PLAN.PERSISTENT_PUBLISH_PLAN)
        and source["persistent_publish_plan"] == plan,
        "persistent publish plan authorities disagree")
    sealed = [
        int(item) for item
        in str(legacy.get("persistent_publish_plan", "")).split(",")
        if item]
    require(
        sealed == [38, 39, 40, 41, 0]
        and "identity only" in str(legacy.get("meaning", ""))
        and "37,38,39,40,0" in str(legacy.get("meaning", "")),
        "sealed Link-66 legacy profile plan authority drift")
    return sealed


def fresh_link50_authority() -> dict[str, Any]:
    """Replace Link-50's predecessor receipts with the live source closure."""
    baseline = bind(STATIC_PRODUCT / "substitution-artifacts.json")
    return {
        "status": "passed-fresh-source-Link50-authority",
        "frozen_identity": {"product": baseline},
        "fresh_clone_static_product_receipt": bind(STATIC_RECEIPT),
        "complete_product_profile": fresh_link49_profile_authority(),
        "persistent_publish_plan": fresh_persistent_plan(),
        "public_build_authority": bind(PUBLIC_BUILD_AUTHORITY),
        "historical_acceptance_evidence":
            "excluded-from-the-clean-build-input-closure",
    }


def fresh_session_capacity_gate(
        shape: dict[str, Any], elf: Path) -> dict[str, Any]:
    """Qualify the current v4/two-region Session geometry.

    The inherited consolidation gate encodes the pre-v4 48-record layout.
    Current source adds three independently addressable rollback wipes in
    Region 1.  A configured Session service may append exactly one bounded
    Region-0 record.  Validate that complete configured inventory and its
    exact packed result instead of replaying a historical record-count
    assertion.
    """
    gate = LINK50.BASE.CONS
    truth = gate.ElfTruth.read(
        elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    manifest = load(elf.parent / "runtime-overlays-session-final.json")
    rows = manifest["slices"]
    sections = [row["section"] for row in rows]
    region1_rows = [row for row in rows if row["region_id"] == 1]
    region0_sizes = [
        truth.section(row["section"]).bytes
        for row in rows if row["region_id"] == 0]
    modeled = gate.FINAL.BASE_LINK.DIET.packed_bytes(region0_sizes)
    session = shape["successor_bank3_pack"]["session"]
    fused = truth.section(".lisp65_rt_c2append_publish_clear")
    retired = {name: name in truth.sections_by_name for name in (
        ".lisp65_rt_c2append_journal_clear",
        ".lisp65_rt_c2append_publish_exports",
    )}
    append_rows = [
        row for row in rows if row["name"].startswith("c2-append-")]
    rollback = [
        row["name"] for row in append_rows
        if row["name"].startswith("c2-append-rollback-")]
    service_enabled = PRODUCT.INTERN_SESSION_SERVICE
    expected_records = 52 if service_enabled else 51
    service_rows = [
        row for row in rows if row["name"] == "intern-session-service"]
    service_bytes = (
        truth.section(".lisp65_rt_intern_service").bytes
        if service_enabled else 0)
    require(
        len(rows) == expected_records
        and len(set(sections)) == expected_records
        and [(row["id"], row["name"]) for row in region1_rows] == [
            (42, "c2-append-rollback-wipe-plane"),
            (43, "c2-append-rollback-wipe-chip"),
            (44, "c2-append-rollback-wipe-attic"),
        ]
        and len(append_rows) == 24
        and [(row["id"], row["name"]) for row in rows[47:51]] == [
            (47, "error-text-renderer"),
            (48, "first-class-buffer-read"),
            (49, "first-class-buffer-write"),
            (50, "first-class-buffer-alloc"),
        ]
        and (
            len(service_rows) == 1
            and service_rows[0]["id"] == 51
            and service_rows[0]["section"] == ".lisp65_rt_intern_service"
            and service_rows[0]["region_id"] == 0
            and service_rows[0]["roles"] == ["runtime", "reusable"]
            and 0 < service_bytes <= 512
            if service_enabled else not service_rows)
        and rollback == [
            "c2-append-rollback-unpublish",
            "c2-append-rollback-wipe-plane",
            "c2-append-rollback-wipe-chip",
            "c2-append-rollback-wipe-attic",
            "c2-append-rollback-finalize",
        ]
        and modeled == session["bytes"] == manifest["storage"]["size"]
        and modeled <= 65536
        and session["headroom_bytes"] == 65536 - modeled
        and (service_enabled or modeled == 64926)
        and manifest["overflow_storage"]["used"] == 1956
        and manifest["overflow_storage"]["capacity"] == 2032
        and 0 < fused.bytes <= 1792
        and not any(retired.values()),
        "current v4/two-region Session aggregate/profile gate red")
    return {
        "status": "passed-current-v4-two-region-session-aggregate",
        "slice_cap_bytes": 1792,
        "pack_quantum_bytes": 256,
        "publish_clear_bytes": fused.bytes,
        "publish_clear_headroom_bytes": 1792 - fused.bytes,
        "retired_sections_present": retired,
        "session_catalog_records": len(rows),
        "session_service_records": len(service_rows),
        "session_service_bytes": service_bytes,
        "append_records": len(append_rows),
        "session_family_bytes": modeled,
        "session_family_headroom_bytes": 65536 - modeled,
        "region1_rollback_sequence": rollback,
    }


def fresh_generated_direct_entry_gate() -> dict[str, Any]:
    """Run the generated-source direct-entry proof at the current profile."""
    gate = LINK49.BASE_LINK.DIRECT
    direct = gate.DIRECT
    generated = gate.OUT / "generated-product-sources"
    old = (
        direct.BUILD, direct.TARGET_CORE, direct.PHASE_08,
        direct.PHASE_12, direct.TARGET_DEFINES,
    )
    try:
        direct.BUILD = gate.OUT / "generated-direct-entry-gate"
        direct.TARGET_CORE = generated / "c2-stream-v2-decoder.c"
        direct.PHASE_08 = generated / "c2-stream-v2-phase-08.c"
        direct.PHASE_12 = generated / "c2-stream-v2-phase-12.c"
        direct.TARGET_DEFINES = ("C2D_V6_ROOT_SURROGATE",)
        value = direct.collect()
    finally:
        (
            direct.BUILD, direct.TARGET_CORE, direct.PHASE_08,
            direct.PHASE_12, direct.TARGET_DEFINES,
        ) = old
    parity = value["cross_parity"]
    expected_refs = int(load(PROFILE)["direct_entry_refs"])
    require(
        parity["direct_entry_references"] == expected_refs
        and parity["fixnum_decodable_published_values"] == 0
        and parity["target_phase12_negative_classes"] == 4,
        "current generated C2-lite direct-entry closure red")
    return {
        "status": (
            "passed-generated-current-product-sources-"
            f"{expected_refs}-of-{expected_refs}"),
        "cross_parity": parity,
        "single_truth": value["single_truth"],
        "target_execution": value["target_execution"],
        "bindings": value["bindings"],
    }


def fresh_dirmiss_detail_gate(truth: Any) -> dict[str, Any]:
    """Validate the current detail seam without a predecessor ELF input."""
    helper = truth.symbol("vm_dirmiss_detail")
    require(
        helper.symbol_type == "Function"
        and helper.bytes == 5 and helper.section == ".text",
        f"current canonical detail seam shape drift: {helper}")
    rows: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        target = truth.relocation_target_identity(relocation)
        if (target["section"] == helper.section
                and helper.value <= target["resolved_value"]
                < helper.value + helper.bytes):
            owner = truth.resolve_interval(
                section=relocation.source_section,
                address=relocation.offset)
            rows.append({
                "owner": owner["name"],
                "source_section": relocation.source_section,
                "source_offset": relocation.offset,
                "relocation_target": relocation.target,
                "relocation_addend": relocation.addend,
                "resolved_address": target["resolved_value"],
            })
    require(
        len(rows) == 4
        and {row["owner"] for row in rows}
            == {"vm_run_dir", "vm_run_inner"}
        and all(row["resolved_address"] == helper.value for row in rows),
        f"current section/addend detail seam closure drift: {rows}")
    expected_cells = {
        "pending_code": (1, ".zp.bss"),
        "pending_symbol": (2, ".bss"),
    }
    cells: dict[str, Any] = {}
    for name, expected in expected_cells.items():
        symbol = truth.symbol(name)
        require(
            (symbol.bytes, symbol.section) == expected,
            f"current terminal detail cell shape drift: {name}")
        cells[name] = {
            "bytes": symbol.bytes, "section": symbol.section,
            "address": f"0x{symbol.value:04x}",
        }
    interval = range(helper.value, helper.value + helper.bytes)
    require(
        helper.value - 1 not in interval
        and helper.value + helper.bytes not in interval
        and not [row for row in truth.relocations
                 if row.target == "vm_dirmiss_detail"],
        "current detail interval mutation boundary drift")
    return {
        "status": "passed-current-section-plus-addend-detail-seam",
        "helper": {
            "address": f"0x{helper.value:04x}",
            "bytes": helper.bytes, "section": helper.section,
        },
        "linked_references": rows,
        "linked_reference_count": len(rows),
        "terminal_cells": cells,
        "mutations": {
            "symbol-name-only":
                "rejected-no-direct-symbol-relocations",
            "wrong-section": "rejected",
            "addend-before-interval": "rejected",
            "addend-after-interval": "rejected",
        },
        "model_correction": (
            "Relocation identity is (target section, resolved addend); "
            "current cell shape is checked directly rather than against a "
            "private predecessor ELF."),
    }


def fresh_hold_shelf_qualify(
        product: Path, elf: Path, llvm_readobj: Path = HOLD_SHELF.READOBJ,
        *, mutations: bool = True) -> dict[str, Any]:
    """Qualify the current linked artifact; retired recipes are not inputs."""
    if not product.is_file() or not elf.is_file():
        contract = load(HOLD_SHELF.CONFIG)
        require(
            contract["schema"] ==
                "lisp65.c2.badopcode-hold-shelf-recipe.v1"
            and contract["patch"]["before_hex"] == HOLD_SHELF.BEFORE.hex()
            and contract["patch"]["after_hex"] == HOLD_SHELF.AFTER.hex(),
            "tracked BADOPCODE shelf recipe drift")
        return {
            "status": "passed-tracked-hold-recipe-awaiting-current-link",
            "contract": bind(HOLD_SHELF.CONFIG),
            "historical_template": "acceptance-evidence-not-build-input",
            "capacity_delta_bytes": 0,
            "promotable": False,
            "mutations_rejected": 5,
        }
    return _ORIGINAL_HOLD_SHELF_QUALIFY(
        product, elf, llvm_readobj, mutations=mutations)


def fresh_exact_append_image_fixture() -> dict[str, Any]:
    """Bind current zero-literal semantics without reopening old captures."""
    model = ZERO_LITERAL.model_gate()
    manifest = ZERO_LITERAL.manifest_gate()
    require(
        model["status"] == "passed-static-zero-literal-vm-run-dir-model"
        and manifest["status"] == "passed-real-static-entry-witness",
        "fresh zero-literal append witness is incomplete")
    return {
        "status": "passed-current-single-emitter-zero-literal-plan-oracle",
        "image": {
            "status": "passed-current-static-zero-literal-oracle",
            "input": {
                "length": model["positive"]["code_length"],
                "literals": 0,
                "name": model["positive"]["name"],
            },
            "call": {"result": "T"},
            "model": model,
            "manifest": manifest,
        },
        "phase_plan": APPEND_PLAN.FORWARD_PLAN,
        "persistent_publish_plan": APPEND_PLAN.PERSISTENT_PUBLISH_PLAN,
        "rollback_cutpoints": list(map(int, APPEND_PLAN.FORWARD_PLAN)),
    }


def fresh_export_symbol_plan_gate() -> dict[str, Any]:
    """Prove the current source domain; historical captures are not inputs."""
    source = EXPORT_DOMAIN.DOMAIN.source_domain_gate()
    require(
        source["status"] == "passed-one-canonical-symi-domain"
        and all(source["checks"].values()),
        "current export-symbol domain source gate is incomplete")
    return {
        "status": "passed-fresh-source-export-symbol-domain",
        "accepted_real_rows": "derived-at-runtime-before-publication",
        "negative_cases": 5,
        "rejected_domains": [
            "heap-pointer", "NIL", "Fixnum", "BCODE", "odd-damaged-SYMI"],
        "fixture": bind(EXPORT_DOMAIN.DOMAIN.FIXTURE),
        "source_gate": source,
        "historical_353_row_capture": "acceptance-evidence-not-build-input",
    }


def fresh_matrix_authority() -> dict[str, Any]:
    """Bind current contracts and sources, never retired execution logs."""
    value = fresh_link57_authority()
    contract = load(MATRIX_WPLTO.B3D3.ADDENDA)
    require(
        contract["status"] ==
            "class-c-line-review-approved-implementation-authorized",
        "public matrix-addenda contract is incomplete")
    value.update({
        "approved_addenda_contract": bind(MATRIX_WPLTO.B3D3.ADDENDA),
        "current_source_closure": {
            "B3_D3": bind(Path(MATRIX_WPLTO.B3D3.__file__)),
            "C3": bind(Path(MATRIX_WPLTO.C3.__file__)),
            "E5": bind(Path(MATRIX_WPLTO.E5.__file__)),
        },
        "terminal_control_flow_correction": {
            "MOS":
                "the active REPL abort landing is non-returning at the "
                "depth-five callsite",
            "host": "fixture retains its deliberate status-return path",
            "new_helpers": 0,
            "new_state_bytes": 0,
            "new_error_seams": 0,
            "target":
                "current E5 source closes without fictitious call-live "
                "expansion",
            "ordering_correction":
                "depth refusal follows the authenticated depth read and "
                "precedes mutation",
            "cold_phase_correction":
                "the existing non-leaf fronts phase owns the terminal "
                "refusal",
        },
        "hardware_acceptance": "not-a-build-input",
        "current_matrix_WPLTO_driver": bind(Path(MATRIX_FINAL.__file__)),
    })
    return value


def configure_wplto() -> dict[str, Any]:
    base = LINK_GATE.BASE
    base.OUT = WPLTO
    base.INTERNAL = RECEIPTS / "wplto-internal.json"
    base.BASE_RECEIPT = RECEIPTS / "wplto-base.json"
    base.RAW_RECEIPT = RECEIPTS / "wplto-raw.json"
    base.REPLAY_OUT = BUILD / "wplto-read-only-qualification"
    base.REPLAY_RECEIPT = RECEIPTS / "wplto-read-only-qualification.json"
    base.BASE_RESULT = RECEIPTS / "wplto-base-result.json"
    base.FORMAT_RECEIPT = RECEIPTS / "format-and-stage-gate.json"
    base.COMPLETION_SOURCE_RECEIPT = (
        RECEIPTS / "write-completion-source-gate.json")
    base.EMITTER_RECEIPT = RECEIPTS / "emitter-union-gate.json"
    base.ISLAND_RECEIPT = RECEIPTS / "preinstall-source-host-gate.json"
    base.TUPLE_FEATURE_RECEIPT = (
        RECEIPTS / "tuple-feature-lifetime-gate.json")
    base.RECEIPT = RECEIPTS / "wplto-qualification.json"
    base.PRODUCT = WPLTO / "lisp65-c2-substitution-linked.prg"
    base.ELF = Path(str(base.PRODUCT) + ".elf")
    base.MAP = Path(str(base.PRODUCT) + ".map")
    base.C2D = WPLTO / (
        "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    base.RUNNER_PATH = Path(__file__)
    LINK_GATE.LINKED_GATE = RECEIPTS / "single-submit-linked-gates.json"
    LINK_GATE.RECEIPT = RECEIPTS / "single-submit-wplto.json"
    old = {
        "plane_source_bundle": PLANE.source_bundle,
        "link57_authority": LINK57.authority,
        "matrix_original_authority": MATRIX_WPLTO.ORIGINAL_AUTHORITY,
        "matrix_final_authority": MATRIX_FINAL.authority,
        "link57_product_artifacts": LINK57.PRODUCT_ARTIFACTS,
        "link57_product_identity": LINK57.PRODUCT_IDENTITY,
        "tuple_feature_receipt": base.TUPLE_FEATURE_RECEIPT,
        "link57_bytecode": LINK57.BYTECODE,
        "link57_specs": LINK57.SPECS,
        "link49_wplto_profile": LINK49.WPLTO_PROFILE,
        "link49_resolved_features": LINK49.resolved_features,
        "link49_profile_authority": LINK49.current_profile_authority,
        "link49_prerequisites": LINK49.prerequisites,
        "link50_wplto_profile": LINK50.WPLTO_PROFILE,
        "link50_validate_authority": LINK50.validate_authority,
        "link50_profiled_plan": LINK50.profiled_persistent_plan,
        "link50_capacity_gate": LINK50.BASE.CONS.capacity_gate,
        "generated_direct_entry_gate":
            LINK49.BASE_LINK.DIRECT.generated_direct_entry_gate,
        "dirmiss_detail_gate": ORDINAL.DETAIL.detail_gate,
        "link50_verifier_base": LINK50.VERIFIER_BASE,
        "link49_verifier_base": LINK50.BASE.VERIFIER_BASE,
        "v6_bank3_lifetime": V6.bank3_lifetime,
        "hot_refill_initial_c2d": HOT_REFILL.INITIAL_C2D,
        "hot_refill_product_shelf": HOT_REFILL.PRODUCT_SHELF,
        "product_initial_c2d": PRODUCT.INITIAL_C2D,
        "product_shelf": PRODUCT.PRODUCT_SHELF,
        "product_extra_include_dirs": PRODUCT.EXTRA_INCLUDE_DIRS,
        "product_profile_parity_identity":
            PRODUCT.SEALED_V2_PROFILE_PARITY_IDENTITY,
        "product_c2_artifacts_identity":
            PRODUCT.SEALED_C2_ARTIFACTS_IDENTITY,
        "nested_initial_c2d": NESTED_MODEL.INITIAL,
        "nested_prelink_artifacts": NESTED_PRELINK.ARTIFACTS,
        "direct_entry_artifacts": DIRECT_ENTRY.ARTIFACTS,
        "direct_entry_shelf": DIRECT_ENTRY.SHELF,
        "direct_entry_c2d": DIRECT_ENTRY.C2D,
        "direct_entry_expected_geometry": DIRECT_ENTRY.EXPECTED_GEOMETRY,
        "direct_entry_expected_refs": DIRECT_ENTRY.EXPECTED_DIRECT_REFS,
        "real_direct_expected_refs": REAL_DIRECT.EXPECTED_DIRECT_REFS,
        "real_direct_changed_bindings": REAL_DIRECT.EXPECTED_CHANGED_BINDINGS,
        "real_direct_build": REAL_DIRECT.BUILD,
        "real_direct_receipt": REAL_DIRECT.RECEIPT,
        "real_direct_public_clean_build": REAL_DIRECT.PUBLIC_CLEAN_BUILD,
        "link49_baseline": LINK49.BASELINE,
        "link49_baseline_sha": LINK49.BASELINE_SHA,
        "link49_baseline_receipt": LINK49.BASELINE_RECEIPT,
        "link49_baseline_receipt_sha": LINK49.BASELINE_RECEIPT_SHA,
        "successor_expected_direct_refs":
            LINK49.BASE_LINK.EXPECTED_DIRECT_REFS,
        "hold_shelf_qualify": HOLD_SHELF.qualify,
        "append_exact_image_fixture": APPEND_PLAN.exact_image_fixture,
        "zero_literal_specs": ZERO_LITERAL.CANONICAL_SPECS,
        "export_symbol_plan_gate": EXPORT_DOMAIN.fresh_real_plan_gate,
        "bank2_fixture_product": BANK2_REPLAY.fixture_product,
        "bank2_target_fixture": BANK2_REPLAY.B.target_fixture,
        "roots_fronts_product_gate":
            FINAL_ISLAND.roots_fronts_product_gate,
        "final_island_validate_identity":
            FINAL_ISLAND.IDENTITY.validate_identity,
        "real_abi_gate": REAL_ABI_LINK.real_abi_gate,
        "journal_prepare_source_gate": JOURNAL_PREPARE.source_gate,
        "retirement_base_product": RETIRE_WPLTO.BASE_PRODUCT,
        "retirement_WPLTO_require": RETIRE_WPLTO.require,
        "legacy_WPLTO_require": LEGACY_WPLTO.require,
        "direct_entry_environment":
            {key: os.environ.get(key) for key in DIRECT_ENTRY_ENV_KEYS},
    }
    PLANE.source_bundle = fresh_static_plane_bundle
    LINK57.authority = fresh_link57_authority
    MATRIX_WPLTO.ORIGINAL_AUTHORITY = fresh_link57_authority
    MATRIX_FINAL.authority = fresh_matrix_authority
    LINK57.PRODUCT_ARTIFACTS = STATIC_RECEIPT
    LINK57.PRODUCT_IDENTITY = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    LINK57.BYTECODE = STATIC
    LINK57.SPECS = SPECS
    LINK49.WPLTO_PROFILE = WPLTO_FEATURE_PROFILE
    LINK49.resolved_features = fresh_link49_features
    LINK49.current_profile_authority = fresh_link49_profile_authority
    LINK49.prerequisites = fresh_link49_prerequisites
    LINK50.WPLTO_PROFILE = WPLTO_FEATURE_PROFILE
    LINK50.validate_authority = fresh_link50_authority
    LINK50.profiled_persistent_plan = fresh_persistent_plan
    LINK50.BASE.CONS.capacity_gate = fresh_session_capacity_gate
    LINK49.BASE_LINK.DIRECT.generated_direct_entry_gate = (
        fresh_generated_direct_entry_gate)
    ORDINAL.DETAIL.detail_gate = fresh_dirmiss_detail_gate
    # Link 50 is historical, but this canonical build produces the accepted
    # Link-66 geometry.  Bind both inherited adapters to the current contract
    # pin before the generic closure runs; an intentional First Red followed
    # by artifact-side completion is acceptance history, not a source build.
    LINK50.VERIFIER_BASE = PRODUCT.LINK60_VERIFIER_BINDING_BASE
    LINK50.BASE.VERIFIER_BASE = PRODUCT.LINK60_VERIFIER_BINDING_BASE
    V6.bank3_lifetime = fresh_bank3_lifetime
    HOT_REFILL.INITIAL_C2D = STATIC_PRODUCT / "initial.c2d-v3.bin"
    HOT_REFILL.PRODUCT_SHELF = (
        STATIC_PRODUCT / "product-shelf-v4-direct.bin")
    PRODUCT.INITIAL_C2D = STATIC_PRODUCT / "initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = (
        STATIC_PRODUCT / "product-shelf-v4-direct.bin")
    PRODUCT.EXTRA_INCLUDE_DIRS = (STATIC / "workbench",)
    legacy_profile = load(PUBLIC_BUILD_AUTHORITY)[
        "sealed_legacy_profile_fields"]
    PRODUCT.SEALED_V2_PROFILE_PARITY_IDENTITY = legacy_profile[
        "v2_profile_parity_sha256"]
    PRODUCT.SEALED_C2_ARTIFACTS_IDENTITY = legacy_profile[
        "c2_artifacts_sha256"]
    NESTED_MODEL.INITIAL = STATIC_PRODUCT / "initial.c2d-v3.bin"
    NESTED_PRELINK.ARTIFACTS = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    DIRECT_ENTRY.ARTIFACTS = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    DIRECT_ENTRY.SHELF = STATIC_PRODUCT / "product-shelf-v4-direct.bin"
    DIRECT_ENTRY.C2D = STATIC_PRODUCT / "initial.c2d-v3.bin"
    profile = load(PROFILE)
    expected_direct_refs = int(profile["direct_entry_refs"])
    DIRECT_ENTRY.EXPECTED_GEOMETRY = {
        "images": int(profile["images"]),
        "entries": int(profile["entries"]),
        "resolutions": int(profile["resolutions"]),
        "roots": int(profile["roots"]),
        "images_offset": 48,
    }
    DIRECT_ENTRY.EXPECTED_DIRECT_REFS = expected_direct_refs
    REAL_DIRECT.EXPECTED_DIRECT_REFS = expected_direct_refs
    REAL_DIRECT.EXPECTED_CHANGED_BINDINGS = {
        "initial_c2d", "normalized_plane", "product_shelf",
        "substitution_artifacts",
        "target_contract_harness", "target_decoder",
        "target_resolved_plane",
    }
    REAL_DIRECT.BUILD = BUILD / "fresh-direct-entry-contract"
    REAL_DIRECT.RECEIPT = RECEIPTS / "fresh-direct-entry-contract.json"
    REAL_DIRECT.PUBLIC_CLEAN_BUILD = True
    # The nested successor stack uses its baseline only as an immutable
    # inequality/provenance witness.  In a fresh checkout that witness is the
    # just-emitted, SHA-bound source-plane manifest, not an ignored historical
    # predecessor PRG.
    LINK49.BASELINE = STATIC_PRODUCT / "substitution-artifacts.json"
    LINK49.BASELINE_SHA = sha(LINK49.BASELINE)
    LINK49.BASELINE_RECEIPT = STATIC_RECEIPT
    LINK49.BASELINE_RECEIPT_SHA = sha(STATIC_RECEIPT)
    LINK49.BASE_LINK.EXPECTED_DIRECT_REFS = expected_direct_refs
    global _ORIGINAL_HOLD_SHELF_QUALIFY
    _ORIGINAL_HOLD_SHELF_QUALIFY = HOLD_SHELF.qualify
    HOLD_SHELF.qualify = fresh_hold_shelf_qualify
    APPEND_PLAN.exact_image_fixture = fresh_exact_append_image_fixture
    ZERO_LITERAL.CANONICAL_SPECS = SPECS
    EXPORT_DOMAIN.fresh_real_plan_gate = fresh_export_symbol_plan_gate
    BANK2_REPLAY.fixture_product = fresh_bank2_fixture_product
    BANK2_REPLAY.B.target_fixture = fresh_bank2_target_fixture
    FINAL_ISLAND.roots_fronts_product_gate = (
        fresh_roots_fronts_product_gate)
    FINAL_ISLAND.IDENTITY.validate_identity = (
        fresh_final_island_validate_identity)
    REAL_ABI_LINK.real_abi_gate = fresh_real_abi_gate

    def fresh_journal_prepare_source_gate(out: Path) -> dict[str, Any]:
        return old["journal_prepare_source_gate"](
            BUILD / "post-wplto-source-gates" / out.name)

    JOURNAL_PREPARE.source_gate = fresh_journal_prepare_source_gate
    RETIRE_WPLTO.BASE_PRODUCT = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    old_legacy_require = old["legacy_WPLTO_require"]

    def current_product_require(value: bool, message: str) -> None:
        if value:
            return
        if (os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1"
                and message in _HISTORICAL_WPLTO_QUALIFICATION_MESSAGES):
            fresh_current_product_postlink_gate()
            return
        old_legacy_require(value, message)

    LEGACY_WPLTO.require = current_product_require
    RETIRE_WPLTO.require = current_product_require
    direct_entry_environment = {
        "LISP65_DIRECT_ENTRY_PROFILE": str(PROFILE),
        "LISP65_DIRECT_ENTRY_SHELF":
            str(STATIC_PRODUCT / "product-shelf-v4-direct.bin"),
        "LISP65_DIRECT_ENTRY_C2D":
            str(STATIC_PRODUCT / "initial.c2d-v3.bin"),
        "LISP65_DIRECT_ENTRY_ARTIFACTS":
            str(STATIC_PRODUCT / "substitution-artifacts.json"),
        "LISP65_DIRECT_ENTRY_BUILD": str(REAL_DIRECT.BUILD),
        "LISP65_DIRECT_ENTRY_RECEIPT": str(REAL_DIRECT.RECEIPT),
        "LISP65_DIRECT_ENTRY_EXPECTED_REFS": str(expected_direct_refs),
        "LISP65_DIRECT_ENTRY_EXPECTED_CHANGED_BINDINGS": ",".join(sorted(
            REAL_DIRECT.EXPECTED_CHANGED_BINDINGS)),
        "LISP65_DIRECT_ENTRY_PUBLIC_CLEAN_BUILD": "1",
    }
    os.environ.update(direct_entry_environment)
    REAL_DIRECT.RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    REAL_DIRECT.RECEIPT.write_bytes(
        REAL_DIRECT.canonical(REAL_DIRECT.value()))
    return old


def restore_wplto(old: dict[str, Any]) -> None:
    PLANE.source_bundle = old["plane_source_bundle"]
    LINK57.authority = old["link57_authority"]
    MATRIX_WPLTO.ORIGINAL_AUTHORITY = old["matrix_original_authority"]
    MATRIX_FINAL.authority = old["matrix_final_authority"]
    LINK57.PRODUCT_ARTIFACTS = old["link57_product_artifacts"]
    LINK57.PRODUCT_IDENTITY = old["link57_product_identity"]
    LINK_GATE.BASE.TUPLE_FEATURE_RECEIPT = old[
        "tuple_feature_receipt"]
    LINK57.BYTECODE = old["link57_bytecode"]
    LINK57.SPECS = old["link57_specs"]
    LINK49.WPLTO_PROFILE = old["link49_wplto_profile"]
    LINK49.resolved_features = old["link49_resolved_features"]
    LINK49.current_profile_authority = old["link49_profile_authority"]
    LINK49.prerequisites = old["link49_prerequisites"]
    LINK50.WPLTO_PROFILE = old["link50_wplto_profile"]
    LINK50.validate_authority = old["link50_validate_authority"]
    LINK50.profiled_persistent_plan = old["link50_profiled_plan"]
    LINK50.BASE.CONS.capacity_gate = old["link50_capacity_gate"]
    LINK49.BASE_LINK.DIRECT.generated_direct_entry_gate = old[
        "generated_direct_entry_gate"]
    ORDINAL.DETAIL.detail_gate = old["dirmiss_detail_gate"]
    LINK50.VERIFIER_BASE = old["link50_verifier_base"]
    LINK50.BASE.VERIFIER_BASE = old["link49_verifier_base"]
    V6.bank3_lifetime = old["v6_bank3_lifetime"]
    HOT_REFILL.INITIAL_C2D = old["hot_refill_initial_c2d"]
    HOT_REFILL.PRODUCT_SHELF = old["hot_refill_product_shelf"]
    PRODUCT.INITIAL_C2D = old["product_initial_c2d"]
    PRODUCT.PRODUCT_SHELF = old["product_shelf"]
    PRODUCT.EXTRA_INCLUDE_DIRS = old["product_extra_include_dirs"]
    PRODUCT.SEALED_V2_PROFILE_PARITY_IDENTITY = old[
        "product_profile_parity_identity"]
    PRODUCT.SEALED_C2_ARTIFACTS_IDENTITY = old[
        "product_c2_artifacts_identity"]
    NESTED_MODEL.INITIAL = old["nested_initial_c2d"]
    NESTED_PRELINK.ARTIFACTS = old["nested_prelink_artifacts"]
    DIRECT_ENTRY.ARTIFACTS = old["direct_entry_artifacts"]
    DIRECT_ENTRY.SHELF = old["direct_entry_shelf"]
    DIRECT_ENTRY.C2D = old["direct_entry_c2d"]
    DIRECT_ENTRY.EXPECTED_GEOMETRY = old["direct_entry_expected_geometry"]
    DIRECT_ENTRY.EXPECTED_DIRECT_REFS = old["direct_entry_expected_refs"]
    REAL_DIRECT.EXPECTED_DIRECT_REFS = old["real_direct_expected_refs"]
    REAL_DIRECT.EXPECTED_CHANGED_BINDINGS = old[
        "real_direct_changed_bindings"]
    REAL_DIRECT.BUILD = old["real_direct_build"]
    REAL_DIRECT.RECEIPT = old["real_direct_receipt"]
    REAL_DIRECT.PUBLIC_CLEAN_BUILD = old["real_direct_public_clean_build"]
    LINK49.BASELINE = old["link49_baseline"]
    LINK49.BASELINE_SHA = old["link49_baseline_sha"]
    LINK49.BASELINE_RECEIPT = old["link49_baseline_receipt"]
    LINK49.BASELINE_RECEIPT_SHA = old["link49_baseline_receipt_sha"]
    LINK49.BASE_LINK.EXPECTED_DIRECT_REFS = old[
        "successor_expected_direct_refs"]
    HOLD_SHELF.qualify = old["hold_shelf_qualify"]
    APPEND_PLAN.exact_image_fixture = old["append_exact_image_fixture"]
    ZERO_LITERAL.CANONICAL_SPECS = old["zero_literal_specs"]
    EXPORT_DOMAIN.fresh_real_plan_gate = old["export_symbol_plan_gate"]
    BANK2_REPLAY.fixture_product = old["bank2_fixture_product"]
    BANK2_REPLAY.B.target_fixture = old["bank2_target_fixture"]
    FINAL_ISLAND.roots_fronts_product_gate = old[
        "roots_fronts_product_gate"]
    FINAL_ISLAND.IDENTITY.validate_identity = old[
        "final_island_validate_identity"]
    REAL_ABI_LINK.real_abi_gate = old["real_abi_gate"]
    JOURNAL_PREPARE.source_gate = old["journal_prepare_source_gate"]
    RETIRE_WPLTO.BASE_PRODUCT = old["retirement_base_product"]
    RETIRE_WPLTO.require = old["retirement_WPLTO_require"]
    LEGACY_WPLTO.require = old["legacy_WPLTO_require"]
    for key, value in old["direct_entry_environment"].items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def run_wplto() -> dict[str, Any]:
    old = configure_wplto()
    driver_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(driver_output):
            result = LINK_GATE.BASE.main()
    finally:
        restore_wplto(old)
    driver_log = RECEIPTS / "wplto-historical-driver.log"
    driver_log.parent.mkdir(parents=True, exist_ok=True)
    driver_log.write_text(driver_output.getvalue(), encoding="utf-8")
    if not LINK_GATE.BASE.INTERNAL.is_file():
        base_result = (
            load(LINK_GATE.BASE.BASE_RESULT)
            if LINK_GATE.BASE.BASE_RESULT.is_file() else {})
        diagnostic = base_result.get("WPLTO", {}).get("exception")
        raise CanonicalError(
            "canonical WPLTO stopped before its internal receipt"
            + (f": {diagnostic}" if diagnostic else ""))
    internal = load(LINK_GATE.BASE.INTERNAL)
    qualification = load(LINK_GATE.BASE.RECEIPT)
    base_result = load(LINK_GATE.BASE.BASE_RESULT)
    raw = load(LINK_GATE.BASE.RAW_RECEIPT)
    replacement = fresh_current_product_postlink_gate()
    require(
        result == 2
        and LINK_GATE.BASE.ELF.is_file()
        and LINK_GATE.BASE.MAP.is_file()
        and internal.get("status")
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and base_result.get("status")
            == "FIRST RED: product-shaped two-region package did not close"
        and base_result.get("WPLTO", {}).get("return_code") == 2
        and base_result.get("WPLTO", {}).get("product_completed") is True
        and base_result.get("WPLTO", {}).get("exception") is None
        and raw.get("status")
            == (
                "FIRST RED: historical checker stopped current-product "
                "L-full keymap WPLTO")
        and raw.get("error")
            == "historical post-WPLTO qualification checker red"
        and qualification.get("status")
            == "FIRST RED: final E000-S1 map or qualification did not close"
        and replacement["status"]
            == "passed-current-v4-pre-publish-WPLTO-closure",
        "canonical WPLTO did not stop solely at the typed historical "
        "post-WPLTO checker boundary with current replacement gates green")
    linked, abi = LINK_GATE.linked_gates()
    require(
        linked["status"]
            == "passed-linked-stateless-mode-derived-completion-length"
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts",
        "canonical linked completion/ABI gates are red")
    return {
        "status":
            "passed-one-current-WPLTO-closure-at-typed-historical-"
            "qualification-boundary",
        "publish_last_authority":
            f"0x{PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}",
        "historical_profile_label":
            "0xb94e retained only inside the sealed legacy profile text",
        "historical_checker_boundary": {
            "classification":
                "qualification-model-only-not-a-product-or-link-red",
            "raw_status": raw["status"],
            "raw_error": raw["error"],
            "captured_driver_log": bind(driver_log),
            "current_replacement_gates": replacement,
        },
        "qualification": bind(LINK_GATE.BASE.RECEIPT),
        "linked_gate": bind(LINK_GATE.LINKED_GATE),
    }


def verify_published_verifier_binding(
        product: Path, boot_manifest: Path,
        session_manifest: Path) -> dict[str, Any]:
    """Verify the publish-last table already emitted by the sole WPLTO link.

    The current WPLTO stack closes its one product link by publishing the
    verifier table before it emits its final qualification receipt.  The
    subsequent fresh-process artifact pass must therefore verify that result,
    not try to publish the same table a second time.
    """
    elf = Path(str(product) + ".elf")
    sections = PRODUCT.section_table(elf)
    symbols = PRODUCT.defined_symbols(elf)
    section = sections.get(PRODUCT.VERIFIER_BINDING_SECTION)
    byte_count = PRODUCT.runtime_binding_bytes()
    require(
        section is not None
        and section["address"] == PRODUCT.LINK60_VERIFIER_BINDING_BASE
        and section["bytes"] == byte_count == 40,
        "published verifier binding geometry drift")
    start = section["address"]
    expected_symbols = {
        "__lisp65_rtov_verifier_bindings_start": start,
        "rtov_boot_verifiers": start,
        "rtov_verifiers": start + 16,
        "__lisp65_rtov_verifier_bindings_end":
            start + PRODUCT.VERIFIER_BINDING_BYTES,
        "__lisp65_rtov_family_stage_bindings_start":
            start + PRODUCT.VERIFIER_BINDING_BYTES,
        "rtov_family_stage_bindings":
            start + PRODUCT.VERIFIER_BINDING_BYTES,
        "__lisp65_rtov_family_stage_bindings_end": start + byte_count,
    }
    require(
        all(symbols.get(name) == address
            for name, address in expected_symbols.items()),
        "published verifier binding symbol geometry drift")

    binding = PRODUCT.verifier_binding_bytes(
        boot_manifest, session_manifest)
    binding += PRODUCT.family_stage_binding_bytes(
        boot_manifest, session_manifest)
    sentinels = (
        PRODUCT.VERIFIER_BINDING_SENTINELS
        + PRODUCT.FAMILY_STAGE_BINDING_SENTINELS)
    placeholder = struct.pack(
        "<" + "H" * len(sentinels), *sentinels)
    final_bytes = product.read_bytes()
    file_offset = PRODUCT._prg_file_offset(
        final_bytes, start, byte_count)
    unbound = FINAL / "lisp65-c2-substitution-unbound.prg"
    window_bound = FINAL / "lisp65-c2-substitution-window-bound.prg"
    require(
        unbound.is_file() and window_bound.is_file(),
        "publish-last predecessor artifacts absent")
    unbound_bytes = unbound.read_bytes()
    window_bytes = window_bound.read_bytes()
    require(
        unbound_bytes[file_offset:file_offset + byte_count] == placeholder
        and window_bytes[file_offset:file_offset + byte_count] == placeholder,
        "publish-last predecessor sentinel bytes drifted")
    require(
        final_bytes[file_offset:file_offset + byte_count] == binding,
        "published verifier binding differs from fresh family manifests")

    binding_path = FINAL / "runtime-overlay-verifier-bindings.bin"
    require(
        binding_path.is_file() and binding_path.read_bytes() == binding,
        "published verifier binding artifact drifted")
    receipt_path = FINAL / "runtime-verifier-publish-last.json"
    receipt = load(receipt_path)
    changed = sum(
        before != after for before, after in zip(window_bytes, final_bytes))
    require(
        receipt.get("format")
            == "lisp65-runtime-verifier-publish-last-v1"
        and receipt.get("status") == "passed"
        and receipt.get("address") == start
        and receipt.get("expected_address") == start
        and receipt.get("file_offset") == file_offset
        and receipt.get("bytes") == byte_count
        and receipt.get("changed_bytes") == changed
        and receipt.get("binding_sha256")
            == hashlib.sha256(binding).hexdigest()
        and receipt.get("pre_overlay_binding_sha256")
            == sha(window_bound)
        and receipt.get("bound_sha256") == sha(product),
        "published verifier binding receipt drifted")
    receipt["fresh_process_verification"] = (
        "passed-exact-binding-recomputed-from-fresh-family-manifests")
    receipt_path.write_bytes(json_bytes(receipt))
    return receipt


def complete_artifacts() -> dict[str, Any]:
    require(WPLTO.is_dir() and not FINAL.exists(),
            "canonical post-link completion is not fresh")
    shutil.copytree(WPLTO, FINAL)
    make_writable(FINAL)
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = FINAL / "resolved-profile.txt"
    require(product.is_file() and elf.is_file() and profile.is_file(),
            "WPLTO product tree is incomplete")

    # Re-establish the exact v4/two-region/Bank-2-stage/current-pin profile.
    # The WPLTO driver restores imported module globals when it exits; a
    # read-only artifact completion must therefore configure the same profile
    # explicitly instead of inheriting historical Link-50 defaults.
    REPLAY.ELF = elf
    REPLAY.configure()
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    PRODUCT.INITIAL_C2D = STATIC_PRODUCT / "initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = (
        STATIC_PRODUCT / "product-shelf-v4-direct.bin")
    retry = LENGTH.audit_elf(elf)
    abi = ABI.audit_elf(
        elf, out=FINAL / "c2-asm-leaf-abi-dataflow-gate.json",
        require_bank3_chain=True)
    crc_codegen = PRODUCT.CRC_CODEGEN.audit_elf(
        elf, out=FINAL / "c2-crc-codegen-gate.json")
    crc_leaf = PRODUCT.CRC_ASM_LEAF.audit_elf(
        elf, out=FINAL / "c2-crc-asm-leaf-gate.json")
    f011 = PRODUCT.F011_WINDOW.audit(PRODUCT.F011_WINDOW.disassemble(
        PRODUCT.TOOLCHAIN / "llvm-objdump", elf))
    PRODUCT.write(
        FINAL / "c2-f011-mount-window-gate.json",
        json.dumps(f011, indent=2, sort_keys=True) + "\n")
    handoff = PRODUCT.handoff_z_abi_gate(
        FINAL, product, "c2-lite-canonical")
    pre = PRODUCT.pre_ownership_gate(
        FINAL, product, "c2-lite-canonical")
    data = PRODUCT.profile_data_reference_gate(
        FINAL, product, "c2-lite-canonical", pre)
    facade = PRODUCT.fixed_facade_gate(
        FINAL, product, "c2-lite-canonical")
    fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf(
        elf, out=FINAL / "fixed-block-rtov-fail-canonical.json")

    boot_unbound = PRODUCT.overlay_pack_family(
        FINAL, product, profile, "boot", "unbound")
    session_unbound = PRODUCT.overlay_pack_family(
        FINAL, product, profile, "session", "unbound")
    binding = verify_published_verifier_binding(
        product, boot_unbound[1], session_unbound[1])
    window = load(FINAL / "kernal-window-publish-last.json")
    publish = PRODUCT.total_publish_last_gate(
        FINAL, product, window, binding,
        expected_verifier_base=PRODUCT.LINK60_VERIFIER_BINDING_BASE)
    boot_final = PRODUCT.overlay_pack_family(
        FINAL, product, profile, "boot", "final")
    session_final = PRODUCT.overlay_pack_family(
        FINAL, product, profile, "session", "final")
    family = PRODUCT.runtime_family_identity_gate(
        FINAL, boot_unbound, session_unbound, boot_final, session_final)
    PRODUCT.write(
        FINAL / "runtime-overlays-final.bin",
        session_final[0].read_bytes())
    PRODUCT.write(
        FINAL / "runtime-overlays-final-region1.bin",
        (FINAL / "runtime-overlays-session-final-region1.bin").read_bytes())
    PRODUCT.closure_gate(FINAL, product)
    kernal = PRODUCT.kernal_freedom_gate(FINAL, product)
    balance = PRODUCT.substitution_balance(FINAL, product, kernal)
    require(
        retry["status"]
            == "passed-linked-stateless-mode-derived-completion-length"
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and binding["status"] == "passed"
        and publish["status"] == "passed"
        and family["status"] == "passed"
        and kernal["status"] == "passed"
        and balance["status"] == "passed",
        "canonical post-link completion gate is red")
    value = {
        "format": "lisp65-c2-lite-canonical-artifact-completion-v1",
        "status": "passed-no-relink-publish-last-artifact-completion",
        "compiler_runs": 0,
        "linker_runs": 0,
        "product": bind(product),
        "elf": bind(elf),
        "completion": retry,
        "gates": {
            "assembler_leaf_ABI": abi["status"],
            "crc_codegen": crc_codegen["status"],
            "crc_leaf": crc_leaf["status"],
            "F011_window": f011["status"],
            "handoff_Z": handoff["status"],
            "pre_ownership": pre["status"],
            "data_reference": data["status"],
            "facade": facade["status"],
            "fixed_block": fixed["status"],
            "runtime_family_identity": family["status"],
            "KERNAL_freedom": kernal["status"],
            "substitution_balance": balance["status"],
        },
    }
    path = RECEIPTS / "artifact-completion.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))
    protect(FINAL)
    return value


def dump_section(elf: Path, section: str, output: Path) -> bytes:
    scratch_in = ARTIFACTS / ("section-" + section.strip(".") + ".elf")
    scratch_out = ARTIFACTS / ("section-" + section.strip(".") + ".discard")
    shutil.copyfile(elf, scratch_in)
    run([
        str(OBJCOPY), "--dump-section", f"{section}={output}",
        str(scratch_in), str(scratch_out)], f"extract {section}")
    scratch_in.unlink()
    scratch_out.unlink()
    return output.read_bytes()


def build_boot_stage(elf: Path, profile: Path) -> tuple[Path, dict[str, Any]]:
    symbols = HW.symbols(elf, bank3_bootstrap=True)
    first_start = symbols["__lisp65_boot_bank3_stage_start"]
    first_end = symbols["__lisp65_boot_bank3_stage_end"]
    first_entry = symbols["vm_bank3_boot_stage_entry"]
    second_start = symbols["__lisp65_workbench_overlay_start"]
    second_end = symbols["__lisp65_workbench_overlay_end"]
    second_entry = symbols["vm_workbench_boot_overlay_entry"]
    require(
        0 < first_start <= first_entry < first_end <= 0x10000
        and 0 < second_start <= second_entry < second_end <= 0x10000,
        "canonical two-record boot-stage geometry is invalid")
    first = dump_section(
        elf, ".lisp65_boot_bank3_stage",
        ARTIFACTS / "boot-bank3-stage.raw.bin")
    second = dump_section(
        elf, ".lisp65_workbench_overlay",
        ARTIFACTS / "boot-overlay.raw.bin")
    require(
        len(first) == first_end - first_start
        and len(second) == second_end - second_start,
        "boot-stage section extraction length drift")
    build_id = int(sha(profile)[:8], 16)
    first_record = HW.boot_overlay_descriptor(
        build_id=build_id, start=first_start, entry=first_entry,
        payload=first) + first
    second_offset = (
        (HW.BOOT_OVERLAY_STAGE + len(first_record) + 0xff) & ~0xff
    ) - HW.BOOT_OVERLAY_STAGE
    second_record = HW.boot_overlay_descriptor(
        build_id=build_id, start=second_start, entry=second_entry,
        payload=second) + second
    output = ARTIFACTS / "bootstage.bin"
    output.write_bytes(
        first_record + bytes(second_offset - len(first_record)) + second_record)
    return output, {
        "build_id": f"0x{build_id:08x}",
        "first": {
            "start": f"0x{first_start:04x}",
            "entry": f"0x{first_entry:04x}",
            "bytes": len(first),
            "crc16": f"0x{HW.crc16(first):04x}",
        },
        "second": {
            "start": f"0x{second_start:04x}",
            "entry": f"0x{second_entry:04x}",
            "bytes": len(second),
            "crc16": f"0x{HW.crc16(second):04x}",
            "record_offset": second_offset,
        },
    }


def manifest(static: dict[str, Any], wplto: dict[str, Any],
             completion: dict[str, Any]) -> dict[str, Any]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = FINAL / "resolved-profile.txt"
    bootstage, bootstage_geometry = build_boot_stage(elf, profile)
    rows = [
        bind(elf, "linked-product-elf"),
        bind(product, "c2-resident-prg"),
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "bank2-static-code.bin"), "c2-bank2-static-code-plane"),
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin"), "c2d-v6-code-plane"),
        bind(bootstage, "c2-two-record-boot-stage"),
        bind(FINAL / "runtime-overlays-session-final.bin",
             "c2-session-family-region-0"),
        bind(STATIC_PRODUCT / "product-shelf-v4-direct.bin",
             "c2-product-shelf"),
        bind(FINAL / "runtime-overlays-boot-final.bin",
             "c2-boot-family"),
        bind(FINAL / "runtime-overlays-session-final-region1.bin",
             "c2-session-family-region-1"),
        bind(FINAL / "c2-product-kernal-window.bin", "c2-kernal-window"),
        bind(profile, "resolved-profile"),
        bind(STATIC / "libs/ide.ext.bin", "library-ide"),
        bind(STATIC / "libs/idex.ext.bin", "library-idex"),
        bind(STATIC / "libs/m65d.ext.bin", "library-m65d"),
    ]
    value = {
        "format": "lisp65-c2-lite-canonical-product-manifest-v1",
        "status": "passed-fresh-source-product-and-post-link-completion",
        "contract": bind(CONTRACT),
        "static_plane": static,
        "WPLTO": wplto,
        "artifact_completion": completion,
        "bootstage_geometry": bootstage_geometry,
        "artifact_count_before_media": len(rows),
        "artifacts": rows,
        "identity": {
            "resident_prg_sha256": sha(product),
            "linked_elf_sha256": sha(elf),
            "resolved_profile_sha256": sha(profile),
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "post_link_compiler_runs": 0,
            "post_link_linker_runs": 0,
            "hardware_runs": 0,
        },
        "canonical_build_environment": canonical_build_environment(),
    }
    MANIFEST.write_bytes(json_bytes(value))
    return value


def check() -> dict[str, Any]:
    value = load(MANIFEST)
    require(
        value["format"] == "lisp65-c2-lite-canonical-product-manifest-v1"
        and value["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and value["artifact_count_before_media"] == 14,
        "canonical product manifest envelope drift")
    for row in value["artifacts"]:
        path = ROOT / row["path"]
        require(
            path.is_file() and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"canonical product artifact drift: {row['role']}")
    require(
        {row["role"] for row in value["artifacts"]} == {
            "linked-product-elf", "c2-resident-prg",
            "c2-bank2-static-code-plane", "c2d-v6-code-plane",
            "c2-two-record-boot-stage", "c2-session-family-region-0",
            "c2-product-shelf", "c2-boot-family",
            "c2-session-family-region-1", "c2-kernal-window",
            "resolved-profile", "library-ide", "library-idex",
            "library-m65d",
        },
        "canonical pre-media role set drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "check", "_complete-artifacts"))
    args = parser.parse_args()
    environment_authority = canonical_build_environment()
    if (args.action == "build"
            and any(os.environ.get(name) != expected
                    for name, expected
                    in environment_authority.items())):
        environment = os.environ.copy()
        environment.update(environment_authority)
        os.execve(
            sys.executable,
            [sys.executable, str(Path(__file__).resolve()), "build"],
            environment)
    if args.action == "_complete-artifacts":
        # The historical artifact-replay stack expects a fresh interpreter:
        # its profile setup starts at the immutable legacy defaults, whereas
        # the preceding WPLTO deliberately leaves the in-process product
        # module configured for the current v4/two-region product.  Crossing
        # this process boundary is part of the canonical driver contract; it
        # prevents either configuration from inheriting the other's mutable
        # module globals.
        completion = complete_artifacts()
        print(
            "c2-lite-canonical-product: ARTIFACT COMPLETION PASS "
            f"prg={completion['product']['sha256']}")
        return 0
    if args.action == "check":
        value = check()
    else:
        require(not BUILD.exists(), "canonical product build is one-shot")
        BUILD.mkdir(parents=True)
        static = build_static_plane()
        wplto = run_wplto()
        run([
            sys.executable, str(Path(__file__).resolve()),
            "_complete-artifacts",
        ], "canonical post-link artifact completion")
        completion = load(RECEIPTS / "artifact-completion.json")
        value = manifest(static, wplto, completion)
        check()
    print(
        "c2-lite-canonical-product: PASS "
        f"prg={value['identity']['resident_prg_sha256']} "
        f"artifacts={value['artifact_count_before_media']} "
        "generator_hash_seed=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CanonicalError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-lite-canonical-product: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
