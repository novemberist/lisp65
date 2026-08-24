#!/usr/bin/env python3
"""Attribute the deep v1.6 hybrid feature-projection loss hop by hop."""

from __future__ import annotations

import argparse
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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_input_service_hybrid_final_world_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-final-world-card-final-red.json"
REPORT = ARCH / "c2.3-v1.6-hybrid-deep-projection-attribution.json"
PRODUCT_SOURCE = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
BUILD = ROOT / "build/c2.3/v1.6-hybrid-deep-projection-hop-probe"
PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-deep-projection-hop-preflight"
AUTHORIZATION = "a43ac1ad"
FORMAT = "lisp65-c2-v160-hybrid-deep-projection-attribution-v1"
STATUS = "ATTRIBUTED: CAPTURE EARLY RETURN SKIPPED HYBRID PROJECTION"
CAPTURE = "LISP65_V160_INPUT_CAPTURE"
HYBRID = "LISP65_V160_INPUT_HYBRID"
CONSUMER = "src/optional/c2_kernal_input_consumer.s"


class AttributionError(RuntimeError):
    pass


class ConsumerReached(BaseException):
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


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("host-only attribution", "walks the chain",
                  "exact projection writer", "which value, written where",
                  "no retry", "no successor"):
        require(token in text, f"deep-projection authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_witnesses() -> dict[str, Any]:
    lines = PRODUCT_SOURCE.read_text(encoding="utf-8").splitlines()
    needles = (
        "probe_definitions = input_capture_compile_profile(probe_definitions)",
        "return (*definitions, feature)",
        "hybrid_count = definitions.count(INPUT_HYBRID_FEATURE)",
        "definitions = (*definitions, INPUT_HYBRID_FEATURE)",
        "for path in source_list(probe_definitions):",
    )
    rows: list[dict[str, Any]] = []
    for needle in needles:
        matches = [{"line": index, "text": line.strip()}
                   for index, line in enumerate(lines, 1) if needle in line]
        require(len(matches) == 1, f"projection source witness drift: {needle}")
        rows.extend(matches)
    by_text = {row["text"]: row["line"] for row in rows}
    capture_return = next(row["line"] for row in rows
                          if row["text"] == "return (*definitions, feature)")
    hybrid_count = next(row["line"] for row in rows
                        if row["text"].startswith("hybrid_count ="))
    require(capture_return < hybrid_count,
            "capture early-return no longer precedes hybrid projection")
    return {"source": bind(PRODUCT_SOURCE), "rows": rows,
            "capture_return_precedes_hybrid_projection": True,
            "line_index": by_text}


def real_consumer_probe() -> dict[str, Any]:
    require(not BUILD.exists() and not PREFLIGHT.exists(),
            "deep-projection attribution probe is one-shot")
    CARD.BUILD = BUILD; CARD.PREFLIGHT = PREFLIGHT
    CARD.configure_module()
    core, activation = REOPEN.configure_stack(BUILD, PREFLIGHT)
    before_install = {
        "capture_enabled": PRODUCT.INPUT_CAPTURE_ENABLED,
        "hybrid_enabled": PRODUCT.INPUT_HYBRID_ENABLED,
        "definitions": list(PRODUCT.CONVERGENCE_DEFINES),
        "hybrid_source_selected": PRODUCT.INPUT_HYBRID_SOURCE.resolve() in {
            Path(path).resolve() for path in
            PRODUCT.source_list(PRODUCT.CONVERGENCE_DEFINES)},
    }
    static = core.install_static(BUILD)
    core.bind_paths_only(BUILD, PREFLIGHT); core.write_projections()
    before_producer = {
        "capture_enabled": PRODUCT.INPUT_CAPTURE_ENABLED,
        "hybrid_enabled": PRODUCT.INPUT_HYBRID_ENABLED,
        "definitions": list(PRODUCT.CONVERGENCE_DEFINES),
        "static_consumer_observed_bytes": static["consumer_observed_bytes"],
    }
    captured: dict[str, Any] = {}
    original = PRODUCT.single_link

    def stop(_out: Path, *, probe_definitions: tuple[str, ...] = (),
             **_kwargs: Any) -> None:
        incoming = tuple(probe_definitions)
        projected = PRODUCT.input_capture_compile_profile(incoming)
        selected = [Path(path).relative_to(ROOT).as_posix()
                    for path in PRODUCT.source_list(projected)]
        captured.update({
            "incoming_definitions": list(incoming),
            "global_definitions_at_consumer": list(PRODUCT.CONVERGENCE_DEFINES),
            "capture_enabled_at_consumer": PRODUCT.INPUT_CAPTURE_ENABLED,
            "hybrid_enabled_at_consumer": PRODUCT.INPUT_HYBRID_ENABLED,
            "projected_definitions": list(projected),
            "capture_in_incoming": CAPTURE in incoming,
            "hybrid_in_incoming": HYBRID in incoming,
            "capture_in_projected": CAPTURE in projected,
            "hybrid_in_projected": HYBRID in projected,
            "hybrid_source_selected": CONSUMER in selected,
            "selected_source_count": len(selected),
        })
        raise ConsumerReached()

    PRODUCT.single_link = stop
    try:
        core.PRODUCT.BASE.produce_child()
    except ConsumerReached:
        pass
    finally:
        PRODUCT.single_link = original
    require(captured, "real producer did not reach single_link consumer")
    require(not (BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf").exists(),
            "attribution probe unexpectedly linked a product")
    require(before_install["capture_enabled"] is True
            and before_install["hybrid_enabled"] is True
            and before_install["hybrid_source_selected"] is True
            and before_producer["hybrid_enabled"] is True
            and captured["hybrid_enabled_at_consumer"] is True
            and captured["capture_in_incoming"] is False
            and captured["hybrid_in_incoming"] is False
            and captured["capture_in_projected"] is True
            and captured["hybrid_in_projected"] is False
            and captured["hybrid_source_selected"] is False,
            "deep-projection probe did not reproduce frozen Red")
    return {"activation": activation, "before_core_install": before_install,
            "after_core_install_before_producer": before_producer,
            "real_single_link_consumer": captured,
            "execution": {"WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0}}


def frozen_red() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red["status"] ==
                "FINAL RED: V1.6 HYBRID FINAL-WORLD SUCCESSOR STOPS"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and red["final_world_observation"] == {
                "canonical_consumer_object_present": False,
                "capture_object_present": True,
                "consumer_section_present": False,
                "resolved_profile_hybrid_feature_present": False},
            "frozen final-world Red drift")
    profile_path = ROOT / red["artifacts"]["resolved_profile"]["path"]
    text = profile_path.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines()
               if line.startswith("feature_defines="))
    features = row.removeprefix("feature_defines=").split(",")
    require(CAPTURE in features and HYBRID not in features,
            "frozen compiler profile no longer reproduces Capture-only world")
    return {"Final_Red": bind(FINAL_RED), "resolved_profile": bind(profile_path),
            "compiler_consumed_definitions": features,
            "capture_consumed": True, "hybrid_consumed": False}


def derive() -> dict[str, Any]:
    auth = authority(); red = frozen_red(); probe = real_consumer_probe()
    consumer = probe["real_single_link_consumer"]
    source = source_witnesses()
    return {"format": FORMAT, "recorded_on": "2026-08-20", "status": STATUS,
        "authority": auth, "frozen_red_world": red,
        "hop_chain": [
            {"hop": 1, "writer": "final-world configure_stack",
             "destination": "PRODUCT.CONVERGENCE_DEFINES and activation flags",
             "reader": "core.install",
             "input": {"capture": True, "hybrid": True},
             "output": probe["before_core_install"], "feature_lost": None},
            {"hop": 2, "writer": "core.install configurator closure",
             "destination": "installed product producer state",
             "reader": "core.PRODUCT.BASE.produce_child",
             "input": probe["before_core_install"],
             "output": probe["after_core_install_before_producer"],
             "feature_lost": None},
            {"hop": 3, "writer": "real WPLTO caller",
             "destination": "single_link(probe_definitions)",
             "reader": "input_capture_compile_profile",
             "input": probe["after_core_install_before_producer"],
             "output": {"definitions": consumer["incoming_definitions"],
                        "capture": consumer["capture_in_incoming"],
                        "hybrid": consumer["hybrid_in_incoming"]},
             "feature_lost": "both optional features absent; projector owns closure"},
            {"hop": 4, "writer": "input_capture_compile_profile",
             "destination": "single_link local probe_definitions",
             "reader": "source_list and compiler contract writer",
             "input": {"definitions": consumer["incoming_definitions"],
                       "capture_enabled": consumer["capture_enabled_at_consumer"],
                       "hybrid_enabled": consumer["hybrid_enabled_at_consumer"]},
             "output": {"definitions": consumer["projected_definitions"],
                        "capture": consumer["capture_in_projected"],
                        "hybrid": consumer["hybrid_in_projected"],
                        "hybrid_source_selected":
                            consumer["hybrid_source_selected"]},
             "feature_lost": HYBRID},
            {"hop": 5, "writer": "resolved-profile/compiler input closure",
             "destination": "canonical objects and final ELF",
             "reader": "final-world gate",
             "input": {"definitions": consumer["projected_definitions"]},
             "output": red, "feature_lost": HYBRID},
        ],
        "exact_projection_writer": {
            "function": "c2_product_substitution_link.input_capture_compile_profile",
            "written_value": consumer["projected_definitions"],
            "written_to": "single_link local probe_definitions",
            "read_by": "source_list(probe_definitions) and resolved-profile writer",
            "mechanism": (
                "when Capture is enabled but absent from the incoming tuple, the "
                "Capture branch returns immediately after appending Capture; control "
                "never reaches the following Hybrid projection block"),
            "source_evidence": source,
        },
        "decision": {"classification": "known-family",
            "family": "bound-not-consumed / premature-return projection",
            "new_class": False, "product_behavior_finding": False,
            "wrapper_order_repair_exonerated": True,
            "final_world_gate_exonerated": True,
            "successor_authorized": False},
        "probe_execution": probe["execution"],
        "claim_limit": (
            "Host-only attribution. The probe stops at the real single_link consumer; "
            "no WPLTO, product link, successor, media or device contact.")}


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "deep-projection attribution status drift")
    writer = value.get("exact_projection_writer", {})
    decision = value.get("decision", {})
    hops = value.get("hop_chain", [])
    require(len(hops) == 5 and hops[0]["feature_lost"] is None
            and hops[1]["feature_lost"] is None
            and hops[3]["feature_lost"] == HYBRID,
            "deep-projection hop accounting drift")
    require(writer.get("function") ==
                "c2_product_substitution_link.input_capture_compile_profile"
            and CAPTURE in writer.get("written_value", [])
            and HYBRID not in writer.get("written_value", [])
            and decision == {"classification": "known-family",
                "family": "bound-not-consumed / premature-return projection",
                "new_class": False, "product_behavior_finding": False,
                "wrapper_order_repair_exonerated": True,
                "final_world_gate_exonerated": True,
                "successor_authorized": False}
            and value.get("probe_execution") == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0, "device_contacts": 0},
            "deep-projection writer/decision drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("report", "check", "selftest"))
    action = parser.parse_args().action
    if action == "report":
        value = derive(); validate(value); REPORT.write_bytes(canonical(value))
        print("v1.6 hybrid deep projection: REPORT WRITTEN writer=capture-early-return")
    else:
        value = load(REPORT); validate(value)
        print("v1.6 hybrid deep projection: "
              f"{action.upper()} PASS hops=5 writer=capture-early-return")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 hybrid deep projection: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
