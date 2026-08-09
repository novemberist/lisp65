#!/usr/bin/env python3
"""Reconstruct the exact Link-82 require/defstruct sequence on the host.

Phase A deliberately joins boundaries that older receipts proved separately:
the released Link-82 resolver and C2D plane, the product-bound library medium,
the compiler carrier actually bound by Link 82, the returned defstruct macro
expansion, and every persistent definition emitted by that expansion.

The Python VM executes objects directly.  ``WindowTrace`` shadows the linked
VM_CODEBUF=56 algorithm over the same instruction stream and records every
initial window and post-return/sequential refill.  Its expected bytes always
come from the bound CodeObject payload, never from refill metadata.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402
import c2_link75_require_defstruct_host_attribution as CARRIER  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.5-candidate-product-link82"
STATIC = BASE / "static-plane/narrow-static"
STDLIB = STATIC / "stdlib-p0.manifest.json"
STATIC_C2D = STATIC / "v6-semantics/initial.c2d-v6.bin"
STATIC_CODE = STATIC / "v6-semantics/bank2-static-code.bin"
MEDIA = ROOT / (
    "build/ship-builder/v1-device-session/defstruct-media/"
    "require-defstruct-ship-session.d81"
)
MEDIA_DIR = MEDIA.parent
FOUNDATIONS = ROOT / "build/post-promotion/defstruct-v1/foundations"
LINK82 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-phase-b-link82-receipt.json"
)
QUIET_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-first-red.json"
)
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
VM_SOURCE = ROOT / "src/vm.c"
RUNTIME_PROFILE = ROOT / "config/runtime-core.mk"
GATES = ROOT / "mk/gates.mk"
BOUND_PARITY = BASE / "receipts/bound-artifact-source-parity.json"
COMPILER_MANIFEST = ROOT / (
    "build/post-promotion/phase-v/while/gate/carrier/lcc.manifest.json"
)
COMPILER_TIER = ROOT / (
    "build/post-promotion/phase-v/while/gate/compiler-tier/"
    "tier-generation.json"
)
WRONG_MEDIA = ROOT / "build/c2.2/v1.2.5-candidate-media/lisp65-product.d81"
OUT = ROOT / "build/post-promotion/v16/defstruct-phase-a"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json"
)
FORMAT = "lisp65-c2.3-v1.6-defstruct-phase-a-host-reconstruction-v1"
RECORDED_ON = "2026-08-04"
VM_CODEBUF = 56
EXPECTED_SOURCE_COMMIT = "fe5c98fea63236af3bddca86bf1bb955cf9a6ffe"
EXPECTED_MEDIA_SHA = "871b90824924dacbe27f071d56b0b97488257da0c1a0b9e80f5d5eeae5f23380"
EXPECTED_CARRIER_SHA = (
    "7996e2a714e3ef2490d296d7867fb7c98710c3d6f36f3fe7965d7ff293886519"
)


class PhaseAError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseAError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = str(path.resolve())
    return {"path": name, "bytes": len(data), "sha256": sha_bytes(data)}


def git_blob(relative: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{EXPECTED_SOURCE_COMMIT}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(
        process.returncode == 0,
        process.stderr.decode(errors="replace").strip()
        or f"historical source absent: {relative}",
    )
    return process.stdout


def bind_git(relative: str) -> dict[str, Any]:
    data = git_blob(relative)
    return {
        "authority": "git-blob",
        "commit": EXPECTED_SOURCE_COMMIT,
        "path": relative,
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(encoded, encoding="utf-8")


def geometry() -> dict[str, int]:
    data = STATIC_C2D.read_bytes()
    code = STATIC_CODE.read_bytes()
    require(
        len(data) == 33840 and data[:8] == b"C2D\0\x06\x30\x20\x0a",
        "Link-82 C2D identity/geometry drift",
    )
    u16 = lambda at: struct.unpack_from("<H", data, at)[0]
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]
    result = {
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
        result == {
            "generation": 1,
            "images": 6,
            "entries": 725,
            "resolutions": 2842,
            "roots": 340,
            "code_bytes": 43237,
            "immutable_images": 6,
            "catalog_crc32": 0xA8E0DAEC,
            "build_id": 0x270030C3,
        },
        f"Link-82 static geometry drift: {result}",
    )
    return result


def validate_window_authority() -> None:
    source = git_blob(VM_SOURCE.relative_to(ROOT).as_posix()).decode("utf-8")
    profile = git_blob(RUNTIME_PROFILE.relative_to(ROOT).as_posix()).decode(
        "utf-8"
    )
    required = (
        "#define BUF_ENSURE_MINE(pcur_) do {",
        "win = (pcur_); winlen = 0; ip = code; streaming = 1;",
        "#define WIN_ENSURE() do {",
        "uint16_t need_ =",
        "vm_object_load(bank, off, (uint16_t)(payload_off + pc_), winlen",
    )
    require(
        all(fragment in source for fragment in required),
        "linked VM window/refill algorithm drift",
    )
    require("-DVM_CODEBUF=56" in profile, "Link-82 VM_CODEBUF profile drift")


def configure_resolver() -> dict[str, int]:
    result = geometry()
    R.BASE = BASE
    R.STATIC = STATIC
    R.STDLIB = STDLIB
    R.STATIC_C2D = STATIC_C2D
    R.STATIC_CODE = STATIC_CODE
    R.MEDIA = MEDIA
    R.OUT = OUT
    R.ATTR.initial_geometry = lambda: dict(result)
    return result


class HistoricalCarrier(CARRIER.BoundCarrierCompiler):
    """Load the exact Link-82 carrier without comparing it to today's source.

    ``c2_bound_artifact_source_parity`` correctly rejects this historical
    carrier against the post-1.3 working source.  Link 82's own parity receipt
    is the authority here; accepting current-source parity would silently
    replace the forensic base.
    """

    def __init__(self) -> None:
        parity = load(BOUND_PARITY)
        carrier_binding = parity["compiler_carrier"]["carrier"]
        require(
            carrier_binding["sha256"] == EXPECTED_CARRIER_SHA
            and bind(COMPILER_MANIFEST)["sha256"] == EXPECTED_CARRIER_SHA,
            "Link-82 compiler-carrier binding drift",
        )
        self.manifest = load(COMPILER_MANIFEST)
        self.suite = load(ROOT / self.manifest["suite"])
        self.source_binding = {
            "mode": "historical-Link82-bound-artifact",
            "current_source_parity_claimed": False,
            "Link82_parity_receipt": bind(BOUND_PARITY),
        }
        self.blob = (ROOT / self.manifest["blob"]).read_bytes()
        require(
            sha_bytes(self.blob) == self.manifest["blob_sha256"],
            "Link-82 carrier blob drift",
        )
        patch_by_offset = {
            int(row["blob_offset"]): int(row["node"])
            for row in self.manifest["literal_patches"]
        }
        self.heap = C.prepare_heap([])
        self.directory: dict[int, B.CodeObject] = {}
        self.macro_symbols: set[int] = set()
        self.code_names: dict[int, str] = {}
        for entry in self.manifest["entries"]:
            code = STD._patched_code_from_manifest_entry(
                self.heap, self.manifest, self.blob, entry, patch_by_offset
            )
            symbol = self.heap.intern(entry["name"])
            require(symbol not in self.directory, "duplicate carrier entry")
            self.directory[symbol] = code
            self.code_names[id(code)] = entry["name"]
            if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
                self.macro_symbols.add(symbol)
        resident_names, resident_code, resident_flags = STD._compile_resident_code(
            self.suite, self.heap
        )
        overrides = set(STD._as_list(self.suite.get("resident_overrides")))
        STD._add_code_to_directory(
            self.heap,
            self.directory,
            [name for name in resident_names if name not in overrides],
            resident_code,
            "Link-82 carrier resident suite",
        )
        self.macro_symbols.update(
            STD._macro_symbol_objs(self.heap, resident_flags)
        )
        self.code_names.update(
            {id(code): name for name, code in resident_code.items()}
        )
        self.ledger = load(ROOT / "config/bytecode-abi-ledger.json")
        self.compiler_symbol = self.heap.intern("%c2-compile-form")
        require(
            self.compiler_symbol in self.directory,
            "Link-82 carrier lacks %c2-compile-form",
        )

    def compile_traced(
        self, source: str, trace: "WindowTrace"
    ) -> dict[str, Any]:
        parsed = C.parse_one(source)
        require(
            isinstance(parsed, list)
            and len(parsed) >= 4
            and parsed[0] in ("defun", "defmacro")
            and isinstance(parsed[1], str),
            "carrier input is not one named definition",
        )
        vm = self.vm(trace)
        source_obj = vm._compiler_form_obj(parsed)
        fnlist = vm.run(self.directory[self.compiler_symbol], [source_obj])
        values = CARRIER.proper_list(self.heap, fnlist, parsed[1] + ".fnlist")
        require(len(values) == 1, f"{parsed[1]} emitted {len(values)} objects")
        code = self.decode_code(values[0], parsed[1])
        return {
            "name": parsed[1].lower(),
            "kind": parsed[0],
            "flags": 1 if parsed[0] == "defmacro" else 0,
            "code": code,
            "steps": vm.steps,
            "summary": CARRIER.code_summary(self.heap, code),
        }


@dataclass
class TraceFrame:
    name: str
    code: B.CodeObject


class WindowTrace:
    """Shadow the linked VM_CODEBUF state over an executed P0VM stream."""

    def __init__(self, lane: str, identities: dict[str, dict[str, Any]]) -> None:
        require(lane in ("windowed", "direct"), "unknown window lane")
        self.lane = lane
        self.identities = identities
        self.frames: list[TraceFrame] = []
        self.owner: int | None = None
        self.win = 0
        self.winlen = 0
        self.streaming = False
        self.instructions = 0
        self.initial_windows: list[dict[str, Any]] = []
        self.refills: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _identity(name: str, code: B.CodeObject) -> dict[str, Any]:
        encoded = code.encode()
        return {
            "name": name,
            "encoded_bytes": len(encoded),
            "encoded_sha256": sha_bytes(encoded),
            "payload_bytes": len(code.payload),
            "payload_sha256": sha_bytes(bytes(code.payload)),
            "literal_count": len(code.littab),
        }

    def _row(
        self, name: str, code: B.CodeObject, start: int, length: int, reason: str
    ) -> dict[str, Any]:
        expected = code.payload[start] if start < len(code.payload) else None
        identity = dict(self._identity(name, code))
        identity.update(self.identities.get(name, {}))
        return {
            "reason": reason,
            "object": identity,
            "payload_pc_start": start,
            "payload_pc_end_exclusive": start + length,
            "expected_first_opcode": None if expected is None else expected,
            "expected_first_opcode_hex": (
                None if expected is None else f"0x{expected:02x}"
            ),
        }

    def enter(self, name: str, code: B.CodeObject, _args: list[int]) -> None:
        self.frames.append(TraceFrame(name, code))
        header = 7 + 2 * len(code.littab)
        require(header + 3 <= VM_CODEBUF, f"{name} header exceeds VM_CODEBUF")
        capacity = VM_CODEBUF - header
        self.owner = id(code)
        self.win = 0
        self.winlen = min(len(code.payload), capacity)
        self.streaming = self.winlen < len(code.payload)
        if self.lane == "windowed":
            self.initial_windows.append(
                self._row(name, code, 0, self.winlen, "object-entry")
            )

    def exit(self, _name: str, _code: B.CodeObject) -> None:
        require(bool(self.frames), "trace frame underflow")
        self.frames.pop()

    def instruction(
        self,
        name: str,
        code: B.CodeObject,
        pc: int,
        _spec: Any,
        _operand: Any,
    ) -> None:
        self.instructions += 1
        if self.lane == "direct":
            return
        header = 7 + 2 * len(code.littab)
        capacity = VM_CODEBUF - header
        reason = None
        if self.owner != id(code):
            self.owner = id(code)
            self.win = pc
            self.winlen = 0
            self.streaming = True
            reason = "post-call-owner-restore"
        need = min(len(code.payload), pc + 3)
        if self.streaming and (pc < self.win or self.win + self.winlen < need):
            if reason is None:
                reason = "sequential-or-branch-window-edge"
            self.win = pc
            self.winlen = min(len(code.payload) - pc, capacity)
            self.refills.append(self._row(name, code, pc, self.winlen, reason))

    def call(
        self,
        caller: str,
        kind: str,
        target: str,
        argc: int,
        pc: int | None = None,
        resolved: bool = False,
    ) -> None:
        self.calls.append(
            {
                "caller": caller,
                "kind": kind,
                "target": target,
                "argc": argc,
                "pc": pc,
                "resolved": resolved,
            }
        )

    def native_frame(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def native_stack(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def report(self) -> dict[str, Any]:
        initial = compact_rows(self.initial_windows)
        refills = compact_rows(self.refills)
        return {
            "lane": self.lane,
            "instructions": self.instructions,
            "initial_window_count": len(self.initial_windows),
            "refill_count": len(self.refills),
            "initial_window_site_count": initial["site_count"],
            "refill_site_count": refills["site_count"],
            "initial_window_sequence_sha256": initial[
                "expanded_sequence_sha256"
            ],
            "refill_sequence_sha256": refills["expanded_sequence_sha256"],
            "schedule_sha256": sha_bytes(
                canonical({"initial": self.initial_windows, "refills": self.refills})
            ),
        }


def compact_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Retain every crossing as a site-id stream without repeating identity."""
    sites: list[dict[str, Any]] = []
    site_by_key: dict[bytes, int] = {}
    sequence: list[int] = []
    counts: list[int] = []
    for row in rows:
        key = canonical(row)
        site = site_by_key.get(key)
        if site is None:
            site = len(sites)
            site_by_key[key] = site
            sites.append(row)
            counts.append(0)
        sequence.append(site)
        counts[site] += 1
    runs: list[list[int]] = []
    for site in sequence:
        if runs and runs[-1][0] == site:
            runs[-1][1] += 1
        else:
            runs.append([site, 1])
    return {
        "event_count": len(rows),
        "site_count": len(sites),
        "sites": [dict(row, count=counts[index]) for index, row in enumerate(sites)],
        "sequence_rle": runs,
        "expanded_sequence_sha256": sha_bytes(canonical(sequence)),
    }


def compact_segments(
    segments: list[tuple[str, WindowTrace]], attribute: str
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    boundaries = []
    for name, trace in segments:
        part = getattr(trace, attribute)
        start = len(rows)
        rows.extend(part)
        boundaries.append(
            {
                "name": name,
                "start_event": start,
                "end_event_exclusive": len(rows),
                "event_count": len(part),
                "event_sha256": sha_bytes(canonical(part)),
            }
        )
    return {
        **compact_rows(rows),
        "segments": boundaries,
        "sha256": sha_bytes(canonical(rows)),
    }


def manifest_directory(
    heap: B.Heap,
    manifest_path: Path,
    identities: dict[str, dict[str, Any]],
    *,
    role: str,
) -> tuple[dict[int, B.CodeObject], set[int], dict[int, str]]:
    manifest = load(manifest_path)
    blob_path = ROOT / manifest["blob"]
    blob = blob_path.read_bytes()
    require(
        len(blob) == int(manifest["code_bytes"])
        and sha_bytes(blob) == manifest["blob_sha256"],
        f"{role} manifest/blob drift",
    )
    patches = {
        int(row["blob_offset"]): int(row["node"])
        for row in manifest["literal_patches"]
    }
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    names: dict[int, str] = {}
    for ordinal, entry in enumerate(manifest["entries"]):
        code = STD._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patches
        )
        symbol = heap.intern(entry["name"])
        directory[symbol] = code
        names[id(code)] = entry["name"]
        identities[entry["name"]] = {
            "role": role,
            "manifest": manifest_path.relative_to(ROOT).as_posix(),
            "manifest_entry": ordinal,
            "blob_offset": int(entry["blob_offset"]),
        }
        if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
            macros.add(symbol)
    return directory, macros, names


def install_published_libraries(
    carrier: HistoricalCarrier,
    plane: R.LivePlane,
    identities: dict[str, dict[str, Any]],
) -> tuple[dict[int, B.CodeObject], set[int], dict[int, str], list[dict[str, Any]]]:
    runtime, macros, code_names = manifest_directory(
        carrier.heap, STDLIB, identities, role="Link82-static-stdlib"
    )
    installed = []
    for library in ("place", "defstruct"):
        exact = (MEDIA_DIR / f"{library}.l65s").read_bytes()
        foundation = (FOUNDATIONS / f"{library}.l65s").read_bytes()
        require(
            len(exact) == len(foundation)
            and exact[64:] == foundation[64:],
            f"{library} product envelope changed C2I/code payload",
        )
        image = plane.images[library]
        append = next(row for row in plane.appends if row["library"] == library)
        entry_base = int(append["before"][1])
        resolution_base = int(append["before"][2])
        for local, entry in enumerate(image.manifest["entries"]):
            _raw, symbol = plane.host._sync_symbol(entry["name"])
            ordinal = entry_base + local
            plane.host.ordinal_to_symbol[ordinal] = symbol
            plane.host.raw_to_host[CARRIER.SESSION.mk_bcode(ordinal)] = symbol
        plane.host._bind_image_objects(image, resolution_base, entry_base)
        rows = []
        for local, entry in enumerate(image.manifest["entries"]):
            ordinal = entry_base + local
            snapshot = plane.host.snapshot_entry(ordinal)
            start = int(entry["blob_offset"])
            length = int(entry["length"])
            require(
                snapshot["cold_sha256"]
                == sha_bytes(image.code[start:start + length]),
                f"{library}/{entry['name']} published cold object drift",
            )
            symbol = carrier.heap.intern(entry["name"])
            runtime[symbol] = snapshot["code"]
            code_names[id(snapshot["code"])] = entry["name"]
            identities[entry["name"]] = {
                "role": f"published-{library}",
                "image_slot": append["image_slot"],
                "entry_ordinal": ordinal,
                "bank2_code_offset": snapshot["code_offset"],
                "generation": snapshot["generation"],
            }
            if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
                macros.add(symbol)
            rows.append(
                {
                    "name": entry["name"],
                    "entry_ordinal": ordinal,
                    "code_offset": snapshot["code_offset"],
                    "code_length": snapshot["code_length"],
                    "generation": snapshot["generation"],
                    "cold_sha256": snapshot["cold_sha256"],
                    "target_materialized_sha256": snapshot[
                        "target_materialized_sha256"
                    ],
                }
            )
        installed.append(
            {
                "library": library,
                "exact_envelope": bind(MEDIA_DIR / f"{library}.l65s"),
                "foundation_payload": bind(FOUNDATIONS / f"{library}.l65s"),
                "payload_from_byte_64_byteidentical": True,
                "published_image_slot": append["image_slot"],
                "entries": rows,
            }
        )
    return runtime, macros, code_names, installed


def parse_expansion(heap: B.Heap, value: int) -> tuple[str, list[Any]]:
    source = heap.obj_to_text(value)
    parsed = C.parse_one(source)
    require(
        isinstance(parsed, list)
        and parsed
        and parsed[0] == "progn"
        and len(parsed) == 12,
        "defstruct did not return the expected eleven-form expansion",
    )
    return source, parsed[1:]


def form_source(form: Any) -> str:
    # The compiler parser accepts the canonical printer spelling used by the
    # heap.  Materializing through a temporary heap avoids a second ad-hoc
    # source printer.
    heap = B.Heap()
    vm = B.P0VM(heap=heap)
    return heap.obj_to_text(vm._compiler_form_obj(form))


def compile_eval_wrapper(
    carrier: HistoricalCarrier,
    form: Any,
    index: int,
    trace: WindowTrace,
) -> dict[str, Any]:
    source = f"(defun %v16-phase-a-eval-{index} () {form_source(form)})"
    return carrier.compile_traced(source, trace)


def target_row_correction(plane: R.LivePlane, append: dict[str, Any]) -> None:
    row_at = 48 + int(append["image_slot"]) * 32
    plane.host.plane.c2d[row_at + 2] = int(append["image_slot"]) - 6
    struct.pack_into("<H", plane.host.plane.c2d, 8, 4096)


def sequence(
    lane: str,
    *,
    require_only: bool = False,
    suppress_generated_append: str | None = None,
) -> dict[str, Any]:
    geom = configure_resolver()
    carrier = HistoricalCarrier()
    identities: dict[str, dict[str, Any]] = {}
    for ordinal, entry in enumerate(carrier.manifest["entries"]):
        identities[entry["name"]] = {
            "role": "Link82-bound-compiler-carrier",
            "manifest_entry": ordinal,
            "blob_offset": int(entry["blob_offset"]),
        }
    plane = R.LivePlane()
    CARRIER.attach_heap(plane.host, carrier.heap)
    media = MEDIA.read_bytes()
    locators, payloads = R.media_locators(media)
    decoded = L65I.decode_index(
        payloads["l65index"],
        {"place": payloads["place"], "defstruct": payloads["defstruct"]},
        artifact_build_id=geom["build_id"],
    )
    require(
        L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY) == [0, 1],
        "exact Link-82 medium does not resolve place -> defstruct",
    )
    bound = R.BoundStdlib()
    resolver_trace = WindowTrace(lane, identities)
    vm = R.ResolverVM(bound, plane, media, locators)
    # The resolver heap differs from the carrier/runtime heap, so its exact
    # object trace has a separate registry but the same window algorithm.
    resolver_trace.identities.update(
        {
            entry["name"]: {
                "role": "Link82-static-stdlib-resolver",
                "manifest_entry": ordinal,
                "blob_offset": int(entry["blob_offset"]),
            }
            for ordinal, entry in enumerate(bound.manifest["entries"])
        }
    )
    vm.trace = resolver_trace
    result = vm.run(
        bound.directory[bound.require_symbol], [bound.heap.intern("defstruct")]
    )
    require(bound.heap.obj_to_text(result) == "t", "exact require returned non-t")
    require(
        [row["library"] for row in plane.appends] == ["place", "defstruct"]
        and len(vm.prim67_reads) > 0,
        "real resolver did not publish place then defstruct through Prim 67",
    )
    require_row = {
        "result": "t",
        "steps": vm.steps,
        "prim67_reads": len(vm.prim67_reads),
        "disk_sector_reads": vm.io_counters["disk_read"],
        "appends": list(plane.appends),
        "window_trace": resolver_trace.report(),
    }
    if require_only:
        return {
            "lane": lane,
            "require": require_row,
            "final_counts": {
                "images": plane.host.plane.images,
                "entries": plane.host.plane.entries,
                "resolutions": plane.host.plane.resolutions,
                "roots": plane.host.plane.roots,
                "code_bytes": plane.host.plane.code_low,
            },
        }

    runtime, macros, code_names, installed = install_published_libraries(
        carrier, plane, identities
    )
    plane.host.directory = runtime
    plane.host.code_names = code_names
    macro_trace = WindowTrace(lane, identities)
    runtime_vm = B.P0VM(
        heap=carrier.heap,
        directory=runtime,
        macro_symbols=macros,
        max_steps=10_000_000,
        max_call_args=12,
        trace=macro_trace,
        code_names=code_names,
        abi_profile="dialect-v2",
        abi_ledger=carrier.ledger,
    )
    expansion_obj = runtime_vm.run(
        runtime[carrier.heap.intern("defstruct")],
        [
            carrier.heap.intern("point"),
            carrier.heap.intern("x"),
            carrier.heap.intern("y"),
        ],
    )
    expansion_source, forms = parse_expansion(carrier.heap, expansion_obj)
    expansion = {
        "input": "(defstruct point x y)",
        "expanded_source": expansion_source,
        "expanded_source_sha256": sha_bytes(expansion_source.encode("utf-8")),
        "steps": runtime_vm.steps,
        "window_trace": macro_trace.report(),
    }

    form_rows = []
    form_trace_segments: list[tuple[str, WindowTrace]] = []
    last_definition = None
    journal = "CLEAR"
    for index, form in enumerate(forms):
        source = form_source(form)
        compile_trace = WindowTrace(lane, identities)
        form_trace_segments.append((f"form-{index}-compile", compile_trace))
        if isinstance(form, list) and form and form[0] == "defun":
            compiled = carrier.compile_traced(source, compile_trace)
            identities[compiled["name"]] = {
                "role": "defstruct-generated-session-definition",
                "expanded_form_index": index,
            }
            before = {
                "image": plane.host.plane.images,
                "entry": plane.host.plane.entries,
                "generation": plane.host.plane.generation,
                "journal": journal,
            }
            if compiled["name"] == suppress_generated_append:
                form_rows.append(
                    {
                        "index": index,
                        "kind": "suppressed-persistent-definition-mutation",
                        "source": source,
                        "source_sha256": sha_bytes(source.encode("utf-8")),
                        "suppressed_entry": compiled["name"],
                    }
                )
                continue
            transitions = ["CLEAR", "PREPARED", "ACTIVE", "CLEAR"]
            append = plane.host.append_compiled_definition(
                source,
                compiled["name"],
                compiled["code"],
                compiler_authority=EXPECTED_CARRIER_SHA,
            )
            target_row_correction(plane, append)
            journal = "CLEAR"
            last_definition = compiled["name"]
            row = {
                "index": index,
                "kind": "persistent-definition",
                "source": source,
                "source_sha256": sha_bytes(source.encode("utf-8")),
                "entry": compiled["name"],
                "compiler_steps": compiled["steps"],
                "code": compiled["summary"],
                "compile_window_trace": compile_trace.report(),
                "append": {
                    "before": before,
                    "after": {
                        "image": plane.host.plane.images,
                        "entry": plane.host.plane.entries,
                        "generation": plane.host.plane.generation,
                        "journal": journal,
                    },
                    "image_slot": append["image_slot"],
                    "handle": append["handle"],
                    "materialized": append["materialized"],
                    "C2J_transition": transitions,
                    "C2J_authority": (
                        "target-contract shadow; ProductSessionHost owns C2D/code "
                        "bytes but not physical Bank-5 C2J"
                    ),
                },
            }
        else:
            compiled = compile_eval_wrapper(carrier, form, index, compile_trace)
            runtime[carrier.heap.intern(compiled["name"])] = compiled["code"]
            code_names[id(compiled["code"])] = compiled["name"]
            identities[compiled["name"]] = {
                "role": "defstruct-expansion-evaluator",
                "expanded_form_index": index,
            }
            eval_trace = WindowTrace(lane, identities)
            form_trace_segments.append((f"form-{index}-evaluate", eval_trace))
            eval_vm = B.P0VM(
                heap=carrier.heap,
                directory=runtime,
                macro_symbols=macros,
                max_steps=10_000_000,
                max_call_args=12,
                trace=eval_trace,
                code_names=code_names,
                abi_profile="dialect-v2",
                abi_ledger=carrier.ledger,
            )
            eval_result = eval_vm.run(compiled["code"], [])
            row = {
                "index": index,
                "kind": "evaluated-expression",
                "source": source,
                "source_sha256": sha_bytes(source.encode("utf-8")),
                "result": carrier.heap.obj_to_text(eval_result),
                "compiler_steps": compiled["steps"],
                "evaluation_steps": eval_vm.steps,
                "code": compiled["summary"],
                "compile_window_trace": compile_trace.report(),
                "evaluation_window_trace": eval_trace.report(),
            }
        form_rows.append(row)

    constructor_trace = WindowTrace(lane, identities)
    constructor_vm = B.P0VM(
        heap=carrier.heap,
        directory=runtime,
        macro_symbols=macros,
        max_steps=1_000_000,
        max_call_args=12,
        trace=constructor_trace,
        code_names=code_names,
        abi_profile="dialect-v2",
        abi_ledger=carrier.ledger,
    )
    constructor = constructor_vm.run(
        runtime[carrier.heap.intern("make-point")], [B.mkfix(3), B.mkfix(4)]
    )
    constructor_text = carrier.heap.obj_to_text(constructor)
    require(
        constructor_text == "(point 3 4)"
        and last_definition == "point-with-y"
        and [row["entry"] for row in form_rows if "entry" in row]
        == [
            "make-point",
            "point-p",
            "copy-point",
            "point-x",
            "point-set-x",
            "point-with-x",
            "point-y",
            "point-set-y",
            "point-with-y",
        ]
        and form_rows[0]["result"] == "t"
        and form_rows[-1]["result"] == "t",
        "actual defstruct expansion/append semantics drift",
    )
    # Preserve the executed chronology.  The aggregate below is the one
    # lossless event stream in the receipt; per-form reports carry counts and
    # hashes only, avoiding repeated object identities.
    trace_segments = [
        ("require-resolver", resolver_trace),
        ("defstruct-macro-expansion", macro_trace),
        *form_trace_segments,
        ("constructor-control", constructor_trace),
    ]
    initial_windows = compact_segments(trace_segments, "initial_windows")
    refills = compact_segments(trace_segments, "refills")
    return {
        "lane": lane,
        "require": require_row,
        "installed_libraries": installed,
        "expansion": expansion,
        "forms": form_rows,
        "last_successful_definition": last_definition,
        "constructor": {
            "form": "(make-point 3 4)",
            "result": constructor_text,
            "steps": constructor_vm.steps,
            "window_trace": constructor_trace.report(),
        },
        "initial_window_schedule": initial_windows,
        "refill_schedule": {
            "count": refills["event_count"],
            **refills,
        },
        "final_counts": {
            "images": plane.host.plane.images,
            "entries": plane.host.plane.entries,
            "resolutions": plane.host.plane.resolutions,
            "roots": plane.host.plane.roots,
            "code_bytes": plane.host.plane.code_low,
            "C2J": journal,
        },
    }


def wrong_media_mutation() -> dict[str, Any]:
    configure_resolver()
    data = bytearray(MEDIA.read_bytes())
    data[L65I.D81.sector_offset(39, 0) + 2] ^= 1
    bound = R.BoundStdlib()
    plane = R.LivePlane()
    locators, _payloads = R.media_locators(bytes(data))
    vm = R.ResolverVM(bound, plane, bytes(data), locators)
    result = vm.run(
        bound.directory[bound.require_symbol], [bound.heap.intern("defstruct")]
    )
    require(bound.heap.obj_to_text(result) == "nil", "wrong medium survived")
    return {"result": "nil", "mutation": "L65INDEX magic byte"}


def suppress_append_mutation() -> dict[str, Any]:
    suppressed = "point-set-y"
    try:
        sequence("windowed", suppress_generated_append=suppressed)
    except PhaseAError as error:
        require(
            "actual defstruct expansion/append semantics drift" in str(error),
            f"one-append mutation failed for wrong reason: {error}",
        )
        return {
            "result": "rejected",
            "suppressed_generated_persistent_append": suppressed,
        }
    raise PhaseAError("one suppressed generated append survived")


def omitted_require_mutation() -> dict[str, Any]:
    carrier = HistoricalCarrier()
    runtime, macros, code_names = manifest_directory(
        carrier.heap, STDLIB, {}, role="Link82-static-stdlib"
    )
    vm = B.P0VM(
        heap=carrier.heap,
        directory=runtime,
        macro_symbols=macros,
        code_names=code_names,
        abi_profile="dialect-v2",
        abi_ledger=carrier.ledger,
    )
    try:
        vm._invoke_function(
            carrier.heap.intern("defstruct"),
            [
                carrier.heap.intern("point"),
                carrier.heap.intern("x"),
                carrier.heap.intern("y"),
            ],
        )
    except B.VMError as error:
        require(error.status == "DirMiss", "omit-require failed for wrong reason")
        return {"result": "DirMiss", "library_entries_installed": 0}
    raise PhaseAError("defstruct survived omitted prior require")


def comparable(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "require_result": result["require"]["result"],
        "expanded_source_sha256": result["expansion"]["expanded_source_sha256"],
        "forms": [
            {
                "kind": row["kind"],
                "entry": row.get("entry"),
                "source_sha256": row["source_sha256"],
                "code_semantic_sha256": row["code"]["semantic_sha256"],
                "result": row.get("result"),
            }
            for row in result["forms"]
        ],
        "constructor": result["constructor"]["result"],
        "final_counts": result["final_counts"],
    }


def build_receipt() -> dict[str, Any]:
    geom = configure_resolver()
    link = load(LINK82)
    quiet = load(QUIET_FIRST_RED)
    require(
        link["qualifying_candidate"]["link"] == 82
        and link["qualifying_candidate"]["product_build_id"] == "0x270030c3"
        and quiet["source_commit"] == EXPECTED_SOURCE_COMMIT
        and bind(MEDIA)["sha256"] == EXPECTED_MEDIA_SHA,
        "quiet Link-82 diagnosis authority drift",
    )
    require_control = sequence("windowed", require_only=True)
    windowed = sequence("windowed")
    direct = sequence("direct")
    require(
        comparable(windowed) == comparable(direct),
        "windowed/direct host lanes differ semantically",
    )
    require(
        windowed["refill_schedule"]["count"] > 0
        and direct["refill_schedule"]["count"] == 0,
        "real expansion did not discriminate windowed/direct lanes",
    )
    mutations = {
        "omit-prior-require": omitted_require_mutation(),
        "wrong-library-medium": wrong_media_mutation(),
        "suppress-persistent-append": suppress_append_mutation(),
    }
    flattened = json.loads(json.dumps(windowed["refill_schedule"]))
    flattened["count"] = 0
    flattened["event_count"] = 0
    flattened["site_count"] = 0
    flattened["sites"] = []
    flattened["sequence_rle"] = []
    try:
        require(flattened["count"] > 0, "flattened window schedule")
    except PhaseAError:
        mutations["silently-flatten-windowed-lane"] = {
            "result": "rejected",
            "baseline_refills": windowed["refill_schedule"]["count"],
        }
    else:
        raise PhaseAError("flattened window lane survived")

    crossing_names = sorted(
        {
            row["object"]["name"]
            for row in windowed["refill_schedule"]["sites"]
        }
    )
    defstruct_names = {
        "defstruct",
        "%defstruct-symbol",
        "%defstruct-slot-symbol",
        "%defstruct-member",
        "%defstruct-slots-valid-p",
        "%defstruct-names-free-p",
        "%defstruct-slot-names",
        "%defstruct-generated-names",
        "%defstruct-constructor-form",
        "%defstruct-predicate-form",
        "%defstruct-copy-form",
        "%defstruct-update-values",
        "%defstruct-one-slot-forms",
        "%defstruct-slot-forms",
        "%defstruct-register-forms",
        "%defstruct-expansion",
    }
    expansion_crossings = sorted(set(crossing_names) & defstruct_names)
    require(expansion_crossings, "actual defstruct expansion crossed no window")
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": (
            "passed-exact-Link82-real-require-and-defstruct-expansion-"
            "host-reconstruction"
        ),
        "promotable": False,
        "product_delta_bytes": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "base": {
            "release": "v1.2.5",
            "link": 82,
            "source_commit": EXPECTED_SOURCE_COMMIT,
            "geometry": geom,
            "media_sha256": EXPECTED_MEDIA_SHA,
        },
        "require_only_control": require_control,
        "windowed_sequence": windowed,
        "direct_memory_control": {
            "semantic_projection": comparable(direct),
            "refill_schedule": direct["refill_schedule"],
        },
        "lane_equivalence": {
            "semantic_projection_byteidentical": True,
            "projection_sha256": sha_bytes(canonical(comparable(windowed))),
            "windowed_refills": windowed["refill_schedule"]["count"],
            "direct_refills": 0,
        },
        "mutations_rejected": mutations,
        "refill_hypothesis": {
            "membership_retained_for_Phase_B": True,
            "reason": "the actual macro expansion crosses VM_CODEBUF boundaries",
            "defstruct_objects_with_refills": expansion_crossings,
            "all_objects_with_refills": crossing_names,
            "expected_opcode_oracle": (
                "bound CodeObject payload byte at the post-refill cursor; "
                "never submit-return or completion metadata"
            ),
        },
        "historical_receipt_disposition": {
            "Link75_append_model": "input-not-authority",
            "replacement": (
                "real Link82 require with Prim-67 and exact D81, followed by "
                "actual macro execution and nine generated persistent appends"
            ),
        },
        "authority": {
            "Link82": bind(LINK82),
            "quiet_first_red": bind(QUIET_FIRST_RED),
            "plan": bind(PLAN),
            "VM_window_source": bind_git("src/vm.c"),
            "Link82_runtime_profile": bind_git("config/runtime-core.mk"),
            "gate_wiring": bind(GATES),
            "bound_parity": bind(BOUND_PARITY),
            "stdlib": bind(STDLIB),
            "static_c2d": bind(STATIC_C2D),
            "static_bank2": bind(STATIC_CODE),
            "compiler_carrier": bind(COMPILER_MANIFEST),
            "compiler_tier": bind(COMPILER_TIER),
            "library_medium": bind(MEDIA),
            "library_index": bind(MEDIA_DIR / "l65index"),
            "place_L65S": bind(MEDIA_DIR / "place.l65s"),
            "defstruct_L65S": bind(MEDIA_DIR / "defstruct.l65s"),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "The exact Link-82 Lisp resolver, exact product-bound D81, bound "
            "compiler carrier, macro objects and C2D-v6 append model execute "
            "on the host. WindowTrace is an instruction-exact shadow of the "
            "linked VM_CODEBUF=56 state machine, not physical F018B DMA. C2J "
            "rows are target-contract shadows because ProductSessionHost does "
            "not execute physical Bank-5 journal writes. This receipt retains "
            "the refill hypothesis for Phase B but makes no target-failure, "
            "hardware, fix or product-byte claim."
        ),
        "next_gate": (
            "Phase B must partition every statically reachable fail-closed edge "
            "and derive dispatcher expected bytes from this refill schedule."
        ),
    }
    return value


def verify_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value.get("format") == FORMAT, "Phase-A receipt format drift")
    for label, row in value["authority"].items():
        current = (
            bind_git(row["path"])
            if row.get("authority") == "git-blob"
            else bind(ROOT / row["path"])
        )
        require(current == row, f"Phase-A authority drift: {label}")
    require(
        value["status"]
        == (
            "passed-exact-Link82-real-require-and-defstruct-expansion-"
            "host-reconstruction"
        )
        and value["windowed_sequence"]["last_successful_definition"]
        == "point-with-y"
        and value["windowed_sequence"]["constructor"]["result"]
        == "(point 3 4)"
        and value["refill_hypothesis"]["membership_retained_for_Phase_B"]
        and len(value["mutations_rejected"]) == 4,
        "Phase-A bound conclusions drift",
    )
    current = build_receipt()
    require(
        value == current,
        "Phase-A receipt is not the exact current execution result; "
        "run action required",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    validate_window_authority()
    if args.action == "selftest":
        require(VM_CODEBUF == 56 and geometry()["entries"] == 725, "selftest drift")
        print(
            "c2-v16-defstruct-phase-a: SELFTEST PASS "
            "vm-codebuf=56 Link82-entries=725"
        )
        return 0
    if args.action == "run":
        value = build_receipt()
        write_json(RECEIPT, value)
    else:
        value = verify_receipt()
    print(
        "c2-v16-defstruct-phase-a: PASS "
        f"prim67={value['windowed_sequence']['require']['prim67_reads']} "
        f"forms={len(value['windowed_sequence']['forms'])} "
        f"appends={sum('entry' in row for row in value['windowed_sequence']['forms'])} "
        f"refills={value['windowed_sequence']['refill_schedule']['count']} "
        "mutations=4"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        PhaseAError,
        B.VMError,
        CARRIER.AttributionError,
        R.ResolverError,
        L65I.GateError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"c2-v16-defstruct-phase-a: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
