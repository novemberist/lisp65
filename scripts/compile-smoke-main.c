/* lisp65 — Compiler-Smoke (Host, Lane K). Verifiziert bc_compile_top BYTE-EXAKT: Bytecode (Main +
 * lambda helpers and literal-table content. Read source, compile, and compare with expectations.
 * Minimal-Link (compile/mem/symbol/reader/interrupt). Exit 0 = PASS. */
#include <stdio.h>
#include <string.h>
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "reader.h"
#include "compile.h"

static int failed = 0;

#define NF 8
static bc_func FN[NF];
static uint8_t CODE[NF][160];
static obj     LIT[NF][16];

static bc_unit compile_src(const char *src) {
    const char *p = src;
    obj form = read_expr(&p);
    bc_unit u; int i;
    u.fn = FN; u.fncap = NF; u.nfn = 0; u.gensym = 0; u.err = 0;
    for (i = 0; i < NF; i++) { FN[i].code = CODE[i]; FN[i].codecap = 160; FN[i].lit = LIT[i]; FN[i].litcap = 16; }
    bc_compile_top(&u, form);
    return u;
}

static void check(const char *src, const uint8_t *want, uint16_t wantlen) {   /* Main-Bytecode */
    bc_unit u = compile_src(src);
    printf("%-26s -> ", src);
    if (u.err) { printf("UNSUPPORTED/ERR\n"); failed++; return; }
    bc_func *m = &u.fn[0];
    int ok = (m->codelen == wantlen) && (memcmp(m->code, want, wantlen) == 0);
    for (uint16_t i = 0; i < m->codelen; i++) printf("%02x ", m->code[i]);
    printf("| %s%s\n", ok ? "OK" : "MISMATCH", u.nfn > 1 ? " (+helper)" : "");
    if (!ok) failed++;
}

static void check_helper(const char *src, uint8_t hidx, uint8_t nargs, const uint8_t *want, uint16_t wantlen) {
    bc_unit u = compile_src(src);
    printf("  helper[%u] %-18s -> ", hidx, src);
    if (u.err || u.nfn <= hidx) { printf("FEHLT\n"); failed++; return; }
    bc_func *h = &u.fn[hidx];
    int ok = (h->nargs == nargs) && (h->codelen == wantlen) && (memcmp(h->code, want, wantlen) == 0);
    for (uint16_t i = 0; i < h->codelen; i++) printf("%02x ", h->code[i]);
    printf("| nargs=%u %s\n", h->nargs, ok ? "OK" : "MISMATCH");
    if (!ok) failed++;
}


static void assert_true(const char *what, int cond) {
    printf("  lit: %-32s %s\n", what, cond ? "OK" : "FAIL");
    if (!cond) failed++;
}

/* Closure analysis: check captured upvalues for helper function fnidx (count + first slot).
 * Code generation follows the opcode IDs. Compilation may still report an error here, but the
 * analysis metadata in fn.nupvals must already be populated. */
static void check_upvals(const char *src, uint8_t fnidx, uint8_t want_n, int want_slot0) {
    bc_unit u = compile_src(src);
    printf("  upvals %-38s -> ", src);
    if (u.nfn <= fnidx) { printf("fn[%u] FEHLT (nfn=%u)\n", fnidx, u.nfn); failed++; return; }
    { uint8_t got = u.fn[fnidx].nupvals;
      int ok = (got == want_n) && (want_n == 0 || u.fn[fnidx].upval_slot[0] == (uint8_t)want_slot0);
      printf("fn[%u].nupvals=%u", fnidx, got);
      if (want_n > 0) printf(" slot0=%u", u.fn[fnidx].upval_slot[0]);
      printf(" | %s\n", ok ? "OK" : "MISMATCH");
      if (!ok) failed++; }
}

int main(void) {
    mem_init();
    /* PUSHI8=1 ADD=2 RET=5 PUSHLIT=6 PUSHARG0=11 PUSHARG1=12 PUSHARGN=56 MUL=15 LESS=18 JMPREL=28
       JFALSEREL=29 NOT=42 PUSHNIL=43 CONS=51 CAR=52 LOADL=57 STOREL=58 DROP=59 CALL=60 CALLPRIM=61 */
    puts("== M1/M2 (Regression) ==");
    check("(+ 1 2)",             (const uint8_t[]){1,1, 1,2, 2, 5}, 6);
    check("(car (cons 1 2))",    (const uint8_t[]){1,1, 1,2, 51, 52, 5}, 7);
    check("(quote (1 2 3))",     (const uint8_t[]){6,0, 5}, 3);
    check("(foo 1 2)",           (const uint8_t[]){1,1, 1,2, 60,0,2, 5}, 8);
    check("(numberp 5)",         (const uint8_t[]){1,5, 61,6,1, 5}, 6);
    check("x",                   (const uint8_t[]){6,0, 61,19,1, 5}, 6);
    check("(setq g 7)",          (const uint8_t[]){6,0, 1,7, 61,20,2, 5}, 8);

    puts("== M3 (Regression) ==");
    check("(if (< 1 2) 10 20)",  (const uint8_t[]){1,1, 1,2, 18, 29,4, 1,10, 28,2, 1,20, 5}, 14);
    check("(and 1 2)",           (const uint8_t[]){1,1, 29,4, 1,2, 28,1, 43, 5}, 10);
    check("(let ((x 5)) (+ x 1))", (const uint8_t[]){1,5, 58,0, 57,0, 1,1, 2, 5}, 10);

    puts("== M3-Rest: or / cond / let* / <= >= ==");
    check("(or 1 2)",             (const uint8_t[]){1,1, 58,0, 57,0, 29,4, 57,0, 28,2, 1,2, 5}, 15);
    check("(cond ((< 1 2) 10) (t 20))", (const uint8_t[]){1,1, 1,2, 18, 29,4, 1,10, 28,2, 1,20, 5}, 14);
    check("(let* ((a 1) (b (+ a 1))) (+ a b))", (const uint8_t[]){1,1, 58,0, 57,0, 1,1, 2, 58,1, 57,0, 57,1, 2, 5}, 17);
    check("(>= 5 3)",             (const uint8_t[]){1,5, 1,3, 18, 42, 5}, 7);
    check("(<= 3 5)",             (const uint8_t[]){1,3, 1,5, 19, 42, 5}, 7);

    puts("== M-lambda: Main = PUSHLIT<Helper> ==");
    check("(lambda (x) (* x x))",  (const uint8_t[]){6,0, 5}, 3);
    check("(lambda (a b) (+ a b))",(const uint8_t[]){6,0, 5}, 3);
    check("(function car)",        (const uint8_t[]){6,0, 5}, 3);

    puts("== M-lambda: Helper-Rumpf (Params -> PUSHARG) ==");
    /* (* x x): PUSHARG0 PUSHARG0 MUL RET */
    check_helper("(lambda (x) (* x x))",   1, 1, (const uint8_t[]){11, 11, 15, 5}, 4);
    /* (+ a b): PUSHARG0 PUSHARG1 ADD RET */
    check_helper("(lambda (a b) (+ a b))", 1, 2, (const uint8_t[]){11, 12, 2, 5}, 4);
    /* (lambda (a b c d) d): d=slot3 -> PUSHARGN 3, RET */
    check_helper("(lambda (a b c d) d)",   1, 4, (const uint8_t[]){56, 3, 5}, 3);
    /* A free symbol without an outer lexical binding resolves to the global value cell. */
    check_helper("(lambda (x) y)",         1, 1, (const uint8_t[]){6,0, 61,19,1, 5}, 6);

    puts("== M-lambda: verschachtelt + Rumpf mit if/let ==");
    /* (lambda (n) (if (< n 1) 0 n)): PUSHARG0, PUSHI8 1, LESS, JFALSEREL, PUSHI8 0, JMPREL, PUSHARG0, RET */
    check_helper("(lambda (n) (if (< n 1) 0 n))", 1, 1,
                 (const uint8_t[]){11, 1,1, 18, 29,4, 1,0, 28,1, 11, 5}, 12);
    /* (lambda (x) (let ((y (* x 2))) (+ x y))): PUSHARG0,PUSHI8 2,MUL,STOREL 1,PUSHARG0,LOADL 1,ADD,RET
       (Param x=slot0; let y=slot1) */
    check_helper("(lambda (x) (let ((y (* x 2))) (+ x y)))", 1, 1,
                 (const uint8_t[]){11, 1,2, 15, 58,1, 11, 57,1, 2, 5}, 11);

    puts("== lit + Kontext-Erhalt nach lambda ==");
    { bc_unit u = compile_src("(lambda (x) (* x x))");
      assert_true("Main littab[0] == Helper-Symbol == fn[1].name",
                  u.nfn == 2 && u.fn[0].nlit == 1 && u.fn[0].lit[0] == u.fn[1].name); }
    /* The outer let scope remains intact after a lambda in the body. */
    { bc_unit u = compile_src("(let ((z 9)) (progn (lambda (q) q) z))");
      assert_true("(let ((z 9)) ... z) nach lambda -> Main endet mit LOADL 0, RET",
                  !u.err && u.fn[0].codelen >= 2 &&
                  u.fn[0].code[u.fn[0].codelen-3] == 57 /*LOADL*/ &&
                  u.fn[0].code[u.fn[0].codelen-2] == 0  &&
                  u.fn[0].code[u.fn[0].codelen-1] == 5  /*RET*/); }

    puts("== Immediate-Lambda ((lambda (p..) body) a..) == (let ((p a)..) body) ==");
    /* ((lambda (x) x) 5) == (let ((x 5)) x): PUSHI8 5, STOREL 0, LOADL 0, RET */
    check("((lambda (x) x) 5)",            (const uint8_t[]){1,5, 58,0, 57,0, 5}, 7);
    /* ((lambda (a b) (+ a b)) 3 4): Inits zuerst (aeusserer Scope), dann Rumpf */
    check("((lambda (a b) (+ a b)) 3 4)",  (const uint8_t[]){1,3, 58,0, 1,4, 58,1, 57,0, 57,1, 2, 5}, 14);

    puts("== M-closures Analyse: freie Vars -> Upvalues gesammelt ==");
    check_upvals("(lambda (n) (lambda (x) (+ x n)))",       2, 1, 0);  /* inner faengt n (aussen Slot 0) */
    check_upvals("(lambda (a) (lambda (b) (+ a b)))",       2, 1, 0);  /* inner faengt a */
    check_upvals("(lambda (n) (lambda (x) (+ n (+ x n))))", 2, 1, 0);  /* n 2x -> 1 Upvalue (dedup) */
    check_upvals("(lambda (x) (let ((y 1)) (+ x y)))",      1, 0, 0);  /* keine Capture -> 0 Upvalues */
    /* Phase 3: mehrstufig -- innerste faengt a (2 Ebenen) + b (1 Ebene) => 2 Upvalues; Mitte faengt a => 1 */
    check_upvals("(lambda (a) (lambda (b) (lambda (c) (+ a (+ b c)))))", 3, 2, 0);
    check_upvals("(lambda (a) (lambda (b) (lambda (c) (+ a (+ b c)))))", 2, 1, 0);

    puts("== M-closures Codegen (byte-exakt): OP_UPVAL im Rumpf, OP_CLOSURE an der Creation-Site ==");
    /* (lambda (n) (lambda (x) (+ x n))): fn[2]-Rumpf (+ x n) = PUSHARG0, UPVAL 0, ADD, RET */
    check_helper("(lambda (n) (lambda (x) (+ x n)))", 2, 1, (const uint8_t[]){11, 64,0, 2, 5}, 5);
    /* fn[1]-Rumpf = Creation-Site: n pushen (PUSHARG0) + CLOSURE lit=0 nuv=1 + RET */
    check_helper("(lambda (n) (lambda (x) (+ x n)))", 1, 1, (const uint8_t[]){11, 63,0,1, 5}, 5);

    puts("== M-closures Phase 2 (byte-exakt): setq einer freien Var -> OP_SETUPVAL ==");
    /* (lambda (c) (lambda () (setq c 5))): fn[2]-Rumpf (setq c 5) = PUSHI8 5, SETUPVAL 0, UPVAL 0, RET */
    check_helper("(lambda (c) (lambda () (setq c 5)))", 2, 0, (const uint8_t[]){1,5, 65,0, 64,0, 5}, 7);

    printf(failed ? "\nFAILED (%d)\n" : "\nALL PASS\n", failed);
    return failed ? 1 : 0;
}
