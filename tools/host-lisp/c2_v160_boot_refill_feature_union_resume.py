#!/usr/bin/env python3
"""Resume boot-refill qualification read-only with a derived feature union."""

from __future__ import annotations

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

import c2_v160_boot_refill_dma_closure as CLOSURE  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as PROJECTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-card"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
GENERATED = BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-preflight/preflight.json"
PRODUCER = BUILD / "producer-result.json"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
FINAL_RED = ARCH / "c2.3-v1.6-boot-refill-generator-template-card-final-red.json"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-feature-union-resume.json"
AUTHORIZATION = "84924e89"
FORMAT = "lisp65-c2-v160-boot-refill-feature-union-resume-v1"
STATUS = "PASS: BOOT REFILL DMA FIX CHAIN CLOSED"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


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
    for token in ("feature set derives from the candidate",
                  "active registry union", "read-only qualification resume",
                  "no wplto, no relink, no card"):
        require(token in text, f"feature-union resume authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    error = json.loads(value["error"]["message"].split(": ", 1)[1])
    require(value["status"] ==
                "FINAL RED: V1.6 BOOT REFILL GENERATOR CARD STOPS"
            and error["comparison"] == "effective-features"
            and len(error["expected"]) == 9 and len(error["observed"]) == 10
            and "LISP65_C2_REFILL_BOUNDARY_WITNESS" in error["observed"]
            and "LISP65_C2_REFILL_BOUNDARY_WITNESS" not in error["expected"],
            "feature-set Final Red drift")
    return {"binding": bind(FINAL_RED), "drift": error}


def active_union() -> dict[str, Any]:
    preflight = load(PREFLIGHT)
    profile, previous = PROJECTION.bound_features()
    fold = preflight["real_single_link_feature_fold"]
    incoming = tuple(fold["incoming_definitions"])
    wrapper = tuple(item for item in incoming
                    if item not in profile and item not in previous)
    selected = preflight["witness_registration"]["selected"]
    registry = (selected["feature"],) if selected["selected"] else ()
    expected = tuple(dict.fromkeys((*previous, *wrapper, *registry)))
    observed = tuple(final_red()["drift"]["observed"])
    value = {"authority": "active-candidate-registry-union",
        "previous_candidate_features": list(previous),
        "configured_wrapper_features": list(wrapper),
        "active_card_registry_features": list(registry),
        "expected_members": list(expected), "observed_members": list(observed)}
    validate_union(value)
    return value


def validate_union(value: dict[str, Any]) -> None:
    expected = value.get("expected_members", [])
    observed = value.get("observed_members", [])
    require(value.get("authority") == "active-candidate-registry-union"
            and len(expected) == len(set(expected))
            and len(observed) == len(set(observed))
            and set(expected) == set(observed)
            and "LISP65_C2_REFILL_BOUNDARY_WITNESS" in expected,
            "candidate-derived feature union drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "omit-active-witness": lambda x: x["observed_members"].remove(
            "LISP65_C2_REFILL_BOUNDARY_WITNESS"),
        "restore-exact-nine-pin": lambda x: x.update(
            authority="stored-exact-nine-feature-list"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_union(trial)
        except ResumeError:
            rejected.append(name)
    require(rejected == list(cases), "feature-union mutation survived")
    return rejected


def qualification() -> dict[str, Any]:
    pair_before = {"ELF": bind(ELF), "PRG": bind(PRG)}
    for path in (PRODUCER, SCOPE, ACCEPTANCE):
        require(load(path)["status"] == "PASS",
                f"persisted qualification tail is not green: {path.name}")
    emitted = CLOSURE.generated_source_gate(GENERATED)
    linked = CLOSURE.linked_read_model(ELF)
    CLOSURE.validate_final(linked)
    union = active_union()
    pair_after = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(pair_after == pair_before, "read-only resume changed frozen pair")
    return {"format": FORMAT, "recorded_on": "2026-08-23",
        "status": STATUS, "authority": authority(), "Final_Red": final_red(),
        "frozen_pair_before": pair_before, "frozen_pair_after": pair_after,
        "feature_union": union, "mutations_rejected": mutations(union),
        "emitted_candidate_gate": emitted, "final_ELF_gate": linked,
        "qualification_tail": {path.name: bind(path)
            for path in (PRODUCER, SCOPE, ACCEPTANCE)},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "artifact-only media, then seam confirmation contact"}


def check(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["execution_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0}
            and value["final_ELF_gate"]["unsafe_content_DMA_count"] == 0
            and value["final_ELF_gate"]["product_entry"]["MAP_CPU_edges"] >= 1
            and value["mutations_rejected"] == [
                "omit-active-witness", "restore-exact-nine-pin"],
            "feature-union resume receipt drift")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "resume":
        require(not RECEIPT.exists(), "feature-union resume is one-shot")
        value = qualification(); check(value); RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        value = load(RECEIPT); check(value)
    else:
        raise ResumeError("usage: resume|check")
    print("boot-refill feature union: PASS unsafe=0 pair=SHA-identical")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResumeError, OSError, KeyError, ValueError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"boot-refill feature union: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
