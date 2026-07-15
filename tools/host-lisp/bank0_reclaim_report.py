#!/usr/bin/env python3
"""Rank native Bank-0 symbols and likely reclaim areas for lisp65."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ELF = ROOT / "build" / "lisp65-mega65-vm-stdlib-einsuite-core.prg.elf"
DEFAULT_FOOTPRINT = ROOT / "build" / "bytecode" / "mvp-vm-stdlib-einsuite-core-footprint.txt"
DEFAULT_OUT = ROOT / "build" / "bytecode" / "bank0-reclaim-report.txt"
DEFAULT_NM = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"
DEFAULT_SIZE = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-size"


def _read_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _parse_int(text: str, default: int = 0) -> int:
    try:
        return int(str(text), 0)
    except Exception:
        return default


def _nm_symbols(nm: Path, elf: Path) -> list[dict]:
    out = subprocess.check_output(
        [str(nm), "--defined-only", "--print-size", "--size-sort", "--radix=d", str(elf)],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    symbols = []
    pat = re.compile(r"^\s*([0-9]+)\s+([0-9]+)\s+(\S)\s+(.+?)\s*$")
    for line in out.splitlines():
        m = pat.match(line)
        if not m:
            continue
        addr, size, typ, name = m.groups()
        symbols.append({"addr": int(addr), "size": int(size), "type": typ, "name": name})
    return symbols


def _section_sizes(size_tool: Path, elf: Path) -> list[tuple[str, int, int]]:
    out = subprocess.check_output([str(size_tool), "-A", str(elf)], text=True, stderr=subprocess.DEVNULL)
    sections = []
    for raw in out.splitlines():
        parts = raw.split()
        if len(parts) >= 3 and parts[0].startswith("."):
            try:
                sections.append((parts[0], int(parts[1], 0), int(parts[2], 0)))
            except ValueError:
                pass
    return sections


def _cluster_name(name: str) -> str:
    return re.sub(r"\.[0-9]+$", "", name)


def _top(symbols: list[dict], types: str, limit: int) -> list[dict]:
    return sorted((s for s in symbols if s["type"] in types), key=lambda s: (-s["size"], s["name"]))[:limit]


def _write_symbol_table(lines: list[str], title: str, symbols: list[dict]) -> None:
    lines.append(title)
    lines.append("size type addr   name")
    for sym in symbols:
        lines.append("%4d  %s  $%04x  %s" % (sym["size"], sym["type"], sym["addr"], sym["name"]))
    if not symbols:
        lines.append("  none")
    lines.append("")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", type=Path, default=DEFAULT_ELF)
    ap.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--nm", type=Path, default=DEFAULT_NM)
    ap.add_argument("--size", type=Path, default=DEFAULT_SIZE)
    ap.add_argument("--top", type=int, default=35)
    ns = ap.parse_args(argv)

    fp = _read_kv(ns.footprint)
    symbols = _nm_symbols(ns.nm, ns.elf)
    sections = _section_sizes(ns.size, ns.elf)

    clusters: dict[str, dict] = defaultdict(lambda: {"allocations": {}, "names": []})
    for sym in symbols:
        if sym["type"] not in "tTrRdDbB":
            continue
        base = _cluster_name(sym["name"])
        physical_key = (sym["type"].lower(), sym["addr"], sym["size"])
        clusters[base]["allocations"].setdefault(physical_key, []).append(sym["name"])
        clusters[base]["names"].append(sym["name"])
    clone_clusters = []
    for name, info in clusters.items():
        allocations = info["allocations"]
        size = sum(key[2] for key in allocations)
        if len(allocations) > 1 and size >= 80:
            clone_clusters.append(
                {
                    "name": name,
                    "size": size,
                    "count": len(allocations),
                    "aliases": len(info["names"]),
                    "names": info["names"],
                }
            )
    clone_clusters.sort(key=lambda item: (-item["size"], item["name"]))

    reserve = _parse_int(fp.get("bank0_reserve_bytes", "0"))
    stack_gap = _parse_int(fp.get("stack_gap_bytes", "0"))
    target = _parse_int(fp.get("bank0_reserve_target_bytes", "1024"))
    need_guard = max(0, 300 - reserve)
    need_edma = max(0, 450 - reserve)

    lines = [
        "# lisp65 Bank-0 reclaim report",
        "elf=%s" % ns.elf,
        "footprint=%s" % ns.footprint,
        "status=%s" % fp.get("status", "missing"),
        "prg_bytes=%s" % fp.get("prg_bytes", "missing"),
        "bank0_text_data_bytes=%s" % fp.get("bank0_text_data_bytes", "missing"),
        "bank0_bss_bytes=%s" % fp.get("bank0_bss_bytes", "missing"),
        "stack_gap_bytes=%s" % fp.get("stack_gap_bytes", "missing"),
        "bank0_reserve_bytes=%s" % fp.get("bank0_reserve_bytes", "missing"),
        "bank0_reserve_target_bytes=%s" % fp.get("bank0_reserve_target_bytes", "missing"),
        "estimated_reclaim_for_stack_guard_300b=%d" % need_guard,
        "estimated_reclaim_for_edma_scroll_450b=%d" % need_edma,
        "estimated_reclaim_for_1kb_target=%d" % max(0, target - reserve),
        "",
        "Sections:",
        "name               size  addr",
    ]
    for name, size, addr in sections:
        lines.append("%-16s %5d  $%04x" % (name, size, addr))
    lines.append("")

    _write_symbol_table(lines, "Top text/rodata/data symbols:", _top(symbols, "tTrRdD", ns.top))
    _write_symbol_table(lines, "Top bss/noinit symbols:", _top(symbols, "bB", ns.top))

    lines.append("Clone/variant clusters (same symbol base after .NNN suffix stripping):")
    lines.append("size physical aliases base                 variants")
    for item in clone_clusters[: ns.top]:
        variants = ", ".join(item["names"][:8])
        if len(item["names"]) > 8:
            variants += ", ..."
        lines.append(
            "%4d  %8d %7d %-20s %s"
            % (item["size"], item["count"], item["aliases"], item["name"], variants)
        )
    if not clone_clusters:
        lines.append("  none")
    lines.extend(
        [
            "",
            "Reading guide:",
            "- Large text symbols are candidates only after call-site/runtime review.",
            "- Clone clusters point at possible inline/static duplication, not automatic wins.",
            "- BSS reductions move __heap_start down one byte per byte saved and directly increase stack_gap.",
            "- Text reductions help both PRG size and bank0 reserve by moving heap_start down.",
        ]
    )

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("bank0-reclaim-report: WROTE %s stack_gap=%d reserve=%d" % (ns.out, stack_gap, reserve))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
