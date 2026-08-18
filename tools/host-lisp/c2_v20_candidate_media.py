#!/usr/bin/env python3
"""Bind the first media-closure result for the green 2.0 product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_candidate_media as OLD  # noqa: E402
import c2_v20_invariant_golden_card as CARD  # noqa: E402
import c2_v17_state_ownership_phase_b as LMA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OWNER_COMMIT = "ee134b375550214a527c576f78bd79acedfe6e5a"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CANDIDATE = CARD.BUILD
ELF = CANDIDATE / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = CANDIDATE / "wplto/lisp65-c2-substitution-linked.prg"
MAP = Path(str(PRG) + ".map")
PREDECESSOR = ROOT / "build/c2.3/v1.5.0-candidate-product-link97/final"
PREDECESSOR_ELF = PREDECESSOR / "lisp65-c2-substitution-linked.prg.elf"
PREDECESSOR_PRG = PREDECESSOR / "lisp65-c2-substitution-linked.prg"
BUILD = ROOT / "build/c2.3/v2.0-invariant-golden-media"
SUCCESS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-invariant-golden-media-closure-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-invariant-golden-media-closure-first-red.json")

PREDECESSOR_SESSION_CHAIN = tuple(
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks" / name
    for name in (
        "c2.3-v1.5.0-link97-device-session-preparation-receipt.json",
        "c2.3-v1.5.0-link97-stager-liveness-media-receipt.json",
        "c2.3-v1.5.0-link97-stager-liveness-d1-first-red-receipt.json",
        "c2.3-v1.5.0-link97-stager-liveness-d1-preparation-receipt.json",
        "c2.3-v1.5.0-link97-stager-liveness-d1-receipt.json",
        "c2.3-v1.5.0-link97-stager-liveness-d2-d5-preparation-receipt.json",
        "c2.3-v1.5.0-name-freight-media-receipt.json",
        "c2.3-v1.5.0-name-freight-d1-preparation-receipt.json",
        "c2.3-v1.5.0-name-freight-d1-receipt.json",
        "c2.3-v1.5.0-name-freight-d2-d5-preparation-receipt.json",
    ))

LOW_RESIDENT = (
    ".lisp65_c2_kernal_handoff",
    ".lisp65_c2_host_facade",
    ".lisp65_c2_kernal_io_reveal",
    ".lisp65_c2_kernal_map_switch",
)


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        stdout=subprocess.PIPE, check=True).stdout
    return {"authority": "git-blob", "commit": commit, "path": relative,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_bind(OWNER_COMMIT, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{OWNER_COMMIT}:{authority['path']}"], cwd=ROOT,
        stdout=subprocess.PIPE, check=True).stdout
    text = " ".join(raw.decode("utf-8").split())
    require(
        "the media closure for the new candidate world regenerates" in text
        and "contract members regenerate" in text
        and "stale v1.5 closure retires loudly" in text,
        "2.0 media-closure owner authorization absent")
    return authority


def card_authority() -> dict[str, Any]:
    value = load(CARD.RECEIPT)
    require(
        value.get("status")
            == "PASS: owned v1.5 plus F018B candidate satisfies invariant golden"
        and value.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "product_link_attempts": 1,
            "wplto_runs": 1}
        and value.get("acceptance", {}).get("comparison")
            == "invariants-exact-derived-freight-validated",
        "green invariant-golden card authority absent")
    for role in ("elf", "prg", "map", "lto", "linker"):
        require(value["artifacts"][role]
                == bind(ROOT / value["artifacts"][role]["path"]),
                f"green card artifact drift: {role}")
    return value


def resident_delivery_rows() -> list[dict[str, Any]]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    data = PRG.read_bytes()
    require(len(data) >= 2, "2.0 resident PRG is truncated")
    load_address = int.from_bytes(data[:2], "little")
    rows: list[dict[str, Any]] = []
    for name in LOW_RESIDENT:
        section = truth.section(name)
        lma = LMA.section_lma(ELF, name)
        delivered = (
            lma == section.address
            and load_address <= section.address
            and section.address + section.bytes <= load_address + len(data) - 2)
        rows.append({
            "section": name, "vma": f"0x{section.address:04x}",
            "lma": f"0x{lma:05x}", "bytes": section.bytes,
            "resident_prg_delivered": delivered,
        })
    return rows


def content_witness() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    section = truth.section(LOW_RESIDENT[0])
    prefix = truth.section_bytes(section.name)[:6]
    data = PRG.read_bytes()
    load_address = int.from_bytes(data[:2], "little")
    offset = 2 + section.address - load_address

    predecessor_truth = ElfTruth.read(
        PREDECESSOR_ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    predecessor_section = predecessor_truth.section(section.name)
    predecessor_lma = LMA.section_lma(PREDECESSOR_ELF, section.name)
    predecessor_data = PREDECESSOR_PRG.read_bytes()
    predecessor_offset = predecessor_data.find(prefix)
    return {
        "candidate_ELF_handoff_prefix": prefix.hex(),
        "candidate_resident_PRG_occurrences": data.count(prefix),
        "candidate_resident_PRG_bytes_at_VMA_derived_offset":
            data[offset:offset + len(prefix)].hex(),
        "link97_predecessor": {
            "handoff_lma": f"0x{predecessor_lma:x}",
            "handoff_vma": f"0x{predecessor_section.address:x}",
            "resident_PRG_occurrences": predecessor_data.count(prefix),
            "resident_PRG_offset": predecessor_offset,
        },
        "conclusion": (
            "the current ELF owns the code semantically but no packed media "
            "role delivers its bytes"),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    rows = resident_delivery_rows()
    require(
        value.get("format")
            == "lisp65-c2.3-v20-invariant-golden-media-closure-first-red-v1"
        and value.get("status")
            == "FIRST-RED: BOOT-CRITICAL-LOW-RESIDENT-SECTIONS-NOT-DELIVERED"
        and value.get("authority", {}).get("owner_acceptance_commit")
            == OWNER_COMMIT
        and value.get("authority", {}).get("card_receipt")
            == bind(CARD.RECEIPT)
        and value.get("authority", {}).get("predecessor_media_receipt")
            == bind(OLD.RECEIPT)
        and value.get("authority", {}).get("predecessor_session_chain")
            == [bind(path) for path in PREDECESSOR_SESSION_CHAIN]
        and value.get("authority", {}).get("candidate") == {
            "elf": bind(ELF), "map": bind(MAP), "resident_prg": bind(PRG)}
        and value.get("attempt_accounting") == {
            "artifact_completions": 0, "device_contacts": 0,
            "media_builds": 0, "product_links": 0, "wplto_runs": 0}
        and value.get("first_red", {}).get("product_completed") is False
        and value.get("first_red", {}).get("media_created") is False
        and value.get("first_red", {}).get("sections") == rows
        and value.get("content_witness") == content_witness()
        and len(rows) == 4
        and not any(row["resident_prg_delivered"] for row in rows),
        "2.0 media First-Red authority or delivery facts drift")
    if verify:
        authorization(); card_authority()
        require(not BUILD.exists() and not SUCCESS.exists(),
                "2.0 media First Red no longer bounds an uncompleted closure")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-WPLTO": lambda x: x["attempt_accounting"].update(wplto_runs=1),
        "claim-completion": lambda x: x["attempt_accounting"].update(
            artifact_completions=1),
        "claim-media": lambda x: x["attempt_accounting"].update(media_builds=1),
        "hide-missing-section": lambda x: x["first_red"]["sections"][0].update(
            resident_prg_delivered=True),
        "rewrite-LMA": lambda x: x["first_red"]["sections"][0].update(
            lma="0x0b4a3"),
        "rewrite-predecessor": lambda x: x["authority"][
            "predecessor_media_receipt"].update(sha256="0" * 64),
        "rewrite-predecessor-session": lambda x: x["authority"][
            "predecessor_session_chain"][0].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); candidate.pop("mutations_rejected", None)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "2.0 media First-Red mutation survived")
    return rejected


def check() -> int:
    value = load(FIRST_RED); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value),
            "2.0 media First-Red mutation set drift")
    print("2.0 invariant-golden media: FIRST RED BOUND "
          "missing-low-resident-sections=4 mutations=7")
    return 0


def selftest() -> int:
    value = load(FIRST_RED); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=False)
    require(rejected == mutations(value) and len(rejected) == 7,
            "2.0 media First-Red selftest drift")
    print("2.0 invariant-golden media selftest: PASS mutations=7")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "first-red-check"))
    return {"selftest": selftest, "first-red-check": check}[
        parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MediaError, OSError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print("2.0 INVARIANT-GOLDEN MEDIA: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
