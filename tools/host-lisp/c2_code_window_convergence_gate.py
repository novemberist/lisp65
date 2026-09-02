#!/usr/bin/env python3
"""Permanent independent-oracle gate for streamed VM code windows."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from evidence_era import stable_recorded_on


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-code-window-convergence-contract.json"
VM = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
EMBED = ROOT / "src/vm_embed.c"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SHIP_H = ROOT / "src/ship_runtime_io.h"
SHIP_MAIN = ROOT / "products/runtime-core/main.c"
HOST = ROOT / "scripts/ship-runtime-host-main.c"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
C2_DMA = ROOT / "src/c2_platform_dma.c"
C2_DMA_H = ROOT / "src/c2_platform_dma.h"
C2_RUNTIME = ROOT / "src/c2_product_runtime.c"
MEM = ROOT / "src/mem.c"
C2_LINK = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    value = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def converge(source: bytes, stale: bytes, *, primary_after: int | None,
             start: int = 0,
             timeout: int = 64) -> tuple[bool, int]:
    require(len(source) == len(stale) and len(source) > 0,
            "invalid model window")
    destination = bytearray(stale)
    first = next((i for i in range(len(source))
                  if source[i] != destination[i]), len(source))
    if first == len(source):
        return True, 0
    elapsed = 0
    while True:
        if primary_after is not None and elapsed >= primary_after:
            destination[:] = source
        if destination[first] == source[first]:
            return True, elapsed
        if elapsed >= timeout:
            return False, elapsed
        elapsed = (elapsed + 1) & 0xffff
        # `start` exists to exercise modulo-frame arithmetic explicitly.
        _frame = (start + elapsed) & 0xffff
        require(((_frame - start) & 0xffff) == elapsed,
                "model frame arithmetic drift")


def validate(contract: dict[str, Any], vm: str, vm_h: str, embed: str,
             ship_io: str, ship_h: str, ship_main: str, host: str,
             builder: str, c2_dma: str, c2_dma_h: str, c2_runtime: str,
             mem: str, c2_link: str) -> None:
    require(
        contract["format"] == "lisp65-c2-code-window-content-convergence-v1"
        and contract["status"] == "owner-commissioned-permanent-gate"
        and contract["timeout_frames"] == 64
        and contract["model_cases"] == 8
        and contract["mutation_cases"] == 15,
        "code-window convergence contract identity drift",
    )
    oracle = contract["content_oracle"]
    form = contract["structural_form"]
    require("first-difference" in oracle["source"]
            and "first unequal source byte" in oracle["initialization"]
            and "exactly once" in oracle["resubmission"]
            and form["primitive_count_per_product"] == 1
            and form["per_consumer_convergence_loops"] == 0
            and form["resident_destination_witness_bytes"] == 1
            and form["exhaustive_oracle_location"]
            == "host and device class gates",
            "independent content oracle drift")

    for token in (
        "#define VM_CODE_CONVERGENCE_TIMEOUT_FRAMES 64u",
        "unsigned char vm_dma_verify_list[24]",
        "static volatile uint8_t vm_code_verify;",
        "static volatile uint8_t vm_code_verify_done;",
        "vm_code_verify_done = (uint8_t)~vm_code_verify_marker;",
        "while (vm_code_verify_done != vm_code_verify_marker)",
        "vm_dma_source_byte(bank, (uint16_t)(off + i), &expected)",
        "if (observed[i] != expected) break;",
        "while (observed[i] != expected)",
        "if (i == len) return 1u;",
        ">= VM_CODE_CONVERGENCE_TIMEOUT_FRAMES",
        "return 0u;",
        "sta $d700",
    ):
        require(token in embed, f"target convergence token drift: {token}")
    require(embed.count(
                "vm_dma_source_byte(bank, (uint16_t)(off + i), &expected)") == 1
            and embed.count("vm_code_load(bank, off, len, dst);") == 1,
            "shared discriminator or one primary submission drift")
    match = embed.index("if (i == len) return 1u;")
    timeout = embed.index(">= VM_CODE_CONVERGENCE_TIMEOUT_FRAMES", match)
    require(match < timeout, "timeout is checked before exact-edge content")

    require("uint8_t vm_code_load_converged" in vm_h
            and "return vm_code_load_converged(" in vm,
            "VM object seam does not consume the convergence result")
    require(vm.count("if (!vm_object_load(") == 4
            and vm.count("vm_object_load(") == 5,
            "not every VM object/header/window refill uses the common seam")
    require(vm.count("vm_status = VM_BADOPCODE; goto done;") >= 8,
            "nonconvergent object load does not fail closed")
    require("RUNTIME_VM_ERROR = 0xe3" in ship_main
            and "lisp65_runtime_state = RUNTIME_VM_ERROR" in ship_main,
            "Ship VM failure publication drift")

    require("uint16_t lisp65_ship_io_frame_count(void);" in ship_h
            and ship_io.count("lisp65_ship_io_frame_count(void)") == 2,
            "Ship advancing-frame interface drift")
    require("uint8_t vm_code_load_converged" in host
            and "dst[first] == ext_code[(uint16_t)(off + first)]" in host,
            "host execution does not cross the converged VM seam")
    require(builder.count('"-DLISP65_CODE_WINDOW_CONVERGENCE"') == 2,
            "host and target Ship builds do not bind the same convergence seam")
    for token in (
        "uint8_t c2_dma_verify_list[24]",
        "volatile uint8_t c2_dma_verify",
        "volatile uint8_t LISP65_C2_ZP c2_dma_verify_done",
        "LISP65_C2_CONVERGENCE_STATE(\"d700_jobs\")",
        "LISP65_C2_CONVERGENCE_ZP(\"d700_done\")",
        "c2_dma_verify_done = (uint8_t)~c2_dma_verify_marker;",
        "while (c2_dma_verify_done != c2_dma_verify_marker)",
        "c2_dma_source_byte(bank, (uint16_t)(offset + i), &expected)",
        "if (observed[i] != expected) break;",
        "while (observed[i] != expected)",
        ">= C2_DMA_CONTENT_TIMEOUT_FRAMES",
        "sta $d700",
    ):
        require(token in c2_dma,
                f"C2 target convergence token drift: {token}")
    require(c2_dma.count(
                "c2_dma_source_byte(bank, (uint16_t)(offset + i), &expected)") == 1
            and c2_dma.count("vm_code_load(bank, offset, length, destination);") == 1
            and '#include "c2_platform_dma.h"' in c2_dma
            and "#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u" in c2_dma_h,
            "C2 discriminator is absent, primary-resubmitted, unbounded or undeclared")
    require("c2_edma_probe_jobs[40]" in c2_runtime
            and "LISP65_C2_CONVERGENCE_STATE(\"d705_jobs\")"
                in c2_runtime
            and "LISP65_C2_CONVERGENCE_ZP(\"d705_done\")"
                in c2_runtime
            and "while (c2_edma_probe_done != c2_edma_probe_marker)"
                in c2_runtime
            and "c2_physical_source_byte(source + i, &expected)" in c2_runtime
            and c2_runtime.count("uint8_t C2_PHYSICAL_READ_CONVERGED_IMPL(")
                == 1
            and "return vm_code_load_converged(" in c2_runtime
            and "while (length)" not in c2_runtime[
                c2_runtime.index("C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read"):
                c2_runtime.index("C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write")]
            and mem.count("vm_code_load_converged(") == 1,
            "consumers did not route through the compact owned primitives")
    require('def ownership_scope_selected(' in c2_link
            and ('ownership_opt_in=ownership_scope_selected('
                 'probe_definitions)') in c2_link
            and 'if not ownership_scope_selected(extra_definitions):'
                in c2_link
            and 'return FULL_MAP_OWNERSHIP or CONVERGENCE_FEATURE in '
                'extra_definitions' in c2_link
            and 'CONVERGENCE_FEATURE = "LISP65_CODE_WINDOW_CONVERGENCE"'
                in c2_link
            and 'src/c2_mapped_far_service.s' in c2_link
            and 'src/c2_mapped_far_convergence.s' in c2_link
            and '"LISP65_C2_ASM_CONVERGENCE"' in c2_link
            and '__lisp65_c2_mapped_far_required_param=1' in c2_link,
            "C2-lite product does not bind the owned convergence seam")


def run_cases(timeout: int) -> dict[str, dict[str, Any]]:
    source = bytes([0x3b, 0x06, 0x01, 0x01, 0x2f, 0x01, 0x53])
    stale = bytes([0x0b, 0x00, 0x01, 0x01, 0x2f, 0x01, 0x53])
    specs = {
        "immediate": (source, stale, 0, 0, True, 0),
        "primary-late-35": (source, stale, 35, 0, True, 35),
        "exact-edge-64": (source, stale, 64, 0, True, 64),
        "nonconvergent": (source, stale, None, 0, False, 64),
        "uint16-wrap": (source, stale, 35, 0xfff0, True, 35),
        "destination-already-source": (source, source, None, 0, True, 0),
        "first-difference-at-tail": (
            source, source[:-1] + bytes([source[-1] ^ 0xff]), 9, 0, True, 9),
        "one-byte": (source[:1], stale[:1], 3, 0, True, 3),
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, (case_source, initial, primary, start, accepted, at) in specs.items():
        result, elapsed = converge(
            case_source, initial, primary_after=primary,
            start=start, timeout=timeout)
        require((result, elapsed) == (accepted, at),
                f"model case failed: {name} -> {(result, elapsed)}")
        rows[name] = {"accepted": result, "elapsed_frames": elapsed}
    return rows


def audit_facts(facts: dict[str, Any]) -> None:
    require(facts["timeout_frames"] == 64, "timeout drift")
    require(facts["oracle"] == "source-derived-first-difference",
            "metadata accepted as content truth")
    require(facts["descriptor_count"] == 3,
            "ordered source-probe chain or primary descriptor lost")
    require(facts["resident_destination_witness_bytes"] == 1,
            "resident discriminator is no longer one byte")
    require(facts["primary_submissions"] == 1,
            "silent primary retry introduced")
    require(facts["match_before_timeout"] is True,
            "exact-edge convergence rejected")
    require(facts["refill_paths"] == 4, "refill path coverage drift")
    require(facts["host_target_define_count"] == 2,
            "host/target build parity drift")
    require(facts["target_products"] == 2,
            "one target product silently lost convergence")
    require(facts["per_consumer_convergence_loops"] == 0,
            "per-consumer convergence infrastructure returned")
    require(facts["d705_probe_descriptor_bytes"] == 40
            and facts["d705_probe_descriptor_named_owner"] is True,
            "D705 source-probe chain has no named owner")
    require(facts["fail_closed"] == "VM_BADOPCODE->RUNTIME_VM_ERROR",
            "nonconvergence is no longer fail closed")
    require(facts["completion_metadata_consumed"] is False,
            "refill metadata consumed as content truth")
    require(facts["product_link_built"] is False,
            "source gate overclaims a product link")
    require(facts["hardware_contacts"] == 0,
            "source gate overclaims hardware")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases = {
        "timeout": ("timeout_frames", 63),
        "metadata-oracle": ("oracle", "refill-completion-flag"),
        "shared-descriptor": ("descriptor_count", 2),
        "wide-resident-witness": ("resident_destination_witness_bytes", 56),
        "silent-resubmit": ("primary_submissions", 2),
        "timeout-first": ("match_before_timeout", False),
        "drop-refill-path": ("refill_paths", 3),
        "host-only": ("host_target_define_count", 1),
        "not-fail-closed": ("fail_closed", "retry-forever"),
        "consume-metadata": ("completion_metadata_consumed", True),
        "claim-link": ("product_link_built", True),
        "claim-hardware": ("hardware_contacts", 1),
        "drop-c2-product": ("target_products", 1),
        "per-consumer-loops": ("per_consumer_convergence_loops", 1),
        "unowned-d705-descriptor": ("d705_probe_descriptor_named_owner", False),
    }
    rejected: dict[str, str] = {}
    for name, (key, value) in cases.items():
        candidate = deepcopy(facts)
        candidate[key] = value
        try:
            audit_facts(candidate)
        except GateError as error:
            rejected[name] = str(error)
        else:
            raise GateError(f"mutation survived: {name}")
    return rejected


def main() -> int:
    try:
        contract = load(CONTRACT)
        texts = [path.read_text(encoding="utf-8") for path in (
            VM, VM_H, EMBED, SHIP_IO, SHIP_H, SHIP_MAIN, HOST, BUILDER,
            C2_DMA, C2_DMA_H, C2_RUNTIME, MEM, C2_LINK)]
        validate(contract, *texts)
        cases = run_cases(contract["timeout_frames"])
        facts = {
            "timeout_frames": 64,
            "oracle": "source-derived-first-difference",
            "descriptor_count": 3,
            "resident_destination_witness_bytes": 1,
            "primary_submissions": 1,
            "match_before_timeout": True,
            "refill_paths": 4,
            "host_target_define_count": 2,
            "target_products": 2,
            "per_consumer_convergence_loops": 0,
            "d705_probe_descriptor_bytes": 40,
            "d705_probe_descriptor_named_owner": True,
            "fail_closed": "VM_BADOPCODE->RUNTIME_VM_ERROR",
            "completion_metadata_consumed": False,
            "product_link_built": False,
            "hardware_contacts": 0,
        }
        audit_facts(facts)
        rejected = mutations(facts)
        require(len(cases) == contract["model_cases"]
                and len(rejected) == contract["mutation_cases"],
                "execution witness count drift")
        receipt = {
            "format": "lisp65-c2-code-window-content-convergence-gate-v1",
            "recorded_on": stable_recorded_on(RECEIPT),
            "status": "PASS",
            "authorities": {path.name: bind(path) for path in (
                CONTRACT, VM, VM_H, EMBED, SHIP_IO, SHIP_H, SHIP_MAIN,
                HOST, BUILDER, C2_DMA, C2_DMA_H, C2_RUNTIME, MEM, C2_LINK,
                Path(__file__).resolve())},
            "facts": facts,
            "executions": cases,
            "execution_witness": len(cases),
            "mutations_rejected": rejected,
            "claim_limit": contract["claim_limit"],
        }
        write(RECEIPT, receipt)
        print("c2-code-window-convergence-gate: PASS "
              f"executions={len(cases)} mutations={len(rejected)} "
              "refills=4 products=2 timeout=64 witness=1 routing=shared")
        return 0
    except (GateError, OSError, ValueError, KeyError) as error:
        print(f"c2-code-window-convergence-gate: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
