#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 production-order witness."""

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


CONFIG = ROOT / "config/c2-v14-link90-production-order-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
LIBRARY = ROOT / "lib/m65-hw.lisp"
FIXTURE = ROOT / (
    "tests/bytecode/dialect-v2/fixtures/v14-parity-toy-production-order/main.l65")
PROJECT = FIXTURE.with_name("project.l65p")
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
HW = ROOT / "scripts/c2-v14-link90-production-order-witness-hw.sh"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-production-order-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-production-order-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-production-order-witness"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DIAGNOSTIC_ARTIFACT = BASE / "artifact-proof"
PRODUCT_ARTIFACT = ROOT / "build/post-promotion/v14/parity-toy-link90-artifact"
RAW_UNLOCK = EVIDENCE / "c2.3-v1.4-link89-vic-unlock-tailcall-attribution.json"


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
                 "verify witness source tree")
    require(status == "", "witness preparation requires a clean worktree")
    return run(["git", "rev-parse", "HEAD"], "resolve source commit").strip()


def ordered(source: str, tokens: list[str], label: str) -> list[int]:
    positions: list[int] = []
    cursor = 0
    for token in tokens:
        position = source.find(token, cursor)
        require(position >= 0, f"{label} token absent or out of order: {token}")
        positions.append(position)
        cursor = position + len(token)
    return positions


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
        "address": "0x17b0", "bytes": 6,
        "stages": [
            {"offset": 0, "value": 161, "meaning": "argument-guard-passed"},
            {"offset": 1, "value": 178, "meaning": "pointer-guard-passed"},
            {"offset": 2, "value": 195, "meaning": "first-shape-byte-completed"},
        ],
        "live_geometry_offsets": [3, 4, 5],
        "ordinary_ram_only": True,
    }, "production-order witness contract drift")
    require(facts["path_equivalence"]["outer_guard_exact"] is True
            and facts["path_equivalence"]["pointer_guard_exact"] is True
            and facts["path_equivalence"]["first_write_exact"] is True
            and facts["path_equivalence"]["order_proven"] is True,
            "production-path equivalence drift")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "claim-product-link": (["identity", "product_links"], 1),
        "add-physical-key": (["contact", "physical_keys"], 1),
        "add-screen-poll": (["contact", "screen_polls_during_execution"], 1),
        "read-during-execution": (["contact", "monitor_reads_during_execution"], 1),
        "drop-post-stop-read": (["contact", "post_stop_ram_reads"], 1),
        "move-witness": (["witness", "address"], "0x17a0"),
        "drop-live-geometry": (["witness", "live_geometry_offsets"], [3, 4]),
        "change-argument-stamp": (["witness", "stages", 0, "value"], 160),
        "change-pointer-stamp": (["witness", "stages", 1, "value"], 177),
        "change-shape-stamp": (["witness", "stages", 2, "value"], 194),
        "break-outer-equivalence": (["path_equivalence", "outer_guard_exact"], False),
        "break-pointer-equivalence": (["path_equivalence", "pointer_guard_exact"], False),
        "break-first-write-equivalence": (["path_equivalence", "first_write_exact"], False),
        "erase-order-proof": (["path_equivalence", "order_proven"], False),
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
            raise WitnessError(f"witness mutation survived: {name}")
    return rejected


def source_proof() -> dict[str, Any]:
    production = " ".join(LIBRARY.read_text(encoding="utf-8").split())
    fixture = " ".join(FIXTURE.read_text(encoding="utf-8").split())
    outer = "(and (%m65-sprite-number-p sprite) (stringp shape) (= (string-length shape) 63))"
    pointer = "(and (= table-high 0) (<= table-low 248))"
    first_write = "(m65-byte-write (%m65-sprite-shape-slot-hi) (+ (%m65-sprite-shape-slot-lo) index) (string-ref shape index))"
    for token in (outer, pointer, first_write):
        require(token in production, f"production path token drift: {token}")
        require(token in fixture, f"witness path token drift: {token}")
    positions = ordered(fixture, [
        outer,
        "(m65-byte-write 23 176 161)",
        "(%m65-vic-open)",
        "(m65-byte-write 23 179 table-low)",
        "(m65-byte-write 23 180 table-mid)",
        "(m65-byte-write 23 181 table-high)",
        pointer,
        "(m65-byte-write 23 177 178)",
        "(%v14-order-write-shape shape 0)",
    ], "guard path")
    writer = fixture[fixture.index("(defun %v14-order-write-shape"):fixture.index(
        "(defun %v14-order-sprite-shape")]
    writer_positions = ordered(writer, [
        first_write,
        "(if (= index 0) (m65-byte-write 23 178 195) nil)",
        "(%v14-order-write-shape shape (+ index 1))",
    ], "shape writer")
    clear_positions = ordered(fixture, [
        f"(m65-byte-write 23 {low} 0)" for low in range(176, 182)
    ], "witness clear")
    return {
        "outer_guard_exact": True,
        "pointer_guard_exact": True,
        "first_write_exact": True,
        "order_proven": positions == sorted(positions)
                        and writer_positions == sorted(writer_positions)
                        and clear_positions == sorted(clear_positions),
        "guard_token": outer, "pointer_token": pointer,
        "first_write_token": first_write,
    }


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


def emitted_prefix_proof() -> dict[str, Any]:
    diagnostic_manifest = load(DIAGNOSTIC_ARTIFACT / "stdlib-p0.manifest.json")
    product_manifest = load(PRODUCT_ARTIFACT / "stdlib-p0.manifest.json")
    diagnostic_entries = {row["name"] for row in diagnostic_manifest["entries"]}
    product_entries = {row["name"] for row in product_manifest["entries"]}
    require("%m65-vic-open" not in diagnostic_entries
            and "%m65-vic-open" not in product_entries,
            "private VIC-open helper escaped into an emitted object")
    require("%m65-vic-open" in diagnostic_manifest["private_inline_functions"]
            and "%m65-vic-open" in product_manifest["private_inline_functions"],
            "private VIC-open inline contract drift")
    diagnostic = [
        instruction for offset, instruction in disassembly_block(
            DIAGNOSTIC_ARTIFACT / "stdlib-p0.disasm.txt",
            "%v14-order-pointer-stage")
        if 0x0A <= offset <= 0x37
    ]
    product = [
        instruction for offset, instruction in disassembly_block(
            PRODUCT_ARTIFACT / "stdlib-p0.disasm.txt", "m65-sprite-shape")
        if 0x1B <= offset <= 0x48
    ]
    diagnostic = [
        row.replace("PUSHLIT 3", "PUSHLIT 1").replace(
            "CALL lit=4", "CALL lit=3")
        for row in diagnostic
    ]
    require(len(product) == 22 and diagnostic == product,
            "emitted unlock/read prefix equivalence drift")
    raw = load(RAW_UNLOCK)
    exact_pair = raw["discriminators"]["exact_pair_fixture"]
    require(exact_pair["target_state"] == "RUNTIME_COMPLETE=3"
            and exact_pair["virtual_or_physical_input"] is False,
            "prior raw VIC-unlock target-green authority drift")
    return {
        "equivalent_instruction_count": 22,
        "product_payload_range": "0x001b-0x0048",
        "diagnostic_payload_range": "0x000a-0x0037",
        "private_vic_open_inlined_in_both": True,
        "raw_unlock_pair_previously_target_green": True,
        "localized_band": (
            "after accepted outer guard and target-green raw unlock; "
            "before a completed geometry mirror/pointer guard"),
        "claim_limit": (
            "does not distinguish live-register read, return/materialization, "
            "or streamed-window refill within the localized band"),
    }


def prepare() -> int:
    head = clean_head()
    config = load(CONFIG)
    owner = " ".join(OWNER.read_text(encoding="utf-8").split())
    require(config["status"] ==
            "owner-authorized-non-promotable-production-order-witness",
            "owner authorization status drift")
    for token in (
        "Production-order witnesses — authorized",
        "after the argument guard", "after the pointer guard",
        "after the first shape byte", "Zero product bytes, Link 90 unchanged",
    ):
        require(token in owner, f"owner authorization text absent: {token}")

    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"],
            "Link-90 reference image drift")
    require(sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 reference Runtime ELF drift")
    before = {reference_image: sha(reference_image), reference_elf: sha(reference_elf)}

    output = ROOT / config["diagnostic_output"]
    require(not output.exists(), f"diagnostic output already exists: {output}")
    build_output = run([
        sys.executable, str(BUILDER), "build", "--form", config["form"],
        "--project", config["project"], "--out", str(output),
    ], "build production-order witness")
    run([sys.executable, str(BUILDER), "verify", "--image", str(output)],
        "verify production-order witness")
    receipt_path = output.with_suffix(".receipt.json")
    runtime_elf = output.with_suffix(".runtime.elf")
    ship_receipt = load(receipt_path)
    require(ship_receipt["host_execution"]["status"] == "passed",
            "production-order host execution is not green")
    required_names = {
        "%v14-order-write-shape", "%v14-order-sprite-shape",
        "%v14-order-pointer-stage", "m65-byte-read", "m65-byte-write",
        "%m65-vic-open", "%m65-sprite-number-p", "%m65-error",
    }
    closure_names = set(ship_receipt["closure"]["function_names"])
    require(required_names <= closure_names,
            f"production-order closure incomplete: {sorted(required_names - closure_names)}")

    truth = ElfTruth.read(runtime_elf, llvm_readobj=READOBJ)
    state = truth.symbol("lisp65_runtime_state")
    require(state.section not in ("Absolute", "Undefined"),
            "runtime state symbol absent")
    require(all(sha(path) == digest for path, digest in before.items()),
            "Link-90 product candidate changed during witness build")

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
            "address": f"0x{config['witness_address']:04x}",
            "bytes": config["witness_bytes"],
            "stages": [
                {"offset": 0, "value": 161, "meaning": "argument-guard-passed"},
                {"offset": 1, "value": 178, "meaning": "pointer-guard-passed"},
                {"offset": 2, "value": 195, "meaning": "first-shape-byte-completed"},
            ],
            "live_geometry_offsets": [3, 4, 5],
            "ordinary_ram_only": True,
        },
        "path_equivalence": source_proof(),
    }
    audit(facts)
    rejected = mutations(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-production-order-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(output), "runtime_elf": bind(runtime_elf),
        "remote": config["remote"],
        "runtime_state": {
            "address": f"0x{state.value:08x}", "bytes": state.bytes or 1,
        },
        "witness": {
            "address": f"0x{config['witness_address']:08x}",
            "bytes": config["witness_bytes"],
        },
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-production-order-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-PRODUCTION-ORDER-WITNESS",
        "candidate_link": 90, "facts": facts,
        "diagnostic": {
            "image": bind(output), "runtime_elf": bind(runtime_elf),
            "ship_receipt": bind(receipt_path), "build_output": build_output.strip(),
        },
        "reference_candidate": {
            "image": bind(reference_image), "runtime_elf": bind(reference_elf),
            "unchanged_after_build": True,
        },
        "verification": {
            "executions": 2, "mutation_count": len(rejected),
            "mutations_rejected": rejected,
        },
        "bindings": {
            "config": bind(CONFIG), "owner_review": bind(OWNER),
            "library": bind(LIBRARY), "fixture": bind(FIXTURE),
            "project": bind(PROJECT), "ship_builder": bind(BUILDER),
            "hardware_script": bind(HW), "driver": bind(DRIVER),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"PRODUCTION ORDER PREPARED host=1 mutations={len(rejected)} "
          f"witness=0x{config['witness_address']:04x}+{config['witness_bytes']}")
    return 0


def dry_run() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    require(preparation["status"] ==
            "PREPARED-NON-PROMOTABLE-PRODUCTION-ORDER-WITNESS",
            "preparation status drift")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", deployment["source_commit"], "HEAD"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require(ancestry.returncode == 0,
            "prepared identity source commit is not an ancestor of HEAD")
    for name, row in preparation["bindings"].items():
        path = ROOT / row["path"]
        require(bind(path) == row, f"prepared source binding drift: {name}")
    require(deployment["image"] == bind(ROOT / config["diagnostic_output"]),
            "prepared image drift")
    require(sha(ROOT / config["reference_image"]) ==
            config["reference_image_sha256"], "Link-90 image drift")
    require(sha(ROOT / config["reference_runtime_elf"]) ==
            config["reference_runtime_elf_sha256"], "Link-90 Runtime ELF drift")
    require(not (RUN / "contact.consumed").exists(),
            "production-order hardware contact already consumed")
    print("PRODUCTION ORDER DRY RUN PASS contact=1 stages=A1/B2/C3 keys=0")
    return 0


def classify(values: list[int], state: int) -> tuple[str, str]:
    stages = values[:3]
    geometry = values[3:]
    valid_prefixes = ([0, 0, 0], [161, 0, 0], [161, 178, 0], [161, 178, 195])
    require(stages in valid_prefixes,
            f"non-monotonic or unknown production-order stamps: {stages}")
    if stages == [161, 0, 0]:
        require(state == 227, "pointer rejection stamps ended in non-error state")
        if geometry[2] != 0:
            return ("ATTRIBUTED-POINTER-GUARD-REJECTION",
                    "argument guard passed; completed live geometry mirror rejects on D06E")
        return ("BOUNDED-FIRST-RED-BEFORE-POINTER-STAGE",
                "argument guard passed; zero-valued mirror cannot prove its own completion, "
                "and the pointer stage was not reached")
    if stages == [161, 178, 0]:
        require(state == 227, "first-write edge stamps ended in non-error state")
        return ("ATTRIBUTED-TARGET-ONLY-FIRST-SHAPE-WRITE-EDGE",
                "both guards passed; first shape byte did not complete")
    if stages == [161, 178, 195]:
        if state == 3:
            return ("BOUNDED-FIRST-RED-DIAGNOSTIC-PATH-COMPLETED",
                    "diagnostic path completed; it did not reproduce the Link-90 error")
        return ("ATTRIBUTED-TARGET-ONLY-AFTER-FIRST-SHAPE-BYTE",
                "both guards and first shape byte completed")
    if stages == [0, 0, 0]:
        require(state == 227, "outer-guard stamps ended in non-error state")
        return ("BOUNDED-FIRST-RED-OUTER-GUARD",
                "outer argument guard did not pass despite prior argument evidence")
    raise AssertionError("unreachable")


def analyze() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "production_order_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 6,
            "six-byte production-order witness absent")
    require(state_path.is_file() and state_path.stat().st_size == 1,
            "runtime-state capture absent")
    require(readback_path.is_file(), "D81 readback absent")
    require(sha(readback_path) == deployment["image"]["sha256"],
            "device-upload D81 readback drift")
    values = list(witness_path.read_bytes())
    state = state_path.read_bytes()[0]
    require(state in config["terminal_values"],
            f"unexpected runtime state: {state}")
    status, conclusion = classify(values, state)
    prefix_proof = emitted_prefix_proof()
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"]
            and sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift after contact")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-production-order-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {
            "hardware_contacts": 1, "runtime_state": state,
            "stage_bytes": values[:3], "live_d06c_d06d_d06e": values[3:],
            "conclusion": conclusion,
        },
        "interpretation": {
            "vm_debug_tuple_used_as_proof": False,
            "production_order_is_monotonic_prefix": True,
            "product_fix_authorized": False,
            "emitted_prefix_proof": prefix_proof,
        },
        "candidate_unchanged": {
            "image": bind(reference_image), "runtime_elf": bind(reference_elf),
        },
        "bindings": {
            "preparation": bind(PREPARATION), "deployment": bind(DEPLOYMENT),
            "config": bind(CONFIG), "owner_review": bind(OWNER),
            "driver": bind(DRIVER), "hardware_script": bind(HW),
            "witness": bind(witness_path), "runtime_state": bind(state_path),
            "device_readback": bind(readback_path),
            "fresh_basic": bind(RUN / "fresh-basic.txt"),
            "upload_log": bind(RUN / "upload.log"),
            "contact_consumed": bind(RUN / "contact.consumed"),
            "diagnostic_artifact_manifest": bind(
                DIAGNOSTIC_ARTIFACT / "stdlib-p0.manifest.json"),
            "diagnostic_artifact_disassembly": bind(
                DIAGNOSTIC_ARTIFACT / "stdlib-p0.disasm.txt"),
            "product_artifact_manifest": bind(
                PRODUCT_ARTIFACT / "stdlib-p0.manifest.json"),
            "product_artifact_disassembly": bind(
                PRODUCT_ARTIFACT / "stdlib-p0.disasm.txt"),
            "raw_unlock_authority": bind(RAW_UNLOCK),
        },
    }
    write_json(RESULT, receipt)
    print(f"PRODUCTION ORDER {status} stages={values[:3]} "
          f"geometry={values[3:]} state={state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "dry-run", "analyze"))
    action = parser.parse_args().action
    try:
        return {"prepare": prepare, "dry-run": dry_run, "analyze": analyze}[action]()
    except WitnessError as error:
        print(f"FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
