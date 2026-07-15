#!/usr/bin/env python3
"""Lint and run the repository's semantic contract registry."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Sequence


REGISTRY_FORMAT = "lisp65-semantic-contract-registry-v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "config" / "semantic-contracts.json"
ADAPTER_TIMEOUT_SECONDS = 300

EXIT_OK = 0
EXIT_LINT = 1
EXIT_ADAPTER = 2
EXIT_INFRASTRUCTURE = 3
EXIT_SELFTEST = 4
EXIT_USAGE = 64

TOP_KEYS = {"format", "engines", "contracts"}
ENGINE_KEYS = {"id", "class"}
CONTRACT_KEYS = {
    "id",
    "kind",
    "status",
    "fixture",
    "claims",
    "required_engines",
    "adapters",
    "coverage_gaps",
    "legacy_references",
}
FIXTURE_KEYS = {"path", "format"}
ADAPTER_KEYS = {
    "id",
    "engine",
    "stage",
    "mode",
    "fixture_binding",
    "argv",
}
GAP_KEYS = {"engine", "target_stage", "reason"}

ENGINE_CLASSES = {"model", "native", "product", "legacy"}
CONTRACT_STATUSES = {"normative", "candidate"}
CLAIMS = {"host", "product"}
STAGES = {"G0", "G1", "G2"}
ADAPTER_MODES = {"cases", "drift", "malformed"}
FIXTURE_BINDINGS = {"argument", "generated"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PYTHON_PROGRAM_RE = re.compile(r"^python(?:3(?:\.\d+)?)?(?:\.exe)?$")
STAGE_ORDER = {"G0": 0, "G1": 1, "G2": 2}
# Product claims require a separately reviewed runner entry point. Each tuple
# pins both the registry adapter id and its repository entry point.
APPROVED_PRODUCT_ADAPTERS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "workbench-eval-surface-binding",
            "tools/host-lisp/workbench_eval_surface.py",
        )
    }
)
SHELL_PROGRAMS = {
    "ash",
    "bash",
    "cmd",
    "cmd.exe",
    "csh",
    "dash",
    "fish",
    "ksh",
    "nu",
    "powershell",
    "pwsh",
    "sh",
    "tcsh",
    "xonsh",
    "zsh",
}
INDIRECT_PROGRAMS = {"busybox", "env"}


class RegistryError(RuntimeError):
    """A registry or fixture violates the semantic-contract schema."""


class AdapterError(RuntimeError):
    """An adapter could not be launched or returned a failure status."""

    def __init__(self, contract_id: str, adapter_id: str, detail: str):
        super().__init__(detail)
        self.contract_id = contract_id
        self.adapter_id = adapter_id


class AdapterLaunchError(AdapterError):
    """An adapter process could not be started."""


class ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RegistryError(f"cannot read {label} {path}: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_strict_object)
    except RegistryError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"invalid JSON in {label} {path}: {exc}") from exc


def _exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{label} must be an object")
    actual = set(value)
    missing = sorted(keys - actual)
    unknown = sorted(actual - keys)
    if missing:
        raise RegistryError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise RegistryError(f"{label} has unknown keys: {', '.join(unknown)}")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{label} must be a non-empty string")
    if "\x00" in value:
        raise RegistryError(f"{label} must not contain NUL")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _nonempty_string(value, label)
    if not ID_RE.fullmatch(value):
        raise RegistryError(f"{label} must match {ID_RE.pattern!r}")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RegistryError(f"{label} must be a list")
    return value


def _string_list(value: Any, label: str, *, unique: bool = True) -> list[str]:
    values = _list(value, label)
    result = [_nonempty_string(item, f"{label}[{index}]") for index, item in enumerate(values)]
    if unique and len(result) != len(set(result)):
        raise RegistryError(f"{label} contains duplicate values")
    return result


def _choice(value: Any, choices: set[str], label: str) -> str:
    value = _nonempty_string(value, label)
    if value not in choices:
        raise RegistryError(f"{label} has invalid value {value!r}")
    return value


def _repo_path(
    root: Path, value: Any, label: str, *, require_file: bool = False
) -> tuple[str, Path]:
    raw = _nonempty_string(value, label)
    if "\\" in raw:
        raise RegistryError(f"{label} must use normalized POSIX separators")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or raw != pure.as_posix() or any(part in {"", ".", ".."} for part in pure.parts):
        raise RegistryError(f"{label} must be a normalized relative repository path")

    root = root.resolve()
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except FileNotFoundError as exc:
        raise RegistryError(f"{label} does not exist: {raw}") from exc
    except (OSError, ValueError) as exc:
        raise RegistryError(f"{label} escapes repository root: {raw}") from exc
    if require_file and not resolved.is_file():
        raise RegistryError(f"{label} is not a file: {raw}")
    return raw, resolved


def _check_argv(argv: Any, binding: str, label: str, root: Path) -> list[str]:
    values = _string_list(argv, label, unique=False)
    if not values:
        raise RegistryError(f"{label} must be non-empty")
    for index, arg in enumerate(values):
        remainder = arg.replace("{root}", "").replace("{fixture}", "")
        if "{" in remainder or "}" in remainder:
            raise RegistryError(f"{label}[{index}] contains an unknown or malformed placeholder")
    if binding == "argument" and not any("{fixture}" in arg for arg in values):
        raise RegistryError(f"{label} must bind the fixture with {{fixture}}")
    if binding == "generated" and any("{fixture}" in arg for arg in values):
        raise RegistryError(f"{label} generated binding must not pass {{fixture}}")
    program = PurePosixPath(values[0]).name.lower()
    if program in SHELL_PROGRAMS:
        raise RegistryError(f"{label} must not invoke a shell: {values[0]!r}")
    if program in INDIRECT_PROGRAMS:
        raise RegistryError(f"{label} must not use indirect launcher {values[0]!r}")
    if program.endswith(".sh"):
        raise RegistryError(f"{label} must not invoke a shell script directly: {values[0]!r}")
    if PYTHON_PROGRAM_RE.fullmatch(program):
        if len(values) < 2 or not values[1].endswith(".py"):
            raise RegistryError(f"{label} Python adapter must name a repository .py file")
        script = values[1].replace("{root}/", "")
        _repo_path(root, script, f"{label} Python script", require_file=True)

    expanded = values[0].replace("{root}", str(root))
    program_path = Path(expanded)
    if not program_path.is_absolute():
        program_path = root / program_path
    if program_path.is_file():
        try:
            first_line = program_path.open("rb").readline(256).decode("ascii", errors="ignore")
        except OSError as exc:
            raise RegistryError(f"{label} cannot inspect executable {values[0]!r}: {exc}") from exc
        if first_line.startswith("#!"):
            words = first_line[2:].strip().split()
            interpreter = PurePosixPath(words[0]).name.lower() if words else ""
            if interpreter in SHELL_PROGRAMS or interpreter in INDIRECT_PROGRAMS:
                raise RegistryError(
                    f"{label} executable uses an indirect/shell shebang: {values[0]!r}"
                )
    return values


def _adapter_entrypoint(root: Path, argv: list[str]) -> str | None:
    program = PurePosixPath(argv[0]).name.lower()
    raw = argv[1] if PYTHON_PROGRAM_RE.fullmatch(program) and len(argv) > 1 else argv[0]
    expanded = raw.replace("{root}/", "")
    try:
        path = (root / expanded).resolve(strict=True)
        return path.relative_to(root.resolve()).as_posix()
    except (FileNotFoundError, OSError, ValueError):
        return None


def validate_registry(
    data: Any,
    root: Path,
    *,
    approved_product_adapters: frozenset[tuple[str, str]] = APPROVED_PRODUCT_ADAPTERS,
) -> dict[str, int]:
    root = root.resolve()
    top = _exact_object(data, TOP_KEYS, "registry")
    if top["format"] != REGISTRY_FORMAT:
        raise RegistryError(f"registry.format must be {REGISTRY_FORMAT!r}")

    engines = _list(top["engines"], "registry.engines")
    if not engines:
        raise RegistryError("registry.engines must be non-empty")
    engine_classes: dict[str, str] = {}
    for index, raw_engine in enumerate(engines):
        label = f"registry.engines[{index}]"
        engine = _exact_object(raw_engine, ENGINE_KEYS, label)
        engine_id = _identifier(engine["id"], f"{label}.id")
        if engine_id in engine_classes:
            raise RegistryError(f"duplicate engine id {engine_id!r}")
        engine_classes[engine_id] = _choice(engine["class"], ENGINE_CLASSES, f"{label}.class")

    contracts = _list(top["contracts"], "registry.contracts")
    if not contracts:
        raise RegistryError("registry.contracts must be non-empty")
    contract_ids: set[str] = set()
    adapter_ids: set[str] = set()
    adapter_count = 0
    for contract_index, raw_contract in enumerate(contracts):
        base = f"registry.contracts[{contract_index}]"
        contract = _exact_object(raw_contract, CONTRACT_KEYS, base)
        contract_id = _identifier(contract["id"], f"{base}.id")
        if contract_id in contract_ids:
            raise RegistryError(f"duplicate contract id {contract_id!r}")
        contract_ids.add(contract_id)
        label = f"contract {contract_id!r}"
        _nonempty_string(contract["kind"], f"{label}.kind")
        status = _choice(contract["status"], CONTRACT_STATUSES, f"{label}.status")

        fixture = _exact_object(contract["fixture"], FIXTURE_KEYS, f"{label}.fixture")
        _, fixture_path = _repo_path(
            root, fixture["path"], f"{label}.fixture.path", require_file=True
        )
        fixture_format = _nonempty_string(fixture["format"], f"{label}.fixture.format")
        fixture_data = _load_json(fixture_path, f"fixture for {contract_id!r}")
        if not isinstance(fixture_data, dict) or fixture_data.get("format") != fixture_format:
            actual = fixture_data.get("format") if isinstance(fixture_data, dict) else None
            raise RegistryError(
                f"{label}.fixture.format {fixture_format!r} does not match fixture JSON {actual!r}"
            )

        claims = _string_list(contract["claims"], f"{label}.claims")
        if status == "normative" and not claims:
            raise RegistryError(f"{label}.claims must be non-empty for a normative contract")
        for claim in claims:
            _choice(claim, CLAIMS, f"{label}.claims")

        required_engines = _string_list(contract["required_engines"], f"{label}.required_engines")
        if status == "normative" and not required_engines:
            raise RegistryError(
                f"{label}.required_engines must be non-empty for a normative contract"
            )
        for engine_id in required_engines:
            if engine_id not in engine_classes:
                raise RegistryError(f"{label} references unknown required engine {engine_id!r}")
            if engine_classes[engine_id] == "legacy":
                raise RegistryError(f"{label} must not require legacy engine {engine_id!r}")

        adapters = _list(contract["adapters"], f"{label}.adapters")
        cases_by_engine: dict[str, list[dict[str, Any]]] = {}
        for adapter_index, raw_adapter in enumerate(adapters):
            adapter_label = f"{label}.adapters[{adapter_index}]"
            adapter = _exact_object(raw_adapter, ADAPTER_KEYS, adapter_label)
            adapter_id = _identifier(adapter["id"], f"{adapter_label}.id")
            if adapter_id in adapter_ids:
                raise RegistryError(f"duplicate adapter id {adapter_id!r}")
            adapter_ids.add(adapter_id)
            adapter_count += 1
            engine_id = _nonempty_string(adapter["engine"], f"{adapter_label}.engine")
            if engine_id not in engine_classes:
                raise RegistryError(f"{adapter_label} references unknown engine {engine_id!r}")
            if engine_classes[engine_id] == "legacy":
                raise RegistryError(f"{adapter_label} must not execute legacy engine {engine_id!r}")
            _choice(adapter["stage"], STAGES, f"{adapter_label}.stage")
            mode = _choice(adapter["mode"], ADAPTER_MODES, f"{adapter_label}.mode")
            binding = _choice(
                adapter["fixture_binding"], FIXTURE_BINDINGS, f"{adapter_label}.fixture_binding"
            )
            _check_argv(adapter["argv"], binding, f"{adapter_label}.argv", root)
            if mode == "cases":
                cases_by_engine.setdefault(engine_id, []).append(adapter)

        for engine_id in required_engines:
            if not cases_by_engine.get(engine_id):
                raise RegistryError(f"{label} required engine {engine_id!r} has no cases adapter")

        if "host" in claims:
            for engine_id in required_engines:
                adapters_for_engine = cases_by_engine.get(engine_id, [])
                if not any(adapter["stage"] in {"G0", "G1"} for adapter in adapters_for_engine):
                    raise RegistryError(
                        f"{label} host engine {engine_id!r} requires a G0/G1 cases adapter"
                    )

        if "product" in claims:
            product_ready = any(
                engine_classes[engine_id] == "product"
                and any(
                    adapter["stage"] == "G2"
                    and adapter["fixture_binding"] == "argument"
                    and (
                        adapter["id"],
                        _adapter_entrypoint(root, adapter["argv"]),
                    )
                    in approved_product_adapters
                    for adapter in cases_by_engine.get(engine_id, [])
                )
                for engine_id in required_engines
            )
            if not product_ready:
                raise RegistryError(
                    f"{label} product claim requires an approved fixture-bound G2 product adapter"
                )

        gaps = _list(contract["coverage_gaps"], f"{label}.coverage_gaps")
        gap_engines: set[str] = set()
        for gap_index, raw_gap in enumerate(gaps):
            gap_label = f"{label}.coverage_gaps[{gap_index}]"
            gap = _exact_object(raw_gap, GAP_KEYS, gap_label)
            engine_id = _nonempty_string(gap["engine"], f"{gap_label}.engine")
            if engine_id not in engine_classes:
                raise RegistryError(f"{gap_label} references unknown engine {engine_id!r}")
            if engine_id in gap_engines:
                raise RegistryError(f"{label}.coverage_gaps duplicates engine {engine_id!r}")
            target_stage = _choice(
                gap["target_stage"], STAGES, f"{gap_label}.target_stage"
            )
            covered_at_target = any(
                STAGE_ORDER[adapter["stage"]] <= STAGE_ORDER[target_stage]
                for adapter in cases_by_engine.get(engine_id, [])
            )
            if covered_at_target:
                raise RegistryError(
                    f"{label}.coverage_gaps engine {engine_id!r} is already covered at "
                    f"{target_stage}"
                )
            gap_engines.add(engine_id)
            _nonempty_string(gap["reason"], f"{gap_label}.reason")

        references = _string_list(contract["legacy_references"], f"{label}.legacy_references")
        for reference_index, reference in enumerate(references):
            _repo_path(root, reference, f"{label}.legacy_references[{reference_index}]")

    return {
        "engines": len(engines),
        "contracts": len(contracts),
        "adapters": adapter_count,
    }


def load_registry(path: Path, root: Path) -> tuple[dict[str, Any], dict[str, int]]:
    data = _load_json(path, "registry")
    summary = validate_registry(data, root)
    return data, summary


def _expand_argv(argv: list[str], root: Path, fixture: Path) -> list[str]:
    replacements = {"{root}": str(root), "{fixture}": str(fixture)}
    return [
        arg.replace("{root}", replacements["{root}"]).replace("{fixture}", replacements["{fixture}"])
        for arg in argv
    ]


def _emit_line(message: str) -> None:
    print(message, flush=True)


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        if process.poll() is None:
            process.terminate()
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        # The group can outlive its leader when a child ignores SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        if process.poll() is None:
            process.kill()
    if process.poll() is None:
        process.wait()


def run_stage(
    data: dict[str, Any],
    root: Path,
    stage: str,
    *,
    emit: Callable[[str], None] = _emit_line,
    timeout: float = ADAPTER_TIMEOUT_SECONDS,
) -> int:
    if stage not in STAGES:
        raise ValueError(f"invalid stage {stage!r}")
    root = root.resolve()
    count = 0
    for contract in data["contracts"]:
        fixture = root / contract["fixture"]["path"]
        for adapter in contract["adapters"]:
            if adapter["stage"] != stage:
                continue
            count += 1
            emit(
                "semantic-contracts: RUN "
                f"stage={stage} contract={contract['id']} adapter={adapter['id']}"
            )
            argv = _expand_argv(adapter["argv"], root, fixture)
            try:
                process = subprocess.Popen(
                    argv,
                    cwd=root,
                    shell=False,
                    start_new_session=os.name == "posix",
                )
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _terminate_process_tree(process)
                raise AdapterError(
                    contract["id"],
                    adapter["id"],
                    f"adapter timed out after {timeout:g}s",
                ) from exc
            except OSError as exc:
                raise AdapterLaunchError(
                    contract["id"], adapter["id"], f"cannot execute: {exc}"
                ) from exc
            if returncode != 0:
                raise AdapterError(
                    contract["id"], adapter["id"], f"adapter exited {returncode}"
                )
    return count


def _base_selftest_registry(python: str) -> dict[str, Any]:
    def adapter(adapter_id: str, engine: str, stage: str) -> dict[str, Any]:
        return {
            "id": adapter_id,
            "engine": engine,
            "stage": stage,
            "mode": "cases",
            "fixture_binding": "argument",
            "argv": [
                python,
                "{root}/adapter.py",
                stage,
                "{root}/runs.txt",
                "{fixture}",
            ],
        }

    return {
        "format": REGISTRY_FORMAT,
        "engines": [
            {"id": "model", "class": "model"},
            {"id": "native", "class": "native"},
            {"id": "product", "class": "product"},
            {"id": "old", "class": "legacy"},
        ],
        "contracts": [
            {
                "id": "reader-v1",
                "kind": "reader",
                "status": "normative",
                "fixture": {"path": "fixtures/reader.json", "format": "reader-fixture-v1"},
                "claims": ["product"],
                "required_engines": ["model", "native", "product"],
                "adapters": [
                    adapter("model-cases", "model", "G0"),
                    adapter("native-cases", "native", "G1"),
                    adapter("product-cases", "product", "G2"),
                ],
                "coverage_gaps": [
                    {"engine": "old", "target_stage": "G1", "reason": "reference only"}
                ],
                "legacy_references": ["legacy/reader.py"],
            }
        ],
    }


def selftest() -> int:
    cases = 0
    failures: list[str] = []

    def expect(label: str, condition: bool, detail: str = "") -> None:
        nonlocal cases
        cases += 1
        if not condition:
            failures.append(f"{label}: {detail or 'condition was false'}")

    with tempfile.TemporaryDirectory(prefix="lisp65-semantic-contracts-") as temp_name:
        root = Path(temp_name)
        (root / "fixtures").mkdir()
        (root / "legacy").mkdir()
        (root / "fixtures" / "reader.json").write_text(
            json.dumps({"format": "reader-fixture-v1", "cases": []}) + "\n", encoding="ascii"
        )
        (root / "legacy" / "reader.py").write_text("# reference\n", encoding="ascii")
        (root / "adapter.py").write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "Path(sys.argv[2]).open('a', encoding='ascii').write(sys.argv[1] + '\\n')\n",
            encoding="ascii",
        )
        base = _base_selftest_registry(sys.executable)
        approved = frozenset({("product-cases", "adapter.py")})

        def validate(value: dict[str, Any]) -> dict[str, int]:
            return validate_registry(
                value,
                root,
                approved_product_adapters=approved,
            )

        try:
            summary = validate(base)
        except RegistryError as exc:
            expect("happy-lint", False, str(exc))
        else:
            expect("happy-lint", summary == {"engines": 4, "contracts": 1, "adapters": 3})

        def reject(label: str, mutate: Callable[[dict[str, Any]], None], needle: str) -> None:
            value = deepcopy(base)
            mutate(value)
            try:
                validate(value)
            except RegistryError as exc:
                expect(label, needle in str(exc), str(exc))
            else:
                expect(label, False, "registry was accepted")

        reject("unknown-key", lambda value: value.update({"extra": True}), "unknown keys")
        reject("missing-key", lambda value: value["contracts"][0].pop("kind"), "missing keys")
        reject("empty-contracts", lambda value: value.update({"contracts": []}), "non-empty")
        reject(
            "duplicate-engine",
            lambda value: value["engines"].append({"id": "model", "class": "model"}),
            "duplicate engine",
        )
        reject(
            "unknown-engine",
            lambda value: value["contracts"][0]["required_engines"].append("missing"),
            "unknown required engine",
        )
        reject(
            "path-traversal",
            lambda value: value["contracts"][0]["fixture"].update({"path": "../reader.json"}),
            "normalized relative",
        )
        reject(
            "fixture-format",
            lambda value: value["contracts"][0]["fixture"].update({"format": "wrong"}),
            "does not match",
        )
        reject(
            "missing-cases",
            lambda value: value["contracts"][0]["adapters"][0].update({"mode": "drift"}),
            "has no cases adapter",
        )
        reject(
            "product-stage",
            lambda value: value["contracts"][0]["adapters"][2].update({"stage": "G1"}),
            "G2 product",
        )
        reject(
            "gap-reason",
            lambda value: value["contracts"][0]["coverage_gaps"][0].update({"reason": ""}),
            "non-empty string",
        )
        reject(
            "fixture-binding",
            lambda value: value["contracts"][0]["adapters"][0].update(
                {"argv": [sys.executable, "{root}/adapter.py"]}
            ),
            "bind the fixture",
        )
        reject(
            "generated-binding",
            lambda value: value["contracts"][0]["adapters"][0].update(
                {"fixture_binding": "generated"}
            ),
            "must not pass",
        )
        reject(
            "placeholder",
            lambda value: value["contracts"][0]["adapters"][0]["argv"].append("{other}"),
            "placeholder",
        )
        reject(
            "shell",
            lambda value: value["contracts"][0]["adapters"][0].update(
                {"argv": ["sh", "{root}/adapter.py", "{fixture}"]}
            ),
            "must not invoke a shell",
        )
        reject(
            "indirect-shell",
            lambda value: value["contracts"][0]["adapters"][0].update(
                {"argv": ["env", "-i", "sh", "-c", "true", "{fixture}"]}
            ),
            "indirect launcher",
        )
        reject(
            "covered-gap",
            lambda value: value["contracts"][0]["coverage_gaps"][0].update(
                {"engine": "model"}
            ),
            "already covered",
        )

        try:
            repeated = _check_argv(
                [sys.executable, "{root}/adapter.py", "same", "same", "{fixture}"],
                "argument",
                "selftest.argv",
                root,
            )
        except RegistryError as exc:
            expect("repeated-argv", False, str(exc))
        else:
            expect("repeated-argv", repeated[2:4] == ["same", "same"])

        reject(
            "host-stage",
            lambda value: value["contracts"][0].update(
                {
                    "claims": ["host"],
                    "required_engines": ["product"],
                    "adapters": [value["contracts"][0]["adapters"][2]],
                }
            ),
            "G0/G1",
        )
        reject(
            "product-generated",
            lambda value: value["contracts"][0]["adapters"][2].update(
                {"fixture_binding": "generated", "argv": [sys.executable, "{root}/adapter.py"]}
            ),
            "approved fixture-bound G2",
        )
        reject(
            "product-unapproved",
            lambda value: value["contracts"][0]["adapters"][2].update(
                {"argv": ["true", "{fixture}"]}
            ),
            "approved fixture-bound G2",
        )
        reject(
            "legacy-adapter",
            lambda value: value["contracts"][0]["adapters"].append(
                {
                    "id": "legacy-cases",
                    "engine": "old",
                    "stage": "G0",
                    "mode": "cases",
                    "fixture_binding": "argument",
                    "argv": [sys.executable, "{root}/adapter.py", "G0", "{root}/runs.txt", "{fixture}"],
                }
            ),
            "must not execute legacy engine",
        )

        (root / "shell-env-s").write_text("#!/usr/bin/env -Ssh -eu\n", encoding="ascii")
        reject(
            "shell-env-shebang",
            lambda value: value["contracts"][0]["adapters"][0].update(
                {"argv": ["{root}/shell-env-s", "{fixture}"]}
            ),
            "shell shebang",
        )

        later_gap = deepcopy(base)
        later_gap["contracts"][0]["coverage_gaps"] = [
            {"engine": "product", "target_stage": "G1", "reason": "only covered in G2"}
        ]
        try:
            validate(later_gap)
        except RegistryError as exc:
            expect("later-stage-gap", False, str(exc))
        else:
            expect("later-stage-gap", True)

        (root / "timeout.py").write_text(
            "from pathlib import Path\n"
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', "
            "'from pathlib import Path; import signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(0.3); Path(sys.argv[1]).write_text(\\\"late\\\")', "
            "sys.argv[1]])\n"
            "time.sleep(10)\n",
            encoding="ascii",
        )
        timeout_registry = deepcopy(base)
        timeout_registry["contracts"][0]["claims"] = ["host"]
        timeout_registry["contracts"][0]["required_engines"] = ["native"]
        timeout_registry["contracts"][0]["adapters"] = [
            {
                "id": "timeout-cases",
                "engine": "native",
                "stage": "G1",
                "mode": "cases",
                "fixture_binding": "argument",
                "argv": [
                    sys.executable,
                    "{root}/timeout.py",
                    "{root}/late.txt",
                    "{fixture}",
                ],
            }
        ]
        try:
            validate(timeout_registry)
            run_stage(timeout_registry, root, "G1", emit=lambda _: None, timeout=0.05)
        except AdapterError as exc:
            time.sleep(0.3)
            expect(
                "timeout-process-tree",
                "timed out" in str(exc) and not (root / "late.txt").exists(),
                str(exc),
            )
        else:
            expect("timeout-process-tree", False, "timeout adapter succeeded")

        failure_registry = deepcopy(base)
        failure_registry["contracts"][0]["claims"] = ["host"]
        failure_registry["contracts"][0]["required_engines"] = ["native"]
        failure_registry["contracts"][0]["adapters"] = [
            {
                "id": "failure-cases",
                "engine": "native",
                "stage": "G1",
                "mode": "cases",
                "fixture_binding": "argument",
                "argv": [sys.executable, "{root}/failure.py", "{fixture}"],
            }
        ]
        (root / "failure.py").write_text("raise SystemExit(7)\n", encoding="ascii")
        try:
            validate(failure_registry)
            run_stage(failure_registry, root, "G1", emit=lambda _: None)
        except AdapterError as exc:
            expect("adapter-exit", "exited 7" in str(exc), str(exc))
        else:
            expect("adapter-exit", False, "failing adapter succeeded")

        launch_registry = deepcopy(failure_registry)
        launch_registry["contracts"][0]["adapters"][0].update(
            {"argv": ["{root}/missing-adapter", "{fixture}"]}
        )
        try:
            validate(launch_registry)
            run_stage(launch_registry, root, "G1", emit=lambda _: None)
        except AdapterLaunchError as exc:
            expect("adapter-launch", "cannot execute" in str(exc), str(exc))
        else:
            expect("adapter-launch", False, "missing adapter executable succeeded")

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            missing_status = main(["lint", "--registry", str(root / "missing-registry.json")])
        expect(
            "missing-registry-exit",
            missing_status == EXIT_INFRASTRUCTURE and "phase=infrastructure" in stderr.getvalue(),
            f"status={missing_status} stderr={stderr.getvalue()!r}",
        )

        output: list[str] = []
        try:
            count = run_stage(base, root, "G1", emit=output.append)
            runs = (root / "runs.txt").read_text(encoding="ascii").splitlines()
        except (AdapterError, OSError) as exc:
            expect("exact-stage-run", False, str(exc))
        else:
            expect(
                "exact-stage-run",
                count == 1 and runs == ["G1"] and len(output) == 1 and "native-cases" in output[0],
                f"count={count} runs={runs!r} output={output!r}",
            )

        duplicate_path = root / "duplicate.json"
        duplicate_path.write_text(
            '{"format":"%s","format":"%s","engines":[],"contracts":[]}\n'
            % (REGISTRY_FORMAT, REGISTRY_FORMAT),
            encoding="ascii",
        )
        try:
            _load_json(duplicate_path, "selftest registry")
        except RegistryError as exc:
            expect("duplicate-json-key", "duplicate JSON key" in str(exc), str(exc))
        else:
            expect("duplicate-json-key", False, "duplicate key was accepted")

    if failures:
        print(
            f"semantic-contracts selftest: FAIL cases={cases} failures={len(failures)} "
            + "; ".join(failures),
            file=sys.stderr,
        )
        return EXIT_SELFTEST
    print(f"semantic-contracts selftest: PASS cases={cases}")
    return EXIT_OK


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = ContractArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    lint_parser = commands.add_parser("lint", help="validate the registry and fixture bindings")
    lint_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    run_parser = commands.add_parser("run", help="run adapters assigned to one exact stage")
    run_parser.add_argument("--stage", choices=sorted(STAGES), required=True)
    run_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    commands.add_parser("selftest", help="run isolated validator and execution tests")
    return parser.parse_args(argv)


def _registry_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.command == "selftest":
        return selftest()

    registry_path = _registry_path(args.registry)
    if not registry_path.is_file():
        print(
            f"semantic-contracts: FAIL command={args.command} phase=infrastructure "
            f"detail=registry does not exist: {registry_path}",
            file=sys.stderr,
        )
        return EXIT_INFRASTRUCTURE
    try:
        data, summary = load_registry(registry_path, ROOT)
    except RegistryError as exc:
        print(f"semantic-contracts: FAIL command={args.command} phase=lint detail={exc}", file=sys.stderr)
        return EXIT_LINT

    if args.command == "lint":
        print(
            "semantic-contracts: PASS command=lint "
            f"engines={summary['engines']} contracts={summary['contracts']} "
            f"adapters={summary['adapters']}"
        )
        return EXIT_OK

    try:
        count = run_stage(data, ROOT, args.stage)
    except AdapterLaunchError as exc:
        print(
            "semantic-contracts: FAIL command=run phase=infrastructure "
            f"stage={args.stage} contract={exc.contract_id} adapter={exc.adapter_id} detail={exc}",
            file=sys.stderr,
        )
        return EXIT_INFRASTRUCTURE
    except AdapterError as exc:
        print(
            "semantic-contracts: FAIL command=run "
            f"stage={args.stage} contract={exc.contract_id} adapter={exc.adapter_id} detail={exc}",
            file=sys.stderr,
        )
        return EXIT_ADAPTER
    if count == 0:
        has_product_claim = any("product" in contract["claims"] for contract in data["contracts"])
        if args.stage == "G2" and not has_product_claim:
            print(
                "semantic-contracts: SKIP command=run stage=G2 "
                "reason=no-product-claims adapters=0"
            )
            return EXIT_OK
        print(
            f"semantic-contracts: FAIL command=run stage={args.stage} detail=no adapters configured",
            file=sys.stderr,
        )
        return EXIT_LINT
    print(f"semantic-contracts: PASS command=run stage={args.stage} adapters={count}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
