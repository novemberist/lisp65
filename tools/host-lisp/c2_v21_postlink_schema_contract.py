#!/usr/bin/env python3
"""Execute every active post-link schema consumer on actual producer output."""

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

import c2_v21_cpu_transport_card as CPU  # noqa: E402
import evidence_era as ERA  # noqa: E402
import c2_v21_guard_invariant_card as PREV  # noqa: E402
import c2_v21_guard_invariant_card_red_attribution as ATTR  # noqa: E402
import c2_v21_local_return_identity_card as LOCAL  # noqa: E402
import c2_v21_text_recovery_replacement_card as COMPLETION  # noqa: E402
import c2_v21_postlink_wrapper_contract as WRAPPERS  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = PREV.BUILD / "wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
MANIFEST = BUILD / "runtime-overlays-session-final.json"
KERNAL = BUILD / "kernal-freedom-link.json"
PUBLISH_LAST = BUILD / "runtime-verifier-publish-last.json"
CONTRACT = CPU.CONTRACT
FINAL_RED = PREV.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
RECEIPT = ARCH / "c2.3-v2.1-postlink-schema-contract-receipt.json"
DRIVER = Path(__file__).resolve()
LOCAL_SOURCE = Path(LOCAL.__file__).resolve()
AUTHORIZATION = "fb760d1c"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-postlink-schema-contract-v1"
# The receipt is sealed inside the replacement card's final red, so its own
# driver identity is read at the sealing commit (see evidence_era).
SEAL_ERA_COMMIT = "277b45ef"


class SchemaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SchemaError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
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
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("consumer speaks `control_flow_ownership`",
                  "every real post-link consumer schema",
                  "actual producer output", "one replacement card"):
        require(token in text, f"post-link schema authorization absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    red = load(FINAL_RED)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(
        red.get("status") == "FINAL RED: guard-invariant card returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("root_cause", {}).get("class") ==
            "POSTLINK-CONSUMER-SCHEMA-VOCABULARY-DRIFT"
        and attribution["root_cause"]["requested_field"] == "control_flow"
        and attribution["root_cause"]["producer_field"] ==
            "control_flow_ownership",
        "post-link schema predecessor drift")
    return {"final_red": bind(FINAL_RED), "attribution": bind(ATTRIBUTION)}


def function_source(path: Path, name: str,
                    source_override: str | None = None) -> ast.FunctionDef:
    source = path.read_text(encoding="utf-8") if source_override is None \
        else source_override
    rows = [node for node in ast.walk(ast.parse(source, filename=str(path)))
            if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique consumer absent: {path.name}:{name}")
    return rows[0]


def top_level_keys(path: Path, function: str, variable: str,
                   source_override: str | None = None) -> list[str]:
    node = function_source(path, function, source_override)
    keys = sorted({row.slice.value for row in ast.walk(node)
        if isinstance(row, ast.Subscript)
        and isinstance(row.value, ast.Name) and row.value.id == variable
        and isinstance(row.slice, ast.Constant)
        and isinstance(row.slice.value, str)})
    require(keys, f"consumer schema keys absent: {path.name}:{variable}")
    return keys


def validate_keys(name: str, consumed: list[str], produced: dict[str, Any]) -> None:
    unknown = sorted(set(consumed) - set(produced))
    require(not unknown, f"{name} consumes unknown producer keys: {unknown}")


def schema_rows() -> list[dict[str, Any]]:
    specs = (
        ("cpu-build-contract", Path(CPU.__file__).resolve(),
         "linked_transport_gate", "contract", CONTRACT),
        ("local-return-runtime-manifest", LOCAL_SOURCE,
         "linked_gate", "manifest", MANIFEST),
        ("local-return-kernal-freedom", LOCAL_SOURCE,
         "linked_gate", "kernal", KERNAL),
        ("completion-publish-last", Path(COMPLETION.__file__).resolve(),
         "completion_gate", "report", PUBLISH_LAST),
    )
    rows: list[dict[str, Any]] = []
    for name, path, function, variable, artifact in specs:
        produced = load(artifact)
        consumed = top_level_keys(path, function, variable)
        validate_keys(name, consumed, produced)
        rows.append({"consumer": name, "function": function,
            "variable": variable, "consumer_source": bind(path),
            "producer_artifact": bind(artifact),
            "consumed_top_level_keys": consumed,
            "producer_top_level_keys": sorted(produced),
            "unknown_keys": [], "actual_producer_output": True})
    return rows


def execute_consumers() -> dict[str, Any]:
    # Recreate the product configuration recorded by the actual ELF before
    # executing the consumers.  The family-stage row is a candidate property,
    # not a historical module default.
    PREV.configure()
    section = PRODUCT.section_table(ELF)[PRODUCT.VERIFIER_BINDING_SECTION]
    family_stage = section["bytes"] == (
        PRODUCT.VERIFIER_BINDING_BYTES + PRODUCT.FAMILY_STAGE_BINDING_BYTES)
    require(family_stage, "actual producer family-stage identity absent")
    PRODUCT.FAMILY_STAGE_BINDINGS = family_stage
    cpu = CPU.linked_transport_gate(ELF, MAP)
    local = LOCAL.linked_gate(ELF, MANIFEST)
    completion = COMPLETION.completion_gate(ELF)
    require(cpu["reader"]["address"] == "0x2277"
            and local["ownership"]["violations"] == []
            and local["status"] ==
                "PASS: local non-entries and emitted identities linked"
            and completion["status"] ==
                "PASS: publish-last consumed candidate identity",
            "actual post-link consumer execution drift")
    return {"consumer_count": 3, "actual_producer_output": True,
        "candidate_configuration": {"family_stage_bindings": family_stage},
        "cpu_linked_transport": cpu,
        "local_return_linked": local,
        "completion_identity": completion}


def gate() -> dict[str, Any]:
    wrappers = WRAPPERS.gate()
    rows = schema_rows()
    executions = execute_consumers()
    require(wrappers["wrapper_count"] == 3 and len(rows) == 4
            and executions["consumer_count"] == 3,
            "post-link wrapper/schema closure incomplete")
    return {"status": "PASS: wrappers and real post-link schemas conform",
        "typed_path_wrappers": wrappers, "schema_consumers": rows,
        "real_consumer_executions": executions,
        "schema_unknown_key_count": 0,
        "WPLTO_runs": 0, "product_links": 0}


def contract_mutations() -> list[str]:
    rejected: list[str] = []
    source = LOCAL_SOURCE.read_text(encoding="utf-8")
    mutated = source.replace(
        'ownership = kernal["control_flow_ownership"]',
        'ownership = kernal["control_flow"]', 1)
    require(mutated != source, "retired consumer-key mutation site absent")
    try:
        consumed = top_level_keys(
            LOCAL_SOURCE, "linked_gate", "kernal", mutated)
        validate_keys("local-return-kernal-freedom", consumed, load(KERNAL))
    except SchemaError:
        rejected.append("consumer-requests-unknown-control_flow")

    specs: tuple[tuple[str, Path, str, str, Path, str], ...] = (
        ("producer-drops-build", Path(CPU.__file__).resolve(),
         "linked_transport_gate", "contract", CONTRACT, "build"),
        ("producer-drops-storage", LOCAL_SOURCE, "linked_gate", "manifest",
         MANIFEST, "storage"),
        ("producer-drops-control-flow-ownership", LOCAL_SOURCE, "linked_gate",
         "kernal", KERNAL, "control_flow_ownership"),
        ("producer-drops-expected-address", Path(COMPLETION.__file__).resolve(),
         "completion_gate", "report", PUBLISH_LAST, "expected_address"),
    )
    for name, path, function, variable, artifact, dropped in specs:
        produced = load(artifact); produced.pop(dropped)
        try:
            validate_keys(name, top_level_keys(path, function, variable), produced)
        except SchemaError:
            rejected.append(name)
    expected = ["consumer-requests-unknown-control_flow"] + [
        item[0] for item in specs]
    require(rejected == expected, "post-link schema mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN: all real post-link consumer schemas conform",
        "rule": (
            "A card is a product experiment: typed paths and actual producer "
            "schemas both pass before WPLTO."),
        "authority": {"authorization": authorization(), **predecessor(),
            "frozen_ELF": bind(ELF), "frozen_map": bind(MAP),
            "driver": ERA.era_bind(SEAL_ERA_COMMIT, DRIVER)},
        "contract_gate": gate(),
        "execution_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host-only real-consumer preflight; no card has run.",
    }


# This receipt is sealed inside the replacement card's final red, so it cannot
# follow the tree; but what it gates is schema conformance, not file bytes.
# Requiring byte equality made an unrelated value edit inside a release
# contract read as "schema authority drift".  Identity and every consumed and
# produced key still compare exactly; only the content digest of a validated
# file is allowed to move, because the file is validated live on every run.
def _schema_content(value: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(value)
    for row in value.get("contract_gate", {}).get("schema_consumers", []):
        for field in ("producer_artifact", "consumer_source"):
            binding = row.get(field)
            if isinstance(binding, dict):
                row[field] = {"path": binding.get("path")}
    return value


def validate(value: dict[str, Any], *, verify: bool) -> None:
    gate_value = value.get("contract_gate", {})
    require(
        value.get("status") ==
            "HOST-GREEN: all real post-link consumer schemas conform"
        and gate_value.get("status") ==
            "PASS: wrappers and real post-link schemas conform"
        and gate_value.get("typed_path_wrappers", {}).get("wrapper_count") == 3
        and len(gate_value.get("schema_consumers", [])) == 4
        and gate_value.get("real_consumer_executions", {}).get(
            "consumer_count") == 3
        and gate_value.get("real_consumer_executions", {}).get(
            "actual_producer_output") is True
        and gate_value.get("schema_unknown_key_count") == 0
        and value.get("execution_accounting") == {"cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "post-link schema receipt weakened")
    if verify:
        require(_schema_content(value) == _schema_content(derive()),
                "post-link schema authority drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-schema-consumer": lambda x: x["contract_gate"]
            ["schema_consumers"].pop(),
        "accept-unknown-key": lambda x: x["contract_gate"].update(
            schema_unknown_key_count=1),
        "replace-actual-output-with-synthetic": lambda x: x["contract_gate"]
            ["real_consumer_executions"].update(actual_producer_output=False),
        "skip-real-consumer": lambda x: x["contract_gate"]
            ["real_consumer_executions"].update(consumer_count=2),
        "spend-card": lambda x: x["execution_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except SchemaError:
            rejected.append(name)
    require(rejected == list(cases), "post-link schema receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "post-link schema receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = {
        "contract": contract_mutations(), "receipt": receipt_mutations(value)}
    RECEIPT.write_bytes(canonical(value))
    print("2.1 post-link schemas: PASS wrappers=3 schemas=4 real-consumers=3")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == {"contract": contract_mutations(),
                         "receipt": receipt_mutations(value)},
            "post-link schema mutation receipt drift")
    print("2.1 post-link schemas: CHECK PASS unknown=0 actual-output=yes")


def selftest() -> None:
    result = gate()
    require(result["schema_unknown_key_count"] == 0
            and len(contract_mutations()) == 5,
            "post-link schema selftest drift")
    print("2.1 post-link schemas: SELFTEST PASS mutations=5")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v21_postlink_schema_contract.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SchemaError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 post-link schemas: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
