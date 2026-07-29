#!/usr/bin/env python3
"""Rebind Link-75 defstruct media to the linked product envelope.

The historical foundation artifacts predate both the current product build
identity and the fixed SESS record identity.  This successor re-emits only the
two L65S envelopes through the canonical generator, keeps their code/C2I
payloads and the L65I index byte-identical, rebuilds the D81, and binds a new
hardware deployment without creating a product link.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
FOUNDATIONS = ROOT / "build/post-promotion/defstruct-v1/foundations"
SESSION = BASE / "bundled-completion-session"
PREDECESSOR_DEPLOYMENT = (
    SESSION / "reset-domain-successor/product-phase-deployment.json")
BUILD = SESSION / "library-media-successor"
DEPLOYMENT = BUILD / "product-phase-deployment.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_C2D = BASE / (
    "final/fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
CURRENT_STATE = SESSION / (
    "hardware-symbol-read-session-v2/retry-valid-reset-first-red-state")
SCREEN = SESSION / (
    "hardware-symbol-read-session-v2/retry-require-first.txt")
ZERO_C2J = ROOT / "build/c2.2/destructive-restage-link57/zero-c2j.bin"
LINK72_MEDIA = ROOT / (
    "build/post-promotion/link71-defstruct-session-record-identity-rebind/"
    "require-defstruct-sess-bound.d81")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-valid-reset-library-envelope-hardware-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-library-media-successor-receipt.json")


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
    )


def product_build_id() -> int:
    profile = load(PROFILE)
    result = int(profile["product_build_id"], 0)
    c2d = STATIC_C2D.read_bytes()
    require(
        len(c2d) == 33840
        and int.from_bytes(c2d[44:48], "little") == result,
        "profile and linked C2D product identities diverge",
    )
    return result


def manifest_rows() -> tuple[tuple[Any, ...], ...]:
    return (
        (
            "place", "place", "place",
            FOUNDATIONS / "place.manifest.json", (),
        ),
        (
            "defstruct", "defstruct", "dfstrct",
            FOUNDATIONS / "defstruct.manifest.json", (0,),
        ),
    )


def expected_artifacts(
    build_id: int, locators: dict[str, tuple[int, int]],
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    artifacts: dict[str, bytes] = {}
    rows = []
    for name, image_key, shelf_name, manifest, dependencies in manifest_rows():
        require(name in locators, f"missing D81 locator: {name}")
        track, sector = locators[name]
        row, artifact = FOUNDATION.measured_row(
            name, image_key, shelf_name, manifest, dependencies,
            track, sector, product_build_id=build_id,
        )
        require(
            artifact[32:40] == L65I.S.SESSION_RECORD_ID,
            f"{name} canonical generator did not emit SESS",
        )
        L65I.S.decode_extension(
            artifact, expected_build_id=build_id)
        artifacts[name] = artifact
        rows.append(row)
    return artifacts, rows


def stale_media_truth(build_id: int) -> dict[str, Any]:
    stale = {
        name: (FOUNDATIONS / f"{name}.l65s").read_bytes()
        for name, *_rest in manifest_rows()
    }
    result = {}
    for name, data in stale.items():
        stale_id = struct.unpack_from("<I", data, 22)[0]
        record_identity = data[32:40]
        require(
            stale_id != build_id
            and record_identity != L65I.S.SESSION_RECORD_ID,
            f"{name} no longer exhibits the bound-media First Red",
        )
        try:
            L65I.S.decode_extension(
                data, expected_build_id=build_id)
        except L65I.S.ProbeError as error:
            rejection = str(error)
        else:
            raise SuccessorError(
                f"stale {name} survived current product-envelope decode")
        result[name] = {
            "binding": bind(FOUNDATIONS / f"{name}.l65s"),
            "product_build_id": f"0x{stale_id:08x}",
            "record_identity_hex": record_identity.hex(),
            "current_decoder_rejection": rejection,
        }
    return result


def hardware_first_red(stale: dict[str, Any], build_id: int) -> dict[str, Any]:
    phase = [
        (CURRENT_STATE / f"phase-scratch-{index}.bin").read_bytes()
        for index in range(1, 4)
    ]
    c2j = [
        (CURRENT_STATE / f"c2j-{index}.bin").read_bytes()
        for index in range(1, 4)
    ]
    require(
        phase[0] == phase[1] == phase[2]
        and c2j[0] == c2j[1] == c2j[2] == ZERO_C2J.read_bytes(),
        "valid-reset First-Red captures are not time-stable/clean",
    )
    require(
        int.from_bytes(phase[0][50:52], "little") == 1925
        and phase[0][302:304] == bytes((39, 0)),
        "valid-reset First-Red phase witness drift",
    )
    screen = SCREEN.read_text(encoding="utf-8")
    require("*** vm: bad bytecode" in screen,
            "valid-reset First-Red screen drift")
    value = {
        "format":
            "lisp65-c2.2-link75-valid-reset-library-envelope-first-red-v1",
        "recorded_on": "2026-07-28",
        "status":
            "FIRST RED-attributed-stale-library-envelope-before-C2J",
        "hardware": {
            "result": "*** vm: bad bytecode",
            "requested_library": "defstruct",
            "failing_dependency": "place",
            "mounted_artifact_bytes": 1925,
            "complete_reset_domain_preverified": True,
            "C2J_before": "64 zero bytes",
            "C2J_after_three_captures": "64 zero bytes",
            "rollback_restored_header": True,
            "phase_capture_count": 3,
            "screen": bind(SCREEN),
            "phase_scratch": bind(
                CURRENT_STATE / "phase-scratch-1.bin"),
            "C2J": bind(CURRENT_STATE / "c2j-1.bin"),
            "bank5": bind(CURRENT_STATE / "bank5-current.bin"),
        },
        "attribution": {
            "linked_product_build_id": f"0x{build_id:08x}",
            "linked_record_identity": "SESS",
            "bound_media": stale,
            "mechanism": (
                "c2_append_envelope_phase rejects each bound L65S before "
                "C2J because its product build identity is stale; its "
                "record-local name also violates the fixed SESS identity."
            ),
            "historical_Link72_green_is_not_same_input": bind(LINK72_MEDIA),
            "slot39_limit": (
                "The final Slot-39 stamp is rollback provenance. It is not "
                "used as primary failure attribution."
            ),
        },
        "execution_accounting": {
            "new_product_links": 0,
            "product_bytes_changed": 0,
            "automatic_retries": 0,
        },
        "next":
            "Re-emit the two L65S envelopes against Link75, keep code/C2I "
            "and L65I fixed, rebuild the D81, then request one hardware retry.",
    }
    return value


def build_successor() -> dict[str, Any]:
    build_id = product_build_id()
    predecessor = load(PREDECESSOR_DEPLOYMENT)
    old_media = Path(ROOT / predecessor["media"]["path"])
    require(
        old_media.resolve()
            == (FOUNDATIONS / "require-defstruct.d81").resolve(),
        "predecessor deployment media authority drift",
    )
    old_bytes = old_media.read_bytes()
    locators = L65I.d81_locators(old_media)
    stale = stale_media_truth(build_id)
    first_red = hardware_first_red(stale, build_id)
    artifacts, rows = expected_artifacts(build_id, locators)

    BUILD.mkdir(parents=True, exist_ok=True)
    paths = []
    deltas: dict[str, list[int]] = {}
    for name, data in artifacts.items():
        old = (FOUNDATIONS / f"{name}.l65s").read_bytes()
        delta = [
            index for index, (before, after) in enumerate(zip(old, data))
            if before != after
        ]
        require(
            len(old) == len(data)
            and data[64:] == old[64:]
            and set(delta) <= (
                set(range(18, 26)) | set(range(32, 40))
            ),
            f"{name} changed outside envelope identity/catalog fields",
        )
        path = BUILD / f"{name}.l65s"
        write_bytes(path, data)
        paths.append((path, name))
        deltas[name] = delta

    old_index = FOUNDATIONS / "l65index"
    index_data = old_index.read_bytes()
    require(
        L65I.encode_index(rows) == index_data,
        "L65I changed while record-local identity was repaired",
    )
    index = BUILD / "l65index"
    write_bytes(index, index_data)
    decoded = L65I.decode_index(
        index_data, artifacts, artifact_build_id=build_id)
    require(
        L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY)
            == [0, 1],
        "successor dependency resolution drift",
    )
    mutations = L65I.mutation_gate(
        index_data, artifacts, artifact_build_id=build_id)

    d81 = BUILD / "require-defstruct-link75-bound.d81"
    L65I.build_d81(d81, index, paths)
    require(
        L65I.d81_locators(d81) == locators,
        "successor D81 locator drift",
    )
    visible = L65I.D81.visible_files(d81.read_bytes())
    require(
        visible[b"L65INDEX"] == index_data
        and visible[b"PLACE"] == artifacts["place"]
        and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
        "successor D81 visible-file truth drift",
    )
    changed = [
        offset for offset, (before, after)
        in enumerate(zip(old_bytes, d81.read_bytes()))
        if before != after
    ]
    require(
        len(old_bytes) == d81.stat().st_size
        and len(changed) == sum(len(row) for row in deltas.values()),
        "successor D81 changed outside the two L65S envelopes",
    )

    deployment = deepcopy(predecessor)
    deployment["format"] = (
        "lisp65-c2.2-link75-library-media-successor-deployment-v1")
    deployment["status"] = (
        "ready-product-phase-after-library-envelope-rebind")
    deployment["media"] = bind(d81)
    deployment["media"]["role"] = "Link75-bound-L65I-v1-library-media"
    deployment["execution_accounting"] = {
        "new_product_links": 0,
        "product_bytes_changed": 0,
        "hardware_runs": 0,
    }

    write_json(FIRST_RED, first_red)
    receipt = {
        "format": "lisp65-c2.2-link75-library-media-successor-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-Link75-product-bound-SESS-media-no-product-link",
        "correction": {
            "product_build_id": f"0x{build_id:08x}",
            "record_identity": "SESS",
            "library_name_authority": "L65I-v1 only",
            "artifact_deltas": deltas,
            "code_and_C2I": "byte-identical",
            "combined_CRC32": "byte-identical",
            "catalog_CRC32": "recomputed over final SESS record",
            "L65I": "byte-identical",
            "D81_changed_bytes": changed,
        },
        "bound_media_gate": {
            "canonical_generator_replayed": True,
            "actual_D81_visible_files_compared": True,
            "linked_product_identity_compared": True,
            "linked_record_identity_compared": True,
            "index_mutations_rejected": len(mutations),
            "stale_media_rejected": sorted(stale),
        },
        "artifacts": {
            "index": bind(index),
            "place": bind(BUILD / "place.l65s"),
            "defstruct": bind(BUILD / "defstruct.l65s"),
            "D81": bind(d81),
        },
        "execution_accounting": {
            "new_product_links": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "profile": bind(PROFILE),
            "linked_C2D": bind(STATIC_C2D),
            "predecessor_deployment": bind(PREDECESSOR_DEPLOYMENT),
            "hardware_First_Red": bind(FIRST_RED),
            "canonical_emitter":
                bind(ROOT / "tools/host-lisp/c2_session_extension_probe.py"),
            "driver": bind(Path(__file__).resolve()),
        },
        "next":
            "Upload/readback the successor D81, deploy the unchanged Link75 "
            "product under the qualified full-reset contract, mount, and "
            "rerun require-first once.",
        "claim_limit":
            "Host/media successor only. No new product link and no hardware "
            "require/defstruct claim.",
    }
    # The receipt must exist before its binding is embedded in the deployment.
    write_json(RECEIPT, receipt)
    deployment["authority"]["library_media_successor"] = bind(RECEIPT)
    write_json(DEPLOYMENT, deployment)
    return receipt


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    build_id = product_build_id()
    d81 = BUILD / "require-defstruct-link75-bound.d81"
    locators = L65I.d81_locators(d81)
    artifacts, rows = expected_artifacts(build_id, locators)
    require(
        receipt["status"]
            == "passed-Link75-product-bound-SESS-media-no-product-link"
        and deployment["media"] == {
            **bind(d81), "role": "Link75-bound-L65I-v1-library-media"}
        and (BUILD / "place.l65s").read_bytes() == artifacts["place"]
        and (BUILD / "defstruct.l65s").read_bytes()
            == artifacts["defstruct"]
        and (BUILD / "l65index").read_bytes() == L65I.encode_index(rows),
        "Link75 library-media successor drift",
    )
    visible = L65I.D81.visible_files(d81.read_bytes())
    require(
        visible[b"PLACE"] == artifacts["place"]
        and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
        "bound successor D81 differs from canonical re-emission",
    )
    return {
        "status": "verified",
        "product_build_id": f"0x{build_id:08x}",
        "record_identity": "SESS",
        "D81": bind(d81),
        "product_links": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    args = parser.parse_args()
    try:
        value = build_successor() if args.action == "prepare" else verify()
        print(
            "c2-link75-library-media-successor: PASS "
            f"action={args.action} product-links=0")
        if args.action == "verify":
            print(json.dumps(value, sort_keys=True))
        return 0
    except (
        OSError, ValueError, KeyError, json.JSONDecodeError, SuccessorError,
        FOUNDATION.FoundationError, L65I.GateError, L65I.S.ProbeError,
    ) as error:
        print(
            "c2-link75-library-media-successor: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
