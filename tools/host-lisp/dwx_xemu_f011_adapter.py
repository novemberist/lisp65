#!/usr/bin/env python3
"""Build the version-bound Xemu F011 mapped-buffer adapter used by DWX."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile

from evidence_era import era_blob


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/dwx-xemu-link73-contract.json"
RECEIPT_PATH = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-link73-xemu-boot-receipt-20260902.json"
PATCH_RECEIPT_ERA = "1d86e948e60af586f200cc3972cfee945a0451b5"


class ContractError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, check=True, **kwargs)


def contract() -> dict[str, object]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if value.get("format") != "lisp65-dwx-xemu-link73-contract-v1":
        raise ContractError("unexpected DWX Xemu contract format")
    return value


def source_revision(source: Path) -> str:
    return run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
    ).stdout.decode().strip()


def verify_source(source: Path, cfg: dict[str, object]) -> None:
    expected = cfg["xemu_source"]
    assert isinstance(expected, dict)
    revision = source_revision(source)
    if revision != expected["commit"]:
        raise ContractError(
            f"Xemu source revision mismatch: expected {expected['commit']}, got {revision}"
        )
    for relative, key in (
        ("targets/mega65/sdcard.c", "sdcard_c_sha256"),
        ("targets/mega65/io_mapper.c", "io_mapper_c_sha256"),
    ):
        observed = sha256(source / relative)
        if observed != expected[key]:
            raise ContractError(
                f"Xemu source mismatch for {relative}: expected {expected[key]}, got {observed}"
            )


def safe_extract(archive: bytes, destination: Path) -> None:
    destination_abs = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as handle:
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if target != destination_abs and destination_abs not in target.parents:
                raise ContractError(f"unsafe archive member: {member.name}")
        handle.extractall(destination)


def verify_selected_views(source_text: str) -> None:
    body_start = source_text.find("static XEMU_INLINE void set_disk_buffer_cpu_view")
    body_end = source_text.find("\n}\n", body_start)
    if body_start < 0 or body_end < 0:
        raise ContractError("cannot derive set_disk_buffer_cpu_view body")
    body = source_text[body_start:body_end]
    required = (
        "selected_buffer = disk_buffers + ((sd_regs[9] & 0x80) ? SD_BUFFER_POS : FD_BUFFER_POS)",
        "disk_buffer_cpu_view = selected_buffer",
        "disk_buffer_io_mapped = selected_buffer",
    )
    missing = [item for item in required if item not in body]
    if missing:
        raise ContractError("patched Xemu does not bind both CPU views: " + ", ".join(missing))


def patch_semantics(raw: bytes) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lines = raw.decode("utf-8").splitlines()
    removed = tuple(line[1:].strip() for line in lines
                    if line.startswith("-") and not line.startswith("---"))
    added = tuple(line[1:].strip() for line in lines
                  if line.startswith("+") and not line.startswith("+++"))
    required_added = (
        "Uint8 *const selected_buffer = disk_buffers + ((sd_regs[9] & 0x80) ? SD_BUFFER_POS : FD_BUFFER_POS);",
        "disk_buffer_cpu_view = selected_buffer;",
        "disk_buffer_io_mapped = selected_buffer;",
    )
    if added != required_added or len(removed) != 1:
        raise ContractError("F011 patch semantic delta drift")
    return removed, added


def build(source: Path, output: Path, prefix: list[str]) -> dict[str, object]:
    cfg = contract()
    verify_source(source, cfg)
    output = output.resolve()
    build_root = (ROOT / "build").resolve()
    if output == build_root or build_root not in output.parents:
        raise ContractError(f"output must be below {build_root}")
    if output.exists():
        raise ContractError(f"output already exists: {output}")
    output.mkdir(parents=True)

    revision = cfg["xemu_source"]["commit"]
    archive = run(
        ["git", "-C", str(source), "archive", str(revision)],
        stdout=subprocess.PIPE,
    ).stdout
    safe_extract(archive, output)

    patch_path = ROOT / str(cfg["adapter"]["patch"])
    before_sha = sha256(output / "targets/mega65/sdcard.c")
    run(
        ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch_path)],
        cwd=output,
    )
    patched_source = output / "targets/mega65/sdcard.c"
    verify_selected_views(patched_source.read_text(encoding="utf-8"))

    command = prefix + ["make", "-C", str(output / "targets/mega65"), "-j2"]
    env = dict(os.environ)
    env.update(
        {
            "TRAVIS_BRANCH": "dwx-f011-adapter",
            "TRAVIS_COMMIT": str(revision),
        }
    )
    run(command, env=env)
    binary = output / "build/bin/xmega65.native"
    if not binary.is_file():
        raise ContractError(f"Xemu build did not emit {binary}")

    receipt = {
        "format": "lisp65-dwx-xemu-f011-adapter-build-v1",
        "status": "PASS",
        "source": {
            "root": str(source.resolve()),
            "commit": revision,
            "sdcard_c_before_sha256": before_sha,
            "sdcard_c_after_sha256": sha256(patched_source),
            "io_mapper_c_sha256": sha256(output / "targets/mega65/io_mapper.c"),
        },
        "patch": {"path": str(patch_path.relative_to(ROOT)), "sha256": sha256(patch_path)},
        "binary": {"path": str(binary), "sha256": sha256(binary)},
        "proof": {
            "flat_cpu_view_follows_d689_7": True,
            "de00_io_view_follows_d689_7": True,
            "both_views_share_one_derived_pointer": True,
        },
        "claim_limit": "Tooling adapter only; no product byte and no device-acceptance claim.",
    }
    manifest = output / "dwx-xemu-f011-adapter.json"
    manifest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def selftest() -> None:
    good = """static XEMU_INLINE void set_disk_buffer_cpu_view ( void )
{
 Uint8 *const selected_buffer = disk_buffers + ((sd_regs[9] & 0x80) ? SD_BUFFER_POS : FD_BUFFER_POS);
 disk_buffer_cpu_view = selected_buffer;
 disk_buffer_io_mapped = selected_buffer;
}
"""
    verify_selected_views(good)
    cfg = contract()
    patch_path = ROOT / str(cfg["adapter"]["patch"])
    historical_patch = era_blob(
        PATCH_RECEIPT_ERA, patch_path.relative_to(ROOT).as_posix())
    if patch_semantics(patch_path.read_bytes()) != patch_semantics(historical_patch):
        raise ContractError("licensed patch no longer matches its sealed functional delta")
    mutations = {
        "io-view-remains-sd-only": good.replace(
            "disk_buffer_io_mapped = selected_buffer;", "disk_buffer_io_mapped = disk_buffers + SD_BUFFER_POS;"
        ),
        "flat-view-remains-f011-only": good.replace(
            "disk_buffer_cpu_view = selected_buffer;", "disk_buffer_cpu_view = disk_buffers + FD_BUFFER_POS;"
        ),
        "selector-lost": good.replace("sd_regs[9] & 0x80", "0"),
    }
    for name, value in mutations.items():
        try:
            verify_selected_views(value)
        except ContractError:
            continue
        raise ContractError(f"mutation survived: {name}")
    print(f"dwx-xemu-f011-adapter selftest PASS mutations={len(mutations)}")


def check() -> None:
    cfg = contract()
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    source = cfg["xemu_source"]
    binding = receipt.get("source_binding", {})
    patch_path = ROOT / str(cfg["adapter"]["patch"])
    historical_patch = era_blob(
        PATCH_RECEIPT_ERA, patch_path.relative_to(ROOT).as_posix())
    if patch_semantics(patch_path.read_bytes()) != patch_semantics(historical_patch):
        raise ContractError("current F011 patch differs functionally from sealed receipt")
    expected = {
        "sdcard_c_sha256": source["sdcard_c_sha256"],
        "io_mapper_c_sha256": source["io_mapper_c_sha256"],
        "patch_path": str(patch_path.relative_to(ROOT)),
        "patch_sha256": hashlib.sha256(historical_patch).hexdigest(),
    }
    observed = {key: binding.get(key) for key in expected}
    if observed != expected:
        raise ContractError(f"adapter receipt drift: expected {expected}, got {observed}")
    if (
        receipt.get("status") != "PASS"
        or receipt.get("product_bytes_changed") != 0
        or receipt.get("attribution", {}).get("xemu_source_commit") != source["commit"]
        or receipt.get("mutations", {}).get("adapter")
        != ["io-view-remains-sd-only", "flat-view-remains-f011-only", "selector-lost"]
        or receipt.get("mutations", {}).get("survived") != []
    ):
        raise ContractError("adapter receipt lost its claim boundary or mutation set")
    print("dwx-xemu-f011-adapter check PASS receipt-bound")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/dwx/xemu-f011-adapter")
    parser.add_argument(
        "--build-prefix",
        default=os.environ.get("DWX_XEMU_BUILD_PREFIX", ""),
        help="command prefix, e.g. 'distrobox enter arch --'",
    )
    args = parser.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
    if args.check:
        check()
        return 0
    if args.source is None:
        parser.error("--source is required unless --selftest is used")
    receipt = build(args.source, args.output, shlex.split(args.build_prefix))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ContractError, subprocess.CalledProcessError, OSError) as error:
        print(f"dwx-xemu-f011-adapter: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
