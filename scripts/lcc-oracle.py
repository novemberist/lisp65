#!/usr/bin/env python3
"""lisp65 lcc byte oracle for the historical self-hosting P0 block.

Legacy forms mode compiles each form with Lisp-written lcc through the tree
engine and with the host Python compiler as `(lambda () FORM)`. It compares the
payload and decoded literal table byte-for-byte, binding lcc to both the pinned
ABI and the reference compiler.

The fixture mode compiles tests/bytecode/p0-golden-vectors.json directly with lcc and
compares the declared code header, literal table and payload byte-for-byte. Negative
compile vectors are accepted only when the harness returns its controlled !error marker.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "host-lisp"))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
BIN = os.path.join(ROOT, "build", "equivalence", "equivalence-check")
FORMS = os.path.join(ROOT, "tests", "equivalence", "lcc-p0-forms.lisp")
LCC = os.path.join(ROOT, "lib", "lcc.lisp")
FIXTURE_FORMAT = "lisp65-bytecode-p0-golden-vectors-v1"


class OracleError(ValueError):
    pass


def read_forms(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith(";"):
            out.append(line)
    return out


def lcc_compile_all(binary, forms):
    """Alle Formen in EINEM tree-Lauf durch lcc schicken (lcc-compile-obj); Ausgaben parsen."""
    src = "".join("(lcc-compile-obj (quote %s))\n" % wrap(f) for f in forms)
    with tempfile.NamedTemporaryFile("w", suffix=".lisp", delete=False) as tf:
        tf.write(src)
        tmp = tf.name
    try:
        out = subprocess.run([binary, "tree", tmp, "--preload", LCC],
                             capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(tmp)
    results = []
    for line in out.splitlines():
        if "=>" not in line:
            continue
        results.append(line.split("=>", 1)[1].strip())
    if len(results) != len(forms):
        raise SystemExit("lcc run returned %d results for %d forms" % (len(results), len(forms)))
    return results


def wrap(form):
    """Wrap expressions as (lambda () F), leaving complete lambda/defun forms unchanged."""
    return form if (form.startswith("(lambda") or form.startswith("(defun")) else "(lambda () %s)" % form


def parse_sexp(s):
    """Parse numbers, string-backed symbols, and nested lists from lcc output."""
    toks = re.findall(r"[()]|[^()\s]+", s)
    pos = [0]

    def rd():
        t = toks[pos[0]]; pos[0] += 1
        if t == "(":
            out = []
            while toks[pos[0]] != ")":
                out.append(rd())
            pos[0] += 1
            return out
        return int(t) if re.fullmatch(r"-?\d+", t) else t

    try:
        value = rd()
    except (IndexError, ValueError) as e:
        raise OracleError("invalid lcc output: %r" % s) from e
    if pos[0] != len(toks):
        raise OracleError("Resttoken in lcc-Ausgabe: %r" % s)
    return value


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise OracleError("doppelter JSON-Schluessel: %s" % key)
        out[key] = value
    return out


def validate_fixture(doc):
    if not isinstance(doc, dict) or doc.get("format") != FIXTURE_FORMAT:
        raise OracleError("unerwartetes Fixture-Format")
    vectors = doc.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        raise OracleError("Fixture braucht eine nichtleere vectors-Liste")
    names = set()
    positives = negatives = 0
    for i, vector in enumerate(vectors):
        if not isinstance(vector, dict):
            raise OracleError("vector[%d] ist kein Objekt" % i)
        name = vector.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise OracleError("fehlender oder doppelter Vektorname: %r" % name)
        names.add(name)
        if not isinstance(vector.get("source"), str):
            raise OracleError("%s: source fehlt" % name)
        positive = "code" in vector
        negative = "expect_compile_error" in vector
        if positive == negative:
            raise OracleError("%s: genau code oder expect_compile_error ist erforderlich" % name)
        if positive:
            positives += 1
            validate_expected_code(vector)
        else:
            negatives += 1
            if not isinstance(vector["expect_compile_error"], str) or not vector["expect_compile_error"]:
                raise OracleError("%s: leere Fehlererwartung" % name)
    return vectors, positives, negatives


def load_fixture(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f, object_pairs_hook=strict_object)
    return validate_fixture(doc)


def validate_expected_code(vector):
    name = vector["name"]
    code = vector["code"]
    if not isinstance(code, dict):
        raise OracleError("%s: code ist kein Objekt" % name)
    for field in ("nargs", "nlocals", "flags"):
        if not isinstance(code.get(field), int) or not 0 <= code[field] <= 255:
            raise OracleError("%s: ungueltiges %s" % (name, field))
    if not isinstance(code.get("literals"), list) or not isinstance(code.get("payload_hex"), str):
        raise OracleError("%s: literals/payload_hex fehlen" % name)
    try:
        payload = B.parse_hex(code["payload_hex"])
    except (TypeError, ValueError) as e:
        raise OracleError("%s: ungueltiges payload_hex" % name) from e
    encoded = vector.get("code_object_hex")
    if encoded is not None:
        try:
            obj = B.decode_code_object(B.parse_hex(encoded))
        except (B.DecodeError, TypeError, ValueError) as e:
            raise OracleError("%s: ungueltiges code_object_hex" % name) from e
        declared = (code["nargs"], code["nlocals"], code["flags"], len(code["literals"]), payload)
        actual = (obj.nargs, obj.nlocals, obj.flags, len(obj.littab), obj.payload)
        if actual != declared:
            raise OracleError("%s: code und code_object_hex widersprechen sich" % name)


def expected_literal(spec):
    if spec is None or spec is False or (isinstance(spec, str) and spec.lower() == "nil"):
        return ("symbol", "nil")
    if spec is True or (isinstance(spec, str) and spec.lower() == "t"):
        return ("symbol", "t")
    if isinstance(spec, int):
        return ("integer", spec)
    if isinstance(spec, dict) and set(spec) == {"symbol"} and isinstance(spec["symbol"], str):
        return ("symbol", spec["symbol"].lower())
    raise OracleError("nicht vergleichbares Golden-Literal: %r" % spec)


def actual_literal(value):
    if isinstance(value, int):
        return ("integer", value)
    if isinstance(value, str):
        return ("symbol", value.lower())
    raise OracleError("nicht vergleichbares lcc-Literal: %r" % value)


def actual_literals(value):
    if isinstance(value, str) and value.lower() == "nil":
        return []
    if isinstance(value, list):
        return [actual_literal(x) for x in value]
    raise OracleError("ungueltige lcc-Littab: %r" % value)


def compare_golden_result(vector, out_s):
    name = vector["name"]
    if "expect_compile_error" in vector:
        if out_s != "!error":
            raise OracleError("%s: erwartete !error, bekam %s" % (name, out_s))
        return
    if out_s in ("nil", "!error"):
        raise OracleError("%s: lcc lieferte %s" % (name, out_s))
    fns = parse_sexp(out_s)
    if not isinstance(fns, list) or len(fns) != 1:
        raise OracleError("%s: Golden-Vektor muss genau ein Codeobjekt liefern" % name)
    fn = fns[0]
    if not isinstance(fn, list) or len(fn) != 5:
        raise OracleError("%s: ungueltige Codeobjekt-Form" % name)
    code = vector["code"]
    want_lits = [expected_literal(x) for x in code["literals"]]
    got_lits = actual_literals(fn[3])
    want = (code["nargs"], code["nlocals"], code["flags"], want_lits,
            list(B.parse_hex(code["payload_hex"])))
    got = (fn[0], fn[1], fn[2], got_lits, fn[4] if isinstance(fn[4], list) else None)
    if got != want:
        raise OracleError("%s: Code-Drift\n      lcc:   %s\n      golden: %s" % (name, got, want))


def run_fixture(binary, fixture_path):
    vectors, positives, negatives = load_fixture(fixture_path)
    if (positives, negatives) != (23, 1):
        raise OracleError("Golden-Vertrag erwartet 23 positive und 1 negativen Vektor, bekam %d/%d" %
                          (positives, negatives))
    groups = ([v for v in vectors if "code" in v],
              [v for v in vectors if "expect_compile_error" in v])
    fails = 0
    for group in groups:
        results = lcc_compile_all(binary, [v["source"] for v in group])
        for vector, out_s in zip(group, results):
            try:
                compare_golden_result(vector, out_s)
                print("  %-46s => OK" % vector["name"])
            except OracleError as e:
                fails += 1
                print("  %-46s => DRIFT" % vector["name"])
                print("      %s" % str(e).replace("\n", "\n      "))
    if fails:
        print("lcc-oracle: FAIL (%d/%d Golden-Vektoren weichen ab)" % (fails, len(vectors)))
        return 1
    print("lcc-oracle: PASS vectors=%d positive=%d reject=%d (direct golden fixture)" %
          (len(vectors), positives, negatives))
    return 0


def run_selftest():
    base = {
        "name": "selftest", "source": "(lambda () 7)",
        "code": {"nargs": 0, "nlocals": 0, "flags": 0,
                 "literals": [128, {"symbol": "Length"}], "payload_hex": "01 07 05"},
    }
    good = "((0 0 0 (128 length) (1 7 5)))"
    cases = 0
    compare_golden_result(base, good)
    cases += 1
    empty = copy.deepcopy(base)
    empty["code"]["literals"] = []
    compare_golden_result(empty, "((0 0 0 nil (1 7 5)))")
    cases += 1

    def rejects(vector, output):
        nonlocal cases
        cases += 1
        try:
            compare_golden_result(vector, output)
        except OracleError:
            return
        raise AssertionError("Mutation blieb unentdeckt: %s" % output)

    rejects(base, "((0 0 0 (128 length) (1 6 5)))")
    rejects(base, "((1 0 0 (128 length) (1 7 5)))")
    rejects(base, "((0 0 0 (129 length) (1 7 5)))")
    negative = {"name": "negative", "source": "(lambda () nil)",
                "expect_compile_error": "controlled"}
    compare_golden_result(negative, "!error")
    cases += 1
    rejects(negative, "nil")

    duplicate = '{"format":"%s","vectors":[],"vectors":[]}' % FIXTURE_FORMAT
    try:
        json.loads(duplicate, object_pairs_hook=strict_object)
    except OracleError:
        cases += 1
    else:
        raise AssertionError("doppelter JSON-Schluessel blieb unentdeckt")
    duplicate_names = {"format": FIXTURE_FORMAT, "vectors": [base, copy.deepcopy(base)]}
    try:
        validate_fixture(duplicate_names)
    except OracleError:
        cases += 1
    else:
        raise AssertionError("doppelter Vektorname blieb unentdeckt")
    print("lcc-oracle selftest: PASS cases=%d" % cases)
    return 0


def lit_shape_list(lits):
    """geparste lcc-littab (Objekte) -> Fixnum-Werte, sonst 'ptr'."""
    return [x if isinstance(x, int) else "ptr" for x in (lits if isinstance(lits, list) else [])]


def py_lit_shape(littab):
    """Python-littab (kodierte obj-Woerter) -> Fixnums dekodiert, sonst 'ptr'."""
    out = []
    for w in littab:
        if w & 1:                      # MKFIX(n) = n*2+1 (15-Bit, vorzeichenbehaftet)
            v = w >> 1
            if v >= 0x4000:
                v -= 0x8000
            out.append(v)
        else:
            out.append("ptr")
    return out


def run_forms(binary, forms_path):
    if not os.path.exists(binary):
        raise SystemExit("equivalence-Binary fehlt (%s) — erst scripts/equivalence-check.sh laufen lassen" % binary)

    forms = read_forms(forms_path)
    lcc = lcc_compile_all(binary, forms)
    fails = 0
    for form, out_s in zip(forms, lcc):
        heap = C.prepare_heap([])
        try:
            _, code, helpers = C.compile_top_form_with_helpers(C.parse_one(wrap(form)), heap)
        except C.CompileError as e:
            print("  %-46s => python-unsupported (%s)" % (form, e))
            continue
        if out_s == "nil":
            print("  %-46s => DRIFT (lcc: unsupported/error)" % form)
            fails += 1
            continue
        fns = parse_sexp(out_s)                      # function list, MAIN last
        def shape(o):
            return (o[0], o[1], o[2], lit_shape_list(o[3]), o[4] if isinstance(o[4], list) else [])
        got_main = shape(fns[-1])
        want_main = (code.nargs, code.nlocals, code.flags, py_lit_shape(code.littab), list(code.payload))
        got_helpers = [shape(o) for o in fns[:-1]]
        want_helpers = [(h[1].nargs, h[1].nlocals, h[1].flags, py_lit_shape(h[1].littab), list(h[1].payload))
                        for h in helpers]
        ok = got_main == want_main and got_helpers == want_helpers
        print("  %-46s => %s" % (form, "OK" if ok else "DRIFT"))
        if not ok:
            fails += 1
            print("      lcc:    main=%s helpers=%s" % (got_main, got_helpers))
            print("      python: main=%s helpers=%s" % (want_main, want_helpers))
    if fails:
        print("lcc-oracle: FAIL (%d/%d Formen weichen ab)" % (fails, len(forms)))
        return 1
    print("lcc-oracle: PASS forms=%d (lcc byte-identisch mit dem Referenz-Compiler)" % len(forms))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default=BIN)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--forms", default=None)
    modes.add_argument("--fixture")
    modes.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    if not os.path.exists(args.binary):
        raise SystemExit("equivalence-Binary fehlt (%s) - erst scripts/equivalence-check.sh laufen lassen" %
                         args.binary)
    try:
        if args.fixture:
            return run_fixture(args.binary, args.fixture)
        return run_forms(args.binary, args.forms or FORMS)
    except (OracleError, OSError, json.JSONDecodeError) as e:
        print("lcc-oracle: FAIL (%s)" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
