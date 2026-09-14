"""Form-(c) projection of an already selected product editor.

This module does not select another editor or add a function population.
It consumes the product's source, removes Capture setup/teardown, replaces
raw reads by public blocking reads, and declines printable prefetch. The
editing algorithm and quoted data are otherwise unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import bytecode_p0_compiler as Reader


class LoweringError(ValueError):
    pass


def compose_list_domain(base: str, domain: str) -> tuple[str, dict]:
    """Resolve the product's strict definitions once, before closure selection."""
    base_forms, domain_forms = Reader.parse_all(base), Reader.parse_all(domain)
    require(all(isinstance(f, list) and len(f) >= 4 and f[0] == 'defun'
                for f in domain_forms), 'unexpected list-domain top-level form')
    replacements = {f[1]: f for f in domain_forms}
    require(len(replacements) == len(domain_forms), 'duplicate list-domain definition')
    names = [f[1] for f in base_forms if isinstance(f, list) and f
             and f[0] in ('defun', 'defmacro')]
    require(len(names) == len(set(names)), 'duplicate base definition')
    forms = [replacements.get(f[1], f) if isinstance(f, list) and f
             and f[0] == 'defun' else f for f in base_forms]
    forms += [f for f in domain_forms if f[1] not in names]
    result = '\n\n'.join(render(f) for f in forms) + '\n'
    require(Reader.parse_all(result) == forms, 'domain projection roundtrip differs')
    return result, dict(base_sha256=hashlib.sha256(base.encode()).hexdigest(),
                        domain_sha256=hashlib.sha256(domain.encode()).hexdigest(),
                        output_sha256=hashlib.sha256(result.encode()).hexdigest(),
                        replaced=sorted(set(names) & replacements.keys()),
                        added=sorted(replacements.keys() - set(names)))


def require(condition, message):
    if not condition:
        raise LoweringError(message)


def render(value):
    if isinstance(value, Reader.StringLit):
        # The source reader's string syntax is deliberately not broadened here.
        require('"' not in value.value, 'unsupported quote in generated string')
        return '"' + value.value + '"'
    if isinstance(value, Reader.DottedList):
        return '(' + ' '.join(map(render, value.items)) + ' . ' + render(value.tail) + ')'
    if isinstance(value, list):
        return '(' + ' '.join(map(render, value)) + ')'
    require(isinstance(value, (str, int)), 'unsupported source atom')
    return str(value)


def product_source(authored: str, selected: str) -> tuple[str, dict]:
    """Use the product-selected population and its two lifecycle/input seams.

    Shared bodies come from the authored editor. The native constructor and
    poll expression retain the selected product policy (no shelf idle job).
    Newly reached helpers are derived to closure, never a second member list.
    """
    def definitions(text):
        forms = Reader.parse_all(text)
        require(all(isinstance(f, list) and len(f) >= 4 and f[0] == 'defun'
                    for f in forms), 'unexpected editor top-level form')
        result = {f[1]: f for f in forms}
        require(len(result) == len(forms), 'duplicate editor definition')
        return result
    source, template = definitions(authored), definitions(selected)
    require(set(template) <= set(source), 'selected product member missing')
    chosen = {n: copy.deepcopy(source[n]) for n in template}
    chosen['read-line'] = copy.deepcopy(template['read-line'])
    loop = chosen['%read-line-loop']
    require(loop[3][1][0] == ['event', ['%rl-poll', 'state']], 'authored poll seam drift')
    loop[3][1][0] = copy.deepcopy(template['%read-line-loop'][3][1][0])

    def calls(value):
        if not isinstance(value, list) or not value or value[0] == 'quote':
            return set()
        result = {value[0]} if isinstance(value[0], str) and value[0] in source else set()
        for child in value:
            result |= calls(child)
        return result
    todo = list(chosen)
    while todo:
        name = todo.pop()
        for target in sorted(calls(chosen[name][3:])):
            if target not in chosen:
                chosen[target] = copy.deepcopy(source[target])
                todo.append(target)
    result = '\n\n'.join(render(f) for f in chosen.values()) + '\n'
    require(Reader.parse_all(result) == list(chosen.values()), 'product source roundtrip differs')
    return result, dict(authored_sha256=hashlib.sha256(authored.encode()).hexdigest(),
                        selected_sha256=hashlib.sha256(selected.encode()).hexdigest(),
                        output_sha256=hashlib.sha256(result.encode()).hexdigest(),
                        selected_definitions=list(template), derived_definitions=list(chosen),
                        retained_policy=['native constructor', 'native polling expression'])


def lower(source: str) -> tuple[str, dict]:
    original = Reader.parse_all(source)
    forms = copy.deepcopy(original)
    entries = [f for f in forms if isinstance(f, list) and len(f) >= 4
               and f[:2] == ['defun', 'read-line']]
    require(len(entries) == 1, 'product read-line owner must be unique')
    entry = entries[0]
    require(len(entry) == 4, 'read-line body shape drift')
    body = entry[3]
    setup = Reader.parse_all('''(poke 255 141 255) (poke 255 140 0)
      (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))
      (poke 255 141 0)''')
    require(isinstance(body, list) and len(body) == 6
            and body[0] == 'progn' and body[1:5] == setup,
            'Capture setup does not match the product seam')
    main = body[5]
    require(isinstance(main, list) and main[0] == 'let*'
            and main[-1] == ['progn', ['poke', 255, 141, 255], 'answer'],
            'Capture teardown does not match the product seam')
    main[-1] = 'answer'
    entry[3] = main
    counts = {2: 0, 3: 0}

    def walk(value):
        if not isinstance(value, list) or not value:
            return value
        if value[0] == 'quote':
            return value
        for mode in counts:
            if value == ['key-event', mode]:
                counts[mode] += 1
                return ['key-event', 1] if mode == 2 else 'nil'
        require(value[0] != 'poke', 'unexpected remaining hardware write')
        return [walk(v) for v in value]

    forms = [walk(f) for f in forms]
    require(counts[2] == 1 and counts[3] == 1,
            'raw input seam population drift')
    result = '; Generated from the selected product editor; do not edit.\n'
    result += '\n\n'.join(render(f) for f in forms) + '\n'
    require(Reader.parse_all(result) == forms, 'generated source roundtrip differs')
    names = lambda fs: [f[1] for f in fs if isinstance(f, list) and f
                        and f[0] in ('defun', 'defmacro')]
    require(names(original) == names(forms), 'definition population changed')
    return result, {
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'output_sha256': hashlib.sha256(result.encode()).hexdigest(),
        'definitions': names(forms), 'raw_read_sites': counts[2],
        'declined_prefetch_sites': counts[3],
        'semantics': ['public blocking mode 1', 'no printable prefetch',
                      'public event allocation', 'no Capture initialization'],
    }


def verify(source: str, output: str, receipt: dict):
    expected, binding = lower(source)
    require(output == expected, 'hand-edited or stale lowered source')
    require(receipt == binding, 'lowering provenance drift')


def materialize(source: Path, output: Path) -> dict:
    text, receipt = lower(source.read_text(encoding='utf-8'))
    if output.exists():
        verify(source.read_text(encoding='utf-8'), output.read_text(), receipt)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding='utf-8')
    verify(source.read_text(encoding='utf-8'), output.read_text(), receipt)
    return receipt


def selftest(source: str) -> dict:
    output, receipt = lower(source)
    verify(source, output, receipt)
    rejected = []
    cases = [
        ('hand-edited-file', source, output + '\n; manual edit', receipt),
        ('source-sha-drift', source + '\n; changed source', output, receipt),
        ('binding-drift', source, output, dict(receipt, raw_read_sites=0)),
        ('missing-raw-read', source.replace('(key-event 2)', '(key-event 1)'), output, receipt),
        ('missing-prefetch', source.replace('(key-event 3)', 'nil'), output, receipt),
        ('missing-capture-setup', source.replace('(poke 255 140 0)', 'nil'), output, receipt),
    ]
    for name, src, out, proof in cases:
        try:
            verify(src, out, proof)
        except LoweringError:
            rejected.append(name)
        else:
            raise LoweringError('mutation escaped: ' + name)
    return dict(status='PASS: STRUCTURAL LOWERING ONLY', binding=receipt,
                mutations_rejected=rejected, product_builds=0,
                limits=['execution, typing costs and composed prompt not tested here'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    print(json.dumps(selftest(args.source.read_text()), indent=2))
