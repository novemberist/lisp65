#!/usr/bin/env python3
"""Attribute the Block-3 B3-1 device input freeze without a device retry.

The delivered editor arms the resident capture ring, but the Block-3 idle
scheduler polls the public hardware queue.  On the target the IRQ owns that
queue while capture is armed, so the key has already moved to the private ring
when the public poll runs.  The host VM did not model that arbitration and was
therefore a false-green fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORITY_COMMIT = "d38ea2e3"
PLAN_HEADER = (
    "## Owner decision — v2.0 reshaped; the delivery chain becomes the target — 2026-09-01")
PRODUCT_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-receipt.json")
DEVICE_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-device-result-receipt.json")
HOST_PREFLIGHT = ARCH / (
    "c2.3-v2.0-block3-banner-only-repair-preflight.json")
V19_DEVICE = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-device-result-receipt.json")
DISASM = ROOT / (
    "build/c2.3/v2.0-block3-banner-only-repair-preflight/stdlib-p0.disasm.txt")
MANIFEST = ROOT / (
    "build/c2.3/v2.0-block3-banner-repair-product-card-r2-preflight/"
    "setup-owned/static-plane/narrow-static/stdlib-p0.manifest.json")
PROFILE = ROOT / (
    "build/c2.3/v2.0-block3-banner-repair-product-card-r2/wplto/resolved-profile.txt")
V19_EDITOR = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/sources/stdlib-read-line.lisp")
LIVE_EDITOR = ROOT / "lib/stdlib-read-line.lisp"
EDITOR_EVIDENCE_ERA = "d38ea2e3"
VM_SOURCE = ROOT / "src/vm.c"
IRQ_SOURCE = ROOT / "src/optional/c2_kernal_input_capture.s"
TAKE_SOURCE = ROOT / "src/optional/c2_kernal_input_consumer.s"
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
HOST_VM = ROOT / "tools/host-lisp/bytecode_p0.py"
RECEIPT = ARCH / "c2.3-v2.0-block3-b31-input-attribution-receipt.json"
STATUS = "PASS: B3-1 ATTRIBUTED TO ARMED-RING/PUBLIC-QUEUE SOURCE SPLIT"
FORMAT = "lisp65-c2-v200-block3-b31-input-attribution-v1"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_editor() -> tuple[str, dict[str, Any]]:
    relative = LIVE_EDITOR.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{EDITOR_EVIDENCE_ERA}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return raw.decode("utf-8"), {"path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_file(path: Path) -> tuple[bytes, dict[str, Any]]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{EDITOR_EVIDENCE_ERA}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return raw, {"path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_vm() -> tuple[str, dict[str, Any]]:
    raw, binding = sealed_file(VM_SOURCE)
    return raw.decode("utf-8"), binding


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "B3-1 authority section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("b3-1 is attributed now", "host-only", "zero contacts",
                  "blink idle"):
        require(token in folded, f"B3-1 authority absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORITY_COMMIT, "path": relative,
            "section": PLAN_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "right": "host-only attribution; zero device contacts, WPLTOs, links or repairs"}


def function_block(text: str, name: str) -> str:
    match = re.search(
        rf"^\[\d+\] {re.escape(name)}\n(?P<body>.*?)(?=^\[\d+\] |\Z)",
        text, flags=re.MULTILINE | re.DOTALL)
    require(match is not None, f"emitted function absent: {name}")
    return match.group(0)


def manifest_entry(name: str) -> dict[str, Any]:
    rows = load(MANIFEST).get("entries")
    require(isinstance(rows, list), "Block-3 manifest entries absent")
    matches = [row for row in rows if isinstance(row, dict)
               and row.get("kind") == "function" and row.get("name") == name]
    require(len(matches) == 1, f"manifest function identity drift: {name}")
    return matches[0]


def emitted_route() -> dict[str, Any]:
    text = DISASM.read_text(encoding="utf-8")
    poll = function_block(text, "%rl-poll")
    read_line = function_block(text, "read-line")
    require("length: 197" in poll
            and "002c PUSHI8 0" in poll
            and "002e CALLPRIM prim=60:key-event argc=1" in poll,
            "final Block-3 %rl-poll is not the public nonblocking queue route")
    require("length: 118" in read_line
            and "CALLPRIM prim=62:poke argc=3" in read_line,
            "final Block-3 read-line arm owner drift")
    poll_row = manifest_entry("%rl-poll")
    read_row = manifest_entry("read-line")
    require(int(poll_row["length"]) == 197 and int(read_row["length"]) == 118,
            "disassembly/manifest object identity mismatch")
    profile = PROFILE.read_text(encoding="utf-8")
    require("LISP65_V160_INPUT_CAPTURE" in profile
            and "LISP65_V160_INPUT_HYBRID" in profile,
            "final linked profile lacks the armed capture/hybrid world")
    source, source_binding = sealed_editor()
    require("(poke 255 141 0)" in source
            and "(defun %rl-poll" in source
            and "(key-event 0)" in source,
            "living editor source no longer expresses the attributed route")
    return {
        "poll": {"entry": poll_row, "bytecode_offset": "0x002c/0x002e",
                 "mode": 0, "consumer": "public hardware queue"},
        "read_line": {"entry": read_row,
                      "arm_write": "$FF8D := $00",
                      "closed_marker": "$FF"},
        "profile_features": ["LISP65_V160_INPUT_CAPTURE",
                             "LISP65_V160_INPUT_HYBRID"],
        "bindings": [bind(DISASM), bind(MANIFEST), bind(PROFILE),
                     source_binding],
    }


def target_contract() -> dict[str, Any]:
    vm, vm_binding = sealed_vm()
    irq = IRQ_SOURCE.read_text(encoding="utf-8")
    take = TAKE_SOURCE.read_text(encoding="utf-8")
    interrupt = INTERRUPT_SOURCE.read_text(encoding="utf-8")
    require("mode == 2 || mode == 3" in vm
            and "c2_kernal_input_take" in vm
            and "lisp_input_event(0u, 0u, &event)" in vm,
            "target key-event mode ownership drift")
    require("lda C2K_INPUT_RING_TAIL" in irq
            and "lda $d60a" in irq and "lda $d619" in irq
            and "inc C2K_INPUT_EVENTS_STORED" in irq,
            "IRQ capture queue-to-ring transfer drift")
    require("inc C2K_INPUT_EVENTS_TAKEN" in take,
            "private ring-take witness drift")
    require("every other tail value makes it the sole queue" in interrupt,
            "single-owner queue contract absent")
    return {
        "armed_owner": "IRQ capture is the sole physical-queue consumer",
        "public_modes": [0, 1],
        "private_ring_modes": [2, 3],
        "transfer": "$D60A/$D619 -> C2K_INPUT_RING_BASE",
        "taken_witness": "C2K_INPUT_EVENTS_TAKEN increments only in c2_kernal_input_take",
        "bindings": [vm_binding, bind(IRQ_SOURCE), bind(TAKE_SOURCE),
                     bind(INTERRUPT_SOURCE)],
    }


def simulate(mode: int, *, irq_enabled: bool = True) -> dict[str, Any]:
    physical = [0x41]
    ring: list[int] = []
    counters = {"raw": 0, "seen": 0, "stored": 0, "taken": 0}
    if irq_enabled and physical:
        counters["raw"] += 1
        counters["seen"] += 1
        ring.append(physical.pop(0))
        counters["stored"] += 1
    if mode in (2, 3):
        value = ring.pop(0) if ring else 0
        if value:
            counters["taken"] += 1
            if 0x41 <= value < 0x5B:
                value |= 0x20
    else:
        value = physical.pop(0) if physical else 0
    return {"input": "PETSCII $41", "mode": mode,
            "irq_capture_before_poll": irq_enabled,
            "result": None if value == 0 else value,
            "physical_queue": physical, "ring": ring,
            "counters": counters}


def ownership_model() -> dict[str, Any]:
    candidate = simulate(0)
    successor = simulate(2)
    host_false_green = simulate(0, irq_enabled=False)
    require(candidate["result"] is None and candidate["ring"] == [0x41]
            and candidate["counters"]["taken"] == 0,
            "candidate ownership model no longer reproduces the freeze")
    require(successor["result"] == 0x61 and successor["ring"] == []
            and successor["counters"] ==
                {"raw": 1, "seen": 1, "stored": 1, "taken": 1},
            "private-consumer counterfactual does not drain the ring")
    require(host_false_green["result"] == 0x41,
            "host false-green model no longer bypasses IRQ arbitration")
    return {"candidate": candidate,
            "sharp_countermutation_key_event_0_to_2": successor,
            "host_without_async_irq_arbitration": host_false_green,
            "mutations_rejected": [
                "claim-mode-0-consumes-the-armed-ring",
                "claim-host-key-event-list-models-target-IRQ-arbitration",
                "claim-input-freeze-is-a-blink-service-time-stall",
            ]}


def host_fixture_gap() -> dict[str, Any]:
    preflight_raw, _preflight_binding = sealed_file(HOST_PREFLIGHT)
    preflight = json.loads(preflight_raw)
    candidate = preflight["composed_framebuffer_gate"]["candidate"]
    require(candidate["row_24"] == "lisp65> abc",
            "Block-3 host false-green framebuffer observation drift")
    host_raw, host_binding = sealed_file(HOST_VM)
    host = host_raw.decode("utf-8")
    require("if name == \"key-event\":" in host
            and "code, modifiers = self.key_events.pop(0)" in host
            and "def _c2_raw_capture_before_peek" in host,
            "host input fixture implementation drift")
    return {"observed_false_green": candidate,
            "mechanism": ("mode-0 key-event consumes the fixture key_events list "
                          "directly; asynchronous target IRQ queue-to-ring transfer "
                          "is only modeled at an explicit peek seam"),
            "binding": host_binding}


def predecessor() -> dict[str, Any]:
    source = V19_EDITOR.read_text(encoding="utf-8")
    require("(%rl-render nil 0 0 0 0 -1)" in source,
            "accepted v1.9 private ring route absent")
    receipt = load(V19_DEVICE)
    row = next(row for row in receipt["rows"]
               if row["id"] == "ABR7-2-native-prompt-editor")
    require(row["result"] == "PASS" and "(1 2 3)" in row["observations"][0],
            "v1.9 device editor authority drift")
    return {"route": "%read-line-loop -> %rl-render(row=-1) -> key-event 2",
            "device_row": row, "bindings": [bind(V19_EDITOR), bind(V19_DEVICE)]}


def derive() -> dict[str, Any]:
    product = load(PRODUCT_RECEIPT)
    pair = product["artifacts_after"]
    require(product["status"] ==
            "PASS: V2.0 BLOCK3 BANNER REPAIR PRODUCT CARD GREEN"
            and pair["ELF"]["sha256"] ==
                "75f5700343d27dc68a4e46e67c663d75ee148b3cb37a1a805cea093f49442a83"
            and pair["PRG"]["sha256"] ==
                "89963ac6178dd752b7aef5b852a7518d06f7eb576234e2811455999fa4b0c995",
            "frozen repaired Block-3 pair drift")
    device = load(DEVICE_RECEIPT)
    red = next(row for row in device["observations"]
               if row["id"] == "B3-1-line-editor-matcher")
    require(red["result"] == "FIRST RED: DAILY-USE INPUT FREEZE",
            "B3-1 device observation drift")
    return {
        "format": FORMAT, "recorded_on": "2026-09-01", "status": STATUS,
        "authority": authority(),
        "frozen_pair": {"ELF": pair["ELF"], "PRG": pair["PRG"]},
        "device_observation": red,
        "emitted_route": emitted_route(),
        "target_contract": target_contract(),
        "ownership_execution": ownership_model(),
        "accepted_predecessor": predecessor(),
        "host_false_green": host_fixture_gap(),
        "attribution": {
            "named_mechanism": "armed-ring/public-queue source split",
            "sequence": [
                "read-line writes $00 to C2K_INPUT_RING_TAIL and arms capture",
                "the raster IRQ becomes the sole physical-queue owner",
                "the IRQ acknowledges the physical event and stores it in the private ring",
                "%rl-poll calls key-event mode 0 and observes the now-empty public queue",
                "the first event remains in the ring; no dispatch occurs and the prompt appears frozen",
            ],
            "classification": "product input-consumption wiring defect plus host fixture-fidelity gap",
            "blink_role": "the idle rewrite introduced the mode-0 seam; scanner/blink work never receives a key",
            "not_service_time": True,
            "not_generic_keyboard_failure": True,
        },
        "claim_limit": {
            "proves": "mechanism for the deterministic B3-1 repaired-world device freeze",
            "does_not": ["repair Block 3", "reopen interactive freight",
                         "authorize WPLTO, link, medium or device contact"],
            "next": "input to the commissioned interactive delivery-chain block",
        },
        "bindings": [bind(PRODUCT_RECEIPT), bind(DEVICE_RECEIPT),
                     sealed_file(HOST_PREFLIGHT)[1]],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("record", "check"))
    args = parser.parse_args()
    raw = canonical(derive())
    if args.command == "record":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(raw)
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == raw,
                "B3-1 attribution receipt drift; run record intentionally")
    print("c2-v200-block3-b31-input-attribution: PASS "
          "mechanism=armed-ring/public-queue-source-split")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v200-block3-b31-input-attribution: FAIL {error}")
        raise SystemExit(1)
