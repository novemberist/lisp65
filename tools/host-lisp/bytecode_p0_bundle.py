#!/usr/bin/env python3
"""Host-side P0 code bundle and directory packer.

This is the T3 bridge between the source compiler and the native streaming
loader: compile small multi-defun programs, lay their code objects flat in the
extended-RAM address space, encode ABI directory entries, then reconstruct the
Host-VM directory from the flat blob as a roundtrip check.
"""

import argparse
from dataclasses import dataclass
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402


DEFAULT_BASE_ADDR = 0x050000
DIR_ENTRY_SIZE = 7


class BundleError(Exception):
    pass


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _default_paths():
    return sorted(glob.glob(os.path.join(_repo_root(), "tests", "bytecode", "programs", "*.json")))


def _u16le(n):
    return bytes((n & 0xFF, (n >> 8) & 0xFF))


def _read_u16le(data, off):
    return data[off] | (data[off + 1] << 8)


def _ext_addr_bytes(addr):
    if not 0 <= addr <= 0xFFFFFF:
        raise BundleError("extended address out of range: 0x%06x" % addr)
    return bytes((addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF))


def _read_ext_addr(data, off):
    return data[off] | (data[off + 1] << 8) | (data[off + 2] << 16)


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    name_obj: int
    ext_addr: int
    obj_len: int
    blob_offset: int

    def encode(self):
        if not 0 <= self.obj_len <= 0xFFFF:
            raise BundleError("code object too long for directory: %s" % self.name)
        return (
            _u16le(B.to_u16(self.name_obj))
            + _ext_addr_bytes(self.ext_addr)
            + _u16le(self.obj_len)
        )

    def manifest(self):
        return {
            "name": self.name,
            "name_obj": B.obj_hex(self.name_obj),
            "ext_addr": "0x%06x" % self.ext_addr,
            "offset": self.blob_offset,
            "length": self.obj_len,
        }


@dataclass(frozen=True)
class CodeBundle:
    base_addr: int
    blob: bytes
    entries: tuple

    def directory_bytes(self):
        return b"".join(entry.encode() for entry in self.entries)

    def manifest(self):
        return {
            "base_addr": "0x%06x" % self.base_addr,
            "code_bytes": len(self.blob),
            "directory_bytes": len(self.directory_bytes()),
            "objects": [entry.manifest() for entry in self.entries],
        }


def pack_code_objects(heap, names, code_by_name, base_addr=DEFAULT_BASE_ADDR):
    blob = bytearray()
    entries = []
    for name in names:
        if name not in code_by_name:
            raise BundleError("missing code object for %s" % name)
        encoded = code_by_name[name].encode()
        offset = len(blob)
        ext_addr = base_addr + offset
        if ext_addr + len(encoded) - 1 > 0xFFFFFF:
            raise BundleError("bundle crosses 24-bit address space")
        entry = DirectoryEntry(
            name=name,
            name_obj=heap.intern(name),
            ext_addr=ext_addr,
            obj_len=len(encoded),
            blob_offset=offset,
        )
        entries.append(entry)
        blob += encoded
    return CodeBundle(base_addr=base_addr, blob=bytes(blob), entries=tuple(entries))


def decode_directory(directory_bytes, names=None, base_addr=DEFAULT_BASE_ADDR):
    directory_bytes = bytes(directory_bytes)
    if len(directory_bytes) % DIR_ENTRY_SIZE != 0:
        raise BundleError("bad directory byte length: %d" % len(directory_bytes))
    count = len(directory_bytes) // DIR_ENTRY_SIZE
    if names is not None and len(names) != count:
        raise BundleError("directory name count mismatch")

    entries = []
    for idx in range(count):
        off = idx * DIR_ENTRY_SIZE
        name_obj = B.to_i16(_read_u16le(directory_bytes, off))
        ext_addr = _read_ext_addr(directory_bytes, off + 2)
        obj_len = _read_u16le(directory_bytes, off + 5)
        if ext_addr < base_addr:
            raise BundleError("directory entry before base address")
        name = names[idx] if names is not None else "#%d" % idx
        entries.append(
            DirectoryEntry(
                name=name,
                name_obj=name_obj,
                ext_addr=ext_addr,
                obj_len=obj_len,
                blob_offset=ext_addr - base_addr,
            )
        )
    return tuple(entries)


def load_bundle_directory(heap, bundle):
    directory = {}
    parsed = decode_directory(
        bundle.directory_bytes(),
        names=[entry.name for entry in bundle.entries],
        base_addr=bundle.base_addr,
    )
    if parsed != bundle.entries:
        raise BundleError("directory decode/encode mismatch")

    for entry in parsed:
        if heap.intern(entry.name) != entry.name_obj:
            raise BundleError("symbol obj mismatch for %s" % entry.name)
        start = entry.blob_offset
        end = start + entry.obj_len
        if start < 0 or end > len(bundle.blob):
            raise BundleError("directory slice outside bundle for %s" % entry.name)
        directory[entry.name_obj] = B.decode_code_object(bundle.blob[start:end])
    return directory


def _check_compiled_hex(program, names, code_by_name, path):
    expected_objects = program.get("code_objects")
    if expected_objects is None:
        return
    if set(expected_objects) != set(code_by_name):
        raise AssertionError(
            "%s (%s): code object names mismatch expected %r got %r"
            % (program["name"], path, sorted(expected_objects), sorted(code_by_name))
        )
    for name in names:
        got = B.hex_bytes(code_by_name[name].encode())
        expected = B.hex_bytes(B.parse_hex(expected_objects[name]))
        if got != expected:
            raise AssertionError(
                "%s/%s (%s): compiler hex mismatch\nexpected: %s\nactual:   %s"
                % (program["name"], name, path, expected, got)
            )


def check_bundle_program(path, root_symbols, program, base_addr=DEFAULT_BASE_ADDR):
    heap = C.prepare_heap(root_symbols + program.get("symbols", []))
    expected_compile_error = program.get("expect_compile_error")
    try:
        names, code_by_name = C.compile_program(
            program["source"],
            heap,
            strict_arity=bool(program.get("strict_arity", False)),
        )
    except Exception as exc:
        if expected_compile_error and expected_compile_error in str(exc):
            return {
                "name": program["name"],
                "objects": 0,
                "code_bytes": 0,
                "directory_bytes": 0,
                "steps": 0,
                "manifest": None,
            }
        raise
    if expected_compile_error:
        raise AssertionError(
            "%s (%s): expected compile error containing %r"
            % (program["name"], path, expected_compile_error)
        )
    _check_compiled_hex(program, names, code_by_name, path)

    bundle = pack_code_objects(heap, names, code_by_name, base_addr=base_addr)
    directory = load_bundle_directory(heap, bundle)

    expected_blob = b"".join(code_by_name[name].encode() for name in names)
    if bundle.blob != expected_blob:
        raise AssertionError("%s (%s): bundle blob order mismatch" % (program["name"], path))

    entry = program.get("entry")
    entry_obj = heap.intern(entry)
    if entry_obj not in directory:
        raise AssertionError("%s (%s): missing entry %r" % (program["name"], path, entry))

    args = [B.obj_from_json(heap, arg) for arg in program.get("args", [])]
    vm = B.P0VM(heap=heap, directory=directory)
    expected_vm_error = program.get("expect_vm_error")
    try:
        result = vm.run(directory[entry_obj], args)
    except B.VMError as exc:
        if expected_vm_error == exc.status:
            return {
                "name": program["name"],
                "objects": len(names),
                "code_bytes": len(bundle.blob),
                "directory_bytes": len(bundle.directory_bytes()),
                "steps": vm.steps,
                "manifest": bundle.manifest(),
            }
        raise
    if expected_vm_error:
        raise AssertionError(
            "%s (%s): expected VM error %r"
            % (program["name"], path, expected_vm_error)
        )
    got_text = heap.obj_to_text(result)
    if got_text != program["expect"]:
        raise AssertionError(
            "%s (%s): result mismatch expected %r got %r"
            % (program["name"], path, program["expect"], got_text)
        )
    if "expect_obj" in program:
        got_obj = B.obj_hex(result)
        if got_obj.lower() != program["expect_obj"].lower():
            raise AssertionError(
                "%s (%s): result obj mismatch expected %s got %s"
                % (program["name"], path, program["expect_obj"], got_obj)
            )

    return {
        "name": program["name"],
        "objects": len(names),
        "code_bytes": len(bundle.blob),
        "directory_bytes": len(bundle.directory_bytes()),
        "steps": vm.steps,
        "manifest": bundle.manifest(),
    }


def check_paths(paths, base_addr=DEFAULT_BASE_ADDR, verbose=False):
    ok = 0
    total_objects = 0
    total_code_bytes = 0
    total_directory_bytes = 0
    for path, data in C.load_vector_files(paths):
        root_symbols = data.get("symbols", [])
        for program in data.get("programs", []):
            info = check_bundle_program(path, root_symbols, program, base_addr=base_addr)
            ok += 1
            total_objects += info["objects"]
            total_code_bytes += info["code_bytes"]
            total_directory_bytes += info["directory_bytes"]
            if verbose:
                print(
                    "PASS %-28s objects=%d code=%d dir=%d steps=%d"
                    % (
                        info["name"],
                        info["objects"],
                        info["code_bytes"],
                        info["directory_bytes"],
                        info["steps"],
                    )
                )
    if ok == 0:
        raise AssertionError("no program vectors found")
    return {
        "programs": ok,
        "objects": total_objects,
        "code_bytes": total_code_bytes,
        "directory_bytes": total_directory_bytes,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="program-vector JSON files")
    ap.add_argument("--check", action="store_true", help="run bundle roundtrip checks")
    ap.add_argument("--base-addr", default="0x050000", help="flat extended-RAM base address")
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args(argv)

    if not ns.check:
        print("bytecode_p0_bundle.py requires --check", file=sys.stderr)
        return 2
    paths = ns.paths or _default_paths()
    if not paths:
        print("bytecode-p0-bundle-check: no program vectors found", file=sys.stderr)
        return 1
    try:
        base_addr = int(ns.base_addr, 0)
        info = check_paths(paths, base_addr=base_addr, verbose=ns.verbose)
    except Exception as e:
        print("bytecode-p0-bundle-check: FAIL: %s" % e, file=sys.stderr)
        return 1
    print(
        "bytecode-p0-bundle-check: PASS programs=%d objects=%d code_bytes=%d dir_bytes=%d"
        % (
            info["programs"],
            info["objects"],
            info["code_bytes"],
            info["directory_bytes"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
