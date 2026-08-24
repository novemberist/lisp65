#!/usr/bin/env python3
"""Run the one owner-authorized graph-complete R1 collective card."""

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
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_r1_stored_world_collective_card as PREV  # noqa: E402
import c2_v160_r1_graph_conversions as CONVERT  # noqa: E402
import c2_v160_r1_graph_stored_world_sweep as SWEEP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-r1-graph-collective-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-r1-graph-collective-preflight"
RECEIPT = ARCH / "c2.3-v1.6-r1-graph-collective-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-r1-graph-collective-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-r1-stored-world-collective-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "71d5d38b"
STATUS = "PASS: V1.6 R1 GRAPH-COMPLETE COLLECTIVE CARD GREEN"
FORMAT = "lisp65-c2-v160-r1-graph-collective-card-v1"
ORIGINAL_CONFIGURE = PREV.configure_module
ORIGINAL_CORE_INSTALL = PREV.PREV.CORE.install


class GraphCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GraphCardError(message)


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


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("six classes", "installation graph", "one wplto",
                  "one product link", "exceptionless"):
        require(token in text, f"graph collective authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: R1 STORED-WORLD COLLECTIVE RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and set(value["artifacts"]) == {"ELF", "PRG"},
            "graph collective predecessor drift")
    return value


def install_after_real_configuration(build: Path = BUILD,
                                     preflight: Path = PREFLIGHT) -> None:
    """Put conversions after the transitive configure chain, not before it."""
    ORIGINAL_CORE_INSTALL(build, preflight)
    root = PREV.PREV.CORE.PRODUCT.BASE
    configure = root.configure
    if getattr(configure, "_r1_graph_collective", False):
        return

    def configured() -> Any:
        result = configure()
        CONVERT.install()
        return result

    configured._r1_graph_collective = True  # type: ignore[attr-defined]
    root.configure = configured


def configure_module() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.PREDECESSOR_RED = PREDECESSOR_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.STATUS = STATUS
    PREV.FORMAT = FORMAT
    PREV.predecessor = predecessor
    ORIGINAL_CONFIGURE()
    PREV.PREV.CORE.install = install_after_real_configuration


def _callable_snapshot() -> dict[tuple[str, str], tuple[str, str, int]]:
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


def _frame_identity(frame: Any) -> tuple[str, str, int] | None:
    try:
        relative = Path(frame.f_code.co_filename).resolve().relative_to(HOST)
    except (OSError, ValueError):
        return None
    return relative.as_posix(), frame.f_code.co_name, frame.f_code.co_firstlineno


def _is_consumer(attribute: str) -> bool:
    lowered = attribute.lower()
    return ("linked" in lowered or "gate" in lowered
            or lowered in {"acceptance_child", "placement_contract",
                           "patch_verifier_binding_table"})


def graph_probe(mode: str) -> dict[str, Any]:
    before = _callable_snapshot()
    edges: set[tuple[tuple[str, str, int], tuple[str, str, int]]] = set()
    nodes: set[tuple[str, str, int]] = set()

    def profile(frame: Any, event: str, _arg: Any) -> None:
        if event != "call":
            return
        current = _frame_identity(frame)
        if current is None:
            return
        nodes.add(current)
        parent = frame.f_back
        while parent is not None:
            caller = _frame_identity(parent)
            if caller is not None:
                edges.add((caller, current)); break
            parent = parent.f_back

    sys.setprofile(profile)
    try:
        PREV.configure_module = configure_module
        configure_module()
        core = PREV.PREV.CORE
        frozen_build = SWEEP.ELF.parent.parent
        frozen_preflight = ROOT / (
            "build/c2.3/v1.6-r1-stored-world-collective-preflight")
        core.install(frozen_build, frozen_preflight)
        root = core.PRODUCT.BASE
        root.configure()
        if mode == "hidden-linked-gate":
            def linked_hidden_gate() -> None:
                return None
            root.linked_hidden_gate = linked_hidden_gate
    finally:
        sys.setprofile(None)
    after = _callable_snapshot()
    assignments = []
    for target in sorted(set(before) | set(after)):
        if before.get(target) == after.get(target):
            continue
        assignments.append({"target_module": target[0],
            "target_attribute": target[1], "before": before.get(target),
            "after": after.get(target)})
    consumers = [row for row in assignments
                 if _is_consumer(row["target_attribute"])]
    return {"mode": mode, "call_node_count": len(nodes),
        "call_edge_count": len(edges),
        "call_nodes": [list(row) for row in sorted(nodes)],
        "call_edges": [[list(a), list(b)] for a, b in sorted(edges)],
        "callable_installation_count": len(assignments),
        "callable_installations": assignments,
        "installed_consumer_count": len(consumers),
        "installed_consumers": consumers}


def run_graph(mode: str) -> dict[str, Any]:
    run = subprocess.run([sys.executable, str(DRIVER), "_graph", mode],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(run.returncode == 0, f"graph card probe red: {run.stderr}")
    value = json.loads(run.stdout)
    require(isinstance(value, dict), "graph card probe returned no object")
    return value


def graph_completeness() -> dict[str, Any]:
    prior = load(SWEEP.RECEIPT)["installation_graph"]
    current = run_graph("normal")
    prior_targets = {(row["target_module"], row["target_attribute"])
                     for row in prior["installed_consumers"]}
    current_targets = {(row["target_module"], row["target_attribute"])
                       for row in current["installed_consumers"]}
    added_targets = current_targets - prior_targets
    require(not (prior_targets - current_targets)
            and all(row["after"] and row["after"][0] == CONVERT.__name__
                    for row in current["installed_consumers"]
                    if (row["target_module"], row["target_attribute"])
                        in added_targets)
            and current["call_node_count"] >= prior["call_node_count"]
            and current["call_edge_count"] >= prior["call_edge_count"],
            "configured installation graph lost or gained an unclassified consumer")
    changed = [row for row in current["installed_consumers"]
               if row["after"] and row["after"][0] == CONVERT.__name__]
    changed_targets = {(row["target_module"], row["target_attribute"])
                       for row in changed}
    required = {
        ("c2_v21_candidate_derived_local_return.py", "placement_contract"),
        ("c2_v21_local_return_identity_card.py", "linked_gate"),
        ("c2_v21_text_recovery_card.py", "linked_gate"),
        ("c2_v21_text_recovery_replacement_card.py", "linked_gate"),
        ("c2_v20_map_tuple_fix_card.py", "linked_tuple_gate"),
        ("c2_v21_cpu_transport_replacement_card.py",
         "dynamic_configuration_gate"),
    }
    require(required <= changed_targets,
            "one of the six graph conversions missed its real consumer")
    mutant = run_graph("hidden-linked-gate")
    hidden = [row for row in mutant["installed_consumers"]
              if row["target_attribute"] == "linked_hidden_gate"]
    require(len(hidden) == 1
            and mutant["installed_consumer_count"] ==
                current["installed_consumer_count"] + 1,
            "hidden graph consumer mutation survived")
    return {"status": "PASS: installed graph completely classified",
        "call_nodes": current["call_node_count"],
        "call_edges": current["call_edge_count"],
        "installed_consumers": current["installed_consumer_count"],
        "classified_targets": len(current_targets),
        "new_conversion_installations": len(changed_targets),
        "hidden_consumer_mutation_rejected": True}


def conversion_evidence() -> dict[str, Any]:
    sweep = load(SWEEP.RECEIPT)
    conversion = CONVERT.preflight()
    require(sweep["replacement_card_checklist"] == conversion["inventory_ids"],
            "six-class graph checklist drift")
    elf = SWEEP.ELF
    manifest = elf.parent / "runtime-overlays-session-final.json"
    old_artifacts = CONVERT.OLD.artifact_paths
    CONVERT.OLD.artifact_paths = lambda: {"elf": elf}
    try:
        registry = CONVERT.dynamic_configuration_gate()
        linked = CONVERT.linked_gate(elf, manifest)
        tuple_value = CONVERT.linked_tuple_gate(elf)
        rejected = (CONVERT.linked_mutations(linked, elf, manifest)
            + CONVERT.tuple_mutations(elf) + CONVERT.registry_mutation())
        real_consumers = CONVERT.real_consumer_preflight(elf, manifest)
    finally:
        CONVERT.OLD.artifact_paths = old_artifacts
    require(rejected == conversion["reintroduction_mutations"],
            "six-class reintroduction mutation coverage drift")
    return {**conversion, "frozen_red_elf": bind(elf),
        "candidate_registry": registry,
        "candidate_linked_relations": linked,
        "candidate_MAP_semantics": tuple_value,
        "mutations_rejected": rejected,
        "real_consumer_preflight": real_consumers}


def arm() -> dict[str, Any]:
    return {"status": "PASS: GRAPH COLLECTIVE CARD ARMED 0/1",
        "authority": authorization(), "sweep": bind(SWEEP.RECEIPT),
        "conversions": conversion_evidence(),
        "installation_graph": graph_completeness()}


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["graph_collective_authority"] = authorization()
    value["stored_world_collective_Final_Red"] = bind(PREDECESSOR_RED)
    value["graph_collective"] = arm()
    value["next"] = ("input-fidelity reopen on derived 82-byte reserve"
                     if green else
                     "owner disposition required; no retry or downstream work")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "graph collective card is one-shot")
    armed = arm()
    PREV.configure_module = configure_module
    configure_module()
    PREV.preflight()
    value = load(PREFLIGHT / "preflight.json")
    value["graph_collective"] = armed
    value["graph_collective_authority"] = authorization()
    (PREFLIGHT / "preflight.json").write_bytes(canonical(value))
    print("v1.6 R1 graph collective: PREFLIGHT PASS card=0/1 classes=6")


def card() -> None:
    predecessor()
    PREV.configure_module = configure_module
    configure_module()
    PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 graph collective: CARD PASS card=1/1 classes=6")


def child(action: str) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: R1 GRAPH COLLECTIVE RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 R1 graph collective: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 R1 graph collective: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 graph collective: CHECK ARMED")
    else:
        print("v1.6 R1 graph collective: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_graph"))
    parser.add_argument("mode", nargs="?", default="normal")
    args = parser.parse_args()
    if args.action == "preflight": preflight()
    elif args.action == "card": card()
    elif args.action == "check": check()
    elif args.action == "_graph":
        print(json.dumps(graph_probe(args.mode), sort_keys=True))
    else: child(args.action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"graph collective receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 R1 graph collective: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
