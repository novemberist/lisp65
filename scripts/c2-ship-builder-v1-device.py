#!/usr/bin/env python3
"""Prepare and close the Ship-v1 bundled quiet hardware session."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_link75_library_media_successor as MEDIA  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-ship-builder-v1-hardware-session.json"
PLAN = ROOT / "docs/planning/1.3-ship-builder-work-plan.md"
DRIVER = Path(__file__).resolve()
SCRIPT = ROOT / "scripts/c2-ship-builder-v1-hw.sh"
OUT = ROOT / "build/ship-builder/v1-device-session"
DEPLOYMENT = OUT / "deployment.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-preparation-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-receipt.json")
OWNER_REVIEW = ROOT / "docs/planning/1.3-ship-builder-halt1-review.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-first-red.json")
COMPLETION_PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-completion-preparation-receipt.json")
COMPLETION_HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-ship-builder-v1-device-completion-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
BASE_DEFSTRUCT = ROOT / (
    "build/post-release/link78-dirmiss-renderer/d1-d2-bundled-session/"
    "library-media/require-defstruct-link78-bound.d81")


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file(), f"bound file absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def check_binding(row: dict[str, Any]) -> Path:
    path = ROOT / row["path"]
    require(
        path.is_file()
        and ("bytes" not in row or path.stat().st_size == row["bytes"])
        and sha(path) == row["sha256"],
        f"binding drift: {path}",
    )
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def rebind_defstruct_media(build_id: int, base: Path) -> Path:
    require(base.is_file(), "base defstruct medium absent")
    out = OUT / "defstruct-media"
    out.mkdir(parents=True, exist_ok=True)
    locators = L65I.d81_locators(base)
    artifacts, rows = MEDIA.expected_artifacts(build_id, locators)
    visible0 = L65I.D81.visible_files(base.read_bytes())
    artifact_paths: list[tuple[Path, str]] = []
    for name, data in artifacts.items():
        old = visible0[name.upper().encode("ascii")]
        require(
            len(old) == len(data)
            and old[64:] == data[64:]
            and struct.unpack_from("<I", data, 22)[0] == build_id
            and data[32:40] == b"SESS\0\0\0\0",
            f"defstruct artifact changed outside bound envelope: {name}",
        )
        path = out / f"{name}.l65s"
        path.write_bytes(data)
        artifact_paths.append((path, name))
    index = L65I.encode_index(rows)
    require(index == visible0[b"L65INDEX"], "defstruct index drift")
    index_path = out / "l65index"
    index_path.write_bytes(index)
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    require(
        L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY) == [0, 1],
        "defstruct dependency order drift",
    )
    require(
        len(L65I.mutation_gate(
            index, artifacts, artifact_build_id=build_id)) >= 6,
        "defstruct media mutation witness drift",
    )
    d81 = out / "require-defstruct-ship-session.d81"
    L65I.build_d81(d81, index_path, artifact_paths)
    visible = L65I.D81.visible_files(d81.read_bytes())
    require(
        L65I.d81_locators(d81) == locators
        and visible[b"PLACE"] == artifacts["place"]
        and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
        "rebuilt defstruct medium verification failed",
    )
    return d81


def bind_candidate(deployment: dict[str, Any]) -> dict[str, Any]:
    candidate = deployment["candidate"]
    product = check_binding(candidate["product"])
    elf = check_binding(candidate["ELF"])
    package = check_binding(candidate["package_medium"])
    preloads = []
    for row in candidate["preloads"]:
        check_binding(row)
        preloads.append(row)
    return {
        "release": candidate["release"],
        "link": candidate["link"],
        "product": bind(product, int(candidate["product"].get(
            "address", "0x00002001"), 16)),
        "ELF": bind(elf),
        "package_medium": bind(package),
        "remote_media": candidate.get("remote_media", "S13WORK.D81"),
        "preloads": preloads,
    }


def prepare() -> dict[str, Any]:
    config = load(CONFIG)
    require(
        config["status"] == "owner-commissioned-one-quiet-device-session"
        and config["policy"]["persistent_forms_are_quiet"]
        and not config["policy"][
            "screenshot_polling_around_persistent_forms"],
        "quiet device-session policy drift",
    )

    d1 = []
    expected_images = {
        "ship-hello":
            "6b2435b420f84d6992bfa7a9019484235ff36887f912c090fba5b6b6885478a7",
        "ship-random-fx":
            "cca45cc4148d4b80b67b023afbc7a7d4b79c5dd3077636c94374732444cf8cd8",
        "ship-long-runner":
            "101049128097662ccb1b1b1264ca8e0deeb2326a9df2c5c2dfc188f293b1f3c7",
    }
    for row in config["D1"]:
        image = ROOT / row["image"]
        elf = ROOT / row["elf"]
        require(sha(image) == expected_images[row["id"]],
                f"Ship image drift: {row['id']}")
        truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
        addresses = {
            name: truth.symbol(name).value
            for name in (
                "lisp65_runtime_state",
                "lisp65_runtime_result",
                "lisp65_runtime_preload_detail",
            )
        }
        require(
            addresses["lisp65_runtime_result"]
                == addresses["lisp65_runtime_state"] + 1
            and addresses["lisp65_runtime_preload_detail"]
                == addresses["lisp65_runtime_state"] + 3,
            f"Ship runtime result span drift: {row['id']}",
        )
        d1.append({
            **row,
            "image": bind(image),
            "ELF": bind(elf),
            "addresses": {
                key: f"0x{value:08x}" for key, value in addresses.items()
            },
        })

    d2_source = load(ROOT / config["D2"]["candidate_deployment"])
    d2 = bind_candidate(d2_source)
    require(
        d2["release"] == "v1.2.5" and d2["link"] == 82,
        "D2 baseline is not released Link 82",
    )
    build_id = int(d2_source["candidate"]["product_build_id"], 16)
    media = rebind_defstruct_media(
        build_id, ROOT / config["D2"]["base_defstruct_media"])
    d2["defstruct_media"] = bind(media)
    d2["remote_media"] = config["D2"]["remote"]
    d2["rows"] = config["D2"]["rows"]
    truth2 = ElfTruth.read(ROOT / d2["ELF"]["path"], llvm_readobj=READOBJ)
    scratch = truth2.symbol("lisp65_c2_phase_scratch").value
    d2["readbacks"] = {
        "trace": [f"0x{scratch + 302:08x}", 2],
        "c2d_header": ["0x00050000", 48],
        "place_row": ["0x000500f0", 32],
        "defstruct_row": ["0x00050110", 32],
        "c2j": ["0x0005c640", 64],
        "phase_owner": [
            f"0x{truth2.symbol('c2_phase_owner').value:08x}", 1],
        "mem_oom": [f"0x{truth2.symbol('mem_oom').value:08x}", 1],
        "gc_badobj": [f"0x{truth2.symbol('gc_badobj').value:08x}", 2],
    }

    d3_source = load(ROOT / config["D3"]["candidate_deployment"])
    d3 = bind_candidate(d3_source)
    require(
        d3["release"] == "v1.2.6" and d3["link"] == 83,
        "D3 baseline is not parked Link 83",
    )
    d3.update({key: config["D3"][key] for key in (
        "editor_form", "character", "keys", "quiet_seconds",
        "query_form", "expected")})

    value = {
        "format": "lisp65-c2.3-ship-builder-v1-device-deployment-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-host-green-one-quiet-device-session",
        "D1": d1,
        "D2": d2,
        "D3": d3,
        "D4": config["D4"],
        "policy": config["policy"],
    }
    write_json(DEPLOYMENT, value)
    prep = {
        "format": "lisp65-c2.3-ship-builder-v1-device-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-host-green-one-quiet-device-session",
        "promotable": False,
        "hardware_runs": 0,
        "ship_images": [row["image"] for row in d1],
        "defstruct_media": d2["defstruct_media"],
        "authorities": {
            "config": bind(CONFIG),
            "plan": bind(PLAN),
            "driver": bind(DRIVER),
            "script": bind(SCRIPT),
            "deployment": bind(DEPLOYMENT),
        },
        "quiet_proof": {
            "persistent_rows": [row["id"] for row in d2["rows"]]
                + ["standing-require-place"],
            "monitor_traffic_during_quiet_windows": 0,
            "editor_keys_without_polling": d3["keys"],
        },
        "next_gate": "one physical session, then Class-C Halt #1",
        "claim_limit": "Preparation only; no device, defstruct, editor or physical Ship boot claim.",
    }
    write_json(PREPARATION, prep)
    return value


def read_result(path: Path) -> bytes:
    data = path.read_bytes()
    require(len(data) == 4, f"Ship result width drift: {path}")
    return data


def prepare_completion() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    first_red = load(FIRST_RED)
    owner = OWNER_REVIEW.read_text(encoding="utf-8")
    require(
        first_red["D2"]["status"]
            == "product-first-red-quiet-defstruct-does-not-complete"
        and first_red["D3"]["status"] == "not-run-session-terminal-after-D2"
        and first_red["D4"]["status"] == "not-run-session-terminal-after-D2",
        "historical D2/D3/D4 disposition drift",
    )
    require(
        "accepted" in owner.lower()
        and "D1+D3+D4 only" in owner
        and "redundant reset" in owner
        and "defstruct is neither retried nor investigated" in owner,
        "owner completion authorization drift",
    )
    for row in deployment["D1"]:
        check_binding(row["image"])
        check_binding(row["ELF"])
    for section in ("D2", "D3"):
        check_binding(deployment[section]["product"])
        check_binding(deployment[section]["ELF"])
        check_binding(deployment[section]["package_medium"])
        for row in deployment[section]["preloads"]:
            check_binding(row)
    check_binding(deployment["D2"]["defstruct_media"])
    value = {
        "format": "lisp65-c2.3-ship-builder-v1-device-completion-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "owner-authorized-host-green-D1-D3-D4-only",
        "promotable": False,
        "hardware_runs": 0,
        "rows": {
            "D1": [row["id"] for row in deployment["D1"]],
            "D2": "excluded-concluded-product-first-red",
            "D3": ["quiet-editor-typing", "buffer-length", "post-stop-repl"],
            "D4": [row["id"] for row in deployment["D4"]],
        },
        "authorized_harness_delta": (
            "Remove only the redundant explicit reset after the D1 FTP "
            "helper's mount-and-reset exit."),
        "authorities": {
            "config": bind(CONFIG),
            "plan": bind(PLAN),
            "owner_review": bind(OWNER_REVIEW),
            "first_red": bind(FIRST_RED),
            "driver": bind(DRIVER),
            "script": bind(SCRIPT),
            "deployment": bind(DEPLOYMENT),
        },
        "claim_limit": (
            "Preparation only. D2 is bound as concluded evidence and is not "
            "executed; no new physical or release claim is made."),
    }
    write_json(COMPLETION_PREPARATION, value)
    return deployment


def evaluate() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    run = OUT / "run"
    ship_results = []
    for row in deployment["D1"]:
        raw = read_result(run / f"{row['id']}-result.bin")
        expected = int(row["expected_result"], 16)
        require(
            raw == bytes((3, expected & 0xFF, expected >> 8, 0)),
            f"Ship target result drift: {row['id']} got={raw.hex()}",
        )
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")
        ship_results.append({
            "id": row["id"],
            "state": "RUNTIME_COMPLETE",
            "result": row["expected_result"],
            "readback": bind(run / f"{row['id']}-result.bin",
                             int(row["addresses"]["lisp65_runtime_state"], 16)),
            "screen": bind(run / f"{row['id']}.png"),
            "package_readback": bind(
                run / f"{row['id']}-package-readback.d81"),
        })
        require(
            (ROOT / row["image"]["path"]).read_bytes()
                == (run / f"{row['id']}-package-readback.d81").read_bytes(),
            f"Ship uploaded media drift: {row['id']}",
        )

    for row in deployment["D2"]["rows"]:
        SCREEN.check_latest_result(
            run / f"{row['id']}.txt", row["form"], row["expected"])
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")
    for row in deployment["D4"]:
        SCREEN.check_latest_result(
            run / f"{row['id']}.txt", row["form"], row["expected"])
    require(
        (run / "D2-c2j.bin").read_bytes() == bytes(64),
        "D2 C2J is not CLEAR",
    )
    require(
        (run / "D2-phase_owner.bin").read_bytes() == bytes(1)
        and (run / "D2-mem_oom.bin").read_bytes() == bytes(1)
        and (run / "D2-gc_badobj.bin").read_bytes() == bytes(2),
        "D2 standing status readback is not clean",
    )

    SCREEN.check_fail_closed_frame(run / "editor-quiet-end.png")
    SCREEN.check_latest_result(
        run / "editor-query.txt",
        deployment["D3"]["query_form"],
        deployment["D3"]["expected"],
        allow_editor_status_tail=True,
    )
    SCREEN.check_latest_result(
        run / "editor-post-stop.txt", "(+ 4 5)", "9",
        allow_editor_status_tail=True,
    )

    result = {
        "format": "lisp65-c2.3-ship-builder-v1-device-receipt-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-ship-fleet-and-quiet-followup-rows",
        "hardware_sessions": 1,
        "D1": {
            "status": "passed-three-standalone-images-from-power-on",
            "rows": ship_results,
        },
        "D2": {
            "status": "passed-quiet-defstruct-completion",
            "rows": [row["id"] for row in deployment["D2"]["rows"]],
            "readbacks": {
                name: bind(run / f"D2-{name}.bin", int(address, 16))
                for name, (address, _size) in
                deployment["D2"]["readbacks"].items()
            },
        },
        "D3": {
            "status": "passed-quiet-editor-typing",
            "keys": deployment["D3"]["keys"],
            "character": deployment["D3"]["character"],
            "end_screen": bind(run / "editor-quiet-end.png"),
            "query_screen": bind(run / "editor-query.txt"),
        },
        "D4": {
            "status": "passed-require-fx-time",
            "rows": [row["id"] for row in deployment["D4"]],
        },
        "bindings": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
        },
        "claim_limit": "One bundled physical session proves the three bound Ship images and the listed quiet Workbench rows only; release and promotion remain unclaimed until Halt #1.",
    }
    write_json(HARDWARE, result)
    return result


def evaluate_completion() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    preparation = load(COMPLETION_PREPARATION)
    require(
        preparation["status"] == "owner-authorized-host-green-D1-D3-D4-only",
        "completion preparation status drift",
    )
    run = OUT / "run-completion"
    ship_results = []
    for row in deployment["D1"]:
        raw = read_result(run / f"{row['id']}-result.bin")
        expected = int(row["expected_result"], 16)
        require(
            raw == bytes((3, expected & 0xFF, expected >> 8, 0)),
            f"Ship target result drift: {row['id']} got={raw.hex()}",
        )
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")
        image = ROOT / row["image"]["path"]
        readback = run / f"{row['id']}-package-readback.d81"
        require(image.read_bytes() == readback.read_bytes(),
                f"Ship uploaded media drift: {row['id']}")
        ship_results.append({
            "id": row["id"],
            "state": "RUNTIME_COMPLETE",
            "result": row["expected_result"],
            "readback": bind(
                run / f"{row['id']}-result.bin",
                int(row["addresses"]["lisp65_runtime_state"], 16)),
            "screen": bind(run / f"{row['id']}.png"),
            "package_readback": bind(readback),
        })

    for row in deployment["D4"]:
        SCREEN.check_latest_result(
            run / f"{row['id']}.txt", row["form"], row["expected"])
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")

    SCREEN.check_fail_closed_frame(run / "editor-quiet-end.png")
    SCREEN.check_latest_result(
        run / "editor-query.txt",
        deployment["D3"]["query_form"],
        deployment["D3"]["expected"],
        allow_editor_status_tail=True,
    )
    SCREEN.check_latest_result(
        run / "editor-post-stop.txt", "(+ 4 5)", "9",
        allow_editor_status_tail=True,
    )

    result = {
        "format": "lisp65-c2.3-ship-builder-v1-device-completion-receipt-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-owner-authorized-D1-D3-D4-completion",
        "hardware_sessions": 1,
        "D1": {
            "status": "passed-three-standalone-images-from-power-on",
            "rows": ship_results,
        },
        "D2": {
            "status": "not-retried-concluded-product-first-red",
            "evidence": bind(FIRST_RED),
        },
        "D3": {
            "status": "passed-quiet-editor-typing",
            "keys": deployment["D3"]["keys"],
            "character": deployment["D3"]["character"],
            "end_screen": bind(run / "editor-quiet-end.png"),
            "query_screen": bind(run / "editor-query.txt"),
        },
        "D4": {
            "status": "passed-require-fx-time",
            "rows": [row["id"] for row in deployment["D4"]],
        },
        "bindings": {
            "preparation": bind(COMPLETION_PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "owner_review": bind(OWNER_REVIEW),
        },
        "claim_limit": (
            "One dependency-sharp physical session proves the three bound "
            "Ship images, quiet editor row and D4 rows only. D2 remains a "
            "separate concluded product failure; release and promotion remain "
            "unclaimed until Halt #2."),
    }
    write_json(COMPLETION_HARDWARE, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "dry-run", "evaluate", "prepare-completion",
        "dry-run-completion", "evaluate-completion"))
    args = parser.parse_args()
    try:
        if args.action in {"prepare", "dry-run"}:
            value = prepare()
        elif args.action in {"prepare-completion", "dry-run-completion"}:
            value = prepare_completion()
        elif args.action == "evaluate-completion":
            value = evaluate_completion()
        else:
            value = evaluate()
        if args.action == "dry-run":
            print("c2-ship-builder-v1-device: DRY-RUN PASS")
            print("D1:", ", ".join(row["id"] for row in value["D1"]))
            print("D2 quiet:", ", ".join(row["id"] for row in value["D2"]["rows"]))
            print(f"D3 quiet keys: {value['D3']['keys']}")
            print("D4:", ", ".join(row["id"] for row in value["D4"]))
        elif args.action == "dry-run-completion":
            print("c2-ship-builder-v1-device: COMPLETION DRY-RUN PASS")
            print("D1:", ", ".join(row["id"] for row in value["D1"]))
            print("D2: excluded (concluded product First Red)")
            print(f"D3 quiet keys: {value['D3']['keys']}")
            print("D4:", ", ".join(row["id"] for row in value["D4"]))
        else:
            print(f"c2-ship-builder-v1-device: PASS status={value['status']}")
        return 0
    except (
        SessionError, SCREEN.CheckError, OSError, ValueError, KeyError,
        TypeError, json.JSONDecodeError,
    ) as error:
        print(f"c2-ship-builder-v1-device: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
