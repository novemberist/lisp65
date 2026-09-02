MEMORY {
  probe (rx) : ORIGIN = 0x2001, LENGTH = 0x022c
}

SECTIONS {
  .text 0x2001 : {
    KEEP(*(.text.c2_link34_crc_probe))
  } > probe
}

ASSERT(ADDR(.text) == 0x2001,
       "Link-34 CRC probe BASIC load address drift")
ASSERT(ADDR(.text) + SIZEOF(.text) <= 0x222d,
       "Link-34 CRC probe would overwrite the exact product leaf")
ASSERT(c2_link34_crc_probe_entry == 0x200d,
       "Link-34 CRC probe SYS entry drift")
