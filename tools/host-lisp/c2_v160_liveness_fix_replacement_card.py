#!/usr/bin/env python3
"""Run the real-consumer replacement for the retirement-liveness card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402
import c2_v160_liveness_config as CONFIG  # noqa: E402
import c2_v160_liveness_fix_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-liveness-fix-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-liveness-fix-replacement-process"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-liveness-fix-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-liveness-fix-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "41f2d958"
FORMAT = "lisp65-c2-v160-retirement-liveness-fix-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 RETIREMENT LIVENESS REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX FINAL WORLD GREEN"
TAG = "retirement-liveness-replacement"


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
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("self-disposition 1/3", "bound != consumed",
                  "exactly one replacement card", "transitive product-root configure()",
                  "real-process argv gate", "zero cards were consumed"):
        require(token in text, f"liveness replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red["status"] == "FINAL RED: V1.6 RETIREMENT LIVENESS FIX STOPS"
            and red["error"]["message"].endswith("c2_rtov_retire_continuations (0)")
            and red["classification"]["known_family"] ==
                "bound-not-consumed at the real compiler-profile projection"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["retry_authorized"] is False,
            "liveness predecessor Final Red drift")
    return red


def configure_module() -> None:
    # The real-process witness re-enters this configurator through the
    # inherited producer.  Preserve its probe-owned paths instead of
    # snapping the transitive gates back onto the card-owned namespace.
    active_build = BASE.BUILD
    active_preflight = BASE.PREFLIGHT
    probing = active_build in (NORMAL_BUILD, MUTANT_BUILD)
    build = active_build if probing else BUILD
    preflight = active_preflight if probing else PREFLIGHT
    tag = (TAG + "-process-mutant" if active_build == MUTANT_BUILD
           else TAG + "-process-normal" if probing
           else TAG)
    PREV.set_paths(build, preflight, tag=tag)
    BASE.PREV.configure_module()
    current_single_link = PRODUCT.single_link
    if not getattr(current_single_link, "_v160_retirement_liveness", False):
        def single_link_with_liveness(*args: Any, **kwargs: Any) -> Any:
            # This is the first real compiler consumer after the complete
            # historical configure chain.  Select the successor here, where
            # no later restore can replace a bound-but-not-consumed profile.
            CONFIG.restore_predecessor(PRODUCT)
            CONFIG.configure(PRODUCT)
            definitions = tuple(kwargs.get("probe_definitions", ()))
            require(CONFIG.FEATURE not in definitions,
                    "liveness feature already entered single-link arguments")
            kwargs["probe_definitions"] = (*definitions, CONFIG.FEATURE)
            try:
                return current_single_link(*args, **kwargs)
            finally:
                # The linked artifacts and resolved profile own the successor
                # world after this boundary.  Do not leave mutable build
                # configuration active for historical post-link readers.
                CONFIG.restore_predecessor(PRODUCT)

        single_link_with_liveness._v160_retirement_liveness = True  # type: ignore[attr-defined]
        single_link_with_liveness._v160_retirement_delegate = current_single_link  # type: ignore[attr-defined]
        PRODUCT.single_link = single_link_with_liveness


def install() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT; PREV.PROCESS = PROCESS
    PREV.NORMAL_BUILD = NORMAL_BUILD; PREV.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    PREV.MUTANT_BUILD = MUTANT_BUILD; PREV.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    PREV.PRODUCT_ELF = PRODUCT_ELF; PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED; PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority; PREV.predecessor = predecessor
    PREV.configure_module = configure_module
    BASE.authority = authority; BASE.predecessor = predecessor
    BASE.configure_module = configure_module
    BASE.process_gate = process_gate


def real_consumer_gate(value: dict[str, Any]) -> dict[str, Any]:
    normal = value["real_process_argv_witness"]["normal"]
    rows = normal["processes"]
    sources = set(normal["source_order"])
    new_service = CONFIG.NEW_SERVICE.relative_to(ROOT).as_posix()
    new_padding = CONFIG.NEW_PADDING.relative_to(ROOT).as_posix()
    old_service = CONFIG.OLD_SERVICE.relative_to(ROOT).as_posix()
    old_padding = CONFIG.OLD_PADDING.relative_to(ROOT).as_posix()
    require(rows and all(CONFIG.FEATURE in row["feature_defines"] for row in rows)
            and new_service in sources and new_padding in sources
            and old_service not in sources and old_padding not in sources,
            "real compiler processes did not consume liveness world")
    red = load(PREDECESSOR_RED)
    resolved = ROOT / red["artifacts"]["resolved_profile"]["path"]
    require(bind(resolved)["sha256"] == red["artifacts"]["resolved_profile"]["sha256"],
            "frozen predecessor resolved-profile identity drift")
    historical = resolved.read_text(encoding="utf-8")
    mutation_rejected = (new_service not in historical and new_padding not in historical
        and old_service in historical and old_padding in historical
        and CONFIG.FEATURE not in historical)
    require(mutation_rejected, "predecessor-consumption mutation did not reproduce")
    return {"status": "PASS: REAL COMPILER CONSUMES LIVENESS SUCCESSORS",
        "compiler_processes": len(rows), "all_processes_carry_feature": True,
        "successor_sources": [new_service, new_padding],
        "predecessor_sources_absent": True,
        "frozen_predecessor_mutation_rejected": True,
        "predecessor_resolved_profile": bind(resolved)}


def discard_process_probe_outputs() -> None:
    """Discard only ephemeral outputs owned by the real-process witness."""
    suffixes = ("qualification", "real-probe", "real-preflight",
        "profile-probe", "profile-preflight", "fold-probe", "fold-preflight",
        "fold-mutant", "fold-mutant-preflight", "contract-probe",
        "contract-preflight", "contract-mutant", "contract-mutant-preflight")
    paths = [PROCESS, *(ROOT / "build/c2.3" /
        ("retirement-liveness-fix-" + suffix) for suffix in suffixes)]
    for path in paths:
        if not path.exists():
            continue
        for root, directories, files in os.walk(path):
            os.chmod(root, 0o755)
            for name in directories:
                child = Path(root) / name
                if not child.is_symlink():
                    os.chmod(child, 0o755)
            for name in files:
                child = Path(root) / name
                if not child.is_symlink():
                    os.chmod(child, 0o644)
        shutil.rmtree(path)


def process_gate() -> dict[str, Any]:
    """Re-prove the changed normal world; inherit the orthogonal snapshot red."""
    discard_process_probe_outputs()
    normal = BASE.child_value("_process_probe")
    discard_process_probe_outputs()
    primary = load(PREV.PRIMARY_RECEIPT)
    inherited = primary["real_process_argv_witness"]["snapshot_mutation"]
    require(normal["all_capture"] is True and normal["all_hybrid"] is True
            and normal["consumer_source_process_present"] is True
            and inherited["all_capture"] is True
            and inherited["all_hybrid"] is False
            and inherited["consumer_source_process_present"] is False,
            "live normal/inherited snapshot decision table drift")
    return {"status": "PASS: LIVE STACK PLUS LIVENESS REACH REAL COMPILERS",
        "normal": normal, "snapshot_mutation": inherited,
        "snapshot_mutation_authority": bind(PREV.PRIMARY_RECEIPT),
        "configured_source_count_delta": 1, "permanent_gate": True}


def preflight() -> None:
    install(); predecessor(); authority()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, PROCESS,
        NORMAL_BUILD, NORMAL_PREFLIGHT, MUTANT_BUILD, MUTANT_PREFLIGHT,
        RECEIPT, FINAL_RED)), "liveness replacement is one-shot")
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    gate = real_consumer_gate(value)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "replacement_authority": authority(), "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_liveness_consumer": gate,
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 liveness replacement: PREFLIGHT PASS card=0/1 real-consumer=green")


def card() -> None:
    install(); configure_module(); armed = load(PREFLIGHT / "preflight.json")
    require(armed["status"] == PREFLIGHT_STATUS
            and armed["real_liveness_consumer"]["all_processes_carry_feature"] is True,
            "persisted real-consumer preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "replacement_authority": authority(), "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_liveness_consumer": armed["real_liveness_consumer"],
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent review; then same-world media and owner acceptance with abort row"})
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 liveness replacement: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    install(); configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 RETIREMENT LIVENESS REPLACEMENT STOPS",
            "replacement_authority": authority(), "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "retry_authorized": False, "media_authorized": False, "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe", "_process_probe_mutant",
        "_contract_probe", "_contract_probe_mutant", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce", "_scope", "_accept",
        "_r1_arm", "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    install()
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        value = load(RECEIPT); require(value["status"] == FINAL_STATUS,
            "liveness replacement receipt drift")
        print("v1.6 liveness replacement: CHECK PASS final-world=green")
    elif action == "_process_probe":
        configure_module(); BASE.process_probe_child(mutant=False)
    elif action == "_process_probe_mutant":
        configure_module(); BASE.process_probe_child(mutant=True)
    else:
        configure_module(); BASE.PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"liveness replacement Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 liveness replacement: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
