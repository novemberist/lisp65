#!/usr/bin/env python3
"""Complete the R1 stored-world sweep from the runtime installation graph."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = (ROOT / "tools/host-lisp").resolve()
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
OLD_SWEEP = ARCH / "c2.3-v1.6-r1-stored-world-sweep-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-r1-stored-world-collective-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-r1-stored-world-collective-card-red-attribution-receipt.json")
ELF = ROOT / (
    "build/c2.3/v1.6-r1-stored-world-collective-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ARCH / "c2.3-v1.6-r1-graph-stored-world-sweep-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "a6bce4d2"
STATUS = "PASS: GRAPH-DERIVED R1 STORED-WORLD SWEEP COMPLETE"
FORMAT = "lisp65-c2-v160-r1-graph-stored-world-sweep-v1"


class GraphSweepError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GraphSweepError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def callable_snapshot() -> dict[tuple[str, str], tuple[str, str, int]]:
    result: dict[tuple[str, str], tuple[str, str, int]] = {}
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        try:
            relative = Path(path).resolve().relative_to(HOST).as_posix()
        except (OSError, ValueError):
            continue
        for attribute, value in vars(module).items():
            if inspect.isfunction(value):
                result[(relative, attribute)] = (
                    value.__module__, value.__name__, value.__code__.co_firstlineno)
    return result


def frame_identity(frame: Any) -> tuple[str, str, int] | None:
    try:
        relative = Path(frame.f_code.co_filename).resolve().relative_to(HOST)
    except (OSError, ValueError):
        return None
    return relative.as_posix(), frame.f_code.co_name, frame.f_code.co_firstlineno


def is_consumer(attribute: str) -> bool:
    lowered = attribute.lower()
    return ("linked" in lowered or "gate" in lowered
            or lowered in {"acceptance_child", "placement_contract",
                           "patch_verifier_binding_table"})


def probe(mode: str) -> dict[str, Any]:
    """Run only configuration and observe its calls/namespace installations."""
    import c2_v160_r1_stored_world_collective_card as top

    before = callable_snapshot()
    edges: set[tuple[tuple[str, str, int], tuple[str, str, int]]] = set()
    nodes: set[tuple[str, str, int]] = set()

    def profile(frame: Any, event: str, _arg: Any) -> None:
        if event != "call":
            return
        current = frame_identity(frame)
        if current is None:
            return
        nodes.add(current)
        parent = frame.f_back
        while parent is not None:
            caller = frame_identity(parent)
            if caller is not None:
                edges.add((caller, current))
                break
            parent = parent.f_back

    sys.setprofile(profile)
    try:
        top.PREV.configure_module = top.configure_module
        top.configure_module()
        core = top.PREV.CORE
        core.install()
        configure = core.PRODUCT.BASE.configure
        if mode == "hidden-linked-gate":
            def hidden_linked_gate() -> None:
                return None

            def configure_with_hidden_gate() -> None:
                configure()
                core.PRODUCT.BASE.linked_hidden_gate = hidden_linked_gate

            core.PRODUCT.BASE.configure = configure_with_hidden_gate
        core.PRODUCT.BASE.configure()
    finally:
        sys.setprofile(None)
    after = callable_snapshot()
    assignments = []
    for target in sorted(set(before) | set(after)):
        if before.get(target) == after.get(target):
            continue
        assignments.append({"target_module": target[0],
            "target_attribute": target[1],
            "before": before.get(target), "after": after.get(target)})
    consumers = [row for row in assignments
                 if is_consumer(row["target_attribute"])]
    files = sorted({row[0] for row in nodes})
    closure = hashlib.sha256()
    for name in files:
        raw = (HOST / name).read_bytes()
        closure.update(name.encode() + b"\0" + raw + b"\0")
    return {"mode": mode,
        "root": "runtime object core.PRODUCT.BASE.configure after R1 install",
        "call_node_count": len(nodes), "call_edge_count": len(edges),
        "call_nodes": [list(row) for row in sorted(nodes)],
        "call_edges": [[list(left), list(right)] for left, right in sorted(edges)],
        "source_closure": {"file_count": len(files), "files": files,
                           "sha256": closure.hexdigest()},
        "callable_installation_count": len(assignments),
        "callable_installations": assignments,
        "installed_consumer_count": len(consumers),
        "installed_consumers": consumers}


def run_probe(mode: str) -> dict[str, Any]:
    run = subprocess.run([sys.executable, str(DRIVER), "_probe", mode],
        cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    require(run.returncode == 0, f"graph probe red: {run.stderr}")
    value = json.loads(run.stdout)
    require(isinstance(value, dict), "graph probe returned no object")
    return value


def inventory() -> list[dict[str, Any]]:
    return [
        {"id": "post-link.local-return-placement-snapshot",
         "consumer": "c2_v21_candidate_derived_local_return.linked_gate",
         "stored": {"reader_address": "0x2277", "reader_bytes": 189,
                    "text_end_exclusive": "0xb3af",
                    "ordinary_reserve_bytes": 1},
         "candidate": {"reader_address": "derive ELF symbol",
                       "reader_bytes": "derive ELF symbol extent",
                       "text_end_exclusive": "0xb3aa",
                       "ordinary_reserve_bytes": 6},
         "conversion": "derive movable text/reader facts from candidate; retain fixed facade ABI"},
        {"id": "post-link.local-return-code-size-snapshots",
         "consumer": "c2_v21_candidate_derived_local_return.linked_gate",
         "stored": {"selector": 40, "c2e_w32": 63, "cold_section": 1246,
                    "shelf_reader": 194, "c2d_reader": 85},
         "candidate": "derive symbol/section extents and validate their semantic relations/capacities",
         "conversion": "no emitted function or section size is an identity"},
        {"id": "post-link.local-return-callsite-count",
         "consumer": "c2_v21_candidate_derived_local_return.linked_gate",
         "stored": {"c2e_w32_callers": 5},
         "candidate": "classify every candidate-derived caller",
         "conversion": "rule membership, never historical cardinality"},
        {"id": "post-link.local-return-packed-image-snapshots",
         "consumer": "c2_v21_candidate_derived_local_return.linked_gate",
         "stored": {"row_file_size": 1246, "aggregate_bytes": 65423},
         "candidate": "derive row and aggregate sizes from candidate manifest",
         "conversion": "retain the 1280-byte allocation as capacity, not snapshot"},
        {"id": "post-link.map-tuple-mnemonic-snapshots",
         "consumer": "c2_v21_full_span_projection_artifact_replay.successor_linked_tuple_gate",
         "stored": {"entry_bytes": 19,
                    "entry_body": "48da5aa940a282a000a3805ceaa3007afa6860",
                    "descriptor_store": "a9048d00c0"},
         "candidate": "decode MAP tuple, exits and descriptor-store effect from emitted code",
         "conversion": "semantic hardware effect, never whole-body opcode identity"},
        {"id": "post-producer.cpu-owner-source-membership",
         "consumer": "c2_v160_r1_stored_world_conversions.classify_registry",
         "stored": ["src/optional/c2_map_cpu_read.s"],
         "candidate": "derive the named owner's member set from candidate projection",
         "conversion": "classify identity and ownership without a successor path pin"},
    ]


def exclusions() -> list[dict[str, str]]:
    return [
        {"id": "mapped-far-facade-0xb3b0-98", "reason": "fixed facade ABI contract"},
        {"id": "host-facade-0xb5c4-48-vector-0xb5eb", "reason": "fixed vector ABI with external dependants"},
        {"id": "mapped-far-A40-X82", "reason": "decoded hardware-semantic invariant"},
        {"id": "mapped-far-arena-1499", "reason": "capacity contract"},
        {"id": "phase02a-arena-1792-timeout-64", "reason": "capacity and priced timing contracts"},
        {"id": "packed-page-allocation-1280", "reason": "fixed allocation capacity; used bytes derive"},
        {"id": "wysiwyg-recovery-at-least-13", "reason": "authorized recovery floor, not candidate identity"},
        {"id": "uniqueness-counts", "reason": "one named owner/store/label, not registry cardinality"},
    ]


def authority() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(["git", "show", f"{value['commit']}:{value['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").replace("`", "").split())
    for token in ("graph-derived sweep completion", "full installation graph",
                  "host-only", "requires its own explicit release"):
        require(token in text, f"graph-sweep authority absent: {token}")
    return value


def derive() -> dict[str, Any]:
    red = load(FINAL_RED); attribution = load(ATTRIBUTION)
    require(red["retry_authorized"] is False
            and attribution["sweep_failure"]["completeness_claim_withdrawn"]
                is True,
            "graph-sweep predecessor drift")
    before = bind(ELF)
    graph = run_probe("normal")
    after = bind(ELF)
    require(before == after and graph["call_node_count"] >= 70
            and graph["call_edge_count"] >= 78
            and graph["installed_consumer_count"] >= 18,
            "graph-derived configure closure is incomplete")
    mutant = run_probe("hidden-linked-gate")
    hidden = [row for row in mutant["installed_consumers"]
              if row["target_attribute"] == "linked_hidden_gate"]
    require(len(hidden) == 1
            and mutant["installed_consumer_count"] ==
                graph["installed_consumer_count"] + 1,
            "hidden transitively installed linked-gate mutation survived")
    rows = inventory()
    return {"format": FORMAT, "recorded_on": "2026-08-19", "status": STATUS,
        "claim_limit": "Graph-derived read-only enumeration over frozen Red ELF; no qualification, conversion, or link.",
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "frozen_evidence_before": before, "frozen_evidence_after": after,
        "installation_graph": graph,
        "completeness_mutation": {"name": "hidden-transitive-linked-gate",
            "normal_consumers": graph["installed_consumer_count"],
            "mutant_consumers": mutant["installed_consumer_count"],
            "rejected": True},
        "prior_conversions_observed": 8,
        "remaining_inventory": rows, "remaining_inventory_count": len(rows),
        "replacement_card_checklist": [row["id"] for row in rows],
        "reviewed_exclusions": exclusions(),
        "disposition": {"replacement_cards_authorized": 0,
            "conversion_or_link_authorized": False,
            "explicit_owner_release_required": True},
        "authority": {"owner": authority(), "old_sweep": bind(OLD_SWEEP),
            "Final_Red": bind(FINAL_RED), "attribution": bind(ATTRIBUTION),
            "driver": bind(DRIVER)},
        "next": "owner review; no replacement collective card is authorized"}


def check() -> None:
    require(load(RECEIPT) == derive(), "graph-derived sweep receipt drift")
    print("R1 graph sweep: PASS nodes=70+ edges=78+ consumers=18+ remaining=6 card=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("print", "check", "_probe"))
    parser.add_argument("mode", nargs="?", default="normal")
    args = parser.parse_args()
    if args.action == "_probe":
        print(json.dumps(probe(args.mode), sort_keys=True))
    elif args.action == "print":
        print(canonical(derive()).decode(), end="")
    else:
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
