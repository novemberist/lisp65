#!/usr/bin/env python3
"""Bind Link 44's first dynamic-top-level hardware First Red.

This is a read-only evidence pass.  It consumes the SHA-bound Link-44
product, deployment, terminal captures and JTAG captures.  It does not
compile, link, patch, deploy, reset or otherwise alter product or device
state.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / (
    "build/c2.2/substitution/"
    "product-link-44-c2-lite-v6-bank2-target-stage-replay")
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link44-bank2-target-stage"
LATENCY = PRESMOKE / "latency"
CAPTURE = PRESMOKE / "first-red-undefined-function"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-bank2-target-stage-replay-"
    "structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-dynamic-top-level-"
    "hardware-first-red.json")

PRODUCT = LINK / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
DEPLOYMENT = PRESMOKE / "deployment.json"
INITIAL_C2D = LINK / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
EXPECTED_BANK2 = LINK / "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin"
EXPECTED_BANK3 = LINK / "runtime-overlays-session-final.bin"
LIVE_LOW = CAPTURE / "low-0000-ffff.bin"
LIVE_BANK2 = CAPTURE / "bank2.bin"
LIVE_BANK3 = CAPTURE / "bank3.bin"
LIVE_C2D = CAPTURE / "c2d-v6.bin"
BOOT_TRANSCRIPT = LATENCY / "boot_counter.txt"
SETUP_TRANSCRIPT = LATENCY / "definition_setup.txt"
COLD_TRANSCRIPT = LATENCY / "definition_first_call.txt"
WARM_TRANSCRIPT = LATENCY / "warm_second_call.txt"
BOOT_SCREENSHOT = LATENCY / "boot_counter.png"
PRESMOKE_CONTRACT = ROOT / "config/c2-hot-refill-hardware-presmoke.json"
DIALECT_CONTRACT = ROOT / "config/dialect-v2-contract.json"
NATIVE_REGISTRY = ROOT / "config/v2-native-function-registry.json"
LIST_SOURCE = ROOT / "lib/dialect-v2/lists-core.lisp"
VM_SOURCE = ROOT / "src/vm.c"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"

PRODUCT_SHA256 = "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926"
STRUCTURAL_SHA256 = "f358d14604eac270d78e407dec9ecf43559267b1344d371ee92fb95189504ede"
DEPLOYMENT_SHA256 = "b8d1c873f5140b5f332ff923e303f1cceb8a005a63867b71b9a229f083ee0125"
BANK2_SHA256 = "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac"
BANK3_SHA256 = "c389f8aab29fcc313ffce971b7ff4341b03c55a6d24757c1efefb6bc8ccf4a80"
LIVE_C2D_SHA256 = "ff4e9643e3886d6dc3ae4a7dc26ec3daae105f0f338889708430de28306c2f25"

STATIC_CODE_BYTES = 34403
SESSION_BYTES = 65438
C2D_BYTES = 33840
UNDEFINED = "*** vm: undefined function"


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def main() -> None:
    require(not RECEIPT.exists(), "Link-44 dynamic-top-level receipt already exists")
    require(sha(PRODUCT) == PRODUCT_SHA256, "Link-44 product identity drift")
    require(sha(STRUCTURAL) == STRUCTURAL_SHA256, "Link-44 structural receipt drift")
    require(sha(DEPLOYMENT) == DEPLOYMENT_SHA256, "Link-44 deployment drift")
    require(sha(EXPECTED_BANK2) == BANK2_SHA256, "expected Bank-2 plane drift")
    require(sha(EXPECTED_BANK3) == BANK3_SHA256, "expected Bank-3 plane drift")
    require(sha(LIVE_C2D) == LIVE_C2D_SHA256, "live C2D capture drift")

    structural = load(STRUCTURAL)
    deployment = load(DEPLOYMENT)
    require(structural.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-44 structural status drift")
    require(deployment.get("status") == "ready-receipt-less"
            and deployment.get("product", {}).get("sha256") == PRODUCT_SHA256
            and deployment.get("new_product_links") == 0,
            "deployment does not bind the Link-44 product")
    require(all(row.get("address") != "0x00020000"
                for row in deployment.get("preloads", [])),
            "harness externally preloaded the product Bank-2 plane")

    low = LIVE_LOW.read_bytes()
    bank2 = LIVE_BANK2.read_bytes()
    bank3 = LIVE_BANK3.read_bytes()
    live_c2d = LIVE_C2D.read_bytes()
    initial_c2d = INITIAL_C2D.read_bytes()
    expected_bank2 = EXPECTED_BANK2.read_bytes()
    expected_bank3 = EXPECTED_BANK3.read_bytes()
    require(len(low) == len(bank2) == len(bank3) == 65536,
            "hardware capture geometry drift")
    require(len(live_c2d) == len(initial_c2d) == C2D_BYTES,
            "C2D-v6 capture geometry drift")
    require(bank2[:STATIC_CODE_BYTES] == expected_bank2,
            "live Bank-2 static plane differs from Link-44 truth")
    require(bank3[:SESSION_BYTES] == expected_bank3,
            "live Bank-3 session plane differs from Link-44 truth")
    require(sha(EXPECTED_BANK2) == sha_bytes(bank2[:STATIC_CODE_BYTES])
            and sha(EXPECTED_BANK3) == sha_bytes(bank3[:SESSION_BYTES]),
            "active Chip-plane hash mismatch")

    runtime_bytes = low[0xc084:0xc084 + 46]
    runtime = {
        "shelf_bytes": u32(runtime_bytes, 0),
        "catalog_crc32": f"0x{u32(runtime_bytes, 4):08x}",
        "c2d_bytes": u16(runtime_bytes, 8),
        "generation": u16(runtime_bytes, 10),
        "image_count": u16(runtime_bytes, 12),
        "entry_count": u16(runtime_bytes, 14),
        "resolution_count": u16(runtime_bytes, 16),
        "root_count": u16(runtime_bytes, 26),
        "resolution_cursor": u16(runtime_bytes, 30),
        "root_cursor": u16(runtime_bytes, 32),
        "phase": runtime_bytes[42],
        "finished": runtime_bytes[43],
        "error": runtime_bytes[44],
    }
    require(runtime == {
        "shelf_bytes": 70897,
        "catalog_crc32": "0x3d6302f3",
        "c2d_bytes": 33840,
        "generation": 1,
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
        "resolution_cursor": 2264,
        "root_cursor": 283,
        "phase": 13,
        "finished": 1,
        "error": 0,
    }, f"unexpected completed decoder state: {runtime}")

    # These addresses come from the exact Link-44 map, not a historical ABI.
    live_state = {
        "c2_ready_vma": "0x008c",
        "c2_ready_after_queued_forms": low[0x008c],
        "vm_status_vma": "0x005f",
        "vm_status_after_repl_report_reset": low[0x005f],
        "rtov_family_vma": "0x0079",
        "rtov_family": low[0x0079],
        "rtov_island_state_vma": "0x007a",
        "rtov_island_state": low[0x007a],
        "family_generation_vma": "0xc028",
        "family_generation": u16(low, 0xc028),
        "committed_roots_vma": "0xc080",
        "committed_roots": u16(low, 0xc080),
    }
    require(live_state["c2_ready_after_queued_forms"] == 0
            and live_state["vm_status_after_repl_report_reset"] == 0
            and live_state["rtov_family"] == 2
            and live_state["rtov_island_state"] == 2
            and live_state["family_generation"] == 1
            and live_state["committed_roots"] == 283,
            f"unexpected post-error live state: {live_state}")

    contract = load(PRESMOKE_CONTRACT)
    forms = contract.get("forms", {})
    require(forms.get("boot_counter") ==
            "(list(peek 255 132)(peek 255 131)(peek 255 132))",
            "boot-counter form drift")
    boot_text = BOOT_TRANSCRIPT.read_text(encoding="utf-8", errors="replace")
    require("WORKBENCH - DIALECT V2" in boot_text
            and "lisp65> " + forms["boot_counter"] in boot_text
            and UNDEFINED in boot_text,
            "line-1/line-2 terminal transcript drift")
    queued_transcripts = [SETUP_TRANSCRIPT, COLD_TRANSCRIPT, WARM_TRANSCRIPT]
    require(all(UNDEFINED in path.read_text(encoding="utf-8", errors="replace")
                for path in queued_transcripts),
            "queued post-first-red transcript drift")

    dialect = load(DIALECT_CONTRACT)
    registry = load(NATIVE_REGISTRY)
    list_source = LIST_SOURCE.read_text(encoding="utf-8")
    require("peek" in dialect.get("public_names", []),
            "peek is no longer in the dialect-v2 required surface")
    native_rows = registry.get("functions", registry.get("entries", []))
    require(any(row.get("name") == "peek" and row.get("kind") == "callprim"
                and row.get("value") == 61 for row in native_rows),
            "peek native registry binding drift")
    require("(defun list (&rest xs)" in list_source,
            "stdlib list definition drift")
    require("case 61: /* peek */" in VM_SOURCE.read_text(encoding="utf-8"),
            "product peek dispatch drift")

    receipt = {
        "format": "lisp65-c2-lite-v6-dynamic-top-level-hardware-first-red-v1",
        "status": "first-red-product-semantics-review-required",
        "date": "2026-07-22",
        "candidate": {
            "link": 44,
            "product_sha256": PRODUCT_SHA256,
            "structural_receipt": bind(STRUCTURAL),
            "deployment": bind(DEPLOYMENT),
        },
        "hardware_result": {
            "line_1_boot_to_repl": {
                "status": "passed",
                "observation": "visible Workbench banner and REPL prompt",
                "evidence": [bind(BOOT_TRANSCRIPT), bind(BOOT_SCREENSHOT)],
                "claim": (
                    "Link 44 staged both Chip planes, completed all decoder "
                    "phases, published READY and entered the REPL on hardware."),
            },
            "line_2_boot_counter": {
                "status": "first-red",
                "form": forms["boot_counter"],
                "observed": UNDEFINED,
                "vm_status_class": "VM_DIRMISS",
                "first_deviation": True,
            },
            "queued_after_first_red": {
                "status": "non-independent-diagnostic-only",
                "note": (
                    "The already queued setup/cold/warm forms also reported "
                    "VM_DIRMISS.  They are not counted as separate findings, "
                    "measurements or attempts."),
                "evidence": [bind(path) for path in queued_transcripts],
            },
        },
        "read_only_localization": {
            "bank2": {
                "active_bytes": STATIC_CODE_BYTES,
                "expected_sha256": BANK2_SHA256,
                "captured_active_sha256": sha_bytes(bank2[:STATIC_CODE_BYTES]),
                "different_bytes": 0,
            },
            "bank3": {
                "active_bytes": SESSION_BYTES,
                "expected_sha256": BANK3_SHA256,
                "captured_active_sha256": sha_bytes(bank3[:SESSION_BYTES]),
                "different_bytes": 0,
            },
            "decoder": runtime,
            "post_error_state": live_state,
            "live_c2d": bind(LIVE_C2D),
            "conclusion": (
                "The First Red is downstream of successful static Boot/Stage/"
                "Publish and upstream or inside dynamic top-level install/call. "
                "It is not a Bank-2 or Bank-3 transport/content failure."),
        },
        "surface_validity": {
            "boot_counter_is_not_an_out_of_contract_harness_form": True,
            "list": {
                "authority": bind(LIST_SOURCE),
                "evidence": "(defun list (&rest xs) is in dialect-v2 stdlib",
            },
            "peek": {
                "dialect_contract": bind(DIALECT_CONTRACT),
                "native_registry": bind(NATIVE_REGISTRY),
                "vm_source": bind(VM_SOURCE),
                "binding": "callprim 61",
            },
        },
        "claim_boundary": {
            "proved": [
                "hardware line 1 passed through visible banner and REPL",
                "the first latency form reported VM_DIRMISS",
                "both active Chip planes remained byteidentical to Link 44",
                "the static decoder completed phase 13 with error zero",
                "C2 was fail-closed after the queued failed forms (READY=0)",
            ],
            "not_proved": [
                "which symbol or directory lookup produced VM_DIRMISS",
                "whether the defect is in emit, append, export, lookup or call",
                "any cold or warm latency value",
            ],
            "reason": (
                "The public error is intentionally generic and the read-only "
                "capture was taken after the pre-emitted batch.  Assigning a "
                "single sub-cause would exceed the evidence."),
        },
        "budgets": {
            "line_1_product_first_reds": {
                "before": "2/3",
                "after": "2/3",
                "reason": (
                    "The written 3-run rule counts a new product-class First "
                    "Red in line 1.  Line 1 passed; this finding begins line 2."),
            },
            "completed_latency_measurements": {
                "before": "0/2", "after": "0/2",
                "reason": "No valid counter tuple or latency result was produced.",
            },
        },
        "execution": {
            "new_product_bytes": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_inputs_after_first_red_batch": 0,
            "next_action": (
                "Class-C review.  No product fix, diagnostic link or additional "
                "hardware input is authorized by this receipt."),
        },
        "artifacts": [
            bind(PRODUCT), bind(ELF), bind(MAP), bind(INITIAL_C2D),
            bind(EXPECTED_BANK2), bind(EXPECTED_BANK3), bind(LIVE_LOW),
            bind(LIVE_BANK2), bind(LIVE_BANK3), bind(LIVE_C2D),
            bind(PRESMOKE_CONTRACT), bind(RUNTIME_SOURCE),
        ],
        "value_string": (
            "link44=" + PRODUCT_SHA256
            + " line1=pass-banner-repl line2=FIRST-RED-VM_DIRMISS"
            + " bank2=34403/34403-identical bank3=65438/65438-identical"
            + " decoder=phase13/error0 ready-after-batch=0"
            + " line1-budget=2/3 latency=0/2 acceptance=blocked"
        ),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(json.dumps(receipt, indent=2, sort_keys=True))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    main()
