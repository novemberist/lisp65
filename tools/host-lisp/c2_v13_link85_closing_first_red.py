#!/usr/bin/env python3
"""Bind the Link-85 closing contact without laundering its Ship input row."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402


RUN = ROOT / "build/ship-builder/v13/link85-closing-device-session/run"
DEPLOYMENT = ROOT / "build/ship-builder/v13/link85-closing-device-session/deployment.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-preparation-receipt.json"
)
HOST = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-domain-host-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-first-red-receipt.json"
)


class EvidenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EvidenceError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    row: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def latest_result(path: Path, form: str, expected: str) -> None:
    SCREEN.check_latest_result(
        path, form, expected, allow_editor_status_tail=True)


def main() -> int:
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    host = load(HOST)
    require(
        preparation["status"] == "prepared-1-ship-samples-link85-D3-D4"
        and host["status"]
            == "passed-full-reset-domain-gate-link85-and-closing-preparation"
        and deployment["D3"]["link"] == 85,
        "Link-85 authority drift",
    )

    quiet = (RUN / "editor-quiet-end.txt").read_text(
        encoding="utf-8", errors="replace")
    retained = max((len(value) for value in re.findall(r"a+", quiet)), default=0)
    stopped = (RUN / "editor-stopped.txt").read_text(
        encoding="utf-8", errors="replace")
    private_query = (RUN / "editor-query.txt").read_text(
        encoding="utf-8", errors="replace")
    require(
        retained == 30
        and "*** stopped (run/stop)" in stopped
        and "lisp65>" in stopped
        and "*** undefined function: %ide-buffers-find" in private_query,
        "D3 screen evidence drift",
    )
    latest_result(RUN / "editor-post-stop.txt", "(+ 4 5)", "9")
    for name in ("editor-quiet-end", "editor-stopped", "editor-post-stop"):
        SCREEN.check_fail_closed_frame(RUN / f"{name}.png")

    for row in deployment["D4"]:
        expected = "0 3" if row["id"] == "standing-time" else row["expected"]
        latest_result(RUN / f"{row['id']}.txt", row["form"], expected)
        SCREEN.check_fail_closed_frame(RUN / f"{row['id']}.png")

    ship = deployment["D1"][0]
    require(ship["id"] == "ship-interactive", "unexpected Link-85 Ship row")
    state_address = int(ship["addresses"]["lisp65_runtime_state"], 16)
    raw = (RUN / "ship-interactive-result.bin").read_bytes()
    require(
        raw == bytes.fromhex("02000000")
        and (RUN / "ship-interactive-runtime-state.bin").read_bytes() == b"\x02",
        "interactive Ship stopped-state drift",
    )
    require(
        (ROOT / ship["image"]["path"]).read_bytes()
        == (RUN / "ship-interactive-package-readback.d81").read_bytes(),
        "interactive Ship medium readback drift",
    )

    d3_medium = Path(deployment["D3"]["package_medium"]["path"])
    d4_medium = Path(deployment["D3"]["library_medium"]["path"])
    require(
        (ROOT / d3_medium).read_bytes()
        == (RUN / "D3-retry-package-readback.d81").read_bytes()
        and (ROOT / d4_medium).read_bytes()
        == (RUN / "D4-package-readback.d81").read_bytes(),
        "candidate media readback drift",
    )

    result = {
        "format": "lisp65-c2.3-v1.3-link85-closing-device-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED-Link85-interactive-Ship-input-harness-owner-review",
        "candidate_link": 85,
        "product_links_created_after_contact": 0,
        "product_bytes_changed_after_contact": 0,
        "release_ready": False,
        "reset_domain_fix": {
            "status": "passed-on-target",
            "D3_retained_keys": retained,
            "run_stop": "returned-live-REPL",
            "post_stop_result": "9",
            "claim": (
                "The full-domain restage removed the stale-C2J post-RUN/STOP "
                "failure: the same product identity evaluated (+ 4 5) after "
                "the abort. No READY shortcut exists."
            ),
            "screens": {
                "quiet": bind(RUN / "editor-quiet-end.png"),
                "stopped": bind(RUN / "editor-stopped.png"),
                "post_stop": bind(RUN / "editor-post-stop.png"),
            },
        },
        "D4": {
            "status": "passed-require-q-time",
            "rows": [row["id"] for row in deployment["D4"]],
            "screens": {
                row["id"]: bind(RUN / f"{row['id']}.png")
                for row in deployment["D4"]
            },
        },
        "tool_first_red": {
            "row": "ship-interactive",
            "classification": "unacknowledged-multi-character-input-transport",
            "observed_state_and_result": raw.hex(),
            "state_interpretation": "entry-running; no completed result",
            "mechanism_boundary": (
                "The runner waited for runtime state 2, then sent Ada<RETURN> "
                "as one virtual-keyboard invocation. This violates the already "
                "bound harness fact that unacknowledged multi-character "
                "submissions are not lossless. The row therefore cannot "
                "distinguish input loss from a product read-line failure."
            ),
            "required_discriminator": (
                "one character per invocation with an acknowledgement boundary; "
                "no product or media change"
            ),
            "result": bind(RUN / "ship-interactive-result.bin", state_address),
            "screen": bind(RUN / "ship-interactive.png"),
            "medium_readback": bind(
                RUN / "ship-interactive-package-readback.d81"),
            "prior_transport_authority": bind(
                ROOT / "docs/planning/c2.2-v1.2.6-editor-option1-contact-review.md"),
        },
        "harness_note": {
            "private_query": (
                "%ide-buffers-find is a compiler-owned private helper, not a "
                "public callable directory entry. Its undefined result cannot "
                "be used as D3 acceptance; the commissioned public liveness "
                "witness (+ 4 5) passed."
            ),
            "screen": bind(RUN / "editor-query.png"),
            "time_result": (
                "The standing-time config retained the plain form result 3; "
                "the public renderer contract emits the measured frame count "
                "and value together, here 0 3. The target row is green."
            ),
        },
        "scope": {
            "prior_media_gap": "class-wide-internal-media-only",
            "field_exposure": "zero-v1.3-first-advertised-release-still-closed",
            "next_gate": (
                "Owner disposition of one corrected interactive-only hardware "
                "row before Halt #2; Link 85 and all passed rows stay fixed."
            ),
        },
        "bindings": {
            "host": bind(HOST),
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "executed_driver": bind(ROOT / "scripts/c2-v13-closing-device.py"),
            "executed_wrapper": bind(ROOT / "scripts/c2-v13-link85-closing-device.py"),
            "executed_session": bind(ROOT / "scripts/c2-v13-closing-hw.sh"),
            "executed_session_wrapper": bind(ROOT / "scripts/c2-v13-link85-closing-hw.sh"),
        },
        "claim_limit": (
            "This receipt claims the Link-85 full reset-domain repair, D3 "
            "post-abort liveness and all D4 rows. It does not claim the "
            "interactive Ship input row and makes no acceptance or release claim."
        ),
    }
    RECEIPT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "c2-v13-link85-closing-first-red: RECORDED "
        "D3=pass D4=3/3 ship-interactive=unclaimed-tool-first-red"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, SCREEN.CheckError, OSError, ValueError, KeyError) as error:
        print(f"c2-v13-link85-closing-first-red: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
