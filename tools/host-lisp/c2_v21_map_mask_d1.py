#!/usr/bin/env python3
"""Prepare and record crossing-free Link-109 D1."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2-v150-v21-map-mask-far-device-session.json"
RUNNER = ROOT / "scripts/c2-v21-map-mask-d1-hw.sh"
MEDIA = ARCH / "c2.3-v2.1-map-mask-media-receipt.json"
SUMMARY = ARCH / "c2.3-v2.1-map-mask-completion-media-receipt.json"
PREP = ARCH / "c2.3-v2.1-map-mask-d1-preparation-receipt.json"
RESULT = ARCH / "c2.3-v2.1-map-mask-d1-receipt.json"
OUT = ROOT / "build/c2.3/v2.1-map-mask-d1"
VISIBLE = ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
           "LISP65: LOADING LIBRARIES", "WORKBENCH 1.5.0", "lisp65>"]


class D1Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value: raise D1Error(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def contract(override: dict[str, Any] | None = None) -> dict[str, Any]:
    config = load(CONFIG) if override is None else override
    media = load(MEDIA); summary = load(SUMMARY)
    packed = media.get("packed_artifact_gate_registry", {})
    require(
        config.get("status") == "prepared-D1-repeat-authorized"
        and config.get("boot_access_free_seconds") == 45
        and config.get("recontact_authorized") is True
        and config.get("D2_D5_open") is False
        and config["identity"]["product_medium"] ==
            media["shared_system"]["product_D81"]["path"]
        and config["identity"]["library_medium"] ==
            media["library"]["D81"]["path"]
        and config["authority"]["media_closure"] ==
            MEDIA.relative_to(ROOT).as_posix()
        and media.get("status") ==
            "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
        and media["materialization"]["delivered_bytes"] == 48156
        and media["materialization"]["payload_bytes"] == 874
        and media["materialization"]["gate"]["identity_mismatches"] == 0
        and media["pair_identity"]["result"] == "same-world-pair"
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and media["hardware_handoff"]["D1_repeat_authorized"] is True
        and media["hardware_handoff"]["D2_D5_open"] is False
        and summary.get("status") ==
            "PASS: Link 109 completed and same-world media closed; D1 ready"
        and summary["hardware_handoff"] == {"D1_ready": True,
            "D2_D5_open": False, "session": bind(CONFIG)},
        "Link-109 D1 contract/media authority drift")
    return config


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = RUNNER.read_text(encoding="utf-8") if source_override is None else source_override
    require("dry-run|stage|confirm-terminal" in source
        and source.count("ftp_bundle_under_basic") == 2
        and 'cmp "$product" "$OUT/product-readback.d81"' in source
        and 'cmp "$library" "$OUT/library-readback.d81"' in source
        and "# PRODUCT-LIVE-BEGIN" in source
        and 'python3 "$PY" record' in source,
        "Link-109 D1 runner lifecycle token absent")
    live = source.split("# PRODUCT-LIVE-BEGIN", 1)[1]
    require("capture_screen" not in live and "run_m65" not in live
        and "mega65_ftp" not in live and "$FTP" not in live
        and live.count("sleep") == 1,
        "Link-109 D1 admits automated post-mount access")
    require(all(f"'{line}'" in live for line in VISIBLE),
            "Link-109 D1 owner postcondition incomplete")
    return {"result": "passed", "fresh_BASIC_capture_before_boot": 1,
        "media_readbacks_before_boot": 2,
        "automated_post_mount_observations": 0, "post_boot_FTP": 0,
        "owner_visible_postcondition": True,
        "minimum_hands_off_seconds": 45, "D2_D5_actions": 0}


def mutations(config: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    for name, key, value in (("short-window", "boot_access_free_seconds", 20),
                             ("open-D2", "D2_D5_open", True)):
        def check(key=key, value=value) -> None:
            trial = deepcopy(config); trial[key] = value; contract(trial)
        cases[name] = check
    source_cases = {
        "postmount-screenshot": source.replace(
            "# PRODUCT-LIVE-BEGIN", "# PRODUCT-LIVE-BEGIN\n  capture_screen forbidden", 1),
        "postmount-monitor": source.replace(
            "# PRODUCT-LIVE-BEGIN", "# PRODUCT-LIVE-BEGIN\n  run_m65 -r", 1),
        "skip-product-readback": source.replace(
            '  cmp "$product" "$OUT/product-readback.d81"\n', "", 1),
        "skip-library-readback": source.replace(
            '  cmp "$library" "$OUT/library-readback.d81"\n', "", 1),
        "drop-terminal-line": source.replace(
            "  'lisp65>' > \"$OUT/owner-visible-postcondition.txt\"\n", "", 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)
    rejected = []
    for name, check in cases.items():
        try: check()
        except D1Error: rejected.append(name)
    require(rejected == list(cases), "Link-109 D1 mutation survived")
    return rejected


def derive_preparation() -> dict[str, Any]:
    config = contract(); source = RUNNER.read_text(encoding="utf-8")
    return {"format": "lisp65-c2.3-v2.1-map-mask-d1-preparation-v1",
        "recorded_on": "2026-08-15", "status": "V21-LINK109-D1-PREPARED-NOT-RUN",
        "authority": {"media": bind(MEDIA), "summary": bind(SUMMARY),
            "config": bind(CONFIG), "runner": bind(RUNNER),
            "checker": bind(Path(__file__))},
        "runner_gate": runner_gate(source),
        "owner_visible_postcondition": VISIBLE,
        "mutations_rejected": mutations(config, source),
        "execution_accounting": {"hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1": True, "D2_D5": False},
        "claim_limit": "Fresh crossing-free Link-109 D1 only; D2-D5 closed."}


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("status") == "V21-LINK109-D1-PREPARED-NOT-RUN"
        and value.get("runner_gate", {}).get(
            "automated_post_mount_observations") == 0
        and len(value.get("mutations_rejected", [])) == 7
        and value.get("unlock") == {"D1": True, "D2_D5": False},
        "Link-109 D1 preparation drift")
    if verify: require(value == derive_preparation(), "Link-109 D1 preparation stale")


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    lines = (OUT / "owner-visible-postcondition.txt").read_text(
        encoding="utf-8").splitlines()
    require(lines == VISIBLE and (OUT / "owner-terminal-confirmed").is_file(),
            "Link-109 owner terminal confirmation absent")
    config = load(CONFIG)
    product = ROOT / config["identity"]["product_medium"]
    library = ROOT / config["identity"]["library_medium"]
    require((OUT / "product-readback.d81").read_bytes() == product.read_bytes()
        and (OUT / "library-readback.d81").read_bytes() == library.read_bytes(),
        "Link-109 D1 media readback drift")
    return {"format": "lisp65-c2.3-v2.1-map-mask-d1-v1",
        "recorded_on": "2026-08-15", "status": "V21-LINK109-D1-GREEN",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA)},
        "physical_owner_observation": lines,
        "discipline": {"automated_post_mount_observations": 0,
            "stops": 0, "resumes": 0, "forms": 0},
        "unlock": {"D2_D5": True},
        "claim_limit": "D1 only; D2-D5 have not run."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "prepare", "check", "record"))
    action = parser.parse_args().action
    if action == "selftest":
        validate_preparation(derive_preparation(), verify=False)
        print("Link-109 D1: SELFTEST PASS mutations=7")
    elif action == "prepare":
        require(not PREP.exists(), "Link-109 D1 preparation exists")
        PREP.write_bytes(canonical(derive_preparation()))
        print("Link-109 D1: PREPARED D2-D5=CLOSED")
    elif action == "check":
        validate_preparation(load(PREP), verify=True)
        print("Link-109 D1: CHECK PASS D2-D5=CLOSED")
    else:
        require(not RESULT.exists(), "Link-109 D1 result exists")
        RESULT.write_bytes(canonical(derive_result()))
        print("Link-109 D1: PASS D2-D5 now permitted")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"LINK-109 D1: {error}", file=sys.stderr)
        raise SystemExit(1)
