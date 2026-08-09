#!/usr/bin/env python3
"""Attribute the Link-90 streamed-window refill fix form from bound evidence.

This is deliberately a host/ELF-only attribution.  It binds the ordinary
Link-90 Ship Runtime, the contact-8 device witness and the emitted bytecode
object.  It does not build, patch, link or contact a device.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ELF = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/"
    "parity-toy.runtime.elf"
)
IMAGE = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/parity-toy.d81"
)
SHIP_RECEIPT = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/"
    "parity-toy.receipt.json"
)
CONFIG = ROOT / "config/c2-v14-link90-opcode-view-witness.json"
CONTACT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-link90-opcode-view-witness-device-receipt.json"
)
MANIFEST = ROOT / (
    "build/post-promotion/v14/parity-toy-link90-artifact/"
    "stdlib-p0.manifest.json"
)
EXT = ROOT / (
    "build/post-promotion/v14/parity-toy-link90-artifact/stdlib-p0.ext.bin"
)
DISASM = ROOT / (
    "build/post-promotion/v14/parity-toy-link90-artifact/"
    "stdlib-p0.disasm.txt"
)
VM = ROOT / "src/vm.c"
VM_EMBED = ROOT / "src/vm_embed.c"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
DRIVER = Path(__file__).resolve()
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-link90-refill-fix-form-host-elf-attribution.json"
)


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    value = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def bytes_at(truth: ElfTruth, address: int, length: int) -> bytes:
    section = truth.section(".text")
    start = address - section.address
    value = truth.section_bytes(".text")[start:start + length]
    require(start >= 0 and len(value) == length,
            f"linked text address outside .text: 0x{address:04x}")
    return value


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    value = truth.section_bytes(symbol.section)[start:start + symbol.bytes]
    require(symbol.bytes > 0 and len(value) == symbol.bytes,
            f"invalid linked symbol body: {name}")
    return symbol, value


def audit(facts: dict[str, Any]) -> None:
    observed = facts["device_observation"]
    require(observed["cursor"] == "0x0024"
            and observed["owner"] == "5:0x06e1"
            and observed["window_base"] == "0x0024"
            and observed["fetched_byte"] == "0x0b"
            and observed["expected_byte"] == "0x3b",
            "contact-8 opcode-view authority drift")
    require(observed["fetched_byte_is_initial_destination_byte"] is True,
            "stale initial payload identity drift")

    artifact = facts["artifact"]
    require(artifact == {
        "object": "m65-sprite-shape",
        "bank": 5,
        "object_offset": "0x06e1",
        "object_bytes": 140,
        "header_bytes": 21,
        "payload_bytes": 119,
        "code_buffer_bytes": 56,
        "payload_window_bytes": 35,
        "initial_source": "5:0x06f6",
        "refill_cursor": "0x0024",
        "refill_relative": "0x0039",
        "refill_source": "5:0x071a",
        "refill_destination": "0:0x8a1e",
        "refill_bytes": 35,
        "initial_payload_byte": "0x0b",
        "refill_payload_byte": "0x3b",
    }, "emitted object/refill geometry drift")

    linked = facts["linked_path"]
    require(linked["runtime_elf_sha256"]
            == "dcb415da6379d0fc68185a4a486ab07a72442524bbefbca0fc7b3cffda8e841f"
            and linked["refill_call"] == "0x3bdc -> vm_code_load@0x720a"
            and linked["transport"] == "normal-F018B-D700"
            and linked["job_list"] == "0x0076+12"
            and linked["job_bytes_for_observed_refill"]
            == [0, 35, 0, 26, 7, 5, 30, 138, 0, 0, 0, 0],
            "linked refill/descriptor identity drift")
    require(linked["software_source_equation"]
            == "0x06e1 + 0x0015 + 0x0024 = 0x071a"
            and linked["software_destination_equation"]
            == "0x8a09 + 0x0015 = 0x8a1e",
            "linked source/destination dataflow drift")
    require(linked["unconditional_D700_submit_before_return"] is True
            and linked["return_immediately_after_submit"] is True
            and linked["destination_readback_before_dispatch"] is False
            and linked["independent_content_oracle"] is False,
            "linked completion boundary drift")

    forms = facts["fix_form_attribution"]
    require(forms["missing_software_submit"] == "eliminated"
            and forms["wrong_software_source_offset"] == "eliminated"
            and forms["selected"]
            == "D700-submission-is-treated-as-content-completion"
            and forms["required_fix_form"]
            == "content-defined-streamed-window-convergence",
            "fix-form classification drift")
    require(forms["delivery_eventually_lands"] == "not-measured"
            and forms["DMA_engine_consumed_descriptor_exactly"] == "not-measured",
            "target timing or engine behavior was overclaimed")
    require(forms["family"]
            == "L10-DMA-visibility-contract-class; distinct-D700-transport",
            "DMA visibility family boundary drift")

    scope = facts["scope"]
    require(scope == {
        "host_elf_only": True,
        "hardware_contacts": 0,
        "product_candidate_bytes_changed": 0,
        "product_fixes": 0,
        "product_links": 0,
        "link_91_built": False,
    }, "attribution scope drift")


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "erase-stale-byte-identity": (
            ["device_observation", "fetched_byte_is_initial_destination_byte"],
            False),
        "move-source-offset": (["artifact", "refill_source"], "5:0x06f6"),
        "move-destination": (["artifact", "refill_destination"], "0:0x8a09"),
        "drop-submit": (["linked_path", "unconditional_D700_submit_before_return"],
                        False),
        "invent-readback": (["linked_path", "destination_readback_before_dispatch"],
                            True),
        "invent-content-oracle": (["linked_path", "independent_content_oracle"],
                                  True),
        "select-wrong-offset": (["fix_form_attribution", "wrong_software_source_offset"],
                                "selected"),
        "claim-eventual-delivery": (["fix_form_attribution", "delivery_eventually_lands"],
                                    "yes"),
        "claim-identical-L10-transport": (["fix_form_attribution", "family"],
                                         "identical-L10-D705-transport"),
        "claim-product-fix": (["scope", "product_fixes"], 1),
        "claim-link91": (["scope", "link_91_built"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, value) in cases.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        try:
            audit(candidate)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"attribution mutation survived: {name}")
    return rejected


def main() -> int:
    try:
        config = load(CONFIG)
        contact = load(CONTACT)
        manifest = load(MANIFEST)
        ship_receipt = load(SHIP_RECEIPT)
        owner = " ".join(OWNER.read_text(encoding="utf-8").split())
        vm = VM.read_text(encoding="utf-8")
        vm_embed = VM_EMBED.read_text(encoding="utf-8")
        ext = EXT.read_bytes()

        require(contact["status"] == "ATTRIBUTED-WRONG-POST-REFILL-OPCODE"
                and contact["device"]["witness_bytes"]
                == [161, 178, 36, 0, 11, 5, 225, 6, 36, 0],
                "contact-8 device authority drift")
        require(contact["candidate_unchanged"]["runtime_elf"]["sha256"]
                == config["reference_runtime_elf_sha256"],
                "contact-8 Runtime identity drift")
        require(bind(IMAGE)["sha256"] == config["reference_image_sha256"]
                and bind(ELF)["sha256"]
                == config["reference_runtime_elf_sha256"],
                "Link-90 candidate identity drift")
        require(ship_receipt["runtime_audit"]["elf_sha256"]
                == config["reference_runtime_elf_sha256"],
                "Ship receipt Runtime identity drift")
        for token in ("fix-form attribution", "missing overwrite",
                      "late overwrite", "wrong source offset",
                      "independent content oracle", "no device"):
            require(token.lower() in owner.lower(),
                    f"owner commission text absent: {token}")

        shape = next(row for row in manifest["entries"]
                     if row["name"] == "m65-sprite-shape")
        object_offset = int(shape["ext_addr"], 16) & 0xffff
        nlits = ext[object_offset + 6]
        header_bytes = 7 + 2 * nlits
        payload_bytes = ext[object_offset + 4] | (
            ext[object_offset + 5] << 8)
        cursor = config["expected_cursor"]
        code_buffer_bytes = 56
        window_bytes = code_buffer_bytes - header_bytes
        initial_source = object_offset + header_bytes
        refill_relative = header_bytes + cursor
        refill_source = object_offset + refill_relative
        require(shape["length"] == header_bytes + payload_bytes == 140
                and shape["lit_count"] == nlits == 7,
                "shape object geometry drift")
        require(ext[initial_source] == 0x0b
                and ext[refill_source] == 0x3b,
                "initial/refill opcode identity drift")
        require("0024 DROP" in DISASM.read_text(encoding="utf-8"),
                "bound artifact DROP disassembly drift")

        truth = ElfTruth.read(
            ELF, llvm_readobj=READOBJ, include_section_data=True)
        run, run_body = symbol_body(truth, "vm_run_inner")
        dma, dma_body = symbol_body(truth, "vm_dma")
        code_load, code_load_body = symbol_body(truth, "vm_code_load")
        codebuf = truth.symbol("vm_codebuf")
        dma_list = truth.symbol("vm_dma_list")
        poff = truth.symbol("vmr_poff")
        pwmax = truth.symbol("vmr_pwmax")
        winlen = truth.symbol("vmr_winlen")
        require(run.value == 0x3802 and run.bytes == 7869
                and dma.value == 0x71d2 and dma.bytes == 56
                and code_load.value == 0x720a and code_load.bytes == 38
                and codebuf.value == 0x8a09 and codebuf.bytes == 56
                and dma_list.value == 0x0076 and dma_list.bytes == 12
                and poff.value == 0x8a43 and pwmax.value == 0x8a47
                and winlen.value == 0x8a49,
                "Link-90 Runtime symbol geometry drift")
        require(sha_bytes(run_body)
                == "dcbd3a00efa11d141af7e642b1c3de4fbeeb153128b7e7c70fa23af731081869"
                and sha_bytes(dma_body)
                == "6d845425c9a912c2a9bb33ccaaa30734475f47fee77490bac2df523689dbc04a"
                and sha_bytes(code_load_body)
                == "0633ce09955a10608cc86dd5c7c54fdf0e0fb7095c0cbe1c04b863f48a0511f9",
                "linked Runtime symbol body drift")

        # Link-90 native dataflow at the streamed-window refill.  It stores
        # winlen, forms destination vm_codebuf+hdrlen, forms source
        # object+win+payload_off, calls vm_code_load, and immediately fetches
        # from the destination after the call returns.
        require(bytes_at(truth, 0x3ba2, 69) == bytes.fromhex(
            "8e498a8c4a8a18a9096565850886058406a98a65668509"
            "a61f860418a50e6504a8a6208604a50a650485041898"
            "6d438aaaa5046d448a8504a51d200a72a667a46886048405"),
            "linked refill argument/call dataflow drift")
        require(bytes_at(truth, 0x3bdc, 39) == bytes.fromhex(
            "200a72a667a46886048405a6048616a6058617e316b204"
            "c94290034c053985060606a6067c1c7e"),
            "linked refill return-to-dispatch edge drift")
        require(code_load_body == bytes.fromhex(
            "da7aa60448a505850aa506850b6407a5088505a5098506"
            "688504a50a8508a50b8509984cd271"),
            "vm_code_load ABI adapter drift")
        require(dma_body == bytes.fromhex(
            "860aa608a4098677847864768579a60a867aa604867ba605"
            "867ca606867da607867e647f64806481a9008d02d7a900"
            "8d01d7a9768d00d760"),
            "normal F018B submission leaf drift")
        require("vm_dma(off, bank, (uint16_t)(uintptr_t)dst, 0, len);"
                in vm_embed
                and "sta $d700" in vm_embed
                and "return 1;" in vm[
                    vm.index("static uint8_t vm_object_load"):
                    vm.index("static int dir_find")],
                "source-level Runtime transport path drift")

        refill_destination = codebuf.value + header_bytes
        expected_job = [
            0, window_bytes & 0xff, window_bytes >> 8,
            refill_source & 0xff, refill_source >> 8, 5,
            refill_destination & 0xff, refill_destination >> 8, 0,
            0, 0, 0,
        ]
        require(expected_job == [0, 35, 0, 26, 7, 5,
                                 30, 138, 0, 0, 0, 0],
                "modeled linked F018B descriptor drift")

        facts = {
            "device_observation": {
                "cursor": "0x0024", "owner": "5:0x06e1",
                "window_base": "0x0024", "fetched_byte": "0x0b",
                "expected_byte": "0x3b",
                "fetched_byte_is_initial_destination_byte": True,
                "capture_width": "one-opcode-byte",
            },
            "artifact": {
                "object": "m65-sprite-shape", "bank": 5,
                "object_offset": "0x06e1", "object_bytes": 140,
                "header_bytes": header_bytes, "payload_bytes": payload_bytes,
                "code_buffer_bytes": code_buffer_bytes,
                "payload_window_bytes": window_bytes,
                "initial_source": "5:0x06f6",
                "refill_cursor": "0x0024",
                "refill_relative": "0x0039",
                "refill_source": "5:0x071a",
                "refill_destination": "0:0x8a1e",
                "refill_bytes": window_bytes,
                "initial_payload_byte": "0x0b",
                "refill_payload_byte": "0x3b",
            },
            "linked_path": {
                "runtime_elf_sha256": bind(ELF)["sha256"],
                "refill_call": "0x3bdc -> vm_code_load@0x720a",
                "transport": "normal-F018B-D700",
                "job_list": "0x0076+12",
                "job_bytes_for_observed_refill": expected_job,
                "software_source_equation":
                    "0x06e1 + 0x0015 + 0x0024 = 0x071a",
                "software_destination_equation":
                    "0x8a09 + 0x0015 = 0x8a1e",
                "unconditional_D700_submit_before_return": True,
                "return_immediately_after_submit": True,
                "destination_readback_before_dispatch": False,
                "independent_content_oracle": False,
                "next_consumer": "opcode fetch at 0x3bf1",
            },
            "fix_form_attribution": {
                "missing_software_submit": "eliminated",
                "wrong_software_source_offset": "eliminated",
                "selected": "D700-submission-is-treated-as-content-completion",
                "required_fix_form": "content-defined-streamed-window-convergence",
                "independent_oracle":
                    "compare complete destination window bytes with the authoritative source; never use submit return or refill metadata",
                "coverage":
                    "every streamed execution refill path before opcode consumption",
                "family":
                    "L10-DMA-visibility-contract-class; distinct-D700-transport",
                "delivery_eventually_lands": "not-measured",
                "DMA_engine_consumed_descriptor_exactly": "not-measured",
                "claim_limit":
                    "the one-byte device capture cannot distinguish late delivery from engine-side descriptor misexecution; the ELF eliminates only software-side missing-submit and wrong-offset forms",
            },
            "scope": {
                "host_elf_only": True, "hardware_contacts": 0,
                "product_candidate_bytes_changed": 0, "product_fixes": 0,
                "product_links": 0, "link_91_built": False,
            },
        }
        audit(facts)
        mutations = mutation_check(facts)
        receipt = {
            "format":
                "lisp65-c2.3-v1.4-link90-refill-fix-form-host-elf-attribution-v1",
            "recorded_on": date.today().isoformat(),
            "status":
                "ATTRIBUTED-D700-SUBMISSION-ACCEPTED-AS-CONTENT-COMPLETION",
            "candidate_link": 90,
            "facts": facts,
            "verification": {
                "executions": 1,
                "mutations_rejected": len(mutations),
                "mutation_results": mutations,
            },
            "bindings": {
                "candidate_image": bind(IMAGE),
                "runtime_elf": bind(ELF),
                "ship_receipt": bind(SHIP_RECEIPT),
                "opcode_view_config": bind(CONFIG),
                "contact_8": bind(CONTACT),
                "artifact_manifest": bind(MANIFEST),
                "artifact_ext": bind(EXT),
                "artifact_disassembly": bind(DISASM),
                "vm": bind(VM), "vm_embed": bind(VM_EMBED),
                "owner_review": bind(OWNER), "driver": bind(DRIVER),
            },
        }
        write_json(RECEIPT, receipt)
        print("LINK90 REFILL FIX FORM ATTRIBUTED "
              "transport=D700 source=5:071a target=0:8a1e bytes=35 "
              f"mutations={len(mutations)} product-delta=0")
        return 0
    except (AttributionError, StopIteration) as error:
        print(f"FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
