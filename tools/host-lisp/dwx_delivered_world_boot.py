#!/usr/bin/env python3
"""Boot a shipped lisp65 product D81 in the DWX Xemu prefilter."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/dwx-xemu-link73-contract.json"
BLIND_CONTRACT_PATH = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
RECEIPT_PATH = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-link73-xemu-boot-receipt-20260902.json"
SAFE_RUNNER = ROOT / "scripts/xmega65-safe-run.sh"


class BootError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BootError(f"expected object in {path}")
    return value


def require_sha(path: Path, expected: str, role: str) -> str:
    observed = sha256(path)
    if observed != expected:
        raise BootError(f"{role} SHA mismatch: expected {expected}, got {observed}")
    return observed


def framebuffer_result(text: str, oracle: dict[str, object]) -> dict[str, object]:
    # Xemu's dumpscreen marks reverse-video glyphs as {W}{O}... rather than
    # plain text.  Decode single glyph tokens, but leave named PETSCII tokens
    # such as {dash} alone so they cannot manufacture an oracle word.
    decoded = re.sub(r"\{([A-Za-z0-9])\}", r"\1", text)
    folded = decoded.upper()
    required = [str(value).upper() for value in oracle["required"]]
    forbidden = [str(value).upper() for value in oracle["forbidden"]]
    missing = [value for value in required if value not in folded]
    present_forbidden = [value for value in forbidden if value in folded]
    return {
        "passed": not missing and not present_forbidden,
        "required": required,
        "missing": missing,
        "forbidden": forbidden,
        "present_forbidden": present_forbidden,
    }


def verify_adapter(manifest_path: Path, xemu: Path, cfg: dict[str, object]) -> dict[str, object]:
    manifest = load_json(manifest_path)
    if manifest.get("status") != "PASS":
        raise BootError("adapter manifest is not green")
    if manifest.get("format") == "lisp65-dwx-xemu-f011-adapter-build-v1":
        source = manifest.get("source")
        if not isinstance(source, dict) or source.get("commit") != cfg["xemu_source"]["commit"]:
            raise BootError("adapter was not built from the contract Xemu revision")
    elif manifest.get("format") == "lisp65-dwx-xemu-cycle-probe-build-v1":
        if manifest.get("source_commit") != cfg["xemu_source"]["commit"]:
            raise BootError("cycle-probe fork was not built from the contract Xemu revision")
    else:
        raise BootError("unexpected adapter manifest format")
    binary = manifest.get("binary")
    if not isinstance(binary, dict):
        raise BootError("adapter manifest has no binary binding")
    observed = sha256(xemu)
    if binary.get("sha256") != observed:
        raise BootError("executed Xemu does not match the adapter manifest")
    return manifest


def run_boot(args: argparse.Namespace) -> dict[str, object]:
    cfg = load_json(CONTRACT_PATH)
    blind_contract = load_json(BLIND_CONTRACT_PATH)
    if cfg.get("format") != "lisp65-dwx-xemu-link73-contract-v1":
        raise BootError("unexpected DWX Xemu contract format")
    delivered = cfg["delivered_world"]
    assert isinstance(delivered, dict)
    args.out.mkdir(parents=True, exist_ok=False)
    adapter_manifest = verify_adapter(args.adapter_manifest, args.xemu, cfg)
    binary = adapter_manifest["binary"]
    if adapter_manifest["format"] == "lisp65-dwx-xemu-cycle-probe-build-v1":
        prefilter_tool_identity = {
            "source_commit": adapter_manifest["source_commit"],
            "patches": adapter_manifest["patches"],
            "patched_source_sha256": adapter_manifest["patched_source_sha256"],
            "binary_sha256": binary["sha256"],
        }
    else:
        source = adapter_manifest["source"]
        patch = adapter_manifest["patch"]
        prefilter_tool_identity = {
            "source_commit": source["commit"],
            "source_file_sha256": {
                "targets/mega65/sdcard.c": source["sdcard_c_before_sha256"],
                "targets/mega65/io_mapper.c": cfg["xemu_source"]["io_mapper_c_sha256"],
            },
            "patch_sha256": patch["sha256"],
            "patched_source_sha256": source["sdcard_c_after_sha256"],
            "binary_sha256": binary["sha256"],
        }
    if prefilter_tool_identity != blind_contract.get("qualified_tool_identity"):
        raise BootError("executed Xemu is not the qualified DWX fork identity")
    device_mandatory_rows = [
        row["id"]
        for row in blind_contract.get("contract_rows", [])
        if row.get("kind") == "blind-spot" and row.get("device_mandatory") is True
    ]
    if blind_contract.get("evidence_class") != "xemu-prefilter-green" or len(device_mandatory_rows) != 5:
        raise BootError("DWX blind-spot contract is incomplete")
    bindings = {
        "product_d81": require_sha(args.d81, delivered["product_d81_sha256"], "product D81"),
        "rom": require_sha(args.rom, delivered["rom_sha256"], "ROM"),
        "system_sd": require_sha(args.sd_image, delivered["system_sd_sha256"], "system SD"),
    }

    sd_copy = args.out / "system-sd.img"
    subprocess.run(
        ["cp", "--reflink=auto", "--sparse=always", str(args.sd_image), str(sd_copy)],
        check=True,
    )
    d81_copy = args.out / "lisp65-product.d81"
    shutil.copyfile(args.d81, d81_copy)
    d81_copy.chmod(0o444)
    screen = args.out / "framebuffer.txt"
    screenshot = args.out / "framebuffer.png"
    memory = args.out / "memory.bin"
    log = args.out / "xemu.log"
    command = [
        str(SAFE_RUNNER), str(memory), str(args.timeout), str(args.xemu),
        "-skipconfigfile", "-headless", "-testing", "-sleepless", "-besure", "-fastboot",
        "-rom", str(args.rom), "-sdimg", str(sd_copy), "-8", str(d81_copy), "-autoload",
        "-dumpscreen", str(screen), "-screenshot", str(screenshot), "-dumpmem", str(memory),
    ]
    with log.open("wb") as handle:
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if completed.returncode not in (0, 124):
        raise BootError(f"safe Xemu run failed with status {completed.returncode}")
    for artifact in (screen, screenshot, memory):
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise BootError(f"Xemu did not emit {artifact}")

    oracle = framebuffer_result(screen.read_text(encoding="utf-8"), cfg["framebuffer_oracle"])
    bindings_after = {
        "product_d81": sha256(d81_copy),
        "rom": sha256(args.rom),
        "system_sd_source": sha256(args.sd_image),
        "system_sd_copy": sha256(sd_copy),
    }
    if bindings_after != {
        "product_d81": bindings["product_d81"],
        "rom": bindings["rom"],
        "system_sd_source": bindings["system_sd"],
        "system_sd_copy": bindings["system_sd"],
    }:
        raise BootError("a bound input changed during the emulator run")
    if not oracle["passed"]:
        raise BootError(
            f"framebuffer oracle failed: missing={oracle['missing']} forbidden={oracle['present_forbidden']}"
        )

    receipt = {
        "format": "lisp65-dwx-delivered-world-boot-v1",
        "status": "PASS",
        "evidence_class": blind_contract["evidence_class"],
        "prefilter_tool_identity": prefilter_tool_identity,
        "inputs": {
            "product_d81": {"path": str(args.d81.resolve()), "sha256": bindings["product_d81"]},
            "rom": {"path": str(args.rom.resolve()), "sha256": bindings["rom"]},
            "system_sd": {"path": str(args.sd_image.resolve()), "sha256": bindings["system_sd"]},
            "xemu": {"path": str(args.xemu.resolve()), "sha256": sha256(args.xemu)},
            "adapter_manifest": {
                "path": str(args.adapter_manifest.resolve()),
                "sha256": sha256(args.adapter_manifest),
            },
        },
        "execution": {"timeout_seconds": args.timeout, "status": completed.returncode},
        "framebuffer_oracle": oracle,
        "outputs": {
            "framebuffer": {"path": str(screen), "sha256": sha256(screen)},
            "screenshot": {"path": str(screenshot), "sha256": sha256(screenshot)},
            "memory": {"path": str(memory), "sha256": sha256(memory)},
        },
        "device_mandatory_rows": device_mandatory_rows,
        "claim_limit": "Xemu functional prefilter only; not physical-device acceptance and not evidence for freezer, DMA timing, core identity, or typing feel.",
    }
    (args.out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def selftest() -> None:
    oracle = {"required": ["WORKBENCH 2.0.0", "LISP65>"], "forbidden": ["DISK ERROR"]}
    good = "WORKBENCH 2.0.0\n\nLISP65> "
    if not framebuffer_result(good, oracle)["passed"]:
        raise BootError("green framebuffer rejected")
    reverse_video = "{W}{O}{R}{K}{B}{E}{N}{C}{H} 2.0.0\nLISP65>"
    if not framebuffer_result(reverse_video, oracle)["passed"]:
        raise BootError("reverse-video framebuffer rejected")
    mutations = {
        "prompt-only-in-log": "WORKBENCH 2.0.0\n",
        "historical-media-error": "WORKBENCH 2.0.0\nDISK ERROR\nLISP65>",
        "banner-from-wrong-world": "WORKBENCH 1.9.0\nLISP65>",
    }
    for name, text in mutations.items():
        if framebuffer_result(text, oracle)["passed"]:
            raise BootError(f"framebuffer mutation survived: {name}")
    print(f"dwx-delivered-world-boot selftest PASS mutations={len(mutations)}")


def check() -> None:
    cfg = load_json(CONTRACT_PATH)
    receipt = load_json(RECEIPT_PATH)
    delivered = cfg["delivered_world"]
    oracle = cfg["framebuffer_oracle"]
    successor = receipt.get("successor", {})
    if (
        receipt.get("status") != "PASS"
        or receipt.get("product_bytes_changed") != 0
        or receipt.get("delivered_inputs") != delivered
        or successor.get("runs") != 2
        or successor.get("independent_release_pack_roots") != 2
        or successor.get("framebuffer_byte_identical") is not True
        or successor.get("screenshot_byte_identical") is not True
        or successor.get("required_visible") != oracle["required"]
        or successor.get("forbidden_visible") != oracle["forbidden"]
        or cfg["framebuffer_oracle"].get("logs_are_authority") is not False
        or receipt.get("mutations", {}).get("framebuffer_oracle")
        != ["prompt-only-in-log", "historical-media-error", "banner-from-wrong-world"]
        or receipt.get("mutations", {}).get("survived") != []
    ):
        raise BootError("delivered-world boot receipt drift")
    print("dwx-delivered-world-boot check PASS receipt-bound")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--xemu", type=Path)
    parser.add_argument("--adapter-manifest", type=Path)
    parser.add_argument("--d81", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--sd-image", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
    if args.check:
        check()
        return 0
    missing = [name for name in ("xemu", "adapter_manifest", "d81", "rom", "sd_image", "out") if getattr(args, name) is None]
    if missing:
        parser.error("required arguments missing: " + ", ".join(missing))
    receipt = run_boot(args)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (BootError, OSError, subprocess.CalledProcessError) as error:
        print(f"dwx-delivered-world-boot: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
