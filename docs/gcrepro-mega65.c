/* MINIMAL-REPRO: eval_init (31 Prims) + gc_collect -> Freeze beim ersten gc_mark auf echter
 * MEGA65 (llvm-mos mega65-Target). Keine DMA, kein Reader, kein VM. Rahmen: 7=vor GC,
 * 5(gruen)=GC ueberlebt, dauerhaft 7=Freeze im GC. */
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "eval.h"
#define BORDER (*(volatile unsigned char*)0xD020)
#define BG     (*(volatile unsigned char*)0xD021)
const char *io_load_file(const char *n){(void)n;return 0;}
int main(void){
  BG=0; BORDER=0;
  eval_init();
  BORDER=7;              /* gelb: gleich kommt der GC */
  gc_collect();
  BORDER=5; BG=6;        /* gruen+blau: GC ueberlebt */
  for(;;){}
  return 0;
}
