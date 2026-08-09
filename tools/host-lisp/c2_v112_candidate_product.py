#!/usr/bin/env python3
"""Build/check the one-core v1.4 release candidate as Link 92."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_ship_input_wait_gate as INPUT  # noqa: E402
import c2_product_substitution_link as PRODUCT_LINK  # noqa: E402
import c2_v13_link88_candidate_product as LINK88  # noqa: E402
import c2_v112_product_compiler_tier as TIER  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


P = LINK88.PREV
CAN = P.CAN
RELEASE = "v1.4.0"
LINK = 92
BUILD = ROOT / "build/c2.3/v1.4.0-candidate-product-link92-r5"
PREFLIGHT = ROOT / "build/c2.3/v1.4.0-release/phase-c/profile-preflight-r6"
MANIFEST = BUILD / "canonical-product-manifest.json"
PROFILE_RECEIPT = PREFLIGHT / "profile-receipt.json"
DRIVER = Path(__file__).resolve()
FREIGHT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-release-freight-receipt.json"
)
EXPECTED_STATIC = 45794
EXPECTED_ENTRIES = 748
EXPECTED_RESOLUTIONS = 2913
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 674
# Filled from the linker-free profile preflight before the one WPLTO.
EXPECTED_PRODUCT_ID = "0x3b48650d"
EXPECTED_BANK2_SHA = "f6844434b528a24a5194aa919ed8a39cf7d7d29bc67ccfb3d8084d5d8a43751e"
BASE_BUILD_MANIFEST = P.build_manifest
PROMOTED_SUITE = ROOT / "build/post-promotion/v112/compiler-tier/suite.json"
PROMOTED_PREFIX = ROOT / "build/post-promotion/v112/compiler/lcc"
RELEASE_STDLIB_PREFIX = ROOT / "build/post-promotion/v112/stdlib/stdlib-p0"
RELEASE_STDLIB = RELEASE_STDLIB_PREFIX.with_suffix(".manifest.json")
RELEASE_STDLIB_OBSERVATIONS = (
    ROOT / "build/post-promotion/v112/stdlib/observations.json"
)
PUBLIC_COMPLETION_ACTION = "complete"
PUBLIC_ACTIONS = (
    "profile", "build", "check", PUBLIC_COMPLETION_ACTION, "replay",
    "selftest", "ownership-closure-seed",
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-fourth-card-completion-dispatch-first-red.json"
)
COMPLETION_REPLAY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-artifact-completion-replay-receipt.json"
)
AUTHORITY_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-completion-authority-reconstruction-first-red.json"
)
PERSISTED_REPLACEMENT_STATUS = "passed"
LIVE_REPLACEMENT_STATUS = "passed-current-v4-pre-publish-WPLTO-closure"
R5_ARTIFACT_IDENTITY = {
    "product": (
        "wplto/lisp65-c2-substitution-linked.prg", 41566,
        "fcc785365d2a6d7a3269367a4234cb372783d46b9debdee6ad37e758f6e20a52",
    ),
    "elf": (
        "wplto/lisp65-c2-substitution-linked.prg.elf", 622592,
        "e7cca3de31062c6872cdb35fde711a16af802cc2a7b1023bcfcdee34366766f8",
    ),
    "map": (
        "wplto/lisp65-c2-substitution-linked.prg.map", 179735,
        "69ec93fc58c1c27b935c4cf0d599e99901da2bbe4716dc743ad9f653937946a2",
    ),
    "resolved_profile": (
        "wplto/resolved-profile.txt", 12052,
        "95092a27a5c523e3a328be042604ab07114594fe1c6650505e8fa6f259c76bca",
    ),
}


class CandidateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CandidateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"candidate authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def parse_action(arguments: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=PUBLIC_ACTIONS)
    return str(parser.parse_args(arguments).action)


def r5_artifact_preflight() -> dict[str, dict[str, Any]]:
    first_red = load(FIRST_RED)
    require(
        first_red.get("status")
            == "FIRST RED-attributed-post-link-fresh-process-completion-dispatch-closure"
        and first_red["execution_accounting"]["fourth_card_attempts_consumed"] == 1
        and first_red["execution_accounting"]["fifth_card_authorized"] is False,
        "r5 completion replay lacks its owner-disposition input",
    )
    rows: dict[str, dict[str, Any]] = {}
    for name, (relative, byte_count, expected_sha) in R5_ARTIFACT_IDENTITY.items():
        path = BUILD / relative
        row = bind(path)
        require(
            row["bytes"] == byte_count and row["sha256"] == expected_sha,
            f"immutable r5 {name} identity drift before completion",
        )
        rows[name] = row
    return rows


def completion_dispatch_gate(
    source_override: str | None = None, *, exercise_unknown: bool = False,
) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    closer = functions.get("complete_in_fresh_process")
    binder = functions.get("bind_inherited_entrypoint")
    require(closer is not None and binder is not None,
            "public completion closer/binder absent")
    closer_text = ast.unparse(closer)
    assignments = {
        ast.unparse(child.targets[0]): ast.unparse(child.value)
        for child in binder.body if isinstance(child, ast.Assign)
    }
    require(
        "[sys.executable, str(DRIVER), PUBLIC_COMPLETION_ACTION]" in closer_text
        and "'_complete'" not in closer_text
        and '"_complete"' not in closer_text
        and assignments.get("P.PRODUCT.complete_in_fresh_process")
            == "complete_in_fresh_process"
        and PUBLIC_COMPLETION_ACTION in PUBLIC_ACTIONS
        and not PUBLIC_COMPLETION_ACTION.startswith("_"),
        "closer escaped the public driver action contract",
    )
    unknown_rejected = False
    if exercise_unknown:
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                parse_action(["not-a-driver-action"])
        except SystemExit as error:
            unknown_rejected = (
                error.code == 2 and "invalid choice" in stderr.getvalue()
            )
        require(unknown_rejected, "unknown driver action did not fail loudly")
    return {
        "status": "passed-public-completion-dispatch-contract",
        "public_completion_action": PUBLIC_COMPLETION_ACTION,
        "private_actions_spoken_by_closer": 0,
        "unknown_action_rejected": unknown_rejected if exercise_unknown else None,
    }


def completion_resume_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    replay = functions.get("replay_action")
    authority = functions.get("completed_wplto_authority")
    require(replay is not None and authority is not None,
            "completion resume/authority entrypoint absent")
    replay_calls = [
        ast.unparse(node.func) for node in ast.walk(replay)
        if isinstance(node, ast.Call)
    ]
    authority_text = ast.unparse(authority)
    require(
        "complete_in_fresh_process" not in replay_calls
        and "public_completion_action" not in replay_calls
        and "P.PRODUCT.complete_action" not in replay_calls
        and replay_calls.count("completed_artifact_preflight") == 2
        and "expected_replacement_status: str=PERSISTED_REPLACEMENT_STATUS"
            in authority_text
        and "replacement.get('status') == expected_replacement_status"
            in authority_text,
        "resume path can re-enter completion or reads the wrong status vocabulary",
    )
    return {
        "status": "passed-resume-only-after-existing-artifact-completion",
        "artifact_completion_calls": 0,
        "completed_artifact_identity_checks": 2,
        "persisted_replacement_status": PERSISTED_REPLACEMENT_STATUS,
    }


def configure(build: Path | None = None) -> dict[str, Path]:
    build = BUILD if build is None else build
    P.STDLIB = RELEASE_STDLIB
    P.RELEASE = RELEASE
    P.LINK = LINK
    P.BUILD = build
    P.MANIFEST = build / "canonical-product-manifest.json"
    P.DRIVER = DRIVER
    P.EXPECTED_STATIC = EXPECTED_STATIC
    P.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    P.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    P.EXPECTED_ROOTS = EXPECTED_ROOTS
    P.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    P.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    P.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    P.PRODUCT.RELEASE = RELEASE
    P.PRODUCT.LINK = LINK
    P.PRODUCT.BUILD = build
    P.PRODUCT.MANIFEST = build / "canonical-product-manifest.json"
    P.PRODUCT.DRIVER = DRIVER
    P.PRODUCT.V.EXPECTED_STATIC = EXPECTED_STATIC
    P.PRODUCT.V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    P.PRODUCT.V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    P.PRODUCT.V.EXPECTED_ROOTS = EXPECTED_ROOTS
    P.PRODUCT.V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    P.PRODUCT.V.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    P.PRODUCT.V.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    CAN.COMPILER_TIER = TIER
    paths = P.configure()
    CAN.COMPILER_TIER = TIER
    CAN.SUITES = (*CAN.SUITES[:-1], PROMOTED_SUITE)
    CAN.PREFIXES = (*CAN.PREFIXES[:-1], (PROMOTED_PREFIX, "disk-lib", "0x000000"))
    promoted_manifest = PROMOTED_PREFIX.with_suffix(".manifest.json")
    specs = tuple(
        (key, name, promoted_manifest if key == "lcc" else path)
        for key, name, path in CAN.SPECS
    )
    require(sum(key == "lcc" for key, _name, _path in specs) == 1,
            "candidate lacks a unique compiler role")
    CAN.SPECS = specs
    req = P.BASE.PROBE.REQ
    req.SPECS = specs
    req.F1W.SPECS = specs
    plane = req.F1W.PLANE
    plane.FRESH_MANIFESTS = tuple(path for _key, _name, path in specs)
    P.PRODUCT.build_manifest = build_manifest
    return paths


def emit_promoted_carrier() -> Path:
    suite = PROMOTED_SUITE
    TIER.generate(suite)
    prefix, role, base = PROMOTED_PREFIX, "disk-lib", "0x000000"
    require(role == "disk-lib" and base is not None, "compiler role geometry drift")
    checked = STD._read_suite(str(suite))
    STD.check_suite(str(suite), checked)
    STD.emit_artifacts(str(suite), checked, str(prefix), base_addr=0,
                       artifact_role="disk-lib")
    manifest = prefix.with_suffix(".manifest.json")
    require(load(manifest)["name"] == "c2-v112-product-compiler-tier",
            "live product carrier is not the promoted v1.4 tier")
    return manifest


def emit_release_stdlib() -> Path:
    manifest = INPUT.run_suite(
        INPUT.SUITE, RELEASE_STDLIB_PREFIX, RELEASE_STDLIB_OBSERVATIONS)
    names = {str(row.get("name")) for row in manifest.get("entries", [])}
    require(
        {"read-line", "wait", "q", "time"}.issubset(names)
        and "WORKBENCH 1.4.0" in RELEASE_STDLIB.read_text(encoding="utf-8"),
        "v1.4 release stdlib lacks its input/timing surface or regular banner",
    )
    return RELEASE_STDLIB


def direct_entry_census(product_dir: Path) -> int:
    c2d = (product_dir / "initial.c2d-v3.bin").read_bytes()
    shelf = (product_dir / "product-shelf-v4-direct.bin").read_bytes()
    require(c2d[:8] == b"C2D\0\x03\x30\x20\x0a",
            "profile direct-entry C2D identity drift")
    images = struct.unpack_from("<H", c2d, 12)[0]
    count = 0
    for slot in range(images):
        row = 48 + slot * 32
        resolutions = struct.unpack_from("<H", c2d, row + 12)[0]
        metadata = int.from_bytes(c2d[row + 23:row + 26], "little")
        require(metadata + 24 <= len(shelf),
                "profile direct-entry metadata range drift")
        literal_count = struct.unpack_from("<H", shelf, metadata + 12)[0]
        literal_offset = struct.unpack_from("<H", shelf, metadata + 16)[0]
        require(literal_count == resolutions,
                "profile direct-entry descriptor/C2D drift")
        for local in range(literal_count):
            descriptor = metadata + literal_offset + local * 8
            require(descriptor + 8 <= len(shelf),
                    "profile direct-entry descriptor range drift")
            count += shelf[descriptor] == 4
    return count


def profile() -> dict[str, Any]:
    require(not PREFLIGHT.exists(), "v1.4 profile preflight is one-shot")
    freight = load(FREIGHT)
    require(freight.get("status") == "passed-host-integrated-release-freight",
            "Phase-B freight is not host-green")
    PREFLIGHT.mkdir(parents=True)
    emitted_stdlib = emit_release_stdlib()
    paths = configure(PREFLIGHT)
    promoted = emit_promoted_carrier()
    # Rebind after emission so every consumer sees the exact promoted manifest.
    specs = tuple(CAN.SPECS)
    require(sum(key == "lcc" and path == promoted for key, _name, path in specs) == 1,
            "promoted compiler does not own the unique lcc role")
    old_sub = (CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS)
    old_v6 = (CAN.V6.OUT, CAN.V6.PRODUCT_IDENTITY,
              CAN.V6.STATIC_CODE_BYTES, CAN.V6.A.SPECS)
    try:
        CAN.SUBSTITUTION.BUILD = paths["static_product"]
        CAN.SUBSTITUTION.SPECS = specs
        product = CAN.SUBSTITUTION.build()
        direct_refs = direct_entry_census(paths["static_product"])
        static_bytes = sum(int(load(path)["code_bytes"])
                           for _key, _name, path in specs)
        CAN.V6.OUT = paths["v6"]
        CAN.V6.PRODUCT_IDENTITY = (
            paths["static_product"] / "substitution-artifacts.json")
        CAN.V6.STATIC_CODE_BYTES = static_bytes
        CAN.V6.A.SPECS = specs
        CAN.V6.OUT.mkdir(parents=True, exist_ok=True)
        semantics = CAN.V6.host_semantics()
    finally:
        CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS = old_sub
        (CAN.V6.OUT, CAN.V6.PRODUCT_IDENTITY,
         CAN.V6.STATIC_CODE_BYTES, CAN.V6.A.SPECS) = old_v6
    bank2 = paths["v6"] / "bank2-static-code.bin"
    bank2_sha = hashlib.sha256(bank2.read_bytes()).hexdigest()
    require(static_bytes == EXPECTED_STATIC
            and product["entries"] == EXPECTED_ENTRIES
            and product["resolutions"] == EXPECTED_RESOLUTIONS
            and product["roots"] == EXPECTED_ROOTS
            and direct_refs == EXPECTED_DIRECT_REFS
            and semantics["static_bank2"]["code_bytes"] == EXPECTED_STATIC,
            "v1.4 linker-free profile geometry drift")
    value = {
        "format": "lisp65-c2.3-v1.12-v1.4-profile-preflight-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-linker-free-one-core-profile",
        "product_links": 0,
        "wplto_runs": 0,
        "geometry": {
            "static_code_bytes": static_bytes,
            "entries": product["entries"],
            "resolutions": product["resolutions"],
            "roots": product["roots"],
            "direct_entry_refs": direct_refs,
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256": bank2_sha,
            "bank2_headroom_bytes": 65536 - static_bytes,
        },
        "authorities": {
            "freight": bind(FREIGHT),
            "promoted_compiler_manifest": bind(promoted),
            "release_stdlib_manifest": bind(emitted_stdlib),
            "static_product": bind(
                paths["static_product"] / "substitution-artifacts.json"),
            "bank2": bind(bank2),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Linker-free static profile only. No WPLTO, product core, media, "
            "device, link, Halt-1 or release claim."
        ),
    }
    PROFILE_RECEIPT.write_bytes(CAN.json_bytes(value))
    return value


def freight_gates() -> dict[str, Any]:
    freight = load(FREIGHT)
    require(freight.get("status") == "passed-host-integrated-release-freight"
            and freight.get("bank2", {}).get("resident_delta_bytes") == 0,
            "v1.4 release freight authority drift")
    summaries = {
        "banner": P.run(
            [sys.executable, "tools/host-lisp/c2_repl_banner_version_gate.py",
             "--selftest"], "v1.4 banner gate"),
        "release_freight": P.run(
            [sys.executable, "tools/host-lisp/c2_v112_release_freight.py", "check"],
            "v1.4 release freight gate"),
        "editor": P.run(
            [sys.executable, "tools/host-lisp/c2_v126_editor_allocation_gate.py",
             "check"], "v1.4 editor allocation gate"),
        "surface": P.run(
            [sys.executable, "tools/host-lisp/v11_surface_delivery_parity.py"],
            "v1.4 surface parity"),
    }
    return {"mode": "v1.4-release-freight", "summaries": summaries,
            "release_freight": bind(FREIGHT)}


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = BASE_BUILD_MANIFEST(wplto, completion)
    value["static_plane"].update({
        "status": "passed-v1.4-release-single-core-static-plane",
        "release_freight": bind(FREIGHT),
        "promoted_compiler": bind(
            PROMOTED_PREFIX.with_suffix(".manifest.json")),
        "conditional_defstruct_public": False,
    })
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = bind(DRIVER)
    P.PRODUCT.MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = load(path)
    value.update(freight)
    value["status"] = "passed-v1.4-release-feature-gates"
    path.write_bytes(CAN.json_bytes(value))


def startup_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    node = functions.get("product")
    binder = functions.get("bind_inherited_entrypoint")
    require(node is not None and binder is not None,
            "candidate product entrypoint/binder absent")
    calls = [
        child for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "configure"
    ]
    assignments = {
        ast.unparse(child.targets[0]): ast.unparse(child.value)
        for child in binder.body
        if isinstance(child, ast.Assign)
    }
    required = {
        "P.PRODUCT.RELEASE": "RELEASE",
        "P.PRODUCT.LINK": "LINK",
        "P.PRODUCT.BUILD": "BUILD",
        "P.PRODUCT.MANIFEST": "MANIFEST",
        "P.PRODUCT.DRIVER": "DRIVER",
        "P.PRODUCT.configure": "configure",
    }
    binder_calls = [ast.unparse(child) for child in ast.walk(binder)
                    if isinstance(child, ast.Call)]
    product_calls = [ast.unparse(child.func) for child in ast.walk(node)
                     if isinstance(child, ast.Call)]
    require(
        not calls
        and all(assignments.get(key) == value for key, value in required.items())
        and "os.environ.update(CAN.canonical_build_environment())" in binder_calls
        and product_calls.count("bind_inherited_entrypoint") == 1
        and product_calls.count("P.main") == 1,
        "candidate inherited entrypoint bootstrap is incomplete or preconfigured",
    )
    return {
        "status": "passed-single-configure-owned-by-product-entrypoint",
        "direct_preconfigure_calls": 0,
        "product_configure_bindings": 1,
        "canonical_environment_bindings": 1,
        "driver_rebindings": 1,
    }


def profile_source_gate(source_override: str | None = None) -> None:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    profile_node = functions.get("profile")
    require(profile_node is not None, "linker-free profile entrypoint absent")
    calls = [ast.unparse(child.func) for child in ast.walk(profile_node)
             if isinstance(child, ast.Call)]
    comparisons = [ast.unparse(child) for child in ast.walk(profile_node)
                   if isinstance(child, ast.Compare)]
    dictionary_rows = [
        (ast.literal_eval(key), ast.unparse(value))
        for child in ast.walk(profile_node) if isinstance(child, ast.Dict)
        for key, value in zip(child.keys, child.values)
        if key is not None and isinstance(key, ast.Constant)
        and isinstance(key.value, str)
    ]
    require(
        "direct_entry_census" in calls
        and "direct_refs == EXPECTED_DIRECT_REFS" in comparisons
        and ("direct_entry_refs", "direct_refs") in dictionary_rows,
        "linker-free profile omits its direct-entry census",
    )


def startup_selftest() -> dict[str, Any]:
    result = startup_gate()
    completion_dispatch = completion_dispatch_gate(exercise_unknown=True)
    completion_resume = completion_resume_gate()
    semantic = ZERO.semantic_witness_selftest()
    source_owner = PRODUCT_LINK.source_owner_scope_selftest()
    source = DRIVER.read_text(encoding="utf-8")
    profile_source_gate(source)
    before, anchor, after = source.rpartition(
        "    bind_inherited_entrypoint()\n")
    require(bool(anchor), "startup mutation anchor absent")
    mutated = before + "    configure(BUILD)\n" + after
    try:
        startup_gate(mutated)
    except CandidateError:
        rejected = True
    else:
        rejected = False
    require(rejected, "double-configure startup mutation survived")
    mutated = source.replace(
        "    os.environ.update(CAN.canonical_build_environment())\n",
        "",
        1,
    )
    require(mutated != source, "canonical-environment mutation anchor absent")
    try:
        startup_gate(mutated)
    except CandidateError:
        rejected_environment = True
    else:
        rejected_environment = False
    require(rejected_environment,
            "inherited-driver re-exec startup mutation survived")
    mutated = source.replace(
        "and direct_refs == EXPECTED_DIRECT_REFS",
        "and EXPECTED_DIRECT_REFS == EXPECTED_DIRECT_REFS",
        1,
    )
    require(mutated != source, "direct-entry mutation anchor absent")
    try:
        profile_source_gate(mutated)
    except CandidateError:
        rejected_direct = True
    else:
        rejected_direct = False
    require(rejected_direct, "missing direct-entry profile census survived")
    before, anchor, after = source.rpartition(
        "[sys.executable, str(DRIVER), PUBLIC_COMPLETION_ACTION]")
    require(bool(anchor), "private completion-action mutation anchor absent")
    mutated = before + '[sys.executable, str(DRIVER), "_complete"]' + after
    try:
        completion_dispatch_gate(mutated)
    except CandidateError:
        rejected_private_completion = True
    else:
        rejected_private_completion = False
    require(rejected_private_completion,
            "closer private-action mutation survived")
    try:
        completed_wplto_authority(LIVE_REPLACEMENT_STATUS)
    except CandidateError:
        rejected_live_status_projection = True
    else:
        rejected_live_status_projection = False
    require(rejected_live_status_projection,
            "live status vocabulary survived persisted authority reconstruction")
    mutated = source.replace(
        "    completed_before = completed_artifact_preflight()\n",
        "    complete_in_fresh_process()\n",
        1,
    )
    require(mutated != source, "resume completion-call mutation anchor absent")
    try:
        completion_resume_gate(mutated)
    except CandidateError:
        rejected_completion_reentry = True
    else:
        rejected_completion_reentry = False
    require(rejected_completion_reentry,
            "resume path completion re-entry mutation survived")
    result["semantic_witness_rebind"] = semantic
    result["source_owner_scope"] = source_owner
    result["completion_dispatch"] = completion_dispatch
    result["completion_resume"] = completion_resume
    result["mutations_rejected"] = (
        7 + semantic["mutations_rejected"]
        + source_owner["mutations_rejected"]
    )
    return result


def bind_inherited_entrypoint() -> None:
    os.environ.update(CAN.canonical_build_environment())
    P.PRODUCT.RELEASE = RELEASE
    P.PRODUCT.LINK = LINK
    P.PRODUCT.BUILD = BUILD
    P.PRODUCT.MANIFEST = MANIFEST
    P.PRODUCT.DRIVER = DRIVER
    P.PRODUCT.configure = configure
    P.PRODUCT.complete_in_fresh_process = complete_in_fresh_process


def complete_in_fresh_process() -> None:
    before = r5_artifact_preflight()
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), PUBLIC_COMPLETION_ACTION],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0,
        "v1.4 public fresh-process artifact completion red:\n" + result.stdout,
    )
    require(
        r5_artifact_preflight() == before,
        "r5 WPLTO artifacts changed across artifact completion",
    )
    paths = P.PRODUCT.BASE.paths(BUILD)
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def public_completion_action() -> int:
    before = r5_artifact_preflight()
    bind_inherited_entrypoint()
    result = P.PRODUCT.complete_action()
    require(
        result == 0 and r5_artifact_preflight() == before,
        "public completion action changed immutable r5 WPLTO artifacts",
    )
    return result


def completed_artifact_preflight() -> dict[str, dict[str, Any]]:
    first_red = load(AUTHORITY_FIRST_RED)
    require(
        first_red.get("status")
            == "FIRST RED-attributed-post-completion-WPLTO-authority-projection-mismatch"
        and first_red.get("disposition", {}).get("state")
            == "owner-disposition-required"
        and first_red.get("completion_authority", {}).get(
            "final_tree_is_one_shot") is True,
        "resume path lacks its completed-artifact First-Red authority",
    )
    paths = P.PRODUCT.BASE.paths(BUILD)
    completion_path = paths["receipts"] / "artifact-completion.json"
    completion_log = paths["receipts"] / "artifact-completion.log"
    completion = load(completion_path)
    require(
        completion.get("status")
            == "passed-no-relink-publish-last-artifact-completion"
        and completion.get("compiler_runs") == 0
        and completion.get("linker_runs") == 0
        and bind(completion_path)
            == first_red["completion_authority"]["receipt"]
        and bind(completion_log)
            == first_red["completion_authority"]["log"],
        "existing artifact completion authority drift",
    )
    final_paths = {
        "product": BUILD / "final/lisp65-c2-substitution-linked.prg",
        "elf": BUILD / "final/lisp65-c2-substitution-linked.prg.elf",
        "map": BUILD / "final/lisp65-c2-substitution-linked.prg.map",
        "resolved_profile": BUILD / "final/resolved-profile.txt",
    }
    rows = {name: bind(path) for name, path in final_paths.items()}
    expected = first_red["immutable_identity"]["wplto"]
    require(
        all(
            rows[name]["bytes"] == expected[name]["bytes"]
            and rows[name]["sha256"] == expected[name]["sha256"]
            for name in rows
        )
        and completion.get("product") == rows["product"],
        "completed final artifacts differ from immutable r5 WPLTO identity",
    )
    return rows


def completed_wplto_authority(
    expected_replacement_status: str = PERSISTED_REPLACEMENT_STATUS,
) -> dict[str, Any]:
    paths = P.PRODUCT.BASE.paths(BUILD)
    internal = load(paths["receipts"] / "wplto-internal.json")
    base = load(paths["receipts"] / "wplto-base-result.json")
    raw = load(paths["receipts"] / "wplto-raw.json")
    qualification = paths["receipts"] / "wplto-qualification.json"
    driver_log = paths["receipts"] / "wplto-historical-driver.log"
    linked_gate = paths["receipts"] / "single-submit-linked-gates.json"
    replacement = internal.get("fresh_replacement_gates")
    require(
        internal.get("status")
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal.get("execution_accounting", {}).get(
            "product_closure_links") == 1
        and base.get("WPLTO", {}).get("product_completed") is True
        and base.get("WPLTO", {}).get("exception") is None
        and raw.get("error")
            == "historical post-WPLTO qualification checker red"
        and isinstance(replacement, dict)
        and replacement.get("status") == expected_replacement_status
        and qualification.is_file() and driver_log.is_file()
        and linked_gate.is_file(),
        "completed r5 WPLTO authority is incomplete",
    )
    return {
        "status": (
            "passed-one-current-WPLTO-closure-at-typed-historical-"
            "qualification-boundary"
        ),
        "publish_last_authority": (
            f"0x{CAN.PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}"
        ),
        "historical_profile_label": (
            "0xb94e retained only inside the sealed legacy profile text"
        ),
        "historical_checker_boundary": {
            "classification": "qualification-model-only-not-a-product-or-link-red",
            "raw_status": raw["status"],
            "raw_error": raw["error"],
            "captured_driver_log": bind(driver_log),
            "current_replacement_gates": replacement,
        },
        "qualification": bind(qualification),
        "linked_gate": bind(linked_gate),
    }


def replay_action() -> int:
    require(not MANIFEST.exists(), "r5 completion replay is one-shot")
    wplto_before = r5_artifact_preflight()
    completed_before = completed_artifact_preflight()
    dispatch = completion_dispatch_gate(exercise_unknown=True)
    resume = completion_resume_gate()
    authority = completed_wplto_authority()
    paths = configure()
    completion_path = paths["receipts"] / "artifact-completion.json"
    completion = load(completion_path)
    require(
        completion.get("status")
            == "passed-no-relink-publish-last-artifact-completion"
        and completion.get("compiler_runs") == completion.get("linker_runs") == 0
        and completion.get("product") == bind(
            BUILD / "final/lisp65-c2-substitution-linked.prg"),
        "r5 artifact-completion receipt did not close without compilation/link",
    )
    value = build_manifest(authority, completion)
    checked = CAN.check()
    wplto_after = r5_artifact_preflight()
    completed_after = completed_artifact_preflight()
    require(
        checked["identity"] == value["identity"]
        and value["identity"]["resident_prg_sha256"]
            == wplto_before["product"]["sha256"]
        and wplto_after == wplto_before
        and completed_after == completed_before,
        "r5 completed candidate identity red",
    )
    replay = {
        "format": "lisp65-c2.3-v1.12-link92-r5-artifact-completion-replay-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-public-dispatch-artifact-only-completion-replay",
        "authorization_commit": "425cc95d",
        "dispatch_gate": dispatch,
        "resume_authorization_commit": "ac172f65",
        "resume_gate": resume,
        "persisted_status_projection": {
            "expected": PERSISTED_REPLACEMENT_STATUS,
            "observed": authority["historical_checker_boundary"]
                ["current_replacement_gates"]["status"],
            "live_status_name_consumed": False,
        },
        "immutable_wplto_before": wplto_before,
        "immutable_wplto_after": wplto_after,
        "completed_final_before": completed_before,
        "completed_final_after": completed_after,
        "artifact_completion": bind(completion_path),
        "canonical_product_manifest": bind(MANIFEST),
        "identity": value["identity"],
        "execution_accounting": {
            "additional_product_compiler_runs": 0,
            "additional_product_linker_runs": 0,
            "additional_product_cards": 0,
            "artifact_completion_replays": 0,
            "artifact_completion_receipts_consumed": 1,
            "hardware_runs": 0,
        },
        "next_gate": "construct and close both Phase-C media variants",
        "claim_limit": (
            "Artifact-only completion of the existing r5 product card. No new "
            "compiler, linker, product-card, media, device, Halt or release claim."
        ),
    }
    COMPLETION_REPLAY.parent.mkdir(parents=True, exist_ok=True)
    COMPLETION_REPLAY.write_bytes(CAN.json_bytes(replay))
    print(
        "c2-v112-candidate-product: REPLAY PASS "
        f"product={value['identity']['resident_prg_sha256']} compiler=0 linker=0"
    )
    return 0


def product(action: str) -> int:
    require(EXPECTED_PRODUCT_ID != "0x00000000" and EXPECTED_BANK2_SHA != "0" * 64,
            "profile identities have not been bound into the candidate driver")
    emit_release_stdlib()
    emit_promoted_carrier()
    startup_gate()
    bind_inherited_entrypoint()
    if os.environ.get("LISP65_CANONICAL_SCOPE_SEED_ONLY") == "1":
        # The closure proves the current candidate's compile/link scope, not
        # unrelated release-freight receipts.  Those gates are already
        # permanent check-source prerequisites and some deliberately refresh
        # historical evidence.  Keep this seed check read-only outside its
        # owned build/receipt paths while leaving every link input and wrapper
        # in the candidate stack unchanged.
        P.freight_gates = lambda: {
            "mode": "canonical-opt-out-seed-link-closure",
            "summaries": {},
            "release_freight": bind(FREIGHT),
        }
    else:
        P.freight_gates = freight_gates
    P.augment_feature_receipt = augment_feature_receipt
    sys.argv = [sys.argv[0], action]
    return P.main()


def ownership_closure_seed() -> int:
    """Run the exact candidate stack only through its canonical seed link."""
    global BUILD, MANIFEST
    raw = os.environ.get("LISP65_CANONICAL_SCOPE_BUILD")
    require(raw is not None, "canonical scope seed build path is unbound")
    build = Path(raw)
    if not build.is_absolute():
        build = ROOT / build
    allowed = ROOT / "build/c2.3/v1.4.0-ownership-opt-out-seed-closure"
    require(build.resolve() == allowed.resolve(),
            "canonical scope seed build escaped its owned directory")
    BUILD = build
    MANIFEST = build / "canonical-product-manifest.json"
    os.environ["LISP65_CANONICAL_SCOPE_SEED_ONLY"] = "1"
    return product("build")


def main() -> int:
    action = parse_action()
    try:
        if action == "selftest":
            value = startup_selftest()
            print(
                "c2-v112-candidate-product-startup: PASS "
                f"mutations={value['mutations_rejected']}"
            )
            return 0
        if action == "profile":
            profile_source_gate()
            value = profile()
            print(
                "c2-v112-release-profile: PASS "
                f"bank2={value['geometry']['static_code_bytes']} "
                f"headroom={value['geometry']['bank2_headroom_bytes']} "
                f"id={value['geometry']['product_build_id']} linker=0"
            )
            return 0
        if action == "ownership-closure-seed":
            return ownership_closure_seed()
        if action == PUBLIC_COMPLETION_ACTION:
            return public_completion_action()
        if action == "replay":
            return replay_action()
        result = product(action)
        if result == 0:
            print(f"c2-v112-candidate-product: PASS action={action} link={LINK}")
        return result
    except (CandidateError, P.CandidateError, RuntimeError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v112-candidate-product: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
