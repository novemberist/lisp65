; Block 2.6 Card 2: ordinary entries into the shared mapped F011 owner.
; Bodies already executing under the MAP domain call their *_far entry
; directly, so the transitive nesting gate can prove that no mapped body
; reaches either MAP transition.

        .section .text.f011_read_at,"ax",@progbits
        .globl f011_read_at
        .type f011_read_at,@function
f011_read_at:
        jsr c2_mapped_far_enter
        jsr f011_read_at_far
        phx
        jsr c2_mapped_far_leave
        plx
        rts
        .size f011_read_at, .-f011_read_at

        .section .text.io_disk_read_sector,"ax",@progbits
        .globl io_disk_read_sector
        .type io_disk_read_sector,@function
io_disk_read_sector:
        jsr c2_mapped_far_enter
        jsr io_disk_read_sector_far
        jmp c2_mapped_far_leave
        .size io_disk_read_sector, .-io_disk_read_sector

        .section .text.disk_source_refill,"ax",@progbits
        .globl disk_source_refill
        .type disk_source_refill,@function
disk_source_refill:
        jsr c2_mapped_far_enter
        jsr disk_source_refill_far
        jmp c2_mapped_far_leave
        .size disk_source_refill, .-disk_source_refill
