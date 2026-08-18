#!/usr/bin/env python3
"""Close the Link-95 trace session from its six bound screen captures."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-packed-callee-link95-world-bound-device-session.json"
MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-world-bound-media-closure-receipt.json"
)
OUT = ROOT / "build/c2.3/packed-callee-link95-world-bound-device-session"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-trace-hardware-result-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
FORMAT = "lisp65-c2.3-link95-trace-hardware-result-v1"
STATUS = "LINK95-TRACE-HARDWARE-GREEN; DEFSTRUCT-SISTER-PENDING"
ROW_IDS = (
    "require-inspect", "define-probe", "install-trace",
    "traced-call", "remove-trace", "restored-call",
)
MUTATIONS = (
    "drop-row", "wrong-restored-result", "allow-current-trace-enter",
    "allow-current-trace-exit", "reject-historical-trace-enter",
    "claim-second-contact", "claim-defstruct", "replace-product-readback",
    "replace-library-readback", "drop-same-world-authority",
)


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def row_evidence(row: dict[str, Any]) -> dict[str, Any]:
    row_id = row["id"]
    text = OUT / f"row-{row_id}.txt"
    image = OUT / f"row-{row_id}.png"
    SCREEN.check_fail_closed_frame(image)
    if "expect_ordered" in row:
        visible = SCREEN._latest_visible_results(text, row["form"])
        require(visible == row["expect_ordered"][:-1],
                f"{row_id}: ordered latest-segment oracle drift: {visible}")
    else:
        SCREEN.check_latest_result(text, row["form"], row["expect"][0])
        visible = SCREEN._latest_visible_results(text, row["form"])
    forbidden = row.get("forbid", [])
    if forbidden:
        SCREEN.check_latest_forbidden(text, row["form"], forbidden)
    return {
        "id": row_id,
        "form": row["form"],
        "quiet_floor_seconds": row["quiet_floor_seconds"],
        "latest_visible_results": visible,
        "forbidden_in_latest_segment": [],
        "screen_text": bind(text),
        "screen_image": bind(image),
        "result": "passed",
    }


def derive() -> dict[str, Any]:
    config = load(CONFIG)
    media = load(MEDIA_RECEIPT)
    require(
        config.get("status") == "prepared-not-run"
        and [row["id"] for row in config["rows"]] == list(ROW_IDS),
        "Link-95 trace session contract drift",
    )
    require(media.get("status")
            == "LINK95-WORLD-BOUND-MEDIA-GREEN; HARDWARE-RECONTACT-READY",
            "same-world media authority is not green")
    rows = [row_evidence(row) for row in config["rows"]]
    product_source = ROOT / config["identity"]["product_medium"]
    library_source = ROOT / config["identity"]["library_medium"]
    product_readback = OUT / "product-readback.d81"
    library_readback = OUT / "library-readback.d81"
    require(product_source.read_bytes() == product_readback.read_bytes(),
            "product D81 readback mismatch")
    require(library_source.read_bytes() == library_readback.read_bytes(),
            "library D81 readback mismatch")
    restored = rows[-1]
    require(
        restored["latest_visible_results"] == ["5"]
        and restored["forbidden_in_latest_segment"] == [],
        "restored function-cell postcondition drift",
    )
    historical = (OUT / "row-restored-call.txt").read_text(encoding="utf-8")
    require(
        "trace-enter" in historical and "trace-exit" in historical,
        "whole-screen First Red no longer reproduces",
    )
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-10",
        "status": STATUS,
        "authority": {
            "same_world_media": bind(MEDIA_RECEIPT),
            "session_contract": bind(CONFIG),
            "result_checker": bind(Path(__file__).resolve()),
            "screen_checker": bind(ROOT / "tools/host-lisp/repl_screen_check.py"),
        },
        "media_readback": {
            "product_source": bind(product_source),
            "product_readback": bind(product_readback),
            "library_source": bind(library_source),
            "library_readback": bind(library_readback),
            "result": "byteidentical",
        },
        "rows": rows,
        "restoration": {
            "original_BCODE_restored": True,
            "result": "5",
            "trace_output_after_final_form": False,
        },
        "harness_first_red": {
            "classification": "whole-screen-negative-assert",
            "mechanism": (
                "The shell grep searched the full 25-row screen and found "
                "trace output belonging to the earlier intentionally traced "
                "call. The latest restored-call segment contains only 5."
            ),
            "product_result_affected": False,
            "replay_source": "same-bound-capture",
            "additional_device_accesses": 0,
        },
        "execution_accounting": {
            "hardware_contacts": 1,
            "physical_forms": 6,
            "replay_device_accesses": 0,
            "defstruct_forms": 0,
        },
        "mutation_contract": list(MUTATIONS),
        "next": "authorized-defstruct-terminal-ingress-sister",
        "claim_limit": (
            "Link-95 inspect/trace/untrace hardware acceptance only. "
            "The defstruct sister, trailing peeks, release and v1.5 scope "
            "remain unclaimed."
        ),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and [row["id"] for row in value["rows"]] == list(ROW_IDS)
        and all(row["result"] == "passed" for row in value["rows"])
        and value["restoration"] == {
            "original_BCODE_restored": True,
            "result": "5",
            "trace_output_after_final_form": False,
        }
        and value["rows"][-1]["forbidden_in_latest_segment"] == []
        and value["harness_first_red"]["classification"]
            == "whole-screen-negative-assert"
        and value["harness_first_red"]["product_result_affected"] is False
        and value["harness_first_red"]["replay_source"] == "same-bound-capture"
        and value["harness_first_red"]["additional_device_accesses"] == 0
        and value["media_readback"]["result"] == "byteidentical"
        and value["media_readback"]["product_source"]["sha256"]
            == value["media_readback"]["product_readback"]["sha256"]
        and value["media_readback"]["library_source"]["sha256"]
            == value["media_readback"]["library_readback"]["sha256"]
        and value["execution_accounting"] == {
            "hardware_contacts": 1, "physical_forms": 6,
            "replay_device_accesses": 0, "defstruct_forms": 0,
        }
        and value["mutation_contract"] == list(MUTATIONS)
        and value["next"] == "authorized-defstruct-terminal-ingress-sister",
        "Link-95 trace hardware-result claim drift",
    )
    if verify:
        require(value == derive(), "Link-95 trace hardware result is stale")


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-row": lambda x: x["rows"].pop(),
        "wrong-restored-result": lambda x: x["restoration"].update(result="4"),
        "allow-current-trace-enter": lambda x: x["restoration"].update(
            trace_output_after_final_form=True),
        "allow-current-trace-exit": lambda x: x["rows"][-1][
            "forbidden_in_latest_segment"].append("trace-exit"),
        "reject-historical-trace-enter": lambda x: x[
            "harness_first_red"].update(classification="product-trace-leak"),
        "claim-second-contact": lambda x: x["execution_accounting"].update(
            hardware_contacts=2),
        "claim-defstruct": lambda x: x["execution_accounting"].update(
            defstruct_forms=2),
        "replace-product-readback": lambda x: x["media_readback"][
            "product_readback"].update(sha256="00" * 32),
        "replace-library-readback": lambda x: x["media_readback"][
            "library_readback"].update(sha256="00" * 32),
        "drop-same-world-authority": lambda x: x.update(
            next="unbound-media-world"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except ResultError:
            rejected.append(name)
    require(rejected == list(MUTATIONS), "trace-result mutation survived")
    return rejected


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-link95-trace-result-selftest:",
        "c2_link95_trace_hardware_result.py selftest",
        "c2-link95-trace-result-check:",
        "c2_link95_trace_hardware_result.py check",
        "check-source: c2-link95-trace-result-selftest",
    )), "Link-95 trace-result gate wiring absent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        validate(value, verify=False)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        (OUT / "row-restored-call-passed").touch()
        (OUT / "rows-complete").touch()
        (OUT / "next-row").write_text("COMPLETE\n", encoding="ascii")
        print(f"Link-95 trace result: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    validate(value, verify=(action == "check"))
    rejected = rejected_mutations(value)
    print(f"Link-95 trace result {action}: PASS rows=6 mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, SCREEN.CheckError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"Link-95 trace result: FIRST RED: {message}", file=sys.stderr)
        raise SystemExit(2)
