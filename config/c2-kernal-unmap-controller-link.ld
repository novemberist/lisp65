/* Receipt-less C2 proof controller: reserve the cross-link mailbox instead
 * of treating an arbitrary low page as unused. */
SECTIONS {
  .lisp65_c2_controller_mailbox 0x3000 (NOLOAD) : {
    __c2ku_mailbox_start = .;
    . = . + 0x0200;
    __c2ku_mailbox_end = .;
  } >ram
} INSERT AFTER .noinit;

ASSERT(__bss_end <= __c2ku_mailbox_start,
       "C2 proof controller overlaps its shared mailbox");
ASSERT(__c2ku_mailbox_start == 0x3000 &&
       __c2ku_mailbox_end == 0x3200,
       "C2 proof mailbox geometry drift");
ASSERT(__c2ku_mailbox_end <= (__stack - 0x0200),
       "C2 proof mailbox violates the stack reserve");
