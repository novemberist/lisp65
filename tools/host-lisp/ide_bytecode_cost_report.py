#!/usr/bin/env python3
"""Report static P0 bytecode costs for IDE-related stdlib functions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "build" / "bytecode" / "stdlib-p0.manifest.json"
DEFAULT_OUT = ROOT / "build" / "bytecode" / "ide-bytecode-costs.txt"


class ReportError(Exception):
    pass


def _resolve_path(path: str, base: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (base / p)


def _literal_name(spec):
    if isinstance(spec, dict) and "symbol" in spec:
        return spec["symbol"]
    return None


def _load_code_objects(manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blob_path = _resolve_path(manifest["blob"], ROOT)
    blob = blob_path.read_bytes()

    objects = {}
    order = []
    for entry in manifest["entries"]:
        name = entry["name"]
        start = int(entry["blob_offset"])
        length = int(entry["length"])
        if start < 0 or start + length > len(blob):
            raise ReportError("%s: blob slice outside blob" % name)
        code = B.decode_code_object(blob[start : start + length])
        objects[name] = {"entry": entry, "code": code}
        order.append(name)
    return manifest, blob_path, order, objects


def _decode_stats(name, info):
    code = info["code"]
    entry = info["entry"]
    pc = 0
    instructions = []
    op_counts = Counter()
    calls = []
    branches = []
    while pc < len(code.payload):
        at = pc
        spec, operand, pc = B.decode_instruction(code.payload, pc)
        op_counts[spec.mnemonic] += 1
        instructions.append((at, spec.mnemonic, operand, pc))
        if spec.mnemonic in ("CALL", "TAILCALL"):
            lit_idx, argc = operand
            literals = entry.get("literals", [])
            target = _literal_name(literals[lit_idx]) if lit_idx < len(literals) else None
            calls.append(
                {
                    "kind": spec.mnemonic,
                    "target": target or "<lit-%d>" % lit_idx,
                    "argc": argc,
                    "pc": at,
                }
            )
        elif spec.mnemonic == "CALLPRIM":
            prim_id, argc = operand
            calls.append(
                {
                    "kind": spec.mnemonic,
                    "target": B.PRIM_IDS.get(prim_id, "#%d" % prim_id),
                    "argc": argc,
                    "pc": at,
                }
            )
        elif spec.mnemonic in ("JMPREL", "JFALSEREL"):
            branches.append({"kind": spec.mnemonic, "pc": at, "rel": operand, "target": pc + operand})
    return {
        "name": name,
        "object_bytes": int(entry["length"]),
        "payload_bytes": len(code.payload),
        "header_lit_bytes": int(entry["length"]) - len(code.payload),
        "nargs": code.nargs,
        "nlocals": code.nlocals,
        "flags": code.flags,
        "literals": len(code.littab),
        "instructions": len(instructions),
        "decoded_instructions": instructions,
        "op_counts": op_counts,
        "calls": calls,
        "branches": branches,
    }


def _is_ide_name(name):
    return name.startswith("ide-") or name.startswith("%ide-")


def _format_calls(calls):
    if not calls:
        return "-"
    return ", ".join("%s:%s/%d@%04x" % (c["kind"], c["target"], c["argc"], c["pc"]) for c in calls)


def _format_ops(op_counts):
    if not op_counts:
        return "-"
    return ", ".join("%s=%d" % (name, count) for name, count in sorted(op_counts.items()))


def _call_targets(stats):
    return {c["target"] for c in stats["calls"]}


def _call_kinds_and_targets(stats):
    return {(c["kind"], c["target"]) for c in stats["calls"]}


def _has_pushi8(stats, value):
    for _, mnemonic, operand, _ in stats["decoded_instructions"]:
        if mnemonic == "PUSHI8" and operand == value:
            return True
    return False


def _reject_render_targets(stats, errors, context, rejected):
    bad_targets = sorted(_call_targets(stats).intersection(rejected))
    if bad_targets:
        errors.append("%s calls forbidden render target(s): %s" % (context, ", ".join(bad_targets)))


def _assert_render_contract(stats_by_name):
    errors = []
    render_string = stats_by_name.get("ide-render-string-at")
    if render_string:
        targets = _call_targets(render_string)
        if "screen-bulk-p" not in targets:
            errors.append("ide-render-string-at missing screen-bulk-p gate")
        if "screen-write-string" not in targets:
            errors.append("ide-render-string-at missing screen-write-string bulk branch")
        if "%ide-render-codes-at" not in targets:
            errors.append("ide-render-string-at missing put-char fallback helper")

    render_line = stats_by_name.get("ide-render-line-at")
    if not render_line:
        errors.append("missing ide-render-line-at")
    else:
        targets = _call_targets(render_line)
        if "screen-bulk-p" not in targets:
            errors.append("ide-render-line-at missing screen-bulk-p gate")
        if "screen-write-string" not in targets:
            errors.append("ide-render-line-at missing screen-write-string bulk branch")
        if "%ide-render-codes-at" not in targets or "%ide-pad-eol" not in targets:
            errors.append("ide-render-line-at missing put-char fallback+pad helpers")
        if not _has_pushi8(render_line, 64):
            errors.append("ide-render-line-at bulk branch missing pad-to-EOL flag")

    dirty_lines = stats_by_name.get("%ide-render-dirty-lines-at")
    if not dirty_lines:
        errors.append("missing %ide-render-dirty-lines-at")
    else:
        targets = _call_targets(dirty_lines)
        _reject_render_targets(dirty_lines, errors, "%ide-render-dirty-lines-at", {"%ide-render-codes-at", "screen-put-char", "screen-clear"})
        if "ide-render-line-at" not in targets:
            errors.append("%ide-render-dirty-lines-at missing call to ide-render-line-at")

    render = stats_by_name.get("ide-render")
    if not render:
        errors.append("missing ide-render")
    else:
        targets = _call_targets(render)
        for required in ("ide-dirty-line-indices", "%ide-render-dirty-lines-at", "ide-render-cursor-from"):
            if required not in targets:
                errors.append("ide-render missing call to %s" % required)
        if "ide-render-cursor" in targets:
            errors.append("ide-render calls ide-render-cursor wrapper instead of ide-render-cursor-from")
        if "screen-clear" in targets:
            errors.append("ide-render still calls screen-clear")

    fast_same_row = stats_by_name.get("%ide-render-fast-same-row")
    if not fast_same_row:
        errors.append("missing %ide-render-fast-same-row")
    else:
        targets = _call_targets(fast_same_row)
        if "ide-render-cursor-from" not in targets:
            errors.append("%ide-render-fast-same-row missing call to ide-render-cursor-from")
        for forbidden in ("ide-render-cursor", "ide-buffer-lines"):
            if forbidden in targets:
                errors.append("%ide-render-fast-same-row calls %s" % forbidden)

    return errors


def _write_report(out, manifest_path, blob_path, stats, focus_names, render_errors):
    focused = [stats[name] for name in focus_names]
    by_payload = sorted(focused, key=lambda s: (-s["payload_bytes"], s["name"]))
    by_object = sorted(focused, key=lambda s: (-s["object_bytes"], s["name"]))
    aggregate_ops = Counter()
    call_targets = Counter()
    reverse_calls = defaultdict(list)
    for s in focused:
        aggregate_ops.update(s["op_counts"])
        for call in s["calls"]:
            call_targets[call["target"]] += 1
            reverse_calls[call["target"]].append((s["name"], call))

    lines = [
        "# lisp65 IDE P0 static bytecode cost report",
        "manifest: %s" % manifest_path,
        "blob: %s" % blob_path,
        "scope: STATIC bytecode metadata only",
        "dynamic_dma_reload_counts: not measured",
        "warning: do not prioritize IDE helper fusion from these static ranks; "
        "use the MEGA65 DMA-reload counter for runtime hotness.",
        "ide_functions: %d" % len(focused),
        "ide_object_bytes: %d" % sum(s["object_bytes"] for s in focused),
        "ide_payload_bytes: %d" % sum(s["payload_bytes"] for s in focused),
        "ide_instructions: %d" % sum(s["instructions"] for s in focused),
        "ide_static_call_sites: %d" % sum(1 for s in focused for c in s["calls"] if c["kind"] == "CALL"),
        "ide_static_tailcall_sites: %d" % sum(1 for s in focused for c in s["calls"] if c["kind"] == "TAILCALL"),
        "render_contract: %s" % ("FAIL" if render_errors else "PASS"),
    ]
    for err in render_errors:
        lines.append("  - %s" % err)
    lines.extend(
        [
            "",
            "Top IDE functions by static payload bytes (not runtime hotness):",
            "name                             obj  pay inst lits loc calls tail prim branches",
        ]
    )
    for s in by_payload[:30]:
        lines.append(
            "%-30s %4d %4d %4d %4d %3d %5d %4d %4d %8d"
            % (
                s["name"],
                s["object_bytes"],
                s["payload_bytes"],
                s["instructions"],
                s["literals"],
                s["nlocals"],
                sum(1 for c in s["calls"] if c["kind"] == "CALL"),
                sum(1 for c in s["calls"] if c["kind"] == "TAILCALL"),
                sum(1 for c in s["calls"] if c["kind"] == "CALLPRIM"),
                len(s["branches"]),
            )
        )

    lines.extend(["", "Render-path details:"])
    for name in (
        "ide-render",
        "%ide-render-dirty-lines-at",
        "ide-render-line-at",
        "ide-render-string-at",
        "ide-render-line-text",
        "%ide-render-fast-same-row",
        "ide-render-cursor-from",
        "ide-render-cursor",
        "ide-dirty-line-indices",
        "%ide-dirty-line-indices-from",
    ):
        if name not in stats:
            continue
        s = stats[name]
        lines.append(
            "- %s: obj=%d payload=%d inst=%d calls=[%s]"
            % (name, s["object_bytes"], s["payload_bytes"], s["instructions"], _format_calls(s["calls"]))
        )
        lines.append("  ops: %s" % _format_ops(s["op_counts"]))

    lines.extend(["", "Top IDE static call targets (call-site counts, not dynamic returns):"])
    for target, count in call_targets.most_common(30):
        callers = ", ".join(name for name, _ in reverse_calls[target][:8])
        more = "" if len(reverse_calls[target]) <= 8 else " ..."
        lines.append("%-30s %3d  %s%s" % (target, count, callers, more))

    lines.extend(["", "All IDE functions by static object bytes:"])
    for s in by_object:
        lines.append(
            "- %s: obj=%d payload=%d inst=%d ops={%s} calls=[%s]"
            % (
                s["name"],
                s["object_bytes"],
                s["payload_bytes"],
                s["instructions"],
                _format_ops(s["op_counts"]),
                _format_calls(s["calls"]),
            )
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="stdlib-p0 manifest JSON")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="report output path")
    ap.add_argument("--check-render-contract", action="store_true", help="fail if IDE render path regresses")
    ns = ap.parse_args(argv)

    manifest_path = Path(ns.manifest)
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    manifest, blob_path, order, objects = _load_code_objects(manifest_path)
    stats = {name: _decode_stats(name, objects[name]) for name in order}
    focus_names = [name for name in order if _is_ide_name(name)]
    if not focus_names:
        raise ReportError("no IDE functions found in %s" % manifest_path)

    render_errors = _assert_render_contract(stats)
    _write_report(out, manifest_path, blob_path, stats, focus_names, render_errors)

    if ns.check_render_contract and render_errors:
        for err in render_errors:
            print("ide-bytecode-cost-report: FAIL: %s" % err, file=sys.stderr)
        return 1

    print(
        "ide-bytecode-cost-report: WROTE %s ide_functions=%d payload_bytes=%d static_only=1 render_contract=%s"
        % (
            out,
            len(focus_names),
            sum(stats[name]["payload_bytes"] for name in focus_names),
            "FAIL" if render_errors else "PASS",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
