#!/usr/bin/env python3
"""Prepare and evaluate Link-80's read-only require discriminator session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import repl_screen_check as SCREEN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-require-host-attribution-receipt.json"
)
DEPLOYMENT = ROOT / (
    "build/post-promotion/v1.2.3/link80-bundled-session/deployment.json"
)
ELF = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
INITIAL_C2D = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/static-plane/"
    "narrow-static/v6-semantics/initial.c2d-v6.bin"
)
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
OVERLAY_SOURCE = ROOT / "src/vm_runtime_overlay.c"
TRACE_CONTRACT = ROOT / "config/c2-install-phase-discriminator-contract.json"
SCRIPT = ROOT / "scripts/c2-v123-link80-require-discriminator-hw.sh"
OUT = ROOT / (
    "build/post-promotion/v1.2.3/link80-require-discriminator"
)
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-require-device-discriminator-retry-preparation-receipt.json"
)
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-require-device-discriminator-retry-hardware-receipt.json"
)
PRIOR_HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-require-device-discriminator-hardware-receipt.json"
)
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

FORMAT_PREP = "lisp65-c2-v1.2.3-link80-require-device-discriminator-prep-v2"
FORMAT_HW = "lisp65-c2-v1.2.3-link80-require-device-discriminator-hw-v2"
FORM = "(require(quote place))"
C2D_PHYSICAL = 0x00050000
C2D_HEADER_BYTES = 48
C2D_IMAGES_OFFSET = 48
C2D_IMAGE_BYTES = 32
PLACE_SLOT = 6
PLACE_ROW_PHYSICAL = C2D_PHYSICAL + C2D_IMAGES_OFFSET + PLACE_SLOT * C2D_IMAGE_BYTES
PLACE_GENERATION = 1
PLACE_CRC32 = 0x485A1CE2
SUCCESS_LAST_DIRECT_SLOT = 39
TRACE_INNER_ENTERED = 1
TRACE_PRIMARY_LOCKED = 128


class DiscriminatorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiscriminatorError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, *, address: int | None = None) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    data = path.read_bytes()
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    if path.exists():
        require(path.read_bytes() == encoded, f"receipt drift: {path}")
    else:
        path.write_bytes(encoded)


def extract_function(source: str, signature: str, next_signature: str) -> str:
    start = source.find(signature)
    end = source.find(next_signature, start + len(signature))
    require(start >= 0 and end > start, f"source function boundary absent: {signature}")
    return source[start:end]


def result_from_screen(path: Path) -> str:
    for result in ("t", "nil"):
        try:
            SCREEN.check_latest_result(path, FORM, result)
        except SCREEN.CheckError:
            continue
        return result
    raise DiscriminatorError(f"screen has neither exact t nor nil result: {path}")


def address_map() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    deployment = load(DEPLOYMENT)
    trace_contract = load(TRACE_CONTRACT)
    require(
        attribution["commission"]["cycles_completed"] == 3
        and attribution["attribution"]["H0_index_lock_or_media_mismatch"]
            == "disproved"
        and attribution["attribution"]["H1_real_Link80_Lisp_resolver_result"]
            == "t",
        "accepted Class-B attribution drift",
    )
    candidate = deployment["candidate"]
    require(
        candidate["link"] == 80
        and candidate["ELF"]["sha256"] == sha_bytes(ELF.read_bytes()),
        "Link-80 deployment authority drift",
    )

    truth = ElfTruth.read(
        ELF, llvm_readobj=LLVM_READOBJ, include_section_data=True
    )
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(
        scratch.value == 0xC0C6 and scratch.bytes == 304,
        "Link-80 phase scratch geometry drift",
    )
    trace_address = scratch.value + int(trace_contract["storage"]["offset"])
    require(trace_address == 0xC1F4, "Link-80 trace address drift")

    c2d = INITIAL_C2D.read_bytes()
    require(
        len(c2d) == 33840
        and c2d[:8] == b"C2D\0\x06\x30\x20\x0a"
        and struct.unpack_from("<H", c2d, 10)[0] == PLACE_GENERATION
        and struct.unpack_from("<H", c2d, 12)[0] == PLACE_SLOT
        and c2d[C2D_IMAGES_OFFSET + PLACE_SLOT * C2D_IMAGE_BYTES:
                C2D_IMAGES_OFFSET + (PLACE_SLOT + 1) * C2D_IMAGE_BYTES]
            == bytes(C2D_IMAGE_BYTES),
        "initial Link-80 C2D/place slot drift",
    )
    require(
        int(attribution["H0_artifact_binding"]["place"]["combined_crc32"], 0)
            == PLACE_CRC32
        and attribution["H1_exact_success_path"]["appends"][0]["image_slot"]
            == PLACE_SLOT,
        "place identity/slot authority drift",
    )

    runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")
    overlay = OVERLAY_SOURCE.read_text(encoding="utf-8")
    append_wrapper = extract_function(
        runtime,
        "uint8_t c2_product_append_staged(uint16_t length)",
        "obj c2_product_install(",
    )
    transaction_end = extract_function(
        overlay,
        "vm_runtime_overlay_status vm_runtime_overlay_transaction_end(void)",
        "vm_runtime_overlay_status vm_runtime_overlay_select_family(",
    )
    require(
        "ok = c2_append_begin" in append_wrapper
        and "vm_runtime_overlay_transaction_end()" in append_wrapper
        and "return ok;" in append_wrapper,
        "append/terminator wrapper contract drift",
    )
    require(
        "C2_INSTALL_TRACE_" not in transaction_end
        and "lisp65_c2_phase_scratch" not in transaction_end,
        "transaction terminator unexpectedly gained a trace store",
    )

    return {
        "phase_trace": {
            "scratch": f"0x{scratch.value:04x}",
            "address": f"0x{trace_address:08x}",
            "bytes": 2,
            "layout": ["last_session_slot", "trace_flags"],
            "flag_bits": {
                "inner_entered": TRACE_INNER_ENTERED,
                "primary_locked": TRACE_PRIMARY_LOCKED,
            },
            "claim": (
                "phase provenance only; transaction_end itself has no trace "
                "store, so this tuple must not be called a terminator status"
            ),
        },
        "c2d_header": {
            "address": f"0x{C2D_PHYSICAL:08x}",
            "bytes": C2D_HEADER_BYTES,
            "initial_images": PLACE_SLOT,
            "published_images": PLACE_SLOT + 1,
        },
        "place_row": {
            "slot": PLACE_SLOT,
            "address": f"0x{PLACE_ROW_PHYSICAL:08x}",
            "bytes": C2D_IMAGE_BYTES,
            "generation_field": {
                "offset": 4,
                "address": f"0x{PLACE_ROW_PHYSICAL + 4:08x}",
                "expected": PLACE_GENERATION,
            },
            "identity_field": {
                "offset": 28,
                "address": f"0x{PLACE_ROW_PHYSICAL + 28:08x}",
                "expected_crc32": f"0x{PLACE_CRC32:08x}",
                "expected_little_endian": struct.pack("<I", PLACE_CRC32).hex(),
            },
        },
    }


def prepare() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    addresses = address_map()
    phase = deployment["phases"]["product"]
    media = ROOT / phase["media"]["path"]
    product = ROOT / phase["product"]["path"]
    preloads = [
        bind(ROOT / row["path"], address=int(row["address"], 0))
        for row in phase["preloads"]
    ]
    value = {
        "format": FORMAT_PREP,
        "recorded_on": "2026-07-30",
        "status": "passed-host-dry-run-ready-for-one-bounded-device-session",
        "promotable": False,
        "product_delta_bytes": 0,
        "product_links": 0,
        "hardware_contacts": 0,
        "commission": {
            "class": "C",
            "source_commit": "204b90a6",
            "maximum_physical_contacts": 3,
            "contact": "3 of 3",
            "precondition": "cold reset plus asserted BASIC 65 READY state",
            "ftp_progress_guard_seconds": 120,
            "peeks_only": True,
        },
        "candidate": {
            "link": 80,
            "product": bind(product, address=int(phase["product"]["address"], 0)),
            "ELF": bind(ELF),
            "media": bind(media),
            "preloads": preloads,
        },
        "form": FORM,
        "addresses": addresses,
        "interpretation": {
            "row_absent": (
                "Prim-18 stage/append/auth side did not leave a published "
                "place image; phase tuple narrows the last transported phase"
            ),
            "row_correct": (
                "place publication landed with the requested generation and "
                "identity; final nil is downstream in the target identity "
                "view/return seam"
            ),
            "second_t": "the published identity becomes visible on the repeat",
            "second_nil": "the target identity view remains divergent",
            "terminator_note": (
                "The trace tuple is not a transaction-end status. A successful "
                "append necessarily crosses authenticated overlay execution; "
                "the native terminator branch remains a structural subcase of "
                "the Prim-18 wrapper, not an independently stamped outcome."
            ),
        },
        "selftest": classifier_selftest(),
        "bindings": {
            "accepted_attribution": bind(ATTRIBUTION),
            "trace_contract": bind(TRACE_CONTRACT),
            "runtime_source": bind(RUNTIME_SOURCE),
            "overlay_source": bind(OVERLAY_SOURCE),
            "initial_c2d": bind(INITIAL_C2D, address=C2D_PHYSICAL),
            "prior_hardware_receipt": bind(PRIOR_HARDWARE),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(SCRIPT),
        },
        "claim_limit": (
            "Read-only target discriminator. It may classify the observed "
            "Link-80 require failure; it makes no fix, release, promotion or "
            "general DMA-completion claim."
        ),
    }
    atomic_json(PREPARATION, value)
    return value


def row_state(row: bytes) -> str:
    require(len(row) == C2D_IMAGE_BYTES, "place row must be 32 bytes")
    if row == bytes(C2D_IMAGE_BYTES):
        return "absent"
    generation = struct.unpack_from("<H", row, 4)[0]
    identity = struct.unpack_from("<I", row, 28)[0]
    if (
        row[0] == 1
        and row[1] == 0
        and row[2] == 0
        and row[3] == 0
        and generation == PLACE_GENERATION
        and identity == PLACE_CRC32
    ):
        return "correct"
    return "divergent"


def classify(result: str, trace: bytes, header: bytes, row: bytes) -> dict[str, Any]:
    require(result in {"t", "nil"}, "result must be t or nil")
    require(len(trace) == 2, "trace must be two bytes")
    require(len(header) == C2D_HEADER_BYTES, "header must be 48 bytes")
    state = row_state(row)
    images = struct.unpack_from("<H", header, 12)[0]
    trace_value = {
        "slot": trace[0],
        "flags": trace[1],
        "inner_entered": bool(trace[1] & TRACE_INNER_ENTERED),
        "primary_locked": bool(trace[1] & TRACE_PRIMARY_LOCKED),
    }
    if result == "t" and state == "correct" and images == PLACE_SLOT + 1:
        disposition = "not-reproduced-published-and-visible"
    elif result == "nil" and state == "absent" and images == PLACE_SLOT:
        disposition = "boundary-1-stage-append-auth-side"
    elif result == "nil" and state == "correct" and images == PLACE_SLOT + 1:
        disposition = "boundary-3-target-identity-view-or-return"
    else:
        disposition = "inconsistent-requires-owner-review"
    return {
        "result": result,
        "trace": trace_value,
        "header_image_count": images,
        "row_state": state,
        "row_generation": struct.unpack_from("<H", row, 4)[0],
        "row_crc32": f"0x{struct.unpack_from('<I', row, 28)[0]:08x}",
        "disposition": disposition,
    }


def classifier_selftest() -> dict[str, Any]:
    correct = bytearray(C2D_IMAGE_BYTES)
    correct[0] = 1
    struct.pack_into("<H", correct, 4, PLACE_GENERATION)
    struct.pack_into("<I", correct, 28, PLACE_CRC32)
    old_header = bytearray(C2D_HEADER_BYTES)
    new_header = bytearray(C2D_HEADER_BYTES)
    struct.pack_into("<H", old_header, 12, PLACE_SLOT)
    struct.pack_into("<H", new_header, 12, PLACE_SLOT + 1)
    cases = {
        "absent": classify(
            "nil", bytes((35, 0x81)), bytes(old_header), bytes(C2D_IMAGE_BYTES)
        )["disposition"],
        "published_nil": classify(
            "nil", bytes((SUCCESS_LAST_DIRECT_SLOT, 0x81)),
            bytes(new_header), bytes(correct)
        )["disposition"],
        "published_t": classify(
            "t", bytes((SUCCESS_LAST_DIRECT_SLOT, 0x81)),
            bytes(new_header), bytes(correct)
        )["disposition"],
    }
    require(
        cases == {
            "absent": "boundary-1-stage-append-auth-side",
            "published_nil": "boundary-3-target-identity-view-or-return",
            "published_t": "not-reproduced-published-and-visible",
        },
        "classifier selftest drift",
    )
    mutations = 0
    for offset, replacement in ((4, b"\x02\x00"), (28, b"\x00\x00\x00\x00")):
        trial = bytearray(correct)
        trial[offset:offset + len(replacement)] = replacement
        require(row_state(bytes(trial)) == "divergent", "row mutation accepted")
        mutations += 1
    return {"cases": cases, "mutations_rejected": mutations}


def captured_attempt(out: Path, number: int) -> tuple[dict[str, Any], dict[str, Any]]:
    prefix = out / f"attempt-{number}"
    trace_path = prefix.with_name(prefix.name + "-trace.bin")
    header_path = prefix.with_name(prefix.name + "-c2d-header.bin")
    row_path = prefix.with_name(prefix.name + "-place-row.bin")
    screen_path = prefix.with_name(prefix.name + ".txt")
    result = result_from_screen(screen_path)
    trace = trace_path.read_bytes()
    header = header_path.read_bytes()
    row = row_path.read_bytes()
    return classify(result, trace, header, row), {
        "screen": bind(screen_path),
        "trace": bind(trace_path, address=0xC1F4),
        "c2d_header": bind(header_path, address=C2D_PHYSICAL),
        "place_row": bind(row_path, address=PLACE_ROW_PHYSICAL),
    }


def evaluate(out: Path) -> dict[str, Any]:
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    phase = deployment["phases"]["product"]
    media = ROOT / phase["media"]["path"]
    media_readback = out / "uploaded-media-readback.d81"
    require(
        media.read_bytes() == media_readback.read_bytes(),
        "uploaded media readback differs from the bound D81",
    )
    fresh_text_path = out / "fresh-start.txt"
    fresh_text = fresh_text_path.read_text(encoding="utf-8")
    require("BASIC 65" in fresh_text, "fresh-state screenshot lacks BASIC 65")
    require("READY." in fresh_text, "fresh-state screenshot lacks READY.")
    require("lisp65>" not in fresh_text, "fresh-state screenshot still shows Lisp")
    baseline_trace_path = out / "baseline-trace.bin"
    baseline_header_path = out / "baseline-c2d-header.bin"
    baseline_row_path = out / "baseline-place-row.bin"
    baseline_trace = baseline_trace_path.read_bytes()
    baseline_header = baseline_header_path.read_bytes()
    baseline_row = baseline_row_path.read_bytes()
    require(len(baseline_trace) == 2, "baseline trace must be two bytes")
    require(
        len(baseline_header) == C2D_HEADER_BYTES,
        "baseline C2D header must be 48 bytes",
    )
    require(
        struct.unpack_from("<H", baseline_header, 12)[0] == PLACE_SLOT,
        "baseline C2D image count is not six",
    )
    require(row_state(baseline_row) == "absent", "baseline place row is not empty")
    first, first_bindings = captured_attempt(out, 1)
    second, second_bindings = captured_attempt(out, 2)
    if first["disposition"] == "boundary-1-stage-append-auth-side":
        final = first["disposition"]
    elif first["disposition"] == "boundary-3-target-identity-view-or-return":
        final = (
            "boundary-3-late-convergence"
            if second["result"] == "t"
            else "boundary-3-persistent-target-identity-view"
        )
    elif first["disposition"] == "not-reproduced-published-and-visible":
        final = "anomaly-not-reproduced"
    else:
        final = "inconsistent-requires-owner-review"
    contact_file = out / "contact-count.txt"
    contacts = int(contact_file.read_text(encoding="ascii").strip())
    require(contacts == 3, "hardware contact must be the commissioned third contact")
    value = {
        "format": FORMAT_HW,
        "recorded_on": "2026-07-30",
        "status": final,
        "promotable": False,
        "product_delta_bytes": 0,
        "product_links": 0,
        "hardware_contacts": contacts,
        "transport_precondition": {
            "state": "asserted-cold-reset-basic-ready",
            "media_readback": "byte-identical",
            "ftp_progress_guard_seconds": 120,
        },
        "baseline": {
            "header_image_count": PLACE_SLOT,
            "place_row_state": "absent",
            "trace": baseline_trace.hex(),
        },
        "attempt_1": first,
        "attempt_2": second,
        "disposition": final,
        "bindings": {
            "preparation": bind(PREPARATION),
            "fresh_start_text": bind(fresh_text_path),
            "fresh_start_screen": bind(out / "fresh-start.png"),
            "media_log": bind(out / "media-upload.log"),
            "media_readback": bind(media_readback),
            "baseline": {
                "trace": bind(baseline_trace_path, address=0xC1F4),
                "c2d_header": bind(baseline_header_path, address=C2D_PHYSICAL),
                "place_row": bind(baseline_row_path, address=PLACE_ROW_PHYSICAL),
            },
            "attempt_1": first_bindings,
            "attempt_2": second_bindings,
        },
        "claim_limit": preparation["claim_limit"],
    }
    atomic_json(HARDWARE, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("prepare", "dry-run", "screen-result", "evaluate")
    )
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--screen", type=Path)
    args = parser.parse_args()
    try:
        if args.command in {"prepare", "dry-run"}:
            value = prepare()
            print(
                "c2-v123-link80-require-device-discriminator: "
                f"{'DRY-RUN ' if args.command == 'dry-run' else ''}PASS "
                f"trace={value['addresses']['phase_trace']['address']} "
                f"row={value['addresses']['place_row']['address']} "
                f"crc={value['addresses']['place_row']['identity_field']['expected_crc32']}"
            )
        elif args.command == "screen-result":
            require(args.screen is not None, "--screen is required")
            print(result_from_screen(args.screen))
        else:
            value = evaluate(args.out)
            print(
                "c2-v123-link80-require-device-discriminator: PASS "
                f"disposition={value['disposition']} "
                f"first={value['attempt_1']['result']} "
                f"second={value['attempt_2']['result']}"
            )
    except (
        DiscriminatorError, OSError, ValueError, KeyError, TypeError,
        json.JSONDecodeError, SCREEN.CheckError,
    ) as error:
        print(f"c2-v123-link80-require-device-discriminator: FAIL {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
