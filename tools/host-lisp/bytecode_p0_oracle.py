#!/usr/bin/env python3
"""Oracle for pinned P0 bytecode vectors in tests/bytecode/.

Each vector carries a structured code-object description plus its golden hex.
The oracle verifies encode/decode/disassembly and runs the P0 host VM.
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _default_paths():
    return sorted(glob.glob(os.path.join(_repo_root(), "tests", "bytecode", "*.json")))


def _load_vectors(paths):
    vectors = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        root_symbols = data.get("symbols", []) if isinstance(data, dict) else []
        items = data.get("vectors", data) if isinstance(data, dict) else data
        for item in items:
            if item.get("expect_compile_error"):
                continue
            item = dict(item)
            item["_path"] = path
            item["_global_symbols"] = root_symbols
            vectors.append(item)
    return vectors


def _materialize_code(heap, spec):
    literals = tuple(B.obj_from_json(heap, lit) for lit in spec.get("literals", []))
    payload = B.parse_hex(spec["payload_hex"])
    return B.CodeObject(
        nargs=spec.get("nargs", 0),
        nlocals=spec.get("nlocals", 0),
        flags=spec.get("flags", 0),
        littab=literals,
        payload=payload,
    )


def _prepare_heap(vector):
    heap = B.Heap()
    seen = set()
    for name in list(vector.get("_global_symbols", [])) + list(vector.get("symbols", [])):
        if name not in seen:
            heap.intern(name)
            seen.add(name)
    return heap


def _run_vector(vector):
    heap = _prepare_heap(vector)
    code = _materialize_code(heap, vector["code"])
    encoded = code.encode()
    expected_hex = B.parse_hex(vector["code_object_hex"])
    if encoded != expected_hex:
        raise AssertionError(
            "code_object_hex mismatch\nexpected: %s\nactual:   %s"
            % (B.hex_bytes(expected_hex), B.hex_bytes(encoded))
        )

    decoded = B.decode_code_object(expected_hex)
    disasm = B.disassemble_code_object(decoded)
    if "expect_disasm" in vector and disasm != vector["expect_disasm"]:
        raise AssertionError(
            "disasm mismatch\nexpected:\n%s\nactual:\n%s"
            % ("\n".join(vector["expect_disasm"]), "\n".join(disasm))
        )

    directory = {}
    entry = vector.get("entry")
    if entry:
        directory[heap.intern(entry)] = decoded
    for item in vector.get("directory", []):
        if item.get("code", "self") != "self":
            raise AssertionError("only directory code='self' is supported for now")
        directory[heap.intern(item["name"])] = decoded

    args = [B.obj_from_json(heap, arg) for arg in vector.get("args", [])]
    vm = B.P0VM(heap=heap, directory=directory)
    result = vm.run(decoded, args)
    got_text = heap.obj_to_text(result)
    if got_text != vector["expect"]:
        raise AssertionError("result mismatch: expected %r, got %r" % (vector["expect"], got_text))

    if "expect_obj" in vector:
        got_obj = B.obj_hex(result)
        if got_obj.lower() != vector["expect_obj"].lower():
            raise AssertionError(
                "result obj mismatch: expected %s, got %s" % (vector["expect_obj"], got_obj)
            )
    return {"name": vector["name"], "steps": vm.steps}


def _check_d81_fixture_allocator():
    usable_sectors = (39 * 40 - 2) + (40 * 40)
    vm = B.P0VM(disk_files={"FULL": {"content": "", "capacity": usable_sectors * 254}})
    sectors = vm.disk_files["FULL"]["sectors"]
    if len(sectors) != usable_sectors or sectors[-1] != (80, 39):
        raise AssertionError("D81 fixture allocator does not fill the last data sector exactly")
    if any(track == 40 for track, _ in sectors):
        raise AssertionError("D81 fixture allocator used reserved directory track 40")
    try:
        B.P0VM(
            disk_files={
                "OVER": {"content": "", "capacity": (usable_sectors + 1) * 254}
            }
        )
    except B.VMError as exc:
        if exc.status != "DiskFull":
            raise
    else:
        raise AssertionError("D81 fixture allocator accepted a disk larger than its data tracks")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="vector JSON files")
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args(argv)

    paths = ns.paths or _default_paths()
    if not paths:
        print("bytecode-p0-oracle: no vectors found", file=sys.stderr)
        return 1

    vectors = _load_vectors(paths)
    _check_d81_fixture_allocator()
    ok = 0
    for vector in vectors:
        try:
            info = _run_vector(vector)
        except Exception as e:  # keep per-vector context visible in Make output
            print(
                "bytecode-p0-oracle: FAIL %s (%s): %s"
                % (vector.get("name", "<unnamed>"), vector.get("_path", "?"), e),
                file=sys.stderr,
            )
            return 1
        ok += 1
        if ns.verbose:
            print("PASS %-28s steps=%d" % (info["name"], info["steps"]))
    print("bytecode-p0-oracle: PASS=%d FAIL=0" % ok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
