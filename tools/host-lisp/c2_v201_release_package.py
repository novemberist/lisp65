#!/usr/bin/env python3
"""Prepare and twice verify the docs-only v2.0.1 Halt-B assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import c2_v200_release_package as BASE
import c2_v201_bundle_docs_gate as DOCS


ROOT = Path(__file__).resolve().parents[2]
VERSION = "2.0.1"
RELEASE = f"v{VERSION}"
TOP = f"lisp65-{VERSION}"
RELEASE_ROOT = ROOT / "build/release-v2.0.1"
DEFAULT_CLEAN_RECEIPT = RELEASE_ROOT / "v2.0.1-public-clean-build-receipt.json"


def readme(product_set: str) -> bytes:
    return (
        "LISP65 WORKBENCH 2.0.1 DOCUMENTATION UPDATE\n"
        "===========================================\n\n"
        "This package corrects the v2.0.0 user documentation.\n"
        "All 19 product artifacts are byte-identical to v2.0.0; the\n"
        "on-device banner therefore remains WORKBENCH 2.0.0.\n"
        f"Product artifact set: {product_set}\n\n"
        "Before use, run:  python3 verify.py\n\n"
        "Media:\n"
        "  media/lisp65-product.d81  bootable, read-only system medium\n"
        "  media/lisp65-work.d81     blank writable work medium\n\n"
        "The documentation now distinguishes the 139-name host metadata\n"
        "population from the 127 identities delivered on the product medium.\n"
        "It also records the actual twenty-one Tier-1 functions and derives\n"
        "the remaining public counts from their product authorities.\n\n"
        "See docs/release-notes.md and docs/known-issues.md.\n"
    ).encode("ascii")


def configure() -> None:
    BASE.VERSION = VERSION
    BASE.RELEASE = RELEASE
    BASE.TOP = TOP
    BASE.PRODUCT_RELEASE = "v2.0.0"
    BASE.PREPARED_ON = "2026-09-03"
    BASE.SOURCE_EPOCH = 1788393600
    BASE.DEFAULT_CLEAN_RECEIPT = DEFAULT_CLEAN_RECEIPT
    BASE.RELEASE_ROOT = RELEASE_ROOT
    BASE.PREPARATION_RECEIPT = (
        RELEASE_ROOT / "v2.0.1-package-preparation-receipt.json")
    BASE.PACKAGE_FORMAT = "lisp65-v2.0.1-release-package-v1"
    BASE.PREPARATION_FORMAT = "lisp65-v201-release-package-preparation-v1"
    BASE.DOCUMENTS = {
        "docs/release-notes.md": ROOT / "docs/releases/2.0.1.md",
        "docs/user-guide.md": ROOT / "docs/user-guide.md",
        "docs/language-reference.md": ROOT / "docs/language-reference.md",
        "docs/known-issues.md": ROOT / "docs/known-issues.md",
        "docs/generated/ide-keymap.md": ROOT / "docs/generated/ide-keymap.md",
    }
    BASE.BUNDLE_DOCS_VALIDATOR = DOCS.validate_bundle
    BASE.readme = readme
    BASE.VERIFIER = BASE.VERIFIER.replace(b"2.0.0", b"2.0.1")
    BASE.COMMON.TOP = TOP
    BASE.COMMON.SOURCE_EPOCH = BASE.SOURCE_EPOCH


def selftest() -> None:
    BASE.selftest()
    rejected = DOCS.selftest()
    BASE.require(len(rejected) == 8,
                 "v2.0.1 bundled-document mutation count drift")
    verifier = BASE.VERIFIER.decode("ascii")
    BASE.require("lisp65-v2.0.1-release-package-v1" in verifier
                 and 'value.get("release") == "v2.0.1"' in verifier,
                 "v2.0.1 offline verifier identity drift")
    print("c2-v201-release-package: SELFTEST PASS "
          "package-mutations=4 docs-mutations=8 double-pack=1")


def main() -> int:
    configure()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("selftest")
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-repository", type=Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument("--product-root", type=Path, default=ROOT)
    prepare_parser.add_argument("--clean-receipt", type=Path,
                                default=DEFAULT_CLEAN_RECEIPT)
    prepare_parser.add_argument("--output", type=Path,
                                default=RELEASE_ROOT / "publish")
    prepare_parser.add_argument("--evidence-receipt", type=Path)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--publish", type=Path,
                              default=RELEASE_ROOT / "publish")
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
        elif args.action == "prepare":
            result = BASE.prepare(
                args.source_repository, args.source_commit,
                args.product_root, args.clean_receipt.resolve(),
                args.output.resolve())
            if args.evidence_receipt is not None:
                evidence = args.evidence_receipt
                if not evidence.is_absolute():
                    evidence = ROOT / evidence
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_bytes(BASE.canonical(result))
            print("c2-v201-release-package: PREPARED "
                  f"assets=4 roles=19 source={result['source_commit']} "
                  f"set={result['product']['artifact_set_sha256']}")
        else:
            result = BASE.check(args.publish.resolve())
            print("c2-v201-release-package: CHECK PASS "
                  f"assets=4 roles=19 source={result['source_commit']}")
        return 0
    except (BASE.PackageError, BASE.COMMON.PackageError, OSError, KeyError,
            ValueError, json.JSONDecodeError) as error:
        print(f"c2-v201-release-package: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
