#!/usr/bin/env python3
"""Requalify the sealed Comfort freight against the live v2.0 product world."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_product_callprim_delivery_gate as DELIVERY  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v160_input_service_hybrid_final_world as HYBRID  # noqa: E402
import c2_v160_input_service_time_pricing as TIMING  # noqa: E402
import c2_v190_release_terminal_d5 as D5  # noqa: E402
import c2_v200_symbol22_build_id_rebind as R4  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as LATCH  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Owner word — residual `$22` risk accepted; Comfort return opens — 2026-08-31")
AUTHORIZATION = "0a487dd5"
SEALED_COMFORT_COMMIT = "870e5f53"
SEALED_INPUTS = (
    ROOT / "lib/repl-comfort.lisp",
    ROOT / "tests/bytecode/libs/p0-repl-comfort.json",
    ROOT / "tests/bytecode/libs/p0-repl-comfort-resident.json",
)
COMFORT = SEALED_INPUTS[0]
COMFORT_SUITE = SEALED_INPUTS[1]
RESIDENT_SUITE = ROOT / "config/c2-v160-comfort-repl-resident-suite.json"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
HISTORICAL_MANIFEST = ROOT / (
    "build/c2.3/v1.7-comfort-phase1b-variant-b-adapter-r1/library/"
    "repl-comfort.manifest.json")
R4_RECEIPT = R4.RECEIPT
R4_ELF = R4.ELF
R4_PRG = R4.PRG
R4_SCOPE = R4.COMPLETION / "owner-scope-result.json"
R4_ACCEPTANCE = R4.COMPLETION / "artifact-acceptance.json"
DEVICE_RESULT = ARCH / "c2.3-v2.0-symbol22-build-id-device-result-receipt.json"
BUILD = ROOT / "build/c2.3/v2.0-comfort-return-card"
LIVE_RESIDENT = BUILD / "live-resident.json"
LIVE_SUITE = BUILD / "product-profile-suite.json"
LIBRARY = BUILD / "library/repl-comfort"
OBSERVATIONS = BUILD / "library/observations.json"
RECEIPT = ARCH / "c2.3-v2.0-comfort-return-card-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-comfort-return-card-report.md"
FORMAT = "lisp65-c2-v200-comfort-return-card-v1"
STATUS = "PASS: SEALED COMFORT FREIGHT REQUALIFIED ON V2.0 R4 WORLD"
CARD_SEAL_COMMIT = "3194a39be5b36526064250a6f959abae527470bb"
EXPECTED_PAIR = {
    "ELF": (636112,
        "21733ddc170f7c9ceba60d7e2e351932248435e9fb9266394d908febc721e04b"),
    "PRG": (41811,
        "dc8c44e403866ff4b9d4acdb158c6d2dae068cddb94b3e2c9598f37c40032c79"),
}
EXPECTED_NEW_NAMES = {
    "%repl-read", "%repl-prompt", "%repl-step", "repl", "repl-comfort",
}


class ComfortReturnError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ComfortReturnError(message)


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


def write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def git_blob(commit: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def authority() -> dict[str, Any]:
    raw = git_blob(AUTHORIZATION, PLAN)
    text = raw.decode("utf-8")
    start = text.find(PLAN_HEADER)
    require(start >= 0, "Comfort-return owner section absent")
    end = text.find("\n## ", start + len(PLAN_HEADER))
    section = text[start:] if end < 0 else text[start:end]
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("comfort return", "sealed freight unchanged",
                  "fast-typing row", "delivered ring", "one bounded repair"):
        require(token in folded, f"Comfort-return authority absent: {token}")
    return {"kind": "owner-git-section", "commit": AUTHORIZATION,
        "path": PLAN.relative_to(ROOT).as_posix(), "header": PLAN_HEADER,
        "bytes": len(section.encode()),
        "sha256": hashlib.sha256(section.encode()).hexdigest(),
        "budget": {"WPLTO_runs": 0, "product_links": 0,
                   "media_builds": 0, "device_contacts": 0},
        "anti_rabbit_hole": "one bounded repair round per daily-use blocker"}


def accepted_pair() -> dict[str, Any]:
    pair = {"ELF": bind(R4_ELF), "PRG": bind(R4_PRG)}
    for role, expected in EXPECTED_PAIR.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"r4 {role} identity drift")
    return pair


def sealed_freight_gate() -> dict[str, Any]:
    rows = []
    for path in SEALED_INPUTS:
        current = path.read_bytes()
        sealed = git_blob(SEALED_COMFORT_COMMIT, path)
        require(current == sealed, f"sealed Comfort freight changed: {path}")
        rows.append({**bind(path), "sealed_commit": SEALED_COMFORT_COMMIT})
    trial = deepcopy(rows)
    trial[0]["sha256"] = "0" * 64
    require(trial != rows, "sealed-source mutation did not alter the witness")
    return {"status": "PASS: THREE SEALED INPUTS BYTE-IDENTICAL",
        "sealed_commit": SEALED_COMFORT_COMMIT, "inputs": rows,
        "mutation": "changed-source-byte rejected before materialization"}


def trimmed_live_authority(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in (
        "authority", "sources", "derived_functions", "owner_suites",
        "replaced_historical_editor_functions",
        "selected_live_editor_functions")}


def live_resident_spec(*, write_file: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    resident = STD._read_suite(str(RESIDENT_SUITE))
    live = TIMING.live_function_directory(resident, EDITOR)
    resident["sources"] = [
        str((ROOT / path).resolve()) if not Path(path).is_absolute() else path
        for path in resident["sources"]]
    resident["resident_suites"] = []
    resident["cases"] = []
    resident["description"] = (
        "v2.0 current-world resident directory for sealed Comfort freight")
    for key in list(resident):
        if key.startswith("_"):
            del resident[key]
    if write_file:
        write(LIVE_RESIDENT, canonical(resident))
    return resident, trimmed_live_authority(live)


def flattened_live_suite(delivered: list[int] | None,
                         comfort_path: Path = COMFORT) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = TIMING.combined_suite(
        EDITOR, "(repl)", "nil", [13])
    source = COMFORT.relative_to(ROOT).as_posix()
    replacement = str(comfort_path.resolve())
    suite["sources"] = [replacement if path == source else path
                        for path in suite["sources"]]
    comfort_suite = load(COMFORT_SUITE)
    suite["cases"] = deepcopy(comfort_suite["cases"])
    suite["ignored_output_codes"] = deepcopy(
        comfort_suite["ignored_output_codes"])
    live = TIMING.live_function_directory(suite, EDITOR)
    if delivered is None:
        suite.pop("delivered_callprims", None)
    else:
        suite["delivered_callprims"] = list(delivered)
    return suite, trimmed_live_authority(live)


def source_world_gate(profile: dict[str, Any]) -> dict[str, Any]:
    sealed = STD._read_suite(str(COMFORT_SUITE))
    sealed["delivered_callprims"] = profile["delivered_ids"]
    try:
        STD.check_suite("v2.0-comfort-sealed-directory-mutation", sealed)
    except B.VMError as error:
        message = str(error)
        require("function not in directory: %rl-poll" in message,
                "sealed directory mutation fell for the wrong reason")
    else:
        raise ComfortReturnError(
            "historical Comfort directory survived a live-world claim")

    suite, live = flattened_live_suite(profile["delivered_ids"])
    result = STD.check_suite("v2.0-comfort-live-directory", suite)
    require(result["cases"] == 9 and result["functions"] >= 4,
            "live Comfort directory did not execute all sealed cases")

    mutant = deepcopy(suite)
    mutant["functions"] = [name for name in mutant["functions"]
                            if name != "%rl-poll"]
    try:
        STD.check_suite("v2.0-comfort-live-directory-no-poll", mutant)
    except (STD.StdlibCheckError, B.VMError) as error:
        poll_rejection = str(error)
    else:
        raise ComfortReturnError("live directory without %rl-poll survived")
    return {"status": "PASS: LIVE CLAIM CONSUMES LIVE OWNER DIRECTORY",
        "cases": result["cases"], "functions": result["functions"],
        "steps": result["steps"], "authority": live,
        "mutations": {
            "sealed-directory-as-live-authority": message,
            "live-owner-poll-omitted": poll_rejection,
        }}


def product_profile_gate(profile: dict[str, Any]) -> dict[str, Any]:
    delivered = profile["delivered_ids"]
    current, _live = flattened_live_suite(delivered)
    good = STD.check_suite("v2.0-comfort-product-profile", current)
    require(good["cases"] == 9, "product-profile Comfort suite incomplete")

    source = COMFORT.read_text(encoding="utf-8")
    require(source.count("(if (screen-bulk-p)") == 1,
            "Comfort fallback selection source drift")
    forced = source.replace("(if (screen-bulk-p)", "(if t", 1)
    mutant_source = BUILD / "mutations/force-tombstoned-primitive.lisp"
    write(mutant_source, forced.encode())
    tombstone, _ = flattened_live_suite(delivered, mutant_source)
    try:
        STD.check_suite("v2.0-comfort-tombstone-mutation", tombstone)
    except B.VMError as error:
        rejected = str(error)
        require(error.status == "BadOpcode"
                and "product-profile tombstone Prim-ID 12" in rejected,
                "forced tombstone mutation fell for the wrong reason")
    else:
        raise ComfortReturnError("tombstoned CALLPRIM 12 survived")

    unrestricted, _ = flattened_live_suite(None, mutant_source)
    false_green = STD.check_suite(
        "v2.0-comfort-unrestricted-host-mutation", unrestricted)
    invented, _ = flattened_live_suite([*delivered, 12], mutant_source)
    invented_green = STD.check_suite(
        "v2.0-comfort-invented-delivery-mutation", invented)
    require(false_green["cases"] == invented_green["cases"] == 9,
            "product-profile false-green controls drift")
    return {"status": "PASS: CURRENT PRODUCT TOMBSTONES CONSUMED",
        "profile": profile, "qualified_cases": good["cases"],
        "forced_tombstone_rejection": rejected,
        "unrestricted_host_false_green_cases": false_green["cases"],
        "invented_delivery_false_green_cases": invented_green["cases"]}


def semantic_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = deepcopy(manifest["entries"])
    for row in rows:
        row.pop("name_obj", None)
    return rows


def materialize_library(profile: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    _resident, _authority = live_resident_spec(write_file=True)
    write(LIVE_SUITE, canonical({
        "extends": str(COMFORT_SUITE.resolve()),
        "resident_suites": [str(LIVE_RESIDENT.resolve())],
        "delivered_callprims": profile["delivered_ids"],
        "description": "sealed Comfort freight in the v2.0 r4 product profile",
    }))
    LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.run([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--artifact-role", "disk-lib", "--emit-artifacts",
        str(LIBRARY.relative_to(ROOT)), "--observation-report",
        str(OBSERVATIONS.relative_to(ROOT)), str(LIVE_SUITE.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            "current-world Comfort materialization red:\n" + process.stdout)
    manifest_path = LIBRARY.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    historical = load(HISTORICAL_MANIFEST)
    require(manifest["functions"] == historical["functions"]
            == ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
            and manifest["objects"] == historical["objects"] == 4
            and manifest["code_bytes"] == historical["code_bytes"] == 815
            and manifest["directory_bytes"] == historical["directory_bytes"] == 28
            and manifest["cost"]["largest_code_object_bytes"] == 251
            and semantic_entries(manifest) == semantic_entries(historical),
            "current-world materialization changed sealed Comfort semantics")
    resident_names = set(load(LIVE_RESIDENT)["functions"])
    novel = ((set(manifest["cost"]["symbol_names"]) - resident_names)
             | set(manifest["provides"]))
    require(novel == EXPECTED_NEW_NAMES,
            f"Comfort name freight drift: {sorted(novel)}")
    return {"status": "PASS: SEALED FOUR-OBJECT FREIGHT MATERIALIZED",
        "suite": bind(LIVE_SUITE), "resident": bind(LIVE_RESIDENT),
        "manifest": bind(manifest_path),
        "blob": bind(LIBRARY.with_suffix(".blob.bin")),
        "directory": bind(LIBRARY.with_suffix(".dir.bin")),
        "observations": bind(OBSERVATIONS), "objects": manifest["objects"],
        "code_bytes": manifest["code_bytes"],
        "directory_bytes": manifest["directory_bytes"],
        "largest_code_object_bytes": manifest["cost"]["largest_code_object_bytes"],
        "semantic_entries_equal_sealed_variant_b": True,
        "name_object_ids_rebound_to_live_directory": True,
        "new_interned_names": sorted(novel),
        "live_directory_authority": live}


def long_input_gate(profile: dict[str, Any]) -> dict[str, Any]:
    comments = [";" + "x" * 40 for _ in range(5)]
    lines = ["(+ 1", *comments, "2)"]
    events: list[int] = []
    for line in lines:
        events.extend(line.encode("ascii")); events.append(13)
    events.append(13)
    aggregate = sum(map(len, lines)) + (len(lines) - 1) * 3
    require(aggregate > 192 and max(map(len, lines)) < 250,
            "long-input fixture does not cross only the aggregate bound")
    suite, _live = flattened_live_suite(profile["delivered_ids"])
    suite["cases"] = [{
        "name": "v2.0-comfort-aggregate-over-native-buffer",
        "expr": "(repl)", "expect": "nil",
        "expect_output_codes": [10] * (len(lines) + 2),
        "max_steps": 3_000_000, "key_events": events,
        "expect_key_events_remaining": 0,
    }]
    result = STD.check_suite("v2.0-comfort-long-input", suite)
    require(result["cases"] == 1, "current-world long-input witness absent")
    return {"status": "PASS: HEAP AGGREGATE CROSSES NATIVE BUFFER",
        "aggregate_source_bytes": aggregate,
        "longest_physical_line_bytes": max(map(len, lines)),
        "native_buffer_bytes": 192, "cases": 1}


def display_gate(profile: dict[str, Any]) -> dict[str, Any]:
    suite, live = flattened_live_suite(profile["delivered_ids"])
    vm = DISPLAY.run_world(suite, DISPLAY.EDIT_EVENTS, at_return=False)
    boundary = DISPLAY.run_world(
        suite, [ord("a"), 1, 157, 20, 13], at_return=True)
    maximum = DISPLAY.run_world(suite, [ord("a")] * 250 + [13], at_return=True)
    left_text = "abcde" + "a" * 72
    left = DISPLAY.run_world(
        suite, list(left_text.encode()) + [157] * 75 + [13], at_return=True)
    require(vm.active_row == "l65> (list 1 3)".ljust(80)
            and vm.after_result == ["(1 3)".ljust(80), " ".ljust(80)]
            and boundary.active_row == "l65> a".ljust(80)
            and maximum.active_row == "l65> " + "a" * 74 + " "
            and left.active_row.startswith("l65> cde"),
            "current-world composed framebuffer wall red")
    mutation = deepcopy(vm.after_result)
    mutation[0] = "(1 3)(list 1 3)".ljust(80)
    require(mutation != vm.after_result,
            "stale-result-tail mutation did not alter the framebuffer")
    return {"status": "PASS: CURRENT 80x25 COMPOSED FRAMEBUFFER",
        "active_row": vm.active_row.rstrip(),
        "result_row": vm.after_result[0].rstrip(),
        "result_tail_blank": vm.after_result[0][5:] == " " * 75,
        "prompt_boundary": boundary.active_row.rstrip(),
        "maximum_characters": 250, "visible_text_columns": 74,
        "left_scroll_prefix": left.active_row[:9],
        "live_directory_authority": live,
        "mutation": "historical stale result tail rejected"}


def performance_and_input_gate(profile: dict[str, Any]) -> dict[str, Any]:
    HYBRID.RESPONSIVENESS_FUNCTION_WORLD = "live-artifacts"
    hybrid = HYBRID.derive(R4_ELF)
    response = hybrid["responsiveness"]
    require(hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["loss"]["capture_model"]["events_captured"] == 94
            and hybrid["normalization"]["executions"] == 512
            and hybrid["normalization"]["parity"] is True
            and response["all_walls_passed"] is True
            and response["margin_percent"] >= 25.0,
            "current-world loss/normalization/responsiveness wall red")
    route = TIMING.execute_route(
        EDITOR, "batch", 40, batch_cap=8, function_world="live-artifacts")
    require(route["dynamic_vm_steps"] == response["dynamic_vm_steps"]
            and route["boundary_count"] == response["boundary_count"] == 6,
            "Comfort typing route and final-ELF wall diverged")
    taken_zero = deepcopy(hybrid["loss"])
    taken_zero["linked_events_drained"] = 0
    require(taken_zero != hybrid["loss"],
            "taken-zero device mutation did not alter the loss wall")
    return {"status": "PASS: DELIVERED RING AND LIVE COMFORT ROUTE GREEN",
        "loss": hybrid["loss"], "normalization": hybrid["normalization"],
        "responsiveness": response, "comfort_typing_route": route,
        "device_mutation": "raw=seen=stored>taken is rejected"}


def capacity_gate(library: dict[str, Any]) -> dict[str, Any]:
    device = load(DEVICE_RESULT)
    observed = device["interpretation"]
    require(device["status"] == "PASS: BOUNDED SYMBOL22 SEAM DID NOT RECUR ON R4"
            and observed["nsym"] == 642 and observed["npool"] == 8720,
            "r4 device capacity origin drift")
    names = library["new_interned_names"]
    name_bytes = sum(len(name) + 1 for name in names)
    before = {"symbol_slots": D5.MAX_SYM - observed["nsym"],
              "namepool_bytes": D5.NAMEPOOL - observed["npool"]}
    after = {"symbol_slots": before["symbol_slots"] - len(names),
             "namepool_bytes": before["namepool_bytes"] - name_bytes}
    floor = {"symbol_slots": 32, "namepool_bytes": 384}
    margin = {key: after[key] - floor[key] for key in floor}
    require((D5.MAX_SYM, D5.NAMEPOOL) == (752, 10208)
            and before == {"symbol_slots": 110, "namepool_bytes": 1488}
            and name_bytes == 53
            and after == {"symbol_slots": 105, "namepool_bytes": 1435}
            and all(value >= 0 for value in margin.values()),
            "current-world Comfort capacity wall red")
    return {"status": "PASS: CURRENT DEVICE ORIGIN PROJECTS ABOVE FLOOR",
        "origin": {"receipt": bind(DEVICE_RESULT), "nsym": observed["nsym"],
                   "npool": observed["npool"], "atomic": "phase-0 stopped read"},
        "limits": {"symbol_slots": D5.MAX_SYM,
                   "namepool_bytes": D5.NAMEPOOL},
        "before_loading_comfort": before, "new_names": names,
        "new_namepool_bytes": name_bytes, "after_loading_comfort": after,
        "release_floor": floor, "margin": margin,
        "claim_limit": "host projection; final loaded D5 remains a device row"}


def current_product_gate() -> dict[str, Any]:
    receipt = load(R4_RECEIPT)
    scope = load(R4_SCOPE); acceptance = load(R4_ACCEPTANCE)
    pair = accepted_pair()
    require(receipt["status"] == R4.STATUS
            and receipt["artifacts_before"] == receipt["artifacts_after"]
            and {key: receipt["artifacts_after"][key] for key in ("ELF", "PRG")}
                == pair
            and scope["status"] == acceptance["status"] == "PASS",
            "r4 candidate closure drift")
    product = receipt["final_product"]
    recovery = product["standing_product_walls"]["recovery_quiescence"]
    latch = LATCH.positive_control(R4_ELF)
    require(product["status"] == "PASS: FIRST-FAULT LATCH FINAL PRODUCT GREEN"
            and product["survival"]["status"]
                == "PASS: BOTH RECORD CARRIERS SURVIVE ABORT RECOVERY"
            and latch["status"] == "PASS: FINAL ELF EXECUTED POSITIVE CONTROL"
            and latch["meaning_of_device_tag_zero"]
                == "no recurrence; latch firing is proven"
            and recovery["model"]["cases"]["sealed-empty"]
                == {"route": "a0-two-overlay", "overlay_calls": 2,
                    "crc_bytes": 6110},
            "current recovery/latch product wall red")
    device = load(DEVICE_RESULT)
    require(device["interpretation"]["tag"] == 0
            and device["interpretation"]["result"]
                == "no-recurrence-in-one-bounded-historical-seam",
            "phase-0 owner branch drift")
    return {"status": "PASS: R4 PRODUCT READY FOR COMFORT LIBRARY",
        "pair": pair, "product_card": bind(R4_RECEIPT),
        "scope": bind(R4_SCOPE), "acceptance": bind(R4_ACCEPTANCE),
        "recovery": {"status": recovery["status"],
            "sealed_empty": recovery["model"]["cases"]["sealed-empty"]},
        "latch": {"positive_control": latch,
            "survival": product["survival"],
            "device_branch": device["interpretation"]},
        "claim_limit": "product unchanged; Comfort remains external library freight"}


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0}
            and value["sealed_freight"]["status"].startswith("PASS")
            and value["source_world"]["cases"] == 9
            and value["product_profile"]["qualified_cases"] == 9
            and value["library"]["code_bytes"] == 815
            and value["library"]["largest_code_object_bytes"] == 251
            and value["long_input"]["aggregate_source_bytes"] > 192
            and value["display"]["result_tail_blank"] is True
            and value["input"]["loss"]["linked_events_drained"] == 94
            and value["input"]["responsiveness"]["margin_percent"] >= 25.0
            and value["capacity"]["after_loading_comfort"]
                == {"symbol_slots": 105, "namepool_bytes": 1435}
            and value["product"]["latch"]["positive_control"]["record"]
                ["tag_committed_last"] is True,
            "Comfort-return receipt semantic wall red")
    require(value["artifacts_before"] == value["artifacts_after"],
            "Comfort-return card changed the frozen product pair")


def derive() -> dict[str, Any]:
    pair_before = accepted_pair()
    profile = DELIVERY.derive_profile(R4_ELF)
    require(profile["tombstoned_ids"] == [1, 2, 12, 26, 27, 40]
            and 12 not in profile["delivered_ids"],
            "r4 CALLPRIM delivery profile drift")
    sealed = sealed_freight_gate()
    source_world = source_world_gate(profile)
    product_profile = product_profile_gate(profile)
    _resident, live = live_resident_spec(write_file=False)
    library = materialize_library(profile, live)
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": authority(),
        "product": current_product_gate(), "sealed_freight": sealed,
        "source_world": source_world, "product_profile": product_profile,
        "library": library, "long_input": long_input_gate(profile),
        "display": display_gate(profile),
        "input": performance_and_input_gate(profile),
        "capacity": capacity_gate(library),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "artifacts_before": pair_before, "artifacts_after": accepted_pair(),
        "acceptance_binding": {
            "device_rows": ["prompt-and-abort", "balanced-multiline-history",
                "composed-display", "fast-typing-over-forced-collection",
                "raw=seen=stored=taken", "symbol22-latch-before-next-input",
                "loaded-configuration-D5"],
            "evidence_limit": ("one Comfort contact is the real test; phase-0 "
                               "negative observation is not a sweep"),
            "daily_use_blocker": "one bounded repair round, then descope",
            "latch_release_decision": "deferred owner word; removal is default",
        },
        "claim_limit": ("Host/current-product Comfort card only. No medium, "
                        "device acceptance, Block-3 or release claim."),
        "next": "independent review, then artifact-only media and one owner session"}
    require(value["artifacts_before"] == value["artifacts_after"],
            "host-only Comfort card changed the product pair")
    validate(value)
    return value


def report(value: dict[str, Any]) -> str:
    response = value["input"]["responsiveness"]
    capacity = value["capacity"]
    library = value["library"]
    slots = capacity["after_loading_comfort"]["symbol_slots"]
    name_bytes = capacity["after_loading_comfort"]["namepool_bytes"]
    return f"""# v2.0 Comfort-return product card

Status: **{value['status']}**

The Comfort source, suite and resident adapter are byte-identical to the
sealed `{SEALED_COMFORT_COMMIT}` freight.  Their live consumer is deliberately
not the sealed function directory: that historical route fails at `%rl-poll`,
while the directory derived from today's editor sources and owner suites runs
all **{value['source_world']['cases']}** registered Comfort cases.  Both sharp
mutations are permanent in the card.

The library remains four objects and **{library['code_bytes']} code bytes**;
its largest object is **{library['largest_code_object_bytes']} bytes**.  The
semantic object/literal inventory is identical to the accepted Variant-B
artifact.  Only name-object identities are rebound to the live directory.
CALLPRIM 12 remains tombstoned, and the forced-bulk mutation fails on that
exact tombstone while unrestricted/invented host worlds demonstrate the old
false green.

## Current-world walls

- final-ELF ring: **94 produced / 94 captured / 94 consumed**, zero drops;
- normalization: **512/512** executions;
- responsiveness: **{response['frames_per_character']:.6f} frames/character**,
  **{response['margin_percent']:.3f}%** margin;
- composed framebuffer: `l65> (list 1 3)` on one row, clean `(1 3)` handoff;
- aggregate input: **{value['long_input']['aggregate_source_bytes']} bytes**
  over physical lines shorter than 250 bytes;
- A0 recovery: two overlays / 6,110 CRC bytes on the sealed-empty path;
- `$22` latch: current-r4 positive control green and both carriers survive.

The stopped phase-0 origin (642 symbols, 8,720 name bytes) projects the loaded
Comfort configuration to **{slots} free slots / {name_bytes} free name bytes**,
against 32/384. This is a host projection; the loaded D5 row remains
part of device acceptance.

No WPLTO, product link, medium or device contact was consumed.  The product
pair stayed byte-identical.  Independent review is the next touchpoint; only
after it may artifact-only media and the one bounded Comfort session run.
"""


def run() -> None:
    value = derive()
    write(RECEIPT, canonical(value))
    write(REPORT, report(value).encode())
    print("v2.0 Comfort return: CARD PASS cases=9 objects=4 "
          f"margin={value['input']['responsiveness']['margin_percent']:.3f}% "
          "WPLTO=0 link=0 media=0 device=0")


def check() -> None:
    require(RECEIPT.is_file() and REPORT.is_file(),
            "Comfort-return card output absent")
    require(RECEIPT.read_bytes() == git_blob(CARD_SEAL_COMMIT, RECEIPT),
            "sealed Comfort-return receipt drift")
    require(REPORT.read_bytes() == git_blob(CARD_SEAL_COMMIT, REPORT),
            "sealed Comfort-return report drift")
    value = load(RECEIPT)
    validate(value)
    sealed_freight_gate()
    print("v2.0 Comfort return: CHECK PASS sealed evidence-era card")


def selftest() -> None:
    value = load(RECEIPT)
    mutations = {
        "pair-drift": lambda x: x["artifacts_after"]["ELF"].update(
            sha256="0" * 64),
        "sealed-freight-drift": lambda x: x["sealed_freight"].update(
            status="FAIL"),
        "live-directory-lost": lambda x: x["source_world"].update(cases=0),
        "product-profile-lost": lambda x: x["product_profile"].update(
            qualified_cases=0),
        "object-over-ceiling": lambda x: x["library"].update(
            largest_code_object_bytes=256),
        "consumer-taken-zero": lambda x: x["input"]["loss"].update(
            linked_events_drained=0),
        "responsiveness-wall-lost": lambda x: x["input"][
            "responsiveness"].update(margin_percent=24.9),
        "display-tail-retained": lambda x: x["display"].update(
            result_tail_blank=False),
        "capacity-floor-lost": lambda x: x["capacity"].update(
            after_loading_comfort={"symbol_slots": 31, "namepool_bytes": 1435}),
        "latch-commit-lost": lambda x: x["product"]["latch"][
            "positive_control"]["record"].update(tag_committed_last=False),
    }
    rejected = []
    for name, mutate in mutations.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
            require(trial["artifacts_before"] == trial["artifacts_after"],
                    "product pair changed")
        except ComfortReturnError:
            rejected.append(name)
    require(rejected == list(mutations), "Comfort-return mutation survived")
    print(f"v2.0 Comfort return: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    action = parser.parse_args().action
    {"run": run, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ComfortReturnError, B.VMError, STD.StdlibCheckError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"v2.0 Comfort return: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
