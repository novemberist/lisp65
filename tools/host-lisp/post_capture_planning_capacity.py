#!/usr/bin/env python3
"""Verify the post-capture planning-read capacity probe against sealed bytes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/r3/"
    "post-capture-planning-capacity-probe-receipt.json"
)
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
CANDIDATE_ARCHIVE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/promotions/"
    "r4-product-candidate-41cf793.tar.gz"
)
CANDIDATE_ARCHIVE_SHA256 = (
    "d044230a83a3faa0c34805f0e695dd101847976ee77cf972039ed8b44f6340d9"
)
FORMAT = "lisp65-post-capture-planning-capacity-probe-v1"
SHA = re.compile(r"[0-9a-f]{64}")


class ProbeError(RuntimeError):
    pass


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProbeError(f"{label} schema drift")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise ProbeError(f"{label} must be a repository path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or ".." in pure.parts:
        raise ProbeError(f"{label} is not canonical")
    return ROOT / pure


def binding(value: Any, label: str) -> Path:
    row = exact(value, {"path", "bytes", "sha256"}, label)
    path = repo_path(row["path"], f"{label}.path")
    if (
        type(row["bytes"]) is not int or row["bytes"] < 0
        or not SHA.fullmatch(str(row["sha256"]))
        or path.is_symlink() or not path.is_file()
        or path.stat().st_size != row["bytes"] or sha(path.read_bytes()) != row["sha256"]
    ):
        raise ProbeError(f"{label} binding drift")
    return path


def member(archive: tarfile.TarFile, value: Any, label: str) -> bytes:
    row = exact(value, {"path", "bytes", "sha256"}, label)
    name = str(row["path"])
    if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
        raise ProbeError(f"{label} path is not canonical")
    try:
        info = archive.getmember(name)
        source = archive.extractfile(info)
    except (KeyError, tarfile.TarError) as exc:
        raise ProbeError(f"{label} archive member missing") from exc
    if source is None or not info.isfile():
        raise ProbeError(f"{label} is not a regular archive member")
    data = source.read()
    if (
        type(row["bytes"]) is not int or len(data) != row["bytes"]
        or not SHA.fullmatch(str(row["sha256"])) or sha(data) != row["sha256"]
    ):
        raise ProbeError(f"{label} member binding drift")
    return data


def object_from(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"{label} is not JSON") from exc
    if not isinstance(value, dict):
        raise ProbeError(f"{label} must contain an object")
    return value


def archived_candidate_member(
    archive: tarfile.TarFile, value: Any, label: str,
) -> bytes:
    row = exact(value, {"path", "bytes", "sha256"}, label)
    return member(
        archive,
        {
            "path": f"payload/{row['path']}",
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        },
        label,
    )


def symbols(path: Path) -> dict[str, tuple[int, int]]:
    process = subprocess.run(
        [str(NM), "--defined-only", "--print-size", "--size-sort", "--radix=x", str(path)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if process.returncode:
        raise ProbeError(f"llvm-nm failed: {process.stderr.strip()}")
    result: dict[str, tuple[int, int]] = {}
    for line in process.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) == 4:
            address, size, _kind, name = fields
            if name in result:
                raise ProbeError(f"duplicate ELF symbol: {name}")
            result[name] = (int(address, 16), int(size, 16))
    return result


def validate(value: dict[str, Any]) -> None:
    exact(
        value,
        {
            "format", "version", "id", "status", "measured_on", "baseline",
            "candidate_probe", "capacity_delta_from_sealed_candidate", "decision", "result",
        },
        "probe receipt",
    )
    if (
        value["format"] != FORMAT or value["version"] != 1
        or value["id"] != "post-capture-planning-read-status-classification"
        or value["status"] != "passed-not-promoted"
        or value["measured_on"] != "2026-07-15"
        or value["decision"]
        != "owner-authorized-option-1-on-2026-07-15-subject-to-this-explicit-ext-proof"
        or value["result"]
        != "bank-debit-49-authorized-ext-floor-held-and-margin-origin-attributed"
    ):
        raise ProbeError("probe identity/result drift")

    baseline = exact(
        value["baseline"],
        {
            "product_artifact_set_sha256", "archive", "m65d_manifest_member",
            "composition_member", "footprint_member", "product_elf_member",
        },
        "baseline",
    )
    if baseline["product_artifact_set_sha256"] != (
        "1051d7820fa7d8add7f1ce7f59874068343134562a08f66f80e0c2d256adf289"
    ):
        raise ProbeError("sealed product identity drift")
    archive_path = binding(baseline["archive"], "baseline.archive")
    with tarfile.open(archive_path, "r:gz") as archive:
        old_manifest = object_from(
            member(archive, baseline["m65d_manifest_member"], "baseline.m65d_manifest_member"),
            "sealed M65D manifest",
        )
        old_composition = object_from(
            member(archive, baseline["composition_member"], "baseline.composition_member"),
            "sealed composition report",
        )
        old_footprint = object_from(
            member(archive, baseline["footprint_member"], "baseline.footprint_member"),
            "sealed footprint report",
        )
        old_elf = member(archive, baseline["product_elf_member"], "baseline.product_elf_member")

    candidate = exact(
        value["candidate_probe"],
        {"product_elf", "m65d_manifest", "composition_report", "footprint_report"},
        "candidate_probe",
    )
    if (
        CANDIDATE_ARCHIVE.is_symlink() or not CANDIDATE_ARCHIVE.is_file()
        or sha(CANDIDATE_ARCHIVE.read_bytes()) != CANDIDATE_ARCHIVE_SHA256
    ):
        raise ProbeError("sealed candidate archive binding drift")
    with tarfile.open(CANDIDATE_ARCHIVE, "r:gz") as archive:
        sealed_receipt = archive.extractfile(
            "payload/tests/bytecode/dialect-v2/evidence/r3/"
            "post-capture-planning-capacity-probe-receipt.json"
        )
        if (
            sealed_receipt is None
            or object_from(sealed_receipt.read(), "sealed candidate receipt") != value
        ):
            raise ProbeError("sealed candidate receipt binding drift")
        candidate_elf = archived_candidate_member(
            archive, candidate["product_elf"], "candidate_probe.product_elf"
        )
        new_manifest = object_from(
            archived_candidate_member(
                archive, candidate["m65d_manifest"], "candidate_probe.m65d_manifest"
            ),
            "sealed candidate M65D manifest",
        )
        new_composition = object_from(
            archived_candidate_member(
                archive,
                candidate["composition_report"],
                "candidate_probe.composition_report",
            ),
            "sealed candidate composition report",
        )
        new_footprint = object_from(
            archived_candidate_member(
                archive,
                candidate["footprint_report"],
                "candidate_probe.footprint_report",
            ),
            "sealed candidate footprint report",
        )

    if (
        old_manifest.get("code_bytes") != 4024
        or old_manifest.get("cost", {}).get("symbol_count_estimate") != 52
        or "boundp" not in old_manifest.get("cost", {}).get("symbol_names", [])
        or new_manifest.get("code_bytes") != 4020
        or new_manifest.get("cost", {}).get("symbol_count_estimate") != 51
        or "boundp" in new_manifest.get("cost", {}).get("symbol_names", [])
    ):
        raise ProbeError("M65D code/symbol attribution drift")
    if (
        old_composition.get("ext_code", {}).get("post_headroom") != 16384
        or old_composition.get("ext_code", {}).get("stages", [{}])[-1].get("metadata_bytes") != 3230
        or new_composition.get("ext_code", {}).get("post_headroom") != 16388
        or new_composition.get("ext_code", {}).get("stages", [{}])[-1].get("metadata_bytes") != 3190
        or old_composition.get("symbols", {}).get("headroom") != 120
        or new_composition.get("symbols", {}).get("headroom") != 120
        or old_footprint.get("post_boot_reserve") != 1917
        or new_footprint.get("post_boot_reserve") != 1868
    ):
        raise ProbeError("sealed/live capacity measurement drift")

    with tempfile.TemporaryDirectory(prefix="l65-planning-capacity-") as raw:
        old_path = Path(raw) / "baseline.elf"
        old_path.write_bytes(old_elf)
        old_symbols = symbols(old_path)
    with tempfile.TemporaryDirectory(prefix="l65-planning-candidate-") as raw:
        candidate_elf_path = Path(raw) / "candidate.elf"
        candidate_elf_path.write_bytes(candidate_elf)
        new_symbols = symbols(candidate_elf_path)
    if (
        "io_disk_transaction_classify_status" in old_symbols
        or new_symbols.get("io_disk_transaction_classify_status", (0, 0))[1] != 27
        or old_symbols.get("vm_callprim", (0, 0))[1] != 6721
        or new_symbols.get("vm_callprim", (0, 0))[1] != 6735
        or new_symbols.get("__bss_end", (0, 0))[0]
        - old_symbols.get("__bss_end", (0, 0))[0] != 49
    ):
        raise ProbeError("Bank-0 symbol attribution drift")

    delta = exact(
        value["capacity_delta_from_sealed_candidate"],
        {"bank", "ext", "symbols", "namepool", "directory", "boot_overlay_delta_bytes"},
        "capacity_delta_from_sealed_candidate",
    )
    bank = exact(
        delta["bank"],
        {
            "before_post_boot_reserve_bytes", "after_post_boot_reserve_bytes",
            "release_target_bytes", "before_margin_bytes", "after_margin_bytes",
            "delta_bytes", "attribution",
        },
        "capacity_delta.bank",
    )
    if bank != {
        "before_post_boot_reserve_bytes": 1917,
        "after_post_boot_reserve_bytes": 1868,
        "release_target_bytes": 1536,
        "before_margin_bytes": 381,
        "after_margin_bytes": 332,
        "delta_bytes": -49,
        "attribution": {
            "io_disk_transaction_classify_status_bytes": 27,
            "vm_callprim_bytes": 14,
            "layout_bytes": 8,
            "sum_bytes": 49,
        },
    }:
        raise ProbeError("Bank-0 receipt arithmetic/attribution drift")
    ext = delta["ext"]
    if (
        not isinstance(ext, dict)
        or ext.get("before_post_headroom_bytes") != 16384
        or ext.get("after_post_headroom_bytes") != 16388
        or ext.get("release_floor_bytes") != 16384
        or ext.get("before_margin_bytes") != 0
        or ext.get("after_margin_bytes") != 4
        or ext.get("delta_bytes") != 4
        or ext.get("floor_status") != "held-with-4-byte-margin"
        or ext.get("origin", {}).get("m65d_code_delta_bytes") != -4
        or ext.get("origin", {}).get("m65d_metadata_delta_bytes") != -40
        or ext.get("origin", {}).get("post_headroom_rule")
        != "per-library-metadata-is-reclaimed-after-commit-so-only-the-4-byte-code-reduction-increases-post-headroom"
    ):
        raise ProbeError("EXT floor/margin attribution drift")
    if (
        delta["symbols"] != {"before_headroom": 120, "after_headroom": 120, "delta": 0}
        or delta["namepool"]
        != {"before_headroom_bytes": 2160, "after_headroom_bytes": 2160, "delta_bytes": 0}
        or delta["directory"]
        != {"before_headroom_entries": 32, "after_headroom_entries": 32, "delta_entries": 0}
        or delta["boot_overlay_delta_bytes"] != 0
    ):
        raise ProbeError("unchanged capacity dimensions drift")


def selftest(value: dict[str, Any]) -> None:
    validate(value)
    mutations = (
        lambda x: x["capacity_delta_from_sealed_candidate"]["ext"].update(after_margin_bytes=0),
        lambda x: x["capacity_delta_from_sealed_candidate"]["ext"].update(after_post_headroom_bytes=16384),
        lambda x: x["capacity_delta_from_sealed_candidate"]["ext"]["origin"].update(m65d_code_delta_bytes=0),
        lambda x: x["capacity_delta_from_sealed_candidate"]["bank"]["attribution"].update(layout_bytes=7),
        lambda x: x["baseline"]["m65d_manifest_member"].update(sha256="0" * 64),
        lambda x: x["candidate_probe"]["m65d_manifest"].update(sha256="0" * 64),
    )
    for mutate in mutations:
        changed = deepcopy(value)
        mutate(changed)
        try:
            validate(changed)
        except ProbeError:
            continue
        raise ProbeError("capacity probe mutation survived")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "selftest"))
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        value = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ProbeError("report must contain an object")
        if args.command == "selftest":
            selftest(value)
            print("post-capture-planning-capacity: SELFTEST PASS mutations=6")
        else:
            validate(value)
            print("post-capture-planning-capacity: PASS bank=332 ext=16388 ext-margin=4")
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError, ProbeError) as exc:
        print(f"post-capture-planning-capacity: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
