#!/usr/bin/env python3
"""Attribute and prepare a read-only capture for the v1.5 D2 BADOPCODE.

This is deliberately a desk-first tool.  It binds the green D2 prefix and
the exact First Red, proves that the product and compiler carrier did not
change, prices the old/new library materialization, and specifies the one
stopped-state read set that can distinguish compiler/pre-install, emitter,
append and post-commit failures.  It does not touch the product or a device.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_full_emission as F  # noqa: E402
import c2_repl_pipeline_cost_attribution as PIPE  # noqa: E402
import c2_session_extension_probe as SESSION  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT = ROOT / "build/c2.3/v1.5.0-name-freight-d2-d5"
CURRENT_SCREEN = OUT / "row-d2-define-probe.txt"
CONTROL_SCREEN = ROOT / (
    "build/c2.3/v1.5.0-link97-stager-liveness-d2-d5/"
    "row-d2-define-probe.txt"
)
CURRENT_PRODUCT = ROOT / (
    "build/c2.3/v1.5.0-name-freight-media/shared-system/"
    "lisp65-product.d81"
)
CONTROL_PRODUCT = ROOT / (
    "build/c2.3/v1.5.0-candidate-media-link97-stager-liveness/"
    "shared-system/lisp65-product.d81"
)
CURRENT_LIBRARY = ROOT / (
    "build/c2.3/v1.5.0-name-freight-media/library/lisp65-library.d81"
)
OLD_INSPECT = ROOT / "build/c2.3/trace-core-abi/inspect.manifest.json"
CURRENT_INSPECT = ROOT / (
    "build/c2.3/v1.5.0-name-freight-libraries/inspect.manifest.json"
)
STRING_EXTRA = ROOT / (
    "build/post-promotion/v112/string-extra/string-extra.manifest.json"
)
CANONICAL = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/"
    "canonical-product-manifest.json"
)
ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-media-receipt.json"
)
D1_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d1-receipt.json"
)
SESSION_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-d5-preparation-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-desk-receipt.json"
)
RUNNER = ROOT / "scripts/c2-v150-name-freight-d2-badopcode-capture-hw.sh"
RUNTIME = ROOT / "src/c2_product_runtime.c"
PHASE_HEADER = ROOT / "src/c2_phase_scratch.h"
OBJ_HEADER = ROOT / "src/obj.h"
PHASE_CONTRACT = ROOT / "config/c2-install-phase-discriminator-contract.json"

FORMAT = "lisp65-c2.3-v150-name-freight-D2-defun-BADOPCODE-desk-v1"
STATUS = "TARGET-STATE-WITNESS-REQUIRED"
FORM = "(defun trace-probe (x) (+ x 1))"
COMPILED_SHA = "89cafa2f5fe614ac663fe67c5d3e4d5a70e94346435c4a5aef5120e16fec298d"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def screen_facts() -> dict[str, Any]:
    current = CURRENT_SCREEN.read_text(encoding="utf-8")
    control = CONTROL_SCREEN.read_text(encoding="utf-8")
    for value in (current, control):
        require("WORKBENCH 1.5.0" in value, "D2 screen world identity absent")
        require("loading inspect..." in value and "loading string-extra..." in value,
                "D2 green require prefix absent")
        require(FORM in value, "exact D2 definition form absent")
    require("*** vm: bad bytecode" in current and "trace-probe" in control,
            "D2 First Red/control outcome drift")
    require("*** vm: bad bytecode" not in control,
            "old D2 control is not green")
    product_same = CURRENT_PRODUCT.read_bytes() == CONTROL_PRODUCT.read_bytes()
    require(product_same, "D2 control and First Red product media differ")
    return {
        "green_prefix": ["require inspect -> t", "require string-extra -> t"],
        "current": {**bind(CURRENT_SCREEN), "result": "VM_BADOPCODE; usable REPL"},
        "control": {**bind(CONTROL_SCREEN), "result": "trace-probe"},
        "product_medium_byteidentical": product_same,
    }


def emitted(path: Path) -> tuple[F.Emitted, dict[str, Any]]:
    image = F.emit_image(path.stem, "diagnostic", path)
    counts = Counter(item.kind for item in image.descriptors)
    return image, {
        "code_bytes": len(image.code),
        "entries": len(image.manifest["entries"]),
        "resolutions": len(image.descriptors),
        "roots": sum(item.kind in SESSION.ROOT_KINDS for item in image.descriptors),
        "descriptor_kinds": {str(key): counts[key] for key in sorted(counts)},
    }


def materialization_facts() -> dict[str, Any]:
    old, old_row = emitted(OLD_INSPECT)
    current, current_row = emitted(CURRENT_INSPECT)
    string_extra, string_row = emitted(STRING_EXTRA)
    require(old_row == {
        "code_bytes": 558, "entries": 13, "resolutions": 409, "roots": 211,
        "descriptor_kinds": {"0": 1, "7": 211, "8": 197},
    }, "old inspect C2 lowering drift")
    require(current_row == {
        "code_bytes": 579, "entries": 13, "resolutions": 412, "roots": 370,
        "descriptor_kinds": {"0": 1, "3": 159, "7": 211, "8": 41},
    }, "name-freight inspect C2 lowering drift")
    require(string_row["code_bytes"] == 152 and string_row["entries"] == 3
            and string_row["resolutions"] == 10 and string_row["roots"] == 0,
            "string-extra C2 lowering drift")
    strings = [node for node in current.manifest["literal_nodes"]
               if int(node["kind"]) == 7]
    require(len(strings) == 159, "lazy inspect string census drift")
    raw_strings = [str(node["name"]).encode("utf-8") for node in strings]
    require(len(set(raw_strings)) == 60 and sum(map(len, raw_strings)) == 2707,
            "lazy inspect string content census drift")

    static = load(CANONICAL)["static_plane"]
    start = {
        "images": 6, "entries": int(static["entries"]),
        "resolutions": int(static["resolutions"]),
        "roots": int(static["roots"]),
        "code_bytes": int(static["bank2_static_code_bytes"]),
    }
    require(start == {"images": 6, "entries": 755, "resolutions": 2929,
                      "roots": 352, "code_bytes": 46043},
            "Link-97 static plane drift")

    def after(inspect: dict[str, Any]) -> dict[str, int]:
        return {
            "images": start["images"] + 2,
            "entries": start["entries"] + inspect["entries"] + string_row["entries"],
            "resolutions": start["resolutions"] + inspect["resolutions"]
                + string_row["resolutions"],
            "roots": start["roots"] + inspect["roots"] + string_row["roots"],
            "code_bytes": start["code_bytes"] + inspect["code_bytes"]
                + string_row["code_bytes"],
        }

    old_after = after(old_row)
    current_after = after(current_row)
    require(old_after == {"images": 8, "entries": 771, "resolutions": 3348,
                          "roots": 563, "code_bytes": 46753},
            "old D2 C2 geometry drift")
    require(current_after == {"images": 8, "entries": 771,
                              "resolutions": 3351, "roots": 722,
                              "code_bytes": 46774},
            "current D2 C2 geometry drift")
    post_defun = dict(current_after)
    post_defun.update({
        "images": current_after["images"] + 1,
        "entries": current_after["entries"] + 1,
        "code_bytes": current_after["code_bytes"] + 12,
    })
    capacities = {"images": 64, "entries": 2048, "resolutions": 4096,
                  "roots": 1536, "code_bytes": 65536}
    require(all(post_defun[key] <= capacities[key] for key in capacities),
            "nominal trace-probe append does not fit")
    return {
        "old_inspect": old_row,
        "current_inspect": current_row,
        "string_extra": string_row,
        "delta": {key: current_row[key] - old_row[key]
                  for key in ("code_bytes", "entries", "resolutions", "roots")},
        "new_string_nodes": {"records": len(raw_strings),
                             "unique": len(set(raw_strings)),
                             "payload_bytes": sum(map(len, raw_strings))},
        "after_two_requires": {"old": old_after, "current": current_after},
        "nominal_post_defun": post_defun,
        "capacities": capacities,
        "capacity_result": "fits-all-C2D-and-Bank2-counts",
    }


def compiler_facts() -> dict[str, Any]:
    row = PIPE.run_form("trace-probe", FORM, CANONICAL)
    compiled = row["outcome"]["compiled"]
    require(row["outcome"]["route"] == "compile-then-transient-install"
            and row["pipeline"]["instructions"] == 1191
            and row["pipeline"]["instructions_by_role"] == {
                "compiler-carrier": 1115, "product-runtime": 76}
            and row["pipeline"]["install_calls"] == 1
            and compiled["objects"] == 1 and compiled["encoded_bytes"] == 12
            and compiled["payload_bytes"] == 5 and compiled["literal_count"] == 0
            and compiled["entries"][0]["encoded_sha256"] == COMPILED_SHA
            and row["host_heap_cells_allocated_after_read"] == 61,
            "exact Link-97 trace-probe compiler replay drift")
    return {
        "instructions": row["pipeline"]["instructions"],
        "instructions_by_role": row["pipeline"]["instructions_by_role"],
        "initial_windows": row["pipeline"]["initial_window_count"],
        "refills": row["pipeline"]["refill_count"],
        "install_calls": row["pipeline"]["install_calls"],
        "reader_cons_cells": row["reader_structure"]["form_cons_cells"],
        "heap_cells_after_read": row["host_heap_cells_allocated_after_read"],
        "compiled": compiled,
    }


def source_facts() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = PHASE_HEADER.read_text(encoding="utf-8")
    obj = OBJ_HEADER.read_text(encoding="utf-8")
    start = runtime.index("obj c2_product_install(obj fnlist, obj definition_name)")
    end = runtime.index("\n}\n\n#endif /* LISP65_C2_PRODUCT_CUT */", start) + 2
    install = runtime[start:end]
    require(install.index("vm_runtime_overlay_transaction_begin(")
            < install.index("emit = c2_session_emit_reset();"),
            "transaction begin no longer precedes emitter trace reset")
    require(install.count("vm_status = VM_BADOPCODE; return NIL;") == 7,
            "installer BADOPCODE collapse census drift")
    require("LISP65_C2_INSTALL_TRACE_OFFSET" in header
            and "C2_INSTALL_TRACE_ENTER_INNER" in header
            and "HEAP_CELLS" in obj and "EXT_CELLS" in obj,
            "stopped-state witness source seam drift")
    contract = load(PHASE_CONTRACT)
    require(contract["storage"]["offset"] == 302
            and contract["storage"]["bytes"] == 2,
            "installer trace contract drift")
    return {
        "transaction_begin_precedes_trace_reset": True,
        "installer_BADOPCODE_collapse_sites": 7,
        "trace": {"scratch_offset": 302, "bytes": 2,
                  "meaning": contract["interpretation"]},
        "claim": (
            "BADOPCODE alone does not distinguish target compiler/pre-install, "
            "emitter, append, or post-commit transaction-end failure"
        ),
    }


def capture_spec() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False,
    )
    wanted = (
        "c2_journal_count", "alloc_high", "gc_frozen", "freelist",
        "gc_badobj", "allocs_since_gc", "str_cur_off", "str_alt_off",
        "str_top", "str_frozen", "nsym", "vm_status", "gc_rootsp",
        "c2_phase_owner", "c2_pending_roots", "c2_ready", "mem_oom",
        "gc_runs", "npool", "c2_committed_roots", "c2_runtime",
        "lisp65_c2_phase_scratch", "heap",
    )
    symbols = {name: {
        "address": f"0x{truth.symbol(name).value:04x}",
        "bytes": truth.symbol(name).bytes,
    } for name in wanted}
    trace_address = truth.symbol("lisp65_c2_phase_scratch").value + 302
    require(trace_address == 0xC1F4 and symbols["c2_phase_owner"]["address"] == "0x0089",
            "Link-97 witness addresses drift")
    ranges = [
        {"name": "physical-bank0", "start": "0x00000000", "bytes": 65536,
         "purpose": "ZP, counters, phase trace, symbol state and hot heap"},
        {"name": "physical-bank4", "start": "0x00040000", "bytes": 27648,
         "purpose": "EXT heap plus both packed-string arena windows"},
        {"name": "physical-bank5", "start": "0x00050000", "bytes": 50816,
         "purpose": "complete C2D reset domain including C2J"},
    ]
    return {
        "precondition": (
            "same live REPL immediately after the bound D2 First Red; no "
            "intervening form, reboot, resume, mount or monitor access"
        ),
        "operation": "exactly one t1, one register tuple, then read-only physical memsave",
        "resume": False,
        "ranges": ranges,
        "symbols": symbols,
        "installer_trace_address": "0xc1f4",
        "decision_table": {
            "trace_unchanged_and_C2D_unchanged": "compiler/pre-install-or-transaction-begin",
            "trace_slot_15_through_22": "emitter family",
            "trace_slot_23_through_40": "append family",
            "C2D_image9_entry772": "append committed; post-commit/end edge",
            "mem_oom_or_gc_badobj": "allocator/GC state names target-state mechanism",
        },
        "claim_limit": (
            "The capture can name the failing family and exact target resource "
            "state. It does not authorize a fix, relink, replayed form or D3-D5."
        ),
    }


def projection() -> dict[str, Any]:
    result = {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "first_red": screen_facts(),
        "materialization": materialization_facts(),
        "compiler_replay": compiler_facts(),
        "source_boundary": source_facts(),
        "capture": capture_spec(),
        "conclusion": {
            "excluded": [
                "product-medium drift",
                "host-reproduced compiler-output drift",
                "symbol/name exhaustion at this row",
                "nominal C2D or Bank-2 capacity overflow",
            ],
            "not_excluded": [
                "target GC-schedule/live-state divergence after 159 new roots",
                "pre-install transaction refusal",
                "target emitter failure",
                "target append or post-commit transaction-end failure",
            ],
            "mechanism_claimed": False,
            "next": "one read-only salvage of the existing live First-Red state",
        },
        "authority": {
            "current_product": bind(CURRENT_PRODUCT),
            "control_product": bind(CONTROL_PRODUCT),
            "current_library": bind(CURRENT_LIBRARY),
            "old_inspect": bind(OLD_INSPECT),
            "current_inspect": bind(CURRENT_INSPECT),
            "string_extra": bind(STRING_EXTRA),
            "canonical_product": bind(CANONICAL),
            "ELF": bind(ELF),
            "media_receipt": bind(MEDIA_RECEIPT),
            "D1_receipt": bind(D1_RECEIPT),
            "session_preparation": bind(SESSION_PREP),
            "runtime_source": bind(RUNTIME),
            "phase_header": bind(PHASE_HEADER),
            "phase_contract": bind(PHASE_CONTRACT),
            "capture_runner": bind(RUNNER),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "product_bytes_changed": 0, "links": 0, "WPLTO": 0,
            "new_device_contacts": 0, "device_stops": 0,
        },
    }
    validate(result)
    return result


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "desk attribution identity drift")
    require(value["first_red"]["product_medium_byteidentical"] is True,
            "product identity exclusion lost")
    require(value["materialization"]["delta"]["roots"] == 159,
            "159-root target-state delta lost")
    require(value["materialization"]["capacity_result"]
            == "fits-all-C2D-and-Bank2-counts",
            "nominal capacity exclusion lost")
    require(value["compiler_replay"]["compiled"]["entries"][0]["encoded_sha256"]
            == COMPILED_SHA, "compiler identity exclusion lost")
    require(len(value["capture"]["ranges"]) == 3
            and value["capture"]["resume"] is False
            and value["capture"]["installer_trace_address"] == "0xc1f4",
            "read-only capture completeness drift")
    require(value["conclusion"]["mechanism_claimed"] is False
            and value["execution_accounting"]["new_device_contacts"] == 0,
            "desk evidence overclaims a mechanism or contact")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-product-identity": lambda x: x["first_red"].__setitem__(
            "product_medium_byteidentical", False),
        "lose-root-delta": lambda x: x["materialization"]["delta"].__setitem__(
            "roots", 0),
        "invent-capacity-overflow": lambda x: x["materialization"].__setitem__(
            "capacity_result", "overflow"),
        "drift-compiler-object": lambda x: x["compiler_replay"]["compiled"]
            ["entries"][0].__setitem__("encoded_sha256", "0" * 64),
        "drop-physical-bank4": lambda x: x["capture"]["ranges"].pop(1),
        "move-installer-trace": lambda x: x["capture"].__setitem__(
            "installer_trace_address", "0xc1f5"),
        "resume-after-capture": lambda x: x["capture"].__setitem__("resume", True),
        "claim-mechanism-before-state": lambda x: x["conclusion"].__setitem__(
            "mechanism_claimed", True),
        "invent-device-contact": lambda x: x["execution_accounting"].__setitem__(
            "new_device_contacts", 1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "desk attribution mutation survived")
    return rejected


def record() -> None:
    value = projection()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))


def check() -> None:
    observed = load(RECEIPT)
    expected = projection()
    expected["mutations_rejected"] = mutations(expected)
    require(observed == expected, "D2 BADOPCODE desk receipt stale")


def selftest() -> None:
    value = projection()
    rejected = mutations(value)
    require(len(rejected) == 9, "mutation count drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "record":
            record()
        elif args.action == "check":
            check()
        else:
            selftest()
    except (AttributionError, F.FullError, PIPE.PipelineError) as error:
        print(f"D2 BADOPCODE desk attribution: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"D2 BADOPCODE desk attribution: PASS action={args.action} status={STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
