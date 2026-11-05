#!/usr/bin/env python3
"""Assemble a size-bounded NX729J kernel-entry diagnostic, without a Data seed.

Uses the existing core ADT/FAT/Android packers. This deliberately stops short of
userland bring-up: owner-Data is compiled but no root transport is requested.
No phone operations are performed. Device identity is reused from an existing
private payload, never written to source or printed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import importlib.util

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--core', type=Path, required=True)
p.add_argument('--uefi', type=Path, required=True)
p.add_argument('--candidate-report', type=Path, required=True)
p.add_argument('--seed-from-payload', type=Path, required=True)
p.add_argument('--trust-cache', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--revision', type=int, default=1, help='Image filename and firmware menu revision')
a = p.parse_args()
assert a.revision > 0
revision = f'{a.revision:02d}'
root = Path(__file__).resolve().parents[1]
core, uefi, out = a.core.resolve(), a.uefi.resolve(), a.output.resolve()
subprocess.run(['python3', root/'scripts/check-nx729j-sec-heap.py', '--uefi', uefi], check=True)
sys.path.insert(0, str(core / 'scripts'))
from unixnu.cli import parser
from unixnu.config import Context
from unixnu import bootimg, payload, devicetree
from unixnu.util import sha256_file
ctx = Context(parser().parse_args(['status', '-D', str(root), '--os', '27', '--uefi', str(uefi)]))
ctx.uefi = uefi
assert ctx.tree.is_dir(), 'Resolved build tree missing'
plan = json.loads(a.candidate_report.read_text())
source = Path(plan['output'])
assert sha256_file(source) == plan['candidate_sha256'], 'Stale prelink report'
assert plan['missing'] == {} and sum(len(v) for v in plan['stubbed'].values()) == 4
assert set(plan['stubbed']) == {'com.apple.security.Image4'}
assert 'com.apple.security.Image4' in plan['personalities_dropped']
assert sha256_file(a.trust_cache) in ctx.board['payload']['trust_cache_sha256']
out.mkdir(parents=True, exist_ok=True)
os.chmod(out, 0o700)
stage = out/'stage'
if stage.exists(): shutil.rmtree(stage)
files = stage/'EFI/UniXNU/Payloads'
files.mkdir(parents=True)
kernel = files/'kernel.macho'
shutil.copyfile(source, kernel)
arguments = ['-v', 'serial=3', 'debug=0x14e', 'kt_fixed_zones=120', '-no_slto_panic',
             'use_contiguous_hint=0', 'native-source-storage=0', 'native-ufs-root=0',
             'sheng-log=0', 'sheng-smp=0', 'cpus=1']
line = payload.check_args(arguments)
env = dict(os.environ, UNIXNU_UEFI=str(uefi), UNIXNU_XNU_ARCH='arm64e', UNIXNU_IOS_VERSION='27.0')
subprocess.run(['python3', root/'scripts/patch-xnu-entry-probe.py', kernel,
                '--panic-screen', '--no-reset', '--milestones'], env=env, check=True)
subprocess.run(['python3', ctx.tree/'scripts/seal-source-crypto-kernel.py', kernel,
                '--kernel-args', line], env=env, check=True)
# Bound every delivered edit to a reviewed hook, unused executable padding,
# or the source provider's integrity field. Original kext code stays unchanged.
spec = importlib.util.spec_from_file_location('entry_probe', root/'scripts/patch-xnu-entry-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
before, after = source.read_bytes(), kernel.read_bytes()
assert len(before) == len(after)
probe.load_segments(before)
symbols = probe.rebase(source, before)
allowed = [(v, v+4) for v in (probe.ENTRY_VA, probe.MMU_ENABLE_VA, probe.AFTER_MMU_VA,
                              probe.PANIC_VA, symbols['_panic_trap_to_debugger'])]
allowed += [(probe.CAVES[n], probe.CAVES[n]+probe.CAVE_SIZE) for n in (1, 2, 3)]
allowed += [(probe.find_call(before, probe.kernel_symbols(source), '_arm_init', '_PE_init_platform', n)[0],
             probe.find_call(before, probe.kernel_symbols(source), '_arm_init', '_PE_init_platform', n)[0]+4) for n in (1, 2)]
tail = max(v+n for _, seg, v, n in probe.SECTIONS if seg == b'__TEXT_EXEC')
end = next(v+n for v, _, _, n in probe.SEGMENTS if v <= tail < v+n)
allowed.append((tail, end))
allowed += [(v, v+n) for name, _, v, n in probe.SECTIONS if name == b'__fips_hmacs']
file_ranges = [(probe.file_offset(v), probe.file_offset(v)+end-v) for v, end in allowed]
changed = 0
for page in range(0, len(before), 4096):
    if before[page:page+4096] == after[page:page+4096]: continue
    for i in range(page, min(page+4096, len(before))):
        if before[i] != after[i]:
            assert any(begin <= i < end for begin, end in file_ranges), f'Unexpected edit at file offset {i:#x}'
            changed += 1
print(f'PASS: {changed} changed bytes confined to diagnostic hooks/padding and POST HMAC')
# Recover only the existing private platform identity; never put it in argv.
with tempfile.TemporaryDirectory(prefix='nx729j-private-adt-') as td:
    old = Path(td)/'old.adt'
    subprocess.run(['mcopy', '-i', a.seed_from_payload.resolve(),
                    '::/EFI/UniXNU/Payloads/kernel.macho.adt', old], check=True, capture_output=True)
    blob = old.read_bytes()
    key = b'unique-chip-id'+bytes(32-len('unique-chip-id'))
    assert blob.count(key) == 1, 'Expected one identity in prior ADT'
    at = blob.index(key)
    assert struct.unpack_from('<I', blob, at+32)[0] == 8
    seed = format(struct.unpack_from('<Q', blob, at+36)[0], '08x')
# Stage-specific board settings live in this diagnostic recipe, not mainline.
ctx.work = out
ctx.logs = out/'logs'
ctx.logs.mkdir(exist_ok=True)
dtb = devicetree.compile_hardware(ctx)
(files/'kernel.macho.adt').write_bytes(devicetree.generate(
    dtb, ctx.board, unique_chip_id=seed, trust=True, data=False, root_policies=False))
del seed
shutil.copyfile(a.trust_cache, files/'kernel.macho.trustcache')
config = ('version = 1\n[boot]\ntimeout = 8\ndefault = "xnu"\n[kits]\nautoload = false\n'
          f'[[entry]]\nid = "xnu"\ntitle = "NX729J iPadOS 27 ENTRY-{revision} diagnostic - no root"\n'
          f'type = "xnu"\npath = "Payloads/kernel.macho"\nargs = "{line}"\n'
          '[[entry]]\nid = "tools"\ntitle = "Firmware tools and logs"\ntype = "action"\naction = "tools"\n'
          '[[entry]]\nid = "reset"\ntitle = "Restart"\ntype = "action"\naction = "reset"\n'
          '[[entry]]\nid = "shutdown"\ntitle = "Power off"\ntype = "action"\naction = "shutdown"\n')
(stage/'EFI/UniXNU/unixnu.toml').write_text(config)
for f in [stage, *stage.rglob('*')]: os.utime(f, (payload.EPOCH, payload.EPOCH))
fat = out/'payload.img'
payload.write_volume(stage, fat, 'NX729JENTRY', 93)
# Read back all delivered files from FAT, including the actual patched kernel.
with tempfile.TemporaryDirectory(prefix='nx729j-fat-check-') as td:
    for file in stage.rglob('*'):
        if file.is_file():
            dest = Path(td)/file.name
            subprocess.run(['mcopy', '-i', fat, '::/'+file.relative_to(stage).as_posix(), dest], check=True, capture_output=True)
            assert sha256_file(dest) == sha256_file(file), 'FAT readback mismatch'
fd = uefi/'Build/nx729jPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd'
assert sha256_file(fd) == '54eafbac0ffc82aac1260196a75678f58b28a3eab3bbba100e627b57d71be9c0', 'Unexpected firmware'
subprocess.run(['python3', root/'scripts/check-nx729j-sec-heap.py', '--uefi', uefi, '--fd', fd], check=True)
subprocess.run(['python3', root/'scripts/check-nx729j-memory-publication.py', '--uefi', uefi, '--fd', fd], check=True)
image = bootimg.build(ctx, uefi, fd, dtb, fat, out/f'nx729j-ipados27-entry-{revision}.img')
assert image.stat().st_size <= 96*1024*1024, 'Image exceeds saved boot_a size'
report = dict(stage='kernel-entry diagnostic; no root filesystem or Data seed',
              image_sha256=sha256_file(image), image_bytes=image.stat().st_size,
              saved_boot_partition_bytes=96*1024*1024, payload_bytes=fat.stat().st_size,
              base_candidate_sha256=plan['candidate_sha256'], kernel_sha256=sha256_file(kernel),
              kernel_args=line, fd_sha256=sha256_file(fd), trust_cache_sha256=sha256_file(a.trust_cache),
              hardware_tested=False, phone_operations=False, persistent_logs_guaranteed=False,
              entry_stage_values={'1':'MMU enabled', '2':'early PE_init_platform returned', '3':'late PE_init_platform returned'},
              limitations=['Four inactive-service TXM imports remain reporting stubs.',
                           'Panic screen requires a usable kernel framebuffer mapping.',
                           'Firmware tools logs cover firmware; kernel log persistence is unqualified.',
                           'Inherited vendor firmware behavior is not certified storage-write-free.',
                           'Saved boot_a size must be checked again before flashing.'])
(out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
(out/'SHA256SUMS.txt').write_text(report['image_sha256']+'  '+image.name+'\n')
os.chmod(image, 0o600)
print(json.dumps(report, indent=2))
