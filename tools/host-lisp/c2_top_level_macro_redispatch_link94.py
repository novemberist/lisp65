#!/usr/bin/env python3
"""Build and bind the one Link-94 top-level macro redispatch product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_ship_input_wait_gate as INPUT  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT_LINK  # noqa: E402
import c2_v112_candidate_product as V112  # noqa: E402


CAN = V112.CAN
P = V112.P
CORE = P.PRODUCT
BASE = CORE.BASE
RELEASE = "post-v1.4-top-level-macro-redispatch"
LINK = 94
DRIVER = Path(__file__).resolve()
PREFLIGHT = ROOT / "build/c2.3/top-level-macro-redispatch-link94-preflight"
BUILD = ROOT / "build/c2.3/top-level-macro-redispatch-link94"
MANIFEST = BUILD / "canonical-product-manifest.json"
CODEMOD = PREFLIGHT / "codemod"
CODEMOD_SUITE = CODEMOD / "suites/p0-stdlib-einsuite-core-workbench-subset.json"
SUITE_CHAIN = PREFLIGHT / "suite-chain"
STATIC = PREFLIGHT / "static-plane/narrow-static"
STATIC_PRODUCT = STATIC / "product"
V6_PLANE = STATIC / "v6-semantics"
STDLIB_PREFIX = STATIC / "stdlib-p0"
STDLIB = STDLIB_PREFIX.with_suffix(".manifest.json")
SUITE = PREFLIGHT / "link94-stdlib-suite.json"
OBSERVATIONS = PREFLIGHT / "stdlib-observations.json"
IDE_AUTHORITY = PREFLIGHT / "authorities/ide.manifest.json"
BUFFER_AUTHORITY = PREFLIGHT / "authorities/buffer.manifest.json"
PREFLIGHT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-product-preflight-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-product-card-receipt.json"
)
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-top-level-macro-redispatch-receipt.json"
)
V111_CLOSURE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-v111-locality-replay-closure-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-product-card-first-red.json"
)
LINK93 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-link93-receipt.json"
)
CONTRACT = ROOT / "config/c2-top-level-macro-redispatch.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
HEADER = ROOT / "src/c2_lite_static_plane.h"
GATES = ROOT / "mk/gates.mk"
EXPECTED_STATIC = 45905
EXPECTED_ENTRIES = 751
EXPECTED_RESOLUTIONS = 2921
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 674
EXPECTED_PRODUCT_ID = "0x1866da2f"
EXPECTED_BANK2_SHA = (
    "c04e05acf4111d3dd3ad6eb2051c576d6f30e6d73b949acacc80c1ff635bbbe0"
)
LINK93_STATIC = 45794
LINK93_ENTRIES = 748
LINK93_RESOLUTIONS = 2913


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def authority_artifacts(stem: str) -> list[Path]:
    return sorted((PREFLIGHT / "authorities").glob(f"{stem}.*"))


def restore_product_input_authorities() -> None:
    target = ROOT / "build/bytecode/dialect-v2/libs"
    target.mkdir(parents=True, exist_ok=True)
    for stem, manifest, count in (
        ("ide", IDE_AUTHORITY, 8),
        ("buffer", BUFFER_AUTHORITY, 7),
    ):
        artifacts = authority_artifacts(stem)
        require(len(artifacts) == count
                and any(path.name == f"{stem}.manifest.json"
                        for path in artifacts),
                f"Link-94 {stem} authority snapshot is incomplete")
        for source in artifacts:
            shutil.copyfile(source, target / source.name)
        require(sha(target / f"{stem}.manifest.json") == sha(manifest),
                f"Link-94 {stem} authority restore drift")


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip()


def specs() -> tuple[tuple[str, str, Path], ...]:
    return (
        ("stdlib-p0", "stdlib", STDLIB),
        ("ide", "ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
        ("idex", "idex", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.manifest.json")),
        ("m65d", "m65d", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.manifest.json")),
        ("buffer", "buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
        ("lcc", "lcc", ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"),
    )


def direct_entry_census(product_dir: Path) -> int:
    c2d = (product_dir / "initial.c2d-v3.bin").read_bytes()
    shelf = (product_dir / "product-shelf-v4-direct.bin").read_bytes()
    require(c2d[:8] == b"C2D\0\x03\x30\x20\x0a", "C2D-v3 identity drift")
    count = 0
    for slot in range(struct.unpack_from("<H", c2d, 12)[0]):
        row = 48 + slot * 32
        resolutions = struct.unpack_from("<H", c2d, row + 12)[0]
        metadata = int.from_bytes(c2d[row + 23:row + 26], "little")
        literal_count = struct.unpack_from("<H", shelf, metadata + 12)[0]
        literal_offset = struct.unpack_from("<H", shelf, metadata + 16)[0]
        require(literal_count == resolutions, "C2D/shelf literal count drift")
        for local in range(literal_count):
            descriptor = metadata + literal_offset + local * 8
            require(descriptor + 8 <= len(shelf), "literal descriptor out of range")
            count += shelf[descriptor] == 4
    return count


def isolated_stdlib_suite() -> dict[str, Any]:
    chain = (
        "p0-stdlib-ship-input-wait-base.json",
        "p0-stdlib-time-base.json",
        "p0-stdlib-q-base.json",
        "p0-stdlib-random-base.json",
        "p0-stdlib-require-resolver.json",
    )
    source_dir = ROOT / "tests/bytecode/libs"
    SUITE_CHAIN.mkdir(parents=True)
    for name in chain:
        value = load(source_dir / name)
        if name == chain[-1]:
            value["extends"] = os.path.relpath(CODEMOD_SUITE, SUITE_CHAIN)
        (SUITE_CHAIN / name).write_bytes(canonical(value))
    resolved = STD._read_suite(str(SUITE_CHAIN / chain[0]))
    baseline = STD._read_suite(str(INPUT.SUITE))
    resolved["_suite_path"] = baseline["_suite_path"]
    resolved["_suite_dir"] = baseline["_suite_dir"]
    new_prefix = CODEMOD.relative_to(ROOT).as_posix() + "/sources/"
    sources = resolved.get("sources")
    require(isinstance(sources, list), "resolved stdlib source list absent")
    isolated = [source for source in sources
                if isinstance(source, str) and source.startswith(new_prefix)]
    require(len(isolated) >= 10,
            "Link-94 generated sources escaped their isolated tree")
    functions = resolved.get("functions")
    require(isinstance(functions, list), "resolved stdlib function list absent")
    require(all(functions.count(name) == 1 for name in (
        "%c2-top-level-expand", "%c2-top-level-run-forms", "%c2-run-expanded",
    )), "Link-94 function inventory is not unique")
    return resolved


def build_preflight() -> dict[str, Any]:
    require(not PREFLIGHT.exists(), "Link-94 preflight is one-shot")
    PREFLIGHT.mkdir(parents=True)
    codemod = run([
        sys.executable, "tools/host-lisp/v2_workbench_codemod.py",
        "--out", CODEMOD.relative_to(ROOT).as_posix(),
    ], "isolated Link-94 Workbench codemod")
    require("v2-workbench-codemod: PASS" in codemod, "isolated codemod witness absent")
    SUITE.write_text(json.dumps(isolated_stdlib_suite(), indent=2) + "\n",
                     encoding="utf-8")
    stdlib = INPUT.run_suite(SUITE, STDLIB_PREFIX, OBSERVATIONS)
    inventory = specs()
    require(len(inventory) == 6 and all(path.is_file() for _k, _n, path in inventory),
            "six-role Link-94 preflight inventory incomplete")
    old_sub = (SUB.BUILD, SUB.SPECS)
    old_v6 = (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUB.BUILD = STATIC_PRODUCT
        SUB.SPECS = inventory
        product = SUB.build()
        static_bytes = sum(int(load(path)["code_bytes"])
                           for _key, _name, path in inventory)
        V6.OUT = V6_PLANE
        V6.PRODUCT_IDENTITY = STATIC_PRODUCT / "substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = static_bytes
        V6.A.SPECS = inventory
        V6_PLANE.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUB.BUILD, SUB.SPECS = old_sub
        (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS) = old_v6
    bank2 = V6_PLANE / "bank2-static-code.bin"
    IDE_AUTHORITY.parent.mkdir(parents=True)
    for stem, source_manifest, count in (
        ("ide", inventory[1][2], 8),
        ("buffer", inventory[4][2], 7),
    ):
        for source in sorted(source_manifest.parent.glob(f"{stem}.*")):
            shutil.copyfile(source, IDE_AUTHORITY.parent / source.name)
        require(len(authority_artifacts(stem)) == count,
                f"Link-94 {stem} authority snapshot cardinality drift")
    geometry = {
        "static_code_bytes": static_bytes,
        "headroom_bytes": 65536 - static_bytes,
        "entries": int(product["entries"]),
        "resolutions": int(product["resolutions"]),
        "roots": int(product["roots"]),
        "direct_entry_refs": direct_entry_census(STATIC_PRODUCT),
        "product_build_id": str(product["product_build_id_hex"]),
        "bank2_sha256": sha(bank2),
    }
    require(
        geometry == {
            "static_code_bytes": EXPECTED_STATIC,
            "headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": EXPECTED_PRODUCT_ID,
            "bank2_sha256": EXPECTED_BANK2_SHA,
        }
        and semantics["static_bank2"]["code_bytes"] == EXPECTED_STATIC
        and int(stdlib["code_bytes"]) == 17100
        and len(stdlib["entries"]) == 389,
        f"Link-94 linker-free geometry drift: {geometry}",
    )
    value = {
        "format": "lisp65-c2.3-link94-product-preflight-v1",
        "recorded_on": "2026-08-09",
        "status": "passed-link94-linker-free-input-closure",
        "product_links": 0,
        "wplto_runs": 0,
        "geometry": geometry,
        "delta_from_link93": {
            "bank2_code_bytes": static_bytes - LINK93_STATIC,
            "entries": product["entries"] - LINK93_ENTRIES,
            "resolutions": product["resolutions"] - LINK93_RESOLUTIONS,
            "roots": product["roots"] - EXPECTED_ROOTS,
            "direct_entry_refs": geometry["direct_entry_refs"] - EXPECTED_DIRECT_REFS,
            "resident_bytes": 0,
        },
        "authorities": {
            "contract": bind(CONTRACT),
            "host_gate": bind(HOST_RECEIPT),
            "isolated_suite": bind(SUITE),
            "stdlib_manifest": bind(STDLIB),
            "ide_manifest": bind(IDE_AUTHORITY),
            "ide_artifacts": [bind(path) for path in authority_artifacts("ide")],
            "buffer_manifest": bind(BUFFER_AUTHORITY),
            "buffer_artifacts": [
                bind(path) for path in authority_artifacts("buffer")],
            "product_manifest": bind(STATIC_PRODUCT / "substitution-artifacts.json"),
            "bank2": bind(bank2),
            "compiler_carrier": bind(inventory[-1][2]),
            "driver": bind(DRIVER),
        },
        "isolation": {
            "generated_sources": CODEMOD.relative_to(ROOT).as_posix(),
            "historical_v111_generator_tree_changed": False,
            "compiler_carrier_changed": False,
        },
        "claim_limit": "Linker-free Link-94 profile only; no product or hardware claim.",
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    return value


def validate_preflight(value: dict[str, Any], *, verify: bool) -> None:
    geometry = value.get("geometry", {})
    require(
        value.get("format") == "lisp65-c2.3-link94-product-preflight-v1"
        and value.get("status") == "passed-link94-linker-free-input-closure"
        and value.get("product_links") == value.get("wplto_runs") == 0
        and geometry == {
            "static_code_bytes": EXPECTED_STATIC,
            "headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": EXPECTED_PRODUCT_ID,
            "bank2_sha256": EXPECTED_BANK2_SHA,
        }
        and value.get("delta_from_link93") == {
            "bank2_code_bytes": 111,
            "entries": 3,
            "resolutions": 8,
            "roots": 0,
            "direct_entry_refs": 0,
            "resident_bytes": 0,
        },
        "Link-94 preflight claim drift",
    )
    if verify:
        require(value["authorities"]["contract"] == bind(CONTRACT)
                and value["authorities"]["host_gate"] == bind(HOST_RECEIPT)
                and value["authorities"]["isolated_suite"] == bind(SUITE)
                and value["authorities"]["stdlib_manifest"] == bind(STDLIB)
                and value["authorities"]["ide_manifest"] == bind(IDE_AUTHORITY)
                and value["authorities"]["ide_artifacts"]
                    == [bind(path) for path in authority_artifacts("ide")]
                and value["authorities"]["buffer_manifest"]
                    == bind(BUFFER_AUTHORITY)
                and value["authorities"]["buffer_artifacts"]
                    == [bind(path) for path in authority_artifacts("buffer")]
                and value["authorities"]["product_manifest"]
                    == bind(STATIC_PRODUCT / "substitution-artifacts.json")
                and value["authorities"]["bank2"]
                    == bind(V6_PLANE / "bank2-static-code.bin"),
                "Link-94 preflight artifact binding drift")
        profile = load(PROFILE)
        require(
            profile["bank2_static_code"] == {
                "bytes": EXPECTED_STATIC,
                "headroom_bytes": 65536 - EXPECTED_STATIC,
                "sha256": EXPECTED_BANK2_SHA,
            }
            and profile["entries"] == EXPECTED_ENTRIES
            and profile["resolutions"] == EXPECTED_RESOLUTIONS
            and profile["roots"] == EXPECTED_ROOTS
            and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
            and profile["product_build_id"] == EXPECTED_PRODUCT_ID
            and "45905UL" in HEADER.read_text(encoding="utf-8"),
            "tracked Link-94 profile/header pin drift",
        )


def configure_card() -> dict[str, Path]:
    restore_product_input_authorities()
    V112.RELEASE = RELEASE
    V112.LINK = LINK
    V112.BUILD = BUILD
    V112.MANIFEST = MANIFEST
    V112.DRIVER = DRIVER
    V112.RELEASE_STDLIB_PREFIX = STDLIB_PREFIX
    V112.RELEASE_STDLIB = STDLIB
    V112.EXPECTED_STATIC = EXPECTED_STATIC
    V112.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V112.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V112.EXPECTED_ROOTS = EXPECTED_ROOTS
    V112.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V112.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    V112.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    paths = V112.configure(BUILD)
    inherited_single_link = PRODUCT_LINK.single_link

    def service_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path =
            PRODUCT_LINK.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        # The historical product adapters rebuild the Session inventory at
        # the actual link boundary.  Select the Link-93 service shape only
        # after those transforms and immediately before catalog emission.
        PRODUCT_LINK.configure_intern_session_service()
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

    # Every public action configures once in its own process.  Capture the
    # fully composed historical chain here so the resolver and profile
    # adapters remain authoritative, then select the service at its final
    # link boundary.
    PRODUCT_LINK.single_link = service_single_link
    CORE.RELEASE = RELEASE
    CORE.LINK = LINK
    CORE.BUILD = BUILD
    CORE.MANIFEST = MANIFEST
    CORE.DRIVER = DRIVER
    CORE.configure = configure_card
    CORE.build_manifest = build_manifest
    CORE.complete_in_fresh_process = complete_in_fresh_process
    require(tuple(CAN.SPECS) == specs(), "Link-94 card specs differ from preflight")
    return paths


def freight_gates() -> dict[str, Any]:
    host = load(HOST_RECEIPT)
    link93 = load(LINK93)
    locality = load(V111_CLOSURE_RECEIPT)
    require(
        host.get("status") == "HOST-GREEN; ACTUAL-LCC-REDISPATCH-PROVED"
        and host["freight"]["resident_delta_bytes"] == 0
        and host["freight"]["delta"]["encoded_code_object_bytes"] == 111
        and link93.get("status") == "LINK93-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING"
        and locality.get("status")
            == "passed-isolated-SHA-bound-v111-locality-replay-input-closure"
        and locality["attempt_accounting"] == {
            "product_cards": 0, "product_links": 0, "device_contacts": 0,
        }
        and load(FIRST_RED)["attempt_accounting"]["product_cards_consumed"] == 1,
        "Link-94 host/Link-93 authority drift",
    )
    summaries = {
        "redispatch": run([sys.executable,
                           "tools/host-lisp/c2_top_level_macro_redispatch.py",
                           "check"], "actual lcc-run redispatch gate"),
        "published_call": run([sys.executable,
                               "tools/host-lisp/c2_top_level_published_value_call_gate.py"],
                              "published top-level call gate"),
        "locality": run([
            sys.executable,
            "tools/host-lisp/c2_v111_locality_replay_closure.py", "check",
        ], "isolated compiler-locality replay closure wall"),
        "performance": run(["make", "c2-v110-persistent-performance-check"],
                           "persistent-performance wall"),
    }
    return {
        "mode": "Link-94-top-level-macro-redispatch",
        "summaries": summaries,
        "host_receipt": bind(HOST_RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "link93_predecessor": bind(LINK93),
        "locality_replay_closure": bind(V111_CLOSURE_RECEIPT),
        "first_red": bind(FIRST_RED),
    }


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = V112.BASE_BUILD_MANIFEST(wplto, completion)
    value["static_plane"].update({
        "status": "passed-Link94-top-level-macro-redispatch-static-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "product_build_id": EXPECTED_PRODUCT_ID,
        "bank2_sha256": EXPECTED_BANK2_SHA,
        "stdlib_manifest": bind(STDLIB),
        "compiler_carrier": bind(specs()[-1][2]),
        "redispatch_contract": bind(CONTRACT),
        "redispatch_execution": bind(HOST_RECEIPT),
        "linker_free_preflight": bind(PREFLIGHT_RECEIPT),
    })
    value["candidate"] = {
        "release": RELEASE,
        "pre_promotion": True,
        "public_surface_changed": False,
        "source_driver": bind(DRIVER),
    }
    value["session_service"] = {
        "name": "intern-session-service",
        "slot": 51,
        "bytes": 399,
        "catalog_records": 52,
    }
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def complete_action() -> int:
    paths = configure_card()
    replay = CAN.REPLAY
    original = replay.configure

    def current_geometry() -> None:
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.configure_intern_session_service()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            paths["static_product"] / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "Link-94 artifact-completion geometry drift",
        )

    replay.configure = current_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"] == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link-94 artifact completion red",
    )
    print("Link-94 artifact completion: PASS compiler=0 linker=0")
    return 0


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0,
            "Link-94 fresh-process completion red:\n" + result.stdout)
    paths = BASE.paths(BUILD)
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def derive_card_receipt(wplto: dict[str, Any]) -> dict[str, Any]:
    paths = BASE.paths(BUILD)
    internal = load(paths["receipts"] / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = load(MANIFEST)
    require(
        internal["execution_accounting"]["product_closure_links"] == 1
        and replacement["status"] == "passed"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and capacity["session_service_records"] == 1
        and capacity["session_service_bytes"] == 399
        and completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and manifest["static_plane"]["bank2_static_code_bytes"] == EXPECTED_STATIC,
        "Link-94 product closure did not close",
    )
    return {
        "format": "lisp65-c2.3-link94-replacement-product-card-v1",
        "recorded_on": "2026-08-09",
        "status": "LINK94-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING",
        "attempt_accounting": {
            "product_cards_authorized": 2,
            "product_cards_consumed": 2,
            "product_closure_links": 1,
            "hardware_runs": 0,
        },
        "source": {
            "contract": bind(CONTRACT),
            "host_receipt": bind(HOST_RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "locality_replay_closure": bind(V111_CLOSURE_RECEIPT),
            "first_red": bind(FIRST_RED),
            "driver": bind(DRIVER),
        },
        "geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "resident_delta_bytes": 0,
            "walls": walls,
            "session_capacity": capacity,
        },
        "artifacts": {
            "manifest": bind(MANIFEST),
            "product": bind(paths["final"] / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.elf"),
            "map": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.map"),
            "profile": bind(paths["final"] / "resolved-profile.txt"),
            "bank2": bind(paths["static"] / "v6-semantics/bank2-static-code.bin"),
            "completion": bind(paths["receipts"] / "artifact-completion.json"),
            "internal": bind(paths["receipts"] / "wplto-internal.json"),
        },
        "hardware_handoff": {
            "status": "media-pending",
            "trace_forms": [
                "(require (quote inspect))",
                "(defun trace-probe (x) (+ x 1))",
                "(trace trace-probe)",
                "(trace-probe 4)",
                "(untrace trace-probe)",
                "(trace-probe 4)",
            ],
            "bundled_defstruct_sister": True,
        },
        "claim_limit": "One explicitly authorized Link-94 replacement card after one bound pre-link First Red; no media, hardware, release or public-surface claim.",
    }


def validate_card(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == "lisp65-c2.3-link94-replacement-product-card-v1"
        and value.get("status")
            == "LINK94-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING"
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 2,
            "product_cards_consumed": 2,
            "product_closure_links": 1,
            "hardware_runs": 0,
        }
        and value["geometry"]["bank2_static_code_bytes"] == EXPECTED_STATIC
        and value["geometry"]["bank2_headroom_bytes"] == 65536 - EXPECTED_STATIC
        and value["geometry"]["resident_delta_bytes"] == 0
        and value["hardware_handoff"]["status"] == "media-pending",
        "Link-94 card claim drift",
    )
    if verify:
        current = derive_card_receipt({})
        require(value == current, "Link-94 product card receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=0),
        "hide-link": lambda x: x["attempt_accounting"].update(
            product_closure_links=0),
        "claim-device": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "grow-resident": lambda x: x["geometry"].update(resident_delta_bytes=1),
        "move-bank2": lambda x: x["geometry"].update(bank2_static_code_bytes=45904),
        "claim-media": lambda x: x["hardware_handoff"].update(status="prepared"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_card(candidate, verify=False)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(cases), "Link-94 card mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-94 replacement product card is one-shot")
    require(FIRST_RED.is_file() and V111_CLOSURE_RECEIPT.is_file(),
            "Link-94 replacement authority is incomplete")
    preflight = load(PREFLIGHT_RECEIPT)
    validate_preflight(preflight, verify=True)
    freight = freight_gates()
    BUILD.mkdir(parents=True)
    shutil.copytree(PREFLIGHT / "static-plane", BUILD / "static-plane")
    paths = configure_card()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header = CORE.bind_generated_stdlib_header(paths)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and header["manifest"] == bind(STDLIB),
        "Link-94 copied preflight plane failed the product gate",
    )
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"]["current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_headroom_bytes"] >= 0,
            "Link-94 product geometry wall red")
    complete_in_fresh_process()
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = CAN.check()
    require(checked["identity"] == manifest["identity"],
            "Link-94 completed product identity red")
    feature = {
        "status": "passed-Link94-top-level-macro-redispatch-feature-gates",
        "freight": freight,
        "target_stdlib_header": header,
    }
    (paths["receipts"] / f"{RELEASE}-feature-gates.json").write_bytes(
        canonical(feature))
    value = derive_card_receipt(wplto)
    validate_card(value, verify=False)
    RECEIPT.write_bytes(canonical(value))
    print(
        "Link-94 replacement product card: PASS "
        f"bank2={EXPECTED_STATIC} resident=0 "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}"
    )
    return 0


def ownership_closure_seed() -> int:
    """Run the Link-94 canonical scope through its sole non-product seed link."""
    global BUILD, MANIFEST
    raw = os.environ.get("LISP65_CANONICAL_SCOPE_BUILD")
    require(raw is not None, "Link-94 canonical seed build path is unbound")
    build = Path(raw)
    if not build.is_absolute():
        build = ROOT / build
    allowed = ROOT / "build/c2.3/v1.4.0-ownership-opt-out-seed-closure"
    require(build.resolve() == allowed.resolve(),
            "Link-94 canonical seed escaped its owned directory")
    require(not build.exists(), "Link-94 canonical seed build is not fresh")
    BUILD = build
    MANIFEST = build / "canonical-product-manifest.json"
    os.environ["LISP65_CANONICAL_SCOPE_SEED_ONLY"] = "1"
    validate_preflight(load(PREFLIGHT_RECEIPT), verify=True)
    build.mkdir(parents=True)
    shutil.copytree(PREFLIGHT / "static-plane", build / "static-plane")
    paths = configure_card()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header = CORE.bind_generated_stdlib_header(paths)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and header["manifest"] == bind(STDLIB),
        "Link-94 canonical seed input closure drift",
    )
    # The product linker writes the canonical seed receipt and raises
    # SystemExit(0) immediately after its one seed link.  Reaching this return
    # would mean the non-product boundary was bypassed.
    CAN.run_wplto()
    raise CardError("Link-94 canonical seed crossed its terminal boundary")


def check_action() -> int:
    preflight = load(PREFLIGHT_RECEIPT)
    validate_preflight(preflight, verify=True)
    value = load(RECEIPT)
    validate_card(value, verify=True)
    print("Link-94 product card check: PASS")
    return 0


def selftest() -> int:
    preflight = load(PREFLIGHT_RECEIPT)
    validate_preflight(preflight, verify=True)
    if RECEIPT.is_file():
        value = load(RECEIPT)
        validate_card(value, verify=False)
        count = len(mutations(value))
    else:
        count = 0
    gates = GATES.read_text(encoding="utf-8")
    require("c2-top-level-macro-redispatch-check:" in gates,
            "Link-94 actual redispatch gate is not permanent")
    print(f"Link-94 product selftest: PASS card-mutations={count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("preflight", "preflight-check", "build", "_complete",
                           "check", "selftest", "ownership-closure-seed"))
    action = parser.parse_args().action
    if action == "preflight":
        value = build_preflight()
        print("Link-94 preflight: PASS " + json.dumps(value["geometry"], sort_keys=True))
        return 0
    if action == "preflight-check":
        validate_preflight(load(PREFLIGHT_RECEIPT), verify=True)
        print("Link-94 preflight check: PASS")
        return 0
    if action == "_complete":
        os.environ.update(CAN.canonical_build_environment())
        return complete_action()
    if action == "build":
        environment = CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy()
            updated.update(environment)
            os.execve(sys.executable, [sys.executable, str(DRIVER), "build"], updated)
        return build_action()
    if action == "ownership-closure-seed":
        os.environ.update(CAN.canonical_build_environment())
        return ownership_closure_seed()
    if action == "check":
        return check_action()
    return selftest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Link-94 product card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
