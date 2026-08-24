#!/usr/bin/env python3
"""Loudly rebind the unchanged facade-padding contract to the live producer."""

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_probe_oracle_root_facade_padding as PADDING  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREDECESSOR = ARCH / (
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-16.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-facade-padding-linker-producer-rebind-2026-08-17.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7d49bb5d"
FORMAT = "lisp65-c2.3-v2.1-facade-padding-producer-rebind-v1"
STATUS = "PASS: loud facade-padding linker-producer rebind"
SEAL_ERA_COMMIT = "323e3e2396fe985dfbd495c936a69d6b95aeaa0b"
SEALED_MUTATIONS = [
    "change-source", "change-linker", "change-configuration",
    "resize-facade", "accept-implicit", "claim-product",
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
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
                          cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def projection() -> dict[str, Any]:
    historical = load(PADDING.RECEIPT)
    predecessor = load(PREDECESSOR)
    current = {
        "source_contract": PADDING.source_contract(),
        "linked_contract": PADDING.linked_contract(),
        "configuration": PADDING.configuration_contract(),
    }
    require(
        predecessor.get("status") == "PASS: loud linker-producer authority rebind"
        and historical["source_contract"] == current["source_contract"]
        and historical["linked_contract"] == current["linked_contract"]
        and historical["configuration"] == current["configuration"]
        and predecessor["authority"]["authorized_linker_producer"]
            != bind(PADDING.LINKER_PRODUCER),
        "facade-padding semantic rebind premise drift")
    return {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"owner": git_bind(AUTHORIZATION, PLAN),
            "historical_padding": bind(PADDING.RECEIPT),
            "predecessor_rebind": bind(PREDECESSOR),
            "authorized_linker_producer": ERA.era_bind(
                SEAL_ERA_COMMIT, PADDING.LINKER_PRODUCER),
            "driver": ERA.era_bind(SEAL_ERA_COMMIT, DRIVER)},
        "semantic_preservation": {
            "source_contract_equal": True,
            "linked_contract_equal": True,
            "configuration_contract_equal": True,
            "facade_bytes": current["linked_contract"]["fixed_facade_bytes"],
            "padding_bytes": current["linked_contract"]["padding_bytes"],
            "implicit_filler_accepted": current["linked_contract"]
                ["implicit_filler_accepted"],
            "product_artifacts_changed": False,
            "WPLTO_runs": 0, "product_links": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0,
        },
        "current_projection": current,
        "claim_limit": (
            "Loud tool-authority rebind only. The explicit 19-byte filler, "
            "98-byte facade and every product artifact remain unchanged."),
    }


def validate(value: dict[str, Any]) -> None:
    semantic = value["semantic_preservation"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and semantic["source_contract_equal"] is True
            and semantic["linked_contract_equal"] is True
            and semantic["configuration_contract_equal"] is True
            and semantic["facade_bytes"] == 98
            and semantic["padding_bytes"] == 19
            and semantic["implicit_filler_accepted"] is False
            and semantic["product_artifacts_changed"] is False
            and semantic["WPLTO_runs"] == semantic["product_links"] == 0,
            "facade-padding producer rebind drift")
    require(value.get("authority", {}).get("authorized_linker_producer") ==
            ERA.era_bind(SEAL_ERA_COMMIT, PADDING.LINKER_PRODUCER)
            and value.get("authority", {}).get("driver") ==
            ERA.era_bind(SEAL_ERA_COMMIT, DRIVER),
            "facade-padding tool provenance escaped its sealing era")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "change-source": lambda x: x["semantic_preservation"].update(
            source_contract_equal=False),
        "change-linker": lambda x: x["semantic_preservation"].update(
            linked_contract_equal=False),
        "change-configuration": lambda x: x["semantic_preservation"].update(
            configuration_contract_equal=False),
        "resize-facade": lambda x: x["semantic_preservation"].update(
            facade_bytes=97),
        "accept-implicit": lambda x: x["semantic_preservation"].update(
            implicit_filler_accepted=True),
        "claim-product": lambda x: x["semantic_preservation"].update(
            product_artifacts_changed=True),
        "collapse-era-to-live": lambda x: x["authority"].update(
            authorized_linker_producer=ERA.era_bind(
                "HEAD", PADDING.LINKER_PRODUCER)),
        "restore-working-tree-binding": lambda x: x["authority"].update(
            driver=bind(DRIVER)),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "facade-padding rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "facade-padding rebind already exists")
    value = projection(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("facade-padding producer rebind: PASS facade=98 pad=19 mutations=6")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    current = projection()
    require(rejected == SEALED_MUTATIONS
            and len(mutations(value)) == 8
            and value["authority"]["authorized_linker_producer"]["path"]
                == current["authority"]["authorized_linker_producer"]["path"]
            and value["current_projection"] == current["current_projection"],
            "facade-padding live producer rebind drift")
    print("facade-padding producer rebind: CHECK PASS facade=98 pad=19 mutations=8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    {"record": record, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"facade-padding producer rebind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
