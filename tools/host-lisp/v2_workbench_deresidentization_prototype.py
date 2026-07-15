#!/usr/bin/env python3
"""Measure a relaxed, non-shippable Workbench-v2 de-residentization prototype."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-v2-workbench-deresidentization-prototype-v1"
LATENCY_FORMAT = "lisp65-number-to-string-latency-observation-v1"
PROTOTYPE_ID = "number-to-string-bytecode"
LINKER_RELATIVE = Path("tools/llvm-mos/mos-platform/mega65/lib/link.ld")
NM_RELATIVE = Path("tools/llvm-mos/bin/llvm-nm")
CC_RELATIVE = Path("tools/llvm-mos/bin/mos-mega65-clang")
SERVICE_REPORT_RELATIVE = Path(
    "build/bytecode/dialect-v2/workbench-service-call-inventory.json"
)
RESIDENT_MANIFEST_RELATIVE = Path(
    "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
)
BACKUP_SUFFIX = ".v2-deresidentization-prototype.backup"
META_SUFFIX = ".v2-deresidentization-prototype.restore.json"
ORIGINAL_MEMORY = b"LENGTH = 0xafff"
RELAXED_MEMORY = b"LENGTH = 0xbfff"
ORIGINAL_STACK = b"__stack = 0xd000;"
RELAXED_STACK = b"__stack = 0xe000;"
VMA_LIMIT = 0xC356
STACK_TOP = 0xD000
RUNTIME_STACK_GAP = 1450
RESERVE_TARGET = 1536
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

PROFILE_ID = "dialect-v2-capability-carrier-workbench-staging"
SUITE = "build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json"
BYTECODE_DIR = "build/bytecode/dialect-v2/workbench"
STDLIB_PREFIX = "build/bytecode/dialect-v2/workbench/stdlib-p0"
EXTRA_DEFINES = (
    "-DLISP65_STACK_GUARD",
    "-DLISP65_DIALECT_V2",
    "-DLISP65_V2_CARRIER_CUT",
    "-DLISP65_VM_NATIVE_APPLY",
    "-DLISP65_V2_NATIVE_CAPABILITIES",
    "-DLISP65_V2_NATIVE_STRING_CODECS",
    "-DLISP65_V2_SERVICE_REGISTRY_CLOSED",
    "-DLISP65_V2_WORKBENCH_SERVICES",
)


class PrototypeError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrototypeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise PrototypeError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except PrototypeError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrototypeError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise PrototypeError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise PrototypeError(f"{label} keys drift: {actual}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_bytes(_canonical(value))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _regular(path: Path, label: str, *, allow_symlink: bool = False) -> Path:
    if path.is_symlink() and not allow_symlink:
        raise PrototypeError(f"{label} must not be a symlink: {path}")
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise PrototypeError(f"cannot resolve {label}: {path}: {exc}") from exc
    if not path.is_file():
        raise PrototypeError(f"{label} must be a regular file: {path}")
    return path


def _run(
    argv: list[str], *, cwd: Path, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=capture,
        check=False,
    )
    if process.returncode != 0:
        detail = ""
        if capture:
            detail = f"\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        raise PrototypeError(
            f"command failed ({process.returncode}): {' '.join(argv)}{detail}"
        )
    return process


def _git_bytes(root: Path, args: list[str]) -> bytes:
    process = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if process.returncode != 0:
        raise PrototypeError(
            f"git {' '.join(args)} failed: "
            + process.stderr.decode("utf-8", errors="replace")
        )
    return process.stdout


def source_snapshot(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not (root / ".git").exists():
        raise PrototypeError(f"source root is not a Git worktree: {root}")
    head = _git_bytes(root, ["rev-parse", "HEAD"]).decode("ascii").strip()
    if COMMIT_RE.fullmatch(head) is None:
        raise PrototypeError(f"cannot resolve source HEAD: {root}")
    status = _git_bytes(
        root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    diff = _git_bytes(root, ["diff", "--binary", "--no-ext-diff", "HEAD", "--"])
    untracked_raw = _git_bytes(
        root, ["ls-files", "--others", "--exclude-standard", "-z"]
    )
    untracked: list[dict[str, str]] = []
    for raw in filter(None, untracked_raw.split(b"\0")):
        try:
            relative = raw.decode("utf-8")
        except UnicodeError as exc:
            raise PrototypeError("untracked source path is not UTF-8") from exc
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise PrototypeError(f"untracked source input is not a regular file: {relative}")
        untracked.append({"path": relative, "sha256": _sha_file(path)})
    untracked.sort(key=lambda item: item["path"])
    source_payload = {
        "head": head,
        "status_sha256": _sha_bytes(status),
        "tracked_diff_sha256": _sha_bytes(diff),
        "untracked": untracked,
    }
    return {
        "root": str(root),
        "head": head,
        "dirty": bool(status),
        "status_sha256": source_payload["status_sha256"],
        "tracked_diff_sha256": source_payload["tracked_diff_sha256"],
        "untracked_count": len(untracked),
        "untracked_sha256": _sha_bytes(_canonical({"files": untracked})),
        "source_sha256": _sha_bytes(_canonical(source_payload)),
    }


def _sidecars(linker: Path) -> tuple[Path, Path]:
    return (
        linker.with_name(linker.name + BACKUP_SUFFIX),
        linker.with_name(linker.name + META_SUFFIX),
    )


def _replace_regular(path: Path, content: bytes, mode: int) -> None:
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def restore_linker(source_root: Path) -> dict[str, Any]:
    linker = _regular(
        source_root.resolve() / LINKER_RELATIVE,
        "platform linker script",
        allow_symlink=True,
    )
    backup, meta_path = _sidecars(linker)
    if not backup.is_file() or backup.is_symlink() or not meta_path.is_file() or meta_path.is_symlink():
        raise PrototypeError(f"complete linker recovery sidecars are not present for {linker}")
    meta = _load(meta_path, "linker recovery metadata")
    _exact(meta, {"format", "linker", "original_sha256", "relaxed_sha256"}, "linker recovery metadata")
    if meta["format"] != "lisp65-relaxed-linker-recovery-v1" or meta["linker"] != str(linker):
        raise PrototypeError("linker recovery metadata identity drift")
    original = backup.read_bytes()
    if _sha_bytes(original) != meta["original_sha256"]:
        raise PrototypeError("linker recovery backup SHA mismatch")
    mode = linker.stat().st_mode & 0o777 if linker.exists() else 0o644
    _replace_regular(linker, original, mode)
    if _sha_file(linker) != meta["original_sha256"]:
        raise PrototypeError("linker restoration verification failed")
    backup.unlink()
    meta_path.unlink()
    return {
        "original_sha256": meta["original_sha256"],
        "relaxed_sha256": meta["relaxed_sha256"],
        "restored": True,
    }


@contextmanager
def relaxed_linker(source_root: Path) -> Iterator[dict[str, Any]]:
    source_root = source_root.resolve()
    linker = _regular(source_root / LINKER_RELATIVE, "platform linker script")
    backup, meta_path = _sidecars(linker)
    if backup.exists() or meta_path.exists():
        raise PrototypeError(
            f"stale linker recovery state; run restore-linker first: {linker}"
        )
    original = linker.read_bytes()
    if original.count(ORIGINAL_MEMORY) != 1 or original.count(ORIGINAL_STACK) != 1:
        raise PrototypeError("platform linker does not contain the exact production geometry")
    if RELAXED_MEMORY in original or RELAXED_STACK in original:
        raise PrototypeError("platform linker is already relaxed")
    relaxed = original.replace(ORIGINAL_MEMORY, RELAXED_MEMORY).replace(
        ORIGINAL_STACK, RELAXED_STACK
    )
    original_sha = _sha_bytes(original)
    relaxed_sha = _sha_bytes(relaxed)
    mode = linker.stat().st_mode & 0o777
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    _write_json(
        meta_path,
        {
            "format": "lisp65-relaxed-linker-recovery-v1",
            "linker": str(linker),
            "original_sha256": original_sha,
            "relaxed_sha256": relaxed_sha,
        },
    )
    _replace_regular(linker, relaxed, mode)
    if _sha_file(linker) != relaxed_sha:
        restore_linker(source_root)
        raise PrototypeError("relaxed linker mutation verification failed")
    binding = {
        "path": str(linker),
        "original_sha256": original_sha,
        "relaxed_sha256": relaxed_sha,
        "restored": False,
    }
    body_error: BaseException | None = None
    try:
        yield binding
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        current_sha = _sha_file(linker) if linker.is_file() and not linker.is_symlink() else None
        try:
            restored = restore_linker(source_root)
            binding.update(restored)
        except BaseException as restore_error:
            raise PrototypeError(
                f"linker restoration failed after build error {body_error!r}: {restore_error}"
            ) from restore_error
        if current_sha != relaxed_sha and body_error is None:
            raise PrototypeError("platform linker changed unexpectedly during relaxed build")


def _build_flags(out: Path) -> list[str]:
    extra = " ".join(EXTRA_DEFINES)
    return [
        f"WORKBENCH_PROFILE_ID={PROFILE_ID}",
        f"WORKBENCH_SUITE={SUITE}",
        f"WORKBENCH_BYTECODE_DIR={BYTECODE_DIR}",
        f"WORKBENCH_STDLIB_PREFIX={STDLIB_PREFIX}",
        f"WORKBENCH_OVERLAY_DIR={out}",
        f"WORKBENCH_PRODUCT_ELF={out / 'lisp65-workbench-overlay-linked.prg.elf'}",
        f"WORKBENCH_OVERLAY_EXTRA_DEFINES={extra}",
        "WORKBENCH_RUNTIME_OVERLAY_MAX_VMA=0xffff",
    ]


def _parse_symbols(nm: Path, elf: Path) -> dict[str, int]:
    process = _run([str(nm), "--defined-only", str(elf)], cwd=elf.parent, capture=True)
    wanted = {
        "__bss_end",
        "__heap_start",
        "__lisp65_workbench_runtime_overlay_vma",
    }
    result: dict[str, int] = {}
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[-1] not in wanted:
            continue
        try:
            value = int(fields[0], 16)
        except ValueError as exc:
            raise PrototypeError(f"invalid llvm-nm value: {line}") from exc
        name = fields[-1]
        if name in result and result[name] != value:
            raise PrototypeError(f"duplicate conflicting ELF symbol: {name}")
        result[name] = value
    if set(result) != wanted:
        raise PrototypeError(f"missing ELF measurement symbols: {sorted(wanted - set(result))}")
    return result


def _tool_binding(source_root: Path, relative: Path) -> dict[str, str]:
    path = _regular(source_root / relative, f"tool {relative}", allow_symlink=True)
    return {"path": str(path), "sha256": _sha_file(path)}


def prototype_artifact_evidence(source_root: Path, label: str) -> dict[str, Any]:
    service_path = _regular(
        source_root / SERVICE_REPORT_RELATIVE, f"{label} service inventory"
    )
    service = _load(service_path, f"{label} service inventory")
    services = service.get("callprim_services")
    if not isinstance(services, list):
        raise PrototypeError(f"{label} service inventory lacks CALLPRIM records")
    prim40 = [item for item in services if isinstance(item, dict) and item.get("id") == 40]
    if len(prim40) != 1:
        raise PrototypeError(f"{label} service inventory must contain exactly one Prim 40 record")
    record = prim40[0]
    profiles = record.get("profiles")
    v2 = profiles.get("dialect-v2") if isinstance(profiles, dict) else None
    if (
        record.get("name") != "number->string"
        or not isinstance(record.get("total_calls"), int)
        or not isinstance(v2, dict)
        or not isinstance(v2.get("status"), str)
    ):
        raise PrototypeError(f"{label} Prim 40 service record drift")
    for field in ("current_misses", "unresolved_sites", "tombstone_callprims"):
        if service.get(field) != []:
            raise PrototypeError(f"{label} service inventory {field} is not empty")

    manifest_path = _regular(
        source_root / RESIDENT_MANIFEST_RELATIVE, f"{label} resident manifest"
    )
    manifest = _load(manifest_path, f"{label} resident manifest")
    functions = manifest.get("functions")
    entries = manifest.get("entries")
    if not isinstance(functions, list) or not isinstance(entries, list):
        raise PrototypeError(f"{label} resident manifest lacks function inventory")
    matching_entries = [
        item for item in entries
        if isinstance(item, dict) and item.get("name") == "number->string"
    ]
    has_definition = "number->string" in functions and len(matching_entries) == 1
    evidence = {
        "service_inventory": {
            "path": str(service_path),
            "sha256": _sha_file(service_path),
            "current_misses": 0,
            "unresolved_sites": 0,
            "tombstone_callprims": 0,
            "prim40_name": record["name"],
            "prim40_total_calls": record["total_calls"],
            "prim40_v2_status": v2["status"],
        },
        "resident_manifest": {
            "path": str(manifest_path),
            "sha256": _sha_file(manifest_path),
            "number_to_string_bytecode_definition": has_definition,
        },
    }
    if label == "baseline":
        if record["total_calls"] <= 0 or v2["status"] != "active" or has_definition:
            raise PrototypeError("baseline does not describe the native Prim 40 implementation")
    elif record["total_calls"] != 0 or v2["status"] != "tombstone" or not has_definition:
        raise PrototypeError(
            "candidate must have zero Prim 40 calls, a v2 tombstone, and one bytecode definition"
        )
    return evidence


def build_variant(label: str, source_root: Path, out: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    before = source_snapshot(source_root)
    if label == "baseline" and before["dirty"]:
        raise PrototypeError("baseline source must be clean")
    if label == "candidate" and not before["dirty"]:
        raise PrototypeError("candidate source must be dirty for the bounded prototype")
    out = out.resolve()
    if out == source_root or source_root in out.parents:
        raise PrototypeError("measurement output must be outside its source worktree")
    if out.exists() and any(out.iterdir()):
        raise PrototypeError(f"measurement output is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    inventory_command = [
        "make", "--no-print-directory", "workbench-service-call-inventory-staging"
    ]
    _run(inventory_command, cwd=source_root)
    artifact_evidence = prototype_artifact_evidence(source_root, label)
    target = out / "resident-island-seed-linked.prg"
    link_command = [
        "make", "--no-print-directory", *_build_flags(out), str(target)
    ]
    started = time.monotonic_ns()
    with relaxed_linker(source_root) as linker:
        _run(link_command, cwd=source_root)
    elapsed_ns = time.monotonic_ns() - started

    after = source_snapshot(source_root)
    if after != before:
        raise PrototypeError(f"{label} source state changed during measurement")
    elf = _regular(Path(str(target) + ".elf"), f"{label} ELF")
    nm_binding = _tool_binding(source_root, NM_RELATIVE)
    symbols = _parse_symbols(Path(nm_binding["path"]), elf)
    return {
        "label": label,
        "source": before,
        "toolchain": {
            "compiler": _tool_binding(source_root, CC_RELATIVE),
            "nm": nm_binding,
            "linker": linker,
        },
        "build": {
            "artifact_inventory_command": inventory_command,
            "link_command": link_command,
            "target": "resident-island-seed-linked.prg",
            "elapsed_ns": elapsed_ns,
            "relaxed_runtime_overlay_max_vma": "0xffff",
        },
        "prototype_artifacts": artifact_evidence,
        "elf": {
            "path": str(elf),
            "sha256": _sha_file(elf),
            "size_bytes": elf.stat().st_size,
        },
        "symbols": {name: f"0x{value:x}" for name, value in sorted(symbols.items())},
    }


def validate_latency(value: dict[str, Any]) -> dict[str, Any]:
    _exact(
        value,
        {
            "format", "version", "metric", "unit", "environment",
            "measurement_command", "iterations_per_sample", "warmup_iterations",
            "baseline_samples", "candidate_samples", "statistic",
            "max_regression_percent", "baseline_elf_sha256",
            "candidate_elf_sha256",
        },
        "latency observation",
    )
    if (
        value["format"] != LATENCY_FORMAT
        or value["version"] != 1
        or value["metric"] != "ide-render-warm-after-insert"
        or value["unit"] != "vm-instructions"
        or not isinstance(value["environment"], str)
        or not value["environment"]
        or not isinstance(value["measurement_command"], list)
        or not value["measurement_command"]
        or not all(isinstance(item, str) and item for item in value["measurement_command"])
        or not isinstance(value["iterations_per_sample"], int)
        or value["iterations_per_sample"] < 1
        or not isinstance(value["warmup_iterations"], int)
        or value["warmup_iterations"] < 0
        or value["statistic"] != "median-total"
        or not isinstance(value["max_regression_percent"], int)
        or value["max_regression_percent"] < 0
        or not isinstance(value["baseline_elf_sha256"], str)
        or SHA_RE.fullmatch(value["baseline_elf_sha256"]) is None
        or not isinstance(value["candidate_elf_sha256"], str)
        or SHA_RE.fullmatch(value["candidate_elf_sha256"]) is None
    ):
        raise PrototypeError("latency observation identity/metadata drift")
    samples: dict[str, list[int]] = {}
    for label in ("baseline", "candidate"):
        raw = value[f"{label}_samples"]
        if (
            not isinstance(raw, list)
            or len(raw) < 3
            or len(raw) % 2 == 0
            or not all(isinstance(item, int) and item > 0 for item in raw)
        ):
            raise PrototypeError(
                f"latency {label} samples must contain an odd count of at least three positive integers"
            )
        samples[label] = raw
    if len(samples["baseline"]) != len(samples["candidate"]):
        raise PrototypeError("latency baseline/candidate sample counts differ")
    baseline = int(statistics.median(samples["baseline"]))
    candidate = int(statistics.median(samples["candidate"]))
    allowed = baseline * (100 + value["max_regression_percent"])
    passed = candidate * 100 <= allowed
    return {
        "receipt_sha256": _sha_bytes(_canonical(value)),
        "metric": value["metric"],
        "unit": value["unit"],
        "environment": value["environment"],
        "measurement_command": value["measurement_command"],
        "baseline_elf_sha256": value["baseline_elf_sha256"],
        "candidate_elf_sha256": value["candidate_elf_sha256"],
        "iterations_per_sample": value["iterations_per_sample"],
        "warmup_iterations": value["warmup_iterations"],
        "sample_count": len(samples["baseline"]),
        "statistic": value["statistic"],
        "baseline_median_total": baseline,
        "candidate_median_total": candidate,
        "delta_total": candidate - baseline,
        "max_regression_percent": value["max_regression_percent"],
        "passes": passed,
        "observation": value,
    }


def _hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or re.fullmatch(r"0x[0-9a-f]+", value) is None:
        raise PrototypeError(f"{label} must be lowercase hexadecimal")
    return int(value, 16)


def create_report(
    baseline: dict[str, Any], candidate: dict[str, Any], latency: dict[str, Any]
) -> dict[str, Any]:
    base_heap = _hex(baseline["symbols"]["__heap_start"], "baseline heap start")
    cand_heap = _hex(candidate["symbols"]["__heap_start"], "candidate heap start")
    base_bss = _hex(baseline["symbols"]["__bss_end"], "baseline bss end")
    cand_bss = _hex(candidate["symbols"]["__bss_end"], "candidate bss end")
    base_vma = _hex(
        baseline["symbols"]["__lisp65_workbench_runtime_overlay_vma"],
        "baseline VMA",
    )
    cand_vma = _hex(
        candidate["symbols"]["__lisp65_workbench_runtime_overlay_vma"],
        "candidate VMA",
    )
    candidate_reserve = STACK_TOP - cand_heap - RUNTIME_STACK_GAP
    metrics = {
        "baseline_bss_end": f"0x{base_bss:x}",
        "candidate_bss_end": f"0x{cand_bss:x}",
        "bss_reclaim_bytes": base_bss - cand_bss,
        "baseline_heap_start": f"0x{base_heap:x}",
        "candidate_heap_start": f"0x{cand_heap:x}",
        "heap_reclaim_bytes": base_heap - cand_heap,
        "baseline_runtime_overlay_vma": f"0x{base_vma:x}",
        "candidate_runtime_overlay_vma": f"0x{cand_vma:x}",
        "vma_reclaim_bytes": base_vma - cand_vma,
        "runtime_overlay_vma_limit": f"0x{VMA_LIMIT:x}",
        "runtime_overlay_vma_pass": cand_vma <= VMA_LIMIT,
        "production_stack_top": f"0x{STACK_TOP:x}",
        "runtime_stack_gap_bytes": RUNTIME_STACK_GAP,
        "candidate_post_boot_reserve_bytes": candidate_reserve,
        "post_boot_reserve_target_bytes": RESERVE_TARGET,
        "post_boot_reserve_pass": candidate_reserve >= RESERVE_TARGET,
    }
    return {
        "format": FORMAT,
        "version": 1,
        "id": PROTOTYPE_ID,
        "status": "relaxed-diagnostic-only",
        "policy": {
            "abi_profile": "dialect-v2",
            "relaxed_link": True,
            "shippable": False,
            "release_authorization": "none",
            "hardware_g5_claim": "none",
            "promotion": False,
            "product_target_built": False,
            "measurement_target": "resident-island-seed-linked.prg",
        },
        "baseline": baseline,
        "candidate": candidate,
        "metrics": metrics,
        "latency": latency,
        "assessment": {
            "link_budget_pass": metrics["runtime_overlay_vma_pass"]
            and metrics["post_boot_reserve_pass"],
            "latency_pass": latency["passes"],
            "prototype_observation_pass": metrics["runtime_overlay_vma_pass"]
            and metrics["post_boot_reserve_pass"]
            and latency["passes"],
            "promotion_eligible": False,
        },
    }


def _validate_source(value: Any, label: str, check_live: bool) -> dict[str, Any]:
    item = _exact(
        value,
        {
            "root", "head", "dirty", "status_sha256", "tracked_diff_sha256",
            "untracked_count", "untracked_sha256", "source_sha256",
        },
        f"{label} source",
    )
    if (
        not isinstance(item["root"], str)
        or COMMIT_RE.fullmatch(item["head"] or "") is None
        or not isinstance(item["dirty"], bool)
        or not isinstance(item["untracked_count"], int)
        or item["untracked_count"] < 0
    ):
        raise PrototypeError(f"{label} source metadata drift")
    for key in ("status_sha256", "tracked_diff_sha256", "untracked_sha256", "source_sha256"):
        if not isinstance(item[key], str) or SHA_RE.fullmatch(item[key]) is None:
            raise PrototypeError(f"{label} source {key} drift")
    if check_live and source_snapshot(Path(item["root"])) != item:
        raise PrototypeError(f"{label} live source binding mismatch")
    return item


def _validate_binding(value: Any, label: str, check_live: bool) -> dict[str, Any]:
    item = _exact(value, {"path", "sha256"}, label)
    if (
        not isinstance(item["path"], str)
        or not isinstance(item["sha256"], str)
        or SHA_RE.fullmatch(item["sha256"]) is None
    ):
        raise PrototypeError(f"{label} binding drift")
    if check_live:
        path = _regular(Path(item["path"]), label)
        if _sha_file(path) != item["sha256"]:
            raise PrototypeError(f"{label} SHA mismatch")
    return item


def _validate_variant(value: Any, label: str, check_live: bool) -> dict[str, Any]:
    item = _exact(
        value,
        {"label", "source", "toolchain", "build", "prototype_artifacts", "elf", "symbols"},
        label,
    )
    if item["label"] != label:
        raise PrototypeError(f"{label} label drift")
    source = _validate_source(item["source"], label, check_live)
    if (label == "baseline" and source["dirty"]) or (label == "candidate" and not source["dirty"]):
        raise PrototypeError(f"{label} dirty-state policy drift")
    toolchain = _exact(item["toolchain"], {"compiler", "nm", "linker"}, f"{label} toolchain")
    _validate_binding(toolchain["compiler"], f"{label} compiler", check_live)
    _validate_binding(toolchain["nm"], f"{label} nm", check_live)
    linker = _exact(
        toolchain["linker"],
        {"path", "original_sha256", "relaxed_sha256", "restored"},
        f"{label} linker",
    )
    if (
        not isinstance(linker["path"], str)
        or linker["restored"] is not True
        or not all(SHA_RE.fullmatch(linker[key] or "") for key in ("original_sha256", "relaxed_sha256"))
        or linker["original_sha256"] == linker["relaxed_sha256"]
    ):
        raise PrototypeError(f"{label} linker binding/restoration drift")
    if check_live and _sha_file(_regular(Path(linker["path"]), f"{label} linker")) != linker["original_sha256"]:
        raise PrototypeError(f"{label} linker is not restored to its original SHA")
    build = _exact(
        item["build"],
        {
            "artifact_inventory_command", "link_command", "target", "elapsed_ns",
            "relaxed_runtime_overlay_max_vma",
        },
        f"{label} build",
    )
    out = Path(item["elf"]["path"]).parent
    expected_link = ["make", "--no-print-directory", *_build_flags(out), str(out / "resident-island-seed-linked.prg")]
    accepted_links = [expected_link]
    if not check_live:
        accepted_links.append([
            part.replace(
                "-DLISP65_V2_NATIVE_STRING_CODECS",
                "-DLISP65_V2_NATIVE_STRING_CAPS",
            )
            for part in expected_link
        ])
    if (
        build["artifact_inventory_command"]
        != ["make", "--no-print-directory", "workbench-service-call-inventory-staging"]
        or build["link_command"] not in accepted_links
        or build["target"] != "resident-island-seed-linked.prg"
        or not isinstance(build["elapsed_ns"], int)
        or build["elapsed_ns"] <= 0
        or build["relaxed_runtime_overlay_max_vma"] != "0xffff"
    ):
        raise PrototypeError(f"{label} build flags/target drift")
    artifacts = _exact(
        item["prototype_artifacts"],
        {"service_inventory", "resident_manifest"},
        f"{label} prototype artifacts",
    )
    service = _exact(
        artifacts["service_inventory"],
        {
            "path", "sha256", "current_misses", "unresolved_sites",
            "tombstone_callprims", "prim40_name", "prim40_total_calls",
            "prim40_v2_status",
        },
        f"{label} service inventory",
    )
    _validate_binding(
        {"path": service["path"], "sha256": service["sha256"]},
        f"{label} service inventory",
        check_live,
    )
    manifest = _exact(
        artifacts["resident_manifest"],
        {"path", "sha256", "number_to_string_bytecode_definition"},
        f"{label} resident manifest",
    )
    _validate_binding(
        {"path": manifest["path"], "sha256": manifest["sha256"]},
        f"{label} resident manifest",
        check_live,
    )
    common_service = (
        service["current_misses"] == 0
        and service["unresolved_sites"] == 0
        and service["tombstone_callprims"] == 0
        and service["prim40_name"] == "number->string"
    )
    if not common_service:
        raise PrototypeError(f"{label} service closure drift")
    if label == "baseline":
        artifact_policy = (
            isinstance(service["prim40_total_calls"], int)
            and service["prim40_total_calls"] > 0
            and service["prim40_v2_status"] == "active"
            and manifest["number_to_string_bytecode_definition"] is False
        )
    else:
        artifact_policy = (
            service["prim40_total_calls"] == 0
            and service["prim40_v2_status"] == "tombstone"
            and manifest["number_to_string_bytecode_definition"] is True
        )
    if not artifact_policy:
        raise PrototypeError(f"{label} Prim 40/bytecode-definition policy drift")
    if check_live and prototype_artifact_evidence(Path(source["root"]), label) != artifacts:
        raise PrototypeError(f"{label} live prototype artifact evidence mismatch")
    elf = _exact(item["elf"], {"path", "sha256", "size_bytes"}, f"{label} ELF")
    _validate_binding({"path": elf["path"], "sha256": elf["sha256"]}, f"{label} ELF", check_live)
    if not isinstance(elf["size_bytes"], int) or elf["size_bytes"] <= 0:
        raise PrototypeError(f"{label} ELF size drift")
    if check_live and Path(elf["path"]).stat().st_size != elf["size_bytes"]:
        raise PrototypeError(f"{label} ELF size mismatch")
    symbols = _exact(
        item["symbols"],
        {"__bss_end", "__heap_start", "__lisp65_workbench_runtime_overlay_vma"},
        f"{label} symbols",
    )
    for name, raw in symbols.items():
        _hex(raw, f"{label} {name}")
    if check_live:
        actual = _parse_symbols(Path(toolchain["nm"]["path"]), Path(elf["path"]))
        expected = {name: f"0x{number:x}" for name, number in sorted(actual.items())}
        if expected != symbols:
            raise PrototypeError(f"{label} live ELF symbols mismatch")
    return item


def validate_report(value: dict[str, Any], *, check_live: bool = True) -> None:
    _exact(
        value,
        {"format", "version", "id", "status", "policy", "baseline", "candidate", "metrics", "latency", "assessment"},
        "prototype report",
    )
    if (
        value["format"] != FORMAT
        or value["version"] != 1
        or value["id"] != PROTOTYPE_ID
        or value["status"] != "relaxed-diagnostic-only"
    ):
        raise PrototypeError("prototype report identity/status drift")
    policy = _exact(
        value["policy"],
        {
            "abi_profile", "relaxed_link", "shippable", "release_authorization",
            "hardware_g5_claim", "promotion", "product_target_built", "measurement_target",
        },
        "prototype policy",
    )
    if policy != {
        "abi_profile": "dialect-v2",
        "relaxed_link": True,
        "shippable": False,
        "release_authorization": "none",
        "hardware_g5_claim": "none",
        "promotion": False,
        "product_target_built": False,
        "measurement_target": "resident-island-seed-linked.prg",
    }:
        raise PrototypeError("prototype non-promotion policy drift")
    baseline = _validate_variant(value["baseline"], "baseline", check_live)
    candidate = _validate_variant(value["candidate"], "candidate", check_live)
    if baseline["source"]["source_sha256"] == candidate["source"]["source_sha256"]:
        raise PrototypeError("baseline and candidate source snapshots are identical")
    if baseline["source"]["head"] != candidate["source"]["head"]:
        raise PrototypeError("baseline and candidate must share the same Git HEAD")
    expected_latency = validate_latency(value["latency"]["observation"])
    if expected_latency != value["latency"]:
        raise PrototypeError("latency receipt/arithmetic drift")
    if (
        expected_latency["baseline_elf_sha256"] != baseline["elf"]["sha256"]
        or expected_latency["candidate_elf_sha256"] != candidate["elf"]["sha256"]
    ):
        raise PrototypeError("latency receipt is not bound to the measured ELF pair")
    expected = create_report(baseline, candidate, expected_latency)
    if expected["metrics"] != value["metrics"] or expected["assessment"] != value["assessment"]:
        raise PrototypeError("prototype metric/assessment arithmetic drift")


def build_pair(args: argparse.Namespace) -> None:
    baseline_root = Path(args.baseline_root).resolve()
    candidate_root = Path(args.candidate_root).resolve()
    if baseline_root == candidate_root:
        raise PrototypeError("baseline and candidate must use separate source worktrees")
    output = Path(args.out_dir).resolve()
    report_path = Path(args.report).resolve()
    if any(root == report_path or root in report_path.parents for root in (baseline_root, candidate_root)):
        raise PrototypeError("prototype report must be written outside both source worktrees")
    if output.exists() and any(output.iterdir()):
        raise PrototypeError(f"prototype output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    baseline = build_variant("baseline", baseline_root, output / "baseline")
    candidate = build_variant("candidate", candidate_root, output / "candidate")
    latency_value = _load(Path(args.latency_receipt), "latency receipt")
    latency = validate_latency(latency_value)
    report = create_report(baseline, candidate, latency)
    validate_report(report)
    _write_json(report_path, report)
    print(
        "prototype=" + PROTOTYPE_ID
        + f" heap_reclaim={report['metrics']['heap_reclaim_bytes']}"
        + f" vma_reclaim={report['metrics']['vma_reclaim_bytes']}"
        + f" reserve={report['metrics']['candidate_post_boot_reserve_bytes']}"
        + f" latency={'pass' if report['latency']['passes'] else 'fail'}"
        + " shippable=false promotion=false"
    )


def build_variants(args: argparse.Namespace) -> None:
    baseline_root = Path(args.baseline_root).resolve()
    candidate_root = Path(args.candidate_root).resolve()
    if baseline_root == candidate_root:
        raise PrototypeError("baseline and candidate must use separate source worktrees")
    output = Path(args.out_dir).resolve()
    variants_path = Path(args.variants).resolve()
    if any(root == variants_path or root in variants_path.parents for root in (baseline_root, candidate_root)):
        raise PrototypeError("variant receipt must be written outside both source worktrees")
    if output.exists() and any(output.iterdir()):
        raise PrototypeError(f"prototype output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    baseline = build_variant("baseline", baseline_root, output / "baseline")
    candidate = build_variant("candidate", candidate_root, output / "candidate")
    if baseline["source"]["head"] != candidate["source"]["head"]:
        raise PrototypeError("baseline and candidate must share the same Git HEAD")
    _write_json(
        variants_path,
        {
            "format": "lisp65-v2-workbench-deresidentization-variants-v1",
            "version": 1,
            "baseline": baseline,
            "candidate": candidate,
        },
    )
    print(
        f"prototype variants built: baseline={baseline['elf']['sha256']} "
        f"candidate={candidate['elf']['sha256']}"
    )


def seal_report(args: argparse.Namespace) -> None:
    variants = _load(Path(args.variants), "prototype variant receipt")
    _exact(variants, {"format", "version", "baseline", "candidate"}, "prototype variants")
    if (
        variants["format"] != "lisp65-v2-workbench-deresidentization-variants-v1"
        or variants["version"] != 1
    ):
        raise PrototypeError("prototype variant receipt identity drift")
    baseline = _validate_variant(variants["baseline"], "baseline", False)
    candidate = _validate_variant(variants["candidate"], "candidate", False)
    if baseline["source"]["head"] != candidate["source"]["head"]:
        raise PrototypeError("baseline and candidate must share the same Git HEAD")
    latency = validate_latency(_load(Path(args.latency_receipt), "latency receipt"))
    report = create_report(baseline, candidate, latency)
    validate_report(report, check_live=False)
    _write_json(Path(args.report).resolve(), report)
    print(
        "prototype=" + PROTOTYPE_ID
        + f" heap_reclaim={report['metrics']['heap_reclaim_bytes']}"
        + f" vma_reclaim={report['metrics']['vma_reclaim_bytes']}"
        + f" reserve={report['metrics']['candidate_post_boot_reserve_bytes']}"
        + f" latency={'pass' if report['latency']['passes'] else 'fail'}"
        + " shippable=false promotion=false"
    )


def _selftest_variant(root: Path, label: str, elf: Path, dirty: bool) -> dict[str, Any]:
    snapshot = source_snapshot(root)
    if snapshot["dirty"] != dirty:
        raise PrototypeError("selftest dirty setup failed")
    linker = root / LINKER_RELATIVE
    nm = root / NM_RELATIVE
    compiler = root / CC_RELATIVE
    out = elf.parent
    link_command = ["make", "--no-print-directory", *_build_flags(out), str(out / "resident-island-seed-linked.prg")]
    return {
        "label": label,
        "source": snapshot,
        "toolchain": {
            "compiler": {"path": str(compiler.resolve()), "sha256": _sha_file(compiler)},
            "nm": {"path": str(nm.resolve()), "sha256": _sha_file(nm)},
            "linker": {
                "path": str(linker.resolve()),
                "original_sha256": _sha_file(linker),
                "relaxed_sha256": "1" * 64,
                "restored": True,
            },
        },
        "build": {
            "artifact_inventory_command": ["make", "--no-print-directory", "workbench-service-call-inventory-staging"],
            "link_command": link_command,
            "target": "resident-island-seed-linked.prg",
            "elapsed_ns": 1,
            "relaxed_runtime_overlay_max_vma": "0xffff",
        },
        "prototype_artifacts": {
            "service_inventory": {
                "path": str(root / "service-inventory.json"),
                "sha256": "3" * 64,
                "current_misses": 0,
                "unresolved_sites": 0,
                "tombstone_callprims": 0,
                "prim40_name": "number->string",
                "prim40_total_calls": 4 if label == "baseline" else 0,
                "prim40_v2_status": "active" if label == "baseline" else "tombstone",
            },
            "resident_manifest": {
                "path": str(root / "resident-manifest.json"),
                "sha256": "4" * 64,
                "number_to_string_bytecode_definition": label == "candidate",
            },
        },
        "elf": {"path": str(elf), "sha256": _sha_file(elf), "size_bytes": elf.stat().st_size},
        "symbols": {
            "__bss_end": "0xcc70" if label == "baseline" else "0xca70",
            "__heap_start": "0xcc78" if label == "baseline" else "0xca78",
            "__lisp65_workbench_runtime_overlay_vma": "0xcc78" if label == "baseline" else "0xca78",
        },
    }


def selftest() -> None:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-deres-selftest-") as temp:
        base = Path(temp)
        baseline_root = base / "baseline"
        candidate_root = base / "candidate"
        (baseline_root / LINKER_RELATIVE.parent).mkdir(parents=True)
        (baseline_root / NM_RELATIVE.parent).mkdir(parents=True, exist_ok=True)
        (baseline_root / LINKER_RELATIVE).write_bytes(
            b"MEMORY { ram (rw) : ORIGIN = 0x2001, LENGTH = 0xafff }\n__stack = 0xd000;\n"
        )
        (baseline_root / NM_RELATIVE).write_text("nm\n", encoding="ascii")
        (baseline_root / CC_RELATIVE).write_text("cc\n", encoding="ascii")
        _run(["git", "init", "-q"], cwd=baseline_root)
        _run(["git", "config", "user.email", "selftest@example.invalid"], cwd=baseline_root)
        _run(["git", "config", "user.name", "Selftest"], cwd=baseline_root)
        _run(["git", "add", "."], cwd=baseline_root)
        _run(["git", "commit", "-q", "-m", "fixture"], cwd=baseline_root)
        _run(["git", "clone", "-q", str(baseline_root), str(candidate_root)], cwd=base)
        roots = [baseline_root, candidate_root]
        (roots[1] / "candidate-change.txt").write_text("dirty\n", encoding="ascii")

        original = (roots[0] / LINKER_RELATIVE).read_bytes()
        try:
            with relaxed_linker(roots[0]) as binding:
                if binding["restored"] or RELAXED_STACK not in (roots[0] / LINKER_RELATIVE).read_bytes():
                    failures.append("linker mutation was not active inside context")
                raise RuntimeError("forced body failure")
        except RuntimeError:
            pass
        if (roots[0] / LINKER_RELATIVE).read_bytes() != original:
            failures.append("linker was not restored after body failure")
        if any(path.exists() for path in _sidecars(roots[0] / LINKER_RELATIVE)):
            failures.append("linker recovery sidecars survived successful restoration")

        for index, root in enumerate(roots):
            linker = root / LINKER_RELATIVE
            backup, meta = _sidecars(linker)
            backup.write_bytes(linker.read_bytes())
            _write_json(meta, {
                "format": "lisp65-relaxed-linker-recovery-v1",
                "linker": str(linker.resolve()),
                "original_sha256": _sha_file(linker),
                "relaxed_sha256": "2" * 64,
            })
            linker.write_bytes(linker.read_bytes().replace(ORIGINAL_STACK, RELAXED_STACK))
            restored = restore_linker(root)
            if not restored["restored"] or linker.read_bytes() != original:
                failures.append(f"explicit linker recovery failed for fixture {index}")

        out_base = base / "out" / "baseline"
        out_cand = base / "out" / "candidate"
        out_base.mkdir(parents=True)
        out_cand.mkdir(parents=True)
        elf_base = out_base / "resident-island-seed-linked.prg.elf"
        elf_cand = out_cand / "resident-island-seed-linked.prg.elf"
        elf_base.write_bytes(b"baseline-elf")
        elf_cand.write_bytes(b"candidate-elf")
        baseline = _selftest_variant(roots[0], "baseline", elf_base, False)
        candidate = _selftest_variant(roots[1], "candidate", elf_cand, True)
        latency_input = {
            "format": LATENCY_FORMAT,
            "version": 1,
            "metric": "ide-render-warm-after-insert",
            "unit": "vm-instructions",
            "environment": "selftest",
            "measurement_command": ["selftest-benchmark"],
            "iterations_per_sample": 100,
            "warmup_iterations": 10,
            "baseline_samples": [1000, 1100, 1050],
            "candidate_samples": [1200, 1150, 1100],
            "statistic": "median-total",
            "max_regression_percent": 10,
            "baseline_elf_sha256": _sha_file(elf_base),
            "candidate_elf_sha256": _sha_file(elf_cand),
        }
        report = create_report(baseline, candidate, validate_latency(latency_input))
        try:
            validate_report(report, check_live=False)
        except PrototypeError as exc:
            failures.append(f"valid report rejected: {exc}")

        mutations = {
            "promotion": lambda value: value["policy"].__setitem__("promotion", True),
            "reserve": lambda value: value["metrics"].__setitem__("candidate_post_boot_reserve_bytes", 9999),
            "latency": lambda value: value["latency"].__setitem__("candidate_median_total", 1),
            "flags": lambda value: value["candidate"]["build"]["link_command"].append("UNBOUND=1"),
            "dirty": lambda value: value["candidate"]["source"].__setitem__("dirty", False),
            "restored": lambda value: value["candidate"]["toolchain"]["linker"].__setitem__("restored", False),
            "prim40": lambda value: value["candidate"]["prototype_artifacts"]["service_inventory"].__setitem__("prim40_total_calls", 1),
            "bytecode-definition": lambda value: value["candidate"]["prototype_artifacts"]["resident_manifest"].__setitem__("number_to_string_bytecode_definition", False),
        }
        for label, mutate in mutations.items():
            changed = json.loads(json.dumps(report))
            mutate(changed)
            try:
                validate_report(changed, check_live=False)
            except PrototypeError:
                continue
            failures.append(f"mutation accepted: {label}")

    if failures:
        raise PrototypeError("selftest failures:\n- " + "\n- ".join(failures))
    print("v2 Workbench de-residentization prototype selftest: ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    build = sub.add_parser("build-pair")
    build.add_argument("--baseline-root", required=True)
    build.add_argument("--candidate-root", required=True)
    build.add_argument("--out-dir", required=True)
    build.add_argument("--latency-receipt", required=True)
    build.add_argument("--report", required=True)
    variants = sub.add_parser("build-variants")
    variants.add_argument("--baseline-root", required=True)
    variants.add_argument("--candidate-root", required=True)
    variants.add_argument("--out-dir", required=True)
    variants.add_argument("--variants", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--variants", required=True)
    seal.add_argument("--latency-receipt", required=True)
    seal.add_argument("--report", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--report", required=True)
    verify.add_argument("--offline", action="store_true")
    restore = sub.add_parser("restore-linker")
    restore.add_argument("--source-root", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "build-pair":
            build_pair(args)
        elif args.command == "build-variants":
            build_variants(args)
        elif args.command == "seal":
            seal_report(args)
        elif args.command == "verify":
            validate_report(
                _load(Path(args.report), "prototype report"),
                check_live=not args.offline,
            )
            print("v2 Workbench de-residentization prototype report: ok")
        elif args.command == "restore-linker":
            restored = restore_linker(Path(args.source_root))
            print(f"platform linker restored: {restored['original_sha256']}")
        else:
            raise PrototypeError(f"unknown command: {args.command}")
    except PrototypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
