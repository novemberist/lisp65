#!/usr/bin/env python3
"""Pack Card 6's omission world and close boot/print-9 DWX evidence."""

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

import block_26_small_hardening_omission_product_card as CARD  # noqa: E402
import block_26_vm_hardening_dwx_prefilter as BASE  # noqa: E402
import block_26_f011_dwx_prefilter as BOOT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card6-small-hardening-omission-dwx-r2"
MEDIA_BUILD = BUILD / "media"
WPLTO = MEDIA_BUILD / "inputs/wplto"
STATIC = MEDIA_BUILD / "inputs/static-plane"
TARGET = MEDIA_BUILD / "canonical-product"
SHARED = MEDIA_BUILD / "shared-system"
MEDIA_RECEIPT = BUILD / "prefilter-medium-receipt.json"
SESSION = BUILD / "unused-device-session.json"
PREFILTER_RECEIPT = ARCH / (
    "block-2.6-card6-small-hardening-omission-dwx-r2.json")
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-omission-dwx-r2.md"
BOOT_LEDGER = ROOT / "config/boot-phase-cycle-ledger.json"
CARD3_DWX_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-dwx-r2.json"
CARD3_PRODUCT_RECEIPT = ARCH / (
    "block-2.6-card3-vm-hardening-product-r2-receipt.json")
FORMAT = "lisp65-block-2.6-card6-small-hardening-omission-dwx-r2-v1"
STATUS = "PASS: CARD-6 OMISSION PACKED PREFILTER AND BOOT CYCLES GREEN"
RED_STATUS = "PRODUCT RED: A13 RUNTIME-OVERLAY EDMA SOURCE ADDRESS MISENCODED"
MEDIA_STATUS = "PASS: CARD-6 OMISSION DWX PREFILTER MEDIUM READY"
MEDIA_FORMAT = "lisp65-block-2.6-card6-small-hardening-omission-dwx-medium-r2-v1"
SESSION_FORMAT = "lisp65-block-2.6-card6-small-hardening-omission-unused-device-session-v1"
LEDGER_ID = "block-2.6-card6-small-hardening-omission-packed-cold-boot"
BOOT_MANIFEST = TARGET / "final/runtime-overlays-boot-final.json"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
REFERENCE_RUN = BUILD / "runtime/run-card3-r2-boot-reference"
CANDIDATE_RUNS = (
    BUILD / "runtime/run-card6-r2-omission-boot",
    BUILD / "runtime/run-card6-r2-omission-boot-120s",
)


class PrefilterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PrefilterError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size, "sha256": sha256(path)}


def configure_card() -> None:
    # Propagate the omission world's values through the inherited Card-6 and
    # Card-3 adapters, then restore this outermost override once more.
    CARD.BASE.configure_stack()
    CARD.configure()
    CARD.BASE.configure_stack()
    CARD.configure()


class CardAdapter:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    REPORT = CARD.REPORT
    STATUS = CARD.STATUS
    READOBJ = CARD.BASE.READOBJ
    PREDECESSOR_ELF = CARD.BASE.PREDECESSOR_ELF
    CARD2 = CARD.BASE.PREV.CARD.CARD2

    @staticmethod
    def patch_card() -> None:
        configure_card()

    authority = staticmethod(CARD.authority)
    validate = staticmethod(CARD.validate)
    write_report = staticmethod(CARD.write_report)


class ProductCard:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    LINK = CardAdapter.CARD2.R2.CARD.BASE.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        configure_card()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        configure_card()
        return CardAdapter.CARD2.R2.CARD.BASE.CHAIN.setup_link_world()


class MediaAdapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = BASE.MediaPrice.RECEIPT
    PRICE = BASE.MediaPrice


def configure_base() -> None:
    configure_card()
    BASE.CARD = CardAdapter
    BASE.ProductCard = ProductCard
    BASE.Adapter = MediaAdapter
    for name, value in {
        "BUILD": BUILD, "MEDIA_BUILD": MEDIA_BUILD, "WPLTO": WPLTO,
        "STATIC": STATIC, "TARGET": TARGET, "SHARED": SHARED,
        "MEDIA_RECEIPT": MEDIA_RECEIPT, "SESSION": SESSION,
        "PREFILTER_RECEIPT": PREFILTER_RECEIPT, "REPORT": REPORT,
        "BASELINE_RECEIPT": CARD3_DWX_RECEIPT,
        "FORMAT": FORMAT, "STATUS": STATUS,
        "MEDIA_FORMAT": MEDIA_FORMAT, "MEDIA_STATUS": MEDIA_STATUS,
        "SESSION_FORMAT": SESSION_FORMAT,
    }.items():
        setattr(BASE, name, value)
    BOOT.BUILD = BUILD
    # BASE's adapter installation walks the inherited Card-3 stack. Reapply
    # the omission world's final overrides after that walk so validation does
    # not accidentally fall back to the predecessor status/authority.
    configure_card()


def accepted_pair() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    pair = {role: bind(path) for role, path in (
        ("PRG", CARD.PRG), ("ELF", CARD.ELF))}
    require(pair == {role: receipt["artifacts_after"][role] for role in pair},
            "Card-6 omission accepted pair drift")
    return pair


def _symbol(name: str) -> dict[str, int]:
    truth = CARD.BASE.ElfTruth.read(CARD.ELF, llvm_readobj=CARD.BASE.READOBJ)
    rows = [row for row in truth.symbols if row.name == name]
    require(len(rows) == 1, f"final ELF symbol population drift: {name}")
    return {"address": rows[0].value, "bytes": rows[0].bytes}


def _run_outputs(path: Path) -> dict[str, Any]:
    memory = path / "memory.bin"
    screen = path / "framebuffer.txt"
    log = path / "xemu.log"
    medium = path / "lisp65-product.d81"
    for artifact in (memory, screen, log, medium):
        require(artifact.is_file(), f"DWX red artifact absent: {artifact}")
    pcs = re.findall(r"CPU: Execution ended at PC=\$([0-9A-Fa-f]+)",
                     log.read_text(encoding="utf-8", errors="replace"))
    require(len(pcs) == 1, f"DWX final-PC population drift: {path.name}")
    return {"id": path.name, "final_PC": int(pcs[0], 16),
        "outputs": {"framebuffer_raw": bind(screen), "memory_raw": bind(memory),
            "log_non_authoritative": bind(log), "medium_readonly_copy": bind(medium)},
        "decoded_framebuffer": BOOT.ROWS.decoded_framebuffer(
            screen.read_text(encoding="utf-8", errors="replace"))}


def _descriptor(raw: bytes) -> dict[str, Any]:
    require(len(raw) == 20, "EDMA descriptor must contain exactly 20 bytes")
    return {"raw_hex": raw.hex(),
        "source_address": (raw[2] << 20) | (raw[13] << 16)
            | (raw[12] << 8) | raw[11],
        "target_address": (raw[4] << 20) | (raw[16] << 16)
            | (raw[15] << 8) | raw[14],
        "length": raw[9] | (raw[10] << 8), "command": raw[8]}


def _edma_copy_descriptor(source: int, target: int, length: int) -> bytes:
    return bytes((0x0b, 0x80, (source >> 20) & 0xff, 0x81,
        (target >> 20) & 0xff, 0x85, 1, 0, 0, length & 0xff,
        (length >> 8) & 0xff, source & 0xff, (source >> 8) & 0xff,
        (source >> 16) & 0x0f, target & 0xff, (target >> 8) & 0xff,
        (target >> 16) & 0x0f, 0, 0, 0))


def _final_trigger(function: dict[str, int]) -> dict[str, Any]:
    output = subprocess.run([str(OBJDUMP), "-d", "--no-show-raw-insn",
        str(CARD.ELF)], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout
    triggers = []
    for match in re.finditer(
            r"^\s*([0-9a-f]+):\s+sta\s+\$d705(?:\s|$)", output,
            flags=re.MULTILINE):
        address = int(match.group(1), 16)
        if function["address"] <= address < function["address"] + function["bytes"]:
            triggers.append(address)
    require(len(triggers) == 1,
            "runtime-overlay final-ELF DMA-trigger population drift")
    return {"function": "vm_runtime_overlay_exec_family",
        "function_address": function["address"],
        "function_bytes": function["bytes"], "trigger_instruction": "sta $d705",
        "trigger_PC": triggers[0], "post_trigger_PC": triggers[0] + 3,
        "decoder": bind(OBJDUMP)}


def _packed_summary() -> dict[str, Any]:
    value = load(MEDIA_RECEIPT)
    packed = value["packed_readback"]["absent_INIT"]
    medium = value["media"]["absent_INIT"]
    require(packed["status"] ==
            "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
        and packed["closure"]["object_count"] == 760
        and packed["closure"]["call_site_count"] == 2436
        and packed["generation_coherence"]["status"] ==
            "PASS: PACKED OBJECT GENERATION COHERENT"
        and bind(ROOT / medium["path"]) == {
            key: medium[key] for key in ("path", "bytes", "sha256")},
        "Card-6 packed medium closure/coherence drift")
    return {"status": packed["status"],
        "object_count": packed["closure"]["object_count"],
        "call_site_count": packed["closure"]["call_site_count"],
        "generation_status": packed["generation_coherence"]["status"],
        "mutations_rejected": packed["mutations_rejected"],
        "medium": {key: medium[key] for key in ("path", "bytes", "sha256")},
        "receipt": bind(MEDIA_RECEIPT)}


def runtime_red_evidence() -> dict[str, Any]:
    packed = _packed_summary()
    descriptor_symbol = _symbol("rtov_edma_job")
    function = _symbol("vm_runtime_overlay_exec_family")
    trigger = _final_trigger(function)
    reference = _run_outputs(REFERENCE_RUN)
    candidates = [_run_outputs(path) for path in CANDIDATE_RUNS]
    require("LISP65>" in reference["decoded_framebuffer"]
        and all("LISP65>" not in row["decoded_framebuffer"] for row in candidates),
        "Card-3 control / Card-6 red framebuffer discriminator drift")
    require(all(row["outputs"]["medium_readonly_copy"]["sha256"] ==
                packed["medium"]["sha256"] for row in candidates),
        "candidate red did not execute the packed Card-6 medium")
    baseline = load(CARD3_DWX_RECEIPT)["medium"]
    require(reference["outputs"]["medium_readonly_copy"]["sha256"] ==
            baseline["sha256"], "Card-3 control medium drift")

    raws = []
    for row, path in zip(candidates, CANDIDATE_RUNS):
        memory = (path / "memory.bin").read_bytes()
        start = descriptor_symbol["address"]
        raw = memory[start:start + descriptor_symbol["bytes"]]
        require(len(raw) == 20, "runtime descriptor capture is incomplete")
        raws.append(raw)
        row["raw_first_capture"] = {"address": start, "bytes": len(raw),
                                    "hex": raw.hex()}
    require(raws[0] == raws[1]
        and all(row["final_PC"] == trigger["post_trigger_PC"] for row in candidates),
        "Card-6 runtime-overlay boot red was not deterministic")

    observed = _descriptor(raws[0])
    manifest = load(BOOT_MANIFEST)
    matching = [row for row in manifest["slices"]
        if row["source_address"] & 0xffff == observed["source_address"] & 0xffff
        and row["file_size"] == observed["length"]]
    require(len(matching) == 1, "runtime descriptor has no unique packed slice")
    packed_slice = matching[0]
    target = manifest["policy"]["common_vma"]
    expected_raw = _edma_copy_descriptor(
        packed_slice["source_address"], target, packed_slice["file_size"])
    expected = _descriptor(expected_raw)
    changed = [index for index, pair in enumerate(zip(expected_raw, raws[0]))
               if pair[0] != pair[1]]
    require(changed == [2] and observed["source_address"] !=
            packed_slice["source_address"] and observed["target_address"] == target,
        "A13 runtime-overlay EDMA discriminator drift")

    source = packed_slice["source_address"]
    source_low = source & 0xffff
    encoded_high = ((source >> 16) & 0x0f) | ((source >> 12) & 0xff00)
    incorrect = (encoded_high << 16) | source_low
    require(_edma_copy_descriptor(incorrect, target, packed_slice["file_size"]) ==
            raws[0], "A13 packed-high-word recomposition does not explain raw bytes")
    old_raw = subprocess.run(["git", "show",
        "426a1788^:src/vm_runtime_overlay.c"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    old_text = old_raw.decode()
    live_text = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    require("rtov_edma_job[2] = (uint8_t)(source_high >> 8);" in old_text
        and "uint32_t source = ((uint32_t)source_high << 16) | source_low;" in live_text,
        "A13 source-seam attribution drift")
    return {"status": RED_STATUS, "packed_medium": packed,
        "control": {"status": "PASS: CARD-3 PACKED MEDIUM REACHES PROMPT",
            "medium": baseline, "run": reference},
        "candidate_runs": candidates,
        "final_ELF_execution_point": {"descriptor_symbol": descriptor_symbol,
            "trigger": trigger},
        "raw_first_descriptor": {"observed": observed, "expected": expected,
            "expected_raw_hex": expected_raw.hex(),
            "differing_byte_offsets": changed},
        "packed_slice_authority": {"manifest": bind(BOOT_MANIFEST),
            "name": packed_slice["name"], "source_address": source,
            "file_offset": packed_slice["file_offset"],
            "file_size": packed_slice["file_size"], "target_address": target},
        "causal_attribution": {
            "card_item": "A13 shared F018/EDMA descriptor construction seam",
            "packed_source_high": encoded_high, "source_low": source_low,
            "incorrect_ordinary_u32_recomposition": incorrect,
            "correct_physical_source_address": source,
            "mechanism": ("rtov_read_source receives source_high as the already-"
                "encoded EDMA megabyte/bank tuple; A13 treated it as an ordinary "
                "upper 16-bit word, so byte 2 became 0x20 instead of 0x82"),
            "predecessor_source": {"commit": "426a1788^",
                "path": "src/vm_runtime_overlay.c", "bytes": len(old_raw),
                "sha256": hashlib.sha256(old_raw).hexdigest()},
            "candidate_source": bind(ROOT / "src/vm_runtime_overlay.c"),
            "descriptor_builder": bind(ROOT / "src/mega65_dma_descriptor.h")},
        "gate_gap": ("the final-emission gate proved byte-store coverage and "
            "trigger ordering, but did not execute a runtime-overlay call and "
            "compare its descriptor values to the packed slice authority")}


def boot_rows(product: Path) -> dict[str, Any]:
    predecessor = load(CARD3_DWX_RECEIPT)
    baseline = ROOT / predecessor["medium"]["path"]
    require(bind(baseline) == predecessor["medium"],
            "Card-3 packed boot reference drift")
    before = BOOT.run_to_framebuffer("card3-r2-boot-reference", baseline,
                                      ["LISP65>"])
    after = BOOT.run_to_framebuffer("card6-r2-omission-boot", product,
                                     ["LISP65>"])
    old_cycles = before["emulated_CPU_DMA_cycles"]
    new_cycles = after["emulated_CPU_DMA_cycles"]
    require(old_cycles > 0 and new_cycles > 0, "boot cycle counter did not advance")
    return {"status": "PASS",
        "metric": "monotonic-emulated-CPU-and-DMA-cycles",
        "reference": before, "candidate": after,
        "delta_cycles": new_cycles - old_cycles,
        "ratio": new_cycles / old_cycles,
        "interpretation": ("packed Card-3 to Card-6 cold-boot comparison; "
            "DWX emulator observation only, not wall-clock or device timing")}


def ledger_entry(boot: dict[str, Any]) -> dict[str, Any]:
    return {"id": LEDGER_ID,
        "reference": boot["reference"]["medium"],
        "candidate": boot["candidate"]["medium"],
        "reference_cycles": boot["reference"]["emulated_CPU_DMA_cycles"],
        "candidate_cycles": boot["candidate"]["emulated_CPU_DMA_cycles"],
        "delta_cycles": boot["delta_cycles"], "ratio": boot["ratio"]}


def append_ledger(boot: dict[str, Any]) -> dict[str, Any]:
    value = load(BOOT_LEDGER)
    BOOT.validate_ledger_entry(value,
        load(BOOT.PREFILTER_RECEIPT)["boot_cycles"])
    require(LEDGER_ID not in {row["id"] for row in value["entries"]},
            "Card-6 boot-ledger row already exists")
    value["entries"].append(ledger_entry(boot))
    value["entries"].sort(key=lambda row: row["id"])
    BOOT_LEDGER.write_bytes(canonical(value))
    return value


def validate_ledger(value: dict[str, Any], boot: dict[str, Any]) -> None:
    BOOT.validate_ledger_entry(value,
        load(BOOT.PREFILTER_RECEIPT)["boot_cycles"])
    rows = [row for row in value["entries"] if row.get("id") == LEDGER_ID]
    require(rows == [ledger_entry(boot)]
            and len(value["entries"]) == len({row["id"] for row in value["entries"]}),
            "Card-6 boot-ledger entry is missing, stale or duplicated")


def gc_preservation(row: dict[str, Any]) -> dict[str, Any]:
    predecessor = load(CARD3_DWX_RECEIPT)["gc_cycle_wall"]
    reference = predecessor["candidate"]
    noise = predecessor["admitted_noise_cycles"]
    require(row["cycles"] <= reference["mean"] + noise,
            "Card-6 changed the forced-collection cycle wall")
    return {"status": "PASS",
        "metric": "gc_collect-entry-to-RTS-emulated-CPU-DMA-cycles",
        "reference_receipt": bind(CARD3_DWX_RECEIPT),
        "reference_mean_cycles": reference["mean"],
        "candidate_cycles": row["cycles"], "admitted_noise_cycles": noise,
        "ratio": row["cycles"] / reference["mean"],
        "candidate_run": row,
        "post_input_length_oracle": row["post_input_length_oracle"],
        "post_input_symbol_oracle": row["post_input_symbol_oracle"],
        "stopped_counters": row["stopped_counters"],
        "claim_limit": "DWX emulator only; no physical-device timing claim"}


def report(value: dict[str, Any]) -> str:
    boot = value["boot_cycles"]
    gc = value["forced_collection_and_print9"]
    packed = value["packed_readback"]
    return f"""# Block 2.6 Card 6 — omission-form packed DWX closure

Status: **{value['status']}**

The actually packed Card-6 D81 passes transitive closure and generation
coherence over its read-back bytes ({packed['closure']['object_count']} objects,
{packed['closure']['call_site_count']} calls). The same six-line forced-
collection choreography used by Card 3 finishes at framebuffer oracles `7`
and `(print 9) -> 9`, with stopped capture counters
`{gc['stopped_counters']}`. The measured collection is
**{gc['candidate_cycles']:,} emulated CPU/DMA cycles**, within the inherited
non-increase wall.

Cold boot over the same qualified three-patch Xemu, ROM, SD image and launch
choreography measures **{boot['reference']['emulated_CPU_DMA_cycles']:,} ->
{boot['candidate']['emulated_CPU_DMA_cycles']:,} cycles** (delta
{boot['delta_cycles']:+,}, ratio {boot['ratio']:.6f}). This is a DWX prefilter
observation, not wall-clock, physical-key or device evidence.

The frozen product pair was neither rebuilt nor relinked. The packed tail used
zero WPLTOs, zero product links and zero physical-device contacts. Card 6 and
Block 2.6 are review-ready.
"""


def red_report(value: dict[str, Any]) -> str:
    red = value["runtime_overlay_DMA_red"]
    raw = red["raw_first_descriptor"]
    source = red["packed_slice_authority"]
    trigger = red["final_ELF_execution_point"]["trigger"]
    return f"""# Block 2.6 Card 6 — omission-form packed DWX product red

Status: **{value['status']}**

The actually packed Card-6 D81 first passes transitive closure and generation
coherence ({red['packed_medium']['object_count']} objects,
{red['packed_medium']['call_site_count']} calls). The Card-3 control medium
reaches `LISP65>`, while two independent Card-6 boots stop deterministically
at `${trigger['post_trigger_PC']:04X}`, immediately after the final ELF's
`sta $d705` Enhanced-DMA trigger at `${trigger['trigger_PC']:04X}`. Neither
candidate boot reaches a prompt.

The raw 20-byte descriptor at `rtov_edma_job` is captured before
interpretation in both runs and is byte-identical:

    {raw['observed']['raw_hex']}

The packed boot manifest identifies that transfer uniquely as
`{source['name']}`: source `${source['source_address']:08X}`, target
`${source['target_address']:04X}`, length `${source['file_size']:04X}`. The
expected descriptor differs at exactly byte 2 (`82`, observed `20`). The
observed bytes decode source `${raw['observed']['source_address']:08X}`.

The cause is A13's shared descriptor seam. `rtov_read_source` receives
`source_high` as an already encoded EDMA megabyte/bank tuple (`$8200` here),
but the successor recomposes it as an ordinary upper 16-bit word. That creates
`$82004000`; the canonical builder then emits megabyte byte `$20` instead of
the physical packed-source byte `$82`. This is a source-semantic defect, not a
toolchain, packing, emulator-focus or timing discrepancy.

The earlier emitted-byte gate proved all descriptor stores and trigger
ordering, but not runtime descriptor-value equivalence. Its permanent successor
must execute each semantic descriptor family against its packed authority; a
store-complete descriptor with a wrong value must fall.

The pair remains **FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE**. The authorized one
WPLTO and one product link are consumed. One medium was built; one control and
two red DWX boots ran; boot-cycle and `(print 9)` qualification did not run;
physical-device contacts remain zero.
"""


def validate_red(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == RED_STATUS
        and value["accepted_pair"] == accepted_pair()
        and value["runtime_overlay_DMA_red"] == runtime_red_evidence()
        and value["disposition"] == "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
        and value["boot_cycles"]["status"] ==
            "NOT RUN: CANDIDATE FAILS BEFORE PROMPT"
        and value["forced_collection_and_print9"]["status"] ==
            "NOT RUN: CANDIDATE FAILS BEFORE PROMPT"
        and value["attempt_accounting"] == {"WPLTO_runs": 0,
            "product_links": 0, "candidate_media_builds": 1,
            "DWX_control_runs": 1, "DWX_product_red_runs": 2,
            "device_contacts": 0},
        "Card-6 omission packed-DWX product-red receipt drift")


def seal_red() -> None:
    configure_base()
    require(not PREFILTER_RECEIPT.exists() and not REPORT.exists()
        and BUILD.exists() and MEDIA_RECEIPT.exists(),
        "Card-6 omission DWX red-seal boundary drift")
    product_receipt = load(CARD.RECEIPT)
    require(product_receipt["review_ready"] is False
        and product_receipt["final_product"]["packed_prefilter"]["status"] ==
            "PENDING"
        and product_receipt["final_product"]["boot_cycles"]["status"] ==
            "PENDING",
        "Card-6 omission product is not at its packed-tail boundary")
    red = runtime_red_evidence()
    value = {"format": FORMAT, "recorded_on": "2026-09-04",
        "status": RED_STATUS, "authority": CARD.authority(),
        "accepted_pair": accepted_pair(),
        "runtime_overlay_DMA_red": red,
        "boot_cycles": {"status": "NOT RUN: CANDIDATE FAILS BEFORE PROMPT"},
        "forced_collection_and_print9": {
            "status": "NOT RUN: CANDIDATE FAILS BEFORE PROMPT"},
        "disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "candidate_media_builds": 1, "DWX_control_runs": 1,
            "DWX_product_red_runs": 2, "device_contacts": 0},
        "claim_limit": ("packed-DWX product-red evidence; no boot-cycle, "
            "forced-collection, physical-device or qualified-successor claim")}
    PREFILTER_RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(red_report(value), encoding="utf-8")
    validate_red(value)

    product_receipt["final_product"]["packed_prefilter"] = {
        "status": "RED: A13 RUNTIME-OVERLAY EDMA SOURCE ADDRESS MISENCODED",
        "receipt": bind(PREFILTER_RECEIPT),
        "medium": red["packed_medium"]["medium"],
        "closure_and_generation_coherence": True}
    product_receipt["final_product"]["boot_cycles"] = {
        "status": "NOT RUN: CANDIDATE FAILS BEFORE PROMPT",
        "receipt": bind(PREFILTER_RECEIPT)}
    product_receipt["final_product"]["gc_cycle_wall"] = {
        "status": "NOT RUN: CANDIDATE FAILS BEFORE PROMPT",
        "receipt": bind(PREFILTER_RECEIPT)}
    product_receipt["attempt_accounting"]["DWX_prefilter_runs"] = 3
    product_receipt["attempt_accounting"]["media_builds"] = 1
    product_receipt["review_ready"] = False
    product_receipt["disposition"] = "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
    product_receipt["qualification_red"] = bind(PREFILTER_RECEIPT)
    CARD.RECEIPT.write_bytes(canonical(product_receipt))
    CARD.write_report(product_receipt)
    product_report = CARD.REPORT.read_text(encoding="utf-8").replace(
        f"Status: **{CARD.STATUS}**; packed DWX tail **pending**.",
        "Status: **FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE**; packed DWX product red.",
        1)
    product_report = product_report.replace(
        "zero unexplained members. The emitted nine-user DMA trigger population is\n"
        "byte-equivalent after relocation operands are normalized, and the clobber-drop\n"
        "mutation remains sharp.",
        "zero unexplained members. The static nine-user DMA store/trigger population\n"
        "and clobber-drop mutation are green, but the packed DWX execution proves that\n"
        "store coverage is not runtime descriptor-value equivalence.")
    product_report += ("\nThe packed DWX tail deterministically established "
        "an A13 product defect: `rtov_read_source` converts an encoded EDMA "
        "source tuple as an ordinary upper word, producing byte `$20` instead "
        "of `$82` for the resident-Island installer. The pair is frozen "
        "unqualified evidence; boot-cycle and `(print 9)` rows did not run.\n")
    CARD.REPORT.write_text(product_report, encoding="utf-8")
    CARD.validate(product_receipt, require_dwx=False)
    print("Block 2.6 Card 6: PRODUCT RED A13 EDMA source tuple; device=0")


def validate(value: dict[str, Any]) -> None:
    packed = value["packed_readback"]
    gc = value["forced_collection_and_print9"]
    boot = value["boot_cycles"]
    require(value["format"] == FORMAT and value["status"] == STATUS
        and value["accepted_pair"] == accepted_pair()
        and packed["status"] ==
            "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
        and packed["closure"]["object_count"] == 760
        and packed["closure"]["call_site_count"] == 2436
        and gc["status"] == "PASS"
        and gc["post_input_length_oracle"] == 7
        and gc["post_input_symbol_oracle"] == 9
        and gc["stopped_counters"] == "88888888"
        and boot["status"] == "PASS" and boot["ratio"] > 0
        and value["attempt_accounting"] == {"WPLTO_runs": 0,
            "product_links": 0, "candidate_media_builds": 1,
            "DWX_prefilter_runs": 3, "device_contacts": 0},
        "Card-6 omission packed DWX receipt drift")
    validate_ledger(load(BOOT_LEDGER), boot)


def write() -> None:
    configure_base()
    require(not PREFILTER_RECEIPT.exists() and not REPORT.exists()
            and not BUILD.exists(), "Card-6 omission DWX close is one-shot")
    product_receipt = load(CARD.RECEIPT)
    require(product_receipt["review_ready"] is False
        and product_receipt["final_product"]["packed_prefilter"]["status"] ==
            "PENDING"
        and product_receipt["final_product"]["boot_cycles"]["status"] == "PENDING",
        "Card-6 omission product is not at its packed-tail boundary")
    tool = BASE.tool_identity()
    product, packed = BASE.build_medium()
    boot = boot_rows(product)
    forced = BASE.measure_one("card6-r2-forced-collection", product, CARD.ELF)
    gc = gc_preservation(forced)
    append_ledger(boot)
    value = {"format": FORMAT, "recorded_on": "2026-09-04",
        "status": STATUS, "authority": CARD.authority(),
        "accepted_pair": accepted_pair(), "medium_receipt": bind(MEDIA_RECEIPT),
        "medium": bind(product), "packed_readback": packed,
        "boot_cycles": boot, "forced_collection_and_print9": gc,
        "boot_phase_ledger": bind(BOOT_LEDGER), "tool_identity": tool,
        "blind_spot_contract": bind(BASE.BLIND_CONTRACT),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "candidate_media_builds": 1, "DWX_prefilter_runs": 3,
            "device_contacts": 0}}
    PREFILTER_RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)

    product_receipt["final_product"]["packed_prefilter"] = {
        "status": "PASS", "receipt": bind(PREFILTER_RECEIPT),
        "medium": bind(product), "closure_and_generation_coherence": True,
        "framebuffer_oracles": [7, 9], "stopped_counters": "88888888"}
    product_receipt["final_product"]["boot_cycles"] = {
        "status": "PASS", "receipt": bind(PREFILTER_RECEIPT),
        "ledger": bind(BOOT_LEDGER),
        "reference_cycles": boot["reference"]["emulated_CPU_DMA_cycles"],
        "candidate_cycles": boot["candidate"]["emulated_CPU_DMA_cycles"],
        "delta_cycles": boot["delta_cycles"], "ratio": boot["ratio"]}
    product_receipt["final_product"]["gc_cycle_wall"] = {
        "status": "PASS", "receipt": bind(PREFILTER_RECEIPT),
        "reference_mean_cycles": gc["reference_mean_cycles"],
        "candidate_mean_cycles": gc["candidate_cycles"],
        "delta_mean_cycles": gc["candidate_cycles"] -
            gc["reference_mean_cycles"],
        "admitted_noise_cycles": gc["admitted_noise_cycles"],
        "ratio": gc["ratio"]}
    product_receipt["attempt_accounting"]["DWX_prefilter_runs"] = 3
    product_receipt["attempt_accounting"]["media_builds"] = 1
    product_receipt["review_ready"] = True
    CARD.RECEIPT.write_bytes(canonical(product_receipt))
    CARD.write_report(product_receipt)
    CARD.validate(product_receipt)
    print("Block 2.6 Card 6: PACKED DWX PASS boot=measured print9=9 device=0")


def check() -> None:
    configure_base()
    value = load(PREFILTER_RECEIPT)
    if value["status"] == RED_STATUS:
        validate_red(value)
        product = load(CARD.RECEIPT)
        require(product["disposition"] ==
                    "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"
            and product["qualification_red"] == bind(PREFILTER_RECEIPT)
            and REPORT.read_text(encoding="utf-8") == red_report(value),
            "Card-6 omission product-red closure drift")
        CARD.validate(product, require_dwx=False)
        print("Block 2.6 Card 6: PACKED DWX PRODUCT-RED CHECK PASS device=0")
        return
    validate(value)
    product = load(CARD.RECEIPT)
    require(product["review_ready"] is True
        and product["final_product"]["packed_prefilter"]["status"] == "PASS"
        and product["final_product"]["boot_cycles"]["status"] == "PASS"
        and product["final_product"]["gc_cycle_wall"]["status"] == "PASS"
        and REPORT.read_text(encoding="utf-8") == report(value),
        "Card-6 product did not consume packed DWX closure")
    CARD.validate(product)
    print("Block 2.6 Card 6: PACKED DWX CHECK PASS device=0")


def selftest() -> None:
    configure_base()
    value = load(PREFILTER_RECEIPT)
    if value["status"] == RED_STATUS:
        cases: dict[str, Callable[[dict[str, Any]], None]] = {
            "descriptor-difference-hidden": lambda row: row[
                "runtime_overlay_DMA_red"]["raw_first_descriptor"].update(
                    differing_byte_offsets=[]),
            "second-reproduction-hidden": lambda row: row[
                "runtime_overlay_DMA_red"].update(candidate_runs=row[
                    "runtime_overlay_DMA_red"]["candidate_runs"][:1]),
            "pair-promoted": lambda row: row.update(disposition="CANDIDATE"),
            "boot-cycle-claimed": lambda row: row["boot_cycles"].update(
                status="PASS"),
            "device-contact-hidden": lambda row: row[
                "attempt_accounting"].update(device_contacts=1),
        }
        rejected = []
        for label, mutate in cases.items():
            trial = deepcopy(value); mutate(trial)
            try:
                validate_red(trial)
            except (PrefilterError, RuntimeError, KeyError, ValueError):
                rejected.append(label)
        require(rejected == list(cases),
                "Card-6 omission product-red mutation survived")
        print(f"Block 2.6 Card 6: PRODUCT-RED SELFTEST mutations={len(rejected)}")
        return
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "packed-closure-hidden": lambda row: row["packed_readback"].update(
            status="RED"),
        "print9-hidden": lambda row: row["forced_collection_and_print9"].update(
            post_input_symbol_oracle=0),
        "capture-loss-hidden": lambda row: row[
            "forced_collection_and_print9"].update(stopped_counters="88888800"),
        "boot-measurement-hidden": lambda row: row["boot_cycles"].update(
            status="PENDING"),
        "device-contact-hidden": lambda row: row["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected = []
    for label, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PrefilterError, RuntimeError, KeyError, ValueError):
            rejected.append(label)
    ledger_mutant = deepcopy(load(BOOT_LEDGER))
    ledger_mutant["entries"] = [row for row in ledger_mutant["entries"]
        if row.get("id") != LEDGER_ID]
    try:
        validate_ledger(ledger_mutant, value["boot_cycles"])
    except (PrefilterError, RuntimeError, KeyError, ValueError):
        rejected.append("boot-ledger-entry-omitted")
    require(rejected == [*cases, "boot-ledger-entry-omitted"],
            "Card-6 omission DWX mutation survived")
    print(f"Block 2.6 Card 6: PACKED DWX SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "seal-red", "check", "selftest"))
    {"write": write, "seal-red": seal_red, "check": check,
        "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block 2.6 Card 6 omission DWX: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
