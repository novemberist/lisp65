#!/usr/bin/env python3
"""Consume the MAP-CPU repair from the candidate-generated source closure."""

from __future__ import annotations

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

import c2_v160_boot_refill_dma_closure as CLOSURE  # noqa: E402
import c2_v160_boot_refill_dma_fix_card as PREV  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as PROJECTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-replacement-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-replacement-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-map-cpu-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-boot-refill-map-cpu-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-boot-refill-map-cpu-card-final-red.json"
FIRST_BUILD = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-card"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "6a63bb62"
FORMAT = "lisp65-c2-v160-boot-refill-map-cpu-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOOT REFILL CANDIDATE SOURCE ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOOT REFILL CANDIDATE SOURCE FINAL WORLD GREEN"
_ORIGINAL_EXACT = PROJECTION.exact_source_list


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("generated candidate bound, frozen generator consumed",
                  "codex self-disposition 1/3", "current candidate wplto",
                  "real compiler invocation", "exact feature tuple"):
        require(token in text, f"replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red["status"] == "FINAL RED: V1.6 BOOT REFILL MAP-CPU CARD STOPS"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0}
            and red["retry_authorized"] is False,
            "boot-refill predecessor Red drift")
    generated = FIRST_BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
    red_elf = FIRST_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    model = CLOSURE.linked_read_model(red_elf)
    require(CLOSURE.source_gate(generated.read_text(encoding="utf-8"))[
                "failure_propagated"] is True
            and model["product_entry"]["raw_read_edges"] == 1
            and model["product_entry"]["MAP_CPU_edges"] == 0,
            "bound-not-consumed counterproof drift")
    return {"Final_Red": bind(PREDECESSOR_RED),
            "bound_candidate_source": bind(generated),
            "consumed_final_ELF": bind(red_elf),
            "candidate_bound_but_not_consumed": True}


def candidate_exact_source_list(
        rows: list[dict[str, Any]], expected: tuple[str, ...]
        ) -> Callable[..., list[str]]:
    inherited = _ORIGINAL_EXACT(rows, expected)

    def selected(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        paths = inherited(extra_definitions)
        result: list[str] = []
        replaced: list[str] = []
        for raw in paths:
            path = Path(raw)
            if "generated-product-sources" not in path.parts:
                result.append(raw)
                continue
            candidate = BUILD / "wplto/generated-product-sources" / path.name
            require(candidate.is_file() and not candidate.is_symlink(),
                    f"candidate-generated compiler input absent: {path.name}")
            result.append(str(candidate))
            replaced.append(path.name)
        require("c2_product_runtime.c" in replaced,
                "candidate runtime escaped generated-source projection")
        return result

    return selected


def projection_gate() -> dict[str, Any]:
    frozen = load(PROJECTION.PREFLIGHT)["inputs"]["compiler_inputs"]
    names = sorted(Path(row["path"]).name for row in frozen
                   if "generated-product-sources" in Path(row["path"]).parts)
    require("c2_product_runtime.c" in names,
            "frozen closure lacks product runtime counterexample")
    return {"status": "PASS: GENERATED SOURCES PROJECT FROM LIVE CANDIDATE",
            "frozen_generated_members": names,
            "candidate_root": (BUILD / "wplto/generated-product-sources").
                relative_to(ROOT).as_posix(),
            "replacement_rule": "basename under candidate-owned generated root",
            "mutations_rejected": ["restore-frozen-generated-runtime",
                                   "omit-candidate-runtime"]}


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = PROCESS
    PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.install()


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "replacement_authority": authority(), "predecessor": predecessor(),
        "candidate_source_projection": projection_gate(),
        "source_gate": CLOSURE.source_gate(),
        "source_mutations_rejected": CLOSURE.source_mutations(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "boot-refill replacement card is one-shot")
    predecessor(); authority(); PREV.preflight(); append_preflight()
    print("v1.6 boot refill replacement: PREFLIGHT PASS card=0/1 "
          "candidate-source=bound")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["boot_refill_DMA_closure"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["unsafe_content_DMA_count"] == 0
            and gate["product_entry"]["raw_read_edges"] == 0
            and gate["product_entry"]["MAP_CPU_edges"] >= 1
            and gate["instrument"]["neutral"] is True,
            "boot-refill replacement final receipt drift")
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS,
            "persisted replacement preflight drift")
    old = PROJECTION.exact_source_list
    PROJECTION.exact_source_list = candidate_exact_source_list
    try:
        PREV.card()
    finally:
        PROJECTION.exact_source_list = old
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = CLOSURE.linked_read_model(elf)
    CLOSURE.validate_final(gate)
    mutations = CLOSURE.final_mutations(gate)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "replacement_authority": authority(), "predecessor": predecessor(),
        "candidate_source_projection": projection_gate(),
        "compiled_candidate_runtime": bind(
            BUILD / "wplto/generated-product-sources/c2_product_runtime.c"),
        "boot_refill_DMA_closure": gate,
        "mutations_rejected": mutations,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope and acceptance; no media before final-world green"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 boot refill replacement: CARD PASS card=1/1 unsafe=0")


def record_red(error: Exception) -> None:
    value = {"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 BOOT REFILL REPLACEMENT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "replacement_authority": authority(), "predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "media_authorized": False,
        "next": "full chain to reviewer; no autonomous successor"}
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 boot refill replacement: CHECK PASS"); return 0
    return PREV.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"boot-refill replacement Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 boot refill replacement: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
