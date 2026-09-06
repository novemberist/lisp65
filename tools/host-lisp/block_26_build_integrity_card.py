#!/usr/bin/env python3
"""Permanent checks and the explicit historical-receipt seal for block 2.6 card 5."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import r6_g6 as G6  # noqa: E402


RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-receipt.json"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_texts(root: Path) -> dict[str, str]:
    paths = ["Makefile", "mk/workbench.mk", "mk/toolchain.mk", "mk/gates.mk",
             "mk/runtime-core-v2-proof.mk", "README.md", "CONTRIBUTING.md",
             "docs/development.md", "docs/toolchain-setup.md"]
    return {name: (root / name).read_text(encoding="utf-8") for name in paths}


def validate(text: dict[str, str]) -> dict[str, Any]:
    workbench = text["mk/workbench.mk"]
    make = text["Makefile"]
    gates = text["mk/gates.mk"]
    toolchain = text["mk/toolchain.mk"]
    all_make = "\n".join(text[name] for name in text if name == "Makefile" or name.startswith("mk/"))
    require("if test -f build/c2.3/" not in workbench,
            "product lifecycle still selects verify from artifact existence")
    releases = ("", "-v160", "-v170", "-v180", "-v190", "-v200")
    for release in releases:
        require(f"workbench-product{release}-build:" in workbench
                and f"workbench-product{release}-verify:" in workbench,
                f"explicit product build/verify targets absent: {release or 'v150'}")
        require(f"workbench-product{release}-build: toolchain-external-product-verify" in workbench
                and f"workbench-product{release}-verify: toolchain-external-product-verify" in workbench,
                f"product lifecycle bypasses toolchain verification: {release or 'v150'}")
    require("python3 $(WORKBENCH_PRODUCT_TOOL) build --release" in workbench
            and "python3 $(WORKBENCH_PRODUCT_TOOL) verify --release" in workbench,
            "parameterized product lifecycle front end is not the target authority")
    require("check-product: check-host toolchain-external-product-verify" in gates
            and "workbench-product" in gates,
            "check-product does not verify toolchain and source-bound product bytes")
    require("toolchain-external-product-verify:" in toolchain
            and "--product-build-only" in toolchain
            and "--llvm-mos-root '$(LLVM_MOS_ROOT)'" in toolchain,
            "product path does not verify the toolchain it consumes")
    require("$(shell" not in all_make,
            "Make parse-time shell execution remains")
    require("/tmp/lisp65" not in all_make,
            "build log still escapes the build/ ownership root")
    require("R6_G6_PREFLIGHT_RECEIPT := build/" in make
            and "R6_G6_PROFILE_RECEIPT := build/" in make
            and "r6-g6-receipts-seal:" in make,
            "R6/G6 producer still writes tracked evidence or lacks explicit seal")
    development = text["docs/development.md"]
    require("sole build-command authority" in development
            and "make workbench-product-v200-build" in development
            and "make workbench-product-v200-verify" in development
            and "mega65_ftp" in development and "cmp \"$D81\"" in development,
            "development guide lacks the clone-to-deploy authoritative flow")
    for name in ("README.md", "CONTRIBUTING.md", "docs/toolchain-setup.md"):
        require("make workbench-product" not in text[name]
                and "Development Guide" in text[name],
                f"duplicate build authority remains in {name}")
    return {
        "explicit_product_lifecycles": 6,
        "toolchain_verified_on_product_path": True,
        "parse_time_shell_occurrences": 0,
        "tmp_log_occurrences": 0,
        "generated_r6_g6_receipts": 2,
        "explicit_r6_g6_seal": True,
        "single_build_authority": "docs/development.md",
    }


def lifecycle_mutation() -> str:
    completed = subprocess.run(
        [sys.executable, "tools/host-lisp/workbench_product.py", "selftest"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    require(completed.returncode == 0 and "changed-source-before-old-bytes" in completed.stdout,
            f"changed-source lifecycle mutation failed:\n{completed.stdout}")
    return "changed-source-cannot-verify-old-product-bytes"


def selftest() -> dict[str, Any]:
    clean = source_texts(ROOT)
    validate(clean)
    mutations = {
        "artifact-existence-selects-check": ("mk/workbench.mk", "\nif test -f build/c2.3/old; then :; fi\n"),
        "product-toolchain-edge-removed": ("mk/gates.mk", clean["mk/gates.mk"].replace(
            "check-product: check-host toolchain-external-product-verify", "check-product: check-host", 1)),
        "product-target-toolchain-edge-removed": ("mk/workbench.mk", clean["mk/workbench.mk"].replace(
            "workbench-product-v200-build: toolchain-external-product-verify",
            "workbench-product-v200-build:", 1)),
        "parse-time-shell-restored": ("Makefile", clean["Makefile"] + "\nX := $(shell false)\n"),
        "tmp-log-restored": ("mk/workbench.mk", clean["mk/workbench.mk"] + "\nX=/tmp/lisp65.log\n"),
        "tracked-receipt-produced": ("Makefile", clean["Makefile"].replace(
            "R6_G6_PREFLIGHT_RECEIPT := build/", "R6_G6_PREFLIGHT_RECEIPT := tests/", 1)),
        "duplicate-build-authority": ("README.md", clean["README.md"] + "\nmake workbench-product-v200-build\n"),
    }
    for name, (path, mutation) in mutations.items():
        changed = dict(clean)
        changed[path] = mutation if mutation.startswith(clean[path][:20]) else clean[path] + mutation
        try:
            validate(changed)
        except CardError:
            pass
        else:
            raise CardError(f"build-integrity mutation survived: {name}")
    lifecycle_mutation()
    print(f"block-2.6 card5: SELFTEST PASS mutations={len(mutations) + 1}")
    return {"count": len(mutations) + 1,
            "names": [*mutations, "changed-source-verifies-old-bytes"]}


def check(write: bool) -> dict[str, Any]:
    from evidence_era import era_bind
    facts = validate(source_texts(ROOT))
    mutations = selftest()
    inputs = [ROOT / name for name in source_texts(ROOT)] + [
        ROOT / "tools/host-lisp/workbench_product.py",
        ROOT / "tools/host-lisp/make_recipe_value.py",
        ROOT / "tools/host-lisp/toolchain_external.py",
        ROOT / "tools/host-lisp/r6_g6.py",
        ROOT / "tools/host-lisp/block_26_build_integrity_card.py",
    ]
    receipt = {
        "format": "lisp65-block-2.6-card5-build-integrity-v1",
        "status": "passed",
        "facts": facts,
        "mutation_suite": mutations,
        # Provenance belongs to the receipt's seal; all semantic validation
        # and sharp mutations above still consume the living build sources.
        "inputs": [{k: v for k, v in era_bind("55414fb3", path).items() if k != "bytes"}
                   for path in inputs],
        "product_builds": 0,
        "product_links": 0,
        "device_contacts": 0,
    }
    if write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(receipt))
    elif RECEIPT.read_bytes() != canonical(receipt):
        raise CardError("registered card-5 receipt differs from derived result")
    print("block-2.6 card5: CHECK PASS targets=6 mutations=8 product-builds=0")
    return receipt


def seal_r6(profile: Path, preflight: Path, tracked_profile: Path,
            tracked_preflight: Path) -> None:
    ship = ROOT / G6.contract()["ship"]["path"]
    G6.verify_profile_receipt(profile, ship_root=ship)
    value = G6.verify_preflight(preflight, require_ship=True)
    tracked_profile.parent.mkdir(parents=True, exist_ok=True)
    tracked_profile.write_bytes(profile.read_bytes())
    sealed = deepcopy(value)
    sealed["hardware_profile"]["applicability_receipt"] = tracked_profile.relative_to(ROOT).as_posix()
    sealed["hardware_profile"]["applicability_receipt_sha256"] = sha(tracked_profile)
    tracked_preflight.write_bytes(G6.canonical(sealed))
    G6.verify_preflight(tracked_preflight, require_ship=True)
    print("block-2.6 card5: R6/G6 SEAL PASS generated=2 tracked=2")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("selftest")
    sub.add_parser("build")
    sub.add_parser("check")
    seal = sub.add_parser("seal-r6-g6")
    for name in ("profile", "preflight", "tracked-profile", "tracked-preflight"):
        seal.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
        elif args.action == "build":
            check(True)
        elif args.action == "check":
            check(False)
        else:
            rooted = lambda path: path if path.is_absolute() else ROOT / path
            seal_r6(rooted(args.profile), rooted(args.preflight),
                    rooted(args.tracked_profile), rooted(args.tracked_preflight))
    except (OSError, UnicodeError, json.JSONDecodeError, CardError, G6.G6Error) as error:
        print(f"block-2.6 card5: FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
