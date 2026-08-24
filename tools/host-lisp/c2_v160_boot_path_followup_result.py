#!/usr/bin/env python3
"""Bind the v1.6 boot-path follow-up read and decide class membership."""

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
from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / ("build/c2.3/v1.6-boot-refill-generator-template-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / "build/c2.3/v1.6-boot-path-followup-read-20260823/capture.json"
ATTRIBUTION = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                      "c2.3-v1.6-boot-path-two-layer-attribution.json")
FIRST_HOLDER = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                       "c2.3-v1.6-stale-holder-broadened-result-receipt.json")
REGISTRY = ROOT / ("build/c2.3/v1.6-boot-refill-dma-media/canonical-product/final/"
                   "runtime-overlay-verifier-bindings.bin")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-boot-path-followup-result.json")
FORMAT = "lisp65-c2.3-v1.6-boot-path-followup-result-v1"
EXPECTED = {
    "ELF": "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99",
    "capture": "538dcc947b6f0064c3dbc89ef2c98eefb25a810d62892c5b096e1905edaeb16e",
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def derive() -> dict[str, Any]:
    inputs = {"ELF": bind(ELF), "capture": bind(CAPTURE),
              "preceding_attribution": bind(ATTRIBUTION),
              "first_holder_result": bind(FIRST_HOLDER),
              "materialized_registry": bind(REGISTRY)}
    require({key: inputs[key]["sha256"] for key in EXPECTED} == EXPECTED,
            "follow-up result identity drift")
    capture = load(CAPTURE)
    require(capture["tuple"] == {
        "A": "0x02", "B": "0x00", "MAPH": "0x8000", "MAPL": "0x0000",
        "PC": "0xe096", "SP": "0x01ce", "X": "0x00", "Y": "0xe2",
        "Z": "0x00", "suffix": "4C96E0  00     24 ..E..I.. ...P 15 -  00 - .....lh."
    }, "original stopped tuple was not conserved")
    require(capture["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False, "raw_first": True,
        "resets": 0, "resumes": 0, "runs": 0, "stops": 1,
        "tuple_before_memory": True,
    }, "read-only stopped-state discipline drift")
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    require({name: len(raw) for name, raw in rows.items()} == {
        "lisp-toplevel-jmp-buf": 19,
        "vm-codebuf-and-bookkeeping": 75,
        "overlay-registry-bindings": 40,
        "overlay-call-family-generation": 10,
        "overlay-zp-transaction-state": 8,
        "map-generation": 1,
    }, "follow-up range extent drift")

    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
                          include_section_data=True)
    jmp = rows["lisp-toplevel-jmp-buf"]
    saved_pairs = [{"pair": f"__rc{18 + offset}/__rc{19 + offset}",
                    "jmp_buf_offset": 5 + offset,
                    "value": f"0x{u16(jmp, 5 + offset):04x}"}
                   for offset in range(0, 14, 2)]
    in_window = [row for row in saved_pairs
                 if 0xC356 <= int(row["value"], 16) < 0xCA91]
    require(in_window == [{"pair": "__rc18/__rc19", "jmp_buf_offset": 5,
                           "value": "0xc356"}],
            "unique current jmp_buf holder decision drift")
    first = load(FIRST_HOLDER)
    require(first["named_holder"]["ABI_identity"] == "saved __rc18/__rc19"
            and first["named_holder"]["value"] == "0xc356",
            "first holder identity drift")
    require(jmp.hex() == "fca9dececf56c3d0cf003901010904d3005202",
            "current jmp_buf bytes drift")

    vm = rows["vm-codebuf-and-bookkeeping"]
    require(vm == bytes(75), "refill window/bookkeeping is not fully retired")
    registry = rows["overlay-registry-bindings"]
    section = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    require(section.address == 0xB98C and section.bytes == 40,
            "registry section geometry drift")
    require(inputs["materialized_registry"]["sha256"]
            == "1125caaaee34cb1d796f7d1e99718c7a0c8f82047f9626965cf80f56b94f3225"
            and registry == REGISTRY.read_bytes(),
            "live overlay registry differs from completion truth")

    family = rows["overlay-call-family-generation"]
    zp = rows["overlay-zp-transaction-state"]
    require(family.hex() == "00180000000000020100"
            and zp.hex() == "9bcf000200000019"
            and rows["map-generation"] == b"\x01",
            "overlay generation/state discriminator drift")

    return {
        "format": FORMAT,
        "status": "PROVEN: THIRD RETIRED-WINDOW HOLDER INSTANCE; BOOT-PATH TRIGGER",
        "recorded_on": "2026-08-23", "inputs": inputs,
        "contact": {"kind": "read original conserved stop", "stops": 1,
                    "resumes": 0, "runs": 0, "resets": 0,
                    "bytes_read": sum(len(raw) for raw in rows.values()),
                    "CPU_left_stopped": True},
        "holder": {
            "owner": "current lisp_toplevel jmp_buf",
            "native_return": "0xa9fc",
            "saved_pairs": saved_pairs,
            "unique_in_window_pair": in_window[0],
            "same_as_first_holder": True,
            "first_instance_identity": first["named_holder"],
        },
        "retirement": {
            "vm_codebuf_and_bookkeeping": "75/75 bytes zero",
            "rtov_busy": 0, "rtov_loaded_len": 0,
            "rtov_fault": 0, "rtov_family": "session (2)",
            "rtov_family_generation": 1, "map_generation": 1,
            "registry": "40/40 live bytes equal the completion-materialized registry",
            "meaning": ("The execution/refill window is retired and its bookkeeping clear, "
                        "while a restorable continuation still names the window entry."),
        },
        "membership_decision": {
            "class": "retirement with a restorable in-generation reference",
            "instance_ordinal": 3,
            "new_trigger": "ordinary boot/banner path",
            "discriminator": ("The exact current jmp_buf, not zero-page resemblance, contains "
                              "$c356 while vm_codebuf/bookkeeping are fully zero."),
            "refuted_alternative": "fresh non-retired vm_codebuf payload or corrupt registry",
        },
        "escalation": {
            "required": True,
            "question": ("Move the v1.7 execution-boundary backstop into v1.6 now that the class "
                         "has a deterministic ordinary-boot trigger?"),
            "authority": "owner decision required by commission 17be2562",
            "no_automatic_fix": True,
        },
        "claim_limit": ("Proves class membership and the boot trigger. It does not choose or "
                        "authorize the execution-boundary design, a fix card, media or another "
                        "device contact."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        ("holder", "unique_in_window_pair", "value", "0xb411"),
        ("retirement", "vm_codebuf_and_bookkeeping", None, "74/75 bytes zero"),
        ("membership_decision", "instance_ordinal", None, 2),
    ]
    for first, second, third, replacement in mutations:
        clone = json.loads(json.dumps(value))
        if third is None:
            clone[first][second] = replacement
        else:
            clone[first][second][third] = replacement
        accepted = (clone["holder"]["unique_in_window_pair"]["value"] == "0xc356"
                    and clone["retirement"]["vm_codebuf_and_bookkeeping"] == "75/75 bytes zero"
                    and clone["membership_decision"]["instance_ordinal"] == 3)
        require(not accepted, "follow-up result mutation accepted")
    print(f"v1.6 boot-path follow-up result: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest(); return 0
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "boot-path follow-up result receipt drift")
    print("v1.6 boot-path follow-up result: PASS membership=retired-window instance=3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError) as error:
        print(f"v1.6 boot-path follow-up result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
