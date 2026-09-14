#!/usr/bin/env python3
"""A8: derive the L65I reader bounds from the live format writer.

AST operands, not comment/search hits, supply the reader values. No product
build or source rewrite; disagreement (including an unknown syntax) fails.
"""
import ast
import hashlib
import json
from pathlib import Path

import bytecode_p0_stdlib as P

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT/'tools/host-lisp/c2_require_resolver_gate.py'
READER = ROOT/'lib/stdlib-require.lisp'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def nodes(form):
    if isinstance(form, list):
        yield form
        for child in form:
            yield from nodes(child)


def one_operand(form, prefix):
    found = [n[len(prefix)] for n in nodes(form)
             if len(n) == len(prefix)+1 and n[:len(prefix)] == prefix]
    require(len(found) == 1 and type(found[0]) is int,
            'missing/ambiguous/nonliteral bound: '+repr(prefix))
    return found[0]


def values(writer, reader):
    constants = {}
    wanted = {'HEADER_BYTES', 'ROW_BYTES', 'MAX_ROWS', 'MAX_DEPS'}
    for node in ast.parse(writer).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    require(target.id not in constants, 'duplicate writer bound')
                    value = ast.literal_eval(node.value)
                    require(type(value) is int and value > 0, 'invalid writer bound')
                    constants[target.id] = value
    require(set(constants) == wanted, 'missing writer bound')
    forms = P.C.parse_all(reader)
    funcs = {}
    for form in forms:
        if isinstance(form, list) and form and form[0] == 'defun':
            require(form[1] not in funcs, 'duplicate reader function')
            funcs[form[1]] = form
    header = funcs['%l65i-header']
    read = dict(
        header=one_operand(header, ['=', 'header-bytes']),
        row=one_operand(header, ['=', 'row-bytes']),
        deps=one_operand(header, ['=', 'max-dependencies']),
        rows=one_operand(header, ['<=', 'rows']),
        product_row=one_operand(header, ['*', 'rows']),
        fuel=one_operand(funcs['%l65i-parse'], ['set-symbol-value', ['quote', '*l65i-fuel*']]),
        sentinel=one_operand(funcs['%l65i-dependencies'], ['=', 'ordinal']))
    return constants, read


def validate(writer, reader):
    header, row, count, deps = [writer[n] for n in ('HEADER_BYTES', 'ROW_BYTES', 'MAX_ROWS', 'MAX_DEPS')]
    require((reader['header'], reader['row'], reader['rows'], reader['deps'], reader['product_row'])
            == (header, row, count, deps, row), 'writer/reader format disagreement')
    # 1581 DOS: 256 physical bytes minus the two link bytes per data sector.
    payload = 256-2
    fuel = (header+count*row+payload-1)//payload
    require(reader['fuel'] == fuel, 'reader fuel is not the format-derived ceiling')
    require(reader['sentinel'] == 255 and reader['sentinel'] > count,
            'dependency sentinel collides with the row population')
    return dict(maximum_index_bytes=header+count*row, data_bytes_per_sector=payload,
                derived_sector_fuel=fuel, writer=writer, reader=reader)


def run():
    w, r = values(WRITER.read_text(), READER.read_text())
    result = validate(w, r)
    controls = []
    for key in r:
        for delta in (-1, 1):
            changed = dict(r); changed[key] += delta
            try:
                validate(w, changed)
            except ValueError:
                controls.append(f'reader-{key}{delta:+}')
            else:
                raise ValueError('reader mutation survived: '+key)
    for key in w:
        changed = dict(w); changed[key] += 1
        try:
            validate(changed, r)
        except ValueError:
            controls.append('writer-'+key)
        else:
            raise ValueError('writer mutation survived: '+key)
    result.update(status='PASS', mutations_rejected=controls,
        inputs=[dict(path=p.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in (WRITER, READER)])
    return result


if __name__ == '__main__':
    result = run()
    out = ROOT/'build/library-index-couplings/receipt.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+'\n')
    print('library-index-couplings: PASS, %d rejected mutations' % len(result['mutations_rejected']))
