SECTIONS {
  .c2_v124_curve_mailbox 0x7000 (NOLOAD) : {
    __c2_v124_curve_mailbox_start = .;
    . = . + 0x0100;
    __c2_v124_curve_mailbox_end = .;
  } >ram
} INSERT AFTER .noinit;

ASSERT(__bss_end <= __c2_v124_curve_mailbox_start,
       "v1.2.4 Chip-RAM curve overlaps its mailbox");
ASSERT(__c2_v124_curve_mailbox_start == 0x7000
       && __c2_v124_curve_mailbox_end == 0x7100,
       "v1.2.4 Chip-RAM curve mailbox geometry drift");
