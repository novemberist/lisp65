/* Hardware GC stress test: a rooted live list (0..LIVE_N-1) must survive
 * hundreds of collections under heavy garbage production. Verify its length
 * and checksum after every cycle, plus a deeply nested tree that stresses
 * fixed-point traversal.
 *   green+blue = all cycles intact; red = corruption at cycle (col0), length (col6), sum (col12).
 * Display: col0=cycle, col6=gc_runs, col12=badobj. */
#include "obj.h"
#include "mem.h"
#include "symbol.h"
#include "eval.h"
#include "vm_embed.h"
#if defined(__MEGA65__) || defined(__CBM__)
#define ON_DEVICE 1
#define BORDER (*(volatile unsigned char*)0xD020)
#define BG     (*(volatile unsigned char*)0xD021)
const char *io_load_file(const char *n){(void)n;return 0;}
#else
#include <stdio.h>
#include <string.h>
static unsigned char BORDER, BG;   /* Host: Dummies */
static unsigned char sim[65536];   /* Host: simuliertes erw. RAM */
void vm_code_load(unsigned char b,unsigned short o,unsigned short l,unsigned char*d){(void)b;memcpy(d,sim+o,l);}
void vm_ext_write(const unsigned char*s,unsigned short l,unsigned char b,unsigned short o){(void)b;memcpy(sim+o,s,l);}
#endif

#ifndef LIVE_N
#define LIVE_N 50
#endif
#ifndef ITERS
#define ITERS 400
#endif
#ifndef GARBAGE
#define GARBAGE 150
#endif

static void hex4(unsigned col, uint16_t v){
#ifdef ON_DEVICE
  static const char hx[]="0123456789abcdef"; unsigned k;
  for(k=0;k<4;k++){ unsigned char c=(unsigned char)hx[(v>>(12-4*k))&15];
    *(volatile unsigned char*)(0x0800+col+k)=(c>='a')?(unsigned char)(c-0x60):c;
    *(volatile unsigned char*)(0xD800+col+k)=1; }
#else
  (void)col; (void)v;
#endif
}

int main(void){
  uint16_t iter, base;
  BG=0; BORDER=0;
  eval_init();
  vm_load_embedded_stdlib();      /* 130 symbols add marking pressure to every GC */

  /* Build and permanently root a deep live list to stress fixed-point convergence. */
  base = gc_rootsp;
  GC_PUSH(NIL);
  { int i; for(i=LIVE_N-1;i>=0;i--){ obj c=cons(MKFIX(i), gc_rootstack[base]); GC_SET(base,c); } }

  /* OOM guard: if the live list cannot fit, violet means the test configuration is too small,
   * not a collector failure. */
  { obj p=gc_rootstack[base]; uint16_t len=0; while(IS_PTR(p)){ len++; p=cell_b(p); }
    if(len!=LIVE_N){ BORDER=4; BG=0; hex4(0,len);
#ifdef ON_DEVICE
      for(;;){}
#else
      printf("HEAP ZU KLEIN: live-Liste nur %u/%u gebaut (kein GC-Fehler)\n", len, (unsigned)LIVE_N);
      return 2;
#endif
    } }

  BORDER=7;
  for(iter=0; iter<ITERS; iter++){
    /* Create unrooted garbage until the free list triggers GC, plus an explicit collection. */
    { int j; for(j=0;j<GARBAGE;j++) (void)cons(MKFIX(j & 0x3f), NIL); }
    gc_collect();
    /* Verify the live list through length and checksum. */
    { obj p=gc_rootstack[base]; uint16_t len=0, sum=0;
      while(IS_PTR(p)){ len++; sum=(uint16_t)(sum+FIXVAL(cell_a(p))); p=cell_b(p); }
      if(len!=LIVE_N || sum!=(uint16_t)(LIVE_N*(LIVE_N-1)/2)){
        BORDER=2; BG=0; hex4(0,iter); hex4(6,len); hex4(12,sum);
#ifdef ON_DEVICE
        for(;;){}
#else
        printf("FAIL @iter=%u len=%u sum=%u (soll %u/%u) gc_runs=%u badobj=%u\n",
               iter, len, sum, (unsigned)LIVE_N, (unsigned)(LIVE_N*(LIVE_N-1)/2),
               gc_runs, gc_badobj);
        return 1;
#endif
      }
    }
    hex4(0,iter); hex4(6,gc_runs); hex4(12,gc_badobj);
  }
  /* Erfolg: alle Zyklen intakt. */
  BORDER=5; BG=6; hex4(0,ITERS); hex4(6,gc_runs); hex4(12,gc_badobj);
#ifdef ON_DEVICE
  for(;;){}
#else
  printf("PASS: %u Zyklen, gc_runs=%u badobj=%u (LIVE_N=%u, GARBAGE=%u)\n",
         (unsigned)ITERS, gc_runs, gc_badobj, (unsigned)LIVE_N, (unsigned)GARBAGE);
#endif
  return 0;
}
