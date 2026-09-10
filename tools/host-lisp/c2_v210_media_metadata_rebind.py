#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Field-level release-authority census; no compiler invocation or source edit."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess

FIELD = 'selected_media_sha256'
AUTHORITY = 'config/c2-v210-public-build-authority.json'
HOST = 'tools/host-lisp/'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text())


def blob(repo, commit, name):
    return subprocess.check_output(['git','show',f'{commit}:{name}'],cwd=repo)


def authority_keys(text, filename):
    """Close every reference to the product authority accessor, not a call list.

    Its dictionary may only be projected by a literal top-level key. Passing,
    aliasing or enumerating the whole dictionary fails closed. The product
    accessor's own envelope reads are separately derived from its local value.
    """
    tree = ast.parse(text)
    parents = {child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    result = []
    for node in ast.walk(tree):
        accessor = (isinstance(node,ast.Name) and node.id=='authority' and
                    filename.endswith('c2_v210_public_product.py')) or (
                    isinstance(node,ast.Attribute) and node.attr=='authority' and
                    isinstance(node.value,ast.Name) and node.value.id=='P')
        if not accessor:
            continue
        call = parents.get(node)
        require(isinstance(call,ast.Call) and call.func is node and not call.args and not call.keywords,
                'authority accessor escapes: '+filename+':'+str(node.lineno))
        use = parents.get(call)
        if isinstance(use,ast.Subscript) and use.value is call:
            key = use.slice
        elif isinstance(use,ast.Attribute) and use.value is call and use.attr=='get':
            getcall=parents.get(use)
            require(isinstance(getcall,ast.Call) and len(getcall.args)>=1,'unresolved get')
            key=getcall.args[0]
        else:
            raise ValueError('whole authority dictionary escapes: '+filename+':'+str(node.lineno))
        require(isinstance(key,ast.Constant) and isinstance(key.value,str),'dynamic authority key')
        result.append({'path':filename,'line':node.lineno,'key':key.value,
                       'expression':ast.get_source_segment(text,use)})
    return sorted(result,key=lambda row:row['line'])


def census(repo, commit):
    files = subprocess.check_output(['git','ls-tree','-r','--name-only',commit],cwd=repo).decode().splitlines()
    sources={name:blob(repo,commit,name).decode() for name in files if name.endswith('.py')}
    literals=[]; field_uses=[]
    for name,text in sources.items():
        tree=ast.parse(text)
        parents={child:n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for n in ast.walk(tree):
            if isinstance(n,ast.Constant) and n.value==AUTHORITY:
                literals.append({'path':name,'line':n.lineno})
            if isinstance(n,ast.Constant) and n.value==FIELD:
                parent=parents.get(n)
                if isinstance(parent,ast.Subscript):
                    kind='subscript';expr=parent
                elif isinstance(parent,ast.Call):
                    kind='call';expr=parent
                elif isinstance(parent,ast.Dict):
                    kind='dictionary-construction';expr=n
                else:
                    kind='other';expr=parent
                field_uses.append({'path':name,'line':n.lineno,'kind':kind,
                                   'expression':ast.get_source_segment(text,expr)})
    # All direct v210 authority-file owners, derived across the public Python
    # population. New owners stop this bounded proof instead of inheriting it.
    owner_contracts = {
        HOST+'c2_v210_public_product.py':'product envelope and literal-key projections',
        HOST+'workbench_product.py':'driver selection and whole-file source signature, not compiler input',
        HOST+'c2_v210_public_clean_build.py':'reproduction orchestration and role verification',
        HOST+'c2_v210_bundle_docs_gate.py':'document facts and whole-file provenance hash',
    }
    require({r['path'] for r in literals}==set(owner_contracts),'unresolved authority-file owner population')
    keys=[]
    for name in (HOST+'c2_v210_public_product.py',HOST+'c2_v210_public_media.py'):
        keys.extend(authority_keys(sources[name],name))
    require(not any(r['key']==FIELD for r in keys),'product/media consumes selected media field')
    # Envelope and file-owning helpers use local dictionaries. For these names
    # close all dictionary uses, allowing only literal projections and the
    # single accessor return already closed above.
    local_reads=[]
    for name in owner_contracts:
        tree=ast.parse(sources[name])
        parents={child:n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for n in ast.walk(tree):
            if not isinstance(n,ast.Name) or not isinstance(n.ctx,ast.Load):continue
            wanted='value' if name.endswith('c2_v210_public_product.py') else 'authority'
            if n.id!=wanted:continue
            ancestor=n
            while ancestor in parents and not isinstance(ancestor,ast.FunctionDef):ancestor=parents[ancestor]
            if wanted=='value' and getattr(ancestor,'name',None)!='authority':continue
            p=parents[n]
            if isinstance(p,ast.Subscript) and p.value is n:key=p.slice
            elif isinstance(p,ast.Attribute) and p.value is n and p.attr=='get':
                call=parents[p];require(isinstance(call,ast.Call) and call.args,'unresolved local get');key=call.args[0]
            elif wanted=='value' and isinstance(p,ast.Return):continue
            elif name.endswith('workbench_product.py') and getattr(ancestor,'name','')=='selftest':continue
            else:raise ValueError('unresolved local authority escape: '+name+':'+str(n.lineno))
            require(isinstance(key,ast.Constant) and isinstance(key.value,str),'dynamic local authority projection')
            require(key.value!=FIELD,'file-owning route consumes selected media field')
            local_reads.append({'path':name,'line':n.lineno,'key':key.value})
    # Whole-file hashes do change; do not mislabel them as unchanged inputs.
    require('bind(root, selected["authority"])' in sources[HOST+'workbench_product.py'],
            'source signature model changed')
    return {'python_files':len(sources),'authority_file_owners':literals,
            'owner_dispositions':owner_contracts,'product_accessor_reads':keys,
            'local_dictionary_reads':local_reads,'all_literal_field_uses':field_uses,
            'sources':[{'path':n,'sha256':digest(t.encode())} for n,t in sources.items()
                       if n in owner_contracts or n==HOST+'c2_v210_public_media.py'],
            'whole_file_metadata_consumers':['source-signature','bundle-docs provenance'],
            'compile_link_field_consumers':0,
            'scope':'selected v210 product and media accessor plus every direct public authority-file owner; no claim about arbitrary reflection'}


def check_medium(authority):
    require(authority[FIELD]==authority['sealed_roles']['product-d81']['sha256'],
            'selected media disagrees with sealed product D81')


def reject_compile_field(rows):
    require(not any(r['key']==FIELD for r in rows),'compile/link field consumer present')


def main():
    p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,required=True)
    p.add_argument('--commit',required=True);p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();result=census(a.repository,a.commit)
    authority=json.loads(blob(a.repository,a.commit,AUTHORITY));before=copy.deepcopy(authority)
    authority[FIELD]=authority['sealed_roles']['product-d81']['sha256'];check_medium(authority)
    mutations=[]
    for value in ('0'*64,before[FIELD]):
        trial=copy.deepcopy(authority);trial[FIELD]=value
        try:check_medium(trial)
        except ValueError:mutations.append('wrong-medium-'+value[:8])
        else:raise ValueError('wrong media mutation survived')
    source=blob(a.repository,a.commit,HOST+'c2_v210_public_product.py').decode()
    trial=source+'\ndef injected_compile_consumer():\n    return authority()["'+FIELD+'"]\n'
    try:reject_compile_field(authority_keys(trial,HOST+'c2_v210_public_product.py'))
    except ValueError:mutations.append('new-compile-field-consumer')
    else:raise ValueError('new compile field consumer accepted')
    trial=source+'\ndef escaped_authority():\n    return authority()\n'
    try:authority_keys(trial,HOST+'c2_v210_public_product.py')
    except ValueError:mutations.append('whole-dictionary-escape')
    else:raise ValueError('whole dictionary escape accepted')
    result.update({'authorization':'85179434','status':'PASS: route C, no compile/link field consumer',
                   'source_commit':a.commit,'mutations':mutations,'product_builds':0,
                   'field_before':before[FIELD],'field_after':authority[FIELD]})
    a.receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(result['status'])


if __name__=='__main__':main()
