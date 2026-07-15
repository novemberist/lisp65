/* lisp65 - shared bytecode directory registration for boot and runtime loaders. */
#ifndef LISP65_VM_REGISTRY_H
#define LISP65_VM_REGISTRY_H

#include <stdint.h>

typedef struct {
    const char *name;
    uint8_t     bank;
    uint8_t     flags;
    uint16_t    off;
    uint16_t    len;
} vm_embed_entry;

/* Intern names, append code locations, and publish BCODE or macro function cells. */
uint8_t vm_register_embedded(const vm_embed_entry *tab, uint16_t count);

#endif /* LISP65_VM_REGISTRY_H */
