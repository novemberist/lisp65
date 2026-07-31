#!/usr/bin/env python3
"""Run the one v1.2.5 Option-A product-shaped WPLTO capacity card."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_v124_time_wplto as T  # noqa: E402


V = T.V
BASE = T.BASE
CAN = T.CAN
PRODUCT = T.PRODUCT
BUILD = ROOT / "build/post-promotion/v125/require-fix/product-shaped-wplto-v2"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.5-require-option-A-wplto-receipt.json"
PREDECESSOR = EVIDENCE / "c2.2-v1.2.4-phase-e-link81-receipt.json"
OPTION_A = EVIDENCE / (
    "c2.2-require-prior-append-option-A-host-gate-receipt.json")
FASTPATH = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
FX_REVALIDATION = EVIDENCE / (
    "c2.2-v1.2.4-fx-final-composition-revalidation-receipt.json")
TIME_REVALIDATION = EVIDENCE / (
    "c2.2-v1.2.4-time-final-composition-revalidation-receipt.json")
RANDOM_REVALIDATION = EVIDENCE / (
    "c2.2-v1-random-base-final-composition-revalidation-receipt.json")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_HEADER = ROOT / "src/c2_lite_static_plane.h"
TIME_MANIFEST = T.TIME_MANIFEST
EXPECTED_STATIC = 43237
EXPECTED_ENTRIES = 725
EXPECTED_RESOLUTIONS = 2842
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 656
EXPECTED_PRODUCT_ID = "0x270030c3"
EXPECTED_BANK2_SHA = (
    "55193531f424da0c85349cd08679963223715c1f571704ab314743fb5f3dc248")
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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def configure() -> dict[str, Path]:
    V.RANDOM_MANIFEST = TIME_MANIFEST
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.configure_candidate()
    BASE.LINK = 82
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
            not BUILD.exists() and not RECEIPT.exists(),
            "v1.2.5 Option-A WPLTO is a one-shot card",
        )
        summaries = {
            "resolver": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_resolver_gate.py"],
                "resolver source/index gate",
            ),
            "prior_append": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_prior_append_option_a_gate.py"],
                "Option-A prior-append execution gate",
            ),
            "fastpath": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_idempotence_fastpath.py"],
                "require idempotence fastpath gate",
            ),
            "fx": "bound-current-source-final-composition-revalidation",
            "time": "bound-current-source-final-composition-revalidation",
            "random": "bound-current-source-final-composition-revalidation",
        }
        option = load(OPTION_A)
        fastpath = load(FASTPATH)
        fx = load(FX_REVALIDATION)
        timing = load(TIME_REVALIDATION)
        random = load(RANDOM_REVALIDATION)
        profile = load(PROFILE)
        header = STATIC_HEADER.read_text(encoding="utf-8")
        require(
            option["status"]
                == "passed-option-A-require-after-two-ordinary-appends-host-lane"
            and option["execution_witness"]["cases_executed"] == 2
            and option["execution_witness"]["mutations_executed"] == 5
            and fastpath["status"] == "passed-parser-free-idempotence-fastpath"
            and fastpath["fallback_mutations"]["foreign-identity"]["result"]
                == "t"
            and fx["status"]
                == "passed-fx-host-reference-in-final-v1.2.4-composition"
            and timing["status"]
                == "passed-time-host-reference-in-final-v1.2.4-composition"
            and random["status"]
                == "passed-random-base-in-final-v1.2.4-composition"
            and profile["bank2_static_code"]["bytes"] == EXPECTED_STATIC
            and profile["bank2_static_code"]["sha256"]
                == EXPECTED_BANK2_SHA
            and profile["product_build_id"] == EXPECTED_PRODUCT_ID
            and profile["resolutions"] == EXPECTED_RESOLUTIONS
            and f"LISP65_C2_LITE_STATIC_CODE_BYTES {EXPECTED_STATIC}UL"
                in header,
            "Option-A profile or host authority drift",
        )

        paths = configure()
        static = BASE.PROBE.REQ.build_static_plane()
        plane = BASE.PROBE.REQ.F1W.static_gate()
        header_binding = PRODUCT.bind_generated_stdlib_header(paths)
        product_path = (
            paths["static_product"] / "substitution-artifacts.json")
        product = load(product_path)
        require(
            static["semantics"]["code_bytes"] == EXPECTED_STATIC
            and plane["static_code_bytes"] == EXPECTED_STATIC
            and product["images"] == 6
            and product["entries"] == EXPECTED_ENTRIES
            and product["resolutions"] == EXPECTED_RESOLUTIONS
            and product["roots"] == EXPECTED_ROOTS
            and product["product_build_id_hex"] == EXPECTED_PRODUCT_ID
            and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS,
            "Option-A single-emitter static-plane identity drift",
        )
        V.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
        V.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA

        wplto = CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        predecessor = load(PREDECESSOR)
        old_walls = predecessor["qualifying_candidate"]["walls"]
        for key in (
            "bank0_text_headroom_bytes",
            "e000_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "resident_island_headroom_bytes",
        ):
            require(walls[key] == old_walls[key],
                    f"closed resident wall moved: {key}")
        require(
            capacity["session_family_headroom_bytes"]
                == old_walls["session_family_headroom_bytes"]
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_headroom_bytes"] >= 0,
            "Option-A WPLTO crossed a closed product wall",
        )
        elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
        require(elf.is_file(), "Option-A WPLTO linked ELF absent")
        value = {
            "format": "lisp65-c2.2-v1.2.5-require-option-A-WPLTO-v1",
            "recorded_on": "2026-07-31",
            "status": "passed-require-option-A-one-product-shaped-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "wplto_probes_consumed": 1,
            "predecessor": bind(PREDECESSOR),
            "host_gates": {
                "summaries": summaries,
                "option_A": bind(OPTION_A),
                "fastpath": bind(FASTPATH),
                "fx_revalidation": bind(FX_REVALIDATION),
                "time_revalidation": bind(TIME_REVALIDATION),
                "random_revalidation": bind(RANDOM_REVALIDATION),
            },
            "static_geometry": {
                "bank2_static_code_bytes": EXPECTED_STATIC,
                "bank2_delta_from_Link81_bytes": 19,
                "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
                "entries": EXPECTED_ENTRIES,
                "resolutions": EXPECTED_RESOLUTIONS,
                "roots": EXPECTED_ROOTS,
                "direct_entry_refs": EXPECTED_DIRECT_REFS,
                "product_build_id": EXPECTED_PRODUCT_ID,
                "bank2_sha256": EXPECTED_BANK2_SHA,
            },
            "target_stdlib_header": header_binding,
            "walls": walls,
            "capacity": capacity,
            "wplto": wplto,
            "authority": {
                "contract": bind(T.CONTRACT)
                    if hasattr(T, "CONTRACT") else bind(
                        ROOT / "config/c2-require-resolver-contract.json"),
                "resolver_contract": bind(
                    ROOT / "config/c2-require-resolver-contract.json"),
                "acceptance_row": bind(
                    ROOT / "config/c2-require-prior-append-acceptance.json"),
                "candidate_manifest": bind(TIME_MANIFEST),
                "profile": bind(PROFILE),
                "static_product": bind(product_path),
                "linked_ELF": bind(elf),
                "driver": bind(DRIVER),
            },
            "next_gate": "The commissioned v1.2.5 successor product link.",
            "claim_limit": (
                "One non-promotable product-shaped WPLTO. No successor "
                "product identity, hardware result, acceptance or release "
                "claim is made."
            ),
        }
        RECEIPT.write_bytes(CAN.json_bytes(value))
        print(
            "c2-v125-require-fix-wplto: PASS "
            f"bank2={EXPECTED_STATIC} delta=+19 "
            f"headroom={65536 - EXPECTED_STATIC} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']} links=0"
        )
        return 0
    except (
        OSError,
        KeyError,
        ValueError,
        WPLTOError,
        Exception,
    ) as error:
        print(
            "c2-v125-require-fix-wplto: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
