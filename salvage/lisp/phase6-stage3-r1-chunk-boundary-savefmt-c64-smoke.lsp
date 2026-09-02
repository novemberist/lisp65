; SAVE-format C64 smoke for R1 chunk-boundary stress.
; Der emittierte Record ist ~190 Zeichen lang, sodass beim LOAD mehrere
; InputLineLimit-lBUF-Chunks nachgefuellt werden. Das Atom streckt sich ueber die
; erste 88er-Grenze, das String-Literal ueber die zweite (~176) -- genau die
; Faelle, die ReadNextLine / ReadNextLine4 fortsetzen muessen.
; Das Atom bleibt <= 88 Zeichen, liegt aber so im Record,
; dass es die Eingabe-Chunkgrenze kreuzt.

(DE R1CHUNKBOUNDARY ()
  (LIST
    'R1OK
    'R1LONGATOMTOKENSTRADDLINGTHEEIGHTYCHARINPUTCHUNK
    "R1-LONG-STRING-LITERAL-THAT-CROSSES-THE-ONE-HUNDRED-SIXTY-CHARACTER-SECOND-CHUNK-BOUNDARY"))
