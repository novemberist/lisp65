#!/usr/bin/env python3
"""Execute actual native admission helpers on the host; never an ELF claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import re

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/host-lisp/fixtures/comfort_entry_context.c"
SOURCE = ROOT / "src/repl.c"


def query_tests(work):
    reader_path, io_path = ROOT / "src/reader.c", ROOT / "src/io.c"
    reader = reader_path.read_text()
    match = re.search(r"unsigned char io_source_terminal\(void\) \{.*?\n\}", io_path.read_text(), re.S)
    if not match:
        raise RuntimeError("IO terminal source predicate missing")
    io = match.group()
    mutations = {
        "file-position-equals-length-with-unread-form": ("io", io,
            "unsigned char io_source_terminal(void) { return disk_file_pos == disk_file_len; }"),
        "query-consumes-input": ("reader", "return rd_sc == '\\0' && rd_sn == '\\0';",
            "return reader_skip_peek() == '\\0';"),
        "query-ignores-unread-lookahead": ("reader", "rd_sc == '\\0' && rd_sn == '\\0'", "rd_sn == '\\0'"),
        "query-ignores-invalid-source-link": ("io", "(disk_source_link & DISK_SOURCE_LINK_VALID)", "1"),
    }
    results = []
    fixture = ROOT / "tools/host-lisp/fixtures/comfort_reader_query.c"
    for name in ["query-control", *mutations]:
        sources = {"reader": reader, "io": io}
        if name in mutations:
            target, old, new = mutations[name]
            if sources[target].count(old) != 1:
                raise RuntimeError("query mutation anchor drift: " + name)
            sources[target] = sources[target].replace(old, new)
        (work / "reader.c").write_text(sources["reader"])
        (work / "io_terminal.c").write_text(sources["io"])
        binary = work / "query"
        subprocess.run(["cc", "-std=c11", "-ffunction-sections", "-fdata-sections",
                        "-I" + str(work), "-I" + str(ROOT / "src"), str(fixture),
                        "-Wl,--gc-sections", "-o", str(binary)], check=True, capture_output=True)
        run = subprocess.run([str(binary)], cwd=work, capture_output=True, timeout=5)
        if (name == "query-control") != (run.returncode == 0):
            raise RuntimeError("query control/mutation failed: " + name)
        results.append({"case": name, "exit": run.returncode})
    return {"cases": results, "sources": [
        {"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in (reader_path, io_path, fixture)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = SOURCE.read_text()
    vm_source = (ROOT / "src/vm.c").read_text()
    mode = re.search(r"case 20:.*?#ifdef LISP65_COMFORT_TRAMPOLINE\n(.*?)#endif", vm_source, re.S)
    if not mode:
        raise RuntimeError("Prim20 source mode block missing")
    mode = mode.group(1)
    mutations = {
        "depth-check-removed": ("repl_vm_depth != (uint8_t)(repl_base_depth + 2u)", "0"),
        "context-check-removed": ("!repl_context ||", ""),
        "terminal-check-removed": ("!io_source_terminal()", "0"),
        "nested-stream-allowed": ("repl_stream_depth == 1u ? 2u : 0u", "repl_stream_depth >= 1u ? 2u : 0u"),
        "ordinary-load-jumps": ("if (repl_booting && repl_input_entry != NIL)", "if (repl_input_entry != NIL)"),
        "handoff-uses-error-landing": ("longjmp(lisp_toplevel, 2)", "longjmp(lisp_toplevel, 1)"),
    }
    results = []
    with tempfile.TemporaryDirectory(prefix="comfort-entry-context-") as directory:
        work = Path(directory)
        owner_mutations = {
            "executing-owner-check-removed": ("a[1] != MK_BCODE(vm_buf_off)", "0"),
            "executing-bank-check-removed": ("vm_buf_bank != LISP65_C2_CODE_BANK_TAG", "0"),
        }
        for name in ["control", *mutations, *owner_mutations]:
            text = source
            mode_text = mode
            if name in owner_mutations:
                old, new = owner_mutations[name]
                if mode_text.count(old) != 1:
                    raise RuntimeError("owner mutation anchor drift: " + name)
                mode_text = mode_text.replace(old, new)
            elif name != "control":
                old, new = mutations[name]
                if text.count(old) != 1:
                    raise RuntimeError("mutation anchor drift: " + name)
                text = text.replace(old, new)
            # Mechanical mutation of the actual translation unit, not a
            # reimplementation of its decision logic.
            (work / "repl.c").write_text(text)
            (work / "prim20.c").write_text(mode_text)
            binary = work / "fixture"
            command = ["cc", "-std=c11", "-ffunction-sections", "-fdata-sections",
                       "-I" + str(work), "-I" + str(ROOT / "src"), str(FIXTURE),
                       "-Wl,--gc-sections", "-o", str(binary)]
            subprocess.run(command, check=True, capture_output=True)
            try:
                run = subprocess.run([str(binary)], cwd=work, capture_output=True, timeout=5)
                status = run.returncode
            except subprocess.TimeoutExpired:
                # A mistaken continuation can return to its old setjmp again.
                status = "timeout"
            if (name == "control") != (status == 0):
                raise RuntimeError("unexpected admission result: " + name)
            results.append({"case": name, "exit": status})
        queries = query_tests(work)
    report = {
        "status": "host-native-source-admission-pass",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "vm_source_sha256": hashlib.sha256(vm_source.encode()).hexdigest(),
        "cases": results,
        "reader_query": queries,
        "limits": ["host ABI, not final MOS emission", "stream-terminal predicate is supplied by fixture",
                   "no measured hardware-stack or timing claim", "no packed-medium claim"],
        "budget": {"seed_WPLTO": 0, "final_C_LTO": 0, "product_links": 0, "host_images": 0},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
