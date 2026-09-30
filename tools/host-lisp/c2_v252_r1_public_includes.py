#!/usr/bin/env python3
"""Check the frozen r7c include closure against the public replay inputs.

Static authority only; the public build separately re-derives every
compiler-consumed dependency with `-E -M` in the fresh root.
"""
import json
import c2_v252_r1_public_native as N

CLOSURE = N.ROOT / ('config/%s-include-closure.json' % N.PREFIX)


def check():
    N.check()
    recipe = N.load(N.RECIPE)
    closure = N.load(CLOSURE)
    inputs = {r['materialized_path'] for r in recipe['inputs']}
    commands = recipe['commands']
    N.require(closure['translation_units'] == len(closure['rows']) == 73, 'translation unit population')
    count = 0
    for row, command in zip(closure['rows'], commands[:73], strict=True):
        source = command[command.index('-c') + 1]
        N.require(row['source'] == source and source in row['dependencies'], 'TU/closure order drift: ' + source)
        for dep in row['dependencies']:
            N.require(dep in inputs, 'dependency not a bound replay input: ' + dep)
            count += 1
    return dict(status='PASS: FROZEN R7C INCLUDE AUTHORITY', translation_units=73, dependency_bindings=count,
                compiler_invocations=0, qualification='Authority only; the public build re-derives the closure')


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
