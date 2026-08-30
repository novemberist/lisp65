#!/usr/bin/env python3
"""Stop v1.8 media before a losslessness claim without an activation owner.

The Capture/Hybrid product card deliberately delivered an inert native
substrate.  This pre-media gate joins that product truth to the proposed
hardware claim.  It records a First Red when the selected media world excludes
the only owner that can atomically arm the ring.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"

import sys
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT_RECEIPT = ARCH / \
    "c2.3-v1.8-capture-hybrid-product-card-r1-receipt.json"
RELEASE_MEDIA = ARCH / "c2.3-v1.7.0-release-media-receipt.json"
ELF = ROOT / (
    "build/c2.3/v1.8-capture-hybrid-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CAPTURE = ROOT / "src/optional/c2_kernal_input_capture.s"
CONSUMER = ROOT / "src/optional/c2_kernal_input_consumer.s"
INTERRUPT = ROOT / "src/interrupt.c"
REPL = ROOT / "src/repl.c"
COMFORT = ROOT / "lib/repl-comfort.lisp"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
RECEIPT = ARCH / \
    "c2.3-v1.8-capture-hybrid-acceptance-pre-media-first-red.json"
REPORT = ROOT / \
    "docs/planning/v1.8.0-capture-hybrid-acceptance-pre-media-first-red.md"
FORMAT = "lisp65-c2-v18-capture-hybrid-acceptance-pre-media-first-red-v1"
ELF_SHA = "67f89b7354d0f473c3057508ed6a47af69edad29c0807bc1d6f031442daaceab"
PRG_SHA = "4a08b5a8e2cc1eb6924af0e43201fccaeea305bc56b7aa9ab37393d2e5e26123"
ARM = (
    "(poke 255 141 255)",
    "(poke 255 140 0)",
    "(dotimes (counter 4 nil)",
    "(poke 188 (+ 252 counter) 0)",
    "(poke 255 141 0)",
)
SEAL_ERA_COMMIT = "b7928fa07ca9d6a3f4d171cb4fa69f32ed4d9be6"


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def derive() -> dict[str, Any]:
    product = load(PRODUCT_RECEIPT)
    release_media = load(RELEASE_MEDIA)
    pair = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(pair["ELF"]["sha256"] == ELF_SHA, "frozen ELF identity drift")
    require(pair["PRG"]["sha256"] == PRG_SHA, "frozen PRG identity drift")
    require(product["artifacts_after"]["ELF"]["sha256"] == ELF_SHA
            and product["artifacts_after"]["PRG"]["sha256"] == PRG_SHA,
            "product receipt does not bind the frozen pair")

    configuration = product["configuration"]
    features = set(configuration["features"])
    require({"LISP65_V160_INPUT_CAPTURE", "LISP65_V160_INPUT_HYBRID"}
            <= features, "final product lacks Capture/Hybrid substrate")
    lifecycle = configuration["capture_lifecycle"]
    require(lifecycle["activation_in_product"] is False,
            "expected inert product lifecycle changed")
    require(lifecycle["arm_sequence"] == list(ARM),
            "accepted arm sequence drift")
    require("Comfort library" in configuration["closed_freight"]
            and "repl-comfort" in configuration["excluded"],
            "accepted product no longer excludes Comfort")

    truth = ElfTruth.read(
        ELF, llvm_readobj=READOBJ, include_section_data=True)
    state = truth.section(".lisp65_c2_kernal_window.state")
    state_bytes = truth.section_bytes(state.name)
    tail = truth.symbol("C2K_INPUT_RING_TAIL").value
    tail_offset = tail - state.address
    require(len(state_bytes) == 16 and tail_offset == 13,
            "final ELF Capture state geometry drift")
    require(state_bytes[tail_offset] == 0xff,
            "final ELF no longer starts with Capture closed")

    def era_text(path: Path) -> str:
        return ERA.era_blob(
            SEAL_ERA_COMMIT, path.relative_to(ROOT).as_posix()).decode("utf-8")

    comfort = era_text(COMFORT)
    repl = era_text(REPL)
    interrupt = era_text(INTERRUPT)
    consumer = era_text(CONSUMER)
    editor = era_text(EDITOR)
    require(all(token in comfort for token in ARM),
            "Comfort no longer owns the complete atomic arm sequence")
    require("C2K_INPUT_RING_TAIL = 0xff;" in repl
            and "C2K_INPUT_RING_TAIL = 0;" not in repl,
            "native REPL lifecycle changed")
    require("if (C2K_INPUT_RING_TAIL != C2K_INPUT_RING_CLOSED)" in interrupt,
            "evaluator queue-owner guard drift")
    require("lda C2K_INPUT_RING_TAIL" in consumer
            and "bmi .Ltake_none" in consumer,
            "consumer closed-ring guard drift")
    require("(key-event 2)" in editor and "(key-event 3)" in editor,
            "live editor no longer contains private ring consumers")

    library = release_media["library_closure"]
    require(library["Comfort_absent"] is True
            and library["row_names"] == ["v16core"],
            "release library closure no longer proves Comfort absent")

    return {
        "format": FORMAT,
        "recorded_on": "2026-08-28",
        "status": (
            "FIRST RED: LOSSLESSNESS CLAIM HAS NO SHIPPED CAPTURE "
            "ACTIVATION OWNER"),
        "frozen_pair": pair,
        "product_world": {
            "features_present": sorted(
                features & {"LISP65_V160_INPUT_CAPTURE",
                            "LISP65_V160_INPUT_HYBRID"}),
            "native_substrate_present": True,
            "activation_in_product": lifecycle["activation_in_product"],
            "closed_freight": configuration["closed_freight"],
            "excluded": configuration["excluded"],
            "product_receipt": bind(PRODUCT_RECEIPT),
        },
        "final_elf_origin": {
            "section": state.name,
            "section_address": state.address,
            "section_bytes": state.bytes,
            "initial_bytes_hex": state_bytes.hex(),
            "tail_symbol": tail,
            "tail_offset": tail_offset,
            "initial_tail": state_bytes[tail_offset],
            "meaning": "capture closed",
            "authority": "ElfTruth section bytes from the frozen final ELF",
        },
        "lifecycle_owners": {
            "arm_owner": "lib/repl-comfort.lisp",
            "arm_sequence": list(ARM),
            "native_repl": "close-only on abort",
            "interrupt": "read-only lifecycle guard",
            "consumer": "closed-tail returns empty; cannot arm itself",
            "live_editor": "modes 2/3 consume only after an owner arms",
            "sources": {name: ERA.era_bind(SEAL_ERA_COMMIT, path)
                        for name, path in {
                "capture": CAPTURE, "consumer": CONSUMER,
                "interrupt": INTERRUPT, "native_repl": REPL,
                "comfort": COMFORT, "editor": EDITOR}.items()},
        },
        "selected_media_claim_world": {
            "claim": "B2-1 lossless normal and fast typing",
            "claim_excludes": ["Comfort", "Matcher/Blink", "Block 3", "$22"],
            "available_optional_library_roles": library["row_names"],
            "comfort_absent_from_release_library": library["Comfort_absent"],
            "activation_owner_shipped": False,
            "B2_1_executable": False,
        },
        "decision": {
            "media_authorized_but_not_produced": True,
            "media_preflight": "STOP",
            "reason": (
                "The frozen product is an inert Capture/Hybrid substrate. "
                "The accepted claim world excludes its sole activation owner; "
                "hardware would exercise the public scalar key-event path and "
                "could not retire the fast-typing Known Issue."),
            "requires_owner_decision": True,
            "no_successor_before_decision": True,
        },
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "mutations": {
            "substrate_without_activation_claims_losslessness": "RED",
            "closed_tail_is_treated_as_armed": "RED",
            "excluded_arm_owner_is_hidden": "RED",
        },
        "claim_limit": (
            "This is a pre-media lifecycle/claim attribution.  It does not "
            "invalidate the review-green native substrate or its host walls."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "acceptance preflight receipt drift")


def selftest(value: dict[str, Any]) -> None:
    mutations = (
        lambda row: row["product_world"].update(activation_in_product=True),
        lambda row: row["final_elf_origin"].update(initial_tail=0),
        lambda row: row["selected_media_claim_world"].update(
            claim_excludes=["Matcher/Blink", "Block 3", "$22"]),
        lambda row: row["selected_media_claim_world"].update(
            B2_1_executable=True),
        lambda row: row["lifecycle_owners"]["sources"].update(
            native_repl=bind(REPL)),
    )
    for mutate in mutations:
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PreflightError:
            continue
        raise PreflightError("acceptance preflight mutation survived")


def write_report(value: dict[str, Any]) -> None:
    origin = value["final_elf_origin"]
    REPORT.write_text(f"""# v1.8 Capture/Hybrid acceptance pre-media First Red

Status: **STOP — B2-1 has no shipped activation owner**

The frozen pair remains review-green and byte-identical: ELF
`{value['frozen_pair']['ELF']['sha256']}` and PRG
`{value['frozen_pair']['PRG']['sha256']}`.  It contains the native Capture and
Hybrid substrate, but its own final receipt records
`activation_in_product: false`: Comfort is the sole atomic lifecycle owner and
is excluded from this card and from the proposed release claim.

ElfTruth closes the question at the final artifact.  The 16-byte state section
starts as `{origin['initial_bytes_hex']}`; `C2K_INPUT_RING_TAIL` is byte 13 and
equals `$FF`, the closed marker.  The native REPL only closes Capture on abort,
the IRQ observes the marker, and the consumer returns empty while it is
negative.  Only `lib/repl-comfort.lisp` performs the complete close / reset /
counter-zero / arm transaction.

Therefore the requested Comfort-free media could boot and accept input, but it
would use the old public scalar `key-event` path.  B2-1 would not exercise the
reviewed ring and could neither prove losslessness nor retire the v1.5
fast-typing Known Issue.  Treating an inert substrate as an active feature is
the exact false-green mutation this preflight rejects.

No D81 was produced.  WPLTO, product link, media and device counts are all
zero.  The product card stays green; the hardware handoff stops for an owner
decision about the missing client/lifecycle owner.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
        write_report(value)
    else:
        validate(load(RECEIPT))
    if action == "selftest":
        selftest(value)
    print("v1.8 Capture acceptance preflight: PASS bound First Red "
          "activation-owner=absent media=0 device=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, PreflightError) as error:
        print(f"v1.8 Capture acceptance preflight: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
