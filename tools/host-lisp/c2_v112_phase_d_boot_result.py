#!/usr/bin/env python3
"""Close the owner-authorized Link-92 Phase-D D1 launch repetition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402

PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-boot-choreography-diff-receipt.json")
MEDIA = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5/shared-system/"
    "lisp65-product.d81")
RUN = ROOT / "build/c2.3/v1.4.0-release/phase-d-split/d1-boot"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-split-d1-boot-device-receipt.json")
RECORDED_ON = "2026-08-08"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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


def main() -> int:
    try:
        preparation = load(PREPARATION)
        require(preparation.get("status") ==
                "passed-precedent-equivalent-mount-reset-corrected-observation-contract",
                "D1 boot preparation authority drift")
        require(preparation.get("mutation_count") == 18
                and preparation.get("execution_accounting", {}).get(
                    "hardware_contacts") == 0,
                "D1 boot preparation accounting drift")

        fresh_png = RUN / "D1-fresh-basic.png"
        fresh_text = RUN / "D1-fresh-basic.txt"
        upload = RUN / "D1-upload.log"
        readback = RUN / "D1-package-readback.d81"
        banner_png = RUN / "D1-banner.png"
        banner_text = RUN / "D1-banner.txt"
        fresh = fresh_text.read_text(encoding="utf-8", errors="replace")
        banner = banner_text.read_text(encoding="utf-8", errors="replace")
        require(("BASIC 65" in fresh or "READY." in fresh)
                and "lisp65>" not in fresh,
                "D1 fresh-BASIC precondition did not hold")
        require(MEDIA.read_bytes() == readback.read_bytes(),
                "D1 uploaded medium readback drift")
        SCREEN.check_fail_closed_frame(banner_png)
        require("WORKBENCH 1.4.0" in banner and "lisp65>" in banner,
                "D1 banner/prompt postcondition drift")

        result = {
            "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-split-d1-boot-device-v1",
            "recorded_on": RECORDED_ON,
            "status": "passed-split-media-link92-d1-autoboot-launch-banner-and-prompt",
            "authorization": {
                "boot_choreography_commit": "e001a1cc",
                "split_restart_commit": "a1cf5b9b",
                "calendar_authority_repair_commit": "55c39443",
                "class": "B",
                "scope": "one fresh D1 launch on the host-green split media through the sole bound entry point",
            },
            "preconditions": {
                "fresh_BASIC": "passed",
                "exact_D81_readback": "passed",
                "mount_and_reset_shape": "v1.3-precedent-equivalent",
                "post_mount_explicit_resets": 0,
                "quiet_seconds_before_first_observation": 45,
            },
            "postcondition": {
                "fail_closed_frame": False,
                "banner": "WORKBENCH 1.4.0",
                "prompt": "lisp65>",
                "classification": "D1 launch green",
            },
            "bindings": {
                "preparation": bind(PREPARATION),
                "source_media": bind(MEDIA),
                "fresh_basic_screen": bind(fresh_png),
                "fresh_basic_text": bind(fresh_text),
                "upload_log": bind(upload),
                "package_readback": bind(readback),
                "banner_screen": bind(banner_png),
                "banner_text": bind(banner_text),
            },
            "execution_accounting": {
                "hardware_contacts": 1,
                "D1_launch_rows": 1,
                "D1_smoke_rows": 0,
                "D3_rows": 0,
                "D2_rows": 0,
                "owner_input": 0,
                "product_rebuilds": 0,
                "media_rebuilds": 0,
                "additional_links": 0,
            },
            "disposition": {
                "split_restart_D1": "green",
                "next": "run all three D1 smokes on this live split-media REPL before D3 and D2",
                "D3": "not_started",
                "D2": "not_started",
                "phase_E": "closed",
            },
            "claim_limit": "The exact split-media Link-92-r5 product medium proves cold AUTOBOOT through the visible WORKBENCH 1.4.0 lisp65 prompt only. D1 smokes, D3, D2, selector, Halt, Phase E and release remain unclaimed.",
        }
        RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        print("c2-v112-phase-d-boot-result: PASS banner='WORKBENCH 1.4.0' prompt='lisp65>'")
        return 0
    except (ResultError, SCREEN.CheckError, OSError, json.JSONDecodeError) as error:
        message = getattr(error, "message", str(error))
        print(f"c2-v112-phase-d-boot-result: FIRST RED: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
