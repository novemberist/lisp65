#!/usr/bin/env python3
"""Refuse Completion when a stopped card preserved only its seed link."""

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_relocation_inventory_artifact_replay as REPLAY  # noqa: E402
import c2_v21_dma_content_structural_absence as ABSENCE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = REPLAY.BUILD
WPLTO = BUILD / "wplto"
SEED = WPLTO / "resident-island-seed.prg"
FINAL = WPLTO / "lisp65-c2-substitution-linked.prg"
PRECEDENT = ROOT / "build/c2.3/v2.1-full-span-convergence-card/wplto"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-completion-preflight-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "da4bf9f5"
FORMAT = "lisp65-c2.3-v2.1-root-padding-completion-preflight-red-v1"
STATUS = "FINAL RED: COMPLETION INPUTS ABSENT; OWNER DISPOSITION REQUIRED"


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


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


def authorization() -> dict[str, Any]:
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").split())
    for token in ("artifact-only qualification replay",
                  "no wplto, no relink, no card",
                  "behind green: the structural-absence gate, completion"):
        require(token in text, f"completion boundary authority absent: {token}")
    return value


def artifact_family(base: Path) -> list[Path]:
    return [base, Path(str(base) + ".elf"), Path(str(base) + ".map"),
            Path(str(base) + ".lto.o")]


def byte_differences(left: Path, right: Path) -> int:
    a = left.read_bytes()
    b = right.read_bytes()
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))


def producer_sequence() -> dict[str, Any]:
    source = Path(PRODUCT.__file__).read_text(encoding="utf-8")
    seed_call = 'seed = compile_link(out, "resident-island-seed.prg"'
    materialize = 'tool("resident_island.py", "materialize"'
    final_call = 'final = compile_link(out, "lisp65-c2-substitution-linked.prg"'
    finish = "finish_single_link(out, final, contract)"
    positions = [source.index(token) for token in (
        seed_call, materialize, final_call, finish)]
    require(positions == sorted(positions) and len(set(positions)) == 4,
            "producer seed/final/Completion sequence drift")
    return {
        "ordered_steps": ["seed-link", "resident-island-materialize",
                          "final-product-link", "Completion"],
        "source_offsets": positions,
        "seed_is_completion_input": False,
        "final_product_link_required_before_completion": True,
    }


def precedent() -> dict[str, Any]:
    seed_prg = PRECEDENT / "resident-island-seed.prg"
    final_prg = PRECEDENT / "lisp65-c2-substitution-linked.prg"
    seed_elf = Path(str(seed_prg) + ".elf")
    final_elf = Path(str(final_prg) + ".elf")
    require(all(path.is_file() for path in (
        seed_prg, final_prg, seed_elf, final_elf)),
        "seed/final distinction precedent absent")
    prg_delta = byte_differences(seed_prg, final_prg)
    elf_delta = byte_differences(seed_elf, final_elf)
    require((prg_delta, elf_delta) == (3226, 5900),
            "seed/final distinction precedent drift")
    return {
        "world": "Link-111 full-span card",
        "seed_PRG": bind(seed_prg), "final_PRG": bind(final_prg),
        "seed_ELF": bind(seed_elf), "final_ELF": bind(final_elf),
        "differing_PRG_bytes": prg_delta,
        "differing_ELF_bytes": elf_delta,
        "seed_is_not_interchangeable_with_final": True,
    }


def derive() -> dict[str, Any]:
    replay = load(REPLAY.RECEIPT)
    absence = load(ABSENCE.RECEIPT)
    seed = {path.name.removeprefix("resident-island-seed."): bind(path)
            for path in artifact_family(SEED)}
    final_paths = artifact_family(FINAL)
    missing = [path.relative_to(ROOT).as_posix() for path in final_paths
               if not path.exists()]
    require(
        replay.get("status") ==
            "PASS: frozen root-fix link qualification tail green"
        and absence.get("status") == "PASS: LINKED-IMAGE CONTENT-DMA ABSENCE"
        and replay["frozen_artifacts_after"]["candidate_PRG"] == bind(SEED)
        and len(seed) == 4 and len(missing) == 4,
        "Completion preflight boundary drift")
    completion_outputs = [
        WPLTO / "product-substitution-link.json",
        WPLTO / "runtime-overlays-final.bin",
        BUILD / "producer-result.json",
    ]
    require(not any(path.exists() for path in completion_outputs),
            "Completion or producer continuation already ran")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": STATUS,
        "authority": {
            "owner": authorization(),
            "artifact_replay": bind(REPLAY.RECEIPT),
            "structural_absence": bind(ABSENCE.RECEIPT),
            "producer": bind(Path(PRODUCT.__file__)),
            "driver": bind(DRIVER),
        },
        "green_preconditions": {
            "relocation_artifact_replay": True,
            "structural_DMA_absence": True,
            "frozen_seed_artifacts_unchanged": True,
        },
        "completion_boundary": {
            "present_seed_artifacts": seed,
            "absent_final_product_artifacts": missing,
            "producer_sequence": producer_sequence(),
            "seed_final_non_interchangeability": precedent(),
            "Completion_safe_to_run": False,
            "media_safe_to_build": False,
        },
        "execution_accounting": {
            "artifact_replays_run": 1,
            "new_WPLTO_runs": 0, "new_product_links": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0,
        },
        "disposition": {
            "owner_required": True,
            "reason": (
                "The authorized no-relink replay qualified the preserved "
                "seed link, but the normal producer still requires island "
                "materialization and a distinct final product link before "
                "Completion. Treating the seed as final would publish bytes "
                "that the producer contract never names as its final product."),
            "narrow_options": [
                "authorize a bounded producer continuation through the final link",
                "authorize a fresh product card",
                "park the continuation",
            ],
        },
        "claim_limit": (
            "Read-only Completion preflight. No WPLTO, relink, card, "
            "Completion, media or device action was performed."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    boundary = value["completion_boundary"]
    require(
        value.get("status") == STATUS
        and all(value["green_preconditions"].values())
        and len(boundary["present_seed_artifacts"]) == 4
        and len(boundary["absent_final_product_artifacts"]) == 4
        and boundary["producer_sequence"][
            "final_product_link_required_before_completion"] is True
        and boundary["seed_final_non_interchangeability"][
            "seed_is_not_interchangeable_with_final"] is True
        and boundary["Completion_safe_to_run"] is False
        and boundary["media_safe_to_build"] is False
        and value["execution_accounting"] == {
            "artifact_replays_run": 1, "new_WPLTO_runs": 0,
            "new_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0}
        and value["disposition"]["owner_required"] is True,
        "Completion preflight Final Red drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-seed-final": lambda x: x["completion_boundary"][
            "seed_final_non_interchangeability"].update(
                seed_is_not_interchangeable_with_final=False),
        "skip-final-link": lambda x: x["completion_boundary"][
            "producer_sequence"].update(
                final_product_link_required_before_completion=False),
        "allow-completion": lambda x: x["completion_boundary"].update(
            Completion_safe_to_run=True),
        "allow-media": lambda x: x["completion_boundary"].update(
            media_safe_to_build=True),
        "invent-link": lambda x: x["execution_accounting"].update(
            new_product_links=1),
        "invent-completion": lambda x: x["execution_accounting"].update(
            completion_runs=1),
        "hide-owner-boundary": lambda x: x["disposition"].update(
            owner_required=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except PreflightError:
            rejected.append(name)
    require(rejected == list(cases),
            "Completion preflight mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "Completion preflight receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(load(RECEIPT) == value,
                "Completion preflight receipt stale")
    print("root-padding Completion preflight: FINAL RED final=0 seed=1 "
          "WPLTO=0 link=0 completion=0 mutations=7")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreflightError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"root-padding Completion preflight: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
