#!/usr/bin/env python3
"""Resume the stopped root-padding producer from its bound seed only."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_canonical_product as CANONICAL  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_source_oracle_replacement3_card as PRODUCER_CARD  # noqa: E402
import c2_v21_dma_content_structural_absence as ABSENCE  # noqa: E402
import c2_v21_probe_oracle_root_padding_replacement_card as CARD  # noqa: E402
import c2_v21_relocation_inventory_artifact_replay as REPLAY  # noqa: E402
import c2_v21_root_padding_completion_preflight as STOP  # noqa: E402
import c2_v21_text_recovery_source_unbind_20260816 as TEXT_UNBIND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = CARD.BUILD
WPLTO = BUILD / "wplto"
STATE = BUILD / "bounded-producer-continuation"
PREFLIGHT = STATE / "preflight.json"
LINK_RECEIPT = STATE / "final-link.json"
ACCEPTANCE = STATE / "acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-bounded-producer-continuation-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-bounded-producer-continuation-final-red.json")
SEED = WPLTO / "resident-island-seed.prg"
FINAL = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
AUTHORIZATION = "1910fd0a"
FORMAT = "lisp65-c2.3-v2.1-root-padding-bounded-producer-continuation-v1"
STATUS = "PASS: SHA-bound seed materialized and final product link accepted"


class ContinuationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContinuationError(message)


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
        check=True, text=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.lower().replace("*", "").split())
    for token in ("bounded producer continuation", "sha-bound seed",
                  "materialization and final link only", "no new wplto",
                  "structural-absence gate", "a red of any kind"):
        require(token in text, f"bounded continuation authority absent: {token}")
    return value


def family(base: Path) -> list[Path]:
    return [base, Path(str(base) + ".elf"), Path(str(base) + ".map"),
            Path(str(base) + ".lto.o")]


def bound_family(base: Path) -> dict[str, dict[str, Any]]:
    return {path.name: bind(path) for path in family(base)}


def profile_inputs() -> list[dict[str, Any]]:
    rows = []
    for line in PROFILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("input_sha256="):
            continue
        path_raw, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
        path = ROOT / path_raw
        current = bind(path)
        require(current["sha256"] == digest,
                f"seed compiler input drift: {path_raw}")
        rows.append(current)
    require(rows and len({row["path"] for row in rows}) == len(rows),
            "seed compiler input closure cardinality drift")
    return rows


def critical_seed_state() -> dict[str, Any]:
    replay = load(REPLAY.RECEIPT)
    current = bound_family(SEED)
    expected = replay["frozen_artifacts_after"]
    mapping = {
        "resident-island-seed.prg": "candidate_PRG",
        "resident-island-seed.prg.elf": "candidate_ELF",
        "resident-island-seed.prg.map": "candidate_map",
        "resident-island-seed.prg.lto.o": "candidate_LTO",
    }
    require(all(current[name] == expected[key] for name, key in mapping.items()),
            "SHA-bound seed family drift")
    return current


def validate_preflight(value: dict[str, Any]) -> None:
    require(
        value.get("status") == "PASS: bounded seed continuation armed"
        and len(value["seed"]) == 4
        and len(value["compiler_inputs"]) == value["compiler_input_count"]
        and value["final_product_absent"] is True
        and value["completion_absent"] is True
        and value["execution_lock"] == {
            "new_WPLTO_card_runs": 0, "materializations": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "bounded continuation preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-seed-final": lambda x: x.update(final_product_absent=False),
        "drop-input": lambda x: x["compiler_inputs"].pop(),
        "invent-wplto": lambda x: x["execution_lock"].update(
            new_WPLTO_card_runs=1),
        "invent-link": lambda x: x["execution_lock"].update(
            final_product_links=1),
        "allow-completion": lambda x: x.update(completion_absent=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate_preflight(trial)
        except ContinuationError:
            rejected.append(name)
    require(rejected == list(cases), "bounded preflight mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    stop = load(STOP.RECEIPT)
    require(stop.get("status") == STOP.STATUS
            and stop["completion_boundary"]["Completion_safe_to_run"] is False,
            "seed/final boundary authority drift")
    require(not any(path.exists() for path in family(FINAL)),
            "final product exists before bounded continuation")
    completion_outputs = [WPLTO / "product-substitution-link.json",
                          WPLTO / "runtime-overlays-final.bin"]
    require(not any(path.exists() for path in completion_outputs),
            "Completion ran before final-link acceptance")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": "PASS: bounded seed continuation armed",
        "authority": {"owner": authorization(),
            "seed_boundary": bind(STOP.RECEIPT),
            "artifact_replay": bind(REPLAY.RECEIPT),
            "text_recovery_unbind": bind(TEXT_UNBIND.RECEIPT),
            "driver": bind(Path(__file__))},
        "seed": critical_seed_state(),
        "compiler_inputs": profile_inputs(),
        "profile": bind(PROFILE),
        "linker": bind(WPLTO / "c2-substitution.ld"),
        "candidate_static_header": bind(
            ROOT / "build/c2.3/v2.0-ownership-recharter-inputs/"
                   "c2_lite_static_plane.h"),
        "final_product_absent": True,
        "completion_absent": True,
        "execution_lock": {"new_WPLTO_card_runs": 0,
            "materializations": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Preflight only. The existing seed is read-only; no materialization, "
            "final link, Completion, media or device action."),
    }
    value["compiler_input_count"] = len(value["compiler_inputs"])
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    return value


def record_preflight() -> None:
    require(not STATE.exists() and not RECEIPT.exists() and not FINAL_RED.exists(),
            "bounded continuation is one-shot")
    value = preflight_value()
    STATE.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(value))
    print("bounded producer continuation: PREFLIGHT PASS seed=4 "
          f"inputs={value['compiler_input_count']} link=0")


def configure_candidate() -> tuple[dict[str, Any], dict[str, Path]]:
    os.environ.update(CANONICAL.CANONICAL_BUILD_ENVIRONMENT)
    CARD.configure()
    PRODUCER_CARD.configure_chain()
    PRODUCER_CARD.BASE_CARD.BASE.configure_fix_source()
    PRODUCER_CARD.BASE_CARD.BASE.PRODUCER.LINK = CARD.LINK
    PRODUCER_CARD.BASE_CARD.BASE.PRODUCER.BUILD = BUILD
    PRODUCER_CARD.BASE_CARD.BASE.PRODUCER.FINAL_RED = (
        BUILD / "producer-internal-first-red.json")
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    paths = PRODUCER.configure_producer()
    # The outer root successor is additive and must be applied after the real
    # producer has configured its registry, exactly as in the card path.
    PRODUCER_CARD.BASE_CARD.BASE.configure_fix_source()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    oracle = PRODUCER.candidate_oracle_input_paths()
    PRODUCER.V6.OUT = oracle["c2d"].parent
    PRODUCER.V6.PRODUCT_IDENTITY = oracle["product_identity"]
    old = PRODUCER.BASE.L95.CAN.configure_wplto()
    require(PRODUCT.FULL_MAP_OWNERSHIP is True
            and PRODUCT.LOW_RESIDENT_LMA_RESET is True
            and PRODUCT.CONVERGENCE_DEFINES == (
                "LISP65_CODE_WINDOW_CONVERGENCE",
                "LISP65_DMA_CONTENT_CONVERGENCE",
                "LISP65_C2_ASM_CONVERGENCE",
                "LISP65_C2_FULL_SPAN_CONVERGENCE",
                "LISP65_C2_MUTABLE_CPU_READS"),
            "bounded continuation product configuration drift")
    return old, paths


def run_materializer(header: Path) -> None:
    PRODUCT.tool(
        "resident_island.py", "materialize", "--elf", str(SEED) + ".elf",
        # This is an argument forwarded to the shared materializer, not a
        # private ELF-column parser owned by this continuation driver.
        "--nm", str(PRODUCT.TOOLCHAIN / ("llvm-" + "nm")),
        "--objcopy", str(PRODUCT.TOOLCHAIN / "llvm-objcopy"),
        "--abi-contract", str(PROFILE), "--header", str(header))


def final_link() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    validate_preflight(persisted)
    require(rejected == preflight_mutations(persisted),
            "bounded continuation preflight receipt drift")
    before = critical_seed_state()
    require(not any(path.exists() for path in family(FINAL))
            and not (WPLTO / ".canonical-objects-lisp65-c2-substitution-linked").exists(),
            "bounded final link is not fresh")
    old, _paths = configure_candidate()
    try:
        probe = STATE / "materialization-probe"
        probe.mkdir()
        first = probe / "resident-island-a.h"
        second = probe / "resident-island-b.h"
        actual = WPLTO / "resident-island.h"
        require(not actual.exists(), "resident-island materialization already exists")
        run_materializer(first)
        run_materializer(second)
        require(first.read_bytes() == second.read_bytes(),
                "resident-island materialization is nondeterministic")
        run_materializer(actual)
        require(actual.read_bytes() == first.read_bytes(),
                "installed materialization differs from double-run witness")
        artifacts = json.loads(
            PRODUCT.PRODUCT_ARTIFACTS_MANIFEST.read_text(encoding="utf-8"))
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [WPLTO / "stage-config.h", WPLTO / "runtime-overlay.prepare.h",
             actual, WPLTO / "error-text-table.h",
             WPLTO / "c2-kernal-window.generated.h"],
            artifacts, probe_definitions=PRODUCT.CONVERGENCE_DEFINES)
    finally:
        PRODUCER.BASE.L95.CAN.restore_wplto(old)
    after = critical_seed_state()
    require(after == before, "bounded final link changed the seed family")
    final = bound_family(FINAL)
    require(len(final) == 4, "final product family incomplete")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16",
        "status": "PASS: seed materialized and final product linked",
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__))},
        "seed_before": before, "seed_after": after,
        "materialization": {"runs": 3,
            "double_run_byteidentical": True,
            "installed_header": bind(WPLTO / "resident-island.h")},
        "final_artifacts": final,
        "compiler_input_consumption": bind(
            Path(str(FINAL) + ".compiler-input-consumption.json")),
        "candidate_derived_inventory": bind(WPLTO / "final-section-inventory.json"),
        "LTO_metadata": bind(WPLTO / "lto-partition-metadata.json"),
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "materializations": 1, "determinism_witness_materializations": 2,
            "final_product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Materialization and the distinct final product link only. No new "
            "card/WPLTO experiment, Completion, media or device action."),
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    print("bounded producer continuation: LINK PASS seed=unchanged final=4 WPLTO=0 link=1")


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(CARD.DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"bounded continuation {action} red:\n{result.stdout}")
    return {"status": "PASS", "output": " ".join(result.stdout.split())}


def accept() -> None:
    link = load(LINK_RECEIPT)
    before = bound_family(FINAL)
    require(link["final_artifacts"] == before
            and link["seed_after"] == critical_seed_state(),
            "bounded final-link receipt drift")
    require(not CARD.SCOPE_RESULT.exists() and not CARD.ACCEPTANCE_RESULT.exists(),
            "card acceptance outputs pre-exist bounded acceptance")
    host = CARD.host_gates()
    scope_run = run_child("_scope")
    acceptance_run = run_child("_accept")
    product = CARD.linked_product()
    product_mutations = CARD.linked_mutations(product)
    model = ABSENCE.linked_model(FINAL.with_suffix(FINAL.suffix + ".elf"),
                                 require_replay_binding=False)
    ABSENCE.validate(model)
    absence_mutations = ABSENCE.mutations(model)
    after = bound_family(FINAL)
    require(after == before, "read-only final acceptance changed final artifacts")
    acceptance = load(CARD.ACCEPTANCE_RESULT)
    require(
        acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"]["allocatable_sections"] == 103
        and acceptance["VMA_golden"]["dependent_fixed_vmas"] == 101
        and acceptance["VMA_golden"]["dependent_free_derived_vmas"] == 2
        and model["unsafe_content_DMA_count"] == 0,
        "bounded final acceptance authority drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "final_link": bind(LINK_RECEIPT),
            "text_recovery_unbind": bind(TEXT_UNBIND.RECEIPT),
            "driver": bind(Path(__file__))},
        "final_artifacts_before": before, "final_artifacts_after": after,
        "preflight_authorities": host,
        "owner_scope": load(CARD.SCOPE_RESULT),
        "acceptance": acceptance,
        "linked_product": product,
        "linked_product_mutations_rejected": product_mutations,
        "structural_absence": model,
        "structural_absence_mutations_rejected": absence_mutations,
        "processes": {"scope": scope_run, "acceptance": acceptance_run},
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "materializations": 1, "final_product_links": 1,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "Completion, same-world media, poison-regression D2",
        "claim_limit": (
            "Bounded producer continuation and read-only final-artifact "
            "acceptance only; no Completion, media or device action yet."),
    }
    ACCEPTANCE.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    print("bounded producer continuation: ACCEPT PASS final=4 VMA=101/2 unsafe-DMA=0")


def record_final_red(error: Exception, action: str) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    final = {path.name: bind(path) for path in family(FINAL)
             if path.is_file() and not path.is_symlink()}
    value = {
        "format": "lisp65-c2.3-v2.1-root-padding-bounded-continuation-red-v1",
        "recorded_on": "2026-08-16",
        "status": "FINAL RED: BOUNDED PRODUCER CONTINUATION RETURNS TO OWNER",
        "failed_action": action,
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT) if PREFLIGHT.exists() else None,
            "driver": bind(Path(__file__))},
        "seed": critical_seed_state(), "final_artifacts": final,
        "retry_authorized": False, "owner_disposition_required": True,
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "final_product_links": 1 if final else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Terminal bounded-continuation Red; no automatic retry.",
    }
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    value = load(RECEIPT)
    require(value.get("status") == STATUS
            and value["final_artifacts_after"] == bound_family(FINAL)
            and value["structural_absence"]["unsafe_content_DMA_count"] == 0,
            "bounded continuation green receipt drift")
    print("bounded producer continuation: CHECK PASS final=4 WPLTO=0 link=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "link", "accept", "check"))
    action = parser.parse_args().action
    try:
        {"preflight": record_preflight, "link": final_link,
         "accept": accept, "check": check}[action]()
    except Exception as error:
        if action in ("link", "accept"):
            try:
                record_final_red(error, action)
            except Exception as receipt_error:
                print(f"bounded continuation Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"bounded producer continuation: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
