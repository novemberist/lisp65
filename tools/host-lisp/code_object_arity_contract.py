#!/usr/bin/env python3
"""Validate and report the P0 CodeObject STRICT_ARITY flag contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))
import bytecode_p0 as P0  # noqa: E402
import bytecode_p0_compiler as P0C  # noqa: E402


DEFAULT_CONTRACT = ROOT / "config" / "code-object-arity-contract.json"
DEFAULT_OUT = ROOT / "build" / "code-object-arity-report.txt"
DEFAULT_CC = ROOT / "tools" / "llvm-mos" / "bin" / "mos-mega65-clang"
DEFAULT_NM = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise ContractError(f"{label} keys drift: missing={missing} extra={extra}")
    return value


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"contract must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read contract: {exc}") from exc
    top = _exact(
        value,
        {
            "format", "version", "header", "flags", "semantics", "profiles",
            "flag_spaces", "consumers", "cost_gate",
        },
        "contract",
    )
    if top["format"] != "lisp65-code-object-arity-contract-v1" or top["version"] != 1:
        raise ContractError("contract identity drift")
    return top


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ContractError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a non-empty string")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.resolve().read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractError(f"cannot hash {path}: {exc}") from exc


def _contract_values(contract: dict[str, Any]) -> dict[str, int]:
    header = _exact(contract["header"], {"flags_offset", "flags_width_bits"}, "header")
    flags = _exact(contract["flags"], {"rest", "strict_arity", "optional_count"}, "flags")
    rest = _exact(flags["rest"], {"mask", "requires_local_slot"}, "flags.rest")
    strict = _exact(flags["strict_arity"], {"mask"}, "flags.strict_arity")
    optional = _exact(
        flags["optional_count"],
        {
            "mask", "shift", "width_bits", "maximum", "requires_strict_arity",
            "must_not_exceed_nargs",
        },
        "flags.optional_count",
    )
    values = {
        "offset": _integer(header["flags_offset"], "header.flags_offset", 0, 255),
        "width": _integer(header["flags_width_bits"], "header.flags_width_bits", 1, 8),
        "rest": _integer(rest["mask"], "flags.rest.mask", 0, 255),
        "strict": _integer(strict["mask"], "flags.strict_arity.mask", 0, 255),
        "optional_mask": _integer(optional["mask"], "flags.optional_count.mask", 0, 255),
        "optional_shift": _integer(optional["shift"], "flags.optional_count.shift", 0, 7),
        "optional_width": _integer(optional["width_bits"], "flags.optional_count.width_bits", 1, 8),
        "optional_max": _integer(optional["maximum"], "flags.optional_count.maximum", 0, 255),
    }
    if rest["requires_local_slot"] is not True:
        raise ContractError("REST must require a local slot")
    if optional["requires_strict_arity"] is not True or optional["must_not_exceed_nargs"] is not True:
        raise ContractError("optional count guards must be enabled")
    if values != {
        "offset": 3,
        "width": 8,
        "rest": 0x01,
        "strict": 0x02,
        "optional_mask": 0xFC,
        "optional_shift": 2,
        "optional_width": 6,
        "optional_max": 63,
    }:
        raise ContractError(f"frozen flag layout drift: {values}")
    if values["rest"] & values["strict"] or (
        values["rest"] | values["strict"] | values["optional_mask"]
    ) != 0xFF:
        raise ContractError("CodeObject flag fields must partition the complete byte")
    return values


def _shape_error(nargs: int, nlocals: int, flags: int, values: dict[str, int]) -> str | None:
    optional = (flags & values["optional_mask"]) >> values["optional_shift"]
    if optional and not flags & values["strict"]:
        return "optional-without-strict-arity"
    if optional > nargs:
        return "optional-count-exceeds-nargs"
    if flags & values["rest"] and nlocals == 0:
        return "variadic-without-rest-local"
    return None


def _accepts(actual: int, nargs: int, flags: int, values: dict[str, int]) -> bool:
    optional = (flags & values["optional_mask"]) >> values["optional_shift"]
    if not flags & values["strict"]:
        return True
    minimum = nargs - optional
    return actual >= minimum and (bool(flags & values["rest"]) or actual <= nargs)


def _semantic_counts(values: dict[str, int]) -> dict[str, int]:
    shapes = 0
    malformed = 0
    accepted = 0
    rejected = 0
    for flags in range(256):
        for nargs in range(256):
            nlocals = 1 if flags & values["rest"] else 0
            if _shape_error(nargs, nlocals, flags, values):
                malformed += 1
                continue
            shapes += 1
            optional = (flags & values["optional_mask"]) >> values["optional_shift"]
            minimum = nargs - optional if flags & values["strict"] else 0
            for actual in {0, minimum, nargs, 255}:
                if _accepts(actual, nargs, flags, values):
                    accepted += 1
                else:
                    rejected += 1
    return {
        "valid_shapes": shapes,
        "malformed_shapes": malformed,
        "sampled_accepts": accepted,
        "sampled_rejects": rejected,
    }


def _macro(text: str, name: str) -> int:
    match = re.search(rf"^#define\s+{re.escape(name)}\s+(0x[0-9a-fA-F]+|[0-9]+)u?\s*$", text, re.M)
    if not match:
        raise ContractError(f"cannot resolve {name} in src/vm.h")
    return int(match.group(1), 0)


def _require(path: str, tokens: tuple[str, ...]) -> str:
    full = ROOT / path
    try:
        text = full.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    missing = [token for token in tokens if token not in text]
    if missing:
        raise ContractError(f"{path} lacks STRICT_ARITY contract markers: {missing}")
    return text


def _lcc_finish(path: str) -> tuple[list[Any], int]:
    text = _require(path, ("%lcc-finish",))
    try:
        forms = P0C.parse_all(text)
    except Exception as exc:
        raise ContractError(f"cannot parse {path}: {exc}") from exc
    matches = [
        form for form in forms
        if isinstance(form, list) and len(form) >= 4
        and form[0] == "defun" and form[1] == "%lcc-finish"
    ]
    if len(matches) != 1:
        raise ContractError(f"{path} must define %lcc-finish exactly once")
    form = matches[0]
    try:
        flags = form[3][2][2][1]
    except (IndexError, TypeError) as exc:
        raise ContractError(f"{path} %lcc-finish shape drift") from exc
    if not isinstance(flags, int):
        raise ContractError(f"{path} %lcc-finish flags must be an integer")
    return form, flags


def _symbols(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_symbols(item))
        return result
    return set()


def _audit_emitters(values: dict[str, int]) -> dict[str, int]:
    _require(
        "src/compile.c",
        ("&optional", "CO_FLAG_OPTIONAL_SHIFT", "optional > 63u"),
    )
    _require(
        "src/eval.c",
        ("sf_optional", "optional > 63u", "tree_arity_accepts"),
    )
    _require(
        "tools/host-lisp/bytecode_p0_compiler.py",
        ("optional_count", "CO_FLAG_OPTIONAL_SHIFT", "&optional requires dialect-v2 strict arity"),
    )
    source = "(defun f (x &rest xs) (lambda (y &rest ys) y))"
    form = P0C.parse_one(source)
    legacy_heap = P0.Heap()
    explicit_heap = P0.Heap()
    strict_heap = P0.Heap()
    _, legacy, legacy_helpers = P0C.compile_top_form_with_helpers(form, legacy_heap)
    _, explicit, explicit_helpers = P0C.compile_top_form_with_helpers(
        form, explicit_heap, strict_arity=False
    )
    _, strict, strict_helpers = P0C.compile_top_form_with_helpers(
        form, strict_heap, strict_arity=True
    )
    if legacy.encode() != explicit.encode() or [code.encode() for _, code in legacy_helpers] != [
        code.encode() for _, code in explicit_helpers
    ]:
        raise ContractError("Python compiler default no longer preserves v1 byte output")
    if legacy.flags != values["rest"] or any(
        code.flags != values["rest"] for _, code in legacy_helpers
    ):
        raise ContractError("Python compiler v1 REST flags drift")
    if strict.flags != values["rest"] | values["strict"] or any(
        code.flags != values["rest"] | values["strict"] for _, code in strict_helpers
    ):
        raise ContractError("Python compiler does not propagate STRICT_ARITY to helpers")
    if (
        legacy.nargs != strict.nargs
        or legacy.nlocals != strict.nlocals
        or legacy.littab != strict.littab
        or legacy.payload != strict.payload
    ):
        raise ContractError("Python STRICT_ARITY changed fields outside CodeObject.flags")

    v1_form, v1_flags = _lcc_finish("lib/lcc.lisp")
    profile_path = "lib/dialect-v2/lcc-profile.lisp"
    profile_text = _require(profile_path, ("Dialect-v2 emitter profile",))
    try:
        profile_forms = P0C.parse_all(profile_text)
    except Exception as exc:
        raise ContractError(f"cannot parse {profile_path}: {exc}") from exc
    profile_by_name = {
        form[1]: form for form in profile_forms
        if isinstance(form, list) and len(form) >= 4 and form[0] == "defun"
    }
    surface_overrides = {
        "%lcc-finish", "%lcc-do-p", "%lcc-expr-ops2", "%lcc-sf-p",
        "%lcc-opform-p", "%lcc-prim", "%lcc-v2-prim2", "%lcc-v2-prim3",
        "%lcc-v2-prim4",
    }
    arity_overrides = {
        "%lcc-imm-binds", "%lcc-compile-defun", "%lcc-compile-lambda",
        "%lcc-lambda",
    }
    arity_helpers = {
        "%lcc-v2-param-p", "%lcc-v2-param-seen-p", "%lcc-v2-param-error",
        "%lcc-v2-param-optional", "%lcc-v2-param-rest", "%lcc-v2-param-add",
        "%lcc-v2-param-step", "%lcc-v2-params-walk", "%lcc-v2-params", "%lcc-v2-nargs",
        "%lcc-v2-optional", "%lcc-v2-rest", "%lcc-v2-max0", "%lcc-v2-env",
        "%lcc-v2-finish", "%lcc-v2-fixed-binds", "%lcc-v2-drop",
        "%lcc-v2-imm-binds",
    }
    expected_definitions = surface_overrides | arity_overrides | arity_helpers
    if (
        set(profile_by_name) != expected_definitions
        or len(profile_forms) != len(expected_definitions)
    ):
        raise ContractError(
            "v2 LCC profile definition inventory drift: "
            f"{sorted(profile_by_name)}"
        )
    v2_form = profile_by_name["%lcc-finish"]
    try:
        v2_flags = v2_form[3][2][2][1]
    except (IndexError, TypeError) as exc:
        raise ContractError("v2 LCC %lcc-finish shape drift") from exc
    if v1_flags != 0 or v2_flags != values["strict"]:
        raise ContractError(f"LCC profile flags drift: v1={v1_flags} v2={v2_flags}")
    v2_normalized = json.loads(json.dumps(v2_form))
    v2_normalized[3][2][2][1] = 0
    if v2_normalized != v1_form:
        raise ContractError("v2 LCC profile must replace only %lcc-finish flags")
    forbidden_by_override = {
        "%lcc-do-p": {"do", "do*"},
        "%lcc-expr-ops2": {"remainder"},
        "%lcc-sf-p": {"do", "do*"},
        "%lcc-opform-p": {"remainder"},
    }
    for name, forbidden in forbidden_by_override.items():
        leaked = _symbols(profile_by_name[name]) & forbidden
        if leaked:
            raise ContractError(f"v2 LCC override {name} retains removed names: {sorted(leaked)}")
    parser_symbols = _symbols(profile_by_name["%lcc-v2-param-step"])
    parser_guard_symbols = set().union(*(
        _symbols(profile_by_name[name])
        for name in (
            "%lcc-v2-param-optional", "%lcc-v2-param-rest", "%lcc-v2-param-add",
        )
    ))
    if (
        not {"&optional", "&rest"} <= parser_symbols
        or "%lcc-v2-param-error" not in parser_guard_symbols
    ):
        raise ContractError("v2 LCC parameter grammar markers/guard drift")
    finish_symbols = _symbols(profile_by_name["%lcc-v2-finish"])
    if not {"%lcc-v2-nargs", "%lcc-v2-optional", "%lcc-v2-rest"} <= finish_symbols:
        raise ContractError("v2 LCC optional/rest flag lowering drift")
    for name in arity_overrides:
        if "%lcc-v2-params" not in _symbols(profile_by_name[name]):
            raise ContractError(f"v2 LCC arity override bypasses parameter parser: {name}")
    return {
        "host_v1_main_flags": legacy.flags,
        "host_v1_helper_flags": legacy_helpers[0][1].flags,
        "host_v2_main_flags": strict.flags,
        "host_v2_helper_flags": strict_helpers[0][1].flags,
        "lcc_v1_finish_flags": v1_flags,
        "lcc_v2_finish_flags": v2_flags,
        "lcc_v2_surface_overrides": len(surface_overrides) - 1,
        "lcc_v2_arity_overrides": len(arity_overrides),
        "lcc_v2_arity_helpers": len(arity_helpers),
    }


def _audit_sources(values: dict[str, int], contract: dict[str, Any]) -> tuple[int, dict[str, int]]:
    vm_h = _require(
        "src/vm.h",
        ("CO_FLAG_REST", "CO_FLAG_STRICT_ARITY", "CO_FLAG_OPTIONAL_SHIFT", "CO_FLAG_OPTIONAL_MASK"),
    )
    native = {
        "offset": _macro(vm_h, "CO_OFF_FLAGS"),
        "rest": _macro(vm_h, "CO_FLAG_REST"),
        "strict": _macro(vm_h, "CO_FLAG_STRICT_ARITY"),
        "optional_shift": _macro(vm_h, "CO_FLAG_OPTIONAL_SHIFT"),
        "optional_mask": _macro(vm_h, "CO_FLAG_OPTIONAL_MASK"),
    }
    for key, value in native.items():
        if value != values[key]:
            raise ContractError(f"src/vm.h {key} drift: {value} != {values[key]}")

    p0 = _require(
        "tools/host-lisp/bytecode_p0.py",
        ("CO_FLAG_REST = 0x01", "CO_FLAG_STRICT_ARITY = 0x02", "CO_FLAG_OPTIONAL_SHIFT = 2", "ArityError"),
    )
    del p0
    vm_c = _require(
        "src/vm.c",
        ("vm_arity_accepts", "CO_OPTIONAL_COUNT(flags)", "CO_FLAG_STRICT_ARITY", "CO_FLAG_REST"),
    )
    call_sites = len(re.findall(r"\bvm_arity_accepts\s*\(", vm_c)) - 1
    if call_sites != contract["cost_gate"]["native_static_call_sites"]:
        raise ContractError(f"native arity call-site drift: {call_sites}, expected 2")

    _require(
        "tools/host-lisp/l65m_contract.py",
        ("optional-without-strict-arity", "optional-count-exceeds-nargs", "variadic-without-rest-local"),
    )
    _require(
        "src/l65m_validate.c",
        ("CO_FLAG_STRICT_ARITY", "CO_OPTIONAL_COUNT", "CO_FLAG_REST"),
    )
    _require(
        "src/lcc_install_overlay.c",
        ("CO_FLAG_STRICT_ARITY", "CO_OPTIONAL_COUNT", "CO_FLAG_REST"),
    )
    _require(
        "src/compile.c",
        ("CC_PROFILE_FLAGS CO_FLAG_STRICT_ARITY", "cc->flags |= CO_FLAG_REST"),
    )
    emitter_report = _audit_emitters(values)

    docs = _require(
        "docs/archive/pre-1.0/contracts/bytecode-abi.md",
        ("STRICT_ARITY", "optional_count", "Directory-Entry-Flags"),
    )
    del docs

    consumers = contract["consumers"]
    if not isinstance(consumers, list) or not consumers:
        raise ContractError("consumers must be a non-empty list")
    seen: set[str] = set()
    for index, raw in enumerate(consumers):
        item = _exact(raw, {"path", "role"}, f"consumers[{index}]")
        path = _string(item["path"], f"consumers[{index}].path")
        _string(item["role"], f"consumers[{index}].role")
        if path in seen or not (ROOT / path).is_file():
            raise ContractError(f"consumer inventory duplicate/missing: {path}")
        seen.add(path)
    return call_sites, emitter_report


def _probe_native_cost(cc: Path, nm: Path, values: dict[str, int]) -> dict[str, int]:
    for tool in (cc, nm):
        if tool.is_symlink() and not tool.exists():
            raise ContractError(f"tool symlink is broken: {tool}")
        if not tool.exists():
            raise ContractError(f"tool is missing: {tool}")
    source = f"""
typedef unsigned char uint8_t;
#define REST {values['rest']}u
#define STRICT {values['strict']}u
#define SHIFT {values['optional_shift']}u
__attribute__((noinline, used))
uint8_t lisp65_arity_accepts_probe(uint8_t actual, uint8_t nargs, uint8_t flags) {{
    uint8_t optional = (uint8_t)(flags >> SHIFT);
    uint8_t minimum;
    if (!(flags & STRICT)) return 1;
    if (optional > nargs) return 0;
    minimum = (uint8_t)(nargs - optional);
    if (actual < minimum) return 0;
    return (flags & REST) || actual <= nargs;
}}
__attribute__((noinline, used))
uint8_t lisp65_arity_call_probe(uint8_t actual, uint8_t nargs, uint8_t flags) {{
    return lisp65_arity_accepts_probe(actual, nargs, flags);
}}
int main(int argc, char **argv) {{
    (void)argv;
    return lisp65_arity_call_probe((uint8_t)argc, 2u, STRICT);
}}
"""
    with tempfile.TemporaryDirectory(prefix="lisp65-arity-") as td:
        src = Path(td) / "probe.c"
        prg = Path(td) / "probe.prg"
        elf = Path(str(prg) + ".elf")
        src.write_text(source, encoding="ascii")
        built = subprocess.run(
            [str(cc), "-Os", "-ffunction-sections", str(src), "-o", str(prg)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if built.returncode:
            raise ContractError(f"MOS cost probe compile failed: {built.stderr.strip()}")
        measured = subprocess.run(
            [str(nm), "--print-size", "--radix=d", str(elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if measured.returncode:
            raise ContractError(f"MOS cost probe nm failed: {measured.stderr.strip()}")
    sizes: dict[str, int] = {}
    for line in measured.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[-1] in {
            "lisp65_arity_accepts_probe", "lisp65_arity_call_probe",
        }:
            try:
                sizes[fields[-1]] = int(fields[1], 10)
            except ValueError as exc:
                raise ContractError(f"invalid llvm-nm size line: {line}") from exc
    if set(sizes) != {"lisp65_arity_accepts_probe", "lisp65_arity_call_probe"}:
        raise ContractError(f"MOS cost probe symbols missing: {sizes}")
    return {
        "helper_text_bytes": sizes["lisp65_arity_accepts_probe"],
        "call_wrapper_text_bytes": sizes["lisp65_arity_call_probe"],
    }


def _validate_contract_sections(contract: dict[str, Any]) -> None:
    semantics = _exact(
        contract["semantics"],
        {"required_count", "strict_fixed", "strict_rest", "legacy", "malformed"},
        "semantics",
    )
    for key, value in semantics.items():
        _string(value, f"semantics.{key}")
    profiles = _exact(contract["profiles"], {"dialect-v1", "dialect-v2"}, "profiles")
    for profile, expected in (("dialect-v1", False), ("dialect-v2", True)):
        item = _exact(
            profiles[profile],
            {"emits_strict_arity", "requires_strict_arity", "compatibility"},
            f"profiles.{profile}",
        )
        if (
            item["emits_strict_arity"] is not expected
            or item["requires_strict_arity"] is not expected
        ):
            raise ContractError(f"{profile} STRICT_ARITY emission drift")
        _string(item["compatibility"], f"profiles.{profile}.compatibility")
    spaces = _exact(contract["flag_spaces"], {"code_object", "directory_entry"}, "flag_spaces")
    for key, value in spaces.items():
        _string(value, f"flag_spaces.{key}")
    cost = _exact(
        contract["cost_gate"],
        {
            "artifact_header_delta_bytes", "arity_checks_per_function_entry",
            "native_static_call_sites",
            "native_helper_max_text_bytes", "native_call_wrapper_max_text_bytes",
            "runtime_cycle_claim",
        },
        "cost_gate",
    )
    if _integer(cost["artifact_header_delta_bytes"], "cost artifact delta", 0, 255) != 0:
        raise ContractError("STRICT_ARITY must not enlarge the CodeObject header")
    if _integer(cost["arity_checks_per_function_entry"], "cost checks", 1, 1) != 1:
        raise ContractError("exactly one arity check is required per function entry")
    _integer(cost["native_static_call_sites"], "native call sites", 1, 16)
    _integer(cost["native_helper_max_text_bytes"], "helper budget", 1, 255)
    _integer(cost["native_call_wrapper_max_text_bytes"], "wrapper budget", 1, 255)
    if cost["runtime_cycle_claim"] != "not-measured":
        raise ContractError("host report must not claim unmeasured target cycles")


def _selftest() -> None:
    values = {
        "rest": 1, "strict": 2, "optional_mask": 252, "optional_shift": 2,
    }
    cases = [
        (2, 0, 0, 0, None, True),
        (2, 0, 0, 7, None, True),
        (2, 0, 2, 1, None, False),
        (2, 0, 2, 2, None, True),
        (2, 0, 2, 3, None, False),
        (3, 0, 6, 1, None, False),
        (3, 0, 6, 2, None, True),
        (3, 0, 6, 3, None, True),
        (1, 1, 3, 9, None, True),
        (1, 0, 3, 1, "variadic-without-rest-local", True),
        (1, 0, 4, 1, "optional-without-strict-arity", True),
        (1, 0, 10, 1, "optional-count-exceeds-nargs", True),
    ]
    for nargs, nlocals, flags, actual, error, accepted in cases:
        got_error = _shape_error(nargs, nlocals, flags, values)
        got_accepted = _accepts(actual, nargs, flags, values)
        if got_error != error or got_accepted is not accepted:
            raise ContractError(
                f"selftest mismatch: {(nargs, nlocals, flags, actual)} "
                f"got={(got_error, got_accepted)} want={(error, accepted)}"
            )
    print(f"code-object-arity-contract-selftest: PASS={len(cases)} FAIL=0")


def run(args: argparse.Namespace) -> str:
    contract = _load(args.contract)
    _validate_contract_sections(contract)
    values = _contract_values(contract)
    call_sites, emitter_report = _audit_sources(values, contract)
    counts = _semantic_counts(values)
    cost = _probe_native_cost(args.cc, args.nm, values)
    budget = contract["cost_gate"]
    if cost["helper_text_bytes"] > budget["native_helper_max_text_bytes"]:
        raise ContractError("native arity helper exceeds its text budget")
    if cost["call_wrapper_text_bytes"] > budget["native_call_wrapper_max_text_bytes"]:
        raise ContractError("native arity call wrapper exceeds its text budget")
    lines = [
        "format=lisp65-code-object-arity-report-v1",
        "status=PASS",
        f"contract={args.contract.relative_to(ROOT)}",
        f"contract_sha256={_sha256(args.contract)}",
        f"mos_cc_sha256={_sha256(args.cc)}",
        f"llvm_nm_sha256={_sha256(args.nm)}",
        f"flags_offset={values['offset']}",
        f"rest_mask=0x{values['rest']:02x}",
        f"strict_arity_mask=0x{values['strict']:02x}",
        f"optional_count_mask=0x{values['optional_mask']:02x}",
        f"optional_count_shift={values['optional_shift']}",
        f"optional_count_max={values['optional_max']}",
        f"valid_flag_nargs_shapes={counts['valid_shapes']}",
        f"malformed_flag_nargs_shapes={counts['malformed_shapes']}",
        f"sampled_accepts={counts['sampled_accepts']}",
        f"sampled_rejects={counts['sampled_rejects']}",
        f"native_arity_call_sites={call_sites}",
        f"native_helper_text_bytes={cost['helper_text_bytes']}",
        f"native_helper_text_budget={budget['native_helper_max_text_bytes']}",
        f"native_call_wrapper_text_bytes={cost['call_wrapper_text_bytes']}",
        f"native_call_wrapper_text_budget={budget['native_call_wrapper_max_text_bytes']}",
        "artifact_header_delta_bytes=0",
        "arity_checks_per_function_entry=1",
        "runtime_cycle_claim=not-measured",
        "directory_entry_flags=separate-macro-bit-space",
        "optional_source_lowering=all-v2-emitters",
    ]
    lines.extend(f"{key}={value}" for key, value in emitter_report.items())
    for item in contract["consumers"]:
        lines.append(f"participant={item['role']}:{item['path']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cc", type=Path, default=DEFAULT_CC)
    parser.add_argument("--nm", type=Path, default=DEFAULT_NM)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            _selftest()
            return 0
        report = run(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="ascii")
        sys.stdout.write(report)
        return 0
    except (ContractError, OSError) as exc:
        print(f"code-object-arity-contract: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
