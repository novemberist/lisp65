#!/usr/bin/env python3
"""Bind the semantic-preflight Red before the replacement run.

The configured product state was projected, but the bounded continuation
called ``compile_link`` directly and therefore skipped three features owned by
the real final-link wrapper chain.  The first declaration-sensitive TU
(``src/vm.c``) exposed the omission before the authorized replacement run.
"""

from __future__ import annotations

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

import c2_v21_root_padding_configurator_projection_replacement as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FAILED_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-projection-preflight")
FAILED_OBJECTS = FAILED_ROOT / "semantic-objects"
CONTROL_ROOT = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-projection-red-attribution")
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-configurator-projection-preflight-red.json")
DRIVER_COMMIT = "7b4fba80"
FORMAT = "lisp65-c2.3-v2.1-configurator-projection-preflight-red-v1"
STATUS = "PREFLIGHT RED: REAL LINK-WRAPPER FEATURE PROJECTION INCOMPLETE"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def failed_objects() -> list[dict[str, Any]]:
    rows = [bind(path) for path in sorted(FAILED_OBJECTS.glob("*.o"))]
    require(len(rows) == 22, "failed semantic-TU prefix is not 22 objects")
    require([Path(row["path"]).name.split("-", 1)[0] for row in rows]
            == [f"{index:03d}" for index in range(22)],
            "failed semantic-TU prefix ordinals drift")
    return rows


def compile_prefix(projection: dict[str, Any],
                   combined: tuple[str, ...]) -> list[str]:
    command = BASE.RED.parse_command(BASE.load(BASE.PREVIOUS.FINAL_RED))
    compile_at = command.index("-c")
    prefix = command[:compile_at]
    positions = [index for index, token in enumerate(prefix)
                 if token.startswith("-D")]
    require(positions, "failed compiler command has no definitions")
    insert_at = positions[0]
    stripped = [token for token in prefix if not token.startswith("-D")]
    definitions = [
        *projection["final_state"]["compiler_definitions"],
        *BASE.PRODUCT.scoped_probe_definitions(combined),
    ]
    names = [item.split("=", 1)[0] for item in definitions]
    require(len(names) == len(set(names)), "control compiler definitions repeat")
    return [*stripped[:insert_at], *(f"-D{item}" for item in definitions),
            *stripped[insert_at:]]


def compile_control(prefix: list[str], output: Path) -> dict[str, Any]:
    source = ROOT / "src/vm.c"
    completed = subprocess.run(
        [*prefix, "-c", source.relative_to(ROOT).as_posix(), "-o",
         output.relative_to(ROOT).as_posix()], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    value = {
        "source": bind(source), "exit_status": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "undefined_vm_c2d_byte": (
            "undeclared function 'vm_c2d_byte'" in completed.stderr),
    }
    if output.is_file():
        value["object"] = bind(output)
    return value


def capture_real_wrapper_projection() -> tuple[dict[str, Any], dict[str, Any]]:
    captured: dict[str, Any] = {}

    def final_consumer(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path | None = None,
        direct_entry_check_tool: str = "", extra_contract_lines: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        require(not captured, "real final-link consumer invoked twice")
        captured.update({
            "out": out.relative_to(ROOT).as_posix(),
            "probe_definitions": list(probe_definitions),
            "direct_entry_receipt": (
                direct_entry_receipt.relative_to(ROOT).as_posix()
                if direct_entry_receipt is not None else None),
            "direct_entry_check_tool": direct_entry_check_tool,
            "extra_contract_lines": list(extra_contract_lines),
            "extra_arguments": kwargs,
        })

    BASE.PRODUCT.single_link = final_consumer
    old, projection = BASE.configure_projected_candidate()
    BASE.PRODUCT.single_link(
        ROOT / "build/c2.3/configurator-projection-capture-only",
        probe_definitions=BASE.PRODUCT.CONVERGENCE_DEFINES)
    expected = (
        "LISP65_CODE_WINDOW_CONVERGENCE",
        "LISP65_DMA_CONTENT_CONVERGENCE",
        "LISP65_C2_ASM_CONVERGENCE",
        "LISP65_C2_FULL_SPAN_CONVERGENCE",
        "LISP65_C2_MUTABLE_CPU_READS",
        "LISP65_C2_TERMINAL_RETURN_GUARD",
        "LISP65_STARTUP_REQUIRE_EXPERIENCE",
        "LISP65_C2_MAP_CPU_TRANSPORT",
        "LISP65_C2_REQUIRE_RESOLVER",
    )
    require(tuple(captured["probe_definitions"]) == expected,
            "real final-link wrapper feature projection drift")
    return old, {"projection": projection, "consumer": captured}


def validate(value: dict[str, Any]) -> None:
    wrapper = value["real_final_link_consumer"]
    require(
        value.get("status") == STATUS
        and value["failed_semantic_prefix"]["translation_units_green"] == 22
        and value["execution_accounting"] == {
            "semantic_preflight_attempts": 1, "replacement_runs": 0,
            "product_objects": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and wrapper["feature_count"] == 9
        and wrapper["previous_candidate_feature_count"] == 6
        and wrapper["missing_wrapper_features"] == [
            "LISP65_C2_TERMINAL_RETURN_GUARD",
            "LISP65_STARTUP_REQUIRE_EXPERIENCE",
            "LISP65_C2_REQUIRE_RESOLVER"]
        and value["controls"]["unprojected"]["exit_status"] != 0
        and value["controls"]["unprojected"]["undefined_vm_c2d_byte"] is True
        and value["controls"]["real_wrapper_projected"]["exit_status"] == 0
        and value["controls"]["real_wrapper_projected"][
            "undefined_vm_c2d_byte"] is False
        and value["source_owner"]["feature"] == "LISP65_C2_REQUIRE_RESOLVER"
        and value["source_owner"]["source"]["path"] == "src/vm_c2d_byte.s",
        "configurator-projection preflight-Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-run-consumed": lambda x: x["execution_accounting"].update(
            replacement_runs=1),
        "drop-failed-TU": lambda x: x["failed_semantic_prefix"].update(
            translation_units_green=21),
        "hide-negative": lambda x: x["controls"]["unprojected"].update(
            exit_status=0),
        "hide-positive": lambda x: x["controls"][
            "real_wrapper_projected"].update(exit_status=1),
        "drop-resolver-projection": lambda x: x[
            "real_final_link_consumer"]["missing_wrapper_features"].pop(),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "preflight-Red attribution mutation survived")
    return rejected


def record() -> None:
    require(not CONTROL_ROOT.exists() and not RECEIPT.exists(),
            "preflight-Red attribution is one-shot")
    require(not (FAILED_ROOT / "preflight.json").exists(),
            "failed semantic preflight incorrectly persisted PASS")
    require(not BASE.OBJECT_ROOT.exists(),
            "authorized replacement object root exists after preflight Red")
    require(not any(path.exists() for path in BASE.BASE.family(BASE.FINAL)),
            "final product exists after preflight Red")
    CONTROL_ROOT.mkdir(parents=True)
    old: dict[str, Any] | None = None
    try:
        old, captured = capture_real_wrapper_projection()
        projection = captured["projection"]
        prior_profile = tuple(projection["bound_profile_features"])
        prior_candidate = tuple(projection["candidate_scope_features"])
        effective = tuple(captured["consumer"]["probe_definitions"])
        fully_projected = tuple(dict.fromkeys((*prior_profile, *effective)))
        require(len(prior_profile) == 24 and len(prior_candidate) == 6
                and len(effective) == 9 and len(fully_projected) == 33,
                "feature cardinality attribution drift")
        missing = [item for item in effective if item not in prior_candidate]
        negative = compile_control(
            compile_prefix(projection, (*prior_profile, *prior_candidate)),
            CONTROL_ROOT / "unprojected-vm.o")
        positive = compile_control(
            compile_prefix(projection, fully_projected),
            CONTROL_ROOT / "real-wrapper-projected-vm.o")
        resolver_source = ROOT / "src/vm_c2d_byte.s"
        require(str(resolver_source) in BASE.PRODUCT.source_list(effective),
                "real resolver configurator did not own its source")
        value = {
            "format": FORMAT, "recorded_on": "2026-08-17",
            "status": STATUS,
            "authority": {"owner": BASE.authorization(),
                "failed_driver": git_bind(DRIVER_COMMIT, BASE.Path(__file__).with_name(
                    "c2_v21_root_padding_configurator_projection_replacement.py")),
                "attribution_driver": bind(Path(__file__)),
                "bound_profile": bind(BASE.BASE.PROFILE)},
            "failed_semantic_prefix": {"root": FAILED_ROOT.relative_to(ROOT).as_posix(),
                "translation_units_green": 22, "objects": failed_objects(),
                "first_red_source": bind(ROOT / "src/vm.c"),
                "failure": "call to undeclared function vm_c2d_byte"},
            "real_final_link_consumer": {
                **captured["consumer"], "feature_count": len(effective),
                "previous_candidate_features": list(prior_candidate),
                "previous_candidate_feature_count": len(prior_candidate),
                "missing_wrapper_features": missing,
                "fully_projected_feature_count": len(fully_projected)},
            "source_owner": {"feature": "LISP65_C2_REQUIRE_RESOLVER",
                "configurator": BASE.function_binding(
                    BASE.BASE.PREVIOUS.PRODUCER.BASE.L95.BASE.PROBE.REQ.configure),
                "source": bind(resolver_source),
                "source_list_requires_feature": True},
            "controls": {"unprojected": negative,
                "real_wrapper_projected": positive},
            "execution_accounting": {"semantic_preflight_attempts": 1,
                "replacement_runs": 0, "product_objects": 0,
                "final_product_links": 0, "completion_runs": 0,
                "media_builds": 0, "device_contacts": 0},
            "disposition": (
                "Capture the fully composed real final-link consumer after all "
                "configurators, add its features to the profile-derived set, "
                "and rerun all 66 semantic TUs in a new disposable root."),
            "claim_limit": (
                "Preflight attribution only. The authorized replacement run "
                "remains unused; no product artifact exists."),
        }
        validate(value)
        value["mutations_rejected"] = mutations(value)
        RECEIPT.write_bytes(canonical(value))
    finally:
        if old is not None:
            BASE.BASE.PREVIOUS.PRODUCER.BASE.L95.CAN.restore_wplto(old)
    print("configurator projection: PREFLIGHT RED ATTRIBUTED "
          "semantic=22 wrapper=9 missing=3 replacement=0")


def check() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "persisted mutation set drift")
    print("configurator projection: PREFLIGHT RED CHECK PASS")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"record", "check"}:
            raise AttributionError("usage: script {record|check}")
        {"record": record, "check": check}[sys.argv[1]]()
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.SubprocessError) as error:
        print(f"configurator projection preflight Red: {error}", file=sys.stderr)
        raise SystemExit(2)
