#!/usr/bin/env python3
"""Run the one owner-authorized Link-116 WYSIWYG replacement card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
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
import c2_v21_wysiwyg_input_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
REPL = ROOT / "src/repl.c"
BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card-preflight-r3")
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
SEMANTIC_RECEIPT = PREFLIGHT / "semantic-repl-compile.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / "c2.3-v2.1-wysiwyg-input-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-wysiwyg-input-card-red-attribution-receipt.json")
PRICING = ARCH / "c2.3-v2.1-wysiwyg-text-recovery-pricing-receipt.json"
WYSIWYG = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
ORIGIN = ARCH / "c2.3-v2.1-a0-origin-attribution-receipt.json"
PRIOR_ACCEPTANCE = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-acceptance-receipt.json")
PRIOR_MEDIA = ARCH / (
    "c2.3-v2.1-configurator-parity-completion-media-receipt.json")
PRIOR_ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "eb688c60"
LINK = 116
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-text-recovery-replacement-card-v1"
STATUS = "PASS: LINK-116 WYSIWYG TEXT-RECOVERY REPLACEMENT CARD GREEN"
RECORDED_ON = "2026-08-17"

_LINKED_WYSIWYG = BASE.linked_wysiwyg


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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


def git_bind(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, value = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("text-recovery pricing ii", "winner by price",
                  "ordinary-text bytes", "contracted cold relocation",
                  "margins stay non-budgets", "one replacement card"):
        require(token in text, f"replacement authority token absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    red, attribution, pricing = (load(PREDECESSOR_RED), load(ATTRIBUTION),
                                 load(PRICING))
    require(red["status"] == "FINAL RED: WYSIWYG card returns to owner"
            and red["retry_authorized"] is False
            and red["attempt_accounting"]["cards_consumed"] == 1
            and attribution["capacity"]["ordinary_text_deficit_bytes"] == 13
            and pricing["status"] ==
                "PRICED: 42-BYTE SEMANTIC MICRO-RECOVERY WINS"
            and pricing["decision"]["winner"] ==
                "option-a-semantic-instruction-selection"
            and pricing["decision"]["replacement_cards_authorized"] == 1
            and pricing["decision"]["replacement_cards_consumed"] == 0,
            "Link-115 Final Red/pricing authority drift")
    return {
        "Link115_Final_Red": bind(PREDECESSOR_RED),
        "Link115_attribution": bind(ATTRIBUTION), "pricing": bind(PRICING),
        "WYSIWYG": bind(WYSIWYG), "origin": bind(ORIGIN),
        "prior_acceptance": bind(PRIOR_ACCEPTANCE),
        "prior_media": bind(PRIOR_MEDIA), "prior_ELF": bind(PRIOR_ELF),
    }


def set_paths() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.SEMANTIC_RECEIPT = SEMANTIC_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    BASE.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.WYSIWYG = WYSIWYG
    BASE.ORIGIN = ORIGIN
    BASE.PRIOR_ACCEPTANCE = PRIOR_ACCEPTANCE
    BASE.PRIOR_MEDIA = PRIOR_MEDIA
    BASE.PRIOR_ELF = PRIOR_ELF
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.LINK = LINK
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS
    BASE.RECORDED_ON = RECORDED_ON
    BASE.set_paths()


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    require(completed.returncode == 0 and token in completed.stdout,
            f"fresh {label} red:\n{completed.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(completed.stdout.split())}


def host_gates() -> dict[str, Any]:
    inherited = BASE.PRODUCT.host_gates()
    inherited.update({
        "WYSIWYG_input": run_gate(
            [sys.executable, str(HOST / "c2_v21_wysiwyg_input.py"), "check"],
            "fixtures=2 canonical-bytes=12 mutations=17", "WYSIWYG input"),
        "A0_origin": run_gate(
            [sys.executable, str(HOST / "c2_v21_a0_origin_attribution.py"),
             "check"], "mutations=17", "A0 origin"),
        "text_recovery_pricing": run_gate(
            [sys.executable,
             str(HOST / "c2_v21_wysiwyg_text_recovery_pricing.py"), "check"],
            "micro=42 cold=374 image-delta=512 mutations=15",
            "text-recovery pricing"),
    })
    return inherited


def preflight_value() -> dict[str, Any]:
    semantic, pricing = load(SEMANTIC_RECEIPT), load(PRICING)
    require(semantic["status"].startswith("PASS")
            and semantic["source"] == bind(REPL)
            and semantic["compiler_definition_count"] == 73
            and semantic["candidate_static_bytes_consumed"] == 46043
            and pricing["option_a_micro"]["resident_bytes_recovered_nolto"] == 42
            and pricing["option_a_micro"]["checks_removed"] == 0,
            "replacement semantic/pricing preflight drift")
    set_paths()
    BASE.PRODUCT.configure()
    source = BASE.PRODUCT.BASE.configure_root_source()
    return {
        "format": "lisp65-c2.3-v2.1-wysiwyg-text-recovery-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: WYSIWYG Link-116 replacement card armed 0/1",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "delta": "src/repl.c semantic instruction selection only",
            "source_owner_projection": source},
        "capacity": {"minimum_recovery_bytes": 13,
            "priced_recovery_bytes": 42, "projected_headroom_bytes": 29,
            "mapped_far_facade_fixed": True,
            "contracted_margins_used_as_freight": False},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": host_gates(),
        "semantic_compile": bind(SEMANTIC_RECEIPT),
        "authority": {"owner": authorization(), **predecessor(),
            # Product-source identity is its content, not whichever later
            # bookkeeping commit happens to be HEAD when the card resumes.
            "implementation": bind(REPL),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value["status"] ==
                "PASS: WYSIWYG Link-116 replacement card armed 0/1"
            and value["configuration"]["link"] == LINK
            and value["configuration"]["cards_authorized"] == 1
            and value["configuration"]["delta"] ==
                "src/repl.c semantic instruction selection only"
            and value["capacity"] == {"minimum_recovery_bytes": 13,
                "priced_recovery_bytes": 42, "projected_headroom_bytes": 29,
                "mapped_far_facade_fixed": True,
                "contracted_margins_used_as_freight": False}
            and value["attempt_accounting"] == {
                "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
                "completion_runs": 0, "media_builds": 0,
                "device_contacts": 0}
            and {"WYSIWYG_input", "A0_origin", "text_recovery_pricing"}
                <= set(value["host_gates"])
            and value["authority"]["implementation"] == bind(REPL),
            "replacement-card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["configuration"].update(
            cards_authorized=2),
        "wrong-link": lambda x: x["configuration"].update(link=115),
        "grow-scope": lambda x: x["configuration"].update(delta="repl+reader"),
        "recover-twelve": lambda x: x["capacity"].update(
            priced_recovery_bytes=12),
        "move-facade": lambda x: x["capacity"].update(
            mapped_far_facade_fixed=False),
        "spend-margin": lambda x: x["capacity"].update(
            contracted_margins_used_as_freight=True),
        "spend-card": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
        "run-WPLTO": lambda x: x["attempt_accounting"].update(WPLTO_runs=1),
        "link-product": lambda x: x["attempt_accounting"].update(
            product_links=1),
        "build-media": lambda x: x["attempt_accounting"].update(media_builds=1),
        "contact-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
        "drop-WYSIWYG": lambda x: x["host_gates"].pop("WYSIWYG_input"),
        "drop-origin": lambda x: x["host_gates"].pop("A0_origin"),
        "drop-pricing": lambda x: x["host_gates"].pop("text_recovery_pricing"),
        "pin-implementation-to-head": lambda x: x["authority"].update(
            implementation={**x["authority"]["implementation"],
                            "commit": "moving-HEAD"}),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial)
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def linked_wysiwyg() -> dict[str, Any]:
    result = _LINKED_WYSIWYG()
    paths = BASE.artifact_paths()
    elf = next(path for path in paths.values() if path.suffix == ".elf")
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    failed = load(ATTRIBUTION)["capacity"]["candidate_seed_map"]
    end = text.address + text.bytes
    recovery = failed["ordinary_text_end_exclusive"] - end
    headroom = facade.address - end
    pricing = load(PRICING)
    require(facade.address == 0xB3B0 and facade.bytes == 98
            and end <= facade.address and recovery >= 13 and headroom >= 0
            and pricing["option_a_micro"]["checks_removed"] == 0,
            "replacement linked capacity/facade contract red")
    result["capacity"] = {
        "failed_Link115_end_exclusive":
            f"0x{failed['ordinary_text_end_exclusive']:04x}",
        "Link116_end_exclusive": f"0x{end:04x}",
        "facade_start": f"0x{facade.address:04x}",
        "facade_bytes": facade.bytes,
        "final_recovery_bytes": recovery, "final_headroom_bytes": headroom,
        "minimum_recovery_bytes": 13,
        "contracted_margins_used_as_freight": False,
    }
    result["pricing"] = bind(PRICING)
    return result


def install() -> None:
    set_paths()
    BASE.authorization = authorization
    BASE.predecessor = predecessor
    BASE.host_gates = host_gates
    BASE.preflight_value = preflight_value
    BASE.validate_preflight = validate_preflight
    BASE.preflight_mutations = preflight_mutations
    BASE.linked_wysiwyg = linked_wysiwyg


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in BASE.artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": (
            "lisp65-c2.3-v2.1-wysiwyg-text-recovery-replacement-final-red-v1"),
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: Link-116 replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Replacement card consumed; no Completion/media/device.",
    }))


def check() -> None:
    install()
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["status"] ==
                    "FINAL RED: Link-116 replacement returns to owner"
                and value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "Link-116 Final Red drift")
        print("WYSIWYG replacement card: CHECK FINAL RED")
    elif RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"] == STATUS
                and value["attempt_accounting"]["cards_consumed"] == 1
                and value["artifacts_before"] == BASE.frozen_artifacts()
                and value["artifacts_after"] == value["artifacts_before"]
                and value["linked_WYSIWYG"]["capacity"][
                    "final_recovery_bytes"] >= 13,
                "Link-116 green receipt drift")
        print("WYSIWYG replacement card: CHECK PASS link=116 card=1/1")
    else:
        print("WYSIWYG replacement card: CHECK LOCKED/ARMED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_semantic", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    install()
    actions = {"preflight": BASE.preflight, "card": BASE.card,
               "check": check, "_semantic": BASE.semantic_child,
               "_produce": BASE.produce_child, "_scope": BASE.scope_child,
               "_accept": BASE.acceptance_child}
    actions[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"Link-116 Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"WYSIWYG replacement card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
