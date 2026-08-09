#!/usr/bin/env python3
"""Build and bind the owner-authorized pre-installer micro-ladder sibling."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_mem_init_before_after as BASE  # noqa: E402


OWNER_COMMIT = "20b4b990"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-preinstaller-stretch-desk-attribution-receipt.json")
OUT = ROOT / "build/c2.3/v1.6-defstruct-preinstaller-micro-ladder"
ART = OUT / "artifacts"
ELF = ART / "diagnostic-preinstaller-micro-ladder.elf"
PRG = ART / "diagnostic-preinstaller-micro-ladder.prg"
DEPLOY = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-preinstaller-micro-ladder-preparation-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
DRIVER = Path(__file__).resolve()
CONTACT_DRIVER = ROOT / "tools/host-lisp/c2_v16_preinstaller_micro_ladder_contact.py"
RUNNER = ROOT / "scripts/c2-v16-defstruct-preinstaller-micro-ladder-hw.sh"

PRG_LOAD = 0x2001
STATE = 0xB58C
STATE_BYTES = bytes.fromhex("d0d1d2d3d4d5")
CHROUT_WRAPPER = 0xB592
OWNERSHIP_WRAPPER = 0xB59E
INSTALLER_WRAPPER = 0xB5AF
INTERVAL_END = 0xB5C3
CHROUT_CALL = 0x2044
OWNERSHIP_CALL = 0xA4E0
INSTALLER_CALL = 0xA4E6


class LadderError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LadderError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = path.resolve().as_posix()
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], label: str) -> bytes:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"{label} failed:\n{result.stdout.decode(errors='replace')}")
    return result.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"],
               "resolve owner authorization").decode().strip()
    return full, run(["git", "show", f"{full}:{path}"], "read authorization")


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_slice(raw: bytes, address: int, count: int) -> bytes:
    require(int.from_bytes(raw[:2], "little") == PRG_LOAD, "PRG load drift")
    at = 2 + address - PRG_LOAD
    require(2 <= at and at + count <= len(raw), "PRG range absent")
    return raw[at:at + count]


def prg_patch(raw: bytearray, address: int, before: bytes, after: bytes) -> None:
    require(len(before) == len(after), "fixed-size patch required")
    at = 2 + address - PRG_LOAD
    require(raw[at:at + len(before)] == before,
            f"PRG authority drift at ${address:04X}")
    raw[at:at + len(after)] = after


def wrappers() -> tuple[bytes, bytes, bytes, bytes]:
    # CHROUT entry stores incoming A ($0E on the bound route), then commits E1
    # only after return.  The ownership tag commits only after raw A is stored.
    chrout = (b"\x8d" + u16(STATE) + b"\x20\xd2\xff\xa9\xe1\x8d"
              + u16(STATE + 1) + b"\x60")
    ownership = (b"\xa9\xe2\x8d" + u16(STATE + 2) + b"\x20\xa3\xb4\x8d"
                 + u16(STATE + 4) + b"\xa2\xe3\x8e" + u16(STATE + 3)
                 + b"\x60")
    installer = b"\xa9\xe4\x8d" + u16(STATE + 5) + b"\x4c\x14\xa7"
    payload = STATE_BYTES + chrout + ownership + installer
    require((len(chrout), len(ownership), len(installer), len(payload)) ==
            (12, 17, 8, 43), "micro-ladder geometry drift")
    return chrout, ownership, installer, payload


def patch_section_address(path: Path, name: str, address: int) -> None:
    data = bytearray(path.read_bytes())
    require(data[:6] == b"\x7fELF\x01\x01", "ELF32 little-endian required")
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    string_header = shoff + shstrndx * shentsize
    string_offset, string_size = struct.unpack_from("<II", data,
                                                     string_header + 16)
    strings = data[string_offset:string_offset + string_size]
    found = False
    for index in range(shnum):
        header = shoff + index * shentsize
        name_offset = struct.unpack_from("<I", data, header)[0]
        end = strings.find(0, name_offset)
        if bytes(strings[name_offset:end]).decode("ascii") == name:
            struct.pack_into("<I", data, header + 12, address)
            found = True
    require(found, f"ELF section absent: {name}")
    path.chmod(path.stat().st_mode | 0o200)
    path.write_bytes(data)


def derive() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    ART.mkdir(parents=True)
    base_prg = BASE.DIAG_PRG.read_bytes()
    result = bytearray(base_prg)
    _chrout, _ownership, _installer, payload = wrappers()
    require(prg_slice(base_prg, STATE, INTERVAL_END - STATE) ==
            bytes(INTERVAL_END - STATE), "owner-free interval drift")
    prg_patch(result, STATE, bytes(len(payload)), payload)
    prg_patch(result, CHROUT_CALL, b"\x20\xd2\xff",
              b"\x20" + u16(CHROUT_WRAPPER))
    prg_patch(result, OWNERSHIP_CALL, b"\x20\xa3\xb4",
              b"\x20" + u16(OWNERSHIP_WRAPPER))
    prg_patch(result, INSTALLER_CALL, b"\x20\x14\xa7",
              b"\x20" + u16(INSTALLER_WRAPPER))
    PRG.write_bytes(bytes(result))

    truth = ElfTruth.read(BASE.DIAG_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = bytearray(truth.section_bytes(".text"))
    text_start = truth.section(".text").address
    for address, before, after in (
        (CHROUT_CALL, b"\x20\xd2\xff", b"\x20" + u16(CHROUT_WRAPPER)),
        (OWNERSHIP_CALL, b"\x20\xa3\xb4", b"\x20" + u16(OWNERSHIP_WRAPPER)),
        (INSTALLER_CALL, b"\x20\x14\xa7", b"\x20" + u16(INSTALLER_WRAPPER)),
    ):
        at = address - text_start
        require(text[at:at + 3] == before, f"ELF text drift at ${address:04X}")
        text[at:at + 3] = after
    text_file, ladder_file = ART / "section-text.bin", ART / "section-ladder.bin"
    text_file.write_bytes(bytes(text)); ladder_file.write_bytes(payload)
    run([str(OBJCOPY), f"--update-section=.text={text_file}",
         f"--add-section=.lisp65_v16_preinstaller_ladder={ladder_file}",
         "--set-section-flags=.lisp65_v16_preinstaller_ladder=alloc,load,code",
         f"--add-symbol=lisp65_v16_preinstaller_ladder_state=0x{STATE:x},global,object",
         f"--add-symbol=lisp65_v16_preinstaller_chrout_wrapper=0x{CHROUT_WRAPPER:x},global,function",
         f"--add-symbol=lisp65_v16_preinstaller_ownership_wrapper=0x{OWNERSHIP_WRAPPER:x},global,function",
         f"--add-symbol=lisp65_v16_preinstaller_installer_wrapper=0x{INSTALLER_WRAPPER:x},global,function",
         str(BASE.DIAG_ELF), str(ELF)], "derive micro-ladder ELF")
    patch_section_address(ELF, ".lisp65_v16_preinstaller_ladder", STATE)

    deployment = deepcopy(load(BASE.DEPLOY))
    deployment["format"] = "lisp65-c2.3-v1.6-preinstaller-micro-ladder-deployment-v1"
    deployment["status"] = "HOST-GREEN-NON-PROMOTABLE-PREINSTALLER-LADDER"
    deployment["diagnostic"]["prg"] = bind(PRG)
    deployment["diagnostic"]["elf"] = bind(ELF)
    deployment["preinstaller_micro_ladder"] = {
        "state": [f"0x{STATE:04x}", len(STATE_BYTES)],
        "owner_free_interval": [f"0x{STATE:04x}", f"0x{INTERVAL_END:04x}"],
        "wrapper_ranges": [["0xb592", "0xb59e"], ["0xb59e", "0xb5af"],
                           ["0xb5af", "0xb5b7"]],
        "reset_hex": STATE_BYTES.hex(), "layout_shift": 0,
        "product_bytes": 0, "promotable": False,
    }
    DEPLOY.write_text(json.dumps(deployment, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    owner, plan = git_blob(OWNER_COMMIT, PLAN)
    require(b"Micro-ladder contact authorized" in plan
            and b"49 diagnostic bytes" in plan
            and b"eight disjoint" in plan and b"outcomes." in plan,
            "owner authority drift")
    attribution = load(ATTRIBUTION)
    require(attribution["facts"]["micro_ladder"]["total_bytes_actually_different"]
            == 49 and not attribution["facts"]["disposition"]
            ["new_contact_authorized"], "desk attribution drift")
    for path in (ELF, PRG, DEPLOY):
        require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    base, sibling = BASE.DIAG_PRG.read_bytes(), PRG.read_bytes()
    require(len(base) == len(sibling), "PRG extent drift")
    changed = [index for index, pair in enumerate(zip(base, sibling, strict=True))
               if pair[0] != pair[1]]
    addresses = [PRG_LOAD + index - 2 for index in changed]
    callsite_changes = [address for address in addresses if address in {
        CHROUT_CALL + 1, CHROUT_CALL + 2, OWNERSHIP_CALL + 1,
        OWNERSHIP_CALL + 2, INSTALLER_CALL + 1, INSTALLER_CALL + 2}]
    gap_changes = [address for address in addresses if STATE <= address < INTERVAL_END]
    require(len(changed) == 49 and len(callsite_changes) == 6
            and len(gap_changes) == 43 and set(addresses) ==
            set(callsite_changes + gap_changes), "49-byte identity delta drift")
    _chrout, _ownership, _installer, payload = wrappers()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(truth.section(".lisp65_v16_preinstaller_ladder").address == STATE
            and truth.section_bytes(".lisp65_v16_preinstaller_ladder") == payload,
            "ELF ladder placement drift")
    require(prg_slice(sibling, STATE, len(payload)) == payload
            and prg_slice(sibling, CHROUT_CALL, 3) == b"\x20" + u16(CHROUT_WRAPPER)
            and prg_slice(sibling, OWNERSHIP_CALL, 3) ==
                b"\x20" + u16(OWNERSHIP_WRAPPER)
            and prg_slice(sibling, INSTALLER_CALL, 3) ==
                b"\x20" + u16(INSTALLER_WRAPPER), "PRG route drift")
    deploy = load(DEPLOY)
    require(deploy["diagnostic"]["prg"] == bind(PRG)
            and deploy["diagnostic"]["elf"] == bind(ELF)
            and deploy["preinstaller_micro_ladder"]["promotable"] is False,
            "deployment drift")
    facts = {
        "identity": {"base_bytes": len(base), "sibling_bytes": len(sibling),
                     "actual_differing_bytes": 49, "gap_bytes": 43,
                     "callsite_operand_bytes": 6, "layout_shift": 0,
                     "product_bytes": 0, "promotable": False},
        "placement": {"state": ["0xb58c", "0xb592"],
                      "chrout_wrapper": ["0xb592", "0xb59e"],
                      "ownership_wrapper": ["0xb59e", "0xb5af"],
                      "installer_wrapper": ["0xb5af", "0xb5b7"],
                      "owner_free_bytes_left": 12,
                      "durable_boot_witness": "0xb5c3"},
        "semantics": {
            "CHROUT": "incoming A commits entry; E1 commits only after RTS",
            "ownership": "E2 entry; raw return A stored before E3 commit tag",
            "installer": "E4 entry then tail-JMP A714",
            "hidden_callee": "all wrappers share the caller's proved visibility"},
        "decision_table": attribution["facts"]["micro_ladder"]["decision_table"],
        "appointment": {"owner_authority": f"git:{owner}", "contacts": 1,
                        "complete_reset_domain": True,
                        "C2J_CLEAR_before_RUN": True, "physical_RUN": True,
                        "quiet_floor_seconds": 27.653, "stops": 1,
                        "CPU_left_stopped": True},
    }
    authorities = {"owner_authorization": bind_blob(f"git:{owner}:{PLAN}", plan),
                   "desk_attribution": bind(ATTRIBUTION),
                   "base_preparation": bind(BASE.RECEIPT),
                   "base_ELF": bind(BASE.DIAG_ELF), "base_PRG": bind(BASE.DIAG_PRG),
                   "diagnostic_ELF": bind(ELF), "diagnostic_PRG": bind(PRG),
                   "deployment": bind(DEPLOY), "driver": bind(DRIVER),
                   "contact_driver": bind(CONTACT_DRIVER), "runner": bind(RUNNER)}
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    identity, placement = facts["identity"], facts["placement"]
    require(identity == {"base_bytes": 41566, "sibling_bytes": 41566,
                         "actual_differing_bytes": 49, "gap_bytes": 43,
                         "callsite_operand_bytes": 6, "layout_shift": 0,
                         "product_bytes": 0, "promotable": False},
            "identity delta drift")
    require(placement["state"] == ["0xb58c", "0xb592"]
            and placement["owner_free_bytes_left"] == 12
            and placement["durable_boot_witness"] == "0xb5c3",
            "placement drift")
    require(facts["semantics"] == {
        "CHROUT": "incoming A commits entry; E1 commits only after RTS",
        "ownership": "E2 entry; raw return A stored before E3 commit tag",
        "installer": "E4 entry then tail-JMP A714",
        "hidden_callee": "all wrappers share the caller's proved visibility"},
        "wrapper semantic drift")
    require(facts["decision_table"] == {
                "enter-absent": "LOCAL-CRT-INIT-BOUNDARY",
                "enter-set,return-absent": "CHROUT-NONRETURN-OR-MAP-NOT-RESTORED",
                "return-set,ownership-enter-absent": "MAIN-PREFIX-BOUNDARY",
                "ownership-enter-set,return-tag-absent": "OWNERSHIP-IN-FLIGHT-BOUNDARY",
                "ownership-return-raw=0": "OWNERSHIP-FAIL-CLOSED-EXIT",
                "ownership-return-raw!=0,installer-enter-absent": "POST-OWNERSHIP-PRE-INSTALLER",
                "installer-enter-set,ov_started=0": "INSTALLER-PROLOGUE-BEFORE-ARM",
                "ov_started=1": "HAND-OFF-TO-EXISTING-STATUS-TABLE",
            } and facts["appointment"] == {
                "owner_authority": "git:20b4b990666e74a9bb2ebe5251c1617a4ea094d1",
                "contacts": 1, "complete_reset_domain": True,
                "C2J_CLEAR_before_RUN": True, "physical_RUN": True,
                "quiet_floor_seconds": 27.653, "stops": 1,
                "CPU_left_stopped": True}, "appointment/closure drift")


def selftest() -> dict[str, Any]:
    facts, _ = exact_facts(); audit(facts)
    mutations = [
        (["identity", "actual_differing_bytes"], 48),
        (["identity", "gap_bytes"], 42),
        (["identity", "callsite_operand_bytes"], 7),
        (["identity", "layout_shift"], 1),
        (["identity", "product_bytes"], 49),
        (["identity", "promotable"], True),
        (["placement", "state", 0], "0xb58b"),
        (["placement", "owner_free_bytes_left"], 11),
        (["placement", "durable_boot_witness"], "0xb5c2"),
        (["semantics", "CHROUT"], "return assumed"),
        (["semantics", "ownership"], "tag before raw return"),
        (["semantics", "hidden_callee"], "mapping assumed"),
        (["decision_table", "enter-absent"], "PRODUCT-FAULT"),
        (["appointment", "contacts"], 2),
        (["appointment", "complete_reset_domain"], False),
        (["appointment", "C2J_CLEAR_before_RUN"], False),
        (["appointment", "physical_RUN"], False),
        (["appointment", "stops"], 2),
        (["appointment", "CPU_left_stopped"], False),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(facts); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except LadderError as error: rejected[f"mutation-{index:02d}"] = str(error)
        else: raise LadderError(f"micro-ladder mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts(); audit(facts)
    return {"format": "lisp65-c2.3-v1.6-preinstaller-micro-ladder-preparation-v1",
            "recorded_on": "2026-08-06", "status": "HOST-GREEN; CONTACT READY",
            "authorities": authorities, "facts": facts,
            "mutations_rejected": selftest()["rejected"],
            "claim_limit": "Non-promotable diagnostic preparation only. One owner-authorized contact; no product bytes, mem_init answer, R/A/I/G row, fix, Link or release."}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "dump", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "build":
        derive(); value = {"status": "BUILD PASS", "artifacts": 3}
    elif args.action == "dump":
        sys.stdout.buffer.write(canonical(expected())); return 0
    elif args.action == "selftest": value = selftest()
    else:
        require(RECEIPT.read_bytes() == canonical(expected()),
                "micro-ladder preparation receipt drift")
        value = {"status": "PASS", "mutations": len(selftest()["rejected"]),
                 "actual_differing_bytes": 49}
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (LadderError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"PREINSTALLER MICRO-LADDER FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
