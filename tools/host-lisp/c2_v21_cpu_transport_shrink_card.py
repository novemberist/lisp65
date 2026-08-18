#!/usr/bin/env python3
"""Price the 2.1 reader shrink and run the one owner-authorized card."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_cpu_transport_preflight as PRE  # noqa: E402
import c2_v21_cpu_transport_replacement_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
BUILD = ROOT / "build/c2.3/v2.1-cpu-transport-shrink-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-cpu-transport-shrink-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-cpu-transport-shrink-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-shrink-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v2.1-cpu-transport-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9204d521"
OLD_READER_COMMIT = "f1ab67cc"
LINK = 107
RECORDED_ON = "2026-08-14"


class ShrinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ShrinkError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_blob(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, authority = git_blob(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "shrink the 169-byte cpu reader by ≥2 bytes",
            "identical behavior, identical map discipline",
            "instruction selection, not from dropping a check",
            "exactly one card"):
        require(token in text, f"shrink authorization token absent: {token}")
    return authority


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.RECEIPT = BUILD / "unused-replacement-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-replacement-final-red.json"
    BASE.LINK = LINK
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(
        value.get("status") == "FINAL RED: CPU-transport replacement returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting", {}).get("replacement_cards_consumed") == 1
        and "ordinary text displaced the mapped far facade"
            in value.get("error", {}).get("message", ""),
        "two-byte predecessor Final Red drift")
    return value


def instruction_lines(source: str) -> list[str]:
    rows: list[str] = []
    for raw in source.splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            rows.append(re.sub(r"\s+", " ", line))
    return rows


def reader_equivalence(current_override: str | None = None) -> dict[str, Any]:
    old_raw, old_authority = git_blob(OLD_READER_COMMIT, READER)
    old = old_raw.decode()
    current = (READER.read_text(encoding="utf-8")
               if current_override is None else current_override)
    old_lines = instruction_lines(old)
    new_lines = instruction_lines(current)
    deleted = "ldy #0"
    candidates = [index for index, line in enumerate(old_lines)
                  if line == deleted and index > 0
                  and old_lines[index - 1] == ".Lc2_cpu_copy:"]
    require(len(candidates) == 1, "historical redundant LDY identity drift")
    index = candidates[0]
    require(old_lines[:index] + old_lines[index + 1:] == new_lines,
            "reader shrink changed more than the one redundant instruction")

    helper = current[current.index(".Lc2_cpu_map_window:"):]
    copy = current[current.index(".Lc2_cpu_copy:"):
                   current.index(".Lc2_cpu_restore:")]
    require(
        helper.count("\tldy #0") == 1
        and helper.index("\tldy #0") < helper.index("\tmap\n")
        and not re.search(r"\t(?:iny|dey|ply|tay)\b", helper)
        and not re.search(r"\t(?:ldy|iny|dey|ply|tay)\b", copy)
        and current[current.index("jsr .Lc2_cpu_map_window"):
                    current.index(".Lc2_cpu_copy:")].count(
                        "jsr .Lc2_cpu_map_window") == 1
        and copy.count("bne .Lc2_cpu_copy") == 1
        and current.count("jsr .Lc2_cpu_map_window") == 2
        and current.count("bra .Lc2_cpu_copy") == 1,
        "Y=0 induction is not closed over every copy-loop entry/backedge")

    old_assembly = PRE.assemble_reader(old)
    new_assembly = PRE.assemble_reader(current)
    old_bytes = old_assembly["object_bytes"]
    new_bytes = new_assembly["object_bytes"]
    require(old_bytes == 169 and new_bytes == 166
            and old_bytes - new_bytes >= 2,
            "reader instruction price did not recover the required capacity")
    return {
        "status": "PASS: redundant Y reload removed under closed Y=0 induction",
        "historical_reader": old_authority,
        "source_delta": {"deleted_instruction": "LDY #0 at copy-loop head",
                         "other_instruction_changes": 0,
                         "checks_removed": 0},
        "price": {"before_bytes": old_bytes, "after_bytes": new_bytes,
                  "saved_bytes": old_bytes - new_bytes,
                  "direct_instruction_bytes": 2,
                  "secondary_short_branch_relaxation_bytes": 1,
                  "required_saving_bytes": 2},
        "equivalence": {
            "initial_entry": "map-window helper returns Y=0",
            "backedge": "copy body has no Y writer",
            "window_crossing": "map-window helper reasserts Y=0",
            "all_noncomment_instructions_except_deleted_LDY_identical": True,
            "MAP_EOM_pairs": current.count("\tmap\n"),
            "restore_PLP_present": "\tplp" in current,
            "high_length_rejection_present":
                "\tlda __rc7\n\tbne .Lc2_cpu_fail" in current,
        },
    }


def equivalence_mutations() -> list[str]:
    source = READER.read_text(encoding="utf-8")
    cases = {
        "restore-redundant-LDY": source.replace(
            ".Lc2_cpu_copy:\n", ".Lc2_cpu_copy:\n\tldy #0\n", 1),
        "lose-helper-Y-zero": source.replace("\tldy #0\n", "", 1),
        "write-Y-on-backedge": source.replace(
            ".Lc2_cpu_copy:\n", ".Lc2_cpu_copy:\n\tiny\n", 1),
        "drop-high-length-check": source.replace(
            "\tlda __rc7\n\tbne .Lc2_cpu_fail\n", "", 1),
        "drop-restore-PLP": source.replace("\tplp\n", "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            reader_equivalence(candidate)
        except (ShrinkError, PRE.PreflightError):
            rejected.append(name)
    require(rejected == list(cases), "reader equivalence mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v2.1-cpu-transport-shrink-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: 166-byte equivalent reader; one card armed",
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
                               "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "cards_authorized": 1},
        "reader_equivalence": reader_equivalence(),
        "source_owner": BASE.dynamic_configuration_gate(),
        "authority": {"authorization": authorization(),
                      "predecessor_final_red": bind(PREDECESSOR),
                      "contract": bind(PRE.CONTRACT), "reader": bind(READER),
                      "driver": bind(DRIVER)},
        "claim_limit": "Host pricing/equivalence only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "shrink preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "authorize-two-cards": lambda x: x["configuration"].update(cards_authorized=2),
        "claim-two-byte-reader": lambda x: x["reader_equivalence"]["price"].update(
            after_bytes=167),
        "detach-predecessor": lambda x: x["authority"]["predecessor_final_red"].update(
            sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except ShrinkError:
            rejected.append(name)
    require(rejected == list(cases), "shrink preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "shrink preflight/card is one-shot")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = {
        "equivalence": equivalence_mutations(),
        "preflight": preflight_mutations(value),
    }
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    price = value["reader_equivalence"]["price"]
    print("2.1 CPU transport shrink: PREFLIGHT PASS "
          f"reader={price['before_bytes']}->{price['after_bytes']}B "
          f"saved={price['saved_bytes']} mutations=8 card=0/1")


def produce_child() -> int:
    configure()
    result = BASE.produce_child()
    value = load(PRODUCER_RESULT)
    reader = value["v21_linked_transport"]["reader"]
    require(reader["bytes"] == 166,
            "linked reader does not carry the priced shrink")
    value["v21_reader_shrink"] = reader_equivalence()
    PRODUCER_RESULT.write_bytes(canonical(value))
    return result


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh CPU-reader shrink child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == {"equivalence": equivalence_mutations(),
                         "preflight": preflight_mutations(value)},
            "shrink mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "CPU-reader shrink card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor_final_red": bind(PREDECESSOR),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "shrink acceptance changed linked artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "shrink card process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-cpu-transport-shrink-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-107 CPU-reader shrink card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "contract": bind(PRE.CONTRACT),
            "reader": bind(READER), "driver": bind(DRIVER)},
        "reader_equivalence": producer["v21_reader_shrink"],
        "transport": producer["v21_linked_transport"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": rejected,
        "next": "completion and complete same-world media closure, then D1",
        "claim_limit": "One product card only; media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 CPU transport shrink: CARD PASS card=1/1 "
          f"reader={receipt['transport']['reader']['bytes']}B VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-cpu-transport-shrink-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: CPU-reader shrink card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "shrink Final Red drift")
        print("2.1 CPU transport shrink: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == {"equivalence": equivalence_mutations(),
                                 "preflight": preflight_mutations(value)},
                    "shrink preflight receipt drift")
        print("2.1 CPU transport shrink: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: Link-107 CPU-reader shrink card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["transport"]["reader"]["bytes"] == 166,
            "shrink green receipt drift")
    print("2.1 CPU transport shrink: CHECK PASS card=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"shrink Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 CPU transport shrink: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
