#include <stdio.h>
#include <stdlib.h>

struct write_event {
    unsigned int address;
    unsigned char value;
};

static unsigned char registers[0x10000u];
static struct write_event trace[8];
static unsigned int trace_count;

static void record_write(unsigned int address, unsigned char value) {
    if (trace_count >= sizeof trace / sizeof trace[0]) abort();
    trace[trace_count].address = address;
    trace[trace_count].value = value;
    trace_count++;
    registers[address] = value;
}

#define LISP65_F011_WRITE8(address, value) \
    record_write((unsigned int)(address), (unsigned char)(value))
#include "f011_context.h"

static void expect(unsigned int index, unsigned int address, unsigned char value) {
    if (index >= trace_count || trace[index].address != address || trace[index].value != value) {
        fprintf(stderr, "f011-context: trace mismatch at %u\n", index);
        exit(1);
    }
}

int main(void) {
    registers[LISP65_SD_REG_COMMAND] = LISP65_BUFFER_WINDOW_MAP;
    registers[LISP65_F011_REG_CONTROL] = 0xffu;
    registers[LISP65_SD_REG_BUFFER_SELECT] = 0x80u; /* freezer/direct-SD state */

    lisp65_f011_take_context();
    lisp65_f011_map_buffer();
    lisp65_f011_unmap_buffer();

    if (trace_count != 5u) {
        fprintf(stderr, "f011-context: write count mismatch: %u\n", trace_count);
        return 1;
    }
    expect(0, LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_UNMAP);
    expect(1, LISP65_F011_REG_CONTROL, LISP65_F011_DRIVE0_MOTOR);
    expect(2, LISP65_SD_REG_BUFFER_SELECT, LISP65_F011_BUFFER_SELECTED);
    expect(3, LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_MAP);
    expect(4, LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_UNMAP);
    if (registers[LISP65_SD_REG_BUFFER_SELECT] != 0x00u ||
        registers[LISP65_SD_REG_COMMAND] != 0x82u ||
        registers[LISP65_F011_REG_CONTROL] != 0x60u) {
        fputs("f011-context: final register context mismatch\n", stderr);
        return 1;
    }
    puts("f011-context: PASS forced-D689=80 reclaimed, F011 selected, window closed");
    return 0;
}
