#!/usr/bin/env python3
"""Gate the released v1.6 adaptive input-service hybrid before its card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as C  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
EVAL = ROOT / "src/eval.c"
VM = ROOT / "src/vm.c"
HEADER = ROOT / "src/petscii_normalization.h"
CAPTURE = ROOT / "src/optional/c2_kernal_input_capture.s"
CONSUMER = ROOT / "src/optional/c2_kernal_input_consumer.s"
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
FORMAT = "lisp65-c2-v160-input-service-hybrid-v1"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def normalize(raw: int, rules: list[dict[str, Any]]) -> tuple[int, bool]:
    for row in rules:
        if row["first"] <= raw <= row["last"]:
            return ((raw + row["delta"]) & 0xff, bool(row["shift"]))
    return raw, False


def normalization_gate(contract: dict[str, Any]) -> dict[str, Any]:
    rules = contract["normalization"]
    header = HEADER.read_text(encoding="utf-8")
    capture = CONSUMER.read_text(encoding="utf-8")
    eval_c = EVAL.read_text(encoding="utf-8")
    vm_c = VM.read_text(encoding="utf-8")
    require(eval_c.count("lisp65_normalize_petscii") == 1
            and vm_c.count("lisp65_normalize_petscii") == 1,
            "shared public normalization consumer drift")
    require("mode != 2 && mode != 3" in vm_c
            and "mode == 2 || mode == 3" in vm_c,
            "private scalar/printable dispatcher modes are not both consumed")
    for token in ("cmp #$a0", "cmp #$41", "cmp #$5b", "cmp #$c1",
                  "cmp #$db", "and #$7f", "ora #$20"):
        require(token in capture, f"raw scalar normalization token absent: {token}")
    require("LISP65_PETSCII_NORMALIZATION_ROWS" in header,
            "generated normalization authority absent")
    rows = [normalize(raw, rules) for raw in range(256)]
    require(rows[0x41] == (0x61, False)
            and rows[0x5a] == (0x7a, False)
            and rows[0xc1] == (0x41, True)
            and rows[0xda] == (0x5a, True)
            and rows[0xa0] == (0x20, False)
            and rows[0x03] == (0x03, False),
            "raw PETSCII boundary parity drift")
    return {"raw_inputs": 256, "consumer_pairs": 2, "parity": True,
            "fixtures": "raw-PETSCII", "a0_to_space": True}


def native_gate(contract: dict[str, Any]) -> dict[str, Any]:
    compiler = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    readobj = ROOT / "tools/llvm-mos/bin/llvm-readobj"
    with tempfile.TemporaryDirectory(prefix="c2-v160-hybrid-") as name:
        obj = Path(name) / "capture.o"
        result = subprocess.run([str(compiler), "-Isrc",
            "-c", str(CONSUMER), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(result.returncode == 0, f"native assembly red: {result.stderr}")
        truth = ElfTruth.read(obj, llvm_readobj=readobj,
                              include_section_data=True)
        section = truth.section(".lisp65_c2_kernal_window.input_consumer")
        require(0 < section.bytes <= contract["capacity"]["native_body_max_bytes"],
                f"native scalar body price drift: {section.bytes}")
        raw = truth.section_bytes(section.name)
        tail_stores = [row for row in truth.relocations
            if row.source_section == section.name
            and truth.relocation_target_identity(row)["symbol"] ==
                "C2K_INPUT_RING_TAIL"]
        require(raw.endswith(b"\xa9\x00\x60") and len(tail_stores) == 2,
                "native scalar empty/consumer-commit shape drift")
    return {"section": section.name, "bytes": section.bytes,
            "ceiling": contract["capacity"]["native_body_max_bytes"]}


def bytecode_sizes() -> dict[str, int]:
    forms = [form for form in C.parse_all(EDITOR.read_text(encoding="utf-8"))
             if isinstance(form, list) and len(form) > 1 and form[0] == "defun"]
    heap = C.prepare_heap([form[1] for form in forms])
    sizes: dict[str, int] = {}
    for form in forms:
        name, code, helpers = C.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile="dialect-v2",
            prebuilt_primitives=True)
        require(not helpers, f"hybrid introduced compiler helper: {name}")
        sizes[name] = len(code.encode())
    for name in ("%rl-render", "%rl-put", "%read-line-loop"):
        require(sizes[name] <= 255, f"bytecode object overflow: {name}")
    return sizes


def responsiveness_gate(contract: dict[str, Any]) -> dict[str, Any]:
    raw = PRICE.execute_route(EDITOR, "batch", 40, batch_cap=8)
    price = contract["responsiveness"]
    frames = (raw["vm_steps_per_character"]
              * price["calibration_cycles_per_vm_step"]
              / price["cycles_per_frame"]
              + raw["screen_cells_per_character"]
              * price["screen_cell_cycles"] / price["cycles_per_frame"]
              + raw["heap_cells_per_character"] * price["collection_frames"]
              / price["nursery_cells"])
    rate = 1.0 / frames
    margin = (rate - 1.0) * 100.0
    require(frames <= price["maximum_frames_per_character"]
            and rate >= price["minimum_service_events_per_frame"]
            and margin >= price["minimum_margin_percent"],
            f"responsiveness row red: frames={frames:.6f} rate={rate:.6f}")
    editor = EDITOR.read_text(encoding="utf-8")
    require("(key-event 2)" in editor and "(key-event 3)" in editor
            and "(if (= (car s4) 250) nil (key-event 3))" in editor,
            "adaptive/no-fixed-wait/max-line shape drift")
    return {**raw, "frames_per_character": frames,
            "service_events_per_frame": rate, "margin_percent": margin,
            "batch_fixture": 8, "adaptive_runtime_wait": 0}


def loss_gate(contract: dict[str, Any]) -> dict[str, Any]:
    row = PRICE.capture_simulation() if hasattr(PRICE, "capture_simulation") else None
    # The implementation predecessor owns the canonical non-atomic model.
    import c2_v160_comfort_input_fidelity as fidelity
    row = fidelity.capture_simulation()
    require(row["events_captured"] == 94 and row["ordered"]
            and row["dropped"] == 0 and row["sixth_event_present"],
            "94-event forced-collection wall red")
    return row


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract["format"] == FORMAT
            and contract["status"] == "owner-released-one-product-card",
            "hybrid contract identity drift")
    authority = ERA.era_bind(contract["authority_commit"],
                             PLAN.relative_to(ROOT).as_posix())
    text = ERA.era_blob(contract["authority_commit"],
        PLAN.relative_to(ROOT).as_posix()).decode("utf-8")
    for token in ("adaptive hybrid", "30.2 % margin", "a full ring drains"):
        require(token in text, f"implementation authority token absent: {token}")
    source = PRODUCT.read_text(encoding="utf-8")
    import c2_v160_input_drop_counters as counters
    placement = counters.linker_contract()
    require("configure_input_hybrid" in source
            and placement["free_bytes_minimum"] == 57
            and placement["fixed_floor_bytes"] == 54
            and placement["surplus_watch_bytes"] == 3,
            "born-derived hybrid placement gate absent")
    sizes = bytecode_sizes()
    return {"format": FORMAT, "status": "PASS: ADAPTIVE INPUT HYBRID HOST GREEN",
        "authority": authority, "contract": bind(CONTRACT),
        "sources": [bind(EDITOR), bind(EVAL), bind(VM), bind(HEADER),
                    bind(CAPTURE), bind(CONSUMER), bind(PRODUCT)],
        "normalization": normalization_gate(contract),
        "native_scalar": native_gate(contract),
        "bytecode_sizes": sizes,
        "bank2_touched_bytes": sum(sizes[n] for n in
            ("%rl-render", "%rl-put", "%read-line-loop")),
        "responsiveness": responsiveness_gate(contract),
        "loss_wall": loss_gate(contract),
        "walls": contract["walls"],
        "claim_limit": "host implementation gates only; no link, media or device claim"}


def selftest() -> None:
    value = derive()
    mutations = 0
    bad = json.loads(json.dumps(load(CONTRACT)))
    bad["normalization"][0]["delta"] = 31
    try:
        normalization_gate(bad)
    except GateError:
        mutations += 1
    else:
        raise GateError("normalization mutation survived")
    bad = json.loads(json.dumps(load(CONTRACT)))
    bad["responsiveness"]["maximum_frames_per_character"] = 0.7
    try:
        responsiveness_gate(bad)
    except GateError:
        mutations += 1
    else:
        raise GateError("responsiveness mutation survived")
    require(mutations == 2 and value["normalization"]["raw_inputs"] == 256,
            "hybrid selftest drift")
    print("v1.6 input service hybrid: SELFTEST PASS mutations=2 raw=256")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        value = derive()
        print("v1.6 input service hybrid: CHECK PASS "
              f"native={value['native_scalar']['bytes']} "
              f"frames={value['responsiveness']['frames_per_character']:.3f} "
              f"margin={value['responsiveness']['margin_percent']:.1f}%")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 input service hybrid: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
