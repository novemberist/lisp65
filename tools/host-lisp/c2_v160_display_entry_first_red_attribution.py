#!/usr/bin/env python3
"""Attribute the v1.6 display-entry First Red from the frozen read-only row."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-contact/"
    "display-entry-first-red-stopped-state/capture.json")
ELF = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/lisp65-c2-substitution-linked.prg.elf")
COMFORT_MANIFEST = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library-inputs/"
    "repl-comfort.manifest.json")
COMFORT_BLOB = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library-inputs/"
    "repl-comfort.blob.bin")
V16CORE_MANIFEST = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library-inputs/"
    "v16core.manifest.json")
VM = ROOT / "src/vm.c"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-display-entry-first-red-attribution.json")


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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
    require(0 <= offset <= len(raw) - 2, "u16 outside captured row")
    return int.from_bytes(raw[offset:offset + 2], "little")


def symbol_publication(ext: bytes, nsym: int) -> tuple[dict[str, int], dict[int, int]]:
    namepool = 10208
    max_sym = 752
    nameoff_at = namepool + max_sym * 2
    symfn_at = nameoff_at + max_sym * 2
    require(symfn_at + max_sym * 2 == len(ext),
            "Bank-5 publication extent drift")
    names: dict[str, int] = {}
    functions: dict[int, int] = {}
    require(0 < nsym <= max_sym, "live symbol count outside publication")
    for index in range(nsym):
        at = u16(ext, nameoff_at + index * 2)
        if at < namepool:
            end = ext.find(b"\0", at, namepool)
            if end >= 0:
                name = ext[at:end].decode("latin-1", "replace")
                if name:
                    require(name not in names, f"duplicate runtime symbol: {name}")
                    names[name] = index
        functions[index] = u16(ext, symfn_at + index * 2)
    return names, functions


def derive() -> dict[str, Any]:
    inputs = {name: bind(path) for name, path in {
        "capture": CAPTURE, "candidate_ELF": ELF,
        "comfort_manifest": COMFORT_MANIFEST, "comfort_blob": COMFORT_BLOB,
        "v16core_manifest": V16CORE_MANIFEST, "VM_source": VM,
        "attribution_tool": Path(__file__).resolve(),
    }.items()}
    capture = load(CAPTURE)
    require(capture["format"] ==
            "lisp65-c2.3-v1.6-display-entry-first-red-raw-v1"
            and capture["tuple"]["PC"] == "0xe096"
            and capture["discipline"]["CPU_left_stopped"] is True
            and capture["discipline"]["resumes"] == 0,
            "stopped-state identity or discipline drift")
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    require(set(rows) == {"bank0-zp-stack", "vm-error-status",
            "hot-heap-state", "bank4-installed-object-headers",
            "bank5-symbol-publication"}, "capture row inventory drift")

    bank0 = rows["bank0-zp-stack"]
    vmstate = rows["vm-error-status"]
    require(bank0[0x38] == 43, "pending error is not VM_BAD_BYTECODE")
    # vm-error-status begins at $bfe0: high byte of littab, then code pointer,
    # payload offset/length, capacity, window, window length and streaming.
    decoded = {
        "code_pointer": f"0x{u16(vmstate, 1):04x}",
        "payload_offset": u16(vmstate, 3),
        "payload_length": u16(vmstate, 5),
        "payload_window_capacity": u16(vmstate, 7),
        "window_start": u16(vmstate, 9),
        "window_length": u16(vmstate, 11),
        "streaming": vmstate[13],
    }
    require(decoded == {"code_pointer": "0xbfc7", "payload_offset": 35,
            "payload_length": 220, "payload_window_capacity": 21,
            "window_start": 0x45, "window_length": 21, "streaming": 1},
            f"unexpected VM window state: {decoded}")

    comfort = load(COMFORT_MANIFEST)
    v16core = load(V16CORE_MANIFEST)
    step = next(row for row in comfort["entries"] if row["name"] == "%repl-step")
    helper = next(row for row in v16core["entries"]
                  if row["name"] == "%rl-screen-tail")
    loop = next(row for row in v16core["entries"]
                if row["name"] == "%read-line-loop")
    require((step["length"], step["lit_count"],
             step["length"] - (7 + 2 * step["lit_count"])) == (255, 14, 220)
            and (helper["length"], helper["lit_count"]) == (185, 2)
            and loop["length"] == 250,
            "candidate object geometry drift")

    names, functions = symbol_publication(
        rows["bank5-symbol-publication"], u16(bank0, 0x5D))
    identities = {}
    for name, expected_directory in (("%read-line-loop", 760),
                                     ("%rl-screen-tail", 762),
                                     ("%repl-step", 765)):
        index = names[name]
        raw = functions[index]
        require(raw == 0xC000 + expected_directory * 2,
                f"runtime function identity drift: {name}")
        identities[name] = {"symbol_index": index,
                            "function_cell": f"0x{raw:04x}",
                            "directory": expected_directory}

    blob = COMFORT_BLOB.read_bytes()
    obj_at = int(step["blob_offset"])
    obj = blob[obj_at:obj_at + int(step["length"])]
    payload = obj[35:]
    bank4 = rows["bank4-installed-object-headers"]
    # Literal words in the immutable source carrier are placeholders and are
    # materialized by c2_product_entry_read.  Payload bytes are immutable.
    live_payload_at = bank4.find(payload[:64])
    require(live_payload_at == 0x6B4D,
            f"unique live %repl-step payload not found: {live_payload_at:#x}")
    compared = min(len(payload), len(bank4) - live_payload_at)
    require(compared == 179
            and bank4[live_payload_at:live_payload_at + compared]
                == payload[:compared],
            "live/source %repl-step payload differs")

    vm_source = VM.read_text(encoding="utf-8")
    for token in (
        "if (vm_status != VM_OK) { r = res; goto done; }",
        "BUF_ENSURE_MINE(pcur);",
        "win = (pcur_); winlen = 0; ip = code; streaming = 1;",
        "winlen = (uint16_t)(((uint16_t)(payload_len - pc_) < pwin_max)",
        "if (!vm_object_load(bank, off, (uint16_t)(payload_off + pc_), winlen",
    ):
        require(token in vm_source, f"VM return/refill seam drift: {token}")

    # The caller identity proves that the nested helper returned VM_OK and the
    # caller header was reparsed.  The observed winlen does *not* prove that
    # the payload read completed: WIN_ENSURE assigns it before vm_object_load.
    return {
        "format": "lisp65-c2.3-v1.6-display-entry-first-red-attribution-v1",
        "recorded_on": "2026-08-22",
        "status": "ATTRIBUTED TO CALLER RETURN/REFILL SEAM; MECHANISM SPLIT OPEN",
        "inputs": inputs,
        "device_result": {
            "pending_error": {"code": 43, "name": "VM_BAD_BYTECODE"},
            "VM_window": decoded,
            "runtime_identities": identities,
            "live_payload": {"physical_start": "0x00046b4d",
                             "bytes_compared": compared,
                             "differences": 0,
                             "source": "%repl-step payload"},
        },
        "decisions": {
            "mixed_library_identity": "EXCLUDED: one symbol and one BCODE directory per function",
            "helper_failure": ("EXCLUDED: a non-OK helper return exits before BUF_ENSURE_MINE; "
                               "the captured globals are the reparsed %repl-step caller"),
            "stale_or_corrupt_payload_source":
                "EXCLUDED for all 179 captured bytes, including the complete $45..$59 band",
            "remaining_split": [
                ("caller payload refill at logical PC $45 returned failure; WIN_ENSURE "
                 "records $45/21 before it calls vm_object_load"),
                ("caller payload refill completed, then the operand-stack result was lost "
                 "before DROP at $45 or the later DROP at $52"),
            ],
        },
        "instrument_gap": {
            "missing_range": "vm_codebuf $bfa4..$bfdb",
            "why_decisive": ("source bytes plus requested window cannot distinguish a failed "
                              "read from a completed read; the destination buffer can"),
            "self_correction": ("$45/21 is an attempted-window witness, not a completion "
                                "witness; no operand-stack mechanism is claimed"),
        },
        "next_step": {
            "kind": "host-first attribution/instrument specification; no fix authorized",
            "required_observation": ("bind refill success/failure and the post-CALL operand "
                                     "depth at logical PC $45 in the same final-world path"),
            "fixture_rule": ("a streamed caller with 14 literals, 21-byte payload window and "
                             "a nested CALL immediately before a refill must be a permanent gate"),
        },
        "claim_limit": ("Excludes the proposed mixed-identity/helper hypotheses and narrows the "
                        "First Red to the caller return/refill seam. It does not choose between "
                        "refill failure and operand-stack loss, authorize a fix, link, medium, "
                        "or another device contact."),
    }


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_display_entry_first_red_attribution.py check|write")
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "display-entry attribution receipt drift")
    print("v1.6 display-entry First Red: PASS identities=consistent "
          "payload=179/179 split=refill-or-stack")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, StopIteration) as error:
        print(f"v1.6 display-entry First Red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
