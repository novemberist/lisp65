#!/usr/bin/env python3
"""Run the one approved replacement Link-107 CPU-transport card."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_map_tuple_fix_card as MAP_FIX  # noqa: E402
import c2_v20_source_oracle_replacement3_card as REAL_PRODUCER  # noqa: E402
import c2_v21_cpu_transport_card as CARD  # noqa: E402
import c2_v21_cpu_transport_preflight as PRE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-cpu-transport-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-cpu-transport-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-cpu-transport-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-replacement-card-final-red.json"
HISTORICAL_RED = ARCH / "c2.3-v2.1-cpu-transport-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v2.1-cpu-transport-card-red-attribution-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9f0ae17a"
LINK = 107
RECORDED_ON = "2026-08-14"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "registry-style configuration is additive and identity-scoped",
            "mutates only by identity/addition",
            "after the real producer configuration",
            "one replacement card"):
        require(token in text, f"replacement authorization token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure() -> None:
    CARD.BUILD = BUILD
    CARD.PREFLIGHT = PREFLIGHT
    CARD.INVOCATION = INVOCATION
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.RECEIPT = BUILD / "unused-first-card-receipt.json"
    CARD.FINAL_RED = BUILD / "unused-first-card-final-red.json"
    CARD.LINK = LINK
    CARD.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return CARD.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def historical_red() -> dict[str, Any]:
    red = load(HISTORICAL_RED)
    attribution = load(ATTRIBUTION)
    require(
        red.get("status") == "FINAL RED: Link-107 returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and attribution.get("root_cause", {}).get("class")
            == "BOUND-SOURCE-OWNER-NOT-CONSUMED-BY-REAL-PRODUCER"
        and attribution.get("attempt_accounting", {}).get("product_ELFs") == 0,
        "replacement predecessor Final Red drift")
    return attribution


def _function_text(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next((row for row in tree.body
                 if isinstance(row, ast.FunctionDef) and row.name == name), None)
    require(node is not None, f"function absent: {name}")
    return ast.unparse(node)


def configuration_source_gate(
        map_source_override: str | None = None,
        producer_source_override: str | None = None) -> dict[str, Any]:
    map_source = (Path(MAP_FIX.__file__).read_text(encoding="utf-8")
                  if map_source_override is None else map_source_override)
    producer_source = (Path(REAL_PRODUCER.__file__).read_text(encoding="utf-8")
                       if producer_source_override is None else producer_source_override)
    configured = _function_text(map_source, "configure_fix_source")
    produce = _function_text(producer_source, "produce_child")
    require(
        "for scope in PRODUCT.SOURCE_OWNER_SCOPES" in configured
        and "scope.get('name') == replacement['name']" in configured
        and "replaced == 1" in configured
        and "PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)" in configured
        and "PRODUCT.source_owner_scope_gate" in configured
        and configured.index("PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)")
            < configured.index("PRODUCT.source_owner_scope_gate")
        and "PRODUCT.SOURCE_OWNER_SCOPES = ({" not in configured,
        "source-owner registry is substitutive or checked before configuration")
    require(
        "BASE_CARD.BASE.configure_fix_source()" in produce
        and "BASE_CARD.BASE.PRODUCER.produce_candidate()" in produce
        and produce.index("BASE_CARD.BASE.configure_fix_source()")
            < produce.index("BASE_CARD.BASE.PRODUCER.produce_candidate()"),
        "real producer does not configure/check source owners before WPLTO")
    return {
        "status": "PASS: additive identity mutation and post-config real-consumer gate",
        "registry_mutation": "replace mapped-far-content-convergence by name; preserve all others",
        "gate_order": "tuple(scopes) -> source_list(selected) -> source_owner_scope_gate",
        "producer_order": "configure_fix_source -> produce_candidate",
    }


def dynamic_configuration_gate() -> dict[str, Any]:
    value = MAP_FIX.configure_fix_source()
    rows = value.get("scopes", [])
    require(
        [(row["name"], row["selected"]) for row in rows] == [
            ("mapped-far-content-convergence", True),
            ("map-cpu-library-read", True)]
        and rows[1]["sources"] == ["src/optional/c2_map_cpu_read.s"],
        "post-configuration real source list omitted the CPU owner")
    return value


def configuration_mutations() -> list[str]:
    source = Path(MAP_FIX.__file__).read_text(encoding="utf-8")
    producer = Path(REAL_PRODUCER.__file__).read_text(encoding="utf-8")
    cases = {
        "restore-wholesale-replacement": (source.replace(
            "    PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)\n",
            "    PRODUCT.SOURCE_OWNER_SCOPES = (replacement,)\n", 1), producer),
        "gate-before-registry-mutation": (source.replace(
            "    PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)\n",
            "    return PRODUCT.source_owner_scope_gate(\n"
            "        PRODUCT.definitions(dummy), selected, PRODUCT.source_list(selected))\n"
            "    PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)\n", 1), producer),
        "produce-before-real-configuration": (source, producer.replace(
            "    BASE_CARD.BASE.configure_fix_source()\n",
            "", 1).replace(
            "    artifacts = BASE_CARD.BASE.PRODUCER.produce_candidate()\n",
            "    artifacts = BASE_CARD.BASE.PRODUCER.produce_candidate()\n"
            "    BASE_CARD.BASE.configure_fix_source()\n", 1)),
    }
    rejected: list[str] = []
    for name, (map_source, producer_source) in cases.items():
        try:
            configuration_source_gate(map_source, producer_source)
        except (ReplacementError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "replacement configuration mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    historical_red()
    return {
        "format": "lisp65-c2.3-v2.1-cpu-transport-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one additive-registry replacement card armed",
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "host_gates": {"source_order": configuration_source_gate(),
                       "post_configuration": dynamic_configuration_gate(),
                       "mutations": configuration_mutations()},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(HISTORICAL_RED),
            "attribution": bind(ATTRIBUTION), "base_preflight": bind(PRE.RECEIPT),
            "contract": bind(PRE.CONTRACT), "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "replacement preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "detach-final-red": lambda x: x["authority"]["predecessor_final_red"].update(
            sha256="0" * 64),
        "accept-preconfiguration-gate": lambda x: x["host_gates"]["source_order"].update(
            gate_order="before mutation"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 CPU transport replacement: PREFLIGHT PASS card=0/1 "
          "scopes=2 mutations=6")


def produce_child() -> int:
    configure()
    result = CARD.produce_child()
    post = dynamic_configuration_gate()
    product = load(PRODUCER_RESULT)
    product["post_configuration_source_owner_gate"] = post
    objects = BUILD / "wplto/.canonical-objects-resident-island-seed"
    names = sorted(path.name for path in objects.iterdir() if path.is_file())
    owner = [name for name in names if "c2_map_cpu_read" in name]
    require(len(owner) == 1, "real producer did not compile exactly one CPU owner")
    product["CPU_reader_owner_objects"] = owner
    PRODUCER_RESULT.write_bytes(canonical(product))
    return result


def scope_child() -> int:
    configure()
    return CARD.scope_child()


def acceptance_child() -> int:
    configure()
    return CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh CPU-transport replacement child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "replacement preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "historical_final_red": bind(HISTORICAL_RED),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement acceptance changed linked artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "replacement process isolation drift")
    require(len(producer["CPU_reader_owner_objects"]) == 1
            and len(producer["post_configuration_source_owner_gate"]["scopes"]) == 2,
            "replacement real-consumer source-owner proof drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-cpu-transport-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: replacement Link-107 CPU transport card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "attribution": bind(ATTRIBUTION), "preflight": bind(PREFLIGHT_RECEIPT),
            "contract": bind(PRE.CONTRACT), "driver": bind(DRIVER)},
        "configuration_contract": configuration_source_gate(),
        "post_configuration_source_owner_gate":
            producer["post_configuration_source_owner_gate"],
        "CPU_reader_owner_objects": producer["CPU_reader_owner_objects"],
        "transport": producer["v21_linked_transport"],
        "workload": load(PRE.RECEIPT)["workload"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "mutations_rejected": {"configuration": configuration_mutations(),
            "preflight": rejected, "linked": producer["v21_linked_mutations"]},
        "next": "completion and complete same-world media closure, then D1",
        "claim_limit": "One replacement product card only; media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 CPU transport replacement: CARD PASS card=1/1 "
          f"reader={receipt['transport']['reader']['bytes']}B VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-cpu-transport-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: CPU-transport replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "replacement Final Red drift")
        print("2.1 CPU transport replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT); rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value), "preflight receipt drift")
        print("2.1 CPU transport replacement: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: replacement Link-107 CPU transport card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["process_isolation"]["all_distinct"] is True,
            "replacement green receipt drift")
    print("2.1 CPU transport replacement: CHECK PASS card=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 CPU transport replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
