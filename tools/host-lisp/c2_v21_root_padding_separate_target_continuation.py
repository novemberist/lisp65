#!/usr/bin/env python3
"""Materialize and link once from the immutable root-padding seed."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_root_padding_bounded_producer_continuation as PREVIOUS  # noqa: E402
import c2_v112_ownership_opt_in_historical_unbind_20260817 as V112  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SOURCE_WPLTO = PREVIOUS.WPLTO
SEED = PREVIOUS.SEED
PROFILE = PREVIOUS.PROFILE
SOURCE_MANIFEST = (
    PREVIOUS.BUILD / "static-plane/narrow-static/product/substitution-artifacts.json")
TARGET = ROOT / "build/c2.3/v2.1-root-padding-separate-target-continuation"
WPLTO = TARGET / "wplto"
FINAL = WPLTO / "lisp65-c2-substitution-linked.prg"
PREFLIGHT_ROOT = ROOT / "build/c2.3/v2.1-root-padding-separate-target-preflight"
PREFLIGHT = PREFLIGHT_ROOT / "preflight.json"
LINK_RECEIPT = TARGET / "final-link.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-continuation-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-continuation-final-red.json")
AUTHORIZATION = "bdc22229"
FORMAT = "lisp65-c2.3-v2.1-root-padding-separate-target-continuation-v1"


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


def git_bind(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, value = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("separate continuation target authorized",
                  "seed stays physically read-only",
                  "consumed by reference", "created by the continuation alone",
                  "materialization + final link", "same acceptance authorities"):
        require(token in text, f"separate-target authority absent: {token}")
    return value


def family(base: Path) -> list[Path]:
    return [base, Path(str(base) + ".elf"), Path(str(base) + ".map"),
            Path(str(base) + ".lto.o")]


def bound_family(base: Path) -> dict[str, dict[str, Any]]:
    return {path.name: bind(path) for path in family(base)}


def immutable_tree() -> dict[str, Any]:
    require(SOURCE_WPLTO.is_dir() and not SOURCE_WPLTO.is_symlink(),
            "immutable source WPLTO absent")
    mode = stat.S_IMODE(SOURCE_WPLTO.stat().st_mode)
    require(mode == 0o555, "source WPLTO is not physically read-only")
    rows: list[bytes] = []
    files = 0
    total = 0
    for path in sorted(SOURCE_WPLTO.rglob("*")):
        require(not path.is_symlink(), f"immutable tree contains symlink: {path}")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        relative = path.relative_to(SOURCE_WPLTO).as_posix()
        rows.append(relative.encode() + b"\0" + str(len(raw)).encode() + b"\0"
                    + hashlib.sha256(raw).hexdigest().encode() + b"\n")
        files += 1
        total += len(raw)
    require(files > 100, "immutable source WPLTO tree unexpectedly small")
    return {"path": SOURCE_WPLTO.relative_to(ROOT).as_posix(), "mode": "0555",
            "regular_files": files, "bytes": total,
            "closure_sha256": hashlib.sha256(b"".join(rows)).hexdigest()}


def profile_inputs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in PROFILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("input_sha256="):
            continue
        path_raw, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
        path = ROOT / path_raw
        current = bind(path)
        require(current["sha256"] == digest,
                f"bound compiler input drift: {path_raw}")
        rows.append(current)
    require(len(rows) == 66 and len({row["path"] for row in rows}) == 66,
            "bound compiler input closure cardinality drift")
    return rows


def seed_family() -> dict[str, dict[str, Any]]:
    current = bound_family(SEED)
    red = load(PREVIOUS.FINAL_RED)
    require(current == red["seed"], "immutable seed family drift")
    return current


def reference_inputs() -> dict[str, Any]:
    profile = bind(PROFILE)
    linker = bind(SOURCE_WPLTO / "c2-substitution.ld")
    linker_rows = [bind(path) for path in sorted(
        (SOURCE_WPLTO / "full-map-linker").iterdir()) if path.is_file()]
    require(hashlib.sha256((SOURCE_WPLTO / "c2-substitution.ld").read_bytes()
                           ).hexdigest() == next(
        line.split("=", 1)[1] for line in PROFILE.read_text().splitlines()
        if line.startswith("linker_sha256=")), "profile/linker identity drift")
    return {
        "seed": seed_family(), "profile": profile, "linker": linker,
        "full_map_linker": linker_rows,
        "fixed_headers": [bind(SOURCE_WPLTO / name) for name in (
            "stage-config.h", "runtime-overlay.prepare.h",
            "error-text-table.h", "c2-kernal-window.generated.h")],
        "product_identity": bind(SOURCE_MANIFEST),
        "compiler_inputs": profile_inputs(),
        "candidate_static_header": bind(
            ROOT / "build/c2.3/v2.0-ownership-recharter-inputs/"
                   "c2_lite_static_plane.h"),
    }


def validate_preflight(value: dict[str, Any]) -> None:
    lock = value["execution_lock"]
    require(
        value.get("format") == FORMAT
        and value.get("status") ==
            "PASS: immutable seed referenced; separate target armed"
        and value["source_evidence"]["mode"] == "0555"
        and value["target"]["preexisted"] is False
        and value["target"]["owner"] == "continuation-producer-only"
        and value["seed_consumption"] == "direct-read-only-reference"
        and value["write_lease_on_source_evidence"] is False
        and len(value["inputs"]["seed"]) == 4
        and len(value["inputs"]["compiler_inputs"]) == 66
        and lock == {"new_WPLTO_card_runs": 0, "materializations": 0,
                     "final_product_links": 0, "completion_runs": 0,
                     "media_builds": 0, "device_contacts": 0},
        "separate-target continuation preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "precreate-target": lambda x: x["target"].update(preexisted=True),
        "grant-source-write-lease": lambda x: x.update(
            write_lease_on_source_evidence=True),
        "copy-seed": lambda x: x.update(seed_consumption="copied-into-target"),
        "drop-input": lambda x: x["inputs"]["compiler_inputs"].pop(),
        "invent-card": lambda x: x["execution_lock"].update(
            new_WPLTO_card_runs=1),
        "invent-link": lambda x: x["execution_lock"].update(
            final_product_links=1),
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
    require(rejected == list(cases), "separate-target preflight mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    require(not TARGET.exists(), "continuation target pre-exists")
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "separate-target continuation already terminated")
    inputs = reference_inputs()
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17",
        "status": "PASS: immutable seed referenced; separate target armed",
        "authority": {"owner": authorization(),
            "predecessor_Final_Red": bind(PREVIOUS.FINAL_RED),
            "red_attribution": bind(ARCH /
                "c2.3-v2.1-root-padding-bounded-continuation-red-attribution.json"),
            "v1.12_historical_unbind": bind(V112.RECEIPT),
            "driver": bind(Path(__file__))},
        "source_evidence": immutable_tree(), "inputs": inputs,
        "seed_consumption": "direct-read-only-reference",
        "write_lease_on_source_evidence": False,
        "target": {"path": TARGET.relative_to(ROOT).as_posix(),
            "preexisted": False, "owner": "continuation-producer-only",
            "creation_operation": "exactly-once producer mkdir"},
        "execution_lock": {"new_WPLTO_card_runs": 0, "materializations": 0,
            "final_product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Preflight only. Immutable evidence is read, never leased or changed; "
            "the separate target does not yet exist."),
    }
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    return value


def record_preflight() -> None:
    require(not PREFLIGHT_ROOT.exists(), "separate-target preflight already exists")
    value = preflight_value()
    PREFLIGHT_ROOT.mkdir()
    PREFLIGHT.write_bytes(canonical(value))
    print("separate-target continuation: PREFLIGHT PASS seed=4 inputs=66 target=absent")


def consume_preflight() -> dict[str, Any]:
    value = load(PREFLIGHT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "separate-target preflight mutation receipt drift")
    require(value["authority"]["driver"] == bind(Path(__file__)),
            "separate-target driver changed after preflight")
    return value


def link_reference(path: Path, source: Path) -> None:
    require(source.exists() and not path.exists(), f"input reference collision: {path}")
    path.symlink_to(source.relative_to(path.parent), target_is_directory=source.is_dir())
    require(path.resolve() == source.resolve(), f"input reference misbound: {path}")


def materialize(header: Path) -> None:
    PRODUCT.tool(
        "resident_island.py", "materialize", "--elf", str(SEED) + ".elf",
        "--nm", str(PRODUCT.TOOLCHAIN / "llvm-nm"),
        "--objcopy", str(PRODUCT.TOOLCHAIN / "llvm-objcopy"),
        "--abi-contract", str(PROFILE), "--header", str(header))


def exact_source_list(rows: list[dict[str, Any]]) -> Callable[..., list[str]]:
    paths = [str(ROOT / row["path"]) for row in rows]

    def selected(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        require(tuple(extra_definitions) == PRODUCT.CONVERGENCE_DEFINES,
                "final link requested a compiler-input scope other than the seed")
        return list(paths)

    return selected


def run_link() -> None:
    preflight = consume_preflight()
    require(not TARGET.exists(), "producer-owned continuation target pre-exists")
    source_before = immutable_tree()
    inputs_before = reference_inputs()
    TARGET.mkdir()
    WPLTO.mkdir()
    link_reference(WPLTO / "c2-substitution.ld",
                   SOURCE_WPLTO / "c2-substitution.ld")
    link_reference(WPLTO / "full-map-linker",
                   SOURCE_WPLTO / "full-map-linker")
    header = WPLTO / "resident-island.h"
    materialize(header)
    witness = bind(PREVIOUS.STATE / "materialization-probe/resident-island-a.h")
    require(bind(header)["sha256"] == witness["sha256"],
            "separate-target materialization differs from bound witnesses")

    old_config, _paths = PREVIOUS.configure_candidate()
    old_source_list = PRODUCT.source_list
    old_manifest = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    try:
        PRODUCT.source_list = exact_source_list(inputs_before["compiler_inputs"])
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = SOURCE_MANIFEST
        artifacts = load(SOURCE_MANIFEST)
        PRODUCT.compile_link(
            WPLTO, FINAL.name,
            [SOURCE_WPLTO / "stage-config.h",
             SOURCE_WPLTO / "runtime-overlay.prepare.h", header,
             SOURCE_WPLTO / "error-text-table.h",
             SOURCE_WPLTO / "c2-kernal-window.generated.h"],
            artifacts, probe_definitions=PRODUCT.CONVERGENCE_DEFINES)
    finally:
        PRODUCT.source_list = old_source_list
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old_config)

    source_after = immutable_tree()
    inputs_after = reference_inputs()
    require(source_after == source_before, "immutable source evidence changed")
    require(inputs_after == inputs_before, "referenced input closure changed")
    require(not any((WPLTO / path.name).exists() for path in family(SEED)),
            "immutable seed was copied into continuation target")
    finals = bound_family(FINAL)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17",
        "status": "PASS: separate target materialized and final product linked",
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(Path(__file__))},
        "source_evidence_before": source_before,
        "source_evidence_after": source_after,
        "inputs_before": inputs_before, "inputs_after": inputs_after,
        "seed_consumption": {"mode": "direct-read-only-reference",
            "copied_into_target": False, "family": seed_family()},
        "target_ownership": {"preexisted": False,
            "created_by": "continuation-producer", "single_owner": True},
        "materialization": {"runs": 1, "header": bind(header),
            "equals_prior_determinism_witness": True, "witness": witness},
        "final_artifacts": finals,
        "compiler_input_consumption": bind(
            Path(str(FINAL) + ".compiler-input-consumption.json")),
        "candidate_derived_inventory": bind(
            WPLTO / f"final-section-inventory-{FINAL.name}.json"),
        "LTO_metadata": bind(
            WPLTO / f"lto-partition-metadata-{FINAL.name}.json"),
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "materializations": 1, "final_product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "next": "same acceptance authorities over the four final artifacts",
        "claim_limit": (
            "Materialization and final link only. Acceptance, Completion, media "
            "and device actions have not run."),
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    print("separate-target continuation: LINK PASS seed=reference final=4 WPLTO=0 link=1")


def record_final_red(error: Exception) -> None:
    if FINAL_RED.exists() or RECEIPT.exists():
        return
    finals = {path.name: bind(path) for path in family(FINAL)
              if path.is_file() and not path.is_symlink()}
    value = {
        "format": "lisp65-c2.3-v2.1-separate-target-continuation-red-v1",
        "recorded_on": "2026-08-17",
        "status": "FINAL RED: SEPARATE-TARGET CONTINUATION RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT) if PREFLIGHT.exists() else None,
            "driver": bind(Path(__file__))},
        "source_evidence": immutable_tree(), "seed": seed_family(),
        "final_artifacts": finals, "retry_authorized": False,
        "owner_disposition_required": True,
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "final_product_links": 1 if finals else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Terminal separate-target continuation Red; no retry.",
    }
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    value = load(RECEIPT if RECEIPT.exists() else LINK_RECEIPT)
    require(value["final_artifacts"] == bound_family(FINAL),
            "separate-target continuation artifact drift")
    print("separate-target continuation: CHECK PASS final=4 WPLTO=0 link=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "link", "check"))
    action = parser.parse_args().action
    try:
        {"preflight": record_preflight, "link": run_link,
         "check": check}[action]()
    except Exception as error:
        if action == "link":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"separate-target Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"separate-target continuation: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
