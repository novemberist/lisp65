"""Replay 2.1 documents with their keymap era; bind current IDE-exit docs."""
import c2_v210_bundle_docs_gate as H
import c2_v251_r2_20260929_bundle_docs_gate as LIVE
import evidence_era as E
import ide_exit_successor_20260928 as S


def derive():
    with E.host_source_world(H.RELEASE_DOC_COMMIT, (S.KEYMAP,)) as reads:
        facts = H.facts(S.ROOT)
        texts, era = H.historical_texts(S.ROOT)
        mutations = H.selftest(texts, facts)
        result = H.validate(texts, H.TOP, facts)
    # Demonstrate that substituting the live count into frozen prose is red.
    live_count = len(H.json.loads((S.ROOT / S.KEYMAP).read_bytes())['bindings'])
    S.require(live_count == 42 and facts['key_bindings'] == 41, 'IDE exit key count delta drift')
    try:
        H.validate(texts, H.TOP, dict(facts, key_bindings=live_count))
    except ValueError:
        mutations.append('live-keymap-count-in-historical-docs')
    else:
        raise ValueError('mixed document era mutation survived')
    LIVE.check(S.ROOT)
    return dict(historical=result, historical_documents=era, historical_reads=reads,
                mutations_rejected=mutations, current_key_bindings=live_count)

RECEIPT = 'config/c2-v251-r2-20260929-v210-bundle-docs-receipt.json'
HISTORY = {'tools/host-lisp/c2_v210_bundle_docs_gate.py': 'a4dac1d528e89eab7ae641419238b6a73741be92dd5fb50b4300bc86fbec21a2', 'config/c2-v210-document-metadata.json': 'cf55e830b7d84529d5eea10ae4fb615e92dd1cc286d732e9267d36c851a14d3e'}


if __name__ == '__main__':
    S.finish('c2-v210-bundle-docs', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, LIVE.__file__, S.KEYMAP,
              'docs/user-guide.md', 'docs/generated/ide-keymap.md',
              'config/c2-v251-r2-20260929-bundle-docs.json'))
