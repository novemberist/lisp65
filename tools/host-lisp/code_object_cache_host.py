"""Compile actual baseline/candidate V6 record seams into a differential host oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from code_object_cache_transform import DECLARATIONS, RECORD, transform

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/put-kit-product-r4/wplto/generated-product-sources/c2_product_runtime.c'


def body(source, start):
    begin = source.index(start)
    brace = source.index('{', begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]


PRELUDE = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define C2_KERNAL_RESIDENT
#define LISP65_C2_NESTED_APPEND_V5
#define LISP65_C2D_REGION_BYTES 50816u
#define LISP65_C2D_BASE 0u
#define LISP65_C2D_BANK 5u
struct context { uint16_t resolution_count, entry_count, entry_first, entries_offset, generation; };
static struct context c2_runtime;
static uint8_t c2_ready, fail_io, rows[2048][10];
static unsigned reads, writes;
static uint16_t c2_u16(const uint8_t *p) { return p[0] | (uint16_t)p[1]<<8; }
static void put16(uint8_t *p,uint16_t v) { p[0]=v;p[1]=v>>8; }
static uint16_t normalize(struct context *c,uint16_t h) {
 if(h>=4096u) return 0xffffu;
 if(h<2048u) return h<c->entry_count?h:0xffffu;
 return h<c->entry_first?0xffffu:(uint16_t)(h-2048u);
}
#define C2_HANDLE_NORMALIZE normalize
static uint8_t c2_stream_c2d_read(uint16_t off,void *dst,uint16_t len) {
 ++reads; if(fail_io) return 0;
 assert(off>=c2_runtime.entries_offset && len==10);
 off-=c2_runtime.entries_offset; assert(off%10==0 && off/10<2048);
 memcpy(dst,rows[off/10],10); return 1;
}
static void c2_facade_c2_dma(uint16_t a,uint8_t b,uint16_t c,uint8_t d,uint16_t n) {
 (void)a;(void)b;(void)c;(void)d;(void)n; ++writes;
}
'''
TEST = r'''
static uint32_t rng=1;
static uint32_t next(void) { rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng; }
static unsigned cases;
static void check(uint16_t h) {
 uint8_t a[10],b[10],ra,rb;uint16_t pa=0xeeee,pb=0xeeee;
 ra=baseline_record(h,a,&pa); rb=c2_product_entry_record(h,b,&pb);
 assert(ra==rb); if(ra) { assert(pa==pb);assert(!memcmp(a,b,10)); }
 ++cases;
}
int main(void) {
 c2_runtime=(struct context){4096,2048,2048,2096,7}; c2_ready=1;
 for(unsigned i=0;i<2048;++i) { rows[i][0]=i%64;put16(rows[i]+2,42);put16(rows[i]+4,17);put16(rows[i]+8,7); }
 for(unsigned i=0;i<=4096;++i) {
  check(i); unsigned before=reads;uint8_t r[10];uint16_t p;
  if(i<4096) {assert(c2_product_entry_record(i,r,&p)); assert(reads==before);}
 }
 /* Every valid offset, critical lengths around exact 64-KiB end and overflow. */
 for(unsigned off=0;off<65536u;++off) {
  uint32_t lengths[]={0,1,65535,65536u-off,(65536u-off+1)&65535u,(65536u-off-1)&65535u};
  for(unsigned k=0;k<6;++k) if(lengths[k]<65536u) {
   assert(c2_stream_c2d_write(0,0,0));put16(rows[0]+2,off);put16(rows[0]+4,lengths[k]);check(0);
  }
 }
 /* Resolution arithmetic, all bases and count extrema with varying limits. */
 for(unsigned base=0;base<65536u;++base) for(unsigned count=0;count<256u;count+=255) {
  assert(c2_stream_c2d_write(0,0,0));put16(rows[0]+2,42);put16(rows[0]+4,17);
  put16(rows[0]+6,base);rows[0][1]=count;
  c2_runtime.resolution_count=(uint16_t)next();check(0);check(2048);
 }
 /* Random rows include generation, image, length, resolution and zero literals. */
 for(unsigned i=0;i<200000u;++i) {
  assert(c2_stream_c2d_write(0,0,0));
  for(unsigned j=0;j<10;++j) rows[0][j]=next();
  if(i&1) put16(rows[0]+8,7);
  rows[0][0]&=127;check(0);check(0);
 }
 memset(rows[0],0,10);put16(rows[0]+2,42);put16(rows[0]+4,17);put16(rows[0]+8,7);
 c2_runtime.resolution_count=4096;assert(c2_stream_c2d_write(0,0,0));check(0);
 /* A same-generation rewrite must not return the previous cached bytes. */
 assert(c2_code_cache_key[1]);assert(c2_stream_c2d_write(0,0,0));put16(rows[0]+2,99);check(0);
 /* Warm lookup still obeys ready, normalization and transient watermark. */
 c2_ready=0;check(0);c2_ready=1;c2_runtime.entry_count=0;check(0);
 c2_runtime.entry_first=2049;check(2048);c2_runtime.entry_first=2048;check(2048);
 c2_code_cache_key[1]=0;fail_io=1;check(2048);assert(c2_code_cache_key[1]==0);fail_io=0;check(2048);
 uint16_t physical;uint8_t row[10];
 assert(!c2_product_entry_record(2048,0,&physical));assert(!c2_product_entry_record(2048,row,0));
 printf("PASS differential cases=%u reads=%u writes=%u\n",cases,reads,writes);
 return 0;
}
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    original=BASE.read_text(); candidate,inventory=transform(original)
    baseline=body(original,'C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(').replace('c2_product_entry_record','baseline_record',1)
    writer=body(candidate,'C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write(')
    harness=PRELUDE+DECLARATIONS+baseline+'\n'+RECORD+'\n'+writer+'\n'+TEST
    src=args.out/'oracle.c';src.write_text(harness)
    exe=args.out/'oracle';cmd=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(src),'-o',str(exe)]
    subprocess.run(cmd,check=True)
    result=subprocess.run([str(exe)],check=True,text=True,capture_output=True)
    (args.out/'output.txt').write_text(result.stdout)
    # A missing write invalidation must make the same tests fail.
    mutant=args.out/'mutant.c';mutant.write_text(harness.replace('c2_code_cache_key[1] = 0u; /* before any possible C2D mutation */','/* invalidation deliberately removed */'))
    mexe=args.out/'mutant';subprocess.run(['cc','-std=c11','-O2',str(mutant),'-o',str(mexe)],check=True)
    bad=subprocess.run([str(mexe)],capture_output=True,text=True)
    assert bad.returncode!=0,'missing-invalidation mutant survived'
    (args.out/'mutant-output.txt').write_text(bad.stdout+bad.stderr)
    def bind(path):
        d=path.read_bytes();return dict(path=str(path),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
    receipt=dict(status='PASS: DIFFERENTIAL RECORD ORACLE; NOT NATIVE QUALIFICATION',command=cmd,output=result.stdout.strip(),mutant_returncode=bad.returncode,inventory=inventory,inputs=[bind(BASE),bind(Path(__file__)),bind(Path(__file__).with_name('code_object_cache_transform.py')),bind(src)])
    (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(result.stdout.strip())

if __name__=='__main__':main()
