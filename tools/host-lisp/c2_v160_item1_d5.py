#!/usr/bin/env python3
"""Prepare and record release-terminal D5 for the shipped v1.6 Item-1 world."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_name_freight_pricing as HEADROOM  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CONFIG = ROOT / "config/c2-v160-item1-d5-session.json"
CONTRACT = ROOT / "config/release-user-headroom-contract.json"
RUNNER = ROOT / "scripts/c2-v160-item1-d5-hw.sh"
DEVICE = ARCH / "c2.3-v1.6-item1-only-r1-public2-device-result-receipt.json"
MEDIA = ARCH / "c2.3-v1.6-item1-only-media-r1-public2-receipt.json"
PREPARATION = ARCH / "c2.3-v1.6-item1-d5-preparation-receipt.json"
RESULT = ARCH / "c2.3-v1.6-item1-d5-result-receipt.json"
OUT = ROOT / "build/c2.3/v1.6-item1-d5"
ROWS = OUT / "owner-row-results.json"
SHIP_COMMIT = "d03243af"
PREP_STATUS = "PASS: V1.6 ITEM-1 D5 PREPARED; OWNER CONTACT READY"
RESULT_STATUS = "PASS: V1.6 ITEM-1 D5 GREEN; CANDIDATE SEAL OPEN"


class D5Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise D5Error(message)


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


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{SHIP_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("halt a decision — ship", "loads the one-row v16core library",
                  "excludes repl-comfort", "exactly one stopped-state"):
        require(token in text, f"owner Ship authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def session_contract(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or load(CONFIG)
    roles = value.get("configuration", {})
    dance = value.get("choreography", {})
    post = value.get("headroom_postcondition", {})
    rows = value.get("rows", [])
    require(
        value.get("format") == "lisp65-c2-v160-item1-d5-session-v1"
        and value.get("status") == "prepared-not-run"
        and roles.get("loaded_library_roles") == ["v16core"]
        and roles.get("absent_library_roles") == ["repl-comfort"]
        and roles.get("library_rows") == 1
        and dance == {
            "final_stops": 1,
            "fresh_product_boot": True,
            "library_mounted_physically_through_freezer": True,
            "observation_during_active_form": 0,
            "one_form_per_submission": True,
            "owner_physical_keyboard_only": True,
            "physical_bank0_captures": 1,
            "post_boot_FTP": 0,
        }
        and len(rows) == 5
        and [row.get("id") for row in rows] == [
            "d5-setup-published-call", "d5-list-read", "d5-list-write",
            "d5-string-op", "d5-published-call"]
        and rows[0].get("form") == "(defun v16-perf-probe (x) (+ x 1))"
        and rows[-1].get("form") == "(time (v16-perf-probe 41))"
        and post.get("contract") == CONTRACT.relative_to(ROOT).as_posix()
        and post.get("counter_addresses") ==
            "accepted candidate ELF symbols nsym and npool"
        and post.get("public_repl_introspection") == 0,
        "v1.6 Item-1 D5 session contract drift")
    return value


def accepted_world() -> dict[str, Any]:
    device = load(DEVICE)
    media = load(MEDIA)
    delivered = device.get("delivered_identity", {})
    pair = delivered.get("accepted_pair", {})
    require(
        device.get("status") ==
            "PASS: V1.6 ITEM 1 HARDWARE ACCEPTED; HALT A REACHED"
        and device.get("acceptance", {}).get("item_1") == "ACCEPTED"
        and device.get("acceptance", {}).get("Halt_A") ==
            "REACHED-UNDER-OWNER-ITEM1-ONLY-DISPOSITION"
        and media.get("status") ==
            "PASS: V1.6 ITEM 1 ONLY R1 PUBLIC2 ACCEPTANCE MEDIA READY"
        and media.get("same_world_pair", {}).get("row_names") == ["v16core"]
        and media.get("same_world_pair", {}).get("index_rows") == 1
        and media.get("library_closure", {}).get("Comfort_absent") is True
        and pair == media.get("accepted_pair")
        and delivered.get("product") == media.get("media", {}).get("product")
        and delivered.get("library") == media.get("media", {}).get("library"),
        "accepted Item-1 product/library authority drift")
    for row in [pair["PRG"], pair["ELF"], delivered["product"],
                delivered["product_readback"], delivered["library"],
                delivered["library_readback"]]:
        require(bind(ROOT / row["path"]) == row,
                f"accepted D5 input identity drift: {row['path']}")
    require((ROOT / delivered["product"]["path"]).read_bytes() ==
                (ROOT / delivered["product_readback"]["path"]).read_bytes()
            and (ROOT / delivered["library"]["path"]).read_bytes() ==
                (ROOT / delivered["library_readback"]["path"]).read_bytes(),
            "accepted deployed media readback drift")
    return {"device": device, "media": media, "delivered": delivered,
            "ELF": ROOT / pair["ELF"]["path"]}


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or RUNNER.read_text(encoding="utf-8")
    require(
        "dry-run|capture-final" in source
        and source.count("--memsave") == 1
        and source.count("final-physical-bank0.bin") == 2
        and "0x00000000:0x0000c000" in source
        and "mega65_ftp" not in source and "etherload" not in source
        and "# IDLE-ONLY" in source
        and '[ -e "$OUT/rows-complete" ]' in source
        and source.index("rows-complete") < source.index("--screenshot")
        < source.index("--memsave") < source.index("verify-headroom")
        < source.rindex("final-capture-complete"),
        "v1.6 Item-1 D5 runner lifecycle drift")
    return {"physical_forms": 5, "post_boot_FTP": 0,
            "active_form_observations": 0, "final_stops": 1,
            "physical_bank0_captures": 1,
            "headroom_addresses": "accepted candidate ELF derived"}


def mutations(config: dict[str, Any], runner: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    changed = deepcopy(config)
    changed["configuration"]["loaded_library_roles"].append("repl-comfort")
    cases["load-Comfort"] = lambda: session_contract(changed)
    changed = deepcopy(config)
    changed["configuration"]["loaded_library_roles"] = []
    cases["drop-v16core"] = lambda: session_contract(changed)
    changed = deepcopy(config)
    changed["headroom_postcondition"]["counter_addresses"] = "0x005f/0x0060"
    cases["pin-counter-addresses"] = lambda: session_contract(changed)
    changed = deepcopy(config)
    changed["headroom_postcondition"]["public_repl_introspection"] = 1
    cases["add-public-introspection"] = lambda: session_contract(changed)
    runner_cases = {
        "capture-before-rows": runner.replace(
            '[ -e "$OUT/rows-complete" ]', '[ true ]', 1),
        "add-second-stop": runner.replace(
            "# The only stop and the only physical Bank-0 capture",
            'run_m65 -H --memsave "0x0:0x1=$OUT/extra.bin"\n'
            "# The only stop and the only physical Bank-0 capture", 1),
        "add-post-boot-FTP": runner.replace(
            "# IDLE-ONLY", "mega65_ftp forbidden\n# IDLE-ONLY", 1),
    }
    for name, source in runner_cases.items():
        cases[name] = lambda source=source: runner_gate(source)
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except (D5Error, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "v1.6 Item-1 D5 mutation survived")
    return rejected


def derive_preparation() -> dict[str, Any]:
    config = session_contract()
    world = accepted_world()
    source = RUNNER.read_text(encoding="utf-8")
    addresses = HEADROOM.elf_symbol_addresses(world["ELF"])
    return {
        "format": "lisp65-c2-v160-item1-d5-preparation-v1",
        "recorded_on": "2026-08-25",
        "status": PREP_STATUS,
        "authority": {
            "owner_Ship": git_authority(), "Halt_A": bind(DEVICE),
            "media": bind(MEDIA), "session": bind(CONFIG),
            "headroom_contract": bind(CONTRACT), "runner": bind(RUNNER),
            "checker": bind(Path(__file__).resolve()),
        },
        "delivered_identity": world["delivered"],
        "measurement_configuration": config["configuration"],
        "rows": config["rows"],
        "session": runner_gate(source),
        "ELF_derived_counter_addresses": {
            name: f"0x{address:04X}" for name, address in addresses.items()},
        "minimum_free": load(CONTRACT)["minimum_free"],
        "mutations_rejected": mutations(config, source),
        "execution_accounting": {"hardware_contacts": 0, "physical_forms": 0,
                                 "WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0},
        "claim_limit": config["claim_scope"],
        "next": "one owner D5 contact; fresh boot; five rows; one final stop",
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") == PREP_STATUS
        and value.get("measurement_configuration", {}).get(
            "loaded_library_roles") == ["v16core"]
        and value.get("measurement_configuration", {}).get(
            "absent_library_roles") == ["repl-comfort"]
        and len(value.get("rows", [])) == 5
        and value.get("session", {}).get("final_stops") == 1
        and value.get("session", {}).get("physical_bank0_captures") == 1
        and value.get("minimum_free") == {
            "namepool_bytes": 384, "symbol_slots": 32}
        and len(value.get("mutations_rejected", [])) == 7,
        "v1.6 Item-1 D5 preparation claim drift")
    if verify:
        require(value == derive_preparation(),
                "v1.6 Item-1 D5 preparation stale")


def verify_observed(row: dict[str, Any], observed: str) -> dict[str, Any]:
    observed = " ".join(observed.strip().split())
    oracle = row["oracle"]
    if oracle["kind"] == "exact":
        require(observed == oracle["value"],
                f"{row['id']} expected {oracle['value']}, got {observed}")
        return {"id": row["id"], "form": row["form"],
                "observed": observed, "value": observed}
    parts = observed.split(" ", 1)
    require(len(parts) == 2 and parts[0].isdigit(),
            f"{row['id']} expected '<frames> <value>', got {observed}")
    frames = int(parts[0])
    require(frames <= oracle["max_frames"] and parts[1] == oracle["value"],
            f"{row['id']} D5 oracle failed: {observed}")
    return {"id": row["id"], "form": row["form"],
            "observed": observed, "frames": frames, "value": parts[1]}


def record_row(row_id: str, observed: str) -> None:
    validate_preparation(load(PREPARATION), verify=True)
    config = session_contract()
    configured = config["rows"]
    current = load(ROWS).get("rows", []) if ROWS.exists() else []
    require(len(current) < len(configured), "all v1.6 D5 rows already recorded")
    expected = configured[len(current)]
    require(row_id == expected["id"],
            f"next D5 row is {expected['id']}, not {row_id}")
    current.append(verify_observed(expected, observed))
    OUT.mkdir(parents=True, exist_ok=True)
    ROWS.write_bytes(canonical({"format": "lisp65-c2-v160-item1-d5-rows-v1",
                                "rows": current}))
    if len(current) == len(configured):
        (OUT / "rows-complete").touch()
    print(f"v1.6 D5 row {row_id}: PASS observed={observed}")


def verify_headroom(path: Path) -> dict[str, Any]:
    world = accepted_world()
    try:
        return HEADROOM.verify_device(world["ELF"], path)
    except HEADROOM.PricingError as error:
        raise D5Error(str(error)) from error


def derive_result() -> dict[str, Any]:
    prep = load(PREPARATION)
    validate_preparation(prep, verify=True)
    require((OUT / "rows-complete").is_file()
            and (OUT / "final-capture-complete").is_file(),
            "v1.6 D5 stopped-state capture is incomplete")
    row_value = load(ROWS)
    configured = session_contract()["rows"]
    results = row_value.get("rows", [])
    require(len(results) == len(configured), "v1.6 D5 row result count drift")
    for expected, result in zip(configured, results, strict=True):
        require(result == verify_observed(expected, result["observed"]),
                f"v1.6 D5 row receipt drift: {expected['id']}")
    headroom = verify_headroom(OUT / "final-physical-bank0.bin")
    return {
        "format": "lisp65-c2-v160-item1-d5-result-v1",
        "recorded_on": "2026-08-25",
        "status": RESULT_STATUS,
        "authority": {"preparation": bind(PREPARATION),
                      "owner_rows": bind(ROWS)},
        "measurement_configuration": prep["measurement_configuration"],
        "delivered_identity": prep["delivered_identity"],
        "rows": results,
        "D5_user_headroom": headroom,
        "idle_screen": {"image": bind(OUT / "final-idle.png"),
                        "text": bind(OUT / "final-idle.txt"),
                        "red_frame": False},
        "execution_accounting": {"hardware_contacts": 1,
                                 "physical_forms": 5,
                                 "post_boot_FTP": 0, "final_stops": 1,
                                 "physical_bank0_captures": 1,
                                 "WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0},
        "claim_limit": prep["claim_limit"],
        "next": "candidate-seal",
    }


def validate_result(value: dict[str, Any], *, verify: bool) -> None:
    free = value.get("D5_user_headroom", {}).get("free", {})
    require(
        value.get("status") == RESULT_STATUS
        and value.get("measurement_configuration", {}).get(
            "loaded_library_roles") == ["v16core"]
        and value.get("measurement_configuration", {}).get(
            "absent_library_roles") == ["repl-comfort"]
        and len(value.get("rows", [])) == 5
        and free.get("symbol_slots", -1) >= 32
        and free.get("namepool_bytes", -1) >= 384
        and value.get("idle_screen", {}).get("red_frame") is False
        and value.get("execution_accounting", {}).get("final_stops") == 1
        and value.get("next") == "candidate-seal",
        "v1.6 Item-1 D5 result claim drift")
    if verify:
        require(value == derive_result(), "v1.6 Item-1 D5 result stale")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "record-row",
                                           "verify-headroom", "record",
                                           "result-check"))
    parser.add_argument("--row")
    parser.add_argument("--observed")
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREPARATION.exists(), "v1.6 Item-1 D5 preparation exists")
        PREPARATION.write_bytes(canonical(derive_preparation()))
        print("v1.6 Item-1 D5 preparation: PASS rows=5 stop=1")
    elif args.action == "check":
        validate_preparation(load(PREPARATION), verify=True)
        print("v1.6 Item-1 D5 preparation: CHECK PASS rows=5 stop=1")
    elif args.action == "record-row":
        require(args.row is not None and args.observed is not None,
                "record-row requires --row and --observed")
        record_row(args.row, args.observed)
    elif args.action == "verify-headroom":
        require(args.path is not None, "verify-headroom requires --path")
        result = verify_headroom(args.path)
        print("v1.6 D5 headroom: PASS " + json.dumps(
            result["free"], sort_keys=True))
    elif args.action == "record":
        require(not RESULT.exists(), "v1.6 Item-1 D5 result exists")
        value = derive_result()
        RESULT.write_bytes(canonical(value))
        print("v1.6 Item-1 D5: PASS candidate-seal-open")
    else:
        validate_result(load(RESULT), verify=True)
        print("v1.6 Item-1 D5 result: CHECK PASS candidate-seal-open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D5Error, HEADROOM.PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"v1.6 Item-1 D5: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
