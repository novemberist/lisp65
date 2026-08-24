#!/usr/bin/env python3
"""Attribute the frozen input-fidelity companion-without-trigger Red."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-phase-owner-card-final-red.json")
ELF = ROOT / (
    "build/c2.3/v1.6-input-fidelity-phase-owner-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ROOT / (
    "build/c2.3/v1.6-input-fidelity-phase-owner-card/wplto/"
    "lisp65-c2-substitution-linked.prg")
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-companion-trigger-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "fa53002b"
FORMAT = "lisp65-c2-v160-input-fidelity-companion-trigger-attribution-v1"
STATUS = "ATTRIBUTED: GLOBAL DEFINE COPIED INTO WRONG SOURCE-OWNER DOMAIN"
SCOPE = "mapped-far-content-convergence"
CAPTURE = "LISP65_V160_INPUT_CAPTURE"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(["git", "show",
        f"{value['commit']}:{value['path']}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("`", "").replace("*", "").split())
    for token in ("host-only attribution", "frozen elf/prg pair",
                  "exact configuration writer", "both sides persisted",
                  "no successor card"):
        require(token in text,
                f"companion-trigger attribution authority absent: {token}")
    return value


def scope_row(product: Any) -> dict[str, Any]:
    rows = [row for row in product.SOURCE_OWNER_SCOPES
            if row.get("name") == SCOPE]
    require(len(rows) == 1, "mapped-far source-owner scope is not unique")
    return rows[0]


def snapshot(product: Any) -> dict[str, Any]:
    row = scope_row(product)
    capture_rows = [item for item in product.SOURCE_OWNER_SCOPES
                    if item.get("name") == "v160-input-capture"]
    return {
        "global_convergence_defines": list(product.CONVERGENCE_DEFINES),
        "mapped_far_scope": {
            "trigger": str(row["trigger"]),
            "defines": list(row["defines"]),
            "sources": [Path(path).relative_to(ROOT).as_posix()
                        for path in row["sources"]],
        },
        "capture_scope": None if not capture_rows else {
            "trigger": str(capture_rows[0]["trigger"]),
            "defines": list(capture_rows[0]["defines"]),
            "sources": [Path(path).relative_to(ROOT).as_posix()
                        for path in capture_rows[0]["sources"]],
        },
    }


def capture() -> dict[str, Any]:
    """Reproduce the real Scope setup and retain only the decisive writes."""
    import c2_product_substitution_link as product
    import c2_v21_full_span_convergence_card as full_span
    import c2_v160_input_fidelity_phase_owner_replacement_card as card

    before_pair = {"ELF": bind(ELF), "PRG": bind(PRG)}
    transitions: list[dict[str, Any]] = []
    failing: dict[str, Any] = {}
    original_probe = product.scoped_probe_definitions
    original_capture = product.configure_input_capture
    original_scope_writer = full_span.ORIGINAL_CONFIGURE_FIX_SOURCE
    entries: dict[int, tuple[str, Any, dict[str, Any]]] = {}

    def transition(kind: str, function: Any, before: dict[str, Any],
                   after: dict[str, Any]) -> None:
        transitions.append({"kind": kind,
            "writer": {
                "path": Path(inspect.getsourcefile(function) or "").relative_to(
                    ROOT).as_posix(),
                "first_line": function.__code__.co_firstlineno,
                "function": function.__name__,
            },
            "before": before, "after": after})

    watched = {
        original_capture.__code__: ("global-aggregate-write", original_capture),
        original_scope_writer.__code__: (
            "source-owner-scope-write", original_scope_writer),
    }

    def profile(frame: Any, event: str, _arg: Any) -> Any:
        watched_row = watched.get(frame.f_code)
        if watched_row is None:
            return profile
        if event == "call":
            entries[id(frame)] = (*watched_row, snapshot(product))
        elif event == "return" and id(frame) in entries:
            kind, function, before = entries.pop(id(frame))
            after = snapshot(product)
            if (kind == "global-aggregate-write"
                    and CAPTURE not in before["global_convergence_defines"]
                    and CAPTURE in after["global_convergence_defines"]):
                transition(kind, function, before, after)
            if (kind == "source-owner-scope-write"
                    and CAPTURE not in before["mapped_far_scope"]["defines"]
                    and CAPTURE in after["mapped_far_scope"]["defines"]):
                transition(kind, function, before, after)
        return profile

    def probe(extra_definitions: tuple[str, ...] = ()) -> tuple[str, ...]:
        try:
            return original_probe(extra_definitions)
        except RuntimeError as error:
            failing.update({
                "error": str(error),
                "extra_definitions": list(extra_definitions),
                "state": snapshot(product),
            })
            raise

    product.scoped_probe_definitions = probe
    sys.setprofile(profile)
    try:
        card.child("_scope")
    except Exception:
        pass
    finally:
        sys.setprofile(None)
        product.scoped_probe_definitions = original_probe
    after_pair = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(failing.get("error") ==
                "source-owner companion escaped trigger: " + SCOPE,
            "real Scope consumer did not reproduce companion-trigger Red")
    decisive = [row for row in transitions
                if row["kind"] in {"global-aggregate-write",
                                   "source-owner-scope-write"}]
    require(len(decisive) == 2
            and decisive[0]["writer"] == {
                "path": "tools/host-lisp/c2_product_substitution_link.py",
                "first_line": 1266, "function": "configure_input_capture"}
            and decisive[1]["writer"] == {
                "path": "tools/host-lisp/c2_v20_map_tuple_fix_card.py",
                "first_line": 83, "function": "configure_fix_source"},
            "exact companion-trigger writer chain drift")
    require(before_pair == after_pair, "frozen Red pair changed during capture")
    return {"transitions": decisive, "failing_consumer": failing,
            "frozen_pair_before": before_pair,
            "frozen_pair_after": after_pair,
            "frozen_pair_unchanged": True}


def run_capture() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_capture"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"companion-trigger raw capture red: {result.stderr}")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "raw capture returned no object")
    return value


def source_identity(function: Any) -> dict[str, Any]:
    path = Path(inspect.getsourcefile(function) or "")
    return {"module": function.__module__, "function": function.__name__,
            "path": path.relative_to(ROOT).as_posix(),
            "first_line": function.__code__.co_firstlineno,
            "source": bind(path)}


def assignment_line(function: Any, token: str) -> int:
    lines, first = inspect.getsourcelines(function)
    matches = [first + index for index, line in enumerate(lines)
               if token in line]
    require(len(matches) == 1,
            f"writer assignment token is not unique: {token}")
    return matches[0]


def derive() -> dict[str, Any]:
    import c2_product_substitution_link as product
    import c2_v20_map_tuple_fix_card as map_fix

    red = load(FINAL_RED)
    frozen = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(red["status"] ==
                "FINAL RED: INPUT-FIDELITY PHASE OWNER RETURNS TO REVIEW"
            and red["retry_authorized"] is False
            and red["artifacts"] == frozen
            and red["attribution_boundary"]["exact_configuration_writer"] ==
                "unattributed",
            "companion-trigger frozen Red authority drift")
    raw = run_capture()
    transitions = raw["transitions"]
    seed = transitions[0]
    writer = transitions[1]
    observed = raw["failing_consumer"]
    mapped = observed["state"]["mapped_far_scope"]
    capture_scope = observed["state"]["capture_scope"]
    require(observed["extra_definitions"] == [CAPTURE]
            and CAPTURE in mapped["defines"]
            and mapped["trigger"] not in observed["extra_definitions"]
            and capture_scope == {
                "trigger": CAPTURE, "defines": [CAPTURE],
                "sources": ["src/optional/c2_kernal_input_capture.s"]},
            "expected and observed source-owner domains are not separated")

    expected = {
        "selected_definitions_at_consumer": [CAPTURE],
        "selected_owner": "v160-input-capture",
        "selected_owner_trigger": CAPTURE,
        "selected_owner_defines": [CAPTURE],
        "mapped_far_owner_selected": False,
        "invariant": (
            "a definition belongs only to the source-owner row whose "
            "identity declares it; global build membership is not owner-scope "
            "membership"),
    }
    actual = {
        "selected_definitions_at_consumer": observed["extra_definitions"],
        "mapped_far_owner_trigger": mapped["trigger"],
        "mapped_far_owner_defines": mapped["defines"],
        "escaped_companion": CAPTURE,
        "consumer_error": observed["error"],
    }
    return {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": STATUS,
        "claim_limit": (
            "Host-only attribution over the frozen fourth-Red pair and a "
            "fresh-process reproduction of its real Scope setup; no fix, "
            "qualification, link, card, media, or device."),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_authorized": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "frozen_evidence": {"Final_Red": bind(FINAL_RED), **frozen},
        "raw_first_capture": raw,
        "drift_report": {"expected": expected, "observed": actual},
        "writer_attribution": {
            "seed_writer": {
                **source_identity(product.configure_input_capture),
                "write_line": assignment_line(product.configure_input_capture,
                    "CONVERGENCE_DEFINES = (*CONVERGENCE_DEFINES,"),
                "effect": (
                    "adds the capture feature to the global convergence "
                    "definition aggregate while its dedicated owner row "
                    "remains correct"),
            },
            "exact_scope_writer": {
                **source_identity(map_fix.configure_fix_source),
                "write_line": assignment_line(map_fix.configure_fix_source,
                    "PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)"),
                "effect": (
                    "copies PRODUCT.CONVERGENCE_DEFINES wholesale into the "
                    "mapped-far-content-convergence row"),
            },
            "later_configuration_layers": (
                "propagate the already-misclassified row; they do not create "
                "the first companion-without-trigger membership"),
        },
        "decision": {
            "classification": (
                "known-domain-membership-family-global-aggregate-used-as-"
                "source-owner-local-registry"),
            "known_family_member": True,
            "new_class": False,
            "product_finding": False,
            "standing_rule": (
                "right identity, right owner domain: registry membership is "
                "derived by owner identity, never copied from a cross-domain "
                "aggregate"),
            "mechanical_basis": (
                "The capture feature is correctly selected and has its own "
                "source-owner row. configure_fix_source() then writes that "
                "global feature into the unrelated mapped-far row. The real "
                "consumer selects only capture, so mapped-far sees a companion "
                "without its trigger. No emitted product byte is implicated."),
        },
        "disposition": {
            "successor_cards_authorized": 0,
            "required_conversion": (
                "derive each source-owner row from that row's identity rather "
                "than PRODUCT.CONVERGENCE_DEFINES"),
            "seam_self_disposition_budget": "reset-by-attribution",
            "next": "attribution report before any successor",
        },
        "authority": {"reviewer": authorization(), "driver": bind(DRIVER)}}


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "companion-trigger attribution receipt drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "_capture"))
    action = parser.parse_args().action
    if action == "_capture":
        print(json.dumps(capture(), sort_keys=True))
    elif action == "write":
        require(not RECEIPT.exists(), "attribution receipt already exists")
        RECEIPT.write_bytes(canonical(derive()))
        print("input-fidelity companion-trigger: ATTRIBUTED "
              "known-domain-family card=0 link=0")
    else:
        validate(load(RECEIPT))
        print("input-fidelity companion-trigger: CHECK PASS "
              "known-domain-family card=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"input-fidelity companion-trigger attribution: FIRST RED: "
              f"{error}", file=sys.stderr)
        raise SystemExit(2)
