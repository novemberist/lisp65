#!/usr/bin/env python3
"""Build/check the Link-95 inspect medium as a product-world pair.

This successor deliberately leaves the historical Link-95 cross-world media
closure intact.  It recompiles inspect through the canonical library pipeline,
wraps that image with the Link-95 product build identity, and proves the pair
against the C2D.BIN actually visible on the product D81.  The old Link-93
library under the same Link-95 product is the permanent negative witness.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
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

import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_product_card as CARD  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import c2_session_extension_probe as S  # noqa: E402
import c2_trace_core_abi as TRACE  # noqa: E402
import evidence_era as ERA  # noqa: E402


BUILD = ROOT / "build/c2.3/packed-callee-link95-world-bound-media"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "trace-library"
READBACK = BUILD / "readback"
MANIFEST = SHARED / "candidate-manifest.json"
OLD_MEDIA = ROOT / "build/c2.3/packed-callee-link95-acceptance-media"
OLD_LIBRARY = OLD_MEDIA / "trace-library"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
INSPECT = LIBRARY / "inspect.l65s"
INDEX = LIBRARY / "l65index"
SOURCE_MANIFEST = TRACE.PREFIX.with_suffix(".manifest.json")
SOURCE_EXTENDED = TRACE.PREFIX.with_suffix(".ext.bin")
SOURCE_DISASSEMBLY = TRACE.PREFIX.with_suffix(".disasm.txt")
ATTRIBUTION_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-library-world-attribution-receipt.json"
)
HISTORICAL_MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-media-closure-receipt.json"
)
CROSSING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-live-repl-ftp-crossing-gate-receipt.json"
)
SISTER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-world-bound-media-closure-receipt.json"
)
SESSION_CONFIG = ROOT / (
    "config/c2-packed-callee-link95-world-bound-device-session.json"
)
SESSION_SCRIPT = ROOT / "scripts/c2-packed-callee-link95-world-bound-hw.sh"
BASE_SCRIPT = ROOT / "scripts/c2-trace-core-abi-link93-hw.sh"
GATES = ROOT / "mk/gates.mk"

FORMAT = "lisp65-c2.3-link95-world-bound-media-closure-v1"
STATUS = "LINK95-WORLD-BOUND-MEDIA-GREEN; HARDWARE-RECONTACT-READY"
RECORDED_ON = "2026-08-10"
SEALED_COMMIT = "61a861f14f1aeda8328fc5b4426202170ba56754"
LINK93_ID = 0x3B48650D
LINK95_ID = 0x14D980C3
EXPECTED_PRODUCT_D81 = (
    "b58d41997e8a2e78f8f79065029097b9bcb03d136cab202f01e2cc9b5c2f951d"
)
EXPECTED_OLD_LIBRARY = {
    "inspect.l65s": "c89c230fa647f8f90cf9c18845f7fe15d6eee9f9699227025f829c5c87416746",
    "l65index": "c5df5fa3ff650ccab7f84483f7d03e3e9b93f9090f64051e75054d9db707fdbe",
    "lisp65-library.d81": "5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd",
}
MUTATION_NAMES = (
    "accept-cross-world-link93-library",
    "change-product-world",
    "change-library-world",
    "require-predecessor-byteidentity",
    "claim-byte-patch-producer",
    "skip-readback",
    "change-readback-inspect",
    "change-library-medium",
    "change-product-medium",
    "change-index-row-count",
    "claim-product-link",
    "claim-hardware-run",
    "allow-virtual-input",
    "swap-session-order",
)


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def artifact_world(raw: bytes) -> int:
    require(len(raw) >= 26 and raw[:4] == b"L65S", "library envelope absent")
    return struct.unpack_from("<I", raw, 22)[0]


def product_world(product_d81: Path) -> tuple[int, bytes]:
    visible = L65I.D81.visible_files(product_d81.read_bytes())
    require(b"C2D.BIN" in visible, "product D81 lacks C2D.BIN")
    c2d = visible[b"C2D.BIN"]
    require(
        len(c2d) == MEDIA.C2D_RESET_DOMAIN_BYTES
        and c2d[:8] == b"C2D\0\x06\x30\x20\x0a",
        "mounted product C2D identity/extent drift",
    )
    return struct.unpack_from("<I", c2d, 44)[0], c2d


def pair_identity(product_d81: Path, library_d81: Path) -> dict[str, Any]:
    product_id, c2d = product_world(product_d81)
    visible = L65I.D81.visible_files(library_d81.read_bytes())
    require(b"L65INDEX" in visible, "library D81 lacks L65INDEX")
    artifacts = {
        name.decode("ascii").lower(): raw
        for name, raw in visible.items() if name != b"L65INDEX"
    }
    require(artifacts, "library D81 contains no artifacts")
    worlds = {name: artifact_world(raw) for name, raw in artifacts.items()}
    require(
        all(world == product_id for world in worlds.values()),
        "library/product world mismatch",
    )
    rows = L65I.decode_index(
        visible[b"L65INDEX"], artifacts, artifact_build_id=product_id
    )
    require(
        sorted(row["name"] for row in rows) == sorted(artifacts),
        "library index/artifact inventory mismatch",
    )
    return {
        "mounted_C2D_sha256": sha_bytes(c2d),
        "product_build_id": f"0x{product_id:08x}",
        "library_build_ids": {
            name: f"0x{world:08x}" for name, world in sorted(worlds.items())
        },
        "index_rows": len(rows),
        "row_names": [row["name"] for row in rows],
        "result": "same-world-pair",
    }


def configure_media() -> None:
    CARD.configure_card()
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


def build_library_d81(output: Path, index: Path, artifact: Path) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    command = [
        c1541, "-format", "L65LIB,65", "d81", str(output),
        "-write", str(artifact), "inspect",
        "-write", str(index), "l65index",
    ]
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, "library D81 build red:\n" + result.stdout)


def build_library() -> dict[str, Any]:
    compile_result = TRACE.build_library()
    require(
        compile_result["manifest"] == bind(SOURCE_MANIFEST)
        and compile_result["code_bytes"] == 558,
        "canonical inspect compilation drift",
    )
    LIBRARY.mkdir(parents=True)
    placeholder, artifact = FOUNDATION.measured_row(
        "inspect", "inspect", "inspect", SOURCE_MANIFEST, (), 1, 1,
        product_build_id=LINK95_ID,
    )
    INSPECT.write_bytes(artifact)
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(L65I.encode_index([placeholder]))
    seed_d81 = LIBRARY / "library.seed.d81"
    build_library_d81(seed_d81, seed_index, INSPECT)
    locators = L65I.d81_locators(seed_d81)
    require(locators.get("inspect") is not None, "inspect seed locator absent")
    row, final_artifact = FOUNDATION.measured_row(
        "inspect", "inspect", "inspect", SOURCE_MANIFEST, (),
        *locators["inspect"], product_build_id=LINK95_ID,
    )
    require(final_artifact == artifact, "locator changed inspect artifact bytes")
    INDEX.write_bytes(L65I.encode_index([row]))
    build_library_d81(LIBRARY_D81, INDEX, INSPECT)
    require(
        L65I.d81_locators(LIBRARY_D81) == locators,
        "final library locator drift",
    )
    visible = L65I.D81.visible_files(LIBRARY_D81.read_bytes())
    require(
        visible == {b"INSPECT": artifact, b"L65INDEX": INDEX.read_bytes()},
        "library D81 readback differs from generated inputs",
    )
    decoded = L65I.decode_index(
        INDEX.read_bytes(), {"inspect": artifact}, artifact_build_id=LINK95_ID
    )
    mutations = L65I.mutation_gate(
        INDEX.read_bytes(), {"inspect": artifact}, artifact_build_id=LINK95_ID
    )
    require(
        len(decoded) == 1 and decoded[0] == row and len(mutations) == 29
        and "one-row-unconditional-second-row-access" in mutations,
        "one-row Link-95 index closure drift",
    )
    READBACK.mkdir(parents=True)
    (READBACK / "inspect.l65s").write_bytes(visible[b"INSPECT"])
    (READBACK / "l65index").write_bytes(visible[b"L65INDEX"])
    seed_d81.unlink()
    seed_index.unlink()
    return {
        "compile": compile_result,
        "index_row": row,
        "index_mutations_rejected": len(mutations),
    }


def validate_session_contract() -> None:
    value = load(SESSION_CONFIG)
    rows = value.get("rows", [])
    expected_paths = {
        "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
        "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
        "library_index": INDEX.relative_to(ROOT).as_posix(),
        "library_source": INSPECT.relative_to(ROOT).as_posix(),
    }
    require(
        value.get("format")
            == "lisp65-c2.3-packed-callee-link95-world-bound-device-session-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("link_authority") == {
            "path": RECEIPT.relative_to(ROOT).as_posix(), "status": STATUS,
        }
        and all(value["identity"].get(key) == path
                for key, path in expected_paths.items())
        and value.get("input") == {
            "owner_physical_keyboard": True,
            "virtual_transport_forbidden": True,
            "one_form_per_submission": True,
        }
        and [row.get("id") for row in rows] == [
            "require-inspect", "define-probe", "install-trace",
            "traced-call", "remove-trace", "restored-call",
        ]
        and [row.get("form") for row in rows] == [
            "(require (quote inspect))",
            "(defun trace-probe (x) (+ x 1))",
            "(trace trace-probe)", "(trace-probe 4)",
            "(untrace trace-probe)", "(trace-probe 4)",
        ]
        and [row.get("quiet_floor_seconds") for row in rows]
            == [180, 180, 180, 30, 120, 30]
        and rows[3].get("expect_ordered") == [
            "(trace-enter trace-probe 4)",
            "(trace-exit trace-probe 5)", "5", "lisp65>",
        ]
        and rows[5].get("forbid") == ["trace-enter", "trace-exit"],
        "same-world session contract drift",
    )
    script = SESSION_SCRIPT.read_text(encoding="utf-8")
    require(
        "c2_link95_world_bound_media.py" in script
        and "c2-packed-callee-link95-world-bound-device-session.json" in script
        and "exec scripts/c2-trace-core-abi-link93-hw.sh" in script
        and "mega65_ftp" not in script and " m65 " not in script,
        "same-world wrapper does not delegate purely to audited base runner",
    )


def shared_facts() -> dict[str, Any]:
    configure_media()
    facts = MEDIA.check()
    require(
        facts["artifact_count"] == 19
        and facts["canonical_product"] == bind(CARD.MANIFEST)
        and sha(PRODUCT_D81) == EXPECTED_PRODUCT_D81,
        "same-world shared product closure drift",
    )
    return facts


def cross_world_rejection() -> dict[str, Any]:
    require(
        all(sha(OLD_LIBRARY / name) == digest
            for name, digest in EXPECTED_OLD_LIBRARY.items()),
        "historical Link-93 library authority drift",
    )
    try:
        pair_identity(PRODUCT_D81, OLD_LIBRARY / "lisp65-library.d81")
    except ClosureError as error:
        require(str(error) == "library/product world mismatch",
                "cross-world pair rejected for a different reason")
        return {
            "mutation": "Link-93-library-under-Link-95-product",
            "product_build_id": f"0x{LINK95_ID:08x}",
            "library_build_id": f"0x{LINK93_ID:08x}",
            "result": "rejected",
            "reason": str(error),
            "historical_library_D81": bind(
                OLD_LIBRARY / "lisp65-library.d81"),
        }
    raise ClosureError("cross-world Link-93 library was accepted")


def derive() -> dict[str, Any]:
    validate_session_contract()
    attribution = load(ATTRIBUTION_RECEIPT)
    require(
        attribution["attribution"]["first_divergent_edge"]
            == "L65S header offset 22 product-build-id guard",
        "world attribution authority drift",
    )
    historical = load(HISTORICAL_MEDIA_RECEIPT)
    require(
        historical.get("status")
            == "LINK95-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
        "historical cross-world media authority drift",
    )
    shared = shared_facts()
    pair = pair_identity(PRODUCT_D81, LIBRARY_D81)
    require(
        pair["product_build_id"] == f"0x{LINK95_ID:08x}"
        and pair["library_build_ids"] == {"inspect": f"0x{LINK95_ID:08x}"}
        and pair["index_rows"] == 1,
        "new product/library pair is not Link-95-complete",
    )
    old_artifact = (OLD_LIBRARY / "inspect.l65s").read_bytes()
    new_artifact = INSPECT.read_bytes()
    require(
        artifact_world(old_artifact) == LINK93_ID
        and artifact_world(new_artifact) == LINK95_ID
        and new_artifact[:22] == old_artifact[:22]
        and new_artifact[26:] == old_artifact[26:]
        and new_artifact != old_artifact,
        "canonical rebuild changed content beyond the world envelope",
    )
    decoded = L65I.decode_index(
        INDEX.read_bytes(), {"inspect": new_artifact},
        artifact_build_id=LINK95_ID,
    )
    readback = {
        "status": "passed",
        "inspect": bind(READBACK / "inspect.l65s"),
        "index": bind(READBACK / "l65index"),
        "library_D81_sha256": sha(LIBRARY_D81),
    }
    require(
        readback["inspect"]["sha256"] == sha(INSPECT)
        and readback["index"]["sha256"] == sha(INDEX),
        "library readback binding drift",
    )
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": STATUS,
        "authorization": "4c7b6977",
        "attempt_accounting": {
            "product_links": 0, "library_pipeline_builds": 1,
            "library_media_builds": 1, "hardware_runs": 0,
        },
        "authority": {
            "attribution": bind(ATTRIBUTION_RECEIPT),
            "historical_cross_world_media": bind(HISTORICAL_MEDIA_RECEIPT),
            "product_card": bind(CARD.RECEIPT),
            "product_manifest": bind(CARD.MANIFEST),
            "canonical_library_manifest": bind(SOURCE_MANIFEST),
            "canonical_library_extended_image": bind(SOURCE_EXTENDED),
            "canonical_library_disassembly": bind(SOURCE_DISASSEMBLY),
            "live_REPL_FTP_crossing_gate": bind(CROSSING_RECEIPT),
            "producer": bind(Path(__file__).resolve()),
        },
        "producer_contract": {
            "method": "canonical-bytecode-library-pipeline-plus-L65S-envelope",
            "byte_patch": False,
            "source_suite": TRACE.TRACE_SUITE.relative_to(ROOT).as_posix(),
            "predecessor_byteidentity_policy": "forbidden-as-acceptance-oracle",
            "content_comparison": {
                "equal_outside_world_id_offsets_22_through_25": True,
                "delivery_route": "independent-pipeline-rebuild",
            },
        },
        "shared_system": {
            "artifact_count": shared["artifact_count"],
            "artifact_set_sha256": shared["artifact_set_sha256"],
            "manifest": bind(MANIFEST),
            "product_D81": bind(PRODUCT_D81),
            "work_D81": bind(SHARED / "lisp65-work.d81"),
        },
        "trace_library": {
            "inspect": bind(INSPECT),
            "index": bind(INDEX),
            "library_D81": bind(LIBRARY_D81),
            "index_row": decoded[0],
            "index_mutations_rejected": 29,
            "readback": readback,
        },
        "pair_identity": pair,
        "cross_world_negative_witness": cross_world_rejection(),
        "mutation_contract": list(MUTATION_NAMES),
        "hardware_handoff": {
            "status": "prepared-not-run",
            "trace_rows": 6,
            "physical_owner_keyboard": True,
            "persistent_by_default": True,
            "bundled_defstruct_sister": True,
        },
        "bundled_session": {
            "trace_contract": bind(SESSION_CONFIG),
            "trace_runner": bind(SESSION_SCRIPT),
            "trace_runner_base": bind(BASE_SCRIPT),
            "defstruct_sister_receipt": bind(SISTER_RECEIPT),
            "order": [
                "Link95-same-world-trace-acceptance",
                "Link92-defstruct-terminal-ingress-sister",
                "standing-trailing-peeks",
            ],
        },
        "claim_limit": (
            "Same-world Link-95 library/media and bundled-session preparation "
            "only; no hardware, release, publication, trace-result, "
            "defstruct-result, parity or Link-91 claim."
        ),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "library_pipeline_builds": 1,
            "library_media_builds": 1, "hardware_runs": 0,
        }
        and value["producer_contract"]["method"]
            == "canonical-bytecode-library-pipeline-plus-L65S-envelope"
        and value["producer_contract"]["byte_patch"] is False
        and value["producer_contract"]["predecessor_byteidentity_policy"]
            == "forbidden-as-acceptance-oracle"
        and value["producer_contract"]["content_comparison"] == {
            "equal_outside_world_id_offsets_22_through_25": True,
            "delivery_route": "independent-pipeline-rebuild",
        }
        and value["shared_system"]["artifact_count"] == 19
        and value["shared_system"]["product_D81"]["sha256"]
            == EXPECTED_PRODUCT_D81
        and value["pair_identity"]["product_build_id"]
            == f"0x{LINK95_ID:08x}"
        and value["pair_identity"]["library_build_ids"]
            == {"inspect": f"0x{LINK95_ID:08x}"}
        and value["pair_identity"]["index_rows"] == 1
        and value["pair_identity"]["result"] == "same-world-pair"
        and value["cross_world_negative_witness"]["result"] == "rejected"
        and value["cross_world_negative_witness"]["reason"]
            == "library/product world mismatch"
        and value["cross_world_negative_witness"]["library_build_id"]
            == f"0x{LINK93_ID:08x}"
        and value["trace_library"]["index_mutations_rejected"] == 29
        and value["trace_library"]["readback"]["status"] == "passed"
        and value["trace_library"]["inspect"]["sha256"]
            == value["trace_library"]["readback"]["inspect"]["sha256"]
        and value["trace_library"]["index"]["sha256"]
            == value["trace_library"]["readback"]["index"]["sha256"]
        and value["trace_library"]["library_D81"]["sha256"]
            == value["trace_library"]["readback"]["library_D81_sha256"]
        and value["trace_library"]["index_row"]["name"] == "inspect"
        and value["mutation_contract"] == list(MUTATION_NAMES)
        and value["hardware_handoff"] == {
            "status": "prepared-not-run", "trace_rows": 6,
            "physical_owner_keyboard": True, "persistent_by_default": True,
            "bundled_defstruct_sister": True,
        }
        and value["bundled_session"]["order"] == [
            "Link95-same-world-trace-acceptance",
            "Link92-defstruct-terminal-ingress-sister",
            "standing-trailing-peeks",
        ],
        "Link-95 same-world media claim drift",
    )
    if verify:
        # The same-world media receipt is sealed Link-95 evidence.  Calling
        # derive() here would call configure_media(), which restores historical
        # IDE/buffer inputs into the shared live build paths.  Bind the emitted
        # product, library and session artifacts without materializing that
        # historical producer world.
        require(RECEIPT.read_bytes() == ERA.era_blob(
            SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
            "sealed Link-95 same-world receipt was rewritten")
        rows = [
            value["authority"]["attribution"],
            value["authority"]["historical_cross_world_media"],
            value["authority"]["product_card"],
            value["authority"]["product_manifest"],
            value["authority"]["live_REPL_FTP_crossing_gate"],
            value["shared_system"]["manifest"],
            value["shared_system"]["product_D81"],
            value["shared_system"]["work_D81"],
            value["trace_library"]["inspect"],
            value["trace_library"]["index"],
            value["trace_library"]["library_D81"],
            value["trace_library"]["readback"]["inspect"],
            value["trace_library"]["readback"]["index"],
            value["cross_world_negative_witness"]["historical_library_D81"],
            value["bundled_session"]["trace_contract"],
            value["bundled_session"]["trace_runner"],
            value["bundled_session"]["trace_runner_base"],
            value["bundled_session"]["defstruct_sister_receipt"],
        ]
        require(all(bind(ROOT / row["path"]) == row for row in rows),
                "Link-95 sealed same-world artifact drift")


def sealed_check_source_gate(source_override: str | None = None) -> None:
    source = Path(__file__).read_text(encoding="utf-8") \
        if source_override is None else source_override
    tree = ast.parse(source)
    validate_node = next((node for node in tree.body
                          if isinstance(node, ast.FunctionDef)
                          and node.name == "validate"), None)
    require(validate_node is not None, "Link-95 same-world validator absent")
    calls = [ast.unparse(node.func) for node in ast.walk(validate_node)
             if isinstance(node, ast.Call)]
    require("derive" not in calls and "configure_media" not in calls
            and "bind" in calls,
            "same-world media check can materialize historical inputs")


def sealed_check_source_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    anchor = 'bind(ROOT / row["path"])'
    # One executable binding plus this mutation literal.
    require(source.count(anchor) == 2,
            "sealed same-world source mutation anchor drift")
    cases = {
        "restore-live-derive": source.replace(anchor, "derive()", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            sealed_check_source_gate(candidate)
        except ClosureError:
            rejected.append(name)
    require(rejected == list(cases),
            "sealed same-world source mutation survived")
    return rejected


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "accept-cross-world-link93-library": lambda x: x[
            "cross_world_negative_witness"].update(result="accepted"),
        "change-product-world": lambda x: x["pair_identity"].update(
            product_build_id=f"0x{LINK93_ID:08x}"),
        "change-library-world": lambda x: x["pair_identity"].update(
            library_build_ids={"inspect": f"0x{LINK93_ID:08x}"}),
        "require-predecessor-byteidentity": lambda x: x[
            "producer_contract"].update(
                predecessor_byteidentity_policy="required"),
        "claim-byte-patch-producer": lambda x: x["producer_contract"].update(
            byte_patch=True),
        "skip-readback": lambda x: x["trace_library"]["readback"].update(
            status="skipped"),
        "change-readback-inspect": lambda x: x["trace_library"][
            "readback"]["inspect"].update(sha256="00" * 32),
        "change-library-medium": lambda x: x["trace_library"][
            "library_D81"].update(sha256="00" * 32),
        "change-product-medium": lambda x: x["shared_system"][
            "product_D81"].update(sha256="00" * 32),
        "change-index-row-count": lambda x: x["pair_identity"].update(
            index_rows=2),
        "claim-product-link": lambda x: x["attempt_accounting"].update(
            product_links=1),
        "claim-hardware-run": lambda x: x["attempt_accounting"].update(
            hardware_runs=1),
        "allow-virtual-input": lambda x: x["hardware_handoff"].update(
            physical_owner_keyboard=False),
        "swap-session-order": lambda x: x["bundled_session"]["order"].reverse(),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except ClosureError:
            rejected.append(name)
    require(rejected == list(MUTATION_NAMES),
            "same-world pair-identity mutation survived")
    return rejected


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-link95-world-bound-media-selftest:",
        "c2_link95_world_bound_media.py selftest",
        "c2-link95-world-bound-media-check:",
        "c2_link95_world_bound_media.py check",
        "check-source: c2-link95-world-bound-media-check",
    )), "same-world media gate wiring absent")


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-95 same-world media build is one-shot")
    validate_session_contract()
    # Re-run the canonical media producer against the sealed Link-95 product.
    # Copying the old directory would retain path-bearing reset-domain proof
    # bindings and would therefore not constitute a real closure rebuild.
    configure_media()
    media = MEDIA.build()
    require(media["artifact_count"] == 19,
            "rebuilt shared-system role count drift")
    build_library()
    pair = pair_identity(PRODUCT_D81, LIBRARY_D81)
    require(pair["product_build_id"] == f"0x{LINK95_ID:08x}",
            "built pair did not converge on Link 95")
    print("Link-95 same-world media build: PASS " + json.dumps(
        {"pair": pair, "product_D81": bind(PRODUCT_D81),
         "library_D81": bind(LIBRARY_D81)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "build":
        return build_action()
    if action == "record":
        value = derive()
        validate(value, verify=False)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"Link-95 same-world media: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    sealed_check_source_gate()
    source_mutations = sealed_check_source_mutations()
    validate(value, verify=(action == "check"))
    rejected = rejected_mutations(value)
    print(
        f"Link-95 same-world media {action}: PASS "
        f"mutations={len(rejected)}+{len(source_mutations)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ClosureError, FOUNDATION.FoundationError, L65I.GateError,
        S.ProbeError, MEDIA.MediaError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(f"Link-95 same-world media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
