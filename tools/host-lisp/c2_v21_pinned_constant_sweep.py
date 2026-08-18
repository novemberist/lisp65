#!/usr/bin/env python3
"""Close pinned address/size/identity constants on the Link-107 remainder."""

from __future__ import annotations

import argparse
import ast
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


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
LINK50 = HOST / "c2_lite_v6_link50_persistent_header_successor_link.py"
LINK49 = HOST / "c2_lite_v6_link49_append_final_hybrid_facade16_successor_link.py"
LINK47 = HOST / "c2_lite_v6_link47_l65e_transient_successor_link.py"
RTOV = HOST / "c2_lite_v6_rtov_crc_real_abi_successor_link.py"
CANONICAL = HOST / "c2_lite_canonical_product.py"
MODERN = HOST / "c2_v150_candidate_product.py"
AMBIENT = HOST / "c2_v150_qualification_ambient_closure.py"
PREDECESSOR = ARCH / "c2.3-v2.1-local-return-identity-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-local-return-identity-card-red-attribution-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-pinned-constant-sweep-receipt.json"
EXPECTATION_SHAPE = (
    ARCH / "c2.3-v2.1-expectation-shape-sweep-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d615bcf4"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v21-pinned-constant-sweep-v1"
STATUS = "PASS: remaining qualification constants candidate-derived; pinned=0"


class SweepError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SweepError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "pinned-address sweep commissioned", "broaden-once",
            "one-time pinned-constant sweep",
            "every pinned one converts or dies", "one card"):
        require(token in text, f"pinned sweep authorization absent: {token}")
    return authority


def sources(overrides: dict[str, str] | None = None) -> dict[str, str]:
    values = {name: path.read_text(encoding="utf-8") for name, path in {
        "link50": LINK50, "link49": LINK49, "link47": LINK47,
        "rtov": RTOV, "canonical": CANONICAL, "modern": MODERN,
        "ambient": AMBIENT}.items()}
    if overrides:
        values.update(overrides)
    return values


def function(text: str, name: str) -> ast.FunctionDef:
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, f"unique qualification function absent: {name}")
    return nodes[0]


def expressions(node: ast.AST) -> set[str]:
    return {ast.unparse(item) for item in ast.walk(node)}


def integer_literals(node: ast.AST) -> set[int]:
    return {item.value for item in ast.walk(node)
            if isinstance(item, ast.Constant)
            and isinstance(item.value, int) and not isinstance(item.value, bool)}


def source_gate(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    text = sources(overrides)
    link50 = function(text["link50"], "corrected_replacement")
    link49 = function(text["link49"], "replacement")
    link47 = function(text["link47"], "replacement")
    rtov = function(text["rtov"], "build")
    configure = function(text["canonical"], "configure_wplto")
    replay = function(text["modern"], "post_link_replay")
    ambient = function(text["ambient"], "source_gate")
    e50, e49, e47, ertov = (expressions(node) for node in (
        link50, link49, link47, rtov))
    econfigure, ereplay, eambient = (expressions(node) for node in (
        configure, replay, ambient))

    require(
        "artifact_root = elf.parent" in e50
        and "verifier = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "
            "'llvm-readobj').section(P.VERIFIER_BINDING_SECTION)" in e50
        and "BASE.ART.stage_product_gate(elf, verifier_base=verifier.address)"
            in e50
        and "BASE.ART.stage_product_gate(elf)" not in e50
        and "expected_sections=set(family['overlay_sections'])" in e50
        and "BASE_LINK.DIRECT.OUT = artifact_root" in e50
        and "BASE_LINK.OUT = artifact_root" in e50,
        "Link-50 replacement retains a default, ambient or historical identity")
    require(
        "expected = {'.lisp65_c2_host_facade': (46532, 48)" not in text["link49"]
        and "walls == {'bank0_text_headroom_bytes': 37" not in text["link49"]
        and "capacity['session_family_bytes'] == 65438" not in e49
        and "append['walker']['facade']['address'] == 46577" not in e49
        and "actual == expected" not in e49
        and "append_facade.value" in e49
        and "walls['e000_headroom_bytes']" in e49
        and not (integer_literals(link49) - {0, 1}),
        "Link-49 remainder retains pinned address/size expectations")
    require(
        "L65E_CONTRACT.read_text" not in e47
        and "LINK44.P.E000_FINAL_FLOOR_BYTES" not in e47
        and "capacity['session_family_bytes'] <= 65536" not in e47
        and "renderer_slice['cap_bytes'] - renderer_slice['bytes']" in e47
        and "walls['e000_headroom_bytes']" in e47
        and not (integer_literals(link47) - {0}),
        "Link-47 remainder retains pinned shape or capacity expectations")
    require(
        "declared_domain_bytes = sum((int(row['bytes']) for row in "
            "total.get('declared_domains', ())))" in ertov
        and "total.get('declared_domain_bytes') == 42" not in ertov,
        "publish-last remainder retains a pinned domain size")
    require(
        "LINK50.VERIFIER_BASE = PRODUCT.LINK60_VERIFIER_BINDING_BASE"
            in econfigure
        and "LINK50.BASE.VERIFIER_BASE = "
            "PRODUCT.LINK60_VERIFIER_BINDING_BASE" in econfigure
        and "verifier.bytes == P.runtime_binding_bytes()" in text["link50"],
        "final Link-50 identity is not candidate-contract-derived")
    require(
        "verifier_base=can.PRODUCT.LINK60_VERIFIER_BINDING_BASE" in ereplay
        and "stage-historical-verifier-base" in text["ambient"]
        and "ART.stage_product_gate(elf, verifier_base=verifier_base)"
            in text["ambient"],
        "modern qualification precedent no longer rejects the default pin")

    inventory = [
        ("replacement.artifact-root", "candidate-ELF-parent-derived"),
        ("replacement.verifier-address", "candidate-ELF-section-derived"),
        ("replacement.verifier-size", "candidate-product-contract-derived"),
        ("replacement.overlay-membership", "candidate-family-derived"),
        ("link47.renderer-size", "candidate-linked-slice-derived"),
        ("link47.wall-sizes", "candidate-replacement-derived"),
        ("link47.session-size", "candidate-capacity-derived"),
        ("link49.section-addresses", "candidate-ELF-section-derived"),
        ("link49.section-sizes", "candidate-ELF-section-derived"),
        ("link49.append-facade-identity", "candidate-ELF-symbol-derived"),
        ("link49.E000-floor", "candidate-wall-derived"),
        ("publish-last-domain-size", "candidate-declared-domains-derived"),
        ("final.verifier-address", "candidate-configure-derived"),
        ("final.verifier-size", "candidate-product-contract-derived"),
    ]
    converted = [
        "implicit-stage-verifier-default-0xb9cd",
        "historical-link49-section-address-and-size-table",
        "historical-link49-wall-and-capacity-shape",
        "historical-link49-append-facade-identity",
        "historical-link47-renderer-shape",
        "historical-link47-E000-and-bank-size",
        "historical-publish-last-domain-size-42",
    ]
    return {
        "status": "passed-complete-pinned-constant-sweep",
        "scope": "actual Link-107 remaining replacement and completion path",
        "expectations": [
            {"id": name, "classification": classification, "pinned": False}
            for name, classification in inventory],
        "expectation_count": len(inventory),
        "candidate_derived_count": len(inventory),
        "pinned_count": 0,
        "converted_or_retired_pins": converted,
        "converted_or_retired_count": len(converted),
        "rule": (
            "Every address, size and identity expectation on the remaining "
            "qualification path derives from the passed candidate or its "
            "bound current contract; historical numeric snapshots are forbidden."),
    }


def source_mutations() -> list[str]:
    base = sources()
    cases: list[tuple[str, str, str, str]] = [
        ("restore-implicit-0xb9cd-stage-default", "link50",
         "stage = BASE.ART.stage_product_gate(\n        elf, verifier_base=verifier.address)",
         "stage = BASE.ART.stage_product_gate(elf)"),
        ("restore-link49-section-table", "link49",
         "section_names = (", "expected = {'.lisp65_c2_host_facade': (46532, 48)}\n        section_names = ("),
        ("restore-link49-wall-pin", "link49",
         "all(int(value) >= 0 for value in walls.values())",
         "walls == {'bank0_text_headroom_bytes': 37}"),
        ("restore-link49-facade-pin", "link49",
         "append_facade.value", "46577"),
        ("restore-link47-renderer-contract-pin", "link47",
         "renderer_slice = renderer[\"slice\"]",
         "expected = json.loads(L65E_CONTRACT.read_text())[\"renderer\"][\"l65e_expected_shape\"]\n        renderer_slice = renderer[\"slice\"]"),
        ("restore-link47-E000-pin", "link47",
         "walls[\"e000_headroom_bytes\"]",
         "LINK44.P.E000_FINAL_FLOOR_BYTES"),
        ("restore-publish-last-42", "rtov",
         "total.get(\"declared_domain_bytes\")\n                    == declared_domain_bytes",
         "total.get(\"declared_domain_bytes\") == 42"),
    ]
    rejected: list[str] = []
    for name, role, old, new in cases:
        require(old in base[role], f"pinned mutation anchor absent: {name}")
        mutant = dict(base)
        mutant[role] = mutant[role].replace(old, new, 1)
        try:
            source_gate(mutant)
        except (SweepError, SyntaxError):
            rejected.append(name)
    require(rejected == [name for name, *_rest in cases],
            "pinned-constant source mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    predecessor = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    require(predecessor.get("retry_authorized") is False
            and attribution.get("status") ==
                "ATTRIBUTED FINAL RED: legacy qualification stage pins verifier base"
            and attribution["new_final_red"]["implicit_expected_address"]
                == "0xb9cd"
            and attribution["new_final_red"]["candidate_address"] == "0xb98c",
            "pinned-address Final Red authority drift")
    gate = source_gate()
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "sweep": gate, "mutations_rejected": source_mutations(),
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER),
            "sources": {name: bind(path) for name, path in {
                "link50": LINK50, "link49": LINK49, "link47": LINK47,
                "rtov": RTOV, "canonical": CANONICAL,
                "modern": MODERN, "ambient": AMBIENT}.items()}},
        "claim_limit": (
            "Host-only one-time constant closure. No WPLTO, product link, "
            "completion, medium or device action."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    sweep = value.get("sweep", {})
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and sweep.get("pinned_count") == 0
            and sweep.get("expectation_count") ==
                sweep.get("candidate_derived_count")
            and sweep.get("converted_or_retired_count") == 7
            and value.get("mutations_rejected") == source_mutations(),
            "pinned-constant sweep receipt drift")
    if verify:
        expected = derive()
        if value != expected:
            successor = load(EXPECTATION_SHAPE)
            successor_authority = successor.get("authority", {})
            require(
                successor.get("status") ==
                    "PASS: remaining candidate expectation forms derive or classify"
                and successor.get("sweep", {}).get(
                    "pinned_candidate_shape_count") == 0
                and successor_authority.get("canonical_consumer") ==
                    bind(CANONICAL)
                and successor_authority.get("ambient_closure") ==
                    bind(AMBIENT)
                and successor_authority.get("prior_constant_sweep_driver") ==
                    bind(DRIVER),
                "pinned-constant successor authority drift")
            recorded_projection = deepcopy(value)
            current_projection = deepcopy(expected)
            for projection in (recorded_projection, current_projection):
                projection["authority"].pop("driver")
                projection["authority"]["sources"].pop("canonical")
                projection["authority"]["sources"].pop("ambient")
            require(
                recorded_projection == current_projection,
                "pinned-constant sweep drift exceeds the successor-bound "
                "canonical-consumer/driver rebind")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-pinned-constant": lambda x: x["sweep"].update(pinned_count=1),
        "drop-expectation": lambda x: x["sweep"]["expectations"].pop(),
        "claim-incomplete-conversion": lambda x: x["sweep"].update(
            converted_or_retired_count=6),
        "detach-authorization": lambda x: x["authority"]["authorization"].update(
            sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except SweepError:
            rejected.append(name)
    require(rejected == list(cases), "pinned sweep receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "pinned-constant sweep receipt exists")
    value = derive(); validate(value, verify=True)
    value["receipt_mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 pinned-constant sweep: PASS expectations=14 pinned=0 "
          "conversions=7 mutations=11")


def check() -> None:
    value = load(RECEIPT)
    receipt_rejected = value.pop("receipt_mutations_rejected", None)
    validate(value, verify=True)
    require(receipt_rejected == receipt_mutations(value),
            "pinned sweep receipt mutation set drift")
    print("2.1 pinned-constant sweep: CHECK PASS expectations=14 pinned=0")


def selftest() -> None:
    value = derive(); validate(value, verify=True); receipt_mutations(value)
    print("2.1 pinned-constant sweep: SELFTEST PASS mutations=11")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SweepError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 pinned-constant sweep: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
