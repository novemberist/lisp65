#!/usr/bin/env python3
"""Enforce the identity and physical blind spots of the DWX Xemu prefilter."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import dwx_keymap_transport as KEYMAP


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
LINK73_CONTRACT_PATH = ROOT / "config/dwx-xemu-link73-contract.json"
LINK73_RECEIPT_PATH = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-link73-xemu-boot-receipt-20260902.json"
RECEIPT_PATH = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-prefilter-blind-spot-contract-receipt-20260902.json"
REPORT_PATH = ROOT / "docs/planning/dwx-blind-spot-contract-report.md"
WORK_PLAN_PATH = ROOT / "docs/planning/dwx-delivered-world-executor-work-plan.md"
UPSTREAM_DRAFT_PATH = ROOT / "docs/upstream-issue-drafts.md"
UPSTREAM_REGISTER_PATH = ROOT / "docs/upstream-findings.md"
CYCLE_MANIFEST_PATH = ROOT / "build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json"

ROW_IDS = (
    "freezer-entry-return",
    "dma-visibility-completion-timing",
    "fpga-core-identity",
    "native-latency-and-typing-feel",
    "uart-hwa-versus-physical-keyboard",
    "patched-xemu-fork-identity",
)
BLIND_IDS = ROW_IDS[:-1]
SEALED_ITEM2_ROW_IDS = ROW_IDS[:4] + ROW_IDS[-1:]
SEALED_ITEM2_BLIND_IDS = ROW_IDS[:4]
INJECTION_VALID_CLAIMS = (
    "typed-event-queue-counter-equality",
    "typed-event-queue-order-preserved",
    "typed-event-queue-losslessness",
)
IDENTITY_FIELDS = (
    "source_commit",
    "patches",
    "patched_source_sha256",
    "binary_sha256",
)
SEALED_ITEM2_IDENTITY_FIELDS = (
    "source_commit",
    "source_file_sha256",
    "patch_sha256",
    "patched_source_sha256",
    "binary_sha256",
)
PATCH_ROLES = ("base_patch", "transport_patch", "cycle_patch")
SEALED_ITEM2_MUTATIONS = (
    "claim-capability-core-specific-defect-closed",
    "claim-capability-dma-completion-timing-bounded",
    "claim-capability-dma-content-visible-on-completion",
    "claim-capability-fpga-rtl-behavior-proven",
    "claim-capability-freezer-entry-correct",
    "claim-capability-freezer-return-correct",
    "claim-capability-gc-hitch-imperceptible",
    "claim-capability-l10-closed",
    "claim-capability-native-single-key-latency-green",
    "claim-capability-post-freezer-state-restored",
    "claim-capability-tested-core-equivalent",
    "claim-capability-typing-feel-accepted",
    "claim-over-dma-visibility-completion-timing",
    "claim-over-fpga-core-identity",
    "claim-over-freezer-entry-return",
    "claim-over-native-latency-and-typing-feel",
    "device-row-omitted",
    "fork-identity-field-missing",
    "prefilter-promoted-to-device-acceptance",
    "unpatched-or-other-binary-substituted",
)


class ContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"expected an object in {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-prefilter-blind-spot-contract-v3",
        "unexpected blind-spot contract format",
    )
    require(contract.get("status") == "ACTIVE", "blind-spot contract is not active")
    require(
        contract.get("evidence_class") == "xemu-prefilter-green",
        "prefilter evidence class drift",
    )
    require(
        contract.get("authority_rule")
        == "Xemu is a functional prefilter, never device acceptance authority.",
        "prefilter authority rule drift",
    )
    rows = contract.get("contract_rows")
    require(isinstance(rows, list), "contract_rows must be a list")
    require(tuple(row.get("id") for row in rows) == ROW_IDS, "contract row population drift")
    for row in rows[:-1]:
        require(row.get("kind") == "blind-spot", f"{row.get('id')} lost blind-spot kind")
        require(row.get("device_mandatory") is True, f"{row.get('id')} is not device-mandatory")
        claims = row.get("forbidden_prefilter_claims")
        require(
            isinstance(claims, list) and len(claims) >= 1 and len(claims) == len(set(claims)),
            f"{row.get('id')} has no unique forbidden claim population",
        )
    injection_row = rows[-2]
    require(
        tuple(injection_row.get("valid_prefilter_claims", ()))
        == INJECTION_VALID_CLAIMS,
        "UART/HWA row lost its queue-only valid claim population",
    )
    identity_row = rows[-1]
    require(identity_row.get("kind") == "tool-identity", "fork row lost tool-identity kind")
    require(identity_row.get("device_mandatory") is False, "fork identity became a device row")
    require(
        identity_row.get("unpatched_xemu_is_equivalent") is False,
        "unpatched Xemu was treated as the qualified fork",
    )
    require(
        tuple(identity_row.get("required_on_every_prefilter_claim", ())) == IDENTITY_FIELDS,
        "required prefilter identity field population drift",
    )

    identity = contract.get("qualified_tool_identity")
    require(isinstance(identity, dict), "qualified_tool_identity must be an object")
    require(set(identity) == set(IDENTITY_FIELDS), "qualified tool identity fields drift")
    for field in ("source_commit", "binary_sha256"):
        require(
            isinstance(identity[field], str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", identity[field]) is not None,
            f"qualified identity {field} is malformed",
        )
    patches = identity.get("patches")
    require(
        isinstance(patches, list)
        and tuple(row.get("role") for row in patches) == PATCH_ROLES
        and all(set(row) == {"role", "path", "sha256"} for row in patches),
        "qualified three-patch population drift",
    )
    for row in patches:
        path = ROOT / str(row["path"])
        require(path.is_file() and sha256(path) == row["sha256"],
                f"qualified patch identity drift: {row['role']}")
    sources = identity.get("patched_source_sha256")
    navigation = contract.get("navigation_transport", {})
    expected_events = [list(event) for event in KEYMAP.population()]
    require(
        isinstance(sources, dict) and isinstance(navigation, dict)
        and navigation.get("events") == expected_events
        and navigation.get("dropped_event_mutations") == expected_events
        and navigation.get("authority", {}).get("sha256") == sha256(KEYMAP.AUTHORITY)
        and navigation.get("header", {}).get("sha256") == hashlib.sha256(
            KEYMAP.render(KEYMAP.population()).encode()).hexdigest()
        and sources.get(KEYMAP.HEADER) == navigation.get("header", {}).get("sha256"),
        "derived navigation population/provenance incomplete",
    )
    require(
        isinstance(sources, dict) and len(sources) == 10
        and "targets/mega65/dwx_keymap_generated.h" in sources
        and all(re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in sources.values()),
        "qualified patched-source population drift",
    )

    sealed = contract.get("sealed_item2_tool_identity")
    require(isinstance(sealed, dict)
            and set(sealed) == set(SEALED_ITEM2_IDENTITY_FIELDS),
            "sealed Item-2 tool identity drift")

    references = contract.get("hardware_references")
    require(
        isinstance(references, list)
        and [(row.get("pdf_page"), row.get("printed_page"), row.get("section")) for row in references]
        == [(134, 120, "Buffered Sector Operations"), (135, 121, "Buffered Sector Operations")],
        "hardware reference population or page binding drift",
    )
    for reference in references:
        reference_path = ROOT / str(reference.get("path"))
        require(reference_path.is_file(), "hardware reference is missing")
        require(sha256(reference_path) == reference.get("sha256"), "hardware reference SHA drift")
    require(
        "03b24c6b" in references[1].get("claim", "")
        and "contradiction" in references[1].get("claim", "")
        and sources.get("xemu/f011_core.c") == "d8b5b3fc6d1ba202b7e4b4d79a17b3c78b0702030a09a39786f50cfd81b29611",
        "F011 completion reference lost core authority or restored EQ patch",
    )
    confirmations = contract.get("device_confirmation_rows")
    require(
        isinstance(confirmations, list)
        and len(confirmations) == 1
        and confirmations[0].get("id") == "card2-f011-d082-success-status"
        and confirmations[0].get("device_mandatory") is True
        and "($D082 & $D8) == $40" in confirmations[0].get("oracle", "")
        and "product finding" in confirmations[0].get("disagreement_disposition", ""),
        "card-2 physical status confirmation row drift",
    )
    runtime = contract.get("runtime_requalification")
    binding = runtime.get("receipt") if isinstance(runtime, dict) else None
    runtime_path = ROOT / str(binding.get("path", "")) if isinstance(binding, dict) else ROOT
    require(
        isinstance(runtime, dict)
        and isinstance(binding, dict)
        and runtime_path.is_file()
        and sha256(runtime_path) == binding.get("sha256")
        and runtime.get("framebuffer_sha256") == "000c4a3a9de447297c76360a6ce0ed3810d8d708158bf36396091ac925d2be8c"
        and runtime.get("screenshot_sha256") == "677483700fc2415178f39c994b3ead06d8578b57ea2998e2e1cfbf99a61061e1"
        and runtime.get("device_acceptance_claimed") is False,
        "four-patch runtime requalification binding drift",
    )
    runtime_receipt = load_json(runtime_path)
    require(
        runtime_receipt.get("status") == "PASS"
        and runtime_receipt.get("prefilter_tool_identity") == identity
        and runtime_receipt.get("framebuffer_oracle", {}).get("passed") is True
        and runtime_receipt.get("outputs", {}).get("framebuffer", {}).get("sha256")
        == runtime["framebuffer_sha256"]
        and runtime_receipt.get("outputs", {}).get("screenshot", {}).get("sha256")
        == runtime["screenshot_sha256"],
        "four-patch runtime requalification did not execute the qualified identity",
    )
    outward = contract.get("outward_items")
    require(
        isinstance(outward, list)
        and [row.get("id") for row in outward] == ["X2", "X3"]
        and all(row.get("status") == "OWNER_REVIEW_REQUIRED_NOT_FILED" for row in outward),
        "outward items lost their owner-held status",
    )


def forbidden_claims(contract: dict[str, Any]) -> set[str]:
    rows = contract["contract_rows"]
    return {
        claim
        for row in rows[:-1]
        for claim in row["forbidden_prefilter_claims"]
    }


def validate_prefilter_claim(claim: dict[str, Any], contract: dict[str, Any]) -> None:
    require(
        set(claim)
        == {
            "evidence_class",
            "tool_identity",
            "prefilter_rows",
            "device_mandatory_rows",
            "device_acceptance_claimed",
        },
        "prefilter claim schema drift",
    )
    require(
        claim.get("evidence_class") == contract["evidence_class"],
        "prefilter claim elevated or changed its evidence class",
    )
    require(claim.get("device_acceptance_claimed") is False, "prefilter claimed device acceptance")
    require(
        claim.get("tool_identity") == contract["qualified_tool_identity"],
        "prefilter claim does not cite the qualified patched source and binary identity",
    )
    require(
        tuple(claim.get("device_mandatory_rows", ())) == BLIND_IDS,
        "prefilter claim lost or reordered a device-mandatory blind-spot row",
    )
    rows = claim.get("prefilter_rows")
    require(isinstance(rows, list) and rows, "prefilter claim has no functional rows")
    forbidden = forbidden_claims(contract)
    for number, row in enumerate(rows):
        require(
            isinstance(row, dict) and set(row) == {"id", "result", "touches"},
            f"prefilter row {number} schema drift",
        )
        row_id = row.get("id")
        touches = row.get("touches")
        require(isinstance(row_id, str) and row_id, f"prefilter row {number} has no id")
        require(row.get("result") in ("PASS", "RED"), f"prefilter row {row_id} has invalid result")
        require(isinstance(touches, list), f"prefilter row {row_id} touches must be a list")
        require(row_id not in BLIND_IDS and row_id not in forbidden, f"prefilter claimed blind row {row_id}")
        require(not set(touches).intersection(BLIND_IDS), f"prefilter row {row_id} touches a blind spot")
        require(not set(touches).difference(BLIND_IDS), f"prefilter row {row_id} names an unknown blind spot")


def item1_claim(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_class": "xemu-prefilter-green",
        "tool_identity": receipt.get("prefilter_tool_identity"),
        "prefilter_rows": [
            {
                "id": "published-v2.0.0-drive8-boot-to-native-prompt",
                "result": "PASS",
                "touches": [],
            }
        ],
        "device_mandatory_rows": list(BLIND_IDS),
        "device_acceptance_claimed": False,
    }


def claim_mutations(base: dict[str, Any], contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base = {
        key: deepcopy(value) for key, value in base.items()
    }
    mutations: dict[str, dict[str, Any]] = {}
    for blind_id in BLIND_IDS:
        value = deepcopy(base)
        value["prefilter_rows"][0]["touches"] = [blind_id]
        mutations[f"claim-over-{blind_id}"] = value
    for forbidden in sorted(forbidden_claims(contract)):
        value = deepcopy(base)
        value["prefilter_rows"][0]["id"] = forbidden
        mutations[f"claim-capability-{forbidden}"] = value
    value = deepcopy(base)
    del value["tool_identity"]["binary_sha256"]
    mutations["fork-identity-field-missing"] = value
    value = deepcopy(base)
    value["tool_identity"]["binary_sha256"] = "0" * 64
    mutations["unpatched-or-other-binary-substituted"] = value
    value = deepcopy(base)
    value["tool_identity"]["patches"].pop()
    mutations["fork-patch-set-incomplete"] = value
    value = deepcopy(base)
    value["tool_identity"]["patches"][1]["sha256"] = "0" * 64
    mutations["fork-patch-identity-drift"] = value
    value = deepcopy(base)
    value["device_mandatory_rows"].pop()
    mutations["device-row-omitted"] = value
    value = deepcopy(base)
    value["device_acceptance_claimed"] = True
    mutations["prefilter-promoted-to-device-acceptance"] = value
    return mutations


def selftest() -> None:
    contract = load_json(CONTRACT_PATH)
    validate_contract(contract)
    base = {
        "evidence_class": contract["evidence_class"],
        "tool_identity": deepcopy(contract["qualified_tool_identity"]),
        "prefilter_rows": [{"id": "boot-to-prompt", "result": "PASS", "touches": []}],
        "device_mandatory_rows": list(BLIND_IDS),
        "device_acceptance_claimed": False,
    }
    validate_prefilter_claim(base, contract)
    mutations = claim_mutations(base, contract)

    for name, value in mutations.items():
        try:
            validate_prefilter_claim(value, contract)
        except ContractError:
            continue
        raise ContractError(f"blind-spot mutation survived: {name}")
    print(f"dwx-prefilter-blind-spot selftest PASS mutations={len(mutations)}")


def check() -> None:
    contract = load_json(CONTRACT_PATH)
    link73 = load_json(LINK73_CONTRACT_PATH)
    link73_receipt = load_json(LINK73_RECEIPT_PATH)
    receipt = load_json(RECEIPT_PATH)
    validate_contract(contract)

    identity = contract["qualified_tool_identity"]
    cycle = load_json(CYCLE_MANIFEST_PATH)
    expected_live_identity = {
        "source_commit": cycle.get("source_commit"),
        "patches": cycle.get("patches"),
        "patched_source_sha256": cycle.get("patched_source_sha256"),
        "binary_sha256": cycle.get("binary", {}).get("sha256"),
    }
    require(identity == expected_live_identity,
            "live four-patch fork identity differs from the qualified cycle probe")

    sealed = contract["sealed_item2_tool_identity"]
    sources = sealed["source_file_sha256"]
    link73_source = link73["xemu_source"]
    link73_binding = link73_receipt["source_binding"]
    require(sealed["source_commit"] == link73_source["commit"], "source commit is not Link-73-bound")
    require(
        sources["targets/mega65/sdcard.c"] == link73_source["sdcard_c_sha256"]
        and sources["targets/mega65/io_mapper.c"] == link73_source["io_mapper_c_sha256"],
        "source-file identity is not Link-73-bound",
    )
    require(sealed["patch_sha256"] == link73_binding["patch_sha256"], "patch identity drift")
    require(
        sealed["patched_source_sha256"] == link73_binding["patched_sdcard_c_sha256"],
        "patched-source identity drift",
    )
    require(
        sealed["binary_sha256"] == link73_receipt["successor"]["adapter_binary_sha256"],
        "adapter binary identity drift",
    )
    require(item1_claim(link73_receipt)["tool_identity"] == sealed,
            "sealed Item-2 claim lost its own fork identity")
    require(
        receipt.get("format") == "lisp65-dwx-prefilter-blind-spot-contract-receipt-v1"
        and receipt.get("status") == "PASS"
        # Item 2 is sealed in its original five-row evidence era.  Item 5
        # extends the live contract with the injection-path row and carries
        # the current six-row mutation proof in its own receipt.
        and receipt.get("contract_rows") == list(SEALED_ITEM2_ROW_IDS)
        and receipt.get("device_mandatory_rows") == list(SEALED_ITEM2_BLIND_IDS)
        and receipt.get("qualified_tool_identity") == sealed
        and receipt.get("runtime_identity_run", {}).get("evidence_class")
        == "xemu-prefilter-green"
        and receipt.get("runtime_identity_run", {}).get("qualified_identity_present") is True
        and receipt.get("runtime_identity_run", {}).get("device_mandatory_rows_present") is True
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(receipt.get("runtime_identity_run", {}).get("receipt_sha256", "")),
        )
        is not None
        and receipt.get("runtime_identity_run", {}).get("framebuffer_sha256")
        == link73_receipt["successor"]["framebuffer_sha256"]
        and receipt.get("runtime_identity_run", {}).get("screenshot_sha256")
        == link73_receipt["successor"]["screenshot_sha256"]
        and receipt.get("mutations", {}).get("attempted") == list(SEALED_ITEM2_MUTATIONS)
        and receipt.get("mutations", {}).get("survived") == [],
        "blind-spot receipt drift",
    )
    report = REPORT_PATH.read_text(encoding="utf-8")
    work_plan = WORK_PLAN_PATH.read_text(encoding="utf-8")
    upstream_draft = UPSTREAM_DRAFT_PATH.read_text(encoding="utf-8")
    upstream_register = UPSTREAM_REGISTER_PATH.read_text(encoding="utf-8")
    require(
        "PDF page 134 (printed page 120)" in report
        and "PDF page 135 (printed page 121)" in report
        and "OWNER_REVIEW_REQUIRED_NOT_FILED" in report,
        "report lost hardware reference or owner-held outward status",
    )
    require("**Closed 2026-09-02:**" in work_plan.split("### Item 2", 1)[1], "work plan does not close Item 2")
    require(
        "X2 — `$DE00` F011 buffer selection ignores `$D689.7`" in upstream_register
        and "X2 (Xemu) — `$DE00` F011 window ignores `$D689.7`" in upstream_draft
        and "X3 — F011 buffered-read completion clears `EQ`" in upstream_register
        and "X3 (MEGA65 documentation) — buffered-read EQ/LOST recipe" in upstream_draft
        and "OWNER_REVIEW_REQUIRED_NOT_FILED" in upstream_draft,
        "X2/X3 outward items are not registered as owner-held drafts",
    )
    print(
        "dwx-prefilter-blind-spot check PASS "
        "live-rows=6 device-mandatory=5 sealed-item2-rows=5 "
        "fork-patches=3 live-mutations=27 device-confirmations=1"
    )


def main(argv: list[str]) -> int:
    if argv[1:] == ["--selftest"]:
        selftest()
        return 0
    if argv[1:] == ["--check"]:
        check()
        return 0
    raise ContractError("usage: dwx_prefilter_blind_spot_contract.py --selftest|--check")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ContractError, OSError) as error:
        print(f"dwx-prefilter-blind-spot: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
