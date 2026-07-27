#!/usr/bin/env python3
"""Emit the current L-full plane with the published-nullary latency fix.

This is host artifact work only.  It regenerates the canonical Workbench
sources, emits the four affected bytecode images into a private directory and
builds their C2D-v6/Bank-2 identity.  It runs no target compiler, linker or
hardware action.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_top_level_published_nullary_call_gate as DIRECT  # noqa: E402


BASE = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts")
PRODUCT = BASE / "product"
V6_OUT = BASE / "v6-semantics"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-published-nullary-call-bytecode-product-artifacts-receipt.json")
GENERATED = ROOT / "build/bytecode/dialect-v2"
SUITES = (
    GENERATED / "suites/p0-stdlib-einsuite-core-workbench-subset.json",
    GENERATED / "suites/p0-ide-core-lib.json",
    GENERATED / "suites/p0-ide-extra-lib.json",
    GENERATED / "suites/p0-m65d-lib.json",
)
PREFIXES = (
    (BASE / "workbench/stdlib-p0", "stdlib", "0x050000"),
    (BASE / "libs/ide", "disk-lib", "0x000000"),
    (BASE / "libs/idex", "disk-lib", "0x000000"),
    (BASE / "libs/m65d", "disk-lib", "0x000000"),
)
SPECS = (
    ("stdlib-p0", "stdlib", BASE / "workbench/stdlib-p0.manifest.json"),
    ("ide", "ide", BASE / "libs/ide.manifest.json"),
    ("idex", "idex", BASE / "libs/idex.manifest.json"),
    ("m65d", "m65d", BASE / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/c2.2/substitution/lcc.manifest.json"),
)
OLD_STDLIB = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "workbench/stdlib-p0.manifest.json")


class ArtifactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ArtifactError(message)


def sha(path: Path) -> str:
    import hashlib
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


def run(command: list[str]) -> None:
    result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ArtifactError(
            "host artifact command failed: " + " ".join(command)
            + "\n" + result.stdout + result.stderr)


def protect(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)


def main() -> int:
    require(
        not BASE.exists() and not RECEIPT.exists(),
        "published-nullary product artifact emission is one-shot",
    )
    source = DIRECT.validate_source(DIRECT.bundle())
    source["mutations_rejected"] = DIRECT.mutation_tests(DIRECT.bundle())
    execution = DIRECT.executable_fixtures()

    run([sys.executable, "tools/host-lisp/v2_workbench_codemod.py"])
    generated_eval = (
        GENERATED / "sources/lib/dialect-v2/eval-runtime.lisp")
    require(
        generated_eval.read_text(encoding="utf-8")
            == DIRECT.SOURCE.read_text(encoding="utf-8"),
        "generated Workbench source did not consume the canonical fast path",
    )
    for suite, (prefix, role, base_address) in zip(SUITES, PREFIXES):
        prefix.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check", "--emit-artifacts", str(prefix),
        ]
        if role == "disk-lib":
            command += [
                "--artifact-role", role, "--base-addr", base_address]
        command.append(str(suite))
        run(command)

    old_stdlib = load(OLD_STDLIB)
    stdlib = load(SPECS[0][2])
    old_lcc = next(
        row for row in old_stdlib["entries"] if row["name"] == "lcc-run")
    lcc = next(row for row in stdlib["entries"] if row["name"] == "lcc-run")
    require(
        int(old_stdlib["code_bytes"]) == 8293
        and int(stdlib["code_bytes"]) == 8326
        and int(old_lcc["length"]) == 76
        and int(lcc["length"]) == 109
        and int(stdlib["code_bytes"]) - int(old_stdlib["code_bytes"]) == 33,
        "compiled fast-path attribution is not exactly the 33-byte lcc-run delta",
    )
    require(
        {str(row.get("symbol")) for row in lcc["literals"]}
        == {
            "%c2-compile-form", "bytecode", "defmacro", "defun",
        },
        "compiled lcc-run literal domain drift",
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

    keymap = KEYGATE.validate(KEYGATE.source_bundle(), run_oracle=True)
    keymap["mutations_rejected"] = KEYGATE.mutation_tests(
        KEYGATE.source_bundle())
    require(
        static_code_bytes == 34542
        and product["images"] == 6
        and product["entries"] == 590
        and semantics["static_bank2"]["code_bytes"] == static_code_bytes
        and semantics["static_bank2"]["headroom_bytes"]
            == V6.BANK_BYTES - static_code_bytes
        and keymap["mutations_rejected"] == 10,
        "published-nullary six-image/C2D qualification red",
    )
    value = {
        "format":
            "lisp65-c2-published-nullary-call-product-artifacts-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-L-full-plus-published-nullary-six-image-product-and-C2D-v6-plane",
        "promotable": False,
        "source_gate": source,
        "host_execution_gate": execution,
        "compiled_attribution": {
            "baseline_stdlib_code_bytes": 8293,
            "current_stdlib_code_bytes": 8326,
            "baseline_lcc_run_bytes": 76,
            "current_lcc_run_bytes": 109,
            "delta_bytes": 33,
            "entry": {
                "blob_offset": int(lcc["blob_offset"]),
                "length": int(lcc["length"]),
                "literal_symbols": sorted(
                    str(row["symbol"]) for row in lcc["literals"]),
            },
        },
        "authority": {
            "canonical_source": bind(DIRECT.SOURCE),
            "direct_call_contract": bind(DIRECT.CONTRACT),
            "direct_call_gate": bind(Path(DIRECT.__file__)),
            "generated_source": bind(generated_eval),
            "generated_suites": [bind(path) for path in SUITES],
            "current_manifests": [
                bind(path) for _key, _name, path in SPECS],
            "keymap_gate": bind(Path(KEYGATE.__file__)),
            "driver": bind(Path(__file__)),
        },
        "queue_to_action_gate": keymap,
        "six_image_product": product,
        "c2d_v6": semantics,
        "capacity": {
            "bank2_static_code_bytes": static_code_bytes,
            "bank2_headroom_bytes": V6.BANK_BYTES - static_code_bytes,
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
            "latency_measurements_consumed": 0,
        },
        "next_gate":
            "bind canonical static-plane profile, then one product-shaped WPLTO",
    }
    report = BASE / "product-artifacts-report.json"
    report.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    value["report"] = bind(report)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    protect(BASE)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-published-nullary-call-product-artifacts: PASS "
        f"lcc-run=109 delta=33 bank2={static_code_bytes}/65536 "
        f"headroom={V6.BANK_BYTES - static_code_bytes}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ArtifactError,
        DIRECT.GateError,
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
            "c2-published-nullary-call-product-artifacts: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
