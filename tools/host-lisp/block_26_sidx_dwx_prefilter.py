#!/usr/bin/env python3
"""Pack Card-1 prefilter media and execute the exact sidx DWX row."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_sidx_product_card as CARD  # noqa: E402
import c2_v200_release_strip_device_media as MEDIA  # noqa: E402
import dwx_mirrored_prefilter_rows as DWX  # noqa: E402
import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402
from evidence_era import era_bind, era_blob  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card1-sidx-dwx-prefilter-r2"
MEDIA_BUILD = BUILD / "media"
WPLTO = MEDIA_BUILD / "inputs/wplto"
STATIC = MEDIA_BUILD / "inputs/static-plane"
TARGET = MEDIA_BUILD / "canonical-product"
SHARED = MEDIA_BUILD / "shared-system"
MEDIA_RECEIPT = BUILD / "prefilter-medium-receipt.json"
SESSION = BUILD / "unused-device-session.json"
PREFILTER_RECEIPT = ARCH / "block-2.6-card1-sidx-dwx-prefilter-r2.json"
PRODUCT_ID = 0x4A1713AB
STATUS = "PASS: CARD-1 R2 DWX PREFILTER MEDIUM READY"
FORMAT = "lisp65-block-2.6-card1-sidx-dwx-prefilter-medium-r2-v1"
SESSION_FORMAT = "lisp65-block-2.6-card1-unused-device-session-v1"
XEMU = ROOT / "build/dwx/xemu-cycle-probe-r3/build/bin/xmega65.native"
ROM = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
SD_IMAGE = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))
BLIND_CONTRACT = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
PREFILTER_EVIDENCE_ERA = "eb2d6e3a18a7a290cade7b69c01b066f7ecbc620"


class PrefilterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PrefilterError(message)


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
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProductCard:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    LINK = CARD.BASE.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        CARD.configure()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        CARD.configure()
        return CARD.BASE.CHAIN.setup_link_world()


MediaPrice = MEDIA.MediaPrice


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = MediaPrice.RECEIPT
    PRICE = MediaPrice


def accepted_pair() -> dict[str, Any]:
    return {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}


def authority() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    require(
        receipt["status"] == CARD.STATUS
        and receipt["review_ready"] is False
        and receipt["DWX_prefilter"]["status"] == "PENDING UNTIL CANDIDATE MEDIUM EXISTS"
        and {key: receipt["artifacts_after"][key] for key in ("PRG", "ELF")}
        == accepted_pair(),
        "Card-1 pair is not ready for its mandated prefilter",
    )
    return {
        "product_card": bind(CARD.RECEIPT),
        "commission": CARD.authority()["commission"],
        "right": "one transient artifact-only DWX fixture medium; no device contact",
    }


def plan_section() -> dict[str, Any]:
    return CARD.authority()["commission"]


def session_config(product: Path, valid: Path | None = None) -> dict[str, Any]:
    return {
        "format": SESSION_FORMAT,
        "status": "not-a-device-session",
        "medium": bind(product),
        "claim_scope": {
            "accepts": ["functional DWX prefilter of exact (setq 5 x) domain error"],
            "excludes": ["device acceptance", "Freezer", "DMA timing", "typing feel"],
        },
        "claim": "DWX functional prefilter only",
        "device_acceptance_claimed": False,
    }


def inherited_check(*, source_only: bool = False) -> None:
    value = load(MEDIA_RECEIPT)
    require(
        value["status"] == STATUS
        and value["accepted_pair"] == accepted_pair()
        and value["accounting"]["WPLTO_runs"] == 0
        and value["accounting"]["product_links"] == 0
        and value["accounting"]["device_contacts"] == 0,
        "Card-1 transient prefilter medium drift",
    )
    if not source_only:
        observed = bind(ROOT / value["media"]["absent_INIT"]["path"])
        require(all(value["media"]["absent_INIT"][key] == observed[key]
                    for key in ("path", "bytes", "sha256")),
            "Card-1 transient D81 identity drift")


def configure_media() -> None:
    candidate = SimpleNamespace(
        PRODUCT_KEYS=CARD.PRODUCT_KEYS,
        RECEIPT=CARD.RECEIPT,
        PRG=CARD.PRG,
        ELF=CARD.ELF,
        WPLTO=CARD.WPLTO,
        PLANE=CARD.PLANE,
        BUILD=CARD.BUILD,
        STATUS=CARD.STATUS,
        CHAIN=CARD.BASE.CHAIN,
        configure=CARD.configure,
    )
    MEDIA.STRIP = candidate
    MEDIA.ProductCard = ProductCard
    MEDIA.Adapter = Adapter
    for name, value in {
        "BUILD": MEDIA_BUILD,
        "WPLTO": WPLTO,
        "STATIC": STATIC,
        "TARGET": TARGET,
        "SHARED": SHARED,
        "RECEIPT": MEDIA_RECEIPT,
        "SESSION": SESSION,
        "VALID": BUILD / "unused-init-valid.d81",
        "VALID_SOURCE": BUILD / "unused-init-valid.l65",
        "PRODUCT_REMOTE": "B26C1.D81",
        "VALID_REMOTE": "UNUSED.D81",
        "PRODUCT_ID": PRODUCT_ID,
        "PLANE_BYTES": CARD.EXTENT,
        "EXPECTED": {
            "PRG": (CARD.PRG.stat().st_size, bind(CARD.PRG)["sha256"]),
            "ELF": (CARD.ELF.stat().st_size, bind(CARD.ELF)["sha256"]),
        },
        "STATUS": STATUS,
        "FORMAT": FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT,
    }.items():
        setattr(MEDIA, name, value)
    MEDIA.accepted_pair = accepted_pair
    MEDIA.authority = authority
    MEDIA.plan_section = plan_section
    MEDIA.session_config = session_config
    MEDIA.inherited_check = inherited_check
    MEDIA.check = inherited_check
    MEDIA.configure()


def build_medium() -> Path:
    configure_media()
    if not MEDIA_RECEIPT.exists():
        MEDIA.BASE.build()
    inherited_check()
    value = load(MEDIA_RECEIPT)
    product = ROOT / value["media"]["absent_INIT"]["path"]
    require(value["packed_readback"]["absent_INIT"]["status"] ==
            "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE",
            "Card-1 packed readback gates are not green")
    return product


def row() -> dict[str, Any]:
    return {
        "id": "block-2.6-card1-exact-setq-symbol-domain",
        "state": "ACTIVE",
        "execution": "headless-HWA-input",
        "medium": "candidate-product",
        "input": "(setq 5 x)\n",
        "oracle": {
            "type": "framebuffer",
            "required": ["VM: TYPE ERROR", "LISP65>"],
            "forbidden": ["DISK ERROR", "RED FRAME"],
        },
    }


def run_prefilter() -> None:
    built_here = not MEDIA_RECEIPT.exists()
    product = build_medium()
    if built_here:
        # Media construction temporarily rebinds the long-lived card-module
        # graph. Execute the row in a fresh interpreter so the prefilter sees
        # only packed bytes, never producer globals.
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "_runtime"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        require(result.returncode == 0,
                "Card-1 clean-process DWX runtime red:\n" + result.stdout)
        print(result.stdout.strip())
        return
    execute_prefilter(product)


def execute_prefilter(product: Path) -> None:
    require(not PREFILTER_RECEIPT.exists(), "Card-1 DWX prefilter is one-shot")
    blind = load(BLIND_CONTRACT)
    BLIND.validate_contract(blind)
    tool = blind["qualified_tool_identity"]
    require(
        sha256(XEMU) == tool["binary_sha256"]
        and sha256(ROM) ==
            load(ROOT / "config/dwx-mirrored-prefilter-rows-contract.json")["inputs"]["rom_sha256"]
        and sha256(SD_IMAGE) ==
            load(ROOT / "config/dwx-mirrored-prefilter-rows-contract.json")["inputs"]["system_sd_sha256"],
        "Card-1 DWX tool/ROM/SD identity drift",
    )
    output = BUILD / "runtime"
    output.mkdir(parents=True, exist_ok=False)
    args = argparse.Namespace(xemu=XEMU, rom=ROM, sd_image=SD_IMAGE, timeout=35)
    runtime, stopped = DWX.run_headless(row(), product, output, args)
    require(
        stopped is None
        and runtime["status"] == "PASS"
        and runtime["oracle"]["passed"] is True
        and runtime["desktop_focus_used"] is False
        and runtime["GUI_used"] is False,
        "Card-1 exact SETQ DWX row red",
    )
    value = {
        "format": "lisp65-block-2.6-card1-sidx-dwx-prefilter-v1",
        "recorded_on": "2026-09-03",
        "status": "PASS: DWX PREFILTER GREEN",
        "evidence_class": "xemu-prefilter-green",
        "product_card": bind(CARD.RECEIPT),
        "medium_receipt": bind(MEDIA_RECEIPT),
        "medium": bind(product),
        "row": row(),
        "runtime": runtime,
        "tool_identity": tool,
        "blind_spot_contract": bind(BLIND_CONTRACT),
        "claim_limit": (
            "Functional headless Xemu prefilter only; not physical-device acceptance, "
            "not a Freezer/DMA/core/timing/typing-feel claim."
        ),
        "accounting": {
            "fresh_headless_xemu_processes": 1,
            "desktop_focus_input_events": 0,
            "device_contacts": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
        },
    }
    PREFILTER_RECEIPT.write_bytes(canonical(value))
    receipt = load(CARD.RECEIPT)
    receipt["DWX_prefilter"] = {
        "status": value["status"],
        "receipt": bind(PREFILTER_RECEIPT),
        "row": row()["id"],
        "oracle": "framebuffer",
        "device_acceptance_claimed": False,
    }
    receipt["attempt_accounting"]["DWX_prefilter_runs"] = 1
    receipt["attempt_accounting"]["DWX_fixture_media_builds"] = 1
    receipt["review_ready"] = True
    CARD.RECEIPT.write_bytes(canonical(receipt))
    CARD.write_report(receipt)
    CARD.validate(receipt)
    print("Block 2.6 Card 1: DWX PREFILTER PASS exact=(setq 5 x) device=0")


def check() -> None:
    value = load(PREFILTER_RECEIPT)
    sealed_blind = json.loads(era_blob(
        PREFILTER_EVIDENCE_ERA,
        BLIND_CONTRACT.relative_to(ROOT).as_posix()))
    current_blind = load(BLIND_CONTRACT)
    BLIND.validate_contract(current_blind)
    require(
        value["status"] == "PASS: DWX PREFILTER GREEN"
        and value["runtime"]["oracle"]["passed"] is True
        and value["tool_identity"] == sealed_blind["qualified_tool_identity"]
        and value["blind_spot_contract"] ==
            era_bind(PREFILTER_EVIDENCE_ERA, BLIND_CONTRACT)
        # This run belongs to the archived three-patch fork, not whichever
        # successor fork is qualified today. Verify the actual old tool too.
        and sha256(XEMU) == value["tool_identity"]["binary_sha256"]
        and all(sha256(XEMU.parents[2] / name) == digest for name, digest in
                value["tool_identity"]["patched_source_sha256"].items())
        and value["medium"] == bind(ROOT / value["medium"]["path"])
        and value["accounting"]["device_contacts"] == 0,
        "Card-1 DWX receipt drift",
    )
    CARD.check()
    print("Block 2.6 Card 1: DWX CHECK PASS device=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "_runtime"))
    action = parser.parse_args().action
    {"build": run_prefilter, "check": check,
     "_runtime": lambda: execute_prefilter(build_medium())}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block 2.6 Card 1 DWX: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
