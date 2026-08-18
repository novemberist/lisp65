#!/usr/bin/env python3
"""Build the regular v1.5 media successor for the name-freight fix."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v112_candidate_media as LIB  # noqa: E402
import c2_v150_candidate_media as BASE  # noqa: E402
import c2_v150_name_freight_implementation as FREIGHT  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-name-freight-media"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
MANIFEST = SHARED / "candidate-manifest.json"
DESCRIPTOR = SHARED / "boot.id"
STAGER = SHARED / "autoboot.c65"
STAGER_ELF = SHARED / "autoboot.c65.elf"
STAGER_MAP = SHARED / "autoboot.c65.map"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
MOUNT = SHARED / "lisp65-product.mount.json"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
SESSION = ROOT / "config/c2-v150-name-freight-device-session.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-media-receipt.json")
FORMAT = "lisp65-c2.3-v1.5.0-name-freight-media-v1"
STATUS = "V150-NAME-FREIGHT-HOST-AND-MEDIA-GREEN; FRESH-D1-PENDING"
VARIANTS = {
    "v1.5": (
        ("string-extra", "strx", "strextr", BASE.STRING, ()),
        ("inspect", "inspect", "inspect", FREIGHT.INSPECT_MANIFEST, ()),
        ("place", "place", "place", BASE.PLACE, ()),
        ("defstruct", "defstruct", "dfstrct", FREIGHT.DEFSTRUCT_MANIFEST, (2,)),
    ),
}


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def configure() -> None:
    BASE.configure()
    MEDIA.BUILD = SHARED
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = DESCRIPTOR
    MEDIA.STAGER = STAGER
    MEDIA.STAGER_MAP = STAGER_MAP
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = MOUNT


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    configure_node = functions.get("configure")
    require(build is not None and configure_node is not None,
            "name-freight media producer lifecycle absent")
    calls = [ast.unparse(node.func) for node in ast.walk(build)
             if isinstance(node, ast.Call)]
    build_text = ast.unparse(build)
    variants_text = source.split("VARIANTS =", 1)[1].split(
        "\n\n\nclass MediaError", 1)[0]
    require(
        calls.count("MEDIA.build") == 1
        and calls.count("LIB.build_library_variant") == 1
        and "stager_compile_defines=(LIVE.OPT_IN,)" in build_text
        and variants_text.count("FREIGHT.INSPECT_MANIFEST") == 1
        and variants_text.count("FREIGHT.DEFSTRUCT_MANIFEST") == 1
        and "BASE.CARD.build" not in calls
        and "BASE.CARD.post_link_replay" not in calls,
        "media producer can omit a fixed library, liveness opt-in or scope wall")
    configure_text = ast.unparse(configure_node)
    require(all(token in configure_text for token in (
        "MEDIA.BUILD = SHARED", "MEDIA.MANIFEST = MANIFEST",
        "MEDIA.DESCRIPTOR = DESCRIPTOR", "MEDIA.STAGER = STAGER",
        "MEDIA.PRODUCT_D81 = PRODUCT_D81")),
        "media producer did not own every regenerated contract member")
    return {"result": "passed", "shared_media_builds": 1,
            "library_builds": 1, "product_links": 0, "WPLTO_runs": 0}


def source_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    cases = {
        "drop-liveness-opt-in": source.replace(
            "    shared = MEDIA.build(stager_compile_defines=(LIVE.OPT_IN,))",
            "    shared = MEDIA.build(stager_compile_defines=())", 2),
        "reuse-old-inspect": source.replace(
            "FREIGHT.INSPECT_MANIFEST", "BASE.INSPECT", 1),
        "reuse-old-defstruct": source.replace(
            "FREIGHT.DEFSTRUCT_MANIFEST", "BASE.DEFSTRUCT", 1),
        "skip-library-build": source.replace(
            "        LIB.build_library_variant(\"v1.5\", LIBRARY, build_id)\n",
            "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "name-freight media source mutation survived")
    return rejected


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    require(
        value.get("format") == "lisp65-c2-v150-name-freight-device-session-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("order") == ["D1", "D2", "D3", "D4", "D5"]
        and value.get("release_terminal_row") == "D5"
        and value.get("identity") == {
            "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
            "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix()}
        and value["headroom_postcondition"] == {
            "contract": "config/release-user-headroom-contract.json",
            "counter_addresses": "candidate ELF symbols nsym and npool",
            "counter_view": "one final physical Bank-0 stopped-state capture",
            "observation_point": "after every D5 performance row",
            "public_repl_probes": 0},
        "name-freight D1-D5 session contract drift")
    return value


def library_facts(build_id: int) -> dict[str, Any]:
    old = LIB.VARIANTS
    try:
        LIB.VARIANTS = VARIANTS
        result = LIB.existing_library_variant("v1.5", LIBRARY, build_id)
    finally:
        LIB.VARIANTS = old
    require([row["name"] for row in result["index_rows"]]
            == ["string-extra", "inspect", "place", "defstruct"]
            and result["resolver_contracts"]["defstruct"]
                ["declared_dependency_closure"] == [2, 3]
            and result["index_mutations_rejected"] == 32,
            "name-freight library dependency/index closure drift")
    return result


def facts(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    shared = MEDIA.check()
    build_id = BASE.product_build_id()
    library = library_facts(build_id)
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    liveness = LIVE.delivered_liveness_gate(STAGER_ELF)
    require(shared["artifact_count"] == 19
            and pair["result"] == "same-world-pair"
            and pair["index_rows"] == 4
            and library["D81"] == bind(LIBRARY_D81),
            "name-freight media/readback/pair closure red")
    return {"shared": shared, "library": library, "pair": pair,
            "liveness": liveness}


def derive(*, configured: bool = False) -> dict[str, Any]:
    session_contract()
    implementation = load(FREIGHT.RECEIPT)
    require(implementation["status"]
            == "HOST-GREEN-COMBINED-NAME-FREIGHT; MEDIA-PENDING",
            "name-freight implementation authority drift")
    result = facts(configured=configured)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_links": 0, "WPLTO_runs": 0, "qualification_replays": 0,
            "cold_stager_compiler_runs": 1, "shared_system_builds": 1,
            "library_builds": 1, "media_readbacks": 1, "hardware_runs": 0},
        "authority": {
            "owner_authorization": {"commit": "a8f7f08a"},
            "implementation": bind(FREIGHT.RECEIPT),
            "frozen_product_manifest": bind(BASE.CARD.MANIFEST),
            "session_contract": bind(SESSION), "producer": bind(Path(__file__)),
        },
        "producer_gate": source_gate(),
        "producer_mutations_rejected": source_mutations(),
        "completion": {
            "resume_after_post_build_mutation_harness_red": True,
            "artifacts_rebuilt_during_resume": False,
        },
        "actual_packed_ELF_gate": result["liveness"],
        "shared_system": {
            "artifact_count": result["shared"]["artifact_count"],
            "artifact_set_sha256": result["shared"]["artifact_set_sha256"],
            "manifest": bind(MANIFEST), "boot_id": bind(DESCRIPTOR),
            "autoboot": bind(STAGER), "product_D81": bind(PRODUCT_D81),
            "work_D81": bind(WORK_D81), "readback": "passed"},
        "library": {**result["library"], "readback": "passed",
                    "inspect_manifest": bind(FREIGHT.INSPECT_MANIFEST),
                    "defstruct_manifest": bind(FREIGHT.DEFSTRUCT_MANIFEST)},
        "pair_identity": result["pair"],
        "hardware_handoff": {
            "status": "fresh-D1-pending", "rows": ["D1", "D2", "D3", "D4", "D5"],
            "required_visible_signs": [
                "LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
                "LISP65: LOADING LIBRARIES"],
            "D2_D5_open": False,
            "D5_headroom_postcondition": load(SESSION)["headroom_postcondition"]},
        "claim_limit": (
            "Regular same-world media closure for the host-green name-freight "
            "implementation. Product bytes are frozen. No device, D1-D5, Halt "
            "or release claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value.get("attempt_accounting") == {
                "product_links": 0, "WPLTO_runs": 0,
                "qualification_replays": 0, "cold_stager_compiler_runs": 1,
                "shared_system_builds": 1, "library_builds": 1,
                "media_readbacks": 1, "hardware_runs": 0}
            and value.get("actual_packed_ELF_gate", {}).get("result")
                == "passed-actual-linked-stager-prefix"
            and value.get("pair_identity", {}).get("result") == "same-world-pair"
            and value.get("shared_system", {}).get("artifact_count") == 19
            and value.get("shared_system", {}).get("readback") == "passed"
            and value.get("library", {}).get("readback") == "passed"
            and value.get("hardware_handoff", {}).get("D2_D5_open") is False,
            "name-freight media claim drift")
    if verify:
        require(value == derive(), "name-freight media receipt stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "drop-role": lambda x: x["shared_system"].update(artifact_count=18),
        "skip-shared-readback": lambda x: x["shared_system"].update(readback="skipped"),
        "skip-library-readback": lambda x: x["library"].update(readback="skipped"),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "open-D2": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "name-freight media receipt mutation survived")
    return rejected


def build_action() -> int:
    require(not RECEIPT.exists(), "name-freight media receipt already exists")
    FREIGHT.audit(load(FREIGHT.RECEIPT))
    session_contract(); source_gate(); source_mutations()
    configure()
    resumed = BUILD.exists()
    if not resumed:
        shared = MEDIA.build(stager_compile_defines=(LIVE.OPT_IN,))
        require(shared["artifact_count"] == 19, "shared media role count drift")
        build_id = BASE.product_build_id()
        old = LIB.VARIANTS
        try:
            LIB.VARIANTS = VARIANTS
            LIB.build_library_variant("v1.5", LIBRARY, build_id)
        finally:
            LIB.VARIANTS = old
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 name-freight media build: PASS roles=19 rows=4 same-world"
          + (" resumed-no-rebuild" if resumed else ""))
    return 0


def fresh_readback() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "check"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            "name-freight media fresh readback red:\n" + completed.stdout)
    print(completed.stdout.strip())


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "name-freight media mutation set drift")
    print("v1.5 name-freight media check: PASS roles=19 rows=4 same-world")
    return 0


def selftest() -> int:
    source_gate(); source_mutations(); session_contract()
    print("v1.5 name-freight media selftest: PASS mutations=4")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    if action == "build":
        result = build_action(); fresh_readback(); return result
    return {"check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MediaError, FREIGHT.ImplementationError, BASE.MediaError,
            MEDIA.MediaError, LIB.MediaClosureError, RuntimeError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"V1.5 NAME FREIGHT MEDIA: {error}", file=sys.stderr)
        raise SystemExit(1)
