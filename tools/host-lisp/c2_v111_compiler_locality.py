#!/usr/bin/env python3
"""Permanent host gate for the 1.11 compiler-carrier locality block.

The exact 1.10 defstruct candidate and pricing remain the ruler.  This gate
regenerates the host-only C2 compiler candidate, substitutes it only for the
historical Link-82 carrier in the already bound reconstruction, and proves
that the emitted definitions are unchanged while the carrier work shrinks.
It makes no product, release, link, device, or wall-time claim.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v111_compiler_tier as TIER  # noqa: E402
import c2_v16_defstruct_phase_a as PHASE_A  # noqa: E402
import c2_v110_persistent_performance as V110  # noqa: E402
import comfort_track_gate as COMFORT  # noqa: E402


CONTRACT = ROOT / "config/c2-v111-compiler-locality.json"
PLAN = ROOT / "docs/planning/1.11-compiler-locality-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.11-compiler-locality-receipt.json"
)
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.11-release-promotion-rebind-2026-08-07.json"
)
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
OWNER_COMMIT = "06198df1"
CLOSURE_COMMIT = "e9024b5c"
HISTORICAL_RECEIPT_COMMIT = "f2096e5b"
FORMAT = "lisp65-c2.3-v1.11-compiler-locality-v1"
RECORDED_ON = "2026-08-07"


class LocalityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LocalityError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE,
    ).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE,
    ).stdout
    return {"commit": full, "path": path, "bytes": len(raw), "sha256": sha(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def gate_wiring_projection() -> dict[str, Any]:
    text = GATES.read_text(encoding="utf-8")
    required = [
        "c2-v111-compiler-locality-selftest:",
        "python3 tools/host-lisp/c2_v111_compiler_locality.py selftest",
        "c2-v111-compiler-locality-check: c2-v111-compiler-locality-selftest",
        "python3 tools/host-lisp/c2_v111_compiler_locality.py check",
        "check-source: c2-v111-compiler-locality-check",
    ]
    require(all(row in text for row in required),
            "1.11 permanent gate wiring absent")
    return {
        "path": "mk/gates.mk",
        "selftest_target": "c2-v111-compiler-locality-selftest",
        "check_target": "c2-v111-compiler-locality-check",
        "check_source_dependency": "check-source: c2-v111-compiler-locality-check",
        "semantic_projection": required,
    }


def json_pointer(value: Any, pointer: str) -> Any:
    require(pointer.startswith("/"), "JSON pointer must be absolute")
    current = value
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        require(isinstance(current, dict) and key in current,
                f"JSON pointer absent: {pointer}")
        current = current[key]
    return current


def audit_contract(contract: dict[str, Any]) -> None:
    require(contract.get("format") ==
            "lisp65-c2-v111-compiler-locality-contract-v1",
            "1.11 contract format drift")
    require(contract.get("scope") == {
        "execution": "host-only",
        "placement": "Bank 2 compiler carrier",
        "resident_delta_bytes": 0,
        "device_contacts": 0,
        "product_links": 0,
        "release_claim": False,
        "public_surface_claim": False,
        "packaging_deferred_to_release_block": True,
    }, "1.11 scope broadened")
    require(contract.get("target") == {
        "post_require_operational_floor_seconds_lt": 180,
        "persistent_appends": 9,
        "generated_definition_bytes": 182,
        "final_journal": "CLEAR",
    }, "1.11 target/semantic wall drift")
    require(contract["candidate"]["private_inline_functions"]
            == list(TIER.PRIVATE_INLINE), "private-inline contract drift")
    require(contract["candidate"]["generator"] ==
            "tools/host-lisp/c2_v111_compiler_tier.py"
            and contract["candidate"]["base_generator"] ==
            "tools/host-lisp/c2_product_compiler_tier.py"
            and contract["candidate"]["profile_source"] ==
            "lib/dialect-v2/lcc-locality-candidate.lisp",
            "candidate escaped its host-only overlay")
    graph = contract["graph"]
    require(graph == {
        "comfort_contract": "config/comfort-track-contract.json",
        "edge_authority": "directory_only.entry_refs",
        "comfort_exact_edges": 109,
        "baseline_carrier_edges": 306,
        "candidate_carrier_edges": 270,
    }, "call-edge contract drift")


def build_carrier(contract: dict[str, Any]) -> dict[str, Any]:
    candidate = contract["candidate"]
    suite_path = ROOT / candidate["suite"]
    generation = TIER.generate(suite_path)
    write_json(ROOT / candidate["generation_receipt"], generation)
    suite = STD._read_suite(str(suite_path))
    checked = STD.check_suite(str(suite_path), suite)
    prefix = ROOT / candidate["artifact_prefix"]
    info = STD.emit_artifacts(
        str(suite_path), suite, str(prefix), base_addr=0,
        artifact_role="disk-lib",
    )
    manifest_path = prefix.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    require(manifest["private_inline_functions"] == list(TIER.PRIVATE_INLINE)
            and manifest["cost"]["private_inline_gate"] == {
                "expansions": 73,
                "functions": 10,
                "names": list(TIER.PRIVATE_INLINE),
                "resident_functions": 0,
            }, "private-inline execution closure drift")
    return {
        "suite_path": suite_path,
        "generation": generation,
        "checked": checked,
        "emit": info,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def carrier_class(manifest_path: Path) -> type[PHASE_A.HistoricalCarrier]:
    class CandidateCarrier(PHASE_A.HistoricalCarrier):
        def __init__(self) -> None:
            self.manifest = load(manifest_path)
            suite_path = Path(self.manifest["suite"])
            if not suite_path.is_absolute():
                suite_path = ROOT / suite_path
            self.suite = load(suite_path)
            self.source_binding = {
                "mode": "v1.11-current-source-generated-carrier",
                "manifest": bind(manifest_path),
            }
            blob_path = Path(self.manifest["blob"])
            if not blob_path.is_absolute():
                blob_path = ROOT / blob_path
            self.blob = blob_path.read_bytes()
            require(sha(self.blob) == self.manifest["blob_sha256"],
                    "candidate carrier blob drift")
            patches = {
                int(row["blob_offset"]): int(row["node"])
                for row in self.manifest["literal_patches"]
            }
            self.heap = C.prepare_heap([])
            self.directory: dict[int, B.CodeObject] = {}
            self.macro_symbols: set[int] = set()
            self.code_names: dict[int, str] = {}
            for entry in self.manifest["entries"]:
                code = STD._patched_code_from_manifest_entry(
                    self.heap, self.manifest, self.blob, entry, patches
                )
                symbol = self.heap.intern(entry["name"])
                require(symbol not in self.directory,
                        "duplicate candidate carrier entry")
                self.directory[symbol] = code
                self.code_names[id(code)] = entry["name"]
                if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
                    self.macro_symbols.add(symbol)
            resident_names, resident_code, resident_flags = (
                STD._compile_resident_code(self.suite, self.heap)
            )
            overrides = set(STD._as_list(self.suite.get("resident_overrides")))
            STD._add_code_to_directory(
                self.heap, self.directory,
                [name for name in resident_names if name not in overrides],
                resident_code, "v1.11 candidate carrier resident suite",
            )
            self.macro_symbols.update(
                STD._macro_symbol_objs(self.heap, resident_flags)
            )
            self.code_names.update(
                {id(code): name for name, code in resident_code.items()}
            )
            self.ledger = load(ROOT / "config/bytecode-abi-ledger.json")
            self.compiler_symbol = self.heap.intern("%c2-compile-form")
            require(self.compiler_symbol in self.directory,
                    "candidate carrier lacks %c2-compile-form")

    return CandidateCarrier


def run_with_carrier(
    manifest_path: Path, defstruct_manifest: Path, lane: str,
) -> dict[str, Any]:
    original = PHASE_A.HistoricalCarrier
    PHASE_A.HistoricalCarrier = carrier_class(manifest_path)
    try:
        return V110.candidate_sequence(defstruct_manifest, lane)
    finally:
        PHASE_A.HistoricalCarrier = original


def code_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "expansion_sha256": value["expansion"]["expanded_source_sha256"],
        "forms": [
            {
                "source_sha256": row["source_sha256"],
                "kind": row["kind"],
                "entry": row.get("entry"),
                "nargs": int(row["code"]["nargs"]),
                "nlocals": int(row["code"]["nlocals"]),
                "flags": int(row["code"]["flags"]),
                "literals": row["code"]["literals"],
                "payload_hex": row["code"]["payload_hex"],
                "encoded_bytes": int(row["code"]["encoded_bytes"]),
                "result": row.get("result"),
            }
            for row in value["forms"]
        ],
        "constructor": value["constructor"]["result"],
        "behavior": V110.behavioral_projection(value),
    }


def graph_info(manifest: dict[str, Any]) -> dict[str, int]:
    refs = manifest["directory_only"]["entry_refs"]
    return {
        "entry_refs": len(refs),
        "entry_ref_nodes": int(manifest["directory_only"]["entry_ref_nodes"]),
        "unique_edges": len({(row["caller"], row["target"]) for row in refs}),
        "targets": len({row["target"] for row in refs}),
    }


def freight(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        "objects": len(manifest["entries"]),
        "code_bytes": int(manifest["code_bytes"]),
        "directory_bytes": int(manifest["directory_bytes"]),
        "external_image_bytes": int(manifest["external_image"]["bytes"]),
    }


def core_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    audit_contract(contract)
    v110 = load(ROOT / contract["baseline"]["v110_receipt"])
    V110.audit_result(v110)
    built_defstruct = V110.build_candidate(V110.load(V110.CONTRACT))
    built_carrier = build_carrier(contract)
    baseline_manifest_path = ROOT / contract["baseline"]["carrier_manifest"]
    baseline_manifest = load(baseline_manifest_path)
    candidate_manifest = built_carrier["manifest"]

    baseline = V110.candidate_sequence(built_defstruct["manifest_path"], "windowed")
    candidate = run_with_carrier(
        built_carrier["manifest_path"], built_defstruct["manifest_path"], "windowed"
    )
    direct = run_with_carrier(
        built_carrier["manifest_path"], built_defstruct["manifest_path"], "direct"
    )
    baseline_projection = code_projection(baseline)
    candidate_projection = code_projection(candidate)
    require(candidate_projection == baseline_projection,
            "candidate changed generated CodeObjects or persistent semantics")
    require(V110.behavioral_projection(candidate)
            == V110.behavioral_projection(direct),
            "candidate windowed/direct semantics differ")

    require_counts = deepcopy(v110["workload"]["one_time_require"])
    baseline_counts = V110.count_sequence(baseline)
    candidate_counts = V110.count_sequence(candidate)
    require(baseline_counts == v110["workload"]["full_sequence"]["candidate"],
            "1.10 exact workload was not reproduced")
    baseline_post = {
        name: int(baseline_counts[name]) - int(require_counts[name])
        for name in ("initial_windows", "refills", "window_events", "vm_instructions")
    }
    candidate_post = {
        name: int(candidate_counts[name]) - int(require_counts[name])
        for name in ("initial_windows", "refills", "window_events", "vm_instructions")
    }
    baseline_post["persistent_appends"] = 9
    candidate_post["persistent_appends"] = 9
    require(baseline_post == v110["workload"]["post_require_definition"]["candidate"],
            "1.10 post-require split was not reproduced")

    constants = V110.load(V110.CONTRACT)["price"]
    prices = {
        "full_sequence": {
            "baseline": V110.price_lane(baseline_counts, constants),
            "candidate": V110.price_lane(candidate_counts, constants),
        },
        "post_require_definition": {
            "baseline": V110.price_lane(baseline_post, constants),
            "candidate": V110.price_lane(candidate_post, constants),
        },
    }
    headline = int(contract["target"]["post_require_operational_floor_seconds_lt"])
    require(prices["full_sequence"]["candidate"]["operational_floor_seconds"] == 677
            and prices["post_require_definition"]["candidate"]
            ["operational_floor_seconds"] == 179
            and prices["post_require_definition"]["candidate"]
            ["operational_floor_seconds"] < headline,
            "priced locality target drift")

    comfort_graph, comfort_info = COMFORT.shelf_graph(
        COMFORT.load(ROOT / contract["graph"]["comfort_contract"])
    )
    base_graph = graph_info(baseline_manifest)
    cand_graph = graph_info(candidate_manifest)
    require(comfort_info["unique_edges"] == 109 and len(comfort_graph) == 50,
            "comfort who-calls instrument drift")
    require(base_graph["unique_edges"] == 306
            and cand_graph["unique_edges"] == 270,
            "carrier call-edge closure drift")

    old_freight = freight(baseline_manifest)
    new_freight = freight(candidate_manifest)
    freight_delta = {key: new_freight[key] - old_freight[key] for key in old_freight}
    budget = contract["budget"]
    budget_authority = load(ROOT / budget["bank2_headroom_authority"])
    headroom = int(json_pointer(
        budget_authority, budget["bank2_headroom_json_pointer"]
    ))
    remaining = headroom - freight_delta["external_image_bytes"]
    require(freight_delta == {
        "objects": -9,
        "code_bytes": 280,
        "directory_bytes": -63,
        "external_image_bytes": -336,
    } and remaining >= int(budget["minimum_preserved_headroom_bytes"]),
            "candidate carrier freight drift")

    current_frozen = bind(ROOT / contract["candidate"]["frozen_v1_source"])
    commissioned_frozen = git_bind(
        OWNER_COMMIT, contract["candidate"]["frozen_v1_source"]
    )
    require(current_frozen["sha256"] == commissioned_frozen["sha256"],
            "frozen v1 compiler source changed")
    live_profile = bind(ROOT / "lib/dialect-v2/lcc-profile.lisp")
    commissioned_profile = git_bind(
        OWNER_COMMIT, "lib/dialect-v2/lcc-profile.lisp")
    base_generator = bind(ROOT / contract["candidate"]["base_generator"])
    commissioned_generator = git_bind(
        OWNER_COMMIT, contract["candidate"]["base_generator"])
    require(live_profile["sha256"] == commissioned_profile["sha256"]
            and base_generator["sha256"] == commissioned_generator["sha256"],
            "host-only candidate changed a live product carrier input")
    closing_plan = git_bind(
        CLOSURE_COMMIT, "docs/planning/1.11-compiler-locality-work-plan.md")
    require(bind(PLAN)["sha256"] == closing_plan["sha256"],
            "1.11 closing plan changed after reviewer acceptance")

    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-CLOSED; POST-REQUIRE-HEADLINE-REACHED",
        "scope": deepcopy(contract["scope"]),
        "authorities": {
            "owner_commission": git_bind(
                OWNER_COMMIT, "docs/planning/1.11-compiler-locality-work-plan.md"
            ),
            "contract": bind(CONTRACT),
            "closing_plan": closing_plan,
            "v1.10_receipt": bind(ROOT / contract["baseline"]["v110_receipt"]),
            "baseline_carrier_manifest": bind(baseline_manifest_path),
            "candidate_generator": bind(ROOT / contract["candidate"]["generator"]),
            "base_generator": bind(ROOT / contract["candidate"]["base_generator"]),
            "base_generator_at_commission": commissioned_generator,
            "candidate_generation": bind(
                ROOT / contract["candidate"]["generation_receipt"]
            ),
            "candidate_suite": bind(built_carrier["suite_path"]),
            "candidate_manifest": bind(built_carrier["manifest_path"]),
            "profile_source": bind(ROOT / contract["candidate"]["profile_source"]),
            "live_product_profile": live_profile,
            "live_product_profile_at_commission": commissioned_profile,
            "frozen_v1_source": current_frozen,
            "frozen_v1_source_at_commission": commissioned_frozen,
            "comfort_graph_contract": bind(
                ROOT / contract["graph"]["comfort_contract"]
            ),
            "driver": bind(DRIVER),
            "gate_wiring": gate_wiring_projection(),
        },
        "host_execution": {
            "carrier_suite_cases": int(built_carrier["checked"]["cases"]),
            "carrier_suite_steps": int(built_carrier["checked"]["steps"]),
            "carrier_private_inline_functions": list(TIER.PRIVATE_INLINE),
            "carrier_private_inline_expansions": 73,
            "candidate_overlay_isolated_from_product_sources": True,
            "windowed_direct_behavior_byteidentical": True,
            "generated_CodeObjects_normalized_semantics_byteidentical_to_v110": True,
            "raw_host_object_sha_claimed": False,
            "generated_projection_sha256": sha(canonical(candidate_projection)),
            "behavior_projection": V110.behavioral_projection(candidate),
            "segments": V110.segments(candidate),
        },
        "call_graph": {
            "authority": "directory_only.entry_refs",
            "comfort_instrument": {
                "exact_edges": comfort_info["unique_edges"],
                "targets": comfort_info["targets"],
            },
            "baseline_carrier": base_graph,
            "candidate_carrier": cand_graph,
            "edge_delta": cand_graph["unique_edges"] - base_graph["unique_edges"],
            "claim": (
                "The comfort track's exact-edge machinery is reused as the graph "
                "instrument; the carrier graph is separately derived from its own "
                "directory-only references."
            ),
        },
        "freight": {
            "resident_delta_bytes": 0,
            "baseline": old_freight,
            "candidate": new_freight,
            "delta": freight_delta,
            "bank2_headroom_before_bytes": headroom,
            "bank2_headroom_after_delta_bytes": remaining,
            "minimum_preserved_headroom_bytes": int(
                budget["minimum_preserved_headroom_bytes"]
            ),
        },
        "workload": {
            "one_time_require": require_counts,
            "full_sequence": {
                "baseline": baseline_counts,
                "candidate": candidate_counts,
                "window_event_delta": V110.delta(
                    baseline_counts["window_events"], candidate_counts["window_events"]
                ),
                "VM_instruction_delta": V110.delta(
                    baseline_counts["vm_instructions"], candidate_counts["vm_instructions"]
                ),
            },
            "post_require_definition": {
                "baseline": baseline_post,
                "candidate": candidate_post,
                "window_event_delta": V110.delta(
                    baseline_post["window_events"], candidate_post["window_events"]
                ),
                "VM_instruction_delta": V110.delta(
                    baseline_post["vm_instructions"], candidate_post["vm_instructions"]
                ),
            },
            "generated_definition_bytes": 182,
        },
        "pricing": {
            **prices,
            "full_sequence_floor_delta_seconds": (
                prices["full_sequence"]["candidate"]["operational_floor_seconds"]
                - prices["full_sequence"]["baseline"]["operational_floor_seconds"]
            ),
            "post_require_floor_delta_seconds": (
                prices["post_require_definition"]["candidate"]
                ["operational_floor_seconds"]
                - prices["post_require_definition"]["baseline"]
                ["operational_floor_seconds"]
            ),
            "headline_seconds": headline,
            "headline_reached": True,
            "claim": (
                "Conservative structural price from the unchanged 1.10 ruler; "
                "not target wall time and not a completion upper bound."
            ),
        },
        "lever_disposition": {
            "emission_locality": {
                "status": "implemented",
                "mechanism": (
                    "four hot emission seams use one raw-equivalent carrier-local "
                    "constructor and ten proven private helpers are inlined; the "
                    "hot macro/generic-call tests lead the tail dispatcher"
                ),
                "emitted_CodeObjects_changed": False,
            },
            "definition_freight_shape": {
                "status": "rejected",
                "priced_post_require_floor_seconds": 259,
                "reason": "forcing a locality wrapper added calls and window traffic",
            },
            "pure_object_reordering": {
                "status": "rejected-structurally-zero",
                "reason": (
                    "VM_CODEBUF=56 is object-owned; adjacent packed objects cannot "
                    "share a live code window across a call"
                ),
            },
            "larger_window": {
                "status": "rejected",
                "reason": "resident growth is forbidden by the block wall",
            },
            "larger_helper_inlining": {
                "status": "rejected",
                "reason": (
                    "candidate objects exceeded the 8-bit branch or 255-byte "
                    "CodeObject contracts"
                ),
            },
        },
        "decision": {
            "headline_under_180_seconds_achieved": True,
            "post_require_operational_floor_seconds": 179,
            "candidate_retained_for_next_release_block": True,
            "release_recommendation": (
                "carry the compiler-locality carrier beside the 1.10 defstruct and "
                "comfort freight plus the editor known-issue correction into the "
                "next ordinary release block; obtain normal product/link/device "
                "acceptance there"
            ),
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "device_contacts": 0,
        },
        "claim_limit": (
        "Host execution proves normalized CodeObject semantic equivalence and "
        "prices structural "
            "carrier work. It does not claim target duration, delivery, packaging, "
            "a release, public surface, product bytes, a link, or hardware acceptance."
        ),
    }
    return value


def recompute_price(value: dict[str, Any], lane: str, side: str) -> dict[str, Any]:
    constants = V110.load(V110.CONTRACT)["price"]
    return V110.price_lane(value["workload"][lane][side], constants)


def audit_result(value: dict[str, Any]) -> None:
    contract = load(CONTRACT)
    audit_contract(contract)
    require(value.get("format") == FORMAT
            and value.get("status") ==
            "HOST-CLOSED; POST-REQUIRE-HEADLINE-REACHED",
            "1.11 result identity drift")
    require(value.get("scope") == contract["scope"], "1.11 scope drift")
    require(value.get("accounting") == {
        "product_bytes_changed": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "device_contacts": 0,
    }, "host-only accounting drift")
    host = value["host_execution"]
    require(host["carrier_suite_cases"] == 6
            and host["generated_CodeObjects_normalized_semantics_byteidentical_to_v110"]
            and host["raw_host_object_sha_claimed"] is False
            and host["windowed_direct_behavior_byteidentical"]
            and host["carrier_private_inline_functions"] == list(TIER.PRIVATE_INLINE)
            and host["carrier_private_inline_expansions"] == 73
            and host["candidate_overlay_isolated_from_product_sources"] is True
            and host["behavior_projection"]["C2J"] == "CLEAR",
            "semantic/private-inline closure drift")
    expected_counts = {
        "full_sequence": {
            "baseline": {"initial_windows": 11441, "refills": 12209,
                         "window_events": 23650, "vm_instructions": 187092,
                         "persistent_appends": 9},
            "candidate": {"initial_windows": 10671, "refills": 11624,
                          "window_events": 22295, "vm_instructions": 185100,
                          "persistent_appends": 9},
        },
        "post_require_definition": {
            "baseline": {"initial_windows": 3686, "refills": 2911,
                         "window_events": 6597, "vm_instructions": 34401,
                         "persistent_appends": 9},
            "candidate": {"initial_windows": 2916, "refills": 2326,
                          "window_events": 5242, "vm_instructions": 32409,
                          "persistent_appends": 9},
        },
    }
    for lane, expected in expected_counts.items():
        row = value["workload"][lane]
        require(row["baseline"] == expected["baseline"]
                and row["candidate"] == expected["candidate"],
                f"{lane} exact workload drift")
        require(row["window_event_delta"] == V110.delta(
            expected["baseline"]["window_events"],
            expected["candidate"]["window_events"]),
            f"{lane} window delta drift")
        require(row["VM_instruction_delta"] == V110.delta(
            expected["baseline"]["vm_instructions"],
            expected["candidate"]["vm_instructions"]),
            f"{lane} VM delta drift")
        for side in ("baseline", "candidate"):
            require(value["pricing"][lane][side]
                    == recompute_price(value, lane, side),
                    f"{lane} price drift")
    require(value["workload"]["generated_definition_bytes"] == 182,
            "definition freight changed")
    require(value["pricing"]["full_sequence"]["baseline"]
            ["operational_floor_seconds"] == 716
            and value["pricing"]["full_sequence"]["candidate"]
            ["operational_floor_seconds"] == 677
            and value["pricing"]["post_require_definition"]["baseline"]
            ["operational_floor_seconds"] == 218
            and value["pricing"]["post_require_definition"]["candidate"]
            ["operational_floor_seconds"] == 179
            and value["pricing"]["headline_reached"] is True,
            "headline pricing drift")
    require(value["call_graph"]["comfort_instrument"] == {
        "exact_edges": 109, "targets": 50,
    } and value["call_graph"]["baseline_carrier"]["unique_edges"] == 306
      and value["call_graph"]["candidate_carrier"]["unique_edges"] == 270,
      "call graph closure drift")
    freight_row = value["freight"]
    require(freight_row["resident_delta_bytes"] == 0
            and freight_row["delta"] == {
                "objects": -9, "code_bytes": 280,
                "directory_bytes": -63, "external_image_bytes": -336,
            }
            and freight_row["bank2_headroom_after_delta_bytes"]
            == freight_row["bank2_headroom_before_bytes"] + 336
            and freight_row["bank2_headroom_after_delta_bytes"]
            >= freight_row["minimum_preserved_headroom_bytes"],
            "Bank-2 freight closure drift")
    require(value["lever_disposition"]["emission_locality"] == {
        "status": "implemented",
        "mechanism": (
            "four hot emission seams use one raw-equivalent carrier-local "
            "constructor and ten proven private helpers are inlined; the "
            "hot macro/generic-call tests lead the tail dispatcher"
        ),
        "emitted_CodeObjects_changed": False,
    } and value["lever_disposition"]["definition_freight_shape"]["status"]
      == "rejected"
      and value["lever_disposition"]["pure_object_reordering"]["status"]
      == "rejected-structurally-zero"
      and value["lever_disposition"]["larger_window"]["status"] == "rejected"
      and value["lever_disposition"]["larger_helper_inlining"]["status"]
      == "rejected", "lever disposition drift")
    require(value["decision"]["headline_under_180_seconds_achieved"] is True
            and value["decision"]["post_require_operational_floor_seconds"] == 179
            and value["decision"]["candidate_retained_for_next_release_block"]
            is True, "closing decision drift")


def rejected(
    label: str, value: dict[str, Any], mutate: Callable[[dict[str, Any]], None],
    result: dict[str, str],
) -> None:
    candidate = deepcopy(value)
    mutate(candidate)
    try:
        audit_result(candidate)
    except (LocalityError, V110.PerformanceError) as error:
        result[label] = str(error)
    else:
        raise LocalityError(f"1.11 mutation survived: {label}")


def mutation_proof(value: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    tests: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("format", lambda x: x.__setitem__("format", "wrong")),
        ("resident-byte", lambda x: x["freight"].__setitem__(
            "resident_delta_bytes", 1)),
        ("device-contact", lambda x: x["accounting"].__setitem__(
            "device_contacts", 1)),
        ("product-link", lambda x: x["accounting"].__setitem__(
            "product_links", 1)),
        ("release-claim", lambda x: x["scope"].__setitem__(
            "release_claim", True)),
        ("surface-claim", lambda x: x["scope"].__setitem__(
            "public_surface_claim", True)),
        ("journal", lambda x: x["host_execution"]["behavior_projection"]
         .__setitem__("C2J", "ACTIVE")),
        ("codeobject-equivalence", lambda x: x["host_execution"].__setitem__(
            "generated_CodeObjects_normalized_semantics_byteidentical_to_v110",
            False)),
        ("direct-equivalence", lambda x: x["host_execution"].__setitem__(
            "windowed_direct_behavior_byteidentical", False)),
        ("inline-set", lambda x: x["host_execution"]
         ["carrier_private_inline_functions"].pop()),
        ("inline-expansions", lambda x: x["host_execution"].__setitem__(
            "carrier_private_inline_expansions", 72)),
        ("carrier-equivalence-case", lambda x: x["host_execution"].__setitem__(
            "carrier_suite_cases", 5)),
        ("live-product-source-intrusion", lambda x: x["host_execution"].__setitem__(
            "candidate_overlay_isolated_from_product_sources", False)),
        ("append-count", lambda x: x["workload"]["full_sequence"]
         ["candidate"].__setitem__("persistent_appends", 8)),
        ("window-count", lambda x: x["workload"]["full_sequence"]
         ["candidate"].__setitem__("window_events", 1)),
        ("VM-count", lambda x: x["workload"]["post_require_definition"]
         ["candidate"].__setitem__("vm_instructions", 1)),
        ("definition-bytes", lambda x: x["workload"].__setitem__(
            "generated_definition_bytes", 181)),
        ("price", lambda x: x["pricing"]["post_require_definition"]
         ["candidate"].__setitem__("operational_floor_seconds", 1)),
        ("headline", lambda x: x["pricing"].__setitem__(
            "headline_reached", False)),
        ("comfort-edge", lambda x: x["call_graph"]["comfort_instrument"]
         .__setitem__("exact_edges", 108)),
        ("carrier-edge", lambda x: x["call_graph"]["candidate_carrier"]
         .__setitem__("unique_edges", 269)),
        ("carrier-code-freight", lambda x: x["freight"]["delta"]
         .__setitem__("code_bytes", 0)),
        ("carrier-external-freight", lambda x: x["freight"]["delta"]
         .__setitem__("external_image_bytes", 0)),
        ("bank2-headroom", lambda x: x["freight"].__setitem__(
            "bank2_headroom_after_delta_bytes", 1)),
        ("emission-locality", lambda x: x["lever_disposition"]
         ["emission_locality"].__setitem__("status", "rejected")),
        ("definition-freight-overclaim", lambda x: x["lever_disposition"]
         ["definition_freight_shape"].__setitem__("status", "implemented")),
        ("object-reorder-overclaim", lambda x: x["lever_disposition"]
         ["pure_object_reordering"].__setitem__("status", "implemented")),
        ("resident-window-growth", lambda x: x["lever_disposition"]
         ["larger_window"].__setitem__("status", "implemented")),
        ("decision", lambda x: x["decision"].__setitem__(
            "headline_under_180_seconds_achieved", False)),
    ]
    for label, mutate in tests:
        rejected(label, value, mutate, result)
    require(len(result) == 29, "mutation execution count drift")
    return result


def derive() -> dict[str, Any]:
    value = core_receipt()
    audit_result(value)
    value["mutations_rejected"] = mutation_proof(value)
    return value


def audit(value: dict[str, Any]) -> None:
    audit_result(value)
    require(len(value.get("mutations_rejected", {})) == 29,
            "mutation closure drift")
    require(value == derive(),
            "1.11 locality receipt differs from current host execution")
    require(load(REBIND) == derive_rebind(value),
            "1.11 release-promotion rebind drift")


def derive_rebind(value: dict[str, Any]) -> dict[str, Any]:
    audit_result(value)
    historical = git_bind(
        HISTORICAL_RECEIPT_COMMIT,
        RECEIPT.relative_to(ROOT).as_posix(),
    )
    return {
        "format": "lisp65-c2.3-v1.11-release-promotion-rebind-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-loud-dated-release-promotion-rebind",
        "reason": (
            "The reviewer appended the accepted closing disposition and the "
            "v1.4 release block added unrelated gate rows. Replace mutable whole-"
            "file bindings with the accepted-plan commit and an exact semantic "
            "wiring projection; do not rewrite any 1.11 workload or claim."
        ),
        "historical_receipt": historical,
        "accepted_closing_plan": value["authorities"]["closing_plan"],
        "current_driver": value["authorities"]["driver"],
        "gate_wiring_projection": value["authorities"]["gate_wiring"],
        "semantic_invariants": {
            "full_sequence_seconds": 677,
            "post_require_seconds": 179,
            "window_events": 5242,
            "vm_instructions": 32409,
            "external_image_delta_bytes": -336,
            "resident_delta_bytes": 0,
            "mutations": 29,
        },
        "historical_payload_rewritten_silently": False,
        "claim_limit": (
            "Authority-binding repair only. No compiler, freight, product, device, "
            "link, surface, timing-upper-bound or release claim is added."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "rebind", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            audit_contract(load(CONTRACT))
            value = load(RECEIPT)
            audit_result(value)
            require(len(mutation_proof(value)) == 29,
                    "selftest mutation count drift")
            print("c2-v111-compiler-locality: SELFTEST PASS mutations=29")
            return 0
        if args.action == "run":
            value = derive()
            write_json(RECEIPT, value)
        elif args.action == "rebind":
            value = load(RECEIPT)
            audit_result(value)
            write_json(REBIND, derive_rebind(value))
        else:
            value = load(RECEIPT)
            audit(value)
        full = value["pricing"]["full_sequence"]
        post = value["pricing"]["post_require_definition"]
        freight_delta = value["freight"]["delta"]
        print(
            "c2-v111-compiler-locality: PASS "
            f"full={full['baseline']['operational_floor_seconds']}->"
            f"{full['candidate']['operational_floor_seconds']}s "
            f"post-require={post['baseline']['operational_floor_seconds']}->"
            f"{post['candidate']['operational_floor_seconds']}s "
            f"carrier-external={freight_delta['external_image_bytes']:+d} "
            "resident=0 device=0 release=deferred"
        )
        return 0
    except (
        LocalityError, V110.PerformanceError, PHASE_A.PhaseAError,
        B.VMError, KeyError, TypeError, ValueError, OSError,
    ) as error:
        print(f"c2-v111-compiler-locality: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
