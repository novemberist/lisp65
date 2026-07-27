#!/usr/bin/env python3
"""Bind the real L-full Lisp payload to the frozen Link-57 WPLTO truth.

The target C/runtime WPLTO has already run exactly once.  This host-only
completion emits the six current Lisp images into a private product shelf and
builds the matching C2D-v6/Bank-2 plane.  It deliberately does not compile or
link target code and does not touch the historical substitution artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402


BASE = ROOT / "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts"
PRODUCT = BASE / "product"
V6_OUT = BASE / "v6-semantics"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-bytecode-product-artifacts-receipt.json")
OLD_IDE = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
SPECS = (
    ("stdlib-p0", "stdlib", BASE / "workbench/stdlib-p0.manifest.json"),
    ("ide", "ide", BASE / "libs/ide.manifest.json"),
    ("idex", "idex", BASE / "libs/idex.manifest.json"),
    ("m65d", "m65d", BASE / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/c2.2/substitution/lcc.manifest.json"),
)
SUITES = (
    ROOT / "build/bytecode/dialect-v2/suites/"
           "p0-stdlib-einsuite-core-workbench-subset.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-extra-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-m65d-lib.json",
)


class ArtifactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ArtifactError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def protect(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)


def main() -> int:
    require(BASE.is_dir() and not PRODUCT.exists() and not V6_OUT.exists()
            and not RECEIPT.exists(),
            "L-full bytecode product completion is one-shot")
    for _key, _name, manifest in SPECS:
        require(manifest.is_file(), f"current product manifest absent: {manifest}")
    for suite in SUITES:
        require(suite.is_file(), f"current product suite absent: {suite}")

    ide = load(BASE / "libs/ide.manifest.json")
    old_ide = load(OLD_IDE)
    entries = {str(row["name"]): row for row in ide["entries"]}
    required = {
        "ide-event-modifiers": 12,
        "%ide-modifier-command": 61,
        "ide-event-command": 126,
    }
    require(
        all(name in entries and int(entries[name]["length"]) == length
            for name, length in required.items()),
        "compiled L-full IDE consumer is incomplete",
    )
    require(
        int(ide["code_bytes"]) - int(old_ide["code_bytes"]) == 106
        and len(ide["entries"]) - len(old_ide["entries"]) == 2,
        "compiled L-full IDE attribution drift",
    )
    command_literals = entries["ide-event-command"]["literals"]
    require(
        {"ide-event-modifiers", "%ide-modifier-command"}.issubset({
            str(row["symbol"]) for row in command_literals
            if isinstance(row, dict) and "symbol" in row
        }),
        "compiled ide-event-command bypasses the modifier consumer",
    )

    original_sub = (SUB.BUILD, SUB.SPECS)
    original_v6 = (
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUB.BUILD = PRODUCT
        SUB.SPECS = SPECS
        product = SUB.build()
        static_code_bytes = sum(
            int(load(manifest)["code_bytes"])
            for _key, _name, manifest in SPECS)
        V6.OUT = V6_OUT
        V6.PRODUCT_IDENTITY = PRODUCT / "substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = static_code_bytes
        V6.A.SPECS = SPECS
        V6_OUT.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUB.BUILD, SUB.SPECS = original_sub
        (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES,
         V6.A.SPECS) = original_v6

    source_gate = KEYGATE.validate(KEYGATE.source_bundle(), run_oracle=True)
    source_gate["mutations_rejected"] = KEYGATE.mutation_tests(
        KEYGATE.source_bundle())
    require(
        product["images"] == 6
        and product["entries"] == 590
        and semantics["static_bank2"]["code_bytes"] == 34509
        and semantics["static_bank2"]["headroom_bytes"] == 31027
        and semantics["static_bank2"]["code_bytes"] < V6.BANK_BYTES
        and source_gate["status"] ==
            "passed-queue-tuple-to-compiled-product-action"
        and source_gate["mutations_rejected"] == 10,
        "current L-full Lisp product qualification red",
    )
    value = {
        "format": "lisp65-c2-link57-l-full-keymap-product-artifacts-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-current-L-full-six-image-product-and-C2D-v6-plane",
        "promotable": False,
        "authority": {
            "current_suites": [bind(path) for path in SUITES],
            "current_manifests": [
                bind(path) for _key, _name, path in SPECS],
            "canonical_keymap_contract": bind(KEYGATE.CONTRACT),
            "queue_to_action_gate": bind(Path(KEYGATE.__file__)),
            "emitter": bind(
                ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"),
            "one_C2_emitter": bind(
                ROOT / "tools/host-lisp/c2_full_emission.py"),
            "driver": bind(Path(__file__)),
        },
        "compiled_keymap_consumer": {
            "old_IDE": {
                "entries": len(old_ide["entries"]),
                "code_bytes": int(old_ide["code_bytes"]),
                "authority": bind(OLD_IDE),
            },
            "current_IDE": {
                "entries": len(ide["entries"]),
                "code_bytes": int(ide["code_bytes"]),
                "authority": bind(BASE / "libs/ide.manifest.json"),
                "functions": {
                    name: {
                        "length": int(entries[name]["length"]),
                        "blob_offset": int(entries[name]["blob_offset"]),
                    }
                    for name in required
                },
            },
            "delta": {"entries": 2, "code_bytes": 106},
            "consumer_calls_modifier_path": True,
        },
        "queue_to_action_gate": source_gate,
        "six_image_product": product,
        "c2d_v6": semantics,
        "capacity": {
            "bank2_static_code_bytes": 34509,
            "bank2_headroom_bytes": 31027,
            "bank5_C2D_bytes": V6.C2D_TOTAL_BYTES,
            "bank5_C2D_region_headroom_bytes":
                V6.C2D_REGION_BYTES - V6.C2D_TOTAL_BYTES,
        },
        "execution_accounting": {
            "host_bytecode_emitter_runs": 4,
            "target_compiler_runs": 0,
            "target_linker_runs": 0,
            "whole_program_LTO_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Current Lisp product emission and C2D-v6/Bank-2 capacity only; "
            "the frozen target WPLTO truth is joined by a separate replay."),
    }
    report = BASE / "product-artifacts-report.json"
    report.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    value["report"] = bind(report)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    protect(BASE)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link57-l-full-keymap-product-artifacts: PASS "
        f"ide={ide['code_bytes']} delta=106 "
        f"entries={product['entries']} "
        "bank2=34509/65536 headroom=31027")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ArtifactError,
        KEYGATE.GateError,
        KEYGATE.KEYMAP.KeymapError,
        SUB.SubstitutionArtifactError,
        V6.ProbeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-l-full-keymap-product-artifacts: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
