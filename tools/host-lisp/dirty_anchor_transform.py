"""Retain the first inserted list node for incremental REPL painting."""
import re

def transform(text):
    seams=[
        (r'\(defun %rl-put \(code state cursor dirty\)', '(defun %rl-put (code state cursor dirty anchor)'),
        (r'\(%rl-put next-code state inserted dirty\)', '(%rl-put next-code state inserted dirty anchor)'),
        (r'\(nthcdr dirty \(cdr \(car state\)\)\)', '(cdr anchor)'),
        (r'\(%rl-put code state \(car \(cdr state\)\)\s*\(car \(nthcdr 3 state\)\)\)', '(%rl-put code state (car (cdr state))\n                     (car (nthcdr 3 state)) (car (cdr state)))'),
    ]
    for pattern,replacement in seams:
        text,n=re.subn(pattern,lambda _:replacement,text)
        if n!=1:raise ValueError('REPL anchor seam drift: '+pattern)
    return text


def check_authored(root, authority):
    import subprocess
    import bytecode_p0_stdlib as S
    path='lib/stdlib-read-line.lisp'
    prior=subprocess.check_output(['git','show',authority+':'+path],cwd=root,text=True)
    current=(root/path).read_text()
    if S.C.parse_all(current)!=S.C.parse_all(transform(prior)):
        raise ValueError('authored REPL change differs from the four qualified anchor seams')
