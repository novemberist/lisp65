"""Price a bounded six-entry resolver query; isolated objects, no product link."""
import inspect
from pathlib import Path
import traceback
import set_b_load_preflight_native_r2_20260926 as O
import set_b_producer as P

ROOT = P.ROOT
OUT = ROOT/'build/set-b-load-batch-native-r1'
HELPER = '''/* Synchronous read-only query. Every charged entry is validated,
 * including retired rows; batches never exceed the admitted 64-byte reader.
 * The automatic buffer has no escaping pointer and is dead before cons. */
_Static_assert(LISP65_C2_BANK2_CODE_LIMIT < 65536UL,
               "front query requires the bound sub-bank owner limit");
__attribute__((noinline)) obj c2_resolver_charged_front(void){
 uint8_t rows[60],n,j;uint16_t generation,count,offset=2096u,low=0;
 const uint16_t limit=(uint16_t)LISP65_C2_BANK2_CODE_LIMIT;
 if(!c2_ready || !c2_stream_c2d_read(10u,rows,8u))return NIL;
 generation=c2_u16(rows);count=c2_u16(rows+6);
 if(count>C2D_ENTRY_CAP)return NIL;
 while(count){
  n=count>6u ? 60u : (uint8_t)(count*10u);
  if(!c2_stream_c2d_read(offset,rows,n))return NIL;
  for(j=0;j<n;j+=10u){
   uint8_t *row=rows+j;
   uint16_t at=c2_u16(row+2),length=c2_u16(row+4),end;
   if(c2_u16(row+8)!=generation || !length || at>limit
      || length>(uint16_t)(limit-at))return NIL;
   end=at+length;if(end>low)low=end;
  }
  offset+=n;
  count=count>6u ? count-6u : 0u;
 }
 return cons(MKFIX(low&255u),MKFIX(low>>8));
}
'''


def main():
    folder = ROOT/'build/set-b-load-batch-native-driver-r1'
    folder.mkdir(exist_ok=False)
    source = inspect.getsource(O.main)
    (folder/'executed.py').write_text(source)
    P.write(folder/'binding.json', dict(driver=P.bind(Path(__file__)),
        parent=P.bind(Path(O.__file__)), executed=P.bind(folder/'executed.py'),
        changes='Only output root and exact helper replaced; same five-file proposal, matched four objects and dependency closure.'))
    ns = dict(vars(O)); ns.update(OUT=OUT, HELPER=HELPER, __file__=__file__)
    exec(compile(source, str(folder/'executed.py'), 'exec'), ns)
    ns['main']()


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        if OUT.exists():
            (OUT/'failure.txt').write_text(traceback.format_exc())
        raise
