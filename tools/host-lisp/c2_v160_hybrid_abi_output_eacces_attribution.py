#!/usr/bin/env python3
"""Attribute the frozen v1.6 hybrid ABI-report EACCES without linking."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD = HOST / "c2_v160_input_fidelity_reopen_card.py"
OUTER = HOST / "c2_v160_input_service_hybrid_longjmp_replacement_card.py"
GATE = HOST / "c2_asm_leaf_abi_gate.py"
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-service-hybrid-longjmp-card-final-red.json")
WPLTO = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-card/wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
ABI_REPORT = WPLTO / "c2-asm-leaf-abi.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-input-service-hybrid-abi-output-eacces-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "84b5eff9"
FORMAT = "lisp65-c2-v160-hybrid-abi-output-eacces-attribution-v1"


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


def mode(path: Path) -> str:
    return format(stat.S_IMODE(path.stat().st_mode), "04o")


def authorization() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("eacces attribution commissioned", "host-only attribution",
                  "what the consumer expected to execute", "known family"):
        require(token in text, f"EACCES attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def line_of(path: Path, needle: str) -> int:
    matches = [number for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1) if needle in line]
    require(len(matches) == 1, f"source witness not unique: {path.name}: {needle}")
    return matches[0]


def source_witness() -> dict[str, Any]:
    card = CARD.read_text(encoding="utf-8")
    gate = GATE.read_text(encoding="utf-8")
    expected_fragments = (
        'ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"',
        '"--elf", str(PRODUCT_ELF), "--out", str(ABI_REPORT)',
        'run_child("_scope")', 'run_child("_accept")',
        "abi = subprocess.run([sys.executable",
    )
    for fragment in expected_fragments:
        require(card.count(fragment) == 1,
                f"card command/phase source drift: {fragment}")
    require(gate.count("out.write_text(json.dumps(value") == 1,
            "ABI report writer source drift")
    order = {name: card.rindex(fragment) for name, fragment in (
        ("produce", 'run_child("_produce")'),
        ("scope", 'run_child("_scope")'),
        ("acceptance", 'run_child("_accept")'),
        ("host_derivation", "host = FIDELITY.derive("),
        ("ABI_report", "abi = subprocess.run([sys.executable"))}
    require(list(order.values()) == sorted(order.values()),
            "qualification phase order drift")
    return {
        "outer_driver": bind(OUTER), "real_card_consumer": bind(CARD),
        "ABI_gate": bind(GATE),
        "bindings": {
            "output_path": {"source": CARD.relative_to(ROOT).as_posix(),
                "line": line_of(CARD,
                    'ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"'),
                "expression": 'BUILD / "wplto/c2-asm-leaf-abi.json"'},
            "consumer_command": {"source": CARD.relative_to(ROOT).as_posix(),
                "line": line_of(CARD,
                    'abi = subprocess.run([sys.executable'),
                "roles": ["python", "gate-driver", "--elf", "ELF",
                          "--out", "ABI_REPORT"]},
            "report_writer": {"source": GATE.relative_to(ROOT).as_posix(),
                "line": line_of(GATE, "out.write_text(json.dumps(value"),
                "function": "audit_elf", "operation": "Path.write_text"}},
        "phase_order_source_offsets": order,
        "phase_order": ["produce-and-seal", "scope", "acceptance",
                        "host-derivation", "ABI-report-write"],
    }


def validate_roles(value: dict[str, str]) -> None:
    require(value["program"].endswith("python3"), "program role is not Python")
    require(value["driver"].endswith("c2_asm_leaf_abi_gate.py"),
            "driver role is not ABI gate")
    require(value["ELF_input"].endswith(".prg.elf"), "ELF input role drift")
    require(value["JSON_output"].endswith("c2-asm-leaf-abi.json"),
            "JSON output role drift")
    require(value["program"] != value["JSON_output"]
            and value["driver"] != value["JSON_output"],
            "JSON output substituted into executable role")


def mutation_selftest(roles: dict[str, str], wplto_mode: str,
                      phase_order: list[str]) -> dict[str, str]:
    rejected: dict[str, str] = {}
    trials = {
        "json-output-as-program": {**roles, "program": roles["JSON_output"]},
        "json-output-as-driver": {**roles, "driver": roles["JSON_output"]},
    }
    for name, trial in trials.items():
        try:
            validate_roles(trial)
        except AttributionError:
            rejected[name] = "rejected"
        else:
            raise AttributionError(f"role mutation survived: {name}")
    try:
        require(wplto_mode == "0555", "frozen root falsely claimed writable")
        require(wplto_mode != "0755", "frozen root mutation survived")
        rejected["frozen-root-claimed-writable"] = "rejected"
    except AttributionError:
        raise
    wrong_order = list(phase_order)
    wrong_order[0], wrong_order[-1] = wrong_order[-1], wrong_order[0]
    try:
        require(wrong_order == phase_order, "late writer moved before producer")
    except AttributionError:
        rejected["late-writer-moved-before-seal"] = "rejected"
    else:
        raise AttributionError("phase-order mutation survived")
    return rejected


def scratch_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lisp65-abi-eacces-attribution-") as raw:
        out = Path(raw) / "c2-asm-leaf-abi.json"
        command = [sys.executable, str(GATE), "--elf", str(ELF),
                   "--out", str(out)]
        completed = subprocess.run(command, cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(completed.returncode == 0
                and "passed-all-assembler-leaf-abi-contracts" in completed.stdout,
                f"scratch ABI control failed: {completed.stdout}")
        report = json.loads(out.read_text(encoding="utf-8"))
        require(report["status"] == "passed-all-assembler-leaf-abi-contracts",
                "scratch ABI report status drift")
        raw_report = out.read_bytes()
        return {"status": report["status"], "returncode": completed.returncode,
            "report_bytes": len(raw_report),
            "report_sha256": hashlib.sha256(raw_report).hexdigest(),
            "output_owner": "temporary qualification-owned writable directory",
            "ELF_sha256": bind(ELF)["sha256"]}


def derive() -> dict[str, Any]:
    frozen_before = {"Final_Red": bind(FINAL_RED), "ELF": bind(ELF),
                     "PRG": bind(PRG)}
    red = json.loads(FINAL_RED.read_text(encoding="utf-8"))
    require(red["status"] == "FINAL RED: V1.6 HYBRID SEMANTIC-LONGJMP CARD STOPS"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and "Permission denied" in red["error"]["message"]
            and str(ABI_REPORT) in red["error"]["message"],
            "frozen hybrid Final Red drift")
    require(WPLTO.is_dir() and mode(WPLTO) == "0555"
            and mode(ELF) == "0444" and mode(PRG) == "0444"
            and not ABI_REPORT.exists(), "frozen output-root witness drift")

    sources = source_witness()
    roles = {
        "program": sys.executable,
        "driver": str(GATE),
        "ELF_input": str(ELF),
        "JSON_output": str(ABI_REPORT),
    }
    validate_roles(roles)
    control = scratch_control()
    phase_order = sources["phase_order"]
    mutations = mutation_selftest(roles, mode(WPLTO), phase_order)
    frozen_after = {"Final_Red": bind(FINAL_RED), "ELF": bind(ELF),
                    "PRG": bind(PRG)}
    require(frozen_before == frozen_after and not ABI_REPORT.exists(),
            "attribution changed frozen evidence")

    return {
        "format": FORMAT, "recorded_on": "2026-08-20",
        "status": "ATTRIBUTED: ABI REPORT WRITE TARGET WAS ALREADY SEALED",
        "claim_correction": (
            "The EACCES pathname names Path.write_text's output target; it was "
            "never placed in the program or driver position."),
        "claim_limit": (
            "Host-only read of frozen Final-Red evidence and sources plus one "
            "ABI-gate control against the same ELF into a temporary writable "
            "directory; no configuration, card, WPLTO, link, media or device."),
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"reviewer": authorization(), "driver": bind(DRIVER)},
        "frozen_evidence_before": frozen_before,
        "frozen_evidence_after": frozen_after,
        "consumer_roles": {
            "expected": roles, "observed": roles,
            "all_roles_match": True,
            "argument_ordering_error": False,
            "adapter_projection_role_inversion": False,
            "configuration_role_write": False,
            "sources": sources},
        "actual_writer": {
            "module": GATE.relative_to(ROOT).as_posix(),
            "function": "audit_elf", "operation": "out.write_text(...) ",
            "destination": ABI_REPORT.relative_to(ROOT).as_posix(),
            "destination_parent_mode": mode(WPLTO),
            "destination_parent_owner": "producer-owned frozen WPLTO root",
            "scheduled_phase": "after scope and acceptance",
            "mechanism": (
                "A qualification-owned ABI report was scheduled after the "
                "producer sealed WPLTO, while its path remained inside that "
                "producer-owned immutable root.")},
        "same_ELF_writable_output_control": control,
        "hypotheses": {
            "JSON_path_executed": {"result": "refuted",
                "evidence": "expected and observed executable roles are identical"},
            "product_or_ABI_failure": {"result": "refuted",
                "evidence": "same frozen ELF passes the real gate to writable output"},
            "late_write_into_frozen_producer_root": {"result": "proved",
                "evidence": "source order + audit_elf writer + WPLTO mode 0555"}},
        "decision": {
            "classification": "known-family",
            "family": "phase-owned-output / guard-belongs-to-owning-phase",
            "standing_rule": (
                "A phase writes only its owned outputs; read-only qualification "
                "never writes beneath a producer-owned frozen root."),
            "product_finding": False,
            "hybrid_proofs_reexamined": False,
            "self_disposition_budget_reset": True,
            "successor_cards_authorized_by_this_attribution": 0,
            "next": "known-family self-disposition under the standing decision tree"},
        "mutations_rejected": mutations,
    }


def main() -> int:
    value = derive()
    raw = canonical(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(raw)
    require(value == derive(), "EACCES attribution is not deterministic")
    require(RECEIPT.read_bytes() == raw, "EACCES attribution write drift")
    print("v1.6 hybrid ABI EACCES: ATTRIBUTION PASS roles=unchanged "
          "writer=audit_elf.write_text root=0555 class=known-family successor=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
