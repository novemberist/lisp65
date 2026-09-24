#!/usr/bin/env python3
"""Loudly re-widen the oracle rebind to the boot-name-index wrapper population.

Class-1 successor to c2_v20_source_authoritative_oracle_rebind_20260814.py.

The 2026-08-14 tool bound exactly four paths (authority.driver.*,
authority.source.*) as the only projection drift a decoder-source rebind may
carry -- the id-only move from a live file binding to an era-sealed one. That
receipt is untouched here and stays the historical predecessor: its own
`check` still runs (mk/gates.mk keeps calling it directly nowhere else), and
this tool re-verifies its receipt bytes on every run.

Its `check`, however, went red on 2026-09-21: the parked boot-time-name-index
card (authorities 1d964e4c/7ec22e55, feature LISP65_C2_BOOT_NAME_INDEX) added
two new phase wrappers -- scripts/c2-stream-v2-phase-10a.c and -10b.c -- to
the accepted world's phase-source list (tools/host-lisp/
c2_product_substitution_link.py, C2_PHASE_SOURCES and BOOT_NAME_INDEX_ROWS).
Neither wrapper is compiled into anything the accepted world links; they
exist so a *later* card can opt the two boot-only decoder records in via
`configure_boot_name_index_slices()`. Their mere presence in the source list
the live oracle walks moves two more counters that were previously constant:
`source_gate.symbol_ownership.phase_wrappers` and
`target_codegen.translation_units`, both 18 -> 20. The 2026-08-14 tool's
`changed == ALLOWED` check (four paths) therefore now sees six, and its
frozen `current_projection_sha256` no longer matches the live projection.

This is not decoder-source drift and it is not scope creep: it is a fully
understood, bounded, sha256-pinned population change with a named cause.
This tool widens ALLOWED to those exact six paths, proves nothing else in
the oracle projection moved (the same old-semantic == new-semantic check the
2026-08-14 tool ran, now over the wider allowance), and binds the cause
itself -- both wrapper files by sha256 against the authorship commit, and
the exact BOOT_NAME_INDEX_ROWS source lines that queued them -- so a further,
unbound wrapper cannot ride through silently.

mk/gates.mk's `c2-v20-source-authoritative-oracle-check` target is retargeted
here (see its comment); the 2026-08-14 receipt and tool are otherwise
untouched and this tool re-validates that receipt's bytes every run.
"""

from __future__ import annotations

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

import c2_v20_source_authoritative_oracle as O  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREDECESSOR = ARCH / (
    "c2.3-v2.0-source-authoritative-oracle-rebind-2026-08-14.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-source-authoritative-oracle-rebind-2026-09-21.json")
DRIVER = Path(__file__).resolve()
LINK_TOOL = HOST / "c2_product_substitution_link.py"
AUTHORIZATION = "b3f6adc2"
SEAL_ERA_COMMIT = "4db8b6dc7d08c233c330a34c46a184eb05588504"
WRAPPER_COMMIT = "1d964e4c"
WRAPPERS = (
    ROOT / "scripts/c2-stream-v2-phase-10a.c",
    ROOT / "scripts/c2-stream-v2-phase-10b.c",
)
FEATURE = "LISP65_C2_BOOT_NAME_INDEX"
ROW_TEXT = (
    'BOOT_NAME_INDEX_ROWS = [("10a", "c2_stream_phase_10a"),\n'
    '                        ("10b", "c2_stream_phase_10b")]\n'
)
ALLOWED = (
    "authority.driver.bytes", "authority.driver.sha256",
    "authority.source.bytes", "authority.source.sha256",
    "source_gate.symbol_ownership.phase_wrappers",
    "target_codegen.translation_units",
)
# Unlike the 2026-08-14 predecessor -- whose sealed five were recorded
# before its four "era" cases were added by a later fix, so its receipt
# legitimately carries fewer names than its live `mutations()` -- this tool
# is new today with its full case set already in place, so the sealed list
# recorded at `record` time equals the live set completely.
SEALED_MUTATIONS = [
    "rewrite-history", "change-claims", "widen-fields", "drop-site",
    "consume-card", "collapse-driver-era-to-live", "escape-source-sealing-era",
    "collapse-generator-era-to-live", "corrupt-rebind-driver",
    "third-wrapper-silently-allowed", "drop-a-wrapper-cause",
    "change-semantic-field",
]


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("full closure" in text and "loud, dated rebind" in text,
            "oracle source rebind authority absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


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


def wrapper_cause() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{WRAPPER_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s", full], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    stat = subprocess.run(
        ["git", "show", "--stat", "--format=", full], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    require("boot-time name index" in subject.lower()
            and all(path.relative_to(ROOT).as_posix() in stat
                    for path in WRAPPERS),
            "wrapper authority commit does not introduce the two wrappers")
    wrappers = []
    for path in WRAPPERS:
        sealed = ERA.era_bind(full, path.relative_to(ROOT).as_posix())
        live = bind(path)
        require(sealed["sha256"] == live["sha256"]
                and sealed["bytes"] == live["bytes"],
                f"wrapper drifted from its authority commit: {path.name}")
        wrappers.append(sealed)
    sealed_link_tool = ERA.era_blob(
        full, LINK_TOOL.relative_to(ROOT).as_posix()).decode("utf-8")
    live_link_tool = LINK_TOOL.read_text(encoding="utf-8")
    require(ROW_TEXT in sealed_link_tool and ROW_TEXT in live_link_tool,
            "boot-name-index row binding drift")
    require(f'FEATURE = \'{FEATURE}\'' in
            (HOST / "boot_name_index_producer.py").read_text(encoding="utf-8"),
            "boot-name-index feature binding absent")
    return {"authority_commit": full, "authority_subject": subject,
            "feature": FEATURE, "wrappers": wrappers,
            "link_tool_rows": ROW_TEXT,
            "link_tool_rows_sha256": hashlib.sha256(
                ROW_TEXT.encode()).hexdigest()}


def derive() -> dict[str, Any]:
    historical = load(O.RECEIPT)
    historical_rejected = historical.pop("mutations_rejected", None)
    require(
        historical.get("status") ==
            "PASS: source-authoritative phase-02a fix host green; card locked"
        and len(historical["host_equivalence"]["sites"]) == 3
        and historical["timeout_pricing"]["selected_frames"] == 64
        and historical["card_boundary"]["consumed"] == 0
        and isinstance(historical_rejected, list)
        and len(historical_rejected) == 15,
        "historical oracle semantic/mutation inventory drift",
    )
    O.value.cache_clear()
    current = O.value(); O.validate(current)
    require(
        current["authority"]["driver"] == ERA.era_bind(
            SEAL_ERA_COMMIT, O.DRIVER)
        and current["authority"]["generator"] == ERA.era_bind(
            SEAL_ERA_COMMIT, O.GENERATOR)
        and current["authority"]["source"] == ERA.era_bind(
            SEAL_ERA_COMMIT, O.SOURCE),
        "oracle tool provenance escaped its sealing era",
    )
    changed = tuple(changed_paths(historical, current))
    require(changed == ALLOWED,
            f"oracle rebind exceeds wrapper-population authority: {changed}")
    old_semantic = deepcopy(historical); new_semantic = deepcopy(current)
    for path in ALLOWED:
        remove_path(old_semantic, path); remove_path(new_semantic, path)
    require(old_semantic == new_semantic,
            "oracle semantic projection changed")
    predecessor = load(PREDECESSOR)
    require(
        predecessor.get("status") ==
            "PASS: loud semantic-preserving oracle source rebind"
        and predecessor["change"]["allowed_paths"] == [
            "authority.driver.bytes", "authority.driver.sha256",
            "authority.source.bytes", "authority.source.sha256"],
        "predecessor rebind receipt drift",
    )
    return {
        "format": "lisp65-c2.3-v20-source-authoritative-oracle-rebind-v2",
        "recorded_on": "2026-09-21",
        "status": "PASS: loud semantic-preserving oracle wrapper-population "
                  "rebind",
        "predecessor": {"receipt": bind(PREDECESSOR),
            "status": predecessor["status"],
            "allowed_paths": predecessor["change"]["allowed_paths"]},
        "cause": wrapper_cause(),
        "authority": {"authorization": authorization(),
            "historical_driver": historical["authority"]["driver"],
            "current_driver": current["authority"]["driver"],
            "historical_source": historical["authority"]["source"],
            "current_source": current["authority"]["source"],
            "current_projection_sha256": hashlib.sha256(
                O.canonical(current)).hexdigest(),
            # DRIVER is this tool itself, introduced only now: there is no
            # prior commit to era-seal it against, so (like the very first,
            # pre-era-binding 2026-08-13 receipt) it is bound live.
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": list(ALLOWED),
            "actual_changed_paths": list(changed),
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False,
            "semantic_projection_sha256": hashlib.sha256(
                canonical(old_semantic)).hexdigest()},
        "claim_continuity": {"status": current["status"],
            "site_count": len(current["host_equivalence"]["sites"]),
            "timeout_frames": current["timeout_pricing"]["selected_frames"],
            "card_consumed": current["card_boundary"]["consumed"]},
        "claim_limit": (
            "Source-authority and named wrapper-population rebind only. "
            "The 2026-08-14 receipt, the historical oracle receipt and all "
            "semantic claims remain unchanged; no card or device action."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("status") ==
                "PASS: loud semantic-preserving oracle wrapper-population "
                "rebind"
            and value["change"]["allowed_paths"] == list(ALLOWED)
            and value["change"]["semantic_claims_changed"] is False
            and value["change"]["historical_receipt_rewritten"] is False
            and value["claim_continuity"] == {"status":
                "PASS: source-authoritative phase-02a fix host green; card locked",
                "site_count": 3, "timeout_frames": 64,
                "card_consumed": 0},
            "oracle wrapper-population rebind receipt red")
    predecessor_now = bind(PREDECESSOR)
    require(value["predecessor"]["receipt"] == predecessor_now
            and value["predecessor"]["status"] ==
                "PASS: loud semantic-preserving oracle source rebind",
            "predecessor rebind receipt was rewritten")
    cause = value["cause"]
    require(cause.get("authority_commit") == subprocess.run(
                ["git", "rev-parse", f"{WRAPPER_COMMIT}^{{commit}}"],
                cwd=ROOT, check=True, text=True,
                stdout=subprocess.PIPE).stdout.strip()
            and cause.get("feature") == FEATURE
            and isinstance(cause.get("wrappers"), list)
            and len(cause["wrappers"]) == 2
            and {row["path"] for row in cause["wrappers"]} == {
                path.relative_to(ROOT).as_posix() for path in WRAPPERS}
            and all(row == ERA.era_bind(cause["authority_commit"], row["path"])
                    for row in cause["wrappers"])
            and cause.get("link_tool_rows") == ROW_TEXT
            and cause.get("link_tool_rows_sha256") == hashlib.sha256(
                ROW_TEXT.encode()).hexdigest(),
            "wrapper cause binding drift")
    sealed_projection = O.value()
    require(
        value["authority"]["current_driver"] == ERA.era_bind(
            SEAL_ERA_COMMIT, O.DRIVER)
        and value["authority"]["current_source"] == ERA.era_bind(
            SEAL_ERA_COMMIT, O.SOURCE)
        and value["authority"]["current_projection_sha256"]
            == hashlib.sha256(O.canonical(sealed_projection)).hexdigest()
        and value["authority"]["rebind_driver"] == bind(DRIVER),
        "oracle rebind tool provenance escaped its sealing era",
    )
    historical = load(O.RECEIPT); historical.pop("mutations_rejected", None)
    old_semantic = deepcopy(historical); new_semantic = deepcopy(sealed_projection)
    for path in ALLOWED:
        remove_path(old_semantic, path); remove_path(new_semantic, path)
    require(old_semantic == new_semantic
            and value["change"]["semantic_projection_sha256"]
                == hashlib.sha256(canonical(old_semantic)).hexdigest(),
            "oracle semantic projection changed")
    if verify:
        require(value == derive(), "oracle wrapper-population rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "change-claims": lambda x: x["change"].update(
            semantic_claims_changed=True),
        "widen-fields": lambda x: x["change"]["allowed_paths"].append(
            "host_equivalence.sites"),
        "drop-site": lambda x: x["claim_continuity"].update(site_count=2),
        "consume-card": lambda x: x["claim_continuity"].update(card_consumed=1),
        "collapse-driver-era-to-live": lambda x: x["authority"].update(
            current_driver=bind(O.DRIVER)),
        "escape-source-sealing-era": lambda x: x["authority"].update(
            current_source=deepcopy(x["authority"]["historical_source"])),
        "collapse-generator-era-to-live": lambda x: x["authority"].update(
            current_projection_sha256=hashlib.sha256(O.canonical({
                **O.value(),
                "authority": {
                    **O.value()["authority"],
                    "generator": bind(O.GENERATOR),
                },
            })).hexdigest()),
        "corrupt-rebind-driver": lambda x: x["authority"].update(
            rebind_driver={"path": x["authority"]["rebind_driver"]["path"],
                           "bytes": 0, "sha256": "0" * 64}),
        "third-wrapper-silently-allowed": lambda x: x["cause"][
            "wrappers"].append({
                "path": "scripts/c2-stream-v2-phase-99.c",
                "bytes": 64, "sha256": "0" * 64}),
        "drop-a-wrapper-cause": lambda x: x["cause"]["wrappers"].pop(),
        "change-semantic-field": lambda x: x["change"].update(
            semantic_projection_sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "oracle wrapper-population rebind "
            "mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "oracle wrapper-population rebind receipt "
            "exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("source-authoritative oracle wrapper-population rebind: PASS "
          f"fields={len(ALLOWED)} mutations={len(SEALED_MUTATIONS)}")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == SEALED_MUTATIONS
            and len(mutations(value)) == len(SEALED_MUTATIONS),
            "oracle wrapper-population rebind mutation set drift")
    print("source-authoritative oracle wrapper-population rebind: CHECK "
          f"PASS history=unchanged predecessor=unchanged "
          f"sealed={len(SEALED_MUTATIONS)}")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_source_authoritative_oracle_rebind_20260921.py "
            "record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, O.OracleError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"source-authoritative oracle wrapper-population rebind: "
              f"FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
