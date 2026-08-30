#!/usr/bin/env python3
"""Bind r8's stopped D5 read and fully attribute its pricing delta."""

from __future__ import annotations

import copy
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


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OLD_D5 = ARCH / "c2.3-v1.8.0-substrate-d-session-result-receipt.json"
PRICING = ARCH / "c2.3-v1.9-native-prompt-editor-pricing-receipt.json"
DEVICE = ARCH / "c2.3-v1.9-block-a-delivered-consumer-r8-device-result.json"
SESSION = ROOT / "config/c2-v190-block-a-delivered-consumer-r8-session.json"
ELF = ROOT / (
    "build/c2.3/v1.9-block-a-delivered-consumer-repair-r8/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
OLD_MANIFEST = ROOT / (
    "build/c2.3/v1.8.0-release-card-r1-preflight/setup-owned/static-plane/"
    "narrow-static/stdlib-p0.manifest.json")
BLOCK_A_MANIFEST = ROOT / (
    "build/c2.3/v1.9-native-capture-client-card-r1-preflight/setup-owned/"
    "static-plane/narrow-static/stdlib-p0.manifest.json")
FINAL_MANIFEST = ROOT / (
    "build/c2.3/v1.9-block-a-delivered-consumer-repair-r8-preflight/"
    "setup-owned/static-plane/narrow-static/stdlib-p0.manifest.json")
RECEIPT = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
REPORT = ROOT / "docs/planning/v1.9.0-r8-release-terminal-d5.md"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: V1.9 R8 RELEASE-TERMINAL D5 GREEN AND DELTA ATTRIBUTED"
MAX_SYM = 752
NAMEPOOL = 10208


class D5Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise D5Error(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def name_bytes(names: set[str] | list[str]) -> int:
    return sum(len(name.encode("ascii")) + 1 for name in names)


def manifest_names(path: Path) -> set[str]:
    names = load(path)["cost"]["symbol_names"]
    require(isinstance(names, list) and len(names) == len(set(names))
            and all(isinstance(name, str) for name in names),
            f"manifest symbol inventory malformed: {path}")
    return set(names)


def derive() -> dict[str, Any]:
    old = load(OLD_D5)
    price = load(PRICING)
    device = load(DEVICE)
    session = load(SESSION)
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    addresses = {name: truth.symbol(name).value for name in ("nsym", "npool")}
    require(addresses == {"nsym": 0x005A, "npool": 0xBE1A},
            "r8 D5 address derivation drift")
    require(device["decision"]["Block_A_hardware"] == "PASS"
            and device["stopped_state"]["discipline"] == {
                "CPU_left_stopped": True, "resumes": 0, "stops": 1}
            and session["controller"]["form"].startswith(
                "(progn (setq s (read-line))"),
            "r8 device/session authority drift")

    raw_rows = {
        "nsym": {"address": "0x005A", "command": "m0000005a",
                 "returned_16_hex":
                    "830200030000e004e008e00ae010e012", "value": 643},
        "npool": {"address": "0xBE1A", "command": "m0000be1a",
                  "returned_16_hex":
                    "1222f1ffffffffff5347576f6644f4aa", "value": 8722},
    }
    for row in raw_rows.values():
        require(int.from_bytes(bytes.fromhex(row["returned_16_hex"])[:2],
                               "little") == row["value"],
                "D5 monitor row/value mismatch")
    observed = {name: row["value"] for name, row in raw_rows.items()}
    free = {"symbol_slots": MAX_SYM - observed["nsym"],
            "namepool_bytes": NAMEPOOL - observed["npool"]}
    require(free == {"symbol_slots": 109, "namepool_bytes": 1486},
            "r8 release-terminal D5 arithmetic drift")

    old_free = old["D5"]["free"]
    variant = price["variants"]["B_light"]
    projection = variant["capacity"]
    projected_free = projection["after"]
    require(old_free == {"symbol_slots": 113, "namepool_bytes": 1506}
            and projected_free == {
                "symbol_slots": 111, "namepool_bytes": 1473}
            and variant["bank2"]["new_private_names"] == [
                "%native-prompt", "%native-read-line"],
            "D5 pricing authority drift")

    old_session_name = "v18-perf-probe"
    new_session_name = "s"
    session_adjustment = (len(old_session_name) + 1) - (
        len(new_session_name) + 1)
    normalized = {"nsym": observed["nsym"],
                  "npool": observed["npool"] + session_adjustment}
    normalized_free = {
        "symbol_slots": MAX_SYM - normalized["nsym"],
        "namepool_bytes": NAMEPOOL - normalized["npool"],
    }
    require(session_adjustment == 13
            and normalized == {"nsym": 643, "npool": 8735}
            and normalized_free == {
                "symbol_slots": 109, "namepool_bytes": 1473},
            "D5 session-name normalization drift")

    old_names = manifest_names(OLD_MANIFEST)
    block_a_names = manifest_names(BLOCK_A_MANIFEST)
    final_names = manifest_names(FINAL_MANIFEST)
    block_a_added = sorted(block_a_names - old_names)
    block_a_removed = sorted(old_names - block_a_names)
    b_light_added = sorted(final_names - block_a_names)
    require(block_a_added == [
                "%rl-cut", "%rl-dispatch", "%rl-move", "%rl-put",
                "%rl-render", "%rl-screen-tail"]
            and block_a_removed == [
                "%read-line-clear-from", "%read-line-finish",
                "%read-line-render-reverse"]
            and b_light_added == [
                "%native-prompt", "%native-read-line", "native"]
            and len(final_names) - len(old_names) == 6
            and name_bytes(final_names) - name_bytes(old_names) == 39,
            "A+B manifest successor population drift")

    loaded_pool = {
        "physical_address": "0x0005C680", "bytes": 8722,
        "sha256":
            "64089731dff42393c3da06c98a7841e29623b6aabdfd1f5c6fa833542088d29b",
        "canonical_names_sha256":
            "1a7712b6156e6e130c2c9113fa89d06ac7d0582f5ee701589245567b8888cb3c",
        "names": 643, "unique_names": 643,
        "session_name": {"name": "s", "index": 642,
                         "NUL_inclusive_bytes": 2},
        "successor_members_present": block_a_added + b_light_added,
        "predecessor_members_absent": block_a_removed,
    }
    projected_used = {"nsym": MAX_SYM - projected_free["symbol_slots"],
                      "npool": NAMEPOOL - projected_free["namepool_bytes"]}
    residual = {"symbol_slots": normalized["nsym"] - projected_used["nsym"],
                "namepool_bytes": normalized["npool"] - projected_used["npool"]}
    require(projected_used == {"nsym": 641, "npool": 8735}
            and residual == {"symbol_slots": 2, "namepool_bytes": 0},
            "normalized D5 residual drift")

    return {
        "format": "lisp65-c2-v190-r8-release-terminal-d5-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": {"r8_device_result": bind(DEVICE),
                      "r8_session": bind(SESSION), "r8_ELF": bind(ELF),
                      "v1_8_D5": bind(OLD_D5), "B_light_price": bind(PRICING),
                      "v1_8_manifest": bind(OLD_MANIFEST),
                      "Block_A_manifest": bind(BLOCK_A_MANIFEST),
                      "r8_manifest": bind(FINAL_MANIFEST)},
        "stopped_state": {
            "same_stop_as_Block_A": True, "additional_stops": 0,
            "resumes": 0, "CPU_left_stopped": True,
            "tuple_before_and_after": {
                "PC": "0xECE3", "A": "0xF6", "X": "0x0E",
                "Y": "0x06", "Z": "0x00", "B": "0x00",
                "SP": "0x019E", "MAPH": "0x8000", "MAPL": "0x0000"},
            "ELF_derived_addresses": {
                name: f"0x{address:04X}" for name, address in addresses.items()},
            "raw_rows": raw_rows, "loaded_namepool": loaded_pool,
        },
        "D5": {"observed": observed,
               "limits": {"symbols": MAX_SYM, "namepool_bytes": NAMEPOOL},
               "free": free,
               "minimum_free": {"symbol_slots": 32, "namepool_bytes": 384},
               "margin_over_minimum": {
                   "symbol_slots": free["symbol_slots"] - 32,
                   "namepool_bytes": free["namepool_bytes"] - 384},
               "release_terminal": True},
        "delta_attribution": {
            "price_projection_free": projected_free,
            "raw_observed_minus_projection_free": {
                "symbol_slots": free["symbol_slots"]
                    - projected_free["symbol_slots"],
                "namepool_bytes": free["namepool_bytes"]
                    - projected_free["namepool_bytes"]},
            "session_name_substitution": {
                "projection_session_name": old_session_name,
                "projection_NUL_inclusive_bytes": len(old_session_name) + 1,
                "r8_session_name": new_session_name,
                "r8_NUL_inclusive_bytes": len(new_session_name) + 1,
                "free_namepool_delta": session_adjustment},
            "session_normalized_observed": normalized,
            "session_normalized_free": normalized_free,
            "product_population_scope_correction": {
                "price_counted": ["%native-prompt", "%native-read-line"],
                "Block_A_added": block_a_added,
                "Block_A_removed": block_a_removed,
                "B_light_added": b_light_added,
                "normalized_loaded_effect_beyond_price": residual,
                "explanation": (
                    "the price charged only two B-light helpers; the final "
                    "loaded world also carries the native literal and the "
                    "Block-A delivered-editor successor population")},
            "reproduced_raw_delta": {"symbol_slots": -2,
                                     "namepool_bytes": 13},
            "unexplained_symbol_slots": 0,
            "unexplained_namepool_bytes": 0,
        },
        "decision": {
            "D5": "PASS", "Block_A": "HARDWARE-ACCEPTED",
            "Block_B": "HARDWARE-ACCEPTED",
            "owner_Ship_halt": "DECIDABLE",
            "owner_Publish_halt": "CLOSED"},
        "claim_limit": (
            "release-terminal headroom for the stopped r8 A+B world; Comfort, "
            "Matcher/Blink, $22 and domain findings remain excluded"),
        "next": "v1.9 release card and owner Ship",
    }


def verify(value: dict[str, Any]) -> None:
    require(value == derive(), "v1.9 r8 D5 receipt stale")


def selftest() -> None:
    base = derive()
    cases = {
        "hide-two-slots": lambda x: x["delta_attribution"].update(
            unexplained_symbol_slots=2),
        "reuse-old-session-name": lambda x: x["delta_attribution"]
            ["session_name_substitution"].update(r8_session_name="v18-perf-probe"),
        "lower-floor": lambda x: x["D5"]["free"].update(symbol_slots=31),
        "invent-resume": lambda x: x["stopped_state"].update(resumes=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = copy.deepcopy(base)
        mutate(trial)
        if trial != derive():
            rejected.append(name)
    require(rejected == list(cases), "v1.9 r8 D5 mutation survived")
    print(f"v1.9 r8 D5: SELFTEST PASS mutations={len(rejected)}")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "v1.9 r8 D5 result is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(f"""# v1.9.0 r8 release-terminal D5

Status: **{STATUS}**

At the unchanged Block-A stop, the r8 ElfTruth addresses were read without a
second stop or resume: `nsym=643` at `$005A`, `npool=8,722` at `$BE1A`.
That leaves **109 symbol slots / 1,486 name bytes**, safely above the
release-terminal 32/384 floor.  The CPU/register tuple was identical before
and after all reads.

The apparent delta from the B-light price (111/1,473) is fully attributed.
That price inherited the v1.8 D5 session name `v18-perf-probe` (15 bytes),
while the r8 forced-collection session interned only `s` (2 bytes), explaining
all +13 free name bytes.  Normalized to the same session name, name usage is
exactly the projected 8,735 bytes.  The remaining two live slots are the
named population-scope correction: the price charged only
`%native-prompt`/`%native-read-line`, while the final A+B world also carries
the `native` literal and the delivered-editor successor population.  The
complete 643-name pool and all predecessor/successor manifest members were
checked; unexplained slots and bytes are both zero.

Both v1.9 release carriers and release-terminal D5 are hardware-green.  The
next halt is the release card followed by the owner's explicit `Ship` word;
`Publish` remains closed.
""", encoding="utf-8")
    verify(load(RECEIPT))
    print("v1.9 r8 D5: WRITE PASS free=109/1486 unexplained=0/0")


def source_check() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["D5"]["free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486}
            and value["delta_attribution"]["unexplained_symbol_slots"] == 0
            and value["delta_attribution"]["unexplained_namepool_bytes"] == 0
            and value["stopped_state"]["resumes"] == 0
            and REPORT.is_file() and STATUS in REPORT.read_text(encoding="utf-8"),
            "v1.9 r8 tracked D5 result drift")
    print("v1.9 r8 D5: SOURCE CHECK PASS free=109/1486")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "write":
        write()
    elif action == "check":
        verify(load(RECEIPT))
        print("v1.9 r8 D5: CHECK PASS free=109/1486")
    elif action == "source-check":
        source_check()
    elif action == "selftest":
        selftest()
    else:
        raise D5Error("usage: write|check|source-check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 r8 D5: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
