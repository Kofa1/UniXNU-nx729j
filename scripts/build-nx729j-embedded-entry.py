#!/usr/bin/env python3
"""Repackage an existing NX729J entry payload for the older Chinese ABL.

The Android ramdisk is empty. A self-relocating shim carries the unchanged FD,
a board FDT with explicit initrd bounds, and FAT in the compressed kernel.
No device, ABL, kernel code, platform identity or storage content is modified.
"""
import argparse,gzip,hashlib,json,os,shutil,struct,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--core',type=Path,required=True);p.add_argument('--uefi',type=Path,required=True)
p.add_argument('--entry',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--revision',type=int,default=5)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
core,uefi,entry,out=[v.resolve() for v in [a.core,a.uefi,a.entry,a.output]]
out.mkdir(parents=True,exist_ok=True);os.chmod(out,0o700)
sys.path.insert(0,str(core/'scripts'))
from unixnu.config import Context
from unixnu.cli import parser
from unixnu import bootimg
from unixnu.util import sha256_file
c=Context(parser().parse_args(['status','-D',str(repo),'--os','27','--uefi',str(uefi)]))
m=json.loads((entry/'manifest.json').read_text())
fat=entry/'payload.img';fd=uefi/'Build/nx729jPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd'
assert sha256_file(fd)==m['fd_sha256']=='54eafbac0ffc82aac1260196a75678f58b28a3eab3bbba100e627b57d71be9c0'
assert fd.stat().st_size==0x300000 and fat.stat().st_size==93*1024*1024
# Keep the private payload and its identity unchanged. Show the wrapper revision in docs/filename.
fatbytes=fat.read_bytes();assert fatbytes[510:512]==b'\x55\xaa'
parent_image=entry/(entry.name+'.img')
assert sha256_file(parent_image)==m['image_sha256']
parent_bytes=parent_image.read_bytes()
pk,_,pr,_,_,_,_,pp=struct.unpack_from('<8I',parent_bytes,8)
parent_offset=pp*(1+(pk+pp-1)//pp)
assert parent_bytes[parent_offset:parent_offset+pr]==fatbytes,'Parent FAT differs from delivered image'
sector=struct.unpack_from('<H',fatbytes,11)[0]
sectors=struct.unpack_from('<H',fatbytes,19)[0] or struct.unpack_from('<I',fatbytes,32)[0]
assert sector==512 and sector*sectors==len(fatbytes)
shim_size=0x1000;dtb_slot=0x100000;base=0xA8000000
fat_offset=shim_size+fd.stat().st_size+dtb_slot;total=fat_offset+len(fatbytes)
assert total%16==0 and base+total<=0xB7F00000
assert total < 0xB7F00000-0xA7000000-0x1000 # at least one trampoline is outside any source interval
handoff=out/'embedded-handoff.dtb';shutil.copyfile(entry/'device-tree/hardware.dtb',handoff)
def run(args):
 r=subprocess.run([str(x) for x in args],capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr.decode())
 return r
if subprocess.run(['fdtget','-p',str(handoff),'/chosen'],capture_output=True).returncode:
 run(['fdtput','-c',handoff,'/chosen'])
for key,value in [('linux,initrd-start',base+fat_offset),('linux,initrd-end',base+total)]:
 run(['fdtput','-t','x',handoff,'/chosen',key,'0',hex(value)])
 got=run(['fdtget','-t','x',handoff,'/chosen',key]).stdout.decode().split()
 assert [int(v,16) for v in got]==[0,value]
dtb=handoff.read_bytes();assert len(dtb)<=dtb_slot
obj=out/'embedded-shim.o';shimfile=out/'embedded-shim.bin'
run(['clang','--target=aarch64-none-elf','-c',f'-DBUNDLE_SIZE={total}',repo/'firmware/bootshim/EmbeddedPayload.S','-o',obj])
run(['llvm-objcopy','-O','binary',obj,shimfile]);shim=shimfile.read_bytes()
assert len(shim)==shim_size and shim[56:60]==b'ARM\x64'
assert struct.unpack_from('<QQ',shim,8)==(0xA7100000,total)
bundle=shim+fd.read_bytes()+dtb+bytes(dtb_slot-len(dtb))+fatbytes
assert len(bundle)==total
# Use the shared DTB fixups, Android image settings and container verifier.
settings,*_=bootimg.settings(c,uefi)
assert settings['header_version']==0
scratch=out/'packing';scratch.mkdir(exist_ok=True)
abl_dtb=bootimg.patch_dtb((entry/'device-tree/hardware.dtb').read_bytes(),c.board.get('bootimg',{}).get('dtb_node',[]),scratch)
kernel=scratch/'Image.gz-dtb';kernel.write_bytes(gzip.compress(bundle,compresslevel=6,mtime=0)+abl_dtb)
empty=scratch/'empty-ramdisk';empty.write_bytes(b'')
image=out/f'nx729j-ipados27-entry-{a.revision:02d}.img'
cmd=['python3',uefi/'Resources/Scripts/mkbootimg.py','--kernel',kernel,'--ramdisk',empty,'-o',image]
for key in bootimg.MKBOOTIMG_FLAGS:
 if key in settings:cmd+=['--'+key,str(settings[key])]
run(cmd)
record=bootimg.verify(image,bundle,abl_dtb,empty,settings)
assert image.stat().st_size<=96*1024*1024
record['android_kernel_sha256']=record.pop('kernel_sha256')
record.update(image_sha256=sha256_file(image),image_bytes=image.stat().st_size,fd_sha256=sha256_file(fd),payload_sha256=sha256_file(fat),kernel_sha256=m['kernel_sha256'],bundle_bytes=total,bundle_base=hex(base),fat_base=hex(base+fat_offset),fdt_base=hex(base+shim_size+fd.stat().st_size),payload_source='embedded in compressed kernel; Android ramdisk empty',parent_entry=entry.name,phone_tested=False,abl_modified=False,phone_operations=False)
(out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
(out/'SHA256SUMS.txt').write_text(record['image_sha256']+'  '+image.name+'\n')
os.chmod(image,0o600)
print(json.dumps(record,indent=2))
