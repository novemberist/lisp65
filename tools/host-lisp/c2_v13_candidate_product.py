#!/usr/bin/env python3
"""Build/check the regular v1.3.0 Ship candidate as Link 84."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v126_candidate_product as PREV  # noqa: E402
import c2_v13_ship_freight_wplto as JOINT  # noqa: E402
import c2_q_gate as Q  # noqa: E402
import c2_random_base_gate as RANDOM  # noqa: E402
import c2_while_gate as WHILE  # noqa: E402


PRODUCT = PREV.PRODUCT
CAN = PRODUCT.CAN
V = PRODUCT.V
BASE = PRODUCT.BASE
RELEASE = "v1.3.0"
LINK = 84
BUILD = ROOT / "build/c2.3/v1.3.0-candidate-product-link84-r1"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD = EVIDENCE / "c2.3-v1.3-bank2-read-line-wplto-receipt.json"
BANNER_REBIND = EVIDENCE / "c2.3-v1.3-banner-identity-rebind-receipt.json"
INPUT_RECEIPT = EVIDENCE / "c2.2-v1.3-ship-input-wait-host-first-receipt.json"
Q_RECEIPT = EVIDENCE / "c2.2-v1.3-q-host-first-receipt.json"
EDITOR_RECEIPT = EVIDENCE / "c2-v126-editor-allocation-gate-receipt.json"
PUBLIC_FREIGHT = ROOT / (
    "build/c2.3/v1.3.0-public-current/source-freight.json"
)
STDLIB = JOINT.INPUT_MANIFEST
IDE = JOINT.CURRENT_IDE
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
EXPECTED_STATIC = 45514
EXPECTED_ENTRIES = 757
EXPECTED_RESOLUTIONS = 2947
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
EXPECTED_PRODUCT_ID = "0x74e2765d"
EXPECTED_BANK2_SHA = (
    "49658f5239abf867a29875a1464629f1885d3dab58102077fda5ba19af882589"
)


class CandidateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CandidateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"candidate authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def bind_current_specs() -> None:
    req = BASE.PROBE.REQ
    specs = tuple(
        (
            key, name,
            STDLIB if key == "stdlib-p0" else IDE if key == "ide" else path,
        )
        for key, name, path in req.SPECS
    )
    require(
        len(specs) == 6
        and sum(key == "stdlib-p0" for key, _name, _path in specs) == 1
        and sum(key == "ide" for key, _name, _path in specs) == 1,
        "Link-84 six-image inventory lacks unique stdlib/IDE roles",
    )
    req.SPECS = specs
    req.EXPECTED_STATIC = EXPECTED_STATIC
    req.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    req.F1W.SPECS = specs
    req.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    req.F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    CAN.SPECS = specs
    CAN.PREFIXES = tuple(
        (
            path.with_suffix(""),
            "stdlib" if index == 0 else "disk-lib",
            None if index == 0 else "0x000000",
        )
        for index, (_key, _name, path) in enumerate(specs)
    )


def configure() -> dict[str, Path]:
    V.RANDOM_MANIFEST = STDLIB
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    V.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    V.configure_candidate()
    BASE.LINK = LINK
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    V.bind_candidate_specs()
    bind_current_specs()
    plane_gate = BASE.PROBE.REQ.F1W.PLANE
    plane_gate.FRESH_PRODUCT = (
        paths["static_product"] / "substitution-artifacts.json")
    plane_gate.FRESH_IDE = IDE
    plane_gate.FRESH_BANK2 = paths["v6"] / "bank2-static-code.bin"
    plane_gate.FRESH_MANIFESTS = tuple(
        path for _key, _name, path in CAN.SPECS)
    os.environ.update(CAN.canonical_build_environment())
    return paths


def emit_inherited_manifests() -> dict[str, Any]:
    V.RANDOM_MANIFEST = STDLIB
    V.configure_candidate()
    bind_current_specs()
    specs = tuple(CAN.SPECS)
    require(
        len(specs) == 6 and all(path.is_file() for _k, _n, path in specs),
        "Link-84 current-source manifest inventory incomplete",
    )
    return {
        "status": "passed-six-source-emitted-predecessor-manifests",
        "selection": "v1.3-current-stdlib-and-editor-manifests",
        "manifests": [bind(path) for _key, _name, path in specs],
    }


def freight_gates() -> dict[str, Any]:
    public_build = (
        os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
        or not CARD.is_file()
    )
    if public_build:
        os.environ["LISP65_PUBLIC_CURRENT_SOURCE_BUILD"] = "1"
        # The q/random suite chain and the surface gate consume the complete
        # generated Workbench artifact family.  A proof worktree normally
        # inherits those files from earlier gates; a fresh public clone must
        # materialize them before any freight gate runs.  Invoke the canonical
        # producer rather than reproducing any part of its emission sequence.
        run(
            ["make", "--no-print-directory", "v2-workbench-artifacts"],
            "v1.3 public Workbench artifact generation",
        )
        while_summary = run(
            [sys.executable, "tools/host-lisp/c2_while_gate.py"],
            "v1.3 public while carrier generation and execution",
        )
        fasl_summary = run(
            ["make", "--no-print-directory", "fasl-emit-check"],
            "v1.3 public real-compiler L65M oracle",
        )
    q_summary: str
    if public_build:
        require(Q.main(public_build=True) == 0, "v1.3 public q gate red")
        q_summary = "c2-q-gate: PASS public-current-source"
    else:
        q_summary = run(
            [sys.executable, "tools/host-lisp/c2_q_gate.py"],
            "v1.3 q gate",
        )
    summaries = {
        "banner": run(
            [sys.executable, "tools/host-lisp/c2_repl_banner_version_gate.py",
             "--selftest"],
            "v1.3 banner gate",
        ),
        "input_wait": run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "v1.3 input/wait gate",
        ),
        "q": q_summary,
        "editor": run(
            [sys.executable,
             "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
            "v1.3 editor allocation gate",
        ),
        "surface": run(
            [sys.executable,
             "tools/host-lisp/v11_surface_delivery_parity.py"],
            "v1.3 surface-delivery parity",
        ),
    }
    if public_build:
        require(
            RANDOM.main(public_build=True) == 0,
            "v1.3 public random gate red",
        )
        for prefix, suite in PREV.PREV.REQUIRE_LIBRARY_INPUTS:
            prefix.parent.mkdir(parents=True, exist_ok=True)
            run(
                [
                    sys.executable,
                    "tools/host-lisp/bytecode_p0_stdlib.py",
                    "--check",
                    "--emit-artifacts",
                    prefix.relative_to(ROOT).as_posix(),
                    "--artifact-role",
                    "disk-lib",
                    "--base-addr",
                    "0x000000",
                    suite.relative_to(ROOT).as_posix(),
                ],
                f"v1.3 public require input {suite.stem}",
            )
        summaries.update({
            "random": "c2-random-base-gate: PASS public-current-source",
            "while": while_summary,
            "real_compiler_L65M": fasl_summary,
            "resolver": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_resolver_gate.py"],
                "v1.3 public require resolver gate",
            ),
            "prior_append": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_prior_append_option_a_gate.py"],
                "v1.3 public prior-append gate",
            ),
            "fastpath": run(
                [sys.executable,
                 "tools/host-lisp/c2_require_idempotence_fastpath.py"],
                "v1.3 public require fastpath gate",
            ),
        })
        input_receipt = load(INPUT_RECEIPT)
        q_receipt = load(Q.PUBLIC_BUILD_RECEIPT)
        while_receipt = load(WHILE.RECEIPT)
        editor = load(EDITOR_RECEIPT)
        option = load(PREV.PREV.OPTION_A)
        fastpath = load(PREV.PREV.FASTPATH)
        profile = load(PROFILE)
        require(
            input_receipt["status"]
                == "passed-bank2-lisp-source-artifact-allocation-and-execution"
            and q_receipt["status"]
                == "passed-q-current-source-artifact-public-build"
            and q_receipt["composition"]["private_evidence_inputs"] == 0
            and while_receipt["status"]
                == "passed-four-view-while-successor-link-authorized-not-run"
            and while_receipt["bound_device_carrier"]["manifest"]["sha256"]
                == bind(WHILE.CARRIER_PREFIX.with_suffix(".manifest.json"))[
                    "sha256"
                ]
            and editor["status"] == "passed"
            and option["authority"]["private_evidence_inputs"] == 0
            and fastpath["baseline_repeat"]["private_evidence_inputs"] == 0
            and profile["product_build_id"] == EXPECTED_PRODUCT_ID
            and profile["bank2_static_code"]["sha256"]
                == EXPECTED_BANK2_SHA,
            "v1.3 public current-source freight drift",
        )
        value = {
            "format": "lisp65-v1.3-public-current-source-freight-v1",
            "version": 1,
            "status": "passed-without-private-evidence-inputs",
            "private_evidence_inputs": 0,
            "summaries": summaries,
            "input_wait": bind(INPUT_RECEIPT),
            "q": bind(Q.PUBLIC_BUILD_RECEIPT),
            "while_carrier": bind(
                WHILE.CARRIER_PREFIX.with_suffix(".manifest.json")
            ),
            "while_tier_generation": bind(WHILE.TIER_RECEIPT),
            "real_compiler_L65M": bind(
                ROOT / "build/equivalence/fasl-test.bin"
            ),
            "editor": bind(EDITOR_RECEIPT),
            "require_option_A": bind(PREV.PREV.OPTION_A),
            "require_idempotence_fastpath": bind(PREV.PREV.FASTPATH),
            "banner_source": bind(ROOT / "lib/repl-banner.lisp"),
            "banner_authority": bind(ROOT / "config/v12-known-issues.json"),
        }
        PUBLIC_FREIGHT.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_FREIGHT.write_bytes(CAN.json_bytes(value))
        return {
            "mode": "v1.3-public-current-source-without-private-history",
            "private_evidence_inputs": 0,
            "summaries": summaries,
            "public_current_source": bind(PUBLIC_FREIGHT),
        }
    card = load(CARD)
    rebind = load(BANNER_REBIND)
    input_receipt = load(INPUT_RECEIPT)
    q_receipt = load(Q_RECEIPT)
    editor = load(EDITOR_RECEIPT)
    profile = load(PROFILE)
    require(
        card["status"] == "passed-v1.3-joint-one-product-shaped-WPLTO"
        and card["inherited_native_geometry"]["status"] == "restored-exactly"
        and card["inherited_native_geometry"]["noinit_bytes"] == 6
        and card["inherited_native_geometry"]["overlay_floor"] == "0xc354"
        and rebind["status"]
            == "passed-linker-free-regular-v1.3-banner-identity-rebind"
        and rebind["final_plane"]["product_build_id"] == EXPECTED_PRODUCT_ID
        and input_receipt["status"]
            == "passed-bank2-lisp-source-artifact-allocation-and-execution"
        and input_receipt["artifacts"]["allocation"][
            "maximum_cells_per_key"] <= 4
        and len(input_receipt["mutations_rejected"]) == 14
        and q_receipt["status"].startswith("passed-")
        and editor["status"] == "passed"
        and profile["product_build_id"] == EXPECTED_PRODUCT_ID
        and profile["bank2_static_code"]["sha256"] == EXPECTED_BANK2_SHA,
        "Link-84 freight authority drift",
    )
    return {
        "mode": "v1.3-current-source-ship-public-surface",
        "summaries": summaries,
        "input_wait": bind(INPUT_RECEIPT),
        "q": bind(Q_RECEIPT),
        "editor": bind(EDITOR_RECEIPT),
        "accepted_native_geometry": bind(CARD),
        "regular_banner_identity": bind(BANNER_REBIND),
    }


def build_manifest(
    wplto: dict[str, Any], completion: dict[str, Any],
) -> dict[str, Any]:
    value = PREV.PREV.LINK81._inherited_build_manifest(wplto, completion)
    plane = value["static_plane"]
    public_build = (
        os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
    )
    input_receipt = INPUT_RECEIPT
    q_receipt = Q.PUBLIC_BUILD_RECEIPT if public_build else Q_RECEIPT
    accepted_geometry = PUBLIC_FREIGHT if public_build else CARD
    banner_identity = (
        ROOT / "config/v12-known-issues.json"
        if public_build else BANNER_REBIND
    )
    plane.update({
        "status": "passed-v1.3-ship-single-emitter-static-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "product_build_id": EXPECTED_PRODUCT_ID,
        "bank2_sha256": EXPECTED_BANK2_SHA,
        "stdlib_manifest": bind(STDLIB),
        "ide_manifest": bind(IDE),
        "ship_contract": bind(ROOT / "config/ship-builder-v1.json"),
        "input_wait_contract": bind(
            ROOT / "config/c2-ship-input-wait-contract.json"),
        "q_contract": bind(ROOT / "config/c2-q-contract.json"),
        "editor_contract": bind(
            ROOT / "config/c2-v126-editor-allocation-contract.json"),
        "accepted_native_geometry": bind(accepted_geometry),
        "regular_banner_identity": bind(banner_identity),
        "require_option_A": {
            "contract": bind(PREV.PREV.RESOLVER_CONTRACT),
            "host_execution_gate": bind(PREV.PREV.OPTION_A),
            "idempotence_fastpath": bind(PREV.PREV.FASTPATH),
            "acceptance_row": bind(PREV.PREV.ACCEPTANCE),
        },
    })
    if public_build:
        plane["public_current_source_freight"] = bind(PUBLIC_FREIGHT)
        plane["input_wait_execution"] = bind(input_receipt)
        plane["q_execution"] = bind(q_receipt)
    plane.pop("random_manifest", None)
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = bind(DRIVER)
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = load(path)
    value.update(freight)
    value["status"] = "passed-v1.3-current-source-ship-feature-gates"
    path.write_bytes(CAN.json_bytes(value))


PRODUCT.__doc__ = __doc__
PRODUCT.RELEASE = RELEASE
PRODUCT.LINK = LINK
PRODUCT.BUILD = BUILD
PRODUCT.MANIFEST = MANIFEST
PRODUCT.DRIVER = DRIVER
PRODUCT.configure = configure
PRODUCT.emit_inherited_manifests = emit_inherited_manifests
PRODUCT.build_manifest = build_manifest
PRODUCT.V.RANDOM_MANIFEST = STDLIB
PRODUCT.V.EXPECTED_STATIC = EXPECTED_STATIC
PRODUCT.V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
PRODUCT.V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
PRODUCT.V.EXPECTED_ROOTS = EXPECTED_ROOTS
PRODUCT.V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
PRODUCT.V.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
PRODUCT.V.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else None
    freight: dict[str, Any] | None = None
    if action == "build":
        freight = freight_gates()
        PRODUCT.V.feature_gates = PREV.PREV.current_random_while_feature_gates
    result = PRODUCT.main()
    if result == 0 and action == "build" and freight is not None:
        augment_feature_receipt(freight)
        print(
            "c2-v1.3.0-candidate-product: FREIGHT PASS "
            "ship=4 input=Bank2 q=public editor=Link83 "
            f"bank2={EXPECTED_STATIC} resident=+0"
        )
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CandidateError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"c2-v1.3.0-candidate-product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
