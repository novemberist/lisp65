"""Split cache allocation, preserving all accepted owners and both BSS floors."""
ROW = '''
.lisp65_code_cache_row __storage_soft_frames_end (NOLOAD) : {
    __lisp65_code_cache_row_start = .;
    KEEP(*(.lisp65_code_cache_row))
    __lisp65_code_cache_row_end = .;
} >c_writeable
ASSERT(SIZEOF(.lisp65_code_cache_row) == 10, "code cache row size drift")
ASSERT(__lisp65_code_cache_row_end + 5 <= ADDR(.lisp65_c2_input_raw_owner), "code cache low BSS floor")
'''
KEY = '''
.lisp65_code_cache_key __lisp65_c2_symbol_metadata_bss_end (NOLOAD) : {
    __lisp65_code_cache_key_start = .;
    KEEP(*(.lisp65_code_cache_key))
    __lisp65_code_cache_key_end = .;
    __bss_end = .;
} >c_writeable
ASSERT(SIZEOF(.lisp65_code_cache_key) == 2, "code cache key size drift")
ASSERT(__lisp65_code_cache_key_end + 5 <= 0xc000, "code cache high BSS floor")
'''


def transform(text):
    if '.lisp65_code_cache' in text:
        raise ValueError('cache linker already transformed')
    before='\n.lisp65_c2_input_raw_owner 0xbc90 (NOLOAD) : {'
    if text.count(before)!=1 or text.count('__bss_size = __bss_end - __bss_start;')!=1:
        raise ValueError('cache linker predecessor drift')
    text=text.replace(before,'\n'+ROW+before,1)
    return text.replace('__bss_size = __bss_end - __bss_start;',KEY+'\n__bss_size = __bss_end - __bss_start;',1)
