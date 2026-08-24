#!/usr/bin/env python3
"""Graph-derived output-owner rebind for the v1.6 fidelity successor."""

from __future__ import annotations

import ast
from pathlib import Path
import types
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = (ROOT / "tools/host-lisp").resolve()


class OwnerRebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise OwnerRebindError(message)


def module_graph(roots: list[types.ModuleType]) -> dict[str, Any]:
    """Traverse module-valued ownership edges; no entry-point hand list."""
    pending = list(roots)
    seen: dict[str, types.ModuleType] = {}
    edges: set[tuple[str, str, str]] = set()
    while pending:
        module = pending.pop()
        if not isinstance(module, types.ModuleType):
            continue
        path = getattr(module, "__file__", None)
        try:
            relative = Path(path).resolve().relative_to(HOST)
        except (TypeError, OSError, ValueError):
            continue
        if module.__name__ in seen:
            continue
        seen[module.__name__] = module
        for attribute, value in vars(module).items():
            if not isinstance(value, types.ModuleType):
                continue
            child_path = getattr(value, "__file__", None)
            try:
                Path(child_path).resolve().relative_to(HOST)
            except (TypeError, OSError, ValueError):
                continue
            edges.add((module.__name__, attribute, value.__name__))
            pending.append(value)
    return {"modules": seen, "edges": sorted(edges),
            "root_modules": sorted(module.__name__ for module in roots)}


def _owns_exclusive_build(module: types.ModuleType) -> bool:
    path = Path(module.__file__).resolve()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    producers = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == "produce_child"]
    if len(producers) != 1:
        return False
    return any(isinstance(node, ast.Call)
               and ((isinstance(node.func, ast.Name)
                     and node.func.id == "producer_build_owner_gate")
                    or (isinstance(node.func, ast.Attribute)
                        and node.func.attr == "producer_build_owner_gate"))
               for node in ast.walk(producers[0]))


def owners(roots: list[types.ModuleType]) -> tuple[dict[str, Any],
                                                   list[types.ModuleType]]:
    graph = module_graph(roots)
    selected = sorted((module for module in graph["modules"].values()
                       if _owns_exclusive_build(module)),
                      key=lambda module: module.__name__)
    require(selected, "ownership graph contains no exclusive build owner")
    return graph, selected


def _bind(module: types.ModuleType, build: Path, preflight: Path,
          driver: Path, link: int) -> None:
    values = {
        "BUILD": build, "PREFLIGHT": preflight,
        "PREFLIGHT_RECEIPT": preflight / "preflight.json",
        "INVOCATION": preflight / "card-invocation.json",
        "PRODUCER_RESULT": build / "producer-result.json",
        "SCOPE_RESULT": build / "owner-scope-result.json",
        "ACCEPTANCE_RESULT": build / "artifact-acceptance.json",
        "RECEIPT": build / f"unused-{module.__name__}-receipt.json",
        "FINAL_RED": build / f"unused-{module.__name__}-final-red.json",
        "DRIVER": driver, "LINK": link,
    }
    for name, value in values.items():
        if hasattr(module, name):
            setattr(module, name, value)


def validate(selected: list[types.ModuleType], build: Path) -> None:
    stale = {module.__name__: str(module.BUILD.relative_to(ROOT))
             for module in selected if Path(module.BUILD) != build}
    require(not stale, f"transitive output owner retained stale path: {stale}")


def rebind(roots: list[types.ModuleType], build: Path, preflight: Path,
           driver: Path, link: int) -> dict[str, Any]:
    graph, selected = owners(roots)
    before = {module.__name__: str(Path(module.BUILD).relative_to(ROOT))
              for module in selected}
    for module in selected:
        _bind(module, build, preflight, driver, link)
    validate(selected, build)
    after = {module.__name__: str(Path(module.BUILD).relative_to(ROOT))
             for module in selected}

    mutant = selected[-1]
    saved = mutant.BUILD
    mutant.BUILD = ROOT / "build/c2.3/stale-transitive-owner-mutation"
    rejected = False
    try:
        validate(selected, build)
    except OwnerRebindError:
        rejected = True
    finally:
        mutant.BUILD = saved
    validate(selected, build)
    require(rejected, "stale transitive output-owner mutation survived")
    return {"status": "PASS: TRANSITIVE OUTPUT OWNERS REBOUND",
        "derivation": "module-valued ownership graph from configured roots",
        "root_modules": graph["root_modules"],
        "graph_module_count": len(graph["modules"]),
        "graph_edge_count": len(graph["edges"]),
        "exclusive_owner_count": len(selected),
        "exclusive_owners": [module.__name__ for module in selected],
        "paths_before": before, "paths_after": after,
        "replacement_build": str(build.relative_to(ROOT)),
        "stale_transitive_owner_mutation_rejected": True}
