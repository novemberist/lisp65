#!/usr/bin/env python3
"""Report runtime symbol/namepool pressure for the embedded MVP VM stdlib."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shlex
import subprocess
from collections.abc import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "build" / "bytecode" / "stdlib-p0.manifest.json"
DEFAULT_EVAL_C = ROOT / "src" / "eval.c"
MAX_INTERN_NAME_LEN = 32


def parse_int(text: object) -> int:
    s = str(text).strip()
    if s.endswith(("u", "U")):
        s = s[:-1]
    return int(s, 0)


def d_flags(cflags: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in shlex.split(cflags or ""):
        if not token.startswith("-D"):
            continue
        item = token[2:]
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, "1"
        out[key] = value
    return out


def git_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _pp_expr_value(expr: str, defines: set[str]) -> bool:
    expr = re.sub(
        r"\bdefined\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        lambda m: "True" if m.group(1) in defines else "False",
        expr,
    )
    expr = re.sub(
        r"\bdefined\s+([A-Za-z_][A-Za-z0-9_]*)",
        lambda m: "True" if m.group(1) in defines else "False",
        expr,
    )
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!\s*(?!=)", " not ", expr)
    def replace_identifier(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in {"True", "False", "and", "or", "not"}:
            return token
        return "0"

    expr = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", replace_identifier, expr)
    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return True


def _active_c_text(text: str, initial_defines: Iterable[str]) -> str:
    defines = set(initial_defines)
    out: list[str] = []
    stack: list[dict[str, bool]] = []

    def active() -> bool:
        return all(frame["active"] for frame in stack)

    for line in text.splitlines():
        directive = re.match(r"\s*#\s*(\w+)(.*)$", line)
        if not directive:
            if active():
                out.append(line)
            continue
        op, rest = directive.group(1), directive.group(2).strip()
        if op == "ifdef":
            parent = active()
            cond = rest.split(None, 1)[0] in defines if rest else False
            stack.append({"parent": parent, "active": parent and cond, "taken": parent and cond})
        elif op == "ifndef":
            parent = active()
            cond = rest.split(None, 1)[0] not in defines if rest else False
            stack.append({"parent": parent, "active": parent and cond, "taken": parent and cond})
        elif op == "if":
            parent = active()
            cond = _pp_expr_value(rest, defines) if parent else False
            stack.append({"parent": parent, "active": parent and cond, "taken": parent and cond})
        elif op == "elif":
            if stack:
                frame = stack[-1]
                if not frame["parent"] or frame["taken"]:
                    frame["active"] = False
                else:
                    cond = _pp_expr_value(rest, defines)
                    frame["active"] = cond
                    frame["taken"] = cond
        elif op == "else":
            if stack:
                frame = stack[-1]
                frame["active"] = frame["parent"] and not frame["taken"]
                frame["taken"] = True
        elif op == "endif":
            if stack:
                stack.pop()
        elif op == "define":
            if active():
                match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", rest)
                if match:
                    defines.add(match.group(1))
        elif op == "undef":
            if active():
                match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", rest)
                if match:
                    defines.discard(match.group(1))
        elif active():
            out.append(line)
    return "\n".join(out)


def native_symbols(
    eval_c: Path,
    defines: Iterable[str] = (),
) -> tuple[set[str], set[str], set[str]]:
    text = _active_c_text(eval_c.read_text(encoding="utf-8"), defines)
    prim_names = set(re.findall(r'defprim\("([^"]+)"', text))
    intern_names = set(re.findall(r'\bintern\("([^"]+)"', text))
    names = prim_names | intern_names
    names.add("t")
    return names, prim_names, intern_names


def native_symbols_from_sources(
    sources: Iterable[Path],
    defines: Iterable[str] = (),
) -> tuple[set[str], set[str], set[str]]:
    names: set[str] = set()
    prim_names: set[str] = set()
    intern_names: set[str] = set()
    for source in sources:
        source_names, source_prim_names, source_intern_names = native_symbols(source, defines)
        names.update(source_names)
        prim_names.update(source_prim_names)
        intern_names.update(source_intern_names)
    names.add("t")
    return names, prim_names, intern_names


def manifest_symbols(manifest: dict) -> tuple[set[str], set[str]]:
    entries = {
        entry["name"]
        for entry in manifest.get("entries", [])
        if (isinstance(entry.get("name"), str) and entry.get("name")
            and not entry.get("anonymous", False))
    }
    literal_symbols = {
        node["name"]
        for node in manifest.get("literal_nodes", [])
        if int(node.get("kind", 0)) == 4 and isinstance(node.get("name"), str) and node.get("name")
    }
    return entries, literal_symbols


def codebuf_budget(manifest: dict) -> dict[str, object]:
    entries = manifest.get("entries", [])
    max_entry = None
    max_required = 0
    for entry in entries:
        lit_count = int(entry.get("lit_count", 0))
        required = 7 + 2 * lit_count + 3
        if required > max_required:
            max_required = required
            max_entry = entry
    return {
        "required": max_required,
        "entry": max_entry.get("name", "-") if isinstance(max_entry, dict) else "-",
        "lit_count": int(max_entry.get("lit_count", 0)) if isinstance(max_entry, dict) else 0,
    }


def namepool_bytes(names: set[str]) -> int:
    return sum(len(name) + 1 for name in names)


def _status(
    sym_headroom: int | None,
    min_sym_headroom: int,
    namepool_headroom: int | None,
    dir_headroom: int | None,
    codebuf_headroom: int | None,
    long_names: list[str],
) -> str:
    problems = []
    if long_names:
        problems.append("name-too-long")
    if sym_headroom is not None and sym_headroom < 0:
        problems.append("max-sym-too-small")
    if sym_headroom is not None and sym_headroom < min_sym_headroom:
        problems.append("symbol-headroom-too-small")
    if namepool_headroom is not None and namepool_headroom < 0:
        problems.append("namepool-too-small")
    if dir_headroom is not None and dir_headroom < 0:
        problems.append("vm-dir-too-small")
    if codebuf_headroom is not None and codebuf_headroom < 0:
        problems.append("vm-codebuf-too-small")
    return "ok" if not problems else ",".join(problems)


def compute_budget(
    manifest_path: Path = DEFAULT_MANIFEST,
    eval_c: Path = DEFAULT_EVAL_C,
    max_sym: int | None = None,
    namepool: int | None = None,
    extra_cflags: str = "",
    target_defines: Iterable[str] = ("__MEGA65__",),
    native_sources: Iterable[Path] = (),
    min_sym_headroom: int = 0,
    symbol_correction: int = 0,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    defines = d_flags(extra_cflags)
    if max_sym is None and "MAX_SYM" in defines:
        max_sym = parse_int(defines["MAX_SYM"])
    if namepool is None and "NAMEPOOL" in defines:
        namepool = parse_int(defines["NAMEPOOL"])
    vm_dir_max = parse_int(defines["VM_DIR_MAX"]) if "VM_DIR_MAX" in defines else None
    vm_codebuf = parse_int(defines["VM_CODEBUF"]) if "VM_CODEBUF" in defines else None

    active_defines = set(defines)
    active_defines.update(target_defines)
    native_paths = [eval_c, *native_sources]
    native, native_prim_symbols, native_intern_symbols = native_symbols_from_sources(
        native_paths,
        active_defines,
    )
    entries, literal_symbols = manifest_symbols(manifest)
    after_directory = native | entries
    all_runtime = after_directory | literal_symbols
    required_namepool = namepool_bytes(all_runtime)
    long_names = sorted(name for name in all_runtime if len(name) > MAX_INTERN_NAME_LEN)

    required_symbols = len(all_runtime) + symbol_correction
    sym_headroom = None if max_sym is None else max_sym - required_symbols
    namepool_headroom = None if namepool is None else namepool - required_namepool
    dir_entries = len(manifest.get("entries", []))
    dir_headroom = None if vm_dir_max is None else vm_dir_max - dir_entries
    codebuf = codebuf_budget(manifest)
    codebuf_headroom = None if vm_codebuf is None else vm_codebuf - int(codebuf["required"])

    return {
        "status": _status(
            sym_headroom,
            min_sym_headroom,
            namepool_headroom,
            dir_headroom,
            codebuf_headroom,
            long_names,
        ),
        "manifest": str(manifest_path),
        "eval_c": str(eval_c),
        "native_sources": [str(path) for path in native_paths],
        "target_defines": sorted(target_defines),
        "max_sym": max_sym,
        "namepool": namepool,
        "vm_dir_max": vm_dir_max,
        "vm_dir_entries": dir_entries,
        "vm_dir_headroom": dir_headroom,
        "vm_codebuf": vm_codebuf,
        "vm_codebuf_required": int(codebuf["required"]),
        "vm_codebuf_headroom": codebuf_headroom,
        "vm_codebuf_worst_entry": str(codebuf["entry"]),
        "vm_codebuf_worst_lit_count": int(codebuf["lit_count"]),
        "required_symbols": required_symbols,
        "static_required_symbols": len(all_runtime),
        "symbol_correction": symbol_correction,
        "min_sym_headroom": min_sym_headroom,
        "required_namepool_bytes": required_namepool,
        "sym_headroom": sym_headroom,
        "namepool_headroom": namepool_headroom,
        "native_symbols": len(native),
        "native_prim_symbols": len(native_prim_symbols),
        "native_intern_symbols": len(native_intern_symbols),
        "entry_symbols": len(entries),
        "literal_symbol_names": len(literal_symbols),
        "literal_symbol_nodes": sum(
            1 for node in manifest.get("literal_nodes", []) if int(node.get("kind", 0)) == 4
        ),
        "literal_nodes": len(manifest.get("literal_nodes", [])),
        "literal_patches": len(manifest.get("literal_patches", [])),
        "after_eval_init_symbols": len(native),
        "after_directory_symbols": len(after_directory),
        "after_literal_materialization_symbols": len(all_runtime),
        "directory_new_symbols": len(entries - native),
        "literal_new_symbols": len(literal_symbols - after_directory),
        "functions": len(manifest.get("functions", [])),
        "objects": int(manifest.get("objects", 0)),
        "entries": dir_entries,
        "code_bytes": int(manifest.get("code_bytes", 0)),
        "directory_bytes": int(manifest.get("directory_bytes", 0)),
        "long_names": long_names,
        "longest_names": sorted(all_runtime, key=lambda name: (-len(name), name))[:15],
        "literal_only_symbols": sorted(literal_symbols - after_directory),
        "native_intern_only_symbols": sorted(native_intern_symbols - native_prim_symbols),
    }


def _value(value: object) -> str:
    return "unknown" if value is None else str(value)


def report_lines(info: dict) -> list[str]:
    lines = [
        "lisp65 mvp vm stdlib boot budget report",
        "built_at=%s" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit=%s" % git_short(),
        "status=%s" % info["status"],
        "",
        "Inputs:",
        "manifest=%s" % info["manifest"],
        "eval_c=%s" % info["eval_c"],
        "native_sources=%s" % ",".join(info["native_sources"]),
        "target_defines=%s" % (",".join(info["target_defines"]) if info["target_defines"] else "none"),
        "",
        "Runtime budget:",
        "max_sym=%s" % _value(info["max_sym"]),
        "required_symbols=%d" % info["required_symbols"],
        "static_required_symbols=%d" % info["static_required_symbols"],
        "symbol_correction=%d" % info["symbol_correction"],
        "min_sym_headroom=%d" % info["min_sym_headroom"],
        "sym_headroom=%s" % _value(info["sym_headroom"]),
        "namepool=%s" % _value(info["namepool"]),
        "required_namepool_bytes=%d" % info["required_namepool_bytes"],
        "namepool_headroom=%s" % _value(info["namepool_headroom"]),
        "vm_dir_max=%s" % _value(info["vm_dir_max"]),
        "vm_dir_entries=%d" % info["vm_dir_entries"],
        "vm_dir_headroom=%s" % _value(info["vm_dir_headroom"]),
        "vm_codebuf=%s" % _value(info["vm_codebuf"]),
        "vm_codebuf_required=%d" % info["vm_codebuf_required"],
        "vm_codebuf_headroom=%s" % _value(info["vm_codebuf_headroom"]),
        "vm_codebuf_worst_entry=%s" % info["vm_codebuf_worst_entry"],
        "vm_codebuf_worst_lit_count=%d" % info["vm_codebuf_worst_lit_count"],
        "",
        "Boot stages:",
        "after_eval_init_symbols=%d" % info["after_eval_init_symbols"],
        "directory_new_symbols=%d" % info["directory_new_symbols"],
        "after_directory_symbols=%d" % info["after_directory_symbols"],
        "literal_new_symbols=%d" % info["literal_new_symbols"],
        "after_literal_materialization_symbols=%d" % info["after_literal_materialization_symbols"],
        "",
        "Artifact summary:",
        "functions=%d" % info["functions"],
        "objects=%d" % info["objects"],
        "entries=%d" % info["entries"],
        "entry_symbols=%d" % info["entry_symbols"],
        "native_symbols=%d" % info["native_symbols"],
        "native_prim_symbols=%d" % info["native_prim_symbols"],
        "native_intern_symbols=%d" % info["native_intern_symbols"],
        "literal_nodes=%d" % info["literal_nodes"],
        "literal_symbol_nodes=%d" % info["literal_symbol_nodes"],
        "literal_symbol_names=%d" % info["literal_symbol_names"],
        "literal_patches=%d" % info["literal_patches"],
        "code_bytes=%d" % info["code_bytes"],
        "directory_bytes=%d" % info["directory_bytes"],
        "",
        "Intern constraints:",
        "max_intern_name_len=%d" % MAX_INTERN_NAME_LEN,
        "long_name_count=%d" % len(info["long_names"]),
    ]
    if info["long_names"]:
        lines.append("long_names=%s" % ",".join(info["long_names"]))
    lines.extend(
        [
            "",
            "Literal-only symbols:",
            "literal_only_symbols=%s"
            % (",".join(info["literal_only_symbols"]) if info["literal_only_symbols"] else "none"),
            "",
            "Native intern-only symbols:",
            "native_intern_only_symbols=%s"
            % (
                ",".join(info["native_intern_only_symbols"])
                if info["native_intern_only_symbols"]
                else "none"
            ),
            "",
            "Longest runtime names:",
        ]
    )
    for name in info["longest_names"]:
        lines.append("%d %s" % (len(name), name))
    return lines


def write_report(path: Path, lines: list[str]) -> None:
    if str(path) == "-":
        print("\n".join(lines))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--eval-c", type=Path, default=DEFAULT_EVAL_C)
    ap.add_argument("--native-c", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, default=Path("-"))
    ap.add_argument("--max-sym", type=parse_int)
    ap.add_argument("--namepool", type=parse_int)
    ap.add_argument("--min-symbol-headroom", type=int, default=0)
    ap.add_argument("--extra-cflags", default="")
    ap.add_argument("--target-define", action="append", default=["__MEGA65__"])
    ap.add_argument(
        "--symbol-correction",
        type=int,
        default=0,
        help="add measured runtime-only symbols not inferable from the static manifest",
    )
    ap.add_argument(
        "--fail-on-over-budget",
        action="store_true",
        help="return non-zero when MAX_SYM/NAMEPOOL cannot cover the boot set",
    )
    ns = ap.parse_args(argv)

    info = compute_budget(
        manifest_path=ns.manifest,
        eval_c=ns.eval_c,
        max_sym=ns.max_sym,
        namepool=ns.namepool,
        extra_cflags=ns.extra_cflags,
        target_defines=ns.target_define,
        native_sources=ns.native_c,
        min_sym_headroom=ns.min_symbol_headroom,
        symbol_correction=ns.symbol_correction,
    )
    write_report(ns.out, report_lines(info))
    destination = "stdout" if str(ns.out) == "-" else str(ns.out)
    print(
        "mvp-vm-stdlib-boot-budget: status=%s symbols=%d/%s namepool=%d/%s report=%s"
        % (
            info["status"],
            info["required_symbols"],
            _value(info["max_sym"]),
            info["required_namepool_bytes"],
            _value(info["namepool"]),
            destination,
        )
    )
    if ns.fail_on_over_budget and info["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
