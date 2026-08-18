#!/usr/bin/env python3
"""Build/check Link-96 product and defstruct media for the guarded point row."""

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
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_terminal_return_guard_link96 as CARD  # noqa: E402
import c2_v112_candidate_media as LIB  # noqa: E402


PREDECESSOR_COMMIT = "3a0aba8e1b980a855eb0edde05c5862c430da968"
PREDECESSOR_BUILD = ROOT / "build/c2.3/terminal-return-guard-link96-media"
PREDECESSOR_DEVICE = ROOT / "build/c2.3/terminal-return-guard-link96-device-session"
BUILD = ROOT / "build/c2.3/terminal-return-guard-link96-media-r2"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "defstruct-library"
MANIFEST = SHARED / "candidate-manifest.json"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-receipt.json"
)
LIVE_BINDINGS_REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-live-bindings-rebind-receipt.json"
)
LIVE_BINDINGS_REBIND_R2 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-live-bindings-rebind-r2-receipt.json"
)
LIVE_BINDINGS_REBIND_R2_AUTHORITY = "bf195e3202c904810d6986df20bd8df762747fab"
LIVE_BINDINGS_REBIND_R3 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-live-bindings-rebind-r3-receipt.json"
)
LIVE_BINDINGS_REBIND_R3_AUTHORITY = "20a5f4ec"
V20_PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
V150_PLAN = ROOT / "docs/planning/v1.5.0-release-work-plan.md"
V21_PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-stager-path-first-red.json"
)
DEVICE_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-missing-place-device-first-red.json"
)
SESSION = ROOT / "config/c2-terminal-return-guard-link96-device-session.json"
RUNNER = ROOT / "scripts/c2-terminal-return-guard-link96-hw.sh"
RESULT_RECORDER = ROOT / "tools/host-lisp/c2_terminal_return_guard_device_result.py"
GATES = ROOT / "mk/gates.mk"
DEFSTRUCT_MANIFEST = ROOT / (
    "build/post-promotion/v110-performance/defstruct-candidate.manifest.json"
)
PLACE_MANIFEST = ROOT / (
    "build/post-promotion/defstruct-v1/foundations/place.manifest.json"
)
FORMAT = "lisp65-c2.3-link96-terminal-return-guard-media-v1"
STATUS = "LINK96-GUARDED-MEDIA-R2-GREEN; POINT-HARDWARE-ROW-READY"
BUILD_ID = 0x14D980C3
MUTATIONS = (
    "claim-product-link", "claim-hardware", "change-product-world",
    "change-library-world", "change-row-count", "skip-readback",
    "move-shadow-arena", "allow-virtual-input", "allow-active-polling",
    "drop-make-point", "claim-point", "drop-guard-authority",
    "drop-result-recorder", "drop-place-row", "change-defstruct-dependency",
    "drop-device-first-red",
)


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
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_bind(commit: str, path: str) -> dict[str, Any]:
    run = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(run.returncode == 0,
            run.stderr.decode(errors="replace") or "git authority absent")
    return {
        "authority": "git-blob", "commit": commit, "path": path,
        "bytes": len(run.stdout),
        "sha256": hashlib.sha256(run.stdout).hexdigest(),
    }


def configure() -> None:
    CARD.configure()
    CAN.MANIFEST = CARD.MANIFEST
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = CARD.MANIFEST
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def product_build_id() -> int:
    product = load(CARD.MANIFEST)
    value = int(product["static_plane"]["product_build_id"], 0)
    roles = {row["role"]: row for row in product["artifacts"]}
    c2d = (ROOT / roles["c2d-v6-code-plane"]["path"]).read_bytes()
    require(
        value == BUILD_ID and len(c2d) == MEDIA.C2D_PREFIX_BYTES
        and int.from_bytes(c2d[44:48], "little") == value,
        "Link-96 manifest/C2D world identity drift")
    return value


def build_defstruct_library(build_id: int) -> dict[str, Any]:
    old = LIB.VARIANTS
    old_mutations = LIB.resolver_contract_mutation_gate

    def complete_two_row_mutations(
        rows: list[dict[str, Any]], name: str,
    ) -> dict[str, str]:
        declared = LIB.declared_dependency_closure(rows, name)
        require(declared == [0, 1],
                "two-row dependency mutation fixture drift")
        rejected: dict[str, str] = {}
        for label, expected, actual in (
            ("undeclared-phantom-row-required", [0, 1, 2], None),
            ("declared-place-row-omitted", None, [1]),
        ):
            try:
                LIB.resolver_contract(
                    rows, name, expected_override=expected,
                    actual_override=actual)
            except LIB.MediaClosureError as error:
                rejected[label] = str(error)
            else:
                raise MediaError(
                    f"two-row resolver mutation survived: {label}")
        require(len(rejected) == 2,
                "two-row resolver mutation count drift")
        return rejected

    try:
        LIB.VARIANTS = {
            "guarded": (
                ("place", "place", "place", PLACE_MANIFEST, ()),
                ("defstruct", "defstruct", "dfstrct",
                 DEFSTRUCT_MANIFEST, (0,)),
            ),
        }
        LIB.resolver_contract_mutation_gate = complete_two_row_mutations
        return LIB.build_library_variant("guarded", LIBRARY, build_id)
    finally:
        LIB.VARIANTS = old
        LIB.resolver_contract_mutation_gate = old_mutations


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    rows = value.get("rows", [])
    require(
        value.get("format")
            == "lisp65-c2.3-link96-terminal-return-guard-device-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("link_authority") == {
            "path": RECEIPT.relative_to(ROOT).as_posix(), "status": STATUS}
        and value.get("identity", {}).get("product_medium")
            == PRODUCT_D81.relative_to(ROOT).as_posix()
        and value.get("identity", {}).get("library_medium")
            == LIBRARY_D81.relative_to(ROOT).as_posix()
        and value.get("input") == {
            "owner_physical_keyboard": True,
            "virtual_transport_forbidden": True,
            "one_form_per_submission": True,
            "polling_during_persistent_form": False,
        }
        and [row.get("id") for row in rows]
            == ["require-defstruct", "define-point", "make-point"]
        and [row.get("form") for row in rows] == [
            "(require (quote defstruct))", "(defstruct point x y)",
            "(make-point 3 4)"]
        and [row.get("quiet_floor_seconds") for row in rows]
            == [180, 240, 30]
        and rows[0].get("expect") == ["t"]
        and rows[1].get("expect") == ["t"]
        and rows[2].get("expect") == ["(point 3 4)"],
        "Link-96 guarded device contract drift")
    source = RUNNER.read_text(encoding="utf-8")
    require(
        "exec scripts/c2-trace-core-abi-link93-hw.sh" in source
        and "0x0000b582:0x0000b592" in source
        and "mega65_ftp" not in source
        and "capture-guard" in source,
        "Link-96 runner escaped the audited no-live-FTP choreography")
    require(
        "c2_terminal_return_guard_device_result.py record" in source,
        "Link-96 runner does not close the device result")
    return value


def predecessor_dependency_first_red() -> dict[str, Any]:
    old_library = PREDECESSOR_BUILD / "defstruct-library"
    artifact = old_library / "defstruct.l65s"
    index = old_library / "l65index"
    decoded = LIB.L65I.decode_index(
        index.read_bytes(), {"defstruct": artifact.read_bytes()},
        artifact_build_id=BUILD_ID)
    manifest = load(DEFSTRUCT_MANIFEST)
    require(
        manifest.get("name") == "defstruct"
        and manifest.get("requires") == ["place"]
        and decoded == [{
            "name": "defstruct", "track": 39, "sector": 0,
            "combined_crc32": 685635141, "dependencies": [],
            "execution_source": 2, "artifact_bytes": 2877,
            "bank2": 1031, "images": 1, "entries": 21,
            "resolutions": 86, "roots": 18, "scratch": 168,
        }],
        "predecessor missing-place evidence drift")
    require(
        (PREDECESSOR_DEVICE / "row-require-defstruct-passed").is_file()
        and not (PREDECESSOR_DEVICE / "row-define-point-passed").exists(),
        "predecessor device boundary drift")
    return {
        "format": "lisp65-c2.3-link96-missing-place-device-first-red-v1",
        "recorded_on": "2026-08-11",
        "status": "FIRST RED: defstruct dependency declared but not packed",
        "observation": {
            "require_form": "(require (quote defstruct))",
            "require_result": "t",
            "definition_form": "(defstruct point x y)",
            "owner_visible_result": "*** undefined function: %setf-register-begin",
            "result_latency": "immediate",
            "automated_device_access_after_error": 0,
        },
        "mechanism": {
            "manifest_declared_requires": ["place"],
            "packed_rows": ["defstruct"],
            "packed_defstruct_dependencies": [],
            "first_missing_callee": "%setf-register-begin",
            "owner": "lib/stdlib-places.lisp",
            "classification": "declared-dependency-omitted-from-medium",
        },
        "authorities": {
            "predecessor_media_receipt": git_bind(
                PREDECESSOR_COMMIT,
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-link96-terminal-return-guard-media-receipt.json"),
            "defstruct_manifest": bind(DEFSTRUCT_MANIFEST),
            "predecessor_index": bind(index),
            "predecessor_defstruct": bind(artifact),
            "predecessor_library_D81": bind(
                old_library / "lisp65-library.d81"),
            "require_screen_text": bind(
                PREDECESSOR_DEVICE / "row-require-defstruct.txt"),
            "require_screen_image": bind(
                PREDECESSOR_DEVICE / "row-require-defstruct.png"),
        },
        "attempt_accounting": {
            "product_links": 0, "hardware_contacts": 1,
            "physical_forms": 2, "monitor_accesses_after_error": 0,
        },
        "exonerations": {
            "terminal_return_guard_reached": False,
            "product_link_changed": False,
            "runtime_mechanism_claimed": False,
        },
        "repair": (
            "Pack place before defstruct and encode defstruct dependency [0] "
            "through the existing resolver contract; rebuild media only."),
        "claim_limit": (
            "One physical media-closure First Red. No return-guard, runtime, "
            "point, release or writer-attribution claim."),
    }


def dependency_closure() -> dict[str, Any]:
    artifacts = {
        "place": (LIBRARY / "place.l65s").read_bytes(),
        "defstruct": (LIBRARY / "defstruct.l65s").read_bytes(),
    }
    rows = LIB.L65I.decode_index(
        (LIBRARY / "l65index").read_bytes(), artifacts,
        artifact_build_id=BUILD_ID)
    contract = LIB.resolver_contract(rows, "defstruct")
    require(
        [row["name"] for row in rows] == ["place", "defstruct"]
        and [row["dependencies"] for row in rows] == [[], [0]]
        and contract["declared_dependency_closure"] == [0, 1]
        and contract["actual_resolver_order"] == [0, 1],
        "Link-96 place/defstruct dependency closure drift")
    return {
        "rows": ["place", "defstruct"],
        "dependency_ordinals": {"place": [], "defstruct": [0]},
        "requested": "defstruct", "resolver_order": ["place", "defstruct"],
        "mutations_rejected": 2,
    }


STAGER_LIVE_BINDINGS = {
    "build_dir": "BUILD",
    "stager": "STAGER",
    "stager_map": "STAGER_MAP",
    "compile_defines": "stager_compile_defines",
}


def stager_live_binding_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (MEDIA.__file__ and Path(MEDIA.__file__).read_text(encoding="utf-8"))
    if source_override is not None:
        source = source_override
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "compile_stager"]
    require(len(calls) == 1,
            "media stager producer must have one production compile_stager call")
    actual = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in calls[0].keywords if keyword.arg is not None
    }
    require(all(actual.get(name) == value
                for name, value in STAGER_LIVE_BINDINGS.items()),
            "media stager producer does not consume all live successor bindings")
    rejected_bindings = []
    if source_override is None:
        for name, value in STAGER_LIVE_BINDINGS.items():
            mutation = source.replace(
                f"{name}={value}", f"{name}=None", 1)
            require(mutation != source,
                    f"live-binding mutation did not alter source: {name}")
            try:
                stager_live_binding_gate(mutation)
            except MediaError:
                rejected_bindings.append(name)
        require(rejected_bindings == list(STAGER_LIVE_BINDINGS),
                "one or more missing stager live bindings survived")
    return {
        "status": "passed-semantic-live-successor-stager-bindings",
        "bindings": STAGER_LIVE_BINDINGS,
        "mutations_rejected": rejected_bindings,
    }


def live_bindings_rebind() -> dict[str, Any]:
    historical = load(RECEIPT)
    live = stager_live_binding_gate()
    return {
        "format": "lisp65-c2.3-link96-stager-live-bindings-rebind-v1",
        "recorded_on": "2026-08-11",
        "status": "PASS-SEMANTIC-LIVE-BINDINGS-REBIND",
        "authorization": "7f629631",
        "historical_receipt": bind(RECEIPT),
        "historical_receipt_rewritten": False,
        "historical_gate": historical["stager_live_binding_gate"],
        "successor_gate": live,
        "authority": {
            "checker": bind(Path(__file__).resolve()),
            "stager_producer": bind(Path(MEDIA.__file__).resolve()),
            "plan": bind(V150_PLAN),
        },
        "execution_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Semantic checker successor only; the sealed Link-96 receipt and "
            "all product and media artifacts remain unchanged."),
    }


def validate_live_bindings_rebind(value: dict[str, Any]) -> None:
    require(value == live_bindings_rebind(),
            "Link-96 live-bindings rebind receipt drift")


def live_bindings_rebind_r2() -> dict[str, Any]:
    predecessor = load(LIVE_BINDINGS_REBIND)
    live = stager_live_binding_gate()
    require(predecessor["successor_gate"] == live,
            "Link-96 semantic live bindings changed since predecessor rebind")
    approval = git_bind(
        LIVE_BINDINGS_REBIND_R2_AUTHORITY,
        V20_PLAN.relative_to(ROOT).as_posix())
    raw = subprocess.run(
        ["git", "show",
         f"{LIVE_BINDINGS_REBIND_R2_AUTHORITY}:{approval['path']}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False)
    require(
        raw.returncode == 0
        and b"unrelated Link-96 receipt drift receives the standard loud" in raw.stdout,
        "Link-96 r2 loud-rebind authorization absent")
    return {
        "format": "lisp65-c2.3-link96-stager-live-bindings-rebind-r2-v1",
        "recorded_on": "2026-08-12",
        "status": "PASS-LOUD-LINK96-AUTHORITY-REBIND-R2",
        "authorization": approval,
        "predecessor_rebind": bind(LIVE_BINDINGS_REBIND),
        "predecessor_rewritten": False,
        "semantic_gate": live,
        "authority": {
            "checker": bind(Path(__file__).resolve()),
            "stager_producer": bind(Path(MEDIA.__file__).resolve()),
            "live_plan": bind(V150_PLAN),
        },
        "execution_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Loud authority-only successor to the immutable Link-96 rebind; "
            "semantic bindings and all product/media bytes are unchanged."),
    }


def validate_live_bindings_rebind_r2(value: dict[str, Any]) -> None:
    current = live_bindings_rebind_r2()
    # stager_live_binding_gate() above parses the current real producer call
    # and proves all successor arguments plus their mutations.  Compare the
    # immutable rebind semantically instead of pinning either that whole
    # shared file or this checker's self-referential byte identity.
    value = deepcopy(value)
    current = deepcopy(current)
    for role in ("checker", "stager_producer"):
        historical_source = value["authority"][role]
        current_source = current["authority"][role]
        require(historical_source["path"] == current_source["path"],
                f"Link-96 {role} identity drift")
        value["authority"][role] = {"path": historical_source["path"]}
        current["authority"][role] = {"path": current_source["path"]}
    require(value == current,
            "Link-96 live-bindings r2 semantic revalidation drift")


def live_bindings_rebind_r3() -> dict[str, Any]:
    predecessor = load(LIVE_BINDINGS_REBIND_R2)
    live = stager_live_binding_gate()
    require(predecessor["semantic_gate"] == live,
            "Link-96 semantic bindings changed since r2")
    approval = git_bind(
        LIVE_BINDINGS_REBIND_R3_AUTHORITY,
        V21_PLAN.relative_to(ROOT).as_posix())
    raw = subprocess.run(
        ["git", "show",
         f"{LIVE_BINDINGS_REBIND_R3_AUTHORITY}:{approval['path']}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False)
    require(
        raw.returncode == 0
        and b"historical Link-96 live-plan drift gets its" in raw.stdout
        and b"authorized loud, dated rebind" in raw.stdout,
        "Link-96 r3 loud-rebind authorization absent")
    return {
        "format": "lisp65-c2.3-link96-stager-live-bindings-rebind-r3-v1",
        "recorded_on": "2026-08-16",
        "status": "PASS-LOUD-LINK96-AUTHORITY-REBIND-R3",
        "authorization": approval,
        "predecessor_rebind": bind(LIVE_BINDINGS_REBIND_R2),
        "predecessor_rewritten": False,
        "semantic_gate": live,
        "authority": {
            "checker": bind(Path(__file__).resolve()),
            "stager_producer": bind(Path(MEDIA.__file__).resolve()),
            "live_plan": bind(V150_PLAN),
        },
        "execution_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Loud authority-only successor to immutable r2; the semantic "
            "bindings and every historical product/media byte are unchanged."),
    }


def validate_live_bindings_rebind_r3(value: dict[str, Any]) -> None:
    current = live_bindings_rebind_r3()
    # The r3 receipt binds the newly authorized live-plan identity.  Source
    # identities remain semantic: checker/stager edits cannot rewrite history.
    value = deepcopy(value)
    current = deepcopy(current)
    for role in ("checker", "stager_producer"):
        historical_source = value["authority"][role]
        current_source = current["authority"][role]
        require(historical_source["path"] == current_source["path"],
                f"Link-96 r3 {role} identity drift")
        value["authority"][role] = {"path": historical_source["path"]}
        current["authority"][role] = {"path": current_source["path"]}
    require(value == current,
            "Link-96 live-bindings r3 semantic revalidation drift")


def project_historical_bindings(value: dict[str, Any],
                                historical: dict[str, Any]) -> None:
    value["stager_live_binding_gate"] = deepcopy(
        historical["stager_live_binding_gate"])
    value["authority"]["producer"] = deepcopy(
        historical["authority"]["producer"])
    value["authority"]["stager_producer"] = deepcopy(
        historical["authority"]["stager_producer"])


def facts() -> dict[str, Any]:
    configure()
    media = MEDIA.check()
    require(
        media["artifact_count"] == 19
        and media["canonical_product"] == bind(CARD.MANIFEST),
        "Link-96 shared-system media closure drift")
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    require(
        pair["product_build_id"] == f"0x{BUILD_ID:08x}"
        and pair["library_build_ids"] == {
            "place": f"0x{BUILD_ID:08x}",
            "defstruct": f"0x{BUILD_ID:08x}"}
        and pair["index_rows"] == 2
        and pair["row_names"] == ["place", "defstruct"],
        "Link-96 product/defstruct medium is not one world")
    require(
        PRODUCT_D81.read_bytes()
            == (PREDECESSOR_BUILD / "shared-system/lisp65-product.d81").read_bytes(),
        "Link-96 media-only repair changed the product D81")
    return {"media": media, "pair": pair,
            "dependency_closure": dependency_closure()}


def derive() -> dict[str, Any]:
    contract = session_contract()
    stager_gate = stager_live_binding_gate()
    card = load(CARD.RECEIPT)
    require(
        card.get("status") == "LINK96-HOST-GREEN; POINT-HARDWARE-ROW-PENDING"
        and card["attempt_accounting"]["product_closure_links"] == 1
        and card["attempt_accounting"]["hardware_runs"] == 0,
        "Link-96 guarded product authority drift")
    result = facts()
    library = {
        "D81": bind(LIBRARY_D81),
        "index": bind(LIBRARY / "l65index"),
        "place": bind(LIBRARY / "place.l65s"),
        "defstruct": bind(LIBRARY / "defstruct.l65s"),
    }
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "attempt_accounting": {
            "product_links": 0, "media_builds": 2,
            "prior_hardware_first_reds": 1, "hardware_green_runs": 0},
        "authority": {
            "media_stager_first_red": bind(FIRST_RED),
            "missing_place_device_first_red": bind(DEVICE_FIRST_RED),
            "product_card": bind(CARD.RECEIPT),
            "guard_gate": bind(CARD.GUARD_RECEIPT),
            "product_manifest": bind(CARD.MANIFEST),
            "producer": bind(Path(__file__).resolve()),
            "stager_producer": bind(Path(MEDIA.__file__).resolve()),
            "device_result_recorder": bind(RESULT_RECORDER),
        },
        "stager_live_binding_gate": stager_gate,
        "shared_system": {
            "artifact_count": result["media"]["artifact_count"],
            "artifact_set_sha256": result["media"]["artifact_set_sha256"],
            "manifest": bind(MANIFEST),
            "product_D81": bind(PRODUCT_D81),
            "work_D81": bind(SHARED / "lisp65-work.d81"),
            "predecessor_product_byteidentical": True,
        },
        "defstruct_library": {**library, "readback": "passed"},
        "pair_identity": result["pair"],
        "dependency_closure": result["dependency_closure"],
        "guard_readback": {
            "physical_range": "0x0000b582..0x0000b591",
            "arm_must_be_zero": True,
            "records": 4,
            "interpretation": (
                "all tags zero means clean; tag 1/2/3 carries live and "
                "shadow return-low/return-high/phase-owner bytes"),
        },
        "hardware_handoff": {
            "status": "prepared-not-run",
            "forms": [row["form"] for row in contract["rows"]],
            "expected": "(point 3 4)",
            "physical_owner_keyboard": True,
            "polling_during_persistent_form": False,
        },
        "session": {"contract": bind(SESSION), "runner": bind(RUNNER)},
        "mutation_contract": list(MUTATIONS),
        "claim_limit": (
            "Link-96 guarded product/defstruct media preparation only; no "
            "device, point, writer attribution, release or surface claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "media_builds": 2,
            "prior_hardware_first_reds": 1, "hardware_green_runs": 0}
        and value.get("authority", {}).get("guard_gate")
            == bind(CARD.GUARD_RECEIPT)
        and value.get("authority", {}).get("device_result_recorder")
            == bind(RESULT_RECORDER)
        and value.get("authority", {}).get("missing_place_device_first_red")
            == bind(DEVICE_FIRST_RED)
        and value.get("shared_system", {}).get("artifact_count") == 19
        and value.get("stager_live_binding_gate") == {
            "status": "passed-live-successor-stager-path-bindings",
            "mutations_rejected": 1}
        and value.get("defstruct_library", {}).get("readback") == "passed"
        and value.get("defstruct_library", {}).get("place")
            == bind(LIBRARY / "place.l65s")
        and value.get("defstruct_library", {}).get("defstruct")
            == bind(LIBRARY / "defstruct.l65s")
        and value.get("pair_identity", {}).get("product_build_id")
            == f"0x{BUILD_ID:08x}"
        and value.get("pair_identity", {}).get("library_build_ids")
            == {"place": f"0x{BUILD_ID:08x}",
                "defstruct": f"0x{BUILD_ID:08x}"}
        and value.get("pair_identity", {}).get("index_rows") == 2
        and value.get("dependency_closure") == {
            "rows": ["place", "defstruct"],
            "dependency_ordinals": {"place": [], "defstruct": [0]},
            "requested": "defstruct",
            "resolver_order": ["place", "defstruct"],
            "mutations_rejected": 2}
        and value.get("guard_readback", {}).get("physical_range")
            == "0x0000b582..0x0000b591"
        and value.get("hardware_handoff") == {
            "status": "prepared-not-run",
            "forms": ["(require (quote defstruct))",
                      "(defstruct point x y)", "(make-point 3 4)"],
            "expected": "(point 3 4)",
            "physical_owner_keyboard": True,
            "polling_during_persistent_form": False,
        }
        and value.get("mutation_contract") == list(MUTATIONS),
        "Link-96 guarded media claim drift")
    if verify:
        require(value == derive(), "Link-96 guarded media receipt is stale")


def rejected_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-product-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-hardware": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "change-product-world": lambda x: x["pair_identity"].update(product_build_id="0x00000000"),
        "change-library-world": lambda x: x["pair_identity"].update(library_build_ids={"defstruct": "0x00000000"}),
        "change-row-count": lambda x: x["pair_identity"].update(index_rows=1),
        "skip-readback": lambda x: x["defstruct_library"].update(readback="skipped"),
        "move-shadow-arena": lambda x: x["guard_readback"].update(physical_range="0x0000b583..0x0000b592"),
        "allow-virtual-input": lambda x: x["hardware_handoff"].update(physical_owner_keyboard=False),
        "allow-active-polling": lambda x: x["hardware_handoff"].update(polling_during_persistent_form=True),
        "drop-make-point": lambda x: x["hardware_handoff"]["forms"].pop(),
        "claim-point": lambda x: x["hardware_handoff"].update(status="passed"),
        "drop-guard-authority": lambda x: x["authority"].pop("guard_gate"),
        "drop-result-recorder": lambda x: x["authority"].pop(
            "device_result_recorder"),
        "drop-place-row": lambda x: x["dependency_closure"].update(
            rows=["defstruct"]),
        "change-defstruct-dependency": lambda x: x["dependency_closure"][
            "dependency_ordinals"].update(defstruct=[]),
        "drop-device-first-red": lambda x: x["authority"].pop(
            "missing_place_device_first_red"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(MUTATIONS), "Link-96 media mutation survived")
    return rejected


def gate_wiring() -> None:
    source = GATES.read_text(encoding="utf-8")
    require(all(token in source for token in (
        "c2-terminal-return-guard-media-selftest:",
        "c2_terminal_return_guard_media.py selftest",
        "c2-terminal-return-guard-media-check:",
        "c2_terminal_return_guard_media.py check",
        "check-source: c2-terminal-return-guard-media-check",
    )), "Link-96 media gate is not permanent")


def build_action() -> int:
    require(not BUILD.exists() and RECEIPT.exists()
            and DEVICE_FIRST_RED.exists(),
            "Link-96 guarded media-r2 build precondition drift")
    session_contract()
    stager_live_binding_gate()
    configure()
    media = MEDIA.build()
    require(media["artifact_count"] == 19,
            "Link-96 shared product medium role count drift")
    library = build_defstruct_library(product_build_id())
    require(
        library["index_mutations_rejected"] == 32
        and len(library["resolver_mutations_rejected"]) == 2,
        "Link-96 two-row place/defstruct library gate drift")
    print("Link-96 guarded media-r2 build: PASS product=19 library=2")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("record-first-red", "build", "record", "rebind",
                 "rebind-current", "rebind-r3", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record-first-red":
        value = predecessor_dependency_first_red()
        if DEVICE_FIRST_RED.exists():
            require(load(DEVICE_FIRST_RED) == value,
                    "Link-96 missing-place First Red drift")
        else:
            DEVICE_FIRST_RED.parent.mkdir(parents=True, exist_ok=True)
            DEVICE_FIRST_RED.write_bytes(canonical(value))
        print(f"Link-96 missing-place First Red: WROTE "
              f"{DEVICE_FIRST_RED.relative_to(ROOT)}")
        return 0
    if action == "build":
        return build_action()
    if action == "rebind":
        require(not LIVE_BINDINGS_REBIND.exists(),
                "Link-96 live-bindings rebind receipt already exists")
        value = live_bindings_rebind()
        LIVE_BINDINGS_REBIND.write_bytes(canonical(value))
        validate_live_bindings_rebind(value)
        print("Link-96 guarded media: PASS semantic live-bindings rebind "
              "mutations=4")
        return 0
    if action == "rebind-current":
        require(not LIVE_BINDINGS_REBIND_R2.exists(),
                "Link-96 live-bindings r2 rebind receipt already exists")
        value = live_bindings_rebind_r2()
        LIVE_BINDINGS_REBIND_R2.write_bytes(canonical(value))
        validate_live_bindings_rebind_r2(value)
        print("Link-96 guarded media: PASS loud authority rebind r2 "
              "semantic-bindings=4 mutations=4")
        return 0
    if action == "rebind-r3":
        require(not LIVE_BINDINGS_REBIND_R3.exists(),
                "Link-96 live-bindings r3 rebind receipt already exists")
        value = live_bindings_rebind_r3()
        LIVE_BINDINGS_REBIND_R3.write_bytes(canonical(value))
        validate_live_bindings_rebind_r3(value)
        print("Link-96 guarded media: PASS loud authority rebind r3 "
              "semantic-bindings=4 mutations=4")
        return 0
    if action == "record":
        value = derive()
        validate(value, verify=False)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"Link-96 guarded media: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    gate_wiring()
    value = load(RECEIPT)
    validate(value, verify=False)
    stager_live_binding_gate()
    if action == "check":
        require(LIVE_BINDINGS_REBIND.is_file(),
                "Link-96 live-bindings rebind receipt absent")
        require(LIVE_BINDINGS_REBIND_R2.is_file(),
                "Link-96 live-bindings r2 rebind receipt absent")
        require(LIVE_BINDINGS_REBIND_R3.is_file(),
                "Link-96 live-bindings r3 rebind receipt absent")
        validate_live_bindings_rebind_r3(load(LIVE_BINDINGS_REBIND_R3))
        current = derive()
        project_historical_bindings(current, value)
        require(current == value,
                "Link-96 historical media receipt differs after semantic projection")
    rejected = rejected_mutations(value)
    print(f"Link-96 guarded media {action}: PASS mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MediaError, MEDIA.MediaError, PAIR.ClosureError, LIB.MediaClosureError,
        RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(f"Link-96 guarded media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
