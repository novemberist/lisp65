#!/usr/bin/env python3
"""Attribute the Link-75 require/defstruct First Red without target hardware.

The tool executes the compiler bytecode that is actually packed in the Link-75
LCC carrier.  It compiles every top-level form of stdlib-places and defstruct,
then sends those detached CodeObjects through the canonical C2I-v2 emitter and
the persistent C2D-v6 append model in two independent lanes:

* one source form per image, so the first failing form is an exact cutpoint;
* one image per library, matching require's two-image publication shape.

It also executes the new %lcc-v2-prim4 -> %lcc-v2-prim5 tail boundary directly.
No product source, product link, emulator or hardware is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_bundle as PB  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_bound_artifact_source_parity as BOUND  # noqa: E402
import c2_full_emission as F  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_session_host as SESSION  # noqa: E402
from stdlib_source_budget import strip_comments, top_level_forms  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
CARRIER = BASE / "compiler-carrier/lcc.manifest.json"
TIER = BASE / "compiler-carrier/compiler-tier/tier-generation.json"
STATIC_C2D = (
    BASE / "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin")
STATIC_CODE = (
    BASE / "static-plane/narrow-static/v6-semantics/bank2-static-code.bin")
HARDWARE_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-require-hardware-first-red.json")
OUT = BASE / "require-defstruct-host-attribution"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-require-defstruct-host-attribution.json")
FORMAT = "lisp65-c2-link75-require-defstruct-host-attribution-v1"

LIBRARIES = (
    {
        "name": "place",
        "source": ROOT / "lib/stdlib-places.lisp",
        "old_manifest":
            ROOT / "build/post-promotion/defstruct-v1/foundations/"
            "place.manifest.json",
    },
    {
        "name": "defstruct",
        "source": ROOT / "lib/defstruct.lisp",
        "old_manifest":
            ROOT / "build/post-promotion/defstruct-v1/foundations/"
            "defstruct.manifest.json",
    },
)


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input is absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def proper_list(heap: B.Heap, value: int, label: str) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    while value != B.NIL:
        require(heap.consp(value), f"{label} is not a proper list")
        raw = B.to_u16(value)
        require(raw not in seen, f"{label} is cyclic")
        seen.add(raw)
        result.append(heap.car(value))
        value = heap.cdr(value)
    return result


def fixnum(heap: B.Heap, value: int, label: str) -> int:
    del heap
    require(B.is_fix(value), f"{label} is not a fixnum")
    return B.fixval(value)


class CallTrace:
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


class BoundCarrierCompiler:
    """Execute the exact packed Link-75 compiler carrier."""

    def __init__(self) -> None:
        carrier, suite, source_binding = BOUND.source_binding_gate(
            CARRIER, TIER)
        self.manifest = carrier
        self.suite = suite
        self.source_binding = source_binding
        self.blob = (ROOT / carrier["blob"]).read_bytes()
        require(
            sha_bytes(self.blob) == carrier["blob_sha256"],
            "carrier blob hash drift",
        )
        patch_by_offset = {
            int(row["blob_offset"]): int(row["node"])
            for row in carrier["literal_patches"]
        }
        self.heap = C.prepare_heap([])
        self.directory: dict[int, B.CodeObject] = {}
        self.macro_symbols: set[int] = set()
        self.code_names: dict[int, str] = {}
        for entry in carrier["entries"]:
            name = entry["name"]
            code = STD._patched_code_from_manifest_entry(
                self.heap, carrier, self.blob, entry, patch_by_offset)
            symbol = self.heap.intern(name)
            require(symbol not in self.directory,
                    f"duplicate carrier entry: {name}")
            self.directory[symbol] = code
            self.code_names[id(code)] = name
            if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
                self.macro_symbols.add(symbol)
        resident_names, resident_code, resident_flags = (
            STD._compile_resident_code(suite, self.heap))
        resident_overrides = set(
            STD._as_list(suite.get("resident_overrides")))
        STD._add_code_to_directory(
            self.heap,
            self.directory,
            [name for name in resident_names
             if name not in resident_overrides],
            resident_code,
            "Link-75 carrier resident suite",
        )
        self.macro_symbols.update(
            STD._macro_symbol_objs(self.heap, resident_flags))
        self.code_names.update(
            {id(code): name for name, code in resident_code.items()})
        self.ledger = load(ROOT / "config/bytecode-abi-ledger.json")
        self.compiler_symbol = self.heap.intern("%c2-compile-form")
        require(
            self.compiler_symbol in self.directory,
            "Link-75 carrier lacks %c2-compile-form",
        )

    def vm(self, trace: CallTrace | None = None) -> B.P0VM:
        return B.P0VM(
            heap=self.heap,
            directory=self.directory,
            macro_symbols=self.macro_symbols,
            max_steps=5_000_000,
            max_call_args=self.suite.get("max_call_args"),
            trace=trace,
            code_names=self.code_names,
            abi_profile="dialect-v2",
            abi_ledger=self.ledger,
        )

    def decode_code(self, value: int, label: str) -> B.CodeObject:
        fields = proper_list(self.heap, value, label)
        require(len(fields) == 5, f"{label} is not a five-field CodeObject")
        nargs = fixnum(self.heap, fields[0], label + ".nargs")
        nlocals = fixnum(self.heap, fields[1], label + ".nlocals")
        flags = fixnum(self.heap, fields[2], label + ".flags")
        literals = tuple(proper_list(
            self.heap, fields[3], label + ".literals"))
        payload_values = proper_list(
            self.heap, fields[4], label + ".payload")
        payload = bytes(
            fixnum(self.heap, item, label + ".payload-byte")
            for item in payload_values
        )
        require(
            all(0 <= item <= 255 for item in payload),
            f"{label} payload byte outside u8",
        )
        code = B.CodeObject(nargs, nlocals, flags, literals, payload)
        require(
            len(code.encode()) <= 255,
            f"{label} exceeds the target CodeObject ceiling",
        )
        return code

    def compile(self, source: str) -> dict[str, Any]:
        parsed = C.parse_one(source)
        require(
            isinstance(parsed, list)
            and len(parsed) >= 4
            and parsed[0] in ("defun", "defmacro")
            and isinstance(parsed[1], str),
            "library source form is not defun/defmacro",
        )
        trace = CallTrace()
        vm = self.vm(trace)
        source_obj = vm._compiler_form_obj(parsed)
        fnlist = vm.run(
            self.directory[self.compiler_symbol], [source_obj])
        values = proper_list(self.heap, fnlist, parsed[1] + ".fnlist")
        require(
            len(values) == 1,
            f"{parsed[1]} emitted {len(values)} objects; "
            "one-form cutpoint needs one object",
        )
        code = self.decode_code(values[0], parsed[1])
        tail_rows = [
            row for row in trace.calls
            if row["caller"] == "%lcc-v2-prim4"
            and row["target"] == "%lcc-v2-prim5"
        ]
        return {
            "name": parsed[1].lower(),
            "kind": parsed[0],
            "flags": 1 if parsed[0] == "defmacro" else 0,
            "code": code,
            "steps": vm.steps,
            "tail_boundary_calls": tail_rows,
            "summary": code_summary(self.heap, code),
        }


def code_summary(heap: B.Heap, code: B.CodeObject) -> dict[str, Any]:
    value = {
        "nargs": code.nargs,
        "nlocals": code.nlocals,
        "flags": code.flags,
        "literals": [STD._obj_spec(heap, item) for item in code.littab],
        "payload_hex": bytes(code.payload).hex(),
        "encoded_bytes": len(code.encode()),
        "encoded_sha256": sha_bytes(code.encode()),
    }
    value["semantic_sha256"] = sha_bytes(canonical(value))
    return value


def initial_geometry() -> dict[str, Any]:
    data = STATIC_C2D.read_bytes()
    code = STATIC_CODE.read_bytes()
    require(
        len(data) == V6.C2D_TOTAL_BYTES
        and data[:4] == b"C2D\0"
        and data[4] == V6.C2D_VERSION
        and len(code) == 40284,
        "Link-75 static C2D/Bank-2 geometry drift",
    )
    u16 = lambda at: struct.unpack_from("<H", data, at)[0]
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]
    geometry = {
        "generation": u16(10),
        "images": u16(12),
        "entries": u16(16),
        "resolutions": u16(20),
        "roots": u16(24),
        "code_bytes": len(code),
        "immutable_images": u16(38),
        "catalog_crc32": u32(40),
        "build_id": u32(44),
    }
    require(
        geometry == {
            "generation": 1,
            "images": 6,
            "entries": 677,
            "resolutions": 2685,
            "roots": 340,
            "code_bytes": 40284,
            "immutable_images": 6,
            "catalog_crc32": 0xC9E5A0C5,
            "build_id": 0x911D21FE,
        },
        "Link-75 base geometry no longer matches the bound First Red",
    )
    return geometry


def attach_heap(
    host: SESSION.ProductSessionHost, heap: B.Heap,
) -> None:
    """Use carrier-owned literals without lossy cross-heap serialization."""
    host.heap = heap
    host.raw_to_host = {
        host.symbols.intern("t"): heap.t_obj,
    }


def source_rows(path: Path) -> list[dict[str, Any]]:
    texts = top_level_forms(strip_comments(path.read_text(encoding="utf-8")))
    rows = []
    for index, text in enumerate(texts):
        parsed = C.parse_one(text)
        require(
            isinstance(parsed, list)
            and len(parsed) >= 4
            and parsed[0] in ("defun", "defmacro")
            and isinstance(parsed[1], str),
            f"{path.name} form {index} is not a named definition",
        )
        rows.append({
            "index": index,
            "source": text,
            "name": parsed[1].lower(),
            "kind": parsed[0],
        })
    require(rows, f"{path.name} has no top-level definitions")
    return rows


def old_artifact_differences(
    heap: B.Heap,
    compiled: list[dict[str, Any]],
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = load(manifest_path)
    blob = (ROOT / manifest["blob"]).read_bytes()
    old = {row["name"]: row for row in manifest["entries"]}
    differences = []
    for item in compiled:
        name = item["name"]
        require(name in old, f"old artifact lacks source entry: {name}")
        row = old[name]
        start, length = int(row["blob_offset"]), int(row["length"])
        raw = B.decode_code_object(blob[start:start + length])
        previous = {
            "nargs": raw.nargs,
            "nlocals": raw.nlocals,
            "flags": raw.flags,
            "literals": row["literals"],
            "payload_hex": bytes(raw.payload).hex(),
        }
        current = {
            key: item["summary"][key]
            for key in (
                "nargs", "nlocals", "flags", "literals", "payload_hex")
        }
        reasons = [
            key for key in current if current[key] != previous[key]
        ]
        if reasons:
            differences.append({
                "form_index": item["index"],
                "entry": name,
                "fields": reasons,
                "old_semantic_sha256": sha_bytes(canonical(previous)),
                "carrier_semantic_sha256": sha_bytes(canonical(current)),
                "old_payload_hex": previous["payload_hex"],
                "carrier_payload_hex": current["payload_hex"],
            })
    require(
        len(old) == len(compiled),
        "old artifact/source form count drift",
    )
    return {
        "old_artifact": bind(manifest_path),
        "entries_compared": len(compiled),
        "different_entries": len(differences),
        "differences": differences,
        "claim":
            "descriptive delta only; semantic differences do not alone "
            "constitute a First Red",
    }


def aggregate_manifest(
    name: str,
    heap: B.Heap,
    rows: list[dict[str, Any]],
    out: Path,
) -> Path:
    names = [row["name"] for row in rows]
    code_by_name = {row["name"]: row["code"] for row in rows}
    bundle = PB.pack_code_objects(
        heap, names, code_by_name, base_addr=0)
    pool = STD.LiteralPool()
    entries = []
    patches = []
    for entry in bundle.entries:
        row = next(item for item in rows if item["name"] == entry.name)
        code = row["code"]
        first, count = pool.add_obj_list(heap, code.littab)
        for slot in range(count):
            patches.append({
                "blob_offset":
                    entry.blob_offset + STD.CODE_LITTAB_OFFSET + 2 * slot,
                "node": pool.index[first + slot],
            })
        entries.append({
            "name": entry.name,
            "kind": "macro" if row["flags"] else "function",
            "flags": row["flags"],
            "code_flags": code.flags,
            "blob_offset": entry.blob_offset,
            "length": entry.obj_len,
            "lit_first": first,
            "lit_count": count,
            "literals": [
                STD._obj_spec(heap, literal) for literal in code.littab
            ],
        })
    require(
        len(pool.index) == len(pool.nodes)
        and sorted(pool.index) == list(range(len(pool.nodes))),
        f"{name} aggregate literal topology is incomplete",
    )
    out.mkdir(parents=True, exist_ok=True)
    blob_path = out / f"{name}.carrier-code.bin"
    manifest_path = out / f"{name}.carrier-manifest.json"
    blob_path.write_bytes(bytes(bundle.blob))
    value = {
        "format": "lisp65-c2-link75-carrier-session-input-v1",
        "name": name,
        "blob": blob_path.relative_to(ROOT).as_posix(),
        "blob_sha256": sha_bytes(bytes(bundle.blob)),
        "code_bytes": len(bundle.blob),
        "entries": entries,
        "exports": names,
        "late_bound_exports": [],
        "literal_nodes": pool.nodes,
        "literal_index": pool.index,
        "literal_patches": patches,
    }
    manifest_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def plane_counters(host: SESSION.ProductSessionHost) -> dict[str, int]:
    return {
        "images": host.plane.images,
        "entries": host.plane.entries,
        "resolutions": host.plane.resolutions,
        "roots": host.plane.roots,
        "code_bytes": host.plane.code_low,
    }


def append_aggregate(
    host: SESSION.ProductSessionHost,
    name: str,
    rows: list[dict[str, Any]],
    manifest_path: Path,
) -> dict[str, Any]:
    image = F.emit_image(name, name[:7], manifest_path)
    before = plane_counters(host)
    entry_base = host.plane.entries
    resolution_base = host.plane.resolutions
    symbols: list[tuple[int, int]] = []
    for local, row in enumerate(rows):
        raw, symbol = host._sync_symbol(row["name"])
        symbols.append((raw, symbol))
        host.ordinal_to_symbol[entry_base + local] = symbol
        host.raw_to_host[SESSION.mk_bcode(entry_base + local)] = symbol
    result = V6.append_image(
        host.plane,
        image,
        transient=False,
        direct_resolver=host._resolve_direct(image),
    )
    require(
        result["entries"] == len(rows)
        and result["handles"]
            == list(range(entry_base, entry_base + len(rows))),
        f"{name} aggregate append handle drift",
    )
    host._bind_image_objects(image, resolution_base, entry_base)
    snapshots = []
    for local, row in enumerate(rows):
        ordinal = entry_base + local
        snapshot = host.snapshot_entry(ordinal)
        symbol = symbols[local][1]
        host.directory[symbol] = snapshot["code"]
        host.code_names[id(snapshot["code"])] = row["name"]
        snapshots.append({
            key: value for key, value in snapshot.items() if key != "code"
        })
    return {
        "library": name,
        "status": "passed-one-persistent-image",
        "before": before,
        "after": plane_counters(host),
        "entries": len(rows),
        "handles": result["handles"],
        "code": {
            "bytes": len(image.code),
            "sha256": sha_bytes(image.code),
        },
        "metadata": {
            "bytes": len(image.metadata),
            "sha256": sha_bytes(image.metadata),
        },
        "descriptors": len(image.descriptors),
        "max_pair_depth": image.pair_depth,
        "snapshots": snapshots,
        "manifest": bind(manifest_path),
    }


def verify_tail_row(
    row: dict[str, Any],
    expected: int | None,
    crosses: bool,
) -> None:
    require(row.get("result") == expected, "tail result drift")
    calls = row.get("tail_calls")
    require(isinstance(calls, list), "tail call list absent")
    if crosses:
        require(
            len(calls) == 1
            and calls[0]["kind"] == "TAILCALL"
            and calls[0]["caller"] == "%lcc-v2-prim4"
            and calls[0]["target"] == "%lcc-v2-prim5"
            and calls[0]["argc"] == 1,
            "prim4/prim5 Tail boundary state drift",
        )
    else:
        require(not calls, "in-range prim4 case crossed its Tail boundary")


def tail_boundary_gate(compiler: BoundCarrierCompiler) -> dict[str, Any]:
    cases = (
        ("set", 59, False),
        ("key-event", 60, True),
        ("peek", 61, True),
        ("poke", 62, True),
        ("%c2d-byte", 67, True),
        ("intern", 68, True),
        ("%lcc-tail-miss", None, True),
    )
    rows = []
    for name, expected, crosses in cases:
        trace = CallTrace()
        vm = compiler.vm(trace)
        result = vm.run(
            compiler.directory[
                compiler.heap.intern("%lcc-v2-prim4")],
            [compiler.heap.intern(name)],
        )
        actual = None if result == B.NIL else fixnum(
            compiler.heap, result, f"{name}.result")
        tail_calls = [
            call for call in trace.calls
            if call["caller"] == "%lcc-v2-prim4"
            and call["target"] == "%lcc-v2-prim5"
        ]
        row = {
            "input": name,
            "expected": expected,
            "result": actual,
            "tail_calls": tail_calls,
            "steps": vm.steps,
        }
        verify_tail_row(row, expected, crosses)
        rows.append(row)

    rejected = []
    mutations = (
        ("wrong-target", 1, "target", "%lcc-v2-prim4"),
        ("call-not-tail", 1, "kind", "CALL"),
        ("wrong-result", 1, "result", 61),
    )
    for label, index, field, value in mutations:
        changed = json.loads(json.dumps(rows[index]))
        if field == "result":
            changed["result"] = value
        else:
            changed["tail_calls"][0][field] = value
        try:
            verify_tail_row(changed, cases[index][1], cases[index][2])
        except AttributionError:
            rejected.append(label)
        else:
            raise AttributionError(
                f"Tail-boundary mutation survived: {label}")
    return {
        "status": "passed-executed-packed-prim4-to-prim5-tail-boundary",
        "cases": rows,
        "mutations_rejected": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    output = args.output.resolve()
    receipt = args.receipt.resolve()
    try:
        output.mkdir(parents=True, exist_ok=True)
        compiler = BoundCarrierCompiler()
        geometry = initial_geometry()
        tail = tail_boundary_gate(compiler)
        compiled_libraries = []
        all_compiled: list[dict[str, Any]] = []
        for library in LIBRARIES:
            source = library["source"]
            compiled = []
            for source_row in source_rows(source):
                result = compiler.compile(source_row["source"])
                require(
                    result["name"] == source_row["name"]
                    and result["kind"] == source_row["kind"],
                    f"{source.name} carrier/source identity drift",
                )
                result.update(source_row)
                compiled.append(result)
                all_compiled.append(result)
            compiled_libraries.append({
                "name": library["name"],
                "source": bind(source),
                "forms": compiled,
                "old_artifact_comparison": old_artifact_differences(
                    compiler.heap, compiled, library["old_manifest"]),
            })

        # Lane 1: one persistent Session append per source form.  A thrown
        # exception names the exact last successful form without a second run.
        form_host = SESSION.ProductSessionHost(
            geometry, output / "formwise")
        attach_heap(form_host, compiler.heap)
        form_rows = []
        for library in compiled_libraries:
            for item in library["forms"]:
                append = form_host.append_compiled_definition(
                    item["source"],
                    item["name"],
                    item["code"],
                    export_flags=item["flags"],
                    compiler_authority=bind(CARRIER)["sha256"],
                )
                form_rows.append({
                    "library": library["name"],
                    "form_index": item["index"],
                    "entry": item["name"],
                    "kind": item["kind"],
                    "compiler_steps": item["steps"],
                    "compiler_tail_boundary_calls":
                        len(item["tail_boundary_calls"]),
                    "code": item["summary"],
                    "append": append,
                })

        # Lane 2: require-shaped publication, one image per library.
        aggregate_host = SESSION.ProductSessionHost(
            geometry, output / "aggregate")
        attach_heap(aggregate_host, compiler.heap)
        aggregate_rows = []
        for library in compiled_libraries:
            manifest = aggregate_manifest(
                library["name"],
                compiler.heap,
                library["forms"],
                output / "aggregate",
            )
            aggregate_rows.append(append_aggregate(
                aggregate_host,
                library["name"],
                library["forms"],
                manifest,
            ))

        require(
            len(form_rows) == 32
            and len(aggregate_rows) == 2
            and plane_counters(form_host)["images"]
                == geometry["images"] + 32
            and plane_counters(aggregate_host)["images"]
                == geometry["images"] + 2,
            "Session lane completion accounting drift",
        )
        carrier_compile_tail_forms = [
            {
                "library": library["name"],
                "form_index": item["index"],
                "entry": item["name"],
                "calls": len(item["tail_boundary_calls"]),
            }
            for library in compiled_libraries
            for item in library["forms"]
            if item["tail_boundary_calls"]
        ]
        require(
            any(row["entry"] == "%defstruct-symbol"
                for row in carrier_compile_tail_forms),
            "real defstruct compilation did not exercise prim4/prim5 Tail",
        )
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-28",
            "status":
                "passed-bound-carrier-and-append-shapes-real-resolver-"
                "not-executed",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "incident": bind(HARDWARE_FIRST_RED),
            "carrier": {
                "manifest": bind(CARRIER),
                "blob": bind(ROOT / compiler.manifest["blob"]),
                "tier": bind(TIER),
                "source_binding": compiler.source_binding,
                "objects": len(compiler.manifest["entries"]),
            },
            "base_geometry": geometry,
            "tail_boundary": tail,
            "real_library_compilation_tail_crossings":
                carrier_compile_tail_forms,
            "formwise_session_lane": {
                "status": "passed-all-32-source-forms",
                "meaning":
                    "Each form was compiled by the packed carrier and "
                    "persistently appended via C2I-v2/C2D-v6; the row order "
                    "is an exact source-form bisect.",
                "last_successful_form": {
                    "library": form_rows[-1]["library"],
                    "form_index": form_rows[-1]["form_index"],
                    "entry": form_rows[-1]["entry"],
                },
                "forms": form_rows,
                "final": plane_counters(form_host),
            },
            "require_shaped_session_lane": {
                "status": "passed-place-then-defstruct-as-two-images",
                "scope": "append-shape-only",
                "actual_lisp_resolver_executed": False,
                "prim67_c2d_byte_calls": 0,
                "dependency_order": ["place", "defstruct"],
                "images": aggregate_rows,
                "final": plane_counters(aggregate_host),
            },
            "previous_artifact_deltas": {
                library["name"]: library["old_artifact_comparison"]
                for library in compiled_libraries
            },
            "attribution": {
                "host_reproduction": "not-tested-at-resolver-boundary",
                "last_successful_form": "lib/defstruct.lisp form 15 defstruct",
                "compiler_bytecode": "entire bound Link-75 carrier executed",
                "tail_split":
                    "executed directly and crossed by real defstruct forms",
                "formwise_append": "all 32 forms passed",
                "require_shaped_append":
                    "place and defstruct each passed as one persistent image; "
                    "this lane did not call require, %l65i-parse, "
                    "%require-resolve or %c2d-byte",
                "remaining_boundary":
                    "the actual compiled Lisp resolver and its Prim-67 C2D "
                    "reads are untested; only after that host boundary passes "
                    "does the remaining surface become target-specific",
                "next_step":
                    "Execute the exact Link-75 resolver bytecode host-side "
                    "against the exact Link-75 C2D image and defstruct D81 "
                    "before any hardware retry.",
            },
            "claim_limit": (
                "Host execution proves the packed carrier bytecode, its "
                "prim4/prim5 Tail contract, C2I-v2 emission and the C2D-v6 "
                "persistent append model. The two-image lane is append-shaped "
                "only: it executes neither require nor %l65i-parse, "
                "%require-resolve or %c2d-byte (Prim-67 call count is zero). "
                "It also does not execute MEGA65 CPU semantics, physical "
                "DMA/media/overlay transport or target timing."
            ),
            "authority": {
                "static_c2d": bind(STATIC_C2D),
                "static_bank2": bind(STATIC_CODE),
                "session_runner": bind(
                    ROOT / "tools/host-lisp/c2_product_session_host.py"),
                "driver": bind(Path(__file__).resolve()),
            },
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "c2-link75-require-defstruct-host-attribution: PASS "
            "carrier-forms=32 form-appends=32 aggregate-images=2 "
            f"tail-cases={len(tail['cases'])} "
            "resolver-executed=no prim67-calls=0"
        )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        B.BytecodeError,
        STD.StdlibCheckError,
        BOUND.GateError,
        F.FullError,
        V6.ProbeError,
        SESSION.SessionHostError,
        AttributionError,
    ) as error:
        print(
            "c2-link75-require-defstruct-host-attribution: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
