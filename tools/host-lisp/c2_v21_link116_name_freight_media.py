#!/usr/bin/env python3
"""Rebuild the Link-116 library medium from the accepted name-freight inputs.

The Link-116 product medium is immutable input.  This successor repairs only
the library side of the same-world pair after the device proved that the
post-2.0 media lineage had silently returned to the pre-freight variants.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v112_candidate_media as LIB  # noqa: E402
import c2_v150_name_freight_media as FREIGHT  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-link116-name-freight-media"
LIBRARY = BUILD / "library"
PRODUCT = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-media/shared-system/"
    "lisp65-product.d81")
PRODUCT_MANIFEST = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/"
    "canonical-product-manifest.json")
OLD_LIBRARY = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-media-base/library")
OLD_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-base-media-receipt.json")
COMPLETION_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-completion-media-receipt.json")
FREIGHT_RECEIPT = ARCH / "c2.3-v1.5.0-name-freight-media-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-link116-name-freight-media-receipt.json"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v2.1-link116-name-freight-media-v1"
STATUS = "PASS: LINK-116 SAME-WORLD NAME-FREIGHT LIBRARY MEDIA"
FREIGHT_SEALED_COMMIT = "c2aadc022b36f2cbe713b8e184d17e2c9724fcd8"
LINK116_SEALED_COMMIT = "eb2047995cd945584a81357ea905e37d74b60c71"


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


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


def content_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("bytes", "sha256")}


def product_build_id() -> int:
    value = load(PRODUCT_MANIFEST)
    build_id = int(value["static_plane"]["product_build_id"], 0)
    require(build_id == 0x0401E53E, "Link-116 product-world identity drift")
    return build_id


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: ast.unparse(node) for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = (functions.get("build_library", "") + "\n"
             + functions.get("library_facts", ""))
    derive_text = functions.get("derive", "")
    require(
        "LIB.VARIANTS = FREIGHT.VARIANTS" in build
        and "LIB.build_library_variant" in build
        and "PAIR.pair_identity(PRODUCT" in derive_text
        and "OLD.VARIANTS" not in build,
        "Link-116 library producer can fall back to pre-freight variants")
    return {
        "status": "PASS: freight variants are the sole library producer input",
        "product_links": 0,
        "WPLTO_runs": 0,
        "product_media_builds": 0,
        "library_media_builds": 1,
    }


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "restore-pre-freight-variants": source.replace(
            "        LIB.VARIANTS = FREIGHT.VARIANTS\n",
            "        LIB.VARIANTS = OLD.VARIANTS\n", 1),
        "drop-real-library-builder": source.replace(
            "\n                  else LIB.build_library_variant)",
            "\n                  else LIB.existing_library_variant)", 1),
        "drop-pair-identity": source.replace(
            "\n    pair = PAIR.pair_identity(PRODUCT",
            "\n    pair = PAIR.pair_identity(OLD_LIBRARY / 'bad.d81'", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "name-freight successor mutation survived")
    return rejected


def library_facts(*, existing: bool) -> dict[str, Any]:
    old = LIB.VARIANTS
    try:
        LIB.VARIANTS = FREIGHT.VARIANTS
        action = (LIB.existing_library_variant if existing
                  else LIB.build_library_variant)
        value = action("v1.5", LIBRARY, product_build_id())
    finally:
        LIB.VARIANTS = old
    require(
        [row["name"] for row in value["index_rows"]]
            == ["string-extra", "inspect", "place", "defstruct"]
        and value["resolver_contracts"]["defstruct"][
            "declared_dependency_closure"] == [2, 3]
        and value["index_mutations_rejected"] == 32,
        "optimized library semantic closure drift")
    return value


def authority() -> dict[str, Any]:
    old = load(OLD_RECEIPT)
    freight = load(FREIGHT_RECEIPT)
    require(
        OLD_RECEIPT.read_bytes() == ERA.era_blob(
            LINK116_SEALED_COMMIT, OLD_RECEIPT.relative_to(ROOT).as_posix())
        and COMPLETION_RECEIPT.read_bytes() == ERA.era_blob(
            LINK116_SEALED_COMMIT,
            COMPLETION_RECEIPT.relative_to(ROOT).as_posix())
        and FREIGHT_RECEIPT.read_bytes() == ERA.era_blob(
            FREIGHT_SEALED_COMMIT,
            FREIGHT_RECEIPT.relative_to(ROOT).as_posix())
        and old.get("library", {}).get("D81") is not None
        and freight.get("status") ==
            "V150-NAME-FREIGHT-HOST-AND-MEDIA-GREEN; FRESH-D1-PENDING"
        and freight.get("library", {}).get("inspect_manifest") is not None
        and freight.get("library", {}).get("defstruct_manifest") is not None,
        "predecessor or accepted freight authority drift")
    return {"predecessor_media": bind(OLD_RECEIPT),
            "Link116_completion": bind(COMPLETION_RECEIPT),
            "accepted_name_freight_media": bind(FREIGHT_RECEIPT),
            "product_manifest": bind(PRODUCT_MANIFEST)}


def derive(*, existing: bool = True) -> dict[str, Any]:
    facts = library_facts(existing=existing)
    freight = load(FREIGHT_RECEIPT)["library"]["artifacts"]
    old = load(OLD_RECEIPT)["library"]["artifacts"]
    require(
        {key: content_identity(value) for key, value in facts["artifacts"].items()}
            == {key: content_identity(value) for key, value in freight.items()}
        and content_identity(facts["D81"]) == content_identity(
            load(FREIGHT_RECEIPT)["library"]["D81"])
        and content_identity(facts["artifacts"]["string-extra"])
            == content_identity(old["string-extra"])
        and content_identity(facts["artifacts"]["place"])
            == content_identity(old["place"])
        and content_identity(facts["artifacts"]["inspect"])
            != content_identity(old["inspect"])
        and content_identity(facts["artifacts"]["defstruct"])
            != content_identity(old["defstruct"]),
        "successor did not preserve the exact authorized freight delta")
    pair = PAIR.pair_identity(PRODUCT, LIBRARY / "lisp65-library.d81")
    require(pair.get("result") == "same-world-pair"
            and pair.get("product_build_id") == "0x0401e53e",
            "Link-116 product/library world identity red")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "first_red": {
            "device_result": "too many symbols at require defstruct",
            "cause": "post-2.0 media lineage consumed pre-freight VARIANTS",
            "product_bytes_implicated": False,
        },
        "attempt_accounting": {
            "product_links": 0, "WPLTO_runs": 0, "product_cards": 0,
            "product_media_builds": 0, "library_media_builds": 1,
            "device_contacts": 0,
        },
        "authority": authority(),
        "producer_gate": source_gate(),
        "product_medium": bind(PRODUCT),
        "retired_library_medium": bind(OLD_LIBRARY / "lisp65-library.d81"),
        "library": facts,
        "pair_identity": pair,
        "claim_limit": (
            "Media-only restoration of the accepted name-freight library "
            "inputs against unchanged Link-116 product bytes; no device or "
            "D1-D5 claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "WPLTO_runs": 0, "product_cards": 0,
            "product_media_builds": 0, "library_media_builds": 1,
            "device_contacts": 0}
        and value.get("pair_identity", {}).get("result") == "same-world-pair"
        and value.get("first_red", {}).get("product_bytes_implicated") is False,
        "Link-116 name-freight media claim drift")
    if verify:
        require(value == derive(), "Link-116 name-freight media receipt stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-product-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(device_contacts=1),
        "accept-cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "implicate-product": lambda x: x["first_red"].update(product_bytes_implicated=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "successor receipt mutation survived")
    return rejected


def build_library() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-116 name-freight successor output already exists")
    source_gate(); source_mutations(); authority()
    product_before = bind(PRODUCT)
    library_facts(existing=False)
    require(bind(PRODUCT) == product_before, "library build changed product medium")
    value = derive()
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("Link-116 name-freight media: PASS same-world rows=4 mutations=7")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value), "receipt mutation set drift")
    print("Link-116 name-freight media check: PASS same-world rows=4")
    return 0


def selftest() -> int:
    source_gate(); source_mutations(); authority()
    print("Link-116 name-freight media selftest: PASS mutations=3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    return {"build": build_library, "check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MediaError, LIB.MediaClosureError, PAIR.ClosureError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"LINK-116 NAME-FREIGHT MEDIA: {error}", file=sys.stderr)
        raise SystemExit(1)
