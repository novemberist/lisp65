#!/usr/bin/env python3
"""Run the one authorized v1.2.4 fx product-shaped WPLTO capacity card."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v123_candidate_product as LINK80  # noqa: E402
import c2_q_gate as FX  # noqa: E402


PRODUCT = LINK80.PRODUCT
V = PRODUCT.V
BASE = PRODUCT.BASE
CAN = PRODUCT.CAN
BUILD = ROOT / "build/post-promotion/v124/fx/product-shaped-wplto-v5"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.4-fx-wplto-receipt.json"
FIRST_RED = EVIDENCE / "c2.2-v1.2.4-fx-wplto-first-red.json"
HOST_RECEIPT = EVIDENCE / "c2.2-v1.2.4-fx-host-first-receipt.json"
PREDECESSOR = EVIDENCE / "c2.2-v1.2.3-phase-b-link80-receipt.json"
FX_MANIFEST = FX.CANDIDATE_PREFIX.with_suffix(".manifest.json")
EXPECTED_STATIC = 42936
EXPECTED_ENTRIES = 722
EXPECTED_RESOLUTIONS = 2831
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 656
DRIVER = Path(__file__).resolve()


class WPLTOError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WPLTOError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def configure() -> dict[str, Path]:
    V.RANDOM_MANIFEST = FX_MANIFEST
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.configure_candidate()
    BASE.LINK = 81
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    V.bind_candidate_specs()
    os.environ.update(CAN.canonical_build_environment())
    return paths


def main() -> int:
    try:
        require(
            not BUILD.exists() and not RECEIPT.exists()
            and (
                not FIRST_RED.exists()
                or load(FIRST_RED).get("target_linker_invocations") == 0
            ),
            "v1.2.4 fx WPLTO is a one-shot card",
        )
        host_result = FX.main()
        require(host_result == 0, "fx host-first gate red")
        host = load(HOST_RECEIPT)
        predecessor = load(PREDECESSOR)
        require(
            host["status"]
                == "passed-fx-host-reference-modeled-register-and-capacity"
            and host["artifacts"]["delta"]["resident_bytes"] == 0
            and host["artifacts"]["delta"]["bank2_code_bytes"] == 1451
            and predecessor["status"]
                == "passed-B3-bound-successor-product-link-and-check-source"
            and predecessor["qualifying_candidate"]["link"] == 80,
            "fx host or Link-80 predecessor authority drift",
        )

        paths = configure()
        static = BASE.PROBE.REQ.build_static_plane()
        plane = BASE.PROBE.REQ.F1W.static_gate()
        header = PRODUCT.bind_generated_stdlib_header(paths)
        product_path = (
            paths["static_product"] / "substitution-artifacts.json")
        product = load(product_path)
        profile = load(ROOT / "config/c2-l-full-product-profile.json")
        require(
            static["semantics"]["code_bytes"] == EXPECTED_STATIC
            and plane["static_code_bytes"] == EXPECTED_STATIC
            and product["images"] == 6
            and product["entries"] == EXPECTED_ENTRIES
            and product["resolutions"] == EXPECTED_RESOLUTIONS
            and product["roots"] == EXPECTED_ROOTS
            and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
            and profile["bank2_static_code"]["bytes"] == EXPECTED_STATIC
            and profile["bank2_static_code"]["headroom_bytes"]
                == 65536 - EXPECTED_STATIC,
            "fx single-emitter static-plane identity drift",
        )
        V.EXPECTED_PRODUCT_ID = product["product_build_id_hex"]
        V.EXPECTED_BANK2_SHA = profile["bank2_static_code"]["sha256"]

        # The sole target linker invocation authorized for Phase F.
        wplto = CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        old_walls = predecessor["qualifying_candidate"]["walls"]
        require(
            walls["bank0_text_headroom_bytes"]
                == old_walls["bank0_text_headroom_bytes"]
            and walls["e000_headroom_bytes"]
                == old_walls["e000_headroom_bytes"]
            and walls["fixed_hot_block_headroom_bytes"]
                == old_walls["fixed_hot_block_headroom_bytes"]
            and walls["ordinary_bank0_bss_headroom_bytes"]
                == old_walls["ordinary_bank0_bss_headroom_bytes"]
            and walls["resident_island_headroom_bytes"]
                == old_walls["resident_island_headroom_bytes"]
            and capacity["session_family_headroom_bytes"]
                == old_walls["session_family_headroom_bytes"]
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_headroom_bytes"] >= 0,
            "fx WPLTO moved a closed resident/session wall",
        )
        elf = (
            paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf")
        require(elf.is_file(), "fx WPLTO linked ELF absent")
        value = {
            "format": "lisp65-c2.2-v1.2.4-fx-WPLTO-v1",
            "recorded_on": "2026-07-30",
            "status": "passed-fx-one-product-shaped-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "wplto_probes_consumed": 1,
            "pre_wplto_first_red": (
                bind(FIRST_RED) if FIRST_RED.is_file() else None
            ),
            "predecessor": bind(PREDECESSOR),
            "host_first": bind(HOST_RECEIPT),
            "static_geometry": {
                "bank2_static_code_bytes": EXPECTED_STATIC,
                "bank2_delta_from_Link80_bytes": 1451,
                "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
                "entries": EXPECTED_ENTRIES,
                "resolutions": EXPECTED_RESOLUTIONS,
                "roots": EXPECTED_ROOTS,
                "direct_entry_refs": EXPECTED_DIRECT_REFS,
                "product_build_id": product["product_build_id_hex"],
                "bank2_sha256": profile["bank2_static_code"]["sha256"],
            },
            "target_stdlib_header": header,
            "walls": walls,
            "capacity": capacity,
            "wplto": wplto,
            "authority": {
                "contract": bind(FX.CONTRACT),
                "source": bind(FX.SOURCE),
                "candidate_manifest": bind(FX_MANIFEST),
                "profile": bind(ROOT / "config/c2-l-full-product-profile.json"),
                "static_product": bind(product_path),
                "linked_ELF": bind(elf),
                "driver": bind(DRIVER),
            },
            "next_gate": (
                "Phase M confirms high product bytes and the division "
                "fraction-bit row before any successor product link."
            ),
            "claim_limit": (
                "Exactly one non-promotable product-shaped WPLTO, with no "
                "successor product identity and no on-metal fx claim."
            ),
        }
        RECEIPT.write_bytes(CAN.json_bytes(value))
        print(
            "c2-v124-fx-wplto: PASS "
            f"bank2={EXPECTED_STATIC} "
            f"headroom={65536 - EXPECTED_STATIC} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']} "
            "links=0 hardware=0"
        )
        return 0
    except Exception as error:
        if not RECEIPT.exists() and not FIRST_RED.exists():
            FIRST_RED.write_bytes(CAN.json_bytes({
                "format": "lisp65-c2.2-v1.2.4-fx-WPLTO-first-red-v1",
                "recorded_on": "2026-07-30",
                "status": "FIRST RED: fx one-shot WPLTO did not close",
                "promotable": False,
                "wplto_retry_authorized": False,
                "product_links": 0,
                "hardware_runs": 0,
                "error": str(error),
                "driver": (
                    bind(DRIVER) if DRIVER.is_file()
                    else {"path": str(DRIVER)}
                ),
            }))
        print(f"c2-v124-fx-wplto: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
