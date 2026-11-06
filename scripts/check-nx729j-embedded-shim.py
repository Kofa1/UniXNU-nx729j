#!/usr/bin/env python3
"""Execute the production ARM64 relocation shim against overlapping layouts.

Requires unicorn==2.1.4 in a test venv. Cache maintenance is bypassed in this
memory-copy test; hardware cache behavior remains a phone-test requirement.
"""
from pathlib import Path
import subprocess,struct,tempfile,argparse,zlib
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_PC,UC_ARM64_REG_X0,UC_ARM64_REG_X23
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernel-blob',type=Path)
parser.add_argument('--shim-object',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
size=0x304000;fdsize=0x300000;base=0xA8000000;fd=0xA7100000
with tempfile.TemporaryDirectory(prefix='nx729j-shim-') as td:
 td=Path(td);obj=td/'shim.o';raw=td/'shim.bin'
 subprocess.run(['clang','--target=aarch64-none-elf','-c',f'-DBUNDLE_SIZE={size}',root/'firmware/bootshim/EmbeddedPayload.S','-o',obj],check=True)
 subprocess.run(['llvm-objcopy','-O','binary',obj,raw],check=True)
 names={x.split()[-1]:int(x.split()[0],16) for x in subprocess.check_output(['llvm-nm','-n',obj],text=True).splitlines() if len(x.split())==3}
 shim=raw.read_bytes();assert len(shim)==4096
 # A patterned firmware+tail exposes truncation, reversed lanes and source corruption.
 pattern=bytes(range(256))*4096
 data=(pattern*((size-4096+len(pattern)-1)//len(pattern)))[:size-4096]
 bundle=shim+data
 cases=[(source,bundle,names) for source in [0xA8000000,0xA7F00000,0xA8100000,0xA7000000,0xB7E00000]]
 if args.kernel_blob:
  assert args.shim_object
  actual=zlib.decompressobj(16+zlib.MAX_WBITS).decompress(args.kernel_blob.read_bytes())
  actual_names={x.split()[-1]:int(x.split()[0],16) for x in subprocess.check_output(['llvm-nm','-n',args.shim_object],text=True).splitlines() if len(x.split())==3}
  cases.append((0xA7000000,actual,actual_names))
 for source,bundle,names in cases:
  size=len(bundle)
  cpu=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
  cpu.mem_map(0xA6000000,0x16000000);cpu.mem_write(source,bundle)
  def skip_cache(mu,address,length,user):
   mu.reg_write(UC_ARM64_REG_PC,address+names['_CleanDone']-names['_Clean'])
  for location in [source,0xA7000000,0xB7F00000]:
   address=location+names['_Clean'];cpu.hook_add(UC_HOOK_CODE,skip_cache,begin=address,end=address)
  cpu.emu_start(source,fd,count=100_000_000)
  assert cpu.reg_read(UC_ARM64_REG_PC)==fd,f'Did not reach firmware; PC={cpu.reg_read(UC_ARM64_REG_PC):#x}'
  assert bytes(cpu.mem_read(base,size))==bundle,'Embedded bundle was overwritten during relocation'
  assert bytes(cpu.mem_read(fd,fdsize))==bundle[4096:4096+fdsize],'FD copy differs'
  assert cpu.reg_read(UC_ARM64_REG_X0)==base+4096+fdsize,'FDT handoff points elsewhere'
  chosen=cpu.reg_read(UC_ARM64_REG_X23)
  assert not(source<chosen+4096 and chosen<source+size),'Trampoline overlaps source'
  print(f'PASS: {size} bytes; source {source:#x}, trampoline {chosen:#x}, overlap-safe relocation and FD/FDT handoff')
 print('Cache maintenance skipped by emulator; phone qualification pending.')
