#!/usr/bin/env python3
"""Verify a sealed Workbench L65M golden against an independent re-emission."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import d81_persistence_fault as D81  # noqa: E402
import l65m_contract as L65M  # noqa: E402
import runtime_export_workbench_artifact as W  # noqa: E402


FORMAT = "lisp65-runtime-export-workbench-golden-v1"
RECEIPT_KEYS = {
    "format", "status", "emitter", "application", "capture", "provenance",
    "derivation", "comparisons",
}
APPLICATION_KEYS = {"entry", "slot", "l65m", "preload"}
ENTRY_KEYS = {"name", "arity"}
L65M_KEYS = {"bytes", "sha256", "blob_bytes", "metadata_bytes", "entry_names"}
PRELOAD_KEYS = {"address", "bytes", "sha256"}
CAPTURE_KEYS = {
    "capture_id", "directory_track", "directory_sector", "directory_entry", "file_type", "blocks",
    "slot_payload_bytes", "slot_payload_sha256", "padding_byte", "padding_bytes",
    "d81_changed",
}
PROVENANCE_KEYS = {
    "source", "workbench_ship", "before_d81", "after_d81", "lcc_inputs",
}
FILE_KEYS = {"path", "bytes", "sha256"}
SHIP_KEYS = FILE_KEYS | {
    "manifest_format", "status", "product", "profile", "source", "gates",
}
DERIVATION_KEYS = {"format", "inputs", "sha256"}
COMPARISON_KEYS = {
    "equal", "left_bytes", "right_bytes", "differing_bytes", "first_difference",
    "left_sha256", "right_sha256",
}


class GoldenError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GoldenError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def _read(path: Path, label: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise GoldenError("%s must be a regular non-symlink file: %s" % (label, path))
        return path.read_bytes()
    except GoldenError:
        raise
    except OSError as exc:
        raise GoldenError("cannot read %s %s: %s" % (label, path, exc)) from exc


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_strict_object)
    except GoldenError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GoldenError("%s is not valid strict JSON" % label) from exc
    if not isinstance(value, dict):
        raise GoldenError("%s must be a JSON object" % label)
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoldenError("%s must be an object" % label)
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise GoldenError(
            "%s keys differ: missing=%s extra=%s"
            % (label, ",".join(missing) or "-", ",".join(extra) or "-")
        )
    return value


def _sha(value: Any, label: str) -> str:
    if not W._is_hex(value, 64):
        raise GoldenError("%s must be a lowercase SHA-256" % label)
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise GoldenError("%s must be an integer >= %d" % (label, minimum))
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GoldenError("%s must be a non-empty string" % label)
    return value


def _file_record(value: Any, label: str) -> dict[str, Any]:
    record = _exact(value, FILE_KEYS, label)
    _text(record["path"], label + ".path")
    _integer(record["bytes"], label + ".bytes", 1)
    _sha(record["sha256"], label + ".sha256")
    return record


def parse_receipt(data: bytes, label: str) -> dict[str, Any]:
    receipt = _exact(_json(data, label), RECEIPT_KEYS, label)
    if receipt["format"] != W.FORMAT or receipt["status"] != "passed":
        raise GoldenError("%s format/status is not a passed Workbench artifact receipt" % label)
    if receipt["emitter"] != W.EMITTER:
        raise GoldenError("%s emitter must be %s" % (label, W.EMITTER))

    application = _exact(receipt["application"], APPLICATION_KEYS, label + ".application")
    entry = _exact(application["entry"], ENTRY_KEYS, label + ".application.entry")
    _text(entry["name"], label + ".entry.name")
    _integer(entry["arity"], label + ".entry.arity")
    _text(application["slot"], label + ".slot")
    l65m = _exact(application["l65m"], L65M_KEYS, label + ".application.l65m")
    _integer(l65m["bytes"], label + ".l65m.bytes", 1)
    _sha(l65m["sha256"], label + ".l65m.sha256")
    _integer(l65m["blob_bytes"], label + ".l65m.blob_bytes", 1)
    _integer(l65m["metadata_bytes"], label + ".l65m.metadata_bytes", 38)
    if not isinstance(l65m["entry_names"], list) or not l65m["entry_names"]:
        raise GoldenError("%s L65M entry_names must be a non-empty list" % label)
    if any(not isinstance(item, str) or not item for item in l65m["entry_names"]):
        raise GoldenError("%s L65M entry_names contain an invalid name" % label)
    if len(l65m["entry_names"]) != len(set(l65m["entry_names"])):
        raise GoldenError("%s L65M entry_names contain duplicates" % label)
    preload = _exact(application["preload"], PRELOAD_KEYS, label + ".application.preload")
    if preload["address"] != W.PRELOAD_ADDRESS:
        raise GoldenError("%s preload address must be 0x050000" % label)
    _integer(preload["bytes"], label + ".preload.bytes", 1)
    _sha(preload["sha256"], label + ".preload.sha256")

    capture = _exact(receipt["capture"], CAPTURE_KEYS, label + ".capture")
    try:
        W.validate_capture_id(capture["capture_id"])
    except W.ArtifactError as exc:
        raise GoldenError("%s has an invalid capture id: %s" % (label, exc)) from exc
    for key in (
        "directory_track", "directory_sector", "directory_entry", "file_type", "blocks",
        "slot_payload_bytes", "padding_byte", "padding_bytes",
    ):
        _integer(capture[key], label + ".capture." + key)
    _sha(capture["slot_payload_sha256"], label + ".capture.slot_payload_sha256")
    if capture["padding_byte"] != 0x20 or not isinstance(capture["d81_changed"], bool):
        raise GoldenError("%s capture padding/change contract differs" % label)

    provenance = _exact(receipt["provenance"], PROVENANCE_KEYS, label + ".provenance")
    for key in ("source", "before_d81", "after_d81"):
        _file_record(provenance[key], label + ".provenance." + key)
    ship = _exact(provenance["workbench_ship"], SHIP_KEYS, label + ".provenance.workbench_ship")
    _file_record({key: ship[key] for key in FILE_KEYS}, label + ".provenance.workbench_ship.file")
    if ship["manifest_format"] != W.WORKBENCH_FORMAT or ship["status"] != W.WORKBENCH_STATUS:
        raise GoldenError("%s Workbench ship format/status differs" % label)
    if ship["product"] != W.WORKBENCH_PRODUCT or ship["profile"] != W.WORKBENCH_PROFILE:
        raise GoldenError("%s Workbench ship product/profile differs" % label)
    if not isinstance(ship["source"], dict) or ship["gates"] != W.WORKBENCH_GATES:
        raise GoldenError("%s Workbench ship source/gates differ" % label)
    lcc_inputs = provenance["lcc_inputs"]
    if not isinstance(lcc_inputs, list) or not lcc_inputs:
        raise GoldenError("%s lcc_inputs must be a non-empty list" % label)
    seen: set[str] = set()
    for index, record in enumerate(lcc_inputs):
        parsed = _file_record(record, "%s.provenance.lcc_inputs[%d]" % (label, index))
        if parsed["path"] in seen:
            raise GoldenError("%s contains duplicate lcc input paths" % label)
        seen.add(parsed["path"])

    derivation = _exact(receipt["derivation"], DERIVATION_KEYS, label + ".derivation")
    if derivation["format"] != "lisp65-runtime-export-workbench-derivation-v1":
        raise GoldenError("%s derivation format differs" % label)
    if not isinstance(derivation["inputs"], dict):
        raise GoldenError("%s derivation inputs must be an object" % label)
    _sha(derivation["sha256"], label + ".derivation.sha256")
    comparisons = receipt["comparisons"]
    if not isinstance(comparisons, dict) or set(comparisons) - {"host_l65m", "host_preload"}:
        raise GoldenError("%s comparisons contain unknown records" % label)
    for key, comparison in comparisons.items():
        _exact(comparison, COMPARISON_KEYS, "%s.comparisons.%s" % (label, key))
    return receipt


def reconstruct_derivation(receipt: dict[str, Any], label: str) -> dict[str, Any]:
    application = receipt["application"]
    provenance = receipt["provenance"]
    expected = W._derivation(
        capture_id=receipt["capture"]["capture_id"],
        source_sha256=provenance["source"]["sha256"],
        ship_sha256=provenance["workbench_ship"]["sha256"],
        before_sha256=provenance["before_d81"]["sha256"],
        after_sha256=provenance["after_d81"]["sha256"],
        slot=application["slot"],
        slot_sha256=receipt["capture"]["slot_payload_sha256"],
        l65m_sha256=application["l65m"]["sha256"],
        preload_sha256=application["preload"]["sha256"],
        lcc_records=provenance["lcc_inputs"],
    )
    if receipt["derivation"] != expected:
        raise GoldenError("%s derivation hash/inputs do not reconstruct" % label)
    return expected


def _pinned_ship_record(args: argparse.Namespace) -> dict[str, Any]:
    ship_data = _read(args.ship_manifest, "pinned Workbench ship manifest")
    try:
        ship = W.parse_workbench_ship(ship_data)
    except W.ArtifactError as exc:
        raise GoldenError("pinned Workbench ship failed validation: %s" % exc) from exc
    ship_record = {
        "path": str(args.ship_manifest),
        "bytes": len(ship_data),
        "sha256": W._sha(ship_data),
        "manifest_format": ship["manifest_format"],
        "status": ship["status"],
        "product": ship["product"],
        "profile": ship["profile"],
        "source": ship["source"],
        "gates": ship["gates"],
    }
    return ship_record


def _bind_receipt(
    receipt: dict[str, Any], label: str, image: bytes, preload: bytes,
    ship: dict[str, Any],
) -> None:
    application = receipt["application"]
    summary = L65M.validate_image(image)
    expected_l65m = {
        "bytes": len(image), "sha256": W._sha(image), "blob_bytes": summary.blob_bytes,
        "metadata_bytes": summary.metadata_bytes, "entry_names": summary.entry_names,
    }
    expected_preload = {
        "address": W.PRELOAD_ADDRESS, "bytes": len(preload), "sha256": W._sha(preload),
    }
    if application["l65m"] != expected_l65m:
        raise GoldenError("%s L65M record differs from its artifact" % label)
    if application["preload"] != expected_preload:
        raise GoldenError("%s preload record differs from structured Bank-5 rebase" % label)
    W.validate_entry(image, application["entry"]["name"], application["entry"]["arity"])
    provenance = receipt["provenance"]
    receipt_ship = dict(provenance["workbench_ship"])
    current_ship = dict(ship)
    receipt_ship.pop("path", None)
    current_ship.pop("path", None)
    if receipt_ship != current_ship:
        raise GoldenError("%s Workbench ship binding differs from the pinned manifest" % label)
    reconstruct_derivation(receipt, label)


def check(args: argparse.Namespace) -> dict[str, Any]:
    try:
        same_receipt = os.path.samefile(args.first_receipt, args.reemission_receipt)
    except OSError:
        same_receipt = args.first_receipt.resolve() == args.reemission_receipt.resolve()
    if same_receipt:
        raise GoldenError("first and re-emission receipt files must be distinct")

    golden = _read(args.golden_l65m, "golden L65M")
    reemitted = _read(args.reemitted_l65m, "re-emitted L65M")
    try:
        L65M.validate_image(golden)
        L65M.validate_image(reemitted)
    except L65M.ContractError as exc:
        raise GoldenError("Workbench L65M failed validation: %s" % exc) from exc
    golden_preload = W.bank5_preload(golden)
    reemitted_preload = W.bank5_preload(reemitted)
    if golden != reemitted:
        diff = W.byte_diff(golden, reemitted)
        raise GoldenError(
            "Workbench re-emission is not byte-identical: differing_bytes=%d first=%s"
            % (diff["differing_bytes"], diff["first_difference"])
        )
    if golden_preload != reemitted_preload:
        raise GoldenError("Workbench re-emission Bank-5 preload differs")

    first = parse_receipt(_read(args.first_receipt, "first receipt"), "first receipt")
    second = parse_receipt(
        _read(args.reemission_receipt, "re-emission receipt"), "re-emission receipt"
    )
    if first["capture"]["capture_id"] == second["capture"]["capture_id"]:
        raise GoldenError("first and re-emission capture ids must be distinct")
    if first["application"]["entry"] != second["application"]["entry"]:
        raise GoldenError("receipt runtime entries differ")
    if W._canonical_name(first["application"]["slot"]) != W._canonical_name(second["application"]["slot"]):
        raise GoldenError("receipt slot identities differ")
    ship = _pinned_ship_record(args)
    _bind_receipt(first, "first receipt", golden, golden_preload, ship)
    _bind_receipt(second, "re-emission receipt", reemitted, reemitted_preload, ship)
    if (
        first["provenance"]["source"] != second["provenance"]["source"]
        or first["provenance"]["lcc_inputs"] != second["provenance"]["lcc_inputs"]
    ):
        raise GoldenError("sealed receipt input identities differ")

    host_l65m = _read(args.host_l65m, "Python host L65M")
    try:
        L65M.validate_image(host_l65m)
    except L65M.ContractError as exc:
        raise GoldenError("Python host L65M failed validation: %s" % exc) from exc
    host_preload = _read(args.host_preload, "Python host preload")
    host_rebase = W.bank5_preload(host_l65m)
    differential = {
        "golden_vs_python_l65m": W.byte_diff(golden, host_l65m),
        "golden_vs_python_preload": W.byte_diff(golden_preload, host_preload),
        "python_rebase_vs_python_preload": W.byte_diff(host_rebase, host_preload),
    }
    report = {
        "format": FORMAT,
        "status": "passed",
        "workbench": {
            "golden_l65m_sha256": W._sha(golden),
            "reemitted_l65m_sha256": W._sha(reemitted),
            "preload_sha256": W._sha(golden_preload),
            "entry": first["application"]["entry"],
            "slot": first["application"]["slot"],
            "byte_identical": True,
        },
        "receipts": {
            "first_capture_id": first["capture"]["capture_id"],
            "reemission_capture_id": second["capture"]["capture_id"],
            "first_derivation_sha256": first["derivation"]["sha256"],
            "reemission_derivation_sha256": second["derivation"]["sha256"],
        },
        "sealed_inputs": {
            "source": first["provenance"]["source"],
            "workbench_ship": first["provenance"]["workbench_ship"],
            "lcc_inputs": first["provenance"]["lcc_inputs"],
        },
        "python_host_differential_oracle": differential,
    }
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=args.report_out.name + ".", dir=args.report_out.parent, delete=False
    ) as handle:
        tmp = Path(handle.name)
        handle.write(encoded)
    try:
        os.replace(tmp, args.report_out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return report


def _expect_failure(label: str, needle: str, operation: Any) -> None:
    try:
        operation()
    except (GoldenError, W.ArtifactError) as exc:
        if needle not in str(exc):
            raise GoldenError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
    else:
        raise GoldenError("selftest mutation passed: %s" % label)


def selftest() -> int:
    fixture = json.loads((ROOT / "tests/bytecode/formats/p0-disk-lib-v1.json").read_text())
    minimal = bytes.fromhex(next(item for item in fixture["goldens"] if item["id"] == "minimal")["image_hex"])
    host = bytes.fromhex(next(item for item in fixture["goldens"] if item["id"] == "all-kinds")["image_hex"])
    payload = minimal + b" " * (8192 - len(minimal))
    after = D81.seed_file(bytes(D81.blank_image()), "fasl0", payload)
    with tempfile.TemporaryDirectory(prefix="runtime-export-golden-selftest-") as raw:
        base = Path(raw)
        source = base / "source.lisp"
        ship = base / "manifest.json"
        before = base / "before.d81"
        after_path = base / "after.d81"
        lcc = base / "lcc.lisp"
        source.write_text("(defun id () 0)\n", encoding="ascii")
        ship.write_bytes(W._json_bytes(W._selftest_ship_manifest()))
        before.write_bytes(bytes(D81.blank_image()))
        after_path.write_bytes(after)
        lcc.write_text("; lcc selftest\n", encoding="ascii")

        def receipt(prefix: str) -> tuple[Path, Path, Path]:
            out_l65m = base / (prefix + ".l65m")
            out_preload = base / (prefix + ".preload")
            out_report = base / (prefix + ".json")
            W.capture(argparse.Namespace(
                capture_id="selftest-" + prefix,
                source=source, ship_manifest=ship, before_d81=before, after_d81=after_path,
                slot="fasl0", entry="id", arity=0, lcc_input=[lcc],
                l65m_out=out_l65m, preload_out=out_preload, report_out=out_report,
                host_l65m=None, host_preload=None, require_host_equal=False,
                require_d81_change=True,
            ))
            return out_l65m, out_preload, out_report

        golden, _preload, first = receipt("golden")
        reemitted, _preload2, second = receipt("reemitted")
        host_l65m = base / "host.l65m"
        host_preload = base / "host.preload"
        host_l65m.write_bytes(host)
        host_preload.write_bytes(W.bank5_preload(host))
        args = argparse.Namespace(
            golden_l65m=golden, reemitted_l65m=reemitted,
            first_receipt=first, reemission_receipt=second,
            source=source, ship_manifest=ship, lcc_input=[lcc],
            host_l65m=host_l65m, host_preload=host_preload,
            report_out=base / "golden-report.json",
        )
        report = check(args)
        differential = report["python_host_differential_oracle"]
        if differential["golden_vs_python_l65m"]["equal"]:
            raise GoldenError("selftest Python host differential unexpectedly equals the golden")
        if not differential["python_rebase_vs_python_preload"]["equal"]:
            raise GoldenError("selftest Python host preload is not its own structured rebase")

        args.reemission_receipt = first
        _expect_failure(
            "same-receipt", "receipt files must be distinct", lambda: check(args)
        )
        args.reemission_receipt = second

        same_id = _json(second.read_bytes(), "selftest same-id receipt")
        same_id["capture"]["capture_id"] = report["receipts"]["first_capture_id"]
        same_id["derivation"] = W._derivation(
            capture_id=same_id["capture"]["capture_id"],
            source_sha256=same_id["provenance"]["source"]["sha256"],
            ship_sha256=same_id["provenance"]["workbench_ship"]["sha256"],
            before_sha256=same_id["provenance"]["before_d81"]["sha256"],
            after_sha256=same_id["provenance"]["after_d81"]["sha256"],
            slot=same_id["application"]["slot"],
            slot_sha256=same_id["capture"]["slot_payload_sha256"],
            l65m_sha256=same_id["application"]["l65m"]["sha256"],
            preload_sha256=same_id["application"]["preload"]["sha256"],
            lcc_records=same_id["provenance"]["lcc_inputs"],
        )
        same_id_receipt = base / "same-id-receipt.json"
        same_id_receipt.write_text(json.dumps(same_id), encoding="utf-8")
        args.reemission_receipt = same_id_receipt
        _expect_failure(
            "same-capture-id", "capture ids must be distinct", lambda: check(args)
        )
        args.reemission_receipt = second

        _expect_failure(
            "receipt-duplicate-key", "duplicate JSON key",
            lambda: parse_receipt(b'{"format":"a","format":"b"}', "mutated receipt"),
        )
        mutated = _json(first.read_bytes(), "selftest receipt")
        mutated["derivation"]["sha256"] = "0" * 64
        bad_receipt = base / "bad-receipt.json"
        bad_receipt.write_text(json.dumps(mutated), encoding="utf-8")
        args.first_receipt = bad_receipt
        _expect_failure("derivation", "do not reconstruct", lambda: check(args))
        args.first_receipt = first

        forged = _json(first.read_bytes(), "selftest forged receipt")
        forged["application"]["l65m"]["sha256"] = "7" * 64
        forged["derivation"] = W._derivation(
            capture_id=forged["capture"]["capture_id"],
            source_sha256=forged["provenance"]["source"]["sha256"],
            ship_sha256=forged["provenance"]["workbench_ship"]["sha256"],
            before_sha256=forged["provenance"]["before_d81"]["sha256"],
            after_sha256=forged["provenance"]["after_d81"]["sha256"],
            slot=forged["application"]["slot"],
            slot_sha256=forged["capture"]["slot_payload_sha256"],
            l65m_sha256=forged["application"]["l65m"]["sha256"],
            preload_sha256=forged["application"]["preload"]["sha256"],
            lcc_records=forged["provenance"]["lcc_inputs"],
        )
        forged_receipt = base / "forged-receipt.json"
        forged_receipt.write_text(json.dumps(forged), encoding="utf-8")
        args.first_receipt = forged_receipt
        _expect_failure("forged-l65m", "differs from its artifact", lambda: check(args))
        args.first_receipt = first

        bad_reemission = base / "bad-reemission.l65m"
        bad_reemission.write_bytes(host)
        args.reemitted_l65m = bad_reemission
        _expect_failure("reemission", "not byte-identical", lambda: check(args))
        args.reemitted_l65m = reemitted

        ship_data = _json(ship.read_bytes(), "selftest ship")
        ship_data["status"] = "unverified-candidate"
        bad_ship = base / "bad-ship.json"
        bad_ship.write_text(json.dumps(ship_data), encoding="utf-8")
        args.ship_manifest = bad_ship
        _expect_failure("ship-status", "g2-verified-candidate", lambda: check(args))
        args.ship_manifest = ship

        host_preload.write_bytes(b"different but explicitly non-normative")
        report = check(args)
        if report["python_host_differential_oracle"]["golden_vs_python_preload"]["equal"]:
            raise GoldenError("selftest accepted host differential as equality")

    print("runtime-export-workbench-golden selftest: PASS mutations=7 differential=non-normative")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--golden-l65m", type=Path, required=True)
    check_parser.add_argument("--reemitted-l65m", type=Path, required=True)
    check_parser.add_argument("--first-receipt", type=Path, required=True)
    check_parser.add_argument("--reemission-receipt", type=Path, required=True)
    check_parser.add_argument("--ship-manifest", type=Path, required=True)
    check_parser.add_argument("--host-l65m", type=Path, required=True)
    check_parser.add_argument("--host-preload", type=Path, required=True)
    check_parser.add_argument("--report-out", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest()
        report = check(args)
    except (GoldenError, W.ArtifactError, L65M.ContractError, OSError, ValueError, KeyError) as exc:
        print("runtime-export-workbench-golden: FAIL: %s" % exc, file=sys.stderr)
        return 1
    differential = report["python_host_differential_oracle"]
    print(
        "runtime-export-workbench-golden: PASS byte_identical=true "
        "python_l65m_equal=%s python_preload_equal=%s"
        % (
            str(differential["golden_vs_python_l65m"]["equal"]).lower(),
            str(differential["golden_vs_python_preload"]["equal"]).lower(),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
