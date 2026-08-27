#!/usr/bin/env python3
"""Pack artifact-only Block-3 media after the banner-ordinal repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_block3_banner_ordinal_repair as CARD  # noqa: E402
import c2_v17_block3_r10_acceptance_media as BASE_MEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = CARD.SETUP
LIBRARY_SOURCE = CARD.R10.CARD.PLANE
INPUT_ROOT = ROOT / "build/c2.3/v1.7-block3-banner-ordinal-media-inputs"
STATIC = INPUT_ROOT / "static-plane"
BUILD = ROOT / "build/c2.3/v1.7-block3-banner-ordinal-acceptance-media"
ADAPTER = BUILD.parent / "v1.7-block3-banner-ordinal-media-adapter.json"
RECEIPT = (ARCH /
    "c2.3-v1.7-block3-banner-ordinal-acceptance-media-receipt.json")
SESSION = ROOT / "config/c2-v17-block3-banner-ordinal-acceptance-session.json"
CLOSURE = CARD.RECEIPT
ACCEPTANCE = CARD.ACCEPTANCE
PRODUCT_REMOTE = "V17B3P.D81"
LIBRARY_REMOTE = "V17B3L.D81"
EXPECTED = {
    "PRG": (41566,
        "2e8274902a357bae76d55f31ee4e2869480126c9a7cb791291a56c6d1708387d"),
    "ELF": (647940,
        "9ce3ff079ead7df5b15c8b3d0cc57c5729009b860522002d19425c168456221b"),
}
STATUS = "PASS: V1.7 BLOCK3 BANNER-ORDINAL REPAIR MEDIA READY"
ORIGINAL_SESSION_CONFIG = BASE_MEDIA.session_config


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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


def authority() -> dict[str, Any]:
    closure = load(CLOSURE)
    session = load(ROOT / "config/c2-v17-block3-r10-acceptance-session.json")
    require(closure["status"] == CARD.STATUS
            and closure["attempt_accounting"]["repair_rounds"] == 1
            and session["decision_table"]["daily-use-blocker"] ==
                "at most one fix round, else feature descope",
            "bounded Block-3 media authority absent")
    return {"authority": "qualified bounded-repair successor",
            "repair_closure": bind(CLOSURE),
            "session_authority": bind(
                ROOT / "config/c2-v17-block3-r10-acceptance-session.json"),
            "repair_rounds": 1, "further_repair_rounds_authorized": False}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    projection = BASE_MEDIA.prepare_static_inputs()
    pair = closure["frozen_pair"]
    require(closure["status"] == CARD.STATUS
            and closure["final_real_caller"]["ordinal"] == CARD.NEW_ORDINAL
            and closure["scope"] == bind(CARD.SCOPE)
            and closure["acceptance"] == bind(CARD.ACCEPTANCE)
            and closure["composed_bank2"]["largest_contiguous_hole"]["bytes"]
                == 11436
            and closure["tuple_LOADADDR"]["shared_offset"] == 0x28000
            and pair == {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)},
            "banner-ordinal repair closure is not media-ready")
    value = {"format": "lisp65-v17-block3-banner-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "banner_ordinal_repair_closed": True,
        "r10_closure": bind(CLOSURE),
        "repair_closure": bind(CLOSURE), "review_authority": authority(),
        "frozen_pair_before": pair, "frozen_pair_after": pair,
        "composed_bank2": closure["composed_bank2"],
        "tuple_LOADADDR": closure["tuple_LOADADDR"],
        "compiler_stdlib_consumption": closure["real_compiler_consumption"],
        "final_real_caller": closure["final_real_caller"],
        "completion_input_projection": projection,
        "rule": "same-world artifact projection; no compile or link"}
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct candidate paths only; never compile or link."""
    CARD.install()
    CARD.R10.CARD.BASE.configure_full_candidate()
    CARD.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    CARD.R10.CARD.bind_current_plane(STATIC)
    base = BASE_MEDIA.BASE
    base.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    base.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    base.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    truth = ElfTruth.read(CARD.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(base.PRODUCT.VERIFIER_BINDING_SECTION)
    base.PRODUCT.VERIFIER_BINDING_BASE = section.address
    base.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ORIGINAL_SESSION_CONFIG(product, library)
    value["format"] = "lisp65-c2-v17-block3-banner-repair-session-v1"
    value["recorded_on"] = "2026-08-26"
    value["entry_precondition"] = {
        "actions": ["boot product", "load the one-row library medium"],
        "expect": ("libraries complete, native lisp65> appears, and no "
                   "wrong-argument-count error is shown"),
        "failure": "daily-use-blocker; Block 3 descopes after this one round",
    }
    value["repair_witness"] = {
        "expected_final_banner_ordinal": CARD.NEW_ORDINAL,
        "candidate": bind(CARD.ELF),
        "consumer_proof": bind(CLOSURE),
    }
    return value


def configure_successor() -> None:
    BASE_MEDIA.CARD_BUILD = CARD_BUILD
    BASE_MEDIA.WPLTO = WPLTO
    BASE_MEDIA.SOURCE_STATIC = SOURCE_STATIC
    BASE_MEDIA.LIBRARY_SOURCE = LIBRARY_SOURCE
    BASE_MEDIA.INPUT_ROOT = INPUT_ROOT
    BASE_MEDIA.STATIC = STATIC
    BASE_MEDIA.BUILD = BUILD
    BASE_MEDIA.ADAPTER = ADAPTER
    BASE_MEDIA.RECEIPT = RECEIPT
    BASE_MEDIA.SESSION = SESSION
    BASE_MEDIA.CLOSURE = CLOSURE
    BASE_MEDIA.ACCEPTANCE = ACCEPTANCE
    BASE_MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    BASE_MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    BASE_MEDIA.EXPECTED = EXPECTED
    BASE_MEDIA.STATUS = STATUS
    BASE_MEDIA.authority = authority
    BASE_MEDIA.closure_adapter = closure_adapter
    BASE_MEDIA.configure_candidate = configure_candidate
    BASE_MEDIA.session_config = session_config
    BASE_MEDIA.configure_successor()


def build() -> None:
    configure_successor()
    BASE_MEDIA.MEDIA.build()


def check() -> None:
    configure_successor()
    BASE_MEDIA.MEDIA.check()
    value = load(RECEIPT)
    product = ROOT / value["media"]["product"]["path"]
    library = ROOT / value["media"]["library"]["path"]
    config = load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == {
                "ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)}
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 2, "device_contacts": 0}
            and value["shipped_byte_facade"]["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf"
            and value["same_world_pair"]["result"] == "same-world-pair"
            and config["repair_witness"]["expected_final_banner_ordinal"]
                == CARD.NEW_ORDINAL
            and bind(product) == value["media"]["product"]
            and bind(library) == value["media"]["library"],
            "banner-repair packed-media proof drift")
    print("v1.7 Block3 banner repair media: CHECK PASS device=0")


def source_check() -> None:
    value = load(RECEIPT)
    config = load(SESSION)
    expected_pair = {
        "ELF": {"path": CARD.ELF.relative_to(ROOT).as_posix(),
                "bytes": EXPECTED["ELF"][0], "sha256": EXPECTED["ELF"][1]},
        "PRG": {"path": CARD.PRG.relative_to(ROOT).as_posix(),
                "bytes": EXPECTED["PRG"][0], "sha256": EXPECTED["PRG"][1]},
    }
    require(value["status"] == STATUS
            and value["accepted_pair"] == expected_pair
            and config["entry_precondition"]["failure"].startswith(
                "daily-use-blocker")
            and config["repair_witness"]["expected_final_banner_ordinal"]
                == CARD.NEW_ORDINAL
            and config["repair_witness"]["candidate"] == expected_pair["ELF"],
            "banner-repair media/session evidence drift")
    print("v1.7 Block3 banner repair media: SOURCE CHECK PASS ordinal=247")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "check": check,
     "source-check": source_check}.get(action, lambda: (_ for _ in ()).throw(
         RuntimeError("usage: build|check|source-check")))()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
