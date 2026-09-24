/* Host-only: no guest writes or side-effecting reads. */
#include "boot_boundaries.h"
extern unsigned long long dwx_cpu_cycles_total;
static int boot_phase=-1,boot_done,boot_world=-1;
static int boot_charge_disabled=-1;
static unsigned boot_seen[BOOT_N],boot_last_pc,boot_last_linear;
static unsigned long long boot_cpu[BOOT_N],boot_dma[BOOT_N],boot_pc[BOOT_N][65536];
static unsigned long long boot_nonidentity[BOOT_N],boot_hypervisor[BOOT_N],boot_interrupt[BOOT_N];
static FILE *boot_file;
static void boot_observe_instruction(unsigned elapsed) {
    boot_last_pc=CPU65.pc;boot_last_linear=memory_cpu_addr_to_linear(CPU65.pc,NULL);
    if(boot_done || !getenv("LISP65_BOOT_LEDGER"))return;
    for(unsigned i=0;i<BOOT_N;i++) {
        const struct boot_boundary *b=&boot_boundaries[i];
        if(CPU65.pc!=b->pc || in_hypervisor || boot_last_linear!=b->pc)continue;
        if(memcmp(main_ram+b->pc,b->sig,16))continue;
        if(b->world==0 && boot_world==1)continue;
        const struct boot_boundary *m=&boot_boundaries[b->world ? 5:1];
        if(memcmp(main_ram+m->pc,m->sig,16))continue;
        if(!boot_file){boot_file=fopen(getenv("LISP65_BOOT_LEDGER"),"w");if(!boot_file)abort();}
        fprintf(boot_file,"E %u %llu %u %u %u %u %u\n",i,dwx_cpu_cycles_total+elapsed,CPU65.a,CPU65.x,CPU65.y,CPU65.sphi|CPU65.s,main_ram[4]+256u*main_ram[5]);fflush(boot_file);
        boot_world=b->world;if(!boot_seen[i]++)boot_phase=i;
        if(i==BOOT_N-1){
            boot_done=1;
            for(unsigned j=0;j<BOOT_N;j++){
                fprintf(boot_file,"T %u %llu %llu %llu %llu %llu\n",j,boot_cpu[j],boot_dma[j],boot_nonidentity[j],boot_hypervisor[j],boot_interrupt[j]);
                for(unsigned pc=0;pc<65536;pc++)if(boot_pc[j][pc])fprintf(boot_file,"P %u %u %llu\n",j,pc,boot_pc[j][pc]);
            }
            fflush(boot_file);fclose(boot_file);boot_file=NULL;
        }
    }
}
void dwx_boot_charge(int dma,unsigned cycles){
    if(boot_charge_disabled<0)boot_charge_disabled=!!getenv("LISP65_BOOT_NO_CHARGE");
    if(boot_charge_disabled)return;
    if(boot_phase<0 || boot_done)return;
    if(dma)boot_dma[boot_phase]+=cycles;
    else {boot_cpu[boot_phase]+=cycles;boot_pc[boot_phase][boot_last_pc]+=cycles;
        if(boot_last_linear!=boot_last_pc)boot_nonidentity[boot_phase]+=cycles;
        if(in_hypervisor)boot_hypervisor[boot_phase]+=cycles;}
}
