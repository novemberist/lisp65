#!/usr/bin/env python3
"""Verify the evaluator-free Runtime Core link and named entry contract."""

import argparse
import json
import subprocess
from pathlib import Path


FORBIDDEN = {
    "apply",
    "compile_top_form",
    "crepl_boot_init",
    "eval",
    "eval_init",
    "eval_vm_bridge",
    "lcc_install_obj",
    "load_source_stream",
    "read_atom",
    "read_expr",
    "read_expr_1",
    "repl",
}

REQUIRED = {
    "main",
    "vm_run",
}


def parse_nm(text):
    symbols = set()
    for raw in text.splitlines():
        fields = raw.split()
        if len(fields) >= 2:
            symbols.add(fields[-1])
    return symbols


def load_entry(manifest_path, entry_name):
    with open(manifest_path, "r", encoding="ascii") as handle:
        manifest = json.load(handle)
    matches = [entry for entry in manifest.get("entries", []) if entry.get("name") == entry_name]
    if len(matches) != 1:
        raise ValueError("entry %r occurs %d times" % (entry_name, len(matches)))
    entry = matches[0]
    if entry.get("kind") != "function" or int(entry.get("flags", -1)) != 0:
        raise ValueError("entry %r is not a plain function" % entry_name)

    blob_path = Path(manifest["blob"])
    blob = blob_path.read_bytes()
    offset = int(entry["blob_offset"])
    length = int(entry["length"])
    if offset < 0 or length < 2 or offset + length > len(blob):
        raise ValueError("entry %r has an invalid blob span" % entry_name)
    if blob[offset] != 0xB5:
        raise ValueError("entry %r has no bytecode object magic" % entry_name)
    if blob[offset + 1] != 0:
        raise ValueError("entry %r must accept zero arguments" % entry_name)
    return entry


def selftest():
    sample = "00002001 00000010 T main\n00002011 t local.name\n         U external\n"
    symbols = parse_nm(sample)
    assert symbols == {"main", "local.name", "external"}
    assert not (symbols & FORBIDDEN)
    assert "main" in symbols
    print("runtime-core-audit selftest: PASS cases=4")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf")
    parser.add_argument("--manifest")
    parser.add_argument("--entry")
    parser.add_argument("--nm", default="llvm-nm")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    missing = [name for name in ("elf", "manifest", "entry") if getattr(args, name) is None]
    if missing:
        parser.error("required arguments missing: %s" % ", ".join("--" + name for name in missing))

    proc = subprocess.run(
        [args.nm, "-S", "--defined-only", args.elf],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    symbols = parse_nm(proc.stdout)
    forbidden = sorted(symbols & FORBIDDEN)
    required_missing = sorted(REQUIRED - symbols)
    if forbidden:
        raise SystemExit("runtime-core-audit: FAIL forbidden symbols: %s" % ", ".join(forbidden))
    if required_missing:
        raise SystemExit("runtime-core-audit: FAIL missing symbols: %s" % ", ".join(required_missing))
    try:
        entry = load_entry(args.manifest, args.entry)
    except (KeyError, OSError, ValueError) as exc:
        raise SystemExit("runtime-core-audit: FAIL %s" % exc)

    print(
        "runtime-core-audit: PASS symbols=%d forbidden=0 entry=%s entry_bytes=%d nargs=0"
        % (len(symbols), args.entry, int(entry["length"]))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
