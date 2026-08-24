#!/usr/bin/env python3
"""Attribute the primary v1.6 Comfort-activation VM_TYPE First Red.

This is host-only.  It executes the delivered Comfort bytecode with the
product-shaped private input modes and records the separately authorized
holder-read specification without touching a device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
SOURCE = ROOT / "lib/repl-comfort.lisp"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
MANIFEST = ROOT / (
    "build/c2.3/v1.6-items12-hybrid-device-preparation/library-inputs/"
    "repl-comfort.manifest.json"
)
BLOB = MANIFEST.with_name("repl-comfort.blob.bin")
CORE_MANIFEST = MANIFEST.with_name("v16core.manifest.json")
CORE_BLOB = MANIFEST.with_name("v16core.blob.bin")
ELF = ROOT / (
    "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
CAPTURE = ROOT / (
    "build/c2.3/v1.6-items12-hybrid-owner-contact/"
    "hybrid-entry-first-red-stopped-state/capture.json"
)
PROFILE_RECEIPT = ROOT / (
    "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/"
    "input-fidelity-reopen-host.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-primary-vm-type-attribution-receipt.json"
)
FORMAT = "lisp65-c2.3-v1.6-primary-vm-type-attribution-v1"
AUTHORITY_COMMIT = "5d8b3b82"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in all_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in all_strings(child)]
    return []


def artifact_case(events: list[int], *, expect_error: bool) -> dict[str, Any]:
    suite = STD._read_suite(str(SUITE))
    case: dict[str, Any] = {
        "name": "comfort-cursor-down-then-real-input-gap",
        "expr": "(repl)",
        "expect": "nil",
        "max_steps": 3_000_000,
        "key_events": events,
    }
    if expect_error:
        case["expect_vm_error"] = "TypeError"
    else:
        case["expect_key_events_remaining"] = 0
    suite["cases"] = [case]
    manifest = load(MANIFEST)
    result = STD._check_embed_manifest(
        MANIFEST, suite, manifest, BLOB.read_bytes(), verbose=False
    )
    require(result["cases"] == 1, "delivered-artifact case did not execute")
    return result


def derive() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    editor = EDITOR.read_text(encoding="utf-8")
    manifest = load(MANIFEST)
    core_manifest = load(CORE_MANIFEST)
    require(manifest["blob_sha256"] == bind(BLOB)["sha256"],
            "delivered Comfort blob/manifest drift")
    require(core_manifest["blob_sha256"] == bind(CORE_BLOB)["sha256"],
            "delivered v16core blob/manifest drift")
    require(
        "(%rl-render nil 0 0 0 0 -1)" in editor
        and "(code (if (numberp event) event (cadr event)))" in editor
        and "(if (and (>= code 32) (<= code 126))" in editor,
        "faulting input expression shape drift",
    )
    require(
        "((or (= command 1108) (= command 1003))" in editor
        and "(if (car (nthcdr 8 state)) command (%read-line-loop state))" in editor,
        "cursor-down empty-history path drift",
    )
    require("(%repl-step nil \"\" 0)" in source,
            "Comfort activation no longer enters an empty-history step")

    # _check_embed_manifest executes the delivered Comfort object over the
    # resident suite.  Prove that the exact resident function reached by that
    # run has the same executable payload/header as the delivered v16core
    # candidate, so the host result is not a source-only surrogate.
    resident_suite = STD._read_suite(str(SUITE))
    resident_names, resident_codes, _resident_flags = STD._compile_resident_code(
        resident_suite, B.Heap()
    )
    require("%read-line-loop" in resident_names, "resident loop absent")
    core_entry = next(
        row for row in core_manifest["entries"] if row["name"] == "%read-line-loop"
    )
    core_blob = CORE_BLOB.read_bytes()
    core_code = B.decode_code_object(core_blob[
        int(core_entry["blob_offset"]):
        int(core_entry["blob_offset"]) + int(core_entry["length"])
    ])
    resident_code = resident_codes["%read-line-loop"]
    require(
        (core_code.nargs, core_code.nlocals, core_code.flags, core_code.payload)
        == (resident_code.nargs, resident_code.nlocals,
            resident_code.flags, resident_code.payload),
        "executed resident loop differs from delivered v16core payload",
    )

    # The delivered artifact fails only when time is represented by an empty
    # producer interval.  Preloading Return masks that interval and is the
    # exact limitation of the former fixtures.
    gap = artifact_case([17], expect_error=True)
    preloaded = artifact_case([17, 13], expect_error=False)

    vm = B.P0VM(key_events=[17], private_key_event_modes=True)
    first = vm._private_key_event(2)
    second = vm._private_key_event(2)
    require(B.is_fix(first) and B.fixval(first) == 17 and second == B.NIL,
            "private mode-2 empty-gap model drift")

    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj"
    )
    roots = truth.symbol("gc_rootstack")
    top = truth.symbol("lisp_toplevel")
    upvals = truth.symbol("vm_upvals")
    evaluator = [truth.symbol(name) for name in
                 ("k_primitive", "k_closure", "eval.k_lccrun", "pending_symbol")]
    require(
        roots.value == 0x1ECC and roots.bytes == 256
        and top.value == 0xBD47 and top.bytes == 19
        and upvals.value == 0xBF92 and upvals.bytes == 2
        and evaluator[0].value == 0xB9E1
        and evaluator[-1].value + evaluator[-1].bytes == 0xB9E9,
        "candidate dynamic-holder symbol geometry drift",
    )
    profile_strings = set(all_strings(load(PROFILE_RECEIPT)))
    needed = {
        "GC_ROOTS=128", "SYMPOOL_EXT_OFF=0xc680", "NAMEPOOL=10208",
        "MAX_SYM=752", "LISP65_SYMVAL_EXT", "LISP65_NAMEOFF_EXT",
        "LISP65_SYMFN_EXT",
    }
    require(needed <= profile_strings, "candidate extended-symbol profile drift")
    sympool = 0xC680
    namepool = 10208
    max_sym = 752
    symval = sympool + namepool
    nameoff = symval + max_sym * 2
    symfn = nameoff + max_sym * 2
    symend = symfn + max_sym * 2
    require((symval, nameoff, symfn, symend)
            == (0xEE60, 0xF440, 0xFA20, 0x10000),
            "candidate extended-symbol layout arithmetic drift")

    holder_ranges = [
        {
            "space": "physical-bank0", "first": "0x0060", "last": "0x0061",
            "bytes": 2, "owner": "gc_rootsp",
            "purpose": "bind the live prefix of the VM/evaluator root stack",
        },
        {
            "space": "physical-bank0", "first": f"0x{roots.value:04x}",
            "last": f"0x{roots.value + roots.bytes - 1:04x}",
            "bytes": roots.bytes, "owner": "gc_rootstack[128]",
            "purpose": "enumerate live VM/evaluator arguments, forms and continuations",
        },
        {
            "space": "physical-bank0", "first": f"0x{evaluator[0].value:04x}",
            "last": f"0x{evaluator[-1].value + evaluator[-1].bytes - 1:04x}",
            "bytes": sum(symbol.bytes for symbol in evaluator),
            "owner": "k_primitive/k_closure/eval.k_lccrun/pending_symbol",
            "purpose": "bind dynamic evaluator and pending-publication holders",
        },
        {
            "space": "physical-bank0", "first": f"0x{top.value:04x}",
            "last": f"0x{top.value + top.bytes - 1:04x}",
            "bytes": top.bytes, "owner": "lisp_toplevel jmp_buf",
            "purpose": "capture the live non-local continuation record",
        },
        {
            "space": "physical-bank0", "first": f"0x{upvals.value:04x}",
            "last": f"0x{upvals.value + upvals.bytes - 1:04x}",
            "bytes": upvals.bytes, "owner": "vm_upvals",
            "purpose": "capture the active bytecode closure continuation root",
        },
        {
            "space": "physical-bank5", "first": f"0x05{sympool:04x}",
            "last": f"0x05{symend - 1:04x}", "bytes": symend - sympool,
            "owner": "namepool + symval + nameoff + symfn for MAX_SYM=752",
            "purpose": "resolve every dynamic value/function publication by name and value",
        },
    ]

    return {
        "format": FORMAT,
        "recorded_on": "2026-08-20",
        "status": "ATTRIBUTED: PRIMARY VM_TYPE; HOLDER READ SPECIFIED NOT EXECUTED",
        "authority": ERA.era_bind(AUTHORITY_COMMIT, PLAN.relative_to(ROOT).as_posix()),
        "inputs": {
            "candidate_elf": bind(ELF),
            "stopped_state": bind(CAPTURE),
            "candidate_profile_receipt": bind(PROFILE_RECEIPT),
            "comfort_manifest": bind(MANIFEST),
            "comfort_blob": bind(BLOB),
            "v16core_manifest": bind(CORE_MANIFEST),
            "v16core_blob": bind(CORE_BLOB),
            "comfort_source": bind(SOURCE),
            "editor_source": bind(EDITOR),
        },
        "track_1": {
            "reproduced": True,
            "world": "delivered repl-comfort blob plus its real resident suite",
            "resident_candidate_parity": {
                "function": "%read-line-loop",
                "encoded_bytes": int(core_entry["length"]),
                "payload_bytes": len(core_code.payload),
                "header_and_payload_byteidentical": True,
            },
            "activation": "(repl), empty history",
            "physical_sequence": ["Cursor Down ($11)", "producer interval with no key"],
            "delivered_artifact_gap_case": gap,
            "preloaded_return_control": preloaded,
            "faulting_function": "%read-line-loop",
            "faulting_form": "(>= code 32)",
            "expected_type": "fixnum key code",
            "received_type": "NIL",
            "source": (
                "Comfort replaces blocking key-event mode 1 with private mode 2 via "
                "%rl-render(row=-1). Mode 2 is a nonblocking scalar dequeue. After "
                "Cursor Down is consumed and redispatched with empty history, the "
                "recursive loop observes an empty ring as NIL; its legacy event adapter "
                "applies cadr to NIL and then submits NIL to the numeric >= comparison."
            ),
            "fixture_gap": (
                "Former cases preload all later keys. Cursor Down followed by an already "
                "queued Return never exposes the empty producer interval and passes."
            ),
            "classification": "blocking-contract/nonblocking-consumer mismatch",
        },
        "track_2": {
            "status": "SPECIFIED; OWNER CONTACT REQUIRED; NOT EXECUTED",
            "trigger": (
                "reproduce the bound B=1 / continuation-$C5B8 stop; confirm tuple and "
                "media identities before any read"
            ),
            "protocol": [
                "one stop only; no resume/reset/input",
                "persist every range raw-first before interpretation",
                "read only the enumerated broadened ranges after identity confirmation",
                "leave CPU stopped; power-off is allowed only after raw persistence",
            ],
            "ranges": holder_ranges,
            "decision": (
                "decode all 16-bit objects in the live gc_rootstack prefix, jmp_buf, "
                "evaluator holders, upvalues and named Bank-5 value/function cells; the "
                "first object or callable target in $C356..$CA91 names the dynamic holder"
            ),
        },
        "claim_limit": (
            "Track 1 names the primary fault but authorizes no fix/card. Track 2 is a "
            "read specification only: no device access, product change, link or medium. "
            "The primary fault and stale-holder/liveness class remain independently open."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"))
    args = parser.parse_args()
    value = derive()
    if args.action == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    else:
        require(load(RECEIPT) == value, "primary VM_TYPE attribution receipt drift")
    print("v1.6 primary VM_TYPE attribution: PASS gap=NIL->>= holder-read=specified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 primary VM_TYPE attribution: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
