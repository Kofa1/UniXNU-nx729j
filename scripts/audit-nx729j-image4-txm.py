#!/usr/bin/env python3
"""Audit the four 24A446 TXM imports; static evidence, not boot qualification."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--prelink-kit', required=True, type=Path)
p.add_argument('--kernelcache', required=True, type=Path)
p.add_argument('--candidate-report', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
sys.path.insert(0, str(a.prelink_kit.resolve()))
from kc_image import Image, scan

raw = a.kernelcache.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '38e6d9fa5f789b8228f4617ef4c6d2a3fd8ab564abdc9b62920f1db53fc1780a', 'Unexpected cache'
cache = Image(raw)
owner = 'com.apple.security.Image4'
image = Image(raw, cache.entries[owner][1])
kernel = Image(raw, cache.entries['com.apple.kernel'][1])
plan = json.loads(a.candidate_report.read_text())
candidate = Path(plan['output'])
assert hashlib.sha256(candidate.read_bytes()).hexdigest() == plan['candidate_sha256'], 'Stale report'
assert plan['inputs']['kernelcache_sha256'] == hashlib.sha256(raw).hexdigest()
assert owner in plan['personalities_dropped'], 'Image4 driver matching is enabled; reassess reachability'
assert plan['missing'] == {}, 'Additional unresolved references'
expected = {
    0xfffffe000b2a1694: (0xfffffe000a9e2694, 0xfffffe0008479bd8, 'service startup'),
    0xfffffe000b2a170c: (0xfffffe000a9e2b6c, 0xfffffe0008479bd0, 'user-client operation'),
    0xfffffe000b2a1778: (0xfffffe000a9e2dd0, 0xfffffe0008479bc0, 'user-client objectLoad'),
    0xfffffe000b2a1798: (0xfffffe000a9e2e00, 0xfffffe0008479bc8, 'user-client objectLoad'),
}
fixups = cache.fixups()
rows = []
for target, (pc, slot, context) in expected.items():
    assert fixups[slot][0] == target
    calls, _, _ = scan(image.read(pc, 4), pc)
    assert len(calls) == 1
    _, refs, _ = scan(cache.read(calls[0][1], 12), calls[0][1])
    assert slot in [v for _, v, _ in refs], 'Call no longer uses expected import'
    rows.append(dict(target=hex(target), callsite=hex(pc), import_slot=hex(slot), context=context))
# Both direct RPC wrappers and the other two wrappers' copying helpers converge
# on this dispatcher. Its own error strings identify TXM, rather than DER parsing.
starts = kernel.function_starts()
dispatch = 0xfffffe000b2a17c8
end = starts[starts.index(dispatch) + 1]
_, refs, _ = scan(kernel.read(dispatch, end-dispatch), dispatch)
strings = sorted({s for _, v, _ in refs if (s := kernel.cstring(v)) and 'TXM' in s})
assert any('Image4_V2' in s for s in strings), 'Dispatcher identity changed'
slide = int(plan['collection_slide'], 16)
stubs = {int(v, 16)-slide for owners in plan['stubbed'].values() for v in owners}
assert stubs == set(expected), 'Remaining stub set changed'
result = dict(kernelcache_sha256=hashlib.sha256(raw).hexdigest(),
              candidate_sha256=plan['candidate_sha256'], calls=rows,
              dispatcher=hex(dispatch), dispatcher_strings=strings,
              service_personality_removed=True, resolved=False,
              early_kernel_entry_blocker_established=False,
              full_userland_requirement='unqualified; inspect runtime consumers before enabling Image4 service',
              limitations=['Static direct-call audit only; indirect entry and runtime behavior are not qualified.',
                           'Retained library code is distinct from an automatically matched IOService.',
                           'Four imports still lead to the reporting panic stub if reached.'],
              hardware_tested=False)
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(result, indent=2)+'\n')
print('PASS: four TXM imports traced; Image4 service matching removed in this candidate. Runtime qualification pending.')
