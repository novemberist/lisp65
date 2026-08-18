#!/usr/bin/env python3
"""Bind the nine Link-97 replacement-gate names by semantic identity.

The historical replacement gate named nine pre-split/pre-fusion runtime
slices.  This desk-only gate proves whether their obligations are present in
the green Link-95/96 worlds and the frozen Link-97 ELF.  It deliberately does
not complete artifacts, build media, compile, link, or run hardware.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HISTORICAL_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-nine-slice-content-map-receipt.json")
REBOUND_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-nine-slice-content-map-rebind-receipt.json")
RECEIPT = (REBOUND_RECEIPT if REBOUND_RECEIPT.is_file()
           else HISTORICAL_RECEIPT)
FIRST_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r2-first-red.json")
GATE_SOURCE = ROOT / "tools/host-lisp/c2_lite_v6_boot_crc_abi_successor_link.py"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
SEMANTIC_SPLIT_SOURCE = ROOT / "tools/host-lisp/c2_lite_v6_semantic_split_probe.py"
CORESIDENT_SOURCE = ROOT / "tools/host-lisp/c2_lite_v6_coresident_diet_probe.py"
PHASE11_RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-phase11-split-e000-analysis-receipt.json")
CORESIDENT_RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-coresident-diet-successor-gate-replay3-receipt.json")
FINAL_APPEND_RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-artifact-replay3-receipt.json")

WORLD_ROOTS = {
    "link95": ROOT / "build/c2.3/packed-callee-closure-link95/final",
    "link96": ROOT / "build/c2.3/terminal-return-guard-link96/final",
    "link97": ROOT / "build/c2.3/v1.5.0-candidate-product-link97/wplto",
}


class ContentMapError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContentMapError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"content-map authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


# Each row binds an old vocabulary item to its semantic successor sections and
# the concrete functions that carry those duties.  A shared successor is
# intentional for fused rows; it is identity, not ordinal or one-to-one naming.
CONTENT_MAP: dict[str, dict[str, Any]] = {
    ".lisp65_rt_c2d_05": {
        "duties": [
            "validate and decode the phase-05 descriptor stream",
            "preserve the phase-05 handoff before later decoding",
        ],
        "successors": {
            ".lisp65_rt_c2d_05a": ("c2_stream_phase_05a",),
            ".lisp65_rt_c2d_05b": ("c2_stream_phase_05b",),
        },
    },
    ".lisp65_rt_c2d_11": {
        "duties": [
            "validate immutable pair descriptors and backward child ordinals",
            "resolve children, allocate pairs, publish roots and run the GC checkpoint",
        ],
        "successors": {
            ".lisp65_rt_c2d_11a": ("c2_stream_phase_11a",),
            ".lisp65_rt_c2d_11b": ("c2_stream_phase_11b",),
        },
    },
    ".lisp65_rt_c2append_crc": {
        "duties": [
            "calculate staged CRC-32 values",
            "validate envelope, code, metadata and combined CRC fields",
        ],
        "successors": {
            ".lisp65_rt_c2append_crc_metadata": (
                "c2_stage_crc", "c2_append_crc_metadata_phase"),
        },
    },
    ".lisp65_rt_c2append_metadata": {
        "duties": [
            "validate staged C2 metadata shape, counts and offsets",
            "derive entry, literal and root counts for the append transaction",
        ],
        "successors": {
            ".lisp65_rt_c2append_crc_metadata": (
                "c2_stage_crc", "c2_append_crc_metadata_phase"),
        },
    },
    ".lisp65_rt_c2append_capacity": {
        "duties": [
            "derive roots and current Bank-2/session fronts",
            "bound transient and persistent directory/code reservations",
        ],
        "successors": {
            ".lisp65_rt_c2append_roots_fronts": (
                "c2_append_roots_phase", "c2_append_fronts_phase",
                "c2_append_roots_fronts_phase"),
            ".lisp65_rt_c2append_reserve_transient_bounds": (
                "c2_append_reserve_transient_bounds_phase",),
            ".lisp65_rt_c2append_reserve_transient_code": (
                "c2_append_reserve_transient_code_phase",),
            ".lisp65_rt_c2append_reserve_persistent_bounds": (
                "c2_append_reserve_persistent_bounds_phase",),
            ".lisp65_rt_c2append_reserve_persistent_code": (
                "c2_append_reserve_persistent_code_phase",),
        },
    },
    ".lisp65_rt_c2append_stage": {
        "duties": [
            "copy staged payload into its owned code/session destination",
            "materialize the mutable C2D image, entry, resolution and root plane",
        ],
        "successors": {
            ".lisp65_rt_c2append_stage_copy": (
                "c2_append_stage_copy_phase",),
            ".lisp65_rt_c2append_stage_plane": (
                "c2_append_stage_plane_phase",),
        },
    },
    ".lisp65_rt_c2append_publish_names": {
        "duties": [
            "validate and resolve every export name before publication",
            "keep the publication plan free of partial callable state",
        ],
        "successors": {
            ".lisp65_rt_c2append_publish_clear": (
                "c2_append_publish_exports_phase",),
        },
    },
    ".lisp65_rt_c2append_publish_cells": {
        "duties": [
            "journal prior function-cell values and publish new callable cells",
            "clear publication state only after the publish-last boundary",
        ],
        "successors": {
            ".lisp65_rt_c2append_publish_clear": (
                "c2_append_publish_exports_phase",),
        },
    },
    ".lisp65_rt_c2append_rollback": {
        "duties": [
            "unpublish changed function cells",
            "wipe staged C2D, chip-code and attic payloads",
            "restore header/runtime state and finalize rollback",
        ],
        "successors": {
            ".lisp65_rt_c2append_rollback_unpublish": (
                "c2_append_rollback_unpublish_phase",),
            ".lisp65_rt_c2append_rollback_wipe_plane": (
                "c2_append_rollback_wipe_plane_phase",),
            ".lisp65_rt_c2append_rollback_wipe_chip": (
                "c2_append_rollback_wipe_chip_phase",),
            ".lisp65_rt_c2append_rollback_wipe_attic": (
                "c2_append_rollback_wipe_attic_phase",),
            ".lisp65_rt_c2append_rollback_finalize": (
                "c2_append_rollback_finalize_phase",),
        },
    },
}


def expand_historical_sections(names: Iterable[str],
                               present: Iterable[str] = ()) -> tuple[str, ...]:
    """Resolve old vocabulary without breaking a genuine pre-split ELF.

    If an old section is physically present, it remains authoritative for that
    old artifact.  If it is absent, its semantic successors become the wall.
    A partial successor set remains expanded so the missing member fails loud.
    """
    available = set(present)
    expanded: list[str] = []
    for name in names:
        row = CONTENT_MAP.get(name)
        replacements = tuple(row["successors"]) if row else (name,)
        selected = (name,) if name in available else replacements
        for item in selected:
            if item not in expanded:
                expanded.append(item)
    return tuple(expanded)


def checker_input_closure_gate(source: str | None = None) -> dict[str, Any]:
    """Prove the family checker reads only the supplied ELF artifact set."""
    text = GATE_SOURCE.read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    function = next((node for node in tree.body
                     if isinstance(node, ast.FunctionDef)
                     and node.name == "walls_and_family"), None)
    require(function is not None, "replacement family checker absent")
    loaded_names = {node.id for node in ast.walk(function)
                    if isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)}
    expressions = {ast.unparse(node) for node in ast.walk(function)}
    require("OUT" not in loaded_names and "elf.parent" in expressions,
            "family checker reads module-global context outside supplied ELF")
    return {
        "status": "passed-explicit-ELF-artifact-set-only",
        "artifact_root": "elf.parent",
        "module_global_OUT_reads": 0,
        "rule": (
            "A qualification stage reads only its supplied artifact set, "
            "never ambient or module-global output state."),
    }


def checker_input_closure_mutations() -> list[str]:
    source = GATE_SOURCE.read_text(encoding="utf-8")
    anchor = "family_root = elf.parent"
    require(anchor in source, "checker input-closure mutation anchor absent")
    mutant = source.replace(anchor, "family_root = OUT", 1)
    rejected: list[str] = []
    try:
        checker_input_closure_gate(mutant)
    except ContentMapError:
        rejected.append("restore-module-global-OUT")
    require(rejected == ["restore-module-global-OUT"],
            "module-global checker context mutation survived")
    return rejected


def transition_authorities() -> dict[str, Any]:
    split_source = SEMANTIC_SPLIT_SOURCE.read_text(encoding="utf-8")
    diet_source = CORESIDENT_SOURCE.read_text(encoding="utf-8")
    runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")
    phase11 = json.loads(PHASE11_RECEIPT.read_text(encoding="utf-8"))
    diet = json.loads(CORESIDENT_RECEIPT.read_text(encoding="utf-8"))
    final = json.loads(FINAL_APPEND_RECEIPT.read_text(encoding="utf-8"))
    phase11_boundary = phase11["phase11_split"]["semantic_boundary"]
    diet_checks = diet["product_semantics"]["checks"]
    final_checks = final["fresh_read_only_replay"]["product_semantics"]["checks"]
    require(
        'replace_slice(decoder, "05"' in split_source
        and '("05a", "c2_stream_phase_05a")' in split_source
        and '("05b", "c2_stream_phase_05b")' in split_source
        and 'replace_slice(append, "stage"' in split_source
        and '"stage_copy"' in split_source and '"stage_plane"' in split_source,
        "semantic split transition authority drift",
    )
    require(
        'fuse_pair(append, "crc", "metadata"' in diet_source
        and 'fuse_pair(append, "publish_names", "publish_cells"' in diet_source
        and diet_checks["only_fused_crc_metadata_emitted"] is True
        and diet_checks["only_fused_publication_emitted"] is True
        and final_checks["only_fused_crc_metadata_emitted"] is True
        and final_checks["only_fused_publication_emitted"] is True,
        "fusion transition authority drift",
    )
    require(
        phase11_boundary["11a"].startswith("validate every immutable pair")
        and phase11_boundary["11b"].startswith("resolve children")
        and phase11["phase11_split"]["cutpoint_gate"]["status"] == "passed"
        and all(name in runtime for name in (
            "c2_append_roots_fronts_phase",
            "c2_append_reserve_transient_bounds_phase",
            "c2_append_reserve_transient_code_phase",
            "c2_append_reserve_persistent_bounds_phase",
            "c2_append_reserve_persistent_code_phase",
            "c2_append_rollback_unpublish_phase",
            "c2_append_rollback_wipe_plane_phase",
            "c2_append_rollback_wipe_chip_phase",
            "c2_append_rollback_wipe_attic_phase",
            "c2_append_rollback_finalize_phase",
        )),
        "phase-11/capacity/rollback transition authority drift",
    )
    return {
        "semantic_split_source": bind(SEMANTIC_SPLIT_SOURCE),
        "coresident_fusion_source": bind(CORESIDENT_SOURCE),
        "runtime_source": bind(RUNTIME_SOURCE),
        "phase11_semantic_boundary": phase11_boundary,
        "phase11_receipt": bind(PHASE11_RECEIPT),
        "coresident_fusion_receipt": bind(CORESIDENT_RECEIPT),
        "final_append_receipt": bind(FINAL_APPEND_RECEIPT),
        "proven_fusions": {
            "crc_metadata": True,
            "publication": True,
        },
    }


def world_paths(root: Path) -> tuple[Path, dict[str, Path]]:
    elf = root / "lisp65-c2-substitution-linked.prg.elf"
    manifests = {
        family: root / f"runtime-overlays-{family}-final.json"
        for family in ("boot", "session")
    }
    return elf, manifests


def collect_world(name: str, root: Path) -> dict[str, Any]:
    elf, manifests = world_paths(root)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    documents = {family: json.loads(path.read_text(encoding="utf-8"))
                 for family, path in manifests.items()}
    orders = {family: [row["section"] for row in document["slices"]]
              for family, document in documents.items()}
    all_rows = {row["section"]: row for document in documents.values()
                for row in document["slices"]}
    mapped: dict[str, Any] = {}
    for old, spec in CONTENT_MAP.items():
        successors: dict[str, Any] = {}
        for section_name, required_functions in spec["successors"].items():
            section = truth.section(section_name)
            functions = sorted(symbol.name for symbol in truth.symbols
                               if symbol.section == section_name
                               and symbol.symbol_type == "Function")
            require(section_name in all_rows,
                    f"{name}: successor absent from media manifest: {section_name}")
            require(all(function in functions for function in required_functions),
                    f"{name}: successor function absent: {old}/{section_name}")
            manifest = all_rows[section_name]
            successors[section_name] = {
                "ELF": {
                    "address": section.address,
                    "bytes": section.bytes,
                    "functions": functions,
                },
                "runtime_slice": {
                    "name": manifest["name"],
                    "file_size": manifest["file_size"],
                    "crc16": manifest["crc16"],
                    "record_crc16": manifest["record_crc16"],
                    "sha256": manifest["sha256"],
                },
            }
        mapped[old] = {
            "historical_section_in_ELF": old in truth.sections_by_name,
            "historical_section_in_manifests": old in all_rows,
            "successors": successors,
        }
    return {
        "ELF": bind(elf),
        "manifests": {family: bind(path)
                      for family, path in manifests.items()},
        "ordered_sections": orders,
        "content": mapped,
    }


def collect() -> dict[str, Any]:
    worlds = {name: collect_world(name, root)
              for name, root in WORLD_ROOTS.items()}
    reference_orders = worlds["link96"]["ordered_sections"]
    require(worlds["link95"]["ordered_sections"] == reference_orders
            and worlds["link97"]["ordered_sections"] == reference_orders,
            "Link-95/96/97 runtime-family section identities differ")
    entries: dict[str, Any] = {}
    for old, spec in CONTENT_MAP.items():
        entries[old] = {
            "classification": "vocabulary-successor-content-present",
            "semantic_duties": spec["duties"],
            "successor_sections": list(spec["successors"]),
            "required_functions": {
                section: list(functions)
                for section, functions in spec["successors"].items()
            },
            "worlds": {
                name: world["content"][old] for name, world in worlds.items()
            },
        }
    value = {
        "format": "lisp65-c2.3-v150-link97-nine-slice-content-map-v1",
        "recorded_on": "2026-08-11",
        "status": "passed-nine-vocabulary-successors-zero-freight-gaps",
        "scope": {
            "product_links": 0,
            "compiler_or_WPLTO_runs": 0,
            "artifact_completions": 0,
            "media_builds": 0,
            "hardware_runs": 0,
            "frozen_Link97_artifacts_modified": False,
        },
        "authorities": {
            "commission": "ece93d1a",
            "first_red": bind(FIRST_RED),
            "content_map_tool": bind(Path(__file__)),
            "replacement_gate": bind(GATE_SOURCE),
            "checker_input_closure": checker_input_closure_gate(),
            "checker_input_closure_mutations_rejected":
                checker_input_closure_mutations(),
            "transitions": transition_authorities(),
        },
        "world_identity": {
            "ordered_boot_sections_equal": True,
            "ordered_session_sections_equal": True,
            "reference_world": "link96",
            "worlds": worlds,
        },
        "content_map": entries,
        "decision": {
            "vocabulary_cases": len(entries),
            "freight_cases": 0,
            "mixed_result": False,
            "replacement_gate_action": (
                "resolve each absent historical identity to its explicit "
                "semantic successors; never require the pinned old name"),
            "card_or_replay_authorized": False,
        },
        "claim_limit": (
            "Desk-only attribution of the nine Link-97 slice-wall names. "
            "No artifact completion, media, replay, card, device, Halt #1, "
            "release or publication claim."),
    }
    validate(value, verify=True)
    return value


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format")
            == "lisp65-c2.3-v150-link97-nine-slice-content-map-v1"
            and value.get("status")
            == "passed-nine-vocabulary-successors-zero-freight-gaps",
            "content-map status/format drift")
    decision = value.get("decision", {})
    require(decision.get("vocabulary_cases") == 9
            and decision.get("freight_cases") == 0
            and decision.get("mixed_result") is False
            and decision.get("card_or_replay_authorized") is False,
            "content-map decision drift")
    rebind = value.get("authority_rebind")
    if rebind is not None:
        require(
            rebind.get("authorization_commit") == "37f12ed3"
            and rebind.get("recorded_on") == "2026-08-11"
            and rebind.get("semantic_rows_reasserted") == 9
            and rebind.get("semantic_rows_inherited") == 0
            and rebind.get("prior_replacement_source", {}).get("sha256")
                == "349bf9437e13c582565a88d1e88809d80338c531475debf9c76d633c564a85f3"
            and rebind.get("current_replacement_source")
                == value.get("authorities", {}).get("replacement_gate"),
            "content-map authority-rebind ancestry drift")
    entries = value.get("content_map", {})
    require(set(entries) == set(CONTENT_MAP),
            "content-map historic identity set drift")
    for old, spec in CONTENT_MAP.items():
        row = entries[old]
        expected_sections = list(spec["successors"])
        require(row.get("classification")
                == "vocabulary-successor-content-present"
                and row.get("semantic_duties") == spec["duties"]
                and row.get("successor_sections") == expected_sections
                and row.get("required_functions") == {
                    section: list(functions)
                    for section, functions in spec["successors"].items()},
                f"content-map semantic identity drift: {old}")
        require(set(row.get("worlds", {})) == set(WORLD_ROOTS),
                f"content-map world coverage drift: {old}")
        for world_name, evidence in row["worlds"].items():
            require(evidence.get("historical_section_in_ELF") is False
                    and evidence.get("historical_section_in_manifests") is False
                    and set(evidence.get("successors", {}))
                        == set(expected_sections),
                    f"pinned or missing successor identity: {world_name}/{old}")
            for section, functions in spec["successors"].items():
                successor = evidence["successors"][section]
                elf = successor["ELF"]
                media = successor["runtime_slice"]
                require(0 < elf["bytes"] <= 1792
                        and all(function in elf["functions"]
                                for function in functions)
                        and media["file_size"] == elf["bytes"]
                        and len(media["sha256"]) == 64,
                        f"successor content/CRC duty absent: {world_name}/{old}")
    identity = value.get("world_identity", {})
    require(identity.get("ordered_boot_sections_equal") is True
            and identity.get("ordered_session_sections_equal") is True,
            "cross-world runtime-family identity drift")
    worlds = identity.get("worlds", {})
    require(set(worlds) == set(WORLD_ROOTS)
            and worlds["link95"]["ordered_sections"]
                == worlds["link96"]["ordered_sections"]
                == worlds["link97"]["ordered_sections"],
            "Link-95/96/97 ordered section identity drift")
    if verify:
        for world_name, root in WORLD_ROOTS.items():
            elf, manifests = world_paths(root)
            require(worlds[world_name]["ELF"] == bind(elf)
                    and worlds[world_name]["manifests"] == {
                        family: bind(path) for family, path in manifests.items()},
                    f"content-map artifact binding drift: {world_name}")
        authorities = value.get("authorities", {})
        require(authorities.get("first_red") == bind(FIRST_RED)
                and authorities.get("content_map_tool") == bind(Path(__file__))
                and authorities.get("replacement_gate") == bind(GATE_SOURCE)
                and authorities.get("checker_input_closure")
                    == checker_input_closure_gate()
                and authorities.get(
                    "checker_input_closure_mutations_rejected")
                    == checker_input_closure_mutations(),
                "content-map authority drift")
        transition_authorities()


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Any] = {}
    for old in CONTENT_MAP:
        cases[f"pin-historical-name:{old}"] = (
            lambda candidate, old=old:
                candidate["content_map"][old].update(
                    successor_sections=[old]))
    cases.update({
        "drop-link97-successor": lambda candidate: next(iter(
            candidate["content_map"].values()))["worlds"]["link97"]
                ["successors"].popitem(),
        "drop-required-function": lambda candidate: next(iter(next(iter(
            candidate["content_map"].values()))["worlds"]["link97"]
                ["successors"].values()))["ELF"].update(functions=[]),
        "change-session-order": lambda candidate: candidate["world_identity"]
            ["worlds"]["link97"]["ordered_sections"]["session"].reverse(),
        "claim-freight": lambda candidate: candidate["decision"].update(
            freight_cases=1, vocabulary_cases=8, mixed_result=True),
    })
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except (ContentMapError, KeyError):
            rejected.append(name)
    require(rejected == list(cases), "content-map mutation survived")
    return rejected


def selftest() -> int:
    checker_input_closure_gate()
    checker_input_closure_mutations()
    old = tuple(CONTENT_MAP)
    present = {section for spec in CONTENT_MAP.values()
               for section in spec["successors"]}
    expanded = expand_historical_sections(old, present)
    require(not (set(old) & set(expanded)) and set(expanded) == present,
            "historical-name expansion pins old vocabulary")
    pre_split = expand_historical_sections(old, old)
    require(pre_split == old, "pre-split artifact identity was not preserved")
    value = collect()
    mutations(value)
    print("v1.5 Link-97 nine-slice content-map selftest: PASS "
          "vocabulary=9 freight=0")
    return 0


def capture() -> int:
    value = collect()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 nine-slice content map: PASS "
          f"vocabulary={value['decision']['vocabulary_cases']} freight=0")
    return 0


def rebind() -> int:
    require(HISTORICAL_RECEIPT.is_file() and not REBOUND_RECEIPT.exists(),
            "content-map rebind boundary is not fresh")
    historical = json.loads(HISTORICAL_RECEIPT.read_text(encoding="utf-8"))
    prior_source = historical["authorities"]["replacement_gate"]
    require(
        historical.get("status")
            == "passed-nine-vocabulary-successors-zero-freight-gaps"
        and historical.get("decision", {}).get("vocabulary_cases") == 9
        and prior_source.get("sha256")
            == "349bf9437e13c582565a88d1e88809d80338c531475debf9c76d633c564a85f3",
        "historical content-map rebind ancestry drift")
    value = collect()
    value["authority_rebind"] = {
        "recorded_on": "2026-08-11",
        "authorization_commit": "37f12ed3",
        "classification": "semantic-preserving-source-authority-rebind",
        "prior_receipt": bind(HISTORICAL_RECEIPT),
        "prior_replacement_source": prior_source,
        "current_replacement_source": value["authorities"]["replacement_gate"],
        "semantic_rows_reasserted": value["decision"]["vocabulary_cases"],
        "semantic_rows_inherited": 0,
        "rule": (
            "All nine content identities are recalculated from the three "
            "bound worlds under the current replacement source; only the "
            "source-authority binding descends from the historical receipt."),
    }
    validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    REBOUND_RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 nine-slice content-map rebind: PASS "
          "reasserted=9 inherited=0")
    return 0


def check() -> int:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "content-map mutation receipt drift")
    print("v1.5 Link-97 nine-slice content-map check: PASS "
          "vocabulary=9 freight=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("capture", "rebind", "check", "selftest"))
    args = parser.parse_args()
    return {"capture": capture, "rebind": rebind, "check": check,
            "selftest": selftest}[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
