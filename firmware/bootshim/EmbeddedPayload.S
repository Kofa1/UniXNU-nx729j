/* NX729J ABL compatibility wrapper. No ABL modification or storage access.
 * Relocate the whole decompressed bundle into the board's reserved Kernel
 * window, restore the existing FD, and supply our own FAT initrd FDT.
 * The 4 KiB shim first moves outside both source and destination ranges.
 */
#ifndef BUNDLE_SIZE
#error BUNDLE_SIZE is required
#endif
#define SHIM_SIZE 0x1000
#define BUNDLE_BASE 0xA8000000
#define FD_BASE 0xA7100000
#define FD_SIZE 0x300000
#define TRAMP_LOW 0xA7000000
#define TRAMP_HIGH 0xB7F00000

.text
.global _Head, _Payload
_Head:
  adr x20, _Head
  b _Start
  .quad FD_BASE
  .quad BUNDLE_SIZE
  .quad 0
  .quad 0
  .quad 0
  .quad 0
  .ascii "ARM\x64"
  .long 0
_Start:
  /* A trampoline cannot overlap any input byte: moving it would damage FAT. */
  ldr x21, =BUNDLE_SIZE
  add x22, x20, x21
  ldr x23, =TRAMP_LOW
  add x8, x23, #SHIM_SIZE
  cmp x8, x20
  b.ls 1f
  cmp x23, x22
  b.hs 1f
  ldr x23, =TRAMP_HIGH
1:
  mov x4, x20
  mov x5, x23
  mov x6, #SHIM_SIZE
2:
  ldp x2, x3, [x4], #16
  stp x2, x3, [x5], #16
  subs x6, x6, #16
  b.ne 2b
  /* Publish the relocated shim before branching to it. */
  mov x8, x23
  add x7, x23, #SHIM_SIZE
  bl _Clean
  mov x8, #(_Stage2 - _Head)
  add x8, x23, x8
  br x8
_Stage2:
  ldr x24, =BUNDLE_BASE
  mov x4, x20
  mov x5, x24
  mov x6, x21
  cmp x4, x5
  b.eq 5f
  b.hi 3f
  /* Destination is above source: copy backwards, even if they overlap. */
  add x4, x4, x6
  add x5, x5, x6
4:
  ldp x2, x3, [x4, #-16]!
  stp x2, x3, [x5, #-16]!
  subs x6, x6, #16
  b.ne 4b
  b 5f
3:
  ldp x2, x3, [x4], #16
  stp x2, x3, [x5], #16
  subs x6, x6, #16
  b.ne 3b
5:
  /* Copy the unchanged firmware from the relocated bundle to its fixed FD. */
  add x4, x24, #SHIM_SIZE
  ldr x5, =FD_BASE
  ldr x6, =FD_SIZE
6:
  ldp x2, x3, [x4], #16
  stp x2, x3, [x5], #16
  subs x6, x6, #16
  b.ne 6b
  mov x8, x24
  add x7, x24, x21
  bl _Clean
  ldr x8, =FD_BASE
  ldr x7, =(FD_BASE + FD_SIZE)
  bl _Clean
_Firmware:
  /* Shared SEC and UniXNURamDiskDxe consume this normal FDT handoff. */
  ldr x0, =(BUNDLE_BASE + SHIM_SIZE + FD_SIZE)
  ldr x5, =FD_BASE
  br x5
_Clean:
  dsb sy
  mrs x9, ctr_el0
  ubfx x9, x9, #16, #4
  mov x10, #4
  lsl x9, x10, x9
  sub x10, x9, #1
  bic x8, x8, x10
7:
  dc cvac, x8
  add x8, x8, x9
  cmp x8, x7
  b.lo 7b
  dsb sy
  ic iallu
  dsb sy
  isb
_CleanDone:
  ret
.ltorg
.org SHIM_SIZE
_Payload:
