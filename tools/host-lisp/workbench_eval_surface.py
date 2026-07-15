#!/usr/bin/env python3
"""Verify the shipped Workbench eval surface and its build bindings."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import workbench_ship as Ship  # noqa: E402


FORMAT = "lisp65-workbench-eval-surface-v1"
DEFAULT_FIXTURE = ROOT / "tests" / "bytecode" / "runtime" / "workbench-eval-surface.json"
DEFAULT_SHIP_DIR = ROOT / "build" / "ship-candidate"
ROOT_KEYS = {
    "format",
    "product",
    "profile",
    "ship_manifest_format",
    "bound_inputs",
    "route",
    "resolved_profile",
    "native_symbols",
    "stdlib",
}
ROUTE_KEYS = {"entry", "compiler", "installer", "executor"}
PROFILE_KEYS = {"required_flags", "forbidden_flags"}
NATIVE_SYMBOL_KEYS = {"required", "forbidden"}
STDLIB_KEYS = {
    "suite",
    "required_sources",
    "required_functions",
    "forbidden_functions",
    "required_entry_literals",
}
CANONICAL_ROUTE = {
    "entry": "TREEWALK_STRIP",
    "compiler": "lcc-run",
    "installer": "lcc-install",
    "executor": "P0-VM",
}
CANONICAL_PROFILE_BINDINGS = {
    "product_elf": "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay-linked.prg.elf",
    "eval_surface_contract": FORMAT,
    "eval_surface_fixture": "tests/bytecode/runtime/workbench-eval-surface.json",
    "eval_route": "internal-eval:treewalk-strip:lcc-run:p0-vm",
    "eval_forbidden_public_functions": "eval,eval-string",
}
CANONICAL_BOUND_INPUTS = [
    "config/semantic-contracts.json",
    "tests/bytecode/runtime/workbench-eval-surface.json",
    "tools/host-lisp/semantic_contracts.py",
    "tools/host-lisp/workbench_eval_surface.py",
]
CANONICAL_REQUIRED_SYMBOLS = {
    "eval", "eval_init", "lcc_enter", "lcc_install_phase_00", "vm_run", "vm_run_dir"
}
CANONICAL_FORBIDDEN_SYMBOLS = {
    "eval_env", "eval_string", "workbench_boot_name_eval", "workbench_boot_name_eval_string"
}
CANONICAL_STDLIB = {
    "suite": "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json",
    "required_sources": ["lib/lcc.lisp"],
    "required_functions": ["lcc-compile-obj", "lcc-run"],
    "forbidden_functions": ["eval", "eval-string"],
    "required_entry_literals": {"lcc-run": ["lcc-compile-obj", "lcc-install"]},
}
DEFAULT_NM = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"


class SurfaceError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise SurfaceError("duplicate JSON key: %s" % key)
        out[key] = value
    return out


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except SurfaceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SurfaceError("cannot read %s %s: %s" % (label, path, exc)) from exc
    if not isinstance(data, dict):
        raise SurfaceError("%s must be a JSON object" % label)
    return data


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SurfaceError("%s must be an object" % label)
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise SurfaceError(
            "%s keys differ: missing=%s extra=%s"
            % (label, ",".join(missing) or "-", ",".join(extra) or "-")
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SurfaceError("%s must be a non-empty string" % label)
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise SurfaceError("%s must be an array" % label)
    out = [_text(item, "%s[%d]" % (label, index)) for index, item in enumerate(value)]
    if len(out) != len(set(out)):
        raise SurfaceError("%s contains duplicates" % label)
    return out


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    _exact(fixture, ROOT_KEYS, "fixture")
    if fixture["format"] != FORMAT:
        raise SurfaceError("unexpected fixture format")
    for key in ("product", "profile", "ship_manifest_format"):
        _text(fixture[key], "fixture.%s" % key)
    bound_inputs = _strings(fixture["bound_inputs"], "fixture.bound_inputs")
    if bound_inputs != CANONICAL_BOUND_INPUTS:
        raise SurfaceError("fixture.bound_inputs differs from the approved surface")
    route = _exact(fixture["route"], ROUTE_KEYS, "fixture.route")
    if route != CANONICAL_ROUTE:
        raise SurfaceError("fixture.route must describe TREEWALK_STRIP -> lcc-run -> P0-VM")
    profile = _exact(
        fixture["resolved_profile"], PROFILE_KEYS, "fixture.resolved_profile"
    )
    required_flags = _strings(profile["required_flags"], "required_flags")
    forbidden_flags = _strings(profile["forbidden_flags"], "forbidden_flags")
    overlap = sorted(set(required_flags) & set(forbidden_flags))
    if overlap:
        raise SurfaceError("profile flags are both required and forbidden: %s" % ", ".join(overlap))
    native = _exact(fixture["native_symbols"], NATIVE_SYMBOL_KEYS, "fixture.native_symbols")
    required_symbols = _strings(native["required"], "native_symbols.required")
    forbidden_symbols = _strings(native["forbidden"], "native_symbols.forbidden")
    overlap = sorted(set(required_symbols) & set(forbidden_symbols))
    if overlap:
        raise SurfaceError("native symbols are both required and forbidden: %s" % ", ".join(overlap))
    if set(required_symbols) != CANONICAL_REQUIRED_SYMBOLS:
        raise SurfaceError("required native symbols differ from the approved surface")
    if set(forbidden_symbols) != CANONICAL_FORBIDDEN_SYMBOLS:
        raise SurfaceError("forbidden native symbols differ from the approved surface")
    stdlib = _exact(fixture["stdlib"], STDLIB_KEYS, "fixture.stdlib")
    _text(stdlib["suite"], "fixture.stdlib.suite")
    for key in ("required_sources", "required_functions", "forbidden_functions"):
        _strings(stdlib[key], "fixture.stdlib.%s" % key)
    literal_map = stdlib["required_entry_literals"]
    if not isinstance(literal_map, dict) or not literal_map:
        raise SurfaceError("required_entry_literals must be a non-empty object")
    for entry, literals in literal_map.items():
        _text(entry, "required_entry_literals entry")
        _strings(literals, "required_entry_literals.%s" % entry)
    if stdlib != CANONICAL_STDLIB:
        raise SurfaceError("fixture.stdlib differs from the approved surface")
    return fixture


def _profile_values(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key, []).append(value)
    return values


def _one(values: dict[str, list[str]], key: str) -> str:
    found = values.get(key, [])
    if len(found) != 1:
        raise SurfaceError("resolved profile needs exactly one %s line" % key)
    return found[0]


def _artifact(manifest: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise SurfaceError("ship artifacts must be an array")
    found = [item for item in artifacts if isinstance(item, dict) and item.get("id") == artifact_id]
    if len(found) != 1:
        raise SurfaceError("ship needs exactly one %s artifact" % artifact_id)
    return found[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root_path(value: str, label: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise SurfaceError("%s escapes the repository: %s" % (label, value)) from exc
    return path


def _native_symbols(nm_path: Path, elf_path: Path) -> set[str]:
    try:
        result = subprocess.run(
            [str(nm_path), "--defined-only", str(elf_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise SurfaceError("cannot run llvm-nm: %s" % exc) from exc
    if result.returncode != 0:
        raise SurfaceError("llvm-nm failed: %s" % (result.stderr.strip() or result.returncode))
    return {line.split()[-1] for line in result.stdout.splitlines() if line.split()}


def _check_elf_binding(ship_manifest: dict[str, Any], actual_sha256: str) -> None:
    runtime_overlays = ship_manifest.get("runtime_overlays")
    elf = runtime_overlays.get("elf") if isinstance(runtime_overlays, dict) else None
    expected = elf.get("sha256") if isinstance(elf, dict) else None
    if not isinstance(expected, str) or len(expected) != 64:
        raise SurfaceError("Ship-v5 runtime overlay ELF hash is missing or malformed")
    if expected != actual_sha256:
        raise SurfaceError("final Workbench ELF hash does not match Ship-v5")


def check_surface(
    fixture: dict[str, Any],
    ship_manifest: dict[str, Any],
    stdlib_manifest: dict[str, Any],
    profile_text: str,
    native_symbols: set[str],
) -> None:
    validate_fixture(fixture)
    for key in ("product", "profile"):
        if ship_manifest.get(key) != fixture[key]:
            raise SurfaceError("ship %s does not match the surface contract" % key)
    if ship_manifest.get("manifest_format") != fixture["ship_manifest_format"]:
        raise SurfaceError("ship manifest format does not match the surface contract")

    values = _profile_values(profile_text)
    if _one(values, "profile") != fixture["profile"]:
        raise SurfaceError("resolved profile name does not match the surface contract")
    for key, expected in CANONICAL_PROFILE_BINDINGS.items():
        if _one(values, key) != expected:
            raise SurfaceError("resolved profile %s does not match the surface contract" % key)
    fixture_path = _root_path(CANONICAL_PROFILE_BINDINGS["eval_surface_fixture"], "eval fixture")
    if _one(values, "eval_surface_fixture_sha256") != _sha256(fixture_path):
        raise SurfaceError("resolved profile eval fixture hash does not match")
    input_pins = values.get("input_sha256", [])
    for source in fixture["bound_inputs"]:
        path = _root_path(source, "bound input")
        expected = "%s:%s" % (source, _sha256(path))
        if input_pins.count(expected) != 1:
            raise SurfaceError("resolved profile needs exactly one bound input pin for %s" % source)
    flags = set(shlex.split(_one(values, "extra_cflags")))
    profile_contract = fixture["resolved_profile"]
    missing_flags = sorted(set(profile_contract["required_flags"]) - flags)
    forbidden_flags = sorted(set(profile_contract["forbidden_flags"]) & flags)
    if missing_flags:
        raise SurfaceError("resolved profile is missing flags: %s" % ", ".join(missing_flags))
    if forbidden_flags:
        raise SurfaceError("resolved profile enables forbidden flags: %s" % ", ".join(forbidden_flags))

    symbol_contract = fixture["native_symbols"]
    missing_symbols = sorted(set(symbol_contract["required"]) - native_symbols)
    forbidden_symbols = sorted(set(symbol_contract["forbidden"]) & native_symbols)
    if missing_symbols:
        raise SurfaceError("final Workbench ELF is missing symbols: %s" % ", ".join(missing_symbols))
    if forbidden_symbols:
        raise SurfaceError("final Workbench ELF contains forbidden symbols: %s" % ", ".join(forbidden_symbols))

    if stdlib_manifest.get("format") != "lisp65-bytecode-p0-stdlib-artifacts-v1":
        raise SurfaceError("shipped stdlib is not a P0 artifact")
    if stdlib_manifest.get("artifact_role") != "stdlib":
        raise SurfaceError("shipped P0 artifact is not the stdlib")
    stdlib_contract = fixture["stdlib"]
    if stdlib_manifest.get("suite") != stdlib_contract["suite"]:
        raise SurfaceError("shipped stdlib suite does not match the surface contract")
    sources = set(_strings(stdlib_manifest.get("sources"), "stdlib.sources"))
    functions = set(_strings(stdlib_manifest.get("functions"), "stdlib.functions"))
    entries_raw = stdlib_manifest.get("entries")
    if not isinstance(entries_raw, list):
        raise SurfaceError("stdlib.entries must be an array")
    entries = {
        item.get("name"): item
        for item in entries_raw
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    entry_names = set(entries)
    missing_sources = sorted(set(stdlib_contract["required_sources"]) - sources)
    missing_functions = sorted(set(stdlib_contract["required_functions"]) - functions)
    forbidden_exports = sorted(
        set(stdlib_contract["forbidden_functions"]) & (functions | entry_names)
    )
    if missing_sources:
        raise SurfaceError("stdlib is missing sources: %s" % ", ".join(missing_sources))
    if missing_functions:
        raise SurfaceError("stdlib is missing functions: %s" % ", ".join(missing_functions))
    if forbidden_exports:
        raise SurfaceError("stdlib exports forbidden functions: %s" % ", ".join(forbidden_exports))
    for name, required_literals in stdlib_contract["required_entry_literals"].items():
        entry = entries.get(name)
        if not isinstance(entry, dict):
            raise SurfaceError("stdlib is missing entry metadata for %s" % name)
        if entry.get("kind") != "function":
            raise SurfaceError("stdlib entry %s is not a P0 function" % name)
        literals = entry.get("literals")
        if not isinstance(literals, list):
            raise SurfaceError("stdlib entry %s has no literal metadata" % name)
        symbols = {
            literal["symbol"]
            for literal in literals
            if isinstance(literal, dict) and isinstance(literal.get("symbol"), str)
        }
        missing = sorted(set(required_literals) - symbols)
        if missing:
            raise SurfaceError("stdlib entry %s is missing literals: %s" % (name, ", ".join(missing)))

    trust = ship_manifest.get("stdlib_trust")
    semantic_gate = trust.get("semantic_gate") if isinstance(trust, dict) else None
    if not isinstance(semantic_gate, dict) or semantic_gate.get("result") != "pass":
        raise SurfaceError("ship stdlib semantic gate is not pass")


def check_package(fixture_path: Path, ship_dir: Path) -> None:
    fixture = validate_fixture(_load_json(fixture_path, "surface fixture"))
    errors = Ship.verify_package(
        ship_dir, strict=False, expected_format=fixture["ship_manifest_format"]
    )
    if errors:
        raise SurfaceError("Ship-v5 verification failed: " + "; ".join(errors))
    ship_manifest_path = ship_dir / "manifest.json"
    ship_manifest = _load_json(ship_manifest_path, "ship manifest")
    profile_record = _artifact(ship_manifest, "resolved-profile")
    stdlib_record = _artifact(ship_manifest, "stdlib-artifact-manifest")
    profile_path = ship_dir / _text(profile_record.get("path"), "resolved-profile.path")
    stdlib_path = ship_dir / _text(stdlib_record.get("path"), "stdlib manifest path")
    for path, record, label in (
        (profile_path, profile_record, "resolved profile"),
        (stdlib_path, stdlib_record, "stdlib manifest"),
    ):
        if not path.is_file() or _sha256(path) != record.get("sha256"):
            raise SurfaceError("%s artifact hash does not match Ship-v5" % label)
    try:
        profile_text = profile_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise SurfaceError("cannot read resolved profile: %s" % exc) from exc
    stdlib_manifest = _load_json(stdlib_path, "stdlib manifest")
    values = _profile_values(profile_text)
    elf_path = _root_path(_one(values, "product_elf"), "product ELF")
    if not elf_path.is_file():
        raise SurfaceError("final Workbench ELF is missing: %s" % elf_path)
    _check_elf_binding(ship_manifest, _sha256(elf_path))
    check_surface(
        fixture,
        ship_manifest,
        stdlib_manifest,
        profile_text,
        _native_symbols(DEFAULT_NM, elf_path),
    )


def selftest() -> int:
    fixture = _load_json(DEFAULT_FIXTURE, "surface fixture")
    validate_fixture(fixture)
    ship_manifest = {
        "manifest_format": fixture["ship_manifest_format"],
        "product": fixture["product"],
        "profile": fixture["profile"],
        "stdlib_trust": {"semantic_gate": {"result": "pass"}},
        "runtime_overlays": {"elf": {"sha256": "a" * 64}},
    }
    stdlib = {
        "format": "lisp65-bytecode-p0-stdlib-artifacts-v1",
        "artifact_role": "stdlib",
        "suite": fixture["stdlib"]["suite"],
        "sources": list(fixture["stdlib"]["required_sources"]),
        "functions": list(fixture["stdlib"]["required_functions"]),
        "entries": [
            {
                "name": "lcc-run",
                "kind": "function",
                "literals": [
                    {"symbol": name}
                    for name in fixture["stdlib"]["required_entry_literals"]["lcc-run"]
                ],
            }
        ],
    }
    profile_lines = [
        "profile=%s" % fixture["profile"],
        "extra_cflags=%s" % " ".join(fixture["resolved_profile"]["required_flags"]),
    ]
    profile_lines.extend("%s=%s" % item for item in CANONICAL_PROFILE_BINDINGS.items())
    profile_lines.append("eval_surface_fixture_sha256=%s" % _sha256(DEFAULT_FIXTURE))
    profile_lines.extend(
        "input_sha256=%s:%s" % (source, _sha256(_root_path(source, "bound input")))
        for source in fixture["bound_inputs"]
    )
    profile = "\n".join(profile_lines) + "\n"
    symbols = set(fixture["native_symbols"]["required"])
    check_surface(fixture, ship_manifest, stdlib, profile, symbols)

    mutations: list[tuple[str, Any, str]] = []

    def add(label: str, mutate: Any, needle: str) -> None:
        mutations.append((label, mutate, needle))

    add("route", lambda f, s, m, p: f["route"].update({"executor": "treewalk"}), "route")
    add("profile", lambda f, s, m, p: s.update({"profile": "wrong"}), "profile")
    add("missing-flag", lambda f, s, m, p: p.pop(), "missing flags")
    add("forbidden-flag", lambda f, s, m, p: p.append("-DLISP65_EVAL_PRIMS"), "forbidden flags")
    add("missing-source", lambda f, s, m, p: m.update({"sources": []}), "missing sources")
    add("missing-function", lambda f, s, m, p: m.update({"functions": ["lcc-run"]}), "missing functions")
    add("forbidden-export", lambda f, s, m, p: m["functions"].append("eval"), "forbidden functions")
    add(
        "forbidden-entry",
        lambda f, s, m, p: m["entries"].append({"name": "eval-string", "kind": "function"}),
        "forbidden functions",
    )
    add("entry-kind", lambda f, s, m, p: m["entries"][0].update({"kind": "data"}), "not a P0 function")
    add(
        "missing-compile-literal",
        lambda f, s, m, p: m["entries"][0].update(
            {"literals": [{"symbol": "lcc-install"}]}
        ),
        "missing literals",
    )
    add(
        "missing-install-literal",
        lambda f, s, m, p: m["entries"][0].update(
            {"literals": [{"symbol": "lcc-compile-obj"}]}
        ),
        "missing literals",
    )
    add("gate", lambda f, s, m, p: s["stdlib_trust"]["semantic_gate"].update({"result": "fail"}), "not pass")

    for label, mutate, needle in mutations:
        f = copy.deepcopy(fixture)
        s = copy.deepcopy(ship_manifest)
        m = copy.deepcopy(stdlib)
        flags = list(fixture["resolved_profile"]["required_flags"])
        mutate(f, s, m, flags)
        mutated_profile = "profile=%s\nextra_cflags=%s\n" % (
            fixture["profile"], " ".join(flags)
        )
        mutated_profile = profile.replace(
            "extra_cflags=%s" % " ".join(fixture["resolved_profile"]["required_flags"]),
            "extra_cflags=%s" % " ".join(flags),
        )
        mutated_symbols = set(symbols)
        try:
            check_surface(f, s, m, mutated_profile, mutated_symbols)
        except SurfaceError as exc:
            if needle not in str(exc):
                raise SurfaceError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
        else:
            raise SurfaceError("selftest mutation passed: %s" % label)

    def expect_failure(label: str, changed_profile: str, changed_symbols: set[str], needle: str) -> None:
        nonlocal mutations
        mutations.append((label, None, needle))
        try:
            check_surface(fixture, ship_manifest, stdlib, changed_profile, changed_symbols)
        except SurfaceError as exc:
            if needle not in str(exc):
                raise SurfaceError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
        else:
            raise SurfaceError("selftest mutation passed: %s" % label)

    missing_vm = set(symbols)
    missing_vm.remove("vm_run")
    expect_failure("missing-native-symbol", profile, missing_vm, "missing symbols")
    forbidden_native = set(symbols)
    forbidden_native.add("eval_env")
    expect_failure("forbidden-native-symbol", profile, forbidden_native, "forbidden symbols")
    fixture_pin = "input_sha256=%s:%s\n" % (
        CANONICAL_PROFILE_BINDINGS["eval_surface_fixture"],
        _sha256(DEFAULT_FIXTURE),
    )
    expect_failure("missing-input-pin", profile.replace(fixture_pin, ""), symbols, "bound input pin")
    expect_failure(
        "fixture-hash",
        profile.replace(_sha256(DEFAULT_FIXTURE), "0" * 64, 1),
        symbols,
        "fixture hash",
    )
    expect_failure(
        "route-binding",
        profile.replace(CANONICAL_PROFILE_BINDINGS["eval_route"], "internal-eval:treewalk"),
        symbols,
        "eval_route",
    )
    _check_elf_binding(ship_manifest, "a" * 64)
    mutations.append(("elf-hash", None, "ELF hash"))
    try:
        _check_elf_binding(ship_manifest, "b" * 64)
    except SurfaceError as exc:
        if "ELF hash" not in str(exc):
            raise SurfaceError("selftest elf-hash failed for wrong reason: %s" % exc) from exc
    else:
        raise SurfaceError("selftest mutation passed: elf-hash")

    duplicate = '{"format":"%s","format":"%s"}' % (FORMAT, FORMAT)
    try:
        json.loads(duplicate, object_pairs_hook=_strict_object)
    except SurfaceError:
        pass
    else:
        raise SurfaceError("selftest duplicate JSON key passed")
    print("workbench-eval-surface selftest: PASS mutations=%d" % (len(mutations) + 1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--ship-dir", type=Path, default=DEFAULT_SHIP_DIR)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        check_package(args.fixture, args.ship_dir)
    except (OSError, SurfaceError, ValueError) as exc:
        print("workbench-eval-surface: FAIL: %s" % exc, file=sys.stderr)
        return 1
    print("workbench-eval-surface: PASS route=TREEWALK_STRIP->lcc-run->P0-VM claim=surface-binding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
