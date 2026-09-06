#!/usr/bin/env python3
"""Build and execute honest freezer-free DWX boot variants."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_init_l65_product_variants_media as INIT  # noqa: E402
import dwx_delivered_world_boot as BOOT  # noqa: E402
import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402


CONTRACT_PATH = ROOT / "config/dwx-freezer-free-boot-variants-contract.json"
BLIND_CONTRACT_PATH = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
SEALED_ITEM3_BLIND_BINDING = {
    "path": "config/dwx-prefilter-blind-spot-contract.json",
    "bytes": 3535,
    "sha256": "01b86f775ff799c2e09d6a4918794ae5205a5efc451bea05170377552ba30fd9",
}
SEALED_ITEM3_DEVICE_ROWS = list(BLIND.BLIND_IDS[:4])
RECEIPT_PATH = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-freezer-free-boot-variants-receipt-20260902.json"
REPORT_PATH = ROOT / "docs/planning/dwx-freezer-free-boot-variants-report.md"
WORK_PLAN_PATH = ROOT / "docs/planning/dwx-delivered-world-executor-work-plan.md"
SAFE_RUNNER = ROOT / "scripts/xmega65-safe-run.sh"
VARIANT_IDS = (
    "published-v2.0.0-drive-8-only",
    "product-medium-init-absent",
    "product-medium-init-valid",
    "product-medium-init-error",
)
PRODUCT_IDS = VARIANT_IDS[1:]
GAP = "The device library-medium Freezer mount is not exercised by any Xemu variant."
EXPECTED_MEDIA_SHA256 = {
    "product-medium-init-absent": "7bd0cd478da52b0d731a1fd837bce16d76832b4d1ae0e836ad63209433d68f2d",
    "product-medium-init-valid": "0cd8583bf60cabdf1a2da4bba0f6aa45cfa6933790c7066f56114b033649823e",
    "product-medium-init-error": "fee93d69a6d7c54b3fb8e1ce0c283bc1d8aa00c242f8bed4a3e65d4a6b3fcc1a",
}
EXPECTED_FRAMEBUFFER_SHA256 = {
    "product-medium-init-absent": "000c4a3a9de447297c76360a6ce0ed3810d8d708158bf36396091ac925d2be8c",
    "product-medium-init-valid": "f5b1d709b312bafb0f89c71f809d9cfb2c4980fec98a8b6c2a23f0796f3ad010",
    "product-medium-init-error": "62ab5442f1131c53ba0d988d67834035fd01e35983014af93ad1b49239dcd05c",
}


class VariantError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VariantError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VariantError(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_contract(value: dict[str, Any]) -> None:
    require(
        value.get("format") == "lisp65-dwx-freezer-free-boot-variants-contract-v1"
        and value.get("status") == "ACTIVE"
        and value.get("evidence_class") == "xemu-prefilter-green",
        "freezer-free variant contract header drift",
    )
    require(
        value.get("authority_rule")
        == "Freezer-free Xemu variants expose the choreography gap; they never claim Freezer behavior.",
        "freezer-free authority rule drift",
    )
    policy = value.get("variant_policy")
    require(isinstance(policy, dict), "variant policy absent")
    require(
        policy == {
            "manual_boot_media_swap": False,
            "fresh_emulator_process_per_product_variant": True,
            "freezer_operations": 0,
            "claims_freezer_behavior": False,
            "device_choreography_gap": GAP,
        },
        "freezer-free choreography policy drift",
    )
    variants = value.get("variants")
    require(
        isinstance(variants, list)
        and tuple(row.get("id") for row in variants) == VARIANT_IDS,
        "freezer-free variant population drift",
    )
    require(
        variants[0] == {
            "id": VARIANT_IDS[0],
            "family": "drive-8-only",
            "source": "bound-item1-runtime-receipt",
            "init_l65": "absent",
        },
        "drive-8-only predecessor row drift",
    )
    for row, mode in zip(variants[1:], ("absent", "valid", "error")):
        require(
            row == {
                "id": f"product-medium-init-{mode}",
                "family": "complete-product-medium-per-cold-boot",
                "source": "published-v2.0.0-product-copy",
                "init_l65": mode,
            },
            f"{mode} product-medium row drift",
        )
    inputs = value.get("inputs")
    require(isinstance(inputs, dict), "variant inputs absent")
    product = inputs.get("published_product_d81")
    item1 = inputs.get("item1_receipt")
    require(
        isinstance(product, dict)
        and product.get("sha256") == "7bd0cd478da52b0d731a1fd837bce16d76832b4d1ae0e836ad63209433d68f2d"
        and isinstance(item1, dict)
        and item1.get("sha256") == "cc1339ab3f04c709936244b4a878332e973be1c2ba0a89c6bc1531556b10a334",
        "variant input authority drift",
    )
    payloads = value.get("init_payloads")
    require(
        isinstance(payloads, dict)
        and payloads.get("valid", {}).get("sha256")
        == "f5817bf7ba721960fcf246c129cdb0df47b4f61ae7572321e37157f7631cd764"
        and payloads.get("error", {}).get("sha256")
        == "073038300abc088f99613adbcbd343d2867cbb6f258bcea2eacdf8c1dfbf2000",
        "INIT payload authority drift",
    )
    oracles = value.get("framebuffer_oracles")
    require(
        isinstance(oracles, dict)
        and set(oracles) == {"absent", "valid", "error"}
        and all(row.get("required") and row.get("forbidden") for row in oracles.values()),
        "framebuffer oracle population drift",
    )


def contract_mutations(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    value = deepcopy(contract)
    value["variant_policy"]["manual_boot_media_swap"] = True
    result["manual-media-swap-introduced"] = value
    value = deepcopy(contract)
    value["variant_policy"]["fresh_emulator_process_per_product_variant"] = False
    result["one-process-reused-across-cold-boots"] = value
    value = deepcopy(contract)
    value["variant_policy"]["freezer_operations"] = 1
    result["freezer-operation-claimed"] = value
    value = deepcopy(contract)
    value["variant_policy"]["claims_freezer_behavior"] = True
    result["freezer-behavior-claimed"] = value
    value = deepcopy(contract)
    value["variant_policy"]["device_choreography_gap"] = ""
    result["device-choreography-gap-hidden"] = value
    value = deepcopy(contract)
    value["variants"].pop()
    result["product-variant-omitted"] = value
    value = deepcopy(contract)
    value["variants"][0]["family"] = "freezer-equivalent"
    result["drive8-renamed-freezer-equivalent"] = value
    value = deepcopy(contract)
    value["variants"][2]["source"] = "external-library-medium"
    result["product-medium-replaced-by-library-swap"] = value
    value = deepcopy(contract)
    value["variants"][3]["init_l65"] = "absent"
    result["error-variant-lost"] = value
    value = deepcopy(contract)
    value["evidence_class"] = "device-accepted"
    result["prefilter-promoted-to-device-acceptance"] = value
    return result


def mutation_names(contract: dict[str, Any]) -> list[str]:
    names = []
    for name, value in contract_mutations(contract).items():
        try:
            validate_contract(value)
        except VariantError:
            names.append(name)
            continue
        raise VariantError(f"choreography mutation survived: {name}")
    return sorted(names)


def verify_bound_inputs(contract: dict[str, Any], rom: Path, sd_image: Path) -> tuple[Path, Path, Path]:
    inputs = contract["inputs"]
    product = ROOT / inputs["published_product_d81"]["path"]
    item1 = ROOT / inputs["item1_receipt"]["path"]
    require(sha256(product) == inputs["published_product_d81"]["sha256"], "published D81 SHA drift")
    require(sha256(item1) == inputs["item1_receipt"]["sha256"], "Item-1 receipt SHA drift")
    require(sha256(rom) == inputs["rom_sha256"], "ROM SHA drift")
    require(sha256(sd_image) == inputs["system_sd_sha256"], "system SD SHA drift")
    for role in ("valid", "error"):
        row = contract["init_payloads"][role]
        require(sha256(ROOT / row["path"]) == row["sha256"], f"{role} INIT SHA drift")
    return product, item1, ROOT / contract["init_payloads"]["valid"]["path"]


def append_init(source: Path, image: Path) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    result = subprocess.run(
        [c1541, str(image), "-write", str(source), "init.l65"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, "c1541 INIT append failed")


def create_media(contract: dict[str, Any], output: Path) -> dict[str, Path]:
    product = ROOT / contract["inputs"]["published_product_d81"]["path"]
    result = {}
    for mode in ("absent", "valid", "error"):
        target = output / f"lisp65-v2.0.0-init-{mode}.d81"
        shutil.copyfile(product, target)
        if mode != "absent":
            append_init(ROOT / contract["init_payloads"][mode]["path"], target)
        result[mode] = target
    return result


def run_variant(
    mode: str,
    image: Path,
    output: Path,
    args: argparse.Namespace,
    contract: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    run_dir = output / f"run-{mode}"
    run_dir.mkdir()
    sd_copy = run_dir / "system-sd.img"
    subprocess.run(
        ["cp", "--reflink=auto", "--sparse=always", str(args.sd_image), str(sd_copy)],
        check=True,
    )
    d81_copy = run_dir / image.name
    shutil.copyfile(image, d81_copy)
    d81_copy.chmod(0o444)
    screen = run_dir / "framebuffer.txt"
    screenshot = run_dir / "framebuffer.png"
    memory = run_dir / "memory.bin"
    log = run_dir / "xemu.log"
    command = [
        str(SAFE_RUNNER), str(memory), str(args.timeout), str(args.xemu),
        "-skipconfigfile", "-headless", "-testing", "-sleepless", "-besure", "-fastboot",
        "-rom", str(args.rom), "-sdimg", str(sd_copy), "-8", str(d81_copy), "-autoload",
        "-dumpscreen", str(screen), "-screenshot", str(screenshot), "-dumpmem", str(memory),
    ]
    with log.open("wb") as handle:
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
    require(completed.returncode in (0, 124), f"{mode} Xemu failed with {completed.returncode}")
    require(all(path.is_file() and path.stat().st_size for path in (screen, screenshot, memory)),
            f"{mode} did not emit all runtime artifacts")
    oracle = BOOT.framebuffer_result(
        screen.read_text(encoding="utf-8"), contract["framebuffer_oracles"][mode]
    )
    require(oracle["passed"], f"{mode} framebuffer failed: {oracle}")
    require(sha256(image) == sha256(d81_copy), f"{mode} D81 changed during run")
    require(sha256(args.sd_image) == sha256(sd_copy), f"{mode} system SD changed during run")
    return {
        "id": f"product-medium-init-{mode}",
        "family": "complete-product-medium-per-cold-boot",
        "transport": "external-drive-8-only",
        "fresh_emulator_process": True,
        "manual_boot_media_swap": False,
        "freezer_operations": 0,
        "claims_freezer_behavior": False,
        "device_choreography_gap": GAP,
        "evidence_class": contract["evidence_class"],
        "tool_identity": identity,
        "media": bind(image),
        "execution": {"timeout_seconds": args.timeout, "status": completed.returncode},
        "framebuffer_oracle": oracle,
        "outputs": {
            "framebuffer_sha256": sha256(screen),
            "screenshot_sha256": sha256(screenshot),
            "memory_sha256": sha256(memory),
        },
    }


def receipt_claim(rows: list[dict[str, Any]], blind: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_class": blind["evidence_class"],
        "tool_identity": blind["qualified_tool_identity"],
        "prefilter_rows": [
            {"id": row["id"], "result": "PASS", "touches": []} for row in rows
        ],
        "device_mandatory_rows": list(BLIND.BLIND_IDS),
        "device_acceptance_claimed": False,
    }


def build(args: argparse.Namespace) -> None:
    contract = load(CONTRACT_PATH)
    blind = load(BLIND_CONTRACT_PATH)
    validate_contract(contract)
    BLIND.validate_contract(blind)
    verify_bound_inputs(contract, args.rom, args.sd_image)
    adapter = BOOT.verify_adapter(args.adapter_manifest, args.xemu, load(BOOT.CONTRACT_PATH))
    identity = blind["qualified_tool_identity"]
    require(adapter["binary"]["sha256"] == identity["binary_sha256"], "adapter identity drift")
    require(not args.out.exists(), f"output already exists: {args.out}")
    args.out.mkdir(parents=True)
    media = create_media(contract, args.out)
    absent_raw, valid_raw, error_raw = (media[mode].read_bytes() for mode in ("absent", "valid", "error"))
    diff = INIT.cross_variant_proof(absent_raw, valid_raw, error_raw)
    rows = [run_variant(mode, media[mode], args.out, args, contract, identity)
            for mode in ("absent", "valid", "error")]
    item1 = load(ROOT / contract["inputs"]["item1_receipt"]["path"])
    drive8_row = {
        "id": VARIANT_IDS[0],
        "family": "drive-8-only",
        "source": "bound-item1-runtime-receipt",
        "evidence_class": contract["evidence_class"],
        "freezer_operations": 0,
        "claims_freezer_behavior": False,
        "device_choreography_gap": GAP,
        "framebuffer_sha256": item1["successor"]["framebuffer_sha256"],
        "screenshot_sha256": item1["successor"]["screenshot_sha256"],
    }
    all_rows = [drive8_row, *rows]
    claim = receipt_claim(all_rows, blind)
    BLIND.validate_prefilter_claim(claim, blind)
    receipt = {
        "format": "lisp65-dwx-freezer-free-boot-variants-receipt-v1",
        "status": "PASS",
        "recorded_on": "2026-09-02",
        "evidence_class": contract["evidence_class"],
        "authority": {
            "contract": bind(CONTRACT_PATH),
            "blind_spot_contract": bind(BLIND_CONTRACT_PATH),
            "item1_receipt": bind(ROOT / contract["inputs"]["item1_receipt"]["path"]),
        },
        "tool_identity": identity,
        "choreography": contract["variant_policy"],
        "drive8_only": drive8_row,
        "product_media_variants": rows,
        "product_media_diff_attribution": diff,
        "prefilter_claim": claim,
        "mutations": {"attempted": mutation_names(contract), "survived": []},
        "accounting": {
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "fresh_xemu_processes": 3,
        },
        "claim_limit": "The freezer-free variants expose but do not exercise the device library-medium Freezer choreography.",
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("dwx freezer-free variants BUILD PASS drive8=1 product-media=3 freezer=0")


def validate_receipt(receipt: dict[str, Any], contract: dict[str, Any], blind: dict[str, Any]) -> None:
    validate_contract(contract)
    BLIND.validate_contract(blind)
    rows = receipt.get("product_media_variants")
    claim = receipt.get("prefilter_claim")
    require(isinstance(claim, dict), "freezer-free prefilter claim absent")
    sealed_claim = claim.get("device_mandatory_rows") == SEALED_ITEM3_DEVICE_ROWS
    expected_identity = (
        blind["sealed_item2_tool_identity"]
        if sealed_claim else blind["qualified_tool_identity"]
    )
    require(
        receipt.get("format") == "lisp65-dwx-freezer-free-boot-variants-receipt-v1"
        and receipt.get("status") == "PASS"
        and receipt.get("evidence_class") == "xemu-prefilter-green"
        and receipt.get("tool_identity") == expected_identity
        and receipt.get("choreography") == contract["variant_policy"]
        and receipt.get("drive8_only", {}).get("id") == VARIANT_IDS[0]
        and isinstance(rows, list)
        and tuple(row.get("id") for row in rows) == PRODUCT_IDS,
        "freezer-free receipt header or row population drift",
    )
    blind_binding = SEALED_ITEM3_BLIND_BINDING if sealed_claim else bind(BLIND_CONTRACT_PATH)
    require(
        receipt.get("authority") == {
            "contract": bind(CONTRACT_PATH),
            "blind_spot_contract": blind_binding,
            "item1_receipt": bind(ROOT / contract["inputs"]["item1_receipt"]["path"]),
        },
        "freezer-free receipt authority drift",
    )
    item1 = load(ROOT / contract["inputs"]["item1_receipt"]["path"])
    require(
        receipt["drive8_only"].get("framebuffer_sha256")
        == item1["successor"]["framebuffer_sha256"]
        and receipt["drive8_only"].get("screenshot_sha256")
        == item1["successor"]["screenshot_sha256"],
        "drive-8-only evidence is not Item-1-bound",
    )
    for row in [receipt["drive8_only"], *rows]:
        require(
            row.get("freezer_operations") == 0
            and row.get("claims_freezer_behavior") is False
            and row.get("device_choreography_gap") == GAP
            and row.get("evidence_class") == "xemu-prefilter-green",
            f"{row.get('id')} hid or overclaimed the Freezer gap",
        )
    require(
        all(row.get("fresh_emulator_process") is True for row in rows)
        and all(row.get("manual_boot_media_swap") is False for row in rows)
        and all(row.get("family") == "complete-product-medium-per-cold-boot" for row in rows)
        and all(row.get("transport") == "external-drive-8-only" for row in rows)
        and all(row.get("framebuffer_oracle", {}).get("passed") is True for row in rows),
        "product-medium choreography or oracle drift",
    )
    require(
        {row["id"]: row["media"]["sha256"] for row in rows} == EXPECTED_MEDIA_SHA256
        and {row["id"]: row["outputs"]["framebuffer_sha256"] for row in rows}
        == EXPECTED_FRAMEBUFFER_SHA256,
        "product-medium or framebuffer identity drift",
    )
    diff = receipt.get("product_media_diff_attribution")
    require(isinstance(diff, dict), "product-media diff attribution absent")
    valid_diff = diff.get("absent_to_valid", {})
    error_diff = diff.get("absent_to_error", {})
    cross_diff = diff.get("valid_to_error", {})
    require(
        diff.get("rule") == "one frozen product filesystem; INIT.L65 is the sole variant"
        and diff.get("frozen_product", {}).get("visible_member_count") == 15
        and valid_diff.get("non_INIT_member_count") == 15
        and error_diff.get("non_INIT_member_count") == 15
        and valid_diff.get("non_INIT_members") == error_diff.get("non_INIT_members")
        and valid_diff.get("INIT_L65", {}).get("sha256")
        == contract["init_payloads"]["valid"]["sha256"]
        and error_diff.get("INIT_L65", {}).get("sha256")
        == contract["init_payloads"]["error"]["sha256"]
        and valid_diff.get("result") == "only-INIT-payload-and-owned-filesystem-metadata-differ"
        and error_diff.get("result") == "only-INIT-payload-and-owned-filesystem-metadata-differ"
        and cross_diff.get("result") == "only-shared-INIT-payload-chain-differs",
        "product-medium diff attribution drift",
    )
    if sealed_claim:
        require(
            claim.get("evidence_class") == "xemu-prefilter-green"
            and claim.get("tool_identity") == expected_identity
            and claim.get("device_acceptance_claimed") is False
            and all(
                row.get("result") == "PASS" and row.get("touches") == []
                for row in claim.get("prefilter_rows", [])
            ),
            "sealed Item-3 prefilter claim drift",
        )
    else:
        BLIND.validate_prefilter_claim(claim, blind)
    require(
        receipt.get("mutations") == {"attempted": mutation_names(contract), "survived": []}
        and receipt.get("accounting") == {
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "fresh_xemu_processes": 3,
        },
        "freezer-free mutations or accounting drift",
    )


def check() -> None:
    contract = load(CONTRACT_PATH)
    blind = load(BLIND_CONTRACT_PATH)
    receipt = load(RECEIPT_PATH)
    validate_receipt(receipt, contract, blind)
    report = REPORT_PATH.read_text(encoding="utf-8")
    plan = WORK_PLAN_PATH.read_text(encoding="utf-8")
    require(
        "Laufwerk-8-only" in report
        and "Produktmedium pro Kaltboot" in report
        and "keine Freezer-Aussage" in report,
        "freezer-free report lost its choreography boundary",
    )
    item3 = plan.split("### Item 3", 1)[1].split("### Item 4", 1)[0]
    require("**Closed 2026-09-02:**" in item3, "work plan does not close Item 3")
    print("dwx freezer-free variants CHECK PASS drive8=1 product-media=3 freezer-claims=0")


def selftest() -> None:
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    names = mutation_names(contract)
    require(len(names) == 10, "freezer-free mutation population drift")
    print(f"dwx freezer-free variants SELFTEST PASS mutations={len(names)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    parser.add_argument("--xemu", type=Path)
    parser.add_argument("--adapter-manifest", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--sd-image", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args(argv[1:])
    if args.action == "selftest":
        selftest()
    elif args.action == "check":
        check()
    else:
        missing = [name for name in ("xemu", "adapter_manifest", "rom", "sd_image", "out")
                   if getattr(args, name) is None]
        require(not missing, "build arguments missing: " + ", ".join(missing))
        args.xemu = args.xemu.resolve()
        args.adapter_manifest = args.adapter_manifest.resolve()
        args.rom = args.rom.resolve()
        args.sd_image = args.sd_image.resolve()
        args.out = args.out.resolve()
        build(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (VariantError, BLIND.ContractError, BOOT.BootError, OSError, subprocess.CalledProcessError) as error:
        print(f"dwx-freezer-free-boot-variants: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
