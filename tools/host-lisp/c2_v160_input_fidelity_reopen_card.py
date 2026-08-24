#!/usr/bin/env python3
"""Run the owner-released post-R1 v1.6 input-fidelity reopen card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT_LINK  # noqa: E402
import c2_v160_abort_driver_relocation as R1_GATE  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_r1_scope_projection_replacement as R1_TOP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-reopen-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-reopen-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRODUCT_PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
QUALIFICATION_ROOT: Path | None = None
HOST_REPORT = BUILD / "input-fidelity-reopen-host.json"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-reopen-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-reopen-card-final-red.json"
R1_CLOSURE = ARCH / "c2.3-v1.6-r1-golden-acceptance-replay-receipt.json"
R1_STUDY = ARCH / "c2.3-v1.6-e000-relocation-study-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "c7d3b496"
FORMAT = "lisp65-c2-v160-input-fidelity-reopen-card-v1"
STATUS = "PASS: V1.6 INPUT-FIDELITY REOPEN GREEN"
LINK = 118
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ReopenError(RuntimeError):
    pass


class DryLinkReached(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReopenError(message)


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


def abi_report_path(build: Path) -> Path:
    """Derive the ABI report from its qualification-phase owner when set."""
    if QUALIFICATION_ROOT is not None:
        return QUALIFICATION_ROOT / "c2-asm-leaf-abi.json"
    return build / "wplto/c2-asm-leaf-abi.json"


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("input-fidelity reopen card", "expected: 136 free",
                  "94-event", "$a0 → $20", "all eleven r1-era gates",
                  "exceptionless"):
        require(token in text, f"reopen authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def r1_predecessor() -> dict[str, Any]:
    closure = load(R1_CLOSURE)
    require(closure["status"] == "PASS: R1 CLOSED UNDER ACCEPTED V5 GOLDEN"
            and closure["R1_closed"] is True
            and closure["execution_witness"] == {
                "WPLTO_runs": 0, "acceptance_replays": 1,
                "cards_consumed": 0, "device_contacts": 0,
                "media_builds": 0, "product_links": 0,
                "output": closure["execution_witness"]["output"]}
            and closure["frozen_pair_before"] == closure["frozen_pair_after"],
            "R1 closure drift")
    return closure


def core_module() -> Any:
    return R1_TOP.PREV.PREV.PREV.PREV.CORE


def set_core_paths(build: Path, preflight: Path) -> Any:
    core = core_module()
    core.BUILD = build; core.PREFLIGHT = preflight
    core.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    core.INVOCATION = preflight / "card-invocation.json"
    core.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    core.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    core.PRODUCER_RESULT = build / "producer-result.json"
    core.SCOPE_RESULT = build / "owner-scope-result.json"
    core.ACCEPTANCE_RESULT = build / "artifact-acceptance.json"
    core.ABI_REPORT = abi_report_path(build)
    core.R1_REPORT = build / "abort-driver-relocation-host.json"
    core.PRODUCT_ELF = build / "wplto/lisp65-c2-substitution-linked.prg.elf"
    core.PRODUCT_PRG = build / "wplto/lisp65-c2-substitution-linked.prg"
    core.RECEIPT = build / "unused-r1-receipt.json"
    core.FINAL_RED = build / "unused-r1-final-red.json"
    core.DRIVER = DRIVER; core.LINK = LINK
    return core


def roots(build: Path = BUILD, preflight: Path = PREFLIGHT) -> dict[str, str]:
    return {"build": build.relative_to(ROOT).as_posix(),
            "preflight": preflight.relative_to(ROOT).as_posix(),
            "projected_ownership": (preflight /
                "projected-ownership-contract.json").relative_to(ROOT).as_posix(),
            "projected_full_map": (preflight /
                "projected-full-map-authority.json").relative_to(ROOT).as_posix()}


def configure_stack(build: Path = BUILD, preflight: Path = PREFLIGHT,
                    *, activate_capture: bool = True) -> tuple[Any, dict[str, Any]]:
    """Install the accepted R1 stack, then select the separate capture file."""
    R1_TOP.configure_module()
    core = set_core_paths(build, preflight)
    core.install(build, preflight)
    activation = (PRODUCT_LINK.configure_input_capture()
                  if activate_capture else {"already_active": False})
    return core, activation


def bind_paths_only(build: Path = BUILD,
                    preflight: Path = PREFLIGHT) -> dict[str, str]:
    R1_TOP.configure_module()
    core = set_core_paths(build, preflight)
    core.bind_paths_only(build, preflight)
    current = FIDELITY.output_root_snapshot()
    require(current == roots(build, preflight),
            "reopen path-only output projection missed root producer")
    return current


def write_projections(core: Any) -> None:
    core.write_projections()


def setup(build: Path = BUILD, preflight: Path = PREFLIGHT) -> tuple[Any, dict[str, Any]]:
    core, activation = configure_stack(build, preflight)
    static = core.install_static(build)
    core.bind_paths_only(build, preflight)
    write_projections(core)
    require(static["consumer_observed_bytes"] == 46043,
            "candidate static-plane consumer drift")
    return core, activation


def run_r1_arm() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_r1_arm"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, f"R1 inherited arm red: {result.stderr}")
    value = json.loads(result.stdout)
    require(value["status"] == "PASS: R1 SCOPE PROJECTION REPLACEMENT ARMED 0/1",
            "R1 inherited arm status drift")
    return value


def inherited_gate_inventory(arm: dict[str, Any]) -> dict[str, Any]:
    closure = r1_predecessor()
    conversions = arm["six_conversion_projection_recheck"]
    require(len(conversions) == 6
            and arm["projection_order_gate"]["mutations_rejected"] == [
                "capture-before-configuration", "omit-live-scope-projection"],
            "R1 inherited projection/conversion gate drift")
    rows = {
        "01-derived-reserve": "rechecked-on-final-capture-ELF",
        "02-file-membership-boundary": "configuration-effectiveness-probe",
        "03-single-owner-equates": "source-and-linked-single-definition",
        "04-worst-state-abort": "rechecked-on-final-capture-ELF",
        "05-transitive-ASM-ABI-and-eight-exits": "rechecked-on-final-capture-ELF",
        "06-name-derived-zero-literal-witness": "inherited-arm-green",
        "07-graph-complete-six-conversions": "inherited-arm-green",
        "08-real-caller-adapter-signatures": "inherited-arm-green",
        "09-post-configuration-projection": "inherited-arm-green",
        "10-accepted-v5-golden": "rechecked-by-acceptance-child",
        "11-frozen-R1-closure-identity": "sha-bound-green-predecessor",
    }
    require(len(rows) == 11 and closure["frozen_pair_before"] ==
            closure["frozen_pair_after"], "R1 eleven-gate inventory drift")
    return {"status": "PASS: ALL ELEVEN R1-ERA GATES ARE MEMBERS",
            "members": rows, "inherited_arm": arm,
            "R1_closure": bind(R1_CLOSURE)}


def dry_child() -> None:
    build = PREFLIGHT / "real-producer-dry-build"
    preflight = PREFLIGHT / "real-producer-dry-preflight"
    core, activation = setup(build, preflight)
    require(activation["source"] ==
                "src/optional/c2_kernal_input_capture.s",
            "capture activation did not select its file member")
    reached = False

    def stop(*_args: Any, **_kwargs: Any) -> None:
        nonlocal reached
        reached = True
        raise DryLinkReached("reopen real single_link reached")

    PRODUCT_LINK.single_link = stop
    try:
        core.PRODUCT.BASE.produce_child()
    except DryLinkReached:
        print("REOPEN REAL PRODUCER PREFLIGHT PASS single-link WPLTO=0 link=0")
        return
    except Exception as error:
        elf = build / "wplto/lisp65-c2-substitution-linked.prg.elf"
        prg = build / "wplto/lisp65-c2-substitution-linked.prg"
        if (str(error) == "producer did not emit the linked candidate artifacts"
                and reached and not elf.exists() and not prg.exists()):
            print("REOPEN REAL PRODUCER PREFLIGHT PASS sentinel WPLTO=0 link=0")
            return
        raise
    raise ReopenError("reopen dry producer missed real single_link")


def run_child(action: str) -> str:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"reopen child {action} red:\n{result.stdout}")
    return result.stdout


def preflight() -> None:
    r1_predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "input-fidelity reopen card is one-shot")
    authority = authorization()
    arm = run_r1_arm()
    inherited = inherited_gate_inventory(arm)
    host = FIDELITY.derive(output_rebind=bind_paths_only,
        expected_output_roots=roots())
    source = R1_GATE.source_gate()
    configuration = R1_GATE.configuration_gate()
    require(configuration["R1_capture_source_present"] is False
            and configuration["capture_world_capture_source_present"] is True
            and configuration["input_sets_differ"] is True
            and source["capture_activation"] == "real-link-input-membership",
            "capture file-membership/effectiveness boundary red")
    PREFLIGHT.mkdir(parents=True)
    dry = run_child("_dry")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-19",
        "status": "PASS: INPUT-FIDELITY REOPEN ARMED 0/1",
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "authority": authority, "R1_closure": bind(R1_CLOSURE),
        "R1_study": bind(R1_STUDY), "driver": bind(DRIVER),
        "input_fidelity": host, "source_boundary": source,
        "configuration_boundary": configuration,
        "R1_inherited_gates": inherited,
        "real_producer_lifecycle": {"status": "passed-to-single-link",
            "WPLTO_runs": 0, "product_links": 0,
            "witness": " ".join(dry.split())},
        "red_policy": "exceptionless-owner-return-no-retry",
        "claim_limit": "Preflight only; no WPLTO, link, media or device."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity reopen: PREFLIGHT PASS card=0/1 R1-gates=11")


def produce_child() -> None:
    core, _activation = setup()
    raise SystemExit(core.PRODUCT.BASE.produce_child())


def scope_child() -> None:
    core, _activation = setup()
    raise SystemExit(core.PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    core, _activation = setup()
    os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(ACCEPTANCE_RESULT)
    raise SystemExit(core.PRODUCT.BASE.acceptance_child())


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    values = {"ELF": bind(PRODUCT_ELF), "PRG": bind(PRODUCT_PRG)}
    for name, path in (("map", BUILD / "wplto/lisp65-c2-substitution-linked.map"),
                       ("lto", BUILD / "wplto/resident-island-seed.prg.lto.o")):
        if path.is_file():
            values[name] = bind(path)
    return values


def capture_successor_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    service = truth.section(R1_GATE.FAR)
    facade = truth.section(R1_GATE.FACADE_SECTION)
    abort = truth.symbol("c2_abort_driver")
    entry = truth.symbol("c2_abort_driver_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    require(service.bytes == 1382 and abort.section == R1_GATE.FAR
            and abort.bytes == 134 and facade.bytes == 98
            and entry.bytes == 9 and padding.bytes == 10,
            "post-R1 capture changed abort/facade contracts")
    sections = {row.name: row for row in truth.sections}
    require(all(name in sections for name in R1_GATE.CAPTURE_SECTIONS),
            "capture successor omitted a capture section")
    capture_bytes = sum(sections[name].bytes
                        for name in R1_GATE.CAPTURE_SECTIONS)
    allocated_rows = sorted((max(R1_GATE.E000_START, row.address),
        min(R1_GATE.E000_END, row.address + row.bytes))
        for row in truth.sections if row.bytes > 0
        and "SHF_ALLOC" in set(row.flags)
        and row.address < R1_GATE.E000_END
        and row.address + row.bytes > R1_GATE.E000_START)
    allocated: list[tuple[int, int]] = []
    for start, end in allocated_rows:
        if not allocated or start > allocated[-1][1]:
            allocated.append((start, end))
        else:
            allocated[-1] = (allocated[-1][0], max(allocated[-1][1], end))
    free = R1_GATE.E000_END - R1_GATE.E000_START - sum(
        end - start for start, end in allocated)
    require(capture_bytes == 59 and free >= 54,
            "post-R1 successor exceeds the fixed E000 reserve floor")
    edges = R1_GATE.graph(truth)
    reached = R1_GATE.closure(edges, [
        "c2_mapped_far_vm_code_load_converged",
        "c2_mapped_far_physical_read_converged"])
    require(not (reached & {"c2_abort_driver", "c2_abort_driver_facade",
        "c2_product_abort_cleanup", "lisp_abort", "lisp_abort_code",
        "lisp_abort_symbol", "lisp_abort_static", "c2_mapped_far_leave"}),
        "post-R1 capture invalidated worst-state abort closure")
    equates = {}
    for name, expected in R1_GATE.SPLIT_EQUATES.items():
        rows = [row for row in truth.symbols if row.name == name]
        require(len(rows) == 1 and rows[0].value == expected
                and rows[0].section == "Absolute",
                f"post-R1 equate ownership drift: {name}")
        equates[name] = {"count": 1, "value": expected}
    return {"status": "PASS: POST-R1 CAPTURE SUCCESSOR CONTRACTS",
        "service_bytes": service.bytes, "abort_bytes": abort.bytes,
        "facade_bytes": facade.bytes, "entry_bytes": entry.bytes,
        "padding_bytes": padding.bytes, "capture_bytes": capture_bytes,
        "post_capture_free_bytes": free, "reserve_floor_bytes": 54,
        "surplus_over_floor_bytes": free - 54,
        "reserve_authority": "final ELF allocation minus fixed 54-byte floor",
        "stored_capture_only_reserve_pin_rejected": True,
        "worst_state_forbidden_reached": [], "equates": equates}


PREFLIGHT_STATUS_VOCABULARY = {
    "PASS: INPUT-FIDELITY REOPEN ARMED 0/1",
    "PASS: INPUT-FIDELITY REOPEN REPLACEMENT ARMED 0/1",
    "PASS: INPUT-FIDELITY GRAPH-REBIND REPLACEMENT ARMED 0/1",
}


def validate_card_preflight(preflight_value: dict[str, Any]) -> None:
    require(preflight_value["status"] in PREFLIGHT_STATUS_VOCABULARY
            and len(preflight_value["R1_inherited_gates"]["members"]) == 11,
            "persisted reopen/replacement preflight drift")
    FIDELITY.validate(preflight_value["input_fidelity"], final=False)


def card() -> None:
    r1_predecessor()
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "input-fidelity reopen lifecycle drift")
    preflight_value = load(PREFLIGHT_RECEIPT)
    validate_card_preflight(preflight_value)
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "card": "input-fidelity-reopen 1/1", "WPLTO_runs": 1,
        "product_links": 1, "exceptionless": True,
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    output = run_child("_produce")
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "reopen producer returned without linked product")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(before == after, "reopen qualification changed linked artifacts")

    host = FIDELITY.derive(PRODUCT_ELF, output_rebind=bind_paths_only,
                          expected_output_roots=roots())
    successor = capture_successor_gate(PRODUCT_ELF)
    HOST_REPORT.write_bytes(canonical({"input_fidelity": host,
        "R1_capture_successor": successor}))
    abi = subprocess.run([sys.executable, str(HOST / "c2_asm_leaf_abi_gate.py"),
        "--elf", str(PRODUCT_ELF), "--out", str(ABI_REPORT)], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(abi.returncode == 0
            and "passed-all-assembler-leaf-abi-contracts" in abi.stdout,
            f"reopen transitive ABI/every-exit gate red:\n{abi.stdout}")
    abi_value = load(ABI_REPORT)
    require(abi_value["transitive_callee_saved_preservation"]["model"]
                ["unpreserved_callee_saved_writers"] == []
            and abi_value["contractual_mapped_far_exit_preservation"]
                ["status"] == "passed-eight-contractual-service-exits-preserved",
            "reopen linked ABI/exit report drift")
    producer, scope, acceptance = (load(PRODUCER_RESULT), load(SCOPE_RESULT),
                                    load(ACCEPTANCE_RESULT))
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4 and scope["status"] == "PASS"
            and acceptance["status"] == "PASS",
            "reopen process isolation/scope/acceptance drift")
    value = {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": STATUS,
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "R1_closure": bind(R1_CLOSURE), "driver": bind(DRIVER)},
        "artifacts_before": before, "artifacts_after": after,
        "input_fidelity": bind(HOST_REPORT), "placement": host["placement"],
        "loss": host["loss"], "R1_capture_successor": successor,
        "ABI_and_exit_gate": bind(ABI_REPORT),
        "R1_inherited_gate_count": 11,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "stdout_tail": " ".join(output.split()[-30:]),
        "next": "owner device acceptance of v1.6 items 1 and 2",
        "claim_limit": "Host product card only; no Completion/media/device."}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity reopen: CARD PASS card=1/1 "
          "events=94/94 E000-free=136 surplus=82")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in
        (("ELF", PRODUCT_ELF), ("PRG", PRODUCT_PRG)) if path.is_file()}
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "recorded_on": "2026-08-19",
        "status": "FINAL RED: INPUT-FIDELITY REOPEN RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_link_attempts": 1,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"preflight": bind(PREFLIGHT_RECEIPT),
                      "driver": bind(DRIVER)}}))


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 input fidelity reopen: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 input fidelity reopen: CHECK FINAL RED")
    elif PREFLIGHT_RECEIPT.exists():
        print("v1.6 input fidelity reopen: CHECK ARMED")
    else:
        print("v1.6 input fidelity reopen: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_dry": dry_child()
    elif action == "_produce": produce_child()
    elif action == "_scope": scope_child()
    elif action == "_accept": acceptance_child()
    elif action == "_r1_arm":
        print(json.dumps(R1_TOP.arm(), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"reopen Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity reopen: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
