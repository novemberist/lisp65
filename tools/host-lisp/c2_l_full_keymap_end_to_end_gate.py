#!/usr/bin/env python3
"""Prove the physical C-Space/M-x queue-to-product-action chain.

The canonical binding table lives in config/v11-l-lite-keymap.json.  This
gate does not reconstruct that table.  It follows each row through the pinned
MEGA65 queue producer, the product-owned queue capture, vm_key_event's real
normalisation, the generated Lisp consumer and the Werkbank compilation
manifest.  Mutations exercise both sides of each boundary.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_kernal_unmap_probe as KPROBE  # noqa: E402
import v11_l_lite_keymap as KEYMAP  # noqa: E402


CONTRACT = ROOT / "config/v11-l-lite-keymap.json"
CROSS_CHECK = ROOT / "config/c2-l-full-keymap-probe.json"
WINDOW = ROOT / "src/c2_kernal_window.s"
VM = ROOT / "src/vm.c"
NORMALIZATION_H = ROOT / "src/petscii_normalization.h"
RUNTIME_H = ROOT / "src/c2_kernal_runtime.h"
GENERATED = ROOT / "lib/ide-keymap-generated.lisp"
WERKBANK = ROOT / "tests/bytecode/stdlib/p0-stdlib-werkbank-subset.json"
CORE = ROOT / "build/upstream-verification/mega65-core"
MATRIX = CORE / "src/vhdl/matrix_to_ascii.vhdl"
IOMAPPER = CORE / "src/vhdl/iomapper.vhdl"
UART = CORE / "src/vhdl/c65uart.vhdl"
CORE_SNAPSHOT = ROOT / (
    "tests/bytecode/dialect-v2/fixtures/"
    "c2-l-full-keymap-core-source-snapshot.json")
ORACLE = ROOT / "tools/host-lisp/ide_ui_eval_oracle.py"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_body(text: str, name: str) -> str:
    match = re.search(
        rf"\bsignal\s+{re.escape(name)}\s*:\s*key_matrix_t\s*:=\s*\("
        rf"(.*?)\n\s*\);",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    require(match is not None, f"core key table absent: {name}")
    return match.group(1)


def table_value(text: str, name: str, index: int) -> int:
    body = table_body(text, name)
    match = re.search(
        rf"^\s*{index}\s*=>\s*x\"([0-9a-f]{{2}})\"",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    require(match is not None, f"core key table index absent: {name}[{index}]")
    return int(match.group(1), 16)


def normalise(raw: int, modifiers: int) -> tuple[int, tuple[str, ...]]:
    code = raw
    if 0xC1 <= code <= 0xDA:
        code -= 0x80
        modifiers |= 0x03
    elif 0x41 <= code <= 0x5A:
        code += 0x20
    names: list[str] = []
    if modifiers & 0x03:
        names.append("shift")
    if modifiers & 0x04:
        names.append("control")
    if modifiers & 0x10:
        names.append("meta")
    # cons() prepends in vm_key_event, so the observable list is reversed.
    return code, tuple(reversed(names))


def dispatch(
    code: int, modifiers: tuple[str, ...], contract: dict[str, Any]
) -> int | None:
    for row in contract["modifier_bindings"]:
        if (
            code == row["normalized_code"]
            and row["required_modifiers"][0] in modifiers
        ):
            return int(row["command"])
    for row in contract["bindings"]:
        if len(row["codes"]) == 1 and code == row["codes"][0]:
            return int(row["command"])
    if contract["event_model"]["printable_min"] <= code <= (
        contract["event_model"]["printable_max"]
    ):
        return int(contract["event_model"]["printable_command"])
    return None


def source_bundle() -> dict[str, Any]:
    snapshot = json.loads(CORE_SNAPSHOT.read_text(encoding="utf-8"))
    expected_sources = {
        **KPROBE.CORE_BINDINGS,
        "src/vhdl/matrix_to_ascii.vhdl":
            "068dab4dfea391e8c6ac06ac31108be2e29d9d4510becbcbc1b2125bcb535536",
    }
    require(
        snapshot.get("format")
            == "lisp65-c2-l-full-keymap-core-source-snapshot-v1"
        and snapshot.get("core_commit")
            == "a9158930665763c592d004c895d52eff4a9eefc3"
        and snapshot.get("source_sha256") == expected_sources,
        "pinned MEGA65 core source snapshot identity drift")
    proof = snapshot.get("proof_sources")
    require(
        isinstance(proof, dict)
        and set(proof) == {"matrix", "iomapper", "uart"},
        "pinned MEGA65 core proof-source snapshot incomplete")
    full_paths = {
        relative: CORE / relative for relative in expected_sources
    }
    if all(path.is_file() for path in full_paths.values()):
        for relative, path in full_paths.items():
            require(
                sha(path) == expected_sources[relative],
                f"pinned MEGA65 core source drift: {relative}")
        full = {
            "matrix": MATRIX.read_text(encoding="utf-8"),
            "iomapper": IOMAPPER.read_text(encoding="utf-8"),
            "uart": UART.read_text(encoding="utf-8"),
        }
        for name, excerpt in proof.items():
            require(
                all(line in full[name] for line in excerpt.splitlines()
                    if line.strip()),
                f"MEGA65 core proof excerpt drift: {name}")
        core_mode = "full-pinned-source-plus-tracked-proof-excerpts"
        core_sources = full
    else:
        core_mode = "tracked-proof-excerpts-of-pinned-full-source"
        core_sources = proof
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "cross_check": json.loads(CROSS_CHECK.read_text(encoding="utf-8")),
        "window": WINDOW.read_text(encoding="utf-8"),
        "vm": VM.read_text(encoding="utf-8"),
        "normalization_h": NORMALIZATION_H.read_text(encoding="utf-8"),
        "runtime_h": RUNTIME_H.read_text(encoding="utf-8"),
        "generated": GENERATED.read_text(encoding="utf-8"),
        "werkbank": json.loads(WERKBANK.read_text(encoding="utf-8")),
        "matrix": core_sources["matrix"],
        "iomapper": core_sources["iomapper"],
        "uart": core_sources["uart"],
        "core_authority": {
            "mode": core_mode,
            "snapshot": snapshot,
        },
    }


def validate(bundle: dict[str, Any], *, run_oracle: bool) -> dict[str, Any]:
    contract = bundle["contract"]
    KEYMAP.validate(contract)
    cross = bundle["cross_check"]
    require(
        cross.get("format") == "lisp65-c2-l-full-keymap-probe-v2"
        and cross.get("canonical_binding_source")
        == "config/v11-l-lite-keymap.json#modifier_bindings",
        "L-full cross-check does not consume the canonical binding rows",
    )
    require(
        bundle["generated"] == KEYMAP.render_lisp(contract),
        "product Lisp consumer is not the canonical generated output",
    )
    require(
        "lib/ide-keymap-generated.lisp" in bundle["werkbank"].get("sources", []),
        "Werkbank product compilation manifest omits the generated consumer",
    )

    core = bundle["core_authority"]["snapshot"]
    require(
        core["core_commit"] == "a9158930665763c592d004c895d52eff4a9eefc3"
        and core["source_sha256"] == {
            **KPROBE.CORE_BINDINGS,
            "src/vhdl/matrix_to_ascii.vhdl":
                "068dab4dfea391e8c6ac06ac31108be2e29d9d4510becbcbc1b2125bcb535536",
        },
        "MEGA65 core authority is not the pinned source identity")

    window = bundle["window"]
    queue_start = window.index("\n.Lqueue_next:")
    queue_end = window.index("\n.Lqueue_empty:", queue_start)
    queue_window = window[queue_start:queue_end]
    capture_steps = [
        "lda $d60a",
        "and #$7f",
        "tay",
        "lda $d619",
        "sta $d619",
        "sta (__rc2),z",
    ]
    capture_positions = [queue_window.find(step) for step in capture_steps]
    require(
        all(position >= 0 for position in capture_positions)
        and capture_positions == sorted(capture_positions)
        and queue_window.count("sta (__rc2),z") == 2
        and queue_window.count("sta $d619") == 1,
            "product queue capture does not preserve one-head modifiers/code/dequeue order")

    runtime_h = bundle["runtime_h"]
    require(
        re.search(r"#define\s+LISP65_KEYMOD_CONTROL\s+0x04u", runtime_h)
        and re.search(r"#define\s+LISP65_KEYMOD_META\s+0x10u", runtime_h),
        "product modifier masks drifted from the queue contract",
    )
    vm = bundle["vm"]
    require(
        "lisp65_normalize_petscii((uint8_t)c, &event_modifiers)" in vm
        and "code >= 0x41u && code <= 0x5au" in bundle["normalization_h"]
        and "return (uint8_t)(code + 0x20u);" in bundle["normalization_h"],
        "vm_key_event no longer performs the raw-88 to code-120 normalisation",
    )
    require(
        "event_modifiers & LISP65_KEYMOD_CONTROL" in vm
        and "event_modifiers & LISP65_KEYMOD_META" in vm,
        "vm_key_event does not consume both required modifier domains",
    )

    matrix = bundle["matrix"]
    require(table_value(matrix, "matrix_petscii_normal", 23) == 0x58,
            "physical X no longer produces raw PETSCII 88")
    require(table_value(matrix, "matrix_petscii_control", 60) == 0xFF,
            "physical Control-Space no longer produces raw PETSCII 255")
    require(
        "elsif bucky_key_internal(4)='1' then" in matrix
        and "petscii_matrix := matrix_petscii_normal;" in matrix
        and "elsif bucky_key_internal(2)='1' then" in matrix
        and "petscii_matrix := matrix_petscii_control;" in matrix,
        "core Alt/Control PETSCII table selection drift",
    )
    require(
        "bucky_key_buffer(key_buffer_count) <= bucky_key;" in bundle["iomapper"]
        and "bucky_key_buffered <= bucky_key_buffer(0);" in bundle["iomapper"]
        and "porto => petscii_key_buffered" in bundle["iomapper"],
        "core queue no longer carries code and modifiers from one entry",
    )
    require(
        "fastio_rdata(6 downto 0) <= unsigned(bucky_key_buffered(6 downto 0));"
        in bundle["uart"]
        and "fastio_rdata <= unsigned(porto);" in bundle["uart"],
        "D60A/D619 queue register binding drift",
    )

    rows = {row["id"]: row for row in contract["modifier_bindings"]}
    masks = contract["event_model"]["modifier_masks"]
    expected = {
        "control-space": (0xFF, masks["control"], 0xFF, ("control",), 1115),
        "meta-x": (0x58, masks["meta"], 0x78, ("meta",), 1013),
    }
    positive: list[dict[str, Any]] = []
    for name, (raw, mask, code, modifiers, command) in expected.items():
        row = rows[name]
        require(
            (row["raw_petscii"], row["normalized_code"],
             row["required_modifiers"], row["command"])
            == (raw, code, list(modifiers), command),
            f"canonical binding domain drift: {name}",
        )
        actual_code, actual_modifiers = normalise(raw, mask)
        actual_command = dispatch(actual_code, actual_modifiers, contract)
        require(
            (actual_code, actual_modifiers, actual_command)
            == (code, modifiers, command),
            f"queue-to-action chain failed: {name}",
        )
        positive.append({
            "id": name,
            "queue_tuple": [raw, mask],
            "lisp_event": ["key", code, list(modifiers)],
            "linked_action": command,
        })

    negatives = [
        ("cspace-no-control", 0xFF, 0x00, None),
        ("cspace-wrong-meta", 0xFF, 0x10, None),
        ("mx-no-meta", 0x58, 0x00, 1110),
        ("mx-wrong-control", 0x58, 0x04, 1110),
        ("mx-raw-consumer-domain", 0x58, 0x10, 1013),
    ]
    negative_rows: list[dict[str, Any]] = []
    for name, raw, mask, expected_command in negatives:
        code, modifiers = normalise(raw, mask)
        command = dispatch(code, modifiers, contract)
        require(command == expected_command,
                f"negative queue-to-action case drift: {name}")
        negative_rows.append({
            "id": name, "queue_tuple": [raw, mask],
            "lisp_event": ["key", code, list(modifiers)],
            "linked_action": command,
        })
    # The consumer itself must reject the pre-normalised Meta-X domain.
    require(dispatch(0x58, ("meta",), contract) == 1110,
            "consumer accepted raw 88 as the Meta-X product domain")

    oracle_result = None
    if run_oracle:
        completed = subprocess.run(
            [sys.executable, str(ORACLE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        require(
            completed.returncode == 0 and "FAIL=0" in completed.stdout,
            "actual generated Lisp consumer oracle failed: "
            + (completed.stderr or completed.stdout).strip(),
        )
        oracle_result = completed.stdout.strip()

    return {
        "status": "passed-queue-tuple-to-compiled-product-action",
        "canonical_binding_source": "config/v11-l-lite-keymap.json#modifier_bindings",
        "positive_cases": positive,
        "negative_cases": negative_rows,
        "consumer_raw_88_action": 1110,
        "compiled_source_manifest": WERKBANK.relative_to(ROOT).as_posix(),
        "core_source_mode": bundle["core_authority"]["mode"],
        "oracle": oracle_result,
    }


def mutation_tests(bundle: dict[str, Any]) -> int:
    mutations: list[tuple[str, dict[str, Any]]] = []

    def add(name: str, mutator: Any) -> None:
        candidate = copy.deepcopy(bundle)
        mutator(candidate)
        mutations.append((name, candidate))

    add("control-space-code", lambda b: b["contract"]["modifier_bindings"][0].update(
        {"normalized_code": 0}))
    add("meta-x-raw", lambda b: b["contract"]["modifier_bindings"][1].update(
        {"raw_petscii": 120}))
    add("meta-mask", lambda b: b["contract"]["event_model"]["modifier_masks"].update(
        {"meta": 8}))
    add("queue-capture", lambda b: b.update({"window": b["window"].replace(
        ".Lstore_event:\n\tldz #$00\n\tsta (__rc2),z",
        ".Lstore_event:\n\tldz #$00\n\tsta C2K_EVENT_CODE",
        1)}))
    add("normalization", lambda b: b.update({"normalization_h":
        b["normalization_h"].replace(
            "return (uint8_t)(code + 0x20u);",
            "return (uint8_t)(code + 0x00u);", 1)}))
    add("consumer-modifiers", lambda b: b.update({"generated": b["generated"].replace(
        "(ide-event-modifiers event)", "nil", 1)}))
    add("compiled-source", lambda b: b["werkbank"]["sources"].remove(
        "lib/ide-keymap-generated.lisp"))
    normal_start = bundle["matrix"].index(
        "signal matrix_petscii_normal : key_matrix_t := (")
    normal_tail = bundle["matrix"][normal_start:]
    normal_x_row = re.search(r'^\s*23\s*=>\s*x"58",', normal_tail,
                             re.MULTILINE | re.IGNORECASE)
    require(normal_x_row is not None, "cannot construct physical X mutation")
    normal_absolute = normal_start + normal_x_row.start()

    def mutate_physical_x(candidate: dict[str, Any]) -> None:
        text = candidate["matrix"]
        candidate["matrix"] = (
            text[:normal_absolute]
            + text[normal_absolute:].replace('x"58"', 'x"59"', 1)
        )

    add("physical-x", mutate_physical_x)
    control_start = bundle["matrix"].index(
        "signal matrix_petscii_control : key_matrix_t := (")
    control_tail = bundle["matrix"][control_start:]
    control_row = re.search(r'^\s*60\s*=>\s*x"ff",', control_tail,
                            re.MULTILINE | re.IGNORECASE)
    require(control_row is not None, "cannot construct Control-Space mutation")
    absolute = control_start + control_row.start()

    def mutate_control_space(candidate: dict[str, Any]) -> None:
        text = candidate["matrix"]
        candidate["matrix"] = (
            text[:absolute] + text[absolute:].replace('x"ff"', 'x"20"', 1)
        )

    add("physical-control-space", mutate_control_space)
    add("cross-check-authority", lambda b: b["cross_check"].update(
        {"canonical_binding_source": "config/c2-l-full-keymap-probe.json"}))

    rejected = 0
    accepted: list[str] = []
    for name, candidate in mutations:
        try:
            validate(candidate, run_oracle=False)
        except (GateError, KEYMAP.KeymapError):
            rejected += 1
        else:
            accepted.append(name)
    require(rejected == len(mutations),
            "end-to-end keymap mutations passed: " + ", ".join(accepted))
    return rejected


def main() -> int:
    bundle = source_bundle()
    result = validate(bundle, run_oracle=True)
    rejected = mutation_tests(bundle)
    result["mutations_rejected"] = rejected
    result["bindings"] = {
        "canonical_contract": sha(CONTRACT),
        "generated_product_consumer": sha(GENERATED),
        "product_vm_normalizer": sha(VM),
        "product_queue_capture": sha(WINDOW),
        "werkbank_compilation_manifest": sha(WERKBANK),
        "pinned_core_snapshot": sha(CORE_SNAPSHOT),
        "pinned_core_matrix":
            bundle["core_authority"]["snapshot"]["source_sha256"][
                "src/vhdl/matrix_to_ascii.vhdl"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        GateError,
        KEYMAP.KeymapError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print("c2-l-full-keymap-end-to-end: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
