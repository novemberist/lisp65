#!/usr/bin/env python3
"""Run separately appended Session definitions through the C2D-v6 host path.

This is a reusable, host-only integration runner.  Each definition is compiled
to a normal code object, converted to the legacy semantic manifest consumed by
the one C2I-v2 emitter, appended persistently through the C2D-v6 model, hot
materialized from the published C2D records, and only then executed by the
reference VM.

The runner deliberately does not use the historical REPL store/installer path.
It does not claim target timing, DMA, overlay, or hardware equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_bundle as PB  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_full_emission as F  # noqa: E402
import c2_lite_root_surrogate as R  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402


DEFAULT_FIXTURE = ROOT / "tests/equivalence/c2-product-session-cross-entry.json"
DEFAULT_OUT = ROOT / "build/equivalence/c2-product-session-host"
TARGET_OVERLAY_SOURCE = ROOT / "scripts/c2-equivalence-overlay-model.c"
TARGET_OVERLAY_FIXTURE = (
    ROOT / "tests/equivalence/c2-product-session-prim68-overlay.lisp")
FORMAT = "lisp65-c2-product-session-host-fixture-v1"
RESULT_FORMAT = "lisp65-c2-product-session-host-result-v1"
SYMI_BASE = 0x7000
BCODE_BASE = 0x6000


class SessionHostError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionHostError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        name = path.relative_to(ROOT).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "bytes": len(data), "sha256": sha_bytes(data)}


def u16(data: bytes | bytearray, at: int) -> int:
    require(0 <= at <= len(data) - 2, "truncated u16")
    return struct.unpack_from("<H", data, at)[0]


def p16(value: int) -> bytes:
    require(0 <= value <= 0xFFFF, "u16 overflow")
    return struct.pack("<H", value)


def mk_symi(index: int) -> int:
    require(0 <= index < 4096, "target symbol table exceeds SYMI domain")
    return ((SYMI_BASE + index) << 1) & 0xFFFF


def is_symi(value: int) -> bool:
    return value >= 0xE000 and not value & 1


def symi_index(value: int) -> int:
    require(is_symi(value), f"not a SYMI value: 0x{value:04x}")
    return (value >> 1) - SYMI_BASE


def mk_bcode(ordinal: int) -> int:
    require(0 <= ordinal < 4096, "directory ordinal exceeds BCODE domain")
    return ((BCODE_BASE + ordinal) << 1) & 0xFFFF


def is_bcode(value: int) -> bool:
    return 0xC000 <= value < 0xE000 and not value & 1


class TargetSymbols:
    """Canonical target-side interner using the product's MK_SYMI formula."""

    def __init__(self) -> None:
        self._names: list[str] = []
        self._values: dict[str, int] = {}
        self.intern("t")

    def intern(self, name: str) -> int:
        require(isinstance(name, str) and name, "empty target symbol")
        key = name.lower()
        if key not in self._values:
            value = mk_symi(len(self._names))
            self._names.append(key)
            self._values[key] = value
        return self._values[key]

    def name(self, value: int) -> str:
        index = symi_index(value)
        require(index < len(self._names), "SYMI index is not interned")
        return self._names[index]

    def rows(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "index": index, "raw": f"0x{mk_symi(index):04x}"}
            for index, name in enumerate(self._names)
        ]


class Trace:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call(
        self, caller: str, kind: str, target: str, argc: int,
        pc: int | None = None, resolved: bool = False,
    ) -> None:
        self.calls.append({
            "caller": caller,
            "kind": kind,
            "target": target,
            "argc": argc,
            "pc": pc,
            "resolved": resolved,
        })


def _string_records(image: F.Emitted) -> dict[int, bytes]:
    strings_offset = F.u16(image.metadata, 18)
    strings_bytes = F.u16(image.metadata, 20)
    return F.string_records(
        image.metadata[strings_offset:strings_offset + strings_bytes])


def _descriptor_name(image: F.Emitted, descriptor: F.Desc) -> str:
    records = _string_records(image)
    require(
        descriptor.arg1 in records
        and len(records[descriptor.arg1]) == descriptor.arg0,
        "symbol/string descriptor has no canonical C2I string",
    )
    return records[descriptor.arg1].decode("ascii").lower()


def _manifest_for_code(
    entry: str,
    code: B.CodeObject,
    heap: B.Heap,
    out: Path,
    *,
    export_flags: int = 0,
) -> tuple[Path, bytes]:
    """Build the semantic compiler manifest consumed by F.emit_image."""
    require(export_flags in (0, 1), "Session export flags are not function/macro")
    bundle = PB.pack_code_objects(heap, [entry], {entry: code}, base_addr=0)
    pool = STD.LiteralPool()
    lit_first, lit_count = pool.add_obj_list(heap, code.littab)
    require(
        len(pool.index) == len(pool.nodes)
        and sorted(pool.index) == list(range(len(pool.nodes))),
        "single-entry literal topology is not a complete permutation",
    )
    patches = [
        {
            "blob_offset": 7 + 2 * slot,
            "node": pool.index[lit_first + slot],
        }
        for slot in range(lit_count)
    ]
    blob = bytes(bundle.blob)
    out.mkdir(parents=True, exist_ok=True)
    blob_path = out / f"{entry}.code.bin"
    manifest_path = out / f"{entry}.manifest.json"
    blob_path.write_bytes(blob)
    manifest = {
        "format": "lisp65-c2-product-session-host-input-v1",
        "name": entry,
        "blob": blob_path.relative_to(ROOT).as_posix(),
        "blob_sha256": sha_bytes(blob),
        "code_bytes": len(blob),
        "entries": [{
            "name": entry,
            "kind": "macro" if export_flags else "function",
            "flags": export_flags,
            "code_flags": code.flags,
            "blob_offset": 0,
            "length": len(blob),
            "lit_first": lit_first,
            "lit_count": lit_count,
            "literals": [STD._obj_spec(heap, value) for value in code.littab],
        }],
        "exports": [entry],
        "late_bound_exports": [],
        "literal_nodes": pool.nodes,
        "literal_index": pool.index,
        "literal_patches": patches,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path, blob


def _seed_plane(geometry: dict[str, Any]) -> V6.V6Plane:
    required = {
        "generation", "images", "entries", "resolutions", "roots",
        "code_bytes", "immutable_images", "catalog_crc32", "build_id",
    }
    require(set(geometry) == required, "base geometry fields drift")
    plane = V6.V6Plane()
    plane.generation = int(geometry["generation"])
    plane.images = int(geometry["images"])
    plane.entries = int(geometry["entries"])
    plane.resolutions = int(geometry["resolutions"])
    plane.roots = int(geometry["roots"])
    plane.code_low = int(geometry["code_bytes"])
    plane.immutable_images = int(geometry["immutable_images"])
    plane.catalog_crc = int(geometry["catalog_crc32"])
    plane.build_id = int(geometry["build_id"])
    require(
        0 < plane.generation <= 0xFFFF
        and 0 <= plane.images < 64
        and 0 <= plane.entries < 2048
        and 0 <= plane.resolutions < 4096
        and 0 <= plane.roots < 1536
        and 0 <= plane.code_low < 65536,
        "base geometry is outside C2D-v6 bounds",
    )
    plane.publish_header()
    return plane


class ProductSessionHost:
    """Reusable compiler/emitter/append/materialize/execute integration seam."""

    def __init__(self, geometry: dict[str, Any], out: Path) -> None:
        self.out = out
        self.heap = B.Heap()
        self.symbols = TargetSymbols()
        self.plane = _seed_plane(geometry)
        self.ledger = json.loads(
            (ROOT / "config/bytecode-abi-ledger.json").read_text(
                encoding="utf-8"))
        self.directory: dict[int, B.CodeObject] = {}
        self.code_names: dict[int, str] = {}
        self.raw_to_host: dict[int, int] = {
            self.symbols.intern("t"): self.heap.t_obj,
        }
        self.ordinal_to_symbol: dict[int, int] = {}
        self.append_rows: list[dict[str, Any]] = []

    def _sync_symbol(self, name: str) -> tuple[int, int]:
        host = self.heap.intern(name.lower())
        raw = self.symbols.intern(name.lower())
        self.raw_to_host[raw] = host
        return raw, host

    def _resolve_direct(
        self, image: F.Emitted,
    ) -> Callable[[F.Desc, int, int], int]:
        def resolve(descriptor: F.Desc, ordinal: int, directory_base: int) -> int:
            del ordinal
            if descriptor.kind == F.K_NIL:
                return 0
            if descriptor.kind == F.K_TRUE:
                return self.symbols.intern("t")
            if descriptor.kind == F.K_FIXNUM:
                signed = (
                    descriptor.arg0 - 0x10000
                    if descriptor.arg0 & 0x8000 else descriptor.arg0
                )
                return ((signed & 0x7FFF) << 1 | 1) & 0xFFFF
            if descriptor.kind == F.K_ENTRY:
                return mk_bcode(directory_base + descriptor.arg0)
            if descriptor.kind in (F.K_EXPORT, F.K_SYMBOL):
                name = _descriptor_name(image, descriptor)
                raw, _host = self._sync_symbol(name)
                return raw
            if descriptor.kind == F.K_NATIVE:
                return ((descriptor.arg0 & 0x3FFF) << 1) | 1
            raise SessionHostError(
                f"descriptor kind {descriptor.kind} is not direct")
        return resolve

    def _resolution_raw(self, ordinal: int) -> int:
        require(
            0 <= ordinal < self.plane.resolutions,
            f"resolution ordinal outside active plane: {ordinal}",
        )
        raw = u16(
            self.plane.c2d, V6.C2D_RESOLUTIONS_OFFSET + 2 * ordinal)
        if raw and raw < 0x8000 and not raw & 1:
            root = R.root_ordinal(raw)
            require(root < self.plane.roots, "root surrogate outside active roots")
            raw = u16(self.plane.c2d, V6.C2D_ROOTS_OFFSET + 2 * root)
        return raw

    def _bind_image_objects(
        self, image: F.Emitted, resolution_base: int, entry_base: int,
    ) -> None:
        host_values: list[int] = []
        records = _string_records(image)
        for local, descriptor in enumerate(image.descriptors):
            raw = self._resolution_raw(resolution_base + local)
            if descriptor.kind == F.K_NIL:
                host = B.NIL
            elif descriptor.kind == F.K_TRUE:
                host = self.heap.t_obj
            elif descriptor.kind == F.K_FIXNUM:
                host = B.to_i16(raw)
            elif descriptor.kind in (F.K_SYMBOL, F.K_EXPORT):
                host = self.heap.intern(
                    records[descriptor.arg1].decode("ascii").lower())
                require(
                    raw == self.symbols.intern(self.heap.symbol_name(host)),
                    "C2D symbol resolution is not canonical intern identity",
                )
            elif descriptor.kind == F.K_STRING:
                host = self.heap.string_from_text(
                    records[descriptor.arg1].decode("utf-8"))
            elif descriptor.kind == F.K_PAIR:
                require(
                    descriptor.arg0 < len(host_values)
                    and descriptor.arg1 < len(host_values),
                    "pair descriptor is not topological",
                )
                host = self.heap.cons(
                    host_values[descriptor.arg0], host_values[descriptor.arg1])
            elif descriptor.kind == F.K_ENTRY:
                ordinal = entry_base + descriptor.arg0
                require(
                    ordinal in self.ordinal_to_symbol,
                    "entry descriptor precedes its directory identity",
                )
                host = self.ordinal_to_symbol[ordinal]
            elif descriptor.kind == F.K_NATIVE:
                host = B.to_i16(raw)
            else:
                raise SessionHostError(
                    f"unsupported descriptor kind: {descriptor.kind}")
            host_values.append(host)
            self.raw_to_host[raw] = host

    def _host_value(self, raw: int) -> int:
        if raw == 0:
            return B.NIL
        if raw & 1:
            return B.to_i16(raw)
        if raw in self.raw_to_host:
            return self.raw_to_host[raw]
        if is_symi(raw):
            host = self.heap.intern(self.symbols.name(raw))
            self.raw_to_host[raw] = host
            return host
        if is_bcode(raw):
            ordinal = (raw >> 1) - BCODE_BASE
            require(ordinal in self.ordinal_to_symbol,
                    "BCODE has no published host directory identity")
            return self.ordinal_to_symbol[ordinal]
        raise SessionHostError(f"unbound target object: 0x{raw:04x}")

    def snapshot_entry(self, ordinal: int) -> dict[str, Any]:
        """Materialize one published entry and expose both target and host views."""
        require(0 <= ordinal < self.plane.entries, "entry ordinal outside plane")
        at = V6.C2D_ENTRIES_OFFSET + ordinal * V6.C2D_ENTRY_BYTES
        row = bytes(self.plane.c2d[at:at + V6.C2D_ENTRY_BYTES])
        require(len(row) == V6.C2D_ENTRY_BYTES, "truncated C2D entry")
        image, literal_count = row[0], row[1]
        code_offset, code_length = u16(row, 2), u16(row, 4)
        resolution_base, generation = u16(row, 6), u16(row, 8)
        require(
            image < self.plane.images
            and generation == self.plane.generation
            and code_length > 0
            and code_offset + code_length <= len(self.plane.code)
            and resolution_base + literal_count <= self.plane.resolutions,
            f"entry {ordinal} fails C2D-v6 bounds/generation",
        )
        cold = bytes(self.plane.code[code_offset:code_offset + code_length])
        require(
            len(cold) >= 7
            and cold[0] == B.CO_MAGIC
            and cold[6] == literal_count
            and 7 + literal_count * 2 + u16(cold, 4) == len(cold),
            f"entry {ordinal} code-object geometry",
        )
        require(
            all(byte == 0 for byte in cold[7:7 + 2 * literal_count]),
            f"entry {ordinal} immutable literal slots are not zero",
        )
        raw_literals = [
            self._resolution_raw(resolution_base + index)
            for index in range(literal_count)
        ]
        patched = bytearray(cold)
        for index, raw in enumerate(raw_literals):
            patched[7 + 2 * index:9 + 2 * index] = p16(raw)
        code = B.CodeObject(
            cold[1], cold[2], cold[3],
            tuple(self._host_value(raw) for raw in raw_literals),
            cold[7 + literal_count * 2:],
        )
        return {
            "ordinal": ordinal,
            "image": image,
            "generation": generation,
            "code_offset": code_offset,
            "code_length": code_length,
            "resolution_base": resolution_base,
            "raw_literals": raw_literals,
            "raw_literals_hex": [f"0x{raw:04x}" for raw in raw_literals],
            "cold_sha256": sha_bytes(cold),
            "target_materialized_sha256": sha_bytes(bytes(patched)),
            "code": code,
        }

    def append_definition(self, source: str, expected_entry: str) -> dict[str, Any]:
        form = C.parse_one(source)
        require(
            isinstance(form, list) and len(form) >= 4 and form[0] == "defun",
            "Session host accepts one defun per append",
        )
        definition = str(form[1]).lower()
        require(definition == expected_entry.lower(), "fixture entry/source drift")
        name, code, helpers = C.compile_top_form_with_helpers(
            form, self.heap, strict_arity=True, abi_profile="dialect-v2")
        require(name == definition and not helpers,
                "one-entry Session fixture unexpectedly emitted helpers")
        return self.append_compiled_definition(
            source,
            expected_entry,
            code,
            compiler_authority="python-reference-compiler",
        )

    def append_compiled_definition(
        self,
        source: str,
        expected_entry: str,
        code: B.CodeObject,
        *,
        export_flags: int = 0,
        compiler_authority: str,
    ) -> dict[str, Any]:
        """Append one already-compiled function through the canonical C2 path.

        This is the reusable seam for device-carrier execution fixtures.  The
        caller supplies the detached CodeObject produced by the carrier; this
        method owns only the one-emitter, persistent-append and materialization
        stages.  It deliberately accepts no helper list: each call remains one
        source form, one image and one published entry for cutpoint attribution.
        """
        form = C.parse_one(source)
        require(
            isinstance(form, list)
            and len(form) >= 4
            and form[0] in ("defun", "defmacro"),
            "Session compiled append accepts one defun/defmacro",
        )
        definition = str(form[1]).lower()
        require(definition == expected_entry.lower(), "fixture entry/source drift")
        require(
            export_flags == (1 if form[0] == "defmacro" else 0),
            "Session compiled append export-kind drift",
        )
        require(
            isinstance(compiler_authority, str) and compiler_authority,
            "Session compiled append lacks its compiler authority",
        )
        raw_symbol, host_symbol = self._sync_symbol(definition)
        manifest_path, compiler_blob = _manifest_for_code(
            definition,
            code,
            self.heap,
            self.out / definition,
            export_flags=export_flags,
        )
        image = F.emit_image(
            f"session-{definition}", f"s-{definition}", manifest_path)
        before = {
            "images": self.plane.images,
            "entries": self.plane.entries,
            "resolutions": self.plane.resolutions,
            "roots": self.plane.roots,
            "code_bytes": self.plane.code_low,
        }
        entry_base = self.plane.entries
        resolution_base = self.plane.resolutions
        appended = V6.append_image(
            self.plane, image, transient=False,
            direct_resolver=self._resolve_direct(image))
        require(
            appended["entries"] == 1
            and appended["handles"] == [entry_base],
            "persistent append did not publish one canonical handle",
        )
        self.ordinal_to_symbol[entry_base] = host_symbol
        self.raw_to_host[mk_bcode(entry_base)] = host_symbol
        self._bind_image_objects(image, resolution_base, entry_base)
        materialized = self.snapshot_entry(entry_base)
        self.directory[host_symbol] = materialized["code"]
        self.code_names[id(materialized["code"])] = definition
        after = {
            "images": self.plane.images,
            "entries": self.plane.entries,
            "resolutions": self.plane.resolutions,
            "roots": self.plane.roots,
            "code_bytes": self.plane.code_low,
        }
        row = {
            "entry": definition,
            "source": source,
            "source_form_kind": form[0],
            "export_flags": export_flags,
            "compiler_authority": compiler_authority,
            "target_symbol": f"0x{raw_symbol:04x}",
            "target_symbol_index": symi_index(raw_symbol),
            "handle": entry_base,
            "image_slot": before["images"],
            "before": before,
            "after": after,
            "compiler_code": {
                "bytes": len(compiler_blob),
                "sha256": sha_bytes(compiler_blob),
            },
            "manifest": bind(manifest_path),
            "c2i_code": {
                "bytes": len(image.code),
                "sha256": sha_bytes(image.code),
            },
            "c2i_metadata": {
                "bytes": len(image.metadata),
                "sha256": sha_bytes(image.metadata),
            },
            "materialized": {
                key: value for key, value in materialized.items()
                if key != "code"
            },
        }
        self.append_rows.append(row)
        return row

    def assert_symbol_binding(
        self, entry: str, literal_index: int, symbol: str,
    ) -> dict[str, Any]:
        host_entry = self.heap.intern(entry.lower())
        require(host_entry in self.directory, f"entry is not published: {entry}")
        ordinal = next(
            (row["handle"] for row in self.append_rows
             if row["entry"] == entry.lower()),
            -1,
        )
        require(ordinal >= 0, f"entry has no append receipt: {entry}")
        snap = self.snapshot_entry(ordinal)
        require(
            0 <= literal_index < len(snap["raw_literals"]),
            "binding literal index outside materialized entry",
        )
        raw = snap["raw_literals"][literal_index]
        expected = self.symbols.intern(symbol.lower())
        host_expected = self.heap.intern(symbol.lower())
        require(is_symi(raw), "bound literal is not in the SYMI domain")
        require(raw == expected, "bound literal is not canonical intern identity")
        require(
            snap["code"].littab[literal_index] == host_expected,
            "host VM view differs from target SYMI identity",
        )
        return {
            "entry": entry.lower(),
            "literal_index": literal_index,
            "symbol": symbol.lower(),
            "raw": f"0x{raw:04x}",
            "symbol_index": symi_index(raw),
            "c2d_resolution_ordinal":
                snap["resolution_base"] + literal_index,
            "identity": "materialized literal == canonical intern(symbol)",
        }

    def execute(self, entry: str, args: list[Any]) -> dict[str, Any]:
        symbol = self.heap.intern(entry.lower())
        require(symbol in self.directory, f"invoke entry is not published: {entry}")
        trace = Trace()
        vm = B.P0VM(
            heap=self.heap,
            directory=self.directory,
            trace=trace,
            code_names=self.code_names,
            abi_profile="dialect-v2",
            abi_ledger=self.ledger,
        )
        host_args = [B.obj_from_json(self.heap, value) for value in args]
        result = vm.run(self.directory[symbol], host_args)
        return {
            "entry": entry.lower(),
            "result_obj": B.obj_hex(result),
            "result_text": self.heap.obj_to_text(result),
            "steps": vm.steps,
            "calls": trace.calls,
        }


def source_closure_gate() -> dict[str, Any]:
    append_source = (
        inspect.getsource(ProductSessionHost.append_definition)
        + inspect.getsource(ProductSessionHost.append_compiled_definition)
    )
    manifest_source = inspect.getsource(_manifest_for_code)
    runtime = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    checks = {
        "compiler_manifest_is_emitter_input":
            "_manifest_for_code(" in append_source,
        "one_c2i_v2_emitter":
            "F.emit_image(" in append_source,
        "persistent_c2d_v6_append":
            "V6.append_image(" in append_source
            and "transient=False" in append_source,
        "hot_materialization_after_append":
            append_source.index("V6.append_image(")
            < append_source.index("self.snapshot_entry("),
        "no_historical_repl_store":
            "crepl_" not in append_source + manifest_source,
        "no_legacy_installer":
            "compile_run_top_form" not in append_source + manifest_source
            and "vm_dir_add" not in append_source + manifest_source,
        "product_installer_uses_session_emitter":
            "c2_session_emit_add(fnlist," in runtime,
        "product_installer_uses_staged_append":
            "c2_product_append_staged" in runtime,
    }
    require(all(checks.values()), "Session-host source closure drift")
    return checks


def target_overlay_reload_gate(out: Path) -> dict[str, Any]:
    """Run the real C VM buffer takeover/reload with only DMA modeled."""
    target = out / "c-target"
    target.mkdir(parents=True, exist_ok=True)
    binary = target / "prim68-buffer-reload"
    command = [
        os.environ.get("HOSTCC", "cc"),
        "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-DLISP65_COMPILE_REPL", "-DLISP65_VM",
        "-DLISP65_VM_GLOBAL_PRIMS", "-DLISP65_EVAL_PRIMS",
        "-DLISP65_EVAL_CONTROL_SF", "-DLISP65_VM_APPLY_OPFN",
        "-DLISP65_MACROEXPAND_PRIM", "-DLISP65_DIALECT_V2",
        "-DLISP65_STRING_ARENA", "-DLISP65_V2_NATIVE_CAPABILITIES",
        "-DLISP65_DIALECT_FAMILY_HARNESS", "-DLISP65_NUMERIC_ERRORS",
        "-DLISP65_FIRST_CLASS_BUFFER", "-DLISP65_RUNTIME_OVERLAY",
        "-DLISP65_INTERN_SESSION_SERVICE",
        "-DLISP65_INTERN_SERVICE_SLOT=51",
        "-DLISP65_EQUIVALENCE_OVERLAY_OBSERVER",
        "-DHEAP_CELLS=8192", "-DGC_ROOTS=1024", "-DMAX_SYM=512",
        "-DNAMEPOOL=8192", "-DVM_DIR_MAX=128", "-DIO_BUF_MAX=16",
        "-Isrc",
        "scripts/equivalence-main.c",
        "scripts/c2-equivalence-overlay-model.c",
        "src/intern_service_overlay.c",
        "src/eval.c", "src/compile.c", "src/compile_repl.c", "src/vm.c",
        "src/mem.c", "src/symbol.c", "src/reader.c", "src/printer.c",
        "src/io.c", "src/interrupt.c", "src/screen.c",
        "-o", str(binary),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    environment = dict(os.environ)
    environment["ASAN_OPTIONS"] = "detect_leaks=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1"
    executed = subprocess.run(
        [str(binary), "vm", str(TARGET_OVERLAY_FIXTURE)],
        cwd=ROOT, env=environment, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    expected = [
        "(defun %is (n) (if (> n 0) "
        "(progn (intern \"abc\") (%is (- n 1))) t)) => %is",
        "(%is 3) => t",
        "c2-prim68-buffer-reload: PASS calls=3 copies=3 "
        "prefix-reloads=3 header-reloads=3 literal-checks=3",
    ]
    actual = executed.stdout.strip().splitlines()
    require(actual == expected, "target C buffer/reload fixture output drift")
    require(not executed.stderr, "target C buffer/reload fixture wrote stderr")
    vm_source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    case = vm_source[
        vm_source.index("case 68:"):
        vm_source.index("#endif", vm_source.index("case 68:"))
    ]
    facade = vm_source[
        vm_source.index("static LISP65_RESIDENT_ISLAND_FN obj vm_buffer_call("):
        vm_source.index("\n}\n\n#endif", vm_source.index(
            "static LISP65_RESIDENT_ISLAND_FN obj vm_buffer_call(")) + 2
    ]
    callprim = vm_source[
        vm_source.index("case OP_CALLPRIM:"):
        vm_source.index("case OP_UPVAL:", vm_source.index("case OP_CALLPRIM:"))
    ]
    require(
        "return vm_buffer_call(pid, a, n);" in case
        and facade.index("vm_buf_bank = 0xFFu;")
            < facade.index("context->args = a;")
        and facade.index("vm_buf_off = 0xFFFFu;")
            < facade.index("context->args = a;")
        and "BUF_ENSURE_MINE(pcur);" in callprim,
        "target C fixture no longer traverses the product takeover/reload seam",
    )
    return {
        "status": "passed-real-c-vm-modeled-physical-transport",
        "prim68_calls": 3,
        "modeled_bank3_to_c356_copies": 3,
        "owner_invalidations": 3,
        "prefix_reloads": 3,
        "header_reloads": 3,
        "recursive_literal_identity_checks": 3,
        "result": "t",
        "asan": "passed",
        "ubsan": "passed",
        "executed_product_sources": [
            "src/vm.c",
            "src/intern_service_overlay.c",
        ],
        "modeled_boundary": (
            "physical Bank-3 record load to $C356 only; checked memcpy"),
        "binary": bind(binary),
        "fixture": bind(TARGET_OVERLAY_FIXTURE),
        "model": bind(TARGET_OVERLAY_SOURCE),
        "stdout": actual,
    }


def _expect_reject(label: str, operation: Callable[[], None]) -> str:
    try:
        operation()
    except SessionHostError:
        return label
    raise SessionHostError(f"negative fixture accepted: {label}")


def mutation_gate(
    host: ProductSessionHost, binding: dict[str, Any],
) -> list[str]:
    entry = binding["entry"]
    literal_index = int(binding["literal_index"])
    symbol = binding["symbol"]
    ordinal = next(
        row["handle"] for row in host.append_rows if row["entry"] == entry)
    snap = host.snapshot_entry(ordinal)
    at = (
        V6.C2D_RESOLUTIONS_OFFSET
        + 2 * (snap["resolution_base"] + literal_index)
    )
    original_resolution = bytes(host.plane.c2d[at:at + 2])
    entry_at = V6.C2D_ENTRIES_OFFSET + ordinal * V6.C2D_ENTRY_BYTES
    original_entry = bytes(
        host.plane.c2d[entry_at:entry_at + V6.C2D_ENTRY_BYTES])
    code_at = snap["code_offset"] + 7 + 2 * literal_index
    original_code = bytes(host.plane.code[code_at:code_at + 2])
    labels: list[str] = []

    def assert_binding() -> None:
        host.assert_symbol_binding(entry, literal_index, symbol)

    def mutate_resolution(raw: int) -> Callable[[], None]:
        def operation() -> None:
            host.plane.c2d[at:at + 2] = p16(raw)
            try:
                assert_binding()
            finally:
                host.plane.c2d[at:at + 2] = original_resolution
        return operation

    labels.append(_expect_reject(
        "different-symi",
        mutate_resolution(host.symbols.intern(entry + "-mutation"))))
    labels.append(_expect_reject("fixnum", mutate_resolution(3)))
    labels.append(_expect_reject(
        "odd-damaged-symi",
        mutate_resolution(host.symbols.intern(symbol) | 1)))

    def wrong_generation() -> None:
        row = bytearray(original_entry)
        row[8:10] = p16((host.plane.generation + 1) & 0xFFFF)
        host.plane.c2d[entry_at:entry_at + V6.C2D_ENTRY_BYTES] = row
        try:
            assert_binding()
        finally:
            host.plane.c2d[entry_at:entry_at + V6.C2D_ENTRY_BYTES] = original_entry

    labels.append(_expect_reject("entry-generation", wrong_generation))

    def nonzero_cold_literal() -> None:
        host.plane.code[code_at:code_at + 2] = p16(
            host.symbols.intern(symbol))
        try:
            assert_binding()
        finally:
            host.plane.code[code_at:code_at + 2] = original_code

    labels.append(_expect_reject(
        "immutable-code-literal-not-zero", nonzero_cold_literal))

    def coalesced_image() -> None:
        row = bytearray(original_entry)
        expected_image = next(
            item["image_slot"] for item in host.append_rows
            if item["entry"] == entry)
        row[0] = (expected_image - 1) & 0xFF
        host.plane.c2d[entry_at:entry_at + V6.C2D_ENTRY_BYTES] = row
        try:
            require(
                host.snapshot_entry(ordinal)["image"] == expected_image,
                "entry no longer belongs to its separate Session append",
            )
        finally:
            host.plane.c2d[entry_at:entry_at + V6.C2D_ENTRY_BYTES] = original_entry

    labels.append(_expect_reject("coalesced-session-image", coalesced_image))
    return labels


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(
        isinstance(value, dict) and value.get("format") == FORMAT,
        "unexpected Session-host fixture format",
    )
    require(
        value.get("profile") == "dialect-v2"
        and isinstance(value.get("base_geometry"), dict)
        and isinstance(value.get("cases"), list)
        and value["cases"],
        "Session-host fixture is incomplete",
    )
    return value


def run(fixture_path: Path, out: Path) -> dict[str, Any]:
    fixture = load_fixture(fixture_path)
    rows: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        host = ProductSessionHost(fixture["base_geometry"], out / case["name"])
        appends = [
            host.append_definition(row["source"], row["entry"])
            for row in case["definitions"]
        ]
        require(
            len(appends) == len(case["definitions"])
            and len({row["image_slot"] for row in appends}) == len(appends),
            "definitions did not traverse separate Session appends",
        )
        bindings = [
            host.assert_symbol_binding(
                row["entry"], int(row["literal_index"]), row["symbol"])
            for row in case["bindings"]
        ]
        invoke = case["invoke"]
        execution = host.execute(invoke["entry"], invoke.get("args", []))
        expected = case["expect"]
        if "fixnum" in expected:
            require(
                execution["result_text"] == str(expected["fixnum"]),
                f"{case['name']}: result mismatch",
            )
        elif "symbol" in expected:
            require(
                execution["result_text"] == expected["symbol"].lower(),
                f"{case['name']}: symbol result mismatch",
            )
        else:
            raise SessionHostError(
                f"{case['name']}: unsupported expected result")
        for expected_call in expected.get("calls", []):
            actual = sum(
                call["kind"] == expected_call["kind"]
                and call["target"] == expected_call["target"].lower()
                and call["resolved"]
                for call in execution["calls"]
            )
            require(
                actual == int(expected_call["count"]),
                f"{case['name']}: expected {expected_call['count']} "
                f"{expected_call['kind']} calls to "
                f"{expected_call['target']}, got {actual}",
            )
        require(
            any(
                call["target"] == bindings[0]["symbol"] and call["resolved"]
                for call in execution["calls"]
            ),
            f"{case['name']}: VM never resolved the cross-entry call",
        )
        mutations = mutation_gate(host, case["bindings"][0])
        rows.append({
            "name": case["name"],
            "status": "passed",
            "appends": appends,
            "bindings": bindings,
            "execution": execution,
            "mutations": mutations,
            "target_symbols": host.symbols.rows(),
            "plane_after": {
                "images": host.plane.images,
                "entries": host.plane.entries,
                "resolutions": host.plane.resolutions,
                "roots": host.plane.roots,
                "code_bytes": host.plane.code_low,
                "generation": host.plane.generation,
            },
        })

    closure = source_closure_gate()
    target_overlay = target_overlay_reload_gate(out)
    result = {
        "format": RESULT_FORMAT,
        "recorded_on": "2026-07-28",
        "status": "passed",
        "cases": rows,
        "summary": {
            "cases": len(rows),
            "separate_session_appends": sum(
                len(row["appends"]) for row in rows),
            "exact_symi_bindings": sum(
                len(row["bindings"]) for row in rows),
            "mutations_rejected": sum(
                len(row["mutations"]) for row in rows),
            "executions": len(rows),
            "target_c_buffer_reload_cases": 1,
            "target_c_prim68_calls": target_overlay["prim68_calls"],
        },
        "source_closure": closure,
        "target_c_buffer_reload": target_overlay,
        "base_geometry": fixture["base_geometry"],
        "base_geometry_source": fixture.get("base_geometry_source"),
        "claim": (
            "The canonical host model can execute both a cross-entry g/h "
            "Session append and the real recursive %is/Prim-68 reproducer "
            "through published C2D-v6 records. Each symbolic callee literal "
            "is bound to the exact target-side canonical intern identity; "
            "%is completes three resolved calls to intern and three resolved "
            "self-tailcalls and returns t. A companion C-target lane executes "
            "the real vm_buffer_call, vm_codebuf takeover, intern service, and "
            "BUF_ENSURE_MINE reload three times, modeling only the physical "
            "Bank-3-to-$C356 copy, and also returns t."
        ),
        "claim_limit": (
            "Host integration evidence only. It executes the canonical "
            "compiler/emitter/C2D-v6 models, not the linked 45GS02 product; "
            "the isolated host interner proves identity equality but does not "
            "claim Link-73's numeric runtime symbol ordinal; "
            "the two host lanes therefore exclude shared logic plus the C "
            "vm_codebuf takeover/reload mechanism, but do not exclude the "
            "target-only physical record transport, family/generation cells, "
            "DMA, IRQ, CPU semantics, or ABI faults."
        ),
        "infrastructure": {
            "reusable_api": [
                "ProductSessionHost.append_definition",
                "ProductSessionHost.snapshot_entry",
                "ProductSessionHost.assert_symbol_binding",
                "ProductSessionHost.execute",
            ],
            "two_timepoint_ready": (
                "snapshot_entry may be called before and after an arbitrary "
                "host-modeled service action without rebuilding the image"
            ),
            "required_before_future_freight": True,
        },
        "scope": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "xemu_runs": 0,
            "promotable": False,
        },
        "authority": {
            "fixture": bind(fixture_path),
            "runner": bind(Path(__file__)),
            "compiler": bind(ROOT / "tools/host-lisp/bytecode_p0_compiler.py"),
            "vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
            "c2i_emitter": bind(ROOT / "tools/host-lisp/c2_full_emission.py"),
            "c2d_v6_model": bind(
                ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"),
            "product_emitter": bind(ROOT / "src/c2_session_emitter.c"),
            "product_append_runtime": bind(ROOT / "src/c2_product_runtime.c"),
            "object_encoding": bind(ROOT / "src/obj.h"),
            "abi_ledger": bind(ROOT / "config/bytecode-abi-ledger.json"),
            "target_overlay_model": bind(TARGET_OVERLAY_SOURCE),
            "target_overlay_fixture": bind(TARGET_OVERLAY_FIXTURE),
            "target_vm_harness": bind(ROOT / "scripts/equivalence-main.c"),
            "target_intern_service": bind(ROOT / "src/intern_service_overlay.c"),
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.fixture.resolve(), args.out.resolve())
        args.out.mkdir(parents=True, exist_ok=True)
        result_path = args.out / "result.json"
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.receipt is not None:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, SessionHostError, F.FullError) as error:
        print(f"c2-product-session-host: FIRST RED: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print(
        "c2-product-session-host: PASS "
        f"cases={summary['cases']} "
        f"appends={summary['separate_session_appends']} "
        f"symi={summary['exact_symi_bindings']} "
        f"mutations={summary['mutations_rejected']} "
        f"c-buffer-reloads={summary['target_c_prim68_calls']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
