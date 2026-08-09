#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 refill/read/return witness."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-v14-link90-read-edge-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-read-edge-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-read-edge-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-read-edge-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-read-edge-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-read-edge-witness"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"


class WitnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WitnessError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
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


def run(args: list[str], label: str) -> str:
    process = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    require(process.returncode == 0, f"{label} failed:\n{process.stdout}")
    return process.stdout


def clean_head() -> str:
    status = run(["git", "status", "--porcelain", "--untracked-files=all"],
                 "verify read-edge source tree")
    require(status == "", "read-edge preparation requires a clean worktree")
    return run(["git", "rev-parse", "HEAD"], "resolve source commit").strip()


def disassembly_block(path: Path, name: str) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = next((index for index, line in enumerate(lines)
                   if line.startswith("[") and line.endswith(" " + name)), None)
    require(header is not None, f"disassembly object absent: {name}")
    payload = lines.index("  payload:", header) + 1
    result: list[tuple[int, str]] = []
    for line in lines[payload:]:
        match = re.match(r"    ([0-9a-f]{4}) (.+)", line)
        if match is None:
            if result:
                break
            continue
        result.append((int(match.group(1), 16), match.group(2)))
    return result


def artifact_edges(config: dict[str, Any]) -> dict[str, Any]:
    manifest_path = ROOT / config["artifact_manifest"]
    disassembly_path = ROOT / config["artifact_disassembly"]
    manifest = load(manifest_path)
    by_name = {row["name"]: row for row in manifest["entries"]}
    shape = by_name["m65-sprite-shape"]
    read = by_name["m65-byte-read"]
    require(int(shape["ext_addr"], 16) ==
            (config["shape_bank"] << 16) + config["shape_offset"],
            "Link-90 shape object address drift")
    require(shape["lit_count"] == 7 and read["lit_count"] == 0,
            "Link-90 shape/read literal geometry drift")
    shape_ops = dict(disassembly_block(disassembly_path, "m65-sprite-shape"))
    read_ops = dict(disassembly_block(disassembly_path, "m65-byte-read"))
    expected_shape = {
        0x25: "PUSHLIT 1", 0x27: "PUSHI8 47", 0x29: "PUSHI8 83",
        0x2B: "CALL lit=2 argc=3", 0x2E: "DROP", 0x2F: "PUSHLIT 1",
        0x31: "PUSHI8 108", 0x33: "CALL lit=3 argc=2", 0x36: "STOREL 2",
    }
    require(all(shape_ops.get(offset) == instruction
                for offset, instruction in expected_shape.items()),
            "Link-90 refill/first-read/return instruction seam drift")
    require(read_ops == {
        0x00: "PUSHARG0", 0x01: "PUSHARG1",
        0x02: "CALLPRIM prim=61:peek argc=2", 0x05: "RET",
    }, "Link-90 m65-byte-read object drift")
    header = 7 + 2 * shape["lit_count"]
    payload_window = 56 - header
    require(header == 21 and payload_window == 35,
            "Link-90 streamed window geometry drift")
    require(config["refill_pc"] == 0x2E
            and config["return_pc"] == 0x36
            and config["first_read_address"] == 0xD06C,
            "configured read-edge constants drift")
    return {
        "shape_bank": config["shape_bank"],
        "shape_offset": f"0x{config['shape_offset']:04x}",
        "shape_header_bytes": header,
        "initial_payload_window_bytes": payload_window,
        "post_unlock_refill_pc": "0x002e",
        "first_geometry_read_address": "0xd06c",
        "first_geometry_call_pc": "0x0033",
        "post_return_resume_pc": "0x0036",
        "read_object": {
            "bank": int(read["ext_addr"], 16) >> 16,
            "offset": f"0x{int(read['ext_addr'], 16) & 0xffff:04x}",
            "payload": [row for _, row in sorted(read_ops.items())],
        },
    }


def symbol_row(truth: ElfTruth, name: str, expected_bytes: int) -> dict[str, Any]:
    symbol = truth.symbol(name)
    require(symbol.section not in ("Absolute", "Undefined"),
            f"diagnostic symbol not linked: {name}")
    require(0x0020 <= symbol.value < 0xD000,
            f"diagnostic symbol not in ordinary RAM: {name}")
    require(symbol.bytes == expected_bytes,
            f"diagnostic symbol size drift: {name}={symbol.bytes}")
    return {"name": name, "address": f"0x{symbol.value:08x}",
            "bytes": symbol.bytes, "section": symbol.section}


def audit(facts: dict[str, Any]) -> None:
    require(facts["identity"] == {
        "promotable": False, "product_candidate_bytes_changed": 0,
        "product_links": 0, "diagnostic_identities": 1,
    }, "diagnostic identity boundary drift")
    require(facts["contact"] == {
        "hardware_contacts": 1, "physical_keys": 0, "virtual_keys": 0,
        "screen_polls_during_execution": 0,
        "monitor_reads_during_execution": 0, "post_stop_ram_reads": 2,
    }, "device-contact boundary drift")
    require(facts["witness"] == {
        "layout": ["window_stage", "read_stage", "return_stage",
                   "mirror_tag", "mirror_value"],
        "initial": [17, 34, 51, 68, 85],
        "complete_stages": [161, 178, 195],
        "complete_mirror_tag": 212,
        "nonzero_stage_sentinels": True,
        "separate_mirror_tag": True,
        "ordinary_ram_only": True,
    }, "read-edge witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["window_after_successful_refill"] is True
            and edges["read_after_cpu_value"] is True
            and edges["return_after_buf_ensure_mine"] is True,
            "read-edge placement drift")


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "claim-product-link": (["identity", "product_links"], 1),
        "add-physical-key": (["contact", "physical_keys"], 1),
        "add-virtual-key": (["contact", "virtual_keys"], 1),
        "add-screen-poll": (["contact", "screen_polls_during_execution"], 1),
        "read-during-execution": (["contact", "monitor_reads_during_execution"], 1),
        "drop-post-stop-read": (["contact", "post_stop_ram_reads"], 1),
        "zero-window-sentinel": (["witness", "initial", 0], 0),
        "zero-read-sentinel": (["witness", "initial", 1], 0),
        "zero-return-sentinel": (["witness", "initial", 2], 0),
        "drop-tag": (["witness", "separate_mirror_tag"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "stamp-before-refill": (["edges", "window_after_successful_refill"], False),
        "stamp-before-read": (["edges", "read_after_cpu_value"], False),
        "stamp-before-reload": (["edges", "return_after_buf_ensure_mine"], False),
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
        except WitnessError as error:
            rejected[name] = str(error)
        else:
            raise WitnessError(f"read-edge mutation survived: {name}")
    return rejected


def build_image(output: Path, config: dict[str, Any], cc: Path | None) -> str:
    require(not output.exists(), f"diagnostic output already exists: {output}")
    args = [sys.executable, str(BUILDER), "build", "--form", config["form"],
            "--project", config["project"], "--out", str(output)]
    if cc is not None:
        args += ["--cc", str(cc)]
    output_text = run(args, f"build {output.parent.name} Ship identity")
    run([sys.executable, str(BUILDER), "verify", "--image", str(output)],
        f"verify {output.parent.name} Ship identity")
    return output_text.strip()


def prepare() -> int:
    head = clean_head()
    config = load(CONFIG)
    owner = " ".join(OWNER.read_text(encoding="utf-8").split())
    vm_source = VM.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    require(config["status"] ==
            "owner-authorized-non-promotable-read-edge-witness",
            "owner authorization status drift")
    for token in (
        "Authorized: witness contact 3", "Non-zero sentinel stamps per stage",
        "after window refill", "after the first geometry read", "after the return",
        "zero product bytes", "no Link 91", "One contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_READ_EDGE_WITNESS", "window_stage", "read_stage",
        "return_stage", "mirror_tag", "LISP65_V14_WITNESS_WINDOW",
        "LISP65_V14_WITNESS_READ", "LISP65_V14_WITNESS_RETURN",
        "BUF_ENSURE_MINE(pcur);", "LISP65_V14_WITNESS_RETURN(bank, off, pcur);",
    ):
        require(token in vm_source, f"read-edge VM seam drift: {token}")
    require("lisp65_v14_read_edge_witness_reset();" in main_source,
            "read-edge reset is not immediately bound to Runtime entry")
    for token in (
        "LISP65_V14_WITNESS_SHAPE_OFF=0x06e1",
        "LISP65_V14_WITNESS_REFILL_PC=0x002e",
        "LISP65_V14_WITNESS_RETURN_PC=0x0036",
    ):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    edges = artifact_edges(config)
    prior = load(ROOT / config["prior_witness_receipt"])
    raw_unlock = load(ROOT / config["raw_unlock_receipt"])
    require(prior["status"] == "BOUNDED-FIRST-RED-BEFORE-POINTER-STAGE"
            and prior["device"]["stage_bytes"] == [161, 0, 0],
            "contact-2 boundary authority drift")
    require(raw_unlock["discriminators"]["exact_pair_fixture"]["target_state"]
            == "RUNTIME_COMPLETE=3", "raw unlock target-green authority drift")

    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    reference_receipt = load(ROOT / config["reference_receipt"])
    require(sha(reference_image) == config["reference_image_sha256"],
            "Link-90 reference image drift")
    require(sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 reference Runtime ELF drift")
    before = {reference_image: sha(reference_image), reference_elf: sha(reference_elf)}

    control = ROOT / config["control_output"]
    diagnostic = ROOT / config["diagnostic_output"]
    build_image(control, config, None)
    control_elf = control.with_suffix(".runtime.elf")
    require(sha(control_elf) == config["reference_runtime_elf_sha256"],
            "inactive read-edge seams changed the ordinary Runtime ELF")

    toolchain = diagnostic.parent / "diagnostic-toolchain"
    toolchain.mkdir(parents=True, exist_ok=False)
    cc = toolchain / "mos-mega65-clang"
    readobj = toolchain / "llvm-readobj"
    cc.symlink_to(WRAPPER)
    readobj.symlink_to(READOBJ)
    diagnostic_build = build_image(diagnostic, config, cc)
    diagnostic_elf = diagnostic.with_suffix(".runtime.elf")
    diagnostic_receipt = load(diagnostic.with_suffix(".receipt.json"))
    require(diagnostic_receipt["build_identity_sha256"]
            == reference_receipt["build_identity_sha256"],
            "diagnostic identity changed the emitted Lisp artifact")
    require(diagnostic_receipt["host_execution"]["status"] == "passed",
            "diagnostic identity host execution is not green")

    truth = ElfTruth.read(diagnostic_elf, llvm_readobj=READOBJ)
    control_truth = ElfTruth.read(control_elf, llvm_readobj=READOBJ)
    witness = symbol_row(truth, config["witness_symbol"], 5)
    state = symbol_row(truth, config["runtime_state_symbol"], 1)
    control_names = {row.name for row in control_truth.symbols}
    require(config["witness_symbol"] not in control_names,
            "read-edge witness escaped into the ordinary Runtime")
    reserve = truth.symbol(
        "__lisp65_runtime_core_inline_required_post_boot_reserve_param").value
    actual_stack_heap = truth.symbol("__stack").value - truth.symbol("__heap_start").value
    require(reserve == config["diagnostic_post_boot_reserve_param"]
            and actual_stack_heap >= 8192 + reserve,
            "diagnostic-only stack/heap reserve proof drift")
    require(all(sha(path) == digest for path, digest in before.items()),
            "Link-90 product candidate changed during diagnostic build")

    facts = {
        "identity": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "diagnostic_identities": 1,
        },
        "contact": {
            "hardware_contacts": config["limits"]["hardware_contacts"],
            "physical_keys": config["limits"]["physical_keys"],
            "virtual_keys": config["limits"]["virtual_keys"],
            "screen_polls_during_execution":
                config["limits"]["screen_polls_during_execution"],
            "monitor_reads_during_execution":
                config["limits"]["monitor_reads_during_execution"],
            "post_stop_ram_reads": config["limits"]["post_stop_ram_reads"],
        },
        "witness": {
            "layout": ["window_stage", "read_stage", "return_stage",
                       "mirror_tag", "mirror_value"],
            "initial": config["initial_bytes"],
            "complete_stages": config["stage_bytes"],
            "complete_mirror_tag": config["mirror_tag"],
            "nonzero_stage_sentinels": True,
            "separate_mirror_tag": True,
            "ordinary_ram_only": True,
        },
        "edges": {
            "artifact_bound": True,
            "window_after_successful_refill": True,
            "read_after_cpu_value": True,
            "return_after_buf_ensure_mine": True,
            **edges,
        },
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-read-edge-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-read-edge-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-READ-EDGE-WITNESS",
        "candidate_link": 90, "facts": facts,
        "diagnostic_runtime_contract": {
            "product_wall_changed": False,
            "post_boot_reserve_param": reserve,
            "actual_stack_heap_bytes": actual_stack_heap,
        },
        "control": {"image": bind(control), "runtime_elf": bind(control_elf),
                    "byteidentical_to_link90_runtime_elf": True},
        "diagnostic": {"image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
                       "ship_receipt": bind(diagnostic.with_suffix(".receipt.json")),
                       "build_output": diagnostic_build},
        "reference_candidate": {"image": bind(reference_image),
                                "runtime_elf": bind(reference_elf),
                                "unchanged_after_build": True},
        "verification": {"executions": 2, "mutation_count": len(rejected),
                         "mutations_rejected": rejected},
        "bindings": {
            "config": bind(CONFIG), "owner_review": bind(OWNER), "vm": bind(VM),
            "runtime_main": bind(MAIN), "compiler_wrapper": bind(WRAPPER),
            "hardware_script": bind(HW), "ship_builder": bind(BUILDER),
            "driver": bind(DRIVER), "artifact_manifest": bind(
                ROOT / config["artifact_manifest"]),
            "artifact_disassembly": bind(ROOT / config["artifact_disassembly"]),
            "contact_2": bind(ROOT / config["prior_witness_receipt"]),
            "raw_unlock": bind(ROOT / config["raw_unlock_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"READ EDGE PREPARED host=2 mutations={len(rejected)} "
          f"witness={witness['address']}+5")
    return 0


def verify_preparation_bindings(preparation: dict[str, Any]) -> None:
    for name, row in preparation["bindings"].items():
        require(bind(ROOT / row["path"]) == row,
                f"prepared source binding drift: {name}")


def dry_run() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    require(preparation["status"] ==
            "PREPARED-NON-PROMOTABLE-READ-EDGE-WITNESS",
            "preparation status drift")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", deployment["source_commit"], "HEAD"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require(ancestry.returncode == 0,
            "prepared identity source commit is not an ancestor of HEAD")
    verify_preparation_bindings(preparation)
    require(deployment["image"] == bind(ROOT / config["diagnostic_output"]),
            "prepared image drift")
    require(sha(ROOT / config["reference_image"]) == config["reference_image_sha256"]
            and sha(ROOT / config["reference_runtime_elf"])
            == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift")
    require(not (RUN / "contact.consumed").exists(),
            "read-edge hardware contact already consumed")
    print("READ EDGE DRY RUN PASS contact=1 sentinel=11/22/33 tag=44")
    return 0


def classify(values: list[int]) -> tuple[str, str]:
    window, read, returned, tag, value = values
    if values == [17, 34, 51, 68, 85]:
        return ("ATTRIBUTED-REFILL-NOT-COMPLETED",
                "post-unlock caller window refill did not complete")
    if values == [161, 34, 51, 68, 85]:
        return ("ATTRIBUTED-FIRST-GEOMETRY-READ-NOT-COMPLETED",
                "caller refill completed; the first D06C CPU read did not complete")
    if window == 161 and read == 178 and returned == 51 and tag == 212:
        return ("ATTRIBUTED-READ-COMPLETE-RETURN-NOT-COMPLETED",
                f"D06C read completed with {value}; caller return/reload did not complete")
    if window == 161 and read == 178 and returned == 195 and tag == 212:
        return ("ATTRIBUTED-AFTER-FIRST-READ-RETURN",
                f"refill, D06C read ({value}) and caller return/reload all completed")
    raise WitnessError(f"non-atomic or unknown read-edge witness: {values}")


def analyze() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "read_edge_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 5,
            "five-byte read-edge witness absent")
    require(state_path.is_file() and state_path.stat().st_size == 1,
            "runtime-state capture absent")
    require(readback_path.is_file(), "D81 readback absent")
    require(sha(readback_path) == deployment["image"]["sha256"],
            "device-upload D81 readback drift")
    state = state_path.read_bytes()[0]
    require(state == config["terminal_value"],
            f"unexpected runtime state: {state}")
    values = list(witness_path.read_bytes())
    status, conclusion = classify(values)
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"]
            and sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift after contact")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-read-edge-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion},
        "interpretation": {"nonzero_sentinels": True,
                           "mirror_completion_tagged": True,
                           "product_fix_authorized": False},
        "candidate_unchanged": {"image": bind(reference_image),
                                "runtime_elf": bind(reference_elf)},
        "bindings": {
            "preparation": bind(PREPARATION), "deployment": bind(DEPLOYMENT),
            "config": bind(CONFIG), "owner_review": bind(OWNER),
            "driver": bind(DRIVER), "hardware_script": bind(HW),
            "witness": bind(witness_path), "runtime_state": bind(state_path),
            "device_readback": bind(readback_path),
            "fresh_basic": bind(RUN / "fresh-basic.txt"),
            "upload_log": bind(RUN / "upload.log"),
            "contact_consumed": bind(RUN / "contact.consumed"),
        },
    }
    write_json(RESULT, receipt)
    print(f"READ EDGE {status} witness={values} state={state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "dry-run", "analyze"))
    action = parser.parse_args().action
    try:
        return {"prepare": prepare, "dry-run": dry_run,
                "analyze": analyze}[action]()
    except WitnessError as error:
        print(f"FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
