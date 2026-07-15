/* lisp65 — geraeteseitiger Bytecode-Compiler (Lane K)
 *
 * Uebersetzt REPL-Eingaben on-device zu Bytecode (Ziel: EIN Ausfuehrungsmodell via vm_run +
 * schneller Nutzercode; Treewalk raus am Ende). Portiert die P0-Codegen aus
 * tools/host-lisp/bytecode_p0_compiler.py; byte-exakt verifiziert (scripts/compile-smoke-main.c).
 *
 * STAND (Meilensteine):
 *   M1: Literale + binaere/unaere Arithmetik/Vergleich/cons/car/cdr/not.
 *   M2: littab + PUSHLIT (grosse Fixnums, quote) + Calls (CALL/CALLPRIM).
 *   M3: progn/if/when/unless/and + let (LOKALE Variablen, Scopes) + setq (lokal); rel8-Branch-Patching.
 *   M-lambda: `lambda`/`function` -> Helper-Code-Objekte. Der Compiler emittiert eine FAMILIE von
 *       Funktionen (bc_unit.fn[0]=Main, fn[1..]=Helper); jeder Lambda-Rumpf ist ein eigenes CodeObject,
 *       im aeusseren per PUSHLIT<Helper-Symbol> referenziert. Params -> PUSHARG0..N. KEINE Capture
 *       (P0: freie Variablen im Rumpf -> unsupported). Laufzeit-Registrierung der Helper = M6.
 *   M6-Globals: globale Wertzellen via CALLPRIM 19/20 (symbol-value/set-symbol-value).
 *   OFFEN: case, Vergleichsketten (>2), immediate lambda, &rest; M4 quasiquote;
 *          M5 Makro-Expansion (via vm_run); M6 REPL-Integration; M7 Treewalk raus.
 * err=1 fuer noch-nicht-Unterstuetztes -- nie stiller Fehlcode.
 */
#include "compile.h"
#include "vm.h"        /* OP_* Opcodes (ABI-Wahrheit) */
#include "symbol.h"    /* intern */
#include "v2_native_function_dispatch.h"

#ifdef LISP65_DIALECT_V2
#define CC_PROFILE_FLAGS CO_FLAG_STRICT_ARITY
#else
#define CC_PROFILE_FLAGS 0u
#endif

static bc_unit *cu;    /* aktuelle Uebersetzungseinheit (Helper-Alloc, gensym, err) */
static bc_func *cc;    /* aktuell emittierte Funktion (code/littab)               */

/* Scope-State der AKTUELL kompilierten Funktion (module-static; um lambda gesichert/wiederhergestellt). */
#define CC_SCOPEMAX 32
static uint8_t cc_nparams, cc_nextslot, cc_scopen, cc_scopebase;   /* resolve scannt [scopebase, scopen) */
static struct { obj name; uint8_t slot; } cc_scope[CC_SCOPEMAX];

/* M-closures (Phase 1+3): Upvalue-Tabelle PRO Verschachtelungsebene (Funktions-Stack). Erlaubt transitive
 * Capture (Var >1 Ebene aussen): jede Zwischen-Fn faengt sie mit ein. uv.src = Quelle im UNMITTELBAR aeusseren
 * Scope: via_upval=0 -> aeusseres Local (Slot, Creation-Site emit_arg), via_upval=1 -> aeussere Upvalue
 * (Index, Creation-Site OP_UPVAL). cc_lvl[L].scopebase = Start der Scope-Region von Ebene L in cc_scope[].
 * Design docs/closures-design.md. */
#define CC_FNDEPTH 8
static struct {
    uint8_t scopebase, nuv;
    struct { obj name; uint8_t src; uint8_t via_upval; } uv[BC_MAXUPVAL];
} cc_lvl[CC_FNDEPTH];
static uint8_t cc_depth;   /* aktuelle Ebene (0 = Toplevel/main) */

/* --- Bytecode-Emit --- */
static void emit1(uint8_t b)                        { if (cc->codelen < cc->codecap) cc->code[cc->codelen++] = b; else cu->err = 1; }
static void emit2(uint8_t op, uint8_t a)            { emit1(op); emit1(a); }
static void emit3(uint8_t op, uint8_t a, uint8_t b) { emit1(op); emit1(a); emit1(b); }

static uint16_t emit_branch(uint8_t opc) { emit1(opc); emit1(0); return (uint16_t)(cc->codelen - 1); }
static void patch_to(uint16_t opidx, uint16_t target) {   /* rel8-Operand @opidx -> target (vor/rueck) */
    int16_t rel = (int16_t)target - (int16_t)(opidx + 1);
    if (rel < -128 || rel > 127) { cu->err = 1; return; }
    if (opidx < cc->codelen) cc->code[opidx] = (uint8_t)(int8_t)rel;
}
static void patch_here(uint16_t opidx) { patch_to(opidx, cc->codelen); }

/* --- Symbole / Listen / Literale --- */
static uint8_t op_is(obj op, const char *name) { return op == intern(name); }
static uint16_t list_len(obj l) { uint16_t n = 0; while (IS_PTR(l) && cell_type(l) == T_CONS) { n++; l = cell_b(l); } return n; }
static uint8_t is_cons(obj o) { return IS_PTR(o) && cell_type(o) == T_CONS; }
#ifdef LISP65_DIALECT_V2
static uint8_t is_symbol(obj o) { return IS_SYMI(o) || (IS_PTR(o) && cell_type(o) == T_SYM); }
#endif

static uint8_t lit_add(obj o) {
    uint8_t i;
    for (i = 0; i < cc->nlit; i++) if (cc->lit[i] == o) return i;
    if (cc->nlit >= cc->litcap) { cu->err = 1; return 0; }
    cc->lit[cc->nlit] = o;
    return cc->nlit++;
}

/* --- Lokale Variablen --- */
static uint8_t alloc_slot(void) {
    uint8_t s;
    if (cc_nextslot >= 254) { cu->err = 1; return 0; }
    s = cc_nextslot++;
    if ((uint8_t)(cc_nextslot - cc_nparams) > cc->nlocals) cc->nlocals = (uint8_t)(cc_nextslot - cc_nparams);
    return s;
}
static int resolve_slot(obj name) {
    uint8_t i = cc_scopen;
    while (i > cc_scopebase) { i--; if (cc_scope[i].name == name) return cc_scope[i].slot; }
    return -1;   /* nicht im aktuellen Funktions-Scope -> Global; im Lambda-Rumpf bleibt Capture unsupported */
}
/* M-closures: `name` als Upvalue der Ebene L aufloesen (transitiv, Phase 3) -> Index in L; -1 = nicht
 * capturable (dann global). Dedup; jede Zwischen-Ebene faengt name mit ein (via_upval-Quelle: aeusseres
 * Local vs aeussere Upvalue). Rekursion terminiert bei L==0 (main). */
static int resolve_uv(obj name, uint8_t L) {
    uint8_t i, obase, oend; int up;
    if (L == 0) return -1;                                        /* main hat keine aeussere Fn */
    for (i = 0; i < cc_lvl[L].nuv; i++) if (cc_lvl[L].uv[i].name == name) return (int)i;   /* dedup */
    obase = cc_lvl[L-1].scopebase; oend = cc_lvl[L].scopebase;    /* Locals der aeusseren Ebene L-1 */
    for (i = oend; i > obase; ) { i--; if (cc_scope[i].name == name) {   /* aeusseres Local -> emit_arg */
        if (cc_lvl[L].nuv >= BC_MAXUPVAL) { cu->err = 1; return -1; }
        cc_lvl[L].uv[cc_lvl[L].nuv].name = name;
        cc_lvl[L].uv[cc_lvl[L].nuv].src = cc_scope[i].slot; cc_lvl[L].uv[cc_lvl[L].nuv].via_upval = 0;
        return (int)cc_lvl[L].nuv++;
    } }
    up = resolve_uv(name, (uint8_t)(L - 1));                      /* tiefer -> Upvalue von L-1 (transitiv) */
    if (up < 0) return -1;
    if (cc_lvl[L].nuv >= BC_MAXUPVAL) { cu->err = 1; return -1; }
    cc_lvl[L].uv[cc_lvl[L].nuv].name = name;
    cc_lvl[L].uv[cc_lvl[L].nuv].src = (uint8_t)up; cc_lvl[L].uv[cc_lvl[L].nuv].via_upval = 1;   /* aeussere Upvalue -> OP_UPVAL */
    return (int)cc_lvl[L].nuv++;
}
static void emit_arg(uint8_t slot) {
    if (slot >= cc_nparams)  emit2(OP_LOADL, slot);
    else if (slot == 0)      emit1(OP_PUSHARG0);
    else if (slot == 1)      emit1(OP_PUSHARG1);
    else if (slot == 2)      emit1(OP_PUSHARG2);
    else                     emit2(OP_PUSHARGN, slot);
}

/* --- Kern --- */
static void compile_expr(obj form);
static void compile_sequence(obj body);

static void push_value(obj o) {
    if (IS_FIX(o)) {
        int16_t v = FIXVAL(o);
        if (v >= -128 && v <= 127) { emit2(OP_PUSHI8, (uint8_t)(int8_t)v); return; }
        emit2(OP_PUSHLIT, lit_add(o)); return;
    }
    if (o == NIL)      { emit1(OP_PUSHNIL); return; }
    if (op_is(o, "t")) { emit1(OP_PUSHT);   return; }
    emit2(OP_PUSHLIT, lit_add(o));
}

static void compile_binary(obj args, uint8_t opc) {
    if (list_len(args) != 2) { cu->err = 1; return; }
    compile_expr(cell_a(args)); compile_expr(cell_a(cell_b(args))); emit1(opc);
}
static void compile_unary(obj args, uint8_t opc) {
    if (list_len(args) != 1) { cu->err = 1; return; }
    compile_expr(cell_a(args)); emit1(opc);
}
static void compile_args(obj args) {
    for (; is_cons(args); args = cell_b(args)) compile_expr(cell_a(args));
}
static void compile_call(obj op, obj args) {
    uint16_t n = list_len(args);
    if (n > 255) { cu->err = 1; return; }
    compile_args(args);
    emit3(OP_CALL, lit_add(op), (uint8_t)n);
}
static void compile_callprim(uint8_t pid, obj args) {
    uint16_t n = list_len(args);
    if (n > 255) { cu->err = 1; return; }
    compile_args(args);
    emit3(OP_CALLPRIM, pid, (uint8_t)n);
}

static void compile_sequence(obj body) {
    if (!is_cons(body)) { emit1(OP_PUSHNIL); return; }
    while (is_cons(cell_b(body))) { compile_expr(cell_a(body)); emit1(OP_DROP); body = cell_b(body); }
    compile_expr(cell_a(body));
}

static void compile_if(obj args) {
    uint16_t n = list_len(args), jf, jmp;
    obj test, then_f, else_f;
    if (n == 2)      { test = cell_a(args); then_f = cell_a(cell_b(args)); else_f = NIL; }
    else if (n == 3) { test = cell_a(args); then_f = cell_a(cell_b(args)); else_f = cell_a(cell_b(cell_b(args))); }
    else { cu->err = 1; return; }
    compile_expr(test);
    jf = emit_branch(OP_JFALSEREL);
    compile_expr(then_f);
    jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    compile_expr(else_f);
    patch_here(jmp);
}

static void compile_when(obj args, uint8_t negate) {
    uint16_t jf, jmp;
    if (list_len(args) < 1) { cu->err = 1; return; }
    compile_expr(cell_a(args));
    jf = emit_branch(OP_JFALSEREL);
    if (negate) emit1(OP_PUSHNIL); else compile_sequence(cell_b(args));
    jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    if (negate) compile_sequence(cell_b(args)); else emit1(OP_PUSHNIL);
    patch_here(jmp);
}

static void compile_and(obj args) {
    uint16_t n = list_len(args), jf, jmp;
    if (n == 0) { emit1(OP_PUSHT); return; }
    if (n == 1) { compile_expr(cell_a(args)); return; }
    compile_expr(cell_a(args));
    jf = emit_branch(OP_JFALSEREL);
    compile_and(cell_b(args));
    jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    emit1(OP_PUSHNIL);
    patch_here(jmp);
}

static void compile_let(obj args) {
    uint8_t saved_scopen = cc_scopen, i;
    struct { uint8_t slot; obj name; obj init; } binds[CC_SCOPEMAX];
    uint8_t nb = 0;
    obj bindings, body, b;
    if (list_len(args) < 1) { cu->err = 1; return; }
    bindings = cell_a(args); body = cell_b(args);
    for (b = bindings; is_cons(b); b = cell_b(b)) {
        obj bd = cell_a(b), name, init;
        if (is_cons(bd)) { name = cell_a(bd); init = (list_len(bd) >= 2) ? cell_a(cell_b(bd)) : NIL; }
        else { name = bd; init = NIL; }
        if (nb >= CC_SCOPEMAX) { cu->err = 1; return; }
        binds[nb].slot = alloc_slot(); binds[nb].name = name; binds[nb].init = init; nb++;
    }
    for (i = 0; i < nb; i++) { compile_expr(binds[i].init); emit2(OP_STOREL, binds[i].slot); }
    for (i = 0; i < nb; i++) {
        if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
        cc_scope[cc_scopen].name = binds[i].name; cc_scope[cc_scopen].slot = binds[i].slot; cc_scopen++;
    }
    compile_sequence(body);
    cc_scopen = saved_scopen;
}

static void compile_setq(obj args) {
    uint16_t n = list_len(args), pair = 0, pairs;
    obj a;
    int slot;
    if (n == 0) { emit1(OP_PUSHNIL); return; }
    if (n % 2 != 0) { cu->err = 1; return; }
    pairs = n / 2;
    for (a = args; is_cons(a); a = cell_b(cell_b(a))) {
        obj name = cell_a(a), value = cell_a(cell_b(a));
        slot = resolve_slot(name);
        if (slot >= 0) {
            compile_expr(value);
            emit2(OP_STOREL, (uint8_t)slot);
            emit2(OP_LOADL, (uint8_t)slot);             /* setq liefert den gesetzten Wert */
        } else if ((slot = resolve_uv(name, cc_depth)) >= 0) {   /* setq einer freien Var -> Upvalue (Phase 2) */
            compile_expr(value);
            emit2(OP_SETUPVAL, (uint8_t)slot);          /* Wert poppen + Upvalue i schreiben (per-Closure-mutierbar) */
            emit2(OP_UPVAL, (uint8_t)slot);             /* setq liefert den gesetzten Wert (wie STOREL/LOADL) */
        } else {
            emit2(OP_PUSHLIT, lit_add(name));
            compile_expr(value);
            emit3(OP_CALLPRIM, 20, 2);                  /* set-symbol-value */
        }
        pair++;
        if (pair < pairs) emit1(OP_DROP);
    }
}

/* or: () -> nil; (x) -> x; (x . rest) -> (let ((tmp x)) (if tmp tmp (or rest))), Temp-Slot,
 * byte-exakt wie die Host-Lowering. */
static void compile_or(obj args) {
    uint16_t n = list_len(args), jf, jmp;
    uint8_t tmp;
    if (n == 0) { emit1(OP_PUSHNIL); return; }
    if (n == 1) { compile_expr(cell_a(args)); return; }
    tmp = alloc_slot();
    compile_expr(cell_a(args)); emit2(OP_STOREL, tmp);
    emit2(OP_LOADL, tmp); jf = emit_branch(OP_JFALSEREL);
    emit2(OP_LOADL, tmp); jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    compile_or(cell_b(args));
    patch_here(jmp);
}

/* cond: (t/otherwise . body) -> progn body (finaler else); (test) einzeln -> or-Semantik;
 * (test . body) -> (if test (progn body) (cond rest)). Byte-exakt wie lower_cond. */
static void compile_cond(obj clauses) {
    obj clause, test, body;
    uint16_t jf, jmp;
    uint8_t tmp;
    if (!is_cons(clauses)) { emit1(OP_PUSHNIL); return; }
    clause = cell_a(clauses);
    if (!is_cons(clause)) { cu->err = 1; return; }
    test = cell_a(clause); body = cell_b(clause);
    if (op_is(test, "t") || op_is(test, "otherwise")) {
        if (is_cons(body)) compile_sequence(body); else emit1(OP_PUSHT);
        return;
    }
    if (!is_cons(body)) {                                 /* (test) -> (or test (cond rest)) */
        tmp = alloc_slot();
        compile_expr(test); emit2(OP_STOREL, tmp);
        emit2(OP_LOADL, tmp); jf = emit_branch(OP_JFALSEREL);
        emit2(OP_LOADL, tmp); jmp = emit_branch(OP_JMPREL);
        patch_here(jf); compile_cond(cell_b(clauses)); patch_here(jmp);
        return;
    }
    compile_expr(test);
    jf = emit_branch(OP_JFALSEREL);
    compile_sequence(body);
    jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    compile_cond(cell_b(clauses));
    patch_here(jmp);
}

/* let*: sequentiell binden -- jeder init sieht die vorherigen Bindungen (== geschachtelte lets). */
static void compile_letstar(obj args) {
    uint8_t saved_scopen = cc_scopen;
    obj bindings, body, b;
    if (list_len(args) < 1) { cu->err = 1; return; }
    bindings = cell_a(args); body = cell_b(args);
    for (b = bindings; is_cons(b); b = cell_b(b)) {
        obj bd = cell_a(b), name, init; uint8_t slot;
        if (is_cons(bd)) { name = cell_a(bd); init = (list_len(bd) >= 2) ? cell_a(cell_b(bd)) : NIL; }
        else { name = bd; init = NIL; }
        slot = alloc_slot();
        compile_expr(init);                              /* sieht die bereits gebundenen (Scope aktiv) */
        emit2(OP_STOREL, slot);
        if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
        cc_scope[cc_scopen].name = name; cc_scope[cc_scopen].slot = slot; cc_scopen++;
    }
    compile_sequence(body);
    cc_scopen = saved_scopen;
}

/* <= (negopc=GREATER) / >= (negopc=LESS): 2 Args -> (not (negop a b)). Ketten (>2) noch offen. */
static void compile_cmpchain(obj args, uint8_t negopc) {
    uint16_t n = list_len(args);
    if (n <= 1) { emit1(OP_PUSHT); return; }
    if (n != 2) { cu->err = 1; return; }                 /* Vergleichsketten (>2 Args) -> spaeter */
    compile_expr(cell_a(args));
    compile_expr(cell_a(cell_b(args)));
    emit1(negopc); emit1(OP_NOT);
}

/* Body einer Schleife: jede Form kompilieren + DROP (Statement-Semantik, kein Stack-Wachstum). */
static void compile_loop_body(obj body) {
    for (; is_cons(body); body = cell_b(body)) { compile_expr(cell_a(body)); emit1(OP_DROP); }
}

/* dotimes (var count [result]): var 0..count-1, Body je Iteration; Wert = result (var=count danach). */
static void compile_dotimes(obj args) {
    obj spec, var, count, result, body;
    uint8_t limslot, varslot, saved = cc_scopen;
    uint16_t loop_start, exit_op, back_op;
    if (list_len(args) < 1) { cu->err = 1; return; }
    spec = cell_a(args); body = cell_b(args);
    if (!is_cons(spec) || list_len(spec) < 2) { cu->err = 1; return; }
    var = cell_a(spec); count = cell_a(cell_b(spec));
    result = (list_len(spec) >= 3) ? cell_a(cell_b(cell_b(spec))) : NIL;
    limslot = alloc_slot(); varslot = alloc_slot();
    compile_expr(count); emit2(OP_STOREL, limslot);
    emit2(OP_PUSHI8, 0);  emit2(OP_STOREL, varslot);
    if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
    cc_scope[cc_scopen].name = var; cc_scope[cc_scopen].slot = varslot; cc_scopen++;
    loop_start = cc->codelen;
    emit2(OP_LOADL, varslot); emit2(OP_LOADL, limslot); emit1(OP_LESS);
    exit_op = emit_branch(OP_JFALSEREL);
    compile_loop_body(body);
    emit2(OP_LOADL, varslot); emit2(OP_PUSHI8, 1); emit1(OP_ADD); emit2(OP_STOREL, varslot);
    back_op = emit_branch(OP_JMPREL); patch_to(back_op, loop_start);
    patch_here(exit_op);
    emit2(OP_LOADL, limslot); emit2(OP_STOREL, varslot);   /* var = count nach der Schleife */
    compile_expr(result);
    cc_scopen = saved;
}

/* dolist (var list [result]): var laeuft ueber die Listenelemente; Wert = result (var=nil danach). */
static void compile_dolist(obj args) {
    obj spec, var, listf, result, body;
    uint8_t lslot, varslot, saved = cc_scopen;
    uint16_t loop_start, exit_op, back_op;
    if (list_len(args) < 1) { cu->err = 1; return; }
    spec = cell_a(args); body = cell_b(args);
    if (!is_cons(spec) || list_len(spec) < 2) { cu->err = 1; return; }
    var = cell_a(spec); listf = cell_a(cell_b(spec));
    result = (list_len(spec) >= 3) ? cell_a(cell_b(cell_b(spec))) : NIL;
    lslot = alloc_slot(); varslot = alloc_slot();
    compile_expr(listf); emit2(OP_STOREL, lslot);
    if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
    cc_scope[cc_scopen].name = var; cc_scope[cc_scopen].slot = varslot; cc_scopen++;
    loop_start = cc->codelen;
    emit2(OP_LOADL, lslot); emit1(OP_CONSP);
    exit_op = emit_branch(OP_JFALSEREL);
    emit2(OP_LOADL, lslot); emit1(OP_CAR); emit2(OP_STOREL, varslot);
    compile_loop_body(body);
    emit2(OP_LOADL, lslot); emit1(OP_CDR); emit2(OP_STOREL, lslot);
    back_op = emit_branch(OP_JMPREL); patch_to(back_op, loop_start);
    patch_here(exit_op);
    emit1(OP_PUSHNIL); emit2(OP_STOREL, varslot);
    compile_expr(result);
    cc_scopen = saved;
}

/* case-Schluesseltest: (eql tmp <key>) -- key ist implizit gequotet (Reader-obj direkt). */
static void compile_case_test(uint8_t tmp, obj keyspec) {
    if (is_cons(keyspec)) { cu->err = 1; return; }    /* Schluessel-LISTE ((1 2) ..) -> spaeter */
    emit2(OP_LOADL, tmp);
    push_value(keyspec);
    emit1(OP_EQL);
}
/* case-Klauseln: (t/otherwise . body) finaler else; sonst (if (eql tmp key) (progn body) rest). */
static void compile_case_clauses(uint8_t tmp, obj clauses) {
    obj clause, keyspec, body;
    uint16_t jf, jmp;
    if (!is_cons(clauses)) { emit1(OP_PUSHNIL); return; }
    clause = cell_a(clauses);
    if (!is_cons(clause)) { cu->err = 1; return; }
    keyspec = cell_a(clause); body = cell_b(clause);
    if (op_is(keyspec, "t") || op_is(keyspec, "otherwise")) { compile_sequence(body); return; }
    compile_case_test(tmp, keyspec);
    jf = emit_branch(OP_JFALSEREL);
    compile_sequence(body);
    jmp = emit_branch(OP_JMPREL);
    patch_here(jf);
    compile_case_clauses(tmp, cell_b(clauses));
    patch_here(jmp);
}
/* case: Schluessel EINMAL in einen Temp-Slot, dann eql-Kette (== lower_case, aber ohne Rebuild). */
static void compile_case(obj args) {
    uint8_t tmp, saved = cc_scopen;
    if (list_len(args) < 1) { cu->err = 1; return; }
    tmp = alloc_slot();
    compile_expr(cell_a(args)); emit2(OP_STOREL, tmp);
    compile_case_clauses(tmp, cell_b(args));
    cc_scopen = saved;
}

/* Eindeutiger Helper-Name "__L<n>" (interniert, damit CALL/Registrierung ihn finden; kein stdio). */
static obj gen_helper_name(void) {
    char buf[8], tmp[6]; uint16_t n = cu->gensym++; uint8_t i = 0, j = 0;
    buf[i++] = '_'; buf[i++] = 'L';
    if (n == 0) tmp[j++] = '0';
    while (n) { tmp[j++] = (char)('0' + (n % 10)); n /= 10; }
    while (j) buf[i++] = tmp[--j];
    buf[i] = 0;
    return intern(buf);
}

/* Params (inkl. &rest) als Slots 0.. im AKTUELLEN Scope (cc/cc_scopen) binden; setzt cc_nparams/
 * cc_nextslot + cc->nargs/nlocals/flags. Gemeinsam von compile_lambda_helper + bc_compile_defun
 * (kein Duplikat -> weniger .text). Voraussetzung: cc_scopen/cc_scopebase sind vom Aufrufer gesetzt. */
static void cc_bind_params(obj params) {
#ifdef LISP65_DIALECT_V2
    obj p = params, restname = NIL;
    uint8_t np = 0, optional = 0, state = 0; /* required, optional, rest */
    while (is_cons(p)) {
        obj pn = cell_a(p);
        p = cell_b(p);
        if (op_is(pn, "&optional")) {
            if (state != 0) { cu->err = 1; break; }
            state = 1;
            continue;
        }
        if (op_is(pn, "&rest")) {
            if (state == 2 || !is_cons(p) || cell_b(p) != NIL) { cu->err = 1; break; }
            restname = cell_a(p);
            if (!is_symbol(restname) || op_is(restname, "&optional") || op_is(restname, "&rest"))
                cu->err = 1;
            p = NIL;
            state = 2;
            break;
        }
        if (!is_symbol(pn) || state == 2 || cc_scopen >= CC_SCOPEMAX) {
            cu->err = 1;
            break;
        }
        cc_scope[cc_scopen].name = pn;
        cc_scope[cc_scopen].slot = np;
        cc_scopen++;
        np++;
        if (state == 1) optional++;
    }
    if (p != NIL || optional > 63u) cu->err = 1;
    cc_nparams = np;
    cc_nextslot = np;
    cc->nargs = np;
    cc->flags |= (uint8_t)(optional << CO_FLAG_OPTIONAL_SHIFT);
    if (restname != NIL && !cu->err) {
        if (cc_scopen >= CC_SCOPEMAX) cu->err = 1;
        else {
            cc_scope[cc_scopen].name = restname;
            cc_scope[cc_scopen].slot = np;
            cc_scopen++;
            cc_nextslot = (uint8_t)(np + 1);
            cc->nlocals = 1;
            cc->flags |= CO_FLAG_REST;
        }
    }
#else
    obj p, restname = NIL; uint8_t np = 0, sawrest = 0;
    for (p = params; is_cons(p); p = cell_b(p)) {
        obj pn = cell_a(p);
        if (op_is(pn, "&rest")) { sawrest = 1; continue; }
        if (sawrest) { restname = pn; break; }
        if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; break; }
        cc_scope[cc_scopen].name = pn; cc_scope[cc_scopen].slot = np; cc_scopen++; np++;
    }
    cc_nparams = np; cc_nextslot = np; cc->nargs = np;
    if (restname != NIL) {
        if (cc_scopen >= CC_SCOPEMAX) cu->err = 1;
        else { cc_scope[cc_scopen].name = restname; cc_scope[cc_scopen].slot = np;
               cc_scopen++; cc_nextslot = (uint8_t)(np + 1); cc->nlocals = 1;
               cc->flags |= CO_FLAG_REST; }
    } else if (sawrest) cu->err = 1;
#endif
}

/* lambda: Rumpf als eigenes Helper-CodeObject kompilieren (frischer Scope = Params), Namen in fn[k].name;
 * im aeusseren PUSHLIT<Name>. Rueckgabe: das Helper-Symbol (fuer `function`). */
static obj compile_lambda_helper(obj form) {
    bc_func *outer = cc;
    uint8_t s_nparams = cc_nparams, s_nextslot = cc_nextslot, s_scopen = cc_scopen, s_scopebase = cc_scopebase;
    uint8_t s_depth = cc_depth;                                  /* M-closures: Ebene sichern */
    obj params, body, name;
    if (list_len(form) < 3) { cu->err = 1; return NIL; }         /* (lambda (params) body...) */
    if (cu->nfn >= cu->fncap) { cu->err = 1; return NIL; }
    cc = &cu->fn[cu->nfn++];
    name = gen_helper_name();
    cc->name = name; cc->codelen = 0; cc->nlit = 0; cc->nlocals = 0;
    cc->flags = CC_PROFILE_FLAGS;
    params = cell_a(cell_b(form)); body = cell_b(cell_b(form));
    /* frischer Scope OHNE Capture: Params ab cc_scopen; cc_scopebase blendet aeussere aus.
     * &rest: der Param DANACH ist der Rest-Slot (Local @ nparams, flags Bit0 -> VM sammelt Extra-Args). */
    cc_scopebase = cc_scopen; cc_nextslot = 0; cc_nparams = 0;
    if ((uint8_t)(cc_depth + 1) >= CC_FNDEPTH) cu->err = 1;      /* Verschachtelung zu tief */
    else { cc_depth++; cc_lvl[cc_depth].scopebase = cc_scopen; cc_lvl[cc_depth].nuv = 0; }  /* M-closures: neue Ebene */
    cc->nupvals = 0;
    cc_bind_params(params);
    compile_sequence(body);
    emit1(OP_RET);
    /* M-closures: Upvalues dieser Ebene -> Helfer-Fn + Creation-Site im aeusseren Scope. */
    { uint8_t k, cd = cc_depth, nuv = cc_lvl[cd].nuv;
      struct { uint8_t src, via; } uvs[BC_MAXUPVAL];
      cc->nupvals = nuv;
      for (k = 0; k < nuv; k++) { cc->upval_slot[k] = cc_lvl[cd].uv[k].src; uvs[k].src = cc_lvl[cd].uv[k].src; uvs[k].via = cc_lvl[cd].uv[k].via_upval; }
      cc = outer; cc_nparams = s_nparams; cc_nextslot = s_nextslot; cc_scopen = s_scopen; cc_scopebase = s_scopebase;
      cc_depth = s_depth;                                        /* M-closures: Ebene wiederherstellen */
      /* Creation-Site im aeusseren Scope: Nicht-Closure -> PUSHLIT (Fast-Path). Closure -> je Upvalue den Wert
       * pushen (via=0: aeusseres Local -> emit_arg; via=1: aeussere Upvalue -> OP_UPVAL) + OP_CLOSURE. */
      if (nuv == 0) emit2(OP_PUSHLIT, lit_add(name));
      else {
          for (k = 0; k < nuv; k++) { if (uvs[k].via) emit2(OP_UPVAL, uvs[k].src); else emit_arg(uvs[k].src); }
          emit3(OP_CLOSURE, lit_add(name), nuv);
      }
    }
    return name;
}

static const struct { const char *name; uint8_t id; } PRIMS[] = {
#ifndef LISP65_DIALECT_V2
    {"stringp",0},
    {"string->list",1},{"list->string",2},
    {"string-length",3},{"string-ref",4},
    {"symbolp",5},{"numberp",6},{"apply",7},{"funcall",8},{"screen-size",9},{"screen-clear",10},
    {"screen-put-char",11},{"screen-write-string",12},{"read-key",13},{"poll-key",14},
    {"%disk-read-sector",15},{"%disk-byte",16},{"%disk-load-file",17},{"%disk-load-lib",18},
    {"symbol-value",19},{"set-symbol-value",20},
    {"%disk-poke",21},{"%disk-write-sector",22},
#else
#define V2_ACTIVE_PRIM_ROW(name, id) {name, id},
    LISP65_V2_CALLPRIM_ACTIVE_ROWS(V2_ACTIVE_PRIM_ROW)
#undef V2_ACTIVE_PRIM_ROW
#endif
};

/* Immediate-Lambda ((lambda (p1 p2 ...) . body) a1 a2 ...) == (let ((p1 a1) (p2 a2) ...) . body):
 * Args in Params-Slots binden, Rumpf laufen. Wie compile_let, nur kommen die Namen aus den
 * Lambda-Params und die Inits aus den Call-Args (Lockstep, ohne Bindings-Liste zu konsen). Der
 * Rumpf hat -- anders als der Helper-Pfad -- korrekten lexikalischen Zugriff auf aeussere Locals.
 * Nur feste Parameter (kein &rest): deckt den Prelude-Fall (append) + allgemeine Immediate-Lambdas ab. */
static void compile_immediate_lambda(obj lam, obj callargs) {
    uint8_t saved_scopen = cc_scopen, i, nb = 0;
    struct { uint8_t slot; obj name; obj init; } binds[CC_SCOPEMAX];
    obj params, body, pp, aa;
    if (list_len(cell_b(lam)) < 1) { cu->err = 1; return; }      /* (lambda PARAMS . body) */
    params = cell_a(cell_b(lam));
    body   = cell_b(cell_b(lam));
#ifdef LISP65_DIALECT_V2
    {
        obj names[CC_SCOPEMAX], restname = NIL, tail;
        uint8_t required = 0, optional = 0, state = 0, nformal = 0;
        uint8_t actual = 0, nextra, restslot = 0;
        for (pp = params; is_cons(pp); pp = cell_b(pp)) {
            obj name = cell_a(pp);
            if (op_is(name, "&optional")) {
                if (state != 0) { cu->err = 1; return; }
                state = 1;
                continue;
            }
            if (op_is(name, "&rest")) {
                pp = cell_b(pp);
                if (state == 2 || !is_cons(pp) || cell_b(pp) != NIL) { cu->err = 1; return; }
                restname = cell_a(pp);
                if (!is_symbol(restname) || op_is(restname, "&optional") || op_is(restname, "&rest"))
                    cu->err = 1;
                pp = NIL;
                state = 2;
                break;
            }
            if (!is_symbol(name) || state == 2 || nformal >= CC_SCOPEMAX) { cu->err = 1; return; }
            names[nformal++] = name;
            if (state == 0) required++; else optional++;
        }
        if (pp != NIL || cu->err || optional > 63u) { cu->err = 1; return; }
        for (tail = callargs; is_cons(tail); tail = cell_b(tail)) {
            if (actual == 255u) { cu->err = 1; return; }
            actual++;
        }
        if (tail != NIL || actual < required || (restname == NIL && actual > nformal)) {
            cu->err = 1;
            return;
        }
        nextra = actual > nformal ? (uint8_t)(actual - nformal) : 0;
        if ((uint16_t)nformal + nextra + (restname != NIL ? 1u : 0u) > CC_SCOPEMAX) {
            cu->err = 1;
            return;
        }
        aa = callargs;
        for (i = 0; i < nformal; i++) {
            binds[nb].slot = alloc_slot();
            binds[nb].name = names[i];
            binds[nb].init = is_cons(aa) ? cell_a(aa) : NIL;
            if (is_cons(aa)) aa = cell_b(aa);
            nb++;
        }
        for (i = 0; i < nextra; i++) {
            binds[nb].slot = alloc_slot();
            binds[nb].name = NIL;                  /* nur temporaer fuer Restlisten-Aufbau */
            binds[nb].init = cell_a(aa);
            aa = cell_b(aa);
            nb++;
        }
        if (restname != NIL) restslot = alloc_slot();
        for (i = 0; i < nb; i++) {
            compile_expr(binds[i].init);
            emit2(OP_STOREL, binds[i].slot);
        }
        if (restname != NIL) {
            emit1(OP_PUSHNIL);
            emit2(OP_STOREL, restslot);
            for (i = nextra; i > 0; i--) {
                emit2(OP_LOADL, binds[nformal + i - 1].slot);
                emit2(OP_LOADL, restslot);
                emit1(OP_CONS);
                emit2(OP_STOREL, restslot);
            }
        }
        for (i = 0; i < nformal; i++) {
            if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
            cc_scope[cc_scopen].name = binds[i].name;
            cc_scope[cc_scopen].slot = binds[i].slot;
            cc_scopen++;
        }
        if (restname != NIL) {
            if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
            cc_scope[cc_scopen].name = restname;
            cc_scope[cc_scopen].slot = restslot;
            cc_scopen++;
        }
        compile_sequence(body);
        cc_scopen = saved_scopen;
        return;
    }
#else
    for (pp = params, aa = callargs; is_cons(pp); pp = cell_b(pp), aa = is_cons(aa) ? cell_b(aa) : NIL) {
        obj name = cell_a(pp), init = is_cons(aa) ? cell_a(aa) : NIL;
        if (op_is(name, "&rest")) { cu->err = 1; return; }        /* &rest im Immediate-Lambda: nicht unterstuetzt */
        if (nb >= CC_SCOPEMAX) { cu->err = 1; return; }
        binds[nb].slot = alloc_slot(); binds[nb].name = name; binds[nb].init = init; nb++;
    }
    for (i = 0; i < nb; i++) { compile_expr(binds[i].init); emit2(OP_STOREL, binds[i].slot); }  /* Inits im aeusseren Scope */
    for (i = 0; i < nb; i++) {                                    /* dann Params sichtbar machen */
        if (cc_scopen >= CC_SCOPEMAX) { cu->err = 1; return; }
        cc_scope[cc_scopen].name = binds[i].name; cc_scope[cc_scopen].slot = binds[i].slot; cc_scopen++;
    }
    compile_sequence(body);
    cc_scopen = saved_scopen;
#endif
}

int bc_is_special_form(obj sym) {
    static const char *sf[] = { "if","when","unless","and","or","cond","case","let","let*",
                                "progn","setq","quote","lambda","function","dotimes","dolist" };
    uint8_t i;
    for (i = 0; i < (uint8_t)(sizeof(sf) / sizeof(sf[0])); i++)
        if (op_is(sym, sf[i])) return 1;
    return 0;
}

static void compile_expr(obj form) {
    if (IS_FIX(form))                       { push_value(form); return; }
    if (form == NIL || op_is(form, "nil"))  { emit1(OP_PUSHNIL); return; }
    if (op_is(form, "t"))                   { emit1(OP_PUSHT);   return; }

    if (is_cons(form)) {
        obj op = cell_a(form), args = cell_b(form);
        uint8_t i;
        if (is_cons(op)) {                              /* ((lambda ..) ..) immediate-Lambda -> wie let */
            if (op_is(cell_a(op), "lambda")) compile_immediate_lambda(op, args);
            else cu->err = 1;
            return;
        }
        if      (op_is(op, "+"))                        compile_binary(args, OP_ADD);
        else if (op_is(op, "-"))                        compile_binary(args, OP_SUB);
        else if (op_is(op, "*"))                        compile_binary(args, OP_MUL);
        else if (op_is(op, "/"))                        compile_binary(args, OP_DIV);
        else if (op_is(op, "<"))                        compile_binary(args, OP_LESS);
        else if (op_is(op, ">"))                        compile_binary(args, OP_GREATER);
        else if (op_is(op, "=") || op_is(op, "eq"))     compile_binary(args, OP_EQ);
        else if (op_is(op, "eql"))                      compile_binary(args, OP_EQL);
#ifndef LISP65_DIALECT_V2
        else if (op_is(op, "remainder"))                compile_binary(args, OP_REMAINDER);
#endif
        else if (op_is(op, "mod"))                      compile_binary(args, OP_MOD);
        else if (op_is(op, "cons"))                     compile_binary(args, OP_CONS);
        else if (op_is(op, "car"))                      compile_unary(args, OP_CAR);
        else if (op_is(op, "cdr"))                      compile_unary(args, OP_CDR);
        else if (op_is(op, "consp"))                    compile_unary(args, OP_CONSP);
        else if (op_is(op, "not") || op_is(op, "null")) compile_unary(args, OP_NOT);
        else if (op_is(op, "quote"))    { if (list_len(args) != 1) { cu->err = 1; return; } push_value(cell_a(args)); }
        else if (op_is(op, "progn"))    compile_sequence(args);
        else if (op_is(op, "if"))       compile_if(args);
        else if (op_is(op, "when"))     compile_when(args, 0);
        else if (op_is(op, "unless"))   compile_when(args, 1);
        else if (op_is(op, "and"))      compile_and(args);
        else if (op_is(op, "let"))      compile_let(args);
        else if (op_is(op, "let*"))     compile_letstar(args);
        else if (op_is(op, "setq"))     compile_setq(args);
        else if (op_is(op, "or"))       compile_or(args);
        else if (op_is(op, "cond"))     compile_cond(args);
        else if (op_is(op, "dotimes"))  compile_dotimes(args);
        else if (op_is(op, "dolist"))   compile_dolist(args);
        else if (op_is(op, "case"))     compile_case(args);
        else if (op_is(op, "<="))       compile_cmpchain(args, OP_GREATER);
        else if (op_is(op, ">="))       compile_cmpchain(args, OP_LESS);
        else if (op_is(op, "lambda"))   compile_lambda_helper(form);   /* emittiert Creation-Site selbst (PUSHLIT/OP_CLOSURE) */
        else if (op_is(op, "function")) {                /* (function foo) | (function (lambda ..)) */
            obj t;
            if (list_len(args) != 1) { cu->err = 1; return; }
            t = cell_a(args);
            if (is_cons(t) && op_is(cell_a(t), "lambda")) compile_lambda_helper(t);   /* Creation-Site intern */
            else emit2(OP_PUSHLIT, lit_add(t));          /* benannte Funktion: Symbol pushen */
        }
        else {
            for (i = 0; i < (uint8_t)(sizeof(PRIMS) / sizeof(PRIMS[0])); i++)
                if (op == intern(PRIMS[i].name)) { compile_callprim(PRIMS[i].id, args); return; }
            compile_call(op, args);
        }
        return;
    }

    /* Nicht-Symbol-Atome (String-Literale u. ae.) sind LITERALE, keine Variablen — sonst
     * wuerde "abc" als Global-Read (CALLPRIM 19) kompiliert -> TYPEERROR zur Laufzeit.
     * (Befund der Aequivalenz-Suite 2026-07-05: Treewalk ok, Compiler !error.) */
    if (IS_PTR(form) && cell_type(form) != T_SYM) { push_value(form); return; }

    {   /* blankes Atom: lokal -> laden; freie Var (ein- ODER mehrstufig) -> Upvalue (resolve_uv); sonst global. */
        int slot = resolve_slot(form), uvi;
        if (slot >= 0) emit_arg((uint8_t)slot);
        else if ((uvi = resolve_uv(form, cc_depth)) >= 0) emit2(OP_UPVAL, (uint8_t)uvi);
        else { emit2(OP_PUSHLIT, lit_add(form)); emit3(OP_CALLPRIM, 19, 1); }
    }
}

void bc_compile_top(bc_unit *u, obj form) {
    cu = u; u->nfn = 0; u->err = 0;
    if (u->fncap < 1) { u->err = 1; return; }
    cc = &u->fn[u->nfn++];               /* fn[0] = Main */
    cc->name = NIL; cc->codelen = 0; cc->nlit = 0; cc->nargs = 0; cc->nlocals = 0;
    cc->flags = CC_PROFILE_FLAGS; cc->nupvals = 0;
    cc_nparams = 0; cc_nextslot = 0; cc_scopen = 0; cc_scopebase = 0;
    cc_depth = 0; cc_lvl[0].scopebase = 0; cc_lvl[0].nuv = 0;   /* M-closures: Ebenen-Stack zuruecksetzen */
    compile_expr(form);
    emit1(OP_RET);
}

/* Der gepinnte Defun-Codegen beendet den THEN-Zweig eines tail-positionierten IF direkt.
 * Dadurch braucht der Zweig keinen Sprung ueber ELSE; der abschliessende RET unten gehoert
 * ausschliesslich zum ELSE-Pfad. Lambda-Helper behalten vorerst ihren historischen Codegen. */
static void compile_defun_tail_expr(obj form) {
    obj args, test, then_f, else_f;
    uint16_t n, jf;
    if (!is_cons(form) || !op_is(cell_a(form), "if")) {
        compile_expr(form);
        return;
    }
    args = cell_b(form); n = list_len(args);
    if (n == 2) {
        test = cell_a(args); then_f = cell_a(cell_b(args)); else_f = NIL;
    } else if (n == 3) {
        test = cell_a(args); then_f = cell_a(cell_b(args));
        else_f = cell_a(cell_b(cell_b(args)));
    } else {
        cu->err = 1;
        return;
    }
    compile_expr(test);
    jf = emit_branch(OP_JFALSEREL);
    compile_defun_tail_expr(then_f);
    emit1(OP_RET);
    patch_here(jf);
    compile_defun_tail_expr(else_f);
}

static void compile_defun_tail_sequence(obj body) {
    if (!is_cons(body)) { emit1(OP_PUSHNIL); return; }
    while (is_cons(cell_b(body))) {
        compile_expr(cell_a(body)); emit1(OP_DROP); body = cell_b(body);
    }
    compile_defun_tail_expr(cell_a(body));
}

/* defun DIREKT als benannte Funktion in fn[0] kompilieren (Params ab Slot 0), OHNE den Umweg
 * "-> lambda -> Helfer liften -> fn[0]=PUSHLIT". Spart je defun ein CodeObject + Dir-Eintrag + ein
 * "__L"-Symbol -- der Geraete-Compiler war so ~2x objekt-schwerer als der Host-Blob (480 vs 232 Objekte;
 * S5-Objekt-Effizienz, docs/vollprofil-stack-heap-collision.md). Innere lambdas im Rumpf werden weiter
 * regulaer geliftet (fn[1..]). Der Aufrufer registriert fn[0] unter dem defun-Namen. */
void bc_compile_defun(bc_unit *u, obj params, obj body) {
    cu = u; u->nfn = 0; u->err = 0;
    if (u->fncap < 1) { u->err = 1; return; }
    cc = &u->fn[u->nfn++];               /* fn[0] = die benannte Funktion selbst (kein Lift) */
    cc->name = NIL; cc->codelen = 0; cc->nlit = 0; cc->nargs = 0; cc->nlocals = 0;
    cc->flags = CC_PROFILE_FLAGS; cc->nupvals = 0;
    cc_nparams = 0; cc_nextslot = 0; cc_scopen = 0; cc_scopebase = 0;
    cc_depth = 0; cc_lvl[0].scopebase = 0; cc_lvl[0].nuv = 0;
    cc_bind_params(params);              /* Params ab Slot 0 (frischer Toplevel-Scope, kein Capture) */
    compile_defun_tail_sequence(body);
    emit1(OP_RET);
}

uint16_t bc_assemble(const bc_func *f, uint8_t *out, uint16_t cap) {
    uint16_t n = 0, j; uint8_t i;
    if ((uint32_t)7 + 2u * f->nlit + f->codelen > cap) return 0;
    out[n++] = CO_MAGIC; out[n++] = f->nargs; out[n++] = f->nlocals; out[n++] = f->flags;
    out[n++] = (uint8_t)(f->codelen & 0xff); out[n++] = (uint8_t)(f->codelen >> 8);
    out[n++] = f->nlit;
    for (i = 0; i < f->nlit; i++) { uint16_t v = (uint16_t)f->lit[i]; out[n++] = (uint8_t)v; out[n++] = (uint8_t)(v >> 8); }
    for (j = 0; j < f->codelen; j++) out[n++] = f->code[j];
    return n;
}
