#!/usr/bin/env python3
"""Resume execution-boundary Scope qualification over its frozen pair."""

from __future__ import annotations

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

import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_execution_boundary_backstop_uint8_irq_return_replacement_card as TOP  # noqa: E402
import c2_v160_input_fidelity_reopen_card as CORE  # noqa: E402
import c2_v160_input_fidelity_reopen_replacement_card as LEAF  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ATTRIBUTION = ARCH / "c2.3-v1.6-projection-mutation-population-attribution.json"
RED = ARCH / (
    "c2.3-v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card-final-red.json")
RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-scope-resume.json"
AUTHORIZATION = "f2730e34"
FORMAT = "lisp65-c2-v160-execution-boundary-scope-resume-v1"
STATUS = "PASS: V1.6 EXECUTION BOUNDARY SCOPE CLOSED READ-ONLY"


class ResumeError(RuntimeError):
    pass


class ScopeCaptured(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


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
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("read-only scope/qualification resume",
                  "frozen sha-identical pair", "no rebuild, no wplto, no card",
                  "artifact-only media", "seam confirmation contact"):
        require(token in text, f"Scope-resume authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair() -> dict[str, dict[str, Any]]:
    attribution = load(ATTRIBUTION)
    require(attribution["decision"] == {
                "branch": "legitimately-grown-population",
                "exact_new_member": "LISP65_C2_REFILL_BOUNDARY_WITNESS",
                "gate_integrity_defect": False,
                "scope_resume_authorized": False,
                "successor": "candidate-derived named population; no stored count"}
            and attribution["candidate_world"]["mutation_population"][
                "survivors"] == [],
            "mutation-population attribution drift")
    pair = attribution["frozen_world"]
    observed = {name: bind(ROOT / pair[name]["path"])
                for name in ("ELF", "PRG")}
    require(observed == {name: pair[name] for name in ("ELF", "PRG")},
            "frozen execution-boundary pair identity drift")
    return observed


def configured_scope() -> dict[str, Any]:
    captured: dict[str, Any] = {}
    original_child = LEAF.child
    previous_argv = sys.argv

    def intercept(action: str) -> None:
        require(action == "_scope", f"unexpected resume action: {action}")
        captured.update(FIDELITY.derive(
            CORE.PRODUCT_ELF, output_rebind=CORE.bind_paths_only,
            expected_output_roots=CORE.roots()))
        raise ScopeCaptured

    LEAF.child = intercept
    sys.argv = [str(Path(__file__)), "_scope"]
    try:
        TOP.main()
    except ScopeCaptured:
        pass
    finally:
        sys.argv = previous_argv
        LEAF.child = original_child
    require(captured, "real configured Scope consumer was not reached")
    return captured


def derive() -> dict[str, Any]:
    red = load(RED)
    require(red["status"] == "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS"
            and red["error"]["message"] ==
                "feature-without-configurator-output mutation survived",
            "execution-boundary Scope predecessor drift")
    before = frozen_pair()
    host = configured_scope()
    producer = load(CORE.PRODUCER_RESULT)
    scope = load(CORE.SCOPE_RESULT)
    acceptance = load(CORE.ACCEPTANCE_RESULT)
    require(producer["status"] == scope["status"] == acceptance["status"] == "PASS",
            "persisted product/Scope/Acceptance tail is not green")
    require(host["status"] ==
                "HOST-GREEN: FINAL ELF PROVES LOSSLESS COMFORT CAPTURE"
            and host["loss"]["status"] == "passed"
            and host["placement"]["status"] == "passed-final-linked-ELF",
            "resumed real Scope consumer is not host-green")
    after = frozen_pair()
    require(before == after, "read-only Scope resume changed frozen pair")
    return {
        "format": FORMAT, "recorded_on": "2026-08-23", "status": STATUS,
        "authority": authority(), "predecessor_Final_Red": bind(RED),
        "mutation_population_attribution": bind(ATTRIBUTION),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "persisted_tail": {"producer": bind(CORE.PRODUCER_RESULT),
            "scope": bind(CORE.SCOPE_RESULT),
            "acceptance": bind(CORE.ACCEPTANCE_RESULT)},
        "configured_scope": host,
        "execution": {"scope_qualification_resumes": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "artifact-only media, then seam-confirmation contact",
        "claim_limit": (
            "Read-only Scope qualification over the frozen final pair; no "
            "card, rebuild, WPLTO, link, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["configured_scope"]["status"].startswith("HOST-GREEN:")
            and value["execution"] == {"scope_qualification_resumes": 1,
                "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0},
            "execution-boundary Scope resume receipt drift")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in {"resume", "check"}, "usage: resume|check")
    if action == "resume":
        require(not RECEIPT.exists(), "execution-boundary Scope resume is one-shot")
        value = derive(); validate(value); RECEIPT.write_bytes(canonical(value))
    else:
        value = load(RECEIPT); validate(value)
        require(frozen_pair() == value["frozen_pair_after"],
                "Scope resume pair drift after sealing")
    print("v1.6 execution boundary: SCOPE RESUME PASS pair=SHA-identical "
          "WPLTO=0 link=0 card=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResumeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.6 execution boundary Scope resume: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
