#!/usr/bin/env python3
"""Build one-drive INIT.L65 product variants from one frozen product D81."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_init_l65_acceptance_media as BASE  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-v17-init-l65-product-variants-media-contract.json"
SESSION = ROOT / "config/c2-v17-init-l65-product-variants-resume-session.json"
PREDECESSOR = ARCH / "c2.3-v1.7-init-l65-acceptance-media-receipt.json"
RECEIPT = ARCH / (
    "c2.3-v1.7-init-l65-product-variants-media-receipt.json")
DEVICE_RESULT = ARCH / (
    "c2.3-v1.7-init-l65-product-variants-device-result-receipt.json")
BUILD = ROOT / "build/c2.3/v1.7-init-l65-product-variants-media"
ABSENT = BUILD / "lisp65-product-init-absent.d81"
VALID = BUILD / "lisp65-product-init-valid.d81"
ERROR = BUILD / "lisp65-product-init-error.d81"
VALID_SOURCE = BUILD / "INIT-VALID.L65"
ERROR_SOURCE = BUILD / "INIT-ERROR.L65"
ABSENT_REMOTE = "V17IM.D81"
VALID_REMOTE = "V17IOK.D81"
ERROR_REMOTE = "V17IBAD.D81"
STATUS = "PASS: V1.7 INIT.L65 ONE-DRIVE PRODUCT VARIANTS READY"
DEVICE_STATUS = "PASS: V1.7 NATIVE INIT.L65 HARDWARE ACCEPTED"
VALID_INIT = (
    b"(write 17)\n"
    b"(terpri)\n"
    b"(defun init-proof () 17)\n"
)
ERROR_INIT = b"(>= nil 32)\n"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"


class VariantError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VariantError(message)


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


def bind_bytes(raw: bytes) -> dict[str, Any]:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def error_runtime_proof(raw: bytes) -> dict[str, Any]:
    """Require the exact error payload to fail in the product VM profile."""
    source = raw.decode("ascii")
    form = C.parse_one(source)
    heap = B.Heap()
    ledger = load(ABI_LEDGER)
    _name, code, helpers = C.compile_top_form_with_helpers(
        ["defun", "__init_error_probe", [], form], heap,
        strict_arity=True, abi_profile="dialect-v2", abi_ledger=ledger)
    require(helpers == [], "INIT error probe unexpectedly emitted helpers")
    vm = B.P0VM(heap=heap, directory={}, abi_profile="dialect-v2",
                abi_ledger=ledger)
    try:
        vm.run(code, [])
    except B.VMError as error:
        require(str(error) == "expected two fixnums",
                "INIT error payload raised the wrong product-profile error")
        return {"result": "VM_TYPEERROR", "detail": str(error),
                "steps_before_error": vm.steps}
    raise VariantError("INIT error payload completed without VM_TYPEERROR")


def source_compile_proof() -> dict[str, Any]:
    """Prove that the exact media payloads parse and compile as stream forms."""
    suite = STD._read_suite(str(SUITE))
    abi_profile = suite.get("abi_profile", "dialect-v2")
    result: dict[str, Any] = {}
    for label, raw in (("valid", VALID_INIT), ("error", ERROR_INIT)):
        source = raw.decode("ascii")
        forms = C.parse_all(source)
        heap = B.Heap()
        rows = []
        for form in forms:
            emitted = (form if isinstance(form, list) and form
                       and form[0] == "defun" else ["lambda", [], form])
            name, code, helpers = C.compile_top_form_with_helpers(
                emitted, heap, strict_arity=True, abi_profile=abi_profile)
            require(helpers == [],
                    f"{label} INIT form unexpectedly emitted helpers")
            rows.append({
                "form": form,
                "entry": name,
                "object_bytes": len(code.encode()),
                "call_edges": [list(row) for row in
                               STD._call_edges(heap, code, suite)],
            })
        result[label] = {"source": bind_bytes(raw), "forms": rows}
    require(
        [row["entry"] for row in result["valid"]["forms"]] ==
            [None, None, "init-proof"]
        and result["valid"]["forms"][0]["call_edges"] ==
            [["CALL", "write", 1]]
        and result["valid"]["forms"][1]["call_edges"] ==
            [["CALL", "terpri", 0]]
        and len(result["error"]["forms"]) == 1,
        "INIT media source compile proof drift")
    result["error"]["product_profile_execution"] = error_runtime_proof(
        ERROR_INIT)
    return result


def authority() -> tuple[dict[str, Any], Path]:
    contract = load(CONTRACT)
    predecessor = load(PREDECESSOR)
    product = ROOT / predecessor["media"]["product"]["path"]
    require(contract["status"] ==
                "OPEN: REVIEW-AUTHORIZED ARTIFACT-ONLY PRODUCT VARIANTS AND SESSION RESUME"
            and contract["scope"] == {"new_WPLTO_runs": 0,
                "new_product_links": 0, "new_product_cards": 0,
                "device_contacts_during_build": 0, "artifact_only": True}
            and contract["device_resume"]["accepted_predecessor_row"] ==
                "I-absent"
            and contract["device_resume"]["manual_boot_media_swap"] is False
            and predecessor["status"] == BASE.STATUS
            and bind(product) == predecessor["media"]["product"],
            "INIT product-variant authority drift")
    return predecessor, product


def _append_init(source: Path, image: Path) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    result = subprocess.run([c1541, str(image), "-write", str(source),
                             "init.l65"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, "c1541 INIT append failed:\n" +
            result.stdout.decode("latin-1", errors="replace"))


def _records(raw: bytes) -> dict[bytes, dict[str, Any]]:
    result = {}
    for slot in D81.directory_slots(raw):
        if slot.record[2] == 0:
            continue
        name = D81.entry_name(slot.record)
        require(name not in result, f"duplicate D81 member: {name!r}")
        chain = D81.file_chain(raw, slot.record)
        result[name] = {
            "record": slot.record,
            "directory_sector": (slot.track, slot.sector),
            "directory_index": slot.index,
            "chain": chain,
            "payload": D81.read_record_payload(raw, slot.record),
        }
    return result


def _sector(offset: int) -> tuple[int, int]:
    ordinal = offset // D81.SECTOR_SIZE
    return ordinal // D81.SECTORS_PER_TRACK + 1, ordinal % D81.SECTORS_PER_TRACK


def _sector_label(value: tuple[int, int]) -> str:
    return f"T{value[0]:02d}/S{value[1]:02d}"


def variant_proof(absent: bytes, candidate: bytes,
                  expected_init: bytes) -> dict[str, Any]:
    require(len(absent) == len(candidate) == D81.IMAGE_SIZE,
            "INIT product variant D81 size drift")
    base_files = D81.visible_files(absent)
    candidate_files = D81.visible_files(candidate)
    init = candidate_files.pop(b"INIT.L65", None)
    require(init == expected_init, "INIT product variant payload drift")
    require(candidate_files == base_files,
            "non-INIT product payload changed across variant")
    base_records = _records(absent)
    candidate_records = _records(candidate)
    init_record = candidate_records.pop(b"INIT.L65", None)
    require(init_record is not None and set(candidate_records) == set(base_records),
            "INIT product variant directory membership drift")
    require(all(candidate_records[name]["record"] == base_records[name]["record"]
                and candidate_records[name]["chain"] == base_records[name]["chain"]
                for name in base_records),
            "non-INIT product directory or chain changed across variant")
    init_chain = set(init_record["chain"])
    metadata = {init_record["directory_sector"]}
    metadata.update((D81.DIRECTORY_TRACK, D81.bam_half(track))
                    for track, _sector_number in init_chain)
    allowed = init_chain | metadata
    changed_offsets = [index for index, (left, right) in
                       enumerate(zip(absent, candidate)) if left != right]
    changed_sectors = {_sector(offset) for offset in changed_offsets}
    require(changed_offsets and changed_sectors == allowed,
            "raw D81 diff escaped INIT payload/allocation/publication ownership")
    product_rows = [{"name": name.decode("ascii"),
        "payload": bind_bytes(base_records[name]["payload"]),
        "directory_record_sha256": hashlib.sha256(
            base_records[name]["record"]).hexdigest(),
        "chain": [_sector_label(row) for row in base_records[name]["chain"]]}
        for name in sorted(base_records)]
    return {
        "non_INIT_members": product_rows,
        "non_INIT_member_count": len(product_rows),
        "INIT_L65": bind_bytes(expected_init),
        "INIT_chain": sorted(_sector_label(row) for row in init_chain),
        "filesystem_metadata_sectors": sorted(
            _sector_label(row) for row in metadata),
        "raw_changed_bytes": len(changed_offsets),
        "raw_changed_sectors": sorted(_sector_label(row)
                                      for row in changed_sectors),
        "result": "only-INIT-payload-and-owned-filesystem-metadata-differ",
    }


def cross_variant_proof(absent: bytes, valid: bytes,
                        error: bytes) -> dict[str, Any]:
    valid_proof = variant_proof(absent, valid, VALID_INIT)
    error_proof = variant_proof(absent, error, ERROR_INIT)
    valid_records = _records(valid)
    error_records = _records(error)
    require(valid_records[b"INIT.L65"]["chain"] ==
                error_records[b"INIT.L65"]["chain"]
            and all(valid_records[name]["record"] == error_records[name]["record"]
                    for name in valid_records if name != b"INIT.L65"),
            "valid/error variants do not share one product filesystem")
    diff_offsets = [index for index, (left, right) in
                    enumerate(zip(valid, error)) if left != right]
    init_chain = set(valid_records[b"INIT.L65"]["chain"])
    require({_sector(offset) for offset in diff_offsets} == init_chain,
            "valid/error raw diff escaped the shared INIT chain")
    return {"absent_to_valid": valid_proof,
            "absent_to_error": error_proof,
            "valid_to_error": {
                "raw_changed_bytes": len(diff_offsets),
                "raw_changed_sectors": sorted(
                    _sector_label(row) for row in init_chain),
                "result": "only-shared-INIT-payload-chain-differs"},
            "frozen_product": {
                "visible_member_count": len(D81.visible_files(absent)),
                "inventory_sha256": hashlib.sha256(canonical(
                    {name.decode("ascii"): bind_bytes(payload)
                     for name, payload in sorted(
                         D81.visible_files(absent).items())})).hexdigest()},
            "rule": "one frozen product filesystem; INIT.L65 is the sole variant"}


def _reject(name: str, function: Any) -> dict[str, str]:
    try:
        function()
    except (VariantError, ValueError, AssertionError):
        return {"name": name, "result": "rejected"}
    raise VariantError(f"INIT product-variant mutation survived: {name}")


def mutations(absent: bytes, valid: bytes) -> list[dict[str, str]]:
    records = _records(valid)
    init = records[b"INIT.L65"]
    product_name = next(name for name in sorted(records)
                        if name != b"INIT.L65")
    product = records[product_name]
    changed_product = bytearray(valid)
    changed_product[D81.sector_offset(*product["chain"][0]) + 2] ^= 1
    lost_init = bytearray(valid)
    slot_offset = (D81.sector_offset(*init["directory_sector"])
                   + init["directory_index"] * D81.DIR_ENTRY_SIZE)
    lost_init[slot_offset + 2] = 0
    changed_init = bytearray(valid)
    changed_init[D81.sector_offset(*init["chain"][0]) + 2] ^= 1
    outside = next((track, sector) for track in range(1, D81.TRACKS + 1)
                   for sector in range(D81.SECTORS_PER_TRACK)
                   if D81.sector_is_free(valid, track, sector))
    escaped = bytearray(valid)
    escaped[D81.sector_offset(*outside) + 100] ^= 1
    return [
        _reject("changed-non-INIT-product-byte", lambda:
            variant_proof(absent, bytes(changed_product), VALID_INIT)),
        _reject("missing-INIT-directory-publication", lambda:
            variant_proof(absent, bytes(lost_init), VALID_INIT)),
        _reject("changed-INIT-payload-against-bound-source", lambda:
            variant_proof(absent, bytes(changed_init), VALID_INIT)),
        _reject("raw-D81-diff-outside-INIT-ownership", lambda:
            variant_proof(absent, bytes(escaped), VALID_INIT)),
        _reject("compiled-but-nonerror-INIT-payload", lambda:
            error_runtime_proof(b"(car 1)\n")),
    ]


def session_config(media: dict[str, dict[str, Any]]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-v17-native-init-product-variants-resume-session-v1",
        "recorded_on": "2026-08-27",
        "status": "ready-owner-contact-resume",
        "claim_scope": {
            "accepts": ["v1.7-native-INIT.L65"],
            "observes_only": ["A0-error-to-prompt-perception"],
            "excludes": ["Comfort", "Block-3", "canonical-prompt-swap",
                         "release-publication", "automatic-feature-reopening"]},
        "predecessor_contact": {
            "I-absent": "accepted-green: frozen product without INIT.L65 reached a usable native lisp65>",
            "remaining_rows": ["I-present", "I-error", "A0-perception"]},
        "media": media,
        "choreography": {
            "one_product_medium_per_cold_boot": True,
            "manual_boot_media_swap": False,
            "all_media_uploaded_and_read_back_before_resume": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True},
        "rows": [
            {"id": "I-present", "medium": VALID_REMOTE,
             "actions": ["cold boot this product medium",
                         "observe exactly one line containing 17 before the banner",
                         "at lisp65> submit (init-proof)"],
             "expect": ["INIT executes before the first banner",
                        "the pre-banner 17 side effect appears exactly once",
                        "init-proof returns 17", "no INIT retry"]},
            {"id": "I-error", "medium": ERROR_REMOTE,
             "actions": ["cold boot this product medium",
                         "observe exactly one product-profile VM type error",
                         "report approximate seconds from the error to lisp65>",
                         "at the returned lisp65> submit (list 1 3)"],
             "expect": ["exactly one VM_TYPEERROR with distinguishable text",
                        "the banner may be absent because INIT aborts %repl-banner",
                        "no red frame",
                        "INIT is not retried", "result is (1 3)",
                        "A0 perception time recorded"]},
            {"id": "A0-perception", "medium": ERROR_REMOTE,
             "actions": ["reuse the I-error startup measurement",
                         "do not inject a second error"],
             "expect": ["ordinary type error", "no red frame",
                        "usable native prompt", "one timing observation"],
             "claim": "observation only; does not reopen Comfort or Block 3"}],
        "decision_table": {
            "predecessor-I-absent-plus-all-resume-rows-green":
                "Block I hardware accepted",
            "A0-observation": "owner input to a later reopening decision",
            "daily-use-blocker":
                "stop under the standing anti-rabbit-hole rule"}}
    audit_session(value)
    return value


def audit_session(value: dict[str, Any]) -> None:
    rows = value.get("rows", [])
    ids = [row.get("id") for row in rows]
    require(value.get("status") == "ready-owner-contact-resume"
            and value.get("predecessor_contact", {}).get("remaining_rows") ==
                ["I-present", "I-error", "A0-perception"]
            and ids == ["I-present", "I-error", "A0-perception"]
            and value.get("choreography", {}).get(
                "one_product_medium_per_cold_boot") is True
            and value.get("choreography", {}).get(
                "manual_boot_media_swap") is False
            and all("library" not in json.dumps(row).lower() for row in rows)
            and "exactly once" in rows[0]["expect"][1]
            and rows[1]["expect"][0] ==
                "exactly one VM_TYPEERROR with distinguishable text",
            "INIT one-drive Resume session drift")


def device_result_value() -> dict[str, Any]:
    media = load(RECEIPT)
    session = load(SESSION)
    audit_session(session)
    require(media.get("source_compile_proof", {}).get("error", {}).get(
                "product_profile_execution", {}).get("result") ==
                "VM_TYPEERROR",
            "device result lacks product-profile error authority")
    return {
        "format": "lisp65-c2-v17-native-init-product-variants-device-result-v1",
        "recorded_on": "2026-08-27", "status": DEVICE_STATUS,
        "media_authority": bind(RECEIPT),
        "session_authority": bind(SESSION),
        "delivered_media": {
            key: {"remote_name": row["remote_name"],
                  "sha256": row["sha256"], "readback": "byteidentical"}
            for key, row in sorted(media["media"].items())},
        "contact": {
            "device": "/dev/ttyUSB1", "transport": "mega65_ftp-over-JTAG",
            "owner_keyboard_only_after_boot": True,
            "automated_access_after_boot": 0,
            "session_contacts": 1, "cold_boots": 3,
            "artifact_correction_inside_contact": {
                "first_payload": "(car 1)",
                "observation": "nil-semantics; normal native REPL",
                "replacement_payload": "(>= nil 32)",
                "classification":
                    "session-fixture semantic drift; hook and product exonerated"}},
        "rows": {
            "I-absent": {
                "source": "accepted predecessor observation",
                "result": "usable native lisp65> with INIT.L65 absent"},
            "I-present": {
                "pre_banner_effect": "17", "effect_count": 1,
                "probe": "(init-proof)", "probe_result": "17",
                "retry_observed": False, "result": "PASS"},
            "I-error": {
                "semantic_error": "VM_TYPEERROR",
                "observed_rendering": "*** vm: type error",
                "banner_after_error": "absent",
                "prompt": "lisp65>", "red_frame": False,
                "probe": "(list 1 3)", "probe_result": "(1 3)",
                "retry_observed": False, "result": "PASS"},
            "A0-perception": {
                "carrier": "I-error startup recovery",
                "owner_observation": "prompt returned practically immediately",
                "claim": "perception only", "result": "RECORDED"}},
        "acceptance": {
            "Block_I_native_INIT_L65": "ACCEPTED",
            "Comfort_reopened": False, "Block_3_reopened": False,
            "canonical_prompt_swap": False},
        "claim_limit": session["claim_scope"],
    }


def audit_device_result(value: dict[str, Any]) -> None:
    expected = device_result_value()
    require(value == expected
            and value.get("status") == DEVICE_STATUS
            and value.get("rows", {}).get("I-present", {}).get("result") ==
                "PASS"
            and value.get("rows", {}).get("I-error", {}).get(
                "semantic_error") == "VM_TYPEERROR"
            and value.get("rows", {}).get("I-error", {}).get("red_frame")
                is False
            and value.get("acceptance", {}).get(
                "Block_I_native_INIT_L65") == "ACCEPTED",
            "native INIT device result drift")


def build() -> None:
    predecessor, product = authority()
    BASE.check()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    for target in (ABSENT, VALID, ERROR):
        shutil.copyfile(product, target)
    VALID_SOURCE.write_bytes(VALID_INIT)
    ERROR_SOURCE.write_bytes(ERROR_INIT)
    _append_init(VALID_SOURCE, VALID)
    _append_init(ERROR_SOURCE, ERROR)
    absent_raw, valid_raw, error_raw = (
        path.read_bytes() for path in (ABSENT, VALID, ERROR))
    proof = cross_variant_proof(absent_raw, valid_raw, error_raw)
    compile_proof = source_compile_proof()
    rejected = mutations(absent_raw, valid_raw)
    require(len(rejected) == 5, "INIT media mutation inventory drift")
    product_id, c2d = BASE.PREP.PAIR.product_world(ABSENT)
    require(all(BASE.PREP.PAIR.product_world(path)[0] == product_id
                for path in (VALID, ERROR)),
            "INIT product variants changed the frozen product identity")
    media = {
        "absent": {**bind(ABSENT), "remote_name": ABSENT_REMOTE,
                   "INIT_L65": None},
        "valid": {**bind(VALID), "remote_name": VALID_REMOTE,
                  "INIT_L65": bind(VALID_SOURCE)},
        "error": {**bind(ERROR), "remote_name": ERROR_REMOTE,
                  "INIT_L65": bind(ERROR_SOURCE)}}
    session = session_config(media)
    SESSION.write_bytes(canonical(session))
    value = {
        "format": "lisp65-c2-v17-init-l65-product-variants-media-v1",
        "recorded_on": "2026-08-27", "status": STATUS,
        "authority": {"contract": bind(CONTRACT),
                      "predecessor_media": bind(PREDECESSOR)},
        "frozen_pair": predecessor["accepted_pair"],
        "frozen_product_base": bind(product),
        "product_build_id": f"0x{product_id:08x}",
        "mounted_C2D_sha256": hashlib.sha256(c2d).hexdigest(),
        "media": media, "diff_attribution": proof,
        "source_compile_proof": compile_proof,
        "session": bind(SESSION), "mutations": rejected,
        "prior_device_evidence": {
            "I-absent": "accepted-green-owner-observation",
            "manual_swap_attempt": "discarded-before-claim",
            "I-error-r1": {
                "observation": "normal native REPL; no E38",
                "payload": "(car 1)",
                "attribution":
                    "OP_CAR is product-semantically totalized to NIL for non-pointers"}},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "replacement_media_builds": 3,
            "device_contacts_during_build": 0},
        "claim_limit": session["claim_scope"]}
    RECEIPT.write_bytes(canonical(value))
    print("v1.7 INIT product variants: BUILD PASS media=3 links=0 cards=0")


def check() -> None:
    predecessor, product = authority()
    BASE.check()
    value = load(RECEIPT)
    session = load(SESSION)
    audit_session(session)
    absent_raw, valid_raw, error_raw = (
        path.read_bytes() for path in (ABSENT, VALID, ERROR))
    proof = cross_variant_proof(absent_raw, valid_raw, error_raw)
    compile_proof = source_compile_proof()
    require(value.get("status") == STATUS
            and value.get("authority") == {
                "contract": bind(CONTRACT),
                "predecessor_media": bind(PREDECESSOR)}
            and value.get("frozen_pair") == predecessor["accepted_pair"]
            and value.get("frozen_product_base") == bind(product)
            and value.get("media") == {
                "absent": {**bind(ABSENT), "remote_name": ABSENT_REMOTE,
                           "INIT_L65": None},
                "valid": {**bind(VALID), "remote_name": VALID_REMOTE,
                          "INIT_L65": bind(VALID_SOURCE)},
                "error": {**bind(ERROR), "remote_name": ERROR_REMOTE,
                          "INIT_L65": bind(ERROR_SOURCE)} }
            and value.get("diff_attribution") == proof
            and value.get("source_compile_proof") == compile_proof
            and value.get("session") == bind(SESSION)
            and value.get("accounting") == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 3,
                "device_contacts_during_build": 0}
            and len(value.get("mutations", [])) == 5,
            "INIT product-variant media receipt drift")
    print("v1.7 INIT product variants: CHECK PASS media=3 links=0 cards=0 device=0")


def selftest() -> None:
    check()
    session = load(SESSION)
    trial = deepcopy(session)
    trial["choreography"]["manual_boot_media_swap"] = True
    rejected = _reject("manual-boot-media-swap", lambda: audit_session(trial))
    require(rejected["result"] == "rejected",
            "INIT session choreography mutation survived")
    if DEVICE_RESULT.exists():
        audit_device_result(load(DEVICE_RESULT))
    print("v1.7 INIT product variants: SELFTEST PASS mutations=6")


def record_device_result() -> None:
    require(not DEVICE_RESULT.exists(), "INIT device result already exists")
    value = device_result_value()
    DEVICE_RESULT.write_bytes(canonical(value))
    audit_device_result(value)
    print("v1.7 INIT product variants: DEVICE PASS Block-I=accepted")


def check_device_result() -> None:
    audit_device_result(load(DEVICE_RESULT))
    print("v1.7 INIT product variants: DEVICE CHECK PASS Block-I=accepted")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "record-device-result":
        record_device_result()
    elif action == "device-check":
        check_device_result()
    else:
        raise VariantError(
            "usage: build|check|selftest|record-device-result|device-check")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VariantError, OSError, KeyError, ValueError) as error:
        print(f"INIT PRODUCT VARIANTS: {error}", file=sys.stderr)
        raise SystemExit(1)
