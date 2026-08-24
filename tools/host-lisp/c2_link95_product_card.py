#!/usr/bin/env python3
"""Bind and execute the one commissioned Link-95 product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_link95_packed_callee_closure as CLOSURE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_packed_symbolic_callee_closure as PACKED  # noqa: E402
import c2_top_level_macro_redispatch_link94 as L94  # noqa: E402


CAN = L94.CAN
V112 = L94.V112
CORE = L94.CORE
BASE = L94.BASE
RELEASE = "post-v1.4-packed-callee-closure"
LINK = 95
DRIVER = Path(__file__).resolve()
PREFLIGHT = CLOSURE.OUT
BUILD = ROOT / "build/c2.3/packed-callee-closure-link95"
MANIFEST = BUILD / "canonical-product-manifest.json"
STATIC = PREFLIGHT / "static-plane/narrow-static"
STATIC_PRODUCT = STATIC / "product"
V6_PLANE = STATIC / "v6-semantics"
STDLIB_PREFIX = STATIC / "stdlib-p0"
STDLIB = STDLIB_PREFIX.with_suffix(".manifest.json")
PREFLIGHT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-product-preflight-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-product-card-receipt.json"
)
HOST_RECEIPT = CLOSURE.RECEIPT
FIRST_RED = CLOSURE.FIRST_RED
CONTRACT = ROOT / "config/c2-top-level-macro-publication.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
HEADER = ROOT / "src/c2_lite_static_plane.h"
GATES = ROOT / "mk/gates.mk"
EXPECTED_STATIC = 45939
EXPECTED_ENTRIES = 753
EXPECTED_RESOLUTIONS = 2920
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 674
EXPECTED_PRODUCT_ID = "0x14d980c3"
EXPECTED_BANK2_SHA = (
    "dc02b18be46f96f2b4e72d6502d4c193ee0dcbee4ee0abf4ca1ebd27f1b7a16d"
)
HISTORICAL_CARD_DRIVER = {
    "path": "tools/host-lisp/c2_link95_product_card.py",
    "bytes": 25664,
    "sha256": "98c7c0f0b8d09798d47d84274dbaabe570cf35683457e003652e4a7bf855cbb0",
}
HISTORICAL_LINK94_PREFLIGHT = L94.PREFLIGHT
HISTORICAL_LINK94_PREFLIGHT_RECEIPT = L94.PREFLIGHT_RECEIPT


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    output = result.stdout.encode()
    return {
        "status": "passed",
        "output_bytes": len(output),
        "output_sha256": hashlib.sha256(output).hexdigest(),
    }


def specs() -> tuple[tuple[str, str, Path], ...]:
    return (
        ("stdlib-p0", "stdlib", STDLIB),
        ("ide", "ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
        ("idex", "idex", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.manifest.json")),
        ("m65d", "m65d", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.manifest.json")),
        ("buffer", "buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
        ("lcc", "lcc", ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"),
    )


def geometry() -> dict[str, Any]:
    product = load(CLOSURE.PRODUCT)
    bank2 = V6_PLANE / "bank2-static-code.bin"
    return {
        "static_code_bytes": sum(int(load(path)["code_bytes"])
                                 for _key, _name, path in specs()),
        "headroom_bytes": 65536 - EXPECTED_STATIC,
        "entries": int(product["entries"]),
        "resolutions": int(product["resolutions"]),
        "roots": int(product["roots"]),
        "direct_entry_refs": L94.direct_entry_census(STATIC_PRODUCT),
        "product_build_id": str(product["product_build_id_hex"]),
        "bank2_sha256": sha(bank2),
    }


def expected_geometry() -> dict[str, Any]:
    return {
        "static_code_bytes": EXPECTED_STATIC,
        "headroom_bytes": 65536 - EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "product_build_id": EXPECTED_PRODUCT_ID,
        "bank2_sha256": EXPECTED_BANK2_SHA,
    }


def regenerate_v6_plane() -> None:
    CLOSURE.restore_bound_authorities()
    if V6_PLANE.exists():
        shutil.rmtree(V6_PLANE)
    old = (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        V6.OUT = V6_PLANE
        V6.PRODUCT_IDENTITY = CLOSURE.PRODUCT
        V6.STATIC_CODE_BYTES = EXPECTED_STATIC
        V6.A.SPECS = specs()
        V6_PLANE.mkdir(parents=True)
        result = V6.host_semantics()
    finally:
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old
    require(result["static_bank2"]["code_bytes"] == EXPECTED_STATIC,
            "Link-95 C2D-v6 code extent drift")


def build_preflight() -> dict[str, Any]:
    require(not PREFLIGHT_RECEIPT.exists(), "Link-95 preflight is one-shot")
    host = load(HOST_RECEIPT)
    CLOSURE.validate_receipt(host)
    regenerate_v6_plane()
    actual = geometry()
    require(actual == expected_geometry(), f"Link-95 preflight geometry drift: {actual}")
    value = {
        "format": "lisp65-c2.3-link95-product-preflight-v1",
        "recorded_on": "2026-08-10",
        "status": "passed-link95-linker-free-input-closure",
        "product_links": 0,
        "wplto_runs": 0,
        "geometry": actual,
        "delta_from_link94": {
            "bank2_code_bytes": 34,
            "entries": 2,
            "resolutions": -1,
            "roots": 0,
            "direct_entry_refs": 0,
            "resident_bytes": 0,
        },
        "authorities": {
            "contract": bind(CONTRACT),
            "host_closure": bind(HOST_RECEIPT),
            "stdlib_manifest": bind(STDLIB),
            "product_manifest": bind(CLOSURE.PRODUCT),
            "bank2": bind(V6_PLANE / "bank2-static-code.bin"),
            "compiler_carrier": bind(specs()[-1][2]),
            "profile": bind(PROFILE),
            "header": bind(HEADER),
            "driver": bind(DRIVER),
        },
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "claim_limit": "Linker-free Link-95 input closure only; no product or hardware claim.",
    }
    PREFLIGHT_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    return value


def validate_preflight(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == "lisp65-c2.3-link95-product-preflight-v1"
        and value.get("status") == "passed-link95-linker-free-input-closure"
        and value.get("product_links") == value.get("wplto_runs") == 0
        and value.get("geometry") == expected_geometry()
        and value.get("delta_from_link94") == {
            "bank2_code_bytes": 34, "entries": 2, "resolutions": -1,
            "roots": 0, "direct_entry_refs": 0, "resident_bytes": 0,
        }
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 0,
            "product_links": 0, "device_contacts": 0,
        },
        "Link-95 preflight claim drift",
    )
    if verify:
        CLOSURE.validate_receipt(load(HOST_RECEIPT))
        require(geometry() == expected_geometry(), "Link-95 input geometry drift")
        current_authorities = {
            "contract": bind(CONTRACT),
            "host_closure": bind(HOST_RECEIPT),
            "stdlib_manifest": bind(STDLIB),
            "product_manifest": bind(CLOSURE.PRODUCT),
            "bank2": bind(V6_PLANE / "bank2-static-code.bin"),
            "compiler_carrier": bind(specs()[-1][2]),
            "profile": bind(PROFILE),
            "header": bind(HEADER),
            "driver": bind(DRIVER),
        }
        # The Link-95 receipt witnesses the carrier bytes of its own world.
        # The living carrier is rebuilt by the selected-product cycle and is
        # validated there by the bound-artifact parity gate.  Keep identity
        # (the delivered role/path) here, but do not make a historical receipt
        # a byte pin on a later product world.
        for role in ("compiler_carrier", "driver"):
            historical_role = value["authorities"][role]
            current_role = current_authorities[role]
            require(historical_role["path"] == current_role["path"],
                    f"Link-95 {role} identity drift")
            current_authorities[role] = historical_role
        require(value["authorities"] == current_authorities,
                "Link-95 preflight authority drift")
        profile = load(PROFILE)
        require(
            profile["bank2_static_code"] == {
                "bytes": EXPECTED_STATIC,
                "headroom_bytes": 65536 - EXPECTED_STATIC,
                "sha256": EXPECTED_BANK2_SHA,
            }
            and profile["entries"] == EXPECTED_ENTRIES
            and profile["resolutions"] == EXPECTED_RESOLUTIONS
            and profile["roots"] == EXPECTED_ROOTS
            and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
            and profile["product_build_id"] == EXPECTED_PRODUCT_ID
            and f"{EXPECTED_STATIC}UL" in HEADER.read_text(encoding="utf-8"),
            "tracked Link-95 profile/header pin drift",
        )


def historical_link94_check() -> int:
    """Verify sealed Link-94 inputs without projecting today's profile onto them."""
    value = load(HISTORICAL_LINK94_PREFLIGHT_RECEIPT)
    require(
        value.get("format") == "lisp65-c2.3-link94-product-preflight-v1"
        and value.get("status") == "passed-link94-linker-free-input-closure"
        and value.get("product_links") == value.get("wplto_runs") == 0
        and value.get("geometry") == {
            "static_code_bytes": 45905,
            "headroom_bytes": 19631,
            "entries": 751,
            "resolutions": 2921,
            "roots": 350,
            "direct_entry_refs": 674,
            "product_build_id": "0x1866da2f",
            "bank2_sha256": (
                "c04e05acf4111d3dd3ad6eb2051c576d6f30e6d73b949acacc80c1ff635bbbe0"
            ),
        }
        and value.get("delta_from_link93") == {
            "bank2_code_bytes": 111, "entries": 3, "resolutions": 8,
            "roots": 0, "direct_entry_refs": 0, "resident_bytes": 0,
        },
        "sealed Link-94 preflight claim drift",
    )
    authorities = value["authorities"]
    require(
        authorities["driver"] == {
            "path": "tools/host-lisp/c2_top_level_macro_redispatch_link94.py",
            "bytes": 34046,
            "sha256": (
                "6a98e902541951b897cdeb485bbfbe9bac8f9273fc40905a193ca14bdae1d2c3"
            ),
        }
        and authorities["stdlib_manifest"] == bind(
            HISTORICAL_LINK94_PREFLIGHT
            / "static-plane/narrow-static/stdlib-p0.manifest.json")
        and authorities["product_manifest"] == bind(
            HISTORICAL_LINK94_PREFLIGHT
            / "static-plane/narrow-static/product/substitution-artifacts.json")
        and authorities["bank2"] == bind(
            HISTORICAL_LINK94_PREFLIGHT
            / "static-plane/narrow-static/v6-semantics/bank2-static-code.bin"),
        "sealed Link-94 preflight artifact drift",
    )
    print("Link-94 product preflight: PASS sealed-artifact authority")
    return 0


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = V112.BASE_BUILD_MANIFEST(wplto, completion)
    value["static_plane"].update({
        "status": "passed-Link95-packed-symbolic-callee-closure-static-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "product_build_id": EXPECTED_PRODUCT_ID,
        "bank2_sha256": EXPECTED_BANK2_SHA,
        "stdlib_manifest": bind(STDLIB),
        "compiler_carrier": bind(specs()[-1][2]),
        "packed_callee_closure": bind(HOST_RECEIPT),
        "linker_free_preflight": bind(PREFLIGHT_RECEIPT),
    })
    value["candidate"] = {
        "release": RELEASE,
        "pre_promotion": True,
        "public_surface_changed": False,
        "source_driver": bind(DRIVER),
    }
    value["session_service"] = {
        "name": "intern-session-service", "slot": 51,
        "bytes": 399, "catalog_records": 52,
    }
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def patch_link94() -> None:
    replacements = {
        "RELEASE": RELEASE, "LINK": LINK, "DRIVER": DRIVER,
        "PREFLIGHT": PREFLIGHT, "BUILD": BUILD, "MANIFEST": MANIFEST,
        "STATIC": STATIC, "STATIC_PRODUCT": STATIC_PRODUCT,
        "V6_PLANE": V6_PLANE, "STDLIB_PREFIX": STDLIB_PREFIX,
        "STDLIB": STDLIB, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "RECEIPT": RECEIPT, "HOST_RECEIPT": HOST_RECEIPT,
        "FIRST_RED": FIRST_RED, "CONTRACT": CONTRACT,
        "EXPECTED_STATIC": EXPECTED_STATIC, "EXPECTED_ENTRIES": EXPECTED_ENTRIES,
        "EXPECTED_RESOLUTIONS": EXPECTED_RESOLUTIONS,
        "EXPECTED_ROOTS": EXPECTED_ROOTS,
        "EXPECTED_DIRECT_REFS": EXPECTED_DIRECT_REFS,
        "EXPECTED_PRODUCT_ID": EXPECTED_PRODUCT_ID,
        "EXPECTED_BANK2_SHA": EXPECTED_BANK2_SHA,
    }
    for name, value in replacements.items():
        setattr(L94, name, value)
    L94.specs = specs
    L94.restore_product_input_authorities = CLOSURE.restore_bound_authorities
    L94.build_manifest = build_manifest
    L94.complete_in_fresh_process = complete_in_fresh_process


def configure_card() -> dict[str, Path]:
    patch_link94()
    return L94.configure_card()


def complete_action() -> int:
    patch_link94()
    return L94.complete_action()


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0,
            "Link-95 fresh-process completion red:\n" + result.stdout)
    paths = BASE.paths(BUILD)
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def freight_gates() -> dict[str, Any]:
    CLOSURE.validate_receipt(load(HOST_RECEIPT))
    validate_preflight(load(PREFLIGHT_RECEIPT), verify=True)
    summaries = {
        "host_closure": run([
            sys.executable, "tools/host-lisp/c2_link95_packed_callee_closure.py",
            "check"], "Link-95 host closure"),
        "packed_product": run([
            sys.executable, "tools/host-lisp/c2_packed_symbolic_callee_closure.py",
            "audit", "--product", CLOSURE.PRODUCT.relative_to(ROOT).as_posix(),
        ], "packed product call closure"),
        "redispatch": run([
            sys.executable, "tools/host-lisp/c2_top_level_macro_redispatch.py",
            "check"], "top-level macro redispatch"),
        "published_call": run([
            sys.executable,
            "tools/host-lisp/c2_top_level_published_value_call_gate.py",
        ], "published top-level call"),
        "locality": run([
            sys.executable, "tools/host-lisp/c2_v111_locality_replay_closure.py",
            "check"], "isolated compiler-locality replay"),
        "performance": run([
            "make", "c2-v110-persistent-performance-check",
        ], "persistent-performance wall"),
    }
    return {
        "mode": "Link-95-packed-symbolic-callee-closure",
        "summaries": summaries,
        "host_closure": bind(HOST_RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "first_red": bind(FIRST_RED),
    }


def derive_card_receipt() -> dict[str, Any]:
    paths = BASE.paths(BUILD)
    internal = load(paths["receipts"] / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = load(MANIFEST)
    require(
        internal["execution_accounting"]["product_closure_links"] == 1
        and replacement["status"] == "passed"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and capacity["session_service_records"] == 1
        and capacity["session_service_bytes"] == 399
        and completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and manifest["static_plane"]["bank2_static_code_bytes"] == EXPECTED_STATIC,
        "Link-95 product closure did not close",
    )
    return {
        "format": "lisp65-c2.3-link95-product-card-v1",
        "recorded_on": "2026-08-10",
        "status": "LINK95-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING",
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 1,
            "product_closure_links": 1,
            "hardware_runs": 0,
        },
        "source": {
            "contract": bind(CONTRACT),
            "host_closure": bind(HOST_RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "first_red": bind(FIRST_RED),
            "driver": bind(DRIVER),
        },
        "geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "resident_delta_bytes": 0,
            "walls": walls,
            "session_capacity": capacity,
        },
        "artifacts": {
            "manifest": bind(MANIFEST),
            "product": bind(paths["final"] / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.elf"),
            "map": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.map"),
            "profile": bind(paths["final"] / "resolved-profile.txt"),
            "bank2": bind(paths["static"] / "v6-semantics/bank2-static-code.bin"),
            "completion": bind(paths["receipts"] / "artifact-completion.json"),
            "internal": bind(paths["receipts"] / "wplto-internal.json"),
        },
        "hardware_handoff": {
            "status": "media-pending",
            "trace_forms": [
                "(require (quote inspect))",
                "(defun trace-probe (x) (+ x 1))",
                "(trace trace-probe)",
                "(trace-probe 4)",
                "(untrace trace-probe)",
                "(trace-probe 4)",
            ],
            "bundled_defstruct_sister": True,
        },
        "claim_limit": (
            "One commissioned Link-95 card after the full packed-callee host "
            "closure; no media, hardware, release, or public-surface claim."
        ),
    }


def validate_card(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == "lisp65-c2.3-link95-product-card-v1"
        and value.get("status")
            == "LINK95-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING"
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_closure_links": 1, "hardware_runs": 0,
        }
        and value["geometry"]["bank2_static_code_bytes"] == EXPECTED_STATIC
        and value["geometry"]["bank2_headroom_bytes"] == 65536 - EXPECTED_STATIC
        and value["geometry"]["resident_delta_bytes"] == 0
        and value["hardware_handoff"]["status"] == "media-pending",
        "Link-95 card claim drift",
    )
    require(value["source"]["driver"] == HISTORICAL_CARD_DRIVER,
            "Link-95 historical driver authority drift")
    if verify:
        # The card witnesses the driver that produced Link 95.  Later source
        # edits must not turn that historical binding into a predicate over
        # the living driver, while all emitted card artifacts remain checked.
        current = derive_card_receipt()
        current["source"]["driver"] = HISTORICAL_CARD_DRIVER
        require(value == current, "Link-95 product card receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=0),
        "hide-link": lambda x: x["attempt_accounting"].update(
            product_closure_links=0),
        "claim-device": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "grow-resident": lambda x: x["geometry"].update(resident_delta_bytes=1),
        "move-bank2": lambda x: x["geometry"].update(bank2_static_code_bytes=45938),
        "claim-media": lambda x: x["hardware_handoff"].update(status="prepared"),
        "replace-historical-driver": lambda x: x["source"]["driver"].update(
            sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_card(candidate, verify=False)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(cases), "Link-95 card mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-95 product card is one-shot")
    preflight = load(PREFLIGHT_RECEIPT)
    validate_preflight(preflight, verify=True)
    freight = freight_gates()
    BUILD.mkdir(parents=True)
    shutil.copytree(PREFLIGHT / "static-plane", BUILD / "static-plane")
    paths = configure_card()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header = CORE.bind_generated_stdlib_header(paths)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and header["manifest"] == bind(STDLIB),
        "Link-95 copied preflight plane failed the product gate",
    )
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"]["current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_headroom_bytes"] >= 0,
            "Link-95 product geometry wall red")
    complete_in_fresh_process()
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = CAN.check()
    require(checked["identity"] == manifest["identity"],
            "Link-95 completed product identity red")
    feature = {
        "status": "passed-Link95-packed-symbolic-callee-feature-gates",
        "freight": freight,
        "target_stdlib_header": header,
    }
    (paths["receipts"] / f"{RELEASE}-feature-gates.json").write_bytes(
        canonical(feature))
    value = derive_card_receipt()
    validate_card(value, verify=False)
    RECEIPT.write_bytes(canonical(value))
    print(
        "Link-95 product card: PASS "
        f"bank2={EXPECTED_STATIC} resident=0 "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}"
    )
    return 0


def check_action() -> int:
    # Link 95 is sealed evidence.  Its preflight proves its own recorded
    # geometry; successor builds must not turn the mutable paths named by the
    # receipt into predicates over the living product world.
    validate_preflight(load(PREFLIGHT_RECEIPT), verify=False)
    if RECEIPT.is_file():
        validate_card(load(RECEIPT), verify=True)
        print("Link-95 product card check: PASS")
    else:
        print("Link-95 product preflight check: PASS card=unconsumed")
    return 0


def selftest() -> int:
    validate_preflight(load(PREFLIGHT_RECEIPT), verify=False)
    count = 0
    if RECEIPT.is_file():
        value = load(RECEIPT)
        validate_card(value, verify=False)
        count = len(mutations(value))
    gates = GATES.read_text(encoding="utf-8")
    require("c2-link95-product-card-check:" in gates,
            "Link-95 product-card gate is not permanent")
    print(f"Link-95 product selftest: PASS card-mutations={count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=(
            "preflight", "build", "_complete", "check", "selftest",
            "historical-link94-check",
        ))
    action = parser.parse_args().action
    if action == "preflight":
        value = build_preflight()
        print("Link-95 preflight: PASS " + json.dumps(value["geometry"], sort_keys=True))
        return 0
    if action == "_complete":
        os.environ.update(CAN.canonical_build_environment())
        return complete_action()
    if action == "build":
        environment = CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy()
            updated.update(environment)
            os.execve(sys.executable, [sys.executable, str(DRIVER), "build"], updated)
        return build_action()
    if action == "historical-link94-check":
        return historical_link94_check()
    if action == "check":
        return check_action()
    return selftest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Link-95 product card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
