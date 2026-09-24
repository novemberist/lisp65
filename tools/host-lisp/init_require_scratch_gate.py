#!/usr/bin/env python3
"""Host gate: `require` inside a disk-loaded source (INIT.L65) and the DIR scratch.

The native source loader (src/io.c: io_disk_load_chain / disk_source_fetch)
parks the current sector of the source file in the 256-byte DIR scratch and
feeds the reader from it.  Every %disk-read-sector (require's index reader,
load, load-lib, IDE, M65D, FASL) writes the same scratch.  This gate executes
the live compiled require/L65I Lisp against a host D81 sector model while a
Python mirror of the native loader streams INIT.L65 form by form:

  two-owner     unrepaired io.c: the loader trusts the scratch between fetches
                (failing regression control);
  owner-token   this branch's io.c: every scratch write clears the stream's
                owner bit and the next fetch re-reads its parked sector;
  whole-buffer  form B with a private whole-file buffer;
  file-window   form B inside the existing DISK_EXT_FILE window, which
                %disk-load-lib staging reuses (priced as not viable).

Fixtures (instrumented callees), stated plainly: %require-world,
%require-run-plan, %require-fast-note and %require-fast-loaded-p replace the
C2D/Prim-67 plane with a host loaded-name list; Prim 18 (two-argument
locator form) installs the library by compiling its lib/ source into the
live heap. The D81 model now supports general locators; this gate's subclass
additionally executes source forms between loader fetches. That interleaving
is a fixture, not execution of the native loader. The companion
init_repair_host_gate executes the actual C fetch/refill components.
No product build, link, media or device.
"""
from __future__ import annotations

import hashlib
import json
import ctypes
from functools import lru_cache
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_stdlib as P  # noqa: E402
import c2_require_resolver_gate as G  # noqa: E402

B = P.B
C = P.C

SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
REQUIRE = ROOT / "lib/stdlib-require.lisp"
FIXTURE = ROOT / "tests/fixtures/init-l65/INIT.L65"
IO_SOURCE = ROOT / "src/io.c"
LIBS = {
    "place": ROOT / "lib/stdlib-places.lisp",
    "string-extra": ROOT / "lib/comfort-strings.lisp",
}
FIXTURE_TEXT = '(require "place")\n(require "string-extra")\n'

VALID = 0x8000
OWNS = 0x4000
INIT_T = 17
INDEX_TS = (18, 34)
LIB_TS = {"place": (19, 0), "string-extra": (19, 1)}
TAIL_TS = (20, 0)

HOST_FIXTURES = (
    "(defun %require-world (rows) (list 'state 'code-low 'fronts))",
    "(defun %require-run-plan (ordinal rows lock state fronts code-low)"
    " (let ((row (nth ordinal rows)))"
    " (%disk-load-lib (nth 2 row) (nth 3 row))))",
    "(defun %require-host-member (x xs)"
    " (if xs (if (string= x (car xs)) t (%require-host-member x (cdr xs))) nil))",
    "(defun %require-fast-note (library row lock rows previous)"
    " (set-symbol-value '*require-fast*"
    " (cons library (symbol-value '*require-fast*))) t)",
    "(defun %require-fast-loaded-p (library)"
    " (%require-host-member library (symbol-value '*require-fast*)))",
)


class GateError(RuntimeError):
    pass


def check(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def pack(track: int, sector: int) -> int:
    return VALID | (track << 6) | sector


def unpack(link: int) -> tuple[int, int]:
    return (link >> 6) & 0x7F, link & 0x3F


def chain_count(t: int, s: int, nt: int, ns: int) -> int:
    """src/io.c disk_chain_count."""
    if not nt:
        return 255 if not ns else ns - 1
    if nt > 80 or ns > 39 or (nt == t and ns == s):
        return 255
    return 254


def file_sectors(first: tuple[int, int], payload: bytes) -> dict:
    chunks = [payload[i:i + 254] for i in range(0, len(payload), 254)] or [b""]
    out = {}
    t, s = first
    for index, chunk in enumerate(chunks):
        if index + 1 < len(chunks):
            head = bytes((t, s + 1))
        else:
            head = bytes((0, len(chunk) + 1))
        out[(t, s)] = (head + chunk).ljust(256, b"\0")
        s += 1
    return out


def build_disk(init_text: str, tail_text: str | None = None) -> dict:
    records = [dict(name=name, track=ts[0], sector=ts[1],
                    combined_crc32=i + 1, dependencies=[],
                    execution_source=2, artifact_bytes=512, bank2=16,
                    images=1, entries=1, resolutions=1, roots=1, scratch=8)
               for i, (name, ts) in enumerate(LIB_TS.items())]
    index = G.encode_index(records)
    G.decode_index(index)
    directory = bytearray(256)
    directory[1] = 255
    files = [("INIT.L65", (INIT_T, 0)), ("L65INDEX", INDEX_TS),
             ("PLACE", LIB_TS["place"]),
             ("STRING-EXTRA", LIB_TS["string-extra"])]
    if tail_text is not None:
        files.append(("TAIL.L65", TAIL_TS))
    for entry, (name, (t, s)) in enumerate(files):
        base = entry * 32
        directory[base + 2:base + 5] = bytes((0x82, t, s))
        directory[base + 5:base + 21] = name.encode().ljust(16, b"\xa0")
    sectors = {(40, 3): bytes(directory)}
    sectors.update(file_sectors((INIT_T, 0), init_text.encode("ascii")))
    sectors.update(file_sectors(INDEX_TS, index))
    for name, ts in LIB_TS.items():
        sectors.update(file_sectors(ts, b"L65S" + name.encode()))
    if tail_text is not None:
        sectors.update(file_sectors(TAIL_TS, tail_text.encode("ascii")))
    return sectors


class UnclosedList(Exception):
    pass


class Stream:
    def __init__(self, fetch):
        self.fetch = fetch
        self.peeked = None

    def peek(self) -> str:
        if self.peeked is None:
            self.peeked = self.fetch()
        return self.peeked

    def take(self) -> str:
        c = self.peek()
        self.peeked = None
        return c


def read_top_form(stream: Stream) -> str | None:
    """Top-level form reader over the fetch stream (native READER shape)."""
    while True:
        c = stream.peek()
        if c in " \t\r\n":
            stream.take()
            continue
        if c == ";":
            while stream.peek() not in ("\n", "\0"):
                stream.take()
            continue
        break
    if stream.peek() == "\0":
        return None
    out: list[str] = []
    depth = 0
    in_string = False
    while True:
        c = stream.peek()
        if c == "\0":
            if depth or in_string:
                raise UnclosedList()
            break
        if in_string:
            out.append(stream.take())
            if c == "\\":
                out.append(stream.take())
            elif c == '"':
                in_string = False
            continue
        if c == ";" and depth:
            while stream.peek() not in ("\n", "\0"):
                stream.take()
            continue
        if c in " \t\r\n" and depth == 0:
            break
        out.append(stream.take())
        if c == '"':
            in_string = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
    return "".join(out)


class NativeSourceLoader:
    """Mirror of io_disk_load_chain/disk_source_fetch; one global instance."""

    def __init__(self, vm: "DiskVM", mode: str) -> None:
        self.vm = vm
        self.mode = mode
        self.file_len = self.file_pos = self.link = self.cur = 0
        self.file_window = bytearray()
        self.private = b""

    def chain_to_scratch(self, t: int, s: int) -> bytes | None:
        out = bytearray()
        while t:
            raw = self.vm.disk.get((t, s))
            if raw is None:
                return None
            nt, ns = raw[0], raw[1]
            count = chain_count(t, s, nt, ns)
            if count > 254:
                return None
            out.extend(raw[2:2 + count])
            t, s = nt, ns
        return bytes(out)

    def read(self, t: int, s: int) -> bool:
        # io_disk_read_sector(_link_far) clears the owner bit first.
        return self.vm._disk_read_sector_impl(t, s)

    def load_chain(self, t: int, s: int) -> bool:
        payload = self.chain_to_scratch(t, s)
        if not payload:
            return False
        self.file_window = bytearray(payload)       # DISK_EXT_FILE staging
        self.file_len, self.file_pos = len(payload), 0
        if self.mode == "two-owner":
            if not self.read(t, s):
                return False
            buf = self.vm.disk_buf
            if chain_count(t, s, buf[0], buf[1]) > 254:
                return False
            self.link = pack(buf[0], buf[1] if buf[0] else 0)
        else:
            self.link, self.cur = pack(t, s), 0
        self.private = bytes(payload)
        self.vm.disk_source_active = True
        try:
            self.vm.load_source_stream(self.fetch)
        finally:
            self.vm.disk_source_active = False
        if self.mode in ("whole-buffer", "file-window"):
            return True
        return bool(self.link & VALID)

    def fetch(self) -> str:
        if self.file_pos >= self.file_len:
            return "\0"
        if self.mode in ("whole-buffer", "file-window"):
            source = self.private if self.mode == "whole-buffer" else self.file_window
            c = source[self.file_pos]
            self.file_pos += 1
            return chr(c)
        folded = (self.file_pos & 0xFF) + ((self.file_pos >> 8) << 1)
        while folded >= 254:
            folded -= 254
        if self.mode == "two-owner":
            refill = self.file_pos and not folded
            target = self.link
        else:
            if self.file_pos and not folded:
                self.cur = 0
            refill = not (self.cur & OWNS)
            target = self.cur if self.cur & VALID else self.link
        if refill:
            t, s = unpack(target)
            if not (target & VALID) or not t or not self.read(t, s):
                self.link = 0
                return "\0"
            buf = self.vm.disk_buf
            if chain_count(t, s, buf[0], buf[1]) > 254:
                self.link = 0
                return "\0"
            self.link = pack(buf[0], buf[1] if buf[0] else 0)
            if self.mode == "owner-token":
                self.cur = target | OWNS
        self.file_pos += 1
        return chr(self.vm.disk_buf[2 + folded])


class DiskVM(B.P0VM):
    def setup(self, disk: dict, mode: str, abi, ledger) -> None:
        self.disk = disk
        self.abi, self.ledger = abi, ledger
        self.loader = NativeSourceLoader(self, mode)
        self.reads: list[tuple[int, int]] = []
        self.loaded: list[str] = []
        self.transcript: list[dict] = []
        self.locators = {ts: name for name, ts in LIB_TS.items()}
        # This source-stream fixture owns no transient code. Derive its empty
        # handle front and capacity query from the actual native owner, rather
        # than silently returning zero through the reference VM's old seam.
        self.owner_native = source_owner_model()
        self.owner_header = bytearray(28)
        self.owner_header[:8] = b'C2D\0\6\x30\x20\x0a'
        def word(at, value):
            self.owner_header[at:at+2] = value.to_bytes(2, 'little')
        word(8, self.owner_native.expected_owner(6)); word(10, 1); word(12, 6)
        for field in range(1, 5):
            word(10 + 4 * field, self.owner_native.expected_owner(field))

    def _disk_read_sector_impl(self, track, sector):
        self.loader.cur &= ~OWNS
        self.reads.append((track, sector))
        raw = self.disk.get((track, sector))
        self.disk_buf = list(raw) if raw is not None else [0] * 256
        return raw is not None

    def install(self, name: str) -> None:
        heap = self.heap
        for form in C.parse_all(LIBS[name].read_text(encoding="utf-8")):
            check(isinstance(form, list) and form[0] in ("defun", "defmacro"),
                  f"{name}: unmodelled top-level form {form!r:.60}")
            fn, code, helpers = C.compile_top_form_with_helpers(
                ["defun", *form[1:]], heap, strict_arity=True,
                abi_profile=self.abi, abi_ledger=self.ledger)
            for helper_name, helper in [(fn, code), *helpers]:
                symbol = heap.intern(helper_name)
                self.directory[symbol] = helper
                self.function_cells[B.to_i16(symbol)] = B.to_i16(symbol)
            if form[0] == "defmacro":
                self.macro_symbols.add(heap.intern(fn))

    def _callprim(self, prim_id, argc, stack, pc=None, native_base=0,
                  frame_slots=0):
        if prim_id == 67:
            args = self._pop_args(argc, stack)
            if argc not in (1, 2) or not all(B.is_fix(a) and 0 <= B.fixval(a) <= 255 for a in args):
                raise B.VMError('TypeError', 'product owner byte domain')
            if argc == 1:
                self.owner_native.set_header(ctypes.create_string_buffer(bytes(self.owner_header)))
                value = self.owner_native.c2_resolver_owner_part(B.fixval(args[0]))
                return B.NIL if value == 65535 else B.mkfix(value)
            at = B.fixval(args[0]) + 256 * B.fixval(args[1])
            check(at < len(self.owner_header), 'source fixture reached an unmodelled C2D row')
            return B.mkfix(self.owner_header[at])
        if prim_id == 18 and argc == 0:
            return super()._callprim(prim_id, argc, stack, pc, native_base,
                                     frame_slots)
        if prim_id not in (17, 18, 21):
            return super()._callprim(prim_id, argc, stack, pc, native_base,
                                     frame_slots)
        self._check_argc(argc, "CALLPRIM")
        args = self._pop_args(argc, stack)
        if prim_id == 21:                         # %disk-poke
            self.loader.cur &= ~OWNS
            self.disk_buf[B.fixval(args[0]) & 0xFF] = B.fixval(args[1]) & 0xFF
            return args[1]
        if prim_id == 18 and argc == 1:           # no reset-persistent shelf
            return B.NIL
        locator = tuple(B.fixval(a) for a in args)
        if prim_id == 17:                          # %disk-load-file
            return self.heap.t_obj if self.loader.load_chain(*locator) else B.NIL
        name = self.locators.get(locator)
        if name is None:
            return B.NIL
        # Product: io_disk_stage_chain stages the L65S into DISK_EXT_FILE.
        staged = (b"L65S-" + name.encode()) * 64
        self.loader.file_window[:len(staged)] = staged
        self.install(name)
        self.loaded.append(name)
        return self.heap.t_obj

    def evaluate(self, text: str):
        form = C.parse_one(text)
        if isinstance(form, list) and form and form[0] == "defun":
            self.install_form(form)
            return form[1]
        _, code, helpers = C.compile_top_form_with_helpers(
            ["lambda", [], form], self.heap, strict_arity=True,
            abi_profile=self.abi, abi_ledger=self.ledger)
        for helper_name, helper in helpers:
            symbol = self.heap.intern(helper_name)
            self.directory[symbol] = helper
            self.function_cells[B.to_i16(symbol)] = B.to_i16(symbol)
        return self.heap.obj_to_text(self.run(code, []))

    def install_form(self, form) -> None:
        fn, code, helpers = C.compile_top_form_with_helpers(
            form, self.heap, strict_arity=True, abi_profile=self.abi,
            abi_ledger=self.ledger)
        for helper_name, helper in [(fn, code), *helpers]:
            symbol = self.heap.intern(helper_name)
            self.directory[symbol] = helper
            self.function_cells[B.to_i16(symbol)] = B.to_i16(symbol)

    def load_source_stream(self, fetch) -> None:
        """compile_repl.c load_source_stream: read, evaluate, stop on error."""
        stream = Stream(fetch)
        while True:
            try:
                text = read_top_form(stream)
            except UnclosedList:
                self.transcript.append({"reader": "READER: UNCLOSED LIST"})
                return
            if text is None:
                return
            try:
                value = self.evaluate(text)
            except (B.VMError, C.CompileError) as error:
                self.transcript.append({"form": text, "error": str(error)[:120]})
                return
            self.transcript.append({"form": text, "value": value})


@lru_cache(maxsize=1)
def source_owner_model():
    import resolver_owner_gate as OWNER
    return OWNER.build(ROOT / 'build/init-require-owner-fixture')


class World:
    def __init__(self) -> None:
        suite = P._read_suite(str(SUITE))
        suite["cases"] = [dict(name="compile-only", expr="(%l65i-parse)",
                               expect="nil")]
        self.heap, _, _, _, _, _, self.directory, _, _, _ = P._compile_suite(suite)
        self.abi, self.ledger = P._suite_abi(suite)
        for text in HOST_FIXTURES:
            fn, code, helpers = C.compile_top_form_with_helpers(
                C.parse_one(text), self.heap, strict_arity=True,
                abi_profile=self.abi, abi_ledger=self.ledger)
            check(not helpers, f"fixture helper: {fn}")
            self.directory[self.heap.intern(fn)] = code

    def vm(self, disk: dict, mode: str) -> DiskVM:
        heap = self.heap.clone()
        vm = DiskVM(heap=heap, directory=dict(self.directory),
                    abi_profile=self.abi, abi_ledger=self.ledger,
                    max_steps=50_000_000)
        vm.setup(disk, mode, self.abi, self.ledger)
        for name in ("*require-fast*", "*require-index-lock*"):
            heap.set_symbol_value(heap.intern(name), B.NIL)
        return vm


def multi_sector_init() -> str:
    """Fixture forms, a sector boundary inside the second require, a tail."""
    first = '(require "place")\n'
    filler = ";" + "-" * (254 - len(first) - 12) + "\n"
    second = '(require "string-extra")\n'
    tail = (
        "; the rest of INIT still evaluates after both packages\n"
        "(defun init-tail-probe ()\n"
        "  (list (capitalize \"abc\")\n"
        "        (%setf-expand 'x 5)\n"
        "        (%setf-expand 'x (list 'cons 0 'x))))\n"
        "(set-symbol-value '*init-tail* (init-tail-probe))\n"
        "(set-symbol-value '*init-end* 42)\n"
    )
    text = first + filler + second + ";" + "=" * 230 + "\n" + tail
    boundary = len(first) + len(filler)
    check(boundary < 254 < boundary + len(second),
          "second require does not straddle the first sector boundary")
    check(len(text) > 2 * 254, "INIT does not span three sectors")
    return text


def run_init(world: World, text: str, mode: str) -> dict:
    vm = world.vm(build_disk(text), mode)
    loaded = vm.evaluate('(load "init.l65")')
    heap = vm.heap
    tail = heap.obj_to_text(heap.symbol_value(heap.intern("*init-tail*")))
    end = heap.obj_to_text(heap.symbol_value(heap.intern("*init-end*")))
    row = {"mode": mode, "load": loaded, "loaded": vm.loaded,
           "transcript": vm.transcript, "init_tail": tail, "init_end": end,
           "sector_reads": len(vm.reads)}
    bound = {}
    for name in ("setf", "push", "capitalize"):
        symbol = heap.intern(name)
        bound[name] = symbol in vm.directory
    row["bound"] = bound
    if bound["setf"] and bound["push"]:
        x = heap.intern("x")
        row["setf_expansion"] = heap.obj_to_text(
            vm.run(vm.directory[heap.intern("setf")], [x, B.mkfix(5)]))
        row["push_expansion"] = heap.obj_to_text(
            vm.run(vm.directory[heap.intern("push")], [B.mkfix(0), x]))
        row["macros"] = sorted(heap.symbol_name(s) for s in vm.macro_symbols)
    return row


def require_equivalence(world: World) -> list[dict]:
    rows = []
    for order in (("'place", '"place"'), ('"place"', "'place")):
        vm = world.vm(build_disk(FIXTURE_TEXT), "owner-token")
        results = []
        for arg in order:
            before = len(vm.reads)
            value = vm.evaluate(f"(require {arg})")
            results.append({"argument": arg, "value": value,
                            "sector_reads": len(vm.reads) - before})
        check([r["value"] for r in results] == ["t", "t"]
              and vm.loaded == ["place"] and results[1]["sector_reads"] == 0,
              f"symbol/string require not equivalent: {results} {vm.loaded}")
        rows.append({"order": list(order), "results": results,
                     "loader_calls": vm.loaded})
    vm = world.vm(build_disk(FIXTURE_TEXT), "owner-token")
    others = {arg: vm.evaluate(f"(require {arg})")
              for arg in ('"no-such"', "'no-such", "7", "nil")}
    check(set(others.values()) == {"nil"} and vm.loaded == [],
          f"non-package require not nil: {others}")
    rows.append({"non_package": others})
    return rows


def directory_contract(world: World) -> dict:
    vm = world.vm(build_disk(FIXTURE_TEXT), "owner-token")
    calls = {
        "(%disk-directory-link-valid-p 40 3 18 34)": "nil",
        "(%disk-directory-link-valid-p 40 3 40 4)": "t",
        "(%disk-directory-link-valid-p 40 3 0 255)": "t",
        "(%disk-file-link-valid-p 18 34 18 35)": "t",
        "(%disk-file-link-valid-p 18 34 18 34)": "nil",
        '(load "absent")': "nil",
    }
    got = {expr: vm.evaluate(expr) for expr in calls}
    check(got == calls, f"directory contract drift: {got}")
    text = REQUIRE.read_text(encoding="utf-8")
    check(text.count("(%disk-directory-link-valid-p") == 1
          and "(%disk-file-link-valid-p" in text,
          "index reader guard population drift")
    return {"cases": got, "directory_guard_in_require": "%l65i-find only",
            "file_guard_in_require": "%l65i-next-byte"}


def nested_scratch_users(world: World) -> list[dict]:
    """Class members beyond require: a raw sector read and a nested load."""
    rows = []
    probe = ('(require "place")\n(%disk-read-sector 40 3)\n'
             "(set-symbol-value '*after-raw-read* 7)\n")
    for mode in ("two-owner", "owner-token"):
        vm = world.vm(build_disk(probe), mode)
        vm.evaluate('(load "init.l65")')
        value = vm.heap.obj_to_text(vm.heap.symbol_value(
            vm.heap.intern("*after-raw-read*")))
        rows.append({"case": "raw-%disk-read-sector-inside-init", "mode": mode,
                     "after": value, "transcript": vm.transcript})
    check(rows[0]["after"] != "7" and rows[1]["after"] == "7",
          "raw scratch reader inside INIT is not repaired by the owner token")
    nested = ('(load "tail.l65")\n'
              "(set-symbol-value '*after-nested-load* 9)\n")
    vm = world.vm(build_disk(nested, "(set-symbol-value '*inner* 1)\n"),
                  "owner-token")
    vm.evaluate('(load "init.l65")')
    inner = vm.heap.obj_to_text(vm.heap.symbol_value(vm.heap.intern("*inner*")))
    after = vm.heap.obj_to_text(vm.heap.symbol_value(
        vm.heap.intern("*after-nested-load*")))
    rows.append({"case": "nested-load-inside-init (by-catch)",
                 "mode": "owner-token", "inner": inner, "after": after,
                 "transcript": vm.transcript,
                 "finding": "separate class: io_disk_load_chain re-enters and "
                            "overwrites disk_file_len/pos/link/cur and the reader "
                            "fetch; the outer INIT ends silently after it"})
    return rows


def symbol_figures(world: World) -> dict:
    out = {}
    for label, text in (("symbol-form", "(require 'place)\n(require 'string-extra)\n"),
                        ("string-form", FIXTURE_TEXT)):
        heap = world.heap.clone()
        before = set(heap.symbols)
        for form in C.parse_all(text):
            C.compile_top_form_with_helpers(
                ["lambda", [], form], heap, strict_arity=True,
                abi_profile=world.abi, abi_ledger=world.ledger)
        new = sorted(set(heap.symbols) - before)
        out[label] = {"new_symbols": new,
                      "name_bytes": sum(len(n) for n in new)}
    return out


def bind(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run() -> dict:
    check(FIXTURE.read_text(encoding="ascii") == FIXTURE_TEXT,
          "INIT.L65 fixture is not exactly the two string-form requires")
    io_source = IO_SOURCE.read_text(encoding="utf-8")
    check("DISK_SOURCE_OWNS_SCRATCH" in io_source,
          "src/io.c lacks the DIR scratch owner token")
    world = World()
    init = multi_sector_init()
    rows = {mode: run_init(world, init, mode)
            for mode in ("two-owner", "owner-token", "whole-buffer", "file-window")}
    fixture_rows = {mode: run_init(world, FIXTURE_TEXT, mode)
                    for mode in ("two-owner", "owner-token")}
    good = rows["owner-token"]
    check(good["loaded"] == ["place", "string-extra"]
          and good["bound"] == {"setf": True, "push": True, "capitalize": True}
          and good["init_tail"] == '("Abc" (setq x 5) (setq x (cons 0 x)))'
          and good["init_end"] == "42"
          and good["setf_expansion"] == "(setq x 5)"
          and good["push_expansion"] == "(setq x (cons 0 x))",
          f"owner-token INIT red: {good}")
    check(rows["whole-buffer"]["init_end"] == "42", "form-B model red")
    control = rows["two-owner"]
    check(control["init_end"] != "42" and control["loaded"] != ["place", "string-extra"],
          f"two-owner control unexpectedly green: {control}")
    check(rows["file-window"]["init_end"] != "42",
          "form B inside DISK_EXT_FILE unexpectedly survived library staging")
    check(fixture_rows["owner-token"]["loaded"] == ["place", "string-extra"]
          and fixture_rows["two-owner"]["loaded"] != ["place", "string-extra"],
          f"exact fixture rows drift: {fixture_rows}")
    return {
        "status": "PASS",
        "init_bytes": len(init),
        "init_sectors": (len(init) + 253) // 254,
        "multi_sector": rows,
        "exact_fixture": fixture_rows,
        "require_equivalence": require_equivalence(world),
        "directory_contract": directory_contract(world),
        "nested_scratch_users": nested_scratch_users(world),
        "symbols": symbol_figures(world),
        "inputs": [bind(p) for p in (REQUIRE, SUITE, FIXTURE, IO_SOURCE,
                                     *LIBS.values(), Path(__file__))],
        "claim": ("Host model of the native source loader plus live compiled "
                  "require/L65I Lisp; C2D plane and L65S publication are "
                  "fixtures. No product qualification."),
    }


if __name__ == "__main__":
    try:
        result = run()
    except GateError as error:
        print(f"init-require-scratch: FAIL: {error}")
        sys.exit(1)
    out = ROOT / "build/init-require-scratch-gate/receipt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    control = result["multi_sector"]["two-owner"]["transcript"]
    print("init-require-scratch: PASS init=%dB/%d sectors modes=%d "
          "control=%s" % (result["init_bytes"], result["init_sectors"],
                          len(result["multi_sector"]),
                          json.dumps(control[-1] if control else None)))
