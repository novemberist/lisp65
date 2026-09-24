#!/usr/bin/env python3
"""Declarative host D81 edge worlds for the widened bytecode_p0 disk model.

A world spec is a plain dict:

    {"name": "w3-libs-20",
     "files": [{"name": "LIB01", "size": 600},            # synthetic bytes
               {"name": "INIT.L65", "text": "(defun a () 1)"},
               {"name": "L65INDEX", "hex": "...", "track": 80, "sector": 38},
               {"name": "X", "size": 300, "sectors": [[1, 5], [9, 9]]}],
     "directory_sectors": 37,          # optional: pad the directory chain
     "cyclic_directory": true,         # optional: last dir sector -> 40/3
     "read_fail": ["40/4", {"file": "BIG", "chunk": 2}],
     "failure_semantics": "host-nil"}  # or "product-abort"

world_kwargs(spec) turns it into P0VM keyword arguments; world_image(spec)
renders the 819,200-byte D81 image the model serves (faults are not
representable in an image and travel in the sidecar JSON).  PRESETS holds
the part-2 edge worlds of docs/planning/assumption-inventory-1.md §3.

    python3 tools/host-lisp/host_d81_worlds.py --selftest
    python3 tools/host-lisp/host_d81_worlds.py --list
    python3 tools/host-lisp/host_d81_worlds.py --emit build/host-d81-worlds [--world NAME]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import bytecode_p0 as B  # noqa: E402

D81_IMAGE_BYTES = B.D81_TRACKS * B.D81_SECTORS * B.D81_SECTOR_BYTES


def _synthetic(size: int, seed: str) -> bytes:
    """Deterministic printable bytes (no NUL, no CR), independent of Python hash."""
    salt = hashlib.sha256(seed.encode()).digest()[0]
    return bytes(33 + ((i * 7 + salt) % 90) for i in range(size))


def _file_spec(row: dict) -> tuple[str, dict]:
    if "text" in row:
        payload = row["text"].encode("latin-1")
    elif "hex" in row:
        payload = bytes.fromhex(row["hex"])
    elif "bytes" in row:
        payload = bytes(row["bytes"])
    else:
        payload = _synthetic(int(row["size"]), row["name"])
    spec = {"bytes": payload, "capacity": int(row.get("capacity", len(payload)))}
    for key in ("track", "sector", "sectors", "type"):
        if key in row:
            spec[key] = row[key]
    return row["name"], spec


def _materialize(spec: dict) -> dict:
    disk_files = dict(_file_spec(row) for row in spec.get("files", ()))
    kwargs = {
        "disk_files": disk_files,
        "d81_bam_model": bool(spec.get("bam", True)),
        "d81_full_geometry": bool(spec.get("full_geometry", True)),
        "d81_directory_sectors": spec.get("directory_sectors"),
        "disk_failure_semantics": spec.get("failure_semantics", "host-nil"),
    }
    probe = B.P0VM(**kwargs)
    raw = {}
    if spec.get("cyclic_directory"):
        last = B.D81_DIR_FIRST_SECTOR + probe.d81_directory_sector_count - 1
        probe._disk_read_sector_impl(B.D81_DIR_TRACK, last)
        data = list(probe.disk_buf)
        data[0], data[1] = B.D81_DIR_TRACK, B.D81_DIR_FIRST_SECTOR
        raw["%d/%d" % (B.D81_DIR_TRACK, last)] = data
    faults = []
    for item in spec.get("read_fail", ()):
        if isinstance(item, dict):
            key = probe._disk_fixture_name(item["file"])
            faults.append(tuple(probe.disk_files[key]["sectors"][int(item["chunk"])]))
        else:
            faults.append(B._d81_ts(item))
    kwargs["disk_raw_sectors"] = raw
    kwargs["disk_read_fail_sectors"] = faults
    return kwargs


def world_kwargs(spec: dict) -> dict:
    return _materialize(spec)


def world_vm(spec: dict, **extra) -> B.P0VM:
    kwargs = dict(world_kwargs(spec))
    kwargs.update(extra)
    return B.P0VM(**kwargs)


def file_table(vm: B.P0VM) -> list[dict]:
    return [
        {"name": name, "track": meta["track"], "sector": meta["sector"],
         "blocks": len(meta["sectors"]), "bytes": len(meta["content"]),
         "capacity": meta["capacity"], "last": list(meta["sectors"][-1])}
        for name, meta in vm.disk_files.items()
    ]


def world_image(spec: dict) -> bytes:
    vm = world_vm(spec)
    out = bytearray(D81_IMAGE_BYTES)
    for track in range(1, B.D81_TRACKS + 1):
        for sector in range(B.D81_SECTORS):
            if vm._disk_read_sector_impl(track, sector):
                offset = ((track - 1) * B.D81_SECTORS + sector) * B.D81_SECTOR_BYTES
                out[offset : offset + B.D81_SECTOR_BYTES] = bytes(vm.disk_buf)
    return bytes(out)


def image_sector(image: bytes, track: int, sector: int) -> bytes:
    offset = ((track - 1) * B.D81_SECTORS + sector) * B.D81_SECTOR_BYTES
    return image[offset : offset + B.D81_SECTOR_BYTES]


# ---------------------------------------------------------------- presets
def _libs(count: int, size: int = 600) -> list[dict]:
    return [{"name": "LIB%02d" % i, "size": size} for i in range(1, count + 1)]


INDEX_ROWS_FOR_SECTORS = {2: 5, 3: 10, 4: 16, 5: 21, 6: 26, 7: 32, 8: 32}


def index_bytes(rows: int) -> bytes:
    import c2_require_resolver_gate as G

    records = [
        dict(name="lib%02d" % i, track=18, sector=i % 40, combined_crc32=i + 1,
             dependencies=[], execution_source=2, artifact_bytes=512, bank2=16,
             images=1, entries=1, resolutions=1, roots=1, scratch=8)
        for i in range(rows)
    ]
    return G.encode_index(records)


def _index_world(sectors: int, placement: str) -> dict:
    data = index_bytes(INDEX_ROWS_FOR_SECTORS[sectors])
    row = {"name": "L65INDEX", "hex": data.hex(), "capacity": max(len(data), sectors * 254 if sectors == 8 else len(data))}
    if placement == "t18s34":
        row.update(track=18, sector=34)
    elif placement == "end-80-39":
        row.update(track=80, sector=40 - sectors)
    elif placement == "across-40":
        row.update(track=39, sector=40 - (sectors + 1) // 2)
    note = ("a valid index holds at most 32 rows = 7 sectors; the eighth is a "
            "padding sector, so the parser's fuel edge is not crossed"
            if sectors == 8 else "")
    return {"name": "w4-index-%d-%s" % (sectors, placement),
            "files": [{"name": "PLACE", "size": 600}, row], "note": note}


def _init_world(variant: str, sectors: int = 3) -> dict:
    mid = {"require": "(require 'place)", "load-lib": '(load-lib "place")',
           "load": '(load "other")', "dir": "(dir)"}[variant]
    head = "(defun init-a () 1)\n" + mid + "\n"
    # Pad with a comment so the mid form ends inside sector 1 and the rest
    # of the source spans `sectors` sectors.
    body = ";" + "x" * (254 * sectors - len(head) - 40) + "\n"
    text = head + body + "(defun init-b () 2)\n"
    return {"name": "w2-init-%s-%d" % (variant, sectors),
            "files": [{"name": "INIT.L65", "text": text},
                      {"name": "PLACE", "size": 600},
                      {"name": "OTHER", "text": "(defun other () 3)\n"}]}


def _presets() -> dict[str, dict]:
    worlds = []
    for n in (1, 4, 8, 20):
        worlds.append({"name": "w3-libs-%d" % n, "files": _libs(n)})
    for k in range(2, 9):
        for placement in ("t18s34", "end-80-39", "across-40"):
            worlds.append(_index_world(k, placement))
    worlds.append({"name": "w5-dir-37-sectors",
                   "files": [{"name": "F%03d" % i, "size": 100} for i in range(1, 297)],
                   "directory_sectors": 37})
    worlds.append({"name": "w5-dir-cyclic", "files": _libs(10), "cyclic_directory": True})
    worlds.append({"name": "w5-read-fail-dir", "files": _libs(20), "read_fail": ["40/4"]})
    worlds.append({"name": "w5-read-fail-chain",
                   "files": [{"name": "BIG", "size": 5 * 254}],
                   "read_fail": [{"file": "BIG", "chunk": 2}]})
    for size in (38399, 38400, 38401):
        worlds.append({"name": "w6-size-%d" % size, "files": [{"name": "SIZE", "size": size}]})
    for variant in ("require", "load-lib", "load", "dir"):
        for k in (2, 3):
            worlds.append(_init_world(variant, k))
    worlds.append({"name": "w7-names-16-15",
                   "files": [{"name": "ABCDEFGHIJKLMNOP", "size": 100},
                             {"name": "ABCDEFGHIJKLMNO", "size": 100}],
                   "lookups": ["abcdefghijklmnopq"]})
    worlds.append({"name": "w7-names-far-80-39",
                   "files": [{"name": "LIB01", "size": 100},
                             {"name": "FAR", "size": 100, "track": 80, "sector": 39}]})
    return {w["name"]: w for w in worlds}


PRESETS = _presets()
# Specs that product media cannot hold; building them must fail loudly.
REFUSED = {
    "w7-names-17-fixture": ({"name": "w7-names-17-fixture",
                             "files": [{"name": "ABCDEFGHIJKLMNOPQ", "size": 10}]}, "BadName"),
    "w7-names-17-collision": ({"name": "w7-names-17-collision",
                               "files": [{"name": "abcdefghijklmnop", "size": 10},
                                         {"name": "ABCDEFGHIJKLMNOP", "size": 10}]},
                              "DuplicateName"),
}


# ---------------------------------------------------------------- selftest
class LispSuite:
    """Compile one stdlib suite once; run expressions against D81 worlds."""

    def __init__(self, suite_rel: str, exprs: list[str]):
        import bytecode_p0_stdlib as P

        self.P = P
        suite = P._read_suite(str(ROOT / suite_rel))
        suite["cases"] = [dict(name="hdw-%d" % i, expr=e, expect="nil")
                          for i, e in enumerate(exprs)]
        (heap, _names, _code, entry_flags, resident_flags, _bundle,
         directory, _cases, entry_names, _inliner) = P._compile_suite(suite)
        self.suite = suite
        self.heap = heap
        self.directory = directory
        self.macros = P._macro_symbol_objs(heap, entry_flags, resident_flags)
        self.entries = dict(zip(exprs, entry_names))
        self.abi, self.ledger = P._suite_abi(suite)

    def mutated(self, source_rel: str, old: str, new: str, defuns: tuple[str, ...]):
        heap = self.heap.clone()
        directory = dict(self.directory)
        text = (ROOT / source_rel).read_text()
        assert text.count(old) == 1, old
        text = text.replace(old, new)
        for form in self.P.C.parse_all(text):
            if form[0] != "defun" or form[1] not in defuns:
                continue
            name, code, helpers = self.P.C.compile_top_form_with_helpers(
                form, heap, strict_arity=(self.abi == 'dialect-v2'), abi_profile=self.abi)
            directory[heap.intern(name)] = code
            for helper, helper_code in helpers:
                directory[heap.intern(helper)] = helper_code
        return heap, directory

    def run(self, expr: str, spec: dict, heap=None, directory=None, vm_class=None, **extra):
        heap = (heap or self.heap).clone()
        directory = directory or self.directory
        kwargs = dict(world_kwargs(spec))
        kwargs.update(extra)
        vm = (vm_class or B.P0VM)(heap=heap, directory=directory, macro_symbols=self.macros,
                    max_steps=20_000_000, max_call_args=self.suite.get("max_call_args"),
                    abi_profile=self.abi, abi_ledger=self.ledger, **kwargs)
        try:
            value = vm.run(directory[heap.intern(self.entries[expr])], [])
        except B.VMError as exc:
            return {"error": exc.status, "message": str(exc)}, vm
        return heap.obj_to_text(value), vm


def _check(rows: list, name: str, ok: bool, **detail):
    rows.append(dict(check=name, ok=bool(ok), **detail))
    if not ok:
        raise AssertionError("%s: %r" % (name, detail))


def selftest() -> dict:
    rows: list[dict] = []

    # --- pure model geometry -------------------------------------------
    w20 = PRESETS["w3-libs-20"]
    vm = world_vm(w20)
    _check(rows, "dir-sector-count-20-files", vm.d81_directory_sector_count == 3,
           count=vm.d81_directory_sector_count)
    links = []
    for s in (3, 4, 5):
        vm._disk_read_sector_impl(40, s)
        links.append(tuple(vm.disk_buf[:2]))
    _check(rows, "dir-chain-links", links == [(40, 4), (40, 5), (0, 255)], links=links)
    vm._disk_read_sector_impl(40, 4)
    ninth = "".join(chr(c & 0x7F) for c in vm.disk_buf[5:21]).rstrip("\x20")
    _check(rows, "ninth-entry-in-40-4", ninth == "LIB09", entry=ninth)

    far = world_vm(PRESETS["w7-names-far-80-39"])
    _check(rows, "file-at-80-39", far.disk_files["FAR"]["sectors"] == [(80, 39)],
           sectors=far.disk_files["FAR"]["sectors"])

    for name, (spec, status) in REFUSED.items():
        try:
            world_vm(spec)
        except B.VMError as exc:
            _check(rows, name, exc.status == status, status=exc.status)
        else:
            _check(rows, name, False, status=None)
    alias = world_vm(PRESETS["w7-names-16-15"])
    _check(rows, "lookup-17-aliases-16", alias._disk_key("abcdefghijklmnopq") == "ABCDEFGHIJKLMNOP"
           and "ABCDEFGHIJKLMNO" in alias.disk_files, key=alias._disk_key("abcdefghijklmnopq"))

    # every preset materializes; the image serves the model's bytes
    images = {}
    for name, spec in PRESETS.items():
        image = world_image(spec)
        assert len(image) == D81_IMAGE_BYTES
        images[name] = hashlib.sha256(image).hexdigest()
    probe = world_vm(w20)
    probe._disk_read_sector_impl(40, 4)
    _check(rows, "image-matches-model",
           image_sector(world_image(w20), 40, 4) == bytes(probe.disk_buf))
    _check(rows, "presets-built", len(images) == len(PRESETS), worlds=len(images))

    # --- product Lisp walkers on the widened model ------------------------
    exprs = ['(load-lib "lib09")', '(load-lib "lib20")', '(load-lib "far")',
             '(load "far")', '(load-lib "big")', '(load-lib "size")',
             '(load-lib "f296")', '(load-lib "missing")',
             '(load-lib "abcdefghijklmnopq")', '(load-lib "abcdefghijklmnop")']
    L = LispSuite("tests/bytecode/stdlib/p0-stdlib-disklibs-subset.json", exprs)

    value, vm = L.run('(load-lib "lib09")', w20)
    start = world_vm(w20).disk_files["LIB09"]["sectors"][0]
    _check(rows, "ninth-file-found-by-load-lib", value == "t" and vm.disk_loaded_libs == [start],
           value=value, loaded=vm.disk_loaded_libs)
    value, vm = L.run('(load-lib "lib20")', w20)
    _check(rows, "twentieth-file-found", value == "t", value=value,
           dir_reads=[(r["track"], r["sector"]) for r in vm.disk_read_trace])

    value, vm = L.run('(load-lib "far")', PRESETS["w7-names-far-80-39"])
    _check(rows, "load-lib-at-80-39", value == "t" and vm.disk_loaded_libs == [(80, 39)],
           value=value, loaded=vm.disk_loaded_libs)
    value, vm = L.run('(load "far")', PRESETS["w7-names-far-80-39"])
    _check(rows, "load-at-80-39-streams-scratch",
           value == "t" and vm.disk_loaded == [(80, 39)]
           and vm.disk_buf[2:4] == list(vm.disk_loaded_sources[0]["bytes"][:2]),
           value=value, loaded=vm.disk_loaded)

    value, vm = L.run('(load-lib "abcdefghijklmnopq")', PRESETS["w7-names-16-15"])
    _check(rows, "product-17-char-lookup-rejected",
           value == "nil" and vm.disk_loaded_libs == [],
           value=value)
    value, vm = L.run('(load-lib "abcdefghijklmnop")', PRESETS["w7-names-16-15"])
    _check(rows, "product-16-char-lookup-accepted", value == "t" and
           vm.disk_loaded_libs == [world_vm(PRESETS["w7-names-16-15"])
                                   .disk_files["ABCDEFGHIJKLMNOP"]["sectors"][0]], value=value)
    heap, directory = L.mutated('lib/stdlib-load.lisp',
        '(if (= index 16)\n      (null codes)', '(if (= index 16)\n      t',
        ('%load-name-match-at',))
    value, vm = L.run('(load-lib "abcdefghijklmnopq")', PRESETS["w7-names-16-15"],
                      heap=heap, directory=directory)
    _check(rows, "old-17-char-alias-mutation-reproduced", value == "t" and
           len(vm.disk_loaded_libs) == 1, value=value)

    fail_chain = PRESETS["w5-read-fail-chain"]
    named = tuple(world_vm(fail_chain).disk_files["BIG"]["sectors"][2])
    value, vm = L.run('(load-lib "big")', fail_chain)
    report = vm.disk_fault_report()
    _check(rows, "injected-chain-fault-reported",
           value == "nil" and report == [{"source": "%disk-load-lib", "track": named[0],
                                          "sector": named[1], "reason": "injected-sector-fault"}],
           value=value, report=report)
    value, vm = L.run('(load-lib "lib20")', PRESETS["w5-read-fail-dir"])
    report = vm.disk_fault_report()
    _check(rows, "injected-directory-fault-reported",
           value == "nil" and report == [{"source": "%disk-read-sector", "track": 40,
                                          "sector": 4, "reason": "injected-sector-fault"}],
           value=value, report=report)
    value, vm = L.run('(load-lib "lib20")', PRESETS["w5-read-fail-dir"],
                      disk_failure_semantics="product-abort")
    _check(rows, "injected-directory-fault-product-abort",
           isinstance(value, dict) and value["error"] == "LoadOpen" and "40/4" in value["message"],
           value=value)

    got = {}
    for size in (38399, 38400, 38401):
        value, vm = L.run('(load-lib "size")', PRESETS["w6-size-%d" % size])
        got[size] = value
    _check(rows, "disk-file-max-edge", got == {38399: "t", 38400: "t", 38401: "nil"}, got=got)

    value, vm = L.run('(load-lib "f296")', PRESETS["w5-dir-37-sectors"])
    dir_reads = [r["sector"] for r in vm.disk_read_trace if r["track"] == 40]
    _check(rows, "dir-37-sectors-last-entry", value == "t" and dir_reads == list(range(3, 40)),
           value=value, reads=len(dir_reads))
    value, vm = L.run('(load-lib "missing")', PRESETS["w5-dir-cyclic"])
    _check(rows, "dir-cyclic-bounded-by-fuel", value == "nil" and vm.io_counters["disk_read"] == 64,
           value=value, reads=vm.io_counters["disk_read"])

    # --- two-sector L65INDEX: repaired vs directory-guard reader -----------
    R = LispSuite("tests/bytecode/libs/p0-stdlib-require-resolver.json", ["(%l65i-parse)"])
    spec = PRESETS["w4-index-2-end-80-39"]
    current, vm = R.run("(%l65i-parse)", spec)
    reads = [(r["track"], r["sector"]) for r in vm.disk_read_trace]
    heap, directory = R.mutated("lib/stdlib-require.lisp", "(if (%disk-file-link-valid-p",
                                "(if (%disk-directory-link-valid-p",
                                ("%l65i-next-byte",))
    old, vm_old = R.run("(%l65i-parse)", spec, heap=heap, directory=directory)
    old_reads = [(r["track"], r["sector"]) for r in vm_old.disk_read_trace]
    _check(rows, "index-2-sectors-at-80-38-current-reader-passes",
           current != "nil" and all("lib%02d" % i in current for i in range(5))
           and reads[-2:] == [(80, 38), (80, 39)], reads=reads)
    _check(rows, "index-2-sectors-directory-guard-reader-fails",
           old == "nil" and old_reads[-1] == (80, 38), result=old, reads=old_reads)
    for placement in ("t18s34", "across-40"):
        current, vm = R.run("(%l65i-parse)", PRESETS["w4-index-2-%s" % placement])
        old, _ = R.run("(%l65i-parse)", PRESETS["w4-index-2-%s" % placement],
                       heap=heap, directory=directory)
        _check(rows, "index-2-%s" % placement, current != "nil" and old == "nil",
               reads=[(r["track"], r["sector"]) for r in vm.disk_read_trace])
    for k in range(3, 8):
        current, vm = R.run("(%l65i-parse)", PRESETS["w4-index-%d-end-80-39" % k])
        _check(rows, "index-%d-sectors-end-80-39" % k,
               current != "nil" and (80, 39) in [(r["track"], r["sector"]) for r in vm.disk_read_trace],
               sectors=k)

    return {"status": "PASS", "checks": len(rows), "rows": rows,
            "presets": images, "refused": sorted(REFUSED)}


def emit(out_dir: Path, names: list[str]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in names:
        spec = PRESETS[name]
        vm = world_vm(spec)
        image = world_image(spec)
        (out_dir / (name + ".d81")).write_bytes(image)
        meta = {"name": name, "note": spec.get("note", ""), "files": file_table(vm),
                "directory_sectors": vm.d81_directory_sector_count,
                "read_fail_sectors": sorted(vm.disk_read_fail_sectors),
                "raw_sectors": sorted(vm.disk_raw_sectors),
                "image_sha256": hashlib.sha256(image).hexdigest()}
        (out_dir / (name + ".json")).write_text(json.dumps(meta, indent=2) + "\n")
        written.append(name)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--emit", metavar="DIR")
    ap.add_argument("--world", action="append")
    ap.add_argument("--receipt", metavar="PATH")
    ns = ap.parse_args(argv)
    if ns.list:
        for name, spec in PRESETS.items():
            print(name, spec.get("note", ""))
        return 0
    if ns.emit:
        names = ns.world or list(PRESETS)
        written = emit(Path(ns.emit), names)
        print("host-d81-worlds: emitted %d worlds to %s" % (len(written), ns.emit))
        return 0
    if ns.selftest:
        result = selftest()
        if ns.receipt:
            Path(ns.receipt).parent.mkdir(parents=True, exist_ok=True)
            Path(ns.receipt).write_text(json.dumps(result, indent=2, default=list) + "\n")
        print("host-d81-worlds selftest: PASS checks=%d presets=%d refused=%d"
              % (result["checks"], len(result["presets"]), len(result["refused"])))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
