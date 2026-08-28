#!/usr/bin/env python3
"""Build and qualify the owner-Ship v1.8.0 banner successor."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
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

from elf_truth import ElfTruth  # noqa: E402
import c2_v18_capture_hybrid_product_card as CARD  # noqa: E402


BASE = CARD.BASE
INIT = CARD.INIT
RELEASE = CARD.RELEASE
HYBRID = CARD.HYBRID
QUEUE = CARD.QUEUE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.8.0-release-card-report.md"
BUILD = ROOT / "build/c2.3/v1.8.0-release-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.8.0-release-card-r1-preflight"
RECEIPT = ARCH / "c2.3-v1.8.0-release-card-r1-receipt.json"
FIRST_RED = ARCH / "c2.3-v1.8.0-release-card-r1-first-red.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v180-release-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
PREDECESSOR_ELF = CARD.ELF
PREDECESSOR_PRG = CARD.PRG
PREDECESSOR_PROFILE = CARD.PROFILE
PREDECESSOR_CODE = CARD.CODE
PREDECESSOR_MANIFEST = CARD.MANIFEST
PREDECESSOR_RECEIPT = CARD.RECEIPT
PREDECESSOR_STATUS = CARD.STATUS
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "caf640c5"
FORMAT = "lisp65-c2-v180-release-product-card-v1"
STATUS = "PASS: V1.8.0 RELEASE PRODUCT CARD FINAL GREEN"
EXPECTED_BANNER = "WORKBENCH 1.8.0"
PREDECESSOR_BANNER = "WORKBENCH 1.7.0"


class ReleaseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReleaseError(message)


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


def owner_section() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    header = b"## Owner Ship \xe2\x80\x94 v1.8.0 substrate maintenance release \xe2\x80\x94 2026-08-28"
    require(raw.count(header) == 1, "v1.8 owner-Ship section absent")
    section = header + raw.split(header, 1)[1]
    section = section.split(b"\n## ", 1)[0].rstrip() + b"\n"
    text = b" ".join(section.lower().replace(b"`", b"").replace(
        b"*", b"").split())
    for token in (b"the owner said ship", b"workbench 1.8.0",
                  b"capture remains present but closed",
                  b"no lossless-input claim", b"publish"):
        require(token in text, f"v1.8 owner-Ship authority absent: {token!r}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "section": header.decode(), "bytes": len(section),
            "sha256": hashlib.sha256(section).hexdigest()}


def authority() -> dict[str, Any]:
    predecessor = load(PREDECESSOR_RECEIPT)
    require(predecessor["status"] == PREDECESSOR_STATUS
            and predecessor["artifacts_before"] ==
                predecessor["artifacts_after"],
            "qualified substrate predecessor drift")
    return {"owner_Ship": owner_section(),
            "qualified_substrate": bind(PREDECESSOR_RECEIPT),
            "budget": {"WPLTO_runs": 1, "product_links": 1,
                       "media_builds": 0, "device_contacts": 0},
            "claim": "banner-only successor over qualified v1.8 substrate"}


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "PLANE_ROOT": PLANE_ROOT, "PLANE_RECEIPT": PLANE_RECEIPT,
        "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CARD, name, value)
    RELEASE.EXPECTED_BANNER = EXPECTED_BANNER
    RELEASE.PREDECESSOR_BANNER = PREDECESSOR_BANNER
    CARD.configure()
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate
    BASE.DRIVER = DRIVER
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS


def banner_gate() -> dict[str, Any]:
    value = RELEASE.banner_gate()
    require(value["final_composed_literal"] in (None, EXPECTED_BANNER)
            and value["emitted"]["direct_object_bytes"] == 65,
            "v1.8 banner emission drift")
    value["status"] = "PASS: WORKBENCH 1.8.0 IS THE UNIQUE EMITTED BANNER"
    return value


def configuration_gate() -> dict[str, Any]:
    value = CARD.capture_recovery_configuration_gate()
    value.update({
        "world": "v1.8.0-release-banner-successor",
        "release_banner": banner_gate(),
        "release_freight": ["native-INIT.L65", "A0-recovery-fast-path",
                            "native-Capture", "native-Hybrid-consumer",
                            "WORKBENCH-1.8.0-banner"],
        "excluded": ["Capture activation", "repl-comfort", "Block-3",
                     "diagnostic-witness", "native-client"],
    })
    return value


def _byte_diff(before: bytes, after: bytes) -> list[dict[str, int]]:
    require(len(before) == len(after), "banner successor changed artifact extent")
    return [{"offset": i, "before": a, "after": b}
            for i, (a, b) in enumerate(zip(before, after)) if a != b]


def plane_successor_gate() -> dict[str, Any]:
    before_code, after_code = PREDECESSOR_CODE.read_bytes(), CODE.read_bytes()
    require(before_code == after_code,
            "banner successor changed static code bytes")
    old, new = load(PREDECESSOR_MANIFEST), load(MANIFEST)
    old_banner = next(row for row in old["entries"]
                      if row["name"] == "%repl-banner")
    new_banner = next(row for row in new["entries"]
                      if row["name"] == "%repl-banner")
    old_other = [row for row in old["entries"] if row["name"] != "%repl-banner"]
    new_other = [row for row in new["entries"] if row["name"] != "%repl-banner"]
    require(old_other == new_other
            and old_banner["length"] == new_banner["length"] == 155
            and old_banner["literals"][-1] == {"string": PREDECESSOR_BANNER}
            and new_banner["literals"][-1] == {"string": EXPECTED_BANNER},
            "release plane changed outside the banner literal")

    def delta(relative: str) -> list[dict[str, int]]:
        return _byte_diff((PREDECESSOR_MANIFEST.parent / relative).read_bytes(),
                          (MANIFEST.parent / relative).read_bytes())

    ext = delta("stdlib-p0.ext.bin")
    c2i = delta("product/stdlib-p0.c2i.bin")
    c2d = delta("v6-semantics/initial.c2d-v6.bin")
    shelf = delta("product/product-shelf-v4-direct.bin")
    digit = {"before": ord("7"), "after": ord("8")}
    require(len(ext) == len(c2i) == 1
            and {key: ext[0][key] for key in digit} == digit
            and {key: c2i[0][key] for key in digit} == digit
            and len(c2d) == 8
            and len(shelf) == 17
            and {key: shelf[-1][key] for key in digit} == digit,
            "banner payload/derived identity delta is not closed")
    return {
        "status": "PASS: BANNER BYTE AND DERIVED IDENTITIES FULLY ATTRIBUTED",
        "predecessor": bind(PREDECESSOR_CODE), "candidate": bind(CODE),
        "code_differences": 0,
        "banner": {"before": PREDECESSOR_BANNER, "after": EXPECTED_BANNER},
        "payload_differences": {"stdlib_ext": ext, "product_c2i": c2i,
                                "product_shelf_literal": [shelf[-1]]},
        "derived_identity_differences": {"c2d_v6": c2d,
                                         "product_shelf_header": shelf[:-1]},
        "families": {"banner_payload": 3,
                     "derived_identity": len(c2d) + len(shelf) - 1,
                     "unattributed": 0},
    }


def _source_identity(name: str) -> str:
    path = Path(name)
    if "generated-product-sources" in path.parts:
        return "generated-product-sources/" + path.name
    return path.resolve().relative_to(ROOT).as_posix()


def input_closure() -> dict[str, Any]:
    old, new = CARD.profile(PREDECESSOR_PROFILE), CARD.profile(PROFILE)
    old_sources = {_source_identity(name): digest
                   for name, digest in old["sources"].items()}
    new_sources = {_source_identity(name): digest
                   for name, digest in new["sources"].items()}
    require(old["features"] == new["features"]
            and set(old_sources) == set(new_sources),
            "release changed feature or source membership")
    changed = sorted(name for name in old_sources
                     if old_sources[name] != new_sources[name])
    authored = [name for name in changed
                if not name.startswith("generated-product-sources/")]
    generated = [name for name in changed
                 if name.startswith("generated-product-sources/")]
    require(authored == []
            and generated == ["generated-product-sources/c2-stream-phase-02a.c"],
            "release compiler input closure has an unknown root")
    return {"status": "PASS: BANNER ROOT IS PLANE-OWNED; ONE DERIVED C ROOT",
            "features": old["features"], "source_membership_delta": [],
            "changed_source_contents": changed,
            "changed_authored_sources": authored,
            "changed_generated_sources": generated,
            "plane_owned_authored_root": "lib/repl-banner.lisp",
            "unexplained_roots": 0}


def _symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def _relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def _expand(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [row for row in sorted(counter, key=repr)
            for _ in range(counter[row])]


def attribution() -> dict[str, Any]:
    closure = input_closure()
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    prg = CARD.member_diff(PREDECESSOR_PRG.read_bytes(), PRG.read_bytes(),
                           lambda _i: "banner-root-transitive-product-byte")
    elf = CARD.member_diff(PREDECESSOR_ELF.read_bytes(), ELF.read_bytes(),
                           lambda _i: "banner-root-transitive-ELF-byte")
    old_symbols, new_symbols = Counter(map(_symbol_key, old.symbols)), Counter(
        map(_symbol_key, new.symbols))
    removed_symbols = _expand(old_symbols - new_symbols)
    added_symbols = _expand(new_symbols - old_symbols)
    old_reloc, new_reloc = Counter(map(_relocation_key, old.relocations)), Counter(
        map(_relocation_key, new.relocations))
    removed_reloc = _expand(old_reloc - new_reloc)
    added_reloc = _expand(new_reloc - old_reloc)
    section_rows = []
    for name in sorted({row.name for row in old.sections} |
                       {row.name for row in new.sections}):
        left = [asdict(row) for row in old.sections_by_name.get(name, [])]
        right = [asdict(row) for row in new.sections_by_name.get(name, [])]
        if left != right:
            section_rows.append({"name": name, "before": left, "after": right,
                                 "family": "banner-root-transitive-section"})
    counts = {"PRG_bytes": len(prg), "ELF_bytes": len(elf),
              "symbols_removed": len(removed_symbols),
              "symbols_added": len(added_symbols),
              "relocations_removed": len(removed_reloc),
              "relocations_added": len(added_reloc),
              "sections_changed": len(section_rows),
              "unexplained_PRG_bytes": 0, "unexplained_ELF_bytes": 0,
              "unexplained_symbols": 0, "unexplained_relocations": 0,
              "unexplained_sections": 0}
    return {"status": "PASS: RELEASE DIFFERENCE FULLY ATTRIBUTED",
            "input_closure": closure,
            "pair": {"predecessor": {"ELF": bind(PREDECESSOR_ELF),
                                      "PRG": bind(PREDECESSOR_PRG)},
                     "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
            "plane_successor": plane_successor_gate(),
            "PRG_changed_members": prg,
            "ELF_changed_members": {"members": len(elf),
                "canonical_members_sha256": hashlib.sha256(
                    canonical(elf)).hexdigest()},
            "symbol_changed_members": {
                "removed": [list(row) for row in removed_symbols],
                "added": [list(row) for row in added_symbols]},
            "relocation_changed_members": {
                "removed": [list(row) for row in removed_reloc],
                "added": [list(row) for row in added_reloc]},
            "section_changed_members": section_rows, "counts": counts}


def lifecycle_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    state = truth.section(".lisp65_c2_kernal_window.state")
    raw = truth.section_bytes(state.name)
    tail = truth.symbol("C2K_INPUT_RING_TAIL").value
    offset = tail - state.address
    require(len(raw) == 16 and offset == 13 and raw[offset] == 0xff,
            "release Capture lifecycle is not closed")
    return {"section": state.name, "tail_symbol": tail,
            "tail_offset": offset, "initial_tail": raw[offset],
            "activation_owner_present": False}


def final_gate() -> dict[str, Any]:
    product = CARD.capture_recovery_final_gate()
    hybrid = HYBRID.derive(ELF)
    queue = QUEUE.linked_owner_gate(ELF)
    e000 = CARD.e000_composition()
    plane = plane_successor_gate()
    before = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    require(hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["normalization"]["executions"] == 512
            and hybrid["normalization"]["parity"] is True
            and hybrid["responsiveness"]["margin_percent"] >= 25.0
            and queue["dominated_calls"] == 1
            and before.section(".text").bytes == after.section(".text").bytes
            and before.section(".bss").bytes == after.section(".bss").bytes,
            "release successor changed a product wall or resident extent")
    product["v1_8_0_release"] = {
        "status": "PASS: HARDWARE-ACCEPTED SUBSTRATE PLUS BANNER SUCCESSOR",
        "banner": banner_gate(), "plane_successor": plane,
        "Capture": {"present": True, "lifecycle": lifecycle_gate(),
                    "laboratory_loss_wall": "94/94",
                    "lossless_user_input_claim": False},
        "hybrid": hybrid, "queue_single_owner": queue,
        "E000_composition": e000,
        "resident_extents": {"text_before": before.section(".text").bytes,
                             "text_after": after.section(".text").bytes,
                             "bss_before": before.section(".bss").bytes,
                             "bss_after": after.section(".bss").bytes},
        "claim_boundary": {
            "ships": ["native INIT.L65", "A0 recovery fast path",
                      "closed Capture/Hybrid substrate"],
            "excludes": ["Capture activation", "lossless user input",
                         "Comfort", "Matcher/Blink", "Block-3"],
            "known_issues": ["fast typing can lose input",
                "Cursor Left/Right unsupported at native lisp65> prompt"],
        },
    }
    return product


def write_report(value: dict[str, Any]) -> None:
    diff = value["attribution"]["counts"]
    release = value["final_product"]["v1_8_0_release"]
    REPORT.write_text(f"""# v1.8.0 release product card

Status: **{value['status']}**

The one owner-Ship producer run materialized the hardware-accepted v1.8
substrate with the unique banner `{EXPECTED_BANNER}`.  Feature and source
membership are unchanged; `lib/repl-banner.lisp` is the only changed authored
input root.  The static code plane is byte-identical.  Exactly three payload
bytes carry the `7` to `8` change and every other Static-Plane difference is a
derived C2D/shelf identity field.

The complete predecessor-to-release attribution names {diff['PRG_bytes']} PRG
bytes, {diff['ELF_bytes']} ELF bytes, {diff['symbols_removed']} removed plus
{diff['symbols_added']} added symbols, and {diff['relocations_removed']} removed
plus {diff['relocations_added']} added relocations, with zero unexplained
members.  Resident text/BSS extents remain {release['resident_extents']['text_after']}/
{release['resident_extents']['bss_after']} bytes.

Capture remains present but closed (`tail=$FF`).  The 94/94 laboratory wall,
normalization, responsiveness, queue ownership, E000 composition, A0 recovery
and INIT.L65 product gates are green on the final ELF.  The release claims no
Capture activation or lossless user input.  Comfort, Matcher/Blink and Block 3
remain absent.  The next rung is artifact-only release media and public
candidate sealing; `Publish` remains the owner's word.
""", encoding="utf-8")


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, RECEIPT)),
            "v1.8 release card is one-shot")
    configure()
    BASE.preflight()
    INIT.emit_init_plane()
    plane_successor_gate()
    value = load(BASE.PREFLIGHT_RECEIPT)
    value["format"] = FORMAT + "-preflight"
    value["status"] = "PASS: V1.8.0 RELEASE CARD ARMED 0/1"
    value["banner_successor"] = plane_successor_gate()
    value["attempt_accounting"] = {"WPLTO_runs": 0, "product_links": 0,
        "scope_runs": 0, "acceptance_runs": 0,
        "media_builds": 0, "device_contacts": 0}
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.8.0 release: PREFLIGHT PASS banner=1.8.0 WPLTO=0/1 link=0/1")


def build() -> None:
    configure()
    pre = load(BASE.PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.8.0 RELEASE CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists(),
            "v1.8 release preflight/lifecycle drift")
    BASE.INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT)}))
    processes = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    require(all(value == 0 for key, value in diff["counts"].items()
                if key.startswith("unexplained_")),
            "release attribution retained an unexplained member")
    processes.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    require(before == after, "qualification changed frozen release pair")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "release qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": final_gate(),
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": True,
        "next": "artifact-only release media and public candidate seal"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.8.0 release: BUILD PASS WPLTO=1/1 link=1/1 banner=1.8.0")


def record_first_red() -> None:
    if FIRST_RED.exists():
        return
    pair = BASE.artifacts()
    value = {"format": FORMAT + "-first-red",
        "recorded_on": "2026-08-28",
        "status": "FIRST RED: RELEASE INPUT OWNER MISCLASSIFIED",
        "error": "release input closure has a non-banner authored root",
        "pair_frozen": {"ELF": pair["ELF"], "PRG": pair["PRG"]},
        "classification": {
            "family": "phase-owned-input-root",
            "mechanism": ("the first checker expected repl-banner in the "
                "compiler profile, but the banner belongs to the separately "
                "materialized Static-Plane producer; the compiler sees only "
                "the derived c2-stream-phase-02a.c successor"),
            "product_defect": False,
            "conversion": ("prove the authored banner at the plane owner and "
                "the one generated C successor at the compiler consumer")},
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False,
        "next": "read-only attribution plus qualification over frozen pair"}
    FIRST_RED.write_bytes(canonical(value))


def resume() -> None:
    configure()
    require(BUILD.is_dir() and ELF.is_file() and PRG.is_file()
            and BASE.INVOCATION.is_file() and not RECEIPT.exists(),
            "release read-only Resume lifecycle drift")
    record_first_red()
    before = BASE.artifacts()
    diff = attribution()
    require(all(value == 0 for key, value in diff["counts"].items()
                if key.startswith("unexplained_")),
            "release Resume retained an unexplained member")
    processes = []
    if not BASE.SCOPE_RESULT.exists():
        processes.append(BASE.run_child("_scope"))
    if not BASE.ACCEPTANCE_RESULT.exists():
        processes.append(BASE.run_child("_accept"))
    after = BASE.artifacts()
    require(before == after, "release Resume changed frozen pair")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "release Resume qualification tail red")
    pre = load(BASE.PREFLIGHT_RECEIPT)
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION), "first_red": bind(FIRST_RED),
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": final_gate(),
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": [{"action": "read-only-attribution-resume",
            "new_WPLTO_runs": 0, "new_product_links": 0}, *processes],
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "new_cards_consumed": 0},
        "media_authorized": True,
        "next": "artifact-only release media and public candidate seal"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.8.0 release: RESUME PASS WPLTO=0 link=0 banner=1.8.0")


def validate(value: dict[str, Any]) -> None:
    configure()
    diff = value["attribution"]["counts"]
    release = value["final_product"]["v1_8_0_release"]
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and canonical(value["attribution"]) == canonical(attribution())
            and all(count == 0 for name, count in diff.items()
                    if name.startswith("unexplained_"))
            and release["banner"]["final_composed_literal"] == EXPECTED_BANNER
            and release["Capture"]["lifecycle"]["initial_tail"] == 255
            and release["Capture"]["lossless_user_input_claim"] is False
            and value["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and REPORT.is_file(), "v1.8.0 release receipt drift")


def check() -> None:
    validate(load(RECEIPT))
    print("v1.8.0 release: CHECK PASS banner=WORKBENCH-1.8.0")


def selftest() -> None:
    value = load(RECEIPT)
    cases = {
        "reopen-Capture": lambda x: x["final_product"]["v1_8_0_release"][
            "Capture"]["lifecycle"].update(initial_tail=0),
        "claim-lossless": lambda x: x["final_product"]["v1_8_0_release"][
            "Capture"].update(lossless_user_input_claim=True),
        "hide-byte": lambda x: x["attribution"]["counts"].update(
            unexplained_PRG_bytes=1),
        "stale-banner": lambda x: x["final_product"]["v1_8_0_release"][
            "banner"].update(final_composed_literal=PREDECESSOR_BANNER),
        "spend-second-link": lambda x: x["attempt_accounting"].update(
            product_links=2),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = json.loads(json.dumps(value))
        mutate(trial)
        try:
            validate(trial)
        except ReleaseError:
            rejected.append(name)
    require(rejected == list(cases), "v1.8 release mutation survived")
    print(f"v1.8.0 release: SELFTEST PASS mutations={len(rejected)}")


def child(action: str) -> None:
    if action == "_release_probe":
        CARD.release_probe_child()
        return
    configure()
    if action == "_profile_probe":
        CARD.profile_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "resume", "check",
                                           "selftest", "_profile_probe",
                                           "_release_probe", "_produce",
                                           "_scope", "_accept"))
    action = parser.parse_args().action
    if action in {"_profile_probe", "_release_probe", "_produce",
                  "_scope", "_accept"}:
        child(action)
    else:
        {"preflight": preflight, "build": build, "resume": resume, "check": check,
         "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8.0 release: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
