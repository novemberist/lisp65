#!/usr/bin/env python3
"""Build fresh same-world media for the bound-origin counter measurement."""

from __future__ import annotations

import argparse
import copy
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

import c2_v160_bound_origin_fragmentation_device_preparation as PREP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-measurement-media"
RECEIPT = ARCH / "c2.3-v1.6-bound-origin-measurement-media-receipt.json"
SESSION = ROOT / "config/c2-v160-bound-origin-measurement-device-session.json"
PREDECESSOR = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-device-preparation-receipt.json")
AUTHORIZATION = "166227be"
MEASUREMENT_AUTHORIZATION = "80baec42"
PRODUCT_REMOTE = "V16PM.D81"
LIBRARY_REMOTE = "V16LM.D81"
FORMAT = "lisp65-c2-v160-bound-origin-measurement-media-v1"
STATUS = "PASS: V1.6 BOUND-ORIGIN MEASUREMENT MEDIA READY"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    rows: dict[str, Any] = {}
    for label, ref, tokens in (
        ("release_shape", AUTHORIZATION,
         ("one-byte fragmentation card", "product link, fresh media",
          "one short measuring contact")),
        ("measurement", MEASUREMENT_AUTHORIZATION,
         ("stay under 256 events", "physical keystroke count")),
    ):
        commit = subprocess.run(["git", "rev-parse", f"{ref}^{{commit}}"],
            cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
            check=True, stdout=subprocess.PIPE).stdout
        text = " ".join(raw.decode().lower().replace("`", "").replace(
            "*", "").split())
        for token in tokens:
            require(token in text, f"measurement-media authority absent: {token}")
        rows[label] = {"authority": "git-blob", "commit": commit,
            "path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}
    return rows


def configure() -> None:
    PREP.BUILD = BUILD
    PREP.RECEIPT = RECEIPT
    PREP.SESSION = SESSION
    PREP.PRODUCT_REMOTE = PRODUCT_REMOTE
    PREP.LIBRARY_REMOTE = LIBRARY_REMOTE
    PREP.authority = lambda: {"release_shape": authority()}
    PREP.configure()


def validate(value: dict[str, Any], session: dict[str, Any],
             *, verify_files: bool) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "measurement-media status drift")
    require(value["measurement_authority"] == authority(),
            "measurement-media authority drift")
    require(value["accepted_pair"] == {
        "PRG": {"path": ("build/c2.3/v1.6-bound-origin-fragmentation-"
                          "second-replacement-card/wplto/"
                          "lisp65-c2-substitution-linked.prg"),
                "bytes": 41566,
                "sha256": ("f43bf592ba6f245e4032f0860aa9c4ce100e6e933767d0a4c"
                           "f0c355ad6770a3b")},
        "ELF": {"path": ("build/c2.3/v1.6-bound-origin-fragmentation-"
                          "second-replacement-card/wplto/"
                          "lisp65-c2-substitution-linked.prg.elf"),
                "bytes": 632832,
                "sha256": ("8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659"
                           "eb79fc580fecd45")}},
            "measurement-media final product pair drift")
    run = value["execution_accounting"]["successful_run"]
    require(run["WPLTO_runs"] == 0 and run["product_links"] == 0
            and run["artifact_completions"] == 1
            and run["media_builds"] == 2 and run["device_contacts"] == 0,
            "measurement-media execution accounting drift")
    witness = session["counter_witness"]
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and witness["origin"].startswith("atomic zero")
            and witness["maximum_physical_events"] == 255
            and witness["submit_after_target"] is False
            and witness["decision_table"] == {
                "physical>raw": "keyboard/core before queue-present observation",
                "raw>seen": "IRQ queue read or filtering",
                "seen>stored": "ring write or full-ring admission",
                "stored>taken": "consumer/take path",
                "physical=raw=seen=stored=taken":
                    "no loss; display/timing path"},
            "measurement session decision table drift")
    require(value["predecessor_media"] == bind(PREDECESSOR),
            "measurement predecessor identity drift")
    if verify_files:
        rows = [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"], value["predecessor_media"]]
        for row in rows:
            require(bind(ROOT / row["path"]) == row,
                    f"measurement artifact identity drift: {row['path']}")
        pair = PREP.BASE.PAIR.pair_identity(
            ROOT / value["media"]["product"]["path"],
            ROOT / value["media"]["library"]["path"])
        require(pair == value["same_world_pair"],
                "measurement media are not a same-world pair")


def preflight() -> None:
    configure()
    previous = load(PREDECESSOR)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "measurement-media output closure is one-shot")
    require(previous["status"] ==
                "PASS: V1.6 BOUND-ORIGIN DEVICE CONTACT READY"
            and previous["accepted_pair"] == {
                "ELF": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
                "PRG": bind(PREP.WPLTO / "lisp65-c2-substitution-linked.prg")},
            "measurement-media predecessor drift")
    authority()
    print("v1.6 bound-origin measurement media: PREFLIGHT PASS "
          "link=frozen media=0 contact=0")


def build() -> None:
    configure()
    PREP.build()
    value = load(RECEIPT)
    session = load(SESSION)
    session["format"] = "lisp65-c2-v160-bound-origin-measurement-session-v1"
    session["measurement_authority"] = authority()
    SESSION.write_bytes(canonical(session))
    value["format"] = FORMAT
    value["status"] = STATUS
    value["measurement_authority"] = authority()
    value["predecessor_media"] = bind(PREDECESSOR)
    value["session"] = bind(SESSION)
    value["execution_accounting"] = {
        "successful_run": {"WPLTO_runs": 0, "product_links": 0,
            "artifact_completions": 1, "media_builds": 2,
            "device_contacts": 0},
        "reason": ("the authorized fragmentation card already emitted and "
                   "accepted the final pair; this successor reads it and "
                   "builds fresh media")}
    RECEIPT.write_bytes(canonical(value))
    validate(value, session, verify_files=True)
    print("v1.6 bound-origin measurement media: PASS media=2 contact=ready")


def check() -> None:
    configure()
    value = load(RECEIPT)
    session = load(SESSION)
    validate(value, session, verify_files=True)
    print("v1.6 bound-origin measurement media: CHECK PASS")


def selftest() -> None:
    configure()
    value = load(RECEIPT)
    session = load(SESSION)
    mutations = []
    for label, mutate_value, mutate_session in (
        ("product-link-repeated",
         lambda row: row["execution_accounting"]["successful_run"].update(
             {"product_links": 1}), lambda _row: None),
        ("old-media-name", lambda _row: None,
         lambda row: row["media"]["product"].update(
             {"remote_name": "V16P5.D81"})),
        ("counter-wrap-authorized", lambda _row: None,
         lambda row: row["counter_witness"].update(
             {"maximum_physical_events": 256})),
        ("decision-arc-erased", lambda _row: None,
         lambda row: row["counter_witness"]["decision_table"].pop(
             "physical>raw")),
    ):
        candidate = copy.deepcopy(value)
        candidate_session = copy.deepcopy(session)
        mutate_value(candidate)
        mutate_session(candidate_session)
        try:
            validate(candidate, candidate_session, verify_files=False)
        except RuntimeError:
            mutations.append(label)
        else:
            raise RuntimeError(f"measurement-media mutation survived: {label}")
    require(len(mutations) == 4, "measurement-media mutation count drift")
    print("v1.6 bound-origin measurement media: SELFTEST PASS mutations=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check",
                                           "selftest"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    elif action == "check":
        check()
    else:
        selftest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
