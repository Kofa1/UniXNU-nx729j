#!/usr/bin/env python3
"""Exercise the production helper with an allocator that can choose newly published RAM."""
import argparse
import hashlib
import lzma
import struct
import uuid
import os
from pathlib import Path
import re
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--uefi',type=Path,default=os.environ.get('UNIXNU_UEFI'))
p.add_argument('--fd',type=Path,help='verify rebuilt RamManagerDxe is actually embedded in this FD')
p.add_argument('--baseline',action='store_true',help='reproduce the unsafe order in the pinned source')
a=p.parse_args()
if not a.uefi:p.error('--uefi or UNIXNU_UEFI required')
r=a.uefi.resolve();rel='Silicon/Silicium/SiliciumPkg/Library/MemoryAllocationHelperLib/MemoryAllocationHelper.c'
source=subprocess.check_output(['git','-C',r,'show','HEAD:'+rel],text=True) if a.baseline else (r/rel).read_text()
source=re.sub(r'^#include.*$','',source,flags=re.M)
pre='''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define IN
#define EFI_ERROR(s) ((s)!=0)
#define MAX_UINT64 UINT64_MAX
#define EFI_SUCCESS 0
#define EFI_UNSUPPORTED 1
#define EFI_INVALID_PARAMETER 2
#define EFI_ACCESS_DENIED 3
#define ARM_MEMORY_REGION_ATTRIBUTE_WRITE_BACK 1
#define ARM_MEMORY_REGION_ATTRIBUTE_DEVICE 2
#define EFI_MEMORY_WB 8
#define EFI_MEMORY_UC 1
typedef uint64_t UINT64; typedef uint64_t EFI_PHYSICAL_ADDRESS;
typedef int EFI_STATUS; typedef int EFI_MEMORY_TYPE; typedef int EFI_GCD_MEMORY_TYPE;
enum {EfiConventionalMemory, EfiMemoryMappedIO};
enum {EfiGcdMemoryTypeNonExistent, EfiGcdMemoryTypeSystemMemory, EfiGcdMemoryTypeMemoryMappedIo};
typedef struct {uint64_t BaseAddress,Length; int GcdMemoryType;} EFI_GCD_MEMORY_SPACE_DESCRIPTOR;
static int published,mapped,failmap,failadd,failattr,occupied,shortgap,systemram;
static char order[32]; static int used;
static void mark(char c){order[used++]=c;order[used]=0;}
static void reset(void){published=mapped=failmap=failadd=failattr=occupied=shortgap=systemram=used=0;memset(order,0,sizeof(order));}
static int query(uint64_t base,EFI_GCD_MEMORY_SPACE_DESCRIPTOR *d){mark('Q');d->BaseAddress=base;d->Length=shortgap?4096:0x400000;d->GcdMemoryType=occupied?EfiGcdMemoryTypeSystemMemory:EfiGcdMemoryTypeNonExistent;return 0;}
static int add(int type,uint64_t base,uint64_t length,uint64_t caps){(void)base;(void)length;(void)caps;mark('P');if(failadd)return 5;systemram=type==EfiGcdMemoryTypeSystemMemory;published=1;return 0;}
static int attributes(uint64_t base,uint64_t length,uint64_t attr){(void)base;(void)length;(void)attr;mark('S');return failattr?6:0;}
static int ArmSetMemoryAttributes(uint64_t base,uint64_t length,uint64_t attr,uint64_t mask){(void)base;(void)length;(void)attr;(void)mask;mark('M');if(published&&systemram&&!mapped)return 9;/* translation-table allocation chose the unmapped newly published page */if(failmap)return 4;mapped=1;return 0;}
static struct {int (*AddMemorySpace)(int,uint64_t,uint64_t,uint64_t);int (*SetMemorySpaceAttributes)(uint64_t,uint64_t,uint64_t);int (*GetMemorySpaceDescriptor)(uint64_t,EFI_GCD_MEMORY_SPACE_DESCRIPTOR*);} services={add,attributes,query},*gDS=&services;
'''
main='''int main(void){reset();int status=MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory);
#ifdef BASELINE
assert(status==9 && published && !mapped && !strcmp(order,"PM"));puts("PASS: pinned helper reproduces allocation from published-but-unmapped RAM");
#else
assert(status==0 && mapped && published && !strcmp(order,"QMPS"));
reset();failmap=1;assert(MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory)==4 && !published);
reset();failadd=1;assert(MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory)==5 && mapped && !published);
reset();occupied=1;assert(MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory)==EFI_ACCESS_DENIED && !mapped && !published);
reset();shortgap=1;assert(MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory)==EFI_ACCESS_DENIED && !mapped && !published);
reset();assert(MapMemoryRegion(UINT64_MAX-4095,8192,EfiConventionalMemory)==EFI_INVALID_PARAMETER && used==0);
reset();assert(MapMemoryRegion(0x80e00000,0,EfiConventionalMemory)==EFI_INVALID_PARAMETER && used==0);
reset();failattr=1;assert(MapMemoryRegion(0x80e00000,0x400000,EfiConventionalMemory)==6 && mapped && published);
reset();assert(MapMemoryRegion(0x80e00000,0x400000,EfiMemoryMappedIO)==0 && !strcmp(order,"PMS"));
puts("PASS: production helper maps before publication; failure, overlap, overflow and unchanged MMIO paths checked");
#endif
return 0;}
'''
with tempfile.TemporaryDirectory(prefix='nx729j-publish-test-') as td:
 td=Path(td);(td/'check.c').write_text(pre+source+main)
 cmd=['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(td/'check.c'),'-o',str(td/'check')]
 if a.baseline:cmd.insert(1,'-DBASELINE')
 subprocess.run(cmd,check=True);subprocess.run([str(td/'check')],check=True)

if a.fd:
 data=a.fd.read_bytes();guided=uuid.UUID('ee4e5898-3914-4259-9d6e-dc7bd79403cf').bytes_le
 raw=None;pos=0
 while (pos:=data.find(guided,pos))>=0:
  start=pos-4;pos+=16
  if start<0 or data[start+3]!=2:continue
  size=int.from_bytes(data[start:start+3],'little');offset=struct.unpack_from('<H',data,start+20)[0]
  if not 24<=offset<size or start+size>len(data):continue
  try:decoded=lzma.decompress(data[start+offset:start+size])
  except lzma.LZMAError:continue
  if b'_FVH' in decoded[:64]:raw=decoded;break
 assert raw is not None,'Compressed firmware volume not found'
 base=raw.index(b'_FVH')-40;end=base+struct.unpack_from('<Q',raw,base+32)[0]
 assert 0<=base<end<=len(raw)
 pos=(base+struct.unpack_from('<H',raw,base+48)[0]+7)&~7
 guid=uuid.UUID('f4c010c0-96f1-4b49-bfda-e982b807f44e').bytes_le;found=[]
 while pos+24<=end:
  size=int.from_bytes(raw[pos+20:pos+23],'little')
  if size<24 or pos+size>end:break
  if raw[pos:pos+16]==guid:
   section=pos+24
   while section+4<=pos+size:
    length=int.from_bytes(raw[section:section+3],'little')
    assert length>=4 and section+length<=pos+size
    if raw[section+3]==16:found.append(raw[section+4:section+length])
    section=(section+length+3)&~3
  pos=(pos+size+7)&~7
 assert len(found)==1,'Expected exactly one RamManagerDxe PE image'
 module=r/'Build/nx729jPkg/DEBUG_CLANGPDB/AARCH64/RamManagerDxe.efi'
 assert found[0]==module.read_bytes(),'FD contains a different or stale RamManagerDxe'
 print('PASS: actual FD embeds rebuilt RamManagerDxe SHA256 '+hashlib.sha256(found[0]).hexdigest())
