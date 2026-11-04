#!/usr/bin/env python3
"""Apply NX729J's reviewed 24A446 symbol anchors to the pinned XnuPrelink fixture."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRELINK = (ROOT / 'kits/XnuPrelink').resolve()
CORE = PRELINK.parents[1]
EXPECTED_CORE = '474cfeeb4e35b3fc91ec98cd2bb54e1ab25389b8'
EXPECTED_PRELINK = 'b1888c12456c46a2226d63c794465dfcee08d465'

def commit(repo):
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()

if commit(CORE) != EXPECTED_CORE or commit(PRELINK) != EXPECTED_PRELINK:
    raise SystemExit('NX729J fileset anchors require UniXNU 474cfeeb and XnuPrelink b1888c12')
fixture = PRELINK / 'fixtures/fileset-24A446-symbols.json'
data = json.loads(fixture.read_text())
anchors = {
 'functions': [
  {'original':'0xfffffe000ad94128','original_size':16,'original_sha256':'486f0d0485670e933a6986389c215972ab15ae46a265bfa627f24f6f43ee3ab1','native_symbol':'_thread_tid','evidence':'Checks for a null thread pointer and returns thread->thread_id. Original code loads the 64-bit field at +0x4f0; the same pinned XNU source implementation is thread.c:3057, and native _thread_tid reads the native-layout field at +0x5e8. Matching the source operation preserves each build’s own thread layout.'},
  {'original':'0xfffffe000ad94e9c','original_size':84,'original_sha256':'15e9c81465efac6623f23e50ec9ccfe028aa75f4b8d009b2ad9962c2639727a8','native_symbol':'_thread_set_allocation_name','evidence':'Reads current_thread()->kernel_state->allocation_name, returns its old value, and writes the new value only when it is zero or no name was set. Original code reads TPIDR_EL1+336 and the state field at +192; the same pinned XNU source implementation is thread.c:3924 and native _thread_set_allocation_name uses the native thread layout.'},
 ],
 'data': [
  {'original':'0xfffffe00070446a8','native_symbol':'_PE_arm_debug_panic_hook','addend':0,'evidence':'The AppleARMWatchdogTimer and AppleProcessorTrace GOT sites resolve to this exact original kernelcache slot. The symbol is the exported XNU variable PE_arm_debug_panic_hook (pexpert/arm/hwtrace/hwtrace.c); RELEASE declares a const NULL pointer, while the native DEVELOPMENT build exports the same variable as the debug panic-hook pointer. This maps the imported API identity to the symbol produced by the selected DEVELOPMENT configuration.'},
  {'original':'0xfffffe000b8b3ce8','native_symbol':'_debugger_panic_caller','addend':0,'evidence':'IOHIDFamily imports the original debugger_panic_caller slot. In the exact 24A446 kernelcache, it is at +0x34 from the matched _debugger_current_op global; the following globals match debugger.c declarations (panic string, args, data, options, message, caller). XNU source defines unsigned long debugger_panic_caller in osfmk/kern/debug.c; the native DEVELOPMENT kernel exports that variable at the symbol address. The source-backed identity maps across the differing debugger_op padding.'},
 ],
 'sites': [
  {'site':'0xfffffe0008153010','native_symbol':'_ml_set_interrupts_enabled_with_debug','evidence':'ApplePMGR __DATA_CONST site 0xfffffe0008153010 is an authenticated pointer to original function 0xfffffe000ad6df18 in the exact 24A446 kernelcache. The target contains the __func__ name ml_set_interrupts_enabled_with_debug, its machine_routines_common.c marker, and the function’s exact debug-exceptions panic text; its instructions read DAIF. The pinned XNU declaration has boolean (enable, debug) arguments and a boolean return. Bind only this ApplePMGR import to the same source API in the native build, preserving the rest of the function map.'},
 ]
}
changed = False
for section, entries in anchors.items():
    key_field = 'site' if section == 'sites' else 'original'
    existing = {entry[key_field]: entry for entry in data.get(section, [])}
    for entry in entries:
        prior = existing.get(entry[key_field])
        if prior is not None and prior != entry:
            raise SystemExit(f'conflicting {section} anchor for {entry[key_field]}')
        if prior is None:
            data.setdefault(section, []).append(entry)
            existing[entry[key_field]] = entry
            changed = True
if changed:
    fixture.write_text(json.dumps(data, indent=2) + '\n')
print('NX729J 24A446 prelink anchors present' if not changed else 'Applied reviewed NX729J 24A446 prelink anchors')
