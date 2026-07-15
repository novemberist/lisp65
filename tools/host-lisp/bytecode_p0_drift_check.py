#!/usr/bin/env python3
"""Drift check for the pinned lisp65 P0 bytecode ABI."""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as S  # noqa: E402


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(ROOT, "docs", "archive", "pre-1.0", "contracts", "bytecode-abi.md")
EMBED_DOC_PATH = os.path.join(ROOT, "docs", "archive", "pre-1.0", "reference", "bytecode-embed-loader.md")
VM_H_PATH = os.path.join(ROOT, "src", "vm.h")
VM_C_PATH = os.path.join(ROOT, "src", "vm.c")
VM_EMBED_C_PATH = os.path.join(ROOT, "src", "vm_embed.c")
VM_REGISTRY_H_PATH = os.path.join(ROOT, "src", "vm_registry.h")
STDLIB_HEADER_PATH = os.path.join(ROOT, "build", "bytecode", "stdlib-p0.h")
STDLIB_C_PATH = os.path.join(ROOT, "build", "bytecode", "stdlib-p0.c")
ABI_LEDGER_PATH = os.path.join(ROOT, "config", "bytecode-abi-ledger.json")
BYTECODE_P0_PATH = os.path.join(ROOT, "tools", "host-lisp", "bytecode_p0.py")


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_md(s):
    s = s.replace("**", "").replace("`", "")
    return s.strip()


def section(text, start_re, end_re):
    start = re.search(start_re, text, re.M)
    if not start:
        raise ValueError("section start not found: %s" % start_re)
    end = re.search(end_re, text[start.end():], re.M)
    if not end:
        return text[start.end():]
    return text[start.end(): start.end() + end.start()]


def parse_doc_ops(text):
    sec = section(text, r"^## 4\. ISA v1", r"^## 4a\.")
    ops = {}
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---") or cells[0] == "#":
            continue
        nums = expand_doc_numbers(strip_md(cells[0]))
        mnems = expand_doc_mnemonics(strip_md(cells[1]), len(nums))
        operand = strip_md(cells[2])
        for num, mnem in zip(nums, mnems):
            ops[num] = (mnem, operand)
    return ops


def expand_doc_numbers(cell):
    cell = cell.replace(" ", "")
    if "\u2013" in cell or "-" in cell:
        parts = re.split(r"[\u2013-]", cell)
        if len(parts) != 2:
            raise ValueError("bad opcode range: %r" % cell)
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, end + 1))
    return [int(cell)]


def expand_doc_mnemonics(cell, count):
    cell = re.sub(r"\s*\([^)]*\)", "", cell).strip()
    if count == 1:
        return [cell]
    m = re.match(r"^([A-Z]+)([0-9/]+)$", cell)
    if not m:
        raise ValueError("cannot expand mnemonic range: %r" % cell)
    prefix, suffixes = m.groups()
    parts = suffixes.split("/")
    if len(parts) != count:
        raise ValueError("mnemonic range length mismatch: %r" % cell)
    return [prefix + part for part in parts]


def parse_doc_prims(text):
    sec = section(text, r"^## 4a\. Gefrorene Prim-ID-Tabelle", r"^## 5\.")
    prims = {}
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].startswith("---") or cells[0] == "Prim-ID":
            continue
        prims[int(strip_md(cells[0]))] = strip_md(cells[1])
    return prims


def python_ops():
    return {spec.code: (spec.mnemonic, spec.operand) for spec in B.OP_SPECS}


def python_prims():
    return dict(B.PRIM_IDS)


def parse_abi_prim_profiles(text):
    value = json.loads(text)
    profiles = {
        item["id"]: item["prim_ids"] for item in value.get("profiles", [])
    }
    return {
        profile: {
            "active": list(space.get("active", [])),
            "tombstone": list(space.get("tombstone", [])),
        }
        for profile, space in profiles.items()
    }


def strip_c_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def parse_vm_h_ops(text):
    cleaned = strip_c_comments(text)
    ops = {}
    current = -1
    for body in re.findall(r"enum\s*\{(.*?)\};", cleaned, flags=re.S):
        for raw in body.split(","):
            item = raw.strip()
            if not item:
                continue
            m = re.match(r"OP_([A-Z0-9_]+)\s*(?:=\s*([0-9]+))?$", item)
            if not m:
                continue
            name, value = m.groups()
            if value is None:
                current += 1
            else:
                current = int(value)
            ops[current] = name
    return ops


def parse_vm_c_callprim_cases(text, doc_prims):
    m = re.search(
        r"static\s+(?:__attribute__\s*\(\([^)]*\)\)\s*)*obj\s+vm_callprim\s*\([^)]*\)\s*\{(.*?)\n\}",
        text,
        re.S,
    )
    if not m:
        return {}
    body = m.group(1)
    cases = {}
    matches = list(re.finditer(r"\bcase\s+([0-9]+)\s*:", body))
    for idx, match in enumerate(matches):
        prim_id = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        block = body[start:end]
        name = None
        for comment in re.findall(r"/\*\s*([^*]+?)\s*\*/", block):
            candidate = comment.strip()
            if candidate in doc_prims.values():
                name = candidate
                break
        cases[prim_id] = name
    return cases


def parse_python_callprim_cases(text):
    cases = {
        int(ident)
        for ident in re.findall(r"\bif\s+prim_id\s*==\s*([0-9]+)\s*:", text)
    }
    for first, last in re.findall(
        r"\bif\s+([0-9]+)\s*<=\s*prim_id\s*<=\s*([0-9]+)\s*:", text
    ):
        cases.update(range(int(first), int(last) + 1))
    return cases


def parse_c_defines(text, prefix):
    defines = {}
    pattern = r"^\s*#define\s+(" + re.escape(prefix) + r"[A-Z0-9_]+)\s+([0-9]+)u?\b"
    for name, value in re.findall(pattern, text, flags=re.M):
        defines[name] = int(value)
    return defines


def python_literal_kinds():
    return {
        "LISP65_BC_LIT_INVALID": 0,
        "LISP65_BC_LIT_FIX": S.K_FIX,
        "LISP65_BC_LIT_NIL": S.K_NIL,
        "LISP65_BC_LIT_T": S.K_T,
        "LISP65_BC_LIT_SYMBOL": S.K_SYMBOL,
        "LISP65_BC_LIT_CONS": S.K_CONS,
        "LISP65_BC_LIT_LIST": S.K_LIST,
        "LISP65_BC_LIT_STRING": S.K_STRING,
        "LISP65_BC_LIT_ENTRY_REF": S.K_ENTRY_REF,
    }


def normalize_c_type(s):
    s = " ".join(s.strip().split())
    return re.sub(r"\s*\*\s*", "*", s)


def parse_c_struct_fields(text, typedef_name):
    m = re.search(r"typedef\s+struct\s*\{([^}]*)\}\s*" + re.escape(typedef_name) + r"\s*;", text, re.S)
    if not m:
        return None
    fields = []
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("/*"):
            continue
        line = line.split("/*", 1)[0].strip()
        m_field = re.match(r"(.+?)([A-Za-z_][A-Za-z0-9_]*)\s*;", line)
        if m_field:
            fields.append((normalize_c_type(m_field.group(1)), m_field.group(2)))
    return fields


def parse_vm_embed_literal_cases(text):
    return set(re.findall(r"\bcase\s+(LISP65_BC_LIT_[A-Z]+)\s*:", text))


def c_unquote_string(s):
    return bytes(s[1:-1], "utf-8").decode("unicode_escape")


def parse_generated_boot_strings(text):
    strings = {}
    pattern = r"static\s+const\s+char\s+([A-Za-z_][A-Za-z0-9_]*)\[\]\s+LISP65_STDLIB_BOOTDATA\s*=\s*(\"(?:\\\\.|[^\"])*\")\s*;"
    for sym, value in re.findall(pattern, text):
        strings[sym] = c_unquote_string(value)
    return strings


def parse_generated_embed_names(text):
    m = re.search(
        r"const\s+vm_embed_entry\s+lisp65_embed\[\]\s*(?:LISP65_STDLIB_BOOTDATA\s*)?=\s*\{(.*?)\n\};",
        text,
        re.S,
    )
    if not m:
        return None
    boot_strings = parse_generated_boot_strings(text)
    names = []
    for expr in re.findall(r"\{\s*([^,]+)\s*,", m.group(1)):
        expr = expr.strip()
        if expr.startswith('"'):
            names.append(c_unquote_string(expr))
        elif expr in boot_strings:
            names.append(boot_strings[expr])
        else:
            return None
    return names


def compare_maps(label, expected, actual, errors):
    if expected == actual:
        return
    expected_keys = set(expected)
    actual_keys = set(actual)
    for key in sorted(expected_keys - actual_keys):
        errors.append("%s missing key %r (expected %r)" % (label, key, expected[key]))
    for key in sorted(actual_keys - expected_keys):
        errors.append("%s extra key %r (actual %r)" % (label, key, actual[key]))
    for key in sorted(expected_keys & actual_keys):
        if expected[key] != actual[key]:
            errors.append(
                "%s mismatch key %r: expected %r, actual %r"
                % (label, key, expected[key], actual[key])
            )


def run(verbose=False):
    doc_text = read_text(DOC_PATH)
    embed_doc_text = read_text(EMBED_DOC_PATH)
    vm_h_text = read_text(VM_H_PATH)
    vm_c_text = read_text(VM_C_PATH)
    vm_embed_c_text = read_text(VM_EMBED_C_PATH)
    vm_registry_h_text = read_text(VM_REGISTRY_H_PATH)
    stdlib_h_text = read_text(STDLIB_HEADER_PATH)
    stdlib_c_text = read_text(STDLIB_C_PATH)
    abi_prim_profiles = parse_abi_prim_profiles(read_text(ABI_LEDGER_PATH))
    python_callprim_cases = parse_python_callprim_cases(read_text(BYTECODE_P0_PATH))

    doc_ops = parse_doc_ops(doc_text)
    doc_prims = parse_doc_prims(doc_text)
    py_ops = python_ops()
    py_prims = python_prims()
    c_ops = parse_vm_h_ops(vm_h_text)
    c_prims = parse_vm_c_callprim_cases(vm_c_text, doc_prims)
    doc_literal_kinds = parse_c_defines(embed_doc_text, "LISP65_BC_LIT_")
    header_literal_kinds = parse_c_defines(stdlib_h_text, "LISP65_BC_LIT_")
    py_literal_kinds = python_literal_kinds()
    vm_embed_literal_cases = parse_vm_embed_literal_cases(vm_embed_c_text)

    errors = []
    compare_maps("docs vs bytecode_p0.py opcodes", doc_ops, py_ops, errors)
    compare_maps("docs vs src/vm.h opcodes", {k: v[0] for k, v in doc_ops.items()}, c_ops, errors)
    compare_maps("docs vs bytecode_p0.py prim IDs", doc_prims, py_prims, errors)
    expected_prim_profiles = {
        "dialect-v1": {"active": list(range(23)), "tombstone": []},
        "dialect-v2": {
            "active": [0] + list(range(3, 26)) + [28, 29] + list(range(30, 34)) + list(range(35, 40)) + list(range(41, 63)),
            "tombstone": [1, 2, 26, 27, 34, 40],
        },
    }
    compare_maps(
        "ABI ledger Prim-ID profile allocation",
        expected_prim_profiles,
        abi_prim_profiles,
        errors,
    )
    if B.INTERNAL_ONLY_PRIM_IDS != frozenset(
        prim_id for prim_id, name in B.PRIM_IDS.items() if name.startswith("%")
    ):
        errors.append("bytecode_p0.py internal-only Prim-ID classification drift")
    compare_maps(
        "bytecode_p0_stdlib.py vs stdlib-p0.h literal kind codes",
        py_literal_kinds,
        header_literal_kinds,
        errors,
    )
    compare_maps(
        "embed docs vs bytecode_p0_stdlib.py literal kind codes",
        doc_literal_kinds,
        {
            name: value for name, value in py_literal_kinds.items()
            if name != "LISP65_BC_LIT_ENTRY_REF"
        },
        errors,
    )

    for prim_id, name in sorted(c_prims.items()):
        if prim_id not in doc_prims:
            errors.append("src/vm.c CALLPRIM extra undocumented Prim-ID %d" % prim_id)
        elif name is not None and name != doc_prims[prim_id]:
            errors.append(
                "src/vm.c CALLPRIM Prim-ID %d comment mismatch: expected %s, actual %s"
                % (prim_id, doc_prims[prim_id], name)
            )
    staging_dispatch = set(range(30, 57))
    for prim_id in sorted(set(doc_prims) - set(c_prims) - staging_dispatch):
        errors.append("src/vm.c CALLPRIM missing documented Prim-ID %d" % prim_id)
    for prim_id in sorted(set(doc_prims) - python_callprim_cases - staging_dispatch):
        errors.append("bytecode_p0.py CALLPRIM missing documented Prim-ID %d" % prim_id)
    for prim_id in sorted(python_callprim_cases - set(doc_prims)):
        errors.append("bytecode_p0.py CALLPRIM has undocumented Prim-ID %d" % prim_id)

    expected_node_fields = [
        ("uint8_t", "kind"),
        ("int16_t", "value"),
        ("uint16_t", "first"),
        ("uint16_t", "count"),
        ("const char*", "name"),
    ]
    expected_patch_fields = [("uint16_t", "blob_offset"), ("uint16_t", "node")]
    expected_stdlib_entry_fields = [
        ("const char*", "name"),
        ("uint32_t", "ext_addr"),
        ("uint8_t", "flags"),
        ("uint16_t", "blob_offset"),
        ("uint16_t", "length"),
        ("uint16_t", "lit_first"),
        ("uint8_t", "lit_count"),
    ]
    expected_vm_embed_entry_fields = [
        ("const char*", "name"),
        ("uint8_t", "bank"),
        ("uint8_t", "flags"),
        ("uint16_t", "off"),
        ("uint16_t", "len"),
    ]
    for label, text, typedef_name, expected in (
        ("stdlib-p0.h literal node ABI", stdlib_h_text, "lisp65_bc_literal_node", expected_node_fields),
        ("stdlib-p0.h literal patch ABI", stdlib_h_text, "lisp65_bc_literal_patch", expected_patch_fields),
        ("stdlib-p0.h stdlib entry ABI", stdlib_h_text, "lisp65_bc_stdlib_entry", expected_stdlib_entry_fields),
        ("vm_registry.h embed entry ABI", vm_registry_h_text, "vm_embed_entry", expected_vm_embed_entry_fields),
    ):
        actual = parse_c_struct_fields(text, typedef_name)
        if actual is None:
            errors.append("%s missing typedef %s" % (label, typedef_name))
        elif actual != expected:
            errors.append("%s mismatch: expected %r, actual %r" % (label, expected, actual))

    materialized_kinds = set(doc_literal_kinds) - {"LISP65_BC_LIT_INVALID"}
    missing_cases = sorted(materialized_kinds - vm_embed_literal_cases)
    extra_cases = sorted(vm_embed_literal_cases - materialized_kinds)
    for name in missing_cases:
        errors.append("src/vm_embed.c materializer missing case %s" % name)
    for name in extra_cases:
        errors.append("src/vm_embed.c materializer has extra case %s" % name)
    for needle in (
        "LISP65_BYTECODE_STDLIB_EMIT_METADATA",
        "stdlib-p0.h",
        "lisp65_bytecode_stdlib_literal_patches",
        "lisp65_bytecode_stdlib_literal_nodes",
        "lisp65_bytecode_stdlib_literal_index",
        "LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT",
    ):
        if needle not in vm_embed_c_text:
            errors.append("src/vm_embed.c missing metadata materializer reference %s" % needle)

    all_defines = parse_c_defines(stdlib_h_text, "LISP65_BYTECODE_STDLIB_")
    embed_names = parse_generated_embed_names(stdlib_c_text)
    embed_count = all_defines.get("LISP65_BYTECODE_STDLIB_EMBED_COUNT")
    if embed_names is None:
        errors.append("stdlib-p0.c missing string-name lisp65_embed[] definition")
    elif embed_count is not None and len(embed_names) != embed_count:
        errors.append(
            "stdlib-p0.c lisp65_embed[] string-name count mismatch: expected %d, actual %d"
            % (embed_count, len(embed_names))
        )
    elif embed_names is not None and len(set(embed_names)) != len(embed_names):
        errors.append("stdlib-p0.c lisp65_embed[] contains duplicate string names")

    if errors:
        for err in errors:
            print("bytecode-p0-drift-check: FAIL: %s" % err, file=sys.stderr)
        return 1

    if verbose:
        print("opcodes:", len(doc_ops))
        print("prim_ids:", len(doc_prims))
        print("src/vm.c CALLPRIM implemented ids:", ",".join(str(i) for i in sorted(c_prims)))
        print("literal_kinds:", len(doc_literal_kinds))
        print("stdlib_embed_names:", len(embed_names or ()))
    print(
        "bytecode-p0-drift-check: PASS opcodes=%d prim_ids=%d c_callprim_impl=%d literal_kinds=%d embed_names=%d"
        % (len(doc_ops), len(doc_prims), len(c_prims), len(doc_literal_kinds), len(embed_names or ()))
    )
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args(argv)
    return run(verbose=ns.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
