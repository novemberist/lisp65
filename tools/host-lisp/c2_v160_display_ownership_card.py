#!/usr/bin/env python3
"""Build the authorized Bank-2 Comfort display-ownership successor card."""

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

import bytecode_p0_stdlib as P  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v160_queue_owner_cold_relocation_card as QUEUE  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
RESIDENT = ROOT / "tests/bytecode/libs/p0-repl-comfort-resident.json"
PRODUCT_ELF = QUEUE.BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
QUEUE_CLOSURE = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-resume-receipt.json"
BUILD = ROOT / "build/c2.3/v1.6-display-ownership-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-display-ownership-preflight"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = ARCH / "c2.3-v1.6-display-ownership-card-receipt.json"
RED = ARCH / "c2.3-v1.6-display-ownership-card-final-red.json"
AUTHORIZATION = "516a73fc"
DISPLAY_SEALING_COMMIT = "36063046bf5b37a6700a85328ef66fa831b3337d"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("%rl-screen-tail", "%fasl-fs reclaim", "33 free slots",
                  "594 name bytes", "real-framebuffer gate",
                  "viewport arithmetic", "all standing walls"):
        require(token in text, f"display card authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def compile_library(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    artifact = root / "repl-comfort"
    observations = root / "observations.json"
    command = [sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check", "--artifact-role", "disk-lib", "--emit-artifacts",
        str(artifact.relative_to(ROOT)), "--observation-report",
        str(observations.relative_to(ROOT)), str(SUITE.relative_to(ROOT))]
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0 and "bytecode-p0-stdlib-check: PASS" in run.stdout,
            "display card real library consumer red:\n" + run.stdout)
    manifest_path = artifact.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    rows = {row["name"]: row["length"] for row in manifest["entries"]}
    require(set(rows) == {"%repl-read", "%repl-step", "repl"}
            and max(rows.values()) <= 255
            and manifest["objects"] == 3,
            f"display card object contract drift: {rows}")
    path_fields = ("blob", "c_source", "directory", "disasm", "header")
    normalized_manifest = json.loads(json.dumps(manifest))
    for key in path_fields:
        normalized_manifest[key] = Path(normalized_manifest[key]).name
    normalized_manifest["external_image"]["path"] = Path(
        normalized_manifest["external_image"]["path"]).name
    manifest_semantic_sha = hashlib.sha256(canonical(normalized_manifest)).hexdigest()
    return {"artifacts": {name: bind(path) for name, path in (
            ("manifest", manifest_path),
            ("blob", artifact.with_suffix(".blob.bin")),
            ("directory", artifact.with_suffix(".dir.bin")),
            ("observations", observations))},
        "objects": rows, "code_bytes": manifest["code_bytes"],
        "largest_object_bytes": max(rows.values()),
        "manifest_semantic_sha256": manifest_semantic_sha,
        "stdout_tail": " ".join(run.stdout.split()[-24:])}


def library_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {"objects": value["objects"], "code_bytes": value["code_bytes"],
        "largest_object_bytes": value["largest_object_bytes"],
        "manifest_semantic_sha256": value["manifest_semantic_sha256"],
        "artifact_content": {name: {"bytes": row["bytes"],
            "sha256": row["sha256"]} for name, row in value["artifacts"].items()
            if name != "manifest"}}


def final_world() -> dict[str, Any]:
    display = DISPLAY.derive()
    artifacts = display["artifacts"]
    composed = display["composed_framebuffer"]
    require(display["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF"
            and artifacts["largest_bytes"] <= 255
            and artifacts["new_names"] == artifacts["reclaimed_names"] == 1
            and composed["active_row"] == "l65> (list 1 3)"
            and composed["result_row"] == "(1 3)"
            and composed["result_tail_blank"] is True
            and composed["maximum_characters"] == 250
            and composed["left_scroll_prefix"].startswith("l65> cde"),
            "display final-world claims are not all enforced")
    return display


def predecessor() -> dict[str, Any]:
    closure = load(QUEUE_CLOSURE)
    require(closure["status"] ==
                "PASS: V1.6 QUEUE-OWNER COLD RELOCATION CLOSED READ-ONLY"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"],
            "queue-owner final-world predecessor drift")
    return closure


def sealed_final_world_projection(
        living: dict[str, Any], sealed: dict[str, Any]) -> dict[str, Any]:
    """Keep historical display provenance in the world that sealed it.

    Later Comfort work is required to pass the living display gate, but it
    cannot rewrite the source identities recorded by this completed card.
    Product and emitted library artifacts remain live predicates in check().
    """
    require(living["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF",
            "living display ownership claims are not green")
    historical = sealed.get("final_world")
    require(isinstance(historical, dict),
            "sealed display final-world projection absent")
    authorities = historical.get("authority")
    require(isinstance(authorities, dict) and authorities,
            "sealed display authority projection absent")
    for name, row in authorities.items():
        require(isinstance(row, dict) and isinstance(row.get("path"), str)
                and ERA.era_bind(DISPLAY_SEALING_COMMIT, row["path"]) == row,
                f"sealed display {name} provenance drift")
    return historical


def sealed_projection_selftest() -> int:
    sealed = load(RECEIPT)
    living = copy.deepcopy(sealed["final_world"])
    living["authority"]["editor"]["bytes"] += 1
    living["authority"]["editor"]["sha256"] = "living-editor"
    require(sealed_final_world_projection(living, sealed)
                == sealed["final_world"],
            "living display identity remained a sealed predicate")
    rejected = 2  # the old byte-count and SHA equality both differ above
    malformed = copy.deepcopy(sealed)
    malformed["final_world"]["authority"]["editor"]["sha256"] = "0" * 64
    try:
        sealed_final_world_projection(living, malformed)
    except CardError:
        rejected += 1
    require(rejected == 3, "sealed display projection mutation survived")
    return rejected


def preflight() -> None:
    require(not any(path.exists() for path in
                    (PREFLIGHT, BUILD, INVOCATION, RECEIPT, RED)),
            "display ownership card is one-shot")
    before = bind(PRODUCT_ELF)
    value = {"format": "lisp65-c2-v160-display-ownership-preflight-v1",
        "recorded_on": "2026-08-22",
        "status": "PASS: DISPLAY OWNERSHIP CARD ARMED 0/1",
        "authority": authority(), "queue_closure": bind(QUEUE_CLOSURE),
        "product_elf": before, "final_world": final_world(),
        "library": compile_library(PREFLIGHT),
        "capacity": {"bias_adjusted_free": {"symbol_slots": 33,
            "namepool_bytes": 594}, "release_minimum": {
            "symbol_slots": 32, "namepool_bytes": 384}},
        "execution": {"cards_consumed": 0, "library_builds": 1,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0}}
    require(bind(PRODUCT_ELF) == before, "preflight changed final product ELF")
    (PREFLIGHT / "preflight.json").write_bytes(canonical(value))
    print("v1.6 display ownership: PREFLIGHT PASS card=0/1 "
          "objects<=255 slots=33/594 framebuffer=composed")


def card() -> None:
    require((PREFLIGHT / "preflight.json").is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists() and not RED.exists(),
            "display ownership card lifecycle drift")
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == "PASS: DISPLAY OWNERSHIP CARD ARMED 0/1",
            "display preflight status drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "card": "1/1",
        "authority": authority(), "preflight": bind(PREFLIGHT / "preflight.json")}))
    before = bind(PRODUCT_ELF)
    library = compile_library(BUILD)
    display = final_world()
    require(library["artifacts"]["manifest"]["path"]
                != pre["library"]["artifacts"]["manifest"]["path"],
            "preflight and card unexpectedly share an output owner")
    require(library_identity(library) == library_identity(pre["library"]),
            "real card library content differs from its real-consumer preflight")
    require(display == pre["final_world"],
            "real card display claims differ from preflight")
    require(bind(PRODUCT_ELF) == before == pre["product_elf"],
            "Bank-2 display card changed final product ELF")
    predecessor()
    value = {"format": "lisp65-c2-v160-display-ownership-card-v1",
        "recorded_on": "2026-08-22",
        "status": "PASS: V1.6 DISPLAY OWNERSHIP GREEN",
        "authority": authority(), "preflight": bind(PREFLIGHT / "preflight.json"),
        "queue_closure": bind(QUEUE_CLOSURE), "product_elf": before,
        "library": library, "final_world": display,
        "capacity": pre["capacity"],
        "execution": {"cards_consumed": 1, "library_builds": 1,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "fresh same-world media and sixth owner contact"}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 display ownership: CARD PASS card=1/1 "
          "objects<=255 slots=33/594 framebuffer=composed")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or RED.exists():
        return
    RED.write_bytes(canonical({
        "format": "lisp65-c2-v160-display-ownership-card-final-red-v1",
        "recorded_on": "2026-08-22",
        "status": "FINAL RED: DISPLAY OWNERSHIP CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": authority(), "invocation": bind(INVOCATION),
        "execution": {"cards_consumed": 1, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False}))


def check() -> None:
    value = load(RECEIPT)
    living = final_world()
    require(value["status"] == "PASS: V1.6 DISPLAY OWNERSHIP GREEN"
            and value["final_world"]
                == sealed_final_world_projection(living, value)
            and value["product_elf"] == bind(PRODUCT_ELF),
            "display ownership card receipt drift")
    for row in value["library"]["artifacts"].values():
        require(bind(ROOT / row["path"]) == row,
                f"display card artifact drift: {row['path']}")
    sealed_projection_selftest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "card":
        card()
    else:
        check()
        print("v1.6 display ownership card: CHECK PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"display Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 display ownership card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
