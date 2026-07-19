#!/usr/bin/env python3
"""Prove the authorized 16-name Wave-2 harvest and its 18 echo cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools/host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0_stdlib as Stdlib  # noqa: E402


CONTRACT = ROOT / "config/v11-wave2-policy-name-revocation.json"
PREPARED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-policy-name-audit-receipt.json"
)
LIST_AUTHORIZATION = ROOT / (
    "config/v11-wave2-list-primitive-unification-capacity-authorization.json"
)
IDE_SOURCES = tuple(ROOT / f"lib/{name}" for name in (
    "ide-status.lisp", "ide-syntax.lisp", "ide-buffer.lisp",
    "ide-keymap-generated.lisp", "ide-ui.lisp",
    "ide-disk.lisp",
))
IDE_UI = ROOT / "lib/ide-ui.lisp"
IDE_KEYMAP = ROOT / "lib/ide-keymap-generated.lisp"
IDE_DISK = ROOT / "lib/ide-disk.lisp"
HW_UX_HARNESS = ROOT / "scripts/hw-workbench-ux-smoke.sh"
MANIFESTS = tuple(ROOT / f"build/bytecode/dialect-v2/libs/{name}.manifest.json"
                  for name in ("ide", "idex", "m65d"))
SUITES = {
    "ide": ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json",
    "idex": ROOT / "build/bytecode/dialect-v2/suites/p0-ide-extra-lib.json",
}
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-policy-name-implementation-receipt.json"
)


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def defun_body(source: str, name: str, next_name: str) -> str:
    start = source.find(f"(defun {name} ")
    end = source.find(f"(defun {next_name} ", start + 1)
    require(start >= 0 and end > start, f"cannot isolate {name}")
    return source[start:end]


def observation_map(path: Path) -> dict[str, str]:
    suite = Stdlib._read_suite(str(path))
    checked = Stdlib.check_suite(str(path), suite)
    rows: dict[str, str] = {}
    for row in checked["observations"]:
        require(isinstance(row.get("name"), str), "observation name missing")
        value = row.get("result")
        if value is None and isinstance(row.get("error"), str):
            value = f"error:{row['error']}"
        require(isinstance(value, str), f"observation value missing: {row['name']}")
        require(row["name"] not in rows, f"duplicate observation: {row['name']}")
        rows[row["name"]] = value
    return rows


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    prepared = load(PREPARED_RECEIPT)
    authorization = load(LIST_AUTHORIZATION)
    require(contract.get("status") == "owner-authorized-prepared-for-wave2-repin",
            "policy-name owner authorization drift")
    require(prepared.get("status") == "prepared-no-product-change-awaiting-wave2-repin",
            "prepared policy-name audit identity drift")
    require(authorization.get("status") == "owner-authorized-for-common-wave2-repin",
            "common Wave-2 repin authorization missing")

    command_rows = contract["classification"]["command_tokens"]
    commands = {row["name"]: int(row["id"]) for row in command_rows}
    private_name = contract["classification"]["private_state"]["name"]
    revoked = set(commands) | {private_name}
    retained = contract["classification"]["retained_kind_symbol"]["name"]
    require(len(commands) == 15 and len(revoked) == 16,
            "authorized name set cardinality drift")

    source_text = {path: path.read_text(encoding="utf-8") for path in IDE_SOURCES}
    combined = "\n".join(source_text.values())
    for name in sorted(revoked):
        quoted = re.compile(
            rf"(?:'|\(quote\s+){re.escape(name)}(?:\s|\))",
            re.IGNORECASE,
        )
        require(quoted.search(combined) is None,
                f"revoked symbol still appears as data: {name}")
    require("(defun ide-buffers " in source_text[IDE_UI],
            "public ide-buffers function was lost")
    require(source_text[IDE_UI].count("(quote ide-buffers)") >= 4,
            "private buffer state is not consistently on the ide-buffers value cell")
    hw_ux_harness = HW_UX_HARNESS.read_text(encoding="utf-8")
    require("*ide-buffers*" not in hw_ux_harness,
            "hardware UX harness still uses the revoked private buffer-state name")
    require(hw_ux_harness.count("(quote ide-buffers)") >= 6,
            "hardware UX harness does not use the harvested ide-buffers value-cell seam")
    hardware_command_oracles = {
        'run_phase find-tab "(1002 \\"Find file: \\" \\"DEMO\\")"':
            "find-file TAB marker",
        'run_phase buffer-tab "(1006 \\"Buffer: \\" \\"b\\" \\"a\\")"':
            "switch-buffer TAB marker",
        'run_phase mini-history "(1002 \\"Find file: \\" \\"demo\\")"':
            "find-file minibuffer history marker",
        '(list 1002 \\"demo\\")': "find-file minibuffer history payload",
    }
    for snippet, claim in hardware_command_oracles.items():
        require(snippet in hw_ux_harness,
                f"hardware UX harness numeric command drift: {claim}")
    for stale in (
        '(find-file \\"Find file:',
        '(switch-buffer \\"Buffer:',
        '(list (quote find-file)',
    ):
        require(stale not in hw_ux_harness,
                f"hardware UX harness retained revoked command data: {stale}")

    keymap = source_text[IDE_KEYMAP]
    launcher_start = keymap.find("(defun %ide-command-named ")
    require(launcher_start >= 0, "generated M-x launcher missing")
    launcher = keymap[launcher_start:]
    command_names = defun_body(keymap, "ide-command-names", "%ide-command-named")
    require("intern" not in launcher.lower() and "string-ref" not in launcher
            and "string=" in launcher,
            "M-x launcher is not exact String-to-ID")
    display_to_id = {
        "find-file": 1002,
        "save-buffer": 1001,
        "compile-load": 1008,
        "goto-line": 1012,
        "eval-buffer": 1014,
    }
    for displayed, wanted in display_to_id.items():
        require(f'"{displayed}"' in command_names,
                f"public M-x spelling missing: {displayed}")
        require(re.search(rf"\)\s+{wanted}(?:\s|\))", launcher) is not None,
                f"M-x mapping drift: {displayed} -> {wanted}")
    require(commands["write-file"] == 1004 and display_to_id["save-buffer"] == 1001,
            "public save-buffer/internal write-file separation drift")
    require("(function-kind (quote m65d-save)) (quote bytecode)" in source_text[IDE_DISK],
            "bytecode kind seam drift")

    manifests = [load(path) for path in MANIFESTS]
    interned_by_manifest = {
        manifest["name"]: set(manifest["cost"]["symbol_names"])
        for manifest in manifests
    }
    interned = set().union(*interned_by_manifest.values())
    require(not revoked & interned,
            f"revoked names remain interned: {sorted(revoked & interned)}")
    require(retained in interned, "bytecode kind symbol was removed")
    exported = set().union(*(
        set(manifest.get("exports", [])) |
        set(manifest.get("late_bound_exports", [])) |
        set(manifest.get("provides", []))
        for manifest in manifests
    ))
    require(not revoked & exported, "revoked name remains an exported API")

    observed = {name: observation_map(path) for name, path in SUITES.items()}
    echo_specs = {
        "compile-load": ("ide", "ide-event-command-cx-compile-load", "1008"),
        "delete-backward": ("ide", "ide-event-command-delete-backward", "1101"),
        "delete-forward": ("ide", "ide-event-command-delete-forward", "1102"),
        "find-file": ("ide", "ide-event-command-cx-find", "1002"),
        "goto-line": ("ide", "ide-event-command-ctrl-l-goto-line", "1012"),
        "line-end": ("ide", "ide-event-command-ctrl-e-line-end", "1103"),
        "line-start": ("ide", "ide-event-command-ctrl-a-line-start", "1104"),
        "lisp-mode": ("ide", "ide-buffer-default-mode-id", "1105"),
        "move-left": ("ide", "ide-event-command-ctrl-b-move-left", "1106"),
        "move-right": ("ide", "ide-event-command-ctrl-f-move-right", "1107"),
        "move-up": ("ide", "ide-event-command-ctrl-p-move-up", "1108"),
        "newline": ("ide", "ide-event-command-ctrl-j-newline", "1109"),
        "self-insert": ("ide", "ide-event-command-self-insert", "1110"),
        "switch-buffer": ("ide", "ide-event-command-cx-switch-buffer", "1006"),
        "write-file": ("ide", "ide-event-command-cx-write", "1004"),
        "private-buffer-state-survives-ide-reentry":
            ("ide", "ide-persist-state-replaces-front-buffer", "1"),
        "function-kind-still-returns-bytecode":
            ("idex", "ide-extra-hook-overrides-core", "bytecode"),
        "unknown-m-x-command-remains-rejected":
            ("idex", "ide-extra-unknown-mx-command-rejected", "nil"),
    }
    require(list(echo_specs) == contract["echo_cases"], "echo-case order/set drift")
    echoes = []
    for claim, (suite_name, case_name, wanted) in echo_specs.items():
        actual = observed[suite_name].get(case_name)
        require(actual == wanted,
                f"echo case failed: {claim} expected={wanted} actual={actual}")
        echoes.append({
            "claim": claim, "suite": suite_name, "case": case_name,
            "result": actual,
        })

    before = prepared["baseline"]
    after_names = ({retained} | revoked) & interned
    require(before["symbols"] == 17 and before["namepool_bytes"] == 191,
            "prepared baseline arithmetic drift")
    require(after_names == {retained}, "policy-name after-set drift")
    recovery = {
        "symbols": before["symbols"] - len(after_names),
        "namepool_bytes": before["namepool_bytes"] -
            sum(len(name.encode("utf-8")) + 1 for name in after_names),
    }
    require(recovery == {
        "symbols": contract["expected_recovery"]["symbols"],
        "namepool_bytes": contract["expected_recovery"]["namepool_bytes"],
    },
            "measured targeted recovery drift")

    return {
        "format": "lisp65-v11-wave2-policy-name-implementation-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "implemented-passed-awaiting-common-wave2-repin-link",
        "claim_limit": (
            "This receipt proves the source/manifests implementation and all 18 host echo "
            "cases. Final product capacity and product identity belong to the common Wave-2 "
            "repin receipt; hardware behavior remains not-run."
        ),
        "bindings": {
            "contract": binding(CONTRACT),
            "prepared_audit": binding(PREPARED_RECEIPT),
            "common_repin_authorization": binding(LIST_AUTHORIZATION),
            "sources": [binding(path) for path in IDE_SOURCES],
            "hardware_ux_harness": binding(HW_UX_HARNESS),
            "manifests": [binding(path) for path in MANIFESTS],
            "suites": [binding(path) for path in SUITES.values()],
        },
        "harvest": {
            "revoked_names": sorted(revoked),
            "retained_name": retained,
            "before_symbols": 17,
            "after_symbols": 1,
            "recovered_symbols": recovery["symbols"],
            "before_namepool_bytes": 191,
            "after_namepool_bytes": 9,
            "recovered_namepool_bytes": recovery["namepool_bytes"],
            "revoked_names_in_standard_composition": [],
            "bytecode_manifest_owners": sorted(
                name for name, names in interned_by_manifest.items() if retained in names
            ),
        },
        "m_x": {
            "mapping": "String-to-numeric-ID",
            "runtime_intern": False,
            "display_to_id": display_to_id,
            "save_buffer_public_id": 1001,
            "write_file_internal_id": 1004,
        },
        "echo_cases": echoes,
        "summary": {
            "echo_cases": len(echoes),
            "passed": len(echoes),
            "revoked_names_remaining": 0,
            "recovered_symbols": 16,
            "recovered_namepool_bytes": 182,
        },
    }


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    expected = collect()
    require(actual == expected, "policy-name implementation receipt drift")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args()
    try:
        value = write() if args.command == "collect" else check()
    except (AuditError, Stdlib.StdlibCheckError, OSError, ValueError) as exc:
        print(f"v11-wave2-policy-name-implementation: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-wave2-policy-name-implementation: PASS "
        f"echo={value['summary']['passed']}/{value['summary']['echo_cases']} "
        f"symbols=+{value['summary']['recovered_symbols']} "
        f"namepool=+{value['summary']['recovered_namepool_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
