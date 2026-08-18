#!/usr/bin/env python3
"""Prove the linked product has no unsafe content-consuming DMA read."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v21_relocation_inventory_artifact_replay as REPLAY  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ROOT_FIX = ARCH / "c2.3-v2.1-probe-oracle-root-fix-receipt.json"
SWEEP = ROOT / "config/c2-dma-content-consumption-sweep.json"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
KERNAL = ROOT / "src/c2_kernal_runtime.c"
ELF = REPLAY.ELF
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ARCH / (
    "c2.3-v2.1-dma-content-structural-absence-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "20a5f4ec"
RECORDED_ON = "2026-08-16"


class AbsenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AbsenceError(message)


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("step 3 of the permanence plan", "structural-absence gate",
                  "no content-consuming dma read outside",
                  "crc-covered immutable spans", "linked-image-derived",
                  "born-derived"):
        require(token in text, f"structural-absence authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def disassembly() -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", "--symbolize-operands", str(ELF)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout


def function_bodies() -> dict[tuple[str, str], str]:
    """Return emitted function bodies keyed by (section, symbol)."""
    text = disassembly()
    section = ""
    current: tuple[str, str] | None = None
    rows: dict[tuple[str, str], list[str]] = {}
    for line in text.splitlines():
        if line.startswith("Disassembly of section "):
            section = line.removeprefix("Disassembly of section ").rstrip(":")
            current = None
            continue
        match = re.match(r"^[0-9a-f]+ <([^>]+)>:$", line)
        if match:
            current = (section, match.group(1))
            rows.setdefault(current, [])
            continue
        if current is not None:
            if not line.strip():
                current = None
            else:
                rows[current].append(line)
    return {key: "\n".join(value) for key, value in rows.items()}


def direct_callers(bodies: dict[tuple[str, str], str],
                   target: str) -> list[dict[str, str]]:
    marker = f"<{target}>"
    return sorted(
        ({"section": section, "function": name}
         for (section, name), body in bodies.items() if marker in body),
        key=lambda row: (row["section"], row["function"]))


def unique_body(bodies: dict[tuple[str, str], str], name: str) -> str:
    matches = [body for (section, symbol), body in bodies.items()
               if symbol == name]
    require(len(matches) == 1, f"linked function identity drift: {name}")
    return matches[0]


def registered_workbench_surfaces() -> list[dict[str, Any]]:
    value = load(SWEEP)
    rows = [row for row in value.get("sites", [])
            if row.get("image") == "workbench"
            and row.get("classification") in (
                "content-consumed",
                "predecessor-content-consumed-source-fixed")]
    require(rows and len({(row["owner"], row["register"], row["ordinal"])
                          for row in rows}) == len(rows),
            "registered workbench content surfaces drift")
    return rows


def linked_model() -> dict[str, Any]:
    replay = load(REPLAY.RECEIPT)
    root = load(ROOT_FIX)
    require(
        replay.get("status") ==
            "PASS: frozen root-fix link qualification tail green"
        and replay["frozen_artifacts_after"]["candidate_ELF"] == bind(ELF)
        and root.get("status") ==
            "HOST-GREEN: NINE-MUTABLE-READERS-USE-MAP-CPU; CARD-PENDING",
        "structural-absence predecessor drift")
    bodies = function_bodies()
    wrappers = {}
    caller_rows = []
    for wrapper in ("ext_dma_read_or_abort", "c2_dma_read_or_abort"):
        body = unique_body(bodies, wrapper)
        callers = direct_callers(bodies, wrapper)
        require(
            body.count("<c2_map_cpu_read>") == 1
            and "<c2_facade_vm_code_load>" not in body
            and "<c2_facade_c2_dma>" not in body,
            f"mutable wrapper is not rooted at MAP-CPU: {wrapper}")
        wrappers[wrapper] = {
            "transport": "MAP-CPU", "linked_callers": callers,
            "linked_caller_count": len(callers),
            "DMA_submission_edges": 0,
        }
        caller_rows.extend({**row, "wrapper": wrapper,
                            "transport": "MAP-CPU"} for row in callers)

    # The historical sweep is semantic registration, never a count pin.  Its
    # five workbench content surfaces must each classify under the current
    # linked image.  Two immutable boot surfaces retain independent CRC
    # convergence; both mutable roots are now CPU; the old physical facade is
    # dead as a content entry in this candidate.
    registered = registered_workbench_surfaces()
    registered_owners = {str(row["owner"]) for row in registered}
    expected_classes = {
        "ext_dma": "mutable-content-rerouted-to-MAP-CPU",
        "c2_facade_target_c2_dma": "mutable-content-rerouted-to-MAP-CPU",
        "c2_product_physical_copy": "no-linked-content-entry",
        "vm_runtime_overlay_exec_family": "immutable-delivery-CRC",
        "c2k_copy": "immutable-delivery-CRC",
    }
    require(registered_owners == set(expected_classes),
            "unclassified registered workbench content surface")
    physical_callers = direct_callers(bodies, "c2_physical_read_converged")
    require(not physical_callers,
            "physical DMA convergence has a live content entry")
    runtime_source = RUNTIME.read_text(encoding="utf-8")
    kernal_source = KERNAL.read_text(encoding="utf-8")
    require(
        all(token in runtime_source for token in (
            "rtov_crc_converge", "VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT"))
        and all(token in kernal_source for token in (
            "c2k_crc16", "C2_KERNAL_WINDOW_CRC16")),
        "immutable CRC source authority drift")
    classifications = [{"owner": owner, "classification": classification}
                       for owner, classification in sorted(
                           expected_classes.items())]
    unsafe = [row for row in classifications
              if row["classification"] not in (
                  "mutable-content-rerouted-to-MAP-CPU",
                  "no-linked-content-entry", "immutable-delivery-CRC")]
    return {
        "status": "PASS: no unsafe content-consuming DMA read in linked image",
        "derivation": "ELF function bodies plus semantic content-surface registry",
        "born_derived": {
            "mutable_callers": caller_rows,
            "mutable_caller_count": len(caller_rows),
            "historical_caller_count_acceptance_pin": False,
            "new_wrapper_callers_automatically_enumerated": True,
        },
        "wrappers": wrappers,
        "registered_surfaces": classifications,
        "physical_DMA_content_entry_callers": physical_callers,
        "immutable_CRC_authority": {
            "vm_runtime_overlay_exec_family": bind(RUNTIME),
            "c2k_copy": bind(KERNAL),
        },
        "unsafe_content_DMA_surfaces": unsafe,
        "unsafe_content_DMA_count": len(unsafe),
    }


def validate(model: dict[str, Any]) -> None:
    require(
        model.get("status") ==
            "PASS: no unsafe content-consuming DMA read in linked image"
        and model.get("unsafe_content_DMA_count") == 0
        and model.get("unsafe_content_DMA_surfaces") == []
        and model.get("physical_DMA_content_entry_callers") == []
        and all(row.get("transport") == "MAP-CPU"
                for row in model.get("born_derived", {}).get(
                    "mutable_callers", []))
        and model.get("born_derived", {}).get(
            "historical_caller_count_acceptance_pin") is False
        and all(row.get("DMA_submission_edges") == 0
                for row in model.get("wrappers", {}).values())
        and all(row.get("classification") in (
                    "mutable-content-rerouted-to-MAP-CPU",
                    "no-linked-content-entry", "immutable-delivery-CRC")
                for row in model.get("registered_surfaces", [])),
        "linked content-DMA structural absence red")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "reroute-one-reader-to-DMA": lambda x: x["born_derived"][
            "mutable_callers"][0].update(transport="DMA-completion"),
        "restore-wrapper-DMA-edge": lambda x: next(iter(
            x["wrappers"].values())).update(DMA_submission_edges=1),
        "revive-physical-content-entry": lambda x: x.update(
            physical_DMA_content_entry_callers=[{
                "section": ".text", "function": "new_reader"}]),
        "lose-immutable-CRC-class": lambda x: x["registered_surfaces"][0].update(
            classification="DMA-completion-only"),
        "pin-historical-caller-count": lambda x: x["born_derived"].update(
            historical_caller_count_acceptance_pin=True),
        "hide-unsafe-surface": lambda x: x.update(unsafe_content_DMA_count=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except AbsenceError:
            rejected.append(name)
    require(rejected == list(cases), "content-DMA mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    model = linked_model()
    validate(model)
    value = {
        "format": "lisp65-c2.3-v2.1-dma-content-structural-absence-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: LINKED-IMAGE CONTENT-DMA ABSENCE",
        "authority": {"owner": authorization(),
            "artifact_replay": bind(REPLAY.RECEIPT),
            "root_fix": bind(ROOT_FIX), "content_sweep": bind(SWEEP),
            "candidate_ELF": bind(ELF), "driver": bind(DRIVER)},
        "linked_model": model,
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "Completion and same-world media, then poison-regression D2",
        "claim_limit": (
            "Read-only linked-image permanence gate. It changes no product "
            "artifact and authorizes no device action by itself."),
    }
    value["mutations_rejected"] = mutations(model)
    return value


def record() -> None:
    require(not RECEIPT.exists(), "content-DMA absence receipt exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("content-DMA structural absence: PASS unsafe=0 born-derived")


def check() -> None:
    require(RECEIPT.read_bytes() == canonical(derive()),
            "content-DMA structural absence receipt drift")
    print("content-DMA structural absence: CHECK PASS unsafe=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    {"record": record, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AbsenceError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"content-DMA structural absence: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
