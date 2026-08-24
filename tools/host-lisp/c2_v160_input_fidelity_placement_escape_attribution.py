#!/usr/bin/env python3
"""Attribute the frozen input-fidelity placement-wall Red without linking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-owner-scope-family-card-final-red.json")
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-owner-scope-family-card/wplto"
MAP = BUILD / "resident-island-seed.prg.map"
LINKER = BUILD / "c2-substitution.ld"
PROFILE = BUILD / "resolved-profile.txt"
PREDECESSOR_ELF = ROOT / (
    "build/c2.3/v1.6-input-fidelity-owner-scope-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-placement-escape-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "fa3e3a84"
FORMAT = "lisp65-c2-v160-input-fidelity-placement-escape-attribution-v1"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(["git", "show", f"{value['commit']}:{value['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("`", "").replace("*", "").split())
    for token in ("placement-escape attribution commissioned", "host-only",
                  "both persisted", "stored-address", "re-pricing"):
        require(token in text, f"placement attribution authority absent: {token}")
    return value


def map_section(name: str) -> dict[str, Any]:
    pattern = re.compile(
        rf"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(name) + r"\s*$", re.MULTILINE)
    matches = pattern.findall(MAP.read_text(encoding="utf-8"))
    require(len(matches) == 1, f"map output section not unique: {name}")
    vma, lma, size = (int(item, 16) for item in matches[0])
    return {"name": name, "address": vma, "load_address": lma,
            "bytes": size, "end_exclusive": vma + size}


def predecessor_section(name: str) -> dict[str, Any]:
    command = [str(ROOT / "tools/llvm-mos/bin/llvm-readobj"),
               "--elf-output-style=JSON", "--sections", str(PREDECESSOR_ELF)]
    raw = subprocess.run(command, cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout
    document = json.loads(raw)
    rows = []
    for wrapper in document[0]["Sections"]:
        row = wrapper["Section"]
        raw_name = row["Name"]
        actual = raw_name["Name"] if isinstance(raw_name, dict) else raw_name
        if actual == name:
            rows.append({"name": actual, "address": int(row["Address"]),
                         "bytes": int(row["Size"]),
                         "end_exclusive": int(row["Address"]) + int(row["Size"])})
    require(len(rows) == 1, f"predecessor section not unique: {name}")
    return rows[0]


def linker_source() -> dict[str, Any]:
    text = LINKER.read_text(encoding="utf-8")
    expressions = {
        "main": ("ADDR(.lisp65_c2_kernal_window.reopen_gap0) +\n"
                 "        SIZEOF(.lisp65_c2_kernal_window.reopen_gap0)"),
        "helper": ("ADDR(.lisp65_c2_kernal_window.reopen_gap1) +\n"
                   "        SIZEOF(.lisp65_c2_kernal_window.reopen_gap1)"),
    }
    for value in expressions.values():
        require(text.count(value) == 1, "generated placement expression drift")
    generator = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
    generator_text = generator.read_text(encoding="utf-8")
    for value in expressions.values():
        require(generator_text.count(value) == 1,
                "placement generator expression drift")
    return {"generated_linker": bind(LINKER), "generator": bind(generator),
            "assignment_expressions": expressions,
            "classification": "predecessor-end-derived; no numeric address pin"}


def source_consumption() -> dict[str, Any]:
    lines = PROFILE.read_text(encoding="utf-8").splitlines()
    features = [line.split("=", 1)[1].split(",") for line in lines
                if line.startswith("feature_defines=")]
    base = [line for line in lines
            if "input_sha256=src/c2_kernal_irq_base.s:" in line]
    capture = [line for line in lines
               if "input_sha256=src/optional/c2_kernal_input_capture.s:" in line]
    require(len(features) == 1 and len(base) == 1 and not capture,
            "real compiler source-selection witness drift")
    objects = sorted((BUILD / ".canonical-objects-resident-island-seed").glob("*.o"))
    names = [path.name for path in objects]
    require("052-c2_kernal_irq_base.s.o" in names
            and not any("input_capture" in name for name in names),
            "canonical object source-owner witness drift")
    return {"resolved_profile": bind(PROFILE),
            "feature_defines": features[0],
            "capture_feature_consumed": "LISP65_V160_INPUT_CAPTURE" in features[0],
            "selected_irq_owner": base[0],
            "capture_owner_rows": capture,
            "canonical_object_count": len(objects),
            "canonical_irq_owner_object": "052-c2_kernal_irq_base.s.o",
            "canonical_capture_owner_objects": [name for name in names
                                                 if "input_capture" in name],
            "real_consumer": (
                "c2_product_substitution_link.compile_link() calls "
                "source_list(probe_definitions) for the compiler inputs")}


def derive() -> dict[str, Any]:
    red_before = bind(FINAL_RED)
    inputs_before = {"map": bind(MAP), "linker": bind(LINKER),
                     "profile": bind(PROFILE),
                     "predecessor_ELF": bind(PREDECESSOR_ELF)}
    red = json.loads(FINAL_RED.read_text(encoding="utf-8"))
    require(red["hard_stop"]["mechanism"] == "open"
            and red["hard_stop"]["successors_authorized"] == 0,
            "frozen placement Red authority drift")

    gap0 = map_section(".lisp65_c2_kernal_window.reopen_gap0")
    gap1 = map_section(".lisp65_c2_kernal_window.reopen_gap1")
    profile = map_section(".lisp65_c2_kernal_window.profile_rodata")
    state = map_section(".lisp65_c2_kernal_window.state")
    main = map_section(".lisp65_c2_kernal_window.input_capture_main")
    helper = map_section(".lisp65_c2_kernal_window.input_capture_helper")
    main_hole = [gap0["end_exclusive"], profile["address"]]
    helper_hole = [gap1["end_exclusive"], state["address"]]
    expected = {"main": 34, "helper": 25}
    require(main["address"] == main_hole[0] == 0xFD08
            and helper["address"] == helper_hole[0] == 0xFEE1,
            "assigned fragment starts differ from derived hole starts")
    require(main_hole == [0xFD08, 0xFD2C]
            and helper_hole == [0xFEE1, 0xFF80],
            "post-R1 hole geometry drift")
    projected_residual = ((main_hole[1] - main_hole[0] - expected["main"])
                          + (helper_hole[1] - helper_hole[0] - expected["helper"]))
    require(projected_residual == 136 and main["bytes"] == 0
            and helper["bytes"] == 0,
            "zero-byte output-section mechanism not reproduced")
    predecessor = {
        "main": predecessor_section(
            ".lisp65_c2_kernal_window.input_capture_main"),
        "helper": predecessor_section(
            ".lisp65_c2_kernal_window.input_capture_helper"),
    }
    require(predecessor["main"] == {"name":
                ".lisp65_c2_kernal_window.input_capture_main",
                "address": 0xFD08, "bytes": 34, "end_exclusive": 0xFD2A}
            and predecessor["helper"] == {"name":
                ".lisp65_c2_kernal_window.input_capture_helper",
                "address": 0xFEE1, "bytes": 25, "end_exclusive": 0xFEFA},
            "last linked capture-world placement drift")
    consumption = source_consumption()
    inputs_after = {"map": bind(MAP), "linker": bind(LINKER),
                    "profile": bind(PROFILE),
                    "predecessor_ELF": bind(PREDECESSOR_ELF)}
    require(inputs_before == inputs_after and red_before == bind(FINAL_RED),
            "frozen attribution evidence changed")
    return {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": "ATTRIBUTED: CAPTURE LAYOUT ENABLED BUT OWNER SOURCE NOT CONSUMED",
        "claim_limit": (
            "Host-only read of the frozen failed-link map, generated linker, "
            "real compiler profile, canonical object names and predecessor "
            "ELF; no configuration, qualification, link, card, media or device."),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_authorized": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"reviewer": authorization(), "driver": bind(DRIVER)},
        "frozen_evidence": {"Final_Red": red_before, **inputs_before,
                            "unchanged_after": True},
        "two_geometries": {
            "final_image_derived": {
                "source": "failed-link map predecessor ends and successor starts",
                "main_hole": {"range": main_hole,
                    "bytes": main_hole[1] - main_hole[0],
                    "lower_owner": gap0, "upper_owner": profile},
                "helper_hole": {"range": helper_hole,
                    "bytes": helper_hole[1] - helper_hole[0],
                    "lower_owner": gap1, "upper_owner": state},
                "expected_payload_bytes": expected,
                "projected_post_capture_free_bytes": projected_residual},
            "assigned_by_placement": {
                "main": main, "helper": helper,
                "address_source": linker_source(),
                "starts_match_derived_holes": True,
                "emitted_payload_bytes": 0,
                "predecessor_linked_control": predecessor}},
        "compiler_consumption": consumption,
        "decision": {
            "stored_pre_R1_addresses": False,
            "holes_shrank_or_require_repricing": False,
            "commissioned_dichotomy_exhaustive": False,
            "classification": "bound-layout-with-unconsumed-source-owner",
            "new_mechanism_relative_to_commissioned_branches": True,
            "mechanical_basis": (
                "Both generated starts equal the current predecessor ends and "
                "both holes retain the priced 34+25 payload with 136 bytes "
                "free. The assertion text fired because its first conjunct, "
                "SIZEOF == 34/25, saw two zero-byte output sections. The real "
                "compiler profile selected c2_kernal_irq_base.s and omitted "
                "both the capture feature and c2_kernal_input_capture.s; the "
                "canonical object inventory confirms the same source owner."),
            "known_principle": "bound is not consumed",
            "product_or_capacity_finding": False},
        "disposition": {"successor_cards_authorized": 0,
            "self_disposition_authorized": False,
            "next": "return attribution; reviewer disposition required"}}


def main() -> int:
    value = derive()
    raw = canonical(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(raw)
    check = derive()
    require(value == check, "placement attribution is not deterministic")
    require(RECEIPT.read_bytes() == raw, "placement attribution write drift")
    print("v1.6 placement escape: ATTRIBUTION PASS starts=fd08/fee1 "
          "holes=36/159 payload=0/0 projected-free=136 successor=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
