#!/usr/bin/env python3
"""Exercise the complete post-link wrapper chain against its typed paths API."""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
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
import c2_v21_expectation_shape_card as CARD  # noqa: E402
import c2_v21_expectation_shape_card_red_attribution as ATTR  # noqa: E402
import c2_v21_text_recovery_card as TEXT  # noqa: E402
import c2_v21_text_recovery_replacement_card as REPLACEMENT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / "c2.3-v2.1-postlink-wrapper-contract-receipt.json"
PREDECESSOR = CARD.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "34e92a14"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-postlink-wrapper-contract-v1"
HISTORICAL_COMMIT = "bd2bfcf4"
CONTRACT_ROLES = (
    "elf", "generated_decoder", "generated_phase02a", "linker", "lto",
    "map", "prg", "publish_last", "resolved_profile")
WRAPPERS: tuple[tuple[str, Any, tuple[str, ...]], ...] = (
    ("cpu-transport", CPU, ("elf", "map")),
    ("text-recovery", TEXT, ("elf",)),
    ("text-recovery-replacement", REPLACEMENT, ("elf",)),
)


class ContractError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


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


def git_source(commit: str, path: Path) -> str:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout


def historical_bind(path: Path) -> dict[str, Any]:
    raw = git_source(HISTORICAL_COMMIT, path).encode()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("all three wrappers normalize", "conformance preflight",
                  "synthetic, contract-typed paths object",
                  "a card is a product experiment", "one replacement card"):
        require(token in text, f"wrapper-contract authorization absent: {token}")
    return authority


class TypedPaths(Mapping[str, Path]):
    """Strict synthetic producer object: unknown roles fail at the access site."""

    def __init__(self, roles: tuple[str, ...] = CONTRACT_ROLES) -> None:
        self._values = {role: Path(f"/synthetic/producer/{role}") for role in roles}
        self.accesses: list[str] = []

    def __getitem__(self, role: str) -> Path:
        self.accesses.append(role)
        if role not in self._values:
            raise ContractError(f"post-link wrapper accessed untyped role: {role}")
        return self._values[role]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def function(source: str, path: Path, name: str) -> ast.FunctionDef:
    rows = [node for node in ast.walk(ast.parse(source, filename=str(path)))
            if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique {name} absent: {path}")
    return rows[0]


def path_roles(node: ast.AST) -> list[str]:
    return [row.slice.value for row in ast.walk(node)
            if isinstance(row, ast.Subscript)
            and isinstance(row.value, ast.Name) and row.value.id == "paths"
            and isinstance(row.slice, ast.Constant)
            and isinstance(row.slice.value, str)]


def source_contract(path: Path, expected: tuple[str, ...],
                    source_override: str | None = None) -> dict[str, Any]:
    source = (path.read_text(encoding="utf-8")
              if source_override is None else source_override)
    helper = function(source, path, "postlink_artifacts")
    producer = function(source, path, "produce_child")
    calls = [row for row in ast.walk(producer)
             if isinstance(row, ast.Call)
             and isinstance(row.func, ast.Name)
             and row.func.id == "postlink_artifacts"]
    require(len(calls) == 1,
            f"{path.name}: produce_child bypasses typed post-link adapter")
    require(path_roles(producer) == [],
            f"{path.name}: produce_child directly indexes artifact roles")
    roles = tuple(path_roles(helper))
    require(roles == expected and set(roles) <= set(CONTRACT_ROLES),
            f"{path.name}: post-link adapter role vocabulary drift: {roles}")
    return {"adapter": "postlink_artifacts", "roles": list(roles),
            "producer_calls_adapter": True, "direct_producer_lookups": 0}


def execute_adapter(adapter: Callable[[Mapping[str, Path]], tuple[Path, ...]],
                    expected: tuple[str, ...]) -> dict[str, Any]:
    paths = TypedPaths()
    resolved = tuple(adapter(paths))
    require(tuple(paths.accesses) == expected,
            f"wrapper access trace drift: {paths.accesses}")
    require(resolved == tuple(paths._values[role] for role in expected),
            "wrapper did not return its typed producer values")
    return {"accessed_roles": list(paths.accesses),
            "resolved_values": [str(path) for path in resolved]}


def execute_mutated_adapter(path: Path, role: str) -> None:
    source = path.read_text(encoding="utf-8")
    node = function(source, path, "postlink_artifacts")
    mutated = deepcopy(node)
    changed = 0
    for row in ast.walk(mutated):
        if (isinstance(row, ast.Subscript)
                and isinstance(row.value, ast.Name) and row.value.id == "paths"
                and isinstance(row.slice, ast.Constant)
                and row.slice.value == "elf"):
            row.slice.value = role
            changed += 1
            break
    require(changed == 1, f"uppercase mutation site absent: {path}")
    module = ast.fix_missing_locations(ast.Module(body=[mutated], type_ignores=[]))
    namespace: dict[str, Any] = {"Mapping": Mapping, "Path": Path}
    exec(compile(module, str(path), "exec"), namespace)
    namespace["postlink_artifacts"](TypedPaths())


def actual_producer_roles() -> tuple[str, ...]:
    """Read the real contract in a fresh process so configuration cannot leak."""
    program = (
        "import json,sys; sys.path.insert(0,'tools/host-lisp'); "
        "import c2_v21_expectation_shape_card as c; "
        "print(json.dumps(sorted(c.artifact_paths())))")
    output = subprocess.run(
        [sys.executable, "-c", program], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout
    roles = json.loads(output)
    require(isinstance(roles, list) and all(isinstance(role, str) for role in roles),
            "producer contract subprocess returned invalid roles")
    return tuple(roles)


def gate(*, historical: bool = False) -> dict[str, Any]:
    actual_roles = actual_producer_roles()
    require(actual_roles == CONTRACT_ROLES,
            f"producer typed contract drift: {actual_roles}")
    rows = []
    for order, (name, module, expected) in enumerate(WRAPPERS):
        path = Path(module.__file__).resolve()
        source = git_source(HISTORICAL_COMMIT, path) if historical else None
        static = source_contract(path, expected, source)
        executed = execute_adapter(module.postlink_artifacts, expected)
        rows.append({"execution_order": order, "wrapper": name,
            "source": historical_bind(path) if historical else bind(path),
            "static_contract": static,
            "executed_contract": executed})
    require([row["wrapper"] for row in rows] == [
        "cpu-transport", "text-recovery", "text-recovery-replacement"],
        "post-link wrapper chain is incomplete")
    return {"status": "PASS: complete post-link chain executed against typed paths",
            "producer_roles": list(actual_roles),
            "wrapper_count": len(rows), "wrappers_inner_to_outer": rows,
            "WPLTO_runs": 0, "product_links": 0}


def mutations() -> list[str]:
    rejected: list[str] = []
    for name, module, _expected in WRAPPERS:
        try:
            execute_mutated_adapter(Path(module.__file__).resolve(), "ELF")
        except ContractError:
            rejected.append(f"uppercase-role:{name}")
    try:
        execute_adapter(lambda paths: (paths["outside-contract"],),
                        ("outside-contract",))
    except ContractError:
        rejected.append("wrapper-accesses-role-outside-contract")
    for name, module, expected in WRAPPERS:
        path = Path(module.__file__).resolve()
        source = path.read_text(encoding="utf-8")
        mutated = source.replace(
            "postlink_artifacts(paths)", "(paths[\"ELF\"],)", 1)
        try:
            source_contract(path, expected, mutated)
        except ContractError:
            rejected.append(f"producer-bypasses-adapter:{name}")
    expected = ([f"uppercase-role:{name}" for name, _module, _roles in WRAPPERS]
                + ["wrapper-accesses-role-outside-contract"]
                + [f"producer-bypasses-adapter:{name}"
                   for name, _module, _roles in WRAPPERS])
    require(rejected == expected, "post-link wrapper contract mutation survived")
    return rejected


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(red.get("status") ==
            "FINAL RED: sole expectation-shape card returns to owner"
            and red.get("retry_authorized") is False
            and attribution.get("root_cause", {}).get("invalid_consumer_count") == 3
            and attribution.get("root_cause", {}).get("first_missing_key") == "ELF",
            "wrapper-contract predecessor authority drift")
    return {"final_red": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION)}


def derive() -> dict[str, Any]:
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN: post-link wrapper contract conformance",
        "rule": "A card is a product experiment, not a plumbing test.",
        "authority": {"authorization": authorization(), **predecessor(),
                      "driver": historical_bind(DRIVER)},
        "contract_gate": gate(historical=True),
        "execution_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host-only wrapper conformance; no product card has run.",
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    gate_value = value.get("contract_gate", {})
    require(value.get("status") ==
            "HOST-GREEN: post-link wrapper contract conformance"
            and value.get("rule") ==
                "A card is a product experiment, not a plumbing test."
            and gate_value.get("producer_roles") == list(CONTRACT_ROLES)
            and gate_value.get("wrapper_count") == 3
            and gate_value.get("WPLTO_runs") == 0
            and value.get("execution_accounting") == {
                "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0},
            "post-link wrapper contract receipt drift")
    if verify:
        require(value == derive(), "post-link wrapper authority drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "hide-wrapper": lambda x: x["contract_gate"].update(wrapper_count=2),
        "accept-uppercase-role": lambda x: x["contract_gate"]
            ["producer_roles"].__setitem__(0, "ELF"),
        "spend-card": lambda x: x["execution_accounting"].update(cards_consumed=1),
        "run-WPLTO": lambda x: x["execution_accounting"].update(WPLTO_runs=1),
        "weaken-rule": lambda x: x.update(rule="Wrappers are tested by cards."),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except ContractError:
            rejected.append(name)
    require(rejected == list(cases), "wrapper receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "wrapper contract receipt already exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = {
        "contract": mutations(), "receipt": receipt_mutations(value)}
    RECEIPT.write_bytes(canonical(value))
    print("2.1 post-link wrapper contract: PASS wrappers=3 roles=9 card=0/1")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == {"contract": mutations(),
                         "receipt": receipt_mutations(value)},
            "wrapper contract mutation receipt drift")
    print("2.1 post-link wrapper contract: CHECK PASS wrappers=3 roles=9")


def selftest() -> None:
    result = gate()
    require(result["wrapper_count"] == 3 and len(mutations()) == 7,
            "post-link wrapper selftest drift")
    print("2.1 post-link wrapper contract: SELFTEST PASS mutations=7")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v21_postlink_wrapper_contract.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"2.1 post-link wrapper contract: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
