#!/usr/bin/env python3
"""Black-box self-test for the Ship-v5 reset/remount hardware dry-run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "hw-workbench-overlay-stack-smoke.sh"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def require(
    condition: bool,
    message: str,
    result: subprocess.CompletedProcess[str] | None = None,
) -> None:
    if condition:
        return
    detail = ""
    if result is not None:
        detail = f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    raise AssertionError(message + detail)


def fixture(root: Path) -> tuple[Path, dict[str, Path], dict[str, object]]:
    island = b"resident-island-image"
    installer = b"slot-37-prefix:" + island + b":slot-37-suffix"
    slot_offset = 64
    payloads = {
        "workbench-prg": b"\x01\x20resident-prg-payload",
        "workbench-stdlib-blob": b"bank5-preload",
        "workbench-runtime-overlays": bytes(slot_offset) + installer,
        "workbench-d81": b"d81-fixture",
    }
    names = {
        "workbench-prg": "lisp65-mvp-workbench.prg",
        "workbench-stdlib-blob": "lisp65-mvp-workbench.blob.bin",
        "workbench-runtime-overlays": "lisp65-mvp-workbench.overlays.bin",
        "workbench-d81": "lisp65-mvp-workbench.d81",
    }
    paths = {artifact_id: root / name for artifact_id, name in names.items()}
    for artifact_id, path in paths.items():
        path.write_bytes(payloads[artifact_id])
    elf = root / "lisp65-workbench-overlay-linked.prg.elf"
    elf.write_bytes(b"manifest-bound-island-elf")
    island_section = root / "island-section.bin"
    island_section.write_bytes(island)
    installer_section = root / "island-installer-section.bin"
    installer_section.write_bytes(installer)
    nm = root / "fake-llvm-nm"
    nm.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' "
        "'00001800 T __lisp65_resident_island_start' "
        f"'{0x1800 + len(island):08x} T __lisp65_resident_island_end' "
        "'0000cc00 T __lisp65_workbench_runtime_overlay_limit' "
        "'00003000 B lisp65_boot_probe_complete' "
        "'00003001 B lisp65_boot_probe_flags' "
        "'00003002 B lisp65_boot_probe_soft_initial' "
        "'00003004 B lisp65_boot_probe_hw_initial' "
        "'00003005 B lisp65_boot_overlay_wipe_ok' "
        "'00001c54 B __lisp65_resident_island_annex_start' "
        "'00001c54 B lisp65_rootstack_canary_before' "
        "'00001c56 B gc_rootstack' "
        "'00001d56 B lisp65_rootstack_canary_after' "
        "'00001d58 B __lisp65_resident_island_annex_end'\n",
        encoding="ascii",
    )
    nm.chmod(0o755)
    objcopy = root / "fake-llvm-objcopy"
    objcopy.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "section = next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--only-section='))\n"
        f"sources = {{'.lisp65_resident_island': {str(island_section)!r}, "
        f"'.lisp65_rt_island_00': {str(installer_section)!r}}}\n"
        "Path(sys.argv[-1]).write_bytes(Path(sources[section]).read_bytes())\n",
        encoding="ascii",
    )
    objcopy.chmod(0o755)
    paths["workbench-elf"] = elf
    paths["nm"] = nm
    paths["objcopy"] = objcopy
    manifest: dict[str, object] = {
        "manifest_format": "lisp65-workbench-ship-v5",
        "artifacts": [
            {
                "id": artifact_id,
                "path": names[artifact_id],
                "size": len(payload),
                "sha256": sha256(payload),
            }
            for artifact_id, payload in payloads.items()
        ],
        "preloads": [
            {
                "role": "runtime-overlays",
                "artifact": "workbench-runtime-overlays",
                "file": names["workbench-runtime-overlays"],
                "kind": "attic-ram",
                "address": 0x08000000,
                "address_bits": 28,
                "length": len(payloads["workbench-runtime-overlays"]),
                "crc16": crc16(payloads["workbench-runtime-overlays"]),
                "crc16_algorithm": "crc-16-ccitt-false",
                "sha256": sha256(payloads["workbench-runtime-overlays"]),
                "build_id": 0x12345678,
                "persistence": "reset-stable-power-volatile",
                "recovery": "redeploy-required",
            },
            {
                "role": "workbench-stdlib-boot",
                "artifact": "workbench-stdlib-blob",
                "file": names["workbench-stdlib-blob"],
                "bank": 5,
                "address": 0x00050000,
                "size": len(payloads["workbench-stdlib-blob"]),
                "sha256": sha256(payloads["workbench-stdlib-blob"]),
            },
        ],
        "runtime_overlays": {
            "schema": "lisp65-runtime-overlay-package-v2",
            "profile_build_id": 0x12345678,
            "elf": {
                "file": elf.name,
                "sha256": sha256(elf.read_bytes()),
            },
            "slices": [
                {
                    "id": 37,
                    "name": "resident-island-installer",
                    "roles": ["boot"],
                    "slice_build_id": 0x12345678,
                    "file_offset": slot_offset,
                    "file_size": len(installer),
                    "sha256": sha256(installer),
                    "crc16": crc16(installer),
                }
            ],
            "storage": {
                "format": "lisp65-runtime-overlay-bank-v1",
                "file": names["workbench-runtime-overlays"],
                "kind": "attic-ram",
                "address": 0x08000000,
                "address_bits": 28,
                "limit": 0x08010000,
                "size": len(payloads["workbench-runtime-overlays"]),
                "build_id": 0x12345678,
                "crc16": crc16(payloads["workbench-runtime-overlays"]),
                "crc16_algorithm": "crc-16-ccitt-false",
                "sha256": sha256(payloads["workbench-runtime-overlays"]),
                "persistence": "reset-stable-power-volatile",
            },
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="ascii")
    return manifest_path, paths, manifest


def command(
    root: Path,
    manifest: Path,
    paths: dict[str, Path],
    extra: tuple[str, ...] = (),
    *,
    readback: bool = False,
) -> list[str]:
    result = [
        "sh",
        str(SMOKE),
        "--dry-run",
    ]
    if not readback:
        result.append("--no-readback")
    result.extend([
        "--ship-manifest",
        str(manifest),
        "--tools",
        str(root / "fake-tools"),
        "--device",
        "fake-jtag",
        "--resident-prg",
        str(paths["workbench-prg"]),
        "--preload",
        str(paths["workbench-stdlib-blob"]),
        "--runtime-overlay",
        str(paths["workbench-runtime-overlays"]),
        "--elf",
        str(paths["workbench-elf"]),
        "--nm",
        str(paths["nm"]),
        "--objcopy",
        str(paths["objcopy"]),
        "--d81",
        str(paths["workbench-d81"]),
        "--remote-d81",
        "G5TEST.D81",
        "--out-dir",
        str(root / "out"),
        "--prefix",
        "g5-test",
        "--boot-wait",
        "0",
        "--boot-ready-timeout",
        "60",
        "--wait",
        "0",
        "--form-wait",
        "0",
        *extra,
    ])
    return result


def run(
    root: Path,
    manifest: Path,
    paths: dict[str, Path],
    extra: tuple[str, ...] = (),
    *,
    readback: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command(root, manifest, paths, extra, readback=readback),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


def check_workflow(root: Path, manifest: Path, paths: dict[str, Path]) -> None:
    result = run(root, manifest, paths)
    require(result.returncode == 0, "complete G5 dry-run must pass", result)
    require("mega65_ftp" in result.stdout and "put " in result.stdout,
            "G5 dry-run must upload the manifest-bound D81", result)
    markers = [
        "G5 Stage A: Attic und Bank 5 per JTAG laden",
        "G5 Stage A SHA: ungelaufener PRG-Payload, Bank 5 und Attic",
        "Ship-v5 memory readback staged: DRY-RUN",
        "G5 Stage B: kanonischer Etherload-Reset, Remount und PRG-Reload/Run",
        "G5 Stage B Attic-SHA und Insel-Canary nach Reset und Produktboot",
        "Ship-v5 memory readback post-reset: DRY-RUN",
        "JTAG-REPL-Probe: load-ide",
        "--expect '\"overlay-ide-ok\"'",
    ]
    positions = [result.stdout.find(marker) for marker in markers]
    require(all(position >= 0 for position in positions), "G5 dry-run is missing a required phase", result)
    require(positions == sorted(positions), "G5 dry-run phases are out of order", result)
    require(result.stdout.count("expect attic-catalog address=0x08000000") == 2,
            "Attic must be checked before and after reset", result)
    require(result.stdout.count("expect resident-island address=0x00001800") == 1,
            "installed island must be checked exactly once after reset", result)
    require("poll manifest-bound island canary for up to 60s" in result.stdout,
            "G5 must gate post-reset progress on the bound island canary", result)
    require("expect resident-island address=0x00001800 length=21 sha256=" in result.stdout
            and "crc16=0x" in result.stdout,
            "island canary must pin exact length, SHA-256 and CRC-16", result)
    require("expect prg-payload address=0x00002001" in result.stdout,
            "resident PRG payload readback is missing", result)
    require("expect bank5-preload address=0x00050000" in result.stdout,
            "Bank-5 readback is missing", result)
    stage_a = result.stdout[positions[0]:positions[1]]
    require(stage_a.count(" -H -@ ") == 2 and " -H -1 " in stage_a,
            "Stage A must use two raw JTAG loads and one halted PRG load", result)
    stage_b = result.stdout[positions[3]:positions[4]]
    require("--preload-bin" not in stage_b, "Stage B must not refresh preloads", result)
    require("etherload -m G5TEST.D81 -r" in stage_b,
            "Stage B must reset/remount/reload through canonical etherload", result)
    load_ide_oracle = result.stdout[positions[6]:positions[7]]
    require("repl_screen_check.py" in load_ide_oracle,
            "load-lib result must use the structured REPL oracle", result)
    require(
        "Post-IDE-Stack/Wipe-Readback uebersprungen "
        "(--no-readback: Guard-ELF hat keine LISP65_BOOT_STACK_PROBE-Canaries)"
        in result.stdout,
        "guard-only G5 must explicitly disclose missing post-IDE stack evidence",
        result,
    )
    require("hw-stack-probe: dry-run" not in result.stdout,
            "--no-readback must retain guard-only semantics", result)
    receipt = root / "out" / "g5-test-ship-manifest-receipt.json"
    require(receipt.is_file(), "Stage A must emit the manifest receipt", result)
    receipt_data = json.loads(receipt.read_text())
    require(receipt_data.get("dry_run") is True,
            "dry-run receipt must remain explicitly non-live evidence", result)
    require(receipt_data.get("island_sha256") == sha256(b"resident-island-image"),
            "Stage-A receipt must bind the exact resident island image", result)


def check_stack_readback_workflow(
    root: Path, manifest: Path, paths: dict[str, Path]
) -> None:
    result = run(root, manifest, paths, readback=True)
    require(result.returncode == 0, "readback-capable G5 dry-run must pass", result)
    runtime_stack = result.stdout.find("==> Runtime-Stack/Wipe-Readback")
    load_ide = result.stdout.find("==> JTAG-REPL-Probe: load-ide")
    post_ide = result.stdout.find("==> Post-IDE-Stack/Wipe-Readback")
    compile_kind = result.stdout.find("==> JTAG-REPL-Probe: compile-kind")
    require(min(runtime_stack, load_ide, post_ide, compile_kind) >= 0,
            "readback-capable G5 is missing a stack phase", result)
    require(runtime_stack < load_ide < post_ide < compile_kind,
            "post-IDE stack readback must immediately follow successful load-ide", result)
    require(result.stdout.count("hw-stack-probe: dry-run") == 2,
            "readback-capable G5 must run exactly two stack decoders", result)
    require("g5-test-stack-post-ide-lisp65_boot_probe_complete.bin" in result.stdout,
            "post-IDE stack readback needs its own evidence prefix", result)
    require(
        result.stdout.count("rootstack-annex-canary-before") == 2
        and result.stdout.count("rootstack-annex-canary-after") == 2,
        "boot and post-IDE phases must both capture annex canary evidence",
        result,
    )

    reports = [
        root / "out" / "g5-test-stack.txt",
        root / "out" / "g5-test-stack-post-ide.txt",
    ]
    for report in reports:
        require(report.is_file(), f"missing stack dry-run report {report.name}", result)
        body = report.read_text(encoding="ascii")
        require("min_soft_margin=256" in body and "min_hw_remaining=32" in body,
                f"{report.name} must bind both hard stack margins", result)
        require("status=DRY-RUN" in body,
                f"{report.name} must remain explicit dry-run evidence", result)
        require("rootstack_annex_evidence=present" in body,
                f"{report.name} must disclose annex canary evidence", result)


def check_manifest_fail_closed(
    root: Path, manifest: Path, paths: dict[str, Path], data: dict[str, object]
) -> None:
    bad = root / "bad-format.json"
    mutated = json.loads(json.dumps(data))
    mutated["manifest_format"] = "lisp65-workbench-ship-v4"
    bad.write_text(json.dumps(mutated, sort_keys=True) + "\n", encoding="ascii")
    result = run(root, bad, paths)
    require(result.returncode != 0, "non-v5 manifest must fail", result)
    require("G5 Stage B" not in result.stdout, "manifest failure must happen before Stage B", result)


def check_deploy_binding_fail_closed(
    root: Path, manifest: Path, paths: dict[str, Path]
) -> None:
    wrong = root / "wrong.prg"
    wrong.write_bytes(b"\x01\x20wrong-payload")
    supplied = dict(paths)
    supplied["workbench-prg"] = wrong
    result = run(root, manifest, supplied)
    require(result.returncode != 0, "unbound deployed PRG must fail", result)
    require("G5 Stage B" not in result.stdout, "artifact failure must happen before Stage B", result)


def check_target_addresses_fail_closed(
    root: Path, manifest: Path, paths: dict[str, Path]
) -> None:
    for option, address in (
        ("--preload-addr", "0x050001"),
        ("--runtime-overlay-addr", "0x08000001"),
    ):
        result = run(root, manifest, paths, (option, address))
        require(result.returncode == 2, f"wrong Ship target {option} must fail", result)
        require("G5 Stage A" not in result.stdout,
                f"wrong Ship target {option} must fail before Stage A", result)


def check_island_binding_fail_closed(
    root: Path, manifest: Path, paths: dict[str, Path], data: dict[str, object]
) -> None:
    for name, mutate in (
        ("island-elf-sha", lambda value: value["runtime_overlays"]["elf"].__setitem__("sha256", "0" * 64)),
        ("island-slot-sha", lambda value: value["runtime_overlays"]["slices"][0].__setitem__("sha256", "0" * 64)),
        ("island-slot-id", lambda value: value["runtime_overlays"]["slices"][0].__setitem__("id", 38)),
    ):
        candidate = root / f"bad-{name}.json"
        mutated = json.loads(json.dumps(data))
        mutate(mutated)
        candidate.write_text(json.dumps(mutated, sort_keys=True) + "\n", encoding="ascii")
        result = run(root, candidate, paths)
        require(result.returncode != 0, f"{name} must fail closed", result)
        require("G5 Stage B" not in result.stdout,
                f"{name} must fail before reset/remount", result)

    wrong_elf = root / "wrong-island.elf"
    wrong_elf.write_bytes(b"wrong-manifest-bound-elf")
    supplied = dict(paths)
    supplied["workbench-elf"] = wrong_elf
    result = run(root, manifest, supplied)
    require(result.returncode != 0, "unbound resident island ELF must fail", result)
    require("G5 Stage B" not in result.stdout,
            "unbound resident island ELF must fail before reset/remount", result)


def check_d81_upload_required(
    root: Path, manifest: Path, paths: dict[str, Path]
) -> None:
    result = run(root, manifest, paths, ("--no-d81-upload",))
    require(result.returncode == 2, "Ship G5 must reject --no-d81-upload", result)
    require("G5 Stage A" not in result.stdout,
            "missing D81 upload must fail before Stage A", result)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lisp65-hw-ship-g5-") as raw_tmp:
        root = Path(raw_tmp)
        manifest, paths, data = fixture(root)
        check_workflow(root, manifest, paths)
        check_stack_readback_workflow(root, manifest, paths)
        check_manifest_fail_closed(root, manifest, paths, data)
        check_deploy_binding_fail_closed(root, manifest, paths)
        check_target_addresses_fail_closed(root, manifest, paths)
        check_island_binding_fail_closed(root, manifest, paths, data)
        check_d81_upload_required(root, manifest, paths)
    print("hw-ship-g5 harness selftest: PASS (11 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
