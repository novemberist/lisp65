#!/usr/bin/env python3
"""Build/check the same-world v1.5 Link-97 product and library media."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v112_candidate_media as LIB  # noqa: E402
import c2_v150_candidate_product as CARD  # noqa: E402
import c2_v150_replay_r10 as R10  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-candidate-media-link97"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
MANIFEST = SHARED / "candidate-manifest.json"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-media-closure-receipt.json")
SESSION = ROOT / "config/c2-v150-link97-device-session.json"
CONTRACT = ROOT / "config/c2-v150-release-contract.json"
RESUME = CARD.REPLAY_RECEIPT
STRING = ROOT / "build/post-promotion/v112/string-extra/string-extra.manifest.json"
INSPECT = ROOT / "build/c2.3/trace-core-abi/inspect.manifest.json"
PLACE = ROOT / "build/post-promotion/defstruct-v1/foundations/place.manifest.json"
DEFSTRUCT = ROOT / (
    "build/post-promotion/v110-performance/defstruct-candidate.manifest.json")
VARIANTS = {
    "v1.5": (
        ("string-extra", "strx", "strextr", STRING, ()),
        ("inspect", "inspect", "inspect", INSPECT, ()),
        ("place", "place", "place", PLACE, ()),
        ("defstruct", "defstruct", "dfstrct", DEFSTRUCT, (2,)),
    ),
}
FORMAT = "lisp65-c2.3-v150-link97-media-closure-v1"
STATUS = "V150-LINK97-HOST-AND-MEDIA-GREEN; D1-D5-PENDING"
_CONFIGURE_CALLS = 0


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
    global _CONFIGURE_CALLS
    require(_CONFIGURE_CALLS == 0, "v1.5 media configured twice in one process")
    _CONFIGURE_CALLS += 1
    R10.configure_replay()
    CARD.configure(CARD.REPLAY_PROFILE)
    CARD.L95.CAN.MANIFEST = CARD.MANIFEST
    MEDIA.CANONICAL = CARD.L95.CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = CARD.MANIFEST
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    configure_node = functions.get("configure")
    fresh = functions.get("fresh_readback")
    require(build is not None and configure_node is not None and fresh is not None,
            "v1.5 media lifecycle entrypoint absent")
    build_calls = [ast.unparse(node.func) for node in ast.walk(build)
                   if isinstance(node, ast.Call)]
    configure_text = ast.unparse(configure_node)
    fresh_text = ast.unparse(fresh)
    require(
        "CARD.configure(CARD.REPLAY_PROFILE)" in configure_text
        and "_CONFIGURE_CALLS == 0" in configure_text
        and build_calls.count("MEDIA.build") == 1
        and build_calls.count("LIB.build_library_variant") == 1
        and "CARD.build" not in build_calls
        and "CARD.replay" not in build_calls
        and "CARD.post_link_replay" not in build_calls
        and "subprocess.run" in fresh_text and "'check'" in fresh_text,
        "v1.5 media producer can escape its one-card/readback boundary")
    return {
        "status": "passed-media-only-same-world-producer-source-gate",
        "product_links": 0, "qualification_replays": 0,
        "shared_system_builds": 1, "library_builds": 1,
        "fresh_readback_processes": 1,
    }


def source_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    anchor = "    configure()\n    shared = MEDIA.build()"
    cases = {
        "reenter-card": source.replace(
            anchor, "    configure()\n    CARD.build()\n    shared = MEDIA.build()", 1),
        "reenter-qualification": source.replace(
            anchor, "    configure()\n    CARD.post_link_replay()\n"
            "    shared = MEDIA.build()", 1),
        "double-shared": source.replace(
            anchor, "    configure()\n    MEDIA.build()\n"
            "    shared = MEDIA.build()", 1),
        "drop-config-guard": source.replace(
            "_CONFIGURE_CALLS == 0", "_CONFIGURE_CALLS >= 0", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "v1.5 media source mutation survived")
    return rejected


def product_build_id() -> int:
    product = load(CARD.MANIFEST)
    value = int(product["static_plane"]["product_build_id"], 0)
    roles = {row["role"]: row for row in product["artifacts"]}
    c2d = (ROOT / roles["c2d-v6-code-plane"]["path"]).read_bytes()
    require(
        len(c2d) == MEDIA.C2D_PREFIX_BYTES
        and int.from_bytes(c2d[44:48], "little") == value,
        "v1.5 product manifest/C2D world identity drift")
    return value


def library_facts(build_id: int) -> dict[str, Any]:
    old = LIB.VARIANTS
    try:
        LIB.VARIANTS = VARIANTS
        value = LIB.existing_library_variant("v1.5", LIBRARY, build_id)
    finally:
        LIB.VARIANTS = old
    rows = value["index_rows"]
    require(
        [row["name"] for row in rows]
            == ["string-extra", "inspect", "place", "defstruct"]
        and [row["dependencies"] for row in rows] == [[], [], [], [2]]
        and value["resolver_contracts"]["defstruct"][
            "declared_dependency_closure"] == [2, 3]
        and value["index_mutations_rejected"] == 32,
        "v1.5 library dependency/index closure drift")
    return value


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    contract = load(CONTRACT)
    require(
        value.get("format") == "lisp65-c2-v150-link97-device-session-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("order") == ["D1", "D2", "D3", "D4", "D5"]
        and value.get("release_terminal_row") == "D5"
        and value.get("identity") == {
            "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
            "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
        }
        and value.get("input") == {
            "one_form_per_submission": True,
            "owner_physical_keyboard": True,
            "polling_during_persistent_form": False,
            "virtual_transport_forbidden": True,
        }
        and value["rows"]["D5"]["smokes_from"]
            == CONTRACT.relative_to(ROOT).as_posix()
        and contract["device"]["ceremony_frames"]["release_max"] == 72
        and len(contract["device"]["performance_smokes"]) == 4,
        "v1.5 D1-D5 session contract drift")
    return value


def facts(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    shared = MEDIA.check()
    build_id = product_build_id()
    library = library_facts(build_id)
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    require(
        shared["artifact_count"] == 19
        and shared["canonical_product"] == bind(CARD.MANIFEST)
        and pair["product_build_id"] == f"0x{build_id:08x}"
        and pair["index_rows"] == 4
        and pair["row_names"]
            == ["string-extra", "inspect", "place", "defstruct"],
        "v1.5 media readback or same-world pair red")
    return {"shared": shared, "library": library, "pair": pair}


def derive(*, configured: bool = False) -> dict[str, Any]:
    contract = session_contract()
    result = facts(configured=configured)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_links": 0, "qualification_replays": 0,
            "shared_system_builds": 1, "library_builds": 1,
            "media_readbacks": 1, "hardware_runs": 0,
        },
        "authority": {
            "product_card": bind(CARD.RECEIPT),
            "completion_resume": bind(RESUME),
            "product_manifest": bind(CARD.MANIFEST),
            "release_contract": bind(CONTRACT),
            "producer": bind(Path(__file__)),
        },
        "producer_source_gate": source_gate(),
        "producer_mutations_rejected": source_mutations(),
        "shared_system": {
            "artifact_count": result["shared"]["artifact_count"],
            "artifact_set_sha256": result["shared"]["artifact_set_sha256"],
            "manifest": bind(MANIFEST), "product_D81": bind(PRODUCT_D81),
            "work_D81": bind(WORK_D81), "readback": "passed",
        },
        "library": {**result["library"], "readback": "passed"},
        "pair_identity": result["pair"],
        "hardware_handoff": {
            "status": "prepared-not-run", "rows": list(contract["order"]),
            "session_contract": bind(SESSION),
            "owner_physical_keyboard": True,
            "polling_during_persistent_form": False,
        },
        "claim_limit": (
            "Host-closed v1.5 same-world product/library media and D1-D5 "
            "handoff only; no hardware, Halt, release or publication claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "qualification_replays": 0,
            "shared_system_builds": 1, "library_builds": 1,
            "media_readbacks": 1, "hardware_runs": 0,
        }
        and value.get("shared_system", {}).get("artifact_count") == 19
        and value.get("shared_system", {}).get("readback") == "passed"
        and value.get("library", {}).get("readback") == "passed"
        and value.get("pair_identity", {}).get("result") == "same-world-pair"
        and value.get("pair_identity", {}).get("index_rows") == 4
        and value.get("hardware_handoff", {}).get("rows")
            == ["D1", "D2", "D3", "D4", "D5"],
        "v1.5 media closure claim drift")
    if verify:
        require(value == derive(), "v1.5 media closure receipt is stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-qualification": lambda x: x["attempt_accounting"].update(
            qualification_replays=1),
        "claim-device": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "drop-role": lambda x: x["shared_system"].update(artifact_count=18),
        "skip-shared-readback": lambda x: x["shared_system"].update(
            readback="skipped"),
        "skip-library-readback": lambda x: x["library"].update(readback="skipped"),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "drop-library-row": lambda x: x["pair_identity"].update(index_rows=3),
        "reorder-session": lambda x: x["hardware_handoff"]["rows"].reverse(),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "v1.5 media receipt mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "v1.5 media closure is one-shot")
    session_contract(); source_gate(); source_mutations()
    configure()
    shared = MEDIA.build()
    require(shared["artifact_count"] == 19, "v1.5 shared role count drift")
    build_id = product_build_id()
    old = LIB.VARIANTS
    try:
        LIB.VARIANTS = VARIANTS
        LIB.build_library_variant("v1.5", LIBRARY, build_id)
    finally:
        LIB.VARIANTS = old
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 media build: PASS roles=19 rows=4 same-world")
    return 0


def fresh_readback() -> None:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "check"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, "v1.5 media fresh readback red:\n" + result.stdout)
    print(result.stdout.strip())


def check() -> int:
    value = load(RECEIPT); mutations = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(mutations == receipt_mutations(value),
            "v1.5 media receipt mutation set drift")
    print("v1.5 Link-97 media check: PASS roles=19 rows=4 same-world")
    return 0


def selftest() -> int:
    source_gate(); rejected = source_mutations(); session_contract()
    require(len(rejected) == 4, "v1.5 media source mutation count drift")
    print("v1.5 Link-97 media selftest: PASS mutations=4")
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
    except (MediaError, MEDIA.MediaError, LIB.MediaClosureError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.5 Link-97 media: FIRST RED: {error}")
        raise SystemExit(2)
