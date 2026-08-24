#!/usr/bin/env python3
"""Attribute the frozen eleventh-R1 scope identity disagreement."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v1.6-r1-graph-collective-adapter-replacement-final-red.json")
ELF = ROOT / (
    "build/c2.3/v1.6-r1-graph-collective-adapter-replacement/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ROOT / (
    "build/c2.3/v1.6-r1-graph-collective-adapter-replacement/wplto/"
    "lisp65-c2-substitution-linked.prg")
RECEIPT = ARCH / "c2.3-v1.6-r1-scope-identity-attribution-receipt.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "3c2636dc"
STATUS = "ATTRIBUTED: R1 SCOPE BOUNDARY RETURNS PRE-COMPONENT PROJECTION"
FORMAT = "lisp65-c2-v160-r1-scope-identity-attribution-v1"
SCOPE = "mapped-far-content-convergence"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
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
    for token in ("host-only attribution", "frozen pair",
                  "lays both identities side by side", "source of each side",
                  "no successor card is authorized"):
        require(token in text, f"scope attribution authority absent: {token}")
    return value


def capture() -> dict[str, Any]:
    """Reproduce only the configured scope seam in a fresh process."""
    import c2_v160_r1_graph_collective_adapter_replacement as top
    top.PREV.configure_module = top.configure_module
    top.configure_module()
    core = top.PREV.PREV.PREV.CORE
    core.install()
    core.PRODUCT.BASE.configure()

    import c2_v160_r1_stored_world_conversions as conversion
    projection_function = conversion.MAP_CARD.configure_fix_source
    harness_function = conversion.MAP_CARD.PRODUCT.source_owner_scope_selftest
    projected = projection_function()
    harness = harness_function()
    projected_row = next(row for row in projected["scopes"]
                         if row["name"] == SCOPE)
    harness_row = next(row for row in harness["selected"]["scopes"]
                       if row["name"] == SCOPE)
    component = projected["components"]["abort_driver_relocation"]
    return {"projected_row_raw": projected_row,
        "harness_row_raw": harness_row,
        "abort_component_raw": component,
        "all_projected_rows_raw": projected["scopes"],
        "all_harness_rows_raw": harness["selected"]["scopes"],
        "provenance": {
            "projection_callable": {
                "module": projection_function.__module__,
                "name": projection_function.__name__,
                "source": Path(inspect.getsourcefile(
                    projection_function)).relative_to(ROOT).as_posix(),
                "first_line": projection_function.__code__.co_firstlineno,
            },
            "harness_callable": {
                "module": harness_function.__module__,
                "name": harness_function.__name__,
                "source": Path(inspect.getsourcefile(
                    harness_function)).relative_to(ROOT).as_posix(),
                "first_line": harness_function.__code__.co_firstlineno,
            },
        }}


def run_capture() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_capture"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, f"scope capture red: {result.stderr}")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "scope capture returned no object")
    return value


def identity(row: dict[str, Any]) -> dict[str, Any]:
    sources = []
    for name in row["sources"]:
        path = ROOT / name
        sources.append(bind(path))
    raw = canonical({"name": row["name"], "selected": row["selected"],
        "defines": row["defines"], "sources": sources})
    return {"name": row["name"], "selected": row["selected"],
        "defines": row["defines"], "sources": sources,
        "identity_sha256": hashlib.sha256(raw).hexdigest()}


def structural_order_gate(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    start = source.index("    def configure_root_source()")
    end = source.index("\n\n", start)
    body = source[start:end]
    tokens = ("projection = current()", "component = configure(product)",
              'components["abort_driver_relocation"] = component',
              'projection["components"] = components', "return projection")
    require(all(token in body for token in tokens)
            and [body.index(token) for token in tokens] == sorted(
                body.index(token) for token in tokens)
            and 'projection["scopes"]' not in body,
            "root projection/component ordering witness drift")
    return {"status": "passed-returned-projection-precedes-component-mutation",
        "ordered_operations": list(tokens),
        "scope_projection_refreshed_after_component": False,
        "source": bind(path)}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red["status"] ==
                "FINAL RED: R1 ADAPTER REPLACEMENT RETURNS TO OWNER"
            and red["retry_authorized"] is False
            and red["owner_disposition_required"] is True
            and red["artifacts"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and "scope identity differs from candidate projection"
                in red["error"]["message"],
            "scope attribution frozen Red authority drift")
    captured = run_capture()
    projected = identity(captured["projected_row_raw"])
    harness = identity(captured["harness_row_raw"])
    component = captured["abort_component_raw"]
    component_sources = sorted(component["sources"])
    component_defines = sorted(component["definitions"])
    require(projected["identity_sha256"] != harness["identity_sha256"]
            and component_sources == captured["harness_row_raw"]["sources"]
            and component_defines == captured["harness_row_raw"]["defines"]
            and component["feature"] in harness["defines"]
            and component["feature"] not in projected["defines"],
            "scope identity decision is not mechanically separated")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    abort = truth.symbol("c2_abort_driver")
    facade = truth.symbol("c2_abort_driver_facade")
    far = truth.section(".lisp65_c2_mapped_far_service")
    require(abort.section == far.name and abort.bytes == 134
            and facade.section == ".lisp65_c2_mapped_far_facade"
            and facade.bytes == 9 and far.bytes == 1382,
            "frozen ELF does not carry the R1 abort component")
    elf_witness = {"abort_driver": {"VMA": f"0x{abort.value:04x}",
            "bytes": abort.bytes, "section": abort.section},
        "abort_facade": {"VMA": f"0x{facade.value:04x}",
            "bytes": facade.bytes, "section": facade.section},
        "far_service_bytes": far.bytes,
        "matches_harness_abort_component": True}

    config_path = ROOT / captured["provenance"]["projection_callable"]["source"]
    ordering = structural_order_gate(config_path)
    return {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": STATUS,
        "claim_limit": "Host-only attribution over frozen Red artifacts and fresh-process configuration; no qualification, fix, link, card, media, or device.",
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_authorized": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_evidence": {"Final_Red": bind(FINAL_RED),
            "ELF": bind(ELF), "PRG": bind(PRG)},
        "raw_first_capture": captured,
        "identity_comparison": {"returned_candidate_projection": projected,
            "scope_harness_expected": harness,
            "identities_equal": False},
        "emitted_ELF_witness": elf_witness,
        "projection_order_witness": ordering,
        "decision": {
            "classification": "incomplete-candidate-projection-at-scope-boundary",
            "persisted_earlier_world_identity_in_harness": False,
            "scope_harness_matches_abort_component": True,
            "scope_harness_matches_frozen_ELF": True,
            "returned_projection_omits_installed_abort_component": True,
            "mechanical_basis": (
                "The root wrapper captures projection=current() before "
                "configure(product), then adds only component metadata and "
                "returns without refreshing projection.scopes. The live "
                "scope harness and frozen ELF both carry the abort component."),
        },
        "disposition": {"successor_cards_authorized": 0,
            "required_successor_class": "candidate scope-projection repair",
            "collective_conversions_must_be_rechecked": True,
            "owner_release_required": True},
        "authority": {"owner": authorization(), "driver": bind(DRIVER)},
        "next": "owner review; no successor card is authorized"}


def validate(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "scope attribution receipt drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "_capture"))
    action = parser.parse_args().action
    if action == "_capture":
        print(json.dumps(capture(), sort_keys=True))
    elif action == "write":
        require(not RECEIPT.exists(), "scope attribution receipt already exists")
        RECEIPT.write_bytes(canonical(derive()))
        print("R1 scope identity: ATTRIBUTED incomplete-projection card=0 link=0")
    else:
        validate(load(RECEIPT))
        print("R1 scope identity: CHECK PASS incomplete-projection card=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"R1 scope identity attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
