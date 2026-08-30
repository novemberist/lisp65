#!/usr/bin/env python3
"""Qualify the physical-REPL WYSIWYG input boundary.

The product change is deliberately local to ``read_line``.  PETSCII shifted
Space ($A0) becomes ASCII Space before echo/storage, while an otherwise
unhandled control byte raises the existing visible reader error.  Stored
files, media bytes, and the canonical reader are not rewritten.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_name_freight_d2_badopcode_capture as CAPTURE  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
REPL = ROOT / "src/repl.c"
READER = ROOT / "src/reader.c"
SCREEN = ROOT / "src/screen.c"
ORIGIN = ARCH / "c2.3-v2.1-a0-origin-attribution-receipt.json"
PRIOR = ARCH / "c2.3-v2.1-reader-caller-path-attribution-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
AUTHORIZATION = "01914313"
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-input-v1"
STATUS = "PASS: A0-TO-SPACE; UNMAPPABLE-CONTROLS-VISIBLE; TWO-CAPTURES-CANONICAL"
RECORDED_ON = "2026-08-17"
CANONICAL_CODE = "b50100020500000b01010205"
SEAL_ERA_COMMIT = "ea1f8377150e9ef9345e4afe06211e0b1286ad95"
SEALED_MUTATIONS = [
    "normalize-after-echo", "normalize-after-store", "accept-invisible-a0",
    "silent-control-drop", "wrong-visible-error", "miss-one-control",
    "link112-poison-object", "link113-poison-object", "noncanonical-size",
    "change-reader-rules", "change-stored-files", "change-media",
    "add-product-source", "authorize-two-cards",
    "consume-card-in-preflight", "device-contact-in-preflight",
    "erase-device-byte-type",
]


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in (
        "the wysiwyg card is released",
        "$a0 → $20",
        "unmappable controls reject visibly",
        "canonical 12-byte object",
        "one product card",
    ):
        require(token in text, f"authorization token absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def normalize_device_line(raw: bytes) -> tuple[bytes, list[int]]:
    """Model the authorized ordinary-byte portion of DEVICE_KB read_line."""
    out = bytearray()
    rejected: list[int] = []
    for value in raw:
        if value == 0xA0:
            value = 0x20
        elif value < 0x20 or 0x80 <= value < 0xA0:
            rejected.append(value)
            continue
        if 0x41 <= value <= 0x5A:
            value += 0x20
        elif 0xC1 <= value <= 0xDA:
            value -= 0x80
        out.append(value)
    return bytes(out), rejected


def source_contract(repl: str) -> dict[str, Any]:
    for token in (
        "#ifdef DEVICE_KB\n    uint8_t c;\n#else\n    int c;\n#endif",
        "if ((c & 0x7F) < 0x20) {",
        "} else if (n < max - 1) {",
        "if (c == 0xA0) c = ' ';",
        "lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);",
        "buf[n++] = (char)c;",
    ):
        require(token in repl, f"WYSIWYG input source seam absent: {token}")
    require(
        repl.index("if ((c & 0x7F) < 0x20) {")
        < repl.index("lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);")
        < repl.index("if (c == 0xA0) c = ' ';")
        < repl.index("echo_char((char)c);")
        < repl.index("buf[n++] = (char)c;"),
        "normalization no longer precedes echo and storage")
    return {
        "site": "src/repl.c:read_line DEVICE_KB ordinary-byte boundary",
        "a0_normalized_before_echo": True,
        "a0_normalized_before_store": True,
        "unhandled_controls": "lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN)",
        "device_code_type": "uint8_t",
        "host_EOF_type": "int",
        "stored_file_reader_changed": False,
        "media_format_changed": False,
    }


def derive() -> dict[str, Any]:
    origin, prior = load(ORIGIN), load(PRIOR)
    require(origin["status"].startswith("ATTRIBUTED: SHIFTED-TABLE-SPACE")
            and origin["attribution"]["observed_a0_is_semantic_whitespace"]
            is True
            and prior["status"] == "ATTRIBUTED: INVISIBLE-PETSCII-A0-INGRESS",
            "input-origin authority drift")
    reader_binding = ERA.era_bind(SEAL_ERA_COMMIT, READER)
    screen_binding = ERA.era_bind(SEAL_ERA_COMMIT, SCREEN)
    require(reader_binding["sha256"] == prior["authority"]["reader"]["sha256"]
            and screen_binding["sha256"] == prior["authority"]["screen"]["sha256"],
            "reader/screen changed outside the input-boundary scope")
    source = source_contract(
        ERA.era_blob(SEAL_ERA_COMMIT, REPL.relative_to(ROOT).as_posix())
        .decode("utf-8"))
    fixtures: dict[str, Any] = {}
    for name, row in origin["captured_buffers"].items():
        raw = bytes.fromhex(row["line_hex"])
        normalized, rejected = normalize_device_line(raw)
        require(rejected == [] and b"\xA0" not in normalized
                and normalized.decode("ascii") == row["visible_ascii"],
                f"{name} did not normalize to its visible line")
        compiled = CAPTURE.host_compile(normalized.decode("ascii"))
        require(compiled["encoded_hex"] == CANONICAL_CODE
                and compiled["literal_count"] == 0
                and len(bytes.fromhex(compiled["encoded_hex"])) == 12,
                f"{name} did not compile to the canonical object")
        fixtures[name] = {
            "captured_hex": raw.hex(),
            "a0_offset_zero_based": row["a0_offset_zero_based"],
            "normalized_ascii": normalized.decode("ascii"),
            "normalized_hex": normalized.hex(),
            "compile": compiled,
            "canonical_object_bytes": 12,
        }
    controls = bytes((0x01, 0x10, 0x80, 0x91, 0x9F))
    normalized, rejected = normalize_device_line(controls)
    require(normalized == b"" and rejected == list(controls),
            "unhandled-control rejection model drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "contract": source,
        "historical_regressions": fixtures,
        "control_rejection": {
            "sample_hex": controls.hex(),
            "rejected_hex": bytes(rejected).hex(),
            "visible_error_code": "LISP65_ERR_READER_INVALID_TOKEN",
            "silent_drop_allowed": False,
        },
        "scope": {
            "product_source_delta": ["src/repl.c"],
            "reader_rules_unchanged": True,
            "stored_files_unchanged": True,
            "media_bytes_unchanged_by_this_gate": True,
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "device_contacts": 0,
        },
        "authority": {
            "owner": git_authority(), "origin": bind(ORIGIN),
            "prior_attribution": bind(PRIOR),
            "repl": ERA.era_bind(SEAL_ERA_COMMIT, REPL),
            "reader": reader_binding, "screen": screen_binding,
            "checker": ERA.era_bind(SEAL_ERA_COMMIT, Path(__file__)),
        },
        "claim_limit": (
            "Host qualification of the physical input boundary only. No WPLTO, "
            "product link, media build, device contact, or D2 claim."),
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "WYSIWYG receipt identity drift")
    require(value["authority"]["repl"] ==
            ERA.era_bind(SEAL_ERA_COMMIT, REPL)
            and value["authority"]["checker"] ==
            ERA.era_bind(SEAL_ERA_COMMIT, Path(__file__))
            and value["authority"]["reader"] ==
            ERA.era_bind(SEAL_ERA_COMMIT, READER)
            and value["authority"]["screen"] ==
            ERA.era_bind(SEAL_ERA_COMMIT, SCREEN),
            "WYSIWYG authority escaped its sealing era")
    contract = value["contract"]
    require(contract["a0_normalized_before_echo"] is True
            and contract["a0_normalized_before_store"] is True
            and contract["unhandled_controls"]
                == "lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN)"
            and contract["device_code_type"] == "uint8_t"
            and contract["host_EOF_type"] == "int"
            and contract["stored_file_reader_changed"] is False
            and contract["media_format_changed"] is False,
            "input-boundary contract drift")
    rows = value["historical_regressions"]
    require(set(rows) == {"Link112", "Link113"}
            and all(row["compile"]["encoded_hex"] == CANONICAL_CODE
                    and row["compile"]["literal_count"] == 0
                    and row["canonical_object_bytes"] == 12
                    and 0xA0 not in bytes.fromhex(row["normalized_hex"])
                    for row in rows.values()),
            "historical canonical-object regression drift")
    control = value["control_rejection"]
    require(control["rejected_hex"] == control["sample_hex"]
            and control["visible_error_code"]
                == "LISP65_ERR_READER_INVALID_TOKEN"
            and control["silent_drop_allowed"] is False,
            "visible control rejection drift")
    scope = value["scope"]
    require(scope["product_source_delta"] == ["src/repl.c"]
            and scope["reader_rules_unchanged"] is True
            and scope["stored_files_unchanged"] is True
            and scope["media_bytes_unchanged_by_this_gate"] is True
            and scope["product_cards_authorized"] == 1
            and scope["product_cards_consumed"] == 0
            and scope["device_contacts"] == 0,
            "WYSIWYG scope/card boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "normalize-after-echo": lambda x: x["contract"].update(
            a0_normalized_before_echo=False),
        "normalize-after-store": lambda x: x["contract"].update(
            a0_normalized_before_store=False),
        "accept-invisible-a0": lambda x: x["historical_regressions"]
            ["Link112"].update(normalized_hex=x["historical_regressions"]
                ["Link112"]["captured_hex"]),
        "silent-control-drop": lambda x: x["control_rejection"].update(
            silent_drop_allowed=True),
        "wrong-visible-error": lambda x: x["control_rejection"].update(
            visible_error_code="none"),
        "miss-one-control": lambda x: x["control_rejection"].update(
            rejected_hex="011080919e"),
        "link112-poison-object": lambda x: x["historical_regressions"]
            ["Link112"]["compile"].update(
                encoded_hex="b50100020b00010c0006003d13013b0b01010205"),
        "link113-poison-object": lambda x: x["historical_regressions"]
            ["Link113"]["compile"].update(literal_count=1),
        "noncanonical-size": lambda x: x["historical_regressions"]
            ["Link113"].update(canonical_object_bytes=20),
        "change-reader-rules": lambda x: x["scope"].update(
            reader_rules_unchanged=False),
        "change-stored-files": lambda x: x["scope"].update(
            stored_files_unchanged=False),
        "change-media": lambda x: x["scope"].update(
            media_bytes_unchanged_by_this_gate=False),
        "add-product-source": lambda x: x["scope"]["product_source_delta"].append(
            "src/reader.c"),
        "authorize-two-cards": lambda x: x["scope"].update(
            product_cards_authorized=2),
        "consume-card-in-preflight": lambda x: x["scope"].update(
            product_cards_consumed=1),
        "device-contact-in-preflight": lambda x: x["scope"].update(
            device_contacts=1),
        "erase-device-byte-type": lambda x: x["contract"].update(
            device_code_type="int"),
        "collapse-era-to-live": lambda x: x["authority"].update(
            repl=bind(REPL)),
        "restore-working-tree-binding": lambda x: x["authority"].update(
            checker=bind(Path(__file__))),
        "corrupt-era-reader-binding": lambda x: x["authority"]["reader"].update(
            sha256="0" * 64),
        "restore-live-screen-binding": lambda x: x["authority"].update(
            screen=bind(SCREEN)),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except GateError:
            rejected.append(name)
    require(rejected == list(cases), "WYSIWYG mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    rejected = mutations(value)
    if action == "record":
        value["mutations_rejected"] = rejected
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        historical = load(RECEIPT)
        sealed_rejected = historical.pop("mutations_rejected", None)
        require(historical == value and sealed_rejected == SEALED_MUTATIONS
                and len(rejected) == 21,
                "WYSIWYG input receipt stale")
    else:
        require(len(rejected) == 21,
                "mutation count drift")
    print("WYSIWYG input: PASS "
          f"action={action} fixtures=2 canonical-bytes=12 "
          f"mutations=17+4")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError, UnicodeDecodeError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"WYSIWYG input: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
