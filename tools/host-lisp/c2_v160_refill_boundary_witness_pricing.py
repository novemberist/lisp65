#!/usr/bin/env python3
"""Price the v1.6 target refill-boundary witness without linking a product."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/lisp65-c2-substitution-linked.prg.elf")
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-refill-irq-state-intersection.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-display-entry-first-red-attribution.json")
CAPACITY = ELF.parent / "fixed-host-facade-c2-lite-canonical.json"
MAIN_SOURCE = ROOT / "src/main.c"
RUNTIME_SOURCE = ROOT / "src/vm_runtime_overlay.c"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-refill-boundary-witness-pricing.json")
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "8c0bbbd4"
RECORDED_ON = "2026-08-22"
SECTION = ".text.refill_trace_price"

REPL_START = 0xBC87
REPL_BYTES = 192
INPUT_RING_START = 0xBC90
INPUT_RING_END = 0xBD00
TRACE_PREFIX_START = 0xBC87
TRACE_PREFIX_BYTES = 5
TRACE_SLOTS_START = 0xBD00
SLOT_BYTES = 34
SLOT_COUNT = 2
TRACE_BYTES = TRACE_PREFIX_BYTES + SLOT_BYTES * SLOT_COUNT
TARGET_ORDINAL = 765
TARGET_PC = 0x45
TARGET_LENGTH = 21


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def authorization() -> dict[str, Any]:
    row = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{row['commit']}:{row['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    compact = " ".join(raw.lower().split())
    for token in ("refill-boundary witness pricing commissioned",
                  "bound origin and wrap discipline",
                  "repl.buf", "no fix before the witness"):
        require(token in compact, f"pricing authority absent: {token}")
    return row


def assemble(source: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="c2-v160-refill-price-") as raw:
        work = Path(raw)
        asm = work / "trace.s"
        obj = work / "trace.o"
        asm.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(asm), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0,
                f"refill witness assembly red:\n{result.stdout}")
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                              include_section_data=True)
        return truth.section_bytes(SECTION)


def stub_source() -> str:
    return f'''\
\t.section {SECTION},"ax",@progbits
\t.globl vm_runtime_overlay_install_island
\t.globl c2_mapped_far_enter
\t.globl vm_runtime_overlay_install_island_far
\t.globl c2_mapped_far_leave
vm_runtime_overlay_install_island:
\tjsr c2_mapped_far_enter
\tjsr vm_runtime_overlay_install_island_far
\tjmp c2_mapped_far_leave
'''


def body_source(observation: str) -> str:
    require(observation in {"edges", "payload"}, "unknown observation form")
    observed = '''\
\tlda $bfc7
\tsta $bd0d,x
\tlda $bfdb
\tsta $bd0e,x
''' if observation == "edges" else '''\
\tclc
\tlda #$a4
\tadc $bfdd
\tsta $04
\tlda #$bf
\tadc $bfde
\tsta $05
\ttxa
\tclc
\tadc #$0d
\tsta $06
\tlda #$bd
\tadc #$00
\tsta $07
\tldy #$00
.Lcopy:
\tlda ($04),y
\tsta ($06),y
\tiny
\tcpy #$15
\tbne .Lcopy
'''
    return f'''\
\t.section {SECTION},"ax",@progbits
\t.globl c2_refill_trace_body
\t.globl c2_product_entry_read
c2_refill_trace_body:
\tpha
\tphx
\tlda $b9b4
\tcmp #$fd
\tbne .Lpass
\tlda $b9b5
\tcmp #$02
\tbne .Lpass
\tlda $bfe9
\tcmp #$45
\tbne .Lpass
\tlda $bfea
\tbne .Lpass
\tlda $bfeb
\tcmp #$15
\tbne .Lpass
\tlda $bfec
\tbne .Lpass
\tldx $bc87
\tstz $bd00,x
\tinc $bc88
\tlda $bc88
\tsta $bd01,x
\tlda $b9b4
\tsta $bd02,x
\tlda $b9b5
\tsta $bd03,x
\tlda $bfe9
\tsta $bd04,x
\tlda $bfea
\tsta $bd05,x
\tlda $bfeb
\tsta $bd06,x
\tlda $bfec
\tsta $bd07,x
\tstz $bd08,x
\tlda $ff83
\tsta $bd09,x
\tlda $ff84
\tsta $bd0a,x
\tstx $bc8a
\tcpx #$00
\tbne .Lnext_zero
\tldx #${SLOT_BYTES:02x}
\tbra .Lnext_store
.Lnext_zero:
\tldx #$00
\tinc $bc89
.Lnext_store:
\tstx $bc87
\tplx
\tpla
\tjsr c2_product_entry_read
\tpha
\tldx $bc8a
\tsta $bd08,x
\tlda $ff83
\tsta $bd0b,x
\tlda $ff84
\tsta $bd0c,x
{observed}\
\tlda #$a5
\tsta $bd00,x
\tpla
\trts
.Lpass:
\tplx
\tpla
\tjmp c2_product_entry_read
'''


def ring_model() -> dict[str, Any]:
    slots = [bytearray(SLOT_BYTES) for _ in range(SLOT_COUNT)]
    header = {"next": 0, "sequence": 0, "wraps": 0,
              "active": 0xFF, "origin_commit": 0}

    # Atomic origin: capture is closed externally; all slot commits are first
    # invalidated, indices are reset, and the origin tag is published last.
    for slot in slots:
        slot[0] = 0
    header.update(next=0, sequence=0, wraps=0, active=0xFF)
    header["origin_commit"] = 0xA5

    def record(payload: bytes, *, status: int = 1) -> None:
        require(len(payload) == TARGET_LENGTH, "fixture payload length drift")
        index = header["next"] // SLOT_BYTES
        slot = slots[index]
        slot[0] = 0
        header["sequence"] = (header["sequence"] + 1) & 0xFF
        slot[1] = header["sequence"]
        slot[2:4] = TARGET_ORDINAL.to_bytes(2, "little")
        slot[4:6] = TARGET_PC.to_bytes(2, "little")
        slot[6:8] = TARGET_LENGTH.to_bytes(2, "little")
        slot[8] = status
        slot[9:11] = (17 + header["sequence"]).to_bytes(2, "little")
        slot[11:13] = (18 + header["sequence"]).to_bytes(2, "little")
        slot[13:34] = payload
        header["active"] = header["next"]
        header["next"] ^= SLOT_BYTES
        if header["next"] == 0:
            header["wraps"] = (header["wraps"] + 1) & 0xFF
        slot[0] = 0xA5

    payloads = [bytes([seed] + list(range(1, 20)) + [seed ^ 0xFF])
                for seed in (0x10, 0x20, 0x30)]
    for payload in payloads:
        record(payload)
    committed = sorted(
        [{"sequence": slot[1], "payload_sha256": sha(bytes(slot[13:34]))}
         for slot in slots if slot[0] == 0xA5],
        key=lambda row: row["sequence"])
    require([row["sequence"] for row in committed] == [2, 3]
            and header["wraps"] == 1 and header["origin_commit"] == 0xA5,
            "two-slot overwrite/wrap model drift")
    torn = deepcopy(slots)
    torn[header["active"] // SLOT_BYTES][0] = 0
    require(sum(slot[0] == 0xA5 for slot in torn) == 1,
            "commit-last torn-slot rejection drift")
    return {"origin": header, "committed_after_three_records": committed,
            "wrap_policy": ("two slots overwrite oldest; sequence and wrap are "
                            "uint8 modulo 256; the contact must stop before 256 wraps"),
            "torn_last_slot_rejected": True}


def validate(value: dict[str, Any]) -> None:
    winner = value["winner"]
    require(winner["observation"] == "full 21-byte payload snapshot"
            and winner["new_resident_state_bytes"] == 0
            and winner["trace_alias_bytes"] == 73
            and winner["mapped_diagnostic_capacity_bytes"] == 371
            and winner["mapped_diagnostic_used_bytes"] == 211
            and winner["mapped_diagnostic_headroom_bytes"] == 160
            and winner["ordinary_text_headroom_after_bytes"] == 3,
            "winner price drift")
    require(value["alternatives"]["first_last"]["verdict"] ==
            "REJECTED: MIDDLE-BYTE DIFFERENCE SURVIVES",
            "first/last oracle was accepted")
    require(value["origin_and_wrap"]["origin"]["origin_commit"] == 0xA5
            and value["origin_and_wrap"]["torn_last_slot_rejected"] is True,
            "bound origin/commit-last discipline drift")
    require(value["card_lock"] == {"product_sources_changed": 0,
                                   "WPLTO_runs": 0, "product_links": 0,
                                   "media_builds": 0, "device_contacts": 0},
            "pricing crossed its claim boundary")


def derive() -> dict[str, Any]:
    authorization_row = authorization()
    predecessor = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(predecessor["decision"]["class"] ==
            "NOT REGISTER-FORM IRQ CORRUPTION", "predecessor drift")
    runtime = first_red["device_result"]["runtime_identities"]["%repl-step"]
    window = first_red["device_result"]["VM_window"]
    require(runtime["directory"] == TARGET_ORDINAL
            and window["window_start"] == TARGET_PC
            and window["window_length"] == TARGET_LENGTH,
            "target seam identity drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    repl = truth.symbol("repl.buf")
    require(repl.value == REPL_START and repl.bytes == REPL_BYTES,
            "repl.buf geometry drift")
    require(INPUT_RING_END <= TRACE_SLOTS_START
            and TRACE_SLOTS_START + SLOT_BYTES * SLOT_COUNT <= repl.value + repl.bytes
            and TRACE_PREFIX_START + TRACE_PREFIX_BYTES <= INPUT_RING_START,
            "trace aliases live input-ring storage")
    alias_free = ((INPUT_RING_START - repl.value)
                  + (repl.value + repl.bytes - INPUT_RING_END))
    require(alias_free == 80 and TRACE_BYTES == 73,
            "scratch-alias price drift")

    capacity = json.loads(CAPACITY.read_text(encoding="utf-8"))
    measurements = capacity["fixed_block_rtov_fail_leaf"]["VMA_golden"][
        "capacity_measurements"]
    by_id = {row["id"]: row for row in measurements}
    require(by_id["ordinary-text"]["candidate_headroom_bytes"] == 6
            and by_id["mapped-bank2-far-service"]["candidate_headroom_bytes"] == 15
            and by_id["resident-island"]["candidate_headroom_bytes"] == 50,
            "thin-arena authority drift")
    service = truth.section(".lisp65_c2_mapped_far_service")
    require(service.address == 0x78B2 and service.bytes == 1484,
            "mapped far-service geometry drift")
    mapped_block_end = 0x8000
    second_arena_start = 0x7E8D  # fixed 1499-byte contract end
    second_arena_capacity = mapped_block_end - second_arena_start
    require(service.address + 1499 == second_arena_start
            and second_arena_capacity == 371,
            "adjacent mapped diagnostic arena geometry drift")

    mover = truth.symbol("vm_runtime_overlay_install_island")
    require(mover.section == ".text" and mover.value == 0xA8FE
            and mover.bytes == 211, "cold relocation candidate drift")
    incoming = []
    outgoing_calls = []
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        if identity.get("resolved_value") == mover.value:
            incoming.append({"section": relocation.source_section,
                             "offset": relocation.offset})
        if (relocation.source_section == mover.section
                and mover.value <= relocation.offset < mover.value + mover.bytes
                and relocation.relocation_type == "R_MOS_ADDR16"):
            target = identity.get("resolved_value")
            if target in {0xB347, 0x290D, 0xC245}:
                outgoing_calls.append(target)
    require(incoming == [{"section": ".text", "offset": 0xA5EA}]
            and sorted(set(outgoing_calls)) == [0x290D, 0xB347, 0xC245]
            and all(not 0x6000 <= value < 0x8000 for value in outgoing_calls),
            "cold relocation call graph/MAP visibility drift")
    main_source = MAIN_SOURCE.read_text(encoding="utf-8")
    require(main_source.count("vm_runtime_overlay_install_island()") == 1
            and main_source.index("c2_product_prepare_boot()")
            < main_source.index("vm_runtime_overlay_install_island()"),
            "cold relocation materialization order drift")

    stub = assemble(stub_source())
    edge = assemble(body_source("edges"))
    payload = assemble(body_source("payload"))
    require(len(stub) == 9 and len(payload) > len(edge),
            "emitted witness price ordering drift")
    ordinary_before = by_id["ordinary-text"]["candidate_headroom_bytes"]
    ordinary_after = ordinary_before + mover.bytes - len(stub) - len(payload)
    require(ordinary_after == 3, "winner ordinary-text arithmetic drift")

    middle_a = bytes([0x11] + [0x22] * 19 + [0x33])
    middle_b = bytearray(middle_a)
    middle_b[10] ^= 0xFF
    require((middle_a[0], middle_a[-1]) == (middle_b[0], middle_b[-1])
            and middle_a != bytes(middle_b),
            "first/last collision control drift")

    result = {
        "format": "lisp65-c2.3-v1.6-refill-boundary-witness-pricing-v1",
        "recorded_on": RECORDED_ON,
        "status": "PRICED: FULL-PAYLOAD TWO-SLOT WITNESS FITS WITH ONE COLD RELOCATION",
        "authority": {"owner": authorization_row,
                      "candidate_ELF": bind(ELF),
                      "predecessor": bind(PREDECESSOR),
                      "first_red": bind(FIRST_RED),
                      "capacity_authority": bind(CAPACITY),
                      "boot_order_source": bind(MAIN_SOURCE),
                      "cold_body_source": bind(RUNTIME_SOURCE),
                      "pricing_tool": bind(Path(__file__).resolve())},
        "target_seam": {"window_id": TARGET_ORDINAL,
                        "logical_offset": TARGET_PC,
                        "length": TARGET_LENGTH,
                        "source": "Same-World %repl-step manifest/runtime directory"},
        "storage": {
            "owner": "repl.buf lifetime alias while native REPL is inactive",
            "repl_buf": {"start": f"${repl.value:04X}", "bytes": repl.bytes},
            "active_input_ring": {"start": "$BC90", "end_exclusive": "$BD00"},
            "free_alias_bytes": alias_free,
            "trace_prefix": {"start": "$BC87", "bytes": TRACE_PREFIX_BYTES,
                             "fields": ["next", "sequence", "wraps", "active",
                                        "origin_commit"]},
            "trace_slots": {"start": "$BD00", "count": SLOT_COUNT,
                            "bytes_each": SLOT_BYTES, "bytes": SLOT_BYTES * SLOT_COUNT},
            "unclaimed_alias_bytes": alias_free - TRACE_BYTES,
            "new_resident_state_bytes": 0,
        },
        "slot_schema": [
            "commit", "sequence", "window-id:u16", "offset:u16", "length:u16",
            "result", "start-frame:u16", "end-frame:u16", "payload[21]"],
        "origin_and_wrap": ring_model(),
        "emitted_prices": {
            "cold_relocation_stub_bytes": len(stub),
            "first_last_body_bytes": len(edge),
            "full_payload_body_bytes": len(payload),
            "measurement": "standalone mos45gs02 assembly, no product link",
        },
        "alternatives": {
            "first_last": {
                "body_bytes": len(edge), "trace_alias_bytes": 35,
                "verdict": "REJECTED: MIDDLE-BYTE DIFFERENCE SURVIVES",
                "control": {"same_edges": True, "different_middle": True}},
            "crc16": {
                "verdict": "REJECTED FOR THIS WITNESS: EXTRA 168-BIT-STEP LATENCY",
                "reason": ("the existing CRC16 leaf is source-authoritative but adds "
                           "eight bit rounds per byte at the seam whose timing remains open")},
            "new_resident_ring": {
                "verdict": "DOMINATED",
                "bytes": TRACE_BYTES,
                "reason": "the proven repl.buf lifetime alias supplies all 73 bytes"},
        },
        "winner": {
            "observation": "full 21-byte payload snapshot",
            "request": "window id, logical offset and length recorded per refill",
            "result": "return status, start/end frame and exact observed payload",
            "trace_alias_bytes": TRACE_BYTES,
            "new_resident_state_bytes": 0,
            "cold_relocation": {
                "symbol": mover.name, "body_bytes": mover.bytes,
                "ordinary_stub_bytes": len(stub),
                "ordinary_net_reclaim_bytes": mover.bytes - len(stub),
                "incoming_edges": ["$A5EA"],
                "temperature": "one runtime-overlay island-install edge; no refill/key/eval edge",
                "availability": ("the sole main call follows c2_product_prepare_boot; "
                                 "the second arena must be materialized in the same "
                                 "Bank-2 static plane before that call"),
                "mapped_callees": ["$290D", "$B347", "$C245"],
                "callee_visibility": "all outside mapped CPU block 3",
            },
            "witness_body_bytes": len(payload),
            "mapped_diagnostic_arena": "$7E8D..$7FFF",
            "mapped_diagnostic_capacity_bytes": second_arena_capacity,
            "mapped_diagnostic_used_bytes": mover.bytes,
            "mapped_diagnostic_headroom_bytes": second_arena_capacity - mover.bytes,
            "ordinary_text_headroom_before_bytes": ordinary_before,
            "ordinary_text_headroom_after_bytes": ordinary_after,
            "ordinary_text_net_growth_bytes": ordinary_before - ordinary_after,
            "ordinary_text_headroom_delta_bytes": ordinary_after - ordinary_before,
            "existing_far_service_delta_bytes": 0,
            "E000_delta_bytes": 0,
            "resident_island_delta_bytes": 0,
            "callsite_form": ("retarget only the existing WIN_ENSURE product-read JSR "
                              "to the ordinary trace wrapper; no callsite growth"),
            "timing_price": ("one target-filtered wrapper call plus a 21-byte linear "
                             "snapshot; no CRC loop and no IRQ-path work"),
        },
        "implementation_gates_if_authorized": [
            "cold relocation stub is exactly 9 bytes and preserves the mapped-far ABI",
            "the 211-byte cold body lies wholly in the derived $7E8D..$7FFF second arena",
            "the second arena is materialized with the Bank-2 static plane before the sole main call",
            "its sole caller and all three callees retain visibility under the MAP tuple",
            "only the WIN_ENSURE product-read edge is retargeted",
            "origin is published atomically while capture is closed",
            "slot commit is written last; torn slot is rejected",
            "two-slot wrap and uint8 sequence/wrap interpretation are receipt-bound",
            "payload bytes compare exactly with the Same-World medium",
        ],
        "removal_or_retention": {
            "recommendation": "REMOVE AFTER ATTRIBUTION",
            "removal_cost": ("restore one JSR target and the cold mover's ordinary body; "
                             "remove its 9-byte stub, the witness body and Comfort-origin "
                             "pokes; repl.buf alias returns without migration"),
            "retention_case": ("weak: this is seam-specific forensic telemetry, consumes "
                               "mapped Bank-2 code and adds work to a hot refill; unlike "
                               "input counters it has no standing user-health meaning"),
        },
        "decision_power": {
            "result_zero_or_uncommitted": "refill returned failure or never completed",
            "committed_payload_differs": "refill returned bytes different from Same-World source",
            "committed_payload_matches": ("content is correct; start/end frame ordering leaves "
                                          "a time-shaped target-only failure"),
        },
        "card_lock": {"product_sources_changed": 0, "WPLTO_runs": 0,
                      "product_links": 0, "media_builds": 0,
                      "device_contacts": 0},
        "claim_boundary": ("Pricing only. The emitted micro-sections establish byte cost, "
                           "not product correctness. No witness, fix, link, medium or "
                           "device contact is authorized by this receipt."),
    }
    validate(result)
    return result


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-new-state": lambda x: x["winner"].update(new_resident_state_bytes=73),
        "accept-first-last": lambda x: x["alternatives"]["first_last"].update(
            verdict="ACCEPTED"),
        "erase-origin": lambda x: x["origin_and_wrap"]["origin"].update(
            origin_commit=0),
        "spend-link": lambda x: x["card_lock"].update(product_links=1),
        "overstate-ordinary-headroom": lambda x: x["winner"].update(
            ordinary_text_headroom_after_bytes=4),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "pricing mutation survived")
    return rejected


def main(argv: list[str]) -> int:
    require(len(argv) == 2 and argv[1] in {"check", "write"},
            "usage: c2_v160_refill_boundary_witness_pricing.py check|write")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if argv[1] == "write":
        OUT.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    else:
        require(OUT.is_file(), f"pricing receipt absent: {OUT}")
        require(json.loads(OUT.read_text(encoding="utf-8")) == value,
                "recorded pricing drift")
    print("v1.6 refill witness pricing: PASS storage=73/80 new-state=0 "
          f"ordinary={value['winner']['ordinary_text_headroom_after_bytes']} "
          f"mapped={value['winner']['mapped_diagnostic_used_bytes']}/371")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (PricingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 refill witness pricing: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
