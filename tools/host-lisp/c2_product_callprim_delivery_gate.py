#!/usr/bin/env python3
"""Product-profile delivery authority for host CALLPRIM qualification."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DEFAULT_ELF = ROOT / (
    "build/c2.3/v1.6-clean-product-operand-root-fix/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
TOMBSTONE_PRIM = 12


class DeliveryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeliveryError(message)


def _section_slice(truth: ElfTruth, section_name: str,
                   address: int, size: int) -> bytes:
    section = truth.section(section_name)
    require(section.address <= address
            and address + size <= section.address + section.bytes,
            f"range 0x{address:04x}+{size} escaped {section_name}")
    offset = address - section.address
    return truth.section_bytes(section_name)[offset:offset + size]


def derive_profile(elf: Path) -> dict[str, Any]:
    """Derive delivered primitive IDs from one final linked product."""
    truth = ElfTruth.read(
        elf, llvm_readobj=READOBJ, include_section_data=True)
    start = truth.symbol("__lisp65_c2_profile_rodata_callprim_start")
    end = truth.symbol("__lisp65_c2_profile_rodata_callprim_end")
    require(start.section == end.section, "CALLPRIM markers split sections")
    raw = _section_slice(
        truth, start.section, start.value, end.value - start.value)
    require(len(raw) % 2 == 0 and len(raw) > TOMBSTONE_PRIM * 2,
            "CALLPRIM table extent drift")
    targets = [int.from_bytes(raw[index:index + 2], "little")
               for index in range(0, len(raw), 2)]
    tombstone = targets[TOMBSTONE_PRIM]
    tombstones = [index for index, target in enumerate(targets)
                  if target == tombstone]
    delivered = [index for index, target in enumerate(targets)
                 if target != tombstone]
    require(TOMBSTONE_PRIM in tombstones
            and TOMBSTONE_PRIM not in delivered,
            "delivery partition lost the reference tombstone")
    return {"table_entries": len(targets),
            "table_start": f"0x{start.value:04x}",
            "tombstone_target": f"0x{tombstone:04x}",
            "tombstoned_ids": tombstones, "delivered_ids": delivered}


def _invoke_screen_write(delivered: list[int] | None) -> int:
    heap = B.Heap()
    string = heap.alloc(
        B.T_STR, heap.list_from_py([ord("x")]), B.NIL)
    ledger = C._abi_ledger("dialect-v2", None)
    vm = B.P0VM(
        heap=heap, abi_profile="dialect-v2", abi_ledger=ledger,
        delivered_callprims=delivered)
    stack = [B.mkfix(0), B.mkfix(0), string]
    return vm._callprim(TOMBSTONE_PRIM, 3, stack)


def selftest(elf: Path = DEFAULT_ELF) -> dict[str, Any]:
    profile = derive_profile(elf)
    # This is the historical false-green shape: dialect semantics alone
    # answer even though the selected product does not deliver the primitive.
    require(_invoke_screen_write(None) == B.NIL,
            "unrestricted host no longer demonstrates the fixture blind spot")
    try:
        _invoke_screen_write(profile["delivered_ids"])
    except B.VMError as error:
        require(error.status == "BadOpcode"
                and "product-profile tombstone Prim-ID 12" in str(error),
                f"wrong product-profile rejection: {error}")
        rejected = str(error)
    else:
        raise DeliveryError("product tombstone survived host qualification")
    invented = list(profile["delivered_ids"]) + [TOMBSTONE_PRIM]
    require(_invoke_screen_write(invented) == B.NIL,
            "invented-delivery mutation no longer demonstrates false green")
    for invalid in ([256], ["12"], 12):
        try:
            B.P0VM(delivered_callprims=invalid)
        except ValueError:
            pass
        else:
            raise DeliveryError(
                f"invalid delivered-callprim profile survived: {invalid!r}")
    return {"profile": profile, "rejection": rejected,
            "mutations_rejected": 4,
            "rule": ("product-bound host execution consumes the final ELF "
                     "CALLPRIM delivery set, including tombstones")}


def main() -> int:
    require(len(sys.argv) == 1,
            "usage: c2_product_callprim_delivery_gate.py")
    result = selftest()
    print("product CALLPRIM delivery gate: PASS "
          f"entries={result['profile']['table_entries']} "
          f"tombstones={len(result['profile']['tombstoned_ids'])} "
          f"mutations={result['mutations_rejected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
