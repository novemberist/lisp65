#!/usr/bin/env python3
"""Attribute the false-green v1.6 hybrid-consumer acceptance receipt."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-card"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
OBJECTS = WPLTO / ".canonical-objects-lisp65-c2-substitution-linked"
CARD_RECEIPT = ARCH / (
    "c2.3-v1.6-input-service-hybrid-phase-output-consumption-card-receipt.json")
PRODUCER_RESULT = BUILD / "producer-result.json"
REPORT = ARCH / "c2.3-v1.6-hybrid-consumer-absence-attribution.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
HYBRID_CARD = ROOT / "tools/host-lisp/c2_v160_input_service_hybrid_card.py"
REOPEN_CARD = ROOT / "tools/host-lisp/c2_v160_input_fidelity_reopen_card.py"
HYBRID_GATE = ROOT / "tools/host-lisp/c2_v160_input_service_hybrid.py"
AUTHORIZATION = "3fe17b87"
FORMAT = "lisp65-c2-v160-hybrid-consumer-absence-attribution-v1"
STATUS = "ATTRIBUTED: HYBRID CONSUMER WAS BOUND AFTER THE REAL COMPILER WORLD"
SECTION = ".lisp65_c2_kernal_window.input_consumer"
FEATURE = "LISP65_V160_INPUT_HYBRID"
SOURCE = "src/optional/c2_kernal_input_consumer.s"


class AttributionError(RuntimeError):
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
    for token in ("which world is true", "hybrid_consumer_present: false",
                  "a receipt may not record a claim-relevant value",
                  "why did the reviewer's verification not see it"):
        require(token in text, f"attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_lines(path: Path, needles: tuple[str, ...]) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[dict[str, Any]] = []
    for needle in needles:
        matches = [{"line": index, "text": line.strip()}
                   for index, line in enumerate(lines, 1) if needle in line]
        require(matches, f"source-order witness absent: {path.name}: {needle}")
        found.extend(matches)
    return {"source": bind(path), "witnesses": found}


def final_elf_truth() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    sections = {row.name for row in truth.sections}
    symbols = {row.name for row in truth.symbols}
    consumer_objects = sorted(path.name for path in OBJECTS.glob("*.o")
                              if "input_consumer" in path.name)
    capture_objects = sorted(path.name for path in OBJECTS.glob("*.o")
                             if "input_capture" in path.name)
    profile = PROFILE.read_text(encoding="utf-8")
    require(SECTION not in sections and not consumer_objects
            and FEATURE not in profile and SOURCE not in profile,
            "frozen final compiler world unexpectedly contains hybrid consumer")
    require(capture_objects == ["052-c2_kernal_input_capture.s.o"],
            "frozen final capture object identity drift")
    consumer_symbols = sorted(name for name in symbols
                              if "input" in name.lower()
                              and ("ring" in name.lower()
                                   or "consumer" in name.lower()))
    return {
        "arbiter": "ElfTruth plus real WPLTO profile and canonical object closure",
        "ELF": bind(ELF), "PRG": bind(PRG), "resolved_profile": bind(PROFILE),
        "canonical_object_count": len(list(OBJECTS.glob("*.o"))),
        "capture_objects": capture_objects,
        "consumer_objects": consumer_objects,
        "hybrid_feature_consumed": FEATURE in profile,
        "hybrid_source_consumed": SOURCE in profile,
        "consumer_section_present": SECTION in sections,
        "consumer_symbols": consumer_symbols,
        "verdict": "real-product-link-never-consumed-67-byte-consumer",
    }


def receipt_world() -> dict[str, Any]:
    receipt = load(CARD_RECEIPT)
    producer = load(PRODUCER_RESULT)
    native = receipt["hybrid_host_gates"]["native_scalar"]
    placement = receipt["placement"]
    profile = receipt["real_hybrid_profile"]
    require(receipt["status"] ==
                "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN"
            and native == {"bytes": 67, "ceiling": 70, "section": SECTION}
            and placement["hybrid_consumer_present"] is False
            and profile["status"] == "passed-real-profile-hybrid-consumption",
            "accepted false-green receipt evidence drift")
    post = producer.get("post_configuration_source_owner_gate", {})
    return {
        "accepted_receipt": bind(CARD_RECEIPT),
        "accepted_status": receipt["status"],
        "standalone_source_object_proof": native,
        "fresh_probe_projection": profile,
        "final_link_placement_observation": {
            "status": placement["status"],
            "ELF": placement["ELF"],
            "hybrid_consumer_present": placement["hybrid_consumer_present"],
        },
        "late_post_configuration_projection": post,
        "producer_result": bind(PRODUCER_RESULT),
    }


def configuration_order() -> dict[str, Any]:
    reopen = source_lines(REOPEN_CARD, (
        "core.install(build, preflight)",
        "PRODUCT_LINK.configure_input_capture()"))
    hybrid = source_lines(HYBRID_CARD, (
        "core, activation = current(",
        'activation["hybrid"] = PRODUCT.configure_input_hybrid()'))
    native = source_lines(HYBRID_GATE, (
        'def native_gate(',
        '"-c", str(CONSUMER), "-o", str(obj)'))
    install_line = next(row["line"] for row in reopen["witnesses"]
                        if "core.install" in row["text"])
    capture_line = next(row["line"] for row in reopen["witnesses"]
                        if "configure_input_capture" in row["text"])
    current_line = next(row["line"] for row in hybrid["witnesses"]
                        if "current(" in row["text"])
    hybrid_line = next(row["line"] for row in hybrid["witnesses"]
                       if "configure_input_hybrid" in row["text"])
    require(install_line < capture_line and current_line < hybrid_line,
            "configuration-order attribution drift")
    return {
        "classification": "bound-not-consumed / capture-after-install ordering",
        "exact_writer": "c2_v160_input_service_hybrid_card.configure_module wrapper",
        "mechanism": (
            "the wrapper runs the inherited configure_stack through core.install "
            "before configure_input_hybrid mutates the product globals; the fresh "
            "probe and post-configuration registry see that later mutation, while "
            "the already-installed real compiler world does not"),
        "reopen_order": reopen, "hybrid_wrapper_order": hybrid,
        "standalone_native_gate": native,
    }


def enforce_claims(receipt: dict[str, Any]) -> None:
    require(receipt.get("status") ==
                "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN",
            "hybrid claim status absent")
    placement = receipt.get("placement")
    require(isinstance(placement, dict), "claim-relevant placement absent")
    require(placement.get("hybrid_consumer_present") is True,
            "green hybrid claim records absent final-ELF consumer")
    native = receipt.get("hybrid_host_gates", {}).get("native_scalar", {})
    require(native.get("bytes") == 67 and native.get("section") == SECTION,
            "hybrid native source-object proof absent")


def enforcement_mutations(receipt: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "recorded-false-not-walled": lambda x: x["placement"].update(
            hybrid_consumer_present=False),
        "claim-field-omitted": lambda x: x["placement"].pop(
            "hybrid_consumer_present", None),
        "standalone-proof-substituted-for-linked-presence": lambda x: (
            x["placement"].update(hybrid_consumer_present=False),
            x["hybrid_host_gates"]["native_scalar"].update(bytes=67)),
    }
    rejected: dict[str, str] = {}
    baseline = deepcopy(receipt)
    baseline["placement"]["hybrid_consumer_present"] = True
    enforce_claims(baseline)
    for name, mutate in cases.items():
        trial = deepcopy(baseline); mutate(trial)
        try:
            enforce_claims(trial)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"claim-enforcement mutation survived: {name}")
    return rejected


def derive() -> dict[str, Any]:
    auth = authority()
    final = final_elf_truth()
    recorded = receipt_world()
    accepted = load(CARD_RECEIPT)
    mutations = enforcement_mutations(accepted)
    require(len(mutations) == 3, "claim-enforcement mutation accounting drift")
    return {
        "format": FORMAT, "recorded_on": "2026-08-20", "status": STATUS,
        "authority": auth,
        "question_1_world_truth": {
            "answer": "the real product link omitted the consumer",
            "final_compiler_world": final,
            "bound_but_nonfinal_world": recorded,
            "configuration_order": configuration_order(),
            "consequence": (
                "the 67-byte, responsiveness, normalization and loss gates prove "
                "host components or a synthetic profile, not their presence in the "
                "final product; those claims require re-verification on a successor"),
        },
        "question_2_false_green": {
            "answer": (
                "input_fidelity_reopen_host placement recorded the final-ELF false "
                "value, but neither the card nor acceptance validator required true"),
            "recorded_value": False,
            "why_green": (
                "the standalone 67-byte native gate and fresh profile probe were "
                "independent PASS claims; placement's presence field was telemetry"),
            "permanent_rule": (
                "A receipt may not record a claim-relevant value it does not enforce."),
            "claim_enforcement_mutations_rejected": mutations,
        },
        "question_3_review_blind_spot": {
            "answer": (
                "the review re-ran the reported gates in situ, but none joined the "
                "final ELF to the real compiler profile and consumer section"),
            "blind_dimensions": [
                "standalone object size was mistaken for linked membership",
                "fresh synthetic profile was mistaken for the producing compiler",
                "capacity/placement was checked while its false membership field was not",
            ],
            "review_correction": (
                "verification of a product claim must include the final linked artifact "
                "and turn every claim-relevant recorded predicate into an assertion"),
        },
        "classification": {
            "family": "bound-not-consumed",
            "layer": "compile-profile installation order",
            "product_finding": True,
            "accepted_product_reached_hybrid_consumer": False,
            "media_builds_authorized": 0,
            "device_contacts_authorized": 0,
            "successor_authorized": False,
        },
        "claim_limit": (
            "Host-only attribution over the frozen accepted pair. No source fix, "
            "WPLTO, link, media, device contact or successor authorization."),
    }


def validate_report(value: dict[str, Any]) -> None:
    truth = value.get("question_1_world_truth", {}).get(
        "final_compiler_world", {})
    false_green = value.get("question_2_false_green", {})
    review = value.get("question_3_review_blind_spot", {})
    classification = value.get("classification", {})
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "hybrid-consumer attribution status drift")
    require(truth.get("ELF", {}).get("sha256") ==
                "6832bb9596431fe63ec2202ee58ee7762e8acdff1a2e0500b2e5ee39c4cfc0d1"
            and truth.get("consumer_section_present") is False
            and truth.get("consumer_objects") == []
            and truth.get("hybrid_feature_consumed") is False,
            "persisted final compiler-world finding drift")
    require(false_green.get("recorded_value") is False
            and len(false_green.get(
                "claim_enforcement_mutations_rejected", {})) == 3
            and "final ELF" in review.get("answer", "")
            and classification == {
                "family": "bound-not-consumed",
                "layer": "compile-profile installation order",
                "product_finding": True,
                "accepted_product_reached_hybrid_consumer": False,
                "media_builds_authorized": 0,
                "device_contacts_authorized": 0,
                "successor_authorized": False,
            }, "persisted false-green/review classification drift")


def check() -> None:
    actual = load(REPORT)
    validate_report(actual)
    print("v1.6 hybrid consumer absence attribution: CHECK PASS "
          "final-consumer=absent false-green=walled mutations=3")


def selftest() -> None:
    validate_report(load(REPORT))
    synthetic = {
        "status": "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN",
        "placement": {"hybrid_consumer_present": True},
        "hybrid_host_gates": {"native_scalar": {
            "bytes": 67, "ceiling": 70, "section": SECTION}},
    }
    require(len(enforcement_mutations(synthetic)) == 3,
            "claim-enforcement selftest mutation drift")
    print("v1.6 hybrid consumer absence attribution: SELFTEST PASS "
          "worlds=2 mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("report", "check", "selftest"))
    action = parser.parse_args().action
    if action == "report":
        REPORT.write_bytes(canonical(derive()))
        print("v1.6 hybrid consumer absence attribution: REPORT WRITTEN")
    elif action == "check":
        check()
    else:
        selftest()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 hybrid consumer absence attribution: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
