#!/usr/bin/env python3
"""Seal and verify the bounded r4 `$22` device result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RAW = ROOT / "build/c2.3/v2.0-symbol22-build-id-device-contact-r4"
MEDIA = ARCH / "c2.3-v2.0-symbol22-build-id-device-media-receipt.json"
SESSION = ROOT / "config/c2-v200-symbol22-build-id-device-session.json"
RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-build-id-device-result-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-build-id-device-result.md"
STATUS = "PASS: BOUNDED SYMBOL22 SEAM DID NOT RECUR ON R4"
EXPECTED_RAW = {
    "latch-state": ("latch-state.bin", 5, "0000000000",
        "8855508aade16ec573d21e6a485dfd0a7624085c1a14b5ecdd6485de0c6839a4"),
    "repl.buf-payload": ("repl-buf-payload.bin", 34,
        "286c6973742031203329005420312033299d0d000000000000000000000000000000",
        "44522eda85eab908126ea70cb86408223a388a327cfeb43b46e941cb0331ae15"),
    "nsym": ("nsym.bin", 2, "8202",
        "6d2fd7bfe1ecf41ec430787f4fbd2605d8a2961df1d6ead24385830ccd7f1341"),
    "npool": ("npool.bin", 2, "1022",
        "872a2533027ee09719ebc5f2121807102a6663afb5ebb62c47b2c60afe4b4be6"),
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def raw_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for name, (filename, size, hex_value, digest) in EXPECTED_RAW.items():
        path = RAW / filename
        identity = bind(path)
        raw = path.read_bytes()
        require(identity["bytes"] == size and raw.hex() == hex_value
                and identity["sha256"] == digest,
                f"raw-first device bytes drift: {name}")
        rows[name] = {**identity, "hex": hex_value}
    return rows


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "device result is one-shot")
    media, session = load(MEDIA), load(SESSION)
    rows = raw_rows()
    require(media["status"] == "PASS: V2.0 SYMBOL22 BUILD-ID DEVICE MEDIA READY"
            and session["status"] == "ready-owner-bounded-symbol22-contact"
            and media["session"] == bind(SESSION)
            and media["media"]["product"]["sha256"] ==
                "e20c161509f790aeecd1f6fa008e84bd2020f303a26500a41df49b9c980b0d0c"
            and media["media"]["library"]["sha256"] ==
                "b76883347454c6d1a7b864a23bbe5fb88487b4b370b42f9bf95d51bc94f11080",
            "device result media/session authority drift")
    state = bytes.fromhex(rows["latch-state"]["hex"])
    nsym = int.from_bytes(bytes.fromhex(rows["nsym"]["hex"]), "little")
    npool = int.from_bytes(bytes.fromhex(rows["npool"]["hex"]), "little")
    require(state == bytes(5) and nsym == 642 and npool == 8720,
            "bounded result does not select the tag-zero branch")
    value = {
        "format": "lisp65-c2-v200-symbol22-build-id-device-result-v1",
        "recorded_on": "2026-08-31", "status": STATUS,
        "authority": {"media": bind(MEDIA), "session": bind(SESSION),
                      "positive_control": session["positive_control"]},
        "contact": {
            "count": 1, "retries": 0, "CPU_stopped": True,
            "resume_after_read": False, "reset_after_read": False,
            "product_readback_sha256": media["media"]["product"]["sha256"],
            "library_readback_sha256": media["media"]["library"]["sha256"],
            "owner_observation": {
                "prompt_before_stimulus": "visible",
                "cursor_after_left": "on closing parenthesis",
                "submitted_result": "(1 3)",
                "visible_symbol22": False,
                "further_input_before_read": False,
            },
        },
        "raw_first": rows,
        "interpretation": {
            "tag": 0, "caller": 0, "name_pointer": 0,
            "payload_claim": "none-without-tag-last-commit",
            "nsym": nsym, "npool": npool,
            "decision_table_branch": "tag-zero-and-no-visible-symbol22",
            "result": "no-recurrence-in-one-bounded-historical-seam",
        },
        "claim_limit": {
            "accepts": ["one bounded seam did not reproduce symbol22"],
            "excludes": ["global exoneration", "Comfort return",
                         "Block-3 return", "repair", "release"],
        },
        "next": ("owner residual-risk decision with final-ELF-positive latch "
                 "retained; no automatic feature reopening"),
    }
    write(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    session = load(SESSION)
    require(value["status"] == STATUS
            and value["authority"]["media"] == bind(MEDIA)
            and value["authority"]["session"] == bind(SESSION)
            and value["authority"]["positive_control"] ==
                session["positive_control"]
            and value["interpretation"] == {
                "tag": 0, "caller": 0, "name_pointer": 0,
                "payload_claim": "none-without-tag-last-commit",
                "nsym": 642, "npool": 8720,
                "decision_table_branch": "tag-zero-and-no-visible-symbol22",
                "result": "no-recurrence-in-one-bounded-historical-seam"}
            and value["contact"]["count"] == 1
            and value["contact"]["retries"] == 0
            and value["contact"]["CPU_stopped"] is True
            and value["contact"]["resume_after_read"] is False,
            "persisted device-result semantics drift")
    for name, (_, size, hex_value, digest) in EXPECTED_RAW.items():
        row = value["raw_first"][name]
        require(row["bytes"] == size and row["hex"] == hex_value
                and row["sha256"] == digest,
                f"persisted raw-first row drift: {name}")
    report = REPORT.read_text(encoding="utf-8")
    for token in ("tag == 0", "`nsym` was 642", "`npool` was 8720",
                  "owner's residual-risk decision"):
        require(token in report, f"device-result report claim absent: {token}")
    print("v2.0 symbol22 build-ID device result: CHECK PASS "
          "branch=tag-zero contact=1")
    return value


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "record":
        record()
        check()
    elif action == "check":
        check()
    else:
        raise ResultError("usage: record|check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 symbol22 build-ID device result: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
