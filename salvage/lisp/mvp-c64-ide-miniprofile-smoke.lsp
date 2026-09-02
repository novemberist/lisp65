; MVP C64 IDE miniprofile smoke.
;
; Kept deliberately small: one edit operation, buffer/session wrapping, and view
; composition. This is the first native-loadable vertical slice before key input
; and eval are wired.

; C64-bare replacements for the selected host IDE functions whose CL-style LET
; expansion would otherwise emit direct LAMBDA calls. The native LOAD path keeps
; this profile in the old dialect: DE + PROG + helpers.

(DE TAKE (n l)
  (COND ((ZEROP n) NIL)
        ((NULL l) NIL)
        (T (CONS (CAR l) (TAKE (SUB1 n) (CDR l))))))

(DE DROP (n l)
  (COND ((ZEROP n) l)
        ((NULL l) NIL)
        (T (DROP (SUB1 n) (CDR l)))))

(DE NTH-ELEM (n l)
  (CAR (DROP n l)))

(DE REPLACE-AT (l n new)
  (COND ((NULL l) NIL)
        ((ZEROP n) (CONS new (CDR l)))
        (T (CONS (CAR l) (REPLACE-AT (CDR l) (SUB1 n) new)))))

(DE CAT-CHARS (strs)
  (COND ((NULL strs) NIL)
        (T (APPEND (UNPACK (CAR strs)) (CAT-CHARS (CDR strs))))))

(DE CAT (strs)
  (PACK (CAT-CHARS strs)))

(DE INT->STR (n)
  (PACK (INT->CHARS n)))

(DE SS-MK args
  (LIST (CAR args)
        (CAR (CDR args))
        (CAR (CDR (CDR args)))
        (CAR (CDR (CDR (CDR args))))))

(DE ED-INSERT-LINE-LEFT (s)
  (TAKE (ED-COL s) (CUR-LINE s)))

(DE LINE->STR (l)
  (COND ((NULL l) "") (T (PACK l))))

(DE ED-INSERT-LINE-RIGHT (s)
  (DROP (ED-COL s) (CUR-LINE s)))

(DE ED-INSERT-LINE (s ch)
  (APPEND (ED-INSERT-LINE-LEFT s) (CONS ch (ED-INSERT-LINE-RIGHT s))))

(DE ED-INSERT-LINES (s ch)
  (REPLACE-AT (ED-LINES s) (ED-ROW s) (ED-INSERT-LINE s ch)))

(DE ED-INSERT (s ch)
  (MK-ED (ED-INSERT-LINES s ch) (ED-ROW s) (ADD1 (ED-COL s))))

(DE INSERT-AT (l n new)
  (COND ((ZEROP n) (CONS new l))
        ((NULL l) (CONS new NIL))
        (T (CONS (CAR l) (INSERT-AT (CDR l) (SUB1 n) new)))))

(DE ED-BACKSPACE-LINE (s)
  (APPEND (TAKE (SUB1 (ED-COL s)) (CUR-LINE s))
          (DROP (ED-COL s) (CUR-LINE s))))

(DE ED-BACKSPACE (s)
  (COND ((GREATERP (ED-COL s) 0)
         (MK-ED (REPLACE-AT (ED-LINES s) (ED-ROW s) (ED-BACKSPACE-LINE s))
                (ED-ROW s)
                (SUB1 (ED-COL s))))
        (T s)))

(DE ED-NEWLINE (s)
  (MK-ED (INSERT-AT
           (REPLACE-AT (ED-LINES s) (ED-ROW s) (ED-INSERT-LINE-LEFT s))
           (ADD1 (ED-ROW s))
           (ED-INSERT-LINE-RIGHT s))
         (ADD1 (ED-ROW s))
         0))

(DE ED-LEFT (s)
  (COND ((GREATERP (ED-COL s) 0)
         (MK-ED (ED-LINES s) (ED-ROW s) (SUB1 (ED-COL s))))
        (T s)))

(DE ED-RIGHT (s)
  (COND ((LESSP (ED-COL s) (LENGTH (CUR-LINE s)))
         (MK-ED (ED-LINES s) (ED-ROW s) (ADD1 (ED-COL s))))
        (T s)))

(DE ED-HOME (s)
  (MK-ED (ED-LINES s) (ED-ROW s) 0))

(DE ED-END (s)
  (MK-ED (ED-LINES s) (ED-ROW s) (LENGTH (CUR-LINE s))))

(DE PAD-RIGHT (s width)
  (PACK (APPEND (UNPACK s) (SPACES (DIFFERENCE width (LENGTH (UNPACK s)))))))

(DE DIGIT-CHAR (d)
  (CHAR (PLUS 48 d)))

(DE INT->CHARS (n)
  (COND ((LESSP n 10) (LIST (DIGIT-CHAR n)))
        (T (APPEND (INT->CHARS (QUOTIENT n 10))
                   (LIST (DIGIT-CHAR (REMAINDER n 10)))))))

(DE SPACES (n)
  (COND ((LESSP n 1) NIL) (T (CONS " " (SPACES (SUB1 n))))))

(DE MODELINE-MOD (b)
  (COND ((BUF-MODIFIED b) " * ") (T "   ")))

(DE MODELINE-POS (b)
  (CAT (LIST "("
             (INT->STR (ED-ROW (BUF-ED b)))
             ","
             (INT->STR (ED-COL (BUF-ED b)))
             ")")))

(DE MODELINE (bs)
  (CAT (LIST "-- "
             (BUF-NAME (BS-CURRENT bs))
             (MODELINE-MOD (BS-CURRENT bs))
             (MODELINE-POS (BS-CURRENT bs)))))

(DE CLIP-PAD (cs width)
  (PACK (APPEND cs (SPACES (DIFFERENCE width (LENGTH cs))))))

(DE CLIP-CS (cs width)
  (COND ((LESSP (LENGTH cs) width) (CLIP-PAD cs width))
        (T (PACK (TAKE width cs)))))

(DE CLIP (s width)
  (CLIP-CS (UNPACK s) width))

(DE LINE-TAIL (n lines)
  (DROP n lines))

(DE LINE-AT (n lines)
  (COND ((NULL (LINE-TAIL n lines)) "")
        (T (LINE->STR (CAR (LINE-TAIL n lines))))))

(DE VIEW-EDIT-ROWS (ed top h width)
  (COND ((LESSP h 1) NIL)
        (T (CONS (CLIP (LINE-AT top (ED-LINES ed)) width)
                 (VIEW-EDIT-ROWS ed (ADD1 top) (SUB1 h) width)))))

(DE COMPOSE-TAIL (rows modeline minibuffer)
  (COND ((NULL rows) (LIST modeline minibuffer))
        (T (CONS (CAR rows) (COMPOSE-TAIL (CDR rows) modeline minibuffer)))))

(DE COMPOSE-SCREEN (sess top height width)
  (COMPOSE-TAIL
    (VIEW-EDIT-ROWS (SS-ED sess) top (DIFFERENCE height 2) width)
    (CLIP (MODELINE (SS-BS sess)) width)
    (CLIP (MB-LINE sess) width)))

(DE MVP-IDE-ED ()
  (ED-INSERT (MK-ED (LIST (STR->LINE "A")) 0 1) "B"))

(DE MVP-IDE-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-ED))) "MAIN"))

(DE MVP-IDE-SESSION ()
  (SS-MK (MVP-IDE-BS) "" NIL NIL))

(DE MVP-IDE-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-SESSION) 0 4 8))

(DE MVP-IDE-FIRST-OK (f)
  (COND ((EQUAL (LENGTH (UNPACK (CAR f))) 2)
         (COND ((EQUAL (ASC (CAR (UNPACK (CAR f)))) 65)
                (EQUAL (ASC (CAR (CDR (UNPACK (CAR f))))) 66))
               (T NIL)))
        (T NIL)))

(DE MVP-IDE-SECOND-OK (f)
  (EQUAL (LENGTH (UNPACK (CAR (CDR f)))) 0))

(DE MVP-IDE-FRAME-OK (f)
  (COND ((NULL f) NIL)
        ((NULL (CDR f)) NIL)
        ((MVP-IDE-FIRST-OK f)
         (MVP-IDE-SECOND-OK f))
        (T NIL)))

(DE MVP-IDE-SMOKE ()
  (COND ((MVP-IDE-FRAME-OK (MVP-IDE-FRAME)) 'MVPIDEOK)
        (T 'MVPIDEFAIL)))

(DE MVP-IDE-INPUT-ED ()
  (ED-INSERT (MK-ED (LIST (STR->LINE "A")) 0 1) (PETSCII->TOKEN 66)))

(DE MVP-IDE-INPUT-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-INPUT-ED))) "MAIN"))

(DE MVP-IDE-INPUT-SESSION ()
  (SS-MK (MVP-IDE-INPUT-BS) "" NIL NIL))

(DE MVP-IDE-INPUT-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-INPUT-SESSION) 0 4 8))

(DE MVP-IDE-INPUT-SMOKE ()
  (COND ((MVP-IDE-FRAME-OK (MVP-IDE-INPUT-FRAME)) 'MVPKEYIDEOK)
        (T 'MVPKEYIDEFAIL)))

(DE MVP-IDE-BASE-ED ()
  (MK-ED (LIST (STR->LINE "A")) 0 1))

(DE MVP-IDE-BASE-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-BASE-ED))) "MAIN"))

(DE MVP-IDE-BASE-SESSION ()
  (SS-MK (MVP-IDE-BASE-BS) "" NIL NIL))

(DE MVP-IDE-EMPTY-ED ()
  (MK-ED (LIST NIL) 0 0))

(DE MVP-IDE-EMPTY-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-EMPTY-ED))) "MAIN"))

(DE MVP-IDE-EMPTY-SESSION ()
  (SS-MK (MVP-IDE-EMPTY-BS) "" NIL NIL))

(DE MVP-IDE-PRINTABLE-P (token)
  (COND ((NULL token) NIL)
        ((EQUAL (LENGTH (UNPACK token)) 1) T)
        (T NIL)))

(DE MVP-TOKEN-CODE (token n)
  (ASC (CAR (DROP n (UNPACK token)))))

(DE MVP-TOKEN-3-P (token a b c)
  (COND ((NULL token) NIL)
        ((EQUAL (LENGTH (UNPACK token)) 3)
         (MVP-TOKEN-3-CODES-P token a b c))
        (T NIL)))

(DE MVP-TOKEN-3-CODES-P (token a b c)
  (COND ((EQUAL (MVP-TOKEN-CODE token 0) a)
         (MVP-TOKEN-3-CODES2-P token b c))
        (T NIL)))

(DE MVP-TOKEN-3-CODES2-P (token b c)
  (COND ((EQUAL (MVP-TOKEN-CODE token 1) b)
         (EQUAL (MVP-TOKEN-CODE token 2) c))
        (T NIL)))

(DE MVP-TOKEN-C-A-P (token) (MVP-TOKEN-3-P token 67 45 97))
(DE MVP-TOKEN-C-E-P (token) (MVP-TOKEN-3-P token 67 45 101))
(DE MVP-TOKEN-C-R-P (token) (MVP-TOKEN-3-P token 67 45 114))
(DE MVP-TOKEN-DEL-P (token) (MVP-TOKEN-3-P token 68 69 76))
(DE MVP-TOKEN-RET-P (token) (MVP-TOKEN-3-P token 82 69 84))

(DE MVP-IDE-SET-ED (sess ed)
  (SS-MK (BS-MK (LIST (BUF-MK "MAIN" ed)) "MAIN") "" NIL NIL))

(DE MVP-IDE-SELF-INSERT (sess token)
  (MVP-IDE-SET-ED sess (ED-INSERT (SS-ED sess) token)))

(DE MVP-IDE-DISPATCH (sess token)
  (COND ((MVP-TOKEN-C-A-P token) (MVP-IDE-HOME sess))
        (T (MVP-IDE-DISPATCH2 sess token))))

(DE MVP-IDE-DISPATCH2 (sess token)
  (COND ((MVP-TOKEN-C-E-P token) (MVP-IDE-END sess))
        (T (MVP-IDE-DISPATCH3 sess token))))

(DE MVP-IDE-DISPATCH3 (sess token)
  (COND ((MVP-TOKEN-DEL-P token) (MVP-IDE-BACKSPACE sess))
        (T (MVP-IDE-DISPATCH4 sess token))))

(DE MVP-IDE-DISPATCH4 (sess token)
  (COND ((MVP-TOKEN-RET-P token) (MVP-IDE-NEWLINE sess))
        (T (MVP-IDE-DISPATCH5 sess token))))

(DE MVP-IDE-DISPATCH5 (sess token)
  (COND
        ((MVP-TOKEN-C-R-P token) (MVP-IDE-EVAL-CURRENT sess))
        ((MVP-IDE-PRINTABLE-P token) (MVP-IDE-SELF-INSERT sess token))
        (T sess)))

(DE MVP-IDE-HOME (sess)
  (MVP-IDE-SET-ED sess (ED-HOME (SS-ED sess))))

(DE MVP-IDE-END (sess)
  (MVP-IDE-SET-ED sess (ED-END (SS-ED sess))))

(DE MVP-IDE-BACKSPACE (sess)
  (MVP-IDE-SET-ED sess (ED-BACKSPACE (SS-ED sess))))

(DE MVP-IDE-NEWLINE (sess)
  (MVP-IDE-SET-ED sess (ED-NEWLINE (SS-ED sess))))

(DE MVP-IDE-DISPATCH-PETSCII (sess code)
  (MVP-IDE-DISPATCH sess (PETSCII->TOKEN code)))

(DE MVP-IDE-DISPATCH-SESSION ()
  (MVP-IDE-DISPATCH-PETSCII (MVP-IDE-BASE-SESSION) 66))

(DE MVP-IDE-DISPATCH-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-DISPATCH-SESSION) 0 4 8))

(DE MVP-IDE-DISPATCH-SMOKE ()
  (COND ((MVP-IDE-FRAME-OK (MVP-IDE-DISPATCH-FRAME)) 'MVPDISPATCHOK)
        (T 'MVPDISPATCHFAIL)))

(DE MVP-IDE-GETKEY-SESSION ()
  (MVP-IDE-DISPATCH (MVP-IDE-BASE-SESSION) (GETKEY->TOKEN)))

(DE MVP-IDE-GETKEY-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-GETKEY-SESSION) 0 4 8))

(DE MVP-IDE-GETKEY-SMOKE ()
  (COND ((MVP-IDE-FRAME-OK (MVP-IDE-GETKEY-FRAME)) 'MVPGETKEYOK)
        (T 'MVPGETKEYFAIL)))

(DE MVP-IDE-RUN-CODES (sess codes)
  (COND ((NULL codes) sess)
        (T (MVP-IDE-RUN-CODES
             (MVP-IDE-DISPATCH-PETSCII sess (CAR codes))
             (CDR codes)))))

(DE MVP-IDE-KEYMAP-SESSION ()
  (MVP-IDE-RUN-CODES (MVP-IDE-BASE-SESSION)
                     (LIST 66 1 67 20 5 13)))

(DE MVP-IDE-KEYMAP-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-KEYMAP-SESSION) 0 4 8))

(DE MVP-IDE-KEYMAP-SMOKE ()
  (COND ((MVP-IDE-FRAME-OK (MVP-IDE-KEYMAP-FRAME)) 'MVPKEYMAPOK)
        (T 'MVPKEYMAPFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE ()
  (COND ((EQUAL (LINE->STR (CUR-LINE (SS-ED (MVP-IDE-DISPATCH-SESSION)))) "AB")
         (MVP-IDE-INPUT-GATE-SMOKE2))
        (T 'MVPINPUTDISPATCHFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE2 ()
  (COND ((EQUAL (LINE->STR (CUR-LINE (SS-ED (MVP-IDE-GETKEY-SESSION)))) "AB")
         (MVP-IDE-INPUT-GATE-SMOKE3))
        (T 'MVPINPUTGETKEYFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE3 ()
  (COND ((EQUAL (LINE->STR (CAR (ED-LINES (SS-ED (MVP-IDE-KEYMAP-SESSION))))) "AB")
         (MVP-IDE-INPUT-GATE-SMOKE4))
        (T 'MVPINPUTKEYMAPFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE4 ()
  (COND ((EQUAL (LINE->STR (CAR (CDR (ED-LINES (SS-ED (MVP-IDE-KEYMAP-SESSION)))))) "")
         (MVP-IDE-INPUT-GATE-SMOKE5))
        (T 'MVPINPUTKEYMAPFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE5 ()
  (COND ((EQUAL (ED-ROW (SS-ED (MVP-IDE-KEYMAP-SESSION))) 1)
         (MVP-IDE-INPUT-GATE-SMOKE6))
        (T 'MVPINPUTKEYMAPFAIL)))

(DE MVP-IDE-INPUT-GATE-SMOKE6 ()
  (COND ((EQUAL (ED-COL (SS-ED (MVP-IDE-KEYMAP-SESSION))) 0)
         'MVPINPUTOK)
        (T 'MVPINPUTKEYMAPFAIL)))

(DE MVP-CS-CODES-P (cs codes)
  (COND ((NULL cs) (NULL codes))
        ((NULL codes) NIL)
        ((EQUAL (ASC (CAR cs)) (CAR codes))
         (MVP-CS-CODES-P (CDR cs) (CDR codes)))
        (T NIL)))

(DE MVP-FIRST-CODE-P (cs code)
  (COND ((NULL cs) NIL)
        (T (EQUAL (ASC (CAR cs)) code))))

(DE MVP-SKIP-SPACES (cs)
  (COND ((MVP-FIRST-CODE-P cs 32) (MVP-SKIP-SPACES (CDR cs)))
        (T cs)))

(DE MVP-DIGIT-CHAR-P (ch)
  (PROG (c)
    (SETQ c (ASC ch))
    (RETURN (AND (GREATERP c 47) (LESSP c 58)))))

(DE MVP-DVAL (ch)
  (DIFFERENCE (ASC ch) 48))

(DE MVP-PARSE-NAT-END (acc seen)
  (COND ((NULL seen) NIL)
        (T (CONS acc NIL))))

(DE MVP-PARSE-NAT-DIGIT (cs acc)
  (MVP-PARSE-NAT1
    (CDR cs)
    (PLUS (TIMES acc 10) (MVP-DVAL (CAR cs)))
    T))

(DE MVP-PARSE-NAT1 (cs acc seen)
  (COND ((NULL cs) (MVP-PARSE-NAT-END acc seen))
        ((MVP-DIGIT-CHAR-P (CAR cs))
         (MVP-PARSE-NAT-DIGIT cs acc))
        ((NULL seen) NIL)
        (T (CONS acc cs))))

(DE MVP-PARSE-NAT (cs)
  (MVP-PARSE-NAT1 cs 0 NIL))

(DE MVP-CHARS-MATCH (cs pat)
  (COND ((NULL pat) (CONS (QUOTE OK) cs))
        ((NULL cs) NIL)
        ((EQUAL (CAR cs) (CAR pat))
         (MVP-CHARS-MATCH (CDR cs) (CDR pat)))
        (T NIL)))

(DE MVP-OP-MATCH (cs name sym)
  (PROG (m r)
    (SETQ m (MVP-CHARS-MATCH cs (UNPACK name)))
    (COND ((NULL m) (RETURN NIL)))
    (SETQ r (CDR m))
    (COND ((MVP-FIRST-CODE-P r 32) (RETURN (CONS sym r)))
          (T (RETURN NIL)))))

(DE MVP-PARSE-OP (cs)
  (PROG (r)
    (SETQ r (MVP-OP-MATCH cs "PLUS" (QUOTE PLUS)))
    (COND ((NULL r) (RETURN (MVP-PARSE-OP2 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-OP2 (cs)
  (PROG (r)
    (SETQ r (MVP-OP-MATCH cs "DIFFERENCE" (QUOTE DIFFERENCE)))
    (COND ((NULL r) (RETURN (MVP-PARSE-OP3 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-OP3 (cs)
  (PROG (r)
    (SETQ r (MVP-OP-MATCH cs "ADD1" (QUOTE ADD1)))
    (COND ((NULL r) (RETURN (MVP-PARSE-OP4 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-OP4 (cs)
  (PROG (r)
    (SETQ r (MVP-OP-MATCH cs "SUB1" (QUOTE SUB1)))
    (COND ((NULL r) (RETURN (MVP-PARSE-OP5 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-OP5 (cs)
  (PROG (r)
    (SETQ r (MVP-OP-MATCH cs "TIMES" (QUOTE TIMES)))
    (COND ((NULL r) (RETURN (MVP-OP-MATCH cs "QUOTIENT" (QUOTE QUOTIENT))))
          (T (RETURN r)))))

(DE MVP-UNARY-OP-P (op)
  (COND ((EQ op (QUOTE ADD1)) T)
        ((EQ op (QUOTE SUB1)) T)
        (T NIL)))

(DE MVP-PARSE-CLOSE-REST (cs)
  (PROG (r)
    (SETQ r (MVP-SKIP-SPACES cs))
    (COND ((MVP-FIRST-CODE-P r 41)
           (RETURN (CONS (QUOTE OK) (MVP-SKIP-SPACES (CDR r)))))
          (T (RETURN NIL)))))

(DE MVP-CLOSE-END-P (cs)
  (PROG (r)
    (SETQ r (MVP-PARSE-CLOSE-REST cs))
    (COND ((NULL r) (RETURN NIL))
          (T (RETURN (NULL (CDR r)))))))

(DE MVP-PARSE-UNARY-FORM (op a r)
  (PROG (c)
    (SETQ c (MVP-PARSE-CLOSE-REST r))
    (COND ((NULL c) (RETURN NIL))
          (T (RETURN (CONS (LIST op a) (CDR c)))))))

(DE MVP-PARSE-BINARY-FORM (op a r)
  (PROG (p)
    (SETQ p (MVP-PARSE-EXPR r))
    (COND ((NULL p) (RETURN NIL)))
    (RETURN (MVP-PARSE-BINARY-FORM2 op a p))))

(DE MVP-PARSE-BINARY-FORM2 (op a p)
  (MVP-PARSE-BINARY-FORM3
    op
    a
    (CAR p)
    (MVP-PARSE-CLOSE-REST (CDR p))))

(DE MVP-PARSE-BINARY-FORM3 (op a b c)
  (COND ((NULL c) NIL)
        (T (CONS (LIST op a b) (CDR c)))))

(DE MVP-PARSE-ZERO-EXPR (r)
  (PROG (m)
    (SETQ m (MVP-CHARS-MATCH r (UNPACK "MVPSAVED")))
    (COND ((NULL m) (RETURN NIL)))
    (RETURN (MVP-PARSE-ZERO-EXPR2 m))))

(DE MVP-PARSE-ZERO-EXPR2 (m)
  (MVP-PARSE-ZERO-EXPR3 (MVP-PARSE-CLOSE-REST (CDR m))))

(DE MVP-PARSE-ZERO-EXPR3 (c)
  (COND ((NULL c) NIL)
        (T (CONS (LIST (QUOTE MVPSAVED)) (CDR c)))))

(DE MVP-PARSE-ZERO-FORM (r)
  (PROG (z)
    (SETQ z (MVP-PARSE-ZERO-EXPR r))
    (COND ((NULL z) (RETURN NIL)))
    (COND ((NULL (CDR z)) (RETURN (CAR z)))
          (T (RETURN NIL)))))

(DE MVP-PARSE-EXPR (l)
  (MVP-PARSE-EXPR1 (MVP-SKIP-SPACES l)))

(DE MVP-PARSE-EXPR1 (r)
  (COND ((MVP-FIRST-CODE-P r 40)
         (MVP-PARSE-FORM2 (MVP-SKIP-SPACES (CDR r))))
        (T (MVP-PARSE-NAT r))))

(DE MVP-PARSE-FORM (l)
  (MVP-PARSE-FORM-TOP (MVP-PARSE-EXPR l)))

(DE MVP-PARSE-FORM-TOP (p)
  (COND ((NULL p) NIL)
        ((NULL (MVP-SKIP-SPACES (CDR p))) (CAR p))
        (T NIL)))

(DE MVP-PARSE-FORM1 (r)
  (MVP-PARSE-EXPR1 r))

(DE MVP-PARSE-FORM2A (r)
  (PROG (op)
    (SETQ op (MVP-PARSE-OP r))
    (COND ((NULL op) (RETURN NIL)))
    (RETURN (MVP-PARSE-FORM3 op (MVP-SKIP-SPACES (CDR op))))))

(DE MVP-PARSE-FORM2 (r)
  (PROG (z)
    (SETQ z (MVP-PARSE-ZERO-EXPR r))
    (COND ((NULL z) (RETURN (MVP-PARSE-FORM2A r)))
          (T (RETURN z)))))

(DE MVP-PARSE-FORM3 (op r)
  (PROG (p)
    (SETQ p (MVP-PARSE-EXPR r))
    (COND ((NULL p) (RETURN NIL)))
    (RETURN (MVP-PARSE-FORM4 op p))))

(DE MVP-PARSE-FORM4 (op p)
  (MVP-PARSE-FORM5 (CAR op) (CAR p) (MVP-SKIP-SPACES (CDR p))))

(DE MVP-PARSE-FORM5 (op a r)
  (COND ((MVP-UNARY-OP-P op) (MVP-PARSE-UNARY-FORM op a r))
        (T (MVP-PARSE-BINARY-FORM op a r))))

(DE MVP-CMD-END-P (cs)
  (NULL (MVP-SKIP-SPACES cs)))

(DE MVP-CMD-MATCH2 (r sym)
  (COND ((MVP-CMD-END-P r) sym)
        (T NIL)))

(DE MVP-CMD-MATCH (cs name sym)
  (PROG (m r)
    (SETQ m (MVP-CHARS-MATCH cs (UNPACK name)))
    (COND ((NULL m) (RETURN NIL)))
    (SETQ r (MVP-SKIP-SPACES (CDR m)))
    (RETURN (MVP-CMD-MATCH2 r sym))))

(DE MVP-CMD-LOAD (cs)
  (PROG (m)
    (SETQ m (MVP-CHARS-MATCH cs (UNPACK "LOAD")))
    (COND ((NULL m) (RETURN NIL)))
    (RETURN (MVP-CMD-LOAD1 (CDR m)))))

(DE MVP-CMD-LOAD1 (r)
  (PROG ()
    (COND ((NULL (MVP-FIRST-CODE-P r 32)) (RETURN NIL)))
    (RETURN (MVP-CMD-LOAD2 (MVP-SKIP-SPACES r)))))

(DE MVP-CMD-LOAD2 (r)
  (COND ((MVP-CMD-END-P r) NIL)
        (T (CONS (QUOTE LOAD) (PACK r)))))

(DE MVP-CMD-SAVE (cs)
  (PROG (m)
    (SETQ m (MVP-CHARS-MATCH cs (UNPACK "SAVE")))
    (COND ((NULL m) (RETURN NIL)))
    (RETURN (MVP-CMD-SAVE1 (CDR m)))))

(DE MVP-CMD-SAVE1 (r)
  (PROG ()
    (COND ((NULL (MVP-FIRST-CODE-P r 32)) (RETURN NIL)))
    (RETURN (MVP-CMD-SAVE2 (MVP-SKIP-SPACES r)))))

(DE MVP-CMD-SAVE2 (r)
  (COND ((MVP-CMD-END-P r) NIL)
        (T (CONS (QUOTE SAVE) (PACK r)))))

(DE MVP-PARSE-CMD-NAME (cs)
  (PROG (r)
    (SETQ r (MVP-CMD-MATCH cs "CLEAR" (QUOTE CLEAR)))
    (COND ((NULL r) (RETURN (MVP-PARSE-CMD-NAME2 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-CMD-NAME2 (cs)
  (PROG (r)
    (SETQ r (MVP-CMD-MATCH cs "HELP" (QUOTE HELP)))
    (COND ((NULL r) (RETURN (MVP-PARSE-CMD-NAME3 cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-CMD-NAME3 (cs)
  (PROG (r)
    (SETQ r (MVP-CMD-LOAD cs))
    (COND ((NULL r) (RETURN (MVP-CMD-SAVE cs)))
          (T (RETURN r)))))

(DE MVP-PARSE-CMD (l)
  (PROG (r)
    (SETQ r (MVP-SKIP-SPACES l))
    (COND ((MVP-FIRST-CODE-P r 58)
           (RETURN (MVP-PARSE-CMD-NAME (MVP-SKIP-SPACES (CDR r)))))
          (T (RETURN NIL)))))

(DE MVP-IDE-COMMAND-LINE-P (l)
  (MVP-FIRST-CODE-P (MVP-SKIP-SPACES l) 58))

(DE MVP-IDE-CLEAR-COMMAND (sess)
  (SS-MK (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-EMPTY-ED))) "MAIN")
         ""
         (MB-MK "CLEARED")
         NIL))

(DE MVP-IDE-HELP-COMMAND (sess)
  (SS-MK (SS-BS sess) "" (MB-MK ":CLEAR :HELP :LOAD :SAVE") NIL))

(DE MVP-IDE-COMMAND-ERR (sess)
  (SS-MK (SS-BS sess) "" (MB-MK "CMDERR") NIL))

(DE MVP-IDE-LOAD-COMMAND (sess file)
  (PROG (r)
    (SETQ r (LOAD 8 file))
    (RETURN (SS-MK (SS-BS sess)
                   ""
                   (MB-MK (CAT (LIST "LOADED " file)))
                   NIL))))

(DE MVP-IDE-FIRST-LINE-FORM (sess)
  (MVP-IDE-LINE-FORM (CAR (ED-LINES (SS-ED sess)))))

(DE MVP-IDE-SAVE-LAMBDA (form)
  (LIST (QUOTE LAMBDA) NIL form))

(DE MVP-IDE-SAVE-RECORD (form)
  (LIST (QUOTE MVPSAVED) (QUOTE EXPR) (MVP-IDE-SAVE-LAMBDA form)))

(DE MVP-IDE-SAVE-RECORDS (form)
  (MVP-IDE-SAVE-RECORD form))

(DE MVP-IDE-SAVE-OK (sess file)
  (SS-MK (SS-BS sess) "" (MB-MK "SAVED") NIL))

(DE MVP-IDE-SAVE-SPEC (file)
  (PACK (LIST file ",U,W")))

(DE MVP-IDE-SAVE-EMIT (file form)
  (PROG (record)
    (SETQ record (MVP-IDE-SAVE-RECORDS form))
    (OPEN 1 8 2 (MVP-IDE-SAVE-SPEC file))
    (OUTPUT 1)
    (PRINT record)
    (PRINT NIL)
    (NORMAL)
    (CLOSE 1)
    (RETURN T)))

(DE MVP-IDE-SAVE-FORM (sess file form)
  (PROG ()
    (MVP-IDE-SAVE-EMIT file form)
    (RETURN (MVP-IDE-SAVE-OK sess file))))

(DE MVP-IDE-SAVE-COMMAND (sess file)
  (PROG (form)
    (SETQ form (MVP-IDE-FIRST-LINE-FORM sess))
    (COND ((NULL form) (RETURN (MVP-IDE-COMMAND-ERR sess))))
    (RETURN (MVP-IDE-SAVE-FORM sess file form))))

(DE MVP-IDE-COMMAND-SESSION (sess)
  (MVP-IDE-COMMAND-SESSION2
    sess
    (MVP-PARSE-CMD (CUR-LINE (SS-ED sess)))))

(DE MVP-IDE-COMMAND-SESSION2 (sess cmd)
  (COND ((NULL cmd) (MVP-IDE-COMMAND-ERR sess))
        ((EQ cmd (QUOTE CLEAR)) (MVP-IDE-CLEAR-COMMAND sess))
        (T (MVP-IDE-COMMAND-SESSION3 sess cmd))))

(DE MVP-IDE-COMMAND-SESSION3 (sess cmd)
  (COND ((EQ cmd (QUOTE HELP)) (MVP-IDE-HELP-COMMAND sess))
        (T (MVP-IDE-COMMAND-SESSION4 sess cmd))))

(DE MVP-IDE-COMMAND-SESSION4 (sess cmd)
  (COND ((ATOM cmd) (MVP-IDE-COMMAND-ERR sess))
        ((EQ (CAR cmd) (QUOTE LOAD)) (MVP-IDE-LOAD-COMMAND sess (CDR cmd)))
        (T (MVP-IDE-COMMAND-SESSION5 sess cmd))))

(DE MVP-IDE-COMMAND-SESSION5 (sess cmd)
  (COND ((ATOM cmd) (MVP-IDE-COMMAND-ERR sess))
        ((EQ (CAR cmd) (QUOTE SAVE)) (MVP-IDE-SAVE-COMMAND sess (CDR cmd)))
        (T (MVP-IDE-COMMAND-ERR sess))))

(DE MVP-PLUS12-CODES ()
  (LIST 40 80 76 85 83 32 49 32 50 41))

(DE MVP-PLUS12-LINE-P (l)
  (MVP-CS-CODES-P l (MVP-PLUS12-CODES)))

(DE MVP-IDE-LINE-FORM (l)
  (MVP-PARSE-FORM l))

(DE MVP-IDE-EVAL-RESULT (sess)
  (EVAL (MVP-IDE-LINE-FORM (CUR-LINE (SS-ED sess)))))

(DE MVP-IDE-EVAL-MB (result)
  (MB-MK (CAT (LIST "=> " (INT->STR result)))))

(DE MVP-IDE-EVAL-SESSION (sess)
  (MVP-IDE-EVAL-SESSION2
    sess
    (MVP-IDE-LINE-FORM (CUR-LINE (SS-ED sess)))))

(DE MVP-IDE-EVAL-SESSION2 (sess form)
  (COND ((NULL form) (MVP-IDE-EVAL-ERR sess))
        (T (MVP-IDE-EVAL-OK sess (EVAL form)))))

(DE MVP-IDE-EVAL-ERR (sess)
  (SS-MK (SS-BS sess) "" (MB-MK "ERR") NIL))

(DE MVP-IDE-EVAL-OK (sess result)
  (SS-MK (SS-BS sess) "" (MVP-IDE-EVAL-MB result) NIL))

(DE MVP-IDE-EVAL-CURRENT (sess)
  (COND ((MVP-IDE-COMMAND-LINE-P (CUR-LINE (SS-ED sess)))
         (MVP-IDE-COMMAND-SESSION sess))
        (T (MVP-IDE-EVAL-SESSION sess))))

(DE MVP-IDE-EVAL-CODES ()
  (MVP-PLUS12-CODES))

(DE MVP-IDE-EVAL-INPUT-SESSION ()
  (MVP-IDE-RUN-CODES (MVP-IDE-EMPTY-SESSION) (MVP-IDE-EVAL-CODES)))

(DE MVP-IDE-LINE-ED (s)
  (MK-ED (LIST (STR->LINE s)) 0 (LENGTH (UNPACK s))))

(DE MVP-IDE-LINE-BS (s)
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-LINE-ED s))) "MAIN"))

(DE MVP-IDE-LINE-SESSION (s)
  (SS-MK (MVP-IDE-LINE-BS s) "" NIL NIL))

(DE MVP-IDE-SAVE-ED ()
  (MK-ED (LIST (STR->LINE "(TIMES 3 4)") (STR->LINE ":SAVE MVPSAVE")) 1 13))

(DE MVP-IDE-SAVE-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-SAVE-ED))) "MAIN"))

(DE MVP-IDE-SAVE-SESSION ()
  (SS-MK (MVP-IDE-SAVE-BS) "" NIL NIL))

(DE MVP-IDE-EVAL-DIRECT-ED ()
  (MVP-IDE-LINE-ED "(PLUS 1 2)"))

(DE MVP-IDE-EVAL-DIRECT-BS ()
  (BS-MK (LIST (BUF-MK "MAIN" (MVP-IDE-EVAL-DIRECT-ED))) "MAIN"))

(DE MVP-IDE-EVAL-DIRECT-SESSION ()
  (SS-MK (MVP-IDE-EVAL-DIRECT-BS) "" NIL NIL))

(DE MVP-IDE-EVAL-DEMO-SESSION ()
  (MVP-IDE-EVAL-SESSION (MVP-IDE-EVAL-DIRECT-SESSION)))

(DE MVP-IDE-EVAL-SCREEN-SESSION ()
  (SS-MK (MVP-IDE-EVAL-DIRECT-BS) "" (MB-MK "=> 3") NIL))

(DE MVP-IDE-EVAL-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-EVAL-DEMO-SESSION) 0 4 12))

(DE MVP-IDE-EVAL-SCREEN-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-EVAL-SCREEN-SESSION) 0 4 12))

(DE MVP-IDE-EVAL-SCREEN-ROWS ()
  (LIST "(PLUS 1 2)  " "            " "-- MAIN    " "=> 3        "))

(DE MVP-IDE-EVAL-SMOKE ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT (MVP-IDE-EVAL-INPUT-SESSION)) 3)
         'MVPEVALOK)
        (T 'MVPEVALFAIL)))

(DE MVP-IDE-PARSER-SMOKE ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT
                  (MVP-IDE-LINE-SESSION "(DIFFERENCE 7 4)"))
                3)
         (MVP-IDE-PARSER-SMOKE2))
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-PARSER-SMOKE2 ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT (MVP-IDE-LINE-SESSION "(ADD1 9)")) 10)
         (MVP-IDE-PARSER-SMOKE3))
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-PARSER-SMOKE3 ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT (MVP-IDE-LINE-SESSION "(TIMES 3 4)")) 12)
         (MVP-IDE-PARSER-SMOKE4))
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-PARSER-SMOKE4 ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT (MVP-IDE-LINE-SESSION "(QUOTIENT 9 3)")) 3)
         (MVP-IDE-PARSER-SMOKE5))
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-PARSER-SMOKE5 ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT
                  (MVP-IDE-LINE-SESSION "(PLUS (TIMES 2 3) 4)"))
                10)
         (MVP-IDE-PARSER-SMOKE6))
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-PARSER-SMOKE6 ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT
                  (MVP-IDE-LINE-SESSION "(TIMES (ADD1 2) (DIFFERENCE 9 5))"))
                12)
         'MVPPARSEOK)
        (T 'MVPPARSEFAIL)))

(DE MVP-IDE-COMMAND-SMOKE ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-EVAL-CURRENT
                           (MVP-IDE-LINE-SESSION ":HELP")))
                ":CLEAR :HELP :LOAD :SAVE")
         (MVP-IDE-COMMAND-SMOKE2))
        (T 'MVPCMDSFAIL)))

(DE MVP-IDE-COMMAND-SMOKE2 ()
  (COND ((EQUAL (LINE->STR
                  (CUR-LINE
                    (SS-ED
                      (MVP-IDE-EVAL-CURRENT
                        (MVP-IDE-LINE-SESSION ":CLEAR")))))
                "")
         (MVP-IDE-COMMAND-SMOKE3))
        (T 'MVPCMDSFAIL)))

(DE MVP-IDE-COMMAND-SMOKE3 ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-EVAL-CURRENT
                           (MVP-IDE-LINE-SESSION ":NOPE")))
                "CMDERR")
         (MVP-IDE-COMMAND-SMOKE4))
        (T 'MVPCMDSFAIL)))

(DE MVP-IDE-COMMAND-SMOKE4 ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-EVAL-CURRENT
                           (MVP-IDE-SAVE-SESSION)))
                "SAVED")
         'MVPCMDSOK)
        (T 'MVPCMDSFAIL)))

(DE MVPCMDS ()
  (MVP-IDE-COMMAND-SMOKE))

(DE MVP-IDE-RENDER-EVAL ()
  (TERM-BLIT (MVP-IDE-EVAL-SCREEN-ROWS)))

(DE MVP-IDE-RENDER-EVAL-SMOKE ()
  (PROG (r)
    (SETQ r (MVP-IDE-RENDER-EVAL))
    (RETURN (MVP-IDE-RENDER-EVAL-CHECK))))

(DE MVP-IDE-RENDER-EVAL-CHECK ()
  (COND ((EQUAL (PEEK 1024) 40) (MVP-IDE-RENDER-EVAL-CHECK2))
        (T 'MVPRENDERFAIL)))

(DE MVP-IDE-RENDER-EVAL-CHECK2 ()
  (COND ((EQUAL (PEEK 1025) 16) (MVP-IDE-RENDER-EVAL-CHECK3))
        (T 'MVPRENDERFAIL)))

(DE MVP-IDE-RENDER-EVAL-CHECK3 ()
  (COND ((EQUAL (PEEK 1144) 61) (MVP-IDE-RENDER-EVAL-CHECK4))
        (T 'MVPRENDERFAIL)))

(DE MVP-IDE-RENDER-EVAL-CHECK4 ()
  (COND ((EQUAL (PEEK 1145) 62) (MVP-IDE-RENDER-EVAL-CHECK5))
        (T 'MVPRENDERFAIL)))

(DE MVP-IDE-RENDER-EVAL-CHECK5 ()
  (COND ((EQUAL (PEEK 1147) 51) 'MVPRENDEROK)
        (T 'MVPRENDERFAIL)))

(DE MVP-IDE-PLUS12-TOKENS ()
  (LIST "(" "P" "L" "U" "S" " " "1" " " "2" ")"))

(DE MVP-IDE-LOOP-TOKENS ()
  (APPEND (MVP-IDE-PLUS12-TOKENS) (LIST "C-r")))

(DE MVP-IDE-RUN-TOKENS (sess tokens)
  (COND ((NULL tokens) sess)
        (T (MVP-IDE-RUN-TOKENS
             (MVP-IDE-DISPATCH sess (CAR tokens))
             (CDR tokens)))))

(DE MVP-IDE-LOOP-SESSION ()
  (MVP-IDE-RUN-TOKENS (MVP-IDE-EMPTY-SESSION) (MVP-IDE-LOOP-TOKENS)))

(DE MVP-IDE-LOOP-FRAME ()
  (COMPOSE-SCREEN (MVP-IDE-LOOP-SESSION) 0 4 12))

(DE MVP-IDE-LOOP-SMOKE ()
  (COND ((EQUAL (MVP-IDE-EVAL-RESULT (MVP-IDE-LOOP-SESSION)) 3)
         (MVP-IDE-LOOP-SMOKE2))
        (T 'MVPLOOPFAIL)))

(DE MVP-IDE-LOOP-SMOKE2 ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-LOOP-SESSION)) "=> 3") 'MVPLOOPOK)
        (T 'MVPLOOPFAIL)))

(DE MVP-IDE-LOOP-RENDER ()
  (TERM-BLIT (MVP-IDE-LOOP-FRAME)))

(DE MVP-IDE-LOOP-RENDER-SMOKE ()
  (PROG (r)
    (SETQ r (MVP-IDE-LOOP-RENDER))
    (RETURN (MVP-IDE-RENDER-EVAL-CHECK))))

(DE MVPRF ()
  (PROG (r)
    (SETQ r (MVP-IDE-RENDER-EVAL))
    L
    (GO L)))

(DE MVP-IDE-IDLE-SOAK-SESSION ()
  (MVP-IDE-LIVE-STEP2
    (MVP-IDE-LIVE-STEP2 (MVP-IDE-EVAL-SCREEN-SESSION) NIL)
    NIL))

(DE MVP-IDE-IDLE-SOAK-SMOKE ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-IDLE-SOAK-SESSION)) "=> 3")
         'MVPIDLESOAKOK)
        (T 'MVPIDLESOAKFAIL)))

(DE MVP-IDE-IDLE-SOAK-RENDER ()
  (TERM-BLIT (COMPOSE-SCREEN (MVP-IDE-IDLE-SOAK-SESSION) 0 4 12)))

(DE MVP-IDE-IDLE-SOAK-RENDER-SMOKE ()
  (PROG (r)
    (SETQ r (MVP-IDE-IDLE-SOAK-RENDER))
    (COND ((EQ (MVP-IDE-RENDER-EVAL-CHECK) 'MVPRENDEROK)
           (RETURN 'MVPIDLERENDEROK))
          (T (RETURN 'MVPIDLERENDERFAIL)))))

(DE MVPIDLES ()
  (MVP-IDE-IDLE-SOAK-SMOKE))

(DE MVPIDLER ()
  (MVP-IDE-IDLE-SOAK-RENDER-SMOKE))

(DE MVPIF ()
  (MVPRF))

(DE MVP-K2 (a b)
  (PACK (APPEND (UNPACK a) (UNPACK b))))

(DE MVP-PET-PRINTABLEP (c)
  (AND (GREATERP c 31) (LESSP c 128)))

(DE MVP-PET-CTRLP (c)
  (AND (GREATERP c 0) (LESSP c 27)))

(DE MVP-PET-CTRL-TOKEN (c)
  (MVP-K2 "C-" (CHAR (PLUS c 96))))

(DE MVP-PETSCII->TOKEN (c)
  (COND ((NULL c) NIL)
        ((EQ c 0) NIL)
        ((EQ c 13) "RET")
        ((EQ c 20) "DEL")
        ((EQ c 32) " ")
        ((MVP-PET-CTRLP c) (MVP-PET-CTRL-TOKEN c))
        ((MVP-PET-PRINTABLEP c) (CHAR c))
        (T NIL)))

(DE MVP-GETKEY->TOKEN ()
  (MVP-PETSCII->TOKEN (GETKEY)))

(DE MVP-IDE-DRAIN-KEYS (n)
  (COND ((LESSP n 1) 'MVPLIVEKEYSOK)
        (T (MVP-IDE-DRAIN-KEYS2 n (GETKEY)))))

(DE MVP-IDE-DRAIN-KEYS2 (n c)
  (MVP-IDE-DRAIN-KEYS (SUB1 n)))

(DE MVP-IDE-LIVE-STEP (sess)
  (MVP-IDE-LIVE-STEP2 sess (MVP-GETKEY->TOKEN)))

(DE MVP-IDE-LIVE-STEP2 (sess token)
  (COND ((NULL token) sess)
        (T (MVP-IDE-LIVE-RENDER-SESSION (MVP-IDE-DISPATCH sess token)))))

(DE MVP-IDE-CURSOR-CODE ()
  160)

(DE MVP-IDE-RENDER-CURSOR (sess)
  (SCREEN-POKE
    (ED-COL (SS-ED sess))
    (ED-ROW (SS-ED sess))
    (MVP-IDE-CURSOR-CODE)))

(DE MVP-IDE-LIVE-RENDER-SESSION (sess)
  (PROG (r)
    (SETQ r (TERM-BLIT (COMPOSE-SCREEN sess 0 4 40)))
    (SETQ r (MVP-IDE-RENDER-CURSOR sess))
    (RETURN sess)))

(DE MVP-IDE-INTERACTIVE-LOOP (sess)
  (MVP-IDE-INTERACTIVE-LOOP (MVP-IDE-LIVE-STEP sess)))

(DE MVP-IDE-INTERACTIVE ()
  (MVP-IDE-INTERACTIVE-LOOP
    (MVP-IDE-LIVE-RENDER-SESSION (MVP-IDE-EMPTY-SESSION))))

(DE MVP-IDE-LIVE-LOOP (sess n)
  (COND ((LESSP n 1) sess)
        (T (MVP-IDE-LIVE-LOOP (MVP-IDE-LIVE-STEP sess) (SUB1 n)))))

(DE MVP-IDE-LIVE-SESSION ()
  (MVP-IDE-LIVE-LOOP (MVP-IDE-EMPTY-SESSION) 11))

(DE MVP-IDE-LIVE-SMOKE ()
  (COND ((EQUAL (MB-LINE (MVP-IDE-LIVE-SESSION)) "=> 3") 'MVPLIVEOK)
        (T 'MVPLIVEFAIL)))

(DE MVP-IDE-LIVE-RENDER-SMOKE ()
  (PROG (s)
    (SETQ s (MVP-IDE-LIVE-SESSION))
    (RETURN (MVP-IDE-RENDER-EVAL-CHECK))))

(DE MVPLF ()
  (PROG (k r)
    (SETQ r (MVP-IDE-RENDER-EVAL))
    (SETQ k (GETKEY))
    L
    (GO L)))
