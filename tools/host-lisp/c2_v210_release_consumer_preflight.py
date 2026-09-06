#!/usr/bin/env python3
"""Artifact-only replay of selected release consumers; never compile a product.

The population is the actual file-consuming call sites of the selected
qualification/media route, augmented with the compiler's emitted input census.
It is not the import closure of dormant historical cards. Unbound build inputs
are reported together. No claim is made about unselected historical workflows.
"""
import argparse
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys


def run(P, output):
    import c2_v210_public_media as M
    root = P.ROOT.resolve()
    current = (P.PUBLIC, P.BUILD, P.PREFLIGHT)
    observed = {}
    writes = set()
    active = [True]
    processes = []
    source_files = {Path(__file__).resolve()}
    previous_profile = sys.getprofile()
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_filename.startswith(str(root/'tools/host-lisp')):
            source_files.add(Path(frame.f_code.co_filename))

    def audit(event, args):
        if not active[0]:
            return
        if event == 'subprocess.Popen':
            argv = args[1]
            executable = Path(str(args[0])).name
            if 'clang' in executable or executable in ('ld.lld', 'lld'):
                raise RuntimeError('preflight forbids product/stager compilation')
            processes.append([str(x) for x in argv])
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0]))
        if not path.is_absolute():
            path = Path.cwd() / path
        path = Path(os.path.normpath(path))
        if not path.is_relative_to(root/'build'):
            return
        mode, flags = args[1:3]
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR))
        frame = sys._getframe(1)
        while frame and not str(frame.f_code.co_filename).startswith(str(root/'tools/host-lisp')):
            frame = frame.f_back
        caller = (str(Path(frame.f_code.co_filename).relative_to(root)) + ':' +
                  frame.f_code.co_name + ':' + str(frame.f_lineno)) if frame else '<external>'
        row = observed.setdefault(path, {'readers':set(), 'writers':set(), 'fresh':None})
        if writing:
            row['writers'].add(caller)
            writes.add(path)
        else:
            row['readers'].add(caller)
            if row['fresh'] is None:
                row['fresh'] = path in writes

    # The subprocess branches select these exact functions. Invoke them in the
    # traced process, retaining their own configuration and all real gates.
    original_child = P.run_child
    def child(action):
        if action == '_scope':
            P.write_public_scope()
        elif action == '_public_accept':
            P.write_public_acceptance()
        else:
            raise RuntimeError('unapproved preflight child: '+action)
        return 'artifact-only preflight '+action
    P.run_child = child
    sys.addaudithook(audit)
    sys.setprofile(profile)
    try:
        before = {role:P.bind(path) for role,path in
                  (('PRG',P.PRG),('ELF',P.ELF),('profile',P.PROFILE))}
        P.configure_card()
        P.CARD.CHAIN.LINK.configure()
        P.CARD.CHAIN.LINK.setup_child()
        P.bind_completion_plane()
        product = P.CARD.CHAIN.LINK.PRODUCT
        product.closure_gate(P.PRG.parent, P.PRG)
        product.kernal_freedom_gate(P.PRG.parent, P.PRG)
        pre = P.load(P.source_preflight_path())
        sources = [root/row['path'] for row in pre['sources']]
        generated = {p:p for p in sources if 'generated-product-sources' in p.parts}
        P.consume_source_preflight(P.source_preflight_path(), pre, sources, generated)
        P.qualify_link('replay of read-only qualification; no compiler invoked')
        M.pack(P, resume=True)
        P.check()
        import c2_v210_bundle_docs_gate as DOCS
        facts = DOCS.facts(root)
        texts = DOCS.source_texts(root)
        documents = DOCS.validate(texts, DOCS.TOP, facts)
        documents['mutations_rejected'] = DOCS.selftest(texts, facts)
        after = {role:P.bind(path) for role,path in
                 (('PRG',P.PRG),('ELF',P.ELF),('profile',P.PROFILE))}
        P.require(before == after, 'consumer preflight changed product')
    finally:
        active[0] = False
        sys.setprofile(previous_profile)
        P.run_child = original_child

    # Aliases are derived from the materializer's bound source projections,
    # not accepted just because some unrelated file has matching contents.
    aliases = {}
    def bound_rows(value):
        if isinstance(value, dict):
            if {'path','bytes','sha256'} <= value.keys():
                aliases[root/value['path']] = value
            for child in value.values(): bound_rows(child)
        elif isinstance(value, list):
            for child in value: bound_rows(child)
    bound_rows(P.load(P.STATIC_RECEIPT))
    bound_rows(P.load(P.PLANE_RECEIPT))
    def classification(path, event):
        if any(path.is_relative_to(base) for base in current):
            return 'renderer-producer-root'
        if path in aliases and path.is_file() and P.bind(path) == aliases[path]:
            return 'producer-bound-materialization-view'
        if event['fresh']:
            return 'generated-by-selected-consumer-before-read'
        return 'UNBOUND PREEXISTING BUILD INPUT'

    rows, reds = [], []
    for path, event in sorted(observed.items()):
        if not event['readers']:
            continue
        row = {'path':str(path.relative_to(root)),
               'readers':sorted(event['readers']), 'writers':sorted(event['writers'])}
        row['classification'] = classification(path, event)
        if row['classification'] == 'UNBOUND PREEXISTING BUILD INPUT':
            reds.append(row)
        if path.is_file(): row['identity'] = P.bind(path)
        rows.append(row)
    # The expected population is the executed census, never a maintained list.
    def validate_population(trial):
        P.require(trial == rows and not reds, 'release consumer census divergence')
    mutations = []
    if not reds:
        validate_population(rows)
        samples = {'input-omitted':rows[:-1], 'reader-omitted':copy.deepcopy(rows),
                   'consumer-path-divergence':copy.deepcopy(rows)}
        samples['reader-omitted'][0]['readers'] = []
        samples['consumer-path-divergence'][0]['path'] = 'build/foreign-release/resolved-profile.txt'
        for name, trial in samples.items():
            try: validate_population(trial)
            except P.PublicBuildError: mutations.append(name)
            else: raise RuntimeError('consumer mutation survived: '+name)
        P.require(classification(root/'build/foreign-release/resolved-profile.txt',
                                 {'fresh':False}) == 'UNBOUND PREEXISTING BUILD INPUT',
                  'foreign profile accepted')
        mutations.append('foreign-profile-root')
        # Reading an old input and only later overwriting it never legitimizes
        # the original read; the census remembers the first-read state.
        P.require(classification(root/'build/foreign-release/product.prg',
                                 {'fresh':False}) == 'UNBOUND PREEXISTING BUILD INPUT',
                  'read-before-generation accepted')
        mutations.append('read-before-generation')
    value = {'format':'lisp65-v210-selected-release-consumer-preflight-v1',
        'status':'PASS' if not reds else 'HALT',
        'scope':'executed selected qualification and packed-media route; compiler population from executed producer receipt',
        'unselected_historical_workflows_claimed':False,
        'compiler_sources':pre['compiler_sources'],
        'inputs':rows, 'unbound_inputs':reds, 'subprocesses':processes,
        'documents':documents, 'mutations_rejected':mutations,
        'executed_tool_sources':[P.bind(p) for p in sorted(source_files)],
        'raw_pair_before':before, 'raw_pair_after':after,
        'product_compiler_invocations':0, 'product_links':0}
    output.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':value['status'],'inputs':len(rows),'unbound':len(reds),
                      'unbound_paths':[r['path'] for r in reds]},indent=2))
    return value


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',required=True,type=Path)
    args=parser.parse_args()
    import c2_v210_public_product as P
    result=run(P,args.receipt)
    sys.exit(0 if result['status']=='PASS' else 2)
