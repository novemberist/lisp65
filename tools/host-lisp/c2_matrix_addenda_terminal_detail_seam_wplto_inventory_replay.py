#!/usr/bin/env python3
"""Resume the E5 WPLTO after a pure seed-inventory replay.

The preceding attempt emitted and froze the prerequisite resident-Island seed,
then a historical section inventory stopped before Island materialization and
before the one product-closure link.  This driver copies that immutable seed,
replays the corrected profile-derived inventory, and performs only the still
unconsumed closure link.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_terminal_detail_seam_wplto as BASE  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-inventory-replay")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay-receipt.json")
FIRST = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-receipt.json")
FIRST_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-internal.json")
ORIGINAL_AUTHORITY = BASE.authority

SEED_FILES = (
    "resident-island-seed.prg",
    "resident-island-seed.prg.elf",
    "resident-island-seed.prg.map",
    "resident-island-seed.prg.lto.o",
    "resident-island-seed.prg.link.stdout.txt",
    "resident-island-seed.prg.link.stderr.txt",
    "exact-orphan-wrapper-resident-island-seed.prg.json",
    "c2-substitution.ld",
    "resolved-profile.txt",
    "runtime-overlay.prepare-standard.h",
    "runtime-overlay.prepare.h",
    "resident-island.prepare.h",
    "stage-config.h",
    "error-text-table.h",
    "error-text-table.bin",
    "c2-kernal-window.generated.h",
    "v2-product-profile-parity.json",
)


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "bytes": (SOURCE / name).stat().st_size,
            "sha256": sha(SOURCE / name),
            "mode": oct((SOURCE / name).stat().st_mode & 0o777),
        }
        for name in paths
    }


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    internal = json.loads(FIRST_INTERNAL.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"].startswith(
            "final section inventory red: ")
        and "frame_source" in internal["diagnostic"]["message"]
        and "event_poll" in internal["diagnostic"]["message"]
        and "typed_queue_driver" in internal["diagnostic"]["message"]
        and internal["execution_accounting"]["product_closure_links"] == 0,
        "typed-queue inventory First Red drift",
    )
    value["class_A_inventory_first_red"] = BASE.BASE.P.bind(FIRST)
    value["class_A_inventory_diagnosis"] = BASE.BASE.P.bind(FIRST_INTERNAL)
    value["class_A_inventory_correction"] = {
        "canonical_source": "configured KERNAL_SECTIONS product profile",
        "retired_members": [
            ".lisp65_c2_kernal_window.frame_source",
            ".lisp65_c2_kernal_window.event_poll",
            ".rela.lisp65_c2_kernal_window.event_poll",
        ],
        "profile_member": ".rela.lisp65_c2_kernal_window.typed_queue_driver",
        "hard_edges": "missing and additional names remain red",
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
    }
    value["replay_driver"] = BASE.BASE.P.bind(Path(__file__))
    return value


def copy_seed(out: Path) -> dict[str, dict[str, Any]]:
    before = snapshot(SEED_FILES)
    require(all((int(row["mode"], 8) & 0o222) == 0
                for row in before.values()),
            "source seed evidence is not read-only")
    out.mkdir(parents=True, exist_ok=True)
    for name in SEED_FILES:
        source = SOURCE / name
        target = out / name
        require(source.is_file(), f"seed replay input absent: {name}")
        if target.exists():
            require(target.read_bytes() == source.read_bytes(),
                    f"pre-existing replay input differs: {name}")
        else:
            shutil.copy2(source, target)
        os.chmod(target, 0o444)
    return before


def resume_single_link(out: Path, *,
                       probe_definitions: tuple[str, ...] = (),
                       **_kwargs: Any) -> None:
    require(out == OUT, "inventory replay output route drift")
    before = copy_seed(out)
    seed = out / "resident-island-seed.prg"
    inventory = PRODUCT.final_section_inventory_gate(out, seed)
    metadata = PRODUCT.lto_partition_metadata_gate(out, seed)
    expectation = PRODUCT.final_section_inventory_expectation()
    require(
        inventory["status"] == "passed"
        and expectation["typed_queue_profile"] is True
        and expectation["base_pin_names"] == 140
        and expectation["expected_names"] == 175
        and len(expectation["removed_from_link28"]) >= 3
        and metadata["status"] == "passed",
        "corrected immutable seed qualification is red",
    )

    contract = out / "resolved-profile.txt"
    island_header = out / "resident-island.h"
    PRODUCT.tool(
        "resident_island.py", "materialize",
        "--elf", str(seed) + ".elf",
        "--nm", str(PRODUCT.TOOLCHAIN / "llvm-nm"),
        "--objcopy", str(PRODUCT.TOOLCHAIN / "llvm-objcopy"),
        "--abi-contract", str(contract),
        "--header", str(island_header),
    )
    artifacts = json.loads(
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST.read_text(encoding="utf-8"))
    final = PRODUCT.compile_link(
        out, "lisp65-c2-substitution-linked.prg",
        [
            out / "stage-config.h",
            out / "runtime-overlay.prepare.h",
            island_header,
            out / "error-text-table.h",
            out / "c2-kernal-window.generated.h",
        ],
        artifacts,
        probe_definitions=probe_definitions,
    )
    PRODUCT.finish_single_link(out, final, contract)
    require(before == snapshot(SEED_FILES),
            "resume modified the immutable source seed evidence")


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "terminal-detail WPLTO inventory replay is one-shot",
    )
    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
        "single_link": PRODUCT.single_link,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        PRODUCT.single_link = resume_single_link
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
        PRODUCT.single_link = old["single_link"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["format"] = (
        "lisp65-c2-link58-matrix-addenda-terminal-detail-seam-"
        "WPLTO-inventory-replay-v1")
    value["status"] = (
        "passed-E5-terminal-detail-seam-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["class_A_inventory_replay"] = {
        **authority()["class_A_inventory_correction"],
        "compiler_runs_for_seed": 0,
        "linker_runs_for_seed": 0,
        "product_closure_links": 1,
    }
    value["next_gate"] = (
        "authorized successor product link, then bundled C1 Freezer cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-terminal-detail-seam-inventory-replay: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-terminal-detail-seam-inventory-replay: "
            "FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
