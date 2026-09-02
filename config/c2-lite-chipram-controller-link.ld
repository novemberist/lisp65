SECTIONS {
  .lisp65_c2lt_mailbox 0x7000 (NOLOAD) : {
    __c2lt_mailbox_start = .;
    . = . + 0x0100;
    __c2lt_mailbox_end = .;
  } >ram
} INSERT AFTER .noinit;

ASSERT(__bss_end <= __c2lt_mailbox_start,
       "C2-lite proof controller overlaps mailbox");
ASSERT(__c2lt_mailbox_start == 0x7000 && __c2lt_mailbox_end == 0x7100,
       "C2-lite proof mailbox geometry drift");
ASSERT(__c2lt_mailbox_end <= 0x8000,
       "C2-lite proof mailbox overlaps fixed source scratch");
