#!/usr/bin/env python3
"""Gate packed DWX media before device-session bindings are issued."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402
from evidence_era import era_bind  # noqa: E402


CONTRACT_PATH = ROOT / "config/dwx-media-admission-gate-contract.json"
RECEIPT_PATH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "dwx-media-admission-gate-receipt-20260902.json"
)
REPORT_PATH = ROOT / "docs/planning/dwx-media-admission-gate-report.md"
WORK_PLAN_PATH = ROOT / "docs/planning/dwx-delivered-world-executor-work-plan.md"

ACTIVE_ROW_IDS = (
    "boot-surface-without-libraries",
    "tier1-documented-domain-error",
    "library-require-over-packed-medium",
    "init-l65-absent",
    "init-l65-valid",
    "init-l65-broken",
    "composed-native-prompt-and-cursor",
    "capture-counters-at-stopped-point",
)
STAGE_ORDER = (
    "packed-medium",
    "emulator-prefilter",
    "admission-decision",
    "device-session-binding",
)
PASS_CLASS = "xemu-prefilter-green"
RED_CLASS = "xemu-prefilter-red-bound-blind-spot"
RECEIPT_EVIDENCE_ERA = "114d0a6159aae2b2e5a586d9b4b11936b8835684"


class AdmissionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AdmissionError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdmissionError(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_contract(contract: dict[str, Any], blind: dict[str, Any]) -> None:
    require(
        contract.get("format") == "lisp65-dwx-media-admission-gate-contract-v1"
        and contract.get("status") == "ACTIVE",
        "media-admission contract header drift",
    )
    require(tuple(contract.get("stage_order", ())) == STAGE_ORDER, "gate stage order drift")
    policy = contract.get("admission_policy")
    require(
        policy
        == {
            "pass_result": "PASS",
            "pass_evidence_class": PASS_CLASS,
            "red_result": "RED",
            "red_evidence_class": RED_CLASS,
            "red_requires_exact_bound_blind_spot": True,
            "every_session_row_remains_device_mandatory": True,
            "device_acceptance_claimed": False,
            "logs_are_oracle": False,
        },
        "media-admission policy drift",
    )
    require(
        contract.get("authority_rule")
        == "A packed medium may be associated with a device-session row only after every derived emulator row is PASS or every RED has one exact attribution to a device-mandatory blind spot; admission never claims device acceptance.",
        "media-admission authority rule drift",
    )
    BLIND.validate_contract(blind)
    injection = next(
        row for row in blind["contract_rows"]
        if row["id"] == "uart-hwa-versus-physical-keyboard"
    )
    boundary = contract.get("injection_path_boundary")
    require(
        boundary
        == {
            "transport": "local-unix-uart-monitor-to-HWA-queue",
            "valid_prefilter_claims": injection["valid_prefilter_claims"],
            "device_mandatory_claims": injection["forbidden_prefilter_claims"],
        },
        "UART/HWA injection boundary drift",
    )


def session_binding(counterpart: str) -> dict[str, Any]:
    require("#" in counterpart, f"session counterpart has no row: {counterpart}")
    relative, row_id = counterpart.rsplit("#", 1)
    path = ROOT / relative
    value = load(path)
    rows = value.get("rows")
    require(
        isinstance(rows, list) and sum(row.get("id") == row_id for row in rows) == 1,
        f"session row is not unique: {counterpart}",
    )
    return {"artifact": bind(path), "row_id": row_id}


def item3_media(item3: dict[str, Any], item3_id: str) -> dict[str, Any]:
    rows = item3.get("product_media_variants")
    require(isinstance(rows, list), "Item-3 product medium population absent")
    matches = [row for row in rows if row.get("id") == item3_id]
    require(len(matches) == 1, f"Item-3 medium id is not unique: {item3_id}")
    medium = matches[0].get("media")
    require(isinstance(medium, dict), f"Item-3 medium absent: {item3_id}")
    path = ROOT / str(medium.get("path"))
    actual = bind(path)
    require(actual == medium, f"Item-3 medium binding drift: {item3_id}")
    return actual


def medium_for_row(
    row: dict[str, Any],
    row_contract: dict[str, Any],
    source_receipt: dict[str, Any],
    item3: dict[str, Any],
) -> dict[str, Any]:
    runtime = row.get("runtime")
    require(isinstance(runtime, dict), f"source row has no runtime: {row.get('id')}")
    if "item3_id" in runtime:
        medium = item3_media(item3, str(runtime["item3_id"]))
        require(
            medium["sha256"] == runtime.get("media_sha256"),
            f"Item-3 runtime medium SHA drift: {row.get('id')}",
        )
        return medium
    if row.get("id") == "library-require-over-packed-medium":
        medium = source_receipt.get("packed_require_medium")
        require(isinstance(medium, dict), "packed require medium absent")
        actual = bind(ROOT / str(medium.get("path")))
        require(actual == medium, "packed require medium binding drift")
        return actual
    product = row_contract["inputs"]["product_d81"]
    actual = bind(ROOT / product["path"])
    require(
        actual["path"] == product["path"]
        and actual["sha256"] == product["sha256"],
        f"product medium binding drift: {row.get('id')}",
    )
    return actual


def decision(result: str, blind_spot: str | None, blind: dict[str, Any]) -> dict[str, Any]:
    if result == "PASS":
        require(blind_spot is None, "green row carries a blind-spot attribution")
        evidence = PASS_CLASS
    elif result == "RED":
        require(blind_spot is not None, "red row lacks a blind-spot attribution")
        require(blind_spot in BLIND.BLIND_IDS, "red row names an unbound blind spot")
        evidence = RED_CLASS
    else:
        raise AdmissionError(f"unknown prefilter result: {result}")
    return {
        "eligible_for_device_session_binding": True,
        "evidence_class": evidence,
        "bound_blind_spot": blind_spot,
        "device_row_still_required": True,
        "device_acceptance_claimed": False,
    }


def source_world(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = contract["source_prefilter"]
    row_contract = load(ROOT / source["contract"])
    source_receipt = load(ROOT / source["receipt"])
    item3_path = ROOT / row_contract["inputs"]["item3_receipt"]["path"]
    item3 = load(item3_path)
    rows = source_receipt.get("rows")
    require(
        isinstance(rows, list) and tuple(row.get("id") for row in rows) == ACTIVE_ROW_IDS,
        "source prefilter row population drift",
    )
    require(
        all(row.get("result") in ("PASS", "RED") for row in rows),
        "source prefilter result population drift",
    )
    return row_contract, source_receipt, item3


def make_admissions(
    contract: dict[str, Any], blind: dict[str, Any]
) -> list[dict[str, Any]]:
    row_contract, source_receipt, item3 = source_world(contract)
    results = []
    for row in source_receipt["rows"]:
        result = row["result"]
        # Current Item-4 evidence is green.  A future RED source receipt must
        # carry its bound blind spot explicitly before this gate can admit it.
        blind_spot = row.get("bound_blind_spot") if result == "RED" else None
        results.append(
            {
                "id": row["id"],
                "stage_order": list(STAGE_ORDER),
                "medium": medium_for_row(row, row_contract, source_receipt, item3),
                "prefilter_row": {
                    "source_row_sha256": canonical_sha(row),
                    "result": result,
                    "oracle_type": row["oracle_type"],
                },
                "admission": decision(result, blind_spot, blind),
                "session_binding": session_binding(row["device_counterpart"]),
            }
        )
    return results


def validate_admissions(
    admissions: list[dict[str, Any]],
    contract: dict[str, Any],
    blind: dict[str, Any],
) -> None:
    row_contract, source_receipt, item3 = source_world(contract)
    source_rows = {row["id"]: row for row in source_receipt["rows"]}
    require(
        tuple(row.get("id") for row in admissions) == ACTIVE_ROW_IDS,
        "a source prefilter row reached no admission decision",
    )
    for row in admissions:
        row_id = row["id"]
        source = source_rows[row_id]
        require(tuple(row.get("stage_order", ())) == STAGE_ORDER, f"stage order drift: {row_id}")
        require(
            row.get("medium") == medium_for_row(source, row_contract, source_receipt, item3),
            f"medium binding drift: {row_id}",
        )
        require(
            row.get("prefilter_row")
            == {
                "source_row_sha256": canonical_sha(source),
                "result": source["result"],
                "oracle_type": source["oracle_type"],
            },
            f"prefilter evidence drift: {row_id}",
        )
        require(
            row.get("session_binding") == session_binding(source["device_counterpart"]),
            f"session binding drift: {row_id}",
        )
        admission = row.get("admission")
        require(isinstance(admission, dict), f"admission decision absent: {row_id}")
        expected = decision(
            source["result"], admission.get("bound_blind_spot"), blind
        )
        require(admission == expected, f"admission decision drift: {row_id}")


def mutation_cases(receipt: dict[str, Any], blind: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    value = deepcopy(receipt)
    value["admissions"].pop()
    result["source-row-admission-omitted"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["stage_order"][1:3] = reversed(
        value["admissions"][0]["stage_order"][1:3]
    )
    result["session-binding-precedes-admission"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["medium"]["sha256"] = "0" * 64
    result["medium-identity-drift"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["session_binding"]["artifact"]["sha256"] = "0" * 64
    result["session-binding-identity-drift"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["prefilter_row"]["source_row_sha256"] = "0" * 64
    result["prefilter-row-identity-drift"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["admission"]["device_row_still_required"] = False
    result["device-row-made-optional"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["admission"]["device_acceptance_claimed"] = True
    result["prefilter-promoted-to-device-acceptance"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["admission"]["evidence_class"] = RED_CLASS
    result["green-row-relabelled-as-red"] = value
    value = deepcopy(receipt)
    value["admissions"][0]["admission"]["bound_blind_spot"] = BLIND.BLIND_IDS[0]
    result["green-row-carries-blind-attribution"] = value
    return result


def mutation_names(receipt: dict[str, Any], contract: dict[str, Any], blind: dict[str, Any]) -> list[str]:
    names = []
    for name, value in mutation_cases(receipt, blind).items():
        try:
            validate_admissions(value["admissions"], contract, blind)
        except AdmissionError:
            names.append(name)
            continue
        raise AdmissionError(f"media-admission mutation survived: {name}")

    red = decision("RED", BLIND.BLIND_IDS[0], blind)
    require(red["evidence_class"] == RED_CLASS, "bound-blind RED positive control failed")
    negative = {
        "red-without-bound-blind-spot": ("RED", None),
        "red-with-unknown-blind-spot": ("RED", "not-a-bound-blind-spot"),
        "red-bound-to-tool-identity": ("RED", "patched-xemu-fork-identity"),
        "pass-with-blind-spot": ("PASS", BLIND.BLIND_IDS[0]),
    }
    for name, args in negative.items():
        try:
            decision(args[0], args[1], blind)
        except AdmissionError:
            names.append(name)
            continue
        raise AdmissionError(f"decision mutation survived: {name}")
    return sorted(names)


def blind_successor_proof(blind: dict[str, Any]) -> dict[str, Any]:
    base = {
        "evidence_class": blind["evidence_class"],
        "tool_identity": deepcopy(blind["qualified_tool_identity"]),
        "prefilter_rows": [
            {"id": "media-admission-positive-control", "result": "PASS", "touches": []}
        ],
        "device_mandatory_rows": list(BLIND.BLIND_IDS),
        "device_acceptance_claimed": False,
    }
    BLIND.validate_prefilter_claim(base, blind)
    names = []
    for name, value in BLIND.claim_mutations(base, blind).items():
        try:
            BLIND.validate_prefilter_claim(value, blind)
        except BLIND.ContractError:
            names.append(name)
            continue
        raise AdmissionError(f"live blind-spot mutation survived: {name}")
    require(len(names) == 27, "live blind-spot mutation population drift")
    return {
        "contract_rows": list(BLIND.ROW_IDS),
        "device_mandatory_rows": list(BLIND.BLIND_IDS),
        "mutations": {"attempted": sorted(names), "survived": []},
        "sealed_item2_receipt_rewritten": False,
    }


def build_receipt(contract: dict[str, Any], blind: dict[str, Any]) -> dict[str, Any]:
    admissions = make_admissions(contract, blind)
    provisional = {
        "format": "lisp65-dwx-media-admission-gate-receipt-v1",
        "status": "PASS",
        "recorded_on": "2026-09-02",
        "authority": {},
        "admissions": admissions,
    }
    mutations = mutation_names(provisional, contract, blind)
    injection = contract["injection_path_boundary"]
    media_paths = {row["medium"]["path"] for row in admissions}
    media_shas = {row["medium"]["sha256"] for row in admissions}
    session_paths = {row["session_binding"]["artifact"]["path"] for row in admissions}
    source = contract["source_prefilter"]
    return {
        "format": "lisp65-dwx-media-admission-gate-receipt-v1",
        "status": "PASS",
        "recorded_on": "2026-09-02",
        "authority": {
            "executor": bind(Path(__file__)),
            "contract": bind(CONTRACT_PATH),
            "blind_spot_contract": bind(ROOT / contract["blind_spot_contract"]),
            "source_prefilter_contract": bind(ROOT / source["contract"]),
            "source_prefilter_receipt": bind(ROOT / source["receipt"]),
        },
        "stage_order": list(STAGE_ORDER),
        "admissions": admissions,
        "admission_summary": {
            "rows": len(admissions),
            "prefilter_green": sum(
                row["admission"]["evidence_class"] == PASS_CLASS for row in admissions
            ),
            "bound_blind_spot_red": sum(
                row["admission"]["evidence_class"] == RED_CLASS for row in admissions
            ),
            "bound_medium_paths": len(media_paths),
            "unique_medium_content_identities": len(media_shas),
            "bound_session_files": len(session_paths),
            "device_rows_still_required": len(admissions),
        },
        "evidence_classes": {
            "green": PASS_CLASS,
            "red_with_bound_blind_spot": RED_CLASS,
            "device_acceptance": "NOT_CLAIMED",
        },
        "blind_spot_contract_successor": blind_successor_proof(blind),
        "blind_red_positive_control": decision("RED", BLIND.BLIND_IDS[0], blind),
        "injection_path_boundary": {
            **injection,
            "physical_keyboard_path_exercised": False,
            "device_acceptance_claimed": False,
        },
        "mutations": {"attempted": mutations, "survived": []},
        "accounting": {
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "fresh_xemu_runs": 0,
            "focus_dependent_input_events": 0,
        },
        "next": "DWX Item 6 retroactive reproduction remains unopened pending review",
        "claim_limit": "Media are eligible only for device-session execution. Prefilter green and bound-blind-spot red are not device acceptance.",
    }


def validate_receipt(receipt: dict[str, Any], contract: dict[str, Any], blind: dict[str, Any]) -> None:
    require(
        receipt.get("format") == "lisp65-dwx-media-admission-gate-receipt-v1"
        and receipt.get("status") == "PASS",
        "media-admission receipt header drift",
    )
    validate_admissions(receipt.get("admissions", []), contract, blind)
    expected = build_receipt(contract, blind)
    expected["authority"]["executor"] = era_bind(
        RECEIPT_EVIDENCE_ERA, Path(__file__))
    expected["authority"]["blind_spot_contract"] = era_bind(
        RECEIPT_EVIDENCE_ERA,
        ROOT / str(contract["blind_spot_contract"]),
    )
    require(receipt == expected, "media-admission receipt drift")


def build() -> None:
    contract = load(CONTRACT_PATH)
    blind = load(ROOT / contract["blind_spot_contract"])
    validate_contract(contract, blind)
    receipt = build_receipt(contract, blind)
    RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "dwx media admission BUILD PASS rows=8 prefilter-green=8 "
        "bound-blind-red=0 device-acceptance=0 focus=0"
    )


def check() -> None:
    contract = load(CONTRACT_PATH)
    blind = load(ROOT / contract["blind_spot_contract"])
    validate_contract(contract, blind)
    receipt = load(RECEIPT_PATH)
    validate_receipt(receipt, contract, blind)
    report = REPORT_PATH.read_text(encoding="utf-8")
    plan = WORK_PLAN_PATH.read_text(encoding="utf-8")
    require(
        "prefilter green" in report
        and "UART/HWA" in report
        and "keine Geräteabnahme" in report,
        "Item-5 report lost evidence or injection boundary",
    )
    item5 = plan.split("### Item 5", 1)[1].split("### Item 6", 1)[0]
    require("**Closed 2026-09-02:**" in item5, "work plan does not close Item 5")
    print(
        "dwx media admission CHECK PASS rows=8 prefilter-green=8 "
        "blind-contract-rows=6 mutations=13 device-acceptance=0"
    )


def selftest() -> None:
    contract = load(CONTRACT_PATH)
    blind = load(ROOT / contract["blind_spot_contract"])
    validate_contract(contract, blind)
    receipt = build_receipt(contract, blind)
    names = mutation_names(receipt, contract, blind)
    require(len(names) == 13, "media-admission mutation population drift")
    require(
        decision("RED", "freezer-entry-return", blind)["evidence_class"] == RED_CLASS,
        "bound blind-spot RED was not admitted",
    )
    print("dwx media admission SELFTEST PASS mutations=13 bound-red-positive-control=PASS")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args(argv[1:])
    if args.action == "build":
        build()
    elif args.action == "check":
        check()
    else:
        selftest()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (AdmissionError, OSError) as error:
        print(f"dwx-media-admission: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
