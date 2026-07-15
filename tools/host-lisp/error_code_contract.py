#!/usr/bin/env python3
"""Verify stable Lisp error identities and the linked Workbench emission set.

The product proof intentionally has no source-scanning fallback. Each constant error
origin emits one byte into ``.lisp65_error_callsites``; LTO and section GC then remove
markers with their unreachable code. The final ELF section is non-ALLOC at address
zero, so it costs neither Bank-0 bytes nor runtime-overlay space. A missing marker
section fails closed. Dynamic code selectors must mark every constant branch that can
reach ``lisp_abort_code`` rather than attempting to mark the dynamic call itself.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import Any, Iterable, Sequence


SCHEMA = "lisp65-error-code-contract-v1"
PRESENTATIONS = frozenset(
    ("active-text", "resident-text", "textless", "not-built")
)
TEXT_PRESENTATIONS = frozenset(("active-text", "resident-text"))
C_NAME_RE = re.compile(r"^LISP65_ERR_[A-Z][A-Z0-9_]*$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ENUM_RE = re.compile(
    r"^\s*(LISP65_ERR_[A-Z][A-Z0-9_]*|LISP65_ERROR_CODE_LIMIT)\s*=\s*"
    r"(0[xX][0-9a-fA-F]+|[0-9]+)\s*,?\s*$",
    re.MULTILINE,
)
SHF_ALLOC = 0x2
SHT_PROGBITS = 1
COMPILE_SENTINEL_IDS = (
    "fasl-entries-overflow", "fasl-nodes-overflow", "fasl-not-a-defun",
    "fasl-output-overflow", "fasl-patches-overflow", "fasl-strings-overflow",
    "fasl-too-many-helpers", "fasl-unsupported-literal",
    "fasl-window-overflow", "lcc-do-body-too-big",
    "lcc-invalid-parameter-list",
)


class ContractError(RuntimeError):
    """A deterministic contract or product-drift failure."""


@dataclass(frozen=True)
class CodeContract:
    code: int
    ident: str
    c_name: str
    error_class: str
    presentation: str
    reason: str | None
    meaning: str | None


@dataclass(frozen=True)
class Contract:
    profile: str
    text_profile: str
    none_name: str
    none_code: int
    limit_name: str
    limit_value: int
    marker_section: str
    marker_non_alloc: bool
    required_text_classes: frozenset[str]
    textless_classes: frozenset[str]
    not_built_classes: frozenset[str]
    codes: tuple[CodeContract, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} root must be an object")
    return value


def _string_set(value: Any, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{label} must be a non-empty string list")
    if any(not isinstance(item, str) or not item for item in value):
        raise ContractError(f"{label} must contain non-empty strings")
    if len(set(value)) != len(value):
        raise ContractError(f"{label} contains duplicates")
    return frozenset(value)


def load_contract(path: Path) -> Contract:
    raw = _load_json(path, "error-code contract")
    expected_root = {
        "schema", "format", "profile", "text_profile", "numbering", "emission_marker",
        "selection_policy", "codes",
    }
    if set(raw) != expected_root:
        raise ContractError("error-code contract has missing or unknown root fields")
    if raw["schema"] != SCHEMA or raw["format"] != SCHEMA:
        raise ContractError(
            "unsupported error-code contract schema/format: "
            f"{raw['schema']!r}/{raw['format']!r}"
        )
    if not isinstance(raw["profile"], str) or not raw["profile"]:
        raise ContractError("contract profile must be a non-empty string")
    if not isinstance(raw["text_profile"], str) or not raw["text_profile"]:
        raise ContractError("contract text_profile must be a non-empty string")

    numbering = raw["numbering"]
    numbering_keys = {
        "none_name", "none_code", "first_code", "last_code", "limit_name",
        "limit_value", "dense",
    }
    if not isinstance(numbering, dict) or set(numbering) != numbering_keys:
        raise ContractError("numbering policy has missing or unknown fields")
    if numbering["dense"] is not True:
        raise ContractError("error codes must remain dense")
    integer_fields = ("none_code", "first_code", "last_code", "limit_value")
    if any(type(numbering[name]) is not int for name in integer_fields):
        raise ContractError("numbering values must be integers")
    if numbering["none_code"] != 0 or numbering["first_code"] != 1:
        raise ContractError("error numbering must reserve zero and start at one")
    if numbering["limit_value"] != numbering["last_code"] + 1:
        raise ContractError("error-code limit must be one past the last stable code")

    marker = raw["emission_marker"]
    if not isinstance(marker, dict) or set(marker) != {
        "section", "encoding", "must_be_non_alloc"
    }:
        raise ContractError("emission-marker policy has missing or unknown fields")
    if (not isinstance(marker["section"], str) or not marker["section"].startswith(".")
            or marker["encoding"] != "u8-code-v1"
            or marker["must_be_non_alloc"] is not True):
        raise ContractError("invalid emission-marker policy")

    policy = raw["selection_policy"]
    policy_keys = {
        "rule", "user_text_required_classes", "textless_allowed_classes",
        "not_built_allowed_classes", "future_requirements",
    }
    if not isinstance(policy, dict) or set(policy) != policy_keys:
        raise ContractError("selection policy has missing or unknown fields")
    if not isinstance(policy["rule"], str) or not policy["rule"]:
        raise ContractError("selection policy needs a rule")
    required = _string_set(policy["user_text_required_classes"], "text-required classes")
    textless = _string_set(policy["textless_allowed_classes"], "textless classes")
    not_built = _string_set(policy["not_built_allowed_classes"], "not-built classes")
    if required & textless or required & not_built or textless & not_built:
        raise ContractError("selection-policy class sets must be disjoint")
    future = policy["future_requirements"]
    if (not isinstance(future, list) or not future
            or any(not isinstance(item, str) or not item for item in future)):
        raise ContractError("selection policy needs explicit future requirements")
    if "persistence" not in required:
        raise ContractError("future persistence errors must require text")

    raw_codes = raw["codes"]
    if not isinstance(raw_codes, list) or not raw_codes:
        raise ContractError("contract codes must be a non-empty list")
    codes: list[CodeContract] = []
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_codes):
        label = f"codes[{index}]"
        if not isinstance(item, dict):
            raise ContractError(f"{label} must be an object")
        base_keys = {"code", "id", "c_name", "class", "presentation"}
        optional_keys = {"reason", "meaning"}
        if not base_keys <= set(item) or not set(item) <= base_keys | optional_keys:
            raise ContractError(f"{label} has missing or unknown fields")
        code = item["code"]
        ident = item["id"]
        c_name = item["c_name"]
        error_class = item["class"]
        presentation = item["presentation"]
        reason = item.get("reason")
        meaning = item.get("meaning")
        if type(code) is not int or not 1 <= code <= 255:
            raise ContractError(f"{label}.code must be in 1..255")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise ContractError(f"{label}.id is not canonical")
        if not isinstance(c_name, str) or not C_NAME_RE.fullmatch(c_name):
            raise ContractError(f"{label}.c_name is not canonical")
        if not isinstance(error_class, str) or not error_class:
            raise ContractError(f"{label}.class must be a non-empty string")
        if error_class not in required | textless | not_built:
            raise ContractError(f"{label}.class is not declared by the selection policy")
        if presentation not in PRESENTATIONS:
            raise ContractError(f"{label}.presentation is unsupported")
        if presentation in TEXT_PRESENTATIONS:
            if error_class in not_built:
                raise ContractError(f"{label} text uses a profile-excluded class")
            if reason is not None:
                raise ContractError(f"{label} text must not carry an omission reason")
            if presentation == "resident-text" and error_class not in required:
                raise ContractError(f"{label} resident text must remain user-reachable")
        elif presentation == "textless":
            if error_class not in textless:
                raise ContractError(f"{label} textless is not an internal allowed class")
            if not isinstance(reason, str) or not reason:
                raise ContractError(f"{label} textless needs an explicit reason")
        else:
            if error_class not in not_built:
                raise ContractError(f"{label} not-built is not a profile exclusion")
            if not isinstance(reason, str) or not reason:
                raise ContractError(f"{label} not-built needs an explicit reason")
        if error_class in required and presentation not in TEXT_PRESENTATIONS:
            raise ContractError(f"{label} user-reachable class must have text")
        if meaning is not None and (
            not isinstance(meaning, str) or not meaning or not meaning.isascii()
        ):
            raise ContractError(f"{label}.meaning must be non-empty ASCII")
        if c_name in seen_names or ident in seen_ids:
            raise ContractError(f"{label} duplicates a C name or semantic id")
        seen_names.add(c_name)
        seen_ids.add(ident)
        codes.append(CodeContract(
            code, ident, c_name, error_class, presentation, reason, meaning
        ))

    expected_codes = list(range(numbering["first_code"], numbering["last_code"] + 1))
    if [item.code for item in codes] != expected_codes:
        raise ContractError("stable error codes must be ordered and dense across the pinned range")
    if len(codes) >= 49:
        sentinels = tuple(item for item in codes if 49 <= item.code <= 59)
        if (tuple(item.ident for item in sentinels) != COMPILE_SENTINEL_IDS
                or any(item.meaning is None for item in sentinels)):
            raise ContractError(
                "stable compile-sentinel identities or documented meanings drifted"
            )
    return Contract(
        raw["profile"], raw["text_profile"], numbering["none_name"], numbering["none_code"],
        numbering["limit_name"], numbering["limit_value"], marker["section"],
        marker["must_be_non_alloc"], required, textless, not_built, tuple(codes),
    )


def read_header_codes(path: Path) -> dict[str, int]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"error-code header must be a regular non-symlink file: {path}")
        source = path.read_text(encoding="ascii")
    except ContractError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read error-code header {path}: {exc}") from exc
    pairs = ENUM_RE.findall(source)
    values: dict[str, int] = {}
    for name, raw_value in pairs:
        if name in values:
            raise ContractError(f"duplicate error-code definition in header: {name}")
        values[name] = int(raw_value, 0)
    if not values:
        raise ContractError("error-code header has no explicit stable definitions")
    return values


def verify_header(contract: Contract, header_values: dict[str, int]) -> None:
    expected = {contract.none_name: contract.none_code, contract.limit_name: contract.limit_value}
    expected.update((item.c_name, item.code) for item in contract.codes)
    missing = sorted(set(expected) - set(header_values))
    extra = sorted(set(header_values) - set(expected))
    changed = sorted(
        name for name in set(expected) & set(header_values)
        if expected[name] != header_values[name]
    )
    if missing or extra or changed:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("new/unclassified=" + ",".join(extra))
        if changed:
            details.append(
                "renumbered=" + ",".join(
                    f"{name}:{expected[name]}->{header_values[name]}" for name in changed
                )
            )
        raise ContractError("stable error-code header drift: " + "; ".join(details))
    inverse: dict[int, list[str]] = {}
    for name, code in header_values.items():
        inverse.setdefault(code, []).append(name)
    reused = sorted((code, names) for code, names in inverse.items() if len(names) != 1)
    if reused:
        raise ContractError(f"error-code number reused: {reused}")


def read_text_bindings(path: Path, profile: str) -> dict[int, tuple[str, str, str]]:
    raw = _load_json(path, "error-text spec")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ContractError("error-text spec entries must be a list")
    result: dict[int, tuple[str, str, str]] = {}
    names: set[str] = set()
    ids: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ContractError(f"error-text entries[{index}] must be an object")
        code = item.get("code")
        ident = item.get("id")
        c_name = item.get("c_name")
        text = item.get("text")
        profiles = item.get("profiles")
        delivery = item.get("delivery", "overlay")
        if (type(code) is not int or not isinstance(ident, str)
                or not isinstance(c_name, str) or not isinstance(text, str) or not text):
            raise ContractError(f"error-text entries[{index}] has invalid binding fields")
        if profiles is not None and (
            not isinstance(profiles, list)
            or any(not isinstance(value, str) or not value for value in profiles)
            or len(set(profiles)) != len(profiles)
        ):
            raise ContractError(f"error-text entries[{index}].profiles is invalid")
        if delivery not in ("overlay", "resident-only"):
            raise ContractError(f"error-text entries[{index}].delivery is invalid")
        selected = profiles is None or profile in profiles
        if delivery == "resident-only":
            if item.get("audience") != "user":
                raise ContractError(
                    f"error-text entries[{index}] resident-only text is not user-facing"
                )
            if profiles is None or "host" not in profiles:
                raise ContractError(
                    f"error-text entries[{index}] resident-only text lacks host coverage"
                )
            if selected:
                raise ContractError(
                    f"error-text entries[{index}] resident-only text leaks into {profile}"
                )
        if delivery == "overlay" and not selected:
            continue
        if code in result or ident in ids or c_name in names:
            raise ContractError(f"duplicate error-text binding at entries[{index}]")
        result[code] = (ident, c_name, delivery)
        ids.add(ident)
        names.add(c_name)
    return result


def verify_texts(contract: Contract,
                 bindings: dict[int, tuple[str, str, str]]) -> None:
    expected = {
        item.code: (
            item.ident,
            item.c_name,
            "resident-only" if item.presentation == "resident-text" else "overlay",
        )
        for item in contract.codes if item.presentation in TEXT_PRESENTATIONS
    }
    missing = sorted(set(expected) - set(bindings))
    stale = sorted(set(bindings) - set(expected))
    changed = sorted(
        code for code in set(expected) & set(bindings) if expected[code] != bindings[code]
    )
    if missing or stale or changed:
        raise ContractError(
            "error-text selection drift: "
            f"missing={missing} stale={stale} rebound={changed}"
        )


def _elf_sections(data: bytes) -> list[tuple[str, int, int, int, int, int]]:
    if len(data) < 16 or data[:4] != b"\x7fELF":
        raise ContractError("linked product is not ELF")
    elf_class, endian = data[4], data[5]
    if endian not in (1, 2):
        raise ContractError("ELF has unsupported byte order")
    order = "<" if endian == 1 else ">"
    if elf_class == 1:
        header_format = order + "HHIIIIIHHHHHH"
        section_format = order + "IIIIIIIIII"
    elif elf_class == 2:
        header_format = order + "HHIQQQIHHHHHH"
        section_format = order + "IIQQQQIIQQ"
    else:
        raise ContractError("ELF has unsupported class")
    header_size = struct.calcsize(header_format)
    if len(data) < 16 + header_size:
        raise ContractError("ELF header is truncated")
    header = struct.unpack_from(header_format, data, 16)
    section_offset = header[5]
    section_entry_size = header[10]
    section_count = header[11]
    string_index = header[12]
    expected_entry_size = struct.calcsize(section_format)
    if section_entry_size < expected_entry_size or section_count == 0:
        raise ContractError("ELF section table is absent or malformed")
    table_end = section_offset + section_entry_size * section_count
    if table_end > len(data) or string_index >= section_count:
        raise ContractError("ELF section table is outside the file")

    raw_sections = []
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        fields = struct.unpack_from(section_format, data, offset)
        raw_sections.append(fields)
    strings = raw_sections[string_index]
    string_offset, string_size = strings[4], strings[5]
    if string_offset + string_size > len(data):
        raise ContractError("ELF section-name table is outside the file")
    names = data[string_offset:string_offset + string_size]

    result: list[tuple[str, int, int, int, int, int]] = []
    for fields in raw_sections:
        name_offset, section_type, flags, address, offset, size = fields[:6]
        if name_offset >= len(names):
            raise ContractError("ELF section name is outside the string table")
        end = names.find(b"\0", name_offset)
        if end < 0:
            raise ContractError("ELF section name is unterminated")
        try:
            name = names[name_offset:end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ContractError("ELF section name is not ASCII") from exc
        if section_type != 8 and offset + size > len(data):
            raise ContractError(f"ELF section {name!r} is outside the file")
        result.append((name, section_type, flags, address, offset, size))
    return result


def read_elf_emissions(path: Path, contract: Contract) -> frozenset[int]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"ELF must be a regular non-symlink file: {path}")
        data = path.read_bytes()
    except ContractError:
        raise
    except OSError as exc:
        raise ContractError(f"cannot read ELF {path}: {exc}") from exc
    matches = [item for item in _elf_sections(data) if item[0] == contract.marker_section]
    if len(matches) != 1:
        raise ContractError(
            f"ELF must contain exactly one {contract.marker_section} marker section; "
            f"found {len(matches)}"
        )
    _, section_type, flags, address, offset, size = matches[0]
    if section_type != SHT_PROGBITS:
        raise ContractError("error-callsite marker section must be PROGBITS")
    if contract.marker_non_alloc and (flags & SHF_ALLOC or address != 0):
        raise ContractError("error-callsite marker section consumes target address space")
    payload = data[offset:offset + size]
    if not payload:
        raise ContractError("error-callsite marker section is empty")
    if 0 in payload:
        raise ContractError("error-callsite marker section contains reserved code zero")
    return frozenset(payload)


def verify_emissions(contract: Contract, emitted: Iterable[int]) -> None:
    actual = frozenset(emitted)
    known = {item.code for item in contract.codes}
    unknown = sorted(actual - known)
    if unknown:
        raise ContractError(f"linked product emits unclassified error codes: {unknown}")
    expected_live = {
        item.code for item in contract.codes if item.presentation != "not-built"
    }
    missing = sorted(expected_live - actual)
    unexpected = sorted(actual - expected_live)
    if missing or unexpected:
        raise ContractError(
            "linked error emission drift: "
            f"stale-active-or-textless={missing} newly-live-not-built={unexpected}"
        )


def verify_all(contract_path: Path, header_path: Path, texts_path: Path,
               elf_path: Path) -> Contract:
    contract = load_contract(contract_path)
    verify_header(contract, read_header_codes(header_path))
    verify_texts(contract, read_text_bindings(texts_path, contract.text_profile))
    verify_emissions(contract, read_elf_emissions(elf_path, contract))
    return contract


def _write_fixture(path: Path, raw: dict[str, Any]) -> None:
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


def selftest() -> int:
    base_contract = {
        "schema": SCHEMA,
        "format": SCHEMA,
        "profile": "selftest",
        "text_profile": "workbench",
        "numbering": {
            "none_name": "LISP65_ERR_NONE", "none_code": 0, "first_code": 1,
            "last_code": 3, "limit_name": "LISP65_ERROR_CODE_LIMIT",
            "limit_value": 4, "dense": True,
        },
        "emission_marker": {
            "section": ".lisp65_error_callsites", "encoding": "u8-code-v1",
            "must_be_non_alloc": True,
        },
        "selection_policy": {
            "rule": "user text, internal reason, excluded reason",
            "user_text_required_classes": ["reader", "persistence"],
            "textless_allowed_classes": ["internal-validator"],
            "not_built_allowed_classes": ["profile-excluded"],
            "future_requirements": ["persistence remains text"],
        },
        "codes": [
            {"code": 1, "id": "reader-a", "c_name": "LISP65_ERR_READER_A",
             "class": "reader", "presentation": "active-text"},
            {"code": 2, "id": "internal-b", "c_name": "LISP65_ERR_INTERNAL_B",
             "class": "internal-validator", "presentation": "textless",
             "reason": "diagnostic code is sufficient"},
            {"code": 3, "id": "excluded-c", "c_name": "LISP65_ERR_EXCLUDED_C",
             "class": "profile-excluded", "presentation": "not-built",
             "reason": "surface is not built"},
        ],
    }
    header = """enum {
LISP65_ERR_NONE = 0,
LISP65_ERR_READER_A = 1,
LISP65_ERR_INTERNAL_B = 2,
LISP65_ERR_EXCLUDED_C = 3,
LISP65_ERROR_CODE_LIMIT = 4
};
"""
    text_spec = {
        "entries": [
            {"code": 1, "id": "reader-a", "c_name": "LISP65_ERR_READER_A",
             "text": "a", "audience": "user"}
        ]
    }
    cases = 0
    with tempfile.TemporaryDirectory(prefix="error-code-contract-") as temp_name:
        temp = Path(temp_name)
        contract_path = temp / "contract.json"
        header_path = temp / "error_codes.h"
        text_path = temp / "texts.json"
        _write_fixture(contract_path, base_contract)
        header_path.write_text(header, encoding="ascii")
        _write_fixture(text_path, text_spec)
        contract = load_contract(contract_path)
        verify_header(contract, read_header_codes(header_path))
        verify_texts(contract, read_text_bindings(text_path, contract.text_profile))
        verify_emissions(contract, {1, 2})
        cases += 1

        resident_contract_raw = json.loads(json.dumps(base_contract))
        resident_contract_raw["codes"][0]["presentation"] = "resident-text"
        resident_contract_path = temp / "resident-contract.json"
        _write_fixture(resident_contract_path, resident_contract_raw)
        resident_text_spec = json.loads(json.dumps(text_spec))
        resident_text_spec["entries"][0]["profiles"] = ["host"]
        resident_text_spec["entries"][0]["delivery"] = "resident-only"
        resident_text_path = temp / "resident-text.json"
        _write_fixture(resident_text_path, resident_text_spec)
        resident_contract = load_contract(resident_contract_path)
        verify_texts(
            resident_contract,
            read_text_bindings(resident_text_path, resident_contract.text_profile),
        )
        cases += 1

        def expect_failure(label: str, action: Any) -> None:
            nonlocal cases
            try:
                action()
            except ContractError:
                cases += 1
                return
            raise AssertionError(f"selftest case unexpectedly passed: {label}")

        expect_failure(
            "renumber",
            lambda: verify_header(contract, read_header_codes(_temp_header(
                temp, header.replace("READER_A = 1", "READER_A = 2")
            ))),
        )
        expect_failure(
            "new-enum",
            lambda: verify_header(contract, read_header_codes(_temp_header(
                temp, header.replace(
                    "LISP65_ERROR_CODE_LIMIT = 4",
                    "LISP65_ERR_NEW = 4,\nLISP65_ERROR_CODE_LIMIT = 5",
                )
            ))),
        )
        expect_failure(
            "deleted-enum",
            lambda: verify_header(contract, read_header_codes(_temp_header(
                temp, header.replace("LISP65_ERR_INTERNAL_B = 2,\n", "")
            ))),
        )
        stale_text = json.loads(json.dumps(text_spec))
        stale_text["entries"].append(
            {"code": 3, "id": "excluded-c", "c_name": "LISP65_ERR_EXCLUDED_C", "text": "c"}
        )
        stale_path = temp / "stale-text.json"
        _write_fixture(stale_path, stale_text)
        expect_failure(
            "stale-entry",
            lambda: verify_texts(
                contract, read_text_bindings(stale_path, contract.text_profile)
            ),
        )
        expect_failure("unclassified-callsite", lambda: verify_emissions(contract, {1, 2, 3}))

        user_textless = json.loads(json.dumps(base_contract))
        user_textless["codes"][0]["presentation"] = "textless"
        user_textless["codes"][0]["reason"] = "wrong"
        bad_contract_path = temp / "user-textless.json"
        _write_fixture(bad_contract_path, user_textless)
        expect_failure("user-textless", lambda: load_contract(bad_contract_path))
        expect_failure("stale-omission", lambda: verify_emissions(contract, {1}))

    print(f"error-code-contract selftest: PASS cases={cases}")
    return 0


def _temp_header(temp: Path, contents: str) -> Path:
    path = temp / "mutated-error-codes.h"
    path.write_text(contents, encoding="ascii")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="verify fixture, header, texts and linked ELF")
    check.add_argument("--contract", required=True, type=Path)
    check.add_argument("--header", required=True, type=Path)
    check.add_argument("--texts", required=True, type=Path)
    check.add_argument("--elf", required=True, type=Path)
    subparsers.add_parser("selftest", help="run negative mutation tests")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest()
        contract = verify_all(args.contract, args.header, args.texts, args.elf)
        active = sum(item.presentation == "active-text" for item in contract.codes)
        resident = sum(item.presentation == "resident-text" for item in contract.codes)
        textless = sum(item.presentation == "textless" for item in contract.codes)
        not_built = sum(item.presentation == "not-built" for item in contract.codes)
        print(
            "error-code-contract: PASS "
            f"profile={contract.profile} stable={len(contract.codes)} "
            f"active-text={active} resident-text={resident} "
            f"textless={textless} not-built={not_built}"
        )
        return 0
    except (ContractError, AssertionError) as exc:
        print(f"error-code-contract: FAIL {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
