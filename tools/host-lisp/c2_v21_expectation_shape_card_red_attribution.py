#!/usr/bin/env python3
"""Attribute the sole expectation-shape card Final Red without replay."""

from __future__ import annotations

import ast
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

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_v21_cpu_transport_card as CPU  # noqa: E402
import c2_v21_expectation_shape_card as CARD  # noqa: E402
import c2_v21_text_recovery_card as TEXT  # noqa: E402
import c2_v21_text_recovery_replacement_card as REPLACEMENT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
PRODUCER = CARD.PRODUCER_RESULT
ABI_REPORT = CARD.ABI_REPORT
INTERNAL = BUILD / "receipts/wplto-internal.json"
BASE_RESULT = BUILD / "receipts/wplto-base-result.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-expectation-shape-card-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-14"
HISTORICAL_COMMIT = "6d29dafd"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def historical_source(path: Path) -> str:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{HISTORICAL_COMMIT}:{name}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout


def historical_bind(path: Path) -> dict[str, Any]:
    raw = historical_source(path).encode()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def function(source: str, path: Path, name: str) -> ast.FunctionDef:
    rows = [node for node in ast.walk(ast.parse(
        source, filename=str(path)))
        if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique function absent: {path}:{name}")
    return rows[0]


def artifact_role_references(path: Path) -> list[str]:
    node = function(historical_source(path), path, "produce_child")
    roles: list[str] = []
    for row in ast.walk(node):
        if (isinstance(row, ast.Subscript)
                and isinstance(row.value, ast.Name)
                and row.value.id == "paths"
                and isinstance(row.slice, ast.Constant)
                and isinstance(row.slice.value, str)):
            roles.append(row.slice.value)
    return roles


def producer_roles() -> list[str]:
    program = (
        "import json,sys; sys.path.insert(0,'tools/host-lisp'); "
        "import c2_v21_expectation_shape_card as c; "
        "print(json.dumps(sorted(c.artifact_paths())))")
    output = subprocess.run(
        [sys.executable, "-c", program], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout
    roles = json.loads(output)
    require(isinstance(roles, list) and all(isinstance(role, str) for role in roles),
            "producer artifact-role subprocess drift")
    return roles


def chain_attribution() -> dict[str, Any]:
    actual_roles = producer_roles()
    chain = [
        ("cpu-transport", Path(CPU.__file__).resolve()),
        ("text-recovery", Path(TEXT.__file__).resolve()),
        ("text-recovery-replacement", Path(REPLACEMENT.__file__).resolve()),
    ]
    consumers = []
    for order, (name, path) in enumerate(chain):
        references = artifact_role_references(path)
        invalid = sorted(set(references) - set(actual_roles))
        consumers.append({"execution_order": order, "consumer": name,
            "source": historical_bind(path),
            "artifact_role_references": references,
            "invalid_references": invalid})
    invalid_consumers = [row for row in consumers if row["invalid_references"]]
    require(
        actual_roles == [
            "elf", "generated_decoder", "generated_phase02a", "linker",
            "lto", "map", "prg", "publish_last", "resolved_profile"]
        and [row["invalid_references"] for row in consumers] == [
            ["ELF"], ["ELF"], ["ELF"]]
        and consumers[0]["artifact_role_references"] == ["ELF", "map"],
        "artifact-role vocabulary attribution drift")
    return {
        "producer_roles": actual_roles,
        "producer_role_case": "lowercase",
        "consumers_inner_to_outer": consumers,
        "invalid_consumer_count": len(invalid_consumers),
        "first_failing_consumer": invalid_consumers[0]["consumer"],
        "first_missing_key": "ELF",
        "valid_role": "elf",
    }


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    producer = load(PRODUCER)
    internal = load(INTERNAL)
    base = load(BASE_RESULT)
    abi_report = load(ABI_REPORT)
    callers = abi_report["rtov_crc_mem_callers"]
    classification = CAN.classify_rtov_crc_callers(callers)
    chain = chain_attribution()
    require(
        red.get("status") ==
            "FINAL RED: sole expectation-shape card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red.get("attempt_accounting", {}).get(
            "replacement_cards_consumed") == 1
        and red.get("attempt_accounting", {}).get("WPLTO_runs") == 1
        and red.get("attempt_accounting", {}).get("product_link_attempts") == 1
        and red.get("error", {}).get("message", "").rstrip().endswith(
            "FINAL RED: 'ELF'")
        and producer.get("status") == "PASS"
        and internal.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal.get("execution_accounting", {}).get(
            "product_closure_links") == 1
        and base.get("WPLTO", {}).get("product_completed") is True
        and base.get("WPLTO", {}).get("exception") is None
        and abi_report.get("status") ==
            "passed-all-assembler-leaf-abi-contracts"
        and callers.get("callsite_count") == 10
        and classification.get("candidate_derived_callsite_count") == 10
        and classification.get("all_callers_classified") is True
        and abi_report["ELF_derived_C_called_inventory"]
            ["unclassified_C_called_functions"] == [],
        "expectation-shape card evidence drift")
    return {
        "format": "lisp65-c2.3-v21-expectation-shape-card-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": (
            "ATTRIBUTED FINAL RED: post-link wrapper requests uppercase "
            "artifact role from lowercase producer contract"),
        "card_result": {
            "cards_consumed": 1, "WPLTO_runs": 1, "product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0,
        },
        "product_evidence": {
            "WPLTO_internal_status": internal["status"],
            "product_completed_by_WPLTO": True,
            "real_ABI_status": abi_report["status"],
            "rtov_crc_callers": callers["callsite_count"],
            "classified_callers":
                classification["candidate_derived_callsite_count"],
            "unclassified_C_called_functions": [],
            "artifact_identity": producer["artifacts"],
        },
        "root_cause": {
            "class": "ARTIFACT-ROLE-VOCABULARY-CASE-MISMATCH",
            "mechanism": (
                "The real producer returns lowercase artifact roles. The "
                "first post-link CPU-transport wrapper indexes paths['ELF']; "
                "Python raises KeyError before linked-result augmentation. "
                "Two outer wrappers retain the same latent uppercase form."),
            **chain,
            "product_or_ABI_failure": False,
            "post_link_adapter_failure": True,
        },
        "card_disposition": {
            "retry_authorized": False,
            "owner_disposition_required": True,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False,
        },
        "authority": {"final_red": bind(FINAL_RED),
            "producer": bind(PRODUCER), "WPLTO_internal": bind(INTERNAL),
            "WPLTO_base_result": bind(BASE_RESULT),
            "real_ABI_report": bind(ABI_REPORT),
            "driver": historical_bind(DRIVER)},
        "claim_limit": (
            "Read-only attribution of the consumed card. It proves a "
            "post-link adapter vocabulary failure after a green product link "
            "and ABI classification; it authorizes no repair or retry."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    root = value.get("root_cause", {})
    require(
        value.get("status") ==
            "ATTRIBUTED FINAL RED: post-link wrapper requests uppercase "
            "artifact role from lowercase producer contract"
        and value.get("card_result") == {
            "cards_consumed": 1, "WPLTO_runs": 1, "product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and root.get("class") == "ARTIFACT-ROLE-VOCABULARY-CASE-MISMATCH"
        and root.get("invalid_consumer_count") == 3
        and root.get("first_failing_consumer") == "cpu-transport"
        and root.get("first_missing_key") == "ELF"
        and root.get("valid_role") == "elf"
        and root.get("product_or_ABI_failure") is False
        and value.get("card_disposition", {}).get("retry_authorized") is False,
        "expectation-shape card red attribution drift")
    if verify:
        require(value == derive(),
                "expectation-shape card red attribution authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-consumed-card": lambda x: x["card_result"].update(
            cards_consumed=0),
        "claim-green-card": lambda x: x.update(status="PASS"),
        "claim-product-failure": lambda x: x["root_cause"].update(
            product_or_ABI_failure=True),
        "erase-first-consumer": lambda x: x["root_cause"].update(
            first_failing_consumer=None),
        "erase-latent-consumers": lambda x: x["root_cause"].update(
            invalid_consumer_count=1),
        "accept-uppercase-role": lambda x: x["root_cause"].update(
            valid_role="ELF"),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "authorize-media": lambda x: x["card_disposition"].update(
            media_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "attribution receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "attribution receipt already exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 expectation-shape card red attribution: PASS "
          "product=green ABI=10/10 first=cpu-transport key=ELF retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "attribution mutation set drift")
    print("2.1 expectation-shape card red attribution: CHECK PASS "
          "product=green failure=post-link-role-vocabulary")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_expectation_shape_card_red_attribution.py "
            "record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"2.1 expectation-shape card red attribution: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
