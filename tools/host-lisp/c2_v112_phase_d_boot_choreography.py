#!/usr/bin/env python3
"""Bind Link-92 D1 boot choreography to the hardware-green v1.3 precedent."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import r3_product_block as D81  # noqa: E402

CONFIG = ROOT / "config/c2-v112-link92-phase-d-boot-choreography.json"
SCRIPT = ROOT / "scripts/c2-v112-link92-phase-d-boot-hw.sh"
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d1-autoboot-first-red.json")
SHIP_SCRIPT = ROOT / "scripts/c2-ship-builder-v1-hw.sh"
WORKBENCH_SCRIPT = ROOT / "scripts/c2-v13-closing-hw.sh"
SHIP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link84-closing-device-receipt.json")
LINK88_SCRIPT = ROOT / "scripts/c2-v13-link88-interactive-human-test-hw.sh"
LINK88_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link88-interactive-human-device-receipt.json")
MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-split-media-readback-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-boot-choreography-diff-receipt.json")
CALENDAR_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-restart-calendar-first-red.json")
RECORDED_ON = "2026-08-07"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"binding absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") ==
            "lisp65-c2-v112-link92-phase-d-boot-choreography-v1",
            "boot choreography format drift")
    require(
        value.get("status") == "owner-authorized-split-media-phase-d-restart"
        and value.get("authorization_commit") == "a33a438d"
        and value.get("restart_authorization_commit") == "a1cf5b9b",
        "D1 owner authorization chain drift",
    )
    d1 = value.get("d1", {})
    require(d1.get("media_sha256") ==
            "ed4e5c7281913e351550f10533a585c2516a7a0a4214a66cf93cf35252aee306",
            "D1 media identity drift")
    require(d1.get("remote") == "V14L92.D81",
            "D1 mounted image association drift")
    require(d1.get("drive") == 8, "D1 drive association drift")
    require(d1.get("autoboot_member") == "autoboot.c65"
            and d1.get("autoboot_type") == "PRG",
            "D1 AUTOBOOT member contract drift")
    require(d1.get("cold_reset") == "m65 -F"
            and d1.get("fresh_basic_assert") is True,
            "D1 cold-reset/fresh-BASIC precondition drift")
    require(d1.get("ftp_flags") == ["-0", "5", "-F"]
            and d1.get("ftp_mount_and_reset_exit") is True,
            "D1 precedent FTP mount/reset contract drift")
    require(d1.get("post_mount_explicit_resets") == 0,
            "D1 redundant post-mount reset reintroduced")
    require(d1.get("quiet_seconds_before_first_observation") == 45,
            "D1 first observation precedes proven Workbench convergence floor")
    require(d1.get("expected_banner") == "WORKBENCH 1.4.0"
            and d1.get("expected_prompt") == "lisp65>"
            and d1.get("fail_closed_frame_check") is True,
            "D1 visible AUTOBOOT postcondition drift")


def boot_order(source: str) -> str:
    begin = "# BOOT-ORDER-BEGIN"
    end = "# BOOT-ORDER-END"
    require(source.count(begin) == 1 and source.count(end) == 1,
            "D1 boot-order ownership markers drift")
    return source.split(begin, 1)[1].split(end, 1)[0]


def validate_script(source: str) -> None:
    order = boot_order(source)
    tokens = [
        "fresh_start D1",
        "ftp_package D1",
        'sleep "$quiet"',
        "capture_screen D1-banner",
        'fail_if_red "$OUT/D1-banner.png"',
        'grep -Fq "$banner" "$OUT/D1-banner.txt"',
        'grep -Fq "$prompt" "$OUT/D1-banner.txt"',
    ]
    positions = []
    for token in tokens:
        require(order.count(token) == 1, f"D1 boot token drift: {token}")
        positions.append(order.index(token))
    require(positions == sorted(positions), "D1 boot-order precedence drift")
    require("run_m65 -F" not in order,
            "D1 explicit reset appears after FTP mount")
    for token in (
        "run_m65 -F", "capture_screen \"$prefix-fresh-basic\"",
        "grep -Eqi 'BASIC 65|READY\\.'",
        "! grep -q 'lisp65>'",
        '"$FTP" -0 5 -F', '-c "put $media $remote"',
        '-c "get $remote $readback"', '-c "mount $remote" -c exit',
        'cmp "$media" "$readback"',
    ):
        require(token in source, f"D1 precedent implementation absent: {token}")


def validate_recording_authority(source: str) -> None:
    evaluate_source = source.rsplit("\ndef evaluate", 1)[1].split("\ndef selftest", 1)[0]
    require('"recorded_on": RECORDED_ON' in evaluate_source
            and "date.today()" not in evaluate_source,
            "D1 receipt calendar tag must remain historical, not recomputed")


def validate_registration(source: str) -> None:
    require("c2-v112-phase-d-boot-choreography-selftest:" in source
            and ("python3 tools/host-lisp/"
                 "c2_v112_phase_d_boot_choreography.py selftest") in source
            and ("check-source: "
                 "c2-v112-phase-d-boot-choreography-selftest") in source,
            "D1 boot-choreography permanent gate registration drift")


def rejected_mutations(contract: dict[str, Any], source: str,
                       driver_source: str) -> list[str]:
    mutations: list[tuple[str, dict[str, Any]]] = []

    def changed(name: str, key: str, value: Any) -> None:
        candidate = deepcopy(contract)
        candidate["d1"][key] = value
        mutations.append((name, candidate))

    changed("media-identity-dimmed", "media_sha256", "00" * 32)
    changed("wrong-drive", "drive", 9)
    changed("wrong-mounted-image", "remote", "OTHER.D81")
    changed("autoboot-type-dimmed", "autoboot_type", "SEQ")
    changed("fresh-basic-assert-removed", "fresh_basic_assert", False)
    changed("ftp-reset-semantics-dimmed", "ftp_mount_and_reset_exit", False)
    changed("redundant-post-mount-reset", "post_mount_explicit_resets", 1)
    changed("historical-30-second-look", "quiet_seconds_before_first_observation", 30)
    changed("banner-assert-removed", "expected_banner", "")
    changed("prompt-assert-removed", "expected_prompt", "")
    stale_authorization = deepcopy(contract)
    stale_authorization["restart_authorization_commit"] = ""
    mutations.append(("split-restart-authorization-removed", stale_authorization))
    rejected: list[str] = []
    for name, candidate in mutations:
        try:
            validate_contract(candidate)
        except GateError:
            rejected.append(name)
        else:
            raise GateError(f"contract mutation survived: {name}")

    source_mutations = {
        "source-fresh-start-removed": source.replace("fresh_start D1", ": # fresh_start removed", 1),
        "source-late-reset-added": source.replace(
            "ftp_package D1\n", "ftp_package D1\n  run_m65 -F\n", 1),
        "source-quiet-wait-bypassed": source.replace(
            'sleep "$quiet"', "sleep 30", 1),
        "source-banner-assert-removed": source.replace(
            'grep -Fq "$banner" "$OUT/D1-banner.txt"', ": # banner removed", 1),
        "source-prompt-assert-removed": source.replace(
            'grep -Fq "$prompt" "$OUT/D1-banner.txt"', ": # prompt removed", 1),
        "source-mounted-image-drift": source.replace(
            '-c "mount $remote" -c exit', '-c "mount OTHER.D81" -c exit', 1),
    }
    for name, candidate in source_mutations.items():
        try:
            validate_script(candidate)
        except GateError:
            rejected.append(name)
        else:
            raise GateError(f"source mutation survived: {name}")
    calendar_mutation = driver_source.replace(
        '        "recorded_on": RECORDED_ON,\n        "status":',
        '        "recorded_on": date.today().isoformat(),\n        "status":', 1)
    require(calendar_mutation != driver_source,
            "calendar mutation did not alter the driver")
    try:
        validate_recording_authority(calendar_mutation)
    except GateError:
        rejected.append("driver-live-calendar-recomputation")
    else:
        raise GateError("driver live-calendar mutation survived")
    return rejected


def directory_type(image: bytes, wanted: str) -> str | None:
    track, number, fuel = 40, 0, 64
    while fuel:
        fuel -= 1
        data = D81.sector(image, track, number)
        first = 8 if (track, number) == (40, 0) else 0
        for index in range(first, 8):
            record = data[index * 32:(index + 1) * 32]
            if record[2] & 7 and D81.fold_name(record[5:21]).lower() == wanted:
                return {1: "SEQ", 2: "PRG", 3: "USR", 4: "REL"}.get(record[2] & 7)
        track, number = data[0], data[1]
        if not track:
            break
    return None


def evaluate(*, write: bool) -> dict[str, Any]:
    contract = load(CONFIG)
    validate_contract(contract)
    source = SCRIPT.read_text(encoding="utf-8")
    driver_source = DRIVER.read_text(encoding="utf-8")
    validate_script(source)
    validate_recording_authority(driver_source)
    validate_registration(GATES.read_text(encoding="utf-8"))
    mutations = rejected_mutations(contract, source, driver_source)

    first_red = load(FIRST_RED)
    ship = load(SHIP_RECEIPT)
    link88 = load(LINK88_RECEIPT)
    media_receipt = load(MEDIA_RECEIPT)
    calendar_first_red = load(CALENDAR_FIRST_RED)
    require(first_red.get("status") == "first-red-d1-autoboot-not-entered",
            "D1 First Red authority drift")
    require(ship.get("D1", {}).get("status") ==
            "three-passed-one-tool-unclaimed",
            "v1.3 Ship D1 precedent drift")
    require("D3 fixed 20-second AUTOBOOT wait ended before measured convergence"
            in ship.get("tool_first_reds", []),
            "v1.3 Workbench AUTOBOOT timing precedent drift")
    workbench_source = WORKBENCH_SCRIPT.read_text(encoding="utf-8")
    require("deploy_autoboot_workbench()" in workbench_source
            and "sleep 45" in workbench_source
            and "grep -q 'lisp65>'" in workbench_source,
            "v1.3 corrected Workbench AUTOBOOT choreography drift")
    require(link88.get("status") ==
            "passed-Link88-physical-keyboard-end-to-end",
            "Link-88 power-on precedent drift")
    require(media_receipt.get("status") ==
            "passed-read-only-split-media-closure",
            "Link-92 media authority drift")
    require(
        calendar_first_red.get("status") ==
        "first-red-historical-receipt-calendar-recomputation"
        and calendar_first_red.get("observed_delta") == {
            "json_pointer": "/recorded_on",
            "persisted": RECORDED_ON,
            "recomputed": "2026-08-08",
        },
        "D1 calendar First Red authority drift",
    )

    d1 = contract["d1"]
    media = ROOT / d1["media"]
    descriptor_path = ROOT / d1["mount_descriptor"]
    descriptor = load(descriptor_path)
    image = media.read_bytes()
    directory = D81.d81_directory(image)
    stager = ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5/shared-system/autoboot.c65"
    require(len(image) == 819200 and sha(media) == d1["media_sha256"],
            "Link-92 D1 media binding drift")
    require(descriptor.get("media_sha256") == sha(media)
            and descriptor.get("drive") == 8
            and descriptor.get("media") == media.name,
            "Link-92 mount descriptor drift")
    require(list(directory)[0] == "autoboot.c65"
            and directory_type(image, "autoboot.c65") == "PRG"
            and D81.d81_file(image, directory["autoboot.c65"]) == stager.read_bytes(),
            "Link-92 AUTOBOOT delivery contract drift")
    require("boot.id" in directory and "lisp65.prg" in directory,
            "Link-92 stager inputs absent")

    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-boot-choreography-diff-v1",
        "recorded_on": RECORDED_ON,
        "status": "passed-precedent-equivalent-mount-reset-corrected-observation-contract",
        "authorization": {
            "choreography_commit": contract["authorization_commit"],
            "split_restart_commit": contract["restart_authorization_commit"],
            "scope": "desk diff plus one D1 restart over the host-green split media; D3 and D2 remain ordered behind D1",
        },
        "named_difference": {
            "mount_mechanism": "no difference: m65 -F, fresh BASIC, mega65_ftp -0 5 -F, put/get/mount, helper reset-and-exit",
            "drive_and_image": "same drive-8/default-drive-0 association; Link-92 descriptor, remote name and D81 AUTOBOOT payload are now bound",
            "reset_entry": "same helper-owned mount-and-reset; no second reset",
            "first_red_gap": "the failed D1 omitted the machine-checked fresh-BASIC precondition and used one screen-only look after 30 seconds",
            "precedent_fact": "the Link-84 Workbench AUTOBOOT remained on the BASIC 65 splash at 20 seconds and reached the REPL roughly 14 seconds later",
            "correction": "wait 45 seconds with zero post-mount access, then require both WORKBENCH 1.4.0 and lisp65> plus the fail-closed-frame check",
            "mechanism_claim": "the prior C65 screen is an under-specified early observation, not evidence that mount or AUTOBOOT failed",
        },
        "choreography": d1,
        "media_structure": {
            "directory_first_member": list(directory)[0],
            "autoboot_type": directory_type(image, "autoboot.c65"),
            "autoboot_payload_matches": True,
            "required_stager_inputs": ["boot.id", "lisp65.prg"],
            "mount_descriptor_drive": descriptor["drive"],
        },
        "mutations_rejected": mutations,
        "mutation_count": len(mutations),
        "bindings": {
            "contract": bind(CONFIG),
            "driver": bind(DRIVER),
            "gate_registration": bind(GATES),
            "runner": bind(SCRIPT),
            "first_red": bind(FIRST_RED),
            "media_readback": bind(MEDIA_RECEIPT),
            "calendar_first_red": bind(CALENDAR_FIRST_RED),
            "link92_media": bind(media),
            "link92_mount_descriptor": bind(descriptor_path),
            "link92_autoboot": bind(stager),
            "v13_ship_runner": bind(SHIP_SCRIPT),
            "v13_workbench_runner": bind(WORKBENCH_SCRIPT),
            "v13_ship_device_receipt": bind(SHIP_RECEIPT),
            "link88_runner": bind(LINK88_SCRIPT),
            "link88_device_receipt": bind(LINK88_RECEIPT),
        },
        "execution_accounting": {
            "hardware_contacts": 0,
            "product_rebuilds": 0,
            "media_rebuilds": 0,
            "links": 0,
            "D1_rows": 0,
            "D3_rows": 0,
            "D2_rows": 0,
        },
        "disposition": {
            "dry_run": "passed",
            "recontact_authorized": True,
            "recommended_contact": "one fresh D1 launch through scripts/c2-v112-link92-phase-d-boot-hw.sh start-d1; then D1 smokes, D3 and D2 in the bound order",
        },
        "claim_limit": "Host choreography and exact-media preparation only. No device, D1 product, D3, D2, selector, Halt, Phase E or release claim.",
    }
    if write:
        RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return result


def selftest() -> dict[str, Any]:
    contract = load(CONFIG)
    validate_contract(contract)
    source = SCRIPT.read_text(encoding="utf-8")
    driver_source = DRIVER.read_text(encoding="utf-8")
    validate_script(source)
    validate_recording_authority(driver_source)
    validate_registration(GATES.read_text(encoding="utf-8"))
    rejected = rejected_mutations(contract, source, driver_source)
    return {"status": "passed", "mutations": len(rejected)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "prepare", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            value = selftest()
            print(f"c2-v112-phase-d-boot-choreography: SELFTEST PASS mutations={value['mutations']}")
        elif args.action == "prepare":
            value = evaluate(write=True)
            print("c2-v112-phase-d-boot-choreography: PREPARE PASS "
                  f"mutations={value['mutation_count']} contacts=0")
        else:
            expected = evaluate(write=False)
            actual = load(RECEIPT)
            require(actual == expected, "boot choreography preparation receipt drift")
            print("c2-v112-phase-d-boot-choreography: CHECK PASS "
                  f"mutations={expected['mutation_count']} contacts=0")
        return 0
    except GateError as error:
        print(f"c2-v112-phase-d-boot-choreography: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
