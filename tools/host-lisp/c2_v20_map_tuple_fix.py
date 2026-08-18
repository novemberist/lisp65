#!/usr/bin/env python3
"""Bind the primary-semantics correction of the mapped-far MAP tuple.

This is the loud contract/source correction authorized at fbd1983e.  It keeps
the eb2451bc attribution immutable, decodes the successor tuple from primary
MEGA65 sources, and models the first service entry and descriptor store.  It
does not build a product card or touch hardware.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v20_mapped_far_dispatch_attribution as ATTR  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
SOURCE = ROOT / "src/optional/c2_mapped_far_service_v2.s"
HISTORICAL_SOURCE = ROOT / "src/c2_mapped_far_service.s"
BASE_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v2.0-mapped-far-dispatch-attribution-receipt.json")
DELIVERY = EVIDENCE / "c2.3-v2.0-far-payload-delivery-closure-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
GUIDE = ROOT / (
    "build/upstream-verification/mega65-user-guide/"
    "appendix-45gs02-registers.tex")
CORE = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-fix-receipt.json"

FORMAT = "lisp65-c2.3-v20-map-tuple-fix-v1"
STATUS = "PASS: primary-semantics MAP tuple corrected and modeled"
RECORDED_ON = "2026-08-13"
AUTHORIZATION_COMMIT = "fbd1983ebeb98ca2dd3e3c5f1a0d1c94c1c2a35c"
HISTORICAL_COMMIT = "eb2451bcf8d4fb8e6c060dc15e4bb79b3689e82a"


class FixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FixError(message)


def sha(raw: bytes) -> str:
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
            "sha256": sha(raw)}


def git_bytes(commit: str, path: Path) -> bytes:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    raw = git_bytes(commit, path)
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    return {"authority": "git-blob", "commit": full,
            "path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authorization() -> dict[str, Any]:
    authority = git_bind(AUTHORIZATION_COMMIT, PLAN)
    text = " ".join(git_bytes(AUTHORIZATION_COMMIT, PLAN).decode().split())
    lower = text.lower()
    require(
        "MAP-tuple fix authorized" in text
        and "A=$40, X=$82" in text
        and "one product card" in lower
        and "hardware semantics are validated by decoding" in lower,
        "MAP-tuple owner authorization text drift")
    return authority


def source_tuple(text: str | None = None) -> dict[str, int]:
    source = SOURCE.read_text(encoding="utf-8") if text is None else text
    match = re.search(
        r"c2_mapped_far_enter:.*?lda\s+#(0x[0-9a-f]+).*?"
        r"ldx\s+#(0x[0-9a-f]+).*?ldy\s+#(0x[0-9a-f]+).*?"
        r"ldz\s+#(0x[0-9a-f]+).*?\n\s*map\s*\n\s*eom",
        source, re.IGNORECASE | re.DOTALL)
    require(match is not None, "corrected MAP source sequence absent")
    return {name: int(value, 16) for name, value in zip(
        ("A", "X", "Y", "Z"), match.groups())}


def decode_low(a: int, x: int) -> dict[str, Any]:
    offset = ((x & 0x0F) << 16) | ((a & 0xFF) << 8)
    mask = (x >> 4) & 0x0F
    blocks = [block for block in range(4) if mask & (1 << block)]
    return {"A": f"0x{a:02X}", "X": f"0x{x:02X}",
            "physical_offset": f"0x{offset:05X}",
            "block_mask": f"0x{mask:X}", "mapped_low_half_blocks": blocks}


def map_low(address: int, decoded: dict[str, Any]) -> int:
    block = address // 0x2000
    if block in decoded["mapped_low_half_blocks"]:
        return address + int(decoded["physical_offset"], 16)
    return address


def primary_semantics() -> dict[str, Any]:
    guide = GUIDE.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    require(
        "contents of the A register and the lower-nibble of the X register form a 12-bit value" in guide
        and "upper nibble of the X register is used as flags" in guide
        and "reg_offset_low <= reg_x(3 downto 0) & reg_a;" in core
        and "reg_map_low <= std_logic_vector(reg_x(7 downto 4));" in core,
        "primary MAP decode witnesses absent")
    return {"guide": bind(GUIDE), "core_RTL": bind(CORE),
            "decoded_rule": (
                "offset20=(X[3:0]<<16)|(A<<8); "
                "low block mask=X[7:4]")}


def modeled_entry() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(".lisp65_c2_mapped_far_service")
    raw = truth.section_bytes(section.name)
    decoded = decode_low(0x40, 0x82)
    service_entry = truth.symbol("c2_mapped_far_vm_code_load_converged").value
    descriptor_setup = section.address + 0x32
    first_store = raw[0x32:0x37]
    require(
        (section.address, section.bytes) == (0x78B2, 874)
        and service_entry == 0x79DC
        and first_store == bytes.fromhex("a9048d00c0")
        and map_low(service_entry, decoded) == 0x2B9DC
        and map_low(descriptor_setup, decoded) == 0x2B8E4
        and map_low(0x3185, decoded) == 0x3185,
        "corrected service-entry model drift")
    return {
        "logical_service_entry": "0x79DC",
        "physical_service_entry": "0x02B9DC",
        "installed_service_range": ["0x02B8B2", "0x02BC1C"],
        "block1_probe": {"logical": "0x3185", "physical": "0x03185",
                         "unchanged": True},
        "first_descriptor_store": {
            "logical_PC": "0x78E4", "physical_PC": "0x02B8E4",
            "bytes": first_store.hex(), "effect": "STA $C000 <= $04",
            "executes_under_corrected_map": True,
        },
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    base = load(BASE_CONTRACT)
    attribution = load(ATTRIBUTION)
    delivery = load(DELIVERY)
    source = source_tuple()
    decoded = decode_low(source["A"], source["X"])
    require(
        contract["format"] == "lisp65-c2-mapped-far-map-contract-v2"
        and contract["accepted_by"] == AUTHORIZATION_COMMIT
        and contract["tuple"] == {
            "maplo_a": "0x40", "maplo_x": "0x82",
            "maphi_y": "0x00", "maphi_z": "0x80",
            "restore_a": "0x00", "restore_x": "0x00",
            "restore_y": "0x00", "restore_z": "0x80"}
        and contract["correction"]["predecessor_contract"]["sha256"]
            == sha(BASE_CONTRACT.read_bytes())
        and base["mapped_far_service"]["map_tuple"]["maplo_a"] == "0x80"
        and base["mapped_far_service"]["map_tuple"]["maplo_x"] == "0x24",
        "loud successor contract or predecessor binding drift")
    require(source == {"A": 0x40, "X": 0x82, "Y": 0, "Z": 0x80}
            and decoded["physical_offset"] == "0x24000"
            and decoded["mapped_low_half_blocks"] == [3],
            "live trampoline does not implement corrected tuple")
    require(
        attribution["mechanism"] == "MAPPED-FAR-LOW-HALF-MAP-TUPLE-TRANSPOSED"
        and attribution["mapping_decode"]["correct_low_tuple"]
            == {"A": "0x40", "X": "0x82"}
        and delivery["materialization"]["gate"]["identity_mismatches"] == 0,
        "attribution or installed-payload authority drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "contract_correction": {
            "loud_and_dated": True, "source_bound": True,
            "predecessor_tuple": {"A": "0x80", "X": "0x24"},
            "successor_tuple": {"A": "0x40", "X": "0x82"},
            "historical_source_immutable": git_bind(
                HISTORICAL_COMMIT, HISTORICAL_SOURCE),
        },
        "primary_MAP_semantics": primary_semantics(),
        "source_tuple": {key: f"0x{number:02X}" for key, number in source.items()},
        "decoded_mapping": decoded,
        "host_model": modeled_entry(),
        "authorization": {"fix": True, "one_product_card": True,
                          "media_regeneration": True, "D1_repeat": True,
                          "D2_D5_open": False},
        "authorities": {
            "owner_authorization": authorization(),
            "historical_attribution": bind(ATTRIBUTION),
            "historical_contract": bind(BASE_CONTRACT),
            "successor_contract": bind(CONTRACT), "trampoline_source": bind(SOURCE),
            "installed_payload_delivery": bind(DELIVERY),
            "candidate_ELF_for_body_truth": bind(ELF), "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Host/source correction and first-entry model only. The authorized "
            "product card, media regeneration and D1 have not yet run; D2-D5 "
            "remain closed."),
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "fix receipt identity drift")
    correction = value["contract_correction"]
    decoded = value["decoded_mapping"]
    model = value["host_model"]
    require(
        correction["loud_and_dated"] is True
        and correction["source_bound"] is True
        and correction["predecessor_tuple"] == {"A": "0x80", "X": "0x24"}
        and correction["successor_tuple"] == {"A": "0x40", "X": "0x82"}
        and decoded == decode_low(0x40, 0x82)
        and model["physical_service_entry"] == "0x02B9DC"
        and model["block1_probe"]["unchanged"] is True
        and model["first_descriptor_store"]["bytes"] == "a9048d00c0"
        and model["first_descriptor_store"]["executes_under_corrected_map"] is True,
        "contract/source decode or entry model drift")
    require(value["primary_MAP_semantics"] == primary_semantics(),
            "primary MAP authority or decoded rule drift")
    require(
        value["authorities"]["successor_contract"] == bind(CONTRACT)
        and value["authorities"]["trampoline_source"] == bind(SOURCE)
        and value["authorities"]["historical_attribution"] == bind(ATTRIBUTION),
        "source/contract/attribution binding drift")
    require(value["authorization"] == {
        "fix": True, "one_product_card": True, "media_regeneration": True,
        "D1_repeat": True, "D2_D5_open": False},
        "authorized boundary drift")
    require("have not yet run" in value["claim_limit"], "claim boundary widened")


def mutations(value: dict[str, Any]) -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "restore-old-A": lambda x: x["contract_correction"]["successor_tuple"].update(A="0x80"),
        "restore-old-X": lambda x: x["contract_correction"]["successor_tuple"].update(X="0x24"),
        "decode-old-offset": lambda x: x["decoded_mapping"].update(physical_offset="0x48000"),
        "decode-old-block": lambda x: x["decoded_mapping"].update(mapped_low_half_blocks=[1]),
        "miss-service-entry": lambda x: x["host_model"].update(physical_service_entry="0x079DC"),
        "map-block1": lambda x: x["host_model"]["block1_probe"].update(unchanged=False),
        "skip-first-descriptor-store": lambda x: x["host_model"]["first_descriptor_store"].update(executes_under_corrected_map=False),
        "alter-first-store": lambda x: x["host_model"]["first_descriptor_store"].update(bytes="0000000000"),
        "silent-correction": lambda x: x["contract_correction"].update(loud_and_dated=False),
        "unbound-source": lambda x: x["contract_correction"].update(source_bound=False),
        "erase-guide": lambda x: x["primary_MAP_semantics"]["guide"].update(sha256="0" * 64),
        "erase-RTL": lambda x: x["primary_MAP_semantics"]["core_RTL"].update(sha256="0" * 64),
        "consume-card-early": lambda x: x["claim_limit"].replace("not yet", "already"),
        "open-D2-D5": lambda x: x["authorization"].update(D2_D5_open=True),
    }


def expected() -> dict[str, Any]:
    value = derive()
    rejected: dict[str, str] = {}
    for name, mutate in mutations(value).items():
        candidate = deepcopy(value)
        result = mutate(candidate)
        if isinstance(result, str):
            candidate["claim_limit"] = result
        try:
            validate(candidate)
        except (FixError, KeyError, TypeError) as error:
            rejected[name] = str(error)
        else:
            raise FixError(f"MAP-tuple fix mutation survived: {name}")
    value["mutations_rejected"] = rejected
    return value


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_map_tuple_fix.py record|check|selftest")
    value = expected()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "MAP-tuple fix receipt stale")
    print("v2.0 MAP-tuple fix: PASS A=40 X=82 offset=24000 block=3 "
          f"mutations={len(value['mutations_rejected'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FixError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as error:
        print(f"v2.0 MAP-tuple fix: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
