#!/usr/bin/env python3
"""Name the dynamic RTOV holder from the broadened v1.6 stopped-state row."""

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


ELF = ROOT / ("build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / ("build/c2.3/v1.6-items12-hybrid-owner-contact/"
                  "stale-holder-broadened-stopped-state/capture.json")
SPEC = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.3-v1.6-primary-vm-type-attribution-receipt.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-stale-holder-broadened-result-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2.3-v1.6-stale-holder-broadened-result-v1"
WINDOW = (0xC356, 0xCA92)
EXPECTED = {"ELF": "a03f9fafc5629f913dcf213925d7f007fd91b353ab2229a6189080c37f604c9c",
            "capture": "69b42d51b3d7eaf920f564471d7515d6de7fa09058aa036dc0371548bbc65776"}


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
    inputs = {"ELF": bind(ELF), "capture": bind(CAPTURE), "read_spec": bind(SPEC)}
    require({name: inputs[name]["sha256"] for name in EXPECTED} == EXPECTED,
            "broadened stopped-state identity drift")
    spec = load(SPEC)
    require(spec["track_2"]["status"] ==
            "SPECIFIED; OWNER CONTACT REQUIRED; NOT EXECUTED",
            "Track-2 read specification drift")
    capture = load(CAPTURE)
    require(capture["tuple"]["PC"] == "0xe096"
            and capture["tuple"]["SP"] == "0x01c5"
            and capture["tuple"]["MAPL"] == "0x0000"
            and capture["tuple"]["MAPH"] == "0x8000"
            and capture["discipline"] == {"CPU_left_stopped": True,
                "D2_D5_executed": False, "raw_first": True, "resets": 0,
                "resumes": 0, "runs": 0, "stops": 1,
                "tuple_before_memory": True},
            "bound stopped-state/protocol drift")
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    require({name: len(raw) for name, raw in rows.items()} == {
        "gc-rootsp": 2, "gc-rootstack": 256, "evaluator-holders": 8,
        "lisp-toplevel-jmp-buf": 19, "vm-upvals": 2,
        "bank5-publication-domain": 14720},
        "broadened range extent drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    for name, address in (("lisp_toplevel", 0xBD47), ("setjmp", 0x23F9),
                          ("longjmp", 0x2460), ("__call_indir", 0x24CB)):
        require(truth.symbol(name).value == address, f"candidate symbol drift: {name}")
    text = truth.section(".text"); text_raw = truth.section_bytes(".text")
    code = lambda first, last: text_raw[first - text.address:last - text.address]
    setjmp = code(0x23F9, 0x2460)
    longjmp = code(0x2460, 0x24CB)
    indirect = code(0x24CB, 0x24CE)
    require(
        bytes.fromhex("a514c89104a515c89104") in setjmp
        and bytes.fromhex("b104851588b1048514") in longjmp
        and indirect == bytes.fromhex("6c1400"),
        "emitted setjmp/longjmp/indirect register identity drift",
    )

    jmp = rows["lisp-toplevel-jmp-buf"]
    require(jmp.hex() == "60aadececf56c3d0cf003901010904d3005202",
            "live jmp_buf bytes drift")
    saved_pairs = [{"pair": f"__rc{18 + offset}/__rc{19 + offset}",
                    "jmp_buf_offset": 5 + offset,
                    "value": f"0x{u16(jmp, 5 + offset):04x}"}
                   for offset in range(0, 14, 2)]
    in_window = [row for row in saved_pairs
                 if WINDOW[0] <= int(row["value"], 16) < WINDOW[1]]
    require(in_window == [{"pair": "__rc18/__rc19", "jmp_buf_offset": 5,
                           "value": "0xc356"}],
            "unique saved-CSR holder decision drift")
    require(u16(jmp, 0) == 0xAA60,
            "setjmp native return identity drift")

    # Type-aware publication decoding is essential: raw Cxxx values in symfn
    # are BCODE immediates, not heap/native pointers into the RTOV VMA.
    ext = rows["bank5-publication-domain"]
    namepool = 10208; max_sym = 752
    symval_at = namepool
    nameoff_at = symval_at + max_sym * 2
    symfn_at = nameoff_at + max_sym * 2
    require(symfn_at + max_sym * 2 == len(ext), "Bank-5 symbol layout drift")
    publication_rows = []
    pointer_targets = []
    for index in range(max_sym):
        value = u16(ext, symfn_at + index * 2)
        if WINDOW[0] <= value < WINDOW[1]:
            name_at = u16(ext, nameoff_at + index * 2)
            name = ext[name_at:name_at + 34].split(b"\0", 1)[0].decode(
                "latin-1", "replace")
            is_bcode = value % 2 == 0 and 0xC000 <= value < 0xE000
            is_pointer = value != 0 and value < 0x8000 and value % 2 == 0
            publication_rows.append({"index": index, "name": name,
                                     "value": f"0x{value:04x}",
                                     "classification": "BCODE-immediate" if is_bcode
                                     else "other"})
            if is_pointer:
                pointer_targets.append((index, value))
    symval_targets = [index for index in range(max_sym)
                      if WINDOW[0] <= u16(ext, symval_at + index * 2) < WINDOW[1]
                      and u16(ext, symval_at + index * 2) < 0x8000]
    require(len(publication_rows) == 90 and not pointer_targets and not symval_targets,
            "typed publication-holder classification drift")
    require(u16(rows["gc-rootsp"], 0) == 0
            and rows["vm-upvals"] == b"\0\0"
            and not any(WINDOW[0] <= u16(rows["evaluator-holders"], offset) < WINDOW[1]
                        for offset in range(0, 8, 2)),
            "secondary dynamic-holder exclusion drift")

    return {
        "format": FORMAT,
        "status": "ATTRIBUTED: LISP_TOPLEVEL SAVED CSR HOLDS RETIRED RTOV ENTRY",
        "recorded_on": "2026-08-20", "inputs": inputs,
        "contact": {"device_contacts": 1, "stops": 1, "reads": 6,
                    "bytes": sum(len(raw) for raw in rows.values()),
                    "resumes": 0, "runs_after_stop": 0, "CPU_left_stopped": True},
        "named_holder": {
            "owner": "lisp_toplevel.csrs[0..1]",
            "ABI_identity": "saved __rc18/__rc19",
            "address": "0xbd4c..0xbd4d", "value": "0xc356",
            "target": "defprim / first byte of retired RTOV window",
            "setjmp_save": "emitted setjmp stores __rc18 then __rc19 at jmp_buf offsets 5/6",
            "longjmp_restore": "emitted longjmp restores offsets 6/5 to __rc19/__rc18",
            "consumer": "__call_indir is JMP ($14), i.e. __rc18/__rc19",
            "causal_chain": ["setjmp snapshots $c356 in the top-level continuation",
                             "VM_TYPE abort runs RTOV wipe",
                             "longjmp restores the pre-retirement $c356 snapshot",
                             "indirect control can re-enter the retired window"],
        },
        "excluded_holders": {
            "gc_rootstack": "live prefix empty (gc_rootsp=0)",
            "evaluator_holders": "no aligned RTOV-window value",
            "vm_upvals": "NIL",
            "symval": "no typed pointer into the RTOV window",
            "symfn": {"raw_values_in_numeric_window": 90,
                      "typed_pointer_targets": 0,
                      "classification": "all 90 are even $c000..$dffe BCODE immediates"},
        },
        "liveness_contract_form": {
            "rule": ("Before retiring an RTOV generation, every continuation snapshot "
                     "that may be restored afterward must contain no pointer into that generation."),
            "minimal_mechanism": ("sanitize every pointer-aligned saved-CSR pair in the active "
                                  "lisp_toplevel jmp_buf against the retiring VMA before wipe; "
                                  "then longjmp cannot resurrect a callable RTOV address"),
            "required_gates": ["all seven saved CSR pairs checked",
                               "mutation per pair restores a window pointer and fails",
                               "abort at every RTOV exit leaves no restored in-window pair",
                               "ordinary setjmp/longjmp ABI state outside RTOV is byte-preserved",
                               "deterministic old reproduction no longer reaches the BRK frame"],
        },
        "claim_limit": ("Names the holder and the required liveness-contract form. "
                        "It authorizes no fix card, link, medium, or further device contact."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"))
    action = parser.parse_args().action
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "broadened stale-holder result receipt drift")
    print("v1.6 stale-holder broadened result: PASS holder=lisp_toplevel.__rc18/19")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 stale-holder broadened result: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
