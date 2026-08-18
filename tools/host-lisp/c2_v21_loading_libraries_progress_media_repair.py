#!/usr/bin/env python3
"""Repair and close the Link-107 progress diagnostic medium."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as RING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FIRST_RED = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-first-red-receipt.json")
RESCUE = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-rescue-receipt.json")
BUILD = ROOT / "build/c2.3/v2.1-loading-libraries-progress-media-repair"
STAGER_BUILD = BUILD / "stager-build"
STAGER = BUILD / "autoboot.c65"
STAGER_MAP = BUILD / "autoboot.c65.map"
DESCRIPTOR = BUILD / "boot.id"
PRODUCT_D81 = BUILD / "lisp65-loading-libraries-progress.d81"
READBACK = BUILD / "readback"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-repair-receipt.json")
FORMAT = "lisp65-c2.3-v2.1-loading-progress-media-repair-v1"
AUTHORIZATION = "0c99d88aa8e5ac9085074e8ff95924476b6edebf"


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
                         cwd=ROOT, check=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("rescue read authorized", "second occurrence",
                  "structural enumeration", "every medium builder"):
        require(token in text, f"media-repair authority token absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION,
            "path": name, "bytes": len(raw), "sha256": digest(raw)}


def packed_medium_gate(path: Path) -> dict[str, Any]:
    roles = SISTER.medium_roles(path, READBACK)
    paths = SISTER.role_paths(roles)
    descriptor = paths["boot.id"].read_bytes()
    rows, build_id, profile_id = SISTER.descriptor_rows(descriptor, paths)
    SISTER.target_descriptor_check(descriptor, rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    require(paths["autoboot.c65"].read_bytes() == STAGER.read_bytes(),
            "packed repaired stager differs from closed artifact")
    return {"result": "passed-15-role-readback-and-13-row-descriptor",
            "roles": len(roles), "descriptor_rows": len(rows),
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}"}


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "media repair build is one-shot")
    first_red = load(FIRST_RED); rescue = load(RESCUE)
    require(first_red["status"].endswith("CPU-RATE-UNMEASURED")
            and rescue["status"] ==
                "STAGE-ROLE-REJECTION-BEFORE-OR-AT-ROLE8",
            "media repair lacks bound First Red/rescue authority")
    BUILD.mkdir(parents=True)
    shutil.copyfile(RING.DIAG_DESCRIPTOR, DESCRIPTOR)
    source_roles = SISTER.medium_roles(RING.DIAG_D81, BUILD / "source-roles")
    source_paths = SISTER.role_paths(source_roles)
    rows, build_id, profile_id = SISTER.descriptor_rows(
        DESCRIPTOR.read_bytes(), source_paths)
    stager_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=STAGER_BUILD, stager=STAGER,
        stager_map=STAGER_MAP, compile_defines=(LIVE.OPT_IN,))
    shutil.copyfile(RING.DIAG_D81, PRODUCT_D81)
    subprocess.run(["c1541", "-attach", str(PRODUCT_D81),
                    "-delete", "autoboot.c65", "-write", str(STAGER),
                    "autoboot.c65"], cwd=ROOT, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    gates: dict[str, Callable[[Path], dict[str, Any]]] = {
        "autoboot.c65.elf": LIVE.delivered_liveness_gate,
        "diagnostic-product.d81": packed_medium_gate,
    }
    closure = MEDIA.close_packed_artifacts(
        {"autoboot.c65.elf": Path(str(STAGER) + ".elf"),
         "diagnostic-product.d81": PRODUCT_D81}, gates)
    require(closure["complete"] is True
            and closure["registered"] == closure["executed"] ==
                ["autoboot.c65.elf", "diagnostic-product.d81"],
            "repaired media packed-artifact closure incomplete")
    value = {"format": FORMAT, "recorded_on": "2026-08-15",
             "status": "HOST-GREEN; REPAIRED-DIAGNOSTIC-MEDIA-CLOSED",
             "authority": {"owner": authority(), "first_red": bind(FIRST_RED),
                 "rescue": bind(RESCUE), "ring": bind(RING.RECEIPT)},
             "repair": {"stager_opt_in": LIVE.OPT_IN,
                 "product_bytes_changed": 0,
                 "diagnostic_PRG": bind(RING.DIAG_PRG),
                 "diagnostic_WINDOW": bind(RING.DIAG_WINDOW),
                 "descriptor": bind(DESCRIPTOR), "stager": bind(STAGER),
                 "stager_ELF": bind(Path(str(STAGER) + ".elf")),
                 "stager_gate": stager_gate},
             "packed_artifact_gate_registry": closure,
             "media": {"product_D81": bind(PRODUCT_D81),
                 "library_D81": bind(RING.LIBRARY_D81),
                 "build_id": f"0x{build_id:08x}",
                 "profile_id": f"0x{profile_id:08x}"},
             "claim_limit": (
                 "Host-only diagnostic media repair. No CPU-rate claim and "
                 "no device recontact authorization.")}
    value["mutations"] = mutations(value)
    audit(value)
    RECEIPT.write_bytes(canonical(value))
    return value


def audit(value: dict[str, Any]) -> None:
    registry = value.get("packed_artifact_gate_registry", {})
    require(
        value.get("status") == "HOST-GREEN; REPAIRED-DIAGNOSTIC-MEDIA-CLOSED"
        and value.get("repair", {}).get("stager_opt_in") == LIVE.OPT_IN
        and value.get("repair", {}).get("product_bytes_changed") == 0
        and registry.get("complete") is True
        and registry.get("registered") == registry.get("executed") ==
            ["autoboot.c65.elf", "diagnostic-product.d81"],
        "repaired diagnostic media closure drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-opt-in": lambda x: x["repair"].update(stager_opt_in=""),
        "change-product": lambda x: x["repair"].update(product_bytes_changed=1),
        "omit-stager-gate": lambda x: x["packed_artifact_gate_registry"]
            ["executed"].remove("autoboot.c65.elf"),
        "omit-medium-gate": lambda x: x["packed_artifact_gate_registry"]
            ["executed"].remove("diagnostic-product.d81"),
        "open-incomplete": lambda x: x["packed_artifact_gate_registry"]
            .update(complete=False),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            audit(trial)
        except RepairError:
            rejected.append(name)
    require(len(rejected) == len(cases), "media repair mutation survived")
    return sorted(rejected)


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value["authority"]["owner"] == authority()
            and value["authority"]["first_red"] == bind(FIRST_RED)
            and value["authority"]["rescue"] == bind(RESCUE)
            and value["media"]["product_D81"] == bind(PRODUCT_D81),
            "media repair authority/artifact drift")
    return value


def selftest() -> dict[str, Any]:
    with __import__("tempfile").TemporaryDirectory(prefix="media-close-") as raw:
        path = Path(raw) / "a"; path.write_bytes(b"a")
        closed = MEDIA.close_packed_artifacts(
            {"a": path}, {"a": lambda p: {"sha256": digest(p.read_bytes())}})
        rejected = []
        for artifacts, gates in (({"a": path}, {}), ({}, {"a": lambda _p: {}})):
            try:
                MEDIA.close_packed_artifacts(artifacts, gates)
            except MEDIA.MediaError:
                rejected.append(True)
    require(closed["complete"] is True and len(rejected) == 2,
            "media repair closure selftest drift")
    return {"status": "SELFTEST PASS", "mutations": 2}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    value = build() if args.action == "build" else (
        check() if args.action == "check" else selftest())
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RepairError, MEDIA.MediaError, LIVE.SuccessorError, OSError,
            KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"LINK 107 MEDIA REPAIR: {error}", file=sys.stderr)
        raise SystemExit(1)
