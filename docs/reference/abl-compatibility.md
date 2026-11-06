# NX729J ABL compatibility comparison — 2026-11-06

The user reports that switching ABL to enable the fastboot button combination coincided with UniXNU showing `no boot entry found`. Read-only fastboot checks: current slot a, is-userspace no, boot_a 0x6000000, max-download-size 805306368; slot a successful and bootable. Bootloader fetch is unsupported. No assistant flash was performed.

| Input | SHA-256 | File bytes | Embedded build path |
| --- | --- | ---: | --- |
| Stock `/Volumes/Untitled/RM8PROEEA/abl.img` | 29ec6899e408bd03e22c23ed274effbf98ff45a47369e0994e1fa79f5bef59a4 | 212992 | NX729S_EEA_U_SM8550_U_TA_20240123_20240514_12_DAILYBUILD |
| Replacement `/Users/j/Desktop/ablnew.img` | d9e74dfff7e2e943267407ca50ab1393b5855d12a71532a8c76b59b81bb3272d | 1048576 | NX729J_Z0_CN_ZML1T_V236/20230701123627 |

Both use the same ELF32 ARM wrapper with one compressed firmware volume containing an ARM64 EFI application. The replacement is a different build, not a small button-only patch. Its additional 835584 file bytes are zero padding; the actual decompressed volume is also different (692424 versus 717000 bytes).

Both binaries contain and reference linux,initrd-start and linux,initrd-end. The inspected initrd-end update code has matching structure: write ramdisk base plus size through corresponding FDT calls (stock RVAs 0x4c3c4/0x4c414; replacement 0x48840/0x48890). Thus the replacement does not simply lack initrd property support. This comparison does not yet isolate the runtime loss of the payload.

ENTRY-03 and ENTRY-04 have identical boot sizes/load addresses, BootShim/FD and appended DTB. ENTRY-04's embedded FAT matches its staged payload, its TOML has the XNU entry, and its USB image hash matches the delivered manifest. The missing-entry message precedes XNU execution; ENTRY-04's crypto fix has not been tested in this failing startup route.

## Working compatibility path

ENTRY-05 now boots with the older Chinese ABL unchanged. Its board shim carries FD, handoff FDT and the unchanged ENTRY-04 FAT volume in the compressed kernel bundle, relocates that bundle inside the existing reserved Kernel range, restores the FD to its original address, and passes the embedded FAT bounds to the shared UniXNURamDiskDxe. Android ramdisk size is zero.

The user tested it on 2026-11-06: payload discovery works and XNU reaches ENTRY-STAGE=3, then panics in AppleARMCPU.cpp:111 (`CPU configuration in device tree is invalid`). The exact older-ABL ramdisk failure was bypassed, not conclusively isolated by binary comparison. The Chinese ABL and working fastboot button combination are mandatory. No ABL flash or change was performed by the assistant.
