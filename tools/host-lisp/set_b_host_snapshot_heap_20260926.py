"""Conservative nonmoving heap for long reference-VM resolver fixtures.

The reference VM otherwise never reclaims objects. At its allocation seam
this host-only adapter retains code literals, symbol cells/values and all
integer objects in active bytecode_p0 Python frames (including tail frames).
It may retain excess cells. It does not model or price the product collector.
"""
import sys
import bytecode_p0 as B

class SnapshotHeap(B.Heap):
    def __init__(self,original,root_provider,threshold=16000):
        self.__dict__.update(original.__dict__)
        self.root_provider=root_provider;self.threshold=threshold;self.free=[];self.collections=[]

    def collect(self,pending=()):
        roots=[];seen=set()
        def walk(v):
            if isinstance(v,int):roots.append(v);return
            if id(v) in seen:return
            seen.add(id(v))
            if isinstance(v,B.CodeObject):walk(v.littab)
            elif isinstance(v,dict):
                for k,x in v.items():walk(k);walk(x)
            elif isinstance(v,(list,tuple,set)):
                for x in v:walk(x)
        walk(self.symbols);walk(self.sym_values);walk(self.root_provider());walk(pending)
        f=sys._getframe().f_back
        while f:
            if f.f_code.co_filename==B.__file__:walk(f.f_locals)
            f=f.f_back
        marked=set();todo=roots
        while todo:
            obj=todo.pop()
            if not B.is_ptr(obj):continue
            i=B.to_u16(obj)>>1
            if not 0<i<len(self.cells) or i in marked or self.cells[i] is None:continue
            marked.add(i);cell=self.cells[i];todo.extend([cell.a,cell.b])
        self.free=[]
        for i in range(1,len(self.cells)):
            if i not in marked:self.cells[i]=None;self.free.append(i)
        self.collections.append(dict(arena=len(self.cells)-1,retained=len(marked),free=len(self.free)))

    def alloc(self,typ,a=B.NIL,b=B.NIL,name=''):
        if not self.free and len(self.cells)>=self.threshold:self.collect((a,b))
        if self.free:
            i=self.free.pop();self.cells[i]=B.Cell(typ,B.to_i16(a),B.to_i16(b),name);return B.to_i16(i<<1)
        return super().alloc(typ,a,b,name)

def selftest():
    h=B.Heap();keep=h.cons(B.mkfix(7),B.NIL);discard=h.cons(B.mkfix(9),B.NIL)
    x=SnapshotHeap(h,lambda:[keep]);x.collect()
    assert x.cell(keep).a==B.mkfix(7) and x.cells[B.to_u16(discard)>>1] is None
    new=x.cons(keep,B.mkfix(11));assert x.cell(new).a==keep and x.cell(new).b==B.mkfix(11)
    return 3
