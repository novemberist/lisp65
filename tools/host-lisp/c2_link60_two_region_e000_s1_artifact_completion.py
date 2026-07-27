#!/usr/bin/env python3
"""Complete Link 60 after its inherited B94E checker First Red.

The product closure already finished and the immutable ELF measures the
owner-authorized B972 table.  This class-A replay copies that exact artifact,
publishes the declared 42-byte domain and runs the current gates without a
compiler, linker or hardware run.
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
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as PROFILE  # noqa: E402
import c2_lite_v6_bank2_target_stage_wplto as BANK2  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_two_region_session_store_wplto as TWO  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as LINK60  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-60-two-region-e000-s1")
SOURCE_PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
SOURCE_ELF = Path(str(SOURCE_PRODUCT) + ".elf")
SOURCE_MAP = Path(str(SOURCE_PRODUCT) + ".map")
PROFILE_PATH = SOURCE / "resolved-profile.txt"
FIRST_RED = EVIDENCE / "c2.2-product-link60-internal.json"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-60-two-region-e000-s1-completion")
PRODUCT = OUT / SOURCE_PRODUCT.name
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
RECEIPT = LINK60.RECEIPT
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "product/substitution-artifacts.json")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-60 artifact absent: {path}")
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


def configure() -> None:
    PROFILE.configure()
    # Bank-2 staging owns a real linked decoder record.  It is part of the
    # canonical feature profile and must be installed into the structural
    # Boot inventory before any artifact-side pack/repack.  The previous
    # completion reconstructed only the generic predecessor inventory and
    # therefore omitted c2-decode-03b while retaining the compiled slot ABI.
    BANK2.configure_bank2_stage()
    TWO.configure_two_region()
    LINK60.configure_current_pin_adapters()
    P.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
    require(
        P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
        and P.VERIFIER_BINDING_BASE == 0xB972
        and P.runtime_binding_bytes() == 40
        and P.total_publish_last_bytes() == 42
        and P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D
        and P.SESSION_EMITTER_STATE_BASE == 0xFD22
        and P.PROFILE_RODATA_BASE == 0xFD2C,
        "Link-60 completion profile geometry drift",
    )
    require(
        len(P.BOOT_SLICE_SPECS) + len(P.BOOT_DATA_SPECS) == 12
        and P.BOOT_BANK3_STAGE_SLOT == 9
        and P.BOOT_ISLAND_SLOT == 10
        and P.BOOT_ISLAND_CARRIER_SLOT == 11,
        "Link-60 canonical Boot inventory drift",
    )


def measured_walls() -> dict[str, int]:
    sections = P.section_table(ELF)
    return {
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


def main() -> int:
    require(
        not OUT.exists() and not RECEIPT.exists(),
        "Link-60 artifact completion is one-shot",
    )
    authority_paths = (
        SOURCE_PRODUCT, SOURCE_ELF, SOURCE_MAP, PROFILE_PATH, FIRST_RED,
        LINK60.ARTIFACT_COMPLETION, LINK60.WPLTO_PROFILE,
        LINK60.BASELINE, LINK60.BASELINE_RECEIPT,
        LINK60.KERNAL_CONTRACT, LINK60.REGION_CONTRACT,
        LINK60.FORMAT_RECEIPT, LINK60.COMPLETION_SOURCE_RECEIPT,
        LINK60.EMITTER_RECEIPT, LINK60.ISLAND_RECEIPT, PRODUCT_IDENTITY,
    )
    require(
        all(path.is_file() for path in authority_paths)
        and sha(LINK60.ARTIFACT_COMPLETION)
            == LINK60.ARTIFACT_COMPLETION_SHA
        and sha(LINK60.WPLTO_PROFILE) == LINK60.WPLTO_PROFILE_SHA
        and sha(LINK60.BASELINE) == LINK60.BASELINE_SHA,
        "Link-60 completion authority drift",
    )
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["status"] == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and first["diagnostic"] == {
            "message": "verifier binding address drift 0xb972 != 0xb94e",
            "type": "RuntimeError",
        }
        and first["execution_accounting"]["product_closure_links"] == 1,
        "Link-60 inherited-pin First Red drift",
    )
    profile_preflight = LINK60.feature_preflight()
    profile_equal = (
        LINK60.canonical_profile_rows(PROFILE_PATH)
        == LINK60.canonical_profile_rows(LINK60.WPLTO_PROFILE))
    require(
        profile_equal,
        "Link-60 linked profile differs from canonical WPLTO profile",
    )
    before = snapshot(SOURCE)
    require(
        before
        and all((int(row["mode"], 8) & 0o222) == 0
                for row in before.values()),
        "Link-60 First-Red artifact tree is not immutable",
    )

    shutil.copytree(SOURCE, OUT)
    os.chmod(OUT, 0o755)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o644)
        elif path.is_dir():
            os.chmod(path, 0o755)
    configure()

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
            f"Link-60 completion attempted compiler/linker: {executable}",
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
            ELF,
            out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
            require_bank3_chain=P.FAMILY_STAGE_BINDINGS,
        )
        f011 = P.F011_WINDOW.audit(P.F011_WINDOW.disassemble(
            P.TOOLCHAIN / "llvm-objdump", ELF))
        P.write(
            OUT / "c2-f011-mount-window-gate.json",
            json.dumps(f011, indent=2, sort_keys=True) + "\n")
        handoff = P.handoff_z_abi_gate(OUT, PRODUCT, "link60-completion")
        pre = P.pre_ownership_gate(OUT, PRODUCT, "link60-completion")
        data = P.profile_data_reference_gate(
            OUT, PRODUCT, "link60-completion", pre)
        facade = P.fixed_facade_gate(
            OUT, PRODUCT, "link60-completion")
        fixed = P.FIXED_BLOCK_LEAF.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-link60.json")

        unbound_boot = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "unbound")
        unbound_session = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "unbound")
        binding = P.patch_verifier_binding_table(
            OUT, PRODUCT, unbound_boot[1], unbound_session[1],
            expected_base=0xB972)
        window = json.loads(
            (OUT / "kernal-window-publish-last.json").read_text(
                encoding="utf-8"))
        publish = P.total_publish_last_gate(
            OUT, PRODUCT, window, binding,
            expected_verifier_base=0xB972)
        final_boot = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "boot", "final")
        final_session = P.overlay_pack_family(
            OUT, PRODUCT, PROFILE_PATH, "session", "final")
        family = P.runtime_family_identity_gate(
            OUT, unbound_boot, unbound_session, final_boot, final_session)
        P.write(
            OUT / "runtime-overlays-final.bin",
            final_session[0].read_bytes())
        P.write(
            OUT / "runtime-overlays-final-region1.bin",
            (OUT / "runtime-overlays-session-final-region1.bin").read_bytes())
        P.closure_gate(OUT, PRODUCT)
        kernal = P.kernal_freedom_gate(OUT, PRODUCT)
        balance = P.substitution_balance(OUT, PRODUCT, kernal)
        static_island = ISLAND.static_elf_gate(ELF)
    finally:
        subprocess.run = original_run

    walls = measured_walls()
    boot = json.loads(final_boot[1].read_text(encoding="utf-8"))
    session = json.loads(final_session[1].read_text(encoding="utf-8"))
    overflow = session["overflow_storage"]
    format_gate = json.loads(
        LINK60.FORMAT_RECEIPT.read_text(encoding="utf-8"))
    completion_source = json.loads(
        LINK60.COMPLETION_SOURCE_RECEIPT.read_text(encoding="utf-8"))
    emitter = json.loads(
        LINK60.EMITTER_RECEIPT.read_text(encoding="utf-8"))
    source_host = json.loads(
        LINK60.ISLAND_RECEIPT.read_text(encoding="utf-8"))
    sections = P.section_table(ELF)
    require(
        walls == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and int(session["storage"]["size"]) == 64926
        and 65536 - int(session["storage"]["size"]) == 610
        and int(overflow["used"]) == 1956
        and int(overflow["capacity"]) == 2032
        and sections[P.VERIFIER_BINDING_SECTION] == {
            "address": 0xB972, "bytes": 40}
        and binding["status"] == "passed"
        and publish["status"] == "passed"
        and publish["declared_domain_bytes"] == 42
        and family["status"] == "passed"
        and kernal["status"] == "passed"
        and balance["status"] == "passed"
        and static_island["E000_S1"]["status"].startswith("passed")
        and format_gate["status"].startswith("passed")
        and format_gate["stage_source_authority"]["status"].startswith(
            "passed")
        and completion_source["status"].startswith("passed")
        and completion_source["mutation_count"] == 21
        and emitter["status"].startswith("passed")
        and source_host["status"].startswith("passed")
        and fixed["fixed_code"]["end_exclusive"] == 0xC25D
        and fixed["hot_bss"]["address"] == 0xC25D,
        "Link-60 artifact-side final qualification red",
    )
    require(
        before == snapshot(SOURCE)
        and sha(LINK60.BASELINE) == LINK60.BASELINE_SHA,
        "Link-60 completion changed source artifact or Link-59 rollback",
    )

    artifact_report = {
        "format": "lisp65-c2-link60-artifact-completion-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-current-B972-gate-replay-and-product-completion",
        "historical_checker": {
            "owner_authority": "0xb972",
            "inherited_adapter": "0xb94e",
            "correction":
                "current Link-60 adapter consumes current contract pin; "
                "historical Link-50 source and receipts remain unchanged",
            "product_bytes_before_completion_changed": 0,
        },
        "walls": walls,
        "runtime_families": {
            "boot_main_bytes": boot["storage"]["size"],
            "session_main_bytes": session["storage"]["size"],
            "session_main_headroom_bytes": 610,
            "session_overflow_used_bytes": overflow["used"],
            "session_overflow_capacity_bytes": overflow["capacity"],
            "session_overflow_headroom_bytes":
                int(overflow["capacity"]) - int(overflow["used"]),
        },
        "publish_last": {
            "verifier": binding,
            "total": publish,
        },
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
            "family_identity": family["status"],
            "one_truth": "passed",
            "KERNAL_freedom": kernal["status"],
            "substitution_balance": balance["status"],
            "preinstall_E000_S1": static_island["E000_S1"]["status"],
            "strict_v4": format_gate["status"],
            "write_completion_mutations": completion_source["mutation_count"],
            "emitter_union": emitter["status"],
            "all_fresh_green": True,
        },
        "execution_accounting": {
            "product_closure_links": 1,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "automatic_retries": 0,
            "hardware_runs": 0,
            "read_only_tool_invocations": commands,
        },
    }
    report_path = OUT / "link60-artifact-completion.json"
    write_json(report_path, artifact_report)

    receipt = {
        "format": "lisp65-c2-lite-v6-link60-two-region-E000-S1-v1",
        "recorded_on": "2026-07-24",
        "link_number": 60,
        "status":
            "passed-link60-two-region-E000-S1-product-identity-hardware-not-run",
        "promotable": False,
        "authority": {
            "qualified_WPLTO_artifact_completion": bind(
                LINK60.ARTIFACT_COMPLETION),
            "canonical_WPLTO_profile": bind(LINK60.WPLTO_PROFILE),
            "link60_first_red": bind(FIRST_RED),
            "link60_artifact_completion": bind(report_path),
            "link59_rollback_product": {
                **bind(LINK60.BASELINE), "status": "untouched"},
            "link59_rollback_receipt": bind(LINK60.BASELINE_RECEIPT),
            "kernal_contract": bind(LINK60.KERNAL_CONTRACT),
            "two_region_contract": bind(LINK60.REGION_CONTRACT),
            "driver": bind(Path(__file__)),
        },
        "profile_binding": {
            **profile_preflight,
            "link_profile_sha256": sha(PROFILE_PATH),
            "path_normalized_rows_byteidentical": profile_equal,
        },
        "walls": walls,
        "runtime_families": artifact_report["runtime_families"],
        "publish_last": {
            "verifier_table_address": "0xb972",
            "verifier_and_family_stage_bytes": 40,
            "kernal_CRC_addresses": ["0xb4cc", "0xb4d0"],
            "total_declared_bytes": 42,
            "status": "passed",
        },
        "fresh_gate_program": artifact_report["gates"],
        "product_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "runtime_boot": bind(final_boot[0]),
            "runtime_session": bind(final_session[0]),
            "runtime_session_region1": bind(
                OUT / "runtime-overlays-session-final-region1.bin"),
            "predecessor_sha256": LINK60.BASELINE_SHA,
            "new_identity": sha(PRODUCT) != LINK60.BASELINE_SHA,
        },
        "C1_Freezer_cutpoints": {
            "cutpoint_3":
                "repeat-with-episode-latch-on-exact-Link60-identity",
            "cutpoint_4":
                "repeat-with-write-completion-barriers-on-exact-Link60-"
                "identity",
            "matrix_C1": "OPEN-until-both-hardware-results-green",
        },
        "execution_accounting": artifact_report["execution_accounting"],
        "counters": {
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "2/2-passed",
        },
        "next_gate":
            "prepare Cutpoint-3 episode-latch and Cutpoint-4 write-"
            "completion carriers for this exact product; request hardware "
            "start before execution",
        "claim_limit":
            "Structurally complete Link 60 only. C1, matrix closure, "
            "promotion and R4/R5/R6/G5/G6 are not claimed.",
    }
    require(
        receipt["product_identity"]["new_identity"],
        "Link 60 did not produce a new identity relative to Link 59",
    )
    write_json(RECEIPT, receipt)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link60-artifact-completion: COMPLETE "
        f"product={sha(PRODUCT)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"island={walls['resident_island_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        "session=64926+1956 verifier=B972 compiler=0 linker=0 hardware=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CompletionError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link60-artifact-completion: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
