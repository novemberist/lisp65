#!/usr/bin/env python3
"""Build/check the regular v1.2.6 editor-latency candidate as Link 83."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v125_candidate_product as PREV  # noqa: E402


PRODUCT = PREV.PRODUCT
CAN = PRODUCT.CAN
V = PRODUCT.V
BASE = PRODUCT.BASE
RELEASE = "v1.2.6"
LINK = 83
BUILD = ROOT / "build/c2.2/v1.2.6-candidate-product-link83"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
WPLTO = EVIDENCE / "c2.2-v1.2.6-editor-wplto-receipt.json"
PROFILE_PREFLIGHT = EVIDENCE / (
    "c2.2-v1.2.6-editor-profile-preflight-receipt.json")
BANNER_REBIND = EVIDENCE / (
    "c2.2-v1.2.6-banner-identity-rebind-receipt.json")
EDITOR_RECEIPT = EVIDENCE / (
    "c2-v126-editor-allocation-gate-receipt.json")
CURRENT_IDE = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
TIME_MANIFEST = PREV.TIME_MANIFEST
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
EXPECTED_STATIC = 45063
EXPECTED_ENTRIES = 750
EXPECTED_RESOLUTIONS = 2931
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
EXPECTED_PRODUCT_ID = "0x0934e4f0"
EXPECTED_BANK2_SHA = (
    "8d9a7f8fde18543d78033b73dbe74cc3d15453f1f8ef507a6fb45fb90ca28ccd")


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
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def bind_editor_spec() -> None:
    req = BASE.PROBE.REQ
    specs = tuple(
        (key, name, CURRENT_IDE if key == "ide" else path)
        for key, name, path in req.SPECS
    )
    require(
        len(specs) == 6
        and sum(key == "ide" for key, _name, _path in specs) == 1,
        "Link-83 six-image inventory has no unique IDE role",
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
    V.RANDOM_MANIFEST = TIME_MANIFEST
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
    bind_editor_spec()
    os.environ.update(CAN.canonical_build_environment())
    return paths


def emit_inherited_manifests() -> dict[str, Any]:
    """Bind the six already source-emitted current manifests.

    The v1.2.6 host gate emitted IDE/IDEX/M65D; the accepted fx/time and
    while lanes emitted the two changing base roles.  Re-emitting the old
    substitution paths here would overwrite the historical IDE delta
    baseline, so Link 83 binds the selected producers directly.
    """
    V.RANDOM_MANIFEST = TIME_MANIFEST
    V.configure_candidate()
    bind_editor_spec()
    specs = tuple(CAN.SPECS)
    require(
        len(specs) == 6 and all(path.is_file() for _k, _n, path in specs),
        "Link-83 current-source manifest inventory incomplete",
    )
    return {
        # The inherited build action consumes this stable status token.  The
        # additional field records that Link 83 selects current producer
        # paths rather than overwriting the historical IDE delta baseline.
        "status": "passed-six-source-emitted-predecessor-manifests",
        "selection": "current-producer-manifests-without-history-overwrite",
        "manifests": [bind(path) for _key, _name, path in specs],
    }


def freight_gates() -> dict[str, Any]:
    summaries = {
        "banner": run(
            [sys.executable,
             "tools/host-lisp/c2_repl_banner_version_gate.py",
             "--selftest"],
            "v1.2.6 banner gate",
        ),
        "editor": run(
            [sys.executable,
             "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
            "v1.2.6 editor allocation gate",
        ),
        "resolver": run(
            [sys.executable,
             "tools/host-lisp/c2_require_resolver_gate.py"],
            "v1.2.6 require resolver gate",
        ),
        "prior_append": run(
            [sys.executable,
             "tools/host-lisp/c2_require_prior_append_option_a_gate.py"],
            "v1.2.6 prior-append gate",
        ),
        "fastpath": run(
            [sys.executable,
             "tools/host-lisp/c2_require_idempotence_fastpath.py"],
            "v1.2.6 require fastpath gate",
        ),
    }
    editor = load(EDITOR_RECEIPT)
    wplto = load(WPLTO)
    rebind = load(BANNER_REBIND)
    preflight = load(PROFILE_PREFLIGHT)
    profile = load(PROFILE)
    require(
        editor["status"] == "passed"
        and wplto["status"] == "passed-editor-one-product-shaped-WPLTO"
        and rebind["status"]
            == "passed-linker-free-regular-release-banner-identity-rebind"
        and preflight["geometry"]["product_build_id"] == EXPECTED_PRODUCT_ID
        and profile["product_build_id"] == EXPECTED_PRODUCT_ID
        and profile["bank2_static_code"]["sha256"] == EXPECTED_BANK2_SHA,
        "Link-83 editor/profile authority drift",
    )
    return {
        "mode": "v1.2.6-private-current-source-editor-authority",
        "summaries": summaries,
        "editor_gate": bind(EDITOR_RECEIPT),
        "editor_wplto": bind(WPLTO),
        "profile_preflight": bind(PROFILE_PREFLIGHT),
        "banner_identity_rebind": bind(BANNER_REBIND),
    }


def build_manifest(
    wplto: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    value = PREV.LINK81._inherited_build_manifest(wplto, completion)
    plane = value["static_plane"]
    plane.update({
        "status": "passed-v1.2.6-editor-single-emitter-static-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "product_build_id": EXPECTED_PRODUCT_ID,
        "bank2_sha256": EXPECTED_BANK2_SHA,
        "fx_time_manifest": bind(TIME_MANIFEST),
        "editor_manifest": bind(CURRENT_IDE),
        "editor_contract": bind(
            ROOT / "config/c2-v126-editor-allocation-contract.json"),
        "editor_wplto": bind(WPLTO),
        "banner_identity_rebind": bind(BANNER_REBIND),
        "require_option_A": {
            "contract": bind(PREV.RESOLVER_CONTRACT),
            "host_execution_gate": bind(PREV.OPTION_A),
            "idempotence_fastpath": bind(PREV.FASTPATH),
            "acceptance_row": bind(PREV.ACCEPTANCE),
        },
    })
    plane.pop("random_manifest", None)
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = bind(DRIVER)
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = load(path)
    value.update(freight)
    value["status"] = (
        "passed-v1.2.6-current-source-editor-and-inherited-feature-gates")
    path.write_bytes(CAN.json_bytes(value))


# Rebind the inherited canonical producer to the regular successor.
PRODUCT.__doc__ = __doc__
PRODUCT.RELEASE = RELEASE
PRODUCT.LINK = LINK
PRODUCT.BUILD = BUILD
PRODUCT.MANIFEST = MANIFEST
PRODUCT.DRIVER = DRIVER
PRODUCT.configure = configure
PRODUCT.emit_inherited_manifests = emit_inherited_manifests
PRODUCT.build_manifest = build_manifest
PRODUCT.V.RANDOM_MANIFEST = TIME_MANIFEST
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
        PRODUCT.V.feature_gates = PREV.current_random_while_feature_gates
    result = PRODUCT.main()
    if result == 0 and action == "build" and freight is not None:
        augment_feature_receipt(freight)
        print(
            "c2-v1.2.6-candidate-product: FREIGHT PASS "
            "editor=+1826 bank2=45063 resident=+0")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CandidateError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-v1.2.6-candidate-product: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
