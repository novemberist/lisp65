#!/usr/bin/env python3
"""Loudly widen the D1/E25 decoder call-site check to its successor block form.

Class-1 successor to c2_v20_map_tuple_d1_e25_rebind_20260814.py.

The 2026-08-14 tool rebinds only `authority.runtime.{bytes,sha256}` between
the historical D1/E25 first-red receipt and a freshly-derived live snapshot,
by calling straight through to `c2_v20_map_tuple_d1_e25.derive()`. That
`derive()` pins the boot decoder call site in src/c2_product_runtime.c as
the *literal* one line:

    if (!c2_decode_from(&c2_runtime, 0u)) return 0;

Commit 227e59e9 ("Export publication over the boot-time name index: ...")
turned that line into a block: on decoder failure, boot now invalidates the
boot-time name index (behind `#ifdef LISP65_C2_BOOT_NAME_INDEX`) before
returning 0, because the index's owner window otherwise stays valid past
the decoder for the export publication that follows it to resolve over.
The publication call site (`if (!c2_publish_exports_from(0))`) is untouched.
This is a source-*form* change with the decoder/publication split fully
intact, not semantic drift -- but the 2026-08-14 tool's hardcoded literal
match cannot see that, so its `selftest`/`check` (and the base tool's own
`selftest`) go red as "decoder/publication split drift".

Neither the base tool (c2_v20_map_tuple_d1_e25.py) nor the 2026-08-14
rebind may be edited: both are era-bound predecessors this tool re-verifies
by sha256 on every run, unchanged. This tool instead re-implements the
D1/E25 derivation with a widened decoder-site classifier that accepts
EXACTLY two forms at that call site -- the historical one-liner, or the
block whose only addition is the feature-guarded
`c2_boot_name_index_invalidate();` call -- and rejects everything else
(extra statements, a missing `#ifdef` guard, a missing publication call, a
missing decoder call) as drift, the same way the base tool's single literal
string used to.

mk/gates.mk's `c2-v20-map-tuple-d1-e25-selftest` and
`c2-v20-map-tuple-d1-e25-check` targets are retargeted here (see their
comments); the base tool and the 2026-08-14 receipt/tool are otherwise
untouched and this tool re-validates the 2026-08-14 receipt's bytes and the
base tool's own `verify()` every run.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_map_tuple_d1_e25 as E25  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREDECESSOR = ARCH / "c2.3-v2.0-map-tuple-d1-e25-rebind-2026-08-14.json"
RECEIPT = ARCH / "c2.3-v2.0-map-tuple-d1-e25-rebind-2026-09-22.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b3f6adc2"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RUNTIME_AUTHORITY_COMMIT = "227e59e9"
FEATURE = "LISP65_C2_BOOT_NAME_INDEX"
SITE_PREFIX = "if (!c2_decode_from(&c2_runtime, 0u))"
PUBLISH_LINE = "if (!c2_publish_exports_from(0))"
BLOCK_LINES = (
    f"#ifdef {FEATURE}",
    "c2_boot_name_index_invalidate();",
    "#endif",
    "return 0;",
)
ALLOWED = ("authority.runtime.bytes", "authority.runtime.sha256")
SEALED_MUTATIONS = [
    "rewrite-history", "change-claims", "widen-fields", "collapse-split",
    "drop-predecessor-binding", "escape-cause-authority",
    "corrupt-rebind-driver",
]
FORM_CASES: dict[str, tuple[str, bool]] = {
    "historical-one-liner": (
        "before\n    " + SITE_PREFIX + " return 0;\n    after\n", True),
    "current-block": (
        "before\n    " + SITE_PREFIX + " {\n"
        f"#ifdef {FEATURE}\n"
        "        /* Phases 11 and 12 run after the collecting/resolving "
        "window. */\n"
        "        c2_boot_name_index_invalidate();\n"
        "#endif\n"
        "        return 0;\n    }\n    after\n", True),
    "block-extra-statement": (
        "before\n    " + SITE_PREFIX + " {\n"
        f"#ifdef {FEATURE}\n"
        "        c2_boot_name_index_invalidate();\n"
        "        extra_call();\n"
        "#endif\n"
        "        return 0;\n    }\n    after\n", False),
    "block-missing-ifdef-guard": (
        "before\n    " + SITE_PREFIX + " {\n"
        "        c2_boot_name_index_invalidate();\n"
        "        return 0;\n    }\n    after\n", False),
    "decoder-call-removed": (
        "before\n    after\n", False),
}


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


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


def _significant_lines(body: str) -> list[str]:
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//[^\n]*", "", stripped)
    return [line.strip() for line in stripped.splitlines() if line.strip()]


def classify_decoder_site(text: str) -> str:
    """Return 'historical' or 'current' for the boot decoder call site.

    Exactly two forms are accepted: the historical single line, or the
    block whose only non-comment content is the feature-guarded
    `c2_boot_name_index_invalidate();` call. Anything else -- an extra
    statement, a missing `#ifdef` guard, or no call site at all -- raises.
    """
    require(text.count(SITE_PREFIX) == 1, "decoder call site not unique")
    start = text.index(SITE_PREFIX)
    one_liner = SITE_PREFIX + " return 0;"
    if text[start:start + len(one_liner)] == one_liner:
        return "historical"
    block_open = SITE_PREFIX + " {\n"
    require(text[start:start + len(block_open)] == block_open,
            "decoder call site form unrecognized")
    require("\n    }\n" in text[start:], "decoder call site block unterminated")
    close_at = text.index("\n    }\n", start)
    body = text[start + len(block_open):close_at]
    require(tuple(_significant_lines(body)) == BLOCK_LINES,
            "decoder call site block form drift")
    return "current"


def check_form_matrix() -> list[str]:
    passed: list[str] = []
    for name, (text, should_pass) in FORM_CASES.items():
        try:
            classify_decoder_site(text)
        except RebindError:
            ok = False
        else:
            ok = True
        require(ok == should_pass, f"decoder-site form matrix drift: {name}")
        passed.append(name)
    return passed


def derive_current() -> dict[str, Any]:
    """Re-run c2_v20_map_tuple_d1_e25.derive() with a widened site check.

    Identical to the base tool's derive() in every respect except the one
    hardcoded literal-string require for the decoder call site, which is
    replaced by classify_decoder_site() accepting either sanctioned form.
    """
    session = E25.load(E25.SESSION)
    row = E25.load(E25.ROW)
    elf = E25.bind(E25.ELF)
    product = E25.bind(E25.PRODUCT)
    library = E25.bind(E25.LIBRARY)
    screen = E25.bind(E25.SCREEN)
    screen_text = E25.bind(E25.SCREEN_TEXT)
    product_readback = E25.bind(E25.PRODUCT_READBACK)
    library_readback = E25.bind(E25.LIBRARY_READBACK)
    require(elf["sha256"] == E25.ELF_SHA256, "candidate ELF identity drift")
    require(product["sha256"] == E25.PRODUCT_SHA256
            and product_readback["sha256"] == E25.PRODUCT_SHA256,
            "product medium/readback identity drift")
    require(library["sha256"] == E25.LIBRARY_SHA256
            and library_readback["sha256"] == E25.LIBRARY_SHA256,
            "library medium/readback identity drift")
    require(screen["sha256"] == E25.SCREEN_SHA256, "screen identity drift")
    require(screen_text["sha256"] == E25.TEXT_SHA256,
            "screen-text identity drift")
    visible = E25.SCREEN_TEXT.read_text(encoding="utf-8")
    require("E25" in visible and "lisp65>" not in visible,
            "E25/no-prompt screen classification drift")
    require(session["D2_D5_open"] is False,
            "D2-D5 must remain closed after D1 red")
    require(row["status"] == "host-specified-owner-authorization-pending",
            "capture row must not self-authorize device access")
    symbols = E25.elf_symbols()
    runtime = E25.RUNTIME.read_text(encoding="utf-8")
    main = E25.MAIN.read_text(encoding="utf-8")
    errors = E25.ERRORS.read_text(encoding="utf-8")
    layout = E25.LAYOUT.read_text(encoding="utf-8")
    require("LISP65_ERR_STDLIB_PROFILED_PRELOAD = 37" in errors,
            "E25 enum binding absent")
    require("if (!c2_product_boot())" in main
            and '"c2: invalid product image"' in main,
            "E25 c2_product_boot call-site binding absent")
    classify_decoder_site(runtime)  # raises on drift; form recorded separately
    require(PUBLISH_LINE in runtime, "decoder/publication split drift")
    require("uint8_t phase;" in layout and "uint8_t finished;" in layout
            and "uint8_t error;" in layout and "uint8_t reserved;" in layout,
            "c2_stream_context terminal layout drift")
    return {
        "format": E25.FORMAT,
        "recorded_on": "2026-08-13",
        "status": "D1-FIRST-RED-E25; SUBMECHANISM-UNDECIDED",
        "artifacts": {
            "candidate_ELF": elf,
            "product_D81": product,
            "product_D81_readback": product_readback,
            "library_D81": library,
            "library_D81_readback": library_readback,
            "screen": screen,
            "screen_text": screen_text,
        },
        "owner_observation": {
            "liveness_lines": ["LISP65: STAGING MEDIA",
                               "LISP65: BUILDING HEAP",
                               "LISP65: LOADING LIBRARIES"],
            "terminal": {"frame": "red", "background": "blue",
                         "text": "E25", "prompt_visible": False},
            "provenance": "owner physical observation; E25/no-prompt independently screen-bound",
        },
        "classification": {
            "error_code": {"hex": "0x25", "decimal": 37,
                           "name": "LISP65_ERR_STDLIB_PROFILED_PRELOAD"},
            "bound_call": "c2_product_boot",
            "excluded_before_libraries_liveness": [
                "KERNAL ownership rejection", "c2_product_prepare_boot rejection",
                "runtime-island installation rejection"],
            "remaining_split": ["c2_decode_from", "c2_publish_exports_from"],
            "claim_limit": "E25 proves c2_product_boot returned non-OK after decoder entry; it does not yet identify decoder versus export publication.",
        },
        "elf_state": {
            "symbols": {name: f"0x{address:04x}" for name, address in symbols.items()},
            "c2_runtime_bytes": 46,
            "terminal_offsets": {"phase": "0xc0ae", "finished": "0xc0af",
                                 "error": "0xc0b0", "reserved": "0xc0b1"},
            "successful_decode_tuple": {"phase": 13, "finished": 1, "error": 0},
        },
        "capture": row,
        "authority": {
            "device_session": E25.bind(E25.SESSION), "capture_row": E25.bind(E25.ROW),
            "main": E25.bind(E25.MAIN), "error_codes": E25.bind(E25.ERRORS),
            "runtime": E25.bind(E25.RUNTIME), "runtime_layout": E25.bind(E25.LAYOUT),
            "driver": E25.bind(E25.DRIVER),
        },
        "next": "Owner authorization for the single stopped-state discriminator row; no repeat boot is needed while the state remains available.",
    }


def changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        result: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                result.append(child)
            else:
                result.extend(changed_paths(old[key], new[key], child))
        return result
    return [] if old == new else [prefix]


def remove_path(value: dict[str, Any], path: str) -> None:
    parts = path.split("."); cursor: Any = value
    for part in parts[:-1]:
        cursor = cursor[part]
    del cursor[parts[-1]]


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("map-tuple fixture red" in text and "full closure" in text,
            "D1/E25 closure rebind authority absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def runtime_cause() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{RUNTIME_AUTHORITY_COMMIT}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s", full], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    stat = subprocess.run(
        ["git", "show", "--stat", "--format=", full], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    runtime_name = E25.RUNTIME.relative_to(ROOT).as_posix()
    require("export publication" in subject.lower()
            and runtime_name in stat,
            "runtime source-form authority commit does not touch the boot decoder site")
    diff = subprocess.run(
        ["git", "show", full, "--", runtime_name], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    require("c2_boot_name_index_invalidate();" in diff and SITE_PREFIX in diff,
            "runtime source-form authority commit does not introduce the boot decoder block")
    live_text = E25.RUNTIME.read_text(encoding="utf-8")
    form = classify_decoder_site(live_text)
    return {"authority_commit": full, "authority_subject": subject,
            "feature": FEATURE, "decoder_site_form": form,
            "runtime_live": E25.bind(E25.RUNTIME),
            "form_matrix_cases": check_form_matrix()}


def derive() -> dict[str, Any]:
    historical = load(E25.RECEIPT)
    E25.verify(historical)
    live = derive_current(); E25.verify(live)
    current = deepcopy(live)
    changed = tuple(changed_paths(historical, current))
    require(changed == ALLOWED,
            f"D1/E25 decoder-site-form rebind exceeds runtime source authority: {changed}")
    old_semantic = deepcopy(historical); new_semantic = deepcopy(current)
    for path in ALLOWED:
        remove_path(old_semantic, path); remove_path(new_semantic, path)
    require(old_semantic == new_semantic,
            "D1/E25 semantic projection changed")
    predecessor = load(PREDECESSOR)
    require(predecessor.get("status") ==
                "PASS: loud semantic-preserving D1/E25 runtime-source rebind"
            and predecessor["change"]["allowed_paths"] == list(ALLOWED),
            "predecessor rebind receipt drift")
    return {
        "format": "lisp65-c2.3-v20-map-tuple-d1-e25-rebind-v2",
        "recorded_on": "2026-09-22",
        "status": "PASS: loud semantic-preserving D1/E25 decoder-site-form rebind",
        "predecessor": {"receipt": bind(PREDECESSOR),
            "status": predecessor["status"],
            "allowed_paths": predecessor["change"]["allowed_paths"]},
        "cause": runtime_cause(),
        "authority": {"authorization": authorization(),
            "historical_receipt": bind(E25.RECEIPT),
            "historical_runtime": historical["authority"]["runtime"],
            "current_runtime": current["authority"]["runtime"],
            "current_projection_sha256": hashlib.sha256(
                canonical(current)).hexdigest(),
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": list(ALLOWED),
            "actual_changed_paths": list(changed),
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False,
            "predecessor_receipt_rewritten": False},
        "claim_continuity": {"status": current["status"],
            "remaining_split": current["classification"]["remaining_split"],
            "capture_status": current["capture"]["status"]},
        "claim_limit": (
            "Source-form rebind only: widens the decoder call-site check to "
            "the two sanctioned forms (historical one-liner, or the block "
            "adding only the feature-guarded boot-name-index invalidation). "
            "The base tool, its historical receipt and the 2026-08-14 "
            "rebind receipt remain unchanged; every semantic claim is "
            "unchanged; no device action is authorized."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("status") ==
                "PASS: loud semantic-preserving D1/E25 decoder-site-form rebind"
            and value["change"]["allowed_paths"] == list(ALLOWED)
            and value["change"]["semantic_claims_changed"] is False
            and value["change"]["historical_receipt_rewritten"] is False
            and value["change"]["predecessor_receipt_rewritten"] is False,
            "D1/E25 decoder-site-form rebind receipt red")
    require(value["cause"]["authority_commit"] == subprocess.run(
                ["git", "rev-parse", f"{RUNTIME_AUTHORITY_COMMIT}^{{commit}}"],
                cwd=ROOT, check=True, text=True,
                stdout=subprocess.PIPE).stdout.strip()
            and value["cause"]["feature"] == FEATURE
            and value["cause"]["decoder_site_form"] == "current"
            and value["cause"]["runtime_live"] == bind(E25.RUNTIME)
            and value["cause"]["form_matrix_cases"] == list(FORM_CASES),
            "runtime-form cause binding drift")
    predecessor_now = bind(PREDECESSOR)
    require(value["predecessor"]["receipt"] == predecessor_now
            and value["predecessor"]["status"] ==
                "PASS: loud semantic-preserving D1/E25 runtime-source rebind",
            "predecessor rebind receipt was rewritten")
    historical_now = bind(E25.RECEIPT)
    require(value["authority"]["historical_receipt"] == historical_now,
            "historical D1/E25 receipt was rewritten")
    if verify:
        require(value == derive(), "D1/E25 decoder-site-form rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "change-claims": lambda x: x["change"].update(
            semantic_claims_changed=True),
        "widen-fields": lambda x: x["change"]["allowed_paths"].append(
            "classification.remaining_split"),
        "collapse-split": lambda x: x["claim_continuity"].update(
            remaining_split=["c2_decode_from"]),
        "drop-predecessor-binding": lambda x: x["change"].update(
            predecessor_receipt_rewritten=True),
        "escape-cause-authority": lambda x: x["cause"].update(
            decoder_site_form="historical"),
        "corrupt-rebind-driver": lambda x: x["authority"].update(
            rebind_driver=bind(DRIVER) | {"sha256": "0" * 64}),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "D1/E25 decoder-site-form rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "D1/E25 decoder-site-form rebind receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("D1/E25 decoder-site-form rebind: PASS "
          f"fields={len(ALLOWED)} mutations={len(SEALED_MUTATIONS)}")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == SEALED_MUTATIONS and mutations(value) == SEALED_MUTATIONS,
            "D1/E25 decoder-site-form rebind mutation set drift")
    print("D1/E25 decoder-site-form rebind: CHECK PASS "
          f"historical=unchanged predecessor=unchanged mutations={len(SEALED_MUTATIONS)}")


def selftest() -> None:
    value = derive(); validate(value, verify=False)
    rejected = mutations(value)
    require(rejected == SEALED_MUTATIONS,
            "D1/E25 decoder-site-form rebind mutation set drift")
    print(json.dumps({"status": "green", "mutations_rejected": len(rejected),
                       "decoder_site_form": value["cause"]["decoder_site_form"]},
                      sort_keys=True))


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v20_map_tuple_d1_e25_rebind_20260922.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, E25.EvidenceError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"D1/E25 decoder-site-form rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
