#!/usr/bin/env python3
"""Pack artifact-only `$22` media from the qualified r4 build-ID successor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v200_symbol22_build_id_rebind as R4  # noqa: E402
import c2_v200_symbol22_first_fault_device_media as BASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — phase-0 r4 closure and device-session authority — 2026-08-31")
CARD_RECEIPT = R4.RECEIPT
CARD_BUILD = R4.BUILD
SOURCE_WPLTO = R4.COMPLETION
SEED_WPLTO = R4.BUILD / "wplto"
SOURCE_STATIC = R4.CARD.RELEASE_PLANE_ROOT
BUILD = ROOT / "build/c2.3/v2.0-symbol22-build-id-device-media"
WPLTO = BUILD / "inputs/wplto"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "library"
RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-build-id-device-media-receipt.json")
SESSION = ROOT / "config/c2-v200-symbol22-build-id-device-session.json"
SCOPE = R4.COMPLETION / "owner-scope-result.json"
ACCEPTANCE = R4.COMPLETION / "artifact-acceptance.json"
PRODUCT_REMOTE = "V20S22P4.D81"
LIBRARY_REMOTE = "V20S22L4.D81"
PRODUCT_ID = 0x8C6CC520
PLANE_BYTES = 47469
EXPECTED = {
    "PRG": (41811,
        "dc8c44e403866ff4b9d4acdb158c6d2dae068cddb94b3e2c9598f37c40032c79"),
    "ELF": (636112,
        "21733ddc170f7c9ceba60d7e2e351932248435e9fb9266394d908febc721e04b"),
}
STATUS = "PASS: V2.0 SYMBOL22 BUILD-ID DEVICE MEDIA READY"
FORMAT = "lisp65-c2-v200-symbol22-build-id-device-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-symbol22-build-id-device-session-v1"


ORIGINAL_PRODUCT_MANIFEST = BASE.product_manifest
ORIGINAL_FINISH = BASE.finish
ORIGINAL_SESSION_CONFIG = BASE.session_config


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.MediaError(message)


def load(path: Path) -> dict[str, Any]:
    return BASE.load(path)


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(R4.PRG), "ELF": bind(R4.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"r4 {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt, scope, acceptance = (load(CARD_RECEIPT), load(SCOPE),
                                  load(ACCEPTANCE))
    pair = accepted_pair()
    require(receipt["status"] == R4.STATUS
            and receipt["artifacts_before"] == receipt["artifacts_after"]
            and {name: receipt["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == pair
            and receipt["accounting"] == {
                "device_contacts": 0, "media_builds": 0,
                "new_WPLTOs": 0, "new_product_links": 1,
                "product_links_total": 3, "seed_WPLTOs": 1}
            and scope["status"] == acceptance["status"] == "PASS",
            "r4 closure is not device-media ready")
    return {
        "independent_review": BASE.section_authority(),
        "product_card": bind(CARD_RECEIPT),
        "authority_prelink": bind(R4.PRELINK_RECEIPT),
        "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE),
        "right": ("artifact-only r4 product media, current-plane external "
                  "library and the still-unspent bounded contact"),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "product_cards": 0, "device_contacts": 0},
    }


def read_ranges() -> list[dict[str, Any]]:
    truth = ElfTruth.read(R4.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    state = truth.symbol("lisp65_symbol22_latch_state").value
    payload = truth.symbol("c2_symbol22_repl_buf").value
    nsym = truth.symbol("nsym").value
    npool = truth.symbol("npool").value
    require((state, payload, nsym, npool) == (0xC34D, 0xBC89, 0x005A, 0xBE1A),
            "r4 stopped-state read cutpoint drift")
    return [
        {"name": "latch-state", "address": f"0x{state:04X}", "bytes": 5,
         "layout": ["tag", "caller-lo", "caller-hi", "name-lo", "name-hi"]},
        {"name": "repl.buf-payload", "address": f"0x{payload:04X}",
         "bytes": 34, "layout": "name bytes, NUL-stopped"},
        {"name": "nsym", "address": f"0x{nsym:04X}", "bytes": 2,
         "encoding": "little-endian"},
        {"name": "npool", "address": f"0x{npool:04X}", "bytes": 2,
         "encoding": "little-endian"},
    ]


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = ORIGINAL_PRODUCT_MANIFEST(completion)
    value["static_plane"]["status"] = (
        "passed-v2.0-symbol22-r4-build-id-static-plane")
    value["static_plane"]["membership_authority"] = (
        "r4 final-ELF composed ownership over the unchanged 47,469-byte plane")
    BASE.MEDIA.CAN.MANIFEST.write_bytes(BASE.canonical(value))
    BASE.MEDIA.CAN.check()
    return value


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] ==
                "passed-v2.0-symbol22-r4-build-id-static-plane"
            and plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and owners[0]["bytes"] == PLANE_BYTES
            and plane["largest_contiguous_hole"]["bytes"] == 16197
            and any(item["owner"] == "mapped-tenant-congruence-gap"
                    and item["bytes"] == 11 for item in owners)
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "r4 composed Bank-2 drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ORIGINAL_SESSION_CONFIG(product, library)
    value["format"] = SESSION_FORMAT
    value["candidate"] = {
        "qualified_pair": accepted_pair(),
        "product_card": bind(CARD_RECEIPT),
        "authority_prelink": bind(R4.PRELINK_RECEIPT),
        "phase0_build_id": f"0x{PRODUCT_ID:08x}",
        "decoder_compare": ["0x8C", "0x6C", "0xC5", "0x20"],
    }
    value["read_cutpoint"]["ranges"] = read_ranges()
    return value


def finish(packed: dict[str, Any], completion: dict[str, Any],
           library: dict[str, Any]) -> dict[str, Any]:
    value = ORIGINAL_FINISH(packed, completion, library)
    value["format"] = FORMAT
    value["predecessor_media"] = bind(BASE.ARCH / (
        "c2.3-v2.0-symbol22-first-fault-device-media-receipt.json"))
    value["successor_reason"] = (
        "r4 phase-0 decoder consumes the delivered candidate build ID")
    BASE.write(RECEIPT, value)
    return value


def configure() -> None:
    values = {
        "CARD": R4, "CARD_RECEIPT": CARD_RECEIPT,
        "CARD_BUILD": CARD_BUILD, "SOURCE_WPLTO": SOURCE_WPLTO,
        "SEED_WPLTO": SEED_WPLTO, "SOURCE_STATIC": SOURCE_STATIC,
        "BUILD": BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "LIBRARY": LIBRARY,
        "RECEIPT": RECEIPT, "SESSION": SESSION, "SCOPE": SCOPE,
        "ACCEPTANCE": ACCEPTANCE, "PRODUCT_REMOTE": PRODUCT_REMOTE,
        "LIBRARY_REMOTE": LIBRARY_REMOTE, "PRODUCT_ID": PRODUCT_ID,
        "PLANE_BYTES": PLANE_BYTES, "EXPECTED": EXPECTED, "STATUS": STATUS,
        "PLAN": PLAN, "PLAN_HEADER": PLAN_HEADER,
    }
    for name, value in values.items():
        setattr(BASE, name, value)
    BASE.accepted_pair = accepted_pair
    BASE.authority = authority
    BASE.product_manifest = product_manifest
    BASE.static_plane_gate = static_plane_gate
    BASE.session_config = session_config
    BASE.finish = finish
    BASE.configure_paths()


def build() -> None:
    configure()
    # A source-authority rejection may happen after the copy-only WPLTO
    # projection but before Completion.  That projection is immutable input,
    # not a consumed product operation, so a retry may reuse it after proving
    # that no later output or receipt exists.
    if BUILD.exists():
        children = sorted(path.relative_to(BUILD).as_posix()
                          for path in BUILD.iterdir())
        require(children == ["inputs"] and WPLTO.is_dir()
                and not RECEIPT.exists() and not SESSION.exists(),
                "r4 device-media retry found outputs beyond input projection")
    else:
        require(not RECEIPT.exists() and not SESSION.exists(),
                "r4 device media is one-shot")
    adapter = BASE.closure_adapter()
    BUILD.mkdir(parents=True, exist_ok=True)
    BASE.write(BUILD / "closure-adapter.json", adapter)
    completion = BASE.complete_artifacts()
    product_manifest(completion)
    BASE.configure_paths()
    packed = BASE.MEDIA.MEDIA.build(
        stager_compile_defines=(BASE.MEDIA.PREP.LIVENESS.OPT_IN,))
    library = BASE.external_library()
    value = finish(packed, completion, library)
    check()
    print("v2.0 symbol22 build-ID device media: BUILD PASS product="
          f"{value['media']['product']['sha256']} library="
          f"{value['media']['library']['sha256']} device=0")


def check(*, source_only: bool = False) -> None:
    configure()
    BASE.check(source_only=source_only)
    value, session = load(RECEIPT), load(SESSION)
    require(value["format"] == FORMAT
            and value["accepted_pair"] == accepted_pair()
            and session["format"] == SESSION_FORMAT
            and session["read_cutpoint"]["ranges"] == read_ranges()
            and session["candidate"]["phase0_build_id"] == "0x8c6cc520",
            "r4 successor media/session drift")
    print("v2.0 symbol22 build-ID device media: CHECK PASS "
          f"source_only={str(source_only).lower()}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "source-check":
        check(source_only=True)
    else:
        raise BASE.MediaError("usage: build|check|source-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 symbol22 build-ID device media: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
