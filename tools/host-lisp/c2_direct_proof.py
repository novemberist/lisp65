#!/usr/bin/env python3
"""Build, decode and execute the isolated C2.1 direct-container proof image.

The target deliberately does not import the product L65M loader or modify a
v1.1 source.  Its emitter follows the owner-approved C2I-v1 envelope, while
the decoder derives all counts, widths and section boundaries from the bytes.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import eval_surface_contract as E  # noqa: E402


TARGET = ROOT / "config" / "c2.1-direct-proof.json"
CORE = ROOT / "config" / "c2-address-identity-contract.json"
ENVELOPE = ROOT / "config" / "c2-metadata-envelope-proposal.json"
FIXTURE = ROOT / "tests" / "bytecode" / "dialect-v2" / "c2" / "cases.json"
BINARY = ROOT / "build" / "equivalence" / "dialect-v2-equivalence-check"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-direct-proof-receipt.json"
)

HEADER_BYTES = 24
ENTRY_BYTES = 16
LITERAL_BYTES = 8
CO_MAGIC = 0xB5
CO_STRICT_ARITY = 0x02
ANONYMOUS = 0xFFFF
ENTRY_REF = 4
PRIM_APPLY = 7
PRIM_FUNCALL = 8


class ProofError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha_path(path),
    }


def u24(value: int) -> bytes:
    require(0 <= value <= 0xFFFFFF, "u24 overflow")
    return bytes((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))


def read_u16(data: bytes, offset: int) -> int:
    require(offset + 2 <= len(data), "truncated u16")
    return data[offset] | data[offset + 1] << 8


def read_u24(data: bytes, offset: int) -> int:
    require(offset + 3 <= len(data), "truncated u24")
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def code_object(arity: int, literal_count: int, payload: bytes) -> bytes:
    require(0 <= arity <= 0xFF and 0 <= literal_count <= 0xFF, "code header overflow")
    require(len(payload) <= 0xFFFF, "code payload overflow")
    header = bytes((CO_MAGIC, arity, 0, CO_STRICT_ARITY))
    header += struct.pack("<H", len(payload)) + bytes((literal_count,))
    return header + bytes(2 * literal_count) + payload


def proof_code_objects() -> list[bytes]:
    # Opcodes are the pinned P0 ABI: PUSHI8=1, ADD=2, RET=5, PUSHLIT=6,
    # PUSHARG0=11, PUSHNIL=43, CONS=51, CALL=60, CALLPRIM=61,
    # TAILCALL=62 and CLOSURE=63.
    return [
        code_object(1, 0, bytes((11, 1, 1, 2, 5))),
        code_object(0, 1, bytes((1, 41, 60, 0, 1, 5))),
        code_object(0, 1, bytes((6, 0, 1, 41, 61, PRIM_FUNCALL, 2, 5))),
        code_object(0, 1, bytes((6, 0, 1, 41, 43, 51, 61, PRIM_APPLY, 2, 5))),
        code_object(0, 1, bytes((63, 0, 0, 1, 41, 61, PRIM_FUNCALL, 2, 5))),
        code_object(0, 1, bytes((1, 41, 62, 0, 1))),
    ]


def literal_entry_ref(ordinal: int) -> bytes:
    return bytes((ENTRY_REF, 0)) + struct.pack("<H", ordinal) + u24(0) + b"\0"


def build_image(target: dict[str, Any]) -> tuple[bytes, bytes]:
    code_objects = proof_code_objects()
    require(len(target.get("entries", [])) == len(code_objects), "target entry count drift")
    code = b"".join(code_objects)
    offsets: list[int] = []
    cursor = 0
    for item in code_objects:
        offsets.append(cursor)
        cursor += len(item)

    descriptors: list[bytes] = []
    entries = bytearray()
    for index, (spec, encoded) in enumerate(zip(target["entries"], code_objects)):
        require(spec.get("ordinal") == index, "target ordinal drift")
        literals = spec.get("literals")
        require(isinstance(literals, list), "target literals must be a list")
        first = len(descriptors)
        for literal in literals:
            require(literal == {"kind": "container-entry-ordinal-u16", "ordinal": 0},
                    "unexpected proof literal")
            descriptors.append(literal_entry_ref(0))
        record = bytearray()
        record += u24(offsets[index])
        record += struct.pack("<H", len(encoded))
        record += struct.pack("<H", first)
        record += bytes((len(literals), ANONYMOUS & 0xFF, ANONYMOUS >> 8))
        record += bytes((spec["arity"], 0))
        record += struct.pack("<H", index)
        record += b"\0\0"
        require(len(record) == ENTRY_BYTES, "entry encoder width drift")
        entries += record

    literal_blob = b"".join(descriptors)
    strings = b""
    entries_offset = HEADER_BYTES
    literals_offset = entries_offset + len(entries)
    strings_offset = literals_offset + len(literal_blob)
    header = bytearray(b"C2I\0")
    header += bytes((1, HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES))
    header += struct.pack(
        "<HHHHHHHH",
        0,
        len(code_objects),
        len(descriptors),
        entries_offset,
        literals_offset,
        strings_offset,
        len(strings),
        0,
    )
    require(len(header) == HEADER_BYTES, "metadata header encoder width drift")
    metadata = bytes(header) + bytes(entries) + literal_blob + strings
    if len(metadata) & 1:
        metadata += b"\0"
    return code, metadata


@dataclass(frozen=True)
class Entry:
    ordinal: int
    code_offset: int
    code_length: int
    literal_first: int
    literal_count: int
    arity: int
    diagnostic_ordinal: int
    payload_offset: int
    payload_length: int


@dataclass(frozen=True)
class BCode:
    generation: int
    ordinal: int


@dataclass(frozen=True)
class Closure:
    target: BCode
    captures: tuple[Any, ...]


@dataclass(frozen=True)
class Pair:
    car: Any
    cdr: Any


@dataclass
class DecodedImage:
    code: bytes
    metadata: bytes
    entries: list[Entry]
    resolutions: list[Any]
    generation: int
    identity: str


def parse_string_records(pool: bytes) -> dict[int, bytes]:
    records: dict[int, bytes] = {}
    cursor = 0
    while cursor < len(pool):
        require(cursor + 2 <= len(pool), "truncated string length")
        length = read_u16(pool, cursor)
        end = cursor + 2 + length
        require(end <= len(pool), "string record crosses pool")
        records[cursor] = pool[cursor + 2:end]
        cursor = end
    return records


def decode_image(code: bytes, metadata: bytes, generation: int = 1) -> DecodedImage:
    require(len(metadata) >= HEADER_BYTES, "metadata shorter than header")
    require(metadata[:4] == b"C2I\0" and metadata[4] == 1, "bad C2I magic or version")
    require(tuple(metadata[5:8]) == (HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES),
            "record-size mismatch")
    require(read_u16(metadata, 8) == 0, "nonzero header flags")
    entry_count = read_u16(metadata, 10)
    literal_count = read_u16(metadata, 12)
    entries_offset = read_u16(metadata, 14)
    literals_offset = read_u16(metadata, 16)
    strings_offset = read_u16(metadata, 18)
    strings_bytes = read_u16(metadata, 20)
    require(read_u16(metadata, 22) == 0, "nonzero header reserved")
    require(entries_offset == HEADER_BYTES, "entry section is not contiguous")
    require(literals_offset == entries_offset + entry_count * ENTRY_BYTES,
            "literal section arithmetic mismatch")
    require(strings_offset == literals_offset + literal_count * LITERAL_BYTES,
            "string section arithmetic mismatch")
    unaligned = strings_offset + strings_bytes
    expected_bytes = (unaligned + 1) & ~1
    require(expected_bytes == len(metadata), "metadata length mismatch")
    if unaligned != expected_bytes:
        require(metadata[-1] == 0, "nonzero metadata alignment byte")
    require(generation != 0, "zero session generation")

    string_pool = metadata[strings_offset:unaligned]
    string_records = parse_string_records(string_pool)
    descriptors: list[tuple[int, int, int]] = []
    for index in range(literal_count):
        offset = literals_offset + index * LITERAL_BYTES
        kind, flags = metadata[offset], metadata[offset + 1]
        arg0 = read_u16(metadata, offset + 2)
        arg1 = read_u24(metadata, offset + 4)
        reserved = metadata[offset + 7]
        require(kind <= 6, "unknown literal kind")
        require(flags == 0 and reserved == 0, "nonzero literal flags or reserved")
        if kind == ENTRY_REF:
            require(arg0 < entry_count and arg1 == 0, "entry-ref descriptor out of range")
        elif kind in (0, 1):
            require(arg0 == 0 and arg1 == 0, "unused literal argument is nonzero")
        elif kind == 2:
            signed = arg0 - 0x10000 if arg0 & 0x8000 else arg0
            require(-16384 <= signed <= 16383 and arg1 == 0, "fixnum descriptor out of range")
        elif kind in (3, 5):
            require(arg1 in string_records, "string offset is not a record boundary")
            require(len(string_records[arg1]) == arg0, "string descriptor length mismatch")
            if kind == 5:
                value = string_records[arg1]
                require(1 <= len(value) <= 255, "symbol name length is invalid")
                require(all(0x21 <= byte <= 0x7E for byte in value),
                        "symbol name is not canonical ASCII")
        elif kind == 6:
            require(arg1 == 0, "native primitive unused argument is nonzero")
        descriptors.append((kind, arg0, arg1))

    entries: list[Entry] = []
    late_bound: set[int] = set()
    for ordinal in range(entry_count):
        offset = entries_offset + ordinal * ENTRY_BYTES
        code_offset = read_u24(metadata, offset)
        code_length = read_u16(metadata, offset + 3)
        literal_first = read_u16(metadata, offset + 5)
        local_count = metadata[offset + 7]
        export_offset = read_u16(metadata, offset + 8)
        arity = metadata[offset + 10]
        flags = metadata[offset + 11]
        diagnostic = read_u16(metadata, offset + 12)
        reserved = read_u16(metadata, offset + 14)
        require(code_length != 0 and code_offset + code_length <= len(code),
                "entry code range outside region")
        require(literal_first + local_count <= literal_count,
                "entry literal range outside metadata")
        require(flags & ~3 == 0 and reserved == 0, "entry flags or reserved invalid")
        if export_offset == ANONYMOUS:
            require(flags == 0, "anonymous entry carries export flags")
        else:
            require(export_offset in string_records, "export name offset is not a record boundary")
            name = string_records[export_offset]
            require(1 <= len(name) <= 255 and all(0x21 <= byte <= 0x7E for byte in name),
                    "export name is not canonical ASCII")
        if flags & 2:
            late_bound.add(ordinal)
        raw = code[code_offset:code_offset + code_length]
        require(len(raw) >= 7 and raw[0] == CO_MAGIC, "bad code-object header")
        payload_length = read_u16(raw, 4)
        code_literals = raw[6]
        payload_offset = 7 + 2 * code_literals
        require(raw[1] == arity and code_literals == local_count,
                "entry/code header arity or literal-count mismatch")
        require(payload_offset + payload_length == len(raw), "code-length equation mismatch")
        require(all(byte == 0 for byte in raw[7:payload_offset]),
                "stored literal-shaped code bytes are not zero")
        entries.append(Entry(
            ordinal, code_offset, code_length, literal_first, local_count,
            arity, diagnostic, payload_offset, payload_length,
        ))

    for kind, arg0, _arg1 in descriptors:
        if kind == ENTRY_REF:
            require(arg0 not in late_bound, "late-bound entry targeted by ordinal")

    resolutions: list[Any] = []
    for kind, arg0, arg1 in descriptors:
        if kind == 0:
            resolutions.append(None)
        elif kind == 1:
            resolutions.append(True)
        elif kind == 2:
            resolutions.append(arg0 - 0x10000 if arg0 & 0x8000 else arg0)
        elif kind == ENTRY_REF:
            resolutions.append(BCode(generation, arg0))
        elif kind in (3, 5):
            resolutions.append(string_records[arg1])
        else:
            resolutions.append(("primitive", arg0))
    identity = sha_bytes(code + metadata)
    return DecodedImage(code, metadata, entries, resolutions, generation, identity)


class DirectVM:
    def __init__(self, image: DecodedImage, window_bytes: int):
        require(window_bytes > 0, "code window must be nonzero")
        self.image = image
        self.window_bytes = window_bytes
        self.refills = 0
        self.max_depth = 0
        self.steps = 0
        self._window_key: tuple[int, int, int] | None = None
        self._window = b""
        self._window_start = 0

    def _byte(self, entry: Entry, pc: int) -> int:
        require(0 <= pc < entry.payload_length, "code-window refill crosses entry bounds")
        absolute = entry.code_offset + entry.payload_offset + pc
        key = (self.image.generation, entry.ordinal, absolute // self.window_bytes)
        if key != self._window_key:
            start = absolute - (absolute % self.window_bytes)
            entry_end = entry.code_offset + entry.code_length
            end = min(start + self.window_bytes, entry_end)
            require(start >= entry.code_offset and end <= entry_end, "window outside entry")
            self._window = self.image.code[start:end]
            self._window_start = start
            self._window_key = key
            self.refills += 1
        return self._window[absolute - self._window_start]

    @staticmethod
    def _pop_args(stack: list[Any], count: int) -> list[Any]:
        require(count <= len(stack), "call stack underflow")
        args = stack[-count:] if count else []
        if count:
            del stack[-count:]
        return args

    @staticmethod
    def _list_values(value: Any) -> list[Any]:
        out: list[Any] = []
        while value is not None:
            require(isinstance(value, Pair), "apply expects a proper list")
            out.append(value.car)
            value = value.cdr
        return out

    def _invoke(self, target: Any, args: list[Any], depth: int) -> Any:
        captures: tuple[Any, ...] = ()
        if isinstance(target, Closure):
            captures = target.captures
            target = target.target
        require(isinstance(target, BCode), "value is not callable")
        require(target.generation == self.image.generation, "stale session generation")
        return self._run(target.ordinal, args, depth + 1, captures)

    def _run(self, ordinal: int, args: list[Any], depth: int, captures: tuple[Any, ...] = ()) -> Any:
        require(0 <= ordinal < len(self.image.entries), "directory ordinal out of range")
        entry = self.image.entries[ordinal]
        require(len(args) == entry.arity, "wrong argument count")
        self.max_depth = max(self.max_depth, depth)
        stack: list[Any] = []
        pc = 0
        while pc < entry.payload_length:
            op = self._byte(entry, pc)
            pc += 1
            self.steps += 1
            require(self.steps <= 10000, "step limit")
            if op == 1:  # PUSHI8
                value = self._byte(entry, pc)
                pc += 1
                stack.append(value - 256 if value & 0x80 else value)
            elif op == 2:  # ADD
                require(len(stack) >= 2 and type(stack[-1]) is int and type(stack[-2]) is int,
                        "ADD expects integers")
                right, left = stack.pop(), stack.pop()
                stack.append(left + right)
            elif op == 5:  # RET
                require(stack, "RET with empty stack")
                return stack.pop()
            elif op == 6:  # PUSHLIT
                index = self._byte(entry, pc)
                pc += 1
                require(index < entry.literal_count, "literal index out of range")
                stack.append(self.image.resolutions[entry.literal_first + index])
            elif op == 11:  # PUSHARG0
                require(args, "PUSHARG0 without argument")
                stack.append(args[0])
            elif op == 43:  # PUSHNIL
                stack.append(None)
            elif op == 51:  # CONS
                require(len(stack) >= 2, "CONS stack underflow")
                cdr, car = stack.pop(), stack.pop()
                stack.append(Pair(car, cdr))
            elif op in (60, 62):  # CALL / TAILCALL
                index = self._byte(entry, pc)
                argc = self._byte(entry, pc + 1)
                pc += 2
                require(index < entry.literal_count, "callee literal index out of range")
                call_args = self._pop_args(stack, argc)
                result = self._invoke(
                    self.image.resolutions[entry.literal_first + index], call_args, depth
                )
                if op == 62:
                    return result
                stack.append(result)
            elif op == 61:  # CALLPRIM apply/funcall
                prim = self._byte(entry, pc)
                argc = self._byte(entry, pc + 1)
                pc += 2
                call_args = self._pop_args(stack, argc)
                require(call_args, "CALLPRIM lacks function designator")
                if prim == PRIM_FUNCALL:
                    stack.append(self._invoke(call_args[0], call_args[1:], depth))
                elif prim == PRIM_APPLY:
                    require(len(call_args) >= 2, "apply needs function and list")
                    expanded = call_args[1:-1] + self._list_values(call_args[-1])
                    stack.append(self._invoke(call_args[0], expanded, depth))
                else:
                    raise ProofError("unsupported proof primitive %d" % prim)
            elif op == 63:  # CLOSURE
                index = self._byte(entry, pc)
                capture_count = self._byte(entry, pc + 1)
                pc += 2
                require(index < entry.literal_count and capture_count <= len(stack),
                        "CLOSURE operands invalid")
                captured = tuple(self._pop_args(stack, capture_count))
                target = self.image.resolutions[entry.literal_first + index]
                require(isinstance(target, BCode), "CLOSURE target is not an entry ref")
                stack.append(Closure(target, captured))
            else:
                raise ProofError("unsupported proof opcode %d" % op)
        raise ProofError("entry ended without RET or TAILCALL")

    def run(self, ordinal: int) -> Any:
        return self._run(ordinal, [], 1)


def validate_target(target: dict[str, Any]) -> None:
    require(target.get("format") == "lisp65-c2.1-direct-proof-v1", "target format drift")
    require(target.get("status") == "internal-proof-implementation", "target status drift")
    require(target.get("metadata_envelope") == "local-24-byte-header", "target envelope drift")
    require(target.get("session_generation") == 1, "target generation drift")
    require(target.get("window_bytes") == 8, "target window drift")
    routes = target.get("expected_routes")
    require(routes == {route: 42 for route in ("direct", "funcall", "apply", "closure", "tail-call")},
            "target route closure drift")
    require(target.get("required_engines") == [
        "native-c-treewalk", "native-c-compiler-vm",
        "python-p0-compiler-vm", "lisp-lcc",
    ], "four-engine list drift")


def run_four_engines(target: dict[str, Any]) -> list[dict[str, Any]]:
    fixture = E._load_fixture(FIXTURE)
    require(BINARY.is_file() and not BINARY.is_symlink(), "dialect-v2 equivalence binary missing")
    rows: list[dict[str, Any]] = []
    cases, forms, steps, helpers = E.run_fixture(
        fixture, str(FIXTURE), abi_profile="dialect-v2"
    )
    rows.append({
        "id": "python-p0-compiler-vm", "cases": cases, "forms": forms,
        "p0_steps": steps, "helpers": helpers, "status": "passed",
    })
    for engine, adapter in (
        ("native-c-treewalk", "native-treewalk"),
        ("native-c-compiler-vm", "native-c-compiler-vm"),
    ):
        cases, forms = E.run_native_fixture(fixture, BINARY, adapter, str(FIXTURE))
        rows.append({"id": engine, "cases": cases, "forms": forms, "status": "passed"})
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".lisp") as preload:
        preload.write((ROOT / "lib" / "lcc.lisp").read_text(encoding="utf-8"))
        preload.write("\n")
        preload.write((ROOT / "lib" / "dialect-v2" / "lcc-profile.lisp").read_text(encoding="utf-8"))
        preload.flush()
        cases, forms = E.run_native_fixture(
            fixture, BINARY, "lisp-lcc", str(FIXTURE), preload=Path(preload.name)
        )
    rows.append({"id": "lisp-lcc", "cases": cases, "forms": forms, "status": "passed"})
    order = target["required_engines"]
    rows.sort(key=lambda row: order.index(row["id"]))
    require(all(row["cases"] == 5 and row["forms"] == 7 for row in rows),
            "four-engine case coverage drift")
    return rows


def render() -> dict[str, Any]:
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    core = json.loads(CORE.read_text(encoding="utf-8"))
    envelope = json.loads(ENVELOPE.read_text(encoding="utf-8"))
    validate_target(target)
    require(core.get("status") == "owner-approved-c2.1-proof-authorized", "C2 core not approved")
    require(envelope.get("status") == "owner-approved-c2.1-bytes-authorized", "C2 envelope not approved")
    code, metadata = build_image(target)
    before = sha_bytes(code)
    image = decode_image(code, metadata, target["session_generation"])
    vm = DirectVM(image, target["window_bytes"])
    observations: dict[str, int] = {}
    for entry in target["entries"]:
        route = entry["route"]
        if route == "helper":
            continue
        observations[route] = vm.run(entry["ordinal"])
    require(observations == target["expected_routes"], "direct-image route result drift")
    require(sha_bytes(code) == before, "immutable code changed during execution")
    engine_rows = run_four_engines(target)
    return {
        "format": "lisp65-c2.1-direct-proof-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "host-proof-passed-device-link-not-run",
        "claim_limit": (
            "This receipt proves exact owner-approved C2I emission/decoding, immutable "
            "host-model execution and semantic route parity in four engines. It does not "
            "prove the target decoder, Enhanced-DMA timing, reset hardware, capacity or a product."
        ),
        "bindings": {
            "target": binding(TARGET),
            "core_contract": binding(CORE),
            "metadata_envelope": binding(ENVELOPE),
            "four_engine_fixture": binding(FIXTURE),
            "equivalence_binary": binding(BINARY),
            "verifier": binding(Path(__file__)),
        },
        "image": {
            "code_bytes": len(code),
            "metadata_bytes": len(metadata),
            "entry_count": len(image.entries),
            "literal_count": len(image.resolutions),
            "code_sha256": sha_bytes(code),
            "metadata_sha256": sha_bytes(metadata),
            "image_sha256": image.identity,
            "immutable_after_execution": True,
        },
        "direct_image_execution": {
            "routes": observations,
            "window_bytes": vm.window_bytes,
            "window_refills": vm.refills,
            "steps": vm.steps,
            "maximum_call_depth": vm.max_depth,
        },
        "semantic_four_engine_closure": {
            "relationship": (
                "The four engines execute the source-level route semantics; the exact C2 "
                "image is independently emitted, decoded and executed above. No claim says "
                "that the legacy engines decode C2I bytes."
            ),
            "engines": engine_rows,
            "cases_per_engine": 5,
            "forms_per_engine": 7,
            "evaluations": 20,
        },
        "capacity_delta": {
            "product_bytes": 0,
            "bank0": "not-linked",
            "ext": "not-linked",
            "boot_overlay": "not-linked",
            "runtime_overlay_bank": "not-linked",
            "resident_island": "not-linked",
            "installer_slice": "not-linked",
        },
        "next_authorized_action": (
            "Implement the independent target-side decoder/refill proof and the full "
            "negative/reset matrix, then stop before any product or capacity claim."
        ),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expect_failure(label: str, action: Any, contains: str) -> None:
    try:
        action()
    except ProofError as exc:
        require(contains in str(exc), "selftest %s wrong failure: %s" % (label, exc))
        return
    raise ProofError("selftest %s mutation passed" % label)


def selftest() -> None:
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    code, metadata = build_image(target)
    decoded = decode_image(code, metadata)
    require(len(decoded.entries) == 6 and len(decoded.resolutions) == 5, "selftest baseline drift")

    bad_magic = bytearray(metadata)
    bad_magic[0] ^= 1
    expect_failure("magic", lambda: decode_image(code, bytes(bad_magic)), "bad C2I")

    zero_length = bytearray(metadata)
    zero_length[HEADER_BYTES + 3:HEADER_BYTES + 5] = b"\0\0"
    expect_failure("zero-length", lambda: decode_image(code, bytes(zero_length)), "entry code range")

    bad_ref = bytearray(metadata)
    literal_offset = read_u16(metadata, 16)
    bad_ref[literal_offset + 2:literal_offset + 4] = struct.pack("<H", 99)
    expect_failure("entry-ref", lambda: decode_image(code, bytes(bad_ref)), "entry-ref")

    bad_literal_shape = bytearray(code)
    second = len(proof_code_objects()[0])
    bad_literal_shape[second + 7] = 1
    expect_failure(
        "literal-shaped-code-byte",
        lambda: decode_image(bytes(bad_literal_shape), metadata),
        "literal-shaped",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
            print("c2-direct-proof: SELFTEST PASS mutations=4")
            return 0
        value = render()
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data)
            action = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "pinned C2.1 direct-proof receipt drift")
            action = "PASS"
        print(
            "c2-direct-proof: %s entries=%d routes=5 engines=4 image=%s"
            % (action, value["image"]["entry_count"], value["image"]["image_sha256"][:12])
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, E.ContractError, ProofError) as exc:
        print("c2-direct-proof: FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
