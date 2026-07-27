#!/usr/bin/env python3
"""Contract probe and permanent gate for append suffix/source domains."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-append-suffix-read-domain-contract.json"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
HEADER = ROOT / "scripts/c2-stream-decoder.h"
RUNTIME = ROOT / "src/c2_product_runtime.c"
PHASES = ("06a", "06b", "07", "08")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = text.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated function: {signature}")


def compact(text: str) -> str:
    return "".join(text.split())


def visit(first: int, count: int) -> list[int]:
    require(0 <= first <= count <= 64, "invalid image interval")
    return list(range(first, count))


def domain_accepts(*, ready: bool, append_active: bool, tagged: bool,
                   offset: int, length: int, attic: int,
                   transaction_length: int) -> bool:
    if length < 0 or offset < 0 or attic < 0 or transaction_length < 0:
        return False
    if not ready:
        return True
    if not append_active or not tagged:
        return False
    end = attic + transaction_length
    return (end <= 0x100000 and attic <= offset <= end
            and length <= end - offset)


def fixture() -> dict[str, Any]:
    boot = visit(0, 6)
    persistent = visit(6, 7)
    transient = visit(63, 64)
    domains = {
        "boot_shelf": domain_accepts(ready=False, append_active=False,
                                     tagged=False, offset=32, length=32,
                                     attic=0, transaction_length=0),
        "append_owned_start": domain_accepts(
            ready=True, append_active=True, tagged=True,
            offset=0x1200, length=32, attic=0x1200,
            transaction_length=0x200),
        "append_owned_end": domain_accepts(
            ready=True, append_active=True, tagged=True,
            offset=0x13e0, length=32, attic=0x1200,
            transaction_length=0x200),
        "ready_shelf_rejected": not domain_accepts(
            ready=True, append_active=True, tagged=False,
            offset=32, length=32, attic=0x1200,
            transaction_length=0x200),
        "foreign_context_rejected": not domain_accepts(
            ready=True, append_active=False, tagged=True,
            offset=0x1200, length=32, attic=0x1200,
            transaction_length=0x200),
        "below_span_rejected": not domain_accepts(
            ready=True, append_active=True, tagged=True,
            offset=0x11ff, length=1, attic=0x1200,
            transaction_length=0x200),
        "above_span_rejected": not domain_accepts(
            ready=True, append_active=True, tagged=True,
            offset=0x13ff, length=2, attic=0x1200,
            transaction_length=0x200),
        "wrapped_span_rejected": not domain_accepts(
            ready=True, append_active=True, tagged=True,
            offset=0xfffff0, length=1, attic=0xfffff0,
            transaction_length=0x20),
    }
    require(boot == [0, 1, 2, 3, 4, 5]
            and persistent == [6] and transient == [63]
            and all(domains.values()), "suffix/domain fixture drift")
    return {
        "status": "passed-boot-full-and-append-suffix-domain-matrix",
        "boot": boot,
        "persistent_append": persistent,
        "transient_append": transient,
        "domain_cases": domains,
        "cases_passed": 11,
    }


def probe() -> dict[str, Any]:
    decoder = DECODER.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    require("A session append validates and resolves only the newly staged suffix"
            in header, "decoder suffix contract absent")
    observed = {}
    for phase in PHASES:
        body = compact(function_body(
            decoder, f"C2_SLICE({phase}) uint8_t c2_stream_phase_{phase}("))
        observed[phase] = (
            "image_first" if
            "for(image=c->image_first;image<c->image_count;++image)" in body
            else "zero" if
            "for(image=0;image<c->image_count;++image)" in body
            else "unknown")
    require(observed == {phase: "zero" for phase in PHASES},
            f"pre-fix four-phase observation drift: {observed}")
    require("append.resolution_cursor = old_res" in runtime
            and "w->append.resolution_cursor = w->old_res" in runtime
            and "w->append.resolution_cursor = w->new_res" in runtime,
            "append resolution cursor does not begin at its suffix")
    return {
        "status": "passed-contract-classification-before-product-fix",
        "observed_current_lower_bounds": observed,
        "required_lower_bounds": {phase: "image_first" for phase in PHASES},
        "reason": {
            "06a": "only newly staged code/literal structure is unproved",
            "06b": "only newly staged export spellings are unproved",
            "07": "resolution_cursor already begins at old_res/new_res",
            "08": "pair resolution must close that same suffix at resolution_count",
        },
        "boot_preservation": "image_first is zero during full staging",
        "fixture": fixture(),
        "product_bytes_changed": 0,
        "compiler_runs": 0,
        "linker_runs": 0,
    }


def source_gate(parts: dict[str, str] | None = None,
                *, mutations: bool = False) -> dict[str, Any]:
    text = parts or {
        "decoder": DECODER.read_text(encoding="utf-8"),
        "header": HEADER.read_text(encoding="utf-8"),
        "runtime": RUNTIME.read_text(encoding="utf-8"),
    }
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] == "lisp65.c2.append-suffix-read-domain.v1"
            and list(contract["classification"]) == list(PHASES)
            and contract["capacity"]["new_state_bytes"] == 0
            and contract["capacity"]["resident_window_delta_bytes"] == 0,
            "suffix read-domain contract drift")
    bodies = {}
    for phase in PHASES:
        body = compact(function_body(
            text["decoder"],
            f"C2_SLICE({phase}) uint8_t c2_stream_phase_{phase}("))
        require(body.count(
            "for(image=c->image_first;image<c->image_count;++image)") == 1
            and "for(image=0;image<c->image_count;++image)" not in body,
            f"phase {phase} is not suffix-bound")
        bodies[phase] = body
    read = compact(function_body(
        text["runtime"],
        "C2_KERNAL_RESIDENT uint8_t c2_stream_shelf_read("))
    seam_fragments = (
        "uint32_tbase=LISP65_C2_SHELF_PHYSICAL;",
        "uint32_tlimit=(uint32_t)LISP65_C2_PRODUCT_SHELF_BYTES;",
        "if(offset&C2_SESSION_SOURCE_TAG){",
        "offset&=~C2_SESSION_SOURCE_TAG;",
        "base=LISP65_C2_SESSION_PHYSICAL;limit=LISP65_C2_SESSION_BYTES;}",
        "if(offset>limit||length>limit-offset)return0;",
        "c2_dma_copy(base+offset,",
    )
    require(all(fragment in read for fragment in seam_fragments)
            and "c2_ready" not in read and "c2aw." not in read
            and read.count("offset&=~C2_SESSION_SOURCE_TAG;") == 1,
            "Link-54 resident source-read seam was not restored")

    guard = compact(function_body(
        text["runtime"],
        "uint8_t c2_append_source_domain_guard("))
    guard_fragments = (
        "if(!c)return0;",
        "if(!c2_ready)return(uint8_t)!c->image_first;",
        "if(!c->image_first||c!=&c2aw.append||c2_decode_active!=c"
            "||!c2aw.staged||!c2aw.length)return0;",
        "base=c2aw.attic;",
        "return(uint8_t)(base<=LISP65_C2_SESSION_BYTES"
            "&&c2aw.length<=LISP65_C2_SESSION_BYTES-base);",
    )
    require(all(fragment in guard for fragment in guard_fragments),
            "cold phase-04 source-domain guard drift")
    guard_at = text["runtime"].index(
        "uint8_t c2_append_source_domain_guard(")
    require("section(\".lisp65_rt_c2d_04\")" in compact(
                text["runtime"][max(0, guard_at - 180):guard_at]),
            "cold source-domain guard lost its phase-04 section")
    phase04 = compact(function_body(
        text["decoder"], "C2_SLICE(04) uint8_t c2_stream_phase_04("))
    require("||!c2_append_source_domain_guard(c)" in phase04
            and phase04.index("c2_append_source_domain_guard(c)")
                < phase04.index("c2_image_read(c,image,im)")
            and phase04.index("c2_append_source_domain_guard(c)")
                < phase04.index("c2_stream_shelf_read("),
            "phase 04 can reach a source consumer before the cold guard")

    entries = compact(function_body(
        text["runtime"],
        "C2_APPEND_SECTION(\"entries\") uint8_t c2_append_entries_phase("))
    require("w->append=c2_runtime;" in entries
            and "w->append.shelf_bytes=" not in entries
            and "w->append.c2d_bytes=" not in entries
            and "C2_SESSION_SOURCE_TAG" not in entries,
            "Append entries materialized a second source-domain truth")
    header = compact(function_body(
        text["runtime"],
        "C2_APPEND_SECTION(\"header\") uint8_t c2_append_header_phase("))
    require("w->append.shelf_bytes=" not in header
            and "w->append.c2d_bytes=" not in header
            and "c2_runtime=w->append;" in header,
            "Append header no longer publishes the canonical context directly")

    image_read = compact(function_body(
        text["runtime"],
        "C2_KERNAL_RESIDENT uint8_t c2_stream_product_image_read("))
    image_fragments = (
        "if(c!=&c2aw.append||!c2aw.staged",
        "||image<c2aw.append.image_first",
        "||image>=c2aw.append.image_count)return0;",
        "tag=C2_SESSION_SOURCE_TAG;",
        "code=c2aw.attic+c2aw.code_off;",
        "meta=c2aw.attic+c2aw.meta_off;",
        "code|=tag;meta|=tag;",
    )
    require(all(fragment in image_read for fragment in image_fragments),
            "suffix image coordinates no longer derive from the active append")
    envelope = compact(function_body(
        text["runtime"],
        "C2_APPEND_SECTION(\"envelope\") uint8_t c2_append_envelope_phase("))
    require("(uint32_t)w->meta_off+w->meta_len!=w->length" in envelope
            and "w->code_off!=64u" in envelope
            and "w->meta_off!=(uint16_t)(w->code_off+w->code_len)" in envelope,
            "append metadata no longer bounds every subordinate source interval")
    scan = compact(function_body(
        text["runtime"],
        "uint8_t c2_append_publish_plan_scan_phase("))
    resolve = compact(function_body(
        text["runtime"],
        "uint8_t c2_append_publish_plan_resolve_phase("))
    require("!w->append.finished" in scan
            and "C2AW_PLAN_MARK(w)!=C2_EXPORT_PLAN_MARK" in resolve,
            "source-consuming publication can bypass completed guarded decode")

    driver = compact(function_body(
        text["runtime"],
        "static C2_KERNAL_RESIDENT uint8_t c2_decode_from("))
    sequence = (
        "LISP65_C2_PHASE_04_SLOT", "LISP65_C2_PHASE_05A_SLOT",
        "LISP65_C2_PHASE_05B_SLOT", "LISP65_C2_PHASE_06A_SLOT",
        "LISP65_C2_PHASE_06B_SLOT", "LISP65_C2_PHASE_07_SLOT",
        "LISP65_C2_PHASE_08_SLOT", "LISP65_C2_PHASE_09_SLOT",
    )
    positions = [driver.index(name) for name in sequence]
    require(positions == sorted(positions),
            "serial decoder no longer dominates suffix consumers from phase 04")
    begin_signature = "static C2_KERNAL_RESIDENT uint8_t c2_append_begin("
    begin_at = text["runtime"].rfind(begin_signature)
    require(begin_at >= 0, "sliced append driver absent")
    begin_end = text["runtime"].find(
        "static uint8_t c2_append_rollback(", begin_at)
    require(begin_end > begin_at, "sliced append driver end absent")
    begin = compact(text["runtime"][begin_at:begin_end])
    require("c2_decode_active=&c2aw.append;"
            "if(!c2_decode_from(&c2aw.append,4u)" in begin,
            "post-READY decoder bypasses the active append context")
    require("A session append validates and resolves only the newly staged suffix"
            in text["header"], "suffix context contract drift")

    rejected: dict[str, str] = {}
    if mutations:
        trials: dict[str, dict[str, str]] = {}

        def replace(name: str, owner: str, old: str, new: str) -> None:
            require(old in text[owner], f"mutation anchor absent: {name}")
            trial = dict(text)
            trial[owner] = trial[owner].replace(old, new, 1)
            trials[name] = trial

        for phase in PHASES:
            signature = f"C2_SLICE({phase}) uint8_t c2_stream_phase_{phase}("
            start = text["decoder"].index(signature)
            loop = "for (image = c->image_first; image < c->image_count; ++image)"
            at = text["decoder"].index(loop, start)
            trial = dict(text)
            trial["decoder"] = (text["decoder"][:at]
                + "for (image = 0; image < c->image_count; ++image)"
                + text["decoder"][at + len(loop):])
            trials[f"phase{phase}-starts-at-zero"] = trial
        replace("boot-skips-image-zero", "header",
                "A session append validates and resolves only the newly staged suffix",
                "A boot and session append validate an implementation-selected suffix")
        signature = "C2_SLICE(06a) uint8_t c2_stream_phase_06a("
        start = text["decoder"].index(signature)
        loop = "for (image = c->image_first; image < c->image_count; ++image)"
        at = text["decoder"].index(loop, start)
        trial = dict(text)
        trial["decoder"] = (text["decoder"][:at]
            + "for (image = c->image_first - 1u; image < c->image_count; ++image)"
            + text["decoder"][at + len(loop):])
        trials["append-reads-prefix"] = trial
        replace("ready-accepts-shelf-domain", "runtime",
                "if (!c2_ready) return (uint8_t)!c->image_first;",
                "if (!c2_ready || !c->image_first) return 1;")
        replace("ready-accepts-missing-session-tag", "runtime",
                "tag = C2_SESSION_SOURCE_TAG;",
                "tag = 0u;")
        replace("ready-accepts-foreign-decode-context", "runtime",
                "c != &c2aw.append || c2_decode_active != c",
                "0 && (c != &c2aw.append || c2_decode_active != c)")
        replace("ready-accepts-before-transaction-span", "runtime",
                "code = c2aw.attic + c2aw.code_off;",
                "code = c2aw.code_off;")
        replace("ready-accepts-after-transaction-span", "runtime",
                "c2aw.length <= LISP65_C2_SESSION_BYTES - base",
                "c2aw.length <= LISP65_C2_SESSION_BYTES")
        replace("ready-accepts-wrapped-transaction-span", "runtime",
                "c2aw.length <= LISP65_C2_SESSION_BYTES - base",
                "base + c2aw.length <= LISP65_C2_SESSION_BYTES")
        replace("domain-failure-starts-dma", "decoder",
                "|| !c2_append_source_domain_guard(c)",
                "|| (c2_stream_shelf_read(0u, im, 1u), "
                "!c2_append_source_domain_guard(c))")

        for name, trial in trials.items():
            try:
                source_gate(trial, mutations=False)
            except (GateError, KeyError, ValueError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"suffix/domain mutation accepted: {name}")
        expected = {name.replace("_", "-")
                    for name in contract["required_mutations"]}
        require(set(rejected) == expected,
                f"suffix/domain mutation inventory drift: {sorted(rejected)}")

    return {
        "status": "passed-four-phase-suffix-and-source-domain-contract",
        "phases": {phase: "image_first" for phase in PHASES},
        "fixture": fixture(),
        "negative_mutations": rejected,
        "new_state_bytes": 0,
        "resident_window_delta_required_bytes": 0,
        "cold_barrier": {
            "authority": "active c2aw transaction scratch",
            "consumer_root": "c2_stream_phase_04",
            "successors": list(sequence[1:]),
            "handoff_bytes": 0,
            "canonical_context_publication": "c2_append_header_phase",
            "dataflow": (
                "active transaction -> Session-kind suffix image -> tagged "
                "code/metadata -> validated subordinate intervals"),
        },
    }


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj)
    rows = {}
    for phase in PHASES:
        symbol = truth.symbol(f"c2_stream_phase_{phase}")
        require(symbol.symbol_type == "Function" and 0 < symbol.bytes <= 1792,
                f"linked suffix phase drift: {phase}")
        rows[phase] = {"section": symbol.section, "address": symbol.value,
                       "bytes": symbol.bytes,
                       "headroom_bytes": 1792 - symbol.bytes}
    read = truth.symbol("c2_stream_shelf_read")
    require(read.symbol_type == "Function" and read.bytes == 209
            and read.section == ".lisp65_c2_kernal_window.c2_resident",
            "Link-54 resident source-read seam identity drift")
    guard = truth.symbol("c2_append_source_domain_guard")
    phase04 = truth.symbol("c2_stream_phase_04")
    require(guard.symbol_type == "Function" and guard.bytes > 0
            and guard.section == ".lisp65_rt_c2d_04"
            and phase04.section == guard.section,
            "cold source-domain guard is not co-resident with phase 04")
    calls = [row for row in truth.relocations
             if row.target_symbol_index == guard.index
             and row.source_section_index == phase04.section_index
             and phase04.value <= row.offset < phase04.value + phase04.bytes]
    require(len(calls) == 1,
            "phase 04 must have exactly one linked guard edge")
    entries = truth.symbol("c2_append_entries_phase")
    header = truth.symbol("c2_append_header_phase")
    require(entries.section == ".lisp65_rt_c2append_entries"
            and header.section == ".lisp65_rt_c2append_header",
            "Append producer or canonical publication left the Session Store")
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(scratch.bytes == 304, "suffix/domain fix changed phase scratch")
    return {
        "status": "passed-linked-four-phase-suffix-domain-closure",
        "phases": rows,
        "source_read": {"section": read.section, "address": read.value,
                        "bytes": read.bytes},
        "cold_guard": {"section": guard.section, "address": guard.value,
                       "bytes": guard.bytes, "phase04_call_edges": len(calls)},
        "append_entries": {"section": entries.section,
                           "address": entries.value, "bytes": entries.bytes},
        "append_header": {"section": header.section,
                          "address": header.value, "bytes": header.bytes},
        "scratch": {"address": scratch.value, "bytes": scratch.bytes},
        "new_state_objects": 0,
        "resident_window_delta_required_bytes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("probe", "check-source", "check-elf"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--llvm-readobj", type=Path,
                        default=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    args = parser.parse_args()
    try:
        if args.command == "probe":
            value = probe()
        elif args.command == "check-source":
            value = source_gate(mutations=True)
        else:
            require(args.elf is not None, "--elf is required")
            value = linked_gate(args.elf, args.llvm_readobj)
    except (GateError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-append-suffix-domain: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
