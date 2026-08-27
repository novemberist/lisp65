#!/usr/bin/env python3
"""Decide whether the frozen card-3 pair depends on its stale plane header."""

from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
PREDECESSOR = ARCH / (
    "c2.3-v1.7-ide-idle-blink-qualification-resume-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v1.7-ide-idle-blink-header-rebind-resume-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ec03ae80"
EXPECTED = {
    "ELF": "c5aaccf702a655223b540e18ccb58176aa500baa37554a0d610c07c2381b6c52",
    "PRG": "7345e84de9e30eae3428ff2444de1c626b873109abb0f2c9dc4c6a35f03ce5d0",
}
FUNCTIONS = ("c2_stream_phase_02b", "c2_stream_phase_03b")
GENERATED = CARD.BUILD / "wplto/generated-product-sources/c2-stream-decoder.c"
HISTORICAL_HEADER = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-inputs/c2_lite_static_plane.h")


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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").replace("`", "").split())
    for token in ("compiler-consumption review disposition",
                  "path and value diverge must fail",
                  "does any emitted byte", "pair is declared dead",
                  "new wplto, product link or card is explicitly not authorized",
                  EXPECTED["ELF"], EXPECTED["PRG"]):
        require(token in text, f"header-rebind resume authority absent: {token}")
    return value


def frozen_pair() -> dict[str, dict[str, Any]]:
    value = {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)}
    require({name: row["sha256"] for name, row in value.items()} == EXPECTED,
            "card-3 frozen pair identity drift")
    return value


def macro_value(path: Path) -> int:
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        path.read_bytes(), re.MULTILINE)
    require(len(values) == 1, f"static extent is ambiguous: {path}")
    return int(values[0])


def living_compiler_projection() -> dict[str, Any]:
    target = CARD.setup_plane()
    CARD.bind_current_plane(target)
    header, header_binding, code_bytes = (
        PRODUCT.resolved_compiler_consumed_static_header())
    require(header is not None and header_binding is not None
            and code_bytes is not None, "candidate compiler resolver absent")
    bank2 = target / "v6-semantics/bank2-static-code.bin"
    require(code_bytes == bank2.stat().st_size
            and bind(bank2)["sha256"]
                == load(CARD.PLANE_RECEIPT)["geometry"]["sha256"]
            and macro_value(header) == code_bytes,
            "living compiler projection is not candidate-derived")

    consumers: list[dict[str, Any]] = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        assertion = CARD.BUILD / "wplto" / (
            stem + ".compiler-input-assert.h")
        order = [header.relative_to(ROOT).as_posix(),
                 assertion.relative_to(ROOT).as_posix()]
        report: dict[str, object] = {
            "force_include_order": order,
            "bound_header": dict(header_binding),
            "consumed_value": code_bytes,
        }
        flags = ["-Oz", "-include", order[0], "-include", order[1]]
        PRODUCT.materialized_compiler_static_header_gate(flags, report)
        require(report["status"] ==
                    "passed-bound-candidate-header-consumed"
                and report["materialized_header"] == header_binding
                and report["materialized_value"] == code_bytes,
                f"living compiler projection red: {stem}")
        consumers.append({"target": stem + ".prg",
            "materialized_force_include_flags": report[
                "actual_force_include_flags"],
            "materialized_header": report["materialized_header"],
            "materialized_value": report["materialized_value"]})

    # An inherited historical configurator may still run later.  The
    # consumer-time resolver must dominate it.
    historical_binding = bind(HISTORICAL_HEADER)
    historical_value = macro_value(HISTORICAL_HEADER)
    PRODUCT.configure_compiler_consumed_static_header(
        HISTORICAL_HEADER, historical_binding, historical_value)
    late_header, late_binding, late_value = (
        PRODUCT.resolved_compiler_consumed_static_header())
    require((late_header, late_binding, late_value)
            == (header, header_binding, code_bytes),
            "historical configurator displaced consumer-time authority")

    mutations: dict[str, Callable[[], None]] = {
        "candidate-path-with-historical-value": lambda:
            PRODUCT.validate_materialized_static_header(
                header_binding, code_bytes, header_binding, historical_value),
        "historical-path-with-candidate-value": lambda:
            PRODUCT.validate_materialized_static_header(
                header_binding, code_bytes, historical_binding, code_bytes),
    }
    rejected: list[str] = []
    for name, mutation in mutations.items():
        try:
            mutation()
        except RuntimeError:
            rejected.append(name)
    require(rejected == list(mutations),
            "compiler path/value divergence mutation survived")
    return {"status": "PASS: CANDIDATE HEADER PROJECTS AT BOTH REAL CONSUMERS",
        "candidate_plane": bind(bank2), "candidate_header": header_binding,
        "derived_value": code_bytes, "consumers": consumers,
        "late_historical_rebind_rejected": True,
        "mutations_rejected": rejected,
        "prover": bind(Path(PRODUCT.__file__))}


def positions(body: bytes, pattern: bytes) -> list[int]:
    return [index for index in range(len(body))
            if body.startswith(pattern, index)]


def frozen_elf_dependency(candidate_value: int) -> dict[str, Any]:
    predecessor = load(PREDECESSOR)
    old_values = predecessor["stopper"]["observed_values"]
    require(len(old_values) == 2 and old_values[0] == old_values[1]
            and old_values[0] != candidate_value,
            "predecessor static-extent worlds are not distinct")
    historical_value = int(old_values[0])
    source = GENERATED.read_text(encoding="utf-8")
    truth = ElfTruth.read(CARD.ELF, llvm_readobj=CARD.BASE.READOBJ,
                          include_section_data=True)
    rows: list[dict[str, Any]] = []
    for name in FUNCTIONS:
        definition = CARD.V6.c_function_definition(source, name)
        require(definition.count("LISP65_C2_LITE_STATIC_CODE_BYTES") == 1,
                f"static extent source consumer drift: {name}")
        symbol = truth.symbol(name)
        section = truth.sections_by_index[symbol.section_index]
        body = truth.section_bytes(section.name)
        require(symbol.value == section.address
                and symbol.bytes == section.bytes == len(body),
                f"function/section body identity drift: {name}")
        old_hi = bytes((0xC9, (historical_value >> 8) & 0xFF))
        old_lo = bytes((0xC9, historical_value & 0xFF))
        new_hi = bytes((0xC9, (candidate_value >> 8) & 0xFF))
        new_lo = bytes((0xC9, candidate_value & 0xFF))
        old_hi_at = positions(body, old_hi); old_lo_at = positions(body, old_lo)
        new_hi_at = positions(body, new_hi); new_lo_at = positions(body, new_lo)
        require(len(old_hi_at) == len(old_lo_at) == 1
                and 0 < old_lo_at[0] - old_hi_at[0] <= 16
                and not new_hi_at and not new_lo_at,
                f"final ELF extent immediate attribution drift: {name}")
        rows.append({"function": name, "source": bind(GENERATED),
            "source_macro_uses": 1,
            "ELF_symbol": {"section": symbol.section,
                "section_index": symbol.section_index,
                "address": symbol.value, "bytes": symbol.bytes},
            "historical_immediate": {"value": historical_value,
                "hex": f"0x{historical_value:04x}",
                "high_compare_offset": old_hi_at[0],
                "low_compare_offset": old_lo_at[0]},
            "candidate_immediate": {"value": candidate_value,
                "hex": f"0x{candidate_value:04x}",
                "high_compare_offsets": new_hi_at,
                "low_compare_offsets": new_lo_at}})
    return {"depends_on_historical_value": True,
        "historical_value": historical_value,
        "candidate_value": candidate_value,
        "difference_bytes": candidate_value - historical_value,
        "derivation": ("Each generated source function consumes the extent "
            "macro once; its exact ElfTruth-owned function section contains "
            "the historical high/low CMP immediates and no candidate pair."),
        "functions": rows}


def validate_execution(value: dict[str, int]) -> None:
    require(value == {"read_only_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "scope_runs": 0,
        "acceptance_runs": 0, "media_builds": 0, "device_contacts": 0},
        "header-rebind resume attempted unauthorized work")


def execution_mutations(value: dict[str, int]) -> list[str]:
    cases = {"rebuild-WPLTO": "WPLTO_runs", "relink-product": "product_links",
             "consume-card": "cards_consumed", "run-Scope": "scope_runs",
             "run-Acceptance": "acceptance_runs"}
    rejected: list[str] = []
    for name, key in cases.items():
        trial = deepcopy(value); trial[key] = 1
        try:
            validate_execution(trial)
        except ResumeError:
            rejected.append(name)
    require(rejected == list(cases), "read-only execution mutation survived")
    return rejected


def validate(value: dict[str, Any]) -> None:
    require(value["status"] ==
                "RESUME RED: FROZEN CARD3 PAIR DEPENDS ON STALE STATIC EXTENT"
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["living_compiler_projection"]["derived_value"] == 52230
            and len(value["living_compiler_projection"]["consumers"]) == 2
            and value["final_ELF_dependency"]["depends_on_historical_value"]
                is True
            and value["final_ELF_dependency"]["historical_value"] == 46043
            and value["pair_disposition"] == "DEAD"
            and value["new_product_link_authorized"] is False,
            "header-rebind resume receipt drift")
    validate_execution(value["attempt_accounting"])


def resume() -> None:
    require(not RECEIPT.exists() and not CARD.RECEIPT.exists()
            and not (CARD.BUILD / "owner-scope-result.json").exists()
            and not (CARD.BUILD / "artifact-acceptance.json").exists(),
            "header-rebind resume lifecycle drift")
    predecessor = load(PREDECESSOR)
    require(predecessor["status"] ==
                "QUALIFICATION RED: CARD3 BANK2 PLANE BOUND BUT NOT COMPILED"
            and predecessor["attempt_accounting"]["WPLTO_runs"] == 0
            and predecessor["attempt_accounting"]["product_links"] == 0,
            "compiler-consumption predecessor drift")
    auth = authority()
    before = frozen_pair()
    projection = living_compiler_projection()
    dependency = frozen_elf_dependency(projection["derived_value"])
    require(dependency["depends_on_historical_value"] is True,
            "unexpected no-dependency branch requires qualification continuation")
    after = frozen_pair()
    require(before == after, "read-only dependency analysis changed frozen pair")
    execution = {"read_only_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "scope_runs": 0,
        "acceptance_runs": 0, "media_builds": 0, "device_contacts": 0}
    validate_execution(execution)
    value = {
        "format": "lisp65-c2-v17-card3-header-rebind-resume-red-v1",
        "recorded_on": "2026-08-26",
        "status": "RESUME RED: FROZEN CARD3 PAIR DEPENDS ON STALE STATIC EXTENT",
        "authority": {"review": auth, "predecessor": bind(PREDECESSOR),
            "driver": bind(DRIVER)},
        "frozen_pair_before": before, "frozen_pair_after": after,
        "living_compiler_projection": projection,
        "final_ELF_dependency": dependency,
        "pair_disposition": "DEAD",
        "scope_and_acceptance_skipped": True,
        "attempt_accounting": execution,
        "unauthorized_work_mutations_rejected": execution_mutations(execution),
        "new_product_link_authorized": False,
        "review_disposition_required": True,
        "published_v1_6_history_reopened": False,
        "claim_limit": ("Living compiler binding repaired and frozen card-3 "
            "pair declared dead from final-ELF evidence; no build, link, card, "
            "Scope, Acceptance, media, device or historical-release claim."),
        "next": "return to review for any new WPLTO/product-link authority",
    }
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink: HEADER RESUME RED pair=DEAD "
          "52230!=46043 scope=0 acceptance=0 WPLTO=0 link=0")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(value["frozen_pair_before"] == frozen_pair()
            and value["frozen_pair_after"] == frozen_pair(),
            "dead frozen pair identity changed after resume")
    print("v1.7 IDE idle/blink: HEADER RESUME CHECK DEAD pair=exact")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resume", "check"))
    {"resume": resume, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
