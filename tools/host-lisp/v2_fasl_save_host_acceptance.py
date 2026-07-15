#!/usr/bin/env python3
"""Host acceptance for the dialect-v2 commit-last FASL writer."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import l65m_contract as L65M  # noqa: E402


TARGETS = (
    "1-",
    "%compile-slot-capacity",
    "%fasl-save-sector",
    "%fasl-save-tail",
    "%fasl-commit-first",
    "%fasl-save-staged-v2",
)
REPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "fasl-save-prototype-report.json"
)
GOLDEN_L65M = ROOT / "tests/bytecode/runtime/workbench-golden-v1/runtime-app.l65m"


class AcceptanceError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha256(commit, path):
    data = subprocess.run(
        ["git", "show", "%s:%s" % (commit, path)],
        cwd=ROOT, check=True, stdout=subprocess.PIPE,
    ).stdout
    return hashlib.sha256(data).hexdigest()


def validate_report(value):
    require(set(value) == {
        "format", "version", "id", "status", "source_commit",
        "source_bindings", "abi",
        "bytecode", "link_measurement", "persistence_acceptance",
        "service_inventory", "latency", "policy",
    }, "FASL report keys drift")
    require(value["format"] == "lisp65-v2-fasl-save-deresidentization-report-v1",
            "FASL report format drift")
    require(value["version"] == 1 and value["id"] == "fasl-save-to-bytecode",
            "FASL report identity drift")
    require(value["status"] == "implemented-relaxed-diagnostic-only",
            "FASL report status drift")
    commit = value["source_commit"]
    require(commit == "b0d6b07fbb1613153a0970402508efae98c362ba",
            "FASL report source commit drift")

    bindings = value["source_bindings"]
    paths = [item.get("path") for item in bindings]
    require(paths == sorted(set(paths)) and len(paths) == 7,
            "FASL report source inventory drift")
    for item in bindings:
        require(set(item) == {"path", "sha256"}, "FASL source binding keys drift")
        require(git_blob_sha256(commit, item["path"]) == item["sha256"],
                "FASL source binding SHA drift: %s" % item["path"])

    require(value["abi"] == {
        "profile": "dialect-v2", "retired_prim_id": 34,
        "canonical_name": "%save-staged", "decoder_name_retained": True,
        "new_emission": "forbidden", "runtime_result": "bad-primitive",
        "reuse": "forbidden", "v1_effect": "none",
    }, "FASL ABI receipt drift")
    bytecode = value["bytecode"]
    require(bytecode["callprim_34_calls"] == 0
            and bytecode["new_runtime_slots"] == 0
            and bytecode["permanent_island_bytes"] == 0,
            "FASL bytecode boundary drift")
    require([(item["name"], item["code_bytes"]) for item in bytecode["objects"]] == [
        ("%compile-slot-capacity", 88), ("compile-string", 175),
        ("%fasl-save-sector", 64), ("%fasl-save-tail", 127),
        ("%fasl-commit-first", 58), ("%fasl-save-staged-v2", 171),
    ], "FASL CodeObject inventory drift")

    link = value["link_measurement"]
    baseline = link["baseline"]
    candidate = link["candidate"]
    require(link["metric"] == "same-head-real-mos-lto-icf-relaxed-link"
            and link["platform_linker_restored"] is True,
            "FASL link measurement policy drift")
    require(int(baseline["runtime_overlay_vma"], 0) == 0xCC28
            and int(candidate["runtime_overlay_vma"], 0) == 0xC9D0,
            "FASL linked VMA drift")
    require(all(value == 600 for value in link["net_reclaim_bytes"].values()),
            "FASL net reclaim drift")
    require(link["remaining_gap_bytes"] == {
        "runtime_overlay_vma": 1658, "post_boot_reserve": 1400,
    }, "FASL remaining gap drift")

    persistence = value["persistence_acceptance"]
    require(persistence["boundary_lengths"] == [0, 1, 3, 4, 253, 254, 255, 256, 599, 600]
            and persistence["fault_cases"] == 5
            and persistence["chain_fuel"] == 255,
            "FASL persistence matrix drift")
    require(persistence["commit_protocol"]
            == "invalidate-first-prefix-write-tail-commit-first-sector-last",
            "FASL commit-last contract drift")
    require(persistence["successful_reload"] == "exact-bytes-and-l65m-valid"
            and persistence["reload_validator"] == "l65m-contract-v4"
            and persistence["reload_after_interrupted_write"] == "reject-invalid-prefix",
            "FASL reload contract drift")
    require(persistence["unchanged_regions"]
            == ["bam", "directory", "neighbor-slots", "guard-file"],
            "FASL D81 differential scope drift")
    require(persistence["successful_chain_ops"] == {
        "disk_reads": "2*N+1", "disk_writes": "N+1",
        "first_sector_writes": 2,
    }, "FASL I/O operation budget drift")

    service = value["service_inventory"]
    require(service["classified_targets"] == 28
            and service["unresolved_calls"] == 0
            and service["unresolved_targets"] == 0
            and service["tombstone_callprim_calls"] == 0,
            "FASL service closure drift")
    require(value["latency"] == {
        "structural_host_receipt": "disk-io-dominates-bytecode-coordinator",
        "hardware_measurement": "blocked-until-workbench-v2-links-and-full-g5",
        "hardware_claim": "none",
    }, "FASL latency claim drift")
    require(value["policy"] == {
        "promotion": False, "shippable": False,
        "release_authorization": "none", "hardware_g5_claim": "none",
        "installer_abi_change_included": False,
    }, "FASL release policy drift")


def load_program():
    ledger = json.loads((ROOT / "config" / "bytecode-abi-ledger.json").read_text())
    forms = {}
    for path in (
        ROOT / "lib" / "prelude-m1.lisp",
        ROOT / "lib" / "lcc-fasl.lisp",
        ROOT / "lib" / "dialect-v2" / "eval-runtime.lisp",
    ):
        for form in C.parse_all(path.read_text(encoding="utf-8")):
            if isinstance(form, list) and len(form) >= 4 and form[0] == "defun":
                forms[form[1]] = form
    missing = [name for name in TARGETS if name not in forms]
    require(not missing, "missing v2 FASL functions: %s" % ", ".join(missing))

    heap = B.Heap()
    for name in TARGETS:
        heap.intern(name)
    code_by_name = {}
    for name in TARGETS:
        entry, code = C.compile_top_form(
            forms[name], heap, strict_arity=True,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
        require(entry == name, "compiled entry drift for %s" % name)
        code_by_name[name] = code

    text = "\n".join(
        line
        for code in code_by_name.values()
        for line in B.disassemble_code_object(
            code, profile_id="dialect-v2", abi_ledger=ledger
        )
    )
    require("prim=34:" not in text, "v2 FASL writer still emits CALLPRIM 34")
    require("TAILCALL" in "\n".join(B.disassemble_code_object(
        code_by_name["%fasl-save-tail"], profile_id="dialect-v2", abi_ledger=ledger
    )), "%fasl-save-tail lost tail recursion")
    return heap, ledger, code_by_name


def sector_image(vm, track, sector):
    saved = list(vm.disk_buf)
    require(vm._disk_read_sector_impl(track, sector), "fixture sector is unreadable")
    result = list(vm.disk_buf)
    vm.disk_buf = saved
    return result


def make_fixture(capacity=600, read_faults=(), write_faults=()):
    heap, ledger, code_by_name = load_program()
    directory = {heap.intern(name): code for name, code in code_by_name.items()}
    vm = B.P0VM(
        heap=heap,
        directory=directory,
        code_names={code: name for name, code in code_by_name.items()},
        max_steps=2_000_000,
        max_call_args=12,
        disk_files={
            "SLOT": {"content": "old", "capacity": capacity},
            "GUARD": {"content": "unchanged-region", "capacity": 508},
        },
        d81_bam_model=True,
        disk_read_fail_ops=read_faults,
        disk_write_fail_ops=write_faults,
        abi_profile="dialect-v2",
        abi_ledger=ledger,
    )
    target = vm.disk_files["SLOT"]
    guard = vm.disk_files["GUARD"]
    originals = {address: sector_image(vm, *address) for address in target["sectors"]}
    guard_images = {address: sector_image(vm, *address) for address in guard["sectors"]}
    for address, image in guard_images.items():
        vm.disk_written[address] = list(image)
    protected = {
        "guard": copy.deepcopy(guard_images),
        "directory": sector_image(vm, 40, 0),
        "bam1": sector_image(vm, 40, 1),
        "bam2": sector_image(vm, 40, 2),
    }
    vm.reset_io_observation()
    return vm, code_by_name, target, originals, protected


def stage_bytes(vm, length, data=None):
    if data is None:
        data = [((index * 37) + 11) & 0xFF for index in range(length)]
    require(len(data) == length, "staged fixture length drift")
    for index, value in enumerate(data):
        require(vm.fasl_stage_put(index, value), "cannot stage fixture byte")
    vm.reset_io_observation()
    return data


def extract_payload(vm, target, length):
    payload = []
    for address in target["sectors"]:
        image = sector_image(vm, *address)
        use = 254 if image[0] else image[1] - 1
        payload.extend(image[2:2 + use])
    require(len(payload) >= length, "target chain shorter than requested payload")
    return bytes(payload[:length])


def require_invalid_l65m(payload, label):
    try:
        L65M.validate_image(payload)
    except L65M.ContractError:
        return
    raise AcceptanceError("%s reloaded as a valid L65M artifact" % label)


def run_save(vm, code_by_name, target, length):
    return vm.run(
        code_by_name["%fasl-save-staged-v2"],
        (B.mkfix(target["track"]), B.mkfix(target["sector"]), B.mkfix(length)),
    )


def chain_uses(originals, sectors):
    uses = []
    for address in sectors:
        image = originals[address]
        uses.append(254 if image[0] else image[1] - 1)
    return uses


def expected_images(originals, sectors, staged, length):
    expected = {}
    position = 0
    for address, use in zip(sectors, chain_uses(originals, sectors)):
        image = list(originals[address])
        for index in range(use):
            source = position + index
            image[index + 2] = staged[source] if source < length else 32
        expected[address] = image
        position += use
    return expected


def assert_protected(vm, target, protected):
    target_set = set(target["sectors"])
    for address, image in protected["guard"].items():
        require(vm.disk_written.get(address) == image, "guard-sector mutation at %r" % (address,))
    require(sector_image(vm, 40, 0) == protected["directory"], "directory region changed")
    require(sector_image(vm, 40, 1) == protected["bam1"], "BAM-1 region changed")
    require(sector_image(vm, 40, 2) == protected["bam2"], "BAM-2 region changed")
    unexpected = set(vm.disk_written) - target_set - set(protected["guard"])
    require(not unexpected, "writer touched sectors outside target chain: %r" % sorted(unexpected))


def check_success(length, capacity=600):
    vm, code, target, originals, protected = make_fixture(capacity=capacity)
    staged = stage_bytes(vm, length)
    result = run_save(vm, code, target, length)
    require(result == vm.heap.t_obj, "length %d did not succeed" % length)
    expected = expected_images(originals, target["sectors"], staged, length)
    for address, image in expected.items():
        require(vm.disk_written.get(address) == image, "payload mismatch at %r" % (address,))
        require(image[:2] == originals[address][:2], "link/end marker changed at %r" % (address,))

    sectors = len(target["sectors"])
    require(vm.io_counters["disk_read"] == 2 * sectors + 1, "read-op budget drift")
    require(vm.io_counters["disk_write"] == sectors + 1, "write-op budget drift")
    require(vm.io_counters["disk_poke"] == capacity + 4, "poke-op budget drift")
    require(vm.io_counters["fasl_stage_get"] == length, "stage-get budget drift")

    first = target["sectors"][0]
    writes = vm.disk_write_trace
    require((writes[0]["track"], writes[0]["sector"]) == first, "first invalidation order drift")
    require(writes[0]["bytes"][2:6] == (0, 0, 0, 0), "prefix was not invalidated first")
    require((writes[-1]["track"], writes[-1]["sector"]) == first, "first sector not committed last")
    require(list(writes[-1]["bytes"]) == expected[first], "final prefix commit mismatch")
    assert_protected(vm, target, protected)


def check_real_l65m_reload():
    golden = GOLDEN_L65M.read_bytes()
    L65M.validate_image(golden)
    vm, code, target, originals, protected = make_fixture(capacity=600)
    stage_bytes(vm, len(golden), list(golden))
    result = run_save(vm, code, target, len(golden))
    require(result == vm.heap.t_obj, "real L65M save did not succeed")
    persisted = extract_payload(vm, target, len(golden))
    require(persisted == golden, "real L65M save changed artifact bytes")
    L65M.validate_image(persisted)
    assert_protected(vm, target, protected)


def check_too_large_and_malformed():
    vm, code, target, _originals, protected = make_fixture(capacity=254)
    stage_bytes(vm, 255)
    result = run_save(vm, code, target, 255)
    require(vm.heap.obj_to_text(result) == "%fasl-too-large", "too-large sentinel drift")
    require(vm.io_counters["disk_write"] == 0, "too-large path wrote a sector")
    assert_protected(vm, target, protected)

    vm, code, target, originals, protected = make_fixture(capacity=254)
    first = target["sectors"][0]
    malformed = list(originals[first])
    malformed[0] = malformed[1] = 0
    vm.disk_written[first] = malformed
    stage_bytes(vm, 4)
    result = run_save(vm, code, target, 4)
    require(vm.heap.obj_to_text(result) == "%fasl-too-large", "malformed end marker accepted")
    require(vm.io_counters["disk_write"] == 0, "malformed chain wrote a sector")
    assert_protected(vm, target, protected)


def check_fault(write_op=None, read_op=None, label="fault"):
    vm, code, target, originals, protected = make_fixture(
        capacity=600,
        read_faults=() if read_op is None else (read_op,),
        write_faults=() if write_op is None else (write_op,),
    )
    golden = GOLDEN_L65M.read_bytes()
    stage_bytes(vm, len(golden), list(golden))
    result = run_save(vm, code, target, len(golden))
    require(result == B.NIL, "%s did not fail closed" % label)
    first = target["sectors"][0]
    if (write_op is not None and write_op > 1) or (read_op is not None and read_op > 4):
        require(vm.disk_written[first][2:6] == [0, 0, 0, 0], "%s left a valid prefix" % label)
    require(not any(
        record["success"] and record["operation"] > 1
        and (record["track"], record["sector"]) == first
        for record in vm.disk_write_trace
    ), "%s committed the first sector" % label)
    require_invalid_l65m(extract_payload(vm, target, len(golden)), label)
    assert_protected(vm, target, protected)


def check_fuel():
    vm, code, target, originals, protected = make_fixture(capacity=254)
    first = target["sectors"][0]
    cycle = list(originals[first])
    cycle[0], cycle[1] = first
    vm.disk_written[first] = cycle
    stage_bytes(vm, 4)
    result = run_save(vm, code, target, 4)
    require(vm.heap.obj_to_text(result) == "%fasl-too-large", "cyclic chain did not fail preflight")
    require(vm.io_counters["disk_read"] == 255, "fuel budget drift on cyclic chain")
    require(vm.io_counters["disk_write"] == 0, "cyclic chain wrote a sector")
    assert_protected(vm, target, protected)


def selftest():
    heap = B.Heap()
    ledger = json.loads((ROOT / "config" / "bytecode-abi-ledger.json").read_text())
    vm = B.P0VM(heap=heap, disk_read_fail_ops=(1,), disk_write_fail_ops=(1,),
                abi_profile="dialect-v2", abi_ledger=ledger)
    require(vm.fasl_stage_put(0, 0x123), "stage put failed")
    require(vm.fasl_stage_get(0) == 0x23, "stage byte truncation drift")
    require(not vm._disk_read_sector(40, 0), "read fault did not fire")
    vm.disk_buf[0] = 7
    require(not vm._disk_write_sector(1, 2), "write fault did not fire")
    require((1, 2) not in vm.disk_written, "failed write mutated disk")
    require(vm.disk_read_trace[0]["success"] is False, "read trace drift")
    require(vm.disk_write_trace[0]["success"] is False, "write trace drift")
    try:
        B.P0VM(disk_read_fail_ops=(0,))
    except ValueError:
        pass
    else:
        raise AcceptanceError("invalid fault ordinal accepted")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    validate_report(report)
    accepted = []
    for label, mutate in (
        ("reclaim", lambda value: value["link_measurement"]["net_reclaim_bytes"].update(bss=599)),
        ("promotion", lambda value: value["policy"].update(promotion=True)),
        ("commit-order", lambda value: value["persistence_acceptance"].update(commit_protocol="tail-first")),
    ):
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate_report(candidate)
        except AcceptanceError:
            continue
        accepted.append(label)
    require(not accepted, "FASL report selftest accepted: %s" % ", ".join(accepted))
    print("v2-fasl-save-host-acceptance selftest: PASS mutations=3")


def check():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    validate_report(report)
    boundary_lengths = (0, 1, 3, 4, 253, 254, 255, 256, 599, 600)
    for length in boundary_lengths:
        check_success(length)
    check_real_l65m_reload()
    check_too_large_and_malformed()
    check_fault(write_op=1, label="first-invalidation-write-fault")
    check_fault(write_op=2, label="mid-tail-write-fault")
    check_fault(read_op=5, label="mid-tail-read-fault")
    check_fault(read_op=7, label="commit-read-fault")
    check_fault(write_op=4, label="commit-write-fault")
    check_fuel()
    print(
        "v2-fasl-save-host-acceptance: PASS boundaries=%d faults=5 fuel=255"
        % len(boundary_lengths)
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
        else:
            check()
    except (AcceptanceError, B.VMError, C.CompileError, OSError, ValueError) as exc:
        print("v2-fasl-save-host-acceptance: FAIL: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
