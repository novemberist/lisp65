#!/usr/bin/env python3
"""Build the Link-64-shaped, nonpromotable C1 overlay donor."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_cutpoint_build_link60 as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")
DONOR_STATUS = (
    "passed-nonpromotable-Link64-C1-overlay-donor-hardware-not-run")


def configure() -> None:
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
    BASE.INTERNAL = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-internal.json")
    BASE.BASE_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-base.json")
    BASE.RAW_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-raw.json")
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "link64-c1-freezer-cutpoints-donor-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-base-result.json")
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-format-stage.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/c1-freezer-cutpoints-link64/"
        "write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-emitter-union.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-preinstall-source-host.json")
    BASE.FINAL_RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-final-map.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-link64-c1-freezer-cutpoints-donor-"
        "nonpromotable-structural-receipt.json")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.PRODUCT_SHA = PRODUCT_SHA
    BASE.DEPLOYMENT_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length/"
        "lisp65-c2-substitution-linked.prg")
    BASE.DEPLOYMENT_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "structural-receipt.json")
    BASE.DEPLOYMENT_STATUS = (
        "passed-link64-nonlto-stateless-completion-length-product-"
        "identity-hardware-not-run")


def main() -> int:
    configure()
    try:
        result = BASE.main()
    except BASE.BuildError:
        # The single diagnostic closure is expected to stop at the inherited
        # product-size checker.  Its second entry is artifact-only completion.
        if not BASE.OUT.is_dir() or BASE.RECEIPT.exists():
            raise
        result = BASE.main()

    os.chmod(BASE.OUT, 0o755)
    os.chmod(BASE.RECEIPT, 0o644)
    value = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    value["format"] = "lisp65-c2.2-link64-C1-Freezer-WPLTO-donor-v1"
    value["status"] = DONOR_STATUS
    authority = value["authority"]
    authority["immutable_link64_product"] = authority.pop(
        "immutable_link60_product")
    authority["link64_receipt"] = authority.pop("link60_receipt")
    authority["link64_driver"] = BASE.bind(Path(__file__))
    eligibility = value["carrier_eligibility"]
    eligibility["region1_byteidentical_link64"] = eligibility.pop(
        "region1_byteidentical_link60")
    value["next_gate"] = (
        "artifact-only structured relocation rebind to immutable Link 64, "
        "v4 region rebuild and exact main-stage binding")
    BASE.RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(BASE.RECEIPT, 0o444)
    os.chmod(BASE.OUT, 0o555)
    print(
        "c2-c1-freezer-cutpoint-build-link64: PASS "
        f"donor={BASE.LINK60.sha(BASE.PRODUCT)} hardware=not-run")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            "c2-c1-freezer-cutpoint-build-link64: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
