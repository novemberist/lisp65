"""Real Lisp resolver/index/fast-note on SBCL with explicit target I/O seams."""
from pathlib import Path
import json
import shutil
import struct
import subprocess
import set_b_producer as P
import c2_link75_real_require_resolver_host as H
import c2_require_resolver_gate as I
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-cl-r1'
CAND=ROOT/'build/set-b-load-repair-proposal-r5/candidate/lib/stdlib-require.lisp'
SNAPS=ROOT/'build/set-b-load-attribution-r1'
MEDIA=ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'
u=lambda b,a:int.from_bytes(b[a:a+2],'little')
def put(b,a,v):struct.pack_into('<H',b,a,v)
def q(x):return json.dumps(str(x))
PREFIX=r'''
(defpackage :set-b-proof (:use :cl) (:shadow :require :symbol-value))
(in-package :set-b-proof)
(declaim (optimize (speed 1) (safety 3) (debug 1)))
(defun symbol-value (s) (if (boundp s) (cl:symbol-value s) nil))
(defun set-symbol-value (s v) (setf (cl:symbol-value s) v))
(defun %string-codes (s) (map 'list #'char-code s))
(defun %string-from-codes (xs) (coerce (mapcar #'code-char xs) 'string))
(defun %list-malformed-error (&rest xs) (error "malformed ~s" xs))
(defun bytes (p) (with-open-file (s p :element-type '(unsigned-byte 8))
  (let ((v (make-array (file-length s) :element-type '(unsigned-byte 8)))) (read-sequence v s) v)))
(defvar *media*) (defvar *c2d*) (defvar *sector*) (defvar *parts*)
(defvar *reads*) (defvar *sectors*) (defvar *appends*) (defvar *plans*)
(defvar *mutation*) (defvar *scans*)
(defun %c2d-byte (lo &optional (hi nil hip))
  (incf *reads*) (if hip (aref *c2d* (+ lo (* 256 hi)))
    (if (= lo 16) 1 (nth lo *parts*))))
(defun %disk-read-sector (track sector)
  (incf *sectors*)
  (let ((at (* 256 (+ (* (1- track) 40) sector))))
    (setf *sector* (subseq *media* at (+ at 256)))) t)
(defun %disk-byte (a &optional (b nil bp))
  (if bp (let ((crc (logxor (+ (car a) (* 256 (cdr a))) (ash b 8))))
           (dotimes (n 8) (setf crc (logand 65535 (logxor (ash crc 1) (if (logbitp 15 crc) 4129 0)))))
           (setf (car a) (logand crc 255) (cdr a) (ash crc -8)) b)
    (aref *sector* a)))
(defun %disk-load-lib (&rest args)
  (if (/= (length args) 2) nil
    (let ((plan (pop *plans*)))
      (assert (equal args (subseq plan 0 2))) (incf *appends*)
      (unless (eq *mutation* :no-publication) (setf *c2d* (bytes (third plan)))) t)))
(defun load-functions (path &optional allowed)
  (with-open-file (s path)
    (loop for f = (read s nil :eof) until (eq f :eof) do
      (when (and (consp f) (eq (car f) 'defun) (or (null allowed) (member (second f) allowed))) (eval f)))))
(defun run-case (label pre plans names wants mutation)
  (dolist (s '(*require-fast* *require-index-lock* *require-visiting* *require-visited* *require-order*)) (set-symbol-value s nil))
  (setf *c2d* (bytes pre) *plans* plans *reads* 0 *sectors* 0 *appends* 0 *mutation* mutation *scans* nil)
  (loop for name in names for want in wants for number from 0 do
    (let* ((r *reads*) (s *sectors*) (a *appends*) (got (if (require name) t nil)))
      (assert (eq got want))
      (when (and (= number 1) (string= name "defstruct")) (assert (= s *sectors*)) (assert (= a *appends*)))
      (format t "ROW|~a|~a|~a|~d|~d|~d~%" label name got (- *reads* r) (- *sectors* s) (- *appends* a))))
  (format t "SCANS|~a|~{~d~^,~}~%" label (reverse *scans*)))
'''

def main():
    OUT.mkdir(exist_ok=False);loc,payload=H.media_locators(MEDIA.read_bytes());index=I.decode_index(payload['l65index']);sources=[];cases=[]
    def read(n,phase):
        p=SNAPS/f'definitions-{n}/{phase}-c2d.bin';sources.append(P.bind(p));return bytearray(p.read_bytes())
    def save(name,b):p=OUT/(name+'.bin');p.write_bytes(b);return p
    def case(label,pre,posts,names,wants,mutation='nil'):
        plans=' '.join(f'({loc[n][0]} {loc[n][1]} {q(save(label+"-after-"+str(i),b))})' for i,(n,b) in enumerate(posts))
        cases.append(f'(run-case {q(label)} {q(save(label+"-before",pre))} \'({plans}) \'({" ".join(q(n) for n in names)}) \'({" ".join("t" if w else "nil" for w in wants)}) {mutation})')
    for n in (0,1):case(f'definitions-{n}',read(n,'before-load'),[('defstruct',read(n,'after-load'))],['defstruct','defstruct'],[True,True])
    pre=read(2,'before-load');source=read(1,'after-load');post=bytearray(pre)
    row=bytearray(source[48+9*32:48+10*32]);oldentry=u(row,6);count=u(row,8);put(row,6,806);put(row,18,u(row,18)+10)
    post[48+9*32:48+10*32]=row
    for i in range(count):
        e=bytearray(source[0x830+(oldentry+i)*10:0x830+(oldentry+i+1)*10]);put(e,2,u(e,2)+10)
        post[0x830+(806+i)*10:0x830+(807+i)*10]=e
    for off,a,n in [(0x5830,10,12),(0x7830,14,16)]:
        start=u(row,a);length=u(row,n);post[off+2*start:off+2*(start+length)]=source[off+2*start:off+2*(start+length)]
    for at,value in [(12,10),(16,806+count),(20,u(source,20)),(24,u(source,24))]:put(post,at,value)
    case('definitions-2',pre,[('defstruct',post)],['defstruct','defstruct'],[True,True])
    case('success-without-publication',pre,[('defstruct',post)],['defstruct'],[False],':no-publication')
    bad=bytearray(post);bad[48+9*32+28]^=1
    case('wrong-published-identity',pre,[('defstruct',bad)],['defstruct'],[False])
    for label,at in [('live-overlap',0x130+18),('bad-generation',0x130+4)]:
        bad=bytearray(pre);bad[at]=2;case(label,bad,[],['defstruct'],[False])
    last=read(0,'before-load');first=last[48+6*32:48+7*32];second=last[48+7*32:48+8*32]
    boot=bytearray(last);middle=bytearray(last)
    for b,row,count in [(boot,first,6),(middle,second,7)]:
        for at,value in [(12,count),(16,u(row,6)),(20,u(row,10)),(24,u(row,14))]:put(b,at,value)
        b[48+count*32:48+8*32]=bytes((8-count)*32)
    case('exact-init-libraries',boot,[('place',middle),('string-extra',last)],['place','string-extra'],[True,True])
    parts=P.load(ROOT/'build/set-b-load-world-checks-r2/owner-parts.json')['parts']
    script=OUT/'run.lisp';script.write_text(PREFIX+f'\n(setf *media* (bytes {q(MEDIA)}) *parts* \'({" ".join(map(str,parts))}))\n'+
        f'(load-functions {q(ROOT/"lib/stdlib-load.lisp")} \'(%load-fold-code %load-name-code-at %load-entry-byte %load-entry-used-p %load-name-match-at %load-entry-match-p %disk-directory-link-valid-p))\n'+
        f'(load-functions {q(CAND)})\n'+
        '''(let ((original (symbol-function '%require-charged-front)))
  (setf (symbol-function '%require-charged-front)
    (lambda (slot count gen low) (when (= slot 0) (push count *scans*))
      (funcall original slot count gen low))))
'''+ '\n'.join(cases)+'\n(format t "PASS ALL 8 CASES~%")\n')
    command=[shutil.which('sbcl'),'--script',str(script)];r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);log=OUT/'execution.txt';log.write_text(r.stdout+r.stderr)
    P.write(OUT/'execution.json',dict(command=command,exit=r.returncode,log=P.bind(log),script=P.bind(script)));assert r.returncode==0,r.stdout+r.stderr[-3000:]
    rows=[s.split('|') for s in r.stdout.splitlines() if s.startswith(('ROW|','SCANS|'))];P.write(OUT/'rows.json',rows)
    P.write(OUT/'receipt.json',dict(status='PASS: 8 REAL INDEXED LISP/FAST-NOTE CASES ON SBCL',driver=P.bind(Path(__file__)),candidate=P.bind(CAND),loader_helpers=P.bind(ROOT/'lib/stdlib-load.lisp'),media=P.bind(MEDIA),snapshots=sources,index=index,execution=P.bind(OUT/'execution.json'),rows=P.bind(OUT/'rows.json'),
        claim='Unmodified resolver defuns and selected loader directory defuns evaluated by SBCL; target CRC-byte, byte-string and unbound-symbol adapters; Prim18 is captured publication replay, not native append. No target GC, arithmetic-overflow or instruction-timing claim.',product_builds=0,product_links=0,seeds=0,guest_launches=0,device_contacts=0))
    print(r.stdout)
if __name__=='__main__':main()
