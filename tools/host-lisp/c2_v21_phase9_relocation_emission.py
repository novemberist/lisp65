#!/usr/bin/env python3
"""Bind phase-9 relocation freight to actual candidate emission, not arithmetic."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = ARCH / "c2.3-v2.1-phase9-abi-fix-card-final-red.json"
SEED_ELF = ROOT / (
    "build/c2.3/v2.1-phase9-abi-fix-card/wplto/"
    "resident-island-seed.prg.elf")
EMITTED_OBJECT = ROOT / (
    "build/c2.3/v2.1-phase9-abi-fix-card/wplto/"
    ".canonical-objects-resident-island-seed/"
    "060-c2_mapped_far_convergence.s.o")
SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ARCH / "c2.3-v2.1-phase9-relocation-emission-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7fa52735"
SECTION = ".rela.lisp65_c2_mapped_far_service"


class EmissionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EmissionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def emitted_section(path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    row = truth.section(SECTION)
    require(row.address == 0 and row.bytes > 0 and row.bytes % 12 == 0
            and "SHF_INFO_LINK" in row.flags,
            "emitted relocation section shape drift")
    return {"name": SECTION, "address": "0x0000", "bytes": row.bytes,
            "entry_bytes": 12, "records": row.bytes // 12,
            "required_flags": ["SHF_INFO_LINK"]}


def validate(value: dict[str, Any]) -> None:
    emission = value["emitted_candidate"]
    require(
        value.get("status")
            == "PASS: relocation freight derived from emitted candidate"
        and emission["linked_ELF_section"] == emission["object_section"]
        and emission["linked_ELF_section"]["bytes"] == 3972
        and emission["linked_ELF_section"]["records"] == 331
        and value["model_disposition"] == {
            "forecast_bytes": 3924,
            "emitted_bytes": 3972,
            "difference_bytes": 48,
            "forecast_status": "FAILED-MODEL",
            "candidate_status": "NOT-REJECTED-BY-FORECAST",
        }
        and value["replacement_projection"]["bytes"] == 3972
        and value["replacement_projection"]["authority"]
            == "emitted-candidate-object-and-linked-ELF",
        "relocation-emission receipt drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-model-forecast": lambda x: x["replacement_projection"].update(
            bytes=3924),
        "blame-candidate": lambda x: x["model_disposition"].update(
            candidate_status="FAILED-CANDIDATE"),
        "accept-model": lambda x: x["model_disposition"].update(
            forecast_status="PASSED-MODEL"),
        "drop-object-emission": lambda x: x["emitted_candidate"].pop(
            "object_section"),
        "invent-record": lambda x: x["emitted_candidate"]
            ["linked_ELF_section"].update(records=330),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except (EmissionError, KeyError):
            rejected.append(name)
    require(rejected == list(cases), "relocation-emission mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red.get("retry_authorized") is False
            and red.get("attempt_accounting", {}).get("WPLTO_runs") == 1,
            "phase-9 predecessor Final Red drift")
    authority = git_bind(AUTHORIZATION, PLAN)
    raw_text = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw_text.lower().split())
    require("relocation freight derives from the emitted candidate" in text
            and "fails the model, never the candidate" in text,
            "relocation-emission authority absent")
    linked = emitted_section(SEED_ELF)
    object_row = emitted_section(EMITTED_OBJECT)
    value = {
        "format": "lisp65-c2.3-v21-phase9-relocation-emission-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: relocation freight derived from emitted candidate",
        "authority": {"owner": authority, "Final_Red": bind(FINAL_RED),
                      "source": bind(SOURCE), "driver": bind(DRIVER)},
        "emitted_candidate": {
            "linked_ELF": bind(SEED_ELF),
            "canonical_object": bind(EMITTED_OBJECT),
            "linked_ELF_section": linked,
            "object_section": object_row,
        },
        "model_disposition": {
            "forecast_bytes": 3924, "emitted_bytes": linked["bytes"],
            "difference_bytes": linked["bytes"] - 3924,
            "forecast_status": "FAILED-MODEL",
            "candidate_status": "NOT-REJECTED-BY-FORECAST",
        },
        "replacement_projection": {
            **linked,
            "authority": "emitted-candidate-object-and-linked-ELF",
        },
        "claim_limit": (
            "Emission/model attribution only; no replacement WPLTO, link, "
            "Completion, media or device contact."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def build() -> None:
    require(not RECEIPT.exists(), "relocation-emission receipt already exists")
    RECEIPT.write_bytes(canonical(derive()))
    print("phase-9 relocation emission: PASS emitted=3972 model=FAILED")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    expected = derive(); expected.pop("mutations_rejected", None)
    require(value == expected and rejected == mutations(value),
            "relocation-emission authority/mutation drift")
    print("phase-9 relocation emission check: PASS emitted=3972 records=331")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]) == 5,
            "relocation-emission mutation count drift")
    print("phase-9 relocation emission selftest: PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    {"build": build, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EmissionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"phase-9 relocation emission: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
