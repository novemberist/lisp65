#!/usr/bin/env python3
"""Write a static callgraph for the IDE render bytecode path."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

import ide_bytecode_cost_report as Cost


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "build" / "bytecode" / "stdlib-p0.manifest.json"
DEFAULT_OUT = ROOT / "build" / "bytecode" / "ide-render-callgraph.txt"
DEFAULT_ROOTS = ["ide-render"]


def _edge_cost(call: dict, stats: dict[str, dict]) -> int:
    kind = call["kind"]
    if kind == "TAILCALL" and call["target"] in stats:
        return 0
    if kind in ("CALL", "TAILCALL", "CALLPRIM"):
        return 1
    return 0


def _fmt_call(call: dict) -> str:
    return "%s %s/%d @%04x" % (call["kind"], call["target"], call["argc"], call["pc"])


def _walk_paths(
    stats: dict[str, dict],
    root: str,
    max_depth: int,
) -> list[dict]:
    paths: list[dict] = []

    def rec(name: str, chain: list[tuple[str, dict]], seen: set[str]) -> None:
        if len(chain) >= max_depth:
            paths.append({"chain": list(chain), "truncated": True, "cycle": False})
            return
        calls = stats.get(name, {}).get("calls", [])
        if not calls:
            paths.append({"chain": list(chain), "truncated": False, "cycle": False})
            return
        for call in calls:
            target = call["target"]
            next_chain = chain + [(name, call)]
            if call["kind"] == "CALLPRIM" or target not in stats:
                paths.append(
                    {
                        "chain": next_chain,
                        "truncated": False,
                        "cycle": False,
                        "external": target,
                    }
                )
                continue
            if target in seen:
                paths.append({"chain": next_chain, "truncated": False, "cycle": True})
                continue
            rec(target, next_chain, seen | {target})

    rec(root, [], {root})
    return paths


def _path_cost(path: dict, stats: dict[str, dict]) -> int:
    return sum(_edge_cost(call, stats) for _, call in path["chain"])


def _path_text(path: dict) -> str:
    if not path["chain"]:
        return "<root has no calls>"
    parts = []
    for src, call in path["chain"]:
        parts.append("%s --%s/%d--> %s" % (src, call["kind"], call["argc"], call["target"]))
    suffix = ""
    if path.get("cycle"):
        suffix = " [cycle]"
    elif path.get("truncated"):
        suffix = " [truncated]"
    return " | ".join(parts) + suffix


def _reachable(stats: dict[str, dict], roots: list[str]) -> set[str]:
    out: set[str] = set()

    def rec(name: str) -> None:
        if name in out or name not in stats:
            return
        out.add(name)
        for call in stats[name]["calls"]:
            if call["kind"] in ("CALL", "TAILCALL"):
                rec(call["target"])

    for root in roots:
        rec(root)
    return out


def _write_report(
    out: Path,
    manifest_path: Path,
    blob_path: Path,
    stats: dict[str, dict],
    roots: list[str],
    max_depth: int,
    top_paths: int,
) -> None:
    reachable = _reachable(stats, roots)
    aggregate = Counter()
    prims = Counter()
    targets = Counter()
    for name in reachable:
        for call in stats[name]["calls"]:
            aggregate[call["kind"]] += 1
            targets[call["target"]] += 1
            if call["kind"] == "CALLPRIM":
                prims[call["target"]] += 1

    all_paths = []
    for root in roots:
        all_paths.extend(_walk_paths(stats, root, max_depth))
    ranked_paths = sorted(
        all_paths,
        key=lambda path: (-_path_cost(path, stats), -len(path["chain"]), _path_text(path)),
    )

    lines = [
        "# lisp65 IDE render static callgraph",
        "manifest=%s" % manifest_path,
        "blob=%s" % blob_path,
        "scope=static-bytecode",
        "roots=%s" % ",".join(roots),
        "max_depth=%d" % max_depth,
        "reachable_functions=%d" % len(reachable),
        "reachable_object_bytes=%d" % sum(stats[name]["object_bytes"] for name in reachable),
        "reachable_payload_bytes=%d" % sum(stats[name]["payload_bytes"] for name in reachable),
        "reachable_instructions=%d" % sum(stats[name]["instructions"] for name in reachable),
        "static_call_sites=%d" % aggregate["CALL"],
        "static_tailcall_sites=%d" % aggregate["TAILCALL"],
        "static_callprim_sites=%d" % aggregate["CALLPRIM"],
        "",
        "Interpretation:",
        "- CALL normally adds one recursive vm_run frame in the C VM.",
        "- TAILCALL reuses the VM frame when the target resolves to bytecode.",
        "- CALLPRIM enters native vm_callprim; apply/funcall can re-enter the VM.",
        "- This is static topology, not dynamic hotness or measured stack depth.",
        "",
        "Reachable render functions:",
        "name                             obj  pay inst CALL TAIL PRIM",
    ]
    for name in sorted(reachable, key=lambda n: (-stats[n]["payload_bytes"], n)):
        s = stats[name]
        kinds = Counter(call["kind"] for call in s["calls"])
        lines.append(
            "%-30s %4d %4d %4d %4d %4d %4d"
            % (
                name,
                s["object_bytes"],
                s["payload_bytes"],
                s["instructions"],
                kinds["CALL"],
                kinds["TAILCALL"],
                kinds["CALLPRIM"],
            )
        )

    lines.extend(["", "Direct edges:"])
    for name in sorted(reachable):
        calls = stats[name]["calls"]
        if calls:
            lines.append("- %s" % name)
            for call in calls:
                marker = ""
                if call["kind"] == "CALLPRIM":
                    marker = " native"
                elif call["kind"] == "TAILCALL" and call["target"] in stats:
                    marker = " frame-reuse"
                elif call["target"] not in stats:
                    marker = " unresolved"
                lines.append("  %s%s" % (_fmt_call(call), marker))

    lines.extend(["", "CALLPRIM targets in reachable render graph:"])
    if prims:
        for name, count in prims.most_common():
            lines.append("  %-28s %3d" % (name, count))
    else:
        lines.append("  none")

    lines.extend(["", "Highest static re-entry chains:"])
    for path in ranked_paths[:top_paths]:
        lines.append("  cost=%d depth=%d  %s" % (_path_cost(path, stats), len(path["chain"]), _path_text(path)))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--max-depth", type=int, default=8)
    ap.add_argument("--top-paths", type=int, default=40)
    ns = ap.parse_args(argv)

    manifest, blob_path, order, objects = Cost._load_code_objects(ns.manifest)
    del manifest
    stats = {name: Cost._decode_stats(name, objects[name]) for name in order}
    roots = ns.root or DEFAULT_ROOTS
    missing = [root for root in roots if root not in stats]
    if missing:
        raise SystemExit("ide-render-callgraph: missing root(s): %s" % ", ".join(missing))
    _write_report(ns.out, ns.manifest, blob_path, stats, roots, ns.max_depth, ns.top_paths)
    print(
        "ide-render-callgraph: WROTE %s roots=%d functions=%d"
        % (ns.out, len(roots), len(_reachable(stats, roots)))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
