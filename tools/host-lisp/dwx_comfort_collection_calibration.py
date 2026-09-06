"""Read-only, world-derived allocation calibration for the Comfort C4 row.

The six measured passes are unchanged. Calibration passes count as warmup;
no counter or heap byte is written by the monitor. A GC only in warmup is red.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import time

import dwx_retroactive_red_replay as R
import c2_v210_comfort_media_card as CARD
from elf_truth import ElfTruth


def model(truth, product_elf=None):
    obj = (CARD.ROOT / "src/obj.h").read_text()
    config = (CARD.ROOT / "config/workbench.mk").read_text()
    width = int(re.search(r'sizeof\(Cell\) == (\d+)u, "target hot Cell', obj)[1])
    heap = truth.symbol("heap")
    R.require(heap.bytes % width == 0, "nonintegral product hot heap")
    hot = heap.bytes // width
    threshold = int(re.search(r'-DLISP65_NURSERY_HYSTERESIS=(\d+)', config)[1])
    alloc = truth.symbol("alloc")
    section = truth.sections[alloc.section_index]
    code = truth.section_bytes(section.name)[alloc.value-section.address:alloc.value-section.address+alloc.bytes]
    symbols = {n: truth.symbol(n).value for n in
               ("gc_runs", "allocs_since_gc", "freelist", "gc_frozen")}
    # Verify the current allocator model against the emitted body's operands.
    # A changed codegen form is not silently interpreted as the old policy.
    a, f = symbols["allocs_since_gc"], symbols["gc_frozen"]
    R.require(0 < threshold < 256 and hot * 2 < 256 and max(a, f) < 255,
              "allocator model requires a new operand decoder")
    R.require(bytes((0xa6, a, 0xe0, threshold)) in code and
              bytes((0xc0, hot * 2)) in code and
              bytes((0xa6, f, 0xa4, f+1)) in code,
              "source nursery policy not consumed by final allocator")
    mem = (CARD.ROOT / "src/mem.c").read_text()
    R.require("gc_frozen && freelist != NIL" in mem and
              "#define EXT_OFF(i) ((uint16_t)(((i) - HEAP_CELLS) * 8))" in mem,
              "allocator/extended-cell ABI model changed")
    bank = int(re.search(r'#define EXT_BANK\s+(0x[0-9a-fA-F]+)u',
                         (CARD.ROOT / "src/mem.h").read_text())[1], 16)
    return {"product": R.bind(product_elf or CARD.PRODUCT_ELF), "hot_cells": hot,
            "hot_cell_bytes": width, "heap_address": heap.value,
            "nursery_hysteresis_allocations": threshold, "extended_bank": bank,
            "symbols": symbols, "allocator_emitted_hex": code.hex(),
            "sources": [R.bind(CARD.ROOT / p) for p in
                        ("src/obj.h", "src/mem.h", "src/mem.c", "config/workbench.mk")]}


def sample(m, authority, out, name, chain=False):
    # End-of-paint is not necessarily end-of-handler; require settled counters.
    def read():
        return {n: int.from_bytes(m.memory16(a)[:2], "little")
                for n, a in authority["symbols"].items()}
    deadline = time.monotonic() + 5
    previous = read()
    while True:
        time.sleep(.05)
        current = read()
        if current == previous:
            break
        R.require(time.monotonic() < deadline, "allocator did not settle at input seam")
        previous = current
    m.command("t1")
    try:
        current = read()
        current["capture_raw"] = m.memory16(0xBCFC)[:4].hex()
        if chain:
            cache, nodes, seen = {}, [], set()
            pointer = current["freelist"]
            hot = authority["hot_cells"]
            while pointer:
                R.require(pointer % 2 == 0 and pointer < 0x8000 and pointer not in seen,
                          "invalid/cyclic free-cell chain")
                seen.add(pointer)
                index = pointer // 2
                address = (authority["heap_address"] + index * authority["hot_cell_bytes"] + 1
                           if index < hot else (authority["extended_bank"] << 16) + (index-hot)*8+2)
                raw = bytearray()
                for at in (address, address+1):
                    base = at & ~15
                    if base not in cache:
                        cache[base] = m.memory16(base)
                    raw.append(cache[base][at-base])
                nxt = int.from_bytes(raw, "little")
                nodes.append({"cell": pointer, "link_address": address, "next": nxt})
                pointer = nxt
            current["free_cells"] = len(nodes)
            current["free_chain"] = nodes
            current["raw_blocks"] = {str(k): v.hex() for k,v in cache.items()}
        (out / (name + ".json")).write_text(json.dumps(current, indent=2) + "\n")
        return current
    finally:
        m.command("t0")


def derive(origin, measurements, capture, authority):
    R.require(origin["gc_frozen"] == 0,
              "active nursery requires a separately derived hot-freelist/hysteresis schedule")
    # With gc_frozen == 0 the emitted nursery branch is disabled; the actual
    # free-cell population, not the nominal hysteresis, controls exhaustion.
    increments = []
    before = origin
    for typed, deleted in measurements:
        R.require(typed["gc_runs"] == deleted["gc_runs"] == origin["gc_runs"],
                  "Collection during calibration sample")
        increments.append((typed["allocs_since_gc"]-before["allocs_since_gc"],
                           deleted["allocs_since_gc"]-typed["allocs_since_gc"]))
        before = deleted
    R.require(len(increments) == 2 and increments[0] == increments[1] and
              increments[0][0] > 0 and increments[0][1] >= 0,
              "allocation sample missing, unstable or nonpositive")
    per_pass = sum(increments[0])
    events = len(capture["pattern"]) + capture["delete_events_per_pass"]
    quantum = 256 // math.gcd(events, 256)
    passes = capture["passes"]
    # Choose the smallest modulo-neutral warmup that leaves fewer cells than
    # the measured six passes allocate. Samples are included, never hidden.
    minimum = max(len(measurements), (origin["free_cells"] + 1 - passes*per_pass + per_pass-1)//per_pass)
    warmup = ((minimum + quantum-1)//quantum)*quantum
    remaining = origin["free_cells"] - warmup*per_pass
    R.require(0 < remaining < passes*per_pass and warmup <= origin["free_cells"]//per_pass,
              "no safe modulo-neutral warmup for the bound six-pass window")
    return {"authority": authority, "origin_free_cells": origin["free_cells"],
            "gc_frozen": origin["gc_frozen"], "policy": "freelist-exhaustion; nursery disabled",
            "sample_passes": len(measurements), "sample_increments": increments,
            "printable_cells_per_key": increments[0][0]/len(capture["pattern"]),
            "delete_cells_per_key": increments[0][1]/capture["delete_events_per_pass"],
            "cells_per_pass": per_pass, "warmup_passes": warmup,
            "warmup_counter_modulo": warmup*events % 256,
            "measured_passes": passes, "predicted_remaining_cells": remaining,
            "predicted_window_allocations": passes*per_pass}


def validate_window(origin, start, end):
    R.require(start["gc_runs"] == origin["gc_runs"], "warmup crossed Collection")
    R.require(0 < (end["gc_runs"]-start["gc_runs"]) % 65536 < 32768,
              "no Collection inside measured typing window")


def selftest():
    validate_window({"gc_runs": 4}, {"gc_runs": 4}, {"gc_runs": 5})
    for label, values in (("collection-only-before-window", (4,5,5)),
                          ("no-collection", (4,4,4)),
                          ("warmup-and-window", (4,5,6))):
        try:
            validate_window(*({"gc_runs": n} for n in values))
        except R.ReplayError:
            continue
        raise R.ReplayError("mutation survived: " + label)
    origin = {"gc_frozen": 0, "gc_runs": 4, "allocs_since_gc": 82, "free_cells": 490}
    samples = [({"gc_runs": 4, "allocs_since_gc": 114}, {"gc_runs": 4, "allocs_since_gc": 114}),
               ({"gc_runs": 4, "allocs_since_gc": 146}, {"gc_runs": 4, "allocs_since_gc": 146})]
    capture = {"pattern": "0"*32, "delete_events_per_pass": 32, "passes": 6}
    R.require(derive(origin, samples, capture, {})["warmup_passes"] == 12, "arithmetic control failed")
    cases = [("missing-sample", origin, samples[:1]),
             ("zero-allocation", origin, [(origin, origin)]*2),
             ("unknown-nursery-mode", dict(origin, gc_frozen=1), samples)]
    for label, o, s in cases:
        try:
            derive(o, s, capture, {})
        except R.ReplayError:
            continue
        raise R.ReplayError("mutation survived: " + label)
    print("Comfort Collection window PASS mutations=6")


def calibrate(m, truth, out, capture, pass_fn, product_elf=None):
    authority = model(truth, product_elf)
    origin = sample(m, authority, out, "calibration-origin", chain=True)
    measurements = []
    for i in range(2):
        measurements.append(pass_fn("calibration-sample-"+str(i+1), authority))
    plan = derive(origin, measurements, capture, authority)
    (out / "collection-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    for i in range(2, plan["warmup_passes"]):
        typed, deleted = pass_fn("calibration-warmup-"+str(i+1), authority)
        R.require(deleted["gc_runs"] == origin["gc_runs"] and
                  deleted["allocs_since_gc"]-origin["allocs_since_gc"] == (i+1)*plan["cells_per_pass"],
                  "warmup deviates from measured allocation model")
    start = sample(m, authority, out, "measured-window-start", chain=True)
    R.require(start["capture_raw"] == "00000000" and start["gc_runs"] == origin["gc_runs"] and
              start["free_cells"] == plan["predicted_remaining_cells"],
              "measured-window start differs from derived plan")
    return {"plan": plan, "origin": origin, "start": start}


def verify_chain(state, authority):
    pointer = state["freelist"]
    seen = set()
    for node in state["free_chain"]:
        R.require(pointer == node["cell"] and pointer not in seen and 0 < pointer < 0x8000
                  and pointer % 2 == 0, "free-chain population drift")
        seen.add(pointer)
        index = pointer // 2
        address = (authority["heap_address"] + index*authority["hot_cell_bytes"] + 1
                   if index < authority["hot_cells"] else
                   (authority["extended_bank"] << 16) + (index-authority["hot_cells"])*8+2)
        raw = bytes(bytes.fromhex(state["raw_blocks"][str(at & ~15)])[at & 15]
                    for at in (address, address+1))
        R.require(address == node["link_address"] and int.from_bytes(raw,"little") == node["next"],
                  "free-chain link differs from stopped raw read")
        pointer = node["next"]
    R.require(pointer == 0 and len(seen) == state["free_cells"], "incomplete free-chain count")


def row_binding(out):
    out = out.resolve()
    receipt = R.load(out / "receipt.json")
    # The accepted r2 row remains a receipt of its own executor generation.
    # Only its two executor identities are historical; media, ELF, samples,
    # model operands and all framebuffer/memory oracles are still verified.
    sealed = out == (CARD.ROOT / 'build/v2.1/comfort-collection-calibration-r2').resolve()
    from evidence_era import era_bind
    R.require(receipt["status"] == "EXECUTED ROWS PASS; COMPOSED DISPLAY REVIEW REQUIRED",
              "runtime rows not passed")
    for key in ("executor", "calibration_executor", "product", "medium", "fork", "repair_card", "session_counterparts"):
        if sealed and key in ('executor', 'calibration_executor'):
            expected_path = 'tools/host-lisp/' + ('dwx_comfort_resume.py' if key == 'executor' else 'dwx_comfort_collection_calibration.py')
            expected = era_bind('bbbaed02', expected_path)
            R.require(receipt[key] == expected, 'sealed executor era mismatch: ' + key)
        else:
            R.verify_binding(receipt[key], key)
    session = R.load(CARD.ROOT / receipt["session_counterparts"]["path"])
    capture = next(row for row in session["rows"] if row["id"] == "C4")["collection"]
    data = receipt["collection_calibration"]
    authority = model(ElfTruth.read(CARD.PRODUCT_ELF, llvm_readobj=Path("/usr/bin/llvm-readobj"),
                                   include_section_data=True))
    samples = [(R.load(out / f"calibration-sample-{i}-typed.json"),
                R.load(out / f"calibration-sample-{i}-deleted.json")) for i in (1,2)]
    derived = json.loads(json.dumps(derive(data["origin"], samples, capture, authority)))
    R.require(derived == data["plan"], "world-derived Collection plan drift")
    verify_chain(data["origin"], authority)
    verify_chain(data["start"], authority)
    R.require(data["origin"] == R.load(out / "calibration-origin.json") and
              data["start"] == R.load(out / "measured-window-start.json") and
              data["end"] == R.load(out / "measured-window-end.json"), "window read provenance drift")
    R.require(data["start"]["free_cells"] == derived["predicted_remaining_cells"] and
              data["start"]["capture_raw"] == "00000000", "window origin drift")
    validate_window(data["origin"], data["start"], data["end"])
    for i in range(3, derived["warmup_passes"]+1):
        deleted = R.load(out / f"calibration-warmup-{i}-deleted.json")
        R.require(deleted["gc_runs"] == data["origin"]["gc_runs"] and
                  deleted["allocs_since_gc"]-data["origin"]["allocs_since_gc"] == i*derived["cells_per_pass"],
                  "warmup trace is not derived")
    rows = {row["id"]: row for row in receipt["rows"]}
    for row in receipt["rows"]:
        path = R.verify_binding(row["framebuffer"], row["id"])
        if row["id"].startswith("C4-pass-"):
            from dwx_comfort_resume import active
            expected = capture["pattern"] if row["id"].endswith("-typed") else ""
            R.require(row["active"] == active(path.read_text()) == expected, "Capture visible oracle drift")
    R.require(all(f"C4-pass-{i}-{kind}" in rows for i in range(1,7) for kind in ("typed","deleted")),
              "Capture row population missing")
    count = (derived["measured_passes"]*(len(capture["pattern"])+capture["delete_events_per_pass"])
             +len(capture["final_text"])+1) % 256
    R.require(count != 0 and receipt["stopped"]["capture"]["raw"] == bytes([count]*4).hex(),
              "stopped Capture equality drift")
    for key, binding in receipt["outputs"].items():
        if isinstance(binding, dict) and "sha256" in binding:
            R.verify_binding(binding, key)
    row = deepcopy(next(row for row in session["rows"] if row["id"] == "C4"))
    # A successor binding replaces, never copies, the obsolete allocation
    # assumption. Device acceptance remains a separate use of this row.
    row["collection"] = {"controller": capture["controller"], "pattern": capture["pattern"],
        "delete_events_per_pass": capture["delete_events_per_pass"],
        "warmup_passes": derived["warmup_passes"], "passes": derived["measured_passes"],
        "final_text": capture["final_text"], "expected_each_modulo_256": count,
        "derivation": derived, "required_gc_window": "after warmup, before final-text/Return",
        "observed_gc": [data["origin"]["gc_runs"], data["start"]["gc_runs"], data["end"]["gc_runs"]],
        "rebinding_rule": "execute calibration on the bound world; never inherit warmup length",
        "physical_keyboard_claimed": False}
    return {"status": "COLLECTION ROW PREFILTER GREEN; NOT DEVICE ACCEPTANCE",
            "producer": era_bind('bbbaed02', Path(__file__)) if sealed else R.bind(Path(__file__)), "runtime": R.bind(out / "receipt.json"),
            "medium": receipt["medium"], "product": receipt["product"], "row": row,
            "snapshots": [R.bind(p) for p in sorted(out.glob("calibration-*.json"))] +
                         [R.bind(out / n) for n in ("measured-window-start.json", "measured-window-end.json")],
            "budget": {"wplto": 0, "product_links": 0, "new_media": 0, "device_contacts": 0}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "bind", "check"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    selftest()
    if args.action != "selftest":
        R.require(args.out is not None, "bound runtime directory required")
        path = args.out / "collection-row-binding.json"
        value = row_binding(args.out)
        if args.action == "bind":
            path.write_text(json.dumps(value, indent=2) + "\n")
        else:
            R.require(R.load(path) == value, "Collection row binding drift")
        print(value["status"])
