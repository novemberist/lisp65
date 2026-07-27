#!/usr/bin/env python3
"""Pure full replay of the repaired Link-60 Boot inventory.

This script consumes the SHA-bound repaired PRG/ELF and families read-only.
It may create reports and independently repacked comparison families, but it
rejects every compiler/linker invocation and never patches product bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_two_region_e000_s1_artifact_completion as CONFIG  # noqa: E402
import c2_link60_boot_inventory_artifact_repair as REPAIR  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


SOURCE = REPAIR.OUT
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
PROFILE = SOURCE / "resolved-profile.txt"
SOURCE_RECEIPT = REPAIR.RECEIPT
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-60-boot-inventory-pure-replay4")
RECEIPT = REPAIR.EVIDENCE / (
    "c2.2-product-link60-boot-inventory-pure-replay-receipt.json")
EXPECTED_PRODUCT_SHA = (
    "5a4e2221c1e03cad4ec5fa1dd3529cdd2e3f593c84e9ee4e7e8cd53eaf750227")
LINK_NUMBER = 60
EXPECTED_SOURCE_STATUS = (
    "passed-link60-canonical-boot-inventory-artifact-repair-"
    "awaiting-pure-replay")
EXPECTED_SOURCE_DIAGNOSTIC: dict[str, str] | None = None
REQUIRE_SOURCE_PRODUCT_BINDING = True
FAILED_PREDECESSOR_PRODUCT: Path | None = None
FAILED_PREDECESSOR_RECEIPT: Path | None = None


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    require(
        not OUT.exists() and not RECEIPT.exists(),
        "Link-60 Boot-inventory replay is one-shot",
    )
    require(
        PRODUCT.is_file() and ELF.is_file() and PROFILE.is_file()
        and SOURCE_RECEIPT.is_file()
        and sha(PRODUCT) == EXPECTED_PRODUCT_SHA,
        "repaired Link-60 replay authority drift",
    )
    source_receipt = json.loads(
        SOURCE_RECEIPT.read_text(encoding="utf-8"))
    require(
        source_receipt["status"] == EXPECTED_SOURCE_STATUS
        and (
            not REQUIRE_SOURCE_PRODUCT_BINDING
            or source_receipt["product_identity"]["product"]["sha256"]
                == EXPECTED_PRODUCT_SHA
        )
        and (
            EXPECTED_SOURCE_DIAGNOSTIC is None
            or source_receipt.get("diagnostic")
                == EXPECTED_SOURCE_DIAGNOSTIC
        ),
        "artifact repair receipt is not the replay authority",
    )
    before = snapshot(SOURCE)
    require(
        before and all((int(row["mode"], 8) & 0o222) == 0
                       for row in before.values()),
        "repaired Link-60 artifact tree is not immutable",
    )
    OUT.mkdir(parents=True)
    shutil.copy2(
        SOURCE / "c2-product-kernal-window.bin",
        OUT / "c2-product-kernal-window.bin")
    CONFIG.configure()

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(
            command[0] if isinstance(command, (list, tuple))
            else command)).name
        lowered = executable.lower()
        require(
            "clang" not in lowered
            and lowered not in {
                "cc", "gcc", "ld", "ld.lld", "lld", "mos-mega65-clang"},
            f"pure replay attempted compiler/linker: {executable}",
        )
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = guarded_run
        crc_codegen = P.CRC_CODEGEN.audit_elf(
            ELF, out=OUT / "c2-crc-codegen-gate.json")
        crc_leaf = P.CRC_ASM_LEAF.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-gate.json")
        leaf_abi = P.ASM_LEAF_ABI.audit_elf(
            ELF, out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
            require_bank3_chain=P.FAMILY_STAGE_BINDINGS)
        f011 = P.F011_WINDOW.audit(P.F011_WINDOW.disassemble(
            P.TOOLCHAIN / "llvm-objdump", ELF))
        P.write(
            OUT / "c2-f011-mount-window-gate.json",
            json.dumps(f011, indent=2, sort_keys=True) + "\n")
        handoff = P.handoff_z_abi_gate(OUT, PRODUCT, "boot-inventory-replay")
        pre = P.pre_ownership_gate(
            OUT, PRODUCT, "boot-inventory-replay")
        data = P.profile_data_reference_gate(
            OUT, PRODUCT, "boot-inventory-replay", pre)
        facade = P.fixed_facade_gate(
            OUT, PRODUCT, "boot-inventory-replay")
        fixed = P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-replay.json")

        replay_boot = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE, "boot", "replay")
        replay_session = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE, "session", "replay")
        source_boot = (
            SOURCE / "runtime-overlays-boot-final.bin",
            SOURCE / "runtime-overlays-boot-final.json")
        source_session = (
            SOURCE / "runtime-overlays-session-final.bin",
            SOURCE / "runtime-overlays-session-final.json")
        identity = P.runtime_family_identity_gate(
            OUT, source_boot, source_session, replay_boot, replay_session)
        P.write(
            OUT / "runtime-overlays-final.bin",
            replay_session[0].read_bytes())
        P.write(
            OUT / "runtime-overlays-final-region1.bin",
            (OUT / "runtime-overlays-session-replay-region1.bin").read_bytes())
        for family, packed in (
                ("boot", replay_boot), ("session", replay_session)):
            P.write(
                OUT / f"runtime-overlays-{family}-final.bin",
                packed[0].read_bytes())
            P.write(
                OUT / f"runtime-overlays-{family}-final.json",
                packed[1].read_bytes())
        P.write(
            OUT / "runtime-overlays-session-final-region1.bin",
            (OUT / "runtime-overlays-session-replay-region1.bin").read_bytes())

        expected_binding = P.verifier_binding_bytes(
            source_boot[1], source_session[1])
        if P.FAMILY_STAGE_BINDINGS:
            expected_binding += P.family_stage_binding_bytes(
                source_boot[1], source_session[1])
        section = P.section_table(ELF)[P.VERIFIER_BINDING_SECTION]
        product_data = PRODUCT.read_bytes()
        file_offset = P._prg_file_offset(
            product_data, section["address"], len(expected_binding))
        require(
            product_data[file_offset:file_offset + len(expected_binding)]
                == expected_binding
            and (SOURCE / "runtime-overlay-verifier-bindings.bin").read_bytes()
                == expected_binding,
            "repaired publish-last Boot/Session tuple is not canonical",
        )
        overlay_binding = json.loads(
            (SOURCE / "runtime-verifier-publish-last.json").read_text(
                encoding="utf-8"))
        window_binding = json.loads(
            (SOURCE / "kernal-window-publish-last.json").read_text(
                encoding="utf-8"))
        shutil.copy2(
            SOURCE / "lisp65-c2-substitution-unbound.prg",
            OUT / "lisp65-c2-substitution-unbound.prg")
        shutil.copy2(
            SOURCE / "runtime-overlay-verifier-bindings.bin",
            OUT / "runtime-overlay-verifier-bindings.bin")
        publish = P.total_publish_last_gate(
            OUT, PRODUCT, window_binding, overlay_binding,
            expected_verifier_base=0xB972)

        P.closure_gate(OUT, PRODUCT)
        kernal = P.kernal_freedom_gate(OUT, PRODUCT)
        balance = P.substitution_balance(OUT, PRODUCT, kernal)
        static_island = ISLAND.static_elf_gate(ELF)
    finally:
        subprocess.run = original_run

    require(
        before == snapshot(SOURCE),
        "pure replay modified the repaired Link-60 authority",
    )
    # Spell the wall arithmetic directly so the replay has no hidden path
    # dependency on the completion driver's mutable module globals.
    sections = P.section_table(ELF)
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE
            - (sections[".text"]["address"] + sections[".text"]["bytes"]),
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE
            - (sections[".bss"]["address"] + sections[".bss"]["bytes"]),
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes":
            2048 - sections[".lisp65_resident_island"]["bytes"],
        "e000_headroom_bytes":
            P.KERNAL_WINDOW_BYTES
            - sum(sections.get(name, {}).get("bytes", 0)
                  for name in P.KERNAL_SECTIONS),
    }
    session = json.loads(source_session[1].read_text(encoding="utf-8"))
    boot_gate = json.loads(
        (OUT / "boot-inventory-one-truth-replay.json").read_text(
            encoding="utf-8"))
    require(
        walls == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and int(session["storage"]["size"]) == 64926
        and int(session["overflow_storage"]["used"]) == 1956
        and identity["status"] == "passed"
        and publish["status"] == "passed"
        and publish["declared_domain_bytes"] == 42
        and boot_gate["status"]
            == "passed-profile-record-and-linked-slot-one-truth"
        and kernal["status"] == "passed"
        and balance["status"] == "passed"
        and static_island["E000_S1"]["status"].startswith("passed"),
        "pure full replay has a structural red",
    )

    value = {
        "format":
            f"lisp65-c2-link{LINK_NUMBER}-boot-inventory-pure-replay-v1",
        "recorded_on": "2026-07-24",
        "status":
            f"passed-link{LINK_NUMBER}-pure-full-replay-all-gates-green",
        "promotable": False,
        "authority": {
            "artifact_repair_receipt": bind(SOURCE_RECEIPT),
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "boot_family": bind(source_boot[0]),
            "session_family": bind(source_session[0]),
            "session_region1": bind(
                SOURCE / "runtime-overlays-session-final-region1.bin"),
            "driver": bind(Path(__file__)),
            **({
                "failed_predecessor_product": bind(
                    FAILED_PREDECESSOR_PRODUCT),
                "failed_predecessor_receipt": bind(
                    FAILED_PREDECESSOR_RECEIPT),
            } if FAILED_PREDECESSOR_PRODUCT is not None
                and FAILED_PREDECESSOR_RECEIPT is not None else {}),
        },
        "boot_inventory": boot_gate,
        "runtime_family_identity": identity,
        "publish_last": {
            "binding_address": "0xb972",
            "binding_bytes": len(expected_binding),
            "total_domain": publish,
        },
        "walls": walls,
        "gates": {
            "crc_codegen": crc_codegen["status"],
            "crc_leaf": crc_leaf["status"],
            "assembler_leaf_ABI": leaf_abi["status"],
            "F011_window": f011["status"],
            "handoff_Z": handoff["status"],
            "pre_ownership": pre["status"],
            "profile_data_reference": data["status"],
            "fixed_facade": facade["status"],
            "fixed_block": fixed["status"],
            "family_identity": identity["status"],
            "boot_inventory_one_truth": boot_gate["status"],
            "publish_last": publish["status"],
            "KERNAL_freedom": kernal["status"],
            "substitution_balance": balance["status"],
            "preinstall_E000_S1": static_island["E000_S1"]["status"],
            "all_green": True,
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0,
            "automatic_retries": 0,
            "read_only_tool_invocations": commands,
        },
        "rollback": {
            "link59_sha256": CONFIG.LINK60.BASELINE_SHA,
            "status": "untouched",
        },
        "next_gate":
            "prepare repaired nonpromotable C1 carriers, then request one "
            "hardware appointment for Cutpoints 3 and 4",
        "claim_limit":
            "Closes the artifact repair and structural replay only. C1, "
            "matrix closure, promotion and acceptance-chain gates are not "
            "claimed.",
    }
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        f"c2-link{LINK_NUMBER}-boot-inventory-pure-replay: PASS "
        f"product={sha(PRODUCT)} "
        f"boot={json.loads(source_boot[1].read_text(encoding='utf-8'))['storage']['size']} "
        "session=64926+1956 walls=134/161/2/443/151 "
        "compiler=0 linker=0 product-delta=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ReplayError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link60-boot-inventory-pure-replay: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
