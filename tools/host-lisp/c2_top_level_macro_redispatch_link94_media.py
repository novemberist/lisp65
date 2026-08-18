#!/usr/bin/env python3
"""Build/check the Link-94 trace-acceptance media without relinking product code."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_top_level_macro_redispatch_link94 as LINK94  # noqa: E402


BUILD = ROOT / "build/c2.3/top-level-macro-redispatch-link94-acceptance-media"
SHARED = BUILD / "shared-system"
LIBRARY = BUILD / "trace-library"
MANIFEST = SHARED / "candidate-manifest.json"
SOURCE_LIBRARY = ROOT / (
    "build/c2.3/trace-core-abi-link93-r6/trace-acceptance-media/trace-library"
)
CARD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-product-card-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link94-media-closure-receipt.json"
)
SESSION_CONFIG = ROOT / "config/c2-top-level-macro-redispatch-link94-device-session.json"
SESSION_SCRIPT = ROOT / "scripts/c2-top-level-macro-redispatch-link94-hw.sh"
BASE_TRACE_SCRIPT = ROOT / "scripts/c2-trace-core-abi-link93-hw.sh"
SISTER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json"
)
SISTER_CONFIG = ROOT / "config/c2-defstruct-terminal-ingress-session.json"
SISTER_SCRIPT = ROOT / "scripts/c2-defstruct-terminal-ingress-hw.sh"
CROSSING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-live-repl-ftp-crossing-gate-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
FORMAT = "lisp65-c2.3-link94-media-closure-v1"
EXPECTED_PRODUCT_D81 = "f47f8e49cd1378cc54dc6f62defc4dca6fa37ae69ce425e52109456f7be515ff"
EXPECTED_WORK_D81 = "bf887cd4f8b14b2e808bccfc223e64bfb1223a61e16e11169be0d34e669c63e3"
EXPECTED_MEDIA_MANIFEST = "696c5427e35132654c7b56fc23d9279b64224a2f815dcb0ff63209f601181679"
EXPECTED_ARTIFACT_SET = "ccca948610eb404cb6b0059bb11fb002f4bcedc4d401383621a9f79cab5a229b"
EXPECTED_LIBRARY = {
    "inspect.l65s": "c89c230fa647f8f90cf9c18845f7fe15d6eee9f9699227025f829c5c87416746",
    "l65index": "c5df5fa3ff650ccab7f84483f7d03e3e9b93f9090f64051e75054d9db707fdbe",
    "lisp65-library.d81": "5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd",
}


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def validate_session_contract() -> None:
    contract = load(SESSION_CONFIG)
    rows = contract.get("rows", [])
    require(
        contract.get("format")
            == "lisp65-c2.3-top-level-macro-redispatch-link94-device-session-v1"
        and contract.get("status") == "prepared-not-run"
        and contract.get("link_authority") == {
            "path": RECEIPT.relative_to(ROOT).as_posix(),
            "status": "LINK94-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
        }
        and contract.get("identity", {}).get("product_medium")
            == (SHARED / "lisp65-product.d81").relative_to(ROOT).as_posix()
        and contract.get("identity", {}).get("library_medium")
            == (LIBRARY / "lisp65-library.d81").relative_to(ROOT).as_posix()
        and contract.get("input") == {
            "owner_physical_keyboard": True,
            "virtual_transport_forbidden": True,
            "one_form_per_submission": True,
        }
        and [row.get("id") for row in rows] == [
            "require-inspect", "define-probe", "install-trace",
            "traced-call", "remove-trace", "restored-call",
        ]
        and [row.get("form") for row in rows] == [
            "(require (quote inspect))",
            "(defun trace-probe (x) (+ x 1))",
            "(trace trace-probe)",
            "(trace-probe 4)",
            "(untrace trace-probe)",
            "(trace-probe 4)",
        ]
        and [row.get("quiet_floor_seconds") for row in rows]
            == [180, 180, 180, 30, 120, 30]
        and rows[3].get("expect_ordered") == [
            "(trace-enter trace-probe 4)",
            "(trace-exit trace-probe 5)", "5", "lisp65>",
        ]
        and rows[5].get("forbid") == ["trace-enter", "trace-exit"],
        "Link-94 device-session contract drift",
    )
    sister = load(SISTER_RECEIPT)
    require(
        sister.get("status")
            == "HOST-GREEN-NON-PROMOTABLE-SISTER; BUNDLED-SESSION-READY"
        and sister["identity"]["hardware_runs"] == 0
        and sister["identity"]["promotable"] is False,
        "defstruct sister is not host-green and session-ready",
    )


def configure() -> None:
    LINK94.configure_card()
    CAN.MANIFEST = LINK94.MANIFEST
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = LINK94.MANIFEST
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = SHARED / "lisp65-product.d81"
    MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def copy_library() -> None:
    require(not LIBRARY.exists(), "Link-94 trace-library copy is one-shot")
    require(SOURCE_LIBRARY.is_dir(), "Link-93 trace-library authority absent")
    shutil.copytree(SOURCE_LIBRARY, LIBRARY)
    require(
        {path.name for path in LIBRARY.iterdir()} == set(EXPECTED_LIBRARY),
        "Link-94 trace-library inventory drift",
    )
    require(
        all(sha(LIBRARY / name) == digest
            for name, digest in EXPECTED_LIBRARY.items()),
        "Link-94 trace-library copy is not byte-identical to Link 93",
    )


def derive(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    validate_session_contract()
    card = load(CARD_RECEIPT)
    require(
        card.get("status")
            == "LINK94-HOST-PRODUCT-GREEN; MEDIA-AND-HARDWARE-PENDING"
        and card["attempt_accounting"]["product_closure_links"] == 1
        and card["attempt_accounting"]["hardware_runs"] == 0,
        "Link-94 product-card authority drift",
    )
    media = MEDIA.check()
    require(
        media["artifact_count"] == 19
        and media["canonical_product"] == bind(LINK94.MANIFEST)
        and media["artifact_set_sha256"] == EXPECTED_ARTIFACT_SET,
        "Link-94 shared-system media closure drift",
    )
    library = {name: bind(LIBRARY / name) for name in sorted(EXPECTED_LIBRARY)}
    require(
        all(row["sha256"] == EXPECTED_LIBRARY[name]
            for name, row in library.items()),
        "Link-94 trace-library authority drift",
    )
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "LINK94-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
        "attempt_accounting": {
            "product_links": 0,
            "media_builds": 1,
            "hardware_runs": 0,
        },
        "authority": {
            "product_card": bind(CARD_RECEIPT),
            "product_manifest": bind(LINK94.MANIFEST),
            "producer": bind(Path(__file__).resolve()),
            "live_REPL_FTP_crossing_gate": bind(CROSSING_RECEIPT),
        },
        "shared_system": {
            "manifest": bind(MANIFEST),
            "artifact_count": media["artifact_count"],
            "artifact_set_sha256": media["artifact_set_sha256"],
            "product_D81": bind(MEDIA.PRODUCT_D81),
            "work_D81": bind(MEDIA.WORK_D81),
            "readback": "passed",
        },
        "trace_library": {
            "source": "byte-identical-Link93-library-authority",
            "artifacts": library,
        },
        "hardware_handoff": {
            "status": "prepared-not-run",
            "trace_rows": 6,
            "physical_owner_keyboard": True,
            "persistent_by_default": True,
            "bundled_defstruct_sister": True,
        },
        "bundled_session": {
            "trace_contract": bind(SESSION_CONFIG),
            "trace_runner": bind(SESSION_SCRIPT),
            "trace_runner_base": bind(BASE_TRACE_SCRIPT),
            "defstruct_sister_receipt": bind(SISTER_RECEIPT),
            "defstruct_contract": bind(SISTER_CONFIG),
            "defstruct_runner": bind(SISTER_SCRIPT),
            "order": [
                "Link94-trace-acceptance",
                "Link92-defstruct-terminal-ingress-sister",
                "standing-trailing-peeks",
            ],
        },
        "claim_limit": (
            "Link-94 media and bundled-session preparation only; no hardware, "
            "release, publication, defstruct-result or public-surface claim."
        ),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "LINK94-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING"
        and value.get("attempt_accounting") == {
            "product_links": 0, "media_builds": 1, "hardware_runs": 0,
        }
        and value["shared_system"]["artifact_count"] == 19
        and value["shared_system"]["readback"] == "passed"
        and value["shared_system"]["artifact_set_sha256"]
            == EXPECTED_ARTIFACT_SET
        and value["shared_system"]["manifest"]["sha256"]
            == EXPECTED_MEDIA_MANIFEST
        and value["shared_system"]["product_D81"]["sha256"]
            == EXPECTED_PRODUCT_D81
        and value["shared_system"]["work_D81"]["sha256"]
            == EXPECTED_WORK_D81
        and all(
            value["trace_library"]["artifacts"][name]["sha256"] == digest
            for name, digest in EXPECTED_LIBRARY.items()
        )
        and value["hardware_handoff"] == {
            "status": "prepared-not-run",
            "trace_rows": 6,
            "physical_owner_keyboard": True,
            "persistent_by_default": True,
            "bundled_defstruct_sister": True,
        }
        and value["bundled_session"]["order"] == [
            "Link94-trace-acceptance",
            "Link92-defstruct-terminal-ingress-sister",
            "standing-trailing-peeks",
        ],
        "Link-94 media closure claim drift",
    )
    if verify:
        require(value == derive(), "Link-94 media closure receipt is stale")


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-link94-media-selftest:",
        "c2_top_level_macro_redispatch_link94_media.py selftest",
        "c2-link94-media-check:",
        "c2_top_level_macro_redispatch_link94_media.py check",
        "check-source: c2-link94-media-selftest",
    )), "Link-94 media gate wiring absent")


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-product-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "drop-role": lambda x: x["shared_system"].update(artifact_count=18),
        "skip-readback": lambda x: x["shared_system"].update(readback="skipped"),
        "replace-product": lambda x: x["shared_system"]["product_D81"].update(
            sha256="00" * 32),
        "replace-work": lambda x: x["shared_system"]["work_D81"].update(
            sha256="00" * 32),
        "replace-media-manifest": lambda x: x["shared_system"]["manifest"].update(
            sha256="00" * 32),
        "replace-library-D81": lambda x: x["trace_library"]["artifacts"][
            "lisp65-library.d81"].update(sha256="00" * 32),
        "replace-library-index": lambda x: x["trace_library"]["artifacts"][
            "l65index"].update(sha256="00" * 32),
        "replace-library-source": lambda x: x["trace_library"]["artifacts"][
            "inspect.l65s"].update(sha256="00" * 32),
        "swap-session-order": lambda x: x["bundled_session"]["order"].reverse(),
        "claim-session": lambda x: x["hardware_handoff"].update(status="passed"),
        "allow-virtual": lambda x: x["hardware_handoff"].update(
            physical_owner_keyboard=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except ClosureError:
            rejected.append(name)
    require(len(rejected) == len(cases), "Link-94 media mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-94 media closure is one-shot")
    configure()
    value = MEDIA.build()
    require(value["artifact_count"] == 19, "Link-94 media role count drift")
    copy_library()
    receipt = derive(configured=True)
    validate(receipt, verify=False)
    RECEIPT.write_bytes(canonical(receipt))
    print(
        "Link-94 media closure: PASS "
        f"roles={value['artifact_count']} "
        f"product={receipt['shared_system']['product_D81']['sha256']} "
        f"library={receipt['trace_library']['artifacts']['lisp65-library.d81']['sha256']}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "build":
        return build_action()
    if action == "record":
        value = derive()
        validate(value, verify=False)
        RECEIPT.write_bytes(canonical(value))
        print(f"Link-94 media closure: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    validate(value, verify=(action == "check"))
    count = len(rejected_mutations(value))
    print(f"Link-94 media {action}: PASS mutations={count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClosureError, MEDIA.MediaError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print(f"Link-94 media closure: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
