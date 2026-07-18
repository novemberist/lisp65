#!/usr/bin/env python3
"""Compile selected real lib/** stdlib functions to P0 bytecode and run them."""

import argparse
import glob
import hashlib
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_bundle as PB  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import m65d_blank_d81_oracle as M65D_D81  # noqa: E402


class StdlibCheckError(Exception):
    pass


K_FIX = 1
K_NIL = 2
K_T = 3
K_SYMBOL = 4
K_CONS = 5
K_LIST = 6
K_STRING = 7
K_ENTRY_REF = 8
CODE_LITTAB_OFFSET = 7
ARTIFACT_FORMAT_STDLIB = "lisp65-bytecode-p0-stdlib-artifacts-v1"
ARTIFACT_FORMAT_DISK_LIB = "lisp65-bytecode-p0-disk-lib-artifacts-v1"
SUITE_FORMAT_DISK_LIB = "lisp65-bytecode-p0-disk-lib-suite-v1"
ARTIFACT_FORMATS = {
    "stdlib": ARTIFACT_FORMAT_STDLIB,
    "disk-lib": ARTIFACT_FORMAT_DISK_LIB,
}
DEFAULT_MAX_CODE_OBJECT_BYTES = 255
SYMBOL_NAME_MAX_BYTES = 33
ENTRY_FLAG_MACRO = 1
OMISSION_RECORD_KEYS = {"name", "reason"}


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _default_paths():
    return sorted(glob.glob(os.path.join(_repo_root(), "tests", "bytecode", "stdlib", "*.json")))


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _suite_path(path, base_dir=None):
    if os.path.isabs(path):
        return path
    if base_dir:
        candidate = os.path.join(base_dir, path)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(_repo_root(), path)


def _append_unique(dst, src):
    out = list(dst)
    seen = set(json.dumps(item, sort_keys=True) if isinstance(item, dict) else item for item in out)
    for item in src:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
        if key not in seen:
            out.append(item)
            seen.add(key)
    return out


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _source_key(path):
    return os.path.normpath(path).replace(os.sep, "/")


def _merge_suite(base, child):
    merged = {key: value for key, value in base.items() if not key.startswith("_")}
    for key in ("sources", "functions", "cases", "tailcall_self"):
        merged[key] = _append_unique(base.get(key, []), child.get(key, []))
    for key, value in child.items():
        if key.startswith("_") or key in ("extends", "sources", "functions", "cases", "tailcall_self"):
            continue
        merged[key] = value
    return merged


def _source_defuns(source_paths):
    forms_by_name = {}
    names = []
    for path in source_paths:
        for form in C.parse_all(_read_source(path)):
            if isinstance(form, list) and len(form) >= 4 and form[0] == "defun":
                name = form[1]
                if isinstance(name, str):
                    if name not in forms_by_name:
                        names.append(name)
                    forms_by_name[name] = form
    return forms_by_name, names


def _source_top_defs(source_paths):
    forms_by_name = {}
    defun_names = []
    macro_names = []
    for path in source_paths:
        for form in C.parse_all(_read_source(path)):
            if (
                isinstance(form, list)
                and len(form) >= 4
                and form[0] in ("defun", "defmacro")
                and isinstance(form[1], str)
            ):
                name = form[1]
                if name not in forms_by_name:
                    if form[0] == "defmacro":
                        macro_names.append(name)
                    else:
                        defun_names.append(name)
                forms_by_name[name] = form
    return forms_by_name, defun_names, set(macro_names)


def _defun_names(source_paths):
    return _source_defuns(source_paths)[1]


def _apply_suite_transforms(suite):
    suite = dict(suite)

    sources = list(suite.get("sources", []))
    remove_sources = set(_source_key(path) for path in _as_list(suite.get("remove_sources")))
    if remove_sources:
        sources = [path for path in sources if _source_key(path) not in remove_sources]
    suite["sources"] = sources

    functions = list(suite.get("functions", []))
    for source_path in _as_list(suite.get("functions_from_sources")):
        functions = _append_unique(functions, _defun_names([source_path]))

    remove_functions = set(_as_list(suite.get("remove_functions")))
    for source_path in _as_list(suite.get("remove_functions_from_sources")):
        remove_functions.update(_defun_names([source_path]))
    if remove_functions:
        functions = [name for name in functions if name not in remove_functions]
    suite["functions"] = functions

    cases = list(suite.get("cases", []))
    remove_case_names = set(_as_list(suite.get("remove_cases")))
    remove_case_prefixes = tuple(_as_list(suite.get("remove_cases_prefixes")))
    if remove_case_names or remove_case_prefixes:
        filtered = []
        for case in cases:
            name = case.get("name", "")
            if name in remove_case_names:
                continue
            if any(name.startswith(prefix) for prefix in remove_case_prefixes):
                continue
            filtered.append(case)
        cases = filtered
    suite["cases"] = cases

    if "tailcall_self" in suite:
        function_set = set(functions)
        suite["tailcall_self"] = [
            name for name in suite.get("tailcall_self", []) if name in function_set
        ]

    return suite


def _read_suite(path, seen=None):
    path = _suite_path(path)
    if seen is None:
        seen = set()
    real = os.path.realpath(path)
    if real in seen:
        raise StdlibCheckError("cyclic suite extends: %s" % path)
    seen.add(real)
    suite = _read_json(path)
    base_dir = os.path.dirname(path)
    bases = suite.get("extends", [])
    if isinstance(bases, str):
        bases = [bases]
    merged = {}
    for base in bases:
        merged = _merge_suite(merged, _read_suite(_suite_path(base, base_dir), seen=seen))
    if bases:
        suite = _merge_suite(merged, suite)
    for case_ref in _as_list(suite.get("cases_from_suites")):
        case_suite = _read_suite(_suite_path(case_ref, base_dir), seen=seen)
        suite["cases"] = _append_unique(
            suite.get("cases", []), case_suite.get("cases", [])
        )
    suite = _apply_suite_transforms(suite)
    suite["_suite_path"] = path
    suite["_suite_dir"] = base_dir
    seen.remove(real)
    return suite


def _read_source(path):
    full = path if os.path.isabs(path) else os.path.join(_repo_root(), path)
    with open(full, "r", encoding="utf-8") as f:
        return f.read()


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _artifact_format(artifact_role):
    if artifact_role not in ARTIFACT_FORMATS:
        raise StdlibCheckError("bad artifact role: %s" % artifact_role)
    return ARTIFACT_FORMATS[artifact_role]


def _cstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _bytes_initializer(data, per_line=12):
    data = bytes(data)
    if not data:
        return ["    0"]
    lines = []
    for i in range(0, len(data), per_line):
        chunk = data[i : i + per_line]
        suffix = "," if i + per_line < len(data) else ""
        lines.append("    " + ", ".join("0x%02x" % b for b in chunk) + suffix)
    return lines


def _align2(data):
    if len(data) & 1:
        data += b"\x00"
    return data


def _symbol_name_bytes(name, role):
    if not isinstance(name, str) or not name or "\x00" in name:
        raise StdlibCheckError("%s must be a non-empty NUL-free string" % role)
    raw = name.encode("utf-8")
    if len(raw) > SYMBOL_NAME_MAX_BYTES:
        raise StdlibCheckError(
            "%s exceeds the %d-byte symbol-name contract: %r"
            % (role, SYMBOL_NAME_MAX_BYTES, name)
        )
    return raw


def _validate_ext_symbol_names(literal_pool, manifest_entries):
    """Reject L65M names that the canonical product interner cannot own."""

    for entry in manifest_entries:
        if not entry.get("anonymous", False):
            _symbol_name_bytes(entry.get("name"), "named L65M entry")
    for node in literal_pool.nodes:
        if int(node.get("kind", 0)) == K_SYMBOL:
            _symbol_name_bytes(node.get("name"), "L65M symbol literal")


def _build_ext_metadata(bundle, literal_pool, manifest_entries, literal_patches,
                        format_version=1):
    """Pack boot metadata into a pointer-free little-endian EXT blob trailer."""

    pool = literal_pool
    _validate_ext_symbol_names(pool, manifest_entries)
    strings = {}
    string_bytes = bytearray()

    def add_string(text):
        if text is None:
            return 0xFFFF
        if text not in strings:
            raw = text.encode("utf-8") + b"\x00"
            if len(string_bytes) + len(raw) > 0xFFFF:
                raise StdlibCheckError("EXT metadata string pool exceeds 64K")
            strings[text] = len(string_bytes)
            string_bytes.extend(raw)
        return strings[text]

    for entry in manifest_entries:
        if not entry.get("anonymous", False):
            add_string(entry["name"])
    for node in pool.nodes:
        add_string(node.get("name"))

    header_size = 38
    metadata = bytearray(b"\x00" * header_size)

    def append_section(payload):
        nonlocal metadata
        metadata = bytearray(_align2(bytes(metadata)))
        off = len(metadata)
        metadata.extend(payload)
        return off

    entry_bytes = bytearray()
    for entry in manifest_entries:
        ext_addr = int(entry["ext_addr"], 0)
        entry_bytes.extend(
            struct.pack(
                "<HBBHH",
                0xFFFF if entry.get("anonymous", False) else add_string(entry["name"]),
                (ext_addr >> 16) & 0xFF,
                int(entry.get("flags", 0)),
                ext_addr & 0xFFFF,
                int(entry["length"]),
            )
        )

    index_bytes = bytearray()
    for idx in pool.index:
        index_bytes.extend(struct.pack("<H", int(idx)))

    node_bytes = bytearray()
    for node in pool.nodes:
        node_bytes.extend(
            struct.pack(
                "<BBhHHH",
                int(node["kind"]),
                0,
                int(node["value"]),
                int(node["first"]),
                int(node["count"]),
                add_string(node.get("name")),
            )
        )

    patch_bytes = bytearray()
    for patch in literal_patches:
        patch_bytes.extend(
            struct.pack("<HH", int(patch["blob_offset"]), int(patch["node"]))
        )

    entries_off = append_section(entry_bytes)
    literal_index_off = append_section(index_bytes)
    literal_nodes_off = append_section(node_bytes)
    literal_patches_off = append_section(patch_bytes)
    strings_off = append_section(string_bytes)
    metadata = bytearray(_align2(bytes(metadata)))

    metadata_bytes = len(metadata)
    if metadata_bytes > 0xFFFF:
        raise StdlibCheckError("EXT metadata exceeds 64K")
    if len(bundle.blob) > 0xFFFF:
        raise StdlibCheckError("EXT metadata header only supports code blobs <= 64K")

    header = struct.pack(
        "<4sBBHIHHHHHHHHHHHHH",
        b"L65M",
        int(format_version),
        header_size,
        0,                       # flags
        int(bundle.base_addr),
        len(bundle.blob),
        metadata_bytes,
        len(manifest_entries),
        len(pool.index),
        len(pool.nodes),
        len(literal_patches),
        entries_off,
        literal_index_off,
        literal_nodes_off,
        literal_patches_off,
        strings_off,
        len(string_bytes),
        0,                       # reserved
    )
    if len(header) != header_size:
        raise StdlibCheckError("bad EXT metadata header size: %d" % len(header))
    metadata[:header_size] = header

    return bytes(metadata)


def _check_ext_metadata(metadata, bundle, literal_pool, manifest_entries,
                        literal_patches, format_version=1):
    header_fmt = "<4sBBHIHHHHHHHHHHHHH"
    header_size = struct.calcsize(header_fmt)
    if len(metadata) < header_size:
        raise StdlibCheckError("EXT metadata too short")
    (
        magic,
        version,
        encoded_header_size,
        flags,
        base_addr,
        code_bytes,
        metadata_bytes,
        entry_count,
        literal_index_count,
        literal_node_count,
        literal_patch_count,
        entries_off,
        literal_index_off,
        literal_nodes_off,
        literal_patches_off,
        strings_off,
        strings_bytes,
        reserved,
    ) = struct.unpack_from(header_fmt, metadata, 0)
    if magic != b"L65M" or version != format_version or encoded_header_size != header_size:
        raise StdlibCheckError("bad EXT metadata header")
    if flags != 0 or reserved != 0:
        raise StdlibCheckError("unexpected EXT metadata flags/reserved")
    if base_addr != bundle.base_addr or code_bytes != len(bundle.blob):
        raise StdlibCheckError("EXT metadata code header mismatch")
    if metadata_bytes != len(metadata):
        raise StdlibCheckError("EXT metadata byte count mismatch")
    if entry_count != len(manifest_entries):
        raise StdlibCheckError("EXT metadata entry count mismatch")
    if literal_index_count != len(literal_pool.index):
        raise StdlibCheckError("EXT metadata literal index count mismatch")
    if literal_node_count != len(literal_pool.nodes):
        raise StdlibCheckError("EXT metadata literal node count mismatch")
    if literal_patch_count != len(literal_patches):
        raise StdlibCheckError("EXT metadata literal patch count mismatch")

    sections = [
        (entries_off, entry_count * 8, "entries"),
        (literal_index_off, literal_index_count * 2, "literal_index"),
        (literal_nodes_off, literal_node_count * 10, "literal_nodes"),
        (literal_patches_off, literal_patch_count * 4, "literal_patches"),
        (strings_off, strings_bytes, "strings"),
    ]
    for off, size, name in sections:
        if off < header_size or off + size > len(metadata):
            raise StdlibCheckError("EXT metadata %s section out of range" % name)

    for ordinal, entry in enumerate(manifest_entries):
        name_off, _bank, entry_flags, _off, _length = struct.unpack_from(
            "<HBBHH", metadata, entries_off + ordinal * 8
        )
        anonymous = bool(entry.get("anonymous", False))
        if anonymous != (name_off == 0xFFFF):
            raise StdlibCheckError("EXT metadata anonymous entry mismatch")
        if anonymous and (format_version != 2 or entry_flags & ENTRY_FLAG_MACRO):
            raise StdlibCheckError("EXT metadata anonymous entry is invalid")
    for ordinal, node in enumerate(literal_pool.nodes):
        kind, reserved, value, first, count, name_off = struct.unpack_from(
            "<BBhHHH", metadata, literal_nodes_off + ordinal * 10
        )
        if kind == K_ENTRY_REF:
            if (format_version != 2 or reserved or value or count
                    or name_off != 0xFFFF or first >= len(manifest_entries)
                    or manifest_entries[first].get("flags", 0) & ENTRY_FLAG_MACRO):
                raise StdlibCheckError("EXT metadata entry-ref is invalid")


def _directory_only_transform(suite, bundle, pool, manifest_entries):
    prefixes = suite.get("directory_only_prefixes", [])
    if prefixes is None:
        prefixes = []
    if (not isinstance(prefixes, list)
            or not all(isinstance(item, str) and item for item in prefixes)):
        raise StdlibCheckError("directory_only_prefixes must be non-empty strings")
    if not prefixes:
        return 1, []
    if suite.get("abi_profile") != "dialect-v2":
        raise StdlibCheckError("Directory-only entries require dialect-v2")
    candidates = {
        entry["name"]: ordinal
        for ordinal, entry in enumerate(manifest_entries)
        if any(entry["name"].startswith(prefix) for prefix in prefixes)
    }
    if not candidates:
        raise StdlibCheckError("Directory-only profile selected no entries")
    entry_names = {entry["name"] for entry in manifest_entries}
    exports = _as_list(suite.get("exports"))
    override_exports = _as_list(suite.get("override_exports"))
    late_bound_exports = _as_list(suite.get("late_bound_exports"))
    for label, names in (
        ("exports", exports),
        ("override_exports", override_exports),
        ("late_bound_exports", late_bound_exports),
    ):
        if (not all(isinstance(name, str) and name for name in names)
                or len(names) != len(set(names))):
            raise StdlibCheckError("%s must contain unique non-empty names" % label)
        unknown = sorted(set(names) - entry_names)
        if unknown:
            raise StdlibCheckError("%s names are not artifact entries: %s"
                                   % (label, ", ".join(unknown)))
    if not set(override_exports) <= set(exports):
        raise StdlibCheckError("override_exports must be a subset of exports")
    if not set(late_bound_exports) <= set(exports):
        raise StdlibCheckError("late_bound_exports must be a subset of exports")
    if not set(override_exports) <= set(late_bound_exports):
        raise StdlibCheckError("override_exports must be late-bound")

    # Publication and local binding are separate contracts.  An exported entry
    # must retain its name so another container can resolve it.  A named export
    # may still use cheap local entry refs; only an explicitly late-bound export
    # must keep symbolic call/designator nodes so a later library can replace
    # its function cell.
    anonymous_candidates = set(candidates) - set(exports)
    ordinal_candidates = set(candidates) - set(late_bound_exports)
    for entry in manifest_entries:
        entry["anonymous"] = entry["name"] in anonymous_candidates
        if entry["anonymous"] and entry.get("flags", 0) & ENTRY_FLAG_MACRO:
            raise StdlibCheckError("macro entries cannot be Directory-only")
    refs = []
    for entry in manifest_entries:
        first = int(entry["lit_first"])
        for slot, literal in enumerate(entry["literals"]):
            if (not isinstance(literal, dict)
                    or literal.get("symbol") not in ordinal_candidates):
                continue
            node_index = pool.index[first + slot]
            node = pool.nodes[node_index]
            if node.get("kind") != K_SYMBOL or node.get("name") != literal["symbol"]:
                raise StdlibCheckError("Directory-only literal/node parity drift")
            node.update(
                kind=K_ENTRY_REF, value=0, first=candidates[literal["symbol"]],
                count=0, name=None,
            )
            refs.append({
                "caller": entry["name"], "literal_slot": slot,
                "target": literal["symbol"], "target_ordinal": candidates[literal["symbol"]],
                "node": node_index,
            })
    remaining = sorted({
        node.get("name") for node in pool.nodes
        if node.get("kind") == K_SYMBOL and node.get("name") in ordinal_candidates
    })
    if remaining:
        raise StdlibCheckError("Directory-only symbols remain materialized: %s" % remaining)
    anonymous_exports = sorted(
        entry["name"] for entry in manifest_entries
        if entry.get("anonymous") and entry["name"] in set(exports)
    )
    if anonymous_exports:
        raise StdlibCheckError("exports were emitted anonymous: %s"
                               % ", ".join(anonymous_exports))
    late_bound_refs = sorted(
        "%s->%s" % (item["caller"], item["target"])
        for item in refs if item["target"] in set(late_bound_exports)
    )
    if late_bound_refs:
        raise StdlibCheckError("late-bound exports became entry refs: %s"
                               % ", ".join(late_bound_refs))
    return 2, refs


def _directory_only_selftest():
    class Pool:
        def __init__(self):
            self.index = [0, 1]
            self.nodes = [
                {"kind": K_SYMBOL, "name": "%hook"},
                {"kind": K_SYMBOL, "name": "%helper"},
            ]

    def inputs(overrides=None):
        suite = {
            "abi_profile": "dialect-v2",
            "directory_only_prefixes": ["%"],
            "exports": ["%hook"],
            "late_bound_exports": ["%hook"],
            "override_exports": ["%hook"],
        }
        if overrides:
            suite.update(overrides)
        entries = [
            {"name": "%hook", "flags": 0, "lit_first": 0, "literals": []},
            {"name": "%helper", "flags": 0, "lit_first": 0, "literals": []},
            {"name": "caller", "flags": 0, "lit_first": 0,
             "literals": [{"symbol": "%hook"}, {"symbol": "%helper"}]},
        ]
        return suite, Pool(), entries

    suite, pool, entries = inputs()
    version, refs = _directory_only_transform(suite, None, pool, entries)
    if (
        version != 2
        or entries[0].get("anonymous")
        or not entries[1].get("anonymous")
        or pool.nodes[0] != {"kind": K_SYMBOL, "name": "%hook"}
        or pool.nodes[1].get("kind") != K_ENTRY_REF
        or [ref["target"] for ref in refs] != ["%helper"]
    ):
        raise StdlibCheckError("Directory-only publication/late-binding split drift")

    bad_cases = (
        {"exports": ["%missing"]},
        {"exports": ["%hook", "%hook"]},
        {"late_bound_exports": ["%helper"]},
        {"late_bound_exports": []},
        {"override_exports": ["%helper"]},
    )
    for mutation in bad_cases:
        suite, pool, entries = inputs(mutation)
        try:
            _directory_only_transform(suite, None, pool, entries)
        except StdlibCheckError:
            pass
        else:
            raise StdlibCheckError(
                "Directory-only contract mutation was accepted: %s" % mutation
            )

    class NamePool:
        def __init__(self, nodes):
            self.nodes = nodes

    boundary = "s" * SYMBOL_NAME_MAX_BYTES
    _validate_ext_symbol_names(
        NamePool([
            {"kind": K_SYMBOL, "name": boundary},
            {"kind": K_STRING, "name": "x" * (SYMBOL_NAME_MAX_BYTES + 40)},
        ]),
        [
            {"name": boundary, "anonymous": False},
            {"name": "host-only-" + ("x" * 40), "anonymous": True},
        ],
    )
    for label, pool, named_entries in (
        (
            "entry",
            NamePool([]),
            [{"name": boundary + "x", "anonymous": False}],
        ),
        (
            "symbol",
            NamePool([{"kind": K_SYMBOL, "name": boundary + "x"}]),
            [],
        ),
    ):
        try:
            _validate_ext_symbol_names(pool, named_entries)
        except StdlibCheckError:
            pass
        else:
            raise StdlibCheckError(
                "%s longer than the symbol-name contract was accepted" % label
            )
    print("bytecode-p0-directory-only selftest: PASS cases=9 symbol-name-max=33")
    return 0


def _entry_definition_source(name, sources, resident_overrides,
                             definition_source_overrides=None):
    pattern = re.compile(r"\(def(?:un|macro)\s+" + re.escape(name) + r"(?=[\s()])")
    matches = []
    for source in sources:
        try:
            with open(source, "r", encoding="utf-8") as stream:
                text = stream.read()
        except OSError as exc:
            raise StdlibCheckError("cannot read Directory-only source %s: %s" % (source, exc))
        if pattern.search(text):
            matches.append(source)
    if len(matches) == 1:
        return matches[0]
    selected = dict(definition_source_overrides or {}).get(name)
    if selected in matches:
        return selected
    if name in set(resident_overrides) and matches:
        return matches[-1]
    raise StdlibCheckError("%s: Directory-only source mapping is ambiguous: %r" % (name, matches))


def _sha256(data):
    return hashlib.sha256(bytes(data)).hexdigest()


def _text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _collect_defuns(source_paths):
    return _source_defuns(source_paths)[0]


def _collect_top_defs(source_paths):
    forms_by_name, _defuns, macro_names = _source_top_defs(source_paths)
    return forms_by_name, macro_names


def _entry_name(case_name):
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", case_name).strip("_").lower()
    return "__p0_stdlib_%s" % (safe or "case")


def _align8(n):
    return (n + 7) & ~7


def _case_object_names(entry_names, code_by_name):
    out = set(entry_names)
    for entry in entry_names:
        prefix = entry + "-h"
        out.update(name for name in code_by_name if name.startswith(prefix))
    return out


def _suite_embed_names(names, entry_names, code_by_name):
    case_names = _case_object_names(entry_names, code_by_name)
    return [name for name in names if name not in case_names]


def _macro_symbol_objs(heap, *flag_maps):
    out = set()
    for flag_map in flag_maps:
        for name, flags in flag_map.items():
            if flags & ENTRY_FLAG_MACRO:
                out.add(heap.intern(name))
    return out


class _PrivateInliner:
    def __init__(self, names, functions, forms_by_name, macro_names, label):
        self.names = tuple(names)
        self.removed_names = self.names
        self.name_set = set(self.names)
        self.forms_by_name = forms_by_name
        self.expansions = {name: 0 for name in self.names}
        if len(self.name_set) != len(self.names):
            raise StdlibCheckError("%s duplicate private_inline_functions" % label)
        bad_names = sorted(
            name
            for name in self.names
            if not isinstance(name, str) or not name.startswith("%")
        )
        if bad_names:
            raise StdlibCheckError(
                "%s private inline names must start with %%: %s"
                % (label, ", ".join(str(name) for name in bad_names))
            )
        unknown = sorted(self.name_set - set(functions))
        if unknown:
            raise StdlibCheckError(
                "%s private inline names are not suite functions: %s"
                % (label, ", ".join(unknown))
            )
        macro_private = sorted(self.name_set & set(macro_names))
        if macro_private:
            raise StdlibCheckError(
                "%s private inline names are macros: %s"
                % (label, ", ".join(macro_private))
            )

        self.specs = {}
        graph = {}
        for name in self.names:
            form = forms_by_name.get(name)
            if not isinstance(form, list) or len(form) < 4 or form[0] != "defun":
                raise StdlibCheckError("%s private inline form is not a defun: %s" % (label, name))
            params, optional_count, rest_param, optional_marker = C._params(form[2])
            if rest_param is not None or optional_marker or optional_count:
                raise StdlibCheckError(
                    "%s private inline optional/rest parameters are unsupported: %s"
                    % (label, name)
                )
            self.specs[name] = (list(params), list(form[3:]))
            graph[name] = set()
            for body_form in form[3:]:
                graph[name].update(self._direct_private_calls(body_form))
            noncall_refs = sorted(
                self._body_noncall_private_refs(form[3:], bound=set(params))
            )
            if noncall_refs:
                raise StdlibCheckError(
                    "%s private inline body uses private functions as data: %s"
                    % (label, ", ".join(noncall_refs))
                )
        self._reject_cycles(graph, label)

    def _direct_private_calls(self, form):
        calls = set()
        if isinstance(form, C.DottedList):
            for item in form.items:
                calls.update(self._direct_private_calls(item))
            calls.update(self._direct_private_calls(form.tail))
            return calls
        if not isinstance(form, list) or not form:
            return calls
        op = form[0]
        if op in ("quote", "quasiquote"):
            return calls
        if isinstance(op, str) and op in self.name_set:
            calls.add(op)
        if op == "function":
            if (
                len(form) == 2
                and isinstance(form[1], list)
                and form[1]
                and form[1][0] == "lambda"
            ):
                return self._direct_private_calls(form[1])
            return calls
        if op == "lambda" and len(form) >= 3:
            for item in form[2:]:
                calls.update(self._direct_private_calls(item))
            return calls
        if isinstance(op, list) and op and op[0] == "lambda":
            calls.update(self._direct_private_calls(op))
            for item in form[1:]:
                calls.update(self._direct_private_calls(item))
            return calls
        if op in ("let", "let*") and len(form) >= 3 and isinstance(form[1], list):
            for binding in form[1]:
                if isinstance(binding, list) and len(binding) == 2:
                    calls.update(self._direct_private_calls(binding[1]))
            for item in form[2:]:
                calls.update(self._direct_private_calls(item))
            return calls
        if op == "setq":
            for item in form[2::2]:
                calls.update(self._direct_private_calls(item))
            return calls
        if op in ("dotimes", "dolist") and len(form) >= 2:
            spec = form[1]
            if isinstance(spec, list):
                for item in spec[1:]:
                    calls.update(self._direct_private_calls(item))
            for item in form[2:]:
                calls.update(self._direct_private_calls(item))
            return calls
        if op == "case" and len(form) >= 2:
            calls.update(self._direct_private_calls(form[1]))
            for clause in form[2:]:
                if isinstance(clause, list):
                    for item in clause[1:]:
                        calls.update(self._direct_private_calls(item))
            return calls
        for item in form[1:]:
            calls.update(self._direct_private_calls(item))
        return calls

    @staticmethod
    def _reject_cycles(graph, label):
        active = set()
        done = set()

        def visit(name, path):
            if name in active:
                cycle = path[path.index(name) :] + [name]
                raise StdlibCheckError(
                    "%s private inline recursion: %s" % (label, " -> ".join(cycle))
                )
            if name in done:
                return
            active.add(name)
            for target in sorted(graph[name]):
                visit(target, path + [target])
            active.remove(name)
            done.add(name)

        for name in sorted(graph):
            visit(name, [name])

    def expand_expr(self, form):
        if isinstance(form, C.DottedList):
            return C.DottedList(
                tuple(self.expand_expr(item) for item in form.items),
                self.expand_expr(form.tail),
            )
        if not isinstance(form, list) or not form:
            return form
        op = form[0]
        if op in ("quote", "quasiquote"):
            return form
        if (
            op == "function"
            and len(form) == 2
            and isinstance(form[1], str)
            and form[1] in self.name_set
        ):
            raise StdlibCheckError(
                "private inline function used as a value: %s" % form[1]
            )
        if isinstance(op, str) and op in self.name_set:
            params, body = self.specs[op]
            call_args = [self.expand_expr(arg) for arg in form[1:]]
            if len(call_args) != len(params):
                raise StdlibCheckError(
                    "private inline arity mismatch for %s: %d != %d"
                    % (op, len(call_args), len(params))
                )
            self.expansions[op] += 1
            expanded_body = [self.expand_expr(item) for item in body]
            return [C.PRIVATE_INLINE_OP, params, expanded_body, call_args]
        if op is C.PRIVATE_INLINE_OP and len(form) == 4:
            return [
                op,
                form[1],
                [self.expand_expr(item) for item in form[2]],
                [self.expand_expr(item) for item in form[3]],
            ]
        if op == "lambda" and len(form) >= 3:
            return [op, form[1]] + [self.expand_expr(item) for item in form[2:]]
        if isinstance(op, list) and op and op[0] == "lambda":
            return [self.expand_expr(op)] + [self.expand_expr(item) for item in form[1:]]
        if op in ("let", "let*") and len(form) >= 3:
            bindings = []
            for binding in form[1]:
                if isinstance(binding, str):
                    bindings.append(binding)
                elif isinstance(binding, list) and len(binding) == 2:
                    bindings.append([binding[0], self.expand_expr(binding[1])])
                else:
                    bindings.append(binding)
            return [op, bindings] + [self.expand_expr(item) for item in form[2:]]
        if op == "setq":
            out = [op]
            for index, item in enumerate(form[1:]):
                out.append(item if index % 2 == 0 else self.expand_expr(item))
            return out
        if op in ("dotimes", "dolist") and len(form) >= 2:
            spec = form[1]
            if isinstance(spec, list) and 2 <= len(spec) <= 3:
                expanded_spec = [spec[0], self.expand_expr(spec[1])]
                if len(spec) == 3:
                    expanded_spec.append(self.expand_expr(spec[2]))
            else:
                expanded_spec = spec
            return [op, expanded_spec] + [self.expand_expr(item) for item in form[2:]]
        if op == "cond":
            return [op] + [
                [self.expand_expr(item) for item in clause]
                if isinstance(clause, list)
                else clause
                for clause in form[1:]
            ]
        if op == "case" and len(form) >= 2:
            clauses = []
            for clause in form[2:]:
                if isinstance(clause, list) and clause:
                    clauses.append(
                        [clause[0]] + [self.expand_expr(item) for item in clause[1:]]
                    )
                else:
                    clauses.append(clause)
            return [op, self.expand_expr(form[1])] + clauses
        if op == "function" and len(form) == 2 and isinstance(form[1], list):
            return [op, self.expand_expr(form[1])]
        return [op] + [self.expand_expr(item) for item in form[1:]]

    def expand_defun(self, form):
        params, _optional_count, rest_param, _optional_marker = C._params(form[2])
        bound = set(params)
        if rest_param is not None:
            bound.add(rest_param)
        noncall_refs = sorted(self._body_noncall_private_refs(form[3:], bound=bound))
        if noncall_refs:
            raise StdlibCheckError(
                "private inline functions used as data: %s"
                % ", ".join(noncall_refs)
            )
        return list(form[:3]) + [self.expand_expr(item) for item in form[3:]]

    def _body_noncall_private_refs(self, body, bound=None):
        refs = set()
        bound = set(bound or ())
        for item in body:
            refs.update(self._noncall_private_refs(item, bound=bound))
        return refs

    def _noncall_private_refs(self, form, bound=None):
        refs = set()
        bound = set(bound or ())
        if isinstance(form, str):
            if form in self.name_set and form not in bound:
                refs.add(form)
            return refs
        if isinstance(form, C.DottedList):
            for item in form.items:
                refs.update(self._noncall_private_refs(item, bound=bound))
            refs.update(self._noncall_private_refs(form.tail, bound=bound))
            return refs
        if not isinstance(form, list) or not form:
            return refs
        op = form[0]
        if (
            op == "function"
            and len(form) == 2
            and isinstance(form[1], list)
            and form[1]
            and form[1][0] == "lambda"
        ):
            return self._noncall_private_refs(form[1], bound=bound)
        if op in ("quote", "quasiquote", "function"):
            stack = list(form[1:])
            while stack:
                item = stack.pop()
                if isinstance(item, str) and item in self.name_set:
                    refs.add(item)
                elif isinstance(item, list):
                    stack.extend(item)
                elif isinstance(item, C.DottedList):
                    stack.extend(item.items)
                    stack.append(item.tail)
            return refs
        if op is C.PRIVATE_INLINE_OP and len(form) == 4:
            refs.update(self._body_noncall_private_refs(form[2], bound=set(form[1])))
            refs.update(self._body_noncall_private_refs(form[3], bound=bound))
            return refs
        if op == "lambda" and len(form) >= 3:
            params, _optional_count, rest_param, _optional_marker = C._params(form[1])
            lambda_bound = bound | set(params)
            if rest_param is not None:
                lambda_bound.add(rest_param)
            return self._body_noncall_private_refs(form[2:], bound=lambda_bound)
        if isinstance(op, list) and op and op[0] == "lambda":
            refs.update(self._noncall_private_refs(op, bound=bound))
            refs.update(self._body_noncall_private_refs(form[1:], bound=bound))
            return refs
        if op in ("let", "let*") and len(form) >= 3 and isinstance(form[1], list):
            body_bound = set(bound)
            for binding in form[1]:
                if isinstance(binding, list) and len(binding) == 2:
                    init_bound = body_bound if op == "let*" else bound
                    refs.update(self._noncall_private_refs(binding[1], bound=init_bound))
                    if isinstance(binding[0], str):
                        body_bound.add(binding[0])
                elif isinstance(binding, str):
                    body_bound.add(binding)
            refs.update(self._body_noncall_private_refs(form[2:], bound=body_bound))
            return refs
        if op == "setq":
            for item in form[2::2]:
                refs.update(self._noncall_private_refs(item, bound=bound))
            return refs
        if op in ("dotimes", "dolist") and len(form) >= 2:
            spec = form[1]
            if isinstance(spec, list):
                if len(spec) >= 2:
                    refs.update(self._noncall_private_refs(spec[1], bound=bound))
                loop_bound = bound | ({spec[0]} if spec and isinstance(spec[0], str) else set())
                if len(spec) >= 3:
                    refs.update(self._noncall_private_refs(spec[2], bound=loop_bound))
            else:
                loop_bound = bound
            refs.update(self._body_noncall_private_refs(form[2:], bound=loop_bound))
            return refs
        if op == "cond":
            for clause in form[1:]:
                if isinstance(clause, list):
                    refs.update(self._body_noncall_private_refs(clause, bound=bound))
            return refs
        if op == "case" and len(form) >= 2:
            refs.update(self._noncall_private_refs(form[1], bound=bound))
            for clause in form[2:]:
                if isinstance(clause, list):
                    refs.update(self._body_noncall_private_refs(clause[1:], bound=bound))
            return refs
        for item in form[1:]:
            refs.update(self._noncall_private_refs(item, bound=bound))
        return refs


class _CompositeInliner:
    def __init__(self, target, resident=None):
        self.target = target
        self.resident = resident
        overlap = target.name_set & (set() if resident is None else resident.name_set)
        if overlap:
            raise StdlibCheckError(
                "target and resident private inline sets overlap: %s"
                % ", ".join(sorted(overlap))
            )
        self.removed_names = target.removed_names
        self.names = target.names + (() if resident is None else resident.names)
        self.name_set = set(self.names)

    @property
    def expansions(self):
        out = dict(self.target.expansions)
        if self.resident is not None:
            out.update(self.resident.expansions)
        return out

    def expand_expr(self, form):
        expanded = self.target.expand_expr(form)
        if self.resident is not None:
            expanded = self.resident.expand_expr(expanded)
        return expanded


def _private_inline_selftest():
    private_form = ["defun", "%private-test", ["value"], ["tail-target", "value"]]
    forms = {"%private-test": private_form}
    inliner = _PrivateInliner(
        ["%private-test"], ["%private-test"], forms, set(), "selftest"
    )
    expanded = inliner.expand_defun(
        [
            "defun",
            "private-test-run",
            [],
            ["let", [["%private-test", 7]], ["%private-test", "%private-test"]],
        ]
    )
    binding = expanded[3][1][0]
    assert binding == ["%private-test", 7]
    assert expanded[3][2][0] is C.PRIVATE_INLINE_OP

    heap = C.prepare_heap(["private-test-run", "tail-target"])
    _name, code, helpers = C.compile_top_form_with_helpers(expanded, heap)
    assert helpers == []
    assert ("TAILCALL", "tail-target", 1) in _call_edges(heap, code)

    try:
        inliner.expand_defun(
            [
                "defun",
                "private-test-indirect",
                [],
                ["funcall", ["quote", "%private-test"], 1],
            ]
        )
    except StdlibCheckError as exc:
        assert "used as data" in str(exc)
    else:
        raise AssertionError("indirect private function reference was accepted")

    _PrivateInliner(
        ["%private-shadow"],
        ["%private-shadow"],
        {
            "%private-shadow": [
                "defun",
                "%private-shadow",
                [],
                ["let", [["%private-shadow", 7]], ["tail-target", "%private-shadow"]],
            ]
        },
        set(),
        "selftest-shadow",
    )

    cycle_forms = {
        "%private-a": ["defun", "%private-a", [], ["%private-b"]],
        "%private-b": ["defun", "%private-b", [], ["%private-a"]],
    }
    try:
        _PrivateInliner(
            ["%private-a", "%private-b"],
            ["%private-a", "%private-b"],
            cycle_forms,
            set(),
            "selftest-cycle",
        )
    except StdlibCheckError as exc:
        assert "recursion" in str(exc)
    else:
        raise AssertionError("private inline cycle was accepted")

    print("bytecode-p0-private-inline selftest: PASS cases=5")
    return 0


def _validated_omission_records(
    raw_records,
    *,
    key,
    required,
    definition_names,
    other_definition_names,
    configured_names,
    label,
):
    records = _as_list(raw_records)
    if records and not required:
        raise StdlibCheckError("%s %s requires its require_all gate" % (label, key))
    if not required:
        return []

    definitions = set(definition_names)
    other_definitions = set(other_definition_names)
    configured = set(configured_names)
    normalized = []
    seen = set()
    for index, record in enumerate(records):
        item_label = "%s %s[%d]" % (label, key, index)
        if not isinstance(record, dict):
            raise StdlibCheckError("%s must be a {name, reason} object" % item_label)
        keys = set(record)
        if keys != OMISSION_RECORD_KEYS:
            missing = sorted(OMISSION_RECORD_KEYS - keys)
            extra = sorted(keys - OMISSION_RECORD_KEYS)
            details = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if extra:
                details.append("extra=" + ",".join(extra))
            raise StdlibCheckError("%s has invalid keys (%s)" % (item_label, "; ".join(details)))
        name = record["name"]
        reason = record["reason"]
        if not isinstance(name, str) or not name.strip():
            raise StdlibCheckError("%s name must be a non-empty string" % item_label)
        if not isinstance(reason, str) or not reason.strip():
            raise StdlibCheckError("%s reason must be a non-empty string" % item_label)
        if name in seen:
            raise StdlibCheckError("%s duplicate omission: %s" % (label, name))
        seen.add(name)
        if name not in definitions:
            if name in other_definitions:
                raise StdlibCheckError("%s wrong definition class: %s" % (label, name))
            raise StdlibCheckError("%s unknown omission: %s" % (label, name))
        normalized.append({"name": name, "reason": reason.strip()})

    actual = definitions - configured
    declared = set(record["name"] for record in normalized)
    stale = sorted(declared - actual)
    if stale:
        raise StdlibCheckError(
            "%s stale or included %s: %s" % (label, key, ", ".join(stale))
        )
    missing = sorted(actual - declared)
    if missing:
        raise StdlibCheckError("%s undeclared %s: %s" % (label, key, ", ".join(missing)))
    return normalized


def _validate_suite_omissions(suite, configured_functions=None):
    label = suite.get("name") or suite.get("_suite_path") or "suite"
    configured = list(configured_functions or suite.get("functions", []))
    _forms, defun_names, macro_names = _source_top_defs(suite.get("sources", []))
    defuns = _validated_omission_records(
        suite.get("allow_omitted_defuns"),
        key="allow_omitted_defuns",
        required=bool(suite.get("require_all_defuns")),
        definition_names=defun_names,
        other_definition_names=macro_names,
        configured_names=configured,
        label=label,
    )
    defmacros = _validated_omission_records(
        suite.get("allow_omitted_defmacros"),
        key="allow_omitted_defmacros",
        required=bool(suite.get("require_all_defmacros")),
        definition_names=macro_names,
        other_definition_names=defun_names,
        configured_names=configured,
        label=label,
    )
    return {
        "defuns": defuns,
        "defmacros": defmacros,
        "defun_count": len(defuns),
        "defmacro_count": len(defmacros),
    }


def _omission_contract_selftest():
    def check(raw, **overrides):
        args = {
            "key": "allow_omitted_defuns",
            "required": True,
            "definition_names": {"kept", "omitted", "%private"},
            "other_definition_names": {"macro-only"},
            "configured_names": {"kept", "%private"},
            "label": "selftest",
        }
        args.update(overrides)
        return _validated_omission_records(raw, **args)

    good = check([{"name": "omitted", "reason": "profile boundary"}])
    assert good == [{"name": "omitted", "reason": "profile boundary"}]

    bad_cases = [
        (["omitted"], {}, "must be a {name, reason} object"),
        ([{"name": "omitted"}], {}, "invalid keys"),
        ([{"name": "omitted", "reason": ""}], {}, "reason must be"),
        (
            [
                {"name": "omitted", "reason": "one"},
                {"name": "omitted", "reason": "two"},
            ],
            {},
            "duplicate omission",
        ),
        ([{"name": "unknown", "reason": "x"}], {}, "unknown omission"),
        ([{"name": "macro-only", "reason": "x"}], {}, "wrong definition class"),
        ([{"name": "kept", "reason": "x"}], {}, "stale or included"),
        ([{"name": "%private", "reason": "x"}], {}, "stale or included"),
        ([], {}, "undeclared allow_omitted_defuns"),
        (
            [{"name": "omitted", "reason": "x"}],
            {"required": False},
            "requires its require_all gate",
        ),
    ]
    for raw, overrides, expected in bad_cases:
        try:
            check(raw, **overrides)
        except StdlibCheckError as exc:
            assert expected in str(exc), (expected, str(exc))
        else:
            raise AssertionError("omission contract accepted negative case: %s" % expected)

    macro = check(
        [{"name": "macro-only", "reason": "profile boundary"}],
        key="allow_omitted_defmacros",
        definition_names={"macro-only"},
        other_definition_names={"kept"},
        configured_names=set(),
    )
    assert macro[0]["name"] == "macro-only"
    print("bytecode-p0-omission-contract selftest: PASS cases=12")
    return 0


def _omission_contract_audit():
    patterns = (
        "tests/bytecode/stdlib/*.json",
        "tests/bytecode/libs/*.json",
        "tests/bytecode/runtime/*.json",
        "tests/bytecode/demos/*.json",
    )
    paths = []
    for pattern in patterns:
        paths.extend(glob.glob(os.path.join(_repo_root(), pattern)))
    checked = 0
    for path in sorted(set(paths)):
        suite = _read_suite(path)
        if not any(
            suite.get(key)
            for key in (
                "require_all_defuns",
                "require_all_defmacros",
                "allow_omitted_defuns",
                "allow_omitted_defmacros",
            )
        ):
            continue
        _validate_suite_omissions(suite)
        checked += 1
    print("bytecode-p0-omission-contract audit: PASS suites=%d" % checked)
    return 0


def _resident_private_inliner(suite):
    selected = _as_list(suite.get("resident_private_inline_functions"))
    if not selected:
        return None
    configured = []
    forms_by_name = {}
    macro_names = set()
    declared = set()
    for resident in _resident_suites(suite):
        configured = _append_unique(configured, resident.get("functions", []))
        resident_forms, resident_macros = _collect_top_defs(resident.get("sources", []))
        forms_by_name.update(resident_forms)
        macro_names.update(resident_macros)
        declared.update(_as_list(resident.get("private_inline_functions")))
    undeclared = sorted(set(selected) - declared)
    if undeclared:
        raise StdlibCheckError(
            "resident private inline names are not declared private: %s"
            % ", ".join(undeclared)
        )
    return _PrivateInliner(
        selected,
        configured,
        forms_by_name,
        macro_names,
        "%s resident-private" % (suite.get("name") or "suite"),
    )


def _suite_functions_and_forms(suite):
    configured_functions = list(suite.get("functions", []))
    if not configured_functions:
        raise StdlibCheckError("suite has no functions")

    forms_by_name, macro_names = _collect_top_defs(suite.get("sources", []))
    missing = [name for name in configured_functions if name not in forms_by_name]
    if missing:
        raise StdlibCheckError("missing defuns/defmacros: %s" % ", ".join(missing))
    _validate_suite_omissions(suite, configured_functions)
    private_names = _as_list(suite.get("private_inline_functions"))
    target_inliner = _PrivateInliner(
        private_names,
        configured_functions,
        forms_by_name,
        macro_names,
        suite.get("name") or suite.get("_suite_path") or "suite",
    )
    resident_inliner = _resident_private_inliner(suite)
    inliner = _CompositeInliner(target_inliner, resident_inliner)
    functions = [name for name in configured_functions if name not in target_inliner.name_set]
    forms_by_name = dict(forms_by_name)
    for name in functions:
        form = target_inliner.expand_defun(forms_by_name[name])
        if resident_inliner is not None:
            form = list(form[:3]) + [
                resident_inliner.expand_expr(item) for item in form[3:]
            ]
        forms_by_name[name] = form
    return functions, forms_by_name, macro_names, inliner


def _resident_suite_refs(suite):
    refs = []
    refs.extend(_as_list(suite.get("resident_suite")))
    refs.extend(_as_list(suite.get("resident_suites")))
    return refs


def _resident_suites(suite, seen=None):
    if seen is None:
        seen = set()
    out = []
    for ref in _resident_suite_refs(suite):
        path = _suite_path(ref, suite.get("_suite_dir"))
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        resident = _read_suite(path)
        out.extend(_resident_suites(resident, seen=seen))
        out.append(resident)
    return out


def _compile_function_objects(
    functions, forms_by_name, heap, macro_names=None, existing_names=None, label="suite",
    strict_arity=False, abi_profile=None,
):
    names = []
    code_by_name = {}
    entry_flags_by_name = {}
    macro_names = set(macro_names or [])
    seen = set(existing_names or [])
    for name in functions:
        if name in seen:
            raise StdlibCheckError("%s duplicate code object: %s" % (label, name))
        form = forms_by_name[name]
        if name in macro_names:
            form = ["defun", name, form[2]] + form[3:]
        compiled_name, code, helpers = C.compile_top_form_with_helpers(
            form, heap, strict_arity=strict_arity, abi_profile=abi_profile
        )
        if compiled_name != name:
            raise StdlibCheckError("compiled name mismatch for %s" % name)
        names.append(name)
        code_by_name[name] = code
        entry_flags_by_name[name] = ENTRY_FLAG_MACRO if name in macro_names else 0
        seen.add(name)
        for helper_name, helper_code in helpers:
            if helper_name in seen:
                raise StdlibCheckError("%s duplicate helper code object: %s" % (label, helper_name))
            names.append(helper_name)
            code_by_name[helper_name] = helper_code
            entry_flags_by_name[helper_name] = 0
            seen.add(helper_name)
    return names, code_by_name, entry_flags_by_name


def _compile_resident_code(suite, heap):
    resident_names = []
    resident_code_by_name = {}
    resident_entry_flags = {}
    for resident in _resident_suites(suite):
        functions, forms_by_name, macro_names, _inliner = _suite_functions_and_forms(resident)
        names, code_by_name, entry_flags = _compile_function_objects(
            functions,
            forms_by_name,
            heap,
            macro_names=macro_names,
            existing_names=set(resident_code_by_name),
            label="resident suite",
            strict_arity=bool(resident.get("strict_arity", False)),
            abi_profile=resident.get("abi_profile"),
        )
        resident_names.extend(names)
        resident_code_by_name.update(code_by_name)
        resident_entry_flags.update(entry_flags)
    return resident_names, resident_code_by_name, resident_entry_flags


def _expand_case_expr(suite, target_inliner, expr):
    expanded = target_inliner.expand_expr(expr)
    # A sequential disk-lib suite compiles its cases against already loaded
    # resident suites.  Their private helpers must therefore be available to
    # test expressions without becoming runtime directory entries.
    for resident in reversed(_resident_suites(suite)):
        _functions, _forms, _macros, resident_inliner = _suite_functions_and_forms(
            resident
        )
        expanded = resident_inliner.expand_expr(expanded)
    return expanded


def _add_code_to_directory(heap, directory, names, code_by_name, label):
    for name in names:
        sym = heap.intern(name)
        if sym in directory:
            raise StdlibCheckError("%s duplicate directory entry: %s" % (label, name))
        directory[sym] = code_by_name[name]


def _compile_suite(suite, base_addr=PB.DEFAULT_BASE_ADDR, include_cases=True):
    functions, forms_by_name, macro_names, inliner = _suite_functions_and_forms(suite)
    cases = list(suite.get("cases", []))
    if not cases:
        raise StdlibCheckError("suite has no cases")

    entry_names = [_entry_name(case["name"]) for case in cases]
    if len(set(entry_names)) != len(entry_names):
        raise StdlibCheckError("duplicate case entry names")
    for entry in entry_names:
        if entry in functions:
            raise StdlibCheckError("case entry collides with function: %s" % entry)

    resident_function_symbols = []
    for resident in _resident_suites(suite):
        resident_function_symbols.extend(resident.get("functions", []))

    heap = C.prepare_heap(
        resident_function_symbols + functions + (entry_names if include_cases else [])
    )
    resident_names, resident_code_by_name, resident_entry_flags = _compile_resident_code(suite, heap)
    resident_overrides = set(_as_list(suite.get("resident_overrides")))
    unknown_overrides = sorted(resident_overrides - set(functions))
    if unknown_overrides:
        raise StdlibCheckError(
            "resident_overrides are not target functions: %s"
            % ", ".join(unknown_overrides)
        )
    missing_resident_overrides = sorted(
        resident_overrides - set(resident_code_by_name)
    )
    if missing_resident_overrides:
        raise StdlibCheckError(
            "resident_overrides are not resident functions: %s"
            % ", ".join(missing_resident_overrides)
        )
    names, code_by_name, entry_flags_by_name = _compile_function_objects(
        functions,
        forms_by_name,
        heap,
        macro_names=macro_names,
        existing_names=set(resident_code_by_name) - resident_overrides,
        label="target suite",
        strict_arity=bool(suite.get("strict_arity", False)),
        abi_profile=suite.get("abi_profile"),
    )

    if include_cases:
        for case, entry in zip(cases, entry_names):
            if entry in code_by_name or entry in resident_code_by_name:
                raise StdlibCheckError("case entry collides with code object: %s" % entry)
            expr = _expand_case_expr(suite, inliner, C.parse_one(case["expr"]))
            form = ["defun", entry, [], expr]
            compiled_name, code, helpers = C.compile_top_form_with_helpers(
                form,
                heap,
                strict_arity=bool(suite.get("strict_arity", False)),
                abi_profile=suite.get("abi_profile"),
            )
            names.append(compiled_name)
            code_by_name[compiled_name] = code
            entry_flags_by_name[compiled_name] = 0
            for helper_name, helper_code in helpers:
                if helper_name in code_by_name or helper_name in resident_code_by_name:
                    raise StdlibCheckError("duplicate helper code object: %s" % helper_name)
                names.append(helper_name)
                code_by_name[helper_name] = helper_code
                entry_flags_by_name[helper_name] = 0

    bundle = PB.pack_code_objects(heap, names, code_by_name, base_addr=base_addr)
    directory = PB.load_bundle_directory(heap, bundle)
    _add_code_to_directory(
        heap,
        directory,
        [name for name in resident_names if name not in resident_overrides],
        resident_code_by_name,
        "resident suite",
    )
    return (
        heap,
        names,
        code_by_name,
        entry_flags_by_name,
        resident_entry_flags,
        bundle,
        directory,
        cases,
        entry_names,
        inliner,
    )


def _suite_abi(suite):
    profile = suite.get("abi_profile", "dialect-v1")
    return profile, C._abi_ledger(profile, None)


def _call_edges(heap, code, suite=None):
    edges = []
    pc = 0
    profile, ledger = _suite_abi(suite or {})
    while pc < len(code.payload):
        spec, operand, pc = B.decode_instruction(
            code.payload, pc, profile_id=profile, abi_ledger=ledger
        )
        if spec.mnemonic not in ("CALL", "TAILCALL"):
            continue
        lit_idx, argc = operand
        if lit_idx < len(code.littab):
            target = heap.obj_to_text(code.littab[lit_idx])
        else:
            target = "<bad-lit-%d>" % lit_idx
        edges.append((spec.mnemonic, target, argc))
    return edges


def _directory_symbol_names(heap, directory):
    names = set()
    for sym in directory:
        if heap.symbolp(sym):
            names.add(heap.symbol_name(sym))
    return names


def _validate_dependency_expectations(suite, heap, code_by_name, directory):
    if suite.get("format") != SUITE_FORMAT_DISK_LIB and not suite.get("dependency_gate"):
        return {"checked": False}
    allowed = set(_as_list(suite.get("allowed_external_calls")))
    known = _directory_symbol_names(heap, directory) | set(B.EVAL_PRIMITIVE_NAMES) | allowed
    missing = []
    for name, code in code_by_name.items():
        for mnemonic, target, argc in _call_edges(heap, code, suite):
            if target.startswith("<bad-lit-"):
                missing.append("%s: %s bad literal argc=%d" % (name, mnemonic, argc))
            elif target not in known:
                missing.append("%s: %s %s argc=%d" % (name, mnemonic, target, argc))
    if missing:
        raise StdlibCheckError("unresolved bytecode call targets: %s" % "; ".join(missing))
    return {
        "checked": True,
        "known_targets": len(known),
        "allowed_external_calls": sorted(allowed),
    }


def _validate_tailcall_expectations(suite, heap, code_by_name):
    for name in suite.get("tailcall_self", []):
        if name not in code_by_name:
            raise StdlibCheckError("tailcall_self missing function: %s" % name)
        edges = [
            edge for edge in _call_edges(heap, code_by_name[name], suite)
            if edge[1] == name
        ]
        if not any(edge[0] == "TAILCALL" for edge in edges):
            raise StdlibCheckError("%s: missing self TAILCALL" % name)
        calls = [edge for edge in edges if edge[0] == "CALL"]
        if calls:
            raise StdlibCheckError("%s: self CALL remains: %r" % (name, calls))


def _validate_private_inline_expectations(suite, heap, code_by_name, inliner):
    minimum = suite.get("min_private_inline_functions", 0)
    if not isinstance(minimum, int) or minimum < 0:
        raise StdlibCheckError("min_private_inline_functions must be a non-negative integer")
    if len(inliner.removed_names) < minimum:
        raise StdlibCheckError(
            "private inline function count %d < %d"
            % (len(inliner.removed_names), minimum)
        )
    unused = sorted(name for name, count in inliner.expansions.items() if count == 0)
    if unused:
        raise StdlibCheckError("unused private inline functions: %s" % ", ".join(unused))
    remaining = []
    for caller, code in code_by_name.items():
        for mnemonic, target, _argc in _call_edges(heap, code, suite):
            if target in inliner.name_set:
                remaining.append("%s: %s %s" % (caller, mnemonic, target))
    if remaining:
        raise StdlibCheckError("private inline calls remain: %s" % "; ".join(remaining))
    return {
        "functions": len(inliner.removed_names),
        "resident_functions": len(inliner.names) - len(inliner.removed_names),
        "expansions": sum(inliner.expansions.values()),
        "names": list(inliner.names),
    }


def _validate_vm_limit_expectations(suite, heap, code_by_name):
    max_call_args = suite.get("max_call_args")
    if max_call_args is None:
        return None
    if not isinstance(max_call_args, int) or max_call_args < 0:
        raise StdlibCheckError("max_call_args must be a non-negative integer")

    for name, code in code_by_name.items():
        pc = 0
        while pc < len(code.payload):
            at = pc
            profile, ledger = _suite_abi(suite)
            spec, operand, pc = B.decode_instruction(
                code.payload, pc, profile_id=profile, abi_ledger=ledger
            )
            if spec.mnemonic in ("CALL", "TAILCALL"):
                lit_idx, argc = operand
                if lit_idx < len(code.littab):
                    target = heap.obj_to_text(code.littab[lit_idx])
                else:
                    target = "<bad-lit-%d>" % lit_idx
                site = "%s:%04x %s %s" % (name, at, spec.mnemonic, target)
            elif spec.mnemonic == "CALLPRIM":
                prim_id, argc = operand
                site = "%s:%04x CALLPRIM %s" % (
                    name,
                    at,
                    B.PRIM_IDS.get(prim_id, "#%d" % prim_id),
                )
            else:
                continue
            if argc > max_call_args:
                raise StdlibCheckError(
                    "%s argc %d exceeds max_call_args %d"
                    % (site, argc, max_call_args)
                )
    return max_call_args


def _validate_code_object_size_expectations(suite, code_by_name, skip_names=None):
    max_bytes = suite.get("max_code_object_bytes", DEFAULT_MAX_CODE_OBJECT_BYTES)
    if max_bytes is None:
        return None
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise StdlibCheckError("max_code_object_bytes must be a positive integer")
    skipped = set(skip_names or [])
    oversized = []
    for name, code in code_by_name.items():
        if name in skipped:
            continue
        size = len(code.encode())
        if size > max_bytes:
            oversized.append((name, size))
    if oversized:
        name, size = max(oversized, key=lambda item: item[1])
        raise StdlibCheckError(
            "%s: code object %d B exceeds max_code_object_bytes %d"
            % (name, size, max_bytes)
        )
    return max_bytes


def _validate_vm_dir_headroom_expectations(suite, embed_names):
    vm_dir_max = suite.get("vm_dir_max")
    if vm_dir_max is None:
        return None
    min_headroom = suite.get("min_vm_dir_headroom", 0)
    align_after_boot = bool(suite.get("vm_dir_align8_after_boot", True))
    if not isinstance(vm_dir_max, int) or vm_dir_max <= 0:
        raise StdlibCheckError("vm_dir_max must be a positive integer")
    if not isinstance(min_headroom, int) or min_headroom < 0:
        raise StdlibCheckError("min_vm_dir_headroom must be a non-negative integer")
    objects = len(embed_names)
    used = _align8(objects) if align_after_boot else objects
    headroom = vm_dir_max - used
    if headroom < min_headroom:
        detail = "align8(%d)=%d" % (objects, used) if align_after_boot else str(objects)
        raise StdlibCheckError(
            "VM_DIR headroom %d < %d (%s, vm_dir_max=%d)"
            % (headroom, min_headroom, detail, vm_dir_max)
        )
    return {
        "vm_dir_max": vm_dir_max,
        "objects": objects,
        "used": used,
        "headroom": headroom,
        "min_headroom": min_headroom,
        "align8_after_boot": align_after_boot,
    }


def _validate_disk_lib_manifest_metadata(suite):
    if suite.get("format") != SUITE_FORMAT_DISK_LIB:
        return
    name = suite.get("name")
    d81_name = suite.get("d81_name")
    provides = suite.get("provides")
    requires = suite.get("requires")
    if not isinstance(name, str) or not name:
        raise StdlibCheckError("disk-lib suite needs non-empty name")
    if not isinstance(d81_name, str) or not d81_name:
        raise StdlibCheckError("%s: disk-lib suite needs non-empty d81_name" % name)
    if len(d81_name) > 16:
        raise StdlibCheckError("%s: d81_name exceeds 16 chars: %s" % (name, d81_name))
    for key, value in (("provides", provides), ("requires", requires)):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise StdlibCheckError("%s: %s must be a list of non-empty strings" % (name, key))


def check_suite(path, suite, verbose=False, base_addr=PB.DEFAULT_BASE_ADDR):
    _validate_disk_lib_manifest_metadata(suite)
    (
        heap,
        names,
        code_by_name,
        entry_flags_by_name,
        resident_entry_flags,
        bundle,
        directory,
        cases,
        entry_names,
        inliner,
    ) = _compile_suite(suite, base_addr=base_addr)
    _validate_tailcall_expectations(suite, heap, code_by_name)
    _validate_private_inline_expectations(suite, heap, code_by_name, inliner)
    max_call_args = _validate_vm_limit_expectations(suite, heap, code_by_name)
    _validate_dependency_expectations(suite, heap, code_by_name, directory)
    case_names = _case_object_names(entry_names, code_by_name)
    _validate_code_object_size_expectations(suite, code_by_name, skip_names=case_names)
    _validate_vm_dir_headroom_expectations(
        suite, _suite_embed_names(names, entry_names, code_by_name)
    )
    macro_symbols = _macro_symbol_objs(heap, entry_flags_by_name, resident_entry_flags)
    abi_profile, abi_ledger = _suite_abi(suite)
    total_steps = 0
    observations = []
    for case, entry in zip(cases, entry_names):
        entry_obj = heap.intern(entry)
        if entry_obj not in directory:
            raise AssertionError("%s: missing entry %s" % (case["name"], entry))
        case_heap = heap.clone()
        vm = B.P0VM(
            heap=case_heap,
            directory=directory,
            macro_symbols=macro_symbols,
            max_steps=case.get("max_steps", 100000),
            max_call_args=max_call_args,
            disk_files=case.get("disk_files", suite.get("disk_files")),
            d81_bam_model=suite.get("d81_bam_model", False),
            disk_read_fail_ops=case.get("disk_read_fail_ops"),
            disk_write_fail_ops=case.get("disk_write_fail_ops"),
            disk_mount_token=case.get("disk_mount_token"),
            disk_mount_token_change_before_read_ops=case.get(
                "disk_mount_token_change_before_read_ops"
            ),
            disk_mount_token_change_before_write_ops=case.get(
                "disk_mount_token_change_before_write_ops"
            ),
            disk_mount_token_change_after_guard_before_write_ops=case.get(
                "disk_mount_token_change_after_guard_before_write_ops"
            ),
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        expected_vm_error = case.get("expect_vm_error")
        try:
            result = vm.run(directory[entry_obj], [])
        except B.VMError as exc:
            total_steps += vm.steps
            if exc.status != expected_vm_error:
                raise
            observations.append({
                "name": case["name"], "error": exc.status,
            })
            if verbose:
                print("PASS %-28s steps=%d error=%s" %
                      (case["name"], vm.steps, exc.status))
            continue
        if expected_vm_error:
            raise AssertionError(
                "%s (%s): expected VM error %r"
                % (case["name"], path, expected_vm_error)
            )
        total_steps += vm.steps
        got = case_heap.obj_to_text(result)
        if got != case["expect"]:
            raise AssertionError(
                "%s (%s): expected %r got %r" % (case["name"], path, case["expect"], got)
            )
        terminal_write = case.get("expect_terminal_media_change_at_write")
        if terminal_write is not None:
            if (
                len(vm.disk_write_trace) != terminal_write
                or vm.disk_write_trace[-1].get("operation") != terminal_write
                or vm.disk_write_trace[-1].get("reason")
                != "media-changed-during-transaction"
                or any(row.get("success") for row in vm.disk_write_trace[terminal_write - 1 :])
            ):
                raise AssertionError(
                    "%s (%s): terminal mount-token guard trace drift: %r"
                    % (case["name"], path, vm.disk_write_trace)
                )
        expected_write_count = case.get("expect_disk_write_count")
        if expected_write_count is not None and len(vm.disk_write_trace) != expected_write_count:
            raise AssertionError(
                "%s (%s): expected %d disk writes got %d: %r"
                % (
                    case["name"], path, expected_write_count,
                    len(vm.disk_write_trace), vm.disk_write_trace,
                )
            )
        if "expect_obj" in case:
            got_obj = B.obj_hex(result)
            if got_obj.lower() != case["expect_obj"].lower():
                raise AssertionError(
                    "%s (%s): expected obj %s got %s"
                    % (case["name"], path, case["expect_obj"], got_obj)
                )
        else:
            got_obj = B.obj_hex(result)
        observation = {
            "name": case["name"], "result": got, "object": got_obj.lower(),
        }
        if "external_d81_oracle" in case:
            observation["external_d81_oracle"] = M65D_D81.verify_vm_image(
                vm, case["external_d81_oracle"]
            )
        if "two_media_phase_oracle" in case:
            observation["two_media_phase_oracle"] = M65D_D81.verify_media_change_phase(
                vm, case["two_media_phase_oracle"]
            )
        if "residual_window_boundary_oracle" in case:
            observation["residual_window_boundary_oracle"] = (
                M65D_D81.verify_residual_window_boundary(
                    vm, case["residual_window_boundary_oracle"]
                )
            )
        planning_oracle = case.get("planning_read_guard_oracle")
        if planning_oracle is not None:
            expected_planning = {
                "token-changed-terminal-12": (True, 12),
                "stable-token-preserves-6": (False, 6),
            }
            if planning_oracle not in expected_planning:
                raise AssertionError(
                    "%s (%s): unknown planning-read guard oracle %r"
                    % (case["name"], path, planning_oracle)
                )
            token_changed, classified_status = expected_planning[planning_oracle]
            if got != str(classified_status) or vm.disk_write_trace:
                raise AssertionError(
                    "%s (%s): planning-read guard oracle drift result=%s writes=%r"
                    % (case["name"], path, got, vm.disk_write_trace)
                )
            observation["planning_read_guard_oracle"] = {
                "result": "pass",
                "read_failure_status": 6,
                "mount_token_changed": token_changed,
                "classified_status": classified_status,
                "persistent_status": classified_status,
                "status_state_synchronized": True,
                "partial_write_latched": False,
                "disk_write_count": 0,
            }
        observations.append(observation)
        if verbose:
            print("PASS %-28s steps=%d result=%s" % (case["name"], vm.steps, got))

    return {
        "functions": len(suite.get("functions", [])) - len(inliner.removed_names),
        "cases": len(cases),
        "objects": len(names),
        "code_bytes": len(bundle.blob),
        "directory_bytes": len(bundle.directory_bytes()),
        "steps": total_steps,
        "observations": observations,
        "code_by_name": code_by_name,
    }


def check_paths(paths, verbose=False, base_addr=PB.DEFAULT_BASE_ADDR):
    totals = {
        "suites": 0,
        "functions": 0,
        "cases": 0,
        "objects": 0,
        "code_bytes": 0,
        "directory_bytes": 0,
        "steps": 0,
        "observation_suites": [],
    }
    for path in paths:
        suite = _read_suite(path)
        info = check_suite(path, suite, verbose=verbose, base_addr=base_addr)
        totals["suites"] += 1
        for key in ("functions", "cases", "objects", "code_bytes", "directory_bytes", "steps"):
            totals[key] += info[key]
        with open(path, "rb") as source:
            suite_sha256 = hashlib.sha256(source.read()).hexdigest()
        totals["observation_suites"].append({
            "path": os.path.relpath(path, _repo_root()).replace(os.sep, "/"),
            "sha256": suite_sha256,
            "observations": info["observations"],
        })
    if totals["suites"] == 0:
        raise AssertionError("no stdlib bytecode suites found")
    return totals


def _obj_spec(heap, obj, seen=None):
    obj = B.to_i16(obj)
    if obj == B.NIL:
        return None
    if B.is_fix(obj):
        return B.fixval(obj)
    if seen is None:
        seen = set()
    key = B.to_u16(obj)
    if key in seen:
        raise StdlibCheckError("cyclic literal cannot be emitted: %s" % B.obj_hex(obj))
    seen.add(key)
    try:
        cell = heap.cell(obj)
        if cell.type == B.T_SYM:
            return {"symbol": cell.name}
        if cell.type == B.T_STR:
            return {"string": heap._string_text(cell.a)}
        if cell.type == B.T_CONS:
            items = []
            cur = obj
            list_seen = set()
            while B.is_ptr(cur) and heap.cell(cur).type == B.T_CONS:
                list_key = B.to_u16(cur)
                if list_key in list_seen:
                    raise StdlibCheckError("cyclic literal cannot be emitted: %s" % B.obj_hex(cur))
                list_seen.add(list_key)
                c = heap.cell(cur)
                items.append(_obj_spec(heap, c.a, seen))
                cur = c.b
            if cur == B.NIL:
                return items
            tail = _obj_spec(heap, cur, seen)
            for item in reversed(items):
                tail = {"cons": [item, tail]}
            return tail
        raise StdlibCheckError("unsupported literal cell type: %s" % cell.type)
    finally:
        seen.remove(key)


class LiteralPool:
    def __init__(self):
        self.nodes = []
        self.index = []

    def add_obj(self, heap, obj):
        return self.add(_obj_spec(heap, obj))

    def add_obj_list(self, heap, objs):
        nodes = [self.add_obj(heap, obj) for obj in objs]
        first = len(self.index)
        self.index.extend(nodes)
        return first, len(nodes)

    def add(self, spec):
        if spec is None:
            return self._node(K_NIL)
        if isinstance(spec, bool):
            return self._node(K_T if spec else K_NIL)
        if isinstance(spec, int):
            return self._node(K_FIX, value=spec)
        if isinstance(spec, list):
            children = [self.add(item) for item in spec]
            first = len(self.index)
            self.index.extend(children)
            return self._node(K_LIST, first=first, count=len(children))
        if isinstance(spec, dict):
            if "symbol" in spec:
                return self._node(K_SYMBOL, name=spec["symbol"])
            if "string" in spec:
                return self._node(K_STRING, name=spec["string"])
            if "cons" in spec:
                a, b = spec["cons"]
                child_a = self.add(a)
                child_b = self.add(b)
                first = len(self.index)
                self.index.extend([child_a, child_b])
                return self._node(K_CONS, first=first, count=2)
        raise StdlibCheckError("unsupported literal spec: %r" % (spec,))

    def _node(self, kind, value=0, first=0, count=0, name=None):
        idx = len(self.nodes)
        self.nodes.append(
            {
                "kind": kind,
                "value": int(value),
                "first": int(first),
                "count": int(count),
                "name": name,
            }
        )
        return idx


def _emit_header(
    path, suite_path, suite, names, bundle, literal_pool, manifest_entries, literal_patches
):
    pool = literal_pool
    guard = "LISP65_BYTECODE_STDLIB_P0_H"
    lines = [
        "/* generated by tools/host-lisp/bytecode_p0_stdlib.py; do not edit */",
        "#ifndef %s" % guard,
        "#define %s" % guard,
        "#include <stdint.h>",
        "",
        "#define LISP65_BC_LIT_INVALID 0",
        "#define LISP65_BC_LIT_FIX 1",
        "#define LISP65_BC_LIT_NIL 2",
        "#define LISP65_BC_LIT_T 3",
        "#define LISP65_BC_LIT_SYMBOL 4",
        "#define LISP65_BC_LIT_CONS 5",
        "#define LISP65_BC_LIT_LIST 6",
        "#define LISP65_BC_LIT_STRING 7",
        "#define LISP65_BC_LIT_ENTRY_REF 8",
        "",
        "#define LISP65_BC_ENTRY_MACRO 1",
        "",
        "#define LISP65_BYTECODE_STDLIB_BASE_ADDR 0x%06xu" % bundle.base_addr,
        "#define LISP65_BYTECODE_STDLIB_OBJECT_COUNT %du" % len(names),
        "#define LISP65_BYTECODE_STDLIB_EMBED_COUNT %du" % len(names),
        "#define LISP65_BYTECODE_STDLIB_BLOB_BYTES %du" % len(bundle.blob),
        "#define LISP65_BYTECODE_STDLIB_DIRECTORY_BYTES %du" % len(bundle.directory_bytes()),
        "#define LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT %du" % len(pool.index),
        "#define LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT %du" % len(pool.nodes),
        "#define LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT %du" % len(literal_patches),
    ]
    if "%repl-banner" in names:
        lines.append(
            "#define LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY %du"
            % names.index("%repl-banner")
        )
    lines.extend([
        "",
        "#if defined(LISP65_STDLIB_BOOT_OVERLAY)",
        "#define LISP65_STDLIB_BOOTDATA __attribute__((section(\".lisp65_boot\"), used))",
        "#else",
        "#define LISP65_STDLIB_BOOTDATA",
        "#endif",
        "",
        "typedef struct {",
        "    uint8_t kind;",
        "    int16_t value;",
        "    uint16_t first;",
        "    uint16_t count;",
        "    const char *name;",
        "} lisp65_bc_literal_node;",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uint32_t ext_addr;",
        "    uint8_t flags;",
        "    uint16_t blob_offset;",
        "    uint16_t length;",
        "    uint16_t lit_first;",
        "    uint8_t lit_count;",
        "} lisp65_bc_stdlib_entry;",
        "",
        "typedef struct {",
        "    uint16_t blob_offset;",
        "    uint16_t node;",
        "} lisp65_bc_literal_patch;",
        "",
        "/* Defined in the generated .c unless LISP65_STDLIB_EXTERNAL_BLOB is set.",
        " * Literal-table obj words in the blob are host placeholders; native loaders must",
        " * rewrite them before running. */",
        "#ifndef LISP65_STDLIB_EXTERNAL_BLOB",
        "extern const uint8_t lisp65_stdlib_blob[];",
        "#endif /* LISP65_STDLIB_EXTERNAL_BLOB */",
        "#define lisp65_bytecode_stdlib_blob lisp65_stdlib_blob",
        "",
        "/* Defined by compiling the generated .c with LISP65_BYTECODE_STDLIB_EMIT_METADATA.",
        " * The native MVP VM stdlib target enables this flag so the C materializer can patch",
        " * literal-table obj words before running embedded bytecode. */",
        "extern const uint16_t lisp65_bytecode_stdlib_literal_index[];",
        "extern const lisp65_bc_literal_node lisp65_bytecode_stdlib_literal_nodes[];",
        "extern const lisp65_bc_literal_patch lisp65_bytecode_stdlib_literal_patches[];",
        "",
        "/* Optional full review metadata; not needed by the native boot materializer. */",
        "#ifdef LISP65_BYTECODE_STDLIB_EMIT_FULL_METADATA",
        "extern const uint8_t lisp65_bytecode_stdlib_directory[];",
        "extern const lisp65_bc_stdlib_entry lisp65_bytecode_stdlib_entries[];",
        "#endif /* LISP65_BYTECODE_STDLIB_EMIT_FULL_METADATA */",
        "",
        "/* K3 boot-loader view: use an external/preloaded blob or stage lisp65_stdlib_blob,",
        " * materialize/patch literals, then register lisp65_embed. */",
        "#ifdef LISP65_VM",
        "#include \"vm_registry.h\"",
        "extern const uint16_t lisp65_stdlib_blob_len;",
        "extern const uint8_t lisp65_stdlib_bank;",
        "extern const uint16_t lisp65_stdlib_off;",
        "extern const vm_embed_entry lisp65_embed[];",
        "extern const uint16_t lisp65_embed_count;",
        "#define lisp65_bytecode_stdlib_embed lisp65_embed",
        "#endif /* LISP65_VM */",
        "",
        "/* suite: %s */" % suite_path,
        "/* format: %s */" % suite.get("format", "unknown"),
        "",
        "#endif /* %s */" % guard,
        "",
    ])

    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines))


def _emit_c_source(
    path, header_basename, bundle, literal_pool, manifest_entries, literal_patches
):
    pool = literal_pool
    manifest_by_name = {entry["name"]: entry for entry in manifest_entries}
    dir_strings = {}
    literal_strings = {}

    def add_string(table, text):
        if text is None:
            return "0"
        if text not in table:
            table[text] = "lisp65_bc_boot_str_%03d" % (len(dir_strings) + len(literal_strings))
        return table[text]

    for entry in bundle.entries:
        add_string(dir_strings, entry.name)
    for node in pool.nodes:
        if node["name"] is not None and node["name"] not in dir_strings:
            add_string(literal_strings, node["name"])

    def boot_string(text):
        if text is None:
            return "0"
        if text in dir_strings:
            return dir_strings[text]
        return literal_strings[text]

    lines = [
        "/* generated by tools/host-lisp/bytecode_p0_stdlib.py; do not edit */",
        "#include \"%s\"" % header_basename,
        "",
    ]
    for text, sym in sorted(dir_strings.items(), key=lambda item: item[1]):
        lines.append("static const char %s[] LISP65_STDLIB_BOOTDATA = %s;" % (sym, _cstr(text)))
    if dir_strings:
        lines.append("")

    lines.append("#ifndef LISP65_STDLIB_EXTERNAL_BLOB")
    lines.append("const uint8_t lisp65_stdlib_blob[] LISP65_STDLIB_BOOTDATA = {")
    lines.extend(_bytes_initializer(bundle.blob))
    lines.extend(["};", "#endif /* LISP65_STDLIB_EXTERNAL_BLOB */", ""])
    lines.append("#ifdef LISP65_BYTECODE_STDLIB_EMIT_METADATA")
    for text, sym in sorted(literal_strings.items(), key=lambda item: item[1]):
        lines.append("static const char %s[] LISP65_STDLIB_BOOTDATA = %s;" % (sym, _cstr(text)))
    if literal_strings:
        lines.append("")
    lines.append("const uint16_t lisp65_bytecode_stdlib_literal_index[] LISP65_STDLIB_BOOTDATA = {")
    if pool.index:
        for i in range(0, len(pool.index), 12):
            chunk = pool.index[i : i + 12]
            suffix = "," if i + 12 < len(pool.index) else ""
            lines.append("    " + ", ".join(str(v) for v in chunk) + suffix)
    else:
        lines.append("    0")
    lines.extend(["};", ""])

    lines.append("const lisp65_bc_literal_node lisp65_bytecode_stdlib_literal_nodes[] LISP65_STDLIB_BOOTDATA = {")
    if pool.nodes:
        for node in pool.nodes:
            name = boot_string(node["name"])
            lines.append(
                "    { %d, %d, %d, %d, %s },"
                % (node["kind"], node["value"], node["first"], node["count"], name)
            )
    else:
        lines.append("    { 0, 0, 0, 0, 0 }")
    lines.extend(["};", ""])

    lines.append("const lisp65_bc_literal_patch lisp65_bytecode_stdlib_literal_patches[] LISP65_STDLIB_BOOTDATA = {")
    if literal_patches:
        for patch in literal_patches:
            lines.append(
                "    { %du, %du },"
                % (patch["blob_offset"], patch["node"])
            )
    else:
        lines.append("    { 0, 0 }")
    lines.extend(["};", ""])
    lines.append("#endif /* LISP65_BYTECODE_STDLIB_EMIT_METADATA */")
    lines.append("")

    lines.append("#ifdef LISP65_BYTECODE_STDLIB_EMIT_FULL_METADATA")
    lines.append("/* Raw ABI directory reference. name_sym words are host placeholders;")
    lines.append(" * native loaders should intern entry.name and call vm_dir_add(). */")
    lines.append("const uint8_t lisp65_bytecode_stdlib_directory[] LISP65_STDLIB_BOOTDATA = {")
    lines.extend(_bytes_initializer(bundle.directory_bytes()))
    lines.extend(["};", ""])

    lines.append("const lisp65_bc_stdlib_entry lisp65_bytecode_stdlib_entries[] LISP65_STDLIB_BOOTDATA = {")
    for entry in manifest_entries:
        lines.append(
            "    { %s, 0x%06xu, %du, %du, %du, %du, %du },"
            % (
                boot_string(entry["name"]),
                int(entry["ext_addr"], 0),
                entry["flags"],
                entry["blob_offset"],
                entry["length"],
                entry["lit_first"],
                entry["lit_count"],
            )
        )
    lines.extend(["};", ""])
    lines.append("#endif /* LISP65_BYTECODE_STDLIB_EMIT_FULL_METADATA */")
    lines.append("")

    lines.append("#ifdef LISP65_VM")
    lines.append("const uint16_t lisp65_stdlib_blob_len = LISP65_BYTECODE_STDLIB_BLOB_BYTES;")
    lines.append("const uint8_t lisp65_stdlib_bank = 0x%02xu;" % ((bundle.base_addr >> 16) & 0xFF))
    lines.append("const uint16_t lisp65_stdlib_off = 0x%04xu;" % (bundle.base_addr & 0xFFFF))
    lines.append("const vm_embed_entry lisp65_embed[] LISP65_STDLIB_BOOTDATA = {")
    for entry in bundle.entries:
        manifest_entry = manifest_by_name[entry.name]
        lines.append(
            "    { %s, 0x%02xu, %du, 0x%04xu, %du },"
            % (
                boot_string(entry.name),
                (entry.ext_addr >> 16) & 0xFF,
                manifest_entry["flags"],
                entry.ext_addr & 0xFFFF,
                entry.obj_len,
            )
        )
    lines.append("};")
    lines.append("const uint16_t lisp65_embed_count = LISP65_BYTECODE_STDLIB_EMBED_COUNT;")
    lines.append("#endif /* LISP65_VM */")
    lines.append("")

    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines))


def _literal_text(heap, obj):
    return heap.obj_to_text(obj).replace("\n", "\\n")


def _disasm_text(suite_path, suite, heap, names, code_by_name, bundle):
    abi_profile, abi_ledger = _suite_abi(suite)
    lines = [
        "# generated by tools/host-lisp/bytecode_p0_stdlib.py; do not edit",
        "suite: %s" % suite_path,
        "format: %s" % suite.get("format", "unknown"),
        "base_addr: 0x%06x" % bundle.base_addr,
        "objects: %d" % len(names),
        "code_bytes: %d" % len(bundle.blob),
        "directory_bytes: %d" % len(bundle.directory_bytes()),
        "",
    ]
    for index, entry in enumerate(bundle.entries):
        code = code_by_name[entry.name]
        lines.extend(
            [
                "[%03d] %s" % (index, entry.name),
                "  ext_addr: 0x%06x" % entry.ext_addr,
                "  blob_offset: %d" % entry.blob_offset,
                "  length: %d" % entry.obj_len,
                "  nargs: %d" % code.nargs,
                "  nlocals: %d" % code.nlocals,
                "  flags: %d" % code.flags,
                "  literals: %d" % len(code.littab),
            ]
        )
        for lit_idx, lit in enumerate(code.littab):
            lines.append(
                "    lit[%d] = %s ; %s" % (lit_idx, B.obj_hex(lit), _literal_text(heap, lit))
            )
        lines.append("  payload:")
        for line in B.disassemble_payload(
            code.payload, profile_id=abi_profile, abi_ledger=abi_ledger
        ):
            lines.append("    " + line)
        lines.append("")
    return "\n".join(lines)


def _int_from_hex(value, name):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise StdlibCheckError("bad %s integer: %r" % (name, value))


def _list_from_objs(heap, objs):
    out = B.NIL
    for obj in reversed(objs):
        out = heap.cons(obj, out)
    return out


def _materialize_literal_node(heap, manifest, node_idx, seen=None):
    nodes = manifest.get("literal_nodes", [])
    index = manifest.get("literal_index", [])
    if not 0 <= node_idx < len(nodes):
        raise StdlibCheckError("literal node index out of range: %d" % node_idx)
    if seen is None:
        seen = set()
    if node_idx in seen:
        raise StdlibCheckError("cyclic literal node reference: %d" % node_idx)
    seen.add(node_idx)
    try:
        node = nodes[node_idx]
        kind = int(node.get("kind", 0))
        if kind == K_FIX:
            return B.mkfix(int(node.get("value", 0)))
        if kind == K_NIL:
            return B.NIL
        if kind == K_T:
            return heap.t_obj
        if kind == K_SYMBOL:
            name = node.get("name")
            if not isinstance(name, str):
                raise StdlibCheckError("symbol literal node missing name")
            return heap.intern(name)
        if kind == K_ENTRY_REF:
            ordinal = int(node.get("first", -1))
            entries = manifest.get("entries", [])
            if not 0 <= ordinal < len(entries):
                raise StdlibCheckError("entry-ref ordinal out of range")
            name = entries[ordinal].get("name")
            if not isinstance(name, str) or not name:
                raise StdlibCheckError("entry-ref target is missing its host name")
            # The Python semantic oracle has a symbol-keyed Directory. Native v2
            # materializes this same node as MK_BCODE(dir_base + ordinal).
            return heap.intern(name)
        if kind == K_STRING:
            text = node.get("name")
            if not isinstance(text, str):
                raise StdlibCheckError("string literal node missing text")
            chars = _list_from_objs(heap, [B.mkfix(ord(ch)) for ch in text])
            return heap.alloc(B.T_STR, chars, B.NIL)
        if kind in (K_CONS, K_LIST):
            first = int(node.get("first", 0))
            count = int(node.get("count", 0))
            if first < 0 or count < 0 or first + count > len(index):
                raise StdlibCheckError("literal index range out of bounds")
            child_objs = [
                _materialize_literal_node(heap, manifest, int(index[first + i]), seen)
                for i in range(count)
            ]
            if kind == K_LIST:
                return _list_from_objs(heap, child_objs)
            if count != 2:
                raise StdlibCheckError("cons literal node needs exactly 2 children")
            return heap.cons(child_objs[0], child_objs[1])
        raise StdlibCheckError("unsupported literal node kind: %d" % kind)
    finally:
        seen.remove(node_idx)


def _patched_code_from_manifest_entry(heap, manifest, blob, entry, patch_by_offset):
    start = int(entry["blob_offset"])
    length = int(entry["length"])
    if start < 0 or length < 0 or start + length > len(blob):
        raise StdlibCheckError("entry blob slice out of range: %s" % entry.get("name"))
    code = B.decode_code_object(blob[start : start + length])
    lit_first = int(entry.get("lit_first", 0))
    lit_count = int(entry.get("lit_count", 0))
    if len(code.littab) != lit_count:
        raise StdlibCheckError(
            "%s: code nlits=%d manifest lit_count=%d"
            % (entry.get("name"), len(code.littab), lit_count)
        )
    literal_index = manifest.get("literal_index", [])
    if lit_first < 0 or lit_count < 0 or lit_first + lit_count > len(literal_index):
        raise StdlibCheckError("%s: literal range out of bounds" % entry.get("name"))
    node_idxs = []
    for i in range(lit_count):
        patch_offset = start + CODE_LITTAB_OFFSET + 2 * i
        if patch_offset not in patch_by_offset:
            raise StdlibCheckError(
                "%s: missing literal patch at blob offset %d" % (entry.get("name"), patch_offset)
            )
        node_idx = patch_by_offset[patch_offset]
        if node_idx != int(literal_index[lit_first + i]):
            raise StdlibCheckError(
                "%s: literal patch/index mismatch at slot %d" % (entry.get("name"), i)
            )
        node_idxs.append(node_idx)
    littab = tuple(_materialize_literal_node(heap, manifest, node_idx) for node_idx in node_idxs)
    return B.CodeObject(code.nargs, code.nlocals, code.flags, littab, code.payload)


def _check_embed_manifest(path, suite, manifest, blob, verbose=False):
    if manifest.get("format") not in set(ARTIFACT_FORMATS.values()):
        raise StdlibCheckError("bad artifact manifest format: %r" % manifest.get("format"))
    blob = bytes(blob)
    if _sha256(blob) != manifest.get("blob_sha256"):
        raise StdlibCheckError("blob sha256 mismatch")
    if len(blob) != int(manifest.get("code_bytes", -1)):
        raise StdlibCheckError("blob size mismatch")

    base_addr = _int_from_hex(manifest.get("base_addr"), "base_addr")
    patch_by_offset = {}
    for patch in manifest.get("literal_patches", []):
        blob_offset = int(patch.get("blob_offset", -1))
        node_idx = int(patch.get("node", -1))
        if blob_offset < 0 or blob_offset + 1 >= len(blob):
            raise StdlibCheckError("literal patch blob offset out of range: %d" % blob_offset)
        if node_idx < 0 or node_idx >= len(manifest.get("literal_nodes", [])):
            raise StdlibCheckError("literal patch node out of range: %d" % node_idx)
        if blob_offset in patch_by_offset:
            raise StdlibCheckError("duplicate literal patch offset: %d" % blob_offset)
        patch_by_offset[blob_offset] = node_idx

    heap = C.prepare_heap([])
    directory = {}
    macro_symbols = set()
    expected_patch_count = 0
    for entry in manifest.get("entries", []):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise StdlibCheckError("manifest entry missing name")
        ext_addr = _int_from_hex(entry.get("ext_addr"), "%s ext_addr" % name)
        if ext_addr != base_addr + int(entry["blob_offset"]):
            raise StdlibCheckError("%s: ext_addr/blob_offset mismatch" % name)
        if int(entry["length"]) > 0xFFFF:
            raise StdlibCheckError("%s: object too long for vm_embed_entry" % name)
        flags = int(entry.get("flags", 0))
        if flags & ~ENTRY_FLAG_MACRO:
            raise StdlibCheckError("%s: bad entry flags %d" % (name, flags))
        sym = heap.intern(name)
        if sym in directory:
            raise StdlibCheckError("duplicate manifest entry: %s" % name)
        if flags & ENTRY_FLAG_MACRO:
            macro_symbols.add(sym)
        expected_patch_count += int(entry.get("lit_count", 0))
        directory[sym] = _patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patch_by_offset
        )
    if len(patch_by_offset) != expected_patch_count:
        raise StdlibCheckError(
            "literal patch count mismatch: expected %d got %d"
            % (expected_patch_count, len(patch_by_offset))
        )

    resident_names, resident_code_by_name, resident_entry_flags = _compile_resident_code(suite, heap)
    _functions, _forms, _macros, inliner = _suite_functions_and_forms(suite)
    macro_symbols.update(_macro_symbol_objs(heap, resident_entry_flags))
    _add_code_to_directory(
        heap,
        directory,
        [
            name
            for name in resident_names
            if name not in set(_as_list(suite.get("resident_overrides")))
        ],
        resident_code_by_name,
        "resident suite",
    )

    total_steps = 0
    cases = list(suite.get("cases", []))
    entry_names = [_entry_name(case["name"]) for case in cases]
    max_call_args = suite.get("max_call_args")
    abi_profile, abi_ledger = _suite_abi(suite)
    for case, entry in zip(cases, entry_names):
        case_heap = heap.clone()
        case_directory = dict(directory)
        expr = _expand_case_expr(suite, inliner, C.parse_one(case["expr"]))
        form = ["defun", entry, [], expr]
        compiled_name, code, helpers = C.compile_top_form_with_helpers(
            form,
            case_heap,
            strict_arity=bool(suite.get("strict_arity", False)),
            abi_profile=abi_profile,
        )
        for helper_name, helper_code in helpers:
            helper_obj = case_heap.intern(helper_name)
            if helper_obj in case_directory:
                raise StdlibCheckError("%s: duplicate embed helper %s" % (case["name"], helper_name))
            case_directory[helper_obj] = helper_code
        entry_obj = case_heap.intern(entry)
        if compiled_name != entry:
            raise StdlibCheckError("%s: compiled case name mismatch" % case["name"])
        case_directory[entry_obj] = code
        vm = B.P0VM(
            heap=case_heap,
            directory=case_directory,
            macro_symbols=macro_symbols,
            max_steps=case.get("max_steps", 100000),
            max_call_args=max_call_args,
            disk_files=case.get("disk_files", suite.get("disk_files")),
            d81_bam_model=suite.get("d81_bam_model", False),
            disk_read_fail_ops=case.get("disk_read_fail_ops"),
            disk_write_fail_ops=case.get("disk_write_fail_ops"),
            disk_mount_token=case.get("disk_mount_token"),
            disk_mount_token_change_before_read_ops=case.get(
                "disk_mount_token_change_before_read_ops"
            ),
            disk_mount_token_change_before_write_ops=case.get(
                "disk_mount_token_change_before_write_ops"
            ),
            disk_mount_token_change_after_guard_before_write_ops=case.get(
                "disk_mount_token_change_after_guard_before_write_ops"
            ),
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        expected_vm_error = case.get("expect_vm_error")
        try:
            result = vm.run(case_directory[entry_obj], [])
        except B.VMError as exc:
            total_steps += vm.steps
            if exc.status != expected_vm_error:
                raise
            if verbose:
                print("EMBED PASS %-22s steps=%d error=%s" %
                      (case["name"], vm.steps, exc.status))
            continue
        if expected_vm_error:
            raise AssertionError(
                "%s (%s embed): expected VM error %r"
                % (case["name"], path, expected_vm_error)
            )
        total_steps += vm.steps
        got = case_heap.obj_to_text(result)
        if got != case["expect"]:
            raise AssertionError(
                "%s (%s embed): expected %r got %r"
                % (case["name"], path, case["expect"], got)
            )
        terminal_write = case.get("expect_terminal_media_change_at_write")
        if terminal_write is not None and (
            len(vm.disk_write_trace) != terminal_write
            or vm.disk_write_trace[-1].get("operation") != terminal_write
            or vm.disk_write_trace[-1].get("reason")
            != "media-changed-during-transaction"
        ):
            raise AssertionError(
                "%s (%s embed): terminal mount-token guard trace drift: %r"
                % (case["name"], path, vm.disk_write_trace)
            )
        expected_write_count = case.get("expect_disk_write_count")
        if expected_write_count is not None and len(vm.disk_write_trace) != expected_write_count:
            raise AssertionError(
                "%s (%s embed): expected %d disk writes got %d: %r"
                % (
                    case["name"], path, expected_write_count,
                    len(vm.disk_write_trace), vm.disk_write_trace,
                )
            )
        if verbose:
            print("EMBED PASS %-22s steps=%d result=%s" % (case["name"], vm.steps, got))

    return {
        "objects": len(directory),
        "cases": len(cases),
        "steps": total_steps,
        "literal_nodes": len(manifest.get("literal_nodes", [])),
        "literal_index": len(manifest.get("literal_index", [])),
        "literal_patches": len(patch_by_offset),
    }


def emit_artifacts(path, suite, prefix, base_addr=PB.DEFAULT_BASE_ADDR, artifact_role="stdlib"):
    manifest_format = _artifact_format(artifact_role)
    _validate_disk_lib_manifest_metadata(suite)
    (
        heap,
        names,
        code_by_name,
        entry_flags_by_name,
        resident_entry_flags,
        bundle,
        directory,
        cases,
        entry_names,
        inliner,
    ) = _compile_suite(suite, base_addr=base_addr, include_cases=False)
    _validate_tailcall_expectations(suite, heap, code_by_name)
    private_inline_gate = _validate_private_inline_expectations(
        suite, heap, code_by_name, inliner
    )
    _validate_vm_limit_expectations(suite, heap, code_by_name)
    dependency_gate = _validate_dependency_expectations(suite, heap, code_by_name, directory)
    _validate_code_object_size_expectations(suite, code_by_name)
    vm_dir_budget = _validate_vm_dir_headroom_expectations(suite, names)
    del directory, cases, entry_names, inliner

    prefix_dir = os.path.dirname(prefix)
    if prefix_dir:
        os.makedirs(prefix_dir, exist_ok=True)
    blob_path = prefix + ".blob.bin"
    ext_path = prefix + ".ext.bin"
    dir_path = prefix + ".dir.bin"
    disasm_path = prefix + ".disasm.txt"
    header_path = prefix + ".h"
    c_path = prefix + ".c"
    manifest_path = prefix + ".manifest.json"

    directory_bytes = bundle.directory_bytes()
    disasm_text = _disasm_text(path, suite, heap, names, code_by_name, bundle)
    with open(blob_path, "wb") as f:
        f.write(bundle.blob)
    with open(dir_path, "wb") as f:
        f.write(directory_bytes)
    with open(disasm_path, "w", encoding="utf-8") as f:
        f.write(disasm_text)
        f.write("\n")

    pool = LiteralPool()
    manifest_entries = []
    literal_patches = []
    for entry in bundle.entries:
        code = code_by_name[entry.name]
        lit_first, lit_count = pool.add_obj_list(heap, code.littab)
        for slot in range(lit_count):
            literal_patches.append(
                {
                    "blob_offset": entry.blob_offset + CODE_LITTAB_OFFSET + 2 * slot,
                    "node": pool.index[lit_first + slot],
                }
            )
        manifest_entries.append(
            {
                "name": entry.name,
                "kind": "macro"
                if (entry_flags_by_name.get(entry.name, 0) & ENTRY_FLAG_MACRO)
                else "function",
                "flags": entry_flags_by_name.get(entry.name, 0),
                "code_flags": code.flags,
                "name_obj": B.obj_hex(entry.name_obj),
                "ext_addr": "0x%06x" % entry.ext_addr,
                "blob_offset": entry.blob_offset,
                "length": entry.obj_len,
                "lit_first": lit_first,
                "lit_count": lit_count,
                "literals": [_obj_spec(heap, lit) for lit in code.littab],
            }
        )

    metadata_version, directory_only_refs = _directory_only_transform(
        suite, bundle, pool, manifest_entries
    )

    _emit_header(header_path, path, suite, names, bundle, pool, manifest_entries, literal_patches)
    _emit_c_source(
        c_path,
        os.path.basename(header_path),
        bundle,
        pool,
        manifest_entries,
        literal_patches,
    )

    ext_metadata = _build_ext_metadata(
        bundle, pool, manifest_entries, literal_patches, metadata_version
    )
    _check_ext_metadata(
        ext_metadata, bundle, pool, manifest_entries, literal_patches,
        metadata_version,
    )
    file_header = b""
    if artifact_role == "disk-lib":
        file_header = struct.pack("<HH", len(bundle.blob), len(ext_metadata))
    ext_image = file_header + bytes(bundle.blob) + ext_metadata
    with open(ext_path, "wb") as f:
        f.write(ext_image)
    code_offset = len(file_header)
    metadata_offset = code_offset + len(bundle.blob)
    symbol_cost_names = sorted(
        set(
            entry["name"] for entry in manifest_entries
            if not entry.get("anonymous", False)
        )
        | set(
            node["name"]
            for node in pool.nodes
            if node["kind"] == K_SYMBOL and node["name"] is not None
        )
    )
    largest_entry = max(bundle.entries, key=lambda entry: entry.obj_len, default=None)

    manifest = {
        "format": manifest_format,
        "artifact_role": artifact_role,
        "suite": path,
        "suite_format": suite.get("format"),
        "name": suite.get("name"),
        "strict_arity": bool(suite.get("strict_arity", False)),
        "d81_name": suite.get("d81_name"),
        "provides": list(suite.get("provides", [])),
        "requires": list(suite.get("requires", [])),
        "exports": list(suite.get("exports", [])),
        "override_exports": list(suite.get("override_exports", [])),
        "late_bound_exports": list(suite.get("late_bound_exports", [])),
        "base_addr": "0x%06x" % bundle.base_addr,
        "sources": list(suite.get("sources", [])),
        "resident_suites": _resident_suite_refs(suite),
        "resident_overrides": list(suite.get("resident_overrides", [])),
        "resident_private_inline_functions": list(
            suite.get("resident_private_inline_functions", [])
        ),
        "private_inline_functions": list(suite.get("private_inline_functions", [])),
        "omission_gate": _validate_suite_omissions(suite),
        "functions": [
            name
            for name in suite.get("functions", [])
            if name not in set(_as_list(suite.get("private_inline_functions")))
        ],
        "cases": [case.get("name") for case in suite.get("cases", [])],
        "objects": len(names),
        "code_bytes": len(bundle.blob),
        "directory_bytes": len(directory_bytes),
        "cost": {
            "dir_slots": len(names),
            "dir_slots_after_align8": _align8(len(names)),
            "macro_entries": sum(
                1 for entry in manifest_entries if entry["flags"] & ENTRY_FLAG_MACRO
            ),
            "region_bytes": len(bundle.blob),
            "largest_code_object": largest_entry.name if largest_entry else None,
            "largest_code_object_bytes": largest_entry.obj_len if largest_entry else 0,
            "max_code_object_bytes": suite.get(
                "max_code_object_bytes", DEFAULT_MAX_CODE_OBJECT_BYTES
            ),
            "symbol_names": symbol_cost_names,
            "symbol_count_estimate": len(symbol_cost_names),
            "vm_dir_budget": vm_dir_budget,
            "dependency_gate": dependency_gate,
            "private_inline_gate": private_inline_gate,
        },
        "blob": blob_path,
        "blob_sha256": _sha256(bundle.blob),
        "external_image": {
            "format": "lisp65-bytecode-p0-disk-lib-image-v1"
            if artifact_role == "disk-lib"
            else "lisp65-bytecode-p0-ext-image-v1",
            "path": ext_path,
            "load_addr": "0x%06x" % bundle.base_addr,
            "bytes": len(ext_image),
            "sha256": _sha256(ext_image),
            "file_header_bytes": len(file_header),
            "file_header_format": "u16 blob_len, u16 md_len"
            if artifact_role == "disk-lib"
            else "none",
            "code_offset": code_offset,
            "code_bytes": len(bundle.blob),
            "metadata_offset": metadata_offset,
            "metadata_addr": "0x%06x" % (bundle.base_addr + len(bundle.blob)),
            "metadata_bytes": len(ext_metadata),
            "metadata_sha256": _sha256(ext_metadata),
            "runtime_code_offset": 0,
            "runtime_metadata_offset": len(bundle.blob),
            "metadata_format": {
                "magic": "L65M",
                "version": metadata_version,
                "endianness": "little",
                "header_bytes": 38,
                "entry_record": "u16 name_off, u8 bank, u8 flags, u16 off, u16 len",
                "entry_flags": {
                    "bit0": "macro entry; loader registers T_MACRO(BCODE) instead of a function cell"
                },
                "literal_index_record": "u16 node",
                "literal_node_record": "u8 kind, u8 reserved, i16 value, u16 first, u16 count, u16 name_off_or_0xffff",
                "literal_patch_record": "u16 blob_offset, u16 node",
                "string_pool": "NUL-terminated UTF-8 strings referenced by name_off",
            },
        },
        "relocation": {
            "kind": "runtime-relative" if artifact_role == "disk-lib" else "fixed-ext",
            "disk_lib_contract": "disk-lib files are [u16 blob_len][u16 md_len][blob][L65M]; entry bank/off and literal patch offsets are blob-relative; the device loader stages blob at lib_hw, trailer at lib_hw+blob_len, then supplies the final Bank-5 base",
        },
        "directory": dir_path,
        "directory_note": "raw dir.bin uses host-heap name_obj values; native loaders should intern entries[].name and call vm_dir_add()",
        "directory_sha256": _sha256(directory_bytes),
        "disasm": disasm_path,
        "disasm_sha256": _text_sha256(disasm_text + "\n"),
        "embed": {
            "blob_symbol": "lisp65_stdlib_blob",
            "compat_blob_macro": "lisp65_bytecode_stdlib_blob",
            "blob_len_symbol": "lisp65_stdlib_blob_len",
            "bank_symbol": "lisp65_stdlib_bank",
            "off_symbol": "lisp65_stdlib_off",
            "base_addr_macro": "LISP65_BYTECODE_STDLIB_BASE_ADDR",
            "entry_type": "vm_embed_entry",
            "table_symbol": "lisp65_embed",
            "compat_table_macro": "lisp65_bytecode_stdlib_embed",
            "count_symbol": "lisp65_embed_count",
            "count_macro": "LISP65_BYTECODE_STDLIB_EMBED_COUNT",
            "name_field": "vm_embed_entry.name is a NUL-terminated runtime string; native registration interns that name",
            "flags_field": "vm_embed_entry.flags bit0 marks macro entries; all other bits are reserved and must be zero",
            "address_encoding": "vm_embed_entry.bank/off/len are derived from each object's ext_addr/length",
        },
        "header": header_path,
        "c_source": c_path,
        "literal_format": {
            "node_table": "lisp65_bytecode_stdlib_literal_nodes",
            "index_table": "lisp65_bytecode_stdlib_literal_index",
            "patch_table": "lisp65_bytecode_stdlib_literal_patches",
            "entry_fields": "lisp65_bytecode_stdlib_entries[].lit_first/lit_count map each code object's littab slots to literal_index nodes",
            "patch_fields": "lisp65_bytecode_stdlib_literal_patches[].blob_offset points at each raw 16-bit littab obj word; .node selects the materialized literal node",
            "materialization": "boot loader walks literal_patches, materializes each node, and overwrites the raw host obj word at blob_offset before execution",
        },
        "literal_index": list(pool.index),
        "literal_nodes": list(pool.nodes),
        "literal_patches": literal_patches,
        "literal_note": "code-object literal-table obj words are host placeholders; native loaders must rewrite them from literal_format before running",
        "entries": manifest_entries,
    }
    if metadata_version == 2:
        anonymous_entries = [
            {"ordinal": ordinal, "helper_name": entry["name"],
             "runtime_message": "lib %s entry #%d" % (suite.get("d81_name", suite.get("name", "lib")).lower(), ordinal),
             "source_path": _entry_definition_source(
                 entry["name"], suite.get("sources", []),
                 suite.get("resident_overrides", []),
                 suite.get("definition_source_overrides", {}),
             ),
             "blob_offset": entry["blob_offset"], "length": entry["length"],
             "code_sha256": _sha256(
                 bundle.blob[entry["blob_offset"]:entry["blob_offset"] + entry["length"]]
             )}
            for ordinal, entry in enumerate(manifest_entries)
            if entry.get("anonymous", False)
        ]
        diagnostic_map_path = prefix + ".diagnostic-map.json"
        diagnostic_map = {
            "format": "lisp65-directory-only-diagnostic-map-v1",
            "library": suite.get("d81_name", suite.get("name", "lib")).lower(),
            "artifact_sha256": _sha256(ext_image),
            "entries": anonymous_entries,
        }
        with open(diagnostic_map_path, "w", encoding="utf-8") as f:
            json.dump(diagnostic_map, f, indent=2, sort_keys=True)
            f.write("\n")
        manifest["directory_only"] = {
            "format_version": 2,
            "anonymous_entries": len(anonymous_entries),
            "entry_refs": directory_only_refs,
            "entry_ref_nodes": len({item["node"] for item in directory_only_refs}),
            "diagnostic_map": diagnostic_map_path,
            "diagnostic_map_sha256": _sha256(_read_bytes(diagnostic_map_path)),
            "container_sha256": _sha256(ext_image),
        }
    if "abi_profile" in suite:
        manifest["abi_profile"] = suite["abi_profile"]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    for out_path, expected_size in (
        (blob_path, len(bundle.blob)),
        (ext_path, len(ext_image)),
        (dir_path, len(directory_bytes)),
        (disasm_path, len((disasm_text + "\n").encode("utf-8"))),
    ):
        got_size = os.path.getsize(out_path)
        if got_size != expected_size:
            raise StdlibCheckError(
                "artifact size mismatch for %s: expected %d got %d"
                % (out_path, expected_size, got_size)
            )

    embed_check = _check_embed_manifest(path, suite, _read_json(manifest_path), _read_bytes(blob_path))

    return {
        "prefix": prefix,
        "manifest": manifest_path,
        "disasm": disasm_path,
        "header": header_path,
        "external_image": ext_path,
        "c_source": c_path,
        "objects": len(names),
        "code_bytes": len(bundle.blob),
        "external_bytes": len(ext_image),
        "directory_bytes": len(directory_bytes),
        "artifact_role": artifact_role,
        "embed_cases": embed_check["cases"],
        "embed_steps": embed_check["steps"],
        "literal_nodes": embed_check["literal_nodes"],
        "literal_patches": embed_check["literal_patches"],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="stdlib bytecode suite JSON files")
    ap.add_argument("--check", action="store_true", help="compile and run stdlib bytecode suites")
    ap.add_argument("--private-inline-selftest", action="store_true")
    ap.add_argument("--omission-contract-selftest", action="store_true")
    ap.add_argument("--omission-contract-audit", action="store_true")
    ap.add_argument("--directory-only-selftest", action="store_true")
    ap.add_argument(
        "--emit-artifacts",
        metavar="PREFIX",
        help="write PREFIX.{blob.bin,dir.bin,h,c,manifest.json}",
    )
    ap.add_argument("--base-addr", default="0x050000", help="flat extended-RAM base address")
    ap.add_argument(
        "--observation-report",
        help="write checked per-case observations, including external oracles, as JSON",
    )
    ap.add_argument(
        "--artifact-role",
        choices=sorted(ARTIFACT_FORMATS),
        default="stdlib",
        help="manifest role; disk-lib uses the same L65M trailer with runtime-relative addresses",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args(argv)

    if ns.private_inline_selftest:
        return _private_inline_selftest()
    if ns.omission_contract_selftest:
        return _omission_contract_selftest()
    if ns.omission_contract_audit:
        return _omission_contract_audit()
    if ns.directory_only_selftest:
        return _directory_only_selftest()
    if not ns.check and not ns.emit_artifacts:
        print("bytecode_p0_stdlib.py requires --check or --emit-artifacts", file=sys.stderr)
        return 2
    paths = ns.paths or _default_paths()
    if not paths:
        print("bytecode-p0-stdlib-check: no stdlib suites found", file=sys.stderr)
        return 1
    try:
        base_addr = int(ns.base_addr, 0)
        info = None
        if ns.check:
            info = check_paths(paths, verbose=ns.verbose, base_addr=base_addr)
            if ns.observation_report:
                report = {
                    "format": "lisp65-bytecode-p0-observations-v1",
                    "suites": info["observation_suites"],
                }
                parent = os.path.dirname(os.path.abspath(ns.observation_report))
                os.makedirs(parent, exist_ok=True)
                with open(ns.observation_report, "w", encoding="utf-8") as output:
                    json.dump(report, output, indent=2, sort_keys=True)
                    output.write("\n")
        artifact_info = None
        if ns.emit_artifacts:
            if len(paths) != 1:
                raise StdlibCheckError("--emit-artifacts needs exactly one suite path")
            artifact_info = emit_artifacts(
                paths[0],
                _read_suite(paths[0]),
                ns.emit_artifacts,
                base_addr=base_addr,
                artifact_role=ns.artifact_role,
            )
    except Exception as e:
        print("bytecode-p0-stdlib-check: FAIL: %s" % e, file=sys.stderr)
        return 1
    if info is not None:
        print(
            "bytecode-p0-stdlib-check: PASS suites=%d functions=%d cases=%d objects=%d code_bytes=%d dir_bytes=%d steps=%d"
            % (
                info["suites"],
                info["functions"],
                info["cases"],
                info["objects"],
                info["code_bytes"],
                info["directory_bytes"],
                info["steps"],
            )
        )
    if artifact_info is not None:
        artifact_label = "bytecode-p0-%s-artifacts" % artifact_info["artifact_role"]
        print(
            "%s: WROTE %s objects=%d code_bytes=%d ext_bytes=%d dir_bytes=%d manifest=%s disasm=%s"
            % (
                artifact_label,
                artifact_info["prefix"],
                artifact_info["objects"],
                artifact_info["code_bytes"],
                artifact_info["external_bytes"],
                artifact_info["directory_bytes"],
                artifact_info["manifest"],
                artifact_info["disasm"],
            )
        )
        print(
            "bytecode-p0-stdlib-embed-check: PASS cases=%d objects=%d literal_nodes=%d literal_patches=%d steps=%d"
            % (
                artifact_info["embed_cases"],
                artifact_info["objects"],
                artifact_info["literal_nodes"],
                artifact_info["literal_patches"],
                artifact_info["embed_steps"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
