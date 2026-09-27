"""Indexed SBCL successor for native-query form, with a declared query model.

Actual query C has an independent target-width host differential/fault proof.
This seam does not claim native instruction timing or a new product.
"""
import inspect
from pathlib import Path
import set_b_load_preflight_cl_20260926 as O
import set_b_producer as P
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-native-cl-r1'
QUERY=r'''
(defun query-u16 (at) (+ (aref *c2d* at) (* 256 (aref *c2d* (1+ at)))))
(defun native-front-query ()
 (let ((generation (query-u16 10)) (count (query-u16 16)) (low 0))
  (push count *scans*)
  (when (> count 2048) (return-from native-front-query nil))
  (dotimes (i count)
   (let* ((row (+ 2096 (* i 10))) (start (query-u16 (+ row 2))) (size (query-u16 (+ row 4))))
    (when (or (/= (query-u16 (+ row 8)) generation) (= size 0) (> start 60758) (> size (- 60758 start)))
     (return-from native-front-query nil))
    (setf low (max low (+ start size)))))
  (cons (logand low 255) (ash low -8))))
'''
def main():
    prefix=O.PREFIX.replace('(if (= lo 16) 1 (nth lo *parts*))','(if (= lo 16) 1 (if (= lo 17) (native-front-query) (nth lo *parts*)))')
    assert prefix!=O.PREFIX
    # Define the query model after shared variables, before loading defuns.
    prefix+=QUERY
    source=inspect.getsource(O.main)
    start=source.index('        \'\'\'(let ((original')
    end=source.index("+ '\\n'.join(cases)",start)
    source=source[:start]+"        ''"+source[end:]
    folder=ROOT/'build/set-b-load-preflight-native-cl-driver-r1';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(source)
    ns=dict(vars(O));ns.update(OUT=OUT,PREFIX=prefix,CAND=ROOT/'build/set-b-load-preflight-native-r2/candidate/lib/stdlib-require.lisp',__file__=__file__)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(O.__file__)),executed=P.bind(folder/'executed.py'),query_C_proof=P.bind(ROOT/'build/set-b-load-preflight-query-r1/receipt.json')))
    exec(compile(source,str(folder/'executed.py'),'exec'),ns);ns['main']()
if __name__=='__main__':main()
