; SAVE-format LOAD smoke for a loaded function calling another loaded function.

(DE INNER (X) (PLUS X 1))
(DE ADDTWO (A B) (INNER (PLUS A B)))
