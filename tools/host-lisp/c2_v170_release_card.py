#!/usr/bin/env python3
"""Build and qualify the owner-commissioned v1.7.0 release product card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_init_l65_card as INIT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = INIT.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-release-card-report.md"
BUILD = ROOT / "build/c2.3/v1.7.0-release-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.7.0-release-card-r1-preflight"
RECEIPT = ARCH / "c2.3-v1.7.0-release-card-r1-receipt.json"
FIRST_RED = ARCH / "c2.3-v1.7.0-release-card-r1-first-red.json"
RESUME_RECEIPT = ARCH / (
    "c2.3-v1.7.0-release-card-r1-read-only-resume-receipt.json")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v170-release-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
BANNER = ROOT / "lib/repl-banner.lisp"
PREDECESSOR_BUILD = INIT.BUILD
PREDECESSOR_ELF = INIT.ELF
PREDECESSOR_PRG = INIT.PRG
PREDECESSOR_CODE = INIT.CODE
PREDECESSOR_MANIFEST = INIT.MANIFEST
PREDECESSOR_RECEIPT = INIT.RECEIPT
PREDECESSOR_STATUS = INIT.STATUS
DEVICE_RESULT = ARCH / (
    "c2.3-v1.7-init-l65-product-variants-device-result-receipt.json")
AUTHORIZATION = "bb2cd463"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v170-release-product-card-v1"
STATUS = "PASS: V1.7.0 RELEASE PRODUCT CARD FINAL GREEN"
EXPECTED_BANNER = "WORKBENCH 1.7.0"
PREDECESSOR_BANNER = "WORKBENCH 1.5.0"


class ReleaseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReleaseError(message)


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


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in (
        "v1.7.0 ships",
        "release block commission",
        "one release card under producer discipline",
        "release media from the accepted final world",
        "d5 measures the shipped configuration against the 32/384 floor",
        "banner workbench 1.7.0",
        "ship at the session",
        "publish at the end",
    ):
        require(token in text, f"v1.7 release authority absent: {token}")
    device = load(DEVICE_RESULT)
    predecessor = load(PREDECESSOR_RECEIPT)
    require(device["status"] == "PASS: V1.7 NATIVE INIT.L65 HARDWARE ACCEPTED"
            and device["rows"]["I-present"]["result"] == "PASS"
            and device["rows"]["I-error"]["result"] == "PASS"
            and device["rows"]["A0-perception"]["owner_observation"]
                == "prompt returned practically immediately"
            and predecessor["status"] == PREDECESSOR_STATUS,
            "accepted INIT/A0 predecessor authority drift")
    return {
        "owner_plan": {"authority": "git-blob", "commit": AUTHORIZATION,
            "path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()},
        "accepted_INIT_device_result": bind(DEVICE_RESULT),
        "accepted_final_world": bind(PREDECESSOR_RECEIPT),
    }


def _configure_paths() -> None:
    INIT.BUILD = BUILD
    INIT.PREFLIGHT = PREFLIGHT
    INIT.RECEIPT = RECEIPT
    INIT.ELF = ELF
    INIT.PRG = PRG
    INIT.PROFILE = PROFILE
    INIT.PLANE_ROOT = PLANE_ROOT
    INIT.PLANE_RECEIPT = PLANE_RECEIPT
    INIT.C2D = C2D
    INIT.CODE = CODE
    INIT.MANIFEST = MANIFEST
    INIT.BANNER = BANNER
    INIT.DRIVER = DRIVER
    INIT.FORMAT = FORMAT
    INIT.STATUS = STATUS


def configure() -> None:
    _configure_paths()
    INIT.configure()
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate


def banner_gate() -> dict[str, Any]:
    source = BANNER.read_text(encoding="utf-8")
    require(source.count(EXPECTED_BANNER) == 1
            and PREDECESSOR_BANNER not in source,
            "release banner source is absent, duplicated or still historical")
    emitted = INIT._compile_banner(source)
    require(emitted["direct_object_bytes"] == 65
            and ["CALL", "%banner-subtitle", 0] in emitted["call_edges"],
            "release banner caller lost its subtitle owner")
    predecessor_source = source.replace(EXPECTED_BANNER, PREDECESSOR_BANNER, 1)
    mutant = INIT._compile_banner(predecessor_source)
    require(predecessor_source.count(PREDECESSOR_BANNER) == 1
            and EXPECTED_BANNER not in predecessor_source,
            "historical-banner mutation was ineffective")
    final_literal = None
    if MANIFEST.is_file():
        manifest = load(MANIFEST)
        owner = next(row for row in manifest["entries"]
                     if row["name"] == "%repl-banner")
        final_literal = owner["literals"][-1].get("string")
        require(final_literal == EXPECTED_BANNER,
                "release banner did not reach the final composed owner")
    return {
        "status": "PASS: WORKBENCH 1.7.0 IS THE UNIQUE EMITTED BANNER",
        "source": bind(BANNER), "emitted": emitted,
        "final_composed_literal": final_literal,
        "mutations_rejected": ["reintroduce-WORKBENCH-1.5.0"],
    }


def configuration_gate() -> dict[str, Any]:
    value = INIT.configuration_gate()
    require(value["world"] == "item-1-plus-A0-plus-native-init"
            and value["closed_freight"] == [
                "Comfort", "Block-3", "diagnostic-witness"],
            "release card reopened parked or diagnostic freight")
    value.update({
        "world": "v1.7.0-release-product",
        "release_banner": banner_gate(),
        "release_freight": ["native-INIT.L65", "A0-recovery-fast-path"],
        "parked": ["Comfort", "Block-3", "canonical-prompt-swap"],
    })
    return value


def _byte_diff(before: bytes, after: bytes) -> list[dict[str, int]]:
    require(len(before) == len(after), "release banner changed plane extent")
    return [{"offset": index, "before": left, "after": right}
            for index, (left, right) in enumerate(zip(before, after))
            if left != right]


def plane_successor_gate() -> dict[str, Any]:
    before = PREDECESSOR_CODE.read_bytes()
    after = CODE.read_bytes()
    differences = _byte_diff(before, after)
    old = load(PREDECESSOR_MANIFEST)
    new = load(MANIFEST)
    old_banner = next(row for row in old["entries"]
                      if row["name"] == "%repl-banner")
    new_banner = next(row for row in new["entries"]
                      if row["name"] == "%repl-banner")
    old_other = [row for row in old["entries"] if row["name"] != "%repl-banner"]
    new_other = [row for row in new["entries"] if row["name"] != "%repl-banner"]
    require(old_other == new_other
            and old_banner["length"] == new_banner["length"] == 155
            and old_banner["literals"][-1] == {"string": PREDECESSOR_BANNER}
            and new_banner["literals"][-1] == {"string": EXPECTED_BANNER}
            and differences == [],
            "release changed emitted code or a non-banner entry")

    def binary_delta(relative: str) -> list[dict[str, int]]:
        return _byte_diff(
            (PREDECESSOR_MANIFEST.parent / relative).read_bytes(),
            (MANIFEST.parent / relative).read_bytes())

    ext = binary_delta("stdlib-p0.ext.bin")
    c2i = binary_delta("product/stdlib-p0.c2i.bin")
    c2d3 = binary_delta("product/initial.c2d-v3.bin")
    c2d6 = binary_delta("v6-semantics/initial.c2d-v6.bin")
    shelf = binary_delta("product/product-shelf-v4-direct.bin")
    banner_delta = {"before": ord("5"), "after": ord("7")}
    require(len(ext) == len(c2i) == 1
            and {key: ext[0][key] for key in ("before", "after")}
                == banner_delta
            and {key: c2i[0][key] for key in ("before", "after")}
                == banner_delta
            and [row["offset"] for row in c2d3]
                == list(range(40, 48)) + list(range(76, 80))
            and [row["offset"] for row in c2d6] == list(range(40, 48))
            and [row["offset"] for row in shelf]
                == list(range(18, 26)) + list(range(54, 62)) + [66162]
            and {key: shelf[-1][key] for key in ("before", "after")}
                == banner_delta,
            "release plane successor has an unattributed payload delta")
    return {
        "status": "PASS: BANNER BYTE PLUS DERIVED IDENTITIES FULLY ATTRIBUTED",
        "predecessor": bind(PREDECESSOR_CODE), "candidate": bind(CODE),
        "code_differences": differences,
        "unchanged_non_banner_entries": len(new_other),
        "banner": {"before": PREDECESSOR_BANNER, "after": EXPECTED_BANNER,
                   "object_bytes": new_banner["length"]},
        "payload_differences": {"stdlib_ext": ext, "product_c2i": c2i,
                                "product_shelf": shelf},
        "derived_identity_differences": {"c2d_v3": c2d3, "c2d_v6": c2d6,
            "product_shelf_header": shelf[:-1]},
        "families": {
            "banner_payload": 3,
            "derived_C2D_identity": len(c2d3) + len(c2d6),
            "derived_shelf_identity": len(shelf) - 1,
            "unattributed": 0,
        },
        "mutations": ["second-code-byte-difference",
                       "second-payload-byte-difference",
                       "identity-byte-outside-derived-fields"],
    }


def final_gate() -> dict[str, Any]:
    product = INIT.final_gate()
    plane = plane_successor_gate()
    before = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=INIT.READOBJ)
    after = ElfTruth.read(ELF, llvm_readobj=INIT.READOBJ)
    require(before.section(".text").bytes == after.section(".text").bytes
            and before.section(".bss").bytes == after.section(".bss").bytes,
            "banner-only release changed resident text or state extent")
    product["release_v1_7_0"] = {
        "status": "PASS: RELEASE PRODUCT IS ACCEPTED WORLD PLUS BANNER",
        "banner": banner_gate(), "plane_successor": plane,
        "resident_extents": {
            "text_before": before.section(".text").bytes,
            "text_after": after.section(".text").bytes,
            "bss_before": before.section(".bss").bytes,
            "bss_after": after.section(".bss").bytes,
        },
        "predecessor_pair": {"ELF": bind(PREDECESSOR_ELF),
                             "PRG": bind(PREDECESSOR_PRG)},
        "claim_boundary": {
            "ships": ["native INIT.L65", "A0 recovery fast path"],
            "excludes": ["Comfort", "Block-3", "canonical prompt swap"],
        },
    }
    return product


def write_report() -> None:
    value = load(RECEIPT)
    release = value["final_product"]["release_v1_7_0"]
    plane = release["plane_successor"]
    REPORT.write_text(f"""# v1.7.0 release product card

Status: **{value['status']}**

The release producer rebuilt the hardware-accepted native `INIT.L65` plus A0
world exactly once.  `WORKBENCH 1.7.0` is the unique emitted banner.  The
accepted and release code planes have equal extent and are byte-identical.
Each materialized banner payload changes exactly one ASCII version digit
(`5` -> `7`); every remaining changed byte belongs to a derived C2D, catalog,
build-ID or CRC field.  All non-banner bytecode entries are identical and the
successor attribution has zero unexplained members.

Resident `.text` and `.bss` extents are unchanged.  Comfort, Block 3, the
canonical prompt swap and diagnostic freight remain absent.  Scope and
Acceptance qualify the same frozen ELF/PRG pair; the card builds no media and
makes no device contact.

The next rung is artifact-only release media plus the owner-held D-session.
`Ship` and `Publish` remain owner words.
""", encoding="utf-8")


def preflight() -> None:
    configure()
    INIT.preflight()
    print("v1.7.0 release: PREFLIGHT PASS card=0/1 banner=1.7.0")


def build() -> None:
    configure()
    BASE.build()
    write_report()
    check()
    print("v1.7.0 release: BUILD PASS WPLTO=1 link=1 media=0 device=0")


def resume() -> None:
    configure()
    require(not RECEIPT.exists() and not RESUME_RECEIPT.exists(),
            "release read-only Resume is one-shot")
    red = load(FIRST_RED)
    require(red["status"] ==
                "FIRST RED: RELEASE SUCCESSOR EXPECTED CODE-PAYLOAD IDENTITY"
            and red["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0},
            "release Resume First-Red authority drift")
    pair_before = BASE.artifacts()
    producer = load(BASE.PRODUCER_RESULT)
    scope = load(BASE.SCOPE_RESULT)
    acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(producer["status"] == scope["status"] == acceptance["status"]
                == "PASS", "release frozen tail is not green")
    gate = final_gate()
    pair_after = BASE.artifacts()
    require(pair_before == pair_after, "release Resume changed frozen pair")
    pre = load(BASE.PREFLIGHT_RECEIPT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-27", "status": STATUS,
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT), "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": pair_before, "artifacts_after": pair_after,
        "processes": [{"action": "read-only-release-final-gate-resume",
            "status": "PASS", "new_WPLTO_runs": 0,
            "new_product_links": 0, "new_cards_consumed": 0}],
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume": {"read_only": True, "first_red": bind(FIRST_RED),
            "artifacts_before": pair_before, "artifacts_after": pair_after,
            "new_WPLTO_runs": 0, "new_product_links": 0,
            "new_cards_consumed": 0},
        "media_authorized": True,
        "next": "artifact-only release media and owner-held D-session",
    }
    RECEIPT.write_bytes(canonical(value))
    RESUME_RECEIPT.write_bytes(canonical({
        "format": "lisp65-c2-v170-release-read-only-resume-v1",
        "recorded_on": "2026-08-27",
        "status": "PASS: RELEASE FINAL GATE RESUMED READ-ONLY",
        "first_red": bind(FIRST_RED), "final_card": bind(RECEIPT),
        "artifacts_before": pair_before, "artifacts_after": pair_after,
        "execution": {"new_WPLTO_runs": 0, "new_product_links": 0,
                      "new_cards_consumed": 0},
        "claim_limit": "Final-gate Resume only; no build, media or device.",
    }))
    write_report()
    check()
    print("v1.7.0 release: RESUME PASS WPLTO=0 link=0 card=0")


def check() -> None:
    configure()
    BASE.check()
    value = load(RECEIPT)
    release = value["final_product"]["release_v1_7_0"]
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and release["banner"]["final_composed_literal"] == EXPECTED_BANNER
            and release["plane_successor"]["families"]["unattributed"] == 0
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and REPORT.is_file(),
            "v1.7.0 release card receipt drift")
    print("v1.7.0 release: CHECK PASS banner=WORKBENCH-1.7.0")


def run(action: str) -> None:
    {"preflight": preflight, "build": build, "resume": resume,
     "check": check,
     "_produce": lambda: (configure(), BASE.produce_child()),
     "_scope": lambda: (configure(), BASE.scope_child()),
     "_accept": lambda: (configure(), BASE.acceptance_child())}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "resume", "check",
        "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7.0 release: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
