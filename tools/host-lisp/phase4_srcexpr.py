#!/usr/bin/env python3
"""Decode historical Phase-6 Source-Expr IR and evaluate it independently.

The native lowerer first emits a prefix-tree IR before compiling VM bytecode.
This tool decodes handwritten expected IR arrays into an AST and evaluates them
with phase4_vm, detecting an expected array whose bytes agree with the lowerer
but whose semantics are wrong. `--check-acme` reports mirrored-table drift.

Usage:
  phase4_srcexpr.py --selftest
  phase4_srcexpr.py --acme-label Phase6SourcePrognSlotExpected
  phase4_srcexpr.py --acme-label Phase6SourceClosureCall1Expr object-closure
  phase4_srcexpr.py --acme-label <QuoteObjectFixture> object-closure
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase4_disasm import extract_acme_label, acme_symbol_table  # noqa: E402
import phase4_vm  # noqa: E402

# Source-expression IR opcodes for the non-object-values profile.
END, LIT8, ADD2, LITS8, LIT16, LITS16, ARG0, ARG1, ARG2 = range(9)
SUB2, MUL2, DIV2, LESS2, GREATER2, ZEROP1, MINUSP1, ADD1, SUB1 = range(9, 18)
REMAINDER2, MINUS1, LOGAND2, LOGOR2, IF3, EQ2, ABS1, LOGXOR2 = range(18, 26)
COMPL1, LBYTE1, HBYTE1, CALL1, TAILSELF1, CALL2, CALL3 = range(26, 33)
TAILSELF2, TAILSELF3, NOT1, NIL, T, LOADL, STOREL, BEGIN2 = range(33, 41)
OBJ_OBJECT_CLOSURE = 38
CLOSURE_OBJECT = 39
CALLCLOSURE1_OBJECT = 40

VM_OP_PUSHLIT8 = 6
VM_OP_PRINTACC = 3
VM_OP_HALT = 0
VM_OP_CLOSURE = 49
VM_OP_CALLCLOSURE1 = 50
VM_OP_PUSHOBJ = 45

# Source AST operator name -> VM bytecode opcode for the payload compiler.
_VM_BIN = {"PLUS": 2, "DIFFERENCE": 14, "TIMES": 15, "QUOTIENT": 16,
           "REMAINDER": 24, "LOGAND": 26, "LOGOR": 27, "LOGXOR": 32,
           "LESSP": 18, "GREATERP": 19, "EQ": 30}
_VM_UN = {"ZEROP": 20, "MINUSP": 21, "ADD1": 22, "SUB1": 23, "MINUS": 25,
          "ABS": 31, "COMPL": 33, "LBYTE": 34, "HBYTE": 35, "NOT": 42}

# opcode -> (operand_bytes, child_count, ast_builder)
# ast_builder receives (operand_list, kind_asts) and returns an AST node.
_BIN = {ADD2: "PLUS", SUB2: "DIFFERENCE", MUL2: "TIMES", DIV2: "QUOTIENT",
        REMAINDER2: "REMAINDER", LOGAND2: "LOGAND", LOGOR2: "LOGOR",
        LOGXOR2: "LOGXOR", LESS2: "LESSP", GREATER2: "GREATERP", EQ2: "EQ"}
_UN = {ZEROP1: "ZEROP", MINUSP1: "MINUSP", ADD1: "ADD1", SUB1: "SUB1",
       MINUS1: "MINUS", ABS1: "ABS", COMPL1: "COMPL", LBYTE1: "LBYTE",
       HBYTE1: "HBYTE", NOT1: "NOT"}


class SrcExprError(Exception):
    pass


def _s8(v):
    return v - 0x100 if v & 0x80 else v


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def decode(mem, pos=0, profile="frame"):
    """Decode one prefix expression at mem[pos] and return (ast, new_pos)."""
    if pos >= len(mem):
        raise SrcExprError("vorzeitiges Ende bei %d" % pos)
    op = mem[pos]
    pos += 1
    if op == LIT8:
        return mem[pos], pos + 1
    if op == LITS8:
        return _s8(mem[pos]), pos + 1
    if op == LIT16:
        return mem[pos] | (mem[pos + 1] << 8), pos + 2
    if op == LITS16:
        return _s16(mem[pos] | (mem[pos + 1] << 8)), pos + 2
    if op in (ARG0, ARG1, ARG2):
        return ("ARG", op - ARG0), pos
    if op == NIL:
        return 0, pos              # Non-Object: NIL == 0
    if op == T:
        return 1, pos              # Non-Object: T == 1
    if op == IF3:                  # COND -> IF3 (Test, Dann, Sonst)
        c, pos = decode(mem, pos, profile)
        t, pos = decode(mem, pos, profile)
        e, pos = decode(mem, pos, profile)
        return ("IF", c, t, e), pos
    if profile == "object-closure" and op == OBJ_OBJECT_CLOSURE:
        # Quoted-Symbol-Objektliteral: OpObj, symptr_lo, symptr_hi
        return ("OBJ", mem[pos] | (mem[pos + 1] << 8)), pos + 2
    if profile == "object-closure" and op == CLOSURE_OBJECT:
        return ("CLOSURE", mem[pos] | (mem[pos + 1] << 8)), pos + 2
    if profile == "object-closure" and op == CALLCLOSURE1_OBJECT:
        closure, pos = decode(mem, pos, profile)
        arg, pos = decode(mem, pos, profile)
        return ("CALLCLOSURE1", closure, arg), pos
    if op == LOADL:
        depth, idx = mem[pos], mem[pos + 1]
        if depth != 0:
            raise SrcExprError("LoadL depth!=0 nicht modelliert")
        return phase4_vm._SLOT_IDX_TO_NAME[idx], pos + 2
    if op == STOREL:
        depth, idx = mem[pos], mem[pos + 1]
        child, pos = decode(mem, pos + 2, profile)
        return ("STOREL", depth, idx, child), pos
    if op == BEGIN2:
        a, pos = decode(mem, pos, profile)
        b, pos = decode(mem, pos, profile)
        return ("BEGIN2", a, b), pos
    if op in _BIN:
        a, pos = decode(mem, pos, profile)
        b, pos = decode(mem, pos, profile)
        return (_BIN[op], a, b), pos
    if op in _UN:
        a, pos = decode(mem, pos, profile)
        return (_UN[op], a), pos
    raise SrcExprError("nicht modellierter Source-Expr-Opcode %d bei %d"
                       % (op, pos - 1))


def decode_top(mem, profile="frame"):
    """Decode one top-level expression and require a trailing END."""
    ast, pos = decode(mem, 0, profile)
    if pos >= len(mem) or mem[pos] != END:
        raise SrcExprError("erwartete OpEnd am Ende, bei %d" % pos)
    return ast


def eval_expected(mem, env=None, profile="frame"):
    """Decode an IR array and evaluate it with the oracle."""
    return phase4_vm.eval_ast(decode_top(mem, profile), env)


class _SourcePayloadComp:
    """Minimal source-expression to VM-payload compiler for host byte checks."""
    def __init__(self):
        self.code = []
        self.literals = []

    def _lit(self, value):
        if value in self.literals:
            return self.literals.index(value)
        self.literals.append(value)
        return len(self.literals) - 1

    def emit_expr(self, ast):
        if isinstance(ast, int):
            self.code += [VM_OP_PUSHLIT8, self._lit(ast)]
            return
        op = ast[0]
        if op == "CLOSURE":
            ptr = ast[1]
            self.code += [VM_OP_CLOSURE, ptr & 0xFF, (ptr >> 8) & 0xFF]
            return
        if op == "CALLCLOSURE1":
            self.emit_expr(ast[1])
            self.emit_expr(ast[2])
            self.code.append(VM_OP_CALLCLOSURE1)
            return
        if op == "OBJ":                            # Objektliteral -> PushObj symptr
            ptr = ast[1]
            self.code += [VM_OP_PUSHOBJ, ptr & 0xFF, (ptr >> 8) & 0xFF]
            return
        if op in _VM_BIN:                          # links, rechts, Opcode (postfix)
            self.emit_expr(ast[1])
            self.emit_expr(ast[2])
            self.code.append(_VM_BIN[op])
            return
        if op in _VM_UN:
            self.emit_expr(ast[1])
            self.code.append(_VM_UN[op])
            return
        # IF/COND needs control flow and is intentionally not modeled; decode coverage is enough
        # for this structural check.
        raise SrcExprError("nicht kompilierbarer Source-Expr-AST: %r" % (ast,))


def _source_result_kind(ast):
    if isinstance(ast, int):
        return "numeric"
    if isinstance(ast, tuple) and ast[0] in ("CLOSURE", "OBJ"):
        return "object"
    if isinstance(ast, tuple) and ast[0] == "CALLCLOSURE1":
        return "numeric"
    return "numeric"


def compile_payload(mem, profile="frame", print_result=True):
    """Compile source-expression IR into VM payload bytes.

    This intentionally smaller model serves the lowering-only closure smoke,
    which expects `CLOSURE ptr; PUSHLIT8 0; CALLCLOSURE1; PRINTACC; HALT`.
    Pure object results such as `CLOSURE ptr` omit the terminal `PRINTACC`,
    matching the native compiler.
    """
    ast = decode_top(mem, profile)
    comp = _SourcePayloadComp()
    comp.emit_expr(ast)
    if print_result and _source_result_kind(ast) != "object":
        comp.code.append(VM_OP_PRINTACC)
    comp.code.append(VM_OP_HALT)
    return bytes(comp.code), comp.literals


def label_env(label):
    if label in ("Phase6SourceLambdaEntryExpected",
                 "Phase6SourceLambdaWrapperPrognExpected"):
        return {"A": 1, "B": 2, "C": 4}
    return None


# ---- .acme-Anbindung -----------------------------------------------------

def _acme_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "src", "v2", "modules",
                        "20-bytecode-vm.acme")


def _symbolic_word_value(tok, symbolic_words):
    if tok not in symbolic_words:
        symbolic_words[tok] = 0x8000 + len(symbolic_words)
    return symbolic_words[tok]


def _resolve_data_byte_token(tok, syms, symbolic_words):
    tok = tok.strip()
    if not tok:
        return None
    if tok.startswith("<"):
        return _resolve_data_word_token(tok[1:], syms, symbolic_words) & 0xFF
    if tok.startswith(">"):
        return (_resolve_data_word_token(tok[1:], syms, symbolic_words) >> 8) & 0xFF
    return _resolve_data_word_token(tok, syms, symbolic_words) & 0xFF


def _resolve_data_word_token(tok, syms, symbolic_words):
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if tok.lstrip("-").isdigit():
        return int(tok) & 0xFFFF
    if tok in syms:
        return syms[tok] & 0xFFFF
    return _symbolic_word_value(tok, symbolic_words)


def extract_source_data_label(path, label):
    """Collect `!byte`/`!word` data from a source-expression fixture label.

    Assign stable placeholders to unknown labels in `!word` operands. The
    closure smoke only needs to prove that the same source-IR operand appears
    as `CLOSURE lo hi` in the payload.
    """
    syms = acme_symbol_table(path)
    symbolic_words = {}
    out = []
    started = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not started:
                if s == label + ":":
                    started = True
                continue
            data = s.split(";", 1)[0].strip()
            if data.startswith("!byte"):
                rest = data[len("!byte"):]
                for tok in rest.split(","):
                    b = _resolve_data_byte_token(tok, syms, symbolic_words)
                    if b is not None:
                        out.append(b)
            elif data.startswith("!word"):
                rest = data[len("!word"):]
                for tok in rest.split(","):
                    w = _resolve_data_word_token(tok, syms, symbolic_words)
                    out.extend([w & 0xFF, (w >> 8) & 0xFF])
            elif data == "":
                continue
            else:
                break
    if not started:
        raise SrcExprError("Label %r nicht gefunden in %s" % (label, path))
    return bytes(out)


def check_acme(path=None, profile="frame"):
    """Report source-IR opcode drift against the last-wins source table."""
    syms = acme_symbol_table(path or _acme_path())
    want = {"Phase4SourceExprOpLit8": LIT8, "Phase4SourceExprOpEnd": END,
            "Phase4SourceExprOpNil": NIL, "Phase4SourceExprOpT": T}
    if profile == "frame":
        want.update({"Phase4SourceExprOpLoadL": LOADL,
                     "Phase4SourceExprOpStoreL": STOREL,
                     "Phase4SourceExprOpBegin2": BEGIN2})
    elif profile == "object-closure":
        want.update({"Phase4SourceExprOpObj": OBJ_OBJECT_CLOSURE,
                     "Phase4SourceExprOpClosure": CLOSURE_OBJECT,
                     "Phase4SourceExprOpCallClosure1": CALLCLOSURE1_OBJECT})
    else:
        raise SrcExprError("unbekanntes Profil: %s" % profile)
    drift = 0
    for name, val in want.items():
        if name in syms and syms[name] != val:
            print("DRIFT: %s = %d in Quelle, hier %d" % (name, syms[name], val))
            drift += 1
    return drift


def check_capture_contract(path=None):
    """Check the native V0 contract for capture-operand classification."""
    path = path or _acme_path()
    syms = acme_symbol_table(path)
    want = {
        "Phase4LowerLispListBodyLambdaClosureOperandUnknown": 0,
        "Phase4LowerLispListBodyLambdaClosureOperandParent": 1,
        "Phase4LowerLispListBodyLambdaClosureOperandLocal": 2,
    }
    drift = 0
    for name, val in want.items():
        if syms.get(name) != val:
            print("DRIFT: %s = %r in Quelle, erwartet %d" % (
                name, syms.get(name), val))
            drift += 1
    with open(path) as f:
        text = f.read()
    start = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_LCALL_RUN_SMOKE {")
    if start < 0:
        print("DRIFT: LCALL-Run-Flagblock nicht gefunden")
        return drift + 1
    end = text.find("\n}", start)
    block = text[start:end] if end >= 0 else text[start:]
    flag = "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_PLUS_BODY_CHILD = 1"
    if flag not in block:
        print("DRIFT: LCALL-Run-Profil nutzt kein body-geprueftes gebautes Capture-Child")
        drift += 1
    plan_flag = "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_PLAN_TARGET = 1"
    if plan_flag not in block:
        print("DRIFT: LCALL-Run-Profil nutzt keinen Plan-Scratch-Child-Puffer")
        drift += 1
    classify_flag = "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_CLASSIFY = 1"
    if classify_flag in block:
        print("DRIFT: LCALL-Run-Profil aktiviert wieder den Capture-Klassifizierer")
        drift += 1
    diff_flag = "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_DIFF_SELECT = 1"
    if diff_flag in block:
        print("DRIFT: LCALL-Run-Profil aktiviert Difference-Child-Auswahl")
        drift += 1
    start = text.find("Phase4LowerLispListBodyLambdaClosureMatchCapture:")
    if start < 0:
        print("DRIFT: Capture-Matcher nicht gefunden")
        return drift + 1
    end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_CLOSURE_CALL1_LOWER", start)
    match_block = text[start:end] if end >= 0 else text[start:]
    for needle in (
            "STA\tPhase4CompilerArgNodePtr",
            "STA\tPhase4CompilerArgNodePtr+1",
            "JSR\tPhase4CompilerNodePtrIsSymbolObject",
            "CMP\tPhase4CompilerArgNodePtr",
            "CMP\tPhase4CompilerArgNodePtr+1",
            "STA\tPhase4CompilerNestedFlags",
            "EOR\tPhase4CompilerNestedFlags",
            "LDA\t#Phase4LowerLispListBodyLambdaClosureOperandUnknown",
            "CMP\t#Phase4LowerLispListBodyLambdaClosureOperandParent + Phase4LowerLispListBodyLambdaClosureOperandLocal",
            "CMP\t#<nPLUS",
            "CMP\t#>nPLUS"):
        if needle not in match_block:
            print("DRIFT: Capture-Matcher nutzt lokalen Parameter nicht generisch: %s" %
                  needle)
            drift += 1
    has_difference = (
        "CMP\t#<nDIFFERENCE" in match_block or
        "CMP\t#>nDIFFERENCE" in match_block)
    if has_difference:
        for needle in (
                diff_flag,
                "STA\tPhase4CompilerRootAppendFlag",
                "Phase4LowerLispListBodyLambdaClosureSelectCaptureChild:",
                "Phase6SourceLambdaClosureDifferenceParentLocalChildCodeObject",
                "Phase6SourceLambdaClosureDifferenceLocalParentChildCodeObject"):
            if needle not in match_block and needle not in text:
                print("DRIFT: Capture-Matcher erweitert Difference ohne Auswahlvertrag: %s" %
                      needle)
                drift += 1
    selector = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_SELECT {")
    selector_end = text.find("Phase4LowerLispListBodyLambdaClosureDone:", selector)
    selector_block = text[selector:selector_end] if selector >= 0 and selector_end >= 0 else ""
    for needle in (
            "Phase4LowerLispListBodyLambdaClosureEmitSelectedChild:",
            "Phase4LowerLispListBodyLambdaClosureEmitSelectedChildPtrReady:",
            "STA\t<NodePtr",
            "STY\t<NodePtr+1",
            "LDA\t<NodePtr+1"):
        if needle not in selector_block:
            print("DRIFT: Capture-Select-Pfad hat keinen Child-Auswahlpunkt: %s" %
                  needle)
            drift += 1
    hard_local = "CMP\t#<Phase4CompilerLispRealDefParamASymbol"
    if hard_local in match_block:
        print("DRIFT: Capture-Matcher ist wieder auf lokalen Parameter A gepinnt")
        drift += 1
    classifier = text.find("Phase4LowerLispListBodyLambdaClosureClassifyNodePtr:")
    if classifier < 0:
        print("DRIFT: Capture-Klassifizierer nicht gefunden")
        return drift + 1
    classifier_end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_CLOSURE_CALL1_LOWER", classifier)
    classifier_block = text[classifier:classifier_end] if classifier_end >= 0 else text[classifier:]
    hard_parent = "CMP\t#<Phase4CompilerLispRealDefParamBSymbol"
    if hard_parent in classifier_block:
        print("DRIFT: Capture-Klassifizierer ist wieder auf Parent-Parameter B gepinnt")
        drift += 1
    if "Phase4LowerLispListBodyLambdaClosureClassifyNodePtrParent:" not in classifier_block:
        print("DRIFT: Capture-Klassifizierer hat keinen generischen Parent-Fallback")
        drift += 1
    if "LDA\t#Phase4LowerLispListBodyLambdaClosureOperandUnknown" not in classifier_block:
        print("DRIFT: Capture-Klassifizierer weist Nicht-Symbole nicht als Unknown ab")
        drift += 1
    base = text.find("Phase6SourceLambdaClosureCapturePlusFirst:")
    base_second = text.find("Phase6SourceLambdaClosureCapturePlusSecond:", base)
    if base < 0 or base_second < 0:
        print("DRIFT: Capture-Basis-Fixture Operandenlabels fehlen")
        drift += 1
    else:
        base_first_block = text[base:base_second]
        base_second_end = text.find("}", base_second)
        base_second_block = text[base_second:base_second_end] if base_second_end >= 0 else text[base_second:]
        if "!word\tPhase4CompilerLispRealDefParamASymbol" not in base_first_block:
            print("DRIFT: Capture-Basis-Fixture erster Operand ist nicht lokal A")
            drift += 1
        if "!word\tPhase4CompilerLispRealDefParamBSymbol" not in base_second_block:
            print("DRIFT: Capture-Basis-Fixture zweiter Operand ist nicht Parent B")
            drift += 1
    dup = text.find("Phase6SourceLambdaClosureCaptureDuplicateParamACell:")
    if dup < 0:
        print("DRIFT: Capture-Duplicate-Fixture nicht gefunden")
        return drift + 1
    dup_end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_UNKNOWN_DATA", dup)
    dup_block = text[dup:dup_end] if dup_end >= 0 else text[dup:]
    if dup_block.count("!word\tPhase4CompilerLispRealDefParamCSymbol") < 2:
        print("DRIFT: Capture-Duplicate-Fixture deckt alternativen lokalen Parameter C nicht ab")
        drift += 1
    unknown = text.find("Phase6SourceLambdaClosureCaptureUnknownParentBody")
    if unknown < 0:
        print("DRIFT: Capture-Unknown-Parent-Fixture nicht gefunden")
        return drift + 1
    unknown_first = text.find("Phase6SourceLambdaClosureCaptureUnknownParentPlusFirst:", unknown)
    unknown_second = text.find("Phase6SourceLambdaClosureCaptureUnknownParentPlusSecond:", unknown)
    if unknown_first < 0 or unknown_second < 0:
        print("DRIFT: Capture-Unknown-Parent-Fixture Operandenlabels fehlen")
        drift += 1
    else:
        first_block = text[unknown_first:unknown_second]
        second_end = text.find("}", unknown_second)
        second_block = text[unknown_second:second_end] if second_end >= 0 else text[unknown_second:]
        if "!word\tPhase4CompilerLispRealDefParamASymbol" not in first_block:
            print("DRIFT: Capture-Unknown-Parent-Fixture erster Operand ist nicht lokal A")
            drift += 1
        if "!word\tPhase4CompilerLispRealDefParamCSymbol" not in second_block:
            print("DRIFT: Capture-Unknown-Parent-Fixture zweiter Operand ist nicht Parent C")
            drift += 1
    unknown_compare = text.find(
        "LDA\t#<Phase6SourceLambdaClosureCaptureExpected", unknown)
    unknown_negative = text.find(
        "LDA\t#<Phase6SourceLambdaClosureCaptureNegativeExpected", unknown)
    if unknown_compare < 0 or 0 <= unknown_negative < unknown_compare:
        print("DRIFT: Capture-Unknown-Parent-Fixture ist nicht positiv abgesichert")
        drift += 1
    lower_start = text.find("TermRunPhase6SourceLambdaClosureCaptureLowerSmokeTest:")
    lower_end = text.find("TermRunPhase6SourceLambdaClosureCaptureLowerSmokeDone:", lower_start)
    lower_block = text[lower_start:lower_end] if lower_start >= 0 and lower_end >= 0 else ""
    for needle in (
            "LDA\t#<Phase4CompilerLispBodyLit4",
            "STA\tPhase6SourceLambdaClosureCaptureUnknownParentPlusSecond",
            "LDA\t#<Phase6SourceLambdaClosureCaptureNegativeExpected"):
        if needle not in lower_block:
            print("DRIFT: Capture-Lower-Smoke deckt Literal-Parent-Grenze nicht ab: %s" %
                  needle)
            drift += 1
    compile_start = text.find("TermRunPhase6SourceLambdaClosureCaptureCompileSmokeTest:")
    compile_end = text.find(
        "TermRunPhase6SourceLambdaClosureCaptureCompileSmokeDone:", compile_start)
    compile_block = (
        text[compile_start:compile_end]
        if compile_start >= 0 and compile_end >= 0 else "")
    for needle in (
            "CMP\tPhase6SourceLambdaClosureCaptureBuiltExpected",
            "CMP\tPhase6SourceLambdaClosureCaptureBuiltPayloadExpected",
            "CMP\t#Phase4VMCodeObjTypeBytecode",
            "LDA\t#<Phase4CompilerLispRealDefParamBSymbol",
            "STA\tPhase6SourceLambdaClosureCaptureUnknownParentPlusFirst",
            "CMP\tPhase6SourceLambdaClosurePayloadExpected"):
        if needle not in compile_block:
            print("DRIFT: Capture-Compile-Smoke deckt Built-Child/Parent-Parent-Payload nicht ab: %s" %
                  needle)
            drift += 1
    if "JSR\tPhase6BuildLambdaCaptureChildCodeObject" in compile_block:
        print("DRIFT: Capture-Compile-Smoke baut Built-Child wieder im Runner")
        drift += 1
    non_diff_selector = (
        "!ifndef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_DIFF_SELECT {\n"
        "\t!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_SELECT_BUILT_CHILD {\n"
        "\t\tJSR\tPhase6BuildLambdaCaptureChildCodeObject\n"
        "\t\tLDA\t#<Phase6LambdaChildBuilderTarget")
    if non_diff_selector not in text:
        print("DRIFT: Capture-Selector baut Built-Child nicht im Select-Pfad")
        drift += 1
    return drift


def check_lcall_lowering_contract(path=None):
    """Check that the LCALL smoke still uses the Lisp-argument lowering path."""
    path = path or _acme_path()
    with open(path) as f:
        text = f.read()
    start = text.find("TermRunPhase6SourceLambdaClosureLCallRunSmokeTest:")
    if start < 0:
        print("DRIFT: LCALL-Run-Smoke nicht gefunden")
        return 1
    end = text.find("\n}", start)
    block = text[start:end] if end >= 0 else text[start:]
    drift = 0
    required = [
        "LDA\t#<nPLUS",
        "STA\tPhase6SourceLambdaClosureCaptureDuplicatePlusBody",
        "JSR\tPhase6LowerLCallRunLambdaArg",
        "BCS\tTermRunPhase6SourceLambdaClosureLCallRunSmokeFail",
        "JSR\tNextPtrNextToNextPtr",
        "JSR\tPhase4LowerLispListEmitLiteralArgNonTail",
        "LDA\t#Phase4SourceExprOpEnd",
        "JSR\tPhase4CompilerEmitByte",
        "JSR\tPhase4CompileSourceExprToSmokeBuffer",
        "JSR\tPhase4VMRunSourceSmokeBuffer",
        "JSR\tPhase4VMPopToACC32",
        "CMP\t#7",
        "ORA\t<ACC32+2",
        "ORA\t<ACC32+3",
    ]
    pos = 0
    for needle in required:
        found = block.find(needle, pos)
        if found < 0:
            print("DRIFT: LCALL-Run-Smoke enthaelt Sequenz nicht: %s" % needle)
            drift += 1
        else:
            pos = found + len(needle)
    if "JSR\tPhase6BuildLambdaCaptureChildCodeObject" in block:
        print("DRIFT: LCALL-Run-Smoke baut Built-Child wieder im Runner")
        drift += 1
    if "Phase6LowerLCallRunLambdaArg:" not in text:
        print("DRIFT: LCALL-Run-Smoke teilt den Lambda-Lower-Helfer nicht")
        drift += 1
    else:
        helper_start = text.find("Phase6LowerLCallRunLambdaArg:")
        helper_end = text.find("\n}", helper_start)
        helper_block = text[helper_start:helper_end] if helper_end >= 0 else text[helper_start:]
        for needle in (
                "JSR\tPhase4CompilerUseMiniFormWriteBuffer",
                "LDA\t#Phase4SourceExprOpCallClosure1",
                "JSR\tPhase4CompilerEmitByte",
                "LDA\t#<Phase6SourceLambdaClosureLCallRunLambdaArg",
                "STA\t<NextPtr",
                "LDA\t#>Phase6SourceLambdaClosureLCallRunLambdaArg",
                "STA\t<NextPtr+1",
                "JMP\tPhase4LowerLispListEmitLiteralArgNonTail"):
            if needle not in helper_block:
                print("DRIFT: LCALL-Lambda-Lower-Helfer enthaelt Sequenz nicht: %s" % needle)
                drift += 1
    required_selector = (
        "!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_PLUS_BODY_CHILD {\n"
        "\t\tJSR\tPhase6BuildLambdaRequiredPlusChildCodeObject\n"
        "\t\tBCS\tPhase4LowerLispListBodyLambdaClosureRequiredBad\n"
        "\t\tLDA\t#<Phase6LambdaChildBuilderTarget")
    if required_selector not in text:
        print("DRIFT: LCALL-Required-Pfad baut Plus-Child nicht body-geprueft im Lowerer")
        drift += 1
    body_builder = text.find("Phase6BuildLambdaRequiredPlusChildCodeObject:")
    if body_builder < 0:
        print("DRIFT: LCALL-Plus-Body-Builder nicht gefunden")
        drift += 1
    else:
        body_block_end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_BODY_HELPERS", body_builder)
        body_block = text[body_builder:body_block_end] if body_block_end >= 0 else text[body_builder:]
        ordered_body_sequence = (
            "JSR\tPhase6LoadLambdaRequiredBodyOperator",
            "CMP\t#<nPLUS",
            "CMP\t#>nPLUS",
            "JSR\tNodeNextPtrToNextPtr",
            "JSR\tNextDataPtrToNodePtr",
            "CMP\t#<Phase4CompilerLispRealDefParamBSymbol",
            "CMP\t#>Phase4CompilerLispRealDefParamBSymbol",
            "JSR\tNextPtrNextToNextPtr",
            "JSR\tNextDataPtrToNodePtr",
            "CMP\t#<Phase4CompilerLispRealDefParamCSymbol",
            "CMP\t#>Phase4CompilerLispRealDefParamCSymbol",
            "JSR\tNextPtrNextToNextPtr",
            "JSR\tCmpNextPtrWithHashBase",
            "JMP\tPhase6BuildLambdaCaptureChildCodeObject",
            "SEC",
            "RTS",
        )
        pos = 0
        for needle in ordered_body_sequence:
            found = body_block.find(needle, pos)
            if found < 0:
                print("DRIFT: LCALL-Plus-Body-Builder prueft Operator/Pfad nicht geordnet: %s" % needle)
                drift += 1
            else:
                pos = found + len(needle)
    if "Phase6LoadLambdaRequiredBodyOperator:" not in text:
        print("DRIFT: LCALL-Required-Builder teilen keinen Body-Operator-Helper")
        drift += 1
    if "STA\tPhase6SourceLambdaClosureCapturePlusFirst" in block:
        print("DRIFT: LCALL-Run-Smoke mutiert Parent-Symbol wieder testlokal")
        drift += 1
    lambda_lowerer = "JSR\tPhase6LowerLCallRunLambdaArg"
    if block.count(lambda_lowerer) != 1:
        print("DRIFT: LCALL-Run-Smoke nutzt Lambda-Lower-Helfer %d statt 1 mal" %
              block.count(lambda_lowerer))
        drift += 1
    split_at = block.rfind("JSR\tNextPtrNextToNextPtr")
    before_split_count = block[:split_at].count(lambda_lowerer) if split_at >= 0 else 0
    value_arg_count = block[split_at:].count("JSR\tPhase4LowerLispListEmitLiteralArgNonTail") if split_at >= 0 else 0
    if split_at < 0 or before_split_count != 1 or value_arg_count != 1:
        print("DRIFT: LCALL-Run-Smoke senkt Lambda- und Wert-Argument nicht getrennt")
        drift += 1
    fixture = [
        "Phase6SourceLambdaClosureLCallRunLambdaArg:",
        "!word\tPhase6SourceLambdaClosureCaptureDuplicateBody",
        "!word\tPhase6SourceLambdaClosureLCallRunValueArg",
        "Phase6SourceLambdaClosureLCallRunValueArg:",
        "!word\tPhase4CompilerLispBodyLit4",
        "!word\tHashBase",
    ]
    for needle in fixture:
        if needle not in text:
            print("DRIFT: LCALL-Run-Fixture fehlt: %s" % needle)
            drift += 1
    return drift


def check_diff_lcall_lowering_contract(path=None):
    """Check the narrow Difference-LCALL contract."""
    path = path or _acme_path()
    with open(path) as f:
        text = f.read()
    drift = 0
    start = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_DIFF_LCALL_RUN_SMOKE {")
    if start < 0:
        print("DRIFT: Difference-LCALL-Flagblock nicht gefunden")
        return 1
    end = text.find("\n}", start)
    flag_block = text[start:end] if end >= 0 else text[start:]
    required_flags = [
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_PLAN_TARGET = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_DIFF_PARENT_LOCAL_BODY_CHILD = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_DIFF_PARENT_LOCAL_DATA = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_BODY_OPERATOR_DIFFERENCE = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_LCALL_RUN_DATA = 1",
    ]
    for needle in required_flags:
        if needle not in flag_block:
            print("DRIFT: Difference-LCALL-Flag fehlt: %s" % needle)
            drift += 1
    forbidden_flags = [
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_BODY_HELPERS = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_CLASSIFY = 1",
        "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_DIFF_SELECT = 1",
    ]
    for needle in forbidden_flags:
        if needle in flag_block:
            print("DRIFT: Difference-LCALL zieht wieder breiten Pfad ein: %s" % needle)
            drift += 1

    start = text.find("TermRunPhase6SourceLambdaClosureDifferenceLCallRunSmokeTest:")
    if start < 0:
        print("DRIFT: Difference-LCALL-Runner nicht gefunden")
        return drift + 1
    end = text.find("\n}", start)
    block = text[start:end] if end >= 0 else text[start:]
    required_sequence = [
        "LDA\t#<Phase6SourceLambdaClosureDifferenceParentFrame",
        "LDA\t#<nDIFFERENCE",
        "STA\tPhase6SourceLambdaClosureCaptureDuplicatePlusBody",
        "JSR\tPhase6LowerLCallRunLambdaArg",
        "BCS\tTermRunPhase6SourceLambdaClosureDifferenceLCallRunSmokeFail",
        "JSR\tNextPtrNextToNextPtr",
        "JSR\tPhase4LowerLispListEmitLiteralArgNonTail",
        "LDA\t#Phase4SourceExprOpEnd",
        "JSR\tPhase4CompileSourceExprToSmokeBuffer",
        "JSR\tPhase4VMRunSourceSmokeBuffer",
        "JSR\tPhase4VMPopToACC32",
        "CMP\t#3",
    ]
    pos = 0
    for needle in required_sequence:
        found = block.find(needle, pos)
        if found < 0:
            print("DRIFT: Difference-LCALL-Runner enthaelt Sequenz nicht: %s" % needle)
            drift += 1
        else:
            pos = found + len(needle)
    if "JSR\tPhase6BuildLambda" in block:
        print("DRIFT: Difference-LCALL-Runner baut Child wieder im Runner")
        drift += 1
    if "Phase6LowerLCallRunLambdaArg:" not in text:
        print("DRIFT: Difference-LCALL-Runner teilt den Lambda-Lower-Helfer nicht")
        drift += 1
    negative_sequence = [
        "LDA\t#<nPLUS",
        "STA\tPhase6SourceLambdaClosureCaptureDuplicatePlusBody",
        "JSR\tPhase6LowerLCallRunLambdaArg",
        "BCC\tTermRunPhase6SourceLambdaClosureDifferenceLCallRunSmokeFail",
        "LDA\t#<nDIFFERENCE",
        "STA\tPhase6SourceLambdaClosureCaptureDuplicatePlusBody",
    ]
    pos = 0
    for needle in negative_sequence:
        found = block.find(needle, pos)
        if found < 0:
            print("DRIFT: Difference-LCALL-Runner prueft falschen Operator nicht negativ: %s" % needle)
            drift += 1
        else:
            pos = found + len(needle)
    lambda_lowerer = "JSR\tPhase6LowerLCallRunLambdaArg"
    if block.count(lambda_lowerer) != 2:
        print("DRIFT: Difference-LCALL-Runner nutzt Lambda-Lower-Helfer %d statt 2 mal" %
              block.count(lambda_lowerer))
        drift += 1

    required_lowerer = (
        "!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_DIFF_PARENT_LOCAL_BODY_CHILD {\n"
        "\t\tJSR\tPhase6BuildLambdaRequiredDifferenceParentLocalChildCodeObject\n"
        "\t\tBCS\tPhase4LowerLispListBodyLambdaClosureRequiredBad\n"
        "\t\tLDA\t#<Phase6LambdaChildBuilderTarget")
    if required_lowerer not in text:
        print("DRIFT: Difference-LCALL-Required-Pfad baut Parent/Local-Child nicht body-geprueft im Lowerer")
        drift += 1
    body_builder = text.find("Phase6BuildLambdaRequiredDifferenceParentLocalChildCodeObject:")
    if body_builder < 0:
        print("DRIFT: Difference-LCALL-Body-Builder nicht gefunden")
        drift += 1
    else:
        body_block_end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_BODY_HELPERS", body_builder)
        body_block = text[body_builder:body_block_end] if body_block_end >= 0 else text[body_builder:]
        for needle in (
                "JSR\tPhase6LoadLambdaRequiredBodyOperator",
                "CMP\t#<nDIFFERENCE",
                "CMP\t#>nDIFFERENCE",
                "JMP\tPhase6BuildLambdaDifferenceParentLocalChildCodeObject",
                "SEC",
                "RTS"):
            if needle not in body_block:
                print("DRIFT: Difference-LCALL-Body-Builder prueft Operator/Pfad nicht: %s" % needle)
                drift += 1
    if "Phase6LoadLambdaRequiredBodyOperator:" not in text:
        print("DRIFT: Difference-LCALL-Required-Builder teilen keinen Body-Operator-Helper")
        drift += 1
    if "Phase6SourceLambdaClosureLCallRunLambdaArg:" not in text:
        print("DRIFT: Difference-LCALL nutzt nicht die gemeinsame LCALL-Lambda-Fixture")
        drift += 1
    local_flag = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_DIFF_LCALL_LOCAL_RUN_SMOKE {")
    if local_flag < 0:
        print("DRIFT: Difference-LCALL-Local-Flagblock nicht gefunden")
        drift += 1
    else:
        local_end = text.find("\n}", local_flag)
        local_flag_block = text[local_flag:local_end] if local_end >= 0 else text[local_flag:]
        for needle in (
                "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_DIFF_LOCAL_PARENT_BODY_CHILD = 1",
                "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_DIFF_LOCAL_PARENT_DATA = 1",
                "TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_LCALL_LOCAL_RUN_DATA = 1"):
            if needle not in local_flag_block:
                print("DRIFT: Difference-LCALL-Local-Flag fehlt: %s" % needle)
                drift += 1
    local_runner = text.find("TermRunPhase6SourceLambdaClosureDifferenceLCallLocalRunSmokeTest:")
    if local_runner < 0:
        print("DRIFT: Difference-LCALL-Local-Runner nicht gefunden")
        drift += 1
    else:
        local_end = text.find("\n}", local_runner)
        local_block = text[local_runner:local_end] if local_end >= 0 else text[local_runner:]
        for needle in (
                "JSR\tPhase4LowerLispListEmitLiteralArgNonTail",
                "JSR\tPhase4CompileSourceExprToSmokeBuffer",
                "JSR\tPhase4VMRunSourceSmokeBuffer",
                "JSR\tPhase4VMPopToACC32",
                "CMP\t#$FD",
                "CMP\t#$FF"):
            if needle not in local_block:
                print("DRIFT: Difference-LCALL-Local-Runner prueft Sequenz nicht: %s" % needle)
                drift += 1
        local_negative_sequence = [
            "LDA\t#<nPLUS",
            "STA\tPhase6SourceLambdaClosureCapturePlusBody",
            "JSR\tPhase6LowerLCallRunLambdaArg",
            "BCC\tTermRunPhase6SourceLambdaClosureDifferenceLCallLocalRunSmokeFail",
            "LDA\t#<nDIFFERENCE",
            "STA\tPhase6SourceLambdaClosureCapturePlusBody",
        ]
        pos = 0
        for needle in local_negative_sequence:
            found = local_block.find(needle, pos)
            if found < 0:
                print("DRIFT: Difference-LCALL-Local-Runner prueft falschen Operator nicht negativ: %s" % needle)
                drift += 1
            else:
                pos = found + len(needle)
        if local_block.count("JSR\tPhase6LowerLCallRunLambdaArg") != 2:
            print("DRIFT: Difference-LCALL-Local-Runner nutzt Lambda-Lower-Helfer %d statt 2 mal" %
                  local_block.count("JSR\tPhase6LowerLCallRunLambdaArg"))
            drift += 1
    local_lowerer = (
        "!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CAPTURE_REQUIRED_BUILT_DIFF_LOCAL_PARENT_BODY_CHILD {\n"
        "\t\tJSR\tPhase6BuildLambdaRequiredDifferenceLocalParentChildCodeObject\n"
        "\t\tBCS\tPhase4LowerLispListBodyLambdaClosureRequiredBad\n"
        "\t\tLDA\t#<Phase6LambdaChildBuilderTarget")
    if local_lowerer not in text:
        print("DRIFT: Difference-LCALL-Local-Required-Pfad baut Local/Parent-Child nicht body-geprueft im Lowerer")
        drift += 1
    local_body_builder = text.find("Phase6BuildLambdaRequiredDifferenceLocalParentChildCodeObject:")
    if local_body_builder < 0:
        print("DRIFT: Difference-LCALL-Local-Body-Builder nicht gefunden")
        drift += 1
    else:
        local_body_end = text.find("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_CHILD_BUILDER_BODY_HELPERS", local_body_builder)
        local_body_block = text[local_body_builder:local_body_end] if local_body_end >= 0 else text[local_body_builder:]
        for needle in (
                "JSR\tPhase6LoadLambdaRequiredBodyOperator",
                "CMP\t#<nDIFFERENCE",
                "CMP\t#>nDIFFERENCE",
                "JMP\tPhase6BuildLambdaDifferenceLocalParentChildCodeObject"):
            if needle not in local_body_block:
                print("DRIFT: Difference-LCALL-Local-Body-Builder prueft Operator/Pfad nicht: %s" % needle)
                drift += 1
    if ("!ifdef TERM_TEST_PHASE6_SOURCE_LAMBDA_CLOSURE_LCALL_LOCAL_RUN_DATA {\n"
            "\t\t!word\tPhase6SourceLambdaClosureCaptureBody") not in text:
        print("DRIFT: Difference-LCALL-Local-Fixture nutzt nicht die Local/Parent-Lambda-Form")
        drift += 1
    return drift


# ---- Self-test -----------------------------------------------------------

def _selftest():
    # Hand-built synthetic IR: BEGIN2(Lit8 1, Lit8 42) -> 42.
    assert decode_top(bytes([BEGIN2, LIT8, 1, LIT8, 42, END])) == (
        "BEGIN2", 1, 42)
    assert eval_expected(bytes([BEGIN2, LIT8, 1, LIT8, 42, END])) == 42

    # StoreL/LoadL: BEGIN2(STOREL 0,1 (Lit8 99), LoadL 0,1) -> 99
    ir = bytes([BEGIN2, STOREL, 0, 1, LIT8, 99, LOADL, 0, 1, END])
    assert eval_expected(ir) == 99, decode_top(ir)

    # Quoted-symbol object literals mirror the core evaluator's object-truth
    # inputs for EQ/NOT/COND (QUOTE QUOTE). Check decode shape and payload bytes.
    eqobj = bytes([EQ2, OBJ_OBJECT_CLOSURE, 0x34, 0x12,
                   OBJ_OBJECT_CLOSURE, 0x78, 0x56, END])
    assert decode_top(eqobj, "object-closure") == (
        "EQ", ("OBJ", 0x1234), ("OBJ", 0x5678))
    payload, lits = compile_payload(eqobj, "object-closure")
    assert payload == bytes([VM_OP_PUSHOBJ, 0x34, 0x12,
                             VM_OP_PUSHOBJ, 0x78, 0x56, 30,
                             VM_OP_PRINTACC, VM_OP_HALT]), list(payload)
    assert lits == []
    notobj = bytes([NOT1, OBJ_OBJECT_CLOSURE, 0x34, 0x12, END])
    assert decode_top(notobj, "object-closure") == ("NOT", ("OBJ", 0x1234))
    payload, _ = compile_payload(notobj, "object-closure")
    assert payload == bytes([VM_OP_PUSHOBJ, 0x34, 0x12, 42,
                             VM_OP_PRINTACC, VM_OP_HALT]), list(payload)
    ifobj = bytes([IF3, OBJ_OBJECT_CLOSURE, 0x34, 0x12, LIT8, 42, LIT8, 99, END])
    assert decode_top(ifobj, "object-closure") == (
        "IF", ("OBJ", 0x1234), 42, 99)

    # Closure source expression V0: lower-only payload form without runtime semantics.
    ccall = bytes([CALLCLOSURE1_OBJECT, CLOSURE_OBJECT, 0x34, 0x12,
                   LIT8, 4, END])
    assert decode_top(ccall, "object-closure") == (
        "CALLCLOSURE1", ("CLOSURE", 0x1234), 4)
    payload, literals = compile_payload(ccall, "object-closure")
    assert payload == bytes([VM_OP_CLOSURE, 0x34, 0x12, VM_OP_PUSHLIT8, 0,
                             VM_OP_CALLCLOSURE1, VM_OP_PRINTACC, VM_OP_HALT])
    assert literals == [4]

    # Cross-check against the real expected arrays from source.
    acme = _acme_path()
    if os.path.exists(acme):
        assert check_acme(acme) == 0, "Source-Expr-Opcode-Drift"
        assert check_acme(acme, "object-closure") == 0, "Closure-Opcode-Drift"
        cases = {
            "Phase6SourceProgn3Expected": (42, None),     # (PROGN 1 2 42)
            "Phase6SourceProgn4Expected": (42, None),     # (PROGN 1 2 4 42)
            "Phase6SourcePrognSlotExpected": (99, None),  # (PROGN 1 (SETQ B 99) B)
            "Phase6SourceMultiSetqExpected": (3, None),   # (PROGN (SETQ A 1) (SETQ B 2) (PLUS A B))
            "Phase6SourceLetExpected": (7, None),         # (LET ((A 1) (B 2) (C 4)) (PLUS A (PLUS B C)))
            "Phase6SourceLambdaEntryExpected": (7, label_env("Phase6SourceLambdaEntryExpected")),
            "Phase6SourceLambdaWrapperPrognExpected": (7, label_env("Phase6SourceLambdaWrapperPrognExpected")),
        }
        for label, (want, env) in cases.items():
            mem = extract_acme_label(acme, label)
            got = eval_expected(mem, env)
            assert got == want, "%s: erwartet %d, dekodiert+ausgewertet %d (%r)" % (
                label, want, got, decode_top(mem))

        native_ccall = extract_source_data_label(acme, "Phase6SourceClosureCall1Expr")
        native_payload, native_literals = compile_payload(native_ccall, "object-closure")
        native_ast = decode_top(native_ccall, "object-closure")
        closure_ptr = native_ast[1][1]
        assert native_payload == bytes([
            VM_OP_CLOSURE, closure_ptr & 0xFF, (closure_ptr >> 8) & 0xFF,
            VM_OP_PUSHLIT8, 0, VM_OP_CALLCLOSURE1, VM_OP_PRINTACC, VM_OP_HALT])
        assert native_literals == [4]

        run_ccall = extract_source_data_label(
            acme, "Phase6SourceClosureCall1RunExpr")
        run_payload, run_literals = compile_payload(run_ccall, "object-closure")
        run_ast = decode_top(run_ccall, "object-closure")
        run_ptr = run_ast[1][1]
        assert run_ast == ("CALLCLOSURE1", ("CLOSURE", run_ptr), 4)
        assert run_payload == bytes([
            VM_OP_CLOSURE, run_ptr & 0xFF, (run_ptr >> 8) & 0xFF,
            VM_OP_PUSHLIT8, 0, VM_OP_CALLCLOSURE1, VM_OP_PRINTACC, VM_OP_HALT])
        assert run_literals == [4]

        lower_ccall = extract_source_data_label(
            acme, "Phase6SourceClosureCall1LowerExpected")
        lower_payload, lower_literals = compile_payload(lower_ccall, "object-closure")
        assert decode_top(lower_ccall, "object-closure") == native_ast
        assert lower_payload == native_payload
        assert lower_literals == native_literals

        lambda_closure = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureExpected")
        lambda_payload, lambda_literals = compile_payload(
            lambda_closure, "object-closure")
        lambda_ast = decode_top(lambda_closure, "object-closure")
        lambda_ptr = lambda_ast[1]
        assert lambda_payload == bytes([
            VM_OP_CLOSURE, lambda_ptr & 0xFF, (lambda_ptr >> 8) & 0xFF,
            VM_OP_HALT])
        assert lambda_literals == []

        lambda_capture = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCaptureExpected")
        lambda_capture_payload, lambda_capture_literals = compile_payload(
            lambda_capture, "object-closure")
        lambda_capture_ast = decode_top(lambda_capture, "object-closure")
        lambda_capture_ptr = lambda_capture_ast[1]
        assert lambda_capture_payload == bytes([
            VM_OP_CLOSURE, lambda_capture_ptr & 0xFF,
            (lambda_capture_ptr >> 8) & 0xFF, VM_OP_HALT])
        assert lambda_capture_literals == []
        lambda_capture_expected = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCapturePayloadExpected")
        assert lambda_capture_payload == lambda_capture_expected

        lambda_capture_negative = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCaptureNegativeExpected")
        lambda_capture_negative_payload, lambda_capture_negative_literals = (
            compile_payload(lambda_capture_negative, "object-closure"))
        lambda_capture_negative_ast = decode_top(
            lambda_capture_negative, "object-closure")
        assert lambda_capture_negative_ast == lambda_ast
        assert lambda_capture_negative_payload == lambda_payload
        assert lambda_capture_negative_literals == []

        lambda_ccall = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCallExpr")
        lambda_ccall_payload, lambda_ccall_literals = compile_payload(
            lambda_ccall, "object-closure")
        lambda_ccall_ast = decode_top(lambda_ccall, "object-closure")
        lambda_ccall_expected = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCallPayloadExpected")
        assert lambda_ccall_ast == (
            "CALLCLOSURE1", ("CLOSURE", lambda_ptr), 4)
        assert lambda_ccall_payload == lambda_ccall_expected
        assert lambda_ccall_literals == [4]

        lambda_run_ccall = extract_source_data_label(
            acme, "Phase6SourceLambdaClosureCallRunExpr")
        lambda_run_payload, lambda_run_literals = compile_payload(
            lambda_run_ccall, "object-closure")
        lambda_run_ast = decode_top(lambda_run_ccall, "object-closure")
        lambda_run_ptr = lambda_run_ast[1][1]
        assert lambda_run_ast == (
            "CALLCLOSURE1", ("CLOSURE", lambda_run_ptr), 4)
        assert lambda_run_payload == bytes([
            VM_OP_CLOSURE, lambda_run_ptr & 0xFF, (lambda_run_ptr >> 8) & 0xFF,
            VM_OP_PUSHLIT8, 0, VM_OP_CALLCLOSURE1, VM_OP_PRINTACC, VM_OP_HALT])
        assert lambda_run_literals == [4]

    print("phase4_srcexpr self-test: ALLES OK")


def main(argv):
    if not argv or "--selftest" in argv:
        _selftest()
        return 0
    if argv[0] == "--check-acme":
        profile = argv[1] if len(argv) > 1 else "frame"
        d = check_acme(profile=profile)
        print("Drift: %d" % d)
        return 1 if d else 0
    if argv[0] == "--check-capture-contract":
        d = check_capture_contract()
        print("Capture contract drift: %d" % d)
        return 1 if d else 0
    if argv[0] == "--check-lcall-lowering-contract":
        d = check_lcall_lowering_contract()
        print("LCALL lowering contract drift: %d" % d)
        return 1 if d else 0
    if argv[0] == "--check-diff-lcall-lowering-contract":
        d = check_diff_lcall_lowering_contract()
        print("Difference LCALL lowering contract drift: %d" % d)
        return 1 if d else 0
    if argv[0] == "--acme-label":
        profile = argv[2] if len(argv) > 2 else "frame"
        mem = extract_source_data_label(_acme_path(), argv[1])
        ast = decode_top(mem, profile)
        print("AST   :", ast)
        if profile == "object-closure":
            payload, literals = compile_payload(mem, profile)
            print("Payload:", " ".join("%02x" % b for b in payload))
            print("Lits  :", literals)
        else:
            print("Wert  :", phase4_vm.eval_ast(ast, label_env(argv[1])))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
