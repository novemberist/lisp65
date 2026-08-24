#!/usr/bin/env python3
"""Attribute and gate the last raw-DMA product refill from final ELF truth."""

from __future__ import annotations

import argparse
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


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SHIPPED_ELF = ROOT / ("build/release-v1.5.0/pack-product-b/lisp65-1.5.0/"
                      "proof/product/lisp65-c2-lite-product.elf")
RED_ELF = ROOT / ("build/c2.3/v1.6-nested-map-swap-replacement-card/wplto/"
                  "lisp65-c2-substitution-linked.prg.elf")
RUNTIME = ROOT / "src/c2_product_runtime.c"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
WITNESS_SOURCE = ROOT / "src/optional/c2_refill_boundary_witness.s"
OLD_RECEIPT = ARCH / "c2.3-v2.1-dma-content-structural-absence-receipt.json"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-dma-closure-attribution.json"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "fe531f3b"
RAW_READ_FACADE = "c2_facade_vm_code_load"
RAW_DMA_FACADE = "c2_facade_c2_dma"
CPU_READER = "c2_map_cpu_read"
CPU_READ_FACADE = "c2_facade_runtime_overlay_exec"
IMMUTABLE_CRC_READERS = {
    "c2_lite_stage_boot_family_impl",
    "c2_lite_stage_session_family_impl",
    "c2_lite_stage_session_overflow",
    "c2_phase02a_record_read",
    "c2_stream_phase_03b",
    "ov_bank_crc16",
    "rtov_read",
    "vm_boot_overlay_chain_prepare",
}


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("regression question first", "gate blind-spot attribution",
                  "linked elf", "unconditional success return",
                  "instrument neutrality"):
        require(token in text, f"boot-refill authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def function_bodies(elf: Path) -> dict[tuple[str, str], str]:
    text = subprocess.run(
        [str(OBJDUMP), "-d", "--symbolize-operands", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    section = ""
    current: tuple[str, str] | None = None
    rows: dict[tuple[str, str], list[str]] = {}
    for line in text.splitlines():
        if line.startswith("Disassembly of section "):
            section = line.removeprefix("Disassembly of section ").rstrip(":")
            current = None
            continue
        match = re.match(r"^[0-9a-f]+ <([^>]+)>:$", line)
        if match:
            current = (section, match.group(1))
            rows.setdefault(current, [])
        elif current is not None:
            if line.strip():
                rows[current].append(line)
            else:
                current = None
    return {key: "\n".join(value) for key, value in rows.items()}


def unique_body(bodies: dict[tuple[str, str], str], name: str) -> str:
    matches = [body for (_section, symbol), body in bodies.items()
               if symbol == name]
    require(len(matches) == 1, f"linked function identity drift: {name}")
    return matches[0]


def direct_callers(bodies: dict[tuple[str, str], str], target: str
                   ) -> list[dict[str, str]]:
    marker = f"<{target}>"
    return sorted(
        ({"section": section, "function": name}
         for (section, name), body in bodies.items() if marker in body),
        key=lambda row: (row["section"], row["function"]))


def source_gate(text: str | None = None) -> dict[str, Any]:
    source = RUNTIME.read_text(encoding="utf-8") if text is None else text
    body = source.split("C2_COLD_SOURCE_FN uint8_t c2_source_read", 1)[1]
    body = body.split("\n}\n", 1)[0]
    require("#ifdef LISP65_C2_MAP_CPU_TRANSPORT" in body
            and "return c2_facade_map_cpu_read(" in body
            and "#else" in body
            and "c2_dma_copy(" in body
            and "return 1;" in body,
            "common product-source seam is not MAP-CPU fail-propagating")
    map_part, legacy = body.split("#else", 1)
    require("c2_dma_copy(" not in map_part
            and "return 1;" not in map_part
            and "c2_facade_map_cpu_read" not in legacy,
            "MAP-CPU product-source branch retains unconditional DMA success")
    return {"status": "PASS: PRODUCT SOURCE SEAM USES MAP-CPU",
            "owner": "c2_source_read",
            "active_transport": "c2_facade_map_cpu_read",
            "failure_propagated": True,
            "legacy_DMA_is_feature_excluded": True}


def source_mutations() -> list[str]:
    source = RUNTIME.read_text(encoding="utf-8")
    cases = {
        "restore-unconditional-DMA-success": source.replace(
            "return c2_facade_map_cpu_read(\n"
            "            base + relative, (uint8_t *)dst, length);",
            "c2_dma_copy(base + relative,\n"
            "                    (uint32_t)(uint16_t)(uintptr_t)dst, length);\n"
            "        return 1;", 1),
        "discard-MAP-read-failure": source.replace(
            "return c2_facade_map_cpu_read(\n"
            "            base + relative, (uint8_t *)dst, length);",
            "(void)c2_facade_map_cpu_read(\n"
            "            base + relative, (uint8_t *)dst, length);\n"
            "        return 1;", 1),
    }
    rejected: list[str] = []
    for name, mutant in cases.items():
        try:
            source_gate(mutant)
        except ClosureError:
            rejected.append(name)
    require(rejected == list(cases), "source pass-through mutation survived")
    return rejected


def generated_source_gate(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    marker = "uint8_t c2_product_entry_read("
    require(source.count(marker) == 1,
            "emitted boot-refill function identity drift")
    body = source.split(marker, 1)[1].split("\n}\n", 1)[0]
    require("c2_facade_map_cpu_read(" in body
            and "c2_facade_runtime_overlay_exec" in body
            and "if (!c2_facade_map_cpu_read(" in body
            and "c2_facade_vm_code_load(" not in body,
            "emitted boot refill is not MAP-CPU fail-propagating")
    return {"status": "PASS: EMITTED BOOT REFILL USES MAP-CPU",
            "emitted_source": bind(path), "owner": "c2_product_entry_read",
            "transport": "c2_facade_runtime_overlay_exec",
            "failure_propagated": True, "raw_read_edges": 0}


def linked_read_model(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    bodies = function_bodies(elf)
    product = unique_body(bodies, "c2_product_entry_read")
    raw_callers = direct_callers(bodies, RAW_READ_FACADE)
    cpu_callers = direct_callers(bodies, CPU_READER)
    witness_matches = [body for (_section, name), body in bodies.items()
                       if name == "c2_refill_trace_read"]
    witness = witness_matches[0] if len(witness_matches) == 1 else ""
    classified = [{**row, "sink": RAW_READ_FACADE,
        "classification": ("immutable-delivery-CRC"
            if row["function"] in IMMUTABLE_CRC_READERS
            else "unchecked-content-DMA-read")}
        for row in raw_callers]
    unsafe = [row for row in classified
              if row["classification"] == "unchecked-content-DMA-read"]
    witness_source = (WITNESS_SOURCE.read_text(encoding="utf-8")
                      if WITNESS_SOURCE.is_file() else "")
    source_passthrough = (witness_source.count("jsr c2_product_entry_read") == 1
                          and witness_source.count(
                              "jmp c2_product_entry_read") == 1)
    return {
        "ELF": bind(elf),
        "product_entry": {
            "section": truth.symbol("c2_product_entry_read").section,
            "raw_read_edges": product.count(f"<{RAW_READ_FACADE}>"),
            "raw_DMA_edges": product.count(f"<{RAW_DMA_FACADE}>"),
            "MAP_CPU_edges": (product.count(f"<{CPU_READER}>")
                              + product.count(f"<{CPU_READ_FACADE}>")),
        },
        "linked_raw_read_callers": raw_callers,
        "classified_raw_read_callers": classified,
        "linked_MAP_CPU_callers": cpu_callers,
        "unsafe_content_DMA_surfaces": unsafe,
        "unsafe_content_DMA_count": len(unsafe),
        "instrument": {
            "present": bool(witness),
            "product_entry_edges": witness.count("<c2_product_entry_read>"),
            "raw_read_edges": witness.count(f"<{RAW_READ_FACADE}>"),
            "raw_DMA_edges": witness.count(f"<{RAW_DMA_FACADE}>"),
            "neutral": (not witness or (
                source_passthrough
                and f"<{RAW_READ_FACADE}>" not in witness
                and f"<{RAW_DMA_FACADE}>" not in witness)),
        },
    }


def validate_final(value: dict[str, Any]) -> None:
    entry = value.get("product_entry", {})
    instrument = value.get("instrument", {})
    require(value.get("unsafe_content_DMA_count") == 0
            and value.get("unsafe_content_DMA_surfaces") == []
            and entry.get("raw_read_edges") == 0
            and entry.get("raw_DMA_edges") == 0
            and entry.get("MAP_CPU_edges", 0) >= 1
            and instrument.get("neutral") is True,
            "final ELF retains an unchecked content-DMA refill")


def final_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-exact-pass-through": lambda x: (
            x["linked_raw_read_callers"].append({
                "section": ".text", "function": "c2_product_entry_read"}),
            x["unsafe_content_DMA_surfaces"].append({
                "section": ".text", "function": "c2_product_entry_read",
                "sink": RAW_READ_FACADE,
                "classification": "unchecked-content-DMA-read"}),
            x.update(unsafe_content_DMA_count=1),
            x["product_entry"].update(raw_read_edges=1)),
        "remove-MAP-CPU-edge": lambda x: x["product_entry"].update(
            MAP_CPU_edges=0),
        "instrument-bypasses-safety": lambda x: x["instrument"].update(
            raw_read_edges=1, neutral=False),
        "hide-recorded-unsafe-count": lambda x: x.update(
            unsafe_content_DMA_count=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_final(trial)
        except ClosureError:
            rejected.append(name)
    require(rejected == list(cases), "boot-refill DMA mutation survived")
    return rejected


def attribution() -> dict[str, Any]:
    shipped = linked_read_model(SHIPPED_ELF)
    current = linked_read_model(RED_ELF)
    old = load(OLD_RECEIPT)
    for label, model in (("v1.5.0", shipped), ("v1.6-red", current)):
        require(model["product_entry"]["raw_read_edges"] == 1
                and model["product_entry"]["MAP_CPU_edges"] == 0
                and any(row["function"] == "c2_product_entry_read"
                        for row in model["linked_raw_read_callers"]),
                f"{label} does not contain the exact raw refill pass-through")
    registered = old["linked_model"]["registered_surfaces"]
    require(old["linked_model"]["unsafe_content_DMA_count"] == 0
            and not any(row.get("owner") == "c2_product_entry_read"
                        for row in registered),
            "historical blind-spot shape drift")
    return {
        "format": "lisp65-c2-v160-boot-refill-dma-closure-attribution-v1",
        "recorded_on": "2026-08-23",
        "status": "PASS: SHIPPED V1.5 AND V1.6 RED SHARE UNCHECKED DMA REFILL",
        "authority": authority(),
        "worlds": {"shipped_v1.5.0": shipped, "v1.6_first_red": current},
        "regression_decision": {
            "v1.6_born": False,
            "shipped_product_affected": True,
            "owner_decision_required": ["known-issues", "v1.5-backport"],
        },
        "blind_spot": {
            "old_receipt": bind(OLD_RECEIPT),
            "old_recorded_unsafe_count": 0,
            "old_population": "two named wrappers plus historical registry",
            "missing_linked_consumer": "c2_product_entry_read",
            "mechanism": ("the gate inspected selected final-ELF bodies but "
                          "never enumerated all callers of the raw read facade"),
            "successor_rule": ("derive every raw content-read facade caller "
                               "from the final linked ELF"),
        },
        "claim_limit": ("Host-only attribution. Historical evidence is read "
                        "without mutation; no media or device action."),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "media_builds": 0, "device_contacts": 0},
    }


def write_attribution() -> None:
    require(not RECEIPT.exists(), "boot-refill attribution receipt exists")
    RECEIPT.write_bytes(canonical(attribution()))
    print("boot-refill DMA attribution: PASS v1.5=affected blind-spot=linked-population")


def check_attribution() -> None:
    # The receipt is sealed evidence for the world in which the attribution
    # was made.  Later strengthening of the linked population must not turn
    # that evidence into a live-source regeneration treadmill.  Re-derive the
    # claim-bearing facts, but compare them semantically rather than requiring
    # the historical JSON projection to gain every new explanatory field.
    stored = load(RECEIPT)
    current = attribution()
    require(stored["status"] == current["status"]
            and stored["regression_decision"] == current["regression_decision"]
            and stored["blind_spot"]["missing_linked_consumer"]
                == "c2_product_entry_read"
            and stored["worlds"]["shipped_v1.5.0"]["ELF"]
                == current["worlds"]["shipped_v1.5.0"]["ELF"]
            and stored["worlds"]["v1.6_first_red"]["ELF"]
                == current["worlds"]["v1.6_first_red"]["ELF"]
            and current["worlds"]["shipped_v1.5.0"]
                ["unsafe_content_DMA_count"] >= 1
            and current["worlds"]["v1.6_first_red"]
                ["unsafe_content_DMA_count"] >= 1,
            "boot-refill attribution claim drift")
    print("boot-refill DMA attribution: CHECK PASS v1.5=affected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write-attribution",
                                           "check-attribution", "final"))
    parser.add_argument("elf", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "write-attribution":
        write_attribution()
    elif args.action == "check-attribution":
        check_attribution()
    else:
        require(args.elf is not None, "final action requires ELF")
        model = linked_read_model(args.elf.resolve())
        validate_final(model)
        mutations = final_mutations(model)
        print("boot-refill DMA final gate: PASS unsafe=0 "
              f"mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClosureError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"boot-refill DMA closure: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
