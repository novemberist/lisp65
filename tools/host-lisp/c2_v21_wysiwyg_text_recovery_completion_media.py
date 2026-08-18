#!/usr/bin/env python3
"""Complete Link 116 and close its same-world WYSIWYG media.

The persisted Scope and Acceptance are immutable inputs.  This successor
only runs publish-last Completion and the established three-stage media
closure; it cannot enter WPLTO, a product link, a card, Scope or Acceptance.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_full_span_media as BASE  # noqa: E402
import c2_v21_wysiwyg_text_recovery_replacement_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
TAIL = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-artifact-replay-receipt.json")
CARD_BUILD = CARD.BUILD
BASE_BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-media-base"
LIVE_BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-media-liveness"
FAR_BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-media"
BASE_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-base-media-receipt.json")
LIVE_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-liveness-media-receipt.json")
FAR_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-far-media-receipt.json")
PIPELINE_RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-completion-media-pipeline-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-completion-media-receipt.json")
BASE_SESSION = ROOT / "config/c2-v150-v21-wysiwyg-text-recovery-device-session.json"
LIVE_SESSION = ROOT / (
    "config/c2-v150-v21-wysiwyg-text-recovery-live-device-session.json")
FAR_SESSION = ROOT / (
    "config/c2-v150-v21-wysiwyg-text-recovery-far-device-session.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "2b92214f"
LINK = 116
RECORDED_ON = "2026-08-17"
ORIGINAL_CONFIGURE = BASE.configure


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


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
    text = " ".join(raw.decode().lower().split())
    for token in ("read-only qualification tail", "candidate-derived reserve",
                  "persisted green scope and acceptance",
                  "no repeated scope/acceptance", "green opens completion and media"):
        require(token in text, f"Link-116 downstream authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def replay_authority() -> dict[str, Any]:
    value = load(TAIL)
    acceptance = value.get("acceptance", {})
    golden = acceptance.get("VMA_golden", {})
    far = acceptance.get("far_payload", {})
    semantics = value.get("producer_tail", {}).get(
        "linked_WYSIWYG_semantics", {})
    accounting = value.get("execution_accounting", {})
    require(
        value.get("status") == "PASS: Link-116 artifact-only Scope/Acceptance"
        and value.get("frozen_artifacts_before") ==
            value.get("frozen_artifacts_after")
        and value.get("scope", {}).get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and value.get("qualification_tail", {}).get("candidate", {}).get(
            "headroom_bytes") == 251
        and value["qualification_tail"].get(
            "historical_headroom_expectations") == 0
        and accounting.get("WPLTO_runs") == 0
        and accounting.get("product_links") == 0
        and accounting.get("cards_consumed") == 0
        and accounting.get("completion_runs") == 0
        and accounting.get("media_builds") == 0
        and golden.get("dependent_fixed_vmas") == 101
        and golden.get("dependent_free_derived_vmas") == 2
        and far.get("candidate_derived_bytes") == 1248
        and far.get("arena_capacity_bytes") == 1499
        and far.get("candidate_headroom_bytes") == 251
        and far.get("fixed_size_expectation") is False
        and semantics.get("status") ==
            "PASS: linked WYSIWYG behavior; instruction selection free"
        and semantics.get("behavior", {}).get("exhaustive_cases") == 512
        and semantics["behavior"].get("historical_poison_forms") == 2
        and semantics["behavior"].get(
            "historical_poison_forms_canonical_bytes") == 12,
        "green Link-116 qualification-tail authority absent")
    for name, fact in value["frozen_artifacts_before"].items():
        require(fact == bind(ROOT / fact["path"]),
                f"frozen Link-116 artifact drift: {name}")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return deepcopy(replay_authority()["frozen_artifacts_before"])


def card_projection() -> dict[str, Any]:
    value = replay_authority()
    return {"status": "PASS: Link 116 projects frozen tail authority",
        "attempt_accounting": {"cards_authorized": 0, "cards_consumed": 0,
            "device_contacts": 0, "product_link_attempts": 0,
            "wplto_runs": 0, "artifact_replays": 1},
        "acceptance": value["acceptance"],
        "artifacts": value["frozen_artifacts_before"],
        "authority": {"Link116_qualification_tail": bind(TAIL)}}


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    exercised = "\n".join(ast.unparse(functions[name])
                           for name in ("configure", "build", "check"))
    required = ("BASE.build()", "BASE.check()",
                "BASE.replay_authority = replay_authority",
                "BASE.frozen_artifacts = frozen_artifacts",
                "BASE.card_projection = card_projection")
    forbidden = ("CARD.card()", "produce_candidate(", "single_link(",
                 "run_wplto(", "owner_scope(", "acceptance_action(")
    require(all(token in exercised for token in required)
            and all(token not in exercised for token in forbidden),
            "Link-116 downstream adapter can re-enter qualified lifecycle")
    return {"status": "PASS: Link-116 downstream-only Completion/media",
        "additional_WPLTO_runs": 0, "additional_product_links": 0,
        "additional_cards": 0, "scope_repeats": 0,
        "acceptance_repeats": 0}


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "drop-tail-authority": source.replace(
            "    BASE.replay_authority = replay_authority\n", "", 1),
        "drop-frozen-binding": source.replace(
            "    BASE.frozen_artifacts = frozen_artifacts\n", "", 1),
        "reenter-card": source.replace(
            "    return BASE.build()\n",
            "    CARD.card()\n    return BASE.build()\n", 1),
        "repeat-acceptance": source.replace(
            "    return BASE.build()\n",
            "    acceptance_action()\n    return BASE.build()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (MediaError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "Link-116 downstream mutation survived")
    return rejected


def configure() -> None:
    BASE.CARD_BUILD = CARD_BUILD
    BASE.BASE_BUILD = BASE_BUILD
    BASE.LIVE_BUILD = LIVE_BUILD
    BASE.FAR_BUILD = FAR_BUILD
    BASE.BASE_RECEIPT = BASE_RECEIPT
    BASE.LIVE_RECEIPT = LIVE_RECEIPT
    BASE.FAR_RECEIPT = FAR_RECEIPT
    BASE.PIPELINE_RECEIPT = PIPELINE_RECEIPT
    BASE.RECEIPT = RECEIPT
    BASE.BASE_SESSION = BASE_SESSION
    BASE.LIVE_SESSION = LIVE_SESSION
    BASE.FAR_SESSION = FAR_SESSION
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE.REPLAY.RECEIPT = TAIL
    BASE.authorization = authorization
    BASE.resume_authorization = authorization
    BASE.replay_authority = replay_authority
    BASE.frozen_artifacts = frozen_artifacts
    BASE.card_projection = card_projection
    BASE.source_gate = source_gate
    BASE.source_mutations = source_mutations
    BASE.run_child = run_child
    ORIGINAL_CONFIGURE()
    BASE.PIPE.SIZE.RECEIPT = TAIL
    BASE.PIPE.RESUME.RECEIPT = TAIL
    BASE.PIPE.GOLD.RECEIPT = TAIL


def run_child(action: str) -> None:
    environment = os.environ.copy()
    environment.update(
        BASE.PIPE.PIPE.FLOW.BASE.PRODUCER.BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False)
    require(result.returncode == 0,
            f"Link-116 Completion/media child {action} red:\n{result.stdout}")


def child(action: str) -> int:
    configure()
    return BASE.PIPE.child(action)


def expected_geometry() -> dict[str, int]:
    configure()
    value = BASE.PIPE.expected_geometry()
    far = replay_authority()["acceptance"]["far_payload"]
    expected = {"payload_bytes": far["candidate_derived_bytes"],
        "delivered_bytes": int(far["LMA_end_exclusive"], 0)
            - BASE.PIPE.PIPE.FLOW.FAR.role_destination(),
        "arena_capacity_bytes": far["arena_capacity_bytes"],
        "candidate_headroom_bytes": far["candidate_headroom_bytes"]}
    require(value == expected,
            "Link-116 media geometry differs from persisted Acceptance")
    return value


def validate(value: dict[str, Any]) -> None:
    geometry = expected_geometry()
    manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    require(
        value.get("status") ==
            "PASS: Link 116 completed and same-world WYSIWYG media closed"
        and value.get("frozen_before") == frozen_artifacts()
        and value.get("frozen_after") == value["frozen_before"]
        and value.get("media", {}).get("roles") == 19
        and all(value["media"].get(key) == expected
                for key, expected in geometry.items())
        and value["media"].get("same_world") is True
        and value["media"].get("readback") == "byteidentical"
        and value["final_artifacts"].get("manifest") == manifest
        and value["execution_accounting"] == {
            "additional_WPLTO_runs": 0, "additional_product_links": 0,
            "additional_cards": 0, "scope_repeats": 0,
            "acceptance_repeats": 0, "artifact_completions": 1,
            "shared_media_builds": 3, "library_builds": 1,
            "device_contacts": 0}
        and value["hardware_handoff"] == {"D2_resume_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "Link-116 Completion/media summary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link": lambda x: x["execution_accounting"].update(
            additional_product_links=1),
        "repeat-scope": lambda x: x["execution_accounting"].update(
            scope_repeats=1),
        "restore-413": lambda x: x["media"].update(
            candidate_headroom_bytes=413),
        "cross-world": lambda x: x["media"].update(same_world=False),
        "skip-readback": lambda x: x["media"].update(readback="skipped"),
        "open-D3": lambda x: x["hardware_handoff"].update(D3_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except MediaError:
            rejected.append(name)
    require(rejected == list(cases), "Link-116 summary mutation survived")
    return rejected


def summary_value(pipeline: dict[str, Any]) -> dict[str, Any]:
    manifest = bind(CARD_BUILD / "canonical-product-manifest.json")
    far = load(FAR_RECEIPT)
    require(far.get("authority", {}).get("frozen_product_manifest") == manifest,
            "media closure did not consume the Link-116 manifest")
    finals = deepcopy(pipeline["final_artifacts"]); finals["manifest"] = manifest
    return {"format": "lisp65-c2.3-v2.1-wysiwyg-completion-media-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link 116 completed and same-world WYSIWYG media closed",
        "authority": {"owner": authorization(),
            "qualification_tail": bind(TAIL),
            "pipeline": bind(PIPELINE_RECEIPT), "driver": bind(DRIVER)},
        "frozen_before": pipeline["frozen_before"],
        "frozen_after": pipeline["frozen_after"],
        "completion": pipeline["completion"],
        "final_artifacts": finals,
        "media": pipeline["media"],
        "source_gate": source_gate(),
        "source_mutations_rejected": source_mutations(),
        "execution_accounting": {"additional_WPLTO_runs": 0,
            "additional_product_links": 0, "additional_cards": 0,
            "scope_repeats": 0, "acceptance_repeats": 0,
            "artifact_completions": 1, "shared_media_builds": 3,
            "library_builds": 1, "device_contacts": 0},
        "hardware_handoff": {"D2_resume_ready": True,
            "D3_D5_open": False, "session": bind(FAR_SESSION)},
        "claim_limit": "Host Completion/media only; D2 not run; D3-D5 closed."}


def install() -> None:
    configure()
    BASE.expected_geometry = expected_geometry
    BASE.validate = validate
    BASE.mutations = mutations
    BASE.summary_value = summary_value


def build() -> int:
    install(); replay_authority(); source_gate(); source_mutations()
    return BASE.build()


def check() -> int:
    install()
    return BASE.check()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "_complete",
        "_base", "_base_check", "_liveness", "_liveness_check", "_far",
        "_far_check", "_finalize_far", "_rebind_base", "_rebind_liveness"))
    action = parser.parse_args().action
    if action == "build":
        return build()
    if action == "check":
        return check()
    install()
    return child(action)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 WYSIWYG Completion/media: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
