#!/usr/bin/env python3
"""Pack Card 3 and measure its forced-collection GC wall in DWX cycles."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from types import SimpleNamespace
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_vm_hardening_product_card as CARD  # noqa: E402
import block_26_f011_dwx_prefilter as CARD2_DWX  # noqa: E402
import c2_v200_release_strip_device_media as MEDIA  # noqa: E402
import dwx_mirrored_prefilter_rows as ROWS  # noqa: E402
import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402
import dwx_retroactive_red_replay as CYCLES  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card3-vm-hardening-dwx-r1"
MEDIA_BUILD = BUILD / "media"
WPLTO = MEDIA_BUILD / "inputs/wplto"
STATIC = MEDIA_BUILD / "inputs/static-plane"
TARGET = MEDIA_BUILD / "canonical-product"
SHARED = MEDIA_BUILD / "shared-system"
MEDIA_RECEIPT = BUILD / "prefilter-medium-receipt.json"
SESSION = BUILD / "unused-device-session.json"
PREFILTER_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-dwx-r1.json"
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-dwx-r1.md"
BASELINE_RECEIPT = CARD2_DWX.PREFILTER_RECEIPT
PRODUCT_ID = 0x4A1713AB
PLANE_BYTES = 47795
PRODUCT_KEYS = CARD.CARD2.R2.CARD.BASE.PRODUCT_KEYS
FORMAT = "lisp65-block-2.6-card3-vm-hardening-dwx-r1-v1"
STATUS = "PASS: CARD-3 A3-A6 PACKED PREFILTER AND GC-CYCLE WALL GREEN"
RED_STATUS = "PRODUCT RED: CARD-3 BSS OVERLAPS FIXED INPUT-RING OWNER"
MEDIA_FORMAT = "lisp65-block-2.6-card3-vm-hardening-dwx-medium-r1-v1"
MEDIA_STATUS = "PASS: CARD-3 A3-A6 DWX PREFILTER MEDIUM READY"
SESSION_FORMAT = "lisp65-block-2.6-card3-vm-hardening-unused-device-session-v1"
XEMU = ROOT / "build/dwx/xemu-cycle-probe-r3/build/bin/xmega65.native"
ROM = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
SD_IMAGE = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))
BLIND_CONTRACT = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
PATTERN = "01234567012345670123456701234567"
CONTROLLER = ("(progn(setq s(read-line))(print(string-length s))"
              "(print 9)(wait 16383))\n")
PASSES = 6
WARMUP_PASSES = 12
FINAL = "abcdefg\n"
EXPECTED_COUNTER = 136
REPEATS = 3
NONQUALIFYING_PREFILTER_ATTEMPTS = 14
FIRST_FAULT_RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r4-receipt.json"


class PrefilterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PrefilterError(message)


class PersistentProbeMonitor(CYCLES.ProbeMonitor):
    """Use one UART connection for a complete cold-boot measurement.

    The qualified fork logs every accepted monitor socket.  Reconnecting for
    every counter poll can itself destabilize a long forced-collection run;
    it is transport noise, not part of the measured target path.
    """

    TERMINATOR = b"\n.\r\n"

    def __init__(self, path: Path):
        super().__init__(path)
        self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.settimeout(3.0)
        self.client.connect(str(path))
        self.pending = b""

    def command(self, command: str, timeout: float = 3.0) -> str:
        self.client.settimeout(timeout)
        self.client.sendall(command.encode("ascii") + b"\r")
        while self.TERMINATOR not in self.pending:
            block = self.client.recv(16384)
            if not block and command == "~exit":
                response, self.pending = self.pending, b""
                return response.decode("utf-8", errors="replace")
            require(bool(block), f"persistent UART monitor closed during {command}")
            self.pending += block
        response, self.pending = self.pending.split(self.TERMINATOR, 1)
        return (response + self.TERMINATOR).decode("utf-8", errors="replace")

    def close(self) -> None:
        self.client.close()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256(path)}


def configure_card() -> None:
    CARD.patch_card(); CARD.CARD2.R2.CARD.configure()


class ProductCard:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    LINK = CARD.CARD2.R2.CARD.BASE.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        configure_card()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        configure_card()
        return CARD.CARD2.R2.CARD.BASE.CHAIN.setup_link_world()


MediaPrice = MEDIA.MediaPrice


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = MediaPrice.RECEIPT
    PRICE = MediaPrice


def accepted_pair() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    pair = {role: bind(path) for role, path in (("PRG", CARD.PRG), ("ELF", CARD.ELF))}
    require(pair == {role: receipt["artifacts_after"][role] for role in pair},
            "Card-3 accepted pair drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    require(receipt["status"] == CARD.STATUS
            and {role: receipt["artifacts_after"][role]
                 for role in ("PRG", "ELF")} == accepted_pair(),
            "Card-3 pair escaped its product receipt")
    return {"product_card_status": CARD.STATUS, "accepted_pair": accepted_pair(),
        "commission": CARD.authority()["commission"],
        "right": "artifact-only packed DWX and GC-cycle wall; zero builds/contacts"}


def session_config(product: Path, valid: Path | None = None) -> dict[str, Any]:
    return {"format": SESSION_FORMAT, "status": "not-a-device-session",
        "medium": bind(product), "device_acceptance_claimed": False,
        "claim": "DWX packed functional and GC-cycle prefilter only",
        "claim_scope": {"accepts": ["packed-byte closure and coherence",
            "forced-collection framebuffer/counter oracle",
            "emulated CPU/DMA cycles within gc_collect"],
            "excludes": ["device acceptance", "Freezer", "physical timing",
                         "typing feel"]}}


def inherited_check(*, source_only: bool = False) -> None:
    value = load(MEDIA_RECEIPT)
    require(value["status"] == MEDIA_STATUS and value["accepted_pair"] == accepted_pair()
            and value["accounting"]["WPLTO_runs"] == 0
            and value["accounting"]["product_links"] == 0
            and value["accounting"]["device_contacts"] == 0,
            "Card-3 transient medium drift")
    if not source_only:
        observed = bind(ROOT / value["media"]["absent_INIT"]["path"])
        require(all(observed[key] == value["media"]["absent_INIT"][key]
                    for key in ("path", "bytes", "sha256")),
                "Card-3 D81 identity drift")


def static_plane_gate() -> dict[str, Any]:
    manifest = TARGET / "canonical-product-manifest.json"
    value = load(manifest)
    plane = value["static_plane"]
    composed = load(CARD.RECEIPT)["final_product"]["composed_bank2"]
    rows = [item for item in value["artifacts"]
            if item["role"] == "c2-bank2-static-code-plane"]
    require(len(rows) == 1, "Card-3 packed static-plane population drift")
    expected = [{key: row[key] for key in ("start", "end_exclusive", "bytes")}
                for row in [*composed["owners"], *composed["free_intervals"]]]
    observed = [{key: row[key] for key in ("start", "end_exclusive", "bytes")}
                for row in plane["composed_owners"]]
    expected.sort(key=lambda row: row["start"]); observed.sort(key=lambda row: row["start"])
    reserve = next(row for row in composed["reserved_owners"]
                   if row["owner"] == "mapped-tenant-bank-end-reserve")
    emitted_extent = reserve["start"] - composed["bank"]["start"]
    require(plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == rows[0]["bytes"] == emitted_extent
            and plane["largest_contiguous_hole"] == composed["largest_contiguous_hole"]
            and observed == expected
            and bind(ROOT / rows[0]["path"])["sha256"] == rows[0]["sha256"] ==
                plane["bank2_sha256"], "Card-3 packed composed-plane drift")
    return {"manifest": bind(manifest), "static_plane": plane,
        "artifact": rows[0], "source": bind(CARD.RECEIPT)}


def configure_media() -> None:
    candidate = SimpleNamespace(PRODUCT_KEYS=PRODUCT_KEYS, RECEIPT=CARD.RECEIPT,
        PRG=CARD.PRG, ELF=CARD.ELF, WPLTO=CARD.WPLTO, PLANE=CARD.PLANE,
        BUILD=CARD.BUILD, STATUS=CARD.STATUS, CHAIN=CARD.CARD2.R2.CARD.BASE.CHAIN,
        configure=configure_card)
    MEDIA.STRIP = candidate
    MEDIA.ProductCard = ProductCard
    MEDIA.Adapter = Adapter
    expected = {"PRG": (CARD.PRG.stat().st_size, sha256(CARD.PRG)),
                "ELF": (CARD.ELF.stat().st_size, sha256(CARD.ELF))}
    for name, value in {"BUILD": MEDIA_BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": MEDIA_RECEIPT,
        "SESSION": SESSION, "VALID": BUILD / "unused-init-valid.d81",
        "VALID_SOURCE": BUILD / "unused-init-valid.l65",
        "PRODUCT_REMOTE": "B26C3.D81", "VALID_REMOTE": "UNUSED.D81",
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": expected, "STATUS": MEDIA_STATUS, "FORMAT": MEDIA_FORMAT,
        "SESSION_FORMAT": SESSION_FORMAT}.items():
        setattr(MEDIA, name, value)
    MEDIA.accepted_pair = accepted_pair
    MEDIA.authority = authority
    MEDIA.plan_section = lambda: CARD.authority()["commission"]
    MEDIA.session_config = session_config
    MEDIA.inherited_check = inherited_check
    MEDIA.check = inherited_check
    MEDIA.configure()
    MEDIA.EXPECTED_LARGEST_HOLE = load(CARD.RECEIPT)["final_product"][
        "composed_bank2"]["largest_contiguous_hole"]["bytes"]
    MEDIA.static_plane_gate = static_plane_gate
    MEDIA.BASE.BASE.EXPECTED_LARGEST_HOLE = MEDIA.EXPECTED_LARGEST_HOLE
    MEDIA.BASE.BASE.static_plane_gate = static_plane_gate


def build_medium() -> tuple[Path, dict[str, Any]]:
    configure_media()
    if not MEDIA_RECEIPT.exists():
        try:
            MEDIA.BASE.BASE.build()
        except KeyError as error:
            # The inherited Block-3 producer prints media.product only after
            # finish() has written and checked the successor's explicit
            # absent/valid INIT variant schema.  That stale presentation tail
            # must not turn a completed medium into product evidence, but it
            # is admissible only when the complete successor receipt exists.
            require(error.args == ("product",) and MEDIA_RECEIPT.is_file(),
                    f"unexpected packed-medium producer failure: {error}")
    inherited_check()
    value = load(MEDIA_RECEIPT)
    product = ROOT / value["media"]["absent_INIT"]["path"]
    packed = value["packed_readback"]["absent_INIT"]
    require(packed["status"] == "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and packed["closure"]["object_count"] == 760
            and packed["closure"]["call_site_count"] == 2436,
            "Card-3 packed closure/coherence red")
    return product, packed


def tool_identity() -> dict[str, Any]:
    blind = load(BLIND_CONTRACT); BLIND.validate_contract(blind)
    tool = blind["qualified_tool_identity"]
    rows = load(ROOT / "config/dwx-mirrored-prefilter-rows-contract.json")
    require(sha256(XEMU) == tool["binary_sha256"]
            and sha256(ROM) == rows["inputs"]["rom_sha256"]
            and sha256(SD_IMAGE) == rows["inputs"]["system_sd_sha256"],
            "Card-3 DWX tool/ROM/SD identity drift")
    return tool


def gc_bounds(elf: Path) -> dict[str, int]:
    truth = ElfTruth.read(elf, llvm_readobj=CARD.READOBJ)
    symbol = truth.symbol("gc_collect")
    output = subprocess.run([str(ROOT / "tools/llvm-mos/bin/llvm-objdump"),
        "-d", "--no-show-raw-insn", str(elf)], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    block = output.split("<gc_collect>:", 1)[1].split("\n\n", 1)[0]
    exits = [int(item, 16) for item in re.findall(
        r"^\s*([0-9a-f]+):\s+rts\s*$", block, re.MULTILINE)]
    require(len(exits) == 1, "gc_collect no longer has one measurable RTS boundary")
    return {"entry": symbol.value, "entry_after_first_opcode": symbol.value + 1,
        "exit_rts": exits[0], "gc_runs": truth.symbol("gc_runs").value,
        "function_bytes": symbol.bytes}


def bss_raw_owner_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=CARD.READOBJ)
    start = truth.symbol("C2K_INPUT_RING_BASE").value
    end = truth.symbol("C2K_INPUT_EVENTS_TAKEN").value + 1
    require(end - start == 112, "input-ring raw-owner width drift")
    rows = []
    for symbol in truth.symbols:
        if (symbol.symbol_type != "Object" or symbol.section not in {
                ".bss", ".lisp65_c2_symbol_metadata_bss"}
                or symbol.bytes <= 0):
            continue
        lo, hi = symbol.value, symbol.value + symbol.bytes
        if lo < end and hi > start:
            rows.append({"name": symbol.name, "start": lo,
                "end_exclusive": hi, "bytes": symbol.bytes,
                "overlap": [max(lo, start), min(hi, end)]})
    rows.sort(key=lambda row: (row["start"], row["name"]))
    allowed = {"repl.buf", "c2_symbol22_repl_buf"}
    violations = [row for row in rows if row["name"] not in allowed]
    return {"raw_owner": {"name": "input-ring-and-counters",
            "start": start, "end_exclusive": end, "bytes": end - start,
            "derivation": "C2K_INPUT_RING_BASE..C2K_INPUT_EVENTS_TAKEN+1"},
        "intersecting_BSS_objects": rows,
        "temporally_proved_aliases": sorted(row["name"] for row in rows
                                              if row["name"] in allowed),
        "alias_authority": bind(FIRST_FAULT_RECEIPT),
        "simultaneously_live_violations": violations,
        "status": "PASS" if not violations else "RED"}


def validate_raw_owner_model(value: dict[str, Any], elf: Path) -> None:
    derived = bss_raw_owner_gate(elf)
    require(value["raw_owner"] == derived["raw_owner"]
            and value["intersecting_BSS_objects"] ==
                derived["intersecting_BSS_objects"]
            and value["simultaneously_live_violations"] ==
                derived["simultaneously_live_violations"]
            and value["status"] == derived["status"],
            "fixed-raw/BSS ownership model is not final-ELF-derived")


def raw_owner_mutations(value: dict[str, Any], elf: Path) -> list[str]:
    cases = {
        "fixed-raw-window-omitted": lambda row: row.update(
            {"raw_owner": {}}),
        "aggregate-bss-margin-substituted": lambda row: row.update(
            {"intersecting_BSS_objects": []}),
        "live-namelen4-declared-inactive": lambda row: row.update(
            {"simultaneously_live_violations": []}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_raw_owner_model(trial, elf)
        except PrefilterError:
            rejected.append(name)
    require(rejected == list(cases), "fixed-raw/BSS ownership mutation survived")
    return rejected


def register_line(monitor: CYCLES.ProbeMonitor) -> str:
    response = monitor.command("r")
    lines = [line for line in response.splitlines()
             if re.match(r"^[0-9A-F]{4} ", line)]
    # A persistent socket also receives the asynchronous register dump emitted
    # when a breakpoint fires.  The explicit `r` reply is the final row.
    require(bool(lines), f"DWX register response malformed: {response!r}")
    return lines[-1]


def wait_register(monitor: CYCLES.ProbeMonitor,
                  predicate: Callable[[str], bool], label: str,
                  timeout: float = 90.0) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = register_line(monitor)
        if predicate(last):
            return last
        # Each monitor connection is deliberately sparse: the qualified fork
        # logs monitor traffic, so tight polling would measure/log the probe
        # rather than the long mapped-heap collection.
        time.sleep(0.5)
    raise PrefilterError(f"{label} breakpoint timeout: {last}")


def wait_counter(monitor: CYCLES.ProbeMonitor, expected: int,
                 timeout: float = 20.0) -> bytes:
    deadline = time.monotonic() + timeout
    target = bytes((expected,)) * 4
    last = b""
    while time.monotonic() < deadline:
        last = monitor.memory16(0xBCFC)[:4]
        if last == target:
            return last
        time.sleep(0.10)
    raise PrefilterError(f"capture counters did not reach {target.hex()}: {last.hex()}")


def measure_one(run_id: str, medium: Path, elf: Path) -> dict[str, Any]:
    runtime = BUILD / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(sd_image=SD_IMAGE, rom=ROM, xemu=XEMU, timeout=180)
    run = CYCLES.start_run(run_id, medium, runtime, args)
    bounds = gc_bounds(elf)
    monitor = PersistentProbeMonitor(run["monitor_path"])
    run["monitor"] = monitor
    try:
        monitor.type_text(CONTROLLER)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if (monitor.memory16(0xFF8D)[0] != 0xFF
                    and monitor.memory16(0xBCFC)[:4] == b"\0\0\0\0"):
                break
            time.sleep(0.05)
        else:
            raise PrefilterError("forced-collection controller never armed fresh ring")

        generation_armed = int.from_bytes(
            monitor.memory16(bounds["gc_runs"])[:2], "little")
        freelist_armed = int.from_bytes(monitor.memory16(0x43)[:2], "little")
        warmup_counter = 0
        for _ in range(WARMUP_PASSES):
            warmup_counter = monitor.type_and_wait_counters(
                PATTERN, warmup_counter)
            warmup_counter = monitor.type_and_wait_counters(
                "\x08" * len(PATTERN), warmup_counter)
        generation_after_warmup = int.from_bytes(
            monitor.memory16(bounds["gc_runs"])[:2], "little")
        freelist_after_warmup = int.from_bytes(
            monitor.memory16(0x43)[:2], "little")
        require(warmup_counter == 0
                and monitor.memory16(0xBCFC)[:4] == b"\0\0\0\0"
                and generation_after_warmup == generation_armed,
                "modulo-neutral warmup crossed GC or counter boundary")

        monitor.command("t1")
        monitor.command(f"b {bounds['entry']:04x}")
        monitor.command("t0")
        chunks = []
        for _ in range(PASSES):
            chunks.extend((PATTERN, "\x08" * len(PATTERN)))
        chunks.extend((FINAL[:-1], "\n"))
        counter = 0
        measured: dict[str, Any] | None = None
        for chunk_index, chunk in enumerate(chunks):
            expected = (counter + len(chunk)) & 0xFF
            response = monitor.command("~typehex " + chunk.encode("ascii").hex())
            require("DWX HWA input queued" in response, "GC trace input was not queued")
            if measured is not None:
                wait_counter(monitor, expected)
                counter = expected
                continue
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current = monitor.memory16(0xBCFC)[:4]
                line = register_line(monitor)
                if line.startswith(f"{bounds['entry_after_first_opcode']:04X} "):
                    before = monitor.cycle_count()
                    generation_before = int.from_bytes(
                        monitor.memory16(bounds["gc_runs"])[:2], "little")
                    monitor.command(f"b {bounds['exit_rts']:04x}")
                    monitor.command("t0")
                    exit_line = wait_register(monitor,
                        lambda row: bool(re.search(r"\s60\s+", row)),
                        "gc_collect exit")
                    after = monitor.cycle_count()
                    generation_after = int.from_bytes(
                        monitor.memory16(bounds["gc_runs"])[:2], "little")
                    require(generation_after == (generation_before + 1) & 0xFFFF
                            and after > before,
                            "GC boundary did not span one collection")
                    measured = {"entry_registers": line,
                        "exit_registers": exit_line,
                        "cycles_before": before, "cycles_after": after,
                        "cycles": after - before,
                        "gc_runs_before": generation_before,
                        "gc_runs_after": generation_after,
                        "trigger_chunk_bytes": len(chunk),
                        "trigger_chunk_index": chunk_index}
                    monitor.command("b ffff"); monitor.command("t0")
                    wait_counter(monitor, expected)
                    counter = expected
                    break
                if current == bytes((expected,)) * 4:
                    counter = expected
                    break
                time.sleep(0.10)
            else:
                raise PrefilterError(
                    "forced-collection chunk neither drained nor hit GC: "
                    f"index={chunk_index} expected={expected:02x} "
                    f"counter={current.hex()} registers={line}")
        require(measured is not None and counter == EXPECTED_COUNTER,
                "six-line choreography did not cross one measured collection")
        final_frame = monitor.wait_screen(["\n7\n", "\n9\n"])
        monitor.command("t1")
        counters = monitor.memory16(0xBCFC)[:4]
        generation_stopped = int.from_bytes(
            monitor.memory16(bounds["gc_runs"])[:2], "little")
        require(counters == bytes((EXPECTED_COUNTER,)) * 4,
                f"forced-collection final counters red: {counters.hex()}")
        require(generation_stopped == measured["gc_runs_after"],
                "six-line measured segment crossed more than one collection")
        screen = monitor.screen()
        outputs = CYCLES.finish_run(run, screen)
        monitor.close()
        decoded = ROWS.decoded_framebuffer(final_frame)
        require("\n7\n" in decoded and "\n9\n" in decoded,
                "post-input length/symbol oracle drift")
        measured.update({"id": run_id, "medium": bind(medium), "ELF": bind(elf),
            "gc_bounds": bounds, "choreography": {"controller": CONTROLLER,
                "warmup": {"passes": WARMUP_PASSES,
                    "events": WARMUP_PASSES * len(PATTERN) * 2,
                    "counter_modulo_before_and_after": 0,
                    "gc_runs_before": generation_armed,
                    "gc_runs_after": generation_after_warmup,
                    "freelist_object_before": freelist_armed,
                    "freelist_object_after": freelist_after_warmup},
                "pattern": PATTERN, "passes": PASSES, "final": FINAL,
                "physical_events": 392, "counter_modulo": EXPECTED_COUNTER},
            "stopped_counters": counters.hex(), "outputs": outputs,
            "gc_runs_stopped": generation_stopped,
            "post_input_length_oracle": 7, "post_input_symbol_oracle": 9,
            "desktop_focus_used": False, "GUI_used": False})
        return measured
    except BaseException:
        status = run["process"].poll()
        print(f"{run_id}: aborting DWX run (xemu_status={status})", file=sys.stderr)
        monitor.close()
        CYCLES.abort_run(run)
        raise


def statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["cycles"] for row in rows]
    return {"runs": len(values), "values": values, "minimum": min(values),
        "maximum": max(values), "mean": sum(values) / len(values),
        "noise_span": max(values) - min(values)}


def reproduce_raw_owner_collision(medium: Path) -> dict[str, Any]:
    runtime = BUILD / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(sd_image=SD_IMAGE, rom=ROM, xemu=XEMU, timeout=90)
    run = CYCLES.start_run("raw-owner-red", medium, runtime, args)
    monitor = PersistentProbeMonitor(run["monitor_path"])
    run["monitor"] = monitor
    bounds = gc_bounds(CARD.ELF)
    gate = bss_raw_owner_gate(CARD.ELF)
    start = gate["raw_owner"]["start"]
    try:
        before_window = monitor.memory_range(start, 112)
        gc_before = int.from_bytes(
            monitor.memory16(bounds["gc_runs"])[:2], "little")
        monitor.type_text("(print 9)\n")
        fresh = monitor.wait_screen(["\n9 9\n"])
        fresh_path = run["dir"] / "fresh-print-framebuffer.txt"
        fresh_path.write_text(fresh, encoding="utf-8")

        monitor.type_text(CONTROLLER)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if (monitor.memory16(0xFF8D)[0] != 0xFF
                    and monitor.memory16(0xBCFC)[:4] == b"\0\0\0\0"):
                break
            time.sleep(0.05)
        else:
            raise PrefilterError("raw-owner reproducer never armed a fresh ring")
        counter = 0
        for _ in range(PASSES):
            counter = monitor.type_and_wait_counters(PATTERN, counter)
            counter = monitor.type_and_wait_counters("\x08" * len(PATTERN), counter)
        response = monitor.command("~typehex " + FINAL.encode("ascii").hex())
        require("DWX HWA input queued" in response,
                "final oracle input was not queued")
        completed = monitor.wait_screen(["\n7\n"], timeout=20)
        gc_after = int.from_bytes(
            monitor.memory16(bounds["gc_runs"])[:2], "little")
        after_window = monitor.memory_range(start, 112)

        monitor.type_text("(print 9)\n")
        red = monitor.wait_screen(["UNDEFINED FUNCTION: PRINT"], timeout=15)
        monitor.command("t1")
        final_screen = monitor.screen()
        outputs = CYCLES.finish_run(run, final_screen)
        monitor.close()
        changed = [index for index, pair in enumerate(
            zip(before_window, after_window)) if pair[0] != pair[1]]
        require(gc_before == gc_after == 0 and changed
                and "UNDEFINED FUNCTION: PRINT" in
                    ROWS.decoded_framebuffer(red),
                "raw-owner runtime discriminator did not reproduce")
        return {"status": "PRODUCT RED REPRODUCED",
            "fresh_print_before_input": True,
            "read_line_oracle": 7,
            "print_after_input": "UNDEFINED FUNCTION: PRINT",
            "gc_runs_before": gc_before, "gc_runs_after": gc_after,
            "gc_collection_involved": False,
            "raw_owner_before_hex": before_window.hex(),
            "raw_owner_after_hex": after_window.hex(),
            "raw_owner_changed_offsets": changed,
            "fresh_framebuffer": bind(fresh_path),
            "final_framebuffer_contains_error": True,
            "completed_framebuffer_observed": bool(completed),
            "outputs": outputs, "desktop_focus_used": False,
            "GUI_used": False}
    except BaseException:
        monitor.close()
        CYCLES.abort_run(run)
        raise


def red_report(value: dict[str, Any]) -> str:
    conflict = value["fixed_raw_BSS_ownership"][
        "simultaneously_live_violations"][0]
    return f"""# Block 2.6 Card 3 — packed DWX product red

Status: **{value['status']}**

The final ELF's 512-byte mark-stack removal moved later ordinary-BSS objects
downward. The `{conflict['name']}` object now spans
`${conflict['start']:04X}..${conflict['end_exclusive'] - 1:04X}` and intersects
the derived fixed-address input-ring/counter owner `$BC90..$BCFF`. Aggregate
BSS end margin remained green, but did not prove that this internal raw-owned
window stayed vacant.

The packed candidate reproduces the consequence headlessly. `(print 9)` is
present on a fresh boot. After the six-line `read-line` choreography returns
`7`, `(print 9)` reports `*** undefined function: print`. `gc_runs` remains
zero throughout, so neither the new fixpoint nor GC timing causes this red;
input-ring writes corrupt the simultaneously live name-length table.

The r1 pair is **frozen unqualified product evidence**. The authorized one
WPLTO and one product link are consumed; no physical-device contact occurred.
The GC-cycle wall did not run because its candidate medium is functionally red.
"""


def validate_red(value: dict[str, Any]) -> None:
    gate = value["fixed_raw_BSS_ownership"]
    validate_raw_owner_model(gate, CARD.ELF)
    runtime = value["runtime_reproduction"]
    require(value["format"] == FORMAT and value["status"] == RED_STATUS
            and value["accepted_pair"] == accepted_pair()
            and gate["status"] == "RED"
            and [row["name"] for row in
                 gate["simultaneously_live_violations"]] == ["namelen4"]
            and runtime["fresh_print_before_input"] is True
            and runtime["print_after_input"] == "UNDEFINED FUNCTION: PRINT"
            and runtime["gc_runs_before"] == runtime["gc_runs_after"] == 0
            and value["disposition"] ==
                "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
            and value["attempt_accounting"]["qualifying_GC_wall_runs"] == 0
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-3 fixed-raw/BSS product-red receipt drift")


def report(value: dict[str, Any]) -> str:
    wall = value["gc_cycle_wall"]
    return f"""# Block 2.6 Card 3 — packed DWX and GC-cycle wall

Status: **{value['status']}**

The candidate D81 passes transitive closure and generation coherence over its
read-back packed bytes. Three reference and three successor cold boots execute
the same six-line 392-event choreography. A breakpoint pair derived from each
final ELF measures exactly one `gc_collect` entry-to-RTS interval; every run
finishes at framebuffer oracle `7` with counters `88 88 88 88`.
The successor runs also execute `(print 9)` after the six-line input and
observe `9`, permanently witnessing that the symbol-name table survives the
fixed raw-input window.

Reference mean: **{wall['reference']['mean']:,.0f} cycles/collection**;
candidate mean: **{wall['candidate']['mean']:,.0f}**; delta
**{wall['delta_mean_cycles']:+,.0f}**. The admitted noise envelope is
**{wall['admitted_noise_cycles']:,.0f} cycles** and the non-increase wall is
**{wall['status']}**. This is a qualified-fork emulated CPU/DMA-cycle prefilter,
not wall-clock, physical-key or device-timing evidence.

No additional WPLTO, product link or physical-device contact was used. Card 3
is review-ready; A7 remains closed for its separate three-lane decision.
Fourteen premeasurement runs are non-qualifying and explicitly attributed in
the receipt: they distinguish stale media presentation, the stopped-read
window, fresh-heap non-collection, unsuitable expression prefill, and the
final in-editor warmup boundary.  The qualified controller prints `7`, prints
`9`, then waits at the bound read intersection.  Twelve modulo-neutral warmup
passes leave `gc_runs` unchanged; the following six bound passes cross exactly
one collection.
"""


def validate(value: dict[str, Any]) -> None:
    wall = value["gc_cycle_wall"]
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["packed_readback"]["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and len(wall["reference_runs"]) == len(wall["candidate_runs"]) == REPEATS
            and wall["status"] == "PASS"
            and wall["candidate"]["mean"] <= wall["reference"]["mean"] +
                wall["admitted_noise_cycles"]
            and all(row["stopped_counters"] == "88888888"
                    for row in wall["reference_runs"] + wall["candidate_runs"])
            and all(row["choreography"]["controller"] == CONTROLLER
                    for row in wall["reference_runs"] + wall["candidate_runs"])
            and all(row["choreography"]["warmup"]["passes"] ==
                        WARMUP_PASSES
                    and row["choreography"]["warmup"]["gc_runs_before"] ==
                        row["choreography"]["warmup"]["gc_runs_after"]
                    and row["gc_runs_after"] == row["gc_runs_before"] + 1 ==
                        row["gc_runs_stopped"]
                    for row in wall["reference_runs"] + wall["candidate_runs"])
            and all(row["post_input_symbol_oracle"] == 9
                    for row in wall["candidate_runs"])
            and value["fixture_attribution"]["stopped_read_fix"] ==
                "print 7; print 9; then wait before the next read-line arms"
            and value["attempt_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "DWX_prefilter_runs": 6,
                "candidate_media_builds": 1,
                "nonqualifying_prefilter_attempts":
                    NONQUALIFYING_PREFILTER_ATTEMPTS,
                "medium_presentation_reds": 1,
                "device_contacts": 0},
            "Card-3 DWX/GC-cycle receipt drift")


def write_red(product: Path, packed: dict[str, Any],
              ownership: dict[str, Any]) -> None:
    runtime = reproduce_raw_owner_collision(product)
    ownership["mutations_rejected"] = raw_owner_mutations(ownership, CARD.ELF)
    value = {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": RED_STATUS, "authority": authority(),
        "accepted_pair": accepted_pair(), "medium_receipt": bind(MEDIA_RECEIPT),
        "medium": bind(product), "packed_readback": packed,
        "fixed_raw_BSS_ownership": ownership,
        "runtime_reproduction": runtime,
        "diagnosis": {"product_defect_established": True,
            "mechanism": ("markstack removal shifts namelen4 into the fixed "
                "input-ring/counter window; read-line capture overwrites the "
                "live name-length table"),
            "GC_algorithm_exonerated_for_this_red": True,
            "missing_gate": ("aggregate BSS-end capacity did not compose "
                "internal fixed-address raw owners with individual live BSS objects")},
        "disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
        "gc_cycle_wall": {"status": "NOT RUN: CANDIDATE PRODUCT RED"},
        "attempt_accounting": {"inherited_WPLTO_runs": 1,
            "inherited_product_links": 1, "candidate_media_builds": 1,
            "product_red_reproduction_runs": 1,
            "qualifying_GC_wall_runs": 0, "device_contacts": 0},
        "claim_limit": ("Host/DWX product-red evidence only; no GC-cycle, "
            "device or successor claim")}
    PREFILTER_RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(red_report(value), encoding="utf-8")
    validate_red(value)

    product_receipt = load(CARD.RECEIPT)
    product_receipt["final_product"]["packed_prefilter"] = {
        "status": "RED: FIXED INPUT RING OVERLAPS LIVE namelen4",
        "receipt": bind(PREFILTER_RECEIPT), "medium": bind(product)}
    product_receipt["final_product"]["gc_cycle_wall"] = {
        "status": "NOT RUN: CANDIDATE PRODUCT RED",
        "receipt": bind(PREFILTER_RECEIPT)}
    product_receipt["attempt_accounting"]["media_builds"] = 1
    product_receipt["attempt_accounting"]["DWX_prefilter_runs"] = 0
    product_receipt["attempt_accounting"]["product_red_reproduction_runs"] = 1
    product_receipt["review_ready"] = False
    product_receipt["disposition"] = "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
    product_receipt["qualification_red"] = bind(PREFILTER_RECEIPT)
    CARD.RECEIPT.write_bytes(canonical(product_receipt))
    CARD.write_report(product_receipt)
    product_report = CARD.REPORT.read_text(encoding="utf-8").replace(
        f"Status: **{CARD.STATUS}**",
        "Status: **FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE**", 1)
    product_report += ("\nThe packed DWX tail established a product red: the fixed "
        "`$BC90..$BCFF` input owner overlaps live `namelen4`; the r1 pair "
        "is frozen unqualified evidence.\n")
    CARD.REPORT.write_text(product_report, encoding="utf-8")
    CARD.validate(product_receipt, require_dwx=False)
    print("Block 2.6 Card 3: PRODUCT RED raw-owner/BSS overlap; device=0")


def write() -> None:
    require(not PREFILTER_RECEIPT.exists() and not REPORT.exists()
            and not (BUILD / "runtime").exists(), "Card-3 DWX close is one-shot")
    product_input = load(CARD.RECEIPT)
    require(product_input["review_ready"] is False
            and product_input["final_product"]["packed_prefilter"]["status"] == "PENDING"
            and product_input["final_product"]["gc_cycle_wall"]["status"] == "PENDING",
            "Card-3 DWX one-shot boundary is not pending")
    tool = tool_identity()
    product, packed = build_medium()
    ownership = bss_raw_owner_gate(CARD.ELF)
    if ownership["status"] == "RED":
        write_red(product, packed, ownership)
        return
    baseline = load(BASELINE_RECEIPT)
    baseline_medium = ROOT / baseline["medium"]["path"]
    require(bind(baseline_medium) == baseline["medium"], "Card-2 baseline medium drift")
    reference_runs = [measure_one(f"reference-{index + 1}", baseline_medium,
                                  CARD.PREDECESSOR_ELF)
                      for index in range(REPEATS)]
    candidate_runs = [measure_one(f"candidate-{index + 1}", product, CARD.ELF)
                      for index in range(REPEATS)]
    reference, candidate = statistics(reference_runs), statistics(candidate_runs)
    noise = max(reference["noise_span"], candidate["noise_span"])
    delta = candidate["mean"] - reference["mean"]
    require(candidate["mean"] <= reference["mean"] + noise,
            f"GC cycle wall red: delta={delta} noise={noise}")
    wall = {"status": "PASS", "metric": "gc_collect-entry-to-RTS-emulated-CPU-DMA-cycles",
        "reference_runs": reference_runs, "candidate_runs": candidate_runs,
        "reference": reference, "candidate": candidate,
        "delta_mean_cycles": delta, "ratio": candidate["mean"] / reference["mean"],
        "admitted_noise_cycles": noise,
        "claim_limit": "DWX emulator only; no wall-clock, physical-key or device claim"}
    value = {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "baseline": {"receipt": bind(BASELINE_RECEIPT), "medium": bind(baseline_medium),
            "ELF": bind(CARD.PREDECESSOR_ELF)},
        "medium_receipt": bind(MEDIA_RECEIPT), "medium": bind(product),
        "packed_readback": packed, "packed_prefilter": {"status": "PASS",
            "oracle": "framebuffer-plus-stopped-counters", "required_line": "7",
            "required_counters": "88888888"},
        "gc_cycle_wall": wall, "tool_identity": tool,
        "blind_spot_contract": bind(BLIND_CONTRACT),
        "fixture_attribution": {
            "medium_finish_presentation": ("the inherited post-finish print "
                "looked for media.product after the successor had written and "
                "checked absent_INIT/valid_INIT/work"),
            "nonqualifying_attempts": [
                "host orchestration interrupted before a qualifying row",
                "controller returned before the stopped counter read",
                "two fresh-world sequences proved gc_runs stayed zero",
                "live-root prefill exhausted the product heap",
                "six expression-prefill forms collected before the row",
                "20- and 16-pass in-editor warmups collected too early",
                "12-pass in-editor calibration proved gc_runs 0 to 0 to 1"],
            "stopped_read_red": ("the no-wait controller returned to the next "
                "read-line and reset 88888888 to 00000000 before the read"),
            "stopped_read_fix":
                "print 7; print 9; then wait before the next read-line arms",
            "sharp_mutation": "controller-without-terminal-wait"},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "DWX_prefilter_runs": 6, "candidate_media_builds": 1,
                "nonqualifying_prefilter_attempts":
                    NONQUALIFYING_PREFILTER_ATTEMPTS,
            "medium_presentation_reds": 1,
            "device_contacts": 0}}
    PREFILTER_RECEIPT.write_bytes(canonical(value)); REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    product_receipt = load(CARD.RECEIPT)
    product_receipt["final_product"]["packed_prefilter"] = {"status": "PASS",
        "receipt": bind(PREFILTER_RECEIPT), "medium": bind(product),
        "closure_and_generation_coherence": True,
        "framebuffer_oracle": "7", "stopped_counters": "88888888"}
    product_receipt["final_product"]["gc_cycle_wall"] = {"status": "PASS",
        "receipt": bind(PREFILTER_RECEIPT), "reference_mean_cycles": reference["mean"],
        "candidate_mean_cycles": candidate["mean"], "delta_mean_cycles": delta,
        "admitted_noise_cycles": noise, "ratio": wall["ratio"]}
    product_receipt["attempt_accounting"]["DWX_prefilter_runs"] = 6
    product_receipt["attempt_accounting"]["media_builds"] = 1
    product_receipt["review_ready"] = True
    CARD.RECEIPT.write_bytes(canonical(product_receipt)); CARD.write_report(product_receipt)
    CARD.validate(product_receipt)
    print(f"Block 2.6 Card 3: DWX PASS GC={reference['mean']:.0f}->{candidate['mean']:.0f} device=0")


def check() -> None:
    value = load(PREFILTER_RECEIPT)
    if value["status"] == RED_STATUS:
        validate_red(value)
        product = load(CARD.RECEIPT)
        require(product["disposition"] ==
                    "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
                and product["qualification_red"] == bind(PREFILTER_RECEIPT)
                and REPORT.read_text(encoding="utf-8") == red_report(value),
                "Card-3 product-red closure drift")
        CARD.validate(product, require_dwx=False)
        print("Block 2.6 Card 3: PRODUCT-RED CHECK PASS device=0")
        return
    validate(value)
    product = load(CARD.RECEIPT)
    require(product["review_ready"] is True
            and product["final_product"]["packed_prefilter"]["status"] == "PASS"
            and product["final_product"]["gc_cycle_wall"]["status"] == "PASS"
            and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-3 product did not consume DWX closure")
    CARD.check()
    print("Block 2.6 Card 3: DWX CHECK PASS device=0")


def selftest() -> None:
    value = load(PREFILTER_RECEIPT)
    if value["status"] == RED_STATUS:
        cases: dict[str, Callable[[dict[str, Any]], None]] = {
            "conflict-hidden": lambda row: row["fixed_raw_BSS_ownership"].update(
                {"simultaneously_live_violations": []}),
            "GC-blamed": lambda row: row["runtime_reproduction"].update(
                {"gc_runs_after": 1}),
            "pair-promoted": lambda row: row.update({"disposition": "CANDIDATE"}),
            "device-contact-hidden": lambda row: row["attempt_accounting"].update(
                {"device_contacts": 1}),
        }
        rejected = []
        for name, mutate in cases.items():
            trial = deepcopy(value); mutate(trial)
            try:
                validate_red(trial)
            except (PrefilterError, RuntimeError, KeyError, ValueError):
                rejected.append(name)
        require(rejected == list(cases), "Card-3 product-red mutation survived")
        print(f"Block 2.6 Card 3: PRODUCT-RED SELFTEST mutations={len(rejected)}")
        return
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "cycle-rise-hidden": lambda row: row["gc_cycle_wall"]["candidate"].update(
            {"mean": row["gc_cycle_wall"]["reference"]["mean"] +
             row["gc_cycle_wall"]["admitted_noise_cycles"] + 1}),
        "counter-loss-hidden": lambda row: row["gc_cycle_wall"][
            "candidate_runs"][0].update({"stopped_counters": "88888800"}),
        "packed-gate-hidden": lambda row: row["packed_readback"].update({"status": "RED"}),
        "post-input-symbol-oracle-hidden": lambda row: row["gc_cycle_wall"][
            "candidate_runs"][0].update({"post_input_symbol_oracle": 0}),
        "stopped-window-regressed": lambda row: row["fixture_attribution"].update(
            {"stopped_read_fix": "return directly to the next read-line"}),
        "controller-wait-removed": lambda row: row["gc_cycle_wall"][
            "reference_runs"][0]["choreography"].update(
                {"controller": "(string-length(read-line))\n"}),
        "warmup-collected-early": lambda row: row["gc_cycle_wall"][
            "candidate_runs"][0]["choreography"]["warmup"].update(
                {"gc_runs_after": 1}),
        "measured-collection-hidden": lambda row: row["gc_cycle_wall"][
            "candidate_runs"][0].update({"gc_runs_after": 0}),
        "device-contact-hidden": lambda row: row["attempt_accounting"].update(
            {"device_contacts": 1})}
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PrefilterError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-3 DWX mutation survived")
    print(f"Block 2.6 Card 3: DWX SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block 2.6 Card 3 DWX: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
