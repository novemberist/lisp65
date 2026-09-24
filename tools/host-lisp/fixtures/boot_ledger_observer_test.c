#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char main_ram[65536];
static struct {unsigned pc,a,x,y,sphi,s,op_cycles;} CPU65;
static unsigned linear;
static int in_hypervisor;
static unsigned memory_cpu_addr_to_linear(unsigned pc,void *unused){(void)pc;(void)unused;return linear;}
unsigned long long dwx_cpu_cycles_total;
#include "boot_ledger_observer.h"
static void setup(void){
    memset(main_ram,0,sizeof main_ram);memset(boot_seen,0,sizeof boot_seen);
    boot_phase=boot_world=-1;boot_done=0;in_hypervisor=0;
    CPU65.pc=linear=boot_boundaries[0].pc;
    memcpy(main_ram+CPU65.pc,boot_boundaries[0].sig,16);
    memcpy(main_ram+boot_boundaries[1].pc,boot_boundaries[1].sig,16);
}
static void reject(void){boot_observe_instruction(0);if(boot_phase!=-1)abort();}
int main(int argc,char **argv){
    if(argc!=2)abort();
    setenv("LISP65_BOOT_LEDGER",argv[1],1);
    setup();main_ram[CPU65.pc]^=1;reject();
    setup();linear+=65536;reject();
    setup();in_hypervisor=1;reject();
    setup();main_ram[boot_boundaries[1].pc]^=1;reject();
    setup();boot_world=1;reject();
    setup();dwx_cpu_cycles_total=100;boot_observe_instruction(13);
    if(boot_phase!=0)abort();
    dwx_boot_charge(0,7);dwx_boot_charge(1,11);
    if(boot_cpu[0]!=7 || boot_dma[0]!=11 || boot_pc[0][CPU65.pc]!=7)abort();
    fclose(boot_file);
    FILE *f=fopen(argv[1],"r");char line[256];if(!fgets(line,sizeof line,f))abort();
    if(strncmp(line,"E 0 113 ",8))abort();
    if(fgets(line,sizeof line,f))abort();
    fclose(f);
    puts("PASS: wrong opcode, nonidentity mapping, hypervisor, wrong world bytes, retired world rejected; within-step timestamp and CPU/DMA partition exact");
}
