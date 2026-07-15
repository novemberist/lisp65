#!/usr/bin/env python3
"""Selftest for the isolated Runtime Export G4/G5 hardware harness."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
sys.path.insert(0, str(HOST_TOOLS))

import runtime_export_ship as SHIP  # noqa: E402


HARNESS = ROOT / "scripts" / "runtime-export-deploy.sh"
ORACLE_TOOL = HOST_TOOLS / "runtime_export_hw_oracle.py"


class SelftestError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(
    command: list[str | Path], *, env: dict[str, str] | None = None,
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in command], cwd=ROOT, env=env,
        text=True, capture_output=True,
    )
    if result.returncode != expected:
        raise SelftestError(
            "command returned %d, expected %d: %s\nstdout:\n%s\nstderr:\n%s"
            % (result.returncode, expected, " ".join(str(item) for item in command),
               result.stdout, result.stderr)
        )
    return result


def _expect_failure(
    command: list[str | Path], *, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in command], cwd=ROOT, env=env,
        text=True, capture_output=True,
    )
    if result.returncode == 0:
        raise SelftestError("command unexpectedly passed: %s" % " ".join(map(str, command)))
    return result


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="ascii")
    path.chmod(0o755)


def _package(path: Path, *, suite_sha: str) -> dict[str, Any]:
    fixture = json.loads(
        (ROOT / "tests/bytecode/formats/p0-disk-lib-v1.json").read_text(encoding="utf-8")
    )
    minimal = next(item for item in fixture["goldens"] if item["id"] == "minimal")
    image = bytes.fromhex(minimal["image_hex"])
    summary, blob, _entries = SHIP._parse_l65m(image)
    app = {
        "format": "lisp65-runtime-app-v1",
        "status": SHIP.STATUS,
        "name": "selftest",
        "suite": "tests/selftest.json",
        "entry": {"name": "id", "arity": 0},
        "exports": ["id"],
        "provides": ["selftest"],
        "requires": ["core"],
        "library_closure": [],
        "native_capabilities": ["vm"],
        "expected_result": "42",
    }
    path.mkdir()
    (path / "runtime-app.json").write_text(
        json.dumps(app, sort_keys=True) + "\n", encoding="utf-8"
    )
    (path / "runtime-app.l65m").write_bytes(image)
    (path / "toolchain-report.txt").write_text(
        "format=lisp65-runtime-export-toolchain-report-v1\n", encoding="ascii"
    )
    zero_sha = "0" * 64
    profile_fields = {
        "format": "lisp65-runtime-export-resolved-profile-v2",
        "profile": "runtime-export-v1-candidate",
        "status": SHIP.STATUS,
        "layout": "inline-boot-overlay",
        "entry_abi": "named-zero-argument-p0",
        "runtime_entry": "id",
        "runtime_prg_format": "mega65-prg",
        "runtime_prg_load_address": "0x2001",
        "application_preload": "bank5-build-bound",
        "runtime_preload_address": "0x050000",
        "runtime_disk_loader": "false",
        "application_descriptor_format": "lisp65-runtime-app-v1",
        "application_artifact_format": "lisp65-bytecode-p0-disk-lib-artifacts-v1",
        "application_bytecode_abi": "P0",
        "application_l65m_version": "1",
        "application_emitter": "workbench-lcc-fasl-v1",
        "min_boot_stack_gap": "512",
        "min_post_boot_reserve": "8192",
        "post_boot_reserve_target": "12288",
        "max_prg_file_end": "45056",
        "min_symbol_headroom": "64",
        "g2_elf_surface": "passed-by-inline-overlay-audit",
        "g2_budgets": "passed-by-inline-overlay-audit",
        "g2_inline_overlay_audit": "passed",
        "g2_package_verifier": "required-post-pack",
        "g2_reproducibility": "required-post-pack",
        "contract_sha256": zero_sha,
        "app_descriptor_sha256": _sha((path / "runtime-app.json").read_bytes()),
        "suite_sha256": suite_sha,
        "config_sha256": zero_sha,
        "make_sha256": zero_sha,
        "inline_linker_sha256": zero_sha,
        "workbench_golden_sha256": _sha(image),
        "workbench_emission_receipt_sha256": zero_sha,
        "workbench_reemission_receipt_sha256": zero_sha,
        "workbench_ship_manifest_sha256": zero_sha,
    }
    (path / "resolved-profile.txt").write_text(
        "".join("%s=%s\n" % item for item in profile_fields.items()), encoding="ascii"
    )
    profile, profile_data = SHIP._parse_profile(path / "resolved-profile.txt")
    build_id = int(_sha(profile_data)[:8], 16)
    preload = SHIP.PRELOAD.bind(SHIP.WORKBENCH.bank5_preload(image), build_id)
    (path / "runtime-preload.bin").write_bytes(preload)
    prg = b"\x01\x20runtime-hw-selftest" + SHIP.preload_binding_record(
        len(SHIP.PRELOAD.parse(preload)[0]), SHIP.crc16_ccitt_false(preload), build_id
    )
    (path / "runtime.prg").write_bytes(prg)
    paths = {name: path / name for name in SHIP.PACKAGE_FILES[1:]}
    manifest = SHIP._manifest(
        paths=paths,
        profile=profile,
        profile_data=profile_data,
        app=app,
        image=image,
        summary=summary,
        blob=blob,
        audit={
            "resident_overlay_control_refs": "1",
            "prg_file_end": hex(SHIP.PRG_LOAD_ADDRESS + len(prg) - 2),
            "boot_stack_gap": "1024",
            "post_boot_reserve": "13000",
        },
        footprint={"boot_sym_headroom": "80"},
        contract_sha256=zero_sha,
        hardware_symbols={
            "state": {
                "name": "lisp65_runtime_state", "address": 0x80,
                "size": 1, "encoding": "u8",
            },
            "result": {
                "name": "lisp65_runtime_result", "address": 0x82,
                "size": 2, "encoding": "obj16-le",
            },
            "preload_detail": {
                "name": "lisp65_runtime_preload_detail", "address": 0x84,
                "size": 1, "encoding": "u8",
            },
        },
        emission_receipt_sha256=zero_sha,
        reemission_receipt_sha256=zero_sha,
    )
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    SHIP.verify(path)
    return manifest


def _fake_tools(path: Path) -> tuple[Path, Path, Path]:
    path.mkdir()
    nm = path / "llvm-nm"
    objcopy = path / "llvm-objcopy"
    m65 = path / "m65"
    _write_executable(
        nm,
        """#!/usr/bin/env python3
print("00000080 00000001 b lisp65_runtime_state")
print("00000082 00000002 b lisp65_runtime_result")
print("00000084 00000001 b lisp65_runtime_preload_detail")
""",
    )
    _write_executable(
        objcopy,
        """#!/usr/bin/env python3
import shutil
import sys
shutil.copyfile(sys.argv[-2], sys.argv[-1])
""",
    )
    _write_executable(
        m65,
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log = Path(os.environ["FAKE_TOOL_LOG"])
with log.open("a", encoding="ascii") as handle:
    handle.write(json.dumps(args) + "\\n")
memory_path = Path(os.environ["FAKE_MEMORY"])
length = int(os.environ["FAKE_PRELOAD_LENGTH"])
preload_address = int(os.environ["FAKE_PRELOAD_ADDRESS"])
if memory_path.exists():
    memory = bytearray(memory_path.read_bytes())
else:
    memory = bytearray([0xCC]) * length

if "-@" in args:
    spec = args[args.index("-@") + 1]
    source, address_text = spec.rsplit("@", 1)
    address = int(address_text, 0)
    data = Path(source).read_bytes()
    offset = address - preload_address
    if offset < 0 or offset + len(data) > len(memory):
        raise SystemExit("fake stage outside Bank 5")
    memory[offset:offset + len(data)] = data
    memory_path.write_bytes(memory)

if "--memsave" in args:
    spec = args[args.index("--memsave") + 1]
    span, output_text = spec.split("=", 1)
    start_text, end_text = span.split(":", 1)
    start, end = int(start_text, 0), int(end_text, 0)
    size = end - start
    output = Path(output_text)
    if start == preload_address:
        data = bytes(memory[:size])
    elif start == int(os.environ["FAKE_STATE_ADDRESS"]):
        phase = os.environ["RUNTIME_EXPORT_PHASE"]
        default = 3 if phase == "clean" else 0xE4
        data = bytes([int(os.environ.get("FAKE_RUNTIME_STATE", default))])
    elif start == int(os.environ["FAKE_RESULT_ADDRESS"]):
        phase = os.environ["RUNTIME_EXPORT_PHASE"]
        default = 85 if phase == "clean" else 0
        raw = int(os.environ.get("FAKE_RUNTIME_RESULT", default))
        data = raw.to_bytes(2, "little")
    elif start == int(os.environ["FAKE_PRELOAD_DETAIL_ADDRESS"]):
        phase = os.environ["RUNTIME_EXPORT_PHASE"]
        defaults = {"clean": 0, "truncated": 1, "bitflip": 3, "build-id-mismatch": 2}
        detail = int(os.environ.get("FAKE_RUNTIME_DETAIL", defaults[phase]))
        data = bytes([detail])
    else:
        raise SystemExit("unknown fake memsave address: 0x%x" % start)
    if len(data) != size:
        raise SystemExit("fake memsave size mismatch")
    output.write_bytes(data)
""",
    )
    return nm, objcopy, m65


def _deploy_command(
    *, phase: str, package: Path, oracle: Path, out_dir: Path, tools: Path,
    cycle: str, mismatch: Path | None = None,
) -> list[str | Path]:
    command: list[str | Path] = [
        HARNESS,
        "--gate", "G5",
        "--phase", phase,
        "--package", package,
        "--oracle", oracle,
        "--out-dir", out_dir,
        "--tools", tools,
        "--power-cycle-token", "POWER-CYCLED",
        "--cycle-id", cycle,
        "--runtime-timeout", "1",
        "--poll-interval", "0",
    ]
    if mismatch is not None:
        command.extend(("--mismatch-package", mismatch))
    return command


def selftest() -> int:
    with tempfile.TemporaryDirectory(prefix="runtime-export-hw-selftest-") as raw:
        base = Path(raw)
        package = base / "package"
        mismatch = base / "mismatch"
        manifest = _package(package, suite_sha="0" * 64)
        create_mismatch = [
            sys.executable, ORACLE_TOOL, "create-mismatch-package",
            "--package", package, "--out", mismatch,
        ]
        _run(create_mismatch)
        mismatch_manifest = json.loads(
            (mismatch / "manifest.json").read_text(encoding="ascii")
        )
        SHIP.verify(mismatch)
        if manifest["profile"]["build_id"] == mismatch_manifest["profile"]["build_id"]:
            raise SelftestError("fixture packages unexpectedly share a build-id")
        canonical_preload = (package / "runtime-preload.bin").read_bytes()
        mismatch_preload = (mismatch / "runtime-preload.bin").read_bytes()
        canonical_payload, canonical_build_id = SHIP.PRELOAD.parse(canonical_preload)
        mismatch_payload, mismatch_build_id = SHIP.PRELOAD.parse(mismatch_preload)
        if canonical_payload != mismatch_payload:
            raise SelftestError("generated mismatch package changed the preload payload")
        if canonical_build_id == mismatch_build_id:
            raise SelftestError("generated mismatch package retained the canonical build-id")
        if canonical_preload[:-4] != mismatch_preload[:-4]:
            raise SelftestError("generated mismatch package changed bytes outside trailer build-id")
        for name in ("runtime-app.json", "runtime-app.l65m", "toolchain-report.txt"):
            if (package / name).read_bytes() != (mismatch / name).read_bytes():
                raise SelftestError("generated mismatch package changed immutable artifact " + name)
        canonical_prg = (package / "runtime.prg").read_bytes()
        mismatch_prg = (mismatch / "runtime.prg").read_bytes()
        expected_mismatch_prg = SHIP.rebind_prg(
            canonical_prg, len(mismatch_payload),
            SHIP.crc16_ccitt_false(mismatch_preload), mismatch_build_id,
        )
        if mismatch_prg != expected_mismatch_prg:
            raise SelftestError("generated mismatch PRG changed outside its L65P binding record")
        canonical_profile = (package / "resolved-profile.txt").read_text(encoding="ascii").splitlines()
        mismatch_profile = (mismatch / "resolved-profile.txt").read_text(encoding="ascii").splitlines()
        if len(canonical_profile) != len(mismatch_profile) or sum(
            left != right for left, right in zip(canonical_profile, mismatch_profile)
        ) != 1 or not next(
            left for left, right in zip(canonical_profile, mismatch_profile) if left != right
        ).startswith("profile="):
            raise SelftestError("generated mismatch profile changed more than its profile id")

        mutated_mismatch = base / "mutated-mismatch-payload"
        shutil.copytree(mismatch, mutated_mismatch)
        mutated_preload_path = mutated_mismatch / "runtime-preload.bin"
        mutated_preload = bytearray(mutated_preload_path.read_bytes())
        mutated_preload[0] ^= 1
        mutated_preload_path.write_bytes(mutated_preload)
        mutated_manifest_path = mutated_mismatch / "manifest.json"
        mutated_manifest = json.loads(mutated_manifest_path.read_text(encoding="ascii"))
        mutated_payload, _ = SHIP.PRELOAD.parse(bytes(mutated_preload))
        preload_record = mutated_manifest["runtime"]["preload"]
        preload_record["crc16"] = SHIP.crc16_ccitt_false(bytes(mutated_preload))
        preload_record["sha256"] = _sha(bytes(mutated_preload))
        preload_record["payload_crc16"] = SHIP.crc16_ccitt_false(mutated_payload)
        preload_record["payload_sha256"] = _sha(mutated_payload)
        artifact_record = next(
            item for item in mutated_manifest["artifacts"]
            if item["path"] == "runtime-preload.bin"
        )
        artifact_record["sha256"] = _sha(bytes(mutated_preload))
        mutated_manifest_path.write_text(
            json.dumps(mutated_manifest, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        try:
            SHIP.verify(mutated_mismatch)
        except SHIP.ShipError:
            pass
        else:
            raise SelftestError("manifest-consistent mismatch payload mutation passed verification")

        mismatch_repeat = base / "mismatch-repeat"
        _run([
            sys.executable, ORACLE_TOOL, "create-mismatch-package",
            "--package", package, "--out", mismatch_repeat,
        ])
        for name in SHIP.PACKAGE_FILES:
            if (mismatch / name).read_bytes() != (mismatch_repeat / name).read_bytes():
                raise SelftestError("mismatch package is not reproducible: " + name)

        _expect_failure(create_mismatch)
        corrupt_source = base / "corrupt-source"
        shutil.copytree(package, corrupt_source)
        (corrupt_source / "runtime-preload.bin").write_bytes(canonical_preload + b"x")
        refused_corrupt = base / "refused-corrupt"
        _expect_failure([
            sys.executable, ORACLE_TOOL, "create-mismatch-package",
            "--package", corrupt_source, "--out", refused_corrupt,
        ])
        if refused_corrupt.exists():
            raise SelftestError("invalid canonical package left a mismatch output")
        refused_same_id = base / "refused-same-id"
        _expect_failure([
            sys.executable, ORACLE_TOOL, "create-mismatch-package",
            "--package", package, "--out", refused_same_id,
            "--profile-id", manifest["profile"]["id"],
        ])
        if refused_same_id.exists():
            raise SelftestError("unchanged profile id left a mismatch output")

        fake_tools = base / "fake-tools"
        nm, objcopy, _m65 = _fake_tools(fake_tools)
        elf = base / "runtime.elf"
        elf.write_bytes((package / "runtime.prg").read_bytes()[2:])
        oracle = base / "oracle.json"
        _run([
            sys.executable, ORACLE_TOOL, "create",
            "--package", package, "--elf", elf,
            "--nm", nm, "--objcopy", objcopy, "--out", oracle,
        ])
        _run([sys.executable, ORACLE_TOOL, "verify", "--package", package, "--oracle", oracle])
        oracle_data = json.loads(oracle.read_text(encoding="ascii"))

        log = base / "m65.log"
        memory = base / "bank5.bin"
        env = os.environ.copy()
        env.update({
            "FAKE_TOOL_LOG": str(log),
            "FAKE_MEMORY": str(memory),
            "FAKE_PRELOAD_LENGTH": str(manifest["runtime"]["preload"]["length"]),
            "FAKE_PRELOAD_ADDRESS": str(oracle_data["runtime"]["preload_address"]),
            "FAKE_STATE_ADDRESS": str(
                oracle_data["hardware_oracle"]["symbols"]["state"]["address"]
            ),
            "FAKE_RESULT_ADDRESS": str(
                oracle_data["hardware_oracle"]["symbols"]["result"]["address"]
            ),
            "FAKE_PRELOAD_DETAIL_ADDRESS": str(
                oracle_data["hardware_oracle"]["symbols"]["preload_detail"]["address"]
            ),
        })

        dry_out = base / "g4-must-not-exist"
        g4 = _run([
            HARNESS, "--gate", "G4", "--phase", "clean",
            "--package", package, "--oracle", oracle,
            "--out-dir", dry_out, "--tools", base / "missing-tools",
        ], env=env)
        plan_start = g4.stdout.index("{")
        plan = json.loads(g4.stdout[plan_start:])
        if plan["offline"] is not True or plan["side_effects"] is not False:
            raise SelftestError("G4 plan does not declare strict offline/no-side-effect mode")
        if dry_out.exists() or log.exists():
            raise SelftestError("G4 dry-run touched output or hardware tools")
        plan_path = base / "g4-clean.txt"
        plan_path.write_text(g4.stdout, encoding="ascii")
        _run([
            sys.executable, ORACLE_TOOL, "verify-plan",
            "--plan", plan_path, "--phase", "clean",
        ])
        bad_plan = base / "g4-optimized-assert-backstop.json"
        plan["offline"] = False
        bad_plan.write_text(json.dumps(plan, sort_keys=True) + "\n", encoding="ascii")
        _expect_failure([
            sys.executable, ORACLE_TOOL, "verify-plan", "--plan", bad_plan,
        ])
        plan_paths = [plan_path]
        for phase in ("truncated", "bitflip", "build-id-mismatch"):
            command: list[str | Path] = [
                HARNESS, "--gate", "G4", "--phase", phase,
                "--package", package, "--oracle", oracle,
                "--out-dir", dry_out, "--tools", base / "missing-tools",
            ]
            if phase == "build-id-mismatch":
                command.extend(("--mismatch-package", mismatch))
            output = _run(command, env=env).stdout
            phase_path = base / ("g4-%s.txt" % phase)
            phase_path.write_text(output, encoding="ascii")
            plan_paths.append(phase_path)
        plan_suite_command: list[str | Path] = [
            sys.executable, ORACLE_TOOL, "verify-plan-suite",
        ]
        for path in plan_paths:
            plan_suite_command.extend(("--plan", path))
        _run(plan_suite_command)
        mixed_path = base / "g4-bitflip-mixed-identity.json"
        mixed = json.loads("{" + plan_paths[2].read_text(encoding="ascii").split("{", 1)[1])
        mixed["oracle_sha256"] = "0" * 64
        mixed_path.write_text(json.dumps(mixed, sort_keys=True) + "\n", encoding="ascii")
        mixed_command = list(plan_suite_command)
        mixed_at = mixed_command.index(plan_paths[2])
        mixed_command[mixed_at] = mixed_path
        _expect_failure(mixed_command)

        bad_package = base / "bad-package"
        shutil.copytree(package, bad_package)
        preload = bad_package / "runtime-preload.bin"
        preload.write_bytes(preload.read_bytes() + b"corrupt")
        bad_out = base / "preverify-must-not-exist"
        _expect_failure(_deploy_command(
            phase="clean", package=bad_package, oracle=oracle, out_dir=bad_out,
            tools=fake_tools, cycle="preverify-01",
        ), env=env)
        if bad_out.exists() or log.exists():
            raise SelftestError("invalid package reached G5 side effects")

        no_ack = _deploy_command(
            phase="clean", package=package, oracle=oracle,
            out_dir=base / "no-ack-must-not-exist", tools=fake_tools,
            cycle="noack-001",
        )
        token_at = no_ack.index("--power-cycle-token") + 1
        no_ack[token_at] = "NOT-CYCLED"
        _expect_failure(no_ack, env=env)
        if (base / "no-ack-must-not-exist").exists() or log.exists():
            raise SelftestError("missing power-cycle acknowledgement reached G5 side effects")

        bad_cycle = _deploy_command(
            phase="clean", package=package, oracle=oracle,
            out_dir=base / "bad-cycle-must-not-exist", tools=fake_tools,
            cycle="invalid cycle",
        )
        _expect_failure(bad_cycle, env=env)
        if (base / "bad-cycle-must-not-exist").exists() or log.exists():
            raise SelftestError("invalid cycle id reached G5 side effects")

        memory.write_bytes((package / manifest["runtime"]["preload"]["path"]).read_bytes())
        equal_out = base / "prestage-equals-target"
        _expect_failure(_deploy_command(
            phase="clean", package=package, oracle=oracle, out_dir=equal_out,
            tools=fake_tools, cycle="equal-target-01",
        ), env=env)
        equal_receipt = json.loads(
            (equal_out / "receipt-clean.json").read_text(encoding="ascii")
        )
        if equal_receipt["status"] != "FAIL" or "fresh staging is unproven" not in equal_receipt["error"]:
            raise SelftestError("target-equal pre-stage digest was not rejected")

        phase_dirs: dict[str, Path] = {}
        expected_details = {"clean": 0, "truncated": 1, "bitflip": 3, "build-id-mismatch": 2}
        for index, phase in enumerate(("clean", "truncated", "bitflip", "build-id-mismatch"), 1):
            memory.unlink(missing_ok=True)
            out_dir = base / ("pass-" + phase)
            phase_dirs[phase] = out_dir
            foreign = mismatch if phase == "build-id-mismatch" else None
            _run(_deploy_command(
                phase=phase, package=package, oracle=oracle, out_dir=out_dir,
                tools=fake_tools, cycle="pass-cycle-%02d" % index,
                mismatch=foreign,
            ), env=env)
            receipt = out_dir / ("receipt-%s.json" % phase)
            verify = [
                sys.executable, ORACLE_TOOL, "verify-receipt",
                "--package", package, "--oracle", oracle, "--receipt", receipt,
            ]
            if foreign is not None:
                verify.extend(("--mismatch-package", foreign))
            _run(verify)
            record = json.loads(receipt.read_text(encoding="ascii"))
            if (record["status"] != "PASS" or not record["operator"]["prestage_digest"] or
                    record["observed"]["preload_detail"] != expected_details[phase] or
                    record["operator"]["prestage_digest"] == manifest["runtime"]["preload"]["sha256"]):
                raise SelftestError("G5 PASS receipt lacks its pre-stage evidence")

        suite_receipts = [
            phase_dirs[phase] / ("receipt-%s.json" % phase)
            for phase in ("clean", "truncated", "bitflip", "build-id-mismatch")
        ]
        suite_command: list[str | Path] = [
            sys.executable, ORACLE_TOOL, "verify-suite",
            "--package", package, "--oracle", oracle,
            "--mismatch-package", mismatch,
        ]
        for receipt in suite_receipts:
            suite_command.extend(("--receipt", receipt))
        _run(suite_command)

        _expect_failure(suite_command[:-2])
        duplicate_dir = base / "duplicate-clean-phase"
        shutil.copytree(phase_dirs["clean"], duplicate_dir)
        duplicate_phase = [
            suite_receipts[0],
            duplicate_dir / "receipt-clean.json",
            suite_receipts[1],
            suite_receipts[2],
        ]
        duplicate_command: list[str | Path] = [
            sys.executable, ORACLE_TOOL, "verify-suite",
            "--package", package, "--oracle", oracle,
            "--mismatch-package", mismatch,
        ]
        for receipt in duplicate_phase:
            duplicate_command.extend(("--receipt", receipt))
        _expect_failure(duplicate_command)

        reused_cycle_dir = base / "reused-cycle-bitflip"
        shutil.copytree(phase_dirs["bitflip"], reused_cycle_dir)
        reused_receipt = reused_cycle_dir / "receipt-bitflip.json"
        reused_record = json.loads(reused_receipt.read_text(encoding="ascii"))
        clean_record = json.loads(suite_receipts[0].read_text(encoding="ascii"))
        reused_record["operator"]["cycle_id"] = clean_record["operator"]["cycle_id"]
        reused_receipt.write_text(
            json.dumps(reused_record, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        reused_command: list[str | Path] = [
            sys.executable, ORACLE_TOOL, "verify-suite",
            "--package", package, "--oracle", oracle,
            "--mismatch-package", mismatch,
        ]
        for receipt in (suite_receipts[0], suite_receipts[1], reused_receipt, suite_receipts[3]):
            reused_command.extend(("--receipt", receipt))
        _expect_failure(reused_command)

        invalid_cycle_dir = base / "invalid-cycle-clean"
        shutil.copytree(phase_dirs["clean"], invalid_cycle_dir)
        invalid_cycle_receipt = invalid_cycle_dir / "receipt-clean.json"
        invalid_cycle_record = json.loads(invalid_cycle_receipt.read_text(encoding="ascii"))
        invalid_cycle_record["operator"]["cycle_id"] = "invalid cycle"
        invalid_cycle_receipt.write_text(
            json.dumps(invalid_cycle_record, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        _expect_failure([
            sys.executable, ORACLE_TOOL, "verify-receipt",
            "--package", package, "--oracle", oracle,
            "--receipt", invalid_cycle_receipt,
        ])

        invalid_verdicts = (
            ("wrong-state", "truncated", {"FAKE_RUNTIME_STATE": "3"}),
            ("wrong-result", "bitflip", {"FAKE_RUNTIME_RESULT": "85"}),
            ("wrong-detail", "build-id-mismatch", {"FAKE_RUNTIME_DETAIL": "3"}),
        )
        for index, (case, phase, overrides) in enumerate(invalid_verdicts, 1):
            memory.unlink(missing_ok=True)
            out_dir = base / ("fail-" + case)
            invalid_env = env.copy()
            invalid_env.update(overrides)
            _expect_failure(_deploy_command(
                phase=phase, package=package, oracle=oracle, out_dir=out_dir,
                tools=fake_tools, cycle="fail-cycle-%02d" % index,
                mismatch=mismatch if phase == "build-id-mismatch" else None,
            ), env=invalid_env)
            receipt = json.loads(
                (out_dir / ("receipt-%s.json" % phase)).read_text(encoding="ascii")
            )
            if receipt["status"] != "FAIL" or not receipt["error"]:
                raise SelftestError("corruption phase did not leave a fail-closed receipt")

        semantic_mutations = (
            ("state", "truncated", "runtime-state", b"\x03", {"state": 3}),
            (
                "result", "bitflip", "runtime-result", (85).to_bytes(2, "little"),
                {"result_raw": 85, "result_fixnum": 42},
            ),
            (
                "detail", "build-id-mismatch", "runtime-preload-detail", b"\x03",
                {"preload_detail": 3},
            ),
        )
        for case, phase, role, raw_value, observed_updates in semantic_mutations:
            tampered = base / ("wrong-" + case)
            shutil.copytree(phase_dirs[phase], tampered)
            receipt_path = tampered / ("receipt-%s.json" % phase)
            record = json.loads(receipt_path.read_text(encoding="ascii"))
            evidence_record = next(item for item in record["evidence"] if item["role"] == role)
            (tampered / evidence_record["file"]).write_bytes(raw_value)
            evidence_record["size"] = len(raw_value)
            evidence_record["sha256"] = _sha(raw_value)
            record["observed"].update(observed_updates)
            receipt_path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="ascii"
            )
            verify = [
                sys.executable, ORACLE_TOOL, "verify-receipt",
                "--package", package, "--oracle", oracle, "--receipt", receipt_path,
            ]
            if phase == "build-id-mismatch":
                verify.extend(("--mismatch-package", mismatch))
            _expect_failure(verify)

        wrong_status = base / "wrong-status"
        shutil.copytree(phase_dirs["clean"], wrong_status)
        wrong_receipt = wrong_status / "receipt-clean.json"
        record = json.loads(wrong_receipt.read_text(encoding="ascii"))
        record["status"] = "FAIL"
        wrong_receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="ascii")
        _expect_failure([
            sys.executable, ORACLE_TOOL, "verify-receipt",
            "--package", package, "--oracle", oracle, "--receipt", wrong_receipt,
        ])

        wrong_evidence = base / "wrong-evidence"
        shutil.copytree(phase_dirs["bitflip"], wrong_evidence)
        wrong_receipt = wrong_evidence / "receipt-bitflip.json"
        record = json.loads(wrong_receipt.read_text(encoding="ascii"))
        record["evidence"][0]["sha256"] = "f" * 64
        wrong_receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="ascii")
        _expect_failure([
            sys.executable, ORACLE_TOOL, "verify-receipt",
            "--package", package, "--oracle", oracle, "--receipt", wrong_receipt,
        ])

        tool_log = log.read_text(encoding="ascii").lower()
        if "d81" in tool_log or "attic" in tool_log:
            raise SelftestError("G5 attempted a D81/Attic operation")

    print(
        "runtime-export-hw-harness selftest: PASS "
        "g4=offline g5=4-phases suite=verified mismatch=reproducible "
        "corruptions=3 receipts=fail-closed"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(selftest())
    except (SelftestError, OSError, ValueError, KeyError, TypeError) as exc:
        print("runtime-export-hw-harness selftest: FAIL: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
