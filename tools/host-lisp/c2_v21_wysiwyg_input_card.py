#!/usr/bin/env python3
"""Run the one authorized Link-115 WYSIWYG input product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_probe_oracle_root_padding_replacement_card as PRODUCT  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as CONFIG  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
REPL = ROOT / "src/repl.c"
BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-input-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-wysiwyg-input-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
SEMANTIC_RECEIPT = PREFLIGHT / "semantic-repl-compile.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
RECEIPT = ARCH / "c2.3-v2.1-wysiwyg-input-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-wysiwyg-input-card-final-red.json"
WYSIWYG = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
ORIGIN = ARCH / "c2.3-v2.1-a0-origin-attribution-receipt.json"
PRIOR_ACCEPTANCE = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-acceptance-receipt.json")
PRIOR_MEDIA = ARCH / "c2.3-v2.1-configurator-parity-completion-media-receipt.json"
PRIOR_ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "01914313"
LINK = 115
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-input-card-v1"
STATUS = "PASS: LINK-115 WYSIWYG INPUT CARD GREEN"
RECORDED_ON = "2026-08-17"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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
    for token in ("the wysiwyg card is released", "$a0 → $20",
                  "unmappable controls reject visibly",
                  "canonical 12-byte object", "one product card"):
        require(token in text, f"card authority token absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    acceptance, media, fix = load(PRIOR_ACCEPTANCE), load(PRIOR_MEDIA), load(WYSIWYG)
    require(acceptance.get("status")
                == "PASS: configurator-parity finals accepted read-only"
            and media.get("status")
                == "PASS: configurator-parity Completion/media closed; D2 ready"
            and fix.get("status", "").startswith("PASS: A0-TO-SPACE")
            and fix["scope"]["product_cards_authorized"] == 1
            and fix["scope"]["product_cards_consumed"] == 0,
            "WYSIWYG predecessor/standing freight drift")
    return {"acceptance": bind(PRIOR_ACCEPTANCE), "media": bind(PRIOR_MEDIA),
            "fix": bind(WYSIWYG), "origin": bind(ORIGIN),
            "prior_ELF": bind(PRIOR_ELF)}


def set_paths() -> None:
    PRODUCT.BUILD = BUILD
    PRODUCT.PREFLIGHT = PREFLIGHT
    PRODUCT.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PRODUCT.INVOCATION = INVOCATION
    PRODUCT.PRODUCER_RESULT = PRODUCER_RESULT
    PRODUCT.SCOPE_RESULT = SCOPE_RESULT
    PRODUCT.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PRODUCT.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    PRODUCT.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    PRODUCT.ABI_REPORT = ABI_REPORT
    PRODUCT.RECEIPT = BUILD / "unused-predecessor-card-receipt.json"
    PRODUCT.FINAL_RED = BUILD / "unused-predecessor-card-final-red.json"
    PRODUCT.DRIVER = DRIVER
    PRODUCT.LINK = LINK
    PRODUCT.set_paths()


def configure() -> None:
    set_paths()
    PRODUCT.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return PRODUCT.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    configure()
    return PRODUCT.frozen_artifacts()


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0 and token in run.stdout,
            f"fresh {label} red:\n{run.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(run.stdout.split())}


def semantic_child() -> None:
    require(PREFLIGHT.is_dir() and not SEMANTIC_RECEIPT.exists(),
            "semantic preflight output ownership drift")
    _old, projection = CONFIG.configure_projected_candidate()
    prefix, static = CONFIG.configured_compile_prefix(projection)
    target = PREFLIGHT / "semantic-repl.c.o"
    command = [*prefix, "-c", "src/repl.c", "-o",
               target.relative_to(ROOT).as_posix()]
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0 and target.is_file(),
            f"real semantic repl compile red:\n{run.stdout}")
    value = {
        "status": "PASS: current repl consumed by real configured compiler",
        "source": bind(REPL), "object": bind(target),
        "compiler_definition_count": len(
            projection["final_state"]["compiler_definitions"]),
        "configured_feature_count": len(projection["combined_compiler_features"]),
        "candidate_static_header": static["bound_header"],
        "candidate_static_bytes_consumed": static["consumed_value"],
        "command_role": "semantic compile only; no LTO or link",
    }
    require(value["compiler_definition_count"] == 73
            and value["candidate_static_bytes_consumed"] == 46043,
            "semantic product configuration drift")
    SEMANTIC_RECEIPT.write_bytes(canonical(value))
    print("WYSIWYG card: SEMANTIC PREFLIGHT PASS definitions=73")


def host_gates() -> dict[str, Any]:
    inherited = PRODUCT.host_gates()
    inherited.update({
        "WYSIWYG_input": run_gate(
            [sys.executable, str(HOST / "c2_v21_wysiwyg_input.py"), "check"],
            "fixtures=2 canonical-bytes=12 mutations=17", "WYSIWYG input"),
        "A0_origin": run_gate(
            [sys.executable, str(HOST / "c2_v21_a0_origin_attribution.py"),
             "check"], "mutations=17", "A0 origin"),
    })
    return inherited


def preflight_value() -> dict[str, Any]:
    semantic = load(SEMANTIC_RECEIPT)
    require(semantic["status"].startswith("PASS")
            and semantic["source"] == bind(REPL)
            and semantic["compiler_definition_count"] == 73
            and semantic["candidate_static_bytes_consumed"] == 46043,
            "semantic preflight receipt drift")
    configure()
    source = PRODUCT.BASE.configure_root_source()
    return {
        "format": "lisp65-c2.3-v2.1-wysiwyg-input-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: WYSIWYG Link-115 card armed 0/1",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "delta": "src/repl.c input boundary only",
            "source_owner_projection": source},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": host_gates(),
        "semantic_compile": bind(SEMANTIC_RECEIPT),
        "authority": {"owner": authorization(), **predecessor(),
            "implementation": git_bind("HEAD", REPL)[1],
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value["status"] == "PASS: WYSIWYG Link-115 card armed 0/1"
            and value["configuration"]["link"] == LINK
            and value["configuration"]["cards_authorized"] == 1
            and value["configuration"]["delta"]
                == "src/repl.c input boundary only"
            and value["attempt_accounting"] == {
                "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
                "completion_runs": 0, "media_builds": 0,
                "device_contacts": 0}
            and {"WYSIWYG_input", "A0_origin"} <= set(value["host_gates"]),
            "WYSIWYG card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["configuration"].update(cards_authorized=2),
        "change-link": lambda x: x["configuration"].update(link=114),
        "grow-scope": lambda x: x["configuration"].update(delta="reader+repl"),
        "spend-card": lambda x: x["attempt_accounting"].update(cards_consumed=1),
        "run-WPLTO": lambda x: x["attempt_accounting"].update(WPLTO_runs=1),
        "link-product": lambda x: x["attempt_accounting"].update(product_links=1),
        "build-media": lambda x: x["attempt_accounting"].update(media_builds=1),
        "contact-device": lambda x: x["attempt_accounting"].update(device_contacts=1),
        "drop-WYSIWYG": lambda x: x["host_gates"].pop("WYSIWYG_input"),
        "drop-origin": lambda x: x["host_gates"].pop("A0_origin"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "WYSIWYG preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "WYSIWYG card is one-shot")
    set_paths()
    PRODUCT.BASE.write_projections()
    run = subprocess.run([sys.executable, str(DRIVER), "_semantic"], cwd=ROOT,
                         text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    require(run.returncode == 0, f"semantic child red:\n{run.stdout}")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("WYSIWYG card: PREFLIGHT PASS card=0/1 mutations=10")


def produce_child() -> None:
    configure()
    raise SystemExit(PRODUCT.produce_child())


def scope_child() -> None:
    configure()
    raise SystemExit(PRODUCT.scope_child())


def acceptance_child() -> None:
    configure()
    raise SystemExit(PRODUCT.acceptance_child())


def run_child(action: str) -> None:
    run = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
                         text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    require(run.returncode == 0, f"WYSIWYG child {action} red:\n{run.stdout}")


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    at = symbol.value - section.address
    require(0 <= at and at + symbol.bytes <= len(raw),
            f"symbol outside section: {name}")
    return raw[at:at + symbol.bytes]


def linked_wysiwyg() -> dict[str, Any]:
    paths = artifact_paths()
    elf = next(path for path in paths.values() if path.suffix == ".elf")
    readobj = ROOT / "tools/llvm-mos/bin/llvm-readobj"
    truth = ElfTruth.read(elf, llvm_readobj=readobj, include_section_data=True)
    prior = ElfTruth.read(PRIOR_ELF, llvm_readobj=readobj,
                          include_section_data=True)
    raw = symbol_bytes(truth, "repl")
    old = symbol_bytes(prior, "repl")
    abort = truth.symbol("lisp_abort_code").value
    abort_call = bytes((0x20, abort & 0xFF, (abort >> 8) & 0xFF))
    visible_reject = bytes((0xA9, 0x05)) + abort_call
    near_normalization = any(
        raw[index:index + 2] == b"\xC9\xA0"
        and b"\xA9\x20" in raw[index + 2:index + 18]
        for index in range(max(0, len(raw) - 1)))
    profile = BUILD / "wplto/resolved-profile.txt"
    repl_sha = hashlib.sha256(REPL.read_bytes()).hexdigest()
    require(raw != old and visible_reject in raw and near_normalization
            and f"input_sha256=src/repl.c:{repl_sha}" in
                profile.read_text(encoding="utf-8"),
            "linked image does not carry the WYSIWYG input boundary")
    return {"ELF": bind(elf), "repl": {"address": f"0x{truth.symbol('repl').value:04x}",
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "predecessor_sha256": hashlib.sha256(old).hexdigest()},
            "a0_to_space_machine_path": True,
            "visible_reader_error_machine_path": True,
            "consumed_repl_sha256": repl_sha}


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(expected)
    require(persisted == expected and rejected == preflight_mutations(expected),
            "WYSIWYG card preflight receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "WYSIWYG product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(before == after, "WYSIWYG acceptance changed product artifacts")
    producer, scope, acceptance = (load(PRODUCER_RESULT), load(SCOPE_RESULT),
                                    load(ACCEPTANCE_RESULT))
    product = PRODUCT.linked_product()
    wysiwyg = linked_wysiwyg()
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4
            and acceptance.get("status") == "PASS"
            and acceptance["VMA_golden"]["dependent_fixed_vmas"] == 101
            and acceptance["VMA_golden"]["dependent_free_derived_vmas"] == 2,
            "WYSIWYG linked acceptance drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), **predecessor(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_WYSIWYG": wysiwyg, "linked_product": product,
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "WYSIWYG": load(WYSIWYG)["mutations_rejected"]},
        "next": "Completion and same-world media, then D2 poison regression",
        "claim_limit": "One product card; Completion/media/device not run.",
    }
    RECEIPT.write_bytes(canonical(value))
    print("WYSIWYG card: CARD PASS link=115 card=1/1")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-wysiwyg-input-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: WYSIWYG card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Card consumed; no Completion, media, or device."}))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "WYSIWYG Final Red drift")
        print("WYSIWYG card: CHECK FINAL RED")
    elif RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"] == STATUS
                and value["attempt_accounting"]["cards_consumed"] == 1
                and value["artifacts_before"] == frozen_artifacts()
                and value["artifacts_after"] == value["artifacts_before"],
                "WYSIWYG green receipt drift")
        print("WYSIWYG card: CHECK PASS link=115 card=1/1")
    else:
        print("WYSIWYG card: CHECK LOCKED/ARMED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_semantic", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_semantic": semantic_child, "_produce": produce_child,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"WYSIWYG Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"WYSIWYG card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
