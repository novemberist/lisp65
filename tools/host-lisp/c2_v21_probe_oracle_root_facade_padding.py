#!/usr/bin/env python3
"""Prove the authorized explicit 19-byte mapped-facade contract filler."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_probe_oracle_root_product_config as CONFIG  # noqa: E402
import c2_v21_probe_oracle_root_fix as ROOT_FIX  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SOURCE = CONFIG.PADDING
LINKER_PRODUCER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
ROOT_RED = ARCH / "c2.3-v2.1-probe-oracle-root-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-probe-oracle-root-card-red-attribution-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-probe-oracle-root-facade-padding-receipt.json")
VMA_REBIND = ARCH / (
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-16.json")
FACADE_PRODUCER_REBIND = ARCH / (
    "c2.3-v2.1-facade-padding-linker-producer-rebind-2026-08-17.json")
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-facade-padding"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
AUTHORIZATION = "7e4a1f86"
FORMAT = "lisp65-c2.3-v2.1-probe-oracle-root-facade-padding-v1"
STATUS = "HOST-GREEN: EXPLICIT-NAMED-19-BYTE-FACADE-PADDING"


class PaddingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PaddingError(message)


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


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        rows: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                rows.append(child)
            else:
                rows.extend(changed_paths(old[key], new[key], child))
        return rows
    return [] if old == new else [prefix]


def git_bind(commit: str, path: Path) -> dict[str, Any]:
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
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").split())
    for token in ("19 bytes become explicit facade padding", "declared, named",
                  "padding is contract filler, never accident",
                  "one replacement card"):
        require(token in text,
                f"facade-padding authorization token absent: {token}")
    return value


def source_contract(source: str | None = None) -> dict[str, Any]:
    text = SOURCE.read_text(encoding="utf-8") if source is None else source
    require(
        text.count(
            '.section .lisp65_c2_mapped_far_facade.padding,"ax",@progbits') == 1
        and text.count(
            "__lisp65_c2_mapped_far_facade_padding_contract_bytes, 19") == 1
        and text.count("__lisp65_c2_mapped_far_facade_padding:") == 1
        and text.count(".fill 19, 1, 0") == 1
        and text.count(
            ".size __lisp65_c2_mapped_far_facade_padding, "
            ".-__lisp65_c2_mapped_far_facade_padding") == 1,
        "facade filler is not explicit, named and exactly 19 PROGBITS bytes")
    return {"section": ".lisp65_c2_mapped_far_facade.padding",
            "symbol": "__lisp65_c2_mapped_far_facade_padding",
            "contract_symbol":
                "__lisp65_c2_mapped_far_facade_padding_contract_bytes",
            "bytes": 19, "fill": "00", "executed": False}


def linked_contract(script: str | None = None,
                    flags: tuple[str, ...] | None = None) -> dict[str, Any]:
    text = PRODUCT.linker_script(ownership_opt_in=True) \
        if script is None else script
    selected = PRODUCT.ownership_link_flags((
        PRODUCT.CONVERGENCE_FEATURE, CONFIG.FEATURE)) \
        if flags is None else flags
    required = (
        "-Wl,--defsym="
        "__lisp65_c2_mapped_far_facade_padding_required_param=1")
    tokens = (
        "__lisp65_c2_mapped_far_facade_padding_start = .;",
        "KEEP(*(.lisp65_c2_mapped_far_facade.padding))",
        "__lisp65_c2_mapped_far_facade_padding_end = .;",
        "DEFINED(__lisp65_c2_mapped_far_facade_padding_contract_bytes)",
        "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 19",
        '"mapped far facade explicit padding drift"',
        "SIZEOF(.lisp65_c2_mapped_far_facade) == 98",
    )
    require(all(text.count(token) == 1 for token in tokens)
            and selected.count(required) == 1,
            "linked facade does not require and measure the explicit filler")
    return {"fixed_facade_bytes": 98, "padding_bytes": 19,
            "padding_required_by_candidate_flag": True,
            "start_end_measured": True, "implicit_filler_accepted": False}


def configuration_contract() -> dict[str, Any]:
    previous = (PRODUCT.CONVERGENCE_DEFINES, PRODUCT.CONVERGENCE_SOURCES,
                PRODUCT.SOURCE_OWNER_SCOPES)
    try:
        value = CONFIG.configure(PRODUCT)
        selected = PRODUCT.source_list(PRODUCT.CONVERGENCE_DEFINES)
        rows = [row for row in PRODUCT.SOURCE_OWNER_SCOPES
                if row.get("name") == "mapped-far-content-convergence"]
        require(len(rows) == 1 and SOURCE in rows[0]["sources"]
                and str(SOURCE) in selected
                and value["facade_padding"]["bytes"] == 19,
                "real producer did not select the explicit padding owner")
        return {"owner": rows[0]["name"],
                "source": SOURCE.relative_to(ROOT).as_posix(),
                "selected": True, "bytes": 19}
    finally:
        (PRODUCT.CONVERGENCE_DEFINES, PRODUCT.CONVERGENCE_SOURCES,
         PRODUCT.SOURCE_OWNER_SCOPES) = previous


def compile_contract() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    obj = BUILD / "facade-padding.o"
    subprocess.run([str(LLVM / "mos-mega65-clang"), "-c", str(SOURCE),
                    "-o", str(obj)], cwd=ROOT, check=True)
    truth = ElfTruth.read(obj, llvm_readobj=LLVM / "llvm-readobj",
                          include_section_data=True)
    section = truth.section(".lisp65_c2_mapped_far_facade.padding")
    symbol = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    raw = truth.section_bytes(section.name)
    require(section.bytes == symbol.bytes == len(raw) == 19
            and raw == bytes(19),
            "assembled padding object is not exactly 19 zero PROGBITS bytes")
    return {"object": bind(obj), "section_bytes": section.bytes,
            "symbol_bytes": symbol.bytes, "payload_sha256":
                hashlib.sha256(raw).hexdigest()}


def fixture_link(*, include_source: bool, implicit_fill: bool) -> dict[str, Any]:
    root = BUILD / ("fixture-good" if include_source else
                    ("fixture-implicit" if implicit_fill else "fixture-missing"))
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    body = root / "body.s"
    body.write_text(
        '.section .lisp65_c2_mapped_far_facade.entries,"ax",@progbits\n'
        '.fill 52, 1, 0\n'
        '.section .lisp65_c2_mapped_far_facade.abort,"ax",@progbits\n'
        '.fill 27, 1, 0\n', encoding="utf-8")
    body_obj = root / "body.o"
    subprocess.run([str(LLVM / "mos-mega65-clang"), "-c", str(body),
                    "-o", str(body_obj)], cwd=ROOT, check=True)
    pad_obj = BUILD / "facade-padding.o"
    if not pad_obj.exists():
        compile_contract()
    linker = root / "fixture.ld"
    implicit = ". += 19;" if implicit_fill else ""
    linker.write_text(f'''SECTIONS {{
  .lisp65_c2_mapped_far_facade 0xb3b0 : {{
    KEEP(*(.lisp65_c2_mapped_far_facade.entries))
    KEEP(*(.lisp65_c2_mapped_far_facade.abort))
    __lisp65_c2_mapped_far_facade_padding_start = .;
    KEEP(*(.lisp65_c2_mapped_far_facade.padding))
    __lisp65_c2_mapped_far_facade_padding_end = .;
    {implicit}
  }}
}}
ASSERT(SIZEOF(.lisp65_c2_mapped_far_facade) == 98,
       "mapped far facade escaped its resident wall");
ASSERT(DEFINED(__lisp65_c2_mapped_far_facade_padding_contract_bytes) &&
       __lisp65_c2_mapped_far_facade_padding_end -
         __lisp65_c2_mapped_far_facade_padding_start ==
           __lisp65_c2_mapped_far_facade_padding_contract_bytes &&
       __lisp65_c2_mapped_far_facade_padding_contract_bytes == 19,
       "mapped far facade explicit padding drift");
''', encoding="utf-8")
    command = [str(LLVM / "ld.lld"), "-T", str(linker), "-o",
               str(root / "fixture.elf"), str(body_obj)]
    if include_source:
        command.append(str(pad_obj))
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"accepted": run.returncode == 0,
            "diagnostic": " ".join(run.stdout.split())}


def derive() -> dict[str, Any]:
    red = load(ROOT_RED)
    attribution = load(ATTRIBUTION)
    require(red.get("retry_authorized") is False
            and attribution["narrow_repair"] == {
                "form": "explicit non-executed mapped-facade contract padding",
                "padding_bytes": 19, "semantic_bytes_changed": 0,
                "reader_or_vector_growth_bytes": 0,
                "expected_execution_delta_bytes": -22,
                "authorized": False, "replacement_card_authorized": False},
            "facade-padding predecessor boundary drift")
    source = source_contract()
    linked = linked_contract()
    configured = configuration_contract()
    compiled = compile_contract()
    good = fixture_link(include_source=True, implicit_fill=False)
    absent = fixture_link(include_source=False, implicit_fill=False)
    implicit = fixture_link(include_source=False, implicit_fill=True)
    require(good["accepted"] is True and absent["accepted"] is False
            and implicit["accepted"] is False
            and "explicit padding drift" in implicit["diagnostic"],
            "real linked fixture accepted an implicit or absent filler")
    historical_root = load(ROOT_FIX.RECEIPT)
    current_root = ROOT_FIX.derive()
    current_root["source_mutations_rejected"] = ROOT_FIX.source_mutations()
    current_root["mutations_rejected"] = ROOT_FIX.mutations(current_root)
    changed = changed_paths(historical_root, current_root)
    authorized_changed = [
        "authority.checker.bytes",
        "authority.checker.sha256",
        "authority.configuration.bytes",
        "authority.configuration.sha256",
        "configuration.component.facade_padding",
        "configuration.source_owner.sources",
    ]
    require(changed == authorized_changed,
            f"root-fix padding successor exceeds authorization: {changed}")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "source_contract": source, "linked_contract": linked,
        "configuration": configured, "assembled": compiled,
        "real_link_fixtures": {"explicit": good, "absent": absent,
                               "implicit": implicit},
        "root_fix_successor": {
            "historical_receipt": bind(ROOT_FIX.RECEIPT),
            "historical_receipt_rewritten": False,
            "current_projection": bind_raw(
                ROOT_FIX.RECEIPT, ROOT_FIX.canonical(current_root)),
            "authorized_changed_paths": authorized_changed,
            "semantic_root_claim_changed": False},
        "execution_accounting": {"host_assembly_compiles": 4,
            "host_fixture_links": 3, "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "Final_Red": bind(ROOT_RED),
            "attribution": bind(ATTRIBUTION), "source": bind(SOURCE),
            "linker_producer": bind(LINKER_PRODUCER), "driver": bind(DRIVER)},
        "claim_limit": "Host padding contract only; replacement card pending.",
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value["source_contract"]["bytes"] == 19
            and value["source_contract"]["executed"] is False
            and value["linked_contract"]["fixed_facade_bytes"] == 98
            and value["linked_contract"]["implicit_filler_accepted"] is False
            and value["configuration"]["selected"] is True
            and value["assembled"]["section_bytes"] == 19
            and value["real_link_fixtures"]["explicit"]["accepted"] is True
            and value["real_link_fixtures"]["absent"]["accepted"] is False
            and value["real_link_fixtures"]["implicit"]["accepted"] is False
            and value["root_fix_successor"][
                "historical_receipt_rewritten"] is False
            and value["root_fix_successor"][
                "semantic_root_claim_changed"] is False,
            "explicit facade padding contract drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "implicit-shortfall": lambda x: x["real_link_fixtures"][
            "implicit"].update(accepted=True),
        "absent-filler": lambda x: x["real_link_fixtures"][
            "absent"].update(accepted=True),
        "wrong-size": lambda x: x["source_contract"].update(bytes=18),
        "executed-filler": lambda x: x["source_contract"].update(executed=True),
        "drop-owner": lambda x: x["configuration"].update(selected=False),
        "drop-linked-assert": lambda x: x["linked_contract"].update(
            implicit_filler_accepted=True),
        "assemble-short": lambda x: x["assembled"].update(section_bytes=18),
        "reject-explicit": lambda x: x["real_link_fixtures"][
            "explicit"].update(accepted=False),
        "rewrite-root-history": lambda x: x["root_fix_successor"].update(
            historical_receipt_rewritten=True),
        "change-root-claim": lambda x: x["root_fix_successor"].update(
            semantic_root_claim_changed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except PaddingError:
            rejected.append(name)
    require(rejected == list(cases), "facade-padding mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive(); value["mutations_rejected"] = mutations(value)
        require(not RECEIPT.exists(), "facade-padding receipt already exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        value = load(RECEIPT)
        rejected = value.pop("mutations_rejected", None)
        validate(value)
        rebind = load(FACADE_PRODUCER_REBIND)
        require(
            rejected == mutations(value) and len(rejected) == 10
            and rebind.get("status") ==
                "PASS: loud facade-padding linker-producer rebind"
            and rebind.get("authority", {}).get(
                "authorized_linker_producer") == bind(LINKER_PRODUCER),
            "historical facade-padding linker-producer rebind drift")
    print(f"probe-oracle root facade padding: PASS action={action} "
          "bytes=19 mutations=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PaddingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"probe-oracle root facade padding: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
