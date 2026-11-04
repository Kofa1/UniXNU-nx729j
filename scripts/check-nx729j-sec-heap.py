#!/usr/bin/env python3
"""Exercise Silicium's real name lookup against the NX729J memory table."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--uefi', type=Path, default=os.environ.get('UNIXNU_UEFI'))
p.add_argument('--fd', type=Path, help='also verify the actual SEC memory descriptor in a built firmware volume')
a = p.parse_args()
if not a.uefi: p.error('--uefi or UNIXNU_UEFI required')
r = a.uefi.resolve()
table = (r/'Platforms/ZTE/nx729jPkg/Library/MemoryMapLib/MemoryMapLib.c').read_text()
helper = (r/'Silicon/Silicium/SiliciumPkg/Library/MemoryMapHelperLib/MemoryMapHelper.c').read_text()
sec = (r/'Silicon/Silicium/SiliciumPkg/Sec/Sec.c').read_text()
assert 'LocateMemoryRegionByName ("DXE Heap", &UefiMemoryRegion)' in sec
assert 'LocateMemoryRegionByName ("DXE_Heap", &UefiMemoryRegion)' in sec
lookup = helper[helper.index('EFI_STATUS'):helper.index('EFI_STATUS', helper.index('EFI_STATUS')+1)]
body = re.sub(r'^#include.*$', '', table, flags=re.M)
rows = re.findall(r'\{"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+),([^}]+)\}',table)
identifiers = sorted({word for _,_,_,attrs in rows for word in re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b',attrs)})
pre = '''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define STATIC static
#define VOID void
#define IN
#define OUT
#define EFIAPI
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 2
#define EFI_INVALID_PARAMETER 3
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define AsciiStriCmp strcasecmp
typedef char CHAR8; typedef uint8_t UINT8; typedef int EFI_STATUS;
typedef struct { char Name[32]; uint64_t Address, Length; int Hob, Resource, Attributes, Type, Arm; } EFI_MEMORY_REGION_DESCRIPTOR;
'''
main = '''
int main(void) {
  EFI_MEMORY_REGION_DESCRIPTOR region = {0}, saved;
  int first = LocateMemoryRegionByName("DXE Heap", &region);
  saved = region;
  int alias = LocateMemoryRegionByName("DXE_Heap", &region);
  if (first != EFI_SUCCESS || alias != EFI_NOT_FOUND || memcmp(&saved,&region,sizeof(region)) ||
      region.Address != 0xBAB00000ULL || region.Length != 0x05500000ULL || region.Type != Conv) {
    fprintf(stderr,"FAIL: SEC DXE Heap lookup/alias/bounds contract\\n"); return 1;
  }
  puts("PASS: production lookup resolves SEC DXE Heap, preserves it on alias miss, and uses the bounded first bank");
  return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='nx729j-sec-heap-') as td:
    td = Path(td)
    source = td/'check.c'
    source.write_text(pre+'enum { '+', '.join(identifiers)+' };\n'+body+'\n'+lookup+'\n'+main)
    subprocess.run(['clang','-Wall','-Wextra','-Werror',str(source),'-o',str(td/'check')],check=True)
    subprocess.run([str(td/'check')],check=True)
# Preserve the reserved ramoops hole and both non-overlapping heap ranges.
regions = {name:(int(base,16),int(size,16)) for name,base,size,_ in rows}
assert regions['Ramoops'] == (0xc0000000,0x200000)
for name in ['DXE Heap','DXE Heap 1']:
    base,size=regions[name];rb,rs=regions['Ramoops'];assert base+size<=rb or base>=rb+rs
assert regions['DXE Heap 1'] == (0xc0200000,0x7fc0000)
print('PASS: reserved ramoops gap retained between the two heaps')
if a.fd:
    fd = a.fd.read_bytes()
    def descriptor(name):
        return name.encode().ljust(32, b'\0') + struct.pack('<QQ', 0xbab00000, 0x05500000)
    assert len(fd) == 0x300000
    assert descriptor('DXE Heap') in fd, 'Built FD lacks the corrected SEC heap descriptor'
    assert descriptor('DXE Heap 0') not in fd, 'Built FD still contains the broken SEC descriptor'
    print('PASS: built FD contains the corrected SEC descriptor and excludes the broken one')
