#!/usr/bin/env python3
"""Attribute the v1.6 early-boot two-layer First Red without a device.

The receipt deliberately tests the commissioned premises.  It replays the
exact packed banner object in both the candidate and shipped-v1.5 worlds,
decodes the stopped state against the candidate ELF, and derives the native
error/recovery ordering from the final linked image.
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
from elf_truth import ElfTruth  # noqa: E402
from v11_repl_banner_visual import ObservingVM  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-boot-refill-generator-template-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / ("build/c2.3/v1.6-boot-refill-dma-media/"
                  "device-first-red-20260823/capture.json")
MANIFEST = ROOT / ("build/c2.3/v1.6-boot-refill-generator-template-card/"
                   "static-plane/narrow-static/stdlib-p0.manifest.json")
BLOB = MANIFEST.with_name("stdlib-p0.blob.bin")
V15_ELF = ROOT / ("build/release-v1.5.0/pack-product-b/lisp65-1.5.0/proof/"
                  "product/lisp65-c2-lite-product.elf")
V15_MANIFEST = ROOT / ("build/release-v1.5.0/public-projection-smoke-repo/"
                       "build/c2.3-red3/top-level-macro-publication-link95-preflight/"
                       "static-plane/narrow-static/stdlib-p0.manifest.json")
V15_BLOB = V15_MANIFEST.with_name("stdlib-p0.blob.bin")
V15_CLASSIFICATION = ROOT / ("tests/bytecode/dialect-v2/evidence/"
                              "architecture-blocks/c2.3-v1.6-retired-window-"
                              "release-classification.json")
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-boot-path-two-layer-attribution.json")
FORMAT = "lisp65-c2.3-v1.6-boot-path-two-layer-attribution-v1"

EXPECTED = {
    "ELF": "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99",
    "capture": "58c1ce79d6eb2f7f036569d0f23f6915e6162ec533a580201d262d35c5c5f0a0",
    "v1.5_ELF": "4f899d1e0c9bcc89d14c9d13c5384e6a843c4093ba9d1029b321820a11bf4942",
}


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
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def replay(manifest_path: Path, blob_path: Path) -> dict[str, Any]:
    manifest = load(manifest_path)
    blob = blob_path.read_bytes()
    require(len(blob) == int(manifest["code_bytes"]), "manifest/blob length drift")
    require(sha(blob) == manifest["blob_sha256"], "manifest/blob identity drift")
    heap = B.Heap()
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    patches = {int(row["blob_offset"]): int(row["node"])
               for row in manifest["literal_patches"]}
    banner_entry = None
    for entry in manifest["entries"]:
        symbol = heap.intern(entry["name"])
        code = STD._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patches)
        directory[symbol] = code
        if entry["name"] == "%repl-banner":
            banner_entry = entry
        if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
            macros.add(symbol)
    require(banner_entry is not None, "%repl-banner absent")
    ledger = load(ABI_LEDGER)
    vm = ObservingVM(
        heap=heap, directory=directory, macro_symbols=macros,
        max_steps=1_000_000, abi_profile="dialect-v2", abi_ledger=ledger)
    result = vm.run(directory[heap.intern("%repl-banner")], [])
    require(result == B.NIL, "banner result drift")
    require(vm.output_codes == [10] * 9, "banner write-char arguments drift")
    require(vm.screen_put_calls == 228 and len(vm.poke_writes) == 66,
            "banner visible side-effect count drift")
    return {
        "manifest": bind(manifest_path), "blob": bind(blob_path),
        "entry_ordinal": next(i for i, row in enumerate(manifest["entries"])
                              if row["name"] == "%repl-banner"),
        "entry_bytes": int(banner_entry["length"]),
        "result": "nil", "steps": vm.steps,
        "screen_put_calls": vm.screen_put_calls,
        "poke_writes": len(vm.poke_writes),
        "write_char_arguments": vm.output_codes,
        "first_type_error": None,
    }


def row_bytes(capture: dict[str, Any], name: str) -> bytes:
    row = next(item for item in capture["reads"] if item["name"] == name)
    return bytes.fromhex(row["observed_hex"])


def symbol_byte(truth: ElfTruth, rows: dict[str, tuple[int, bytes]], name: str) -> int:
    address = truth.symbol(name).value
    for _row_name, (first, raw) in rows.items():
        if first <= address < first + len(raw):
            return raw[address - first]
    raise AttributionError(f"symbol not covered by stopped-state rows: {name}")


def derive() -> dict[str, Any]:
    inputs = {
        "plan": bind(PLAN), "ELF": bind(ELF), "capture": bind(CAPTURE),
        "manifest": bind(MANIFEST), "blob": bind(BLOB),
        "v1.5_ELF": bind(V15_ELF), "v1.5_manifest": bind(V15_MANIFEST),
        "v1.5_blob": bind(V15_BLOB),
        "v1.5_retired_window_classification": bind(V15_CLASSIFICATION),
        "ABI_ledger": bind(ABI_LEDGER),
    }
    require({key: inputs[key]["sha256"] for key in EXPECTED} == EXPECTED,
            "bound attribution identity drift")
    plan = PLAN.read_text(encoding="utf-8")
    require("Two-layer boot-path attribution commissioned" in plan,
            "commission absent")

    current = replay(MANIFEST, BLOB)
    shipped = replay(V15_MANIFEST, V15_BLOB)
    require(current["entry_ordinal"] == 239 and shipped["entry_ordinal"] == 239,
            "banner ordinal drift")
    require(current["steps"] == shipped["steps"] == 8693,
            "cross-release banner execution drift")

    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
                          include_section_data=True)
    capture = load(CAPTURE)
    require(capture["tuple"]["PC"] == "0xe096"
            and capture["tuple"]["SP"] == "0x01ce"
            and capture["tuple"]["MAPL"] == "0x0000"
            and capture["tuple"]["MAPH"] == "0x8000",
            "stopped tuple drift")
    rows = {
        "bank0-zp-stack": (0x0000, row_bytes(capture, "bank0-zp-stack")),
        "vm-and-boot-status": (0xBFE0, row_bytes(capture, "vm-and-boot-status")),
        "c2-boot-runtime": (0xC080, row_bytes(capture, "c2-boot-runtime")),
    }
    observed = {name: symbol_byte(truth, rows, name) for name in (
        "vm_status", "rtov_fault", "rtov_family", "rtov_busy",
        "c2_phase_owner", "c2_ready", "pending_code", "lisp_toplevel_active",
        "gc_rootsp")}
    require(observed == {
        "vm_status": 3, "rtov_fault": 0, "rtov_family": 2,
        "rtov_busy": 0, "c2_phase_owner": 0, "c2_ready": 1,
        "pending_code": 0, "lisp_toplevel_active": 1, "gc_rootsp": 0,
    }, "candidate-symbol stopped-state decode drift")
    zp = rows["bank0-zp-stack"][1]
    require(zp[0x14:0x16] == bytes.fromhex("56c3"), "saved indirect pair drift")

    symbols = {name: truth.symbol(name).value for name in (
        "repl", "setjmp", "longjmp", "lisp_toplevel", "vm_run_dir", "vm_run",
        "lisp_abort_code", "lisp_abort_symbol", "c2_product_abort_cleanup")}
    require(symbols == {
        "repl": 0xA9D9, "setjmp": 0x24DB, "longjmp": 0x2542,
        "lisp_toplevel": 0xBD4B, "vm_run_dir": 0x4456, "vm_run": 0x4525,
        "lisp_abort_code": 0x2F36, "lisp_abort_symbol": 0x2F3D,
        "c2_product_abort_cleanup": 0x2F6A,
    }, "native path symbol drift")

    # These candidate bytes bind the ordering and the banner invocation:
    # setjmp(lisp_toplevel) at A9FA precedes vm_run_dir(ordinal EF) at AC54.
    text = truth.section(".text")
    raw = truth.section_bytes(".text")
    at = lambda address, count: raw[address - text.address:address - text.address + count]
    require(at(0xA9F2, 11) == bytes.fromhex("a24b8604a2bd860520db24"),
            "setjmp installation bytes drift")
    require(at(0xAC46, 17) == bytes.fromhex("a9efa200a0008404a00084056406205644"),
            "banner vm_run_dir invocation bytes drift")
    require(at(0x2F63, 7) == bytes.fromhex("a0bd8405204225"),
            "longjmp consumer bytes drift")

    v15 = load(V15_CLASSIFICATION)
    strings = json.dumps(v15, sort_keys=True)
    require("pre-existing" in strings.lower()
            and "not a v1.6 regression" in strings.lower(),
            "v1.5 retired-window classification drift")

    return {
        "format": FORMAT,
        "status": "ATTRIBUTED: COMMISSIONED PRIMARY PREMISE FALSIFIED; SECONDARY IS POST-INSTALL CORRUPTION",
        "recorded_on": "2026-08-23", "inputs": inputs,
        "primary": {
            "commissioned_claim": "exact boot replay reaches a first VM_TYPEERROR",
            "observed": "no host VM error in either exact packed world",
            "candidate_world": current,
            "shipped_v1.5_world": shipped,
            "faulting_form": None,
            "expected_and_received_type": {
                "expected": "all nine write-char arguments are fixnum 10",
                "received_on_host": "fixnum 10 in all nine calls",
                "received_on_device": "not present in the authorized read ranges",
            },
            "empty_phase_membership": False,
            "decision": ("The logical packed banner is exonerated. The device VM_TYPEERROR "
                         "is target-only state/content corruption at or below the native "
                         "primitive boundary; this evidence cannot truthfully name a Lisp form "
                         "that does not fail in the exact replay."),
        },
        "stopped_state_correction": {
            "commissioned_decode": {"rtov_fault": "ERR_LATCHED=2",
                                     "rtov_family": "boot=1"},
            "candidate_symbol_decode": observed,
            "conclusion": ("rtov_fault is clear and family is session, not boot. The earlier "
                           "two-layer narrative used addresses from a different symbol world."),
            "fail_closed": {"PC": "0xe096", "software_BRK": True,
                            "BRK_address": "0x004a", "BRK_continuation": "0x004c"},
        },
        "secondary": {
            "normal_dispatch": "repl calls vm_run_dir(239), then reads vm_status directly",
            "error_vector_or_handler": "lisp_toplevel jmp_buf at 0xbd4b",
            "installer": "setjmp(lisp_toplevel) at repl+0x21 / 0xa9fa",
            "installer_order": "installed before banner vm_run_dir at 0xac54",
            "null_before_installer": False,
            "never_installed": False,
            "classification": ("neither ordering nor missing freight: the normal error path has "
                               "no null handler dispatch. $004a is a post-install corrupted "
                               "control transfer after/beside recovery, not its configured target."),
            "saved_indirect_pair_at_stop": {"registers": "__rc18/__rc19",
                                             "value": "0xc356"},
            "claim_limit": ("The authorized ranges do not include the live lisp_toplevel jmp_buf "
                            "or vm_codebuf. They therefore do not prove which dynamic carrier "
                            "produced $004a; no carrier or fix is asserted."),
        },
        "regression": {
            "logical_banner": "same 8693-step green execution in v1.5 and v1.6",
            "generic_retired_window_abort_class": "pre-existing in shipped v1.5 evidence",
            "exact_current_instance": ("not attributable to v1.5 without the missing live carrier; "
                                       "no new shipped-product claim follows from this receipt"),
        },
        "decision_tree": {
            "primary": "open target-only boundary; no fix authorized",
            "secondary": "known retired-window signature is suggestive but membership unproved",
            "required_next_evidence": ("if pursued, read lisp_toplevel jmp_buf and vm_codebuf in the "
                                       "same conserved stop; do not infer them from zero page"),
        },
        "claim_limit": ("Host-only attribution. No fix, card, link, medium or device contact is "
                        "authorized or performed."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        ("primary", "candidate_world", "steps", 8692),
        ("stopped_state_correction", "candidate_symbol_decode", "rtov_fault", 2),
        ("secondary", "null_before_installer", None, True),
    ]
    for path0, path1, path2, replacement in mutations:
        clone = json.loads(json.dumps(value))
        if path2 is None:
            clone[path0][path1] = replacement
        else:
            clone[path0][path1][path2] = replacement
        accepted = (
            clone["primary"]["candidate_world"]["steps"] == 8693
            and clone["stopped_state_correction"]["candidate_symbol_decode"]["rtov_fault"] == 0
            and clone["secondary"]["null_before_installer"] is False)
        require(not accepted, "attribution mutation accepted")
    print(f"v1.6 boot two-layer attribution: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest()
        return 0
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "boot two-layer attribution receipt drift")
    print("v1.6 boot two-layer attribution: PASS host_banner=green secondary=post-install")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, B.VMError) as error:
        print(f"v1.6 boot two-layer attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
