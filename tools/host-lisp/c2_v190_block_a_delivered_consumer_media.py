#!/usr/bin/env python3
"""Pack the reviewed r8 Block-A repair and bind its one counter contact."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v190_blocks_ab_acceptance_media as BASE  # noqa: E402
import c2_v190_block_a_delivered_consumer_repair as R8  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
AUTHORITY_HEADER = (
    "## Independent review — Block A delivered-consumer repair — 2026-08-30")
FOLLOWUP_SESSION = ROOT / (
    "config/c2-v190-block-a-forced-collection-followup-session.json")
FIRST_RED = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-first-red-receipt.json")
CARD_RECEIPT = R8.RECEIPT
CARD_BUILD = R8.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = R8.PLANE_ROOT
BUILD = ROOT / "build/c2.3/v1.9-block-a-delivered-consumer-r8-media"
STATIC = BUILD / "inputs/static-plane"
TARGET = BUILD / "canonical-product"
SHARED = BUILD / "shared-system"
RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-r8-media-receipt.json")
SESSION = ROOT / "config/c2-v190-block-a-delivered-consumer-r8-session.json"
REPORT = ROOT / "docs/planning/v1.9.0-block-a-delivered-consumer-media.md"
ELF = R8.ELF
PRG = R8.PRG
SCOPE = CARD_BUILD / "owner-scope-result.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
PRODUCT_REMOTE = "V19R8P.D81"
PRODUCT_ID = 0x75FF7B1C
PLANE_BYTES = 47469
EXPECTED = {
    "PRG": (41564,
        "55725440e41b1dd9f1cf1fa912161846dc523ccc4b8e17ef869eba29430c717d"),
    "ELF": (635496,
        "1b7e85b44060b7729e22f0888f02ac6f21e97f54ade144a1a0fb34e5913f01f2"),
}
STATUS = "PASS: V1.9 BLOCK-A R8 ARTIFACT-ONLY MEDIA READY"
SESSION_STATUS = "READY: V1.9 BLOCK-A R8 COUNTER CONTACT"


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


def write(path: Path, value: dict[str, Any]) -> None:
    raw = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def section_bind(path: Path, header: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"authority section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": path.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(PRG), "ELF": bind(ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"r8 {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    card = load(CARD_RECEIPT)
    red = load(FIRST_RED)
    require(card["status"] == R8.STATUS
            and card["artifacts_before"] == card["artifacts_after"]
            and {name: card["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == accepted_pair()
            and red["device"]["observed"] == {
                "raw": 2, "seen": 2, "stored": 2, "taken": 0},
            "r8 review/media authority drift")
    return {"independent_review": section_bind(PLAN, AUTHORITY_HEADER),
            "repair_card": bind(CARD_RECEIPT), "device_first_red": bind(FIRST_RED),
            "rule": "artifact-only successor; zero WPLTO and product links"}


def configure() -> None:
    R8.configure()
    values = {
        "CARD_BUILD": CARD_BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "BUILD": BUILD, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": RECEIPT,
        "SESSION": SESSION, "CARD_RECEIPT": CARD_RECEIPT,
        "SCOPE": SCOPE, "ACCEPTANCE": ACCEPTANCE,
        "PRODUCT_REMOTE": PRODUCT_REMOTE, "PRODUCT_ID": PRODUCT_ID,
        "PLANE_BYTES": PLANE_BYTES, "EXPECTED": EXPECTED, "STATUS": STATUS,
    }
    for name, value in values.items():
        setattr(BASE, name, value)
    BASE.accepted_pair = accepted_pair
    BASE.authority = authority
    BASE.configure_candidate = configure_candidate
    BASE.configure_paths()


def configure_candidate() -> None:
    R8.configure()
    R8.CARD.BASE.configure_full_candidate()
    R8.R7.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    R8.R7.PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    R8.CARD.CLIENT.INIT._configure_plane_module()
    R8.CARD.CLIENT.CURRENT_PLANE.bind_current_plane(STATIC)
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    truth = ElfTruth.read(ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    section = truth.section(BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "r8 verifier-binding size drift")


def preflight() -> dict[str, Any]:
    configure()
    card = load(CARD_RECEIPT)
    scope = load(SCOPE)
    acceptance = load(ACCEPTANCE)
    identity = load(SOURCE_STATIC / "product/substitution-artifacts.json")
    require(card["status"] == R8.STATUS
            and scope["status"] == acceptance["status"] == "PASS"
            and card["attempt_accounting"] == {
                "WPLTO_runs_total": 1, "product_links_total": 1,
                "resume_WPLTO_runs": 0, "resume_product_links": 0,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and identity["product_build_id_u32"] == PRODUCT_ID
            and R8.CODE.stat().st_size == PLANE_BYTES,
            "r8 artifact-only preflight red")
    return {"status": "PASS: R8 ARTIFACT-ONLY MEDIA PREFLIGHT",
            "authority": authority(), "accepted_pair": accepted_pair(),
            "plane": bind(R8.CODE), "product_identity": bind(
                SOURCE_STATIC / "product/substitution-artifacts.json"),
            "build_budget": {"WPLTO_runs": 0, "product_links": 0}}


def closure_adapter() -> dict[str, Any]:
    value = preflight()
    value.update({"format": "lisp65-v190-block-a-r8-media-adapter-v1",
        "completion_input_projection": BASE.prepare_static_inputs(),
        "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE)})
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = BASE.product_manifest(completion)
    value["static_plane"]["membership_authority"] = (
        "r8 final-ELF composed ownership")
    value["static_plane"]["largest_contiguous_hole"]["bytes"] = 16197
    BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.CAN.check()
    return value


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] == 65489
            and owners[0]["bytes"] == PLANE_BYTES
            and plane["largest_contiguous_hole"]["bytes"] == 16197
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 47
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "r8 packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def counter_addresses() -> dict[str, str]:
    truth = ElfTruth.read(ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    names = {"raw": "C2K_INPUT_EVENTS_RAW", "seen": "C2K_INPUT_EVENTS_SEEN",
        "stored": "C2K_INPUT_EVENTS_STORED", "taken": "C2K_INPUT_EVENTS_TAKEN"}
    return {key: f"0x{truth.symbol(name).value:04X}"
            for key, name in names.items()}


def session_config(product: Path) -> dict[str, Any]:
    value = copy.deepcopy(load(FOLLOWUP_SESSION))
    value.update({"format": "lisp65-c2-v190-block-a-r8-counter-session-v1",
                  "status": SESSION_STATUS, "recorded_on": "2026-08-30"})
    value["artifact_world"] = {
        "product_medium": {**bind(product), "remote_name": PRODUCT_REMOTE},
        "ELF": bind(ELF), "r8_card": bind(CARD_RECEIPT),
        "review_authority": section_bind(PLAN, AUTHORITY_HEADER),
        "predecessor_first_red": bind(FIRST_RED),
        "optional_libraries": [], "product_changes_from_r7": 1,
    }
    value["counter_witness"]["addresses"] = counter_addresses()
    value["steps"][0]["action"] = (
        f"cold boot {PRODUCT_REMOTE} alone and wait for the live lisp65> prompt")
    value["steps"][0]["expect"] = "normal r8 native prompt; no optional library"
    require(value["collection_derivation"]["bound_printable_insertions"] == 199
            and value["counter_witness"]["event_arithmetic"] == {
                "delete_backward": 192, "physical_events": 392,
                "printable_insertions": 199, "return": 1,
                "wraps": 1, "expected_each_modulo_256": 136}
            and value["counter_witness"]["green"] ==
                "raw=seen=stored=taken=136 and visible numeric oracle=7"
            and counter_addresses() == {"raw": "0xBCFC", "seen": "0xBCFD",
                                       "stored": "0xBCFE", "taken": "0xBCFF"},
            "r8 counter-session derivation drift")
    return value


def finish(media: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    configure()
    BASE.MEDIA.check()
    product = BASE.MEDIA.PRODUCT_D81
    product_id, mounted_c2d = BASE.PREP.PAIR.product_world(product)
    require(product_id == PRODUCT_ID, "r8 product D81 carries wrong world")
    visible = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(product.read_bytes())
    require(b"INIT.L65" not in visible and b"REPL-COMFORT" not in visible,
            "r8 medium contains excluded optional freight")
    session = session_config(product)
    write(SESSION, session)
    value = {"format": "lisp65-c2-v190-block-a-r8-media-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": authority(), "accepted_pair": accepted_pair(),
        "completion": bind(BASE.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(BASE.MEDIA.MANIFEST),
        "media": {"product": bind(product), "work": bind(BASE.MEDIA.WORK_D81)},
        "mounted_product_world": {"product_build_id": f"0x{product_id:08x}",
            "C2D_bytes": len(mounted_c2d),
            "C2D_sha256": hashlib.sha256(mounted_c2d).hexdigest()},
        "packed_PRG_facade": completion["packed_PRG_facade"],
        "composed_bank2": static_plane_gate(), "session": bind(SESSION),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "product_media_builds": 1, "work_media_builds": 1,
            "device_contacts": 0},
        "next": "owner says ready; deploy V19R8P.D81 and run A-FC-1..5"}
    write(RECEIPT, value)
    REPORT.write_text(f"""# v1.9 Block A — r8 acceptance medium

Status: **{STATUS}**

The canonical artifact-only Completion consumed the reviewed frozen pair with
zero WPLTO and zero product links.  The packed product medium is
`{product.name}` (remote `{PRODUCT_REMOTE}`), SHA-256
`{value['media']['product']['sha256']}`.  Its mounted product identity is
`0x{product_id:08x}` and its composed Bank-2 map owns the 47,469-byte r8 plane
with a 16,197-byte largest contiguous hole.

The owner session reuses the bound six-pass forced-collection sequence.  Its
visible oracle is `7`; the sole stopped-state read at `$BCFC..$BCFF` must be
`88 88 88 88` (136 each).  No optional library is present or required.
""", encoding="utf-8")
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "r8 media build is one-shot")
    adapter = closure_adapter()
    (BUILD / "closure-adapter.json").parent.mkdir(parents=True, exist_ok=True)
    write(BUILD / "closure-adapter.json", adapter)
    configure()
    completion = BASE.complete_artifacts()
    product_manifest(completion)
    configure()
    media = BASE.MEDIA.build(stager_compile_defines=(BASE.PREP.LIVENESS.OPT_IN,))
    value = finish(media, completion)
    check()
    print("v1.9 Block-A r8 media: PASS artifact-only "
          f"product={value['media']['product']['sha256']} device=0")


def check() -> None:
    configure()
    value = load(RECEIPT)
    session = load(SESSION)
    require(value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["authority"] == authority()
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "artifact_completions": 1,
                "product_media_builds": 1, "work_media_builds": 1,
                "device_contacts": 0}
            and session == session_config(BASE.MEDIA.PRODUCT_D81)
            and bind(SESSION) == value["session"],
            "r8 media receipt/session drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values()]:
        require(bind(ROOT / row["path"]) == row,
                f"r8 prepared artifact identity drift: {row['path']}")
    BASE.MEDIA.check()
    require(value["composed_bank2"] == static_plane_gate(),
            "r8 composed Bank-2 proof drift")
    print("v1.9 Block-A r8 media: CHECK PASS artifact-only")


def source_check() -> None:
    value = load(RECEIPT)
    session = load(SESSION)
    review = section_bind(PLAN, AUTHORITY_HEADER)
    require(value["status"] == STATUS
            and value["authority"]["independent_review"] == review
            and value["authority"]["repair_card"] == bind(CARD_RECEIPT)
            and value["authority"]["device_first_red"] == bind(FIRST_RED)
            and {role: (row["bytes"], row["sha256"])
                 for role, row in value["accepted_pair"].items()} == EXPECTED
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "artifact_completions": 1,
                "product_media_builds": 1, "work_media_builds": 1,
                "device_contacts": 0}
            and session["status"] == SESSION_STATUS
            and session["artifact_world"]["product_medium"]["sha256"] ==
                value["media"]["product"]["sha256"]
            and session["artifact_world"]["product_medium"]["remote_name"] ==
                PRODUCT_REMOTE
            and session["counter_witness"]["green"] ==
                "raw=seen=stored=taken=136 and visible numeric oracle=7"
            and session["counter_witness"]["event_arithmetic"][
                "expected_each_modulo_256"] == expected_counter()
            and len(session["steps"]) == 5
            and REPORT.is_file()
            and STATUS in REPORT.read_text(encoding="utf-8"),
            "r8 tracked media/session closure drift")
    print("v1.9 Block-A r8 media: SOURCE CHECK PASS artifact-only")


def selftest() -> None:
    cases = {
        "omit-final-return": (199 + 192) % 256,
        "forget-wrap": 392,
        "restore-device-red-taken": 0,
    }
    rejected = [name for name, observed in cases.items()
                if observed != expected_counter()]
    require(rejected == list(cases), "r8 media selftest mutation survived")
    print(f"v1.9 Block-A r8 media: SELFTEST PASS mutations={len(rejected)}")


def expected_counter() -> int:
    return (199 + 192 + 1) % 256


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        value = preflight()
        print(f"v1.9 Block-A r8 media: PREFLIGHT PASS {value['accepted_pair']['PRG']['sha256']}")
    elif action == "build":
        build()
    elif action == "check":
        check()
    elif action == "source-check":
        source_check()
    elif action == "selftest":
        selftest()
    else:
        raise MediaError("usage: preflight|build|check|source-check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 Block-A r8 media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
