#!/usr/bin/env python3
"""Attribute the artifact-free Link-107 source-owner Final Red."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-card-final-red.json"
RECEIPT = ARCH / "c2.3-v2.1-cpu-transport-card-red-attribution-receipt.json"
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
FIX = ROOT / "tools/host-lisp/c2_v20_map_tuple_fix_card.py"
OBJECTS = ROOT / (
    "build/c2.3/v2.1-cpu-transport-card/wplto/"
    ".canonical-objects-resident-island-seed")
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-14"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def source_gate(product_override: str | None = None,
                fix_override: str | None = None) -> dict[str, Any]:
    product = PRODUCT.read_text(encoding="utf-8") if product_override is None else product_override
    fix = FIX.read_text(encoding="utf-8") if fix_override is None else fix_override
    cpu_scope = (
        '    "name": "map-cpu-library-read",\n'
        '    "trigger": "LISP65_C2_MAP_CPU_TRANSPORT",\n')
    replacement = (
        "    PRODUCT.SOURCE_OWNER_SCOPES = ({\n"
        "        \"name\": \"mapped-far-content-convergence\",\n")
    require(cpu_scope in product, "CPU source owner was not registered pre-producer")
    require(fix.count(replacement) == 1
            and "map-cpu-library-read" not in fix,
            "MAP tuple configurator did not substitute the complete source-owner registry")
    return {
        "status": "PASS: later configurator substitutes rather than extends owner registry",
        "registered_before_real_consumer": [
            "mapped-far-content-convergence", "map-cpu-library-read"],
        "registered_at_real_consumer": ["mapped-far-content-convergence"],
        "discarded_owner": "src/optional/c2_map_cpu_read.s",
        "class": "BOUND-SOURCE-OWNER-NOT-CONSUMED-BY-REAL-PRODUCER",
    }


def object_gate() -> dict[str, Any]:
    require(OBJECTS.is_dir(), "failed-card object directory absent")
    names = sorted(path.name for path in OBJECTS.iterdir() if path.is_file())
    cpu = [name for name in names if "map_cpu_read" in name]
    convergence = [name for name in names if "mapped_far" in name]
    require(cpu == [] and convergence == [
        "059-c2_mapped_far_service_v2.s.o",
        "060-c2_mapped_far_convergence.s.o"],
        "failed-card owner-object inventory does not match attribution")
    return {"object_count": len(names), "CPU_reader_objects": cpu,
            "convergence_owner_objects": convergence}


def validate(value: dict[str, Any]) -> None:
    red = value["final_red"]
    require(red["status"] == "FINAL RED: Link-107 returns to owner"
            and red["retry_authorized"] is False
            and red["owner_disposition_required"] is True,
            "Link-107 Final Red authority drift")
    require(value["root_cause"]["class"]
            == "BOUND-SOURCE-OWNER-NOT-CONSUMED-BY-REAL-PRODUCER"
            and value["objects"]["CPU_reader_objects"] == [],
            "source-owner substitution mechanism weakened")
    require(value["attempt_accounting"] == {
        "cards_consumed": 1, "WPLTO_runs": 1, "product_links_completed": 0,
        "product_ELFs": 0, "product_PRGs": 0, "device_contacts": 0},
        "Link-107 attempt accounting drift")
    require(value["disposition"]["retry_authorized"] is False,
            "attribution silently authorized a replacement card")


def mutations(value: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    product = PRODUCT.read_text(encoding="utf-8")
    fix = FIX.read_text(encoding="utf-8")
    cases = {
        "erase-pre-registered-owner": (product.replace(
            '    "name": "map-cpu-library-read",\n',
            '    "name": "erased-owner",\n', 1), fix),
        "make-configurator-additive": (product, fix.replace(
            "    PRODUCT.SOURCE_OWNER_SCOPES = ({\n",
            "    PRODUCT.SOURCE_OWNER_SCOPES = (*PRODUCT.SOURCE_OWNER_SCOPES, {\n", 1).replace(
            "    },)\n", "    })\n", 1)),
    }
    for name, (product_source, fix_source) in cases.items():
        try:
            source_gate(product_source, fix_source)
        except AttributionError:
            rejected.append(name)
    for name, mutate in {
            "invent-reader-object": lambda x: x["objects"].update(
                CPU_reader_objects=["064-c2_map_cpu_read.s.o"]),
            "invent-product-link": lambda x: x["attempt_accounting"].update(
                product_links_completed=1),
            "authorize-retry": lambda x: x["disposition"].update(
                retry_authorized=True),
    }.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    expected = ["erase-pre-registered-owner", "make-configurator-additive",
                "invent-reader-object", "invent-product-link", "authorize-retry"]
    require(rejected == expected, "Final-Red attribution mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require("undefined symbol: c2_map_cpu_read" in red["error"]["message"],
            "Link-107 undefined-owner signature absent")
    value = {
        "format": "lisp65-c2.3-v2.1-cpu-transport-card-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": "ATTRIBUTED: REAL-PRODUCER-OWNER-REGISTRY-SUBSTITUTION",
        "authority": {"final_red": bind(FINAL_RED), "product": bind(PRODUCT),
                      "map_tuple_configurator": bind(FIX), "driver": bind(DRIVER)},
        "final_red": {key: red[key] for key in (
            "status", "retry_authorized", "owner_disposition_required")},
        "root_cause": source_gate(), "objects": object_gate(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links_completed": 0, "product_ELFs": 0,
            "product_PRGs": 0, "device_contacts": 0},
        "disposition": {
            "retry_authorized": False,
            "owner_decision_required": True,
            "narrow_repair_if_authorized": (
                "make MAP-tuple source replacement identity-targeted/additive, then run the "
                "source-owner gate after configure_fix_source against the real compile list"),
            "why_preflight_missed_it": (
                "preflight validated the default registry before configure_fix_source; it did "
                "not execute the real producer configurator before enumerating sources"),
        },
        "claim_limit": "Desk attribution only. No repair, replay, product or device claim.",
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("2.1 CPU transport: FINAL RED ATTRIBUTED "
          f"class={value['root_cause']['class']} mutations={len(value['mutations_rejected'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, KeyError, ValueError) as error:
        print(f"2.1 CPU transport attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
