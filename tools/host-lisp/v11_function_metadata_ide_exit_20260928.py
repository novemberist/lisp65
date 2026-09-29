"""Bind current generated IDE metadata without replacing the historical index."""
import copy
import v11_function_metadata as H
import ide_exit_successor_20260928 as S
from bytecode_p0_stdlib import CODE_LITTAB_OFFSET


def idex_projection(manifest, blob):
    """Bind code and loader literals, excluding overwritten host obj pointers."""
    H.require(H.sha(blob) == manifest['blob_sha256'], 'idex blob SHA drift')
    normalized = bytearray(blob)
    expected = []
    for entry in manifest['entries']:
        start, length = entry['blob_offset'], entry['length']
        H.require(0 <= start < start + length <= len(blob), 'idex entry span drift')
        code = H.P0.decode_code_object(blob[start:start + length])
        first, count = entry['lit_first'], entry['lit_count']
        H.require(count == len(code.littab) and first >= 0
                  and first + count <= len(manifest['literal_index']),
                  'idex literal span drift')
        for slot in range(count):
            offset = start + CODE_LITTAB_OFFSET + 2 * slot
            node = manifest['literal_index'][first + slot]
            H.require(0 <= node < len(manifest['literal_nodes']), 'idex literal node drift')
            expected.append(dict(blob_offset=offset, node=node))
            normalized[offset:offset + 2] = b'\0\0'
    H.require(expected == manifest['literal_patches'], 'idex literal patch drift')
    return dict(format='idex-loader-code-and-literals-v1',
                normalized_blob_sha256=H.sha(bytes(normalized)),
                literal_tables_sha256=H.sha(H.canonical({
                    key: manifest[key] for key in
                    ('literal_nodes', 'literal_index', 'literal_patches')})))


def projection_selftest(manifest, blob):
    expected = idex_projection(manifest, blob)
    offset = manifest['literal_patches'][0]['blob_offset']
    trial = bytearray(blob)
    trial[offset] ^= 1
    rebound = copy.deepcopy(manifest)
    rebound['blob_sha256'] = H.sha(bytes(trial))
    H.require(idex_projection(rebound, bytes(trial)) == expected,
              'host pointer affected loader projection')
    trial = bytearray(blob)
    trial[-1] ^= 1
    rebound['blob_sha256'] = H.sha(bytes(trial))
    H.require(idex_projection(rebound, bytes(trial)) != expected,
              'code mutation escaped loader projection')
    rebound = copy.deepcopy(manifest)
    rebound['literal_nodes'][0]['value'] = 999
    H.require(idex_projection(rebound, blob) != expected,
              'literal mutation escaped loader projection')
    rebound = copy.deepcopy(manifest)
    rebound['literal_patches'][0]['blob_offset'] += 1
    try:
        idex_projection(rebound, blob)
    except H.MetadataError:
        pass
    else:
        raise H.MetadataError('invalid literal patch accepted')


def derive():
    H.selftest()
    index, receipt = H.collect()
    # idex contributes no public code-object authority. Its whole-container
    # binding still proves code and literal content, but raw host object words
    # are allocator state, not loader semantics. Keep H.collect's raw SHA and
    # code validation, then explicitly label this successor-only projection.
    H.require(not any(row['authority'].get('library') == 'idex'
                      for row in index['records']), 'new public idex authority needs review')
    authority = next(row for row in receipt['bindings']['bytecode_authorities']
                     if row['library'] == 'idex')
    manifest = H.load(H.ROOT / authority['manifest']['path'])
    projection = idex_projection(manifest, (H.ROOT / manifest['blob']).read_bytes())
    projection_selftest(manifest, (H.ROOT / manifest['blob']).read_bytes())
    del authority['blob']['sha256']
    del authority['manifest']['blob_sha256']
    authority['loader_projection'] = projection
    old = H.load(H.INDEX)
    def public(value):
        value = copy.deepcopy(value)
        for row in value['records']:
            row.pop('authority')
        return value
    H.require(public(old) == public(index), 'public metadata semantics regressed')
    # The complete current index is embedded in the new receipt. Its identity
    # points at that receipt's current.index member, never the old index path.
    receipt['index']['path'] = RECEIPT + '#current/index'
    changed = [row['name'] for row, before in zip(index['records'], old['records'])
               if row != before]
    H.require(changed == ['compile-buffer-to-lib', 'compile-file-to-lib', 'eval-buffer',
                          'load-file-to-buffer', 'save-buffer-to'],
              'unexpected metadata authority population drift')
    return dict(index=index, receipt=receipt, changed_authorities=changed)

RECEIPT = 'config/v11-function-metadata-receipt-ide-exit-r2-20260928.json'
HISTORY = {'tools/host-lisp/v11_function_metadata.py': '654745c9a7cf57bc85fbbe5ff96bb687f55479e608d8327803c0f547cb48ab52', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-index.json': 'ab6b8db550e2cf78b160e16ea7fdd8179e56c2c9ab168f1f649496c4d2b1b422', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-contract-receipt.json': '603da81af65ae0c7a67d26c5c82e542159c2cec39f15f60b93e8003f93fff436'}


if __name__ == '__main__':
    S.finish('v11-function-metadata', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, 'lib/ide-keymap-generated.lisp',
              'tools/host-lisp/bytecode_p0_stdlib.py',
              'config/v11-l-lite-keymap.json'))
