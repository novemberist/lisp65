#!/usr/bin/env python3
"""Build and verify the host-only Directory-only/L65M-v2 measurement probe."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/directory-only-probe"
CONTRACT = ROOT / "config/directory-only-l65m-v2-contract-draft.json"
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
STACK_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/r2-canonical-stack-guard-resolution.json"
HEADER = struct.Struct("<4sBBHIHHHHHHHHHHHHH")
ENTRY = struct.Struct("<HBBHH")
NODE = struct.Struct("<BBhHHH")
K_SYMBOL = 4
K_ENTRY_REF = 8

sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as B  # noqa: E402
import l65m_contract as V1  # noqa: E402


class ProbeError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeError(f"{path} must contain an object")
    return value


def align2(data: bytes) -> bytes:
    return data + (b"\0" if len(data) & 1 else b"")


def source_path(name: str, sources: list[str], *, overridden: bool) -> str:
    definition = re.compile(r"\(def(?:un|macro)\s+" + re.escape(name) + r"(?=[\s()])")
    matches = []
    for source in sources:
        text = (ROOT / source).read_text(encoding="utf-8")
        if definition.search(text):
            matches.append(source)
    if len(matches) == 1:
        return matches[0]
    if overridden and matches:
        return matches[-1]
    if len(matches) != 1:
        raise ProbeError(f"{name}: expected one source definition, found {matches}")
    raise ProbeError(f"{name}: unreachable source mapping state")


def call_slots(blob: bytes, entry: dict[str, Any], ledger: dict[str, Any]) -> set[int]:
    start, length = int(entry["blob_offset"]), int(entry["length"])
    code = B.decode_code_object(blob[start : start + length])
    result: set[int] = set()
    pc = 0
    while pc < len(code.payload):
        spec, operand, pc = B.decode_instruction(
            code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger
        )
        if spec.mnemonic in ("CALL", "TAILCALL"):
            result.add(int(operand[0]))
    return result


def pack_v2(manifest: dict[str, Any], image: bytes, library: str) -> tuple[bytes, dict[str, Any]]:
    V1.validate_image(image, require_strict_arity=True)
    blob_len, metadata_len = struct.unpack_from("<HH", image, 0)
    blob = image[4 : 4 + blob_len]
    old_metadata = image[4 + blob_len :]
    if len(old_metadata) != metadata_len:
        raise ProbeError("v1 input length drift")
    header = list(HEADER.unpack_from(old_metadata, 0))
    if header[0] != b"L65M" or header[1] != 1 or header[2] != HEADER.size:
        raise ProbeError("input is not canonical L65M-v1")
    entries = deepcopy(manifest["entries"])
    nodes = deepcopy(manifest["literal_nodes"])
    indices = [int(value) for value in manifest["literal_index"]]
    patches = deepcopy(manifest["literal_patches"])
    candidates = [entry["name"] for entry in entries if entry["name"].startswith("%")]
    ordinals = {entry["name"]: index for index, entry in enumerate(entries)}
    candidate_set = set(candidates)
    ledger = load(LEDGER)
    direct_refs = designator_refs = 0
    referenced_nodes: set[int] = set()
    for entry in entries:
        calls = call_slots(blob, entry, ledger)
        first = int(entry["lit_first"])
        for slot, literal in enumerate(entry["literals"]):
            if not isinstance(literal, dict) or literal.get("symbol") not in candidate_set:
                continue
            node_index = indices[first + slot]
            node = nodes[node_index]
            if node.get("kind") != K_SYMBOL or node.get("name") != literal["symbol"]:
                raise ProbeError("literal/node symbol parity drift")
            node.update(
                kind=K_ENTRY_REF, value=0, first=ordinals[literal["symbol"]],
                count=0, name=None,
            )
            referenced_nodes.add(node_index)
            if slot in calls:
                direct_refs += 1
            else:
                designator_refs += 1
    remaining = [
        node.get("name") for node in nodes
        if node.get("kind") == K_SYMBOL and node.get("name") in candidate_set
    ]
    if remaining:
        raise ProbeError(f"candidate symbols remain materialized: {sorted(set(remaining))}")

    strings: dict[str, int] = {}
    string_bytes = bytearray()

    def add_string(text: str | None) -> int:
        if text is None:
            return 0xFFFF
        if text not in strings:
            raw = text.encode("utf-8") + b"\0"
            if len(string_bytes) + len(raw) >= 0xFFFF:
                raise ProbeError("name offset would reach anonymous sentinel")
            strings[text] = len(string_bytes)
            string_bytes.extend(raw)
        return strings[text]

    for entry in entries:
        if entry["name"] not in candidate_set:
            add_string(entry["name"])
    for node in nodes:
        add_string(node.get("name"))

    metadata = bytearray(b"\0" * HEADER.size)

    def section(payload: bytes) -> int:
        nonlocal metadata
        metadata = bytearray(align2(bytes(metadata)))
        offset = len(metadata)
        metadata.extend(payload)
        return offset

    entry_bytes = bytearray()
    for entry in entries:
        address = int(entry["ext_addr"], 0)
        name_off = 0xFFFF if entry["name"] in candidate_set else add_string(entry["name"])
        entry_bytes.extend(ENTRY.pack(name_off, (address >> 16) & 0xFF, int(entry["flags"]), address & 0xFFFF, int(entry["length"])))
    node_bytes = bytearray()
    for node in nodes:
        node_bytes.extend(NODE.pack(int(node["kind"]), 0, int(node["value"]), int(node["first"]), int(node["count"]), add_string(node.get("name"))))
    index_bytes = b"".join(struct.pack("<H", item) for item in indices)
    patch_bytes = b"".join(struct.pack("<HH", int(item["blob_offset"]), int(item["node"])) for item in patches)
    entries_off = section(bytes(entry_bytes))
    index_off = section(index_bytes)
    nodes_off = section(bytes(node_bytes))
    patches_off = section(patch_bytes)
    strings_off = section(bytes(string_bytes))
    metadata = bytearray(align2(bytes(metadata)))
    metadata[:HEADER.size] = HEADER.pack(
        b"L65M", 2, HEADER.size, 0, int(manifest["base_addr"], 0), blob_len,
        len(metadata), len(entries), len(indices), len(nodes), len(patches),
        entries_off, index_off, nodes_off, patches_off, strings_off,
        len(string_bytes), 0,
    )
    output = struct.pack("<HH", blob_len, len(metadata)) + blob + bytes(metadata)
    old_strings_bytes = header[16]
    maps = []
    for ordinal, entry in enumerate(entries):
        if entry["name"] not in candidate_set:
            continue
        start, length = int(entry["blob_offset"]), int(entry["length"])
        maps.append({
            "ordinal": ordinal,
            "helper_name": entry["name"],
            "source_path": source_path(
                entry["name"], manifest["sources"],
                overridden=entry["name"] in set(manifest.get("resident_overrides", [])),
            ),
            "code_sha256": sha(blob[start : start + length]),
            "runtime_message": f"lib {library} entry #{ordinal}",
        })
    report = {
        "library": library,
        "v1_sha256": sha(image),
        "v2_sha256": sha(output),
        "entries": len(entries),
        "anonymous_entries": len(candidates),
        "symbol_intern_savings": len(candidates),
        "namepool_savings_bytes": old_strings_bytes - len(string_bytes),
        "directory_entry_delta": 0,
        "container_delta_bytes": len(output) - len(image),
        "direct_entry_refs": direct_refs,
        "function_designator_entry_refs": designator_refs,
        "entry_ref_nodes": len(referenced_nodes),
        "old_string_bytes": old_strings_bytes,
        "new_string_bytes": len(string_bytes),
        "diagnostic_map": maps,
    }
    return output, report


def validate_v2(image: bytes) -> dict[str, int]:
    if len(image) < 4 + HEADER.size:
        raise ProbeError("container too short")
    blob_len, metadata_len = struct.unpack_from("<HH", image, 0)
    if len(image) != 4 + blob_len + metadata_len:
        raise ProbeError("container length mismatch")
    metadata = image[4 + blob_len :]
    fields = HEADER.unpack_from(metadata, 0)
    magic, version, header_size, flags = fields[:4]
    if magic != b"L65M" or version not in (1, 2) or header_size != HEADER.size or flags:
        raise ProbeError("version-bound header rejected")
    entry_count, index_count, node_count, patch_count = fields[7:11]
    entries_off, index_off, nodes_off, patches_off, strings_off, strings_bytes = fields[11:17]
    if fields[6] != metadata_len or fields[17] or strings_off + strings_bytes > metadata_len:
        raise ProbeError("header/section bounds rejected")
    strings_raw = metadata[strings_off : strings_off + strings_bytes]
    starts: dict[int, bytes] = {}
    pos = 0
    while pos < len(strings_raw):
        end = strings_raw.find(b"\0", pos)
        if end < 0:
            raise ProbeError("unterminated string")
        starts[pos] = strings_raw[pos:end]
        pos = end + 1
    named: set[bytes] = set()
    entry_flags = []
    anonymous = 0
    cursor = 0
    for ordinal in range(entry_count):
        name_off, bank, eflags, offset, length = ENTRY.unpack_from(metadata, entries_off + ordinal * ENTRY.size)
        entry_flags.append(eflags)
        if bank or eflags & ~1 or offset != cursor or offset + length > blob_len:
            raise ProbeError("entry ordinal/range validation failed")
        cursor += length
        if name_off == 0xFFFF:
            if version != 2 or eflags & 1:
                raise ProbeError("anonymous sentinel rejected for version/flags")
            anonymous += 1
        else:
            if name_off >= 0xFFFF or name_off not in starts or not starts[name_off]:
                raise ProbeError("legal name offset invariant failed")
            if starts[name_off] in named:
                raise ProbeError("duplicate named entry")
            named.add(starts[name_off])
    if cursor != blob_len:
        raise ProbeError("entry coverage failed")
    entry_refs = 0
    for index in range(node_count):
        kind, reserved, value, first, count, name_off = NODE.unpack_from(metadata, nodes_off + index * NODE.size)
        if reserved or not 1 <= kind <= K_ENTRY_REF:
            raise ProbeError("node kind/reserved rejected")
        if kind == K_ENTRY_REF:
            if version != 2 or value or count or name_off != 0xFFFF or first >= entry_count or entry_flags[first] & 1:
                raise ProbeError("entry-ref ordinal validation failed")
            entry_refs += 1
    if index_off + index_count * 2 > metadata_len or patches_off + patch_count * 4 > metadata_len:
        raise ProbeError("index/patch bounds failed")
    return {"anonymous_entries": anonymous, "entry_ref_nodes": entry_refs}


def artifact_paths(library: str) -> tuple[Path, Path]:
    return EVIDENCE / f"{library}-v2.l65m", EVIDENCE / f"{library}-diagnostic-map.json"


def generate() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    reports = []
    for library in ("ide", "idex"):
        manifest_path = ROOT / f"build/bytecode/dialect-v2/libs/{library}.manifest.json"
        image_path = ROOT / f"build/bytecode/dialect-v2/libs/{library}.ext.bin"
        manifest, image = load(manifest_path), image_path.read_bytes()
        transformed, report = pack_v2(manifest, image, library)
        observed = validate_v2(transformed)
        if observed["anonymous_entries"] != report["anonymous_entries"] or observed["entry_ref_nodes"] != report["entry_ref_nodes"]:
            raise ProbeError("generated v2 validation/report drift")
        out, mapping = artifact_paths(library)
        out.write_bytes(transformed)
        mapping.write_text(json.dumps({"format": "lisp65-directory-only-diagnostic-map-v1", "library": library, "artifact_sha256": sha(transformed), "entries": report.pop("diagnostic_map")}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report.update({"artifact": out.relative_to(ROOT).as_posix(), "artifact_sha256": sha(transformed), "diagnostic_map": mapping.relative_to(ROOT).as_posix(), "diagnostic_map_sha256": file_sha(mapping)})
        reports.append(report)
    totals = {key: sum(item[key] for item in reports) for key in (
        "entries", "anonymous_entries", "symbol_intern_savings", "namepool_savings_bytes",
        "directory_entry_delta", "container_delta_bytes", "direct_entry_refs",
        "function_designator_entry_refs", "entry_ref_nodes",
    )}
    stack = load(STACK_RECEIPT)
    product_sha = stack["targets"][0]["artifact_set_sha256"]
    receipt = {
        "format": "lisp65-directory-only-l65m-v2-probe-receipt-v1",
        "status": "passed-not-promoted",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "contract": {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": file_sha(CONTRACT)},
        "tool_sha256": file_sha(Path(__file__)),
        "libraries": reports,
        "totals": totals,
        "projection": {
            "expected": {"anonymous_entries": 100, "symbol_intern_savings": 100, "namepool_savings_bytes": 2006, "directory_entry_delta": 0},
            "result": "exact",
            "composition_headroom": {"symbols_before": 39, "symbols_after": 139, "namepool_bytes_before": 490, "namepool_bytes_after": 2496, "post_align_directory_slots": 32},
        },
        "negative_matrix": {
            "v1_sentinel": "rejected", "unknown_version": "rejected",
            "anonymous_macro": "rejected", "entry_ref_out_of_range": "rejected",
            "entry_ref_to_macro": "rejected", "duplicate_named_entry": "rejected",
        },
        "bank_delta": {
            "baseline_product_sha256": product_sha, "candidate_product_sha256": product_sha,
            "baseline_banked_headroom_bytes": 435, "candidate_banked_headroom_bytes": 435,
            "delta_bytes": 0, "authorization": None,
        },
    }
    (EVIDENCE / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"directory-only-probe: WROTE anonymous={totals['anonymous_entries']} names={totals['namepool_savings_bytes']} refs={totals['entry_ref_nodes']}")


def check() -> None:
    receipt_path = EVIDENCE / "receipt.json"
    receipt = load(receipt_path)
    if receipt.get("format") != "lisp65-directory-only-l65m-v2-probe-receipt-v1" or receipt.get("status") != "passed-not-promoted":
        raise ProbeError("probe receipt identity drift")
    source_commit = receipt.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ProbeError("probe source commit is missing")
    for path, expected in (
        (Path(__file__).relative_to(ROOT).as_posix(), receipt["tool_sha256"]),
        (CONTRACT.relative_to(ROOT).as_posix(), receipt["contract"]["sha256"]),
    ):
        result = subprocess.run(
            ["git", "show", f"{source_commit}:{path}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode or sha(result.stdout) != expected:
            raise ProbeError(f"probe source snapshot binding drift: {path}")
    totals = {key: 0 for key in receipt["totals"]}
    if [item.get("library") for item in receipt["libraries"]] != ["ide", "idex"]:
        raise ProbeError("probe library order/coverage drift")
    expected_libraries = {
        "ide": {"entries": 150, "anonymous_entries": 87, "symbol_intern_savings": 87, "namepool_savings_bytes": 1715, "directory_entry_delta": 0, "container_delta_bytes": -1714, "direct_entry_refs": 227, "function_designator_entry_refs": 4, "entry_ref_nodes": 231},
        "idex": {"entries": 29, "anonymous_entries": 13, "symbol_intern_savings": 13, "namepool_savings_bytes": 291, "directory_entry_delta": 0, "container_delta_bytes": -290, "direct_entry_refs": 21, "function_designator_entry_refs": 0, "entry_ref_nodes": 21},
    }
    for report in receipt["libraries"]:
        artifact = ROOT / report["artifact"]
        mapping = ROOT / report["diagnostic_map"]
        if file_sha(artifact) != report["artifact_sha256"] or file_sha(mapping) != report["diagnostic_map_sha256"]:
            raise ProbeError("probe artifact/map binding drift")
        observed = validate_v2(artifact.read_bytes())
        if observed["anonymous_entries"] != report["anonymous_entries"] or observed["entry_ref_nodes"] != report["entry_ref_nodes"]:
            raise ProbeError("probe artifact semantic drift")
        if any(report.get(key) != value for key, value in expected_libraries[report["library"]].items()):
            raise ProbeError("probe per-library measurement drift")
        diagnostic = load(mapping)
        if (
            diagnostic.get("format") != "lisp65-directory-only-diagnostic-map-v1"
            or diagnostic.get("library") != report["library"]
            or diagnostic.get("artifact_sha256") != report["artifact_sha256"]
            or not isinstance(diagnostic.get("entries"), list)
            or len(diagnostic["entries"]) != report["anonymous_entries"]
        ):
            raise ProbeError("probe diagnostic map identity/coverage drift")
        ordinals = []
        for entry in diagnostic["entries"]:
            ordinal = entry.get("ordinal")
            ordinals.append(ordinal)
            if (
                type(ordinal) is not int or ordinal < 0
                or entry.get("runtime_message") != f"lib {report['library']} entry #{ordinal}"
                or not isinstance(entry.get("helper_name"), str)
                or not entry["helper_name"].startswith("%")
                or not isinstance(entry.get("source_path"), str)
                or not (ROOT / entry["source_path"]).is_file()
                or not isinstance(entry.get("code_sha256"), str)
                or len(entry["code_sha256"]) != 64
            ):
                raise ProbeError("probe diagnostic map entry drift")
        if len(ordinals) != len(set(ordinals)):
            raise ProbeError("probe diagnostic ordinals are not unique")
        for key in totals:
            totals[key] += report[key]
    expected_totals = {"entries": 179, "anonymous_entries": 100, "symbol_intern_savings": 100, "namepool_savings_bytes": 2006, "directory_entry_delta": 0, "container_delta_bytes": -2004, "direct_entry_refs": 248, "function_designator_entry_refs": 4, "entry_ref_nodes": 252}
    expected_projection = {"anonymous_entries": 100, "symbol_intern_savings": 100, "namepool_savings_bytes": 2006, "directory_entry_delta": 0}
    expected_headroom = {"symbols_before": 39, "symbols_after": 139, "namepool_bytes_before": 490, "namepool_bytes_after": 2496, "post_align_directory_slots": 32}
    if totals != receipt["totals"] or totals != expected_totals or receipt["projection"].get("expected") != expected_projection or receipt["projection"].get("composition_headroom") != expected_headroom or receipt["projection"]["result"] != "exact":
        raise ProbeError("probe totals/projection drift")
    if receipt.get("negative_matrix") != {"v1_sentinel": "rejected", "unknown_version": "rejected", "anonymous_macro": "rejected", "entry_ref_out_of_range": "rejected", "entry_ref_to_macro": "rejected", "duplicate_named_entry": "rejected"}:
        raise ProbeError("probe negative matrix drift")
    bank = receipt["bank_delta"]
    if bank["delta_bytes"] != 0 or bank["baseline_product_sha256"] != bank["candidate_product_sha256"] or bank["authorization"] is not None:
        raise ProbeError("probe bank delta drift")
    print(f"directory-only-probe: PASS anonymous={totals['anonymous_entries']} names={totals['namepool_savings_bytes']} refs={totals['entry_ref_nodes']} bank_delta=0")


def selftest() -> None:
    check()
    image_path, _ = artifact_paths("ide")
    base = image_path.read_bytes()
    blob_len = struct.unpack_from("<H", base, 0)[0]
    md = 4 + blob_len
    fields = HEADER.unpack_from(base, md)
    entry_count, entries_off, nodes_off = fields[7], fields[11], fields[13]

    def first_entry_ref(data: bytearray) -> int:
        for index in range(fields[9]):
            at = md + nodes_off + index * NODE.size
            if data[at] == K_ENTRY_REF:
                return at
        raise ProbeError("selftest fixture lacks entry-ref")

    def anonymous_macro(data: bytearray) -> None:
        data[md + entries_off + 3] |= 1

    def ref_out_of_range(data: bytearray) -> None:
        struct.pack_into("<H", data, first_entry_ref(data) + 4, entry_count)

    def ref_to_macro(data: bytearray) -> None:
        for index in range(entry_count):
            at = md + entries_off + index * ENTRY.size
            if struct.unpack_from("<H", data, at)[0] != 0xFFFF:
                data[at + 3] |= 1
                struct.pack_into("<H", data, first_entry_ref(data) + 4, index)
                return
        raise ProbeError("selftest fixture lacks named entry")

    def duplicate_named(data: bytearray) -> None:
        named = []
        for index in range(entry_count):
            at = md + entries_off + index * ENTRY.size
            off = struct.unpack_from("<H", data, at)[0]
            if off != 0xFFFF:
                named.append(at)
        if len(named) < 2:
            raise ProbeError("selftest fixture lacks named entries")
        data[named[1] : named[1] + 2] = data[named[0] : named[0] + 2]

    mutations = []
    for name, mutate in (
        ("unknown-version", lambda b: b.__setitem__(md + 4, 3)),
        ("v1-sentinel", lambda b: b.__setitem__(md + 4, 1)),
        ("anonymous-macro", anonymous_macro),
        ("entry-ref-out-of-range", ref_out_of_range),
        ("entry-ref-to-macro", ref_to_macro),
        ("duplicate-named-entry", duplicate_named),
    ):
        changed = bytearray(base); mutate(changed)
        try:
            validate_v2(bytes(changed))
        except ProbeError:
            continue
        mutations.append(name)
    if mutations:
        raise ProbeError(f"selftest accepted mutations: {mutations}")
    print("directory-only-probe: SELFTEST PASS mutations=6")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check", "selftest"))
    args = parser.parse_args()
    try:
        {"generate": generate, "check": check, "selftest": selftest}[args.command]()
        return 0
    except (ProbeError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"directory-only-probe: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
