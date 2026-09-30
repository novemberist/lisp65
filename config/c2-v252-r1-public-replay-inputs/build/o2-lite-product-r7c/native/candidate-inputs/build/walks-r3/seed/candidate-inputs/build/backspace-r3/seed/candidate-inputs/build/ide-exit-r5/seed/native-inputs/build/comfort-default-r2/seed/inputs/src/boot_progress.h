/* Product-owned cold-boot liveness.
 *
 * These macros deliberately emit only immediate stores.  They are expanded
 * into the owner that calls them: the separate AUTOBOOT stager, the disposable
 * heap boot overlay, or the transported C2 decoder phase.  There is no helper
 * symbol, string object, resident state or timing loop to survive into the
 * Workbench.
 *
 * The product linker proves the $0800, 80-column screen contract.  AUTOBOOT
 * runs on the same machine-owned screen immediately before that product.  The
 * final scr_init() clears these rows and the Bank-2 banner plus lisp65> prompt
 * become the terminal REPL life sign.
 */
#ifndef LISP65_BOOT_PROGRESS_H
#define LISP65_BOOT_PROGRESS_H

#include <stdint.h>

#if defined(__MEGA65__) && defined(LISP65_STARTUP_REQUIRE_EXPERIENCE)
#define LISP65_BOOT_PROGRESS_CELL(row, column, value) \
    (((volatile uint8_t *)0x0800u)[(uint16_t)(row) * 80u + (column)] = \
        (uint8_t)(value))
#define LISP65_BOOT_PROGRESS_CLEAR(row) do { \
    uint8_t lisp65_boot_progress_column_; \
    for (lisp65_boot_progress_column_ = 0u; \
         lisp65_boot_progress_column_ < 28u; \
         ++lisp65_boot_progress_column_) \
        LISP65_BOOT_PROGRESS_CELL( \
            (row), lisp65_boot_progress_column_, 0x20u); \
} while (0)
#define LISP65_BOOT_PROGRESS_PREFIX(row) do { \
    LISP65_BOOT_PROGRESS_CELL((row), 0u, 'L'); \
    LISP65_BOOT_PROGRESS_CELL((row), 1u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL((row), 2u, 'S'); \
    LISP65_BOOT_PROGRESS_CELL((row), 3u, 'P'); \
    LISP65_BOOT_PROGRESS_CELL((row), 4u, '6'); \
    LISP65_BOOT_PROGRESS_CELL((row), 5u, '5'); \
    LISP65_BOOT_PROGRESS_CELL((row), 6u, ':'); \
    LISP65_BOOT_PROGRESS_CELL((row), 7u, ' '); \
} while (0)
#define LISP65_BOOT_PROGRESS_STAGER() do { \
    LISP65_BOOT_PROGRESS_CLEAR(8u); \
    LISP65_BOOT_PROGRESS_PREFIX(8u); \
    LISP65_BOOT_PROGRESS_CELL(8u, 8u, 'S'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 9u, 'T'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 10u, 'A'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 11u, 'G'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 12u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 13u, 'N'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 14u, 'G'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 15u, ' '); \
    LISP65_BOOT_PROGRESS_CELL(8u, 16u, 'M'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 17u, 'E'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 18u, 'D'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 19u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(8u, 20u, 'A'); \
} while (0)
#define LISP65_BOOT_PROGRESS_HEAP() do { \
    LISP65_BOOT_PROGRESS_CLEAR(9u); \
    LISP65_BOOT_PROGRESS_PREFIX(9u); \
    LISP65_BOOT_PROGRESS_CELL(9u, 8u, 'B'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 9u, 'U'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 10u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 11u, 'L'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 12u, 'D'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 13u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 14u, 'N'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 15u, 'G'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 16u, ' '); \
    LISP65_BOOT_PROGRESS_CELL(9u, 17u, 'H'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 18u, 'E'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 19u, 'A'); \
    LISP65_BOOT_PROGRESS_CELL(9u, 20u, 'P'); \
} while (0)
#define LISP65_BOOT_PROGRESS_LIBRARIES() do { \
    LISP65_BOOT_PROGRESS_CLEAR(10u); \
    LISP65_BOOT_PROGRESS_PREFIX(10u); \
    LISP65_BOOT_PROGRESS_CELL(10u, 8u, 'L'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 9u, 'O'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 10u, 'A'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 11u, 'D'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 12u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 13u, 'N'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 14u, 'G'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 15u, ' '); \
    LISP65_BOOT_PROGRESS_CELL(10u, 16u, 'L'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 17u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 18u, 'B'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 19u, 'R'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 20u, 'A'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 21u, 'R'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 22u, 'I'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 23u, 'E'); \
    LISP65_BOOT_PROGRESS_CELL(10u, 24u, 'S'); \
} while (0)
#else
#define LISP65_BOOT_PROGRESS_STAGER() ((void)0)
#define LISP65_BOOT_PROGRESS_HEAP() ((void)0)
#define LISP65_BOOT_PROGRESS_LIBRARIES() ((void)0)
#endif

#endif
