#!/usr/bin/env python3
"""Check the prospective document population without writing the Git index."""
import subprocess,json
import document_index as D

def main():
    raw=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','--','docs'],cwd=D.ROOT)
    paths=tuple(sorted({p.decode() for p in raw.split(b'\0') if p.endswith(b'.md')}))
    result=D.validate_index(D.load_index(D.DEFAULT_INDEX),paths)
    D.verify_files(D.ROOT,paths)
    print(json.dumps(dict(status='PASS',scope='working tree including untracked reviewer files; Git index unchanged',documents=len(paths),classes=result),indent=2))
if __name__=='__main__':main()
