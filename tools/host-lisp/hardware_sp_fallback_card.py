#!/usr/bin/env python3
"""Bound hardening fallback; no Comfort feature, no implicit build replay."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import comfort_stack_product_card as P

ROOT = P.ROOT
BINDING = "6cf1012c"
OWNER = "28623210"
REPORT = ROOT / "docs/planning/v2.1-hardware-sp-fallback-report.md"
P.BUILD = ROOT / "build/v2.1/hardware-sp-fallback-r1"
P.PREFLIGHT = ROOT / "build/v2.1/hardware-sp-fallback-r1-preflight"
P.ADDITIONS = ("LISP65_HARDWARE_SP_GUARD", "LISP65_HARDWARE_SP_LINK_AUTHORITY")
P.AUTHORIZATION = BINDING
base_configure = P.configure


def authority():
    plan = "docs/planning/v2.0.0-pre-plan.md"
    raw = subprocess.check_output(["git", "show", BINDING + ":" + plan], cwd=ROOT)
    sections = [s for s in raw.split(b"\n## ") if b"Hardening fallback card" in s
                and b"one host prefilter image" in s]
    P.require(len(sections) == 1, "hardening budget missing/ambiguous")
    owner = subprocess.check_output(["git", "show", OWNER + ":" + plan], cwd=ROOT)
    P.require(b"the hardening release is accepted as re-cut" in owner, "owner decision missing")
    predecessor = {n: P.F.C.bind(P.PREDECESSOR[n]) for n in ("ELF", "PRG")}
    P.require(predecessor["ELF"]["sha256"] ==
        "c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c",
        "renderer baseline changed")
    return {"commit": BINDING, "owner_commit": OWNER,
            "section_sha256": hashlib.sha256(sections[0]).hexdigest(),
            "predecessor": predecessor, "comfort_enabled": False,
            "budget": {"seed_WPLTO": 1, "final_C_LTO": 1, "product_links": 1,
                       "host_check_images": 1, "device_contacts": 0},
            "seed_measurement_transport": "direct PRG with unchanged reference D81; not packed acceptance"}


def source_gate():
    value = P.ORIGINAL_SOURCE_GATE()
    features = P.bound_features()
    P.require("LISP65_COMFORT_TRAMPOLINE" not in features, "Comfort reintroduced")
    P.require(all(f in features for f in P.ADDITIONS), "guard or threshold authority omitted")
    value["hardening_features"] = list(P.ADDITIONS)
    value["comfort_feature_absent"] = True
    value["threshold_consumer"] = P.SP.selftest()
    value["final_elf_proofs_pending"] = True
    return value


def configure():
    base_configure()
    P.F.DRIVER = P.F.C.DRIVER = Path(__file__).resolve()
    P.F.REPORT = P.F.C.REPORT = REPORT
    P.F.FORMAT = P.F.C.FORMAT = "hardware-sp-fallback-r1"
    P.F.STATUS = P.F.C.STATUS = "PENDING: HARDWARE-SP FALLBACK QUALIFICATION"


P.authority = authority
P.source_gate = source_gate
P.configure = configure

if __name__ == "__main__":
    P.main()
