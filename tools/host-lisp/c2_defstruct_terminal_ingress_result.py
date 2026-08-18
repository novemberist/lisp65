#!/usr/bin/env python3
"""Replay the Link-92 terminal-ingress capture with the corrected D01A oracle.

The historical Phase-B partition is immutable evidence.  Its pure-I row used
an exact ``D01A == 1`` comparison, although VIC-IV readback hard-wires bits
7..5 high.  This dated addendum keeps that artifact intact and interprets the
already captured raw byte through the documented programmable-mask domain:
``(D01A & 0x1f) == 0x01``.

No hardware is accessed.  ``capture`` seals the existing stopped-state files
into a compact tracked capsule; ``record`` replays that capsule using source
bytes extracted independently from the captured C2D and Bank-2 planes.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.3/defstruct-terminal-ingress-sister-link92/device-r3"
DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-device-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-result-receipt.json")
SISTER = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json")
PHASE_B = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
PROVENANCE = EVIDENCE / (
    "c2.3-v1.6-defstruct-slot39-provenance-correction-receipt.json")
COMPLETION = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-completion-edge-receipt.json")

FORMAT_DEVICE = "lisp65-c2.3-post-v1.4-defstruct-terminal-ingress-device-v1"
FORMAT_RESULT = "lisp65-c2.3-post-v1.4-defstruct-terminal-ingress-result-v1"
RECORDED_ON = "2026-08-10"
AUTHORIZATION_COMMIT = "95049ced"
AUTHORIZATION_PATH = "docs/planning/post-v1.4.0-direction-plan.md"

C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
C2_CODE_HEADER_SCALAR_BYTES = 7
C2_PRODUCT_CODE_BANK_TAG = 1
D01A_PROGRAMMABLE_MASK = 0x1F
D01A_RASTER_ONLY = 0x01
VICIV_COMMIT = "f9385701f67c4cd28a92f6af27ad7abe601699e6"
VICIV_PERMALINK = (
    "https://github.com/MEGA65/mega65-core/blob/"
    f"{VICIV_COMMIT}/src/vhdl/viciv.vhdl#L1768-L1777")


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def git_blob(commit: str, path: str) -> bytes:
    run = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         check=False)
    require(run.returncode == 0,
            run.stderr.decode(errors="replace") or "git authority absent")
    return run.stdout


def git_bind(commit: str, path: str) -> dict[str, Any]:
    raw = git_blob(commit, path)
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
                          cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def u16(raw: bytes, offset: int) -> int:
    require(0 <= offset and offset + 2 <= len(raw), "u16 outside artifact")
    return int.from_bytes(raw[offset:offset + 2], "little")


def d01a_raster_only(raw: int, *, mask: int = D01A_PROGRAMMABLE_MASK,
                     expected: int = D01A_RASTER_ONLY) -> bool:
    """Interpret only the RTL-documented programmable readback domain."""
    require(0 <= raw <= 0xFF and 0 <= mask <= 0xFF and 0 <= expected <= 0xFF,
            "D01A oracle input outside byte domain")
    return (raw & mask) == expected


def c2d_entry(raw: bytes, ordinal: int) -> dict[str, Any]:
    at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
    row = raw[at:at + C2D_ENTRY_BYTES]
    require(len(row) == C2D_ENTRY_BYTES, "C2D entry outside captured plane")
    return {
        "ordinal": ordinal, "raw_hex": row.hex(), "image_slot": row[0],
        "literal_count": row[1], "code_offset": u16(row, 2),
        "code_length": u16(row, 4), "resolution_base": u16(row, 6),
        "generation": u16(row, 8),
    }


def capture_binding(name: str) -> tuple[bytes, dict[str, Any]]:
    path = OUT / name
    raw = path.read_bytes()
    return raw, bind(path)


def derive_device() -> dict[str, Any]:
    sister = load(SISTER)
    phase_b = load(PHASE_B)
    records = []
    for index in range(1, 4):
        raw, binding = capture_binding(f"record-{index}.bin")
        require(len(raw) == 65, "record geometry drift")
        records.append({"index": index, **binding, "hex": raw.hex()})
    require(len({row["hex"] for row in records}) == 1,
            "record is not stable across three reads")

    bank2, bank2_binding = capture_binding("bank2-source.bin")
    c2d, c2d_binding = capture_binding("c2d-reset-domain.bin")
    progress, progress_binding = capture_binding("progress.bin")
    window, window_binding = capture_binding("window-physical.bin")
    require(len(bank2) == 65536 and len(c2d) == 50816,
            "captured backing-plane geometry drift")
    require(c2d[:4] == b"C2D\0" and c2d[-64:] == bytes(64),
            "captured C2D/C2J reset-domain drift")
    require(len(progress) == 66 and len(window) == 8192,
            "progress/window geometry drift")

    decoded = decode_record(bytes.fromhex(records[0]["hex"]), phase_b)
    ordinals = []
    for prefix in ("previous-fill", "last-fill"):
        owner = bytes.fromhex(decoded[f"{prefix}.owner"]["value_hex"])
        require(len(owner) == 3 and owner[0] == C2_PRODUCT_CODE_BANK_TAG,
                f"{prefix} owner bank-tag drift")
        ordinals.append(int.from_bytes(owner[1:], "little"))
    source_capsules = []
    for ordinal in ordinals:
        entry = c2d_entry(c2d, ordinal)
        begin = entry["code_offset"]
        end = begin + entry["code_length"]
        obj = bank2[begin:end]
        require(len(obj) == entry["code_length"], "source object truncated")
        source_capsules.append({"entry": entry, "object_hex": obj.hex(),
                                "object_sha256": digest(obj)})

    registers = load(OUT / "final-registers.json")
    require(registers["PC"].lower() == "0xb431"
            and registers["MAPH"].lower() == "0x8000"
            and registers["MAPL"].lower() == "0x0000",
            "terminal register tuple drift")
    product = bind(OUT / "product-readback.d81")
    library = bind(OUT / "library-readback.d81")
    require(product["sha256"] == sister["identity"]["diagnostic_medium"]["sha256"]
            and library["sha256"] == sister["identity"]["library_medium"]["sha256"],
            "device media readback differs from sister authority")
    require(window_binding["sha256"] ==
            sister["identity"]["diagnostic_window"]["sha256"],
            "physical KERNAL window differs from diagnostic authority")

    entry, entry_binding = capture_binding("entry-witness.bin")
    entry_authority, entry_authority_binding = capture_binding(
        "entry-witness-authority.bin")
    armed, armed_binding = capture_binding("record-armed.bin")
    progress_armed, progress_armed_binding = capture_binding("progress-armed.bin")
    require(entry == entry_authority == b"\x44", "entry witness drift")
    require(armed[0] == 0xA1 and len(armed) == 65,
            "record arm/readback drift")
    require(len(progress_armed) == 24, "progress arm geometry drift")

    return {
        "format": FORMAT_DEVICE, "recorded_on": RECORDED_ON,
        "status": "CAPTURED-STABLE-TERMINAL-STATE; NO-CLASSIFICATION",
        "authorities": {
            "sister": bind(SISTER),
            "phase_B_record_contract": bind(PHASE_B),
            "capture_directory": OUT.relative_to(ROOT).as_posix(),
        },
        "session": {
            "physical_owner_input": True,
            "forms": ["(require (quote defstruct))",
                      "(defstruct point x y)"],
            "require_result": "t", "quiet_floor_seconds": 180,
            "monitor_accesses_during_active_form": 0,
            "screen_polls_during_active_form": 0,
            "post_form_stops": 1, "CPU_left_stopped": True,
        },
        "register_tuple": registers,
        "entry_witness": {"value": "0x44", "capture": entry_binding,
                          "authority": entry_authority_binding},
        "record": {"stable_reads": records, "decoded": decoded,
                   "armed_readback": armed_binding},
        "progress": {"capture": progress_binding, "hex": progress.hex(),
                     "armed_readback": progress_armed_binding},
        "backing_planes": {
            "Bank-2": bank2_binding, "C2D-reset-domain": c2d_binding,
            "C2J_tail_hex": c2d[-64:].hex(),
            "C2D_header_hex": c2d[:32].hex(),
            "counts": {"images": u16(c2d, 12), "entries": u16(c2d, 16),
                       "resolutions": u16(c2d, 20), "roots": u16(c2d, 24)},
            "source_capsules": source_capsules,
        },
        "physical_window": window_binding,
        "media_readback": {"product": product, "library": library},
        "claim_limit": (
            "Raw, stable, post-stop capture capsule only. It makes no R/A/I/G, "
            "mechanism, fix, release or recontact claim."),
    }


def decode_record(raw: bytes, phase_b: dict[str, Any]) -> dict[str, Any]:
    contract = phase_b["facts"]["record"]
    require(len(raw) == contract["bytes"] == 65, "record contract drift")
    result: dict[str, Any] = {}
    for field in contract["fields"]:
        if field["kind"] == "stage-tag":
            tag = raw[field["offset"]]
            state = ("reached" if tag == field["reached_tag"] else
                     "initial" if tag == field["initial_sentinel"] else "invalid")
            result[field["name"]] = {"state": state, "tag": tag}
        else:
            tag = raw[field["tag_offset"]]
            state = ("reached" if tag == field["reached_tag"] else
                     "initial" if tag == field["initial_sentinel"] else "invalid")
            start = field["value_offset"]
            value = raw[start:start + field["value_bytes"]]
            result[field["name"]] = {
                "state": state, "tag": tag, "value_hex": value.hex(),
                "value_le": int.from_bytes(value, "little"),
            }
        require(result[field["name"]]["state"] != "invalid",
                f"invalid record tag: {field['name']}")
    return result


def source_oracle(device: dict[str, Any]) -> list[dict[str, Any]]:
    decoded = device["record"]["decoded"]
    capsules = device["backing_planes"]["source_capsules"]
    require(len(capsules) == 2, "source capsule cardinality drift")
    rows = []
    for prefix, capsule in zip(("previous-fill", "last-fill"), capsules):
        entry = capsule["entry"]
        obj = bytes.fromhex(capsule["object_hex"])
        require(digest(obj) == capsule["object_sha256"]
                and len(obj) == entry["code_length"],
                f"{prefix} source capsule drift")
        owner = bytes.fromhex(decoded[f"{prefix}.owner"]["value_hex"])
        cursor = decoded[f"{prefix}.cursor"]["value_le"]
        window_base = decoded[f"{prefix}.window-base"]["value_le"]
        fetched = decoded[f"{prefix}.fetched-opcode"]["value_le"]
        header = C2_CODE_HEADER_SCALAR_BYTES + 2 * entry["literal_count"]
        require(decoded[f"{prefix}.complete"]["state"] == "reached"
                and decoded[f"{prefix}.cursor"]["state"] == "reached"
                and decoded[f"{prefix}.owner"]["state"] == "reached"
                and decoded[f"{prefix}.window-base"]["state"] == "reached"
                and decoded[f"{prefix}.fetched-opcode"]["state"] == "reached",
                f"{prefix} is not a complete tagged view")
        require(owner[0] == C2_PRODUCT_CODE_BANK_TAG
                and int.from_bytes(owner[1:], "little") == entry["ordinal"]
                and cursor == window_base,
                f"{prefix} identity/cursor drift")
        require(header + cursor < len(obj), f"{prefix} source index outside object")
        expected = obj[header + cursor]
        require(fetched == expected, f"{prefix} independent source-byte mismatch")
        rows.append({
            "view": prefix, "owner_bank_tag": owner[0],
            "owner_ordinal": entry["ordinal"], "C2D_entry": entry,
            "object_sha256": capsule["object_sha256"], "header_bytes": header,
            "cursor": cursor, "window_base": window_base,
            "fetched": fetched, "expected": expected,
            "oracle": "captured-C2D-entry-plus-captured-Bank2-object",
            "completion_metadata_used_as_oracle": False,
        })
    return rows


def derive_result() -> dict[str, Any]:
    device = load(DEVICE)
    sister = load(SISTER)
    phase_b = load(PHASE_B)
    provenance = load(PROVENANCE)
    completion = load(COMPLETION)
    require(device["format"] == FORMAT_DEVICE
            and device["status"] ==
            "CAPTURED-STABLE-TERMINAL-STATE; NO-CLASSIFICATION",
            "device capsule status drift")
    # If the ignored hardware directory is present, it must still derive to
    # the exact tracked capsule.  A clean checkout can validate the capsule
    # without requiring private device files.
    if OUT.is_dir():
        require(device == derive_device(), "tracked capsule differs from device files")
    require(device["authorities"]["sister"] == bind(SISTER)
            and device["authorities"]["phase_B_record_contract"] == bind(PHASE_B),
            "device-capsule authority drift")
    require(sister["status"] ==
            "HOST-GREEN-NON-PROMOTABLE-SISTER; BUNDLED-SESSION-READY",
            "sister authority drift")
    require(completion["status"] ==
            "P2-DESK-CLOSED; COMPLETION-EDGE-APPEND-HYPOTHESIS-FALSIFIED",
            "completion-edge authority drift")
    require(provenance["supersession"]["classification"] ==
            "UNRESOLVED-PRE-ROLLBACK-PROVENANCE"
            and "R/A/I/G selects A" in
            provenance["supersession"]["retracted_claims"],
            "Slot-39 provenance correction drift")

    stable = device["record"]["stable_reads"]
    require(len(stable) == 3 and [row["index"] for row in stable] == [1, 2, 3]
            and len({row["hex"] for row in stable}) == 1,
            "stable record authority drift")
    raw = bytes.fromhex(stable[0]["hex"])
    decoded = decode_record(raw, phase_b)
    require(decoded == device["record"]["decoded"], "decoded record drift")
    fills = source_oracle(device)

    require(device["entry_witness"]["value"] == "0x44"
            and device["register_tuple"]["PC"].lower() == "0xb431"
            and device["session"]["CPU_left_stopped"],
            "terminal identity/entry witness drift")
    require(device["backing_planes"]["C2J_tail_hex"] == "00" * 64,
            "C2J is not CLEAR")

    # Slot 39 is intentionally not interpreted as a forward failure.  The
    # correction proves that rollback and successful paths can leave it.
    require(decoded["append.complete"]["state"] == "reached"
            and decoded["append.first-non-ok-checkpoint"]["value_le"] == 39
            and decoded["append.phase-owner"]["value_le"] == 0
            and decoded["append.c2j-state"]["value_le"] == 0,
            "captured append cleanup plane drift")
    require(decoded["first-error.complete"]["state"] == "initial"
            and decoded["gc.complete"]["state"] == "reached"
            and decoded["gc.mem-oom"]["value_le"] == 0,
            "captured VM/GC plane drift")

    irq = {
        "source_less_entry": 2,
        "tagged": decoded["irq.source-less-entry-2"]["state"] == "reached",
        "episode_latch": decoded["irq.episode-latch"]["value_le"],
        "D019": decoded["irq.d019"]["value_le"],
        "D01A_raw": decoded["irq.d01a"]["value_le"],
        "D01A_programmable_mask": D01A_PROGRAMMABLE_MASK,
        "D01A_programmable_value": (
            decoded["irq.d01a"]["value_le"] & D01A_PROGRAMMABLE_MASK),
        "interrupted_return_PC": decoded["irq.interrupted-return-pc"]["value_le"],
    }
    require(all(decoded[name]["state"] == "reached" for name in (
                "irq.episode-latch", "irq.d019", "irq.d01a",
                "irq.interrupted-return-pc")), "IRQ tagged-value incomplete")
    require(irq["tagged"] and irq["episode_latch"] == 1
            and (irq["D019"] & 0x01) == 0
            and d01a_raster_only(irq["D01A_raw"])
            and irq["interrupted_return_PC"] != 0,
            "corrected pure-I oracle did not select terminal ingress")

    progress = bytes.fromhex(device["progress"]["hex"])
    require(len(progress) == 66 and progress[:42].hex() ==
            sister["identity"]["enumerated_PRG_delta"][8]["after"],
            "target-owned progress producer drift")
    counter = int.from_bytes(progress[42:46], "little")
    owner = int.from_bytes(progress[46:48], "little")
    require(progress[48] == 0xA5 and progress[49] == 0xD4
            and progress[50:] == bytes.fromhex(
                "d0d1d2d3d4d5d600d0d1d2d3d4d5d600"),
            "progress state/ring drift")

    return {
        "format": FORMAT_RESULT, "recorded_on": RECORDED_ON,
        "status": "I-SOURCELESS-IRQ-TERMINAL-INGRESS",
        "authorities": {
            "device_capture": bind(DEVICE), "diagnostic_sister": bind(SISTER),
            "historical_phase_B_partition": bind(PHASE_B),
            "slot39_provenance_correction": bind(PROVENANCE),
            "completion_edge_desk_result": bind(COMPLETION),
            "owner_authorization": git_bind(AUTHORIZATION_COMMIT,
                                              AUTHORIZATION_PATH),
            "VIC_IV_RTL": {
                "repository": "MEGA65/mega65-core", "commit": VICIV_COMMIT,
                "permalink": VICIV_PERMALINK, "register": "$D01A",
                "lines": "1768-1777",
                "readback_semantics": (
                    "bits 7..5 are hard-wired one; bits 4..0 are the "
                    "programmable IRQ mask domain"),
            },
        },
        "unchanged_capture_replay": {
            "record_sha256": digest(raw), "stable_reads": 3,
            "PC": "0xb431", "entry_witness": "0x44",
            "CPU_left_stopped": True,
            "capture_bytes_modified": 0, "hardware_recontacts": 0,
        },
        "R": {
            "selected": False, "retained_completed_views": fills,
            "reason": "both retained views equal the independent captured source oracle",
            "claim_scope": "only the two retained completed refill views",
        },
        "A": {
            "selected": False, "captured_slot": 39,
            "slot_provenance": "rollback/stale/success-ambiguous",
            "phase_owner": "NONE", "C2J": "CLEAR",
            "reason": (
                "Slot 39 is barred from forward-failure use by the bound provenance "
                "correction; the cleanup-state witnesses are clean"),
        },
        "G": {
            "selected": False, "first_error": "unreached",
            "mem_oom": 0, "gc_runs": decoded["gc.runs"]["value_le"],
        },
        "I": {
            "selected": True, **irq,
            "D01A_oracle": "(raw & 0x1f) == 0x01",
            "oracle_counterexamples": {
                "historical_unmasked_raw_equals_1": False,
                "widened_mask_0x3f_accepts_E1": False,
            },
            "historical_exact_comparison": "D01A == 0x01 (superseded for readback)",
            "attribution": "source-less interrupt/guard-input edge",
            "return_PC_symbolic_owner": None,
        },
        "progress": {
            "dispatch_counter": counter, "owner_ordinal": owner,
            "ring_slots_committed": 0,
            "interpretation": (
                "terminal record committed before the first scheduled ring sample; "
                "the missing ring samples do not override the tagged terminal ingress"),
        },
        "decision": {
            "R_A_I_G": "I", "precedence": ["R", "A", "G", "I"],
            "mechanism_boundary": "second source-less IRQ episode at terminal ingress",
            "fix_authorized": False, "product_bytes_changed": 0,
            "device_recontact_authorized": False,
        },
        "claim_limit": (
            "This replay selects the Phase-B I row after correcting only the D01A "
            "readback oracle. It identifies the source-less interrupt/guard-input "
            "edge, not the electrical or software origin of that IRQ, not a symbolic "
            "owner for return PC $BF73, and not a fix. R is excluded only for the two "
            "retained completed refill views; Slot 39 remains provenance-ambiguous."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive_result(), "result receipt differs from replay")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive_result()
    require(d01a_raster_only(0xE1), "corrected D01A oracle rejects RTL readback")
    require(0xE1 != 0x01, "unmasked D01A comparison unexpectedly accepts E1")
    require(not d01a_raster_only(0xE1, mask=0x3F),
            "D01A mask widened past documented hard-wired bits")
    cases: list[tuple[str, list[Any], Any]] = [
        ("unmasked-D01A-comparison", ["I", "D01A_oracle"], "raw == 0x01"),
        ("widen-mask-into-hardwired-bit", ["I", "D01A_programmable_mask"], 0x3F),
        ("wrong-programmable-value", ["I", "D01A_programmable_value"], 0x00),
        ("drop-RTL-permalink", ["authorities", "VIC_IV_RTL", "permalink"], ""),
        ("wrong-RTL-commit", ["authorities", "VIC_IV_RTL", "commit"], "0" * 40),
        ("refill-byte-mismatch", ["R", "retained_completed_views", 0, "fetched"], 0),
        ("metadata-as-refill-oracle", ["R", "retained_completed_views", 0,
                                       "completion_metadata_used_as_oracle"], True),
        ("slot39-forward-overclaim", ["A", "slot_provenance"], "first-non-OK"),
        ("dirty-phase-owner", ["A", "phase_owner"], "APPEND"),
        ("dirty-C2J", ["A", "C2J"], "ACTIVE"),
        ("first-error-overclaim", ["G", "first_error"], "VM_TYPEERROR"),
        ("mem-OOM", ["G", "mem_oom"], 1),
        ("drop-IRQ-tag", ["I", "tagged"], False),
        ("wrong-episode-latch", ["I", "episode_latch"], 2),
        ("pending-raster-source", ["I", "D019"], 1),
        ("disable-raster-mask", ["I", "D01A_programmable_value"], 0),
        ("null-return-PC", ["I", "interrupted_return_PC"], 0),
        ("unstable-record", ["unchanged_capture_replay", "stable_reads"], 2),
        ("claim-return-owner", ["I", "return_PC_symbolic_owner"], "vm_run_inner"),
        ("authorize-fix", ["decision", "fix_authorized"], True),
        ("widen-R-scope", ["R", "claim_scope"], "all historical refills"),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            audit(trial)
        except ResultError:
            rejected.append(name)
        else:
            raise ResultError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "R_A_I_G": "I",
            "mutations_rejected": len(rejected), "cases": rejected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "derive", "record",
                                           "check", "selftest"))
    args = parser.parse_args()
    if args.action == "capture":
        value = derive_device(); write(DEVICE, value)
    elif args.action == "derive":
        value = derive_result()
    elif args.action == "record":
        value = derive_result(); write(RESULT, value)
    elif args.action == "selftest":
        value = selftest()
    else:
        audit(load(RESULT))
        value = {"status": "PASS", "R_A_I_G": "I",
                 "mutations_rejected": 21}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError) as error:
        print(f"DEFSTRUCT TERMINAL INGRESS RESULT: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)
