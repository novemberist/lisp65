/* Included by the owning product translation unit to avoid duplicate implementations. */
uint8_t vm_register_embedded(const vm_embed_entry *tab, uint16_t count) {
    while (count--) {
        uint8_t flags = tab->flags;
        obj sym;
        int di;
        if (flags & (uint8_t)~1u) return 0;
        sym = intern(tab->name);
        di  = vm_dir_add(sym, tab->bank, tab->off, tab->len);
        if (di < 0) return 0;
        if (flags & 1u) {
            obj m = alloc(T_MACRO);
            if (m == NIL) return 0;
            cell_set_a(m, MK_BCODE(di)); cell_set_b(m, NIL);
            set_sym_function(sym, m);
        } else {
            set_sym_function(sym, MK_BCODE(di));
        }
        tab++;
    }
    return 1;
}
