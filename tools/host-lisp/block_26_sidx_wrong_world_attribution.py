#!/usr/bin/env python3
"""Attribute the Card-1 r1 prefilter red to its historical Plane root."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
INVALID_BUILD = ROOT / "build/2.6/card1-sidx-product-r1"
INVALID_PREFLIGHT = ROOT / "build/2.6/card1-sidx-product-r1-preflight"
INVALID_PLANE = INVALID_PREFLIGHT / "setup-owned/static-plane/narrow-static"
INVALID_ELF = INVALID_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
INVALID_PRG = INVALID_BUILD / "wplto/lisp65-c2-substitution-linked.prg"
INVALID_D81 = ROOT / (
    "build/2.6/card1-sidx-dwx-prefilter-r1/media/shared-system/lisp65-product.d81"
)
FRAMEBUFFER = ROOT / (
    "build/2.6/card1-sidx-dwx-prefilter-r1/runtime/"
    "run-block-2.6-card1-exact-setq-symbol-domain/framebuffer.txt"
)
STRIP_PLANE = ROOT / (
    "build/c2.3/v2.0-release-strip-product-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static"
)
RELEASE_PLANE = ROOT / (
    "build/c2.3/v2.0.0-release-card-r3-preflight/"
    "setup-owned/static-plane/narrow-static"
)
PUBLIC_PLANE = ROOT / "config/c2-v200-public-plane/static-plane"
RELEASE_ELF = ROOT / (
    "build/c2.3/v2.0.0-release-card-r3/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
RELEASE_PRG = ROOT / (
    "build/c2.3/v2.0.0-release-card-r3/wplto/"
    "lisp65-c2-substitution-linked.prg"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "block-2.6-card1-sidx-wrong-world-red.json"
)
REPORT = ROOT / "docs/planning/2.6-card1-sidx-wrong-world-red.md"
FORMAT = "lisp65-block-2.6-card1-sidx-wrong-world-red-v1"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def world(root: Path) -> dict[str, Any]:
    manifest = load(root / "stdlib-p0.manifest.json")
    banner = next(row for row in manifest["entries"] if row["name"] == "%repl-banner")
    product = load(root / "product/substitution-artifacts.json")
    return {
        "root": root.relative_to(ROOT).as_posix(),
        "banner": banner["literals"][-1]["string"],
        "product_build_id": product["product_build_id_hex"],
        "manifest": bind(root / "stdlib-p0.manifest.json"),
        "stdlib_ext": bind(root / "stdlib-p0.ext.bin"),
        "shelf": bind(root / "product/product-shelf-v4-direct.bin"),
        "static_code": bind(root / "v6-semantics/bank2-static-code.bin"),
    }


def decoded_screen() -> str:
    raw = FRAMEBUFFER.read_text(encoding="utf-8")
    return re.sub(r"\{([A-Za-z0-9])\}", r"\1", raw).upper()


def validate(value: dict[str, Any]) -> None:
    worlds = value["worlds"]
    same = lambda left, right: all(left[key] == right[key]
                                   for key in ("bytes", "sha256"))
    require(
        value["format"] == FORMAT
        and value["status"] == "FROZEN-UNQUALIFIED-WRONG-PRODUCT-WORLD"
        and worlds["candidate"]["banner"] == worlds["historical_strip"]["banner"]
        == "WORKBENCH 1.9.0"
        and worlds["candidate"]["product_build_id"]
        == worlds["historical_strip"]["product_build_id"] == "0xc4c3ce30"
        and worlds["intended_release"]["banner"] == worlds["public_plane"]["banner"]
        == "WORKBENCH 2.0.0"
        and worlds["intended_release"]["product_build_id"]
        == worlds["public_plane"]["product_build_id"] == "0x4a1713ab"
        and same(worlds["candidate"]["manifest"], worlds["historical_strip"]["manifest"])
        and same(worlds["candidate"]["shelf"], worlds["historical_strip"]["shelf"])
        and same(worlds["intended_release"]["manifest"], worlds["public_plane"]["manifest"])
        and same(worlds["intended_release"]["shelf"], worlds["public_plane"]["shelf"])
        and value["runtime"]["observed_banner"] == "WORKBENCH 1.9.0"
        and value["runtime"]["expected_banner"] == "WORKBENCH 2.0.0"
        and value["classification"]["product_defect_attributed"] is False
        and value["classification"]["card_world_defect"] is True
        and value["accounting"] == {
            "WPLTO_runs_consumed": 1,
            "product_links_consumed": 1,
            "DWX_prefilter_attempts": 1,
            "device_contacts": 0,
        },
        "Card-1 wrong-world attribution drift",
    )


def build() -> None:
    require(not RECEIPT.exists(), "wrong-world attribution is one-shot")
    worlds = {
        "candidate": world(INVALID_PLANE),
        "historical_strip": world(STRIP_PLANE),
        "intended_release": world(RELEASE_PLANE),
        "public_plane": world(PUBLIC_PLANE),
    }
    screen = decoded_screen()
    require("WORKBENCH 1.9.0" in screen and "LISP65>" in screen,
            "DWX framebuffer did not expose the historical world")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-09-03",
        "status": "FROZEN-UNQUALIFIED-WRONG-PRODUCT-WORLD",
        "invalid_pair": {"ELF": bind(INVALID_ELF), "PRG": bind(INVALID_PRG)},
        "intended_predecessor": {"ELF": bind(RELEASE_ELF), "PRG": bind(RELEASE_PRG)},
        "worlds": worlds,
        "runtime": {
            "medium": bind(INVALID_D81),
            "framebuffer": bind(FRAMEBUFFER),
            "observed_banner": "WORKBENCH 1.9.0",
            "expected_banner": "WORKBENCH 2.0.0",
            "domain_oracle_reached": False,
            "device_acceptance_claimed": False,
        },
        "attribution": {
            "mechanism": (
                "Card-1 r1 materialized c2_v200_release_strip_product_card.PRICE.CLEAN_ROOT, "
                "the pre-banner WORKBENCH 1.9.0 Plane, instead of the published v2.0.0/2.0.1 Plane."
            ),
            "candidate_equals_historical_strip": [
                "banner", "product_build_id", "stdlib manifest", "stdlib ext", "product shelf"
            ],
            "intended_release_equals_public_plane": [
                "banner", "product_build_id", "stdlib manifest", "stdlib ext", "product shelf"
            ],
            "static_code_equal_across_banner_worlds": (
                worlds["candidate"]["static_code"]["sha256"]
                == worlds["intended_release"]["static_code"]["sha256"]
            ),
            "why_static_extent_did_not_catch_it": (
                "The 47,795-byte static code payload is unchanged by the banner successor; "
                "the distinguishing authority is the manifest/extended payload, shelf and Product Build ID."
            ),
            "unexplained": [],
        },
        "classification": {
            "product_defect_attributed": False,
            "card_world_defect": True,
            "pair_disposition": "frozen evidence; never resumed as a Block-2.6 candidate",
            "replacement_required": (
                "materialize from the published v2.0.0/2.0.1 Plane and issue one replacement WPLTO/link"
            ),
        },
        "accounting": {
            "WPLTO_runs_consumed": 1,
            "product_links_consumed": 1,
            "DWX_prefilter_attempts": 1,
            "device_contacts": 0,
        },
        "rule": (
            "A post-release product card derives its predecessor and complete Plane authority from the "
            "published product world, never from the last pre-banner hardware candidate."
        ),
    }
    require(value["attribution"]["static_code_equal_across_banner_worlds"] is True,
            "static-code control unexpectedly differs")
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(
        """# Block 2.6 Card 1 — wrong-world first red

Status: **FROZEN-UNQUALIFIED-WRONG-PRODUCT-WORLD**

The first DWX prefilter correctly stopped Card 1 before review. The transient
medium booted `WORKBENCH 1.9.0`, not the published `WORKBENCH 2.0.0` world.

The cause is fully attributed: r1 materialized the pre-banner strip Plane
(Product Build ID `0xc4c3ce30`). Its manifest, extended stdlib and product
shelf are byte-identical to that historical world. The intended release Plane
and checked-in public Plane are mutually byte-identical and carry
`WORKBENCH 2.0.0` / Product Build ID `0x4a1713ab`. The 47,795-byte static-code
blob is equal across the two banner worlds, which explains why the extent and
ordinary packed-code gates could not distinguish them.

This is a product-card world-selection defect, not evidence against the
`sidx()` repair. The emitted ELF/PRG pair is frozen as unqualified evidence and
will never be resumed as a 2.6 candidate. One WPLTO and one product link were
consumed; no physical device was contacted. A replacement requires explicit
authorization and must derive its complete Plane authority from the published
v2.0.0/2.0.1 world before compilation.
""",
        encoding="utf-8",
    )
    print("Block 2.6 Card 1: WRONG-WORLD ATTRIBUTION PASS unexplained=0 device=0")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["invalid_pair"] == {"ELF": bind(INVALID_ELF), "PRG": bind(INVALID_PRG)}
            and value["runtime"]["framebuffer"] == bind(FRAMEBUFFER)
            and REPORT.is_file(), "wrong-world evidence binding drift")
    print("Block 2.6 Card 1: WRONG-WORLD CHECK PASS unexplained=0")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "historical-banner-hidden": lambda row: row["runtime"].update(
            {"observed_banner": "WORKBENCH 2.0.0"}),
        "wrong-build-ID-hidden": lambda row: row["worlds"]["candidate"].update(
            {"product_build_id": "0x4a1713ab"}),
        "pair-promoted": lambda row: row["classification"].update(
            {"product_defect_attributed": True}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (AttributionError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "wrong-world mutation survived")
    print(f"Block 2.6 Card 1: WRONG-WORLD SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, KeyError, ValueError) as error:
        print(f"Block 2.6 Card 1 wrong-world: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
